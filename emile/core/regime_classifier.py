"""
Classificateur de régime de marché — élément manquant identifié : aucun de
nos moteurs (v4, v5) ne distinguait Range vs Tendance vs Bulle avant
d'entrer, alors que c'est la règle de base n°1 du manuel PDF officiel
("TOUJOURS TRADER DANS UN CONTEXTE", RULES_EXTRACTION.md section 1).

4 régimes (fréquences approximatives du manuel : Range neutre ~50%, Range
tendanciel ~25%, Tendance ~20%, Bulle/Excès ~5%) :
  - RANGE_NEUTRE   : canal de contexte stable, pas de biais directionnel net
  - RANGE_TENDANCIEL : range, mais le contexte de l'UT supérieure est
    directionnellement aligné (approximé ici par la pente du canal lui-même,
    faute d'une vraie UT supérieure dans ce script autonome)
  - TENDANCE       : pente du canal marquée + prix majoritairement d'un côté
  - EXCES          : canal trop large (boîtes disjointes) OU trop étroit
    (squeeze) -> "NE PAS TRADER" selon le manuel

Règle du manuel explicitement respectée : "en cas de doute, toujours RANGE".

AJOUT — détecteur "canal TRÈS LARGE" (`compute_wide_channel` en bas de
fichier), support de la règle de volatilité "Stop Loss = taille du canal"
de `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` §5. Placé ICI et pas
ailleurs pour une raison de principe déjà établie dans ce projet ("même
terme = même définition partout, pas une nouvelle par module") : ce fichier
est DÉJÀ celui qui possède le vocabulaire "canal trop large" (EXCES) et la
machinerie de percentile glissant causal qui le mesure. Le MÉCANISME de
sizing associé, lui, vit dans `position_engine.py` (qui possède le sizing) —
cf. le bloc "STOP LOSS = TAILLE DU CANAL" en tête de ce fichier-là pour la
citation exacte, les 4 hypothèses (H-Canal-Large-1..4) et la justification
complète du seuil retenu.
"""
import pandas as pd
import numpy as np

SLOPE_WINDOW = "20D"      # fenêtre réelle pour la pente du canal (calibrée en durée, pas en bougies)
RECENT_WINDOW = 10         # bougies pour la position récente du prix vs médiane
TREND_SLOPE_THRESHOLD = 1.5   # % , seuil de pente pour "tendance" (cf. manuel: slope_pct > 1.5)
# CALIBRATION : les seuils absolus du manuel (1%/12%) sont calibrés pour le
# vrai canal PRO Framework, pas pour notre approximation EMA+/-2xATR (dont la
# largeur médiane sur crypto est ~17%, bien au-dessus de 12%). On utilise donc
# des seuils PERCENTILES ADAPTATIFS (fenêtre glissante causale, pas de
# lookahead) plutôt que les valeurs absolues du manuel, pour cibler
# approximativement les mêmes fréquences relatives (squeeze/excès rares).
PCTL_WINDOW = 250          # bougies, fenêtre glissante pour les percentiles adaptatifs
SQUEEZE_PCTL = 0.05
EXCESS_PCTL = 0.95
# Seuil "canal TRÈS LARGE" (hypothèse H-Canal-Large-3, cf. position_engine.py) —
# strictement EN DESSOUS de EXCESS_PCTL : "très large" est un état de
# DIMENSIONNEMENT (le corpus dit "ajusté selon volatilité"), pas d'abstention
# ("Bulle/Excès -> NE PAS TRADER"). Les deux doivent rester distincts, sinon la
# règle de volatilité serait vacueuse dans tout moteur qui refuse déjà de
# trader en régime EXCES.
WIDE_PCTL = 0.80

def add_regime(df: pd.DataFrame, ctx_median: pd.Series, ctx_width_pct: pd.Series) -> pd.DataFrame:
    """Ajoute la colonne 'regime' (RANGE_NEUTRE/RANGE_TENDANCIEL/TENDANCE/EXCES).
    ctx_median : médiane du canal de contexte (ex. EMA lente)
    ctx_width_pct : largeur du canal en % de la médiane"""
    df = df.copy()
    ts_median = ctx_median.copy()
    ts_median.index = pd.to_datetime(df["date"])
    slope_ref = ts_median.shift(freq=pd.Timedelta(SLOPE_WINDOW)).reindex(ts_median.index, method="nearest")
    # Pente réelle : comparaison directe avec la valeur d'il y a ~20 jours
    slope_pct = ((ts_median.values - slope_ref.values) / slope_ref.values * 100)

    close = df["close"].values
    above_median = close > ctx_median.values
    recent_above_frac = pd.Series(above_median).rolling(RECENT_WINDOW).mean().values

    # Seuils adaptatifs (percentiles glissants CAUSAUX, calculés sur le passé
    # uniquement -> shift(1) pour ne jamais inclure la bougie courante)
    width_series = ctx_width_pct.reset_index(drop=True)
    squeeze_thresh = width_series.shift(1).rolling(PCTL_WINDOW).quantile(SQUEEZE_PCTL).values
    excess_thresh = width_series.shift(1).rolling(PCTL_WINDOW).quantile(EXCESS_PCTL).values

    regimes = []
    for i in range(len(df)):
        w = ctx_width_pct.values[i]
        if (np.isnan(w) or np.isnan(slope_pct[i]) or np.isnan(recent_above_frac[i])
                or np.isnan(squeeze_thresh[i]) or np.isnan(excess_thresh[i])):
            regimes.append("RANGE_NEUTRE")  # "en cas de doute, range" (manuel)
            continue
        if w < squeeze_thresh[i] or w > excess_thresh[i]:
            regimes.append("EXCES")
            continue
        if slope_pct[i] > TREND_SLOPE_THRESHOLD and recent_above_frac[i] >= 0.7:
            regimes.append("TENDANCE")
        elif slope_pct[i] > TREND_SLOPE_THRESHOLD * 0.5 and recent_above_frac[i] >= 0.5:
            regimes.append("RANGE_TENDANCIEL")
        else:
            regimes.append("RANGE_NEUTRE")  # défaut = doute = range (règle explicite du manuel)
    df["regime"] = regimes
    return df

