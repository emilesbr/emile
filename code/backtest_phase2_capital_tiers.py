"""
Phase 2 — moteur v7 paramétré par un CAPITAL DE DÉPART ABSOLU (en €) plutôt
que par un `risk_pct` fixe par profil (RULES_EXTRACTION.md §5, "Paliers de
capital"). Duplique `backtest_phase2_v7.py` (lu, jamais modifié — cf.
consigne de coordination avec les agents en parallèle sur ce dépôt) et
n'en change qu'UNE chose : le `risk_pct` utilisé dans `open_tranche_fn` vient
de `capital_tiers.effective_sizing()` au lieu de `PROFILES_V4[profile_name]
["risk_pct"]` brut. Tout le reste (signal, régime, gate MTF, moteur de
position, table Validation/Confirmation/Limite du profil) est identique à
v7 — cf. `code/capital_tiers.py` pour la règle exacte extraite et les
hypothèses d'implémentation (multiplicateur/plafond par palier, parité €/$).

Limite honnête à ne pas perdre de vue (cf. COUVERTURE_ENSEIGNEMENTS.md) :
le moteur de position raisonne en FRACTION d'equity (comme tout le reste du
projet, cf. `position_engine.py`), pas en montants absolus. Le capital de
départ absolu n'a donc, dans CE backtest, qu'un seul canal d'effet : le
choix du `risk_pct` effectif via le palier. Il ne modélise PAS d'effets qui
dépendraient réellement de la taille absolue du capital (liquidité,
taille de tick minimale, impact de marché, frais fixes) — hors périmètre de
ce projet de backtest personnel, comme documenté depuis le début.
"""
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
import sys
sys.path.insert(0, ".")
from backtest_phase2 import FEE, load_h1, resample, atr, EMA_SLOW, ATR_LEN
from proxy_v2 import add_proxy_v2_score
from position_engine import run_position_engine
from regime_classifier import add_regime
from capital_tiers import effective_sizing

LOCAL_DURATION = "5D"
CONTEXT_DURATION = "15D"
SWING_ORDER = 3
MIN_BORDERS = 3
RULE3_STREAK = 3
RULE3_SIZE_MULT = 0.5
MAX_TRANCHES = 3

# Table Validation/Confirmation identique à v7 (RULES_EXTRACTION.md §3) —
# seul risk_pct est retiré d'ici : il vient désormais du palier de capital.
PROFILES_V4 = {
    "FAIBLE":        {"risk_pct": 0.01, "val_close": 0.50, "conf_close": 0.00},
    "MODERE":        {"risk_pct": 0.02, "val_close": 0.25, "conf_close": 0.25},
    "AGRESSIF":      {"risk_pct": 0.03, "val_close": 0.00, "conf_close": 0.50},
    "TRES_AGRESSIF": {"risk_pct": 0.05, "val_close": 0.00, "conf_close": 0.00},
}


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Identique à `backtest_phase2_v7.prepare` (dupliqué, pas importé, pour
    que ce fichier reste autonome vis-à-vis de futures modifications de v7
    par d'autres agents en parallèle sur cette branche)."""
    df = add_proxy_v2_score(df)
    df["atr"] = atr(df, ATR_LEN)
    ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    df["ctx_support"] = ema_slow - 2 * df["atr"]
    width_pct = (2 * 2 * df["atr"]) / ema_slow * 100
    df = add_regime(df, ema_slow, width_pct)

    ts = df.set_index("date")
    df["local_range"] = (ts["high"].rolling(LOCAL_DURATION).max() - ts["low"].rolling(LOCAL_DURATION).min()).values
    df["context_range"] = (ts["high"].rolling(CONTEXT_DURATION).max() - ts["low"].rolling(CONTEXT_DURATION).min()).values

    low_v = df["low"].values
    swing_low_idx = argrelextrema(low_v, np.less_equal, order=SWING_ORDER)[0]
    is_swing_low = np.zeros(len(df), dtype=bool)
    is_swing_low[swing_low_idx] = True
    df["n_borders"] = pd.Series(is_swing_low, index=ts.index).rolling(CONTEXT_DURATION).sum().values
    return df


def attach_higher_context(df_low: pd.DataFrame, df_high: pd.DataFrame, high_duration: pd.Timedelta) -> tuple:
    """Identique à `backtest_phase2_v7.attach_higher_context`."""
    high = df_high[["date", "score", "regime", "ctx_support"]].copy()
    high["available_at"] = high["date"] + high_duration
    high = high.sort_values("available_at")
    merged = pd.merge_asof(
        df_low[["date"]].sort_values("date"), high, left_on="date", right_on="available_at", direction="backward"
    )
    return merged["score"].values, merged["regime"].values, merged["ctx_support"].values


def run_capital_tiers(h4: pd.DataFrame, d1: pd.DataFrame, capital_eur: float, profile_name: str,
                       use_mtf_gate: bool = True, use_mtf_stop: bool = False) -> dict:
    """Comme `backtest_phase2_v7.run_v7`, sauf que `risk_pct` n'est plus lu
    directement dans PROFILES_V4 : il vient de `effective_sizing(capital_eur,
    profile_name, ...)`, modulé par le palier de capital (cf. capital_tiers.py).
    `MAX_TRANCHES` reste celui du moteur (non modulé par palier, cf. docstring
    de capital_tiers.py)."""
    p = PROFILES_V4[profile_name]
    sizing = effective_sizing(capital_eur, profile_name, PROFILES_V4, MAX_TRANCHES)

    h4 = prepare(h4)
    d1 = prepare(d1)
    ctx_score, ctx_regime, ctx_support_d1 = attach_higher_context(h4, d1, pd.Timedelta(days=1))

    score = h4["score"].values
    atr_v = h4["atr"].values
    ctx_support_v = ctx_support_d1 if use_mtf_stop else h4["ctx_support"].values
    local_range_v = h4["local_range"].values
    context_range_v = h4["context_range"].values
    n_borders_v = h4["n_borders"].values
    high, low, o, c = h4["high"].values, h4["low"].values, h4["open"].values, h4["close"].values
    n = len(h4)
    warmup = EMA_SLOW + 20
    long_signal = score >= 2

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
        risk_pct = sizing.risk_pct  # <-- seule différence de fond avec run_v7
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
        "capital_eur": capital_eur, "tier": sizing.tier,
        "risk_pct_base": sizing.base_risk_pct, "risk_pct_effectif": sizing.risk_pct,
        "n_trades": raw["n_trades"], "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"], "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
        "final_equity_eur": round(capital_eur * raw["final_equity"], 2),
    }


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    # Un montant représentatif par palier (RULES_EXTRACTION.md §5) :
    capitaux_eur = [5_000, 50_000, 500_000]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        for capital_eur in capitaux_eur:
            for profile in PROFILES_V4:
                res = run_capital_tiers(h4.copy(), d1.copy(), capital_eur, profile,
                                         use_mtf_gate=True, use_mtf_stop=False)
                rows.append({"symbol": symbol, "profile": profile, **res})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_capital_tiers_results.csv", index=False)


if __name__ == "__main__":
    main()
