from app.agent.schemas import MeetingNotes


def system_prompt() -> str:
    schema = MeetingNotes.model_json_schema()
    return f"""You extract concise, structured notes from a meeting transcript.

Use only information supported by the transcript. Never invent owners, dates, or
decisions. Use null when an owner or date is unknown; preserve relative dates such
as "tomorrow". List decisions only when explicitly agreed or confirmed; proposals,
needs, discussion topics, and next-meeting topics are not decisions. Separate
confirmed decisions from conflicting claims. Extract explicit and strongly implied
action items, unresolved blockers, and follow-ups. Treat stated risks, incomplete
work, and missing ownership as blockers while they remain unresolved.
Meeting scheduling information must never appear in key_decisions; put a scheduled
next meeting only in next_meeting and scheduling follow-ups in follow_ups. For the
title, use an explicitly named meeting, project, or topic when present; otherwise
derive a concise dominant topic. Use "Team Meeting" only when no meaningful topic
can be inferred, and never invent a project name. Return only JSON that validates
against this schema:
{schema}
"""
