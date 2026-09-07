"""
Phase 2 v7 — première fusion réelle entre le moteur complet (v6 : proxy
TSI+cycle+structure, régime, risk management corrigé) ET la cascade
multi-timeframe (jamais faite jusqu'ici : v4/v5/v6 tournaient chacun sur UN
SEUL timeframe isolé, malgré le nom trompeur "Extreme Channel" qui n'était
qu'une bande de volatilité locale, PAS un vrai canal de l'UT supérieure).

Règle appliquée (cohérente avec les 7 sources du corpus sur le sujet) :
  - Exécution sur H4
  - Contexte/référence sur D1 : un signal H4 n'est validé que si le score
    proxy_v2 du D1 (dernière bougie D1 ENTIÈREMENT CLÔTURÉE, sans lookahead)
    est ÉGALEMENT >= 2. Le régime D1 doit aussi être différent d'EXCES.
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


def attach_higher_context(df_low: pd.DataFrame, df_high: pd.DataFrame, high_duration: pd.Timedelta) -> tuple:
    """Jointure sans lookahead : pour chaque bougie H4, le score, le régime ET
    le `ctx_support` (niveau de prix absolu, "Extreme Channel") de la DERNIÈRE
    bougie D1 entièrement close à cet instant. Même logique temporelle pour
    les trois colonnes (aucune n'utilise une bougie D1 pas encore close)."""
    high = df_high[["date", "score", "regime", "ctx_support"]].copy()
    high["available_at"] = high["date"] + high_duration
    high = high.sort_values("available_at")
    merged = pd.merge_asof(
        df_low[["date"]].sort_values("date"), high, left_on="date", right_on="available_at", direction="backward"
    )
    return merged["score"].values, merged["regime"].values, merged["ctx_support"].values


def run_v7(h4: pd.DataFrame, d1: pd.DataFrame, profile_name: str, use_mtf_gate: bool = True,
           use_mtf_stop: bool = False, record_trace: bool = False, reverse_at_limit: bool = False) -> dict:
    """`use_mtf_stop` (défaut False, préserve le comportement historique de
    v7) : si True, le stop ("Extreme Channel") utilisé à l'entrée est celui
    calculé sur le VRAI D1 (`ctx_support` D1, transmis sans lookahead par
    `attach_higher_context`) plutôt que le `ctx_support` recalculé sur le H4
    lui-même. Les deux sont des niveaux de prix absolus (pas des distances),
    donc directement substituables dans le calcul de `stop_pct` ci-dessous.

    `reverse_at_limit` (défaut False, préserve le comportement historique de
    v7, même principe que `use_mtf_stop`) : transmis tel quel à
    `run_position_engine` -- si True, une tranche qui se clôture à la Limite
    ouvre en plus une jambe short "+Reverse" (RULES_EXTRACTION.md §3, profil
    Très Agressif uniquement au sens du manuel, mais le paramètre est
    utilisable avec n'importe quel profil ici -- c'est l'appelant qui décide
    à qui l'appliquer, cf. hypothèse H-Reverse-Range dans
    `position_engine.py`)."""
    p = PROFILES_V4[profile_name]
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
        # Validation croisée D1 : le contexte (référence) doit être aligné,
        # et ni le H4 ni le D1 ne doivent être en régime EXCES
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

    # NB : la sortie de signal (flip) doit aussi respecter le gate MTF pour
    # être cohérente -> on passe le signal déjà gated à run_position_engine
    gated_long_signal = np.array([
        (score[i] >= 2) and ((ctx_score[i] >= 2) if use_mtf_gate else True)
        and ((ctx_regime[i] != "EXCES") if use_mtf_gate else True)
        for i in range(n)
    ])

    raw = run_position_engine(
        n, o, high, low, c, gated_long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=MAX_TRANCHES, fee=FEE,
        record_trace=record_trace, reverse_at_limit=reverse_at_limit,
    )
    result = {
        "n_trades": raw["n_trades"], "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"], "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
    }
    if record_trace:
        # dates H4 (une par bougie, même longueur que o/high/low/c) -- pour
        # que l'appelant (funding_rate_exact.py) puisse aligner chaque
        # instantané de trace["snapshots"] sur un timestamp réel et donc
        # sur les vrais événements de funding (toutes les 8h).
        result["trace"] = raw["trace"]
        result["dates"] = h4["date"].values
        result["final_equity"] = raw["final_equity"]
    return result


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        for profile in PROFILES_V4:
            res_mtf = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False)
            res_solo = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=False, use_mtf_stop=False)
            res_mtf_stopd1 = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=True)
            rows.append({"symbol": symbol, "profile": profile, "gate": "H4_valide_par_D1", "stop": "H4_meme_UT", **res_mtf})
            rows.append({"symbol": symbol, "profile": profile, "gate": "H4_seul (=v6)", "stop": "H4_meme_UT", **res_solo})
            rows.append({"symbol": symbol, "profile": profile, "gate": "H4_valide_par_D1", "stop": "D1_reel", **res_mtf_stopd1})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_v7_mtf_results.csv", index=False)


if __name__ == "__main__":
    main()
