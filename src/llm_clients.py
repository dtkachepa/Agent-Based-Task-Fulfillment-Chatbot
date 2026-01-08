# src/llm_clients.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from dotenv import load_dotenv
load_dotenv()

def _require_env(key: str) -> str:
    v = os.getenv(key)
    if not v:
        raise RuntimeError(f"Missing environment variable: {key}")
    return v

class GeminiClient:
    def __init__(self, model: str, tools: list[types.Tool]):
        api_key = _require_env("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.tools = tools

    def generate(self, contents: list[types.Content]) -> types.GenerateContentResponse:
        return self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=self.tools,
                temperature=0.2,
            ),
        )
