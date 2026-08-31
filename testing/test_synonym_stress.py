"""
Stress test: pushes the "docstrings don't matter" question to a harder
edge than test_docstring_importance.py — CLUSTERS of near-synonym tools
(several tools that could all plausibly answer the same kind of
question), all with EMPTY descriptions and NO system prompt.

Every tool here is a stub (no real database) so the ONLY variable is
whether the model can pick a semantically-correct tool by name alone.

Run from the project root:
    python testing/test_synonym_stress.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

import config

# CLUSTER 1: four different names, all plausibly "get the price"
@tool(description="")
def get_price(product_name: str) -> str:
    return "CALLED: get_price"

@tool(description="")
def get_product_cost(product_name: str) -> str:
    return "CALLED: get_product_cost"

@tool(description="")
def fetch_item_price(product_name: str) -> str:
    return "CALLED: fetch_item_price"

@tool(description="")
def retrieve_cost(product_name: str) -> str:
    return "CALLED: retrieve_cost"

# CLUSTER 2: four different names, all plausibly "check stock"
@tool(description="")
def check_stock(product_name: str) -> str:
    return "CALLED: check_stock"

@tool(description="")
def get_inventory_level(product_name: str) -> str:
    return "CALLED: get_inventory_level"

@tool(description="")
def get_availability(product_name: str) -> str:
    return "CALLED: get_availability"

@tool(description="")
def check_quantity(product_name: str) -> str:
    return "CALLED: check_quantity"

# CLUSTER 3: four different names, all plausibly "get an address"
@tool(description="")
def get_user_address(user_name: str) -> str:
    return "CALLED: get_user_address"

@tool(description="")
def get_customer_location(user_name: str) -> str:
    return "CALLED: get_customer_location"

@tool(description="")
def fetch_client_address(user_name: str) -> str:
    return "CALLED: fetch_client_address"

@tool(description="")
def get_delivery_address(user_name: str) -> str:
    return "CALLED: get_delivery_address"


ALL_TOOLS = [
    get_price, get_product_cost, fetch_item_price, retrieve_cost,
    check_stock, get_inventory_level, get_availability, check_quantity,
    get_user_address, get_customer_location, fetch_client_address, get_delivery_address,
]

PRICE_CLUSTER = {"get_price", "get_product_cost", "fetch_item_price", "retrieve_cost"}
STOCK_CLUSTER = {"check_stock", "get_inventory_level", "get_availability", "check_quantity"}
ADDRESS_CLUSTER = {"get_user_address", "get_customer_location", "fetch_client_address", "get_delivery_address"}

TEST_CASES = [
    ("What does Laptop A cost?", PRICE_CLUSTER),
    ("How many Laptop A units are left?", STOCK_CLUSTER),
    ("Where does John Perera live?", ADDRESS_CLUSTER),
    ("Is Laptop A available and how much is it?", PRICE_CLUSTER | STOCK_CLUSTER),
]


async def main():
    config.require_openai_key()
    llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0, api_key=config.OPENAI_API_KEY)
    agent = create_react_agent(llm, tools=ALL_TOOLS)  # NOTE: no system prompt either

    print(f"Testing with {len(ALL_TOOLS)} tools, ALL with empty descriptions, NO system prompt.\n")

    correct = 0
    for question, acceptable_cluster in TEST_CASES:
        response = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})
        called = []
        for msg in response["messages"]:
            calls = getattr(msg, "tool_calls", None)
            if calls:
                called.extend(c["name"] for c in calls)

        called_set = set(called)
        is_correct = bool(called_set & acceptable_cluster)
        correct += int(is_correct)
        redundant = len(called) > len(called_set & acceptable_cluster) if is_correct else False

        print(f"Q: {question}")
        print(f"  tool(s) called: {called or 'none'}")
        print(f"  acceptable cluster: {acceptable_cluster}")
        verdict = "CORRECT CLUSTER"
        if redundant:
            verdict += " (but called MORE than one tool from the cluster — hedging, not confident)"
        print(f"  verdict: {verdict if is_correct else 'WRONG / NO TOOL / MULTIPLE CLUSTERS'}\n")

    print(f"===== {correct}/{len(TEST_CASES)} correct with {len(ALL_TOOLS)} tools, zero descriptions =====")


if __name__ == "__main__":
    asyncio.run(main())