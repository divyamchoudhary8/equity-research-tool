"""
utils/pdf_report.py  — v2
Professional equity research PDF, Goldman Sachs / JPMorgan style.
Clean typography, strict Y-tracking, no overlapping content.
"""

import io
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, black

W, H   = A4
ML     = 18*mm   # left margin
MR     = 18*mm   # right margin
MT     = 12*mm   # top margin (below header band)
MB     = 22*mm   # bottom margin (above footer)
TW     = W - ML - MR   # text width

# ── Palette ───────────────────────────────────────────────────────
NAVY    = HexColor("#0d1f3c")
NAVY2   = HexColor("#1a3058")
ACCENT  = HexColor("#1565c0")
CYAN    = HexColor("#0288d1")
GREEN   = HexColor("#2e7d32")
RED     = HexColor("#c62828")
AMBER   = HexColor("#e65100")
GREY1   = HexColor("#f5f7fa")   # lightest bg
GREY2   = HexColor("#e8ecf1")   # alt row
GREY3   = HexColor("#b0bec5")   # muted text
DARK    = HexColor("#1a2332")   # body text
MID     = HexColor("#455a64")   # secondary text
BORDER  = HexColor("#cfd8dc")

RATING_CLR = {"BUY": GREEN, "HOLD": AMBER, "SELL": RED}
RATING_BG  = {
    "BUY":  HexColor("#e8f5e9"),
    "HOLD": HexColor("#fff3e0"),
    "SELL": HexColor("#ffebee"),
}

F_REG  = "Helvetica"
F_BOLD = "Helvetica-Bold"
F_OBL  = "Helvetica-Oblique"
TODAY  = date.today().strftime("%d %B %Y")
TOTAL_PAGES = 6


# ── Low-level helpers ─────────────────────────────────────────────

def _f(c, font=F_REG, size=9, color=DARK):
    c.setFont(font, size)
    c.setFillColor(color)

def _box(c, x, y, w, h, fill=None, stroke_color=None, stroke_w=0.4, r=0):
    c.saveState()
    if fill:        c.setFillColor(fill)
    if stroke_color: c.setStrokeColor(stroke_color); c.setLineWidth(stroke_w)
    kw = dict(fill=1 if fill else 0, stroke=1 if stroke_color else 0)
    if r: c.roundRect(x, y, w, h, r, **kw)
    else: c.rect(x, y, w, h, **kw)
    c.restoreState()

def _hline(c, x1, y, x2, color=BORDER, w=0.4):
    c.saveState(); c.setStrokeColor(color); c.setLineWidth(w)
    c.line(x1, y, x2, y); c.restoreState()

def _text_width(c, text, font, size):
    return c.stringWidth(text, font, size)

def _wrap(c, text, x, y, max_w, font=F_REG, size=9, color=DARK, lh=13):
    """Word-wrap text. Returns Y after last line."""
    _f(c, font, size, color)
    words = str(text).replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>","").split()
    line = ""
    for word in words:
        test = (line + " " + word).strip()
        if _text_width(c, test, font, size) <= max_w:
            line = test
        else:
            if line:
                c.drawString(x, y, line); y -= lh
            line = word
    if line:
        c.drawString(x, y, line); y -= lh
    return y


# ── Page chrome ───────────────────────────────────────────────────

def _cover_header(c, company, ticker, rating):
    pass  # handled inline

def _page_header(c, title, right=""):
    """Dark header band at top of body pages."""
    _box(c, 0, H-16*mm, W, 16*mm, fill=NAVY)
    _f(c, F_BOLD, 11, white)
    c.drawString(ML, H-9*mm, title)
    _f(c, F_REG, 8, HexColor("#90caf9"))
    c.drawRightString(W-MR, H-9*mm, right)

def _page_footer(c, n, company, ticker):
    y = MB - 8*mm
    _hline(c, ML, y+5*mm, W-MR)
    _f(c, F_REG, 7, GREY3)
    c.drawString(ML, y, f"EquityIQ Research  |  {company} ({ticker}.NS)  |  Initiating Coverage")
    c.drawRightString(W-MR, y, f"CONFIDENTIAL — FOR PROFESSIONAL USE ONLY  |  Page {n} of {TOTAL_PAGES}")

