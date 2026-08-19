from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.agent.schemas import ActionItem, Decision, MeetingNotes
from app.db import Base
from app.main import app
from app.models import Meeting
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
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app.state.session_factory = sessionmaker(bind=engine)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_analyze_meeting_uses_provider() -> None:
    response = client.post("/api/v1/meetings/analyze", json={"transcript": "Alice: Ship Friday."})
    assert response.status_code == 200
    assert response.json()["title"] == "Sprint Planning"
    assert response.json()["action_items"][0]["owner"] == "Bob"
    assert response.json()["meeting_id"]


def test_analyze_persists_meeting_relationships_and_pending_status() -> None:
    response = client.post("/api/v1/meetings/analyze", json={"transcript": "Alice: Ship Friday."})
    assert response.status_code == 200

    with app.state.session_factory() as session:
        meeting = session.scalar(select(Meeting))
        assert meeting is not None
        assert meeting.transcript == "Alice: Ship Friday."
        assert meeting.decisions[0].decision == "Ship the MVP by Friday."
        assert meeting.action_items[0].task == "Finish tests"
        assert meeting.action_items[0].status == "pending"


def test_analyze_returns_clean_error_when_database_fails() -> None:
    class FailingSession:
        def add(self, _meeting) -> None:
            pass

        def commit(self) -> None:
            raise SQLAlchemyError("database unavailable")

        def rollback(self) -> None:
            pass

        def close(self) -> None:
            pass

    def failing_session_factory():
        return FailingSession()

    app.state.session_factory = failing_session_factory
    response = client.post("/api/v1/meetings/analyze", json={"transcript": "Alice: Ship Friday."})
    assert response.status_code == 503
    assert response.json() == {"detail": "Meeting notes could not be saved."}


def test_analyze_rejects_empty_transcript() -> None:
    response = client.post("/api/v1/meetings/analyze", json={"transcript": "  "})
    assert response.status_code == 400
    assert response.json() == {"detail": "Transcript cannot be empty."}


def test_analyze_rejects_invalid_request() -> None:
    response = client.post("/api/v1/meetings/analyze", json={})
    assert response.status_code == 422
