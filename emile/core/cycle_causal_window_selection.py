"""
Sélection empirique de la taille de fenêtre pour compute_cycle_phase_causal.

Méthode : pour chaque taille de fenêtre candidate (40/60/100/150), on calcule
le sinewave causal (fenêtre glissante, hilbert() recalculé à chaque barre sur
la fenêtre [t-W+1, t], phase retenue = dernier point de la fenêtre) sur des
données RÉELLES (BTC/ETH, H4 et D1, tout l'historique disponible), et on
mesure :
  1. La corrélation de Pearson (sinewave_t, rendement_t->t+1), comme dans
     OOS_VALIDATION_CYCLE_SIGN.md, sur l'échantillon complet.
  2. La STABILITÉ de cette corrélation en la recalculant séparément sur 3
     tiers temporels de la série (pas juste sur l'ensemble) — un edge qui
     change de signe ou s'effondre d'un tiers à l'autre est un edge instable.
  3. Le temps de calcul (les moteurs de backtest tournent sur H4/D1 seulement,
     mais on mesure aussi H1 pour anticiper un usage futur).

Le critère de choix n'est PAS la vitesse seule (toutes les fenêtres testées
sont utilisables en pratique sur H4/D1) mais la stabilité du signe/magnitude
de la corrélation à travers les tiers temporels.
"""
import time
import sys
import numpy as np
import pandas as pd
from scipy.signal import hilbert

from emile.backtests.backtest_phase2 import load_h1, resample

CYCLE_DETREND_WINDOW = 20

def causal_sinewave(close: pd.Series, window: int) -> np.ndarray:
    detrended = (close - close.rolling(CYCLE_DETREND_WINDOW).mean()).fillna(0).values
    n = len(detrended)
    out = np.zeros(n)
    for t in range(window - 1, n):
        seg = detrended[t - window + 1: t + 1]
        phase = np.angle(hilbert(seg)[-1])
        out[t] = -np.sin(phase)
    return out

def edge_stats(sinewave, close):
    ret_fwd = close.shift(-1).values / close.values - 1.0
    valid = ~np.isnan(ret_fwd)
    x, y = sinewave[valid], ret_fwd[valid]
    if x.std() == 0 or y.std() == 0:
        return np.nan, len(x)
    r = np.corrcoef(x, y)[0, 1]
    return r, len(x)

def thirds_stability(sinewave, close, warmup):
    n = len(close)
    idx = np.arange(warmup, n - 1)  # skip warmup and last (ret_fwd undefined)
    thirds = np.array_split(idx, 3)
    rs = []
    for part in thirds:
        ret_fwd = close.shift(-1).values / close.values - 1.0
        x = sinewave[part]
        y = ret_fwd[part]
        if x.std() == 0 or y.std() == 0 or len(x) < 20:
            rs.append(np.nan)
        else:
            rs.append(np.corrcoef(x, y)[0, 1])
    return rs

symbols = ["BTCUSDT", "ETHUSDT"]
windows = [40, 60, 100, 150]

results = []
for symbol in symbols:
    h1 = load_h1(symbol)
    for tf_name, df in [("H4", resample(h1, "4h")), ("D1", resample(h1, "1D"))]:
        close = df["close"]
        for w in windows:
            t0 = time.time()
            sw = causal_sinewave(close, w)
            elapsed = time.time() - t0
            r_full, n_obs = edge_stats(sw, close)
            warmup = max(w, CYCLE_DETREND_WINDOW) + 5
            rs_thirds = thirds_stability(sw, close, warmup)
            results.append({
                "symbol": symbol, "tf": tf_name, "window": w,
                "n_bars": len(df), "n_obs": n_obs, "r_full": r_full,
                "r_tier1": rs_thirds[0], "r_tier2": rs_thirds[1], "r_tier3": rs_thirds[2],
                "seconds": round(elapsed, 3),
            })

res = pd.DataFrame(results)
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 20)
print(res.to_string(index=False))
res.to_csv("../cycle_causal_window_selection.csv", index=False)

# Also time H1 for one asset/window to anticipate future use (not used by current engines)
h1 = load_h1("BTCUSDT")
for w in [60, 100]:
    t0 = time.time()
    causal_sinewave(h1["close"], w)
    print(f"H1 BTCUSDT window={w}: {time.time()-t0:.2f}s for {len(h1)} bars")
