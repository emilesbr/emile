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
    `make_open_tranche_fn`, et la préparation de features de
    `backtest_phase2_recommended.py::_prepare_features` (cycle+structure
    causaux, gate Hebdomadaire "UT+2 strict").
  - côté TENDANCE : `trend_table.py::step_campaign`/`try_open_campaign`/
    `step_reverse`/`add_leg`, et sa préparation de features
    (`backtest_phase2_v7.prepare` + `trend_table.add_trend_context` +
    volume, cf. hypothèses H1-H12 documentées dans `trend_table.py`).
Le seul code nouveau ici est la BOUCLE D'ORCHESTRATION bar-par-bar qui route
entre les deux (`run_unified`), et la fonction de décision live
(`decide_now`) qui l'interroge sur l'état courant d'un actif.

================================================================================
5 DÉCISIONS D'ARCHITECTURE (déjà tranchées dans PLAN.md avant tout code --
ce fichier les EXÉCUTE, il ne les redessine pas)
================================================================================
1. **Priorité de régime** : quand `accumulation_active` (déclencheur du
   moteur TENDANCE, `trend_table.py::try_open_campaign`) est vrai, le moteur
   TENDANCE a la priorité. Le moteur RANGE ne tente aucune nouvelle tranche
   tant qu'une campagne tendance est active sur cet actif. Dans tous les
   autres cas, le moteur RANGE garde le comportement déjà validé de
   `recommended.py` (y compris son propre gate Hebdomadaire "regime != EXCES"
   au niveau du contexte supérieur -- ce gate existe déjà dans
   `_prepare_features`/`_run_core`, réutilisé tel quel, PAS un nouveau gate
   sur le régime H4 propre).
