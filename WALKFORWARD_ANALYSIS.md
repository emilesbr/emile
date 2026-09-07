# Analyse walk-forward par année — Phase 1 (proxy générique)

Décomposition année par année du backtest multi-timeframe (`BACKTEST_RESULTS_MTF.md`), données brutes dans `walkforward_full.csv` (49 lignes : actif × timeframe × année).

## 1. Stabilité par timeframe

| Timeframe | % années Sharpe>0 | Sharpe moyen | Écart-type Sharpe |
|---|---|---|---|
| M15 | 0% (0/16) | -3,92 | 2,15 |
| H1 | 35,7% (10/28) | -0,30 | 1,4–1,7 |
| H4 | 50,0% (12/24) | +0,40 | 1,3–1,7 |
| D1 | 60,9% (14/23) | +0,44 | 0,8–1,5 |

Le M15 est négatif **toutes les années sans exception** — échec structurel (coût de transaction), pas de malchance ponctuelle. Le D1 est le seul régime à majorité d'années gagnantes et le plus stable.

## 2. Sharpe moyen par année et par timeframe (effet régime de marché)

| Année | D1 | H1 | H4 | M15 | Contexte |
|---|---|---|---|---|---|
| 2020 | +1,66 | +0,74 | +1,43 | -1,15 | Bull run post-Covid |
| 2021 | +0,58 | +1,25 | +1,48 | -2,41 | Bull run / altseason |
| 2022 | -1,24 | -1,81 | -0,74 | -5,21 | Bear market (Luna/FTX) |
| 2023 | +1,40 | -0,08 | +0,89 | -3,51 | Reprise progressive |
| 2024 | +0,04 | +0,04 | +1,27 | -2,79 | Bull run (halving) |
| 2025 | +0,48 | -0,91 | -0,10 | -4,70 | Mitigé |
| 2026* | n/a | -1,36 | -1,42 | -7,68 | Partiel (6 mois) |

2022 est mauvais pour tous les timeframes ET tous les actifs — effet de régime de marché pur (effondrement Luna/FTX), confirmant que le backtest réagit de façon cohérente à la réalité du marché (pas un artefact du code). *2026 : données jusqu'au 01/07/2026 seulement, à ne pas sur-interpréter.

## 3. Cohérence inter-actifs (H1, par année)

| Année | BNB | BTC | ETH | SOL |
|---|---|---|---|---|
| 2020 | +0,09 | +1,90 | +2,49 | -1,52 |
| 2021 | +2,09 | -0,01 | +0,96 | +1,96 |
| 2022 | -1,56 | -2,62 | -0,88 | -2,16 |
| 2023 | -2,10 | +0,43 | -0,74 | +2,08 |
| 2024 | -0,05 | +0,77 | -0,70 | +0,14 |

En crise (2022), tous les actifs plongent ensemble (corrélation crypto classique). En année normale, forte divergence entre actifs (ex. 2023 : BNB -2,10 vs SOL +2,08) — le proxy générique n'a pas d'edge stable et reproductible par actif, surtout de la variance conjoncturelle.

## Conclusions
1. D1 est le timeframe le plus défendable avec ce proxy (majorité d'années positives, meilleure stabilité).
2. H1 est trop instable pour être GO en l'état.
3. M15 rejeté empiriquement sans exception — cohérent à 100% avec la mise en garde anti-scalping du manuel PRO Indicators.
4. Aucun timeframe ni actif n'a échappé à la casse en 2022 — le risk management (stop ATR, 1%/trade) limite l'ampleur des pertes mais n'annule pas un effondrement systémique généralisé.
