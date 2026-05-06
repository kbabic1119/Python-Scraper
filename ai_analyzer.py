import pandas as pd
import requests
import os
import time
import json

JUNK_EMAIL_PATTERNS = [
    'noreply', 'no-reply', 'privacy', 'gdpr', 'legal', 'webmaster',
    'postmaster', 'bounce', 'unsubscribe', 'newsletter', 'cookie',
    'compliance', 'security@', 'abuse@', 'admin@',
]

def analyze_batch(api_key, batch_data):
    """Deep business intelligence extraction with automation scoring."""

    prompt = """You are an expert lead generation and high-ticket automation consultant.
Analyze each company's website data (which includes content from homepage, about, and services pages) and extract deep business intelligence.

"""
    for item in batch_data:
        prompt += f"=== COMPANY: {item['Company Name']} ===\n"
        prompt += f"Website Data: {str(item['Website Text'])[:7000]}\n\n"

    prompt += """
For EACH company above, extract the following and return as JSON:

{
  "Company Name": {
    "automation_score": <integer 1-10, how urgently this business needs automation>,
    "score_reason": "<one sentence why you gave this score>",
    "pain_points": "<specific operational problems detected from website analysis>",
    "automation_opportunities": "<concrete AI/automation solutions you could sell them>",
    "tech_stack": "<likely tech they use e.g. WordPress, Wix, HubSpot, or 'Legacy System'>",
    "business_maturity": "<one of: startup/growing/established>",
    "outreach_subject": "<compelling 3-5 word email subject line>",
    "outreach_email_draft": "<a short, punchy 3-sentence cold email that references a specific detail found in their text>",
    "outreach_angle": "<one powerful opening line for cold outreach>"
  }
}

Scoring guide:
- 8-10: Manual booking, no chatbot, outdated design, large service menu (High potential)
- 5-7: Modern site but lacks advanced AI tools or CRM integration
- 1-4: Already well-automated or small boutique not worth automating

Return ONLY valid JSON. Keys must be exact company names.
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2}
    }

    base_delay = 10
    for attempt in range(4):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=90)

            if response.status_code == 429:
                wait = base_delay * (attempt + 1)
                print(f"    Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                base_delay *= 2
                continue

            response.raise_for_status()
            result = response.json()

            if 'candidates' not in result or not result['candidates']:
                print("    Warning: Empty response from Gemini.")
                return {}

            raw = result['candidates'][0]['content']['parts'][0]['text'].strip()

            # Strip markdown fences
            if raw.startswith("```"):
                lines = raw.split('\n')
                raw = '\n'.join(lines[1:-1]) if lines[-1] == '```' else '\n'.join(lines[1:])
            raw = raw.strip()

            return json.loads(raw)

        except json.JSONDecodeError as e:
            print(f"    JSON parse error on attempt {attempt+1}: {e}")
            return {}
        except Exception as e:
            print(f"    Attempt {attempt+1} failed: {e}")
            if attempt < 3:
                time.sleep(base_delay)
                base_delay *= 2

    return {}


def main():
    input_file  = "enriched_leads.csv"
    output_file = "deep_extracted_leads.csv"

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set.")
        return

    if not os.path.exists(input_file):
        print(f"ERROR: {input_file} not found. Run deep_diver.py first.")
        return

    df = pd.read_csv(input_file)
    # Only process leads that were successfully scraped
    df_valid = df[df['Status'] == 'Success'].copy()
    df_failed = df[df['Status'] != 'Success'].copy()

    total = len(df_valid)
    print(f"Starting AI Deep Analysis for {total} valid leads ({len(df_failed)} skipped — no website data)...")

    batch_size = 5  # Smaller batches = better JSON accuracy
    batches = [df_valid.iloc[i:i+batch_size] for i in range(0, len(df_valid), batch_size)]

    final_results = []

    for i, batch_df in enumerate(batches):
        print(f"\nBatch {i+1}/{len(batches)} ({len(batch_df)} leads)...")

        batch_data = [
            {'Company Name': str(row.get('Company Name', 'Unknown')),
             'Website Text': str(row.get('Website Text', ''))}
            for _, row in batch_df.iterrows()
        ]

        extraction = analyze_batch(api_key, batch_data)

        # Handle list response (fallback)
        if isinstance(extraction, list):
            tmp = {}
            for item in extraction:
                key = item.get('Company Name') or item.get('company_name') or ''
                if key:
                    tmp[str(key)] = item
            extraction = tmp

        for _, row in batch_df.iterrows():
            name = str(row.get('Company Name', ''))
            data = extraction.get(name, {})

            # Fuzzy match if exact key not found
            if not data:
                for key in extraction:
                    if name.lower()[:20] in key.lower() or key.lower()[:20] in name.lower():
                        data = extraction[key]
                        break

            new_row = row.to_dict()
            new_row['Automation Score'] = data.get('automation_score', 'N/A')
            new_row['Score Reason']     = data.get('score_reason', 'N/A')
            new_row['Pain Points']      = data.get('pain_points', 'N/A')
            new_row['Opportunities']    = data.get('automation_opportunities', 'N/A')
            new_row['Decision Maker']   = data.get('decision_maker', 'N/A')
            new_row['Biz Maturity']     = data.get('business_maturity', 'N/A')
            new_row['Outreach Angle']   = data.get('outreach_angle', 'N/A')
            new_row['outreach_subject'] = data.get('outreach_subject', 'N/A')
            new_row['outreach_email_draft'] = data.get('outreach_email_draft', 'N/A')
            new_row['tech_stack']       = data.get('tech_stack', 'N/A')

            score = new_row['Automation Score']
            print(f"  ✓ {name[:45]} → Score: {score}/10")
            final_results.append(new_row)

        print(f"  Batch {i+1} done. Waiting 4s...")
        time.sleep(4)

    # Add failed rows (no website data) without AI fields
    for _, row in df_failed.iterrows():
        new_row = row.to_dict()
        for field in ['Automation Score','Score Reason','Pain Points','Opportunities','Decision Maker','Biz Maturity','Outreach Angle', 'outreach_subject', 'outreach_email_draft', 'tech_stack']:
            new_row[field] = 'N/A'
        final_results.append(new_row)

    result_df = pd.DataFrame(final_results)

    # Sort by automation score descending (best leads first)
    def safe_score(x):
        try: return int(x)
        except: return 0
    result_df['_score_sort'] = result_df['Automation Score'].apply(safe_score)
    result_df = result_df.sort_values('_score_sort', ascending=False).drop(columns=['_score_sort'])

    result_df.to_csv(output_file, index=False)
    print(f"\nDone! {len(final_results)} leads saved to {output_file}")
    print(f"Top lead: {result_df.iloc[0]['Company Name']} — Score: {result_df.iloc[0]['Automation Score']}/10")


if __name__ == "__main__":
    main()
