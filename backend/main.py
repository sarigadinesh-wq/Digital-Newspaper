import os
import json
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

NEWS_API_BASE_URL = os.getenv("NEWS_API_BASE_URL", "https://saurav.tech/NewsAPI").rstrip("/")
API_KEY = os.getenv("API_KEY", "")

app = FastAPI(
    title="Digital Newspaper Backend API",
    description="Asynchronous proxy API to fetch real-time news data with robust local fallback capability.",
    version="1.0.0"
)

# Enable CORS for local testing and Nginx routing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load fallback data
FALLBACK_FILE = os.path.join(os.path.dirname(__file__), "fallback_data.json")
try:
    with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
        fallback_db = json.load(f)
except Exception as e:
    # Minimal hardcoded fallback db in case file is missing
    fallback_db = {
        "sources": [],
        "articles": {
            "general": []
        }
    }

def get_local_headlines(category: str) -> Dict[str, Any]:
    """Helper to structure local fallback headlines."""
    articles = fallback_db.get("articles", {}).get(category, [])
    if not articles:
        # Fallback to general if category is empty
        articles = fallback_db.get("articles", {}).get("general", [])
    return {
        "status": "ok",
        "totalResults": len(articles),
        "articles": articles,
        "is_fallback": True
    }

def get_local_sources() -> Dict[str, Any]:
    """Helper to structure local fallback sources."""
    sources = fallback_db.get("sources", [])
    return {
        "status": "ok",
        "sources": sources,
        "is_fallback": True
    }

def get_local_everything(source_id: str) -> Dict[str, Any]:
    """Helper to generate local fallback articles filtered by source_id."""
    articles = []
    for cat_articles in fallback_db.get("articles", {}).values():
        for art in cat_articles:
            if art.get("source", {}).get("id") == source_id:
                articles.append(art)
    
    # If no specific source found, return a generic list with modified source details
    if not articles:
        generic_articles = fallback_db.get("articles", {}).get("general", [])
        for art in generic_articles:
            art_copy = art.copy()
            art_copy["source"] = {"id": source_id, "name": source_id.replace("-", " ").title()}
            articles.append(art_copy)

    return {
        "status": "ok",
        "totalResults": len(articles),
        "articles": articles,
        "is_fallback": True
    }

@app.get("/api/health")
async def health_check():
    """Simple API health probe."""
    return {"status": "healthy", "news_base_url": NEWS_API_BASE_URL}

@app.get("/api/sources")
async def get_sources():
    """
    Fetch list of news sources from the external API.
    If external API is unreachable, return local fallback sources.
    """
    url = f"{NEWS_API_BASE_URL}/sources.json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                data["is_fallback"] = False
                return data
            else:
                return get_local_sources()
    except Exception:
        # Gracefully handle network timeouts or DNS resolution issues
        return get_local_sources()

@app.get("/api/top-headlines")
async def get_top_headlines(
    category: str = Query("general", description="News category filter"),
    country: str = Query("us", description="Two-letter country code")
):
    """
    Fetch top headlines by category and country.
    If external API fails or is unreachable, returns local fallback category data.
    """
    # Normalize inputs
    category = category.lower()
    country = country.lower()
    
    valid_categories = {"general", "business", "health", "science", "sports", "technology", "entertainment"}
    if category not in valid_categories:
        category = "general"

    url = f"{NEWS_API_BASE_URL}/top-headlines/category/{category}/{country}.json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                data["is_fallback"] = False
                return data
            else:
                return get_local_headlines(category)
    except Exception:
        return get_local_headlines(category)

@app.get("/api/everything/{source_id}")
async def get_everything(
    source_id: str = Path(..., description="The identifier of the news source (e.g. cnn, bbc-news)")
):
    """
    Fetch all articles published by a specific news source.
    If external API fails or is unreachable, returns local fallback source articles.
    """
    url = f"{NEWS_API_BASE_URL}/everything/{source_id}.json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                data["is_fallback"] = False
                return data
            else:
                return get_local_everything(source_id)
    except Exception:
        return get_local_everything(source_id)

from fastapi.staticfiles import StaticFiles

# Mount the static frontend files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

