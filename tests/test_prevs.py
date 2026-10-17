import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from prevs import parse_name, pmo_start, read_prevs, sensitivity, write_prevs
from prevs.ena import artificial_flows
from prevs.io import excel_round

DATA = Path(__file__).parent / "data"
BASE, SE80_S80 = DATA / "202611-prevs.rv0", DATA / "202611-prevs-SE080_S080.rv0"
START = dt.date(2026, 10, 31)  # first PMO Saturday of 2026-11


def test_round_trip_is_byte_identical(tmp_path):
    out = tmp_path / "p.rv0"
    write_prevs(read_prevs(BASE), out)
    assert out.read_bytes() == BASE.read_bytes()


def test_excel_round_half_away_from_zero():
    assert excel_round(np.array([2.5, -2.5, 0.4, -0.4])).tolist() == [3, -3, 0, 0]


def test_dates_from_name():
    # Saturday on/before day 1; Aug/2026 starts on a Saturday itself (matches the workbook calendar)
    assert pmo_start(2026, 11) == START
    assert pmo_start(2026, 8) == dt.date(2026, 8, 1)
    assert pmo_start(2027, 1) == dt.date(2026, 12, 26)
    assert parse_name(BASE) == (START, 0)
    assert parse_name("x/202612-prevs-SE080_S080.rv3") == (dt.date(2026, 11, 28), 3)
    with pytest.raises(ValueError):
        parse_name("my_forecast.txt")


def test_month_weights():
    assert sensitivity.month_weights(START).tolist() == [6, 7, 7, 7, 3, 0]


def test_se80_s80_matches_excel(tmp_path):
    targets = {"SE": 80, "S": 80}
    scaled, _ = sensitivity.build(read_prevs(BASE), START, targets)
    name = sensitivity.scenario_name(START, targets)
    assert name == SE80_S80.name

    write_prevs(scaled, tmp_path / name)
    assert (tmp_path / name).read_bytes() == SE80_S80.read_bytes()


def test_alter_from_keeps_earlier_weeks():
    prevs = read_prevs(BASE)
    scaled, f = sensitivity.build(prevs, START, {"SE": 80}, alter_from=START + dt.timedelta(days=14))
    assert (scaled.loc[1, [1, 2]] == prevs.loc[1, [1, 2]]).all()
    assert np.allclose(scaled.loc[1, [3, 4, 5, 6]], prevs.loc[1, [3, 4, 5, 6]] * f["SE"])


def test_bad_targets_raise():
    prevs = read_prevs(BASE)
    with pytest.raises(ValueError, match="no days"):
        sensitivity.factors(prevs, START, {"SE": 80}, alter_from=START + dt.timedelta(days=35))
    with pytest.raises(ValueError, match="whole"):
        sensitivity.factors(prevs, START, {"SE": 80.5})


def test_light_rules_across_thresholds():
    # weeks 1-3 walk posto 298 through its branches; weeks 4-6 (298 = 160) drive 126 and 303
    prevs = read_prevs(BASE)
    prevs.loc[125] = [100, 200, 230, 300, 300, 300]
    prevs.loc[201] = 0
    prevs.loc[202] = [10, 10, 10, 10, 30, 30]
    prevs.loc[203] = 100
    prevs.loc[129] = [500, 500, 500, 500, 500, 700]
    q = artificial_flows(prevs)
    assert np.allclose(q[298], [100 * 119 / 190, 119, 140, 160, 160, 160])
    w = slice(3, 6)  # 315 = 260 -> 316 = 190, 304 = 70, 131 = 144
    assert np.allclose(q[304][w], 70) and np.allclose(q[131][w], 144)
    assert np.allclose(q[126][w], [220, 220, 340])  # 127 = 129 - 190 -> <=430 branch vs fixed 340
    assert np.allclose(q[303][w], [44, 51, 51])  # 132 = 10 (<17) vs 30 (capped at 17), + min(46, 34)
