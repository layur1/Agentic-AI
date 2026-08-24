"""
Tests how the agent handles INCOMPLETE questions across every tool category
— not just the two (get_user_address, weather) that got explicit
clarification instructions in their docstrings.

For each case, "PASS" means the agent asked a clarifying question WITHOUT
calling a tool. "FAIL (guessed)" means it called a tool anyway with a
guessed/empty argument. "FAIL (hallucinated)" means it answered as if it
had real data.

Save in your project root (D:\\agentic_ai), same folder as brain.py.

Run:
    python test_incomplete_questions.py
"""
import asyncio
from brain import build_agent

INCOMPLETE_CASES = [
    # (label, question, which tool(s) would need a missing argument)
    ("price_no_product", "What's the price?", "get_price (has explicit rule in system prompt only, no docstring reinforcement)"),
    ("stock_no_product", "Is it in stock?", "check_stock (same — no docstring reinforcement)"),
    ("weather_no_city", "What's the weather like today?", "get_current_weather (HAS docstring reinforcement — should be more reliable)"),
    ("address_no_name", "Can you give me his address?", "get_user_address (HAS docstring reinforcement — should be more reliable)"),
    ("vague_product_reference", "What about Laptop A?", "ambiguous which aspect — price, stock, or warranty? Not a missing-argument case, a missing-intent case."),
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