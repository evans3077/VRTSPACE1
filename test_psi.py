import os
import requests
import dotenv

dotenv.load_dotenv(override=True)
PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

def test_psi(url):
    api_key = (
        os.environ.get("webspeed", "").strip()
        or os.environ.get("WEBSPEED", "").strip()
        or os.environ.get("PAGESPEED_API_KEY", "").strip()
    )
    categories = ["performance", "accessibility", "best-practices", "seo"]
    params = [("url", url), ("strategy", "mobile")]
    for cat in categories:
        params.append(("category", cat))
    if api_key:
        params.append(("key", api_key))
        print("Using API KEY")
    else:
        print("NO API KEY")
    
    try:
        response = requests.get(PAGESPEED_API_URL, params=params, timeout=30)
        print("Status Code:", response.status_code)
        if response.status_code != 200:
            print(response.text)
        response.raise_for_status()
        payload = response.json()
        print("Keys:", list(payload.get("lighthouseResult", {}).get("categories", {}).keys()))
    except Exception as e:
        print("Error:", repr(e))

if __name__ == "__main__":
    test_psi("https://www.kaiandkaro.com/")
