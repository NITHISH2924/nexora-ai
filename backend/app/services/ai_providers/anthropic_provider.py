import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
import httpx

from backend.app.config import settings
from backend.app.services.ai_providers.base import BaseAIProvider

logger = logging.getLogger("ai_provider.anthropic")

class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude AI Provider."""

    BASE_URL = "https://api.anthropic.com/v1"

    MODELS = [
        {
            "id": "claude-3-5-sonnet-20241022",
            "name": "Claude 3.5 Sonnet",
            "provider": "anthropic",
            "description": "Anthropic's most intelligent model with exceptional coding, analysis, and nuanced writing.",
            "contextWindow": "200,000 tokens",
            "category": "High Intelligence & Coding",
            "isDefault": False
        },
        {
            "id": "claude-3-haiku-20240307",
            "name": "Claude 3 Haiku",
            "provider": "anthropic",
            "description": "Fast and compact model for near-instant responsiveness.",
            "contextWindow": "200,000 tokens",
            "category": "Fast & Responsive",
            "isDefault": False
        }
    ]

    @property
    def provider_id(self) -> str:
        return "anthropic"

    @property
    def display_name(self) -> str:
        return "Anthropic Claude"

    @property
    def is_configured(self) -> bool:
        return bool(settings.ANTHROPIC_API_KEY and len(settings.ANTHROPIC_API_KEY.strip()) > 5)

    def get_supported_models(self) -> List[Dict[str, Any]]:
        models = []
        for m in self.MODELS:
            m_copy = m.copy()
            m_copy["available"] = self.is_configured
            models.append(m_copy)
        return models

    def _prepare_payload(self, messages: List[Dict[str, str]], system_prompt: Optional[str], model: str, max_tokens: int, temperature: float, stream: bool) -> Dict[str, Any]:
        formatted_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content.strip() or role == "system":
                continue
            formatted_messages.append({
                "role": "user" if role == "user" else "assistant",
                "content": content
            })

        payload = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "stream": stream
        }
        if system_prompt and system_prompt.strip():
            payload["system"] = system_prompt.strip()
        return payload

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-3-5-sonnet-20241022",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ) -> str:
        if not self.is_configured:
            raise ValueError("Anthropic API key is not configured in environment (ANTHROPIC_API_KEY).")

        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = self._prepare_payload(messages, system_prompt, model, max_tokens or 4096, temperature, stream=False)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.BASE_URL}/messages", headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Anthropic API error: {resp.status_code} - {resp.text}")
            
            data = resp.json()
            content_blocks = data.get("content", [])
            return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-3-5-sonnet-20241022",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        if not self.is_configured:
            raise ValueError("Anthropic API key is not configured in environment (ANTHROPIC_API_KEY).")

        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = self._prepare_payload(messages, system_prompt, model, max_tokens or 4096, temperature, stream=True)

        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", f"{self.BASE_URL}/messages", headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err = await response.aread()
                    raise RuntimeError(f"Anthropic streaming error ({response.status_code}): {err.decode('utf-8')}")

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    try:
                        chunk = json.loads(data_str)
                        if chunk.get("type") == "content_block_delta":
                            delta = chunk.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    yield text
                    except json.JSONDecodeError:
                        continue
