# Validation croisée multi-timeframe réelle (H4 exécution / D1 référence) — lacune comblée

**Question à l'origine** : "les stratégies prennent-elles en compte le timeframe inférieur et supérieur dans leur décision ?" Réponse à ce moment-là : **non**. Vérification par lecture directe du code (`code/backtest_phase2_v6.py`) : `ctx_support = ema_slow - 2*atr` est calculé sur le **même** dataframe que celui tradé (H4 seul ou D1 seul, jamais croisés) — malgré le nom "Extreme Channel" qui laissait entendre un vrai canal de l'unité de temps supérieure. **Correction de documentation** : ce n'était qu'une bande de volatilité locale, pas un canal cross-timeframe. Les seules fois où une vraie logique multi-timeframe avait été testée (Phase 1, `backtest_cascade3.py`) utilisaient l'ancien signal EMA générique — jamais fusionnées avec la lignée v4/v5/v6 (proxy TSI+cycle+structure, régime, risk management corrigé).

## Ce qui est construit (`code/backtest_phase2_v7.py`)
Exécution sur H4, référence/contexte sur D1 : un signal H4 n'est validé que si :
1. Le score proxy_v2 (TSI+cycle+structure) de la **dernière bougie D1 entièrement clôturée** (jointure `merge_asof` sans lookahead) est également ≥2
2. Le régime D1 n'est pas EXCES

## Résultat — rejoué avec le moteur causal (P0), chiffres à jour

**Historique de cette section** : le tableau ci-dessous montrait initialement des chiffres calculés avec l'ancien calcul batch (non causal) du cycle Hilbert, signalés obsolètes puis laissés en l'état "à rejouer" pendant le traitement du P1 (stop cross-timeframe, tâche distincte). Les chiffres avec le moteur causal (`compute_cycle_phase_causal`) existaient déjà dans `phase2_v7_mtf_results.csv` (produits lors du rejeu de la section "Correction P1" ci-dessous) mais n'avaient jamais été transcrits ici — corrigé à présent, sans nouveau calcul, juste lecture du CSV déjà à jour.

| Actif (profil FAIBLE, stop H4) | Trades | Win rate | Profit factor | Max DD | Retour |
|---|---|---|---|---|---|
| BTC — H4 seul | 1402 | 39,4% | 1,52 | -14,8% | +81,8% |
| BTC — validé par D1 | 504 | **42,7%** | **1,60** | **-9,1%** | +23,1% |
| ETH — H4 seul | 1363 | 37,1% | 1,49 | -12,6% | +88,2% |
| ETH — validé par D1 | 417 | **45,6%** | **2,40** | **-6,1%** | +55,2% |
| BNB — H4 seul | 1399 | 41,2% | 1,37 | -17,2% | +46,3% |
| BNB — validé par D1 | 544 | **42,1%** | **1,41** | **-12,6%** | +17,0% |
| SOL — H4 seul | 1239 | 38,8% | 1,79 | -21,2% | +182,0% |
| SOL — validé par D1 | 361 | **41,6%** | **1,82** | **-8,7%** | +24,5% |

Détail complet (4 profils × 4 actifs × 2 configurations de stop) : `phase2_v7_mtf_results.csv`.

**Constat révisé (moteur causal) — la direction tient, l'ampleur est bien plus modeste qu'annoncé initialement** : sur les 4 actifs, sans exception, la validation par D1 réduit le nombre de trades (~2,5-3×), améliore le win rate et le profit factor, et réduit le drawdown — la direction du résultat original tient. Mais l'ampleur de l'amélioration, qui semblait spectaculaire avec le calcul batch (+5 à +13 points de win rate), est **beaucoup plus modeste avec le calcul causal** : +0,9 point (BNB) à +8,5 points (ETH) de win rate ; profit factor quasiment inchangé sur BNB/SOL (+0,03 à +0,04) et significatif seulement sur ETH (+0,91) ; le retour cumulé chute fortement partout (cohérent avec l'edge global lui-même surestimé ~4× par le batch, cf. `COUVERTURE_ENSEIGNEMENTS.md` P0).

Ce n'est plus "le résultat le plus uniformément spectaculaire du projet" (affirmation d'origine, à ne plus citer telle quelle) — c'est un résultat qui **confirme la direction** (valider un signal H4 par son contexte D1 aide, sans exception sur les 4 actifs) avec une ampleur bien plus modeste que ce qu'on pensait, cohérent avec 7 sources indépendantes du corpus sur l'intérêt de la validation croisée — mais qui ne suffit plus à lui seul à justifier un déploiement, vu la faiblesse de certains gains (BNB notamment, quasi neutre).

