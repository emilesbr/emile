# Plan directeur — Système de trading formalisé à partir des outils PRO Indicators

**Cadre du projet** : usage strictement personnel des indicateurs de Philippe Roux (PRO Indicators), sur la base d'un abonnement souscrit et d'un accord vérifié avec l'éditeur sur les CGU. Objectif : formaliser une stratégie de trading multi-timeframe testable, avec une gestion du risque explicite, avant toute mise en œuvre avec du capital réel.

**Statut du cadrage**
- Accord obtenu avec Philippe Roux + CGU vérifiées (usage personnel) : ✅ fait
- Pas d'automatisation de l'exécution des trades en phase initiale : ✅ acté
- Objectif "revenu journalier" reformulé : espérance de gain positive sur une fenêtre plus longue, risque borné et mesuré, validée statistiquement avant tout engagement de capital réel.

---

## Document maître de couverture des enseignements

**`COUVERTURE_ENSEIGNEMENTS.md` est désormais le document de référence unique pour savoir ce qui, du corpus (manuel PDF + 17 sources Trading Lessons), est implémenté ou non.** Avant de considérer une phase "faite", vérifier cette table plutôt que ce résumé narratif. Rappel du principe qui gouverne cette table depuis sa formulation explicite par l'utilisateur : **la performance du proxy ne sert jamais à décider si un élément du corpus doit être implémenté ou non** — le proxy n'est pas le vrai signal, donc une contre-performance en backtest n'est jamais un motif de rejet d'un élément documenté de la propriété intellectuelle de Philippe. Un élément documenté et non encore implémenté reste une lacune à combler, jamais une décision de conception.

**Un seul tracker actif** (inspiré de la discipline documentaire du projet `ideeri-v2`, `docs/README.md` : *"pas de deuxième tracker"*) : `PLAN.md` (ce document) est la feuille de route/backlog vivant — mis à jour au fil de l'eau, jamais un deuxième endroit ne doit exister pour "ce qui reste à faire". `STATUS.md` est le classement documentaire (quel fichier lire pour quel sujet), pas une deuxième liste d'items ouverts. `COUVERTURE_ENSEIGNEMENTS.md` est la table de croisement détaillée corpus↔code (l'équivalent d'un "tableau maître" chez ideeri-v2) — elle alimente ce plan, elle ne le duplique pas. En cas de divergence entre ces documents, **ce fichier fait foi sur ce qui reste à faire**.

---

## Méthode de travail (inspirée de la discipline `ideeri-v2`)

Adopté après une observation directe de l'utilisateur : à chaque fois qu'il demande "un directeur ingénieur senior serait-il satisfait ?", une découverte réelle survient (bug de signe trouvé par contrôle aléatoire ; réserve batch/non-causale déjà documentée une fois mais jamais remontée jusqu'ici). Le projet `ideeri-v2` (même utilisateur) documente **exactement le même phénomène** dans son `CLAUDE.md` §16.2 point 7 — deux bugs de production trouvés uniquement parce que l'utilisateur a redemandé "que répondrait un ingénieur senior ?" une 2e fois. Plutôt que de laisser ce pattern se répéter en silence, on l'écrit une fois pour toutes et on en tire une méthode, comme `ideeri-v2` l'a fait.

### Prioriser par risque, pas par ordre de découverte

```
risque = probabilité que ça cache un problème × impact si silencieux × coût de la découverte tardive
```

C'est la formule utilisée dans `ideeri-v2/docs/archive/audit-senior-code-complet.md` §0. Appliquée ici : la composante "cycle" de `proxy_v2.py` obtient le score le plus élevé sur les 3 axes (probabilité : déjà 2 anomalies distinctes trouvées sur cette seule fonction ; impact : elle contribue à l'entrée de tous les moteurs v5/v6/v7 ; coût de découverte tardive : le pire moment pour la découvrir serait en paper trading ou pire, en capital réel) — d'où son classement P0 dans le backlog ci-dessous, avant tout nouvel élément du corpus non encore implémenté.

### Pattern récurrent — risque concentré, pas dispersé (3 occurrences, même fonction)

