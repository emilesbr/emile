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

**Aucune donnée OHLCV réelle (BTC/ETH/BNB/SOL) n'est disponible dans ce dépôt ni
ailleurs sur cette machine, et ne l'a jamais été dans l'historique git.** Trouvé par
audit dédié (pas une supposition) : `data/processed/BTCUSDT_1h_processed.csv`
n'est PAS "BTC présent, ETH/BNB/SOL manquants" comme un cycle précédent l'avait
affirmé à tort — c'est une seule ligne de valeurs rondes fabriquées
(`50000/50100/49900/50050`), committée par erreur pendant la réorg (`645e46c`)
sans que son contenu soit vérifié avant `git add`. La vraie donnée a toujours vécu
sur un chemin absolu d'un autre environnement (`/home/user/spaciousabhi/
binance-futures-backtest-research/data/processed`, visible dans l'historique des
imports), jamais versionnée dans ce dépôt. `git log --all` confirme : c'est la
seule version de ce fichier qui ait jamais existé. Aucune copie de secours
trouvée nulle part sur cette machine (recherche exhaustive faite). L'accès réseau
à l'API Binance fonctionne depuis ce sandbox (vérifié, `api.binance.com` répond) —
récupérer une vraie donnée est possible mais reste à faire, pas un raccourci de
"copier un fichier existant".

**Conséquence directe, plus grave qu'un simple "13 tests rouges" (constat initial
sous-évalué)** : audit complet fait (mobilisation multi-agents + vérification
croisée) plutôt que de s'arrêter aux 13 échecs visibles. Résultat :
- `emile/backtests/backtest_phase2.py::load_h1` refuse maintenant explicitement
  (`ValueError`) tout fichier de moins de 1000 lignes — un stub/placeholder ne
  peut plus produire silencieusement une sortie dégénérée (0-1 trade)
  indiscernable à l'oeil d'un "effet nul" légitime, déjà fréquent dans ce projet.
- **19 tests** dépendent réellement de données réelles absentes (12 initiaux +
  3 trouvés dans `test_backtest_phase2_recommended.py` par audit dédié comme
  faux positifs dangereux — assertions qui ne testaient plus rien contre la
  fixture bidon, cf. `docs/PLAN.md`/historique de session — + 3 trouvés en
  refaisant tourner la suite après le durcissement de `load_h1`, jamais visibles
  avant) : tous marqués `@pytest.mark.data_dependent`.
- **2 tests supplémentaires** (`test_mtf_gate_bypass_never_compares_to_nan`,
  `test_reverse_at_limit_scoped_to_tres_agressif_only`) sont structurellement
  valides quel que soit le contenu réel de la donnée (vérifié par
  instrumentation, pas supposé) mais ont besoin d'AU MOINS une donnée non
  dégénérée pour s'exécuter — marqués `skipif` (pas `data_dependent` : ils ne
  demandent pas de VRAIE donnée, juste une donnée non vide) ; ils repasseront
  automatiquement dès qu'une vraie donnée existera.

`pytest` sans option (convention du projet) : **176 passés, 2 skip, 19 exclus,
0 échec** — honnêtement vert, rien masqué. `pytest -m ""` : 10 échecs directs
(données réelles requises) + 176 passés + 11 skip (176+11+10=197, rien perdu).
Ne pas citer un chiffre de tests verts sans avoir vérifié `pytest -m ""` en plus
du défaut — c'est exactement l'erreur qui a laissé les 9 faux positifs de
`test_backtest_phase2_recommended.py` invisibles jusqu'à cet audit.

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
- **"Que ferait un ingénieur senior (directeur) ?" mobilise plusieurs agents en
  parallèle, pas une analyse individuelle** (règle explicite de l'utilisateur,
  `docs/PLAN.md`). Chaque retour d'agent reste vérifié indépendamment avant d'être
  accepté — la mobilisation multi-agents ne remplace pas la vérification, elle s'y
  ajoute.
- **Un résultat honnête et dégradé est publié tel quel**, jamais habillé — la
  discipline de ce projet est de documenter ce qui ne marche pas autant que ce qui
  marche (voir le ton de `docs/STATUS.md`).
