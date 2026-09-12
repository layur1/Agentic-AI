import requests

API_URL = "http://localhost:8000/chat"
API_KEY = "fb098eccc1aaaddbc5d259ae478789e18e064a356f936171c8c8fa8b81772afc"

r = requests.post(API_URL, json={"message": "What is the price of Laptop A?"},
                   headers={"X-API-Key": API_KEY})
print(r.json())
session_id = r.json()["session_id"]

r = requests.post(API_URL, json={"session_id": session_id, "message": "And its warranty?"},
                   headers={"X-API-Key": API_KEY})
print(r.json())