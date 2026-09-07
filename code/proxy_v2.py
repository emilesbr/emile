"""
Proxy v2 — signal d'entrée reconstruit à partir des enseignements du corpus
Trading Lessons, remplaçant la confluence EMA(8/21/55) générique utilisée
jusqu'ici. Trois composantes, formule des "4 nuances de gris" (Momentum x
Cycle x Structure) :

  1. Momentum : TSI(14,7,9) — True Strength Index, formule publique exacte
     (Blau), alternative documentée au RSI dans le corpus (sources #3/#4).
  2. Cycle : phase extraite par transformée de Hilbert sur le prix détrendé.
     APPROXIMATION documentée du "Sine Wave" d'Ehlers évoqué dans le corpus —
     pas l'algorithme adaptatif exact d'Ehlers (période dominante variable),
     mais le même principe (phase cyclique via analyse harmonique), en
     utilisant scipy.signal.hilbert (méthode publique standard).
  3. Structure : creux ascendants (swing lows croissants, détectés par
     scipy.signal.argrelextrema comme dans la Phase 2 v4) + prix au-dessus
     de l'EMA lente (filtre de tendance de fond).

Score = somme des 3 composantes (0-3). Signal long si score >= 2.
"""
import pandas as pd
import numpy as np
from scipy.signal import hilbert, argrelextrema

TSI_LONG, TSI_SHORT, TSI_SIGNAL = 14, 7, 9
CYCLE_DETREND_WINDOW = 20
CYCLE_MATURE_THRESHOLD = 0.8   # "cycle mature" si |sinewave| > 0.8 (cf. corpus, échelle -100/100 -> -1/1)
SWING_ORDER = 3
TREND_EMA = 55


def compute_tsi(close: pd.Series) -> tuple:
    mom = close.diff()
    ema1 = mom.ewm(span=TSI_LONG, adjust=False).mean()
    ema2 = ema1.ewm(span=TSI_SHORT, adjust=False).mean()
    abs_ema1 = mom.abs().ewm(span=TSI_LONG, adjust=False).mean()
    abs_ema2 = abs_ema1.ewm(span=TSI_SHORT, adjust=False).mean()
    tsi = 100 * ema2 / abs_ema2.replace(0, np.nan)
    signal_line = tsi.ewm(span=TSI_SIGNAL, adjust=False).mean()
    return tsi, signal_line


def compute_cycle_phase(close: pd.Series) -> np.ndarray:
    detrended = (close - close.rolling(CYCLE_DETREND_WINDOW).mean()).fillna(0).values
    analytic = hilbert(detrended)
    phase = np.angle(analytic)
    # CORRECTION (contrôle aléatoire du 2025 : sin(phase) était anti-corrélé au
    # rendement du lendemain sur BTC/ETH/SOL — erreur de convention de signe
    # classique avec la transformée de Hilbert). Signe inversé, vérifié empiriquement.
    return -np.sin(phase)


def compute_ascending_lows(df: pd.DataFrame) -> np.ndarray:
    low_v = df["low"].values
    idx = argrelextrema(low_v, np.less_equal, order=SWING_ORDER)[0]
    is_swing = np.zeros(len(df), dtype=bool)
    is_swing[idx] = True
    # Pour chaque bougie, "creux ascendants" = le dernier swing low détecté
    # est plus haut que l'avant-dernier
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


def add_proxy_v2_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    close = df["close"]

    tsi, tsi_signal = compute_tsi(close)
    momentum_favorable = (tsi > tsi_signal).values

    sinewave = compute_cycle_phase(close)
    sinewave_prev = np.roll(sinewave, 1)
    sinewave_prev[0] = sinewave[0]
    cycle_ascending = sinewave > sinewave_prev
    cycle_not_exhausted = np.abs(sinewave) < CYCLE_MATURE_THRESHOLD
    cycle_favorable = cycle_ascending & cycle_not_exhausted

    ascending_lows = compute_ascending_lows(df)
    ema_trend = close.ewm(span=TREND_EMA, adjust=False).mean().values
    structure_favorable = ascending_lows & (close.values > ema_trend)

    df["momentum_favorable"] = momentum_favorable
    df["cycle_favorable"] = cycle_favorable
    df["structure_favorable"] = structure_favorable
    df["score"] = momentum_favorable.astype(int) + cycle_favorable.astype(int) + structure_favorable.astype(int)
    df["tsi"] = tsi.values
    df["sinewave"] = sinewave
    return df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from backtest_phase2 import load_h1, resample

    df = resample(load_h1("BTCUSDT"), "1D")
    scored = add_proxy_v2_score(df)
    print(scored[["date", "close", "momentum_favorable", "cycle_favorable", "structure_favorable", "score"]].tail(30).to_string(index=False))
    print("\nRépartition des scores (BTC D1) :")
    print(scored["score"].value_counts().sort_index())
