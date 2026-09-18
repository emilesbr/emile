"""
Mesure honnête de `run_repli_neuneu` (`neuneu_repli.py`, 46e round --
`docs/PLAN.md`) sur données réelles BTC/ETH/BNB/SOL, H4 (`LOCAL_DURATION_
H4_BARS`/`CONTEXT_DURATION_H4_BARS`, 39e round -- même calibration que le
reste des moteurs de ce projet sur cette UT, pas une nouvelle fenêtre
inventée).

Ce module N'EST PAS câblé dans `faithful.py`/`unified_protocol.py` (cf.
tête de `neuneu_repli.py`) -- moteur STANDALONE, mesuré isolément, même
statut que `h1_timeframe_bench.py` avant son propre câblage.

`main()` : mesure de référence, `objectif_close_frac` par défaut (0,50,
inchangé depuis le 46e round). `main_objectif_close_frac_sweep()` (62e
round, demande directe de l'utilisateur -- "qu'est-ce qui améliorerait la
rentabilité ? imagine et teste") : balayage de `objectif_close_frac` sur
les 4 actifs, cf. `docs/PLAN.md` section "62e application" pour la lecture
honnête (monotone sur les 4 actifs, mais mesure IN-SAMPLE -- BTC/BNB
restent négatifs même au meilleur réglage testé).

`main_yearly_by_timeframe()` (63e round, demande directe de l'utilisateur --
"je veux connaître le rendement cumulé de tous les trades sur chaque année
pour chaque actif sur toutes les timeframes") : rejoue `run_repli_neuneu`
sur les 3 UT d'EXÉCUTION NATIVE déjà testées ailleurs dans ce projet pour
ce protocole (H1 `h1_timeframe_bench.py`, H4 `neuneu_repli.py` lui-même,
M15 `m15_timeframe_bench.py` -- PAS de nouvelle UT inventée pour ce round),
par actif, par année calendaire. `LOCAL_DURATION_*_BARS`/`CONTEXT_DURATION_
*_BARS` : MÊME cible calendaire 5D/15D que `LOCAL_DURATION_H4_BARS`/
`CONTEXT_DURATION_H4_BARS` (39e round, `backtest_phase2_v7.py`), simplement
exprimée dans le nombre de bougies de chaque UT (24h/1h=24 bougies H1 par
jour, 24*4=96 bougies M15 par jour) -- aucun nouveau chiffre inventé, une
conversion d'unité de la même valeur calendaire déjà citée. Découpage par
année : MÊME convention que `cross_stress_test_unified_capital_tiers.py::
yearly_breakdown_by_tier` (le signal causal est calculé sur l'historique
COMPLET, `run_repli_neuneu(..., start=, end=)` restreint SEULEMENT la
boucle de compte à l'année, capital remis à 1,0 à chaque début d'année --
pas un mark-to-market d'une position à cheval sur 2 années, un redémarrage
propre, comme le précédent déjà établi).
"""
import numpy as np
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, load_m15, resample
from emile.backtests.backtest_phase2_v7 import LOCAL_DURATION_H4_BARS, CONTEXT_DURATION_H4_BARS
from emile.core.neuneu_repli import run_repli_neuneu, compute_repli_neuneu_signal, NEUNEU_OBJECTIF_CLOSE_FRAC

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")

# H1/M15 : MÊME cible calendaire 5D/15D que LOCAL_DURATION_H4_BARS/
# CONTEXT_DURATION_H4_BARS ci-dessus (39e round) -- exprimée en bougies de
# chaque UT (5*24=120/15*24=360 en H1 ; 5*96=480/15*96=1440 en M15, 96
# bougies M15 par jour de 24h). Aucune donnée manquante sur ce projet (H1 et
# M15 natifs disponibles pour les 4 actifs, cf. `CLAUDE.md`).
LOCAL_DURATION_H1_BARS, CONTEXT_DURATION_H1_BARS = 120, 360
LOCAL_DURATION_M15_BARS, CONTEXT_DURATION_M15_BARS = 480, 1440

