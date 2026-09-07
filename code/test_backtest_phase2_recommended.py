"""
Tests pour `backtest_phase2_recommended.py` -- LA config recommandée
(synthèse, vague 4 du plan d'autonomie 8h, PLAN.md). Ne re-teste PAS les
composants déjà couverts ailleurs (proxy_v2.py, position_engine.py,
regime_classifier.py, attach_multi_context de backtest_phase2_ut2.py) --
se concentre sur la logique NON TRIVIALE introduite ici :
  1. Le bypass du gate MTF (`use_mtf_gate=False`) -- doit neutraliser le
     gate sans jamais se comparer à NaN (ce qui donnerait silencieusement
     `False`, l'inverse de l'effet voulu).
  2. Le gate MTF actif doit être identique à un appel direct de
     `attach_multi_context` (pas une réimplémentation qui pourrait diverger).
  3. Le décalage `local_warmup = max(0, WARMUP - start)` -- condition
     nécessaire pour que le walk-forward annuel (`walkforward_recommended.py`)
     ne réintroduise pas un warmup artificiel à chaque découpage. C'est la
     seule logique de sélection réellement nouvelle de ce fichier (le reste
     réutilise `run_v7`/`run_ut2` presque à l'identique).
  4. Le branchement `capital_eur` (décision #9, capital par palier) --
     doit changer le retour/drawdown SANS changer quels trades gagnent
     (n_trades, win_rate identiques), cohérent avec
     COUVERTURE_ENSEIGNEMENTS.md ("le sizing ne change pas quels trades
     gagnent ou perdent").
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")

from backtest_phase2 import load_h1, resample
from backtest_phase2_v7 import prepare
from backtest_phase2_ut2 import attach_multi_context, CLOSURE_DELAY
from backtest_phase2_recommended import (
    _prepare_features, _run_core, run_recommended, WARMUP,
)

# --- Fixtures réelles (petites tranches, réutilisées par plusieurs tests) ---

_H1_BTC = load_h1("BTCUSDT")
_H4_BTC = resample(_H1_BTC, "4h").iloc[:800].reset_index(drop=True)
_WEEKLY_BTC = resample(_H1_BTC, "W")


def test_mtf_gate_bypass_never_compares_to_nan():
    """use_mtf_gate=False doit neutraliser le gate (toujours vrai), pas le
    rendre NaN -- une comparaison `NaN >= 2` retournerait silencieusement
    False en numpy, l'inverse exact de l'effet recherché (neutraliser =
    toujours passant, pas toujours bloquant)."""
    feat = _prepare_features(_H4_BTC.copy(), _WEEKLY_BTC.copy(), use_mtf_gate=False)
    assert np.all(feat["gate_score"] == np.inf), "gate_score doit être +inf partout (jamais NaN) quand le gate est désactivé"
    assert np.all(feat["gate_regime"] == "RANGE_NEUTRE"), "gate_regime doit être neutre (jamais EXCES) quand le gate est désactivé"
    # Et le gate lui-même (score>=2 ET regime!=EXCES) doit être vrai à CHAQUE bougie
    always_true = (feat["gate_score"] >= 2) & (feat["gate_regime"] != "EXCES")
    assert np.all(always_true), "le gate désactivé doit toujours laisser passer, sans exception"


def test_mtf_gate_active_matches_attach_multi_context_directly():
    """Le gate actif (use_mtf_gate=True) doit être EXACTEMENT ce que
    renvoie attach_multi_context appelé directement -- pas une
    réimplémentation parallèle qui pourrait diverger silencieusement."""
    h4 = _H4_BTC.copy()
    weekly = _WEEKLY_BTC.copy()
    feat = _prepare_features(h4.copy(), weekly.copy(), use_mtf_gate=True)

    h4_prepared = prepare(h4.copy())
    weekly_prepared = prepare(weekly.copy())
    ctx = attach_multi_context(h4_prepared, [("H", weekly_prepared)], closure_delay=CLOSURE_DELAY)

    assert np.array_equal(
        np.nan_to_num(feat["gate_score"].astype(float), nan=-999.0),
        np.nan_to_num(ctx["H"]["score"].astype(float), nan=-999.0),
    ), "gate_score de _prepare_features diverge d'un appel direct à attach_multi_context"
    assert list(feat["gate_regime"]) == list(ctx["H"]["regime"]), \
        "gate_regime de _prepare_features diverge d'un appel direct à attach_multi_context"


def _synthetic_feat(n: int, favorable_from: int = 0) -> dict:
    """Tableau synthétique CONTRÔLÉ (pas de proxy_v2/regime réels) pour
    isoler la logique de découpage/warmup de _run_core, indépendamment du
    calcul du signal. Toutes les entrées sont favorables (gate toujours
    vrai, structure toujours mature) à partir de l'indice `favorable_from`,
    ce qui permet de prédire EXACTEMENT le premier index d'ouverture."""
    close = 100 * (1 + 0.001 * np.arange(n))  # légère hausse continue, jamais de stop touché
    high = close * 1.001
    low = close * 0.999
    openp = close.copy()
    score = np.full(n, 3.0)
    score[:favorable_from] = 0.0
    return {
        "date": pd.date_range("2020-01-01", periods=n, freq="4h").values,
        "open": openp, "high": high, "low": low, "close": close,
        "score": score,
        "atr": np.full(n, 1.0),
        "ctx_support": low - 5.0,   # stop bien en dessous, jamais touché par la hausse continue
        "local_range": np.full(n, 50.0),
        "context_range": np.full(n, 80.0),
        "n_borders": np.full(n, 3.0),
        "gate_score": np.full(n, 10.0),
        "gate_regime": np.full(n, "TENDANCE", dtype=object),
    }


