"""
Score de confluence "confiance de trade" — RECADRAGE DIRECT DE L'UTILISATEUR
(après le 22e round) : le capital risqué chez Philippe ne dépend pas d'un
profil FIXE choisi par le trader (`PROFILES_V4` FAIBLE/MODERE/AGRESSIF/
TRES_AGRESSIF), mais de la CONFIANCE dans CE trade précis, elle-même
déterminée par des conditions BOOLÉENNES (pas par le score continu 0-100
propriétaire, catégorie A, jamais tenté -- cf. ci-dessous).

Source : `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` (#5), section 3
("Système de notation -- gradient de confiance 0-100") et sa "Checklist de
pré-trade complète" (7 points).

CE QUI EST LITTÉRAL ET DÉJÀ CODÉ AILLEURS DANS CE PROJET (réutilisé tel
quel, jamais recalculé) -- 3 DES 7 POINTS DE LA CHECKLIST, décision de
conception #1 (H-Confidence-1) :

  1. **"Absence de Conflit MTF : aucun range d'unité de temps supérieure en
     cours ?"** -- déjà un gate exact dans `faithful.py`/`unified_protocol.py`
     (`regime_d1 not in ("RANGE_NEUTRE", "RANGE_TENDANCIEL")`, correction
     Conflit MTF). Réutilisé tel quel, périmètre RANGE (la citation parle
     explicitement d'"une borne de range", pas de tendance).
  2. **"Structure : tendance initiale identifiée et contexte opposé
     renversé ?"** -- section 1 du même document ("Anatomie du pattern
     range", règles 1-2 : "Mouvement de tendance préalable" + "Renversement
     du contexte"). Approximé par la maturité de bornes déjà utilisée comme
     gate d'entrée RANGE dans TOUT ce projet depuis v4 (`n_borders >=
     MIN_BORDERS`) -- même primitive, pas une réinvention (H-Confidence-2).
  3. **"Zone spéculative : prix dans le cluster (Fibonacci + zone
     graphique) ?"** -- `fibonacci.py::fib_favorable` (zone [23%, 61,8%],
     déjà entièrement codée et testée, cf. `test_fibonacci.py`).

CE QUI RESTE HORS PÉRIMÈTRE, À RAISON (pas des oublis) :
  4. **"Dimensionnement : stop loss indexé sur le canal ?"** -- déjà
     INCONDITIONNEL dans `faithful.py`/`unified_protocol.py` (règle de
     volatilité "Stop Loss = taille du canal", 6e round) : ce n'est pas une
     condition qui VARIE d'un trade à l'autre pour évaluer la confiance,
     c'est un mécanisme de sizing déjà toujours actif -- ne peut pas être
     un INPUT de ce score sans double-compte.
  5. **"Nature du signal : couleur (61% possible) ou gris (76% obligatoire)
     ?"** -- dépend de la classification en catégories de signal (TP/
     Overload/DIV/EXIT/SurAchat/BULL-BEAR/SQUEEZE, §2 du manuel) que seul
     l'algorithme PRO propriétaire produit -- catégorie A, `PLAN.md`/
     `COUVERTURE_ENSEIGNEMENTS.md`, "ne pas tenter d'implémenter une
     approximation inventée ici".
  6. **"Note de risque (0-100) : convergence Algo + Humain ?"** -- LE score
     continu propriétaire lui-même. Catégorie A, jamais tenté, même raison
     que le point 5. C'est PRÉCISÉMENT ce que ce module NE reproduit PAS --
     il construit un score DIFFÉRENT, à partir des 3 conditions booléennes
     ci-dessus, explicitement documenté comme une approximation À NOUS de
     l'esprit de la checklist, pas une reproduction du score propriétaire.
  7. **"Automatisation : alertes de validation et confirmation
     positionnées ?"** -- hors périmètre du projet en phase actuelle
     (`tests/unit/test_no_execution_automation.py`, aucune automatisation
     d'exécution réelle).

HYPOTHÈSE DE CONCEPTION (H-Confidence-3, LA SEULE vraie invention de ce
module -- documentée comme telle, pas cachée) : le corpus donne 3 BANDES
nommées sur un score CONTINU 0-100 (<50 abstention totale, 60-75 exposition
standard, 80-90+ "carton plein"), jamais un score DISCRET 0-3. Faute d'un
score continu reproductible, ce module compte simplement COMBIEN des 3
conditions booléennes ci-dessus sont réunies SIMULTANÉMENT à une bougie
donnée (0 à 3), et regroupe ce compte sur les 3 bandes nommées par le
corpus de la façon la plus conservatrice possible (H-Confidence-4) :
  - 0 ou 1 condition réunie -> **ABSTENTION TOTALE** (aucune tranche
    ouverte) -- lecture prudente de "<50" : moins de la majorité des
    conditions connues réunies ne justifie pas d'exposition, exactement
    l'esprit de la citation ("risque dépasse le seuil de rationalité").
  - 2 conditions réunies -> **exposition STANDARD** (même `risk_pct` que
    le profil MODERE actuel, 2%, réutilisé comme ancre déjà légitimée par
    le corpus -- pas un nouveau chiffre inventé).
  - 3 conditions réunies (les 3 en même temps) -> **"CARTON PLEIN"**,
    exposition MAXIMALE (même `risk_pct` que TRES_AGRESSIF, 5%, le
    plafond dur du manuel §5 -- "perte spéculative jamais >5% du capital").

Ce module est un BANC DE MESURE ISOLÉ (même discipline que
`andrews_gate_alternative.py`/`backtest_phase2_v7_squeeze.py` avant eux) :
il calcule le score et son effet mesuré sur des données réelles, MAIS N'EST
PAS ENCORE câblé dans `faithful.py`/`unified_protocol.py` (qui utilisent
toujours un `risk_pct` scalaire par profil, capturé une fois par run --
remplacer ça par un `risk_pct` PAR TRANCHE, résolu à l'ouverture depuis ce
score, est un changement structurel de `position_engine.py::make_open_
tranche_fn`, hors périmètre de ce round). Décision de câblage à prendre
séparément, une fois ce banc validé -- même méthode que Andrews contextuel
(designé et mesuré isolément AVANT d'être combiné, 2 rounds plus tard).
"""
import numpy as np
import pandas as pd

