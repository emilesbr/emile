"""Expérience isolée (PAS un moteur opérationnel, cf. `docs/PLAN.md`), analogue
DIRECT de `h1_timeframe_bench.py` un cran plus bas : que donne le protocole
IP-fidèle (`backtest_phase2_faithful.py::run_faithful`) si le niveau
d'EXÉCUTION est M15 natif au lieu de H4 ?

Motivation (43e round, `docs/PLAN.md`) : `docs/STATUS.md` affirmait depuis le
28e round un "NO-GO H1/**M15**... avec le moteur IP-fidèle actuel" alors que
le script cité (`h1_timeframe_bench.py`) ne rejoue QUE H1 -- M15 n'avait
jamais été retesté avec le vrai moteur, seulement avec l'ancien proxy
générique et pour BTC seul (`CLAUDE.md`, section données : "M15 natif...
complète la Phase 1 (M15 BTC seul -> NO-GO) sur les 4 actifs si ce chantier
est rouvert"). Ce script ferme ce chantier avec la même rigueur que le 28e
round, pas une reformulation sans mesure.

Remapping des rôles (cadre relatif UT/UT+1/UT+2 de Philippe, un cran sous le
remapping H1 -- cf. `h1_timeframe_bench.py`) :
  - exécution ("h4" du point de vue de `run_faithful`)          -> M15 natif
  - stop cross-timeframe UT+1 ("d1" du point de vue de l'appel) -> H1 = resample(M15, "1h")
  - gate Hebdomadaire UT+2 ("weekly" du point de vue de l'appel) -> H4 = resample(M15, "4h")

Mêmes deux régimes d'offset pandas que dans `h1_timeframe_bench.py`, un cran
plus bas :
  - "1h"/"4h" (fréquence FIXE, label=DÉBUT) : le stop UT+1, joué ici par H1
    (au lieu de H4 dans l'expérience H1), a besoin d'un `closure_delay_d1`
    de 1h (durée exacte d'une bougie H1) -- pas `CLOSURE_DELAY` (1 jour,
    24x trop tardif ici).
  - Le gate UT+2, joué ici par H4 (fréquence FIXE, label=début, PAS un
    offset ancré comme "W" dans l'expérience H1 -- différence assumée, cf.
    caveat ci-dessous), a besoin d'un `closure_delay_weekly` de 4h (durée
    exacte d'une bougie H4) -- PAS `CLOSURE_DELAY` (1 jour, 6x trop tardif).
    Contrairement à l'expérience H1 (où D1 jouait ce rôle avec label=début
    ET `CLOSURE_DELAY` par coïncidence exacte, puisque D1 dure justement
    1 jour), ici le rôle est ANALOGUE mais le délai numérique DIFFÈRE --
    vérifié explicitement, pas recopié par erreur du script H1.

Caveat honnête (identique à `h1_timeframe_bench.py`, un cran plus bas) :
les constantes du protocole calibrées en NOMBRE DE BOUGIES (`PCTL_WINDOW=250`,
`EMA_SLOW=55`/`EMA_FAST=8`/`EMA_MID=21`/`ATR_LEN=14`) valent, à cette
granularité, ~250 bougies M15 ~= 2,6 jours (contre ~10,4 jours en H1 et
~41,7 jours en H4) -- un facteur de calibration non revérifié, PAS un bug.
Lire le résultat comme "cadre identique, granularité différente", pas comme
"M15 recalibré et validé".

Pas de XRP ici : aucune donnée M15 native pour cet actif (`CLAUDE.md`).
"""
import pandas as pd

from emile.backtests.backtest_phase2 import load_m15, resample
from emile.backtests.backtest_phase2_v7 import PROFILES_V4
from emile.backtests.backtest_phase2_faithful import run_faithful

H1_ROLE_DELAY = pd.Timedelta(hours=1)
H4_ROLE_DELAY = pd.Timedelta(hours=4)


def run_m15_experiment(symbol: str, profile: str) -> dict:
    m15 = load_m15(symbol)
    h1 = resample(m15, "1h")
    h4 = resample(m15, "4h")
    return run_faithful(m15.copy(), h1.copy(), h4.copy(), profile,
                         closure_delay_d1=H1_ROLE_DELAY,
                         closure_delay_weekly=H4_ROLE_DELAY)


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        m15 = load_m15(symbol)
        h1 = resample(m15, "1h")
        h4 = resample(m15, "4h")
        d1 = resample(m15, "1D")
        weekly = resample(m15, "W")
        for profile in PROFILES_V4:
            res_m15 = run_faithful(m15.copy(), h1.copy(), h4.copy(), profile,
                                    closure_delay_d1=H1_ROLE_DELAY,
                                    closure_delay_weekly=H4_ROLE_DELAY)
            res_h4 = run_faithful(h4.copy(), d1.copy(), weekly.copy(), profile)
            rows.append({
                "symbol": symbol, "profile": profile,
                "m15_n_trades": res_m15["n_trades"],
                "m15_max_dd_%": res_m15["max_dd_%"],
                "m15_total_return_%": res_m15["total_return_%"],
                "m15_win_rate_%": res_m15["win_rate_%"],
                "m15_profit_factor": res_m15["profit_factor"],
                "h4_n_trades": res_h4["n_trades"],
                "h4_max_dd_%": res_h4["max_dd_%"],
                "h4_total_return_%": res_h4["total_return_%"],
                "h4_win_rate_%": res_h4["win_rate_%"],
                "h4_profit_factor": res_h4["profit_factor"],
            })
        print(f"  {symbol} ok", flush=True)
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    print(result.to_string(index=False))
    result.to_csv("results/m15_timeframe_bench_results.csv", index=False)


if __name__ == "__main__":
    main()
