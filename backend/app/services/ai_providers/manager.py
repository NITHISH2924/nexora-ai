import logging
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator

from backend.app.config import settings, is_leadership_query
from backend.app.services.ai_providers.base import BaseAIProvider
from backend.app.services.ai_providers.gemini_provider import GeminiProvider
from backend.app.services.ai_providers.openai_provider import OpenAICompatibleProvider
from backend.app.services.ai_providers.anthropic_provider import AnthropicProvider
from backend.app.services.ai_providers.mock_provider import BuiltinSimulationProvider

logger = logging.getLogger("ai_providers.manager")

def compile_system_prompt(custom_prompt: Optional[str] = None) -> str:
    """Compiles the system prompt ensuring NEXORA AI's official leadership identity mandate is always present."""
    base = settings.SYSTEM_IDENTITY_PROMPT
    if custom_prompt and custom_prompt.strip():
        if "Nithish Kumar R" not in custom_prompt and "Dhanushiya S" not in custom_prompt:
            return f"{base}\n\n{custom_prompt.strip()}"
        return custom_prompt.strip()
    return base

class AIProviderManager:
    """Central manager for dispatching model requests to the appropriate AI provider."""

    def __init__(self):
        self.gemini = GeminiProvider()
        
        # OpenAI
        self.openai = OpenAICompatibleProvider(
            provider_id="openai",
            display_name="OpenAI",
            base_url="https://api.openai.com/v1",
            api_key_env_attr="OPENAI_API_KEY",
            models=[
                {
                    "id": "gpt-4o",
                    "name": "GPT-4o",
                    "provider": "openai",
                    "description": "High-intelligence flagship model for advanced reasoning and code.",
                    "contextWindow": "128,000 tokens",
                    "category": "Flagship"
                },
                {
                    "id": "gpt-4o-mini",
                    "name": "GPT-4o Mini",
                    "provider": "openai",
                    "description": "Fast and lightweight model for efficient everyday tasks.",
                    "contextWindow": "128,000 tokens",
                    "category": "Fast & Efficient"
                }
            ]
        )

        # Groq (Llama 3.3)
        self.groq = OpenAICompatibleProvider(
            provider_id="groq",
            display_name="Groq Ultra-Fast",
            base_url="https://api.groq.com/openai/v1",
            api_key_env_attr="GROQ_API_KEY",
            models=[
                {
                    "id": "llama-3.3-70b-versatile",
                    "name": "Llama 3.3 70B (Groq)",
                    "provider": "groq",
                    "description": "Ultra-low latency open weights model running on Groq LPUs.",
                    "contextWindow": "128,000 tokens",
                    "category": "Ultra Speed"
                }
            ]
        )

        # DeepSeek
        self.deepseek = OpenAICompatibleProvider(
            provider_id="deepseek",
            display_name="DeepSeek",
            base_url="https://api.deepseek.com/v1",
            api_key_env_attr="DEEPSEEK_API_KEY",
            models=[
                {
                    "id": "deepseek-chat",
                    "name": "DeepSeek V3",
                    "provider": "deepseek",
                    "description": "Advanced open architecture reasoning and coding model.",
                    "contextWindow": "64,000 tokens",
                    "category": "Reasoning & Code"
                }
            ]
        )

        self.anthropic = AnthropicProvider()
        self.builtin = BuiltinSimulationProvider()

        self.providers: List[BaseAIProvider] = [
            self.gemini,
            self.openai,
            self.anthropic,
            self.groq,
            self.deepseek,
            self.builtin
        ]

    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models and their active status."""
        all_models = []
        for p in self.providers:
            all_models.extend(p.get_supported_models())
        return all_models

    def resolve_provider_and_model(self, requested_model: Optional[str] = None) -> Tuple[BaseAIProvider, str]:
        """Resolves the best provider and concrete model to use."""
        req = (requested_model or settings.DEFAULT_AI_MODEL or "gemini-1.5-flash").lower()

        # Check Gemini
        if "gemini" in req:
            if self.gemini.is_configured:
                return self.gemini, requested_model or "gemini-1.5-flash"
            logger.info("Gemini requested but not configured, attempting fallback")

        # Check OpenAI
        if "gpt" in req:
            if self.openai.is_configured:
                return self.openai, requested_model or "gpt-4o-mini"
            logger.info("OpenAI requested but not configured, attempting fallback")

        # Check Claude
        if "claude" in req:
            if self.anthropic.is_configured:
                return self.anthropic, requested_model or "claude-3-5-sonnet-20241022"
            logger.info("Claude requested but not configured, attempting fallback")

        # Check Groq
        if "llama" in req or "groq" in req:
            if self.groq.is_configured:
                return self.groq, requested_model or "llama-3.3-70b-versatile"

        # Check DeepSeek
        if "deepseek" in req:
            if self.deepseek.is_configured:
                return self.deepseek, requested_model or "deepseek-chat"

        # Find first configured cloud provider if any
        if self.gemini.is_configured:
            return self.gemini, "gemini-1.5-flash"
        if self.openai.is_configured:
            return self.openai, "gpt-4o-mini"
        if self.anthropic.is_configured:
            return self.anthropic, "claude-3-5-sonnet-20241022"

        # Fallback to smart built-in engine
        return self.builtin, "nexora-core-v2"

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> Tuple[str, str]:
        """Generate complete response. Returns (content, actual_model_used)."""
        # 1. Check for official leadership inquiry
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break
        
        if is_leadership_query(last_user_msg):
            provider, actual_model = self.resolve_provider_and_model(model)
            return settings.LEADERSHIP_RESPONSE, actual_model

        # 2. Compile system prompt with official leadership identity
        compiled_sys_prompt = compile_system_prompt(system_prompt)

        provider, actual_model = self.resolve_provider_and_model(model)
        try:
            content = await provider.generate_response(
                messages=messages,
                model=actual_model,
                system_prompt=compiled_sys_prompt,
                temperature=temperature,
                **kwargs
            )
            return content, actual_model
        except Exception as e:
            logger.warning(f"Provider {provider.provider_id} failed with error: {e}. Falling back to builtin engine.")
            content = await self.builtin.generate_response(
                messages=messages,
                model="nexora-core-v2",
                system_prompt=compiled_sys_prompt,
                temperature=temperature,
                **kwargs
            )
            return content, "nexora-core-v2"

    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream response chunks from resolved provider."""
        # 1. Check for official leadership inquiry
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        if is_leadership_query(last_user_msg):
            import asyncio, re
            words = re.findall(r'\S+|\s+', settings.LEADERSHIP_RESPONSE)
            for word in words:
                yield word
                await asyncio.sleep(0.01)
            return

        # 2. Compile system prompt with official leadership identity
        compiled_sys_prompt = compile_system_prompt(system_prompt)

        provider, actual_model = self.resolve_provider_and_model(model)
        try:
            async for chunk in provider.stream_response(
                messages=messages,
                model=actual_model,
                system_prompt=compiled_sys_prompt,
                temperature=temperature,
                **kwargs
            ):
                yield chunk
        except Exception as e:
            logger.warning(f"Provider {provider.provider_id} streaming failed with error: {e}. Falling back to builtin streaming.")
            async for chunk in self.builtin.stream_response(
                messages=messages,
                model="nexora-core-v2",
                system_prompt=compiled_sys_prompt,
                temperature=temperature,
                **kwargs
            ):
                yield chunk

ai_manager = AIProviderManager()

