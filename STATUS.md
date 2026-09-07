# STATUS — État actuel du projet (point d'entrée unique)

> Ce document est le point d'entrée pour quiconque reprend ce projet. Il ne remplace pas `PLAN.md` (qui reste le plan directeur détaillé, phase par phase) mais donne, en un seul endroit, la liste à jour de « quel document lire pour quel sujet » et « quels documents ignorer ». En cas de doute entre ce fichier et `PLAN.md`, `PLAN.md` fait foi sur le fond (roadmap, phases) — ce fichier fait foi sur le classement documentaire.

## Résumé exécutif

Le projet formalise, à partir du manuel officiel PRO Indicators (Philippe Roux) et de 17 sources vidéo « Trading Lessons », une stratégie de trading crypto multi-timeframe testée par backtest (BTC/ETH/BNB/SOL, données Binance Futures réelles 2020-2026), avant tout engagement de capital réel. La Phase 0 (extraction des règles) et la Phase 1 (backtest multi-timeframe sur un proxy de signal générique) sont substantiellement achevées : **H4 et D1 sont viables (GO), H1 et M15 ne le sont pas (NO-GO, détruits par les frais de transaction)**. La Phase 2 a traversé plusieurs itérations (v4 : money management complet ; v5 : signal reconstruit du corpus (TSI+cycle+structure) ; v6 : classification de régime + interdiction de trader en Excès ; v7 : validation croisée multi-timeframe réelle H4/D1) — voir `MTF_CROSS_VALIDATION_H4_D1.md` pour le résultat le plus solide et le plus uniformément cohérent à ce jour.

**Limite fondamentale, vraie depuis le début** : tout le travail repose sur un **signal proxy**, jamais validé contre le vrai indicateur PRO Framework/Momentum (dont la formule n'est pas divulguée par l'éditeur). Aucun résultat chiffré ci-dessus ne doit être lu comme une validation de la méthode réelle de Philippe Roux — seulement de ce proxy.

**Réserve P0 non résolue, plus prioritaire que tout le reste** : la composante « cycle » (`code/proxy_v2.py::compute_cycle_phase`) appelle `scipy.signal.hilbert()` sur la série de prix entière d'un coup — calcul non causal, jamais quantifié sur données réelles. Le **sens** de la correction du bug de signe original tient (revalidé hors-échantillon sur XRP, `OOS_VALIDATION_CYCLE_SIGN.md`), mais l'**ampleur** de toute performance rapportée depuis v5 (v5/v6/v7, MTF, funding rate, OOS XRP) porte une inflation non quantifiée. Détail complet, mesure et plan de correction : `COUVERTURE_ENSEIGNEMENTS.md` section ⚠️, et `PLAN.md` (backlog priorisé, item P0).

**Pour la liste exhaustive et à jour des lacunes ouvertes (corpus↔code) et leur priorisation : ne pas se fier au paragraphe ci-dessus au-delà du P0, consulter `COUVERTURE_ENSEIGNEMENTS.md` et le backlog priorisé de `PLAN.md`** — ce résumé exécutif n'est pas remis à jour à chaque changement, ces deux documents le sont.

## Classement des documents

### Référence actuelle (à lire — reflète l'état le plus à jour du travail)

