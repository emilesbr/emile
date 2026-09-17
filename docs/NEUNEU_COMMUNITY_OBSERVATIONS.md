# Observations communauté — canal Discord "analyse-range" (Neuneu), captures avec indicateurs réels

**Source** : captures d'écran fournies par l'utilisateur d'un salon Discord communautaire dédié à
l'analyse de ranges "Neuneu" (USDJPY 15min, ETH 1h), montrant les **VRAIS indicateurs PRO Framework
(v5.2)/PRO Momentum (v5.2)** de Philippe Roux appliqués à des graphiques réels — pas notre proxy
(`regime_classifier.py`). Usage strictement personnel (cf. `CLAUDE.md`).

**Convention, identique à `GUIDE_STRATEGIE_PRO_INDICATORS.md`/`RULES_EXTRACTION.md`** : ce document
ne contient AUCUNE capture d'écran, seulement leur substance transcrite. Les pseudonymes Discord des
intervenants sont **anonymisés** (rôle générique substitué — "un membre", "l'auteur du montage")
par principe de minimisation : ils ne sont pas nécessaires à la substance technique, même s'il ne
s'agit pas de coordonnées de clients/prospects au sens du cadre RGPD de l'organisation.

**Document VIVANT** : l'utilisateur prévoit de fournir d'autres captures au fil du temps (49e round,
`docs/PLAN.md`) — nouvelles entrées ajoutées au fil de l'eau à ce même fichier, pas une extraction
figée en un seul passage.

Cette 1ère fournée (8 captures, USDJPY 15min et ETH 1h) a été analysée en réponse à la question
directe de l'utilisateur : *"quels sont les inconnues de l'IP de Philippe ou les données manquantes
nous empêchant de détecter... ou d'appliquer correctement Neuneu ?"*. Chaque section ci-dessous
recoupe une inconnue déjà identifiée par le raisonnement seul (round 48, réponse en conversation)
avec une preuve concrète tirée de la pratique réelle de la communauté.

## 1. Ce que ces captures CONFIRMENT (déjà implémenté, pas une inconnue)

- **L'invalidation par squeeze UT+1 est activement vérifiée en pratique, pas qu'une citation
  isolée du guide.** Un membre relève explicitement, face à un setup proposé par un autre :
  *"attention tu as un squeeze UT+1 et normalement c'est no go."* — mot pour mot la règle déjà
  implémentée au 31e round (`docs/GUIDE_STRATEGIE_PRO_INDICATORS.md` section 3.2,
  `regime_classifier.compute_squeeze`, invalidation 3ème borne par squeeze sur l'UT supérieure).
  Confirme que cette règle est une discipline réelle de la communauté, pas une phrase isolée du
  guide qu'on aurait mal généralisée.

## 2. Nouvelles inconnues/nuances trouvées (absentes du guide officiel ET des 17 sources vidéo)

### 2.1 Le comptage/réancrage des bornes est un JUGEMENT humain, pas une règle mécanique fixe

Sur le graphique USDJPY 15min, un membre observe un nouveau plus haut marginal et demande
explicitement : *"tu viens de faire un nouveau plus haut, mais tu la considères ici ? Même si c'est
un nouveau plus haut je suis ok c'est plus très significatif."* — puis propose DEUX lectures
concurrentes sans trancher : (a) si on considère la zone existante comme la zone de 3ème borne, il
faut remonter dans l'historique pour retrouver la vraie référence ; (b) si on considère ce nouveau
plus haut comme faisant foi, on est en recherche de la 2ème borne, mais *"je n'aime pas trop ce cas
là parce que pour moi tu es déjà en range."* L'auteur du montage répond en proposant une RÈGLE
D'ANCRAGE non documentée ailleurs : *"j'aurais placé ma 3BR quand on retourne les contextes pour la
première fois"* (le retour/croisement des canaux de contexte comme déclencheur de re-marquage,
pas un simple comptage de swings) — et conclut que même si un trade sur "la 9ème borne" aurait été
gagnant, **"ça ne respecte pas la stratégie neuneu"**.

**Ce que ça confirme/révèle** : (1) "qu'est-ce qui compte comme une borne significative" est
tranché au jugement par les praticiens eux-mêmes, sans seuil chiffré partagé — cohérent avec notre
propre constat (`SWING_ORDER=3` est emprunté à un autre composant, jamais une valeur donnée par
Philippe) ; (2) une piste MÉCANIQUE nouvelle et jamais vue ailleurs — le retour/croisement des
canaux de contexte comme déclencheur de RE-marquage de la 3ème borne — qui ne figure dans aucune
des 18 sources déjà extraites ; (3) confirmation explicite que "être routé vers Neuneu" (4+ bornes)
n'autorise PAS à trader n'importe quelle borne suivante : Neuneu a sa propre discipline d'entrée
(exactement ce que `neuneu_repli.py`/`neuneu_borne.py` construisent), un trade route-mais-hors-
discipline reste hors stratégie même s'il aurait été gagnant — payé cash par la communauté elle-même
avant nous.

### 2.2 Risque observé en pratique : 1% cité deux fois, jamais le "risque max 2%" littéral du guide

Deux membres, sur deux fils distincts, recommandent 1% (pas 2%) pour des setups Neuneu concrets :
- *"Viable mais risqué selon moi à prendre avec 1% max. Si tu regardes en H4 nous sommes sur des
  niveaux qui correspondent au haut d'un canal baissier. Canal qui rejette parfaitement."*
