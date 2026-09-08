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
un hypothèse voisine mais DISTINCTE : `trend_table.py` a sa propre
hypothèse H7 sur la phrase "retour min 50% contexte" (RULES_EXTRACTION.md
§1, séquence compressée de la table de tendance à 5 étapes), interprétée
LÀ-BAS comme "recovery_frac >= 0.50" (fraction du retracement regagnée
depuis le creux). C'est une phrase différente, dans un module différent,
pour un usage différent (l'étape Pull-Back de la table TENDANCE à 5
étapes, pas le filtre de qualité d'entrée générique de ce fichier) — H7
n'est PAS modifiée ici, et la "Règle des 50%" ci-dessous n'est PAS
réconciliée avec elle : ce sont deux lectures de deux phrases distinctes du
corpus, chacune scopée à son propre module (cohérent avec H6 ci-dessous :
ce fichier reste délibérément séparé de trend_table.py).

"Le contexte" dans la règle de #13 est interprété comme LE MÊME canal de
contexte déjà établi ailleurs dans le projet (`ctx_high`/`ctx_low`, fenêtre
`CONTEXT_DURATION` = "15D", `backtest_phase2_v7.py::prepare`/
`trend_table.py::add_trend_context`) — pas une nouvelle définition
inventée ici, la même réutilisée à l'identique (même fenêtre, même
construction causale `shift(1)`). Lecture alternative explicitement
écartée mais envisagée : "le contexte" = le mouvement de retracement
lui-même (auquel cas "50% inférieurs" désignerait un retracement >= 50%) —
écartée parce qu'elle contredirait la propre description de #13 du niveau
50% comme "exceptionnel, rare" (un plancher à 50% rendrait le seuil
minimal de 23% sans objet). Ce fichier reste néanmoins volontairement
séparé de `trend_table.py` (H6) : `compute_context_position` ci-dessous
RECALCULE le canal de contexte plutôt que d'importer les colonnes déjà
calculées par `backtest_phase2_v7.py`/`trend_table.py`, pour ne pas rendre
ce module dépendant d'eux.

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
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from proxy_v2 import compute_swing_low_confirmed, compute_swing_high_confirmed

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
    `backtest_phase2_v7.py::prepare`/`trend_table.py::add_trend_context` —
    cf. MISE À JOUR en tête de fichier) : 0.0 = close au sommet du canal,
    1.0 = close au bas du canal.

    CAUSAL comme le reste du fichier : `.shift(1)` avant lecture, la
    bougie courante n'entre jamais dans son propre canal de référence (même
    construction que `trend_table.py::ctx_high`/`ctx_low`).

    Nécessite une colonne `date` (utilisée pour le rolling calendaire,
    comme partout ailleurs où `CONTEXT_DURATION` est utilisé dans le
    projet). NaN pour la toute première bougie (`shift(1)` sans historique
    antérieur) ou si `ctx_high == ctx_low` (canal de largeur nulle, division
    évitée) ; en-deçà de 15 jours calendaires de profondeur, la fenêtre
    reste PARTIELLE (pas NaN) — même comportement par défaut de
    `.rolling(<offset>)` que `context_range`/`ctx_high`/`ctx_low` ailleurs
    dans le projet (`backtest_phase2_v7.py`/`trend_table.py`), pas un choix
    nouveau introduit ici."""
    ts = df.set_index("date")
    ctx_high = ts["high"].rolling(duration).max().shift(1)
    ctx_low = ts["low"].rolling(duration).min().shift(1)
    span = (ctx_high - ctx_low).replace(0, np.nan)
    position = (ctx_high - ts["close"]) / span
    return position.values


def classify_regle_50(retracement_pct, context_position) -> np.ndarray:
    """"Règle des 50%" (#13, citée en tête de fichier) : condition CUMULATIVE
    (ET, pas OU, contrairement à `classify_retracement` ci-dessus qui teste
    une seule condition) — retracement >= 23% (`FAVORABLE_MIN`, même seuil
    que la classification favorable/optimale) ET pénétration du close dans
    les 50% inférieurs du canal de contexte (`context_position >=
    REGLE_50_CONTEXT_MIN`). NaN sur l'une ou l'autre entrée -> False (toute
    comparaison avec NaN vaut False), comme `classify_retracement`."""
    r = np.asarray(retracement_pct, dtype=float)
    p = np.asarray(context_position, dtype=float)
    return (r >= FAVORABLE_MIN) & (p >= REGLE_50_CONTEXT_MIN)


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
    `compute_context_position`)."""
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
    sys.path.insert(0, ".")
    from backtest_phase2 import load_h1, resample

    df = resample(load_h1("BTCUSDT"), "1D")
    scored = add_fibonacci_columns(df)
    print(scored[["date", "close", "fib_retracement_pct", "fib_favorable", "fib_optimal",
                  "fib_context_position", "fib_regle_50"]].tail(40).to_string(index=False))
    print("\nRépartition (BTC D1) :")
    print("favorable :", scored["fib_favorable"].mean().round(3))
    print("optimal   :", scored["fib_optimal"].mean().round(3))
    print("regle_50  :", scored["fib_regle_50"].mean().round(3))
    print("NaN (pas encore de mouvement confirmé) :", scored["fib_retracement_pct"].isna().mean().round(3))
