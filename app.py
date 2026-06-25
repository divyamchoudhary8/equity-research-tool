"""
app.py — EquityIQ
──────────────────
Automated Equity Research Tool · Part 1: Financial Statement Analysis
Dark animated professional dashboard.

Run: streamlit run app.py
"""

import streamlit as st
from datetime import date
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data.fetcher import NSEDataFetcher
from analysis.dupont import DuPontAnalyzer
from analysis.piotroski import PiotroskiScorer
from analysis.ratios import FinancialRatiosCalculator
from analysis.dcf import DCFValuation
from analysis.comps import CompsAnalysis
from analysis.football_field import FootballField
from utilis.pdf_report import generate_report


# ══════════════════════════════════════════════════════════════════
# PAGE CONFIG  — must be the very first Streamlit call
# ══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="EquityIQ",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════
# DESIGN CONSTANTS
# ══════════════════════════════════════════════════════════════════
CYAN   = "#00d4ff"
GREEN  = "#00ff87"
RED    = "#ff4757"
PURPLE = "#a78bfa"
GOLD   = "#ffd700"
MUTED  = "#8892b0"
TEXT   = "#ccd6f6"
BG     = "#0a0e27"

# Every Plotly figure inherits this base layout
BASE = dict(
    paper_bgcolor = "rgba(0,0,0,0)",
    plot_bgcolor  = "rgba(13,27,42,0.6)",
    font          = dict(color=TEXT, family="Inter, sans-serif", size=12),
    title_font    = dict(color=CYAN, size=15),
    xaxis = dict(showgrid=False, color=MUTED, zeroline=False,
                 tickfont=dict(color=MUTED)),
    yaxis = dict(gridcolor="rgba(136,146,176,0.08)", color=MUTED,
                 zeroline=False, tickfont=dict(color=MUTED)),
    hovermode  = "x unified",
    hoverlabel = dict(bgcolor="rgba(10,14,39,0.95)", bordercolor=CYAN,
                      font=dict(color=TEXT, size=13)),
    margin = dict(t=55, b=45, l=55, r=30),
    legend = dict(bgcolor="rgba(10,14,39,0.7)",
                  bordercolor="rgba(0,212,255,0.2)", borderwidth=1,
                  font=dict(color=TEXT, size=12)),
)


# ══════════════════════════════════════════════════════════════════
# CSS  — animated background + full component theming
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<style>

/* ── Animated gradient background ─────────────────────────────── */
@keyframes gradientDrift {
    0%   { background-position: 0%   50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0%   50%; }
}
@keyframes shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position:  200% 0; }
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0);    }
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.7; }
}

/* Animated gradient on the main app container */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(-45deg, #0a0e27, #0b1220, #0d1b2a, #091428, #0e1a35) !important;
    background-size: 400% 400% !important;
    animation: gradientDrift 22s ease infinite !important;
}

/* Header transparent so gradient shows at top */
[data-testid="stHeader"] {
    background: transparent !important;
}

/* Main content area transparent so gradient shows through */
[data-testid="stMain"],
[data-testid="block-container"],
.main {
    background: transparent !important;
}

/* ── Hide Streamlit chrome ─────────────────────────────────────── */
#MainMenu, footer { visibility: hidden; }

/* Keep sidebar and its collapse/expand controls always visible */
section[data-testid="stSidebar"] { display: block !important; }
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: block !important;
    visibility: visible !important;
}

/* ── Sidebar ───────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: rgba(9, 20, 40, 0.97) !important;
    border-right: 1px solid rgba(0, 212, 255, 0.12) !important;
}

/* ── Tabs ──────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(13, 27, 42, 0.7) !important;
    border-radius: 14px !important;
    padding: 5px !important;
    border: 1px solid rgba(0, 212, 255, 0.12) !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px !important;
    color: #8892b0 !important;
    font-weight: 500 !important;
    padding: 10px 22px !important;
    transition: all 0.25s ease !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(0,212,255,0.18),
                rgba(167,139,250,0.18)) !important;
    color: #00d4ff !important;
    border: 1px solid rgba(0,212,255,0.3) !important;
}

/* ── Metrics ───────────────────────────────────────────────────── */
div[data-testid="metric-container"] {
    background: rgba(13, 27, 42, 0.85) !important;
    border: 1px solid rgba(0, 212, 255, 0.15) !important;
    border-radius: 14px !important;
    padding: 18px 16px !important;
    backdrop-filter: blur(12px) !important;
    transition: border-color 0.3s ease, box-shadow 0.3s ease !important;
}
div[data-testid="metric-container"]:hover {
    border-color: rgba(0, 212, 255, 0.45) !important;
    box-shadow: 0 0 20px rgba(0,212,255,0.08) !important;
}
div[data-testid="metric-container"] label {
    color: #8892b0 !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    font-weight: 600 !important;
}
div[data-testid="stMetricValue"] > div {
    color: #00d4ff !important;
    font-size: 21px !important;
    font-weight: 700 !important;
}

/* ── Text input ────────────────────────────────────────────────── */
.stTextInput > div > div > input {
    background: rgba(13, 27, 42, 0.9) !important;
    border: 1px solid rgba(0, 212, 255, 0.25) !important;
    color: #e8eaf6 !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
    font-size: 15px !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}
.stTextInput > div > div > input:focus {
    border-color: #00d4ff !important;
    box-shadow: 0 0 0 3px rgba(0,212,255,0.12) !important;
}

/* ── Primary button ────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00d4ff, #7c3aed) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    letter-spacing: 0.05em !important;
    transition: all 0.3s ease !important;
    padding: 10px !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 32px rgba(0,212,255,0.35) !important;
}

/* ── Expanders ─────────────────────────────────────────────────── */
details summary {
    background: rgba(13, 27, 42, 0.85) !important;
    border: 1px solid rgba(0, 212, 255, 0.12) !important;
    border-radius: 10px !important;
    color: #00d4ff !important;
    padding: 12px 18px !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    transition: border-color 0.2s !important;
}
details[open] summary {
    border-bottom-left-radius: 0 !important;
    border-bottom-right-radius: 0 !important;
    border-color: rgba(0,212,255,0.35) !important;
}

/* ── DataFrames ────────────────────────────────────────────────── */
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(0, 212, 255, 0.1) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

/* ── Scrollbar ─────────────────────────────────────────────────── */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0a0e27; }
::-webkit-scrollbar-thumb { background: rgba(0,212,255,0.25); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,212,255,0.5); }

/* ── Divider ───────────────────────────────────────────────────── */
hr { border-color: rgba(0, 212, 255, 0.08) !important; margin: 24px 0 !important; }

</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def chart(fig: go.Figure, title: str = "", height: int = 370) -> go.Figure:
    """Apply the standard dark theme to any Plotly figure."""
    fig.update_layout(**{**BASE, "title": title, "height": height})
    return fig


def insight(text: str, icon: str = "💡", color: str = CYAN):
    """Blue IB-style interpretation card shown below every chart."""
    st.markdown(f"""
    <div style="
        background: rgba(0,212,255,0.04);
        border: 1px solid rgba(0,212,255,0.14);
        border-left: 4px solid {color};
        border-radius: 0 12px 12px 0;
        padding: 13px 18px; margin: 4px 0 20px 0;
        line-height: 1.65; animation: fadeInUp 0.4s ease;
    ">
        <span style="font-size:15px; margin-right:8px;">{icon}</span>
        <span style="color:{TEXT}; font-size:13px;">{text}</span>
    </div>
    """, unsafe_allow_html=True)


def sec(title: str, sub: str = ""):
    """Section header with optional subtitle."""
    s = f'<p style="color:{MUTED};font-size:13px;margin:3px 0 0 0;">{sub}</p>' if sub else ""
    st.markdown(f"""
    <div style="margin:26px 0 14px 0; animation: fadeInUp 0.3s ease;">
        <h3 style="color:{CYAN};font-size:18px;font-weight:700;margin:0;letter-spacing:0.02em;">{title}</h3>
        {s}
    </div>""", unsafe_allow_html=True)


def fmt(x):
    """Format ratio values cleanly — handles None, NaN, inf."""
    if x is None: return "—"
    if isinstance(x, float) and np.isnan(x):  return "—"
    if isinstance(x, float) and np.isinf(x):  return "∞"
    return f"{x:.2f}"


def rgba_fill(hex_color: str, alpha: float = 0.09) -> str:
    """Convert hex to rgba — Plotly does not support 8-digit hex colors."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def safe_div(a, b, default=0.0):
    """Safe division used across app — returns default when b is zero or None."""
    try:
        if b is None or b == 0 or (isinstance(b, float) and np.isnan(b)):
            return default
        result = a / b
        return result if np.isfinite(result) else default
    except:
        return default


def prep_stmt(df: pd.DataFrame) -> pd.DataFrame:
    """Scale raw INR to Crores and rename columns to fiscal years."""
    out = df.copy()
    for col in out.columns:
        out[col] = pd.to_numeric(out[col], errors='coerce') / 1e7
    out.columns = [str(int(c.year)) for c in df.columns]
    out.index   = [str(i).replace('_', ' ').title() for i in df.index]
    return out.round(2)


def line(df, metric, color, bench=None, bench_label="", height=300):
    """Reusable filled area trend line for a single ratio."""
    if metric not in df.columns:
        return
    dff  = df.reset_index()
    yrs  = dff['Year'].astype(str).tolist()
    vals = [v if (v is not None and not (isinstance(v, float) and np.isnan(v))) else None
            for v in dff[metric].tolist()]

    fig = go.Figure()
    if bench:
        fig.add_hline(y=bench, line_dash="dot",
                      line_color="rgba(255,255,255,0.18)", line_width=1.5,
                      annotation_text=bench_label,
                      annotation_font=dict(color=MUTED, size=11),
                      annotation_position="bottom right")
    fig.add_trace(go.Scatter(
        x=yrs, y=vals, mode="lines+markers",
        line=dict(color=color, width=2.5),
        marker=dict(size=9, color=color, line=dict(color=BG, width=2)),
        fill="tozeroy", fillcolor=rgba_fill(color),
        hovertemplate=f"<b>{metric}:</b> %{{y:.2f}}<extra></extra>",
    ))
    chart(fig, metric, height)
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style="padding:16px 0 18px 0;">
        <div style="
            font-size:20px;font-weight:800;
            background:linear-gradient(135deg,{CYAN},{PURPLE});
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;
            letter-spacing:0.06em;margin-bottom:3px;
        ">EquityIQ</div>
        <div style="color:#546e7a;font-size:10px;letter-spacing:0.05em;">
            EQUITY RESEARCH PLATFORM
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f'<div style="height:1px;background:rgba(255,255,255,0.06);margin-bottom:16px;"></div>', unsafe_allow_html=True)

    ticker_input = st.text_input(
        "NSE Ticker Symbol", value="RELIANCE",
        placeholder="e.g. RELIANCE, TCS, INFY",
        help="Enter NSE ticker without .NS suffix",
    ).strip().upper()

    analyze_btn = st.button("Analyze", type="primary", use_container_width=True)

    # Back to home — only shown when viewing analysis
    if "data" in st.session_state:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← New Search", use_container_width=True, key="back_home"):
            del st.session_state["data"]
            del st.session_state["ticker"]
            st.rerun()

    st.markdown("---")
    st.markdown(f'<div style="color:{MUTED};font-size:11px;text-transform:uppercase;letter-spacing:0.08em;font-weight:600;margin-bottom:8px;">Coverage Universe</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:#455a64;font-size:11px;line-height:1.7;">RELIANCE · TCS · HDFCBANK · INFY · WIPRO · MARUTI · LT · TATAMOTORS · NESTLEIND · BAJFINANCE · SUNPHARMA · TITAN · ETERNAL · ADANIPORTS · ICICIBANK</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f'<div style="color:#37474f;font-size:10px;line-height:1.7;">Data: Yahoo Finance (yfinance)<br>Values: Indian Rupees (₹ Crores)<br>Coverage: NSE Listed Companies</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# LANDING PAGE
# ══════════════════════════════════════════════════════════════════
if not analyze_btn and "data" not in st.session_state:

    # ── Hero ──────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="text-align:center;padding:52px 20px 40px 20px;animation:fadeInUp 0.5s ease;">
        <div style="font-size:10px;color:rgba(0,212,255,0.6);text-transform:uppercase;
                    letter-spacing:0.25em;font-weight:600;margin-bottom:20px;">
            Equity Research &nbsp;·&nbsp; NSE Listed Companies
        </div>
        <div style="
            font-size:68px;font-weight:800;letter-spacing:-0.02em;line-height:1.0;
            background:linear-gradient(135deg,{CYAN} 0%,{PURPLE} 60%,{CYAN} 100%);
            background-size:200% auto;
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;
            animation:shimmer 4s linear infinite;margin-bottom:16px;
        ">EquityIQ</div>
        <div style="font-size:17px;color:#b0bec5;font-weight:300;
                    letter-spacing:0.01em;margin-bottom:40px;">
            Professional-grade equity research and valuation for NSE-listed companies
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Capability stats bar ───────────────────────────────────────
    st.markdown(f"""
    <div style="display:flex;justify-content:center;gap:0;margin:0 auto 44px auto;
                max-width:700px;background:rgba(13,27,42,0.7);
                border:1px solid rgba(0,212,255,0.1);border-radius:12px;overflow:hidden;">
        {"".join([
            f'<div style="flex:1;padding:18px 12px;text-align:center;'
            f'{"border-right:1px solid rgba(0,212,255,0.08);" if i<3 else ""}">'
            f'<div style="font-size:22px;font-weight:700;color:{CYAN};">{val}</div>'
            f'<div style="font-size:10px;color:{MUTED};text-transform:uppercase;'
            f'letter-spacing:0.1em;margin-top:4px;">{lbl}</div>'
            f'</div>'
            for i,(val,lbl) in enumerate([
                ("1,800+", "NSE Tickers"),
                ("4", "Valuation Methods"),
                ("25+", "Financial Ratios"),
                ("6-Page", "PDF Report"),
            ])
        ])}
    </div>
    """, unsafe_allow_html=True)

    # ── Capability grid ────────────────────────────────────────────
    c1, c2 = st.columns(2)
    capabilities = [
        (CYAN,   "Financial Statement Analysis",
         "5-year income statement, balance sheet, and cash flow analysis. "
         "DuPont ROE decomposition, Piotroski F-Score screening, "
         "and 25+ financial ratios across 5 categories."),
        (PURPLE, "DCF Valuation",
         "Discounted cash flow model with FCFF projections across base, bull, "
         "and bear scenarios. WACC via CAPM, Gordon Growth terminal value, "
         "and WACC × growth rate sensitivity table."),
        (GREEN,  "Comparable Company Analysis",
         "Auto-suggested sector peers with live market data. "
         "EV/EBITDA, EV/Revenue, EV/EBIT, P/E, and P/B multiples. "
         "Implied valuation range from peer median multiples."),
        (GOLD,   "Football Field & Research Report",
         "Aggregated valuation across all methodologies with a "
         "BUY / HOLD / SELL recommendation and weighted 12-month target price. "
         "One-click 6-page professional PDF report."),
    ]
    for i, (accent, title, desc) in enumerate(capabilities):
        col = c1 if i % 2 == 0 else c2
        col.markdown(f"""
        <div style="
            background:rgba(13,27,42,0.6);
            border:1px solid rgba(255,255,255,0.05);
            border-left:3px solid {accent};
            border-radius:0 10px 10px 0;
            padding:20px 22px;
            margin-bottom:10px;
        ">
            <div style="color:{accent};font-size:13px;font-weight:700;
                        margin-bottom:7px;letter-spacing:0.01em;">{title}</div>
            <div style="color:#78909c;font-size:12px;line-height:1.65;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── CTA ───────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="text-align:center;margin-top:32px;padding:20px;
                border-top:1px solid rgba(255,255,255,0.05);">
        <div style="color:#546e7a;font-size:12px;margin-bottom:10px;">
            Enter any NSE ticker symbol in the sidebar and click
            <span style="color:{CYAN};font-weight:600;">Analyze</span> to begin
        </div>
        <div style="color:#37474f;font-size:11px;">
            Examples: RELIANCE &nbsp;·&nbsp; TCS &nbsp;·&nbsp; HDFCBANK &nbsp;·&nbsp;
            INFY &nbsp;·&nbsp; MARUTI &nbsp;·&nbsp; TITAN &nbsp;·&nbsp; SUNPHARMA
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════
# DATA FETCH
# ══════════════════════════════════════════════════════════════════
if analyze_btn:
    with st.spinner(f"Fetching {ticker_input} from Yahoo Finance…"):
        try:
            fetcher = NSEDataFetcher(ticker_input)
            data    = fetcher.get_all_data()
            st.session_state["data"]   = data
            st.session_state["ticker"] = ticker_input
        except Exception as e:
            st.error(f"❌ Could not fetch **{ticker_input}.NS** — {e}")
            st.info("Try: RELIANCE · TCS · HDFCBANK · INFY · WIPRO · MARUTI · LT")
            st.stop()

