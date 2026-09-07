# Analyse du funding rate — coût jamais modélisé jusqu'ici

**Contexte** : identifié comme lacune ouverte dans `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md` (point 6) et `PLAN.md` (Phase 2, lacune 4) — les frais de transaction (0,04%/côté) sont modélisés dans tous les backtests du projet, mais le funding des contrats perpétuels Binance Futures, lui, ne l'a jamais été. Ce document en donne l'ordre de grandeur et une recommandation d'intégration.

## Méthodologie

**Données** : dépôt public GitHub `SpaciousAbhi/binance-futures-backtest-research` (déjà utilisé comme source pour `BACKTEST_RESULTS_MTF.md`), fichiers `<ASSET>USDT_1h_processed.csv`. Colonnes vérifiées par inspection directe : chaque fichier contient bien `fundingRate` (taux appliqué) et `fundingTime` (horodatage de l'événement), aux côtés de l'OHLCV horaire.

**Mécanique du funding** (rappel) : sur les perpétuels Binance, un paiement est échangé entre positions longues et courtes toutes les 8h (~00:00/08:00/16:00 UTC), proportionnel à la valeur notionnelle de la position. Taux positif → les longs paient les shorts ; taux négatif → les longs reçoivent (le marché a historiquement plus souvent des longs "en excès", donc un taux majoritairement positif sur les périodes haussières).

**Point technique important** : dans les CSV sources, `fundingRate` est répété (forward-fill) sur chaque bougie horaire entre deux événements réels de funding — sommer directement la colonne horaire aurait compté chaque paiement ~8 fois. Le script déduplique donc sur le couple `(fundingTime, fundingRate)` pour ne garder qu'une ligne par événement réel avant de sommer (vérifié : le nombre d'événements après déduplication correspond à ~3/jour, cohérent avec le cycle de 8h — colonne `coverage_vs_expected_pct` ≈ 100% dans le CSV de sortie).

**Simulation** : position longue permanente (« buy & hold »), taille = 100% du capital, sans levier (cohérent avec la convention du reste du projet — cf. `RULES_EXTRACTION.md`/`BACKTEST_RESULTS_MTF.md`, exposition plafonnée à 100%), sans réinvestissement des gains (approximation au premier ordre, suffisante pour un ordre de grandeur). Coût cumulé = somme des taux de funding réels sur toute la période disponible par actif, exprimé en % du capital initial ; taux annualisé moyen = coût cumulé / nombre d'années couvertes.

Script : `funding_rate_analysis.py` (racine du dépôt). Sortie : `funding_rate_summary.csv`.

## Résultats — position longue permanente, tout l'historique disponible

| Actif | Période | Années | Événements de funding | % événements où le long paie | Coût cumulé (% du capital) | **Coût annualisé moyen (%/an)** |
|---|---|---|---|---|---|---|
| BTC | 2020-01-01 → 2026-07-01 | 6,50 | 7 120 | 85,5% | +77,5% | **+11,9%/an** |
| ETH | 2020-01-01 → 2026-07-01 | 6,50 | 7 120 | 86,0% | +92,2% | **+14,2%/an** |
| BNB | 2020-02-10 → 2026-07-01 | 6,38 | 6 999 | 24,7% | -1,5% | **-0,2%/an** |
| SOL | 2020-09-14 → 2026-07-01 | 5,79 | 6 424 | 71,4% | +0,4% | **+0,1%/an** |

**Lecture** : un long permanent sur BTC ou ETH a payé, en moyenne, l'équivalent de **12 à 14% de son capital par an** rien qu'en funding sur 2020-2026 — cohérent avec le biais structurellement haussier de ces deux marchés sur la période (le long est la position "en excès de demande" la majorité du temps, 85-86% des événements). BNB et SOL sont quasi neutres sur la période (funding tantôt positif tantôt négatif, qui se compense).

## Rapprochement avec les résultats de backtest déjà connus (ordre de grandeur du biais)

Pour traduire ce taux annualisé en coût par trade, on a besoin d'une durée de détention moyenne. Le nombre de trades du projet ne l'indique pas directement mais permet une approximation (durée moyenne ≈ durée totale du backtest / nombre de trades) :

| Source | TF | Trades moyens (4 actifs) | Durée moyenne approx. de détention |
|---|---|---|---|
| `phase2_v5_FIXED_results.csv` (filtre de maturité strict, Phase 2 v4) | H4 | 1 318 | ~1,8 jour |
| `phase2_v5_FIXED_results.csv` | D1 | 29,5 | ~80 jours |
| `phase2_CORRECTED_results.csv` (version intermédiaire, filtre moins strict) | H4 | 799 | ~3,0 jours |
| `phase2_CORRECTED_results.csv` | D1 | 142,25 | ~17 jours |

(Période totale du backtest : 2020-01-01 → 2026-07-01 = 2 373 jours.) Les deux sources donnent des ordres de grandeur cohérents en H4 (~2-3 jours) mais divergent en D1 (17 à 80 jours) selon la sévérité du filtre de maturité utilisé à l'époque — logique : moins de trades filtrés = trades individuels plus longs en moyenne. On retient l'intervalle complet plutôt qu'un chiffre unique.