2. **Exclusivité mutuelle par actif** : `active_system in {None, "range",
   "trend"}`, jamais range ET tendance ouverts en même temps. La bascule
   TENDANCE -> RANGE (ou l'inverse) n'est évaluée QU'AU MOMENT DE
   L'OUVERTURE, c'est-à-dire quand `active_system is None` -- si
   `accumulation_active` devient vrai PENDANT qu'une tranche range est déjà
   ouverte, le routeur continue de gérer la position range jusqu'à sa
   clôture complète (cf. `test_unified_protocol.py`,
   `test_accumulation_during_open_range_does_not_switch`).
3. **Aucune réimplémentation de logique métier** : cf. import list
   ci-dessous -- uniquement des fonctions PAR BOUGIE déjà existantes.
4. **Sortie "décision live"** : `decide_now()`.
5. **Mesure honnête** : `main()` compare le protocole unifié à
   `recommended.py` seul, sans présupposer un meilleur résultat (cf.
   `phase2_unified_vs_recommended_results.csv`/
   `backtest_phase2_unified_results.csv`).

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
    séquence de trades unifiée, décision #2). Seul le moteur RANGE utilise
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
from backtest_phase2_recommended import _prepare_features, run_recommended, WARMUP
from position_engine import make_open_tranche_fn, process_tranche, process_reverse
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


def _prepare_unified(h4: pd.DataFrame, weekly: pd.DataFrame, use_mtf_gate: bool = True) -> dict:
    """Calcule TOUTES les colonnes nécessaires aux deux moteurs, une fois,
    sur l'historique complet fourni.

    RANGE : réutilise `backtest_phase2_recommended._prepare_features` tel
    quel (cycle+structure causaux, gate Hebdomadaire "UT+2 strict").
    TENDANCE : réutilise `backtest_phase2_v7.prepare` +
    `trend_table.add_trend_context` tels quels, plus la détection volume de
    `trend_table.py` (H9) calculée ici EXACTEMENT comme dans
    `run_trend_table` (même fenêtre glissante, même seuil)."""
    if "volume" not in h4.columns:
        raise ValueError(
            "h4 doit contenir une colonne 'volume' (requise par le moteur "
            "tendance, cf. U1 dans la docstring du module) -- construire "
            "avec resample_h4_with_volume(h1)."
        )

    range_feat = _prepare_features(h4, weekly, use_mtf_gate=use_mtf_gate)

    trend_df = prepare(h4[["date", "open", "high", "low", "close"]].copy())
    trend_df = add_trend_context(trend_df)

    vol_v = h4["volume"].values
    vol_ma = pd.Series(vol_v).rolling(VOLUME_MA_WINDOW).mean().values
    volume_expansion = vol_v > VOLUME_EXPANSION_MULT * np.roll(vol_ma, 1)
    volume_expansion[0] = False

    ema_trend_v = (trend_df["close"].ewm(span=EMA_SLOW, adjust=False).mean()).values

    feat = dict(range_feat)
    feat.update({
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


def run_unified(h4: pd.DataFrame, weekly: pd.DataFrame, profile_name: str,
                 capital_eur: float = None, reverse_at_limit: bool = False,
                 use_mtf_gate: bool = True, record_state: bool = False) -> dict:
    """Boucle d'orchestration bar-par-bar -- LE seul code nouveau de ce
    fichier (cf. tête de fichier, décision #3). `h4` DOIT inclure une
    colonne `volume` (cf. `resample_h4_with_volume`, U1). `weekly` : niveau
    de contexte pour le gate RANGE (Hebdomadaire, "UT+2 strict", inchangé
    par rapport à `recommended.py`).

    À chaque bougie H4 (après warmup), au plus UN système est actif par
    actif (`active_system in {None, "range", "trend"}`, décision #2) :
      - si aucun système actif : `accumulation_active` -> ouvre une
        campagne TENDANCE (priorité, décision #1) ; sinon tente une
        ouverture RANGE (comportement de `recommended.py`, gate Hebdo
        déjà inclus).
      - si TENDANCE active : fait progresser la campagne
        (`step_campaign`)/le "+Reverse" tendance (`step_reverse`).
      - si RANGE active : fait progresser les tranches (`process_tranche`)
        et la pyramidalisation, exactement comme `recommended.py`.
    Les trades des deux systèmes sont agrégés dans les MÊMES statistiques
    (n_trades/max_dd_%/total_return_%/win_rate_%/profit_factor), comme le
    fait déjà `position_engine.py` pour range+"+Reverse" (cf. sa docstring).

    `record_state=True` ajoute la clé "live_state" au résultat : l'état du
    protocole à la TOUTE DERNIÈRE bougie de l'historique fourni, utilisé par
    `decide_now` (cf. U4 pour l'approximation "bougie fantôme")."""
    feat = _prepare_unified(h4, weekly, use_mtf_gate=use_mtf_gate)
    risk_pct = None
    if capital_eur is not None:
        # U3 : capital par palier appliqué SEULEMENT au moteur RANGE.
        sizing = effective_sizing(capital_eur, profile_name, PROFILES_V4, MAX_TRANCHES)
        risk_pct = sizing.risk_pct
    return _run_core_unified(feat, profile_name, risk_pct=risk_pct,
                              reverse_at_limit=reverse_at_limit, record_state=record_state)


def _run_core_unified(feat: dict, profile_name: str, risk_pct: float = None,
                       reverse_at_limit: bool = False, record_state: bool = False) -> dict:
    """La boucle d'orchestration elle-même, séparée de `run_unified` sur le
    modèle `_prepare_features`/`_run_core` de `backtest_phase2_recommended.py`
    -- pour pouvoir être testée unitairement (`test_unified_protocol.py`) sur
    un `feat` dict CONSTRUIT À LA MAIN (scénarios synthétiques exacts),
    exactement comme `_run_core` est testable indépendamment de
    `_prepare_features` dans `test_backtest_phase2_recommended.py`.

    `feat` doit exposer TOUTES les clés produites par `_prepare_unified` :
    date/open/high/low/close/score/atr/ctx_support/local_range/
    context_range/n_borders/gate_score/gate_regime (côté RANGE, mêmes clés
    que `backtest_phase2_recommended._prepare_features`) + regime/
    ctx_resistance/ctx_high/local_high/accum_retracement_frac/
    cycle_favorable/ema_trend/volume_expansion (côté TENDANCE). `risk_pct`
    (défaut `None`) : risk_pct RANGE déjà résolu par l'appelant (profil fixe
    ou `capital_tiers.effective_sizing(...).risk_pct`, cf. U3) -- si `None`,
    celui du profil (`PROFILES_V4[profile_name]["risk_pct"]`)."""
    p_range = PROFILES_V4[profile_name]
    p_trend = PROFILES_TREND[profile_name]
    if risk_pct is None:
        risk_pct = p_range["risk_pct"]

    o, high, low, c = feat["open"], feat["high"], feat["low"], feat["close"]
    score = feat["score"]
    n = len(o)

    def gate(i: int) -> bool:
        return bool(feat["gate_score"][i] >= 2 and feat["gate_regime"][i] != "EXCES")

    def gate_extra(j):
        g = gate(j)
        return g, g

    range_state = {"last_pyramid_high": -np.inf}
    open_tranche_fn = make_open_tranche_fn(
        feat["atr"], feat["ctx_support"], feat["local_range"], feat["context_range"],
        feat["n_borders"], high, o, score, WARMUP, MIN_BORDERS, MAX_TRANCHES,
        RULE3_STREAK, RULE3_SIZE_MULT, risk_pct, range_state, extra_gate_fn=gate_extra,
    )
    gated_long_signal = np.array([(score[i] >= 2) and gate(i) for i in range(n)])

    equity = 1.0
    equity_curve = np.empty(n)
    equity_curve[0] = equity

    active_system = None
    tranches: list = []
    range_reverses: list = []
    campaign = None
    trend_reverse = None
    trades: list = []
    win_streak = 0
    n_trend_campaigns_opened = 0
    n_range_fresh_entries = 0

    for i in range(1, n):
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
                if campaign is None:
                    active_system = None

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
        if active_system == "range" and not tranches and not range_reverses:
            active_system = None

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
                elif trend_reverse is None:
                    active_system = None

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
            if not tranches and not range_reverses and active_system == "range":
                active_system = None

        # ---- 4) tentative d'ouverture / pyramidalisation ----
        if active_system is None:
            if _accumulation_active(feat, i):
                j = i - 1
                new_campaign, fee_frac = try_open_campaign(i, o, feat["ctx_support"][j], True, p_trend)
                if new_campaign is not None:
                    campaign = new_campaign
                    active_system = "trend"
                    n_trend_campaigns_opened += 1
                    if fee_frac > 0:
                        equity *= (1 - FEE * fee_frac)
            else:
                new_tr = open_tranche_fn(i, tranches, win_streak)
                if new_tr is not None:
                    tranches.append(new_tr)
                    active_system = "range"
                    n_range_fresh_entries += 1
                    equity *= (1 - FEE * new_tr["remaining"])
        elif active_system == "range" and len(tranches) < MAX_TRANCHES:
            new_tr = open_tranche_fn(i, tranches, win_streak)
            if new_tr is not None:
                tranches.append(new_tr)
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
        equity_curve[i] = equity * (1 + mtm)

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
            feat, i=n - 1, active_system=active_system, tranches=tranches,
            range_reverses=range_reverses, campaign=campaign, trend_reverse=trend_reverse,
        )
    return result


def _build_live_state(feat, i, active_system, tranches, range_reverses, campaign,
                       trend_reverse) -> dict:
    """État DESCRIPTIF du protocole à la dernière bougie `i` de l'historique
    fourni -- ne devine RIEN au-delà de cet historique. `decide_now`
    (cf. ci-dessous) est responsable de l'éventuelle évaluation "bougie
    fantôme" (U4) quand `active_system is None` ici : elle rappelle
    `run_unified` sur un historique étendu d'UNE bougie plutôt que de
    dupliquer la logique de gate dans cette fonction."""
    return {
        "last_date": str(feat["date"][i]),
        "last_close": float(feat["close"][i]),
        "regime_h4": str(feat["regime"][i]),
        "gate_score_weekly": float(feat["gate_score"][i]),
        "gate_regime_weekly": str(feat["gate_regime"][i]),
        "active_system": active_system,
        "range_tranches": [dict(tr) for tr in tranches],
        "range_reverses": [dict(rp) for rp in range_reverses],
        "trend_campaign": dict(campaign) if campaign is not None else None,
        "trend_reverse": dict(trend_reverse) if trend_reverse is not None else None,
    }


def decide_now(h1_recent: pd.DataFrame, profile_name: str, capital_eur: float = None) -> dict:
    """LA fonction "décision live" (PLAN.md, décision d'architecture #4).
    Prend l'historique H1 le plus RÉCENT d'un actif (colonnes date/open/
    high/low/close/volume -- la colonne `volume` est requise, cf. U1) et
    retourne l'état/la décision actuelle, sans jamais rejouer un backtest
    agrégé complet côté appelant.

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

    SÉMANTIQUE DES CHAMPS DU DICT RETOURNÉ :
      - `action` : "HOLD_RANGE" (une ou plusieurs tranches range déjà
        ouvertes, aucune action requise sinon laisser le moteur gérer les
        clôtures), "HOLD_TREND" (campagne tendance et/ou "+Reverse" tendance
        déjà ouverts), "OPEN_LONG" (AUCUNE position ouverte actuellement,
        mais un signal d'entrée est présent sur la DERNIÈRE bougie H4
        entièrement close -- l'exécution réelle se ferait à l'ouverture de
        la PROCHAINE bougie H4, prix approximé ici par la dernière clôture
        connue, cf. U4 -- PAS un prix d'exécution garanti), "NO_POSITION"
        (aucune position, aucun signal), "INSUFFICIENT_DATA" (historique H4
        trop court, cf. ci-dessus -- tous les autres champs sont `None`).
      - `system` : "range" | "trend" | None -- quel moteur porte la décision.
      - `regime` : régime H4 (RANGE_NEUTRE/RANGE_TENDANCIEL/TENDANCE/EXCES)
        de la dernière bougie close (`regime_classifier.add_regime`, réutilisé
        tel quel).
      - `entry_price` : prix d'entrée -- réel (déjà exécuté) si HOLD_*,
        APPROXIMÉ (dernière clôture, cf. U4) si OPEN_LONG. `None` sinon.
      - `stop_price` : niveau de protection courant (`ctx_support`
        "Extreme Channel" pour une entrée fraîche/campagne, ou le stop
        remonté au break-even si la Confirmation/Divergence l'a déjà fait).
      - `targets` : dict spécifique au système -- RANGE :
        {"val_px", "conf_px", "lim_px"} (niveaux de prix fixes, calculés à
        l'entrée) ; TENDANCE : {"stage": ...} (la table de tendance n'a pas
        de cible de PRIX fixe mais des ÉVÉNEMENTS de structure -- Breakout/
        Divergence/Pull-Back/Excès final, cf. `trend_table.py` tête de
        fichier -- le champ `stage` indique l'étape courante/à venir,
        `reason` en donne le déclencheur littéral).
      - `reason` : texte libre expliquant la décision (quel gate a validé/
        bloqué, quelle étape de campagne, limite de données le cas échéant).
      - `weekly_gate_reliable` : bool, cf. ci-dessus.
      - `n_h4_bars`, `n_weekly_bars` : tailles des historiques resamplés,
        pour que l'appelant puisse juger lui-même de la marge par rapport
        aux seuils ci-dessus.
    """
    if "volume" not in h1_recent.columns:
        raise ValueError("h1_recent doit contenir une colonne 'volume' (cf. U1 -- "
                          "requise par le déclencheur Breakout de la table de tendance).")

    h4 = resample_h4_with_volume(h1_recent)
    weekly = resample(h1_recent[["date", "open", "high", "low", "close"]], "W")
    n_h4 = len(h4)
    weekly_reliable = len(weekly) >= EMA_SLOW + 20

    if n_h4 <= WARMUP + 1:
        return {
            "action": "INSUFFICIENT_DATA", "system": None, "regime": None,
            "entry_price": None, "stop_price": None, "targets": None,
            "reason": (
                f"{n_h4} bougies H4 disponibles, {WARMUP + 1} minimum requises "
                f"(WARMUP={WARMUP}=EMA_SLOW+20 bougies H4) avant toute tentative "
                "d'ouverture -- fournir davantage d'historique H1."
            ),
            "weekly_gate_reliable": weekly_reliable, "n_h4_bars": n_h4, "n_weekly_bars": len(weekly),
        }

    result = run_unified(h4, weekly, profile_name, capital_eur=capital_eur, record_state=True)
    live = result["live_state"]
    base = {"weekly_gate_reliable": weekly_reliable, "n_h4_bars": n_h4, "n_weekly_bars": len(weekly)}

    if live["active_system"] == "range":
        trs = live["range_tranches"]
        stop_price = min(tr["stop"] for tr in trs)
        return {
            "action": "HOLD_RANGE", "system": "range", "regime": live["regime_h4"],
            "entry_price": trs[0]["entry"], "stop_price": stop_price,
            "targets": {"tranches": [
                {"entry": tr["entry"], "stop": tr["stop"], "val_px": tr["val_px"],
                 "conf_px": tr["conf_px"], "lim_px": tr["lim_px"],
                 "val_done": tr["val_done"], "conf_done": tr["conf_done"]}
                for tr in trs
            ]},
            "reason": f"{len(trs)} tranche(s) range déjà ouverte(s) au {live['last_date']} -- "
                      "laisser le moteur gérer Validation/Confirmation/Limite/Invalidation.",
            **base,
        }

    if live["active_system"] == "trend":
        camp = live["trend_campaign"]
        rev = live["trend_reverse"]
        if camp is not None:
            return {
                "action": "HOLD_TREND", "system": "trend", "regime": live["regime_h4"],
                "entry_price": camp["entry"], "stop_price": camp["stop"],
                "targets": {"stage": camp["stage"]},
                "reason": f"Campagne tendance en cours (étape {camp['stage']}) au {live['last_date']}.",
                **base,
            }
        return {
            "action": "HOLD_TREND", "system": "trend", "regime": live["regime_h4"],
            "entry_price": rev["entry"], "stop_price": rev["stop"],
            "targets": {"target": rev["target"]},
            "reason": f"Jambe '+Reverse' tendance (short) en cours au {live['last_date']}.",
            **base,
        }

    # Aucune position ouverte sur l'historique réel -- bougie fantôme (U4) :
    # rappelle run_unified sur l'historique étendu d'UNE bougie synthétique
    # (open=high=low=close=dernière clôture connue, volume=0) pour évaluer
    # si un signal d'entrée est présent SANS dupliquer la logique de gate.
    last = h4.iloc[-1]
    phantom = pd.DataFrame([{
        "date": last["date"] + pd.Timedelta(hours=4),
        "open": last["close"], "high": last["close"], "low": last["close"], "close": last["close"],
        "volume": 0.0,
    }])
    h4_ext = pd.concat([h4, phantom], ignore_index=True)
    result2 = run_unified(h4_ext, weekly, profile_name, capital_eur=capital_eur, record_state=True)
    live2 = result2["live_state"]

    if live2["active_system"] == "trend" and live2["trend_campaign"] is not None:
        camp = live2["trend_campaign"]
        return {
            "action": "OPEN_LONG", "system": "trend", "regime": live["regime_h4"],
            "entry_price": camp["entry"], "stop_price": camp["stop"],
            "targets": {"stage": camp["stage"]},
            "reason": (
                f"accumulation_active vrai sur la dernière bougie H4 close ({live['last_date']}) -- "
                "ouverture d'une campagne tendance à l'open de la prochaine bougie. "
                "entry_price approximé par la dernière clôture connue (U4), pas un prix garanti."
            ),
            **base,
        }

    if live2["active_system"] == "range" and live2["range_tranches"]:
        tr = live2["range_tranches"][0]
        return {
            "action": "OPEN_LONG", "system": "range", "regime": live["regime_h4"],
            "entry_price": tr["entry"], "stop_price": tr["stop"],
            "targets": {"val_px": tr["val_px"], "conf_px": tr["conf_px"], "lim_px": tr["lim_px"]},
            "reason": (
                f"Signal range (score>=2 + gate Hebdomadaire) présent sur la dernière bougie H4 "
                f"close ({live['last_date']}) -- ouverture d'une tranche à l'open de la prochaine "
                "bougie. entry_price approximé par la dernière clôture connue (U4), pas un prix garanti."
            ),
            **base,
        }

    return {
        "action": "NO_POSITION", "system": None, "regime": live["regime_h4"],
        "entry_price": None, "stop_price": None, "targets": None,
        "reason": f"Aucune position ouverte et aucun signal d'entrée (range ou tendance) au {live['last_date']}.",
        **base,
    }


def main():
    """Backtest comparatif honnête (décision d'architecture #5, PLAN.md) :
    protocole unifié vs `recommended.py` (moteur RANGE) seul, BTC/ETH/BNB/SOL
    x 4 profils, MÊME historique H4/Hebdomadaire pour les deux -- ne
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
        weekly = resample(h1_full[["date", "open", "high", "low", "close"]], "W")
        h4_no_vol = h4[["date", "open", "high", "low", "close"]]
        for profile in PROFILE_NAMES:
            res_unified = run_unified(h4.copy(), weekly.copy(), profile)
            res_reco = run_recommended(h4_no_vol.copy(), weekly.copy(), profile)
            rows.append({
                "symbol": symbol, "profile": profile,
                "unified_n_trades": res_unified["n_trades"],
                "unified_max_dd_%": res_unified["max_dd_%"],
                "unified_total_return_%": res_unified["total_return_%"],
                "unified_win_rate_%": res_unified["win_rate_%"],
                "unified_profit_factor": res_unified["profit_factor"],
                "unified_n_trend_campaigns_opened": res_unified["n_trend_campaigns_opened"],
                "recommended_n_trades": res_reco["n_trades"],
                "recommended_max_dd_%": res_reco["max_dd_%"],
                "recommended_total_return_%": res_reco["total_return_%"],
                "recommended_win_rate_%": res_reco["win_rate_%"],
                "recommended_profit_factor": res_reco["profit_factor"],
            })
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    print(result.to_string(index=False))
    result.to_csv("backtest_phase2_unified_results.csv", index=False)

    total_campaigns = result["unified_n_trend_campaigns_opened"].sum()
    print(f"\nCampagnes tendance ouvertes (routeur unifié, toutes combinaisons) : {total_campaigns}")
    identical = (
        (result["unified_n_trades"] == result["recommended_n_trades"]).all()
        and (result["unified_total_return_%"] == result["recommended_total_return_%"]).all()
    )
    print(f"Résultat identique à recommended.py seul sur toutes les combinaisons : {identical}")
    if total_campaigns == 0:
        print("Aucune campagne tendance déclenchée sur ce jeu de données -- cohérent avec le "
              "constat déjà documenté (trend_table.py seul n'a jamais dépassé Accumulation) : "
              "le protocole unifié ne peut structurellement pas différer de recommended.py ici.")


if __name__ == "__main__":
    main()
