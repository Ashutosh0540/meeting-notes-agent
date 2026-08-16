from abc import ABC, abstractmethod

from app.agent.schemas import MeetingNotes


class ProviderError(Exception):
    """Raised when a provider cannot return valid meeting notes."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, transcript: str) -> MeetingNotes:
        raise NotImplementedError