**Coût de funding estimé par trade** (à partir du taux annualisé BTC/ETH ci-dessus, ramené au prorata de la durée de détention) :

| TF | Durée moyenne | Coût funding/trade — BTC | Coût funding/trade — ETH |
|---|---|---|---|
| H4 | ~2-3 jours | 0,06% à 0,10% | 0,07% à 0,12% |
| D1 | ~17-80 jours | 0,55% à 0,96% | 0,65% à 1,15% |

**Pourquoi c'est significatif** : `phase2_CORRECTED_results.csv` donne aussi le rendement moyen par trade (`avg_trade_%`) déjà obtenu par le moteur de risque. En le comparant au coût de funding estimé ci-dessus :
- **H4, profil FAIBLE** : rendement moyen par trade ≈ 0,05-0,065% (BTC/ETH). Le coût de funding estimé (0,06-0,12%) est **du même ordre de grandeur, voire supérieur** à l'edge brut par trade. Non modélisé, ce coût peut annuler ou inverser l'edge du profil le plus conservateur.
- **H4, profils AGRESSIF/TRÈS AGRESSIF** : rendement moyen par trade 0,25-0,49% — le funding y reste une ponction réelle (15-45% de l'edge par trade) mais ne renverse pas le signe.
- **D1, profil FAIBLE** : rendement moyen par trade ≈ 0,09-0,19% (BTC/ETH), très inférieur au coût de funding estimé (0,55-1,15%). **C'est le cas le plus préoccupant** : sur ce profil/TF, le funding non modélisé pourrait à lui seul faire basculer un résultat déclaré positif en résultat net négatif.
- **D1, profils plus agressifs** : rendement moyen par trade plus élevé (0,45-1,64%), du même ordre que le coût de funding estimé — l'effet reste significatif mais moins clairement destructeur.

Ce rapprochement reste une approximation (le taux de funding réellement subi pendant les fenêtres exactes d'ouverture de position n'est pas recalculé trade par trade — seule la moyenne longue période est utilisée), mais l'ordre de grandeur est sans ambiguïté : **le funding n'est pas un coût négligeable au regard de l'edge par trade mesuré jusqu'ici, en particulier sur les profils FAIBLE et sur D1.**

## Recommandation

1. **Le funding doit être intégré comme coût dans tout prochain cycle de backtest**, au même titre que les frais de transaction — ce n'est pas une nuance de second ordre : sur BTC/ETH, son ordre de grandeur (12-14%/an) est comparable, voire supérieur, à l'edge net de plusieurs profils/TF actuellement rapportés comme positifs.
2. **Implémentation recommandée** : puisque les CSV sources contiennent déjà `fundingRate`/`fundingTime` alignés sur les mêmes timestamps que l'OHLCV utilisé par le moteur de risque, le calcul exact (pas l'approximation ci-dessus) est direct — à chaque bougie horaire où une position est ouverte, appliquer le coût `position_notionnelle × fundingRate` aux horodatages de funding réels (dédupliqués comme dans `funding_rate_analysis.py`), plutôt que d'utiliser un taux moyen forfaitaire par trade.
3. **Priorité** : reprendre en priorité les profils **FAIBLE en D1** (où le funding non modélisé peut inverser le signe du résultat) et **FAIBLE en H4** (où il peut annuler l'edge), avant de considérer que les chiffres de `PHASE2_V4_IMPLEMENTATION_COMPLETE.md`/`PROXY_V2_TSI_CYCLE_STRUCTURE.md` reflètent un rendement net réaliste sur ces profils.
4. **BNB et SOL** peuvent être laissés au taux forfaitaire ou même ignorés en première approche : le funding y est quasi neutre sur toute la période disponible (-0,2%/an et +0,1%/an respectivement).
5. Cette correction devrait être appliquée **avant** la Phase 3 (paper trading) : un critère GO/NO-GO basé sur un backtest qui ignore un coût structurel de cet ordre de grandeur n'a pas la même valeur probante.

## Limites de cette analyse

- Position "buy & hold" permanente, pas la position réelle intermittente de la stratégie (entrées/sorties selon signal) — le funding réellement payé par la stratégie dépend du taux en vigueur pendant ses fenêtres de détention effectives, qui peuvent différer de la moyenne longue période utilisée ici.
- Durée moyenne de détention approximée par `durée totale du backtest / nombre de trades`, pas mesurée trade par trade (les CSV de résultats du projet ne contiennent pas de date d'entrée/sortie individuelle) — deux sources de trades (`_v5_FIXED` vs `_CORRECTED`) donnent des durées D1 assez différentes (17 vs 80 jours), d'où la fourchette large plutôt qu'un chiffre unique.
- Pas de compounding réinvesti dans le calcul du coût cumulé (approximation au premier ordre) — suffisant pour l'ordre de grandeur demandé, pas pour un chiffrage définitif du coût net sur un capital qui varie dans le temps.
