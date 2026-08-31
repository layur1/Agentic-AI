"""
Controlled experiment: does removing a tool's docstring actually change
routing behavior? Tests THREE conditions:

  A) BASELINE       - all three tools keep their real descriptions
  B) ONE_STRIPPED    - only check_stock's description is emptied
  C) ALL_STRIPPED    - all three tools' descriptions are emptied

Uses deliberately AMBIGUOUS questions, since only ambiguous questions can
reveal a difference — a question with one obvious answer will pass in
every condition regardless of description text.

Bypasses MCP (same reason test_description_length.py does) so the ONLY
variable changing between conditions is description text, using your
real MySQL data underneath.

Run from the project root:
    python testing/test_docstring_importance.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import mysql.connector
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

import config

REAL_DESCRIPTIONS = {
    "get_price": (
        "Get the current price of a product by name. Use this for questions "
        "about cost or price — this is live database data, not stock/inventory "
        "and not documentation."
    ),
    "check_stock": (
        "Check current inventory/stock level for a product. Use this for "
        "questions like 'is X in stock' or 'is X available' — NOT for price "
        "questions, use get_price for those instead."
    ),
    "search_products": (
        "Search products by name or category, browsing broadly. Use this "
        "when the user names a category or wants to browse multiple items, "
        "not for a single specific product's price or stock."
    ),
}

TEST_QUESTIONS = [
    ("Is Laptop A available?", {"check_stock", "search_products"}),
    ("What can you tell me about Laptop A?", {"get_price", "check_stock", "search_products"}),
    ("Do you have the Wireless Mouse M1?", {"check_stock", "search_products"}),
]


def _get_connection():
    return mysql.connector.connect(
        host=config.MYSQL_HOST, port=config.MYSQL_PORT,
        user=config.MYSQL_USER, password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
    )


def build_tools(descriptions: dict):
    @tool(description=descriptions["get_price"])
    def get_price(product_name: str) -> str:
        conn = _get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product_name, price FROM products WHERE product_name LIKE %s LIMIT 1",
                       (f"%{product_name}%",))
        row = cursor.fetchone()
        cursor.close(); conn.close()
        return f"{row['product_name']}: Rs. {row['price']:,.2f}" if row else "Not found."

    @tool(description=descriptions["check_stock"])
    def check_stock(product_name: str) -> str:
        conn = _get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT product_name, stock FROM products WHERE product_name LIKE %s LIMIT 1",
                       (f"%{product_name}%",))
        row = cursor.fetchone()
        cursor.close(); conn.close()
        if not row:
            return "Not found."
        return f"{row['product_name']}: {'In stock' if row['stock'] > 0 else 'Out of stock'} ({row['stock']} units)"

    @tool(description=descriptions["search_products"])
    def search_products(query: str) -> str:
        conn = _get_connection()
        cursor = conn.cursor(dictionary=True)
        like = f"%{query}%"
        cursor.execute("SELECT product_name, category, price, stock FROM products "
                       "WHERE product_name LIKE %s OR category LIKE %s", (like, like))
        rows = cursor.fetchall()
        cursor.close(); conn.close()
        if not rows:
            return "Not found."
        return "\n".join(f"- {r['product_name']}: Rs. {r['price']:,.2f}, {r['stock']} in stock" for r in rows)

    return [get_price, check_stock, search_products]


async def run_condition(name: str, descriptions: dict):
    config.require_openai_key()
    llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)
    tools = build_tools(descriptions)
    agent = create_react_agent(llm, tools=tools)

    print(f"\n===== Condition: {name} =====")
    for question, acceptable_tools in TEST_QUESTIONS:
        response = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})
        called = []
        for msg in response["messages"]:
            calls = getattr(msg, "tool_calls", None)
            if calls:
                called.extend(c["name"] for c in calls)

        called_set = set(called)
        reasonable = bool(called_set & acceptable_tools) if called_set else False
        verdict = "OK" if reasonable else "MISROUTE / NO TOOL"
        print(f"  Q: {question}")
        print(f"    tool(s) called: {called or 'none'}  [{verdict}]")


async def main():
    empty = {"get_price": "", "check_stock": "", "search_products": ""}
    one_stripped = dict(REAL_DESCRIPTIONS)
    one_stripped["check_stock"] = ""

    await run_condition("A) BASELINE (all real descriptions)", REAL_DESCRIPTIONS)
    await run_condition("B) ONE_STRIPPED (only check_stock emptied)", one_stripped)
    await run_condition("C) ALL_STRIPPED (all three emptied)", empty)


if __name__ == "__main__":
    asyncio.run(main())