# Reverse-ingénierie quantitative du canal de "contexte" — 1ère mesure chiffrée

**Source** : 5 captures d'écran fournies directement par l'utilisateur (pas communautaires cette
fois), TradingView, ETHUSD, montrant les **VRAIS indicateurs PRO Framework (v5.2)/PRO Momentum
(v5.2)** de Philippe Roux sur 4 unités de temps (1h, 4h, 1D, 1M — cette dernière avec le
label "CONTEXT" explicite) plus une capture (1D, BITSTAMP, auteur "PrnMarco") affichant la légende
complète de l'indicateur avec ses paramètres numériques ET une ligne de valeurs de plots en clair.
Usage strictement personnel (cf. `CLAUDE.md`). Aucune image stockée dans ce dépôt, seule la mesure
qui en est tirée.

**Contexte de la démarche** : suite à la question directe de l'utilisateur (*"peux-tu mesurer
l'écart entre les prix pour le déduire ?"*), et après avoir expliqué qu'une simple lecture visuelle
ne suffit pas, ce round a utilisé une méthode plus rigoureuse — analyse programmatique des pixels
des captures (calibration prix↔pixel via les libellés d'axe, détection du remplissage gris du canal
de contexte) plutôt qu'une estimation à l'œil. Méthodologie et limites documentées ci-dessous pour
que la mesure soit reproductible et son incertitude honnêtement bornée.

## 1. Finding factuel n°1 : les paramètres réels de l'indicateur, lus en clair

La capture "PrnMarco" affiche la légende complète : *"PRO Framework (v5.2) (Expert (Advanced
Risks), 1, 20, 2)"* et *"PRO Momentum (v5.2) (Beginner (Range), PRO Momentum (x), 14, 5, 0)"*.
Ce sont les valeurs RÉELLES des `input()` de l'indicateur PineScript pour ce préréglage — pas une
supposition. Trois nombres pour PRO Framework (`1, 20, 2`), trois pour PRO Momentum (`14, 5, 0`).

## 2. Méthode de mesure pixel↔prix (image 1D "CONTEXT", ETHUSD, batgen112, publiée 30 nov. 2024)

- Calibration axe des prix : détection programmatique (Python/PIL/numpy) de la position verticale
  (en pixels) de chaque libellé de prix affiché sur l'axe droit (4 600 → -100, pas de 200$),
  donnant une échelle linéaire fiable ≈ 200$ / 48 px (vérifiée cohérente sur 15 libellés
  consécutifs).
- Calibration date : la bougie la plus à droite du graphique correspond, via l'en-tête affiché sur
  la capture elle-même (*"Ethereum / U.S. Dollar · 1D · INDEX  O3,594.05 H3,727.40 L3,572.31
  C3,660.95"*, publié le 30 nov. 2024), à cette date précise — confirmé de façon croisée : notre
  propre donnée OHLCV réelle (Binance Futures, `data/processed/ETHUSDT_1h_processed.csv` resamplée
  1D) donne un close de 3 705,73 $ ce même jour, à 1,2% de l'écran (écart attendu, indices/bourses
  différents : la capture utilise un "INDEX" agrégé, pas Binance seul).
- Détection du remplissage gris du canal de "contexte" : masque de couleur (pixels gris clair,
  195 < RGB < 245, canaux quasi égaux) appliqué à une colonne de pixels juste avant le bord droit
  du graphique (zone la plus stable, aucune ligne de tendance manuelle ne la traverse) ; la plus
  grande plage verticale continue de pixels gris donne le haut et le bas du canal.

**Résultat mesuré, au 30 nov. 2024** : canal de contexte = **[2 846 $ ; 3 312 $]** (largeur
≈ 466 $), le prix de clôture réel (3 660-3 706 $ selon la source) se trouvant AU-DESSUS de ce
canal — cohérent avec le label "PRICE OK"/rupture visible sur la capture.

## 3. Comparaison avec un candidat calculé sur nos propres données réelles

Hypothèse testée : canal = `SMA(close, 20) ± k × ATR(20)` (le "20" du triplet `(1, 20, 2)"`
correspondrait à la période de la moyenne mobile de référence). Calculé sur
`data/processed/ETHUSDT_1h_processed.csv` resamplé en 1D, au 30 nov. 2024 :

| Grandeur | Valeur mesurée (capture) | Valeur calculée (donnée réelle) | Écart |
|---|---|---|---|
| Borne HAUTE du canal | 3 312,5 $ | `SMA20` = 3 314,80 $ | **+0,07%** |
| Borne BASSE du canal | 2 845,8 $ | `SMA20 − 2×ATR20` = 2 919,50 $ | +2,5% |
| Borne BASSE du canal | 2 845,8 $ | `SMA20 − 2,5×ATR20` = 2 820,70 $ | −0,9% |

