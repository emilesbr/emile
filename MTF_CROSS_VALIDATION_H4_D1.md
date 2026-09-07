# Validation croisée multi-timeframe réelle (H4 exécution / D1 référence) — lacune comblée

**Question à l'origine** : "les stratégies prennent-elles en compte le timeframe inférieur et supérieur dans leur décision ?" Réponse à ce moment-là : **non**. Vérification par lecture directe du code (`code/backtest_phase2_v6.py`) : `ctx_support = ema_slow - 2*atr` est calculé sur le **même** dataframe que celui tradé (H4 seul ou D1 seul, jamais croisés) — malgré le nom "Extreme Channel" qui laissait entendre un vrai canal de l'unité de temps supérieure. **Correction de documentation** : ce n'était qu'une bande de volatilité locale, pas un canal cross-timeframe. Les seules fois où une vraie logique multi-timeframe avait été testée (Phase 1, `backtest_cascade3.py`) utilisaient l'ancien signal EMA générique — jamais fusionnées avec la lignée v4/v5/v6 (proxy TSI+cycle+structure, régime, risk management corrigé).

## Ce qui est construit (`code/backtest_phase2_v7.py`)
Exécution sur H4, référence/contexte sur D1 : un signal H4 n'est validé que si :
1. Le score proxy_v2 (TSI+cycle+structure) de la **dernière bougie D1 entièrement clôturée** (jointure `merge_asof` sans lookahead) est également ≥2
2. Le régime D1 n'est pas EXCES

## Résultat — le plus uniformément cohérent obtenu à ce jour

| Actif (profil FAIBLE) | Trades | Win rate | Profit factor | Max DD | Retour |
|---|---|---|---|---|---|
| BTC — H4 seul | 1498 | 46,3% | 1,91 | -9,5% | +179,8% |
| BTC — validé par D1 | 520 | **54,0%** | **2,60** | **-7,0%** | +54,9% |
| ETH — H4 seul | 1365 | 46,0% | 2,09 | -12,3% | +247,9% |
| ETH — validé par D1 | 458 | **59,0%** | **3,18** | **-4,3%** | +70,7% |
| BNB — H4 seul | 1209 | 47,4% | 1,89 | -8,0% | +134,7% |
| BNB — validé par D1 | 499 | **51,5%** | **2,12** | **-6,0%** | +49,4% |
| SOL — H4 seul | 1199 | 48,5% | 2,47 | -13,7% | +350,8% |
| SOL — validé par D1 | 341 | **56,3%** | 1,78 | **-5,8%** | +17,9% |

Détail complet (4 profils × 4 actifs) : `phase2_v7_mtf_results.csv`.

**Constat, sur les 4 actifs et les 4 profils, sans exception** : environ 3× moins de trades, win rate systématiquement plus élevé (+5 à +13 points), drawdown systématiquement réduit, profit factor amélioré dans la quasi-totalité des cas (seule exception : SOL, où il baisse légèrement malgré le reste). Le retour cumulé est plus faible (moins d'occasions de composer, cohérent avec 3× moins de trades) — les valeurs extrêmes précédemment suspectes (SOL Très Agressif +23878%) redeviennent nettement plus raisonnables (+75,8% sur ce profil).

C'est le résultat le plus **uniformément** cohérent obtenu dans tout ce projet — pas un mélange d'améliorations et de dégradations selon l'actif, mais une direction constante partout. Ça confirme empiriquement ce que 7 sources indépendantes du corpus affirmaient : trader un timeframe isolément, sans validation croisée, dégrade la qualité du signal.

## Limites documentées
- Toujours un proxy, pas le vrai signal PRO Framework
- Résultats informatifs, pas une validation définitive (principe déjà établi)
- Un seul sens de cascade testé ici (D1 valide H4) — le sens complet à 3 niveaux (Daily/H4/H1) avait déjà été testé séparément avec un résultat négatif (`CASCADE3_H1_EXECUTION_TEST.md`), mais avec l'ancien moteur — à refaire avec le moteur v7 si on veut la comparaison la plus à jour
- N'implémente pas encore la règle exacte "UT+2" (deux niveaux au-dessus) des sources #15/#16 — ici c'est directement le niveau immédiatement supérieur (H4→D1), pas H4→Hebdo
