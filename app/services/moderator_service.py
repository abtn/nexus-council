import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.models.domain import CouncilSession, AgentPersona
from app.services.llm_provider import LLMProvider
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

        # Load all agents and their reports
        result = await db.execute(
            select(AgentPersona)
            .where(AgentPersona.session_id == session_id)
            .options(selectinload(AgentPersona.report))
        )
        agents = result.scalars().all()

        # Compile reports text
        reports_text = ""
        for agent in agents:
            report_content = agent.report.content if agent.report else "No report submitted."
            reports_text += f"\n=== REPORT FROM: {agent.name} ({agent.role_description}) ===\n{report_content}\n"

        # Determine which model to use
        model_id = settings.MODEL_MODERATOR
        if session.model_config and isinstance(session.model_config, dict):
            configured_moderator = session.model_config.get("moderator")
            if configured_moderator:
                model_id = configured_moderator
                logger.info(f"Using configured moderator model: {model_id}")

        # Generate synthesis
        try:
            await self._generate_synthesis(session, reports_text, model_id, db)
        except Exception as e:
            logger.error(f"Synthesis failed: {e}", exc_info=True)
            session.status = "FAILED"
            await db.commit()

    async def _generate_synthesis(self, session: CouncilSession, reports_text: str, model_id: str, db: AsyncSession):
        """Generate and parse synthesis from LLM."""
        
        # Build system prompt based on mode and tone
        if session.mode == "decomposition":
            system_prompt = f"""
You are a Research Synthesizer. Combine multiple research reports into a unified, coherent response.
Tone: {session.tone}
Length: {session.output_length}

You must output ONLY valid JSON in this exact structure:
{{
    "consensus": "Executive summary combining all research angles...",
    "friction": "Detailed findings from all research angles (markdown supported)...",
    "recommendation": "Key takeaways and actionable insights..."
}}
"""
        else:
            system_prompt = f"""
You are the High Moderator of the Nexus Council. Synthesize expert reports into a final decision.
Tone: {session.tone}
Length: {session.output_length}

You must output ONLY valid JSON in this exact structure:
{{
    "consensus": "The agreed-upon answer...",
    "friction": "Points where experts disagreed or data was missing...",
    "recommendation": "Final actionable advice..."
}}
"""

        prompt = f"""
User Query: "{session.user_prompt}"

Expert Reports:
{reports_text}

Synthesize these findings into the required JSON format.
"""

        # Call LLM
        raw_content = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model_id=model_id,
            json_mode=True
        )

        # Parse with robust error handling
        parsed_data = self._robust_json_parse(raw_content)
        
        if not parsed_data:
            logger.error(f"Failed to parse moderator output. Raw content: {raw_content[:500]}...")
            raise ValueError("Could not parse LLM response as JSON")

        # Extract fields safely
        session.consensus = self._extract_field(parsed_data, ["consensus", "summary", "executive_summary", "conclusion"])
        session.friction = self._extract_field(parsed_data, ["friction", "analysis", "findings", "detailed_analysis", "points"])
        session.recommendation = self._extract_field(parsed_data, ["recommendation", "recommendations", "action", "next_steps", "takeaways"])
        session.status = "COMPLETED"
        
        db.add(session)
        await db.commit()
        logger.info(f"Session {session.id} completed successfully")

    def _robust_json_parse(self, content: str) -> dict:
        """
        Robustly parse JSON content, handling various LLM output formats.
        Returns dict or None if parsing fails.
        """
        if not content or not content.strip():
            return None # pyright: ignore[reportReturnType]
        
        # Clean up markdown formatting
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        try:
            data = json.loads(cleaned)
            
            # Handle case where LLM returns a list instead of dict
            if isinstance(data, list):
                logger.warning(f"LLM returned list instead of dict, attempting to extract or wrap")
                if len(data) > 0 and isinstance(data[0], dict):
                    # Use first item if it's a dict
                    return data[0]
                else:
                    # Wrap list in a dict
                    return {
                        "consensus": str(data),
                        "friction": "Data returned as list",
                        "recommendation": "See consensus"
                    }
            
            # Handle case where LLM returns string
            if isinstance(data, str):
                return {
                    "consensus": data,
                    "friction": "Response returned as string",
                    "recommendation": "See consensus"
                }
            
            return data if isinstance(data, dict) else None # pyright: ignore[reportReturnType]
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            # Try to extract JSON from text
            try:
                # Find JSON object in text
                start = cleaned.find('{')
                end = cleaned.rfind('}')
                if start != -1 and end != -1 and end > start:
                    json_str = cleaned[start:end+1]
                    return json.loads(json_str)
            except Exception:
                pass
            return None # pyright: ignore[reportReturnType]

    def _extract_field(self, data: dict, possible_keys: list) -> str:
        """
        Extract a field from dict, trying multiple possible key names.
        Returns string value or default message.
        """
        if not isinstance(data, dict):
            return f"Invalid data type: {type(data).__name__}"
        
        for key in possible_keys:
            if key in data:
                value = data[key]
                # Convert various types to string
                if isinstance(value, str):
                    return value
                elif isinstance(value, (list, dict)):
                    return json.dumps(value, indent=2)
                else:
                    return str(value)
        
        # If no keys found, return all data as string
        return json.dumps(data, indent=2)[:2000]  # Limit length