import os
import json
from typing import Optional, List, Dict, Any
# pyrefly: ignore [missing-import]
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

import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# LangChain Gemini Elaboration Pipeline Configuration
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gemini-1.5-flash")

llm = None
if LLM_API_KEY:
    try:
        llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL_NAME,
            google_api_key=LLM_API_KEY,
            temperature=0.7
        )
        print(f"Successfully initialized ChatGoogleGenerativeAI with model: {LLM_MODEL_NAME}")
    except Exception as e:
        print(f"Failed to initialize ChatGoogleGenerativeAI: {e}")

def clean_and_parse_json(text: str) -> Optional[Dict[str, str]]:
    """Defensive utility to clean code block backticks and parse JSON output."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        return None

async def elaborate_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """Sends a single article to Gemini to rephrase/elaborate in premium broadsheet style."""
    if not llm:
        return article
    
    title = article.get("title", "")
    description = article.get("description", "")
    content = article.get("content", "")
    
    if not title:
        return article

    prompt = ChatPromptTemplate.from_template(
        "You are an expert news editor for \"The Daily Gazette\", a premium digital broadsheet newspaper.\n"
        "Your task is to rephrase and elaborate on the raw wire news content below to make it sound authoritative, detailed, and written in a classic editorial style.\n\n"
        "Raw Title: {title}\n"
        "Raw Description: {description}\n"
        "Raw Content: {content}\n\n"
        "You must return a valid JSON object matching this schema. Do not output any markdown formatting, commentary, or extra text. Return ONLY the raw JSON string:\n"
        "{{\n"
        "  \"title\": \"Rephrased elegant headline in classic newspaper format\",\n"
        "  \"description\": \"Elaborated, detailed single-sentence summary of the event\",\n"
        "  \"content\": \"Elaborated classic print broadsheet article content (2-3 paragraphs, descriptive, high-quality editorial writing)\"\n"
        "}}"
    )

    chain = prompt | llm | StrOutputParser()

    try:
        output = await asyncio.wait_for(
            chain.ainvoke({"title": title, "description": description or "", "content": content or ""}),
            timeout=10.0
        )
        parsed = clean_and_parse_json(output)
        if parsed:
            article_copy = article.copy()
            article_copy["title"] = parsed.get("title", title)
            article_copy["description"] = parsed.get("description", description)
            article_copy["content"] = parsed.get("content", content)
            return article_copy
    except Exception as e:
        print(f"Elaboration failed for article '{title}': {e}")
        
    return article

async def elaborate_articles(articles: List[Dict[str, Any]], limit: int = 4) -> List[Dict[str, Any]]:
    """Runs elaboration in parallel for the top N articles in a feed list."""
    if not llm or not articles:
        return articles
    
    to_elaborate = articles[:limit]
    remaining = articles[limit:]

    tasks = [elaborate_article(art) for art in to_elaborate]
    elaborated = await asyncio.gather(*tasks, return_exceptions=True)

    result = []
    for i, res in enumerate(elaborated):
        if isinstance(res, Exception):
            result.append(to_elaborate[i])
        else:
            result.append(res)
            
    result.extend(remaining)
    return result

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
                if "articles" in data:
                    data["articles"] = await elaborate_articles(data["articles"])
                return data
            else:
                fallback_data = get_local_headlines(category)
                if "articles" in fallback_data:
                    fallback_data["articles"] = await elaborate_articles(fallback_data["articles"])
                return fallback_data
    except Exception:
        fallback_data = get_local_headlines(category)
        if "articles" in fallback_data:
            fallback_data["articles"] = await elaborate_articles(fallback_data["articles"])
        return fallback_data


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
                if "articles" in data:
                    data["articles"] = await elaborate_articles(data["articles"])
                return data
            else:
                fallback_data = get_local_everything(source_id)
                if "articles" in fallback_data:
                    fallback_data["articles"] = await elaborate_articles(fallback_data["articles"])
                return fallback_data
    except Exception:
        fallback_data = get_local_everything(source_id)
        if "articles" in fallback_data:
            fallback_data["articles"] = await elaborate_articles(fallback_data["articles"])
        return fallback_data


from fastapi.staticfiles import StaticFiles

# Mount the static frontend files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