**Lecture honnête** : la borne HAUTE du canal correspond quasi exactement (0,07% d'écart) à une
simple moyenne mobile 20 périodes du close — cohérent avec le "20" confirmé en clair dans la
légende de l'indicateur (section 1). C'est la première preuve chiffrée, pas une supposition, que
la moyenne mobile de référence du "contexte" a une période proche de 20. La borne BASSE est dans le
bon ordre de grandeur (multiplicateur ATR entre 2 et 2,5×) mais ne colle exactement à AUCUN
multiplicateur rond testé (1 / 1,5 / 2 / 2,5 / 3, SMA-ATR ou ATR façon Wilder) — le "2" du triplet
`(1, 20, 2)` pourrait être ce multiplicateur, ou porter sur autre chose (ex. une période ATR
différente du "20", un paramètre de lissage, ou même s'appliquer à un SEUL côté du canal — la
capture 4h/1M laissait déjà deviner un tracé asymétrique, une moyenne mobile bleue distincte du nuage
gris, non recoupée précisément dans ce round).

## 4. Tentative de corroboration sur d'autres points du MÊME graphique — non concluante, PAS un signal contre l'hypothèse

Le même protocole appliqué à des zones plus anciennes du graphique (avril-juin 2024, canal de
contexte mesuré entre 3 avril et juillet 2024 environ, dates déduites d'une échelle jours/pixel
constante ancrée sur le 30 nov. 2024) donne des écarts de 20 à 40% par rapport au `SMA20` calculé —
en apparence contradictoire avec la section 3. **Mais** : visuellement, ces zones du graphique sont
traversées par les lignes de mesure manuelles de l'utilisateur (les segments "91 bars (364,86%)"/
"21 bars (-49,65%)"), qui contaminent le masque de détection de gris (le nuage de contexte n'est
plus isolable proprement à ces endroits). **Conclusion honnête : ni confirmé ni infirmé sur ces
points-là** — la contamination empêche une mesure fiable, ce n'est pas une preuve que l'hypothèse
SMA20 est fausse ailleurs sur le graphique, juste que ce round n'a qu'UN SEUL point de mesure propre
(30 nov. 2024).

## 5. Ce que ce round NE fait PAS

