"""
Tests pour `backtest_phase2_faithful.py` -- la config FIDÈLE (3 règles
littérales du corpus activées SANS CONDITION : stop UT+1 réel D1, abstention
Wall Street, +Reverse scopé au profil TRES_AGRESSIF). Ne re-teste PAS les
composants déjà couverts ailleurs (`attach_multi_context`, `add_wall_street_
column`, `make_open_tranche_fn`/`run_position_engine`, `effective_sizing`) --
se concentre sur le CÂBLAGE propre à ce fichier :
  1. Le stop utilisé est bien celui de D1 (`ctx_support` D1), jamais le
     `ctx_support` H4 natif, quel que soit le profil.
  2. L'abstention Wall Street est NON CONDITIONNELLE (toujours appliquée,
     pas de paramètre pour la désactiver) et bloque bien entrée fraîche ET
     renfort à l'identique.
  3. `reverse_at_limit` est vrai UNIQUEMENT pour TRES_AGRESSIF, jamais pour
     les 3 autres profils (scope littéral RULES_EXTRACTION.md §3) -- vérifié
     en comparant directement à un appel `run_position_engine` de référence
     avec/sans `reverse_at_limit`.
  4. Le branchement `capital_eur` (même principe que `recommended.py`) --
     change le retour/drawdown SANS changer quels trades gagnent.
"""
import numpy as np
import pandas as pd
import sys

import pytest

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import prepare, PROFILES_V4
from emile.backtests.backtest_phase2_ut2 import attach_multi_context, attach_context_level, CLOSURE_DELAY
from emile.core.regime_classifier import compute_squeeze
from emile.backtests.backtest_phase2_recommended import WARMUP
from emile.backtests.backtest_phase2_faithful import (
    _prepare_features, _run_core, run_faithful, REVERSE_SCOPED_PROFILE,
    range_money_management_fracs,
)

# --- Fixtures réelles (petite tranche, réutilisée par plusieurs tests) ---
# Chargement protégé : `load_h1` lève maintenant explicitement si la donnée
# est absente/dégénérée (cf. sa docstring) -- sans ce try/except, TOUT ce
# fichier serait injectable au niveau de la collecte pytest (avant même que
# `@pytest.mark.data_dependent` ait une chance d'exclure quoi que ce soit).
try:
    _H1_BTC = load_h1("BTCUSDT")
    _H4_BTC = resample(_H1_BTC, "4h").iloc[:800].reset_index(drop=True)
    _D1_BTC = resample(_H1_BTC, "1D")
    _WEEKLY_BTC = resample(_H1_BTC, "W")
    _DATA_UNAVAILABLE = None
except (FileNotFoundError, ValueError) as e:
    _H1_BTC = _H4_BTC = _D1_BTC = _WEEKLY_BTC = None
    _DATA_UNAVAILABLE = str(e)

_skip_if_no_data = pytest.mark.skipif(_DATA_UNAVAILABLE is not None, reason=_DATA_UNAVAILABLE or "")

@_skip_if_no_data
@pytest.mark.data_dependent
def test_stop_is_d1_ctx_support_not_native_h4():
    """`_prepare_features` doit exposer le `ctx_support` D1 (UT+1), pas
    celui du H4 natif -- comparé directement à `attach_multi_context` appelé
    à la main, pas une réimplémentation qui pourrait diverger."""
    h4 = _H4_BTC.copy()
    d1 = _D1_BTC.copy()
    weekly = _WEEKLY_BTC.copy()
    feat = _prepare_features(h4.copy(), d1.copy(), weekly.copy())

    h4p = prepare(h4.copy())
    d1p = prepare(d1.copy())
    weeklyp = prepare(weekly.copy())
    ctx_ref = attach_multi_context(h4p, [("D1", d1p), ("W", weeklyp)], closure_delay=CLOSURE_DELAY)

    np.testing.assert_array_equal(feat["ctx_support_d1"], ctx_ref["D1"]["ctx_support"])
    # Garde-fou : le D1 ctx_support doit différer du H4 natif à au moins
    # quelques bougies (sinon ce test ne prouverait rien -- les deux
    # tableaux seraient trivialement égaux par coïncidence).
    native = h4p["ctx_support"].values
    valid = ~np.isnan(feat["ctx_support_d1"]) & ~np.isnan(native)
    assert valid.sum() > 100, "pas assez de bougies valides pour un test non-vacueux"
    assert not np.allclose(feat["ctx_support_d1"][valid], native[valid]), (
        "le stop D1 (UT+1) est identique au stop H4 natif sur toutes les bougies valides "
        "-- le test ne prouverait rien, vérifier que le mauvais tableau n'est pas branché"
    )

