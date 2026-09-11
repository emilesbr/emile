"""
Diversification statistique du risque "1% + 1%" (2 patterns indépendants) —
`TRADING_LESSONS_CLUSTERS_PRIX.md` (source #16, cf. `TRADING_LESSONS_INDEX.md`
/ `COUVERTURE_ENSEIGNEMENTS.md`, ligne "Diversification 1%+1% + Cluster
Technique"). `PLAN.md`, backlog item 7 ("Patterns/outils jamais construits").

CE QUE LA SOURCE DIT LITTÉRALEMENT
-------------------------------------------------------------------------
    "Diversification statistique du risque — nouvelle règle (1% + 1%)
    Plutôt que de 'bourriner' une seule configuration, diviser le risque
    entre patterns aux psychologies divergentes :
    - Règle d'or : jamais >2% de risque maximal par zone de prix
    - Répartition recommandée : 1% sur la pattern breakout/pullback + 1%
      sur la pattern de moyenne mobile (cluster)
    [...] Logique du dénominateur : passer de 1 à 2 patterns (1/2) offre un
    gain statistique massif en réduction de risque [...] La symbiose se
    trouve dans la paire ou la triplette de patterns."

HYPOTHÈSES D'IMPLÉMENTATION EXPLICITES (le manuel/corpus est sous-spécifié
sur le "comment" — documentées ici, pas décidées en silence)
-------------------------------------------------------------------------
H1. **"Pattern breakout/pullback" = `proxy_v2.py`** (Pattern A ci-dessous),
    réutilisé SANS MODIFICATION via `backtest_phase2_v7.py::prepare`. La
    source ne nomme aucun module précis ; ce projet n'a qu'UN SEUL signal
    de tendance/breakout déjà construit et validé sur plusieurs cycles de
    travail (v4→v7) — c'est le candidat le plus fidèle disponible ici pour
    incarner ce rôle, pas une nouvelle implémentation ad hoc.
H2. **"Pattern de moyenne mobile (cluster)" = `cluster_technique.py`**
    (Pattern B), construit fidèlement à partir de la MÊME source #16 (cf.
    la docstring de ce fichier pour ses propres hypothèses H1-H5).
H3. **Risque FIXE 1%/1%, PAS modulé par le profil de risque choisi**
    (FAIBLE/MODERE/AGRESSIF/TRES_AGRESSIF) — la source donne un chiffre
    ABSOLU ("1% + 1%"), contrairement au reste du risk management de ce
    projet qui varie par profil (`PROFILES_V4`). `PROFILES_V4` n'est
    réutilisé ICI que pour la FORME de gestion de position (fractions de
    clôture Validation/Confirmation, `management_profile`, MODERE par
    défaut — choix arbitraire documenté, la source ne précise rien sur ce
    point pour la règle de diversification elle-même), JAMAIS pour le
    risk_pct des deux patterns.
H4. **Pas de pyramidalisation par pattern** (1 seule tranche ouverte à la
    fois par pattern) — la source ne mentionne AUCUN renforcement pour
    cette règle précise (contrairement à la pyramidalisation, sujet
    distinct déjà traité ailleurs dans ce projet,
    `TRADING_LESSONS_PYRAMIDALISATION.md` / v4-v7). Garder chaque pattern à
    1 tranche rend la règle "1%+1%" directement vérifiable : le risque
    simultané total est <= 2% PAR CONSTRUCTION (jamais besoin d'un plafond
    a posteriori pour le garantir).
H5. **Stop de Pattern B = Extreme Channel de l'UT SUPÉRIEURE (D1)** — la
    source #16 définit littéralement l'Extreme Channel comme "le contexte
    de l'UT supérieure affiché sur l'UT de trading" (sa propre ligne de
    tableau MTF). `ctx_support` du D1 (`attach_higher_context`, comme
    `use_mtf_stop=True` dans v7) est donc utilisé pour Pattern B — PAS le
    `ctx_support` recalculé sur le H4 lui-même. Pattern A garde le
    comportement PAR DÉFAUT de v7 (`use_mtf_stop=False`), le réglage déjà
    mesuré comme préférable pour CE pattern ailleurs dans le projet
    (`MTF_CROSS_VALIDATION_H4_D1.md`), pour rester directement comparable
    à la référence `run_v7` non modifiée.
H6. **"Flux tendanciel établi (post-breakout)" (H3 de `cluster_technique.py`)
    est lu sur le D1 (référence), pas sur le H4** — cohérent avec H5
    ci-dessus et avec le tableau MTF de la source elle-même ("Unité de
    Temps de Référence : Breakout Daily (Flux dominant)") : le "flux"
    évoqué est celui de l'UT de référence, pas de l'UT de trading. Le gate
    MTF standard de v7 (`ctx_score>=2`/`ctx_regime!=EXCES`) N'EST PAS
    répercuté sur Pattern B (déjà entièrement construit contre le contexte
    D1 via H5/H6) — seul Pattern A applique ce gate, comme dans v7.

PLAFONDS DE RISQUE — DEUX PLAFONDS DISTINCTS, NE PAS LES CONFONDRE
-------------------------------------------------------------------------
  - `MAX_RISK_PER_ZONE_PCT` = 2% — plafond SPÉCIFIQUE à cette règle de
    diversification, donné LITTÉRALEMENT par la source #16 elle-même
    ("jamais >2% de risque maximal par zone de prix").
  - `capital_tiers.HARD_MAX_RISK_PCT` = 5% — plafond GLOBAL du §5
    (`RULES_EXTRACTION.md`, "perte spéculative jamais >5% du capital, quel
    que soit le profil"), réutilisé TEL QUEL (import, pas redéfini) comme
    garde-fou ultime, conformément à la tâche demandée.
  Assertion au chargement du module : `MAX_RISK_PER_ZONE_PCT <=
  capital_tiers.HARD_MAX_RISK_PCT` (vrai avec les valeurs actuelles,
  2% <= 5%) — si l'un des deux chiffres était un jour modifié sans
  vérifier l'autre, le module refuse de charger plutôt que de violer
  silencieusement le plafond le plus strict des deux.

DISCIPLINE DE FICHIERS PARTAGÉS
-------------------------------------------------------------------------
Ce module ne touche à AUCUN fichier de production existant (même
discipline que `backtest_phase2_fib.py`) : réutilise `prepare`,
`attach_higher_context`, `PROFILES_V4`, `MIN_BORDERS` de
`backtest_phase2_v7.py` et `process_tranche` de `position_engine.py` TELS
QUELS (import, pas copie/modification — `position_engine.py` est le
fichier de l'autre agent travaillant en parallèle sur cette même branche).

Un moteur DÉDIÉ (pas `run_position_engine`) est nécessaire ici : ce dernier
gère UN SEUL signal / UNE SEULE liste de tranches à la fois, alors qu'il
faut ici DEUX livres de tranches complètement indépendants (patterns et
gating différents) partageant UNE SEULE courbe d'equity — même
raisonnement que documenté dans `trend_table.py` pour ne pas réutiliser
`run_position_engine` hors de son cas d'usage prévu. `process_tranche`
(la mécanique par tranche : Limite/Invalidation/flip/Confirmation/
Validation), en revanche, s'applique à l'identique à chacun des deux
livres — réutilisé tel quel, pas dupliqué.
"""
import numpy as np
import pandas as pd
import sys

