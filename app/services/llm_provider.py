import httpx
import json
import re
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
    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False, max_tokens: int = None) -> str:
        """Generates raw text output."""
        pass

    @abstractmethod
    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model: str):
        """Generates structured Pydantic model output."""
        pass

# =========================================================
# 2. GENERAL CONCRETE STRATEGIES
# =========================================================

class OpenAIStrategy(BaseLLMStrategy):
    """
    Reusable strategy for any provider compatible with the OpenAI API format 
    (e.g., AvalAI, OpenRouter, LocalAI, vLLM).
    """
    def __init__(self, api_key: str, base_url: str):
        self.raw_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.instructor_client = instructor.from_openai(self.raw_client, mode=Mode.JSON)

    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False, max_tokens: int = None) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        payload = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"} if json_mode else None,
            "temperature": 0.3
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        try:
            response = await self.raw_client.chat.completions.create(**payload)
            return response.choices[0].message.content
            
        except Exception as e:
            # GENERAL FIX: Some OpenAI-compatible endpoints (like certain AvalAI models) 
            # reject the "system" role. We catch this specific error and retry by merging 
            # the system prompt into the user prompt.
            error_message = str(e)
            if "Developer instruction is not enabled" in error_message:
                logger.warning(f"Model {model} rejected system role. Retrying with merged prompt...")
                
                merged_prompt = f"SYSTEM INSTRUCTION:\n{system_prompt}\n\nUSER QUERY:\n{prompt}"
                retry_messages = [{"role": "user", "content": merged_prompt}]
                
                payload["messages"] = retry_messages
                response = await self.raw_client.chat.completions.create(**payload)
                return response.choices[0].message.content
            else:
                logger.error(f"OpenAI-compatible API Error: {e}")
                raise e

    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model: str):
        # Note: We rely on the global fallback in LLMProvider if this raises NotImplementedError,
        # but we try native Instructor mode first.
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
            # Retry logic for system prompt rejection applies here too
            if "Developer instruction is not enabled" in str(e):
                logger.warning(f"Model {model} rejected system role in structured mode. Retrying merged...")
                merged_prompt = f"SYSTEM INSTRUCTION:\n{system_prompt}\n\nUSER QUERY:\n{prompt}"
                retry_messages = [{"role": "user", "content": merged_prompt}]
                return await self.instructor_client.chat.completions.create(
                    model=model,
                    response_model=response_model,
                    messages=retry_messages,
                    temperature=0.3,
                    max_retries=2
                )
            logger.error(f"OpenAI-compatible Structured Error: {e}")
            raise e


class CloudflareStrategy(BaseLLMStrategy):
    """
    Strategy for Cloudflare Workers AI.
    Uses raw HTTP requests via httpx.
    """
    def __init__(self):
        self.url_base = f"https://api.cloudflare.com/client/v4/accounts/{settings.CF_ACCOUNT_ID}/ai/run/"
        self.headers = {"Authorization": f"Bearer {settings.CF_API_TOKEN}"}

    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False, max_tokens: int = 1024) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        url = f"{self.url_base}{model}"
        
        payload = {
            "messages": messages,
            "max_tokens": max_tokens
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=self.headers, json=payload, timeout=60.0)
                resp.raise_for_status()
                data = resp.json()
                return data.get("result", {}).get("response") or data.get("result")
        except Exception as e:
            logger.error(f"Cloudflare Error: {e}")
            raise e

    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model: str):
        # We intentionally raise this to trigger the global prompt engineering fallback
        raise NotImplementedError("Cloudflare provider does not support Structured/Instructor mode natively.")


# =========================================================
# 3. PROVIDER MANAGER / FACTORY
# =========================================================

class LLMProvider:
    def __init__(self):
        # Initialize strategies.
        # Notice how AvalAI and OpenRouter now use the SAME class (OpenAIStrategy).
        self.strategies = {
            "avalai": OpenAIStrategy(
                api_key=settings.AVALAI_API_KEY, 
                base_url=settings.AVALAI_BASE_URL
            ),
            "openrouter": OpenAIStrategy(
                api_key=settings.OPENROUTER_API_KEY, 
                base_url="https://openrouter.ai/api/v1"
            ),
            "cloudflare": CloudflareStrategy()
        }

    async def _generate_structured_via_prompt_engineering(
        self, 
        response_model: type[BaseModel], 
        prompt: str, 
        system_prompt: str, 
        strategy: BaseLLMStrategy,
        model_name: str
    ):
        """
        Universal Fallback method.
        Used when a provider doesn't support native Structured Output.
        1. Injects JSON schema into the prompt.
        2. Requests raw text.
        3. Parses and validates the result.
        """
        logger.warning(f"Fallback triggered: Using prompt engineering for {model_name}")

        # 1. Get the JSON schema
        schema = response_model.model_json_schema()

        # 2. Construct the strict system prompt
        strict_system_prompt = f"""
        {system_prompt}

        CRITICAL INSTRUCTION:
        You must respond with a valid JSON object that strictly conforms to the following JSON Schema.
        Do not include any conversational text outside the JSON.
        Do not use markdown code blocks (like ```json). 
        Just return the raw JSON string.

        JSON Schema:
        {json.dumps(schema, indent=2)}
        """

        # 3. Generate text using the strategy's standard text method
        # We request 4096 tokens to ensure the model has enough space
        try:
            raw_content = await strategy.generate_text(
                prompt, 
                strict_system_prompt, 
                model_name, 
                json_mode=False, 
                max_tokens=4096
            )
        except Exception as e:
            logger.error(f"Fallback generation failed: {e}")
            raise e

        # 4. Clean the response (Remove Markdown)
        cleaned_content = raw_content.strip()
        if "```json" in cleaned_content:
            cleaned_content = re.sub(r'^```json\s*', '', cleaned_content)
        if "```" in cleaned_content:
            cleaned_content = re.sub(r'\s*```$', '', cleaned_content)

        # 5. Parse JSON
        try:
            data_dict = json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            logger.error(f"Fallback failed to parse JSON: {e}")
            logger.error(f"Raw Content: {raw_content}")
            raise ValueError(f"Fallback: Model returned invalid JSON: {e}")

        # 6. Validate against Pydantic model
        try:
            return response_model(**data_dict)
        except Exception as e:
            logger.error(f"Fallback validation failed: {e}")
            logger.error(f"Data received: {data_dict}")
            raise ValueError(f"Fallback: Response did not match schema: {e}")

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
        Public method for structured generation. 
        Routes to the appropriate strategy. Falls back to prompt engineering if native mode is not supported.
        """
        strategy = self._get_strategy(model_id)
        model_name = model_id.split("/", 1)[1]

        logger.info(f"Attempting structured generation via {strategy.__class__.__name__} with model {model_name}")

        try:
            # Try native structured generation (Instructor/OpenAI JSON mode)
            return await strategy.generate_structured(response_model, prompt, system_prompt, model_name)
        except (NotImplementedError, Exception) as e:
            # Catch specific errors or general API errors regarding structured mode
            logger.warning(f"Native structured generation failed for {model_id}: {e}")
            logger.info("Switching to Prompt Engineering Fallback...")
            
            # Use the generic fallback method
            return await self._generate_structured_via_prompt_engineering(
                response_model, prompt, system_prompt, strategy, model_name
            )