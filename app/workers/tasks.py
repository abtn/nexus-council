import asyncio
from celery import group
from app.workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.domain import AgentPersona, KnowledgeItem
from app.services.tools import TavilyService
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@celery_app.task(name="tasks.initiate_hunt")
def initiate_hunt(session_id: str):
    async def _hunt():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentPersona).where(AgentPersona.session_id == session_id)
            )
            agents = result.scalars().all()
            
            if not agents:
                return

            job = group(
                execute_expert_search.s(str(agent.id), agent.search_queries) 
                for agent in agents
            )
            job.apply_async()
            logger.info(f"Dispatched {len(agents)} hunters.")

    run_async(_hunt())

@celery_app.task(name="tasks.execute_expert_search")
def execute_expert_search(agent_id: str, queries: list[str]):
    async def _search():
        async with AsyncSessionLocal() as db:
            tavily = TavilyService()
            agent = await db.get(AgentPersona, agent_id)
            if not agent: return

            logger.info(f"Agent {agent.name} hunting...")
            for query in queries:
                urls = await tavily.search(query)
                content = await tavily.scrape_urls(urls)
                
                for url, text in content.items():
                    if text:
                        item = KnowledgeItem(
                            agent_id=agent.id,
                            source_url=url,
                            content=text
                        )
                        db.add(item)
            
            await db.commit()
            logger.info(f"Agent {agent.name} finished.")

    run_async(_search())