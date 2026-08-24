"""
The agent's brain: connects to three MCP servers (PDF + MySQL + Weather),
loads their tools, and wires them into a Groq-powered ReAct agent.
"""
import os
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

import config

SYSTEM_PROMPT = """You are a helpful assistant for TechNova Electronics.

You have access to four kinds of tools:

1. PDF documentation search (search_pdf)
   Use for: warranty policy, specifications, how something works, battery
   and maintenance guidance, troubleshooting steps.

2. MySQL product database tools (get_price, check_stock, search_products)
   Use for: current price, stock/inventory availability, browsing products
   by category.

3. MySQL customer and delivery tools (get_user_address, schedule_delivery)
   Use for: retrieving a specific named customer's address, or scheduling
   a product delivery for a customer on a date.

4. Weather tools (get_current_weather, get_weather_forecast, get_weather_alert)
   Use for: current or upcoming weather conditions, or severe weather
   alerts, for a Sri Lankan city.

General rules:
- Always choose the most relevant tool(s) for the question. If a question
  needs information from more than one category, call each relevant tool
  and combine the results into one clear answer.
- If no tool returns relevant information, say so honestly rather than
  guessing.
- NEVER call a tool with a guessed, assumed, empty, or placeholder value
  for a required argument. Some tools require MORE THAN ONE piece of
  information (for example, schedule_delivery needs a customer, a
  product, AND a date; get_weather_alert needs a city AND a date). If any
  required piece is missing, do not call the tool. Instead, ask the user
  for whichever piece(s) are missing — you may ask for several missing
  pieces in a single question — and wait for their reply before calling
  the tool. If the user then supplies some but not all of what's still
  missing, ask again for only what remains, rather than guessing or
  giving up.
- If a tool reports that a name or value you provided matched more than
  one record, do not guess which one was meant — relay the list of
  matches to the user as a question and wait for their reply.
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
    "weather": {
        "command": "python",
        "args": [os.path.join(_this_dir, "mcp_servers", "weather_server.py")],
        "transport": "stdio",
    },
})


async def build_agent():
    """Fetches tools from all three MCP servers and builds the ReAct agent."""
    config.require_groq_key()

    tools = await _client.get_tools()

    llm = ChatGroq(
        model=config.GROQ_MODEL,
        temperature=0,
        api_key=config.GROQ_API_KEY,
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