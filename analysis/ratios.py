"""
analysis/ratios.py
──────────────────
Five categories of financial ratios:
    1. Profitability  — margins, ROE, ROA, ROCE
    2. Liquidity      — current, quick, cash ratios
    3. Solvency       — D/E, interest coverage, net debt/EBITDA
    4. Efficiency     — DIO, DSO, DPO, Cash Conversion Cycle
    5. Valuation      — EV/EBITDA, EV/Revenue, P/E, P/B

All monetary values in ₹ Crores.
"""

import pandas as pd
from data.fetcher import NSEDataFetcher as F


def safe_div(a, b):
    if b is None or b == 0:
        return 0.0
    return a / b


class FinancialRatiosCalculator:

    def __init__(
        self,
        income_stmt:   pd.DataFrame,
        balance_sheet: pd.DataFrame,
        cash_flow:     pd.DataFrame,
        info:          dict,            # market data from yfinance (price, market cap, etc.)
    ):
        self.income_stmt   = income_stmt
        self.balance_sheet = balance_sheet
        self.cash_flow     = cash_flow
        self.info          = info
        self.years         = F.get_years(income_stmt)
        self.n             = len(self.years)

    def _is(self, labels, col):
        return F.get_safe_value(self.income_stmt, labels, col)

    def _bs(self, labels, col):
        return F.get_safe_value(self.balance_sheet, labels, col)

    def _cf(self, labels, col):
        return F.get_safe_value(self.cash_flow, labels, col)

    def _ebitda(self, col) -> float:
        """
        EBITDA = EBIT + Depreciation & Amortization.

        We first try to read EBITDA directly from yfinance (sometimes available).
        If not, we build it from EBIT + D&A pulled from the cash flow statement.

        Note: D&A appears as a positive add-back in the cash flow statement,
        so we take abs() to be safe regardless of sign convention.
        """
        direct = self._is(['EBITDA', 'Ebitda', 'Normalized EBITDA'], col)
        if direct != 0:
            return direct

        ebit = self._is(['EBIT', 'Operating Income', 'Ebit'], col)
        da   = self._cf(['Depreciation And Amortization', 'Depreciation',
                         'Depreciation Depletion And Amortization',
                         'Reconciled Depreciation'], col)
        return ebit + abs(da)

    # ─────────────────────────────────────────────────────────────
    # 1. PROFITABILITY
    # ─────────────────────────────────────────────────────────────

    def profitability(self) -> pd.DataFrame:
        """
        Measures how efficiently the company converts revenue into profit.

        ROCE uses (Equity + Long-term Debt) as the denominator — this is
        'Capital Employed', i.e. the long-term money invested in the business.
        A company only creates value when ROCE > WACC (cost of capital).
        """
        records = []

        for i in range(self.n):
            revenue  = self._is(['Total Revenue', 'TotalRevenue', 'Revenue'], i)
            gp       = self._is(['Gross Profit', 'GrossProfit'], i)
            ebit     = self._is(['EBIT', 'Operating Income', 'Ebit'], i)
            ni       = self._is(['Net Income', 'NetIncome',
                                 'Net Income Common Stockholders'], i)
            ebitda   = self._ebitda(i)
            assets   = self._bs(['Total Assets', 'TotalAssets'], i)
            equity   = self._bs(['Stockholders Equity', 'Total Stockholders Equity',
                                 'Common Stock Equity'], i)
            lt_debt  = self._bs(['Long Term Debt', 'LongTermDebt',
                                 'Long Term Debt And Capital Lease Obligation'], i)

            capital_employed = equity + lt_debt

            records.append({
                'Year':                        self.years[i],
                'Gross Profit Margin (%)':     round(safe_div(gp,     revenue)          * 100, 2),
                'EBITDA Margin (%)':           round(safe_div(ebitda, revenue)          * 100, 2),
                'Operating Profit Margin (%)': round(safe_div(ebit,   revenue)          * 100, 2),
                'Net Profit Margin (%)':       round(safe_div(ni,     revenue)          * 100, 2),
                'ROE (%)':                     round(safe_div(ni,     equity)           * 100, 2),
                'ROA (%)':                     round(safe_div(ni,     assets)           * 100, 2),
                'ROCE (%)':                    round(safe_div(ebit,   capital_employed) * 100, 2),
            })

        return pd.DataFrame(records).set_index('Year')

    # ─────────────────────────────────────────────────────────────
    # 2. LIQUIDITY
    # ─────────────────────────────────────────────────────────────

    def liquidity(self) -> pd.DataFrame:
        """
        Measures the company's ability to meet short-term obligations.

        Quick Ratio excludes inventory because inventory is the least
        liquid current asset — you can't always sell it quickly at full value.
        """
        records = []

        for i in range(self.n):
            ca   = self._bs(['Current Assets', 'Total Current Assets'], i)
            cl   = self._bs(['Current Liabilities', 'Total Current Liabilities'], i)
            inv  = self._bs(['Inventory', 'Inventories'], i)
            cash = self._bs(['Cash And Cash Equivalents', 'Cash Financial',
                             'Cash And Short Term Investments'], i)

            records.append({
                'Year':               self.years[i],
                'Current Ratio (x)':  round(safe_div(ca,           cl), 2),
                'Quick Ratio (x)':    round(safe_div(ca - inv,     cl), 2),
                'Cash Ratio (x)':     round(safe_div(cash,         cl), 2),
            })

        return pd.DataFrame(records).set_index('Year')

    # ─────────────────────────────────────────────────────────────
    # 3. SOLVENCY
    # ─────────────────────────────────────────────────────────────

    def solvency(self) -> pd.DataFrame:
        """
        Measures long-term financial risk — is the company over-leveraged?

        Interest expense is often stored as a negative number in yfinance
        (cash outflow convention), so we take abs() before dividing.

        Net Debt = Total Debt - Cash.
        If a company has more cash than debt, Net Debt is negative
        (it's actually a net cash position — very healthy).
        """
        records = []

        for i in range(self.n):
            debt    = self._bs(['Total Debt', 'Long Term Debt', 'LongTermDebt',
                                'Long Term Debt And Capital Lease Obligation'], i)
            equity  = self._bs(['Stockholders Equity', 'Total Stockholders Equity',
                                'Common Stock Equity'], i)
            assets  = self._bs(['Total Assets', 'TotalAssets'], i)
            ebit    = self._is(['EBIT', 'Operating Income', 'Ebit'], i)
            int_exp = self._is(['Interest Expense', 'InterestExpense',
                                'Net Interest Income'], i)
            cash    = self._bs(['Cash And Cash Equivalents', 'Cash Financial',
                                'Cash And Short Term Investments'], i)
            ebitda  = self._ebitda(i)

            int_exp_abs = abs(int_exp)              # always positive
            net_debt    = max(debt - cash, 0)       # floor at 0

            # Interest coverage shown as None when no interest expense
            # (debt-free company — we display ∞ in the dashboard)
            int_coverage = round(safe_div(ebit, int_exp_abs), 2) if int_exp_abs > 0 else None
            nd_ebitda    = round(safe_div(net_debt, ebitda), 2)  if ebitda > 0      else None

            records.append({
                'Year':                  self.years[i],
                'D/E Ratio (x)':         round(safe_div(debt, equity), 2),
                'Debt / Assets (x)':     round(safe_div(debt, assets), 3),
                'Interest Coverage (x)': int_coverage,
                'Net Debt / EBITDA (x)': nd_ebitda,
            })

        return pd.DataFrame(records).set_index('Year')

    # ─────────────────────────────────────────────────────────────
    # 4. EFFICIENCY
    # ─────────────────────────────────────────────────────────────

    def efficiency(self) -> pd.DataFrame:
        """
        Measures working capital management and asset utilisation.

        DIO uses COGS (not revenue) as the denominator — because inventory
        is recorded at cost, not selling price.

        DPO also uses COGS because accounts payable relates to purchases
        (cost of goods), not to sales.

        CCC = DIO + DSO - DPO
        The lower the better. Negative CCC means you collect before you pay.
        """
        records = []

        for i in range(self.n):
            revenue  = self._is(['Total Revenue', 'TotalRevenue', 'Revenue'], i)
            cogs     = self._is(['Cost Of Revenue', 'CostOfRevenue',
                                 'Cost Of Goods Sold'], i)
            assets   = self._bs(['Total Assets', 'TotalAssets'], i)
            inv      = self._bs(['Inventory', 'Inventories'], i)
            ar       = self._bs(['Accounts Receivable', 'Net Receivables',
                                 'Receivables'], i)
            ap       = self._bs(['Accounts Payable', 'AccountsPayable',
                                 'Payables'], i)

            dio = safe_div(inv, cogs)     * 365 if cogs    > 0 else 0.0
            dso = safe_div(ar,  revenue)  * 365 if revenue > 0 else 0.0
            dpo = safe_div(ap,  cogs)     * 365 if cogs    > 0 else 0.0
            ccc = dio + dso - dpo

            records.append({
                'Year':                         self.years[i],
                'Asset Turnover (x)':           round(safe_div(revenue, assets), 3),
                'DIO - Inventory Days':         round(dio, 1),
                'DSO - Receivable Days':        round(dso, 1),
                'DPO - Payable Days':           round(dpo, 1),
                'Cash Conversion Cycle (Days)': round(ccc, 1),
            })

        return pd.DataFrame(records).set_index('Year')

    # ─────────────────────────────────────────────────────────────
    # 5. VALUATION
    # ─────────────────────────────────────────────────────────────

    def valuation(self) -> pd.DataFrame:
        """
        Market-based multiples — how is the stock priced?

        EV = Market Cap + Total Debt - Cash
        We use current market cap from yfinance info for all years.
        This is an approximation — historical EV would need historical prices.

        P/E and P/B come from yfinance's live info dict (trailing 12 months).
        We only show them for the most recent year (index 0) since they're
        point-in-time market data, not historical accounting data.
        """
        # Market cap from yfinance info is in raw INR — convert to Crores
        mkt_cap = (self.info.get('marketCap') or 0) / 1e7
        pe      =  self.info.get('trailingPE')
        fwd_pe  =  self.info.get('forwardPE')
        pb      =  self.info.get('priceToBook')

        records = []

        for i in range(self.n):
            debt   = self._bs(['Total Debt', 'Long Term Debt', 'LongTermDebt'], i)
            cash   = self._bs(['Cash And Cash Equivalents', 'Cash Financial',
                               'Cash And Short Term Investments'], i)
            ebitda = self._ebitda(i)
            rev    = self._is(['Total Revenue', 'TotalRevenue', 'Revenue'], i)
            ebit   = self._is(['EBIT', 'Operating Income', 'Ebit'], i)

            ev = mkt_cap + debt - cash   # Enterprise Value in ₹ Crores

            records.append({
                'Year':             self.years[i],
                'EV (₹ Cr)':        round(ev, 0),
                'EV / EBITDA (x)':  round(safe_div(ev, ebitda), 2) if ebitda > 0 else None,
                'EV / Revenue (x)': round(safe_div(ev, rev),    2) if rev    > 0 else None,
                'EV / EBIT (x)':    round(safe_div(ev, ebit),   2) if ebit   > 0 else None,
                # Live market data — only meaningful for the most recent year
                'P/E Trailing (x)': round(pe,     2) if pe     and i == 0 else None,
                'P/E Forward (x)':  round(fwd_pe, 2) if fwd_pe and i == 0 else None,
                'P/B (x)':          round(pb,     2) if pb     and i == 0 else None,
            })

        return pd.DataFrame(records).set_index('Year')

    # ─────────────────────────────────────────────────────────────
    # Combined accessor — returns all 5 as a single dict
    # ─────────────────────────────────────────────────────────────

    def all_ratios(self) -> dict:
        return {
            'profitability': self.profitability(),
            'liquidity':     self.liquidity(),
            'solvency':      self.solvency(),
            'efficiency':    self.efficiency(),
            'valuation':     self.valuation(),
        }
    
    