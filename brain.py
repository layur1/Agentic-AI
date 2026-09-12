import os
import sys

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

import config


SYSTEM_PROMPT = """
You are a helpful assistant for TechNova Electronics.

You have access to tools provided by MCP servers.

Use the available tools to answer the user's questions accurately.

General rules:

1. Select tools based on their names, descriptions, input schemas,
   and the user's request.

2. If a question requires multiple tools, use all relevant tools
   and combine their results into one clear answer.

3. Do not guess information that should be obtained from a tool.

4. Never provide guessed, empty, or placeholder values for required
   tool arguments.

5. If a required argument is missing, ask the user for the missing
   information before calling the tool.

6. If a tool reports that multiple records match the supplied value,
   do not choose one arbitrarily. Ask the user to clarify.

7. If a tool returns no relevant information, say so honestly.

8. Do not expose internal tool names, implementation details,
   SQL queries, or MCP protocol details unless the user specifically
   asks about them.

9. Base answers on information returned by the available tools.
   Do not invent information.

10. Treat the supplied conversation history as belonging only to the
    current user session. Never assume that information from another
    session or user belongs to the current conversation.
"""


_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_MCP_SERVERS_DIR = os.path.join(_THIS_DIR, "mcp_servers")


def discover_mcp_servers() -> dict:
    """
    Automatically discover MCP server files.

    Every Python file inside the mcp_servers directory whose name
    ends with '_server.py' is treated as an MCP server.
    """

    servers = {}

    if not os.path.isdir(_MCP_SERVERS_DIR):
        raise RuntimeError(
            f"MCP server directory not found: {_MCP_SERVERS_DIR}"
        )

    for filename in sorted(os.listdir(_MCP_SERVERS_DIR)):

        if not filename.endswith("_server.py"):
            continue

        server_name = filename[:-len("_server.py")]

        server_path = os.path.join(
            _MCP_SERVERS_DIR,
            filename
        )

        servers[server_name] = {
            "command": sys.executable,
            "args": [server_path],
            "transport": "stdio",
        }

    if not servers:
        raise RuntimeError(
            f"No MCP servers found in {_MCP_SERVERS_DIR}"
        )

    return servers


# The brain does not contain individual tool names.
# It automatically discovers MCP servers.
_client = MultiServerMCPClient(
    discover_mcp_servers()
)


async def build_agent():

    config.require_openai_key()

    # MCP servers provide the tools, descriptions,
    # and input schemas.
    tools = await _client.get_tools()

    llm = ChatOpenAI(
        model=config.OPENAI_MODEL,
        temperature=0,
        api_key=config.OPENAI_API_KEY,
    )

    agent = create_react_agent(
        llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )

    return agent


async def ask(
    agent,
    question: str,
    history=None
) -> str:

    messages = (history or []) + [
        {
            "role": "user",
            "content": question,
        }
    ]

    response = await agent.ainvoke(
        {
            "messages": messages
        }
    )

    final_message = response["messages"][-1]

    return final_message.content