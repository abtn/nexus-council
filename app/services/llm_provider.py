import httpx
from openai import AsyncOpenAI
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class LLMProvider:
    def __init__(self):
        # Initialize clients
        self.avalai_client = AsyncOpenAI(api_key=settings.AVALAI_API_KEY, base_url=settings.AVALAI_BASE_URL)
        self.openrouter_client = AsyncOpenAI(api_key=settings.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
        
        self.cf_url_base = f"https://api.cloudflare.com/client/v4/accounts/{settings.CF_ACCOUNT_ID}/ai/run/"
        self.cf_headers = {"Authorization": f"Bearer {settings.CF_API_TOKEN}"}

    async def generate(self, prompt: str, system_prompt: str, model_id: str, json_mode: bool = False) -> str:
        """
        Dynamically selects the provider based on the model_id string.
        Format: "provider/model_name" (e.g., "avalai/grok-3-mini-fast-beta")
        """
        provider, model_name = model_id.split("/", 1)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Routing LLM call to {provider} with model {model_name}")

        try:
            if provider == "avalai":
                response = await self.avalai_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    response_format={"type": "json_object"} if json_mode else None,
                    temperature=0.3
                )
                return response.choices[0].message.content

            elif provider == "openrouter":
                response = await self.openrouter_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    response_format={"type": "json_object"} if json_mode else None,
                    temperature=0.3
                )
                return response.choices[0].message.content

            elif provider == "cloudflare":
                url = f"{self.cf_url_base}{model_name}"
                payload = {"messages": messages}
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, headers=self.cf_headers, json=payload, timeout=30.0)
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get("result", {}).get("response") or data.get("result")
            
            else:
                raise ValueError(f"Unknown provider: {provider}")

        except Exception as e:
            logger.error(f"LLM Error ({provider}/{model_name}): {e}")
            raise e