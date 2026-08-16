from __future__ import annotations

from app.agent.schemas import MeetingNotes


def _value(value: str | None, fallback: str) -> str:
    return (value or fallback).replace("|", "\\|")


def format_markdown(notes: MeetingNotes) -> str:
    lines = [f"# {notes.title}", "", "## Executive Summary", "", notes.executive_summary, ""]
    lines.extend(["## Key Decisions", ""])
    lines.extend(f"- {decision.decision}" for decision in notes.key_decisions)
    if not notes.key_decisions:
        lines.append("None identified.")

    lines.extend(["", "## Action Items", ""])
    if notes.action_items:
        lines.extend(["| Task | Owner | Due Date | Priority |", "|---|---|---|---|"])
        lines.extend(
            "| {task} | {owner} | {due_date} | {priority} |".format(
                task=_value(item.task, "Unknown"),
                owner=_value(item.owner, "Unknown"),
                due_date=_value(item.due_date, "Unknown"),
                priority=_value(item.priority, "medium"),
            )
            for item in notes.action_items
        )
    else:
        lines.append("None identified.")

    for heading, items in (("Blockers", notes.blockers), ("Follow-ups", notes.follow_ups)):
        lines.extend(["", f"## {heading}", ""])
        lines.extend(f"- {item}" for item in items)
        if not items:
            lines.append("None identified.")

    lines.extend(["", "## Next Meeting", "", notes.next_meeting or "None scheduled."])
    return "\n".join(lines) + "\n"
