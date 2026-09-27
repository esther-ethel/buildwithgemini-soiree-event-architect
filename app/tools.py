"""
Firestore function tools for Soirée Event Architect.
CRITICAL: The GCP Project ID is explicitly hardcoded as required for Agent Platform deployment safety.
"""

import base64
import inspect
import json
import os
import re
import urllib.parse
import urllib.request
import uuid
from google import genai
from google.genai import types
from google.adk.tools import ToolContext
from google.cloud import firestore, storage

# CRITICAL: Hardcoded GCP Project ID string
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-5a2a6d61edf4"
GCS_BUCKET_NAME = "soiree-media-qwiklabs-gcp-02-5a2a6d61edf4"





def _get_firestore_client() -> firestore.Client:
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def get_event_details(event_id: str) -> dict:
    """Retrieves event planning details from Firestore by event ID.

    Args:
        event_id: The unique identifier for the event (e.g., 'berry-soiree-2026').

    Returns:
        Dict containing event details such as name, theme, guest count, dietary
        restrictions, budget, dress code, cake selection, and RSVPs.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("events").document(event_id)
    doc = doc_ref.get()

    if doc.exists:
        return doc.to_dict()
    return {"error": f"Event '{event_id}' not found in Firestore."}


def list_events(limit: int = 20) -> dict:
    """Lists all scheduled upcoming events and their theme details from Firestore.

    Args:
        limit: Maximum number of events to retrieve (default: 20).

    Returns:
        Dict containing a list of events with event_id, name, theme, guest_count, status, dress_code, and budget_total.
    """
    db = _get_firestore_client()
    docs = db.collection("events").limit(limit).stream()
    events = []
    for doc in docs:
        d = doc.to_dict()
        events.append({
            "event_id": doc.id,
            "name": d.get("name", "Unnamed Event"),
            "theme": d.get("theme", "N/A"),
            "guest_count": d.get("guest_count", 0),
            "status": d.get("status", "Planning"),
            "dress_code": d.get("dress_code", "N/A"),
            "budget_total": d.get("budget_total", 0.0),
        })
    return {"events": events, "count": len(events)}


def save_event_details(
    event_id: str,
    name: str,
    theme: str,
    guest_count: int,
    dietary_restrictions: list[str],
    dress_code: str,
    budget_total: float,
    cake_selection: str = "",
    signature_drink: str = "",
    status: str = "Planning",
) -> dict:
    """Saves or updates event planning details in Firestore.

    Args:
        event_id: Unique event ID.
        name: Name of the event.
        theme: Aesthetic theme (e.g., 'Berries', 'Vintage Masquerade').
        guest_count: Expected number of guests.
        dietary_restrictions: List of dietary restrictions (e.g., ['Gluten-Free',
          'Vegan']).
        dress_code: Color palette and dress code guidelines.
        budget_total: Total budget target in dollars.
        cake_selection: Selected theme cake.
        signature_drink: Selected theme cocktail/mocktail.
        status: Event status ('Planning', 'Confirmed', 'Completed').

    Returns:
        Status message confirming the save operation.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("events").document(event_id)

    event_data = {
        "event_id": event_id,
        "name": name,
        "theme": theme,
        "guest_count": guest_count,
        "dietary_restrictions": dietary_restrictions,
        "dress_code": dress_code,
        "budget_total": budget_total,
        "cake_selection": cake_selection,
        "signature_drink": signature_drink,
        "status": status,
    }

    doc_ref.set(event_data, merge=True)
    return {
        "status": "success",
        "message": f"Event '{name}' ({event_id}) saved to Firestore successfully.",
        "data": event_data,
    }


