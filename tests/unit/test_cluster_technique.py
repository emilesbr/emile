"""
Tests de régression pour cluster_technique.py — cas synthétiques à vérité
terrain connue (mêmes conventions que test_fibonacci.py/test_position_engine.py :
valeurs calculées à la main, pas une propriété statistique)."""
import numpy as np
import pandas as pd
import sys

from emile.core.cluster_technique import (
    compute_ma20_rebound, compute_support_confluence, add_cluster_signal,
)

def test_ma20_rebound_hand_calculated():
    """MA20(len=3) = [NaN, NaN, 10, 9.6667, 10] pour close=[10,10,10,9,11].
    Rebond (H1) = mèche basse touche/traverse la MA MAIS clôture au-dessus :
      idx0,1 : MA NaN (warmup) -> jamais de rebond
      idx2 : low=10<=ma=10 (True) mais close=10>10 (False) -> pas de rebond
      idx3 : low=9<=ma=9.667 (True) mais close=9>9.667 (False) -> pas de rebond
      idx4 : low=9.5<=ma=10 (True) ET close=11>10 (True) -> REBOND"""
    df = pd.DataFrame({
        "close": [10, 10, 10, 9, 11],
        "low": [10, 10, 10, 9, 9.5],
        "high": [10.5, 10.5, 10.5, 9.5, 11.5],
    })
    ma20, rebound = compute_ma20_rebound(df, ma_len=3)
    assert np.allclose(ma20[2:], [10, 29 / 3, 10])
    assert list(rebound) == [False, False, False, False, True]

def test_support_confluence_hand_calculated():
    """dist_frac = (close - ctx_support) / (2*atr) = close (car ctx_support=0,
    atr=0.5 -> 2*atr=1) = [10, 5, 1, 8, 2, 0, 9].
    Seuil causal = médiane glissante (pctl_window=3, proximity_pctl=0.5) de
    dist_frac DÉCALÉ d'un cran (shift(1)) :
      shifted = [NaN, 10, 5, 1, 8, 2, 0]
      idx0-2  : <3 valeurs non-NaN dans la fenêtre -> seuil NaN -> exclu
      idx3 : fenêtre [10,5,1] -> médiane 5  | dist_frac[3]=8 <= 5 ? NON
      idx4 : fenêtre [5,1,8]  -> médiane 5  | dist_frac[4]=2 <= 5 ? OUI
      idx5 : fenêtre [1,8,2]  -> médiane 2  | dist_frac[5]=0 <= 2 ? OUI
             MAIS close[5]=0, ctx_support=0 -> close > ctx_support FAUX
             (support invalidé) -> exclu malgré la proximité
      idx6 : fenêtre [8,2,0]  -> médiane 2  | dist_frac[6]=9 <= 2 ? NON
    Attendu : [F, F, F, F, T, F, F]"""
    close = np.array([10.0, 5.0, 1.0, 8.0, 2.0, 0.0, 9.0])
    ctx_support = np.zeros(7)
    atr_v = np.full(7, 0.5)
    result = compute_support_confluence(close, ctx_support, atr_v, pctl_window=3, proximity_pctl=0.5)
    assert list(result) == [False, False, False, False, True, False, False]

def test_cluster_signal_requires_all_three_conditions():
    """Construction où le rebond MA20 (H1) et la confluence support (H2) ne
    sont VRAIS SIMULTANÉMENT qu'à idx4 (idx3 montre que la confluence
    support seule, sans rebond, ne suffit PAS -- l'ET logique est réellement
    exercé, pas un simple passe-plat d'une seule condition) :
      close = [10, 10, 10, 9, 11] (même série que le test MA20 ci-dessus,
      donc rebound = [F,F,F,F,T])
      ctx_support choisi pour donner dist_frac = [8,8,8,8,2] (atr=1 partout,
      largeur=2*atr=2, ctx_support[i] = close[i] - 2*dist_frac[i]) :
        -> ctx_support = [-6,-6,-6,-7,7]
      support_confluence (pctl_window=3, proximity_pctl=0.5, calcul identique
      au test précédent) = [F,F,F,T,T] (idx3 ET idx4 franchissent le seuil,
      mais SEUL idx4 a aussi rebound=True)
    regime = TENDANCE partout -> cluster_signal attendu = rebound & support
      = [F,F,F,F,T]"""
    df = pd.DataFrame({
        "close": [10.0, 10.0, 10.0, 9.0, 11.0],
        "low": [10.0, 10.0, 10.0, 9.0, 9.5],
        "high": [10.5, 10.5, 10.5, 9.5, 11.5],
        "atr": [1.0, 1.0, 1.0, 1.0, 1.0],
        "ctx_support": [-6.0, -6.0, -6.0, -7.0, 7.0],
        "regime": ["TENDANCE"] * 5,
    })
    out = add_cluster_signal(df, ma_len=3, pctl_window=3, proximity_pctl=0.5)
    assert list(out["ma20_rebound"]) == [False, False, False, False, True]
    assert list(out["support_confluence"]) == [False, False, False, True, True]
    # idx3 : support proche MAIS pas de rebond -> pas de cluster (ET réellement exercé)
    assert list(out["cluster_signal"]) == [False, False, False, False, True]

