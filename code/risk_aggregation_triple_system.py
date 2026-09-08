"""
Risque nominal AGRÉGÉ réellement engagé quand LES TROIS moteurs tournent
SIMULTANÉMENT sur le MÊME actif/historique :
  - RANGE      (unified_protocol.py, volet RANGE = backtest_phase2_faithful.py)
  - TENDANCE   (unified_protocol.py, volet TENDANCE = trend_table.py)
  - DIVERSIFICATION 1%+1% (diversification.py : Pattern A "breakout/pullback"
    proxy_v2 + Pattern B "cluster technique")

PLAN.md, "Plan d'autonomie 8h", point 8 (backlog item 8) :
    "aucun plafond de risque agrégé entre systèmes qui peuvent désormais
    tourner simultanément [...] un cumul RANGE+TENDANCE+diversification 1%+1%
    jamais chiffré nulle part si les trois tournent en même temps sur le même
    actif [...] jugé trop risqué à livrer sans tests approfondis dans le
    temps imparti par l'agent qui a tenté les autres combinaisons."

Ce script chiffre ce cumul, walk-forward annuel BTC/ETH/BNB/SOL x 4 profils
(même modèle que walkforward_unified.py), et rapporte le maximum réellement
observé -- sans inventer de plafond ni "corriger" quoi que ce soit : le
corpus ne dit pas comment plafonner CETTE combinaison précise à 3 systèmes
(cf. citations vérifiées ci-dessous, et discussion U5 dans
`unified_protocol.py`).

================================================================================
CITATIONS EXACTES VÉRIFIÉES DANS LE CORPUS (pas supposées, cf. tâche demandée)
================================================================================
- RULES_EXTRACTION.md, section "5. Gestion du risque globale (règles dures)" :
      "Perte spéculative jamais >5% du capital, quel que soit le profil"
  Déjà repris ailleurs dans ce projet (PAS une valeur inventée ici) :
  `capital_tiers.HARD_MAX_RISK_PCT = 0.05` et `trend_table.MAX_CAMPAIGN_RISK_PCT
  = 0.05` (commentaire "H3, RULES_EXTRACTION §5" en tête de trend_table.py).
  C'est LE plafond global du corpus, quel que soit le système.
- TRADING_LESSONS_CLUSTERS_PRIX.md, source #16, section "Diversification
  statistique du risque -- nouvelle règle (1% + 1%)" :
      "Règle d'or : jamais >2% de risque maximal par zone de prix"
  Déjà repris dans `diversification.MAX_RISK_PER_ZONE_PCT = 0.02`, mais
  SPÉCIFIQUE à la paire Pattern A/Pattern B de CE module -- le corpus ne dit
  PAS que ce plafond de 2% s'applique aussi à la combinaison à 3 systèmes
  mesurée ici (RANGE-table + TENDANCE-table + diversification). Rapporté
  pour référence, PAS présenté comme LE plafond applicable à cette
  combinaison précise (extrapolation qui serait non mesurée, cf. `unified_
  protocol.py` U5 pour la même discipline appliquée à RANGE+TENDANCE seuls).

Ce script ne tranche PAS lequel des deux plafonds (ou aucun) devrait
s'appliquer à la combinaison à 3 systèmes -- il mesure et compare aux deux,
et documente le résultat comme une limite ouverte si l'un ou l'autre est
dépassé (cf. section finale de PLAN.md/rapport associé), pas une résolution
inventée silencieusement.

================================================================================
CE QUE CE SCRIPT NE FAIT PAS / NE RÉIMPLÉMENTE PAS
================================================================================
Aucune logique de position/sizing/stop/cible n'est réinventée ici. Réutilisés
TELS QUELS (import, jamais copié/modifié) :
  - position_engine.py :: process_tranche, process_reverse, make_open_tranche_fn
  - trend_table.py     :: step_campaign, try_open_campaign, step_reverse
  - unified_protocol.py:: _prepare_unified, _accumulation_active, _campaign_ev,
                          resample_h4_with_volume (fonctions PAR BOUGIE, déjà
                          testées par test_unified_protocol.py, 6/6)
  - diversification.py :: prepare_diversified, size_fraction, RISK_PCT_PATTERN_A/B

SEULE EXCEPTION documentée : `diversification.py::run_diversified` construit
son `open_fn` (Pattern A / Pattern B) comme une fermeture INTERNE (`make_open_fn`,
~25 lignes), pas exportée par le fichier -- impossible à importer sans modifier
`diversification.py` (interdit ici, "ne modifie AUCUN fichier existant"). Elle
est donc reproduite CI-DESSOUS À L'IDENTIQUE (mêmes formules, mêmes constantes
importées `RISK_PCT_PATTERN_A/B`/`MIN_BORDERS`/`size_fraction`) -- dupliquée
pour l'exposer bougie par bougie, PAS réinventée.

La SEULE chose réellement NEUVE ici est la BOUCLE D'ORCHESTRATION qui fait
tourner le protocole unifié (RANGE+TENDANCE) ET le moteur de diversification
(Pattern A + Pattern B) sur le MÊME index de bougies H4, et calcule à CHAQUE
bougie le risque nominal agrégé RÉEL -- exactement le même principe que
`unified_protocol.py` a déjà appliqué pour fusionner RANGE et TENDANCE (sa
propre docstring : "le seul code nouveau est la boucle d'orchestration
bar-par-bar"). Cette boucle DUPLIQUE volontairement l'ORDRE DES OPÉRATIONS
déjà présent et déjà testé dans `_run_core_unified` (unified_protocol.py) et
`run_diversified` (diversification.py) -- ce n'est pas une nouvelle décision
de conception, seulement la réplication à l'identique de deux boucles déjà
validées séparément, nécessaire car AUCUNE des deux fonctions d'origine
n'expose son état bougie par bougie (elles ne retournent qu'un résultat
agrégé final) -- ce dont ce script a besoin pour mesurer le risque à chaque
instant, pas seulement au dernier.

================================================================================
MÉTHODE DE CALCUL DU "RISQUE NOMINAL RÉELLEMENT ENGAGÉ" (choix documentés,
pas inventés en silence, même esprit que les hypothèses H1-H12/U1-U5 de
trend_table.py/unified_protocol.py)
================================================================================
R1. Pour toute position ouverte (tranche RANGE, jambe "+Reverse" RANGE,
    campagne TENDANCE, jambe "+Reverse" TENDANCE, Pattern A, Pattern B), le
    risque nominal courant = la fraction de capital RÉELLEMENT perdue SI le
    stop ACTUEL (qui peut avoir été remonté au break-even -- Confirmation
    RANGE, Divergence TENDANCE -- ce qui réduit le risque) est touché
    MAINTENANT, avec la taille RESTANTE actuelle (réduite par les clôtures
    partielles Validation/Confirmation, augmentée par les renforts de
    campagne) :
        risque_position = remaining * max(0, (entry - stop) / entry)   [long]
        risque_position = taille    * max(0, (stop  - entry) / entry)  [short]
    Choix explicite, répondant directement à la consigne de la tâche ("pas
    juste le risque nominal théorique par profil, le risque RÉELLEMENT engagé
    bougie par bougie") : PAS le risk_pct théorique de profil (qui suppose un
    stop inchangé et une taille pleine, jamais réduite ni augmentée). Cette
    formule ne dépend PAS du prix courant -- seulement entry/stop/remaining,
    cohérent avec la convention P&L déjà utilisée PARTOUT dans ce projet
    (`(price - entry) / entry * remaining`, cf. `process_tranche`/`step_campaign`)
    -- c'est la grandeur "combien je perds si le stop est touché maintenant",
    pas une estimation mark-to-market du P&L latent (grandeur différente,
    déjà calculée ailleurs sous le nom `equity_curve`/`mtm`). Plafonné à 0
    (jamais négatif) : une position dont le stop est déjà remonté au-delà du
    prix d'entrée (breakeven ou mieux) ne présente plus AUCUN risque de perte
    à ce titre.
R2. Le risque AGRÉGÉ à une bougie = somme des risques de TOUTES les positions
    ouvertes, tous systèmes confondus (jusqu'à MAX_TRANCHES=3 tranches RANGE
    pyramidées + 1 jambe "+Reverse" RANGE + 1 campagne TENDANCE + 1 jambe
    "+Reverse" TENDANCE + Pattern A + Pattern B = jusqu'à 8 positions
    simultanées théoriquement représentables par l'état de ce script).
R3. `n_systems_open` compte les "systèmes" actifs (RANGE / TENDANCE /
    Pattern A / Pattern B), pas les positions individuelles -- répond
    directement à "quel est le moment où le plus de systèmes ont une position
    ouverte simultanément" (max théorique = 4).
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "/home/user/emile/code")

import numpy as np
import pandas as pd

from backtest_phase2 import load_h1, resample, EMA_SLOW
from backtest_phase2_v7 import PROFILES_V4, MIN_BORDERS, RULE3_STREAK, RULE3_SIZE_MULT, MAX_TRANCHES
from backtest_phase2_recommended import WARMUP
from backtest_phase2_faithful import REVERSE_SCOPED_PROFILE
from position_engine import make_open_tranche_fn, process_tranche, process_reverse
from trend_table import PROFILES_TREND, step_campaign, try_open_campaign, step_reverse, load_volume
from unified_protocol import (
    _prepare_unified, _accumulation_active, _campaign_ev, resample_h4_with_volume, PROFILE_NAMES,
)
from diversification import prepare_diversified, size_fraction, RISK_PCT_PATTERN_A, RISK_PCT_PATTERN_B, \
    MAX_RISK_PER_ZONE_PCT
import capital_tiers

HARD_MAX_RISK_PCT = capital_tiers.HARD_MAX_RISK_PCT  # §5 RULES_EXTRACTION.md, 5% -- cf. tête de fichier


# ---------------------------------------------------------------------------
# R1 : risque nominal d'une position, cf. docstring "MÉTHODE DE CALCUL" ci-dessus.
# ---------------------------------------------------------------------------
def _long_risk(pos: dict) -> float:
    if pos is None:
        return 0.0
    remaining = pos.get("remaining", 0.0)
    entry = pos.get("entry", 0.0)
    stop = pos.get("stop", 0.0)
    if remaining <= 0 or entry <= 0:
        return 0.0
    return remaining * max(0.0, (entry - stop) / entry)


def _short_risk(pos: dict, size_key: str = "remaining") -> float:
    if pos is None:
        return 0.0
    size = pos.get(size_key, 0.0)
    entry = pos.get("entry", 0.0)
    stop = pos.get("stop", 0.0)
    if size <= 0 or entry <= 0:
        return 0.0
    return size * max(0.0, (stop - entry) / entry)


def _prepare_triple(h1_full: pd.DataFrame, use_mtf_gate: bool = True) -> tuple:
    """Prépare les features des DEUX pipelines (unified_protocol +
    diversification) sur le MÊME historique H4/D1/Hebdomadaire, et vérifie
    (assert, pas supposé) que les deux grilles de bougies H4 sont
    STRICTEMENT identiques (mêmes dates, même longueur) -- condition
    nécessaire pour que l'indice `i` désigne la MÊME bougie dans les deux
    moteurs lors de l'agrégation bougie par bougie ci-dessous."""
    h4_vol = resample_h4_with_volume(h1_full)
    d1 = resample(h1_full[["date", "open", "high", "low", "close"]], "1D")
    weekly = resample(h1_full[["date", "open", "high", "low", "close"]], "W")
    h4_no_vol = h4_vol[["date", "open", "high", "low", "close"]]

    feat_u = _prepare_unified(h4_vol, d1, weekly, use_mtf_gate=use_mtf_gate)
    h4p, _ = prepare_diversified(h4_no_vol, d1)

    assert len(h4p) == len(feat_u["date"]), (
        "grilles H4 désalignées entre unified_protocol et diversification "
        f"({len(feat_u['date'])} vs {len(h4p)} bougies) -- agrégation invalide"
    )
    assert (pd.to_datetime(h4p["date"]).values == pd.to_datetime(pd.Series(feat_u["date"])).values).all(), (
        "dates désalignées entre les deux pipelines -- agrégation par bougie invalide"
    )
    return feat_u, h4p


