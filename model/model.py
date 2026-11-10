"""Road transport electrification in Finland: stock-flow scenario model to 2050.

Merilehto (2026), extension of the 2030 study (doi:10.5281/zenodo.21078010).
Standard library only. Run from the repository root:

    python model/model.py

Writes data/*.csv and stops (AssertionError) if
  * the 2030 study's published numbers cannot be reproduced from its stated inputs,
  * the 2025 Statistics Finland value is not reproduced by the calibrated stock model, or
  * the retained 2030 low/base/high states are not reproduced exactly by the stock-flow model.

All scenarios are assumed planning states, not forecasts.
"""
from __future__ import annotations

import csv
import hashlib
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INPUTS = DATA / "inputs"
SOURCES = DATA / "sources"

YEARS = list(range(2025, 2051))
CHECK = [2025, 2030, 2035, 2040, 2045, 2050]
STATES = ["low", "base", "high"]
HOURS = 8760.0

# ---------------------------------------------------------------------------------------------
# 0. Retained 2030 study (Merilehto 2026, doi:10.5281/zenodo.21078010) -- stated inputs
# ---------------------------------------------------------------------------------------------
ARCHIVED_CSV = "statfin_12sz_road_transport_electricity_2012-2025_accessed_2026-06-12.csv"
ARCHIVED_MD5 = "5be3534790db3345c2fc1e7dd1ae9aa8"  # md5 of the CSV deposited on Zenodo with the 2030 study
APPENDIX_C = {  # Table 7 (Appendix C) of the 2030 study: year -> (TJ, GWh)
    2012: (0, 0), 2013: (3, 1), 2014: (11, 3), 2015: (20, 5), 2016: (35, 10), 2017: (79, 22),
    2018: (166, 46), 2019: (261, 73), 2020: (453, 126), 2021: (850, 236), 2022: (1126, 313),
    2023: (1968, 547), 2024: (2796, 777), 2025: (4003, 1112),
}
CAGR_2030 = {"low": 0.15, "base": 0.22, "high": 0.28}            # Table 3
PUBLISHED_2030_GWH = {"low": 2237, "base": 3005, "high": 3821}  # Table 3
FINGRID_2025_TWH = 84.6                                          # 2030 study, eq. (6)
FINGRID_Q3_2025_MID_2030 = 113.0                                 # Table 3 note (103-123 TWh midpoint)


def read_2030_series() -> tuple[dict[int, int], str]:
    """Return {year: GWh} for road-transport electricity 2012-2025 and the provenance string."""
    archived = INPUTS / ARCHIVED_CSV
    if archived.exists():
        raw = archived.read_bytes()
        md5 = hashlib.md5(raw).hexdigest()
        assert md5 == ARCHIVED_MD5, f"{ARCHIVED_CSV}: md5 {md5} differs from the Zenodo deposit {ARCHIVED_MD5}"
        text, prov = raw.decode("utf-8-sig", errors="replace"), f"data/inputs/{ARCHIVED_CSV} (md5 verified)"
    else:  # fall back to the identical-valued PX-Web re-extraction (see data/inputs/README.md)
        p = SOURCES / "statfin_12sz_road_electricity_2012-2025_reextracted_2026-11-08.csv"
        text, prov = p.read_text(encoding="utf-8-sig"), f"data/sources/{p.name} (archived CSV not present)"
    series: dict[int, int] = {}
    lines = text.splitlines()
    delim = max([",", ";", "\t"], key=lambda d: sum(l.count(d) for l in lines))
    for fields in csv.reader(lines, delimiter=delim):
        if not fields:
            continue
        m = re.fullmatch(r"\s*(20[12]\d)\*?\s*", fields[0])
        if not m:
            continue
        nums = []
        for fld in fields[1:]:
            t = fld.strip().replace(" ", "").replace(" ", "")
            t = t.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", t) else t.replace(",", ".")
            try:
                nums.append(float(t))
            except ValueError:
                pass
        for a, b in zip(nums, nums[1:]):  # GWh is the value that follows TJ and equals TJ/3.6 rounded
            if abs(a / 3.6 - b) <= 1.0 and b == int(b) and (a > b or a == b == 0):
                series[int(m.group(1))] = int(b)
                break
    return series, prov


def reproduce_2030_study(series: dict[int, int]) -> list[dict]:
    """Recompute every headline number of the 2030 study and assert it matches the published value."""
    rows = []

    def chk(item, value, published, tol):
        assert abs(value - published) <= tol, f"2030 study reproduction failed: {item}: {value} vs {published}"
        rows.append({"item": item, "reproduced": round(value, 4), "published": published})

    for y, (_tj, gwh) in APPENDIX_C.items():
        chk(f"12sz road electricity {y} (GWh)", series[y], gwh, 0)
    e25 = series[2025]
    for s, g in CAGR_2030.items():
        v = e25 * (1 + g) ** 5
        chk(f"2030 {s} (GWh), 1112*(1+{g})^5", v, PUBLISHED_2030_GWH[s], 0.5)
        chk(f"2030 {s} share of 113 TWh (%)", 100 * v / 1000 / FINGRID_Q3_2025_MID_2030,
            {"low": 2.0, "base": 2.7, "high": 3.4}[s], 0.05)
    for s, txt in [("low", 2.24), ("high", 3.82)]:
        chk(f"2030 {s} (TWh, abstract)", e25 * (1 + CAGR_2030[s]) ** 5 / 1000, txt, 0.005)
    chk("2030 base (TWh, abstract 'about 3.0')", e25 * 1.22 ** 5 / 1000, 3.0, 0.05)
    cagr = lambda a, b: 100 * ((series[b] / series[a]) ** (1 / (b - a)) - 1)
    for (a, b), pub in {(2014, 2024): 74.3, (2016, 2025): 68.8, (2019, 2024): 60.5, (2020, 2025): 54.6,
                        (2022, 2025): 52.6, (2023, 2025): 42.6}.items():
        chk(f"CAGR {a}-{b} (%)", cagr(a, b), pub, 0.05)
    chk("2025 share of 84.6 TWh (%)", 100 * e25 / 1000 / FINGRID_2025_TWH, 1.31, 0.005)
    chk("2025 average load (MW)", e25 * 1000 / HOURS, 127, 0.5)
    base = e25 * 1.22 ** 5
    chk("2030 base average load (MW)", base * 1000 / HOURS, 343, 0.5)
    chk("2030 base daily energy (GWh)", base / 365, 8.2, 0.05)
    chk("2030 evening block 70%/3 h (GW)", base / 365 * 0.70 / 3, 1.92, 0.005)
    chk("2030 managed block 100%/10 h (GW)", base / 365 / 10, 0.8, 0.05)
    chk("2025-2030 base increment (TWh)", (base - e25) / 1000, 1.9, 0.05)
    t4 = [1.45, 0.28, 0.40, 0.13, 0.48, 0.26]  # Table 4 segment energies (TWh)
    chk("Table 4 bottom-up total (TWh)", sum(t4), 3.00, 0.005)
    for item, mw, pub in [("Table 6 row 1 (MW)", 100_000 * 3, 300), ("Table 6 row 2 (MW)", 250_000 * 3, 750),
                          ("Table 6 row 3 (MW)", 250_000 * 5, 1250)]:
        chk(item, mw / 1000, pub, 0)
    return rows


