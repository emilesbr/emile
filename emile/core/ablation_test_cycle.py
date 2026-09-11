"""
Test d'ablation du composant cycle — item explicitement recommandé mais
jamais fait pendant le traitement du P0 (COUVERTURE_ENSEIGNEMENTS.md,
"Recommandation directe pour la suite" du niveau 2).

Question posée : une fois `add_proxy_v2_score` rendu causal, le composant
cycle isolé ne montre plus de corrélation significative avec le rendement
futur (sur 5 actifs réels). Deux hypothèses possibles :
  (a) le cycle est un filtre neutre/aléatoire qui DILUE la précision du
      score momentum+structure sans l'annuler (hypothèse posée dans
      COUVERTURE_ENSEIGNEMENTS.md, jamais prouvée)
  (b) le cycle apporte une contribution réelle non captée par la simple
      corrélation cycle-seul (interaction avec les 2 autres composantes)

Méthode : ne touche à aucun fichier de production. Réutilise
`prepare()`/`attach_higher_context()`/`run_v7()` de `backtest_phase2_v7.py`
tels quels, mais après appel à `prepare()` (qui appelle déjà
`add_proxy_v2_score`, donc calcule déjà `momentum_favorable` et
`structure_favorable`), remplace la colonne `score` par un score ablaté
(momentum+structure seuls, 0-2) AVANT `attach_higher_context`/le calcul du
signal. Le seuil d'entrée reste ">= 2" (comme le score complet), donc pour
le score ablaté (max 2) cela revient à exiger momentum ET structure
d'accord simultanément — l'équivalent structurel du seuil ">= 2 sur 3"
appliqué au score complet.
"""
import sys
import numpy as np
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import prepare, attach_higher_context, run_v7, PROFILES_V4
from emile.core.position_engine import run_position_engine
from emile.backtests.backtest_phase2 import FEE, EMA_SLOW

def prepare_ablated(df: pd.DataFrame) -> pd.DataFrame:
    """Comme prepare(), mais le score utilisé en aval est momentum+structure
    seuls (le cycle reste calculé/présent dans le dataframe pour référence,
    juste exclu du score qui pilote les décisions)."""
    df = prepare(df)
    df["score"] = df["momentum_favorable"].astype(int) + df["structure_favorable"].astype(int)
    return df

def run_v7_no_cycle(h4: pd.DataFrame, d1: pd.DataFrame, profile_name: str, use_mtf_gate: bool = True) -> dict:
    """Duplique le corps de run_v7 (backtest_phase2_v7.py) à l'identique,
    seule différence : prepare_ablated() au lieu de prepare(). Dupliqué
    plutôt que factorisé pour ne pas toucher au fichier de production
    pendant ce test ponctuel — si l'ablation s'avère concluante, à
    factoriser proprement (paramètre score_fn) dans un futur commit."""
    import sys as _sys
    from scipy.signal import argrelextrema  # noqa: F401 (déjà importé indirectement par prepare)
    p = PROFILES_V4[profile_name]
    h4 = prepare_ablated(h4)
    d1 = prepare_ablated(d1)
    ctx_score, ctx_regime, ctx_support_d1 = attach_higher_context(h4, d1, pd.Timedelta(days=1))

    score = h4["score"].values
    atr_v = h4["atr"].values
    ctx_support_v = h4["ctx_support"].values
    local_range_v = h4["local_range"].values
    context_range_v = h4["context_range"].values
    n_borders_v = h4["n_borders"].values
    high, low, o, c = h4["high"].values, h4["low"].values, h4["open"].values, h4["close"].values
    n = len(h4)
    warmup = EMA_SLOW + 20
    MIN_BORDERS = 3
    RULE3_STREAK = 3
    RULE3_SIZE_MULT = 0.5
    MAX_TRANCHES = 3

    state = {"last_pyramid_high": -np.inf}

    def open_tranche_fn(i, tranches, win_streak):
        long_signal_prev = score[i - 1] >= 2
        mature = (not np.isnan(n_borders_v[i - 1])) and n_borders_v[i - 1] >= MIN_BORDERS
        d1_aligned = (ctx_score[i - 1] >= 2) if use_mtf_gate else True
        d1_not_excess = (ctx_regime[i - 1] != "EXCES") if use_mtf_gate else True
        valid_inputs = (
            not np.isnan(atr_v[i - 1]) and not np.isnan(ctx_support_v[i - 1])
            and not np.isnan(local_range_v[i - 1]) and local_range_v[i - 1] > 0
            and not np.isnan(context_range_v[i - 1]) and context_range_v[i - 1] > 0
        )
        gated_signal = long_signal_prev and d1_aligned and d1_not_excess
        is_fresh_entry = (i > warmup and len(tranches) == 0 and gated_signal and mature and valid_inputs)
        is_pyramid_add = (
            i > warmup and 0 < len(tranches) < MAX_TRANCHES and gated_signal and valid_inputs
            and high[i - 1] > state["last_pyramid_high"]
        )
        if not (is_fresh_entry or is_pyramid_add):
            return None
        entry_price = o[i]
        stop_price = min(ctx_support_v[i - 1], entry_price * 0.999)
        stop_pct = (entry_price - stop_price) / entry_price
        risk_pct = p["risk_pct"]
        if win_streak >= RULE3_STREAK:
            risk_pct *= RULE3_SIZE_MULT
        size_frac = min(1.0 / MAX_TRANCHES, risk_pct / stop_pct) if stop_pct > 0 else 0.0
        if size_frac <= 0:
            return None
        state["last_pyramid_high"] = max(state["last_pyramid_high"], high[i - 1]) if is_pyramid_add else high[i - 1]
        return {
            "entry": entry_price, "stop": stop_price, "remaining": size_frac,
            "val_done": False, "conf_done": False, "pnl_accum": 0.0,
            "val_px": entry_price + local_range_v[i - 1],
            "conf_px": entry_price + context_range_v[i - 1],
            "lim_px": entry_price + 1.5 * context_range_v[i - 1],
        }

    gated_long_signal = np.array([
        (score[i] >= 2) and ((ctx_score[i] >= 2) if use_mtf_gate else True)
        and ((ctx_regime[i] != "EXCES") if use_mtf_gate else True)
        for i in range(n)
    ])
    raw = run_position_engine(
        n, o, high, low, c, gated_long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=MAX_TRANCHES, fee=FEE,
    )
    return {
        "n_trades": raw["n_trades"], "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"], "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
    }

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        for profile in PROFILES_V4:
            full = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False)
            no_cycle = run_v7_no_cycle(h4.copy(), d1.copy(), profile, use_mtf_gate=True)
            rows.append({"symbol": symbol, "profile": profile, "variant": "score_complet (momentum+cycle+structure>=2)", **full})
            rows.append({"symbol": symbol, "profile": profile, "variant": "score_ablate (momentum+structure, sans cycle)", **no_cycle})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("ablation_test_cycle_results.csv", index=False)

if __name__ == "__main__":
    main()
