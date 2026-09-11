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

Une réorganisation (`code/` + `.md` racine → `docs/`, `emile/` package, `tests/`,
`results/`, `data/`) a eu lieu récemment. **Vérifier `git status` avant de supposer que
la nouvelle arborescence est complète** : au moment de la rédaction, `golden_master.py`
référencé par les scripts de migration (`refactor_tests.py`, `update_imports.py`,
`cleanup_imports.py`, à la racine — jetables, pas des outils du projet) est introuvable,
`data/processed/` ne contient que BTC (ETH/BNB/SOL absents), et **13/181 tests
échouent** pour cette raison. Ne pas relancer une automatisation basée sur "tests
verts" sans avoir vérifié l'état réel de la suite.

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
