"""
Tests pour `emile/core/neuneu_borne.py` -- mécanisme "Borne Neuneu" (47e
round, `docs/PLAN.md`), même discipline que `test_neuneu_repli.py` (arrays
synthétiques fabriqués à la main, résultat attendu calculé AVANT
d'exécuter le code).
"""
import numpy as np
import pandas as pd
import pytest

from emile.core.neuneu_borne import (
    _borne_neuneu_state_machine, process_borne_neuneu_tranche, run_borne_neuneu,
    NEUNEU_FIB_76, NEUNEU_CONFIRMATION_CLOSE_FRAC,
)
from emile.core.neuneu_repli import NEUNEU_RISK_PCT
import emile.core.neuneu_borne as neuneu_borne_mod

NAN = np.nan


def _nan_arr(n):
    return np.full(n, NAN)


# ---------------------------------------------------------------------------
# _borne_neuneu_state_machine
# ---------------------------------------------------------------------------

def test_state_machine_fires_when_beyond_context_and_fib76():
    """Canal de contexte FIXE [0, 100] (fib76=76) : clôture à 80 (>76 ET
    >100 ? NON -- 80 < 100 donc PAS au-delà du contexte) ne doit PAS
    déclencher ; clôture à 105 (>100 ET >76) doit déclencher au bar suivant."""
    n = 5
    close = np.array([50, 80, 105, 50, 50], dtype=float)
    ctx_low = np.full(n, 0.0); ctx_high = np.full(n, 100.0)
    local_low = np.full(n, 40.0); local_high = np.full(n, 60.0)

    out = _borne_neuneu_state_machine(close, ctx_low, ctx_high, local_low, local_high)
    assert out["short_signal"][2] == False, "close[1]=80 < ctx_high=100 -- ne doit pas déclencher à i=2"
    assert out["short_signal"][3] == True, "close[2]=105 > ctx_high=100 ET > fib76=76 -- déclenche à i=3"
    assert out["context_range"][3] == 100.0
    assert out["ctx_high_ref"][3] == 100.0
    assert out["ctx_low_ref"][3] == 0.0
    assert out["local_range"][3] == 20.0
    assert out["local_low_ref"][3] == 40.0

def test_state_machine_close_above_context_but_below_fib76_never_fires():
    """Cas impossible en pratique (fib76 < ctx_high toujours) mais vérité
    terrain directe de la condition ET : les 2 clauses sont bien
    CONJONCTIVES (`and`), pas seulement la 1ère."""
    n = 4
    close = np.array([50, 50, 50, 50], dtype=float)
    ctx_low = np.full(n, 0.0); ctx_high = np.full(n, 100.0)
    local_low = _nan_arr(n); local_high = _nan_arr(n)
    out = _borne_neuneu_state_machine(close, ctx_low, ctx_high, local_low, local_high)
    assert not out["short_signal"].any()

def test_state_machine_refires_repeatedly_no_open_position_state_tracked():
    """`_borne_neuneu_state_machine` est un GATE DIRECT (H-Borne-1), pas une
    machine à états à mémoire -- il signale À CHAQUE bougie où la condition
    est vraie (c'est `run_borne_neuneu`, pas cette fonction, qui empêche une
    2e ouverture tant qu'une tranche est déjà en cours)."""
    n = 5
    close = np.array([50, 105, 110, 120, 50], dtype=float)
    ctx_low = np.full(n, 0.0); ctx_high = np.full(n, 100.0)
    local_low = _nan_arr(n); local_high = _nan_arr(n)
    out = _borne_neuneu_state_machine(close, ctx_low, ctx_high, local_low, local_high)
    assert out["short_signal"][2] and out["short_signal"][3] and out["short_signal"][4]

def test_state_machine_nan_context_bounds_never_signals():
    n = 4
    close = np.array([200, 200, 200, 200], dtype=float)
    ctx_low = _nan_arr(n); ctx_high = _nan_arr(n)
    local_low = _nan_arr(n); local_high = _nan_arr(n)
    out = _borne_neuneu_state_machine(close, ctx_low, ctx_high, local_low, local_high)
    assert not out["short_signal"].any()

