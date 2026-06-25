"""
analysis/comps.py
─────────────────
Comparable Company Analysis (Comps) — IB-grade implementation.

Structure:
    1. Auto-suggest sector peers based on the target company's sector
    2. Fetch live market data for each peer via yfinance
    3. Build standardised comps table (EV/EBITDA, EV/Revenue, P/E, P/B, EV/EBIT)
    4. Compute implied valuation range for the target using peer medians
    5. Premium/discount analysis vs peer group

IB Context:
    Comps (trading comparables) is one of the three core valuation methodologies
    used in every IB pitch book alongside DCF and Precedent Transactions.
    
    Key principle: CAPITAL STRUCTURE NEUTRALITY
    EV-based multiples (EV/EBITDA, EV/Revenue, EV/EBIT) are preferred over
    equity-based multiples (P/E) because they allow fair comparison between
    companies with different debt levels. Two companies with identical operations
    but different leverage will have the same EV/EBITDA but different P/E ratios.

    The output is a RANGE, not a single number. The median is the anchor,
    but the min/max shows how wide the market's view is.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from data.fetcher import NSEDataFetcher as F


def safe_div(a, b, default=None):
    try:
        if b is None or b == 0 or (isinstance(b, float) and (np.isnan(b) or np.isinf(b))):
            return default
        result = a / b
        return result if np.isfinite(result) else default
    except:
        return default


# ─────────────────────────────────────────────────────────────────────
# Sector → default peer tickers (NSE)
# Curated list of well-known, liquid NSE stocks per sector
# ─────────────────────────────────────────────────────────────────────
SECTOR_PEERS = {
    "Technology": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "Information Technology": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "Financial Services": ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN"],
    "Banks": ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN"],
    "Energy": ["RELIANCE", "ONGC", "BPCL", "IOC", "HINDPETRO"],
    "Consumer Defensive": ["NESTLEIND", "HINDUNILVR", "DABUR", "MARICO", "GODREJCP"],
    "Consumer Cyclical": ["MARUTI", "TATAMOTORS", "EICHERMOT", "BAJAJ-AUTO", "HEROMOTOCO"],
    "Industrials": ["LT", "SIEMENS", "ABB", "BHEL", "CUMMINSIND"],
    "Healthcare": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP"],
    "Basic Materials": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "COALINDIA"],
    "Communication Services": ["BHARTIARTL", "IDEA", "TATACOMM", "INDIAMART", "ZOMATO"],
    "Real Estate": ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE"],
    "Utilities": ["POWERGRID", "NTPC", "TATAPOWER", "ADANIPOWER", "CESC"],
    "Consumer Electronics": ["DIXON", "AMBER", "VOLTAS", "BLUESTARCO", "WHIRLPOOL"],
}

DEFAULT_PEERS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR"]

# Industry-level peers — more specific than sector, checked first
# Prevents mismatches like Zomato being grouped with auto companies
INDUSTRY_PEERS = {
    # Internet / Consumer Tech
    "Internet Retail":                  ["ETERNAL", "NYKAA", "INDIAMART", "DELHIVERY", "POLICYBZR"],
    "Internet Content & Information":   ["ETERNAL", "NYKAA", "INDIAMART", "INFO EDGE", "JUST DIAL"],
    "Software—Application":             ["INFY", "WIPRO", "LTIM", "MPHASIS", "PERSISTENT"],
    "Software—Infrastructure":          ["TCS", "HCLTECH", "TECHM", "KPITTECH", "TATAELXSI"],
    # Auto — specific industries within Consumer Cyclical
    "Auto Manufacturers":               ["MARUTI", "TATAMOTORS", "MSIL", "EICHERMOT", "MAHINDRA"],
    "Auto Parts":                       ["BOSCHLTD", "MOTHERSON", "BALKRISIND", "EXIDEIND", "AMARAJABAT"],
    "Motorcycles":                      ["BAJAJ-AUTO", "HEROMOTOCO", "TVSMOTORS", "ROYALENFD", "EICHERMOT"],
    # Financial
    "Banks—Regional":                   ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "INDUSINDBK"],
    "Banks—Diversified":                ["SBIN", "BANKBARODA", "PNB", "CANARABANK", "UNIONBANK"],
    "Insurance—Life":                   ["LICI", "SBILIFE", "HDFCLIFE", "ICICIPRULIFE", "MAXFINSERV"],
    "Credit Services":                  ["BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "MUTHOOTFIN", "MANAPPURAM"],
    # Consumer
    "Packaged Foods":                   ["NESTLEIND", "HINDUNILVR", "BRITANNIA", "DABUR", "MARICO"],
    "Beverages—Non-Alcoholic":          ["HATSUN", "VARUN BEVERAGES", "HINDUSTAN COCA", "CCL", "TASTY BITE"],
    "Luxury Goods":                     ["TITAN", "KALYAN", "SENCO", "PCJEWELLER", "THANGAMAYIL"],
    "Apparel Retail":                   ["TRENT", "ABFRL", "SHOPERSTOP", "MANYAVAR", "BATA"],
    "Specialty Retail":                 ["DMART", "VMART", "SPENCERS", "FRETAIL", "TRENT"],
    # Pharma
    "Drug Manufacturers—General":       ["SUNPHARMA", "CIPLA", "DRREDDY", "LUPIN", "AUROPHARMA"],
    "Drug Manufacturers—Specialty":     ["DIVISLAB", "ALKEM", "IPCA", "GLENMARK", "TORNTPHARM"],
    # Energy
    "Oil & Gas Refining & Marketing":   ["RELIANCE", "BPCL", "IOC", "HINDPETRO", "MRPL"],
    "Oil & Gas E&P":                    ["ONGC", "OIL", "CAIRN", "VEDL", "GAIL"],
    # Industrials
    "Engineering & Construction":       ["LT", "NCC", "KEC", "KALPATPOWR", "IRCON"],
    "Conglomerates":                    ["LT", "RELIANCE", "TATAMOTORS", "BAJAJ-AUTO", "SIEMENS"],
}


class CompsAnalysis:
    """
    Builds a comparable company analysis table for any NSE-listed company.

    Usage:
        comps = CompsAnalysis(target_ticker, target_info, target_financials)
        peers      = comps.suggest_peers()              # auto-suggested tickers
        table      = comps.build_table(peer_tickers)    # full comps DataFrame
        implied    = comps.implied_valuation(table, target_financials)
    """

    # Multiples to compute for every company
    MULTIPLES = ["EV/EBITDA", "EV/Revenue", "EV/EBIT", "P/E", "P/B"]

    # Reasonable bounds — filter out outliers (negative or absurdly high multiples)
    BOUNDS = {
        "EV/EBITDA": (0, 80),
        "EV/Revenue": (0, 30),
        "EV/EBIT":    (0, 100),
        "P/E":        (0, 150),
        "P/B":        (0, 50),
    }

    def __init__(
        self,
        target_ticker:     str,
        target_info:       dict,
        income_stmt:       pd.DataFrame,
        balance_sheet:     pd.DataFrame,
        cash_flow:         pd.DataFrame,
    ):
        self.target        = target_ticker.upper()
        self.target_info   = target_info
        self.is_           = income_stmt
        self.bs_           = balance_sheet
        self.cf_           = cash_flow
        self.target_sector = target_info.get("sector", "")

    # ─────────────────────────────────────────────────────────────
    # 1. Suggest peers
    # ─────────────────────────────────────────────────────────────

    def suggest_peers(self) -> list:
        """
        Returns a list of 5 suggested peer tickers.
        Checks industry first (more specific), then sector, then default.
        This prevents mismatches like food-delivery stocks being
        grouped with auto companies under "Consumer Cyclical".
        """
        target_industry = self.target_info.get("industry", "")

        # Industry-level mapping takes priority — much more specific
        peers = INDUSTRY_PEERS.get(target_industry)

        # Fall back to sector-level if no industry match
        if not peers:
            peers = SECTOR_PEERS.get(self.target_sector, DEFAULT_PEERS)

        # Remove target itself
        peers = [p for p in peers if p.upper() != self.target.upper()]
        return peers[:5]

    # ─────────────────────────────────────────────────────────────
    # 2. Fetch one company's multiples
    # ─────────────────────────────────────────────────────────────

    def _fetch_company_data(self, ticker: str) -> dict:
        """
        Fetches market data and computes multiples for one NSE ticker.
        Returns a dict with company info and all multiples.
        Returns None if data cannot be fetched.
        """
        try:
            t    = yf.Ticker(ticker + ".NS")
            info = t.info

            if not info or info.get("regularMarketPrice") is None:
                return None

            # ── Market data ──────────────────────────────────────
            price    = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            mkt_cap  = (info.get("marketCap") or 0) / 1e7        # → Crores
            shares   = (info.get("sharesOutstanding") or 0) / 1e7

            # ── Balance sheet items (from info dict — faster than full statements) ──
            total_debt = (info.get("totalDebt") or 0) / 1e7
            cash       = (info.get("totalCash") or 0) / 1e7
            ev         = mkt_cap + total_debt - cash

            # ── Income metrics ───────────────────────────────────
            revenue    = (info.get("totalRevenue") or 0) / 1e7
            ebitda     = (info.get("ebitda") or 0) / 1e7
            ebit       = (info.get("ebit") or 0) / 1e7

            # Fallback: if ebit not in info, approximate from ebitda - depreciation
            if ebit == 0 and ebitda != 0:
                depreciation = (info.get("totalDebtEquity") or 0)  # rough proxy
                ebit = ebitda * 0.85  # approximate: ebit ≈ 85% of ebitda

            # ── Per-share metrics ────────────────────────────────
            eps       = info.get("trailingEps") or 0
            book_val  = info.get("bookValue") or 0

            # ── Compute multiples ────────────────────────────────
            pe   = safe_div(price, eps)               if eps > 0      else None
            pb   = safe_div(price, book_val)          if book_val > 0 else None
            ev_ebitda = safe_div(ev, ebitda)          if ebitda > 0   else None
            ev_rev    = safe_div(ev, revenue)         if revenue > 0  else None
            ev_ebit   = safe_div(ev, ebit)            if ebit > 0     else None

            # ── Filter out unreasonable values ───────────────────
            def clip(val, multiple):
                if val is None:
                    return None
                lo, hi = self.BOUNDS[multiple]
                return round(val, 2) if lo <= val <= hi else None

            return {
                "Ticker":       ticker,
                "Company":      info.get("shortName", ticker),
                "Sector":       info.get("sector", "—"),
                "Price (₹)":    round(price, 2),
                "Mkt Cap (Cr)": round(mkt_cap, 0),
                "EV (Cr)":      round(ev, 0),
                "Revenue (Cr)": round(revenue, 0),
                "EBITDA (Cr)":  round(ebitda, 0),
                "EV/EBITDA":    clip(ev_ebitda, "EV/EBITDA"),
                "EV/Revenue":   clip(ev_rev,    "EV/Revenue"),
                "EV/EBIT":      clip(ev_ebit,   "EV/EBIT"),
                "P/E":          clip(pe,         "P/E"),
                "P/B":          clip(pb,         "P/B"),
            }
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────
    # 3. Build full comps table
    # ─────────────────────────────────────────────────────────────

    def build_table(self, peer_tickers: list) -> pd.DataFrame:
        """
        Fetches data for the target + all peers and returns a combined
        DataFrame sorted by EV/EBITDA.

        The target company row is always included and marked with ★.
        Peer rows are fetched fresh from yfinance.

        Returns:
            pd.DataFrame with columns: Ticker, Company, Price, Mkt Cap,
            EV, Revenue, EBITDA, and all multiples.
        """
        # Target company data (from live yfinance info)
        target_data = self._fetch_company_data(self.target)
        if target_data:
            target_data["Ticker"]  = f"★ {self.target}"
            target_data["Company"] = f"★ {target_data['Company']}"

        rows = [target_data] if target_data else []

        # Fetch peer data
        for ticker in peer_tickers:
            if ticker.upper() == self.target.upper():
                continue
            data = self._fetch_company_data(ticker)
            if data:
                rows.append(data)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        return df

    # ─────────────────────────────────────────────────────────────
    # 4. Summary stats (for peer group, excluding target)
    # ─────────────────────────────────────────────────────────────

    def peer_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes min, median, mean, max for each multiple
        across the peer group (excludes the target row).

        These stats are used to:
        - Show the range of peer valuations
        - Apply to target's financials to get implied price range
        """
        # Exclude target (marked with ★)
        peers_df = df[~df["Ticker"].str.startswith("★")]

        stats = {}
        for mult in self.MULTIPLES:
            if mult not in peers_df.columns:
                continue
            vals = peers_df[mult].dropna().values
            if len(vals) == 0:
                stats[mult] = {"Min": None, "Median": None, "Mean": None, "Max": None}
            else:
                stats[mult] = {
                    "Min":    round(float(np.min(vals)),    2),
                    "Median": round(float(np.median(vals)), 2),
                    "Mean":   round(float(np.mean(vals)),   2),
                    "Max":    round(float(np.max(vals)),    2),
                }

        return pd.DataFrame(stats).T

    # ─────────────────────────────────────────────────────────────
    # 5. Implied valuation range
    # ─────────────────────────────────────────────────────────────

    def implied_valuation(
        self,
        stats_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Applies peer median multiples to the target's own financials
        to get an implied Enterprise Value and per-share price range.

        For each multiple:
            Implied EV  = Target metric × Peer multiple
            Implied Eq  = Implied EV − Net Debt
            Implied Px  = Implied Eq / Shares outstanding

        Returns DataFrame with one row per multiple, showing
        implied price at Min, Median, and Max peer multiple.
        """
        # Target fundamentals (most recent year)
        def get(labels):
            return F.get_safe_value(self.is_, labels, 0)

        revenue = get(["Total Revenue", "TotalRevenue", "Revenue"])
        ebitda_direct = get(["EBITDA", "Ebitda"])
        ebit    = get(["EBIT", "Operating Income", "Ebit",
                       "Pretax Income", "Income Before Tax"])
        da      = abs(F.get_safe_value(
            self.cf_,
            ["Depreciation And Amortization", "Depreciation",
             "Reconciled Depreciation"], 0
        ))
        ebitda  = ebitda_direct if ebitda_direct > 0 else (ebit + da)

        total_debt = F.get_safe_value(
            self.bs_, ["Total Debt", "Long Term Debt", "LongTermDebt"], 0)
        cash = F.get_safe_value(
            self.bs_,
            ["Cash And Cash Equivalents", "Cash Financial",
             "Cash And Short Term Investments"], 0)
        net_debt = total_debt - cash

        shares = (self.target_info.get("sharesOutstanding") or 0) / 1e7

        eps       = self.target_info.get("trailingEps") or 0
        book_val  = self.target_info.get("bookValue") or 0
        price_now = self.target_info.get("currentPrice") or \
                    self.target_info.get("regularMarketPrice") or 0

        # Metric map: multiple → (target metric, metric type)
        metric_map = {
            "EV/EBITDA": (ebitda,   "ev"),
            "EV/Revenue":(revenue,  "ev"),
            "EV/EBIT":   (ebit,     "ev"),
            "P/E":       (eps,      "pe"),
            "P/B":       (book_val, "pb"),
        }

        records = []
        for mult, (metric, mtype) in metric_map.items():
            if mult not in stats_df.index:
                continue
            row = stats_df.loc[mult]
            implied_prices = {}
            for stat in ["Min", "Median", "Max"]:
                peer_mult = row.get(stat)
                if peer_mult is None or metric == 0:
                    implied_prices[stat] = None
                    continue
                if mtype == "ev":
                    impl_ev  = metric * peer_mult
                    impl_eq  = impl_ev - net_debt
                    impl_px  = safe_div(impl_eq, shares)
                elif mtype == "pe":
                    impl_px  = eps * peer_mult
                elif mtype == "pb":
                    impl_px  = book_val * peer_mult
                else:
                    impl_px  = None

                implied_prices[stat] = round(impl_px, 2) if impl_px else None

            upside = safe_div(
                (implied_prices.get("Median") or 0) - price_now,
                price_now
            ) * 100 if price_now > 0 else None

            records.append({
                "Multiple":           mult,
                "Peer Median":        row.get("Median"),
                "Implied Price (Min)":implied_prices.get("Min"),
                "Implied Price (Med)":implied_prices.get("Median"),
                "Implied Price (Max)":implied_prices.get("Max"),
                "Current Price":      round(price_now, 2),
                "Upside (Median) %":  round(upside, 1) if upside is not None else None,
            })

        return pd.DataFrame(records).set_index("Multiple")