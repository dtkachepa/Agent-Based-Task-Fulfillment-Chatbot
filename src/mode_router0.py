# src/mode_router.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from src.rule_agent import RuleAgent
from src.agent import StoreAgent  # Gemini tool-calling agent


Mode = Literal["llm", "rule", "auto"]


def is_quota_error(e: Exception) -> bool:
    s = str(e).lower()
    return (
        "429" in s
        or "resource_exhausted" in s
        or "quota" in s
        or "rate limit" in s
        or "too many requests" in s
    )


@dataclass
class ChatRouter:
    mode: Mode = "auto"
    gemini_model: str = "gemini-2.5-flash"

    _rule: Optional[RuleAgent] = None
    _llm: Optional[StoreAgent] = None
    _auto_locked_to_rule: bool = False

    def __post_init__(self):
        self._rule = RuleAgent()
        # Only construct LLM agent if mode requires it
        if self.mode in ("llm", "auto"):
            self._llm = StoreAgent(gemini_model=self.gemini_model) if "gemini_model" in StoreAgent.__init__.__code__.co_varnames else StoreAgent()

    def respond(self, user_text: str, user_id: str) -> str:
        """
        Unified response method.
        - rule: always deterministic tools-based
        - llm: Gemini tool-calling
        - auto: try llm; on quota error switch to rule permanently for session
        """
        if self.mode == "rule":
            return self._rule.handle(user_text, user_id=user_id)

        if self.mode == "llm":
            return self._llm.chat(user_text, user_id=user_id)

        # auto
        if self._auto_locked_to_rule:
            return self._rule.handle(user_text, user_id=user_id)

        try:
            return self._llm.chat(user_text, user_id=user_id)
        except Exception as e:
            if is_quota_error(e):
                self._auto_locked_to_rule = True
                return (
                    "⚠️ LLM quota/rate-limit reached. Switching to RuleAgent for the rest of this session.\n"
                    + self._rule.handle(user_text, user_id=user_id)
                )
            raise
