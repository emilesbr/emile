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
ici.

**CORRECTION (8 sept. 2026, rappel direct de l'utilisateur en tant que
directeur)** : *"nous ne nous fions pas aux résultats du Proxy pour décider
d'utiliser ou non la propriété intellectuelle de Philippe, nous l'utilisons
dans tous les cas."* Ce document appliquait jusqu'ici une distinction
("choisir un défaut par performance mesurée n'est pas la même chose que
rejeter un élément du corpus") qui semblait légitime pour de VRAIES
hypothèses d'implémentation (le corpus est silencieux sur le "comment"),
mais qui a été appliquée À TORT à des **règles littérales du corpus** dans
4 des 10 décisions ci-dessous (items 3, 6, 8, 10 — vérifié source par
source, pas supposé, cf. `PLAN.md` pour le détail complet des citations) :
désactivées par défaut sur la seule base d'une contre-performance mesurée
sur le proxy, exactement le raisonnement interdit. **`code/backtest_phase2_faithful.py`**
(nouveau moteur, `run_faithful`) active ces règles SANS CONDITION — c'est
CE moteur, pas `recommended.py` seul, qui doit être considéré comme le
protocole RANGE à utiliser opérationnellement. `recommended.py` reste décrit
ci-dessous tel quel (son propre chiffre de référence n'est pas invalidé, il
documente une combinaison différente, toujours utile comme point de
comparaison), mais **n'est plus "la config à déployer"** — cf. section 5ter
plus bas pour le détail complet de la correction et le résultat honnête
mesuré.

Cette synthèse répond par ailleurs à une question **différente et plus
étroite**, qui elle reste valide : parmi les éléments **génuinement
ambigus** (le corpus ne précise pas comment les appliquer, pas seulement
"ça marche moins bien" — items 4/5 ci-dessous, gate Fibonacci et gate
Andrews Pitchfork), quel réglage par défaut recommander pour un usage futur
(Phase 3) ? Choisir un défaut par performance mesurée reste légitime pour
CES deux-là — exactement la distinction que ce projet continue d'appliquer,
mais restreinte à ce qui est vraiment une hypothèse à nous.

Le moteur qui implémente cette configuration : `code/backtest_phase2_recommended.py`
(+ `code/walkforward_recommended.py`, `code/oos_xrp_recommended.py`,
`code/test_backtest_phase2_recommended.py`, 7/7 tests). Le moteur à utiliser
opérationnellement : `code/backtest_phase2_faithful.py` (cf. CORRECTION
ci-dessus et section 5ter).

---

## 1. Les 10 décisions ON/OFF, avec preuve chiffrée existante citée

| # | Élément | Décision | Preuve citée (déjà mesurée, pas re-testée ici) |
|---|---|---|---|
| 1 | Cycle causal + structure causale (P0/P0-bis) | **ON, non négociable** | Déjà la seule version en production (`proxy_v2.py::add_proxy_v2_score`, `compute_swing_low_confirmed`) — aucune alternative batch n'est proposée par ce document |
| 2 | Gate MTF | **Hebdomadaire seul ("UT+2 strict"), D1 sauté comme gate de tendance** | `phase2_ut2_results.csv` : D1 seul WR 42,4%/PF 1,81/retour moyen +85,2% (446 trades) vs **UT+2 strict WR 42,1%/PF 2,14/retour moyen +133,2%** (428 trades) — meilleur retour ET profit factor que D1 seul, sans réduire l'échantillon autant que "D1 ET Hebdo" (193 trades, PF 2,43 mais retour +64,9% seulement — pas la règle littérale du corpus, cf. `backtest_phase2_ut2.py`) |
| 3 | Stop cross-timeframe réel (`use_mtf_stop`) | **OFF dans CE moteur (`recommended.py`) — ON sans condition dans `backtest_phase2_faithful.py`** | Règle LITTÉRALE (`TRADING_LESSONS_BREAKOUT_RATIO11.md` #12 : *"Stop-loss = clôture la plus basse du canal de tendance de l'UT+1"*), pas une hypothèse — `MTF_CROSS_VALIDATION_H4_D1.md` (dégrade le ratio retour/drawdown dans 13/16 combinaisons, malgré une réduction de drawdown absolu dans 16/16) documentait une contre-performance mesurée, jamais un motif légitime pour ne pas l'utiliser. Cf. CORRECTION ci-dessus/section 5ter |
| 4 | Fibonacci gate | **OFF** | `phase2_fib_results.csv` : dégrade **32/32** configurations (retour moyen -13,8% vs +107,8% baseline) — **hypothèse d'implémentation À NOUS, pas une règle littérale pour CE protocole** : la règle Fibonacci existe bien dans le corpus (23-38%/38-61%) mais pour valider un pullback de TENDANCE, déjà implémentée sans condition dans `trend_table.py` ; l'appliquer EN PLUS comme filtre d'entrée sur la table RANGE est une extrapolation à nous, légitimement réglable par performance mesurée |
| 5 | Andrews Pitchfork gate | **OFF** | `phase2_patterns_results.csv` : dégrade nettement (retour médian 18% vs 212% référence, négatif sur ETH -9,5% à -21,9%) — **hypothèse de gating retenue ici qui est en cause** (le corpus documente le rôle/le chiffre de l'outil, pas comment l'utiliser comme filtre d'entrée), pas une conclusion sur le pattern géométrique lui-même — piste ouverte, non refermée. Légitimement réglable, contrairement aux items 3/6/8/10 |
| 6 | Wall Street (abstention élargissement) | **OFF dans CE moteur — ON sans condition dans `backtest_phase2_faithful.py`** | Règle LITTÉRALE (#3/#4 : *"aucun outil ne fonctionne, arrêter tout"*, abstention TOTALE prescrite, pas une prudence optionnelle — seule la définition NUMÉRIQUE du pattern est une hypothèse, pas le comportement une fois détecté). `phase2_patterns_results.csv` (effet quasi neutre, WR 38,2% vs 38,9%) documentait juste l'absence d'effet mesuré, jamais un motif légitime de ne pas l'activer. Cf. CORRECTION ci-dessus/section 5ter |
| 7 | Canal manuel comme stop | **OUVERT, non combiné pour une raison différente des items 3/6/8/10** | Règle LITTÉRALE elle aussi (construction géométrique Supports→Apex→Tangente, #3), mais mesurée jusqu'ici SEULEMENT sur le timeframe natif H4 (`phase2_patterns_results.csv`) — alors que le stop UT+1 (item 3) exige le canal du timeframe SUPÉRIEUR (D1). Combiner proprement les deux exigerait de reconstruire le canal manuel SUR D1 (jamais fait) et de trancher lequel des deux stops prime en cas de désaccord, ce que le corpus ne précise pas — non résolu ici pour ne pas inventer cette résolution silencieusement (cf. tête de fichier `backtest_phase2_faithful.py`), PAS parce que le backtest le juge "pas strictement meilleur" |
| 8 | Diversification / Cluster Technique | **OFF dans CE moteur — sleeve PARALLÈLE toujours actif par ailleurs (`diversification.py`)** | Règle LITTÉRALE (`TRADING_LESSONS_CLUSTERS_PRIX.md` #16 : *"1% sur la pattern breakout/pullback + 1% sur la pattern de moyenne mobile... jouer les deux"*), pas une hypothèse. `phase2_diversification_results.csv` (effet marginal isolé mesuré) documentait juste un résultat de backtest, jamais un motif légitime de ne pas l'utiliser — ce sleeve tourne de façon indépendante (risque fixe 1%+1%, jamais fusionné dans `recommended.py`/`faithful.py`), cf. `diversification.py` |
| 9 | Capital par palier | **Paramètre, pas une décision ON/OFF de signal** | `capital_tiers.py::effective_sizing`, exposé via `run_recommended(..., capital_eur=...)`. Absent (`None`) → risk_pct du profil choisi, inchangé |
| 10 | +Reverse (table range, TRES_AGRESSIF) | **OFF dans CE moteur — ON sans condition (profil TRES_AGRESSIF uniquement) dans `backtest_phase2_faithful.py`** | Règle LITTÉRALE et SCOPÉE (`RULES_EXTRACTION.md` §3, ligne "Très agressif" uniquement : *"TP100%+Reverse"*). `phase2_v7_reverse_results.csv` (résultat mixte, 3/4 actifs améliorés, BNB dégradé -6,1 pts) documentait une performance mesurée, jamais un motif légitime de ne pas l'utiliser pour ce profil précis. Cf. CORRECTION ci-dessus/section 5ter |

**Hors périmètre DE CE MOTEUR précis (`backtest_phase2_recommended.py`),
mais toujours utilisé ailleurs, sans condition** : la table "trade de
tendance" à 5 étapes (`trend_table.py`) n'est toujours pas intégrée À CE
FICHIER précis — reste structurellement incompatible avec
`position_engine.py` (justifié en tête de `trend_table.py`, une machine à
états différente, pas une question de performance). **Ce n'est PAS parce
que son propre résultat mesuré (`phase2_trend_table_results.csv`) serait un
motif de ne pas l'utiliser** — cf. correction de tête de document : la table
de tendance
EST utilisée, sans condition, via `code/unified_protocol.py` (section 5bis
ci-dessous), qui répond "oui" à la question "les moteurs sont-ils unifiés ?"
— ce fichier (`backtest_phase2_recommended.py`) reste inchangé et continue
de documenter le moteur RANGE seul, pour comparaison, pas parce que la
table de tendance serait optionnelle.

**CORRECTION (10e round de mobilisation)** : ce paragraphe affirmait jusqu'ici
que la table de tendance closait "100% des campagnes en étape Accumulation".
**C'est inexact et l'affirmation a été retirée** : compté par instrumentation
du vrai moteur, c'est vrai pour les profils MODERE/AGRESSIF/TRES_AGRESSIF (39
campagnes chacun, 0 Breakout) mais FAUX pour le profil FAIBLE (30 campagnes,
dont **8 atteignent le Breakout, 5 la Divergence et 1 l'Excès final**) — les
étapes 2 à 5 de la table SONT exercées empiriquement sur ce profil. Cause
mécanique identifiée : FAIBLE a `accum_frac = 0.00`, donc son stop de
protection (qui exige `remaining > 0`) ne peut pas clôturer la campagne avant
le Breakout, contrairement aux 3 autres profils. Ajouté au même round :
`trend_table.py` expose désormais la contrainte "espace libre" MTF avant
breakout (`use_breakout_space_gate`, OFF par défaut, obstacles UT+1 D1 /
UT+2 Hebdo) — règle littérale du corpus, mesurée mitigée à dégradée (1 couple
amélioré, 3 dégradés, 12 inchangés), cf. `PLAN.md` section "10e application".
Elle n'est PAS activée dans `unified_protocol.py` : ce routeur réplique le
dict d'événements de `trend_table.py` sans cette clé et reste donc
bit-à-bit identique — l'étendre au routeur est un choix de configuration
distinct, non tranché ici plutôt que fait en silence.

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

## 4bis. Tentative de validation hors-échantillon élargie, gate MTF ACTIVÉ — recherche de données, résultat honnête : rien d'exploitable trouvé

Reprend explicitement la limite énoncée en section 4 ("l'OOS XRP... ne valide donc
pas le composant gate MTF, qui reste structurellement intestable sur un historique
aussi court"). Objectif de cette tentative : trouver, sur GitHub, une donnée OHLCV
**horaire ou plus fine** pour un actif **jamais utilisé dans ce projet** (ni
BTC/ETH/BNB/SOL/XRP — les 5 actifs déjà mobilisés pour calibrer ou décider
quelque chose), avec assez d'historique pour que le gate Hebdomadaire ("UT+2
strict") converge (`EMA_SLOW=55` semaines) sur un nombre de bougies Hebdomadaires
qui ne soit pas lui-même un artefact de petit échantillon — contrairement aux 53
bougies Hebdo de l'OOS XRP (section 4).

**Recherche menée** (dépôts et requêtes essayés, par ordre) :

1. **Recherche de code GitHub ciblée par nom de fichier** (`filename:`) sur les
   conventions courantes de nommage horaire (`ADAUSDT.csv`, `Binance_LTCUSDT_1h.csv`,
   `Binance_DOGEUSDT_1h.csv`, `Binance_ADAUSDT_1h.csv`, `Binance_DOTUSDT_1h.csv`,
   `Binance_LINKUSDT_1h.csv`) — résultats trouvés, mais soit des fenêtres de
   quelques jours à quelques mois (caches d'appels API ponctuels, pas des dumps
   historiques), soit en réalité des données **journalières** malgré le nom.
2. **Recherche par contenu** (colonnes caractéristiques du format
   CryptoDataDownload : `Volume XXX`, `Volume USDT`, `tradecount`) pour ADA, DOGE,
   LINK, DOT, ETC, TRX, MATIC, XLM, ATOM, XMR — nombreux résultats, mais **tous**
   en résolution journalière (`_d.csv`) ou sur des fenêtres bien trop courtes en
   horaire.
3. **Dépôt cloné et vérifié directement** (comme demandé, `git clone`, pas
   seulement lu via l'API de recherche) : `priyanshux/cryptopy`
   (`https://github.com/priyanshux/cryptopy`, cloné dans
   `/home/user/priyanshux-cryptopy`). Contient bien des CSV horaires réels
   (`CryptoPy/data_hourly/Binance_LTCUSDT_1h.csv`, colonnes klines Binance
   authentiques) pour un actif jamais utilisé ici (LTC) — mais **seulement 3001
   lignes, du 2020-08-01 23:00 au 2020-12-05 00:00 (~125 jours, ~4 mois)**.
   Resamplé en Hebdomadaire, cela donnerait environ 18 bougies — **moins encore**
   que les 53 bougies de l'OOS XRP D1, donc structurellement pire pour le gate
   MTF, pas mieux. Rejeté pour cette raison précise (pas parce que la donnée est
   fausse, mais parce qu'elle est trop courte pour l'usage visé ici).
4. **Dépôt vérifié** : `ireneannx/deeplearning_crypto` — dossier nommé
   `Crypto_data_Hourly/` contenant des fichiers pour ~25 altcoins jamais utilisés
   ici (TRX, LINK, ETC, XLM, ADA, DOGE, ATOM, XMR, MATIC, DOT, etc.), mais
   vérification directe du contenu : les lignes sont espacées d'**1 jour**, pas
   d'1 heure (`2018-04-17` puis `2018-04-18`), et le SHA git du fichier "hourly"
   est **identique** à celui du fichier "daily" correspondant (`Crypto_data_daily/`)
   — le dossier est mal nommé, c'est une copie de la donnée journalière. Rejeté
   (donnée réelle mais pas horaire malgré le nom).
5. **Dépôts `kochlisGit/VIT2` et `iamaryaak/RL-Crypto-Bot`** : très riches en
   altcoins jamais utilisés ici (LTC, ETC, TRX, LINK, XLM, ADA, DOGE, DOT, MATIC,
   ATOM, XMR, EOS, ZEC, DASH, QTUM...), certains avec plusieurs années
   d'historique réel (ex. `HitBTC_ETHUSD_d.csv`/`HitBTC_LTCUSD_d.csv` depuis
   2018) — mais **exclusivement en résolution journalière** (`_d.csv`), aucun
   fichier horaire dans ces dépôts (vérifié : recherche dédiée `"_1h" OR
   "_hourly" OR "_h.csv"` dans `kochlisGit/VIT2`, 0 résultat). Une donnée
   journalière pluriannuelle aurait pu suffire à faire converger un gate
   Hebdomadaire (contrairement au cas XRP), mais cela aurait testé "exécution
   D1 + gate Hebdo", pas la config de référence "exécution H4 + gate Hebdo" —
   délibérément écarté plutôt que substitué en silence, pour ne pas présenter un
   test différent comme la validation demandée.
6. **Dataset Kaggle "G-Research Crypto Forecasting"** (minute par minute,
   2018-2021, 14 actifs dont Litecoin/Ethereum Classic/Cardano/Dogecoin/Monero/
   Stellar/TRON — plusieurs jamais utilisés ici) identifié comme source
   théoriquement idéale (résolution encore plus fine que l'horaire, plusieurs
   années) — mais son fichier `train.csv` (~24 millions de lignes, plusieurs Go)
   n'est **committé sur aucun dépôt GitHub public trouvé** (recherche dédiée sur
   le schéma de colonnes exact `timestamp,Asset_ID,Count,Open,High,Low,Close,
   Volume,VWAP,Target`, 0 résultat) — cohérent avec sa taille (au-delà de la
   limite de fichier GitHub sans LFS) et les conditions de la compétition
   Kaggle ; seuls des notebooks qui le *lisent* depuis un chemin local/Kaggle
   sont indexés, jamais la donnée elle-même.
7. Dépôt local déjà présent dans l'environnement, `/home/user/trade-v1`
   (`data/fetcher.py`) : récupère de la donnée horaire via `ccxt`/Binance en
   direct, mais **aucune donnée committée** (fetcher exécuté à la demande) — pas
   un dépôt de données au sens de cette tâche, et l'exécuter aurait signifié
   aller chercher une donnée fraîche hors GitHub, hors du périmètre demandé ici.

**Résultat honnête** : aucune source horaire (ou plus fine) exploitable —
c'est-à-dire à la fois (a) réellement horaire ou plus fine, (b) pour un actif
jamais utilisé dans ce projet, et (c) avec assez d'historique pour qu'un
resample Hebdomadaire dépasse largement les 53 bougies déjà jugées trop minces
sur XRP — n'a été trouvée après cette recherche. Conformément au principe déjà
appliqué à l'OOS XRP (ne jamais réduire artificiellement un warmup pour faire
semblant qu'un gate fonctionne), **aucun nouveau script `oos_new_asset_recommended.py`
n'a été écrit** : l'écrire sur la seule donnée disponible (LTC horaire 4 mois,
point 3 ci-dessus) aurait reproduit exactement le problème déjà documenté pour
XRP (gate neutralisé faute de convergence), sans apporter d'information
nouvelle — un "non trouvé, documenté" est le résultat honnête ici, pas un
échec de méthode à masquer.

**Ce que cela signifie pour la Phase 3** : la limite énoncée en section 4 reste
entière — le composant gate MTF ("UT+2 strict", décision #2, l'élément le plus
distinctif de la config recommandée) n'a toujours été testé que sur les 4
actifs BTC/ETH/BNB/SOL déjà utilisés pour construire/choisir la config,
jamais sur un actif véritablement hors-échantillon avec une résolution
suffisante. Cette limite est structurelle à l'environnement actuel (absence de
donnée intrajournalière pluriannuelle accessible pour un nouvel actif), pas à
la méthode : si une telle donnée devient disponible (nouveau dépôt GitHub,
export manuel depuis Binance, etc.), la procédure à suivre est déjà écrite
(section 2 ci-dessus + `OOS_VALIDATION_CYCLE_SIGN.md` section 2) et
`run_recommended(..., use_mtf_gate=True)` est déjà prêt à l'accueillir sans
modification du moteur.

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
  (cf. section 4) — **recherche déjà menée** pour une donnée H4/H1 sur un
  actif indépendant (cf. section 4bis) : rien d'exploitable trouvé sur GitHub
  à ce jour (données horaires trouvées soit trop courtes, soit en réalité
  journalières malgré leur nom ; données journalières pluriannuelles trouvées
  en abondance mais insuffisantes pour tester "H4 exécution", pas seulement
  "gate Hebdo"). Cette limite reste donc ouverte, mais sa cause (absence de
  donnée accessible, pas un choix de méthode) et la procédure à suivre si une
  donnée devient disponible sont désormais documentées.
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

## 5bis. Les moteurs sont-ils unifiés dans un seul protocole de trading ? OUI désormais

Ce document notait initialement (section "Hors périmètre" ci-dessus, point 1)
que la table "trade de tendance" à 5 étapes (`trend_table.py`) n'était pas
intégrée à cette config recommandée — deux moteurs séparés, jamais aiguillés
entre eux, réponse honnête à l'époque à la question directe "avons-nous
unifié tous les moteurs de décision dans un même protocole de trading ?" :
non. **Traité depuis** (PLAN.md, section "Protocole unifié — routeur de
régime range ↔ tendance") : `code/unified_protocol.py` fait tourner le
moteur RANGE et le moteur TENDANCE (`trend_table.py`) dans la MÊME boucle
bar-par-bar, chacun gérant ses positions de façon **totalement
indépendante** — pas d'aiguillage exclusif.

**Correction #1 (8 sept. 2026)** : la version initiale de ce routeur imposait
une exclusivité mutuelle par actif (au plus un système ouvert à la fois),
présentée alors comme fidèle au corpus ("un seul contexte à la fois").
L'utilisateur a contesté directement cette restriction, et la vérification
des sources lui a donné raison : rien dans `RULES_EXTRACTION.md` ne
l'impose, et deux sources documentent explicitement le contraire —
`TRADING_LESSONS_CLUSTERS_PRIX.md` (source #16) et
`TRADING_LESSONS_PYRAMIDALISATION.md` (source #15, "positions multiples"
désignées comme le mécanisme même de la pyramidalisation). L'exclusivité a
donc été retirée — RANGE et TENDANCE peuvent être ouverts en même temps sur
le même actif.

**Correction #2 / CONSOLIDATION (même cycle)** : le côté RANGE de ce routeur
utilisait encore `recommended.py` (les 3 règles littérales désactivées à
tort, cf. section 5ter ci-dessous), alors que le côté TENDANCE, lui, était
déjà fidèle au corpus. Incohérence corrigée : le côté RANGE applique
désormais les MÊMES règles que `backtest_phase2_faithful.py`, SANS
CONDITION (stop D1 UT+1, abstention Wall Street, +Reverse scopé
TRES_AGRESSIF) — `unified_protocol.py` devient ainsi LE protocole complet
unique à utiliser opérationnellement, plutôt que deux livrables séparés
mesurant chacun une combinaison partielle. `run_unified`/`decide_now`
prennent désormais un paramètre `d1` supplémentaire.

**Résultat mesuré, honnête, REGÉNÉRÉ après les deux corrections** (BTC/ETH/BNB/SOL
× 4 profils, `code/backtest_phase2_unified_results.csv`, comparé désormais
à `faithful.py` — la bonne référence RANGE, pas `recommended.py`) : 147
campagnes tendance se déclenchent, mais **toutes se referment en étape
ACCUMULATION** (vérifié par spot-check instrumenté BTC/MODERE : 7/7, pas
supposé), cohérent avec le résultat déjà documenté de `trend_table.py` seul.
Conséquence : **10 des 16 combinaisons actif×profil ont un retour total
INFÉRIEUR** à `faithful.py` seul (moyenne **-9,3 points** — nettement moins
que les -19,2 points mesurés à tort contre `recommended.py` avant la
consolidation, une partie de cet ancien écart venait d'une différence de
règles RANGE, pas seulement du coût de la tendance), drawdown moyen **-1,9 pt**
(régénéré après la correction pyramidalisation-régime ci-dessous, était -1,5 pt avant).
**Point de vigilance identifié AVANT la correction EXCES-H4 ci-dessous, très largement résolu APRÈS** :
BNB/TRES_AGRESSIF cumulait 3 effets défavorables (stop D1 large + "+Reverse"
+ campagnes tendance qui n'aboutissent jamais) — retour -42,6%, **drawdown
-72,5%**. **Chiffres régénérés après la correction EXCES-H4** (le gate ne
vérifiait plus le régime EXCES du H4 natif, cf. section "Correction EXCES-H4"
ci-dessous) : retour **+24,5%**, drawdown **-27,1%**. **RE-régénérés après la
correction pyramidalisation-régime** (cf. section dédiée ci-dessous) : retour
**+27,9%**, drawdown **-27,0%**. **RE-régénérés une 3e fois après la correction
Conflit MTF** (cf. section 5quinquies) : retour **+22,0%**, drawdown **-25,2%**
— mouvement modeste dans le même sens à chaque fois. **RE-régénérés une 4e fois
après l'ajout de "Stop Loss = taille du canal"** (cf. section 5septies
ci-dessous) : retour **+12,2%**, drawdown **-30,5%** — cette fois un mouvement
DÉFAVORABLE (stop resserré sur les bougies à canal très large, dont ce couple
concentre une part disproportionnée). Toujours le
profil le plus faible des 16 combinaisons, toujours pas catastrophique (loin du
-72,5%/-42,6% d'origine), mais désormais à surveiller plus attentivement.
**Approfondi par walk-forward (`code/walkforward_unified.py`)**, également
régénéré : l'année 2021, seule responsable du -72,5%/-45,9% agrégé d'origine,
reste à **+5,2% de retour, -9,5% de drawdown** (inchangée par l'ajout du Stop
Loss = taille du canal — chiffres post Conflit MTF ; +6,1%/-8,8% après
pyramidalisation-régime seule, +6,2%/-8,4% après EXCES-H4 seul) ; **la pire
année, désormais 2024**, passe de **-4,0%/-22,6%** (post Conflit MTF) à
**-11,7%/-27,2%** (post Stop Loss = taille du canal) — dégradation notable sur
cette seule année. Conclusion actionnable révisée : **l'exclusion de
BNB/TRES_AGRESSIF reste non justifiée** (2024 à -27,2% reste loin de l'ancien
-72,5%/2021) — conservé comme profil à surveiller en priorité, avec une
vigilance accrue depuis la dernière correction.

**Recherche systématique d'autres combinaisons dangereuses, faite (mobilisation
multi-agents, AVANT la correction EXCES-H4)** : `code/cross_stress_test_faithful_gates.py` (faithful.py +
gate Fibonacci/Andrews) et `code/cross_stress_test_unified_capital_tiers.py`
(unified.py × 3 paliers de capital), walk-forward annuel BTC/ETH/BNB/SOL ×
4 profils. **Aucune nouvelle combinaison catastrophique trouvée** — BNB/TRES_AGRESSIF/2021
restait alors le seul cas. Deux résultats notables, mesurés sur ce cas AVANT
qu'il ne soit résolu par la correction ci-dessous (conservés pour la
traçabilité, ne décrivent plus un problème actuel) : **le capital par palier
ne résolvait pas ce cas** (le palier >100k€, plafond 2%, donnait un résultat
légèrement PIRE malgré un risque effectif 2,5× plus faible — effet de
chemin de l'équité, cas isolé vérifié 1/112 combinaisons testées) ; **le
gate Fibonacci neutralisait incidemment ce cas précis** (dd -60,2%→-5,3%) mais
reste une hypothèse d'implémentation à nous, pas une règle littérale pour la
table RANGE — un effet favorable incident ne le rend pas littéral, aucun
défaut changé.

**Correction EXCES-H4 (mobilisation multi-agents, audit proactif — même
cycle)** : `RULES_EXTRACTION.md` §1 ("Bulle/Excès -> NE PAS TRADER") est une
règle littérale et inconditionnelle sur le régime du marché **réellement
tradé** (H4 natif), pas seulement sur son contexte supérieur. Depuis
l'introduction de la validation croisée D1 (`backtest_phase2_v7.py`), le
gate ne vérifiait plus QUE le régime D1/Hebdomadaire — le régime H4 natif
était calculé mais jamais relu par le gate, régression silencieuse (v6→v7),
pas un choix documenté (preuve : le commentaire de tête de
`backtest_phase2_fib.py` affirme encore "ni le H4 ni le D1 ne doivent être
en régime EXCES" alors que son code ne vérifiait que le D1). **Corrigé dans
les 3 moteurs opérationnellement recommandés** (`backtest_phase2_faithful.py`,
`unified_protocol.py`, `backtest_phase2_recommended.py`) — gate ajoute la
vérification du régime H4 natif. **Non corrigé, documenté comme tel**, dans
les moteurs superseded/comparaison (`v7`, `ut2`, `capital_tiers`, `fib`,
`diversification` Pattern A), cf. `COUVERTURE_ENSEIGNEMENTS.md` et `PLAN.md`
tableau "2e pattern récurrent". Impact chiffré : cf. BNB/TRES_AGRESSIF
ci-dessus, résolu par cette correction, pas recherché comme tel — la
correction suit la fidélité au corpus, l'amélioration du chiffre est une
conséquence.

**Correction pyramidalisation-régime (mobilisation multi-agents, 2e round,
audit proactif — cycle suivant)** : `RULES_EXTRACTION.md` §3 (table Money
Management RANGE) ne contient JAMAIS de cellule "Renfort", à aucune ligne de
profil — contrairement à §4 (table TENDANCE) qui en a systématiquement.
`backtest_phase2_v6.py` traduisait déjà correctement ça en code
(`pyramiding_allowed = regime in ("TENDANCE", "RANGE_TENDANCIEL")`, appliqué
SEULEMENT au renfort, jamais à l'entrée fraîche) — règle perdue
silencieusement au même refactor v6→v7 que EXCES-H4 ci-dessus (même
catégorie de bug : une donnée déjà calculée, `regime_h4`/`feat["regime"]`,
mais jamais relue pour CETTE règle précise). Preuve littérale : le
commentaire de `backtest_phase2_v7.py::gate_extra` dit lui-même "Même gate
pour l'entrée fraîche et le renfort (pas de distinction ici, contrairement à
v6/fib)". Vérifié empiriquement AVANT correction (script de reproduction
utilisant la factory réelle `position_engine.make_open_tranche_fn`, pas
supposé) : sur BTC/ETH/BNB/SOL réels, **25,7% des renforts réellement
ouverts** par `faithful.py`/`recommended.py` l'étaient en régime
RANGE_NEUTRE — exactement ce que v6 bloquait. **Corrigé dans les 3 moteurs
opérationnellement recommandés** (mêmes 3 que EXCES-H4 ci-dessus) — `gate_extra`
distingue désormais entrée fraîche (inchangée) et renfort (`pyramiding_allowed`
réutilisant la donnée déjà calculée). **Non corrigé, documenté comme tel**,
dans les mêmes moteurs superseded que EXCES-H4. Tests dédiés ajoutés (scénario
synthétique à vérité terrain connue, contrôle positif ET négatif) dans les 3
fichiers de test concernés. Impact chiffré : mouvement modeste dans le même
sens que EXCES-H4 sur toutes les métriques déjà citées ci-dessus (BNB/TRES_AGRESSIF,
walk-forward, canal manuel D1, risque agrégé) — cohérent avec un fix qui
restreint légèrement le nombre de renforts plutôt qu'un changement de
direction. Cf. `PLAN.md` tableau "2e pattern récurrent" occurrence #4 pour le
détail complet.

**Sortie "décision live"** (répond à la demande "lire le jeu de données d'un
actif pour en tirer les positions à prendre") : `unified_protocol.decide_now(h1_recent, profile_name, capital_eur=None)`
prend un historique H1 récent (avec `volume`), le resample en interne
(H4 exécution + D1 stop + Hebdomadaire gate) et retourne un dict structuré,
RANGE et TENDANCE rapportés SÉPARÉMENT. Exemple réel (BTC, historique
tronqué au 2020-11-29, profil AGRESSIF — stop désormais D1, nettement plus
large que l'ancien stop H4 natif) :

```json
{
  "range": {
    "action": "HOLD",
    "entry_price": 17816.9,
    "stop_price": 12903.97,
    "targets": {"tranches": [
      {"entry": 17816.9, "stop": 12903.97, "val_px": 21190.09, "conf_px": 21671.09, "lim_px": 23598.18,
       "val_done": false, "conf_done": false},
      "... (2 tranches pyramidées au total)"
    ]},
    "reason": "2 tranche(s) range déjà ouverte(s) au 2020-11-29T00:00:00 -- laisser le moteur gérer Validation/Confirmation/Limite/Invalidation."
  },
  "trend": {
    "action": "NO_POSITION",
    "entry_price": null,
    "stop_price": null,
    "targets": null,
    "reason": "Aucune campagne tendance ouverte et accumulation_active faux au 2020-11-29T00:00:00."
  },
  "regime": "RANGE_NEUTRE",
  "weekly_gate_reliable": false,
  "n_h4_bars": 1999,
  "n_weekly_bars": 48
}
```

Moteur : `code/unified_protocol.py` (`run_unified`, `decide_now`), 14e
moteur de `code/run_all.py` (alias `unified`), `code/test_unified_protocol.py`
(10/10 tests). Limites documentées, pas cachées :
- le capital par palier (`capital_eur`) n'est appliqué qu'au risk_pct du
  moteur RANGE, pas au moteur TENDANCE (jamais mesuré pour la table de
  tendance) — cf. docstring du module (choix U3) ;
- aucun plafond de risque AGRÉGÉ n'est appliqué entre RANGE et TENDANCE
  quand les deux sont ouverts simultanément (chacun garde son propre
  `risk_pct` de profil, ex. jusqu'à 4% simultanés en MODERE) — le corpus
  documente un plafond agrégé explicite (2% max) mais pour une paire de
  patterns différente (diversification statistique, cf. correction
  ci-dessus) ; l'étendre tel quel ici serait une extrapolation non mesurée
  (choix U5).

---

## 5ter. Config FIDÈLE — les règles littérales du corpus, activées sans condition

Corrige une erreur de conception présente dans ce document depuis sa
rédaction initiale (cf. "CORRECTION" en tête de document) : 4 des 10
décisions ON/OFF ci-dessus (items 3, 6, 8, 10) désactivaient par défaut des
**règles littérales du corpus** sur la seule base d'une contre-performance
mesurée sur le proxy — le principe fondateur du projet ("la performance du
proxy ne décide jamais d'utiliser ou non l'IP de Philippe") s'applique à
elles aussi, pas seulement à la table de tendance/diversification déjà
traitées en section 5bis/ailleurs.

**`code/backtest_phase2_faithful.py`** (`run_faithful`) active SANS
CONDITION les 3 règles littérales concernant CE moteur précis (moteur
RANGE) :
1. **Stop cross-timeframe réel UT+1** — le stop utilisé est TOUJOURS celui
   du canal D1 (`ctx_support` D1, jamais le canal H4 natif).
2. **Abstention Wall Street** — bloque TOUJOURS toute entrée fraîche ET
   tout renfort dès que la structure en élargissement est détectée, aucun
   paramètre pour la désactiver.
3. **+Reverse** — activé SANS CONDITION mais UNIQUEMENT pour le profil
   TRES_AGRESSIF (scope littéral du corpus, `RULES_EXTRACTION.md` §3) ; les
   3 autres profils n'ont pas cette mention, donc pas ce comportement.

(La diversification/Cluster Technique — item 8 — reste un sleeve PARALLÈLE
indépendant, cf. `diversification.py`, toujours utilisable sans condition en
plus de ce moteur ; la table de tendance — item "hors périmètre" — est
utilisée sans condition via `code/unified_protocol.py`, section 5bis. Le
canal manuel — item 7 — reconstruit sur D1 et comparé au stop actif, cf.
section 5quater ci-dessous ; les deux lectures restent valides, aucun
défaut changé, pour une raison d'ambiguïté d'implémentation non résolue par
le corpus, PAS une question de performance.)

**Résultat mesuré, honnête, comparé côte à côte à `recommended.py`, RE-régénéré
après les 3 corrections successives (EXCES-H4, pyramidalisation-régime, Conflit
MTF — `recommended.py` lui-même inchangé par ces 3 corrections, cf. sections
dédiées ci-dessus)**
(BTC/ETH/BNB/SOL × 4 profils, `code/backtest_phase2_faithful_results.csv`) :

| Métrique (delta faithful − recommended) | Moyenne sur 16 combinaisons |
|---|---|
| Retour total | **-37,2 points** (15/16 combinaisons dégradées ; 1/16 — BNB/AGRESSIF — légèrement meilleure) |
| Max drawdown | **+11,5 points** (16/16 combinaisons AMÉLIORÉES — drawdown moins profond) |
| Profit factor | +0,09 (globalement stable) |
| Win rate | -0,44 pt (quasi inchangé) |

Lecture honnête, pas maquillée : le stop UT+1 (D1) est mécaniquement plus
large que le canal H4 natif sur la plupart des configurations — à
`risk_pct` fixe, un stop plus large impose une position plus petite
(distance au stop × taille = risque constant), donc un retour cumulé plus
faible ET un drawdown moins profond. Cohérent avec `MTF_CROSS_VALIDATION_H4_D1.md`
(déjà mesuré isolément : "réduction de drawdown absolu dans 16/16"). Ce
n'est PAS un résultat qui remet en cause la décision d'activer ces règles
(actées comme littérales, pas comme un choix de performance) — c'est le
prix mesuré, honnêtement rapporté, de suivre le corpus à la lettre plutôt
que l'optimum local du proxy.

**Note historique, pour ne pas induire en erreur** : la version initiale de
ce document (avant les 3 corrections ci-dessus) rapportait ici une moyenne
de -77,3 points de retour et signalait BNB/TRES_AGRESSIF comme une
combinaison sortant fortement du lot (-122,9 pts de retour, interaction
stop D1 × +Reverse confirmée par ablation à l'époque). **Ce chiffre n'est
plus d'actualité** : BNB/TRES_AGRESSIF (68,3% de retour vs 77,0% pour
`recommended.py`, soit -8,7 pts, et un drawdown MEILLEUR de +13,5 pts)
n'est aujourd'hui plus un cas hors norme — les 3 corrections successives
(en particulier EXCES-H4, qui bloquait auparavant beaucoup moins de
tranches sur ce couple actif/profil précis) ont changé la composition des
trades qui s'ouvrent au point de dissoudre cette interaction. Conservé ici
par souci de traçabilité de la méthode (l'ablation d'alors était correcte
sur les données d'alors), pas comme un résultat encore valide aujourd'hui.

Moteur : `code/backtest_phase2_faithful.py`, `code/test_backtest_phase2_faithful.py`
(5/5 tests), 15e moteur de `code/run_all.py` (alias `faithful`).

**Walk-forward, fait ce cycle** (`code/walkforward_faithful.py`, sur le même
modèle que `walkforward_recommended.py`, jamais fait jusqu'ici sur ce moteur) :
résultat rassurant et STRICTEMENT MEILLEUR que l'ancien walk-forward de
`recommended.py` sur chaque métrique — pire drawdown annuel **-8,2%**
(régénéré après les 3 corrections successives, était -8,1% avant, contre -24,8%
pour `recommended.py`), pire retour annuel **-3,7%** (était -3,3% puis -2,8%,
contre -14,5%), moins
d'années négatives sur BNB (1/7 contre 3/7). Aucune année catastrophique sur
BTC/ETH/BNB/SOL (2020-2026). Cohérent avec le profil "retour réduit mais
drawdown nettement réduit" déjà documenté en agrégé ci-dessus. **OOS XRP, fait (cycle suivant, mobilisation multi-agents)** : `code/oos_xrp_faithful.py`.
Procédure décidée AVANT tout résultat (même discipline que
`oos_xrp_recommended.py`) : XRP D1 (365 barres) devient l'exécution,
Hebdomadaire (53 barres) le stop UT+1 (gardé ACTIF SANS CONDITION —
règle littérale, la désactiver aurait reproduit le raisonnement interdit
par ce projet), Mensuel (13 barres) le gate UT+2 (désactivé — nouveau
paramètre `use_mtf_gate` ajouté à `run_faithful`/`_prepare_features`,
STRICTEMENT ADDITIF, défaut `True` préservant exactement le comportement
existant, 19/19 tests reconfirmés verts après l'ajout, vérifié
indépendamment). **Résultat honnête, non concluant à l'origine (3 trades sur
365 barres) — RE-régénéré après la correction Conflit MTF (cf. section
5quinquies), résultat honnêtement DIFFÉRENT, pas juste ajusté** : le rôle
"D1" de ce moteur (stop UT+1, littéral et inconditionnel) est ici tenu par
l'Hebdomadaire XRP — Conflit MTF vérifie donc, sans condition (comme le
stop lui-même, `use_mtf_gate=False` ne le neutralise pas, cohérent avec sa
portée documentée), si CE niveau est lui-même en range. Sur cette fenêtre
XRP précise, il l'est suffisamment souvent pour faire passer le résultat de
3 à **0 trade sur les 4 profils**. Ce n'est pas un échec de méthode ni un
bug (vérifié indépendamment, causalité confirmée, cf. `PLAN.md`) — c'est la
conséquence honnête d'une règle littérale appliquée sans exception, même
quand elle rend un test déjà mince structurellement encore plus mince.
Conclusion inchangée : cet OOS ne permettait déjà aucune conclusion
statistique à 3 trades, il n'en permet pas plus à 0 — la limite reste la
même (échantillon XRP trop court), pas une nouvelle limite.

---

## 5quater. Canal manuel D1 et risque agrégé — 2 chantiers de la mobilisation multi-agents (cycle suivant)

**Canal manuel D1 (Agent A)** : le stop UT+1 littéral (`faithful.py`) utilise
le canal EMA±ATR H4 remonté en D1 — le canal manuel (Supports→Apex→Tangente,
`manual_trend_channel.py`) est une règle littérale DISTINCTE, jusqu'ici
mesurée seulement sur H4 natif, jamais reconstruite sur D1.
`code/backtest_phase2_faithful_manual_channel.py` (nouveau, réutilise
`_prepare_features`/`_run_core` de `faithful.py` sans modification) construit
cette alternative. Couverture confirmée : 97,77-99,53% des barres D1 selon
actif/année (BTC/ETH/BNB/SOL, walk-forward 2020-2026) — la reconstruction
fonctionne sans adaptation. **Résultat, comparaison directe, RE-régénéré
après les corrections pyramidalisation-régime PUIS Conflit MTF** (hérité
automatiquement via `_run_core` de `faithful.py`, cf. `PLAN.md`)
(`code/backtest_phase2_faithful_manual_channel_walkforward_results.csv`,
112 lignes actif×année) : canal manuel D1 retour total moyen **8,78%**
(9,91% après pyramidalisation-régime, 10,46% avant toute correction) contre
**3,42%** (4,02% puis 5,31%) pour EMA±ATR D1 (stop actif),
mais aussi drawdown moyen plus profond, **-6,05%** (-6,21% puis -6,58%) contre
**-3,24%** (-3,58% puis -4,14%). Ni l'un ni l'autre strictement
meilleur — conclusion inchangée par ces 2 corrections. **Décision suivie : ne PAS remplacer le stop actuel** — le corpus
ne tranche pas lequel des deux stops littéraux prime en cas de désaccord,
et la performance ne doit jamais servir à choisir entre deux lectures
également fidèles du corpus. Les deux restent documentées comme valides,
aucun code de production changé.

**Risque agrégé RANGE+TENDANCE+diversification (Agent B)** :
`code/risk_aggregation_triple_system.py` (nouveau) fait tourner
simultanément, sur le même actif/historique, `unified_protocol.py`
(RANGE+TENDANCE) et `diversification.py` (Pattern A + Pattern B), et
calcule le risque nominal agrégé bougie par bougie — répond à la limite
laissée ouverte en section 5bis. Sa réplique interne du gate RANGE a été
patchée quatre fois (EXCES-H4, pyramidalisation-régime, Conflit MTF, Stop
Loss = taille du canal, cf. `PLAN.md`) pour rester cohérente avec le
vrai `_run_core_unified`. **Résultat honnête, RE-régénéré après la 4e correction**
(`risk_aggregation_full_history.csv` + `risk_aggregation_walkforward.csv`,
BTC/ETH/BNB/SOL × 4 profils) : risque agrégé maximal observé **17,00%**
(BTC/TRES_AGRESSIF, 2020-11-28, inchangé à travers les 4 corrections — le pic
est atteint pendant une phase déjà en régime TENDANCE), très au-dessus du plafond global 5%
documenté (`RULES_EXTRACTION.md` §5) ; 64/112 combinaisons année×actif×profil
(68/112 avant toute correction, 67/112 après pyramidalisation-régime seule,
66/112 après Conflit MTF) le dépassent en walk-forward — amélioration
apportée par "Stop Loss = taille du canal" (capital risqué réduit sur les
bougies à canal très large). **Root cause** : le pyramidage RANGE seul
(3 tranches × 5% = 15% en TRES_AGRESSIF) dépasse déjà le plafond avant toute
combinaison — ce n'est pas la combinaison de systèmes qui casse le plafond.
**Volontairement pas comblé par un plafond inventé** : le corpus ne spécifie
aucun plafond pour cette combinaison précise de systèmes (RANGE+TENDANCE+
diversification simultanés est une architecture du projet, pas une
prescription du corpus, cf. choix U5 `unified_protocol.py`) — documenté
comme limite ouverte, pas silencieuse.

---

## 5quinquies. Conflit Multi-Timeframe — implémenté ; gate Fibonacci RANGE littéral — toujours backlog P0/P1

Un 3e agent avait refait, DE ZÉRO et indépendamment, la classification "règle littérale vs hypothèse d'implémentation" pour tout ce qui est actif dans `faithful.py`/`unified_protocol.py`, contre l'intégralité de `RULES_EXTRACTION.md` et des 17 sources Trading Lessons — 2 trouvailles significatives. **Un round de mobilisation multi-agents suivant (design puis décision puis implémentation) a depuis traité la première.**

### Conflit Multi-Timeframe — implémenté

`TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` (source #5) : *"Conflit Multi-Timeframe (MTF) : L'erreur numéro un. Ne jamais trader une borne de range si un range d'unité de temps supérieure est déjà actif. La structure supérieure prime systématiquement."* — confirmée par sa propre checklist pré-trade, distincte de UT+2 (`TRADING_LESSONS_INDEX.md` ligne 11).

**Décision de conception, 2 points non tranchés littéralement par le corpus, résolus avant code** :
- **Niveau : D1, pas Hebdomadaire.** 3 agents (recherche + second avis indépendant) convergent : caler le gate sur le niveau Hebdomadaire bloquerait ~89% des tranches RANGE actuellement ouvertes (mesuré empiriquement en rejouant `faithful.py` avec `record_trace=True`) — quasi-suppression du système RANGE, incohérent avec le fait que le corpus décrit lui-même RANGE comme le régime dominant (~75% cumulé, §1). Caler sur D1 ne bloque que ~12-19% des tranches actuelles (BTC 13,0%/ETH 7,5%/BNB 19,1%/SOL 3,7%) — effet mesuré, pas disproportionné. Étayé aussi textuellement par `TRADING_LESSONS_TROISIEME_BORNE.md` (source #11 : "Contexte" = UT immédiatement supérieure à l'exécution).
- **Entrée fraîche ET renfort, uniformément.** Aucune source ne distingue les deux cas pour cette règle (contrairement à pyramidalisation-régime, où l'absence littérale de "Renfort" en §3 permettait de trancher précisément) — appliqué via `gate()`, partagé par les deux, plutôt qu'une distinction inventée.

**Implémenté** dans `backtest_phase2_faithful.py`/`unified_protocol.py` (RANGE) : nouvelle clé `regime_d1` (`ctx["D1"]["regime"]`, déjà calculée pour le stop `ctx_support_d1`, jamais lue pour cette règle — même schéma que EXCES-H4/pyramidalisation-régime), gate bloque désormais aussi quand D1 est RANGE_NEUTRE/RANGE_TENDANCIEL. **Non étendu à `backtest_phase2_recommended.py`** (exige une dépendance D1 qu'il ne charge jamais, hors de son périmètre documenté). Tests dédiés (4 nouveaux, scénario synthétique à vérité terrain connue), 19/19 fichiers verts à l'époque de cette implémentation — 21/21 aujourd'hui après le round de vérification adversariale suivant (`test_risk_aggregation_triple_system.py`, `test_no_execution_automation.py` ajoutés, cf. `PLAN.md`).

**Impact chiffré honnête** (mouvement modeste, cohérent avec les 2 corrections précédentes) : `faithful.py` BNB/TRES_AGRESSIF 373→310 trades, retour 76,5%→68,3%, drawdown -17,6%→-15,6% ; `unified_protocol.py` agrégé retour +27,9%→+22,0%, drawdown -27,0%→-25,2% ; walk-forward 2021 +6,1%/-8,8%→+5,2%/-9,5%, 2024 (pire année) -6,2%/-24,4%→-4,0%/-22,6% (légèrement amélioré) ; canal manuel D1 retour 9,91%→8,78%/EMA±ATR 4,02%→3,42% ; risque agrégé max inchangé 17,00%, 67/112→66/112 dépassements. Aucune combinaison ne devient catastrophique. Détail complet : `PLAN.md` section "Correction Conflit Multi-Timeframe".

### Gate Fibonacci RANGE littéral — toujours backlog P0/P1, raison désormais plus précise

`RULES_EXTRACTION.md` §1 donne des seuils Fibonacci LITTÉRAUX conditionnés par régime : Range neutre ≥76,4% + "débordement du contexte" + "signal & triangle de confirmation" ; Range tendanciel ≥61,8% ; Tendance ≥23%. **Vérifié par 3 agents convergents (relecture exhaustive des 17 sources)** : ce n'est pas un simple seuil à faire varier par régime (ce que disait ce document jusqu'ici) — c'est une condition COMPOSITE à 3 volets, dont 2 des 3 n'ont AUCUNE définition utilisable ailleurs dans le corpus. "Triangle" n'a qu'UNE seule mention dans tout le corpus (`TRADING_LESSONS_ZONE_ACCUMULATION.md`, jamais reliée à cette règle), et aucun code du projet ne le détecte. "Débordement" n'est défini que pour un usage DIFFÉRENT (`TRADING_LESSONS_PULLBACK_MATURITE.md` : cible de SORTIE en Excès Final, pas condition d'ENTRÉE). **Risque de confusion supplémentaire identifié** : `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` §5 utilise le même chiffre "76%" mais comme cible de sortie ("Range Neutre = 76% Fibonacci de la vague précédente") — pas comme seuil d'entrée. Implémenter cette règle exigerait d'inventer 2 définitions sans citation, exactement le risque que ce projet refuse. **Décision : ne PAS implémenter ce cycle**, backlog P0/P1 (item 10 de `PLAN.md`), documenté avec sa raison précise plutôt qu'un simple "à ajuster".

## 5sexies. Audit exhaustif du corpus complet (5e round de mobilisation multi-agents) — "Règle des 50%" du Pull-Back complétée, puis corrigée

Réponse directe à "reste-t-il de l'IP de Philippe non implémentée ?" : 3 agents ont relu DE ZÉRO le manuel + les 17 sources vidéo, sans se fier aux classifications déjà écrites — **~18 éléments supplémentaires trouvés**, classés catégorie A (3, probablement pas reproductible — dépend de l'algorithme propriétaire non divulgué, jamais tenté), catégorie B (3, littéral/faible coût/aucune ambiguïté) et catégorie C (10+, littéral mais exige une décision de conception avant tout code — même discipline que Fibonacci RANGE/Conflit MTF ci-dessus). Détail complet, citations exactes, preuves code : `COUVERTURE_ENSEIGNEMENTS.md` section "Audit exhaustif du corpus complet", `PLAN.md` backlog item 11.

**Catégorie B, item (i) traité, PUIS CORRIGÉ (vérification adversariale dédiée, 6e round de mobilisation)** — **"Règle des 50%" du Pull-Back** (`TRADING_LESSONS_PULLBACK_MATURITE.md`, #13) : condition COMPOSITE à 2 volets cumulatifs, retracement ≥23% ET pénétration dans les 50% inférieurs du canal de contexte. `code/fibonacci.py` citait cette règle verbatim depuis sa création mais n'en codait que le premier volet. Comblé : `compute_context_position`/`classify_regle_50` (canal de contexte `CONTEXT_DURATION="15D"`, MÊME définition que `trend_table.py::add_trend_context`/`accum_retracement_frac` — PAS `backtest_phase2_v7.py::prepare`, référence corrigée après vérification : ce fichier ne calcule ni `ctx_high` ni `ctx_low` — recalculée localement pour ne pas créer de dépendance nouvelle, H6 de `trend_table.py` préservé), colonnes `fib_context_position`/`fib_regle_50` sur `add_fibonacci_columns`, câblé comme nouvelle variante `use_fib_regle_50` de `backtest_phase2_fib.py::run_v7_fib` (même pattern que `use_fib_optimal` déjà existant). **Bug réel trouvé et corrigé par la vérification adversariale** : la version initiale ne plafonnait pas le retracement par le haut, supprimant de fait le Red Flag #10 que le fichier documente lui-même comme invalidant au-delà de 61,8% — mesuré : la version buguée était en réalité PLUS LARGE que `fib_favorable` en nombre de bougies (2642 vs 2388 sur BTC H4), contredisant la prétention "beaucoup plus restrictive" affirmée initialement. Plafond `FAVORABLE_MAX` ajouté ; `fib_regle_50` est désormais un sous-ensemble STRICT vérifié de `fib_favorable`. **Nuance sur la distinction avec H7** (corrigée — l'affirmation initiale d'une séparation nette entre les deux règles était une justification a posteriori fragile) : la tension avec l'hypothèse H7 de `trend_table.py` (phrase similaire — "retour min 50% contexte", RULES_EXTRACTION.md §1 — interprétée là-bas comme "recovery_frac ≥ 0.50") N'EST PAS réconciliée ; les deux décrivent très probablement la même étape Pull-Back de la même table compressée. H7 n'est pas modifiée (hors périmètre), mais la tension est désormais tracée dans `trend_table.py` lui-même, à côté de H7.

Résultat mesuré honnête (`phase2_fib_results.csv`, variante `fib_regle_50`, régénéré après correction) : 2 à 13 trades selon l'actif (vs **80-137**, chiffre corrigé — "80-167" cité initialement n'existait dans aucune variante réellement mesurée, ni avant ni après ce cycle) ; rendement absolu négatif sur 15/16 couples actif×profil (seul SOL/FAIBLE positif, +0,5 pt de retour) mais **dégradé vs `baseline_v7` sur 16/16** (delta -21 à -201 pts selon le couple — l'ancienne formulation "dégrade sur 15/16" confondait le signe absolu du rendement avec la comparaison à la baseline, corrigée). **Implémenté intégralement malgré ce résultat** — conforme au principe inviolable du projet : la performance du proxy ne décide jamais si un élément littéralement documenté de l'IP de Philippe doit être implémenté. 3 nouveaux tests à vérité terrain, `code/test_fibonacci.py` désormais 8/8 (dont un dédié au cas `retracement>61,8%` qui aurait révélé le bug initial).

## 5septies. "Stop Loss = taille du canal" — implémenté (catégorie B, item ii, 6e round de mobilisation multi-agents)

Citation exacte, `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` (#5) §5 : *"Dimensionnement du Stop Loss — Règle standard : Stop Loss = taille du canal de tendance. Règle de volatilité (symétrie du risque) : si canal très large → Taille du Canal / 2 = Taille du Stop Loss ET Taille de Position / 2 simultanément (préserve une exposition capital constante)"* — érigée en OBLIGATION par la checklist pré-trade de la même source (*"Dimensionnement : stop loss indexé sur le canal (ajusté selon volatilité) ?"*). La "règle standard" est déjà en place depuis v4 ; seule la "règle de volatilité" manquait.

**4 hypothèses documentées AVANT tout code** (bloc "STOP LOSS = TAILLE DU CANAL", tête de `code/position_engine.py`), aucun seuil chiffré n'existant nulle part dans le corpus pour "très large" :
- **H-Canal-Large-1 (mécanique des deux "/2")** : le stop passe à la moitié de la distance standard, et la position vaut la moitié de ce que la normalisation par le risque donnerait à CE stop réduit — dans un moteur `size_frac = risk/stop_pct`, les deux divisions se COMPENSENT exactement (`size = (risk/(s/2))/2 = risk/s`), donc l'exposition (position notionnelle) reste INCHANGÉE et le capital réellement risqué est divisé par deux. C'est mot pour mot ce qu'affirme la parenthèse de la source. Lecture alternative (les deux "/2" cumulés, exposition ÷2, risque ÷4) écartée car elle contredit cette parenthèse. Vérifié par recalcul manuel indépendant de ce document.
- **H-Canal-Large-2 (quel canal)** : le même "Extreme Channel" EMA(55)±2×ATR(14) qui porte déjà le stop, mesuré au niveau qui porte CE stop (H4 natif ou D1 selon le moteur) — aucune nouvelle définition de "canal".
- **H-Canal-Large-3 (seuil "très large")** : percentile glissant causal p80 de la largeur du canal (`WIDE_PCTL`, `regime_classifier.py`), strictement en-dessous du p95 déjà utilisé pour EXCES (sinon la règle serait vacueuse dans tout moteur qui refuse déjà d'entrer en régime EXCES — vérifié : seules 26-40% des bougies "très larges" sont aussi EXCES). Hypothèse assumée et documentée, jamais inventée en silence.
- **H-Canal-Large-4 (périmètre)** : table RANGE seulement (`position_engine.py`) — la source #5 s'intitule "Anatomie du Range" et son §5 donne des objectifs typés range. `trend_table.py` (table TENDANCE) volontairement hors périmètre : l'étendre exigerait une 2e décision de conception (interaction avec les unités U/H1 et le plafond de campagne H3 propres à cette table) que le corpus ne tranche nulle part.

**Activé sans condition** dans `backtest_phase2_faithful.py`/`unified_protocol.py` (côté RANGE, canal D1) — même statut que le stop UT+1 et l'abstention Wall Street. Mesuré comme banc de sensibilité isolé (`use_wide_channel_halving`, défaut `False`) dans `backtest_phase2_v7.py`.

**Résultat mesuré honnête, y compris défavorable** (recalculé indépendamment depuis les CSV avant/après, pas seulement repris du rapport de l'agent) :
- Banc isolé (`backtest_phase2_v7.py`, un seul paramètre change) : retour moyen -13,1 pts au seuil retenu (p80), dégrade 16/16 couples actif×profil. Effet monotone en fonction du seuil (p70 -14,6 pts / p80 -13,1 pts / p90 -10,1 pts) — imputable à la règle, pas au bruit.
- `backtest_phase2_faithful.py` (activation inconditionnelle, canal D1) : retour **-2,6 pts en moyenne** (recalculé indépendamment : BTC -1,3 à -13,5 pts, BNB -1,8 à -13,5 pts dégradés ; SOL +0,6 à +8,1 pts amélioré ; ETH **exactement inchangé**, ses seules sorties au stop ne tombent sur aucune bougie à canal très large). Drawdown quasi inchangé en moyenne. 33-43% des tranches ouvertes le sont sur une bougie à canal très large — la règle n'est pas vacueuse.
- Effet de bord réel identifié : sur BTC le nombre de trades MONTE (239→256) — un stop plus serré referme plus tôt une tranche dont le stop standard n'aurait jamais été touché, libérant un emplacement de pyramidage plus tôt.
- Impact sur le risque agrégé (favorable) : dépassements du plafond §5 en walk-forward **66/112 → 64/112** (capital risqué réduit sur les bougies à canal large).
- Impact sur BNB/TRES_AGRESSIF (le couple le plus fragile déjà suivi, cf. section 5bis) : DÉFAVORABLE — retour agrégé +22,0%→+12,2%, drawdown -25,2%→-30,5% ; pire année walk-forward (2024) -4,0%/-22,6%→-11,7%/-27,2%. Reste loin du -72,5%/-42,6% d'origine (avant EXCES-H4), mais mérite une vigilance accrue.
- **Seuil p80 non révisé** malgré p90 mesurant mieux (-10,1 pts au lieu de -13,1) — choisir un paramètre de l'IP pour la performance du proxy est exactement le raisonnement que ce projet s'interdit.

**Implémenté intégralement malgré ce résultat globalement défavorable** — conforme au principe inviolable du projet. 10 nouveaux tests à vérité terrain (`test_position_engine.py` 8→13, `test_regime_classifier.py` 10→15). Détail complet, citations exactes, chiffres complets par actif/profil/seuil : `PLAN.md` backlog item 11 catégorie B et section "6e application".

---

## 5octies. "Red Flags d'invalidation précoce" — investigués, PAS implémentés (catégorie C, 9e round)

Aucune décision ON/OFF de ce document ne change : **aucun changement de comportement, aucun CSV régénéré, suite complète 157/157 avant et après**. La section existe pour que le lecteur de ce document sache que la question a été tranchée, et pourquoi.

Citation exacte (`TRADING_LESSONS_ZONE_ACCUMULATION.md` lignes 44-47, exactement 3 puces, vérifiées mot pour mot) : *"## Signaux d'invalidation précoce (« Red Flags »)"* → *"Clôtures **du contexte** sous la MA20"* / *"Retracement profond : clôture maintenue au-delà de 61% de la structure"* / *"Retour au contexte opposé : atteinte de la borne extérieure opposée du range initial"*.

**La prémisse de l'item était fausse et est corrigée** : l'audit du 5e round écrivait *"pas de mécanisme distinct du stop de protection standard"*. `code/position_engine.py::process_tranche` a en réalité **deux** voies de sortie distinctes — (2) l'Invalidation/stop sur la mèche, et (3) la **sortie "flip de signal" tant que ni Validation ni Confirmation ne sont atteintes**, qui est littéralement une invalidation PRÉCOCE et qui porte déjà les règles d'abstention littérales du corpus (EXCES-H4, gate UT+2 Hebdomadaire, Conflit MTF D1) comme conditions de SORTIE et non seulement d'entrée (comportement déjà documenté en tête de `backtest_phase2_faithful.py`). **Mesuré sur les 4 388 trades de la config FIDÈLE** (BTC/ETH/BNB/SOL × 4 profils, historique complet) : les sorties se répartissent en **FLIP 93,8% / LIMITE 3,8% / STOP 2,4%** — l'invalidation précoce est déjà la voie DOMINANTE de ce moteur, ce que ce document ne disait nulle part jusqu'ici.

Verdict par Red Flag (détail complet et chiffres : `PLAN.md` section "9e application", `COUVERTURE_ENSEIGNEMENTS.md`) :
- **Retracement >61% maintenu** : **déjà implémenté deux fois comme plafond d'ENTRÉE** (`trend_table.py::ACCUM_RETRACEMENT_HIGH = 0.61` ; `fibonacci.py::FAVORABLE_MAX = 0.618`, dont le commentaire cite ce Red Flag nommément — et dont la suppression involontaire avait justement été le bug trouvé au 6e round). En faire aussi une SORTIE serait un 3e usage du même chiffre, alors que le corpus l'emploie comme **minimum** d'entrée dans 3 autres passages (inégalité inverse) — même piège que le 76% déjà documenté en §5quinquies. Et *"maintenue"* n'est chiffré nulle part : paramètre à inventer, motif de refus déjà retenu pour le gate Fibonacci RANGE.
- **Retour au contexte opposé** : **doublon bit-à-bit du stop, prouvé NON précoce**. Le stop RANGE est déjà exactement à ce niveau (`min(ctx_support_d1[j], entry*0.999)` — branche `entry*0.999` jamais mordante, 0/4 388) ; le niveau est atteint par 24 trades (0,5%) et dans **24/24 cas la bougie de déclenchement du Red Flag EST la bougie de sortie réelle** : **0/4 388 trade sortirait plus tôt**. La seule variante réellement précoce serait un `ctx_support` relu en direct (stop suiveur), ce qui contredirait la règle la mieux étayée du corpus (interdiction de resserrer avant la Confirmation, sources #12/#13/#15/#16 nommées, #16 s'annonçant lui-même comme la « 5ᵉ/6ᵉ confirmation ») — donc écartée pour cette raison, pas par préférence.
- **Clôtures du contexte sous la MA20** : le SEUL non redondant, et le vrai apport de ce round — une 2e source plus précise, jamais reliée jusqu'ici (`TRADING_LESSONS_CLUSTERS_PRIX.md:50`, #16, section « Règle de Trois »). Reste backlog catégorie C : 2 paramètres à inventer (*"multiples"*, *"marginales"*), un conflit d'UT entre ses 2 sources (#10 dit "du contexte", le tableau de #16 est calé sur *"Unité de Temps de Trading | Horaire (H1)"*), et le piège terminologique des **trois** "moyennes 20 périodes" déjà distinctes du projet (prix/exécution/entrée dans `cluster_technique.py` ; **volume** dans `trend_table.py` H9 ; prix/contexte/invalidation ici). Impact mesuré s'il était codé quand même comme sortie : avant la sortie réelle sur 8,3% (1 clôture) / 6,9% (3 clôtures) des trades, avance médiane 6 bougies H4 — mais avant le stop dans 65% / 54% des 104 sorties au stop, avance médiane 103-214 bougies : pas un no-op.

## 5nonies. "Règle d'or : calculs sur clôtures, jamais sur les mèches" (#15) vs les amplitudes `local_range`/`context_range` — investiguée, PAS implémentée (catégorie C, 12e round)

Aucune décision ON/OFF de ce document ne change : **aucun changement de comportement, aucun CSV régénéré, suite complète 157/157 avant et après**. La section existe pour que le lecteur sache que la question a été tranchée, et pourquoi — l'item était pourtant recommandé comme *"prochain item C, priorité"* par le 8e round.

Citation exacte, relue mot pour mot (`TRADING_LESSONS_PYRAMIDALISATION.md`, #15) : ligne 20, titre de section — *"## Patterns de pyramidalisation (règle d'or : calculs sur clôtures, jamais sur les mèches)"* ; ligne 22 — *"validation au ratio 1:1 (report de l'amplitude du range en clôture)"* ; ligne 39 — *"ratios de validation en clôture"*. Le constat de code est exact aussi : `backtest_phase2_v7.py::prepare` calcule bien `local_range`/`context_range` en `max(high) - min(low)` (5D/15D), projetés en `val_px`/`conf_px`/`lim_px`.

**Ce qui ne tient pas, c'est l'OBJET de la règle** (même classe d'erreur qu'aux 7e et 8e rounds — une transposition que la source n'énonce pas) :

- **L'ambiguïté n'avait pas été vue.** *"En clôture"* admet (a) *"l'amplitude se mesure sur les clôtures"* et (b) *"la validation du 1:1 se constate sur une clôture"*. La lecture (b) est appuyée par la ligne 39 de la même source (*"ratios **de validation** en clôture"*) et par la tournure du titre (*"jamais sur les mèches"* = la formule stock du corpus pour "ne pas valider sur une mèche"). **Elle est déjà implémentée, exactement** : `process_tranche` déclenche Validation/Confirmation/Limite sur `c[i] >= ...` depuis `PHASE2_CORRECTION_CLOSES.md`, document où le 8e round a lui-même rétabli #15 comme l'une des sources. L'item faisait donc porter la même phrase **deux fois, sur deux mécanismes distincts**.
- **La lecture (a) contredit 5 passages du corpus**, tous relus, qui placent le NIVEAU sur les extrêmes et la CLÔTURE comme TEST : #14 `STRUCTURES_ALTERATIONS.md:28` ; #16 `CLUSTERS_PRIX.md:30` (*"bas de clôture **ou** mèche"*, refus explicite de trancher) ; #10 `ZONE_ACCUMULATION.md:38` (*"sous le **point bas** de la 4ème borne"*) ; **#5 `MAITRISE_GRADIENT_RISQUE.md:56`** (*"Objectifs : Range Neutre = 76% Fibonacci de la vague précédente ; Range Vendeur/Acheteur = **débordement du point extrême précédent**"* — **la seule phrase de tout le corpus qui dise comment se mesure un objectif de trade de range, donc l'étape Limite, donc `lim_px`** : elle dit "point extrême") ; `RULES_EXTRACTION.md:41` (*"Confirmation (médiane canal contexte, **clôturée**)"* — "clôturée" qualifie le CONSTAT du franchissement, pas la mesure du niveau).
- **Argument décisif nouveau, mesuré ce round** : #12 `BREAKOUT_RATIO11.md:8`, source du mécanisme codé, assigne à la Validation la finalité *"payer son stop loss"* — donc ~1 R. Mesuré sur BTC/ETH/BNB/SOL H4, `(val_px - entry) / (entry - stop_D1)`, médiane **0,88 / 0,91 / 0,91 / 1,06 en mèches** (la définition en place est **déjà** calée sur le 1:1 exigé) contre **0,69 / 0,71 / 0,72 / 0,85 en clôtures**, part des bougies où R<1 48-54% → 55-62%. La lecture (a) éloigne la Validation du 1:1 : elle **dégrade** la fidélité au lieu de l'améliorer.
- **Requalification vers la table TENDANCE écartée** : `trend_table.py` exclut la pyramidalisation par son H12 et **n'a aucune projection d'amplitude 1:1** (ses étapes sont *"des ÉVÉNEMENTS DE STRUCTURE DE MARCHÉ détectés ..., pas des niveaux de prix fixes issus de l'entrée"*).

**Mesures faites quand même, pour ne pas décider à l'aveugle** : ratio amplitude clôtures/mèches **revérifié personnellement, conforme au 8e round au millième près** (0,786-0,808 sur `local_range` H4 ; 0,862-0,876 sur `context_range` H4 ; 0,552-0,578 / 0,720-0,752 en D1). Impact backtest si (a) était appliquée (4 actifs × 4 profils, un seul paramètre changé) : `backtest_phase2_v7.py` retour +6,2 pts en moyenne mais **10/16 couples dégradés** (moyenne tirée par le seul BTC/TRES_AGRESSIF, +72 pts), drawdown **-2,21 pt (plus profond)**, -10 trades ; **config FIDÈLE retour -0,9 pt**, 9/16 dégradés, drawdown -1,38 pt, -13,6 trades. Signe mixte, drawdown systématiquement plus profond : la performance ne tranche pas — et ce projet s'interdit de trancher là-dessus. **Invariante `val_px <= conf_px <= lim_px` : préservée par construction dans les DEUX définitions** (fenêtre 5D incluse dans 15D), 0 violation sur 55 171 bougies. **Aucun chiffre de fenêtre nulle part dans le corpus** : `LOCAL_DURATION`/`CONTEXT_DURATION` restent l'hypothèse en place.

**Item compagnon tranché en même temps, et pas dans le sens annoncé** : `fibonacci.py::compute_retracement` n'est **pas** un "hybride mèches/clôtures" accidentel — dénominateur = STRUCTURE mesurée sur ses extrêmes (#10:38, #5:56), numérateur = CLÔTURE comme test de position dans cette structure (#11:23 ; #10:46 *"clôture maintenue au-delà de 61% de la structure"*, mot pour mot la formule codée). **Fermé comme CONFORME.**

**Nouveau candidat catégorie C trouvé en chemin** : le coefficient **`1.5`** de `lim_px = entry + 1.5 * context_range` n'a **aucune source** dans le corpus (grep exhaustif) et n'est documenté dans **aucun** des 40 `.md`, alors qu'il est recopié en littéral dans 7 fichiers — à comparer avec `backtest_phase2.py`, dont les multiples d'ATR (`LIMITE_MULT = 3.5`) sont, eux, explicitement documentés comme approximation assumée. Détail complet et portée chiffrée : `PLAN.md` section "12e application", `COUVERTURE_ENSEIGNEMENTS.md`.

---

## 5novies. "Mécanisme d'emboîtement T/T-1" — investigué, PAS implémenté (catégorie C, 11e round)

Aucune décision ON/OFF de ce document ne change : **aucun changement de comportement, aucun CSV régénéré, suite complète 163/163 avant et après**. La section existe pour que le lecteur de ce document sache que la question a été tranchée, et pourquoi.

Citation exacte (`TRADING_LESSONS_ZONE_ACCUMULATION.md:13`, vérifiée mot pour mot) : *"Le succès repose sur la compréhension de la mécanique d'emboîtement des unités de temps (UT). La règle d'or : le **canal de tendance** observé sur votre unité de temps de contexte (T) n'est rien d'autre que la structure interne de l'unité de temps inférieure (T-1)."*

**Deux prémisses de l'item étaient fausses et sont corrigées** : (1) la paraphrase de l'audit du 5e round écrivait *"le canal observé"* et perdait le mot porteur — « canal de tendance » n'est pas un synonyme de « contexte » dans ce corpus mais un objet situé **un cran sous** lui (`TROISIEME_BORNE.md:14-18` oppose *"UT « Contexte »"* et *"UT « Canal de Tendance »"* ; `BREAKOUT_RATIO11.md:7` place le *"canal de tendance de l'UT+1"* sous le *"range de contexte principal"* de l'UT+2), ce qui fait de la phrase une **identité de lecture graphique**, pas une procédure de calcul ; (2) **H11 de `trend_table.py` ne porte pas sur ce sujet** — elle décline la validation par l'UT **supérieure** (*"H4 validé par D1"*), pas la structure de l'UT **inférieure** que l'item réclamait.

**Ce qui est déjà en place, et que l'item ne voyait pas** : la seule traduction opérationnelle de l'emboîtement dans tout le corpus est la projection vers le **bas** — *"Extreme Channel (contexte de l'UT supérieure **affiché sur l'UT de trading**)"* (`CLUSTERS_PRIX.md:12`), *"Stop Loss : placé sous l'Extreme Channel"* (l.28), *"le canal de l'UT supérieure définit la zone de protection technique réelle"* (`BREAKOUT_RATIO11.md:7`). C'est le **stop UT+1 déjà actif sans condition dans la config FIDÈLE** (`ctx_support_d1`, cf. §2/§3 de ce document) : structure détectée sur le H4 tradé, canal lu sur le D1. L'item était donc partiellement déjà couvert — même classe de trouvaille que le Red Flag 3 au 9e round.

**Pourquoi la lecture littérale T-1 n'est pas implémentée (mesuré, pas supposé — BTC/ETH/BNB/SOL, historique complet)** :
- **No-op mathématique sur la seule grandeur numérique concernée** : `ctx_high`/`ctx_low` calculés en H1 puis joints causalement au H4 sont identiques aux valeurs H4 natives sur **100,00%** des barres une fois neutralisé l'artefact de granularité du `shift(1)` (94,6-95,5% avant) — un max/min sur fenêtre **calendaire** est exactement invariant par agrégation de bougies ; et la clôture H1 jointe est celle de la bougie H4 précédente sur 100% des barres. `accum_retracement_frac` ne porte donc aucune information T-1.
- **Gate additif inerte bit-à-bit** : exiger en plus une « structure T-1 mature » laisse les déclenchements Accumulation à 7/7, 9/9, 16/16, 8/8 — **écart 0 sur 4/4 actifs** (`n_borders` en H1 vaut 32-34 au minimum sur les barres candidates contre un seuil `MIN_BORDERS=3`).
- **Dans la direction que le corpus prescrit, incompatible avec H3 du moteur de tendance** : un stop posé sur le canal D1 passe de 1,20-2,26% à 14,75-19,88% de distance (×8,6-14,6), ce qui fait tomber le plafond de campagne de H3 (5% de risque) de 2,2-4,2 fois U à **0,25-0,34** — les 4 profils s'écrasent sur le même plafond et la table de money management §4 (Renfort +25/+50/+100/+150/+200%) devient inexprimable. `position_engine.py` (donc la config FIDÈLE de ce document) échappe à ce problème car il dimensionne chaque tranche indépendamment (`risk_pct / stop_pct`), sans plafond cumulé de campagne — c'est pourquoi `ctx_support_d1` y fonctionne sans dégât. Utiliser le canal D1 comme référence du **rejet** de canal ferait par ailleurs tomber les déclenchements de 7/9/16/8 à **0/0/0/3**.

**Reste backlog catégorie C, requalifié en deux items mieux étayés** : (1) le `ctx_support` de `trend_table.py` n'est **pas** l'« Extreme Channel » du corpus (bande `ema_slow - 2*ATR` de l'UT tradée au lieu du contexte UT+1 ; écart médian mesuré 7,4-12,7%) — soit porter le stop UT+1 ET redéfinir H1/H3 pour que la table §4 reste exprimable, soit renommer honnêtement la bande H4 ; (2) tension jamais consignée entre `ZONE_ACCUMULATION.md:18` (*"utilise la structure de l'UT inférieure pour valider"*) et `TROISIEME_BORNE.md:9/18` (*"inexistante et non-avenue"*, *"« bruit » dès qu'une borne supérieure est détectée"*). Détail complet : `PLAN.md` section "11e application", `COUVERTURE_ENSEIGNEMENTS.md`.

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
- **Protocole unifié (routeur range ↔ tendance)** : cf. section 5bis
  ci-dessus, `code/unified_protocol.py`, `code/test_unified_protocol.py`
  (6/6 tests), `PLAN.md` section "Protocole unifié".
- **Point d'entrée pipeline** : `python code/run_all.py --only recommended`
  (alias `recommended` de `code/run_all.py`, 13e moteur du pipeline) ou
  `python code/run_all.py --only unified` (alias `unified`, 14e moteur).
