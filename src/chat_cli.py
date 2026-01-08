# src/chat_cli.py
from __future__ import annotations

from src.agent import StoreAgent
import argparse
from src.auth import user_exists, get_user_name
from src.mode_router import ChatRouter


def prompt_for_user_id() -> str | None:
    while True:
        user_id = input("Enter your user ID (or type 'exit' to quit): ").strip()

        if user_id.lower() in {"exit", "quit"}:
            return None

        if not user_id:
            print("User ID cannot be empty. Please try again.")
            continue

        if not user_exists(user_id):
            print(f"Unknown user_id '{user_id}'. Please try again.")
            continue

        return user_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["rule", "llm", "auto"], default="auto",
                        help="rule=deterministic, llm=Gemini tool-calling, auto=try llm then fallback to rule on quota.")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model name (llm/auto modes).")
    args = parser.parse_args()
    
    print("Welcome to Wallet Store Agent! Type 'exit' to quit.")

    user_id = prompt_for_user_id()
    if user_id is None:
        print("Goodbye.")
        return  # <-- hard exit

    name = get_user_name(user_id) or user_id

    router = ChatRouter(mode=args.mode, gemini_model=args.model)

    print(f"\nWelcome {name}! How may I assist you today?")
    print(f"Mode: {args.mode}" + (f" | Model: {args.model}" if args.mode in {"llm", "auto"} else ""))


    while True:
        msg = input("\nYou: ").strip()
        if msg.lower() in {"exit", "quit"}:
            print("Goodbye.")
            return  # <-- hard exit (NOT break)

        reply = router.respond(msg, user_id=user_id)
        print("\nAgent:", reply)


if __name__ == "__main__":
    main()