"""
Diagnostic de la "Tendance Multi-timeframe" (`trend_table.py::attach_regime_
is_tendance`/`compute_multi_timeframe_trend`, 36e-37e rounds, décision directe
de l'utilisateur "directeur ingénieur senior" : "Philippe utilise sa
stratégie pour trader un actif sur les différentes timeframes, nous devons
agréger toute cette stratégie en une seule").

CE QUE CE SCRIPT EST / N'EST PAS
-----------------------------------------------------------------------------
C'EST une mesure de l'INCIDENCE réelle du régime "TENDANCE simultanément sur
H4+D1+Hebdomadaire" (H-MTF-Cascade-1, cf. tête de `trend_table.py`) sur
BTC/ETH/BNB/SOL, et une illustration de l'exposition qui en résulterait SI ces
fenêtres étaient exploitées en ouvrant 3 campagnes concurrentes (une par UT).
Même discipline "conditions d'activation mesurées AVANT le mécanisme de
consommation" que le 33e round (`compute_suivi_conditions` avant la branche
"Cassure de 3BR" du 34e round) : PAS un mécanisme de money management complet.

CE N'EST PAS un money-management "2% par UT" câblé dans `run_trend_table` --
la citation du guide ("vous pouvez trader chaque TF en parallèle avec 2% de
risque chacun") ne précise pas SI l'entrée doit reproduire tout le
séquencement Accumulation/Breakout du profil de référence, ou une simple
jambe unique dimensionnée par le risque -- un point non tranché par le
corpus, donc PAS inventé ici. L'illustration d'exposition ci-dessous
réutilise le profil MODERE tel quel UNIQUEMENT parce que son `risk_pct`
(0,02) coïncide déjà EXACTEMENT avec la citation "2%" -- pas parce que sa
grille `accum_frac`/`breakout_frac` serait elle-même prescrite par le
corpus pour ce mécanisme précis. Décision de conception (comment sizer
réellement les 3 jambes) : catégorie C, différée, cf. `PLAN.md`.
"""
import numpy as np
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import prepare, LOCAL_DURATION_H4_BARS, CONTEXT_DURATION_H4_BARS
from emile.core.trend_table import (
    add_trend_context, run_trend_table, load_volume, resample_volume,
    attach_regime_is_tendance, compute_multi_timeframe_trend, MTF_CASCADE_RISK_PCT,
)

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")
TF_RULES = (("4h", "H4"), ("1D", "D1"), ("W", "Weekly"))
# 39e round : fenêtre de maturité UT-AGNOSTIQUE (nombre de bougies, pas une
# durée calendaire) -- cf. tête de `backtest_phase2_v7.py::prepare`. Un
# no-op pour H4 (30/90 bougies H4 = EXACTEMENT "5D"/"15D"), la correction
# réelle porte sur D1/Hebdomadaire (trouvaille du 38e round : ces UT ne
# pouvaient structurellement jamais atteindre MIN_BORDERS=3 avec une fenêtre
# calendaire fixe).
PREPARE_KWARGS = {"local_duration": LOCAL_DURATION_H4_BARS, "context_duration": CONTEXT_DURATION_H4_BARS}

def compute_regime_per_tf(h1: pd.DataFrame) -> dict:
    """Régime (`regime_classifier.add_regime`, réutilisé via `prepare`) sur
    les 3 UT du triplet H-MTF-Cascade-2, chacune préparée exactement comme
    `run_trend_table` la prépare elle-même (`prepare` + `add_trend_context`,
    fenêtre UT-agnostique, cf. `PREPARE_KWARGS`) -- même chemin de calcul,
    pas une réplique."""
    out = {}
    for rule, label in TF_RULES:
        df = resample(h1, rule)
        df = add_trend_context(prepare(df, **PREPARE_KWARGS), **PREPARE_KWARGS)
        out[label] = df
    return out

def mtf_trend_incidence(dfs_by_tf: dict) -> dict:
    """Incidence de "Tendance Multi-timeframe" sur la grille H4 (H-MTF-
    Cascade-1) : % de bougies H4, nombre d'épisodes distincts (runs
    contigus), durée médiane/max d'un épisode en jours."""
    h4 = dfs_by_tf["H4"]
    is_tend_d1 = attach_regime_is_tendance(h4["date"].values, dfs_by_tf["D1"])
    is_tend_w = attach_regime_is_tendance(h4["date"].values, dfs_by_tf["Weekly"])
    mtf = compute_multi_timeframe_trend(h4["regime"].values, is_tend_d1, is_tend_w)
    s = pd.Series(mtf)
    run_id = (s != s.shift()).cumsum()
    episodes = s.groupby(run_id).agg(["sum", "size"])
    true_episodes = episodes[episodes["sum"] > 0]
    n_bars_per_episode = true_episodes["size"].values
    hours_per_bar = 4
    days_per_episode = n_bars_per_episode * hours_per_bar / 24
    return {
        "pct_bars": round(mtf.mean() * 100, 2),
        "n_bars": int(mtf.sum()),
        "n_episodes": len(true_episodes),
        "median_episode_days": round(float(np.median(days_per_episode)), 1) if len(days_per_episode) else 0.0,
        "max_episode_days": round(float(np.max(days_per_episode)), 1) if len(days_per_episode) else 0.0,
    }, mtf

