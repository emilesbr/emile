"""
Mesure honnête de `H-Context-BB-UT+1`/`H-Context-BB-UT+2` (candidats proposés
par l'utilisateur, cf. `context_bollinger.py`/`unified_protocol.py::
bb_context_level` et `docs/CONTEXT_CHANNEL_REVERSE_ENGINEERING.md`) appliqués
EXCLUSIVEMENT au gate régime de Neuneu (58e/59e rounds, `docs/PLAN.md`).
Demande directe de l'utilisateur : "vérifie notamment sur sa capacité à
rendre la stratégie de trading de range neuneu rentable" (58e round), puis
"place le contexte sur UT+2 et non plus UT+1" (59e round).

CE QUE CE SCRIPT MESURE
-----------------------------------------------------------------------------
Pour chaque profil et chaque actif, rejoue `run_unified` avec `use_neuneu=
True` et compare 3 variantes -- `use_bb_context_for_neuneu=False` (référence
déjà publiée, `neuneu_wired_measure.py`, 48e round), `bb_context_level="ut1"`
(candidat D1, 58e round) et `bb_context_level="ut2"` (candidat Hebdomadaire,
59e round) -- SEUL le gate régime de Neuneu change entre les 3, RANGE/
TENDANCE et tout le reste du protocole restent identiques.
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
            res_ut1 = run_unified(h4.copy(), d1.copy(), weekly.copy(), profile,
                                   use_neuneu=True, use_bb_context_for_neuneu=True, bb_context_level="ut1")
            res_ut2 = run_unified(h4.copy(), d1.copy(), weekly.copy(), profile,
                                   use_neuneu=True, use_bb_context_for_neuneu=True, bb_context_level="ut2")
            rows.append({
                "symbol": symbol, "profile": profile,
                "n_trades_ema": res_ema["n_trades"], "n_trades_ut1": res_ut1["n_trades"], "n_trades_ut2": res_ut2["n_trades"],
                "n_neuneu_opened_ema": res_ema["n_neuneu_opened"], "n_neuneu_opened_ut1": res_ut1["n_neuneu_opened"],
                "n_neuneu_opened_ut2": res_ut2["n_neuneu_opened"],
                "return_ema_%": res_ema["total_return_%"], "return_ut1_%": res_ut1["total_return_%"],
                "return_ut2_%": res_ut2["total_return_%"],
                "max_dd_ema_%": res_ema["max_dd_%"], "max_dd_ut1_%": res_ut1["max_dd_%"], "max_dd_ut2_%": res_ut2["max_dd_%"],
            })
        print(f"  {symbol} ok", flush=True)

    result = pd.DataFrame(rows)
    result["delta_return_ut1_pt"] = result["return_ut1_%"] - result["return_ema_%"]
    result["delta_return_ut2_pt"] = result["return_ut2_%"] - result["return_ema_%"]
    result["delta_max_dd_ut1_pt"] = result["max_dd_ut1_%"] - result["max_dd_ema_%"]
    result["delta_max_dd_ut2_pt"] = result["max_dd_ut2_%"] - result["max_dd_ema_%"]
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 24)
    print(result.to_string(index=False))
    result.to_csv("results/neuneu_bb_context_results.csv", index=False)


def main_k_sweep():
    """60e round -- demande directe de l'utilisateur : faire varier le
    multiplicateur `k` de Bollinger (jusqu'ici toujours 2, jamais testé
    ailleurs). UNIQUEMENT sur `bb_context_level="ut1"` -- le seul candidat
    ayant un cas d'usage positif identifié à ce jour (BNB, 58e round)."""
    K_VALUES = (1.5, 2.0, 2.5, 3.0)
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
            row = {"symbol": symbol, "profile": profile,
                   "n_trades_ema": res_ema["n_trades"], "return_ema_%": res_ema["total_return_%"],
                   "max_dd_ema_%": res_ema["max_dd_%"]}
            for k in K_VALUES:
                res_k = run_unified(h4.copy(), d1.copy(), weekly.copy(), profile,
                                     use_neuneu=True, use_bb_context_for_neuneu=True,
                                     bb_context_level="ut1", bb_k=k)
                row[f"n_trades_k{k}"] = res_k["n_trades"]
                row[f"n_neuneu_opened_k{k}"] = res_k["n_neuneu_opened"]
                row[f"return_k{k}_%"] = res_k["total_return_%"]
                row[f"max_dd_k{k}_%"] = res_k["max_dd_%"]
                row[f"delta_return_k{k}_pt"] = res_k["total_return_%"] - res_ema["total_return_%"]
                row[f"delta_max_dd_k{k}_pt"] = res_k["max_dd_%"] - res_ema["max_dd_%"]
            rows.append(row)
        print(f"  {symbol} ok", flush=True)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_columns", 40)
    delta_cols = ["symbol", "profile"] + [f"delta_return_k{k}_pt" for k in K_VALUES] + [f"delta_max_dd_k{k}_pt" for k in K_VALUES]
    print(result[delta_cols].to_string(index=False))
    result.to_csv("results/neuneu_bb_context_k_sweep_results.csv", index=False)


if __name__ == "__main__":
    main()
