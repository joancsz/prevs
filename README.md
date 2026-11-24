# prevs

Read, write and build sensitivities of ONS **prevs** files: the weekly inflow forecasts
(m³/s per posto) that feed the official DECOMP/NEWAVE models.

The sensitivity logic is a faithful port of the `Matriz_e_Sensibilidade` Excel workbook. Given a
base prevs, it scales every posto of a subsystem so the subsystem's ENA over the PMO month reaches a
target % of the MLT (long-term average). The goal is to later turn
[py-smap](https://github.com/joancsz/py-smap) forecasts into unified prevs files.

## Install

```bash
python -m venv .venv
.venv/Scripts/pip install -e .[dev]   # Windows; use .venv/bin/pip on Linux/macOS
```

Requires Python ≥ 3.10 and pandas.

## Quickstart

### Read and write a prevs

```python
from prevs import read_prevs, write_prevs

df = read_prevs("202611-prevs.rv0")   # index = posto (file order kept), columns 1..6 (weeks)
df.loc[6]                             # Furnas, 6 weekly flows
write_prevs(df, "copy.rv0")           # byte-identical to the input
```

`write_prevs` rounds half away from zero (like Excel) and writes the ONS fixed-width layout:
`I6` index, `I5` posto, 6 × `I10` flows, with CRLF line endings.

### Create a %MLT sensitivity

```python
from prevs import parse_name, read_prevs, write_prevs, sensitivity

path = "202611-prevs.rv0"
base = read_prevs(path)
start, rev = parse_name(path)          # (2026-10-31, 0): week 1 starts on a Saturday
targets = {"SE": 80, "S": 80}          # % of MLT per subsystem

scaled, factors = sensitivity.build(base, start, targets)
write_prevs(scaled, sensitivity.scenario_name(start, targets, rev))   # 202611-prevs-SE080_S080.rv0
print(factors)                         # {'SE': 0.729..., 'S': 0.400...}
```

A prevs file has no dates inside it; the math needs the date week 1 starts to pick the monthly
MLT and the week weights. `parse_name` gets that date from names like `YYYYmm-prevs[...].rv<N>`.
The date is the Saturday on or before day 1 of the PMO month. For any other name, pass the date
yourself: `pmo_start(2026, 11)` or `datetime.date(2026, 10, 31)`.

Subsystems you leave out keep their flows. For a revision, pass `alter_from` (a week start date)
to scale only that week onward, and `rev=` to name the file:

```python
import datetime as dt

scaled, f = sensitivity.build(base, start, {"SE": 90}, alter_from=start + dt.timedelta(days=7))
sensitivity.scenario_name(start, {"SE": 90}, rev=1)              # 202611-prevs-SE090.rv1
```

### A sensitivity matrix (the Excel `Matriz_ENAs` macro)

```python
for se in range(75, 125, 5):
    for s in (80, 120, 160, 200, 240):
        t = {"SE": se, "S": s}
        write_prevs(sensitivity.build(base, start, t)[0], sensitivity.scenario_name(start, t))
```

### Inspect ENA and %MLT

```python
from prevs.ena import subsystem_ena, pct_mlt

ena = subsystem_ena(base, ["SE", "S", "NE", "N"], start)   # MWmed per subsystem x week
pct_mlt(ena, start)                                      # fraction of MLT per week
```

## How a factor is computed

This replicates the workbook exactly:

1. **ENA per plant** = flow × adopted productivity. This includes the artificial postos: Tietê
   pumping, Paraíba do Sul/Light (298, 126, 303 …), Segredo (75) and Belo Monte: 292 = 288 minus
   the monthly hydrograph of the reduced stretch, clipped to [0, 13900], and 302 = 288 − 292. A week
   that crosses into a new month mixes both months by days.
2. **Weekly %MLT** = subsystem ENA / subsystem MLT for the month. A week that crosses into a new
   month uses a day-weighted MLT.
3. **M** = mean %MLT over the PMO month, with each week weighted by its days inside that month.
   **A** = the same mean over the altered weeks only.
4. **factor = T / (100·M) · A / M.** It is computed once, from the base flows, so the result lands
   close to the target but not exactly on it (the Light rules are not linear).

## Data

`prevs/data/*.csv` hold the posto → subsystem/REE table (which also sets the output row order),
the productivities of the ENA plants, the subsystem MLTs and the Belo Monte hydrograph (the curve
picked in the workbook, MÉDIO by default). They were extracted from the workbook.
Regenerate them when ONS updates productivities:

```bash
python tools/extract_xlsm.py path/to/Matriz_e_Sensibilidade.xlsm
```

## Tests

```bash
pytest
```

`tests/data/` contains a base prevs and the SE080_S080 and N080 files produced by Excel. The tests check that
the output is byte-identical.

## Limits

- **REE targets** are not supported yet; `postos.csv` already has the REE of each posto.
- **Revisions (rv1+)** use the same approximate Excel formula, and no Excel reference file has
  checked them yet.

## License

MIT, see [LICENSE](LICENSE).