def test_state_machine_regime_gate_blocks_tendance_and_exces():
    """H-Borne-6 : quand `regime` est fourni, le gate ne doit s'exercer QUE
    sur RANGE_NEUTRE/RANGE_TENDANCIEL -- TENDANCE et EXCES bloquent, même
    si les conditions de prix seraient par ailleurs satisfaites."""
    n = 6
    close = np.array([50, 105, 105, 105, 105, 105], dtype=float)
    ctx_low = np.full(n, 0.0); ctx_high = np.full(n, 100.0)
    local_low = _nan_arr(n); local_high = _nan_arr(n)
    regime = np.array(["RANGE_NEUTRE", "TENDANCE", "EXCES", "RANGE_TENDANCIEL",
                       "RANGE_NEUTRE", "RANGE_NEUTRE"], dtype=object)
    out = _borne_neuneu_state_machine(close, ctx_low, ctx_high, local_low, local_high, regime=regime)
    # close[j] > 100 vrai pour j=1,2,3,4 -- mais seul j=3 (RANGE_TENDANCIEL) et j=4 (RANGE_NEUTRE)
    # doivent déclencher (à i=4 et i=5) ; j=1 (TENDANCE) et j=2 (EXCES) doivent être bloqués.
    assert not out["short_signal"][2], "j=1 est en régime TENDANCE -- doit être bloqué"
    assert not out["short_signal"][3], "j=2 est en régime EXCES -- doit être bloqué"
    assert out["short_signal"][4], "j=3 est en régime RANGE_TENDANCIEL -- doit déclencher"
    assert out["short_signal"][5], "j=4 est en régime RANGE_NEUTRE -- doit déclencher"

def test_state_machine_regime_none_means_no_filter_unchanged_behavior():
    """Non-régression explicite : `regime=None` (défaut) doit reproduire
    EXACTEMENT le comportement d'avant l'ajout de ce paramètre."""
    n = 4
    close = np.array([50, 105, 105, 105], dtype=float)
    ctx_low = np.full(n, 0.0); ctx_high = np.full(n, 100.0)
    local_low = _nan_arr(n); local_high = _nan_arr(n)
    out_none = _borne_neuneu_state_machine(close, ctx_low, ctx_high, local_low, local_high)
    out_explicit_none = _borne_neuneu_state_machine(close, ctx_low, ctx_high, local_low, local_high,
                                                     regime=None)
    np.testing.assert_array_equal(out_none["short_signal"], out_explicit_none["short_signal"])
    assert out_none["short_signal"][2] and out_none["short_signal"][3]


# ---------------------------------------------------------------------------
# process_borne_neuneu_tranche
# ---------------------------------------------------------------------------

def _make_tranche(entry=100.0, stop=110.0, remaining=1.0, objectif_target=70.0,
                  confirmation_target=85.0, validation_target=90.0):
    return {
        "entry": entry, "stop": stop, "remaining": remaining, "pnl_accum": 0.0,
        "objectif_target": objectif_target, "confirmation_target": confirmation_target,
        "validation_target": validation_target, "_min_low_since_entry": entry,
    }

def test_objectif_closes_fully_short():
    """Objectif atteint (`c[i] <= objectif_target`) : clôture TOTALE
    (contrairement à Repli Neuneu, "sortir TOUS les profits restants")."""
    tr = _make_tranche(entry=100.0, objectif_target=70.0, remaining=0.8)
    high = np.array([0, 71.0]); low = np.array([0, 69.0]); c = np.array([0, 69.0])
    closed, fee_frac, realized = process_borne_neuneu_tranche(tr, 1, high, low, c)
    assert closed is True
    expected_pnl = ((100.0 - 69.0) / 100.0) * 0.8
    assert abs(realized - expected_pnl) < 1e-9
    assert abs(fee_frac - 0.8) < 1e-9
    assert tr["remaining"] == 0.0

def test_confirmation_partial_close_50pct_no_stop_move():
    """Confirmation atteinte : TP 50% du reliquat, stop INCHANGÉ (littéral,
    "NE PAS déplacer le stoploss")."""
    tr = _make_tranche(entry=100.0, stop=110.0, confirmation_target=85.0, remaining=1.0,
                        validation_target=5.0, objectif_target=5.0)   # non atteints, isole la Confirmation
    high = np.array([0, 90.0]); low = np.array([0, 84.0]); c = np.array([0, 84.0])
    closed, fee_frac, realized = process_borne_neuneu_tranche(tr, 1, high, low, c)
    assert closed is False
    assert abs(fee_frac - NEUNEU_CONFIRMATION_CLOSE_FRAC) < 1e-9
    assert abs(tr["remaining"] - 0.5) < 1e-9
    assert tr["stop"] == 110.0, "le stop ne doit JAMAIS bouger à la Confirmation"
    assert tr["confirmation_done"] is True

