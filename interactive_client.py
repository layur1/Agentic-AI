import requests

API_URL = "http://localhost:8000/chat"
API_KEY = "fb098eccc1aaaddbc5d259ae478789e18e064a356f936171c8c8fa8b81772afc"


def main():
    session_id = None

    print("Connected to the multi-user API server.")
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
            print(f"[This terminal's session_id: {session_id}]\n")

        print(f"Assistant: {data['response']}\n")


if __name__ == "__main__":
    main()