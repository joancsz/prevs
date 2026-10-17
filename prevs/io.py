"""Read and write ONS prevs files (weekly inflow forecasts per posto).

Layout per line: I6 sequential index, I5 posto, 6 x I10 weekly mean flows (m3/s), CRLF.
"""
import datetime as dt
import re
from pathlib import Path

import numpy as np
import pandas as pd

WEEKS = range(1, 7)
_NAME = re.compile(r"(\d{4})(\d{2})-prevs.*\.rv(\d+)", re.IGNORECASE)


def pmo_start(year: int, month: int) -> dt.date:
    """Saturday that starts week 1 of the PMO: the Saturday on or before day 1 of the month."""
    first = dt.date(year, month, 1)
    return first - dt.timedelta(days=(first.weekday() - 5) % 7)


def parse_name(path) -> tuple[dt.date, int]:
    """(PMO start, revision) from a name like 202611-prevs.rv0 or 202611-prevs-SE080_S080.rv1."""
    m = _NAME.fullmatch(Path(path).name)
    if not m:
        raise ValueError(f"{Path(path).name!r} is not named YYYYmm-prevs[...].rv<N>; pass the start date yourself")
    return pmo_start(int(m[1]), int(m[2])), int(m[3])


def read_prevs(path) -> pd.DataFrame:
    """Return a DataFrame indexed by posto (file order kept) with int columns 1..6."""
    rows = [line.split() for line in Path(path).read_text().splitlines() if line.strip()]
    if any(len(r) != 8 for r in rows):
        raise ValueError(f"{path}: every line must have index, posto and 6 weekly values")
    df = pd.DataFrame([[int(v) for v in r[1:]] for r in rows], columns=["posto", *WEEKS]).set_index("posto")
    if df.index.has_duplicates:
        raise ValueError(f"{path}: duplicated postos {sorted(df.index[df.index.duplicated()])}")
    return df


def excel_round(x):
    """Round half away from zero like Excel (numpy/Python round half to even)."""
    return np.copysign(np.floor(np.abs(x) + 0.5), x)


def write_prevs(df: pd.DataFrame, path) -> None:
    """Write df (index posto, 6 weekly columns) as a prevs file; values are rounded to integers."""
    lines = [
        f"{i:6d}{posto:5d}" + "".join(f"{int(v):10d}" for v in excel_round(row))
        for i, (posto, row) in enumerate(zip(df.index, df.to_numpy()), start=1)
    ]
    Path(path).write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))
