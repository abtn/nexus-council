import httpx
from openai import AsyncOpenAI
import instructor
from instructor import Mode
from app.core.config import get_settings
from pydantic import BaseModel
from abc import ABC, abstractmethod
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

# =========================================================
# 1. ABSTRACT BASE CLASS (The Strategy Interface)
# =========================================================
class BaseLLMStrategy(ABC):
    """
    Abstract base class that defines the contract for all LLM providers.
    """

    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False) -> str:
        """Generates raw text output."""
        pass

    @abstractmethod
    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model: str):
        """Generates structured Pydantic model output."""
        pass

# =========================================================
# 2. CONCRETE STRATEGIES
# =========================================================

class AvalaiStrategy(BaseLLMStrategy):
    def __init__(self):
        self.raw_client = AsyncOpenAI(api_key=settings.AVALAI_API_KEY, base_url=settings.AVALAI_BASE_URL)
        self.instructor_client = instructor.from_openai(self.raw_client, mode=Mode.JSON)

    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        try:
            response = await self.raw_client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"} if json_mode else None,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Avalai Raw Error: {e}")
            raise e

    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model: str):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        try:
            return await self.instructor_client.chat.completions.create(
                model=model,
                response_model=response_model,
                messages=messages,
                temperature=0.3,
                max_retries=2
            )
        except Exception as e:
            logger.error(f"Avalai Structured Error: {e}")
            raise e


class OpenRouterStrategy(BaseLLMStrategy):
    def __init__(self):
        self.raw_client = AsyncOpenAI(api_key=settings.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
        self.instructor_client = instructor.from_openai(self.raw_client, mode=Mode.JSON)

    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        try:
            response = await self.raw_client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"} if json_mode else None,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenRouter Raw Error: {e}")
            raise e

    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model: str):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        try:
            return await self.instructor_client.chat.completions.create(
                model=model,
                response_model=response_model,
                messages=messages,
                temperature=0.3,
                max_retries=2
            )
        except Exception as e:
            logger.error(f"OpenRouter Structured Error: {e}")
            raise e


class CloudflareStrategy(BaseLLMStrategy):
    def __init__(self):
        self.url_base = f"https://api.cloudflare.com/client/v4/accounts/{settings.CF_ACCOUNT_ID}/ai/run/"
        self.headers = {"Authorization": f"Bearer {settings.CF_API_TOKEN}"}

    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        url = f"{self.url_base}{model}"
        payload = {"messages": messages}
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=self.headers, json=payload, timeout=30.0)
                resp.raise_for_status()
                data = resp.json()
                return data.get("result", {}).get("response") or data.get("result")
        except Exception as e:
            logger.error(f"Cloudflare Error: {e}")
            raise e

    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model: str):
        # Cloudflare Workers AI does not natively support JSON mode/Instructor in the same way OpenAI-compatible APIs do
        raise NotImplementedError("Cloudflare provider does not support Structured/Instructor mode yet.")


# =========================================================
# 3. PROVIDER MANAGER / FACTORY
# =========================================================

class LLMProvider:
    def __init__(self):
        # Initialize available strategies
        self.strategies = {
            "avalai": AvalaiStrategy(),
            "openrouter": OpenRouterStrategy(),
            "cloudflare": CloudflareStrategy()
        }

    def _get_strategy(self, model_id: str) -> BaseLLMStrategy:
        """
        Parses the model_id (e.g., 'avalai/gemma-3-27b-it') and returns the corresponding strategy.
        """
        try:
            provider, model_name = model_id.split("/", 1)
        except ValueError:
            logger.error(f"Invalid model_id format: {model_id}. Expected 'provider/model_name'.")
            raise ValueError(f"Invalid model_id format: {model_id}")

        if provider not in self.strategies:
            raise ValueError(f"Unsupported LLM provider: {provider}")

        return self.strategies[provider]

    async def generate(self, prompt: str, system_prompt: str, model_id: str, json_mode: bool = False) -> str:
        """
        Public method for text generation. Routes to the appropriate strategy.
        """
        strategy = self._get_strategy(model_id)
        
        # Extract model name (remove provider prefix)
        model_name = model_id.split("/", 1)[1]
        
        logger.info(f"Generating text via {strategy.__class__.__name__} with model {model_name}")
        return await strategy.generate_text(prompt, system_prompt, model_name, json_mode)

    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model_id: str):
        """
        Public method for structured generation. Routes to the appropriate strategy.
        """
        strategy = self._get_strategy(model_id)
        
        # Extract model name (remove provider prefix)
        model_name = model_id.split("/", 1)[1]
        
        logger.info(f"Generating structured data via {strategy.__class__.__name__} with model {model_name}")
        return await strategy.generate_structured(response_model, prompt, system_prompt, model_name)