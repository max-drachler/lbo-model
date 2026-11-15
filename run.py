"""
Run the LBO on a deal file and save the outputs.

Usage:
    python run.py               # uses deal.json
    python run.py my_deal.json  # uses your own inputs
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np

import lbo

OUT = Path(__file__).parent / "output"


def main(path: str = "deal.json") -> None:
    d = lbo.Deal.from_json(path)
    OUT.mkdir(exist_ok=True)

    sources, uses = lbo.sources_and_uses(d)
    proj = lbo.project(d)
    r = lbo.returns(d)

    print(f"\nLBO Model: {d.company}  ($ in millions)\n")
    print("Sources")
    for k, v in sources.items():
        print(f"  {k:<28}${v:>8,.1f}  {v / sources.sum():>6.1%}")
    print(f"  {'Total':<28}${sources.sum():>8,.1f}\n")
    print("Uses")
    for k, v in uses.items():
        print(f"  {k:<28}${v:>8,.1f}")
    print(f"  {'Total':<28}${uses.sum():>8,.1f}\n")

    table = proj.copy()
    pct_cols = ["EBITDA Margin"]
    x_cols = ["Net Debt / EBITDA", "Interest Coverage"]
    shown = table.T.astype(object)
    for row in shown.index:
        if row in pct_cols:
            shown.loc[row] = [f"{v:.1%}" for v in table[row]]
        elif row in x_cols:
            shown.loc[row] = [f"{v:.1f}x" for v in table[row]]
        else:
            shown.loc[row] = [f"{v:,.1f}" for v in table[row]]
    print(shown.to_string())
    print()

    print("Returns")
    print(f"  Entry equity            ${r['Entry Equity']:,.1f}")
    print(f"  Exit enterprise value   ${r['Exit Enterprise Value']:,.1f}")
    print(f"  Exit net debt           ${r['Exit Net Debt']:,.1f}")
    print(f"  Exit equity             ${r['Exit Equity']:,.1f}")
    print(f"  MOIC                    {r['MOIC']:.2f}x")
    print(f"  IRR                     {r['IRR']:.1%}\n")

    print("Value creation bridge")
    for k, v in r["bridge"].items():
        print(f"  {k:<22}${v:>8,.1f}")
    print()

    entry = [8.0, 9.0, 10.0, 11.0, 12.0]
    exits = [8.0, 9.0, 10.0, 11.0, 12.0]
    sens = lbo.irr_sensitivity(d, entry, exits)
    lev = lbo.leverage_sensitivity(d, [3.0, 3.5, 4.0, 4.5, 5.0], [-0.04, -0.02, 0.0, 0.02, 0.04])

    def show(t, row_fmt, col_fmt, title):
        t = t.copy()
        t.index = [row_fmt.format(x) for x in t.index]
        t.columns = [col_fmt.format(c) for c in t.columns]
        print(title)
        print(t.map(lambda v: f"{v:.1%}").to_string())
        print()

    show(sens, "{:.1f}x", "{:.1f}x", "IRR: entry multiple (rows) vs exit multiple (columns)")
    show(lev, "{:.1f}x", "{:+.0%}", "IRR: senior leverage (rows) vs change in annual revenue growth (columns)")

    proj.round(2).to_csv(OUT / "projection.csv")
    sens.round(4).to_csv(OUT / "irr_entry_vs_exit.csv")
    lev.round(4).to_csv(OUT / "irr_leverage_vs_growth.csv")

    # Chart 1: deleveraging
    fig, ax = plt.subplots(figsize=(8, 4.5))
    years = ["Close"] + [f"Year {i}" for i in proj.index]
    senior = [sources["Senior Debt"]] + list(proj["Senior Debt"])
    sub = [sources["Subordinated Debt"]] + list(proj["Subordinated Debt"])
    lev_x = [(sources["Senior Debt"] + sources["Subordinated Debt"] - d.min_cash) / d.ltm_ebitda] + list(proj["Net Debt / EBITDA"])
    ax.bar(years, senior, color="#1f4e79", label="Senior debt")
    ax.bar(years, sub, bottom=senior, color="#9fb8d6", label="Subordinated debt")
    ax.set_ylabel("$mm")
    ax.set_title(f"{d.company}: debt paydown")
    ax.spines[["top", "right"]].set_visible(False)
    ax2 = ax.twinx()
    ax2.plot(years, lev_x, color="#c0504d", marker="o", label="Net debt / EBITDA")
    ax2.set_ylim(0, max(lev_x) * 1.3)
    ax2.set_ylabel("Net debt / EBITDA (x)")
    ax2.spines[["top"]].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT / "debt_paydown.png", dpi=150)
    plt.close(fig)

    # Chart 2: value creation bridge
    steps = [("Entry\nequity", r["Entry Equity"])] + [(k.replace(" ", "\n"), v) for k, v in r["bridge"].items()]
    fmt = lambda v: f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"
    fig, ax = plt.subplots(figsize=(9, 4.8))
    running = 0.0
    for i, (label, v) in enumerate(steps):
        if i == 0:
            ax.bar(label, v, color="#1f4e79")
            running = v
        else:
            ax.bar(label, v, bottom=running if v >= 0 else running + v,
                   color="#4f8a5b" if v >= 0 else "#c0504d")
            running += v
        ax.text(i, max(running, running - v) + 15, fmt(v), ha="center", fontsize=9)
    ax.bar("Exit\nequity", r["Exit Equity"], color="#1f4e79")
    ax.text(len(steps), r["Exit Equity"] + 15, f"${r['Exit Equity']:,.0f}", ha="center", fontsize=9)
    ax.set_title(f"Sponsor value creation: {r['MOIC']:.2f}x MOIC, {r['IRR']:.1%} IRR")
    ax.set_ylabel("$mm")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "value_creation.png", dpi=150)
    plt.close(fig)

    # Chart 3: IRR heatmap
    fig, ax = plt.subplots(figsize=(7, 4.5))
    data = sens.values
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0.0, vmax=0.45)
    ax.set_xticks(range(len(exits)), [f"{x:.1f}x" for x in exits])
    ax.set_yticks(range(len(entry)), [f"{x:.1f}x" for x in entry])
    ax.set_xlabel("Exit multiple")
    ax.set_ylabel("Entry multiple")
    ax.set_title("IRR sensitivity")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, f"{data[i, j]:.1%}", ha="center", va="center", fontsize=9)
    cb = fig.colorbar(im, ax=ax, label="IRR")
    cb.ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    fig.tight_layout()
    fig.savefig(OUT / "irr_heatmap.png", dpi=150)
    plt.close(fig)

    print(f"Outputs saved to {OUT}/")


if __name__ == "__main__":
    main(*sys.argv[1:])
