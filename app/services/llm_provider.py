import httpx
from openai import AsyncOpenAI
import instructor
from instructor import Mode
from app.core.config import get_settings
from pydantic import BaseModel
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class LLMProvider:
    def __init__(self):
        # --- 1. RAW CLIENTS (For standard text generation) ---
        # Used by Analyst for reports, and Hunter for search queries
        self.raw_avalai = AsyncOpenAI(api_key=settings.AVALAI_API_KEY, base_url=settings.AVALAI_BASE_URL)
        self.raw_openrouter = AsyncOpenAI(api_key=settings.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")

        # --- 2. STRUCTURED CLIENTS (For JSON validation) ---
        # Used by Architect and Moderator for strict Pydantic schema enforcement
        self.instructor_avalai = instructor.from_openai(
            self.raw_avalai, 
            mode=Mode.JSON
        )
        self.instructor_openrouter = instructor.from_openai(
            self.raw_openrouter, 
            mode=Mode.JSON
        )

        # Cloudflare (httpx based) remains unchanged
        self.cf_url_base = f"https://api.cloudflare.com/client/v4/accounts/{settings.CF_ACCOUNT_ID}/ai/run/"
        self.cf_headers = {"Authorization": f"Bearer {settings.CF_API_TOKEN}"}

    async def generate(self, prompt: str, system_prompt: str, model_id: str, json_mode: bool = False) -> str:
        """
        Standard generation (returns string). 
        Uses RAW clients to allow free-form text output.
        """
        provider, model_name = model_id.split("/", 1)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Routing RAW LLM call to {provider} with model {model_name}")

        try:
            if provider == "avalai":
                # Use the raw client, NOT the instructor client
                response = await self.raw_avalai.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    response_format={"type": "json_object"} if json_mode else None,
                    temperature=0.3
                )
                return response.choices[0].message.content

            elif provider == "openrouter":
                # Use the raw client
                response = await self.raw_openrouter.chat.completions.create(
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

    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model_id: str):
        """
        Structured generation using Instructor.
        Returns a validated Pydantic model instance.
        """
        provider, model_name = model_id.split("/", 1)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        logger.info(f"Routing STRUCTURED LLM call to {provider} with model {model_name}")

        if provider == "cloudflare":
            raise NotImplementedError("Cloudflare provider does not support Instructor/Structured mode.")

        # Select the INSTRUCTOR patched client
        client = self.instructor_avalai if provider == "avalai" else self.instructor_openrouter

        try:
            return await client.chat.completions.create(
                model=model_name,
                response_model=response_model,
                messages=messages,
                temperature=0.3,
                max_retries=2
            )
        except Exception as e:
            logger.error(f"Structured LLM Error ({provider}/{model_name}): {e}")
            raise e