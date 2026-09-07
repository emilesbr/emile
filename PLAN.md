# Plan directeur — Système de trading formalisé à partir des outils PRO Indicators

**Cadre du projet** : usage strictement personnel des indicateurs de Philippe Roux (PRO Indicators), sur la base d'un abonnement souscrit et d'un accord vérifié avec l'éditeur sur les CGU. Objectif : formaliser une stratégie de trading multi-timeframe testable, avec une gestion du risque explicite, avant toute mise en œuvre avec du capital réel.

**Statut du cadrage**
- Accord obtenu avec Philippe Roux + CGU vérifiées (usage personnel) : ✅ fait
- Pas d'automatisation de l'exécution des trades en phase initiale : ✅ acté
- Objectif "revenu journalier" reformulé : espérance de gain positive sur une fenêtre plus longue, risque borné et mesuré, validée statistiquement avant tout engagement de capital réel.

---

## État réel au [dernier cycle de travail] — résumé exécutif

Ce plan a beaucoup évolué depuis sa version initiale. **Documents de référence à jour** (ne pas se fier aux anciens documents `PHASE2_MONEYMANAGEMENT.md`/`PHASE2_FULL_MATRIX.md`/`PHASE2_V3_ATTEMPT_REGRESSION.md`, tous supersédés) :

| Sujet | Document de référence actuel |
|---|---|
| Règles extraites du manuel PDF officiel | `RULES_EXTRACTION.md` |
| Corpus Trading Lessons (17 sources vidéo) | `TRADING_LESSONS_INDEX.md` (index + statut de la question multi-timeframe, résolue) |
| Backtest Phase 1 (multi-timeframe, proxy générique) | `PHASE1_CLOSEOUT.md` |
| Moteur de risque Phase 2 — implémentation actuelle | `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` |
| Signal Phase 2 — proxy reconstruit (TSI + cycle + structure) | `PROXY_V2_TSI_CYCLE_STRUCTURE.md` + `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md` (bug de signe trouvé et corrigé via contrôle aléatoire) |
| Lacunes de qualité identifiées et statut | `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md` |

**Résultat le plus solide à ce jour** : signal proxy v2 (TSI+cycle+structure, après correction du bug de signe) sur H4, bat nettement un contrôle aléatoire à fréquence égale, stable sur 7 années de walk-forward (aucune année catastrophique). **Réserve non résolue** : le sens de la correction du signe a été validé sur le même échantillon que celui utilisé pour le résultat rapporté — biais rétrospectif possible, à revalider sur donnée indépendante.

**Toujours vrai depuis le début** : le signal reste un proxy, jamais validé contre le vrai PRO Framework/Momentum (accès TradingView requis). C'est la limite fondamentale qui borne tout le reste.

---

## Phase 0 — Extraction des règles déterministes
**Statut : faite.** Manuel PDF lu intégralement + 17 sources Trading Lessons traitées. Voir `RULES_EXTRACTION.md` et `TRADING_LESSONS_INDEX.md`. Élément non résolu : le signal réel des indicateurs (PRO Framework/Momentum) n'a jamais été exporté/observé directement — tout ce qui suit reste un proxy.

## Phase 1 — Backtest multi-timeframe
**Statut : substantiellement faite.** Voir `PHASE1_CLOSEOUT.md`, `WALKFORWARD_ANALYSIS.md`. Conclusion : H4/D1 = GO, H1/M15 = NO-GO (avec le proxy générique d'origine). Items ouverts : XRP absent (pas de données), cascade 3-niveaux testée pour sauver le H1 → échec documenté (`CASCADE3_H1_EXECUTION_TEST.md`, **mais calculé avec un moteur de risque périmé — à refaire avec le moteur actuel avant de considérer cette conclusion comme définitive**).

## Phase 2 — Gestion du risque + reconstruction du signal
**Statut : cycle de corrections et de reconstruction achevé, avec réserves documentées.**
- Money management dérivé du corpus (breakeven différé, clôtures vs mèches, amplitude réelle calibrée en durée, Règle de Trois, Extreme Channel, maturité par bornes swing, pyramidalisation multi-tranches) : `PHASE2_V4_IMPLEMENTATION_COMPLETE.md`
- Signal reconstruit à partir du corpus (TSI+cycle+structure, remplaçant l'EMA générique) : `PROXY_V2_TSI_CYCLE_STRUCTURE.md`
- Audit qualité + contrôle aléatoire + bug de signe trouvé et corrigé : `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md`

**Lacunes ouvertes, déléguées à des agents spécialisés (voir ci-dessous) :**
1. Aucun test unitaire ; logique de position dupliquée dans 3 fichiers (`backtest_phase2.py`/`_v4.py`/`_v5.py`)
2. Revalidation du signe du cycle sur donnée indépendante (pas encore faite)
3. `CASCADE3_H1_EXECUTION_TEST.md` à refaire avec le moteur actuel
4. Funding rates (Binance Futures) disponibles mais jamais intégrées au coût de la stratégie
5. Documentation éclatée (~25 fichiers) sans état unique consolidé
6. Diversification 1%+1% (deux patterns indépendants) : jamais testée

## Phase 3 — Paper trading (inchangée)
Durée minimale 4-8 semaines, signaux temps réel sur démo. Critère GO/NO-GO : performance paper dans l'intervalle de confiance du backtest.

## Phase 4 — Pilote capital réel, exécution 100 % manuelle (inchangée)
Capital 10-15 % de la cible, wallet connecté sans transaction automatique, garde-fous structurels ajoutés suite au corpus (checklist pré-trade, latence de 10s, session max 60-90 min — cf. `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` et `TRADING_LESSONS_NEUROBIOLOGIE.md`).

## Phase 5 — Automatisation de l'exécution (non engagée)
Inchangée — discussion différée après Phase 4.

---

## Prochaine action immédiate
Trois lots délégués en parallèle (voir rapports d'agents) : (A) qualité du code/tests + refonte cascade3, (B) validation hors-échantillon du signe du cycle, (C) consolidation documentaire + funding rates. Une fois ces lots revenus, décision sur la suite (Phase 3 ou poursuite Phase 2).
