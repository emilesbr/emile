"""
Tests pour `emile/core/neuneu_repli.py` -- mécanisme "Repli Neuneu" (46e
round, `docs/PLAN.md`), sur des séries SYNTHÉTIQUES construites à la main
(même discipline que `test_position_engine.py`/`test_trend_table.py`) --
le résultat attendu de chaque cas est calculé AVANT d'exécuter le code.

Ne teste PAS `compute_swing_low_confirmed`/`compute_swing_high_confirmed`/
`context_channel_bounds` eux-mêmes (déjà couverts ailleurs) -- se concentre
sur :
  1. `_repli_neuneu_state_machine` (cœur pur, arrays fabriqués à la main --
     pas de vraie fenêtre glissante à reproduire).
  2. `process_repli_neuneu_tranche` (Objectif/Validation/Stop).
  3. `run_repli_neuneu` de bout en bout, `compute_repli_neuneu_signal`
     monkeypatché pour éviter de reproduire un vrai canal glissant à la main
     (même technique "monkeypatch-and-observe" déjà établie dans ce projet).
"""
import numpy as np
import pandas as pd
import pytest

from emile.core.neuneu_repli import (
    _repli_neuneu_state_machine, process_repli_neuneu_tranche, run_repli_neuneu,
    NEUNEU_FIB_LOW, NEUNEU_FIB_HIGH, NEUNEU_RISK_PCT, NEUNEU_OBJECTIF_CLOSE_FRAC,
)
import emile.core.neuneu_repli as neuneu_repli_mod

NAN = np.nan


def _nan_arr(n):
    return np.full(n, NAN)


def test_state_machine_full_pattern_ground_truth():
    """Canal de contexte FIXE [0, 100] du début à la fin (fib_low=14,6,
    fib_high=23,6) : creux confirmé (swing_low) à j=2 avec close=10 (<14,6)
    -> dumb zone confirmée (swing_high) à j=5 avec close=50 -> retour dans
    la zone fibo à j=8 avec close=20 (dans [14,6;23,6]) -> signal à i=9."""
    n = 12
    close = np.array([30, 25, 10, 25, 30, 50, 40, 30, 20, 30, 30, 30], dtype=float)
    swing_low = np.zeros(n, dtype=bool); swing_low[2] = True
    swing_high = np.zeros(n, dtype=bool); swing_high[5] = True
    ctx_low = np.full(n, 0.0); ctx_high = np.full(n, 100.0)
    local_low = np.full(n, 40.0); local_high = np.full(n, 60.0)   # local_range = 20 partout

    out = _repli_neuneu_state_machine(close, swing_low, swing_high, ctx_low, ctx_high,
                                       local_low, local_high)
    assert out["long_signal"][9] == True
    assert not out["long_signal"][:9].any() and not out["long_signal"][10:].any()
    assert out["dumb_zone_level"][9] == 50.0, "niveau = close[5] au moment du swing high, pas le high"
    assert out["context_range"][9] == 100.0
    assert out["ctx_high_ref"][9] == 100.0
    assert out["local_range"][9] == 20.0

def test_state_machine_creux_not_below_fib_low_never_transitions():
    """Un swing low dont la clôture N'EST PAS sous la zone fibo basse ne
    doit PAS faire progresser la machine -- aucun signal, même si un swing
    high suit ensuite."""
    n = 10
    close = np.full(n, 50.0)
    close[2] = 50.0   # swing low, mais 50 >= fib_low=14.6 -- ne compte pas
    swing_low = np.zeros(n, dtype=bool); swing_low[2] = True
    swing_high = np.zeros(n, dtype=bool); swing_high[5] = True
    ctx_low = np.full(n, 0.0); ctx_high = np.full(n, 100.0)
    local_low = _nan_arr(n); local_high = _nan_arr(n)

    out = _repli_neuneu_state_machine(close, swing_low, swing_high, ctx_low, ctx_high,
                                       local_low, local_high)
    assert not out["long_signal"].any()

