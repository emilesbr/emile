# Plan directeur — Système de trading formalisé à partir des outils PRO Indicators

**Cadre du projet** : usage strictement personnel des indicateurs de Philippe Roux (PRO Indicators), sur la base d'un abonnement souscrit et d'un accord vérifié avec l'éditeur sur les CGU. Objectif : formaliser une stratégie de trading multi-timeframe testable, avec une gestion du risque explicite, avant toute mise en œuvre avec du capital réel.

**Statut du cadrage**
- Accord obtenu avec Philippe Roux + CGU vérifiées (usage personnel) : ✅ fait
- Pas d'automatisation de l'exécution des trades en phase initiale : ✅ acté
- Objectif "revenu journalier" reformulé : espérance de gain positive sur une fenêtre plus longue, risque borné et mesuré, validée statistiquement avant tout engagement de capital réel.

---

## Document maître de couverture des enseignements

**`COUVERTURE_ENSEIGNEMENTS.md` est désormais le document de référence unique pour savoir ce qui, du corpus (manuel PDF + 17 sources Trading Lessons), est implémenté ou non.** Avant de considérer une phase "faite", vérifier cette table plutôt que ce résumé narratif. Rappel du principe qui gouverne cette table depuis sa formulation explicite par l'utilisateur : **la performance du proxy ne sert jamais à décider si un élément du corpus doit être implémenté ou non** — le proxy n'est pas le vrai signal, donc une contre-performance en backtest n'est jamais un motif de rejet d'un élément documenté de la propriété intellectuelle de Philippe. Un élément documenté et non encore implémenté reste une lacune à combler, jamais une décision de conception.

---

## État réel au dernier cycle de travail — résumé exécutif

Ce plan a beaucoup évolué depuis sa version initiale. **Documents de référence à jour** (ne pas se fier aux anciens documents `PHASE2_MONEYMANAGEMENT.md`/`PHASE2_FULL_MATRIX.md`/`PHASE2_V3_ATTEMPT_REGRESSION.md`, tous supersédés) :

| Sujet | Document de référence actuel |
|---|---|
| Règles extraites du manuel PDF officiel | `RULES_EXTRACTION.md` |
| Corpus Trading Lessons (17 sources vidéo) | `TRADING_LESSONS_INDEX.md` (index + statut de la question multi-timeframe, résolue) |
| Couverture complète du corpus (✅/❌ exhaustif) | `COUVERTURE_ENSEIGNEMENTS.md` |
| Backtest Phase 1 (multi-timeframe, proxy générique) | `PHASE1_CLOSEOUT.md` |
| Moteur de risque Phase 2 — version de base | `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` |
| Signal Phase 2 — proxy reconstruit (TSI + cycle + structure) | `PROXY_V2_TSI_CYCLE_STRUCTURE.md` + `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md` (bug de signe trouvé, corrigé, revalidé hors-échantillon) |
| Classification de régime (Range/Tendance/Excès) | `REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md` |
| Validation croisée multi-timeframe réelle (H4/D1) | `MTF_CROSS_VALIDATION_H4_D1.md` |
| Coût funding rate (ordre de grandeur) | `FUNDING_RATE_ANALYSIS.md` |
| Validation hors-échantillon indépendante (XRP) du signe du cycle | `OOS_VALIDATION_CYCLE_SIGN.md` |
| Lacunes de qualité identifiées et statut | `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md` |
| État du code (架構, tests) | `code/` — moteur de position factorisé et testé (`position_engine.py` + `test_position_engine.py`, 5/5 tests passent) |
| Point d'entrée unique / état du projet | `STATUS.md` |

**Chaîne des moteurs de backtest** (chacun ajoute une brique sur le précédent, tous dans `code/`) :
`backtest_phase2.py` (base, EMA confluence, table range) → `_v4.py` (+ Règle de Trois, amplitude en durée, maturité swing, pyramidalisation) → `_v5.py` (signal remplacé par proxy TSI+cycle+structure) → `_v6.py` (+ classification de régime, interdiction EXCES, pyramidalisation gated) → `_v7.py` (+ validation croisée réelle H4 exécution / D1 référence, sans lookahead).

**Résultat le plus solide et le plus uniformément cohérent à ce jour** : v7 (validation croisée H4/D1) — sur les 4 actifs testés et sans exception, ~3× moins de trades, win rate systématiquement +5 à +13 points, drawdown systématiquement réduit. Confirme empiriquement ce que 7 sources indépendantes du corpus affirmaient sur l'importance de la validation multi-timeframe. Détail : `MTF_CROSS_VALIDATION_H4_D1.md`.

**Réserve non résolue depuis le début** : le signal reste un proxy (TSI+cycle+structure), jamais validé contre le vrai PRO Framework/Momentum (accès TradingView requis — hors de portée technique actuelle). C'est la limite fondamentale qui borne tout le reste. Le bug de signe du cycle a été revalidé hors-échantillon (XRP, `OOS_VALIDATION_CYCLE_SIGN.md`) pour réduire (pas éliminer) le risque de biais rétrospectif.

**Ce qui n'est toujours pas fait, malgré tout ce travail** — voir `COUVERTURE_ENSEIGNEMENTS.md` pour la liste exhaustive. Points les plus significatifs : table "trade de tendance" à 5 étapes jamais testée (seule la table range l'a été) ; Fibonacci retracement jamais utilisé comme critère d'entrée ; règle "UT+2" exacte (2 niveaux au-dessus, pas le niveau immédiat) non implémentée ; le stop "Extreme Channel" reste calculé sur le même timeframe que celui tradé (incohérence avec le nom, même après la correction MTF du signal en v7) ; capital par palier jamais pris en compte ; plusieurs patterns/outils du manuel (Wall Street, Andrews Pitchfork, canal manuel Supports→Apex→Tangente, Cluster Technique, mécanisme +Reverse) jamais construits.