from emile.backtests.backtest_phase2 import FEE, EMA_SLOW
from emile.backtests.backtest_phase2_v7 import prepare, attach_higher_context, PROFILES_V4, MIN_BORDERS
from emile.core.position_engine import process_tranche
from emile.core.cluster_technique import add_cluster_signal
from emile.core import capital_tiers

# Cf. H3 : risque FIXE, PAS dérivé de PROFILES_V4.
RISK_PCT_PATTERN_A = 0.01   # "1% sur la pattern breakout/pullback" (proxy_v2)
RISK_PCT_PATTERN_B = 0.01   # "1% sur la pattern de moyenne mobile (cluster)"

# Cf. section "Plafonds de risque" ci-dessus.
MAX_RISK_PER_ZONE_PCT = 0.02
assert MAX_RISK_PER_ZONE_PCT <= capital_tiers.HARD_MAX_RISK_PCT, (
    "Le plafond de diversification (source #16) doit rester sous le plafond "
    "dur global du §5 (capital_tiers.HARD_MAX_RISK_PCT) — sinon les deux "
    "constantes se sont désynchronisées, à corriger avant tout backtest."
)
assert RISK_PCT_PATTERN_A + RISK_PCT_PATTERN_B <= MAX_RISK_PER_ZONE_PCT, (
    "1% + 1% doit rester <= la règle d'or des 2% par zone de prix (source #16)."
)

