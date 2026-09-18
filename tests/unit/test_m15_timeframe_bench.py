"""
Tests pour `emile/core/m15_timeframe_bench.py` (43e round, `docs/PLAN.md`) --
ferme le surclassement trouvé dans `docs/STATUS.md` ("NO-GO H1/M15
reconfirmé... avec le moteur IP-fidèle actuel", alors que seul H1 avait
réellement été rejoué avec `run_faithful` -- M15 jamais retesté qu'avec
l'ancien proxy générique, BTC seul).

Ne re-teste PAS `run_faithful` lui-même (déjà couvert par
`test_backtest_phase2_faithful.py`) -- se concentre sur :
  1. Le garde-fou anti-stub `load_m15`/`_MIN_M15_ROWS` (analogue de
     `_MIN_H1_ROWS`, jamais vérifié directement même pour `load_h1`).
  2. Le remapping des rôles UT/UT+1/UT+2 et les délais de clôture choisis
     (M15 exécution, H1 stop à `closure_delay_d1=1h`, H4 gate à
     `closure_delay_weekly=4h`) -- comparé directement à un appel
     `run_faithful` de référence, jamais une réimplémentation.
"""
import pandas as pd
import pytest

from emile.backtests.backtest_phase2 import load_m15, resample, _MIN_M15_ROWS
from emile.backtests.backtest_phase2_faithful import run_faithful
from emile.core.m15_timeframe_bench import (
    run_m15_experiment, H1_ROLE_DELAY, H4_ROLE_DELAY,
)

try:
    _M15_BTC = load_m15("BTCUSDT")
    _DATA_UNAVAILABLE = None
except (FileNotFoundError, ValueError) as e:
    _M15_BTC = None
    _DATA_UNAVAILABLE = str(e)

_skip_if_no_data = pytest.mark.skipif(_DATA_UNAVAILABLE is not None, reason=_DATA_UNAVAILABLE or "")


def test_load_m15_rejects_degenerate_stub(tmp_path, monkeypatch):
    """Un fichier de moins de `_MIN_M15_ROWS` lignes doit lever explicitement,
    jamais être silencieusement accepté (même discipline que `load_h1`,
    incident documenté dans `CLAUDE.md`)."""
    import emile.backtests.backtest_phase2 as bp2

    stub = tmp_path / "BTCUSDT_15m_processed.csv"
    stub.write_text("datetime,open,high,low,close,volume\n2019-01-01 00:00:00,1,1,1,1,0\n")
    monkeypatch.setattr(bp2, "DATA_DIR", tmp_path)
    with pytest.raises(ValueError, match="degenere|dégénérée|absente"):
        bp2.load_m15("BTCUSDT")


def test_min_m15_rows_is_h1_threshold_scaled_not_invented():
    """`_MIN_M15_ROWS` doit être exactement 4x `_MIN_H1_ROWS` (ratio de bougies
    M15/H1 sur une même durée calendaire) -- pas une valeur inventée
    indépendamment."""
    from emile.backtests.backtest_phase2 import _MIN_H1_ROWS
    assert _MIN_M15_ROWS == 4 * _MIN_H1_ROWS


@_skip_if_no_data
@pytest.mark.data_dependent
def test_run_m15_experiment_matches_manual_remap_ground_truth():
    """`run_m15_experiment` doit produire EXACTEMENT le même résultat qu'un
    appel `run_faithful` manuel avec le même remapping -- pas une
    réimplémentation qui pourrait diverger silencieusement."""
    m15 = load_m15("BTCUSDT")
    h1 = resample(m15, "1h")
    h4 = resample(m15, "4h")
    expected = run_faithful(m15.copy(), h1.copy(), h4.copy(), "MODERE",
                             closure_delay_d1=H1_ROLE_DELAY,
                             closure_delay_weekly=H4_ROLE_DELAY)
    actual = run_m15_experiment("BTCUSDT", "MODERE")
    assert actual == expected


@_skip_if_no_data
@pytest.mark.data_dependent
def test_role_delays_are_exact_candle_durations_not_recycled_from_h1_experiment():
    """H1_ROLE_DELAY/H4_ROLE_DELAY doivent être respectivement 1h/4h (durée
    EXACTE d'une bougie H1/H4) -- pas recopiés de `h1_timeframe_bench.py`
    (qui vaut 4h pour un rôle différent, H4 comme stop UT+1)."""
    assert H1_ROLE_DELAY == pd.Timedelta(hours=1)
    assert H4_ROLE_DELAY == pd.Timedelta(hours=4)


@_skip_if_no_data
@pytest.mark.data_dependent
def test_m15_execution_produces_more_trades_than_h4_native_same_asset():
    """Vérité de contrôle minimale : passer d'une exécution H4 à M15 (16x
    plus de bougies) doit mécaniquement produire AU MOINS autant de trades
    (le proxy évalue chaque bougie -- une granularité plus fine ne peut pas
    réduire le nombre d'opportunités d'entrée), sinon le remapping des rôles
    est probablement cassé (ex. gate UT+2 mal câblé, tout bloqué)."""
    res_m15 = run_m15_experiment("BTCUSDT", "MODERE")
    m15 = load_m15("BTCUSDT")
    h4 = resample(m15, "4h")
    d1 = resample(m15, "1D")
    weekly = resample(m15, "W")
    res_h4 = run_faithful(h4.copy(), d1.copy(), weekly.copy(), "MODERE")
    assert res_m15["n_trades"] >= res_h4["n_trades"]

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failures += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passent")
    raise SystemExit(1 if failures else 0)
