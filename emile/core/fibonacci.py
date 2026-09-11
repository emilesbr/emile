"""
Fibonacci retracement — filtre de qualité d'entrée additionnel (backlog
`PLAN.md` item 4, `COUVERTURE_ENSEIGNEMENTS.md` ligne Fibonacci).

Règle extraite fidèlement des 5 sources citées pour cet item par
`COUVERTURE_ENSEIGNEMENTS.md` (#9, #10, #11, #13, #14 — identifiées via
`TRADING_LESSONS_INDEX.md`) :
  #9  = TRADING_LESSONS_MTF_SUIVI_TENDANCE.md
  #10 = TRADING_LESSONS_ZONE_ACCUMULATION.md
  #11 = TRADING_LESSONS_TROISIEME_BORNE.md
  #13 = TRADING_LESSONS_PULLBACK_MATURITE.md
  #14 = TRADING_LESSONS_STRUCTURES_ALTERATIONS.md

IMPORTANT — constat honnête avant l'implémentation : la "zone dorée" 38%-
61,8% supposée au départ de ce chantier (énoncé de la tâche) N'EST PAS ce
que ces 5 sources disent une fois relues précisément. Elles ne convergent
PAS sur un unique intervalle — chacune donne une règle légèrement
différente, resynthétisée ci-dessous plutôt que forcée dans un chiffre
unique commode qui masquerait la divergence réelle du corpus :

  - #13 (PULLBACK_MATURITE — la plus précise, table GO/WAIT directement
    implémentable) : 23% = seuil MINIMAL de retracement pour valider
    l'entrée en zone (en-dessous = simple pause de tendance, pas un
    pullback) ; 38% = niveau "standard et optimal" ; 50% = "exceptionnel,
    rare dans les tendances à forte vélocité". "Règle des 50%" : le
    pullback n'est validé QUE SI retracement >= 23% ET pénétration dans les
    50% inférieurs du contexte (deux conditions cumulatives, pas une
    seule). Table de décision : GO si cluster Fibonacci entre 23% et 38%,
    WAIT hors de ces niveaux.
  - #10 (ZONE_ACCUMULATION) : zone Fibonacci favorable = "cluster 38-50%"
    pour la maturité d'une zone d'accumulation ; "61% = seuil de tolérance
    MAXIMUM". Red Flag explicite si "clôture maintenue au-delà de 61% de
    la structure" (invalidation, redevient un simple range).
  - #11 (TROISIEME_BORNE) : le pullback qui suit la cassure/clôture
    confirmée d'une 3ème borne valide vise spécifiquement le niveau
    "Fibonacci 61,8%" — un niveau PONCTUEL (pas un intervalle), pour un
    pattern plus spécifique (retest post-breakout d'une 3ème borne), pas
    une règle d'entrée générale.
  - #9 (MTF_SUIVI_TENDANCE) et #14 (STRUCTURES_ALTERATIONS) : AUCUN niveau
    de retracement chiffré. #9 documente la règle multi-timeframe "UT+2",
    pas Fibonacci. #14 mentionne des "extensions de Fibonacci" mais pour
    la PRISE DE PROFIT en Vague 5 (sorties), pas pour un critère d'entrée
    par profondeur de retracement. Ces 2 des 5 sources attribuées à cette
    ligne par `COUVERTURE_ENSEIGNEMENTS.md` ne documentent en réalité
    aucune règle de retracement d'entrée — à noter honnêtement plutôt que
    de prétendre une convergence à 5/5 qui n'existe pas.

Point de vigilance additionnel, à ne pas cacher : le niveau "76,4%" cité
dans la ligne récapitulative de `COUVERTURE_ENSEIGNEMENTS.md`
("23%/38%/50%/61,8%/76,4%") N'APPARAÎT DANS AUCUNE des 5 sources ci-dessus
une fois relues précisément — c'est un niveau Fibonacci standard, cohérent
avec les autres, mais ce chiffre précis ne provient pas des 5 sources qui
lui sont attribuées (probablement une généralisation implicite depuis
d'autres sources du corpus à 17 sources, non vérifiées ici). Documenté
plutôt que reproduit sans vérification — cf. `COUVERTURE_ENSEIGNEMENTS.md`
pour la mise à jour de cette ligne.

Synthèse retenue pour l'implémentation (résume les points ci-dessus sans
forcer un faux consensus à 5/5) :
  - Zone FAVORABLE = [FAVORABLE_MIN, FAVORABLE_MAX] = [23%, 61,8%] — union
    du seuil minimal de validation (#13) et du plafond de tolérance
    maximum avant invalidation (#10) / du niveau d'intervention ponctuel
    du pattern 3ème borne (#11).
  - Sous-zone OPTIMALE = [FAVORABLE_MIN, FAVORABLE_OPTIMAL_MAX] = [23%,
    50%] — le "standard et optimal" 38% de #13 encadré par son propre
    "exceptionnel" 50%, cohérent avec le cluster 38-50% de #10.
  - En-deçà de 23% (< FAVORABLE_MIN) = défavorable (simple pause de
    tendance, pas un pullback qualifiant, #13).
  - Au-delà de 61,8% (> FAVORABLE_MAX) = défavorable / invalidé (Red Flag
    explicite de #10).

MISE À JOUR (5e round de mobilisation multi-agents, audit exhaustif du
corpus — `COUVERTURE_ENSEIGNEMENTS.md` section "Audit exhaustif du corpus
complet", catégorie B) : la "Règle des 50%" de #13 citée ci-dessus est une
règle à DEUX conditions cumulatives ("pas une seule") — jusqu'ici seule la
première (retracement >= 23%, `FAVORABLE_MIN`) était codée
(`classify_retracement`/`fib_favorable`/`fib_optimal`). La seconde
("pénétration dans les 50% inférieurs DU CONTEXTE") ne l'était pas — gap
honnêtement documenté puis comblé dans ce même cycle par
`compute_context_position`/`classify_regle_50`/`fib_regle_50` ci-dessous.

Point de vigilance résolu au passage, pour éviter une confusion future avec
un hypothèse voisine, PAS clairement distincte (correction après
vérification adversariale, cycle suivant — honnêteté à préserver plutôt
qu'une séparation confortable mais fragile) : `trend_table.py` a sa propre
hypothèse H7 sur la phrase "retour min 50% contexte" (RULES_EXTRACTION.md
§1, séquence compressée de la table de tendance à 5 étapes), interprétée
LÀ-BAS comme "recovery_frac >= 0.50" (fraction du retracement regagnée
depuis le creux). La première version de cette note affirmait que c'était
"une phrase différente, un module différent, un usage différent" — un
examen mot à mot ne soutient PAS cette affirmation aussi nettement :
RULES_EXTRACTION.md §1 ("Pull-Back : retracement min 23-38% + retour min
50% contexte") calque très probablement la même table GO/WAIT que #13
("Entre 23% et 38%" = GO, "50% inférieurs du contexte" = condition
cumulative) — la même étape Pull-Back, la même structure à 2 volets. #13
(leçon vidéo) désambiguïse plausiblement le manuel compressé plutôt que de
décrire autre chose. H7 le reconnaît d'ailleurs lui-même comme "ambigu
dans le manuel" — ce fichier vient précisément de trouver la source qui
lève cette ambiguïté, dans le sens "position dans le canal", pas
"recovery_frac". **H7 n'est PAS modifiée ici** (elle reste utilisée telle
quelle par `trend_table.py`, changement de comportement hors périmètre de
ce chantier) — mais la tension entre les deux lectures est désormais aussi
tracée dans `trend_table.py` lui-même, à côté de H7, pour qu'un futur
lecteur de ce fichier la voie (au lieu de rester visible seulement ici).

"Le contexte" dans la règle de #13 est interprété comme LE MÊME canal de
contexte déjà établi par `trend_table.py::add_trend_context`
(`ctx_high`/`ctx_low`, fenêtre `CONTEXT_DURATION` = "15D", `.shift(1)`
causal) — PAS une nouvelle définition inventée ici. Précision après
vérification adversariale : `backtest_phase2_v7.py::prepare` ne calcule PAS
`ctx_high`/`ctx_low` (seulement `context_range`, une amplitude scalaire,
SANS `.shift(1)`) — la correspondance bit-à-bit n'est vraie que contre
`trend_table.py`, pas contre v7.py ; et `compute_context_position`
ci-dessous ne fait pas que réutiliser la MÊME fenêtre, elle recalcule très
exactement la MÊME grandeur que `trend_table.py::accum_retracement_frac`
(même formule `(ctx_high - close) / (ctx_high - ctx_low)`, même
`.replace(0, np.nan)`) — vérifié bit-à-bit sur données réelles, pas
seulement "la même construction". Lecture alternative explicitement
écartée mais envisagée : "le contexte" = le mouvement de retracement
lui-même (auquel cas "50% inférieurs" désignerait un retracement >= 50%) —
écartée parce qu'elle contredirait la propre description de #13 du niveau
50% comme "exceptionnel, rare" (un plancher à 50% rendrait le seuil
minimal de 23% sans objet). Ce fichier reste néanmoins volontairement
séparé de `trend_table.py` (H6) : `compute_context_position` ci-dessous
RECALCULE le canal de contexte plutôt que d'importer `accum_retracement_frac`
déjà calculée par `trend_table.py`, pour ne pas rendre ce module dépendant
de lui. Note additionnelle : la fraction retournée n'est PAS bornée à
[0,1] par construction (le close peut sortir du canal des `CONTEXT_DURATION`
jours antérieurs) — mesuré sur BTC D1 réel : plage [-0,86, +3,31] — sans
effet sur le test `>= REGLE_50_CONTEXT_MIN` ci-dessous, mais à ne pas lire
comme une fraction strictement bornée.

Pivot de mesure — quel haut/bas sert de référence : le DERNIER mouvement
directionnel haussier complet détecté (dernier swing low, suivi
chronologiquement du dernier swing high) — cohérent avec un projet
long-only (`proxy_v2.py`, tous les moteurs `backtest_phase2_*.py`).
Détection de swing réutilisée à l'identique de
`proxy_v2.py::compute_ascending_lows` : `scipy.signal.argrelextrema`,
même `order` (3 bougies de chaque côté). Ce n'est pas une nouvelle
détection ad hoc, c'est la même déjà en production ailleurs dans ce
projet (également utilisée pour `n_borders` dans
`backtest_phase2_v6.py`/`_v7.py`).

MISE À JOUR (réserve P0-bis, COUVERTURE_ENSEIGNEMENTS.md/PLAN.md occurrence
#4, traitée dans le même cycle de travail qui a construit ce fichier) : la
version initiale de `compute_swing_highs_lows` ci-dessous consommait
`is_swing_high`/`is_swing_low` batch au moment même du creux/sommet — déjà
signalé honnêtement dans sa propre docstring comme "même compromis déjà
présent ailleurs dans le projet". Ce fichier réutilise désormais
`proxy_v2.compute_swing_low_confirmed`/`compute_swing_high_confirmed`
(mêmes primitives causales que `compute_ascending_lows`) : un swing n'est
exploité par `compute_retracement` qu'une fois réellement confirmé (à
l'instant + SWING_ORDER), pas au moment du swing lui-même.

================================================================================
"HYBRIDE MÈCHES/CLÔTURES" DE `compute_retracement` — ITEM EXAMINÉ AU 10e ROUND
ET FERMÉ COMME **CONFORME**, PAS COMME DÉFAUT. Note documentaire, aucun
comportement changé. Décision complète : `PLAN.md` section "10e application",
`COUVERTURE_ENSEIGNEMENTS.md` (catégorie C), et le bloc "RÈGLE D'OR" en tête de
`code/position_engine.py` (même décision, même cycle).
================================================================================
Le 8e round avait inscrit au backlog catégorie C : *"`compute_retracement` est
hybride mèches/clôtures, non documenté comme tel — numérateur en clôture
(conforme), dénominateur (`swing_high - swing_low`) en mèches ; à trancher avec
l'item `local_range`/`context_range`, pas séparément"*. Tranché : ce n'est PAS
un hybride accidentel, c'est la transcription EXACTE de la convention que le
corpus énonce partout — **la STRUCTURE se mesure sur les extrêmes, la CLÔTURE
est le TEST de position dans cette structure** :
  - dénominateur (l'amplitude du dernier mouvement, donc ses extrêmes) :
    #10 `ZONE_ACCUMULATION.md:38` *"sous le POINT BAS de la 4ème borne"* ;
    #5 `MAITRISE_GRADIENT_RISQUE.md:56` *"76% Fibonacci de la VAGUE
    précédente"* ; #14 `STRUCTURES_ALTERATIONS.md:28` *"les mèches peuvent
    pénétrer l'ancien territoire, mais les clôtures doivent rester à
    l'extérieur pour VALIDER la structure"* — le niveau vient des extrêmes ;
    #16 `CLUSTERS_PRIX.md:30` refuse même explicitement de trancher pour un
    creux structurel (*"bas de clôture OU mèche"*) ;
  - numérateur (où se situe la clôture dans cette structure) :
    #11 `TROISIEME_BORNE.md:23` *"uniquement si le prix maintient ses
    CLÔTURES sous/sur le contexte"* ; #10 `ZONE_ACCUMULATION.md:46`
    *"Retracement profond : CLÔTURE maintenue au-delà de 61% de LA
    STRUCTURE"* — mot pour mot la formule codée ici, "la structure" étant le
    dénominateur et "clôture" le numérateur.
Passer le dénominateur en clôtures serait exactement le changement que le 8e
round a lui-même REFUSÉ pour la détection des bornes (`PLAN.md` section "8e
application"), et il n'existe aucune citation du corpus qui mesure une
profondeur de retracement Fibonacci sur des clôtures (grep exhaustif des 17
sources + `RULES_EXTRACTION.md`).
================================================================================
"""
import numpy as np
import pandas as pd
import sys

