# LBO Model

A leveraged buyout model in Python. It builds sources and uses, projects the business, runs a debt schedule with a cash sweep, and calculates sponsor returns (IRR and MOIC). It also splits returns into their three drivers: EBITDA growth, multiple expansion and debt paydown.

## What it does

1. **Sources and uses.** Purchase price from entry multiple x LTM EBITDA, plus fees and minimum cash, funded by senior debt, subordinated debt and sponsor equity.
2. **Operating projections.** Revenue, EBITDA, D&A, interest, taxes, net income, CapEx and working capital.
3. **Debt schedule.** Mandatory amortization on the senior term loan, then a cash sweep that uses excess free cash flow to repay senior debt early. Subordinated debt is a bullet repaid at exit.
4. **Returns.** Exit enterprise value at the exit multiple, less net debt, gives exit equity. MOIC and IRR follow.
5. **Value creation bridge.** Shows how much of the equity gain came from growing EBITDA, from a change in multiple, and from paying down debt.
6. **Sensitivity tables.** IRR across entry vs exit multiples, and across leverage vs revenue growth.

Interest is calculated on beginning-of-year debt balances to avoid a circular reference. This is a common simplification in Excel LBOs.

## Example output

The example is a hypothetical $1.0 billion take-private of a business services company at 10.0x LTM EBITDA. The inputs are illustrative, not a real deal.

**Sources and uses ($mm)**

| Sources | | | Uses | |
|---|---|---|---|---|
| Senior debt (4.0x) | 400.0 | 38.5% | Purchase enterprise value | 1,000.0 |
| Subordinated debt (1.5x) | 150.0 | 14.4% | Transaction fees | 20.0 |
| Sponsor equity | 490.0 | 47.1% | Cash to balance sheet | 20.0 |
| **Total** | **1,040.0** | | **Total** | **1,040.0** |

**Returns**

| | |
|---|---|
| Entry equity | $490.0mm |
| Exit equity (Year 5) | $1,426.6mm |
| **MOIC** | **2.91x** |
| **IRR** | **23.8%** |

Net debt / EBITDA falls from 5.3x at close to 1.5x by Year 5 as the cash sweep pays down $274mm of senior debt.

**Value creation bridge ($mm)**

| | |
|---|---|
| Entry equity | 490.0 |
| + EBITDA growth (100.0 to 168.3 at 10.0x) | 682.8 |
| + Multiple expansion (10.0x in, 10.0x out) | 0.0 |
| + Debt paydown | 273.8 |
| - Transaction fees | (20.0) |
| **Exit equity** | **1,426.6** |

~~~mermaid
xychart-beta
    title "Total debt outstanding, $mm"
    x-axis ["Close", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"]
    y-axis "$mm" 0 --> 600
    bar [550, 519, 477, 422, 355, 276]
~~~

**IRR sensitivity: entry multiple vs exit multiple**

| Entry | 8.0x | 9.0x | 10.0x | 11.0x | 12.0x |
|---|---|---|---|---|---|
| 8.0x | 30.7% | 34.5% | 37.9% | 41.0% | 43.9% |
| 9.0x | 22.9% | 26.5% | 29.7% | 32.7% | 35.4% |
| **10.0x** | 17.3% | 20.8% | **23.8%** | 26.6% | 29.2% |
| 11.0x | 13.0% | 16.3% | 19.2% | 21.9% | 24.4% |
| 12.0x | 9.4% | 12.6% | 15.5% | 18.1% | 20.5% |

**Takeaway:** With no multiple expansion assumed, about 70% of the equity gain comes from EBITDA growth and the rest from debt paydown. Entry price matters most: each 1.0x turn of entry multiple moves IRR by roughly 4 to 6 points, more than a full turn of leverage does.

## How to run

~~~bash
pip install -r requirements.txt
python run.py               # runs the example in deal.json
python run.py my_deal.json  # runs your own inputs
pytest                      # runs the tests
~~~

## Files

| File | Purpose |
|---|---|
| `lbo.py` | Model logic: sources and uses, projections, debt schedule, returns, sensitivities |
| `run.py` | Runs the model, prints results, saves CSVs and charts to `output/` |
| `deal.json` | All deal inputs |
| `tests/test_lbo.py` | Checks sources equal uses, the cash sweep, the returns bridge and IRR math |

## Key formulas

- Free cash flow = net income + D&A - CapEx - change in NWC
- Exit equity = exit EBITDA x exit multiple - net debt at exit
- MOIC = exit equity / entry equity
- IRR = MOIC ^ (1 / years) - 1 (no interim dividends)
- Value creation = EBITDA growth x entry multiple + change in multiple x exit EBITDA + reduction in net debt - fees
