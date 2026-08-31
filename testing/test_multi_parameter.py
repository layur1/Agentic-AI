"""
Tests multi-parameter clarification handling: a 2-required-parameter tool
(get_weather_alert-style pattern is now covered by schedule_delivery's
3-parameter case below) and ambiguity within a multi-parameter tool.

Run from the project root:
    python testing/test_multi_parameter.py
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

    await run_scenario(agent, "Schedule delivery - all three given at once", [
        "Schedule a delivery of the Wireless Mouse M1 for Amaya Silva on 2026-09-01.",
    ])

    await run_scenario(agent, "Schedule delivery - nothing given", [
        "Can you schedule a delivery for me?",
        "Amaya Silva, Wireless Mouse M1, 2026-09-01",
    ])

    await run_scenario(agent, "Schedule delivery - given one piece at a time", [
        "I want to schedule a delivery.",
        "The customer is Amaya Silva.",
        "It's for the Wireless Mouse M1.",
        "Deliver it on 2026-09-01.",
    ])

    await run_scenario(agent, "Schedule delivery - ambiguous customer name", [
        "Schedule a delivery of the Wireless Mouse M1 for John on 2026-09-01.",
        "John Fernando",
    ])


if __name__ == "__main__":
    asyncio.run(main())