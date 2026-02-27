import httpx
import json
import re
import logging
from abc import ABC, abstractmethod

from openai import AsyncOpenAI
import instructor
from instructor import Mode
from pydantic import BaseModel

from app.core.config import get_settings

# =========================================================
# CONFIGURATION & LOGGING
# =========================================================

settings = get_settings()
logger = logging.getLogger(__name__)

# =========================================================
# 1. ABSTRACT BASE STRATEGY (The Interface)
# =========================================================

class BaseLLMStrategy(ABC):
    """
    Abstract Base Class defining the contract for all LLM providers.
    
    This enforces a standard interface so the main LLMProvider can switch
    between different backends (OpenAI, Cloudflare, etc.) without knowing
    implementation details.
    """
    
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False, max_tokens: int = None) -> str:
        """Generates raw text completion."""
        pass

    @abstractmethod
    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model: str):
        """Generates structured output conforming to a Pydantic model."""
        pass

# =========================================================
# 2. CONCRETE STRATEGIES
# =========================================================

class OpenAIStrategy(BaseLLMStrategy):
    """
    Strategy for OpenAI-compatible APIs (OpenAI, AvalAI, OpenRouter, vLLM).
    
    Leverages the `openai` Python client for text generation and `instructor`
    for structured output.
    """
    
    def __init__(self, api_key: str, base_url: str):
        # Initialize the standard OpenAI async client
        self.raw_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        
        # Wrap the client with Instructor for structured data extraction
        self.instructor_client = instructor.from_openai(self.raw_client, mode=Mode.JSON)

    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False, max_tokens: int = None) -> str:
        """Generates text using the OpenAI Chat Completion API."""
        
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
            # RESILIENCE FIX:
            # Some providers (e.g., AvalAI Gemma) reject the 'system' role.
            # We catch this specific error and retry by merging system instructions
            # into the user prompt.
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
        """Generates structured output using Instructor library."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            # Uses Instructor's patched client to handle schema validation
            return await self.instructor_client.chat.completions.create(
                model=model,
                response_model=response_model,
                messages=messages,
                temperature=0.3,
                max_retries=2
            )
        except Exception as e:
            # Retry logic for system role rejection in structured mode
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
    
    Uses raw HTTP requests via `httpx` because Cloudflare's API format
    differs slightly and doesn't always support the OpenAI SDK features.
    """
    
    def __init__(self):
        self.url_base = f"https://api.cloudflare.com/client/v4/accounts/{settings.CF_ACCOUNT_ID}/ai/run/"
        self.headers = {"Authorization": f"Bearer {settings.CF_API_TOKEN}"}
        
        # PERFORMANCE FIX: Persistent HTTP Client
        # We create the client once to enable connection pooling (Keep-Alive),
        # avoiding the overhead of establishing a new TCP/SSL connection for every request.
        self.http_client = httpx.AsyncClient(timeout=60.0)

    async def generate_text(self, prompt: str, system_prompt: str, model: str, json_mode: bool = False, max_tokens: int = 1024) -> str:
        """Generates text via raw HTTP POST to Cloudflare endpoint."""
        
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
            # Use the persistent client instance
            resp = await self.http_client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            
            data = resp.json()
            # Cloudflare returns result nested under 'result'
            return data.get("result", {}).get("response") or data.get("result")
        except Exception as e:
            logger.error(f"Cloudflare Error: {e}")
            raise e

    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model: str):
        # Cloudflare does not natively support Instructor/JSON mode in this implementation.
        # Raising this error triggers the global fallback in LLMProvider.
        raise NotImplementedError("Cloudflare provider does not support Structured/Instructor mode natively.")

# =========================================================
# 3. PROVIDER MANAGER (The Factory)
# =========================================================

class LLMProvider:
    """
    Main entry point for LLM interactions.
    
    Responsibilities:
    1. Route requests to the correct Strategy based on the model_id prefix.
    2. Handle fallback logic if a provider doesn't support structured output.
    3. Manage provider initialization.
    """

    def __init__(self):
        # Initialize strategies on startup.
        # OpenAI Strategy is reused for AvalAI and OpenRouter as they share the same API spec.
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
        Universal Fallback for Structured Output.
        
        Triggered when a provider (like Cloudflare) raises NotImplementedError.
        This method forces JSON compliance via strict prompt instructions.
        """
        logger.warning(f"Fallback triggered: Using prompt engineering for {model_name}")

        # 1. Inject JSON Schema into the prompt
        schema = response_model.model_json_schema()

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

        # 2. Generate text using the strategy's standard text method
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

        # 3. Clean the response (Remove potential Markdown wrappers)
        cleaned_content = raw_content.strip()
        if "```json" in cleaned_content:
            cleaned_content = re.sub(r'^```json\s*', '', cleaned_content)
        if "```" in cleaned_content:
            cleaned_content = re.sub(r'\s*```$', '', cleaned_content)

        # 4. Parse and Validate
        try:
            data_dict = json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            logger.error(f"Fallback failed to parse JSON: {e}")
            logger.error(f"Raw Content: {raw_content}")
            raise ValueError(f"Fallback: Model returned invalid JSON: {e}")

        try:
            return response_model(**data_dict)
        except Exception as e:
            logger.error(f"Fallback validation failed: {e}")
            logger.error(f"Data received: {data_dict}")
            raise ValueError(f"Fallback: Response did not match schema: {e}")

    def _get_strategy(self, model_id: str) -> BaseLLMStrategy:
        """
        Parses the model_id string to identify the provider and returns the
        corresponding strategy instance.
        
        Example: 'avalai/gemma-3-27b-it' -> returns self.strategies['avalai']
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
        Public method for raw text generation.
        """
        strategy = self._get_strategy(model_id)
        model_name = model_id.split("/", 1)[1]

        logger.info(f"Generating text via {strategy.__class__.__name__} with model {model_name}")
        return await strategy.generate_text(prompt, system_prompt, model_name, json_mode)

    async def generate_structured(self, response_model: type[BaseModel], prompt: str, system_prompt: str, model_id: str):
        """
        Public method for structured generation.
        
        Attempts native structured generation first. If unsupported or failed,
        falls back to prompt engineering.
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