# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import os
import re
import urllib.parse
import urllib.request
import uuid
from dotenv import load_dotenv

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from app.a2ui_utils import a2ui_callback

from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

load_dotenv()

# CRITICAL: Hardcode project ID and GCS bucket name as strings
FIRESTORE_PROJECT = "qwiklabs-gcp-03-63362b398b68"
GCS_BUCKET_NAME = "wanderlust-ai-media-63362b398b68"


def get_firestore_client():
    return firestore.Client(project=FIRESTORE_PROJECT)


def search_destinations(city: str = "", category: str = "") -> list[dict]:
    """Search for travel destinations in the database by city or category.

    Args:
        city: Optional city name to filter by (e.g., 'Kyoto', 'Paris', 'Santorini').
        category: Optional category to filter by (e.g., 'Nature & Culture', 'Culture & Art', 'Scenic View').

    Returns:
        List of matching destination dictionaries.
    """
    try:
        db = get_firestore_client()
        docs = db.collection("destinations").stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            matches_city = not city or city.lower() in data.get("city", "").lower()
            matches_cat = not category or category.lower() in data.get("category", "").lower()
            if matches_city and matches_cat:
                results.append(data)
        return results
    except Exception as e:
        return [{"error": f"Failed to search Firestore: {str(e)}"}]


def get_destination_details(destination_id: str) -> dict:
    """Retrieve detailed information for a specific destination by its ID.

    Args:
        destination_id: Unique ID of the destination (e.g., 'dest-001').

    Returns:
        Destination details dictionary or error message.
    """
    try:
        db = get_firestore_client()
        doc = db.collection("destinations").document(destination_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return {"error": f"Destination '{destination_id}' not found."}
    except Exception as e:
        return {"error": f"Failed to fetch destination: {str(e)}"}


def save_destination(
    destination_id: str,
    name: str,
    city: str,
    country: str,
    category: str,
    description: str,
    best_time_of_day: str = "Anytime",
    estimated_cost_usd: float = 0.0,
) -> str:
    """Save or update a travel destination in the Firestore database.

    Args:
        destination_id: Unique identifier for the destination (e.g., 'dest-006').
        name: Name of the destination spot or attraction.
        city: City where the destination is located.
        country: Country where the destination is located.
        category: Category/theme of the spot (e.g., 'Nature', 'Food & Dining').
        description: Brief description of the attraction.
        best_time_of_day: Recommended time to visit (e.g., 'Morning', 'Sunset').
        estimated_cost_usd: Estimated cost per person in USD.

    Returns:
        Confirmation message.
    """
    try:
        db = get_firestore_client()
        doc_ref = db.collection("destinations").document(destination_id)
        doc_data = {
            "name": name,
            "city": city,
            "country": country,
            "category": category,
            "description": description,
            "best_time_of_day": best_time_of_day,
            "estimated_cost_usd": estimated_cost_usd,
        }
        doc_ref.set(doc_data, merge=True)
        return f"Successfully saved destination '{name}' (ID: {destination_id}) to Firestore."
    except Exception as e:
        return f"Failed to save destination to Firestore: {str(e)}"


def calculate_itinerary_budget(
    destination_ids: list[str],
    num_days: int = 3,
    num_travelers: int = 1,
    daily_food_usd_per_person: float = 50.0,
    daily_lodging_usd_per_room: float = 120.0,
) -> dict:
    """Calculate total estimated budget for an itinerary given destination IDs, duration, and traveler count.

    Args:
        destination_ids: List of destination IDs (e.g. ['dest-001', 'dest-002']).
        num_days: Duration of trip in days (default: 3).
        num_travelers: Number of travelers (default: 1).
        daily_food_usd_per_person: Estimated daily dining cost per person in USD (default: 50.0).
        daily_lodging_usd_per_room: Estimated daily lodging cost in USD (default: 120.0).

    Returns:
        Dictionary containing itemized cost breakdown and grand total.
    """
    attraction_costs = 0.0
    try:
        db = get_firestore_client()
        for dest_id in destination_ids:
            doc = db.collection("destinations").document(dest_id).get()
            if doc.exists:
                data = doc.to_dict()
                cost = float(data.get("estimated_cost_usd", 0.0))
                attraction_costs += cost * num_travelers
            else:
                attraction_costs += 15.0 * num_travelers
    except Exception:
        attraction_costs = len(destination_ids) * 15.0 * num_travelers

    total_food = daily_food_usd_per_person * num_travelers * num_days
    rooms_needed = max(1, (num_travelers + 1) // 2)
    total_lodging = daily_lodging_usd_per_room * rooms_needed * num_days
    grand_total = attraction_costs + total_food + total_lodging

    return {
        "num_days": num_days,
        "num_travelers": num_travelers,
        "attraction_entry_total_usd": round(attraction_costs, 2),
        "total_food_usd": round(total_food, 2),
        "total_lodging_usd": round(total_lodging, 2),
        "grand_total_usd": round(grand_total, 2),
        "per_person_total_usd": round(grand_total / max(1, num_travelers), 2),
    }


def get_destination_weather(city: str) -> dict:
    """Fetch current real-time weather and climate information for a target travel city.

    Args:
        city: The name of the city to look up weather for (e.g. 'Kyoto', 'Paris', 'Santorini').

    Returns:
        Dictionary with location information, current temperature, and weather conditions.
    """
    try:
        encoded_city = urllib.parse.quote(city)
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "WanderlustAI/1.0"})
        with urllib.request.urlopen(req) as resp:
            geo_data = json.loads(resp.read().decode("utf-8"))

        results = geo_data.get("results")
        if not results:
            return {"error": f"City '{city}' not found."}

        first_match = results[0]
        lat = first_match.get("latitude")
        lon = first_match.get("longitude")
        country = first_match.get("country", "")
        timezone = first_match.get("timezone", "UTC")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "WanderlustAI/1.0"})
        with urllib.request.urlopen(req_w) as resp_w:
            w_data = json.loads(resp_w.read().decode("utf-8"))

        current = w_data.get("current_weather", {})
        temp_c = current.get("temperature", 20.0)
        temp_f = round(temp_c * 9 / 5 + 32, 1)

        return {
            "city": city,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone,
            "temperature_celsius": temp_c,
            "temperature_fahrenheit": temp_f,
            "windspeed_kmh": current.get("windspeed"),
            "is_daytime": bool(current.get("is_day", 1)),
        }
    except Exception as e:
        return {"error": f"Failed to fetch weather for '{city}': {str(e)}"}


