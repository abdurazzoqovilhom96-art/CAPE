"""Figures of the CAPE manuscript, drawn only from figure_data/*.csv and evidence/numbers.json (both written by
compute_evidence.py): main-text Figs. 2-3 in English and Uzbek (fig4_throughput_*, fig5_exact_gaps_*) and the
supplementary figures (fig2_per_volume_ratios, fig3_bytes_time_gaps). Vector PDF plus 300 dpi PNG.

    python scripts/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.legend_handler import HandlerTuple  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

MS = Path(__file__).resolve().parents[1]
FD, FIG = MS / "figure_data", MS / "figures"
NUM = json.loads((MS / "evidence" / "numbers.json").read_text(encoding="utf-8"))
WF = 160 / 25.4  # two-column template (iicol): full text width 160 mm, for figure*
WC = 76 / 25.4  # one column 76 mm

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "pdf.fonttype": 42, "axes.spines.top": False,
    "axes.spines.right": False, "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
# Okabe-Ito colours (colour-vision-deficiency safe); every series also has its own marker
C = {"pins_opt": "#0072B2", "pins_fast": "#E69F00", "flat": "#7F7F7F", "j0126": "#0072B2", "snemi": "#009E73",
     "hemibrain": "#D55E00", "cape": "#CC79A7"}
MK = {"pins_opt": "o", "pins_fast": "s", "flat": "^", "j0126": "o", "snemi": "s", "hemibrain": "D"}
DSN = {"j0126": "j0126", "snemi": "SNEMI3D", "hemibrain": "hemibrain"}


def strip(ax, xs, ys, color, marker, rng):
    jit = rng.uniform(-0.17, 0.17, size=len(ys))
    ax.scatter(xs + jit, ys, s=9, marker=marker, facecolor="none", edgecolor=color, linewidth=0.7, zorder=3)


def fig_ratios():
    pv = pd.read_csv(FD / "per_volume_ratios.csv")
    groups = [("j0126", "C3_stock_corr", "pins_opt"), ("j0126", "C3_pins_fast", "pins_fast"), ("j0126", "C3_flat", "flat"),
              ("snemi", "C3_stock_corr", "pins_opt"), ("snemi", "C3_pins_fast", "pins_fast"), ("snemi", "C3_flat", "flat"),
              ("hemibrain", "C3_pins_fast", "pins_fast"), ("hemibrain", "C3_flat", "flat")]
    pos, p = [], 0.0
    for i, g in enumerate(groups):
        if i and groups[i - 1][0] != g[0]:
            p += 0.6
        pos.append(p)
        p += 1.0
    pos = np.array(pos)
    fig, axes = plt.subplots(1, 2, figsize=(WF, 2.05), gridspec_kw={"wspace": 0.22})
    rng = np.random.default_rng(20261108)
    for ax, col, ylab, ref in [(axes[0], "speedup", "speed-up  $T_{\\mathrm{comp}}/T_{\\mathrm{CAPE}}$  (log)", 1.0),
                               (axes[1], "peak_ratio", "peak ratio  $M_{\\mathrm{CAPE}}/M_{\\mathrm{comp}}$", 1.0)]:
        for x, (ds, key, kind) in zip(pos, groups):
            y = pv[(pv.dataset == ds) & (pv.comparison == key)][col].dropna().values
            strip(ax, np.full(len(y), x), y, C[kind], MK[kind], rng)
            g = NUM["comparisons"][f"{ds}:{key}"]["speedup_geo" if col == "speedup" else "peak_ratio_geo"]
            ax.hlines(g, x - 0.32, x + 0.32, color="black", linewidth=1.1, zorder=4)
        ax.axhline(ref, color="#555555", linewidth=0.6, linestyle=(0, (3, 2)), zorder=1)
        ax.set_ylabel(ylab)
        ax.set_xticks([])
        ax.set_xlim(pos[0] - 0.6, pos[-1] + 0.6)
        for ds in ["j0126", "snemi", "hemibrain"]:
            xs = [x for x, g in zip(pos, groups) if g[0] == ds]
            ax.annotate(DSN[ds], xy=(np.mean(xs), 0), xycoords=("data", "axes fraction"), xytext=(0, -4),
                        textcoords="offset points", ha="center", va="top", fontsize=7)
    axes[0].set_yscale("log")
    ticks = [0.5, 1, 2, 4, 8, 16, 32]
    axes[0].yaxis.set_major_locator(FixedLocator(ticks))
    axes[0].yaxis.set_minor_locator(NullLocator())
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    axes[0].set_ylim(0.35, 32)
    axes[1].set_ylim(0.2, 1.55)
    axes[0].set_title("(a) encode time", loc="left")
    axes[1].set_title("(b) encode-inclusive peak memory", loc="left")
    handles = [plt.Line2D([], [], marker=MK[k], linestyle="none", markerfacecolor="none", markeredgecolor=C[k],
                          label=lab) for k, lab in [("pins_opt", "upstream pins_opt (corrected)"),
                                                     ("pins_fast", "upstream pins_fast"),
                                                     ("flat", "Crackle flat (no pins)")]]
    handles.append(plt.Line2D([], [], color="black", linewidth=1.1, label="geometric mean"))
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.1),
               handletextpad=0.3, columnspacing=1.6)
    fig.savefig(FIG / "fig2_per_volume_ratios.pdf")
    fig.savefig(FIG / "fig2_per_volume_ratios.png", dpi=300)
    plt.close(fig)


def fig_bytes_time_gaps():
    fig, axes = plt.subplots(2, 1, figsize=(WC, 3.25), gridspec_kw={"height_ratios": [1.1, 1], "hspace": 0.95})
    ax = axes[0]
    dsl = ["j0126", "snemi", "hemibrain"]
    series = [("label section, share of bytes (CAPE)", lambda d: NUM["sections"][d]["labels"]["median"], "#56B4E9", "///"),
              ("pins_opt (corrected): overhead vs flat", lambda d: NUM["excess_time"][d].get(
                  "crackle_pins_opt_corrected_m0", {}).get("median"), C["pins_opt"], None),
              ("pins_fast: overhead vs flat", lambda d: NUM["excess_time"][d]["crackle_pins_fast_m0"]["median"],
               C["pins_fast"], None),
              ("CAPE: overhead vs flat", lambda d: NUM["excess_time"][d]["cape_q1_fast_m0"]["median"], C["cape"], None)]
    bw = 0.19
    for i, (lab, f, col, hatch) in enumerate(series):
        for j, d in enumerate(dsl):
            v = f(d)
            x = j + (i - 1.5) * bw
            if v is None:
                ax.text(x, 9.0, "not evaluated", rotation=90, ha="center", va="bottom", fontsize=5.5,
                        color="#444444")
                continue
            ax.bar(x, 100 * v, width=bw * 0.92, color=col if hatch is None else "white", edgecolor=col,
                   hatch=hatch, linewidth=0.7, label=lab if j == 0 else None)
    ax.set_xticks(range(3))
    ax.set_xticklabels([DSN[d] for d in dsl])
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("median [%]")
    ax.set_ylim(0, 105)
    ax.set_title("(a) bytes vs. encode time", loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.12), ncol=2, frameon=False, handlelength=1.1,
              columnspacing=0.6, fontsize=6.2, handletextpad=0.3)
    ax = axes[1]
    rng = np.random.default_rng(7)
    for j, d in enumerate(dsl):
        g = pd.read_csv(FD / f"gaps_{d}.csv").gap_label_pct.values
        strip(ax, np.full(len(g), j), g, C[d], MK[d], rng)
        ax.hlines(np.median(g), j - 0.32, j + 0.32, color="black", linewidth=1.1, zorder=4)
    ax.set_xticks(range(3))
    ax.set_xticklabels([DSN[d] for d in dsl])
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("$g=(U-L)/U$  [%]")
    ax.set_ylim(-0.4, 12.5)
    ax.set_title("(b) bound gap per volume", loc="left")
    fig.savefig(FIG / "fig3_bytes_time_gaps.pdf")
    fig.savefig(FIG / "fig3_bytes_time_gaps.png", dpi=300)
    plt.close(fig)


TXT = {  # labels of the two main-text figures added in the revision (English / Uzbek)
    "en": {"x": "volume size [voxels]", "y": "throughput [MVoxel/s]", "cape": "CAPE",
           "corr": "pins_opt (corr.)", "fast": "pins_fast", "flat": "flat",
           "j0126": "j0126", "snemi": "SNEMI3D crops", "snemi_scale": "SNEMI3D full/quad.",
           "hemibrain": "hemibrain", "gy": "% of the label section", "g": "bound gap $g=(U-L)/U$",
           "e": "true excess $(U-\\mathrm{OPT})/U$", "ds": {"j0126": "j0126", "snemi": "SNEMI3D", "hemibrain": "hemibrain"}},
    "uz": {"x": "hajm [voksel]", "y": "oʻtkazuvchanlik [MVoksel/s]", "cape": "CAPE",
           "corr": "pins_opt (tuz.)", "fast": "pins_fast", "flat": "flat",
           "j0126": "j0126", "snemi": "SNEMI3D kesmalari", "snemi_scale": "SNEMI3D toʻliq/kv.",
           "hemibrain": "hemibrain", "gy": "yorliq boʻlimidan [%]", "g": "chegara tafovuti $g=(U-L)/U$",
           "e": "haqiqiy ortiqcha $(U-\\mathrm{OPT})/U$", "ds": {"j0126": "j0126", "snemi": "SNEMI3D", "hemibrain": "hemibrain"}},
}


def fig_throughput(lang: str):
    t = TXT[lang]
    d = pd.read_csv(FD / "throughput.csv")
    d = d[d.method.isin(["cape", "corr", "fast", "flat"])]
    col = {"cape": C["cape"], "corr": C["pins_opt"], "fast": C["pins_fast"], "flat": C["flat"]}
    mk = {"j0126": "o", "snemi": "s", "snemi_scale": "*", "hemibrain": "D"}
    # fixed layout: the axes span the column and the legend is centred below them and must not be wider than the
    # figure (a wider legend made the tight bounding box asymmetric and left an empty strip right of the axes)
    fig = plt.figure(figsize=(WC, 1.85))
    ax = fig.add_axes([0.155, 0.385, 0.825, 0.6])
    for (ds, meth), g in d.groupby(["dataset", "method"]):
        ax.scatter(g.voxels, g.mvox_per_s, s=16 if mk[ds] == "*" else 9, marker=mk[ds],
                   facecolor=col[meth] if meth == "cape" else "none", edgecolor=col[meth], linewidth=0.7, zorder=3)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(FixedLocator([1, 3, 10, 30, 100, 300]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_ylim(0.9, 400)
    ax.set_xlabel(t["x"])
    ax.set_ylabel(t["y"])
    h1 = [plt.Line2D([], [], marker="o", linestyle="none", markersize=4, markeredgewidth=0.7,
                     markerfacecolor=col[k] if k == "cape" else "none", markeredgecolor=col[k], label=t[k])
          for k in ["cape", "corr", "fast", "flat"]]
    h2 = [plt.Line2D([], [], marker=mk[k], linestyle="none", markersize=5 if mk[k] == "*" else 4, markeredgewidth=0.7,
                     markerfacecolor="none", markeredgecolor="#333333", label=t[k])
          for k in ["j0126", "snemi", "snemi_scale", "hemibrain"]]
    leg = fig.legend(handles=h1 + h2, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=4, frameon=False,
                     fontsize=5.6, handletextpad=0.3, columnspacing=0.6, labelspacing=0.35, handlelength=0.8,
                     borderaxespad=0.1)
    fig.canvas.draw()
    lw = leg.get_window_extent().width / fig.bbox.width
    assert lw <= 1.0, f"legend wider than the figure ({lw:.2f})"
    fig.savefig(FIG / f"fig4_throughput_{lang}.pdf")
    fig.savefig(FIG / f"fig4_throughput_{lang}.png", dpi=300)
    plt.close(fig)


def fig_exact_gaps(lang: str):
    t = TXT[lang]
    d = pd.read_csv(FD / "exact_gaps.csv")
    dsl = ["j0126", "snemi", "hemibrain"]
    fig, ax = plt.subplots(figsize=(WC, 1.5))
    rng = np.random.default_rng(11)
    for j, ds in enumerate(dsl):
        g = d[d.dataset == ds]
        for off, colname, filled, color in ((-0.18, "bound_gap_pct", False, "#555555"),
                                            (0.18, "excess_pct", True, C[ds])):
            y = g[colname].values
            x = np.full(len(y), j + off) + rng.uniform(-0.09, 0.09, size=len(y))
            ax.scatter(x, y, s=9, marker=MK[ds], facecolor=color if filled else "none", edgecolor=color, linewidth=0.7,
                       zorder=3)
            ax.hlines(np.median(y), j + off - 0.14, j + off + 0.14, color="black", linewidth=1.1, zorder=4)
    ax.set_xticks(range(3))
    ax.set_xticklabels([t["ds"][k] for k in dsl])
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel(t["gy"])
    ax.set_ylim(-0.4, 12.5)
    # legend handles show the markers exactly as plotted: open grey markers (bound gap) and filled dataset-coloured
    # markers (true excess), one per dataset shape
    def mk_(ds, filled):
        col = C[ds] if filled else "#555555"
        return plt.Line2D([], [], marker=MK[ds], linestyle="none", markersize=4, markeredgewidth=0.7,
                          markerfacecolor=col if filled else "none", markeredgecolor=col)
    gap_h = tuple(mk_(ds, False) for ds in dsl)
    exc_h = tuple(mk_(ds, True) for ds in dsl)
    ax.legend(handles=[gap_h, exc_h], labels=[t["g"], t["e"]], handler_map={tuple: HandlerTuple(ndivide=None, pad=0.2)},
              loc="upper left", frameon=False, fontsize=6.3, handletextpad=0.4, labelspacing=0.3, handlelength=3.0)
    fig.savefig(FIG / f"fig5_exact_gaps_{lang}.pdf")
    fig.savefig(FIG / f"fig5_exact_gaps_{lang}.png", dpi=300)
    plt.close(fig)


def main():
    FIG.mkdir(exist_ok=True)
    fig_ratios()
    fig_bytes_time_gaps()
    for lang in ("en", "uz"):
        fig_throughput(lang)
        fig_exact_gaps(lang)
    print("figures written")


if __name__ == "__main__":
    main()
