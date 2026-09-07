# Validation croisée multi-timeframe réelle (H4 exécution / D1 référence) — lacune comblée

**Question à l'origine** : "les stratégies prennent-elles en compte le timeframe inférieur et supérieur dans leur décision ?" Réponse à ce moment-là : **non**. Vérification par lecture directe du code (`code/backtest_phase2_v6.py`) : `ctx_support = ema_slow - 2*atr` est calculé sur le **même** dataframe que celui tradé (H4 seul ou D1 seul, jamais croisés) — malgré le nom "Extreme Channel" qui laissait entendre un vrai canal de l'unité de temps supérieure. **Correction de documentation** : ce n'était qu'une bande de volatilité locale, pas un canal cross-timeframe. Les seules fois où une vraie logique multi-timeframe avait été testée (Phase 1, `backtest_cascade3.py`) utilisaient l'ancien signal EMA générique — jamais fusionnées avec la lignée v4/v5/v6 (proxy TSI+cycle+structure, régime, risk management corrigé).

## Ce qui est construit (`code/backtest_phase2_v7.py`)
Exécution sur H4, référence/contexte sur D1 : un signal H4 n'est validé que si :
1. Le score proxy_v2 (TSI+cycle+structure) de la **dernière bougie D1 entièrement clôturée** (jointure `merge_asof` sans lookahead) est également ≥2
2. Le régime D1 n'est pas EXCES

## Résultat — le plus uniformément cohérent obtenu à ce jour

| Actif (profil FAIBLE) | Trades | Win rate | Profit factor | Max DD | Retour |
|---|---|---|---|---|---|
| BTC — H4 seul | 1498 | 46,3% | 1,91 | -9,5% | +179,8% |
| BTC — validé par D1 | 520 | **54,0%** | **2,60** | **-7,0%** | +54,9% |
| ETH — H4 seul | 1365 | 46,0% | 2,09 | -12,3% | +247,9% |
| ETH — validé par D1 | 458 | **59,0%** | **3,18** | **-4,3%** | +70,7% |
| BNB — H4 seul | 1209 | 47,4% | 1,89 | -8,0% | +134,7% |
| BNB — validé par D1 | 499 | **51,5%** | **2,12** | **-6,0%** | +49,4% |
| SOL — H4 seul | 1199 | 48,5% | 2,47 | -13,7% | +350,8% |
| SOL — validé par D1 | 341 | **56,3%** | 1,78 | **-5,8%** | +17,9% |

Détail complet (4 profils × 4 actifs) : `phase2_v7_mtf_results.csv`.

**Constat, sur les 4 actifs et les 4 profils, sans exception** : environ 3× moins de trades, win rate systématiquement plus élevé (+5 à +13 points), drawdown systématiquement réduit, profit factor amélioré dans la quasi-totalité des cas (seule exception : SOL, où il baisse légèrement malgré le reste). Le retour cumulé est plus faible (moins d'occasions de composer, cohérent avec 3× moins de trades) — les valeurs extrêmes précédemment suspectes (SOL Très Agressif +23878%) redeviennent nettement plus raisonnables (+75,8% sur ce profil).

C'est le résultat le plus **uniformément** cohérent obtenu dans tout ce projet — pas un mélange d'améliorations et de dégradations selon l'actif, mais une direction constante partout. Ça confirme empiriquement ce que 7 sources indépendantes du corpus affirmaient : trader un timeframe isolément, sans validation croisée, dégrade la qualité du signal.

## Limites documentées
- Toujours un proxy, pas le vrai signal PRO Framework
- Résultats informatifs, pas une validation définitive (principe déjà établi)
- Un seul sens de cascade testé ici (D1 valide H4) — le sens complet à 3 niveaux (Daily/H4/H1) avait déjà été testé séparément avec un résultat négatif (`CASCADE3_H1_EXECUTION_TEST.md`), mais avec l'ancien moteur — à refaire avec le moteur v7 si on veut la comparaison la plus à jour
- N'implémente pas encore la règle exacte "UT+2" (deux niveaux au-dessus) des sources #15/#16 — ici c'est directement le niveau immédiatement supérieur (H4→D1), pas H4→Hebdo
- ~~Le stop "Extreme Channel" reste calculé sur le même timeframe que celui tradé~~ → **comblé, voir section suivante.** Le stop bénéficie désormais de la même jointure cross-timeframe sans lookahead que le signal.

## Correction P1 — le STOP utilise désormais le vrai canal D1 (plus seulement le signal)

**Rappel du problème** (déjà documenté ci-dessus et dans `COUVERTURE_ENSEIGNEMENTS.md`) : jusqu'ici, seul le SIGNAL H4 était validé par le score D1 (via `attach_higher_context`) ; le STOP (`ctx_support = ema_slow - 2*atr`) restait calculé sur le H4 lui-même — malgré le nom "Extreme Channel" qui désigne, dans le corpus (#12/#16, `TRADING_LESSONS_CLUSTERS_PRIX.md`), explicitement *"le contexte de l'UT supérieure affiché sur l'UT de trading"*.

**Ce qui a changé** (`code/backtest_phase2_v7.py`) : `attach_higher_context` transmet maintenant, en plus du score et du régime, le `ctx_support` D1 — via la même jointure `merge_asof` sans lookahead (dernière bougie D1 entièrement close). `run_v7` expose un nouveau paramètre `use_mtf_stop` (défaut `False`, comportement historique inchangé) : à `True`, le stop réel à l'entrée est ce `ctx_support` D1 (niveau de prix absolu, substituable tel quel à `ctx_support` H4 — pas de problème d'échelle, les deux sont des prix, pas des distances).

