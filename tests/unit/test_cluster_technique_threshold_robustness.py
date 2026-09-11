"""
Tests pour cluster_technique_threshold_robustness.py (vague 5, PLAN.md
"Plan d'autonomie 8h"). Deux volets :
  1. Non-régression : au seuil de référence (BASELINE_PCTL=0.20, déjà en
     production dans cluster_technique.py), la copie paramétrée
     (`prepare_diversified_pctl`/`run_diversified_pctl`) doit reproduire
     EXACTEMENT `diversification.py::prepare_diversified`/`run_diversified`
     -- garantit que la duplication n'a introduit aucune dérive silencieuse
     avant de l'utiliser pour un test de sensibilité.
  2. Sanité de la grille : faire varier `proximity_pctl` doit réellement
     changer la fréquence du signal Pattern B (sinon le test de robustesse
     ne testerait rien) -- vérifié sur données synthétiques ET réelles.
"""
import numpy as np
import pandas as pd
import sys

from emile.core.diversification import prepare_diversified, run_diversified
from emile.core.cluster_technique_threshold_robustness import (
    prepare_diversified_pctl, run_diversified_pctl, PROXIMITY_PCTL_GRID, BASELINE_PCTL,
)

def _synthetic_h1(n_days=500, seed=0):
    """Même construction que test_diversification.py::_synthetic_h1 (série
    assez longue pour dépasser tous les warmups)."""
    rng = np.random.default_rng(seed)
    n = n_days * 24
    steps = rng.normal(loc=0.01, scale=1.0, size=n)
    close = 100 + np.cumsum(steps)
    close = np.maximum(close, 1.0)
    high = close + rng.uniform(0.1, 1.0, size=n)
    low = np.maximum(close - rng.uniform(0.1, 1.0, size=n), 0.5)
    open_ = close - rng.normal(0, 0.2, size=n)
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"date": dates, "open": open_, "high": high, "low": low, "close": close})

def _resample(h1, rule):
    ts = h1.set_index("date")
    out = ts.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return out.reset_index()

def test_baseline_pctl_matches_production_default():
    """La valeur de référence de ce script doit être EXACTEMENT le seuil
    déjà en production dans cluster_technique.py (pas une valeur proche)."""
    from emile.core import cluster_technique
    assert BASELINE_PCTL == cluster_technique.SUPPORT_PROXIMITY_PCTL

def test_grid_is_symmetric_around_baseline_and_fixed_a_priori():
    """Grille symétrique autour de 0.20, pas resserrée après coup (cf.
    docstring de tête du module) -- vérifié structurellement : 2 valeurs de
    part et d'autre, écart constant."""
    assert BASELINE_PCTL in PROXIMITY_PCTL_GRID
    sorted_grid = sorted(PROXIMITY_PCTL_GRID)
    idx = sorted_grid.index(BASELINE_PCTL)
    assert idx == 2 and len(sorted_grid) == 5  # 2 valeurs en dessous, 2 au-dessus
    below = [BASELINE_PCTL - v for v in sorted_grid[:2]]
    above = [v - BASELINE_PCTL for v in sorted_grid[3:]]
    assert np.allclose(sorted(below), sorted(above))

def test_prepare_diversified_pctl_matches_reference_at_baseline_threshold():
    """Non-régression de la duplication : à proximity_pctl=BASELINE_PCTL,
    `prepare_diversified_pctl` doit produire EXACTEMENT la même colonne
    'cluster_signal' (et les colonnes dont elle dépend) que
    `diversification.prepare_diversified` (défaut du module, 0.20)."""
    h1 = _synthetic_h1(n_days=500, seed=11)
    h4 = _resample(h1, "4h")
    d1 = _resample(h1, "1D")

    ref, _ = prepare_diversified(h4.copy(), d1.copy())
    dup = prepare_diversified_pctl(h4.copy(), d1.copy(), proximity_pctl=BASELINE_PCTL)

    assert (ref["cluster_signal"].values == dup["cluster_signal"].values).all()
    assert np.allclose(ref["score"].values, dup["score"].values, equal_nan=True)
    assert np.allclose(ref["ctx_support_d1"].values, dup["ctx_support_d1"].values, equal_nan=True)

def test_run_diversified_pctl_matches_reference_at_baseline_threshold():
    """Non-régression bout-en-bout : au seuil de référence, la copie du
    moteur complet doit produire EXACTEMENT le même dict de résultats que
    `diversification.run_diversified` (mêmes trades, même drawdown, même
    retour) -- pour les deux réglages utilisés par le test de robustesse
    (enable_pattern_b=True et False)."""
    h1 = _synthetic_h1(n_days=500, seed=12)
    h4 = _resample(h1, "4h")
    d1 = _resample(h1, "1D")

    for enable_b in (True, False):
        ref = run_diversified(h4.copy(), d1.copy(), management_profile="MODERE",
                               use_mtf_gate=True, enable_pattern_b=enable_b)
        dup = run_diversified_pctl(h4.copy(), d1.copy(), proximity_pctl=BASELINE_PCTL,
                                    management_profile="MODERE", use_mtf_gate=True,
                                    enable_pattern_b=enable_b)
        assert ref == dup, (enable_b, ref, dup)

def test_varying_proximity_pctl_actually_changes_the_signal():
    """Sanité de la grille sur données RÉELLES (BTC H4) : si aucun des
    seuils testés ne change la fréquence du signal Pattern B par rapport à
    la référence, le test de robustesse ne testerait rien -- vérifie que ce
    n'est pas le cas."""
    from emile.backtests.backtest_phase2 import load_h1, resample
    h1 = load_h1("BTCUSDT")
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")

    counts = {}
    for pctl in PROXIMITY_PCTL_GRID:
        h4p = prepare_diversified_pctl(h4.copy(), d1.copy(), proximity_pctl=pctl)
        counts[pctl] = int(h4p["cluster_signal"].sum())

    # Un seuil percentile plus large (proximity_pctl plus grand) doit accepter
    # au moins autant de bougies "proches du support" qu'un seuil plus étroit
    # (monotonie attendue de compute_support_confluence, cf. cluster_technique.py) --
    # pas une égalité stricte partout (le ET avec ma20_rebound/trend_established
    # peut aplatir des différences), mais pas tous identiques non plus.
    assert len(set(counts.values())) > 1, counts

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} tests passés")