from emile.core.proxy_v2 import compute_swing_low_confirmed, compute_swing_high_confirmed

# Cohérent avec proxy_v2.SWING_ORDER (même détection de swing réutilisée).
SWING_ORDER = 3

# Cf. synthèse de la règle extraite en tête de fichier.
FAVORABLE_MIN = 0.23
FAVORABLE_OPTIMAL_MAX = 0.50
FAVORABLE_MAX = 0.618

# Canal de "contexte" pour la 2e condition de la Règle des 50% (#13, cf.
# MISE À JOUR en tête de fichier) — MÊME fenêtre que
# backtest_phase2_v7.py::CONTEXT_DURATION/trend_table.py::add_trend_context,
# réutilisée à l'identique (pas une nouvelle définition de "contexte").
CONTEXT_DURATION = "15D"
# "pénétration dans les 50% inférieurs du contexte" (#13) : le close doit se
# situer dans la moitié basse du canal [ctx_low, ctx_high].
REGLE_50_CONTEXT_MIN = 0.50

def compute_swing_highs_lows(df: pd.DataFrame, order: int = SWING_ORDER) -> tuple:
    """Détecte les swing highs/lows, CAUSAL (réserve P0-bis traitée) via
    `proxy_v2.compute_swing_high_confirmed`/`compute_swing_low_confirmed` —
    mêmes primitives que `proxy_v2.py::compute_ascending_lows`. Retourne
    deux arrays booléens (is_swing_high, is_swing_low) où l'indice t est
    vrai ssi un swing est CONFIRMÉ à l'instant t (la barre swing réelle est
    alors à `t - order`, pas à `t` — cf. docstring de
    `compute_swing_low_confirmed`), alignés sur l'index de `df`.

    Avant ce traitement, cette fonction consommait la classification batch
    au moment même du creux/sommet (déjà signalé honnêtement ici comme
    lookahead de `order` bougies — même compromis que `n_borders`,
    `backtest_phase2_v5/v6/v7.py`, avant qu'il n'y soit également corrigé).
    `compute_retracement` ci-dessous a été ajusté en conséquence pour
    récupérer la valeur/l'indice réels du swing (`t - order`), pas `t`."""
    high_v = df["high"].values
    low_v = df["low"].values
    is_swing_high = compute_swing_high_confirmed(high_v, order=order)
    is_swing_low = compute_swing_low_confirmed(low_v, order=order)
    return is_swing_high, is_swing_low

