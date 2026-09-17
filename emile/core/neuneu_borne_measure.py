"""
Mesure honnête de `run_borne_neuneu` (`neuneu_borne.py`, 47e round --
`docs/PLAN.md`) sur données réelles BTC/ETH/BNB/SOL, H4 (`LOCAL_DURATION_
H4_BARS`/`CONTEXT_DURATION_H4_BARS`, 39e round -- même calibration que
`neuneu_repli_measure.py` et le reste des moteurs de ce projet sur H4).

Ce module N'EST PAS câblé dans `faithful.py`/`unified_protocol.py` --
moteur STANDALONE, mesuré isolément, même statut que `neuneu_repli.py`.
"""
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import prepare, LOCAL_DURATION_H4_BARS, CONTEXT_DURATION_H4_BARS
from emile.core.neuneu_borne import run_borne_neuneu, compute_borne_neuneu_signal

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")


def main():
    rows = []
    for symbol in SYMBOLS:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        # H-Borne-6 (trouvaille de ce round, cf. docs/PLAN.md "47e application") :
        # le gate brut se déclenche aussi bien en TENDANCE établie (nouveaux
        # plus hauts locaux = normal en tendance, pas un excès) qu'en vrai
        # excès de RANGE -- Neuneu est explicitement une famille RANGE du
        # guide, jamais Tendance. Régime réutilisé tel quel (aucune invention),
        # même calibration LOCAL/CONTEXT_DURATION que le reste du moteur H4.
        regime = prepare(h4.copy(), local_duration=LOCAL_DURATION_H4_BARS,
                          context_duration=CONTEXT_DURATION_H4_BARS)["regime"].values
        sig = compute_borne_neuneu_signal(h4, CONTEXT_DURATION_H4_BARS, LOCAL_DURATION_H4_BARS,
                                           regime=regime)
        n_signals = int(sig["short_signal"].sum())
        res = run_borne_neuneu(h4, CONTEXT_DURATION_H4_BARS, LOCAL_DURATION_H4_BARS, regime=regime)
        rows.append({
            "symbol": symbol, "n_gate_signals": n_signals,
            "n_trades": res["n_trades"], "total_return_%": res["total_return_%"],
            "max_dd_%": res["max_dd_%"], "win_rate_%": res["win_rate_%"],
            "profit_factor": res["profit_factor"],
        })
        print(f"  {symbol} ok ({n_signals} signaux, {res['n_trades']} trades)", flush=True)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("results/neuneu_borne_results.csv", index=False)


if __name__ == "__main__":
    main()
