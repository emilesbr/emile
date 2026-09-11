"""
Robustesse du seuil de confluence Cluster Technique (`SUPPORT_PROXIMITY_PCTL`)
— vague 5, `PLAN.md` "Plan d'autonomie 8h" : "robustesse du seuil de
confluence Cluster Technique", pisté ouverte depuis la vague 2.

MISE EN GARDE explicite reçue et respectée : ce chantier est le plus à
risque de sur-ajustement de la session. Ce script N'EST PAS une recherche
du MEILLEUR seuil — c'est un test de SENSIBILITÉ : l'effet marginal du
Cluster Technique sur le drawdown, déjà mesuré comme quasi nul et MIXTE au
seuil retenu en production (`SUPPORT_PROXIMITY_PCTL=0.20`, cf.
`COUVERTURE_ENSEIGNEMENTS.md`, note "Diversification 1%+1% + Cluster
Technique" : comparaison ISOLÉE +0,2/+0,3/-0,2/-0,1 pt BTC/ETH/BNB/SOL),
reste-t-il proche de zéro pour d'autres seuils raisonnables, ou bascule-t-il
radicalement selon le choix ? Un résultat "ça bouge dans tous les sens"
serait un signal de FRAGILITÉ/sur-ajustement à signaler explicitement, PAS
une découverte à célébrer. Aucun des seuils testés ici n'est présenté comme
"meilleur" que 0.20 — le seuil retenu en production a été choisi pour une
raison EMPIRIQUE différente et déjà documentée (`cluster_technique.py`,
section H2) : la première définition (distance fixe) ne se déclenchait
JAMAIS sur données réelles ; 0.20 est la valeur qui a permis au signal de
se déclencher DU TOUT (percentile adaptatif), pas une valeur choisie pour
maximiser une performance.

Grille testée : 0.10 / 0.15 / 0.20 (référence, déjà en production,
inchangée) / 0.25 / 0.30 — une grille SYMÉTRIQUE autour du seuil retenu,
fixée AVANT de lancer le script, pas resserrée après avoir regardé les
résultats intermédiaires.

DISCIPLINE DE FICHIERS — ne touche à AUCUN fichier de production
-----------------------------------------------------------------------------
`cluster_technique.py::add_cluster_signal` accepte déjà `proximity_pctl` en
paramètre (jamais modifié ici). Mais `diversification.py::prepare_diversified`/
`run_diversified` ne le propagent pas jusqu'à cet appel. Plutôt que de
modifier `diversification.py` (fichier partagé avec l'agent qui travaille
en parallèle sur la branche, et déjà mesuré/documenté tel quel dans
`COUVERTURE_ENSEIGNEMENTS.md`), ce script DUPLIQUE `prepare_diversified`/
`run_diversified` presque à l'identique — SEULE différence : `proximity_pctl`
transmis en paramètre au lieu du défaut du module — même discipline déjà
appliquée par `backtest_phase2_fib.py`/`backtest_phase2_diversification.py`
("dupliqué de ..., ne touche à aucun fichier de production"). Fidélité de
la duplication vérifiée par test de non-régression
(`test_cluster_technique_threshold_robustness.py`) : au seuil de référence
(0.20), cette copie doit produire EXACTEMENT le même résultat que
`diversification.run_diversified`.

Comparaison reprise à l'identique de `backtest_phase2_diversification.py`
(comparaison ISOLÉE, pyramidalisation neutralisée des deux côtés — PAS la
comparaison naïve, déjà documentée comme trompeuse car elle mélange l'effet
du Cluster Technique avec celui de la suppression de la pyramidalisation) :
Pattern A seul sans pyramide (`enable_pattern_b=False`) vs diversifié
(Pattern A + B), `management_profile="MODERE"`, gate MTF actif sur Pattern
A. Seule la mesure ISOLÉE est reprise ici, car c'est elle qui donne l'effet
marginal réel dont on teste la robustesse.
"""
import numpy as np
import pandas as pd
import sys

from emile.backtests.backtest_phase2 import FEE, load_h1, resample
from emile.backtests.backtest_phase2_v7 import prepare, attach_higher_context, PROFILES_V4, MIN_BORDERS, EMA_SLOW
from emile.core.position_engine import process_tranche
from emile.core.cluster_technique import add_cluster_signal
from emile.core.diversification import RISK_PCT_PATTERN_A, RISK_PCT_PATTERN_B, size_fraction

# Cf. mise en garde de tête : grille SYMÉTRIQUE fixée a priori, 0.20 = seuil
# de référence déjà en production dans cluster_technique.py, inchangé.
PROXIMITY_PCTL_GRID = (0.10, 0.15, 0.20, 0.25, 0.30)
BASELINE_PCTL = 0.20