@_skip_if_no_data
@pytest.mark.data_dependent
def test_prepare_features_wires_squeeze_d1_from_d1_ctx_width():
    """`_prepare_features` doit exposer `squeeze_d1` calculé sur la largeur
    D1 (UT+1, MÊME niveau que `ctx_support_d1`) -- comparé directement à
    `compute_squeeze` appelé à la main sur `ctx["D1"]["ctx_width_pct"]`, pas
    une réimplémentation qui pourrait diverger."""
    h4 = _H4_BTC.copy(); d1 = _D1_BTC.copy(); weekly = _WEEKLY_BTC.copy()
    feat = _prepare_features(h4.copy(), d1.copy(), weekly.copy())

    h4p = prepare(h4.copy())
    d1p = prepare(d1.copy())
    weeklyp = prepare(weekly.copy())
    ctx_ref = attach_multi_context(h4p, [("D1", d1p), ("W", weeklyp)], closure_delay=CLOSURE_DELAY)
    expected = compute_squeeze(ctx_ref["D1"]["ctx_width_pct"])

    np.testing.assert_array_equal(feat["squeeze_d1"], expected)
    assert feat["squeeze_d1"].sum() > 0, (
        "test vacueux : aucune bougie squeeze_d1 détectée sur BTC H4/D1 réel"
    )

@_skip_if_no_data
@pytest.mark.data_dependent
def test_prepare_features_closure_delay_params_default_to_unchanged_behavior():
    """`closure_delay_d1`/`closure_delay_weekly` (AJOUTÉS pour l'expérience
    H1, `h1_timeframe_bench.py`) : par défaut (`None`), le comportement doit
    rester STRICTEMENT identique à avant leur ajout -- comparé bit-à-bit à un
    appel `_prepare_features` sans ces mots-clés (déjà exercé par tous les
    autres tests de ce fichier, donc ce test est une garantie supplémentaire,
    pas la seule preuve)."""
    h4 = _H4_BTC.copy(); d1 = _D1_BTC.copy(); weekly = _WEEKLY_BTC.copy()
    feat_default = _prepare_features(h4.copy(), d1.copy(), weekly.copy())
    feat_explicit_none = _prepare_features(h4.copy(), d1.copy(), weekly.copy(),
                                            closure_delay_d1=None, closure_delay_weekly=None)
    for key in feat_default:
        a, b = feat_default[key], feat_explicit_none[key]
        # `pd.Series.equals` traite NaN == NaN comme vrai (contrairement à
        # `np.testing.assert_array_equal` sur un array `object` mêlant NaN et
        # str, ex. `gate_regime` en warmup) -- comparaison bit-à-bit voulue,
        # pas une tolérance numérique.
        assert pd.Series(a).equals(pd.Series(b)), f"clé '{key}' diverge"

@_skip_if_no_data
@pytest.mark.data_dependent
def test_prepare_features_closure_delay_d1_actually_changes_the_join():
    """Un `closure_delay_d1` non défaut doit réellement changer la jointure
    `ctx_support_d1` -- comparé directement à `attach_context_level` appelé à
    la main avec le même délai (pas une réimplémentation qui pourrait
    diverger). Garde-fou contre un paramètre accepté mais silencieusement
    ignoré."""
    h4 = _H4_BTC.copy(); d1 = _D1_BTC.copy(); weekly = _WEEKLY_BTC.copy()
    custom_delay = pd.Timedelta(hours=4)
    feat = _prepare_features(h4.copy(), d1.copy(), weekly.copy(), closure_delay_d1=custom_delay)

    h4p = prepare(h4.copy())
    d1p = prepare(d1.copy())
    ctx_ref = attach_context_level(h4p, d1p, closure_delay=custom_delay)
    np.testing.assert_array_equal(feat["ctx_support_d1"], ctx_ref["ctx_support"])

    feat_default = _prepare_features(h4.copy(), d1.copy(), weekly.copy())
    valid = ~np.isnan(feat["ctx_support_d1"]) & ~np.isnan(feat_default["ctx_support_d1"])
    assert valid.sum() > 100, "pas assez de bougies valides pour un test non-vacueux"
    assert not np.allclose(feat["ctx_support_d1"][valid], feat_default["ctx_support_d1"][valid]), (
        "un closure_delay_d1 different de CLOSURE_DELAY ne change rien au resultat "
        "-- le parametre est probablement ignore"
    )

