"""
Tests pour `emile/core/trade_confidence.py` (score de confluence "confiance
de trade", cf. tête de fichier pour les 3 conditions H-Confidence-1 et le
mapping H-Confidence-4). Scénarios à vérité terrain calculée à la main --
même discipline que `test_wide_channel`/`test_squeezed_third_border`.
"""
import numpy as np
import pytest

from emile.core.trade_confidence import (
    compute_range_confidence_score, confidence_to_risk_pct, CONFIDENCE_RISK_PCT,
)

MIN_BORDERS = 3


def test_score_all_three_conditions_true_is_3():
    regime_d1 = np.array(["TENDANCE"], dtype=object)   # C1 : pas de conflit MTF
    n_borders = np.array([MIN_BORDERS])                # C2 : structure mature
    fib_favorable = np.array([True])                   # C3 : zone spéculative
    score = compute_range_confidence_score(regime_d1, n_borders, fib_favorable)
    assert score[0] == 3


def test_score_zero_conditions_true_is_0():
    regime_d1 = np.array(["RANGE_NEUTRE"], dtype=object)   # C1 faux (conflit MTF actif)
    n_borders = np.array([MIN_BORDERS - 1])                # C2 faux
    fib_favorable = np.array([False])                      # C3 faux
    score = compute_range_confidence_score(regime_d1, n_borders, fib_favorable)
    assert score[0] == 0


def test_score_counts_exactly_how_many_conditions_hold():
    # Exactement 2 vraies (C1, C3), C2 fausse.
    regime_d1 = np.array(["TENDANCE"], dtype=object)
    n_borders = np.array([MIN_BORDERS - 1])
    fib_favorable = np.array([True])
    score = compute_range_confidence_score(regime_d1, n_borders, fib_favorable)
    assert score[0] == 2


def test_score_is_nan_when_any_input_is_nan_not_treated_as_false():
    """Garde-fou explicite (cf. tête de fichier) : une entrée manquante ne
    doit JAMAIS être traitée comme 'condition non réunie' -- le score
    entier doit rester NaN."""
    regime_d1 = np.array([np.nan], dtype=object)
    n_borders = np.array([MIN_BORDERS])
    fib_favorable = np.array([True])
    score = compute_range_confidence_score(regime_d1, n_borders, fib_favorable)
    assert score[0] != score[0]   # NaN

    regime_d1_2 = np.array(["TENDANCE"], dtype=object)
    n_borders_2 = np.array([np.nan])
    score_2 = compute_range_confidence_score(regime_d1_2, n_borders_2, fib_favorable)
    assert score_2[0] != score_2[0]


def test_score_vectorized_over_multiple_bars_independent():
    # Bar 0 : C1=vrai(TENDANCE), C2=vrai(n_borders>=MIN), C3=vrai -> 3
    # Bar 1 : C1=faux(RANGE_NEUTRE), C2=vrai, C3=vrai -> 2
    # Bar 2 : C1=vrai(TENDANCE), C2=faux(n_borders<MIN), C3=vrai -> 2
    regime_d1 = np.array(["TENDANCE", "RANGE_NEUTRE", "TENDANCE"], dtype=object)
    n_borders = np.array([MIN_BORDERS, MIN_BORDERS, MIN_BORDERS - 1])
    fib_favorable = np.array([True, True, True])
    score = compute_range_confidence_score(regime_d1, n_borders, fib_favorable)
    np.testing.assert_array_equal(score, [3, 2, 2])


def test_confidence_to_risk_pct_abstention_below_2():
    assert confidence_to_risk_pct(0) is None
    assert confidence_to_risk_pct(1) is None


def test_confidence_to_risk_pct_standard_and_carton_plein():
    assert confidence_to_risk_pct(2) == pytest.approx(0.02)
    assert confidence_to_risk_pct(3) == pytest.approx(0.05)


def test_confidence_to_risk_pct_nan_is_abstention_not_default_exposure():
    assert confidence_to_risk_pct(float("nan")) is None


def test_confidence_risk_pct_map_matches_profiles_v4_anchors():
    """H-Confidence-4 (cf. tête de fichier) : les 2 chiffres actifs (0,02 et
    0,05) doivent être les MÊMES que MODERE/TRES_AGRESSIF de PROFILES_V4 --
    des ancres déjà légitimées par le corpus, pas des valeurs inventées ici."""
    from emile.backtests.backtest_phase2_v7 import PROFILES_V4
    assert CONFIDENCE_RISK_PCT[2] == PROFILES_V4["MODERE"]["risk_pct"]
    assert CONFIDENCE_RISK_PCT[3] == PROFILES_V4["TRES_AGRESSIF"]["risk_pct"]