## Limites documentées
- Toujours un proxy, pas le vrai signal PRO Framework
- Résultats informatifs, pas une validation définitive (principe déjà établi)
- Un seul sens de cascade testé ici (D1 valide H4) — le sens complet à 3 niveaux (Daily/H4/H1) avait déjà été testé séparément avec un résultat négatif (`CASCADE3_H1_EXECUTION_TEST.md`), mais avec l'ancien moteur — à refaire avec le moteur v7 si on veut la comparaison la plus à jour
- N'implémente pas encore la règle exacte "UT+2" (deux niveaux au-dessus) des sources #15/#16 — ici c'est directement le niveau immédiatement supérieur (H4→D1), pas H4→Hebdo
- ~~Le stop "Extreme Channel" reste calculé sur le même timeframe que celui tradé~~ → **comblé, voir section suivante.** Le stop bénéficie désormais de la même jointure cross-timeframe sans lookahead que le signal.

## Correction P1 — le STOP utilise désormais le vrai canal D1 (plus seulement le signal)

**Rappel du problème** (déjà documenté ci-dessus et dans `COUVERTURE_ENSEIGNEMENTS.md`) : jusqu'ici, seul le SIGNAL H4 était validé par le score D1 (via `attach_higher_context`) ; le STOP (`ctx_support = ema_slow - 2*atr`) restait calculé sur le H4 lui-même — malgré le nom "Extreme Channel" qui désigne, dans le corpus (#12/#16, `TRADING_LESSONS_CLUSTERS_PRIX.md`), explicitement *"le contexte de l'UT supérieure affiché sur l'UT de trading"*.

**Ce qui a changé** (`code/backtest_phase2_v7.py`) : `attach_higher_context` transmet maintenant, en plus du score et du régime, le `ctx_support` D1 — via la même jointure `merge_asof` sans lookahead (dernière bougie D1 entièrement close). `run_v7` expose un nouveau paramètre `use_mtf_stop` (défaut `False`, comportement historique inchangé) : à `True`, le stop réel à l'entrée est ce `ctx_support` D1 (niveau de prix absolu, substituable tel quel à `ctx_support` H4 — pas de problème d'échelle, les deux sont des prix, pas des distances).

**Mesure — stop H4 (même UT) vs stop D1 réel, gate MTF activé dans les deux cas, 4 actifs × 4 profils, moteur DÉJÀ CAUSAL** (`compute_cycle_phase_causal`, correction P0 intégrée au moment de cette mesure — chiffres les plus à jour du document ; détail complet : `phase2_v7_mtf_results.csv`, colonnes `profile`/`stop`) :

| Actif (profil FAIBLE) | Stop | Trades | Win rate | Profit factor | Max DD | Retour | Retour/DD |
|---|---|---|---|---|---|---|---|
| BTC | H4 (même UT) | 504 | 42,7% | 1,60 | -9,1% | +23,1% | 2,54 |
| BTC | D1 réel | 505 | 42,4% | **2,02** | **-3,1%** | +15,5% | **5,00** |
| ETH | H4 (même UT) | 417 | 45,6% | 2,40 | -6,1% | +55,2% | **9,05** |
| ETH | D1 réel | 418 | 45,0% | 2,41 | **-2,8%** | +20,9% | 7,46 |
| BNB | H4 (même UT) | 544 | 42,1% | 1,41 | -12,6% | +17,0% | **1,35** |
| BNB | D1 réel | 543 | 41,8% | 1,40 | **-5,6%** | +7,0% | 1,25 |
| SOL | H4 (même UT) | 361 | 41,6% | 1,82 | -8,7% | +24,5% | **2,82** |
| SOL | D1 réel | 361 | 41,0% | 1,54 | -3,6% | +6,9% | 1,92 |

