"""
Tests pour `risk_aggregation_triple_system.py` -- absent jusqu'ici malgré le
fait que ce fichier calcule LE chiffre le plus cité comme preuve du risque
non plafonné de ce projet (17,00% vs plafond 5% documenté, `RULES_EXTRACTION.md`
§5), et qu'il duplique VOLONTAIREMENT (documenté en tête du fichier, seule
exception au principe "ne réimplémente rien") le gate RANGE de
`unified_protocol.py::_run_core_unified` -- parce que `diversification.py`
n'exporte pas la fermeture interne dont il aurait besoin. Cette duplication a
déjà dû être resynchronisée manuellement TROIS FOIS (EXCES-H4,
pyramidalisation-régime, Conflit MTF, cf. `PLAN.md`) sans qu'aucun test
n'existe pour attraper un oubli de resynchronisation future -- trouvé par
mobilisation multi-agents (bilan directeur, "regard neuf") comme l'angle
mort le plus concret hors fidélité-corpus de ce cycle.

Ne re-teste PAS la logique déjà couverte ailleurs (`process_tranche`/
`process_reverse`/`make_open_tranche_fn` par `test_position_engine.py`,
`step_campaign`/`try_open_campaign` par `test_trend_table.py`, le VRAI gate
RANGE de `unified_protocol.py` par `test_unified_protocol.py`, Pattern A/B
par `test_diversification.py`) -- se concentre sur ce qui est PROPRE à ce
fichier :
  1. Les formules de risque nominal R1 (`_long_risk`/`_short_risk`), migrées
     depuis `_self_check()` (qui restait un script ponctuel, jamais exécuté
     par la suite de tests du projet) vers de vraies assertions pytest-style.
  2. LE GARDE-FOU ANTI-DÉRIVE qui manquait : le gate RANGE dupliqué dans
     `_run_triple_core` doit produire EXACTEMENT le même nombre de clôtures
     que le VRAI moteur (`unified_protocol.run_unified`), sur données
     réelles -- si une future correction de fidélité IP (une 4e, une 5e...)
     n'est PAS répercutée ici, ce test doit le détecter automatiquement,
     plutôt que de laisser le chiffre "17,00%"/"66/112" dériver en silence.
  3. Même garde-fou pour Pattern A/Pattern B (`diversification.py::run_diversified`,
     seule fermeture dupliquée du fichier, `make_open_fn`).
"""
import numpy as np
import pandas as pd
import sys

import pytest

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.core.trend_table import load_volume
from emile.core.diversification import run_diversified
from emile.core.unified_protocol import run_unified, resample_h4_with_volume
from emile.core.risk_aggregation_triple_system import (
    _long_risk, _short_risk, _prepare_triple, _run_triple_core,
)

# --- Fixture réelle (tranche réduite pour la vitesse, réutilisée par les
# tests de cohérence -- assez longue pour produire des trades sur les 4
# sous-moteurs, condition nécessaire pour que ces tests soient non-vacueux) ---
# Chargement protégé : voir test_backtest_phase2_faithful.py pour la raison
# d'être de ce try/except.

_SYMBOL = "BTCUSDT"
try:
    _H1 = load_h1(_SYMBOL)
    _VOL_H1 = load_volume(_SYMBOL)
    _H1_FULL = _H1.merge(_VOL_H1, on="date", how="inner")
    _H1_SMALL = _H1_FULL.iloc[:20000].reset_index(drop=True)
    _DATA_UNAVAILABLE = None
except (FileNotFoundError, ValueError) as e:
    _H1 = _VOL_H1 = _H1_FULL = _H1_SMALL = None
    _DATA_UNAVAILABLE = str(e)

_skip_if_no_data = pytest.mark.skipif(_DATA_UNAVAILABLE is not None, reason=_DATA_UNAVAILABLE or "")

def test_long_risk_formula():
    """R1 (cf. tête de `risk_aggregation_triple_system.py`) : risque = taille
    restante x distance relative au stop, jamais négatif -- cas migrés
    depuis `_self_check()` (jamais exécutés par la suite de tests avant ce
    fichier)."""
    tr = {"entry": 100.0, "stop": 95.0, "remaining": 0.5}
    assert abs(_long_risk(tr) - 0.025) < 1e-9, _long_risk(tr)
    # Stop remonté au-dessus de l'entrée (breakeven+) -> risque nul, jamais négatif.
    tr_be = {"entry": 100.0, "stop": 101.0, "remaining": 0.5}
    assert _long_risk(tr_be) == 0.0
    assert _long_risk(None) == 0.0

def test_short_risk_formula():
    """Même principe, jambe short (`process_reverse`) : risque croît quand
    le stop est AU-DESSUS de l'entrée (position vendeuse)."""
    rp = {"entry": 100.0, "stop": 105.0, "remaining": 0.3}
    assert abs(_short_risk(rp) - 0.015) < 1e-9, _short_risk(rp)
    rp_be = {"entry": 100.0, "stop": 95.0, "remaining": 0.3}
    assert _short_risk(rp_be) == 0.0
    assert _short_risk(None) == 0.0

