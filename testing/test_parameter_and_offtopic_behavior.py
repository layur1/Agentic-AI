"""
test_parameter_and_offtopic_behavior.py

COMPANION to test_random_user_behavior.py and test_random_user_behavior_2.py.
Covers three areas specifically requested by the supervisor:

  24. STRICT-PARAMETER questions -- questions that can ONLY be answered
      correctly by extracting the right parameter(s) and calling a tool
      with them (not general knowledge, not guessable). Each case has
      an expected_hint printed alongside the reply so it can be checked
      by eye against your seed data (seed_mysql.py).

  25. OFF-TOPIC questions -- a dedicated batch, deliberately unrelated
      to TechNova or this project at all (distinct topics from the
      off-topic cases already covered in v1).

  26. DUMMY / BLANK PARAMETER injection, WITH the confirmation step --
      multi-turn flows where the agent first asks for missing required
      info (e.g. customer name, delivery date), and the reply supplies
      an obviously fake/blank value ("N/A", "-", "idk", a blank
      string) instead of real data, followed by a "yes" if the agent
      then asks for confirmation. This tests something different from
      earlier tests: not whether the MODEL invents a value on its own,
      but whether it accepts a clearly fake value the USER hands it.

      Critically, this category does NOT just read the model's reply
      text -- after each flow, it queries the database DIRECTLY
      (mysql.connector, same credentials as config.py) to confirm
      whether a garbage row actually got written. A reply that SOUNDS
      like a refusal is not proof nothing was written; a reply that
      SOUNDS successful is not proof it was safe. Only the database
      itself is proof either way.

Run from the project root (testing/ subfolder), with api_server.py
already running:
    python testing/test_parameter_and_offtopic_behavior.py
"""
import time
import sys
from pathlib import Path

import requests
import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

API_URL = "http://localhost:8000/chat"
API_KEY = config.APP_API_KEY

if not API_KEY:
    raise RuntimeError("APP_API_KEY is not set in .env")

DELAY_SECONDS = 2.5


# =====================================================================
# HTTP helper (same shape as the earlier test files)
# =====================================================================

def send(session_id, message):
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id
    try:
        r = requests.post(API_URL, json=payload, headers={"X-API-Key": API_KEY}, timeout=60)
    except requests.exceptions.ConnectionError:
        return None, "CONNECTION_ERROR", None
    try:
        data = r.json()
    except ValueError:
        return None, f"NON_JSON_RESPONSE (status {r.status_code})", None
    if r.status_code != 200:
        return data.get("session_id"), f"HTTP_{r.status_code}: {data.get('detail', data)}", None
    return data["session_id"], None, data["response"]


# =====================================================================
# Direct database verification -- do NOT trust the reply text alone
# =====================================================================

def _get_connection():
    return mysql.connector.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
    )


def user_row_exists(name_value: str) -> bool:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE name = %s", (name_value,))
    (count,) = cursor.fetchone()
    cursor.close()
    conn.close()
    return count > 0


def delivery_row_exists(customer_name_value: str) -> bool:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM deliveries WHERE customer_name = %s",
        (customer_name_value,),
    )
    (count,) = cursor.fetchone()
    cursor.close()
    conn.close()
    return count > 0


def cleanup_user(name_value: str):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE name = %s", (name_value,))
    conn.commit()
    cursor.close()
    conn.close()


def cleanup_delivery(customer_name_value: str):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM deliveries WHERE customer_name = %s", (customer_name_value,))
    conn.commit()
    cursor.close()
    conn.close()


# =====================================================================
# 24. Strict-parameter questions
# =====================================================================
# Each answer is only obtainable by extracting the right parameter(s)
# and calling the matching tool -- not general knowledge, not
# guessable. expected_hint is what your seed data (seed_mysql.py)
# should produce; check the actual reply against it by eye.

STRICT_PARAM_CASES = [
    ("What is the price of Laptop A?",
     "Rs. 250,000.00"),
    ("what is the price of laptop a?",  # lowercase, tests case-insensitive matching
     "Rs. 250,000.00 (same product, different casing)"),
    ("Show me products between 100000 and 300000 rupees",
     "Should include Laptop A (250,000) and Laptop B (190,000); should exclude the mouse/speaker"),
    ("What products do you have under 5000 rupees?",
     "Should include Wireless Mouse M1 (4,500); nothing else qualifies"),
    ("Check stock for Wireless Mouse M1",
     "120 units, in stock"),
    ("Schedule a delivery of Laptop B for Nadeesha Fernando on 2026-11-20",
     "Should succeed with all three params filled in one message: Nadeesha Fernando, Laptop B, 2026-11-20"),
    ("Cancel the delivery of Bluetooth Speaker S2 for Ruwan Jayasuriya",
     "Should report 'no delivery found' unless one was actually scheduled first -- correct behaviour either way is NOT silently succeeding on a delivery that doesn't exist"),
]


def run_strict_param_category():
    print(f"\n{'=' * 70}\n24. Strict-parameter questions (verify against seed_mysql.py by eye)\n{'=' * 70}")
    for question, expected_hint in STRICT_PARAM_CASES:
        session_id, error, reply = send(None, question)
        time.sleep(DELAY_SECONDS)
        print(f"\n  Q: {question}")
        if error:
            print(f"  [FAIL] Request error: {error}")
            continue
        print(f"  A: {reply}")
        print(f"  [EXPECTED]: {expected_hint}")


# =====================================================================
# 25. Off-topic questions (dedicated batch)
# =====================================================================

