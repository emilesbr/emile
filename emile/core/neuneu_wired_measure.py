"""
Mesure de la consommation du canal Neuneu câblé (`use_neuneu` de
`unified_protocol.py::run_unified`, 48e round -- `docs/PLAN.md`). Décision
directe de l'utilisateur : après avoir construit et mesuré isolément les
2 moitiés de Neuneu (46e/47e rounds), les câbler réellement dans LE
protocole complet ("que ferait un ingénieur senior à présent ?").

CE QUE CE SCRIPT MESURE
-----------------------------------------------------------------------------
Pour chaque profil, rejoue `run_unified` avec `use_neuneu=False` (comportement
historique, référence déjà publiée) et `use_neuneu=True` (canal Neuneu actif,
indépendant de RANGE/TENDANCE) sur les mêmes 4 actifs, même donnée -- seule la
consommation change.
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
            res_off = run_unified(h4.copy(), d1.copy(), weekly.copy(), profile, use_neuneu=False)
            res_on = run_unified(h4.copy(), d1.copy(), weekly.copy(), profile, use_neuneu=True)
            rows.append({
                "symbol": symbol, "profile": profile,
                "n_trades_off": res_off["n_trades"], "n_trades_on": res_on["n_trades"],
                "n_neuneu_opened": res_on["n_neuneu_opened"],
                "return_off_%": res_off["total_return_%"], "return_on_%": res_on["total_return_%"],
                "max_dd_off_%": res_off["max_dd_%"], "max_dd_on_%": res_on["max_dd_%"],
            })
        print(f"  {symbol} ok", flush=True)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("results/neuneu_wired_unified_results.csv", index=False)


if __name__ == "__main__":
    main()
