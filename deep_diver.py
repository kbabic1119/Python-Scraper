import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment
import re
import os
import time
import concurrent.futures
from urllib.parse import urlparse, urljoin

# ── Junk patterns to filter out ──────────────────────────────────────────────
JUNK_EMAIL_PATTERNS = [
    'noreply', 'no-reply', 'donotreply', 'privacy', 'gdpr', 'legal',
    'webmaster', 'postmaster', 'mailer', 'bounce', 'unsubscribe',
    'admin@', 'seo@', 'newsletter', 'notifications@', 'alerts@',
    'cookie', 'compliance', 'security@', 'abuse@', 'hostmaster',
    'example.com', 'sentry.io', 'wixpress.com', 'placeholder',
]

JUNK_SOCIAL_PATTERNS = [
    'sharer', 'share?', 'login', 'signup', 'intent/tweet',
    'dialog/feed', 'addthis', 'plusone', 'pinterest.com/pin/create',
]

# Tags that contain non-content text (nav, footer, ads, scripts, etc.)
STRIP_TAGS = [
    'script', 'style', 'nav', 'footer', 'header', 'noscript',
    'iframe', 'svg', 'form', 'aside',
]

# Tags that likely contain the main content
CONTENT_TAGS = ['main', 'article', 'section', '[role="main"]']


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


def validate_url(url, timeout=5):
    """Quick HEAD request to verify a URL is reachable."""
    try:
        if not url or url == 'nan':
            return False
        if not url.startswith('http'):
            url = 'https://' + url
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                             headers={'User-Agent': 'Mozilla/5.0'})
        return resp.status_code < 400
    except Exception:
        return False


def is_junk_email(email):
    email_lower = email.lower()
    if any(p in email_lower for p in JUNK_EMAIL_PATTERNS):
        return True
    # Reject image filenames caught by regex (e.g., photo@2x.png)
    if re.search(r'@\d+x?\.(png|jpg|jpeg|gif|svg|webp)', email_lower):
        return True
    # Reject emails with file extensions
    if re.search(r'\.(png|jpg|jpeg|gif|svg|webp|css|js)$', email_lower):
        return True
    return False


def score_email(email, site_domain=""):
    """Score emails — prefer domain-matching ones."""
    if is_junk_email(email):
        return -1
    if site_domain and site_domain in email:
        return 10  # Same domain = best
    if email.startswith(('info@', 'contact@', 'hello@', 'hi@', 'sales@', 'enquiries@', 'office@')):
        return 7
    if email.startswith(('support@', 'help@', 'service@')):
        return 5
    return 3


def extract_emails(html_text, site_url=""):
    """Extract and rank emails, returning only the best 2."""
    email_pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    raw_emails = list(set(re.findall(email_pattern, html_text)))

    domain = ""
    try:
        domain = urlparse(site_url).netloc.replace("www.", "")
    except Exception:
        pass

    scored = []
    for e in raw_emails:
        s = score_email(e, domain)
        if s >= 0:
            scored.append((s, e))

    scored.sort(reverse=True)
    return [e for _, e in scored[:2]]


def extract_phones(text):
    """Extract phone numbers — strict filtering to avoid prices/zip codes."""
    phone_patterns = [
        r'\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{0,4}',
        r'\(\d{3}\)\s*\d{3}[\s\-]?\d{4}',
        r'\b\d{3}[\s\-\.]\d{3}[\s\-\.]\d{4}\b',
    ]

    candidates = []
    for pattern in phone_patterns:
        candidates.extend(re.findall(pattern, text))

    cleaned = []
    for p in candidates:
        digits_only = re.sub(r'\D', '', p)
        if len(digits_only) < 7 or len(digits_only) > 15:
            continue
        # Skip obvious years (1900-2099)
        if re.match(r'^(19|20)\d{2}$', digits_only):
            continue
        # Skip if it looks like a price (preceded by $ or currency)
        if re.search(r'\$\s*' + re.escape(p), text):
            continue
        cleaned.append(p.strip())

    # Deduplicate by digit content and keep best 2
    seen_digits = set()
    unique = []
    for p in cleaned:
        d = re.sub(r'\D', '', p)
        if d not in seen_digits:
            seen_digits.add(d)
            unique.append(p)

    return unique[:2]


