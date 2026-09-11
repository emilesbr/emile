"""
Mécanisme "+Reverse" du profil Très Agressif à la Limite -- TABLE RANGE
(RULES_EXTRACTION.md §3, "Money management -- Trade spéculatif (range)").
Item 7 du backlog `PLAN.md` (moitié "+Reverse table range" -- l'autre
moitié, diversification 1%+1%/Cluster Technique, traitée séparément par un
autre agent, nouveaux fichiers uniquement, `cluster_technique.py`).

POURQUOI CE FICHIER PLUTÔT QUE MODIFIER `main()` DE backtest_phase2_v7.py
--------------------------------------------------------------------------
`run_v7` expose désormais un paramètre `reverse_at_limit` (même principe que
`use_mtf_stop`, ajouté au même endroit -- cf. `code/position_engine.py` pour
le mécanisme lui-même, hypothèse H-Reverse-Range documentée en tête de ce
fichier-là). On AURAIT pu ajouter une 3e combinaison à la boucle de `main()`
dans `backtest_phase2_v7.py`, mais celle-ci boucle sur LES 4 PROFILS pour
comparer gate/stop MTF -- une dimension transverse à tous les profils. Le
"+Reverse" documenté par la source (RULES_EXTRACTION.md §3) est en revanche
SPÉCIFIQUE au profil Très Agressif ("Très agressif | RIEN | — | RIEN |
TP100%+Reverse" -- les 3 autres profils n'ont jamais "+Reverse" dans la
table). Mélanger une comparaison "tous profils x 3 dimensions MTF" avec une
comparaison "Très Agressif seul x reverse on/off" dans la même boucle aurait
produit un tableau confus (3/4 des lignes n'auraient aucun sens pour la
colonne reverse). D'où ce script dédié : import direct de `run_v7` (aucune
duplication du moteur, contrairement à `backtest_phase2_capital_tiers.py` qui,
lui, devait réellement changer le calcul de `risk_pct` de façon incompatible
avec la signature de `run_v7` telle qu'elle existait alors).

PARAMÈTRES EXACTS DE LA JAMBE REVERSE (rappel, hypothèse H-Reverse-Range
détaillée dans `position_engine.py`) : le manuel ne donne NI taille, NI
stop, NI cible pour cette jambe -- seulement "TP100%+Reverse". Hypothèse
retenue : jambe short "miroir" de la jambe long qui vient de se clôturer
(même taille, stop à la même distance % au-dessus du nouveau prix d'entrée
que le long en avait en dessous, cible à la même distance % en dessous que
le long avait au-dessus pour sa Limite), ouverte immédiatement au prix de
clôture qui a déclenché la Limite. AUCUNE sous-étape (pas de Validation/
Confirmation côté short) -- jambe bornée simple, comme le "+Reverse" de la
table TENDANCE (`trend_table.py`, hypothèse H10) l'est déjà pour son propre
mécanisme, structurellement différent (à ne pas confondre, cf. les deux
en-têtes de fichier respectifs).

Rappel du principe du projet, appliqué ici comme partout ailleurs : la
performance mesurée ci-dessous ne remet JAMAIS en cause l'implémentation
elle-même -- un résultat décevant reste un résultat honnête à rapporter,
pas un motif pour ne pas construire un élément documenté du corpus.
"""
import pandas as pd
import sys

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import run_v7, PROFILES_V4

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    profile = "TRES_AGRESSIF"
    assert profile in PROFILES_V4
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        res_off = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False,
                          reverse_at_limit=False)
        res_on = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False,
                         reverse_at_limit=True)
        rows.append({"symbol": symbol, "profile": profile, "reverse_at_limit": False, **res_off})
        rows.append({"symbol": symbol, "profile": profile, "reverse_at_limit": True, **res_on})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_v7_reverse_results.csv", index=False)

if __name__ == "__main__":
    main()
