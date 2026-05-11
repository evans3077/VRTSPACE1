import os
import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class DataForSeoClient:
    """
    Clinical Precision API Client for DataForSEO.
    Used for Enterprise-grade Backlink Data, Search Volume, and Market Gap Analysis.
    
    This client is designed to gracefully fallback or return mock structural data 
    if billing/API keys are not yet fully activated by the user.
    """
    
    BASE_URL = "https://api.dataforseo.com/v3"

    def __init__(self):
        # We read from environment variables directly to allow easy swapping
        self.login = os.environ.get("DATAFORSEO_LOGIN", "").strip()
        self.password = os.environ.get("DATAFORSEO_PASSWORD", "").strip()
        self.is_configured = bool(self.login and self.password)

    def _get_auth(self):
        return (self.login, self.password)

    def get_search_volume(self, keywords, location_code=2840, language_code="en"):
        """
        Fetch real search volume, CPC, and competition data for a list of keywords.
        location_code 2840 = USA.
        """
        if not self.is_configured:
            logger.warning("DataForSEO is not configured. Returning structural mock data for Search Volume.")
            return self._mock_search_volume(keywords)

        url = f"{self.BASE_URL}/dataforseo_labs/google/search_volume/live"
        payload = [{
            "location_code": location_code,
            "language_code": language_code,
            "keywords": keywords
        }]
        
        try:
            response = requests.post(
                url, 
                auth=self._get_auth(), 
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract and return the clinical data
            results = {}
            if "tasks" in data and len(data["tasks"]) > 0:
                task_result = data["tasks"][0].get("result", [])
                if task_result:
                    for item in task_result:
                        kw = item.get("keyword")
                        vol = item.get("search_volume", 0)
                        cpc = item.get("cpc", 0.0)
                        kd = item.get("keyword_difficulty", 0)
                        results[kw] = {"volume": vol, "cpc": cpc, "difficulty": kd}
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"DataForSEO Search Volume API Error: {e}")
            return self._mock_search_volume(keywords)

    def get_backlink_profile(self, target_domain):
        """
        Fetch clinical backlink data (total backlinks, referring domains, referring IPs)
        for competitive gap analysis.
        """
        if not self.is_configured:
            logger.warning("DataForSEO is not configured. Returning structural mock data for Backlinks.")
            return self._mock_backlink_profile(target_domain)

        url = f"{self.BASE_URL}/backlinks/summary/live"
        payload = [{
            "target": target_domain,
            "internal_list_limit": 10
        }]

        try:
            response = requests.post(
                url, 
                auth=self._get_auth(), 
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if "tasks" in data and len(data["tasks"]) > 0:
                result = data["tasks"][0].get("result", [])
                if result:
                    summary = result[0]
                    return {
                        "backlinks": summary.get("backlinks", 0),
                        "referring_domains": summary.get("referring_domains", 0),
                        "referring_ips": summary.get("referring_ips", 0),
                        "rank": summary.get("rank", 0)
                    }
            return self._mock_backlink_profile(target_domain)

        except requests.exceptions.RequestException as e:
            logger.error(f"DataForSEO Backlink API Error: {e}")
            return self._mock_backlink_profile(target_domain)

    # --- Fallback Mock Generators (for while billing is being organized) ---

    def _mock_search_volume(self, keywords):
        """Generates realistic-looking structural data so the UI/Logic doesn't break."""
        mock_data = {}
        for kw in keywords:
            # Generate deterministic mock numbers based on string length
            vol = len(kw) * 150
            kd = min(len(kw) * 3, 85) 
            cpc = round(len(kw) * 0.25, 2)
            mock_data[kw] = {
                "volume": vol,
                "cpc": cpc,
                "difficulty": kd,
                "is_mock": True
            }
        return mock_data

    def _mock_backlink_profile(self, target_domain):
        domain_length = len(target_domain)
        return {
            "backlinks": domain_length * 1500,
            "referring_domains": domain_length * 120,
            "referring_ips": domain_length * 110,
            "rank": max(100 - domain_length, 10),
            "is_mock": True
        }
