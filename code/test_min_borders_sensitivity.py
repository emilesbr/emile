"""
Tests pour `min_borders_sensitivity.py` (tension "3 vs 4 bornes", PLAN.md
backlog item 11 catégorie B (iii)). Même esprit que
`test_cluster_technique_threshold_robustness.py` — quatre volets :

  1. Ancrage : la valeur de référence du script est EXACTEMENT la constante
     déjà en production, dans LES DEUX modules concernés (v7 et trend_table,
     qui ont chacun leur propre liaison), et la grille est fixée a priori
     autour du couple 3-4 en litige.
  2. Non-régression : au seuil de référence (3), les wrappers doivent
     reproduire EXACTEMENT le résultat des moteurs de production appelés
     directement — ici c'est trivialement vrai par construction (aucune
     duplication de code, cf. docstring du module mesuré), mais le test le
     VÉRIFIE au lieu de le supposer, et il détecterait une régression si
     quelqu'un remplaçait un jour l'override par une copie du moteur.
  3. Innocuité de l'override : la constante est restaurée dans tous les cas
     (y compris si le moteur lève), et l'override d'un module ne fuit pas
     dans l'autre. Sans ça, ce script de mesure contaminerait le reste de la
     suite de tests — risque réel puisqu'il touche des modules de production
     en mémoire.
  4. Sanité de la mesure : (a) l'override ATTEINT réellement le moteur (une
     valeur absurde doit supprimer toutes les entrées fraîches — sinon les
     "0 écart" mesurés ne prouveraient rien) ; (b) le gate de maturité est
     documenté comme NON DISCRIMINANT sur données réelles pour toute la
     grille testée — c'est la trouvaille du chantier, elle est verrouillée
     par un test pour qu'une évolution future de la définition de
     `n_borders` le signale au lieu de le laisser passer silencieusement.
"""
import numpy as np
import pandas as pd
import pytest
import sys
sys.path.insert(0, ".")
import backtest_phase2_v7
import trend_table
from backtest_phase2_v7 import run_v7
from trend_table import run_trend_table
from min_borders_sensitivity import (
    MIN_BORDERS_GRID, BASELINE_MIN_BORDERS, override_min_borders,
    run_v7_min_borders, run_trend_table_min_borders, borders_binding_stats,
)


def _synthetic_h1(n_days=500, seed=0):
    """Même construction que `test_cluster_technique_threshold_robustness.py::
    _synthetic_h1` (série assez longue pour dépasser tous les warmups)."""
    rng = np.random.default_rng(seed)
    n = n_days * 24
    steps = rng.normal(loc=0.01, scale=1.0, size=n)
    close = 100 + np.cumsum(steps)
    close = np.maximum(close, 1.0)
    high = close + rng.uniform(0.1, 1.0, size=n)
    low = np.maximum(close - rng.uniform(0.1, 1.0, size=n), 0.5)
    open_ = close - rng.normal(0, 0.2, size=n)
    volume = rng.lognormal(mean=5.0, sigma=0.6, size=n)
    dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"date": dates, "open": open_, "high": high, "low": low,
                         "close": close, "volume": volume})


def _resample(h1, rule):
    ts = h1.set_index("date")
    out = ts.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return out.reset_index()


def _resample_vol(h1, rule):
    ts = h1.set_index("date")
    out = ts.resample(rule).agg({"volume": "sum"}).dropna()
    return out.reset_index()


# ---------------------------------------------------------------------------
# 1. Ancrage sur la production + grille fixée a priori
# ---------------------------------------------------------------------------
def test_baseline_matches_production_constant_in_both_modules():
    """La référence du script doit être la valeur de production elle-même,
    pas une valeur proche — et dans LES DEUX modules, qui portent chacun leur
    propre liaison de `MIN_BORDERS` (trend_table l'importe depuis v7 au
    moment de l'import, donc une divergence entre les deux serait invisible
    sans ce test)."""
    assert BASELINE_MIN_BORDERS == backtest_phase2_v7.MIN_BORDERS == 3
    assert BASELINE_MIN_BORDERS == trend_table.MIN_BORDERS


def test_grid_fixed_a_priori_brackets_the_disputed_pair():
    """La grille doit contenir les DEUX valeurs en litige (3, camp
    `BREAKOUT_RATIO11`/`STRUCTURES_ALTERATIONS`/manuel PDF ; 4, camp
    `ZONE_ACCUMULATION`/`PULLBACK_MATURITE`) et déborder de part et d'autre,
    pour distinguer "3 et 4 se valent" de "aucun seuil n'a d'effet"."""
    assert BASELINE_MIN_BORDERS in MIN_BORDERS_GRID
    assert 4 in MIN_BORDERS_GRID
    grid = sorted(MIN_BORDERS_GRID)
    assert grid == list(range(grid[0], grid[-1] + 1)), "grille contiguë attendue"
    assert grid[0] < 3 and grid[-1] > 4, "la grille doit déborder du couple 3-4"


# ---------------------------------------------------------------------------
# 2. Non-régression contre les moteurs réels au seuil de référence
# ---------------------------------------------------------------------------
def test_run_v7_min_borders_matches_real_engine_at_baseline():
    """Au seuil de référence, le wrapper doit produire EXACTEMENT le même
    résultat que `backtest_phase2_v7.run_v7` appelé directement — pour les
    deux configurations de gate utilisées dans le projet."""
    h1 = _synthetic_h1(n_days=500, seed=21)
    h4 = _resample(h1, "4h")
    d1 = _resample(h1, "1D")

    for use_gate in (True, False):
        ref = run_v7(h4.copy(), d1.copy(), "MODERE", use_mtf_gate=use_gate, use_mtf_stop=False)
        got = run_v7_min_borders(h4.copy(), d1.copy(), "MODERE", BASELINE_MIN_BORDERS,
                                 use_mtf_gate=use_gate, use_mtf_stop=False)
        assert ref == got, (use_gate, ref, got)


