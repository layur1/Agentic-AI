"""
Tests the clarification scenario: asking for "his address" without naming
anyone should make the agent ask a follow-up question instead of guessing
or calling the tool with no name. Providing the name in the next message
should then correctly return that person's address.

Save in your project root (D:\\agentic_ai), same folder as brain.py.

Run:
    python test_clarification.py
"""
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

    # Scenario 1: the exact case you described — ask without a name first,
    # confirm the agent asks a clarifying question, then supply the name.
    await run_scenario(agent, "Missing name, then provided", [
        "Can you give me his address?",
        "John Perera",
    ])

    # Scenario 2: name given immediately — should answer directly, no
    # clarifying question needed, single tool call.
    await run_scenario(agent, "Name given immediately", [
        "What is Amaya Silva's address?",
    ])

    # Scenario 3: name that doesn't exist — should say not found, not
    # invent an address.
    await run_scenario(agent, "Nonexistent user", [
        "What is the address of Michael Johnson?",
    ])

    # Scenario 4: ambiguous name — TWO customers match "John" (John Perera
    # and John Fernando). The agent should list both and ask which one,
    # NOT silently pick one. Providing the full name should then resolve
    # it correctly.
    await run_scenario(agent, "Ambiguous name (two Johns)", [
        "What is John's address?",
        "John Fernando",
    ])


if __name__ == "__main__":
    asyncio.run(main())