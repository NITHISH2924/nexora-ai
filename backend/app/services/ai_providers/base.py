from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional

class BaseAIProvider(ABC):
    """Abstract base class for all server-side AI model providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for provider (e.g., 'gemini', 'openai', 'anthropic', 'builtin')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable provider name."""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the required API key/endpoint is properly configured in environment."""
        pass

    @abstractmethod
    def get_supported_models(self) -> List[Dict[str, Any]]:
        """Return list of models supported by this provider."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate a complete non-streaming response."""
        pass

    @abstractmethod
    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chunks of text response token by token."""
        pass
