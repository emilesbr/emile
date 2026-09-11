"""
Walk-forward année par année du protocole UNIFIÉ complet
(`unified_protocol.py`, RANGE fidèle + TENDANCE concurrents), sur le MÊME
modèle que `walkforward_recommended.py`/`walkforward_faithful.py` -- jamais
fait jusqu'ici sur LE protocole désormais désigné comme celui à utiliser
opérationnellement (PLAN.md, backlog item 5, "reste ouvert" après la
consolidation).

Motivation directe : le backtest agrégé (`backtest_phase2_unified_results.csv`)
a identifié BNB/TRES_AGRESSIF comme un point de fragilité concret (-72,5% de
drawdown) -- un chiffre agrégé sur 6 ans ne dit pas SI ce risque est
concentré sur une seule année catastrophique ou étalé, information
directement utile pour juger si ce couple actif/profil est gérable en
pratique ou à éviter purement et simplement.

MÉTHODE -- identique à `walkforward_faithful.py`, adaptée pour DEUX
systèmes (RANGE+TENDANCE) au lieu d'un seul : `unified_protocol._prepare_unified`
calcule toutes les colonnes UNE SEULE FOIS sur l'historique complet
disponible (2020-2026). Ce script DÉCOUPE ensuite la boucle d'orchestration
à la frontière de chaque année civile (`_run_core_unified(feat, profile,
start=idx_debut, end=idx_fin)`, cf. sa docstring pour le détail de comment
le découpage est géré sans re-trancher `feat` lui-même), l'équité repartant
à 1.0 à chaque année -- objectif "est-ce qu'une année est catastrophique ?",
PAS une estimation de performance cumulée réaliste.
"""
import pandas as pd
import numpy as np
import sys

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.core.trend_table import load_volume
from emile.core.unified_protocol import _prepare_unified, _run_core_unified, resample_h4_with_volume

PROFILE = "MODERE"

def yearly_breakdown(symbol: str, profile: str = PROFILE) -> list:
    h1 = load_h1(symbol)
    vol_h1 = load_volume(symbol)
    h1_full = h1.merge(vol_h1, on="date", how="inner")
    h4 = resample_h4_with_volume(h1_full)
    d1 = resample(h1_full[["date", "open", "high", "low", "close"]], "1D")
    weekly = resample(h1_full[["date", "open", "high", "low", "close"]], "W")
    feat = _prepare_unified(h4, d1, weekly, use_mtf_gate=True)

    dates = pd.to_datetime(feat["date"])
    years = sorted(dates.year.unique())
    rows = []
    for y in years:
        idx = np.where(dates.year == y)[0]
        if len(idx) == 0:
            continue
        start, end = int(idx[0]), int(idx[-1]) + 1
        res = _run_core_unified(feat, profile, start=start, end=end)
        rows.append({
            "symbol": symbol, "profile": profile, "year": int(y), "n_bars": end - start,
            "n_trades": res["n_trades"], "max_dd_%": res["max_dd_%"],
            "total_return_%": res["total_return_%"], "win_rate_%": res["win_rate_%"],
            "profit_factor": res["profit_factor"],
            "n_trend_campaigns_opened": res["n_trend_campaigns_opened"],
        })
    return rows

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        rows.extend(yearly_breakdown(symbol))
        # Point de vigilance identifié par le backtest agrégé (BNB/TRES_AGRESSIF,
        # cf. tête de fichier) : rejoué EN PLUS de MODERE pour ce seul actif,
        # décidé avant de voir le résultat année par année.
        if symbol == "BNBUSDT":
            rows.extend(yearly_breakdown(symbol, profile="TRES_AGRESSIF"))
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("walkforward_unified_results.csv", index=False)

    print("\n% d'années avec retour négatif, par actif/profil :")
    for (symbol, profile), sub in result.groupby(["symbol", "profile"]):
        neg = (sub["total_return_%"] < 0).sum()
        print(f"  {symbol}/{profile}: {neg}/{len(sub)} année(s) négative(s), "
              f"pire retour {sub['total_return_%'].min()}%, pire drawdown {sub['max_dd_%'].min()}%")

if __name__ == "__main__":
    main()
