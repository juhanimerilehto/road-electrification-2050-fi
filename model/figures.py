"""Figures for Merilehto (2026), road transport electrification in Finland to 2050.

Reads data/*.csv (written by model.py) and writes paper/figures/*.pdf and docs/*.png.
Requires matplotlib. Uses Latin Modern if installed, otherwise the matplotlib default.
"""
import csv
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parent.parent
D, F, DOCS = ROOT / "data", ROOT / "paper" / "figures", ROOT / "docs"
F.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(exist_ok=True)

import os
_lm_dirs = [Path("/usr/share/texmf/fonts/opentype/public/lm"), Path("/usr/share/fonts/opentype/lmodern"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/MiKTeX/fonts/opentype/public/lm",
            Path("C:/Program Files/MiKTeX/fonts/opentype/public/lm")]
for d in _lm_dirs:
    for f in ["lmroman10-regular.otf", "lmroman10-bold.otf", "lmroman10-italic.otf"]:
        if (d / f).exists():
            fm.fontManager.addfont(str(d / f))
FAMILY = "Latin Modern Roman" if any("Latin Modern Roman" in f.name for f in fm.fontManager.ttflist) else "DejaVu Serif"
mpl.rcParams.update({
    "font.family": FAMILY, "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#8a8984", "axes.linewidth": 0.6, "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.labelcolor": "#0b0b0b", "text.color": "#0b0b0b",
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "grid.color": "#e4e3df", "grid.linewidth": 0.6, "pdf.fonttype": 3, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03, "mathtext.fontset": "cm", "lines.solid_capstyle": "round",
    "legend.frameon": False,
})
# validated palette (scripts/validate_palette.js, light surface): all checks pass; green needs direct labels
COL = {"low": "#2a78d6", "base": "#eb6834", "high": "#1baf7a"}
NAME = {"low": "Low", "base": "Base", "high": "High"}
INK, INK2, INK3, REF = "#0b0b0b", "#52514e", "#8a8984", "#6b6a66"
STATES = ["low", "base", "high"]
W1 = 6.3


def rows(name):
    with open(D / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fnum(x):
    return float(x)


def save(fig, stem):
    fig.savefig(F / f"{stem}.pdf")
    fig.savefig(DOCS / f"{stem}.png", dpi=200)
    plt.close(fig)


paths = rows("paths.csv")
res = rows("results.csv")


def series(state, key):
    pts = [(int(r["year"]), fnum(r[key])) for r in paths if r["state"] == state]
    return [p[0] for p in pts], [p[1] for p in pts]


def at(state, year, key):
    for r in res:
        if r["state"] == state and int(r["year"]) == year:
            return fnum(r[key])
    raise KeyError((state, year, key))


# ------------------------------------------------------------------ Fig 1: annual electricity, linear scale
hist = {}
with open(D / "sources" / "statfin_12sz_road_electricity_2012-2025_reextracted_2026-11-08.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        hist[int(r["Year"].rstrip("*"))] = fnum(r["Quantity (GWh)"]) / 1000
fig, ax = plt.subplots(figsize=(W1, 3.4))
hy = sorted(hist)
ax.plot(hy, [hist[y] for y in hy], color=INK, lw=2, zorder=4)
ax.annotate("Statistics Finland 12sz\n(road transport)", (2019, hist[2019]), xytext=(-4, 22),
            textcoords="offset points", ha="center", fontsize=7.5, color=INK2)
lo_y, lo_v = series("low", "twh_total")
hi_y, hi_v = series("high", "twh_total")
ax.fill_between(lo_y, lo_v, hi_v, color="#e4e3df", alpha=0.45, lw=0, zorder=1)
for s in STATES:
    yy, vv = series(s, "twh_total")
    ax.plot(yy, vv, color=COL[s], lw=2, zorder=3)
    for cy in (2030, 2035, 2040, 2045, 2050):
        v = vv[yy.index(cy)]
        ax.plot([cy], [v], "o", ms=5, color=COL[s], mec="#fcfcfb", mew=1.2, zorder=5)
    ax.annotate(f"{NAME[s]}  {vv[-1]:.1f} TWh", (2050, vv[-1]), xytext=(7, 0), textcoords="offset points",
                va="center", fontsize=8, color=INK2)
# Fingrid transport less 2025 rail electricity
fg = [(2030, 5.0 - 0.664, "Q3/2026"), (2035, 8.0 - 0.664, "Q3/2026"), (2040, 10.0 - 0.664, "vision 2040")]
ax.plot([p[0] for p in fg], [p[1] for p in fg], "D", ms=5.5, mfc="none", mec=INK2, mew=1.0, zorder=6)
ax.annotate("Fingrid “transport”\nless 2025 rail", (2040, 10.0 - 0.664), xytext=(-8, 14),
            textcoords="offset points", ha="right", fontsize=7.5, color=INK2)
ax.annotate("2030 states retained\nfrom the 2030 study", (2030, at("high", 2030, "twh_total")), xytext=(-10, 26),
            textcoords="offset points", ha="right", fontsize=7.5, color=INK2,
            arrowprops=dict(arrowstyle="-", color=INK3, lw=0.6))
ax.set_xlim(2012, 2050.4)
# MEAE Long-term Climate Plan: electricity in all transport in 2050 (includes rail), 11-15 TWh
ax.plot([2048.7, 2048.7], [11.0, 15.0], color=INK3, lw=3.5, alpha=0.6, solid_capstyle="butt", zorder=2)
ax.annotate("MEAE 2050,\nall transport\n(11\u201315 TWh)", (2048.7, 13.0), xytext=(-6, 0), textcoords="offset points",
            ha="right", va="center", fontsize=7, color=INK2)
ax.set_ylim(0, 16.5)
ax.set_xticks(range(2015, 2051, 5))
ax.set_ylabel("Road-transport electricity (TWh/yr)")
ax.grid(axis="y")
ax.axvline(2025, color=INK3, lw=0.6, ls=(0, (2, 2)))
save(fig, "fig1_paths")

# ------------------------------------------------------------------ Fig 2: 2050 energy by segment
segs = [("twh_car", "Cars (BEV)"), ("twh_phev", "Cars (PHEV, electric km)"), ("twh_van", "Vans"),
        ("twh_bus", "Buses"), ("twh_truck_reg", "Trucks, regional"), ("twh_truck_lh", "Trucks, long-haul")]
fig, axes = plt.subplots(1, 2, figsize=(W1, 2.7), sharey=True, gridspec_kw={"wspace": 0.08})
for ax, yr in zip(axes, (2035, 2050)):
    h = 0.24
    for j, s in enumerate(STATES):
        for i, (k, lab) in enumerate(segs):
            v = at(s, yr, k)
            y = i + (j - 1) * (h + 0.04)
            ax.barh(y, v, height=h, color=COL[s], lw=0)
            if j == 2 or yr == 2050:
                pass
        # direct labels on the largest bar only
    for i, (k, lab) in enumerate(segs):
        v = at("base", yr, k)
        ax.text(max(at(s, yr, k) for s in STATES) + 0.15, i, f"{v:.2f}" if v < 0.995 else f"{v:.1f}",
                va="center", fontsize=7, color=INK2)
    ax.set_title(f"{yr}", loc="left", fontsize=9, color=INK)
    ax.set_xlabel("TWh/yr")
    ax.grid(axis="x")
    ax.set_xlim(0, 11.5)
axes[0].set_yticks(range(len(segs)))
axes[0].set_yticklabels([s[1] for s in segs])
axes[0].invert_yaxis()
handles = [mpl.patches.Patch(color=COL[s], label=NAME[s]) for s in STATES]
fig.legend(handles=handles, loc="upper right", ncol=3, bbox_to_anchor=(0.99, 1.04))
save(fig, "fig2_segments")

# ------------------------------------------------------------------ Fig 3: energy vs peak exposure (MW)
stress = rows("charging_stress.csv")
fig, ax = plt.subplots(figsize=(W1, 2.9))
ylab, yt = [], []
y = 0
for yr in (2030, 2035, 2050):
    for s in STATES:
        avg = at(s, yr, "avg_mw")
        st = {r["case"]: fnum(r["evening_peak_mw"]) for r in stress if r["state"] == s and int(r["year"]) == yr}
        man = at(s, yr, "managed_peak_mw")
        unm = at(s, yr, "unmanaged_peak_mw")
        mod = st.get("Moderate evening (50% in 4 h)")
        ax.plot([man, unm], [y, y], color=COL[s], lw=5, alpha=0.35, solid_capstyle="round")
        ax.plot([avg], [y], "o", ms=6, mfc="#fcfcfb", mec=COL[s], mew=1.5, zorder=4)
        ax.plot([man], [y], "o", ms=6, color=COL[s], mec="#fcfcfb", mew=1.0, zorder=4)
        ax.plot([unm], [y], "s", ms=6, color=COL[s], mec="#fcfcfb", mew=1.0, zorder=4)
        if mod:
            ax.plot([mod], [y], "|", ms=9, color=COL[s], mew=1.6, zorder=4)
        ax.text(unm + 250, y, f"{unm/1000:.1f} GW", va="center", fontsize=7, color=INK2)
        yt.append(y)
        ylab.append(f"{NAME[s]} {yr}")
        y -= 1
    y -= 0.6
ax.axvline(15553, color=REF, lw=0.9, ls=(0, (4, 2)))
ax.text(15553 - 150, y + 0.8, "All-time peak\n15,553 MW\n(Jan 2026)", ha="right", va="bottom", fontsize=7.5, color=INK2)
ax.set_yticks(yt)
ax.set_yticklabels(ylab)
ax.set_xlim(0, 16500)
ax.set_ylim(y + 0.6, 0.6)
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x/1000:g} GW" if x else "0"))
ax.grid(axis="x")
from matplotlib.lines import Line2D
leg = [Line2D([], [], marker="o", ls="", mfc="#fcfcfb", mec=INK2, label="Annual average"),
       Line2D([], [], marker="o", ls="", color=INK2, label="Night block, managed (10 h)"),
       Line2D([], [], marker="|", ls="", color=INK2, mew=1.6, ms=9, label="Evening block, moderate"),
       Line2D([], [], marker="s", ls="", color=INK2, label="Evening block, concentrated (70% in 3 h)")]
ax.legend(handles=leg, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4, fontsize=7.5, handletextpad=0.3,
          columnspacing=1.2)
save(fig, "fig3_peaks")

# ------------------------------------------------------------------ Fig 4: materiality (shares, %)
mat = rows("materiality.csv")
fig, axes = plt.subplots(1, 2, figsize=(W1, 2.6), sharey=True, gridspec_kw={"wspace": 0.1})
labels = []
for k, (ax, title) in enumerate(zip(axes, ["Annual electricity, share of the national\nconsumption range of the year (%)",
                                           "Charging blocks, share of the\nJanuary 2026 record (%)"])):
    y = 0
    yt, labels = [], []
    for yr in (2035, 2045, 2050):
        for s in STATES:
            r = next(m for m in mat if m["state"] == s and int(m["year"]) == yr)
            if k == 0:
                lo_, hi_ = (fnum(v) for v in r["share_national_range_pct"].split("-"))
                ax.plot([lo_, hi_], [y, y], color=COL[s], lw=5, solid_capstyle="round")
                ax.text(hi_ + 0.4, y, f"{lo_:.0f}–{hi_:.0f}", va="center", fontsize=7, color=INK2)
            else:
                lo_, hi_ = fnum(r["managed_peak_share_of_record_pct"]), fnum(r["unmanaged_peak_share_of_record_pct"])
                ax.plot([lo_, hi_], [y, y], color=COL[s], lw=5, alpha=0.35, solid_capstyle="round")
                ax.plot([lo_], [y], "o", ms=5.5, color=COL[s], mec="#fcfcfb", mew=1.0)
                ax.plot([hi_], [y], "s", ms=5.5, color=COL[s], mec="#fcfcfb", mew=1.0)
                ax.text(hi_ + 2, y, f"{lo_:.0f}–{hi_:.0f}", va="center", fontsize=7, color=INK2)
            yt.append(y)
            labels.append(f"{NAME[s]} {yr}")
            y -= 1
        y -= 0.5
    ax.set_title(title, loc="left", fontsize=8.5)
    ax.grid(axis="x")
axes[0].set_xlim(0, 14)
axes[1].set_xlim(0, 90)
axes[0].set_yticks(yt)
axes[0].set_yticklabels(labels)
save(fig, "fig4_materiality")

# ------------------------------------------------------------------ Fig 5: tornado (base, 2050, TWh)
tor = [r for r in rows("tornado.csv") if abs(fnum(r["high_twh"]) - fnum(r["low_twh"])) > 1e-6]
base50 = fnum(tor[0]["base_twh"])
fig, ax = plt.subplots(figsize=(W1, 3.0))
for i, r in enumerate(tor):
    lo_, hi_ = fnum(r["low_twh"]), fnum(r["high_twh"])
    a, b = min(lo_, hi_), max(lo_, hi_)
    ax.barh(i, a - base50, left=base50, height=0.6, color="#8a8984", lw=0)
    ax.barh(i, b - base50, left=base50, height=0.6, color="#c9c8c3", lw=0)
    ax.text(a - 0.08, i, f"{a:.1f}", ha="right", va="center", fontsize=7, color=INK2)
    ax.text(b + 0.08, i, f"{b:.1f}", ha="left", va="center", fontsize=7, color=INK2)
ax.axvline(base50, color=INK, lw=0.8)
ax.set_yticks(range(len(tor)))
ax.set_yticklabels([f"{r['parameter'].replace('kappa', '$\\kappa$')} ({r['range']})" for r in tor], fontsize=7.5)
ax.invert_yaxis()
ax.set_xlabel(f"Base state, 2050 road-transport electricity (TWh/yr); reference {base50:.1f} TWh")
ax.grid(axis="x")
ax.set_xlim(base50 - 2.2, base50 + 1.6)
handles = [mpl.patches.Patch(color="#8a8984", label="Lowers 2050"), mpl.patches.Patch(color="#c9c8c3", label="Raises 2050")]
ax.legend(handles=handles, loc="lower right")
save(fig, "fig5_tornado")

# ------------------------------------------------------------------ Fig 6: delay and stall (base)
rp = rows("robustness_paths.csv")
fig, ax = plt.subplots(figsize=(W1, 3.0))
styles = {"Base": dict(color=COL["base"], lw=2), "Delay 5 yr": dict(color=INK2, lw=1.2, ls=(0, (4, 2))),
          "Delay 10 yr": dict(color=INK2, lw=1.2, ls=(0, (1, 1.5))),
          "Stalled from 2035": dict(color=INK3, lw=1.2, ls=(0, (6, 2, 1, 2))),
          "Stalled from 2030": dict(color=INK3, lw=1.2),
          "2025 entry shares frozen": dict(color="#b5b4af", lw=1.2, ls=(0, (2, 2)))}
offs = {"Base": 0, "Delay 5 yr": 2, "Delay 10 yr": -7, "Stalled from 2035": -4, "Stalled from 2030": 0,
        "2025 entry shares frozen": -4}
for lab, stl in styles.items():
    pts = [(int(r["year"]), fnum(r["twh"])) for r in rp if r["variant"] == lab]
    ax.plot([p[0] for p in pts], [p[1] for p in pts], **stl)
    ax.annotate(f"{lab}  {pts[-1][1]:.1f}", (2050, pts[-1][1]), xytext=(6, offs[lab]), textcoords="offset points",
                va="center", fontsize=7.5, color=INK2)
ax.set_xlim(2025, 2050.3)
ax.set_ylim(0, 13.5)
ax.set_ylabel("TWh/yr")
ax.grid(axis="y")
ax.axvline(2030, color=INK3, lw=0.6, ls=(0, (2, 2)))
save(fig, "fig6_delay_stall")
print("figures written to", F, "and", DOCS, "using", FAMILY)
