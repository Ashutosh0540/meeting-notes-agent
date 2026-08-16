from typing import List, Optional

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    task: str = Field(min_length=1)
    owner: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = "medium"


class Decision(BaseModel):
    decision: str = Field(min_length=1)
    rationale: Optional[str] = None


class MeetingNotes(BaseModel):
    title: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    key_decisions: List[Decision] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    follow_ups: List[str] = Field(default_factory=list)
    next_meeting: Optional[str] = None