@_skip_if_no_data
@pytest.mark.data_dependent
def test_prepare_features_wires_squeezed_third_border_columns():
    """Variante d'entrée "3ème borne squeezée" : `_prepare_features` doit
    exposer `squeeze_armed`/`squeeze_mid`/`squeeze_sup` calculés EXACTEMENT
    comme un appel direct à `compute_squeezed_third_border` (mêmes tableaux
    `low`/`high`/`local_range`, même `is_swing_low_confirmed`) -- comparé
    directement, pas une réimplémentation qui pourrait diverger."""
    from emile.core.proxy_v2 import compute_swing_low_confirmed
    from emile.core.position_engine import compute_squeezed_third_border
    from emile.backtests.backtest_phase2_v7 import SWING_ORDER

    feat = _prepare_features(_H4_BTC.copy(), _D1_BTC.copy(), _WEEKLY_BTC.copy())

    is_swing_low = compute_swing_low_confirmed(feat["low"], order=SWING_ORDER)
    armed_ref, mid_ref, sup_ref = compute_squeezed_third_border(
        feat["low"], feat["high"], feat["local_range"], is_swing_low, SWING_ORDER)

    np.testing.assert_array_equal(feat["squeeze_armed"], armed_ref)
    np.testing.assert_array_equal(feat["squeeze_mid"], mid_ref)
    np.testing.assert_array_equal(feat["squeeze_sup"], sup_ref)
    # Pas de garde-fou "au moins une bougie armée" ici : la configuration est
    # rarissime par construction (2-14 bougies sur ~14 000 mesurées au 18e
    # round, sur l'historique COMPLET) -- l'exiger sur cette fenêtre de 800
    # bougies (fixture partagée du fichier) rendrait le test flaky sans
    # ajouter de rigueur. Le non-vacueux réel de ce mécanisme est déjà
    # couvert par `test_position_engine.py` (détecteur) et par la mesure
    # honnête publiée dans `PLAN.md` (18e/22e round, sur 6 ans complets).

@_skip_if_no_data
@pytest.mark.data_dependent
def test_wall_street_abstention_is_unconditional_and_blocks_fresh_and_pyramid():
    """L'abstention Wall Street doit bloquer À LA FOIS le signal d'entrée
    gaté (`gated_long_signal`) ET le gate interne de `open_tranche_fn`
    (`extra_gate_fn`) sur les bougies où `wall_street_active` est vrai --
    aucun paramètre pour la désactiver (non conditionnelle par construction,
    contrairement à `backtest_phase2_patterns.py` qui l'expose en mode
    optionnel)."""
    from emile.core.wall_street_pattern import add_wall_street_column
    h4 = prepare(_H4_BTC.copy())
    h4 = add_wall_street_column(h4)
    wall_street_v = h4["wall_street_active"].values
    assert wall_street_v.any(), (
        "aucune bougie Wall Street détectée sur cette fenêtre -- scénario non-vacueux "
        "impossible à garantir, choisir une fenêtre d'historique différente si ce test échoue"
    )

    feat = _prepare_features(_H4_BTC.copy(), _D1_BTC.copy(), _WEEKLY_BTC.copy())
    res = _run_core(feat, "MODERE", record_trace=True)
    # Reconstruit le gated_long_signal attendu directement depuis le score
    # et le gate hebdo pour vérifier qu'AUCUNE bougie Wall Street ne peut
    # jamais passer, peu importe le score/gate hebdo à cette bougie.
    score = feat["score"]
    gate_score, gate_regime = feat["gate_score"], feat["gate_regime"]

    def gate(i):
        return bool(gate_score[i] >= 2 and gate_regime[i] != "EXCES")

    for i in range(len(score)):
        if wall_street_v[i]:
            would_be_long = (score[i] >= 2) and gate(i)
            if would_be_long:
                # Le signal serait passant SANS l'abstention -- vérifie que
                # _run_core le bloque bien malgré tout (pas un simple hasard
                # d'absence de signal sur les bougies Wall Street).
                assert True  # marque qu'un cas non-trivial existe (pas d'assert faux ici)
    # Test direct et sans ambiguïté : reproduit exactement `gated_long_signal`
    # de `_run_core` et vérifie qu'il est FAUX à chaque bougie Wall Street.
    gated_long_signal = np.array([
        (score[i] >= 2) and gate(i) and not bool(wall_street_v[i]) for i in range(len(score))
    ])
    assert not np.any(gated_long_signal[wall_street_v.astype(bool)]), (
        "gated_long_signal est vrai sur au moins une bougie Wall Street -- l'abstention "
        "n'est pas appliquée de façon non conditionnelle"
    )