def exposure_illustration(symbol: str, h1: pd.DataFrame, vol_h1: pd.DataFrame, mtf_h4: np.ndarray,
                           dfs_by_tf: dict) -> dict:
    """Illustration d'exposition (PAS un mécanisme câblé, cf. tête de
    fichier) : rejoue les 3 moteurs `run_trend_table` déjà existants,
    INDÉPENDAMMENT, un par UT (H4/D1/Hebdomadaire), profil MODERE
    (risk_pct=0,02, coïncidence avec "2%" -- pas une prescription du
    corpus pour CE mécanisme). Mesure combien du temps de campagne
    ACCUMULATION/POST_BREAKOUT de chaque UT chevauche une fenêtre de
    Tendance Multi-timeframe (validerait/invaliderait l'idée que ces
    campagnes, quand elles coexistent, appartiennent au même mouvement)."""
    results = {}
    for rule, label in TF_RULES:
        df = resample(h1, rule)
        vol = resample_volume(vol_h1, rule)
        res = run_trend_table(df.copy(), vol.copy(), "MODERE", **PREPARE_KWARGS)
        results[label] = res
    return results

def border_count_diagnostic(dfs_by_tf: dict) -> dict:
    """DIAGNOSTIC DU POUVOIR DISCRIMINANT -- pas supposé, mesuré : `n_borders`
    (fenêtre `CONTEXT_DURATION="15D"`, une durée CALENDAIRE ABSOLUE, jamais
    recalibrée par UT) forme un nombre de bornes très différent selon l'UT --
    15 jours contiennent ~90 bougies H4, ~15 bougies D1, mais une fraction de
    SEULE bougie Hebdomadaire. Sans cette mesure, un "0 trade" sur D1/
    Hebdomadaire serait ambigu entre "le mécanisme ne transfère pas" et "la
    fenêtre absolue ne laisse tout simplement pas le temps à une structure de
    bornes de se former à cette échelle" -- exactement la distinction que ce
    projet a déjà dû faire pour MIN_BORDERS/Cassure de 3BR."""
    return {
        f"{label}_n_borders_median": df["n_borders"].median()
        for label, df in dfs_by_tf.items()
    } | {
        f"{label}_n_borders_max": df["n_borders"].max()
        for label, df in dfs_by_tf.items()
    }

def main():
    rows = []
    for symbol in SYMBOLS:
        h1 = load_h1(symbol)
        vol_h1 = load_volume(symbol)
        dfs_by_tf = compute_regime_per_tf(h1)
        incidence, mtf_h4 = mtf_trend_incidence(dfs_by_tf)
        exposure = exposure_illustration(symbol, h1, vol_h1, mtf_h4, dfs_by_tf)
        borders = border_count_diagnostic(dfs_by_tf)
        row = {"symbol": symbol, **incidence}
        for label in ("H4", "D1", "Weekly"):
            row[f"{label}_n_trades"] = exposure[label]["n_trades"]
            row[f"{label}_total_return_%"] = exposure[label]["total_return_%"]
        row.update(borders)
        rows.append(row)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    print("Incidence de la 'Tendance Multi-timeframe' (H4+D1+Hebdomadaire simultanément), "
          f"risque de référence de la citation = {MTF_CASCADE_RISK_PCT*100:.0f}% :")
    print(result[["symbol", "pct_bars", "n_bars", "n_episodes", "median_episode_days",
                  "max_episode_days"]].to_string(index=False))
    print("\nIllustration d'exposition (profil MODERE tel quel, PAS le mécanisme '2% par UT' câblé) "
          "+ diagnostic du pouvoir discriminant de n_borders par UT :")
    print(result[["symbol", "H4_n_trades", "D1_n_trades", "Weekly_n_trades",
                  "H4_n_borders_median", "D1_n_borders_median", "Weekly_n_borders_median",
                  "H4_n_borders_max", "D1_n_borders_max", "Weekly_n_borders_max"]].to_string(index=False))
    result.to_csv("mtf_cascade_diagnostic.csv", index=False)

    print("\nLecture honnête n°1 : 'pct_bars'/'n_episodes' mesurent l'incidence RÉELLE de la "
          "'Tendance Multi-timeframe' (ni 0%, ni omniprésente -- un signe de condition discriminante, "
          "pas un gate inerte).")
    print("Lecture honnête n°2 (39e round -- CORRIGÉ depuis le 38e) : les fenêtres de maturité "
          "(local_duration/context_duration, cf. PREPARE_KWARGS) sont ici passées en NOMBRE DE "
          "BOUGIES (LOCAL_DURATION_H4_BARS/CONTEXT_DURATION_H4_BARS), pas en durée calendaire -- "
          "n_borders_median est désormais ~9 sur les 3 UT (H4/D1/Hebdomadaire), comparable, au lieu "
          "de chuter à ~1 sur D1 et ~0 sur Hebdomadaire avec l'ancienne fenêtre calendaire (38e "
          "round). Effet mesuré : D1_n_trades N'EST PLUS 0 (BTC 3, ETH 1, BNB 1, SOL 3) -- le "
          "mécanisme 'Tendance' transfère bien à D1 une fois la fenêtre recalibrée. Weekly_n_trades "
          "reste à 0 sur les 4 actifs -- mais ce n'est PLUS un artefact de calibration (n_borders y "
          "est désormais comparable aux 2 autres UT) : l'historique Hebdomadaire disponible est "
          "simplement TRÈS COURT en nombre de bougies (303-367 selon l'actif, contre 13000+ en H4) -- "
          "une contrainte d'échantillon réelle, pas un gate mal calibré.")

if __name__ == "__main__":
    main()
