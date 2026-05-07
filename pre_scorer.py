"""
Pre-Score Engine — Phase 2 (Enhanced)
Pure Python pain detection. Scores leads 1-10 based on 16 website checks.
No API keys needed. No Playwright. No Gemini. Free tools only.

Checks: HTTP headers, SSL, CMS, robots.txt, response time, mobile viewport,
Schema.org, Open Graph, chat widgets, booking, analytics, contact forms,
social links, domain age (whois), email provider (DNS MX), site staleness (Wayback).

Usage:
    python pre_scorer.py
    Reads leads.csv → outputs pain_scored_leads.csv
"""

import pandas as pd
import time
import re
import ssl
import socket
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import os
from datetime import datetime

# Use httpx for async-capable HTTP (faster than requests)
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import requests

# python-whois for domain age
try:
    import whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False

# dnspython for MX record lookup
try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

# Timeout for all HTTP requests (seconds)
REQUEST_TIMEOUT = 8
MAX_WORKERS = 10

# ─── PAIN DETECTION CHECKS ──────────────────────────────────────────────────

def normalize_url(url):
    """Ensure URL has scheme."""
    url = str(url).strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _get(url, **kwargs):
    """HTTP GET using httpx if available, else requests."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    kwargs.setdefault("follow_redirects", True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    if HTTPX_AVAILABLE:
        return httpx.get(url, headers=headers, **kwargs)
    else:
        kwargs.pop("follow_redirects", None)
        return requests.get(url, headers=headers, allow_redirects=True, **kwargs)


def _head(url, **kwargs):
    """HTTP HEAD using httpx if available, else requests."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    kwargs.setdefault("follow_redirects", True)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LeadScorer/1.0)"}
    if HTTPX_AVAILABLE:
        return httpx.head(url, headers=headers, **kwargs)
    else:
        kwargs.pop("follow_redirects", None)
        return requests.head(url, headers=headers, allow_redirects=True, **kwargs)


def check_headers(url):
    """Check HTTP headers for server tech, security headers."""
    result = {"server": "", "has_security_headers": False, "response_time_ms": 0}
    try:
        start = time.time()
        resp = _head(url)
        result["response_time_ms"] = int((time.time() - start) * 1000)
        result["server"] = resp.headers.get("Server", "").lower()
        # Security headers check
        security_headers = ["strict-transport-security", "x-content-type-options",
                           "x-frame-options", "content-security-policy"]
        found = sum(1 for h in security_headers if h in resp.headers)
        result["has_security_headers"] = found >= 2
    except Exception:
        result["response_time_ms"] = REQUEST_TIMEOUT * 1000
    return result


