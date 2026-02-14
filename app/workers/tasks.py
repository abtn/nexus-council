import asyncio
from celery import chord
from app.workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.domain import AgentPersona, KnowledgeItem
from app.services.tools import WebTools
from app.services.llm_provider import LLMProvider
from app.services.analyst_service import AnalystService # <--- Added
from app.services.moderator_service import ModeratorService # <--- Added
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@celery_app.task(name="tasks.initiate_hunt")
def initiate_hunt(session_id: str):
    """
    Orchestrator. 
    Uses a 'chord' to run all searches in parallel, 
    then triggers the moderator once all are done.
    """
    async def _prepare_workflow():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentPersona).where(AgentPersona.session_id == session_id)
            )
            agents = result.scalars().all()
            
            # Create a list of signatures (tasks to be executed)
            search_tasks = [
                execute_expert_search.s(str(agent.id), agent.search_queries) 
                for agent in agents
            ]
            
            if not search_tasks:
                logger.warning("No agents found to hunt.")
                return

            # CHORD: execute search_tasks (parallel), then call synthesize_council (callback)
            workflow = chord(
                search_tasks,
                synthesize_council.s(session_id)
            )
            workflow.apply_async()
            logger.info(f"Workflow started for Session {session_id} with {len(search_tasks)} agents.")

    run_async(_prepare_workflow())

@celery_app.task(name="tasks.execute_expert_search", rate_limit="10/m")
def execute_expert_search(agent_id: str, queries: list[str]):
    """
    Worker Phase 1 & 2: Search -> Scrape -> Analyze
    """
    async def _execute():
        db = AsyncSessionLocal()
        try:
            agent = await db.get(AgentPersona, agent_id)
            if not agent: return "Agent Not Found"

            logger.info(f"--- Agent {agent.name}: Starting Hunt ---")
            tools = WebTools()
            
            # 1. HUNT
            for query in queries:
                search_results = await tools.search(query, max_results=2) # Keep low for dev
                for item in search_results:
                    content = await tools.scrape(item['url'])
                    if content:
                        new_item = KnowledgeItem(
                            agent_id=agent.id,
                            source_url=item['url'],
                            content=content
                        )
                        db.add(new_item)
            
            await db.commit() # Save knowledge before analysis

            # 2. ANALYZE (New Phase)
            logger.info(f"--- Agent {agent.name}: Starting Analysis ---")
            analyst = AnalystService()
            await analyst.generate_report(agent_id, db)
            
            await db.commit() # Save report
            return f"Agent {agent.name} Done"

        except Exception as e:
            logger.error(f"Error in expert workflow: {e}")
            await db.rollback()
            return f"Error: {str(e)}"
        finally:
            await db.close()

    return run_async(_execute())

@celery_app.task(name="tasks.synthesize_council")
def synthesize_council(results, session_id: str):
    """
    Worker Phase 3: Moderator
    This runs only after all execute_expert_search tasks finish.
    'results' argument is required by Celery chord callback (contains return values of previous tasks)
    """
    async def _synthesize():
        logger.info(f"All agents finished. Starting Moderation for Session {session_id}")
        logger.info(f"Agent Results: {results}")
        
        async with AsyncSessionLocal() as db:
            moderator = ModeratorService()
            await moderator.synthesize_session(session_id, db)

    run_async(_synthesize())