from serpapi import GoogleSearch
import json

# Your API Key from SerpApi Dashboard
params = {
  "engine": "google_shopping",
  "q": "MacBook Pro M3",
  "location": "Austin, Texas, United States",
  "api_key": "b01477bb312f2a15f48545f460490516a32559229ed9e18b3b703cfa2c1d5ff5"
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
    print("Connection failed. Check your API key.")