Comme `ideeri-v2` le documente pour son propre pattern récurrent ("contexte de validité jamais revérifié", 7 occurrences trouvées) : quand la même fonction produit plusieurs anomalies distinctes, ce n'est plus 3 hasards indépendants, c'est un signal que le risque s'y concentre.

| # | Occurrence | Root cause commune | Statut |
|---|---|---|---|
| 1 | `sin(phase)` anti-corrélé au rendement du lendemain (BTC/ETH/SOL), trouvé par contrôle aléatoire | Convention de signe d'une sortie de transformée de Hilbert jamais vérifiée empiriquement avant usage | Corrigé (`-sin(phase)`), revalidé hors-échantillon (XRP, `OOS_VALIDATION_CYCLE_SIGN.md`) |
| 2 | `hilbert()` appelé sur la série entière d'un coup (non causal) — jamais quantifié sur données réelles | Fonction batch/FFT utilisée telle quelle sans vérifier l'hypothèse de causalité requise pour un usage en backtest | **Traité ce cycle — MITIGÉ, pas résolu au sens plein** : `compute_cycle_phase_causal` (fenêtre glissante) en production, v5/v6/v7 + OOS XRP rejoués. Edge **global** H4 confirmé en direction (48/48 configs v7) mais ampleur surestimée ~4× ; edge du **cycle isolé** non confirmé sur les 5 actifs testés (corrélation causale non significative partout, y compris XRP OOS). Détail : `COUVERTURE_ENSEIGNEMENTS.md` ⚠️→◐ |
| 3 | `cycle_ascending` (dérivée du sinewave) anti-corrélée au rendement futur sur sinusoïde synthétique pure — contredit la validation OOS réelle (positive) | Interprétation d'une grandeur dérivée non vérifiée sur cas synthétique contrôlé avant usage en production | Ouvert, non tranché — `code/test_proxy_v2.py` (docstring) |

**Conséquence pratique** : toute future modification de `proxy_v2.py::compute_cycle_phase`/`add_proxy_v2_score` mérite le "mode ingénieur senior" ci-dessous par défaut, pas seulement quand on y pense.

### Mode ingénieur senior — quand ralentir sans qu'on ait à le redemander

Adapté de `ideeri-v2/CLAUDE.md` §16. Déclencheurs, sur ce projet :
- Toute modification de la composante cycle de `proxy_v2.py` (risque concentré, tableau ci-dessus).
- Tout passage de phase (2→3, 3→4, 4→5) — en pratique irréversible une fois du capital réel engagé.
- Toute décision qui fige un chiffre de performance comme "validé" avant la fin de la Phase 3.

