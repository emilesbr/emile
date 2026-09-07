"""
Réserve P0-bis (COUVERTURE_ENSEIGNEMENTS.md ⚠️, PLAN.md occurrence #4) —
script d'analyse ponctuel qui a servi à VÉRIFIER EMPIRIQUEMENT le choix de
méthode retenu pour `proxy_v2.compute_swing_low_confirmed`/`compute_swing_
high_confirmed`, sur le même modèle que `cycle_causal_window_selection.py`
pour le P0 du cycle. Ne fait partie d'aucun pipeline de production — gardé
pour traçabilité/reproductibilité, comme les autres scripts d'analyse
ponctuels du dossier (`ablation_test_cycle.py`, `cycle_causal_window_
selection.py`).

Deux volets :

1. Vérifie bit-à-bit l'hypothèse qui justifie l'option "a" retenue dans la
   tâche (décaler la CONSOMMATION de la classification batch de
   `SWING_ORDER` barres, PAS recalculer barre par barre) : pour un point
   intérieur k (k + SWING_ORDER < n), `argrelextrema(..., order=N)` ne
   compare k qu'aux N barres avant/après — jamais à la série entière. Donc
   la classification batch de k, calculée sur TOUTE la série, doit être
   identique à celle obtenue en calculant sur une série tronquée juste
   après k+N. Vérifié sur BTC H4 réel ET sur une série synthétique — 0
   différence dans les deux cas, ce qui élimine le besoin d'un recalcul
   incrémental plus lent (option "b").

2. Quantifie l'écart réel introduit par le fix sur `compute_ascending_lows`
   (proxy_v2.py) : proportion de barres où "creux ascendants" (et donc le
   score composite / long_signal) change entre l'ancienne version batch et
   la nouvelle version causale, sur les 4 actifs réels du projet.
"""
import sys
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

sys.path.insert(0, ".")
import proxy_v2
from proxy_v2 import add_proxy_v2_score, compute_ascending_lows, SWING_ORDER
from backtest_phase2 import load_h1, resample


def _old_batch_ascending_lows(df: pd.DataFrame, order: int = SWING_ORDER) -> np.ndarray:
    """Reproduction FIDÈLE de l'ancienne `compute_ascending_lows` batch
    (celle en production jusqu'à ce cycle de travail), gardée ici pour
    comparaison — jamais utilisée en production."""
    low_v = df["low"].values
    idx = argrelextrema(low_v, np.less_equal, order=order)[0]
    is_swing = np.zeros(len(df), dtype=bool)
    is_swing[idx] = True
    ascending = np.zeros(len(df), dtype=bool)
    last_lows = []
    for i in range(len(df)):
        if is_swing[i]:
            last_lows.append(low_v[i])
            if len(last_lows) > 2:
                last_lows.pop(0)
        if len(last_lows) == 2:
            ascending[i] = last_lows[1] > last_lows[0]
    return ascending


def verify_batch_classification_is_local(low_v: np.ndarray, order: int = SWING_ORDER) -> tuple:
    """Volet 1 : compare, pour chaque point intérieur k, la classification
    batch (série entière) à celle d'un recalcul sur une série tronquée juste
    après k+order. Retourne (checked, mismatches)."""
    n = len(low_v)
    idx_full = argrelextrema(low_v, np.less_equal, order=order)[0]
    is_swing_full = np.zeros(n, dtype=bool)
    is_swing_full[idx_full] = True

    mismatches = 0
    checked = 0
    for k in range(order, n - order):
        trunc = low_v[: k + order + 1]
        idx_t = argrelextrema(trunc, np.less_equal, order=order)[0]
        is_swing_t = np.zeros(len(trunc), dtype=bool)
        is_swing_t[idx_t] = True
        checked += 1
        if is_swing_t[k] != is_swing_full[k]:
            mismatches += 1
    return checked, mismatches


def main():
    print("=== Volet 1 : la classification batch d'un point intérieur ne dépend")
    print("    jamais de barres au-delà de k+SWING_ORDER (vérifié bit-à-bit) ===")
    rng = np.random.default_rng(0)
    synth_low = 100 + np.cumsum(rng.normal(0, 1, 500))
    checked, mismatches = verify_batch_classification_is_local(synth_low)
    print(f"Série synthétique : {checked} points vérifiés, {mismatches} différences")

    btc_h4 = resample(load_h1("BTCUSDT"), "4h")
    checked, mismatches = verify_batch_classification_is_local(btc_h4["low"].values)
    print(f"BTC H4 réel        : {checked} points vérifiés, {mismatches} différences")
    print("-> confirme le choix de l'option 'a' (décaler la consommation,")
    print("   pas recalculer barre par barre) plutôt que l'option 'b'.\n")

    print("=== Volet 2 : ampleur réelle du fix sur compute_ascending_lows ===")
    rows = []
    for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]:
        h4 = resample(load_h1(symbol), "4h")

        causal_scored = add_proxy_v2_score(h4.copy())

        orig = proxy_v2.compute_ascending_lows
        proxy_v2.compute_ascending_lows = _old_batch_ascending_lows
        batch_scored = add_proxy_v2_score(h4.copy())
        proxy_v2.compute_ascending_lows = orig

        asc_batch = _old_batch_ascending_lows(h4)
        asc_causal = compute_ascending_lows(h4)
        asc_diff_pct = (asc_batch != asc_causal).mean() * 100

        sf_diff_pct = (causal_scored["structure_favorable"].values != batch_scored["structure_favorable"].values).mean() * 100
        long_causal_pct = (causal_scored["score"].values >= 2).mean() * 100
        long_batch_pct = (batch_scored["score"].values >= 2).mean() * 100

        rows.append({
            "symbol": symbol,
            "ascending_lows_diff_%": round(asc_diff_pct, 2),
            "structure_favorable_diff_%": round(sf_diff_pct, 2),
            "long_signal_%_batch": round(long_batch_pct, 2),
            "long_signal_%_causal": round(long_causal_pct, 2),
        })

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(result.to_string(index=False))
    result.to_csv("structure_causal_vs_batch_comparison.csv", index=False)


if __name__ == "__main__":
    main()
