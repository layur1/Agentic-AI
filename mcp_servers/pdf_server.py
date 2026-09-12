import os
import sys


sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from mcp.server.fastmcp import FastMCP
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import config


mcp = FastMCP("pdf-server")


# ============================================================
# VECTOR STORE
# ============================================================

_embeddings = HuggingFaceEmbeddings(
    model_name=config.EMBEDDING_MODEL
)


_vectorstore = Chroma(
    persist_directory=config.VECTORSTORE_PATH,
    embedding_function=_embeddings,
)


_retriever = _vectorstore.as_retriever(
    search_kwargs={"k": 4}
)


# ============================================================
# PDF TOOL
# ============================================================

@mcp.tool(
    name="search_pdf",
    description=(
        "Search the product documentation for static information "
        "such as product specifications, warranty terms, battery "
        "information, maintenance instructions, troubleshooting "
        "procedures, returns, and support information. "
        "Use this tool when the answer is contained in the product "
        "manuals. Do not use it for current prices, stock availability, "
        "customer information, or delivery information."
    ),
)
def search_pdf(query: str) -> str:

    if not query or not query.strip():
        return "A search query is required."

    documents = _retriever.invoke(
        query.strip()
    )

    if not documents:
        return (
            "No relevant information was found in "
            "the product documentation."
        )

    results = []

    for index, document in enumerate(
        documents,
        start=1
    ):

        page = document.metadata.get(
            "page_label",
            document.metadata.get(
                "page",
                "?"
            )
        )

        source = document.metadata.get(
            "source_file",
            "document"
        )

        results.append(
            f"[Excerpt {index} — {source}, page {page}]\n"
            f"{document.page_content}"
        )

    return "\n\n".join(results)


# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")