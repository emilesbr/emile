"""
Walk-forward année par année de la config FIDÈLE (`backtest_phase2_faithful.py`),
sur le MÊME modèle que `walkforward_recommended.py` -- celui-ci portait sur
`recommended.py`, jamais rejoué sur `faithful.py` (PLAN.md, backlog item 5,
"toujours ouvert, aggravé par ce cycle" : le protocole désormais désigné
comme "à utiliser opérationnellement" n'avait reçu aucun walk-forward).

MÉTHODE -- identique à `walkforward_recommended.py`, pas un recalcul par
sous-fenêtre (piège déjà évité une fois, pas à redécouvrir) : `backtest_phase2_faithful.py::_prepare_features`
calcule le score causal, le régime, la maturité, le stop D1 (UT+1) ET le
gate Hebdomadaire UNE SEULE FOIS sur tout l'historique disponible
(2020-2026). Ce script DÉCOUPE ensuite les tableaux déjà calculés à la
frontière de chaque année civile (`_run_core(feat, profile, start=idx_debut,
end=idx_fin)`), l'équité repartant à 1.0 à chaque année -- objectif
"est-ce qu'une année est catastrophique ?", PAS une estimation de
performance cumulée réaliste.
"""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, ".")

from backtest_phase2 import load_h1, resample
from backtest_phase2_faithful import _prepare_features, _run_core

PROFILE = "MODERE"


def yearly_breakdown(symbol: str, profile: str = PROFILE) -> list:
    h1 = load_h1(symbol)
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")
    weekly = resample(h1, "W")
    feat = _prepare_features(h4, d1, weekly)

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
    result.to_csv("walkforward_faithful_results.csv", index=False)

    print("\n% d'années avec retour négatif, par actif :")
    for symbol in symbols:
        sub = result[result["symbol"] == symbol]
        neg = (sub["total_return_%"] < 0).sum()
        print(f"  {symbol}: {neg}/{len(sub)} année(s) négative(s)")


if __name__ == "__main__":
    main()
