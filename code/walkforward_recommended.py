"""
Walk-forward année par année de LA config recommandée (`backtest_phase2_recommended.py`),
sur le modèle de `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md` (déjà fait une fois,
mais sur BTC H4 MODERE seul et sur un moteur pré-P0/P0-bis/synthèse -- avant
le calcul causal du cycle ET de la structure, avant le gate MTF, avant cette
synthèse). Étendu ici aux 4 actifs (BTC/ETH/BNB/SOL) pour ne pas répéter la
limite "un seul actif" déjà notée comme lacune de l'audit initial. Profil
MODERE retenu comme profil de référence (ni le plus prudent ni le plus agressif),
comme dans l'audit original.

MÉTHODE -- pas un recalcul par sous-fenêtre (piège explicitement évité)
------------------------------------------------------------------------
`backtest_phase2_recommended.py::_prepare_features` calcule le score causal,
le régime, la maturité (n_borders) ET le gate Hebdomadaire UNE SEULE FOIS sur
tout l'historique disponible (2020-2026). Ce script se contente ensuite de
DÉCOUPER les tableaux déjà calculés à la frontière de chaque année civile
(`_run_core(feat, profile, start=idx_debut_annee, end=idx_fin_annee)`),
l'équité repartant à 1.0 à chaque année -- exactement l'objectif d'un
walk-forward "est-ce qu'une année est catastrophique ?", PAS une estimation
de performance cumulée réaliste (un vrai compte ne remet pas son capital à
1.0 chaque 1er janvier). Si on recalculait le contexte Hebdomadaire par
sous-fenêtre annuelle (~52 bougies), EMA_SLOW=55 ne convergerait JAMAIS --
piège vérifié et évité AVANT d'écrire ce script (cf. docstring de
backtest_phase2_recommended.py), pas découvert après coup sur un résultat
suspect.
"""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, ".")

from backtest_phase2 import load_h1, resample
from backtest_phase2_recommended import _prepare_features, _run_core

PROFILE = "MODERE"


def yearly_breakdown(symbol: str, profile: str = PROFILE) -> list:
    h1 = load_h1(symbol)
    h4 = resample(h1, "4h")
    weekly = resample(h1, "W")
    feat = _prepare_features(h4, weekly, use_mtf_gate=True)

    dates = pd.to_datetime(feat["date"])
    years = sorted(dates.year.unique())
    rows = []
    for y in years:
        idx = np.where(dates.year == y)[0]
        if len(idx) == 0:
            continue
        start, end = int(idx[0]), int(idx[-1]) + 1
        res = _run_core(feat, profile, start=start, end=end)
        rows.append({"symbol": symbol, "year": int(y), "n_bars": end - start, **res})
    return rows


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        rows.extend(yearly_breakdown(symbol))
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("walkforward_recommended_results.csv", index=False)

    print("\n% d'années avec retour négatif, par actif :")
    for symbol in symbols:
        sub = result[result["symbol"] == symbol]
        neg = (sub["total_return_%"] < 0).sum()
        print(f"  {symbol}: {neg}/{len(sub)} année(s) négative(s)")


if __name__ == "__main__":
    main()
