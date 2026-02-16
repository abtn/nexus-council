from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models.domain import AgentPersona, KnowledgeItem, ExpertReport
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

    async def generate_report(self, agent_id: str, db: AsyncSession) -> ExpertReport:
        # 1. Fetch Agent
        agent = await db.get(AgentPersona, agent_id)
        if not agent:
            raise ValueError("Agent not found")

        # 2. Embed the Agent's perspective (role) to find relevant chunks
        query_vector = self.embedder.embed_query(agent.role_description)
        
        # 3. Vector Search (Cosine Distance)
        # We use str(query_vector) because asyncpg requires a string representation 
        # for vector types when using raw SQL text queries.
        sql = text("""
            SELECT content, source_url 
            FROM knowledge_items 
            WHERE agent_id = :agent_id 
            ORDER BY embedding <=> :query_vector 
            LIMIT 10
        """)
        
        result = await db.execute(
            sql, 
            {
                "agent_id": str(agent_id), 
                "query_vector": str(query_vector)
            }
        )
        relevant_rows = result.fetchall()

        if not relevant_rows:
            logger.warning(f"No knowledge found for agent {agent.name}")
            content = "No external information was found. I am unable to provide a report."
        else:
            # 4. Prepare Context
            context_text = ""
            for row in relevant_rows:
                # row[0] is content, row[1] is source_url
                clean_content = row[0][:1500].replace("\n", " ")
                context_text += f"\n--- Source: {row[1]} ---\n{clean_content}\n"

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
            
            # 5. Generate
            content = await self.llm.generate(
                prompt=prompt,
                system_prompt="You are a specialized AI analyst. Be objective, thorough, and precise.",
                model_id=settings.MODEL_ANALYST
            )

        # 6. Save Report
        report = ExpertReport(agent_id=agent.id, content=content)
        db.add(report)
        
        logger.info(f"Report generated for {agent.name}")
        return report