def _run_triple_core(feat_u: dict, h4p: pd.DataFrame, profile_name: str,
                      management_profile: str = None, enable_pattern_b: bool = True,
                      start: int = 0, end: int = None) -> dict:
    """Boucle d'orchestration -- fait tourner RANGE+TENDANCE (unified_protocol.py)
    ET Pattern A + Pattern B (diversification.py) sur le MÊME index de
    bougies H4, en réutilisant tels quels les fonctions PAR BOUGIE des deux
    modules (cf. tête de fichier pour la liste exacte et pour la seule
    exception documentée, `make_open_fn`). Calcule à chaque bougie le risque
    nominal agrégé réel (R1/R2 ci-dessus) et retourne le maximum observé sur
    `[start, end)` ainsi que le détail de la bougie où il survient.

    Ne calcule PAS de courbe d'équité combinée (hors périmètre de cette
    mesure -- seul le risque nominal engagé est demandé par la tâche) ;
    `n_*_trades` est rapporté pour vérification croisée (les 4 sous-moteurs
    tournent-ils réellement ?), pas pour une performance chiffrée."""
    management_profile = management_profile or profile_name
    p_range = PROFILES_V4[profile_name]
    p_trend = PROFILES_TREND[profile_name]
    mgmt = PROFILES_V4[management_profile]
    risk_pct = p_range["risk_pct"]
    reverse_at_limit = (profile_name == REVERSE_SCOPED_PROFILE)

    # ===== RANGE + TENDANCE : même préparation que _run_core_unified =====
    o, high, low, c = feat_u["open"], feat_u["high"], feat_u["low"], feat_u["close"]
    score = feat_u["score"]
    wall_street_v = feat_u["wall_street_active"]
    n_total = len(o)
    end = n_total if end is None else end

    def gate(i):
        # CORRECTION EXCES H4 (cf. unified_protocol.py) : réplique le gate
        # RANGE RÉEL de _run_core_unified tel qu'il existe désormais,
        # H4-EXCES inclus -- pas une version pré-correction figée.
        return bool(
            feat_u["gate_score"][i] >= 2 and feat_u["gate_regime"][i] != "EXCES"
            and feat_u["regime"][i] != "EXCES"
        )

    def gate_extra(j):
        # CORRECTION PYRAMIDALISATION-RÉGIME (cf. unified_protocol.py) :
        # réplique le gate RANGE RÉEL de _run_core_unified tel qu'il existe
        # désormais -- le renfort exige EN PLUS que le régime H4 natif soit
        # TENDANCE/RANGE_TENDANCIEL, pas une version pré-correction figée.
        abstain = bool(wall_street_v[j])
        g = gate(j) and not abstain
        pyramiding_allowed = feat_u["regime"][j] in ("TENDANCE", "RANGE_TENDANCIEL")
        return g, (g and pyramiding_allowed)

    range_state = {"last_pyramid_high": -np.inf}
    open_tranche_fn = make_open_tranche_fn(
        feat_u["atr"], feat_u["ctx_support_d1"], feat_u["local_range"], feat_u["context_range"],
        feat_u["n_borders"], high, o, score, WARMUP, MIN_BORDERS, MAX_TRANCHES,
        RULE3_STREAK, RULE3_SIZE_MULT, risk_pct, range_state, extra_gate_fn=gate_extra,
    )
    gated_long_signal = np.array([
        (score[i] >= 2) and gate(i) and not bool(wall_street_v[i]) for i in range(n_total)
    ])

    tranches: list = []
    range_reverses: list = []
    campaign = None
    trend_reverse = None
    win_streak = 0
    n_range_trades = n_trend_trades = 0

    # ===== Diversification : même préparation que run_diversified =====
    score_a = h4p["score"].values
    cluster_signal = h4p["cluster_signal"].values.astype(bool)
    atr_v = h4p["atr"].values
    ctx_support_a = h4p["ctx_support"].values
    ctx_support_b = h4p["ctx_support_d1"].values
    local_range_v = h4p["local_range"].values
    context_range_v = h4p["context_range"].values
    n_borders_v = h4p["n_borders"].values
    ctx_score_d1 = h4p["ctx_score_d1"].values
    ctx_regime_d1 = h4p["ctx_regime_d1"].values
    high_d, low_d, o_d, c_d = h4p["high"].values, h4p["low"].values, h4p["open"].values, h4p["close"].values
    warmup_d = EMA_SLOW + 20

    long_signal_a_raw = score_a >= 2
    gated_a = long_signal_a_raw & (ctx_score_d1 >= 2) & (ctx_regime_d1 != "EXCES")
    gated_b = cluster_signal & enable_pattern_b

    # Réplique EXACTE de diversification.py::run_diversified::make_open_fn
    # (fermeture interne non exportée par le fichier d'origine, cf. tête de
    # fichier -- mêmes formules, mêmes constantes importées).
    def make_open_fn(gated_signal, r_pct, ctx_support_v, require_mature):
        def open_fn(i):
            if i <= warmup_d:
                return None
            valid_inputs = (
                not np.isnan(atr_v[i - 1]) and not np.isnan(ctx_support_v[i - 1])
                and not np.isnan(local_range_v[i - 1]) and local_range_v[i - 1] > 0
                and not np.isnan(context_range_v[i - 1]) and context_range_v[i - 1] > 0
            )
            if not valid_inputs or not bool(gated_signal[i - 1]):
                return None
            if require_mature:
                mature = (not np.isnan(n_borders_v[i - 1])) and n_borders_v[i - 1] >= MIN_BORDERS
                if not mature:
                    return None
            entry_price = o_d[i]
            stop_price = min(ctx_support_v[i - 1], entry_price * 0.999)
            size_frac = size_fraction(r_pct, entry_price, stop_price)
            if size_frac <= 0:
                return None
            return {
                "entry": entry_price, "stop": stop_price, "remaining": size_frac,
                "val_done": False, "conf_done": False, "pnl_accum": 0.0,
                "val_px": entry_price + local_range_v[i - 1],
                "conf_px": entry_price + context_range_v[i - 1],
                "lim_px": entry_price + 1.5 * context_range_v[i - 1],
            }
        return open_fn

    open_fn_a = make_open_fn(gated_a, RISK_PCT_PATTERN_A, ctx_support_a, require_mature=True)
    open_fn_b = make_open_fn(gated_b, RISK_PCT_PATTERN_B, ctx_support_b, require_mature=False)
    tr_a, tr_b = None, None
    n_div_a_trades = n_div_b_trades = 0

    # ===== Suivi du risque agrégé =====
    max_risk_total = -1.0
    max_risk_row = None

    for i in range(max(1, start + 1), end):
        # ---- RANGE+TENDANCE : ordre EXACT de _run_core_unified ----
        if trend_reverse is not None:
            closed_r, _, pnl_r = step_reverse(trend_reverse, i, high, low, c)
            if closed_r:
                n_trend_trades += 1
                win_streak = win_streak + 1 if pnl_r > 0 else 0
                trend_reverse = None

        remaining_reverses = []
        for rp in range_reverses:
            closed_r, _, pnl_r = process_reverse(rp, i, high, low, c)
            if closed_r:
                n_range_trades += 1
                win_streak = win_streak + 1 if pnl_r > 0 else 0
            else:
                remaining_reverses.append(rp)
        range_reverses = remaining_reverses

        if campaign is not None:
            ev = _campaign_ev(feat_u, i)
            closed, _, realized, reverse_request = step_campaign(campaign, i, o, high, low, c, ev, p_trend)
            if realized is not None:
                n_trend_trades += 1
                win_streak = win_streak + 1 if realized > 0 else 0
            if closed:
                campaign = None
                if reverse_request is not None:
                    trend_reverse = reverse_request

        if tranches:
            long_signal_prev = bool(gated_long_signal[i - 1])
            remaining_tranches = []
            new_range_reverses = []
            for tr in tranches:
                closed, _, realized = process_tranche(
                    tr, i, o, low, c, long_signal_prev,
                    val_close_frac=p_range["val_close"], conf_close_frac=p_range["conf_close"],
                    conf_to_be=True, reverse_at_limit=reverse_at_limit,
                )
                if closed:
                    n_range_trades += 1
                    win_streak = win_streak + 1 if realized > 0 else 0
                    rr = tr.get("reverse_request")
                    if rr is not None:
                        new_range_reverses.append(rr)
                else:
                    remaining_tranches.append(tr)
            tranches = remaining_tranches
            range_reverses.extend(new_range_reverses)

        if campaign is None and trend_reverse is None and _accumulation_active(feat_u, i):
            j = i - 1
            new_campaign, _ = try_open_campaign(i, o, feat_u["ctx_support"][j], True, p_trend)
            if new_campaign is not None:
                campaign = new_campaign

        if len(tranches) < MAX_TRANCHES:
            new_tr = open_tranche_fn(i, tranches, win_streak)
            if new_tr is not None:
                tranches.append(new_tr)

        # ---- Diversification : ordre EXACT de run_diversified ----
        if tr_a is not None:
            closed, _, _ = process_tranche(
                tr_a, i, o_d, low_d, c_d, bool(gated_a[i - 1]), mgmt["val_close"], mgmt["conf_close"], True,
            )
            if closed:
                n_div_a_trades += 1
                tr_a = None

        if tr_b is not None:
            closed, _, _ = process_tranche(
                tr_b, i, o_d, low_d, c_d, bool(gated_b[i - 1]), mgmt["val_close"], mgmt["conf_close"], True,
            )
            if closed:
                n_div_b_trades += 1
                tr_b = None

        if tr_a is None:
            new_tr = open_fn_a(i)
            if new_tr is not None:
                tr_a = new_tr

        if tr_b is None:
            new_tr = open_fn_b(i)
            if new_tr is not None:
                tr_b = new_tr

        # ---- R1/R2 : risque nominal agrégé RÉEL à cette bougie ----
        risk_range = sum(_long_risk(tr) for tr in tranches) + sum(_short_risk(rp) for rp in range_reverses)
        risk_trend = _long_risk(campaign) + _short_risk(trend_reverse, size_key="frac")
        risk_div_a = _long_risk(tr_a)
        risk_div_b = _long_risk(tr_b)
        risk_total = risk_range + risk_trend + risk_div_a + risk_div_b

        if risk_total > max_risk_total:
            n_systems_open = (
                int(bool(tranches or range_reverses))
                + int(bool(campaign is not None or trend_reverse is not None))
                + int(tr_a is not None) + int(tr_b is not None)
            )
            max_risk_total = risk_total
            max_risk_row = {
                "bar_index": i, "date": str(feat_u["date"][i]),
                "risk_range_pct": round(risk_range * 100, 4),
                "risk_trend_pct": round(risk_trend * 100, 4),
                "risk_div_a_pct": round(risk_div_a * 100, 4),
                "risk_div_b_pct": round(risk_div_b * 100, 4),
                "risk_total_pct": round(risk_total * 100, 4),
                "n_range_tranches_open": len(tranches),
                "n_range_reverses_open": len(range_reverses),
                "trend_campaign_open": campaign is not None,
                "trend_reverse_open": trend_reverse is not None,
                "pattern_a_open": tr_a is not None,
                "pattern_b_open": tr_b is not None,
                "n_systems_open": n_systems_open,
            }

    return {
        "max_risk_total_pct": round(max_risk_total * 100, 4) if max_risk_total >= 0 else 0.0,
        "max_risk_row": max_risk_row,
        "n_range_trades": n_range_trades, "n_trend_trades": n_trend_trades,
        "n_div_a_trades": n_div_a_trades, "n_div_b_trades": n_div_b_trades,
    }