def test_state_machine_swing_high_before_creux_does_not_count_as_dumbzone():
    """Un swing high survenu AVANT le creux ne doit pas être consommé comme
    "dumb zone" -- la machine doit rester en AWAITING_CREUX jusqu'à ce
    qu'un vrai creux soit détecté, PUIS chercher un swing high après."""
    n = 12
    close = np.array([50, 60, 50, 25, 10, 25, 40, 50, 20, 30, 30, 30], dtype=float)
    swing_high = np.zeros(n, dtype=bool); swing_high[1] = True   # AVANT le creux -- ignoré
    swing_high[6] = True                                          # dumb zone réelle (après creux à j=4)
    swing_low = np.zeros(n, dtype=bool); swing_low[4] = True
    ctx_low = np.full(n, 0.0); ctx_high = np.full(n, 100.0)
    local_low = _nan_arr(n); local_high = _nan_arr(n)

    out = _repli_neuneu_state_machine(close, swing_low, swing_high, ctx_low, ctx_high,
                                       local_low, local_high)
    assert out["long_signal"][9] == True
    assert out["dumb_zone_level"][9] == 40.0, "doit être close[6]=40 (dumb zone RÉELLE), pas close[1]=60"

def test_state_machine_resets_after_signal_for_a_second_cycle():
    """Après un signal, la machine doit revenir en AWAITING_CREUX et
    pouvoir détecter un 2e cycle complet plus loin dans la même série."""
    n = 20
    close = np.full(n, 30.0)
    close[2] = 10.0; close[5] = 50.0; close[8] = 20.0    # 1er cycle -> signal à i=9
    close[12] = 10.0; close[15] = 50.0; close[18] = 20.0  # 2e cycle -> signal à i=19
    swing_low = np.zeros(n, dtype=bool); swing_low[[2, 12]] = True
    swing_high = np.zeros(n, dtype=bool); swing_high[[5, 15]] = True
    ctx_low = np.full(n, 0.0); ctx_high = np.full(n, 100.0)
    local_low = _nan_arr(n); local_high = _nan_arr(n)

    out = _repli_neuneu_state_machine(close, swing_low, swing_high, ctx_low, ctx_high,
                                       local_low, local_high)
    assert out["long_signal"][9] == True
    assert out["long_signal"][19] == True
    assert out["long_signal"].sum() == 2

def test_state_machine_nan_context_bounds_never_signals():
    """Canal de contexte inconnu (NaN, warmup) -> jamais de signal, même si
    creux/dumb zone/retour sont par ailleurs présents dans les prix."""
    n = 10
    close = np.array([30, 25, 10, 25, 30, 50, 40, 30, 20, 30], dtype=float)
    swing_low = np.zeros(n, dtype=bool); swing_low[2] = True
    swing_high = np.zeros(n, dtype=bool); swing_high[5] = True
    ctx_low = _nan_arr(n); ctx_high = _nan_arr(n)
    local_low = _nan_arr(n); local_high = _nan_arr(n)

    out = _repli_neuneu_state_machine(close, swing_low, swing_high, ctx_low, ctx_high,
                                       local_low, local_high)
    assert not out["long_signal"].any()


# ---------------------------------------------------------------------------
# process_repli_neuneu_tranche
# ---------------------------------------------------------------------------

def _make_tranche(entry=100.0, stop=90.0, remaining=1.0, dumb_zone_level=120.0,
                  ctx_high_ref=130.0, objectif_target=115.0):
    return {
        "entry": entry, "stop": stop, "remaining": remaining, "pnl_accum": 0.0,
        "dumb_zone_level": dumb_zone_level, "ctx_high_ref": ctx_high_ref,
        "objectif_target": objectif_target, "_max_high_since_entry": entry,
    }

def test_objectif_partial_close_never_full_close_at_50pct():
    """Objectif atteint : clôture PARTIELLE (`NEUNEU_OBJECTIF_CLOSE_FRAC`
    du reliquat), tranche reste ouverte."""
    tr = _make_tranche(objectif_target=115.0)
    high = np.array([0, 116.0]); low = np.array([0, 114.0]); c = np.array([0, 116.0])
    closed, fee_frac, realized = process_repli_neuneu_tranche(tr, 1, high, low, c)
    assert closed is False
    assert abs(fee_frac - NEUNEU_OBJECTIF_CLOSE_FRAC) < 1e-9
    assert abs(tr["remaining"] - (1.0 - NEUNEU_OBJECTIF_CLOSE_FRAC)) < 1e-9
    assert tr["objectif_done"] is True

