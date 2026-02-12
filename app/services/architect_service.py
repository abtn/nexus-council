import json
from app.schemas.api import ArchitectDecision
from app.models.domain import CouncilSession, AgentPersona
from app.core.config import get_settings
from app.services.llm_provider import LLMProvider
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

class ArchitectService:
    def __init__(self):
        self.llm = LLMProvider()

    async def design_council(self, prompt: str, db: AsyncSession) -> CouncilSession:
        system_prompt = """
        You are the Council Architect. Your job is to analyze a user's complex query and assemble a team of 3-5 virtual experts to answer it.
        
        You must output ONLY valid JSON matching this structure. Do not output markdown code blocks, just raw JSON:
        {
            "experts": [
                {
                    "name": "string (Creative Name)",
                    "role_description": "string (System Prompt for the agent)",
                    "initial_search_queries": ["string", "string"],
                    "brain_tier": "economy" or "pro"
                }
            ]
        }
        
        Rules:
        - Assign 'pro' tier only to agents requiring complex reasoning.
        - Ensure diverse perspectives.
        """

        # Call the LLM Provider
        # We turn OFF json_mode in the provider call to rely on prompt instructions for compatibility
        raw_content = await self.llm.generate(
            prompt=f"Design a council for this topic: {prompt}",
            system_prompt=system_prompt,
            tier="pro", # This now maps to deepseek-v3.1
            json_mode=False # Relying on prompt instructions for JSON
        )

        # Clean the response (remove potential markdown formatting)
        if raw_content.startswith("```json"):
            raw_content = raw_content.strip("`").replace("json", "", 1).strip()
        elif raw_content.startswith("```"):
            raw_content = raw_content.strip("`").strip()

        decision_data = json.loads(raw_content)
        decision = ArchitectDecision(**decision_data)

        new_session = CouncilSession(user_prompt=prompt, status="ARCHITECTED")
        db.add(new_session)
        await db.flush()

        for expert_def in decision.experts:
            new_agent = AgentPersona(
                session_id=new_session.id,
                name=expert_def.name,
                role_description=expert_def.role_description,
                search_queries=expert_def.initial_search_queries,
                brain_tier=expert_def.brain_tier
            )
            db.add(new_agent)
        
        return new_session