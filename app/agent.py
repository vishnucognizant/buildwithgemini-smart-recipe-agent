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

import datetime
import json
import os
import urllib.parse
import urllib.request
import uuid
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import (
    AgentEngineSandboxCodeExecutor,
)
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import client as genai_client, types

from .a2ui_utils import a2ui_callback

# Hardcode project ID, GCS bucket name, and Memory Bank ID as strings per instructions
PROJECT_ID = "qwiklabs-gcp-02-f082f30c93f8"
GCS_BUCKET_NAME = "smart-recipe-agent-assets-qwiklabs-gcp-02-f082f30c93f8"
MEMORY_BANK_ID = "5733449562526318592"

class CustomCodeExecutor(AgentEngineSandboxCodeExecutor):
    """Picklable wrapper for AgentEngineSandboxCodeExecutor during Agent Runtime deployment."""
    def __getstate__(self):
        state = self.__dict__.copy()
        for k in list(state.keys()):
            if k.startswith('_') or 'client' in k.lower():
                state[k] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

def get_code_executor() -> AgentEngineSandboxCodeExecutor:
    """Initializes CustomCodeExecutor using the Agent Engine resource ID from deployment_metadata.json."""
    metadata_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
    agent_engine_id = None
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                data = json.load(f)
                agent_engine_id = data.get("remote_agent_runtime_id")
        except Exception:
            pass

    if agent_engine_id:
        return CustomCodeExecutor(agent_engine_resource_name=agent_engine_id)
    return CustomCodeExecutor()


