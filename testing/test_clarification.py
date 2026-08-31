"""
Tests the clarification and disambiguation scenarios: missing name,
name given immediately, nonexistent name, and an ambiguous name matching
more than one customer.

Run from the project root:
    python testing/test_clarification.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from brain import build_agent, ask


async def run_scenario(agent, label, turns):
    print(f"\n===== Scenario: {label} =====")
    history = []
    for question in turns:
        print(f"User: {question}")
        answer = await ask(agent, question, history)
        print(f"Assistant: {answer}\n")
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


async def main():
    agent = await build_agent()

    await run_scenario(agent, "Missing name, then provided", [
        "Can you give me his address?",
        "John Perera",
    ])

    await run_scenario(agent, "Name given immediately", [
        "What is Amaya Silva's address?",
    ])

    await run_scenario(agent, "Nonexistent user", [
        "What is the address of Michael Johnson?",
    ])

    await run_scenario(agent, "Ambiguous name (two Johns)", [
        "What is John's address?",
        "John Fernando",
    ])


if __name__ == "__main__":
    asyncio.run(main())