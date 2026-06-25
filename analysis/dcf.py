"""
analysis/dcf.py
───────────────
Discounted Cash Flow (DCF) Valuation — IB-grade implementation.

Structure:
    1. Historical FCFF calculation from financial statements
    2. Assumption engine — auto-fills from history, fully overridable
    3. FCFF projection — Base / Bull / Bear scenarios
    4. WACC calculation — CAPM for cost of equity, yield for cost of debt
    5. Terminal Value — Gordon Growth Model
    6. DCF sum → Enterprise Value → Equity Value → Per-Share Price
    7. Sensitivity table — WACC × Terminal Growth Rate grid

IB Context:
    A DCF is the most fundamental valuation method in investment banking.
    Unlike comps (which tell you what the market is paying), a DCF tells you
    what a company is WORTH based on its ability to generate cash.
    The output is only as good as the assumptions — which is why we show
    a sensitivity table and three scenarios instead of a single number.
"""

import pandas as pd
import numpy as np
from data.fetcher import NSEDataFetcher as F


def safe_div(a, b, default=0.0):
    if b is None or b == 0 or (isinstance(b, float) and np.isnan(b)):
        return default
    return a / b


class DCFValuation:
    """
    Full DCF engine for any NSE-listed company.

    Usage:
        dcf = DCFValuation(income_stmt, balance_sheet, cash_flow, info)
        hist    = dcf.historical_fcff()          # past FCFF
        assumptions = dcf.auto_assumptions()     # auto-filled from history
        result  = dcf.run(assumptions)           # full DCF result dict
        table   = dcf.sensitivity(assumptions)   # WACC x growth grid
    """

    # India-specific market constants (Damodaran, 2024)
    RISK_FREE_RATE   = 0.07    # 10Y Indian Govt Bond yield ~7%
    EQUITY_RISK_PREM = 0.075   # India ERP (Damodaran) ~7.5%
    PROJECTION_YEARS = 5

    def __init__(
        self,
        income_stmt:   pd.DataFrame,
        balance_sheet: pd.DataFrame,
        cash_flow:     pd.DataFrame,
        info:          dict,
    ):
        self.is_   = income_stmt
        self.bs_   = balance_sheet
        self.cf_   = cash_flow
        self.info  = info
        self.years = F.get_years(income_stmt)
        self.n     = len(self.years)

    # ─────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────

    def _is(self, labels, col): return F.get_safe_value(self.is_, labels, col)
    def _bs(self, labels, col): return F.get_safe_value(self.bs_, labels, col)
    def _cf(self, labels, col): return F.get_safe_value(self.cf_, labels, col)

    def _get_fcff_components(self, col: int) -> dict:
        """
        Extracts all components needed to compute FCFF for one year.

        FCFF = EBIT × (1 − Tax Rate) + D&A − CapEx − ΔWorking Capital

        Note on signs in yfinance:
        - CapEx is stored as NEGATIVE (cash outflow) in cash flow statement
        - D&A is stored as POSITIVE (non-cash add-back) in cash flow statement
        - We take abs() for CapEx so we can subtract it cleanly
        """
        ebit       = self._is(['EBIT', 'Operating Income', 'Ebit'], col)
        pretax     = self._is(['Pretax Income', 'Income Before Tax', 'PretaxIncome'], col)
        net_income = self._is(['Net Income', 'NetIncome', 'Net Income Common Stockholders'], col)

        # Tax rate: derived from (Net Income / Pretax Income)
        # Tax Burden = Net Inc / Pretax → Tax Rate = 1 − Tax Burden
        tax_rate   = 1 - safe_div(net_income, pretax, default=0.75)
        tax_rate   = max(0.10, min(tax_rate, 0.40))   # clamp 10%–40%

        da   = self._cf([
            'Depreciation And Amortization', 'Depreciation',
            'Depreciation Depletion And Amortization', 'Reconciled Depreciation',
        ], col)

        capex = self._cf([
            'Capital Expenditure', 'Purchase Of Property Plant And Equipment',
            'Purchases Of Property Plant And Equipment',
        ], col)
        capex_abs = abs(capex)   # make positive for subtraction

        # Change in Working Capital: increase in WC = cash use (negative for FCFF)
        # yfinance sometimes provides this directly
        delta_wc = self._cf([
            'Change In Working Capital', 'Changes In Working Capital',
            'Change In Other Working Capital',
        ], col)

        # NOPAT = EBIT after tax (no interest effect)
        nopat = ebit * (1 - tax_rate)
        fcff  = nopat + abs(da) - capex_abs - delta_wc

        return {
            'ebit':       round(ebit, 2),
            'tax_rate':   round(tax_rate, 4),
            'nopat':      round(nopat, 2),
            'da':         round(abs(da), 2),
            'capex':      round(capex_abs, 2),
            'delta_wc':   round(delta_wc, 2),
            'fcff':       round(fcff, 2),
        }

    # ─────────────────────────────────────────────────────────────
    # 1. Historical FCFF
    # ─────────────────────────────────────────────────────────────

    def historical_fcff(self) -> pd.DataFrame:
        """
        Computes FCFF for each historical fiscal year.
        Returns a DataFrame indexed by Year.
        """
        records = []
        for i in range(self.n):
            comp = self._get_fcff_components(i)
            rev  = self._is(['Total Revenue', 'TotalRevenue', 'Revenue'], i)
            records.append({
                'Year':        self.years[i],
                'Revenue':     round(rev, 2),
                'EBIT':        comp['ebit'],
                'Tax Rate (%)':round(comp['tax_rate'] * 100, 1),
                'NOPAT':       comp['nopat'],
                'D&A':         comp['da'],
                'CapEx':       comp['capex'],
                'Δ Working Capital': comp['delta_wc'],
                'FCFF':        comp['fcff'],
            })
        return pd.DataFrame(records).set_index('Year')

    # ─────────────────────────────────────────────────────────────
    # 2. Auto-fill assumptions from history
    # ─────────────────────────────────────────────────────────────

    def auto_assumptions(self) -> dict:
        """
        Derives sensible default assumptions from historical data.
        These pre-fill the dashboard sliders — user can override any value.

        Returns dict of assumptions used by run() and sensitivity().
        """
        hist = self.historical_fcff()

        # ── Revenue growth ───────────────────────────────────────
        revenues = hist['Revenue'].values
        # CAGR over available history
        if len(revenues) >= 2 and revenues[-1] > 0:
            cagr = (revenues[0] / revenues[-1]) ** (1 / (len(revenues) - 1)) - 1
        else:
            cagr = 0.12   # fallback: 12%
        cagr = max(0.03, min(cagr, 0.35))   # clamp 3%–35%

        # ── EBIT margin ──────────────────────────────────────────
        ebit_margins = []
        for i in range(self.n):
            rev  = self._is(['Total Revenue', 'TotalRevenue', 'Revenue'], i)
            ebit = self._is(['EBIT', 'Operating Income', 'Ebit'], i)
            if rev > 0:
                ebit_margins.append(safe_div(ebit, rev))
        avg_margin = float(np.mean(ebit_margins)) if ebit_margins else 0.15
        avg_margin = max(0.02, min(avg_margin, 0.50))

        # ── Tax rate ─────────────────────────────────────────────
        tax_rates = []
        for i in range(self.n):
            pretax = self._is(['Pretax Income', 'Income Before Tax', 'PretaxIncome'], i)
            ni     = self._is(['Net Income', 'NetIncome', 'Net Income Common Stockholders'], i)
            if pretax > 0:
                tax_rates.append(1 - safe_div(ni, pretax))
        avg_tax = float(np.mean(tax_rates)) if tax_rates else 0.25
        avg_tax = max(0.10, min(avg_tax, 0.40))

        # ── CapEx as % of revenue ────────────────────────────────
        capex_pcts = []
        for i in range(self.n):
            rev   = self._is(['Total Revenue', 'TotalRevenue', 'Revenue'], i)
            capex = abs(self._cf(['Capital Expenditure',
                                   'Purchase Of Property Plant And Equipment'], i))
            if rev > 0:
                capex_pcts.append(safe_div(capex, rev))
        avg_capex_pct = float(np.mean(capex_pcts)) if capex_pcts else 0.05
        # Cap CapEx at 8% of revenue — yfinance often inflates this for conglomerates
        # (it picks up financial investments alongside physical CapEx)
        avg_capex_pct = max(0.01, min(avg_capex_pct, 0.08))

        # ── D&A as % of revenue ──────────────────────────────────
        da_pcts = []
        for i in range(self.n):
            rev = self._is(['Total Revenue', 'TotalRevenue', 'Revenue'], i)
            da  = abs(self._cf(['Depreciation And Amortization', 'Depreciation',
                                 'Reconciled Depreciation'], i))
            if rev > 0:
                da_pcts.append(safe_div(da, rev))
        avg_da_pct = float(np.mean(da_pcts)) if da_pcts else 0.03
        avg_da_pct = max(0.01, min(avg_da_pct, 0.08))

        # ── WACC components ──────────────────────────────────────
        beta = self.info.get('beta') or 1.0
        beta = max(0.3, min(beta, 2.5))

        cost_of_equity = self.RISK_FREE_RATE + beta * self.EQUITY_RISK_PREM

        total_debt = self._bs(['Total Debt', 'Long Term Debt', 'LongTermDebt'], 0)
        int_exp    = abs(self._is(['Interest Expense', 'InterestExpense'], 0))
        cost_of_debt = safe_div(int_exp, total_debt, default=0.09)
        cost_of_debt = max(0.06, min(cost_of_debt, 0.18))

        mkt_cap   = (self.info.get('marketCap') or 0) / 1e7
        E         = mkt_cap
        D         = total_debt
        V         = E + D if (E + D) > 0 else 1
        wacc      = (E/V) * cost_of_equity + (D/V) * cost_of_debt * (1 - avg_tax)
        wacc      = max(0.07, min(wacc, 0.18))

        # ── Other market data ────────────────────────────────────
        # sharesOutstanding from yfinance is in raw numbers
        # Dividing by 1e7 converts to Crore shares
        # Equity Value is in Crore ₹, so Price = EquityValue(Cr) / Shares(Cr) = ₹/share
        shares_raw = (self.info.get('sharesOutstanding') or 0)
        shares_outstanding = shares_raw / 1e7  # → Crore shares
        cash               = self._bs(['Cash And Cash Equivalents', 'Cash Financial',
                                        'Cash And Short Term Investments'], 0)

        # Most recent revenue as projection base
        base_revenue = float(hist['Revenue'].iloc[0]) if len(hist) > 0 else 1000.0

        return {
            # Projection inputs
            'base_revenue':    round(base_revenue, 2),
            'rev_growth_base': round(cagr, 4),                     # e.g. 0.12 = 12%
            'rev_growth_bull': round(min(cagr + 0.03, 0.35), 4),
            'rev_growth_bear': round(max(cagr - 0.03, 0.03), 4),
            'ebit_margin':     round(avg_margin, 4),
            'tax_rate':        round(avg_tax, 4),
            'capex_pct':       round(avg_capex_pct, 4),
            'da_pct':          round(avg_da_pct, 4),
            'wc_pct':          0.01,    # working capital change as % of revenue
            # WACC
            'beta':            round(beta, 2),
            'risk_free':       self.RISK_FREE_RATE,
            'erp':             self.EQUITY_RISK_PREM,
            'cost_of_equity':  round(cost_of_equity, 4),
            'cost_of_debt':    round(cost_of_debt, 4),
            'debt_weight':     round(D / V, 4),
            'equity_weight':   round(E / V, 4),
            'wacc':            round(wacc, 4),
            # Terminal value
            'terminal_growth': 0.04,    # 4% perpetual growth (India long-run)
            # Market data
            'net_debt':        round(total_debt - cash, 2),
            'shares':          round(shares_outstanding, 4),
            'current_price':   self.info.get('currentPrice',
                               self.info.get('regularMarketPrice', 0)) or 0,
        }

    # ─────────────────────────────────────────────────────────────
    # 3. Project FCFF — one scenario
    # ─────────────────────────────────────────────────────────────

    def _project_scenario(self, assumptions: dict, rev_growth: float) -> pd.DataFrame:
        """
        Projects FCFF for 5 years under a given revenue growth rate.
        All other assumptions (margin, tax, capex, da, wc) are taken from
        the assumptions dict.

        Returns DataFrame with one row per projected year.
        """
        base_rev     = assumptions['base_revenue']
        ebit_margin  = assumptions['ebit_margin']
        tax_rate     = assumptions['tax_rate']
        capex_pct    = assumptions['capex_pct']
        da_pct       = assumptions['da_pct']
        wc_pct       = assumptions['wc_pct']

        records = []
        prev_rev = base_rev

        for yr in range(1, self.PROJECTION_YEARS + 1):
            # Revenue grows by rev_growth each year
            revenue = prev_rev * (1 + rev_growth)
            ebit    = revenue * ebit_margin
            nopat   = ebit * (1 - tax_rate)
            da      = revenue * da_pct
            capex   = revenue * capex_pct
            delta_wc = revenue * wc_pct          # simplified: WC grows with revenue
            fcff    = nopat + da - capex - delta_wc

            records.append({
                'Year':             f'Y+{yr}',
                'Revenue (₹ Cr)':   round(revenue, 2),
                'EBIT (₹ Cr)':      round(ebit, 2),
                'NOPAT (₹ Cr)':     round(nopat, 2),
                'D&A (₹ Cr)':       round(da, 2),
                'CapEx (₹ Cr)':     round(capex, 2),
                'Δ WC (₹ Cr)':      round(delta_wc, 2),
                'FCFF (₹ Cr)':      round(fcff, 2),
            })
            prev_rev = revenue

        return pd.DataFrame(records).set_index('Year')

    # ─────────────────────────────────────────────────────────────
    # 4. Full DCF run — all three scenarios
    # ─────────────────────────────────────────────────────────────

    def run(self, assumptions: dict) -> dict:
        """
        Runs the full DCF for Base, Bull, and Bear scenarios.

        For each scenario:
            1. Project 5 years of FCFF
            2. Discount each year's FCFF at WACC
            3. Compute Terminal Value via Gordon Growth
            4. Sum PV(FCFFs) + PV(Terminal Value) = Enterprise Value
            5. Subtract Net Debt → Equity Value
            6. Divide by shares outstanding → Intrinsic Value per share

        Returns a dict with keys 'base', 'bull', 'bear',
        each containing the projection table and valuation summary.
        """
        wacc           = assumptions['wacc']
        terminal_growth = assumptions['terminal_growth']
        net_debt       = assumptions['net_debt']
        shares         = assumptions['shares']

        results = {}

        for scenario, growth_key in [
            ('base', 'rev_growth_base'),
            ('bull', 'rev_growth_bull'),
            ('bear', 'rev_growth_bear'),
        ]:
            rev_growth = assumptions[growth_key]
            proj       = self._project_scenario(assumptions, rev_growth)
            fcffs      = proj['FCFF (₹ Cr)'].values

            # ── Discount each year's FCFF ───────────────────────
            pv_fcffs = []
            for t, fcff in enumerate(fcffs, start=1):
                pv = fcff / ((1 + wacc) ** t)
                pv_fcffs.append(round(pv, 2))

            sum_pv_fcff = sum(pv_fcffs)

            # ── Terminal Value (Gordon Growth) ───────────────────
            # TV = FCFF_year5 × (1 + g) / (WACC - g)
            # PV of TV = TV / (1 + WACC)^5
            if wacc <= terminal_growth:
                terminal_growth = wacc - 0.01   # safety guard
            tv    = fcffs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
            pv_tv = tv / ((1 + wacc) ** self.PROJECTION_YEARS)

            # ── Enterprise Value → Equity Value ─────────────────
            enterprise_value = sum_pv_fcff + pv_tv
            equity_value     = enterprise_value - net_debt
            intrinsic_price  = safe_div(equity_value, shares, default=0)

            current_price    = assumptions['current_price']
            upside_pct       = safe_div(
                intrinsic_price - current_price, current_price
            ) * 100 if current_price else 0

            if upside_pct > 15:
                verdict = "🟢 Undervalued"
            elif upside_pct < -15:
                verdict = "🔴 Overvalued"
            else:
                verdict = "🟡 Fairly Valued"

            results[scenario] = {
                'projection':       proj,
                'pv_fcffs':         pv_fcffs,
                'sum_pv_fcff':      round(sum_pv_fcff, 2),
                'terminal_value':   round(tv, 2),
                'pv_terminal_value':round(pv_tv, 2),
                'enterprise_value': round(enterprise_value, 2),
                'net_debt':         round(net_debt, 2),
                'equity_value':     round(equity_value, 2),
                'shares':           round(shares, 4),
                'intrinsic_price':  round(intrinsic_price, 2),
                'current_price':    current_price,
                'upside_pct':       round(upside_pct, 1),
                'verdict':          verdict,
                'rev_growth':       round(rev_growth * 100, 1),
                'tv_pct_of_ev':     round(safe_div(pv_tv, enterprise_value) * 100, 1),
            }

        return results

    # ─────────────────────────────────────────────────────────────
    # 5. Sensitivity Table
    # ─────────────────────────────────────────────────────────────

    def sensitivity(self, assumptions: dict) -> pd.DataFrame:
        """
        Generates a WACC × Terminal Growth Rate sensitivity grid.

        Each cell contains the implied intrinsic share price under that
        combination of assumptions. The dashboard colours each cell green
        (above current price) or red (below current price).

        Returns a DataFrame with WACC values as index and growth rates
        as columns.
        """
        wacc_range   = [round(assumptions['wacc'] + delta, 3)
                        for delta in [-0.02, -0.01, 0, 0.01, 0.02]]
        growth_range = [round(assumptions['terminal_growth'] + delta, 3)
                        for delta in [-0.01, -0.005, 0, 0.005, 0.01]]

        # Use base scenario projections as the FCFF source
        base_proj = self._project_scenario(
            assumptions, assumptions['rev_growth_base']
        )
        fcffs = base_proj['FCFF (₹ Cr)'].values

        net_debt = assumptions['net_debt']
        shares   = assumptions['shares']

        data = {}
        for g in growth_range:
            col_label = f"{g*100:.1f}%"
            col_vals  = []
            for w in wacc_range:
                if w <= g:
                    col_vals.append(None)
                    continue
                # Discount FCFFs
                pv_sum = sum(
                    fcff / ((1 + w) ** t)
                    for t, fcff in enumerate(fcffs, start=1)
                )
                # Terminal value
                tv    = fcffs[-1] * (1 + g) / (w - g)
                pv_tv = tv / ((1 + w) ** self.PROJECTION_YEARS)

                ev     = pv_sum + pv_tv
                eq_val = ev - net_debt
                price  = round(safe_div(eq_val, shares), 2)
                col_vals.append(price)
            data[col_label] = col_vals

        index_labels = [f"{w*100:.1f}%" for w in wacc_range]
        df = pd.DataFrame(data, index=index_labels)
        df.index.name   = "WACC ↓  /  Growth →"
        return df