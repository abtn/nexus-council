import asyncio
from app.workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.domain import AgentPersona, KnowledgeItem
from app.services.tools import WebTools
from app.services.llm_provider import LLMProvider
from app.core.config import get_settings
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@celery_app.task(name="tasks.initiate_hunt")
def initiate_hunt(session_id: str):
    """
    Orchestrator. Creates sub-tasks for each agent.
    Celery will handle queuing them.
    """
    async def _hunt():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentPersona).where(AgentPersona.session_id == session_id)
            )
            agents = result.scalars().all()
            
            # We dispatch them one by one. 
            # Because execute_expert_search has a rate_limit, Celery will 
            # automatically queue them and execute them slowly.
            for agent in agents:
                logger.info(f"Queueing hunt for Agent: {agent.name}")
                execute_expert_search.delay(str(agent.id), agent.search_queries)

    run_async(_hunt())

# RATE LIMIT: "10/m" means 10 tasks per minute.
# Adjust this based on your Tavily/LLM limits.
@celery_app.task(name="tasks.execute_expert_search", rate_limit="10/m")
def execute_expert_search(agent_id: str, queries: list[str]):
    """
    The Worker. Performs Search -> Scrape -> Store.
    Rate limited to prevent API bans.
    """
    async def _search():
        db = AsyncSessionLocal()
        try:
            agent = await db.get(AgentPersona, agent_id)
            if not agent: return

            tools = WebTools()
            llm = LLMProvider()

            for query in queries:
                # 1. Search
                search_results = await tools.search(query)
                
                for item in search_results:
                    url = item['url']
                    
                    # 2. Scrape
                    content = await tools.scrape(url)
                    
                    if content:
                        # 3. Store Knowledge
                        # In a full pipeline, we would embed here.
                        # For now, we just store the text.
                        new_item = KnowledgeItem(
                            agent_id=agent.id,
                            source_url=url,
                            content=content[:5000] # Truncate for safety
                        )
                        db.add(new_item)
                        logger.info(f"Stored knowledge for {agent.name} from {url}")
            
            await db.commit()
            logger.info(f"Agent {agent.name} finished research.")

        except Exception as e:
            logger.error(f"Error in expert search: {e}")
            await db.rollback()
        finally:
            await db.close()

    run_async(_search())