data   = st.session_state["data"]
ticker = st.session_state["ticker"]

inc = data["income_stmt"]
bs  = data["balance_sheet"]
cf  = data["cash_flow"]
inf = data["info"]

dupont_a   = DuPontAnalyzer(inc, bs)
piotr      = PiotroskiScorer(inc, bs, cf)
ratios_obj = FinancialRatiosCalculator(inc, bs, cf, inf)


# ══════════════════════════════════════════════════════════════════
# COMPANY BANNER
# ══════════════════════════════════════════════════════════════════
name    = inf.get("longName",         inf.get("shortName", ticker))
sector  = inf.get("sector",           "N/A")
ind     = inf.get("industry",         "N/A")
price   = inf.get("currentPrice",     inf.get("regularMarketPrice", 0)) or 0
prev    = inf.get("previousClose",    0) or 0
chg_pct = ((price - prev) / prev * 100) if prev else 0
cap_cr  = (inf.get("marketCap") or 0) / 1e7
hi52    = inf.get("fiftyTwoWeekHigh", 0) or 0
lo52    = inf.get("fiftyTwoWeekLow",  0) or 0
beta_v  = inf.get("beta",            None)
c_chg   = GREEN if chg_pct >= 0 else RED
arrow   = "▲" if chg_pct >= 0 else "▼"

