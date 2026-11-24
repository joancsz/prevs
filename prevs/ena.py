"""Natural inflow energy (ENA) per subsystem from a prevs, ported from the REV-3..6 sheets
of Matriz_e_Sensibilidade."""
import datetime as dt
from functools import cache
from importlib.resources import files

import numpy as np
import pandas as pd

from prevs.io import excel_round

# Tietê/Pinheiros pumping postos: artificial = natural - 0.1*(161 - 117 - 118) - 117 - 118
_TIETE = {37: 237, 38: 238, 39: 239, 40: 240, 42: 242, 43: 243, 45: 245, 46: 246, 66: 266}
# natural postos read by artificial_flows
_RULE_INPUTS = {73, 76, 288, 117, 118, 119, 125, 129, 130, 161, 201, 202, 203, *_TIETE.values()}


@cache
def ena_plants() -> pd.DataFrame:
    return pd.read_csv(files("prevs") / "data" / "ena_plants.csv")


@cache
def mlt_subsystem() -> pd.DataFrame:
    df = pd.read_csv(files("prevs") / "data" / "mlt_subsystem.csv", index_col="subsystem")
    df.columns = df.columns.astype(int)
    return df


@cache
def belo_monte() -> pd.DataFrame:
    """Monthly hydrograph of the reduced stretch (Volta Grande do Xingu) and Belo Monte max turbine flow."""
    return pd.read_csv(files("prevs") / "data" / "belo_monte.csv", index_col="month")


def by_week(start: dt.date, n: int, f):
    """f(month, week) per week; a week crossing months mixes both months by days (Excel's rule)."""
    out = []
    for i in range(n):
        d0 = start + dt.timedelta(days=7 * i)
        d1 = d0 + dt.timedelta(days=6)
        same = d0.month == d1.month
        out.append(f(d1.month, i) if same else (f(d1.month, i) * d1.day + f(d0.month, i) * (7 - d1.day)) / 7)
    return out


def artificial_flows(prevs: pd.DataFrame, start: dt.date) -> dict[int, np.ndarray]:
    """Natural flows plus the artificial postos the ENA uses (REV-3 (2) / REV-4 (2) / Belo Monte formulas)."""
    q = {p: row.astype(float) for p, row in zip(prevs.index, prevs.to_numpy())}
    r = {p: excel_round(q[p]) for p in (117, 118, 119, 161)}
    q[116] = r[119] - r[118]
    q[104] = r[118] + r[117]
    q[109] = q[118]
    q[318] = r[117] + r[119] + 0.1 * (r[161] - r[117] - r[118])
    pump = 0.1 * (q[161] - q[117] - q[118]) + q[117] + q[118]
    for art, nat in _TIETE.items():
        q[art] = q[nat] - pump
    # Paraíba do Sul / Light complex
    x = q[125]
    q[298] = np.select([x <= 190, x <= 209, x <= 250], [x * 119 / 190, 119, x - 90], 160)
    q[317] = np.maximum(0, q[201] - 25)
    q[132] = q[202] + np.minimum(q[201], 25)
    q[315] = q[203] - q[201] + q[317] + q[298]
    q[316] = np.minimum(q[315], 190)
    q[304] = q[315] - q[316]
    q[131] = np.minimum(q[316], 144)
    q[303] = np.minimum(q[132], 17) + np.minimum(q[316] - q[131], 34)
    q[306] = q[303] + q[131]
    q[127] = q[129] - q[298] - q[203] + q[304]
    q[126] = np.where(q[127] <= 430, np.maximum(q[127] - 90, 0), 340)
    q[299] = q[130] - q[298] - q[203] + q[304]
    q[75] = q[76] + np.minimum(173.5, q[73] - 10)
    # Belo Monte: 288 minus the hydrograph left in the reduced stretch, up to the max turbine flow
    bm = belo_monte()
    q[292] = np.array(by_week(start, len(q[288]), lambda m, i: np.clip(
        q[288][i] - bm.hydrograph[m], 0, bm.max_turbine[m])))
    q[302] = q[288] - q[292]
    return q


def subsystem_ena(prevs: pd.DataFrame, subsystems, start: dt.date) -> pd.DataFrame:
    """ENA (MWmed) per subsystem x week: sum of productivity * flow over its plants."""
    if missing := sorted(_RULE_INPUTS - set(prevs.index)):
        raise KeyError(f"artificial postos need postos missing from the prevs: {missing}")
    q = artificial_flows(prevs, start)
    plants = ena_plants()
    out = {}
    for sub in subsystems:
        sel = plants[plants.subsystem == sub]
        if missing := sorted(set(sel.posto) - set(q)):
            raise KeyError(f"{sub} ENA needs postos missing from the prevs: {missing}")
        out[sub] = sum(prod * q[p] for p, prod in zip(sel.posto, sel.productivity))
    return pd.DataFrame(out, index=prevs.columns).T


def pct_mlt(ena: pd.DataFrame, start: dt.date) -> pd.DataFrame:
    """ENA as a fraction of the subsystem MLT; a week crossing months uses a day-weighted MLT."""
    m = mlt_subsystem().loc[ena.index]
    refs = by_week(start, len(ena.columns), lambda month, _: m[month])
    return pd.DataFrame({week: ena[week] / ref for week, ref in zip(ena.columns, refs)})
