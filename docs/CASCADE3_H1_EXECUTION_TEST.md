# Test : cascade à 3 niveaux (Daily référence → H4 contexte → H1 exécution)

**Refait le 2026-09-07 avec le moteur de risque actuel — conclusion reconduite, chiffres mis à jour.**
Ce document a été recalculé avec le moteur de gestion de position actuellement
en vigueur (Validation/Confirmation/Limite sur clôtures et pas sur mèches ;
breakeven différé à la Confirmation ; désormais factorisé dans
`position_engine.py`, partagé avec `backtest_phase2.py`/`_v4.py`/`_v5.py` — cf.
`AUDIT_QUALITE_ET_CORRECTION_CYCLE.md`, refactoring effectué et vérifié
numériquement identique au comportement pré-refactoring). La version
précédente (résultat FAIBLE uniquement, moteur périmé) est conservée en note
historique en bas de page.

## Hypothèse testée
Le corpus Trading Lessons (sources #15, #16) décrit le H1 non pas comme une
stratégie autonome, mais comme une **couche d'exécution** au sein d'une cascade
à 3 niveaux : Daily (référence, direction de fond) → H4 (contexte, canaux) →
H1 (exécution, timing). Notre conclusion Phase 1 ("H1 = NO-GO") reposait sur
du H1 testé seul ou avec un seul niveau de contexte. Hypothèse : le H1
correctement utilisé DANS cette cascade à 3 niveaux pourrait devenir viable.

## Méthodologie
Signal = triple alignement haussier (score de confluence EMA ≥2) simultanément
sur Daily, H4 ET H1, exécution/gestion de position en H1, moteur de risque
Phase 2 complet et à jour (breakeven différé à la Confirmation, Validation/
Confirmation/Limite sur clôtures). Code : `backtest_cascade3.py` (logique de
cascade inchangée — seule la fonction de gestion de position qu'il importe,
`run_backtest_mm`, a été refactorisée vers `position_engine.py`, sans
changement de comportement observable, vérifié par ré-exécution comparée à
l'ancien code).

## Résultat (4 profils de risque, 4 actifs) — `code/cascade3_h1execution_results.csv`

| Actif | Profil | Bougies alignées | Trades | Retour | Max Drawdown | Win rate | Profit factor |
|---|---|---:|---:|---:|---:|---:|---:|
| BTC | FAIBLE | 16 686 | 1 516 | **+1,6%** | -40,2% | 36,3% | 1,19 |
| BTC | MODÉRÉ | 16 686 | 1 516 | +17,5% | -53,6% | 35,8% | 1,19 |
| BTC | AGRESSIF | 16 686 | 1 305 | +117,7% | -42,7% | 35,7% | 1,25 |
| BTC | TRÈS AGRESSIF | 16 686 | 1 305 | +183,3% | -42,5% | 31,1% | 1,25 |
| ETH | FAIBLE | 16 300 | 1 539 | **-8,0%** | -50,6% | 36,9% | 1,13 |
| ETH | MODÉRÉ | 16 300 | 1 539 | -11,5% | -72,0% | 36,2% | 1,12 |
| ETH | AGRESSIF | 16 300 | 1 288 | +22,3% | -74,0% | 36,3% | 1,14 |
| ETH | TRÈS AGRESSIF | 16 300 | 1 288 | +16,4% | -76,4% | 30,2% | 1,13 |
| BNB | FAIBLE | 15 826 | 1 608 | **-27,5%** | -52,6% | 37,6% | 1,09 |
| BNB | MODÉRÉ | 15 826 | 1 608 | -46,2% | -73,0% | 37,0% | 1,07 |
| BNB | AGRESSIF | 15 826 | 1 348 | -23,3% | -75,9% | 36,0% | 1,10 |
| BNB | TRÈS AGRESSIF | 15 826 | 1 348 | -32,4% | -81,8% | 29,2% | 1,09 |
| SOL | FAIBLE | 11 993 | 1 208 | **+19,6%** | -30,1% | 36,3% | 1,14 |
| SOL | MODÉRÉ | 11 993 | 1 208 | +28,4% | -52,0% | 35,8% | 1,13 |
| SOL | AGRESSIF | 11 993 | 1 028 | +62,0% | -60,8% | 34,8% | 1,14 |
| SOL | TRÈS AGRESSIF | 11 993 | 1 028 | +105,8% | -63,2% | 29,5% | 1,15 |

Détail complet (avg_trade_%, final_equity) : `code/cascade3_h1execution_results.csv`.

## Comparaison avec l'ancien résultat (profil FAIBLE, moteur périmé)

| Actif | Ancien retour (moteur périmé) | Nouveau retour (moteur actuel) | Ancien Max DD | Nouveau Max DD |
|---|---:|---:|---:|---:|
| BTC | -5,1% | **+1,6%** | -36,6% | -40,2% |
| ETH | -29,9% | **-8,0%** | -53,0% | -50,6% |
| BNB | -41,1% | **-27,5%** | -52,9% | -52,6% |
| SOL | +7,3% | **+19,6%** | -23,0% | -30,1% |

La correction du moteur (clôtures au lieu de mèches, breakeven réellement
différé à la Confirmation) améliore le retour sur les 4 actifs en profil
FAIBLE — cohérent avec l'amélioration déjà observée ailleurs
(`PHASE2_CORRECTION_CLOSES.md`). Le max drawdown, lui, ne s'améliore pas
systématiquement (BTC et SOL légèrement pires qu'avant).

## Diagnostic

Le nombre de trades reste très élevé à tous les profils (1 028 à 1 608 sur
12 000-16 700 bougies alignées, soit un trade toutes les ~10-13 bougies
alignées) malgré le triple alignement Daily/H4/H1 — inchangé par rapport au
constat d'origine. Le signal d'exécution H1 (confluence EMA générique)
continue de générer des allers-retours fréquents même quand Daily et H4
restent alignés bullish. Aux profils plus agressifs, les retours affichés
(BTC +183%, SOL +106%) s'accompagnent de drawdowns de 42-63% — le même
ratio retour/risque globalement dégradé que celui déjà observé sur H4/D1 en
Phase 2 (plus de levier affiché, pas une amélioration de l'edge). BNB reste
négatif sur les 4 profils de risque sans exception.

## Conclusion

**La conclusion d'origine est reconduite, pas infirmée.** Les chiffres absolus
s'améliorent avec le moteur corrigé (surtout en profil FAIBLE), mais le
tableau reste hétérogène et non concluant : BNB perd de l'argent à tous les
niveaux de risque testés, ETH reste négatif ou marginal aux profils
conservateurs, et les cas positifs (BTC, SOL) ne le deviennent nettement
qu'à des niveaux de risque/drawdown élevés (profils AGRESSIF/TRÈS AGRESSIF,
DD 42-81%). Le nombre de trades reste très élevé — **ce n'est toujours pas
la structure de cascade qui pose problème, c'est la qualité du signal
d'exécution H1 lui-même**, qui continue à générer des retournements fréquents
quel que soit le contexte macro validé sur Daily/H4. Le déblocage
quantitatif restant passe par le signal réel PRO Framework/Momentum (export
TradingView), pas par davantage de raffinement de la mécanique multi-
timeframe sur le proxy EMA générique.

---

## Note historique — version pré-correction (calculée avant la correction clôtures/mèches)

Résultat original (profil FAIBLE, 4 actifs), calculé avec une version du
moteur antérieure à `PHASE2_CORRECTION_CLOSES.md` :

| Actif | Retour | Max Drawdown |
|---|---|---|
| BTC | -5,1% | -36,6% |
| ETH | -29,9% | -53,0% |
| BNB | -41,1% | -52,9% |
| SOL | +7,3% | -23,0% |

Conclusion à l'époque : "pire ou équivalent au H1 seul et à la cascade à
2 niveaux testée en Phase 1 ; le goulot d'étranglement n'est plus la
structure temporelle, c'est le signal." Cette conclusion tient toujours
après recalcul avec le moteur actuel (voir ci-dessus) — elle est confirmée,
pas seulement reconduite par défaut.
