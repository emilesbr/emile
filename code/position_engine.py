"""
Moteur de position partagé (Validation / Confirmation / Limite / Invalidation).

Factorise la boucle de gestion de tranche(s) auparavant copiée-collée à la
main dans trois fichiers :
  - backtest_phase2.py   (run_backtest_mm, tranche unique)
  - backtest_phase2_v4.py (run_v4, jusqu'à 3 tranches, pyramidalisation)
  - backtest_phase2_v5.py (run_v5, identique à v4, proxy de signal différent)

Règles de gestion (dérivées du corpus Trading Lessons, cf. RULES_EXTRACTION.md
et PHASE2_CORRECTION_BREAKEVEN.md / PHASE2_CORRECTION_CLOSES.md) :
  1. Limite atteinte  -> clôture totale de la tranche (déclenchée sur CLÔTURE).
  2. Invalidation (stop) touchée -> clôture totale (déclenchée sur la MÈCHE,
     c'est un ordre réel qui s'exécute intrabar).
  3. Sortie de signal (flip) AVANT toute étape (ni Validation ni Confirmation
     atteintes) -> sortie au marché (open de la bougie suivante).
  4. Confirmation atteinte (seulement si Validation déjà faite, séquentiel,
     déclenchée sur CLÔTURE) -> clôture partielle éventuelle + c'est le SEUL
     point où le stop peut être remonté au break-even (si le profil l'autorise).
  5. Validation atteinte (déclenchée sur CLÔTURE) -> clôture partielle
     éventuelle. Le stop n'est JAMAIS remonté à cette étape (interdit avant
     Confirmation, cf. correction du 2025 : l'ancienne approximation qui
     remontait le stop dès la Validation était une lecture erronée du corpus).

Les niveaux de Validation/Confirmation/Limite ainsi que le stop initial sont
calculés par le script appelant (ils diffèrent entre moteurs : multiples
d'ATR fixes dans backtest_phase2.py, vs. amplitude réelle en durée +
Extreme Channel dans v4/v5) et injectés via `open_tranche_fn`. Un hook
optionnel `update_levels_fn` permet de reproduire le comportement spécifique
de backtest_phase2.py, où Validation/Confirmation/Limite sont RECALCULÉS
à chaque pas de temps à partir de l'ATR courant (et non figés à l'entrée
comme dans v4/v5) — un comportement pré-existant, conservé tel quel pour ne
pas changer les résultats numériques du refactoring.

================================================================================
"+Reverse" du profil Très Agressif à la Limite -- TABLE RANGE (RULES_EXTRACTION
§3, "Money management -- Trade spéculatif (range)"), PAS le mécanisme +Reverse
de la table TENDANCE (§4, `trend_table.py::step_reverse`, profil Très Agressif,
étape Excès final -- structurellement différent, ne pas confondre : celui-là
inverse après une campagne à jambes multiples avec renfort progressif, celui-ci
inverse après la clôture d'une simple tranche long au niveau Limite).
================================================================================
Rappel de la source, reproduit ici pour traçabilité (RULES_EXTRACTION.md §3) :

    4 étapes : Validation -> Confirmation -> Invalidation -> Limite (target)

    | Profil         | Validation | Confirmation | Invalidation | Limite         |
    |----------------|------------|--------------|--------------|----------------|
    | Très agressif  | RIEN       | —            | RIEN         | TP100%+Reverse |

"RIEN"/"—" pour Très Agressif à Validation/Confirmation/Invalidation ne change
rien au comportement déjà en place (val_close_frac=0, conf_close_frac=0 dans
PROFILES_V4 de backtest_phase2_v7.py ; Invalidation reste, comme pour tous les
profils, la clôture totale au stop déjà codée en dur). Le seul comportement
manquant est "TP100%+Reverse" : au lieu de simplement clôturer la tranche
long à la Limite (ce que fait déjà l'étape 1 de `process_tranche`), le profil
Très Agressif ouvre EN PLUS une position short au même instant.

HYPOTHÈSE D'IMPLÉMENTATION (H-Reverse-Range -- le manuel ne donne AUCUN
paramètre pour cette jambe short : ni taille, ni stop, ni cible ; documenté
explicitement ici, sur le modèle de `code/capital_tiers.py` pour une règle
source sous-spécifiée, PAS inventé en silence) :
  - **Taille** : identique à la taille (fraction du capital) qui vient de se
    clôturer sur la jambe long (`tr["remaining"]` juste avant la mise à zéro).
    Aucune indication contraire dans la source ; une taille "miroir" est la
    lecture la plus neutre de "Reverse" (inverser la même exposition).
  - **Prix d'entrée** : le prix de clôture (`c[i]`) qui a déclenché la Limite
    -- l'inversion est immédiate, pas différée à la bougie suivante (cohérent
    avec le principe "reverse AU MOMENT de la clôture" du libellé "TP100%+
    Reverse", une seule action combinée dans la source, pas deux évènements
    séparés dans le temps).
  - **Stop de la jambe reverse** : MIROIR de la distance (en %) entre l'entrée
    long et son stop initial, reportée au-dessus du nouveau prix d'entrée
    short. Ex. : le long avait un stop à -5% de son entrée -> le short a un
    stop à +5% de sa propre entrée. Choix motivé par l'absence de toute autre
    référence dans la source, et par cohérence avec le principe du profil (le
    même risque nominal en % est repris, pas un risque arbitraire différent).
  - **Cible de la jambe reverse** : MIROIR de la distance (en %) entre l'entrée
    long et son propre niveau Limite, reportée en dessous du nouveau prix
    d'entrée short. Même justification que pour le stop.
  - **Portée** : jambe short BORNÉE (un seul stop, une seule cible), PAS une
    réplique complète de la table à 4 étapes côté short (la source ne décrit
    aucune sous-étape Validation/Confirmation pour la jambe reverse) -- même
    esprit de simplification assumée que H10 de `trend_table.py` pour son
    propre "+Reverse" (table tendance), documentée là comme "implémentation
    SIMPLIFIÉE ... PAS une table symétrique côté short".
  - **Déclenchement de sortie** : stop touché sur la MÈCHE (`high[i] >=
    stop`, ordre réel intrabar, même convention que l'Invalidation long) ;
    cible atteinte sur la CLÔTURE (`c[i] <= target`, même convention que la
    Limite long). Choix : réutiliser EXACTEMENT les deux conventions de
    déclenchement déjà établies pour la jambe long dans ce même fichier,
    plutôt que d'en inventer une troisième pour la jambe short.
  - **Non-goal explicite (documenté, pas caché)** : le moteur ne force AUCUNE
    exclusion mutuelle entre une jambe reverse ouverte et l'ouverture d'une
    NOUVELLE tranche long (par ex. via la pyramidalisation `max_tranches>1`
    d'un autre appelant) -- chaque tranche/jambe reste gérée indépendamment,
    exactement comme les tranches pyramidées entre elles sont déjà
    indépendantes les unes des autres (aucune ne connaît l'état des autres,
    cf. `process_tranche`). Gérer une éventuelle règle "pas de long tant
    qu'un reverse est ouvert" est laissé à la charge de l'appelant (sa propre
    logique de signal dans `open_tranche_fn`/`long_signal`), pas à ce moteur
    générique. De même, `record_trace=True` ne trace PAS les jambes reverse
    (reste un non-goal de ce cycle, `funding_rate_exact.py` n'est pas mis à
    jour pour un coût de funding sur une position short).

================================================================================
"STOP LOSS = TAILLE DU CANAL" -- règle de volatilité (réduction symétrique
stop + position sur canal TRÈS LARGE). Catégorie B, item (ii) de l'audit
exhaustif du corpus (`COUVERTURE_ENSEIGNEMENTS.md` section "Audit exhaustif
du corpus complet", `PLAN.md` backlog item 11).
================================================================================
CITATION EXACTE, reproduite mot pour mot pour traçabilité
(`TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md`, source #5, §5 "Gestion
tactique -- Stop Loss et objectifs (règles mathématiques précises)") :

    **Dimensionnement du Stop Loss** :
    - Règle standard : **Stop Loss = taille du canal de tendance**
    - Règle de volatilité (symétrie du risque) : si canal très large ->
      **Taille du Canal / 2 = Taille du Stop Loss ET Taille de Position / 2**
      simultanément (préserve une exposition capital constante)

Confirmée comme règle OBLIGATOIRE par la checklist pré-trade de la même
source (§ "Checklist de pré-trade complète") :

    - [ ] Dimensionnement : stop loss indexé sur le canal (ajusté selon
      volatilité) ?

La "Règle standard" est DÉJÀ en place dans ce projet depuis v4 (le stop est
indexé sur le canal "Extreme Channel" -- `stop_price = min(ctx_support[j],
...)` ci-dessous, cf. H4 de `trend_table.py` et la ligne "Extreme Channel"
de `PHASE2_V4_IMPLEMENTATION_COMPLETE.md`). Seule la "Règle de volatilité"
manquait : c'est ce que ce bloc ajoute.

Relecture intégrale de la source faite AVANT d'écrire une ligne de code, et
recherche exhaustive du reste du corpus (17 sources + `RULES_EXTRACTION.md`)
pour un éventuel seuil chiffré de "très large" : AUCUN n'existe. Les deux
seules autres références de largeur de canal du corpus sont (a)
`TRADING_LESSONS_ZONE_ACCUMULATION.md` -- *"Stop-loss = largeur moyenne du
canal de tendance récent"* (une MOYENNE récente comme référence, pas un
seuil de déclenchement) et (b) les seuils absolus du manuel (<1% squeeze,
>12% excès) que ce projet a déjà explicitement refusé d'appliquer tels quels
à notre approximation EMA±2xATR (largeur médiane ~17% sur crypto, cf.
`REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md`) et remplacés par des percentiles
glissants causaux. Le seuil est donc une HYPOTHÈSE assumée (H-Canal-Large-3
ci-dessous), pas une lecture littérale -- documentée comme telle, jamais
inventée en silence (même discipline que H1-H12 de `trend_table.py`, que
H-Reverse-Range ci-dessus et que H1 de `wall_street_pattern.py`).

--------------------------------------------------------------------------
H-Canal-Large-1 -- MÉCANIQUE EXACTE DES DEUX "/2" (quelle est la position de
référence qu'on divise par deux ?). La phrase est ambiguë ; deux lectures
possibles, tranchées par la parenthèse de la source elle-même :

  (A) RETENUE. Le stop passe à la MOITIÉ de la distance standard, et la
      position vaut la moitié de ce que la normalisation par le risque
      donnerait À CE STOP RÉDUIT. Dans un moteur dimensionné par le risque
      (`size_frac = risk_pct / stop_pct`, exactement le cas ici), les deux
      divisions par 2 se COMPENSENT exactement :
          size = (risk / (s/2)) / 2 = risk / s = size standard
      -> la position (l'exposition notionnelle) est INCHANGÉE par rapport à
      la règle standard, et le capital réellement risqué (distance au stop x
      taille) est DIVISÉ PAR DEUX. C'est mot pour mot ce qu'affirme la
      parenthèse de la source : *"(préserve une exposition capital
      constante)"*, et c'est aussi ce que veut dire son intitulé "symétrie
      du risque" (les deux réductions sont symétriques et s'annulent).
  (B) ÉCARTÉE. Le stop passe à la moitié ET la position à la moitié de la
      position STANDARD -> exposition notionnelle divisée par 2, capital
      risqué divisé par 4. Lecture arithmétiquement possible de la phrase
      seule, mais elle CONTREDIT frontalement la parenthèse (l'exposition ne
      serait alors ni constante, ni symétrique). Écartée pour cette raison
      précise, pas par préférence.

  Corollaire d'implémentation (vérifié, pas supposé) : la réduction de
  taille est appliquée à la taille DÉRIVÉE DU RISQUE, AVANT le plafond par
  tranche `1/max_tranches` déjà en place. C'est ce qui rend la propriété
  "exposition constante" exacte MÊME quand ce plafond mord :
      min(cap, risk/(s/2) * 1/2) = min(cap, risk/s)  = taille standard
  alors que l'appliquer après (`1/2 * min(cap, risk/(s/2))`) donnerait une
  exposition réduite dès que le plafond mord -- donc une violation de la
  parenthèse de la source dans exactement les cas les plus volatils. Le code
  ci-dessous écrit malgré tout les DEUX divisions explicitement (plutôt que
  la simplification "ne rien faire sur la taille, resserrer juste le stop"),
  pour rester une transcription littérale de la phrase source et pour que le
  jour où le facteur cesserait d'être 1/2 des deux côtés, le code reste juste.

H-Canal-Large-2 -- DE QUEL CANAL PARLE-T-ON ? Du MÊME canal qui définit déjà
  le stop dans ce projet -- l'"Extreme Channel" EMA(55) ± 2xATR(14)
  (`backtest_phase2_v7.py::prepare`), dont la largeur `ctx_width_pct =
  (2*2*atr)/ema_slow*100` est DÉJÀ calculée là-bas et DÉJÀ consommée par
  `regime_classifier.add_regime`. Aucune nouvelle définition de "canal"
  n'est introduite ici -- principe déjà établi dans ce projet ("même terme
  'contexte'/'canal' = même définition partout, pas une nouvelle par
  module", cf. `fibonacci.py::compute_context_position` qui a réutilisé à
  l'identique `CONTEXT_DURATION="15D"` plutôt que d'en inventer une).
  Précision de scope qui en découle : le canal mesuré est celui qui définit
  le stop DU MOTEUR CONCERNÉ -- le canal H4 natif quand le moteur stoppe sur
  H4 (`backtest_phase2_v7.py`, `use_mtf_stop=False`), le canal D1 (UT+1)
  quand il stoppe sur D1 (`backtest_phase2_faithful.py`, règle littérale du
  stop UT+1). Mesurer la largeur d'un canal autre que celui qui porte le
  stop n'aurait aucun sens pour une règle qui redimensionne CE stop.
  Limite honnête, déjà connue et non aggravée ici : `stop_pct` n'est pas
  littéralement "la taille du canal" mais la distance de l'entrée à la BORNE
  BASSE du canal (approximation en place depuis v4, cf. H4 de
  `trend_table.py`). La règle de volatilité est appliquée à cette distance
  de stop existante (divisée par deux), ce qui est sa transposition fidèle
  À L'INTÉRIEUR de l'approximation déjà en place -- pas une approximation
  nouvelle empilée par-dessus.

H-Canal-Large-3 -- SEUIL "TRÈS LARGE" (aucun chiffre dans le corpus, cf.
  ci-dessus). Retenu : `regime_classifier.compute_wide_channel`, c'est-à-dire
  le percentile glissant CAUSAL (`PCTL_WINDOW=250`, `.shift(1)`) de la MÊME
  série `ctx_width_pct`, au percentile `WIDE_PCTL = 0.80`. Chaîne de
  justification (aucun maillon inventé) :
    1. Il DOIT être strictement en dessous de `EXCESS_PCTL = 0.95` déjà
       utilisé pour EXCES : "Bulle/Excès -> NE PAS TRADER" est une
       ABSTENTION, alors que la règle de volatilité est un
       DIMENSIONNEMENT ("ajusté selon volatilité" dans la checklist). Les
       deux états doivent rester distincts, sinon la règle serait vacueuse
       dans tout moteur qui refuse déjà d'entrer en régime EXCES (ce que
       font tous les moteurs descendants de v7). Vérifié empiriquement sur
       BTC/ETH/BNB/SOL avant de figer le chiffre : au percentile 0,80,
       seules 26% à 40% des bougies "très larges" sont AUSSI en EXCES -- la
       règle porte donc bien majoritairement sur des bougies réellement
       tradables, elle n'est pas un doublon d'EXCES.
    2. Il doit être strictement au-dessus de la seule autre référence de
       largeur du corpus, la *"largeur moyenne du canal de tendance récent"*
       de `TRADING_LESSONS_ZONE_ACCUMULATION.md` : un canal au p80 de sa
       propre distribution récente est par construction plus large que sa
       moyenne récente. 0,80 satisfait cette contrainte, 0,50 non.
    3. Entre les deux, 0,80 est la fréquence la plus grossière que le corpus
       lui-même emploie pour un état de marché DISTINGUÉ (non par défaut) :
       le manuel chiffre ses régimes à Tendance ~20% et Bulle/Excès ~5% ; la
       bande ~5% est déjà prise par EXCES, la bande ~20% est libre. Mesuré :
       le détecteur se déclenche sur 12% à 22% des bougies selon l'actif et
       selon le canal mesuré (H4 natif ou D1) -- cohérent avec cette bande.
  Le seuil reste un PARAMÈTRE (`pctl=` de `compute_wide_channel`), jamais une
  constante enfouie.

  SENSIBILITÉ MESURÉE (même esprit que
  `cluster_technique_threshold_robustness.py`), grille 0,70 / 0,80 (retenu) /
  0,90, BTC/ETH/BNB/SOL x 4 profils, chiffres reproduits ici plutôt que
  renvoyés à un document externe :
    - banc ISOLÉ (`backtest_phase2_v7.py`, `use_wide_channel_halving`, canal
      H4) -- retour moyen vs référence : 0,70 -14,6 pts / 0,80 -13,1 pts /
      0,90 -10,1 pts ; drawdown moyen -0,5 / -0,6 / -0,7 pt. La règle DÉGRADE
      le retour sur 16/16 couples à 0,70 et 0,80, 15/16 à 0,90.
    - `backtest_phase2_faithful.py` (activation inconditionnelle, canal D1) --
      retour moyen : 0,70 -1,9 pt / 0,80 -2,6 pts / 0,90 +0,9 pt ; signe
      mixte selon l'actif (à 0,80 : 4 améliorés / 8 dégradés / 4 inchangés).
    L'effet est MONOTONE en fonction du seuil (moins la règle se déclenche,
    moins elle coûte) -- ce qui confirme que l'écart mesuré est bien imputable
    à la règle et non à du bruit.
  AVERTISSEMENT DE MÉTHODE, explicite : 0,80 n'est PAS le meilleur des trois
  chiffres mesurés (0,90 l'est). Le seuil a été arrêté AVANT toute mesure, sur
  la chaîne de justification 1-2-3 ci-dessus (cohérence avec les définitions
  de canal déjà en place), et il n'est PAS révisé au vu du résultat : choisir
  un paramètre de l'IP de Philippe pour la performance du proxy est exactement
  le raisonnement que ce projet s'interdit ("nous ne nous fions pas aux
  résultats du Proxy pour décider d'utiliser ou non la propriété
  intellectuelle de Philippe, nous l'utilisons dans tous les cas").

H-Canal-Large-4 -- PÉRIMÈTRE : table RANGE seulement (ce fichier), PAS la
  table TENDANCE (`trend_table.py`). Ce n'est pas un oubli : la source #5
  s'intitule *"Gradient de Risque et Anatomie du Range"*, son §1 est
  *"Anatomie du pattern range"*, et le §5 qui porte cette règle donne des
  objectifs explicitement typés range (*"Range Neutre = 76% Fibonacci de la
  vague précédente ; Range Vendeur/Acheteur = débordement du point extrême
  précédent"*). Le stop y est indexé sur le canal DE TENDANCE, mais pour un
  trade DE RANGE -- exactement l'architecture de ce fichier (table "trade
  spéculatif (range)", `RULES_EXTRACTION.md` §3), pas celle de
  `trend_table.py` (table "trade de tendance", §4). Étendre la règle à
  `trend_table.py` exigerait EN PLUS de trancher comment un stop divisé par
  deux interagit avec ses propres unités de sizing (H1, "Renfort +X% de U")
  et son plafond de risque de campagne (H3) -- une seconde décision de
  conception que le corpus ne tranche nulle part. Laissée explicitement hors
  périmètre et documentée ici, plutôt qu'appliquée en silence par analogie.

================================================================================
"RED FLAGS D'INVALIDATION PRÉCOCE" (#10) -- EXAMINÉS ET DÉLIBÉRÉMENT PAS
AJOUTÉS ICI. Note DOCUMENTAIRE (aucun comportement, aucune constante) --
même discipline que la note H7 de `trend_table.py` : la trouvaille doit être
visible par le lecteur du fichier concerné, pas seulement dans les documents
de suivi. Décision complète, chiffres et citations : `PLAN.md` section
"9e application", `COUVERTURE_ENSEIGNEMENTS.md` (section "Audit exhaustif du
corpus complet", item "Red Flags d'invalidation précoce").
================================================================================
Citation exacte (`TRADING_LESSONS_ZONE_ACCUMULATION.md` lignes 44-47, il y en
a exactement TROIS) :

    ## Signaux d'invalidation précoce ("Red Flags")
    - Clôtures du contexte sous la MA20
    - Retracement profond : clôture maintenue au-delà de 61% de la structure
    - Retour au contexte opposé : atteinte de la borne extérieure opposée du
      range initial

Ce qu'il faut savoir en lisant CE fichier, dans l'ordre d'importance :

1. CE MOTEUR A DÉJÀ UN MÉCANISME D'INVALIDATION PRÉCOCE, et ce n'est pas le
   stop -- c'est l'étape 3 de `process_tranche` (« Sortie de signal (flip)
   avant toute étape »), qui ne s'applique QUE tant que `val_done` et
   `conf_done` sont faux, donc précisément "précocement". C'est déjà le canal
   par lequel les règles d'abstention littérales du corpus (EXCES-H4, gate
   UT+2 Hebdomadaire, Conflit MTF D1) FERMENT une tranche déjà ouverte, via
   `gated_long_signal` -- cf. la note dédiée en tête de
   `backtest_phase2_faithful.py`. Mesuré sur les 4 388 trades de `faithful.py`
   (BTC/ETH/BNB/SOL x 4 profils, historique complet) : FLIP 93,8% / LIMITE
   3,8% / STOP 2,4% des sorties. L'affirmation de l'audit du 5e round (« pas
   de mécanisme distinct du stop de protection standard ») était donc FAUSSE,
   et elle est corrigée dans les documents de suivi. Si les Red Flags devaient
   un jour être implémentés, l'endroit juste est ce canal-là (le `gate()` de
   l'appelant), PAS une 6e branche dans `process_tranche`.

2. Le Red Flag « retour au contexte opposé » est un DOUBLON BIT-À-BIT de
   l'étape 2 ci-dessous, et il est PROUVÉ NON PRÉCOCE. Le stop est déjà posé
   exactement à ce niveau (`stop_price = min(ctx_support_v[j], entry*0.999)`,
   `ctx_support_d1` = borne basse du canal de contexte UT+1) et déclenché sur
   la MÈCHE, ce qui est mot pour mot « atteinte de la borne extérieure
   opposée ». Vérifié empiriquement, pas déduit : la branche `entry*0.999` du
   `min()` ne mord JAMAIS (0/4 388 trades) ; le niveau est atteint par 24
   trades seulement, et dans 24/24 cas la bougie de déclenchement EST la
   bougie de sortie réelle -- 0/4 388 trade sortirait plus tôt. La seule
   variante qui sortirait vraiment plus tôt (relire `ctx_support` EN DIRECT à
   chaque bougie au lieu de le figer à l'entrée) est un stop suiveur sur la
   bande de contexte : elle contredit frontalement la règle la mieux étayée de
   tout le corpus (interdiction de resserrer / passer au break-even avant la
   Confirmation -- sources #12/#13/#15/#16 nommées, #16 s'annonçant lui-même
   comme la « 5e/6e confirmation » -- déjà encodée par `conf_to_be` et par
   l'ordre séquentiel des étapes 4/5 ci-dessous). Écartée pour cette raison
   précise, pas par préférence.

3. Le Red Flag « clôture maintenue au-delà de 61% » est DÉJÀ implémenté, deux
   fois, mais comme plafond d'ENTRÉE, pas de sortie :
   `trend_table.py::ACCUM_RETRACEMENT_HIGH = 0.61` et
   `fibonacci.py::FAVORABLE_MAX = 0.618` (dont le commentaire cite déjà ce
   Red Flag nommément). En faire EN PLUS une condition de sortie ici serait un
   TROISIÈME usage du même chiffre, alors que le corpus l'emploie comme
   MINIMUM d'entrée dans trois autres passages (`RULES_EXTRACTION.md` §1
   "Range tendanciel ... >=61,8%" ; #5 "entrée agressive possible dès 61%
   Fibonacci" ; #11 "zone d'intervention à Fibonacci 61,8%") -- même chiffre,
   inégalité INVERSE, référentiels différents. C'est exactement le piège déjà
   documenté pour le 76% (« seuil d'ENTRÉE ici, cible de SORTIE ailleurs --
   deux règles distinctes à ne jamais confondre »). En outre le mot
   "maintenue" n'est chiffré NULLE PART dans le corpus : l'implémenter
   exigerait d'inventer ce paramètre, motif de refus déjà retenu pour le gate
   Fibonacci RANGE §1.

4. Le Red Flag « clôtures du contexte sous la MA20 » est le SEUL des trois qui
   ne soit ni redondant ni déjà codé -- il reste au backlog catégorie C, pas
   ici. Il dispose d'une 2e source plus précise (`TRADING_LESSONS_CLUSTERS_
   PRIX.md:50`, #16, section « Règle de Trois (invalidation statistique) » :
   "clôtures multiples et marginales sous la moyenne mobile"), mais : (a) dans
   cette section de #16, les deux puces voisines énoncent leur conséquence et
   c'est "prudence maximale" (déjà implémentée -- `rule3_streak`/
   `rule3_size_mult` ci-dessous) et "arrêt des NOUVEAUX ENGAGEMENTS", donc une
   abstention, pas la fermeture d'une position ouverte ; (b) "multiples" et
   "marginales" sont deux paramètres à inventer ; (c) les deux sources placent
   la MA20 sur des unités de temps DIFFÉRENTES (#10 dit "clôtures DU
   CONTEXTE", le tableau de #16 est calé sur "Unité de Temps de Trading |
   Horaire (H1)") ; (d) le projet contient déjà TROIS "moyennes 20 périodes"
   distinctes, à ne jamais confondre -- `cluster_technique.py::
   compute_ma20_rebound` (MA20 de PRIX, UT d'exécution, signal d'ENTRÉE,
   exige la clôture AU-DESSUS), `trend_table.py` H9 (MA20 de VOLUME,
   confirmation de breakout) et celle de ce Red Flag (MA20 de prix, sur le
   CONTEXTE, clôture EN DESSOUS, invalidation) : même piège terminologique que
   celui déjà documenté pour "Cluster technique".
================================================================================

================================================================================
"RÈGLE D'OR : CALCULS SUR CLÔTURES, JAMAIS SUR LES MÈCHES" (#15) vs
`local_range`/`context_range` -- EXAMINÉE ET DÉLIBÉRÉMENT PAS APPLIQUÉE AUX
AMPLITUDES. Note DOCUMENTAIRE (aucun comportement, aucune constante), même
discipline que le bloc "RED FLAGS" ci-dessus : la décision doit être visible
par le lecteur de CE fichier, pas seulement dans les documents de suivi.
Décision complète, chiffres et citations : `PLAN.md` section "10e application",
`COUVERTURE_ENSEIGNEMENTS.md` (catégorie C, item "règle d'or (#15)").
================================================================================
Cette note REMPLACE la "TENSION OUVERTE, NON RÉSOLUE" qui était écrite plus
bas dans `make_open_tranche_fn` au 8e round : la tension est tranchée.

Citation exacte, relue mot pour mot (`TRADING_LESSONS_PYRAMIDALISATION.md`,
source #15) -- ligne 20 (titre de section), ligne 22, ligne 39 :

    ## Patterns de pyramidalisation (règle d'or : calculs sur clôtures,
    jamais sur les mèches)
    **Variante 1 -- 3ème borne de range classique** : ... validation au
    ratio 1:1 (report de l'amplitude du range en clôture).
    - **Phase 1 (3-6 mois)** : ... identification visuelle des patterns et
    ratios de validation en clôture

L'item du 8e round demandait de basculer `local_range`/`context_range`
(`backtest_phase2_v7.py::prepare` : `max(high) - min(low)` sur 5D/15D) en
`max(close) - min(close)`. NON FAIT, pour 5 raisons vérifiées une par une.

R1. LA CITATION EST RÉELLE MAIS SON OBJET EST AMBIGU, et le 8e round n'a
    retenu qu'une des deux lectures du complément "en clôture" :
      (a) l'AMPLITUDE se mesure sur les clôtures -- lecture de l'item ;
      (b) la VALIDATION du ratio 1:1 se constate sur une clôture (pas sur
          une mèche) -- lecture au moins aussi naturelle, appuyée par la
          ligne 39 ("ratios DE VALIDATION en clôture") et par la formule du
          titre ("jamais sur les mèches"), qui est la tournure stock du
          corpus pour "ne pas valider sur une mèche" (#11:22 *"pas un simple
          dépassement intra-bougie"* ; #14:28 *"les clôtures ... pour
          VALIDER la structure"*).
    La lecture (b) est DÉJÀ IMPLÉMENTÉE, exactement : `process_tranche`
    ci-dessous déclenche Limite/Confirmation/Validation sur `c[i] >= ...`
    (`PHASE2_CORRECTION_CLOSES.md`). Et c'est déjà la lecture que le projet
    applique à cette phrase : le 8e round a lui-même rétabli #15 parmi les
    sources de la correction des DÉCLENCHEMENTS. L'item revenait donc à
    faire porter DEUX FOIS la même phrase, sur deux mécanismes différents.

R2. LA LECTURE (a) CONTREDIT LA CONVENTION QUE LE CORPUS ÉNONCE PARTOUT
    AILLEURS -- "le NIVEAU / la STRUCTURE vient des extrêmes, la CLÔTURE est
    le TEST" -- vérifiée dans 5 passages distincts, tous relus :
      - #14 `STRUCTURES_ALTERATIONS.md:28` -- *"zone de tolérance, pas une
        ligne mathématique -- les mèches peuvent pénétrer l'ancien
        territoire, mais les clôtures de bougies doivent rester à
        l'extérieur pour valider la structure"* (l'énoncé le plus net) ;
      - #16 `CLUSTERS_PRIX.md:30` -- *"sous le dernier creux structurel (bas
        de clôture OU mèche)"* : le corpus refuse explicitement de trancher ;
      - #10 `ZONE_ACCUMULATION.md:38` -- *"sous le POINT BAS de la 4ème
        borne"* ;
      - #5 `MAITRISE_GRADIENT_RISQUE.md:56` -- *"Objectifs : Range Neutre =
        76% Fibonacci de la vague précédente ; Range Vendeur/Acheteur =
        DÉBORDEMENT DU POINT EXTRÊME PRÉCÉDENT"* : c'est la SEULE phrase du
        corpus qui dise comment se mesure un OBJECTIF de trade de range --
        donc l'étape Limite, donc `lim_px` -- et elle dit "point extrême",
        pas "clôture" ;
      - `RULES_EXTRACTION.md:41` (le manuel officiel) -- *"Confirmation
        (médiane canal contexte, CLÔTURÉE)"* : "clôturée" qualifie la façon
        de CONSTATER le franchissement d'un niveau structurel, pas la façon
        de mesurer ce niveau.
    C'est exactement le raisonnement par lequel le 8e round a lui-même
    REFUSÉ de détecter les bornes par clôtures. Adopter (a) ici retiendrait
    la lecture INVERSE pour le même type d'objet (l'écart entre deux
    extrêmes structurels).

R3. LA LECTURE (a) CASSE LA FINALITÉ QUE LA SOURCE DU MÉCANISME LUI ASSIGNE,
    ET C'EST MESURÉ. Le mécanisme codé (`val_px = entry + local_range`) vient
    de #12 `BREAKOUT_RATIO11.md:8` -- *"Phase de Validation (Ratio 1:1
    Tendance) : projeter l'amplitude du range d'accumulation local (UT).
    Objectif = 'payer son stop loss' -- prise de profit partielle ... finance
    statistiquement le risque initial. Le trade devient 'gratuit'"*. #12 ne
    dit RIEN sur clôtures vs mèches (vérifié), mais il donne un critère
    testable : la cible de Validation doit valoir ~1 R. Mesuré sur
    BTC/ETH/BNB/SOL H4, `(val_px - entry) / (entry - stop_D1)`, médiane :
        mèches   0,88 / 0,91 / 0,91 / 1,06   <- déjà calé sur le 1:1 de #12
        clôtures 0,69 / 0,71 / 0,72 / 0,85
    et part des bougies où R < 1 : 48-54% -> 55-62%. La lecture (a) ÉLOIGNE
    la Validation du 1:1 dont #12 fait la définition même de l'étape : elle
    dégrade la fidélité au lieu de l'améliorer.

R4. REQUALIFICATION VERS `trend_table.py` EXAMINÉE ET ÉCARTÉE : il n'y a
    rien à y requalifier. #15 décrit bien la pyramidalisation post-breakout
    en contexte de TENDANCE, mais (i) la pyramidalisation de ce projet est
    ICI (`MAX_TRANCHES=3`, `is_pyramid_add`), pas dans `trend_table.py`, qui
    l'exclut explicitement (son H12 : *"pas de pyramidalisation de PLUSIEURS
    campagnes ... contrairement à v4-v7 (`MAX_TRANCHES=3` sur des ENTRÉES
    indépendantes)"*) ; et (ii) `trend_table.py` n'a AUCUNE projection
    d'amplitude 1:1 -- ses étapes sont, de son propre aveu, *"des ÉVÉNEMENTS
    DE STRUCTURE DE MARCHÉ détectés ..., pas des niveaux de prix fixes issus
    de l'entrée"* (vérifié par grep : il ne consomme ni `val_px` ni
    `local_range`, seulement `ctx_high`/`ctx_low`/`local_high`). La règle
    d'or n'a donc aucune cible dans ce fichier.

R5. #15 N'APPLIQUE PAS LUI-MÊME "jamais sur les mèches" À SES PROPRES
    NIVEAUX D'ORDRE : sa Variante 1 entre par un *"ordre 'Stop Achat' au
    niveau de la borne validée"* (un stop d'achat se remplit INTRABAR, donc
    sur une mèche) et sa Variante 2 place son stop *"sous le dernier support
    significatif"*. C'est précisément la convention déjà codée dans ce
    fichier (stop sur la MÈCHE = ordre réel intrabar, cible sur la CLÔTURE,
    cf. H-Reverse-Range). La règle d'or porte sur la lecture/validation de
    la structure, pas sur la mesure des extrêmes.

MESURES FAITES QUAND MÊME, pour ne pas décider à l'aveugle (monkeypatch
jeté, aucun moteur modifié) :
  - Ratio amplitude clôtures/mèches, REVÉRIFIÉ personnellement et conforme
    au 8e round : médiane 0,786-0,808 (`local_range` H4), 0,862-0,876
    (`context_range` H4), 0,552-0,578 / 0,720-0,752 en D1.
  - Impact backtest complet si (a) était appliquée (BTC/ETH/BNB/SOL x 4
    profils, un seul paramètre changé) : `backtest_phase2_v7.py` retour
    +6,2 pts en moyenne mais 10/16 couples DÉGRADÉS (moyenne tirée par le
    seul BTC/TRES_AGRESSIF, +72 pts), drawdown -2,21 pt (plus profond),
    -10 trades ; `backtest_phase2_faithful.py` retour -0,9 pt, 9/16
    dégradés, drawdown -1,38 pt, -13,6 trades. Signe mixte, drawdown
    systématiquement plus profond -- la performance ne tranche pas, et de
    toute façon ce projet s'interdit de trancher là-dessus.
  - Invariante `val_px <= conf_px <= lim_px` : PRÉSERVÉE par construction
    dans les DEUX définitions (fenêtre 5D incluse dans 15D => amplitude
    locale <= amplitude contexte), 0 violation sur 55 171 bougies. Seul
    artefact de (a) : exactement 1 bougie par actif où
    `max(close)-min(close) = 0` (première barre, fenêtre d'une seule
    bougie) -- déjà filtrée par la garde `local_range_v[j] > 0` de
    `valid_inputs` ci-dessous, et située très avant `warmup`.
  - Fenêtre de mesure : le corpus ne donne AUCUN chiffre de fenêtre pour ces
    amplitudes (grep exhaustif "amplitude"/"projeter"/"report" sur les 17
    sources + `RULES_EXTRACTION.md` : uniquement #12:8-9 et #15:16/22/24,
    sans aucune durée). `LOCAL_DURATION`/`CONTEXT_DURATION` restent donc
    l'hypothèse en place, inchangée.

ITEM COMPAGNON TRANCHÉ EN MÊME TEMPS, ET PAS DANS LE SENS ANNONCÉ :
`fibonacci.py::compute_retracement` n'est PAS un "hybride mèches/clôtures"
accidentel -- c'est la transcription exacte de la convention R2. Cf. la note
dédiée en tête de `code/fibonacci.py`.

TROUVAILLE ANNEXE, non traitée ici (nouvel item de backlog) : le coefficient
`1.5` de `lim_px = entry + 1.5 * context_range` ci-dessous n'a AUCUNE source
dans le corpus (grep exhaustif : aucun "1,5" appliqué à un objectif) et
n'est documenté NULLE PART, alors qu'il est recopié en littéral dans 7
fichiers. Le corpus donne pourtant deux définitions littérales de l'objectif
d'un trade de range (#5:56, citée en R2), typées par régime -- non
implémentables telles quelles (elles exigent "76% Fibonacci de la vague
précédente" et un "débordement du point extrême précédent", cf. le piège du
76% déjà documenté dans `CONFIGURATION_RECOMMANDEE.md` §5quinquies), mais
c'est le paramètre inventé le moins tracé de ce fichier.
================================================================================
"SIZING 1-1,5% / R:R 1:5 SPÉCIFIQUE AUX TRADES D'ACCUMULATION" (#10) --
INVESTIGUÉ À LA 17e APPLICATION, PAS IMPLÉMENTÉ. Note DOCUMENTAIRE
(aucun comportement, aucune constante), même discipline que la note "Red
Flags" ci-dessus. Décision complète : `PLAN.md` section "17e
application", `COUVERTURE_ENSEIGNEMENTS.md`, `STATUS.md`.
================================================================================
CITATIONS, VÉRIFIÉES MOT POUR MOT (`TRADING_LESSONS_ZONE_ACCUMULATION.md`,
seule source du corpus à porter ces deux nombres -- grep exhaustif "1:5",
"1,5 %", "R:R", "sizing", "taille de position" sur les 17 sources +
`RULES_EXTRACTION.md`) :

    :36  - **Taux de réussite moyen accepté : 50%** (nombreux trades
           clôturés à Break-Even) en échange d'un **ratio R:R élevé, cible
           moyenne 1:5**
    :37  - Taille de position en conséquence : **1 à 1,5% du capital**
           (modérée, car l'espérance de gain est déjà élevée grâce au R:R)
    :50  *"Tenir une position à Break-Even sans céder à la tentation
         d'encaisser prématurément de petits gains est le prix à payer pour
         capturer les tendances majeures qui offrent des ratios SUPÉRIEURS
         À 1:5."*

Précision de statut, qui pèse dans tout ce qui suit : :36 et :37 sont des
PUCES DE SYNTHÈSE (pas de guillemets, pas de bloc `>`), :50 est la SEULE
citation verbatim -- et c'est celle qui dit "supérieurs à".

A. L'ITEM SE TROMPE DE SOURCE, ET SUR LE MOT "SPÉCIFIQUE".
   L'énoncé de l'item soupçonnait `MAITRISE_GRADIENT_RISQUE.md` (#5) : #5 ne
   contient NI "1:5" NI "1-1,5%" (vérifié) -- son sizing est "Stop Loss =
   taille du canal" + "/2 si canal très large", déjà implémenté ici
   (`WIDE_CHANNEL_STOP_FRAC`/`WIDE_CHANNEL_SIZE_FRAC`). Surtout, AUCUN des
   chiffres de sizing du corpus n'est scopé par TYPE DE TRADE ; ils sont
   scopés par EXPÉRIENCE ou par UNITÉ D'AGRÉGATION :
     - `RULES_EXTRACTION.md:63` (manuel)  jamais >5% du capital, tous profils
     - `RULES_EXTRACTION.md:64` (manuel)  <=1% pendant les 6 premiers mois
     - `RULES_EXTRACTION.md:65` (manuel)  gradient expérience x profil
                                          psychologique, table à 4 niveaux
     - #15:28   max 2% de risque PAR POSITION (nominal)
     - #15:40-41  0,5% (apprentissage) -> 2% (expertise)
     - #16:40-41  jamais >2% PAR ZONE DE PRIX ; 1% + 1% sur deux patterns
     - #10:37   1 à 1,5%
   Le "spécifique à l'accumulation" est un artefact du document où la puce se
   trouve, pas une clause du texte : #10:37 donne lui-même sa raison, et elle
   n'est pas le type de trade -- *"car l'espérance de gain est déjà élevée
   grâce au R:R"*. Le sizing y est indexé sur le R:R, pas sur l'accumulation.

B. LE SIZING EST DÉJÀ COUVERT SOUS UN AUTRE NOM (motif (d)), ET C'EST MESURÉ,
   PAS AFFIRMÉ. Le profil FAIBLE vaut `risk_pct = 0.01` -- exactement la borne
   basse de la fourchette [1% ; 1,5%] de #10:37, et exactement le <=1% que le
   manuel recommande. Forcer `risk_pct = 0.010` sur les 4 profils de
   `backtest_phase2_v7.py` est un NO-OP BIT-À-BIT sur exactement les 4 couples
   FAIBLE (BTC/ETH/BNB/SOL, écart de rendement 0,0 pt, 0 trade d'écart) : la
   borne basse de #10 est littéralement déjà en production.

C. IMPLÉMENTER LE SIZING SACRIFIERAIT DEUX MÉCANISMES MIEUX ÉTABLIS (motif
   (c)), tous deux issus du MANUEL (autorité la plus haute), contre une puce
   non-verbatim d'UNE source vidéo :
   C1. `RULES_EXTRACTION.md:54-59` §4 donne DÉJÀ le sizing de l'étape
       Accumulation, profil par profil -- "Attente / Renfort +25% / +50% /
       +100%" -- et il est implémenté tel quel dans
       `trend_table.py::PROFILES_TREND` (`accum_frac` = 0.00 / 0.25 / 0.50 /
       1.00, correspondance exacte des 4 lignes). Un 1-1,5% fixe à
       l'accumulation ÉCRASERAIT cette ligne du manuel et rendrait les 4
       profils identiques à cette étape -- il supprimerait notamment
       l'"Attente" de FAIBLE et le "+100%" de TRES_AGRESSIF.
   C2. `RULES_EXTRACTION.md:65-66` fait de l'agressivité une fonction de
       l'EXPÉRIENCE, du PROFIL PSYCHOLOGIQUE et du PALIER DE CAPITAL --
       mécanisme porté par le choix de profil utilisateur et par
       `capital_tiers.py` (qui se refuse explicitement à "modifier le choix de
       profil de risque fait par l'utilisateur"). Un littéral 1-1,5% câblé
       dans le moteur retirerait ce choix.

D. "R:R 1:5" N'EST PAS EN CONFLIT AVEC LE RATIO 1:1 -- LE SOUPÇON DE L'ITEM
   EST INFIRMÉ PAR LE CORPUS LUI-MÊME. Le "Ratio 1:1" de #12:8-9
   (`BREAKOUT_RATIO11.md`) n'est pas un ratio risque/récompense : c'est le
   REPORT D'AMPLITUDE d'un range (`val_px = entry + local_range`), et #15:24
   le dit expressément -- *"Le ratio 1:1 n'est pas un objectif de profit mais
   un point de validation mathématique du trade."* Un point de validation à
   1:1 et un ratio de sortie à 1:5 sont deux objets compatibles. Le conflit
   redouté par l'énoncé de l'item N'EXISTE PAS, et n'est donc PAS le motif de
   non-implémentation retenu ici.

E. LE VRAI MOTIF SUR LA MOITIÉ "R:R 1:5" : (b) puis (c).
   E1. (b) LE "5" N'EST PAS TRANSPOSABLE : il n'a de sens que relativement au
       stop de #10, et ce n'est pas le stop de ce moteur. #10:38 définit son
       propre stop -- *"largeur moyenne du canal de tendance récent, OU sous
       le point bas de la 4ème borne"* -- deux définitions, la source ne
       tranche pas. Le moteur, lui, utilise l'"Extreme Channel" UT+1 (#16:28 +
       #12:7, deux sources concordantes, mieux établi). Or le R dépend
       entièrement de ce choix -- MESURÉ sur les bougies d'entrée réelles
       (BTC/ETH/BNB/SOL H4, gate MTF v7), médianes :
                                   stop H4 natif      stop D1 (UT+1)
           Validation   (val_px)      1,21-1,26 R        0,53-0,58 R
           Confirmation (conf_px)     1,93-2,10 R        0,90-0,93 R
           Limite       (lim_px)      2,89-3,15 R        1,35-1,40 R
       Le MÊME niveau vaut 3,15 R ou 1,40 R selon le stop : un facteur 2,3.
       Transplanter le nombre 5 de #10 sur un dénominateur que #10 n'emploie
       pas ne serait pas une implémentation littérale, ce serait un chiffre
       recalé sur un autre objet.
   E2. (c) #10:50 -- la SEULE citation verbatim -- demande de capturer des
       ratios *"SUPÉRIEURS à 1:5"*. Un take-profit dur à 5 R rendrait ">5 R"
       impossible par construction : il contredirait la phrase dont il est
       tiré. La lecture fidèle de #10:50 serait de RETIRER le plafond, pas de
       le fixer à 5 -- et retirer le plafond supprimerait l'étape "**Limite**
       (target atteinte) -> TP100%" que `RULES_EXTRACTION.md:41` et la table
       :43-48 prescrivent explicitement pour les 4 profils. Manuel contre puce
       vidéo : le manuel prime.
   E3. #15:30 donne d'ailleurs un AUTRE nombre pour le même type d'énoncé --
       *"ratio moyen visé 1:4"* -- et #15:31 *"l'expert vise à terme le 1:4
       complet"*. Deux sources, deux valeurs (1:4 et 1:5), toutes deux
       formulées comme des moyennes visées. Retenir 5 plutôt que 4 serait
       arbitraire.

F. LE PROCESSUS de #10 EST DÉJÀ IMPLÉMENTÉ, LUI. #10:39-42 ("Connective
   Tissue") -- Validation -> stop réduit ; Confirmation -> Break-Even ;
   *"transformer le trade en 'option gratuite'"* -- est exactement l'échelle
   `val_px` / `conf_px` / `conf_to_be` de `process_tranche` ci-dessous. Ce que
   l'item ajoutait, ce sont les deux ANNOTATIONS CHIFFRÉES de ce processus,
   pas le processus.

G. MESURES FAITES QUAND MÊME, POUR NE PAS DÉCIDER À L'AVEUGLE (monkeypatch
   jeté, aucun moteur modifié ; v7, 4 actifs x 4 profils, un seul paramètre
   changé à la fois) :
     - "R:R 1:5" (`lim_px = entry + 5*(entry-stop)`) : rendement moyen
       +3,71 pt, 12/16 couples AMÉLIORÉS, 4/16 dégradés, drawdown moyen
       +0,74 pt (moins profond), -7,2 trades, win rate -0,17 pt. Dispersion
       énorme : ETH/TRES_AGRESSIF -70,9 pt, BTC/TRES_AGRESSIF +50,9 pt.
     - risk_pct forcé à 1,0% : -51,94 pt de moyenne, 12/16 dégradés, 4/16
       IDENTIQUES (les 4 FAIBLE, cf. B).
     - risk_pct forcé à 1,5% : -35,61 pt de moyenne, 12/16 dégradés.
   /!\\ À LIRE CORRECTEMENT : la variante "R:R 1:5" est mesurée LÉGÈREMENT
   FAVORABLE. Elle n'est donc PAS écartée pour cause de dégradation -- ce
   projet s'interdit ce motif -- mais elle n'est pas non plus retenue PARCE
   QU'elle améliore : la règle du projet interdit symétriquement de laisser le
   Proxy décider de la fidélité au corpus. Les motifs sont E1 (b) et E2 (c),
   et eux seuls. Le sens du chiffre est reporté ici uniquement pour que la
   décision soit vérifiable et non aveugle.

H. CE QUE CETTE INVESTIGATION APPORTE AU BACKLOG (et qu'elle ne referme pas) :
   la 17e application a testé #10:36 comme source possible du
   coefficient `1.5` de `lim_px`, signalé SANS SOURCE au 12e round et recopié
   en littéral dans 7 fichiers. RÉPONSE : NON, #10:36 n'en est pas la source
   -- les deux grandeurs ne sont pas dans la même unité (`1.5` multiplie un
   `context_range`, "1:5" multiplie un RISQUE), et la conversion n'est pas
   stable : pour que `lim_px` vaille 5 R il faudrait un coefficient médian de
   2,38-2,60 sur le stop H4 natif, mais de 5,38-5,57 sur le stop D1 (UT+1).
   Le `1.5` reste donc un paramètre inventé, non tracé, et l'item de backlog
   correspondant reste OUVERT.
================================================================================

================================================================================
"CONFIRMATION = MÉDIANE DU CANAL DE CONTEXTE, CLÔTURÉE" (RULES_EXTRACTION.md
§3 + source #5) -- NIVEAU STRUCTUREL ABSOLU relu EN DIRECT, par opposition à
la distance `entry + context_range` FIGÉE à l'entrée. Item de catégorie C
requalifié au 7e round de mobilisation, traité à la 16e. IMPLÉMENTÉ
ici (mécanisme réel, testé, mesuré) mais DÉSACTIVÉ PAR DÉFAUT -- pour un
motif de FIDÉLITÉ AU CORPUS mesuré, jamais de performance (H-Conf-Struct-5).
Décision complète et chiffres : `PLAN.md` section "16e application",
`COUVERTURE_ENSEIGNEMENTS.md`, `CONFIGURATION_RECOMMANDEE.md`.
================================================================================
CITATIONS, VÉRIFIÉES PERSONNELLEMENT MOT POUR MOT (relecture intégrale des
deux sources + grep, aucune confiance dans la classification déjà écrite) :

  `RULES_EXTRACTION.md` ligne 41 -- LE MANUEL OFFICIEL, autorité la plus
  haute du projet, et c'est LA table que ce fichier implémente (§3 "Money
  management -- Trade spéculatif (range)") :

      4 étapes : **Validation** (borne opposée canal tendance) ->
      **Confirmation** (médiane canal contexte, clôturée) ->
      **Invalidation** (cassure forte canal tendance) -> **Limite** (target
      atteinte)

  `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` ligne 55 (#5, §5 "Gestion
  tactique", sous-titre "Phases de la position") -- corroboration
  INDÉPENDANTE, et plus précise encore que le manuel puisqu'elle CHIFFRE la
  médiane et QUALIFIE l'étape de "structurelle" :

      - Validation (tactique) : atteinte du canal de tendance opposé ->
        sécuriser (breakeven ou réduction du risque)
      - Confirmation (structurelle) : clôture d'une bougie sous/au-dessus
        la médiane (50%) du contexte
      - Objectifs : Range Neutre = 76% Fibonacci de la vague précédente ;
        Range Vendeur/Acheteur = débordement du point extrême précédent

Les deux sources sont RANGE-scopées (le manuel l'écrit dans le titre de §3 ;
#5 s'intitule "Anatomie du Range", son §1 est "Anatomie du pattern range" --
et ce projet a DÉJÀ retenu ce scope pour CETTE source exacte, cf.
H-Canal-Large-4 ci-dessus). La lecture concurrente actuellement codée
(`conf_px = entry + context_range`, une AMPLITUDE PROJETÉE figée) vient de
#12 `BREAKOUT_RATIO11.md:9` (*"Phase de Confirmation (Ratio 1:1 Contexte) :
utiliser l'UT+2 pour projeter l'amplitude du range de contexte principal"*)
et de #15, deux sources BREAKOUT/TENDANCE. Recompté personnellement sur les
6 sources qui disent quelque chose de l'étape Confirmation : **4
structurelles** (manuel §3:41 ; #5:55 ; #13 `PULLBACK_MATURITE.md:9`,
*"Confirmation : le prix retourne et clôture dans le contexte opposé"* ;
#10 `ZONE_ACCUMULATION.md:41`, *"Confirmation : clôture franche à
l'intérieur du contexte OU sortie confirmée du range de départ -> position
mise à Break-Even"*) contre **2 en amplitude projetée** (#12:9 ; #15:22 et
:28). Le décompte "4 sur 6" du 7e round est donc JUSTE, mais sa LISTE était
fausse d'un membre : il citait #16 `CLUSTERS_PRIX.md`, qui ne définit
structurellement que la **Validation** (l.29, *"Validation : atteinte du
contexte vendeur opposé (résistance)"*) et ne donne AUCUN niveau pour la
Confirmation ; la 4e source structurelle réelle est #10.

--------------------------------------------------------------------------
H-Conf-Struct-1 -- QUEL CANAL ? Le canal de contexte DÉJÀ défini par ce
  projet, jamais un nouveau : `[ctx_low, ctx_high]` = min/max glissant sur
  `CONTEXT_DURATION` ("15D") avec `.shift(1)` causal -- la construction
  exacte de `trend_table.py::add_trend_context` ET de
  `fibonacci.py::compute_context_position`, cette dernière ayant DÉJÀ
  tranché la même question de vocabulaire ("Le contexte ... est interprété
  comme LE MÊME canal de contexte déjà établi par `trend_table.py` ... PAS
  une nouvelle définition inventée ici"). Sa médiane est
  `(ctx_high + ctx_low) / 2`, c'est-à-dire très exactement le niveau où
  `fibonacci.py::compute_context_position == 0.50` -- ce projet manipule
  donc déjà ce niveau sous un autre nom (`REGLE_50_CONTEXT_MIN = 0.50`,
  "moitié basse du canal"), mais pour une règle DIFFÉRENTE (le Pull-Back de
  §1, pas la Confirmation de §3) : ce n'est donc PAS un doublon.
  **Aucune définition ni aucun paramètre inventé** : le "50%" est donné
  littéralement par #5, la fenêtre est celle déjà en place partout.

H-Conf-Struct-2 -- CAUSALITÉ / INDEXATION. Le niveau est lu à `[i - 1]`
  (`ctx_median_v[i - 1]`) et comparé à `c[i]` par `process_tranche` -- MÊME
  convention que `trend_table.py::excess_raw` (`c[i] > ctx_high_v[i - 1]`),
  pas une convention nouvelle. Comme `ctx_median` porte DÉJÀ un `.shift(1)`
  interne, le canal n'utilise aucune bougie postérieure à `i - 2` : double
  marge, aucun lookahead possible. Le déclenchement reste SUR CLÔTURE
  (`c[i] >= tr["conf_px"]`, inchangé), ce qui est exactement le mot
  "clôturée" du manuel et le "clôture d'une bougie" de #5.

H-Conf-Struct-3 -- NIVEAU INCONNU (NaN) -> `conf_px = +inf` : un niveau non
  encore calculable ne peut pas être déclaré atteint. Même convention que le
  gate "espace libre" de `trend_table.py` (H15, *"un niveau inconnu (NaN)
  fait ÉCHOUER le gate"*), transposée à une cible. N'arrive qu'à la toute
  première bougie (`.shift(1)` sans historique), très en amont du `warmup`
  de tous les moteurs.

H-Conf-Struct-4 -- ARCHITECTURE : AUCUNE REFONTE, ET UNE PRÉMISSE DU 7e
  ROUND CORRIGÉE. Ce round avait écrit que *"`position_engine.py` ne
  recalcule aujourd'hui aucun seuil après l'ouverture"* -- c'est FAUX :
  `run_position_engine` expose depuis le refactor d'origine un hook
  `update_levels_fn(tr, i)`, appelé pour chaque tranche ouverte AVANT
  `process_tranche`, et ce hook est EXERCÉ EN PRODUCTION par
  `backtest_phase2.py` (qui recalcule Validation/Confirmation/Limite à
  chaque pas depuis l'ATR courant). Un niveau ABSOLU relu en direct passe
  donc par ce hook **sans toucher une seule ligne de `process_tranche`** :
  les latches one-shot `val_done`/`conf_done` fonctionnent tels quels contre
  un niveau MOBILE ("le prix touche une bande qui se déplace" était déjà
  exprimable). La séquentialité Validation -> Confirmation est elle aussi
  préservée telle quelle (l'étape 4 exige `val_done`, que seule l'étape 5
  d'une bougie ANTÉRIEURE peut poser). Conséquence : `make_open_tranche_fn`
  n'est PAS modifiée -- une tranche ouverte au pas `i` n'est traitée qu'au
  pas `i + 1`, après le hook, donc son `conf_px` initial (l'amplitude) n'est
  jamais lu quand le mode est actif.

H-Conf-Struct-5 -- POURQUOI LE DÉFAUT RESTE OFF (motif de FIDÉLITÉ, PAS de
  performance ; c'est le point décisif de l'investigation, et il est MESURÉ,
  pas déduit). Appliqué à nos briques, le niveau structurel est DÉJÀ FRANCHI
  avant même que l'étape n'existe : sur les 4 076 tranches ouvertes par
  `backtest_phase2_faithful.py` (BTC/ETH/BNB/SOL x 4 profils, historique
  complet), la médiane du canal de contexte est SOUS le prix d'entrée sur
  89,6-94,3% des ouvertures et SOUS `val_px` sur **100,0%**. Conséquence
  mécanique, mesurée sur les 212 tranches qui atteignent réellement la
  Validation : la Confirmation se déclencherait dès la bougie qui suit la
  Validation sur **98,1%** d'entre elles (délai médian **0 bougie**, contre
  **43 bougies** aujourd'hui), et 212/212 la franchiraient (contre 176/212
  aujourd'hui). Les 4 lectures possibles de "canal de contexte" présentes
  dans ce projet donnent le MÊME verdict -- ce n'est donc pas un artefact du
  choix de canal :

      variante de "canal de contexte"          <= entry  <= val_px  délai<=1
      A (ctx_high+ctx_low)/2, 15D, H4 [retenue]  91,4%    100,0%      98,1%
      B médiane Extreme Channel H4 (= EMA55)     96,2%    100,0%     100,0%
      C médiane Extreme Channel D1 (UT+1)        98,8%    100,0%     100,0%
      D (ctx_high+ctx_low)/2, 15D, D1 (UT+1)     92,0%    100,0%      98,1%

  Or `conf_to_be=True` : la Confirmation est LE point (et le seul) où le
  stop passe au break-even. L'activer par défaut ferait donc passer le stop
  au BE une bougie après la Validation dans 98-100% des cas, c'est-à-dire
  COLLAPSER Confirmation sur Validation -- ce que le corpus interdit avec sa
  plus grande insistance : #12 `BREAKOUT_RATIO11.md:11` (*"L'erreur fatale,
  responsable de la majorité des échecs en suivi de tendance, consiste à
  remonter son stop loss au point d'entrée (Breakeven) prématurément"*),
  #13 `PULLBACK_MATURITE.md:9` (*"Il est impératif de DISSOCIER deux étapes
  cruciales ... Validation : ... À ce stade, le trade progresse mais il est
  formellement interdit de passer au 'Break-even'"*), #15:28, #16:32, et
  `TRADING_LESSONS_INDEX.md:35` qui la nomme *"la correction la mieux étayée
  de tout le corpus"* (4 sources concordantes). Sacrifier CETTE règle-là
  pour appliquer littéralement celle-ci ferait perdre en fidélité, pas
  gagner -- exactement l'arbitrage déjà retenu au 7e round, ici appuyé sur
  une mesure et non sur une estimation.

  ORIGINE DU CONFLIT, dite honnêtement : il n'est PAS interne au corpus, il
  vient de NOS BRIQUES. La géométrie que le manuel suppose est EMBOÎTÉE --
  on achète le BAS du canal de TENDANCE, la Validation est à sa borne
  OPPOSÉE, et ce canal de tendance tient dans la MOITIÉ BASSE du canal de
  CONTEXTE (plus large, UT au-dessus), si bien que la médiane du contexte
  est encore DEVANT le prix à la Validation. Notre proxy ne reproduit pas
  cet emboîtement, pour deux raisons mesurées : (i) le signal `score >= 2`
  entre dans la moitié HAUTE du canal de contexte 9 fois sur 10 -- ce qui
  contrevient d'ailleurs à `RULES_EXTRACTION.md:17` (*"Ne jamais vendre la
  partie basse du canal de tendance / acheter la partie haute"*, règle de
  base #2, JAMAIS implémentée comme gate d'entrée : nouvel item de backlog
  ouvert par cette investigation) ; (ii) `val_px = entry + local_range`
  projette une amplitude 5D de +17,2% à +28,2% (médiane par actif) au-dessus
  de l'entrée, ce qui saute par-dessus la médiane 15D même dans les 6-9% de
  cas où l'entrée était sous elle. Rendre ce niveau non dégénéré exigerait
  donc DEUX changements couplés supplémentaires -- un vrai canal de tendance
  géométrique emboîté (`manual_trend_channel.py` existe mais a été mesuré
  puis explicitement NON adopté, cf. `PLAN.md` "Canal manuel D1") et un gate
  d'entrée "partie basse du canal" -- dont aucun n'est fourni par le corpus
  sous forme codable pour la table RANGE.

  Le mécanisme est donc CODÉ, TESTÉ et MESURÉ ici (il ne manque rien d'autre
  qu'un `use_structural_confirmation=True` pour l'exercer, cf.
  `backtest_phase2_v7.py` et `backtest_phase2_faithful.py`), et son défaut
  reste OFF -- même discipline que le gate "espace libre" du 10e round
  (*"gardé OPTIONNEL et désactivé par défaut pour une raison de méthode, pas
  de performance"*), et NON un rejet fondé sur le backtest.
================================================================================
"""
import numpy as np
import pandas as pd