def test_local_warmup_matches_absolute_warmup_when_not_sliced():
    """Sans découpage (start=0), le premier trade ne doit jamais s'ouvrir
    avant l'indice absolu WARMUP+1 -- comportement hérité tel quel de
    backtest_phase2_v7.py::run_v7 (`i > warmup`)."""
    n = WARMUP + 40
    feat = _synthetic_feat(n)
    res = _run_core(feat, "MODERE", start=0, end=n, record_trace=True)
    # NB : la hausse synthétique continue ne clôture jamais aucune tranche
    # avant la fin de la série (ni stop ni cible atteints) -- `n_trades`
    # (qui ne compte que les tranches CLÔTURÉES) reste donc 0 ici par
    # construction ; `trace` capture les OUVERTURES quel que soit leur
    # statut de clôture, c'est ce qu'on veut isoler ici.
    assert len(res["trace"]) >= 1, "aucune tranche ouverte sur un scénario pourtant entièrement favorable"
    first_open_i = min(t["open_i"] for t in res["trace"])
    assert first_open_i == WARMUP + 1, (
        f"premier trade ouvert à i={first_open_i}, attendu exactement WARMUP+1={WARMUP + 1} "
        f"(garde-fou 'i > warmup' hérité de run_v7)"
    )


def test_local_warmup_offset_reproduces_same_absolute_timing_when_sliced_at_boundary():
    """Propriété clé introduite par ce fichier (walk-forward annuel) :
    découper exactement à la frontière du warmup (start=WARMUP) doit
    ouvrir le premier trade au MÊME instant absolu que sans découpage --
    ni avant (ce qui violerait le warmup), ni après (ce qui réintroduirait
    un faux warmup à chaque découpage annuel, le bug que ce mécanisme
    évite explicitement)."""
    n = WARMUP + 40
    feat_full = _synthetic_feat(n)
    res_full = _run_core(feat_full, "MODERE", start=0, end=n, record_trace=True)
    first_open_absolute_full = min(t["open_i"] for t in res_full["trace"])

    res_sliced = _run_core(feat_full, "MODERE", start=WARMUP, end=n, record_trace=True)
    assert len(res_sliced["trace"]) >= 1
    first_open_local_sliced = min(t["open_i"] for t in res_sliced["trace"])
    first_open_absolute_sliced = WARMUP + first_open_local_sliced

    assert first_open_absolute_sliced == first_open_absolute_full, (
        f"découper à start=WARMUP change l'instant absolu du premier trade "
        f"({first_open_absolute_sliced} != {first_open_absolute_full}) -- "
        f"régression du mécanisme local_warmup"
    )


def test_slice_deep_past_warmup_opens_on_first_available_bar():
    """Une tranche qui démarre BIEN après le warmup réel (cas typique du
    walk-forward : une année qui n'est pas la première de l'historique)
    ne doit PAS attendre WARMUP bougies de plus avant de pouvoir trader --
    sinon chaque année perdrait ~12 jours de signal pour rien, le piège
    explicitement évité (cf. docstring de backtest_phase2_recommended.py)."""
    n = 300
    start = WARMUP + 50
    feat = _synthetic_feat(n)
    res = _run_core(feat, "MODERE", start=start, end=n, record_trace=True)
    assert len(res["trace"]) >= 1
    first_open_local = min(t["open_i"] for t in res["trace"])
    assert first_open_local == 1, (
        f"premier trade local ouvert à i={first_open_local}, attendu i=1 "
        f"(aucun warmup ne doit être réappliqué -- start={start} est déjà "
        f"bien après WARMUP={WARMUP} dans l'historique complet)"
    )


def test_capital_eur_changes_return_not_which_trades_win():
    """Cf. COUVERTURE_ENSEIGNEMENTS.md, note 'Capital par palier' : le
    sizing par palier module le retour/drawdown, PAS quels trades gagnent
    ou perdent -- n_trades et win_rate doivent rester IDENTIQUES entre
    capital_eur=None (profil de base, équivalent PALIER_2/pas de
    modulation) et un capital de PALIER_1 (<10k€, multiplicateur x1.25),
    seul le retour total doit différer."""
    h4 = _H4_BTC.copy()
    weekly = _WEEKLY_BTC.copy()
    base = run_recommended(h4.copy(), weekly.copy(), "MODERE", capital_eur=None)
    tier1 = run_recommended(h4.copy(), weekly.copy(), "MODERE", capital_eur=5_000.0)

    assert base["n_trades"] == tier1["n_trades"], "le nombre de trades ne doit pas dépendre du capital"
    assert base["win_rate_%"] == tier1["win_rate_%"], "le win rate ne doit pas dépendre du capital (même trades)"
    if base["n_trades"] > 0:
        assert tier1["total_return_%"] != base["total_return_%"], (
            "le retour total DEVRAIT différer : PALIER_1 applique un multiplicateur x1.25 au risk_pct"
        )


def test_reverse_at_limit_default_off_matches_no_reverse_call():
    """`reverse_at_limit=False` (défaut) doit produire EXACTEMENT le même
    résultat qu'un appel qui ne passe pas ce paramètre du tout -- garde-fou
    de non-régression basique sur la signature de `run_recommended`."""
    h4 = _H4_BTC.copy()
    weekly = _WEEKLY_BTC.copy()
    explicit_off = run_recommended(h4.copy(), weekly.copy(), "TRES_AGRESSIF", reverse_at_limit=False)
    implicit_off = run_recommended(h4.copy(), weekly.copy(), "TRES_AGRESSIF")
    assert explicit_off == implicit_off


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
    print(f"\n{len(tests) - failures}/{len(tests)} tests passent")
    raise SystemExit(1 if failures else 0)