def extract_socials(soup):
    """Extract social links, skipping share/login buttons."""
    socials = {'FB': '', 'LI': '', 'IG': '', 'TW': '', 'YT': ''}

    for a in soup.find_all('a', href=True):
        href = a['href']
        href_lower = href.lower()

        if any(j in href_lower for j in JUNK_SOCIAL_PATTERNS):
            continue

        if 'facebook.com/' in href_lower and not socials['FB']:
            parts = href.split('facebook.com/')
            if len(parts) > 1 and len(parts[1].strip('/')) > 2:
                socials['FB'] = href

        elif 'linkedin.com/company' in href_lower and not socials['LI']:
            socials['LI'] = href

        elif 'instagram.com/' in href_lower and not socials['IG']:
            parts = href.split('instagram.com/')
            if len(parts) > 1 and len(parts[1].strip('/')) > 2:
                socials['IG'] = href

        elif ('twitter.com/' in href_lower or 'x.com/' in href_lower) and not socials['TW']:
            socials['TW'] = href

        elif 'youtube.com/' in href_lower and not socials['YT']:
            socials['YT'] = href

    return socials


def clean_html_text(soup):
    """Extract meaningful text by stripping junk HTML elements.
    
    Removes nav, footer, scripts, styles, comments, and other non-content
    elements before extracting text. This typically reduces token count by ~60%.
    """
    # Work on a copy to avoid mutating the original
    clean_soup = BeautifulSoup(str(soup), 'html.parser')

    # Remove junk tags entirely
    for tag_name in STRIP_TAGS:
        for tag in clean_soup.find_all(tag_name):
            tag.decompose()

    # Remove HTML comments
    for comment in clean_soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Remove hidden elements
    for tag in clean_soup.find_all(style=re.compile(r'display\s*:\s*none')):
        tag.decompose()

    # Try to find main content area first
    main_content = None
    for selector in CONTENT_TAGS:
        if selector.startswith('['):
            main_content = clean_soup.find(attrs={"role": "main"})
        else:
            main_content = clean_soup.find(selector)
        if main_content:
            break

    if main_content:
        text = main_content.get_text(separator=' ', strip=True)
    else:
        text = clean_soup.get_text(separator=' ', strip=True)

    # Collapse multiple spaces/newlines
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_company_name_from_html(soup, url):
    """Extract company name from HTML metadata as fallback."""
    # Try og:site_name
    og_name = soup.find('meta', property='og:site_name')
    if og_name and og_name.get('content'):
        return og_name['content'].strip()

    # Try title tag
    title = soup.find('title')
    if title and title.string:
        name = title.string.strip()
        # Clean up common title patterns like "Company - Home" or "Company | About"
        for sep in [' | ', ' - ', ' — ', ' – ', ' :: ']:
            if sep in name:
                name = name.split(sep)[0].strip()
        return name

    return ""


def find_subpages(soup, base_url):
    """Find 3 most relevant subpages to crawl."""
    links = []
    keywords = ['about', 'contact', 'services', 'team', 'staff', 'pricing', 'offer']

    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('/'):
            href = urljoin(base_url, href)

        if base_url in href and href != base_url:
            href_lower = href.lower()
            score = sum(1 for k in keywords if k in href_lower)
            if score > 0:
                links.append((score, href))

    links.sort(reverse=True)
    unique_links = []
    seen = {base_url}
    for _, l in links:
        if l not in seen:
            unique_links.append(l)
            seen.add(l)
        if len(unique_links) >= 3:
            break
    return unique_links


