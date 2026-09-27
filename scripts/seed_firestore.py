#!/usr/bin/env python3
"""
Seed script for Firestore backend for Soirée Event Architect.
Project ID is explicitly hardcoded as required for Agent Platform deployment safety.
"""

from google.cloud import firestore

# CRITICAL: Hardcoded GCP Project ID string
PROJECT_ID = "qwiklabs-gcp-02-5a2a6d61edf4"


def seed_database():
    print(f"Connecting to Firestore with hardcoded project_id: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)

    # 1. Seed Events Collection
    events_ref = db.collection("events")

    events_data = {
        "berry-soiree-2026": {
            "event_id": "berry-soiree-2026",
            "name": "Berry Patch Soirée",
            "theme": "Berries",
            "host": "Aria",
            "guest_count": 12,
            "dietary_restrictions": ["Gluten-Free", "Vegan-Friendly", "Nut-Free"],
            "dress_code": "Raspberry Pink, Deep Burgundy, and Sage Green",
            "budget_total": 1200.00,
            "status": "Planning",
            "cake_selection": "Wildberry Chantilly Cake (Gluten-Free)",
            "games": ["Berry Blind Taste Test", "Berry Mixology Challenge"],
            "signature_drink": "Blackberry Mint Sparkler",
            "rsvps": [
                {"name": "Aria", "status": "Attending", "dietary": "Gluten-Free"},
                {"name": "Leo", "status": "Attending", "dietary": "None"},
                {"name": "Maya", "status": "Attending", "dietary": "Nut-Free"},
            ],
        },
        "masquerade-gala-2026": {
            "event_id": "masquerade-gala-2026",
            "name": "Vintage Masquerade Gala",
            "theme": "Vintage Masquerade",
            "host": "Julian",
            "guest_count": 25,
            "dietary_restrictions": ["Vegetarian"],
            "dress_code": "Black Tie & Velvet Masks",
            "budget_total": 3500.00,
            "status": "Confirmed",
            "cake_selection": "Dark Chocolate Espresso Tower",
            "games": ["Mystery Mask Pairing", "Masquerade Ballroom Bingo"],
            "signature_drink": "Midnight Smoked Old Fashioned",
            "rsvps": [
                {"name": "Julian", "status": "Attending", "dietary": "None"},
                {"name": "Chloe", "status": "Attending", "dietary": "Vegetarian"},
            ],
        },
    }

    for event_id, data in events_data.items():
        events_ref.document(event_id).set(data)
        print(f"  ✓ Seeded event: {event_id} ({data['name']})")

    # 2. Seed Theme Catalog Collection
    catalog_ref = db.collection("theme_catalog")

    catalog_data = {
        "berries": {
            "theme_id": "berries",
            "theme_name": "Berries & Wildflowers",
            "recommended_cakes": [
                "Wildberry Chantilly Cake (Gluten-Free)",
                "Triple Berry Lemon Tart",
            ],
            "decor_elements": [
                "Wild berry vine centerpieces",
                "Deep-red velvet runners",
                "Berry-scented candles",
            ],
            "dress_code_palette": "Raspberry Pink, Deep Burgundy, and Sage Green",
            "recommended_games": [
                "Berry Blind Taste Test",
                "Berry Cocktail Mixology Challenge",
            ],
            "signature_drinks": [
                "Blackberry Mint Sparkler (Mocktail)",
                "Bramble Cocktail",
            ],
        },
        "masquerade": {
            "theme_id": "masquerade",
            "theme_name": "Vintage Masquerade",
            "recommended_cakes": [
                "Dark Chocolate Espresso Tower",
                "Golden Velvet Layer Cake",
            ],
            "decor_elements": [
                "Candelabras with dripping wax",
                "Black velvet drapes",
                "Antique golden masks",
            ],
            "dress_code_palette": "Black Tie, Gold, Midnight Blue, and Velvet Masks",
            "recommended_games": [
                "Mystery Mask Pairing",
                "Masquerade Ballroom Bingo",
            ],
            "signature_drinks": [
                "Midnight Smoked Old Fashioned",
                "Golden Champagne Sparkler",
            ],
        },
    }

    for theme_id, data in catalog_data.items():
        catalog_ref.document(theme_id).set(data)
        print(f"  ✓ Seeded catalog theme: {theme_id} ({data['theme_name']})")

    print("\n✅ Firestore seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
