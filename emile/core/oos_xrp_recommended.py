"""
Validation hors-échantillon (OOS) de LA config recommandée sur XRP -- sur le
modèle de `OOS_VALIDATION_CYCLE_SIGN.md` section 2 ("procédure décidée à
l'avance"), pour éviter le biais rétrospectif déjà identifié comme risque
dans ce projet (`AUDIT_QUALITE_ET_CORRECTION_CYCLE.md`, réserve méthodologique).
Contrairement à `OOS_VALIDATION_CYCLE_SIGN.md` (qui ne testait QUE la
corrélation du composant cycle isolé), ce script teste la config recommandée
COMPLÈTE (signal + gate + risk management + position engine).

REBRANCHÉ SUR LA DONNÉE RÉELLE (40e round, `PLAN.md`) -- l'ancienne version
------------------------------------------------------------------------------
Ce script pointait vers `/home/user/http-kaijin/crypto-decision-bi/...`, un
dépôt d'un ANCIEN sandbox disparu (confirmé par `FileNotFoundError` à
l'exécution) -- XRP n'y existait que comme 365 barres D1 (2025-06-03 ->
2026-06-02), obligeant à toute une procédure de repli (D1 comme "timeframe
disponible", gate MTF désactivé faute d'historique Hebdomadaire suffisant
pour `compute_cycle_phase_causal`, cf. l'historique git de ce fichier pour
le détail complet de cette procédure -- honnête à l'époque, mais plus
nécessaire).

**Cette limite n'existe plus** : XRP a désormais une VRAIE donnée H1 native
dans ce projet (`data/processed/XRPUSDT_1h_processed.csv`, 2020-01-06,
58 569 bougies, restaurée depuis l'API Binance Futures -- cf. `CLAUDE.md`,
intégrité vérifiée comme les 4 autres actifs). XRP peut donc désormais être
traité EXACTEMENT comme BTC/ETH/BNB/SOL : H4 pour l'exécution, Hebdomadaire
dérivé par `resample()` pour le gate MTF -- le pipeline NATUREL de
`recommended.py`, pas une procédure de repli. `use_mtf_gate=True` (le
défaut du moteur, jamais désactivé ici) devient pour la première fois
mesurable sur XRP : ~348 bougies Hebdomadaires disponibles (58569 barres H1
/ (24*7)), largement au-dessus des 150 bougies requises par `compute_
cycle_phase_causal` avant que son garde-fou anti-array-de-zéros ne cesse de
s'appliquer -- contrainte qui forçait la désactivation du gate dans
l'ancienne version.

Les 4 profils (FAIBLE/MODERE/AGRESSIF/TRES_AGRESSIF) restent testés, pas
seulement MODERE, par souci de complétude -- décidé avant résultat, comme
la version précédente. Aucune itération après coup : ce script est rejoué
une fois, le résultat (section CSV, `oos_xrp_recommended_results.csv`) est
rapporté tel quel, qu'il confirme ou non les attentes.

LIMITE RESTANTE, HONNÊTE
------------------------------------------------------------------------------
Toujours un seul actif -- l'OOS reste ce qu'il a toujours été (une
validation hors-échantillon sur XRP, jamais utilisé pour calibrer quoi que
ce soit dans ce projet), mais porte désormais sur ~6 ans d'historique H4
complet plutôt que sur 1 an de D1 -- un échantillon qualitativement
différent, à ne pas confondre avec le résultat de l'ancienne version (les
deux CSV ne sont PAS comparables : timeframe, période et présence du gate
MTF diffèrent tous les trois).
"""
import pandas as pd
import sys

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import PROFILES_V4
from emile.backtests.backtest_phase2_recommended import run_recommended

def main():
    xrp_h1 = load_h1("XRPUSDT")
    xrp_h4 = resample(xrp_h1, "4h")
    xrp_weekly = resample(xrp_h1, "W")
    print(f"XRP H4 : {len(xrp_h4)} barres, {xrp_h4['date'].min()} -> {xrp_h4['date'].max()}")
    print(f"XRP Hebdomadaire (gate) : {len(xrp_weekly)} barres")

    rows = []
    for profile in PROFILES_V4:
        res = run_recommended(xrp_h4.copy(), xrp_weekly.copy(), profile)
        rows.append({"symbol": "XRPUSDT", "timeframe": "H4", "gate_mtf": "ACTIF (donnee H1 native disponible)",
                     "profile": profile, **res})

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("oos_xrp_recommended_results.csv", index=False)

if __name__ == "__main__":
    main()