def compute_retracement(df: pd.DataFrame, order: int = SWING_ORDER) -> np.ndarray:
    """Calcule, pour chaque bougie, le % de retracement du prix de clôture
    par rapport au dernier mouvement directionnel HAUSSIER détecté (dernier
    swing low, suivi chronologiquement par le dernier swing high) :

        retracement_pct = (dernier_swing_high - close) / (dernier_swing_high - dernier_swing_low)

    Un mouvement n'est considéré valide pour le calcul QUE si :
      1. le dernier swing low détecté précède chronologiquement le dernier
         swing high détecté (on est bien en phase de retracement APRÈS un
         plus haut, pas avant un futur plus haut) ;
      2. ce plus haut est strictement supérieur à ce plus bas (amplitude
         du mouvement > 0, jamais de division par zéro/négatif).

    Retourne un array de fractions (0.23 pour 23%, pas 23), NaN tant
    qu'aucun mouvement complet low->high n'a encore été confirmé (warmup)."""
    close = df["close"].values
    high_v = df["high"].values
    low_v = df["low"].values
    is_swing_high, is_swing_low = compute_swing_highs_lows(df, order=order)
    n = len(df)
    retracement = np.full(n, np.nan)

    last_high_px, last_high_i = np.nan, -1
    last_low_px, last_low_i = np.nan, -1

    for i in range(n):
        # is_swing_{high,low}[i] signifie "confirmé à l'instant i" — la barre
        # swing réelle est à i - order (cf. compute_swing_highs_lows).
        if is_swing_low[i]:
            last_low_px, last_low_i = low_v[i - order], i - order
        if is_swing_high[i]:
            last_high_px, last_high_i = high_v[i - order], i - order

        if last_high_i > last_low_i >= 0 and last_high_px > last_low_px:
            amplitude = last_high_px - last_low_px
            retracement[i] = (last_high_px - close[i]) / amplitude

    return retracement

