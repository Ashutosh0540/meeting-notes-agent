from fastapi.testclient import TestClient

from app.agent.schemas import ActionItem, Decision, MeetingNotes
from app.main import app
from app.providers.base import LLMProvider


class FakeProvider(LLMProvider):
    def generate(self, transcript: str) -> MeetingNotes:
        return MeetingNotes(
            title="Sprint Planning",
            executive_summary="The team aligned on the MVP launch.",
            key_decisions=[Decision(decision="Ship the MVP by Friday.")],
            action_items=[ActionItem(task="Finish tests", owner="Bob")],
            blockers=[],
            follow_ups=[],
        )


client = TestClient(app)


def setup_function() -> None:
    app.state.provider = FakeProvider()


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_analyze_meeting_uses_provider() -> None:
    response = client.post("/api/v1/meetings/analyze", json={"transcript": "Alice: Ship Friday."})
    assert response.status_code == 200
    assert response.json()["title"] == "Sprint Planning"
    assert response.json()["action_items"][0]["owner"] == "Bob"


def test_analyze_rejects_empty_transcript() -> None:
    response = client.post("/api/v1/meetings/analyze", json={"transcript": "  "})
    assert response.status_code == 400
    assert response.json() == {"detail": "Transcript cannot be empty."}


def test_analyze_rejects_invalid_request() -> None:
    response = client.post("/api/v1/meetings/analyze", json={})
    assert response.status_code == 422
