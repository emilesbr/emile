"""
Mesure honnête de `run_repli_neuneu` (`neuneu_repli.py`, 46e round --
`docs/PLAN.md`) sur données réelles BTC/ETH/BNB/SOL, H4 (`LOCAL_DURATION_
H4_BARS`/`CONTEXT_DURATION_H4_BARS`, 39e round -- même calibration que le
reste des moteurs de ce projet sur cette UT, pas une nouvelle fenêtre
inventée).

Ce module N'EST PAS câblé dans `faithful.py`/`unified_protocol.py` (cf.
tête de `neuneu_repli.py`) -- moteur STANDALONE, mesuré isolément, même
statut que `h1_timeframe_bench.py` avant son propre câblage.
"""
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import LOCAL_DURATION_H4_BARS, CONTEXT_DURATION_H4_BARS
from emile.core.neuneu_repli import run_repli_neuneu, compute_repli_neuneu_signal

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


if __name__ == "__main__":
    main()
