# Validation croisée multi-timeframe réelle (H4 exécution / D1 référence) — lacune comblée

**Question à l'origine** : "les stratégies prennent-elles en compte le timeframe inférieur et supérieur dans leur décision ?" Réponse à ce moment-là : **non**. Vérification par lecture directe du code (`code/backtest_phase2_v6.py`) : `ctx_support = ema_slow - 2*atr` est calculé sur le **même** dataframe que celui tradé (H4 seul ou D1 seul, jamais croisés) — malgré le nom "Extreme Channel" qui laissait entendre un vrai canal de l'unité de temps supérieure. **Correction de documentation** : ce n'était qu'une bande de volatilité locale, pas un canal cross-timeframe. Les seules fois où une vraie logique multi-timeframe avait été testée (Phase 1, `backtest_cascade3.py`) utilisaient l'ancien signal EMA générique — jamais fusionnées avec la lignée v4/v5/v6 (proxy TSI+cycle+structure, régime, risk management corrigé).

## Ce qui est construit (`code/backtest_phase2_v7.py`)
Exécution sur H4, référence/contexte sur D1 : un signal H4 n'est validé que si :
1. Le score proxy_v2 (TSI+cycle+structure) de la **dernière bougie D1 entièrement clôturée** (jointure `merge_asof` sans lookahead) est également ≥2
2. Le régime D1 n'est pas EXCES

## Résultat — rejoué avec le moteur causal (P0), chiffres à jour

**Historique de cette section** : le tableau ci-dessous montrait initialement des chiffres calculés avec l'ancien calcul batch (non causal) du cycle Hilbert, signalés obsolètes puis laissés en l'état "à rejouer" pendant le traitement du P1 (stop cross-timeframe, tâche distincte). Les chiffres avec le moteur causal (`compute_cycle_phase_causal`) existaient déjà dans `phase2_v7_mtf_results.csv` (produits lors du rejeu de la section "Correction P1" ci-dessous) mais n'avaient jamais été transcrits ici — corrigé à présent, sans nouveau calcul, juste lecture du CSV déjà à jour.

**REFRESH (6e round de mobilisation multi-agents, trouvaille annexe de la sensibilité `MIN_BORDERS`)** : `phase2_v7_mtf_results.csv` était resté périmé depuis les corrections EXCES-H4 et Conflit Multi-Timeframe apportées à `backtest_phase2_v7.py` (ex. BTC 504→**492** trades) — jamais régénéré après ces 2 corrections. Régénéré et tableaux ci-dessous rafraîchis (`python3 backtest_phase2_v7.py`, vérifié par ailleurs indépendamment via `min_borders_sensitivity_v7_results.csv` au seuil de référence).

| Actif (profil FAIBLE, stop H4) | Trades | Win rate | Profit factor | Max DD | Retour |
|---|---|---|---|---|---|
| BTC — H4 seul | 1400 | 41,0% | 1,52 | -14,4% | +79,4% |
| BTC — validé par D1 | 492 | **43,1%** | **1,57** | **-9,8%** | +21,9% |
| ETH — H4 seul | 1405 | 36,9% | 1,29 | -15,1% | +35,0% |
| ETH — validé par D1 | 427 | **46,1%** | **2,06** | **-6,5%** | +38,9% |
| BNB — H4 seul | 1408 | 41,1% | 1,32 | -18,0% | +37,9% |
| BNB — validé par D1 | 525 | **42,7%** | **1,48** | **-12,5%** | +20,5% |
| SOL — H4 seul | 1234 | 39,6% | 1,69 | -19,3% | +141,4% |
| SOL — validé par D1 | 339 | **39,8%** | **1,77** | **-8,4%** | +23,0% |

Détail complet (4 profils × 4 actifs × 2 configurations de stop) : `phase2_v7_mtf_results.csv`.