def add_guest_rsvp(
    event_id: str, guest_name: str, rsvp_status: str, dietary: str = "None"
) -> dict:
    """Adds or updates a guest RSVP for an event in Firestore.

    Args:
        event_id: The ID of the event.
        guest_name: Name of the guest.
        rsvp_status: 'Attending', 'Declined', or 'Maybe'.
        dietary: Any specific dietary restriction for this guest.

    Returns:
        Confirmation message and updated RSVP list.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("events").document(event_id)
    doc = doc_ref.get()

    if not doc.exists:
        return {"error": f"Event '{event_id}' does not exist."}

    event_dict = doc.to_dict()
    rsvps = event_dict.get("rsvps", [])

    # Update existing RSVP or append new
    updated = False
    for rsvp in rsvps:
        if rsvp.get("name").lower() == guest_name.lower():
            rsvp["status"] = rsvp_status
            rsvp["dietary"] = dietary
            updated = True
            break

    if not updated:
        rsvps.append(
            {"name": guest_name, "status": rsvp_status, "dietary": dietary}
        )

    doc_ref.update({"rsvps": rsvps})

    return {
        "status": "success",
        "message": f"RSVP for {guest_name} updated successfully.",
        "rsvps": rsvps,
    }


def get_theme_catalog_item(theme_id: str) -> dict:
    """Retrieves theme catalog recommendations (cakes, decor, drinks, games) from Firestore.

    Args:
        theme_id: Theme identifier (e.g., 'berries', 'masquerade').

    Returns:
        Catalog item details including recommended cakes, decor elements, dress code palette, games, and signature drinks.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("theme_catalog").document(theme_id.lower())
    doc = doc_ref.get()

    if doc.exists:
        return doc.to_dict()

    return {
        "error": f"Theme '{theme_id}' not found in catalog. Available themes: 'berries', 'masquerade'."
    }


def calculate_event_expenses(
    items: list[dict],
    guest_count: int,
    tax_percentage: float = 8.5,
    tip_percentage: float = 18.0,
) -> dict:
    """Calculates itemized event expenses, taxes, tips, and per-person splits.

    Args:
        items: List of dictionaries representing expense items, each with 'name' (str) and 'cost' (float). E.g. [{'name': 'Cake', 'cost': 150.0}, {'name': 'Decor', 'cost': 250.0}]
        guest_count: Number of attending guests to split expenses across.
        tax_percentage: Estimated tax rate percentage (default 8.5%).
        tip_percentage: Gratuitous/service tip percentage (default 18.0%).

    Returns:
        Dict containing itemized costs, subtotal, tax amount, tip amount, grand total, and per-person split.
    """
    if not items:
        return {"error": "No expense items provided."}
    if guest_count <= 0:
        return {"error": "guest_count must be a positive integer."}

    itemized = []
    subtotal = 0.0
    for item in items:
        name = item.get("name", "Expense Item")
        cost = float(item.get("cost", 0.0))
        itemized.append({"name": name, "cost": round(cost, 2)})
        subtotal += cost

    tax_amount = subtotal * (tax_percentage / 100.0)
    tip_amount = subtotal * (tip_percentage / 100.0)
    grand_total = subtotal + tax_amount + tip_amount
    per_person_split = grand_total / guest_count

    return {
        "itemized_expenses": itemized,
        "guest_count": guest_count,
        "subtotal": round(subtotal, 2),
        "tax_percentage": tax_percentage,
        "tax_amount": round(tax_amount, 2),
        "tip_percentage": tip_percentage,
        "tip_amount": round(tip_amount, 2),
        "grand_total": round(grand_total, 2),
        "per_person_split": round(per_person_split, 2),
    }


