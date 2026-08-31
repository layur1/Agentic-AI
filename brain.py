"""
The agent's brain: connects to two MCP servers (PDF + MySQL), loads their
tools, and wires them into an OpenAI-powered ReAct agent.
"""
import os
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

import config

SYSTEM_PROMPT = """You are a helpful assistant for TechNova Electronics.

You have access to four kinds of tools:

1. PDF documentation search (search_pdf)
   Use for: warranty policy, specifications, how something works, battery
   and maintenance guidance, troubleshooting steps.

2. Product lookup tools (get_price, check_stock, search_products,
   get_products_by_price_range)
   Use for: current price, stock/inventory availability, browsing
   products by category, or filtering by a numeric price range.

3. Customer tools (get_user_address, search_customers, add_new_customer)
   Use for: retrieving a specific named customer's address, browsing/
   searching customer names without revealing addresses, or registering
   a new customer.

4. Delivery tools (schedule_delivery, get_delivery_status, cancel_delivery)
   Use for: scheduling a new delivery, checking a customer's scheduled
   deliveries, or cancelling an existing one.

General rules:
- Always choose the most relevant tool(s) for the question. If a question
  needs information from more than one category, call each relevant tool
  and combine the results into one clear answer.
- If no tool returns relevant information, say so honestly rather than
  guessing.
- NEVER call a tool with a guessed, assumed, empty, or placeholder value
  for a required argument. Some tools require MORE THAN ONE piece of
  information (for example, schedule_delivery needs a customer, a
  product, AND a date). If any required piece is missing, do not call the
  tool. Instead, ask the user for whichever piece(s) are missing — you
  may ask for several missing pieces in a single question — and wait for
  their reply before calling the tool. If the user then supplies some but
  not all of what's still missing, ask again for only what remains,
  rather than guessing or giving up.
- If a tool reports that a name or value you provided matched more than
  one record, do not guess which one was meant — relay the list of
  matches to the user as a question and wait for their reply.
- Several tools have similar names or purposes (for example,
  get_user_address vs search_customers, or get_price vs
  get_products_by_price_range). Read each tool's description carefully to
  pick the one that actually matches what the user is asking for, rather
  than the first plausible-sounding name.
"""

_this_dir = os.path.dirname(os.path.abspath(__file__))

_client = MultiServerMCPClient({
    "pdf": {
        "command": "python",
        "args": [os.path.join(_this_dir, "mcp_servers", "pdf_server.py")],
        "transport": "stdio",
    },
    "mysql": {
        "command": "python",
        "args": [os.path.join(_this_dir, "mcp_servers", "mysql_server.py")],
        "transport": "stdio",
    },
})


async def build_agent():
    """Fetches tools from both MCP servers and builds the ReAct agent."""
    config.require_openai_key()

    tools = await _client.get_tools()

    llm = ChatOpenAI(
        model=config.OPENAI_MODEL,
        temperature=0,
        api_key=config.OPENAI_API_KEY,
    )

    agent = create_react_agent(llm, tools=tools, prompt=SYSTEM_PROMPT)
    return agent


async def ask(agent, question: str, history=None) -> str:
    """
    Sends a question (with optional prior conversation history) to the
    agent and returns the final text answer.
    """
    messages = (history or []) + [{"role": "user", "content": question}]
    response = await agent.ainvoke({"messages": messages})
    final_message = response["messages"][-1]
    return final_message.content