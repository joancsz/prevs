"""%MLT sensitivities: scale every posto of a subsystem so its PMO-month ENA hits a target,
ported from the Sensibilidade sheet / Matriz_ENAs macro of Matriz_e_Sensibilidade."""
import datetime as dt
from functools import cache
from importlib.resources import files

import numpy as np
import pandas as pd

from prevs.ena import pct_mlt, subsystem_ena

SUBSYSTEMS = ("SE", "S", "NE", "N")


@cache
def postos() -> pd.DataFrame:
    """Posto -> subsystem/REE; its order is the output row order of a sensitivity prevs."""
    return pd.read_csv(files("prevs") / "data" / "postos.csv", index_col="posto")


def pmo_month(start: dt.date) -> int:
    return (start + dt.timedelta(days=6)).month


def month_weights(start: dt.date) -> np.ndarray:
    """Days of each of the 6 weeks inside the PMO month (Sensibilidade row 28)."""
    month = pmo_month(start)
    return np.array([sum((start + dt.timedelta(days=7 * i + d)).month == month for d in range(7)) for i in range(6)])


def _first_altered(start: dt.date, alter_from: dt.date | None) -> int:
    """Index of the first scaled week; alter_from must be a week start (Excel HLOOKUP exact match)."""
    if alter_from is None:
        return 0
    k, rest = divmod((alter_from - start).days, 7)
    if rest or not 0 <= k < 6:
        raise ValueError(f"alter_from {alter_from} is not the start of one of the 6 weeks from {start}")
    return k


def factors(prevs: pd.DataFrame, start: dt.date, targets: dict[str, int], alter_from=None) -> dict[str, float]:
    """Multiplier per subsystem for targets in %MLT (e.g. {"SE": 80, "S": 80}).

    Replicates Excel L32..L36: f = T/(100*M) * A/M, M = month mean %MLT, A = mean over altered weeks.
    """
    if unknown := set(targets) - set(SUBSYSTEMS):
        raise ValueError(f"unknown subsystems {sorted(unknown)}")
    if fractional := [t for t in targets.values() if t != int(t)]:
        raise ValueError(f"targets must be whole %MLT (file names would collide): {fractional}")
    w = month_weights(start)
    k = _first_altered(start, alter_from)
    if not w[k:].sum():
        raise ValueError(f"altered weeks from {alter_from} have no days in the PMO month")
    pct = pct_mlt(subsystem_ena(prevs, list(targets), start), start).to_numpy()
    m = pct @ w / w.sum()
    a = pct[:, k:] @ w[k:] / w[k:].sum()
    return {sub: t / (100 * mi) * ai / mi for (sub, t), mi, ai in zip(targets.items(), m, a)}


def _apply(prevs: pd.DataFrame, factors: dict[str, float], k: int) -> pd.DataFrame:
    """Scaled prevs (float, unrounded) in the postos.csv row order; weeks before k untouched."""
    table = postos()
    if missing := set(table.index) ^ set(prevs.index):
        raise ValueError(f"postos in only one of prevs / postos.csv: {sorted(missing)}")
    out = prevs.loc[table.index].astype(float)
    f = table.subsystem.map(factors).fillna(1.0).to_numpy()
    out.iloc[:, k:] = out.iloc[:, k:].to_numpy() * f[:, None]
    return out


def build(prevs: pd.DataFrame, start: dt.date, targets: dict[str, int], alter_from=None):
    """Sensitivity prevs for targets in %MLT. Returns (scaled DataFrame, factors per subsystem)."""
    f = factors(prevs, start, targets, alter_from)
    return _apply(prevs, f, _first_altered(start, alter_from)), f


def scenario_name(start: dt.date, targets: dict[str, int], rev: int = 0) -> str:
    """e.g. 202611-prevs-SE080_S080.rv0"""
    tag = "_".join(f"{s}{int(targets[s]):03d}" for s in SUBSYSTEMS if s in targets)
    end = start + dt.timedelta(days=6)
    return f"{end.year}{pmo_month(start):02d}-prevs-{tag}.rv{rev}"