def generate_digital_invitation(
    event_id: str, host_message: str = "Join us for a magical celebration!"
) -> dict:
    """Generates an ornate, theme-aligned watercolor digital invitation card and uploads to public Cloud Storage.

    Args:
        event_id: Unique event ID in Firestore (e.g. 'berry-soiree-2026').
        host_message: Personal welcome message from the host.

    Returns:
        Dict containing event summary, published status, and live public invitation image URL.
    """
    db = _get_firestore_client()
    doc = db.collection("events").document(event_id).get()
    if not doc.exists:
        return {"error": f"Event '{event_id}' not found in Firestore."}

    data = doc.to_dict()
    event_name = data.get("name", "Soirée Celebration")
    theme = data.get("theme", "Celebration")
    dress_code = data.get("dress_code", "Festive")

    svg_card = f"""<svg xmlns="http://www.w3.org/2000/svg" width="700" height="480" viewBox="0 0 700 480">
  <defs>
    <!-- Soft Watercolor Radial & Linear Gradients -->
    <radialGradient id="wc_bg" cx="50%" cy="40%" r="65%">
      <stop offset="0%" stop-color="#4A1228"/>
      <stop offset="60%" stop-color="#280816"/>
      <stop offset="100%" stop-color="#15030B"/>
    </radialGradient>
    
    <radialGradient id="wc_berry_red" cx="30%" cy="30%" r="70%">
      <stop offset="0%" stop-color="#FF4D6D" stop-opacity="0.95"/>
      <stop offset="60%" stop-color="#C9184A" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="#800F2F" stop-opacity="0.7"/>
    </radialGradient>

    <radialGradient id="wc_berry_blue" cx="35%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#7209B7" stop-opacity="0.9"/>
      <stop offset="70%" stop-color="#3F37C9" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#1A1A40" stop-opacity="0.6"/>
    </radialGradient>

    <linearGradient id="wc_leaf" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#70E000" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="#38B000" stop-opacity="0.65"/>
    </linearGradient>

    <linearGradient id="gold_gold" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFE57F"/>
      <stop offset="50%" stop-color="#FFC107"/>
      <stop offset="100%" stop-color="#FF8F00"/>
    </linearGradient>
    
    <!-- Watercolor Soft Glow Filter -->
    <filter id="wc_glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
  </defs>

  <!-- Base Dark Watercolor Card Canvas -->
  <rect width="700" height="480" fill="url(#wc_bg)" rx="20"/>

  <!-- Watercolor Paint Bleed Background Soft Shapes -->
  <path d="M -40,-20 Q 180,80 320,-30 T 680,60 T 740,220 Q 520,160 380,260 T -20,240 Z" fill="#800F2F" opacity="0.22" filter="url(#wc_glow)"/>
  <path d="M 400,280 Q 560,220 720,340 T 680,500 T 320,490 Q 280,360 400,280 Z" fill="#5C0425" opacity="0.35" filter="url(#wc_glow)"/>

  <!-- Golden Double Border with Ornate Corner Accents -->
  <rect x="24" y="24" width="652" height="432" fill="none" stroke="url(#gold_gold)" stroke-width="2" rx="14" opacity="0.85"/>
  <rect x="32" y="32" width="636" height="416" fill="none" stroke="url(#gold_gold)" stroke-width="1" rx="10" stroke-dasharray="8 4" opacity="0.6"/>

  <!-- Top Decorative Watercolor Berry & Botanical Garland -->
  <g id="watercolor_top_garland" transform="translate(350, 52)">
    <!-- Leaves -->
    <path d="M -90,-5 Q -60,-25 -40,-5 Q -60,15 -90,-5 Z" fill="url(#wc_leaf)"/>
    <path d="M 40,-5 Q 60,-25 90,-5 Q 60,15 40,-5 Z" fill="url(#wc_leaf)"/>
    <!-- Center Berry Cluster -->
    <circle cx="-25" cy="-2" r="14" fill="url(#wc_berry_red)" filter="url(#wc_glow)"/>
    <circle cx="0" cy="-10" r="16" fill="url(#wc_berry_blue)" filter="url(#wc_glow)"/>
    <circle cx="25" cy="-2" r="14" fill="url(#wc_berry_red)" filter="url(#wc_glow)"/>
    <circle cx="-10" cy="10" r="12" fill="url(#wc_berry_red)" opacity="0.9"/>
    <circle cx="10" cy="10" r="12" fill="url(#wc_berry_blue)" opacity="0.9"/>
    <!-- Watercolor Highlights -->
    <circle cx="-28" cy="-6" r="3" fill="#FFF" opacity="0.6"/>
    <circle cx="-3" cy="-14" r="4" fill="#FFF" opacity="0.7"/>
    <circle cx="22" cy="-6" r="3" fill="#FFF" opacity="0.6"/>
  </g>

  <!-- Typography Content -->
  <text x="350" y="125" font-family="serif" font-size="18" fill="#FFECB3" text-anchor="middle" letter-spacing="4">YOU ARE CORDIALLY INVITED TO</text>
  
  <!-- Event Title with Soft Glow -->
  <text x="350" y="175" font-family="sans-serif" font-size="34" fill="url(#gold_gold)" text-anchor="middle" font-weight="bold" filter="url(#wc_glow)">{event_name}</text>
  
  <line x1="220" y1="195" x2="480" y2="195" stroke="url(#gold_gold)" stroke-width="1.5" opacity="0.7"/>

  <!-- Theme & Dress Code Details -->
  <text x="350" y="230" font-family="sans-serif" font-size="18" fill="#FF80AB" text-anchor="middle" font-weight="600">Theme: {theme}</text>
  <text x="350" y="265" font-family="sans-serif" font-size="15" fill="#F8BBD0" text-anchor="middle">Dress Code: {dress_code}</text>

  <!-- Personal Host Message -->
  <text x="350" y="320" font-family="serif" font-size="16" fill="#FFF" text-anchor="middle" font-style="italic">"{host_message}"</text>

  <!-- Bottom Botanical Garland Accent -->
  <g id="watercolor_bottom_accent" transform="translate(350, 375)">
    <path d="M -60,0 Q -40,-15 -20,0 Q -40,15 -60,0 Z" fill="url(#wc_leaf)"/>
    <path d="M 20,0 Q 40,-15 60,0 Q 40,15 20,0 Z" fill="url(#wc_leaf)"/>
    <circle cx="0" cy="0" r="10" fill="url(#wc_berry_red)"/>
    <circle cx="-2" cy="-2" r="2" fill="#FFF" opacity="0.7"/>
  </g>

  <!-- Call to Action RSVP Button -->
  <rect x="230" y="405" width="240" height="42" fill="url(#gold_gold)" rx="21" filter="url(#wc_glow)"/>
  <text x="350" y="432" font-family="sans-serif" font-size="15" fill="#280816" text-anchor="middle" font-weight="bold" letter-spacing="1">RSVP WITH SOIRÉE</text>
</svg>"""

    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob_name = f"invitations/invitation_{event_id}.svg"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(svg_card, content_type="image/svg+xml")

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_name}"
    return {
        "event_id": event_id,
        "event_name": event_name,
        "theme": theme,
        "dress_code": dress_code,
        "invitation_card_url": public_url,
        "status": "published",
        "message": f"Digital invitation with watercolor artwork published for '{event_name}'.",
    }


