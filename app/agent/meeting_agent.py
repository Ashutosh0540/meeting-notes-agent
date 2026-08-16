from app.agent.schemas import MeetingNotes
from app.providers.base import LLMProvider


class MeetingAgent:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def analyze(self, transcript: str) -> MeetingNotes:
        if not transcript or not transcript.strip():
            raise ValueError("Transcript must not be empty")
        return self.provider.generate(transcript.strip())
