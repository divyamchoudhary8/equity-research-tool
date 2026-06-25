"""
analysis/piotroski.py
─────────────────────
Piotroski F-Score (0–9) — financial health screening tool.

9 binary signals across 3 categories:
    Profitability      (4 signals: F1–F4)
    Leverage/Liquidity (3 signals: F5–F7)
    Efficiency         (2 signals: F8–F9)

Score interpretation:
    7–9  →  Strong  🟢
    4–6  →  Average 🟡
    0–3  →  Weak    🔴
"""

import pandas as pd
from data.fetcher import NSEDataFetcher as F


def safe_div(a, b):
    if b is None or b == 0:
        return 0.0
    return a / b


class PiotroskiScorer:

    def __init__(
        self,
        income_stmt:   pd.DataFrame,
        balance_sheet: pd.DataFrame,
        cash_flow:     pd.DataFrame,
    ):
        self.income_stmt   = income_stmt
        self.balance_sheet = balance_sheet
        self.cash_flow     = cash_flow
        self.years         = F.get_years(income_stmt)
        self.n             = len(self.years)

    def _is(self, labels, col):
        return F.get_safe_value(self.income_stmt, labels, col)

    def _bs(self, labels, col):
        return F.get_safe_value(self.balance_sheet, labels, col)

    def _cf(self, labels, col):
        return F.get_safe_value(self.cash_flow, labels, col)

    # ─────────────────────────────────────────────────────────────
    # Small helper metrics — used by multiple signals
    # ─────────────────────────────────────────────────────────────

    def _roa(self, col) -> float:
        """ROA = Net Income / Total Assets. Used in F1 and F3."""
        net_income   = self._is(['Net Income', 'NetIncome', 'Net Income Common Stockholders'], col)
        total_assets = self._bs(['Total Assets', 'TotalAssets'], col)
        return safe_div(net_income, total_assets)

    def _current_ratio(self, col) -> float:
        """Current Ratio = Current Assets / Current Liabilities. Used in F6."""
        ca = self._bs(['Current Assets', 'Total Current Assets'], col)
        cl = self._bs(['Current Liabilities', 'Total Current Liabilities'], col)
        return safe_div(ca, cl)

    def _debt_ratio(self, col) -> float:
        """Debt Ratio = Long-term Debt / Total Assets. Used in F5."""
        lt_debt      = self._bs(['Long Term Debt', 'LongTermDebt',
                                 'Long Term Debt And Capital Lease Obligation'], col)
        total_assets = self._bs(['Total Assets', 'TotalAssets'], col)
        return safe_div(lt_debt, total_assets)

    def _gross_margin(self, col) -> float:
        """Gross Margin = Gross Profit / Revenue. Used in F8."""
        gross_profit = self._is(['Gross Profit', 'GrossProfit'], col)
        revenue      = self._is(['Total Revenue', 'TotalRevenue', 'Revenue'], col)
        return safe_div(gross_profit, revenue)

    def _asset_turnover(self, col) -> float:
        """Asset Turnover = Revenue / Total Assets. Used in F9."""
        revenue      = self._is(['Total Revenue', 'TotalRevenue', 'Revenue'], col)
        total_assets = self._bs(['Total Assets', 'TotalAssets'], col)
        return safe_div(revenue, total_assets)

    # ─────────────────────────────────────────────────────────────
    # Main scoring method
    # ─────────────────────────────────────────────────────────────

    def calculate(self, year_index: int = 0) -> dict:
        """
        Calculates the full F-Score for one fiscal year.

        Args:
            year_index: Which year to score. 0 = most recent, 1 = one year ago, etc.
                        Needs year_index + 1 to exist for the YoY comparison signals.

        Returns:
            A dict with:
                year        – the fiscal year being scored
                total_score – integer 0 to 9
                rating      – "🟢 Strong" / "🟡 Average" / "🔴 Weak"
                signals     – dict of each signal name → 0 or 1
                metrics     – the underlying numbers used (for display in the dashboard)
        """
        i      = year_index
        i_prev = year_index + 1   # previous year (needed for YoY signals)

        if i_prev >= self.n:
            return {"error": f"Not enough data to score year index {i}. Need at least {i_prev + 1} years."}

        # ── Pull all values we need ───────────────────────────────

        total_assets     = self._bs(['Total Assets', 'TotalAssets'], i)
        cfo              = self._cf(['Operating Cash Flow',
                                     'Total Cash From Operating Activities',
                                     'Cash Flow From Continuing Operating Activities'], i)

        roa_curr         = self._roa(i)
        roa_prev         = self._roa(i_prev)

        cr_curr          = self._current_ratio(i)
        cr_prev          = self._current_ratio(i_prev)

        dr_curr          = self._debt_ratio(i)
        dr_prev          = self._debt_ratio(i_prev)

        gm_curr          = self._gross_margin(i)
        gm_prev          = self._gross_margin(i_prev)

        at_curr          = self._asset_turnover(i)
        at_prev          = self._asset_turnover(i_prev)

        shares_curr      = self._bs(['Ordinary Shares Number', 'Share Issued',
                                     'Common Stock'], i)
        shares_prev      = self._bs(['Ordinary Shares Number', 'Share Issued',
                                     'Common Stock'], i_prev)

        cfo_over_assets  = safe_div(cfo, total_assets)

        # ── Score each of the 9 signals ───────────────────────────
        # Each line is: int(condition) → gives 1 if True, 0 if False

        signals = {
            # PROFITABILITY
            'F1 - ROA Positive':          int(roa_curr > 0),
            'F2 - CFO Positive':          int(cfo > 0),
            'F3 - ROA Improved':          int(roa_curr > roa_prev),
            'F4 - Low Accruals (CFO>ROA)':int(cfo_over_assets > roa_curr),

            # LEVERAGE / LIQUIDITY
            'F5 - Debt Ratio Fell':       int(dr_curr < dr_prev),
            'F6 - Current Ratio Improved':int(cr_curr > cr_prev),
            'F7 - No Dilution':           int(shares_curr <= shares_prev) if shares_curr > 0 and shares_prev > 0 else 0,

            # EFFICIENCY
            'F8 - Gross Margin Improved': int(gm_curr > gm_prev),
            'F9 - Asset Turnover Improved':int(at_curr > at_prev),
        }

        total_score = sum(signals.values())

        if total_score >= 7:
            rating = '🟢 Strong (7–9)'
        elif total_score >= 4:
            rating = '🟡 Average (4–6)'
        else:
            rating = '🔴 Weak (0–3)'

        return {
            'year':        self.years[i],
            'total_score': total_score,
            'rating':      rating,
            'signals':     signals,
            'metrics': {
                'ROA (%)':            round(roa_curr * 100, 2),
                'CFO (₹ Cr)':         round(cfo, 2),
                'CFO / Assets':       round(cfo_over_assets, 4),
                'Current Ratio (x)':  round(cr_curr, 2),
                'Debt Ratio':         round(dr_curr, 3),
                'Gross Margin (%)':   round(gm_curr * 100, 2),
                'Asset Turnover (x)': round(at_curr, 3),
            },
        }

    def get_trend(self) -> pd.DataFrame:
        """
        Scores every available year (requires a prior year for comparison).
        Returns a DataFrame indexed by Year showing F-Score and all 9 signals.

        If we have 5 years of data, this returns scores for years 0–3 (4 rows).
        Year index 4 can't be scored because there's no year 5 to compare against.
        """
        records = []

        for i in range(self.n - 1):   # stop one short — need i+1 to always exist
            result = self.calculate(i)
            if 'error' not in result:
                row = {'Year': result['year'], 'F-Score': result['total_score']}
                row.update(result['signals'])
                records.append(row)

        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records).set_index('Year')