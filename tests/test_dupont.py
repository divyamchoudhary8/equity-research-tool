"""
tests/test_dupont.py
Unit tests for DuPont ROE decomposition.
"""
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.dupont import DuPontAnalyzer


def make_mock_statements():
    """Create minimal mock financial statements for testing."""
    years = pd.to_datetime(["2024-03-31", "2023-03-31", "2022-03-31"])

    income = pd.DataFrame({
        years[0]: {"Total Revenue": 1000e7, "Net Income": 100e7,
                   "EBIT": 150e7, "Pretax Income": 130e7},
        years[1]: {"Total Revenue": 900e7,  "Net Income": 80e7,
                   "EBIT": 130e7, "Pretax Income": 110e7},
        years[2]: {"Total Revenue": 800e7,  "Net Income": 60e7,
                   "EBIT": 110e7, "Pretax Income": 90e7},
    })

    balance = pd.DataFrame({
        years[0]: {"Total Assets": 500e7, "Stockholders Equity": 250e7},
        years[1]: {"Total Assets": 450e7, "Stockholders Equity": 220e7},
        years[2]: {"Total Assets": 400e7, "Stockholders Equity": 200e7},
    })

    return income, balance


def test_3factor_columns():
    inc, bs = make_mock_statements()
    analyzer = DuPontAnalyzer(inc, bs)
    df = analyzer.compute_3_factor()
    assert "Net Profit Margin (%)" in df.columns
    assert "Asset Turnover (x)" in df.columns
    assert "Equity Multiplier (x)" in df.columns
    assert "ROE (%)" in df.columns


def test_3factor_roe_telescopes():
    """ROE must equal NPM × AT × EM (DuPont identity)."""
    inc, bs = make_mock_statements()
    analyzer = DuPontAnalyzer(inc, bs)
    df = analyzer.compute_3_factor()
    for _, row in df.iterrows():
        computed = (row["Net Profit Margin (%)"] / 100 *
                    row["Asset Turnover (x)"] *
                    row["Equity Multiplier (x)"] * 100)
        assert abs(computed - row["ROE (%)"]) < 0.5


def test_5factor_columns():
    inc, bs = make_mock_statements()
    analyzer = DuPontAnalyzer(inc, bs)
    df = analyzer.compute_5_factor()
    assert "Tax Burden" in df.columns
    assert "Interest Burden" in df.columns
    assert "EBIT Margin (%)" in df.columns


def test_output_length():
    inc, bs = make_mock_statements()
    analyzer = DuPontAnalyzer(inc, bs)
    df = analyzer.compute_3_factor()
    assert len(df) == 3


if __name__ == "__main__":
    test_3factor_columns()
    test_3factor_roe_telescopes()
    test_5factor_columns()
    test_output_length()
    print("All DuPont tests passed.")