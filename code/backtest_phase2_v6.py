"""
Phase 2 v6 — ajoute la distinction de régime (Range/Tendance/Excès) absente
de v4/v5, en s'appuyant sur regime_classifier.py. Règle appliquée :
  - EXCES        : aucune entrée, quel que soit le signal (règle explicite
    du manuel, jamais respectée avant cette version)
  - TENDANCE / RANGE_TENDANCIEL : entrée standard, pyramidalisation autorisée
  - RANGE_NEUTRE : entrée standard, PAS de pyramidalisation (renfort réservé
    au suivi de tendance dans le manuel — "Renfort" apparaît uniquement dans
    la table trade de tendance, jamais dans la table trade spéculatif/range)

Hérite du reste de v5 (proxy TSI+cycle+structure corrigé, breakeven différé,
clôtures, amplitude réelle, Règle de Trois, Extreme Channel, maturité).
"""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, ".")
from backtest_phase2 import FEE, load_h1, resample, atr, EMA_SLOW, ATR_LEN
from proxy_v2 import add_proxy_v2_score, compute_swing_low_confirmed
from position_engine import run_position_engine
from regime_classifier import add_regime

LOCAL_DURATION = "5D"
CONTEXT_DURATION = "15D"
SWING_ORDER = 3
MIN_BORDERS = 3
RULE3_STREAK = 3
RULE3_SIZE_MULT = 0.5
MAX_TRANCHES = 3

PROFILES_V4 = {
    "FAIBLE":        {"risk_pct": 0.01, "val_close": 0.50, "conf_close": 0.00},
    "MODERE":        {"risk_pct": 0.02, "val_close": 0.25, "conf_close": 0.25},
    "AGRESSIF":      {"risk_pct": 0.03, "val_close": 0.00, "conf_close": 0.50},
    "TRES_AGRESSIF": {"risk_pct": 0.05, "val_close": 0.00, "conf_close": 0.00},
}


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = add_proxy_v2_score(df)
    df["atr"] = atr(df, ATR_LEN)
    ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    df["ctx_support"] = ema_slow - 2 * df["atr"]
    width_pct = (2 * 2 * df["atr"]) / ema_slow * 100
    df = add_regime(df, ema_slow, width_pct)

    ts = df.set_index("date")
    df["local_range"] = (ts["high"].rolling(LOCAL_DURATION).max() - ts["low"].rolling(LOCAL_DURATION).min()).values
    df["context_range"] = (ts["high"].rolling(CONTEXT_DURATION).max() - ts["low"].rolling(CONTEXT_DURATION).min()).values

    # CAUSAL depuis le traitement de la réserve P0-bis (COUVERTURE_ENSEIGNEMENTS.md
    # / PLAN.md occurrence #4) : un swing low n'entre dans le compte de bornes
    # qu'une fois confirmé (compute_swing_low_confirmed), pas au moment du creux
    # lui-même (qui dépendrait de SWING_ORDER barres futures).
    low_v = df["low"].values
    is_swing_low_confirmed = compute_swing_low_confirmed(low_v, order=SWING_ORDER)
    df["n_borders"] = pd.Series(is_swing_low_confirmed, index=ts.index).rolling(CONTEXT_DURATION).sum().values
    return df


def run_v6(df: pd.DataFrame, profile_name: str, use_regime_gate: bool = True) -> dict:
    p = PROFILES_V4[profile_name]
    df = prepare(df)
    score = df["score"].values
    atr_v = df["atr"].values
    ctx_support_v = df["ctx_support"].values
    local_range_v = df["local_range"].values
    context_range_v = df["context_range"].values
    n_borders_v = df["n_borders"].values
    regime_v = df["regime"].values
    high, low, o, c = df["high"].values, df["low"].values, df["open"].values, df["close"].values
    n = len(df)
    warmup = EMA_SLOW + 20
    long_signal = score >= 2

    state = {"last_pyramid_high": -np.inf}

    def open_tranche_fn(i, tranches, win_streak):
        long_signal_prev = score[i - 1] >= 2
        mature = (not np.isnan(n_borders_v[i - 1])) and n_borders_v[i - 1] >= MIN_BORDERS
        regime = regime_v[i - 1]
        not_excess = (regime != "EXCES") if use_regime_gate else True  # règle du manuel : ne jamais trader en Excès
        pyramiding_allowed = (regime in ("TENDANCE", "RANGE_TENDANCIEL")) if use_regime_gate else True

        valid_inputs = (
            not np.isnan(atr_v[i - 1]) and not np.isnan(ctx_support_v[i - 1])
            and not np.isnan(local_range_v[i - 1]) and local_range_v[i - 1] > 0
            and not np.isnan(context_range_v[i - 1]) and context_range_v[i - 1] > 0
        )
        is_fresh_entry = (i > warmup and len(tranches) == 0 and long_signal_prev and mature and valid_inputs and not_excess)
        is_pyramid_add = (
            i > warmup and 0 < len(tranches) < MAX_TRANCHES and long_signal_prev and valid_inputs and not_excess
            and pyramiding_allowed and high[i - 1] > state["last_pyramid_high"]
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

    max_tr = MAX_TRANCHES if use_regime_gate else MAX_TRANCHES  # limite structurelle inchangée, le gate agit dans open_tranche_fn
    raw = run_position_engine(
        n, o, high, low, c, long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=max_tr, fee=FEE,
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
        for tf_name, df in [("H4", resample(h1, "4h")), ("D1", resample(h1, "1D"))]:
            for profile in PROFILES_V4:
                res_gated = run_v6(df, profile, use_regime_gate=True)
                res_nogate = run_v6(df, profile, use_regime_gate=False)
                rows.append({"symbol": symbol, "tf": tf_name, "profile": profile,
                             "gate": "avec_regime", **res_gated})
                rows.append({"symbol": symbol, "tf": tf_name, "profile": profile,
                             "gate": "sans_regime", **res_nogate})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_v6_regime_results.csv", index=False)


if __name__ == "__main__":
    main()