# Règle de volatilité "Stop Loss = taille du canal" (cf. le bloc dédié en tête
# de fichier) : les deux "/2" littéraux de la source. Nommés séparément parce
# que la source les énonce séparément ("Taille du Stop Loss" ET "Taille de
# Position"), même s'ils valent tous deux 1/2 -- et parce qu'ils se compensent
# exactement dans un moteur dimensionné par le risque (H-Canal-Large-1).
WIDE_CHANNEL_STOP_FRAC = 0.5   # "Taille du Canal / 2 = Taille du Stop Loss"
WIDE_CHANNEL_SIZE_FRAC = 0.5   # "ET Taille de Position / 2"

# "Confirmation (médiane canal contexte, clôturée)" -- RULES_EXTRACTION.md:41,
# corroboré par TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md:55 qui CHIFFRE la
# médiane ("la médiane (50%) du contexte"). Le 0.5 est donc littéral, pas un
# paramètre à nous : nommé plutôt qu'enfoui, comme WIDE_CHANNEL_*_FRAC.
CONTEXT_MEDIAN_FRAC = 0.5


def context_channel_median(df, duration):
    """Médiane du canal de contexte `[ctx_low, ctx_high]` (H-Conf-Struct-1).

    MÊME construction que `trend_table.py::add_trend_context` et
    `fibonacci.py::compute_context_position` -- min/max glissant sur
    `duration` (fenêtre CALENDAIRE, d'où l'exigence d'une colonne `date`),
    `.shift(1)` causal : la bougie courante n'entre jamais dans son propre
    canal de référence. AUCUNE nouvelle définition de "contexte" n'est
    introduite ici (principe déjà établi dans ce projet : "même terme
    'contexte'/'canal' = même définition partout, pas une nouvelle par
    module").

    NB : ce n'est PAS `backtest_phase2_v7.py::prepare::context_range`, qui
    est une AMPLITUDE scalaire (`max(high) - min(low)`, SANS `.shift(1)`) et
    non un couple de bornes -- distinction déjà relevée par
    `fibonacci.py::compute_context_position`.

    Retourne un array numpy aligné sur `df` (NaN à la première bougie).
    """
    ts = df.set_index("date")
    ctx_high = ts["high"].rolling(duration).max().shift(1)
    ctx_low = ts["low"].rolling(duration).min().shift(1)
    return (ctx_low + (ctx_high - ctx_low) * CONTEXT_MEDIAN_FRAC).values