def classify_retracement(retracement_pct) -> tuple:
    """Classification favorable/optimale à partir d'un array (ou scalaire)
    de fractions de retracement — cf. la règle extraite en tête de fichier.
    NaN (pas encore de mouvement confirmé) est naturellement classé comme
    non favorable/non optimal (toute comparaison avec NaN vaut False)."""
    r = np.asarray(retracement_pct, dtype=float)
    favorable = (r >= FAVORABLE_MIN) & (r <= FAVORABLE_MAX)
    optimal = (r >= FAVORABLE_MIN) & (r <= FAVORABLE_OPTIMAL_MAX)
    return favorable, optimal

def compute_context_position(df: pd.DataFrame, duration: str = CONTEXT_DURATION) -> np.ndarray:
    """Position du close dans le canal de "contexte" [ctx_low, ctx_high]
    (rolling `duration`, MÊME construction que
    `trend_table.py::add_trend_context` — cf. MISE À JOUR en tête de
    fichier ; PAS `backtest_phase2_v7.py::prepare`, qui ne calcule ni
    `ctx_high` ni `ctx_low` et dont le `context_range` n'a pas de
    `.shift(1)`) : 0.0 = close au sommet du canal, 1.0 = close au bas du
    canal — fraction NON bornée à [0,1] par construction (le close peut
    sortir du canal antérieur), cf. MISE À JOUR en tête de fichier.

    CAUSAL comme le reste du fichier : `.shift(1)` avant lecture, la
    bougie courante n'entre jamais dans son propre canal de référence (même
    construction que `trend_table.py::ctx_high`/`ctx_low`). Reproduit très
    exactement `trend_table.py::accum_retracement_frac` (même formule,
    vérifié bit-à-bit) — recalculé ici plutôt qu'importé pour ne pas rendre
    ce module dépendant de `trend_table.py` (H6).

    Nécessite une colonne `date` (utilisée pour le rolling calendaire,
    comme partout ailleurs où `CONTEXT_DURATION` est utilisé dans le
    projet) — exigence dure introduite par cette fonction (cf. note sur
    `add_fibonacci_columns` ci-dessous). NaN pour la toute première bougie
    (`shift(1)` sans historique antérieur) ou si `ctx_high == ctx_low`
    (canal de largeur nulle, division évitée) ; en-deçà de 15 jours
    calendaires de profondeur, la fenêtre reste PARTIELLE (pas NaN) — même
    comportement par défaut de `.rolling(<offset>)` que `ctx_high`/`ctx_low`
    dans `trend_table.py`, pas un choix nouveau introduit ici."""
    ts = df.set_index("date")
    ctx_high = ts["high"].rolling(duration).max().shift(1)
    ctx_low = ts["low"].rolling(duration).min().shift(1)
    span = (ctx_high - ctx_low).replace(0, np.nan)
    position = (ctx_high - ts["close"]) / span
    return position.values