def test_objectif_does_not_retrigger_next_bar():
    tr = _make_tranche(objectif_target=115.0)
    high = np.array([0, 116.0, 116.0]); low = np.array([0, 114.0, 114.0]); c = np.array([0, 116.0, 116.0])
    process_repli_neuneu_tranche(tr, 1, high, low, c)
    remaining_after_first = tr["remaining"]
    closed, fee_frac, realized = process_repli_neuneu_tranche(tr, 2, high, low, c)
    assert fee_frac == 0.0
    assert abs(tr["remaining"] - remaining_after_first) < 1e-9

def test_objectif_close_frac_default_matches_module_constant():
    """Sans argument, `process_repli_neuneu_tranche` doit toujours utiliser
    `NEUNEU_OBJECTIF_CLOSE_FRAC` -- non-régression bit-à-bit pour tout
    appelant existant (62e round, nouveau paramètre `objectif_close_frac`)."""
    tr = _make_tranche(objectif_target=115.0)
    high = np.array([0, 116.0]); low = np.array([0, 114.0]); c = np.array([0, 116.0])
    _, fee_frac, _ = process_repli_neuneu_tranche(tr, 1, high, low, c)
    assert abs(fee_frac - NEUNEU_OBJECTIF_CLOSE_FRAC) < 1e-9

def test_objectif_close_frac_custom_value_used_instead_of_default():
    """`objectif_close_frac` explicite (62e round, demande directe de
    l'utilisateur -- "qu'est-ce qui améliorerait la rentabilité ? imagine
    et teste") remplace `NEUNEU_OBJECTIF_CLOSE_FRAC` sans le modifier."""
    tr = _make_tranche(objectif_target=115.0)
    high = np.array([0, 116.0]); low = np.array([0, 114.0]); c = np.array([0, 116.0])
    closed, fee_frac, realized = process_repli_neuneu_tranche(tr, 1, high, low, c, objectif_close_frac=0.25)
    assert closed is False
    assert abs(fee_frac - 0.25) < 1e-9
    assert abs(tr["remaining"] - 0.75) < 1e-9
    assert tr["objectif_done"] is True

def test_objectif_close_frac_zero_marks_done_without_closing_anything():
    """Cas limite mesuré comme le meilleur réglage sur les 4 actifs
    (`objectif_close_frac=0.0`) : Objectif ne clôture RIEN, mais
    `objectif_done` passe quand même à `True` (ne redéclenche jamais), et la
    Validation reste fonctionnelle ensuite."""
    tr = _make_tranche(entry=100.0, stop=90.0, dumb_zone_level=120.0,
                        ctx_high_ref=130.0, objectif_target=115.0)
    high = np.array([0, 116.0]); low = np.array([0, 114.0]); c = np.array([0, 116.0])
    closed, fee_frac, realized = process_repli_neuneu_tranche(tr, 1, high, low, c, objectif_close_frac=0.0)
    assert closed is False
    assert fee_frac == 0.0
    assert tr["remaining"] == 1.0
    assert tr["objectif_done"] is True
    assert realized is None

    tr["_max_high_since_entry"] = 121.0
    high2 = np.array([0, 116.0, 121.0]); low2 = np.array([0, 114.0, 122.0]); c2 = np.array([0, 116.0, 122.0])
    closed2, fee_frac2, _ = process_repli_neuneu_tranche(tr, 2, high2, low2, c2, objectif_close_frac=0.0)
    assert closed2 is False
    assert tr["validated"] is True
    assert tr["stop"] == 121.0

