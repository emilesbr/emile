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

## Limites de cette analyse (SECTION HISTORIQUE — l'estimation ci-dessus reste l'ordre de grandeur d'origine, non effacée, mais désormais AFFINÉE par le calcul exact ci-dessous)

- Position "buy & hold" permanente, pas la position réelle intermittente de la stratégie (entrées/sorties selon signal) — le funding réellement payé par la stratégie dépend du taux en vigueur pendant ses fenêtres de détention effectives, qui peuvent différer de la moyenne longue période utilisée ici.
- Durée moyenne de détention approximée par `durée totale du backtest / nombre de trades`, pas mesurée trade par trade (les CSV de résultats du projet ne contiennent pas de date d'entrée/sortie individuelle) — deux sources de trades (`_v5_FIXED` vs `_CORRECTED`) donnent des durées D1 assez différentes (17 vs 80 jours), d'où la fourchette large plutôt qu'un chiffre unique.
- Pas de compounding réinvesti dans le calcul du coût cumulé (approximation au premier ordre) — suffisant pour l'ordre de grandeur demandé, pas pour un chiffrage définitif du coût net sur un capital qui varie dans le temps.

---

## Calcul EXACT par timestamp — item 5 du backlog (`PLAN.md`), traité ce cycle de travail

**Ce qui change par rapport à la section ci-dessus** : l'estimation annualisée forfaitaire est remplacée par un calcul événement-par-événement, appliqué à la trace RÉELLE de chaque trade individuel produite par le moteur de risque lui-même (pas une approximation de durée moyenne globale). Code : `code/position_engine.py` (trace optionnelle, `record_trace=True`, n'affecte AUCUN appelant existant — voir "Modification de `position_engine.py`" ci-dessous), `code/backtest_phase2_v7.py` (`run_v7(..., record_trace=True)`, passthrough additif), `code/funding_rate_exact.py` (le calcul lui-même), `code/test_funding_rate_exact.py` (4/4 tests, cas synthétiques à vérité terrain calculée à la main).

### Méthode