def classify_regle_50(retracement_pct, context_position) -> np.ndarray:
    """"Règle des 50%" (#13, citée en tête de fichier) : condition CUMULATIVE
    (ET, pas OU, contrairement à `classify_retracement` ci-dessus qui teste
    une seule condition) — retracement dans la zone favorable [23%, 61,8%]
    (`FAVORABLE_MIN`/`FAVORABLE_MAX`, MÊMES bornes que `classify_retracement`
    ci-dessus) ET pénétration du close dans les 50% inférieurs du canal de
    contexte (`context_position >= REGLE_50_CONTEXT_MIN`). NaN sur l'une ou
    l'autre entrée -> False (toute comparaison avec NaN vaut False), comme
    `classify_retracement`.

    CORRECTION (vérification adversariale dédiée, cycle suivant) : la
    version initiale de cette fonction ne bornait le retracement que par le
    bas (`r >= FAVORABLE_MIN`), sans plafond haut — un bug de fidélité
    réel, pas cosmétique : ce fichier affirme lui-même en tête (synthèse
    retenue) qu'au-delà de 61,8% le retracement est "défavorable / invalidé
    (Red Flag explicite de #10)", et la propre table de décision GO/WAIT de
    #13 est encore plus stricte ("GO si cluster Fibonacci entre 23% et
    38%"). Sans plafond, `fib_regle_50` s'est révélé PLUS LARGE que
    `fib_favorable` en nombre de bougies (mesuré : 65,2% des bougies
    validées par la version buguée avaient en réalité un retracement >61,8%
    sur BTC H4), contredisant la prétention du commit d'origine ("condition
    BEAUCOUP plus restrictive") — le faible nombre de trades mesuré
    initialement venait d'une anticorrélation avec les autres gates
    (score/MTF), pas d'un resserrement réel de la zone. Plafonner à
    `FAVORABLE_MAX` (au lieu du 38% de la table GO/WAIT de #13, plus strict
    encore) est le choix qui réutilise une borne déjà établie et justifiée
    dans ce même fichier plutôt que d'en inventer une 3e — cohérent avec la
    discipline "pas de nouveau seuil sans le documenter comme hypothèse"."""
    r = np.asarray(retracement_pct, dtype=float)
    p = np.asarray(context_position, dtype=float)
    return (r >= FAVORABLE_MIN) & (r <= FAVORABLE_MAX) & (p >= REGLE_50_CONTEXT_MIN)