def make_structural_conf_update_fn(ctx_median_v):
    """Retourne un `update_levels_fn(tr, i)` qui fait de la Confirmation un
    NIVEAU STRUCTUREL ABSOLU relu EN DIRECT à chaque bougie -- la lecture
    littérale de `RULES_EXTRACTION.md:41` ("médiane canal contexte,
    clôturée") et de `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md:55` --
    au lieu de la distance `entry + context_range` figée à l'ouverture.
    Cf. le bloc "CONFIRMATION = MÉDIANE DU CANAL DE CONTEXTE" en tête de
    fichier pour les citations et les hypothèses H-Conf-Struct-1..5.

    À passer tel quel en `update_levels_fn=` de `run_position_engine`.
    Ne touche QUE `conf_px` : `val_px`, `lim_px` et le stop restent gérés
    exactement comme avant (aucun autre niveau n'est structurel dans le
    manuel -- Validation et Limite y sont des projections, cf. #12:8 et
    #5:56).

    - `ctx_median_v` : array du niveau, indexé comme les prix. Produit par
      `context_channel_median` ci-dessus.
    - Lecture à `[i - 1]`, comparée à `c[i]` par `process_tranche`
      (H-Conf-Struct-2 : même convention que `trend_table.py::excess_raw`).
    - Niveau inconnu (NaN) -> `+inf`, donc Confirmation inatteignable tant
      que le canal n'est pas calculable (H-Conf-Struct-3).
    """
    def update_levels_fn(tr, i):
        m = ctx_median_v[i - 1]
        tr["conf_px"] = np.inf if (m is None or np.isnan(m)) else float(m)

    return update_levels_fn


