import requests
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import hashlib
import json
from django.conf import settings
from django.core.cache import cache

@dataclass
class RelevantLink:
    text: str
    link: str

@dataclass
class AEO_Overview:
    snippets: List[str] = field(default_factory=list)
    sources: List[RelevantLink] = field(default_factory=list)
    
@dataclass
class RelatedQuestion:
    question: str
    snippet: str
    link: str
    title: str

@dataclass
class LocalPackPlace:
    title: str
    position: int
    rating: float
    reviews: int
    address: str
    type: str

def fetch_serpapi_engine(engine: str, query: str, location: str = "") -> dict:
    """Wrapper to query specific SerpApi engines."""
    params = {
        "engine": engine,
        "q": query,
        "api_key": settings.SERPAPI_API_KEY,
    }
    if location:
        params["location"] = location
        
    safe_params = {k: v for k, v in params.items() if k != "api_key"}
    param_hash = hashlib.md5(json.dumps(safe_params, sort_keys=True).encode("utf-8")).hexdigest()
    cache_key = f"seo:serpapi:intelligence:{param_hash}"
    
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
        
    try:
        response = requests.get(
            "https://serpapi.com/search.json",
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        cache.set(cache_key, data, 604800)  # Cache for 7 days
        return data
    except Exception as e:
        return {"error": str(e)}

def extract_aeo_overview(payload: dict) -> Optional[AEO_Overview]:
    """Parse the ai_overview key from Google Search API"""
    if not isinstance(payload, dict) or "ai_overview" not in payload:
        return None
        
    ai_data = payload["ai_overview"]
    overview = AEO_Overview()
    
    for block in ai_data.get("text_blocks", []):
        if block.get("snippet"):
            overview.snippets.append(block["snippet"])
    
    for ref in ai_data.get("references", []):
        if ref.get("title") and ref.get("link"):
            overview.sources.append(RelevantLink(text=ref["title"], link=ref["link"]))
            
    return overview if overview.snippets else None

def extract_related_questions(payload: dict) -> List[RelatedQuestion]:
    """Parse the related_questions key from Google Search API"""
    questions = []
    if not isinstance(payload, dict):
        return questions
        
    for item in payload.get("related_questions", []):
        questions.append(
            RelatedQuestion(
                question=item.get("question", ""),
                snippet=item.get("snippet", ""),
                link=item.get("link", ""),
                title=item.get("title", "")
            )
        )
    return questions

def extract_local_pack(payload: dict) -> List[LocalPackPlace]:
    """Parse the local_results or places array"""
    places = []
    if not isinstance(payload, dict):
        return places
        
    local_data = payload.get("local_results", {})
    records = local_data.get("places", []) if isinstance(local_data, dict) else []
    
    # Sometimes it can be list directly
    if isinstance(local_data, list):
        records = local_data
        
    for item in records:
        if isinstance(item, dict) and item.get("title"):
            try:
                rating = float(item.get("rating", 0.0))
            except (ValueError, TypeError):
                rating = 0.0
            
            try:
                reviews = int(item.get("reviews", 0))
            except (ValueError, TypeError):
                reviews = 0
                
            places.append(
                LocalPackPlace(
                    title=item.get("title", ""),
                    position=item.get("position", item.get("rank", 99)),
                    rating=rating,
                    reviews=reviews,
                    address=item.get("address", ""),
                    type=item.get("type", "")
                )
            )
    return places

def run_seo_aeo_pipeline(query: str, location: str, business_type: str) -> Dict[str, Any]:
    """
    Executes the Phase 3 Engine Pipeline to gather multifaceted intelligence.
    Can be run synchronously or wrapped in a Celery task.
    """
    # Pipeline 1 & 2: Google Search (Captures AEO Overview + organic + related questions)
    google_payload = fetch_serpapi_engine("google", query, location)
    
    intelligence = {
        "query": query,
        "location": location,
        "aeo_overview": extract_aeo_overview(google_payload),
        "related_questions": extract_related_questions(google_payload),
        "local_pack": [],
        "bing_copilot_response": None
    }
    
    # Conditional Pipeline 3: Local Pack
    if business_type in ["local_service", "hotel", "automotive", "healthcare", "real_estate"]:
        intelligence["local_pack"] = extract_local_pack(google_payload)
        
    # We can expand to use google_trends, bing_copilot, etc., identically through fetch_serpapi_engine.
    
    return intelligence