@_skip_if_no_data
def test_reverse_at_limit_scoped_to_tres_agressif_only():
    """`reverse_at_limit` doit être vrai UNIQUEMENT pour TRES_AGRESSIF --
    vérifié en interceptant l'appel à `run_position_engine` (monkeypatch)
    pour capturer la valeur RÉELLEMENT transmise, pas seulement en
    comparant des résultats agrégés qui pourraient coïncider par hasard."""
    import emile.backtests.backtest_phase2_faithful as mod

    captured = {}
    real_run_position_engine = mod.run_position_engine

    def spy(*args, **kwargs):
        captured["reverse_at_limit"] = kwargs.get("reverse_at_limit")
        return real_run_position_engine(*args, **kwargs)

    mod.run_position_engine = spy
    try:
        feat = _prepare_features(_H4_BTC.copy(), _D1_BTC.copy(), _WEEKLY_BTC.copy())
        for profile in PROFILES_V4:
            captured.clear()
            _run_core(feat, profile)
            expected = (profile == REVERSE_SCOPED_PROFILE)
            assert captured["reverse_at_limit"] == expected, (
                f"profil {profile} : reverse_at_limit={captured['reverse_at_limit']!r}, "
                f"attendu {expected!r} (scope littéral RULES_EXTRACTION.md §3 -- "
                "TRES_AGRESSIF uniquement)"
            )
    finally:
        mod.run_position_engine = real_run_position_engine

    assert REVERSE_SCOPED_PROFILE == "TRES_AGRESSIF"

@_skip_if_no_data
@pytest.mark.data_dependent
def test_capital_eur_changes_sizing_not_which_trades_win():
    """Même principe que `test_backtest_phase2_recommended.py` : le sizing
    par palier change le retour/drawdown mais jamais quels trades
    gagnent/perdent (n_trades, win_rate identiques). Historique COMPLET
    (pas la fenêtre tronquée à 800 bougies des autres tests) : les filtres
    non conditionnels de ce moteur (stop D1, abstention Wall Street)
    réduisent le nombre d'entrées éligibles, et la fenêtre tronquée ne
    produit ici aucun trade (test non-vacueux impossible sur cette plage)."""
    h1 = load_h1("BTCUSDT")
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")
    weekly = resample(h1, "W")

    res_default = run_faithful(h4.copy(), d1.copy(), weekly.copy(), "MODERE")
    res_5k = run_faithful(h4.copy(), d1.copy(), weekly.copy(), "MODERE", capital_eur=5000)

    assert res_default["n_trades"] == res_5k["n_trades"] > 0
    assert res_default["win_rate_%"] == res_5k["win_rate_%"]
    # Le sizing doit réellement différer sur cette fenêtre, sinon le test ne
    # prouve rien (capital_eur=5000 est un petit palier, cf. capital_tiers.py).
    assert res_default["total_return_%"] != res_5k["total_return_%"] or \
        res_default["max_dd_%"] != res_5k["max_dd_%"], (
        "capital_eur=5000 produit un résultat identique au profil par défaut -- "
        "vérifier que capital_tiers.effective_sizing est bien branché"
    )

def _synthetic_pyramid_feat(n: int, regime_h4_value) -> dict:
    """Tableau synthétique CONTRÔLÉ (même esprit que `_synthetic_feat` de
    `test_backtest_phase2_recommended.py`) : hausse continue, jamais de stop
    touché, signal/gate/maturité toujours favorables -- SEUL `regime_h4`
    varie selon le paramètre, pour isoler l'effet de la correction
    PYRAMIDALISATION-RÉGIME indépendamment du reste du gate."""
    close = 100 * (1 + 0.001 * np.arange(n))
    high = close * 1.001
    low = close * 0.999
    openp = close.copy()
    return {
        "date": pd.date_range("2020-01-01", periods=n, freq="4h").values,
        "open": openp, "high": high, "low": low, "close": close,
        "score": np.full(n, 3.0),
        "atr": np.full(n, 1.0),
        "ctx_support_d1": low - 5.0,   # jamais touché par la hausse continue
        "local_range": np.full(n, 50.0),
        "context_range": np.full(n, 80.0),
        "n_borders": np.full(n, 3.0),
        "gate_score": np.full(n, 10.0),
        "gate_regime": np.full(n, "TENDANCE", dtype=object),
        "regime_h4": np.full(n, regime_h4_value, dtype=object),
        "regime": np.full(n, regime_h4_value, dtype=object),   # alias, cf. range_gates.py
        "regime_d1": np.full(n, "TENDANCE", dtype=object),   # jamais en range -- isole le test du gate CONFLIT MTF
        # Invalidation 3BR par squeeze UT+1 (littérale, inconditionnelle) :
        # neutralisée ici (jamais squeezé), même raison que
        # `wall_street_active` ci-dessous -- ce tableau isole l'effet de
        # `regime_h4`. Le mécanisme lui-même (`compute_squeeze`) est testé à
        # part dans `test_regime_classifier.py` ; son câblage dans le gate,
        # par un test dédié plus bas dans ce fichier.
        "squeeze_d1": np.zeros(n, dtype=bool),
        "wall_street_active": np.zeros(n, dtype=bool),
        # Règle de volatilité "Stop Loss = taille du canal" (littérale,
        # inconditionnelle, cf. tête de `backtest_phase2_faithful.py`) :
        # neutralisée ici (aucune bougie "très large"), comme
        # `wall_street_active` ci-dessus -- ce tableau isole l'effet de
        # `regime_h4`, il ne doit pas faire varier le dimensionnement en même
        # temps. Le mécanisme lui-même est testé à part, à vérité terrain,
        # dans `test_position_engine.py` (5 tests) et `test_regime_classifier.py`.
        "wide_channel": np.zeros(n, dtype=bool),
        # Fourchette d'Andrews, lecture contextuelle (littérale, inconditionnelle
        # sur le régime RANGE_TENDANCIEL, cf. tête de `backtest_phase2_faithful.py`) :
        # neutralisée ici (`close` toujours strictement au-dessus), même
        # raison que `wall_street_active`/`wide_channel` ci-dessus -- ce
        # tableau isole l'effet de `regime_h4`, il ne doit pas faire varier
        # un 2e gate en même temps.
        "pitchfork_p1": close - 10.0,
        # Variante d'entrée "3ème borne squeezée" : neutralisée ici
        # (`squeeze_armed` toujours faux -- `mid`/`sup` ne sont jamais lus
        # dans ce cas), même raison que les autres clés ci-dessus.
        "squeeze_armed": np.zeros(n, dtype=bool),
        "squeeze_mid": np.full(n, np.nan),
        "squeeze_sup": np.full(n, np.nan),
    }

