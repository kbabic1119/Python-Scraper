import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import os
import time
import concurrent.futures

# ── Junk patterns to filter out ──────────────────────────────────────────────
JUNK_EMAIL_PATTERNS = [
    'noreply', 'no-reply', 'donotreply', 'privacy', 'gdpr', 'legal',
    'webmaster', 'postmaster', 'mailer', 'bounce', 'unsubscribe',
    'admin@', 'seo@', 'newsletter', 'notifications@', 'alerts@',
    'cookie', 'compliance', 'security@', 'abuse@', 'hostmaster',
]

JUNK_SOCIAL_PATTERNS = [
    'sharer', 'share?', 'login', 'signup', 'intent/tweet',
    'dialog/feed', 'addthis', 'plusone', 'pinterest.com/pin/create',
]

def is_junk_email(email):
    email_lower = email.lower()
    return any(p in email_lower for p in JUNK_EMAIL_PATTERNS)

def score_email(email, site_domain=""):
    """Score emails — prefer domain-matching ones."""
    if is_junk_email(email):
        return -1
    if site_domain and site_domain in email:
        return 10  # Same domain = best
    if email.startswith(('info@', 'contact@', 'hello@', 'hi@', 'sales@', 'enquiries@')):
        return 7
    return 5

def extract_emails(html_text, site_url=""):
    """Extract and rank emails, returning only the best 2."""
    email_pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
    raw_emails = list(set(re.findall(email_pattern, html_text)))

    # Extract domain from site URL
    domain = ""
    try:
        from urllib.parse import urlparse
        domain = urlparse(site_url).netloc.replace("www.", "")
    except:
        pass

    scored = []
    for e in raw_emails:
        s = score_email(e, domain)
        if s >= 0:
            scored.append((s, e))

    scored.sort(reverse=True)
    return [e for _, e in scored[:2]]  # Return best 2 only


def extract_phones(text):
    """Extract phone numbers — strict filtering to avoid prices/zip codes."""
    # Match international and local formats
    phone_pattern = r'(?<!\d)(\+?[\d\s\-\(\)\.]{7,18})(?!\d)'
    candidates = re.findall(phone_pattern, text)

    cleaned = []
    for p in candidates:
        digits_only = re.sub(r'\D', '', p)
        # Must have 7-15 digits (not prices, zip codes, years)
        if 7 <= len(digits_only) <= 15:
            # Skip obvious years (1900-2099) and short local codes
            if re.match(r'^(19|20)\d{2}$', digits_only):
                continue
            cleaned.append(p.strip())

    # Deduplicate and keep best 2
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
    socials = {'FB': '', 'LI': '', 'IG': ''}

    for a in soup.find_all('a', href=True):
        href = a['href']
        href_lower = href.lower()

        # Skip junk social URLs
        if any(j in href_lower for j in JUNK_SOCIAL_PATTERNS):
            continue

        if 'facebook.com/' in href_lower and not socials['FB']:
            # Must have a real page path (not just facebook.com)
            if len(href.split('facebook.com/')[1].strip('/')) > 2:
                socials['FB'] = href

        elif 'linkedin.com/company' in href_lower and not socials['LI']:
            socials['LI'] = href

        elif 'instagram.com/' in href_lower and not socials['IG']:
            if len(href.split('instagram.com/')[1].strip('/')) > 2:
                socials['IG'] = href

    return socials


def find_subpages(soup, base_url):
    """Find 3 most relevant subpages to crawl."""
    links = []
    keywords = ['about', 'contact', 'services', 'team', 'staff', 'pricing', 'offer']
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Convert relative to absolute
        if href.startswith('/'):
            from urllib.parse import urljoin
            href = urljoin(base_url, href)
        
        if base_url in href and href != base_url:
            href_lower = href.lower()
            # Score the link relevance
            score = sum(1 for k in keywords if k in href_lower)
            if score > 0:
                links.append((score, href))
    
    # Sort by relevance and take top 3
    links.sort(reverse=True)
    unique_links = []
    seen = {base_url}
    for _, l in links:
        if l not in seen:
            unique_links.append(l)
            seen.add(l)
        if len(unique_links) >= 3: break
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
        
        # Extract initial data
        homepage_text = soup.get_text(separator=' ', strip=True)
        emails = extract_emails(response.text, url)
        phones = extract_phones(homepage_text)
        socials = extract_socials(soup)
        
        # 2. Find and crawl subpages
        full_text = homepage_text
        subpages = find_subpages(soup, url)
        for sub in subpages:
            try:
                sub_res = requests.get(sub, headers=headers, timeout=7)
                if sub_res.status_code == 200:
                    sub_soup = BeautifulSoup(sub_res.text, 'html.parser')
                    sub_text = sub_soup.get_text(separator=' ', strip=True)
                    full_text += " " + sub_text
                    
                    # Extract more emails/phones from subpages
                    emails.extend(extract_emails(sub_res.text, url))
                    phones.extend(extract_phones(sub_text))
            except:
                continue

        # Deduplicate and clean up
        emails = list(dict.fromkeys(emails))[:3]
        phones = list(dict.fromkeys(phones))[:3]

        return {
            'Website Text': full_text[:8000], # Significantly more context for Gemini 3
            'Emails':  ", ".join(emails),
            'Phones':  ", ".join(phones),
            'FB':      socials['FB'],
            'LI':      socials['LI'],
            'IG':      socials['IG'],
            'Status':  'Success (Deep Crawl)'
        }

    except Exception as e:
        return {'Website Text': '', 'Emails': '', 'Phones': '', 'FB': '', 'LI': '', 'IG': '', 'Status': f'Failed: {str(e)[:60]}'}


def process_row(index, row, total):
    url     = str(row.get('Website URL', ''))
    company = str(row.get('Company Name', 'Unknown'))
    safe_company = company.encode('ascii', 'ignore').decode('ascii')
    print(f"[{index+1}/{total}] {safe_company[:50]} — {url[:60]}")

    if not url or url == 'nan':
        print(f"  Skipping: no URL")
        return {**row.to_dict(), 'Website Text': '', 'Emails': '', 'Phones': '',
                'FB': '', 'LI': '', 'IG': '', 'Status': 'No URL'}

    data = scrape_website(url)
    print(f"  → {data['Status']} | Emails: {data['Emails'][:40]} | Phones: {data['Phones'][:30]}")
    return {**row.to_dict(), **data}


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

    # Drop duplicates by URL
    before = len(df)
    df = df.drop_duplicates(subset=['Website URL'])
    if len(df) < before:
        print(f"Removed {before - len(df)} duplicate URLs.")

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
    success = sum(1 for r in results if r.get('Status') == 'Success')
    print(f"\nDone in {elapsed:.1f}s — {success}/{total} scraped successfully.")

    pd.DataFrame(results).to_csv(output_file, index=False)
    print(f"Saved to {output_file}")


if __name__ == "__main__":
    main()
