# Smart Recipe Assistant

A personalized, interactive culinary AI assistant powered by the Google Agent Development Kit (ADK) and deployed to Vertex AI Agent Runtime. It helps users discover recipes, search their personal recipe database, calculate nutrition, locate local grocery stores, and generate visual food photography and culinary preparation videos on demand.

![Smart Recipe Assistant Demo](./demo.gif)

---

## 🌟 Capabilities & Features

### 1. **Cross-Session Long-Term Memory**
- **Vertex AI Memory Bank**: Remembers user preferences, dietary restrictions, and favorite cuisines across sessions using `VertexAiMemoryBankService` and `PreloadMemoryTool`.

### 2. **Firestore Recipe Database**
- **Custom Recipe Storage**: Saves, searches, and retrieves full recipe details directly from Google Cloud Firestore.
- **Tools**: `search_recipes`, `get_recipe_details`, `add_recipe`.

### 3. **Generative Visual Media**
- **AI Food Photography**: Generates high-resolution food photos using `gemini-3.1-flash-lite-image` in the `global` region.
- **AI Culinary Video Clips**: Generates short recipe preparation and plating videos using `gemini-omni-flash-preview` in the `global` region.
- **Cloud Storage & Artifacts**: Automatically saves media as ADK Playground artifacts and uploads in-memory to Google Cloud Storage.
- **Tools**: `generate_recipe_image`, `generate_recipe_video`.

### 4. **Location & Grocery Finder**
- **Geocoding & Places Search**: Finds local supermarkets, specialty food stores, and ingredient markets using Google Maps Geocoding and Places APIs.
- **Tools**: `geocode_address`, `find_nearby_places`.

### 5. **External Recipe & Nutrition Integration**
- **Spoonacular API**: Searches public recipe catalogs (`search_public_recipes`).
- **Open Food Facts API**: Retrieves nutritional breakdown and product information (`get_food_product_info`).
- **Utilities**: `get_weather`, `get_current_time`.

### 6. **Rich Dynamic UI (A2UI)**
- **A2UI Cards & Components**: Generates rich interactive cards, structured columns, and dietary highlight chips rendered seamlessly by a built-in FastAPI web frontend.

---

## 🏗️ Technical Architecture

```
                       ┌─────────────────────────┐
                       │  FastAPI Web Frontend   │
                       │  (A2UI Card Renderer)   │
                       └────────────┬────────────┘
                                    │ (A2A Protocol)
                                    ▼
                       ┌─────────────────────────┐
                       │ ADK Agent (root_agent)  │
                       └────────────┬────────────┘
                                    │
    ┌──────────────────┬────────────┼────────────┬──────────────────┐
    ▼                  ▼            ▼            ▼                  ▼
┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌────────────────────┐
│ Vertex AI    │ │ Cloud    │ │ Cloud    │ │ Google    │ │ Gemini Omni /      │
│ Memory Bank  │ │Firestore │ │ Storage  │ │ Maps APIs │ │ Flash Image Models │
└──────────────┘ └──────────┘ └──────────┘ └───────────┘ └────────────────────┘
```

- **Framework**: Google Agent Development Kit (ADK) `v2.0.0`
- **Model**: `gemini-flash-latest` (Root Orchestrator)
- **Deployment Target**: Vertex AI Agent Runtime (`agent_runtime`)
- **Code Executor**: `AgentEngineSandboxCodeExecutor`

---

## 🚀 Setup & Local Execution

### 1. Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) or standard Python virtual environment
- Google Cloud SDK (`gcloud` CLI) authenticated with access to Vertex AI, Firestore, and Cloud Storage.

### 2. Environment Setup

Clone the repository and install dependencies:

```bash
uv sync
```

Set required environment variables:

```bash
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT="<your-gcp-project-id>"
export GOOGLE_CLOUD_LOCATION="us-east1"
export GOOGLE_MAPS_API_KEY="<your-google-maps-api-key>"
```

### 3. Seed Initial Database (Optional)

Seed Firestore with sample recipes:

```bash
uv run python seed_firestore.py
```

### 4. Run Agent & Frontend Locally

Start the local server (FastAPI proxy + Web UI):

```bash
uv run python main.py
```

Open your browser to the local server port displayed in the console output to interact with the Smart Recipe Assistant.

---

## 📦 Deployment to Agent Runtime

To deploy or update the agent on Vertex AI Agent Runtime:

```bash
agents-cli deploy --project <your-gcp-project-id> --region us-east1
```