**Constat révisé (moteur causal, chiffres rafraîchis) — la direction tient, l'ampleur reste modeste** : sur les 4 actifs, sans exception, la validation par D1 réduit le nombre de trades (~2,7-3,3×), améliore le win rate et le profit factor, et réduit le drawdown — la direction du résultat original tient. L'ampleur reste modeste, cohérente avec la mesure précédente (avant EXCES-H4/Conflit MTF) : +0,2 point (SOL) à +9,2 points (ETH) de win rate ; profit factor quasiment inchangé sur BTC/SOL (+0,05 à +0,08) et significatif sur ETH (+0,77) et BNB (+0,16) ; le retour cumulé chute fortement partout (cohérent avec l'edge global lui-même surestimé ~4× par le batch, cf. `COUVERTURE_ENSEIGNEMENTS.md` P0).

Ce n'est plus "le résultat le plus uniformément spectaculaire du projet" (affirmation d'origine, à ne plus citer telle quelle) — c'est un résultat qui **confirme la direction** (valider un signal H4 par son contexte D1 aide, sans exception sur les 4 actifs) avec une ampleur modeste, cohérent avec 7 sources indépendantes du corpus sur l'intérêt de la validation croisée — mais qui ne suffit plus à lui seul à justifier un déploiement, vu la faiblesse de certains gains (SOL notamment, quasi neutre sur le win rate).

## Limites documentées
- Toujours un proxy, pas le vrai signal PRO Framework
- Résultats informatifs, pas une validation définitive (principe déjà établi)
- Un seul sens de cascade testé ici (D1 valide H4) — le sens complet à 3 niveaux (Daily/H4/H1) avait déjà été testé séparément avec un résultat négatif (`CASCADE3_H1_EXECUTION_TEST.md`), mais avec l'ancien moteur — à refaire avec le moteur v7 si on veut la comparaison la plus à jour
- N'implémente pas encore la règle exacte "UT+2" (deux niveaux au-dessus) des sources #15/#16 — ici c'est directement le niveau immédiatement supérieur (H4→D1), pas H4→Hebdo
- ~~Le stop "Extreme Channel" reste calculé sur le même timeframe que celui tradé~~ → **comblé, voir section suivante.** Le stop bénéficie désormais de la même jointure cross-timeframe sans lookahead que le signal.

## Correction P1 — le STOP utilise désormais le vrai canal D1 (plus seulement le signal)

**Rappel du problème** (déjà documenté ci-dessus et dans `COUVERTURE_ENSEIGNEMENTS.md`) : jusqu'ici, seul le SIGNAL H4 était validé par le score D1 (via `attach_higher_context`) ; le STOP (`ctx_support = ema_slow - 2*atr`) restait calculé sur le H4 lui-même — malgré le nom "Extreme Channel" qui désigne, dans le corpus (#12/#16, `TRADING_LESSONS_CLUSTERS_PRIX.md`), explicitement *"le contexte de l'UT supérieure affiché sur l'UT de trading"*.

**Ce qui a changé** (`code/backtest_phase2_v7.py`) : `attach_higher_context` transmet maintenant, en plus du score et du régime, le `ctx_support` D1 — via la même jointure `merge_asof` sans lookahead (dernière bougie D1 entièrement close). `run_v7` expose un nouveau paramètre `use_mtf_stop` (défaut `False`, comportement historique inchangé) : à `True`, le stop réel à l'entrée est ce `ctx_support` D1 (niveau de prix absolu, substituable tel quel à `ctx_support` H4 — pas de problème d'échelle, les deux sont des prix, pas des distances).

**Mesure — stop H4 (même UT) vs stop D1 réel, gate MTF activé dans les deux cas, 4 actifs × 4 profils, moteur DÉJÀ CAUSAL** (`compute_cycle_phase_causal`, correction P0 intégrée au moment de cette mesure ; CSV rafraîchi 6e round, cf. note ci-dessus — détail complet : `phase2_v7_mtf_results.csv`, colonnes `profile`/`stop`) :

| Actif (profil FAIBLE) | Stop | Trades | Win rate | Profit factor | Max DD | Retour | Retour/DD |
|---|---|---|---|---|---|---|---|
| BTC | H4 (même UT) | 492 | 43,1% | 1,57 | -9,8% | +21,9% | 2,23 |
| BTC | D1 réel | 491 | 43,2% | **1,97** | **-3,1%** | +14,5% | **4,68** |
| ETH | H4 (même UT) | 427 | 46,1% | 2,06 | -6,5% | +38,9% | **5,98** |
| ETH | D1 réel | 427 | 45,4% | 2,09 | **-2,9%** | +16,1% | 5,55 |
| BNB | H4 (même UT) | 525 | 42,7% | 1,48 | -12,5% | +20,5% | **1,64** |
| BNB | D1 réel | 522 | 42,5% | 1,41 | **-5,6%** | +7,0% | 1,25 |
| SOL | H4 (même UT) | 339 | 39,8% | 1,77 | -8,4% | +23,0% | **2,74** |
| SOL | D1 réel | 339 | 39,8% | 1,37 | -4,4% | +4,4% | 1,00 |

