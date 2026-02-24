import asyncio
from celery import chord
from app.workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.domain import AgentPersona, KnowledgeItem, CouncilSession, ExpertReport
from app.services.tools import WebTools
from app.services.analyst_service import AnalystService
from app.services.embedding_service import EmbeddingService
from app.services.moderator_service import ModeratorService
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@celery_app.task(name="tasks.finalize_quick_session")
def finalize_quick_session(result, session_id: str):
    """
    Finalizes a Quick Mode session by copying the agent's report 
    directly to the consensus field. No Moderator needed.
    """
    async def _finalize():
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            
            # 1. Get the session
            session = await db.get(CouncilSession, session_id)
            if not session:
                return

            # 2. Get the single agent's report (Quick mode only has 1 agent)
            # We join AgentPersona to ensure we get the report for this session
            stmt = (
                select(ExpertReport)
                .join(AgentPersona)
                .where(AgentPersona.session_id == session_id)
            )
            report_result = await db.execute(stmt)
            report = report_result.scalars().first()

            if report:
                # 3. Copy report content to Consensus (The "Answer")
                session.consensus = report.content
                session.status = "COMPLETED"
                
                # Optional: Clear friction/recommendation if they exist, 
                # as they don't apply to a single direct answer
                session.friction = None
                session.recommendation = None
                
                await db.commit()
                logger.info(f"Quick Session {session_id} finalized successfully.")
            else:
                logger.error(f"Quick Session {session_id} failed: No report found.")
                session.status = "FAILED"
                await db.commit()

    return run_async(_finalize())

@celery_app.task(name="tasks.initiate_hunt")
def initiate_hunt(session_id: str):
    async def _prepare_workflow():
        async with AsyncSessionLocal() as db:
            session = await db.get(CouncilSession, session_id)
            if not session:
                return

            result = await db.execute(
                select(AgentPersona).where(AgentPersona.session_id == session_id)
            )
            agents = result.scalars().all()

            if not agents:
                return

            # Get config from session
            model_config = session.model_config if session.model_config else None

            search_tasks = [
                execute_expert_search.s(
                    str(agent.id),
                    agent.search_queries or [],
                    session.enable_search,
                    model_config
                )
                for agent in agents
            ]

            # =========================================================
            # BRANCHING LOGIC
            # =========================================================
            
            if session.mode == "quick":
                # QUICK MODE: Run agent, then finalize. NO MODERATOR.
                # Since there is only 1 agent in quick mode, we link the finalizer
                # to the first (and only) task.
                if search_tasks:
                    # Run the agent task, and link the finalizer to run after it finishes
                    search_tasks[0].apply_async(link=finalize_quick_session.s(session_id))
                    logger.info(f"Quick workflow initiated for session {session_id}")
            
            else:
                # STANDARD / DECOMPOSITION MODE: Run agents, THEN Moderator (Synthesize).
                from celery import chord
                workflow = chord(search_tasks, synthesize_council.s(session_id))
                workflow.apply_async()
                logger.info(f"Standard/Decomposition workflow initiated for session {session_id}")

    return run_async(_prepare_workflow())

@celery_app.task(name="tasks.execute_expert_search", rate_limit="10/m")
def execute_expert_search(agent_id: str, queries: list[str], enable_search: bool, model_config: dict = None): # pyright: ignore[reportArgumentType]
    """
    Execute expert search and analysis task for a single agent.
    
    Args:
        agent_id: UUID of the agent persona
        queries: List of search queries to execute
        enable_search: Whether to perform web search or skip to analysis
        model_config: Dict with model selections (architect, hunter, analyst, moderator)
                     If None or missing 'analyst' key, uses default model.
    """
    async def _execute():
        db = AsyncSessionLocal()
        try:
            agent = await db.get(AgentPersona, agent_id)
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                return "Agent Not Found"

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
                        embeddings = embedder.embed_texts(texts_to_embed)
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
                logger.info(f"Agent {agent.name}: Search disabled (Quick Mode or user preference).")

            # --- ANALYST PHASE ---
            agent.status = "ANALYZING"
            await db.commit()

            # Get analyst model from config, fallback to default
            analyst_model = None
            if model_config and isinstance(model_config, dict):
                analyst_model = model_config.get('analyst')
                if analyst_model:
                    logger.info(f"Agent {agent.name}: Using configured analyst model: {analyst_model}")
                else:
                    logger.info(f"Agent {agent.name}: No analyst model in config, using default")
            else:
                logger.info(f"Agent {agent.name}: No model config provided, using default")
            
            try:
                analyst = AnalystService()
                await analyst.generate_report(agent_id, db, model_override=analyst_model) # pyright: ignore[reportArgumentType]
            except Exception as analysis_error:
                logger.error(f"Analysis failed for {agent.name}: {analysis_error}")
                raise

            agent.status = "COMPLETED"
            await db.commit()
            logger.info(f"Agent {agent.name}: Analysis complete")
            return f"Agent {agent.name} Done"

        except Exception as e:
            logger.error(f"Worker Error in execute_expert_search for agent {agent_id}: {e}", exc_info=True)
            if 'agent' in locals() and agent: # pyright: ignore[reportPossiblyUnboundVariable]
                try:
                    agent.status = "FAILED"
                    await db.commit()
                except Exception as commit_error:
                    logger.error(f"Failed to update agent status to FAILED: {commit_error}")
            return f"Error: {str(e)}"
        finally:
            await db.close()

    return run_async(_execute())

@celery_app.task(name="tasks.synthesize_council")
def synthesize_council(results, session_id: str):
    async def _synthesize():
        async with AsyncSessionLocal() as db:
            moderator = ModeratorService()
            await moderator.synthesize_session(session_id, db)
    run_async(_synthesize())