st.markdown(f"""
<div style="
    background:rgba(13,27,42,0.88);
    border:1px solid rgba(0,212,255,0.16);
    border-radius:18px; padding:24px 30px;
    margin-bottom:18px; backdrop-filter:blur(14px);
    animation: fadeInUp 0.4s ease;
">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:14px;">
        <div>
            <div style="font-size:27px;font-weight:800;color:#e8eaf6;letter-spacing:-0.01em;">
                {name}
                <span style="font-size:14px;color:{MUTED};font-weight:400;margin-left:10px;">{ticker}.NS</span>
            </div>
            <div style="color:{MUTED};font-size:13px;margin-top:5px;">
                {sector} &nbsp;·&nbsp; {ind}
            </div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:34px;font-weight:800;color:{CYAN};
                        text-shadow:0 0 28px rgba(0,212,255,0.4);">
                ₹{price:,.2f}
            </div>
            <div style="font-size:14px;color:{c_chg};font-weight:600;margin-top:2px;">
                {arrow} {abs(chg_pct):.2f}% today
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Market Cap", f"₹{cap_cr:,.0f} Cr")
m2.metric("52W High",   f"₹{hi52:,.2f}")
m3.metric("52W Low",    f"₹{lo52:,.2f}")
m4.metric("Beta",       f"{beta_v:.2f}" if beta_v else "N/A")
m5.metric("Sector",     sector[:20] + "…" if len(sector) > 20 else sector)

# ── PDF Download ──────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)

with st.expander("📄  Download Equity Research Report (PDF)", expanded=False):
    st.markdown(f"""
    <div style="background:rgba(0,212,255,0.05);border:1px solid rgba(0,212,255,0.15);
                border-radius:12px;padding:14px 18px;margin-bottom:12px;">
        <div style="color:{CYAN};font-weight:700;font-size:14px;margin-bottom:5px;">
            EquityIQ Research — Initiating Coverage Report
        </div>
        <div style="color:{MUTED};font-size:12px;line-height:1.6;">
            6-page professional PDF · Cover Page · Executive Summary · Financial Analysis ·
            DCF Valuation · Comps · Football Field · BUY/HOLD/SELL Recommendation · Disclaimer
        </div>
    </div>
    """, unsafe_allow_html=True)

    pdf_analyst = st.text_input(
        "Analyst Name (printed on the report)",
        value="Divyam Choudhary", key="pdf_analyst"
    )

    if st.button("⚡  Generate PDF Report", type="primary", key="gen_pdf_btn"):
        with st.spinner("Building report… 15–30 seconds"):
            try:
                _d  = DCFValuation(inc, bs, cf, inf)
                _a  = _d.auto_assumptions()
                _dr = _d.run(_a)
                _ce = CompsAnalysis(ticker, inf, inc, bs, cf)
                _ct = _ce.build_table(_ce.suggest_peers())
                _cs = _ce.peer_stats(_ct) if not _ct.empty else pd.DataFrame()
                _ci = _ce.implied_valuation(_cs) if not _cs.empty else pd.DataFrame()
                _ff = FootballField(price, _dr, _ci, inf)
                _fb = _ff.build_bars()
                _ra = ratios_obj.all_ratios()
                _pi = piotr.calculate(0)
                _rc = _ff.recommendation(_fb, _ra, _pi)
                _dp = dupont_a.compute_3_factor()
                _hf = DCFValuation(inc, bs, cf, inf).historical_fcff()

                pdf_bytes = generate_report(
                    ticker=ticker, company=name, sector=sector,
                    industry=ind, info=inf, hist_fcff=_hf,
                    ratios=_ra, dupont_3f=_dp, piotroski=_pi,
                    dcf_results=_dr, implied_df=_ci,
                    rec=_rc, bars=_fb, analyst_name=pdf_analyst,
                )
                st.download_button(
                    label=f"📥  Download {ticker} Research Report (PDF)",
                    data=pdf_bytes,
                    file_name=f"{ticker}_EquityIQ_Research_{date.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    type="primary", use_container_width=True,
                )
                st.success("✅ Report ready — click the button above to download.")
            except Exception as e:
                st.error(f"❌ {e}")

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📋  Financial Statements",
    "🔬  DuPont Analysis",
    "🏥  Piotroski F-Score",
    "📈  Key Ratios",
    "💹  DCF Valuation",
    "🏢  Comps Analysis",
    "🎯  Football Field",
])


# ──────────────────────────────────────────────────────────────────
# TAB 1 — FINANCIAL STATEMENTS
# ──────────────────────────────────────────────────────────────────
with tab1:
    sec("Financial Statements", "5-year annual data · All values in ₹ Crores")
    insight(
        "Three core statements every IB analyst reads before any work. "
        "<b>Income Statement</b>: profitability over time. "
        "<b>Balance Sheet</b>: financial position at a point in time. "
        "<b>Cash Flow</b>: whether profits are backed by real cash.",
        icon="📌"
    )

    with st.expander("📊  Income Statement (₹ Cr)", expanded=True):
        st.dataframe(prep_stmt(inc), use_container_width=True, height=420)
    with st.expander("🏦  Balance Sheet (₹ Cr)", expanded=False):
        st.dataframe(prep_stmt(bs),  use_container_width=True, height=420)
    with st.expander("💸  Cash Flow Statement (₹ Cr)", expanded=False):
        st.dataframe(prep_stmt(cf),  use_container_width=True, height=420)

    st.markdown("---")
    sec("Revenue vs Net Income", "Are margins expanding as the company grows?")

    years     = NSEDataFetcher.get_years(inc)
    yrs_s     = [str(y) for y in years]
    revenues  = [NSEDataFetcher.get_safe_value(inc, ["Total Revenue","TotalRevenue","Revenue"], i) for i in range(len(years))]
    net_incs  = [NSEDataFetcher.get_safe_value(inc, ["Net Income","NetIncome","Net Income Common Stockholders"], i) for i in range(len(years))]
    cfos      = [NSEDataFetcher.get_safe_value(cf,  ["Operating Cash Flow","Total Cash From Operating Activities","Cash Flow From Continuing Operating Activities"], i) for i in range(len(years))]

    # Dual-axis: Revenue bars + Net Income line
    fig_rev = make_subplots(specs=[[{"secondary_y": True}]])
    yrs_s = [str(y) for y in years]  # ensure strings for categorical axis
    fig_rev.add_trace(go.Bar(
        x=yrs_s, y=revenues, name="Revenue",
        marker=dict(
            color=revenues,
            colorscale=[[0,"rgba(0,212,255,0.25)"],[1,"rgba(0,212,255,0.85)"]],
            showscale=False,
            line=dict(color="rgba(0,212,255,0.4)", width=1),
        ),
        hovertemplate="<b>Revenue:</b> ₹%{y:,.0f} Cr<extra></extra>",
    ), secondary_y=False)
    fig_rev.add_trace(go.Scatter(
        x=yrs_s, y=net_incs, name="Net Income",
        mode="lines+markers",
        line=dict(color=GREEN, width=3),
        marker=dict(size=11, color=GREEN, line=dict(color=BG, width=2)),
        hovertemplate="<b>Net Income:</b> ₹%{y:,.0f} Cr<extra></extra>",
    ), secondary_y=True)
    fig_rev.update_layout(**{**BASE, "title": f"{ticker} — Revenue vs. Net Income", "height": 400,
                          "xaxis": dict(type="category", showgrid=False, color=MUTED,
                                       tickfont=dict(color=MUTED))})
    fig_rev.update_yaxes(title_text="Revenue (₹ Cr)", color=MUTED, secondary_y=False,
                         gridcolor="rgba(136,146,176,0.08)")
    fig_rev.update_yaxes(title_text="Net Income (₹ Cr)", color=GREEN, secondary_y=True, showgrid=False)
    st.plotly_chart(fig_rev, use_container_width=True)
    if len(revenues) >= 2 and revenues[-1] > 0:
        rev_cagr  = ((revenues[0]/revenues[-1])**(1/max(len(revenues)-1,1))-1)*100
        ni_cagr   = ((net_incs[0]/net_incs[-1])**(1/max(len(net_incs)-1,1))-1)*100 if net_incs[-1] > 0 else 0
        margin_now  = (net_incs[0]/revenues[0]*100) if revenues[0] > 0 else 0
        margin_then = (net_incs[-1]/revenues[-1]*100) if revenues[-1] > 0 else 0
        margin_dir  = "expanding ▲" if margin_now > margin_then else "compressing ▼"
        insight(
            f"{ticker}'s Revenue CAGR is <b>{rev_cagr:.1f}%</b>, "
            f"Net Income CAGR is <b>{ni_cagr:.1f}%</b>. "
            f"Net Profit Margin is <b>{margin_dir}</b> ({margin_then:.1f}% → {margin_now:.1f}%). "
            f"{'Net Income growing faster than Revenue = quality earnings growth ✓' if ni_cagr > rev_cagr else 'Revenue growing faster than Net Income = margin pressure — investigate cost trends.'}",
            color=GREEN if ni_cagr >= rev_cagr else RED
        )
    else:
        insight("Both Revenue and Net Income should grow together — Net Income growing faster = margin expansion.", color=GREEN)

    # Operating Cash Flow bar chart
    sec("Operating Cash Flow", "Is profit backed by real cash?")
    fig_cfo = go.Figure(go.Bar(
        x=yrs_s, y=cfos,
        marker_color=[GREEN if v >= 0 else RED for v in cfos],
        text=[f"₹{v:,.0f} Cr" for v in cfos],
        textposition="outside",
        textfont=dict(color=TEXT, size=11),
        hovertemplate="<b>CFO:</b> ₹%{y:,.0f} Cr<extra></extra>",
    ))
    fig_cfo.add_hline(y=0, line_color="rgba(255,255,255,0.15)", line_width=1.5)
    chart(fig_cfo, f"{ticker} — Operating Cash Flow (₹ Cr)", 340)
    st.plotly_chart(fig_cfo, use_container_width=True)
    neg_cfo_years = [str(years[i]) for i,v in enumerate(cfos) if v < 0]
    avg_cfo = sum(cfos)/len(cfos) if cfos else 0
    cfo_trend = "improving ▲" if len(cfos)>=2 and cfos[0]>cfos[-1] else "declining ▼"
    if neg_cfo_years:
        insight(
            f"{ticker} had <b>negative CFO in {', '.join(neg_cfo_years)}</b> — "
            f"profits were not backed by cash in those years. "
            f"Average CFO over the period: ₹{avg_cfo:,.0f} Cr. "
            f"Always cross-check negative CFO years against Net Income — a red flag if both diverge.",
            color=RED
        )
    else:
        insight(
            f"{ticker} has maintained <b>consistently positive CFO</b> across all years — "
            f"a strong signal that earnings are backed by real cash. "
            f"CFO trend is <b>{cfo_trend}</b>. Average: ₹{avg_cfo:,.0f} Cr.",
            color=GREEN
        )


# ──────────────────────────────────────────────────────────────────
# TAB 2 — DUPONT ANALYSIS
# ──────────────────────────────────────────────────────────────────
with tab2:
    sec("DuPont ROE Decomposition", "Understanding the quality behind Return on Equity")
    insight(
        "<b>IB Core Concept:</b> Two companies can both have 20% ROE. One earns it through "
        "strong margins — the other through 6× financial leverage. DuPont separates these immediately. "
        "Always decompose ROE before forming a view in M&A or equity research.",
        icon="🎯"
    )

    df3 = dupont_a.compute_3_factor()
    df5 = dupont_a.compute_5_factor()

    cl, cr = st.columns(2)
    with cl:
        sec("3-Factor DuPont", "ROE = Margin × Efficiency × Leverage")
        st.dataframe(df3.style.format(fmt), use_container_width=True)
    with cr:
        sec("5-Factor DuPont", "Splits margin into Tax · Interest · EBIT")
        st.dataframe(df5.style.format(fmt), use_container_width=True)

    st.markdown("---")
    sec("3-Factor Components vs ROE", "Which driver is pushing ROE up or down each year?")

    df3r  = df3.reset_index()
    yrs_s = df3r["Year"].astype(str).tolist()

    fig3 = make_subplots(specs=[[{"secondary_y": True}]])
    for col_name, color, label in [
        ("Net Profit Margin (%)", "rgba(0,212,255,0.75)",  "Net Profit Margin (%)"),
        ("Asset Turnover (x)",    "rgba(0,255,135,0.75)",  "Asset Turnover (x)"),
        ("Equity Multiplier (x)", "rgba(167,139,250,0.75)","Equity Multiplier (x)"),
    ]:
        fig3.add_trace(go.Bar(
            x=yrs_s, y=df3r[col_name], name=label,
            marker_color=color,
            hovertemplate=f"<b>{label}:</b> %{{y:.2f}}<extra></extra>",
        ), secondary_y=False)
    fig3.add_trace(go.Scatter(
        x=yrs_s, y=df3r["ROE (%)"], name="ROE (%)",
        mode="lines+markers+text",
        text=[f"{v:.1f}%" for v in df3r["ROE (%)"]],
        textposition="top center",
        textfont=dict(color=GOLD, size=11),
        line=dict(color=GOLD, width=3, dash="dot"),
        marker=dict(size=11, color=GOLD, line=dict(color=BG, width=2)),
        hovertemplate="<b>ROE:</b> %{y:.2f}%<extra></extra>",
    ), secondary_y=True)
    fig3.update_layout(**{**BASE, "barmode":"group",
                          "title": f"{ticker} — 3-Factor DuPont", "height": 430})
    fig3.update_yaxes(title_text="Component Values", color=MUTED,
                      gridcolor="rgba(136,146,176,0.08)", secondary_y=False)
    fig3.update_yaxes(title_text="ROE (%)", color=GOLD, showgrid=False, secondary_y=True)
    st.plotly_chart(fig3, use_container_width=True)
    # Data-driven 3-factor insight
    em_now   = df3r["Equity Multiplier (x)"].iloc[0]
    em_old   = df3r["Equity Multiplier (x)"].iloc[-1]
    npm_now  = df3r["Net Profit Margin (%)"].iloc[0]
    npm_old  = df3r["Net Profit Margin (%)"].iloc[-1]
    at_now   = df3r["Asset Turnover (x)"].iloc[0]
    roe_now3 = df3r["ROE (%)"].iloc[0]
    em_dir   = "risen" if em_now > em_old else "fallen"
    npm_dir  = "expanded" if npm_now > npm_old else "compressed"
    insight(
        f"{ticker}'s ROE is <b>{roe_now3:.1f}%</b>. "
        f"Net Profit Margin has <b>{npm_dir}</b> ({npm_old:.1f}% → {npm_now:.1f}%), "
        f"Asset Turnover is <b>{at_now:.2f}x</b>, "
        f"Equity Multiplier has <b>{em_dir}</b> ({em_old:.1f}x → {em_now:.1f}x). "
        f"{'⚠️ ROE improvement is driven by rising leverage, not profitability — a risk factor.' if em_now > em_old and npm_now <= npm_old else 'ROE is driven by operating performance rather than leverage ✓.'}",
        color=GOLD
    )

    # 5-Factor — year tabs + ROE trend chart
    if not df5.empty:
        st.markdown("---")
        sec("5-Factor Breakdown by Year", "Click a year tab to see that year's ROE decomposition")

        comps5 = ["Tax Burden","Interest Burden","EBIT Margin (%)","Asset Turnover (x)","Equity Multiplier (x)"]
        clrs5  = [CYAN, "#38bdf8", GREEN, PURPLE, RED]
        yrs5   = [str(y) for y in df5.index]

        # Bank detection — EBIT not meaningful for financial sector
        is_bank = sector in ["Financial Services", "Banks", "Financial", "Insurance"]
        if is_bank or df5["EBIT Margin (%)"].abs().mean() < 0.5:
            st.markdown(f"""
            <div style="background:rgba(255,215,0,0.06);border:1px solid rgba(255,215,0,0.25);
                        border-left:4px solid {GOLD};border-radius:0 10px 10px 0;
                        padding:10px 16px;margin-bottom:12px;font-size:13px;color:{TEXT};">
                ⚠️ <b>Note:</b> {ticker} is a financial sector company. Banks don't have EBIT in the
                traditional sense — interest is their core business cost, not a financing cost.
                EBIT Margin is proxied using Pretax Income / Revenue. Treat 5-Factor DuPont
                with caution for banks — ROA × Equity Multiplier (3-Factor) is more reliable.
            </div>
            """, unsafe_allow_html=True)

        # ── One tab per year ─────────────────────────────────────
        yr_tabs = st.tabs([f"📅 {y}" for y in yrs5])
        for yr_tab, yr in zip(yr_tabs, yrs5):
            with yr_tab:
                row_data = df5.loc[int(yr)]
                vals5    = [row_data[c] for c in comps5]
                roe_yr   = row_data["ROE (%)"]

                col_chart, col_metrics = st.columns([2, 1])
                with col_chart:
                    short_names = ["Tax Burden","Interest Burden","EBIT Margin","Asset Turnover","Equity Multiplier"]
                    fig_yr = go.Figure(go.Bar(
                        x=vals5,
                        y=short_names,
                        orientation="h",
                        marker=dict(color=clrs5, line=dict(color="rgba(255,255,255,0.06)", width=1)),
                        text=[f"{v:.3f}" for v in vals5],
                        textposition="outside",
                        textfont=dict(color=TEXT, size=12),
                        hovertemplate="<b>%{y}:</b> %{x:.4f}<extra></extra>",
                    ))
                    fig_yr.update_layout(**{**BASE,
                        "title": "",
                        "height": 300,
                        "margin": dict(t=10, b=20, l=130, r=90),
                        "xaxis": dict(showgrid=True, gridcolor="rgba(136,146,176,0.08)",
                                     zeroline=True, zerolinecolor="rgba(255,255,255,0.1)",
                                     type="linear"),
                        "yaxis": dict(showgrid=False, type="category",
                                      categoryorder="array",
                                      categoryarray=list(reversed(short_names))),
                        "showlegend": False,
                    })
                    st.plotly_chart(fig_yr, use_container_width=True)

                with col_metrics:
                    rows_html = "".join([
                        f'<div style="display:flex;justify-content:space-between;'
                        f'padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
                        f'<span style="color:{MUTED};font-size:12px;">{short_names[i]}</span>'
                        f'<span style="color:{clrs5[i]};font-weight:700;font-size:13px;">{vals5[i]:.3f}</span>'
                        f'</div>'
                        for i in range(len(comps5))
                    ])
                    st.markdown(f"""
                    <div style="background:rgba(13,27,42,0.8);border:1px solid rgba(0,212,255,0.15);
                                border-radius:14px;padding:20px;margin-top:6px;">
                        <div style="color:{MUTED};font-size:11px;text-transform:uppercase;
                                    letter-spacing:0.08em;margin-bottom:12px;">ROE Build-up {yr}</div>
                        {rows_html}
                        <div style="display:flex;justify-content:space-between;
                                    padding:10px 0 0 0;margin-top:8px;">
                            <span style="color:{MUTED};font-size:13px;font-weight:600;">= ROE</span>
                            <span style="color:{GOLD};font-weight:900;font-size:22px;">{roe_yr:.1f}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # ── ROE Progression chart ────────────────────────────────
        st.markdown("---")
        sec("ROE Progression", "How has Return on Equity evolved year over year?")

        roe_vals5  = df5["ROE (%)"].tolist()
        dot_clrs5  = [GREEN if v >= 15 else (GOLD if v >= 8 else RED) for v in roe_vals5]

        fig_roe = go.Figure()
        fig_roe.add_trace(go.Scatter(
            x=yrs5, y=roe_vals5, fill="tozeroy",
            fillcolor=rgba_fill(CYAN, 0.07),
            line=dict(color=CYAN, width=3),
            mode="lines", showlegend=False, hoverinfo="skip",
        ))
        fig_roe.add_trace(go.Scatter(
            x=yrs5, y=roe_vals5,
            mode="markers+text",
            text=[f"{v:.1f}%" for v in roe_vals5],
            textposition="top center",
            textfont=dict(color=TEXT, size=13),
            marker=dict(size=15, color=dot_clrs5, line=dict(color=BG, width=2)),
            hovertemplate="<b>ROE %{x}:</b> %{y:.2f}%<extra></extra>",
            showlegend=False,
        ))
        fig_roe.add_hline(y=15, line_dash="dot", line_color=GREEN,
                          annotation_text="15% — strong",
                          annotation_font=dict(color=GREEN, size=11),
                          annotation_position="bottom right")
        fig_roe.add_hline(y=8, line_dash="dot", line_color=GOLD,
                          annotation_text="8% — average",
                          annotation_font=dict(color=GOLD, size=11),
                          annotation_position="bottom right")
        fig_roe.update_layout(xaxis=dict(type="category", showgrid=False,
                                          color=MUTED, tickfont=dict(color=MUTED)))
        chart(fig_roe, f"{ticker} — ROE Progression (%)", 320)
        st.plotly_chart(fig_roe, use_container_width=True)

        latest5  = df5.iloc[0]
        oldest5  = df5.iloc[-1]
        roe_now5 = latest5["ROE (%)"]
        roe_old5 = oldest5["ROE (%)"]
        em_now5  = latest5["Equity Multiplier (x)"]
        roe_dir5 = "improved" if roe_now5 > roe_old5 else "declined"
        dominant5 = max(comps5[:-1], key=lambda c: abs(latest5[c]))
        insight(
            f"{ticker}'s ROE has <b>{roe_dir5} from {roe_old5:.1f}% → {roe_now5:.1f}%</b>. "
            f"Biggest driver in the latest year: <b>{dominant5}</b> ({latest5[dominant5]:.3f}). "
            f"Equity Multiplier of <b>{em_now5:.1f}x</b> — "
            f"{'leverage is a significant ROE driver — watch if EBIT Margin weakens.' if em_now5 > 3 else 'leverage is conservative — ROE reflects genuine operating performance ✓'}",
            color=GREEN if roe_now5 > roe_old5 else RED
        )


# ──────────────────────────────────────────────────────────────────
# TAB 3 — PIOTROSKI F-SCORE
# ──────────────────────────────────────────────────────────────────
with tab3:
    sec("Piotroski F-Score", "9-signal financial health screen (0–9)")
    insight(
        "<b>IB Context:</b> Developed by Prof. Piotroski (Chicago Booth, 2000). "
        "9 binary yes/no questions answered purely from public financial data — no market prices needed. "
        "Proven to identify financially strong vs. distressed companies.",
        icon="🎓"
    )

    result   = piotr.calculate(0)
    trend_df = piotr.get_trend()

    if "error" in result:
        st.error(result["error"])
        st.stop()

    score = result["total_score"]
    if score >= 7:   sc, sg, label = GREEN,  "0,255,135",  "Strong"
    elif score >= 4: sc, sg, label = GOLD,   "255,215,0",  "Average"
    else:            sc, sg, label = RED,    "255,71,87",  "Weak"

    # Score badge
    _, badge_mid, _ = st.columns([1.8, 2, 1.8])
    with badge_mid:
        st.markdown(f"""
        <div style="
            text-align:center; padding:38px 28px;
            background:rgba(13,27,42,0.92);
            border:2px solid {sc};
            border-radius:22px;
            box-shadow:0 0 50px rgba({sg},0.22), inset 0 0 40px rgba({sg},0.04);
            margin:8px 0 26px 0; animation: fadeInUp 0.5s ease;
        ">
            <div style="
                font-size:88px; font-weight:900; color:{sc}; line-height:1;
                text-shadow:0 0 40px rgba({sg},0.6);
            ">{score}<span style="font-size:38px;color:{MUTED};">/9</span></div>
            <div style="font-size:24px;font-weight:700;color:{sc};margin-top:14px;">{label}</div>
            <div style="font-size:13px;color:{MUTED};margin-top:6px;">Fiscal Year {result['year']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    sec("Signal Breakdown", "9 binary signals across 3 categories")

    sigs  = result["signals"]
    p_sig = {k:v for k,v in sigs.items() if k.startswith(("F1","F2","F3","F4"))}
    l_sig = {k:v for k,v in sigs.items() if k.startswith(("F5","F6","F7"))}
    e_sig = {k:v for k,v in sigs.items() if k.startswith(("F8","F9"))}

    def sig_card(signals_dict, header, icon, denom):
        passed = sum(signals_dict.values())
        c = GREEN if passed == denom else (GOLD if passed >= denom//2+1 else RED)
        rows = "".join(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;margin:4px 0;
                    background:{'rgba(0,255,135,0.06)' if v else 'rgba(255,71,87,0.06)'};
                    border-radius:8px;border-left:3px solid {'#00ff87' if v else '#ff4757'};">
            <span style="font-size:16px;">{'✅' if v else '❌'}</span>
            <span style="color:{TEXT};font-size:13px;">{k.split(' - ',1)[1] if ' - ' in k else k}</span>
        </div>""" for k, v in signals_dict.items())
        return f"""
        <div style="background:rgba(13,27,42,0.75);border:1px solid rgba(0,212,255,0.1);
                    border-radius:14px;padding:18px;">
            <div style="color:{MUTED};font-size:11px;text-transform:uppercase;
                        letter-spacing:0.08em;margin-bottom:8px;">{icon} {header}</div>
            <div style="font-size:30px;font-weight:800;color:{c};margin-bottom:14px;">{passed}/{denom}</div>
            {rows}
        </div>"""

    c1, c2, c3 = st.columns(3)
    c1.markdown(sig_card(p_sig, "Profitability",       "📊", 4), unsafe_allow_html=True)
    c2.markdown(sig_card(l_sig, "Leverage / Liquidity","🏦", 3), unsafe_allow_html=True)
    c3.markdown(sig_card(e_sig, "Efficiency",          "⚙️",  2), unsafe_allow_html=True)

    # Underlying metrics
    st.markdown("---")
    sec("Underlying Metrics", f"Values that drove the signals for {result['year']}")
    mc = st.columns(len(result["metrics"]))
    for idx, (mn, mv) in enumerate(result["metrics"].items()):
        mc[idx].metric(mn, f"{mv:,.2f}")

    # F-Score trend
    if not trend_df.empty:
        st.markdown("---")
        sec("F-Score Trend", "Has financial health been improving over time?")

        tr       = trend_df.reset_index()
        dot_cols = [GREEN if s >= 7 else (GOLD if s >= 4 else RED) for s in tr["F-Score"]]

        fig_ps = go.Figure()
        fig_ps.add_hrect(y0=7,   y1=9.6, fillcolor="rgba(0,255,135,0.06)", line_width=0)
        fig_ps.add_hrect(y0=4,   y1=7,   fillcolor="rgba(255,215,0,0.05)", line_width=0)
        fig_ps.add_hrect(y0=-0.5,y1=4,   fillcolor="rgba(255,71,87,0.05)", line_width=0)
        for y_pos, lbl, c in [(8.3,"Strong",GREEN),(5.5,"Average",GOLD),(1.8,"Weak",RED)]:
            fig_ps.add_annotation(x=tr["Year"].astype(str).iloc[-1], y=y_pos,
                text=lbl, showarrow=False, font=dict(color=c, size=11),
                xanchor="right", opacity=0.55)
        fig_ps.add_trace(go.Scatter(
            x=tr["Year"].astype(str), y=tr["F-Score"],
            mode="lines+markers+text",
            text=tr["F-Score"], textposition="top center",
            textfont=dict(color=TEXT, size=12),
            line=dict(color=MUTED, width=2),
            marker=dict(size=17, color=dot_cols, line=dict(color=BG, width=3)),
            hovertemplate="<b>%{x}:</b> %{y}/9<extra></extra>",
        ))
        chart(fig_ps, f"{ticker} — Piotroski F-Score Trend", 390)
        fig_ps.update_layout(yaxis=dict(range=[-0.6, 10.2], showgrid=False))
        st.plotly_chart(fig_ps, use_container_width=True)
        insight(
            "<b>Green zone (7–9):</b> Financially healthy — strong profitability, manageable debt, improving efficiency. "
            "<b>Orange zone (4–6):</b> Average — needs closer inspection. "
            "<b>Red zone (0–3):</b> Multiple warning signs — potential distress.",
            color=GREEN
        )

        # Heatmap
        st.markdown("---")
        sec("Signal Heatmap", "See exactly which of the 9 signals pass or fail each year")
        sig_cols  = [c for c in trend_df.columns if c != "F-Score"]
        short_lbl = [c.split(" - ",1)[1] if " - " in c else c for c in sig_cols]

        fig_hm = go.Figure(go.Heatmap(
            z=trend_df[sig_cols].values,
            x=short_lbl,
            y=[str(y) for y in trend_df.index],
            colorscale=[[0,"rgba(255,71,87,0.5)"],[1,"rgba(0,255,135,0.5)"]],
            showscale=False,
            text=trend_df[sig_cols].values,
            texttemplate="%{text}",
            textfont=dict(color="white", size=14),
            hovertemplate="<b>%{y} · %{x}:</b> %{z}<extra></extra>",
            xgap=4, ygap=4,
        ))
        chart(fig_hm, f"{ticker} — Signal Heatmap  (1 = Pass · 0 = Fail)", 280)
        fig_hm.update_layout(
            xaxis=dict(tickangle=-38, tickfont=dict(size=11)),
            margin=dict(t=55, b=100, l=55, r=30),
        )
        st.plotly_chart(fig_hm, use_container_width=True)
        insight(
            "<b>How to read:</b> Each row = fiscal year, each column = one signal. "
            "Green = pass (1), Red = fail (0). "
            "A column that stays red across multiple years is a <b>structural weakness</b> worth investigating deeply.",
            color=PURPLE
        )


# ──────────────────────────────────────────────────────────────────
# TAB 4 — KEY RATIOS
# ──────────────────────────────────────────────────────────────────
with tab4:
    sec("Key Financial Ratios", "5 categories · 25+ ratios · IB benchmarks on every chart")

    all_r = ratios_obj.all_ratios()

    # ── 1. PROFITABILITY ────────────────────────────────────────────
    with st.expander("📊  Profitability Ratios", expanded=True):
        prof = all_r["profitability"]
        st.dataframe(prof.style.format(fmt), use_container_width=True)
        # Data-driven profitability insight
        ebitda_now  = prof["EBITDA Margin (%)"].iloc[0]
        ebitda_old  = prof["EBITDA Margin (%)"].iloc[-1]
        npm_p_now   = prof["Net Profit Margin (%)"].iloc[0]
        roe_p_now   = prof["ROE (%)"].iloc[0]
        roce_p_now  = prof["ROCE (%)"].iloc[0]
        ebitda_dir  = "expanded ▲" if ebitda_now > ebitda_old else "compressed ▼"
        roce_text   = f"ROCE of <b>{roce_p_now:.1f}%</b> — {'above typical WACC range (9–12%), value creation is likely ✓' if roce_p_now > 12 else 'within or below typical WACC range — check if company is earning above its cost of capital'}."
        insight(
            f"{ticker}'s EBITDA Margin is <b>{ebitda_now:.1f}%</b> ({ebitda_dir} from {ebitda_old:.1f}%), "
            f"Net Profit Margin is <b>{npm_p_now:.1f}%</b>, ROE is <b>{roe_p_now:.1f}%</b>. "
            f"{roce_text}",
            icon="📊", color=GREEN if ebitda_now > ebitda_old else RED
        )
        c1, c2 = st.columns(2)
        with c1:
            line(prof, "EBITDA Margin (%)",        CYAN,   bench=15, bench_label="15% — healthy benchmark")
            line(prof, "Net Profit Margin (%)",     GREEN)
        with c2:
            line(prof, "ROE (%)",                   PURPLE, bench=15, bench_label="15% — healthy benchmark")
            line(prof, "ROCE (%)",                  GOLD)

    # ── 2. LIQUIDITY ───────────────────────────────────────────────
    with st.expander("💧  Liquidity Ratios", expanded=False):
        liq = all_r["liquidity"]
        st.dataframe(liq.style.format(fmt), use_container_width=True)
        # Data-driven liquidity insight
        cr_vals = liq["Current Ratio (x)"].dropna()
        qr_vals = liq["Quick Ratio (x)"].dropna()
        if len(cr_vals) >= 2:
            cr_latest = cr_vals.iloc[0]; cr_oldest = cr_vals.iloc[-1]
            cr_trend = "improving ▲" if cr_latest > cr_oldest else "declining ▼"
            cr_status = "healthy (>2x)" if cr_latest >= 2 else ("watch zone (1–2x)" if cr_latest >= 1 else "⚠️ risk zone (<1x)")
            qr_latest = qr_vals.iloc[0] if len(qr_vals) > 0 else 0
            qr_status = "above 1x ✓" if qr_latest >= 1 else "below 1x — may need to liquidate inventory to meet obligations"
            insight(
                f"{ticker}'s Current Ratio is <b>{cr_latest:.1f}x</b> ({cr_status}), "
                f"trending <b>{cr_trend}</b> from {cr_oldest:.1f}x. "
                f"Quick Ratio is <b>{qr_latest:.1f}x</b> — {qr_status}.",
                icon="💧", color=GREEN if cr_latest >= 2 else (GOLD if cr_latest >= 1 else RED)
            )
        else:
            insight("<b>Current Ratio > 2x</b>: Healthy. <b>Quick Ratio > 1x</b>: Can meet obligations without selling inventory.", icon="💧")
        c1, c2 = st.columns(2)
        with c1: line(liq, "Current Ratio (x)", CYAN,  bench=2.0, bench_label="Healthy ≥ 2x")
        with c2: line(liq, "Quick Ratio (x)",   GREEN, bench=1.0, bench_label="Healthy ≥ 1x")

    # ── 3. SOLVENCY ────────────────────────────────────────────────
    with st.expander("🏦  Solvency / Leverage Ratios", expanded=False):
        sol = all_r["solvency"]
        st.dataframe(sol.style.format(fmt), use_container_width=True)
        insight(
            "<b>Interest Coverage > 3x</b>: Comfortable. <b>1.5–3x</b>: Watch closely. <b>< 1.5x</b>: Distress ⚠️ "
            "<b>Net Debt/EBITDA:</b> < 2x safe · 4–6x LBO entry · > 6x distressed. "
            "Most LBOs target 4–6x at close and aim to delever below 3x within 5 years.",
            icon="🏦"
        )
        c1, c2, c3 = st.columns(3)
        with c1: line(sol, "D/E Ratio (x)",          RED)
        with c2: line(sol, "Interest Coverage (x)",  GREEN, bench=3.0, bench_label="Healthy ≥ 3x")
        with c3: line(sol, "Net Debt / EBITDA (x)",  GOLD,  bench=2.0, bench_label="Conservative ≤ 2x")

    # ── 4. EFFICIENCY ──────────────────────────────────────────────
    with st.expander("⚙️  Efficiency / Working Capital Ratios", expanded=False):
        eff = all_r["efficiency"]
        st.dataframe(eff.style.format(fmt), use_container_width=True)
        # Data-driven efficiency insight
        ccc_vals = eff["Cash Conversion Cycle (Days)"].dropna()
        at_vals  = eff["Asset Turnover (x)"].dropna()
        if len(ccc_vals) >= 2:
            ccc_latest = ccc_vals.iloc[0]; ccc_oldest = ccc_vals.iloc[-1]
            ccc_trend  = "improving ▲ (shrinking)" if ccc_latest < ccc_oldest else "worsening ▼ (expanding)"
            ccc_type   = "negative CCC — collects before paying suppliers 🏆" if ccc_latest < 0 else f"{ccc_latest:.0f} days"
            at_latest  = at_vals.iloc[0] if len(at_vals) > 0 else 0
            insight(
                f"{ticker}'s Cash Conversion Cycle is <b>{ccc_type}</b>, "
                f"trending <b>{ccc_trend}</b> ({ccc_oldest:.0f}d → {ccc_latest:.0f}d). "
                f"Asset Turnover of <b>{at_latest:.2f}x</b> — "
                f"{'efficient asset utilisation' if at_latest > 1 else 'capital-intensive business model'}.",
                icon="⚙️", color=GREEN if ccc_latest < 0 else (GOLD if ccc_latest < 60 else RED)
            )
        else:
            insight("<b>CCC = DIO + DSO − DPO.</b> Lower is better. Negative CCC = major working capital advantage.", icon="⚙️")
        eff_r  = eff.reset_index()
        yrs_e  = eff_r["Year"].astype(str).tolist()
        fig_wc = go.Figure()
        fig_wc.add_trace(go.Bar(x=yrs_e, y=eff_r["DIO - Inventory Days"],
            name="DIO (Inventory)", marker_color="rgba(0,212,255,0.7)",
            hovertemplate="<b>DIO:</b> %{y:.1f} days<extra></extra>"))
        fig_wc.add_trace(go.Bar(x=yrs_e, y=eff_r["DSO - Receivable Days"],
            name="DSO (Receivables)", marker_color="rgba(0,255,135,0.7)",
            hovertemplate="<b>DSO:</b> %{y:.1f} days<extra></extra>"))
        fig_wc.add_trace(go.Bar(x=yrs_e, y=[-v for v in eff_r["DPO - Payable Days"]],
            name="DPO (Payables) — offsets", marker_color="rgba(255,71,87,0.7)",
            customdata=eff_r["DPO - Payable Days"],
            hovertemplate="<b>DPO:</b> %{customdata:.1f} days<extra></extra>"))
        fig_wc.add_trace(go.Scatter(x=yrs_e, y=eff_r["Cash Conversion Cycle (Days)"],
            name="CCC (Net)", mode="lines+markers+text",
            text=[f"{v:.0f}d" for v in eff_r["Cash Conversion Cycle (Days)"]],
            textposition="top center", textfont=dict(color=GOLD, size=11),
            line=dict(color=GOLD, width=3, dash="dot"),
            marker=dict(size=9, color=GOLD, line=dict(color=BG, width=2)),
            hovertemplate="<b>CCC:</b> %{y:.1f} days<extra></extra>"))
        fig_wc.add_hline(y=0, line_color="rgba(255,255,255,0.15)", line_width=1.5)
        fig_wc.update_layout(**{**BASE, "barmode":"relative",
            "title": f"{ticker} — Working Capital: DIO + DSO − DPO = CCC", "height": 420})
        st.plotly_chart(fig_wc, use_container_width=True)
        insight(
            "<b>Blue bars</b> = inventory days (DIO). <b>Green bars</b> = receivable days (DSO). "
            "<b>Red bars</b> = payable days (DPO) subtracted as a benefit. "
            "<b>Gold line</b> = net CCC. Below zero = cash-positive working capital cycle.",
            color=GOLD
        )
        c1, c2 = st.columns(2)
        with c1: line(eff, "Cash Conversion Cycle (Days)", GOLD)
        with c2: line(eff, "Asset Turnover (x)",           CYAN)

    # ── 5. VALUATION ───────────────────────────────────────────────
    with st.expander("💰  Valuation Multiples", expanded=False):
        val = all_r["valuation"]
        st.dataframe(val.style.format(fmt), use_container_width=True)
        # Data-driven valuation insight
        ev_ebitda_now = val["EV / EBITDA (x)"].iloc[0]
        ev_rev_now    = val["EV / Revenue (x)"].iloc[0]
        pe_now        = inf.get("trailingPE")
        ev_text = ""
        if ev_ebitda_now and not (isinstance(ev_ebitda_now, float) and (np.isnan(ev_ebitda_now) or np.isinf(ev_ebitda_now))):
            if ev_ebitda_now > 20:
                ev_label = "premium valuation — market pricing in high growth"
            elif ev_ebitda_now > 12:
                ev_label = "moderate valuation — in line with quality mid-caps"
            else:
                ev_label = "below average — either undervalued or reflects risk"
            ev_text = f"EV/EBITDA of <b>{ev_ebitda_now:.1f}x</b> — {ev_label}. "
        pe_text = f"Trailing P/E of <b>{pe_now:.1f}x</b>." if pe_now else ""
        insight(
            f"{ticker}: {ev_text}{pe_text} "
            f"EV/Revenue of <b>{ev_rev_now:.1f}x</b>. "
            f"Compare these multiples with sector peers in the Comps tab (coming in Part 3).",
            icon="💰", color=MUTED
        )
        c1, c2, c3 = st.columns(3)
        with c1: line(val, "EV / EBITDA (x)",  PURPLE)
        with c2: line(val, "EV / Revenue (x)",  CYAN)
        with c3: line(val, "EV / EBIT (x)",     GREEN)

        st.markdown("---")
        sec("Live Market Multiples", "Current data from Yahoo Finance")
        lm1, lm2, lm3, lm4 = st.columns(4)
        lm1.metric("P/E Trailing", f"{inf.get('trailingPE'):.1f}x"  if inf.get("trailingPE")  else "N/A")
        lm2.metric("P/E Forward",  f"{inf.get('forwardPE'):.1f}x"   if inf.get("forwardPE")   else "N/A")
        lm3.metric("P/B Ratio",    f"{inf.get('priceToBook'):.2f}x" if inf.get("priceToBook") else "N/A")
        lm4.metric("PEG Ratio",    f"{inf.get('pegRatio'):.2f}"     if inf.get("pegRatio")    else "N/A")


# ──────────────────────────────────────────────────────────────────
# TAB 5 — DCF VALUATION
# ──────────────────────────────────────────────────────────────────
with tab5:
    sec("DCF Valuation", "Intrinsic value based on projected free cash flows")
    insight(
        "<b>IB Core Concept:</b> Unlike comps which tell you what the market is paying, "
        "a DCF tells you what a company is <i>worth</i> based on future cash generation. "
        "FCFF is discounted at WACC to get Enterprise Value. Subtract Net Debt → Equity Value → Per-Share Price.",
        icon="📐"
    )

    # ── Initialise DCF engine ──────────────────────────────────────
    dcf_engine = DCFValuation(inc, bs, cf, inf)
    auto_assum = dcf_engine.auto_assumptions()
    hist_fcff  = dcf_engine.historical_fcff()

    # ── Historical FCFF ───────────────────────────────────────────
    sec("Historical FCFF", "How much free cash flow has the company generated?")
    st.dataframe(hist_fcff.style.format("{:.2f}"), use_container_width=True)

    # Historical FCFF bar chart
    fig_hfcff = go.Figure()
    hf_years  = [str(y) for y in hist_fcff.index]
    hf_vals   = hist_fcff['FCFF'].tolist()
    fig_hfcff.add_trace(go.Bar(
        x=hf_years, y=hf_vals,
        marker_color=[GREEN if v >= 0 else RED for v in hf_vals],
        text=[f"₹{v:,.0f}" for v in hf_vals],
        textposition="outside",
        textfont=dict(color=TEXT, size=11),
        hovertemplate="<b>FCFF %{x}:</b> ₹%{y:,.0f} Cr<extra></extra>",
    ))
    fig_hfcff.add_hline(y=0, line_color="rgba(255,255,255,0.2)", line_width=1)
    chart(fig_hfcff, f"{ticker} — Historical FCFF (₹ Cr)", 320)
    st.plotly_chart(fig_hfcff, use_container_width=True)
    # Data quality check
    avg_hist_fcff = hist_fcff['FCFF'].mean()
    if avg_hist_fcff < 0:
        st.markdown(f"""
        <div style="background:rgba(255,71,87,0.08);border:1px solid rgba(255,71,87,0.3);
                    border-left:4px solid #ff4757;border-radius:0 12px 12px 0;
                    padding:13px 18px;margin:4px 0 20px 0;line-height:1.65;">
            <span style="font-size:15px;margin-right:8px;">⚠️</span>
            <span style="color:#ccd6f6;font-size:13px;">
            <b>Data Quality Note:</b> yfinance is reporting negative historical FCFF for {ticker}.
            This often happens for conglomerates (Reliance, Tata, Adani) where yfinance includes
            <b>financial investments and acquisitions</b> as CapEx, inflating it artificially.
            The CapEx slider has been capped at 8% — adjust it downward further if needed
            to reflect the company's true maintenance/growth capex.
            </span>
        </div>
        """, unsafe_allow_html=True)
    else:
        insight(
            "<b>What to look for:</b> Consistently positive and growing FCFF is the hallmark of a high-quality business. "
            "Negative FCFF in early years is acceptable for growth companies investing heavily in CapEx. "
            "Persistently negative FCFF in a mature company is a serious red flag.",
            color=GREEN
        )

    st.markdown("---")

    # ── Assumption Panel ──────────────────────────────────────────
    sec("Assumptions", "Auto-filled from history — adjust any value and the DCF updates instantly")

    with st.expander("⚙️  Edit Assumptions", expanded=True):

        st.markdown(f'<div style="color:{MUTED};font-size:12px;margin-bottom:16px;">All assumptions are pre-filled from {ticker}\'s historical financials. Drag any slider to override.</div>', unsafe_allow_html=True)

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.markdown(f'<div style="color:{CYAN};font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">📈 Growth</div>', unsafe_allow_html=True)
            rev_growth_base = st.slider("Base Revenue Growth (%)",  1, 35,
                int(auto_assum['rev_growth_base'] * 100), key="rg_base") / 100
            rev_growth_bull = st.slider("Bull Revenue Growth (%)",  1, 45,
                int(auto_assum['rev_growth_bull'] * 100), key="rg_bull") / 100
            rev_growth_bear = st.slider("Bear Revenue Growth (%)",  1, 30,
                int(auto_assum['rev_growth_bear'] * 100), key="rg_bear") / 100
            terminal_growth = st.slider("Terminal Growth Rate (%)", 1, 8,
                int(auto_assum['terminal_growth'] * 100), key="tg") / 100

        with col_b:
            st.markdown(f'<div style="color:{PURPLE};font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">💰 Margins & Costs</div>', unsafe_allow_html=True)
            ebit_margin = st.slider("EBIT Margin (%)",    1, 50,
                int(auto_assum['ebit_margin'] * 100), key="em") / 100
            tax_rate    = st.slider("Tax Rate (%)",       10, 40,
                int(auto_assum['tax_rate'] * 100), key="tr") / 100
            capex_pct   = st.slider("CapEx (% of Rev)",  1, 30,
                int(auto_assum['capex_pct'] * 100), key="cx") / 100
            da_pct      = st.slider("D&A (% of Rev)",    1, 15,
                int(auto_assum['da_pct'] * 100), key="da") / 100

        with col_c:
            st.markdown(f'<div style="color:{GOLD};font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">⚖️ WACC</div>', unsafe_allow_html=True)
            wacc_input  = st.slider("WACC (%)",           7, 20,
                int(auto_assum['wacc'] * 100), key="wacc") / 100
            beta_input  = st.slider("Beta",               30, 250,
                int(auto_assum['beta'] * 100), key="beta") / 100

            st.markdown(f'<div style="color:{MUTED};font-size:11px;margin-top:8px;">Risk-Free Rate: <b style="color:{TEXT};">{auto_assum["risk_free"]*100:.1f}%</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:{MUTED};font-size:11px;">Equity Risk Premium: <b style="color:{TEXT};">{auto_assum["erp"]*100:.1f}%</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:{MUTED};font-size:11px;">Cost of Equity: <b style="color:{CYAN};">{(auto_assum["risk_free"] + beta_input * auto_assum["erp"])*100:.1f}%</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:{MUTED};font-size:11px;">Cost of Debt: <b style="color:{CYAN};">{auto_assum["cost_of_debt"]*100:.1f}%</b></div>', unsafe_allow_html=True)

    # Build final assumptions dict from sliders
    final_assum = {**auto_assum,
        'rev_growth_base': rev_growth_base,
        'rev_growth_bull': rev_growth_bull,
        'rev_growth_bear': rev_growth_bear,
        'terminal_growth': terminal_growth,
        'ebit_margin':     ebit_margin,
        'tax_rate':        tax_rate,
        'capex_pct':       capex_pct,
        'da_pct':          da_pct,
        'wc_pct':          auto_assum['wc_pct'],
        'wacc':            wacc_input,
        'beta':            beta_input,
    }

    # ── Run DCF ───────────────────────────────────────────────────
    dcf_results = dcf_engine.run(final_assum)

    st.markdown("---")
    sec("Valuation Results", "Base · Bull · Bear scenarios")

    # Verdict cards — one per scenario
    sc_cols = st.columns(3)
    sc_colors = {
        '🟢 Undervalued': GREEN,
        '🟡 Fairly Valued': GOLD,
        '🔴 Overvalued': RED,
    }
    sc_glows = {
        '🟢 Undervalued': "0,255,135",
        '🟡 Fairly Valued': "255,215,0",
        '🔴 Overvalued': "255,71,87",
    }

    for col, (scenario, label) in zip(sc_cols, [
        ('base', '📊 Base Case'),
        ('bull', '🚀 Bull Case'),
        ('bear', '🐻 Bear Case'),
    ]):
        r       = dcf_results[scenario]
        vc      = sc_colors.get(r['verdict'], CYAN)
        vg      = sc_glows.get(r['verdict'], "0,212,255")
        up_sign = "▲" if r['upside_pct'] >= 0 else "▼"
        up_col  = GREEN if r['upside_pct'] >= 0 else RED

        col.markdown(f"""
        <div style="
            background:rgba(13,27,42,0.88);
            border:2px solid {vc};
            border-radius:16px; padding:22px 18px;
            text-align:center;
            box-shadow: 0 0 30px rgba({vg},0.15);
        ">
            <div style="color:{MUTED};font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;">{label}</div>
            <div style="font-size:13px;color:{MUTED};margin:6px 0;">Growth: <b style="color:{TEXT};">{r['rev_growth']}% p.a.</b></div>
            <div style="font-size:36px;font-weight:900;color:{CYAN};margin:10px 0;
                        text-shadow:0 0 20px rgba(0,212,255,0.4);">
                ₹{r['intrinsic_price']:,.0f}
            </div>
            <div style="font-size:13px;color:{MUTED};">Intrinsic Value / Share</div>
            <div style="font-size:15px;font-weight:700;color:{up_col};margin-top:8px;">
                {up_sign} {abs(r['upside_pct']):.1f}% vs ₹{r['current_price']:,.0f}
            </div>
            <div style="font-size:14px;margin-top:10px;">{r['verdict']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Per-scenario detail ────────────────────────────────────────
    sc_tab_base, sc_tab_bull, sc_tab_bear = st.tabs([
        "📊  Base Case", "🚀  Bull Case", "🐻  Bear Case"
    ])

    def render_scenario(r, scenario_label, color):
        proj  = r['projection']
        years = proj.index.tolist()

        # Projection table
        sec("Projected FCFF", "5-year forward projection")
        st.dataframe(proj.style.format("{:.2f}"), use_container_width=True)

        # FCFF projection bar chart
        fcff_vals = proj['FCFF (₹ Cr)'].tolist()
        rev_vals  = proj['Revenue (₹ Cr)'].tolist()

        fig_proj = make_subplots(specs=[[{"secondary_y": True}]])
        fig_proj.add_trace(go.Bar(
            x=years, y=rev_vals, name="Revenue",
            marker_color="rgba(0,212,255,0.5)",
            hovertemplate="<b>Revenue:</b> ₹%{y:,.0f} Cr<extra></extra>",
        ), secondary_y=False)
        fig_proj.add_trace(go.Scatter(
            x=years, y=fcff_vals, name="FCFF",
            mode="lines+markers",
            line=dict(color=color, width=3),
            marker=dict(size=10, color=color, line=dict(color=BG, width=2)),
            hovertemplate="<b>FCFF:</b> ₹%{y:,.0f} Cr<extra></extra>",
        ), secondary_y=True)
        fig_proj.update_layout(**{**BASE,
            "title": f"{scenario_label} — Revenue & FCFF Projection",
            "height": 370, "barmode": "group",
        })
        fig_proj.update_yaxes(title_text="Revenue (₹ Cr)", secondary_y=False,
                              gridcolor="rgba(136,146,176,0.08)")
        fig_proj.update_yaxes(title_text="FCFF (₹ Cr)", color=color,
                              secondary_y=True, showgrid=False)
        st.plotly_chart(fig_proj, use_container_width=True)

        # DCF Bridge — waterfall from components to per-share price
        st.markdown("---")
        sec("DCF Bridge", "How we get from FCFF → Enterprise Value → Share Price")

        bridge_labels = [
            "PV of FCFFs", "PV Terminal Value",
            "Enterprise Value", "Less: Net Debt",
            "Equity Value", "Per Share (₹)"
        ]
        bridge_vals = [
            r['sum_pv_fcff'],
            r['pv_terminal_value'],
            r['enterprise_value'],
            -r['net_debt'],
            r['equity_value'],
            r['intrinsic_price'],
        ]
        bridge_measure = ["relative","relative","total","relative","total","total"]
        bridge_colors  = [CYAN, PURPLE, CYAN, RED if r['net_debt'] > 0 else GREEN,
                          GREEN, GOLD]

        fig_bridge = go.Figure(go.Waterfall(
            orientation="v",
            measure=bridge_measure,
            x=bridge_labels,
            y=bridge_vals,
            connector=dict(line=dict(color="rgba(255,255,255,0.15)", width=1)),
            increasing=dict(marker=dict(color=GREEN)),
            decreasing=dict(marker=dict(color=RED)),
            totals=dict(marker=dict(color=CYAN)),
            text=[f"₹{v:,.0f}" for v in bridge_vals],
            textposition="outside",
            textfont=dict(color=TEXT, size=11),
            hovertemplate="<b>%{x}:</b> ₹%{y:,.0f} Cr<extra></extra>",
        ))
        chart(fig_bridge, f"{scenario_label} — DCF Bridge (₹ Cr)", 420)
        st.plotly_chart(fig_bridge, use_container_width=True)
        insight(
            f"<b>Terminal Value</b> represents <b>{r['tv_pct_of_ev']:.0f}%</b> of total Enterprise Value — "
            "this is typical (60–80% is normal). It means the terminal growth rate assumption is the most sensitive input. "
            "The sensitivity table below shows how the share price changes across different WACC and growth combinations.",
            color=color
        )

        # Key metrics row
        st.markdown("---")
        km1, km2, km3, km4, km5 = st.columns(5)
        km1.metric("PV of FCFFs",       f"₹{r['sum_pv_fcff']:,.0f} Cr")
        km2.metric("PV Terminal Value",  f"₹{r['pv_terminal_value']:,.0f} Cr")
        km3.metric("Enterprise Value",   f"₹{r['enterprise_value']:,.0f} Cr")
        km4.metric("Equity Value",       f"₹{r['equity_value']:,.0f} Cr")
        km5.metric("Intrinsic Price",    f"₹{r['intrinsic_price']:,.0f}")

    with sc_tab_base:
        render_scenario(dcf_results['base'], "Base Case", CYAN)
    with sc_tab_bull:
        render_scenario(dcf_results['bull'], "Bull Case", GREEN)
    with sc_tab_bear:
        render_scenario(dcf_results['bear'], "Bear Case", RED)

    # ── Sensitivity Table ──────────────────────────────────────────
    st.markdown("---")
    sec("Sensitivity Analysis", "Implied share price across WACC × Terminal Growth Rate")
    insight(
        "<b>How to read:</b> Each cell = intrinsic share price under that WACC + growth combination. "
        "<b>Green</b> = above current market price (upside). <b>Red</b> = below current price (downside). "
        "The center cell matches your base assumptions. This is standard in every IB pitch book.",
        icon="🎯"
    )

    sens_df      = dcf_engine.sensitivity(final_assum)
    current_px   = final_assum['current_price']

    # Build plotly heatmap for sensitivity
    z_vals  = []
    z_text  = []
    for row_label in sens_df.index:
        row_z, row_t = [], []
        for col_label in sens_df.columns:
            val = sens_df.loc[row_label, col_label]
            row_z.append(val if val is not None else 0)
            row_t.append(f"₹{val:,.0f}" if val is not None else "—")
        z_vals.append(row_z)
        z_text.append(row_t)

    # Color scale: red below current price, green above
    fig_sens = go.Figure(go.Heatmap(
        z=z_vals,
        x=list(sens_df.columns),
        y=list(sens_df.index),
        text=z_text,
        texttemplate="%{text}",
        textfont=dict(color="white", size=12, family="Inter"),
        colorscale=[
            [0.0,  "rgba(255,71,87,0.85)"],
            [0.45, "rgba(255,71,87,0.3)"],
            [0.5,  "rgba(255,215,0,0.5)"],
            [0.55, "rgba(0,255,135,0.3)"],
            [1.0,  "rgba(0,255,135,0.85)"],
        ],
        zmid=current_px,
        showscale=True,
        colorbar=dict(
            title=dict(text="Share Price (₹)", font=dict(color=MUTED)),
            tickfont=dict(color=MUTED),
            bgcolor="rgba(13,27,42,0.8)",
            bordercolor="rgba(0,212,255,0.2)",
        ),
        xgap=3, ygap=3,
        hovertemplate="WACC: %{y}<br>Growth: %{x}<br>Price: %{text}<extra></extra>",
    ))

    # Add current price annotation line
    fig_sens.add_annotation(
        x=0.5, y=1.08, xref="paper", yref="paper",
        text=f"Current Market Price: ₹{current_px:,.0f}  |  Green = upside · Red = downside",
        showarrow=False,
        font=dict(color=MUTED, size=12),
        xanchor="center",
    )

    chart(fig_sens, f"{ticker} — Sensitivity: WACC × Terminal Growth (Implied Share Price)", 380)
    fig_sens.update_layout(
        xaxis=dict(title="Terminal Growth Rate →", tickfont=dict(color=MUTED)),
        yaxis=dict(title="WACC ↓", tickfont=dict(color=MUTED)),
        margin=dict(t=80, b=50, l=70, r=80),
    )
    st.plotly_chart(fig_sens, use_container_width=True)


# ──────────────────────────────────────────────────────────────────
# TAB 6 — COMPARABLE COMPANY ANALYSIS
# ──────────────────────────────────────────────────────────────────
with tab6:
    sec("Comparable Company Analysis", "How does the market price similar companies?")
    insight(
        "<b>IB Core Concept:</b> Comps tells you what the <i>market</i> is currently paying "
        "for similar businesses. Apply those multiples to your company's own financials "
        "to get a market-implied valuation range. EV-based multiples (EV/EBITDA) are preferred "
        "over P/E because they're capital-structure neutral.",
        icon="🏢"
    )

    # ── Initialise comps engine ────────────────────────────────────
    comps_engine  = CompsAnalysis(ticker, inf, inc, bs, cf)
    suggested     = comps_engine.suggest_peers()

    # ── Peer selector ─────────────────────────────────────────────
    sec("Select Peer Companies", "Auto-suggested from your sector — add or remove any NSE ticker")

    col_peers, col_add = st.columns([3, 1])
    with col_peers:
        selected_peers = st.multiselect(
            "Peer Tickers (NSE)",
            options=suggested + ["TCS","INFY","WIPRO","HCLTECH","TECHM",
                                  "HDFCBANK","ICICIBANK","KOTAKBANK","AXISBANK","SBIN",
                                  "RELIANCE","ONGC","HINDUNILVR","NESTLEIND","MARUTI",
                                  "TATAMOTORS","LT","SUNPHARMA","DRREDDY","TATASTEEL",
                                  "BHARTIARTL","ZOMATO","ETERNAL","BAJFINANCE","ADANIPORTS"],
            default=suggested,
            help="Select 3–7 peers for the best analysis",
        )
    with col_add:
        custom_peer = st.text_input("Add custom ticker", placeholder="e.g. BAJAJFINSV")
        if custom_peer:
            custom_peer = custom_peer.upper().strip()
            if custom_peer not in selected_peers:
                selected_peers = selected_peers + [custom_peer]

    if not selected_peers:
        st.warning("Please select at least one peer company.")
        st.stop()

    # ── Fetch data ────────────────────────────────────────────────
    with st.spinner(f"Fetching live data for {len(selected_peers)} peers…"):
        comps_table = comps_engine.build_table(selected_peers)

    if comps_table.empty:
        st.error("Could not fetch peer data. Check ticker symbols and try again.")
        st.stop()

    st.markdown("---")

    # ── Full comps table ──────────────────────────────────────────
    sec("Comps Table", f"{ticker} vs {len(selected_peers)} peers — live market data")

    display_cols = ["Ticker","Company","Price (₹)","Mkt Cap (Cr)",
                    "EV/EBITDA","EV/Revenue","EV/EBIT","P/E","P/B"]
    display_df   = comps_table[[c for c in display_cols if c in comps_table.columns]].copy()

    # Colour-code: target row is highlighted, multiples coloured vs median
    def style_comps(df):
        styled = df.style
        # Highlight target row (★)
        def highlight_target(row):
            if str(row["Ticker"]).startswith("★"):
                return [f"background:rgba(0,212,255,0.1);font-weight:700;color:{CYAN}"] * len(row)
            return [""] * len(row)
        styled = styled.apply(highlight_target, axis=1)

        # Colour multiples: green if below median (cheap), red if above (expensive)
        for mult in ["EV/EBITDA","EV/Revenue","EV/EBIT","P/E","P/B"]:
            if mult not in df.columns:
                continue
            vals   = df[mult].dropna()
            median = vals.median() if len(vals) > 0 else None
            if median:
                def colour_mult(val, med=median):
                    if pd.isna(val) or val is None:
                        return ""
                    if val < med * 0.85:
                        return f"color:{GREEN};font-weight:600"
                    elif val > med * 1.15:
                        return f"color:{RED};font-weight:600"
                    return f"color:{GOLD}"
                styled = styled.map(colour_mult, subset=[mult])

        return styled

    st.dataframe(
        style_comps(display_df).format(
            {c: "{:.1f}x" for c in ["EV/EBITDA","EV/Revenue","EV/EBIT","P/E","P/B"]
             if c in display_df.columns},
            na_rep="—"
        ),
        use_container_width=True,
        height=min(60 + len(display_df) * 38, 420),
    )

    # Target vs peers colour legend
    st.markdown(f"""
    <div style="display:flex;gap:20px;margin:8px 0 4px 0;font-size:12px;">
        <span style="color:{CYAN};">★ = {ticker} (target)</span>
        <span style="color:{GREEN};">Green = cheap vs peers (&lt;85% of median)</span>
        <span style="color:{GOLD};">Gold = in line with peers</span>
        <span style="color:{RED};">Red = premium vs peers (&gt;115% of median)</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Multiple comparison charts ────────────────────────────────
    sec("Multiple Comparison", "Visual comparison of each valuation multiple across peers")

    mult_cols = [m for m in ["EV/EBITDA","EV/Revenue","EV/EBIT","P/E","P/B"]
                 if m in comps_table.columns]

    for i in range(0, len(mult_cols), 2):
        row_cols = st.columns(2)
        for j, mult in enumerate(mult_cols[i:i+2]):
            with row_cols[j]:
                chart_df = comps_table[["Ticker", mult]].dropna()
                if chart_df.empty:
                    continue

                # Colour target bar differently
                bar_colors = [
                    CYAN if str(t).startswith("★") else
                    "rgba(167,139,250,0.7)"
                    for t in chart_df["Ticker"]
                ]
                median_val = chart_df[mult][
                    ~chart_df["Ticker"].str.startswith("★")
                ].median()

                fig_mult = go.Figure(go.Bar(
                    x=chart_df["Ticker"].str.replace("★ ", ""),
                    y=chart_df[mult],
                    marker_color=bar_colors,
                    text=[f"{v:.1f}x" for v in chart_df[mult]],
                    textposition="outside",
                    textfont=dict(color=TEXT, size=11),
                    hovertemplate="<b>%{x}:</b> %{y:.2f}x<extra></extra>",
                ))
                if median_val:
                    fig_mult.add_hline(
                        y=median_val,
                        line_dash="dot", line_color=GOLD, line_width=1.5,
                        annotation_text=f"Peer median: {median_val:.1f}x",
                        annotation_font=dict(color=GOLD, size=10),
                        annotation_position="top left",
                    )
                fig_mult.update_layout(**{**BASE,
                    "title": mult,
                    "height": 300,
                    "margin": dict(t=50, b=50, l=40, r=20),
                    "xaxis": dict(type="category", showgrid=False,
                                 tickfont=dict(color=MUTED, size=10)),
                    "yaxis": dict(title=f"{mult} (x)",
                                 gridcolor="rgba(136,146,176,0.08)"),
                    "showlegend": False,
                })
                st.plotly_chart(fig_mult, use_container_width=True)

    st.markdown("---")

    # ── Peer summary stats ─────────────────────────────────────────
    sec("Peer Group Statistics", "Min / Median / Mean / Max across the peer group")
    stats_df = comps_engine.peer_stats(comps_table)
    if not stats_df.empty:
        st.dataframe(
            stats_df.style.format(lambda x: f"{x:.2f}x" if pd.notna(x) else "—"),
            use_container_width=True,
        )
    insight(
        "<b>Median is the anchor.</b> Mean can be skewed by outliers. "
        "The Min–Max range tells you how wide the market's view is — "
        "a wide range means sector re-rating is happening or peers have very different growth profiles.",
        icon="📊", color=CYAN
    )

    st.markdown("---")

    # ── Implied valuation ──────────────────────────────────────────
    sec("Implied Valuation Range",
        f"Applying peer multiples to {ticker}'s financials → implied share price")

    implied_df = comps_engine.implied_valuation(stats_df)
    if not implied_df.empty:
        current_px = inf.get("currentPrice") or inf.get("regularMarketPrice") or 0

        # Render as custom cards — one per multiple
        imp_cols = st.columns(len(implied_df))
        for col, (mult, row) in zip(imp_cols, implied_df.iterrows()):
            med_px = row.get("Implied Price (Med)")
            min_px = row.get("Implied Price (Min)")
            max_px = row.get("Implied Price (Max)")
            upside = row.get("Upside (Median) %")

            if med_px is None:
                col.markdown(f"""
                <div style="background:rgba(13,27,42,0.8);border:1px solid rgba(255,255,255,0.08);
                            border-radius:12px;padding:16px;text-align:center;">
                    <div style="color:{MUTED};font-size:11px;font-weight:700;
                                text-transform:uppercase;">{mult}</div>
                    <div style="color:{MUTED};font-size:13px;margin-top:8px;">N/A</div>
                </div>
                """, unsafe_allow_html=True)
                continue

            up_col  = GREEN if (upside or 0) >= 0 else RED
            up_sign = "▲" if (upside or 0) >= 0 else "▼"
            verdict = "Undervalued" if (upside or 0) > 15 else \
                      ("Overvalued" if (upside or 0) < -15 else "Fair Value")
            v_col   = GREEN if verdict == "Undervalued" else \
                      (RED if verdict == "Overvalued" else GOLD)

            col.markdown(f"""
            <div style="background:rgba(13,27,42,0.88);
                        border:1px solid rgba(0,212,255,0.15);
                        border-top:3px solid {v_col};
                        border-radius:12px;padding:16px;text-align:center;">
                <div style="color:{MUTED};font-size:11px;font-weight:700;
                            text-transform:uppercase;letter-spacing:0.08em;">{mult}</div>
                <div style="font-size:10px;color:{MUTED};margin:4px 0;">
                    ₹{min_px:,.0f} — ₹{max_px:,.0f}
                </div>
                <div style="font-size:26px;font-weight:800;color:{CYAN};margin:6px 0;
                            text-shadow:0 0 15px rgba(0,212,255,0.3);">
                    ₹{med_px:,.0f}
                </div>
                <div style="font-size:11px;color:{MUTED};">Median implied</div>
                <div style="font-size:13px;color:{up_col};font-weight:700;margin-top:6px;">
                    {up_sign} {abs(upside or 0):.1f}% vs ₹{current_px:,.0f}
                </div>
                <div style="font-size:12px;color:{v_col};margin-top:4px;">{verdict}</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Range bar chart ────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        sec("Implied Price Range Chart", "The spread from Min to Max peer multiple")

        valid_rows = implied_df[implied_df["Implied Price (Med)"].notna()]
        if not valid_rows.empty:
            fig_range = go.Figure()

            # Min-Max range bars
            fig_range.add_trace(go.Bar(
                name="Price Range (Min–Max)",
                x=valid_rows.index,
                y=valid_rows["Implied Price (Max)"] - valid_rows["Implied Price (Min)"],
                base=valid_rows["Implied Price (Min)"],
                marker_color="rgba(167,139,250,0.25)",
                marker_line_width=0,
                hovertemplate="<b>%{x}</b><br>Min: ₹%{base:,.0f}<br>Max: ₹%{y:,.0f}<extra></extra>",
            ))
            # Median dots
            fig_range.add_trace(go.Scatter(
                name="Median Implied Price",
                x=valid_rows.index,
                y=valid_rows["Implied Price (Med)"],
                mode="markers",
                marker=dict(size=14, color=CYAN, symbol="diamond",
                            line=dict(color=BG, width=2)),
                hovertemplate="<b>%{x} Median:</b> ₹%{y:,.0f}<extra></extra>",
            ))
            # Current price line
            fig_range.add_hline(
                y=current_px,
                line_dash="dash", line_color=GOLD, line_width=2,
                annotation_text=f"Current: ₹{current_px:,.0f}",
                annotation_font=dict(color=GOLD, size=12),
                annotation_position="top right",
            )
            fig_range.update_layout(**{**BASE,
                "title": f"{ticker} — Implied Valuation Range by Multiple",
                "height": 380,
                "xaxis": dict(type="category", showgrid=False,
                             tickfont=dict(color=MUTED)),
                "yaxis": dict(title="Implied Share Price (₹)",
                             gridcolor="rgba(136,146,176,0.08)"),
                "barmode": "overlay",
            })
            st.plotly_chart(fig_range, use_container_width=True)

            # Data-driven insight
            med_prices = valid_rows["Implied Price (Med)"].dropna()
            overall_med = med_prices.median()
            overall_up  = safe_div(overall_med - current_px, current_px) * 100 \
                          if current_px > 0 else 0
            verdict_overall = "trading at a discount to peers" if overall_up > 10 \
                              else ("trading at a premium to peers" if overall_up < -10 \
                                    else "fairly valued relative to peers")
            insight(
                f"Across all multiples, the median implied price for {ticker} is "
                f"<b>₹{overall_med:,.0f}</b> vs current market price of <b>₹{current_px:,.0f}</b>. "
                f"{ticker} appears to be <b>{verdict_overall}</b> "
                f"({'▲' if overall_up >= 0 else '▼'} {abs(overall_up):.1f}%). "
                f"The <b>EV/EBITDA</b> implied price is typically the most reliable "
                f"anchor in M&A analysis.",
                color=GREEN if overall_up > 10 else (RED if overall_up < -10 else GOLD)
            )


# ──────────────────────────────────────────────────────────────────
# TAB 7 — FOOTBALL FIELD CHART + RECOMMENDATION
# ──────────────────────────────────────────────────────────────────
with tab7:
    sec("Football Field Valuation", "All methodologies in one view")
    insight(
        "<b>IB Context:</b> The football field is the headline valuation slide in every pitch book. "
        "Each bar = one methodology's implied price range. The vertical line = current market price. "
        "Where the price sits relative to all bars determines the BUY / HOLD / SELL call.",
        icon="🎯"
    )

    # ── Gather inputs from previous tabs ──────────────────────────
    # DCF results — run with auto assumptions so it always works
    _dcf_engine   = DCFValuation(inc, bs, cf, inf)
    _auto_assum   = _dcf_engine.auto_assumptions()
    _dcf_results  = _dcf_engine.run(_auto_assum)

    # Comps implied — run with suggested peers
    _comps_engine = CompsAnalysis(ticker, inf, inc, bs, cf)
    _peers        = _comps_engine.suggest_peers()

    with st.spinner("Fetching peer data for Football Field…"):
        _comps_table  = _comps_engine.build_table(_peers)

    _stats_df    = _comps_engine.peer_stats(_comps_table) if not _comps_table.empty else pd.DataFrame()
    _implied_df  = _comps_engine.implied_valuation(_stats_df) if not _stats_df.empty else pd.DataFrame()

    # Ratios and piotroski for risk flags
    _ratios_dict     = ratios_obj.all_ratios()
    _piotroski_result = piotr.calculate(0)

    # ── Build Football Field ──────────────────────────────────────
    ff = FootballField(
        current_price = price,
        dcf_results   = _dcf_results,
        implied_df    = _implied_df,
        info          = inf,
    )
    bars = ff.build_bars()
    rec  = ff.recommendation(bars, _ratios_dict, _piotroski_result)

    if "error" in rec:
        st.warning(rec["error"])
        st.stop()

    # ═══════════════════════════════════════════════════════════════
    # RECOMMENDATION CARD
    # ═══════════════════════════════════════════════════════════════
    rating    = rec["rating"]
    target_px = rec["target_price"]
    upside    = rec["upside_pct"]
    conviction= rec["conviction"]

    RAT_COLOR = {
        "BUY":  (GREEN,  "0,255,135",  "📈"),
        "HOLD": (GOLD,   "255,215,0",  "📊"),
        "SELL": (RED,    "255,71,87",  "📉"),
    }
    rc, rg, ri = RAT_COLOR[rating]
    up_sign    = "▲" if upside >= 0 else "▼"
    up_col     = GREEN if upside >= 0 else RED
    conv_color = GREEN if conviction == "High" else (GOLD if conviction == "Medium" else MUTED)

    # Large rating card — no HTML comments (they break Streamlit's renderer)
    c1, c2, c3 = st.columns([1.2, 1.5, 1.5])

    with c1:
        st.markdown(f"""
        <div style="background:rgba(13,27,42,0.9);border:2px solid {rc};border-radius:16px;
                    padding:28px 20px;text-align:center;
                    box-shadow:0 0 50px rgba({rg},0.2);">
            <div style="font-size:13px;color:{MUTED};text-transform:uppercase;
                        letter-spacing:0.1em;font-weight:600;margin-bottom:10px;">Rating</div>
            <div style="font-size:60px;font-weight:900;color:{rc};line-height:1;
                        text-shadow:0 0 40px rgba({rg},0.7);">{ri} {rating}</div>
            <div style="margin-top:14px;">
                <span style="background:rgba({rg},0.1);border:1px solid rgba({rg},0.3);
                             border-radius:20px;padding:5px 16px;font-size:12px;
                             color:{conv_color};font-weight:700;">{conviction} Conviction</span>
            </div>
            <div style="margin-top:12px;font-size:12px;color:{MUTED};">
                {rec['score_above']} of {rec['total_bars']} methods imply upside
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div style="background:rgba(13,27,42,0.9);border:1px solid rgba(0,212,255,0.2);
                    border-radius:16px;padding:28px 20px;text-align:center;">
            <div style="font-size:13px;color:{MUTED};text-transform:uppercase;
                        letter-spacing:0.1em;font-weight:600;margin-bottom:10px;">12-Month Target</div>
            <div style="font-size:52px;font-weight:900;color:{CYAN};line-height:1;
                        text-shadow:0 0 30px rgba(0,212,255,0.45);">₹{target_px:,.0f}</div>
            <div style="font-size:16px;color:{up_col};font-weight:700;margin-top:10px;">
                {up_sign} {abs(upside):.1f}% from ₹{price:,.2f}
            </div>
            <div style="margin-top:10px;display:flex;justify-content:center;gap:20px;">
                <div style="text-align:center;">
                    <div style="font-size:28px;font-weight:900;color:{GREEN};">{rec['score_above']}</div>
                    <div style="font-size:10px;color:{GREEN};font-weight:600;">▲ ABOVE</div>
                </div>
                <div style="font-size:22px;color:{MUTED};padding-top:4px;">/</div>
                <div style="text-align:center;">
                    <div style="font-size:28px;font-weight:900;color:{RED};">{rec['score_below']}</div>
                    <div style="font-size:10px;color:{RED};font-weight:600;">▼ BELOW</div>
                </div>
                <div style="font-size:22px;color:{MUTED};padding-top:4px;">/</div>
                <div style="text-align:center;">
                    <div style="font-size:28px;font-weight:900;color:{MUTED};">{rec['total_bars']}</div>
                    <div style="font-size:10px;color:{MUTED};font-weight:600;">TOTAL</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div style="background:rgba(13,27,42,0.9);border:1px solid rgba(0,212,255,0.15);
                    border-left:3px solid {rc};border-radius:0 16px 16px 0;
                    padding:24px 20px;font-size:13px;color:{TEXT};line-height:1.75;">
            <div style="font-size:12px;color:{MUTED};text-transform:uppercase;
                        letter-spacing:0.1em;font-weight:600;margin-bottom:12px;">
                Research Summary
            </div>
            {rec['summary']}
        </div>
        """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # FOOTBALL FIELD CHART
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    sec("Football Field Chart", "Valuation range from every methodology — current price in gold")

    if bars:
        cat_colors = {"DCF": CYAN, "Comps": PURPLE, "52W": GOLD}
        labels     = [b["label"] for b in bars]
        lows       = [b["low"]   for b in bars]
        mids       = [b["mid"]   for b in bars]
        highs      = [b["high"]  for b in bars]
        widths     = [b["high"] - b["low"] for b in bars]
        cats       = [b["category"] for b in bars]
        bar_clrs   = [cat_colors.get(c, CYAN) for c in cats]

        fig_ff = go.Figure()

        # Invisible base bars (for stacking)
        fig_ff.add_trace(go.Bar(
            name="",
            y=labels,
            x=lows,
            orientation="h",
            marker=dict(color="rgba(0,0,0,0)"),
            hoverinfo="skip",
            showlegend=False,
        ))

        # Coloured range bars
        fig_ff.add_trace(go.Bar(
            name="Valuation Range",
            y=labels,
            x=widths,
            orientation="h",
            base=lows,
            marker=dict(
                color=[c.replace(")", ",0.35)").replace("rgb", "rgba") if c.startswith("rgb") else
                       f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.35)"
                       for c in bar_clrs],
                line=dict(
                    color=bar_clrs,
                    width=2,
                ),
            ),
            customdata=list(zip(lows, mids, highs, cats)),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Low:    ₹%{customdata[0]:,.0f}<br>"
                "Median: ₹%{customdata[1]:,.0f}<br>"
                "High:   ₹%{customdata[2]:,.0f}<br>"
                "<extra></extra>"
            ),
            showlegend=False,
        ))

        # Median dots
        fig_ff.add_trace(go.Scatter(
            name="Median Estimate",
            y=labels,
            x=mids,
            mode="markers+text",
            text=[f"₹{m:,.0f}" for m in mids],
            textposition="middle right",
            textfont=dict(color=TEXT, size=11, family="Inter"),
            marker=dict(
                size=14,
                color=bar_clrs,
                symbol="diamond",
                line=dict(color=BG, width=2),
            ),
            hovertemplate="<b>%{y}</b><br>Median: ₹%{x:,.0f}<extra></extra>",
        ))

        # Current price vertical line
        fig_ff.add_vline(
            x=price,
            line_color=GOLD,
            line_width=2.5,
            line_dash="solid",
            annotation_text=f"  Current: ₹{price:,.0f}",
            annotation_font=dict(color=GOLD, size=13, family="Inter"),
            annotation_position="top",
        )

        # Target price vertical line
        fig_ff.add_vline(
            x=target_px,
            line_color=rc,
            line_width=2,
            line_dash="dot",
            annotation_text=f"  Target: ₹{target_px:,.0f}",
            annotation_font=dict(color=rc, size=12, family="Inter"),
            annotation_position="bottom",
        )

        # Category legend annotations
        legend_html = " &nbsp;|&nbsp; ".join([
            f'<span style="color:{cat_colors[k]};">■ {k}</span>'
            for k in cat_colors
        ])

        fig_ff.update_layout(**{**BASE,
            "barmode":   "stack",
            "height":    max(380, len(bars) * 55 + 100),
            "margin":    dict(t=60, b=60, l=160, r=120),
            "xaxis": dict(
                title="Implied Share Price (₹)",
                showgrid=True,
                gridcolor="rgba(136,146,176,0.08)",
                color=MUTED,
                tickfont=dict(color=MUTED),
                tickprefix="₹",
            ),
            "yaxis": dict(
                showgrid=False,
                color=MUTED,
                tickfont=dict(color=TEXT, size=12),
                categoryorder="array",
                categoryarray=list(reversed(labels)),
            ),
            "title": dict(
                text=f"{ticker} — Football Field Valuation Chart",
                font=dict(color=CYAN, size=15),
            ),
            "legend": dict(
                x=0.01, y=1.08,
                orientation="h",
                font=dict(color=TEXT, size=12),
            ),
        })

        st.plotly_chart(fig_ff, use_container_width=True)

        # Legend
        st.markdown(f"""
        <div style="display:flex;gap:24px;margin:4px 0 8px 0;font-size:13px;flex-wrap:wrap;">
            <span style="color:{CYAN};">■ DCF — Fundamental Value</span>
            <span style="color:{PURPLE};">■ Comps — Market Multiple</span>
            <span style="color:{GOLD};">■ 52-Week Range — Market Sentiment</span>
            <span style="color:{GOLD};">— Gold line = Current Price</span>
            <span style="color:{rc};">⋯ Dotted = Target Price</span>
        </div>
        """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # METHODOLOGY BREAKDOWN TABLE
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    sec("Methodology Breakdown", "Every valuation input used to construct the football field")

    rows_tbl = []
    for b in bars:
        up_b = round((b["mid"] - price) / price * 100, 1) if price > 0 else 0
        rows_tbl.append({
            "Methodology":    b["label"],
            "Category":       b["category"],
            "Low (₹)":        f"₹{b['low']:,.0f}",
            "Median (₹)":     f"₹{b['mid']:,.0f}",
            "High (₹)":       f"₹{b['high']:,.0f}",
            "Upside (Median)":f"{'▲' if up_b >= 0 else '▼'} {abs(up_b):.1f}%",
            "Weight":         f"{b['weight']*100:.0f}%",
        })

    tbl_df = pd.DataFrame(rows_tbl)
    st.dataframe(tbl_df, use_container_width=True, hide_index=True)

    # ═══════════════════════════════════════════════════════════════
    # KEY RISKS
    # ═══════════════════════════════════════════════════════════════
    if rec.get("risks"):
        st.markdown("---")
        sec("Key Risk Factors", "Financial signals that could impair the thesis")

        risks = rec["risks"]
        risk_cols = st.columns(min(len(risks), 3))
        for idx, risk in enumerate(risks):
            risk_cols[idx % 3].markdown(f"""
            <div style="
                background:rgba(255,71,87,0.07);
                border:1px solid rgba(255,71,87,0.2);
                border-left:3px solid {RED};
                border-radius:0 10px 10px 0;
                padding:12px 16px;
                margin:4px 0;
                font-size:13px;
                color:{TEXT};
                line-height:1.5;
            ">⚠️ {risk}</div>
            """, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # FINAL UPSIDE/DOWNSIDE GAUGE
    # ═══════════════════════════════════════════════════════════════
    st.markdown("---")
    sec("Upside / Downside Summary", "Each methodology's implied return from current price")

    if bars:
        upsides_chart = [round((b["mid"] - price)/price*100, 1) if price > 0 else 0
                         for b in bars]
        colors_chart  = [GREEN if u >= 5 else (RED if u <= -5 else GOLD)
                         for u in upsides_chart]

        fig_up = go.Figure(go.Bar(
            x=[b["label"] for b in bars],
            y=upsides_chart,
            marker_color=colors_chart,
            text=[f"{'▲' if u >= 0 else '▼'} {abs(u):.1f}%" for u in upsides_chart],
            textposition="outside",
            textfont=dict(color=TEXT, size=11),
            hovertemplate="<b>%{x}:</b> %{y:+.1f}%<extra></extra>",
        ))
        fig_up.add_hline(y=0, line_color="rgba(255,255,255,0.2)", line_width=1.5)
        fig_up.add_hline(y=15,  line_dash="dot", line_color=GREEN,
                         annotation_text="BUY threshold +15%",
                         annotation_font=dict(color=GREEN, size=10),
                         annotation_position="bottom right")
        fig_up.add_hline(y=-15, line_dash="dot", line_color=RED,
                         annotation_text="SELL threshold -15%",
                         annotation_font=dict(color=RED, size=10),
                         annotation_position="top right")
        fig_up.update_layout(**{**BASE,
            "title":  f"{ticker} — Implied Upside by Methodology (%)",
            "height": 360,
            "xaxis":  dict(type="category", showgrid=False,
                          tickfont=dict(color=MUTED, size=10)),
            "yaxis":  dict(title="Implied Return (%)",
                          gridcolor="rgba(136,146,176,0.08)",
                          ticksuffix="%"),
            "showlegend": False,
        })
        st.plotly_chart(fig_up, use_container_width=True)

        # Final data-driven verdict
        avg_up = sum(upsides_chart) / len(upsides_chart)
        insight(
            f"Across all {len(bars)} valuation methodologies, {ticker} shows an average implied "
            f"return of <b>{'▲' if avg_up >= 0 else '▼'} {abs(avg_up):.1f}%</b> from the current "
            f"price of ₹{price:,.2f}. Our weighted target of <b>₹{target_px:,.0f}</b> "
            f"({'▲' if upside >= 0 else '▼'} {abs(upside):.1f}%) leads to a "
            f"<b style='color:{rc};'>{rating}</b> rating with <b>{conviction} Conviction</b>.",
            icon="🎯", color=rc
        )