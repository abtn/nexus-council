from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.domain import AgentPersona, KnowledgeItem, ExpertReport
from app.services.llm_provider import LLMProvider
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class AnalystService:
    def __init__(self):
        self.llm = LLMProvider()

    async def generate_report(self, agent_id: str, db: AsyncSession) -> ExpertReport:
        # 1. Fetch Agent
        agent = await db.get(AgentPersona, agent_id)
        if not agent:
            raise ValueError("Agent not found")

        # 2. Fetch Knowledge
        result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.agent_id == agent_id)
        )
        knowledge_items = result.scalars().all()

        if not knowledge_items:
            logger.warning(f"No knowledge found for agent {agent.name}")
            content = "No external information was found. I am unable to provide a report."
        else:
            # 3. Prepare Context
            # We truncate content to ensure we don't blow up the context window of smaller models
            context_text = ""
            for k in knowledge_items:
                # Take first 1500 chars per source to keep it tight
                clean_content = k.content[:1500].replace("\n", " ") 
                context_text += f"\n--- Source: {k.source_url} ---\n{clean_content}\n"

            prompt = f"""
            You are {agent.name}.
            Your Role: {agent.role_description}
            
            You have just completed your research. Write a comprehensive expert report based ONLY on the source material provided below.
            
            Format requirements:
            - Start with a clear summary of findings.
            - Use bullet points for key facts.
            - Cite your sources explicitly (e.g., [Source: url]).
            - If sources conflict, note the discrepancy.
            
            RESEARCH MATERIAL:
            {context_text}
            """
            
            logger.info(f"Agent {agent.name} is analyzing research data...")
            
            # 4. Generate
            content = await self.llm.generate(
                prompt=prompt,
                system_prompt="You are a specialized AI analyst. Be objective, thorough, and precise.",
                model_id=settings.MODEL_ANALYST
            )

        # 5. Save Report
        report = ExpertReport(agent_id=agent.id, content=content)
        db.add(report)
        # We don't commit here, we let the caller (Task) commit to keep transaction atomic
        
        logger.info(f"Report generated for {agent.name}")
        return report