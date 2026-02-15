import asyncio
from celery import chord
from app.workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.domain import AgentPersona, KnowledgeItem
from app.services.tools import WebTools
from app.services.analyst_service import AnalystService
from app.services.embedding_service import EmbeddingService
from app.services.moderator_service import ModeratorService
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@celery_app.task(name="tasks.initiate_hunt")
def initiate_hunt(session_id: str):
    async def _prepare_workflow():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentPersona).where(AgentPersona.session_id == session_id)
            )
            agents = result.scalars().all()
            
            search_tasks = [
                execute_expert_search.s(str(agent.id), agent.search_queries)  # pyright: ignore[reportFunctionMemberAccess]
                for agent in agents
            ]
            
            if not search_tasks:
                logger.warning("No agents found to hunt.")
                return

            workflow = chord(search_tasks, synthesize_council.s(session_id)) # pyright: ignore[reportFunctionMemberAccess]
            workflow.apply_async()
            logger.info(f"Workflow started for Session {session_id}")

    run_async(_prepare_workflow())

@celery_app.task(name="tasks.execute_expert_search", rate_limit="10/m")
def execute_expert_search(agent_id: str, queries: list[str]):
    async def _execute():
        db = AsyncSessionLocal()
        try:
            agent = await db.get(AgentPersona, agent_id)
            if not agent: return "Agent Not Found"

            # 1. Update Status: SEARCHING
            agent.status = "SEARCHING"
            await db.commit()
            
            logger.info(f"--- Agent {agent.name}: Starting Hunt ---")
            tools = WebTools()
            embedder = EmbeddingService()
            
            raw_text_content = []

            # 2. Scrape
            for query in queries:
                search_results = await tools.search(query, max_results=2)
                for item in search_results:
                    content = await tools.scrape(item['url'])
                    if content:
                        raw_text_content.append({"url": item['url'], "text": content})
            
            # 3. Chunk & Embed (WITH URL PRESERVATION)
            chunks_data = [] # List of (text, url)
            for item in raw_text_content:
                text = item['text']
                url = item['url']
                # Create chunks of 500 chars
                for i in range(0, len(text), 500):
                    chunk = text[i:i+500]
                    if len(chunk.strip()) > 50:
                        chunks_data.append((chunk, url))

            if chunks_data:
                logger.info(f"Embedding {len(chunks_data)} chunks for {agent.name}...")
                
                # Extract just text for batch embedding
                texts_to_embed = [c[0] for c in chunks_data]
                embeddings = embedder.embed_texts(texts_to_embed)
                
                # Save to DB
                for (chunk, url), vector in zip(chunks_data, embeddings):
                    new_item = KnowledgeItem(
                        agent_id=agent.id,
                        source_url=url, # <--- FIX: Preserving URL for citation
                        content=chunk,
                        embedding=vector
                    )
                    db.add(new_item)
            
            await db.commit()

            # 4. Update Status: ANALYZING
            agent.status = "ANALYZING"
            await db.commit()

            # 5. Analyze
            analyst = AnalystService()
            await analyst.generate_report(agent_id, db)
            
            # 6. Update Status: COMPLETED
            agent.status = "COMPLETED"
            await db.commit()
            
            return f"Agent {agent.name} Done"

        except Exception as e:
            logger.error(f"Error in expert workflow: {e}")
            # Attempt to mark failed
            try:
                if 'agent' in locals():
                    agent.status = "FAILED" # pyright: ignore[reportPossiblyUnboundVariable, reportOptionalMemberAccess]
                    await db.commit()
            except:
                pass
            return f"Error: {str(e)}"
        finally:
            await db.close()

    return run_async(_execute())

@celery_app.task(name="tasks.synthesize_council")
def synthesize_council(results, session_id: str):
    async def _synthesize():
        logger.info(f"Starting Moderation for Session {session_id}")
        async with AsyncSessionLocal() as db:
            moderator = ModeratorService()
            await moderator.synthesize_session(session_id, db)

    run_async(_synthesize())