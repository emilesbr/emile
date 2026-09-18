"""
Mesure de la consommation "SL gain" (`use_sl_gain` de `backtest_phase2_
faithful.py::run_faithful`/`unified_protocol.py::run_unified`, 45e round --
`docs/PLAN.md`). Décision directe de l'utilisateur : accepter la lecture
extrapolée nécessaire pour câbler ce mécanisme (H-SLGain-1, cf. docstring de
`position_engine.py`), après avoir proposé une solution concrète (cf.
question posée : "pourquoi on ne peut pas implémenter Neuneu/Chaos/SL gain ?"
puis "trouve une solution").

CE QUE CE SCRIPT MESURE
-----------------------------------------------------------------------------
Pour AGRESSIF et TRES_AGRESSIF (seuls profils concernés par la ligne "Target
1" du tableau §3bis), rejoue `run_faithful` avec `use_sl_gain=False`
(comportement historique, référence déjà publiée) et `use_sl_gain=True`
(nouveau mécanisme) sur les mêmes 4 actifs, même donnée -- seule la
consommation change. Rapporte aussi combien de tranches ont ATTEINT Target 1
(la seule population concernée).
"""
import numpy as np
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_faithful import run_faithful, _prepare_features, _run_core

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")
PROFILES = ("AGRESSIF", "TRES_AGRESSIF")


def count_target1_hits(feat, profile_name) -> int:
    """Nombre de tranches dont le reliquat baisse au moins 2 fois entre
    l'ouverture et soit la fermeture soit la fin de l'historique -- proxy
    direct de "a atteint au moins Validation+Confirmation+Target1" ou plus
    précisément ici : compte les tranches ouvertes en RANGE_TENDANCIEL dont
    `lim_done` aurait pu s'appliquer (approximé en rejouant avec use_sl_gain=
    True et en comptant les tranches dont `close_i is None` ET `remaining`
    a diminué après Confirmation, OU closed avec `realized_pnl` cohérent
    avec un `lim_close_frac` partiel)."""
    res = _run_core(feat, profile_name, record_trace=True, use_sl_gain=True)
    n_hit = 0
    for tr in res["trace"]:
        sizes = sorted({round(r, 9) for _, r in tr["snapshots"]}, reverse=True)
        if len(sizes) >= 3:   # ouverture -> Confirmation -> Target1 (3 paliers distincts min.)
            n_hit += 1
    return n_hit


def main():
    rows = []
    for symbol in SYMBOLS:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        weekly = resample(h1, "W")
        feat = _prepare_features(h4, d1, weekly)
        for profile in PROFILES:
            res_off = run_faithful(h4.copy(), d1.copy(), weekly.copy(), profile, use_sl_gain=False)
            res_on = run_faithful(h4.copy(), d1.copy(), weekly.copy(), profile, use_sl_gain=True)
            n_hit = count_target1_hits(feat, profile)
            rows.append({
                "symbol": symbol, "profile": profile,
                "n_trades_off": res_off["n_trades"], "n_trades_on": res_on["n_trades"],
                "return_off_%": res_off["total_return_%"], "return_on_%": res_on["total_return_%"],
                "max_dd_off_%": res_off["max_dd_%"], "max_dd_on_%": res_on["max_dd_%"],
                "n_target1_hits": n_hit,
            })
        print(f"  {symbol} ok", flush=True)

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("results/sl_gain_wired_results.csv", index=False)

    n_diff = int((result["n_trades_off"] != result["n_trades_on"]).sum())
    print(f"\n{n_diff}/{len(result)} lignes (actif x profil) montrent un écart de n_trades "
          f"(off vs on). Total tranches ayant atteint Target 1 : {result['n_target1_hits'].sum()}.")


if __name__ == "__main__":
    main()
