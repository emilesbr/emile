# Phase 2 — Correction du breakeven prématuré (suite au corpus Trading Lessons)

**Décision de directeur opérationnel** : après 17 sources traitées, dont 7 confirmant indépendamment la même règle ("le passage au Break-even est interdit avant la Confirmation, pas seulement à la Validation" — sources #12, #13, #15, #16 notamment, formulation quasi identique à chaque fois), la collecte de nouvelles sources atteignait un rendement marginal décroissant (les 2 dernières sources #16/#17 reconfirmaient surtout l'acquis). Plutôt que de continuer à accumuler indéfiniment, on corrige maintenant ce que le corpus a mis en évidence.

## Le bug corrigé
Dans `PHASE2_MONEYMANAGEMENT.md` / `PHASE2_FULL_MATRIX.md`, le stop était remonté au breakeven dès l'étape de **Validation** pour les profils FAIBLE/MODÉRÉ/AGRESSIF (approximation de "SL payé"/"SL BE" du tableau du PDF officiel). Le corpus Trading Lessons indique unanimement que ce passage doit attendre la **Confirmation**, sous peine de sortie systématique sur un pullback de respiration normal.

**Correction appliquée** : le stop n'est plus remonté au breakeven à la Validation (la prise de profit partielle reste inchangée à cette étape) ; il ne l'est qu'à la Confirmation, comme c'était déjà correctement implémenté à cette étape.

## Résultat de la comparaison avant/après (`phase2_CORRECTED_results.csv` vs `phase2_moneymanagement_results.csv`)

| Timeframe | Δ Retour moyen | Δ Max Drawdown moyen |
|---|---|---|
| **H4** | **+35,8 points** | **-5,4 points (meilleur)** |
| D1 | -5,4 points | -0,8 points (légèrement meilleur) |

**Sur H4 : gain net sur toute la ligne** (plus de retour ET moins de risque). Cas le plus marquant : ETH H4 profil Agressif, +43,1% → **+312,6%** de retour, drawdown -65,0% → **-37,9%**. Confirme empiriquement, avec des chiffres, ce que le corpus annonçait théoriquement.

Sur D1 : effet neutre à légèrement négatif sur le retour brut, pas pire sur le drawdown — les mouvements plus larges du D1 rendaient l'ancien bug moins coûteux qu'en H4.

## Profils non affectés (sanity check du fix)
TRÈS_AGRESSIF montre un delta de 0 partout — attendu, puisque ce profil n'avait déjà aucune action de stop à la Validation ("RIEN" dans la table d'origine). Bon signe que la correction est bien isolée aux profils concernés.

## Conclusion
Le corpus Trading Lessons a payé : une correction précise, bien étayée (7 confirmations indépendantes), a été identifiée et validée empiriquement avec un gain substantiel sur H4. `phase2_CORRECTED_results.csv` remplace `phase2_moneymanagement_results.csv` / `phase2_full_matrix_results.csv` comme référence à jour pour la Phase 2.

## Ce qui reste ouvert (non traité par cette correction)
- Mécanisme "+Reverse" du profil Très Agressif toujours non implémenté
- Table "trade de tendance" toujours non testée (seule la table range/spéculatif l'a été)
- Diversification 1%+1% (deux patterns non corrélés) non implémentée — nécessiterait un second signal indépendant du proxy EMA actuel
- "Règle de Trois" (invalidation après 3 zones exploitées) non implémentée
- Signal toujours un proxy générique, pas le vrai PRO Framework/Momentum
