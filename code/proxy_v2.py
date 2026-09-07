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
     Deux implémentations cohabitent volontairement (cf. réserve P0,
     COUVERTURE_ENSEIGNEMENTS.md) : `compute_cycle_phase` (BATCH, NON
     CAUSALE — conservée pour comparaison/archive, ne plus l'utiliser en
     production) et `compute_cycle_phase_causal` (fenêtre glissante,
     utilisée par `add_proxy_v2_score` depuis ce cycle de travail).
  3. Structure : creux ascendants (swing lows croissants, détectés par
     scipy.signal.argrelextrema comme dans la Phase 2 v4) + prix au-dessus
     de l'EMA lente (filtre de tendance de fond).

Score = somme des 3 composantes (0-3). Signal long si score >= 2.

Réserve P0-bis (COUVERTURE_ENSEIGNEMENTS.md / PLAN.md occurrence #4) —
TRAITÉE ce cycle de travail, même catégorie que la réserve P0 ci-dessus
mais sur `compute_ascending_lows` (structure) plutôt que sur le cycle :
`argrelextrema(..., order=SWING_ORDER)` classe un point i en ne comparant
QUE les `SWING_ORDER` barres avant/après i — jamais la série entière — donc
la classification batch reste valable, seul le *moment* où elle a le droit
d'être consommée doit être décalé à i+SWING_ORDER (une fois ces barres
réellement observées). `compute_swing_low_confirmed`/`compute_swing_high_
confirmed` ci-dessous implémentent exactement ce décalage (option "a" de la
tâche, pas un recalcul incrémental — vérifié bit-à-bit identique à un
recalcul tronqué, cf. `code/structure_causal_vs_batch_comparison.py`).
"""
import pandas as pd
import numpy as np
from scipy.signal import hilbert, argrelextrema
from numpy.lib.stride_tricks import sliding_window_view

TSI_LONG, TSI_SHORT, TSI_SIGNAL = 14, 7, 9
CYCLE_DETREND_WINDOW = 20
CYCLE_MATURE_THRESHOLD = 0.8   # "cycle mature" si |sinewave| > 0.8 (cf. corpus, échelle -100/100 -> -1/1)
CYCLE_CAUSAL_WINDOW = 150  # choix empirique (pas seulement la vitesse) : cf.
                           # cycle_causal_window_selection.csv et COUVERTURE_ENSEIGNEMENTS.md —
                           # fenêtre la plus stable (écart-type le plus faible de la corrélation
                           # cycle/rendement futur entre 3 tiers temporels) sur BTC/ETH/BNB/SOL
                           # réels parmi {40, 60, 100, 150}, à corrélation globale comparable
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
    """⚠️ NON CAUSALE — NE PLUS UTILISER EN PRODUCTION (conservée pour
    comparaison/archive uniquement ; `add_proxy_v2_score` utilise désormais
    `compute_cycle_phase_causal`, cf. réserve P0 ci-dessous).

    Appelle scipy.signal.hilbert() sur la série de prix ENTIÈRE d'un seul
    coup (FFT sur tout le tableau) : la phase estimée à l'instant t peut être
    influencée par des valeurs FUTURES de la série (lookahead). Mesuré sur
    données réelles (BTC/ETH/BNB/SOL, H4/D1, tout l'historique disponible) :
    corrélation batch(sinewave_t, rendement_t->t+1) ≈ +0.29 (hautement
    significative), contre une corrélation quasi nulle et non significative
    en calcul causal (`compute_cycle_phase_causal`, cf.
    COUVERTURE_ENSEIGNEMENTS.md et cycle_causal_window_selection.csv /
    phase2_v{5,6,7}_CAUSAL_results.csv vs phase2_v{5,6,7}_BATCH_reference_
    results.csv). Ce n'est donc pas une nuance mineure : la quasi-totalité
    du signal mesuré en batch ne survit pas au calcul causal sur données
    réelles. Gardée en l'état par transparence (pour que quiconque veuille
    reproduire/comparer le chiffre batch le puisse), pas parce qu'elle
    serait encore recommandée pour un usage en backtest ou a fortiori en
    production."""
    detrended = (close - close.rolling(CYCLE_DETREND_WINDOW).mean()).fillna(0).values
    analytic = hilbert(detrended)
    phase = np.angle(analytic)
    # CORRECTION (contrôle aléatoire du 2025 : sin(phase) était anti-corrélé au
    # rendement du lendemain sur BTC/ETH/SOL — erreur de convention de signe
    # classique avec la transformée de Hilbert). Signe inversé, vérifié empiriquement.
    return -np.sin(phase)


def compute_cycle_phase_causal(close: pd.Series, window: int = CYCLE_CAUSAL_WINDOW) -> np.ndarray:
    """Version CAUSALE de `compute_cycle_phase`, utilisée par
    `add_proxy_v2_score` depuis le traitement de la réserve P0
    (COUVERTURE_ENSEIGNEMENTS.md, PLAN.md occurrence #2).

    Recalcule la transformée de Hilbert sur une FENÊTRE GLISSANTE de `window`
    barres (pas sur la série entière, pas non plus une fenêtre expansive sur
    tout l'historique — trop lent sur plusieurs années et probablement
    instable en stationnarité) : pour chaque instant t, on prend les
    `window` dernières valeurs détrendées [t-window+1, t], on calcule
    hilbert() sur CETTE seule fenêtre, et on ne garde que la phase du DERNIER
    point (celui correspondant à t) — aucune valeur postérieure à t n'entre
    jamais dans le calcul de sinewave[t]. Vectorisé via
    `numpy.lib.stride_tricks.sliding_window_view` + `hilbert(..., axis=1)`
    (équivalent bit-à-bit à une boucle barre par barre, ~30 % plus rapide).

    Choix de `window` (150 par défaut, cf. CYCLE_CAUSAL_WINDOW) : comparé
    empiriquement à 40/60/100/150 sur BTC/ETH/BNB/SOL réels (H4 et D1, tout
    l'historique) — critère retenu : STABILITÉ de la corrélation
    cycle/rendement futur entre 3 tiers temporels de la série (pas la
    vitesse, qui est comparable pour toutes ces tailles sur H4/D1). Résultat
    empirique important à connaître avant d'interpréter cette fenêtre : à
    TOUTES les tailles testées, la corrélation causale reste proche de zéro
    et non significative sur données réelles (cf. docstring de
    `compute_cycle_phase` et COUVERTURE_ENSEIGNEMENTS.md) — le choix de 150
    n'est donc pas un réglage qui "sauve" un edge, seulement celui qui s'est
    montré le plus stable (écart-type le plus faible entre tiers temporels)
    parmi des candidats qui ne montrent, de toute façon, pas d'edge causal
    significatif sur les actifs testés.

    Les `window - 1` premières valeurs (warmup, avant qu'une fenêtre complète
    soit disponible) sont mises à 0, comme le faisait déjà implicitement
    l'ancienne fonction pour ses toutes premières barres (fillna(0) du
    détrend) — sans conséquence car ces barres sont de toute façon exclues
    par le warmup plus large (`EMA_SLOW + 20`) des moteurs de backtest."""
    detrended = (close - close.rolling(CYCLE_DETREND_WINDOW).mean()).fillna(0).values
    n = len(detrended)
    out = np.zeros(n)
    if n >= window:
        windows = sliding_window_view(detrended, window)          # (n-window+1, window)
        analytic = hilbert(windows, axis=1)
        phase_last = np.angle(analytic[:, -1])                    # dernier point de chaque fenêtre = t
        out[window - 1:] = -np.sin(phase_last)                    # même convention de signe corrigée
    return out


def _swing_confirmed(values: np.ndarray, comparator, order: int) -> np.ndarray:
    """Primitive CAUSALE partagée par `compute_swing_low_confirmed`/
    `compute_swing_high_confirmed`. `argrelextrema(values, comparator,
    order=order)` classe le point k en ne comparant QUE les `order` valeurs
    avant et après k (jamais la série entière, y compris quand l'appel est
    fait en un seul batch sur tout l'historique) : la classification de k ne
    dépend donc jamais de données au-delà de k+order — vérifié empiriquement
    bit-à-bit (0 différence sur 14233 points BTC H4 réels et 494 points
    synthétiques entre le calcul batch et un recalcul sur une série tronquée
    juste après k+order, cf. `code/structure_causal_vs_batch_comparison.py`).

    Conséquence : PAS besoin de recalculer quoi que ce soit barre par barre
    (option "b" de la tâche, plus lente, évitée) — on réutilise le résultat
    batch tel quel (option "a") et on décale seulement le moment où il a le
    droit d'être consommé, à k+order plutôt qu'à k. Retourne `confirmed`
    (bool) où `confirmed[t]` est vrai ssi la barre `t - order` est un swing
    ET que ses `order` barres suivantes ont réellement été observées (donc
    jamais avant t = order) — l'appelant récupère la valeur/l'indice réel du
    swing via `t - order`, pas via `t`."""
    n = len(values)
    idx = argrelextrema(values, comparator, order=order)[0]
    is_swing = np.zeros(n, dtype=bool)
    is_swing[idx] = True
    confirmed = np.zeros(n, dtype=bool)
    if order < n:
        confirmed[order:] = is_swing[: n - order]
    return confirmed


def compute_swing_low_confirmed(low: np.ndarray, order: int = SWING_ORDER) -> np.ndarray:
    """Version CAUSALE de la détection de swing low (cf. réserve P0-bis en
    tête de fichier). `confirmed[t]` vrai ssi `low[t - order]` est un swing
    low confirmé à l'instant t."""
    return _swing_confirmed(low, np.less_equal, order)


def compute_swing_high_confirmed(high: np.ndarray, order: int = SWING_ORDER) -> np.ndarray:
    """Symétrique de `compute_swing_low_confirmed` pour les swing highs
    (réutilisée par `code/fibonacci.py`, cf. réserve P0-bis)."""
    return _swing_confirmed(high, np.greater_equal, order)


def compute_ascending_lows(df: pd.DataFrame) -> np.ndarray:
    """Creux ascendants — CAUSALE depuis le traitement de la réserve P0-bis
    (COUVERTURE_ENSEIGNEMENTS.md/PLAN.md occurrence #4) : un swing low n'est
    pris en compte qu'à l'instant où il est réellement confirmé
    (`compute_swing_low_confirmed`), pas à l'instant du creux lui-même."""
    low_v = df["low"].values
    n = len(df)
    confirmed = compute_swing_low_confirmed(low_v, order=SWING_ORDER)
    # Pour chaque bougie, "creux ascendants" = le dernier swing low CONFIRMÉ
    # est plus haut que l'avant-dernier
    ascending = np.zeros(n, dtype=bool)
    last_lows = []
    for i in range(n):
        if confirmed[i]:
            last_lows.append(low_v[i - SWING_ORDER])
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

    sinewave = compute_cycle_phase_causal(close)  # bascule P0 : plus jamais la version batch en production
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
