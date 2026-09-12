"""
Proves session isolation under real concurrency: two simulated users,
having completely different multi-turn conversations, run at the SAME
TIME against the SAME shared agent instance. If session isolation is
broken, one user's history will leak into the other's — this checks for
exactly that.

Run from the project root:
    python testing/test_concurrent_sessions.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from brain import build_agent, ask
from session_manager import SessionManager


async def simulate_user(agent, session_manager, session_id, turns, label):
    for turn in turns:
        history = await session_manager.get_history(session_id)
        answer = await ask(agent, turn, history)
        await session_manager.append_turn(session_id, turn, answer)
        print(f"[{label}] Q: {turn}")
        print(f"[{label}] A: {answer}\n")


async def main():
    agent = await build_agent()
    session_manager = SessionManager()

    session_a = await session_manager.create_session()
    session_b = await session_manager.create_session()

    # User A: asks about a person's address across two turns (missing
    # name, then supplied) -- this ONLY works correctly if User A's
    # own history is intact and uncontaminated between the two turns.
    user_a_turns = ["Can you give me his address?", "John Perera"]

    # User B: a completely unrelated conversation, running AT THE SAME
    # TIME as User A's.
    user_b_turns = ["What is the price of Laptop A?", "What about its warranty?"]

    print("Running both users' conversations CONCURRENTLY...\n")
    await asyncio.gather(
        simulate_user(agent, session_manager, session_a, user_a_turns, "User A"),
        simulate_user(agent, session_manager, session_b, user_b_turns, "User B"),
    )

    history_a = await session_manager.get_history(session_a)
    history_b = await session_manager.get_history(session_b)

    print("=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    a_mentions_laptop = any("laptop" in m["content"].lower() for m in history_a)
    b_mentions_perera = any("perera" in m["content"].lower() for m in history_b)

    print(f"User A's history contains 'Laptop' (should be False): {a_mentions_laptop}")
    print(f"User B's history contains 'Perera' (should be False): {b_mentions_perera}")
    print(f"User A's history length: {len(history_a)} messages (expect 4)")
    print(f"User B's history length: {len(history_b)} messages (expect 4)")

    if not a_mentions_laptop and not b_mentions_perera and len(history_a) == 4 and len(history_b) == 4:
        print("\nPASS: Sessions remained fully isolated under concurrent execution.")
    else:
        print("\nFAIL: Cross-contamination or history corruption detected between sessions!")

    print("\nNote: this test uses 2 concurrent users as a first check. It does")
    print("NOT stress-test the underlying stdio MCP transport under heavy")
    print("concurrent load -- if issues appear with many more simultaneous")
    print("users, the stdio connection to each MCP server (a single pipe)")
    print("may need replacing with a network-based transport, per the")
    print("Scalability section of the project documentation.")


if __name__ == "__main__":
    asyncio.run(main())