def _section_hdr(c, title, y):
    """Returns Y after the band."""
    _box(c, ML, y-6.5*mm, TW, 6.5*mm, fill=NAVY2)
    _f(c, F_BOLD, 8.5, CYAN)
    c.drawString(ML+3*mm, y-4.5*mm, title.upper())
    return y - 9*mm


# ── Table helper ──────────────────────────────────────────────────

def _table(c, x, y, hdrs, rows, cws,
           rh=6*mm, hdr_bg=NAVY, alt_bg=GREY1):
    """
    Draw table. Strictly tracks Y. Returns Y after last row.
    hdrs: list[str], rows: list[list], cws: list[float in points]
    """
    tw = sum(cws)

    # Header
    _box(c, x, y-rh, tw, rh, fill=hdr_bg)
    cx = x
    for i, (h, cw) in enumerate(zip(hdrs, cws)):
        _f(c, F_BOLD, 7.5, CYAN)
        pad = cx + 2*mm if i == 0 else cx + cw - 1.5*mm
        if i == 0: c.drawString(pad, y-rh+2*mm, str(h))
        else:      c.drawRightString(pad, y-rh+2*mm, str(h))
        cx += cw
    y -= rh

    for ri, row in enumerate(rows):
        bg = alt_bg if ri % 2 == 0 else white
        _box(c, x, y-rh, tw, rh, fill=bg)
        _hline(c, x, y-rh, x+tw, BORDER, 0.3)
        cx = x
        for ci, (cell, cw) in enumerate(zip(row, cws)):
            v = str(cell) if cell is not None else "—"
            fc = DARK; fn = F_REG
            if v.startswith("▲"):   fc = GREEN;  fn = F_BOLD
            elif v.startswith("▼"): fc = RED;    fn = F_BOLD
            elif v in ("BUY","HOLD","SELL"):
                fc = RATING_CLR[v];  fn = F_BOLD
            _f(c, fn, 8, fc)
            pad = cx+2*mm if ci==0 else cx+cw-1.5*mm
            if ci == 0: c.drawString(pad, y-rh+2*mm, v)
            else:       c.drawRightString(pad, y-rh+2*mm, v)
            cx += cw
        y -= rh

    _hline(c, x, y, x+tw, NAVY, 0.6)
    return y - 2*mm


def _metric_cards(c, x, y, items, card_w, card_h=18*mm, gap=2*mm):
    """
    items: list of (label, value, sub, accent_color)
    Returns Y after the row.
    """
    cx = x
    for label, value, sub, accent in items:
        _box(c, cx, y-card_h, card_w-gap, card_h, fill=GREY1, stroke_color=GREY2, stroke_w=0.5, r=2)
        _box(c, cx, y-2*mm, card_w-gap, 2*mm, fill=accent, r=0)
        _f(c, F_REG, 7, GREY3)
        c.drawCentredString(cx+(card_w-gap)/2, y-card_h+10*mm, label.upper())
        _f(c, F_BOLD, 11.5, DARK)
        c.drawCentredString(cx+(card_w-gap)/2, y-card_h+5.5*mm, str(value))
        if sub:
            _f(c, F_REG, 7, GREY3)
            c.drawCentredString(cx+(card_w-gap)/2, y-card_h+2.5*mm, str(sub))
        cx += card_w
    return y - card_h - 4*mm


# ═════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════

