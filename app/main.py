from __future__ import annotations

import argparse
import logging
import sys
from uuid import UUID
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, TextIO

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.agent.markdown import format_markdown
from app.agent.meeting_agent import MeetingAgent
from app.agent.schemas import ActionItem, Decision, MeetingNotes
from app.models import ActionItem as ActionItemModel
from app.models import Decision as DecisionModel
from app.models import Meeting
from app.providers.base import LLMProvider, ProviderError
from app.providers.groq import GroqProvider

SAMPLE_TRANSCRIPT = """Alice: We should launch the MVP Friday.
Bob: I will finish authentication tests tomorrow.
Sarah: The landing page copy is still missing.
Alice: Let's review testing status Friday at 3 PM."""

app = FastAPI(
    title="Meeting Notes Agent",
    description="Extract structured meeting intelligence from transcripts.",
)
logger = logging.getLogger(__name__)


class AnalyzeMeetingRequest(BaseModel):
    transcript: str


class AnalyzeMeetingResponse(MeetingNotes):
    meeting_id: UUID


class StoredActionItem(ActionItem):
    status: str


class MeetingListItem(BaseModel):
    meeting_id: UUID
    title: str
    created_at: datetime
    next_meeting: str | None


class MeetingDetail(BaseModel):
    meeting_id: UUID
    title: str
    executive_summary: str
    key_decisions: list[Decision]
    action_items: list[StoredActionItem]
    blockers: list[str]
    follow_ups: list[str]
    next_meeting: str | None
    created_at: datetime


def meeting_detail(meeting: Meeting) -> MeetingDetail:
    return MeetingDetail(
        meeting_id=meeting.id,
        title=meeting.title,
        executive_summary=meeting.executive_summary,
        key_decisions=[Decision(decision=item.decision, rationale=item.rationale) for item in meeting.decisions],
        action_items=[
            StoredActionItem(
                task=item.task,
                owner=item.owner,
                due_date=item.due_date,
                priority=item.priority,
                status=item.status,
            )
            for item in meeting.action_items
        ],
        blockers=meeting.blockers,
        follow_ups=meeting.follow_ups,
        next_meeting=meeting.next_meeting,
        created_at=meeting.created_at,
    )


@app.on_event("startup")
def initialize_database() -> None:
    try:
        db.init_db()
    except SQLAlchemyError:
        logger.exception("Database initialization failed")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/v1/meetings", response_model=list[MeetingListItem])
def list_meetings() -> list[MeetingListItem]:
    session_factory = getattr(app.state, "session_factory", db.SessionLocal)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        with session_factory() as session:
            meetings = session.scalars(select(Meeting).order_by(Meeting.created_at.desc())).all()
            return [
                MeetingListItem(
                    meeting_id=meeting.id,
                    title=meeting.title,
                    created_at=meeting.created_at,
                    next_meeting=meeting.next_meeting,
                )
                for meeting in meetings
            ]
    except SQLAlchemyError as error:
        logger.exception("Meeting history query failed")
        raise HTTPException(status_code=503, detail="Meeting history could not be loaded.") from error


@app.get("/api/v1/meetings/{meeting_id}", response_model=MeetingDetail)
def get_meeting(meeting_id: UUID) -> MeetingDetail:
    session_factory = getattr(app.state, "session_factory", db.SessionLocal)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    try:
        with session_factory() as session:
            meeting = session.get(Meeting, meeting_id)
            if meeting is None:
                raise HTTPException(status_code=404, detail="Meeting not found")
            return meeting_detail(meeting)
    except SQLAlchemyError as error:
        logger.exception("Meeting lookup failed")
        raise HTTPException(status_code=503, detail="Meeting could not be loaded.") from error


@app.post("/api/v1/meetings/analyze", response_model=AnalyzeMeetingResponse)
def analyze_meeting(request: AnalyzeMeetingRequest) -> AnalyzeMeetingResponse:
    if not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")
    provider = getattr(app.state, "provider", GroqProvider())
    try:
        notes = MeetingAgent(provider).analyze(request.transcript)
    except ProviderError as error:
        detail = "LLM provider is not configured." if "not configured" in str(error) else "Meeting analysis failed."
        raise HTTPException(status_code=503, detail=detail) from error

    session_factory = getattr(app.state, "session_factory", db.SessionLocal)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured.")
    session = None
    try:
        session = session_factory()
        meeting = Meeting(
            title=notes.title,
            transcript=request.transcript,
            executive_summary=notes.executive_summary,
            next_meeting=notes.next_meeting,
            blockers=notes.blockers,
            follow_ups=notes.follow_ups,
            decisions=[DecisionModel(decision=item.decision, rationale=item.rationale) for item in notes.key_decisions],
            action_items=[
                ActionItemModel(
                    task=item.task,
                    owner=item.owner,
                    due_date=item.due_date,
                    priority=item.priority,
                )
                for item in notes.action_items
            ],
        )
        session.add(meeting)
        session.commit()
        session.refresh(meeting)
    except SQLAlchemyError as error:
        if session is not None:
            session.rollback()
        logger.exception("Meeting persistence failed")
        raise HTTPException(status_code=503, detail="Meeting notes could not be saved.") from error
    finally:
        if session is not None:
            session.close()
    return AnalyzeMeetingResponse(meeting_id=meeting.id, **notes.model_dump())


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create structured meeting notes.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--transcript", type=Path, help="Path to a transcript file")
    source.add_argument("--text", help="Transcript text")
    parser.add_argument("--output", type=Path, help="Markdown output path")
    return parser.parse_args(argv)


def read_transcript(args: argparse.Namespace) -> str:
    if args.text is not None:
        transcript = args.text
    elif args.transcript is not None:
        try:
            transcript = args.transcript.read_text(encoding="utf-8")
        except OSError as error:
            raise ValueError(f"Could not read transcript: {args.transcript}") from error
    else:
        transcript = SAMPLE_TRANSCRIPT
    if not transcript.strip():
        raise ValueError("transcript cannot be empty.")
    return transcript


def output_path(requested: Optional[Path]) -> Path:
    path = requested or Path("meeting_notes.md")
    if not path.exists():
        return path
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{stamp}{path.suffix or '.md'}")


def run(
    argv: Optional[Sequence[str]] = None,
    provider: Optional[LLMProvider] = None,
    stream: Optional[TextIO] = None,
) -> Path:
    args = parse_args(argv)
    notes = MeetingAgent(provider or GroqProvider()).analyze(read_transcript(args))
    markdown = format_markdown(notes)
    path = output_path(args.output)
    path.write_text(markdown, encoding="utf-8")
    print(markdown, end="", file=stream or sys.stdout)
    return path


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        path = run(argv)
        print(f"Saved notes to {path}", file=sys.stderr)
        return 0
    except (ProviderError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
