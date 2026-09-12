"""Expérience isolée (PAS un moteur opérationnel, cf. `docs/PLAN.md`) :
que donne le protocole IP-fidèle (`backtest_phase2_faithful.py::run_faithful`,
tel qu'agrégé après les 27 rounds de ce cycle) si le niveau d'EXÉCUTION est
H1 natif au lieu de H4 ?

Remapping des rôles (cadre relatif UT/UT+1/UT+2 de Philippe -- cf. `CLAUDE.md`,
« aucune UT calendaire fixe n'est exigée nativement ») :
  - exécution ("h4" du point de vue de `run_faithful`)      -> H1 natif
  - stop cross-timeframe UT+1 ("d1" du point de vue de l'appel) -> H4 = resample(H1, "4h")
  - gate Hebdomadaire UT+2 ("weekly" du point de vue de l'appel) -> D1 = resample(H1, "1D")

Point méthodologique vérifié (pas supposé) avant d'écrire cette expérience,
cf. docstring de `_prepare_features` : `resample(df, rule)` de
`backtest_phase2.py` utilise les conventions PAR DÉFAUT de pandas, qui
diffèrent selon le type d'offset :
  - "D"/"4h" (fréquence FIXE)  : label = DÉBUT de période -> une bougie
    n'est intégralement close que `durée de la bougie` après son `date`.
    Donc le stop cross-timeframe UT+1, quand H4 joue ce rôle (au lieu de
    D1 dans l'usage historique), a besoin d'un `closure_delay_d1` de
    4h -- PAS `CLOSURE_DELAY` (1 jour, calibré pour D1, 6x trop tardif ici
    -- pas un lookahead, juste une fraîcheur inutilement dégradée).
  - "W" (offset ANCRÉ)         : label = FIN de période par défaut pandas
    -> une bougie Hebdomadaire est déjà entièrement close AU MOMENT de son
    `date`. C'est pour ça que le gate UT+2, quand D1 joue ce rôle (fréquence
    fixe, label=début), doit lui GARDER `CLOSURE_DELAY`=1 jour (durée EXACTE
    d'une bougie D1) -- valeur par défaut, aucun paramètre à passer.

Caveat honnête, à ne PAS masquer (cf. `CLAUDE.md`, résultat dégradé publié
tel quel) : plusieurs constantes du protocole sont calibrées en NOMBRE DE
BOUGIES, pas en temps calendaire -- `PCTL_WINDOW=250` (regime_classifier.py),
`EMA_SLOW=55`/`EMA_FAST=8`/`EMA_MID=21`/`ATR_LEN=14` (backtest_phase2.py).
Sur H4 (contexte historique de tuning empirique) 250 bougies ~= 41,7 jours ;
sur H1 (exécution ici) 250 bougies ~= 10,4 jours -- une fenêtre glissante
~4x plus courte en temps réel. Ce n'est PAS un bug (même cadre relatif que
Philippe : mêmes formules à toute UT) mais un facteur de calibration non
revérifié sur cette UT -- le résultat ci-dessous doit être lu comme "cadre
identique, granularité différente", pas comme "H1 recalibré et validé"."""
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import PROFILES_V4
from emile.backtests.backtest_phase2_faithful import run_faithful

H4_ROLE_DELAY = pd.Timedelta(hours=4)


def run_h1_experiment(symbol: str, profile: str) -> dict:
    h1 = load_h1(symbol)
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")
    return run_faithful(h1.copy(), h4.copy(), d1.copy(), profile,
                         closure_delay_d1=H4_ROLE_DELAY)


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        weekly = resample(h1, "W")
        for profile in PROFILES_V4:
            res_h1 = run_faithful(h1.copy(), h4.copy(), d1.copy(), profile,
                                   closure_delay_d1=H4_ROLE_DELAY)
            res_h4 = run_faithful(h4.copy(), d1.copy(), weekly.copy(), profile)
            rows.append({
                "symbol": symbol, "profile": profile,
                "h1_n_trades": res_h1["n_trades"],
                "h1_max_dd_%": res_h1["max_dd_%"],
                "h1_total_return_%": res_h1["total_return_%"],
                "h1_win_rate_%": res_h1["win_rate_%"],
                "h1_profit_factor": res_h1["profit_factor"],
                "h4_n_trades": res_h4["n_trades"],
                "h4_max_dd_%": res_h4["max_dd_%"],
                "h4_total_return_%": res_h4["total_return_%"],
                "h4_win_rate_%": res_h4["win_rate_%"],
                "h4_profit_factor": res_h4["profit_factor"],
            })
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    print(result.to_string(index=False))
    result.to_csv("results/h1_timeframe_bench_results.csv", index=False)


if __name__ == "__main__":
    main()
