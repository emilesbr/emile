"""
Protocole unifié — routeur de régime RANGE <-> TENDANCE (PLAN.md, section
"Protocole unifié — routeur de régime range <-> tendance", chantier ouvert
avant ce fichier). Répond au constat honnête de `CONFIGURATION_RECOMMANDEE.md`
("avons-nous unifié tous les moteurs de décision dans un même protocole de
trading ?" -- non) : jusqu'ici `backtest_phase2_recommended.py` (moteur
RANGE) et `trend_table.py` (moteur TENDANCE) tournaient dans deux scripts
séparés, jamais arbitrés, capables de vouloir agir sur le même actif au même
instant sans qu'aucun code ne tranche.

Ce fichier N'IMPLÉMENTE AUCUNE NOUVELLE LOGIQUE DE POSITION. Il réutilise
tel quel :
  - côté RANGE : `position_engine.py::process_tranche`/`process_reverse`/
    `make_open_tranche_fn`, la préparation de features de
    `backtest_phase2_recommended.py::_prepare_features` (cycle+structure
    causaux, gate Hebdomadaire "UT+2 strict"), et depuis la CONSOLIDATION
    ci-dessous les 3 règles littérales de `backtest_phase2_faithful.py`
    (stop D1 UT+1, abstention Wall Street, +Reverse scopé TRES_AGRESSIF).
  - côté TENDANCE : `trend_table.py::step_campaign`/`try_open_campaign`/
    `step_reverse`/`add_leg`, et sa préparation de features
    (`backtest_phase2_v7.prepare` + `trend_table.add_trend_context` +
    volume, cf. hypothèses H1-H12 documentées dans `trend_table.py`).
Le seul code nouveau ici est la BOUCLE D'ORCHESTRATION bar-par-bar qui route
entre les deux (`run_unified`), et la fonction de décision live
(`decide_now`) qui l'interroge sur l'état courant d'un actif.

================================================================================
CONSOLIDATION (8 sept. 2026) -- le côté RANGE utilise désormais les mêmes
règles littérales que `backtest_phase2_faithful.py`, pas celles (moins
fidèles) de `recommended.py`
================================================================================
Constat qui motive ce chantier : `recommended.py` (utilisé jusqu'ici comme
côté RANGE de ce routeur) désactive par défaut 3 règles littérales du corpus
(stop UT+1 réel, abstention Wall Street, +Reverse TRES_AGRESSIF) sur la
seule base d'une contre-performance mesurée sur le proxy -- exactement
l'erreur corrigée dans `backtest_phase2_faithful.py` (cf. sa tête de
fichier, `CONFIGURATION_RECOMMANDEE.md` section 5ter). Faire tourner ce
routeur avec le côté RANGE de `recommended.py` produisait donc un protocole
"unifié" qui n'était PLUS fidèle au corpus sur son propre volet RANGE, alors
même que le volet TENDANCE, lui, l'était. Incohérence corrigée ici : le
côté RANGE de ce fichier applique désormais les 3 mêmes règles SANS
CONDITION, exactement comme `backtest_phase2_faithful.py` -- ce fichier
devient ainsi LE protocole complet à utiliser opérationnellement (RANGE
fidèle + TENDANCE, tous deux concurrents et indépendants), plutôt que deux
livrables séparés (`faithful.py` pour RANGE seul, `unified_protocol.py`
pour RANGE(recommended)+TENDANCE) mesurant chacun une combinaison
partielle.
`h4` DOIT désormais inclure les colonnes nécessaires au stop D1 (fournies
via un nouveau paramètre `d1` dans `run_unified`/`decide_now`, cf.
`resample(h1, "1D")`). Le côté TENDANCE reste inchangé (son propre stop
"Extreme Channel" est déjà, par choix littéral de `trend_table.py` lui-même
-- hypothèse H4 documentée là-bas --, le canal NATIF H4, pas le stop
cross-timeframe D1 : ce sont deux règles distinctes du corpus, pas la même
règle appliquée deux fois).

================================================================================
CORRECTION EXCES H4 (mobilisation multi-agents, audit systématique de
fidélité IP) -- côté RANGE ne vérifiait plus le régime EXCES du H4 natif
================================================================================
`RULES_EXTRACTION.md` §1 ("Bulle / Excès -> NE PAS TRADER", ~5% du temps)
est une règle littérale INCONDITIONNELLE portant sur le régime du MARCHÉ
QU'ON TRADE -- pas seulement sur son contexte supérieur. Depuis
`backtest_phase2_v7.py` (qui a introduit la validation croisée D1), le
gate RANGE de ce fichier (hérité de cette lignée) ne vérifiait plus QUE le
régime EXCES du contexte Hebdomadaire -- le régime EXCES du H4 natif
(`feat["regime"]`, déjà calculé pour le côté TENDANCE, jamais lu côté
RANGE) n'était jamais consulté par le gate RANGE. Le côté TENDANCE, lui,
vérifie correctement son PROPRE régime H4 pour abandonner une campagne
(`_campaign_ev::regime_excess`) -- exactement ce que le côté RANGE ne
faisait plus. **Corrigé** : `gate()` de `_run_core_unified` vérifie
désormais `feat["regime"][i] != "EXCES"` EN PLUS du gate Hebdomadaire.
Impact chiffré honnête : cf. `PLAN.md`/`CONFIGURATION_RECOMMANDEE.md`.

================================================================================
CORRECTION PYRAMIDALISATION-RÉGIME (mobilisation multi-agents, audit
systématique de fidélité IP, cycle suivant) -- côté RANGE pyramidalisait
sans restriction de régime
================================================================================
`RULES_EXTRACTION.md` §3 (table Money Management RANGE) ne contient JAMAIS
de cellule "Renfort", à aucune ligne de profil -- contrairement à §4 (table
TENDANCE) qui en a systématiquement. `backtest_phase2_v6.py` traduisait déjà
correctement ça en code (`pyramiding_allowed = regime in ("TENDANCE",
"RANGE_TENDANCIEL")`, appliqué SEULEMENT au renfort, jamais à l'entrée
fraîche) -- règle perdue silencieusement au refactor v6->v7 (même catégorie
de bug que EXCES-H4 ci-dessus : une donnée déjà calculée, `feat["regime"]`,
mais jamais relue pour CETTE règle précise côté RANGE). Vérifié
empiriquement AVANT correction : sur BTC/ETH/BNB/SOL réels, le côté RANGE de
ce fichier partage le même schéma de `gate_extra` (même booléen pour
entrée fraîche et renfort) que `backtest_phase2_faithful.py`, où 25,7% des
renforts réellement ouverts l'étaient en régime RANGE_NEUTRE avant
correction. **Corrigé** : `gate_extra` de `_run_core_unified` distingue
désormais entrée fraîche (`gate(j)` seul, INCHANGÉ) et renfort (`gate(j)
and pyramiding_allowed`, `pyramiding_allowed = feat["regime"][j] in
("TENDANCE", "RANGE_TENDANCIEL")`). Impact chiffré honnête : cf. `PLAN.md`/
`CONFIGURATION_RECOMMANDEE.md`.

================================================================================
CORRECTION CONFLIT MTF (mobilisation multi-agents, 3e round -- design puis
implémentation, audit systématique de fidélité IP) -- côté RANGE ne
vérifiait jamais si le contexte D1 était lui-même en range
================================================================================
`TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` (source #5) désigne, dans son
propre texte, une règle comme *"l'erreur numéro un"* : *"Ne jamais trader
une borne de range si un range d'unité de temps supérieure est déjà actif."*
Détail complet du raisonnement (niveau D1 retenu plutôt qu'Hebdomadaire,
application uniforme entrée+renfort faute de distinction textuelle, gate
Fibonacci littéral délibérément PAS implémenté ce cycle) : cf. "CORRECTION
CONFLIT MTF" en tête de `backtest_phase2_faithful.py`. Résumé ici : `regime_d1`
(`ctx["D1"]["regime"]`, déjà calculé pour le stop `ctx_support_d1` ci-dessus,
jamais lu pour cette règle) ajouté à `feat`, `gate()` de `_run_core_unified`
bloque désormais aussi quand `regime_d1` est RANGE_NEUTRE ou
RANGE_TENDANCIEL. Impact chiffré honnête : cf. `PLAN.md`/
`CONFIGURATION_RECOMMANDEE.md`. **Portée réelle (vérifiée par un round de
vérification adversariale dédié)** : `gate()` alimente aussi
`gated_long_signal`, qui pilote la sortie "flip de signal" -- une tranche
déjà ouverte mais pas encore Validée (`val_done=False`) est donc FERMÉE, pas
seulement bloquée à l'ouverture, si `regime_d1` bascule en range en cours de
vie -- cf. détail complet dans `backtest_phase2_faithful.py`.

================================================================================
CORRECTION (8 sept. 2026) -- l'exclusivité mutuelle par actif a été RETIRÉE
================================================================================
Version initiale de ce fichier : au plus UN système (RANGE ou TENDANCE)
pouvait avoir une position ouverte par actif (`active_system in {None,
"range", "trend"}`), justifiée à l'époque par "un seul contexte à la fois"
(lecture de RULES_EXTRACTION.md section 1, "TOUJOURS TRADER DANS UN
CONTEXTE"). L'utilisateur a directement contesté cette restriction ("nous ne
devons pas nous limiter a une seul stratégie par actif... les enseignements
n'indiquent pas que nous ne pouvons pas trader plusieurs ranges ou plusieurs
tendances ou des range et des tendances simultanément"). Vérification
directe des sources plutôt qu'une supposition dans un sens ou l'autre :

- `RULES_EXTRACTION.md` section 1 ("Classification du contexte") décrit
  comment CLASSER le régime (range neutre/tendanciel/tendance/excès) pour
  choisir la bonne table de décision -- une règle de LECTURE du marché, pas
  une restriction du nombre de positions simultanées. Rien dans cette
  section ni ailleurs dans le manuel officiel n'interdit plusieurs positions
  concurrentes.
- `TRADING_LESSONS_CLUSTERS_PRIX.md` (source #16) documente EXPLICITEMENT le
  contraire de l'exclusivité : "Diversification statistique du risque...
  1% sur la pattern breakout/pullback + 1% sur la pattern de moyenne mobile
  (cluster)... jouer les deux augmente les chances d'être 'dans le train'"
  -- deux patterns indépendants, ouverts SIMULTANÉMENT, chacun avec son
  propre risque. La seule limite posée est un plafond de risque agrégé
  ("jamais >2% de risque maximal par zone de prix"), pas un système unique à
  la fois.
- `TRADING_LESSONS_PYRAMIDALISATION.md` (source #15) désigne les "positions
  multiples" comme le mécanisme même de la pyramidalisation ("toute
  augmentation du risque nominal (positions multiples) doit être compensée
  par un contexte de probabilités exceptionnelles"), et cite un cas réel
  (S&P 500) de DEUX patterns "3ème borne" ouverts en même temps.
- Précédent déjà présent dans ce projet AVANT ce chantier : la
  pyramidalisation range (`MAX_TRANCHES=3`, `position_engine.py`) autorise
  déjà plusieurs tranches concurrentes sur le même actif -- l'exclusivité
  mutuelle RANGE/TENDANCE était donc une restriction plus stricte que ce que
  le projet appliquait déjà à l'intérieur d'un seul système.

Conclusion : l'exclusivité mutuelle par actif était une simplification
introduite unilatéralement lors de la conception de ce routeur, jamais une
exigence du corpus -- au contraire, contredite par les sources #15/#16.
Retirée ci-dessous. Ce que le corpus établit VRAIMENT comme plafond de
risque (2% max par position -- déjà appliqué par système via son propre
`risk_pct` de profil -- et 1%+1% pour la diversification statistique) reste
hors du périmètre de CE routeur (qui reste RANGE vs TENDANCE, pas la
diversification Cluster Technique, cf. "hors périmètre" plus bas) --
documenté comme limite ouverte plutôt qu'inventé silencieusement : aucun
plafond de risque AGRÉGÉ entre les deux systèmes n'est appliqué ici (cf. U5
ci-dessous).

================================================================================
DÉCISIONS D'ARCHITECTURE (révisées -- ce fichier les EXÉCUTE)
================================================================================
1. **Indépendance totale des deux systèmes** : à chaque bougie, RANGE et
   TENDANCE évaluent et gèrent chacun leurs propres positions SANS jamais se
   bloquer l'un l'autre. `accumulation_active` (déclencheur du moteur
   TENDANCE, `trend_table.py::try_open_campaign`) ouvre une campagne
   tendance dès qu'aucune campagne/"+Reverse" tendance n'est déjà en cours
   -- que le moteur RANGE ait ou non une tranche ouverte au même instant, et
   réciproquement. Chaque système garde le comportement déjà validé de son
   moteur seul (`backtest_phase2_faithful.py` côté RANGE depuis la
   CONSOLIDATION ci-dessus -- gate Hebdomadaire "regime != EXCES", stop D1
   UT+1, abstention Wall Street, +Reverse scopé TRES_AGRESSIF ; `trend_table.py`
   côté TENDANCE, inchangé).
2. **Aucun plafond de risque agrégé inventé entre les deux systèmes** (cf.
   "CORRECTION" ci-dessus) : chaque système applique son propre `risk_pct`
   de profil, déjà borné par système (`PROFILES_V4`/`PROFILES_TREND`,
   inchangés). Le corpus documente un plafond agrégé explicite (1%+1%, "max
   2% par zone de prix") pour la paire SPÉCIFIQUE breakout/pullback +
   cluster-MA (diversification statistique, `TRADING_LESSONS_CLUSTERS_PRIX.md`)
   -- pas pour la paire RANGE-table/TENDANCE-table de ce routeur, qui reste
   une paire différente. Étendre ce plafond ici serait une extrapolation non
   mesurée ; documenté comme limite ouverte (U5), pas comblé par une valeur
   inventée.
3. **Aucune réimplémentation de logique métier** : cf. import list
   ci-dessous -- uniquement des fonctions PAR BOUGIE déjà existantes.
4. **Sortie "décision live"** : `decide_now()`, révisée pour rapporter RANGE
   et TENDANCE indépendamment (les deux peuvent être actifs/avoir un signal
   en même temps, cf. sa docstring).
5. **Mesure honnête** : `main()` compare le protocole unifié (désormais sans
   exclusivité) à `recommended.py` seul, sans présupposer un meilleur
   résultat (cf. `backtest_phase2_unified_results.csv`, regénéré après cette
   correction).

================================================================================
CHOIX D'IMPLÉMENTATION DE CE FICHIER (documentés, pas inventés en silence,
même esprit que les hypothèses H1-H12 de `trend_table.py`)
================================================================================
U1. **`h4` doit inclure une colonne `volume`** (agrégée en somme sur la
    fenêtre H4) -- nécessaire au déclencheur Breakout de la table de
    tendance (H9 de `trend_table.py`, volume > 1.5x sa moyenne mobile 20).
    `resample_h4_with_volume(h1)` construit ce DataFrame en réutilisant
    tels quels `backtest_phase2.resample` (OHLC) et
    `trend_table.resample_volume` (volume), jointure `inner` sur `date`
    pour garantir l'alignement -- pas une nouvelle logique d'agrégation.
U2. **`win_streak` (Règle de Trois) est partagé entre les deux systèmes** :
    incrémenté par CHAQUE trade gagnant, qu'il vienne du moteur range ou du
    moteur tendance (cohérent avec "un seul tracker actif" / une seule
    séquence de trades unifiée -- ce choix ne dépendait pas de l'exclusivité
    mutuelle retirée ci-dessus, il reste valide indépendamment). Seul le moteur RANGE utilise
    concrètement ce compteur (Règle de Trois, `RULE3_STREAK`/
    `RULE3_SIZE_MULT`) ; le moteur tendance ne le lit jamais. Un choix
    alternatif (deux compteurs séparés par système) serait aussi défendable
    -- non retenu ici pour rester au plus près de l'esprit "protocole
    UNIQUE", documenté plutôt que tranché en silence.
U3. **Capital par palier (`capital_eur`)** : appliqué SEULEMENT au risk_pct
    du moteur RANGE (`capital_tiers.effective_sizing`, exactement comme
    `recommended.py`). PAS appliqué au risk_pct du moteur TENDANCE
    (`PROFILES_TREND[profile]["risk_pct"]`, inchangé) -- `capital_tiers.py`
    n'a jamais été construit/mesuré pour la table de tendance (ses jambes
    à taille variable, plafond de risque de campagne H3, ne correspondent
    pas au modèle "tranches à taille fixe, max_tranches" que
    `effective_sizing` suppose) ; l'étendre ici serait une extrapolation non
    mesurée, hors du principe "réutiliser tel quel". Documenté comme limite
    ouverte, pas un oubli.
U4. **`decide_now` : approximation "bougie fantôme"** pour évaluer un signal
    d'ouverture qui n'existe pas encore dans l'historique fourni -- toutes
    les fonctions par bougie (`open_tranche_fn`, `try_open_campaign`)
    calculent leur GATE sur la bougie i-1 (déjà entièrement connue) mais ont
    besoin d'un prix d'OUVERTURE `o[i]` pour la bougie i (pas encore
    observée en direct). On ajoute une bougie synthétique
    (open=high=low=close=dernière clôture connue) à la fin des tableaux pour
    pouvoir appeler ces fonctions SANS les modifier ni les dupliquer -- le
    gate lui-même ne dépend que de la bougie i-1 réelle, seul le prix
    d'entrée reporté est une approximation (documentée dans le champ
    `reason` de `decide_now`, jamais présentée comme un prix d'exécution
    garanti).
U5. **Pas de plafond de risque agrégé RANGE+TENDANCE** (limite ouverte,
    documentée, pas cachée -- cf. "CORRECTION" ci-dessus, décision #2) :
    quand les deux systèmes ont une position ouverte simultanément sur le
    même actif, le risque nominal total engagé est la SOMME des deux
    `risk_pct` de profil (ex. MODERE : 2% range + 2% tendance = jusqu'à 4%
    simultanés), jamais plafonné ici à un chiffre agrégé. Le corpus
    documente un plafond agrégé explicite (2% max) mais pour une paire de
    patterns différente (diversification statistique breakout/pullback +
    cluster-MA, `TRADING_LESSONS_CLUSTERS_PRIX.md`) -- l'étendre tel quel à
    la paire RANGE-table/TENDANCE-table de ce routeur serait une
    extrapolation non mesurée. À réexaminer si ce chantier est un jour
    étendu pour englober aussi la diversification Cluster Technique dans le
    même routeur (hors périmètre actuel, cf. "Ce que ce chantier NE fait
    PAS" dans PLAN.md).
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "/home/user/emile/code")

import numpy as np
import pandas as pd

from backtest_phase2 import FEE, load_h1, resample
from backtest_phase2_v7 import (
    prepare, PROFILES_V4, MIN_BORDERS, RULE3_STREAK, RULE3_SIZE_MULT,
    MAX_TRANCHES, EMA_SLOW,
)
from backtest_phase2_recommended import _prepare_features, WARMUP
from backtest_phase2_faithful import REVERSE_SCOPED_PROFILE, run_faithful
from backtest_phase2_ut2 import attach_multi_context, CLOSURE_DELAY
from position_engine import make_open_tranche_fn, process_tranche, process_reverse
from wall_street_pattern import add_wall_street_column
from regime_classifier import compute_wide_channel
from trend_table import (
    PROFILES_TREND, add_trend_context, add_leg, make_campaign, step_campaign,
    try_open_campaign, step_reverse, load_volume, resample_volume,
    ACCUM_RETRACEMENT_LOW, ACCUM_RETRACEMENT_HIGH, VOLUME_MA_WINDOW,
    VOLUME_EXPANSION_MULT,
)
from capital_tiers import effective_sizing

# Profils partagés entre les deux moteurs (mêmes 4 clés dans PROFILES_V4 et
# PROFILES_TREND -- FAIBLE/MODERE/AGRESSIF/TRES_AGRESSIF).
PROFILE_NAMES = list(PROFILES_V4.keys())


def resample_h4_with_volume(h1: pd.DataFrame) -> pd.DataFrame:
    """Construit un DataFrame H4 avec colonne `volume`, en réutilisant tels
    quels `backtest_phase2.resample` (OHLC) et `trend_table.resample_volume`
    (volume, agrégation somme), puis jointure `inner` sur `date` (cf. U1).
    `h1` doit contenir les colonnes date/open/high/low/close/volume."""
    ohlc = resample(h1[["date", "open", "high", "low", "close"]], "4h")
    vol = resample_volume(h1[["date", "volume"]], "4h")
    merged = ohlc.merge(vol, on="date", how="inner")
    return merged.reset_index(drop=True)


def _prepare_unified(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame,
                      use_mtf_gate: bool = True) -> dict:
    """Calcule TOUTES les colonnes nécessaires aux deux moteurs, une fois,
    sur l'historique complet fourni.

    RANGE : réutilise `backtest_phase2_recommended._prepare_features` tel
    quel (cycle+structure causaux, gate Hebdomadaire "UT+2 strict"), PLUS
    (CONSOLIDATION, cf. tête de fichier) le stop D1 réel UT+1
    (`ctx_support_d1`, même jointure sans lookahead que `backtest_phase2_faithful.py`)
    et la colonne Wall Street (`wall_street_active`).
    TENDANCE : réutilise `backtest_phase2_v7.prepare` +
    `trend_table.add_trend_context` tels quels (stop natif H4, hypothèse H4
    de `trend_table.py`, inchangé -- pas le même stop que RANGE), plus la
    détection volume de `trend_table.py` (H9) calculée ici EXACTEMENT comme
    dans `run_trend_table` (même fenêtre glissante, même seuil)."""
    if "volume" not in h4.columns:
        raise ValueError(
            "h4 doit contenir une colonne 'volume' (requise par le moteur "
            "tendance, cf. U1 dans la docstring du module) -- construire "
            "avec resample_h4_with_volume(h1)."
        )

    range_feat = _prepare_features(h4, weekly, use_mtf_gate=use_mtf_gate)

    # CONSOLIDATION : stop D1 réel (UT+1, cf. backtest_phase2_faithful.py)
    # et colonne Wall Street (abstention totale, non conditionnelle), côté
    # RANGE uniquement -- même jointure sans lookahead que `faithful.py`.
    d1p = prepare(d1.copy())
    ctx = attach_multi_context(h4, [("D1", d1p)], closure_delay=CLOSURE_DELAY)
    ctx_support_d1 = ctx["D1"]["ctx_support"]

    h4_ws = prepare(h4[["date", "open", "high", "low", "close"]].copy())
    h4_ws = add_wall_street_column(h4_ws)
    wall_street_active = h4_ws["wall_street_active"].values

    trend_df = prepare(h4[["date", "open", "high", "low", "close"]].copy())
    trend_df = add_trend_context(trend_df)

    vol_v = h4["volume"].values
    vol_ma = pd.Series(vol_v).rolling(VOLUME_MA_WINDOW).mean().values
    volume_expansion = vol_v > VOLUME_EXPANSION_MULT * np.roll(vol_ma, 1)
    volume_expansion[0] = False

    ema_trend_v = (trend_df["close"].ewm(span=EMA_SLOW, adjust=False).mean()).values

    feat = dict(range_feat)
    feat.update({
        "ctx_support_d1": ctx_support_d1,
        "regime_d1": ctx["D1"]["regime"],   # cf. CORRECTION CONFLIT MTF en tête de fichier
        "wall_street_active": wall_street_active,
        # Règle de volatilité "Stop Loss = taille du canal" (littérale,
        # inconditionnelle côté RANGE, cf. `backtest_phase2_faithful.py`) --
        # largeur du canal D1, le MÊME niveau que `ctx_support_d1` qui porte
        # le stop RANGE ici (H-Canal-Large-2, `position_engine.py`). Répliquée
        # ici pour que le côté RANGE du protocole unifié reste STRICTEMENT
        # identique à `faithful.py` (invariant vérifié par
        # `test_unified_protocol.py::test_pure_range_sequence_matches_faithful_engine`).
        # Le côté TENDANCE n'est PAS concerné (H-Canal-Large-4 : la règle est
        # scopée à la table RANGE par le corpus).
        "wide_channel": compute_wide_channel(ctx["D1"]["ctx_width_pct"]),
        "regime": trend_df["regime"].values,
        "ctx_resistance": trend_df["ctx_resistance"].values,
        "ctx_high": trend_df["ctx_high"].values,
        "local_high": trend_df["local_high"].values,
        "accum_retracement_frac": trend_df["accum_retracement_frac"].values,
        "cycle_favorable": trend_df["cycle_favorable"].values,
        "ema_trend": ema_trend_v,
        "volume_expansion": volume_expansion,
    })
    return feat


def _valid_trend_inputs(feat: dict, j: int) -> bool:
    """Même condition que `trend_table.run_trend_table::valid_inputs`."""
    return (
        not np.isnan(feat["atr"][j]) and not np.isnan(feat["ctx_support"][j])
        and not np.isnan(feat["ctx_resistance"][j]) and not np.isnan(feat["ctx_high"][j])
        and not np.isnan(feat["local_high"][j]) and not np.isnan(feat["n_borders"][j])
        and not np.isnan(feat["accum_retracement_frac"][j])
    )


def _accumulation_active(feat: dict, i: int) -> bool:
    """Réplique EXACTEMENT le calcul de `trend_table.run_trend_table` pour
    `accumulation_active`, gate `i > WARMUP and valid_inputs(i-1)` inclus."""
    if not (i > WARMUP):
        return False
    j = i - 1
    if not _valid_trend_inputs(feat, j):
        return False
    mature = feat["n_borders"][j] >= MIN_BORDERS
    channel_rejection = feat["low"][j] <= feat["ctx_support"][j] and feat["close"][j] > feat["ctx_support"][j]
    retracement_ok = ACCUM_RETRACEMENT_LOW <= feat["accum_retracement_frac"][j] <= ACCUM_RETRACEMENT_HIGH
    return bool(feat["regime"][j] == "TENDANCE" and mature and channel_rejection and retracement_ok)


def _campaign_ev(feat: dict, i: int) -> dict:
    """Même dict `ev` que `trend_table.run_trend_table` (breakout/divergence/
    excès/reverse_stop/reverse_target), calculé sur la bougie i-1 (et i-2
    pour la divergence), jamais i (pas encore connue au moment de l'entrée
    à l'open)."""
    j = i - 1
    valid_j = _valid_trend_inputs(feat, j)
    return {
        "regime_excess": feat["regime"][j] == "EXCES",
        "breakout_raw": (
            valid_j and feat["close"][j] > feat["local_high"][j]
            and feat["volume_expansion"][j] and feat["score"][j] >= 2
        ),
        "divergence_raw": (
            i >= 2 and bool(feat["cycle_favorable"][i - 2]) and not bool(feat["cycle_favorable"][j])
            and feat["close"][j] > feat["ema_trend"][j]
        ),
        "excess_raw": valid_j and feat["close"][i] > feat["ctx_high"][j] and feat["score"][j] >= 2,
        "reverse_stop": (max(feat["ctx_resistance"][j], feat["close"][i] * 1.001) if valid_j
                         else feat["close"][i] * 1.03),
        "reverse_target": feat["ctx_support"][j] if valid_j else feat["close"][i] * 0.97,
    }


def run_unified(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame, profile_name: str,
                 capital_eur: float = None,
                 use_mtf_gate: bool = True, record_state: bool = False) -> dict:
    """Boucle d'orchestration bar-par-bar -- LE seul code nouveau de ce
    fichier (cf. tête de fichier, décision #3). `h4` DOIT inclure une
    colonne `volume` (cf. `resample_h4_with_volume`, U1). `d1` : niveau
    Journalier pour le stop RANGE réel (UT+1, cf. CONSOLIDATION en tête de
    fichier) -- `resample(h1, "1D")`. `weekly` : niveau de contexte pour le
    gate RANGE (Hebdomadaire, "UT+2 strict", inchangé par rapport à
    `recommended.py`/`faithful.py`). `reverse_at_limit` n'est plus un
    paramètre : appliqué SANS CONDITION mais UNIQUEMENT au profil
    TRES_AGRESSIF, exactement comme `backtest_phase2_faithful.py` (règle
    littérale scopée, pas un choix de l'appelant).

    À chaque bougie H4 (après warmup), RANGE et TENDANCE sont gérés de façon
    INDÉPENDANTE (décision #1, révisée -- plus d'exclusivité mutuelle, cf.
    "CORRECTION" en tête de fichier) :
      - TENDANCE : si aucune campagne/"+Reverse" tendance en cours,
        `accumulation_active` ouvre une nouvelle campagne ; sinon fait
        progresser la campagne (`step_campaign`)/le "+Reverse" tendance
        (`step_reverse`) en cours -- exactement comme `trend_table.py` seul.
      - RANGE : tant qu'il reste de la place (`len(tranches) < MAX_TRANCHES`),
        tente une ouverture/pyramidalisation (comportement de
        `recommended.py`, gate Hebdo déjà inclus) ; fait progresser les
        tranches déjà ouvertes (`process_tranche`) -- exactement comme
        `recommended.py` seul.
      - Les deux peuvent être actifs SIMULTANÉMENT sur le même actif -- ce
        n'est plus arbitré (cf. U5 pour la limite documentée sur le risque
        agrégé qui en résulte).
    Les trades des deux systèmes sont agrégés dans les MÊMES statistiques
    (n_trades/max_dd_%/total_return_%/win_rate_%/profit_factor), comme le
    fait déjà `position_engine.py` pour range+"+Reverse" (cf. sa docstring).

    `record_state=True` ajoute la clé "live_state" au résultat : l'état du
    protocole à la TOUTE DERNIÈRE bougie de l'historique fourni, utilisé par
    `decide_now` (cf. U4 pour l'approximation "bougie fantôme")."""
    feat = _prepare_unified(h4, d1, weekly, use_mtf_gate=use_mtf_gate)
    risk_pct = None
    if capital_eur is not None:
        # U3 : capital par palier appliqué SEULEMENT au moteur RANGE.
        sizing = effective_sizing(capital_eur, profile_name, PROFILES_V4, MAX_TRANCHES)
        risk_pct = sizing.risk_pct
    return _run_core_unified(feat, profile_name, risk_pct=risk_pct, record_state=record_state)


def _run_core_unified(feat: dict, profile_name: str, risk_pct: float = None,
                       record_state: bool = False, start: int = 0, end: int = None) -> dict:
    """La boucle d'orchestration elle-même, séparée de `run_unified` sur le
    modèle `_prepare_features`/`_run_core` de `backtest_phase2_recommended.py`
    -- pour pouvoir être testée unitairement (`test_unified_protocol.py`) sur
    un `feat` dict CONSTRUIT À LA MAIN (scénarios synthétiques exacts),
    exactement comme `_run_core` est testable indépendamment de
    `_prepare_features` dans `test_backtest_phase2_recommended.py`.

    `feat` doit exposer TOUTES les clés produites par `_prepare_unified` :
    date/open/high/low/close/score/atr/ctx_support/ctx_support_d1/
    wall_street_active/local_range/context_range/n_borders/gate_score/
    gate_regime (côté RANGE, mêmes clés que `backtest_phase2_faithful.py`
    plus `ctx_support` natif H4, utilisé côté TENDANCE) + regime/
    ctx_resistance/ctx_high/local_high/accum_retracement_frac/
    cycle_favorable/ema_trend/volume_expansion (côté TENDANCE). `risk_pct`
    (défaut `None`) : risk_pct RANGE déjà résolu par l'appelant (profil fixe
    ou `capital_tiers.effective_sizing(...).risk_pct`, cf. U3) -- si `None`,
    celui du profil (`PROFILES_V4[profile_name]["risk_pct"]`).

    RANGE applique désormais SANS CONDITION les 3 règles littérales de
    `backtest_phase2_faithful.py` (CONSOLIDATION, cf. tête de fichier) :
    stop D1 (`ctx_support_d1`, pas le canal H4 natif), abstention Wall
    Street (bloque entrée fraîche ET renfort), +Reverse (`reverse_at_limit`)
    UNIQUEMENT pour le profil TRES_AGRESSIF.

    `start`/`end` (défaut : historique complet) : même principe que
    `backtest_phase2_faithful.py::_run_core` -- permet à `walkforward_unified.py`
    de découper l'équité par année SANS recalculer `feat` (déjà préparé une
    fois sur l'historique complet par `_prepare_unified`). Contrairement à
    `_run_core` (RANGE seul), les tableaux de `feat` ne sont PAS re-tranchés
    ici : `_accumulation_active`/`_campaign_ev`/`try_open_campaign` indexent
    `feat` par position ABSOLUE (le gate `i > WARMUP` de la table de tendance
    compare à l'index absolu dans l'historique complet, pas à un warmup
    relatif à la fenêtre) -- seule la boucle et la courbe d'équité sont
    bornées à `[start, end)`, l'équité repartant à 1.0 à `start` (même
    objectif "année catastrophique ?" que `walkforward_recommended.py`/
    `walkforward_faithful.py`, pas une performance cumulée réaliste)."""
    p_range = PROFILES_V4[profile_name]
    p_trend = PROFILES_TREND[profile_name]
    if risk_pct is None:
        risk_pct = p_range["risk_pct"]
    reverse_at_limit = (profile_name == REVERSE_SCOPED_PROFILE)

    o, high, low, c = feat["open"], feat["high"], feat["low"], feat["close"]
    score = feat["score"]
    wall_street_v = feat["wall_street_active"]
    n_total = len(o)
    end = n_total if end is None else end

    def gate(i: int) -> bool:
        # CORRECTION EXCES H4 (mobilisation multi-agents, audit systématique
        # de fidélité IP -- cf. CORRECTION dans backtest_phase2_faithful.py) :
        # le régime EXCES du H4 natif (feat["regime"], déjà calculé pour le
        # côté TENDANCE, jamais lu ici jusqu'à cette correction) doit aussi
        # bloquer côté RANGE -- "Bulle/Excès -> NE PAS TRADER"
        # (RULES_EXTRACTION.md §1) porte sur le marché qu'on trade, pas
        # seulement sur son contexte Hebdomadaire.
        # CORRECTION CONFLIT MTF (cf. tête de fichier) : ne jamais ouvrir une
        # tranche RANGE H4 si le contexte immédiatement supérieur (D1) est
        # LUI-MÊME en régime range (Neutre ou Tendanciel) -- source #5,
        # "L'erreur numéro un".
        d1_not_range = feat["regime_d1"][i] not in ("RANGE_NEUTRE", "RANGE_TENDANCIEL")
        return bool(
            feat["gate_score"][i] >= 2 and feat["gate_regime"][i] != "EXCES"
            and feat["regime"][i] != "EXCES" and d1_not_range
        )

    def gate_extra(j):
        # Abstention Wall Street NON CONDITIONNELLE (littérale, cf.
        # backtest_phase2_faithful.py) : bloque entrée fraîche ET renfort.
        abstain = bool(wall_street_v[j])
        g = gate(j) and not abstain
        # CORRECTION PYRAMIDALISATION-RÉGIME (cf. tête de fichier) : le
        # renfort (pas l'entrée fraîche) exige EN PLUS que le régime H4 natif
        # soit TENDANCE/RANGE_TENDANCIEL -- "Renfort" n'apparaît jamais dans
        # la table Money Management RANGE (§3), réservé à la table TENDANCE.
        pyramiding_allowed = feat["regime"][j] in ("TENDANCE", "RANGE_TENDANCIEL")
        return g, (g and pyramiding_allowed)

    range_state = {"last_pyramid_high": -np.inf}
    open_tranche_fn = make_open_tranche_fn(
        feat["atr"], feat["ctx_support_d1"], feat["local_range"], feat["context_range"],
        feat["n_borders"], high, o, score, WARMUP, MIN_BORDERS, MAX_TRANCHES,
        RULE3_STREAK, RULE3_SIZE_MULT, risk_pct, range_state, extra_gate_fn=gate_extra,
        wide_channel_v=feat["wide_channel"],   # littéral, non conditionnel (cf. faithful.py)
    )
    gated_long_signal = np.array([
        (score[i] >= 2) and gate(i) and not bool(wall_street_v[i]) for i in range(n_total)
    ])

    equity = 1.0
    equity_curve = np.empty(end - start)
    equity_curve[0] = equity

    tranches: list = []
    range_reverses: list = []
    campaign = None
    trend_reverse = None
    trades: list = []
    win_streak = 0
    n_trend_campaigns_opened = 0
    n_range_fresh_entries = 0

    for i in range(max(1, start + 1), end):
        # ---- 0) "+Reverse" TENDANCE (H10, trend_table.py) en cours ----
        if trend_reverse is not None:
            closed_r, fee_r, pnl_r = step_reverse(trend_reverse, i, high, low, c)
            if closed_r:
                equity *= (1 + pnl_r)
                trades.append(pnl_r)
                win_streak = win_streak + 1 if pnl_r > 0 else 0
            if fee_r > 0:
                equity *= (1 - FEE * fee_r)
            if closed_r:
                trend_reverse = None

        # ---- 1) "+Reverse" RANGE (H-Reverse-Range, position_engine.py) ----
        remaining_reverses = []
        for rp in range_reverses:
            closed_r, fee_r, pnl_r = process_reverse(rp, i, high, low, c)
            if closed_r:
                equity *= (1 + pnl_r)
                trades.append(pnl_r)
                win_streak = win_streak + 1 if pnl_r > 0 else 0
            if fee_r > 0:
                equity *= (1 - FEE * fee_r)
            if not closed_r:
                remaining_reverses.append(rp)
        range_reverses = remaining_reverses

        # ---- 2) campagne TENDANCE en cours ----
        if campaign is not None:
            ev = _campaign_ev(feat, i)
            closed, fee_frac, realized, reverse_request = step_campaign(campaign, i, o, high, low, c, ev, p_trend)
            if fee_frac > 0:
                equity *= (1 - FEE * fee_frac)
            if realized is not None:
                equity *= (1 + realized)
                trades.append(realized)
                win_streak = win_streak + 1 if realized > 0 else 0
            if closed:
                campaign = None
                if reverse_request is not None:
                    trend_reverse = reverse_request

        # ---- 3) tranches RANGE en cours ----
        if tranches:
            long_signal_prev = bool(gated_long_signal[i - 1])
            remaining_tranches = []
            new_range_reverses = []
            for tr in tranches:
                closed, fee_frac, realized = process_tranche(
                    tr, i, o, low, c, long_signal_prev,
                    val_close_frac=p_range["val_close"], conf_close_frac=p_range["conf_close"],
                    conf_to_be=True, reverse_at_limit=reverse_at_limit,
                )
                if fee_frac > 0:
                    equity *= (1 - FEE * fee_frac)
                if closed:
                    equity *= (1 + realized)
                    trades.append(realized)
                    win_streak = win_streak + 1 if realized > 0 else 0
                    rr = tr.get("reverse_request")
                    if rr is not None:
                        new_range_reverses.append(rr)
                        equity *= (1 - FEE * rr["remaining"])
                else:
                    remaining_tranches.append(tr)
            tranches = remaining_tranches
            range_reverses.extend(new_range_reverses)

        # ---- 4) tentatives d'ouverture INDÉPENDANTES (décision #1 révisée --
        # plus d'exclusivité mutuelle, cf. "CORRECTION" en tête de fichier) ----
        # TENDANCE : ouvre une nouvelle campagne si aucune campagne/"+Reverse"
        # tendance n'est en cours, QUEL QUE SOIT l'état RANGE au même instant.
        if campaign is None and trend_reverse is None and _accumulation_active(feat, i):
            j = i - 1
            new_campaign, fee_frac = try_open_campaign(i, o, feat["ctx_support"][j], True, p_trend)
            if new_campaign is not None:
                campaign = new_campaign
                n_trend_campaigns_opened += 1
                if fee_frac > 0:
                    equity *= (1 - FEE * fee_frac)

        # RANGE : tente une ouverture fraîche ou une pyramidalisation tant
        # qu'il reste de la place, QUEL QUE SOIT l'état TENDANCE au même
        # instant -- exactement le même appel que `recommended.py` seul.
        if len(tranches) < MAX_TRANCHES:
            was_flat = not tranches
            new_tr = open_tranche_fn(i, tranches, win_streak)
            if new_tr is not None:
                tranches.append(new_tr)
                if was_flat:
                    n_range_fresh_entries += 1
                equity *= (1 - FEE * new_tr["remaining"])

        # ---- 5) mark-to-market / equity curve ----
        mtm = 0.0
        for tr in tranches:
            mtm += tr["pnl_accum"] + (c[i] - tr["entry"]) / tr["entry"] * tr["remaining"]
        for rp in range_reverses:
            mtm += (rp["entry"] - c[i]) / rp["entry"] * rp["remaining"]
        if campaign is not None and campaign["remaining"] > 0:
            mtm += (c[i] - campaign["entry"]) / campaign["entry"] * campaign["remaining"]
        if trend_reverse is not None:
            mtm += (trend_reverse["entry"] - c[i]) / trend_reverse["entry"] * trend_reverse["frac"]
        equity_curve[i - start] = equity * (1 + mtm)

    trades_arr = np.array(trades) if trades else np.array([])
    eq_series = pd.Series(equity_curve)
    max_dd = (eq_series / eq_series.cummax() - 1).min()
    result = {
        "n_trades": len(trades_arr),
        "max_dd_%": round(max_dd * 100, 1),
        "total_return_%": round((equity - 1) * 100, 1),
        "win_rate_%": round((trades_arr > 0).mean() * 100, 1) if len(trades_arr) else None,
        "profit_factor": round(trades_arr[trades_arr > 0].sum() / abs(trades_arr[trades_arr < 0].sum()), 2)
        if len(trades_arr) and (trades_arr < 0).any() else None,
        "n_trend_campaigns_opened": n_trend_campaigns_opened,
        "n_range_fresh_entries": n_range_fresh_entries,
        "final_equity": equity,
    }

    if record_state:
        result["live_state"] = _build_live_state(
            feat, i=end - 1, tranches=tranches,
            range_reverses=range_reverses, campaign=campaign, trend_reverse=trend_reverse,
        )
    return result


def _build_live_state(feat, i, tranches, range_reverses, campaign, trend_reverse) -> dict:
    """État DESCRIPTIF du protocole à la dernière bougie `i` de l'historique
    fourni -- ne devine RIEN au-delà de cet historique. `range_active` et
    `trend_active` sont rapportés INDÉPENDAMMENT (peuvent être vrais tous les
    deux à la fois, cf. correction de l'exclusivité mutuelle en tête de
    fichier) plutôt qu'un `active_system` exclusif unique. `decide_now`
    (cf. ci-dessous) est responsable de l'éventuelle évaluation "bougie
    fantôme" (U4) quand un système est FLAT ici : elle rappelle
    `run_unified` sur un historique étendu d'UNE bougie plutôt que de
    dupliquer la logique de gate dans cette fonction."""
    return {
        "last_date": str(feat["date"][i]),
        "last_close": float(feat["close"][i]),
        "regime_h4": str(feat["regime"][i]),
        "gate_score_weekly": float(feat["gate_score"][i]),
        "gate_regime_weekly": str(feat["gate_regime"][i]),
        "range_active": bool(tranches or range_reverses),
        "trend_active": bool(campaign is not None or trend_reverse is not None),
        "range_tranches": [dict(tr) for tr in tranches],
        "range_reverses": [dict(rp) for rp in range_reverses],
        "trend_campaign": dict(campaign) if campaign is not None else None,
        "trend_reverse": dict(trend_reverse) if trend_reverse is not None else None,
    }


def _describe_range_hold(live: dict) -> dict:
    """RANGE déjà actif (`live["range_active"]`) -- décrit l'état réel
    (tranches et/ou "+Reverse" range), pas une évaluation "bougie fantôme"."""
    trs = live["range_tranches"]
    revs = live["range_reverses"]
    stops = [tr["stop"] for tr in trs] + [rp["stop"] for rp in revs]
    entry_price = trs[0]["entry"] if trs else revs[0]["entry"]
    targets = {}
    if trs:
        targets["tranches"] = [
            {"entry": tr["entry"], "stop": tr["stop"], "val_px": tr["val_px"],
             "conf_px": tr["conf_px"], "lim_px": tr["lim_px"],
             "val_done": tr["val_done"], "conf_done": tr["conf_done"]}
            for tr in trs
        ]
    if revs:
        targets["reverses"] = [{"entry": rp["entry"], "stop": rp["stop"], "target": rp["target"]} for rp in revs]
    reason = f"{len(trs)} tranche(s)"
    if revs:
        reason += f" + {len(revs)} jambe(s) '+Reverse'"
    reason += (f" range déjà ouverte(s) au {live['last_date']} -- laisser le moteur gérer "
               "Validation/Confirmation/Limite/Invalidation.")
    return {"action": "HOLD", "entry_price": entry_price, "stop_price": min(stops),
            "targets": targets, "reason": reason}


def _describe_trend_hold(live: dict) -> dict:
    """TENDANCE déjà actif (`live["trend_active"]`) -- décrit l'état réel
    (campagne et/ou "+Reverse" tendance), pas une évaluation "bougie fantôme"."""
    camp = live["trend_campaign"]
    if camp is not None:
        return {"action": "HOLD", "entry_price": camp["entry"], "stop_price": camp["stop"],
                "targets": {"stage": camp["stage"]},
                "reason": f"Campagne tendance en cours (étape {camp['stage']}) au {live['last_date']}."}
    rev = live["trend_reverse"]
    return {"action": "HOLD", "entry_price": rev["entry"], "stop_price": rev["stop"],
            "targets": {"target": rev["target"]},
            "reason": f"Jambe '+Reverse' tendance (short) en cours au {live['last_date']}."}


def _describe_range_open(live2: dict, last_date: str) -> dict:
    """RANGE FLAT sur l'historique réel -- évalue la bougie fantôme (U4)
    pour un éventuel signal d'ouverture."""
    trs = live2["range_tranches"]
    if trs:
        tr = trs[0]
        return {
            "action": "OPEN_LONG", "entry_price": tr["entry"], "stop_price": tr["stop"],
            "targets": {"val_px": tr["val_px"], "conf_px": tr["conf_px"], "lim_px": tr["lim_px"]},
            "reason": (
                f"Signal range (score>=2 + gate Hebdomadaire) présent sur la dernière bougie H4 "
                f"close ({last_date}) -- ouverture d'une tranche à l'open de la prochaine bougie. "
                "entry_price approximé par la dernière clôture connue (U4), pas un prix garanti."
            ),
        }
    return {"action": "NO_POSITION", "entry_price": None, "stop_price": None, "targets": None,
            "reason": f"Aucune tranche range ouverte et aucun signal range au {last_date}."}


def _describe_trend_open(live2: dict, last_date: str) -> dict:
    """TENDANCE FLAT sur l'historique réel -- évalue la bougie fantôme (U4)
    pour un éventuel signal d'ouverture (`accumulation_active`)."""
    camp = live2["trend_campaign"]
    if camp is not None:
        return {
            "action": "OPEN_LONG", "entry_price": camp["entry"], "stop_price": camp["stop"],
            "targets": {"stage": camp["stage"]},
            "reason": (
                f"accumulation_active vrai sur la dernière bougie H4 close ({last_date}) -- "
                "ouverture d'une campagne tendance à l'open de la prochaine bougie. "
                "entry_price approximé par la dernière clôture connue (U4), pas un prix garanti."
            ),
        }
    return {"action": "NO_POSITION", "entry_price": None, "stop_price": None, "targets": None,
            "reason": f"Aucune campagne tendance ouverte et accumulation_active faux au {last_date}."}


def _position_risk_pct(pos: dict) -> float:
    """Risque nominal RÉEL d'une position long ouverte SI son stop ACTUEL
    est touché maintenant, avec la taille RESTANTE actuelle -- MÊME formule
    R1 que `risk_aggregation_triple_system.py::_long_risk` (pas réimportée
    ici pour éviter une dépendance circulaire, ce module étant lui-même
    importé par ce fichier -- formule à 2 lignes, dupliquée à l'identique,
    pas réinventée). `pos` : dict avec au moins `entry`/`stop`/`remaining`."""
    if pos is None:
        return 0.0
    remaining = pos.get("remaining", 0.0)
    entry = pos.get("entry", 0.0)
    stop = pos.get("stop", 0.0)
    if remaining <= 0 or entry <= 0:
        return 0.0
    return remaining * max(0.0, (entry - stop) / entry) * 100


def _aggregate_risk_warning(live: dict) -> dict:
    """AJOUTÉ ce cycle (mobilisation multi-agents, bilan directeur "regard
    neuf") : `decide_now()` est l'interface opérationnelle réelle de la
    Phase 3, mais ne signalait jusqu'ici AUCUNE information sur le risque
    agrégé -- alors que ce projet a lui-même quantifié (`risk_aggregation_
    triple_system.py`, backlog item 8 de PLAN.md) un risque nominal agrégé
    pouvant atteindre 17,00% quand RANGE+TENDANCE+diversification sont
    ouverts simultanément, très au-dessus du plafond global 5% documenté
    (`RULES_EXTRACTION.md` §5). Ceci est un WARNING INFORMATIF -- un pur
    report d'un fait déjà mesuré par le projet -- PAS un plafond normatif
    inventé : `decide_now()` ne bloque ni ne modifie AUCUNE décision, cf.
    principe déjà établi (choix U5) que le corpus ne spécifie aucun plafond
    pour cette combinaison précise de systèmes.

    Chiffre seulement le risque RANGE (tranches + jambes "+Reverse" range),
    dont la formule (R1) est simple et déjà éprouvée -- le risque d'une
    campagne TENDANCE en cours n'est PAS inclus ici (calcul non trivial sur
    une campagne à plusieurs jambes déjà en progression ; la quantification
    complète existe dans `risk_aggregation_triple_system.py`, pas reproduite
    à l'identique ici pour ne pas dupliquer un calcul plus complexe sans le
    même niveau de test). Si une campagne TENDANCE est ACTIVE en plus des
    tranches RANGE, le risque réel total est PLUS ÉLEVÉ que le chiffre
    rapporté ici -- signalé explicitement via `trend_also_active`, jamais
    caché."""
    range_pct = sum(_position_risk_pct(tr) for tr in live["range_tranches"])
    range_pct += sum(_position_risk_pct(rp) for rp in live["range_reverses"])
    return {
        "range_nominal_risk_pct": round(range_pct, 2),
        "exceeds_5pct_global_cap": range_pct > 5.0,
        "trend_also_active": bool(live["trend_active"]),
        "note": (
            "range_nominal_risk_pct = risque RANGE réellement engagé (tranches + reverses "
            "ouverts, formule R1). N'inclut PAS le risque d'une campagne TENDANCE en cours "
            "(cf. trend_also_active) -- si vrai, le risque réel total est plus élevé. "
            "Plafond global RULES_EXTRACTION.md §5 = 5%. Quantification complète (jusqu'à "
            "17,00% mesuré historiquement RANGE+TENDANCE+diversification) : "
            "risk_aggregation_triple_system.py, PLAN.md backlog item 8. "
            "Ceci est un avertissement informatif, pas un plafond appliqué -- aucune décision "
            "n'est bloquée par ce champ."
        ),
    }


def decide_now(h1_recent: pd.DataFrame, profile_name: str, capital_eur: float = None) -> dict:
    """LA fonction "décision live" (PLAN.md, décision d'architecture #4).
    Prend l'historique H1 le plus RÉCENT d'un actif (colonnes date/open/
    high/low/close/volume -- la colonne `volume` est requise, cf. U1) et
    retourne l'état/la décision actuelle, sans jamais rejouer un backtest
    agrégé complet côté appelant.

    RÉVISÉ après correction de l'exclusivité mutuelle (cf. "CORRECTION" en
    tête de fichier) : RANGE et TENDANCE sont rapportés INDÉPENDAMMENT sous
    deux clés séparées (`range`, `trend`) -- lire les DEUX, pas un seul
    "système gagnant". Les deux peuvent être simultanément "HOLD" (positions
    déjà ouvertes sur les deux systèmes) ou "OPEN_LONG" (signaux présents
    sur les deux à la fois) ; ce n'est plus arbitré, cf. U5 pour la limite
    documentée sur le risque agrégé qui en résulte.

    COMBIEN D'HISTORIQUE FOURNIR : `h1_recent` est resamplé en interne en H4
    (exécution) et Hebdomadaire (gate RANGE, "UT+2 strict"). Une bougie H4
    ne devient exploitable qu'après `WARMUP = EMA_SLOW + 20` bougies H4
    (`backtest_phase2_v7.EMA_SLOW=55` -> WARMUP=75 bougies H4 = 300 heures
    = 12,5 jours) -- SEUIL MINIMUM DUR appliqué ci-dessous
    (`INSUFFICIENT_DATA` sinon). Le gate Hebdomadaire (contexte RANGE) a lui
    aussi besoin de EMA_SLOW=55 bougies Hebdomadaires (~13 mois) pour
    converger -- sous ce seuil, `weekly_gate_reliable=False` est renvoyé
    (déjà documenté comme limite structurelle ailleurs dans ce projet, cf.
    `CONFIGURATION_RECOMMANDEE.md` section 4, OOS XRP) : la décision est
    quand même rendue (le score neutre "+inf"/"RANGE_NEUTRE" ne bloque
    jamais silencieusement, cf. `_prepare_features`), mais signalée comme
    potentiellement peu fiable plutôt que cachée.

    SÉMANTIQUE DU DICT RETOURNÉ :
      - Cas `INSUFFICIENT_DATA` (historique H4 trop court) : `action` vaut
        `"INSUFFICIENT_DATA"`, `range`/`trend`/`regime` valent `None`.
      - Cas normal : pas de clé `action` au niveau racine (il n'y a plus UN
        système gagnant à annoncer) -- `range` et `trend` sont chacun un
        dict `{"action", "entry_price", "stop_price", "targets", "reason"}`
        où `action` vaut "HOLD" (position déjà ouverte sur CE système --
        `entry_price` réel, déjà exécuté), "OPEN_LONG" (aucune position sur
        CE système, mais un signal d'entrée est présent sur la DERNIÈRE
        bougie H4 entièrement close -- exécution réelle à l'ouverture de la
        PROCHAINE bougie H4, `entry_price` APPROXIMÉ par la dernière clôture
        connue, cf. U4 -- PAS un prix garanti), ou "NO_POSITION" (ni
        position ni signal sur ce système).
      - `targets` (RANGE) : {"tranches": [...]} et/ou {"reverses": [...]}
        si HOLD, {"val_px", "conf_px", "lim_px"} si OPEN_LONG.
      - `targets` (TENDANCE) : {"stage": ...} (campagne) ou {"target": ...}
        ("+Reverse" tendance) si HOLD, {"stage": ...} si OPEN_LONG -- la
        table de tendance n'a pas de cible de PRIX fixe mais des ÉVÉNEMENTS
        de structure (Breakout/Divergence/Pull-Back/Excès final, cf.
        `trend_table.py` tête de fichier).
      - `regime` : régime H4 (RANGE_NEUTRE/RANGE_TENDANCIEL/TENDANCE/EXCES)
        de la dernière bougie close (`regime_classifier.add_regime`, réutilisé
        tel quel) -- commun aux deux systèmes (même bougie).
      - `weekly_gate_reliable` : bool, cf. ci-dessus.
      - `n_h4_bars`, `n_weekly_bars` : tailles des historiques resamplés,
        pour que l'appelant puisse juger lui-même de la marge par rapport
        aux seuils ci-dessus.
      - `aggregate_risk_warning` (ajouté ce cycle, cf. `_aggregate_risk_warning`) :
        dict `{"range_nominal_risk_pct", "exceeds_5pct_global_cap",
        "trend_also_active", "note"}` -- avertissement INFORMATIF sur le
        risque RANGE réellement engagé (tranches+reverses ouverts), jamais
        un plafond appliqué (aucune décision n'est bloquée par ce champ).
        Absent (`None`) dans le cas `INSUFFICIENT_DATA` ci-dessous.
    """
    if "volume" not in h1_recent.columns:
        raise ValueError("h1_recent doit contenir une colonne 'volume' (cf. U1 -- "
                          "requise par le déclencheur Breakout de la table de tendance).")

    h4 = resample_h4_with_volume(h1_recent)
    d1 = resample(h1_recent[["date", "open", "high", "low", "close"]], "1D")
    weekly = resample(h1_recent[["date", "open", "high", "low", "close"]], "W")
    n_h4 = len(h4)
    weekly_reliable = len(weekly) >= EMA_SLOW + 20

    if n_h4 <= WARMUP + 1:
        return {
            "action": "INSUFFICIENT_DATA", "range": None, "trend": None, "regime": None,
            "aggregate_risk_warning": None,
            "reason": (
                f"{n_h4} bougies H4 disponibles, {WARMUP + 1} minimum requises "
                f"(WARMUP={WARMUP}=EMA_SLOW+20 bougies H4) avant toute tentative "
                "d'ouverture -- fournir davantage d'historique H1."
            ),
            "weekly_gate_reliable": weekly_reliable, "n_h4_bars": n_h4, "n_weekly_bars": len(weekly),
        }

    result = run_unified(h4, d1, weekly, profile_name, capital_eur=capital_eur, record_state=True)
    live = result["live_state"]
    base = {"weekly_gate_reliable": weekly_reliable, "n_h4_bars": n_h4, "n_weekly_bars": len(weekly)}

    range_desc = _describe_range_hold(live) if live["range_active"] else None
    trend_desc = _describe_trend_hold(live) if live["trend_active"] else None
    risk_warning = _aggregate_risk_warning(live)

    if range_desc is None or trend_desc is None:
        # Au moins un système est FLAT sur l'historique réel -- bougie
        # fantôme (U4) : rappelle run_unified sur l'historique étendu d'UNE
        # bougie synthétique (open=high=low=close=dernière clôture connue,
        # volume=0) pour évaluer si un signal d'entrée est présent, SANS
        # dupliquer la logique de gate. Évaluée pour les DEUX systèmes FLAT
        # indépendamment -- l'un peut ouvrir pendant que l'autre reste HOLD.
        last = h4.iloc[-1]
        phantom = pd.DataFrame([{
            "date": last["date"] + pd.Timedelta(hours=4),
            "open": last["close"], "high": last["close"], "low": last["close"], "close": last["close"],
            "volume": 0.0,
        }])
        h4_ext = pd.concat([h4, phantom], ignore_index=True)
        result2 = run_unified(h4_ext, d1, weekly, profile_name, capital_eur=capital_eur, record_state=True)
        live2 = result2["live_state"]
        if range_desc is None:
            range_desc = _describe_range_open(live2, live["last_date"])
        if trend_desc is None:
            trend_desc = _describe_trend_open(live2, live["last_date"])

    return {"range": range_desc, "trend": trend_desc, "regime": live["regime_h4"],
            "aggregate_risk_warning": risk_warning, **base}


def main():
    """Backtest comparatif honnête (décision d'architecture #5, PLAN.md) :
    protocole unifié vs `backtest_phase2_faithful.py` (moteur RANGE seul,
    MÊMES règles littérales depuis la CONSOLIDATION) seul, BTC/ETH/BNB/SOL
    x 4 profils, MÊME historique H4/D1/Hebdomadaire pour les deux -- ne
    présuppose PAS que l'unification améliore le résultat, cf. lecture des
    deux colonnes ci-dessous plutôt qu'une seule conclusion forcée.

    Rapporte AUSSI, honnêtement, si des campagnes tendance se déclenchent
    RÉELLEMENT sur ce jeu de données (`n_trend_campaigns_opened`) -- rappel
    du constat déjà documenté dans PLAN.md/COUVERTURE_ENSEIGNEMENTS.md :
    `trend_table.py` seul n'a JAMAIS dépassé l'étape Accumulation dans son
    propre backtest (100% des campagnes se referment en Accumulation). Si
    ce chiffre est encore 0 ici, le protocole unifié ne peut STRUCTURELLEMENT
    rien changer au résultat chiffré par rapport à `recommended.py` seul --
    dit tel quel, pas maquillé en "aucune différence trouvée par hasard"."""
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        vol_h1 = load_volume(symbol)
        h1_full = h1.merge(vol_h1, on="date", how="inner")
        h4 = resample_h4_with_volume(h1_full)
        d1 = resample(h1_full[["date", "open", "high", "low", "close"]], "1D")
        weekly = resample(h1_full[["date", "open", "high", "low", "close"]], "W")
        h4_no_vol = h4[["date", "open", "high", "low", "close"]]
        for profile in PROFILE_NAMES:
            res_unified = run_unified(h4.copy(), d1.copy(), weekly.copy(), profile)
            # Référence : backtest_phase2_faithful.py (RANGE seul, MÊMES 3
            # règles littérales que le côté RANGE de ce routeur depuis la
            # CONSOLIDATION -- comparaison apples-to-apples, pas contre
            # recommended.py qui n'a plus les mêmes règles par défaut).
            res_faithful = run_faithful(h4_no_vol.copy(), d1.copy(), weekly.copy(), profile)
            rows.append({
                "symbol": symbol, "profile": profile,
                "unified_n_trades": res_unified["n_trades"],
                "unified_max_dd_%": res_unified["max_dd_%"],
                "unified_total_return_%": res_unified["total_return_%"],
                "unified_win_rate_%": res_unified["win_rate_%"],
                "unified_profit_factor": res_unified["profit_factor"],
                "unified_n_trend_campaigns_opened": res_unified["n_trend_campaigns_opened"],
                "faithful_n_trades": res_faithful["n_trades"],
                "faithful_max_dd_%": res_faithful["max_dd_%"],
                "faithful_total_return_%": res_faithful["total_return_%"],
                "faithful_win_rate_%": res_faithful["win_rate_%"],
                "faithful_profit_factor": res_faithful["profit_factor"],
            })
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    print(result.to_string(index=False))
    result.to_csv("backtest_phase2_unified_results.csv", index=False)

    total_campaigns = result["unified_n_trend_campaigns_opened"].sum()
    print(f"\nCampagnes tendance ouvertes (routeur unifié, toutes combinaisons) : {total_campaigns}")
    identical = (
        (result["unified_n_trades"] == result["faithful_n_trades"]).all()
        and (result["unified_total_return_%"] == result["faithful_total_return_%"]).all()
    )
    print(f"Résultat identique à faithful.py seul sur toutes les combinaisons : {identical}")
    if total_campaigns == 0:
        print("Aucune campagne tendance déclenchée sur ce jeu de données -- cohérent avec le "
              "constat déjà documenté (trend_table.py seul n'a jamais dépassé Accumulation) : "
              "le protocole unifié ne peut structurellement pas différer de recommended.py ici.")


if __name__ == "__main__":
    main()