def make_open_tranche_fn(atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v,
                          high, o, score, warmup, min_borders, max_tranches,
                          rule3_streak, rule3_size_mult, risk_pct, state,
                          extra_gate_fn=None, wide_channel_v=None):
    """Factory pour `open_tranche_fn`, dette de duplication réelle relevée
    dans la rétrospective (PLAN.md) : 9 moteurs `backtest_phase2_*.py`
    (v4/v5/v6/v7/ut2/patterns/capital_tiers/fib/recommended) portaient
    chacun leur propre copie quasi-identique (~40 lignes) de cette fonction.

    Comparaison ligne à ligne des 9 copies (faite avant d'écrire cette
    factory, pas supposée) : le SQUELETTE est identique partout --
    `long_signal_prev`/`mature`/`valid_inputs`, `is_fresh_entry`/
    `is_pyramid_add` (mature ne gate JAMAIS le pyramidage, dans aucune des
    9 copies), calcul de `stop_pct`/Règle de Trois/`size_frac`, le dict
    retourné (entry/stop/remaining/val_px/conf_px/lim_px), et la mise à jour
    de `state["last_pyramid_high"]`. La SEULE vraie variation d'un moteur à
    l'autre est la condition de gate additionnelle appliquée par-dessus
    `long_signal_prev` (gate MTF différent selon le moteur, gate régime,
    gate Fibonacci, gate patterns géométriques, ou aucun gate -- v4/v5).

    Une seconde variation, plus fine mais réelle (v6 et fib) : le gate
    additionnel n'est PAS toujours le même pour une entrée fraîche que pour
    un renfort (pyramidalisation) -- v6 ajoute `pyramiding_allowed` (régime)
    uniquement au renfort ; fib applique `fib_ok` au renfort seulement si
    `fib_gate_pyramid=True`. D'où `extra_gate_fn(j)` qui retourne un COUPLE
    `(fresh_extra, pyramid_extra)` plutôt qu'un bool unique -- couvre les 9
    moteurs sans distinguer leur cas dans cette factory : un moteur à gate
    unique renvoie simplement `(g, g)`.

    Paramètres (tous des arrays numpy indexés comme dans les moteurs
    d'origine, sauf `risk_pct`/`state` qui sont scalaires/dict) :
      - `score` : signal brut (ex. `score >= 2` déjà appliqué par l'appelant
        -- NON, ce paramètre reçoit le score BRUT, cette factory calcule
        elle-même `long_signal_prev = score[j] >= 2`, comme les 9 copies
        d'origine (jamais un signal déjà booléen).
      - `warmup` : comparé à `i` avec `i > warmup` (index ABSOLU dans le
        moteur appelant -- `recommended.py` passe un `local_warmup` déjà
        ajusté pour un découpage, cf. sa propre docstring).
      - `risk_pct` : valeur scalaire RÉSOLUE par l'appelant (profil fixe,
        ou `capital_tiers.effective_sizing(...).risk_pct`) -- cette factory
        ne connaît pas la source, elle applique juste la Règle de Trois
        dessus, exactement comme faisaient les 9 copies (`risk_pct = ...`
        recalculé identique à chaque appel, jamais muté entre appels).
      - `state` : dict partagé avec la clé `"last_pyramid_high"`, MUTÉ par
        cette fonction exactement comme dans les 9 copies (même sémantique
        : `-np.inf` au départ, mis à jour au plus haut de renfort validé).
      - `extra_gate_fn(j)` : callback optionnel (défaut `None` -> `(True,
        True)`, comportement v4/v5, sans aucun gate additionnel), appelé
        avec `j = i - 1` (déjà décalé, comme `ctx_score[i-1]` etc. dans les
        moteurs d'origine) -- DOIT retourner un tuple `(fresh_extra,
        pyramid_extra)` de bool.
      - `wide_channel_v` : array bool optionnel (défaut `None` -> AUCUN
        changement de comportement ni de résultat numérique pour les 9
        moteurs déjà en place), indexé comme les autres arrays et lu en
        `[j] = [i-1]` comme eux (donc causal par construction, au même titre
        que `ctx_support_v[j]`). Quand `wide_channel_v[j]` est vrai, la
        règle de volatilité "Stop Loss = taille du canal" s'applique à cette
        ouverture : stop divisé par deux ET taille divisée par deux
        (cf. le bloc "STOP LOSS = TAILLE DU CANAL" en tête de fichier pour la
        citation exacte et les hypothèses H-Canal-Large-1..4). Le détecteur
        qui produit cet array est `regime_classifier.compute_wide_channel` --
        cette factory ne le calcule PAS elle-même, exactement comme elle ne
        calcule aucun autre indicateur (même discipline que `score`,
        `ctx_support_v`, `n_borders_v` : des données déjà résolues en entrée).

    Retourne `open_tranche_fn(i, tranches, win_streak)`, prêt à passer tel
    quel à `run_position_engine`.
    """
    def open_tranche_fn(i, tranches, win_streak):
        j = i - 1
        long_signal_prev = score[j] >= 2
        mature = (not np.isnan(n_borders_v[j])) and n_borders_v[j] >= min_borders
        if extra_gate_fn is not None:
            fresh_extra, pyramid_extra = extra_gate_fn(j)
        else:
            fresh_extra, pyramid_extra = True, True

        valid_inputs = (
            not np.isnan(atr_v[j]) and not np.isnan(ctx_support_v[j])
            and not np.isnan(local_range_v[j]) and local_range_v[j] > 0
            and not np.isnan(context_range_v[j]) and context_range_v[j] > 0
        )
        fresh_gated = long_signal_prev and fresh_extra
        pyramid_gated = long_signal_prev and pyramid_extra
        is_fresh_entry = (i > warmup and len(tranches) == 0 and fresh_gated and mature and valid_inputs)
        is_pyramid_add = (
            i > warmup and 0 < len(tranches) < max_tranches and pyramid_gated and valid_inputs
            and high[j] > state["last_pyramid_high"]
        )
        if not (is_fresh_entry or is_pyramid_add):
            return None

        new_tr = _build_tranche(o[i], min(ctx_support_v[j], o[i] * 0.999), j, win_streak)
        if new_tr is None:
            return None
        state["last_pyramid_high"] = max(state["last_pyramid_high"], high[j]) if is_pyramid_add else high[j]
        return new_tr

    def _build_tranche(entry_price, stop_price, j, win_streak):
        """Dimensionne et construit une tranche à partir d'un prix d'entrée et
        d'un stop DÉJÀ décidés par l'appelant. Extrait tel quel du corps de
        `open_tranche_fn` (mêmes opérations, même ordre, donc mêmes flottants
        au bit près -- vérifié par la suite de tests et par la régénération à
        l'identique de `phase2_v7_mtf_results.csv`).

        Retourne `None` si la taille calculée est nulle (comportement d'origine).
        """
        stop_pct = (entry_price - stop_price) / entry_price
        # Règle de volatilité "si canal très large" (cf. bloc dédié en tête de
        # fichier). Transcription littérale des deux moitiés de la phrase
        # source, écrites séparément bien qu'elles se compensent
        # (H-Canal-Large-1) : "Taille du Canal / 2 = Taille du Stop Loss"
        # d'abord, "ET Taille de Position / 2" ensuite -- la seconde appliquée
        # à la taille dérivée du risque, AVANT le plafond 1/max_tranches, ce
        # qui est la seule façon de préserver exactement l'"exposition capital
        # constante" que la source revendique, y compris quand ce plafond mord.
        size_mult = 1.0
        if wide_channel_v is not None and bool(wide_channel_v[j]):
            stop_pct *= WIDE_CHANNEL_STOP_FRAC
            stop_price = entry_price * (1.0 - stop_pct)
            size_mult = WIDE_CHANNEL_SIZE_FRAC
        eff_risk = risk_pct
        if win_streak >= rule3_streak:
            eff_risk *= rule3_size_mult
        size_frac = min(1.0 / max_tranches, eff_risk / stop_pct * size_mult) if stop_pct > 0 else 0.0
        if size_frac <= 0:
            return None
        # TENSION TRANCHÉE au 10e round de mobilisation (elle était notée ici
        # comme "OUVERTE, NON RÉSOLUE" au 8e) — AUCUN changement de
        # comportement, ces 3 lignes restent des amplitudes MÈCHES.
        # `local_range_v`/`context_range_v` sont calculés en amont comme
        # `max(high) - min(low)` (`backtest_phase2_v7.py::prepare` et ses
        # copies), et c'est la lecture RETENUE : le "en clôture" de
        # `TRADING_LESSONS_PYRAMIDALISATION.md:22` (#15) porte sur l'acte de
        # VALIDER le ratio 1:1 (déjà implémenté — `process_tranche` déclenche
        # sur `c[i]`), pas sur la mesure de l'amplitude ; 5 passages du corpus
        # (#14:28, #16:30, #10:38, #5:56, `RULES_EXTRACTION.md:41`) placent le
        # NIVEAU sur les extrêmes et la CLÔTURE comme TEST ; et la variante
        # "amplitude en clôtures" éloigne mesurablement la Validation du 1:1
        # que #12:8 assigne à cette étape (R médian 0,88-1,06 -> 0,69-0,85).
        # Raisonnement complet, citations et chiffres : bloc "RÈGLE D'OR" en
        # tête de ce fichier.
        return {
            "entry": entry_price, "stop": stop_price, "remaining": size_frac,
            "val_done": False, "conf_done": False, "pnl_accum": 0.0,
            "val_px": entry_price + local_range_v[j],
            "conf_px": entry_price + context_range_v[j],
            "lim_px": entry_price + 1.5 * context_range_v[j],
        }

    return open_tranche_fn


