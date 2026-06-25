"""
analysis/football_field.py
──────────────────────────
Football Field Chart — aggregates all valuation methodologies into one
visual and generates a BUY / HOLD / SELL recommendation.

Methodology weights (how much each method contributes to target price):
    DCF Base          35%   ← Fundamentals-driven, highest conviction
    DCF Bull/Bear     10%   ← Scenario bookends
    Comps EV/EBITDA   25%   ← Primary market multiple
    Comps EV/Revenue  10%   ← Secondary market multiple
    Comps P/E         10%   ← Equity multiple
    52-Week Range     10%   ← Market sentiment anchor

IB Context:
    The football field is the cover-page valuation in every pitch book.
    It communicates uncertainty honestly — showing a range, not a fake
    single-point precision. The recommendation is the analyst's judgement
    call on where current price sits relative to that range.
"""

import numpy as np
import pandas as pd


def safe_val(x):
    """Return x if it's a valid positive number, else None."""
    if x is None:
        return None
    try:
        f = float(x)
        return f if np.isfinite(f) and f > 0 else None
    except (TypeError, ValueError):
        return None


class FootballField:
    """
    Aggregates DCF, Comps, and 52-Week Range into a football field
    and generates a BUY / HOLD / SELL recommendation.

    Usage:
        ff = FootballField(current_price, dcf_results, implied_df, info)
        bars    = ff.build_bars()          # list of bar dicts for the chart
        rec     = ff.recommendation(bars)  # full recommendation dict
    """

    # Weight for each methodology in the blended target price
    WEIGHTS = {
        "DCF – Base":           0.35,
        "DCF – Bull":           0.10,
        "DCF – Bear":           0.10,
        "Comps – EV/EBITDA":    0.20,
        "Comps – EV/Revenue":   0.08,
        "Comps – P/E":          0.07,
        "52-Week Range":        0.10,
    }

    # Colour for each bar category
    COLORS = {
        "DCF":   "#00d4ff",    # cyan
        "Comps": "#a78bfa",    # purple
        "52W":   "#ffd700",    # gold
    }

    def __init__(
        self,
        current_price: float,
        dcf_results:   dict,         # output of DCFValuation.run()
        implied_df:    pd.DataFrame, # output of CompsAnalysis.implied_valuation()
        info:          dict,         # yfinance info dict
    ):
        self.price      = current_price
        self.dcf        = dcf_results
        self.implied    = implied_df
        self.info       = info
        self.high_52w   = info.get("fiftyTwoWeekHigh") or 0
        self.low_52w    = info.get("fiftyTwoWeekLow")  or 0

    # ─────────────────────────────────────────────────────────────
    # Build bars
    # ─────────────────────────────────────────────────────────────

    def build_bars(self) -> list:
        """
        Returns a list of bar dicts, one per valuation methodology.
        Each dict: {label, low, mid, high, category, weight}
        """
        bars = []

        # ── DCF bars ─────────────────────────────────────────────
        for scenario, label in [
            ("base", "DCF – Base"),
            ("bull", "DCF – Bull"),
            ("bear", "DCF – Bear"),
        ]:
            if scenario not in self.dcf:
                continue
            r   = self.dcf[scenario]
            mid = safe_val(r.get("intrinsic_price"))
            if mid is None:
                continue

            # Bear/Bull create natural spread around midpoint
            spread = mid * 0.12
            low    = round(max(mid - spread, 0), 2)
            high   = round(mid + spread, 2)

            bars.append({
                "label":    label,
                "low":      low,
                "mid":      round(mid, 2),
                "high":     high,
                "category": "DCF",
                "weight":   self.WEIGHTS.get(label, 0),
            })

        # ── Comps bars ───────────────────────────────────────────
        comps_map = {
            "EV/EBITDA": "Comps – EV/EBITDA",
            "EV/Revenue":"Comps – EV/Revenue",
            "P/E":       "Comps – P/E",
        }
        if self.implied is not None and not self.implied.empty:
            for mult, label in comps_map.items():
                if mult not in self.implied.index:
                    continue
                row  = self.implied.loc[mult]
                low  = safe_val(row.get("Implied Price (Min)"))
                mid  = safe_val(row.get("Implied Price (Med)"))
                high = safe_val(row.get("Implied Price (Max)"))
                if mid is None:
                    continue
                if low  is None: low  = mid * 0.85
                if high is None: high = mid * 1.15
                bars.append({
                    "label":    label,
                    "low":      round(low,  2),
                    "mid":      round(mid,  2),
                    "high":     round(high, 2),
                    "category": "Comps",
                    "weight":   self.WEIGHTS.get(label, 0),
                })

        # ── 52-Week Range bar ─────────────────────────────────────
        lo52 = safe_val(self.low_52w)
        hi52 = safe_val(self.high_52w)
        if lo52 and hi52:
            bars.append({
                "label":    "52-Week Range",
                "low":      round(lo52, 2),
                "mid":      round((lo52 + hi52) / 2, 2),
                "high":     round(hi52, 2),
                "category": "52W",
                "weight":   self.WEIGHTS.get("52-Week Range", 0),
            })

        return bars

    # ─────────────────────────────────────────────────────────────
    # Weighted target price
    # ─────────────────────────────────────────────────────────────

    def weighted_target(self, bars: list) -> float:
        """
        Computes weighted average target price from all bars,
        using WEIGHTS as defined above.
        """
        total_w   = 0
        weighted  = 0
        for bar in bars:
            w   = bar.get("weight", 0)
            mid = bar.get("mid")
            if mid and w > 0:
                weighted += mid * w
                total_w  += w
        if total_w == 0:
            return self.price
        return round(weighted / total_w, 2)

    # ─────────────────────────────────────────────────────────────
    # Risk flags from financial data
    # ─────────────────────────────────────────────────────────────

    def risk_flags(
        self,
        ratios_dict:   dict,
        piotroski_result: dict,
    ) -> list:
        """
        Scans key financial metrics and returns a list of risk strings.
        These appear in the recommendation card under 'Key Risks'.
        """
        risks = []

        # Solvency
        sol = ratios_dict.get("solvency")
        if sol is not None and not sol.empty:
            ic = sol["Interest Coverage (x)"].iloc[0]
            nd = sol["Net Debt / EBITDA (x)"].iloc[0]
            if ic is not None and ic < 2:
                risks.append(f"Interest Coverage is {ic:.1f}x — below 2x, debt service risk")
            if nd is not None and nd > 4:
                risks.append(f"Net Debt/EBITDA of {nd:.1f}x — elevated leverage")

        # Liquidity
        liq = ratios_dict.get("liquidity")
        if liq is not None and not liq.empty:
            cr = liq["Current Ratio (x)"].iloc[0]
            if cr < 1:
                risks.append(f"Current Ratio {cr:.1f}x — below 1x, short-term liquidity risk")

        # Profitability trend
        prof = ratios_dict.get("profitability")
        if prof is not None and len(prof) >= 2:
            npm_now = prof["Net Profit Margin (%)"].iloc[0]
            npm_old = prof["Net Profit Margin (%)"].iloc[-1]
            if npm_now < npm_old * 0.85:
                risks.append(
                    f"Net Profit Margin compressed from {npm_old:.1f}% → {npm_now:.1f}%"
                )
            ebitda_now = prof["EBITDA Margin (%)"].iloc[0]
            if ebitda_now < 10:
                risks.append(f"EBITDA Margin of {ebitda_now:.1f}% — thin operating cushion")

        # Piotroski
        if piotroski_result and "total_score" in piotroski_result:
            score = piotroski_result["total_score"]
            if score <= 3:
                risks.append(f"Piotroski F-Score of {score}/9 — multiple financial health warnings")
            elif score <= 5:
                risks.append(f"Piotroski F-Score of {score}/9 — below average financial health")

        return risks[:5]   # cap at 5 most important risks

    # ─────────────────────────────────────────────────────────────
    # Recommendation
    # ─────────────────────────────────────────────────────────────

    def recommendation(
        self,
        bars:             list,
        ratios_dict:      dict = None,
        piotroski_result: dict = None,
    ) -> dict:
        """
        Generates the full BUY / HOLD / SELL recommendation.

        Logic:
            Count how many bar midpoints are above / below current price.
            If >60% of methodologies imply upside  → BUY
            If >60% of methodologies imply downside → SELL
            Otherwise                               → HOLD

        Returns dict with:
            rating        – "BUY" / "HOLD" / "SELL"
            target_price  – weighted blended target
            upside_pct    – % upside/downside from current price
            conviction    – "High" / "Medium" / "Low"
            summary       – one-paragraph research commentary
            risks         – list of risk strings
            score_above   – how many methods are above current price
            score_below   – how many methods are below current price
        """
        if not bars:
            return {"error": "No valuation bars available."}

        target   = self.weighted_target(bars)
        upside   = round((target - self.price) / self.price * 100, 1) \
                   if self.price > 0 else 0

        # Count methodologies implying upside vs downside
        above = sum(1 for b in bars if b["mid"] > self.price * 1.05)
        below = sum(1 for b in bars if b["mid"] < self.price * 0.95)
        total = len(bars)

        above_pct = above / total if total > 0 else 0
        below_pct = below / total if total > 0 else 0

        if above_pct >= 0.60:
            rating = "BUY"
        elif below_pct >= 0.60:
            rating = "SELL"
        else:
            rating = "HOLD"

        # Conviction level based on how unanimous the methodologies are
        max_pct = max(above_pct, below_pct)
        if max_pct >= 0.80:
            conviction = "High"
        elif max_pct >= 0.60:
            conviction = "Medium"
        else:
            conviction = "Low"

        # Qualitative summary
        ticker    = self.info.get("symbol", "").replace(".NS", "")
        name      = self.info.get("shortName", ticker)
        price_str = f"₹{self.price:,.2f}"
        tgt_str   = f"₹{target:,.2f}"
        up_str    = f"{'▲' if upside >= 0 else '▼'} {abs(upside):.1f}%"

        if rating == "BUY":
            summary = (
                f"We initiate coverage on {name} with a <b>BUY</b> rating and a "
                f"12-month target price of <b>{tgt_str}</b> ({up_str} from current {price_str}). "
                f"{above} out of {total} valuation methodologies imply meaningful upside. "
                f"Our DCF analysis suggests the stock is undervalued on a standalone basis, "
                f"while trading comps confirm the discount relative to sector peers. "
                f"We view the current price as an attractive entry point for long-term investors."
            )
        elif rating == "SELL":
            summary = (
                f"We initiate coverage on {name} with a <b>SELL</b> rating and a "
                f"12-month target price of <b>{tgt_str}</b> ({up_str} from current {price_str}). "
                f"{below} out of {total} valuation methodologies imply downside from current levels. "
                f"The stock appears to be pricing in an overly optimistic growth scenario. "
                f"We recommend investors reduce exposure until valuations become more compelling."
            )
        else:
            summary = (
                f"We initiate coverage on {name} with a <b>HOLD</b> rating and a "
                f"12-month target price of <b>{tgt_str}</b> ({up_str} from current {price_str}). "
                f"Our valuation methodologies present a mixed picture — "
                f"{above} imply upside and {below} imply downside from current levels. "
                f"The stock appears fairly valued at current levels. "
                f"We await a more attractive entry point or a catalyst before turning more constructive."
            )

        # Risk flags
        risks = []
        if ratios_dict and piotroski_result:
            risks = self.risk_flags(ratios_dict, piotroski_result)

        return {
            "rating":       rating,
            "target_price": target,
            "upside_pct":   upside,
            "conviction":   conviction,
            "summary":      summary,
            "risks":        risks,
            "score_above":  above,
            "score_below":  below,
            "total_bars":   total,
            "current_price":self.price,
        }