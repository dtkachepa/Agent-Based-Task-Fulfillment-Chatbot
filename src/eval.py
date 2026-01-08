# src/eval.py
from __future__ import annotations
from src.rule_agent import RuleAgent

def run_case(case_name: str, turns: list[str], user_id: str = "u_1002") -> bool:
    agent = RuleAgent()
    ok = True
    last = ""
    for t in turns:
        last = agent.handle(t, user_id=user_id)
    # crude success checks
    if "Order placed" in last or "✅ Order placed" in last:
        return True
    return False

def main():
    cases = [
        ("buy_with_topup", ["buy 2 ethernet cables", "yes", "yes"]),
        ("buy_direct", ["add $50", "yes", "buy 1 usb-c cable", "yes"]),
    ]
    success = 0
    for name, turns in cases:
        res = run_case(name, turns)
        print(name, "PASS" if res else "FAIL")
        success += int(res)
    print(f"\nSuccess: {success}/{len(cases)}")

if __name__ == "__main__":
    main()