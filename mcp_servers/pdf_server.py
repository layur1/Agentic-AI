"""
FastMCP server exposing PDF search as a tool.

Loads the pre-built Chroma vectorstore (see ingest_pdf.py) and exposes
a single tool: search_pdf(query).

Run standalone for debugging:
    python mcp_servers/pdf_server.py
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import config

mcp = FastMCP("pdf-server")

_embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
_vectorstore = Chroma(
    persist_directory=config.VECTORSTORE_PATH,
    embedding_function=_embeddings,
)
_retriever = _vectorstore.as_retriever(search_kwargs={"k": 4})


@mcp.tool()
def search_pdf(query: str) -> str:
    """
    Search product manuals, warranty policies, specifications, battery/
    maintenance guidance, and troubleshooting instructions.

    Use this tool for questions about static documentation: warranty terms,
    how something works, specs, maintenance tips, or troubleshooting steps.
    Do NOT use this for prices, stock levels, or anything that changes
    frequently — use the MongoDB tool for that instead.

    Args:
        query: The user's question or the topic to search for.

    Returns:
        The most relevant excerpts from the PDF documentation.
    """
    docs = _retriever.invoke(query)
    if not docs:
        return "No relevant information found in the PDF documentation."

    results = []
    for i, d in enumerate(docs, start=1):
        page = d.metadata.get("page_label", d.metadata.get("page", "?"))
        source = d.metadata.get("source_file", "document")
        results.append(f"[Excerpt {i} — {source}, page {page}]\n{d.page_content}")

    return "\n\n".join(results)


if __name__ == "__main__":
    mcp.run(transport="stdio")