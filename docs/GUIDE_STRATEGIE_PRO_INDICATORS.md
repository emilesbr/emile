# Guide de Stratégie PRO Indicators — extraction (Phase 0bis)

Source : outil interactif officiel **« Guide de Stratégie »** de PRO-INDICATORS.com (logo visible
sur chaque écran), 38 captures d'écran organisées en 4 branches thématiques (Chaos / Excès / Range
/ Tendance), reçu de l'utilisateur (cf. `docs/PLAN.md` section "29e application"). Usage personnel.

**Important — ce document ne contient AUCUNE capture d'écran, uniquement leur transcription
texte**, exactement comme `docs/RULES_EXTRACTION.md` (manuel PDF) et `docs/TRADING_LESSONS_*.md`
(17 sources vidéo) ne contiennent jamais le PDF ni les vidéos elles-mêmes — seulement ce qu'ils
enseignent. Les 38 PNG bruts restent hors de ce dépôt (`claude/senior-engineer-role-57jq4k`) ;
leur sort sur la branche où l'utilisateur les a ajoutés (`claude/crypto-daily-capital-growth-b3hq1f`)
reste une décision de l'utilisateur, différée (cf. PLAN.md).

**Convention de transcription** : chaque écran a une zone "critères numérotés" (conditions
cumulatives de validation d'un pattern) et souvent une zone "Gestion du risque"
(STOPLOSS/VALIDATION/CONFIRMATION/OBJECTIF/RISQUE MAX). Je transcris les deux fidèlement, sans
paraphraser le texte libre. Nom du fichier source entre parenthèses pour traçabilité.

**Audit indépendant fait après une première version de ce document** (2 agents adversariaux
mobilisés par l'utilisateur, cf. `docs/PLAN.md` section "30e application") : l'un a rouvert les 38
PNG un par un et comparé au texte ci-dessous, l'autre a revérifié le croisement avec le code. Les
corrections qu'ils ont trouvées sont déjà appliquées dans ce document (pas laissées en note à
part) — cf. section 5 pour le détail des écarts de croisement code, et cette liste d'anomalies pour
les erreurs de transcription/catégorisation corrigées.

**Anomalies de capture trouvées, signalées telles quelles (pas corrigées ni devinées)** :
- 4 écrans sont des **templates vides** (aucun texte rempli, juste la structure UI) :
  `Excès/Excès/Revers.png`, `Excès/Bulle spéculative/Dead-Cat-Bounce.png`,
  `Excès/Bulle spéculative/Reverse-Crash.png`, `Excès/Bulle spéculative/Suivi-de-bulle.png`.
  Contenu réel INCONNU — pas inventé ici.
- `Tendance/Tendance-primaire/Divergence.png` a son texte intégralement rempli, mais l'emplacement
  du graphique affiche littéralement **"IMAGE A VENIR"** — anomalie distincte des 4 templates vides
  ci-dessus (ici seule l'illustration manque, pas le texte).
- `Tendance/Multi-timeframe/Vague-5-étendu.png` contient, à l'identique, le texte de
  `Range/Range-neuneu/Repli-neuneu.png` ("dumb zone" / RÈGLES DE DÉCLENCHEMENT 1-4 / fibo
  14,6-23,6%) — vraisemblablement une capture d'écran prise par erreur sur le mauvais panneau.
  Contenu réel de "Multi-timeframe → Vague 5 étendue" INCONNU.
- `Tendance/Multi-timeframe/Multi-timeframe.png` et `Tendance/Structure-alternative/Structure-
  alternative.png` contiennent la MÊME image (écran d'intro "STRUCTURE ALT.", dossiers VAGUE 1/
  VAGUE 5 étendue) — la vraie capture de l'écran "Multi-timeframe" (mentionné dans
  `Tendance/Tendance.png` : *"vous pouvez trader chaque TF en parallèle avec 2% de risque
  chacun"*) est probablement manquante, remplacée par un doublon de l'écran voisin.
- Un écran d'accueil (`Screenshot 2026-09-11 23.20.40.png`, à la racine du dossier du guide) n'a
  pas de section dédiée dans une première version de ce document — corrigé, cf. section 0
  ci-dessous.

## 0. Écran d'accueil (`Screenshot 2026-09-11 23.20.40.png`, racine du dossier)

« GUIDE DE STRATÉGIE — QUEL EST MON CONTEXTE ? » — écran de menu, logo PRO-INDICATORS.com. 4
dossiers : Excès, **Range** (marqué « DÉBUTANTS »), Tendance, Chaos — l'ordre de présentation suivi
par ce document (sections 1 à 4 ci-dessous couvrent Chaos/Excès/Range/Tendance, pas dans cet ordre
d'affichage mais dans l'ordre de complexité croissante déjà utilisé dans `RULES_EXTRACTION.md`).

## 1. Chaos (`Chaos/Chaos.png`)

Contexte de marché à éviter, 3 critères : **Contextes irréguliers**, **Moyenne plate**,
**Momentum bruyant**.

> « Le marché chaotique peut avoir de nombreuses causes et en réalité chercher à lui donner le
> moindre sens est une pure perte de temps et d'énergie. Il existe une infinité de marchés
> disponibles pour trader, pourquoi vouloir s'attacher à un en particulier. »

Action : **PARTEZ** (changer d'actif, pas de règle de trading proposée).

## 2. Excès

**Correction d'attribution (audit indépendant, cf. tête de document)** : une première version de
ce document avait interverti le contenu réel de `Exit.png` et `Trend-Follow.png` (deux fichiers
voisins, même famille de template "TAKE PROFIT/PSYCHOLOGIE") et avait aussi présenté
`Screenshot 2026-09-11 23.20.54.png` comme si c'était `Bulle-spéculative.png` (deux écrans
distincts, jamais le même titre ni le même contenu). Re-vérifié directement (3 lectures
indépendantes des fichiers réels, pas une seule) avant correction : les 4 sections ci-dessous sont
désormais chacune sourcée sur le bon fichier.

### 2.1 Excès (`Excès/Excès/Excès.png`)

3 critères : **Fondamental haussier**, **Pas de V5 étendue**, **Pas de multi-timeframe**. Aucun
niveau de difficulté ni ratio affichés sur cet écran (contrairement à 2.1bis ci-dessous, qui est un
écran DIFFÉRENT malgré le même titre "EXCÈS").

> « L'Excès n'est pas facile à trader car la composante principale de l'excès est souvent
> d'origine fondamentale. De ce fait il faut chercher une source rationnelle qui peut supporter
> la hausse de prix. Cela peut être dû à une réduction du supply ou une demande plus forte (effet
> d'annonce ou anticipations). Dans ce cas si la réalisation n'est pas à la hauteur des attentes
> la correction sera violente.
> Il est essentiel de s'assurer que vous n'avez pas à faire à une tendance multi-timeframe (sortie
> d'un range multi-timeframe) ni une structure de vague 5 étendue (pas d'overlap). »

Mène vers 3 sous-écrans : **Trend Follow**, **Exit**, **Reverse** (niveau hardcore) — le contenu
détaillé de "Reverse" est un template vide (`Excès/Excès/Revers.png`, cf. anomalies).

**Zone spéculative "Trend Follow"** (`Trend-Follow.png`) : 5 critères — suivi effectué sur UT-2,
prix sous le contexte vendeur UT-0, proche fibo 14,6% ou 23,6%, range mature ou repli moyenne,
signal momentum optionnel.
**Gestion du risque** : Stoploss sous le niveau Fibonacci suivant, au moins sous le contexte d'UT
supérieure, **risque max 2%**. Validation = rejoindre le contexte opposé ou casser la 3BR du range
mature (SL au plus bas récent). Confirmation = le prix quitte la zone de range et atteint le
contexte d'UT supérieure (SL à breakeven). Objectif : conserver jusqu'à un niveau d'objectif ou
apparition d'un pattern d'Exit, **utilisé 2 fois maximum**, ne pas laisser traîner les profits
après le 2ème suivi.

**Zone spéculative "Exit"** (`Exit.png`) : 6 critères — après 2 pattern de suivi UT-2,
débordement du contexte, au-dessus du canal de tendance, break sinewave (target), creux
descendant sur momentum, signal momentum optionnel.
**Gestion du risque** : TP 100% suivi ; TP 50% du reste sur les autres trades (breakout, accu…).
Psychologie : *« pas de trade en reverse, ce n'est pas du tout la même gestion du risque… juste un
TP »*.

### 2.1bis Excès niveau expert (`Screenshot 2026-09-11 23.20.54.png`)

Écran DISTINCT de 2.1 malgré le même titre "EXCÈS" — 3 critères différents : **Contextes
disjoints**, **Cycles inexistants**, **Momentum <0 acheté**. Badge « DIFFICULTÉ NIVEAU EXPERT ».
Ratio risque/rendement **1:10 à 1:20**. Mène vers 2 dossiers : "EXCÈS" et "NIVEAU HARDCORE : BULLE
SPÉCULATIVE" (donc un écran de transition entre 2.1 et 2.2, pas le contenu de 2.2 lui-même).

> « Le marché excessif se caractérise par des boîtes de contexte qui sont disjointes en support et
> en résistance. La situation doit s'établir plusieurs boîtes de suite et dans le cas des bulles,
> la structure continue même d'accélérer.
> Il est très difficile de faire la différence entre un excès et une bulle.
> Un excès peut être le signe d'une TENDANCE MULTI-TIMEFRAME. Alors que la bulle se caractérise par
> un excès qui n'est soutenu par aucun fondamental et ne valide pas de structure multi-timeframe.
> Sa fin sera relativement imprévisible. »

### 2.2 Bulle spéculative (`Excès/Bulle spéculative/Bulle-spéculative.png`)

3 critères (différents de 2.1bis) : **Fondamental inexistant**, **Pas de V5 étendue**, **Pas de
multi-timeframe**.

> « A l'inverse d'un excès la bulle se caractérise par l'absence totale de justification
> fondamentale. Le marché ne cherche plus à valoriser. Le prix est la seule chose dont les gens
> parlent. La structure s'enferme de plus en plus dans des raisonnements de court terme. Chaque
> repli est acheté et les ranges qui ponctuent la structures sont de plus en plus rapides alors que
> les volumes eux deviennent de plus en plus faibles.
> Il est essentiel de s'assurer que vous n'avez pas à faire à une tendance multi-timeframe (sortie
> d'un range multi-timeframe) ni une structure de vague 5 étendue (pas d'overlap). »
> *(« Attention à la psycho. »)*

Sous-écrans **Suivi de bulle**, **Reverse Crash**, **Dead Cat Bounce** : templates vides dans
cette capture (cf. anomalies) — aucune règle transcrite pour ces 3.

## 3. Range

### 3.1 Range (`Range/Range.png`)

2 critères : **Rejet des contextes**, **Pas de range UT+1 (mais OK si range UT+2)**. Difficulté
niveau débutant. Ratio risque/rendement **1:1 à 1:2**.

> « Le marché de range est le plus facile à trader d'un point de vue technique. Son principal
> problème c'est que 95% des prix ne servent à rien… Pour filtrer ces prix il nous faut distinguer
> deux structures de range.
> RANGE PRÉCÉDÉ D'UNE TENDANCE ? (moyenne hors des contextes = tendance)
> Si la réponse est OUI alors on applique la structure de "3EME BORNE". Pour tous les autres cas
> (pas assez d'historique, range avec plus de 4 bornes ou forex au delà de l'UT hebdo) nous
> appliquons la structure "NEUNEU". »

**Ceci est une décision de routage RANGE explicite et littérale, non ambiguë, qui ne semble PAS
actuellement câblée dans le code** (cf. section 5, écart n°1).

### 3.2 3ème borne (`Range/3eme-borne/3ème-borne.png`)

**3 critères propres à CET écran** (`3ème-borne.png` lui-même, distincts des 4 conditions de
`3br.png` ci-dessous) : **Contexte renversé**, **Pas de squeeze sur le prix**, **Pas de squeeze
sur le prix UT+1**. Callouts : *« JE VALIDE MES RÈGLES — AVANT D'ALLER PLUS LOIN »*, *« ATTENTION À
L'IMPATIENCE »* (icône sablier), *« UTILISEZ DES ALERTES »*. Mène vers 3 dossiers : **3BR**, **3BR
SQUEEZÉE**, et **3BR EN RETARD** marqué *« VÉRIFIER EN 1ER »*.

**Rappel des 4 conditions pour activer un pattern de 3BR** (image complémentaire,
`Range/3eme-borne/3br/3br.png` — corrigé : ce sont bien **4** conditions, pas 3, une première
version de ce document comptait mal) : **1** précédé ou au sein d'une tendance, **2** contexte
renversé, **3** triangle de confirmation, **4** pas de débordement du sommet (sinon 3BR
squeezée). *« Lorsque ces conditions sont bien vérifiées, il ne reste alors plus que deux options
possibles… 3BR NEUTRE ou 3BR TENDANCIELLE… À défaut il faudra privilégier la 3BR NEUTRE (car elle
est moins risquée que la variante tendancielle). »*

**"Exemples des erreurs classiques" (`3br.png`, panneau latéral, 4 graphiques annotés — en
anglais dans l'image)**, non transcrit dans une première version de ce document : *"SQUEEZE on
UT+1 (avoid trading that)"* ; *"CONTEXT has reversed on UT+1 (go trade on this TF)"* ; *"Price
SQUEEZED (range is mature, move to higher TF) — NO 3BR"* ; *"Have you seen the candles? (this is
chaos.. GET OUT)"*.

**Règle d'invalidation explicite (`3ème-borne.png`), littérale, VÉRIFIÉE contre le code** (cf.
écart n°2, confirmé par audit indépendant) :
> « La structure de 3EME BORNE peut prendre un grand nombre de formes. On ne doit plus la trader
> si jamais le range produit un SQUEEZE (canal de tendance grisé). On considère alors le range
> mature et on doit donc arrêter de trader sur cette UT.
> Si le range se forme juste après un SQUEEZE sur l'unité de temps supérieure, il faudra alors
> éviter de trader cette 3BR. On fait de même si le marché retourne au niveau de la 1BR (double
> top/bottom).
> Enfin il faudra apprendre la pattern de 3EME BORNE EN RETARD. On les appelle ainsi car vous ne
> pourrez les détecter qu'après coup. Mais il faut savoir le faire et les repérer si elles se
> produisent ! »

**3BR en retard** (`3br-en-retard.png`) — pattern A/B/C : (A) le prix casse le support du canal de
tendance et revient chercher le contexte acheteur mais ce dernier ne se retourne pas ; (B) le prix
rebondit sans faire de nouveau plus haut et retrace au moins jusqu'au canal de tendance résistant ;
(C) puis le prix rebaisse à nouveau, casse le point bas précédent (2BR) et doit également
renverser le contexte. *« L'indicateur est assorti de certaines fonctions de sécurité pour
empêcher le retournement des contextes quand la tendance est vraiment forte. Cela vous protège 9
fois sur 10 mais il reste quelques cas où ces protections vont vous induire en erreur (rien de
bien méchant vous allez juste rater la 3BR). »*

**3BR squeezée** (`3br-squeezée.png`) — 5 critères : débordement du contexte UT+1, débordement du
sommet précédent, boîtes contexte résistant disjointes, momentum > 80, target de break sinewave
optionnel.
> « Cette pattern se produit lorsque le marché ignore totalement la zone de 3BR et la traverse
> comme si de rien n'était. Ces patterns sont courantes dans les contextes de tendance excessive ou
> de tendance multi-timeframe.
> SI VOUS MAÎTRISEZ CES CONTEXTES (EXPERTS) ALORS UNE 3BR SQUEEZÉE SERA UN SIGNE QU'IL FAUT ALLER
> UT+2.
> La plupart du temps cette pattern ne produira pas de signaux dans la zone de 3BR, ce qui veut
> dire que vous n'aurez pas tradé. Dans ce cas il ne faut pas penser que la pattern 3BR n'a pas
> existé. Il faut noter la zone en tant que "3BR squeezée". Car ce n'est pas rien !
> Si vous avez eu un signal dans la zone vous allez alors être invalidé par le déclenchement du
> stoploss sans avoir atteint la validation. Ce sera donc une perte sèche (maximum 2%) et il ne
> faudra pas chercher à lutter. Cette pattern est le signe de tendance se produisant UT+2. Prenez
> du recul et notez la zone squeezée. N'OUBLIEZ PAS DE NOTER LA ZONE ! »

**3BR neutre** (`3br/3br-neutre.png`) — 5 critères : clôture au-dessus du contexte, retracement
≥76% fibo, triangle de confirmation, signal momentum (tous), break sinewave optionnel.
**Gestion du risque, risque max 2%** : Stoploss = reporter la taille du canal de tendance à partir
de la clôture précédente la plus haute. Validation = rejoindre le canal de tendance opposé
(SL et/ou TP partiel, cf. PDF). Confirmation = le prix clôture sous les 50% de contexte (SL à
breakeven + TP partiel). Objectif = récupérer ses profits dès que le prix atteint le contexte
opposé ou retrace plus de 76% de la distance totale du range. *« Ce trade ne rapporte jamais
beaucoup mais il vous aide à structurer votre psycho dans les ranges. »*

**3BR tendancielle** (`3br/3br-tendantiel.png`) — 6 critères : la 2BR a clôturé sous le contexte,
retournement dans le contexte, retracement ≥61% fibo, triangle de confirmation, signal de tendance
momentum, break sinewave optionnel.
**Gestion du risque, risque max 2%** : Stoploss = idem 3BR neutre. Validation = rejoindre le canal
de tendance opposé OU clôture au-dessous de 50% contexte. Confirmation = le prix atteint le
contexte opposé OU déborde le point bas précédent (2ème borne). Objectif = récupérer ses profits
dès que le prix se trouve sous le point bas précédent, sous les contextes acheteurs et que le
momentum donne un signal + triangle de confirmation — *« vous pouvez aussi utiliser un stop
suiveur à placer dès le débordement du point bas précédent »* (corrigé par audit indépendant :
cette citation appartient au champ **Objectif**, pas Confirmation, une première version de ce
document l'avait mal attribuée).

**Ces 2 grilles de validation numériques (neutre : retracement ≥76% ; tendancielle : retracement
≥61%, condition "2BR a clôturé sous le contexte") sont PLUS PRÉCISES que ce qui existe aujourd'hui
dans `RULES_EXTRACTION.md` §1 (retracement ≥76,4% pour Range neutre, ≥61,8% pour Range tendanciel —
cohérent, confirme les seuils déjà codés dans `fibonacci.py`/`regime_classifier.py`, à vérifier
précisément, cf. section 5).**

### 3.3 Range Neuneu (`Range/Range-neuneu/Range-neuneu.png`)

> « Le RANGE NEUNEU est la stratégie à privilégier quand vous avez le moindre doute. Ici il ne
> s'agit pas de prédire l'avenir, mais d'exploiter le fait que notre marché ne semble pas vouloir
> sortir de sa zone de range. Cette stratégie peut être utilisée quand on MANQUE D'HISTORIQUE. Il
> est alors important de vous poser une question simple : avez-vous réellement besoin de trader
> cet actif ?
> Si la réponse est oui alors c'est également la seule stratégie que vous pourrez appliquer dans
> les RANGES MATURES qui comptent 4 bornes et plus. C'est également la stratégie qu'il faudra
> appliquer par défaut pour le FOREX à partir de l'UT hebdo sur les paires majeures. C'est
> également une stratégie pour certaines commodities. »
> (« On place des fibos sur toute la hauteur du range. »)

**Borne Neuneu** (`Borne-neuneu.png`) — 4 critères : le prix est au-delà des contextes, le prix
est au-delà du fibo 76%, break sinewave optionnel, signal momentum optionnel.
**Gestion du risque, risque max 2%** : Stoploss = au-dessus du plus haut du range et au moins égal
à la moitié de la taille du canal de tendance. Validation = retour au canal de tendance opposé
(parfois la confirmation arrivera avant) — SL déplacé au sommet récent. Confirmation = le prix
revient dans le milieu du range (50% contexte, 50% fibo ou moyenne) — **TP 50% et ne pas déplacer
le stoploss !** Objectif : sortir tous les profits restants dès que le prix atteint le contexte
opposé ou la zone fibo 76% opposée.
> « Cette pattern produit près de 85% de taux de réussite pour un ratio gain/perte de 1:1. Elle est
> donc statistiquement viable si vous restez patients et pas gourmands. Il est également essentiel
> de ne jamais déplacer le stop à breakeven. »

**Repli Neuneu / "Dumb Zone"** (`Repli-neuneu.png`) — 4 critères : le prix est proche du contexte,
le prix est dans la zone fibo (14-23%), break sinewave optionnel, signal momentum optionnel.
Pattern 1/2/3 : (1) le prix fait un creux et a tenu plusieurs clôtures largement sous la zone
d'achat fibo (14,6%-23,6%) — *"le creux ne doit pas forcément faire un nouveau plus bas"* ; (2) le
prix rebondit et atteint la "dumb zone" ou il tient plusieurs clôtures sans sortir du haut de la
zone ; (3) puis le prix rebaisse et revient chercher la zone d'achat Fibonacci — dans ce cas on
applique les règles de déclenchement ci-dessus.
**Gestion du risque, risque max 2%** : Stoploss = taille du canal de tendance, au moins égal à la
moitié du canal de contexte. Validation = retour au contexte opposé ou entrée dans la dumb-zone
(SL déplacé au sommet récent). Objectif : viser le bas de la dumb zone pour un TP partiel, ne
jamais viser au-delà de la zone fibo opposée.

## 4. Tendance

### 4.1 Tendance (`Tendance/Tendance.png`)

2 critères : **précédé d'un range mature**, **pas de tendance UT+1**. Difficulté niveau
intermédiaire. Ratio risque/rendement **1:2 à 1:5**.

> « La principale difficulté dans la tendance réside dans le fait de se placer sur le bon
> timeframe (la tendance primaire). À défaut de valider ces conditions, on parle de "fluxs", ceux-
> ci vous indiquent que le contexte est sur une UT supérieure.
> ATTENTION AUX STRUCTURES ALTERNATIVES (les apprendre par cœur).
> Si votre marché est en train de breaker sur 3 timeframes consécutifs, vous avez alors à faire à
> une TENDANCE MULTI-TIMEFRAME. Dans ce cas si vous avez le NIVEAU EXPERT vous pouvez trader
> chaque TF en parallèle avec 2% de risque chacun. »
> Si la réponse est non → « vous avez à faire à un flux. La différence principale d'un flux est sa
> structure très variable. Là où la tendance primaire sera très structurée (break, suivi,
> pullback, excès-final), la navigation d'un flux sera très imprévisible… CHANGEZ DE TIMEFRAME ! »

### 4.2 Tendance primaire (`Tendance-primaire/Tendance-primaire.png`)

> « Après s'être positionné sur le timeframe de référence il faut définir la MATURITÉ DE LA
> TENDANCE. Pour répondre correctement à cette question il est essentiel de comprendre que chaque
> tendance est unique mais elles suivent toutes un schéma récurrent… EN TENDANCE J'ACTIVE "TREND
> SINEWAVE" ». Comment définir la maturité ? **1** le prix (comportement des canaux tendance et
> contexte), **2** la moyenne (position par rapport au contexte), **3** les cycles (pour valider le
> changement de rythme). *"Attention aux dissonances → connaissez vos faiblesses."*

Sous-étapes : **Accumulation → Breakout → Suivi de tendance → Divergence → Pullback → Excès
final** (confirme la séquence déjà connue de `RULES_EXTRACTION.md` §1).

**Accumulation** (`Accumulation.png`) — 5 critères : range mature sur l'UT contexte, range mature
du canal de tendance, retracement entre 38-50% (max 61), prix > au contexte acheteur, signal de
tendance momentum.
**Gestion du risque, risque max 2%** : Stoploss = sous le creux précédent et au moins égal à la
taille du canal de tendance. Validation = débordement du contexte + cassure de cycle (breakout) —
SL sous le range d'accumulation (déplacé à breakeven seulement si le breakout est tradé en plus).
Objectif : *« ne surtout pas chercher à remonter le stoploss trop vite… le trade d'accumulation est
celui qui vous rapportera le plus, son taux de réussite est donc plus faible… ne soyez pas surpris
si certaines accumulations échouent. »*

**Breakout** (`Breakout.png`) — 5 critères : débordement du contexte, cassure de cycle trend
sinewave, cassure de l'accumulation (si), momentum > 80, break sinewave recommandé.
**Gestion du risque, risque max 2%** : Stoploss = sous le creux précédent ou sous l'accumulation
s'il y en a une. Validation = report du range d'accumulation (si présent) — *"ne surtout pas
déplacer le stoploss !!!!!"*. Confirmation = report du range de contexte (SL à breakeven seulement
si réduction de risque voulue, sinon attendre le premier suivi de tendance). Objectif : *« la seule
règle est de ne jamais dépasser 2% de risque sur votre exposition à la tendance. Mais vouloir
ramener le risque à 0 trop vite n'est pas une bonne solution !! »*

**Divergence** (`Divergence.png`, texte intégralement présent mais illustration = placeholder
"IMAGE A VENIR", cf. anomalies) — 6 critères (numérotation source : deux fois "5") :
débordement du contexte, prix proche du canal de tendance, 2 suivis de tendance visibles, trend
sinewave > 80, break sinewave recommandé, signal momentum recommandé.
> « Comme une tendance ne peut être éternelle, nous devons prendre en compte sa maturité dans la
> gestion du risque. La Divergence est l'état de maturité intermédiaire de la tendance qui marque
> la fin du suivi de tendance. Généralement elle va se produire après le second suivi de
> tendance. »
Actions selon expérience : **Intermédiaire** — récupère les profits des trades en suivi, essaie
de laisser ouverts les trades en accu/breakout (ou juste TP50%) ; **Expérimenté** — récupère les
profits du suivi de tendance seulement, prend une position vendeuse au niveau de la 3BR du
pullback ; **Hardcore** — récupère les profits en suivi de tendance ET tente de vendre la
Divergence (contre-tendance) + la 3BR du pullback.

**Pullback** (`Pullback.png`) — 5 critères : clôtures sous 50% canal de contexte, range mature UT
tendance, retracement proche de 23-38% (50 max), signal de tendance momentum, fin de cycle sur
trend sinewave.
**Gestion du risque, risque max 2%** : Stoploss = taille du canal de tendance, au moins sous le
contexte. Validation = retour au canal de tendance opposé (SL déplacé sous le creux précédent).
Confirmation = atteint le canal de contexte opposé ou nouveau plus haut (SL à breakeven, *"se
préparer pour le take profit de l'excès final à venir"*). Objectif : *« une fois le trade de
pullback validé et confirmé il faut éviter de céder au biais qui vous invitera à vouloir "laisser
filer" la position "au cas où". Les tendances ne sont pas éternelles et un bon trade est un trade
encaissé. Il faudra positionner vos ordres limites ou alertes en vue de l'excès final. »*

**Excès final** (`Excès-final.png`) — 6 critères : prix > canal de contexte, prix > canal de
contexte UT+1, prix > sommet précédent, signal momentum (tout types), fin de cycle trend sinewave,
break sinewave recommandé. Actions selon expérience : **Intermédiaire** — récupère tous les
profits, repasse en mode range (*"je n'oublie pas que moins de 5% des marchés forment des excès en
fin de tendance… vous les raterez mais vous profiterez parfaitement des 95% restants !"*) ;
**Expérimenté** — récupère ses profits + s'assure de l'existence de tendances multi-timeframe
(imbriquées sur 3 TF consécutifs) pour appliquer ce modèle de gestion à la place ; **Hardcore** —
récupère ses profits, vérifie la tendance multi-TF et si rien alors tente un trade en reverse pour
venir chercher le repli vers la 2BR — *"il ne faudra en aucun cas trader contre-tendance dans les
tendances MTF ou les marchés peu liquides (fort risque d'excès)"*.

### 4.3 Suivi de tendance (`Suivi-de-tendance/Suivi-de-tendance.png`)

Rappel des conditions pour activer le suivi de tendance : **1** breakout validé et confirmé,
**2** moyenne haussière, **3** éviter si alerte de volatilité récente, **4** éviter si squeeze sur
les prix, **5** pas plus de 2 suivis dans une tendance.
> « Lorsque ces conditions sont bien vérifiées, vous pourrez alors passer sur un TIMEFRAME UT-2 ou
> vous pourrez chercher à acheter un repli sur la moyenne tant que le prix n'a pas atteint la
> formation d'une 3BR. Si la 3BR est déjà formée alors on attendra sa cassure et on ne tradera
> plus la moyenne. NE PAS TRADER LA MOYENNE SI LA 3BR EST DÉJÀ LÀ (dans ce cas on attend simplement
> la rupture de 3BR). »
3 branches : **Repli à la moyenne** (tant que pas de 3BR visible), **Cassure de 3BR** (si 3BR
présente, on attend sa cassure), **Repli sur 3BR squeezée** (si la 3BR est squeezée).

**Cassure de 3BR** (`Cassure-de-3br.png`) — 5 critères : la 3BR doit être validée et confirmée,
pas de squeeze de prix UT+1, entrée au breakout de la 3BR, momentum > 80 (optionnel), break
sinewave (optionnel).
**Gestion du risque, risque max 2%** : Stoploss = sous le point bas du range ou sous le contexte
UT+1. Validation = cassure du point haut précédent (*"ne surtout pas déplacer le stoploss !!!!!"*).
Confirmation = report du range (SL à breakeven seulement si réduction de risque voulue, sinon
attendre le premier suivi de tendance). Objectif : *« le plus simple est de placer un ordre
d'entrée de type stop-achat au-dessus du niveau de la 3BR une fois que cette dernière est validée
et confirmée… vous pouvez mettre une alerte ! »*

**Repli à la moyenne** (`Repli-a-la-moyenne.png`) — 5 critères : repli sur la moyenne, moyenne
ascendante, retracement fibo à proximité, signal momentum optionnel, break sinewave optionnel.
**Gestion du risque, risque max 2%** : Stoploss = sous le contexte UT+1 et au minimum égal à la
taille du canal de tendance. Validation = retour au contexte opposé (*"ne surtout pas déplacer le
stoploss !!!!!"*). Confirmation = sortie de la zone de range dans le sens de la tendance (SL à
breakeven seulement si réduction de risque, sinon attendre le second suivi). Objectif : *« pour le
premier suivi de tendance on essaie de ne pas remonter le stop trop vite, pour le second également,
mais pour celui-ci on fera particulièrement attention à récupérer ses profits (au moins partiels)
sur la pattern de divergence. »*

**Repli sur 3BR squeezée** (`Repli-sur-3br-Squizee.png`) — 4 critères : la 3BR doit être
squeezée, entrée au niveau de la 3BR, sinon au niveau du fibo 50%, signal momentum optionnel.
**Gestion du risque, risque max 2%** : Stoploss = sous le point bas du range ou sous le contexte
UT+1. Validation = cassure du point haut précédent (*"ne surtout pas déplacer le stoploss !!!!!"*).
*« Évitez de trader cette pattern sur le second suivi de tendance (ou alors pensez à récupérer
rapidement vos profits). »* Objectif : *« placer un ordre d'entrée de type limite au niveau de la
3BR ou à défaut à 50% de retracement de la dernière jambe de hausse. »*

**Ceci est la MÊME variante d'entrée par ordre limite sur "3ème borne squeezée" que celle déjà
implémentée côté RANGE (18e/22e rounds, `compute_squeezed_third_border`) — mais ici dans le
contexte TENDANCE/Suivi-de-tendance, avec un niveau d'entrée différent (fibo 50% de la jambe de
hausse, pas le range) : à vérifier si le mécanisme actuel couvre ce cas ou seulement le cas RANGE
(cf. écart n°3).**

### 4.4 Multi-timeframe (`Multi-timeframe/Multi-timeframe.png`)

Contenu réel non capturé (doublon de l'écran Structure Alternative, cf. anomalies) — la seule
information disponible sur le Multi-timeframe est celle déjà citée dans `Tendance.png` : activable
quand le marché breake sur 3 timeframes consécutifs, niveau EXPERT requis, permet de trader chaque
TF en parallèle avec 2% de risque chacun.

**Vague 1 étendue (contexte Multi-timeframe)** (`Multi-timeframe/Vague-1-étendu.png`) :
> « Dans une vague 1 étendue (V1E) le supply est extrêmement rare, à tel point que la hausse de la
> demande va causer un départ prématuré de la tendance. Autrement dit il n'y aura pas
> d'accumulation et le prix va rebondir très violemment en formant généralement un "V bottom". Le
> soucis principal avec la V1E vient du fait qu'on peut difficilement l'anticiper, on la constate.
> La psychologie des investisseurs est alors très altérée… Vous devrez avoir le raisonnement
> inverse. Ramassez les miettes mais si vous l'avez ratée, acceptez-le !! »
Pattern 1/2/3 : le marché réalise un premier breakout mais échoue vers la confirmation et se
replie jusqu'au niveau de break ; le prix tente un second breakout qui échouera également à aller
au-delà du report de range (confirmation) ; le prix réalise un second pullback et retourne
chercher la zone de prix traitée au sommet du 1er break.

**Vague 5 étendue (contexte Multi-timeframe)** : contenu réel non capturé (doublon avec
Range-neuneu, cf. anomalies).

### 4.5 Structure alternative (`Structure-alternative/Structure-alternative.png`)

> « Les structures alternatives sont généralement causées par un déséquilibre dans le supply
> (quantité d'actifs en circulation). Dans le cas où le supply est très faible, la moindre demande
> causera un rebond excessif du prix. On parle alors de schéma de "vague 1 étendue". Dans le cas
> inverse (supply important, par exemple dû à une forte inflation) on assiste souvent à une
> structure en "vague 5 étendue". Dans les deux cas le prix se déplace toujours d'une zone de prix
> A vers une zone B mais la "façon" de le faire sera différente de la tendance primaire dans son
> organisation. Il faudra apprendre ces alternatives pour ne pas être surpris quand elles arrivent
> (moins souvent que la version primaire). » *(Des anomalies dans la structure primaire doivent
> vous alerter — ces structures induisent des biais psycho encore plus prononcés.)*

**Vague 1 étendue (Structure alternative)** (`Structure-alternative/Vague-1-étendu.png`) :
paragraphe théorique PROCHE de celui de 4.4 mais PAS identique mot pour mot (corrigé par audit
indépendant — une première version de ce document affirmait à tort "même paragraphe") : la version
ci-dessus (4.4, Multi-timeframe) se termine par *"...on peut difficilement l'anticiper, on la
constate. [...] Ramassez les miettes mais si vous l'avez ratée, acceptez-le !!"* ; celle-ci se
termine par *"...on la constate en cours de route. [...] Sachez acceptez que vous avez raté le
plus gros, contentez-vous des miettes !!"* — deux variantes rédactionnelles proches, pas le même
texte. Pattern légèrement différent de 4.4 : (1) reverse en "V Bottom", la moyenne repasse sous le
contexte, le prix revient au sommet précédent (peut même le déborder) ; (2) un premier pullback
classique intervient et est suivi par une structure d'excès final classique elle aussi ; (3) arrive
un second pullback qui se positionne en overlap et produira un second, et dernier, excès final.

**Vague 5 étendue (Structure alternative)** (`Structure-alternative/Vague-5-étendu.png`) :
> « Dans une vague 5 étendue (V5E) le marché se comporte de manière assez piégeuse et la
> psychologie sera le facteur déterminant. Il faudra rester très patient car le fait que le marché
> rejette deux breakouts pourra vous faire douter sur l'existence de la tendance. Celle-ci
> n'arrivant que dans la phase finale, elle se fait le plus souvent en "V Top".
> N'ayant pas d'excès final sur le sommet il faudra récupérer ses profits sur des niveaux plus
> arbitraires. Il est essentiel de comprendre que sortir au meilleur prix n'est pas possible. Il
> est même recommandé d'utiliser une sortie "en paliers" avec plusieurs ordres limites.
> La V5E prend une forme excessive sur son dernier breakout ne soyez pas surpris ni sur-éxité.
> Appliquez votre plan de gestion ! »
Pattern 1/2/3 : le marché réalise un premier breakout mais échoue vers la confirmation et se
replie jusqu'au niveau de break ; le prix tente un second breakout qui échouera également à aller
au-delà du report de range (confirmation) ; le prix réalise un second pullback et retourne
chercher la zone de prix traitée au sommet du 1er break.

## 5. Écarts corpus↔code — VÉRIFIÉS contre le code réel (audit indépendant, cf. `PLAN.md` "30e application")

Contrairement à la version précédente de cette section ("à vérifier"), les items 1 à 3 ci-dessous
ont désormais été **relus directement dans le code réel** (pas seulement supposés) par un agent
d'audit indépendant, citations fichier:ligne à l'appui. Toujours **catégorie C — rien implémenté**,
décision de conception requise pour chacun.

1. **PARTIELLEMENT IMPLÉMENTÉ (32e round, cf. `PLAN.md`) — routage RANGE "3ème borne" vs
   "Neuneu".** La grille "3ème borne" s'est révélée être DÉJÀ le mécanisme §3/§3bis existant (mêmes
   seuils 76%/61%, même renvoi au PDF pour les fractions de clôture) — le vrai travail neuf était
   la DÉCISION DE ROUTAGE elle-même. `regime_classifier.py::compute_range_precedes_by_trend` +
   `compute_range_border_count` (compte remis à zéro PAR ÉPISODE de range — PAS une réutilisation
   de `n_borders`, dont la médiane glissante perpétuelle vaut 9 sur BTC H4 réel, la réutiliser
   aurait rendu ce routage trivialement vrai partout) + `compute_use_neuneu` — signal exposé
   (`feat["use_neuneu"]`), mesuré non trivial (~82% des bougies RANGE routeraient vers Neuneu),
   PAS ENCORE CONSOMMÉ par aucun moteur (comportement inchangé). Le mécanisme NEUNEU lui-même
   (grille de risque distincte) reste différé : il exige un stop TRAILING et un ordre Validation/
   Confirmation non séquentiel, deux capacités absentes de `position_engine.py` aujourd'hui.
2. **IMPLÉMENTÉ (31e round, cf. `PLAN.md`) — moitié manquante de l'invalidation 3BR par squeeze
   UT+1.** Nouvelle fonction `regime_classifier.py::compute_squeeze` (miroir exact de
   `compute_wide_channel`, même patron, seule la direction de comparaison change) expose
   spécifiquement l'état "squeeze" du D1, distinct de l'état "canal trop large" — les deux étaient
   pliés dans le même régime `EXCES` par `add_regime`, ce qui empêchait `range_gate` de bloquer
   spécifiquement sur le squeeze sans aussi bloquer sur "D1 trop large" (déjà un cas différent,
   non visé par cette citation). `range_gates.py::range_gate` bloque désormais l'entrée si
   `feat["squeeze_d1"][i]` est vrai — strictement additif, testé (garde-fous "squeeze ⊆ EXCES",
   causalité, cas de base) et mesuré. La 3ème clause ("retour au niveau de la 1BR") reste NON
   implémentée (aucun suivi du niveau de la 1ère borne dans ce moteur — backlog ouvert).
3. **CONFIRMÉ, et PLUS LARGE que prévu — pas seulement la variante squeeze.** L'audit a montré que
   c'est tout le mécanisme "Suivi de tendance" (§4.3 de ce document — 3 branches Repli à la
   moyenne/Cassure de 3BR/Repli sur 3BR squeezée, chacune avec sa propre grille STOPLOSS/
   VALIDATION/CONFIRMATION/OBJECTIF, précédées de 5 conditions d'activation) qui est ABSENT de
   `trend_table.py` (le moteur TENDANCE) — `grep -n "suivi\|volatil\|alerte\|repli.*moyenne"` n'y
   retourne aucun résultat. Le code actuel modélise le Breakout comme un simple "Renfort +X%" figé
   par profil puis saute directement à Divergence : aucune des 3 branches de ré-entrée par ordre en
   attente n'existe. `compute_squeezed_third_border`/`_add_squeeze_columns`
   (`backtest_phase2_faithful.py`) ne sont câblés QUE côté RANGE (moteur séparé, sans import croisé
   avec `trend_table.py`) — la variante squeeze de §4.3 n'est donc, en l'état, qu'un TIERS du trou
   réel.

**Nouvel item trouvé par l'audit, catégorie C** :

4. **Sous-patterns Trend Follow/Exit en régime Excès jamais implémentés.** Le guide (§2.1) donne
   deux patterns tradables EXPERT en régime Excès, avec grilles de risque complètes. Le code
   actuel (`range_gates.py:48`, `feat["regime"][i] != "EXCES"`) bloque INCONDITIONNELLEMENT toute
   entrée en régime EXCES — cohérent avec le choix déjà documenté de laisser Excès hors périmètre
   (`RULES_EXTRACTION.md` : *"Bulle/Excès → NE PAS TRADER"*), mais ce choix mériterait d'être
   reconfirmé explicitement à la lumière de ce contenu plutôt que de rester implicite.

**Correction d'une conclusion FAUSSE de la version précédente de cette section (trouvée par
l'audit, pas glissée sous le tapis)** :

5. ~~**Seuils de retracement 3BR neutre (≥76%) / 3BR tendancielle (≥61%)** — "confirme les seuils
   déjà codés dans `fibonacci.py`/`regime_classifier.py`"~~ — **FAUX, vérifié et corrigé.**
   `regime_classifier.py::add_regime` ne contient AUCUN calcul de retracement Fibonacci (seulement
   pente + position récente). Les seuils de `fibonacci.py` (`FAVORABLE_MIN=0.23`/
   `FAVORABLE_MAX=0.618`, lignes 200-202) servent `classify_retracement` côté **TENDANCE** (zone
   favorable du Pull-Back, 61,8% comme PLAFOND d'invalidation) — c'est l'inverse directionnel du
   seuil RANGE du guide (76,4%/61,8% comme PLANCHER d'entrée). Le rapprochement ne tenait qu'à une
   coïncidence numérique (0,618 des deux côtés), pas à un mécanisme partagé. Pire : le projet
   documente LUI-MÊME, ailleurs, qu'aucun gate RANGE par retracement n'est implémenté —
   `backtest_phase2_faithful.py:299-313`, *"Gate Fibonacci RANGE (manuel, seuils par régime) --
   délibérément PAS implémenté ce cycle"*, avec la citation exacte du même "76%" et l'avertissement
   que ce chiffre est un seuil d'ENTRÉE ici et une cible de SORTIE ailleurs dans le corpus.
   **Aucun gate RANGE par retracement Fibonacci n'est codé, nulle part** — ce n'était pas "à
   vérifier", c'était déjà écrit dans ce même fichier avant que cette section ne soit rédigée, et
   ç'aurait dû être croisé avant d'écrire "confirme".
6. **Range Neuneu, condition d'usage FOREX "à partir de l'UT hebdo sur les paires majeures"** —
   non applicable au périmètre crypto de ce projet (BTC/ETH/BNB/SOL), à noter comme hors-scope
   plutôt qu'un écart.
7. **Taux de réussite chiffré "~85%, ratio 1:1" pour Range Neuneu (Borne Neuneu)** — chiffre du
   guide officiel, jamais mesuré indépendamment sur les moteurs de ce projet ; à comparer si
   l'occasion se présente (mesure honnête, pas une contrainte de conception).

## Prochaine étape (round séparé)

Traiter un écart à la fois avec la discipline habituelle (décision de conception documentée AVANT
le code, mesure honnête, non-régression bit-à-bit) — l'écart n°2 (squeeze UT+1) est le plus mûr
(citation exacte + emplacement précis dans `range_gates.py`), l'écart n°3 (Suivi de tendance
absent de `trend_table.py`) est le plus large en portée. Aucun des deux n'est implémenté par ce
round ni le précédent — décision de conception à prendre séparément, comme pour Fibonacci
RANGE/Conflit MTF avant eux.