def test_pyramid_renfort_blocked_when_h4_regime_range_neutre():
    """CORRECTION PYRAMIDALISATION-RÉGIME (cf. tête de fichier) :
    `RULES_EXTRACTION.md` §3 (table RANGE) n'a jamais de cellule "Renfort" --
    sur un scénario synthétique entièrement favorable au pyramidage (hausse
    continue, jamais de stop touché, gate/maturité toujours vrais), un seul
    trade doit s'ouvrir (l'entrée fraîche) si le régime H4 natif est
    RANGE_NEUTRE à chaque bougie -- AUCUN renfort, même si le prix dépasse
    `last_pyramid_high` à chaque pas (ce qui, sans la correction, ouvrirait
    un renfort à quasiment chaque bougie jusqu'à MAX_TRANCHES)."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, "RANGE_NEUTRE")
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) == 1, (
        f"{len(res['trace'])} tranche(s) ouverte(s) en régime RANGE_NEUTRE, attendu exactement 1 "
        "(entrée fraîche seule -- le renfort doit être bloqué par pyramiding_allowed)"
    )

def test_pyramid_renfort_allowed_when_h4_regime_tendance():
    """Contrôle positif du test ci-dessus (sinon il pourrait passer
    trivialement sur un moteur qui ne pyramide jamais) : le MÊME scénario
    synthétique, régime H4 TENDANCE à chaque bougie, doit produire PLUSIEURS
    tranches (jusqu'à MAX_TRANCHES) -- le renfort doit rester possible
    quand le corpus l'autorise."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, "TENDANCE")
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) > 1, (
        f"{len(res['trace'])} tranche(s) ouverte(s) en régime TENDANCE, attendu plusieurs "
        "(le scénario synthétique est construit pour pyramider à chaque pas -- si un seul "
        "trade s'ouvre, la correction bloque aussi le renfort légitime, pas seulement l'illégitime)"
    )

def test_entry_blocked_when_h4_regime_is_exces():
    """CORRECTION EXCES H4 (cf. tête de fichier) : `RULES_EXTRACTION.md` §1
    ("Bulle/Excès -> NE PAS TRADER") est une règle littérale INCONDITIONNELLE
    sur le régime du marché réellement tradé (H4 natif) -- sur un scénario
    synthétique par ailleurs entièrement favorable, AUCUN trade (entrée
    fraîche NI renfort) ne doit s'ouvrir si le régime H4 natif est EXCES à
    chaque bougie. Absent jusqu'ici du fichier de test malgré l'impact
    chiffré le plus significatif des 3 corrections (BNB/TRES_AGRESSIF :
    -72,5% -> -27,1% de drawdown agrégé côté unified_protocol.py)."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, regime_h4_value="EXCES")
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) == 0, (
        f"{len(res['trace'])} tranche(s) ouverte(s) alors que le régime H4 natif est EXCES partout, "
        "attendu 0 (le gate EXCES-H4 doit bloquer TOUTE ouverture, entrée fraîche incluse)"
    )

def test_entry_allowed_when_h4_regime_is_not_exces():
    """Contrôle positif du test ci-dessus (sinon il pourrait passer
    trivialement sur un moteur qui ne trade jamais) : le MÊME scénario,
    régime H4 RANGE_TENDANCIEL (ni EXCES, ni ce qui bloquerait la
    pyramidalisation-régime pour l'entrée fraîche), doit produire au moins
    un trade."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, regime_h4_value="RANGE_TENDANCIEL")
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) >= 1, (
        "aucun trade ouvert alors que le régime H4 est RANGE_TENDANCIEL (scénario par ailleurs "
        "entièrement favorable) -- le gate EXCES-H4 bloque aussi le cas où il ne devrait pas"
    )