# ---------------------------------------------------------------------------
# Sanity check rapide (pas une suite pytest complète -- analyse ponctuelle,
# cf. rapport) : si UNE seule des 4 sous-briques a une position ouverte à un
# instant donné, le risque agrégé DOIT être exactement égal au risque de
# cette seule position (invariant simple, vérifié sur un mini-scénario
# synthétique avant de faire confiance au résultat sur données réelles).
# ---------------------------------------------------------------------------
def _self_check():
    # Position long ouverte seule : remaining=0.5, entry=100, stop=95 -> risque = 0.5*5% = 2.5%
    tr = {"entry": 100.0, "stop": 95.0, "remaining": 0.5}
    assert abs(_long_risk(tr) - 0.025) < 1e-9, _long_risk(tr)
    # Stop remonté au-dessus de l'entrée (breakeven+) -> risque nul, jamais négatif
    tr_be = {"entry": 100.0, "stop": 101.0, "remaining": 0.5}
    assert _long_risk(tr_be) == 0.0
    # Jambe short : stop=105, entry=100, taille=0.3 -> risque = 0.3*5% = 1.5%
    rp = {"entry": 100.0, "stop": 105.0, "remaining": 0.3}
    assert abs(_short_risk(rp) - 0.015) < 1e-9, _short_risk(rp)
    # None -> 0
    assert _long_risk(None) == 0.0 and _short_risk(None) == 0.0
    print("Self-check R1/R2 : OK (formules de risque nominal vérifiées sur cas synthétiques)")