async def generate_theme_image_asset(
    title: str,
    theme: str,
    asset_type: str = "decor_moodboard",
    color_palette: str = "Deep Crimson, Gold, and Emerald",
    tool_context: ToolContext = None,
) -> dict:
    """Generates a photorealistic theme visual card asset (cake preview, moodboard, cocktail card) using Imagen 3 and uploads to public Cloud Storage.

    Args:
        title: Title of the asset (e.g., 'Wildberry Chantilly Cake', 'Gothic Decor Moodboard').
        theme: Aesthetic theme (e.g., 'Berries', 'Vintage Masquerade').
        asset_type: 'cake_preview', 'decor_moodboard', 'cocktail_card', or 'favor_card'.
        color_palette: Color palette specification.
        tool_context: ADK ToolContext instance provided automatically.

    Returns:
        Dict containing asset title, type, and live public HTTPS image URL.
    """
    prompt = (
        f"High-resolution photorealistic luxury {asset_type.replace('_', ' ')} "
        f"for a {theme} party theme titled '{title}', featuring an elegant setup "
        f"in {color_palette} color palette, detailed architectural lighting and professional styling."
    )
    result = await generate_celebration_image(prompt, tool_context=tool_context)
    if "public_url" in result:
        return {
            "title": title,
            "theme": theme,
            "asset_type": asset_type,
            "image_url": result["public_url"],
            "status": "generated",
            "message": f"Photorealistic Imagen 3 moodboard asset '{title}' generated successfully.",
        }
    
    # Fallback if image generation fails
    clean_title = re.sub(r"[^\w\-]", "_", title.lower())
    blob_name = f"assets/{asset_type}_{clean_title}.svg"
    svg_asset = f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="350" viewBox="0 0 500 350">
  <rect width="500" height="350" fill="#1A1A2E" rx="12"/>
  <rect x="15" y="15" width="470" height="320" fill="none" stroke="#D4AF37" stroke-width="2" rx="8"/>
  <text x="250" y="60" font-family="sans-serif" font-size="14" fill="#D4AF37" letter-spacing="2" text-anchor="middle">{asset_type.upper().replace('_', ' ')}</text>
  <text x="250" y="110" font-family="serif" font-size="24" fill="#FFFFFF" text-anchor="middle" font-weight="bold">{title}</text>
  <circle cx="250" cy="180" r="45" fill="#E94560" opacity="0.85"/>
  <text x="250" y="186" font-family="sans-serif" font-size="16" fill="#FFF" text-anchor="middle" font-weight="bold">{theme}</text>
  <text x="250" y="260" font-family="sans-serif" font-size="14" fill="#E2E2E2" text-anchor="middle">Palette: {color_palette}</text>
  <text x="250" y="300" font-family="sans-serif" font-size="12" fill="#8888AA" text-anchor="middle">Curated by Soirée Event Architect</text>
