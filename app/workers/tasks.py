from app.core.database import AsyncSessionLocal
from app.models.domain import AgentPersona, KnowledgeItem, CouncilSession, ExpertReport
from app.services.tools import WebTools
from app.services.analyst_service import AnalystService
from app.services.embedding_service import EmbeddingService
from app.services.moderator_service import ModeratorService
from sqlalchemy import select, func
import logging

logger = logging.getLogger(__name__)

async def enqueue_next_step(ctx, session_id: str, mode: str):
    """
    Helper to determine what to run next based on session mode.
    Replaces the Celery Chord/Link logic.
    """
    if mode == "quick":
        await ctx['redis'].enqueue_job('finalize_quick_session', session_id)
    else:
        await ctx['redis'].enqueue_job('synthesize_council', session_id)

async def execute_expert_search(ctx, agent_id: str, queries: list[str], enable_search: bool, model_config: dict = None):
    """
    Executes research and analysis for a single agent.
    """
    async with AsyncSessionLocal() as db:
        try:
            agent = await db.get(AgentPersona, agent_id)
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                return

            # --- SEARCH PHASE ---
            if enable_search:
                agent.status = "SEARCHING"
                await db.commit()

                logger.info(f"--- Agent {agent.name}: Starting Hunt ---")
                tools = WebTools()
                embedder = EmbeddingService()

                raw_text_content = []
                for query in queries:
                    try:
                        search_results = await tools.search(query, max_results=2)
                        for item in search_results:
                            try:
                                content = await tools.scrape(item['url'])
                                if content:
                                    raw_text_content.append({"url": item['url'], "text": content})
                            except Exception as scrape_error:
                                logger.warning(f"Failed to scrape {item['url']}: {scrape_error}")
                                continue
                    except Exception as search_error:
                        logger.error(f"Search failed for query '{query}': {search_error}")
                        continue

                # Chunk & Embed
                chunks_data = []
                for item in raw_text_content:
                    text = item['text']
                    url = item['url']
                    for i in range(0, len(text), 500):
                        chunk = text[i:i+500]
                        if len(chunk.strip()) > 50:
                            chunks_data.append((chunk, url))

                if chunks_data:
                    logger.info(f"Embedding {len(chunks_data)} chunks for {agent.name}...")
                    try:
                        texts_to_embed = [c[0] for c in chunks_data]
                        # Await the async embedding call
                        embeddings = await embedder.embed_texts(texts_to_embed)
                        for (chunk, url), vector in zip(chunks_data, embeddings):
                            new_item = KnowledgeItem(
                                agent_id=agent.id,
                                source_url=url,
                                content=chunk,
                                embedding=vector
                            )
                            db.add(new_item)
                        await db.commit()
                    except Exception as embed_error:
                        logger.error(f"Embedding failed for {agent.name}: {embed_error}")
                else:
                    logger.warning(f"No content chunks created for {agent.name}")
            else:
                logger.info(f"Agent {agent.name}: Search disabled (Quick Mode).")

            # --- ANALYST PHASE ---
            agent.status = "ANALYZING"
            await db.commit()

            analyst_model = None
            if model_config and isinstance(model_config, dict):
                analyst_model = model_config.get('analyst')

            try:
                analyst = AnalystService()
                await analyst.generate_report(agent_id, db, model_override=analyst_model)
            except Exception as analysis_error:
                logger.error(f"Analysis failed for {agent.name}: {analysis_error}")
                agent.status = "FAILED"
                await db.commit()
                return

            agent.status = "COMPLETED"
            await db.commit()
            logger.info(f"Agent {agent.name}: Analysis complete")

            # --- WORKFLOW ORCHESTRATION (Replacing Chord) ---
            # Check if this was the last agent to finish
            session = await db.get(CouncilSession, agent.session_id)
            if not session:
                return

            # Count total agents vs completed agents
            total_agents = await db.execute(
                select(func.count(AgentPersona.id)).where(AgentPersona.session_id == session.id)
            )
            total_count = total_agents.scalar() or 0

            completed_agents = await db.execute(
                select(func.count(AgentPersona.id)).where(
                    AgentPersona.session_id == session.id,
                    AgentPersona.status == "COMPLETED"
                )
            )
            completed_count = completed_agents.scalar() or 0

            # Also check if any failed to decide if we should proceed or fail
            failed_agents = await db.execute(
                select(func.count(AgentPersona.id)).where(
                    AgentPersona.session_id == session.id,
                    AgentPersona.status == "FAILED"
                )
            )
            failed_count = failed_agents.scalar() or 0

            # If all done (Completed or Failed), trigger the next step
            if (completed_count + failed_count) >= total_count:
                logger.info(f"All agents done for session {session.id}. Triggering final step.")
                await enqueue_next_step(ctx, str(session.id), session.mode)

        except Exception as e:
            logger.error(f"Worker Error in execute_expert_search for agent {agent_id}: {e}", exc_info=True)
            # Attempt to mark as failed
            if 'agent' in locals() and agent:
                agent.status = "FAILED"
                await db.commit()
            # Still trigger next step so session doesn't hang
            if 'session' in locals() and session:
                await enqueue_next_step(ctx, str(session.id), session.mode)

async def finalize_quick_session(ctx, session_id: str):
    """
    Finalizes a Quick Mode session.
    """
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        session = await db.get(CouncilSession, session_id)
        if not session:
            return

        stmt = (
            select(ExpertReport)
            .join(AgentPersona)
            .where(AgentPersona.session_id == session_id)
        )
        report_result = await db.execute(stmt)
        report = report_result.scalars().first()

        if report:
            session.consensus = report.content
            session.status = "COMPLETED"
            session.friction = None
            session.recommendation = None
            await db.commit()
            logger.info(f"Quick Session {session_id} finalized successfully.")
        else:
            logger.error(f"Quick Session {session_id} failed: No report found.")
            session.status = "FAILED"
            await db.commit()

async def synthesize_council(ctx, session_id: str):
    """
    Synthesizes the council using the Moderator service.
    """
    async with AsyncSessionLocal() as db:
        moderator = ModeratorService()
        await moderator.synthesize_session(session_id, db)