def size_fraction(risk_pct: float, entry_price: float, stop_price: float) -> float:
    """Fraction de capital à risquer pour une tranche : `risk_pct / distance
    au stop (en %)`, plafonnée à 1.0 (1 seule tranche par pattern, cf. H4 --
    contrairement à `backtest_phase2_v7.py` qui plafonne à `1/MAX_TRANCHES`
    pour permettre la pyramidalisation, ici MAX_TRANCHES=1 par pattern donc
    le plafond est directement 1.0). Retourne 0.0 si le stop n'est pas
    valide (stop >= entrée, ou entrée <= 0) plutôt que de lever une
    exception -- cohérent avec la convention déjà en place dans
    `backtest_phase2_v7.py::run_v7` (`size_frac <= 0 -> pas d'entrée`)."""
    if entry_price <= 0 or stop_price >= entry_price:
        return 0.0
    stop_pct = (entry_price - stop_price) / entry_price
    return min(1.0, risk_pct / stop_pct)

def prepare_diversified(h4: pd.DataFrame, d1: pd.DataFrame) -> tuple:
    """Prépare le H4 avec TOUTES les colonnes nécessaires aux deux patterns :
    - Pattern A (proxy_v2) : 'score'/'n_borders'/'local_range'/
      'context_range'/'ctx_support' (H4 propre) via `prepare()` (v7, non
      modifié).
    - Contexte D1 (référence) : 'ctx_score_d1'/'ctx_regime_d1'/
      'ctx_support_d1', joints sans lookahead via `attach_higher_context`
      (identique à v7).
    - Pattern B (Cluster Technique) : 'cluster_signal' etc., calculé en
      passant EXPLICITEMENT le contexte D1 comme 'ctx_support'/'regime' à
      `add_cluster_signal` (cf. H5/H6 ci-dessus) — PAS le H4 propre.

    Retourne (h4_enrichi, d1_préparé)."""
    h4p = prepare(h4)
    d1p = prepare(d1)
    ctx_score, ctx_regime, ctx_support_d1 = attach_higher_context(h4p, d1p, pd.Timedelta(days=1))

    h4p = h4p.copy()
    h4p["ctx_score_d1"] = ctx_score
    h4p["ctx_regime_d1"] = ctx_regime
    h4p["ctx_support_d1"] = ctx_support_d1

    # H5/H6 : Pattern B voit le contexte D1 comme 'ctx_support'/'regime',
    # PAS le H4 propre (déjà présent dans h4p sous ces mêmes noms pour
    # Pattern A) -- df temporaire dédié pour ne pas écraser les colonnes H4.
    cluster_input = h4p.drop(columns=["ctx_support", "regime"]).copy()
    cluster_input["ctx_support"] = ctx_support_d1
    cluster_input["regime"] = ctx_regime
    cluster_out = add_cluster_signal(cluster_input)

    h4p["cluster_signal"] = cluster_out["cluster_signal"].values
    h4p["ma20"] = cluster_out["ma20"].values
    h4p["ma20_rebound"] = cluster_out["ma20_rebound"].values
    h4p["support_confluence"] = cluster_out["support_confluence"].values
    return h4p, d1p

