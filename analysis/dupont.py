"""
analysis/dupont.py
──────────────────
DuPont ROE decomposition — 3-Factor and 5-Factor.

3-Factor:  ROE = Net Profit Margin  x  Asset Turnover  x  Equity Multiplier
5-Factor:  ROE = Tax Burden  x  Interest Burden  x  EBIT Margin  x  Asset Turnover  x  Equity Multiplier
"""

import pandas as pd
from data.fetcher import NSEDataFetcher as F


def safe_div(a, b):
    """
    Divides a by b safely.
    Returns 0.0 if b is zero or None, instead of crashing with ZeroDivisionError.
    We need this everywhere in finance — denominators like equity or revenue
    can occasionally come back as zero from yfinance.
    """
    if b is None or b == 0:
        return 0.0
    return a / b


class DuPontAnalyzer:

    def __init__(self, income_stmt: pd.DataFrame, balance_sheet: pd.DataFrame):
        self.income_stmt   = income_stmt
        self.balance_sheet = balance_sheet
        self.years         = F.get_years(income_stmt)   # e.g. [2024, 2023, 2022, 2021, 2020]
        self.n             = len(self.years)

    def _is(self, labels, col):
        """Shorthand: read one value from the income statement."""
        return F.get_safe_value(self.income_stmt, labels, col)

    def _bs(self, labels, col):
        """Shorthand: read one value from the balance sheet."""
        return F.get_safe_value(self.balance_sheet, labels, col)

    def compute_3_factor(self) -> pd.DataFrame:
        """
        Computes 3-Factor DuPont for each fiscal year.

        Formula:
            ROE = Net Profit Margin (%)  x  Asset Turnover (x)  x  Equity Multiplier (x)

        Where:
            Net Profit Margin  = Net Income / Revenue         (profitability)
            Asset Turnover     = Revenue / Total Assets       (efficiency)
            Equity Multiplier  = Total Assets / Equity        (leverage)

        Multiplying them together telescopes back to Net Income / Equity = ROE. ✓

        Returns a DataFrame indexed by Year, one row per fiscal year.
        """
        records = []

        for i in range(self.n):

            net_income = self._is(
                ['Net Income', 'NetIncome', 'Net Income Common Stockholders'], i
            )
            revenue = self._is(
                ['Total Revenue', 'TotalRevenue', 'Revenue'], i
            )
            total_assets = self._bs(
                ['Total Assets', 'TotalAssets'], i
            )
            equity = self._bs(
                ['Stockholders Equity', 'Total Stockholders Equity',
                 'Common Stock Equity'], i
            )

            # The three components
            net_profit_margin = safe_div(net_income, revenue)      # e.g. 0.12 = 12%
            asset_turnover    = safe_div(revenue, total_assets)    # e.g. 1.5x
            equity_multiplier = safe_div(total_assets, equity)     # e.g. 2.0x

            # ROE = product of all three (× 100 to express as %)
            roe = net_profit_margin * asset_turnover * equity_multiplier * 100

            records.append({
                'Year':                  self.years[i],
                'Net Profit Margin (%)': round(net_profit_margin * 100, 2),
                'Asset Turnover (x)':    round(asset_turnover, 3),
                'Equity Multiplier (x)': round(equity_multiplier, 2),
                'ROE (%)':               round(roe, 2),
            })

        return pd.DataFrame(records).set_index('Year')

    def compute_5_factor(self) -> pd.DataFrame:
        """
        Computes 5-Factor DuPont for each fiscal year.

        Formula:
            ROE = Tax Burden  x  Interest Burden  x  EBIT Margin (%)  x  Asset Turnover  x  Equity Multiplier

        Where:
            Tax Burden       = Net Income / Pretax Income    (how much profit survives tax)
            Interest Burden  = Pretax Income / EBIT          (how much EBIT survives interest)
            EBIT Margin      = EBIT / Revenue                (core operating profitability)
            Asset Turnover   = Revenue / Total Assets        (efficiency — same as 3-Factor)
            Equity Multiplier= Total Assets / Equity         (leverage — same as 3-Factor)

        IB use: separates TAX drag from INTEREST drag from OPERATING margin.
        Two companies with the same net margin can look very different here.

        Returns a DataFrame indexed by Year.
        """
        records = []

        for i in range(self.n):

            net_income   = self._is(
                ['Net Income', 'NetIncome', 'Net Income Common Stockholders'], i
            )
            pretax_income = self._is(
                ['Pretax Income', 'Income Before Tax', 'PretaxIncome'], i
            )
            ebit = self._is(
                ['EBIT', 'Operating Income', 'Ebit'], i
            )
            revenue = self._is(
                ['Total Revenue', 'TotalRevenue', 'Revenue'], i
            )
            total_assets = self._bs(
                ['Total Assets', 'TotalAssets'], i
            )
            equity = self._bs(
                ['Stockholders Equity', 'Total Stockholders Equity',
                 'Common Stock Equity'], i
            )

            # The five components
            tax_burden       = safe_div(net_income,    pretax_income)  # close to 1 = low tax
            interest_burden  = safe_div(pretax_income, ebit)           # close to 1 = low interest
            ebit_margin      = safe_div(ebit,          revenue)        # core operating margin
            asset_turnover   = safe_div(revenue,       total_assets)
            equity_multiplier= safe_div(total_assets,  equity)

            roe = (
                tax_burden
                * interest_burden
                * ebit_margin
                * asset_turnover
                * equity_multiplier
                * 100
            )

            records.append({
                'Year':                  self.years[i],
                'Tax Burden':            round(tax_burden, 3),
                'Interest Burden':       round(interest_burden, 3),
                'EBIT Margin (%)':       round(ebit_margin * 100, 2),
                'Asset Turnover (x)':    round(asset_turnover, 3),
                'Equity Multiplier (x)': round(equity_multiplier, 2),
                'ROE (%)':               round(roe, 2),
            })

        return pd.DataFrame(records).set_index('Year')