@_skip_if_no_data
@pytest.mark.data_dependent
def test_triple_gate_matches_real_unified_protocol_on_real_data():
    """GARDE-FOU ANTI-DÉRIVE (cf. tête de fichier) : le gate RANGE dupliqué
    dans `_run_triple_core` doit produire EXACTEMENT le même nombre total de
    clôtures que le VRAI moteur `unified_protocol.run_unified` sur les MÊMES
    données réelles. `run_unified()["n_trades"]` compte les clôtures RANGE
    ET TENDANCE combinées (vérifié directement dans le code : `trades.append`
    est appelé pour les 4 catégories -- reverse tendance, campagne tendance,
    reverse range, tranche range) -- la somme `n_range_trades + n_trend_trades`
    de `_run_triple_core` est donc la quantité directement comparable, pas
    `n_range_trades` seul."""
    h4 = resample_h4_with_volume(_H1_SMALL)
    d1 = resample(_H1_SMALL[["date", "open", "high", "low", "close"]], "1D")
    weekly = resample(_H1_SMALL[["date", "open", "high", "low", "close"]], "W")

    feat_u, h4p = _prepare_triple(_H1_SMALL, use_mtf_gate=True)

    for profile in ("FAIBLE", "MODERE", "AGRESSIF", "TRES_AGRESSIF"):
        res_triple = _run_triple_core(feat_u, h4p, profile)
        res_real = run_unified(h4.copy(), d1.copy(), weekly.copy(), profile, use_mtf_gate=True)
        combined = res_triple["n_range_trades"] + res_triple["n_trend_trades"]
        assert combined == res_real["n_trades"], (
            f"profil {profile} : n_range_trades+n_trend_trades={combined} de "
            f"_run_triple_core diverge de n_trades={res_real['n_trades']} du VRAI "
            "unified_protocol.run_unified -- le gate dupliqué a dérivé d'une "
            "correction de fidélité IP non répercutée ici (cf. tête de fichier)"
        )
    # Garde-fou non-vacueux : au moins un profil doit produire des trades sur
    # cette fenêtre, sinon la comparaison ci-dessus serait triviale (0 == 0).
    assert any(
        _run_triple_core(feat_u, h4p, p)["n_range_trades"] > 0 for p in ("FAIBLE", "MODERE", "AGRESSIF", "TRES_AGRESSIF")
    ), "aucun trade RANGE produit sur cette fenêtre -- comparaison non-vacueuse impossible"

@_skip_if_no_data
@pytest.mark.data_dependent
def test_triple_pattern_a_b_match_real_diversification_on_real_data():
    """Même garde-fou pour Pattern A/Pattern B : `make_open_fn` (dupliqué
    dans `_run_triple_core`, seule fermeture interne de `diversification.py`
    qui n'est pas exportée) doit produire le même nombre de trades que le
    VRAI `diversification.run_diversified` sur les mêmes données réelles."""
    d1 = resample(_H1_SMALL[["date", "open", "high", "low", "close"]], "1D")
    h4_no_vol = resample_h4_with_volume(_H1_SMALL)[["date", "open", "high", "low", "close"]]

    feat_u, h4p = _prepare_triple(_H1_SMALL, use_mtf_gate=True)

    for profile in ("FAIBLE", "MODERE", "AGRESSIF", "TRES_AGRESSIF"):
        res_triple = _run_triple_core(feat_u, h4p, profile, management_profile=profile, enable_pattern_b=True)
        res_real = run_diversified(h4_no_vol.copy(), d1.copy(), management_profile=profile,
                                    use_mtf_gate=True, enable_pattern_b=True)
        assert res_triple["n_div_a_trades"] == res_real["n_trades_pattern_a"], (
            f"profil {profile} : n_div_a_trades={res_triple['n_div_a_trades']} de _run_triple_core "
            f"diverge de n_trades_pattern_a={res_real['n_trades_pattern_a']} du VRAI "
            "diversification.run_diversified -- la fermeture make_open_fn dupliquée a dérivé"
        )
        assert res_triple["n_div_b_trades"] == res_real["n_trades_pattern_b"], (
            f"profil {profile} : n_div_b_trades={res_triple['n_div_b_trades']} de _run_triple_core "
            f"diverge de n_trades_pattern_b={res_real['n_trades_pattern_b']} du VRAI "
            "diversification.run_diversified -- la fermeture make_open_fn dupliquée a dérivé"
        )
    assert any(
        _run_triple_core(feat_u, h4p, p)["n_div_a_trades"] > 0 for p in ("FAIBLE", "MODERE", "AGRESSIF", "TRES_AGRESSIF")
    ), "aucun trade Pattern A produit sur cette fenêtre -- comparaison non-vacueuse impossible"

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
