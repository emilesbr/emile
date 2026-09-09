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

        entry_price = o[i]
        stop_price = min(ctx_support_v[j], entry_price * 0.999)
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
        state["last_pyramid_high"] = max(state["last_pyramid_high"], high[j]) if is_pyramid_add else high[j]
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
