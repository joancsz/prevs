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
_RULE_INPUTS = {73, 76, 117, 118, 119, 125, 129, 130, 161, 201, 202, 203, *_TIETE.values()}


@cache
def ena_plants() -> pd.DataFrame:
    return pd.read_csv(files("prevs") / "data" / "ena_plants.csv")


@cache
def mlt_subsystem() -> pd.DataFrame:
    df = pd.read_csv(files("prevs") / "data" / "mlt_subsystem.csv", index_col="subsystem")
    df.columns = df.columns.astype(int)
    return df


def artificial_flows(prevs: pd.DataFrame) -> dict[int, np.ndarray]:
    """Natural flows plus the artificial postos the ENA uses (REV-3 (2) / REV-4 (2) formulas)."""
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
    return q


def subsystem_ena(prevs: pd.DataFrame, subsystems) -> pd.DataFrame:
    """ENA (MWmed) per subsystem x week: sum of productivity * flow over its plants."""
    if missing := sorted(_RULE_INPUTS - set(prevs.index)):
        raise KeyError(f"artificial postos need postos missing from the prevs: {missing}")
    q = artificial_flows(prevs)
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
    mlt = mlt_subsystem()
    cols = {}
    for i, week in enumerate(ena.columns):
        d0 = start + dt.timedelta(days=7 * i)
        d1 = d0 + dt.timedelta(days=6)
        m = mlt.loc[ena.index]
        ref = m[d1.month] if d0.month == d1.month else (m[d1.month] * d1.day + m[d0.month] * (7 - d1.day)) / 7
        cols[week] = ena[week] / ref
    return pd.DataFrame(cols)