from emile.backtests.backtest_phase2_v7 import MIN_BORDERS

# H-Confidence-4 (cf. tête de fichier) : mapping score de confluence (0-3)
# -> risk_pct, ancré sur les chiffres DÉJÀ légitimés par le corpus dans
# PROFILES_V4 (pas des valeurs inventées) : 2% = MODERE (exposition
# "standard"), 5% = TRES_AGRESSIF (le plafond dur du manuel §5, "carton
# plein"). `None` = abstention totale (aucune tranche ouverte).
CONFIDENCE_RISK_PCT = {
    0: None,
    1: None,
    2: 0.02,
    3: 0.05,
}


def compute_range_confidence_score(regime_d1, n_borders, fib_favorable,
                                    min_borders: int = MIN_BORDERS) -> np.ndarray:
    """Score de confluence 0-3 par bougie (cf. tête de fichier, les 3
    conditions H-Confidence-1) : fonction PURE, ne recalcule AUCUN
    indicateur -- les 3 tableaux d'entrée sont produits ailleurs
    (`attach_multi_context`/CORRECTION CONFLIT MTF, `n_borders` de
    `prepare()`, `fibonacci.add_fibonacci_columns`), exactement comme les
    autres détecteurs additifs de ce projet (`compute_wide_channel`,
    `compute_squeezed_third_border`).

    Renvoie NaN là où une des 3 entrées est NaN -- un score de confiance
    ne peut pas être évalué sur une donnée manquante, il ne doit JAMAIS
    être traité comme "condition non réunie" (0) par erreur silencieuse."""
    regime_d1 = np.asarray(regime_d1, dtype=object)
    n_borders = np.asarray(n_borders, dtype=float)
    fib_favorable = np.asarray(fib_favorable)
    n = len(regime_d1)
    score = np.full(n, np.nan)
    for i in range(n):
        if n_borders[i] != n_borders[i]:   # NaN
            continue
        r = regime_d1[i]
        if r is None or (isinstance(r, float) and r != r):   # NaN
            continue
        fv = fib_favorable[i]
        if fv is None or (isinstance(fv, float) and fv != fv):   # NaN
            continue
        c1 = r not in ("RANGE_NEUTRE", "RANGE_TENDANCIEL")   # absence Conflit MTF
        c2 = n_borders[i] >= min_borders                     # structure/tendance confirmée
        c3 = bool(fv)                                        # zone spéculative Fibonacci
        score[i] = int(c1) + int(c2) + int(c3)
    return score


def confidence_to_risk_pct(score) -> float | None:
    """Traduit un score de confluence (0-3, éventuellement NaN) en
    `risk_pct` (H-Confidence-4, cf. tête de fichier). `None` = abstention
    totale (aucune tranche ne doit être ouverte) -- NaN (score inconnu)
    traité comme abstention aussi, jamais comme une exposition par défaut."""
    if score != score:   # NaN
        return None
    return CONFIDENCE_RISK_PCT.get(int(score))
