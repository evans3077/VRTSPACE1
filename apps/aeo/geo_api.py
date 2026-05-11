import os
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class GeoApiClient:
    """
    Generative Engine Optimization (GEO) and Answer Engine Optimization (AEO) API Client.
    Integrates Perplexity (Sonar Pro) and Google Cloud Natural Language for Clinical Precision testing.
    
    This client is designed to gracefully fallback or return mock structural data 
    if billing/API keys are not yet fully activated by the user.
    """

    def __init__(self):
        self.perplexity_api_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()
        self.google_nl_api_key = os.environ.get("GOOGLE_CLOUD_API_KEY", "").strip()
        
        self.is_perplexity_configured = bool(self.perplexity_api_key)
        self.is_google_nl_configured = bool(self.google_nl_api_key)

    def run_geo_shootout(self, brand_name, service_query, competitors):
        """
        Runs a test against Perplexity's Sonar Pro to see if the brand is cited 
        when a user searches for the primary service vs competitors.
        """
        if not self.is_perplexity_configured:
            logger.warning("Perplexity API is not configured. Returning structural mock data for GEO Shootout.")
            return self._mock_geo_shootout(brand_name, competitors)

        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = (
            f"You are an expert industry analyst. A user is looking for '{service_query}'. "
            f"Compare the following brands and recommend the best option based on current web data: "
            f"{brand_name}, {', '.join(competitors)}."
        )

        payload = {
            "model": "llama-3-sonar-large-32k-online", # or standard sonar-pro
            "messages": [
                {"role": "system", "content": "Be concise and cite sources."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            data = response.json()
            
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Clinical evaluation: Did the engine cite our brand favorably?
            brand_mentioned = brand_name.lower() in content.lower()
            
            return {
                "engine_response": content,
                "brand_cited": brand_mentioned,
                "confidence_score": 85 if brand_mentioned else 30,
                "is_mock": False
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Perplexity API Error: {e}")
            return self._mock_geo_shootout(brand_name, competitors)

    def get_entity_confidence_score(self, page_content):
        """
        Runs the page text through Google Cloud Natural Language API to see 
        if Google recognizes the primary business entity.
        """
        if not self.is_google_nl_configured:
            logger.warning("Google NL API is not configured. Returning structural mock data for Entity Confidence.")
            return self._mock_entity_confidence()

        url = f"https://language.googleapis.com/v1/documents:analyzeEntities?key={self.google_nl_api_key}"
        payload = {
            "document": {
                "type": "PLAIN_TEXT",
                "content": page_content[:10000] # Limit to avoid huge payloads
            },
            "encodingType": "UTF8"
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            entities = data.get("entities", [])
            # Filter and sort top entities by salience
            top_entities = sorted(entities, key=lambda x: x.get("salience", 0), reverse=True)[:5]
            
            formatted_entities = [
                {
                    "name": e.get("name"), 
                    "type": e.get("type"), 
                    "salience": round(e.get("salience", 0) * 100, 2)
                } for e in top_entities
            ]
            
            return {
                "entities": formatted_entities,
                "highest_salience": formatted_entities[0]["salience"] if formatted_entities else 0,
                "is_mock": False
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Cloud NL API Error: {e}")
            return self._mock_entity_confidence()

    # --- Fallback Mock Generators (for while billing is being organized) ---

    def _mock_geo_shootout(self, brand_name, competitors):
        return {
            "engine_response": f"Based on web searches, {competitors[0]} is frequently mentioned. {brand_name} is also a notable option but lacks the same citation volume.",
            "brand_cited": True,
            "confidence_score": 65,
            "is_mock": True,
            "mock_notice": "Billing inactive. This is a structural preview."
        }

    def _mock_entity_confidence(self):
        return {
            "entities": [
                {"name": "Mock Business Service", "type": "ORGANIZATION", "salience": 82.5},
                {"name": "Local City", "type": "LOCATION", "salience": 45.2}
            ],
            "highest_salience": 82.5,
            "is_mock": True,
            "mock_notice": "Billing inactive. This is a structural preview."
        }