def generate_report(
    ticker, company, sector, industry, info,
    hist_fcff, ratios, dupont_3f, piotroski,
    dcf_results, implied_df, rec, bars,
    analyst_name="Divyam Choudhary",
):
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"{company} — EquityIQ Research")
    c.setAuthor(analyst_name)

    price    = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    target   = rec.get("target_price", 0)
    rating   = rec.get("rating", "HOLD")
    upside   = rec.get("upside_pct", 0)
    mkt_cap  = (info.get("marketCap") or 0) / 1e7
    beta     = info.get("beta") or "N/A"
    hi52     = info.get("fiftyTwoWeekHigh") or 0
    lo52     = info.get("fiftyTwoWeekLow")  or 0
    pe       = info.get("trailingPE")

    rc  = RATING_CLR[rating]
    rbg = RATING_BG[rating]
    usign = "+" if upside >= 0 else ""

    # ─────────────────────────────────────────────────────────────
    # PAGE 1 — COVER
    # ─────────────────────────────────────────────────────────────
    # Background
    _box(c, 0, 0, W, H, fill=NAVY)

    # Top bar
    _box(c, 0, H-14*mm, W, 14*mm, fill=ACCENT)
    _f(c, F_BOLD, 9, white)
    c.drawString(ML, H-8.5*mm, "EQUITYIQ RESEARCH")
    _f(c, F_REG, 8, HexColor("#bbdefb"))
    c.drawString(ML+50*mm, H-8.5*mm, "INITIATING COVERAGE  ·  CONFIDENTIAL")
    c.drawRightString(W-MR, H-8.5*mm, TODAY)

    # Company block
    y = H - 32*mm
    _f(c, F_REG, 10, HexColor("#90caf9"))
    c.drawString(ML, y, f"{ticker}.NS  ·  {sector}  ·  {industry}")
    y -= 12*mm
    _f(c, F_BOLD, 34, white)
    c.drawString(ML, y, company)
    y -= 6*mm
    _hline(c, ML, y, W-MR, HexColor("#1e88e5"), 1.2)
    y -= 10*mm

    # Rating + target box side by side
    rw, rh = 80*mm, 38*mm
    # Rating
    _box(c, ML, y-rh, rw, rh, fill=rc, r=3)
    _f(c, F_BOLD, 30, white)
    c.drawCentredString(ML+rw/2, y-rh+18*mm, rating)
    _f(c, F_REG, 9, white)
    c.drawCentredString(ML+rw/2, y-rh+11*mm, f"{rec.get('conviction','Medium')} Conviction")
    _f(c, F_REG, 8, HexColor("#ffffff88"))
    c.drawCentredString(ML+rw/2, y-rh+5*mm,
        f"{rec.get('score_above',0)}/{rec.get('total_bars',7)} methods imply upside")

    # Target
    tx = ML+rw+5*mm
    tw2 = 70*mm
    _box(c, tx, y-rh, tw2, rh, fill=NAVY2, r=3)
    _f(c, F_REG, 8, GREY3)
    c.drawCentredString(tx+tw2/2, y-rh+30*mm, "12-MONTH TARGET")
    _f(c, F_BOLD, 26, HexColor("#29b6f6"))
    c.drawCentredString(tx+tw2/2, y-rh+21*mm, f"Rs.{target:,.0f}")
    uc = HexColor("#a5d6a7") if upside >= 0 else HexColor("#ef9a9a")
    _f(c, F_BOLD, 11, uc)
    c.drawCentredString(tx+tw2/2, y-rh+13*mm,
        f"{usign}{upside:.1f}% vs Rs.{price:,.2f}")
    _f(c, F_REG, 8, GREY3)
    c.drawCentredString(tx+tw2/2, y-rh+6*mm, "Current Market Price")
    y -= rh + 10*mm

    # Key stats row
    stats = [
        ("Market Cap", f"Rs.{mkt_cap:,.0f} Cr", ""),
        ("52W High",   f"Rs.{hi52:,.2f}", ""),
        ("52W Low",    f"Rs.{lo52:,.2f}", ""),
        ("P/E (TTM)",  f"{pe:.1f}x" if pe else "N/A", ""),
        ("Beta",       f"{beta:.2f}" if isinstance(beta, float) else str(beta), "vs Nifty 50"),
    ]
    sw = TW / len(stats)
    for i, (lbl, val, sub) in enumerate(stats):
        sx = ML + i*sw
        _f(c, F_REG, 7.5, GREY3)
        c.drawCentredString(sx+sw/2, y, lbl)
        _f(c, F_BOLD, 11.5, white)
        c.drawCentredString(sx+sw/2, y-7*mm, val)
        if sub:
            _f(c, F_REG, 7, GREY3)
            c.drawCentredString(sx+sw/2, y-12*mm, sub)
    y -= 20*mm

    _hline(c, ML, y, W-MR, HexColor("#1e3a5f"))
    y -= 8*mm

    # Investment thesis bullets
    _f(c, F_BOLD, 10, HexColor("#29b6f6"))
    c.drawString(ML, y, "Investment Thesis")
    y -= 8*mm

    bullets = [
        f"We initiate coverage on {company} with a {rating} rating and "
        f"12-month target of Rs.{target:,.0f} ({usign}{upside:.1f}% upside).",
        f"Our analysis covers {rec.get('total_bars',7)} valuation methodologies; "
        f"{rec.get('score_above',0)} imply upside from current levels.",
    ]
    summary_clean = (rec.get("summary","")
                     .replace("<b>","").replace("</b>","")
                     .replace("<i>","").replace("</i>",""))
    if len(summary_clean) > 20:
        bullets.append(summary_clean[:240] + "…" if len(summary_clean) > 240 else summary_clean)

    risks = rec.get("risks", [])
    if risks:
        bullets.append(f"Key risk: {risks[0]}")

    for bullet in bullets[:4]:
        _f(c, F_BOLD, 9.5, HexColor("#29b6f6"))
        c.drawString(ML, y, "▸")
        y = _wrap(c, bullet, ML+5*mm, y, TW-5*mm,
                  font=F_REG, size=9.5, color=HexColor("#cfd8dc"), lh=13)
        y -= 4*mm

    # Bottom analyst bar
    _box(c, 0, 0, W, 20*mm, fill=NAVY2)
    _hline(c, 0, 20*mm, W, HexColor("#1e88e5"), 1)
    _f(c, F_BOLD, 9, white)
    c.drawString(ML, 13*mm, analyst_name)
    _f(c, F_REG, 8, GREY3)
    c.drawString(ML, 8*mm, f"Equity Research Analyst  |  EquityIQ Research  |  {TODAY}")
    c.drawRightString(W-MR, 10*mm, "EquityIQ Automated Research Platform")

    c.showPage()

    # ─────────────────────────────────────────────────────────────
    # PAGE 2 — EXECUTIVE SUMMARY
    # ─────────────────────────────────────────────────────────────
    _box(c, 0, 0, W, H, fill=white)
    _page_header(c, "Executive Summary",
                 f"{ticker}.NS  |  {rating}  |  Target Rs.{target:,.0f}")
    _page_footer(c, 2, company, ticker)

    y = H - 16*mm - 8*mm

    # Key metric cards
    card_w = TW / 5
    y = _metric_cards(c, ML, y, [
        ("Price",      f"Rs.{price:,.0f}", TODAY,       ACCENT),
        ("Target",     f"Rs.{target:,.0f}", f"{usign}{upside:.1f}%", rc),
        ("Market Cap", f"Rs.{mkt_cap:,.0f}Cr", "",     CYAN),
        ("P/E (TTM)",  f"{pe:.1f}x" if pe else "N/A", "", GREY3),
        ("Beta",       f"{beta:.2f}" if isinstance(beta,(int,float)) else "N/A", "vs Nifty", GREY3),
    ], card_w)

    y -= 2*mm
    y = _section_hdr(c, "Rating Summary", y)

    # Rating pill
    _box(c, ML, y-10*mm, TW, 10*mm, fill=rbg,
         stroke_color=rc, stroke_w=0.7, r=2)
    _f(c, F_BOLD, 10, rc)
    c.drawString(ML+4*mm, y-6.5*mm, f"RATING: {rating}")
    _f(c, F_REG, 9, DARK)
    c.drawString(ML+32*mm, y-6.5*mm,
        f"12-Month Target: Rs.{target:,.0f}   |   "
        f"Implied Upside: {usign}{upside:.1f}%   |   "
        f"Conviction: {rec.get('conviction','Medium')}")
    y -= 13*mm

    y = _section_hdr(c, "Investment Summary", y)
    y = _wrap(c, summary_clean, ML, y, TW,
              font=F_REG, size=9.5, color=DARK, lh=14)
    y -= 6*mm

    y = _section_hdr(c, "Investment Highlights", y)
    y -= 2*mm

    high = [
        f"Financial Health: Piotroski F-Score {piotroski.get('total_score','N/A')}/9 — "
        f"{piotroski.get('rating','').split('(')[0].strip()}.",
        f"Valuation Consensus: {rec.get('score_above',0)} of {rec.get('total_bars',7)} "
        f"methodologies imply upside from Rs.{price:,.2f}.",
    ]
    dcf_base = dcf_results.get("base", {})
    if dcf_base.get("intrinsic_price"):
        high.append(
            f"DCF Intrinsic Value: Base case yields Rs.{dcf_base['intrinsic_price']:,.0f}/share "
            f"({usign if dcf_base.get('upside_pct',0)>=0 else ''}{dcf_base.get('upside_pct',0):.1f}%).")
    if dcf_base.get("tv_pct_of_ev"):
        high.append(
            f"Terminal Value: {dcf_base['tv_pct_of_ev']:.0f}% of EV — "
            f"within the typical 60–80% range for mature businesses.")

    for h in high:
        _f(c, F_BOLD, 9.5, ACCENT)
        c.drawString(ML, y, "▸")
        y = _wrap(c, h, ML+5*mm, y, TW-5*mm,
                  font=F_REG, size=9.5, color=DARK, lh=13)
        y -= 4*mm

    if y > MB+20*mm and risks:
        y -= 2*mm
        y = _section_hdr(c, "Key Risks to Our Thesis", y)
        y -= 2*mm
        for r2 in risks[:3]:
            _f(c, F_BOLD, 9, RED)
            c.drawString(ML, y, "⚠")
            r2c = r2.replace("<b>","").replace("</b>","")
            y = _wrap(c, r2c, ML+5*mm, y, TW-5*mm,
                      font=F_REG, size=9, color=DARK, lh=13)
            y -= 3*mm

    c.showPage()

    # ─────────────────────────────────────────────────────────────
    # PAGE 3 — FINANCIAL PERFORMANCE
    # ─────────────────────────────────────────────────────────────
    _box(c, 0, 0, W, H, fill=white)
    _page_header(c, "Financial Performance Analysis",
                 f"{ticker}.NS  |  Values in Rs. Crores")
    _page_footer(c, 3, company, ticker)
    y = H - 16*mm - 8*mm

    # FCFF table
    if hist_fcff is not None and not hist_fcff.empty:
        y = _section_hdr(c, "Historical Free Cash Flow (FCFF) — Rs. Crores", y)
        yrs  = [str(yr) for yr in hist_fcff.index]
        cw0  = 48*mm
        cwy  = (TW - cw0) / max(len(yrs),1)
        hdrs = ["Metric"] + yrs
        cws  = [cw0] + [cwy]*len(yrs)
        rows = []
        for col in ["Revenue","EBIT","NOPAT","D&A","CapEx","FCFF"]:
            if col in hist_fcff.columns:
                rows.append([col] + [f"Rs.{v:,.0f}" for v in hist_fcff[col].values])
        if rows:
            y = _table(c, ML, y, hdrs, rows, cws)
        y -= 4*mm

    # Key Ratios table
    prof = ratios.get("profitability")
    sol  = ratios.get("solvency")
    liq  = ratios.get("liquidity")

    if prof is not None and not prof.empty:
        y = _section_hdr(c, "Key Financial Ratios", y)
        yrs  = [str(yr) for yr in prof.index]
        cw0  = 60*mm
        cwy  = (TW - cw0) / max(len(yrs),1)
        hdrs = ["Ratio"] + yrs
        cws  = [cw0] + [cwy]*len(yrs)
        rows = []
        for col in ["EBITDA Margin (%)","Net Profit Margin (%)","ROE (%)","ROCE (%)"]:
            if col in prof.columns:
                rows.append([col] + [
                    f"{v:.1f}%" if v is not None and str(v)!='nan' else "—"
                    for v in prof[col].values])
        if sol is not None and not sol.empty:
            for col in ["Interest Coverage (x)","Net Debt / EBITDA (x)"]:
                if col in sol.columns:
                    rows.append([col] + [
                        f"{v:.1f}x" if v is not None and str(v)!='nan' else "—"
                        for v in sol[col].values])
        if liq is not None and not liq.empty:
            if "Current Ratio (x)" in liq.columns:
                rows.append(["Current Ratio (x)"] + [
                    f"{v:.1f}x" if v is not None and str(v)!='nan' else "—"
                    for v in liq["Current Ratio (x)"].values])
        if rows:
            y = _table(c, ML, y, hdrs, rows, cws)
        y -= 4*mm

    # DuPont
    if dupont_3f is not None and not dupont_3f.empty and y > MB+50*mm:
        y = _section_hdr(c, "DuPont ROE Decomposition (3-Factor)", y)
        yrs  = [str(yr) for yr in dupont_3f.index]
        cw0  = 62*mm
        cwy  = (TW - cw0) / max(len(yrs),1)
        hdrs = ["Component"] + yrs
        cws  = [cw0] + [cwy]*len(yrs)
        rows = []
        for col in ["Net Profit Margin (%)","Asset Turnover (x)","Equity Multiplier (x)","ROE (%)"]:
            if col in dupont_3f.columns:
                rows.append([col] + [f"{v:.2f}" for v in dupont_3f[col].values])
        if rows:
            y = _table(c, ML, y, hdrs, rows, cws)

    c.showPage()

    # ─────────────────────────────────────────────────────────────
    # PAGE 4 — VALUATION
    # ─────────────────────────────────────────────────────────────
    _box(c, 0, 0, W, H, fill=white)
    _page_header(c, "Valuation Analysis",
                 f"{ticker}.NS  |  Rs. Crores unless noted")
    _page_footer(c, 4, company, ticker)
    y = H - 16*mm - 8*mm

    # DCF table
    y = _section_hdr(c, "Discounted Cash Flow (DCF) Valuation", y)
    dcf_rows = []
    for sc in ["base","bull","bear"]:
        r2 = dcf_results.get(sc, {})
        if r2:
            us = "+" if r2.get("upside_pct",0)>=0 else ""
            dcf_rows.append([
                f"{sc.title()} Case",
                f"{r2.get('rev_growth',0):.1f}%",
                f"Rs.{r2.get('sum_pv_fcff',0):,.0f}",
                f"Rs.{r2.get('pv_terminal_value',0):,.0f}",
                f"Rs.{r2.get('enterprise_value',0):,.0f}",
                f"Rs.{r2.get('equity_value',0):,.0f}",
                f"Rs.{r2.get('intrinsic_price',0):,.0f}",
                f"{'▲' if r2.get('upside_pct',0)>=0 else '▼'} {abs(r2.get('upside_pct',0)):.1f}%",
            ])
    dcf_hdrs = ["Scenario","Rev Gth","PV FCFFs","PV Terminal",
                "EV","Equity Val","Intr Price","Upside"]
    dcf_cws  = [26*mm,18*mm,22*mm,22*mm,22*mm,22*mm,22*mm,18*mm]
    if dcf_rows:
        y = _table(c, ML, y, dcf_hdrs, dcf_rows, dcf_cws)
    _f(c, F_OBL, 7.5, GREY3)
    c.drawString(ML, y, f"WACC derived from CAPM  |  Terminal Growth: 4.0%  |  "
                         f"TV ~{dcf_results.get('base',{}).get('tv_pct_of_ev',0):.0f}% of EV")
    y -= 8*mm

    # Football field table
    y = _section_hdr(c, "Football Field — Valuation Range Summary", y)
    ff_rows = []
    for bar in bars:
        up_b = round((bar["mid"]-price)/price*100,1) if price>0 else 0
        ff_rows.append([
            bar["label"], bar["category"],
            f"Rs.{bar['low']:,.0f}",
            f"Rs.{bar['mid']:,.0f}",
            f"Rs.{bar['high']:,.0f}",
            f"{'▲' if up_b>=0 else '▼'} {abs(up_b):.1f}%",
            f"{bar['weight']*100:.0f}%",
        ])
    ff_hdrs = ["Methodology","Type","Low","Median","High","Upside","Wt"]
    ff_cws  = [50*mm,18*mm,24*mm,24*mm,24*mm,20*mm,14*mm]
    if ff_rows:
        y = _table(c, ML, y, ff_hdrs, ff_rows, ff_cws)
    y -= 4*mm

    # Comps implied
    if implied_df is not None and not implied_df.empty and y > MB+40*mm:
        y = _section_hdr(c, "Comparable Company — Implied Valuation", y)
        imp_rows = []
        for mult, row in implied_df.iterrows():
            med = row.get("Implied Price (Med)")
            mn  = row.get("Implied Price (Min)")
            mx  = row.get("Implied Price (Max)")
            up  = row.get("Upside (Median) %")
            if med is None: continue
            imp_rows.append([
                mult,
                f"Rs.{mn:,.0f}" if mn else "—",
                f"Rs.{med:,.0f}",
                f"Rs.{mx:,.0f}" if mx else "—",
                f"Rs.{price:,.0f}",
                f"{'▲' if (up or 0)>=0 else '▼'} {abs(up or 0):.1f}%",
            ])
        imp_hdrs = ["Multiple","Low","Median","High","Current","Upside"]
        imp_cws  = [32*mm,28*mm,30*mm,28*mm,28*mm,28*mm]
        if imp_rows:
            y = _table(c, ML, y, imp_hdrs, imp_rows, imp_cws)

    c.showPage()

    # ─────────────────────────────────────────────────────────────
    # PAGE 5 — RISK + PIOTROSKI
    # ─────────────────────────────────────────────────────────────
    _box(c, 0, 0, W, H, fill=white)
    _page_header(c, "Risk Assessment & Financial Health", f"{ticker}.NS")
    _page_footer(c, 5, company, ticker)
    y = H - 16*mm - 8*mm

    # ── Piotroski in two columns ──────────────────────────────────
    y = _section_hdr(c, "Piotroski F-Score — Financial Health Screen (0–9)", y)
    score   = piotroski.get("total_score", 0)
    p_rat   = piotroski.get("rating","")
    sc_clr  = GREEN if score>=7 else (AMBER if score>=4 else RED)
    sc_bg   = RATING_BG.get("BUY" if score>=7 else ("HOLD" if score>=4 else "SELL"), GREY1)

    # Score badge (left column, fixed height)
    bw, bh = 44*mm, 28*mm
    _box(c, ML, y-bh, bw, bh, fill=sc_clr, r=3)
    _f(c, F_BOLD, 28, white)
    c.drawCentredString(ML+bw/2, y-bh+14*mm, f"{score}/9")
    _f(c, F_REG, 8.5, white)
    c.drawCentredString(ML+bw/2, y-bh+7*mm,
                        p_rat.split("(")[0].strip() if p_rat else "")
    _f(c, F_REG, 7.5, HexColor("#ffffffaa"))
    c.drawCentredString(ML+bw/2, y-bh+3*mm, "Piotroski F-Score")

    # Signals (right column, two sub-columns)
    signals = piotroski.get("signals", {})
    sig_list = list(signals.items())
    rx = ML + bw + 6*mm          # start x for signals
    rw2 = (TW - bw - 6*mm) / 2  # width of each signal column
    sy  = y - 4*mm
    lh_s = 5.5*mm

    for idx, (sig_name, sig_val) in enumerate(sig_list[:9]):
        short = sig_name.split(" - ",1)[1] if " - " in sig_name else sig_name
        icon  = "✓" if sig_val else "✗"
        fc    = GREEN if sig_val else RED
        col_x = rx if idx < 5 else rx + rw2
        row_y = sy - (idx % 5) * lh_s
        _f(c, F_BOLD, 9, fc)
        c.drawString(col_x, row_y, icon)
        _f(c, F_REG, 8, DARK)
        c.drawString(col_x+5*mm, row_y, short[:30])

    # Move Y below the taller of badge vs signals
    y = y - max(bh, 5 * lh_s) - 6*mm

    # ── Key Risk Factors ──────────────────────────────────────────
    y = _section_hdr(c, "Key Risk Factors", y)
    y -= 2*mm

    generic_risks = [
        "Macroeconomic slowdown could reduce demand across key business segments.",
        "Regulatory changes in government policy or sector-specific rules could affect prospects.",
        "Currency exposure creates earnings sensitivity to INR fluctuations.",
        "Competitive intensity from domestic and global peers could compress margins.",
        "Input cost inflation may weigh on gross margins if cost increases cannot be passed through.",
    ]
    all_risks = [r.replace("<b>","").replace("</b>","")
                 for r in rec.get("risks",[])] + generic_risks
    all_risks = list(dict.fromkeys(all_risks))[:6]   # dedupe, cap at 6

    # Two-column risk layout
    col_w2 = (TW - 4*mm) / 2
    for idx, risk in enumerate(all_risks):
        cx2 = ML if idx % 2 == 0 else ML + col_w2 + 4*mm
        if idx % 2 == 0 and idx > 0:
            y -= 3*mm   # gap between rows
        row_y2 = y if idx % 2 == 0 else y   # same row for pairs

        _box(c, cx2, row_y2-14*mm, col_w2, 14*mm,
             fill=HexColor("#fff5f5"), stroke_color=HexColor("#ffcdd2"), stroke_w=0.5, r=2)
        _box(c, cx2, row_y2-14*mm, 3*mm, 14*mm, fill=RED, r=0)
        _f(c, F_BOLD, 7.5, RED)
        c.drawString(cx2+5*mm, row_y2-4.5*mm, f"Risk {idx+1}")
        _f(c, F_REG, 7.5, DARK)
        # Fit text in box
        words = risk.split()
        line1, line2 = "", ""
        for w in words:
            test = (line1+" "+w).strip()
            if _text_width(c, test, F_REG, 7.5) <= col_w2-8*mm:
                line1 = test
            else:
                line2 = (line2+" "+w).strip()
        c.drawString(cx2+5*mm, row_y2-9*mm, line1)
        if line2:
            c.drawString(cx2+5*mm, row_y2-13*mm, line2[:55])

        if idx % 2 == 1 or idx == len(all_risks)-1:
            y -= 17*mm

    c.showPage()

    # ─────────────────────────────────────────────────────────────
    # PAGE 6 — DISCLAIMER
    # ─────────────────────────────────────────────────────────────
    _box(c, 0, 0, W, H, fill=white)
    _page_header(c, "Important Disclosures & Disclaimer", "")
    _page_footer(c, 6, company, ticker)
    y = H - 16*mm - 10*mm

    sections = [
        ("ANALYST CERTIFICATION",
         f"The analyst principally responsible for this report, {analyst_name}, certifies that "
         f"the views expressed accurately reflect personal views about {company} ({ticker}.NS) "
         f"and its securities. No compensation, direct or indirect, was or will be received "
         f"in connection with these specific recommendations."),
        ("GENERAL DISCLAIMER",
         "This report has been prepared by EquityIQ Research for informational purposes only. "
         "Data is sourced from Yahoo Finance (yfinance), company filings, and publicly "
         "available financial information. EquityIQ Research makes no representation as to "
         "accuracy, completeness, or timeliness. This report does not constitute an offer "
         "to buy or sell any security. Investments are subject to market risk. Readers should "
         "conduct independent research and consult a qualified financial advisor before making "
         "any investment decision. EquityIQ Research accepts no liability for direct or "
         "indirect loss arising from use of this report."),
        ("DATA SOURCES",
         "Financial data: Yahoo Finance via yfinance Python library. All values in Indian "
         "Rupees (INR). Values in Crores (1 Crore = 10,000,000 INR). Fiscal year end: "
         "March 31. NSE ticker format: [SYMBOL].NS. Market data as of report date."),
    ]

    for title, text in sections:
        _f(c, F_BOLD, 9.5, NAVY)
        c.drawString(ML, y, title)
        _hline(c, ML, y-2*mm, W-MR, ACCENT, 0.7)
        y -= 5*mm
        y = _wrap(c, text, ML, y, TW, font=F_REG, size=8.5, color=DARK, lh=13)
        y -= 8*mm

    # Rating system table
    _f(c, F_BOLD, 9.5, NAVY)
    c.drawString(ML, y, "RATING SYSTEM")
    _hline(c, ML, y-2*mm, W-MR, ACCENT, 0.7)
    y -= 6*mm

    for rat, desc, rng in [
        ("BUY",  "Expected total return > +15% over 12 months", "> +15%"),
        ("HOLD", "Expected total return between -15% and +15%",  "-15% to +15%"),
        ("SELL", "Expected total return < -15% over 12 months", "< -15%"),
    ]:
        rc2 = RATING_CLR[rat]
        _box(c, ML, y-7*mm, 18*mm, 7*mm, fill=rc2, r=1)
        _f(c, F_BOLD, 8.5, white)
        c.drawCentredString(ML+9*mm, y-4.5*mm, rat)
        _f(c, F_BOLD, 8.5, rc2)
        c.drawString(ML+21*mm, y-4.5*mm, rng)
        _f(c, F_REG, 8.5, DARK)
        c.drawString(ML+45*mm, y-4.5*mm, desc)
        y -= 9*mm

    y -= 6*mm
    # Final stamp
    _box(c, ML, y-10*mm, TW, 10*mm, fill=NAVY, r=2)
    _f(c, F_BOLD, 8.5, CYAN)
    c.drawCentredString(W/2, y-4.5*mm,
        f"EquityIQ Research  |  {company} ({ticker}.NS)  |  "
        f"{rating}  |  Rs.{target:,.0f}  |  {TODAY}")
    _f(c, F_REG, 7, GREY3)
    c.drawCentredString(W/2, y-8.5*mm,
        "Generated by EquityIQ Automated Research Platform — For Professional Use Only")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()