def yearly_breakdown(symbol: str, profile: str, feat_u: dict, h4p: pd.DataFrame) -> list:
    dates = pd.to_datetime(pd.Series(feat_u["date"]))
    years = sorted(dates.dt.year.unique())
    rows = []
    for y in years:
        idx = np.where(dates.dt.year.values == y)[0]
        if len(idx) == 0:
            continue
        start, end = int(idx[0]), int(idx[-1]) + 1
        res = _run_triple_core(feat_u, h4p, profile, start=start, end=end)
        row = {"symbol": symbol, "profile": profile, "year": int(y), "n_bars": end - start,
               "max_risk_total_pct": res["max_risk_total_pct"],
               "n_range_trades": res["n_range_trades"], "n_trend_trades": res["n_trend_trades"],
               "n_div_a_trades": res["n_div_a_trades"], "n_div_b_trades": res["n_div_b_trades"],
               "exceeds_5pct_global_cap": res["max_risk_total_pct"] > 5.0,
               "exceeds_2pct_diversification_cap": res["max_risk_total_pct"] > 2.0}
        mrr = res["max_risk_row"] or {}
        for k, v in mrr.items():
            row[f"max_{k}"] = v
        rows.append(row)
    return rows


def main():
    _self_check()
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    yearly_rows = []
    full_rows = []

    for symbol in symbols:
        h1 = load_h1(symbol)
        vol_h1 = load_volume(symbol)
        h1_full = h1.merge(vol_h1, on="date", how="inner")
        feat_u, h4p = _prepare_triple(h1_full, use_mtf_gate=True)

        for profile in PROFILE_NAMES:
            yearly_rows.extend(yearly_breakdown(symbol, profile, feat_u, h4p))

            # Historique complet (non re-tranché par année) -- borne "pire
            # instant JAMAIS observé" en continu, complémentaire du
            # walk-forward annuel demandé (qui repart à zéro chaque année,
            # cf. méthode de walkforward_unified.py).
            res_full = _run_triple_core(feat_u, h4p, profile)
            row = {"symbol": symbol, "profile": profile,
                   "max_risk_total_pct": res_full["max_risk_total_pct"],
                   "n_range_trades": res_full["n_range_trades"], "n_trend_trades": res_full["n_trend_trades"],
                   "n_div_a_trades": res_full["n_div_a_trades"], "n_div_b_trades": res_full["n_div_b_trades"],
                   "exceeds_5pct_global_cap": res_full["max_risk_total_pct"] > 5.0,
                   "exceeds_2pct_diversification_cap": res_full["max_risk_total_pct"] > 2.0}
            mrr = res_full["max_risk_row"] or {}
            for k, v in mrr.items():
                row[f"max_{k}"] = v
            full_rows.append(row)
            print(f"{symbol}/{profile} (historique complet) : "
                  f"max risque nominal agrégé = {res_full['max_risk_total_pct']}% "
                  f"le {mrr.get('date')} ({mrr.get('n_systems_open')} systèmes ouverts)")

    yearly_df = pd.DataFrame(yearly_rows)
    full_df = pd.DataFrame(full_rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 40)

    yearly_df.to_csv("risk_aggregation_walkforward.csv", index=False)
    full_df.to_csv("risk_aggregation_full_history.csv", index=False)

    print("\n=== Walk-forward annuel (comme walkforward_unified.py) ===")
    print(yearly_df.to_string(index=False))
    print("\n=== Historique complet (2020-2026, non re-tranché) ===")
    print(full_df.to_string(index=False))

    # ---- Synthèse honnête : le maximum GLOBAL, tous scénarios confondus ----
    global_max_row = yearly_df.loc[yearly_df["max_risk_total_pct"].idxmax()]
    print("\n=== MAXIMUM GLOBAL (walk-forward annuel, tous actifs/profils/années) ===")
    print(global_max_row.to_string())

    global_max_full_row = full_df.loc[full_df["max_risk_total_pct"].idxmax()]
    print("\n=== MAXIMUM GLOBAL (historique complet, tous actifs/profils) ===")
    print(global_max_full_row.to_string())

    n_exceed_5 = int(yearly_df["exceeds_5pct_global_cap"].sum())
    n_exceed_2 = int(yearly_df["exceeds_2pct_diversification_cap"].sum())
    print(f"\nCombinaisons (actif x profil x année) dépassant le plafond global "
          f"§5 (5%, RULES_EXTRACTION.md) : {n_exceed_5}/{len(yearly_df)}")
    print(f"Combinaisons dépassant le plafond de diversification (2%, source #16, "
          f"TRADING_LESSONS_CLUSTERS_PRIX.md -- rapporté pour référence, PAS présenté "
          f"comme le plafond applicable à cette combinaison à 3 systèmes) : "
          f"{n_exceed_2}/{len(yearly_df)}")


if __name__ == "__main__":
    main()
