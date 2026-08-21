from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.agent.schemas import ActionItem, Decision, MeetingNotes
from app.db import Base
from app.main import app
from app.models import ActionItem as ActionItemModel
from app.models import Decision as DecisionModel
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


def add_meeting(title: str, created_at: datetime) -> Meeting:
    with app.state.session_factory() as session:
        meeting = Meeting(
            title=title,
            transcript="Transcript",
            executive_summary="Summary",
            next_meeting="Friday",
            blockers=["Blocker"],
            follow_ups=["Follow-up"],
            created_at=created_at,
            decisions=[DecisionModel(decision="Ship it", rationale="Approved")],
            action_items=[ActionItemModel(task="Finish testing", owner="Bob", due_date="Tomorrow", priority="high")],
        )
        session.add(meeting)
        session.commit()
        session.refresh(meeting)
        return meeting


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


def test_list_meetings_returns_empty_list_for_empty_database() -> None:
    response = client.get("/api/v1/meetings")
    assert response.status_code == 200
    assert response.json() == []


def test_list_meetings_returns_newest_first_with_summary_fields() -> None:
    now = datetime.now(timezone.utc)
    older = add_meeting("Older meeting", now - timedelta(days=1))
    newer = add_meeting("Newer meeting", now)

    response = client.get("/api/v1/meetings")
    assert response.status_code == 200
    assert [item["meeting_id"] for item in response.json()] == [str(newer.id), str(older.id)]
    assert set(response.json()[0]) == {"meeting_id", "title", "created_at", "next_meeting"}


def test_get_meeting_returns_complete_saved_meeting() -> None:
    meeting = add_meeting("MVP Planning", datetime.now(timezone.utc))

    response = client.get(f"/api/v1/meetings/{meeting.id}")
    assert response.status_code == 200
    assert response.json()["meeting_id"] == str(meeting.id)
    assert response.json()["key_decisions"][0]["decision"] == "Ship it"
    assert response.json()["action_items"][0]["status"] == "pending"
    assert response.json()["blockers"] == ["Blocker"]


def test_get_meeting_returns_404_for_missing_meeting() -> None:
    response = client.get("/api/v1/meetings/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json() == {"detail": "Meeting not found"}
