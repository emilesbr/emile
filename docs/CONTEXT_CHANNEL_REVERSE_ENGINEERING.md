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
