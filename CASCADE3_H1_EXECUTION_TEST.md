# Test : cascade à 3 niveaux (Daily référence → H4 contexte → H1 exécution)

**Résultat négatif/inconclusif — documenté pour ne pas relancer cette piste inutilement.**

## Hypothèse testée
Le corpus Trading Lessons (sources #15, #16) décrit le H1 non pas comme une stratégie autonome, mais comme une **couche d'exécution** au sein d'une cascade à 3 niveaux : Daily (référence, direction de fond) → H4 (contexte, canaux) → H1 (exécution, timing). Notre conclusion Phase 1 ("H1 = NO-GO") reposait sur du H1 testé seul ou avec un seul niveau de contexte. Hypothèse : le H1 correctement utilisé DANS cette cascade à 3 niveaux pourrait devenir viable.

## Méthodologie
Signal = triple alignement haussier (score de confluence EMA ≥2) simultanément sur Daily, H4 ET H1, exécution/gestion de position en H1, avec le risk management corrigé de la Phase 2 (breakeven différé à la Confirmation, cf. `PHASE2_CORRECTION_BREAKEVEN.md`).

## Résultat (profil FAIBLE, 4 actifs)

| Actif | Retour | Max Drawdown |
|---|---|---|
| BTC | -5,1% | -36,6% |
| ETH | -29,9% | -53,0% |
| BNB | -41,1% | -52,9% |
| SOL | +7,3% | -23,0% |

**Pire ou équivalent au H1 seul et à la cascade à 2 niveaux testée en Phase 1** (`PHASE1_CLOSEOUT.md`). L'hypothèse n'est pas validée.

## Diagnostic
Le nombre de trades reste élevé (1300-1800 sur ~16000 bougies alignées) malgré le triple alignement — le signal d'exécution H1 (confluence EMA générique) continue de générer des allers-retours fréquents même quand Daily et H4 restent alignés bullish. **Ce n'est pas la structure de cascade qui pose problème, c'est la qualité du signal d'exécution lui-même.** Le vrai système utilise vraisemblablement un signal d'entrée précis (type détection de "3ème borne", momentum réel PRO) pour le timing en H1 — pas une simple confluence de moyennes mobiles génériques, qui reste bruitée à cette granularité quel que soit le contexte macro.

## Conclusion
La structure de cascade multi-timeframe a été testée sous plusieurs formes (2 niveaux en Phase 1, 3 niveaux ici) sans rendre le H1 viable avec le proxy générique actuel. **Le goulot d'étranglement n'est plus la structure temporelle — c'est le signal.** Poursuivre l'ingénierie de cascade sur ce proxy a atteint un plafond de rendement. Le déblocage quantitatif restant passe par le signal réel PRO Framework/Momentum (export TradingView), pas par davantage de raffinement de la mécanique multi-timeframe sur le proxy.
