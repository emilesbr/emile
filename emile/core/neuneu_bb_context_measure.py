"""
Mesure honnête de `H-Context-BB-UT+1` (candidat proposé par l'utilisateur,
cf. `context_bollinger.py` et `docs/CONTEXT_CHANNEL_REVERSE_ENGINEERING.md`)
appliqué EXCLUSIVEMENT au gate régime de Neuneu (58e round, `docs/PLAN.md`).
Demande directe de l'utilisateur : "vérifie notamment sur sa capacité à
rendre la stratégie de trading de range neuneu rentable."

CE QUE CE SCRIPT MESURE
-----------------------------------------------------------------------------
Pour chaque profil et chaque actif, rejoue `run_unified` avec `use_neuneu=
True` et compare `use_bb_context_for_neuneu=False` (référence déjà publiée,
`neuneu_wired_measure.py`, 48e round) contre `use_bb_context_for_neuneu=True`
(candidat) -- SEUL le gate régime de Neuneu change, RANGE/TENDANCE et tout le
reste du protocole restent identiques dans les deux colonnes.
"""
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import PROFILES_V4
from emile.core.unified_protocol import run_unified, resample_h4_with_volume
from emile.core.trend_table import load_volume

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")


def main():
    rows = []
    for symbol in SYMBOLS:
        h1 = load_h1(symbol)
        vol_h1 = load_volume(symbol)
        h1_full = h1.merge(vol_h1, on="date", how="inner")
        h4 = resample_h4_with_volume(h1_full)
        d1 = resample(h1_full[["date", "open", "high", "low", "close"]], "1D")
        weekly = resample(h1_full[["date", "open", "high", "low", "close"]], "W")
        for profile in PROFILES_V4:
            res_ema = run_unified(h4.copy(), d1.copy(), weekly.copy(), profile,
                                   use_neuneu=True, use_bb_context_for_neuneu=False)
            res_bb = run_unified(h4.copy(), d1.copy(), weekly.copy(), profile,
                                  use_neuneu=True, use_bb_context_for_neuneu=True)
            rows.append({
                "symbol": symbol, "profile": profile,
                "n_trades_ema": res_ema["n_trades"], "n_trades_bb": res_bb["n_trades"],
                "n_neuneu_opened_ema": res_ema["n_neuneu_opened"], "n_neuneu_opened_bb": res_bb["n_neuneu_opened"],
                "return_ema_%": res_ema["total_return_%"], "return_bb_%": res_bb["total_return_%"],
                "max_dd_ema_%": res_ema["max_dd_%"], "max_dd_bb_%": res_bb["max_dd_%"],
            })
        print(f"  {symbol} ok", flush=True)

    result = pd.DataFrame(rows)
    result["delta_return_pt"] = result["return_bb_%"] - result["return_ema_%"]
    result["delta_max_dd_pt"] = result["max_dd_bb_%"] - result["max_dd_ema_%"]
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("results/neuneu_bb_context_results.csv", index=False)


if __name__ == "__main__":
    main()
