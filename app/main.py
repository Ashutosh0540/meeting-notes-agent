from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, TextIO

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.agent.markdown import format_markdown
from app.agent.meeting_agent import MeetingAgent
from app.agent.schemas import MeetingNotes
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


class AnalyzeMeetingRequest(BaseModel):
    transcript: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/v1/meetings/analyze", response_model=MeetingNotes)
def analyze_meeting(request: AnalyzeMeetingRequest) -> MeetingNotes:
    if not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")
    provider = getattr(app.state, "provider", GroqProvider())
    try:
        return MeetingAgent(provider).analyze(request.transcript)
    except ProviderError as error:
        detail = "LLM provider is not configured." if "not configured" in str(error) else "Meeting analysis failed."
        raise HTTPException(status_code=503, detail=detail) from error


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
