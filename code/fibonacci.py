"""
Fibonacci retracement — filtre de qualité d'entrée additionnel (backlog
`PLAN.md` item 4, `COUVERTURE_ENSEIGNEMENTS.md` ligne Fibonacci).

Règle extraite fidèlement des 5 sources citées pour cet item par
`COUVERTURE_ENSEIGNEMENTS.md` (#9, #10, #11, #13, #14 — identifiées via
`TRADING_LESSONS_INDEX.md`) :
  #9  = TRADING_LESSONS_MTF_SUIVI_TENDANCE.md
  #10 = TRADING_LESSONS_ZONE_ACCUMULATION.md
  #11 = TRADING_LESSONS_TROISIEME_BORNE.md
  #13 = TRADING_LESSONS_PULLBACK_MATURITE.md
  #14 = TRADING_LESSONS_STRUCTURES_ALTERATIONS.md

IMPORTANT — constat honnête avant l'implémentation : la "zone dorée" 38%-
61,8% supposée au départ de ce chantier (énoncé de la tâche) N'EST PAS ce
que ces 5 sources disent une fois relues précisément. Elles ne convergent
PAS sur un unique intervalle — chacune donne une règle légèrement
différente, resynthétisée ci-dessous plutôt que forcée dans un chiffre
unique commode qui masquerait la divergence réelle du corpus :

  - #13 (PULLBACK_MATURITE — la plus précise, table GO/WAIT directement
    implémentable) : 23% = seuil MINIMAL de retracement pour valider
    l'entrée en zone (en-dessous = simple pause de tendance, pas un
    pullback) ; 38% = niveau "standard et optimal" ; 50% = "exceptionnel,
    rare dans les tendances à forte vélocité". "Règle des 50%" : le
    pullback n'est validé QUE SI retracement >= 23% ET pénétration dans les
    50% inférieurs du contexte (deux conditions cumulatives, pas une
    seule). Table de décision : GO si cluster Fibonacci entre 23% et 38%,
    WAIT hors de ces niveaux.
  - #10 (ZONE_ACCUMULATION) : zone Fibonacci favorable = "cluster 38-50%"
    pour la maturité d'une zone d'accumulation ; "61% = seuil de tolérance
    MAXIMUM". Red Flag explicite si "clôture maintenue au-delà de 61% de
    la structure" (invalidation, redevient un simple range).
  - #11 (TROISIEME_BORNE) : le pullback qui suit la cassure/clôture
    confirmée d'une 3ème borne valide vise spécifiquement le niveau
    "Fibonacci 61,8%" — un niveau PONCTUEL (pas un intervalle), pour un
    pattern plus spécifique (retest post-breakout d'une 3ème borne), pas
    une règle d'entrée générale.
  - #9 (MTF_SUIVI_TENDANCE) et #14 (STRUCTURES_ALTERATIONS) : AUCUN niveau
    de retracement chiffré. #9 documente la règle multi-timeframe "UT+2",
    pas Fibonacci. #14 mentionne des "extensions de Fibonacci" mais pour
    la PRISE DE PROFIT en Vague 5 (sorties), pas pour un critère d'entrée
    par profondeur de retracement. Ces 2 des 5 sources attribuées à cette
    ligne par `COUVERTURE_ENSEIGNEMENTS.md` ne documentent en réalité
    aucune règle de retracement d'entrée — à noter honnêtement plutôt que
    de prétendre une convergence à 5/5 qui n'existe pas.

Point de vigilance additionnel, à ne pas cacher : le niveau "76,4%" cité
dans la ligne récapitulative de `COUVERTURE_ENSEIGNEMENTS.md`
("23%/38%/50%/61,8%/76,4%") N'APPARAÎT DANS AUCUNE des 5 sources ci-dessus
une fois relues précisément — c'est un niveau Fibonacci standard, cohérent
avec les autres, mais ce chiffre précis ne provient pas des 5 sources qui
lui sont attribuées (probablement une généralisation implicite depuis
d'autres sources du corpus à 17 sources, non vérifiées ici). Documenté
plutôt que reproduit sans vérification — cf. `COUVERTURE_ENSEIGNEMENTS.md`
pour la mise à jour de cette ligne.

Synthèse retenue pour l'implémentation (résume les points ci-dessus sans
forcer un faux consensus à 5/5) :
  - Zone FAVORABLE = [FAVORABLE_MIN, FAVORABLE_MAX] = [23%, 61,8%] — union
    du seuil minimal de validation (#13) et du plafond de tolérance
    maximum avant invalidation (#10) / du niveau d'intervention ponctuel
    du pattern 3ème borne (#11).
  - Sous-zone OPTIMALE = [FAVORABLE_MIN, FAVORABLE_OPTIMAL_MAX] = [23%,
    50%] — le "standard et optimal" 38% de #13 encadré par son propre
    "exceptionnel" 50%, cohérent avec le cluster 38-50% de #10.
  - En-deçà de 23% (< FAVORABLE_MIN) = défavorable (simple pause de
    tendance, pas un pullback qualifiant, #13).
  - Au-delà de 61,8% (> FAVORABLE_MAX) = défavorable / invalidé (Red Flag
    explicite de #10).

Pivot de mesure — quel haut/bas sert de référence : le DERNIER mouvement
directionnel haussier complet détecté (dernier swing low, suivi
chronologiquement du dernier swing high) — cohérent avec un projet
long-only (`proxy_v2.py`, tous les moteurs `backtest_phase2_*.py`).
Détection de swing réutilisée à l'identique de
`proxy_v2.py::compute_ascending_lows` : `scipy.signal.argrelextrema`,
même `order` (3 bougies de chaque côté). Ce n'est pas une nouvelle
détection ad hoc, c'est la même déjà en production ailleurs dans ce
projet (également utilisée pour `n_borders` dans
`backtest_phase2_v6.py`/`_v7.py`).
"""
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

