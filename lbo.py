"""
Leveraged buyout (LBO) model.

Builds sources and uses, projects operations, runs a debt schedule with a
cash sweep, and calculates sponsor returns (IRR and MOIC) at exit. Also
breaks returns into EBITDA growth, multiple expansion and debt paydown.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd


@dataclass
class Deal:
    company: str
    # Entry
    ltm_revenue: float              # ($mm)
    ltm_ebitda: float               # ($mm)
    entry_multiple: float           # EV / LTM EBITDA
    transaction_fees_pct: float     # % of enterprise value
    min_cash: float                 # cash funded on the balance sheet at close ($mm)
    # Financing (as multiples of LTM EBITDA)
    senior_debt_x: float
    sub_debt_x: float
    senior_rate: float
    sub_rate: float
    senior_amort_pct: float         # mandatory amortization, % of original senior debt per year
    cash_sweep_pct: float           # % of excess cash used to repay senior debt
    # Operations
    revenue_growth: list[float]
    ebitda_margin: list[float]
    da_pct_revenue: float
    capex_pct_revenue: float
    nwc_pct_revenue: float
    tax_rate: float
    # Exit
    exit_multiple: float
    years: int = field(init=False)

    def __post_init__(self) -> None:
        if len(self.revenue_growth) != len(self.ebitda_margin):
            raise ValueError("revenue_growth and ebitda_margin must be the same length")
        self.years = len(self.revenue_growth)

    @classmethod
    def from_json(cls, path: str | Path) -> "Deal":
        with open(path) as f:
            return cls(**json.load(f))


def sources_and_uses(d: Deal) -> tuple[pd.Series, pd.Series]:
    ev = d.ltm_ebitda * d.entry_multiple
    fees = ev * d.transaction_fees_pct
    uses = pd.Series({
        "Purchase Enterprise Value": ev,
        "Transaction Fees": fees,
        "Cash to Balance Sheet": d.min_cash,
    })
    senior = d.ltm_ebitda * d.senior_debt_x
    sub = d.ltm_ebitda * d.sub_debt_x
    equity = uses.sum() - senior - sub
    if equity <= 0:
        raise ValueError("Debt exceeds total uses; sponsor equity would be negative")
    sources = pd.Series({
        "Senior Debt": senior,
        "Subordinated Debt": sub,
        "Sponsor Equity": equity,
    })
    return sources, uses


def project(d: Deal) -> pd.DataFrame:
    """Operating model and debt schedule.

    Interest is calculated on beginning-of-year balances, which avoids a
    circular reference (the same simplification often used in Excel LBOs).
    """
    sources, _ = sources_and_uses(d)
    senior = sources["Senior Debt"]
    sub = sources["Subordinated Debt"]
    original_senior = senior
    cash = d.min_cash
    revenue = d.ltm_revenue
    prior_nwc = revenue * d.nwc_pct_revenue

    rows = []
    for i in range(d.years):
        revenue *= 1 + d.revenue_growth[i]
        ebitda = revenue * d.ebitda_margin[i]
        da = revenue * d.da_pct_revenue
        ebit = ebitda - da
        senior_interest = senior * d.senior_rate
        sub_interest = sub * d.sub_rate
        ebt = ebit - senior_interest - sub_interest
        taxes = max(ebt, 0) * d.tax_rate
        net_income = ebt - taxes
        capex = revenue * d.capex_pct_revenue
        nwc = revenue * d.nwc_pct_revenue
        change_nwc = nwc - prior_nwc
        prior_nwc = nwc
        fcf = net_income + da - capex - change_nwc

        # Debt repayment: mandatory amortization first, then the cash sweep
        mandatory = min(original_senior * d.senior_amort_pct, senior)
        available = cash + fcf - d.min_cash - mandatory
        optional = min(max(available, 0) * d.cash_sweep_pct, senior - mandatory)
        senior -= mandatory + optional
        cash = cash + fcf - mandatory - optional

        rows.append({
            "Year": i + 1,
            "Revenue": revenue,
            "EBITDA": ebitda,
            "EBITDA Margin": ebitda / revenue,
            "D&A": da,
            "EBIT": ebit,
            "Interest Expense": senior_interest + sub_interest,
            "Taxes": taxes,
            "Net Income": net_income,
            "CapEx": capex,
            "Change in NWC": change_nwc,
            "Free Cash Flow": fcf,
            "Senior Debt Repaid": mandatory + optional,
            "Senior Debt": senior,
            "Subordinated Debt": sub,
            "Cash": cash,
            "Net Debt": senior + sub - cash,
            "Net Debt / EBITDA": (senior + sub - cash) / ebitda,
            "Interest Coverage": ebitda / (senior_interest + sub_interest),
        })
    return pd.DataFrame(rows).set_index("Year")


def returns(d: Deal) -> dict:
    sources, _ = sources_and_uses(d)
    proj = project(d)
    exit_ebitda = proj["EBITDA"].iloc[-1]
    exit_ev = exit_ebitda * d.exit_multiple
    exit_net_debt = proj["Net Debt"].iloc[-1]
    exit_equity = exit_ev - exit_net_debt
    entry_equity = sources["Sponsor Equity"]
    moic = exit_equity / entry_equity
    irr = moic ** (1 / d.years) - 1 if moic > 0 else -1.0

    # Value creation bridge (sums to the equity gain)
    entry_net_debt = sources["Senior Debt"] + sources["Subordinated Debt"] - d.min_cash
    ebitda_growth = (exit_ebitda - d.ltm_ebitda) * d.entry_multiple
    multiple_change = (d.exit_multiple - d.entry_multiple) * exit_ebitda
    debt_paydown = entry_net_debt - exit_net_debt
    fees_and_leakage = (exit_equity - entry_equity) - (ebitda_growth + multiple_change + debt_paydown)

    return {
        "Entry Equity": entry_equity,
        "Exit EBITDA": exit_ebitda,
        "Exit Enterprise Value": exit_ev,
        "Exit Net Debt": exit_net_debt,
        "Exit Equity": exit_equity,
        "MOIC": moic,
        "IRR": irr,
        "bridge": {
            "EBITDA Growth": ebitda_growth,
            "Multiple Expansion": multiple_change,
            "Debt Paydown": debt_paydown,
            "Fees": fees_and_leakage,
        },
    }


def irr_sensitivity(d: Deal, entry_multiples: list[float], exit_multiples: list[float]) -> pd.DataFrame:
    """IRR across entry multiple (rows) and exit multiple (columns)."""
    return pd.DataFrame(
        {x: [returns(replace(d, entry_multiple=e, exit_multiple=x))["IRR"] for e in entry_multiples]
         for x in exit_multiples},
        index=entry_multiples,
    )


def leverage_sensitivity(d: Deal, senior_levels: list[float], growth_shifts: list[float]) -> pd.DataFrame:
    """IRR across senior leverage (rows) and a shift to every year's revenue growth (columns)."""
    out = {}
    for s in growth_shifts:
        col = []
        for lev in senior_levels:
            dd = replace(d, senior_debt_x=lev, revenue_growth=[g + s for g in d.revenue_growth])
            col.append(returns(dd)["IRR"])
        out[s] = col
    return pd.DataFrame(out, index=senior_levels)