def add_fibonacci_columns(df: pd.DataFrame, order: int = SWING_ORDER) -> pd.DataFrame:
    """Ajoute `fib_retracement_pct` (fraction, NaN si pas de mouvement
    confirmé), `fib_favorable` (bool, zone [23%, 61,8%]), `fib_optimal`
    (bool, sous-zone [23%, 50%]), `fib_context_position` (fraction, cf.
    `compute_context_position`) et `fib_regle_50` (bool, "Règle des 50%"
    complète à 2 conditions cumulatives, cf. `classify_regle_50`) à `df`.
    N'utilise QUE des données connues à l'instant de chaque bougie — causal
    (réserve P0-bis traitée, cf. `compute_swing_highs_lows`) : un swing
    low/high n'entre dans le calcul de retracement qu'une fois réellement
    confirmé (`order` bougies après le creux/sommet lui-même), jamais
    avant ; le canal de contexte est lu avec `.shift(1)` (cf.
    `compute_context_position`).

    EXIGENCE DURE introduite par les colonnes `fib_context_position`/
    `fib_regle_50` (vérification adversariale dédiée, cycle suivant) : `df`
    doit désormais contenir une colonne `date` (utilisée par
    `compute_context_position` pour le rolling calendaire) — avant leur
    ajout, cette fonction acceptait un df `high`/`low`/`close` seul. Lève
    `KeyError` explicitement si absente, pas un comportement silencieux ;
    les deux appelants réels (`backtest_phase2_fib.py`,
    `cross_stress_test_faithful_gates.py`) passent tous deux un df issu de
    `prepare()`, qui a toujours `date` — non cassé, mais signalé ici comme
    rupture de contrat d'API pour tout futur appelant."""
    df = df.copy()
    retracement = compute_retracement(df, order=order)
    favorable, optimal = classify_retracement(retracement)
    context_position = compute_context_position(df)
    regle_50 = classify_regle_50(retracement, context_position)
    df["fib_retracement_pct"] = retracement
    df["fib_favorable"] = favorable
    df["fib_optimal"] = optimal
    df["fib_context_position"] = context_position
    df["fib_regle_50"] = regle_50
    return df

if __name__ == "__main__":
    import sys
    
    from emile.backtests.backtest_phase2 import load_h1, resample

    df = resample(load_h1("BTCUSDT"), "1D")
    scored = add_fibonacci_columns(df)
    print(scored[["date", "close", "fib_retracement_pct", "fib_favorable", "fib_optimal",
                  "fib_context_position", "fib_regle_50"]].tail(40).to_string(index=False))
    print("\nRépartition (BTC D1) :")
    print("favorable :", scored["fib_favorable"].mean().round(3))
    print("optimal   :", scored["fib_optimal"].mean().round(3))
    print("regle_50  :", scored["fib_regle_50"].mean().round(3))
    print("NaN (pas encore de mouvement confirmé) :", scored["fib_retracement_pct"].isna().mean().round(3))
