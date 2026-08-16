import io
import tempfile
import unittest
from pathlib import Path

from app.agent.markdown import format_markdown
from app.agent.schemas import ActionItem, Decision, MeetingNotes
from app.main import run
from app.providers.base import LLMProvider


class FakeProvider(LLMProvider):
    def generate(self, transcript: str) -> MeetingNotes:
        return MeetingNotes(
            title="Sprint Planning",
            executive_summary="The team aligned on the MVP launch.",
            key_decisions=[Decision(decision="Ship the MVP by Friday.")],
            action_items=[ActionItem(task="Finish authentication tests", owner="Bob", due_date="Tomorrow", priority="high")],
            blockers=["Landing page copy is still pending."],
            follow_ups=["Review testing status before launch."],
            next_meeting="Friday at 3 PM",
        )


class CliTests(unittest.TestCase):
    def test_markdown_includes_meeting_details(self) -> None:
        markdown = format_markdown(FakeProvider().generate("unused"))
        for value in ("Sprint Planning", "aligned on the MVP", "Ship the MVP", "authentication tests", "Landing page", "Review testing", "Friday at 3 PM"):
            self.assertIn(value, markdown)

    def test_markdown_handles_empty_sections(self) -> None:
        notes = MeetingNotes(title="Check-in", executive_summary="Brief update.")
        markdown = format_markdown(notes)
        self.assertEqual(markdown.count("None identified."), 4)
        self.assertIn("None scheduled.", markdown)
        self.assertNotIn("|---|", markdown)

    def test_cli_text_input_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "notes.md"
            stream = io.StringIO()
            result = run(["--text", "Alice: Ship Friday.", "--output", str(output)], FakeProvider(), stream)
            self.assertEqual(result, output)
            self.assertIn("# Sprint Planning", stream.getvalue())
            self.assertIn("Bob", output.read_text(encoding="utf-8"))

    def test_existing_output_gets_timestamped_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "notes.md"
            output.write_text("old", encoding="utf-8")
            result = run(["--text", "Alice: Ship Friday.", "--output", str(output)], FakeProvider(), io.StringIO())
            self.assertNotEqual(result, output)
            self.assertTrue(result.exists())
            self.assertEqual(output.read_text(encoding="utf-8"), "old")


if __name__ == "__main__":
    unittest.main()