**Mesure — stop H4 (même UT) vs stop D1 réel, gate MTF activé dans les deux cas, 4 actifs × 4 profils** (détail complet : `phase2_v7_mtf_results.csv`, colonne `stop`) :

| Actif (profil FAIBLE) | Stop | Trades | Win rate | Profit factor | Max DD | Retour | Retour/DD |
|---|---|---|---|---|---|---|---|
| BTC | H4 (même UT) | 520 | 54,0% | 2,60 | -7,0% | +54,9% | 7,84 |
| BTC | D1 réel | 499 | 54,7% | **3,45** | **-2,6%** | +25,7% | **9,88** |
| ETH | H4 (même UT) | 458 | 59,0% | 3,18 | -4,3% | +70,7% | **16,44** |
| ETH | D1 réel | 459 | 58,6% | 3,01 | **-2,2%** | +25,3% | 11,50 |
| BNB | H4 (même UT) | 499 | 51,5% | 2,12 | -6,0% | +49,4% | **8,23** |
| BNB | D1 réel | 498 | 50,6% | 2,04 | **-3,2%** | +18,7% | 5,84 |
| SOL | H4 (même UT) | 341 | 56,3% | 1,78 | -5,8% | +17,9% | **3,09** |
| SOL | D1 réel | 336 | 54,5% | 1,50 | -7,9% | +5,5% | **0,70** |

**Mécanisme identifié (pas une hypothèse — vérifié sur BTC)** : le `ctx_support` D1 réel est en moyenne ~2,7× plus loin du prix que le `ctx_support` calculé sur H4 (distance moyenne 10,1% vs 3,8% du prix ; le D1 est plus éloigné dans 78% des bougies). Le sizing du moteur (`size_frac = risk_pct / stop_pct`, risque fixe en % de l'equity) réduit donc mécaniquement la taille de position quand le stop réel D1 est utilisé — moins d'exposition, donc moins de retour composé, mais aussi (le plus souvent) moins de drawdown, dans une proportion qui varie par actif.

**Résultat honnête, mesuré sur les 16 combinaisons (4 actifs × 4 profils), gate MTF activé** :
- Le drawdown absolu diminue avec le stop D1 réel dans 14/16 cas (exceptions : BNB Très Agressif, SOL Faible, où il augmente légèrement).
- Le retour total diminue systématiquement (16/16) — cohérent avec le sizing plus petit.
- **Le ratio retour/drawdown (calmar) se dégrade avec le stop D1 réel dans 14/16 combinaisons** — seules exceptions où le stop D1 réel améliore le ratio : BTC/FAIBLE et ETH/Très Agressif. SOL est le cas le plus net : le calmar chute d'un facteur ~4-5× avec le stop D1 réel, quel que soit le profil.
- Le win rate et le profit factor sont globalement proches entre les deux configurations (parfois légèrement meilleurs avec D1, parfois légèrement moins bons), sans direction constante.

**Conclusion mesurée, pas supposée** : le stop D1 réel n'améliore PAS la performance risque-ajustée dans la majorité des cas testés avec ce moteur de sizing à risque fixe — l'effet dominant est la réduction mécanique de la taille de position (stop plus loin ⇒ position plus petite ⇒ moins de retour, sans réduction proportionnelle du drawdown). Ce n'est pas un motif pour ne pas l'avoir implémenté (principe acté dans `COUVERTURE_ENSEIGNEMENTS.md` : la performance du proxy ne décide jamais si un élément du corpus doit être implémenté) — l'implémentation reste due et faite ; c'est en revanche un motif légitime pour garder `use_mtf_stop=False` comme réglage par défaut des campagnes de résultats tant qu'aucune analyse plus fine (ex. ajuster `risk_pct` en fonction de la distance du stop, ou ne prendre le stop D1 que lorsqu'il est plus PROCHE que le H4, pas plus loin) n'a été tentée. Ce point reste ouvert.

**Le nom "Extreme Channel" est-il enfin justifié ?** Partiellement seulement, à distinguer explicitement en deux volets :
- **Volet cross-timeframe** ("contexte de l'UT supérieure affiché sur l'UT de trading") : oui, résolu — le stop peut désormais réellement provenir du D1, avec le même mécanisme sans lookahead que le signal.
- **Volet "channel"** (une construction géométrique de canal) : toujours pas justifié — `ctx_support` reste une bande de volatilité (EMA lente − 2×ATR), pas un vrai canal construit (Supports→Apex→Tangente, item déjà distinct et toujours ❌ dans `COUVERTURE_ENSEIGNEMENTS.md`). Ce deuxième volet n'était pas dans le périmètre de cette tâche et reste une lacune séparée.
