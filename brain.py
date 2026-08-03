"""
The agent's brain: connects to both MCP servers (PDF + MySQL),
loads their tools, and wires them into a Groq-powered ReAct agent.

The LLM decides — per user question — which tool(s) to call, based on
the tool docstrings in mcp_servers/pdf_server.py and mysql_server.py.
No manual if/else routing logic is written here; that's the point.
"""
import os
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

import config

SYSTEM_PROMPT = """You are a helpful product support assistant for TechNova Electronics.

You have access to two kinds of tools:

1. PDF documentation search (search_pdf)
   Use for: warranty policy, specifications, how something works, battery
   and maintenance guidance, troubleshooting steps. This is static
   documentation content.

2. MySQL product database tools (get_price, check_stock, search_products)
   Use for: current price, stock/inventory availability, browsing products
   by category. This is live, frequently-changing structured data.

Always choose the most relevant tool(s) for the question. If a question
needs both kinds of information (e.g. "what's the price and warranty of
Laptop A?"), call both tools and combine the results into one clear answer.
If neither tool returns relevant information, say so honestly rather than
guessing.
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