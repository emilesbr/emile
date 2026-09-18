"""
Validation hors-échantillon (OOS) de la config FIDÈLE (`backtest_phase2_
faithful.py`) sur XRP -- sur le modèle exact de `oos_xrp_recommended.py`
(lui-même sur le modèle de `OOS_VALIDATION_CYCLE_SIGN.md` section 2,
"procédure décidée à l'avance"), pour éviter le biais rétrospectif déjà
identifié comme risque dans ce projet (`AUDIT_QUALITE_ET_CORRECTION_CYCLE.md`,
réserve méthodologique).

REBRANCHÉ SUR LA DONNÉE RÉELLE (40e round, `PLAN.md`) -- l'ancienne version
------------------------------------------------------------------------------
Ce script pointait vers `/home/user/http-kaijin/crypto-decision-bi/...`, un
dépôt d'un ANCIEN sandbox disparu (confirmé par `FileNotFoundError` à
l'exécution) -- XRP n'y existait que comme 365 barres D1, ce qui obligeait à
décaler les 3 rôles de timeframe (exécution/stop UT+1/gate UT+2) d'un cran
vers le haut (D1 -> exécution, Hebdomadaire -> stop, Mensuel -> gate) et à
désactiver le gate Mensuel faute d'historique suffisant pour `compute_
cycle_phase_causal`/`regime_classifier.add_regime` (cf. l'historique git de
ce fichier pour le détail complet de cette procédure -- honnête à l'époque,
mais plus nécessaire).

**Cette limite n'existe plus** : XRP a désormais une VRAIE donnée H1 native
(`data/processed/XRPUSDT_1h_processed.csv`, 2020-01-06, 58 569 bougies --
cf. `CLAUDE.md`). Les 3 rôles peuvent donc reprendre leur position NATURELLE,
identique à BTC/ETH/BNB/SOL dans `backtest_phase2_faithful.py`, sans aucun
décalage ni procédure de repli :
  - `h4`     -> exécution (dérivé du H1 XRP par `resample`, comme les 4
               autres actifs)
  - `d1`     -> stop UT+1 réel (littéral, INCONDITIONNEL dans `faithful.py`)
  - `weekly` -> gate UT+2 (`use_mtf_gate=True`, le défaut du moteur -- ~301
               bougies Hebdomadaires disponibles, largement au-dessus des
               150/250 bougies requises par `compute_cycle_phase_causal`/
               les seuils adaptatifs de `regime_classifier.add_regime`, la
               contrainte qui forçait sa désactivation dans l'ancienne
               version)

Les 4 profils (FAIBLE/MODERE/AGRESSIF/TRES_AGRESSIF) restent testés, pas
seulement MODERE, par souci de complétude -- décidé avant résultat, comme
la version précédente. Aucune itération après coup : ce script est rejoué
une fois, le résultat (`oos_xrp_faithful_results.csv`) est rapporté tel
quel, qu'il confirme ou non les attentes.

LIMITE RESTANTE, HONNÊTE
------------------------------------------------------------------------------
Toujours un seul actif -- l'OOS reste ce qu'il a toujours été (une
validation hors-échantillon sur XRP, jamais utilisé pour calibrer quoi que
ce soit dans ce projet), mais porte désormais sur ~6 ans d'historique H4/D1/
Hebdomadaire complet, avec les 3 règles littérales ET le gate actifs sans
aucune neutralisation forcée par la donnée -- un résultat qualitativement
différent, à ne pas confondre avec celui de l'ancienne version (timeframes,
période et gate MTF diffèrent tous les trois).
"""
import pandas as pd
import sys

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import PROFILES_V4
from emile.backtests.backtest_phase2_faithful import run_faithful

def main():
    xrp_h1 = load_h1("XRPUSDT")
    xrp_h4 = resample(xrp_h1, "4h")
    xrp_d1 = resample(xrp_h1, "1D")
    xrp_weekly = resample(xrp_h1, "W")
    print(f"XRP H4 (exécution) : {len(xrp_h4)} barres, {xrp_h4['date'].min()} -> {xrp_h4['date'].max()}")
    print(f"XRP D1 (stop UT+1, actif sans condition) : {len(xrp_d1)} barres")
    print(f"XRP Hebdomadaire (gate UT+2, ACTIF -- donnee H1 native disponible) : {len(xrp_weekly)} barres")

    rows = []
    for profile in PROFILES_V4:
        res = run_faithful(xrp_h4.copy(), xrp_d1.copy(), xrp_weekly.copy(), profile)
        rows.append({
            "symbol": "XRPUSDT", "timeframe_exec": "H4", "timeframe_stop": "D1 (UT+1, actif)",
            "timeframe_gate": "Hebdomadaire (UT+2, ACTIF)",
            "profile": profile, **res,
        })

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("oos_xrp_faithful_results.csv", index=False)

if __name__ == "__main__":
    main()
