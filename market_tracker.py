from serpapi import GoogleSearch
import json
import os
from dotenv import load_dotenv
import psycopg2


load_dotenv()


API_KEY = os.getenv("SERPAPI_API_KEY")


TARGET_BASKET = [
    "Corsair Vengeance DDR5 32GB 6000MHz",
    "G.Skill Trident Z5 RGB DDR5 32GB 6000MHz",
    "Crucial Pro DDR5 32GB 6000MHz",
    "G.Skill Trident Z5 DDR5 64GB 6400MHz"
]

clean_database_ready_list = []
seen_listings = set()


for product_name in TARGET_BASKET:
    params = {
        "engine": "google_shopping",
        "q": product_name,
        "location": "Austin, Texas, United States",
        "api_key": API_KEY 
    }


    search = GoogleSearch(params)
    results = search.get_dict()


    if "shopping_results" in results:
        for item in results["shopping_results"]:
            
            title = item.get("title")
            price = item.get("price")
            

            if title is None or price is None:
                continue 
                
            clean_price_string = price.replace("$", "").replace(",", "")
            

            try:

                normalized_price = float(clean_price_string)
            except ValueError:

                continue 
                
            unique_identifier = (title, normalized_price)
            

            if unique_identifier not in seen_listings:
                seen_listings.add(unique_identifier)
                

                item["price"] = normalized_price
                clean_database_ready_list.append(item)
                
                print(f"Clean Product: {title}")
                print(f"Clean Price: {normalized_price}")
                print("-" * 20)
            raw_title = item.get("title")


            machine_friendly_title = raw_title.lower().strip()


            item["display_title"] = raw_title
            item["normalized_title"] = machine_friendly_title


print(f"Total Cleaned Items Across All Searches: {len(clean_database_ready_list)}")

# --- DATABASE INJECTION ---

print("\nConnecting to PostgreSQL...")

try:

    conn = psycopg2.connect(
        dbname="victorbassey", 
        user="victorbassey", 
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()


    for item in clean_database_ready_list:
        insert_query = """
            INSERT INTO market_pricing (display_title, normalized_title, price)
            VALUES (%s, %s, %s);
        """
        

        record_to_insert = (
            item["display_title"],
            item["normalized_title"],
            item["price"] 
        )
        

        cursor.execute(insert_query, record_to_insert)


    conn.commit()
    print(f"Successfully saved {len(clean_database_ready_list)} records to SQL!")

except Exception as e:
    print(f"Database Error: {e}")

finally:

    if conn:
        cursor.close()
        conn.close()
        print("PostgreSQL connection closed.")