def scrape_website(url, site_domain=""):
    """Visit website and its subpages for deep intelligence."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        if not url.startswith('http'):
            url = 'https://' + url

        # 1. Scrape Homepage
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract clean text (strips nav, footer, scripts, etc.)
        homepage_text = clean_html_text(soup)
        emails = extract_emails(response.text, url)
        phones = extract_phones(homepage_text)
        socials = extract_socials(soup)
        fallback_name = extract_company_name_from_html(soup, url)

        # 2. Find and crawl subpages
        full_text = homepage_text
        subpages = find_subpages(soup, url)
        for sub in subpages:
            try:
                sub_res = requests.get(sub, headers=headers, timeout=7)
                if sub_res.status_code == 200:
                    sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                    sub_text = clean_html_text(sub_soup)
                    full_text += " " + sub_text

                    emails.extend(extract_emails(sub_res.text, url))
                    phones.extend(extract_phones(sub_text))
            except Exception:
                continue

        # Deduplicate and clean up
        emails = list(dict.fromkeys(emails))[:3]
        phones = list(dict.fromkeys(phones))[:3]

        return {
            'Website Text': full_text[:5000],  # Reduced from 8000 — clean text is more dense
            'Emails':  ", ".join(emails),
            'Phones':  ", ".join(phones),
            'FB':      socials['FB'],
            'LI':      socials['LI'],
            'IG':      socials['IG'],
            'TW':      socials.get('TW', ''),
            'YT':      socials.get('YT', ''),
            'Fallback Name': fallback_name,
            'Status':  'Success (Deep Crawl)'
        }

    except requests.exceptions.Timeout:
        return _empty_result('Failed: Timeout')
    except requests.exceptions.ConnectionError:
        return _empty_result('Failed: Connection Error')
    except Exception as e:
        return _empty_result(f'Failed: {str(e)[:60]}')


def _empty_result(status):
    return {
        'Website Text': '', 'Emails': '', 'Phones': '',
        'FB': '', 'LI': '', 'IG': '', 'TW': '', 'YT': '',
        'Fallback Name': '', 'Status': status,
    }


def process_row(index, row, total):
    url     = str(row.get('Website URL', ''))
    company = str(row.get('Company Name', 'Unknown'))
    safe_company = company.encode('ascii', 'ignore').decode('ascii')
    print(f"[{index+1}/{total}] {safe_company[:50]} — {url[:60]}")

    if not url or url == 'nan':
        print(f"  Skipping: no URL")
        result = row.to_dict()
        result.update(_empty_result('No URL'))
        return result

    # Quick URL validation before full scrape
    if not validate_url(url):
        print(f"  Skipping: URL unreachable")
        result = row.to_dict()
        result.update(_empty_result('Failed: URL Unreachable'))
        return result

    data = scrape_website(url)

    # Use fallback company name if original looks bad
    if data.get('Fallback Name') and company in ('Unknown', '', 'nan'):
        data['Company Name'] = data['Fallback Name']

    print(f"  → {data['Status']} | Emails: {data['Emails'][:40]} | Phones: {data['Phones'][:30]}")
    result = row.to_dict()
    result.update(data)
    return result


def main():
    input_file  = "leads.csv"
    output_file = "enriched_leads.csv"

    if not os.path.exists(input_file):
        print(f"ERROR: {input_file} not found. Run lead_finder.py first.")
        return

    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)

    if "Website URL" not in df.columns:
        print("ERROR: 'Website URL' column not found.")
        return

    # Normalize URLs for better deduplication
    df['Website URL'] = df['Website URL'].apply(normalize_url)

    before = len(df)
    df = df.drop_duplicates(subset=['Website URL'])
    if len(df) < before:
        print(f"Removed {before - len(df)} duplicate URLs.")

    # Check for cached results — skip already-scraped URLs
    if os.path.exists(output_file):
        existing = pd.read_csv(output_file)
        existing_urls = set(existing['Website URL'].apply(normalize_url))
        new_df = df[~df['Website URL'].isin(existing_urls)]
        cached_count = len(df) - len(new_df)
        if cached_count > 0:
            print(f"Skipping {cached_count} already-scraped URLs (cached).")
        df = new_df
        if len(df) == 0:
            print("All URLs already scraped. Nothing to do.")
            return

    total = len(df)
    print(f"Starting scrape for {total} leads (20 concurrent threads)...")
    start = time.time()

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(process_row, i, row, total): i
            for i, (_, row) in enumerate(df.iterrows())
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                print(f"Thread error: {e}")

    elapsed = time.time() - start
    success = sum(1 for r in results if 'Success' in str(r.get('Status', '')))
    print(f"\nDone in {elapsed:.1f}s — {success}/{total} scraped successfully.")

    new_results_df = pd.DataFrame(results)

    # Merge with cached results if they exist
    if os.path.exists(output_file):
        existing = pd.read_csv(output_file)
        combined = pd.concat([existing, new_results_df], ignore_index=True)
        combined.to_csv(output_file, index=False)
        print(f"Appended {len(new_results_df)} new results. Total: {len(combined)}")
    else:
        new_results_df.to_csv(output_file, index=False)
        print(f"Saved {len(new_results_df)} results to {output_file}")


if __name__ == "__main__":
    main()