def test_confirmation_does_not_retrigger_next_bar():
    tr = _make_tranche(entry=100.0, confirmation_target=85.0)
    high = np.array([0, 90.0, 90.0]); low = np.array([0, 84.0, 84.0]); c = np.array([0, 84.0, 84.0])
    process_borne_neuneu_tranche(tr, 1, high, low, c)
    remaining_after_first = tr["remaining"]
    closed, fee_frac, realized = process_borne_neuneu_tranche(tr, 2, high, low, c)
    assert fee_frac == 0.0
    assert abs(tr["remaining"] - remaining_after_first) < 1e-9

def test_validation_tightens_stop_to_min_low_since_entry_no_close():
    """Validation (retour au canal de tendance opposé) : stop RESSERRÉ vers
    le plus bas observé depuis l'ouverture (H-Borne-4), AUCUNE clôture."""
    tr = _make_tranche(entry=100.0, stop=110.0, validation_target=90.0,
                        confirmation_target=10.0, objectif_target=5.0)  # jamais atteints
    tr["_min_low_since_entry"] = 92.0
    # `high` reste SOUS le nouveau stop (92.0) pour isoler la seule question
    # testée (la Validation elle-même) du cas, différent et correct, d'un
    # stop immédiatement retouché après resserrement.
    high = np.array([0, 91.0]); low = np.array([0, 89.0]); c = np.array([0, 89.0])
    closed, fee_frac, realized = process_borne_neuneu_tranche(tr, 1, high, low, c)
    assert closed is False
    assert fee_frac == 0.0
    assert tr["stop"] == 92.0, f"stop={tr['stop']}, attendu 92.0 (_min_low_since_entry, resserré vers le bas)"
    assert tr["validated"] is True

def test_validation_and_confirmation_are_independent_confirmation_can_fire_without_validation():
    """Citation explicite : "parfois la confirmation arrivera avant" -- la
    Confirmation doit pouvoir se déclencher SANS que la Validation ait
    d'abord eu lieu (contrairement à `process_tranche` général, qui
    enchaîne Validation -> Confirmation séquentiellement)."""
    tr = _make_tranche(entry=100.0, stop=110.0, confirmation_target=85.0,
                        validation_target=50.0)   # jamais atteint dans ce test
    high = np.array([0, 86.0]); low = np.array([0, 84.0]); c = np.array([0, 84.0])
    closed, fee_frac, realized = process_borne_neuneu_tranche(tr, 1, high, low, c)
    assert tr["confirmation_done"] is True
    assert tr.get("validated", False) is False, "la Validation n'a pas eu lieu -- ne doit pas être marquée"
    assert fee_frac > 0, "la Confirmation doit s'appliquer même sans Validation préalable"

def test_stop_hit_on_high_wick_closes_fully():
    """SHORT : le stop est touché quand le HIGH atteint/dépasse le niveau
    (pas la clôture) -- ordre réel intrabar."""
    tr = _make_tranche(entry=100.0, stop=105.0, remaining=0.6, objectif_target=5.0,
                        confirmation_target=5.0, validation_target=5.0)
    high = np.array([0, 106.0]); low = np.array([0, 101.0]); c = np.array([0, 102.0])
    closed, fee_frac, realized = process_borne_neuneu_tranche(tr, 1, high, low, c)
    assert closed is True
    expected_pnl = ((100.0 - 105.0) / 100.0) * 0.6
    assert abs(realized - expected_pnl) < 1e-9
    assert abs(fee_frac - 0.6) < 1e-9


# ---------------------------------------------------------------------------
# run_borne_neuneu -- bout en bout, signal monkeypatché
# ---------------------------------------------------------------------------

