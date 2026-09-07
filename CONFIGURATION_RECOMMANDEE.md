# Configuration recommandée — synthèse pour la Phase 3 (paper trading)

Répond à un constat d'ingénieur senior noté dans `PLAN.md` ("plan d'autonomie
8h") : chaque enseignement du corpus a été testé isolément contre la baseline
v7, mais **personne n'avait construit LA configuration recommandée** combinant
tout ce qui est validé en excluant ce qui dégrade — il n'existait pas de
chiffre de référence unique à citer avant de passer en Phase 3. Ce document
est cette synthèse : **il ne réévalue rien** (aucun élément ci-dessous n'est
re-testé ici), il **choisit** parmi 12 mesures déjà faites et documentées
dans `COUVERTURE_ENSEIGNEMENTS.md` (la table de croisement exhaustive
corpus↔code, qui reste la référence pour "qu'est-ce qui est implémenté ?")
et dans `PLAN.md` (le plan directeur/backlog, qui reste la référence pour
"que reste-t-il à faire ?"). Ce document ne duplique ni l'un ni l'autre —
il pointe vers eux et tranche.

**Rappel du principe qui gouverne tout ce document** (déjà énoncé en tête de
`COUVERTURE_ENSEIGNEMENTS.md`, redit ici car c'est le pivot de cette tâche
précise) : la performance du proxy ne sert **jamais** à décider si un élément
documenté du corpus doit être implémenté — c'est acté, ce n'est pas le sujet
ici. Cette synthèse répond à une question **différente et plus étroite** :
parmi ce qui est **déjà implémenté et déjà mesuré**, quel réglage par défaut
recommander pour un usage futur (Phase 3) ? Choisir un défaut par
performance mesurée n'est pas la même chose que rejeter un élément du corpus
— exactement la distinction déjà appliquée par ce projet à `use_mtf_stop`,
`use_fib_gate`, etc. (gardés optionnels, jamais supprimés).

Le moteur qui implémente cette configuration : `code/backtest_phase2_recommended.py`
(+ `code/walkforward_recommended.py`, `code/oos_xrp_recommended.py`,
`code/test_backtest_phase2_recommended.py`, 7/7 tests).

---

## 1. Les 10 décisions ON/OFF, avec preuve chiffrée existante citée