Pratiques concrètes :
1. **Vérifier empiriquement, pas seulement relire le code** — test synthétique à vérité terrain connue plutôt qu'une déduction depuis la formule.
2. **Chercher les implications ailleurs avant de clore** — un fix/une réserve sur `proxy_v2.py` affecte tous les moteurs qui l'utilisent (v5/v6/v7) et tous les documents qui en rapportent la performance (MTF, funding rate, OOS) ; vérifier la liste complète, pas seulement le fichier qu'on vient de modifier.
3. **Documenter en continu**, pas en résumé final une fois le chantier déclaré clos.
4. **Distinguer "mitigé" de "résolu"** — appliqué concrètement au traitement du P0 (occurrence #2 ci-dessus) : le calcul causal a été implémenté et mesuré, l'ampleur du biais **est maintenant quantifiée** (edge H4 global surestimé ~4× en batch), mais ça ne fait pas du sujet un "résolu" au sens plein — la mesure révèle un fait plus sérieux qu'une simple correction de magnitude : le composant cycle **isolé** ne montre aucune corrélation causale significative sur les 5 actifs réels testés. "Mitigé" s'applique à la performance globale (son sens tient) ; le composant cycle lui-même reste une question ouverte — le test d'ablation fait depuis (cf. `COUVERTURE_ENSEIGNEMENTS.md`) ne tranche pas non plus : 4 actifs en désaccord de direction (ETH s'améliore sans le cycle, SOL se dégrade), donc ni "à retirer" ni "confirmé neutre" — un résultat non concluant reste un résultat honnête, pas un échec de méthode.
5. **"Tests unitaires verts" ne prouve ni que l'edge survivra à un calcul causal, ni qu'il survivra en paper trading** — un chiffre n'est définitif qu'après Phase 3, jamais avant.

**Garde-fou mécanique — angle mort assumé, pas encore traité.** `ideeri-v2` (`CLAUDE.md` §16.4) constate qu'un texte seul ("pas d'automatisation de l'exécution en phase initiale", acté en tête de ce document) ne suffit pas à garantir qu'il soit respecté au bon moment, et a construit un hook mécanique bloquant pour ses actions à fort impact. Ce projet n'a **aucun** équivalent aujourd'hui — l'engagement "pas d'automatisation" repose uniquement sur l'accord verbal/textuel. À réexaminer explicitement avant la Phase 4/5, pas à découvrir a posteriori que le texte seul n'a pas suffi.

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

**Résultat le plus solide à ce jour, ampleur révisée à la baisse après P0** : v7 (validation croisée H4/D1) — sur les 4 actifs testés et sans exception, la validation par D1 réduit le nombre de trades (~2,5-3×), améliore le win rate/profit factor et réduit le drawdown. La direction est confirmée, cohérente avec 7 sources indépendantes du corpus, mais l'**ampleur** (chiffrée initialement avec le calcul batch du cycle, +5 à +13 points de win rate) est en réalité bien plus modeste une fois le calcul rendu causal : +0,9 à +8,5 points selon l'actif, quasi neutre sur BNB. Chiffres à jour et nuance complète : `MTF_CROSS_VALIDATION_H4_D1.md`.

**Réserve non résolue depuis le début** : le signal reste un proxy (TSI+cycle+structure), jamais validé contre le vrai PRO Framework/Momentum (accès TradingView requis — hors de portée technique actuelle). C'est la limite fondamentale qui borne tout le reste. Le bug de signe du cycle a été revalidé hors-échantillon (XRP, `OOS_VALIDATION_CYCLE_SIGN.md`) pour réduire (pas éliminer) le risque de biais rétrospectif.

**P0 (calcul causal du cycle) traité ce cycle de travail** — voir occurrence #2 ci-dessus et `COUVERTURE_ENSEIGNEMENTS.md` ⚠️→◐ pour le détail complet. Résumé honnête : la performance **globale** rapportée sur H4 (v5/v6/v7) reste positive en direction (100 % des configurations testées gardent le même signe une fois le cycle rendu causal) mais son ampleur était surestimée d'environ 4× et son win rate d'environ 10 points — nouvelle référence chiffrée : `phase2_v5_causal_results.csv`, `phase2_v6_regime_causal_results.csv`, `phase2_v7_mtf_causal_results.csv`, `cycle_causal_vs_batch_comparison.csv`. Constat plus sérieux, à ne pas minimiser : le composant cycle **pris isolément** ne montre plus aucune corrélation significative avec le rendement futur une fois causal, sur aucun des 5 actifs testés (BTC/ETH/BNB/SOL + XRP OOS) — l'hypothèse la plus probable est que la performance globale tient surtout grâce au momentum et à la structure, le cycle devenant un filtre proche du bruit. **Test d'ablation fait depuis** (`code/ablation_test_cycle.py`) : ne confirme pas cette hypothèse simplement — résultat par actif non consensuel (ETH s'améliore nettement sans le cycle, SOL se dégrade nettement, BTC/BNB mixtes), cf. `COUVERTURE_ENSEIGNEMENTS.md` pour le détail. Ne pas retirer le cycle du score sur cette seule base.

**Ce qui n'est toujours pas fait, malgré tout ce travail** — voir `COUVERTURE_ENSEIGNEMENTS.md` pour la liste exhaustive. Points les plus significatifs : table "trade de tendance" à 5 étapes jamais testée (seule la table range l'a été) ; Fibonacci retracement jamais utilisé comme critère d'entrée ; règle "UT+2" exacte (2 niveaux au-dessus, pas le niveau immédiat) non implémentée ; plusieurs patterns/outils du manuel (Wall Street, Andrews Pitchfork, canal manuel Supports→Apex→Tangente, Cluster Technique, mécanisme +Reverse) jamais construits. Capital par palier : **traité ce cycle** (`code/capital_tiers.py`, cf. item 6 du backlog ci-dessous et `COUVERTURE_ENSEIGNEMENTS.md`). Le stop "Extreme Channel" bénéficie désormais du vrai `ctx_support` D1 (volet cross-timeframe traité, cf. item 4 ci-dessous) mais reste, comme avant, une bande EMA±ATR et non un vrai canal géométrique (volet distinct, toujours ouvert, cf. item 7).

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
- Coût funding rate quantifié à l'ordre de grandeur annuel PUIS calculé EXACT par timestamp (événement réel toutes les 8h, taille réelle du trade, sorties partielles Validation/Confirmation prises en compte) : `FUNDING_RATE_ANALYSIS.md` — constat affiné ce cycle : l'estimation grossière annualisée était une approximation correcte pour FAIBLE/MODERE (écart ≤ ±1,6 pt de retour cumulé) mais sous-estimait le retour net réel sur les profils agressifs (jusqu'à -19,9 pts SOL TRES_AGRESSIF) ; sur H4/FAIBLE (le profil jugé le plus à risque par l'estimation grossière), le coût exact ne renverse ni n'efface l'edge sur aucun des 4 actifs testés (BTC/ETH/BNB/SOL)
- Code : logique de position dédupliquée et testée (`code/position_engine.py`, 5 tests unitaires passent), plus de duplication entre `backtest_phase2.py`/`_v4.py`/`_v5.py`/`_v6.py`/`_v7.py`

