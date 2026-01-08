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


def looks_like_simple_command(text: str) -> bool:
    t = text.strip().lower()
    # cheap routing: these are deterministic and don't need LLM
    keywords = [
        "balance", "orders", "history",
        "show", "list", "catalog", "products",
        "buy", "add", "top up", "load",
    ]
    return any(k in t for k in keywords)


@dataclass
class ChatRouter:
    mode: Mode = "auto"
    gemini_model: str = "gemini-2.5-flash"

    _rule: Optional[RuleAgent] = None
    _llm: Optional[StoreAgent] = None
    _auto_locked_to_rule: bool = False

    def __post_init__(self):
        self._rule = RuleAgent()
        if self.mode in ("llm", "auto"):
            # If your StoreAgent takes gemini_model, pass it; otherwise defaults
            try:
                self._llm = StoreAgent(gemini_model=self.gemini_model)
            except TypeError:
                self._llm = StoreAgent()

    def respond(self, user_text: str, user_id: str) -> str:
        if self.mode == "rule":
            return self._rule.handle(user_text, user_id=user_id)

        if self.mode == "llm":
            return self._llm.chat(user_text, user_id=user_id)

        # auto
        if self._auto_locked_to_rule:
            return self._rule.handle(user_text, user_id=user_id)

        # Reduce Gemini calls: route obvious commands to RuleAgent
        if looks_like_simple_command(user_text):
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
