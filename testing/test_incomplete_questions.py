"""
Tests how the agent handles INCOMPLETE questions across every tool
category, not just the ones with explicit clarification instructions in
their docstrings.

Run from the project root:
    python testing/test_incomplete_questions.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from brain import build_agent

INCOMPLETE_CASES = [
    ("price_no_product", "What's the price?", "get_price — has explicit rule in system prompt only, no docstring reinforcement beyond a general note"),
    ("stock_no_product", "Is it in stock?", "check_stock — same"),
    ("address_no_name", "Can you give me his address?", "get_user_address — HAS explicit docstring reinforcement"),
    ("vague_product_reference", "What about Laptop A?", "ambiguous which aspect — price, stock, or warranty? A missing-intent case, not a missing-argument case."),
]


async def main():
    agent = await build_agent()
    print(f"Running {len(INCOMPLETE_CASES)} incomplete-question cases.\n")

    results = []

    for label, question, note in INCOMPLETE_CASES:
        print(f"--- {label} ---")
        print(f"Q: {question}")
        print(f"Testing: {note}")

        response = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})

        tool_calls = []
        for msg in response["messages"]:
            calls = getattr(msg, "tool_calls", None)
            if calls:
                tool_calls.extend(c["name"] for c in calls)

        answer = response["messages"][-1].content

        if not tool_calls:
            verdict = "PASS (asked for clarification, no tool called)"
        else:
            verdict = f"REVIEW — called {tool_calls}, check answer below for guessed/hallucinated values"

        print(f"Tool(s) called: {tool_calls or 'none'}")
        print(f"Verdict: {verdict}")
        print(f"Answer: {answer}\n")

        results.append((label, tool_calls, verdict))

    print("===== SUMMARY =====")
    for label, tool_calls, verdict in results:
        print(f"{label:<28} tools={tool_calls or 'none':<20} {verdict}")


if __name__ == "__main__":
    asyncio.run(main())