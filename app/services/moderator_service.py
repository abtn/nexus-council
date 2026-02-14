import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.models.domain import CouncilSession, AgentPersona, ExpertReport
from app.services.llm_provider import LLMProvider
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class ModeratorService:
    def __init__(self):
        self.llm = LLMProvider()

    async def synthesize_session(self, session_id: str, db: AsyncSession):
        logger.info(f"Moderator starting synthesis for Session: {session_id}")
        
        # 1. Fetch Session
        session = await db.get(CouncilSession, session_id)
        if not session:
            return

        # 2. Fetch All Agents and their Reports
        # We join AgentPersona -> ExpertReport
        # OPTIMIZED QUERY: Fetch agents AND their reports in one go
        result = await db.execute(
            select(AgentPersona)
            .where(AgentPersona.session_id == session_id)
            .options(selectinload(AgentPersona.report)) # <--- Eager load the report
        )
        agents = result.scalars().all()

        reports_text = ""
        for agent in agents:
            # Now we can access agent.report directly without 'await'
            report = agent.report 
            
            if report:
                reports_text += f"\n=== REPORT FROM: {agent.name} ({agent.role_description}) ===\n"
                reports_text += report.content + "\n"
            else:
                reports_text += f"\n=== REPORT FROM: {agent.name} ===\n(No report submitted - likely due to search failure)\n"

        # 3. Construct System Prompt for Synthesis
        system_prompt = """
        You are the High Moderator of the Nexus Council. 
        Your goal is to synthesize multiple expert reports into a final cohesive decision.
        
        You must output JSON matching this structure:
        {
            "consensus": "The main agreed-upon answer...",
            "friction": "Points where experts disagreed or data was missing...",
            "recommendation": "Final actionable advice..."
        }
        """

        prompt = f"""
        User Query: "{session.user_prompt}"

        Here are the reports from the expert council:
        {reports_text}

        Synthesize these findings into the final JSON format.
        """

        # 4. Generate
        raw_content = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model_id=settings.MODEL_MODERATOR,
            json_mode=True # Gemini handles this well
        )

        # 5. Parse and Save
        try:
            # Clean potential markdown wrapping
            if raw_content.startswith("```json"):
                raw_content = raw_content.strip("`").replace("json", "", 1).strip()
            
            data = json.loads(raw_content)
            
            session.consensus = data.get("consensus")
            session.friction = data.get("friction")
            session.recommendation = data.get("recommendation")
            session.status = "COMPLETED"
            
            db.add(session)
            await db.commit()
            logger.info("Council Session COMPLETED successfully.")
            
        except Exception as e:
            logger.error(f"Failed to parse Moderator output: {e}")
            session.status = "FAILED_MODERATION"
            await db.commit()