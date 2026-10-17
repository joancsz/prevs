"""Read and write ONS prevs files (weekly inflow forecasts per posto).

Layout per line: I6 sequential index, I5 posto, 6 x I10 weekly mean flows (m3/s), CRLF.
"""
from pathlib import Path

import numpy as np
import pandas as pd

WEEKS = range(1, 7)


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
