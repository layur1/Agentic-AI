"""
Fires a batch of sample questions at the agent and prints which tool(s)
it chose for each one, so you can verify routing quality before trusting
the full CLI.

Save this file directly in your project root (D:\\agentic_ai), the same
folder as brain.py.

Run:
    python test_routing.py
"""
import asyncio
from brain import build_agent

TEST_QUESTIONS = [
    "What is the warranty on Laptop A?",
    "What is the current price of Laptop A?",
    "Is Laptop B currently in stock?",
    "How do I maximize the battery life on Laptop A?",
    "Is the Bluetooth Speaker S2 water-resistant?",
    "What is the price and warranty of Laptop A?",  # should hit both tools
    "What accessories do you have available?",
    "Laptop A won't turn on, what should I do?",
]


async def main():
    agent = await build_agent()

    for question in TEST_QUESTIONS:
        print("=" * 70)
        print(f"Q: {question}")

        response = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})

        tool_calls_seen = []
        for msg in response["messages"]:
            calls = getattr(msg, "tool_calls", None)
            if calls:
                for c in calls:
                    tool_calls_seen.append(c["name"])

        final_answer = response["messages"][-1].content

        print(f"Tool(s) called: {tool_calls_seen or 'none'}")
        print(f"Answer: {final_answer}\n")


if __name__ == "__main__":
    asyncio.run(main())