import argparse
import pandas as pd
import os
import sys
import time
import json
import random
from urllib.parse import urlparse


def normalize_url(url):
    """Normalize URL for consistent deduplication."""
    if not url:
        return ""
    url = url.strip().rstrip('/')
    if not url.startswith('http'):
        url = 'https://' + url
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace('www.', '')
    path = parsed.path.rstrip('/')
    return f"{parsed.scheme}://{host}{path}"


def search_duckduckgo(query, max_results=10):
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        print("ERROR: duckduckgo-search not installed. Run 'pip install duckduckgo-search'")
        return []

    print(f"Searching DuckDuckGo for: {query} (Limit: {max_results})")
    try:
        results = []
        # Fetch more to account for post-filtering
        ddgs_results = DDGS().text(query, max_results=max_results * 2)
        if ddgs_results:
            junk_url_patterns = ['/blog', '/article', '/post', '/news', '/directory', '/top-10', '/best-']

            for r in ddgs_results:
                href = r.get("href", "").lower()

                if any(junk in href for junk in junk_url_patterns):
                    continue
                if any(domain in href for domain in ['wikipedia.org', 'reddit.com', 'yelp.', 'yellowpages.']):
                    continue

                results.append({
                    "Company Name": r.get("title", ""),
                    "Website URL":  normalize_url(r.get("href", "")),
                    "Source":       "DuckDuckGo"
                })

                if len(results) >= max_results:
                    break

            print(f"DuckDuckGo returned {len(results)} clean results.")
            return results
        else:
            print("ERROR: DuckDuckGo returned 0 results. Your IP may be rate-limited.")
            return []
    except Exception as e:
        print(f"ERROR: DuckDuckGo search failed: {e}")
        return []


def search_google_maps(query, api_key):
    import requests

    if not api_key:
        print("ERROR: Google Maps API key is required. Set GOOGLE_MAPS_API_KEY environment variable.")
        return []

    results = []
    print(f"Searching Google Maps for: {query}")

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName.text,places.websiteUri"
    }
    data = {"textQuery": query, "maxResultCount": 20}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        places = response.json().get('places', [])
        for place in places:
            website = place.get('websiteUri', '')
            name = place.get('displayName', {}).get('text', '')
            if website:
                results.append({
                    "Company Name": name,
                    "Website URL": normalize_url(website),
                    "Source": "Google Maps",
                })
        print(f"Google Maps returned {len(results)} results.")
    except Exception as e:
        print(f"ERROR: Google Maps API error: {e}")

    return results


def search_serpapi(query, api_key, limit=20):
    try:
        from serpapi import GoogleSearch
    except ImportError:
        print("ERROR: google-search-results not installed. Run 'pip install google-search-results'")
        return []

    if not api_key:
        print("ERROR: SerpApi key is required. Set SERPAPI_KEY environment variable.")
        return []

    results = []
    print(f"Searching SerpApi for: {query} (Limit: {limit})")
    params = {"q": query, "api_key": api_key, "num": min(limit, 100)}

    try:
        search = GoogleSearch(params)
        results_data = search.get_dict()
        for r in results_data.get('organic_results', []):
            results.append({
                "Company Name": r.get("title", ""),
                "Website URL": normalize_url(r.get("link", "")),
                "Source": "SerpApi",
            })
        print(f"SerpApi returned {len(results)} results.")
    except Exception as e:
        print(f"ERROR: SerpApi error: {e}")

    return results


def search_gemini(query, api_key, limit=20):
    if not api_key:
        print("ERROR: GEMINI_API_KEY is required for Gemini Discovery.")
        return []

    import requests

    print(f"Using Gemini AI to discover leads for: {query} (Limit: {limit})")

    prompt = f"""You are a business research assistant. Generate a list of {limit} real businesses matching this query: "{query}".

For each business provide:
- Company Name
- Website URL (real URL, e.g. https://example.com)

Return ONLY a valid JSON array like this:
[
  {{"Company Name": "Example HVAC AS", "Website URL": "https://example.no"}},
  ...
]
Return ONLY the JSON array, no other text."""

    # Use gemini-2.0-flash with structured JSON output
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        }
    }

    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            if response.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"Rate limited (429). Waiting {wait}s before retry...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            result = response.json()
            if 'candidates' not in result or len(result['candidates']) == 0:
                print("ERROR: Gemini returned no candidates.")
                return []

            text = result['candidates'][0]['content']['parts'][0]['text']
            # With responseMimeType, should be clean JSON already
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            leads = json.loads(text)
            if not isinstance(leads, list):
                print("ERROR: Gemini did not return a list.")
                return []

            # Ensure correct keys and normalize URLs
            cleaned = []
            for l in leads:
                name = l.get("Company Name") or l.get("company_name") or l.get("name") or ""
                url_val = l.get("Website URL") or l.get("website_url") or l.get("url") or l.get("website") or ""
                if name:
                    cleaned.append({
                        "Company Name": name,
                        "Website URL": normalize_url(url_val),
                        "Source": "Gemini AI",
                    })

            print(f"Gemini discovered {len(cleaned)} leads.")
            return cleaned

        except json.JSONDecodeError as e:
            print(f"ERROR: Could not parse Gemini JSON response: {e}")
            print(f"Raw response was: {text[:300]}")
            return []
        except Exception as e:
            print(f"ERROR: Gemini discovery attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(5)

    return []


def main():
    parser = argparse.ArgumentParser(description="Lead Finder — Step 1 of Lead Scraper Pipeline")
    parser.add_argument("--query", type=str, required=True, help="Search query")
    parser.add_argument("--source", type=str,
                        choices=["duckduckgo", "google_maps", "serpapi", "gemini"],
                        default="gemini", help="Search source to use")
    parser.add_argument("--output", type=str, default="leads.csv", help="Output CSV file name")
    parser.add_argument("--limit", type=int, default=20, help="Max leads to find")
    parser.add_argument("--pain-reason", type=str, default="", help="Why this lead was searched (from template)")

    args = parser.parse_args()

    leads = []
    if args.source == "duckduckgo":
        leads = search_duckduckgo(args.query, max_results=args.limit)
    elif args.source == "google_maps":
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        leads = search_google_maps(args.query, api_key)[:args.limit]
    elif args.source == "serpapi":
        api_key = os.environ.get("SERPAPI_KEY")
        leads = search_serpapi(args.query, api_key, limit=args.limit)
    elif args.source == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        leads = search_gemini(args.query, api_key, limit=args.limit)

    if leads:
        new_df = pd.DataFrame(leads)
        # Add search context
        pain_reason = getattr(args, 'pain_reason', '') or ''
        if pain_reason:
            new_df["Search Reason"] = pain_reason
        new_df["Search Query"] = args.query
        # Normalize URLs for consistent dedup
        new_df['Website URL'] = new_df['Website URL'].apply(normalize_url)

        # Append to existing leads and deduplicate by normalized URL
        if os.path.exists(args.output):
            existing_df = pd.read_csv(args.output)
            existing_df['Website URL'] = existing_df['Website URL'].apply(normalize_url)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=["Website URL"], keep="first")
            combined_df.to_csv(args.output, index=False)
            added = len(combined_df) - len(existing_df)
            print(f"SUCCESS: Added {added} new leads. Total in file: {len(combined_df)}")
        else:
            new_df.to_csv(args.output, index=False)
            print(f"SUCCESS: Saved {len(new_df)} leads to {args.output}")
        sys.exit(0)
    else:
        print("FAILED: No leads were found. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
