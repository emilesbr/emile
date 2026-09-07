"""
Script de backtest — table "trade de tendance" à 5 étapes (`trend_table.py`),
PLAN.md backlog item 1. Rejoue sur BTC/ETH/BNB/SOL, mêmes profils (FAIBLE/
MODERE/AGRESSIF/TRES_AGRESSIF) que les autres moteurs, même chargement de
données que `backtest_phase2.py::load_h1`/`resample`.

Timeframe unique H4 (pas de validation croisée MTF ici -- H11 dans
trend_table.py : décision de scope volontaire, pour mesurer cette table
ISOLÉMENT plutôt que mélangée à l'effet déjà mesuré de la validation D1).

Rappel du principe du projet (PLAN.md, en tête) : la performance ci-dessous
ne sert JAMAIS à décider si la table de tendance doit être implémentée --
elle est un élément documenté de l'IP de Philippe Roux, implémenté
fidèlement (RULES_EXTRACTION.md §4) quel que soit le résultat. Les résultats
sont rapportés tels quels, y compris s'ils sont décevants.
"""
import pandas as pd
import sys
sys.path.insert(0, ".")
from backtest_phase2 import load_h1, resample
from trend_table import run_trend_table, load_volume, resample_volume, PROFILES_TREND


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        vol_h1 = load_volume(symbol)
        vol_h4 = resample_volume(vol_h1, "4h")
        for profile in PROFILES_TREND:
            res = run_trend_table(h4.copy(), vol_h4.copy(), profile)
            stage_time = res.pop("stage_time_%")
            rows.append({"symbol": symbol, "profile": profile, **res,
                         "time_ACCUMULATION_%": stage_time["ACCUMULATION"],
                         "time_POST_BREAKOUT_%": stage_time["POST_BREAKOUT"],
                         "time_PULLBACK_WATCH_%": stage_time["PULLBACK_WATCH"],
                         "time_EXCESS_WATCH_%": stage_time["EXCESS_WATCH"]})

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_trend_table_results.csv", index=False)


if __name__ == "__main__":
    main()