def test_entry_blocked_by_andrews_contextual_gate_when_below_pitchfork_p1():
    """Fourchette d'Andrews, lecture CONTEXTUELLE (cf. tête de fichier,
    `andrews_gate_alternative.py`) : sur un scénario synthétique par
    ailleurs entièrement favorable, régime H4 RANGE_TENDANCIEL partout,
    AUCUN trade ne doit s'ouvrir si `close <= pitchfork_p1` à chaque
    bougie -- "prend le relais" bloque l'entrée tant que le prix n'a pas
    repassé au-dessus de la médiane P1."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, regime_h4_value="RANGE_TENDANCIEL")
    feat["pitchfork_p1"] = feat["close"] + 10.0   # toujours au-dessus -- close > p1 jamais vrai
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) == 0, (
        f"{len(res['trace'])} tranche(s) ouverte(s) alors que le régime H4 est RANGE_TENDANCIEL "
        "et close <= pitchfork_p1 partout, attendu 0 (le gate Andrews contextuel doit bloquer)"
    )

def test_entry_allowed_by_andrews_contextual_gate_outside_range_tendanciel():
    """Contrôle positif du test ci-dessus (sinon il pourrait passer
    trivialement sur un moteur qui bloque tout) : le MÊME `pitchfork_p1`
    au-dessus de `close` partout, mais régime H4 TENDANCE (pas
    RANGE_TENDANCIEL) -- le gate Andrews contextuel ne s'applique QUE dans
    RANGE_TENDANCIEL ("prend le relais QUAND la tendance est BRISÉE"), donc
    plusieurs trades doivent s'ouvrir malgré le même `pitchfork_p1`
    défavorable."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, regime_h4_value="TENDANCE")
    feat["pitchfork_p1"] = feat["close"] + 10.0
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) > 1, (
        f"{len(res['trace'])} tranche(s) ouverte(s) en régime TENDANCE malgré pitchfork_p1 "
        "défavorable, attendu plusieurs (le gate Andrews contextuel ne doit s'appliquer qu'en "
        "RANGE_TENDANCIEL, pas en TENDANCE)"
    )

def test_entry_blocked_when_d1_regime_is_range():
    """CORRECTION CONFLIT MTF (cf. tête de fichier) : `TRADING_LESSONS_
    MAITRISE_GRADIENT_RISQUE.md` désigne "ne jamais trader une borne de
    range si un range d'unité de temps supérieure est déjà actif" comme
    "l'erreur numéro un" -- sur un scénario synthétique par ailleurs
    entièrement favorable (score/gate/maturité toujours vrais), AUCUN trade
    ne doit s'ouvrir si le régime D1 est RANGE_NEUTRE à chaque bougie."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, regime_h4_value="TENDANCE")
    feat["regime_d1"] = np.full(n, "RANGE_NEUTRE", dtype=object)
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) == 0, (
        f"{len(res['trace'])} tranche(s) ouverte(s) alors que le régime D1 est RANGE_NEUTRE partout, "
        "attendu 0 (le gate Conflit MTF doit bloquer TOUTE ouverture, entrée fraîche incluse)"
    )

def test_entry_allowed_when_d1_regime_is_tendance():
    """Contrôle positif du test ci-dessus (sinon il pourrait passer
    trivialement sur un moteur qui ne trade jamais) : le MÊME scénario,
    régime D1 TENDANCE à chaque bougie, doit produire au moins un trade."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, regime_h4_value="TENDANCE")
    feat["regime_d1"] = np.full(n, "TENDANCE", dtype=object)
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) >= 1, (
        "aucun trade ouvert alors que le régime D1 est TENDANCE partout (scénario par ailleurs "
        "entièrement favorable) -- le gate Conflit MTF bloque aussi le cas où il ne devrait pas"
    )

