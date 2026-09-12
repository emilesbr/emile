# CLAUDE.md — Contexte agent IA (Claude Code et Gemini CLI)

Ce fichier est lu automatiquement par Claude Code. `GEMINI.md` l'importe (`@CLAUDE.md`)
pour que Gemini CLI parte du même contexte — un seul fichier à tenir à jour, pas deux
versions qui divergent.

## Ce que fait ce projet

Formaliser, à partir du manuel PRO Indicators (Philippe Roux, usage personnel sous
CGU) et de 17 sources vidéo « Trading Lessons », une stratégie de trading crypto
multi-timeframe testée par backtest (BTC/ETH/BNB/SOL, données Binance Futures réelles),
avant tout engagement de capital réel. **Usage strictement personnel, aucune
automatisation d'exécution de trades réels en phase actuelle** — garde-fou mécanique :
`tests/unit/test_no_execution_automation.py` (fait échouer la suite si un motif
d'exécution réelle apparaît : `place_order`, `ccxt`, `python-binance`...).

## Où lire — dans cet ordre

1. `docs/STATUS.md` — point d'entrée unique, résumé exécutif à jour, « quel document
   lire pour quel sujet ». En cas de doute entre `STATUS.md` et `PLAN.md`, `PLAN.md`
   fait foi sur le fond (roadmap/phases), `STATUS.md` fait foi sur le classement
   documentaire.
2. `docs/PLAN.md` — plan directeur détaillé, backlog priorisé, historique des rounds
   de travail (chaque correction y est journalisée avec sa méthode et son résultat,
   honnête même quand dégradé).
3. `docs/COUVERTURE_ENSEIGNEMENTS.md` — liste exhaustive et à jour des écarts
   corpus↔code (ce qui manque, ce qui a été refusé et pourquoi).

## État actuel du dépôt (à vérifier avant de faire confiance à l'arborescence)

Réorganisation (`code/` + `.md` racine → `docs/`, `emile/` package, `tests/`,
`results/`, `data/`) faite, committée, poussée (`645e46c`). `golden_master.py`,
référencé par les scripts de migration (`cleanup_imports.py`/`update_imports.py`/
`refactor_tests.py`, racine — jetables), vérifié comme n'ayant jamais existé dans
l'historique : pas une perte, une référence erronée du script.

**Données OHLCV réelles restaurées et complétées** (Binance Futures USDM,
klines publiques). Contexte complet, à connaître avant de retoucher `data/` :
un cycle précédent avait committé par erreur un stub d'une seule ligne
(valeurs rondes fabriquées) dans `data/processed/BTCUSDT_1h_processed.csv`
pendant la réorg (`645e46c`), sans vérifier son contenu avant `git add` — la
vraie donnée n'avait jamais été versionnée dans ce dépôt (elle vivait sur un
ancien sandbox, `/home/user/spaciousabhi/...`, disparu). Récupérée depuis
l'API publique Binance Futures (`fapi.binance.com/fapi/v1/klines`, pas de clé
requise) depuis le premier listing de chaque actif jusqu'à aujourd'hui.

État complet par actif/UT dans `data/processed/` :
- **H1 natif** : BTC (2019-09-08, 61 439 bougies), ETH (2019-11-27, 59 529),
  BNB (2020-02-10, 57 728), SOL (2020-09-14, 52 521), **XRP** (2020-01-06,
  58 569 — n'existait avant que comme 365 barres D1 depuis une source
  externe disparue, cf. `emile/core/oos_xrp_faithful.py`/
  `oos_xrp_recommended.py`, toujours non branchés sur cette nouvelle donnée).
- **M15 natif** : BTC (245 751, déjà présent avant ce cycle, origine
  antérieure à cette session — intégrité revérifiée, pas juste supposée
  bonne), ETH (238 114), BNB (230 913), SOL (210 085) — complète la Phase 1
  (M15 BTC seul → NO-GO) sur les 4 actifs si ce chantier est rouvert.