# Cohérent avec proxy_v2.SWING_ORDER (même détection de swing réutilisée).
SWING_ORDER = 3

# Cf. synthèse de la règle extraite en tête de fichier.
FAVORABLE_MIN = 0.23
FAVORABLE_OPTIMAL_MAX = 0.50
FAVORABLE_MAX = 0.618


def compute_swing_highs_lows(df: pd.DataFrame, order: int = SWING_ORDER) -> tuple:
    """Détecte les swing highs/lows par `scipy.signal.argrelextrema`, même
    convention que `proxy_v2.py::compute_ascending_lows` (comparateurs
    np.greater_equal / np.less_equal, même `order`). Retourne deux arrays
    booléens (is_swing_high, is_swing_low), alignés sur l'index de `df`.

    NB (même compromis déjà présent ailleurs dans le projet, pas une
    faiblesse nouvelle introduite ici) : un swing à l'indice j n'est
    confirmé par argrelextrema qu'une fois `order` bougies après j connues
    — c'est le même comportement que `n_borders` dans
    `backtest_phase2_v6.py`/`_v7.py`, qui utilise déjà exactement cette
    fonction sur toute la série avant que les moteurs n'utilisent
    `score[i-1]`/`n_borders_v[i-1]` (donc une bougie de retard) pour leurs
    décisions."""
    high_v = df["high"].values
    low_v = df["low"].values
    swing_high_idx = argrelextrema(high_v, np.greater_equal, order=order)[0]
    swing_low_idx = argrelextrema(low_v, np.less_equal, order=order)[0]
    is_swing_high = np.zeros(len(df), dtype=bool)
    is_swing_high[swing_high_idx] = True
    is_swing_low = np.zeros(len(df), dtype=bool)
    is_swing_low[swing_low_idx] = True
    return is_swing_high, is_swing_low