def test_run_borne_neuneu_opens_and_sizes_correctly(monkeypatch):
    """Signal fabriqué : entrée à i=3, entry=100 (open), ctx_high_ref=90,
    local_range=10 -> stop_distance = max(100-90, 0.5*10) = max(10,5) = 10
    -> stop=110, stop_pct=0.10 -> size_frac=min(1.0, 0.02/0.10)=0.20."""
    n = 8
    o = np.full(n, 100.0); high = np.full(n, 100.0); low = np.full(n, 100.0); c = np.full(n, 100.0)
    dates = pd.date_range("2020-01-01", periods=n, freq="4h")
    df = pd.DataFrame({"date": dates, "open": o, "high": high, "low": low, "close": c})

    def fake_signal(df, context_duration, local_duration, regime=None):
        short_signal = np.zeros(n, dtype=bool); short_signal[3] = True
        context_range = np.full(n, np.nan); context_range[3] = 50.0
        ctx_high_ref = np.full(n, np.nan); ctx_high_ref[3] = 90.0
        ctx_low_ref = np.full(n, np.nan); ctx_low_ref[3] = 40.0
        local_range = np.full(n, np.nan); local_range[3] = 10.0
        local_low_ref = np.full(n, np.nan); local_low_ref[3] = 60.0
        return {"short_signal": short_signal, "context_range": context_range,
                "ctx_high_ref": ctx_high_ref, "ctx_low_ref": ctx_low_ref,
                "local_range": local_range, "local_low_ref": local_low_ref}

    def fake_median(df, duration):
        return np.full(n, 65.0)

    monkeypatch.setattr(neuneu_borne_mod, "compute_borne_neuneu_signal", fake_signal)
    monkeypatch.setattr(neuneu_borne_mod, "context_channel_median", fake_median)
    res = run_borne_neuneu(df, context_duration=5, local_duration=2, fee=0.0, record_trace=True)
    assert len(res["trace"]) == 1
    tr_trace = res["trace"][0]
    assert tr_trace["open_i"] == 3
    assert abs(tr_trace["entry_size"] - 0.20) < 1e-9, (
        f"entry_size={tr_trace['entry_size']}, attendu 0.20 (0.02/0.10)"
    )

def test_run_borne_neuneu_stop_and_objectif_match_hand_calc(monkeypatch):
    n = 8
    o = np.full(n, 100.0); high = np.full(n, 100.0); low = np.full(n, 100.0); c = np.full(n, 100.0)
    dates = pd.date_range("2020-01-01", periods=n, freq="4h")
    df = pd.DataFrame({"date": dates, "open": o, "high": high, "low": low, "close": c})

    def fake_signal(df, context_duration, local_duration, regime=None):
        short_signal = np.zeros(n, dtype=bool); short_signal[3] = True
        context_range = np.full(n, np.nan); context_range[3] = 50.0
        ctx_high_ref = np.full(n, np.nan); ctx_high_ref[3] = 90.0
        ctx_low_ref = np.full(n, np.nan); ctx_low_ref[3] = 40.0
        local_range = np.full(n, np.nan); local_range[3] = 10.0
        local_low_ref = np.full(n, np.nan); local_low_ref[3] = 60.0
        return {"short_signal": short_signal, "context_range": context_range,
                "ctx_high_ref": ctx_high_ref, "ctx_low_ref": ctx_low_ref,
                "local_range": local_range, "local_low_ref": local_low_ref}

    def fake_median(df, duration):
        return np.full(n, 65.0)

    captured = {}
    orig_process = neuneu_borne_mod.process_borne_neuneu_tranche
    def spy_process(tr, i, high, low, c):
        if "stop_at_open" not in captured:
            captured["stop_at_open"] = tr["stop"]
            captured["objectif_target"] = tr["objectif_target"]
            captured["confirmation_target"] = tr["confirmation_target"]
            captured["validation_target"] = tr["validation_target"]
        return orig_process(tr, i, high, low, c)

    monkeypatch.setattr(neuneu_borne_mod, "compute_borne_neuneu_signal", fake_signal)
    monkeypatch.setattr(neuneu_borne_mod, "context_channel_median", fake_median)
    monkeypatch.setattr(neuneu_borne_mod, "process_borne_neuneu_tranche", spy_process)
    run_borne_neuneu(df, context_duration=5, local_duration=2, fee=0.0)
    # stop_distance = max(entry-ctx_high_ref, 0.5*local_range) = max(100-90, 5) = 10 -> stop=110
    assert abs(captured["stop_at_open"] - 110.0) < 1e-9, captured["stop_at_open"]
    # objectif = max(ctx_low_ref, ctx_low_ref + 0.24*context_range) = max(40, 40+12) = 52.0
    assert abs(captured["objectif_target"] - 52.0) < 1e-9, captured["objectif_target"]
    assert abs(captured["confirmation_target"] - 65.0) < 1e-9
    assert abs(captured["validation_target"] - 60.0) < 1e-9

def test_run_borne_neuneu_no_signal_no_trades():
    n = 10
    o = np.full(n, 100.0); high = np.full(n, 100.0); low = np.full(n, 100.0); c = np.full(n, 100.0)
    dates = pd.date_range("2020-01-01", periods=n, freq="4h")
    df = pd.DataFrame({"date": dates, "open": o, "high": high, "low": low, "close": c})
    res = run_borne_neuneu(df, context_duration=5, local_duration=2)
    assert res["n_trades"] == 0
    assert res["total_return_%"] == 0.0

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
