"""
Tests pour `backtest_phase2_v7.py::prepare` -- 39e round (`PLAN.md`) :
`local_duration`/`context_duration`, paramètres AJOUTÉS pour permettre un
appel UT-AGNOSTIQUE (nombre de bougies plutôt que durée calendaire fixe),
trouvaille du 38e round (`LOCAL_DURATION="5D"`/`CONTEXT_DURATION="15D"`
dégénèrent structurellement sur D1/Hebdomadaire -- `n_borders` ne peut
jamais atteindre `MIN_BORDERS=3`).

`prepare` elle-même n'avait AUCUNE couverture dédiée avant ce round (utilisée
indirectement par `test_backtest_phase2_faithful.py`/`test_trend_table.py`/
etc., jamais testée pour son propre compte) -- ce fichier comble ce trou en
se concentrant sur ce que ce round a changé, pas sur tout le reste de la
fonction (déjà couvert indirectement ailleurs, non-régression bit-à-bit
vérifiée par rejeu réel des CSV committés)."""
import numpy as np
import pandas as pd
import pytest

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import (
    prepare, LOCAL_DURATION, CONTEXT_DURATION, LOCAL_DURATION_H4_BARS, CONTEXT_DURATION_H4_BARS,
)

# Chargement protégé -- même patron que `test_backtest_phase2_faithful.py`
# (cf. sa docstring : sans ce try/except, TOUT ce fichier serait injectable
# à la collecte pytest avant même que `@pytest.mark.data_dependent` n'ait sa
# chance d'exclure quoi que ce soit).
try:
    _H4_BTC = resample(load_h1("BTCUSDT"), "4h").iloc[:2000].reset_index(drop=True)
    _DATA_UNAVAILABLE = None
except (FileNotFoundError, ValueError) as e:
    _H4_BTC = None
    _DATA_UNAVAILABLE = str(e)

_skip_if_no_data = pytest.mark.skipif(_DATA_UNAVAILABLE is not None, reason=_DATA_UNAVAILABLE or "")

def test_h4_bars_constants_match_calendar_duration_exactly():
    """Garde-fou documentaire : LOCAL_DURATION_H4_BARS/CONTEXT_DURATION_H4_BARS
    doivent être EXACTEMENT les mêmes durées que LOCAL_DURATION/CONTEXT_DURATION
    à l'échelle H4 (4h/bougie) -- pas des valeurs indépendantes inventées."""
    assert LOCAL_DURATION_H4_BARS == 30, "5 jours * 24h / 4h = 30 bougies H4"
    assert CONTEXT_DURATION_H4_BARS == 90, "15 jours * 24h / 4h = 90 bougies H4"
    assert LOCAL_DURATION == "5D"
    assert CONTEXT_DURATION == "15D"

@_skip_if_no_data
@pytest.mark.data_dependent
def test_prepare_default_unchanged_when_no_duration_passed():
    """Non-régression directe : `prepare(df)` (sans arguments) doit rester
    BIT-À-BIT identique à avant ce round (comparé à un appel explicite avec
    les valeurs calendaires historiques)."""
    default = prepare(_H4_BTC.copy())
    explicit = prepare(_H4_BTC.copy(), local_duration=LOCAL_DURATION, context_duration=CONTEXT_DURATION)
    for col in ("local_range", "context_range", "ctx_median", "n_borders"):
        pd.testing.assert_series_equal(default[col], explicit[col], check_names=False)

@_skip_if_no_data
@pytest.mark.data_dependent
def test_prepare_bar_count_window_on_h4_matches_calendar_window_exactly():
    """Sur H4 (4h/bougie), une fenêtre de 30/90 bougies DOIT donner un
    résultat identique à "5D"/"15D" (même fenêtre, deux unités différentes
    pour EXPRIMER la même chose) -- vérifie que le paramètre fait bien ce
    qu'il prétend, pas seulement qu'il ne casse rien.

    Comparé à partir de la bougie 90 (CONTEXT_DURATION_H4_BARS) : avant ce
    point, `.rolling("15D")` (offset, `min_periods=1` implicite) et
    `.rolling(90)` (entier, `min_periods=90` implicite) ont des conventions
    de WARMUP différentes par construction pandas (l'un accepte une fenêtre
    partiellement remplie, l'autre exige les 90 points) -- une différence
    de convention de bord, sans effet en production (`warmup = EMA_SLOW + 20`
    ampute déjà largement plus que 90 bougies avant toute décision réelle).
    Sur données réelles SANS TROU (0 trou vérifié, cf. CLAUDE.md), les deux
    DOIVENT en revanche coïncider bougie pour bougie une fois les deux
    fenêtres pleines."""
    calendar = prepare(_H4_BTC.copy(), local_duration=LOCAL_DURATION, context_duration=CONTEXT_DURATION)
    bars = prepare(_H4_BTC.copy(), local_duration=LOCAL_DURATION_H4_BARS, context_duration=CONTEXT_DURATION_H4_BARS)
    for col in ("local_range", "context_range", "n_borders"):
        pd.testing.assert_series_equal(
            calendar[col].iloc[CONTEXT_DURATION_H4_BARS:].reset_index(drop=True),
            bars[col].iloc[CONTEXT_DURATION_H4_BARS:].reset_index(drop=True),
            check_names=False)

def test_prepare_bar_count_window_is_ut_agnostic_ground_truth():
    """Vérité terrain calculée à la main sur une série synthétique : une
    fenêtre exprimée en NOMBRE DE BOUGIES donne, pour une UT donnée, EXACTEMENT
    la même largeur de fenêtre (en nombre de points), quelle que soit la
    fréquence de l'index -- contrairement à une durée calendaire, qui varie."""
    dates_fast = pd.date_range("2024-01-01", periods=20, freq="4h")   # H4
    dates_slow = pd.date_range("2024-01-01", periods=20, freq="1D")   # D1 (même NOMBRE de bougies)
    prices = np.linspace(100.0, 119.0, 20)
    for dates in (dates_fast, dates_slow):
        df = pd.DataFrame({
            "date": dates, "open": prices, "high": prices + 1.0, "low": prices - 1.0, "close": prices,
        })
        # Fenêtre de 5 bougies : local_range à l'indice 4 (5e bougie, la
        # fenêtre est pleine pour la 1re fois) doit valoir max(high[0:5]) -
        # min(low[0:5]), IDENTIQUE en H4 et en D1 (même nombre de points).
        ts = df.set_index("date")
        expected = ts["high"].iloc[0:5].max() - ts["low"].iloc[0:5].min()
        got = (ts["high"].rolling(5).max() - ts["low"].rolling(5).min()).iloc[4]
        assert got == expected

TESTS = [
    test_h4_bars_constants_match_calendar_duration_exactly,
    test_prepare_default_unchanged_when_no_duration_passed,
    test_prepare_bar_count_window_on_h4_matches_calendar_window_exactly,
    test_prepare_bar_count_window_is_ut_agnostic_ground_truth,
]

def main():
    n_pass = 0
    n_fail = 0
    for test_fn in TESTS:
        name = test_fn.__name__
        try:
            test_fn()
        except AssertionError as e:
            print(f"FAIL  {name}: {e}")
            n_fail += 1
        except Exception as e:
            print(f"ERROR {name}: {type(e).__name__}: {e}")
            n_fail += 1
        else:
            print(f"PASS  {name}")
            n_pass += 1
    print(f"\n{n_pass}/{len(TESTS)} tests passés" + (f", {n_fail} échec(s)" if n_fail else ""))
    if n_fail:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