def compute_retracement(df: pd.DataFrame, order: int = SWING_ORDER) -> np.ndarray:
    """Calcule, pour chaque bougie, le % de retracement du prix de clôture
    par rapport au dernier mouvement directionnel HAUSSIER détecté (dernier
    swing low, suivi chronologiquement par le dernier swing high) :

        retracement_pct = (dernier_swing_high - close) / (dernier_swing_high - dernier_swing_low)

    Un mouvement n'est considéré valide pour le calcul QUE si :
      1. le dernier swing low détecté précède chronologiquement le dernier
         swing high détecté (on est bien en phase de retracement APRÈS un
         plus haut, pas avant un futur plus haut) ;
      2. ce plus haut est strictement supérieur à ce plus bas (amplitude
         du mouvement > 0, jamais de division par zéro/négatif).

    Retourne un array de fractions (0.23 pour 23%, pas 23), NaN tant
    qu'aucun mouvement complet low->high n'a encore été confirmé (warmup)."""
    close = df["close"].values
    high_v = df["high"].values
    low_v = df["low"].values
    is_swing_high, is_swing_low = compute_swing_highs_lows(df, order=order)
    n = len(df)
    retracement = np.full(n, np.nan)

    last_high_px, last_high_i = np.nan, -1
    last_low_px, last_low_i = np.nan, -1

    for i in range(n):
        if is_swing_low[i]:
            last_low_px, last_low_i = low_v[i], i
        if is_swing_high[i]:
            last_high_px, last_high_i = high_v[i], i

        if last_high_i > last_low_i >= 0 and last_high_px > last_low_px:
            amplitude = last_high_px - last_low_px
            retracement[i] = (last_high_px - close[i]) / amplitude

    return retracement


def classify_retracement(retracement_pct) -> tuple:
    """Classification favorable/optimale à partir d'un array (ou scalaire)
    de fractions de retracement — cf. la règle extraite en tête de fichier.
    NaN (pas encore de mouvement confirmé) est naturellement classé comme
    non favorable/non optimal (toute comparaison avec NaN vaut False)."""
    r = np.asarray(retracement_pct, dtype=float)
    favorable = (r >= FAVORABLE_MIN) & (r <= FAVORABLE_MAX)
    optimal = (r >= FAVORABLE_MIN) & (r <= FAVORABLE_OPTIMAL_MAX)
    return favorable, optimal


def add_fibonacci_columns(df: pd.DataFrame, order: int = SWING_ORDER) -> pd.DataFrame:
    """Ajoute `fib_retracement_pct` (fraction, NaN si pas de mouvement
    confirmé), `fib_favorable` (bool, zone [23%, 61,8%]) et `fib_optimal`
    (bool, sous-zone [23%, 50%]) à `df`. N'utilise QUE des données connues
    à l'instant de chaque bougie (le calcul est causal dans son usage,
    modulo le même compromis de confirmation de swing différée par
    `order` bougies déjà documenté dans `compute_swing_highs_lows` — comme
    partout ailleurs dans ce projet où ce détecteur est déjà utilisé)."""
    df = df.copy()
    retracement = compute_retracement(df, order=order)
    favorable, optimal = classify_retracement(retracement)
    df["fib_retracement_pct"] = retracement
    df["fib_favorable"] = favorable
    df["fib_optimal"] = optimal
    return df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from backtest_phase2 import load_h1, resample

    df = resample(load_h1("BTCUSDT"), "1D")
    scored = add_fibonacci_columns(df)
    print(scored[["date", "close", "fib_retracement_pct", "fib_favorable", "fib_optimal"]].tail(40).to_string(index=False))
    print("\nRépartition (BTC D1) :")
    print("favorable :", scored["fib_favorable"].mean().round(3))
    print("optimal   :", scored["fib_optimal"].mean().round(3))
    print("NaN (pas encore de mouvement confirmé) :", scored["fib_retracement_pct"].isna().mean().round(3))