def process_tranche(tr, i, o, low, c, long_signal_prev, val_close_frac, conf_close_frac, conf_to_be,
                     reverse_at_limit=False):
    """Fait progresser une tranche ouverte d'un pas de temps `i`. Mute `tr` en place.

    `tr` doit exposer les clés : entry, stop, remaining, val_done, conf_done,
    pnl_accum, val_px, conf_px, lim_px.

    Retourne (closed: bool, fee_frac: float, realized_pnl: float|None).
    `fee_frac` est la fraction du capital (par rapport à la taille initiale
    de la tranche) sur laquelle des frais doivent être prélevés ce pas-ci
    (clôture totale ou partielle). `realized_pnl` est le P&L total de la
    tranche (fraction), renseigné seulement si la tranche se ferme ce pas-ci.

    `reverse_at_limit` (défaut False, AUCUN changement de comportement pour
    tous les appels existants) : si True et que la clôture se fait par la
    Limite, `tr["reverse_request"]` est rempli avec les paramètres de la
    jambe short "+Reverse" (hypothèse H-Reverse-Range, cf. tête de fichier)
    -- charge à l'appelant (`run_position_engine`) de la lire et de l'ouvrir.
    """
    # 1) Limite atteinte -> clôture totale (sur CLÔTURE)
    if c[i] >= tr["lim_px"]:
        remaining_before = tr["remaining"]
        pnl = (c[i] - tr["entry"]) / tr["entry"]
        tr["pnl_accum"] += pnl * remaining_before
        fee_frac = remaining_before
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        if reverse_at_limit:
            stop_pct = (tr["entry"] - tr["stop"]) / tr["entry"]        # H-Reverse-Range : miroir du stop
            gain_pct = (tr["lim_px"] - tr["entry"]) / tr["entry"]      # H-Reverse-Range : miroir de la cible
            r_entry = c[i]
            tr["reverse_request"] = {
                "entry": r_entry,
                "stop": r_entry * (1 + stop_pct),
                "target": r_entry * (1 - gain_pct),
                "remaining": remaining_before,
            }
        return True, fee_frac, realized

    # 2) Invalidation (stop) touchée -- sur MÈCHE (ordre réel, intrabar)
    if low[i] <= tr["stop"]:
        pnl = (tr["stop"] - tr["entry"]) / tr["entry"]
        tr["pnl_accum"] += pnl * tr["remaining"]
        fee_frac = tr["remaining"]
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        return True, fee_frac, realized

    # 3) Sortie de signal (flip) avant toute étape -> sortie au marché (open)
    if not long_signal_prev and not tr["val_done"] and not tr["conf_done"]:
        pnl = (o[i] - tr["entry"]) / tr["entry"]
        tr["pnl_accum"] += pnl * tr["remaining"]
        fee_frac = tr["remaining"]
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        return True, fee_frac, realized

    fee_frac = 0.0

    # 4) Confirmation atteinte (seulement si validation déjà faite, séquentiel)
    if tr["val_done"] and not tr["conf_done"] and c[i] >= tr["conf_px"]:
        close_amt = tr["remaining"] * conf_close_frac
        if close_amt > 0:
            pnl = (c[i] - tr["entry"]) / tr["entry"]
            tr["pnl_accum"] += pnl * close_amt
            fee_frac += close_amt
            tr["remaining"] -= close_amt
        if conf_to_be:
            tr["stop"] = max(tr["stop"], tr["entry"])
        tr["conf_done"] = True

    # 5) Validation atteinte -- PAS de breakeven ici (interdit avant Confirmation)
    if not tr["val_done"] and c[i] >= tr["val_px"]:
        close_amt = tr["remaining"] * val_close_frac
        if close_amt > 0:
            pnl = (c[i] - tr["entry"]) / tr["entry"]
            tr["pnl_accum"] += pnl * close_amt
            fee_frac += close_amt
            tr["remaining"] -= close_amt
        tr["val_done"] = True

    if tr["remaining"] <= 1e-9:
        realized = tr["pnl_accum"]
        return True, fee_frac, realized

    return False, fee_frac, None


