"""
Tests multi-parameter clarification handling: a 2-required-parameter tool
(get_weather_alert: city + date) and a 3-required-parameter tool
(schedule_delivery: customer + product + date), including the case where
one of several parameters is individually ambiguous.

Save in your project root (D:\\agentic_ai), same folder as brain.py.

Run:
    python test_multi_parameter.py
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

    # --- 2-parameter tool: get_weather_alert(city, date) ---

    await run_scenario(agent, "Weather alert - both given at once", [
        "Are there any weather alerts for Colombo on 2026-08-25?",
    ])

    await run_scenario(agent, "Weather alert - both missing", [
        "Are there any severe weather alerts?",
        "Colombo, for 2026-08-25",
    ])

    await run_scenario(agent, "Weather alert - given one at a time", [
        "Are there any weather alerts?",
        "Colombo",
        "2026-08-25",
    ])

    # --- 3-parameter tool: schedule_delivery(customer, product, date) ---

    await run_scenario(agent, "Schedule delivery - all three given at once", [
        "Schedule a delivery of the Wireless Mouse M1 for Amaya Silva on 2026-09-01.",
    ])

    await run_scenario(agent, "Schedule delivery - nothing given", [
        "Can you schedule a delivery for me?",
        "Amaya Silva, Wireless Mouse M1, 2026-09-01",
    ])

    await run_scenario(agent, "Schedule delivery - ambiguous customer name", [
        "Schedule a delivery of the Wireless Mouse M1 for John on 2026-09-01.",
        "John Fernando",
    ])


if __name__ == "__main__":
    asyncio.run(main())