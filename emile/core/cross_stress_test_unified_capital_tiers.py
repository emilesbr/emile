"""
Stress-test de COMBINAISON jamais croisée jusqu'ici : `unified_protocol.py`
(protocole complet RANGE fidèle + TENDANCE, `PLAN.md` section "Protocole
unifié") x `capital_tiers.py` (sizing par palier de capital, `PLAN.md`
backlog item 6), DÉCOUPÉ ANNÉE PAR ANNÉE (walk-forward, même méthode que
`walkforward_unified.py`) -- répond directement à la consigne de la tâche
("un palier de capital change-t-il le tableau des années dangereuses ?").

CONTEXTE QUI MOTIVE CE FICHIER : `walkforward_unified.py` a déjà trouvé que
BNB/TRES_AGRESSIF concentre -63,5% de drawdown sur la seule année 2021, MAIS
toujours au palier de capital IMPLICITE (aucun `capital_eur` passé =
`risk_pct` du profil brut, ni modulé ×1.25 (PALIER_1) ni plafonné à 2%
(PALIER_3), cf. `capital_tiers.py`). `unified_protocol.py::run_unified`
expose déjà `capital_eur` comme paramètre (U3 de sa propre docstring :
"appliqué SEULEMENT au risk_pct du moteur RANGE, jamais au moteur TENDANCE"),
mais aucun script existant ne l'a jamais croisé avec le découpage annuel --
"le tableau des années dangereuses" n'a donc jamais été recalculé au palier
1 (<10k€, ×1.25 -- PLUS agressif) ni au palier 3 (>=100k€, plafond 2% --
MOINS agressif que TRES_AGRESSIF=5%/AGRESSIF=3% bruts).

CE FICHIER NE RÉIMPLÉMENTE AUCUNE LOGIQUE MÉTIER -- réutilise tel quel
`unified_protocol.py::_prepare_unified`/`_run_core_unified`/
`resample_h4_with_volume` (TRIVIALEMENT combinable ici, contrairement aux
gates Fibonacci/Andrews de `cross_stress_test_faithful_gates.py` : `_run_core_unified`
accepte déjà `risk_pct` ET `start`/`end` comme paramètres de première classe,
pas une closure interne à dupliquer) et `capital_tiers.py::effective_sizing`/
`capital_tier` tels quels. Le seul code nouveau est la boucle
palier x année x actif x profil.

3 MONTANTS REPRÉSENTATIFS DES 3 PALIERS (mêmes valeurs que le docstring de
`capital_tiers.py`, choisies pour la même raison -- un montant net à
l'intérieur de chaque palier, pas une valeur frontière ambiguë) :
  - 5 000€   -> PALIER_1_MOINS_10K  (multiplicateur ×1.25)
  - 50 000€  -> PALIER_2_10K_100K   (multiplicateur ×1.00, inchangé)
  - 500 000€ -> PALIER_3_PLUS_100K  (plafond dur 2%)

LIMITE DOCUMENTÉE, PAS CACHÉE (héritée de `unified_protocol.py`, U3, non
résolue ici -- hors scope de ce fichier de mesure) : le capital par palier
ne module QUE le risk_pct du moteur RANGE ; le moteur TENDANCE
(`PROFILES_TREND[profile]["risk_pct"]`) reste inchangé à tous les paliers.
Un lecteur de ce CSV doit donc interpréter un éventuel changement de
drawdown catastrophique comme venant du SEUL sleeve RANGE, pas d'un effet
de palier sur la totalité du protocole.

DÉTECTION DE DRAWDOWN ANNUEL CATASTROPHIQUE (mêmes seuils que la tâche et
que `cross_stress_test_faithful_gates.py`, pour une lecture croisée
cohérente entre les deux fichiers de ce chantier) : `max_dd_% < -30` OU
`total_return_% < -25` sur une seule année civile.
"""
import pandas as pd
import numpy as np
import sys

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import PROFILES_V4, MAX_TRANCHES
from emile.core.trend_table import load_volume
from emile.core.unified_protocol import _prepare_unified, _run_core_unified, resample_h4_with_volume
from emile.core.capital_tiers import effective_sizing, capital_tier

