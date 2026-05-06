import streamlit as st
import pandas as pd
import subprocess
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def safe_read_csv(path):
    """Read CSV safely — returns empty DataFrame if file is missing, empty, or corrupt."""
    try:
        if not os.path.exists(path): return pd.DataFrame()
        if os.path.getsize(path) == 0: return pd.DataFrame()
        df = pd.read_csv(path)
        return df if len(df.columns) > 0 else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

st.set_page_config(page_title="AI Lead Intelligence", page_icon="🤖", layout="wide")

# ─── CYBERPUNK AI THEME ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* Base */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #060912;
    color: #c9d4f0;
}
.main { background-color: #060912; }
.block-container { padding: 1.5rem 2rem; max-width: 1400px; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #080e1f;
    border-right: 1px solid #0e1f42;
}

/* Title glow */
h1 { 
    font-family: 'JetBrains Mono', monospace !important;
    color: #00d4ff !important;
    text-shadow: 0 0 20px rgba(0,212,255,0.5), 0 0 40px rgba(0,212,255,0.2);
    letter-spacing: 2px;
}
h3 { color: #a0b4e0 !important; }

/* Metric boxes */
.metric-box {
    background: linear-gradient(135deg, #0d1628 0%, #0a1220 100%);
    border: 1px solid #0e2a50;
    border-radius: 12px; padding: 18px 20px;
    text-align: center;
    box-shadow: 0 0 20px rgba(0,212,255,0.05), inset 0 1px 0 rgba(255,255,255,0.03);
    transition: all 0.3s ease;
}
.metric-box:hover { border-color: #00d4ff33; box-shadow: 0 0 30px rgba(0,212,255,0.1); }
.metric-box .num { font-family: 'JetBrains Mono', monospace; font-size: 2.4rem; font-weight: 700; color: #00d4ff; line-height: 1; }
.metric-box .lbl { font-size: 0.72rem; color: #4a6080; text-transform: uppercase; letter-spacing: 1.5px; margin-top: 4px; }

/* Pipeline step badges */
.step-badge {
    display: inline-block; padding: 3px 10px;
    border-radius: 20px; font-size: 0.68rem; font-weight: 600;
    font-family: 'JetBrains Mono', monospace; letter-spacing: 1px;
}
.step-found    { background: #0a2540; color: #00d4ff; border: 1px solid #00d4ff44; }
.step-scraped  { background: #0a2020; color: #00ffa3; border: 1px solid #00ffa344; }
.step-analyzed { background: #1a0a30; color: #bf7fff; border: 1px solid #bf7fff44; }

/* Lead Card */
.lead-card {
    background: linear-gradient(145deg, #0c1528 0%, #090e1c 100%);
    border: 1px solid #0e2040;
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 14px;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
}
.lead-card::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #00d4ff44, transparent);
}
.lead-card:hover {
    border-color: #00d4ff33;
    box-shadow: 0 4px 30px rgba(0,212,255,0.08);
    transform: translateY(-1px);
}
.lead-card .company { font-size: 1rem; font-weight: 700; color: #e0eaff; margin-bottom: 6px; }
.lead-card .url     { font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: #00d4ff; opacity: 0.8; }
.lead-card .divider { border: none; border-top: 1px solid #0e2040; margin: 10px 0; }
.lead-card .info-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.info-pill {
    display: inline-flex; align-items: center; gap: 5px;
    background: #0a1830; border: 1px solid #0e2540;
    border-radius: 6px; padding: 3px 9px;
    font-size: 0.72rem; color: #8aafd4;
    font-family: 'JetBrains Mono', monospace;
}
.info-pill.has-data { color: #00ffa3; border-color: #00ffa322; background: #001a10; }
.info-pill.social   { color: #bf7fff; border-color: #bf7fff22; background: #0f0020; }

/* Intel section inside card */
.intel-section { margin-top: 12px; }
.intel-row { margin: 6px 0; }
.intel-label { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1.5px; color: #4a6080; font-family: 'JetBrains Mono', monospace; }
.intel-value { font-size: 0.82rem; color: #c9d4f0; margin-top: 2px; line-height: 1.5; }
.intel-value.highlight { color: #00d4ff; }
.outreach-quote { font-style: italic; color: #7a9fc0; font-size: 0.8rem; border-left: 2px solid #00d4ff33; padding-left: 8px; margin-top: 4px; }

/* Status dot */
.status-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; }
.dot-ok   { background: #00ffa3; box-shadow: 0 0 6px #00ffa3; }
.dot-fail { background: #ff4466; box-shadow: 0 0 6px #ff4466; }
.dot-skip { background: #4a6080; }

/* Score Badge */
.score-badge {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700; font-size: 0.85rem;
    border-radius: 8px; padding: 4px 10px;
    display: inline-block;
}
.score-hot  { background:#001a08; color:#00ff88; border:1px solid #00ff88; box-shadow: 0 0 10px #00ff8866, 0 0 20px #00ff8833; }
.score-mid  { background:#1a1000; color:#ffb800; border:1px solid #ffb800; box-shadow: 0 0 10px #ffb80066, 0 0 20px #ffb80033; }
.score-low  { background:#1a0008; color:#ff4466; border:1px solid #ff4466; box-shadow: 0 0 10px #ff446666, 0 0 20px #ff446633; }
.score-none { background:#0a1020; color:#4a6080; border:1px solid #1a2a40; }

.stButton>button {
    border-radius: 8px; font-weight: 600; font-size: 0.85rem;
    transition: all 0.2s; border: 1px solid #0e2040;
    background: #0c1830; color: #8aafd4;
}
.stButton>button:hover { background: #0e2040; color: #00d4ff; border-color: #00d4ff44; }

/* Pulse Animation for Hot Leads */
@keyframes pulse-glow {
    0% { box-shadow: 0 0 10px #00ff8844; }
    50% { box-shadow: 0 0 25px #00ff8888, 0 0 45px #00ff8822; }
    100% { box-shadow: 0 0 10px #00ff8844; }
}
.pulse-hot {
    animation: pulse-glow 2s infinite ease-in-out;
    border-color: #00ff8866 !important;
}

/* Outreach Lab Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 15px; background-color: transparent; padding: 0;
}
.stTabs [data-baseweb="tab"] {
    height: 40px; background-color: #0a1220; border-radius: 8px 8px 0 0;
    border: 1px solid #0e2040; color: #4a6080; padding: 0 15px;
    font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; text-transform: uppercase;
}
.stTabs [aria-selected="true"] {
    background-color: #0c1c38 !important; color: #00d4ff !important;
    border-color: #00d4ff44 !important; border-bottom: 2px solid #00d4ff !important;
}

/* Primary button */
div[data-testid="column"]:last-child .stButton>button,
button[kind="primary"] {
    background: linear-gradient(135deg, #0040a0, #0060d0) !important;
    color: #ffffff !important; border-color: #0060d0 !important;
    box-shadow: 0 0 20px rgba(0,100,210,0.3);
}

/* Inputs */
.stTextInput>div>div>input, .stSelectbox>div>div {
    background: #0c1528 !important; border-color: #0e2040 !important;
    color: #c9d4f0 !important;
}
.stSlider [data-testid="stSlider"] { accent-color: #00d4ff; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background: #080e1f; border-bottom: 1px solid #0e2040; }
.stTabs [data-baseweb="tab"] { color: #4a6080 !important; }
.stTabs [aria-selected="true"] { color: #00d4ff !important; border-bottom: 2px solid #00d4ff !important; }

/* Download button */
.stDownloadButton>button { background: #001a10 !important; color: #00ffa3 !important; border-color: #00ffa344 !important; }

/* Code blocks (logs) */
.stCodeBlock { background: #050810 !important; border: 1px solid #0e2040; border-radius: 8px; }

/* Container borders */
[data-testid="stVerticalBlockBorderWrapper"] { border-color: #0e2040 !important; border-radius: 12px !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #060912; }
::-webkit-scrollbar-thumb { background: #0e2040; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #00d4ff44; }

/* Source toggle buttons */
.src-btn-row { display: flex; gap: 10px; margin-bottom: 12px; }
.src-btn {
    flex: 1; padding: 10px 6px; border-radius: 10px;
    text-align: center; font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem; font-weight: 600; cursor: pointer;
    border: 1px solid #0e2040; background: #0a1020; color: #4a6080;
    transition: all 0.2s;
}
.src-btn:hover { border-color: #00d4ff44; color: #00d4ff; }
.src-btn.active-gemini  { background:#001a30; color:#00d4ff; border-color:#00d4ff; box-shadow:0 0 14px #00d4ff44; }
.src-btn.active-maps    { background:#001a10; color:#00ffa3; border-color:#00ffa3; box-shadow:0 0 14px #00ffa344; }
.src-btn.active-ddg     { background:#1a1000; color:#ffb800; border-color:#ffb800; box-shadow:0 0 14px #ffb80044; }
.src-btn.active-serp    { background:#1a0030; color:#bf7fff; border-color:#bf7fff; box-shadow:0 0 14px #bf7fff44; }

/* Source description pill */
.src-desc {
    font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
    color: #4a7090; padding: 6px 12px; border-radius: 6px;
    background: #080e1f; border: 1px solid #0e2040; margin-bottom: 12px;
    display: block;
}
</style>
""", unsafe_allow_html=True)

# ─── HEADER ──────────────────────────────────────────────────────────────────
st.markdown("<h1>⬡ AI LEAD INTELLIGENCE ENGINE</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#4a6080; font-family:JetBrains Mono,monospace; font-size:0.78rem; letter-spacing:2px; margin-top:-10px;'>DEEP EXTRACTION SYSTEM v3.0 // GEMINI POWERED // AUTOMATION SCORING</p>", unsafe_allow_html=True)

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-family:JetBrains Mono,monospace;color:#00d4ff;font-size:0.8rem;letter-spacing:2px;'>// SYSTEM CONFIG</p>", unsafe_allow_html=True)
    gmaps_key  = st.text_input("Google Maps API Key", type="password", value=os.environ.get("GOOGLE_MAPS_API_KEY",""))
    gemini_key = st.text_input("Gemini API Key",      type="password", value=os.environ.get("GEMINI_API_KEY",""))

    if st.button("💾 Save Keys"):
        with open(".env","w") as f:
            f.write(f"GOOGLE_MAPS_API_KEY={gmaps_key}\nGEMINI_API_KEY={gemini_key}\n")
        st.success("Keys saved to .env")
        load_dotenv(override=True)

    st.markdown("---")
    st.markdown("<p style='font-family:JetBrains Mono,monospace;color:#00d4ff;font-size:0.8rem;letter-spacing:2px;'>// DATA STATUS</p>", unsafe_allow_html=True)
    for fname, label, color in [
        ("leads.csv",               "leads.csv",               "#00d4ff"),
        ("enriched_leads.csv",      "enriched_leads.csv",      "#00ffa3"),
        ("deep_extracted_leads.csv","deep_extracted_leads.csv","#bf7fff"),
    ]:
        _df = safe_read_csv(fname)
        if len(_df) > 0:
            st.markdown(f"<span class='status-dot dot-ok'></span><span style='color:{color};font-size:0.78rem;font-family:JetBrains Mono,monospace;'>{label}<br>&nbsp;&nbsp;&nbsp;&nbsp;{len(_df)} rows</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"<span class='status-dot dot-skip'></span><span style='color:#4a6080;font-size:0.78rem;font-family:JetBrains Mono,monospace;'>{label}<br>&nbsp;&nbsp;&nbsp;&nbsp;not found</span>", unsafe_allow_html=True)
        st.write("")

    st.markdown("---")
    st.markdown("<p style='font-family:JetBrains Mono,monospace;color:#ff4466;font-size:0.8rem;letter-spacing:2px;'>// RESET</p>", unsafe_allow_html=True)
    total_leads = len(safe_read_csv("leads.csv"))
    st.caption(f"Currently holding **{total_leads}** accumulated leads.")
    if st.button("🗑️ Clear ALL Data", use_container_width=True):
        for f in ["leads.csv","enriched_leads.csv","deep_extracted_leads.csv"]:
            if os.path.exists(f): os.remove(f)
        st.success("All data cleared.")
        st.rerun()
    if st.button("🗑️ Clear Leads Only", use_container_width=True):
        if os.path.exists("leads.csv"): os.remove("leads.csv")
        st.success("leads.csv cleared — you can start a fresh search.")
        st.rerun()

# ─── SOURCE CONFIG ───────────────────────────────────────────────────────────
SOURCE_CONFIG = {
    "gemini":      {"label": "🤖 Gemini AI",    "min": 5, "max": 200, "default": 50,  "cls": "active-gemini", "desc": "Uses Gemini 3 Flash to discover leads — no IP blocks, works globally, 200 leads/call."},
    "google_maps": {"label": "🗺 Google Maps",  "min": 5, "max": 20,  "default": 20,  "cls": "active-maps",   "desc": "Real verified local businesses with addresses. Hard limit: 20 results per API call."},
    "duckduckgo":  {"label": "🦆 DuckDuckGo",   "min": 5, "max": 100, "default": 30,  "cls": "active-ddg",    "desc": "Free web search — no API key needed. May hit rate limits depending on your IP."},
    "serpapi":     {"label": "🔎 SerpApi",       "min": 5, "max": 100, "default": 50,  "cls": "active-serp",   "desc": "Paid Google search API — most reliable. Requires a SerpApi key set in .env."},
}

if "search_source" not in st.session_state:
    st.session_state["search_source"] = "gemini"

# ─── PIPELINE CONTROL ────────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown("<p style='font-family:JetBrains Mono,monospace;color:#4a6080;font-size:0.75rem;letter-spacing:2px;'>// PIPELINE CONTROL</p>", unsafe_allow_html=True)

    # Query input
    search_query = st.text_input("Search Query", placeholder="e.g., HVAC companies Oslo Norway", label_visibility="collapsed")

    # Source toggle buttons
    st.markdown("<p style='font-family:JetBrains Mono,monospace;color:#4a6080;font-size:0.68rem;letter-spacing:1.5px;margin-bottom:6px;'>SELECT SOURCE</p>", unsafe_allow_html=True)
    btn_cols = st.columns(4)
    for i, (src_key, src_cfg) in enumerate(SOURCE_CONFIG.items()):
        with btn_cols[i]:
            is_active = st.session_state["search_source"] == src_key
            btn_style = "primary" if is_active else "secondary"
            if st.button(src_cfg["label"], key=f"src_{src_key}", use_container_width=True, type=btn_style if is_active else "secondary"):
                st.session_state["search_source"] = src_key
                st.rerun()

    search_source = st.session_state["search_source"]
    cfg = SOURCE_CONFIG[search_source]

    # Source description
    st.markdown(f"<span class='src-desc'>⚡ {cfg['desc']}</span>", unsafe_allow_html=True)

    # Smart slider — limits adjust per source
    lead_limit = st.slider(
        f"Leads to find (max {cfg['max']} for {cfg['label']})",
        min_value=cfg["min"],
        max_value=cfg["max"],
        value=min(cfg["default"], cfg["max"]),
        label_visibility="visible"
    )

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1: run_finder   = st.button("🔍 1. Find Leads",  use_container_width=True, help="Search for companies → leads.csv")
    with c2: run_diver    = st.button("🌐 2. Scrape Sites", use_container_width=True, help="Visit websites → enriched_leads.csv")
    with c3: run_analyzer = st.button("🧠 3. AI Analyze",   use_container_width=True, help="Gemini deep extraction → deep_extracted_leads.csv")
    with c4: run_full     = st.button("🚀 FULL PIPELINE",   use_container_width=True, type="primary")

# ─── ENV + HELPERS ───────────────────────────────────────────────────────────
env = os.environ.copy()
if gmaps_key:  env["GOOGLE_MAPS_API_KEY"] = gmaps_key
if gemini_key: env["GEMINI_API_KEY"]      = gemini_key
env["PYTHONUNBUFFERED"] = "1"

if "last_error" not in st.session_state: st.session_state["last_error"] = None

if st.session_state["last_error"]:
    col_e, col_btn = st.columns([5,1])
    with col_e:
        st.error(f"❌ **Error:** {st.session_state['last_error']}")
    with col_btn:
        if st.button("✕ Dismiss"):
            st.session_state["last_error"] = None
            st.rerun()

def run_and_stream(cmd, label):
    st.markdown(f"<p style='font-family:JetBrains Mono,monospace;color:#00d4ff;font-size:0.8rem;'>> {label}</p>", unsafe_allow_html=True)
    log_box = st.empty()
    log_lines = []
    try:
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="ignore", bufsize=1)
        for line in proc.stdout:
            s = line.strip()
            if s:
                log_lines.append(s)
                log_box.code("\n".join(log_lines[-20:]))
        proc.wait()
        if proc.returncode != 0:
            err = next((l for l in reversed(log_lines) if "ERROR" in l or "FAILED" in l), "Unknown error")
            st.session_state["last_error"] = err
            return False
        return True
    except Exception as e:
        st.session_state["last_error"] = str(e)
        return False

def clear_old_data():
    """Full wipe — used by Full Pipeline for a completely fresh start."""
    for f in ["leads.csv","enriched_leads.csv","deep_extracted_leads.csv"]:
        if os.path.exists(f): os.remove(f)

# ─── BUTTON ACTIONS ──────────────────────────────────────────────────────────
if run_full:
    if not search_query: st.error("Enter a search query first.")
    else:
        clear_old_data()
        st.session_state["last_error"] = None
        with st.status("🚀 Full Pipeline Running...", expanded=True) as status:
            ok1 = run_and_stream([sys.executable,"lead_finder.py","--query",search_query,"--source",search_source,"--limit",str(lead_limit)], "STEP 1 — FINDING LEADS")
            if ok1:
                ok2 = run_and_stream([sys.executable,"deep_diver.py"], "STEP 2 — SCRAPING WEBSITES")
                if ok2:
                    ok3 = run_and_stream([sys.executable,"ai_analyzer.py"], "STEP 3 — AI DEEP ANALYSIS")
                    if ok3:
                        status.update(label="✅ Pipeline Complete", state="complete")
                        st.toast("Intelligence ready!", icon="🎉")
        st.rerun()

elif run_finder:
    if not search_query: st.error("Enter a search query first.")
    else:
        # No clear — APPEND to existing leads
        st.session_state["last_error"] = None
        with st.status("Finding Leads...", expanded=True):
            run_and_stream([sys.executable,"lead_finder.py","--query",search_query,"--source",search_source,"--limit",str(lead_limit)], "FINDING LEADS")
        st.rerun()

elif run_diver:
    if not os.path.exists("leads.csv"): st.error("Run Find Leads first.")
    else:
        st.session_state["last_error"] = None
        with st.status("Scraping Websites...", expanded=True):
            run_and_stream([sys.executable,"deep_diver.py"], "SCRAPING WEBSITES")
        st.rerun()

elif run_analyzer:
    if not os.path.exists("enriched_leads.csv"): st.error("Run Scrape Sites first.")
    else:
        st.session_state["last_error"] = None
        with st.status("AI Analyzing...", expanded=True):
            run_and_stream([sys.executable,"ai_analyzer.py"], "AI DEEP EXTRACTION")
        st.rerun()

# ─── METRICS ROW ─────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
def get_count(fname): return len(safe_read_csv(fname))

with m1:
    n = get_count("leads.csv")
    st.markdown(f"<div class='metric-box'><div class='num'>{n}</div><div class='lbl'>🔍 Leads Found</div></div>", unsafe_allow_html=True)
with m2:
    n = get_count("enriched_leads.csv")
    st.markdown(f"<div class='metric-box'><div class='num'>{n}</div><div class='lbl'>🌐 Sites Scraped</div></div>", unsafe_allow_html=True)
with m3:
    n = get_count("deep_extracted_leads.csv")
    st.markdown(f"<div class='metric-box'><div class='num'>{n}</div><div class='lbl'>🧠 AI Analyzed</div></div>", unsafe_allow_html=True)
with m4:
    total    = get_count("leads.csv")
    analyzed = get_count("deep_extracted_leads.csv")
    pct = int((analyzed/total)*100) if total > 0 else 0
    st.markdown(f"<div class='metric-box'><div class='num'>{pct}%</div><div class='lbl'>⚡ Pipeline Complete</div></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ─── LOAD BEST AVAILABLE DATA ────────────────────────────────────────────────
df = None
data_label = ""

_deep = safe_read_csv("deep_extracted_leads.csv")
_enr  = safe_read_csv("enriched_leads.csv")
_raw  = safe_read_csv("leads.csv")

if len(_deep) > 0:
    df = _deep; data_label = "deep_extracted"
elif len(_enr) > 0:
    df = _enr;  data_label = "enriched"
elif len(_raw) > 0:
    df = _raw;  data_label = "raw"

# ─── RESULTS PANEL ───────────────────────────────────────────────────────────
if df is not None and len(df) > 0:

    # --- MARKET PULSE VISUALIZATION ---
    if data_label == "deep_extracted":
        st.markdown("<p style='font-family:JetBrains Mono,monospace;color:#00d4ff;font-size:0.8rem;letter-spacing:2px;'>// MARKET PULSE</p>", unsafe_allow_html=True)
        v1, v2 = st.columns([3, 2])
        with v1:
            # Score distribution chart
            counts = df['Automation Score'].value_counts().sort_index()
            # Ensure all scores 1-10 are present for better visual
            full_counts = pd.Series(0, index=range(1, 11)).add(counts, fill_value=0)
            st.bar_chart(full_counts, color="#00d4ff")
        with v2:
            # Market Heat Gauge
            avg_score = df['Automation Score'].astype(float).mean()
            hot_count = len(df[df['Automation Score'].astype(float) >= 8])
            st.markdown(f"""
            <div style='background:rgba(0,212,255,0.05); border:1px solid #0e2a50; border-radius:12px; padding:20px; text-align:center;'>
                <div style='font-size:0.7rem; color:#4a6080; letter-spacing:1px;'>MARKET TEMPERATURE</div>
                <div style='font-size:2.8rem; font-weight:700; color:{"#00ff88" if avg_score > 7 else "#ffb800"}; line-height:1;'>{avg_score:.1f}/10</div>
                <div style='margin-top:10px; font-size:0.8rem; color:#8aafd4;'>{hot_count} High-Potential Leads Detected</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # Header + download + search filter
    r1, r2, r3 = st.columns([2,2,1])
    with r1:
        badge_map = {
            "deep_extracted": "<span class='step-badge step-analyzed'>🧠 AI ANALYZED</span>",
            "enriched":       "<span class='step-badge step-scraped'>🌐 SCRAPED</span>",
            "raw":            "<span class='step-badge step-found'>🔍 RAW LEADS</span>",
        }
        st.markdown(f"### 📋 Lead Database &nbsp; {badge_map[data_label]}", unsafe_allow_html=True)
    with r2:
        filter_text = st.text_input("🔎 Filter leads", placeholder="Filter by name, URL...", label_visibility="collapsed")
    with r3:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        fname_map = {"deep_extracted":"deep_extracted_leads.csv","enriched":"enriched_leads.csv","raw":"leads.csv"}
        st.download_button("⬇️ Export CSV", data=csv_bytes, file_name=fname_map[data_label], mime="text/csv", use_container_width=True)

    # Apply filter
    if filter_text:
        mask = df.apply(lambda row: row.astype(str).str.contains(filter_text, case=False).any(), axis=1)
        df = df[mask]

    # ── CARD GRID ─────────────────────────────────────────────────────────
    def is_valid(v):
        return str(v).strip() not in ["", "N/A", "nan", "None", "NaN"]

    def score_class(score):
        try:
            s = int(score)
            if s >= 8: return "score-hot",  f"🔥 {s}/10"
            if s >= 5: return "score-mid",  f"⚡ {s}/10"
            return           "score-low",  f"❄ {s}/10"
        except:
            return "score-none", "· /10"

    cols_per_row = 3
    chunks = [df.iloc[i:i+cols_per_row] for i in range(0, len(df), cols_per_row)]

    for chunk in chunks:
        cols = st.columns(cols_per_row)
        for col, (_, lead) in zip(cols, chunk.iterrows()):
            with col:
                # ── Data extraction ──────────────────────────────────────
                name     = str(lead.get("Company Name", "Unknown"))
                url      = str(lead.get("Website URL", ""))
                email    = str(lead.get("Emails", ""))
                phone    = str(lead.get("Phones","") or lead.get("Phone Extracted",""))
                fb       = str(lead.get("FB","") or lead.get("FB Extracted",""))
                li       = str(lead.get("LI","") or lead.get("LI Extracted",""))
                ig       = str(lead.get("IG","") or lead.get("IG Extracted",""))
                score    = str(lead.get("Automation Score",""))
                reason   = str(lead.get("Score Reason",""))
                pain     = str(lead.get("Pain Points",""))
                opps     = str(lead.get("Opportunities",""))
                dm       = str(lead.get("Decision Maker","") or lead.get("Decision Makers",""))
                maturity = str(lead.get("Biz Maturity",""))
                outreach = str(lead.get("Outreach Angle",""))
                status   = str(lead.get("Status",""))

                has_ok  = "Success" in status or not is_valid(status)
                dot_cls = "dot-ok" if has_ok else "dot-fail"
                s_cls, s_label = score_class(score)
                url_href  = url if url.startswith("http") else f"https://{url}"
                url_clean = url.replace("https://","").replace("http://","")[:48]

                # ── Contact pills ─────────────────────────────────────────
                email_pills = ""
                if is_valid(email):
                    for e in str(email).split(",")[:2]:
                        e = e.strip()
                        if e:
                            email_pills += f"<a href='mailto:{e}' target='_blank' class='info-pill has-data' style='text-decoration:none;'>✉ {e[:30]}</a> "

                phone_pills = ""
                if is_valid(phone):
                    for p in str(phone).split(",")[:2]:
                        p = p.strip()
                        if p:
                            phone_pills += f"<a href='tel:{p.replace(' ','')}' class='info-pill has-data' style='text-decoration:none;'>📞 {p[:20]}</a> "

                fb_pill = f"<a href='{fb}' target='_blank' class='info-pill social' style='text-decoration:none;'>f&nbsp;Facebook</a>" if is_valid(fb) else ""
                li_pill = f"<a href='{li}' target='_blank' class='info-pill social' style='text-decoration:none;'>in LinkedIn</a>"  if is_valid(li) else ""
                ig_pill = f"<a href='{ig}' target='_blank' class='info-pill social' style='text-decoration:none;'>◎ Instagram</a>" if is_valid(ig) else ""

                all_pills = email_pills + phone_pills + fb_pill + li_pill + ig_pill
                if not all_pills:
                    all_pills = "<span style='color:#2a3a5a;font-size:0.7rem;font-family:JetBrains Mono,monospace;'>NO CONTACT DATA — Run Scrape Sites</span>"

                # ── Intel rows ────────────────────────────────────────────
                def irow(label, value, cls=""):
                    if not is_valid(value): return ""
                    return f"<div class='intel-row'><div class='intel-label'>{label}</div><div class='intel-value {cls}'>{value}</div></div>"

                intel_html  = irow("🏗️ TECH STACK",              lead.get("tech_stack", ""), "highlight")
                intel_html += irow("👤 DECISION MAKER",          dm)
                intel_html += irow("📊 BUSINESS MATURITY",       maturity)
                intel_html += irow("⚠️ PAIN POINTS",             pain)
                intel_html += irow("💡 OPPORTUNITIES",           opps)

                # ── RENDER CARD ───────────────────────────────────────────
                pulse_cls = "pulse-hot" if s_label.startswith("🔥") else ""
                st.markdown(f"""
                <div class='lead-card {pulse_cls}'>
                    <div style='display:flex; justify-content:space-between; align-items:start;'>
                        <div class='company'>{name}</div>
                        <div class='score-badge {s_cls}'>{s_label}</div>
                    </div>
                    <div class='url'><span class='status-dot {dot_cls}'></span>🔗 <a href='{url_href}' target='_blank' style='color:#00d4ff;text-decoration:none;'>{url_clean}</a></div>
                    <div class='divider'></div>
                    <div class='info-row'>{all_pills}</div>
                </div>
                """, unsafe_allow_html=True)

                # --- Outreach Lab Tabs ---
                if data_label == "deep_extracted":
                    t1, t2 = st.tabs(["🧠 Intelligence", "✉️ Outreach Lab"])
                    with t1:
                        st.markdown(f"<div class='intel-section'>{intel_html}</div>", unsafe_allow_html=True)
                        if is_valid(reason):
                            st.info(f"**AI Reason:** {reason}")
                    with t2:
                        subject = lead.get("outreach_subject", "Quick Question")
                        email_draft = lead.get("outreach_email_draft", "Hi, noticed you might need some help with automation.")
                        st.markdown(f"<div class='intel-label'>SUBJECT:</div><code style='color:#00ffa3;'>{subject}</code>", unsafe_allow_html=True)
                        st.text_area("Draft:", email_draft, height=120, key=f"draft_{name}")
                        st.markdown(f"<div class='outreach-quote'>Hook: {outreach}</div>", unsafe_allow_html=True)
                        st.button("📋 Copy Template", key=f"cp_{name}")
                else:
                    st.markdown(f"<div class='intel-section'>{intel_html}</div>", unsafe_allow_html=True)

else:
    st.markdown("""
<div style='text-align:center;padding:60px 20px;border:1px dashed #0e2040;border-radius:16px;margin-top:20px;'>
  <p style='font-family:JetBrains Mono,monospace;color:#1a3060;font-size:3rem;margin:0;'>⬡</p>
  <p style='font-family:JetBrains Mono,monospace;color:#00d4ff;font-size:1rem;letter-spacing:3px;'>AWAITING INPUT</p>
  <p style='color:#2a4060;font-size:0.85rem;'>Enter a query above and click <strong style='color:#4a80c0'>Find Leads</strong> to begin.</p>
</div>""", unsafe_allow_html=True)

