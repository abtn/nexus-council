import json
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
        
        Args:
            session: The CouncilSession with mode and config
            decomposition_depth: Number of sub-queries for decomposition mode
            db: Async database session
        """
        # Determine model from config or use default
        model_id = session.model_config.get("architect") if session.model_config else settings.MODEL_ARCHITECT
        
        logger.info(f"Architect blueprinting session {session.id} in mode: {session.mode}")
        
        if session.mode == "quick":
            # Quick Mode: Single agent, no search, direct LLM answer
            await self._quick_strategy(session, model_id, db) # pyright: ignore[reportArgumentType]
        elif session.mode == "decomposition":
            # Decomposition Mode: Break query into parallel sub-research tasks
            await self._decompose_strategy(session, decomposition_depth, model_id, db) # pyright: ignore[reportArgumentType]
        else:
            # Standard Mode: Council of experts with different perspectives
            await self._council_strategy(session, model_id, db) # pyright: ignore[reportArgumentType]

    async def _quick_strategy(self, session: CouncilSession, model_id: str, db: AsyncSession):
        """
        Quick Mode: Create a single 'Flash Expert' agent for direct LLM answering.
        No web search performed - relies entirely on model's internal knowledge.
        """
        logger.info(f"Using Quick Strategy with model: {model_id}")
        
        # Create a single generalist agent
        new_agent = AgentPersona(
            session_id=session.id,
            name="Flash Expert",
            role_description=f"You are a knowledgeable expert. Provide a direct, accurate, and comprehensive answer to the user's question based on your training knowledge. Be concise but thorough. User query: {session.user_prompt}",
            search_queries=[],  # Empty = no web search
            brain_tier="pro"    # Use best available model tier
        )
        db.add(new_agent)
        logger.info(f"Created Flash Expert agent for quick mode (session {session.id})")

    async def _council_strategy(self, session: CouncilSession, model_id: str, db: AsyncSession):
        """
        Standard Mode: Create a council of 3-5 experts with diverse perspectives.
        Each expert researches the topic from their specific angle.
        """
        system_prompt = """
        You are the Council Architect. Analyze the user's complex query and assemble a team of 3-5 virtual experts to answer it comprehensively.
        
        You must output ONLY valid JSON matching this structure. Do not output markdown code blocks, just raw JSON:
        {
            "experts": [
                {
                    "name": "Creative Expert Name (e.g., 'The Economist', 'The Skeptic', 'The Historian')",
                    "role_description": "Detailed system prompt defining this expert's perspective, expertise, and approach to analyzing the topic",
                    "initial_search_queries": ["specific search query 1", "specific search query 2"],
                    "brain_tier": "economy" or "pro"
                }
            ]
        }
        
        Rules:
        - Assign 'pro' tier only to agents requiring complex reasoning or domain expertise
        - Assign 'economy' tier to agents doing simpler information gathering
        - Ensure diverse perspectives that might disagree with each other
        - Each expert should have 1-2 specific search queries to start their research
        """
        await self._generate_and_save(session.user_prompt, system_prompt, model_id, session, db)

    async def _decompose_strategy(self, session: CouncilSession, depth: int, model_id: str, db: AsyncSession):
        """
        Decomposition Mode: Break complex query into {depth} distinct sub-queries.
        Each sub-query becomes an expert agent researched in parallel.
        """
        system_prompt = f"""
        You are a Research Decomposition Specialist. Your task is to break down a complex user query into {depth} distinct, non-overlapping sub-queries that can be researched in parallel.
        
        Each sub-query should focus on a specific angle or aspect of the main topic. Treat each sub-query as an expert agent assignment.
        
        You must output ONLY valid JSON matching this structure:
        {{
            "experts": [
                {{
                    "name": "Research Angle Name (e.g., 'Economic Impact Analysis', 'Technical Feasibility Study')",
                    "role_description": "You are an expert researcher focusing specifically on [this angle]. Your task is to gather facts, data, and insights related to this specific aspect. Be thorough and cite sources.",
                    "initial_search_queries": ["specific sub-query 1", "specific sub-query 2"],
                    "brain_tier": "pro"
                }}
            ]
        }}
        
        Rules:
        - Create exactly {depth} experts (no more, no less)
        - Each expert must have a unique, non-overlapping research angle
        - Sub-queries should be specific enough to yield actionable research results
        - All experts use "pro" brain tier for deep research
        """
        await self._generate_and_save(session.user_prompt, system_prompt, model_id, session, db)

    async def _generate_and_save(self, user_prompt: str, system_prompt: str, model_id: str, session: CouncilSession, db: AsyncSession):
        """
        Generate expert definitions using LLM and save them as AgentPersonas.
        Used by both _council_strategy and _decompose_strategy.
        """
        try:
            raw_content = await self.llm.generate(
                prompt=f"User Query: {user_prompt}\n\nDesign the optimal research team to answer this query comprehensively.",
                system_prompt=system_prompt,
                model_id=model_id,
                json_mode=True
            )

            # Cleanup potential markdown wrapping
            if raw_content.startswith("```json"):
                raw_content = raw_content.strip("`").replace("json", "", 1).strip()
            elif raw_content.startswith("```"):
                raw_content = raw_content.strip("`").strip()

            decision_data = json.loads(raw_content)
            decision = ArchitectDecision(**decision_data)

            # Create AgentPersonas from generated experts
            for expert_def in decision.experts:
                new_agent = AgentPersona(
                    session_id=session.id,
                    name=expert_def.name,
                    role_description=expert_def.role_description,
                    search_queries=expert_def.initial_search_queries,
                    brain_tier=expert_def.brain_tier
                )
                db.add(new_agent)
                logger.info(f"Created agent: {expert_def.name} ({expert_def.brain_tier} tier)")
            
            logger.info(f"Total agents created for session {session.id}: {len(decision.experts)}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Architect LLM output as JSON: {e}")
            logger.error(f"Raw content: {raw_content[:500]}...") # pyright: ignore[reportPossiblyUnboundVariable]
            raise ValueError(f"Architect failed to generate valid expert team: {e}")
        except Exception as e:
            logger.error(f"Error in _generate_and_save: {e}", exc_info=True)
            raise