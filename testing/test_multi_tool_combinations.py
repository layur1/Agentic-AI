"""
Comprehensive end-to-end test of the full application: 13 two- and
three-tool combination questions spanning all 11 real tools (PDF search
+ 10 MySQL tools). Produces a full pass/fail summary at the end.

RATE LIMITING: this script is deliberately conservative about OpenAI's
requests-per-minute limit —
  1. A fixed delay between each question (DELAY_BETWEEN_QUESTIONS_SECONDS).
  2. Automatic retry with exponential backoff if OpenAI actually returns
     a 429 RateLimitError, rather than assuming the fixed delay alone is
     always enough (your exact tier's limit isn't knowable from here).

SETUP: seeds one real delivery record (John Perera / Laptop A) directly
via SQL before the test battery runs, so the delivery-status and
cancel-delivery questions have real data to find rather than always
hitting an empty "no deliveries scheduled" case.

Run from the project root:
    python testing/test_multi_tool_combinations.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
import mysql.connector
from openai import RateLimitError

import config
from brain import build_agent

DELAY_BETWEEN_QUESTIONS_SECONDS = 5
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 15

# ---------------------------------------------------------------------
# Test battery: (id, question, expected_tools_or_None, note)
# expected_tools = None means "exploratory only" — no fixed correct
# answer, reported but not graded pass/fail.
# ---------------------------------------------------------------------
TEST_CASES = [
    (1, "What's the price and warranty period of Laptop A?",
     {"get_price", "search_pdf"}, ""),
    (2, "Is Laptop A in stock, and how do I maintain the battery?",
     {"check_stock", "search_pdf"}, ""),
    (3, "What's the price of the Wireless Mouse M1 and what's its warranty?",
     {"get_price", "search_pdf"}, ""),
    (4, "What's John Perera's address, and is Laptop A in stock?",
     {"get_user_address", "check_stock"}, ""),
    (5, "Do we have a customer named Fernando, and what's the price of Laptop A?",
     {"search_customers", "get_price"}, ""),
    (6, "What deliveries does John Perera have scheduled, and what's his address?",
     {"get_delivery_status", "get_user_address"}, ""),
    (7, "Cancel John Perera's delivery of Laptop A and tell me if it's back in stock.",
     {"cancel_delivery", "check_stock"}, ""),
    (8, "Schedule a delivery of Laptop A for John Perera on 2026-09-15, and confirm its current price.",
     {"schedule_delivery", "get_price"}, ""),
    (9, "What deliveries are scheduled for Laptop A's customers, and is it still in stock?",
     None, "Deliberately vague — exploratory only, not graded pass/fail."),
    (10, "What products do you have under Rs. 50,000, and does Laptop A specifically have a warranty?",
     {"get_products_by_price_range", "search_pdf"}, ""),
    (11, "What's the price and warranty of Laptop A, and is John Perera's delivery for it still scheduled?",
     {"get_price", "search_pdf", "get_delivery_status"}, "Three-tool"),
    (12, "Add a new customer Kasun Silva at 45 Galle Road, then schedule a delivery of Laptop A for him on 2026-09-20.",
     {"add_new_customer", "schedule_delivery"}, "Tests correct sequencing"),
    (13, "Is the Wireless Mouse M1 in stock, what's its price, and what does the manual say about its specs?",
     {"check_stock", "get_price", "search_pdf"}, "Three-tool"),
]


def seed_supporting_data():
    """Ensures John Perera has a real scheduled delivery of Laptop A,
    so questions 6, 7, and 11 have actual data to find."""
    conn = mysql.connector.connect(
        host=config.MYSQL_HOST, port=config.MYSQL_PORT,
        user=config.MYSQL_USER, password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
    )
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deliveries (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            product_name VARCHAR(255) NOT NULL,
            delivery_date VARCHAR(20) NOT NULL
        )
    """)
    cursor.execute(
        "SELECT id FROM deliveries WHERE customer_name = 'John Perera' AND product_name = 'Laptop A'"
    )
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO deliveries (customer_name, product_name, delivery_date) VALUES (%s, %s, %s)",
            ("John Perera", "Laptop A", "2026-09-10"),
        )
        conn.commit()
        print("Seeded a supporting delivery: John Perera / Laptop A / 2026-09-10")
    else:
        print("Supporting delivery already exists: John Perera / Laptop A")
    cursor.close()
    conn.close()


