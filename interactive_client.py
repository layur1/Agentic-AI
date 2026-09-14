#python interactive_client.py -> starts a brand new conversation, prints its session_id
#python interactive_client.py 3f2a1c9e-...-b8d1 -> resumes that exact conversation, with full history intact
        
import sys
import requests

API_URL = "http://localhost:8000/chat"
API_KEY = "fb098eccc1aaaddbc5d259ae478789e18e064a356f936171c8c8fa8b81772afc"


def main():
    session_id = sys.argv[1] if len(sys.argv) > 1 else None

    print("Connected to the API server.")
    if session_id:
        print(f"Resuming session: {session_id}")
    print("Type a message and press Enter. Type 'exit' to quit.\n")

    while True:
        try:
            message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not message:
            continue
        if message.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        payload = {"message": message}
        if session_id:
            payload["session_id"] = session_id

        try:
            response = requests.post(API_URL, json=payload, headers={"X-API-Key": API_KEY})
        except requests.exceptions.ConnectionError:
            print("Could not reach the server. Is api_server.py running?\n")
            continue

        data = response.json()

        if response.status_code != 200:
            print(f"Error ({response.status_code}): {data.get('detail', data)}\n")
            continue

        if session_id is None:
            session_id = data["session_id"]
            print(f"[This conversation's session_id: {session_id}]")
            print(f"[Save this to resume later: python interactive_client.py {session_id}]\n")

        print(f"Assistant: {data['response']}\n")


if __name__ == "__main__":
    main()