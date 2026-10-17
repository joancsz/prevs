"""Regenerate prevs/data/*.csv from Matriz_e_Sensibilidade (.xlsm).

Usage: python tools/extract_xlsm.py ref/Matriz_e_Sensibilidade_13.xlsm
Needs openpyxl (dev only). Run again whenever ONS updates productivities or MLTs.
"""
import csv
import re
import sys
from pathlib import Path

import openpyxl

DATA = Path(__file__).resolve().parents[1] / "prevs" / "data"
SUBSYSTEM_NAMES = {"SUDESTE": "SE", "SUL": "S", "NORDESTE": "NE", "NORTE": "N"}
# (sheet, total row) of each subsystem ENA total
TOTALS = {"SE": ("REV-5 (2)", 174), "S": ("REV-6 (2)", 64), "NE": ("REV-6 (2)", 100), "N": ("REV-6 (2)", 140)}


def rows_in(formula):
    """Row numbers referenced in column D by a SUM/plus formula, ranges expanded."""
    rows = []
    for a, b in re.findall(r"D\$?(\d+)(?::D\$?(\d+))?", formula):
        rows += range(int(a), int(b or a) + 1)
    return rows


def plant_rows(ws, row):
    f = ws.cell(row, 4).value
    if not isinstance(f, str) or not f.startswith("="):
        return []
    if "Geral" in f or "Resumo" in f:  # plant ENA row (Resumo = Belo Monte artificial)
        return [row]
    return [r for ref in rows_in(f) for r in plant_rows(ws, ref)]


def main(xlsm):
    wb = openpyxl.load_workbook(xlsm)

    geral = wb["Geral"]
    prod, ree = {}, {}
    for r in range(2, geral.max_row + 1):
        posto, situacao, cadastrada = geral.cell(r, 1).value, geral.cell(r, 7).value, geral.cell(r, 8).value
        if not isinstance(posto, (int, float)) or int(posto) in prod:
            continue  # VLOOKUP keeps the first match
        # Geral!I: IF(ISNUMBER(H),IF(G="Operação",H,0),0)
        ok = isinstance(cadastrada, (int, float)) and situacao == "Operação"
        prod[int(posto)] = cadastrada if ok else 0.0
        ree[int(posto)] = geral.cell(r, 11).value if isinstance(geral.cell(r, 11).value, int) else ""
    resumo = wb["Resumo"]
    bm_prod = {int(resumo.cell(r, 2).value): resumo.cell(r, 3).value for r in (18, 19)}  # 292, 302

    sens = wb["Sensibilidade"]
    with open(DATA / "postos.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["posto", "subsystem", "ree"])
        r = 4
        while sens.cell(r, 3).value is not None:
            posto = int(sens.cell(r, 3).value)
            w.writerow([posto, sens.cell(r, 1).value, ree.get(posto, "")])
            r += 1

    with open(DATA / "ena_plants.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["posto", "subsystem", "productivity"])
        for sub, (sheet, total) in TOTALS.items():
            ws = wb[sheet]
            for r in plant_rows(ws, total):
                posto = int(ws.cell(r, 2).value)
                w.writerow([posto, sub, bm_prod.get(posto, 0.0) if "Resumo" in ws.cell(r, 4).value else prod[posto]])

    mlt = wb["MLT_SUB"]
    with open(DATA / "mlt_subsystem.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["subsystem", *range(1, 13)])
        for r in range(2, 6):
            w.writerow([SUBSYSTEM_NAMES[mlt.cell(r, 1).value.upper()], *(mlt.cell(r, c).value for c in range(2, 14))])


if __name__ == "__main__":
    main(sys.argv[1])
