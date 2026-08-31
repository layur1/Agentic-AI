"""
Re-runs previously-timed-out questions one at a time with spacing and a
longer timeout, to distinguish rate-limiting from an uncapped reasoning
loop. (Historical note: for this project, the root cause was already
confirmed as rate limiting from running many cases back-to-back in one
session — this script remains useful if new timeout clusters appear.)

Run from the project root:
    python testing/test_timeout_isolation.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
from brain import build_agent

TIMEOUT_CASES = [
    ("no_matching_data", "What is the warranty on the iPhone 17?"),
    ("both_tools_needed", "What's the price and warranty of Laptop A?"),
    ("three_way_ambiguous",
     "Tell me everything about Laptop A and Laptop B including price, stock, warranty, and battery life."),
    ("extremely_long_input", "What is the warranty on Laptop A? " * 200),
    ("non_english", "¿Cuál es la garantía de Laptop A?"),
]

DELAY_BETWEEN_QUESTIONS_SECONDS = 8
LONGER_TIMEOUT_SECONDS = 60


async def run_one(agent, label, question):
    print(f"--- {label} ---")
    start = time.perf_counter()
    try:
        response = await asyncio.wait_for(
            agent.ainvoke({"messages": [{"role": "user", "content": question}]}),
            timeout=LONGER_TIMEOUT_SECONDS,
        )
        elapsed = time.perf_counter() - start

        rounds = sum(1 for msg in response["messages"] if getattr(msg, "tool_calls", None))
        tool_calls = []
        for msg in response["messages"]:
            calls = getattr(msg, "tool_calls", None)
            if calls:
                tool_calls.extend(c["name"] for c in calls)

        print(f"Result: OK in {elapsed:.2f}s | reasoning rounds: {rounds} | tools called: {tool_calls}")
        answer = response["messages"][-1].content
        print(f"Answer (first 150 chars): {answer[:150]}")

    except asyncio.TimeoutError:
        elapsed = time.perf_counter() - start
        print(f"Result: STILL TIMED OUT after {elapsed:.2f}s (even with {LONGER_TIMEOUT_SECONDS}s limit)")

    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"Result: ERROR ({type(e).__name__}): {e}")

    print()


async def main():
    print("Building agent...")
    agent = await build_agent()
    print(f"Re-running {len(TIMEOUT_CASES)} questions, "
          f"spaced {DELAY_BETWEEN_QUESTIONS_SECONDS}s apart, with a {LONGER_TIMEOUT_SECONDS}s limit.\n")

    for i, (label, question) in enumerate(TIMEOUT_CASES):
        await run_one(agent, label, question)
        if i < len(TIMEOUT_CASES) - 1:
            await asyncio.sleep(DELAY_BETWEEN_QUESTIONS_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())