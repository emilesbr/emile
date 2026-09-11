"""
Phase 2 v5 — proxy v2 (TSI + cycle Hilbert + creux ascendants) branché sur
le moteur de risque complet de la v4 (breakeven différé, clôtures, amplitude
réelle en durée, Règle de Trois, Extreme Channel, maturité par bornes
swing, pyramidalisation multi-tranches).

Rappel : les résultats sont informatifs, pas un critère d'acceptation —
seul le vrai signal PRO Framework/Momentum permettra une validation réelle.
"""
import pandas as pd
import numpy as np
import sys

from emile.backtests.backtest_phase2 import FEE, load_h1, resample, atr, EMA_SLOW, ATR_LEN
from emile.core.proxy_v2 import add_proxy_v2_score, compute_swing_low_confirmed
from emile.core.position_engine import run_position_engine, make_open_tranche_fn

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
    df = add_proxy_v2_score(df)  # remplace l'ancienne confluence EMA
    df["atr"] = atr(df, ATR_LEN)
    ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    df["ctx_support"] = ema_slow - 2 * df["atr"]

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

def run_v5(df: pd.DataFrame, profile_name: str) -> dict:
    """Identique à run_v4 (backtest_phase2_v4.py) : seule la source du score
    d'entrée change (proxy_v2 au lieu de la confluence EMA). Boucle de
    gestion de tranche(s) factorisée dans position_engine.py (cf.
    AUDIT_QUALITE_ET_CORRECTION_CYCLE.md, "logique dupliquée dans 3 fichiers")."""
    p = PROFILES_V4[profile_name]
    df = prepare(df)
    score = df["score"].values
    atr_v = df["atr"].values
    ctx_support_v = df["ctx_support"].values
    local_range_v = df["local_range"].values
    context_range_v = df["context_range"].values
    n_borders_v = df["n_borders"].values
    high, low, o, c = df["high"].values, df["low"].values, df["open"].values, df["close"].values
    n = len(df)
    warmup = EMA_SLOW + 20
    long_signal = score >= 2

    state = {"last_pyramid_high": -np.inf}

    # Aucun gate additionnel (comme v4) : extra_gate_fn=None -> (True, True).
    open_tranche_fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v, high, o, score,
        warmup, MIN_BORDERS, MAX_TRANCHES, RULE3_STREAK, RULE3_SIZE_MULT, p["risk_pct"], state,
    )

    raw = run_position_engine(
        n, o, high, low, c, long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=MAX_TRANCHES, fee=FEE,
    )
    return {
        "n_trades": raw["n_trades"],
        "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"],
        "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
    }

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        for tf_name, df in [("H4", resample(h1, "4h")), ("D1", resample(h1, "1D"))]:
            for profile in PROFILES_V4:
                res = run_v5(df, profile)
                rows.append({"symbol": symbol, "tf": tf_name, "profile": profile, **res})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_v5_results.csv", index=False)

if __name__ == "__main__":
    main()
