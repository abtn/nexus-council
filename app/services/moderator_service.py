from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.models.domain import CouncilSession, AgentPersona
from app.services.llm_provider import LLMProvider
from app.schemas.api import ModeratorDecision # Import the new schema
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class ModeratorService:
    def __init__(self):
        self.llm = LLMProvider()

    async def synthesize_session(self, session_id: str, db: AsyncSession):
        """Synthesize all agent reports into final council output."""
        logger.info(f"Moderator starting synthesis for Session: {session_id}")

        session = await db.get(CouncilSession, session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return

        # Load agents
        result = await db.execute(
            select(AgentPersona)
            .where(AgentPersona.session_id == session_id)
            .options(selectinload(AgentPersona.report))
        )
        agents = result.scalars().all()

        # Compile reports
        reports_text = ""
        for agent in agents:
            report_content = agent.report.content if agent.report else "No report submitted."
            reports_text += f"\n=== REPORT FROM: {agent.name} ({agent.role_description}) ===\n{report_content}\n"

        # Determine model
        model_id = settings.MODEL_MODERATOR
        if session.model_config and isinstance(session.model_config, dict):
            model_id = session.model_config.get("moderator", model_id)

        try:
            await self._generate_synthesis(session, reports_text, model_id, db)
        except Exception as e:
            logger.error(f"Synthesis failed: {e}", exc_info=True)
            session.status = "FAILED"
            await db.commit()

    async def _generate_synthesis(self, session: CouncilSession, reports_text: str, model_id: str, db: AsyncSession):
        """Generate synthesis using Instructor for guaranteed structure."""

        system_prompt = f"""
        You are the High Moderator. Synthesize expert reports into a final decision.
        Tone: {session.tone}
        Length: {session.output_length}
        """

        prompt = f"""
        User Query: "{session.user_prompt}"

        Expert Reports:
        {reports_text}

        Synthesize these findings.
        """

        # --- INSTRUCTOR INTEGRATION ---
        # We get a validated Pydantic object directly.
        decision: ModeratorDecision = await self.llm.generate_structured(
            response_model=ModeratorDecision,
            prompt=prompt,
            system_prompt=system_prompt,
            model_id=model_id
        )

        # Map Pydantic fields to Database columns
        session.consensus = decision.consensus
        session.friction = decision.friction
        session.recommendation = decision.recommendation
        session.status = "COMPLETED"

        db.add(session)
        await db.commit()
        logger.info(f"Session {session.id} completed successfully")