def prepare_diversified_pctl(h4: pd.DataFrame, d1: pd.DataFrame, proximity_pctl: float) -> pd.DataFrame:
    """Copie de `diversification.py::prepare_diversified` — SEULE
    différence : `proximity_pctl` transmis à `add_cluster_signal` au lieu de
    son défaut de module (`cluster_technique.SUPPORT_PROXIMITY_PCTL`, 0.20).
    Cf. docstring de tête pour la raison de la duplication."""
    h4p = prepare(h4)
    d1p = prepare(d1)
    ctx_score, ctx_regime, ctx_support_d1 = attach_higher_context(h4p, d1p, pd.Timedelta(days=1))

    h4p = h4p.copy()
    h4p["ctx_score_d1"] = ctx_score
    h4p["ctx_regime_d1"] = ctx_regime
    h4p["ctx_support_d1"] = ctx_support_d1

    cluster_input = h4p.drop(columns=["ctx_support", "regime"]).copy()
    cluster_input["ctx_support"] = ctx_support_d1
    cluster_input["regime"] = ctx_regime
    cluster_out = add_cluster_signal(cluster_input, proximity_pctl=proximity_pctl)

    h4p["cluster_signal"] = cluster_out["cluster_signal"].values
    return h4p

def run_diversified_pctl(h4: pd.DataFrame, d1: pd.DataFrame, proximity_pctl: float,
                          management_profile: str = "MODERE", use_mtf_gate: bool = True,
                          enable_pattern_b: bool = True) -> dict:
    """Copie de `diversification.py::run_diversified` — SEULE différence :
    `proximity_pctl` transmis via `prepare_diversified_pctl` ci-dessus.
    Logique de trading (2 livres de tranches indépendants, `process_tranche`
    réutilisé TEL QUEL) rigoureusement identique à l'original — vérifiée par
    `test_cluster_technique_threshold_robustness.py::
    test_matches_diversification_reference_at_baseline_threshold`."""
    mgmt = PROFILES_V4[management_profile]
    h4p = prepare_diversified_pctl(h4, d1, proximity_pctl)

    score = h4p["score"].values
    cluster_signal = h4p["cluster_signal"].values.astype(bool)
    atr_v = h4p["atr"].values
    ctx_support_a = h4p["ctx_support"].values
    ctx_support_b = h4p["ctx_support_d1"].values
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
    gated_b = cluster_signal & enable_pattern_b

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

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        for pctl in PROXIMITY_PCTL_GRID:
            a_alone = run_diversified_pctl(h4.copy(), d1.copy(), proximity_pctl=pctl,
                                            management_profile="MODERE", use_mtf_gate=True,
                                            enable_pattern_b=False)
            div = run_diversified_pctl(h4.copy(), d1.copy(), proximity_pctl=pctl,
                                        management_profile="MODERE", use_mtf_gate=True,
                                        enable_pattern_b=True)
            delta_dd = div["max_dd_%"] - a_alone["max_dd_%"]  # cf. backtest_phase2_diversification.py : >0 = REDUIT le DD
            rows.append({
                "symbol": symbol, "proximity_pctl": pctl,
                "n_trades_pattern_b": div["n_trades_pattern_b"],
                "max_dd_pattern_a_alone_%": a_alone["max_dd_%"],
                "max_dd_diversifie_%": div["max_dd_%"],
                "delta_dd_isole_pt": round(delta_dd, 2),
            })
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("cluster_technique_threshold_robustness_results.csv", index=False)

    print("\n--- Lecture de ROBUSTESSE (pas une recherche du meilleur seuil, cf. mise en garde de tête) ---")
    for symbol in symbols:
        sub = result[result.symbol == symbol]
        lo, hi = sub["delta_dd_isole_pt"].min(), sub["delta_dd_isole_pt"].max()
        spread = hi - lo
        same_sign = (sub["delta_dd_isole_pt"] >= 0).all() or (sub["delta_dd_isole_pt"] <= 0).all()
        print(f"  {symbol:<10} delta_dd_isole sur {len(PROXIMITY_PCTL_GRID)} seuils "
              f"({PROXIMITY_PCTL_GRID}) : min={lo:+.2f} max={hi:+.2f} amplitude={spread:.2f}pt "
              f"signe_stable={same_sign}")

    global_spread = result["delta_dd_isole_pt"].max() - result["delta_dd_isole_pt"].min()
    print(
        f"\nCONSTAT HONNÊTE (pas maquillé) : sur les {len(symbols)} actifs x {len(PROXIMITY_PCTL_GRID)} seuils "
        f"({len(result)} configurations), l'effet marginal isolé du Cluster Technique sur le drawdown reste "
        f"{'proche de zéro et du même ordre de grandeur' if abs(result['delta_dd_isole_pt']).max() < 3 else 'PAS toujours proche de zéro'} "
        f"quel que soit le seuil testé (amplitude globale {global_spread:.2f}pt, valeurs individuelles "
        f"entre {result['delta_dd_isole_pt'].min():+.2f} et {result['delta_dd_isole_pt'].max():+.2f}pt). "
        "Rappel : ceci teste la SENSIBILITÉ de la conclusion 'effet quasi nul et mixte', PAS la recherche "
        "d'un seuil supérieur à 0.20 -- aucun seuil de cette grille n'est recommandé comme remplaçant."
    )

if __name__ == "__main__":
    main()