1. **Trace par trade** : `run_position_engine(..., record_trace=True)` enregistre, pour chaque trade (chaque tranche ouverte, y compris les tranches pyramidées), la bougie d'ouverture, le prix d'entrée, et pour CHAQUE bougie où le trade est déjà ouvert (pas sa propre bougie d'ouverture, cf. justification dans la docstring), un instantané `(indice_de_bougie, taille_restante_avant_traitement_de_cette_bougie)` — donc la taille AVANT qu'une éventuelle clôture partielle Validation/Confirmation de cette même bougie ne la réduise. Ce mécanisme capture nativement les sorties partielles : la taille exposée décroît exactement au bon instant.
2. **Identification des vrais événements de funding** : vérifié empiriquement que les bougies H4 dont l'heure UTC tombe sur 00:00/08:00/16:00 correspondent EXACTEMENT (mêmes comptes, 7120 pour BTC) aux événements de funding réels dédupliqués de la section ci-dessus — donc une simple jointure exacte sur le timestamp suffit (`funding_rate_exact.attach_funding_rate`), pas de tolérance/recalage nécessaire.
3. **Coût par trade** : pour chaque instantané `(i, taille)` du trade qui tombe sur un vrai événement de funding, facteur multiplicatif `(1 - taille × taux_réel_de_l'événement)`, combinés MULTIPLICATIVEMENT sur toute la durée du trade (pas une somme au premier ordre — cf. `funding_rate_exact.compute_funding_cost_per_trade`, exact et non approximatif : l'écart avec une somme serait de toute façon négligeable ici, mais le calcul exact ne coûte rien de plus).
4. **Agrégation portefeuille** : l'équity finale déjà calculée SANS funding par le moteur est multipliée par le produit de tous les multiplicateurs de funding par trade — exact (pas une approximation) car le sizing de ce moteur ne réinjecte jamais l'équity courante dans le calcul de taille des trades suivants (fraction fixe du capital ORIGINAL, comme les frais de transaction), donc le produit de facteurs multiplicatifs est commutatif/associatif quel que soit l'ordre chronologique réel. **Limite assumée** : seul le retour TOTAL est recalculé exactement ainsi — la courbe d'équity intermédiaire (donc `max_dd_%`) n'est PAS recalculée avec le funding interpolé chronologiquement dans la boucle du moteur (demanderait de faire tourner le funding DANS `run_position_engine` plutôt qu'en post-traitement de sa trace — hors scope de ce chantier, aucune campagne du projet ne rapporte un max_dd déjà net de funding).
5. **Convention de taille explicite** : le coût est calculé comme `taille_restante × taux`, où `taille_restante` est exprimée dans la MÊME unité que `remaining` dans `position_engine.py` (fraction du capital total allouée au trade à l'entrée) — PAS une valeur notionnelle remarquée au prix courant (qui croîtrait avec le prix, contrats fixes). Cohérent avec la convention déjà utilisée pour les frais de transaction dans ce même moteur (`fee * fee_frac`, sans reprix au marché). Écart mineur pour des rendements bornés sur la durée d'UN SEUL trade (H4, quelques jours), pas prétendu nul.

### Modification de `position_engine.py` (fichier partagé — traité avec précaution)

Un seul ajout, strictement additif : nouveau paramètre optionnel `record_trace=False` sur `run_position_engine`. Quand `False` (défaut, comportement de TOUS les appelants existants — `backtest_phase2.py`/`_v4.py`/`_v5.py`/`_v6.py`/`_v7.py` sans ce paramètre), le code de bookkeeping de trace ne s'exécute même pas : aucun changement de résultat numérique possible. Vérifié explicitement :
- **`code/test_position_engine.py` : 5/5 tests toujours au vert après la modification** (rejoué immédiatement après le changement).
- `backtest_phase2_v7.run_v7(...)` rejoué SANS `record_trace` (BTC, profil FAIBLE) : résultats identiques bit-à-bit à avant la modification.
- `backtest_phase2_v7.run_v7(..., record_trace=True)` rejoué EN PLUS : mêmes `n_trades`/`total_return_%` que sans trace (504 trades, +23,1%) — la trace est un sous-produit d'observation, elle ne modifie rien à la boucle de simulation elle-même.

`backtest_phase2_v7.run_v7` reçoit le même traitement : paramètre optionnel `record_trace=False` (passthrough vers le moteur), qui expose en plus `trace` et `dates` (timestamps H4) dans le dict retourné quand demandé — les appels existants (`main()`, sans ce paramètre) sont inchangés.

### Résultats — H4, moteur v7 causal (MTF gate D1, stop H4), 4 actifs × 4 profils

Retour TOTAL cumulé sur toute la période disponible (2020-2026, ~6,4 ans) — comparaison retour SANS funding (chiffre déjà rapporté partout ailleurs dans le projet) vs AVEC funding EXACT (ce calcul) vs l'ESTIMATION GROSSIÈRE annualisée (méthode de la section historique ci-dessus, mais recalculée ici avec la vraie durée moyenne de détention MESURÉE sur ce run précis, pas une approximation `durée_totale/n_trades`) :

| Actif | Profil | Trades | Taille moy. position (% capital) | Durée moy. détention | Retour SANS funding | Retour AVEC funding EXACT | Retour estimation GROSSIÈRE | Écart exact − grossier |
|---|---|---|---|---|---|---|---|---|
| BTC | FAIBLE | 504 | 14,8% | 1,01 j | +23,1% | **+21,2%** | +20,1% | +1,1 pt |
| BTC | MODERE | 504 | 24,5% | 1,01 j | +61,0% | **+56,1%** | +54,5% | +1,6 pt |
| BTC | AGRESSIF | 504 | 29,1% | 1,01 j | +115,8% | **+106,7%** | +105,5% | +1,2 pt |
| BTC | TRES_AGRESSIF | 504 | 32,1% | 1,01 j | +157,1% | **+143,7%** | +143,4% | +0,3 pt |
| ETH | FAIBLE | 417 | 10,8% | 1,88 j | +55,2% | **+50,8%** | +50,1% | +0,7 pt |
| ETH | MODERE | 417 | 19,4% | 1,88 j | +139,0% | **+124,5%** | +124,9% | −0,4 pt |
| ETH | AGRESSIF | 417 | 24,8% | 1,88 j | +249,4% | **+218,5%** | +223,0% | −4,5 pts |
| ETH | TRES_AGRESSIF | 417 | 30,3% | 1,88 j | +355,4% | **+295,7%** | +313,3% | −17,6 pts |
| BNB | FAIBLE | 544 | 12,7% | 0,99 j | +17,0% | **+16,7%** | +17,0% | −0,3 pt |
| BNB | TRES_AGRESSIF | 544 | 31,5% | 0,99 j | +57,3% | **+54,4%** | +57,5% | −3,1 pts |
| SOL | FAIBLE | 361 | 7,4% | 1,28 j | +24,5% | **+23,0%** | +24,5% | −1,5 pt |
| SOL | TRES_AGRESSIF | 361 | 26,8% | 1,28 j | +228,2% | **+208,2%** | +228,1% | −19,9 pts |

(Table complète 16 lignes — les 2 profils intermédiaires BNB/SOL omis ici pour la lisibilité — : `code/funding_rate_exact_vs_v7_results.csv`.)

### Conclusion — l'estimation grossière était-elle une bonne approximation ?

**Oui pour les profils FAIBLE/MODERE (les plus pertinents pour une mise en pratique prudente), non pour les profils agressifs.** Sur FAIBLE/MODERE, l'écart entre le calcul exact et l'estimation grossière annualisée reste petit (**−1,0 à +1,6 point** de retour cumulé sur 6,4 ans, sur des retours de 17% à 139%) — l'estimation grossière de la section historique n'était donc pas fausse en ordre de grandeur pour ces profils, malgré son approximation (taux annualisé constant, durée moyenne globale, pas de trace individuelle). Sur les profils **AGRESSIF/TRES_AGRESSIF**, l'écart devient significatif et **systématiquement dans le même sens (le calcul exact est MEILLEUR que l'estimation grossière, donc l'estimation grossière SOUS-estimait le retour net réel)** sur ETH/BNB/SOL (jusqu'à **−19,9 points** sur SOL TRES_AGRESSIF, **−17,6 points** sur ETH TRES_AGRESSIF) — cohérent avec le fait que ces profils utilisent des tailles de position bien plus grandes (jusqu'à 32% du capital par trade, en pyramidalisation) ET des retours cumulés bien plus élevés (jusqu'à +355%), deux facteurs qui amplifient la différence entre une combinaison MULTIPLICATIVE exacte (ce calcul) et une simple soustraction forfaitaire au premier ordre (l'estimation grossière) : sur un retour cumulé de +355%, l'écart entre "coût multiplié" et "coût soustrait" cesse d'être négligeable. BTC fait exception (écart petit et de même signe que FAIBLE/MODERE, +0,3 à +1,6 pt) sur tous les profils testés — à ne pas généraliser aux autres actifs sans vérifier.

**Constat le plus important, qui NUANCE l'alerte de la section historique** : le coût de funding exact, mesuré trade par trade, **n'efface ni n'inverse le signe** de l'edge H4/FAIBLE sur AUCUN des 4 actifs testés (BTC +21,2%, ETH +50,8%, BNB +16,7%, SOL +23,0%, tous restent nettement positifs) — l'estimation qualitative de la section historique ("le funding non modélisé peut annuler l'edge du profil H4/FAIBLE") était une lecture PESSIMISTE justifiée par la seule comparaison brute (taux annualisé vs rendement moyen par trade), qui ne tenait pas compte du fait que la taille RÉELLE de position en H4/FAIBLE (~10-15% du capital, pas 100% comme l'hypothèse "buy & hold" de la section historique) réduit mécaniquement le coût de funding réellement subi d'un facteur ~7-10× par rapport à une exposition pleine. Ceci **ne remet pas en cause la recommandation** d'intégrer le funding avant la Phase 3 — le coût reste réel et mesurable (jusqu'à plusieurs points de retour cumulé, jusqu'à ~13% du capital en coût cumulé sur ETH TRES_AGRESSIF) — mais infirme la lecture la plus alarmiste ("peut annuler l'edge du profil FAIBLE") pour le profil H4/FAIBLE spécifiquement, sur les 4 actifs testés ici.

**Non testé dans ce calcul, à ne pas perdre** : D1 (le moteur v7 exécute uniquement sur H4, D1 sert de référence/contexte MTF, pas de trading direct — voir `backtest_phase2_v7.py`) ; recalcul de `max_dd_%` avec le funding intégré chronologiquement dans la boucle du moteur (limite déclarée ci-dessus) ; les profils intermédiaires (MODERE/AGRESSIF) de BNB/SOL (dans le CSV complet, pas reproduits dans le tableau ci-dessus par souci de lisibilité, mais suivent la même tendance).