- *"On reste sur du 1% mais au moins on trade le range dans un range de l'UT faible risque."*

**Ce que ça révèle** : soit "risque max 2%" (citation littérale des écrans officiels, déjà câblée
`NEUNEU_RISK_PCT=0.02`) est un PLAFOND, pas une taille fixe — la pratique réelle réduit
discrétionnairement selon la qualité perçue de la confluence (canal supérieur qui rejette, range
imbriqué dans un range plus grand) — soit il existe une convention de sous-risque pour les setups
"secondaires"/emboîtés jamais documentée dans le guide. Aucune des deux lectures n'est trancheable
sans plus de captures — noté comme inconnue ouverte, pas choisi arbitrairement.

### 2.3 "Range dans un range" et "UT faible risque" — une structure emboîtée jamais modélisée

Citation complète : *"Une alternative serait d'attendre qu'on vienne revisiter le niveau de 3BR RTD
en H4. On reste sur du 1% mais au moins on trade le range dans un range de l'UT faible risque.
Attention tout de même, on a une target de range en W, les prix n'ont pas bloqué ici pour rien,
c'est une zone de vente potentielle, le ratio 1:1 à la vente se trade ici."*

**Ce que ça révèle** : un range tradé sur une UT donnée (ex. H1) peut être imbriqué DANS un range
plus large visible sur une UT supérieure (ex. Hebdomadaire), dont la borne agit comme
cible/rejet — une dépendance multi-timeframe de l'OBJECTIF qui n'existe dans aucune des 18 sources
déjà extraites, et que `neuneu_repli.py`/`neuneu_borne.py` ne modélisent PAS actuellement (leur
Objectif ne regarde que le canal de CONTEXTE de la même UT d'exécution, jamais une UT supérieure).
"UT faible risque" désigne apparemment une UT choisie spécifiquement PARCE QU'elle est imbriquée
(donc jugée moins risquée) — logique de sélection de timeframe jamais rencontrée ailleurs dans le
corpus.

### 2.4 Le ratio Fibonacci précis est 0,764 (76,4%), pas un "76%" arrondi — et 0,854 apparaît aussi

L'écran officiel du guide dit *"le prix est au-delà du fibo 76%"* (transcrit tel quel,
`NEUNEU_FIB_76=0.76` dans `neuneu_borne.py`). Sur le graphique RÉEL (ETH 1h, indicateur PRO
Framework v5.2 Expert), les niveaux affichés sont précisément **0,236 / 0,764 / 0,854** (plus les
extrêmes 0/1 du range) — et le membre qui propose le setup écrit lui-même *"Fibo 76,4 dépassé !"*,
pas "76%". **Deux trouvailles distinctes** : (1) le chiffre précis du vrai outil est 76,4%, pas 76%
— un écart mineur (0,4 point) mais qui mérite d'être corrigé pour fidélité (`NEUNEU_FIB_76 = 0.764`
plutôt que `0.76`) ; (2) un niveau supplémentaire, **0,854**, apparaît étiqueté sur le graphique réel
sans qu'aucune des 18 sources n'en parle — rôle inconnu (zone de confirmation supplémentaire ? borne
de la "zone fibo opposée" ? aucune preuve suffisante pour trancher avec une seule capture).

### 2.5 Préréglages de l'indicateur (Beginner/Intermediate/Expert, Range/Trend/Advanced Risk) — axe de configuration jamais mappé à nos profils

Les captures montrent l'indicateur réel étiqueté différemment selon le graphique :
*"PRO Framework (v5.2) Intermediate (Trend)"*, *"PRO Framework (v5.2) Expert (Advanced Risk)"*,
*"PRO Momentum (v5.2) Beginner (Range)"*. **Ce que ça révèle** : l'outil de Philippe expose
lui-même un préréglage à 2 dimensions (niveau {Beginner/Intermediate/Expert} × mode
{Range/Trend/Advanced Risk}) — on ne sait pas si ces préréglages changent le CALCUL sous-jacent
(seuils, sensibilité) ou seulement l'affichage. Rien ne garantit que ces préréglages correspondent à
nos 4 profils de risque (FAIBLE/MODERE/AGRESSIF/TRES_AGRESSIF, issus du manuel PDF, un axe
entièrement différent — money management, pas configuration d'indicateur). Ce pourrait être un axe
de variation TOTALEMENT ORTHOGONAL à ce que ce projet a modélisé jusqu'ici.

## 3. Référence hors périmètre notée en passant

Un membre recommande *"AVAX en H1, range très sympa à trader depuis plus de 2 mois"* comme exemple
de range Neuneu propre — AVAX est hors du périmètre actuel du projet (BTC/ETH/BNB/SOL). Noté pour
mémoire seulement, si le périmètre s'élargit un jour.

## 4. Ce que ce round NE fait PAS (catégorie C — décisions à prendre, pas des inventions)

Aucun changement de code à partir de ces seules 8 captures — chacun des 5 points de la section 2 est
une piste réelle mais insuffisamment étayée pour coder sans inventer (un seul exemple chacun,
parfois contradictoire ou incomplet). Exception mineure candidate : corriger `NEUNEU_FIB_76` de
`0.76` à `0.764` (2.4) est une correction de fidélité à coût nul, pas une invention — proposée mais
pas encore appliquée, en attente que l'utilisateur confirme si d'autres captures corroborent ou
nuancent ce chiffre avant de toucher au code déjà mesuré (46e-48e rounds).