def test_run_repli_neuneu_objectif_close_frac_forwarded(monkeypatch):
    """`run_repli_neuneu(objectif_close_frac=...)` doit se répercuter
    jusqu'à `process_repli_neuneu_tranche` -- vérifié de bout en bout avec
    un `realized_pnl` calculé À LA MAIN pour 2 valeurs de `objectif_close_
    frac` distinctes (formule : `total = 0,012 - 0,001*frac`, dérivée de
    entry_size=0,10 (risque 2%/stop 20%), pnl Objectif=0,11, pnl Stop=0,12,
    tous deux déclenchés sur la MÊME bougie -- vérité terrain, pas devinée)."""
    n = 8
    o = np.full(n, 100.0); high = np.full(n, 100.0); low = np.full(n, 100.0); c = np.full(n, 100.0)
    high[4] = 112.0; low[4] = 108.0; c[4] = 111.0
    df = pd.DataFrame({"open": o, "high": high, "low": low, "close": c})

    def fake_signal(df_in, context_duration, local_duration):
        long_signal = np.zeros(n, dtype=bool); long_signal[3] = True
        dumb_zone_level = np.full(n, np.nan); dumb_zone_level[3] = 110.0
        local_range = np.full(n, np.nan); local_range[3] = 10.0
        context_range = np.full(n, np.nan); context_range[3] = 40.0
        ctx_high_ref = np.full(n, np.nan); ctx_high_ref[3] = 1000.0
        return {"long_signal": long_signal, "dumb_zone_level": dumb_zone_level,
                "local_range": local_range, "context_range": context_range,
                "ctx_high_ref": ctx_high_ref}
    monkeypatch.setattr(neuneu_repli_mod, "compute_repli_neuneu_signal", fake_signal)

    for frac in (0.25, 0.75):
        res = run_repli_neuneu(df, context_duration=5, local_duration=2, fee=0.0,
                                record_trace=True, objectif_close_frac=frac)
        expected = 0.012 - 0.001 * frac
        assert abs(res["trace"][0]["realized_pnl"] - expected) < 1e-9, (
            f"frac={frac}: realized_pnl={res['trace'][0]['realized_pnl']}, attendu {expected}"
        )

def test_validation_moves_stop_to_max_high_since_entry_no_close():
    """Validation (retour dans la dumb-zone OU au contexte opposé) : stop
    remonté au plus haut observé depuis l'ouverture, AUCUNE clôture."""
    tr = _make_tranche(entry=100.0, stop=90.0, dumb_zone_level=120.0, objectif_target=200.0)
    tr["_max_high_since_entry"] = 118.0   # déjà tracé par l'appelant avant cet appel
    high = np.array([0, 121.0]); low = np.array([0, 119.0]); c = np.array([0, 121.0])
    closed, fee_frac, realized = process_repli_neuneu_tranche(tr, 1, high, low, c)
    assert closed is False
    assert fee_frac == 0.0
    assert tr["stop"] == 118.0, f"stop={tr['stop']}, attendu 118.0 (_max_high_since_entry, pas 121 ni l'entrée)"
    assert tr["validated"] is True

def test_validation_via_opposite_context_also_triggers():
    """Le retour au CONTEXTE opposé (`ctx_high_ref`), pas seulement la
    dumb-zone, doit AUSSI déclencher la Validation."""
    tr = _make_tranche(entry=100.0, stop=90.0, dumb_zone_level=500.0,   # jamais atteint
                        ctx_high_ref=110.0, objectif_target=500.0)
    tr["_max_high_since_entry"] = 112.0
    high = np.array([0, 111.0]); low = np.array([0, 109.0]); c = np.array([0, 111.0])
    closed, fee_frac, realized = process_repli_neuneu_tranche(tr, 1, high, low, c)
    assert tr["validated"] is True
    assert tr["stop"] == 112.0

def test_stop_hit_closes_fully_on_wick():
    tr = _make_tranche(entry=100.0, stop=95.0, remaining=0.6, objectif_target=200.0,
                        dumb_zone_level=500.0, ctx_high_ref=500.0)
    high = np.array([0, 96.0]); low = np.array([0, 94.0]); c = np.array([0, 96.0])
    closed, fee_frac, realized = process_repli_neuneu_tranche(tr, 1, high, low, c)
    assert closed is True
    expected_pnl = ((95.0 - 100.0) / 100.0) * 0.6
    assert abs(realized - expected_pnl) < 1e-9
    assert abs(fee_frac - 0.6) < 1e-9
    assert tr["remaining"] == 0.0


# ---------------------------------------------------------------------------
# run_repli_neuneu -- bout en bout, signal monkeypatché (évite de reproduire
# un vrai canal glissant à la main)
# ---------------------------------------------------------------------------

