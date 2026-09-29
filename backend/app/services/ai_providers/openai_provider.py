import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
import httpx

from backend.app.config import settings
from backend.app.services.ai_providers.base import BaseAIProvider

logger = logging.getLogger("ai_provider.openai")

class OpenAICompatibleProvider(BaseAIProvider):
    """Universal OpenAI-compatible provider (OpenAI, Groq, DeepSeek, Local Ollama)."""

    def __init__(
        self,
        provider_id: str = "openai",
        display_name: str = "OpenAI",
        base_url: str = "https://api.openai.com/v1",
        api_key_env_attr: str = "OPENAI_API_KEY",
        models: Optional[List[Dict[str, Any]]] = None
    ):
        self._provider_id = provider_id
        self._display_name = display_name
        self._base_url = base_url.rstrip("/")
        self._api_key_attr = api_key_env_attr
        self._models = models or [
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "provider": "openai",
                "description": "Flagship multimodal intelligence for complex problem solving and code.",
                "contextWindow": "128,000 tokens",
                "category": "High Intelligence",
                "isDefault": False
            },
            {
                "id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "provider": "openai",
                "description": "Fast, cost-efficient model for quick answers, lightweight reasoning, and summaries.",
                "contextWindow": "128,000 tokens",
                "category": "Fast & Lightweight",
                "isDefault": False
            }
        ]

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def api_key(self) -> str:
        return getattr(settings, self._api_key_attr, "").strip()

    @property
    def is_configured(self) -> bool:
        if self._provider_id == "ollama":
            return True # Ollama is local, doesn't require API key
        return bool(self.api_key and len(self.api_key) > 5)

    def get_supported_models(self) -> List[Dict[str, Any]]:
        models = []
        for m in self._models:
            m_copy = m.copy()
            m_copy["available"] = self.is_configured
            models.append(m_copy)
        return models

    def _prepare_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        images: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        formatted = []
        if system_prompt and system_prompt.strip():
            formatted.append({"role": "system", "content": system_prompt.strip()})
        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            role = msg.get("role", "user")
            if not content.strip() and not (images and i == len(messages) - 1):
                continue
            
            if images and i == len(messages) - 1 and role == "user":
                parts: List[Dict[str, Any]] = []
                if content.strip():
                    parts.append({"type": "text", "text": content})
                for img in images:
                    if "data" in img and "mime_type" in img:
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{img['mime_type']};base64,{img['data']}"}
                        })
                formatted.append({"role": role, "content": parts})
            else:
                formatted.append({"role": role, "content": content})
        return formatted


    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ) -> str:
        if not self.is_configured:
            raise ValueError(f"{self.display_name} API key is not configured ({self._api_key_attr}).")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": model,
            "messages": self._prepare_messages(messages, system_prompt, images=kwargs.get("images")),
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            "stream": False
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self._base_url}/chat/completions", headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"{self.display_name} API error {resp.status_code}: {resp.text}")
                raise RuntimeError(f"{self.display_name} error: {resp.status_code} - {resp.text}")
            
            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                raise RuntimeError(f"Unexpected response format from {self.display_name}: {e}")

    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        if not self.is_configured:
            raise ValueError(f"{self.display_name} API key is not configured ({self._api_key_attr}).")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": model,
            "messages": self._prepare_messages(messages, system_prompt, images=kwargs.get("images")),
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            "stream": True
        }


        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", f"{self._base_url}/chat/completions", headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err = await response.aread()
                    raise RuntimeError(f"{self.display_name} streaming error ({response.status_code}): {err.decode('utf-8')}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_json = json.loads(data_str)
                            choices = chunk_json.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