def compute_wide_channel(ctx_width_pct, pctl: float = WIDE_PCTL,
                          window: int = PCTL_WINDOW) -> np.ndarray:
    """"Canal TRÈS LARGE" — détecteur de la règle de volatilité de
    `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` §5 (citation exacte et
    hypothèses : bloc "STOP LOSS = TAILLE DU CANAL" en tête de
    `position_engine.py`). Retourne un array booléen aligné sur
    `ctx_width_pct`.

    Réutilise EXACTEMENT la machinerie déjà en place dans `add_regime`
    ci-dessus pour dire "canal trop large" — même série d'entrée
    (`ctx_width_pct`, la largeur du canal Extreme Channel en % de sa médiane,
    calculée une seule fois par `backtest_phase2_v7.py::prepare` puis
    transmise aux deux), même fenêtre (`PCTL_WINDOW`), même construction
    causale (`.shift(1)` avant le rolling : la bougie courante n'entre JAMAIS
    dans le calcul de son propre seuil), même comparaison stricte (`>`).
    Seul le percentile change (`WIDE_PCTL` au lieu de `EXCESS_PCTL`) — ce
    n'est donc pas une nouvelle définition du canal ni une nouvelle notion de
    "large", c'est la même graduée à un cran moins extrême.

    NaN (warmup : moins de `window` bougies d'historique, ou largeur non
    calculable) -> False, c'est-à-dire "pas très large" -> règle STANDARD
    ("Stop Loss = taille du canal"), jamais la règle de volatilité. Même
    esprit de défaut prudent que "en cas de doute, toujours RANGE" du manuel
    (ci-dessus) : en cas de doute, on ne modifie pas le dimensionnement."""
    w = pd.Series(np.asarray(ctx_width_pct, dtype=float)).reset_index(drop=True)
    thresh = w.shift(1).rolling(window).quantile(pctl)
    return (w > thresh).fillna(False).to_numpy(dtype=bool)

def compute_squeeze(ctx_width_pct, pctl: float = SQUEEZE_PCTL,
                     window: int = PCTL_WINDOW) -> np.ndarray:
    """"SQUEEZE" (canal TRÈS ÉTROIT) — miroir exact de `compute_wide_channel`
    ci-dessus, même machinerie, seule la direction de la comparaison change
    (`<` au lieu de `>`) puisqu'un squeeze est un canal trop ÉTROIT, pas trop
    large. Retourne un array booléen aligné sur `ctx_width_pct`.

    Ajouté pour le mécanisme "invalidation 3BR par squeeze sur l'UT+1"
    (`docs/GUIDE_STRATEGIE_PRO_INDICATORS.md` section 3.2, citation exacte :
    *"Si le range se forme juste après un SQUEEZE sur l'unité de temps
    supérieure, il faudra alors éviter de trader cette 3BR"*, `PLAN.md`
    "31e application") -- ce niveau ("l'UT propre est en squeeze") est déjà
    plié dans `add_regime` (régime `EXCES`, ligne `w < squeeze_thresh[i] or w
    > excess_thresh[i]`), mais `add_regime` ne permet pas de savoir SI un
    `EXCES` donné vient d'un squeeze ou d'un canal trop large -- exactement le
    même besoin de granularité que celui qui a motivé `compute_wide_channel`
    (une fonction dédiée, pas une nouvelle définition de canal).

    H-Squeeze-UT1-1 (hypothèse d'opérationnalisation, le corpus ne chiffre
    pas "juste après") : le squeeze D1 est lu de façon CONTEMPORAINE (même
    jointure causale que `regime_d1`, aucun délai supplémentaire inventé) --
    pas une fenêtre de recul explicite, le percentile glissant de 250 bougies
    fait déjà persister l'état "squeeze" sur plusieurs bougies consécutives
    de façon causale, ce qui capture "juste après" sans ajouter de paramètre.

    NaN (warmup) -> False ("pas squeeze"), même convention prudente que
    `compute_wide_channel`/`add_regime`."""
    w = pd.Series(np.asarray(ctx_width_pct, dtype=float)).reset_index(drop=True)
    thresh = w.shift(1).rolling(window).quantile(pctl)
    return (w < thresh).fillna(False).to_numpy(dtype=bool)

if __name__ == "__main__":
    import sys

    from emile.backtests.backtest_phase2 import load_h1, resample, atr, EMA_SLOW

    df = resample(load_h1("BTCUSDT"), "1D")
    ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    atr_v = atr(df, 14)
    width_pct = (2 * 2 * atr_v) / ema_slow * 100  # canal EMA +/- 2*ATR
    scored = add_regime(df, ema_slow, width_pct)
    print(scored["regime"].value_counts())
    print("\n% du temps par régime :")
    print((scored["regime"].value_counts(normalize=True) * 100).round(1))
