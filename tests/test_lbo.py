import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lbo  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def d():
    return lbo.Deal.from_json(ROOT / "deal.json")


def test_sources_equal_uses(d):
    sources, uses = lbo.sources_and_uses(d)
    assert sources.sum() == pytest.approx(uses.sum())
    assert uses["Purchase Enterprise Value"] == pytest.approx(1000)
    assert sources["Sponsor Equity"] == pytest.approx(1000 + 20 + 20 - 400 - 150)


def test_cash_stays_at_minimum_with_full_sweep(d):
    proj = lbo.project(d)
    # With a 100% sweep and senior debt still outstanding, cash should sit at the minimum
    outstanding = proj["Senior Debt"] > 0
    assert proj.loc[outstanding, "Cash"].values == pytest.approx(20)


def test_debt_never_negative(d):
    big = replace(d, revenue_growth=[0.30] * 5)
    proj = lbo.project(big)
    assert (proj["Senior Debt"] >= -1e-9).all()


def test_bridge_sums_to_equity_gain(d):
    r = lbo.returns(d)
    assert sum(r["bridge"].values()) == pytest.approx(r["Exit Equity"] - r["Entry Equity"])


def test_fees_are_the_only_leakage(d):
    sources, uses = lbo.sources_and_uses(d)
    r = lbo.returns(d)
    assert r["bridge"]["Fees"] == pytest.approx(-uses["Transaction Fees"])


def test_irr_matches_moic(d):
    r = lbo.returns(d)
    assert (1 + r["IRR"]) ** d.years == pytest.approx(r["MOIC"])


def test_higher_entry_multiple_lowers_irr(d):
    cheap = lbo.returns(replace(d, entry_multiple=9.0))["IRR"]
    rich = lbo.returns(replace(d, entry_multiple=11.0, exit_multiple=10.0))["IRR"]
    assert rich < cheap


def test_negative_equity_raises(d):
    with pytest.raises(ValueError):
        lbo.sources_and_uses(replace(d, senior_debt_x=9.0, sub_debt_x=2.0))
