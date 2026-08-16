from __future__ import annotations

import json
import os

from pydantic import ValidationError
from dotenv import load_dotenv

from app.agent.prompts import system_prompt
from app.agent.schemas import MeetingNotes
from app.providers.base import LLMProvider, ProviderError


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        load_dotenv()
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if self.api_key == "YOUR_REAL_KEY_HERE":
            self.api_key = None
        self.model = model or os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"

    def generate(self, transcript: str) -> MeetingNotes:
        if not self.api_key:
            raise ProviderError("GROQ_API_KEY is not configured")

        try:
            from groq import Groq

            response = Groq(api_key=self.api_key).chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": transcript},
                ],
            )
            content = response.choices[0].message.content
            return MeetingNotes.model_validate(json.loads(content or ""))
        except (json.JSONDecodeError, ValidationError, IndexError, AttributeError) as error:
            raise ProviderError("Groq returned invalid structured meeting notes") from error
        except Exception as error:
            raise ProviderError("Groq request failed") from error
