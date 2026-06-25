"""
data/fetcher.py
───────────────
Fetches 5-year annual financial statements for any NSE-listed company
using yfinance. This is the data foundation for the entire project.
"""

import yfinance as yf
import pandas as pd


class NSEDataFetcher:

    SCALE = 1_00_00_000  # 1 Crore = 10,000,000. Dividing by this converts raw INR → Crores.

    def __init__(self, ticker: str):
        """
        ticker: NSE symbol WITHOUT the .NS suffix.
                e.g. pass "RELIANCE", not "RELIANCE.NS"
        """
        self.raw_ticker = ticker.upper().strip()
        self.ticker     = self.raw_ticker + ".NS"      # Yahoo Finance NSE format
        self.yf_ticker  = yf.Ticker(self.ticker)

    def get_all_data(self) -> dict:
        """
        Fetches all three financial statements + market info.

        Returns a dict with keys:
            income_stmt   → pd.DataFrame  (rows = line items, cols = fiscal years)
            balance_sheet → pd.DataFrame
            cash_flow     → pd.DataFrame
            info          → dict  (current price, market cap, sector, etc.)

        Column order: newest fiscal year is always column index 0.
        All values are in RAW INR here — we convert to Crores inside analysis.
        """
        # yfinance changed attribute names in v0.2.x
        # We try the new names first, fall back to old names if they don't exist.
        try:
            income_stmt   = self.yf_ticker.income_stmt
            balance_sheet = self.yf_ticker.balance_sheet
            cash_flow     = self.yf_ticker.cash_flow
        except AttributeError:
            income_stmt   = self.yf_ticker.financials   # old API
            balance_sheet = self.yf_ticker.balance_sheet
            cash_flow     = self.yf_ticker.cashflow      # old API

        if income_stmt is None or income_stmt.empty:
            raise ValueError(
                f"No data found for '{self.ticker}'. "
                "Check that the ticker is a valid NSE symbol."
            )

        # Keep only the 5 most recent fiscal years
        income_stmt   = income_stmt.iloc[:, :5]
        balance_sheet = balance_sheet.iloc[:, :5]
        cash_flow     = cash_flow.iloc[:, :5]

        # Drop years where >60% of values are missing (yfinance often returns
        # sparse data for the oldest year — it shows as all-zeros on the dashboard)
        income_stmt   = income_stmt.loc[:, income_stmt.isnull().mean() < 0.6]
        balance_sheet = balance_sheet.loc[:, balance_sheet.isnull().mean() < 0.6]
        cash_flow     = cash_flow.loc[:, cash_flow.isnull().mean() < 0.6]

        info = self.yf_ticker.info

        return {
            "income_stmt":   income_stmt,
            "balance_sheet": balance_sheet,
            "cash_flow":     cash_flow,
            "info":          info,
        }

    @staticmethod
    def get_safe_value(df: pd.DataFrame, labels: list, col: int = 0) -> float:
        """
        Safely reads one value from a financial statement DataFrame.

        Why a list of labels?
        yfinance uses different field names across versions and ticker types.
        e.g. revenue might be "Total Revenue" or "TotalRevenue".
        We try each label in order and return the first one that exists.

        Args:
            df:     A financial statement DataFrame (income_stmt, balance_sheet, etc.)
            labels: List of possible row names to try, in priority order.
            col:    Column index. 0 = most recent fiscal year.

        Returns:
            Value in INR Crores, or 0.0 if no label matched or value is NaN.
        """
        for label in labels:
            if label in df.index:
                val = df.loc[label].iloc[col]
                if pd.notna(val):
                    return float(val) / NSEDataFetcher.SCALE
        return 0.0

    @staticmethod
    def get_years(df: pd.DataFrame) -> list:
        """
        Extracts fiscal year integers from DataFrame column headers.
        yfinance stores columns as Timestamps — this converts them to plain ints.

        e.g. [Timestamp('2024-03-31'), ...] → [2024, 2023, 2022, ...]
        """
        return [col.year for col in df.columns]