def process_reverse(rp, i, high, low, c):
    """Fait progresser une jambe short "+Reverse" (hypothèse H-Reverse-Range,
    cf. tête de fichier) d'un pas de temps `i`. `rp` (dict avec les clés
    entry/stop/target/remaining) n'est PAS muté -- jambe unique bornée, sans
    état à accumuler entre pas de temps (pas de clôture partielle, contraire
    à `process_tranche`/`tr`).

    Retourne (closed: bool, fee_frac: float, realized_pnl: float|None), même
    convention que `process_tranche`. Short : le P&L est positif quand le
    prix BAISSE (entry - prix_de_sortie).
    """
    # Stop touché -- sur MÈCHE (ordre réel, intrabar), miroir de l'Invalidation long
    if high[i] >= rp["stop"]:
        pnl = (rp["entry"] - rp["stop"]) / rp["entry"]
        return True, rp["remaining"], pnl
    # Cible atteinte -- sur CLÔTURE, miroir de la Limite long
    if c[i] <= rp["target"]:
        pnl = (rp["entry"] - c[i]) / rp["entry"]
        return True, rp["remaining"], pnl
    return False, 0.0, None


def run_position_engine(n, o, high, low, c, long_signal, open_tranche_fn,
                         val_close_frac, conf_close_frac, conf_to_be, max_tranches, fee,
                         update_levels_fn=None, mark_new_tranches=True, same_bar_reentry=True,
                         record_trace=False, reverse_at_limit=False):
    """Boucle générique de gestion de position, à tranche unique ou multiple.

    - n : nombre de bougies.
    - o, high, low, c : arrays numpy des prix (open/high/low/close).
    - long_signal : array bool (indexé normalement ; le moteur utilise
      long_signal[i-1], cohérent avec la convention "signal de la bougie
      précédente" des scripts d'origine).
    - open_tranche_fn(i, tranches, win_streak) : callback fourni par le
      script appelant, encapsulant SA logique d'éligibilité à l'entrée
      (warmup, maturité, pyramidalisation, Règle de Trois, calcul du stop
      initial et des niveaux Validation/Confirmation/Limite...). Doit
      retourner soit None (pas d'ouverture ce pas-ci), soit un nouveau
      dict tranche prêt à l'emploi (voir `process_tranche`). N'est appelé
      que lorsque `len(tranches) < max_tranches`.
    - val_close_frac, conf_close_frac : fractions du RESTANT à clôturer à
      Validation / Confirmation (mêmes valeurs pour toutes les tranches
      d'un même appel : ce sont des paramètres de profil de risque).
    - conf_to_be : bool, si True le stop est remonté au break-even (max
      avec l'entrée) à la Confirmation ; certains profils du moteur
      "trade spéculatif" d'origine (AGRESSIF/TRES_AGRESSIF dans
      backtest_phase2.py) désactivent explicitement ce comportement.
    - max_tranches : nombre maximal de tranches simultanément ouvertes
      (1 = pas de pyramidalisation, comme dans backtest_phase2.py).
    - fee : frais proportionnels (fraction) appliqués sur chaque montant
      ouvert ou clôturé.
    - update_levels_fn(tr, i) : hook optionnel, appelé pour chaque tranche
      ouverte avant `process_tranche`, pour recalculer ses niveaux
      Validation/Confirmation/Limite si le moteur appelant les fait
      dériver dans le temps (cas de backtest_phase2.py, qui les recalcule
      à partir de l'ATR courant plutôt que de les figer à l'entrée).
    - mark_new_tranches : si True (comportement d'origine de v4/v5), une
      tranche ouverte à ce pas `i` est immédiatement incluse dans le
      mark-to-market (equity_curve) du même pas. Si False (comportement
      d'origine de backtest_phase2.py, dont la structure en `continue`
      sautait le calcul de mark-to-market le jour même de l'entrée), une
      tranche fraîchement ouverte au pas `i` n'entre dans l'equity_curve
      qu'à partir du pas suivant. Conservé tel quel pour ne pas changer
      les résultats numériques du refactoring (max_dd_% dépend de la
      equity_curve).
    - same_bar_reentry : si True (comportement d'origine de v4/v5), une
      tranche qui se clôture totalement au pas `i` peut être immédiatement
      remplacée par une nouvelle entrée AU MÊME pas `i` (le code d'origine
      v4/v5 n'a jamais de `continue` : gestion des tranches existantes et
      tentative d'ouverture ont toujours lieu dans la même itération). Si
      False (comportement d'origine de backtest_phase2.py, structuré en
      `if not in_position: ...; continue`), une entrée n'est tentée QUE
      lorsqu'aucune tranche n'était déjà ouverte au DÉBUT du pas `i` (donc
      jamais le même pas qu'une clôture) -- et dans ce cas les tranches
      existantes ne sont pas non plus re-traitées ce pas-ci (il n'y en a
      pas). Conservé tel quel pour ne pas changer les résultats numériques
      du refactoring.
    - record_trace : si True (défaut False, AUCUN changement de comportement
      ni de résultat numérique pour les appelants existants -- bookkeeping
      additive uniquement), le moteur enregistre en plus une trace par
      trade : bougie d'ouverture, prix d'entrée, et pour chaque bougie où
      le trade est DÉJÀ ouvert (donc PAS sa propre bougie d'ouverture : la
      taille exposée à l'instant même de l'entrée n'est pas retenue comme
      pertinente pour un coût qui suppose une position déjà détenue, ex. le
      funding) un instantané (indice de bougie, taille RESTANTE avant que
      cette bougie ne déclenche une éventuelle clôture partielle
      Validation/Confirmation/stop). Conçu pour `funding_rate_exact.py` :
      la taille exposée à un événement qui tombe pile sur cette bougie est
      exactement cette valeur.
    - reverse_at_limit : défaut False, AUCUN changement de comportement ni de
      résultat numérique pour les appelants existants. Si True, une tranche
      qui se clôture à la Limite ouvre EN PLUS une jambe short "+Reverse"
      (hypothèse H-Reverse-Range, cf. le bloc dédié en tête de fichier). Les
      jambes reverse ouvertes sont gérées dans une liste séparée des tranches
      long, chacune indépendamment (pas de sous-étapes Validation/
      Confirmation, une seule sortie possible : stop ou cible) ; leurs P&L
      réalisés sont ajoutés aux MÊMES statistiques agrégées (n_trades,
      win_rate_%, profit_factor...) que les tranches long, comme des trades
      distincts. `record_trace` ne couvre PAS les jambes reverse (non-goal
      documenté, cf. tête de fichier).

    Retourne un dict avec : n_trades, final_equity, max_dd_%, total_return_%,
    win_rate_%, profit_factor, avg_trade_%, equity_curve (array numpy, pour
    usage interne/diagnostic -- pas forcément exportée en CSV par l'appelant).
    Si `record_trace=True`, ajoute la clé "trace" : liste de dicts
    {trade_id, open_i, close_i, entry_price, realized_pnl, snapshots}, où
    `snapshots` est une liste de tuples (i, remaining_before_bar_i).
    """
    equity = 1.0
    equity_curve = np.empty(n)
    equity_curve[0] = equity
    tranches = []
    reverses = []
    trades = []
    win_streak = 0
    trace = [] if record_trace else None

    for i in range(1, n):
        long_signal_prev = bool(long_signal[i - 1])
        had_open_at_start = len(tranches) > 0
        process_this_step = same_bar_reentry or had_open_at_start

        # Jambes "+Reverse" en cours (indépendant de process_this_step : ce
        # sont des positions short bornées, sans la nuance historique
        # same_bar_reentry/mark_new_tranches propre aux tranches long -- cf.
        # hypothèse H-Reverse-Range en tête de fichier).
        remaining_reverses = []
        for rp in reverses:
            closed_r, fee_frac_r, realized_r = process_reverse(rp, i, high, low, c)
            if closed_r:
                equity *= (1 + realized_r)
            if fee_frac_r > 0:
                equity *= (1 - fee * fee_frac_r)
            if closed_r:
                trades.append(realized_r)
                win_streak = win_streak + 1 if realized_r > 0 else 0
            else:
                remaining_reverses.append(rp)
        reverses = remaining_reverses

        if process_this_step:
            if record_trace:
                for tr in tranches:
                    trace[tr["_trade_id"]]["snapshots"].append((i, tr["remaining"]))
            remaining_tranches = []
            new_reverses = []
            for tr in tranches:
                if update_levels_fn is not None:
                    update_levels_fn(tr, i)
                closed, fee_frac, realized = process_tranche(
                    tr, i, o, low, c, long_signal_prev, val_close_frac, conf_close_frac, conf_to_be,
                    reverse_at_limit=reverse_at_limit,
                )
                if closed:
                    equity *= (1 + realized)
                if fee_frac > 0:
                    equity *= (1 - fee * fee_frac)
                if closed:
                    trades.append(realized)
                    win_streak = win_streak + 1 if realized > 0 else 0
                    if record_trace:
                        trace[tr["_trade_id"]]["close_i"] = i
                        trace[tr["_trade_id"]]["realized_pnl"] = realized
                    rr = tr.get("reverse_request")
                    if rr is not None:
                        new_reverses.append(rr)
                        equity *= (1 - fee * rr["remaining"])  # frais d'ouverture de la jambe reverse
                else:
                    remaining_tranches.append(tr)
            tranches = remaining_tranches
            reverses.extend(new_reverses)
        still_open = list(tranches)  # survivants AVANT l'ouverture éventuelle d'une nouvelle tranche ce pas-ci

        can_open_this_step = (same_bar_reentry or not had_open_at_start) and len(tranches) < max_tranches
        if can_open_this_step:
            new_tr = open_tranche_fn(i, tranches, win_streak)
            if new_tr is not None:
                if record_trace:
                    new_tr["_trade_id"] = len(trace)
                    trace.append({
                        "trade_id": new_tr["_trade_id"], "open_i": i,
                        "entry_price": new_tr["entry"], "entry_size": new_tr["remaining"],
                        "close_i": None, "realized_pnl": None, "snapshots": [],
                    })
                tranches.append(new_tr)
                equity *= (1 - fee * new_tr["remaining"])

        mtm_tranches = tranches if mark_new_tranches else still_open
        unrealized = sum(tr["pnl_accum"] + (c[i] - tr["entry"]) / tr["entry"] * tr["remaining"] for tr in mtm_tranches)
        unrealized += sum((rp["entry"] - c[i]) / rp["entry"] * rp["remaining"] for rp in reverses)
        equity_curve[i] = equity * (1 + unrealized)

    trades_arr = np.array(trades) if trades else np.array([])
    eq_series = pd.Series(equity_curve)
    max_dd = (eq_series / eq_series.cummax() - 1).min()
    result = {
        "n_trades": len(trades_arr),
        "final_equity": equity,
        "max_dd_%": round(max_dd * 100, 1),
        "total_return_%": round((equity - 1) * 100, 1),
        "win_rate_%": round((trades_arr > 0).mean() * 100, 1) if len(trades_arr) else None,
        "profit_factor": round(trades_arr[trades_arr > 0].sum() / abs(trades_arr[trades_arr < 0].sum()), 2)
        if len(trades_arr) and (trades_arr < 0).any() else None,
        "avg_trade_%": round(trades_arr.mean() * 100, 3) if len(trades_arr) else None,
        "equity_curve": equity_curve,
    }
    if record_trace:
        result["trace"] = trace
    return result
