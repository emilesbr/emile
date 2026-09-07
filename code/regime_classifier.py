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


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    sys.path.insert(0, "/home/user/emile/code")
    from backtest_phase2 import load_h1, resample, atr, EMA_SLOW

    df = resample(load_h1("BTCUSDT"), "1D")
    ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    atr_v = atr(df, 14)
    width_pct = (2 * 2 * atr_v) / ema_slow * 100  # canal EMA +/- 2*ATR
    scored = add_regime(df, ema_slow, width_pct)
    print(scored["regime"].value_counts())
    print("\n% du temps par régime :")
    print((scored["regime"].value_counts(normalize=True) * 100).round(1))