def test_cluster_signal_false_when_trend_not_established():
    """Même configuration que le test précédent (rebond ET confluence
    support toutes deux vraies à idx4), mais regime[4] != TENDANCE : H3
    (flux tendanciel établi) doit à lui seul suffire à invalider le cluster,
    même quand les deux autres composants sont réunis."""
    df = pd.DataFrame({
        "close": [10.0, 10.0, 10.0, 9.0, 11.0],
        "low": [10.0, 10.0, 10.0, 9.0, 9.5],
        "high": [10.5, 10.5, 10.5, 9.5, 11.5],
        "atr": [1.0, 1.0, 1.0, 1.0, 1.0],
        "ctx_support": [-6.0, -6.0, -6.0, -7.0, 7.0],
        "regime": ["TENDANCE", "TENDANCE", "TENDANCE", "TENDANCE", "RANGE_NEUTRE"],
    })
    out = add_cluster_signal(df, ma_len=3, pctl_window=3, proximity_pctl=0.5)
    assert not out["cluster_signal"].iloc[4]
    assert out["ma20_rebound"].iloc[4] and out["support_confluence"].iloc[4]  # les 2 autres composants restent vrais

def test_add_cluster_signal_standalone_computes_defaults_when_columns_missing():
    """Sans 'atr'/'ctx_support'/'regime' fournis (usage standalone), la
    fonction doit les calculer elle-même (mêmes conventions que
    backtest_phase2_v7.py::prepare) sans planter, et exposer les colonnes
    attendues, sur une série assez longue pour dépasser tous les warmups
    (EMA55, ATR14, régime PCTL_WINDOW=250 -> on prend 400 bougies)."""
    rng = np.random.default_rng(42)
    n = 400
    steps = rng.normal(loc=0.05, scale=1.0, size=n)  # dérive légèrement haussière
    close = 100 + np.cumsum(steps)
    high = close + rng.uniform(0.1, 1.0, size=n)
    low = close - rng.uniform(0.1, 1.0, size=n)
    dates = pd.date_range("2024-01-01", periods=n, freq="4h")
    df = pd.DataFrame({"date": dates, "close": close, "high": high, "low": low})
    out = add_cluster_signal(df)
    expected_cols = {"ma20", "ma20_rebound", "support_confluence", "trend_established",
                      "cluster_signal", "atr", "ctx_support", "regime"}
    assert expected_cols <= set(out.columns)
    assert out["cluster_signal"].dtype == bool
    # Pas de NaN dans le signal final (les composants NaN pendant le warmup
    # doivent être neutralisés en False, jamais propagés en NaN dans un bool)
    assert not out["cluster_signal"].isna().any()

def test_momentum_filter_is_optional_and_only_narrows_the_signal():
    """H4 : le filtre de momentum est optionnel et ne fait QUE resserrer le
    signal (jamais l'élargir) -- cluster_signal(momentum=True) doit être un
    sous-ensemble strict ou égal de cluster_signal(momentum=False)."""
    rng = np.random.default_rng(7)
    n = 400
    steps = rng.normal(loc=0.05, scale=1.0, size=n)
    close = 100 + np.cumsum(steps)
    high = close + rng.uniform(0.1, 1.0, size=n)
    low = close - rng.uniform(0.1, 1.0, size=n)
    dates = pd.date_range("2024-01-01", periods=n, freq="4h")
    df = pd.DataFrame({"date": dates, "close": close, "high": high, "low": low})
    base = add_cluster_signal(df, use_momentum_filter=False)
    with_mom = add_cluster_signal(df, use_momentum_filter=True)
    assert "momentum_favorable" in with_mom.columns
    assert "momentum_favorable" not in base.columns
    # sous-ensemble : partout où with_mom est True, base doit aussi être True
    assert (~with_mom["cluster_signal"] | base["cluster_signal"]).all()
    assert with_mom["cluster_signal"].sum() <= base["cluster_signal"].sum()

if __name__ == "__main__":
    test_ma20_rebound_hand_calculated()
    test_support_confluence_hand_calculated()
    test_cluster_signal_requires_all_three_conditions()
    test_cluster_signal_false_when_trend_not_established()
    test_add_cluster_signal_standalone_computes_defaults_when_columns_missing()
    test_momentum_filter_is_optional_and_only_narrows_the_signal()
    print("Tous les tests cluster_technique passent (6/6).")
