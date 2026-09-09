"""
Script de backtest — table "trade de tendance" à 5 étapes (`trend_table.py`),
PLAN.md backlog item 1. Rejoue sur BTC/ETH/BNB/SOL, mêmes profils (FAIBLE/
MODERE/AGRESSIF/TRES_AGRESSIF) que les autres moteurs, même chargement de
données que `backtest_phase2.py::load_h1`/`resample`.

Timeframe unique H4 par défaut (pas de validation croisée MTF -- H11 dans
trend_table.py : décision de scope volontaire, pour mesurer cette table
ISOLÉMENT plutôt que mélangée à l'effet déjà mesuré de la validation D1).

VARIANTE AJOUTÉE (contrainte "espace libre" MTF avant le Breakout, H13-H17 de
`trend_table.py`) : la colonne `space_gate` distingue `off` (comportement
historique, ligne à ligne identique aux versions précédentes de ce CSV) de
`on_x<mult>` (gate actif, obstacles = borne haute du canal D1 (UT+1) et
Hebdomadaire (UT+2), rendement escompté = amplitude du range local, cf. la
citation de `TRADING_LESSONS_BREAKOUT_RATIO11.md` l.17 reproduite dans
`trend_table.py`). Le multiplicateur 1.0 est la seule valeur citée par le
corpus (Ratio 1:1) ; 0.5 et 1.5 sont rejoués UNIQUEMENT comme mesure de
sensibilité, jamais comme calibrage.

Un second CSV (`phase2_trend_table_space_gate_diagnostic.csv`) mesure le
POUVOIR DISCRIMINANT du gate indépendamment de la performance. Il est
nécessaire : sur ce jeu de données, les campagnes de tendance n'atteignent
l'étape Breakout QUE pour le profil FAIBLE (les 3 autres profils se referment
systématiquement en Accumulation), donc 12 des 16 couples actif x profil ne
PEUVENT PAS bouger, quel que soit le gate. Un écart de 0,0 sur ces 12 couples
ne dit rien de la règle -- exactement la distinction que la sensibilité
MIN_BORDERS avait dû faire (0,0 pt mesuré, mais gate INERTE).

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
from trend_table import (run_trend_table, load_volume, resample_volume, PROFILES_TREND,
                          breakout_space_binding_stats)

# 1.0 = Ratio 1:1, la seule valeur citée par le corpus (H15) ; les deux autres
# ne servent qu'à mesurer la sensibilité de la règle, pas à la calibrer.
SPACE_MULTS = (0.5, 1.0, 1.5)


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    diag_rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")        # UT+1 (obstacles), cf. H14
        weekly = resample(h1, "W")     # UT+2 (obstacles), cf. H14
        vol_h1 = load_volume(symbol)
        vol_h4 = resample_volume(vol_h1, "4h")

        for mult in SPACE_MULTS:
            diag_rows.append({"symbol": symbol, **breakout_space_binding_stats(
                h4.copy(), vol_h4.copy(), d1.copy(), weekly.copy(), mult)})

        variants = [("off", {})]
        variants += [(f"on_x{mult}", {"use_breakout_space_gate": True, "df_ut1": d1,
                                       "df_ut2": weekly, "space_mult": mult})
                     for mult in SPACE_MULTS]
        for profile in PROFILES_TREND:
            for gate_name, kwargs in variants:
                kwargs = {k: (v.copy() if isinstance(v, pd.DataFrame) else v)
                          for k, v in kwargs.items()}
                res = run_trend_table(h4.copy(), vol_h4.copy(), profile, **kwargs)
                stage_time = res.pop("stage_time_%")
                rows.append({"symbol": symbol, "profile": profile, "space_gate": gate_name, **res,
                             "time_ACCUMULATION_%": stage_time["ACCUMULATION"],
                             "time_POST_BREAKOUT_%": stage_time["POST_BREAKOUT"],
                             "time_PULLBACK_WATCH_%": stage_time["PULLBACK_WATCH"],
                             "time_EXCESS_WATCH_%": stage_time["EXCESS_WATCH"]})

    result = pd.DataFrame(rows)
    diag = pd.DataFrame(diag_rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    print(result.to_string(index=False))
    print()
    print("Pouvoir discriminant du gate 'espace libre' (indépendant de la performance) :")
    print(diag.to_string(index=False))
    result.to_csv("phase2_trend_table_results.csv", index=False)
    diag.to_csv("phase2_trend_table_space_gate_diagnostic.csv", index=False)

    # Lecture honnête, imprimée plutôt que laissée à l'interprétation.
    off = result[result["space_gate"] == "off"].set_index(["symbol", "profile"])
    on = result[result["space_gate"] == "on_x1.0"].set_index(["symbol", "profile"])
    delta = (on["total_return_%"] - off["total_return_%"]).dropna()
    print(f"\nGate au Ratio 1:1 vs sans gate — couples inchangés : "
          f"{int((delta == 0).sum())}/{len(delta)}, améliorés : {int((delta > 0).sum())}, "
          f"dégradés : {int((delta < 0).sum())} (écart de retour total, points)")
    print(delta[delta != 0].round(2).to_string())


if __name__ == "__main__":
    main()
