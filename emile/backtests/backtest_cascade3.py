"""
Test de la vraie cascade à 3 niveaux décrite par le corpus Trading Lessons
(sources #15/#16) : Référence (Daily) -> Contexte (H4) -> Exécution (H1),
"on descend de deux niveaux sous la référence".

Contrairement à la Phase 1 (H1 testé SEUL, avec au mieux un contexte H4
à un niveau), ici le H1 n'est JAMAIS une stratégie autonome : il ne sert
qu'à exécuter un signal déjà validé sur Daily ET H4 simultanément.

Risk management : version corrigée de la Phase 2 (breakeven différé à la
Confirmation, pas à la Validation - cf. PHASE2_CORRECTION_BREAKEVEN.md).
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

from emile.backtests.backtest_phase2 import PROFILES, run_backtest_mm, load_h1, resample, add_score

PERIODS_PER_YEAR_H1 = 365 * 24

def attach_context(df_low: pd.DataFrame, df_high_scored: pd.DataFrame, high_duration: pd.Timedelta) -> np.ndarray:
    high = df_high_scored[["date", "score"]].copy()
    high["available_at"] = high["date"] + high_duration
    high = high.sort_values("available_at")
    merged = pd.merge_asof(
        df_low[["date"]].sort_values("date"), high, left_on="date", right_on="available_at", direction="backward"
    )
    return merged["score"].values

def run_triple_cascade(h1: pd.DataFrame, h4_scored: pd.DataFrame, d1_scored: pd.DataFrame, profile_name: str) -> dict:
    h1_scored = add_score(h1)
    ctx_h4 = attach_context(h1_scored, h4_scored, pd.Timedelta(hours=4))
    ctx_d1 = attach_context(h1_scored, d1_scored, pd.Timedelta(days=1))

    # Triple gate : H1 (exécution) + H4 (contexte) + Daily (référence) tous alignés haussiers
    triple_signal = (h1_scored["score"].values >= 2) & (ctx_h4 >= 2) & (ctx_d1 >= 2)
    return run_backtest_mm(h1_scored, profile_name, external_signal=triple_signal), int(triple_signal.sum())

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1_raw = load_h1(symbol)
        h4 = resample(h1_raw, "4h")
        d1 = resample(h1_raw, "1D")
        h4_scored = add_score(h4)
        d1_scored = add_score(d1)

        for profile in PROFILES:
            res, n_aligned_bars = run_triple_cascade(h1_raw, h4_scored, d1_scored, profile)
            rows.append({"symbol": symbol, "profile": profile, "n_aligned_bars": n_aligned_bars, **res})

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print("=" * 110)
    print("CASCADE 3 NIVEAUX : Daily (référence) -> H4 (contexte) -> H1 (exécution)")
    print("Risk management corrigé (breakeven différé à la Confirmation)")
    print("=" * 110)
    print(result.to_string(index=False))
    result.to_csv("cascade3_h1execution_results.csv", index=False)

if __name__ == "__main__":
    main()
