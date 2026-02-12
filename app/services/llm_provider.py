import httpx
from openai import AsyncOpenAI
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class LLMProvider:
    """
    Unified interface for Multi-Provider AI.
    Routes: AvalAI (Pro), OpenRouter (Backup), Cloudflare (Fast).
    """

    def __init__(self):
        # 1. Configure AvalAI Client (OpenAI Compatible)
        self.avalai_client = AsyncOpenAI(
            api_key=settings.AVALAI_API_KEY,
            base_url=settings.AVALAI_BASE_URL
        )
        
        # 2. Configure OpenRouter Client (OpenAI Compatible)
        # Note: OpenRouter requires a specific base URL
        self.openrouter_client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        
        # 3. Cloudflare uses native HTTP endpoints (not OpenAI compatible directly)
        self.cf_url = f"https://api.cloudflare.com/client/v4/accounts/{settings.CF_ACCOUNT_ID}/ai/run/{settings.CF_MODEL}"
        self.cf_headers = {
            "Authorization": f"Bearer {settings.CF_API_TOKEN}",
            "Content-Type": "application/json"
        }

    async def generate(self, prompt: str, system_prompt: str, tier: str = "economy", json_mode: bool = False) -> str:
        """
        Generates a response based on the tier.
        tier: 'pro' -> AvalAI (GPT-4o)
        tier: 'backup' -> OpenRouter
        tier: 'economy' -> Cloudflare (Fastest/Free)
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            # TIER 1: PRO (Use AvalAI)
            if tier == "pro":
                logger.info(f"Using AvalAI Pro Model: {settings.AVALAI_MODEL_PRO}")
                response = await self.avalai_client.chat.completions.create(
                    model=settings.AVALAI_MODEL_PRO,
                    messages=messages,
                    response_format={"type": "json_object"} if json_mode else None,
                    temperature=0.3
                )
                return response.choices[0].message.content

            # TIER 2: ECONOMY (Use Cloudflare)
            # Cloudflare is fast and free, ideal for parsing/searching
            elif tier == "economy":
                logger.info(f"Using Cloudflare Model: {settings.CF_MODEL}")
                # Cloudflare Workers AI expects a specific JSON payload
                payload = {
                    "messages": messages
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post(self.cf_url, headers=self.cf_headers, json=payload, timeout=30.0)
                    resp.raise_for_status()
                    data = resp.json()
                    # CF response structure: {"result": {"response": "..."}} or {"result": "string"}
                    # Adjust parsing based on specific CF model output, usually it's result['response']
                    return data.get("result", {}).get("response") or data.get("result")

            # TIER 3: BACKUP (Use OpenRouter)
            else:
                logger.info(f"Using OpenRouter Model: {settings.OPENROUTER_MODEL}")
                response = await self.openrouter_client.chat.completions.create(
                    model=settings.OPENROUTER_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"} if json_mode else None,
                    temperature=0.3
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM Provider Error (Tier: {tier}): {e}")
            # Fallback logic could go here (e.g., try Backup if Pro fails)
            raise e