**Mécanisme identifié (pas une hypothèse — vérifié sur BTC, indépendant du cycle donc inchangé par la correction P0 ; non re-vérifié indépendamment lors du refresh 6e round, mais c'est un fait structurel sur `ctx_support`, indépendant des gates EXCES-H4/Conflit MTF corrigés depuis)** : le `ctx_support` D1 réel est en moyenne ~2,7× plus loin du prix que le `ctx_support` calculé sur H4 (distance moyenne 10,1% vs 3,8% du prix ; le D1 est plus éloigné dans 78% des bougies). Le sizing du moteur (`size_frac = risk_pct / stop_pct`, risque fixe en % de l'equity) réduit donc mécaniquement la taille de position quand le stop réel D1 est utilisé — moins d'exposition, donc moins de retour composé, mais aussi (le plus souvent) moins de drawdown, dans une proportion qui varie par actif.

**Résultat honnête, mesuré sur les 16 combinaisons (4 actifs × 4 profils), gate MTF activé, moteur causal, chiffres rafraîchis 6e round** :
- Le drawdown absolu diminue avec le stop D1 réel dans **16/16 cas**, sans exception.
- Le retour total diminue systématiquement (16/16) — cohérent avec le sizing plus petit.
- **Le ratio retour/drawdown (calmar) se dégrade avec le stop D1 réel dans 11/16 combinaisons** (recalculé après le refresh du CSV, chiffre corrigé — était "13/16" avant les corrections EXCES-H4/Conflit MTF) — exceptions où le stop D1 réel améliore le ratio : BTC/FAIBLE, BTC/MODERE, ETH/MODERE, ETH/AGRESSIF, ETH/TRES_AGRESSIF. BNB et SOL restent les cas les plus nets où le calmar se dégrade avec le stop D1 réel, sur les 4 profils sans exception.
- Le win rate et le profit factor sont globalement proches entre les deux configurations (BTC/ETH plutôt meilleurs ou stables avec D1, BNB/SOL plutôt légèrement moins bons), sans direction constante unique.
- **Conclusion qualitative inchangée par les corrections successives (P0, EXCES-H4, Conflit MTF)** : le sens du résultat (D1 réel réduit systématiquement retour ET drawdown, dégrade le ratio risque-ajusté dans la majorité des cas) est resté stable à travers toutes les corrections apportées à `backtest_phase2_v7.py` depuis — seule l'ampleur des chiffres bruts et le compte exact des exceptions (11/16 vs 13/16) ont changé.

**Conclusion mesurée, pas supposée** : le stop D1 réel n'améliore PAS la performance risque-ajustée dans la majorité des cas testés avec ce moteur de sizing à risque fixe — l'effet dominant est la réduction mécanique de la taille de position (stop plus loin ⇒ position plus petite ⇒ moins de retour, sans réduction proportionnelle du drawdown). Ce n'est pas un motif pour ne pas l'avoir implémenté (principe acté dans `COUVERTURE_ENSEIGNEMENTS.md` : la performance du proxy ne décide jamais si un élément du corpus doit être implémenté) — l'implémentation reste due et faite ; c'est en revanche un motif légitime pour garder `use_mtf_stop=False` comme réglage par défaut des campagnes de résultats tant qu'aucune analyse plus fine (ex. ajuster `risk_pct` en fonction de la distance du stop, ou ne prendre le stop D1 que lorsqu'il est plus PROCHE que le H4, pas plus loin) n'a été tentée. Ce point reste ouvert.

**Le nom "Extreme Channel" est-il enfin justifié ?** Partiellement seulement, à distinguer explicitement en deux volets :
- **Volet cross-timeframe** ("contexte de l'UT supérieure affiché sur l'UT de trading") : oui, résolu — le stop peut désormais réellement provenir du D1, avec le même mécanisme sans lookahead que le signal.
- **Volet "channel"** (une construction géométrique de canal) : toujours pas justifié — `ctx_support` reste une bande de volatilité (EMA lente − 2×ATR), pas un vrai canal construit (Supports→Apex→Tangente, item déjà distinct et toujours ❌ dans `COUVERTURE_ENSEIGNEMENTS.md`). Ce deuxième volet n'était pas dans le périmètre de cette tâche et reste une lacune séparée.
