# Copyright 2026 Google LLC
# Seed script for Firestore collection 'destinations'

from google.cloud import firestore

# CRITICAL: Hardcode the project ID string so it matches both locally and on Agent Platform
FIRESTORE_PROJECT = "qwiklabs-gcp-03-63362b398b68"

DESTINATIONS = [
    {
        "id": "dest-001",
        "name": "Arashiyama Bamboo Grove",
        "city": "Kyoto",
        "country": "Japan",
        "category": "Nature & Culture",
        "description": "A serene natural forest of tall bamboo stalks in western Kyoto, known for scenic walking paths and peaceful atmosphere.",
        "best_time_of_day": "Early Morning",
        "estimated_cost_usd": 0.0,
        "rating": 4.8,
        "tags": ["nature", "bamboo", "kyoto", "scenic", "walking"],
    },
    {
        "id": "dest-002",
        "name": "Montmartre & Sacré-Cœur Basilica",
        "city": "Paris",
        "country": "France",
        "category": "Culture & Art",
        "description": "Historic hilltop neighborhood in Paris famous for artistic heritage, cobblestone streets, and panoramic city views from Sacré-Cœur.",
        "best_time_of_day": "Sunset",
        "estimated_cost_usd": 15.0,
        "rating": 4.7,
        "tags": ["art", "architecture", "views", "paris", "romantic"],
    },
    {
        "id": "dest-003",
        "name": "Oia Sunset Viewpoint",
        "city": "Santorini",
        "country": "Greece",
        "category": "Scenic View",
        "description": "Iconic cliffside village known for whitewashed houses, blue-domed churches, and world-famous Aegean Sea sunsets.",
        "best_time_of_day": "Sunset",
        "estimated_cost_usd": 25.0,
        "rating": 4.9,
        "tags": ["sunset", "greece", "island", "views", "scenic"],
    },
    {
        "id": "dest-004",
        "name": "Fushimi Inari Shrine",
        "city": "Kyoto",
        "country": "Japan",
        "category": "History & Religion",
        "description": "Famous Shinto shrine in southern Kyoto dedicated to Inari, featuring thousands of vermilion torii gates winding up Mount Inari.",
        "best_time_of_day": "Morning",
        "estimated_cost_usd": 0.0,
        "rating": 4.9,
        "tags": ["shrine", "history", "torii", "kyoto", "hiking"],
    },
    {
        "id": "dest-005",
        "name": "Louvre Museum",
        "city": "Paris",
        "country": "France",
        "category": "Museum & Art",
        "description": "The world's largest art museum and historic monument in Paris, housing masterpiece artworks like the Mona Lisa and Venus de Milo.",
        "best_time_of_day": "Morning",
        "estimated_cost_usd": 22.0,
        "rating": 4.8,
        "tags": ["museum", "art", "mona lisa", "paris", "culture"],
    },
]


def seed_database():
    print(f"Connecting to Firestore in project: {FIRESTORE_PROJECT}")
    db = firestore.Client(project=FIRESTORE_PROJECT)
    collection_ref = db.collection("destinations")

    for dest in DESTINATIONS:
        doc_ref = collection_ref.document(dest["id"])
        doc_ref.set(dest)
        print(f"Seeded document: {dest['id']} -> {dest['name']}")

    print("Firestore seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
