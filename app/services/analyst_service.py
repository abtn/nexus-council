from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models.domain import AgentPersona, ExpertReport
from app.services.llm_provider import LLMProvider
from app.services.embedding_service import EmbeddingService
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class AnalystService:
    def __init__(self):
        self.llm = LLMProvider()
        self.embedder = EmbeddingService()

    async def generate_report(self, agent_id: str, db: AsyncSession, model_override: str = None) -> ExpertReport: # pyright: ignore[reportArgumentType]
        # 1. Fetch Agent
        agent = await db.get(AgentPersona, agent_id)
        if not agent:
            raise ValueError("Agent not found")

        # 2. Embed the Agent's perspective (role)
        # Await the async embedding call
        query_vector = await self.embedder.embed_query(agent.role_description)

        # 3. Vector Search
        sql = text("""
            SELECT content, source_url
            FROM knowledge_items
            WHERE agent_id = :agent_id
            ORDER BY embedding <=> :query_vector
            LIMIT 10
        """)

        result = await db.execute(sql, {"agent_id": str(agent_id), "query_vector": str(query_vector)})
        relevant_rows = result.fetchall()

        # 4. Handle Context
        if not relevant_rows:
            # Quick Mode or Search Failed - Fallback to Internal Knowledge
            logger.info(f"Agent {agent.name}: No external context found. Using internal knowledge.")
            context_text = "No external sources. Use your internal knowledge base."
            system_prompt = f"You are {agent.name}. {agent.role_description}. Provide a detailed analysis using your internal knowledge."
        else:
            context_text = ""
            for row in relevant_rows:
                clean_content = row[0][:1500].replace("\n", " ")
                context_text += f"\n--- Source: {row[1]} ---\n{clean_content}\n"
            system_prompt = f"You are {agent.name}. {agent.role_description}. Write a report based ONLY on the provided research."

        prompt = f"""
        ROLE: {agent.role_description}
        
        RESEARCH DATA:
        {context_text}
        
        Write a comprehensive report.
        """

        # 5. Generate with Dynamic Model
        model_to_use = model_override or settings.MODEL_ANALYST
        
        content = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model_id=model_to_use
        )

        # 6. Save Report
        report = ExpertReport(agent_id=agent.id, content=content)
        db.add(report)

        return report