def geocode_address(address: str) -> dict:
    """Turn an address or landmark into geographic coordinates using Google Maps Geocoding API.

    Args:
        address: Street address or landmark name (e.g. 'Kyoto Station', 'Eiffel Tower, Paris').

    Returns:
        Dictionary containing formatted address, latitude, and longitude.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY is not configured in .env"}

    try:
        encoded_address = urllib.parse.quote(address)
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if data.get("status") == "OK" and data.get("results"):
            first = data["results"][0]
            loc = first.get("geometry", {}).get("location", {})
            return {
                "address": address,
                "formatted_address": first.get("formatted_address"),
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
            }
        return {"error": f"Geocoding failed with status: {data.get('status')}"}
    except Exception as e:
        return {"error": f"Geocoding error: {str(e)}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "tourist_attraction",
    radius_meters: float = 1000.0,
) -> list[dict]:
    """Find nearby points of interest or places using Google Places API (New).

    Args:
        latitude: Latitude coordinate of the central location.
        longitude: Longitude coordinate of the central location.
        place_type: Type of place to search for (e.g. 'restaurant', 'tourist_attraction', 'museum', 'park', 'cafe').
        radius_meters: Search radius in meters (default: 1000.0).

    Returns:
        List of nearby places with name, formatted address, location, and type.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return [{"error": "GOOGLE_MAPS_API_KEY is not configured in .env"}]

    try:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        payload = {
            "includedTypes": [place_type],
            "maxResultCount": 5,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": radius_meters,
                }
            },
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.primaryType",
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))

        places = resp_data.get("places", [])
        results = []
        for p in places:
            disp_name = p.get("displayName", {}).get("text", "")
            loc = p.get("location", {})
            results.append({
                "name": disp_name,
                "address": p.get("formattedAddress"),
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
                "primary_type": p.get("primaryType"),
            })
        return results
    except Exception as e:
        return [{"error": f"Places search failed: {str(e)}"}]


async def generate_destination_artwork(
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generate visual artwork for a travel destination using gemini-3.1-flash-lite-image in the global region.
    Saves the image as a Playground artifact and uploads it to public Cloud Storage.

    Args:
        prompt: Detailed description of the travel scene to generate (e.g. 'A serene watercolor illustration of Arashiyama Bamboo Grove in Kyoto at sunrise').
        tool_context: ToolContext instance provided by ADK.

    Returns:
        The public HTTPS URL of the uploaded image.
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT, location="global")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not image_bytes:
            return "Error: Image generation model did not return image data."

        slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower().strip())[:30].strip("_") or "artwork"
        filename = f"{slug}_{uuid.uuid4().hex[:6]}.jpg"

        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        storage_client = storage.Client(project=FIRESTORE_PROJECT)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return f"Successfully generated artwork! Public URL: {public_url}"
    except Exception as e:
        return f"Error generating destination artwork: {str(e)}"