| Document | Sujet |
|---|---|
| `PLAN.md` | Plan directeur, feuille de route par phase, statut le plus à jour |
| `STATUS.md` (ce document) | Point d'entrée unique, classement documentaire |
| `RULES_EXTRACTION.md` | Règles extraites du manuel PDF officiel (Phase 0) |
| `TRADING_LESSONS_INDEX.md` | Index des 17 sources Trading Lessons, statut de la question multi-timeframe (résolue) |
| `TRADING_LESSONS_*.md` (17 fichiers listés dans l'index) | Sources primaires (transcriptions/résumés) référencées par l'index — consulter via `TRADING_LESSONS_INDEX.md` pour le contexte |
| `BACKTEST_RESULTS_MTF.md` | Résultats bruts du backtest multi-timeframe Phase 1 (proxy générique), base factuelle toujours valide pour son périmètre (moteur de risque simple, pré-Phase 2) |
| `WALKFORWARD_ANALYSIS.md` | Analyse walk-forward année par année du backtest Phase 1, toujours valide |
| `PHASE1_CLOSEOUT.md` | État réel de la Phase 1 (cascade multi-timeframe réelle, conclusion GO/NO-GO par timeframe) |
| `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` | Moteur de risque Phase 2 — implémentation actuelle et complète (remplace toutes les itérations précédentes) |
| `PROXY_V2_TSI_CYCLE_STRUCTURE.md` | Signal Phase 2 reconstruit à partir du corpus (TSI + cycle + structure), résultat le plus solide à ce jour |
| `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md` | Audit qualité, contrôle aléatoire, bug de signe trouvé et corrigé, liste des lacunes encore ouvertes |
| `FUNDING_RATE_ANALYSIS.md` | Analyse du coût de funding Binance Futures, jamais modélisé jusqu'ici (nouveau) |
| `CASCADE3_H1_EXECUTION_TEST.md` | Test cascade Daily→H4→H1, refait le 2026-09-07 avec le moteur de risque actuel (`code/position_engine.py`) ; conclusion NO-GO reconduite |
| `REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md` | Classification de régime (Range/Tendance/Excès), interdiction de trader en Excès (v6) |
| `MTF_CROSS_VALIDATION_H4_D1.md` | Validation croisée multi-timeframe réelle H4/D1 (v7) — résultat le plus solide et uniforme à ce jour |
| `OOS_VALIDATION_CYCLE_SIGN.md` | Validation hors-échantillon indépendante (XRP) du signe de la composante cycle — sens confirmé, ampleur non résolue (cf. réserve P0 ci-dessus) |
| `COUVERTURE_ENSEIGNEMENTS.md` | Table de croisement exhaustive corpus↔code (✅ implémenté / ❌ manquant), y compris la réserve P0 — référence pour "tout est-il pris en compte ?" |
| `code/position_engine.py`, `code/test_position_engine.py` | Moteur de gestion de position factorisé (fin de la duplication `backtest_phase2.py`/`_v4.py`/`_v5.py`) + tests unitaires sur cas synthétiques |
| `code/proxy_v2.py`, `code/test_proxy_v2.py` | Signal proxy (TSI+cycle+structure) + premiers tests de régression (nouveau) — a mis en évidence la réserve P0 en les écrivant |
| `code/regime_classifier.py`, `code/backtest_phase2_v6.py`, `code/backtest_phase2_v7.py` | Moteurs v6 (régime) et v7 (validation croisée MTF) |

### Historique / supersédé (pour archive — ne pas utiliser comme source de vérité)

| Document | Pourquoi supersédé | Remplacé par |
|---|---|---|
| `PHASE2_MONEYMANAGEMENT.md` | Première itération du money management Phase 2 (breakeven remonté trop tôt, à la Validation au lieu de la Confirmation — bug corrigé ensuite) ; ne couvrait que H4/D1 | `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` |
| `PHASE2_FULL_MATRIX.md` | Complète `PHASE2_MONEYMANAGEMENT.md` (mêmes limites : bug de breakeven prématuré, engendrant le résultat "H1 s'effondre" qui reflète surtout ce bug) | `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` |
| `PHASE2_CORRECTION_BREAKEVEN.md` | Documente une correction intermédiaire (breakeven différé à la Confirmation) désormais pleinement intégrée et documentée dans la version finale du moteur | `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` |
| `PHASE2_CORRECTION_CLOSES.md` | Documente une correction intermédiaire (validation sur clôtures, pas sur mèches) désormais pleinement intégrée dans la version finale du moteur | `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` |
| `PHASE2_V3_ATTEMPT_REGRESSION.md` | Tentative combinée (Règle de Trois + amplitude réelle + Extreme Channel) rejetée en l'état — régression sur H4 due à un bug de calibration (fenêtres en nombre de bougies, pas en durée réelle), corrigé depuis | `PHASE2_V4_IMPLEMENTATION_COMPLETE.md` (le document lui-même l'indique : « remplace le cadre accepté/rejeté utilisé précédemment ») |
| ~~`CASCADE3_H1_EXECUTION_TEST.md` (version pré-correction)~~ | Résultat négatif/inconclusif calculé avec un moteur de risque antérieur à la correction « clôtures vs mèches » | `CASCADE3_H1_EXECUTION_TEST.md` a été refait le 2026-09-07 avec le moteur actuel (position_engine.py) — conclusion reconduite (voir référence actuelle ci-dessus) |

Les fichiers `.csv` du dépôt (résultats bruts de backtest) ne sont pas reclassés ici : ils restent les données sources citées par les documents ci-dessus, à jour ou historiques selon le document qui les référence.
