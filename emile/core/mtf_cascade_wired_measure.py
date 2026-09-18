"""
Mesure de la consommation "Tendance Multi-timeframe" (`use_mtf_cascade`/
`mtf_cascade_gate` de `trend_table.py::run_trend_table`, 42e round --
`docs/PLAN.md`). Décision directe de l'utilisateur : accepter la lecture
extrapolée nécessaire pour câbler ce mécanisme (H-MTF-Cascade-4/5, cf.
docstring de `run_trend_table`), après que la seule DÉTECTION (38e round) et
son blocage architectural (LOCAL/CONTEXT_DURATION, levé au 39e round) aient
été traités séparément.

CE QUE CE SCRIPT MESURE
-----------------------------------------------------------------------------
Pour chacun de H4/D1/Hebdomadaire, rejoue `run_trend_table` avec `use_mtf_
cascade=True` (gate d'ouverture restreint aux fenêtres de Tendance Multi-
timeframe + jambe de Breakout dimensionnée à 2% de risque) et compare à
`use_mtf_cascade=False` (comportement historique du profil MODERE, déjà
mesuré ailleurs) -- mêmes 4 actifs, même donnée, seule la consommation
change.
"""
import numpy as np
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import LOCAL_DURATION_H4_BARS, CONTEXT_DURATION_H4_BARS
from emile.core.trend_table import (
    add_trend_context, run_trend_table, load_volume, resample_volume,
    attach_regime_is_tendance, compute_multi_timeframe_trend, MTF_CASCADE_RISK_PCT,
)
from emile.backtests.backtest_phase2_v7 import prepare

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")
TF_RULES = (("4h", "H4"), ("1D", "D1"), ("W", "Weekly"))
PREPARE_KWARGS = {"local_duration": LOCAL_DURATION_H4_BARS, "context_duration": CONTEXT_DURATION_H4_BARS}

def compute_regime_per_tf(h1: pd.DataFrame) -> dict:
    out = {}
    for rule, label in TF_RULES:
        df = resample(h1, rule)
        df = add_trend_context(prepare(df, **PREPARE_KWARGS), **PREPARE_KWARGS)
        out[label] = df
    return out

def main():
    rows = []
    for symbol in SYMBOLS:
        h1 = load_h1(symbol)
        vol_h1 = load_volume(symbol)
        dfs_by_tf = compute_regime_per_tf(h1)
        is_tend = {label: (dfs_by_tf[label]["regime"].values == "TENDANCE") for label in ("H4", "D1", "Weekly")}

        for rule, label in TF_RULES:
            df = resample(h1, rule)
            vol = resample_volume(vol_h1, rule)
            own_dates = dfs_by_tf[label]["date"].values
            other_labels = [l for l in ("H4", "D1", "Weekly") if l != label]
            aligned = {}
            for other in other_labels:
                if other == label:
                    continue
                aligned[other] = attach_regime_is_tendance(own_dates, dfs_by_tf[other])
            # Régime propre à `label` déjà sur sa propre grille -- pas de jointure nécessaire.
            own_tend = is_tend[label]
            gate = own_tend & aligned[other_labels[0]] & aligned[other_labels[1]]

            res_off = run_trend_table(df.copy(), vol.copy(), "MODERE", **PREPARE_KWARGS)
            res_on = run_trend_table(df.copy(), vol.copy(), "MODERE", use_mtf_cascade=True,
                                      mtf_cascade_gate=gate, **PREPARE_KWARGS)
            rows.append({
                "symbol": symbol, "timeframe": label,
                "n_trades_off": res_off["n_trades"], "n_trades_on": res_on["n_trades"],
                "return_off_%": res_off["total_return_%"], "return_on_%": res_on["total_return_%"],
                "max_dd_off_%": res_off["max_dd_%"], "max_dd_on_%": res_on["max_dd_%"],
                "gate_pct_bars": round(gate.mean() * 100, 2),
            })
        print(f"  {symbol} ok", flush=True)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("mtf_cascade_wired_results.csv", index=False)

    n_diff = int((result["n_trades_off"] != result["n_trades_on"]).sum())
    print(f"\n{n_diff}/{len(result)} lignes (actif x UT) montrent un écart quelconque "
          f"(risque {MTF_CASCADE_RISK_PCT*100:.0f}% vs profil MODERE tel quel).")

if __name__ == "__main__":
    main()