**Lacunes ouvertes (liste complète et exhaustive : `COUVERTURE_ENSEIGNEMENTS.md`), les plus significatives :**
1. Table "trade de tendance" à 5 étapes jamais implémentée (seule la table range l'a été)
2. Fibonacci retracement jamais utilisé comme critère d'entrée
3. Règle "UT+2" exacte (2 niveaux au-dessus) non implémentée — v7 ne valide qu'avec le niveau immédiatement supérieur
4. ~~Stop "Extreme Channel" toujours calculé sur le même timeframe que celui tradé~~ — **traité ce cycle** : volet cross-timeframe résolu et mesuré (`MTF_CROSS_VALIDATION_H4_D1.md`), dégrade le ratio retour/drawdown dans la majorité des cas testés donc gardé optionnel (`use_mtf_stop`, défaut `False`). Le volet "vraie construction de canal" (pas EMA±ATR) reste ouvert, cf. point 7 ci-dessous
5. ~~Capital par palier (<10k€/10-100k€/>100k€) jamais pris en compte dans le sizing~~ — **traité ce cycle** (autre agent), cf. `COUVERTURE_ENSEIGNEMENTS.md`
6. ~~Funding rate : ordre de grandeur quantifié, pas encore modélisé par timestamp exact~~ — **traité ce cycle** : calcul exact événement-par-événement (`code/funding_rate_exact.py`), appliqué au moteur v7 causal (BTC/ETH/BNB/SOL, 4 profils), cf. `FUNDING_RATE_ANALYSIS.md` section "Calcul EXACT par timestamp" et `COUVERTURE_ENSEIGNEMENTS.md`
7. Patterns/outils jamais construits : règle "Wall Street" (élargissement = abstention), Fourchette d'Andrews, canal manuel (Supports→Apex→Tangente), Cluster Technique (second pattern), diversification 1%+1%, mécanisme "+Reverse" (Très Agressif)

## Phase 3 — Paper trading (inchangée)
Durée minimale 4-8 semaines, signaux temps réel sur démo. Critère GO/NO-GO : performance paper dans l'intervalle de confiance du backtest. **Pas encore engagée** — les lacunes de Phase 2 ci-dessus restent à trancher (combler avant Phase 3, ou accepter et documenter le périmètre non couvert) avant de basculer.

## Phase 4 — Pilote capital réel, exécution 100 % manuelle (inchangée)
Capital 10-15 % de la cible, wallet connecté sans transaction automatique, garde-fous structurels ajoutés suite au corpus (checklist pré-trade, latence de 10s, session max 60-90 min — cf. `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` et `TRADING_LESSONS_NEUROBIOLOGIE.md`).

## Phase 5 — Automatisation de l'exécution (non engagée)
Inchangée — discussion différée après Phase 4.

---

## Backlog priorisé (remplace la liste plate précédente)

Un directeur d'ingénierie priorise par impact sur la validité de ce qui est déjà rapporté, avant d'ajouter de nouvelles fonctionnalités. D'où l'ordre ci-dessous — pas l'ordre de découverte.

| # | Item | Impact si non traité | Effort | Priorité |
|---|---|---|---|---|
| 0 | ~~Calcul non causal de `compute_cycle_phase` (Hilbert sur série entière)~~ | **Traité ce cycle** — `compute_cycle_phase_causal` (fenêtre W=150, choisie empiriquement) en production, v5/v6/v7 + OOS XRP rejoués (`phase2_v{5,6,7}_*causal_results.csv`, `cycle_causal_vs_batch_comparison.csv`, `oos_xrp_cycle_validation_CAUSAL.csv`). Résultat MITIGÉ (pas résolu) : edge global H4 tient en direction (48/48) mais surestimé ~4× en ampleur ; edge du cycle isolé non significatif sur les 5 actifs testés — cf. `COUVERTURE_ENSEIGNEMENTS.md` ⚠️→◐ pour le détail et la nuance | Fait | **Traité** |
| 1 | Table "trade de tendance" à 5 étapes jamais testée | Élément IP documenté non implémenté ; on ne trade qu'en logique range même en régime Tendance | Élevé (nouveau barème complet) | P1 |
| 2 | ~~Stop "Extreme Channel" toujours same-timeframe malgré le nom~~ | **Traité ce cycle** — `attach_higher_context` transmet désormais aussi le `ctx_support` D1 au H4 (même jointure sans lookahead que le score), `run_v7(..., use_mtf_stop=True)`. Mesuré avec le moteur causal (4 actifs × 4 profils, `MTF_CROSS_VALIDATION_H4_D1.md`) : dégrade le ratio retour/drawdown dans 13/16 combinaisons, réduit le drawdown absolu dans 16/16 (sizing à risque fixe + stop D1 réel ~2,7× plus loin en moyenne ⇒ position mécaniquement plus petite). Réglage par défaut des campagnes conservé à `use_mtf_stop=False` ; option disponible pour comparaison. Le volet "channel" (construction géométrique réelle, pas EMA±ATR) reste séparément ouvert (item 7 ci-dessous) | Fait | **Traité** |
| 3 | Règle "UT+2" exacte (2 niveaux au-dessus, pas 1) | Le corpus (6 sources) décrit une règle plus stricte que celle testée | Moyen (nécessite une 3e timeframe, ex. Hebdo) | P2 |
| 4 | Fibonacci retracement comme critère d'entrée | Entrée jamais filtrée par profondeur de retracement, critère répété dans 5 sources | Moyen | P2 |
| 5 | ~~Funding rate exact par timestamp~~ | **Traité ce cycle** — `code/position_engine.py` (trace optionnelle `record_trace=True`, additive, 5/5 tests toujours au vert), `code/backtest_phase2_v7.py` (`run_v7(..., record_trace=True)`), `code/funding_rate_exact.py` (calcul événement-par-événement, taille réelle par trade, sorties partielles prises en compte), `code/test_funding_rate_exact.py` (4/4, cas synthétiques). Mesuré BTC/ETH/BNB/SOL × 4 profils H4 (moteur v7 causal) : l'estimation grossière annualisée précédente était une bonne approximation sur FAIBLE/MODERE (écart ≤ ±1,6 pt) mais sous-estimait le retour net réel sur les profils agressifs (jusqu'à -19,9 pts SOL TRES_AGRESSIF) ; sur H4/FAIBLE, le coût exact ne renverse ni n'efface l'edge sur aucun des 4 actifs — cf. `FUNDING_RATE_ANALYSIS.md` | Faible-moyen | **Traité** |
| 6 | ~~Capital par palier (<10k/10-100k/>100k€)~~ | **Traité ce cycle** — `code/capital_tiers.py` (règle extraite + hypothèse d'implémentation explicite, cf. `COUVERTURE_ENSEIGNEMENTS.md`), `code/backtest_phase2_capital_tiers.py` (BTC/ETH/BNB/SOL, 3 montants représentatifs des 3 paliers), `code/test_capital_tiers.py` (10 fonctions de test, frontières incluses, toutes vertes). Effet mesuré honnête : win rate/profit factor quasi inchangés (le sizing ne change pas quels trades gagnent), retour total et drawdown affectés proportionnellement au risk_pct effectif (de +7 à +27 pts de retour moyen sous 10k€ selon profil, -44 à -104 pts au-dessus de 100k€ pour AGRESSIF/TRES_AGRESSIF) | Faible | **Traité** |
| 7 | Règle "Wall Street", Andrews Pitchfork, canal manuel, Cluster Technique, "+Reverse" | Patterns/outils du corpus jamais construits | Élevé (5 items distincts) | P3 |

**Règle de traitement** : P0 se traite avant toute nouvelle mesure de performance considérée comme fiable — continuer à produire des chiffres v7 sans corriger P0 revient à empiler des résultats sur une base non quantifiée. P1 peut être mené en parallèle de P0 (ne dépend pas du signal cycle). P2/P3 après.

## Critères de sortie Phase 2 → Phase 3 (gate explicite, absent jusqu'ici)

Jusqu'ici "assez fidèle pour passer en paper trading" n'était jamais défini. Critères proposés, à valider avant de déclarer la Phase 2 terminée :
1. P0 (calcul causal du cycle) traité et les moteurs v5/v6/v7 rejoués avec — **fait, mitigé** : edge global H4 toujours positif après correction (100 % des configs, sens confirmé) mais surestimé ~4× en ampleur ; **la partie "statistiquement significatif" ne tient plus pour le composant cycle isolé** (non significatif sur les 5 actifs testés) — nuance à ne pas perdre avant de cocher ce critère comme pleinement acquis, cf. `COUVERTURE_ENSEIGNEMENTS.md` ⚠️→◐
2. Au minimum P1 traité (table trade de tendance testée ; stop réellement cross-timeframe : **fait et mesuré**, cf. item 4 du backlog — dégrade le risque-ajusté donc gardé optionnel plutôt qu'adopté par défaut)
3. Tests de régression (`code/test_*.py`) couvrant au moins : moteur de position (fait, 5/5), signal cycle (fait partiellement, 4/4 — ajout du test de causalité elle-même ce cycle, cf. limites restantes dans `code/test_proxy_v2.py`), classificateur de régime (pas encore fait)
4. Un pipeline unique rejouable (actuellement chaque moteur se lance manuellement, script par script) pour éviter que "refaire avec le moteur actuel" reste un geste ad hoc à chaque fois

## Prochaine action immédiate
P0 (recalcul causal de `compute_cycle_phase`), P1 "stop cross-timeframe" ET le test d'ablation du cycle sont désormais **tous traités** (cf. items 0 et 2 du backlog, `COUVERTURE_ENSEIGNEMENTS.md` ⚠️→◐ et `MTF_CROSS_VALIDATION_H4_D1.md`). Le tableau phare de `MTF_CROSS_VALIDATION_H4_D1.md` (H4 seul vs validé par D1) a aussi été mis à jour avec les chiffres causaux — il citait encore les anciens chiffres batch (4× surestimés) jusqu'à ce cycle de travail, corrigé pour ne pas laisser le résultat le plus visible du projet dans un état "connu obsolète, pas encore corrigé". Items 5 (funding rate exact par timestamp) et 6 (capital par palier) du backlog P2/P3 sont également **traités ce cycle** (en parallèle, par des agents distincts — cf. `COUVERTURE_ENSEIGNEMENTS.md` pour le détail des deux). Prochaine priorité réelle du backlog : item 1 (table "trade de tendance" à 5 étapes, jamais testée), puis item 3 (règle UT+2), item 4 (Fibonacci), item 7 (patterns/outils restants). Les trois lots précédemment délégués (A : qualité du code/tests + refonte cascade3 ; B : validation hors-échantillon du signe du cycle ; C : consolidation documentaire + funding rates) sont revenus et intégrés ci-dessus.
