# Phase 1 — Clôture (compléments : cascade multi-timeframe + sensibilité paramétrique)

Suite à `BACKTEST_RESULTS_MTF.md` et `WALKFORWARD_ANALYSIS.md`, trois points restaient ouverts avant de considérer la Phase 1 terminée. Ce document les clôt.

## A. Cascade multi-timeframe réelle (données : `cascade_results.csv`)

Jusqu'ici chaque timeframe était testé isolément. Or le manuel impose une règle de base : **toujours trader dans un contexte**, avec une table stricte TF Local → TF Supérieur (chapitre 4) : H1→H4, H4→D1, D1→W1. On a donc reconstruit un vrai test en cascade : un signal local n'est validé que si le contexte du TF supérieur (même confluence EMA, sur la bougie supérieure la plus récente **entièrement close**, sans lookahead) est également favorable. W1 dérivé du H1 par agrégation.

| Actif | TF | Sharpe seul → cascade | DD seul → cascade |
|---|---|---|---|
| BTC | H1 | -0,17 → **+0,31** | -70,8% → **-40,9%** |
| BTC | H4 | 1,12 → **1,28** | -23,5% → **-12,7%** |
| BTC | D1 | 1,12 → 0,86 | -11,4% → -10,9% |
| ETH | H1 | 0,22 → **0,46** | -69,1% → **-50,3%** |
| ETH | H4 | 0,86 → 0,82 | -18,9% → -19,2% |
| ETH | D1 | 0,64 → 0,60 | -15,7% → -14,0% |
| BNB | H1 | -0,41 → -0,26 | -81,0% → -70,0% |
| BNB | H4 | 0,90 → 0,95 | -23,4% → -21,3% |
| BNB | D1 | 0,91 → 0,90 | -19,9% → -19,9% |
| SOL | H1 | 0,55 → 0,72 | -43,6% → -30,8% |
| SOL | H4 | 1,07 → **1,23** | -21,1% → **-11,3%** |
| SOL | D1 | 0,98 → 0,99 | -20,9% → -16,0% |

**Constat** : le filtre de contexte améliore quasi systématiquement le couple rendement/risque sur H1 et H4 (drawdowns souvent divisés par 2). Sur D1, l'effet du contexte W1 est neutre/mixte — probablement redondant avec l'EMA(55) déjà lente utilisée en D1.

### Vérification stricte : walk-forward annuel, H1 en cascade

BTC : 2020=+1,91 / 2021=-0,10 / 2022=-1,50 / 2023=+1,04 / 2024=+1,40 / 2025=-1,62 / 2026=-1,72
ETH : 2020=+2,29 / 2021=+0,66 / 2022=0,00 / 2023=-0,03 / 2024=-0,57 / 2025=-0,60 / 2026=-1,16

**Verdict honnête : amélioration nette, mais toujours NO-GO au sens strict du plan.** Aucune série de ≥3 années consécutives à Sharpe positif (max 2 consécutives : 2023-2024 pour BTC). Le H1 progresse mais reste à ne pas trader en l'état avec ce proxy.

## B. Sensibilité paramétrique (données : `sensitivity_results.csv`)

3 réglages d'EMA testés sur H4 et D1 (les deux timeframes GO) : rapide (5/20/50), standard (8/21/55), lent (10/30/100).

Sharpe H4 : 0,83–1,23 selon réglage et actif. Sharpe D1 : 0,63–1,15. **Pas d'effondrement en changeant les paramètres** — signe rassurant de robustesse relative, pas de surapprentissage grossier à un réglage arbitraire.

## C. XRP — limite de périmètre documentée
Aucune donnée horaire réelle avec historique suffisant trouvée sur les dépôts GitHub publics accessibles. XRP reste absent du backtest multi-timeframe (présent uniquement dans l'ancien test 1-an/daily). À combler si une source de données appropriée est identifiée plus tard.

## Verdict final Phase 1
- **H4 = timeframe le plus robuste**, confirmé et renforcé par la cascade (Sharpe jusqu'à 1,28, drawdowns divisés par ~2), stable aux changements de paramètres. **GO.**
- **D1 = solide seul**, cascade neutre. **GO.**
- **H1 = amélioré mais toujours instable** au sens du critère strict (pas de série ≥3 ans positifs). **NO-GO** avec ce proxy en l'état.
- **M15 = rejeté sans appel** (cf. `WALKFORWARD_ANALYSIS.md`). **NO-GO.**

Phase 1 est close. Passage à la Phase 2 (money management appliqué spécifiquement sur H4/D1).