TIMEFRAME_DURATIONS = {
    "H1": (LOCAL_DURATION_H1_BARS, CONTEXT_DURATION_H1_BARS),
    "H4": (LOCAL_DURATION_H4_BARS, CONTEXT_DURATION_H4_BARS),
    "M15": (LOCAL_DURATION_M15_BARS, CONTEXT_DURATION_M15_BARS),
}


def _load_timeframe_df(symbol: str, timeframe: str) -> pd.DataFrame:
    """Charge la donnée native de `timeframe` -- MÊME remapping que
    `h1_timeframe_bench.py`/`m15_timeframe_bench.py` (H1 natif, H4 =
    resample(H1, "4h"), M15 natif via `load_m15`, jamais un resample vers
    le HAUT depuis une UT plus lente qui inventerait de la donnée)."""
    if timeframe == "H1":
        return load_h1(symbol)
    if timeframe == "H4":
        return resample(load_h1(symbol), "4h")
    if timeframe == "M15":
        return load_m15(symbol)
    raise ValueError(f"timeframe inconnu: {timeframe!r}, attendu parmi {tuple(TIMEFRAME_DURATIONS)}")


def main():
    rows = []
    for symbol in SYMBOLS:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        sig = compute_repli_neuneu_signal(h4, CONTEXT_DURATION_H4_BARS, LOCAL_DURATION_H4_BARS)
        n_signals = int(sig["long_signal"].sum())
        res = run_repli_neuneu(h4, CONTEXT_DURATION_H4_BARS, LOCAL_DURATION_H4_BARS)
        rows.append({
            "symbol": symbol, "n_pattern_signals": n_signals,
            "n_trades": res["n_trades"], "total_return_%": res["total_return_%"],
            "max_dd_%": res["max_dd_%"], "win_rate_%": res["win_rate_%"],
            "profit_factor": res["profit_factor"],
        })
        print(f"  {symbol} ok ({n_signals} signaux, {res['n_trades']} trades)", flush=True)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("results/neuneu_repli_results.csv", index=False)


def main_objectif_close_frac_sweep():
    FRACS = (0.0, 0.25, NEUNEU_OBJECTIF_CLOSE_FRAC, 0.75, 1.0)
    rows = []
    for symbol in SYMBOLS:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        row = {"symbol": symbol}
        for frac in FRACS:
            res = run_repli_neuneu(h4, CONTEXT_DURATION_H4_BARS, LOCAL_DURATION_H4_BARS,
                                    objectif_close_frac=frac)
            row[f"n_trades_frac{frac}"] = res["n_trades"]
            row[f"win_rate_frac{frac}_%"] = res["win_rate_%"]
            row[f"profit_factor_frac{frac}"] = res["profit_factor"]
            row[f"return_frac{frac}_%"] = res["total_return_%"]
            row[f"max_dd_frac{frac}_%"] = res["max_dd_%"]
        rows.append(row)
        print(f"  {symbol} ok", flush=True)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", 40)
    print(result.to_string(index=False))
    result.to_csv("results/neuneu_repli_objectif_close_frac_sweep_results.csv", index=False)


def main_yearly_by_timeframe():
    rows = []
    for symbol in SYMBOLS:
        for timeframe, (local_dur, context_dur) in TIMEFRAME_DURATIONS.items():
            df = _load_timeframe_df(symbol, timeframe)
            dates = pd.to_datetime(df["date"])
            years = sorted(dates.dt.year.unique())
            for y in years:
                idx = np.where(dates.dt.year == y)[0]
                if len(idx) == 0:
                    continue
                start, end = max(int(idx[0]), 1), int(idx[-1]) + 1
                if start >= end:
                    continue
                res = run_repli_neuneu(df, context_dur, local_dur, start=start, end=end)
                rows.append({
                    "symbol": symbol, "timeframe": timeframe, "year": int(y),
                    "n_trades": res["n_trades"], "total_return_%": res["total_return_%"],
                    "max_dd_%": res["max_dd_%"], "win_rate_%": res["win_rate_%"],
                    "profit_factor": res["profit_factor"],
                })
            print(f"  {symbol} {timeframe} ok", flush=True)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("results/neuneu_repli_yearly_by_timeframe_results.csv", index=False)
    return result


if __name__ == "__main__":
    main()
