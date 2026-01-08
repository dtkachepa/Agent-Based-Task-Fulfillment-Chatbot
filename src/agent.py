# src/agent.py
from __future__ import annotations

import json
from uuid import uuid4
from typing import Any, Dict, List

from google.genai import types

from src.prompts import SYSTEM_INSTRUCTIONS
from src.llm_clients import GeminiClient
import src.tools as store_tools


def _dispatch_tool(name: str):
    mapping = {
        "get_balance": store_tools.get_balance,
        "add_funds": store_tools.add_funds,
        "search_products": store_tools.search_products,
        "get_product": store_tools.get_product,
        "purchase": store_tools.purchase,
        "get_orders": store_tools.get_orders,
    }
    if name not in mapping:
        raise ValueError(f"Tool not found: {name}")
    return mapping[name]


def _gemini_tool_declarations() -> list[types.Tool]:
    # NOTE: google-genai expects uppercase "type" values.
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_balance",
                    description="Get wallet balance for a user.",
                    parameters={"type": "OBJECT", "properties": {"user_id": {"type": "STRING"}}, "required": ["user_id"]},
                ),
                types.FunctionDeclaration(
                    name="add_funds",
                    description="Add funds to a user's wallet (idempotent via client_request_id).",
                    parameters={
                        "type": "OBJECT",
                        "properties": {
                            "user_id": {"type": "STRING"},
                            "amount_cents": {"type": "INTEGER"},
                            "source": {"type": "STRING"},
                            "client_request_id": {"type": "STRING"},
                        },
                        "required": ["user_id", "amount_cents", "source", "client_request_id"],
                    },
                ),
                types.FunctionDeclaration(
                    name="search_products",
                    description="Search products by name. If query omitted/empty, returns full catalog.",
                    parameters={"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": []},
                ),
                types.FunctionDeclaration(
                    name="get_product",
                    description="Get product by product_id.",
                    parameters={"type": "OBJECT", "properties": {"product_id": {"type": "STRING"}}, "required": ["product_id"]},
                ),
                types.FunctionDeclaration(
                    name="purchase",
                    description="Purchase product for user (idempotent via client_request_id).",
                    parameters={
                        "type": "OBJECT",
                        "properties": {
                            "user_id": {"type": "STRING"},
                            "product_id": {"type": "STRING"},
                            "quantity": {"type": "INTEGER"},
                            "client_request_id": {"type": "STRING"},
                        },
                        "required": ["user_id", "product_id", "quantity", "client_request_id"],
                    },
                ),
                types.FunctionDeclaration(
                    name="get_orders",
                    description="Get recent orders for a user.",
                    parameters={
                        "type": "OBJECT",
                        "properties": {"user_id": {"type": "STRING"}, "limit": {"type": "INTEGER"}},
                        "required": ["user_id", "limit"],
                    },
                ),
            ]
        )
    ]

class StoreAgent:
    def __init__(self, gemini_model: str = "gemini-2.5-flash"):
        self.gemini_tools = _gemini_tool_declarations()
        self.gemini = GeminiClient(model=gemini_model, tools=self.gemini_tools)

        # Gemini conversation state
        self.gemini_contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=SYSTEM_INSTRUCTIONS)])
        ]

    # -------------------------
    # GEMINI PATH
    # -------------------------
    def _chat_gemini(self, user_text: str) -> str:
        self.gemini_contents.append(types.Content(role="user", parts=[types.Part(text=user_text)]))

        for _ in range(10):
            resp = self.gemini.generate(self.gemini_contents)

            cand = (resp.candidates or [None])[0]
            if cand is None or cand.content is None:
                return "Sorry — no valid response."

            parts = cand.content.parts or []
            function_calls = []
            text_chunks = []

            for part in parts:
                if getattr(part, "text", None):
                    text_chunks.append(part.text)
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    function_calls.append(fc)

            if function_calls:
                for fc in function_calls:
                    tool_name = fc.name
                    tool_args = dict(fc.args or {})
                    fn = _dispatch_tool(tool_name)

                    print(f"\n[Gemini TOOL CALL] {tool_name}({tool_args})")
                    try:
                        result = fn(**tool_args)
                        payload = result.model_dump() if hasattr(result, "model_dump") else result
                    except Exception as e:
                        payload = {"error": str(e)}
                    print(f"[Gemini TOOL RESULT] {tool_name}: {payload}\n")

                    self.gemini_contents.append(
                        types.Content(
                            role="tool",
                            parts=[types.Part.from_function_response(name=tool_name, response=payload)],
                        )
                    )
                continue

            out = "".join(text_chunks).strip()
            if out:
                self.gemini_contents.append(types.Content(role="model", parts=[types.Part(text=out)]))
                return out

            return "Sorry — empty response."

        return "Sorry — step limit reached."

           
    # -------------------------
    # PUBLIC CHAT (Gemini -> Grok on 429)
    # -------------------------
    def chat(self, user_message: str, user_id: str) -> str:
        ctx = {
            "user_id": user_id,
            "purchase_request_id": f"purchase_{uuid4().hex}",
            "topup_request_id": f"topup_{uuid4().hex}",
        }
        wrapped = f"USER_CONTEXT:\n{json.dumps(ctx)}\n\nUSER_MESSAGE:\n{user_message}"

        print("\n[LLM] Using Gemini")
        try:
            return self._chat_gemini(wrapped)
        except Exception as e:
            s = str(e).lower()
            if "429" in s or "resource_exhausted" in s or "quota" in s:
                return (
                    "⚠️ Gemini quota/rate-limit reached (HTTP 429).\n"
                    "Please rerun the chatbot with:\n"
                    "  python -m src.chat_cli --mode auto\n"
                    "or use:\n"
                    "  python -m src.chat_cli --mode rule\n"
                )
            raise
