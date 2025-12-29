from typing import Any, Dict
from abc import ABC, abstractmethod

class BaseProvider(ABC):
    @abstractmethod
    def generate(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> str:
        pass

class EchoProvider(BaseProvider):
    """A dummy provider that just echos the prompt."""
    def generate(self, model_id: str, prompt: str, api_key: str = None, **kwargs) -> str:
        return f"[ECHO {model_id}] {prompt}"
