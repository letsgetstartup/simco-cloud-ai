import os
import requests
import pandas as pd
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
IFRASTRUCTURE_SEARCH_QUERIES = [
    "desalination plant Israel",
    "water treatment plant Israel",
    "wastewater treatment plant Israel",
    "Mekorot facility Israel",
    "water reservoir Israel",
    "pumping station water Israel",
    "Israel Water Authority office"
]

def collect_water_infrastructure_data_new(api_key, queries):
    """
    Collects data about water infrastructure in Israel using the NEW Google Places API.
    Ref: https://developers.google.com/maps/documentation/places/web-service/text-search
    """
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY not found in .env file.")
        return None

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.id,places.types,places.rating,places.userRatingCount"
    }

    all_results = []

    for query in queries:
        print(f"Searching for: {query}...")
        data = {
            "textQuery": query,
            "locationBias": {
                "circle": {
                    "center": {"latitude": 31.0461, "longitude": 34.8516}, # Center of Israel
                    "radius": 200000.0 # 200km radius covers Israel
                }
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code != 200:
                print(f"Error from API for '{query}': {response.status_code} - {response.text}")
                continue
            
            results = response.json().get('places', [])
            for place in results:
                details = {
                    'name': place.get('displayName', {}).get('text'),
                    'address': place.get('formattedAddress'),
                    'lat': place.get('location', {}).get('latitude'),
                    'lng': place.get('location', {}).get('longitude'),
                    'place_id': place.get('id'),
                    'types': ", ".join(place.get('types', [])),
                    'rating': place.get('rating'),
                    'user_ratings_total': place.get('userRatingCount'),
                    'query_used': query
                }
                all_results.append(details)
            
            # Note: Pagination in the NEW API uses 'nextPageToken' in the response body
            # and 'routingParameters.routingMode' etc is not needed for simple text search.
            # For simplicity, we'll stick to the first page per query which usually gives enough results.
            
            time.sleep(1) # Be polite

        except Exception as e:
            print(f"Error searching for '{query}': {e}")

    # Remove duplicates based on place_id
    if not all_results:
        return None
        
    df = pd.DataFrame(all_results)
    df = df.drop_duplicates(subset=['place_id'])
    return df

def main():
    print("Starting Water Infrastructure Data Collection (using New Places API)...")
    df = collect_water_infrastructure_data_new(API_KEY, IFRASTRUCTURE_SEARCH_QUERIES)

    if df is not None and not df.empty:
        output_file = "israel_water_infrastructure.csv"
        df.to_csv(output_file, index=False)
        print(f"Successfully collected {len(df)} locations.")
        print(f"Data saved to {output_file}")
    else:
        print("No data collected or error occurred.")

if __name__ == "__main__":
    main()
