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
"""
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import LOCAL_DURATION_H4_BARS, CONTEXT_DURATION_H4_BARS
from emile.core.neuneu_repli import run_repli_neuneu, compute_repli_neuneu_signal, NEUNEU_OBJECTIF_CLOSE_FRAC

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")


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


if __name__ == "__main__":
    main()
