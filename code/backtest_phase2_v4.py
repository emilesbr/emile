"""
Phase 2 v4 — implémentation fidèle de tous les éléments du corpus Trading
Lessons (propriété intellectuelle de Philippe Roux), SANS conditionner leur
inclusion au résultat sur le proxy. Le proxy (confluence EMA) n'est PAS la
vraie stratégie — les résultats ci-dessous sont informatifs, pas un critère
d'acceptation/rejet. Seule l'obtention du vrai signal (export TradingView)
permettra une validation réelle.

Corrections/ajouts par rapport à la v3 :
  A. Fenêtres d'amplitude calibrées en DURÉE RÉELLE (pas en nombre de
     bougies) -> comparable entre H4 et D1. Corrige le bug de calibration
     identifié dans PHASE2_V3_ATTEMPT_REGRESSION.md.
  B. Règle de Trois (risque /2 après 3 zones gagnantes consécutives).
  C. Extreme Channel (stop = support du canal de contexte).
  D. Critères de maturité : détection de swing points réels (scipy),
     comptage des bornes testées avant d'autoriser une entrée.
  E. Pyramidalisation : suivi multi-tranches (jusqu'à 3), renfort sur
     nouveau plus haut validé pendant qu'une position est déjà ouverte.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, ".")
from backtest_phase2 import FEE, load_h1, resample, atr, EMA_FAST, EMA_MID, EMA_SLOW, ATR_LEN
from position_engine import run_position_engine, make_open_tranche_fn
from proxy_v2 import compute_swing_low_confirmed

LOCAL_DURATION = "5D"      # amplitude "range local" : fenêtre en JOURS réels (pas en bougies)
CONTEXT_DURATION = "15D"   # amplitude "contexte"
SWING_ORDER = 3             # bougies de chaque côté pour qu'un point soit un swing
MIN_BORDERS = 3             # maturité minimale (règle des "3-4 bornes", sources #9-#14)
RULE3_STREAK = 3
RULE3_SIZE_MULT = 0.5
MAX_TRANCHES = 3             # pyramidalisation : jusqu'à 3 tranches

PROFILES_V4 = {
    "FAIBLE":        {"risk_pct": 0.01, "val_close": 0.50, "conf_close": 0.00},
    "MODERE":        {"risk_pct": 0.02, "val_close": 0.25, "conf_close": 0.25},
    "AGRESSIF":      {"risk_pct": 0.03, "val_close": 0.00, "conf_close": 0.50},
    "TRES_AGRESSIF": {"risk_pct": 0.05, "val_close": 0.00, "conf_close": 0.00},
}


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    close = df["close"]
    ema_f = close.ewm(span=EMA_FAST, adjust=False).mean()
    ema_m = close.ewm(span=EMA_MID, adjust=False).mean()
    ema_s = close.ewm(span=EMA_SLOW, adjust=False).mean()
    df["score"] = (close > ema_f).astype(int) + (ema_f > ema_m).astype(int) + (ema_m > ema_s).astype(int)
    df["atr"] = atr(df, ATR_LEN)
    df["ctx_support"] = ema_s - 2 * df["atr"]

    # Amplitudes en DURÉE RÉELLE (corrige le bug de calibration v3)
    ts = df.set_index("date")
    df["local_range"] = (ts["high"].rolling(LOCAL_DURATION).max() - ts["low"].rolling(LOCAL_DURATION).min()).values
    df["context_range"] = (ts["high"].rolling(CONTEXT_DURATION).max() - ts["low"].rolling(CONTEXT_DURATION).min()).values

    # Maturité : détection de swing points (creux locaux) et comptage des
    # bornes testées dans la fenêtre "contexte". CAUSAL depuis le traitement
    # de la réserve P0-bis (COUVERTURE_ENSEIGNEMENTS.md/PLAN.md occurrence
    # #4) : un swing low n'entre dans le compte de bornes qu'une fois
    # confirmé (compute_swing_low_confirmed), pas au moment du creux
    # lui-même (qui dépendrait de SWING_ORDER barres futures).
    low_v = df["low"].values
    is_swing_low_confirmed = compute_swing_low_confirmed(low_v, order=SWING_ORDER)
    df["is_swing_low"] = is_swing_low_confirmed
    # nombre de creux (bornes) swing dans la fenêtre contexte précédente
    df["n_borders"] = pd.Series(is_swing_low_confirmed, index=ts.index).rolling(CONTEXT_DURATION).sum().values
    return df


def run_v4(df: pd.DataFrame, profile_name: str) -> dict:
    """Boucle de gestion de tranche(s) factorisée dans position_engine.py (cf.
    AUDIT_QUALITE_ET_CORRECTION_CYCLE.md, "logique dupliquée dans 3 fichiers").
    La logique spécifique à ce moteur (maturité par bornes swing, Extreme
    Channel, Règle de Trois, pyramidalisation multi-tranches) reste locale à
    ce fichier, encapsulée dans `open_tranche_fn`."""
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

    # Aucun gate additionnel dans ce moteur (contrairement à v6/v7/ut2/...) :
    # extra_gate_fn=None -> (True, True), comportement d'origine inchangé.
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
                res = run_v4(df, profile)
                rows.append({"symbol": symbol, "tf": tf_name, "profile": profile, **res})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_v4_results.csv", index=False)


if __name__ == "__main__":
    main()