CATASTROPHIC_DD_PCT = -30.0
CATASTROPHIC_RETURN_PCT = -25.0

# Cf. tête de fichier -- 3 montants représentatifs des 3 paliers, mêmes
# valeurs que le "petit aperçu manuel" de capital_tiers.py.
CAPITAL_AMOUNTS_EUR = (5_000.0, 50_000.0, 500_000.0)

def yearly_breakdown_by_tier(symbol: str, profile: str) -> list:
    h1 = load_h1(symbol)
    vol_h1 = load_volume(symbol)
    h1_full = h1.merge(vol_h1, on="date", how="inner")
    h4 = resample_h4_with_volume(h1_full)
    d1 = resample(h1_full[["date", "open", "high", "low", "close"]], "1D")
    weekly = resample(h1_full[["date", "open", "high", "low", "close"]], "W")
    # Préparé UNE SEULE FOIS par actif (indépendant du capital -- seul
    # risk_pct RANGE change ensuite), réutilisé pour les 3 paliers.
    feat = _prepare_unified(h4, d1, weekly, use_mtf_gate=True)

    dates = pd.to_datetime(feat["date"])
    years = sorted(dates.year.unique())
    rows = []
    for capital_eur in CAPITAL_AMOUNTS_EUR:
        sizing = effective_sizing(capital_eur, profile, PROFILES_V4, MAX_TRANCHES)
        tier = sizing.tier
        for y in years:
            idx = np.where(dates.year == y)[0]
            if len(idx) == 0:
                continue
            start, end = int(idx[0]), int(idx[-1]) + 1
            res = _run_core_unified(feat, profile, risk_pct=sizing.risk_pct, start=start, end=end)
            catastrophic = (res["max_dd_%"] < CATASTROPHIC_DD_PCT) or (res["total_return_%"] < CATASTROPHIC_RETURN_PCT)
            rows.append({
                "symbol": symbol, "profile": profile,
                "capital_eur": capital_eur, "tier": tier,
                "base_risk_pct": sizing.base_risk_pct, "effective_risk_pct": sizing.risk_pct,
                "year": int(y), "n_bars": end - start,
                "n_trades": res["n_trades"], "max_dd_%": res["max_dd_%"],
                "total_return_%": res["total_return_%"], "win_rate_%": res["win_rate_%"],
                "profit_factor": res["profit_factor"],
                "n_trend_campaigns_opened": res["n_trend_campaigns_opened"],
                "catastrophic": catastrophic,
            })
    return rows

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        for profile in PROFILES_V4:
            rows.extend(yearly_breakdown_by_tier(symbol, profile))
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    result.to_csv("cross_stress_test_unified_capital_tiers_walkforward.csv", index=False)

    print("=== Années CATASTROPHIQUES trouvées (max_dd_% < -30 OU total_return_% < -25) ===")
    cata = result[result["catastrophic"]]
    if len(cata) == 0:
        print("AUCUNE -- résultat honnête, pas forcé.")
    else:
        print(cata[["symbol", "profile", "tier", "capital_eur", "year",
                     "total_return_%", "max_dd_%"]].to_string(index=False))

    print("\n=== Le palier de capital change-t-il le tableau des années dangereuses ? ===")
    print("(pire année par symbol/profile/tier -- comparer les 3 lignes d'un même symbol/profile)")
    worst = result.loc[result.groupby(["symbol", "profile", "tier"])["max_dd_%"].idxmin()]
    print(worst[["symbol", "profile", "tier", "capital_eur", "effective_risk_pct",
                 "year", "total_return_%", "max_dd_%", "catastrophic"]].to_string(index=False))
    worst.to_csv("cross_stress_test_unified_capital_tiers_worst_year.csv", index=False)

    print("\n=== Focus BNB/TRES_AGRESSIF (fragilité déjà connue, walkforward_unified.py) ===")
    focus = result[(result.symbol == "BNBUSDT") & (result.profile == "TRES_AGRESSIF")]
    print(focus[["tier", "capital_eur", "effective_risk_pct", "year",
                 "total_return_%", "max_dd_%", "catastrophic"]].to_string(index=False))

if __name__ == "__main__":
    main()
