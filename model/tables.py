"""Writes the LaTeX tables of the paper (paper/tables/*.tex) from data/*.csv. Standard library only."""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D, T = ROOT / "data", ROOT / "paper" / "tables"
T.mkdir(parents=True, exist_ok=True)
NAME = {"low": "Low", "base": "Base", "high": "High"}
STATES = ["low", "base", "high"]


def rows(n):
    with open(D / n, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def g(r, k):
    return float(r[k])


def c0(x):
    return f"{x:,.0f}"


def c1(x):
    return f"{x:,.1f}"


def c2(x):
    return f"{x:,.2f}"


def write(name, body):
    (T / name).write_text(body + "\n", encoding="utf-8")


res = {(r["state"], int(r["year"])): r for r in rows("results.csv")}

# --- checkpoint results -------------------------------------------------------------------------------
L = [r"\begin{tabular}{@{}lrrrrrr@{}}", r"\toprule",
     r"State & 2025 & 2030 & 2035 & 2040 & 2045 & 2050 \\", r"\midrule",
     r"\multicolumn{7}{@{}l}{\emph{Annual electricity (TWh)}} \\"]
for s in STATES:
    L.append(f"{NAME[s]} & " + " & ".join(c2(g(res[s, y], 'twh_total')) for y in (2025, 2030, 2035, 2040, 2045, 2050)) + r" \\")
L.append(r"\multicolumn{7}{@{}l}{\emph{Annual average load (MW)}} \\")
for s in STATES:
    L.append(f"{NAME[s]} & " + " & ".join(c0(g(res[s, y], 'avg_mw')) for y in (2025, 2030, 2035, 2040, 2045, 2050)) + r" \\")
L.append(r"\multicolumn{7}{@{}l}{\emph{Battery-electric cars in traffic, year end (thousand)}} \\")
for s in STATES:
    L.append(f"{NAME[s]} & " + " & ".join(c0(g(res[s, y], 'ev_car') / 1000) for y in (2025, 2030, 2035, 2040, 2045, 2050)) + r" \\")
L.append(r"\multicolumn{7}{@{}l}{\emph{Heavy-duty share of road-transport electricity (\%)}} \\")
for s in STATES:
    L.append(f"{NAME[s]} & " + " & ".join(c0(100 * g(res[s, y], 'twh_hd') / g(res[s, y], 'twh_total')) for y in (2025, 2030, 2035, 2040, 2045, 2050)) + r" \\")
L += [r"\bottomrule", r"\end{tabular}"]
write("checkpoints.tex", "\n".join(L))

# --- load metrics -------------------------------------------------------------------------------------
st = {(r["state"], int(r["year"]), r["case"]): g(r, "evening_peak_mw") for r in rows("charging_stress.csv")}
L = [r"\begin{tabular}{@{}llrrrrrr@{}}", r"\toprule",
     r"Year & State & Average & Night block & Evening block, & Evening block, & Difference & Concentrated \\",
     r" & & load & (managed) & moderate & concentrated & of blocks & / record \\", r"\midrule"]
for y in (2030, 2035, 2050):
    for i, s in enumerate(STATES):
        r = res[s, y]
        L.append(f"{y if i == 0 else ''} & {NAME[s]} & {c0(g(r, 'avg_mw'))} & {c0(g(r, 'night_block_mw'))} & "
                 f"{c0(st[s, y, 'Moderate evening (50% in 4 h)'])} & {c0(g(r, 'evening_block_mw'))} & "
                 f"{c0(g(r, 'block_difference_mw'))} & {c0(100 * g(r, 'evening_block_mw') / 15553)}\\% \\\\")
    if y != 2050:
        L.append(r"\addlinespace")
L += [r"\bottomrule", r"\end{tabular}"]
write("loads.tex", "\n".join(L))

# --- heavy-duty connections ---------------------------------------------------------------------------
hv = {(r["state"], int(r["year"])): r for r in rows("heavy_connections.csv")}
L = [r"\begin{tabular}{@{}llrrrrrr@{}}", r"\toprule",
     r"Year & State & E-buses & E-trucks & Depot, & Depot, & Corridor & MCS-point \\",
     r" & & & (reg.\ / long-haul) & managed (MW) & on return (MW) & peak (MW) & at full power \\", r"\midrule"]
for y in (2035, 2050):
    for i, s in enumerate(STATES):
        r = hv[s, y]
        L.append(f"{y if i == 0 else ''} & {NAME[s]} & {c0(round(g(r, 'e_buses'), -1))} & "
                 f"{c0(round(g(r, 'e_trucks_regional'), -1))} / {c0(round(g(r, 'e_trucks_longhaul'), -1))} & "
                 f"{c0(g(r, 'depot_managed_mw'))} & {c0(g(r, 'depot_unmanaged_mw'))} & {c0(g(r, 'corridor_peak_mw'))} & "
                 f"{c0(g(r, 'mcs_full_power_equiv'))} \\\\")
    if y != 2050:
        L.append(r"\addlinespace")
L += [r"\bottomrule", r"\end{tabular}"]
write("heavy.tex", "\n".join(L))

# --- representative sites -----------------------------------------------------------------------------
L = [r"\begin{tabular}{@{}lr@{}}", r"\toprule", r"Site configuration & MW \\", r"\midrule"]
for r in rows("sites.csv"):
    if r["site"].startswith("Memo"):
        continue
    L.append(f"{r['site'].replace('&', 'and').replace('%', chr(92) + '%')} & {c1(g(r, 'mw'))} \\\\")
L += [r"\bottomrule", r"\end{tabular}"]
write("sites.tex", "\n".join(L))

# --- delay and stall ----------------------------------------------------------------------------------
L = [r"\begin{tabular}{@{}llrrrrr@{}}", r"\toprule",
     r"State & Variant & 2035 & 2040 & 2045 & 2050 & $\Delta$2050 \\", r"\midrule"]
dl = rows("delay.csv")
sl = rows("stalled.csv")
for s in STATES:
    first = True
    for r in dl:
        if r["state"] != s:
            continue
        lab = "As constructed" if r["delay_years"] == "0" else f"Delay {r['delay_years']} yr"
        L.append(f"{NAME[s] if first else ''} & {lab} & " + " & ".join(c2(g(r, f'twh_{y}')) for y in (2035, 2040, 2045, 2050))
                 + (" & -- \\\\" if r["delay_years"] == "0" else f" & ${g(r, 'change_2050_pct'):+.0f}\\%$ \\\\"))
        first = False
    for r in sl:
        if r["state"] != s:
            continue
        L.append(f" & Stalled from {r['frozen_from']} & " + " & ".join(c2(g(r, f'twh_{y}')) for y in (2035, 2040, 2045, 2050))
                 + f" & ${g(r, 'change_2050_pct'):+.0f}\\%$ \\\\")
    L.append(r"\addlinespace")
r = next(x for x in sl if x["frozen_from"] == "2025")
L.append(r"\multicolumn{2}{@{}l}{2025 entry shares frozen (2030: " + c2(g(r, "twh_2030")) + r" TWh)} & "
         + " & ".join(c2(g(r, f'twh_{y}')) for y in (2035, 2040, 2045, 2050)) + f" & ${g(r, 'change_2050_pct'):+.0f}\\%$ \\\\")
L += [r"\bottomrule", r"\end{tabular}"]
write("delay.tex", "\n".join(L))

# --- rebound ------------------------------------------------------------------------------------------
L = [r"\begin{tabular}{@{}lcccrrrrcr@{}}", r"\toprule",
     r"State & Plugged-in & Curtailed & Recovered & Head- & To recover & Min.\ time & Unrecovered & Fits & Synchronised \\",
     r" & share, kW & (h) & fraction & room (MW) & (MWh) & (h) & after 4 h (MWh) & 10 h? & peak (MW) \\", r"\midrule"]
for r in rows("rebound.csv"):
    if r["state"] not in ("base", "high"):
        continue
    L.append(f"{NAME[r['state']]} & {float(r['plugged_share']):.1f}, {float(r['charger_kw']):g} & {float(r['curtail_hours']):g} & "
             f"{float(r['recovered_fraction']):g} & {c0(g(r, 'headroom_mw'))} & {c0(g(r, 'to_recover_mwh'))} & "
             f"{c1(g(r, 'min_recovery_hours'))} & {c0(g(r, 'unrecovered_after_4h_mwh'))} & "
             f"{'yes' if r['fits_10h_window'] == 'True' else 'no'} & {c0(g(r, 'peak_synchronised_mw'))} \\\\")
L += [r"\bottomrule", r"\end{tabular}"]
write("rebound.tex", "\n".join(L))

# --- materiality --------------------------------------------------------------------------------------
mt = {(r["state"], int(r["year"])): r for r in rows("materiality.csv")}
L = [r"\begin{tabular}{@{}llrrrrr@{}}", r"\toprule",
     r"Year & State & TWh & Share of national & Share of & Evening blocks, & Ratio to data- \\",
     r" & & & range (\%) & 2025 use (\%) & \% of record & centre buildout (\%) \\", r"\midrule"]
for y in (2035, 2045, 2050):
    for i, s in enumerate(STATES):
        r = mt[s, y]
        lo, hi = r["share_national_range_pct"].split("-")
        dc = r["vs_dc_buildout_pct"]
        dct = f"{float(dc.split('-')[0]):.0f}--{float(dc.split('-')[1]):.0f}" if dc else "--"
        L.append(f"{y if i == 0 else ''} & {NAME[s]} & {c1(g(r, 'twh'))} & {float(lo):.1f}--{float(hi):.1f} & "
                 f"{c1(g(r, 'share_2025_consumption_pct'))} & {c0(g(r, 'managed_peak_share_of_record_pct'))}--"
                 f"{c0(g(r, 'unmanaged_peak_share_of_record_pct'))} & {dct} \\\\")
    if y != 2050:
        L.append(r"\addlinespace")
L += [r"\bottomrule", r"\end{tabular}"]
write("materiality.tex", "\n".join(L))

# --- reproduction (selected) --------------------------------------------------------------------------
rp = rows("reproduction_2030.csv")
keep = [r for r in rp if not r["item"].startswith("12sz road electricity") and "share of 113" not in r["item"]]
L = [r"\begin{tabular}{@{}lrr@{}}", r"\toprule", r"Quantity in the 2030 study & Reproduced & Published \\", r"\midrule"]
for r in keep:
    item = r["item"].replace("%", r"\%").replace("^", r"\^{}").replace("*", r"$\times$")
    L.append(f"{item} & {float(r['reproduced']):,.2f} & {float(r['published']):g} \\\\")
L += [r"\bottomrule", r"\end{tabular}"]
write("reproduction.tex", "\n".join(L))
print("tables written to", T)