**Aucun changement de code.** `regime_classifier.py` reste un proxy EMA±ATR jamais recalibré sur
cette base — un seul point de mesure corroboré, même à 0,07% de précision, reste une hypothèse
(`H-Context-MA20`), pas une validation. Le principe du projet ("jamais coder à partir d'un exemple
isolé sans corroboration") s'applique ici comme pour les nuances communautaires (`docs/NEUNEU_
COMMUNITY_OBSERVATIONS.md`) — la seule différence est que cette fois la preuve est un nombre mesuré
avec une précision vérifiable, pas une phrase qualitative.

**Prochaine étape concrète, proposée à l'utilisateur** : fournir 1-2 captures supplémentaires
montrant un plateau du canal de contexte NON traversé par des lignes de mesure manuelles, avec
l'en-tête OHLC visible (comme la capture "PrnMarco"/"batgen112" ici) pour permettre un nouvel
ancrage date/prix propre — idéalement sur un autre actif/une autre période, pour éliminer le risque
que ce 30 nov. 2024 soit une coïncidence statistique. Si 2-3 points indépendants confirment
`SMA20` pour la borne haute, ce sera suffisamment corroboré pour envisager de recalibrer
`regime_classifier.py` (round séparé, avec sa propre mesure de non-régression).

## 6. Hypothèse ouverte, nommée pour référence future

**H-Context-MA20** : la borne supérieure du canal de "contexte" de l'indicateur PRO Framework
correspond à une moyenne mobile simple 20 périodes du close (période confirmée en clair par la
légende de l'indicateur, valeur numérique confirmée à 0,07% par mesure d'image sur un point daté et
recoupé avec nos données réelles). Le multiplicateur/formule exacte de la borne inférieure reste
non déterminé (candidat : 2 à 2,5 × ATR(20), aucun multiplicateur rond ne collant exactement).

## 7. 2ème lot de captures (9 images, dont 4 nouvelles) — le 2e point NE corrobore PAS proprement `H-Context-MA20`

Suite directe à la demande "prochaine étape" de la section 5. Nouvelles captures : ETHUSD 1M (INDEX,
historique complet 2015-2033), Market Cap BTC Dominance 1W (CRYPTOCAP, batgen112), **BTCUSD 15 min
(BITSTAMP, "Raxells", publiée 27 juil. 2024) avec un label "CONTEXT" explicite pointant UNE valeur
précise de l'échelle de prix**, BTCUSD 1M (INDEX, historique complet depuis 2010), ETHUSD 15 min (FX)
avec un panneau multi-UT inédit. Les 4 autres images du lot sont des DOUBLONS des captures déjà
analysées en section 2-4 (1h/4h/1M/1D ETHUSD Binance) — pas réanalysées.

**Mesure faite, méthode identique (recoupement OHLC contre notre donnée réelle avant tout calcul)** :
la capture BTCUSD 15 min affiche un en-tête OHLC exact (*"O64,562 H64,658 L64,448 C64,578"*) et une
échelle de prix où le rang étiqueté **"CONTEXT" vaut 63 968,1** — cette fois-ci un **rang unique**
de l'échelle, pas une paire haut/bas comme la section 2 (nuance à noter : "CONTEXT" ne désigne donc
pas toujours un canal à deux bornes — parfois une seule valeur). Bougie identifiée dans
`data/processed/BTCUSDT_15m_processed.csv` par recherche du plus proche OHLC (2024-07-18 13:45,
écart cumulé O+H+L+C = 57$ sur des prix ~64 500$, soit ~0,02% par valeur — match plausible,
BITSTAMP vs Binance Futures).

**Résultat, rapporté SANS filtrer dans le sens de l'hypothèse déjà avancée** :
- `SMA(close, n)` sur le M15 natif, balayage exhaustif `n` de 3 à 99 : **aucune période ne descend
  sous 0,9% d'écart** avec 63 968,1 (meilleure = n=88, +0,905%) — pas de période courte (proche de
  20) qui colle.
- `SMA20` sur H1/H4/D1 (resamplés depuis notre donnée réelle) : **0,98% / 0,54% / -6,05%** d'écart
  — aucun ne s'approche du 0,07% obtenu section 3.
- Le close BRUT du D1 en cours (63 959,9$, sans aucune moyenne) est à **0,013%** de 63 968,1 — un
  match trompeusement parfait, mais jugé **probablement une coïncidence, pas une confirmation** :
  durant cette fenêtre (mi-juillet 2024), BTC évoluait dans un intervalle étroit, donc n'importe
  quelle référence de prix récente (clôture de la veille, dernier plus haut, etc.) tombe
  mécaniquement à moins de 1% du prix courant — une hypothèse aussi peu contraignante ("context =
  dernier close") ne constitue pas une corroboration sérieuse au sens où `SMA20` l'était section 3
  (là, l'écart était minime alors que l'hypothèse était plus spécifique/moins triviale).

**Conclusion honnête, sans arrondir dans le sens souhaité** : ce 2e point **n'apporte PAS la
corroboration recherchée** pour `H-Context-MA20`. Ce n'est pas non plus une réfutation ferme — la
mesure porte sur une UNITÉ DE TEMPS différente (15 min vs 1D), un ACTIF différent (BTC vs ETH), et
la capture ne montre qu'un rang de prix isolé sans le nuage gris complet à comparer (contrairement à
la section 2) ; il est possible que "contexte" désigne une grandeur différente selon le contexte
d'affichage (peut-être une UT de référence encore différente, un mode de calcul propre au
préréglage "Beginner (Range)" de cette capture communautaire vs "Expert (Advanced Risks)" de la
section 2-3, ou une composante non capturée par une simple SMA). `H-Context-MA20` reste une
hypothèse À UN SEUL point corroboré (section 3), ni renforcée ni infirmée par ce round — pas
suffisant pour toucher `regime_classifier.py`, ni pour l'abandonner.

**Nouveau, hors périmètre "contexte"** : la capture ETHUSD 15 min (FX) montre un panneau multi-unité
de temps inédit (1M/1W/1D/4H/1H/15m/3m/1m), chaque ligne affichant un pourcentage ET un score
`dev` (ex. *"4H : -75,7% / -1,74 dev"*, *"15m : -99,9% / 0,05 dev"*), avec un fond de case rouge
sombre ou gris selon la ligne — vraisemblablement l'outil "Pro Alerte" déjà mentionné (jamais vu en
action) par la communauté (`docs/NEUNEU_COMMUNITY_OBSERVATIONS.md` section 2.9). Aucune légende
n'explique ce que "%"/`dev` représentent exactement (pas de bulle d'aide visible sur la capture) —
noté pour mémoire, pas exploitable sans une capture montrant le survol/la légende de l'outil.

**Ce que ce round NE fait PAS** : toujours aucun changement de code — le principe "jamais coder sans
corroboration suffisante" s'applique dans les deux sens : ne pas ignorer un résultat qui ne va PAS
dans le sens espéré autant qu'on ne code pas sur un seul résultat favorable. Prochaine étape
inchangée : d'autres captures avec plateau de contexte propre ET en-tête OHLC visible, idéalement
sur la MÊME UT/le même actif que la section 2-3 pour départager si "contexte" varie selon le
préréglage de l'indicateur (Beginner/Intermediate/Expert × Range/Trend/Advanced Risk, nuance déjà
notée dans `docs/NEUNEU_COMMUNITY_OBSERVATIONS.md` section 2.5).

## 8. 3e lot (6 captures, actions/forex hors périmètre crypto du projet) — enseignements structurels, aucune mesure chiffrée possible

Nouvelles captures fournies par l'utilisateur, hors du périmètre BTC/ETH/BNB/SOL de ce projet
(Sodexo SA en hebdomadaire ET mensuel, Euronext Paris ; Microsoft Corp. hebdomadaire, NASDAQ,
publiée par le compte "PRO_Indicators" lui-même ; NEC Corporation hebdomadaire, TSE ; USDJPY 15 min,
FXCM). **Aucune mesure quantitative recoupée contre nos propres données réelles n'est possible
ici** — ce projet n'a QUE de la donnée crypto (`data/processed/`) ; ces 4 instruments (actions
JP/US/FR, forex) sont hors périmètre par construction (`CLAUDE.md`). Enseignements purement
structurels/qualitatifs :

- **"CONTEXT" confirmé une 3e fois comme valeur UNIQUE (pas toujours une paire haut/bas)** : sur la
  capture USDJPY 15 min, le tag "CONTEXT" pointe une seule ligne pointillée grise, alignée sur le
  rang "159,0" de l'échelle des prix — même lecture qu'au 52e round (BTC 15 min), sur un 3e type
  d'instrument (forex). Style visuel différent de la capture ETH 1D (51e round, un NUAGE gris
  rempli) : ici une simple ligne pointillée fine — indice que "contexte" a possiblement DEUX modes
  de représentation graphique (bande remplie sur UT lentes, ligne fine sur UT rapides/intraday),
  pas nécessairement deux définitions différentes.
- **Cohérence structurelle des légendes entre préréglages différents, jamais vérifiée jusqu'ici** :
  la légende PRO Framework affiche sensiblement la MÊME structure de positions sur Sodexo Weekly
  (préréglage *"Expert (Advanced Risks)"*, valeurs `0,0 / 0,0 / 42,3 / 58,4 / 64,7 / 57,7 / 38,5 /
  34,5 / ⌀ / 48,1(rouge) / 55,3(gras) / 35,7 / 74,9 / ⌀ / 50,1 / ⌀ / 45,2 / 51,2 / 56,1 / 60,9 /
  66,9 / ⌀`) et sur NEC Weekly (préréglage *"Intermediate (Trend)"*, valeurs `0,0 / 0,0 / 3 774,6 /
  5 104,0 / 5 433,6 / 5 016,8 / 3 796,5 / 3 516,0 / ⌀ / 4 406,6(rouge) / 2 520,1(gras) / ⌀ / ⌀ / ⌀ /
  ⌀ / 4 419,4 / ⌀ / …`) : positions 1-2 toujours `0,0`, position 9 toujours `⌀`, position 10
  toujours colorée en rouge, position 11 toujours en gras — **l'ORDRE des grandeurs plottées est
  stable quel que soit le préréglage/l'actif**, seul le préréglage change le CALCUL sous-jacent, pas
  la structure de sortie. Utile pour une future tentative de mapping position→nom si une capture
  montrant le "Data Window" (légendes nommées) apparaît un jour.
- **Sur Sodexo Weekly, une paire resserrée autour du prix courant** (58,05€) : positions 4 et 6
  (58,4 / 57,7, largeur 0,7€ soit ±0,6%) contre les autres valeurs bien plus éloignées (42,3 / 64,7
  / 38,5 / 34,5). Piste plausible pour "contexte serré" (un canal local, pas la bande large) — mais
  **non vérifiable** : pas de donnée Sodexo dans ce dépôt, et une seule capture ne suffirait de
  toute façon pas à corroborer (même principe qu'aux sections 4/7).
- **Nouveau terme, jamais rencontré dans les 6 sources précédentes** : *"3BR en retard"* (Sodexo
  Monthly) — la 3ème borne semble pouvoir être qualifiée de "en retard" (délai/tolérance de
  reconnaissance temporelle), une nuance de timing non documentée ailleurs. Aucun chiffre associé,
  noté pour mémoire.
- **Le panneau multi-UT (%, vu au 52e round avec un score `dev` sur ETH) réapparaît sur Microsoft
  Corp., PUBLIÉ PAR LE COMPTE OFFICIEL "PRO_Indicators" lui-même** (donc pas une capture
  communautaire tierce — plus proche de la source), mais SANS colonne `dev` cette fois (1M 74%,
  1W -99,6%, 1D 54%, 4H 95,4%, 1H 92,6%, 15m tronqué ~-99%) — confirme que le pourcentage est
  probablement une variante d'oscillateur BORNÉ (proche de ±99% aux extrêmes, jamais au-delà),
  conceptuellement proche d'un rang percentile — cohérent avec l'approche déjà utilisée dans
  `regime_classifier.py` (percentiles glissants), mais aucune formule exacte lisible. La couleur de
  fond de la valeur (gris/rose/bleu) ne suit PAS une règle simple de signe (74% positif = gris,
  95,4% positif = bleu, -99,6% négatif = rose, 54% positif = gris) — encodage encore inconnu.

**Ce que ce round NE fait PAS** : aucune mesure chiffrée contre nos données (hors périmètre crypto),
donc aucune corroboration ni infirmation possible de `H-Context-MA20` ici — uniquement des
enseignements structurels/qualitatifs, comme pour les captures communautaires. Aucun changement de
code.

## 9. 4e lot (4 captures ETH, retour au périmètre crypto) — auto-correction méthodologique, et `H-Context-MA20` désormais AFFAIBLIE, pas confirmée

4 nouvelles captures ETH (Binance 1h live, Bitfinex 1h/4h datées "Nash0" 29-30 avr. 2026, et
CRYPTO 4h live avec un 2e indicateur jamais vu : "PRO Financials (v1.0)"). Deux d'entre elles
affichent une légende PRO Framework COMPLÈTE et non tronquée (14-22 valeurs numériques par bougie),
une opportunité inédite de tester `H-Context-MA20` sur un préréglage IDENTIQUE à celui du 51e round.

**Auto-correction méthodologique, à documenter explicitement pour ne pas répéter l'erreur** : une
première passe a comparé les 14 valeurs de la légende ETH 1h (bougie identifiée dans notre donnée
réelle, `ETHUSDT_1h_processed.csv`, 2026-02-03 22:00, écart OHLC cumulé 4,5$ soit ~0,05%) contre
**toutes** les périodes de SMA/EMA de 2 à 300 — et a semblé « trouver » une période quasi parfaite
(< 0,05% d'écart) pour CHACUNE des 14 valeurs. **Ce n'est pas une preuve** : sur une fenêtre de 300
périodes testées pour une grandeur qui varie de façon lisse et quasi monotone avec la période, il
est statistiquement presque garanti de trouver une période qui approche n'importe quelle valeur
cible à moins de 0,05% — un artefact de recherche non contrainte (proche du "p-hacking"), pas une
corroboration. Rejeté comme méthode ; seule une hypothèse PRÉ-ENREGISTRÉE (une période choisie
AVANT de regarder les données, comme `20` au 51e round parce que confirmée par la légende de
l'indicateur) constitue un test valide.

**Test refait correctement (hypothèse pré-enregistrée `SMA20`/`EMA20` uniquement), sur la capture
au MÊME préréglage que le 51e round ("Expert (Advanced Risks), 1, 20, 2")** : capture ETH 4h
(CRYPTO), bougie identifiée dans notre donnée réelle resamplée H4 (2026-05-01 04:00, écart OHLC
cumulé 10,5$ soit ~0,11%). `SMA20` = 2 277,36$, `EMA20` = 2 278,88$. Comparées aux 15 valeurs
lisibles de la légende (`2220,8 / 2348,4 / 2527,2 / 2412,8 / 2053,3 / 1962,4 / 2233,0 / 2394,9 /
1488,0 / 3301,9 / 2295,4 / 2190,6 / 2105,9 / 2021,2 / 1916,4`) : **la MEILLEURE correspondance est à
0,72-0,79% d'écart** (2295,4) — dix fois PIRE que le 0,07% du 51e round, et aucune autre valeur ne
s'approche. Même préréglage, même actif (ETH), méthode identique — et cette fois `SMA20`/`EMA20`
NE matchent RIEN dans la légende.

**Tentative complémentaire, non concluante** : la capture ETH 1h Bitfinex (datée "Nash0", 30 avr.
2026) affiche un tag "CONTEXT" pointant une bande rose — mesurée par pixels (méthode identique aux
rounds précédents) à environ [2 303$ ; 2 319$]. Mais cette bande ne s'étend PAS jusqu'à la bougie la
plus récente (elle s'arrête plusieurs dizaines de bougies avant le bord droit) — probablement une
boîte figée dessinée à un instant passé plutôt qu'un canal vivant qui suit le prix courant. Aucune
date fiable ne peut lui être associée sans un ancrage OHLC propre à CETTE zone précise (nous n'avons
que l'ancrage de la bougie la plus récente) — mesure abandonnée, pas assez fiable pour en tirer une
conclusion dans un sens ou l'autre.

**Conclusion honnête, mise à jour par rapport au 51e/52e round** : avec ce 3e point chiffré (même
préréglage que le point favorable du 51e round, cette fois clairement défavorable), le poids des
preuves **penche maintenant CONTRE `H-Context-MA20`** comme règle générale simple — le match à
0,07% du 51e round apparaît, avec le recul et après la correction méthodologique ci-dessus, plus
probablement une coïncidence qu'un signal réel. `H-Context-MA20` n'est PAS formellement réfutée
(un seul point favorable + deux points défavorables, échantillon encore petit, préréglages/UT pas
tous identiques), mais elle ne doit plus être présentée comme la piste la plus prometteuse pour
recalibrer `regime_classifier.py` — statut rétrogradé à "hypothèse affaiblie", pas "en attente de
corroboration".

**Nouveau, noté pour mémoire** : un 2e indicateur de la suite de Philippe jamais rencontré avant ce
round, **"PRO Financials (v1.0)"**, apparaît dans la légende d'une capture (en plus de PRO
Framework/PRO Momentum déjà connus) — aucune valeur ni fonction déductible d'une seule mention. Les
labels "PRU Actuel"/"23k$" et "neuneu" visibles sur la capture ETH 1h live sont des annotations
manuelles de l'utilisateur lui-même (suivi de position personnelle), pas des sorties de
l'indicateur — non pertinentes pour la reverse-ingénierie de "contexte".

**Ce que ce round NE fait PAS** : aucun changement de code — au contraire, ce round est un exemple
du principe "ne pas coder sur un résultat favorable non reproduit" qui vient d'éviter une erreur :
si `regime_classifier.py` avait été recalibré sur `SMA20` après le seul point du 51e round, ce 4e
lot aurait révélé l'erreur après coup. Prochaine étape, révisée : il faudrait soit (a) une preuve
NETTEMENT plus directe (une capture montrant le survol exact du plot "contexte" nommé comme tel
dans un "Data Window" TradingView, éliminant toute ambiguïté de correspondance), soit (b)
abandonner la piste `SMA20` et chercher un autre schéma (nested Fibonacci ratios, ATR bandé sur une
UT différente, etc.) — mais SANS recherche non contrainte sur l'espace des périodes, pour ne pas
retomber dans l'erreur méthodologique documentée ci-dessus.

## 10. 56e round — hypothèse directe de l'utilisateur testée : `H-Context-BB-UT+1` (Bollinger sur l'UT SUPÉRIEURE), 2 corroborations fortes sur 3

**Hypothèse formulée par l'utilisateur** (raisonnement en conversation, pas une capture) : *"le
contexte est dérivé des unités temporelles supérieures à la timeframe étudiée. C'est déjà un peu
comme les bandes de Bollinger et non les moyennes mobiles. C'est pour ça que nous voyons sur les
graphiques des cases grises... elles sont plates car c'est le prix de l'UT au-dessus qui est
mesuré, et nous sommes dans l'UT inférieur."* Deux idées combinées, jamais testées ensemble
jusqu'ici : (1) le canal de contexte est une bande de type Bollinger (`SMA(n) ± k×écart-type(n)`,
PAS `SMA ± k×ATR` comme testé aux rounds précédents), (2) calculée sur l'UT IMMÉDIATEMENT
SUPÉRIEURE à celle du graphique affiché — ce qui expliquerait directement la forme en paliers plats
déjà observée sur toutes les captures (une grandeur d'UT supérieure ne se met à jour qu'une fois par
bougie de cette UT, donc reste figée entre deux mises à jour vues depuis l'UT inférieure).

**Test rigoureux, hypothèse PRÉ-ENREGISTRÉE (période=20, k=2 — le "2" du triplet confirmé `(1, 20,
2)`, PAS une recherche libre)**, rejoué sur les 3 points déjà mesurés :

| Round | UT du graphique | UT testée ("au-dessus") | Résultat |
|---|---|---|---|
| 54 (ETH 4h, légende complète) | H4 | D1 | **top: −0,34%, bot: +0,31%** — les 2 bornes de la légende (2412,8 et 2220,8) collent au `Bollinger(20,2)` du D1 causal, simultanément, avec le MÊME k pré-enregistré |
| 52 (BTC 15 min, valeur unique) | M15 | H1 | **−0,07% à k=2,5 / −0,11% à k=3** (single-sided, cohérent avec une seule valeur mesurée) — nettement mieux que tout ce qui avait été testé sur cette même bougie aux rounds précédents (meilleur essai alors : 0,9%) |
| 51 (ETH 1D, bande pixel) | 1D | Semaine (calendaire, dim.-lun.) | **NE REPRODUIT PAS** : top +6,1%, bot −29,7% — écart bien trop large pour être un artefact de calendrier (semaine démarrant lundi vs dimanche) |

**Lecture honnête** : 2 points sur 3 corroborent fortement une hypothèse PRÉCISE et pré-enregistrée
(pas une recherche libre comme au 54e round) — un progrès net par rapport à tout ce qui avait été
testé jusqu'ici (le 51e round, meilleur résultat précédent, ne matchait qu'UNE seule borne, sur la
MÊME UT que le graphique, pas l'UT supérieure). Le 51e round ne réplique PAS sous ce nouveau test —
soit sa mesure pixel d'origine était contaminée/erronée (déjà signalé comme risque à l'époque : une
ligne bleue de moyenne mobile distincte traversait la même zone), soit "l'UT au-dessus" n'est pas
toujours la semaine calendaire standard pour un graphique journalier (convention de semaine
propriétaire à l'outil, non vérifiable sans plus de captures). Non tranché.

**Statut de l'hypothèse, mis à jour** : rebaptisée `H-Context-BB-UT+1` (remplace `H-Context-MA20`,
rétrogradée au 54e round) — 2 corroborations indépendantes fortes (rounds 52 et 54, actifs et UT
différents), 1 point non reproduit (round 51). C'est la piste la plus solide trouvée à ce jour,
mais PAS encore suffisante pour toucher `regime_classifier.py` : 2/3 n'est pas une preuve
définitive, et l'écart du 51e round reste inexpliqué plutôt que balayé sous le tapis.

**Ce que ce round NE fait PAS** : aucun changement de code. Prochaine étape proposée : d'autres
captures avec légende complète (comme aux 54e/56e rounds) sur d'autres UT/actifs pour départager le
désaccord du 51e round — en particulier une capture 1D avec une valeur de légende explicite (pas
juste une mesure de nuage par pixels, plus sujette à contamination) permettrait de retester
proprement l'hypothèse "UT au-dessus = Semaine" pour un graphique journalier.

## 11. 57e round — clarification de l'utilisateur : au moins DEUX constructions grises distinctes coexistent sur chaque graphique, piste de réconciliation du désaccord du 51e round

**Observation directe de l'utilisateur**, sur la capture "BTC Dominance 1W" déjà utilisée au 51e
round (`docs/NEUNEU_COMMUNITY_OBSERVATIONS.md`) : *"ce ne sont pas les bandes de Bollinger, car nous
observons sur cette image justement les bandes de Bollinger MAIS AUSSI les boîtes de contexte. Elles
mesurent la même taille. Ce sont des boîtes de contexte [dérivées] des bandes de Bollinger, qui
évoluent chaque semaine, d'où les décalages, et nous analysons l'unité temporelle 4h."* — un point
que ni moi ni les rounds précédents n'avions isolé : **il y a AU MOINS DEUX constructions grises
superposées sur chaque capture**, pas une seule.

**Vérifié visuellement (zoom sur la capture, pas de nouvelle capture nécessaire)** : sur ce
graphique BTC.D 1W, on distingue effectivement (1) une ligne en escalier à PAS LARGES, assez
lente, qui forme un grand arc (visible en haut à gauche, descendant progressivement) — plausible
candidat "bande de Bollinger" au sens de l'utilisateur ; (2) une ligne en escalier à PAS FINS qui
suit le prix de beaucoup plus près (visible en escalier serré juste au-dessus/en dessous des
bougies) ; (3) des zones grises REMPLIES (semi-transparentes), plus ponctuelles, qui ne suivent pas
le prix en continu — le candidat le plus probable pour la "boîte de contexte" proprement dite.
**Tentative de mesure pixel pour vérifier "la boîte mesure la même taille que la bande de
Bollinger"** : non concluante à ce stade — les 3 constructions se chevauchent et sont toutes
rendues en gris semi-transparent proche, une colonne de pixels isolée ne suffit pas à les séparer
proprement (contrairement aux rounds précédents où on mesurait UNE seule zone grise cohérente).
Pas assez fiable pour en tirer un chiffre.

**Piste de réconciliation du désaccord du 51e round, plausible mais non vérifiée** : si le 51e
round a mesuré par erreur la construction (2) (la ligne fine qui suit le prix de près, potentiellement
la vraie "bande de Bollinger" native, continuellement recalculée) au lieu de la construction (3) (la
vraie "boîte de contexte", gelée/mise à jour par intervalles) — cela expliquerait pourquoi ce point
ne collait pas au test `Bollinger(20,2)` de l'UT supérieure alors que les rounds 52/54 (où la
séparation entre constructions était visuellement plus nette) collaient bien. **Hypothèse non
tranchée, pas retenue comme acquise** — nécessite une capture où une seule construction grise est
isolée sans ambiguïté (idéalement via les réglages de l'indicateur, si l'outil permet de masquer
certains tracés individuellement) pour trancher proprement, plutôt que de re-deviner sur une image
où 3 éléments se superposent.

**Ce que ce round NE fait PAS** : aucun changement de code, aucune correction rétroactive du 51e
round (l'hypothèse de réconciliation ci-dessus reste non vérifiée). `H-Context-BB-UT+1` reste au
statut du 56e round (2 corroborations fortes sur 3, désaccord du 51e round toujours non résolu —
mais potentiellement expliqué, pas contredit, par cette clarification).

## 12. 58e round — `H-Context-BB-UT+1` câblé et MESURÉ sur Neuneu : résultat honnête, MITIGÉ, pas un gain net

**Demande directe de l'utilisateur** : *"en tant qu'ingénieur senior, mets une ou plusieurs
hypothèses permettant de prendre connaissance du contexte et de faire un des 4 choix (KO/tendance/
range/excès)... vérifie notamment sur sa capacité à rendre la stratégie de trading de range neuneu
rentable."*

**Implémenté** (strictement additif, aucun changement de comportement par défaut) :
- `emile/core/context_bollinger.py` (nouveau module, 4 tests unitaires) : `compute_bollinger`
  (Bollinger(20,2) natif sur l'UT supérieure), `attach_context_bb` (jointure causale merge_asof,
  MÊME convention `CLOSURE_DELAY=1 jour` que `backtest_phase2_v7.py::attach_higher_context`, jamais
  dupliquée), `compute_regime_bb_context` (réutilise `regime_classifier.add_regime` TEL QUEL — zéro
  modification de ce fichier, il acceptait déjà `ctx_median`/`ctx_width_pct` en paramètres
  génériques).
- `unified_protocol.py` : nouveau paramètre `use_bb_context_for_neuneu: bool = False` (additif) sur
  `run_unified`/`_run_core_unified`/`_prepare_unified`. Quand `True`, SEUL le gate régime de Neuneu
  (`feat["regime"][j] in (RANGE_NEUTRE, RANGE_TENDANCIEL)`, H-Borne-6) lit `feat["regime_bb"]`
  (candidat) au lieu de `feat["regime"]` (proxy EMA±ATR historique) — RANGE et TENDANCE restent
  inchangés dans les deux cas. `ValueError` explicite si `feat["regime_bb"]` absent. 4 nouveaux
  tests (`test_unified_protocol.py`, monkeypatch), dont un vérifiant explicitement que `regime_bb`
  prime sur `regime` quand le flag est actif, et l'inverse par défaut.

**Réponse à la question "4 choix (KO/Tendance/Range/Excès)"** : `compute_regime_bb_context`
produit EXACTEMENT les mêmes 3 catégories que le proxy historique (RANGE_NEUTRE/RANGE_TENDANCIEL/
TENDANCE/EXCES) — le 4e état demandé par l'utilisateur, "KO"/Chaos, reste NON défini : le corpus ne
le chiffre toujours pas (44e round, `docs/PLAN.md`, resté bloqué) et ce round n'invente rien de plus
que lui. Honnêteté : la demande "4 choix" n'est donc satisfaite qu'à 3/4 par ce round.

**Mesuré sur données réelles** (`emile/core/neuneu_bb_context_measure.py`, BTC/ETH/BNB/SOL × 4
profils, `use_neuneu=True` des deux côtés, seul `use_bb_context_for_neuneu` diffère,
`results/neuneu_bb_context_results.csv`) :

| symbole | Δ retour moyen (candidat − référence) | Δ drawdown max moyen | tranches Neuneu ouvertes (réf→candidat) |
|---|---|---|---|
| BTC | **-10,8 pt** | -2,6 pt (plus profond) | 86 → 83 |
| ETH | **-11,6 pt** | +0,9 pt (à peine plus profond/quasi neutre) | 77 → 74 |
| BNB | **+20,4 pt** | **+5,6 pt (nettement moins profond)** | 67 → 58 |
| SOL | **-24,0 pt** | -2,9 pt (plus profond) | 84 → 77 |

**Lecture honnête, sans arrondir dans un sens** : le candidat ouvre systématiquement UN PEU MOINS
de tranches Neuneu que le proxy historique sur les 4 actifs (-4% à -13%) — le gate régime basé sur
`H-Context-BB-UT+1` est un peu plus restrictif partout, effet structurel cohérent. Mais l'impact sur
la rentabilité est **fortement dépendant de l'actif, pas un gain net** : BTC/ETH/SOL se dégradent
nettement (-10,8 à -24,0 pt de retour), tandis que BNB s'améliore nettement, à la fois en retour
(+20,4 pt) ET en drawdown (+5,6 pt, moins profond) — un résultat notable car BNB/TRES_AGRESSIF est
"le chiffre le plus surveillé du projet" (37e round). **Aucune conclusion de performance n'a
influencé ce câblage** (principe inviolable du projet) — `use_bb_context_for_neuneu=False` reste le
défaut, ce résultat informe une décision future sans la trancher à la place de l'utilisateur.

**Conclusion** : `H-Context-BB-UT+1` ne rend PAS Neuneu uniformément plus rentable — 1 actif sur 4
en bénéficie nettement, 3 en pâtissent. Pas un signal suffisant pour changer le défaut. Le candidat
reste disponible en opt-in pour un usage ciblé (ex. BNB seul) si l'utilisateur le souhaite, mais ce
round ne recommande PAS de l'activer globalement.

Suite de tests inchangée pour tout appelant existant, `pytest -m ""` → 323/323 (313 + 6 nouveaux
tests `context_bollinger` + 4 nouveaux tests `unified_protocol`).

## 13. 59e round — demande directe : "place le contexte sur UT+2" -- `H-Context-BB-UT+2` mesuré, PIRE que UT+1 sur les 4 actifs

**Implémenté, strictement additif** : nouveau paramètre `bb_context_level: str = "ut1"` sur
`run_unified`/`_run_core_unified`/`_prepare_unified` (`unified_protocol.py`). `"ut1"` (défaut,
comportement du 58e round, inchangé) = D1 pour ce moteur H4 ; `"ut2"` = Hebdomadaire (`weekly`, déjà
un paramètre existant, aucune donnée supplémentaire à faire transiter). `ValueError` explicite pour
toute autre valeur. 2 nouveaux tests (`test_unified_protocol.py`, monkeypatch) vérifiant que
`"ut1"`/`"ut2"` sélectionnent bien `d1`/`weekly` respectivement, et le rejet d'une valeur inconnue.

**Mesuré sur données réelles** (BTC/ETH/BNB/SOL × 4 profils, `emile/core/
neuneu_bb_context_measure.py` étendu, `results/neuneu_bb_context_results.csv`), moyenne des 4
profils par actif, comparé au MÊME référentiel (proxy EMA±ATR historique) :

| symbole | Δ retour UT+1 (58e round) | Δ retour UT+2 (ce round) | Δ drawdown UT+1 | Δ drawdown UT+2 |
|---|---|---|---|---|
| BTC | -10,8 pt | **-15,8 pt** (pire) | -2,6 pt | -1,9 pt |
| ETH | -11,6 pt | **-36,2 pt** (bien pire) | +0,4 pt | -7,2 pt (pire) |
| BNB | **+20,4 pt** (seul gain) | **-19,4 pt** (bascule en perte) | +5,6 pt | -9,4 pt (bascule en perte) |
| SOL | -24,0 pt | **-52,6 pt** (bien pire) | -2,8 pt | -6,6 pt (pire) |

**Conclusion honnête, sans ambiguïté cette fois** : `H-Context-BB-UT+2` est PIRE que `H-Context-BB-
UT+1` sur les 4 actifs, sans aucune exception — y compris sur BNB, le seul actif qui bénéficiait de
l'UT+1 (+20,4 pt), et qui BASCULE en perte nette avec l'UT+2 (-19,4 pt). Le gate régime basé sur
l'Hebdomadaire est généralement plus restrictif (moins de tranches ouvertes sur 3 actifs sur 4) mais
cette restriction supplémentaire ne protège PAS le rendement — au contraire. Aucune trace
d'amélioration nulle part, contrairement à UT+1 qui au moins bénéficiait à un actif. **Ce round ne
recommande PAS `bb_context_level="ut2"`** — reste disponible en opt-in (implémenté, testé) mais
sans aucun cas d'usage positif identifié à ce stade, contrairement à UT+1 sur BNB spécifiquement.

Aucun changement de comportement par défaut (`use_bb_context_for_neuneu=False` reste le défaut,
`bb_context_level="ut1"` reste le défaut si le premier est activé). Suite de tests : `pytest -m ""`
→ 325/325 (323 + 2 nouveaux tests).
