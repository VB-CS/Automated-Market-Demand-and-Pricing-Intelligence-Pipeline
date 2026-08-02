import os
import sys
from dotenv import load_dotenv
import psycopg2
from serpapi import GoogleSearch


load_dotenv()

API_KEY = os.getenv("API_KEY") or os.getenv("SERPAPI_API_KEY")


DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")


TARGET_BASKET = [
    "G.Skill Trident Z5 RGB DDR5 32GB 6000MHz",
    "Crucial Pro DDR5 32GB 6000MHz",
    "G.Skill Trident Z5 DDR5 64GB 6400MHz"
]

MIN_PRICE_FLOOR = 70.00

clean_database_ready_list = []
seen_listings = set()

print("--------------------------------------------------")
print("Initializing Price Gathering Pipeline from SerpApi")
print("--------------------------------------------------")

for product_name in TARGET_BASKET:
    print(f"Requesting SerpApi Shopping Results for: {product_name}...")
    
    params = {
        "engine": "google_shopping",
        "q": product_name,
        "location": "Austin, Texas, United States",
        "api_key": API_KEY
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception as e:
        print(f"SerpApi Connection Error for {product_name}: {e}")
        continue

    if "shopping_results" in results:
        for item in results["shopping_results"]:
            title = item.get("title")
            price_raw = item.get("price")
            
            # Guard Clause 1: Bypass missing values
            if title is None or price_raw is None:
                continue
                
            # Parse price string to clean float (e.g. "$149.99" -> 149.99)
            try:
                price_clean = float(price_raw.replace("$", "").replace(",", "").strip())
            except ValueError:
                # Skip items with unparseable price formats
                continue
                
            # Guard Clause 2: Safety Floor Constraint
            # This completely eliminates accessories or outlier noise (e.g. $46.00)
            if price_clean < MIN_PRICE_FLOOR:
                continue

# Normalized title for cleaner tracking & partition groupings
            normalized_title = product_name.lower().strip()

# Guard Clause 3: In-Memory Deduplication (Title + Price Tuple)
# MUST use normalized_title here so subtle raw string differences don't bypass deduplication
            listing_fingerprint = (normalized_title, price_clean)

            if listing_fingerprint in seen_listings:
                continue

            seen_listings.add(listing_fingerprint)
            clean_database_ready_list.append((title, normalized_title, price_clean))

print("\n--------------------------------------------------")
print(f"Total Filtered & Cleaned Items: {len(clean_database_ready_list)}")
print("--------------------------------------------------")

if not clean_database_ready_list:
    print("No clean records to write. Database transaction skipped.")
    sys.exit(0)

conn = None
cursor = None

try:
    print("Connecting to local PostgreSQL database...")
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()
    
    # Secure, parameterized batch insert
    insert_query = """
        INSERT INTO market_pricing (display_title, normalized_title, price)
        VALUES (%s, %s, %s);
    """
    
    print(f"Inserting {len(clean_database_ready_list)} rows securely into 'market_pricing'...")
    cursor.executemany(insert_query, clean_database_ready_list)
    
    # Commit changes permanently to database log
    conn.commit()
    print("Database Commit Successful! Data safely stored.")

except Exception as db_error:
    # Safe Rollback on error to protect database transaction consistency
    if conn:
        conn.rollback()
    print(f"CRITICAL - Database Transaction Failed: {db_error}")

finally:
    if cursor:
        cursor.close()
    if conn:
        conn.close()
        print("PostgreSQL connection pool cleanly closed.")
    print("Pipeline Execution Completed.")