---

## Phase 0 — Extraction des règles déterministes
**Statut : faite.** Manuel PDF lu intégralement + 17 sources Trading Lessons traitées. Voir `RULES_EXTRACTION.md` et `TRADING_LESSONS_INDEX.md`. Élément non résolu : le signal réel des indicateurs (PRO Framework/Momentum) n'a jamais été exporté/observé directement — tout ce qui suit reste un proxy.

## Phase 1 — Backtest multi-timeframe
**Statut : substantiellement faite.** Voir `PHASE1_CLOSEOUT.md`, `WALKFORWARD_ANALYSIS.md`. Conclusion : H4/D1 = GO, H1/M15 = NO-GO (avec le proxy générique d'origine). `backtest_cascade3.py` rejoué avec le moteur actuel par l'agent délégué A : conclusion H1 confirmée (toujours NO-GO), chiffres améliorés (`cascade3_h1execution_results.csv`).

## Phase 2 — Gestion du risque + reconstruction du signal + contexte de marché
**Statut : cycle de reconstruction achevé (v4→v7), avec réserves documentées explicitement dans `COUVERTURE_ENSEIGNEMENTS.md`.**
- Money management dérivé du corpus (breakeven différé, clôtures vs mèches, amplitude réelle calibrée en durée, Règle de Trois, maturité par bornes swing, pyramidalisation multi-tranches) : `PHASE2_V4_IMPLEMENTATION_COMPLETE.md`
- Signal reconstruit à partir du corpus (TSI+cycle+structure, remplaçant l'EMA générique) : `PROXY_V2_TSI_CYCLE_STRUCTURE.md`
- Audit qualité + contrôle aléatoire + bug de signe trouvé, corrigé, revalidé hors-échantillon : `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md`, `OOS_VALIDATION_CYCLE_SIGN.md`
- Classification de régime de marché (Range/Tendance/Excès), interdiction de trader en Excès, pyramidalisation restreinte à la Tendance : `REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md`
- Validation croisée multi-timeframe réelle (H4 exécution validé par D1 référence, sans lookahead) : `MTF_CROSS_VALIDATION_H4_D1.md`
- Coût funding rate quantifié à l'ordre de grandeur annuel : `FUNDING_RATE_ANALYSIS.md` — constat : peut effacer/inverser l'edge en H4/FAIBLE et D1/FAIBLE
- Code : logique de position dédupliquée et testée (`code/position_engine.py`, 5 tests unitaires passent), plus de duplication entre `backtest_phase2.py`/`_v4.py`/`_v5.py`/`_v6.py`/`_v7.py`

**Lacunes ouvertes (liste complète et exhaustive : `COUVERTURE_ENSEIGNEMENTS.md`), les plus significatives :**
1. Table "trade de tendance" à 5 étapes jamais implémentée (seule la table range l'a été)
2. Fibonacci retracement jamais utilisé comme critère d'entrée
3. Règle "UT+2" exacte (2 niveaux au-dessus) non implémentée — v7 ne valide qu'avec le niveau immédiatement supérieur
4. Stop "Extreme Channel" toujours calculé sur le même timeframe que celui tradé, malgré son nom — incohérence résiduelle même après la correction MTF du signal
5. Capital par palier (<10k€/10-100k€/>100k€) jamais pris en compte dans le sizing
6. Funding rate : ordre de grandeur quantifié, pas encore modélisé par timestamp exact
7. Patterns/outils jamais construits : règle "Wall Street" (élargissement = abstention), Fourchette d'Andrews, canal manuel (Supports→Apex→Tangente), Cluster Technique (second pattern), diversification 1%+1%, mécanisme "+Reverse" (Très Agressif)

## Phase 3 — Paper trading (inchangée)
Durée minimale 4-8 semaines, signaux temps réel sur démo. Critère GO/NO-GO : performance paper dans l'intervalle de confiance du backtest. **Pas encore engagée** — les lacunes de Phase 2 ci-dessus restent à trancher (combler avant Phase 3, ou accepter et documenter le périmètre non couvert) avant de basculer.

## Phase 4 — Pilote capital réel, exécution 100 % manuelle (inchangée)
Capital 10-15 % de la cible, wallet connecté sans transaction automatique, garde-fous structurels ajoutés suite au corpus (checklist pré-trade, latence de 10s, session max 60-90 min — cf. `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` et `TRADING_LESSONS_NEUROBIOLOGIE.md`).

## Phase 5 — Automatisation de l'exécution (non engagée)
Inchangée — discussion différée après Phase 4.

---

## Prochaine action immédiate
Les trois lots délégués (A : qualité du code/tests + refonte cascade3 ; B : validation hors-échantillon du signe du cycle ; C : consolidation documentaire + funding rates) sont revenus et intégrés ci-dessus. Décision à prendre : combler en priorité les lacunes à plus fort impact documenté (table trade de tendance, Fibonacci, vrai stop cross-timeframe, règle UT+2 exacte) avant de considérer la Phase 2 comme suffisamment fidèle au corpus pour passer en Phase 3, conformément au principe : un élément documenté de la propriété intellectuelle de Philippe reste une lacune à combler tant qu'il n'est pas implémenté, indépendamment de la performance du proxy.
