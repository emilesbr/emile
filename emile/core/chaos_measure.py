"""
Mesure honnête de `regime_classifier.add_chaos_extrapolated` (61e round,
`docs/PLAN.md`) -- EXTRAPOLATION EXPLICITE, décision directe de l'utilisateur.
Rapporte la fréquence réelle de CHAOS sur BTC/ETH/BNB/SOL H4 natif (aucune
donnée de référence publiée à comparer, contrairement à `regime_classifier.py`
lui-même dans `REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md` -- ce round EST la
première mesure, pas une vérification de non-régression).
"""
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import prepare
from emile.core.regime_classifier import add_chaos_extrapolated

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")


def main():
    rows = []
    for symbol in SYMBOLS:
        df = resample(load_h1(symbol), "4h")
        prepared = prepare(df)
        regime = prepared["regime"].to_numpy()
        chaos_regime = add_chaos_extrapolated(prepared, regime, prepared["n_borders"].to_numpy())
        n_total = len(regime)
        n_range_neutre_before = (regime == "RANGE_NEUTRE").sum()
        n_chaos = (chaos_regime == "CHAOS").sum()
        rows.append({
            "symbol": symbol,
            "n_bars": n_total,
            "n_range_neutre_before": n_range_neutre_before,
            "n_chaos": n_chaos,
            "chaos_%_of_all_bars": round(100 * n_chaos / n_total, 2),
            "chaos_%_of_range_neutre": round(100 * n_chaos / n_range_neutre_before, 2) if n_range_neutre_before else float("nan"),
        })
        print(f"  {symbol} ok", flush=True)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(result.to_string(index=False))
    result.to_csv("results/chaos_extrapolated_frequency_results.csv", index=False)


if __name__ == "__main__":
    main()
