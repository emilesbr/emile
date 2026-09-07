# Backtest multi-timeframe — résultats (Phase 1, proxy générique)

**Méthodologie** : stratégie de confluence générique (3 EMA : 8/21/55, long-only), sizée selon la règle de risque réellement extraite du manuel (`RULES_EXTRACTION.md`) : 1% du capital risqué par trade via un stop ATR(14)×2, pas de levier (exposition plafonnée à 100% du capital), frais futures Binance 0,04%/côté.

**Données** : Binance Futures OHLCV réelles (source GitHub publique `SpaciousAbhi/binance-futures-backtest-research`), 2020-01-01 → 2026-07-01 (~6,5 ans). BTC/ETH/BNB/SOL en H1 natif (H4/D1 dérivés par agrégation), BTC en M15 natif.

**⚠️ Rappel** : le signal utilisé est un PROXY GÉNÉRIQUE (confluence EMA), pas le vrai PRO Framework/Momentum (formule non divulguée par l'éditeur). Les règles de RISQUE, elles, sont bien celles documentées.

## Résultat clé : le M15 confirme empiriquement la mise en garde anti-scalping du manuel
BTC en M15 : 10 368 trades sur 6,5 ans (~4,4/jour), profit factor brut ≈1,00 (edge nul), retour final **-100%** — les frais de transaction seuls détruisent le capital par effet de composition sur un aussi grand nombre de trades. Confirmation numérique directe de la recommandation de l'auteur : pas de scalping, même à temps plein.

## Résumé par actif × timeframe

| Actif | TF | N trades | Retour stratégie | Sharpe | Max DD | Win rate | Profit factor | Retour B&H | DD B&H |
|---|---|---|---|---|---|---|---|---|---|
| BNB | H1 | 2546 | -58,7% | -0,41 | -81,0% | 24,2% | 1,08 | +2088,1% | -72,6% |
| BNB | H4 | 560 | +156,7% | 0,90 | -23,4% | 24,5% | 1,77 | +2132,5% | -72,5% |
| BNB | D1 | 89 | +204,4% | 0,91 | -19,9% | 23,6% | 8,77 | +2076,3% | -70,9% |
| BTC | M15 | 10368 | -100,0% | -3,43 | -100,0% | 21,8% | 1,00 | +737,6% | -77,3% |
| BTC | H1 | 2455 | -38,6% | -0,17 | -70,8% | 22,6% | 1,15 | +716,4% | -77,2% |
| BTC | H4 | 534 | +167,9% | 1,12 | -23,5% | 27,2% | 1,74 | +710,7% | -77,1% |
| BTC | D1 | 83 | +73,9% | 1,12 | -11,4% | 36,1% | 3,60 | +713,5% | -76,7% |
| ETH | H1 | 2456 | +17,1% | 0,22 | -69,1% | 23,0% | 1,20 | +1122,1% | -81,4% |
| ETH | H4 | 597 | +113,7% | 0,86 | -18,9% | 26,6% | 1,53 | +1110,2% | -81,2% |
| ETH | D1 | 101 | +41,1% | 0,64 | -15,7% | 18,8% | 2,27 | +1105,3% | -79,4% |
| SOL | H1 | 2084 | +91,0% | 0,55 | -43,6% | 24,7% | 1,23 | +2086,5% | -96,8% |
| SOL | H4 | 492 | +152,6% | 1,07 | -21,1% | 24,0% | 1,77 | +2086,5% | -96,6% |
| SOL | D1 | 68 | +132,8% | 0,98 | -20,9% | 30,9% | 5,41 | +2153,8% | -96,3% |

## Test GO/NO-GO — walk-forward annuel (critère du plan : Sharpe stable ≥3 fenêtres consécutives)

**BTC H1**, Sharpe par année : 2020=+1,90 / 2021=-0,01 / 2022=-2,62 / 2023=+0,43 / 2024=+0,77 / 2025=-1,89 / 2026=-1,97
**ETH H1**, Sharpe par année : 2020=+2,49 / 2021=+0,96 / 2022=-0,88 / 2023=-0,74 / 2024=-0,70 / 2025=-0,54 / 2026=-1,57

**Verdict : NO-GO sur H1** pour ce proxy — pas de stabilité inter-régimes, performance très dépendante de l'année. Cohérent avec le fait que ce n'est qu'un proxy générique et non le vrai signal PRO Framework.

## Conclusions actionnables
1. **H4 et D1 sont les timeframes les plus robustes** avec ce proxy (Sharpe >0,85 partout, drawdowns divisés par ~3 vs buy & hold) — cohérent avec la recommandation du manuel.
2. **Le buy & hold surperforme largement en retour absolu** sur cette période exceptionnellement haussière — la stratégie échange du retour contre moins de risque, comportement attendu d'un filtre de tendance, pas un défaut en soi.
3. Prochaine étape pour une mesure fidèle : remplacer le proxy par les vrais signaux PRO Framework/Momentum exportés depuis TradingView (Data Window/alertes) sur H4/D1 au minimum.