def get_memory_service() -> VertexAiMemoryBankService:
    """Configures the VertexAiMemoryBankService for cross-session long-term memory."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )

memory_service = get_memory_service()

async def ensure_memory_service_callback(callback_context: CallbackContext):
    """Ensures memory_service is attached to invocation_context if not set by runtime."""
    if callback_context._invocation_context.memory_service is None:
        callback_context._invocation_context.memory_service = memory_service
    return None

async def generate_memories_callback(callback_context: CallbackContext):
    """Sends the session events to Memory Bank for durable memory extraction after each turn."""
    try:
        if callback_context._invocation_context.memory_service is None:
            callback_context._invocation_context.memory_service = memory_service
        await callback_context.add_session_to_memory()
    except Exception as e:
        print(f"Warning: generate_memories_callback failed to add session to memory: {e}")
    return None

def get_firestore_client() -> firestore.Client:
    """Returns a Firestore client initialized with hardcoded project ID."""
    return firestore.Client(project=PROJECT_ID)

def generate_recipe_image(
    recipe_name: str,
    tool_context: ToolContext,
    visual_description: str = ""
) -> str:
    """Generate a photo of a recipe dish using gemini-3.1-flash-lite-image in the global region.
    Saves the image as a Playground artifact and uploads it to the public Cloud Storage bucket.

    Args:
        recipe_name: Name of the dish (e.g., 'Avocado Toast with Poached Egg', 'Classic Carbonara').
        tool_context: ADK ToolContext injected automatically by the runtime.
        visual_description: Optional extra details about plating, garnishes, or environment.

    Returns:
        The public HTTPS URL of the uploaded image in Cloud Storage.
    """
    prompt = f"A gourmet, high-resolution food photograph of {recipe_name}."
    if visual_description:
        prompt += f" Additional details: {visual_description}."

    client = genai_client.Client(vertexai=True, project=PROJECT_ID, location="global")
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"])
    )

    image_bytes = None
    mime_type = "image/jpeg"
    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/jpeg"
                break

    if not image_bytes:
        return "Error: Failed to generate image from model."

    object_name = f"dish_{uuid.uuid4().hex[:8]}.jpg"

    # 1. Save with tool_context.save_artifact so it shows up in Playground's Artifacts panel
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    tool_context.save_artifact(filename=object_name, artifact=artifact_part)

    # 2. Upload same image bytes directly to public GCS bucket (in-memory)
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(object_name)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    # Return public HTTPS URL
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"

def generate_recipe_video(
    recipe_name: str,
    tool_context: ToolContext,
    visual_description: str = ""
) -> str:
    """Generate a short video clip showing cooking steps or plating for a recipe dish using gemini-omni-flash-preview in the global region.
    Saves the video as a Playground artifact and uploads it to the public Cloud Storage bucket.

    Args:
        recipe_name: Name of the dish (e.g., 'Avocado Toast', 'Classic Carbonara').
        tool_context: ADK ToolContext injected automatically by the runtime.
        visual_description: Optional extra visual details for the video scene.

    Returns:
        The public HTTPS URL of the uploaded video in Cloud Storage.
    """
    prompt = f"A short video clip showing preparation or plating of {recipe_name}."
    if visual_description:
        prompt += f" Additional details: {visual_description}."

    client = genai_client.Client(vertexai=True, project=PROJECT_ID, location="global")

    video_bytes = None
    mime_type = "video/mp4"

    # Try interactions API first as documented for gemini-omni-flash-preview
    try:
        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt
        )
        if hasattr(interaction, "output_video") and interaction.output_video and getattr(interaction.output_video, "data", None):
            raw_data = interaction.output_video.data
            if isinstance(raw_data, str):
                import base64
                video_bytes = base64.b64decode(raw_data)
            elif isinstance(raw_data, bytes):
                video_bytes = raw_data
        elif hasattr(interaction, "steps"):
            for step in interaction.steps:
                content = getattr(step, "content", [])
                for item in content:
                    item_type = getattr(item, "type", None) if not isinstance(item, dict) else item.get("type")
                    if item_type == "video":
                        raw_data = getattr(item, "data", None) if not isinstance(item, dict) else item.get("data")
                        if raw_data:
                            if isinstance(raw_data, str):
                                import base64
                                video_bytes = base64.b64decode(raw_data)
                            elif isinstance(raw_data, bytes):
                                video_bytes = raw_data
                            break
    except Exception as e:
        print(f"interactions.create failed, attempting generate_content fallback: {e}")

    # Fallback to generate_content if needed
    if not video_bytes:
        try:
            response = client.models.generate_content(
                model="gemini-omni-flash-preview",
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["VIDEO"])
            )
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        video_bytes = part.inline_data.data
                        mime_type = part.inline_data.mime_type or "video/mp4"
                        break
        except Exception as e:
            print(f"generate_content fallback failed: {e}")

    if not video_bytes:
        return "Error: Failed to generate video from model."

    object_name = f"recipe_video_{uuid.uuid4().hex[:8]}.mp4"

    # 1. Save with tool_context.save_artifact so it shows up in Playground's Artifacts panel
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
    tool_context.save_artifact(filename=object_name, artifact=artifact_part)

    # 2. Upload same video bytes directly to public GCS bucket (in-memory)
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(object_name)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    # Return public HTTPS URL
    return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"


def geocode_address(address: str) -> Dict[str, Any]:
    """Convert a street address or city name into geographic coordinates (latitude and longitude).

    Args:
        address: The address or location query (e.g., '1600 Amphitheatre Pkwy, Mountain View, CA' or 'San Francisco').

    Returns:
        Dictionary containing formatted address and location coordinates (latitude and longitude).
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY is not configured in environment variables."}

    encoded_address = urllib.parse.quote(address.strip())
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") != "OK" or not data.get("results"):
                return {"error": f"Geocoding failed for address '{address}': status {data.get('status')}"}

            first_result = data["results"][0]
            loc = first_result["geometry"]["location"]
            return {
                "name": first_result.get("formatted_address"),
                "address": first_result.get("formatted_address"),
                "location": {
                    "latitude": loc["lat"],
                    "longitude": loc["lng"]
                }
            }
    except Exception as e:
        return {"error": f"Failed to geocode address: {str(e)}"}