- H4/D1/Hebdomadaire/Mensuel : dérivés par `resample()` du H1, aucune
  donnée native séparée nécessaire (vérifié contre le corpus : aucune règle
  n'exige une UT calendaire fixe non dérivable — voir section ci-dessous).

Intégrité de chaque fichier vérifiée avant usage (pas supposée) : 0 doublon,
0 trou (pas constant sur toute la série), 0 NaN OHLC, fourchettes de prix
cohérentes avec l'historique connu de chaque actif.

**Encore manquant, gap réel et non comblé** : le funding rate
(`fundingTime`/`fundingRate`, colonnes attendues par
`emile/core/funding_rate_exact.py` dans le même CSV que l'OHLCV) a disparu
avec l'ancienne donnée — masqué silencieusement car son test ne tourne que
sur données synthétiques. Pas un problème de couverture d'UT (le funding
n'est pas une unité de temps), mais un vrai trou à traiter séparément.

**Sur le principe "agréger, pas juger mécanisme par mécanisme" (rappel
explicite de l'utilisateur)** : vérifié contre le corpus (18 sources +
`RULES_EXTRACTION.md`) qu'aucune UT calendaire fixe (M15 compris) n'est
exigée nativement par un mécanisme précis — le mécanisme réel est relatif
(UT/UT+1/UT+2), illustré avec des exemples différents selon la vidéo.
**Mis à jour (20e-22e rounds)** : `faithful.py`/`unified_protocol.py`
combinaient jusqu'ici 7 mécanismes en dur ; 3 des 5+ mécanismes déjà codés
mais jamais agrégés ont depuis été branchés sans condition (Fourchette
d'Andrews lecture contextuelle, scopée RANGE_TENDANCIEL ; contrainte
"espace libre" MTF avant Breakout, H13 ; variante d'entrée "3ème borne
squeezée", #15) — détail et mesures honnêtes : `docs/PLAN.md` sections
"20e/21e/22e application". **Restent hors périmètre, à raison, pas des
oublis** : canal manuel comme stop (tie-break D1 non tranché par le
corpus), Cluster Technique/diversification (paramètres réellement
inventés, corpus sous-spécifié — H1-H5 de `diversification.py`) ; le
tableau money management "Range Tendanciel" (§3bis, distinct du Range
Neutre) reste également un chantier ouvert (19e round : moitié Faible/
Modéré codable mais exige un changement structurel de `position_engine.py`,
moitié Agressif/Très Agressif bloquée par "SL gain" indéfini nulle part
dans le corpus). Les GO/NO-GO déjà publiés (`STATUS.md`,
`PHASE1_CLOSEOUT.md`) portent sur le PROXY générique (confluence EMA), PAS
sur la stratégie réelle de Philippe — reformulation de ces documents encore
à faire pour que le qualificatif survive à une citation partielle.

**Garde-fou ajouté au passage, reste actif** :
`emile/backtests/backtest_phase2.py::load_h1` refuse explicitement
(`ValueError`) tout fichier de moins de 1000 lignes — un futur stub/placeholder
ne pourra plus reproduire silencieusement l'incident ci-dessus. 19 tests
marqués `@pytest.mark.data_dependent` (dont 3 étaient de vrais faux positifs
trouvés par audit dans `test_backtest_phase2_recommended.py` — passaient
contre le stub sans plus rien vérifier) + 2 marqués `skipif` seul (valides
avec n'importe quelle donnée, juste pas avec aucune). Avec la vraie donnée en
place : **`pytest -m ""` (suite complète) → 197/197 passés, 0 échec** —
vérifié par exécution réelle, pas affirmé.

**Mis à jour (37e round)** : la reconciliation demandée ci-dessus est désormais **faite pour
les moteurs actuellement cités comme référence** (pas pour les 49 CSV d'archive
d'engins supersédés — `v3/v4/v5/v6/CLOSES/CORRECTED/full_matrix/moneymanagement/patterns/
capital_tiers/diversification/ut2/reverse/squeeze/fib`... — délibérément laissés tels quels,
`STATUS.md` les classe déjà lui-même "historique, ne pas utiliser comme source de vérité", donc
aucun enjeu à les rejouer). Régénérés et vérifiés : `phase2_v7_mtf_results.csv`,
`phase2_recommended_results.csv`, `walkforward_recommended_results.csv`,
`walkforward_faithful_results.csv`, `cross_stress_test_faithful_gates_*.csv`,
`cross_stress_test_unified_capital_tiers_*.csv`,
`backtest_phase2_faithful_manual_channel_walkforward_results.csv` (les autres — `faithful`/
`unified`/`trend_table`/`risk_aggregation`/`walkforward_unified` — l'étaient déjà, régénérés lors
de rounds précédents de ce même cycle). **Conclusion honnête** : `max_dd_%` change à peine
(la donnée restaurée couvre surtout PLUS d'historique, pas un historique DIFFÉRENT sur les mêmes
bougies) mais `n_trades`/`total_return_%` montent partout, mécaniquement, avec la période plus
longue désormais disponible — v7 (BTC/MODERE H4_valide_par_D1 : 492→508 trades, +57,7%→+64,2%),
`recommended` (BTC/FAIBLE : 343→354 trades, +21,1%→+26,8%) sont les deltas les plus significatifs.
**Le chiffre le plus surveillé du projet, BNB/TRES_AGRESSIF (walk-forward)** : RECONFIRMÉ, pas
infirmé — `cross_stress_test_unified_capital_tiers_*.csv` étaient en fait BEAUCOUP plus périmés
que par la seule donnée (jamais régénérés depuis AVANT les corrections EXCES-H4/pyramidalisation-
régime/Conflit MTF/Stop-Loss-canal déjà connues), d'où un "catastrophique" 2021 à -45,9%/-63,5%
qui semblait réapparaître à tort ; recalculé sur la donnée actuelle avec le code actuel, 2021
retombe à +8,0%/-9,4% (proche de -9,5%/+5,2% déjà documenté dans `STATUS.md`), 2024 reste la pire
année (-12,2%/-26,3%, proche de -11,7%/-27,2% déjà documenté) — la conclusion "n'est plus à
exclure d'un usage réel" tient toujours. **Bug indépendant trouvé et corrigé au passage** (voir
paragraphe dédié ci-dessous) dans `backtest_phase2_faithful_manual_channel.py` — jamais testé
unitairement avant ce round. **Reste non fait, à dessein** : `oos_xrp_recommended.py`/
`oos_xrp_faithful.py` restent câblés sur un chemin de sandbox disparu
(`/home/user/http-kaijin/...`), donc toujours PAS rejouables sur la nouvelle donnée XRP —
rebranchement = chantier de code à part (remplacer le chargeur XRP D1 externe par
`data/processed/XRPUSDT_1h_processed.csv` resamplé), pas fait ce round, différé. Détail complet,
chiffres exacts par fichier : `docs/PLAN.md` section "37e application".

Bug indépendant trouvé et corrigé au passage (`emile/config/env_config.py`) :
le chemin de données par défaut était relatif (`Path("data/processed")`), donc
résolu différemment selon le `cwd` au moment de l'appel — cassait silencieusement
tout appelant qui change de répertoire après l'import (`emile/run_all.py`, qui
`chdir` vers une sortie temporaire). Corrigé en résolvant le chemin en absolu à
l'import.

## Principes non négociables (payés cash, ne pas les redécouvrir)

- **Une règle littérale du corpus s'applique sans condition, même si la performance
  mesurée est dégradée.** Rappel direct de l'utilisateur : *"la performance du Proxy
  ne décide jamais d'utiliser ou non l'IP de Philippe, on l'utilise dans tous les
  cas."* Plusieurs corrections ont désactivé à tort des règles littérales sur la seule
  base d'une contre-performance mesurée — ne pas répéter.
- **Toute citation du corpus attribuée à une règle doit être vérifiée mot pour mot
  avant implémentation, jamais recopiée depuis un document de suivi.** Plusieurs
  erreurs de citation/attribution ont été trouvées et corrigées après coup
  (`docs/STATUS.md`, rounds 6 à 8) — la citation de départ d'un item peut être fausse
  ou partiellement fausse.
- **"Que ferait un ingénieur senior (directeur) ?" n'oblige PLUS à mobiliser
  plusieurs agents en parallèle** (règle abrogée le 11 sept. 2026 — remplace la
  version précédente de ce principe, qui l'imposait systématiquement). La
  mobilisation multi-agents reste une option disponible, à utiliser quand le
  chantier s'y prête (investigations indépendantes croisables, gros volume
  d'exploration parallélisable) ou quand l'utilisateur la demande explicitement —
  jamais par défaut au seul énoncé de la question. Si un ou plusieurs agents sont
  mobilisés (à l'initiative de l'utilisateur ou de sa propre décision), chaque
  retour reste vérifié indépendamment avant d'être accepté — ça, c'est inchangé.
- **Un résultat honnête et dégradé est publié tel quel**, jamais habillé — la
  discipline de ce projet est de documenter ce qui ne marche pas autant que ce qui
  marche (voir le ton de `docs/STATUS.md`).