def test_run_trend_table_min_borders_matches_real_engine_at_baseline():
    """Idem pour le moteur de tendance (module distinct, liaison distincte)."""
    h1 = _synthetic_h1(n_days=500, seed=22)
    h4 = _resample(h1, "4h")
    vol = _resample_vol(h1, "4h")

    for profile in ("MODERE", "AGRESSIF"):
        ref = run_trend_table(h4.copy(), vol.copy(), profile)
        got = run_trend_table_min_borders(h4.copy(), vol.copy(), profile, BASELINE_MIN_BORDERS)
        assert ref == got, (profile, ref, got)


# ---------------------------------------------------------------------------
# 3. Innocuité de l'override (ne doit rien laisser derrière lui)
# ---------------------------------------------------------------------------
def test_override_restores_constant_including_on_exception():
    before_v7, before_trend = backtest_phase2_v7.MIN_BORDERS, trend_table.MIN_BORDERS

    with override_min_borders(backtest_phase2_v7, 42):
        assert backtest_phase2_v7.MIN_BORDERS == 42
    assert backtest_phase2_v7.MIN_BORDERS == before_v7

    with pytest.raises(RuntimeError):
        with override_min_borders(backtest_phase2_v7, 99):
            assert backtest_phase2_v7.MIN_BORDERS == 99
            raise RuntimeError("le moteur lève")
    assert backtest_phase2_v7.MIN_BORDERS == before_v7, "constante non restaurée après exception"
    assert trend_table.MIN_BORDERS == before_trend


def test_override_of_one_module_does_not_leak_into_the_other():
    """`trend_table` importe `MIN_BORDERS` depuis v7 au moment de l'import :
    les deux liaisons sont INDÉPENDANTES. Overrider l'une ne doit pas
    modifier l'autre — c'est précisément pourquoi le script les override
    séparément."""
    before_trend = trend_table.MIN_BORDERS
    with override_min_borders(backtest_phase2_v7, 7):
        assert trend_table.MIN_BORDERS == before_trend
    with override_min_borders(trend_table, 7):
        assert backtest_phase2_v7.MIN_BORDERS == BASELINE_MIN_BORDERS
    assert trend_table.MIN_BORDERS == before_trend


def test_override_rejects_a_module_without_the_constant():
    """Garde-fou : viser un module qui n'a pas la constante doit échouer fort,
    pas créer silencieusement un attribut sans effet (ce qui produirait une
    mesure faussement 'insensible')."""
    import position_engine
    with pytest.raises(AttributeError):
        with override_min_borders(position_engine, 4):
            pass


# ---------------------------------------------------------------------------
# 4. Sanité de la mesure
# ---------------------------------------------------------------------------
def test_override_actually_reaches_the_engine():
    """Test CRUCIAL pour l'interprétation : le résultat du chantier est "aucun
    écart entre 2, 3, 4 et 5". Ce constat n'a de valeur que si l'override
    atteint réellement la condition de maturité du moteur. Avec une valeur
    absurdement haute, plus AUCUNE entrée fraîche ne doit être possible ->
    zéro trade. Si ce test passait avec le même nombre de trades qu'à 3, le
    script ne mesurerait rien du tout."""
    h1 = _synthetic_h1(n_days=500, seed=23)
    h4 = _resample(h1, "4h")
    d1 = _resample(h1, "1D")

    base = run_v7_min_borders(h4.copy(), d1.copy(), "MODERE", BASELINE_MIN_BORDERS)
    blocked = run_v7_min_borders(h4.copy(), d1.copy(), "MODERE", 10_000)
    assert base["n_trades"] > 0, "données synthétiques sans aucun trade : test non concluant"
    assert blocked["n_trades"] == 0, blocked


def test_maturity_gate_is_not_binding_over_the_grid_on_real_data():
    """TROUVAILLE DU CHANTIER, verrouillée par un test.

    Sur données réelles (BTC H4), `n_borders` — défini comme le nombre de
    swings bas CONFIRMÉS dans une fenêtre glissante de 15 jours (soit ~90
    bougies H4) — vaut au minimum 5 sur la population des bougies candidates
    à une entrée fraîche v7. Donc AUCUNE valeur de la grille (2..5) ne
    rejette la moindre candidate : le seuil est inerte, et le "0 écart"
    mesuré est une NON-MESURE, pas une preuve de robustesse du choix de 3.

    Ce test échouera si la définition de `n_borders` change (par ex. si la
    catégorie C "définition stricte de la 3ème borne par clôtures" est un
    jour implémentée) — c'est voulu : la conclusion documentée devra alors
    être re-mesurée au lieu d'être reconduite par inertie."""
    from backtest_phase2 import load_h1, resample
    h1 = load_h1("BTCUSDT")
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")

    stats = borders_binding_stats(h4, d1)
    assert stats["n_candidates"] > 100, stats
    for k in MIN_BORDERS_GRID:
        assert stats[f"pct_candidates_mature_{k}"] == 100.0, (k, stats)
    assert stats["first_binding_threshold"] > max(MIN_BORDERS_GRID), stats


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} tests passés")
