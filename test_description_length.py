"""
Tests how the LENGTH and WORDING of a tool's description affects routing
accuracy.

Save this file directly in your project root (D:\\agentic_ai), the same
folder as config.py.

Run:
    python test_description_length.py
"""
import asyncio
import time

from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

import config

# ---------------------------------------------------------------------
# Three description variants for the SAME underlying function.
# ---------------------------------------------------------------------

DESCRIPTIONS = {
    "TOO_SHORT": "Searches documents.",

    "REASONABLE": (
        "Search product manuals, warranty policies, specifications, and "
        "troubleshooting instructions. Use this for questions about static "
        "documentation — not for prices or stock, which change frequently."
    ),

    "TOO_LONG": (
        "This tool is designed to search through a comprehensive knowledge base "
        "of product documentation that has been carefully compiled and indexed "
        "using advanced semantic vector embeddings, covering a wide range of "
        "topics including but not limited to product warranty terms and "
        "conditions, detailed technical specifications for various hardware "
        "components, step by step troubleshooting procedures for common issues "
        "users might encounter, maintenance recommendations to extend product "
        "lifespan, battery care guidelines, and general information about how "
        "various product features and functions operate under normal and "
        "abnormal circumstances. This tool should be used whenever a user asks "
        "any kind of question that might conceivably be answered by consulting "
        "written documentation, manuals, guides, or reference material, as "
        "opposed to consulting a live, frequently-updated structured database "
        "which would instead be used for retrieving current pricing information, "
        "real-time inventory and stock availability counts, and other "
        "transactional or frequently-changing structured data points."
    ),
}

# Fixed test battery — deliberately includes some easy and some ambiguous cases
TEST_QUESTIONS = [
    ("What is the warranty on Laptop A?", "search_pdf"),
    ("How do I maximize battery life on Laptop A?", "search_pdf"),
    ("Is the Bluetooth Speaker S2 water-resistant?", "search_pdf"),
    ("Laptop A won't turn on, what should I do?", "search_pdf"),
    ("What are the specifications of Laptop B?", "search_pdf"),
]


def build_pdf_tool(description: str):
    embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
    vectorstore = Chroma(persist_directory=config.VECTORSTORE_PATH, embedding_function=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    @tool(description=description)
    def search_pdf(query: str) -> str:
        docs = retriever.invoke(query)
        if not docs:
            return "No relevant information found."
        return "\n\n".join(d.page_content for d in docs)

    return search_pdf


async def run_variant(name: str, description: str):
    config.require_groq_key()
    llm = ChatGroq(model=config.GROQ_MODEL, temperature=0, api_key=config.GROQ_API_KEY)
    tool_fn = build_pdf_tool(description)
    agent = create_react_agent(llm, tools=[tool_fn])

    correct = 0
    total_latency = 0.0

    for question, expected_tool in TEST_QUESTIONS:
        start = time.perf_counter()
        response = await agent.ainvoke({"messages": [{"role": "user", "content": question}]})
        elapsed = time.perf_counter() - start
        total_latency += elapsed

        called_tools = []
        for msg in response["messages"]:
            calls = getattr(msg, "tool_calls", None)
            if calls:
                called_tools.extend(c["name"] for c in calls)

        was_correct = expected_tool in called_tools
        correct += int(was_correct)
        print(f"  [{name}] Q: {question[:50]:<50} tool_called={called_tools} "
              f"{'OK' if was_correct else 'MISROUTE'} ({elapsed:.2f}s)")

    accuracy = correct / len(TEST_QUESTIONS) * 100
    avg_latency = total_latency / len(TEST_QUESTIONS)
    word_count = len(description.split())
    print(f"\n  >> {name}: {accuracy:.0f}% accuracy | "
          f"avg latency {avg_latency:.2f}s | description length {word_count} words\n")
    return accuracy, avg_latency, word_count


async def main():
    results = {}
    for name, desc in DESCRIPTIONS.items():
        print(f"\n===== Testing variant: {name} =====")
        results[name] = await run_variant(name, desc)

    print("\n===== SUMMARY =====")
    print(f"{'Variant':<12} {'Words':>8} {'Accuracy':>10} {'Avg Latency':>14}")
    for name, (acc, lat, words) in results.items():
        print(f"{name:<12} {words:>8} {acc:>9.0f}% {lat:>13.2f}s")


if __name__ == "__main__":
    asyncio.run(main())