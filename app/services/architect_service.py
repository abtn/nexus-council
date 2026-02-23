from app.schemas.api import ArchitectDecision
from app.models.domain import CouncilSession, AgentPersona
from app.core.config import get_settings
from app.services.llm_provider import LLMProvider
from sqlalchemy.ext.asyncio import AsyncSession
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class ArchitectService:
    def __init__(self):
        self.llm = LLMProvider()

    async def blueprint_session(self, session: CouncilSession, decomposition_depth: int, db: AsyncSession):
        """
        Routes the session to the correct architectural strategy.
        """
        model_id = session.model_config.get("architect") if session.model_config else settings.MODEL_ARCHITECT
        logger.info(f"Architect blueprinting session {session.id} in mode: {session.mode}")

        if session.mode == "quick":
            await self._quick_strategy(session, db)
        elif session.mode == "decomposition":
            await self._decompose_strategy(session, decomposition_depth, model_id, db)
        else:
            await self._council_strategy(session, model_id, db)

    async def _quick_strategy(self, session: CouncilSession, db: AsyncSession):
        """Quick Mode: Create a single 'Flash Expert' agent."""
        logger.info(f"Using Quick Strategy")
        new_agent = AgentPersona(
            session_id=session.id,
            name="Flash Expert",
            role_description=f"You are a knowledgeable expert. Provide a direct answer. User query: {session.user_prompt}",
            search_queries=[],
            brain_tier="pro"
        )
        db.add(new_agent)

    async def _council_strategy(self, session: CouncilSession, model_id: str, db: AsyncSession):
        """Standard Mode: Create a council using structured LLM output."""
        system_prompt = """
        You are the Council Architect. Assemble a team of 3-5 virtual experts.
        Assign 'pro' tier only to agents requiring complex reasoning.
        Ensure diverse perspectives.
        """
        
        # --- INSTRUCTOR INTEGRATION ---
        # We request the Pydantic model directly. No manual JSON parsing needed.
        decision: ArchitectDecision = await self.llm.generate_structured(
            response_model=ArchitectDecision,
            prompt=f"User Query: {session.user_prompt}\n\nDesign the optimal research team.",
            system_prompt=system_prompt,
            model_id=model_id
        )

        # Save agents
        for expert_def in decision.experts:
            new_agent = AgentPersona(
                session_id=session.id,
                name=expert_def.name,
                role_description=expert_def.role_description,
                search_queries=expert_def.initial_search_queries,
                brain_tier=expert_def.brain_tier
            )
            db.add(new_agent)
            logger.info(f"Created agent: {expert_def.name}")

    async def _decompose_strategy(self, session: CouncilSession, depth: int, model_id: str, db: AsyncSession):
        """Decomposition Mode: Break query into sub-queries."""
        system_prompt = f"""
        You are a Research Decomposition Specialist. Break down the query into exactly {depth} distinct sub-queries.
        Each sub-query becomes an expert agent assignment.
        All experts should use 'pro' brain tier.
        """

        decision: ArchitectDecision = await self.llm.generate_structured(
            response_model=ArchitectDecision,
            prompt=f"User Query: {session.user_prompt}\n\nDecompose this into {depth} research angles.",
            system_prompt=system_prompt,
            model_id=model_id
        )

        for expert_def in decision.experts:
            new_agent = AgentPersona(
                session_id=session.id,
                name=expert_def.name,
                role_description=expert_def.role_description,
                search_queries=expert_def.initial_search_queries,
                brain_tier=expert_def.brain_tier
            )
            db.add(new_agent)
            logger.info(f"Created decomposed agent: {expert_def.name}")