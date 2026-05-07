# AI Lead Intelligence Engine

A high-performance, automated lead generation and outreach engine built in Python. Uses Gemini AI for intelligent lead discovery and deep business analysis.

## Live Application
You can access the live dashboard here:
**[https://python-scraper-gskykg3vj3z3m2ueewgyfn.streamlit.app/](https://python-scraper-gskykg3vj3z3m2ueewgyfn.streamlit.app/)**

## Features

- **Multi-Source Lead Discovery** — Gemini AI, Google Maps, DuckDuckGo, SerpApi
- **Deep Website Scraping** — Smart text extraction with Playwright fallback for JS-heavy sites, email/phone extraction with scoring, social media link detection
- **AI Business Analysis** — Automation scoring, pain point detection, tech stack identification, outreach email generation
- **Token-Efficient** — Clean HTML extraction reduces Gemini API token usage by ~60%, structured JSON output eliminates parse failures
- **Smart Caching** — Skips already-scraped URLs and already-analyzed companies on reruns
- **Dashboard** — Cyberpunk-themed Streamlit UI with pagination, sorting, score filtering, and collapsible lead cards

## Pipeline

1. **Find Leads** (`lead_finder.py`) — Discover companies via selected source
2. **Scrape Sites** (`deep_diver.py`) — Visit websites, extract contact data and content
3. **AI Analyze** (`ai_analyzer.py`) — Gemini deep analysis with automation scoring

## Local Execution

```bash
pip install -r requirements.txt
playwright install chromium    # install browser for JS rendering
streamlit run app.py
```

> **Note:** `playwright install chromium` downloads a Chromium browser (~130 MB) used to scrape JS-heavy websites. This is optional — if Playwright is not installed, the scraper uses `requests` only.

## Environment Variables

Create a `.env` file or set in the Streamlit sidebar:

```
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_api_key  # optional
SERPAPI_KEY=your_serpapi_key                    # optional
```
