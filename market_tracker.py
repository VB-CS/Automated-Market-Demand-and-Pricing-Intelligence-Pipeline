from serpapi import GoogleSearch
import json
import os
from dotenv import load_dotenv

# Load the keys from the hidden .env file into system environment memory
load_dotenv()

# Securely grab the API key from environment memory
API_KEY = os.getenv("SERPAPI_API_KEY")

params = {
  "engine": "google_shopping",
  "q": "MacBook Pro M3",
  "location": "Austin, Texas, United States",
  "api_key": API_KEY 
}

# Connect and fetch data
search = GoogleSearch(params)
results = search.get_dict()

# Print the data to verify the bridge is working
if "shopping_results" in results:
    for item in results["shopping_results"]:
        print(f"Product: {item.get('title')}")
        print(f"Price: {item.get('price')}")
        print("-" * 20)
else:
    print("Connection failed. Check your API key configuration.")