def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "supermarket",
    radius_meters: float = 3000.0
) -> List[Dict[str, Any]]:
    """Search for nearby places of a specific type (e.g. supermarket, grocery_store, restaurant) near given coordinates.

    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        place_type: Type of place to search for (e.g., 'supermarket', 'grocery_store', 'bakery', 'restaurant').
        radius_meters: Radius around coordinates to search in meters (default: 3000.0).

    Returns:
        A list of nearby places with name, formatted address, and location coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return [{"error": "GOOGLE_MAPS_API_KEY is not configured in environment variables."}]

    url = "https://places.googleapis.com/v1/places:searchNearby"
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "radius": float(radius_meters)
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
    }

    try:
        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            places = data.get("places", [])
            
            results = []
            for p in places:
                loc = p.get("location", {})
                results.append({
                    "name": p.get("displayName", {}).get("text", "Unknown Place"),
                    "address": p.get("formattedAddress", "N/A"),
                    "location": {
                        "latitude": loc.get("latitude"),
                        "longitude": loc.get("longitude")
                    }
                })
            return results
    except Exception as e:
        return [{"error": f"Failed to search nearby places: {str(e)}"}]

def get_food_product_info(query: str) -> List[Dict[str, Any]]:
    """Search Open Food Facts database for food products, nutrition details, and Nutri-Score.

    Args:
        query: Name of the food item, brand, or ingredient to look up (e.g. 'avocado', 'oat milk', 'cheddar cheese').

    Returns:
        A list of matching products with brand, calories, nutriscore, and ingredient info.
    """
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://world.openfoodfacts.net/api/v2/search?q={encoded_query}&page_size=3"
    
    try:
        headers = {"User-Agent": "SmartRecipeAgent/1.0 (contact@smartrecipe.com)"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            products = data.get("products", [])
            if not products:
                return []
            
            results = []
            for p in products[:3]:
                nutriments = p.get("nutriments", {})
                results.append({
                    "product_name": p.get("product_name", "Unknown Product"),
                    "brand": p.get("brands", "Generic"),
                    "nutriscore_grade": p.get("nutriscore_grade", "").upper() or "N/A",
                    "calories_100g": nutriments.get("energy-kcal_100g", "N/A"),
                    "proteins_100g": nutriments.get("proteins_100g", "N/A"),
                    "fat_100g": nutriments.get("fat_100g", "N/A"),
                    "carbs_100g": nutriments.get("carbohydrates_100g", "N/A"),
                    "ingredients_text": p.get("ingredients_text", "")[:150]
                })
            return results
    except Exception as e:
        return [{"error": f"Failed to fetch food product info: {str(e)}"}]

def search_public_recipes(query: str) -> List[Dict[str, Any]]:
    """Search for public recipes from TheMealDB open API.

    Args:
        query: Recipe dish name or main ingredient to search for (e.g., 'chicken', 'arrabiata', 'pasta').

    Returns:
        A list of matching recipe dictionaries with instructions, ingredients, and image URLs.
    """
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={encoded_query}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            meals = data.get("meals")
            if not meals:
                return []
            
            results = []
            for meal in meals[:5]:
                ingredients = []
                for i in range(1, 21):
                    ing = meal.get(f"strIngredient{i}")
                    measure = meal.get(f"strMeasure{i}")
                    if ing and ing.strip():
                        item = f"{measure.strip()} {ing.strip()}".strip() if measure else ing.strip()
                        ingredients.append(item)
                        
                results.append({
                    "id": meal.get("idMeal"),
                    "name": meal.get("strMeal"),
                    "category": meal.get("strCategory"),
                    "cuisine": meal.get("strArea"),
                    "instructions": meal.get("strInstructions", "")[:300] + "...",
                    "image_url": meal.get("strMealThumb"),
                    "ingredients": ingredients
                })
            return results
    except Exception as e:
        return [{"error": f"Failed to fetch public recipes: {str(e)}"}]

def search_recipes(query: str = "", cuisine: str = "") -> List[Dict[str, Any]]:
    """Search for recipes in the Firestore database by keyword or cuisine.

    Args:
        query: Optional keyword search in recipe name or ingredients.
        cuisine: Optional filter by cuisine type (e.g., 'Italian', 'American').

    Returns:
        A list of matching recipe dictionaries.
    """
    db = get_firestore_client()
    recipes_ref = db.collection("recipes")
    docs = recipes_ref.stream()
    
    results = []
    q_lower = query.lower().strip()
    c_lower = cuisine.lower().strip()
    
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        
        # Check cuisine filter
        if c_lower and c_lower not in data.get("cuisine", "").lower():
            continue
            
        # Check query match in name, ingredients, or tags
        if q_lower:
            name_match = q_lower in data.get("name", "").lower()
            ing_match = any(q_lower in ing.lower() for ing in data.get("ingredients", []))
            tag_match = any(q_lower in tag.lower() for tag in data.get("tags", []))
            if not (name_match or ing_match or tag_match):
                continue
                
        results.append(data)
        
    return results

def get_recipe_details(recipe_id: str) -> Dict[str, Any]:
    """Get complete details for a specific recipe by ID.

    Args:
        recipe_id: Unique identifier for the recipe (e.g., 'avocado-toast').

    Returns:
        Recipe document data dictionary or error message.
    """
    db = get_firestore_client()
    doc_ref = db.collection("recipes").document(recipe_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        return {"error": f"Recipe with ID '{recipe_id}' not found."}
        
    data = doc.to_dict()
    data["id"] = doc.id
    return data

def add_recipe(
    name: str,
    cuisine: str,
    prep_time_mins: int,
    calories: int,
    ingredients: List[str],
    instructions: str,
    tags: List[str]
) -> Dict[str, Any]:
    """Add a new recipe to the Firestore database catalog.

    Args:
        name: Name of the recipe dish.
        cuisine: Cuisine style (e.g. 'Mexican', 'Italian').
        prep_time_mins: Preparation time in minutes.
        calories: Calorie count per serving.
        ingredients: List of ingredient strings.
        instructions: Step-by-step cooking instructions.
        tags: Categorization tags (e.g., ['dinner', 'vegetarian']).

    Returns:
        Status message with created recipe ID.
    """
    db = get_firestore_client()
    doc_id = name.lower().replace(" ", "-").replace("'", "")
    doc_ref = db.collection("recipes").document(doc_id)
    
    data = {
        "name": name,
        "cuisine": cuisine,
        "prep_time_mins": prep_time_mins,
        "calories": calories,
        "ingredients": ingredients,
        "instructions": instructions,
        "tags": tags
    }
    
    doc_ref.set(data)
    data["id"] = doc_id
    return {"message": "Recipe added successfully", "recipe": data}

def get_weather(query: str) -> str:
    """Simulates a web search for weather information.

    Args:
        query: Location query.

    Returns:
        Simulated weather information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."