**Mécanisme identifié (pas une hypothèse — vérifié sur BTC, indépendant du cycle donc inchangé par la correction P0)** : le `ctx_support` D1 réel est en moyenne ~2,7× plus loin du prix que le `ctx_support` calculé sur H4 (distance moyenne 10,1% vs 3,8% du prix ; le D1 est plus éloigné dans 78% des bougies). Le sizing du moteur (`size_frac = risk_pct / stop_pct`, risque fixe en % de l'equity) réduit donc mécaniquement la taille de position quand le stop réel D1 est utilisé — moins d'exposition, donc moins de retour composé, mais aussi (le plus souvent) moins de drawdown, dans une proportion qui varie par actif.

**Résultat honnête, mesuré sur les 16 combinaisons (4 actifs × 4 profils), gate MTF activé, moteur causal** :
- Le drawdown absolu diminue avec le stop D1 réel dans **16/16 cas**, sans exception cette fois (avec le moteur pré-P0, deux exceptions apparaissaient sur BNB Très Agressif et SOL Faible ; elles disparaissent avec le cycle causal).
- Le retour total diminue systématiquement (16/16) — cohérent avec le sizing plus petit.
- **Le ratio retour/drawdown (calmar) se dégrade avec le stop D1 réel dans 13/16 combinaisons** — seules exceptions où le stop D1 réel améliore le ratio : BTC/FAIBLE, BTC/MODERE, ETH/TRES_AGRESSIF. SOL et BNB restent les cas les plus nets où le calmar se dégrade avec le stop D1 réel, quel que soit le profil.
- Le win rate et le profit factor sont globalement proches entre les deux configurations (BTC/ETH plutôt meilleurs avec D1, BNB/SOL plutôt légèrement moins bons), sans direction constante unique.
- **Conclusion inchangée par la correction P0** : le sens du résultat (D1 réel réduit systématiquement retour ET drawdown, dégrade le ratio risque-ajusté dans la majorité des cas) est resté stable en recalculant avec le cycle causal — seule l'ampleur des chiffres bruts a changé (win rate/PF nettement plus faibles qu'avant P0, cohérent avec l'inflation du cycle batch documentée dans `COUVERTURE_ENSEIGNEMENTS.md`).

**Conclusion mesurée, pas supposée** : le stop D1 réel n'améliore PAS la performance risque-ajustée dans la majorité des cas testés avec ce moteur de sizing à risque fixe — l'effet dominant est la réduction mécanique de la taille de position (stop plus loin ⇒ position plus petite ⇒ moins de retour, sans réduction proportionnelle du drawdown). Ce n'est pas un motif pour ne pas l'avoir implémenté (principe acté dans `COUVERTURE_ENSEIGNEMENTS.md` : la performance du proxy ne décide jamais si un élément du corpus doit être implémenté) — l'implémentation reste due et faite ; c'est en revanche un motif légitime pour garder `use_mtf_stop=False` comme réglage par défaut des campagnes de résultats tant qu'aucune analyse plus fine (ex. ajuster `risk_pct` en fonction de la distance du stop, ou ne prendre le stop D1 que lorsqu'il est plus PROCHE que le H4, pas plus loin) n'a été tentée. Ce point reste ouvert.

**Le nom "Extreme Channel" est-il enfin justifié ?** Partiellement seulement, à distinguer explicitement en deux volets :
- **Volet cross-timeframe** ("contexte de l'UT supérieure affiché sur l'UT de trading") : oui, résolu — le stop peut désormais réellement provenir du D1, avec le même mécanisme sans lookahead que le signal.
- **Volet "channel"** (une construction géométrique de canal) : toujours pas justifié — `ctx_support` reste une bande de volatilité (EMA lente − 2×ATR), pas un vrai canal construit (Supports→Apex→Tangente, item déjà distinct et toujours ❌ dans `COUVERTURE_ENSEIGNEMENTS.md`). Ce deuxième volet n'était pas dans le périmètre de cette tâche et reste une lacune séparée.