# ---------------------------------------------------------------------------------------------
# 1. Observed stock, entries and mileage (Statistics Finland / AUT, accessed 8 Nov 2026)
# ---------------------------------------------------------------------------------------------
def read_stock() -> dict:
    """Vehicles in traffic use at year end, Statistics Finland table 11ie."""
    out: dict = {}
    with open(SOURCES / "statfin_11ie_stock_by_power_2012-2025_accessed_2026-11-08.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cls, y = r["Vehicle class"], int(r["Year"])
            tot = int(r["Total Number of the vehicles"])
            bev = int(r["Electricity Number of the vehicles"])
            phev = int(r["Petrol/Electricity (plug-in hybrid) Number of the vehicles"]) + \
                int(r["Diesel/Electricity (plug-in hybrid) Number of the vehicles"])
            out.setdefault(cls, {})[y] = (tot, bev, phev)
    return out


def read_vkm() -> dict:
    """Traffic performance (million vehicle-km), Statistics Finland table 12jx."""
    out: dict = {}
    with open(SOURCES / "statfin_12jx_vehicle_km_2012-2025_accessed_2026-11-08.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["Vehicle class"], {})[int(r["Year"])] = float(r["Traffic performance"])
    return out


STOCK, VKM = read_stock(), read_vkm()
CARS, VANS, LORRIES, BUSES = "Passenger cars", "Vans", "Lorries, > 3.5 tonnes", "Buses, coaches"

# Entries to the fleet in 2025 (new registrations + used imports where reported). AUT (2026) annual review:
# 71,888 new cars, 41,092 used imported cars, 10,435 new vans, 2,929 new trucks, 420 new buses.
ENTRIES_2025 = {"car": 71_888 + 41_092, "van": 10_435, "truck": 2_929, "bus": 420}

# Truck segmentation (assumption): Statistics Finland reports lorries > 3.5 t only. 60 % of the stock is treated
# as regional/urban (depot-based), 40 % as long-haul; regional mileage 22,000 km/yr, long-haul mileage solved so
# that the two segments reproduce the 2025 lorry traffic performance exactly.
TRUCK_REGIONAL_SHARE, KM_TRUCK_REGIONAL = 0.60, 22_000.0


def base_year() -> dict:
    s = {}
    tot_c, bev_c, phev_c = STOCK[CARS][2025]
    tot_v, bev_v, _ = STOCK[VANS][2025]
    tot_t, bev_t, _ = STOCK[LORRIES][2025]
    tot_b, bev_b, _ = STOCK[BUSES][2025]
    km_t_total = VKM[LORRIES][2025] * 1e6
    n_reg, n_lh = tot_t * TRUCK_REGIONAL_SHARE, tot_t * (1 - TRUCK_REGIONAL_SHARE)
    km_lh = (km_t_total - n_reg * KM_TRUCK_REGIONAL) / n_lh
    s["stock"] = {"car": tot_c, "van": tot_v, "truck_reg": n_reg, "truck_lh": n_lh, "bus": tot_b}
    s["km"] = {"car": VKM[CARS][2025] * 1e6 / tot_c, "van": VKM[VANS][2025] * 1e6 / tot_v,
               "truck_reg": KM_TRUCK_REGIONAL, "truck_lh": km_lh, "bus": VKM[BUSES][2025] * 1e6 / tot_b}
    s["tau"] = {"car": ENTRIES_2025["car"] / tot_c, "van": ENTRIES_2025["van"] / tot_v,
                "truck_reg": ENTRIES_2025["truck"] / tot_t, "truck_lh": ENTRIES_2025["truck"] / tot_t,
                "bus": ENTRIES_2025["bus"] / tot_b}
    return s


BASE = base_year()

# ---------------------------------------------------------------------------------------------
# 2. Engineering parameters (vehicle level) and survival
# ---------------------------------------------------------------------------------------------
# Energy intensity at the vehicle (kWh/km). Cars, PHEV, vans and buses retained from the 2030 study (Table 4);
# trucks from Oeko-Institut real-world data (0.96 kWh/km average, 1.14 kWh/km for 34-40 t) with a cold-climate
# margin for long-haul (assumption).
KWH_KM = {"car": 0.185, "phev": 0.19, "van": 0.25, "truck_reg": 1.0, "truck_lh": 1.3, "bus": 1.0}
PHEV_EKM = 6_000.0          # electric km per average-age PHEV per year (2030 study, Table 4)
LOSS = 0.10                 # charging losses grid-to-battery (ADAC 2026: 5-7 % wallbox, 13-24 % socket)
WEIBULL_K = 3.0
# Mean register life is set to 1/tau, so that 2025 fleet entries are consistent with a steady-state fleet
# (cars: 23.9 yr, close to the 23.0-yr average scrapping age reported by AUT for 2025).
MEAN_LIFE = {c: 1.0 / BASE["tau"][c] for c in BASE["tau"]}
# Annual mileage declines with vehicle age: km(a) = c * exp(-a / theta). c is set so that the steady-state fleet
# average equals the observed 2025 average (Statistics Finland 12jx / 11ie) and theta so that a new vehicle drives
# KM_NEW_RATIO times the fleet average (assumption: new cars about 20,000 km/yr against a 14,470 km average).
KM_NEW_RATIO = {"car": 1.4, "van": 1.5, "truck_reg": 1.8, "truck_lh": 2.2, "bus": 1.5}
LD, HD = ("car", "phev", "van"), ("truck_reg", "truck_lh", "bus")
CATS = ["car", "van", "truck_reg", "truck_lh", "bus"]
AGES = [a + 0.5 for a in range(0, 90)]


def weibull_lambda(mean_life: float) -> float:
    return mean_life / math.gamma(1 + 1 / WEIBULL_K)


def survival(age: float, cat: str, life_shift: float = 0.0) -> float:
    lam = weibull_lambda(MEAN_LIFE[cat] + life_shift)
    return math.exp(-((max(age, 0.0) / lam) ** WEIBULL_K))


def _ratio(theta: float, cat: str) -> float:
    """New-vehicle km relative to the steady-state fleet average for decay constant theta (base life)."""
    num = sum(survival(a, cat) * math.exp(-a / theta) for a in AGES)
    den = sum(survival(a, cat) for a in AGES)
    return den / num


def _theta(cat: str) -> float:
    lo, hi = 0.5, 500.0
    for _ in range(100):
        mid = math.sqrt(lo * hi)
        if _ratio(mid, cat) > KM_NEW_RATIO[cat]:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


KM_DECAY = {c: _theta(c) for c in CATS}


def km_new(cat: str, life_shift: float = 0.0) -> float:
    """Mileage of a new vehicle such that the steady-state fleet average equals the observed average."""
    num = sum(survival(a, cat, life_shift) * math.exp(-a / KM_DECAY[cat]) for a in AGES)
    den = sum(survival(a, cat, life_shift) for a in AGES)
    return BASE["km"][cat] * den / num


def km_age(age: float, cat: str, life_shift: float = 0.0, _cache: dict = {}) -> float:
    key = (cat, life_shift)
    if key not in _cache:
        _cache[key] = km_new(cat, life_shift)
    return _cache[key] * math.exp(-age / KM_DECAY[cat])


def historic_cohorts(life_shift: float = 0.0) -> dict:
    """Gross electric cohorts 2012-2025, backed out of year-end stocks so that the surviving cohorts reproduce
    every observed year-end stock exactly: N_v = (Obs_v - sum_{w<v} N_w s(v-w+0.5)) / s(0.5)."""
    def gross(cls, idx, cat):
        obs = {y: float(STOCK[cls][y][idx]) for y in range(2012, 2026)}
        out: dict = {}
        for v in range(2012, 2026):
            surv = sum(n * survival(v - w + 0.5, cat, life_shift) for w, n in out.items())
            out[v] = max(obs[v] - surv, 0.0) / survival(0.5, cat, life_shift)
        return out
    return {"car": gross(CARS, 1, "car"), "phev": gross(CARS, 2, "car"), "van": gross(VANS, 1, "van"),
            "truck_reg": gross(LORRIES, 1, "truck_reg"), "truck_lh": {y: 0.0 for y in range(2012, 2026)},
            "bus": gross(BUSES, 1, "bus")}


# ---------------------------------------------------------------------------------------------
# 3. Assumed planning states (electric share of fleet entries)
# ---------------------------------------------------------------------------------------------
# Post-2030 logistic toward zmax with midpoint tm and width w (years). Light-duty 2026-2030 entry shares change
# linearly by `delta` per year from the observed 2025 share (low: frozen; base: +5 pp/yr, i.e. 66 % BEV in 2030,
# in line with the 62.1 % BEV share of new cars in September 2026; high: +10 pp/yr). Heavy-duty 2026-2030 follows
# its own logistic from the observed 2025 entry share. The one solved parameter per state is u, light-duty
# electricity per EV in 2030 relative to 2025 (mileage, efficiency and statistical allocation together), which
# makes 2030 equal the retained 2030 state exactly. Values are assumptions anchored to: EU car/van CO2 rules
# (100 % in law; 90 % proposed Dec 2025; 87.5 % effective in the Oct 2026 Parliament deal), EU HDV CO2 rules
# (-45 % 2030, -65 % 2035, -90 % 2040; urban buses 90 % ZE 2030, 100 % 2035), and observed Finnish shares.
STATE_PARAMS = {
    "low": {"car": (0.85, 2033, 3.5), "van": (0.80, 2034, 3.5), "truck_reg": (0.55, 2040, 4.0),
            "truck_lh": (0.35, 2044, 4.0), "bus": (0.65, 2030, 3.0), "phev_2040": 0.08, "delta": 0.00},
    "base": {"car": (0.95, 2030, 3.0), "van": (0.95, 2031, 3.0), "truck_reg": (0.85, 2036, 3.5),
             "truck_lh": (0.70, 2039, 3.5), "bus": (0.80, 2028, 3.0), "phev_2040": 0.02, "delta": 0.05},
    "high": {"car": (1.00, 2028, 2.5), "van": (1.00, 2029, 2.5), "truck_reg": (0.95, 2033, 3.0),
             "truck_lh": (0.90, 2036, 3.0), "bus": (0.95, 2027, 2.5), "phev_2040": 0.00, "delta": 0.10},
}


def sig(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def logistic_from(t: float, t0: float, z0: float, zmax: float, tm: float, w: float) -> float:
    if zmax <= z0:
        return z0
    a0 = sig((t0 - tm) / w)
    return z0 + (zmax - z0) * (sig((t - tm) / w) - a0) / (1 - a0)


# ---------------------------------------------------------------------------------------------
# 4. Simulation
# ---------------------------------------------------------------------------------------------
def default_opts() -> dict:
    return {
        "delay": 0.0,              # genuine delay: holds 2030 shares for d years, then the same curve d years later
        "stall_from": None,        # freeze all entry shares at their value in this year
        "ld_use_2050": 1.0,        # light-duty electricity per EV in 2050 relative to 2030 (linear after 2030)
        "hd_int": 1.0,             # heavy-duty kWh/km multiplier after 2030
        "hd_km": 1.0,              # heavy-duty km multiplier after 2030
        "kappa_to_one": False,     # light-duty calibration factor decays linearly to 1 by 2050
        "life_shift": 0.0,         # +/- years on mean register life (entry rate follows, 1/life)
        "stock_2050": 1.0,         # fleet size in 2050 relative to 2025 (linear after 2030)
        "zmax_override": {},       # {cat: zmax}
        "phev_2040": None,
        "loss": LOSS,
    }


SUBCATS = ["car", "phev", "van", "truck_reg", "truck_lh", "bus"]


def cat_of(c: str) -> str:
    return "car" if c == "phev" else c


def simulate(state: str, u: float, opts: dict | None = None, kappa: float | None = None) -> dict:
    """Cohort stock-flow. Entries A = S / life; EV entries = A * z. Energy from surviving cohorts x km(age)."""
    o = default_opts()
    o.update(opts or {})
    p = STATE_PARAMS[state]
    delta, ls = p["delta"], o["life_shift"]
    cohorts = {c: dict(v) for c, v in historic_cohorts(ls).items()}
    entries_25 = {c: BASE["stock"][cat_of(c)] / (MEAN_LIFE[cat_of(c)]) for c in SUBCATS}
    entries_25["truck_reg"] = ENTRIES_2025["truck"] * TRUCK_REGIONAL_SHARE
    entries_25["truck_lh"] = ENTRIES_2025["truck"] * (1 - TRUCK_REGIONAL_SHARE)
    z_obs = {c: cohorts[c][2025] / entries_25[c] for c in SUBCATS}   # observed 2025 electric entry shares

    def stock_end(c: str, y: int) -> float:
        return sum(n * survival(y - cy + 0.5, cat_of(c), ls) for cy, n in cohorts[c].items() if cy <= y)

    def vkm(c: str, y: int) -> float:
        """Electric vehicle-km in year y (cohorts enter mid-year: half-year exposure in the entry year)."""
        tot = 0.0
        for cy, n in cohorts[c].items():
            if cy > y:
                continue
            a, w = (0.25, 0.5) if cy == y else (y - cy, 1.0)
            km = km_age(a, cat_of(c), ls)
            if c == "phev":
                km = PHEV_EKM * km / BASE["km"]["car"]
            tot += n * w * survival(a, cat_of(c), ls) * km
        return tot

    z_hist: dict = {c: {2025: z_obs[c]} for c in SUBCATS}
    out = {"year": [], "stock": [], "z": [], "energy": []}
    for y in YEARS:
        if y > 2025:
            frac = min(max((y - 2030) / 20.0, 0.0), 1.0)
            stock_mult = 1.0 + (o["stock_2050"] - 1.0) * frac
            for c in SUBCATS:
                cat = cat_of(c)
                S = BASE["stock"][cat] * stock_mult
                if c.startswith("truck"):
                    share = TRUCK_REGIONAL_SHARE if c == "truck_reg" else 1 - TRUCK_REGIONAL_SHARE
                    A = BASE["stock"]["truck_reg"] / TRUCK_REGIONAL_SHARE * stock_mult * share / (MEAN_LIFE[cat] + ls)
                else:
                    A = S / (MEAN_LIFE[cat] + ls)
                if o["stall_from"] is not None and y > o["stall_from"]:
                    z = z_hist[c][o["stall_from"]]
                elif c == "phev":
                    z0 = z_obs["phev"]
                    if y <= 2030 or y - 2030 <= o["delay"]:
                        z = z0
                    else:
                        z_end = p["phev_2040"] if o["phev_2040"] is None else o["phev_2040"]
                        z = max(z0 + (z_end - z0) * min((y - 2030 - o["delay"]) / 10.0, 1.0), 0.0)
                elif c in ("car", "van") and y <= 2030:
                    z = min(max(z_obs[c] + delta * (y - 2025), 0.0), 1.0)
                else:
                    zmax, tm, w = p[c]
                    zmax = o["zmax_override"].get(c, zmax)
                    # a genuine delay d holds the 2030 share for d years and then follows the same curve
                    # d years later; nothing is renormalised to reach the 2050 value
                    if c in ("car", "van"):
                        z = logistic_from(max(y - o["delay"], 2030), 2030, z_hist[c][2030], zmax, tm, w)
                    elif y <= 2030:
                        z = logistic_from(y, 2025, z_obs[c], p[c][0], p[c][1], p[c][2])
                    else:
                        z = max(z_hist[c][2030], logistic_from(y - o["delay"], 2025, z_obs[c], zmax, tm, w))
                if c == "phev":
                    # combined plug-in share of car entries is capped at 100 %: BEV has priority and PHEV
                    # receives at most the remainder (cars are processed before PHEVs in SUBCATS)
                    z = min(z, max(1.0 - z_hist["car"][y], 0.0))
                z_hist[c][y] = min(z, 1.0)
                cohorts[c][y] = A * z_hist[c][y]
        assert z_hist["car"][y] + z_hist["phev"][y] <= 1.0 + 1e-12, f"car entry shares exceed 100% in {y}"
        cur = {c: stock_end(c, y) for c in SUBCATS}
        tol = 1.0001 * max(1.0, o["stock_2050"])
        assert cur["car"] + cur["phev"] <= BASE["stock"]["car"] * tol, "EV cars exceed fleet"
        for c in ("van", "truck_reg", "truck_lh", "bus"):
            assert cur[c] <= BASE["stock"][c] * tol, f"EV stock exceeds fleet: {c}"
        frac = min(max((y - 2030) / 20.0, 0.0), 1.0)
        ld_use = (1.0 + (u - 1.0) * min(max(y - 2025, 0) / 5.0, 1.0)) * (1.0 + (o["ld_use_2050"] - 1.0) * frac)
        post = y > 2030
        hd_int, hd_km = (o["hd_int"], o["hd_km"]) if post else (1.0, 1.0)
        L = o["loss"] if post else LOSS
        e = {c: vkm(c, y) * KWH_KM[c] * (1 + LOSS) * ld_use for c in LD}
        for c in HD:
            e[c] = vkm(c, y) * hd_km * KWH_KM[c] * hd_int * (1 + L)
        out["year"].append(y)
        out["stock"].append(cur)
        out["z"].append({c: z_hist[c][y] for c in SUBCATS})
        out["energy"].append(e)  # kWh, engineering basis (before calibration)
    e25 = out["energy"][0]
    if kappa is None:
        kappa = (OBS_2025_GWH * 1e6 - sum(e25[c] for c in HD)) / sum(e25[c] for c in LD)
    out["kappa"] = kappa
    out["twh"] = []
    for y, e in zip(out["year"], out["energy"]):
        k = kappa
        if o["kappa_to_one"] and y > 2030:
            k = kappa + (1.0 - kappa) * min((y - 2030) / 20.0, 1.0)
        ld = sum(e[c] for c in LD) * k / 1e9
        hd = {c: e[c] / 1e9 for c in HD}
        out["twh"].append({"car": e["car"] * k / 1e9, "phev": e["phev"] * k / 1e9, "van": e["van"] * k / 1e9,
                           **hd, "ld": ld, "hd": sum(hd.values()), "total": ld + sum(hd.values())})
    return out


SERIES_2030, PROV_2030 = read_2030_series()
OBS_2025_GWH = SERIES_2030[2025]
RETAINED_2030_TWH = {s: OBS_2025_GWH * (1 + g) ** 5 / 1000 for s, g in CAGR_2030.items()}


def solve_u(state: str, opts: dict | None = None) -> float:
    """Bisection on light-duty electricity per EV in 2030 (relative to 2025) so 2030 equals the retained state."""
    target = RETAINED_2030_TWH[state]
    lo, hi = 0.3, 3.0
    f = lambda d: simulate(state, d, opts)["twh"][5]["total"] - target
    flo, fhi = f(lo), f(hi)
    assert flo < 0 < fhi, f"cannot bracket 2030 {state}: {flo}, {fhi}"
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------------------------
# 5. Load metrics: average MW, evening peak (unmanaged vs managed), flexible span, depot and corridor
# ---------------------------------------------------------------------------------------------
LOAD = {
    "winter_ld": 1.25,       # winter-day energy relative to annual mean day, light duty and buses (assumption;
                             # Xu et al. 2019: +2.4 kWh/100 km per 5 C below 10 C)
    "winter_hd": 1.15,       # trucks (assumption)
    "eve_share": 0.70, "eve_hours": 3.0,      # concentrated evening charging (retained from the 2030 study)
    "managed_hours": 10.0,                    # broad off-peak managed charging (retained from the 2030 study)
    "depot_unm_share": 0.60, "depot_unm_hours": 4.0,  # depot: charging on return (assumption)
    "depot_hours": 8.0,                       # depot managed window (assumption)
    "corridor_share_lh": 0.50,                # long-haul energy charged en route (assumption; T&E 2025: 45-70 %
                                              # of long-distance trucks depot-chargeable)
    "corridor_hours": 14.0, "corridor_peak_factor": 1.4,  # daytime corridor profile (assumption)
    "mcs_point_mw": 1.2, "afir_pool_mw": 3.6,             # Kotka MCS 1.2 MW; AFIR core TEN-T pool 2030
    "op_days_truck": 250.0, "op_days_bus": 365.0,
}


def load_metrics(tw: dict, L: dict = LOAD) -> dict:
    """Illustrative winter-day charging blocks (MW). The evening block and the night block occur at different
    hours; their difference is reported as such, not as a reduction of the national peak."""
    ld = tw["ld"] * 1e6 / 365 * L["winter_ld"]                     # MWh per winter day
    bus = tw["bus"] * 1e6 / 365 * L["winter_ld"]
    reg = tw["truck_reg"] * 1e6 / L["op_days_truck"] * L["winter_hd"]
    lh = tw["truck_lh"] * 1e6 / L["op_days_truck"] * L["winter_hd"]
    corr = lh * L["corridor_share_lh"]
    depot = bus + reg + lh * (1 - L["corridor_share_lh"])
    ld_eve = ld * L["eve_share"] / L["eve_hours"]
    ld_night = ld / L["managed_hours"]
    dep_ret = depot * L["depot_unm_share"] / L["depot_unm_hours"]
    dep_night = depot / L["depot_hours"]
    cor_avg = corr / L["corridor_hours"]                # daytime corridor charging, also present in the evening
    cor_pk = cor_avg * L["corridor_peak_factor"]       # daytime corridor peak hour
    evening = ld_eve + dep_ret + cor_avg               # evening block: light duty + depots on return + corridor
    night = ld_night + dep_night                       # night block: managed light duty + managed depots
    return {
        "twh": tw["total"], "avg_mw": tw["total"] * 1e6 / HOURS,
        "ld_unmanaged_mw": ld_eve, "ld_managed_mw": ld_night,
        "depot_unmanaged_mw": dep_ret, "depot_managed_mw": dep_night,
        "corridor_avg_mw": cor_avg, "corridor_peak_mw": cor_pk,
        "evening_block_mw": evening, "night_block_mw": night, "block_difference_mw": evening - night,
        # legacy names used in the outputs
        "unmanaged_peak_mw": evening, "managed_peak_mw": night, "flexible_span_mw": evening - night,
        "mcs_points": cor_pk / L["mcs_point_mw"],
    }


# ---------------------------------------------------------------------------------------------
# 6. Reference points (all cited in the paper)
# ---------------------------------------------------------------------------------------------
REF = {
    "fingrid_2025_twh": 84.5,                     # Fingrid Q3/2026 management review (1-12/2025)
    "fingrid_2030": (106.0, 123.0), "fingrid_2035": (110.0, 162.0),   # Fingrid Q3/2026 outlook
    "fingrid_transport": {2025: 2.0, 2030: 5.0, 2035: 8.0},           # "approximately" (Q3/2026 outlook)
    "vision2040_total": (138.0, 267.0), "vision2040_transport": 10.0,  # Fingrid electricity system vision 2040
    "vision2045_total": (131.0, 359.0), "vision2045_transport_p2p": 10.0,  # Fingrid vision 2023 (2045)
    "peak_record_mw": 15553.0,                    # all-time record, January 2026 (Fingrid Q1/2026 review)
    "dc_signed_twh": 28.0, "dc_signed_gw": 5.0,   # data centres with signed agreements (mid-Aug 2026)
    "dc_2035": (11.0, 35.0),
    "rail_2025_gwh": 664.0,                       # Statistics Finland 12sz
    # Ministry of Economic Affairs and Employment, Long-term Climate Plan (TEM 2026:6), 2050 scenarios
    "meae_final_2050": (134.0, 180.0),            # final electricity consumption, ENV/PPL 134-140 .. BIZ 180 TWh
    "meae_transport_2050": (11.0, 15.0),          # electricity in transport, 2050
    "meae_dc_2050": (10.0, 30.0),                 # data centres: 'runsas 10' TWh (three scenarios), 30 TWh (BIZ)
    # Data-centre buildout references (Merilehto 2026, Gasum blog, 5 Oct 2026): about 4.5 GW under construction,
    # announced projects up to over 11 GW nominal. Converted at the utilisation implied by Fingrid's ~28 TWh for
    # nearly 5 GW of signed agreements (28 / (5 x 8.76) = 0.64). Author's base estimate for 2035: over 30 TWh.
    "dc_util": 28.0 / (5.0 * 8.76),
    "dc_under_construction_gw": 4.5, "dc_announced_gw": 11.0, "dc_author_2035_twh": 30.0,
}
REF["dc_under_construction_twh"] = REF["dc_under_construction_gw"] * 8.76 * REF["dc_util"]
REF["dc_announced_twh"] = REF["dc_announced_gw"] * 8.76 * REF["dc_util"]


def main() -> None:
    DATA.mkdir(exist_ok=True)

    # 0 reproduction of the 2030 study
    rep = reproduce_2030_study(SERIES_2030)
    write_csv("reproduction_2030.csv", rep)

    # 1 boundary reconciliation (StatFin road vs Fingrid "transport")
    rows = []
    with open(SOURCES / "statfin_12sz_transport_electricity_1990-2025_accessed_2026-11-08.csv", encoding="utf-8-sig") as f:
        sz = {}
        for r in csv.DictReader(f):
            if r["Energy source"].startswith("9"):
                sz.setdefault(int(r["Year"].rstrip("*")), {})[r["Transportation sector"][:1]] = r["Quantity (GWh)"]
    for y in range(2018, 2026):
        road, rail, tot = (float(sz[y][k]) if sz[y][k] not in (".", "") else 0.0 for k in ("A", "D", "S"))
        rows.append({"year": y, "road_gwh": road, "rail_gwh": rail, "transport_total_gwh": tot,
                     "other_gwh": tot - road - rail})
    write_csv("boundary_statfin.csv", rows)
    assert rows[-1]["road_gwh"] == OBS_2025_GWH

    # 2 solve 2030 retention per state and run paired states
    deltas = {s: solve_u(s) for s in STATES}
    runs = {s: simulate(s, deltas[s]) for s in STATES}
    kappa = runs["base"]["kappa"]
    for s in STATES:
        tw = runs[s]["twh"]
        assert abs(tw[0]["total"] * 1000 - OBS_2025_GWH) < 1e-6, "2025 calibration failed"
        assert abs(tw[5]["total"] - RETAINED_2030_TWH[s]) < 5e-7, f"2030 {s} not retained exactly"
        assert abs(runs[s]["kappa"] - kappa) < 1e-12
        assert round(tw[5]["total"] * 1000) == PUBLISHED_2030_GWH[s]

    # 2b cohort initialisation reproduces every observed year-end electric stock 2012-2025
    hc = historic_cohorts()
    obs_idx = {"car": (CARS, 1, "car"), "phev": (CARS, 2, "car"), "van": (VANS, 1, "van"),
               "truck_reg": (LORRIES, 1, "truck_reg"), "bus": (BUSES, 1, "bus")}
    sc = []
    for c, (cls, idx, cat) in obs_idx.items():
        for y in range(2012, 2026):
            mod = sum(n * survival(y - w + 0.5, cat) for w, n in hc[c].items() if w <= y)
            ob = STOCK[cls][y][idx]
            # exact unless the observed stock fell below the survivors of earlier cohorts (register corrections;
            # gross entries cannot be negative). 2025 must be exact.
            clipped = hc[c][y] == 0.0 and ob < mod
            assert abs(mod - ob) < 1e-6 or (clipped and y != 2025), f"cohort initialisation misses {c} {y}: {mod} vs {ob}"
            if y in (2015, 2020, 2025):
                sc.append({"segment": c, "year": y, "observed": ob, "modelled": mod,
                           "gross_entries_2012_to_year": sum(n for w, n in hc[c].items() if w <= y)})
    for s_ in STATES:
        st25 = runs[s_]["stock"][0]
        assert abs(st25["car"] - STOCK[CARS][2025][1]) < 1e-6 and abs(st25["bus"] - STOCK[BUSES][2025][1]) < 1e-6
    write_csv("stock_check.csv", sc)

    paths, results = [], []
    for s in STATES:
        r = runs[s]
        for i, y in enumerate(r["year"]):
            tw, st, z = r["twh"][i], r["stock"][i], r["z"][i]
            lm = load_metrics(tw)
            row = {"state": s, "year": y, **{f"twh_{k}": tw[k] for k in tw},
                   **{f"ev_{k}": st[k] for k in st}, **{f"z_{k}": z[k] for k in z}, **lm}
            paths.append(row)
            if y in CHECK:
                results.append(row)
    write_csv("paths.csv", paths)
    write_csv("results.csv", results)
    write_csv("calibration.csv", [{"kappa_ld": kappa, **{f"u_{s}": deltas[s] for s in STATES}, **{f"delta_{s}": STATE_PARAMS[s]["delta"] for s in STATES},
                                   **{f"z2025_{c}": runs['base']['z'][0][c] for c in runs['base']['z'][0]},
                                   **{f"km_{c}": BASE['km'][c] for c in BASE['km']},
                                   **{f"stock_{c}": BASE['stock'][c] for c in BASE['stock']},
                                   **{f"tau_{c}": BASE['tau'][c] for c in BASE['tau']},
                                   "source_2030_series": PROV_2030}])

    def end(run, y=2050):
        return run["twh"][YEARS.index(y)]

    # 3 materiality
    mat = []
    for s in STATES:
        for y in (2030, 2035, 2040, 2045, 2050):
            tw = end(runs[s], y)
            lm = load_metrics(tw)
            row = {"state": s, "year": y, "twh": tw["total"],
                   "share_2025_consumption_pct": 100 * tw["total"] / REF["fingrid_2025_twh"],
                   "unmanaged_peak_share_of_record_pct": 100 * lm["unmanaged_peak_mw"] / REF["peak_record_mw"],
                   "managed_peak_share_of_record_pct": 100 * lm["managed_peak_mw"] / REF["peak_record_mw"],
                   "vs_dc_signed_pct": 100 * tw["total"] / REF["dc_signed_twh"]}
            def rng(lo_hi):
                return f"{100*tw['total']/lo_hi[1]:.1f}-{100*tw['total']/lo_hi[0]:.1f}"
            ref = {2030: ("Fingrid Q3/2026 outlook", REF["fingrid_2030"]),
                   2035: ("Fingrid Q3/2026 outlook", REF["fingrid_2035"]),
                   2040: ("Fingrid system vision 2040", REF["vision2040_total"]),
                   2045: ("Fingrid system vision 2023 (2045)", REF["vision2045_total"]),
                   2050: ("MEAE Long-term Climate Plan, final electricity 2050", REF["meae_final_2050"])}[y]
            row["national_reference"], row["share_national_range_pct"] = ref[0], rng(ref[1])
            if y == 2050:
                row["share_fingrid2045_range_pct"] = rng(REF["vision2045_total"])
                row["vs_meae_dc_2050_pct"] = rng(REF["meae_dc_2050"])
                row["vs_meae_transport_2050_pct"] = rng(REF["meae_transport_2050"])
            if y == 2035:
                row["vs_fingrid_dc_2035_pct"] = rng(REF["dc_2035"])
            row["vs_dc_buildout_pct"] = rng((REF["dc_under_construction_twh"], REF["dc_announced_twh"]))
            row["vs_dc_author_2035_pct"] = 100 * tw["total"] / REF["dc_author_2035_twh"]
            mat.append(row)
    write_csv("materiality.csv", mat)

    # 4 tornado (base state, 2050): one-way, post-2030 variants keep the retained 2030 exactly
    b50 = end(runs["base"])
    b50_lm = load_metrics(b50)
    variants = [
        ("Light-duty electricity per EV by 2050", {"ld_use_2050": 0.85}, {"ld_use_2050": 1.10}, "-15% / +10%"),
        ("Calibration factor kappa", {"kappa_to_one": True}, None, f"decays {kappa:.2f} to 1.00 / held"),
        ("Car electric-entry ceiling", {"zmax_override": {"car": 0.85}}, {"zmax_override": {"car": 1.0}}, "0.85 / 1.00"),
        ("Long-haul truck ceiling", {"zmax_override": {"truck_lh": 0.40}}, {"zmax_override": {"truck_lh": 0.90}}, "0.40 / 0.90"),
        ("Regional truck ceiling", {"zmax_override": {"truck_reg": 0.60}}, {"zmax_override": {"truck_reg": 0.95}}, "0.60 / 0.95"),
        ("Heavy-duty km or kWh/km", {"hd_int": 0.85}, {"hd_int": 1.15}, "-15% / +15%"),
        ("Fleet size in 2050", {"stock_2050": 0.95}, {"stock_2050": 1.05}, "-5% / +5%"),
        ("Mean register life (and entry rate)", {"life_shift": 3.0}, {"life_shift": -3.0}, "+3 yr / -3 yr"),
        ("PHEV entry share 2040", {"phev_2040": 0.0}, {"phev_2040": 0.10}, "0.00 / 0.10"),
        ("Charging losses (heavy duty)", {"loss": 0.06}, {"loss": 0.15}, "6% / 15%"),
    ]
    tor = []
    def run_anchored(state, o_):
        """Re-solve u for the variant so that 2025 and the retained 2030 state stay exact."""
        r = simulate(state, solve_u(state, o_), o_)
        assert abs(r["twh"][0]["total"] * 1000 - OBS_2025_GWH) < 1e-6
        assert abs(r["twh"][5]["total"] - RETAINED_2030_TWH[state]) < 1e-6, f"variant moved 2030: {o_}"
        return r

    for name, lo_o, hi_o, lab in variants:
        lo = end(run_anchored("base", lo_o))
        hi = end(run_anchored("base", hi_o)) if hi_o else b50
        tor.append({"parameter": name, "range": lab, "low_twh": lo["total"], "high_twh": hi["total"],
                    "base_twh": b50["total"], "low_peak_mw": load_metrics(lo)["unmanaged_peak_mw"],
                    "high_peak_mw": load_metrics(hi)["unmanaged_peak_mw"], "base_peak_mw": b50_lm["unmanaged_peak_mw"]})
    # load-shape parameters (energy unchanged)
    for name, key, lo_v, hi_v, lab in [("Winter-day factor (light duty)", "winter_ld", 1.10, 1.40, "1.10 / 1.40"),
                                       ("Evening share in 3 h", "eve_share", 0.50, 0.85, "50% / 85%")]:
        Llo, Lhi = dict(LOAD), dict(LOAD)
        Llo[key], Lhi[key] = lo_v, hi_v
        tor.append({"parameter": name, "range": lab, "low_twh": b50["total"], "high_twh": b50["total"],
                    "base_twh": b50["total"], "low_peak_mw": load_metrics(b50, Llo)["unmanaged_peak_mw"],
                    "high_peak_mw": load_metrics(b50, Lhi)["unmanaged_peak_mw"], "base_peak_mw": b50_lm["unmanaged_peak_mw"]})
    tor.sort(key=lambda r: -abs(r["high_twh"] - r["low_twh"]) - 1e-6 * abs(r["high_peak_mw"] - r["low_peak_mw"]))
    write_csv("tornado.csv", tor)
    ces = []
    for lab, r in [("low", runs["low"]), ("base", runs["base"]), ("high", runs["high"]),
                   ("base, car ceiling 1.00", run_anchored("base", {"zmax_override": {"car": 1.0}}))]:
        for i, y in enumerate(r["year"]):
            zb, zp = r["z"][i]["car"], r["z"][i]["phev"]
            ces.append({"case": lab, "year": y, "bev_share": zb, "phev_share": zp, "plugin_share": zb + zp,
                        "other_share": 1.0 - zb - zp})
    write_csv("car_entry_shares.csv", ces)

    # 5 genuine adoption delay (shifted, not renormalised) and stalled adoption
    # observed-momentum variant: entry shares frozen at 2025 values from 2026 (2030 not retained)
    mom = simulate("base", 1.0, {"stall_from": 2025})
    dl, stl = [], []
    for s in STATES:
        ref = runs[s]
        for d in (0, 5, 10):
            r = run_anchored(s, {"delay": float(d)})
            assert abs(r["twh"][5]["total"] - RETAINED_2030_TWH[s]) < 1e-6
            dl.append({"state": s, "delay_years": d, **{f"twh_{y}": end(r, y)["total"] for y in (2035, 2040, 2045, 2050)},
                       "change_2050_pct": 100 * (end(r)["total"] / end(ref)["total"] - 1)})
        for frm in (2030, 2035):
            r = run_anchored(s, {"stall_from": frm})
            stl.append({"state": s, "frozen_from": frm, **{f"twh_{y}": end(r, y)["total"] for y in (2035, 2040, 2045, 2050)},
                        "change_2050_pct": 100 * (end(r)["total"] / end(ref)["total"] - 1),
                        "bev_cars_2050": r["stock"][-1]["car"]})
    stl.append({"state": "observed 2025 shares frozen", "frozen_from": 2025,
                **{f"twh_{y}": end(mom, y)["total"] for y in (2035, 2040, 2045, 2050)},
                "change_2050_pct": 100 * (end(mom)["total"] / end(runs['base'])["total"] - 1),
                "bev_cars_2050": mom["stock"][-1]["car"], "twh_2030": mom["twh"][5]["total"]})
    write_csv("delay.csv", dl)
    rp = []
    for lab, r in [("Base", runs["base"]), ("Delay 5 yr", run_anchored("base", {"delay": 5.0})),
                   ("Delay 10 yr", run_anchored("base", {"delay": 10.0})),
                   ("Stalled from 2030", run_anchored("base", {"stall_from": 2030})),
                   ("Stalled from 2035", run_anchored("base", {"stall_from": 2035})),
                   ("2025 entry shares frozen", mom)]:
        for i, y in enumerate(r["year"]):
            rp.append({"variant": lab, "year": y, "twh": r["twh"][i]["total"]})
    write_csv("robustness_paths.csv", rp)
    write_csv("stalled.csv", stl)

    # 6 charging-behaviour stress (2050, all states)
    cases = [("Smart (managed, 10 h)", None),
             ("Moderate evening (50% in 4 h)", {"eve_share": 0.50, "eve_hours": 4.0}),
             ("Concentrated evening (70% in 3 h)", {"eve_share": 0.70, "eve_hours": 3.0}),
             ("Extreme evening (85% in 2 h)", {"eve_share": 0.85, "eve_hours": 2.0}),
             ("Concentrated evening + cold snap (winter factor 1.4)", {"eve_share": 0.70, "eve_hours": 3.0, "winter_ld": 1.4})]
    cs = []
    for s in STATES:
        for y in (2030, 2035, 2050):
            tw = end(runs[s], y)
            for name, mod in cases:
                L2 = dict(LOAD)
                L2.update(mod or {})
                lm = load_metrics(tw, L2)
                pk = lm["managed_peak_mw"] if mod is None else lm["unmanaged_peak_mw"]
                cs.append({"state": s, "year": y, "case": name, "evening_peak_mw": pk,
                           "share_of_record_pct": 100 * pk / REF["peak_record_mw"]})
    write_csv("charging_stress.csv", cs)

    # 7 rebound/recovery after a curtailment of managed light-duty charging (2050), explicit assumptions:
    #   the managed night load P_m is withheld for H hours; a fraction rho of the withheld energy must be
    #   recovered; recovery is limited by the headroom between plugged-in charging power and P_m. The managed
    #   night window is 10 h, so curtailment plus recovery should fit within it.
    rb = []
    for s in ("low", "base", "high"):
        tw = end(runs[s])
        lm = load_metrics(tw)
        bev = runs[s]["stock"][-1]["car"] + runs[s]["stock"][-1]["van"] + 0.5 * runs[s]["stock"][-1]["phev"]
        pm = lm["ld_managed_mw"]
        for plugged, kw in ((0.3, 7.4), (0.5, 11.0)):
            avail = bev * plugged * kw / 1000.0
            headroom = max(avail - pm, 0.0)
            for hours in (2.0, 4.0):
                for rho in (0.5, 1.0):
                    rec = pm * hours * rho
                    t_min = rec / headroom if headroom > 0 else float("inf")
                    in4 = min(rec, headroom * 4.0)
                    rb.append({"state": s, "plugged_share": plugged, "charger_kw": kw, "curtail_hours": hours,
                               "recovered_fraction": rho, "managed_ld_mw": pm, "available_power_mw": avail,
                               "headroom_mw": headroom, "to_recover_mwh": rec,
                               "min_recovery_hours": t_min,
                               "recovered_within_4h_mwh": in4, "unrecovered_after_4h_mwh": rec - in4,
                               "fits_10h_window": hours + t_min <= LOAD["managed_hours"] + 1e-9,
                               "peak_4h_recovery_mw": pm + in4 / 4.0,
                               "peak_synchronised_mw": min(avail, pm + rec),
                               "unmanaged_ld_mw": lm["ld_unmanaged_mw"]})
    write_csv("rebound.csv", rb)

    # 8 top-down checks
    vkm = {c: VKM[k][2025] * 1e6 for c, k in (("car", CARS), ("van", VANS), ("truck", LORRIES), ("bus", BUSES))}
    reg_vkm = BASE["stock"]["truck_reg"] * BASE["km"]["truck_reg"]
    lh_vkm = vkm["truck"] - reg_vkm
    ceil_eng = (vkm["car"] * KWH_KM["car"] + vkm["van"] * KWH_KM["van"] + reg_vkm * KWH_KM["truck_reg"]
                + lh_vkm * KWH_KM["truck_lh"] + vkm["bus"] * KWH_KM["bus"]) * (1 + LOSS) / 1e9
    ceil_cal = ((vkm["car"] * KWH_KM["car"] + vkm["van"] * KWH_KM["van"]) * (1 + LOSS) * kappa
                + (reg_vkm * KWH_KM["truck_reg"] + lh_vkm * KWH_KM["truck_lh"] + vkm["bus"] * KWH_KM["bus"]) * (1 + LOSS)) / 1e9
    statnett_cars_per_vkm = 6.5e9 / (2.7e6 * 12_000)  # kWh per vehicle-km implied by Statnett (2019)
    td = [
        {"check": "Full electrification of 2025 road vehicle-km, engineering intensities (TWh)", "value": ceil_eng},
        {"check": "Full electrification of 2025 road vehicle-km, light duty calibrated (TWh)", "value": ceil_cal},
        {"check": "Statnett (2019) Norway car intensity applied to Finnish car vehicle-km (TWh)",
         "value": vkm["car"] * statnett_cars_per_vkm / 1e9},
        {"check": "Statnett (2019) Norway full road electrification incl. vans/trucks/buses (TWh)", "value": 11.5},
        {"check": "Fingrid Q3/2026 transport 2035 minus 2025 rail (TWh)", "value": REF["fingrid_transport"][2035] - REF["rail_2025_gwh"] / 1000},
        {"check": "Fingrid vision 2040 transport minus 2025 rail (TWh)", "value": REF["vision2040_transport"] - REF["rail_2025_gwh"] / 1000},
        {"check": "Fingrid vision 2023, Power to Products 2045 transport (TWh)", "value": REF["vision2045_transport_p2p"]},
    ]
    for s in STATES:
        td.append({"check": f"Model 2050 {s} (TWh)", "value": end(runs[s])["total"]})
        td.append({"check": f"Model 2050 {s} as share of calibrated ceiling (%)", "value": 100 * end(runs[s])["total"] / ceil_cal})
    write_csv("topdown.csv", td)

    # 9 heavy-vehicle connection loads (depot and corridor) by checkpoint
    hv = []
    for s in STATES:
        for y in CHECK:
            tw = end(runs[s], y)
            lm = load_metrics(tw)
            st = runs[s]["stock"][YEARS.index(y)]
            hv.append({"state": s, "year": y, "e_buses": st["bus"], "e_trucks_regional": st["truck_reg"],
                       "e_trucks_longhaul": st["truck_lh"], "depot_managed_mw": lm["depot_managed_mw"],
                       "depot_unmanaged_mw": lm["depot_unmanaged_mw"], "corridor_peak_mw": lm["corridor_peak_mw"],
                       "mcs_full_power_equiv": lm["mcs_points"]})
    write_csv("heavy_connections.csv", hv)
    # representative sites (per-site, independent of the national path)
    kwh_bus_day = BASE["km"]["bus"] / LOAD["op_days_bus"] * KWH_KM["bus"] * (1 + LOSS) * LOAD["winter_ld"]
    kwh_lh_day = BASE["km"]["truck_lh"] / LOAD["op_days_truck"] * KWH_KM["truck_lh"] * (1 + LOSS) * LOAD["winter_hd"]
    sites = [
        {"site": "Bus depot, 100 e-buses, 150 kW chargers, all start on return (simultaneity 0.9)", "mw": 100 * 0.150 * 0.9},
        {"site": "Bus depot, 100 e-buses, energy spread over 8 h", "mw": 100 * kwh_bus_day / 8 / 1000},
        {"site": "Truck depot, 40 trucks x 50 kW (T&E 2025 example)", "mw": 40 * 0.050},
        {"site": "Truck depot, 40 trucks x 150 kW (T&E 2025 example)", "mw": 40 * 0.150},
        {"site": "Kotka MCS hub as installed (3 x 600 kW units)", "mw": 1.8},
        {"site": "AFIR core TEN-T pool, 2030 minimum", "mw": 3.6},
        {"site": "Corridor hub, 4 MCS (1.2 MW) + 4 CCS (0.4 MW), simultaneity 0.8", "mw": (4 * 1.2 + 4 * 0.4) * 0.8},
    ]
    sites.append({"site": "Memo: bus energy per winter day (kWh)", "mw": kwh_bus_day})
    sites.append({"site": "Memo: long-haul truck energy per operating winter day (kWh)", "mw": kwh_lh_day})
    write_csv("sites.csv", sites)

    # 10 console summary
    print(f"2030 series: {PROV_2030}")
    print(f"reproduced {len(rep)} published numbers of the 2030 study; kappa_LD = {kappa:.3f}")
    print("u (LD electricity per EV 2030 vs 2025):", {s: round(d, 3) for s, d in deltas.items()})
    for s in STATES:
        print(s, " ".join(f"{y}:{end(runs[s], y)['total']:.2f}" for y in CHECK))


def write_csv(name: str, rows: list[dict]) -> None:
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(DATA / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == "__main__":
    main()
