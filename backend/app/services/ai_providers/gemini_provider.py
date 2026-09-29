import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
import httpx

from backend.app.config import settings
from backend.app.services.ai_providers.base import BaseAIProvider

logger = logging.getLogger("ai_provider.gemini")

class GeminiProvider(BaseAIProvider):
    """Google Gemini AI Provider using server-side REST/SSE API."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    MODELS = [
        {
            "id": "gemini-1.5-flash",
            "name": "Gemini 1.5 Flash",
            "provider": "gemini",
            "description": "Ultra-fast, lightweight multi-modal model with high throughput.",
            "contextWindow": "1,000,000 tokens",
            "category": "Fast & Efficient",
            "isDefault": True
        },
        {
            "id": "gemini-1.5-pro",
            "name": "Gemini 1.5 Pro",
            "provider": "gemini",
            "description": "State-of-the-art model for complex reasoning, code architecture, and deep analysis.",
            "contextWindow": "2,000,000 tokens",
            "category": "Advanced Reasoning",
            "isDefault": False
        },
        {
            "id": "gemini-2.0-flash",
            "name": "Gemini 2.0 Flash",
            "provider": "gemini",
            "description": "Next-gen multimodal model with superior speed and instruction following.",
            "contextWindow": "1,000,000 tokens",
            "category": "Next Generation",
            "isDefault": False
        }
    ]

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    @property
    def is_configured(self) -> bool:
        return bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY.strip()) > 5)

    def get_supported_models(self) -> List[Dict[str, Any]]:
        models = []
        for m in self.MODELS:
            m_copy = m.copy()
            m_copy["available"] = self.is_configured
            models.append(m_copy)
        return models

    def _format_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        images: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Convert standard message format and images to Gemini contents & system instruction."""
        contents = []
        for i, msg in enumerate(messages):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content.strip() and not (images and i == len(messages) - 1):
                continue
            
            # Map role
            gemini_role = "user" if role == "user" else "model"
            if role == "system" and not system_prompt:
                system_prompt = content
                continue
            
            parts: List[Dict[str, Any]] = []
            if content.strip():
                parts.append({"text": content})

            # If this is the last user message and images are attached, attach inlineData
            if images and i == len(messages) - 1:
                for img in images:
                    if "data" in img and "mime_type" in img:
                        parts.append({
                            "inlineData": {
                                "mimeType": img["mime_type"],
                                "data": img["data"]
                            }
                        })

            if parts:
                contents.append({
                    "role": gemini_role,
                    "parts": parts
                })

        payload: Dict[str, Any] = {"contents": contents}
        if system_prompt and system_prompt.strip():
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt.strip()}]
            }
        return payload


    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-1.5-flash",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ) -> str:
        if not self.is_configured:
            raise ValueError("Gemini API key is not configured in environment (GEMINI_API_KEY).")

        payload = self._format_messages(messages, system_prompt, images=kwargs.get("images"))
        payload["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens or 4096
        }

        url = f"{self.BASE_URL}/{model}:generateContent?key={settings.GEMINI_API_KEY}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error(f"Gemini API error {resp.status_code}: {resp.text}")
                raise RuntimeError(f"Gemini API error: {resp.status_code} - {resp.text}")
            
            data = resp.json()
            try:
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    return "".join(part.get("text", "") for part in parts)
                return "I apologize, but no response was generated."
            except Exception as e:
                logger.error(f"Failed to parse Gemini response: {e}")
                raise RuntimeError(f"Failed to parse Gemini response: {str(e)}")

    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-1.5-flash",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        if not self.is_configured:
            raise ValueError("Gemini API key is not configured in environment (GEMINI_API_KEY).")

        payload = self._format_messages(messages, system_prompt, images=kwargs.get("images"))

        payload["generationConfig"] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens or 4096
        }

        url = f"{self.BASE_URL}/{model}:streamGenerateContent?alt=sse&key={settings.GEMINI_API_KEY}"
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    logger.error(f"Gemini streaming error {response.status_code}: {err_body.decode('utf-8')}")
                    raise RuntimeError(f"Gemini API error ({response.status_code}): {err_body.decode('utf-8')}")

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk_json = json.loads(data_str)
                            candidates = chunk_json.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for part in parts:
                                    text_chunk = part.get("text", "")
                                    if text_chunk:
                                        yield text_chunk
                        except json.JSONDecodeError:
                            continue