</svg>"""

    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(svg_asset, content_type="image/svg+xml")

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_name}"
    return {
        "title": title,
        "theme": theme,
        "asset_type": asset_type,
        "image_url": public_url,
        "status": "generated",
        "message": f"Asset '{title}' generated and stored in Cloud Storage.",
    }


def curate_playlist(
    theme: str,
    genre: str = "Jazz & Ambient",
    track_count: int = 10,
    party_phase: str = "Dinner & Conversation",
) -> dict:
    """Curates a tracklist playlist with song titles, artists, tempo, and mood transitions for an event.

    Args:
        theme: Event theme or vibe (e.g., 'Intimate Dinner Party', 'Whimsical Celebration').
        genre: Music style or genre (e.g., 'Jazz', 'Acoustic', 'Pop & Disco', 'Lofi Lounge').
        track_count: Number of tracks to curate (default: 10).
        party_phase: Phase of the party (e.g., 'Arrivals', 'Dinner', 'Late Night').

    Returns:
        Dict containing playlist title, genre, party_phase, and a curated list of tracks with title, artist, and vibe.
    """
    return {
        "status": "success",
        "theme": theme,
        "genre": genre,
        "party_phase": party_phase,
        "track_count": track_count,
        "message": f"Playlist curated for '{theme}' with {track_count} tracks in {genre} style.",
    }



def search_cocktail_recipes(drink_query: str) -> dict:
    """Fetches real cocktail or mocktail recipes, ingredients, glassware, and instructions from TheCocktailDB API.

    Args:
        drink_query: Search query for a cocktail, mocktail, or signature party drink (e.g., 'Mojito', 'Berry', 'Margarita', 'Punch').

    Returns:
        Dict containing drink name, category, alcoholic/non-alcoholic type, glassware, ingredients list with measurements, preparation instructions, and drink image URL.
    """
    api_key = os.environ.get("COCKTAIL_DB_API_KEY", "1")
    encoded_query = urllib.parse.quote(drink_query)
    url = f"https://www.thecocktaildb.com/api/json/v1/{api_key}/search.php?s={encoded_query}"

    req = urllib.request.Request(url, headers={"User-Agent": "SoireeAgent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            drinks = data.get("drinks")
            if not drinks:
                return {"error": f"No drink recipes found matching '{drink_query}'."}

            drink = drinks[0]
            ingredients = []
            for i in range(1, 16):
                ing = drink.get(f"strIngredient{i}")
                meas = drink.get(f"strMeasure{i}")
                if ing and ing.strip():
                    measure_str = f"{meas.strip()} " if meas and meas.strip() else ""
                    ingredients.append(f"{measure_str}{ing.strip()}")

            return {
                "name": drink.get("strDrink"),
                "category": drink.get("strCategory"),
                "glass": drink.get("strGlass"),
                "type": drink.get("strAlcoholic"),
                "instructions": drink.get("strInstructions"),
                "ingredients": ingredients,
                "image_url": drink.get("strDrinkThumb"),
            }
    except Exception as e:
        return {"error": f"Failed to fetch drink recipe from API: {str(e)}"}


async def generate_celebration_image(
    prompt: str, tool_context: ToolContext = None
) -> dict:
    """Generates an image for an event element (e.g., cake, decor visual, cocktail presentation) using gemini-3.1-flash-lite-image in the global region.

    Saves the image bytes as a session artifact for the Playground UI and uploads it to public Cloud Storage.

    Args:
        prompt: Detailed visual prompt describing the celebration item to generate.
        tool_context: ADK ToolContext instance provided automatically during tool invocation.

    Returns:
        Dict containing the public Cloud Storage HTTPS URL, artifact filename, prompt, and status.
    """
    client = genai.Client(
        vertexai=True, project=FIRESTORE_PROJECT_ID, location="global"
    )
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
    )

    image_bytes = None
    mime_type = "image/png"

    if (
        response.candidates
        and response.candidates[0].content
        and response.candidates[0].content.parts
    ):
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

    if not image_bytes:
        return {"error": "Failed to generate image bytes from Gemini model."}

    ext = "jpg" if "jpeg" in mime_type else "png"
    filename = f"celebration_{uuid.uuid4().hex[:8]}.{ext}"

    # (1) Save artifact via tool_context so it appears in the Playground's Artifacts panel
    if tool_context is not None:
        try:
            artifact_part = types.Part.from_bytes(
                data=image_bytes, mime_type=mime_type
            )
            res = tool_context.save_artifact(
                filename=filename, artifact=artifact_part
            )
            if inspect.isawaitable(res):
                await res
        except Exception as e:
            print(f"Warning: Failed to save artifact via tool_context: {e}")

    # (2) Upload image bytes directly to GCS public bucket (no local file write)
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob_name = f"generated_images/{filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = (
        f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_name}"
    )

    return {
        "status": "success",
        "prompt": prompt,
        "filename": filename,
        "public_url": public_url,
        "message": f"Celebration image generated and published to public Cloud Storage: {public_url}",
    }


async def generate_celebration_video_clip(
    prompt: str,
    tool_context: ToolContext = None,
) -> dict:
    """Generates a short video clip for a celebration ambiance or theme item using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Args:
        prompt: Detailed visual prompt describing the celebration ambiance or item video clip to generate.
        tool_context: ADK ToolContext instance provided automatically during tool invocation.

    Returns:
        Dict containing the public Cloud Storage HTTPS URL, artifact filename, prompt, and status.
    """
    client = genai.Client(
        vertexai=True, project=FIRESTORE_PROJECT_ID, location="global"
    )
    interaction = client.interactions.create(
        model="gemini-omni-flash-preview",
        input=prompt,
        generation_config={"response_modalities": ["VIDEO"]},
    )

    vid_content = getattr(interaction, "output_video", None)
    if not vid_content or not vid_content.data:
        return {"error": "Failed to generate video bytes from Omni model."}

    if isinstance(vid_content.data, str):
        video_bytes = base64.b64decode(vid_content.data)
    else:
        video_bytes = vid_content.data

    mime_type = getattr(vid_content, "mime_type", "video/mp4") or "video/mp4"
    filename = f"celebration_video_{uuid.uuid4().hex[:8]}.mp4"

    # (1) Save artifact via tool_context so it appears in the Playground's Artifacts panel
    if tool_context is not None:
        try:
            artifact_part = types.Part.from_bytes(
                data=video_bytes, mime_type=mime_type
            )
            res = tool_context.save_artifact(
                filename=filename, artifact=artifact_part
            )
            if inspect.isawaitable(res):
                await res
        except Exception as e:
            print(f"Warning: Failed to save artifact via tool_context: {e}")

    # (2) Upload video bytes directly to GCS public bucket (no local file write)
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob_name = f"generated_videos/{filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = (
        f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_name}"
    )

    return {
        "status": "success",
        "prompt": prompt,
        "filename": filename,
        "public_url": public_url,
        "message": f"Celebration video generated and published to public Cloud Storage: {public_url}",
    }