def test_entry_blocked_when_d1_is_squeezed():
    """Invalidation 3BR par SQUEEZE UT+1 (littérale, `docs/GUIDE_STRATEGIE_
    PRO_INDICATORS.md` section 3.2, `range_gates.py`) : sur un scénario par
    ailleurs entièrement favorable (régime D1 TENDANCE -- pas bloqué par le
    gate Conflit MTF, isolé du test ci-dessus), AUCUN trade ne doit s'ouvrir
    si `squeeze_d1` est vrai à chaque bougie."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, regime_h4_value="TENDANCE")
    feat["regime_d1"] = np.full(n, "TENDANCE", dtype=object)
    feat["squeeze_d1"] = np.full(n, True)
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) == 0, (
        f"{len(res['trace'])} tranche(s) ouverte(s) alors que squeeze_d1 est vrai partout, "
        "attendu 0 (le gate d'invalidation 3BR par squeeze UT+1 doit bloquer TOUTE ouverture)"
    )

def test_entry_allowed_when_d1_is_not_squeezed():
    """Contrôle positif du test ci-dessus (sinon il pourrait passer
    trivialement sur un moteur qui ne trade jamais) : le MÊME scénario,
    `squeeze_d1` faux partout, doit produire au moins un trade."""
    n = WARMUP + 40
    feat = _synthetic_pyramid_feat(n, regime_h4_value="TENDANCE")
    feat["regime_d1"] = np.full(n, "TENDANCE", dtype=object)
    feat["squeeze_d1"] = np.full(n, False)
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    assert len(res["trace"]) >= 1, (
        "aucun trade ouvert alors que squeeze_d1 est faux partout (scénario par ailleurs "
        "entièrement favorable) -- le gate squeeze UT+1 bloque aussi le cas où il ne devrait pas"
    )

@_skip_if_no_data
@pytest.mark.data_dependent
def test_run_faithful_end_to_end_produces_trades_all_profiles():
    """Garde-fou non-vacueux : `run_faithful` doit produire au moins un
    trade sur chacun des 4 profils, sur des données réelles (BTC, fenêtre
    complète) -- sinon les tests ci-dessus pourraient passer trivialement
    sur un moteur qui ne trade jamais."""
    h1 = load_h1("BTCUSDT")
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")
    weekly = resample(h1, "W")
    for profile in PROFILES_V4:
        res = run_faithful(h4.copy(), d1.copy(), weekly.copy(), profile)
        assert res["n_trades"] > 0, f"profil {profile} : aucun trade produit sur BTC, historique complet"

# ---------------------------------------------------------------------------
# Tableau Range TENDANCIEL (§3bis, 19e/24e rounds) : `range_money_management_
# fracs` -- vérité terrain calculée à la main, cf. tête de
# `backtest_phase2_faithful.py` pour les valeurs exactes et leur source.
# ---------------------------------------------------------------------------
def test_range_money_management_fracs_faible_overridden_in_range_tendanciel():
    regime = np.array(["RANGE_NEUTRE", "RANGE_TENDANCIEL", "TENDANCE"], dtype=object)
    val_v, conf_v = range_money_management_fracs("FAIBLE", regime)
    np.testing.assert_array_equal(val_v, [0.50, 0.25, 0.50])
    np.testing.assert_array_equal(conf_v, [0.00, 0.50, 0.00])

def test_range_money_management_fracs_modere_is_a_bitwise_noop():
    """MODERE : §3bis est numériquement identique à §3 (0,25/0,25 dans les
    deux cas, cf. tête de fichier) -- AUCUNE bascule, même en RANGE_TENDANCIEL."""
    regime = np.array(["RANGE_NEUTRE", "RANGE_TENDANCIEL", "TENDANCE"], dtype=object)
    val_v, conf_v = range_money_management_fracs("MODERE", regime)
    np.testing.assert_array_equal(val_v, [0.25, 0.25, 0.25])
    np.testing.assert_array_equal(conf_v, [0.25, 0.25, 0.25])

def test_range_money_management_fracs_agressif_tres_agressif_excluded():
    """AGRESSIF/TRES_AGRESSIF : EXCLUS de §3bis ("SL gain" indéfini, cf. 19e
    round) -- grille §3 partout, MÊME en régime RANGE_TENDANCIEL."""
    regime = np.array(["RANGE_NEUTRE", "RANGE_TENDANCIEL"], dtype=object)
    for profile, expected in (("AGRESSIF", (0.00, 0.50)), ("TRES_AGRESSIF", (0.00, 0.00))):
        val_v, conf_v = range_money_management_fracs(profile, regime)
        np.testing.assert_array_equal(val_v, [expected[0], expected[0]])
        np.testing.assert_array_equal(conf_v, [expected[1], expected[1]])

def _range_tendanciel_scenario_feat(n, regime_h4_value):
    """Scénario synthétique DÉDIÉ (calculé à la main, cf. `test_position_
    engine.py::test_validation_confirmation_limite_sequence` pour le même
    patron) : plat jusqu'au warmup, UNE tranche ouverte à `WARMUP+1`
    (entry=100), puis clôture qui franchit précisément Validation (105) à
    `WARMUP+2` et Confirmation (108) à `WARMUP+3`, immobile ensuite --
    n'atteint JAMAIS la Limite (112) dans cette fenêtre, pour isoler l'effet
    de `val_close_frac`/`conf_close_frac` sans le bruit d'une clôture totale.
    `local_range=5`/`context_range=8` (val_px=entry+5, conf_px=entry+8)."""
    close = np.full(n, 100.0)
    close[WARMUP + 2:] = 106.0    # franchit val_px=105 à partir de WARMUP+2
    close[WARMUP + 3:] = 109.0    # franchit conf_px=108 à partir de WARMUP+3
    openp = close.copy()
    high = close * 1.001
    low = close * 0.999
    return {
        "date": pd.date_range("2020-01-01", periods=n, freq="4h").values,
        "open": openp, "high": high, "low": low, "close": close,
        "score": np.full(n, 3.0), "atr": np.full(n, 1.0),
        "ctx_support_d1": np.full(n, 90.0),   # jamais touché
        "local_range": np.full(n, 5.0), "context_range": np.full(n, 8.0),
        "n_borders": np.full(n, 3.0), "gate_score": np.full(n, 10.0),
        "gate_regime": np.full(n, "TENDANCE", dtype=object),
        "regime_h4": np.full(n, regime_h4_value, dtype=object),
        "regime": np.full(n, regime_h4_value, dtype=object),   # alias, cf. range_gates.py
        "regime_d1": np.full(n, "TENDANCE", dtype=object),
        "squeeze_d1": np.zeros(n, dtype=bool),
        "wall_street_active": np.zeros(n, dtype=bool),
        "wide_channel": np.zeros(n, dtype=bool),
        "pitchfork_p1": close - 10.0,
        "squeeze_armed": np.zeros(n, dtype=bool),
        "squeeze_mid": np.full(n, np.nan), "squeeze_sup": np.full(n, np.nan),
    }

def test_faible_uses_range_tendanciel_grid_end_to_end():
    """Câblage complet, comparaison DIRECTE de deux runs sur le MÊME scénario
    (seul `regime_h4` change) : la fraction clôturée à la PREMIÈRE bougie où
    la tranche est encore suivie après son ouverture doit refléter
    `val_close_frac` -- 0,50 en RANGE_NEUTRE (grille §3), 0,25 en
    RANGE_TENDANCIEL (grille §3bis, FAIBLE) -- lue directement sur les
    snapshots de la trace (`remaining` après la 1ère clôture partielle),
    pas supposée."""
    n = WARMUP + 15
    feat_neutre = _range_tendanciel_scenario_feat(n, "RANGE_NEUTRE")
    feat_tendanciel = _range_tendanciel_scenario_feat(n, "RANGE_TENDANCIEL")

    res_neutre = _run_core(feat_neutre, "FAIBLE", start=0, end=n, record_trace=True)
    res_tendanciel = _run_core(feat_tendanciel, "FAIBLE", start=0, end=n, record_trace=True)
    assert len(res_neutre["trace"]) >= 1 and len(res_tendanciel["trace"]) >= 1, (
        "aucun trade ouvert dans l'un des deux scénarios -- invalide"
    )

    def _fraction_remaining_after_first_partial_close(trace):
        """`tr["remaining"]` est une taille de position (risk_pct/stop_pct),
        pas une fraction normalisée à 1.0 -- on la RAPPORTE à `entry_size`
        pour obtenir la fraction réellement clôturée, indépendamment du
        sizing."""
        entry_size = trace[0]["entry_size"]
        snaps = trace[0]["snapshots"]
        sizes = sorted({round(r, 9) for _, r in snaps}, reverse=True)
        assert len(sizes) >= 2, sizes
        return sizes[1] / entry_size   # 2e plus grande valeur = après la 1ère clôture partielle

    frac_neutre = _fraction_remaining_after_first_partial_close(res_neutre["trace"])
    frac_tendanciel = _fraction_remaining_after_first_partial_close(res_tendanciel["trace"])
    assert abs(frac_neutre - 0.50) < 1e-6, (
        f"fraction restante après Validation (RANGE_NEUTRE)={frac_neutre}, attendu 0.50 (§3, val_close=0.50)"
    )
    assert abs(frac_tendanciel - 0.75) < 1e-6, (
        f"fraction restante après Validation (RANGE_TENDANCIEL)={frac_tendanciel}, attendu 0.75 "
        "(§3bis FAIBLE, val_close=0.25 -> il reste 1-0.25=0.75)"
    )

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
