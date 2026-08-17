import unittest
from unittest.mock import patch

from app.agent.meeting_agent import MeetingAgent
from app.agent.prompts import system_prompt
from app.agent.schemas import ActionItem, Decision, MeetingNotes
from app.providers.base import LLMProvider
from app.providers.groq import GroqProvider


class FakeProvider(LLMProvider):
    def generate(self, transcript: str) -> MeetingNotes:
        return MeetingNotes(
            title="MVP launch",
            executive_summary="The team discussed launching the MVP on Friday.",
            key_decisions=[Decision(decision="Launch the MVP Friday")],
            action_items=[ActionItem(task="Finish authentication tests", owner="Bob", due_date="tomorrow")],
            blockers=["Landing page copy is still needed"],
            follow_ups=["Sarah will provide the landing page copy"],
        )


class QualityFakeProvider(LLMProvider):
    def generate(self, transcript: str) -> MeetingNotes:
        return MeetingNotes(
            title="Q3 Mobile App Redesign",
            executive_summary="The team agreed to launch the MVP on Monday.",
            key_decisions=[Decision(decision="Launch the MVP Monday.")],
            action_items=[ActionItem(task="Finish testing", owner="Bob", due_date="tomorrow")],
            blockers=[],
            follow_ups=[],
            next_meeting="Monday at 10 AM",
        )


class MeetingAgentTests(unittest.TestCase):
    def test_schema_validates_structured_notes(self) -> None:
        notes = FakeProvider().generate("unused")
        self.assertEqual(notes.action_items[0].owner, "Bob")
        self.assertIsNone(ActionItem(task="Review copy").owner)

    def test_agent_uses_provider_for_extraction(self) -> None:
        notes = MeetingAgent(FakeProvider()).analyze("Alice: We will launch the MVP Friday.")
        self.assertEqual(notes.key_decisions[0].decision, "Launch the MVP Friday")
        self.assertIn("Landing page copy is still needed", notes.blockers)

    def test_agent_rejects_empty_transcript(self) -> None:
        with self.assertRaises(ValueError):
            MeetingAgent(FakeProvider()).analyze("   ")

    def test_groq_provider_uses_current_default_model(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            provider = GroqProvider(api_key="test")
        self.assertEqual(provider.model, "openai/gpt-oss-120b")

    def test_prompt_keeps_meeting_schedule_out_of_decisions_and_uses_named_topics(self) -> None:
        transcript = """Q3 Mobile App Redesign sync
Alex: We agreed to launch the MVP Monday.
Bob: I'll finish testing tomorrow.
Sarah: Let's meet Monday at 10 AM to review progress."""
        notes = MeetingAgent(QualityFakeProvider()).analyze(transcript)
        prompt = system_prompt()
        self.assertEqual(notes.title, "Q3 Mobile App Redesign")
        self.assertEqual([item.decision for item in notes.key_decisions], ["Launch the MVP Monday."])
        self.assertEqual(notes.next_meeting, "Monday at 10 AM")
        self.assertIn("Meeting scheduling information must never appear in key_decisions", prompt)
        self.assertIn("use an explicitly named meeting, project, or topic", prompt)


if __name__ == "__main__":
    unittest.main()