def test_run_repli_neuneu_opens_and_sizes_correctly(monkeypatch):
    """Signal fabriqué à la main : un signal à i=3 avec local_range=10,
    context_range=40 (=> stop_distance=max(10, 0.5*40)=20, stop_pct=20/100=
    0.20, size_frac=min(1.0, 0.02/0.20)=0.10). Vérité terrain calculée AVANT
    d'exécuter le code."""
    n = 8
    o = np.full(n, 100.0)
    high = np.full(n, 100.0)
    low = np.full(n, 100.0)
    c = np.full(n, 100.0)
    df = pd.DataFrame({"open": o, "high": high, "low": low, "close": c})

    def fake_signal(df, context_duration, local_duration):
        long_signal = np.zeros(n, dtype=bool)
        long_signal[3] = True
        dumb_zone_level = np.full(n, np.nan); dumb_zone_level[3] = 200.0
        local_range = np.full(n, np.nan); local_range[3] = 10.0
        context_range = np.full(n, np.nan); context_range[3] = 40.0
        ctx_high_ref = np.full(n, np.nan); ctx_high_ref[3] = 300.0
        return {"long_signal": long_signal, "dumb_zone_level": dumb_zone_level,
                "local_range": local_range, "context_range": context_range,
                "ctx_high_ref": ctx_high_ref}

    monkeypatch.setattr(neuneu_repli_mod, "compute_repli_neuneu_signal", fake_signal)
    res = run_repli_neuneu(df, context_duration=5, local_duration=2, fee=0.0, record_trace=True)
    assert len(res["trace"]) == 1
    tr_trace = res["trace"][0]
    assert tr_trace["open_i"] == 3
    assert abs(tr_trace["entry_size"] - 0.10) < 1e-9, (
        f"entry_size={tr_trace['entry_size']}, attendu 0.10 (0.02/0.20)"
    )

def test_run_repli_neuneu_stop_price_matches_hand_calc(monkeypatch):
    """Même scénario que ci-dessus : stop = entry - max(local_range,
    0.5*context_range) = 100 - max(10, 20) = 80.0."""
    n = 8
    o = np.full(n, 100.0); high = np.full(n, 100.0); low = np.full(n, 100.0); c = np.full(n, 100.0)
    df = pd.DataFrame({"open": o, "high": high, "low": low, "close": c})

    def fake_signal(df, context_duration, local_duration):
        long_signal = np.zeros(n, dtype=bool); long_signal[3] = True
        dumb_zone_level = np.full(n, np.nan); dumb_zone_level[3] = 200.0
        local_range = np.full(n, np.nan); local_range[3] = 10.0
        context_range = np.full(n, np.nan); context_range[3] = 40.0
        ctx_high_ref = np.full(n, np.nan); ctx_high_ref[3] = 300.0
        return {"long_signal": long_signal, "dumb_zone_level": dumb_zone_level,
                "local_range": local_range, "context_range": context_range,
                "ctx_high_ref": ctx_high_ref}

    captured = {}
    orig_process = neuneu_repli_mod.process_repli_neuneu_tranche
    def spy_process(tr, i, high, low, c, objectif_close_frac=NEUNEU_OBJECTIF_CLOSE_FRAC):
        if "stop_at_open" not in captured:
            captured["stop_at_open"] = tr["stop"]
            captured["objectif_target"] = tr["objectif_target"]
        return orig_process(tr, i, high, low, c, objectif_close_frac=objectif_close_frac)

    monkeypatch.setattr(neuneu_repli_mod, "compute_repli_neuneu_signal", fake_signal)
    monkeypatch.setattr(neuneu_repli_mod, "process_repli_neuneu_tranche", spy_process)
    run_repli_neuneu(df, context_duration=5, local_duration=2, fee=0.0)
    assert abs(captured["stop_at_open"] - 80.0) < 1e-9, captured["stop_at_open"]
    # objectif_target = min(dumb_zone_level=200, ctx_high_ref - FIB_HIGH*context_range
    #                       = 300 - 0.236*40 = 300 - 9.44 = 290.56) = 200.0
    assert abs(captured["objectif_target"] - 200.0) < 1e-9, captured["objectif_target"]

def test_run_repli_neuneu_no_signal_no_trades():
    n = 10
    o = np.full(n, 100.0); high = np.full(n, 100.0); low = np.full(n, 100.0); c = np.full(n, 100.0)
    dates = pd.date_range("2020-01-01", periods=n, freq="4h")
    df = pd.DataFrame({"date": dates, "open": o, "high": high, "low": low, "close": c})
    res = run_repli_neuneu(df, context_duration=5, local_duration=2)
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