async def ask_with_retry(agent, question: str):
    """Calls the agent, retrying with exponential backoff on rate limits."""
    backoff = INITIAL_BACKOFF_SECONDS
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await agent.ainvoke({"messages": [{"role": "user", "content": question}]})
        except RateLimitError as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"  [Rate limit hit — attempt {attempt}/{MAX_RETRIES}, "
                  f"waiting {backoff}s before retry] {e}")
            await asyncio.sleep(backoff)
            backoff *= 2


async def main():
    print("Seeding supporting data...")
    seed_supporting_data()
    print()

    print("Building agent...")
    agent = await build_agent()
    print(f"Running {len(TEST_CASES)} multi-tool questions, "
          f"{DELAY_BETWEEN_QUESTIONS_SECONDS}s apart, with rate-limit retry enabled.\n")

    results = []

    for case_id, question, expected_tools, note in TEST_CASES:
        print(f"--- Q{case_id} ---")
        print(f"Question: {question}")
        if note:
            print(f"Note: {note}")

        start = time.perf_counter()
        try:
            response = await ask_with_retry(agent, question)
            elapsed = time.perf_counter() - start

            called_tools = []
            for msg in response["messages"]:
                calls = getattr(msg, "tool_calls", None)
                if calls:
                    called_tools.extend(c["name"] for c in calls)
            called_set = set(called_tools)

            answer = response["messages"][-1].content

            if expected_tools is None:
                verdict = "EXPLORATORY (not graded)"
            elif expected_tools.issubset(called_set):
                verdict = "PASS"
            else:
                missing = expected_tools - called_set
                verdict = f"FAIL (missing: {missing})"

            print(f"Tools called: {called_tools}")
            print(f"Verdict: {verdict}")
            print(f"Time: {elapsed:.2f}s")
            print(f"Answer: {answer[:200]}")

            results.append({
                "id": case_id, "question": question, "called": called_tools,
                "expected": expected_tools, "verdict": verdict, "time": elapsed,
            })

        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"ERROR ({type(e).__name__}): {e}")
            results.append({
                "id": case_id, "question": question, "called": [],
                "expected": expected_tools, "verdict": f"ERROR: {type(e).__name__}", "time": elapsed,
            })

        print()

        if case_id != TEST_CASES[-1][0]:
            await asyncio.sleep(DELAY_BETWEEN_QUESTIONS_SECONDS)

    # -------------------------------------------------------------
    # Final summary
    # -------------------------------------------------------------
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    graded = [r for r in results if r["verdict"] not in ("EXPLORATORY (not graded)",) and not r["verdict"].startswith("ERROR")]
    passed = [r for r in graded if r["verdict"] == "PASS"]
    failed = [r for r in graded if r["verdict"].startswith("FAIL")]
    errored = [r for r in results if r["verdict"].startswith("ERROR")]
    exploratory = [r for r in results if r["verdict"] == "EXPLORATORY (not graded)"]

    print(f"\n{'Q#':<4}{'Verdict':<20}{'Time':>8}   Question")
    for r in results:
        q_short = r["question"][:55] + ("..." if len(r["question"]) > 55 else "")
        print(f"{r['id']:<4}{r['verdict']:<20}{r['time']:>7.2f}s   {q_short}")

    print(f"\nGraded: {len(graded)}   Passed: {len(passed)}   Failed: {len(failed)}   "
          f"Errored: {len(errored)}   Exploratory: {len(exploratory)}")

    if graded:
        accuracy = len(passed) / len(graded) * 100
        print(f"Accuracy on graded questions: {accuracy:.0f}%")

    total_time = sum(r["time"] for r in results)
    print(f"Total wall-clock time: {total_time:.1f}s")

    if failed:
        print("\nFailed cases — review these first:")
        for r in failed:
            print(f"  Q{r['id']}: {r['question']}")
            print(f"       expected {r['expected']}, got {set(r['called'])}")

    if errored:
        print("\nErrored cases:")
        for r in errored:
            print(f"  Q{r['id']}: {r['verdict']}")


if __name__ == "__main__":
    asyncio.run(main())