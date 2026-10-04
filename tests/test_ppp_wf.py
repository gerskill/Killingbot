import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
import ppp_wf
from ppst_wf import DEFAULTS, run_backtest


def test_ppp_croissance_superieure_au_taux():
    assert ppp_wf.ppp(20, 0.10, 0.04) == pytest.approx(13.68, abs=0.01)


def test_ppp_g_egal_r_vaut_le_per():
    assert ppp_wf.ppp(17, 0.06, 0.06) == 17


def test_ppp_g_inferieur_r_sous_le_plafond():
    # plafond (1+r)/(r-g) = 35 → PER 20 se rembourse
    assert ppp_wf.ppp(20, 0.02, 0.05) == pytest.approx(29.2, abs=0.1)


def test_ppp_g_inferieur_r_au_dessus_du_plafond_jamais():
    assert ppp_wf.ppp(40, 0.02, 0.05) == math.inf


def test_ppp_non_calculable():
    assert math.isnan(ppp_wf.ppp(-5, 0.1, 0.08))
    assert math.isnan(ppp_wf.ppp(20, float("nan"), 0.08))


def _f(start, end, val, form, filed):
    return {"start": start, "end": end, "val": val, "form": form, "filed": filed}


FACTS = [
    _f("2021-01-01", "2021-12-31", 1.0, "10-K", "2022-02-15"),
    _f("2022-01-01", "2022-12-31", 2.0, "10-K", "2023-02-15"),
    _f("2022-01-01", "2022-06-30", 0.8, "10-Q", "2022-08-01"),
    _f("2023-01-01", "2023-06-30", 1.6, "10-Q", "2023-08-01"),
    # comparatif republié plus tard (restaté) : doit être ignoré, première publication seulement
    _f("2022-01-01", "2022-06-30", 9.9, "10-Q", "2023-08-01"),
]


def test_ttm_reconstruit_depuis_le_ytd():
    fund = ppp_wf.eps_point_in_time(FACTS, g_years=3, g_cap=1.0)
    row = fund.loc[pd.Timestamp("2023-08-02")]
    assert row["eps_ttm"] == pytest.approx(2.0 + 1.6 - 0.8)
    assert row["g"] == pytest.approx(1.0)  # 1.0 → 2.0 en 1 exercice


def test_split_ramene_en_base_actuelle():
    splits = pd.Series([2.0], index=[pd.Timestamp("2023-01-01")])
    fund = ppp_wf.eps_point_in_time(FACTS, splits, g_years=3, g_cap=1.0)
    # FY2021 déposé avant le split → divisé par 2 ; FY2022 après → inchangé
    assert fund.loc[pd.Timestamp("2022-02-16"), "eps_ttm"] == pytest.approx(0.5)
    assert fund.loc[pd.Timestamp("2023-02-16"), "eps_ttm"] == pytest.approx(2.0)
    # 0.5 → 2.0 en 1 exercice = +300 %, plafonné à 100 %
    assert fund.loc[pd.Timestamp("2023-02-16"), "g"] == pytest.approx(1.0)


def test_g_plafonne():
    fund = ppp_wf.eps_point_in_time(FACTS, g_years=3, g_cap=0.25)
    assert fund["g"].dropna().max() == pytest.approx(0.25)


def test_masque_sans_anticipation():
    fund = ppp_wf.eps_point_in_time(FACTS, g_years=3, g_cap=0.25)
    idx = pd.date_range("2023-02-14", "2023-02-17", freq="D")
    df = pd.DataFrame({"Close": [10.0] * len(idx)}, index=idx)
    mask, p = ppp_wf.ppp_mask(df, fund, r=0.08, ppp_max=50)
    # dépôt le 15 → connu seulement le 16
    assert p.isna().tolist() == [True, True, False, False]


def _prices(n=1500, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0008, 0.02, n)))
    idx = pd.date_range("2018-01-01", periods=n, freq="D")
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close}, index=idx)


def test_masque_neutre_identique_a_l_original():
    df = _prices()
    base = run_backtest(df, DEFAULTS)
    on = run_backtest(df, {**DEFAULTS, "_entry_mask": pd.Series(True, index=df.index)})
    assert "error" not in base
    assert on == base


def test_masque_bloquant_aucun_trade():
    df = _prices()
    res = run_backtest(df, {**DEFAULTS, "_entry_mask": pd.Series(False, index=df.index)})
    assert res == {"error": "Aucun trade"}