def run_diversified(h4: pd.DataFrame, d1: pd.DataFrame, management_profile: str = "MODERE",
                     use_mtf_gate: bool = True, enable_pattern_b: bool = True) -> dict:
    """Moteur "1%+1%" : Pattern A (proxy_v2, gate MTF optionnel comme v7) et
    Pattern B (Cluster Technique, contexte D1 déjà intégré au signal lui-même
    cf. H5/H6) tournent SIMULTANÉMENT, chacun risquant `RISK_PCT_PATTERN_A`/
    `RISK_PCT_PATTERN_B` de façon INDÉPENDANTE (1 tranche max chacun, cf. H4),
    sur une seule courbe d'equity partagée (capital réellement diversifié
    entre les deux, pas deux comptes séparés additionnés après coup).

    `management_profile` : clé de `PROFILES_V4` utilisée UNIQUEMENT pour la
    FORME de gestion (val_close_frac/conf_close_frac), PAS pour le risk_pct
    (cf. H3). `use_mtf_gate` : comme v7, s'applique à Pattern A seulement
    (Pattern B a déjà son propre contexte D1 intégré, H6).

    `enable_pattern_b` (défaut True) : si False, Pattern B n'ouvre jamais
    de tranche -- PAS un simple raccourci de commodité, c'est le réglage
    qui rend le backtest comparatif (`backtest_phase2_diversification.py`)
    honnête. Vérification empirique faite AVANT de conclure quoi que ce
    soit (discipline "mode ingénieur senior", `PLAN.md`) : Pattern A tourne
    ICI SANS pyramidalisation (H4, 1 seule tranche), alors que la référence
    `run_v7` pyramidalise (jusqu'à 3 tranches). Une comparaison naïve
    "référence `run_v7` vs `run_diversified` complet" mélangerait donc DEUX
    effets différents -- (1) l'ajout réel du Pattern B, et (2) la
    suppression de la pyramidalisation de Pattern A (déjà documentée
    ailleurs dans ce projet comme "le principal moteur de rendement",
    `backtest_phase2_fib.py`) -- et attribuerait à tort au Pattern B une
    baisse de drawdown qui viendrait en réalité surtout de (2).
    `enable_pattern_b=False` isole Pattern A SEUL dans CE MÊME moteur
    (sans pyramidalisation, 1% de risque), ce qui permet de comparer
    ensuite "Pattern A seul (sans pyramide)" vs "Pattern A + Pattern B"
    et donc de mesurer l'effet MARGINAL réel de la diversification, pas
    un effet confondu avec la pyramidalisation.

    Retourne un dict avec les mêmes clés que `run_v7` (n_trades, max_dd_%,
    total_return_%, win_rate_%, profit_factor) + `n_trades_pattern_a`/
    `n_trades_pattern_b` (répartition par pattern, pour vérifier que les
    deux tournent réellement, pas seulement un des deux par accident)."""
    mgmt = PROFILES_V4[management_profile]
    h4p, _ = prepare_diversified(h4, d1)

    score = h4p["score"].values
    cluster_signal = h4p["cluster_signal"].values.astype(bool)
    atr_v = h4p["atr"].values
    ctx_support_a = h4p["ctx_support"].values         # Pattern A : H4 propre (H5, comme v7 use_mtf_stop=False)
    ctx_support_b = h4p["ctx_support_d1"].values       # Pattern B : D1 (H5)
    local_range_v = h4p["local_range"].values
    context_range_v = h4p["context_range"].values
    n_borders_v = h4p["n_borders"].values
    ctx_score_d1 = h4p["ctx_score_d1"].values
    ctx_regime_d1 = h4p["ctx_regime_d1"].values
    high, low, o, c = h4p["high"].values, h4p["low"].values, h4p["open"].values, h4p["close"].values
    n = len(h4p)
    warmup = EMA_SLOW + 20

    long_signal_a_raw = score >= 2
    if use_mtf_gate:
        d1_aligned = ctx_score_d1 >= 2
        d1_not_excess = ctx_regime_d1 != "EXCES"
        gated_a = long_signal_a_raw & d1_aligned & d1_not_excess
    else:
        gated_a = long_signal_a_raw
    gated_b = cluster_signal & enable_pattern_b  # cf. H6 (gate) ; enable_pattern_b : cf. docstring (ablation honnête)

    def make_open_fn(gated_signal, risk_pct, ctx_support_v, require_mature):
        def open_fn(i):
            if i <= warmup:
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
            entry_price = o[i]
            stop_price = min(ctx_support_v[i - 1], entry_price * 0.999)
            size_frac = size_fraction(risk_pct, entry_price, stop_price)
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

    # Pattern A : maturité n_borders exigée (comme v7, H1 -- même définition
    # de "pattern breakout/pullback"). Pattern B : pas de n_borders (sa
    # propre "maturité" est le trend_established + support_confluence déjà
    # dans cluster_signal, cf. cluster_technique.py H3).
    open_fn_a = make_open_fn(gated_a, RISK_PCT_PATTERN_A, ctx_support_a, require_mature=True)
    open_fn_b = make_open_fn(gated_b, RISK_PCT_PATTERN_B, ctx_support_b, require_mature=False)

    equity = 1.0
    equity_curve = np.empty(n)
    equity_curve[0] = 1.0
    tr_a, tr_b = None, None
    trades = []
    n_trades_a, n_trades_b = 0, 0

    for i in range(1, n):
        if tr_a is not None:
            closed, fee_frac, realized = process_tranche(
                tr_a, i, o, low, c, bool(gated_a[i - 1]), mgmt["val_close"], mgmt["conf_close"], True
            )
            if closed:
                equity *= (1 + realized)
            if fee_frac > 0:
                equity *= (1 - FEE * fee_frac)
            if closed:
                trades.append(realized)
                n_trades_a += 1
                tr_a = None

        if tr_b is not None:
            closed, fee_frac, realized = process_tranche(
                tr_b, i, o, low, c, bool(gated_b[i - 1]), mgmt["val_close"], mgmt["conf_close"], True
            )
            if closed:
                equity *= (1 + realized)
            if fee_frac > 0:
                equity *= (1 - FEE * fee_frac)
            if closed:
                trades.append(realized)
                n_trades_b += 1
                tr_b = None

        if tr_a is None:
            new_tr = open_fn_a(i)
            if new_tr is not None:
                tr_a = new_tr
                equity *= (1 - FEE * new_tr["remaining"])

        if tr_b is None:
            new_tr = open_fn_b(i)
            if new_tr is not None:
                tr_b = new_tr
                equity *= (1 - FEE * new_tr["remaining"])

        unrealized = 0.0
        for tr in (tr_a, tr_b):
            if tr is not None:
                unrealized += tr["pnl_accum"] + (c[i] - tr["entry"]) / tr["entry"] * tr["remaining"]
        equity_curve[i] = equity * (1 + unrealized)

    trades_arr = np.array(trades) if trades else np.array([])
    eq_series = pd.Series(equity_curve)
    max_dd = (eq_series / eq_series.cummax() - 1).min()
    return {
        "n_trades": len(trades_arr),
        "n_trades_pattern_a": n_trades_a,
        "n_trades_pattern_b": n_trades_b,
        "max_dd_%": round(max_dd * 100, 1),
        "total_return_%": round((equity - 1) * 100, 1),
        "win_rate_%": round((trades_arr > 0).mean() * 100, 1) if len(trades_arr) else None,
        "profit_factor": round(trades_arr[trades_arr > 0].sum() / abs(trades_arr[trades_arr < 0].sum()), 2)
        if len(trades_arr) and (trades_arr < 0).any() else None,
    }

if __name__ == "__main__":
    import sys
    
    from emile.backtests.backtest_phase2 import load_h1, resample

    h1 = load_h1("BTCUSDT")
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")
    res = run_diversified(h4, d1)
    print("Diversification 1%+1% (BTC, management_profile=MODERE) :")
    for k, v in res.items():
        print(f"  {k}: {v}")