| # | Élément | Décision | Preuve citée (déjà mesurée, pas re-testée ici) |
|---|---|---|---|
| 1 | Cycle causal + structure causale (P0/P0-bis) | **ON, non négociable** | Déjà la seule version en production (`proxy_v2.py::add_proxy_v2_score`, `compute_swing_low_confirmed`) — aucune alternative batch n'est proposée par ce document |
| 2 | Gate MTF | **Hebdomadaire seul ("UT+2 strict"), D1 sauté comme gate de tendance** | `phase2_ut2_results.csv` : D1 seul WR 42,4%/PF 1,81/retour moyen +85,2% (446 trades) vs **UT+2 strict WR 42,1%/PF 2,14/retour moyen +133,2%** (428 trades) — meilleur retour ET profit factor que D1 seul, sans réduire l'échantillon autant que "D1 ET Hebdo" (193 trades, PF 2,43 mais retour +64,9% seulement — pas la règle littérale du corpus, cf. `backtest_phase2_ut2.py`) |
| 3 | Stop cross-timeframe réel (`use_mtf_stop`) | **OFF** | `MTF_CROSS_VALIDATION_H4_D1.md` : dégrade le ratio retour/drawdown dans **13/16** combinaisons actif×profil, malgré une réduction de drawdown absolu dans 16/16 (sizing à risque fixe, position mécaniquement plus petite) |
| 4 | Fibonacci gate | **OFF** | `phase2_fib_results.csv` : dégrade **32/32** configurations (retour moyen -13,8% vs +107,8% baseline) |
| 5 | Andrews Pitchfork gate | **OFF** | `phase2_patterns_results.csv` : dégrade nettement (retour médian 18% vs 212% référence, négatif sur ETH -9,5% à -21,9%) — **hypothèse de gating retenue ici qui est en cause** (le corpus documente le rôle/le chiffre de l'outil, pas comment l'utiliser comme filtre d'entrée), pas une conclusion sur le pattern géométrique lui-même — piste ouverte, non refermée |
| 6 | Wall Street (abstention élargissement) | **OFF** | `phase2_patterns_results.csv` : effet quasi neutre (WR 38,2% vs 38,9%, PF 1,57 vs 1,53) — coût d'implémentation faible mais bénéfice net nul ; argument retenu : ne pas ajouter de surface de code sans bénéfice démontré, cohérent avec "le moteur le plus simple compte tenu des choix" |
| 7 | Canal manuel comme stop | **OFF** | `phase2_patterns_results.csv` : change le profil risque/récompense (WR -9,5 pt, retour médian plus élevé) sans être strictement meilleur — alternative de style, pas un remplacement validé ; le comportement le plus simple/le plus testé (canal EMA±ATR natif) reste la référence |
| 8 | Diversification / Cluster Technique | **OFF** | `phase2_diversification_results.csv` : effet marginal isolé (pyramidalisation neutralisée des deux côtés) proche de zéro et mixte (+0,2/+0,3/-0,2/-0,1 pt BTC/ETH/BNB/SOL) — pas de bénéfice net démontré |
| 9 | Capital par palier | **Paramètre, pas une décision ON/OFF de signal** | `capital_tiers.py::effective_sizing`, exposé via `run_recommended(..., capital_eur=...)`. Absent (`None`) → risk_pct du profil choisi, inchangé |
| 10 | +Reverse (table range, TRES_AGRESSIF) | **OFF par défaut** (paramètre disponible) | `phase2_v7_reverse_results.csv` : mixte (3/4 actifs améliorés +2,2 à +18,7 pts, BNB dégradé -6,1 pts) et spécifique au seul profil TRES_AGRESSIF selon le corpus (RULES_EXTRACTION §3) — pas un défaut applicable aux 4 profils. Exposé via `reverse_at_limit=True` pour qui veut l'activer sur ce profil précis |

**Hors périmètre, justifié, pas un oubli** : la table "trade de tendance" à 5
étapes (`trend_table.py`) n'est pas intégrée — structurellement incompatible
avec `position_engine.py` (justifié en tête de `trend_table.py`), et son
propre résultat mesuré montre que 100% des campagnes se referment en étape
Accumulation sur ce jeu de données (`phase2_trend_table_results.csv`) — les
étapes 2-5 jamais exercées empiriquement. L'intégrer ici ajouterait un
second moteur parallèle sans preuve d'apport, contraire au principe "un
chiffre de référence unique" de cette synthèse.

---

## 2. Le chiffre de référence — BTC/ETH/BNB/SOL × 4 profils

**Nouvelle référence à jour du projet** (remplace la dispersion actuelle
entre `MTF_CROSS_VALIDATION_H4_D1.md`, `phase2_v7_mtf_causal_results.csv`,
`phase2_ut2_results.csv` pour la question "quelle config utiliser ?" — ces
documents restent corrects et ne sont PAS supprimés, ils documentent chacun
UNE variante isolée ; celui-ci documente LA combinaison retenue).

Fichier source : `code/phase2_recommended_results.csv` (produit par
`python code/backtest_phase2_recommended.py`, alias `recommended` de
`code/run_all.py`).

| Symbole | Profil | Trades | Max DD % | Retour total % | Win rate % | Profit factor |
|---|---|---|---|---|---|---|
| BTC | FAIBLE | 429 | -8,9 | +50,9 | 40,1 | 2,02 |
| BTC | MODERE | 429 | -16,1 | +123,7 | 38,7 | 2,16 |
| BTC | AGRESSIF | 429 | -21,7 | +171,7 | 38,7 | 2,13 |
| BTC | TRES_AGRESSIF | 429 | -24,4 | +254,9 | 38,7 | 2,32 |
| ETH | FAIBLE | 440 | -9,6 | +12,7 | 44,3 | 1,37 |
| ETH | MODERE | 440 | -20,3 | +33,0 | 43,2 | 1,45 |
| ETH | AGRESSIF | 440 | -28,7 | +64,4 | 43,2 | 1,55 |
| ETH | TRES_AGRESSIF | 440 | -42,2 | +58,5 | 41,6 | 1,47 |
| BNB | FAIBLE | 578 | -16,2 | +19,2 | 43,1 | 1,40 |
| BNB | MODERE | 578 | -27,2 | +30,1 | 42,4 | 1,35 |
| BNB | AGRESSIF | 578 | -33,4 | +36,0 | 42,4 | 1,32 |
| BNB | TRES_AGRESSIF | 578 | -36,7 | +102,0 | 42,2 | 1,54 |
| SOL | FAIBLE | 265 | -5,4 | +70,8 | 43,8 | 3,59 |
| SOL | MODERE | 265 | -9,3 | +171,9 | 43,8 | 3,49 |
| SOL | AGRESSIF | 265 | -15,0 | +316,1 | 43,8 | 3,44 |
| SOL | TRES_AGRESSIF | 265 | -29,2 | +615,4 | 43,0 | 3,63 |

**Moyenne des 16 lignes** : 428 trades, max DD -21,5 %, retour total moyen
**+133,2 %**, win rate moyen **42,1 %**, profit factor moyen **2,14**.

Ces moyennes sont **identiques** (aux arrondis près) à la ligne "UT+2 strict"
de `phase2_ut2_results.csv`/`COUVERTURE_ENSEIGNEMENTS.md` — attendu et
rassurant : `backtest_phase2_recommended.py` reproduit délibérément ce mode
déjà mesuré (décision #2), sans réintroduire de divergence numérique dans le
nouveau moteur plus simple (pas de D1 chargé du tout, cf. point suivant).

**Simplification permise par les décisions ci-dessus** : la configuration
recommandée ne charge et ne prépare QUE le H4 (exécution) et l'Hebdomadaire
(gate de tendance) — le D1 n'est utilisé nulle part par défaut (ni comme
gate, décision #2, ni comme stop réel, décision #3). C'est délibérément un
moteur plus simple que v7/ut2, pas juste "un flag de plus" : moins de code,
moins de données à charger, moins de surface pour un futur bug — cohérent
avec la consigne de la tâche ("le plus simple possible compte tenu des
choix").

---

## 3. Walk-forward année par année

Fichier source : `code/walkforward_recommended.py` →
`code/walkforward_recommended_results.csv`. Sur le modèle de
`AUDIT_QUALITE_ET_CORRECTION_CYCLE.md` (déjà fait une fois, mais sur BTC H4
MODERE seul et sur un moteur **pré**-P0/P0-bis/synthèse) — étendu ici aux 4
actifs, profil MODERE, avec le moteur **pleinement causal + gate Hebdo**.
Chaque année est rejouée équité-à-1.0 (pas un cumul réaliste, cf. docstring
de `walkforward_recommended.py`) — l'objectif est "y a-t-il une année
catastrophique ?", pas une estimation de performance composée.

| Actif | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (partiel, 6 mois) |
|---|---|---|---|---|---|---|---|
| BTC | +42,0% (81 tr., PF 5,34) | +13,4% (79 tr., PF 1,68) | **-1,5%** (8 tr., PF 0,14) | +18,4% (104 tr.) | +14,2% (110 tr.) | **-4,7%** (38 tr.) | 0 trade |
| ETH | +20,1% (67 tr.) | +0,6% (138 tr.) | **-2,3%** (18 tr.) | **-6,3%** (65 tr.) | +7,2% (93 tr.) | +12,2% (59 tr.) | 0 trade |
| BNB | **-5,4%** (61 tr.) | +19,0% (140 tr.) | +0,7% (3 tr.) | **-1,3%** (23 tr.) | **-14,5%** (206 tr.) | +35,9% (144 tr.) | 0 trade |
| SOL | 0 trade (données partielles) | +16,6% (49 tr.) | 0 trade | +56,5% (38 tr., PF 15,78) | +15,8% (114 tr.) | +28,8% (64 tr.) | 0 trade |

**Lecture honnête, pas arrangée** :
- **Aucune année ne produit un effondrement massif** (le pire cas est BNB
  2024, -14,5 %, contre des effondrements bien plus sévères observés
  ailleurs dans ce projet avec des proxies antérieurs, `WALKFORWARD_ANALYSIS.md`)
  — 7 années négatives sur 26 lignes mesurées (BTC 2/7, ETH 2/7, BNB 3/7,
  SOL 0/7), toutes de faible ampleur.
- **2022 (Luna/FTX) et 2026 (partiel) se distinguent par l'ABSENCE de
  trades plutôt que par des pertes** : le gate Hebdomadaire (`score >= 2`
  sur l'Hebdo) ne s'active quasiment jamais sur ces deux fenêtres — vérifié
  directement (pas supposé) : `gate_score >= 2` est vrai 0 fois sur toute
  l'année 2026 pour les 4 actifs, et 0 fois sur SOL 2022. C'est cohérent
  avec `WALKFORWARD_ANALYSIS.md` qui documentait déjà 2022 comme la seule
  année où TOUS les timeframes et TOUS les actifs plongent ensemble, et le
  Sharpe H4/H1 2026 déjà négatif dans ce même document (-1,42/-1,36). Le
  gate Hebdomadaire, plutôt que de perdre de l'argent pendant ces phases,
  **reste simplement à l'écart** — un comportement défensif, pas un signe
  de panne.
- BTC 2022 (8 trades) et SOL 2020 (données partielles, le listing Binance
  Futures de SOL démarre en cours d'année) restent des échantillons trop
  minces individuellement pour juger — signalé, pas maquillé.

**Conclusion walk-forward** : pas d'année catastrophique identifiée sur les
4 actifs testés avec cette configuration ; les deux fenêtres les plus
difficiles historiquement pour ce projet (2022, 2026 partiel) se traduisent
par une **absence de trades** plutôt que par des pertes, cohérent avec le
rôle attendu du gate Hebdomadaire (rester à l'écart en régime défavorable).

---

## 4. Validation hors-échantillon XRP

Fichier source : `code/oos_xrp_recommended.py` →
`code/oos_xrp_recommended_results.csv`. Sur le modèle de
`OOS_VALIDATION_CYCLE_SIGN.md` section 2 ("procédure décidée à l'avance") —
**procédure et limite de données décidées et documentées AVANT tout calcul
de performance**, reproduites en détail dans la docstring de
`oos_xrp_recommended.py` (section "2. PROCÉDURE DÉCIDÉE À L'AVANCE").

**Limite honnête, énoncée avant le résultat** : seule une donnée **D1** (365
barres, 2025-06-03 → 2026-06-02, même source que l'OOS précédent
`/home/user/http-kaijin/crypto-decision-bi`) est disponible pour XRP dans cet
environnement — aucun H4/H1. Le gate Hebdomadaire (décision #2) a donc été
**désactivé** pour ce test, pour une raison de contrainte de données décidée
AVANT tout calcul, pas après avoir regardé un résultat décevant : 365
barres D1 ne donnent que 53 bougies Hebdomadaires, et
`compute_cycle_phase_causal` retourne un tableau de **zéros** (pas NaN,
vérifié en lisant le code) quand la série est plus courte que sa fenêtre de
150 — un gate Hebdomadaire calculé là-dessus testerait un cycle
artificiellement neutralisé sur toute la série, pas le gate réel. **Cet OOS
valide donc le socle signal (cycle+structure causaux) + risk management +
position engine, PAS le composant gate MTF**, qui reste structurellement
intestable sur un historique aussi court.

| Profil | Trades | Max DD % | Retour total % | Win rate % | Profit factor |
|---|---|---|---|---|---|
| FAIBLE | 3 | -1,2 | -0,3 | 33,3 | 0,70 |
| MODERE | 3 | -2,4 | -0,6 | 33,3 | 0,70 |
| AGRESSIF | 3 | -3,6 | -1,5 | 33,3 | 0,47 |
| TRES_AGRESSIF | 3 | -4,1 | -2,0 | 33,3 | 0,38 |

**Résultat honnête, pas maquillé en conclusion positive** : sur cet
échantillon, **3 trades sur un an de XRP D1** (le gate MTF étant désactivé
faute de données, cf. ci-dessus), retour légèrement négatif sur les 4
profils (-0,3 % à -2,0 %), win rate 33,3 % (1 gagnant sur 3). **Un
échantillon de 3 trades ne permet strictement aucune conclusion
statistique** — ni positive ni négative — sur la validité de la config
recommandée hors-échantillon. Ce n'est pas une surprise compte tenu de
l'échelle : les échantillons D1 sur 6 ans (BTC/ETH/BNB/SOL) étaient déjà
documentés comme minces (13-32 trades, `MTF_CROSS_VALIDATION_H4_D1.md`) ;
un an de D1 sur un seul actif est mécaniquement plus mince encore. **Ce
résultat n'infirme ni ne confirme la config recommandée** — il illustre
plutôt une limite structurelle de ce test précis (résolution D1 disponible,
fenêtre courte), pas un signal sur le socle signal+risk management lui-même.
Aucune tentative n'a été faite pour améliorer ce chiffre après coup (aucun
paramètre changé après avoir vu le -0,3 % à -2,0 % ci-dessus).

**Ce que cet OOS confirme, malgré l'échantillon mince** : le moteur
s'exécute sans erreur sur un actif et une résolution qu'il n'a jamais vus
avant, produit des trades cohérents avec la logique attendue (pas de crash,
pas de comportement aberrant), et le risk management se comporte comme prévu
(drawdown proportionnel au risk_pct du profil, de -1,2% FAIBLE à -4,1%
TRES_AGRESSIF pour les mêmes 3 trades). **Ce que cet OOS ne confirme PAS** :
un edge statistiquement valide sur XRP (échantillon trop petit), ni la
composante gate MTF (structurellement non testée ici).

---

## 5. Ce qui reste ouvert (pas caché)

- Le composant **cycle isolé** ne montre aucune corrélation causale
  significative avec le rendement futur sur les 5 actifs déjà testés
  (BTC/ETH/BNB/SOL + XRP OOS, `COUVERTURE_ENSEIGNEMENTS.md` ⚠️→◐) — il reste
  dans le score composite (décision #1, ON non négociable) parce que le test
  d'ablation dédié est non concluant (4 actifs en désaccord de direction),
  pas parce que son apport causal individuel est démontré. Le composite
  (momentum+cycle+structure, score≥2) reste le réglage validé empiriquement
  au niveau global, pas au niveau du cycle seul.
- L'hypothèse de gating Andrews retenue (décision #5) n'est qu'UNE lecture
  possible d'un manuel muet sur comment utiliser ce pattern en entrée — une
  autre hypothèse pourrait donner un résultat différent, non testée
  (`PLAN.md`, vague 5 potentielle).
- Le seuil de confluence percentile adaptatif du Cluster Technique n'a pas
  été stress-testé pour sa robustesse (`PLAN.md`, vague 5 potentielle).
- L'OOS XRP ne valide que le socle signal+risk management, pas le gate MTF
  (cf. section 4) — une donnée H4/H1 pour un actif indépendant permettrait
  de fermer cette limite si elle devient disponible.
- Le proxy reste un proxy : jamais validé contre le vrai PRO
  Framework/Momentum de Philippe Roux (accès TradingView requis, hors de
  portée technique actuelle) — limite fondamentale de tout ce document,
  déjà rappelée dans `STATUS.md`/`PLAN.md`.
- Cette configuration recommandée n'a, par définition, jamais tourné en
  paper trading réel — c'est précisément l'objet de la Phase 3 qui suit.
  Aucun chiffre ci-dessus ne doit être lu comme "validé" avant que la
  Phase 3 confirme une performance dans l'intervalle de confiance du
  backtest (critère GO/NO-GO déjà posé dans `PLAN.md`).

---

## 6. Pour aller plus loin (documents à consulter, pas à dupliquer)

- **Détail complet des preuves citées section 1** : `COUVERTURE_ENSEIGNEMENTS.md`
  (table de croisement corpus↔code exhaustive).
- **Backlog / feuille de route** : `PLAN.md` (section "Configuration
  recommandée" en tête pointe ici).
- **Méthodologie walk-forward** : `AUDIT_QUALITE_ET_CORRECTION_CYCLE.md`.
- **Méthodologie OOS "décidée à l'avance"** : `OOS_VALIDATION_CYCLE_SIGN.md`.
- **Moteur** : `code/backtest_phase2_recommended.py` (docstring complète,
  10 décisions résumées avec chiffres), `code/walkforward_recommended.py`,
  `code/oos_xrp_recommended.py`, `code/test_backtest_phase2_recommended.py`
  (7/7 tests).
- **Point d'entrée pipeline** : `python code/run_all.py --only recommended`
  (alias `recommended` de `code/run_all.py`, 13e moteur du pipeline).