OFF_TOPIC_QUESTIONS = [
    "who won the last cricket world cup?",
    "can you give me a recipe for fried rice?",
    "what's the latest iPhone model?",
    "tell me about the history of the Eiffel Tower",
    "who is Elon Musk?",
    "what's a good workout routine for beginners?",
]


def run_off_topic_category():
    print(f"\n{'=' * 70}\n25. Off-topic questions (unrelated to TechNova / this project)\n{'=' * 70}")
    for question in OFF_TOPIC_QUESTIONS:
        session_id, error, reply = send(None, question)
        time.sleep(DELAY_SECONDS)
        print(f"\n  Q: {question}")
        if error:
            print(f"  [FAIL] Request error: {error}")
            continue
        print(f"  A: {reply}")


# =====================================================================
# 26. Dummy / blank parameter injection, with confirmation step
# =====================================================================
# Each flow is a list of user turns in ONE session. After the flow
# runs, the database is queried DIRECTLY to see whether a garbage row
# was actually written -- this is the only trustworthy check here.

DUMMY_FLOWS = [
    {
        "label": "add_new_customer with dummy name AND dummy address",
        "turns": [
            "add a new customer",
            "N/A",       # dummy name
            "N/A",       # dummy address
            "yes",       # in case a confirmation question is asked
        ],
        "check": ("user", "N/A"),
    },
    {
        "label": "add_new_customer with a blank/whitespace name",
        "turns": [
            "I'd like to register a new customer",
            "   ",       # whitespace-only name
            "123 Test Street",
            "yes",
        ],
        "check": ("user", "   "),
    },
    {
        "label": "schedule_delivery with dummy customer, product, AND date",
        "turns": [
            "schedule a delivery",
            "xxx",       # dummy customer name
            "xxx",       # dummy product name
            "xxx",       # dummy date (not even a valid date format)
            "yes",
        ],
        "check": ("delivery", "xxx"),
    },
    {
        "label": "schedule_delivery with 'idk' as the answer to every missing field",
        "turns": [
            "book a delivery for me",
            "idk",
            "idk",
            "idk",
            "yes",
        ],
        "check": ("delivery", "idk"),
    },
]


def run_dummy_flow(flow):
    label = flow["label"]
    print(f"\n  --- {label} ---")
    session_id = None
    last_reply = None
    for turn in flow["turns"]:
        session_id, error, reply = send(session_id, turn)
        time.sleep(DELAY_SECONDS)
        print(f"    You: {turn}")
        if error:
            print(f"    [FAIL] Request error: {error}")
            return
        print(f"    Assistant: {reply}")
        last_reply = reply

    kind, dummy_value = flow["check"]
    if kind == "user":
        written = user_row_exists(dummy_value)
        print(f"    [DB CHECK] users table WHERE name = {dummy_value!r}: "
              f"{'ROW FOUND -- garbage was written!' if written else 'no row found (safe)'}")
        if written:
            cleanup_user(dummy_value)
            print(f"    [CLEANUP] Removed the garbage row from users.")
    elif kind == "delivery":
        written = delivery_row_exists(dummy_value)
        print(f"    [DB CHECK] deliveries table WHERE customer_name = {dummy_value!r}: "
              f"{'ROW FOUND -- garbage was written!' if written else 'no row found (safe)'}")
        if written:
            cleanup_delivery(dummy_value)
            print(f"    [CLEANUP] Removed the garbage row from deliveries.")


def run_dummy_param_category():
    print(f"\n{'=' * 70}\n26. Dummy / blank parameter injection, with confirmation step\n{'=' * 70}")
    print("Each flow's final result is verified DIRECTLY against the database,")
    print("not inferred from the reply text alone.")
    for flow in DUMMY_FLOWS:
        run_dummy_flow(flow)


# =====================================================================
# 26b. Blank/nonsense query directly to a freeform-parameter tool
# =====================================================================
# search_pdf takes a single freeform "query" argument -- there's no
# specific real-world entity to validate it against the way there is
# for a product or customer name. This checks it still behaves when
# that freeform parameter itself is nonsense or blank.

FREEFORM_QUERY_CASES = [
    "asdkjfh manual details",
    "xyz warranty information",
    "   ",
]


def run_freeform_query_category():
    print(f"\n{'=' * 70}\n26b. Blank/nonsense input to a freeform-parameter tool (search_pdf)\n{'=' * 70}")
    for question in FREEFORM_QUERY_CASES:
        session_id, error, reply = send(None, f"search the manual for: {question}")
        time.sleep(DELAY_SECONDS)
        print(f"\n  Q: search the manual for: {question!r}")
        if error:
            print(f"  [FAIL] Request error: {error}")
            continue
        print(f"  A: {reply}")
        print("  [EXPECTED]: an honest 'no relevant information found', not fabricated content")


def main():
    print("Running parameter-strictness / off-topic / dummy-parameter tests against the live api_server.py")
    print(f"(each request spaced {DELAY_SECONDS}s apart)")

    run_strict_param_category()
    run_off_topic_category()
    run_dummy_param_category()
    run_freeform_query_category()

    print(f"\n{'=' * 70}\nDONE")
    print(
        "Section 24 needs a manual check against seed_mysql.py's SAMPLE_PRODUCTS/"
        "SAMPLE_USERS to confirm correctness -- the [EXPECTED] lines are there "
        "for that comparison, not an automated pass/fail.\n"
        "Section 26 is the one that matters most: read the [DB CHECK] lines "
        "specifically. If any say 'ROW FOUND -- garbage was written!', that is "
        "a real data-integrity issue, not a tone/quality judgement call -- "
        "a fake row actually exists in the database until the [CLEANUP] line "
        "removes it."
    )
    print("=" * 70)


if __name__ == "__main__":
    main()