async def generate_destination_video(
    prompt: str,
    tool_context: ToolContext,
) -> str:
    """Generate a short video preview for a travel destination using gemini-omni-flash-preview in the global region.
    Saves the video as a Playground artifact and uploads it to public Cloud Storage.

    Args:
        prompt: Detailed description of the travel scene to generate as a short video (e.g. 'A aerial video clip of Santorini sunset over blue dome ocean views').
        tool_context: ToolContext instance provided by ADK.

    Returns:
        The public HTTPS URL of the uploaded video.
    """
    try:
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT, location="global")
        video_bytes = None
        mime_type = "video/mp4"

        try:
            interaction = client.interactions.create(
                model="gemini-omni-flash-preview",
                input=prompt,
                response_modalities=["video"],
            )
            if hasattr(interaction, "output_video") and interaction.output_video:
                vid = interaction.output_video
                if getattr(vid, "mime_type", None):
                    mime_type = vid.mime_type
                if getattr(vid, "data", None):
                    data_val = vid.data
                    if isinstance(data_val, str):
                        video_bytes = base64.b64decode(data_val)
                    elif isinstance(data_val, bytes):
                        video_bytes = data_val
                elif getattr(vid, "uri", None):
                    uri = vid.uri
                    if uri.startswith("gs://"):
                        b_parts = uri[5:].split("/", 1)
                        st_client = storage.Client(project=FIRESTORE_PROJECT)
                        video_bytes = st_client.bucket(b_parts[0]).blob(b_parts[1]).download_as_bytes()
                    elif uri.startswith("http"):
                        req = urllib.request.Request(uri)
                        with urllib.request.urlopen(req) as resp:
                            video_bytes = resp.read()
        except Exception:
            pass

        if not video_bytes:
            try:
                response = client.models.generate_content(
                    model="gemini-omni-flash-preview",
                    contents=prompt,
                )
                if response.candidates and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data:
                            video_bytes = part.inline_data.data
                            if part.inline_data.mime_type:
                                mime_type = part.inline_data.mime_type
                            break
            except Exception:
                pass

        if not video_bytes:
            return "Error: Video generation model did not return video data."

        slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower().strip())[:30].strip("_") or "video"
        filename = f"{slug}_{uuid.uuid4().hex[:6]}.mp4"

        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        storage_client = storage.Client(project=FIRESTORE_PROJECT)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return f"Successfully generated destination video! Public URL: {public_url}"
    except Exception as e:
        return f"Error generating destination video: {str(e)}"


# Load Agent Engine / Sandbox resource names from deployment_metadata.json if available
DEPLOYMENT_METADATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json"
)

agent_engine_resource_name = None
sandbox_resource_name = None

if os.path.exists(DEPLOYMENT_METADATA_FILE):
    try:
        with open(DEPLOYMENT_METADATA_FILE, "r") as f:
            metadata = json.load(f)
            remote_id = metadata.get("remote_agent_runtime_id")
            if remote_id and remote_id != "None":
                agent_engine_resource_name = remote_id
            sandbox_id = metadata.get("sandbox_resource_name")
            if sandbox_id and sandbox_id != "None":
                sandbox_resource_name = sandbox_id
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    sandbox_resource_name=sandbox_resource_name,
    agent_engine_resource_name=agent_engine_resource_name,
)


# WRITE: Callback to send session events to Memory Bank for extraction
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None


MEMORY_BANK_ID = "5142341116317663232"
if agent_engine_resource_name:
    MEMORY_BANK_ID = agent_engine_resource_name.split("/")[-1]


def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT,
        location="us-east4",
        agent_engine_id=MEMORY_BANK_ID,
    )


# Build A2UI 0.8 system prompt
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Wanderlust AI, a knowledgeable travel concierge. "
        "Use your tools to search destinations in Firestore, look up destination details, "
        "save new destinations, calculate estimated itinerary budgets, fetch real-time destination weather, "
        "geocode addresses into coordinates, discover nearby points of interest via Google Maps, "
        "generate custom destination artwork images, generate destination video previews, and run Python code in a sandbox for calculations or data analysis. "
        "You pay strict attention to remembering and honoring all user allergies, food sensitivities, and dietary preferences across sessions."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        search_destinations,
        get_destination_details,
        save_destination,
        calculate_itinerary_budget,
        get_destination_weather,
        geocode_address,
        find_nearby_places,
        generate_destination_artwork,
        generate_destination_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