def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: City name query.

    Returns:
        Current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"

# Build A2UI System Instruction v0.8 with BasicCatalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "A smart culinary assistant that helps users search for recipes, generate recipe dish images, "
        "perform calculations in a Python code sandbox, locate nearby supermarkets, geocode addresses, "
        "lookup nutrition info, view recipe details, and add new recipes."
    ),
    workflow_description=(
        "You ALWAYS remember, track, and strictly honor all user food allergies, dietary restrictions "
        "(e.g., peanuts, tree nuts, dairy, gluten, shellfish, soy, eggs), and dietary preferences across sessions. "
        "Whenever a user states an allergy, acknowledge it and ensure all future recipe suggestions, meal plans, "
        "and ingredient substitutions strictly exclude their allergens. Never suggest a dish containing a known "
        "user allergen without explicitly offering a safe substitution. Analyze the user's request and return "
        "structured UI when appropriate."
    ),
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
    code_executor=get_code_executor(),
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        generate_recipe_image,
        generate_recipe_video,
        geocode_address,
        find_nearby_places,
        get_food_product_info,
        search_public_recipes,
        search_recipes,
        get_recipe_details,
        add_recipe,
        get_weather,
        get_current_time,
    ],
    before_agent_callback=ensure_memory_service_callback,
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