def check_ssl(url):
    """Check if SSL certificate is valid."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(5)
            s.connect((hostname, 443))
        return True
    except Exception:
        return False


def fetch_page(url):
    """Fetch full page HTML for analysis."""
    try:
        resp = _get(url)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return ""


def check_robots_txt(url):
    """Check robots.txt for structure/complexity."""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        resp = _get(robots_url, timeout=5)
        if resp.status_code == 200 and "user-agent" in resp.text.lower():
            lines = [l for l in resp.text.splitlines() if l.strip() and not l.startswith("#")]
            return len(lines)  # More lines = more organized
    except Exception:
        pass
    return 0


def check_mobile_viewport(soup):
    """Check for mobile viewport meta tag."""
    viewport = soup.find("meta", attrs={"name": "viewport"})
    return viewport is not None


def check_schema_org(soup):
    """Check for Schema.org structured data."""
    # JSON-LD
    json_ld = soup.find("script", attrs={"type": "application/ld+json"})
    if json_ld:
        return True
    # Microdata
    if soup.find(attrs={"itemtype": re.compile(r"schema\.org", re.I)}):
        return True
    return False


def check_open_graph(soup):
    """Check for Open Graph meta tags."""
    og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:", re.I)})
    return len(og_tags) >= 2


def check_chat_widget(soup, html):
    """Detect chat widget scripts."""
    chat_providers = [
        "tidio", "intercom", "drift", "livechat", "zendesk",
        "crisp", "tawk", "hubspot", "freshchat", "olark",
        "chatwoot", "smartsupp", "liveperson", "purechat"
    ]
    html_lower = html.lower()
    for provider in chat_providers:
        if provider in html_lower:
            return True
    return False


def check_booking_integration(soup, html):
    """Detect booking/scheduling integrations."""
    booking_signals = [
        "calendly", "acuity", "simplybook", "booksy", "setmore",
        "square.site/book", "appointlet", "youcanbook", "cal.com",
        "hubspot.com/meetings", "book-now", "book-online",
        "online-booking", "schedule-appointment"
    ]
    html_lower = html.lower()
    for signal in booking_signals:
        if signal in html_lower:
            return True
    return False


def check_analytics(soup, html):
    """Detect Google Analytics / Tag Manager."""
    analytics_signals = [
        "google-analytics.com", "googletagmanager.com",
        "gtag(", "ga('create'", "UA-", "G-", "GTM-",
        "analytics.js", "gtag.js"
    ]
    html_lower = html.lower()
    for signal in analytics_signals:
        if signal.lower() in html_lower:
            return True
    return False


def check_contact_form(soup):
    """Detect contact forms."""
    forms = soup.find_all("form")
    for form in forms:
        form_text = form.get_text().lower()
        form_html = str(form).lower()
        contact_signals = ["email", "message", "contact", "name", "phone", "submit", "send"]
        if sum(1 for s in contact_signals if s in form_text or s in form_html) >= 2:
            return True
    return False


def check_social_links(soup):
    """Detect social media links and return which ones are missing."""
    social_patterns = {
        "facebook": re.compile(r"facebook\.com/|fb\.com/", re.I),
        "instagram": re.compile(r"instagram\.com/", re.I),
        "twitter": re.compile(r"twitter\.com/|x\.com/", re.I),
        "linkedin": re.compile(r"linkedin\.com/", re.I),
    }
    found = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        for platform, pattern in social_patterns.items():
            if pattern.search(href):
                found.add(platform)
    return found


def detect_cms(soup, html, server_header):
    """Detect CMS from HTML patterns and headers."""
    html_lower = html.lower()

    if "wp-content" in html_lower or "wordpress" in html_lower:
        return "wordpress"
    if "wix.com" in html_lower or "wixsite" in html_lower:
        return "wix"
    if "squarespace" in html_lower:
        return "squarespace"
    if "shopify" in html_lower:
        return "shopify"
    if "webflow" in html_lower:
        return "webflow"
    if "joomla" in html_lower:
        return "joomla"
    if "drupal" in html_lower:
        return "drupal"
    if "weebly" in html_lower:
        return "weebly"
    if "godaddy" in html_lower:
        return "godaddy"
    return "custom/unknown"


# ─── FREE TOOLS: WHOIS, DNS MX, WAYBACK ─────────────────────────────────────

def check_domain_age(url):
    """Check domain age using python-whois. Returns years since registration."""
    if not WHOIS_AVAILABLE:
        return None
    try:
        parsed = urlparse(url)
        domain = parsed.hostname
        if not domain:
            return None
        w = whois.whois(domain)
        creation = w.creation_date
        if isinstance(creation, list):
            creation = creation[0]
        if creation:
            age_years = (datetime.now() - creation).days / 365.25
            return round(age_years, 1)
    except Exception:
        pass
    return None


def check_mx_records(url):
    """Check MX records to determine email provider. Free email = small business signal."""
    if not DNS_AVAILABLE:
        return {"provider": "unknown", "is_free_email": False}
    try:
        parsed = urlparse(url)
        domain = parsed.hostname
        if not domain:
            return {"provider": "unknown", "is_free_email": False}
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        answers = dns.resolver.resolve(domain, 'MX')
        mx_hosts = [str(r.exchange).lower() for r in answers]
        mx_str = " ".join(mx_hosts)

        # Detect free/generic email providers
        free_providers = ["google", "gmail", "outlook", "hotmail", "yahoo", "zoho"]
        for provider in free_providers:
            if provider in mx_str:
                return {"provider": provider, "is_free_email": True}
        # Custom email = more professional
        return {"provider": "custom", "is_free_email": False}
    except Exception:
        return {"provider": "unknown", "is_free_email": False}


def check_wayback_staleness(url):
    """Check Wayback Machine for last snapshot date. Stale site = opportunity."""
    try:
        api_url = f"https://archive.org/wayback/available?url={url}"
        resp = _get(api_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            snapshot = data.get("archived_snapshots", {}).get("closest", {})
            if snapshot:
                ts = snapshot.get("timestamp", "")
                if ts and len(ts) >= 8:
                    snap_date = datetime.strptime(ts[:8], "%Y%m%d")
                    days_since = (datetime.now() - snap_date).days
                    return days_since
    except Exception:
        pass
    return None


# ─── SCORING ALGORITHM ───────────────────────────────────────────────────────

def calculate_pain_score(checks):
    """
    Calculate pain score 1-10 based on detected issues.
    Higher score = more pain points = better lead for us.

    Weights:
    - Missing chatbot: 2 points (high value service we can sell)
    - Missing booking: 2 points (high value service)
    - No mobile viewport: 1.5 points (critical in 2024)
    - No analytics: 1 point
    - No schema.org: 0.5 points
    - No open graph: 0.5 points
    - Missing social links: 0.5 per missing (max 1.5)
    - No contact form: 1 point
    - Slow response: 0.5 points
    - No SSL: 1 point
    - No security headers: 0.5 points
    - Old server tech: 0.5 points
    - Simple robots.txt: 0.5 points
    """
    score = 0
    pain_points = []

    # Missing chatbot (weight: 2)
    if not checks.get("has_chat_widget"):
        score += 2
        pain_points.append("No chat widget detected")

    # Missing booking (weight: 2)
    if not checks.get("has_booking"):
        score += 2
        pain_points.append("No online booking system")

    # No mobile viewport (weight: 1.5)
    if not checks.get("has_mobile_viewport"):
        score += 1.5
        pain_points.append("Missing mobile viewport (not mobile-ready)")

    # No analytics (weight: 1)
    if not checks.get("has_analytics"):
        score += 1
        pain_points.append("No Google Analytics/Tag Manager")

    # No schema.org (weight: 0.5)
    if not checks.get("has_schema"):
        score += 0.5
        pain_points.append("No structured data (Schema.org)")

    # No open graph (weight: 0.5)
    if not checks.get("has_og_tags"):
        score += 0.5
        pain_points.append("No Open Graph tags (poor social sharing)")

    # Missing social links (weight: 0.5 each, max 1.5)
    missing_socials = checks.get("missing_socials", [])
    if missing_socials:
        social_penalty = min(1.5, len(missing_socials) * 0.5)
        score += social_penalty
        pain_points.append(f"Missing social links: {', '.join(missing_socials[:3])}")

    # No contact form (weight: 1)
    if not checks.get("has_contact_form"):
        score += 1
        pain_points.append("No contact form detected")

    # Slow response (weight: 0.5)
    if checks.get("response_time_ms", 0) > 3000:
        score += 0.5
        pain_points.append(f"Slow response ({checks['response_time_ms']}ms)")

    # No SSL (weight: 1)
    if not checks.get("has_ssl"):
        score += 1
        pain_points.append("No valid SSL certificate")

    # No security headers (weight: 0.5)
    if not checks.get("has_security_headers"):
        score += 0.5
        pain_points.append("Missing security headers")

    # Old server tech (weight: 0.5)
    server = checks.get("server", "")
    if server and any(old in server for old in ["apache/2.2", "apache/2.0", "iis/6", "iis/7"]):
        score += 0.5
        pain_points.append(f"Outdated server: {server}")

    # Simple/missing robots.txt (weight: 0.5)
    if checks.get("robots_lines", 0) < 3:
        score += 0.5
        pain_points.append("No/minimal robots.txt")

    # Free email provider (weight: 0.5)
    if checks.get("is_free_email"):
        score += 0.5
        pain_points.append(f"Uses free email ({checks.get('email_provider', 'gmail')})")

    # Domain age + basic site = stale business (weight: 0.5)
    domain_age = checks.get("domain_age_years")
    if domain_age and domain_age > 5 and not checks.get("has_schema") and not checks.get("has_chat_widget"):
        score += 0.5
        pain_points.append(f"Domain {domain_age:.0f}yrs old but no modern features")

    # Wayback staleness — site unchanged 1+ year (weight: 0.5)
    wayback_days = checks.get("wayback_days_since_change")
    if wayback_days and wayback_days > 365:
        score += 0.5
        pain_points.append(f"Site unchanged for {wayback_days // 30} months (Wayback)")

    # Normalize to 1-10 scale (max raw score is ~16)
    normalized = max(1, min(10, round(score * 10 / 16)))

    return normalized, pain_points


# ─── MAIN SCORING FUNCTION ───────────────────────────────────────────────────

def score_lead(url):
    """
    Score a single lead URL. Returns dict with pain_score and details.
    """
    url = normalize_url(url)
    if not url:
        return {"pain_score": 0, "pain_points": ["Invalid URL"], "checks": {}}

    checks = {}

    # 1. HTTP Headers + Response Time
    header_info = check_headers(url)
    checks["server"] = header_info["server"]
    checks["has_security_headers"] = header_info["has_security_headers"]
    checks["response_time_ms"] = header_info["response_time_ms"]

    # 2. SSL Check
    checks["has_ssl"] = check_ssl(url)

    # 3. Fetch page for HTML analysis
    html = fetch_page(url)
    if not html:
        # If we can't fetch the page, give a moderate score
        return {
            "pain_score": 5,
            "pain_points": ["Could not fetch website (may be down or blocking)"],
            "checks": checks
        }

    soup = BeautifulSoup(html, "html.parser")

    # 4. robots.txt
    checks["robots_lines"] = check_robots_txt(url)

    # 5. CMS Detection
    checks["cms"] = detect_cms(soup, html, checks["server"])

    # 6. Mobile Viewport
    checks["has_mobile_viewport"] = check_mobile_viewport(soup)

    # 7. Schema.org
    checks["has_schema"] = check_schema_org(soup)

    # 8. Open Graph
    checks["has_og_tags"] = check_open_graph(soup)

    # 9. Chat Widget
    checks["has_chat_widget"] = check_chat_widget(soup, html)

    # 10. Booking Integration
    checks["has_booking"] = check_booking_integration(soup, html)

    # 11. Analytics
    checks["has_analytics"] = check_analytics(soup, html)

    # 12. Contact Form
    checks["has_contact_form"] = check_contact_form(soup)

    # 13. Social Links
    all_socials = {"facebook", "instagram", "twitter", "linkedin"}
    found_socials = check_social_links(soup)
    checks["found_socials"] = list(found_socials)
    checks["missing_socials"] = list(all_socials - found_socials)

    # 14. Domain Age (whois)
    checks["domain_age_years"] = check_domain_age(url)

    # 15. Email Provider (DNS MX)
    mx_info = check_mx_records(url)
    checks["email_provider"] = mx_info["provider"]
    checks["is_free_email"] = mx_info["is_free_email"]

    # 16. Wayback Machine Staleness
    checks["wayback_days_since_change"] = check_wayback_staleness(url)

    # Calculate final score
    pain_score, pain_points = calculate_pain_score(checks)

    return {
        "pain_score": pain_score,
        "pain_points": pain_points,
        "checks": checks
    }


# ─── BATCH PROCESSING ────────────────────────────────────────────────────────

def process_leads(input_csv="leads.csv", output_csv="pain_scored_leads.csv"):
    """Process all leads from CSV and output scored results."""
    if not os.path.exists(input_csv):
        print(f"ERROR: {input_csv} not found. Run Find Leads first.")
        sys.exit(1)

    df = pd.read_csv(input_csv)
    if len(df) == 0:
        print("ERROR: No leads found in CSV.")
        sys.exit(1)

    total = len(df)
    print(f"PRE-SCORING {total} leads with 13 pain-point checks...")
    print(f"Workers: {MAX_WORKERS} | Timeout: {REQUEST_TIMEOUT}s per site")
    print("─" * 50)

    results = [None] * total
    completed = 0

    def score_row(idx, row):
        url = str(row.get("Website URL", "")).strip()
        name = str(row.get("Company Name", "Unknown"))
        if not url:
            return idx, {"pain_score": 0, "pain_points": ["No URL"], "checks": {}}
        result = score_lead(url)
        return idx, result

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(score_row, i, row): i for i, row in df.iterrows()}

        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result
            completed += 1
            name = str(df.iloc[idx].get("Company Name", "Unknown"))
            score = result["pain_score"]
            top_pain = result["pain_points"][0] if result["pain_points"] else "None"
            print(f"  [{completed}/{total}] {name[:35]:35s} → Pain Score: {score}/10 | {top_pain}")

    # Build output DataFrame
    df["Pain Score"] = [r["pain_score"] for r in results]
    df["Pain Points"] = [" | ".join(r["pain_points"]) for r in results]
    df["Has Chatbot"] = ["Yes" if r["checks"].get("has_chat_widget") else "No" for r in results]
    df["Has Booking"] = ["Yes" if r["checks"].get("has_booking") else "No" for r in results]
    df["Has Mobile"] = ["Yes" if r["checks"].get("has_mobile_viewport") else "No" for r in results]
    df["Has Analytics"] = ["Yes" if r["checks"].get("has_analytics") else "No" for r in results]
    df["Has Schema"] = ["Yes" if r["checks"].get("has_schema") else "No" for r in results]
    df["CMS Detected"] = [r["checks"].get("cms", "unknown") for r in results]
    df["Response Time (ms)"] = [r["checks"].get("response_time_ms", 0) for r in results]
    df["Domain Age (yrs)"] = [r["checks"].get("domain_age_years", "") for r in results]
    df["Email Provider"] = [r["checks"].get("email_provider", "") for r in results]
    df["Wayback Stale (days)"] = [r["checks"].get("wayback_days_since_change", "") for r in results]

    # Sort by pain score descending (best leads first)
    df = df.sort_values("Pain Score", ascending=False).reset_index(drop=True)

    df.to_csv(output_csv, index=False)

    print("─" * 50)
    high = len(df[df["Pain Score"] >= 7])
    medium = len(df[(df["Pain Score"] >= 4) & (df["Pain Score"] < 7)])
    low = len(df[df["Pain Score"] < 4])
    print(f"DONE! Scored {total} leads → {output_csv}")
    print(f"  🔥 High pain (7-10): {high} leads — GREAT prospects")
    print(f"  ⚡ Medium pain (4-6): {medium} leads — Worth checking")
    print(f"  ❄️  Low pain (1-3):   {low} leads — Low priority")
    print(f"\nRecommendation: Focus Playwright + Gemini on the {high} high-pain leads.")


if __name__ == "__main__":
    process_leads()
