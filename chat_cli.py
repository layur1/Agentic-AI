"""
Simple interactive command-line chat interface.

Run:
    python chat_cli.py
"""
import asyncio
from brain import build_agent, ask


async def main():
    print("Building agent ...")
    agent = await build_agent()
    print("Ready. Ask a question about TechNova products (type 'exit' to quit).\n")

    history = []
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        answer = await ask(agent, question, history)
        print(f"\nAssistant: {answer}\n")

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    asyncio.run(main())