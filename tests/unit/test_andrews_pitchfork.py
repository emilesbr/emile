"""
Tests pour andrews_pitchfork.py (backlog PLAN.md item 7). Écrit
directement (agent délégué interrompu par un rate-limit juste après avoir
fini le module). `pitchfork_lines` est une fonction purement géométrique
(cf. docstring du module) -- testable isolément avec des pivots choisis à
la main, sans passer par la détection causale de swings.
"""
import numpy as np
import pandas as pd
import sys

from emile.core.andrews_pitchfork import pitchfork_lines, compute_andrews_pitchfork_causal, add_andrews_pitchfork_columns

ORDER = 3

def test_pitchfork_lines_hand_computed():
    """P0=(0, 100), P1=(10, 150), P2=(20, 130).
    mid = ((10+20)/2, (150+130)/2) = (15, 140)
    pente médiane = (140-100)/(15-0) = 40/15 = 8/3
    median(t)      = 100 + (8/3)*(t-0)
    parallel_p1(t) = 150 + (8/3)*(t-10)
    parallel_p2(t) = 130 + (8/3)*(t-20)
    Vérifié à t=30 (au-delà de tous les pivots, extrapolation)."""
    p0, p1, p2 = (0, 100.0), (10, 150.0), (20, 130.0)
    t = 30
    median, par1, par2 = pitchfork_lines(p0, p1, p2, t)
    slope = 8.0 / 3.0
    assert np.isclose(median, 100.0 + slope * 30), median
    assert np.isclose(par1, 150.0 + slope * (30 - 10)), par1
    assert np.isclose(par2, 130.0 + slope * (30 - 20)), par2
    # Les 2 parallèles doivent être... parallèles (même pente que la médiane)
    median_a, par1_a, par2_a = pitchfork_lines(p0, p1, p2, 5)
    median_b, par1_b, par2_b = pitchfork_lines(p0, p1, p2, 15)
    assert np.isclose((par1_b - par1_a) / 10, slope)
    assert np.isclose((par2_b - par2_a) / 10, slope)

def test_pitchfork_lines_passes_through_pivots_exactly():
    """La médiane doit passer exactement par P0 (t=idx0), parallel_p1 par
    P1 (t=idx1), parallel_p2 par P2 (t=idx2) -- vérification directe de la
    construction géométrique, pas seulement de la pente."""
    p0, p1, p2 = (0, 100.0), (10, 150.0), (20, 130.0)
    median0, _, _ = pitchfork_lines(p0, p1, p2, 0)
    _, par1_at_10, _ = pitchfork_lines(p0, p1, p2, 10)
    _, _, par2_at_20 = pitchfork_lines(p0, p1, p2, 20)
    assert np.isclose(median0, 100.0)
    assert np.isclose(par1_at_10, 150.0)
    assert np.isclose(par2_at_20, 130.0)

def _pivot_series(pivots, order=ORDER):
    """`pivots` = [(idx, prix, kind)], kind in {"low","high"}, alternance
    stricte imposée par construction (comme H2 du module)."""
    n = max(i for i, _, _ in pivots) + order + 10
    low_v = 1000.0 + np.arange(n) * 0.01
    high_v = 500.0 + np.arange(n) * 0.01
    for idx, price, kind in pivots:
        if kind == "low":
            low_v[idx] = price
        else:
            high_v[idx] = price
    return pd.DataFrame({"low": low_v, "high": high_v})

def test_causal_pivot_selection_matches_hand_computation():
    """3 pivots alternés low/high/low imposés -> une fois les 3 confirmés,
    la fourchette causale doit coïncider avec pitchfork_lines appelé
    directement sur ces 3 pivots (aux index RÉELS, pas décalés).

    Note de construction (piège rencontré et corrigé en écrivant ce test) :
    `argrelextrema` produit un swing low "artefact de bord" à l'index 0 de
    toute série tronquée (comportement connu, cf. warmup des autres
    composants du projet). Sans un pivot HIGH précoce pour alterner et
    évacuer cet artefact (règle H2, alternance stricte), il resterait
    coincé comme P0 à la place du vrai premier pivot voulu -- comportement
    attendu et sans conséquence sur données réelles (warmup ordinaire,
    s'évacue après quelques pivots réels), mais qu'il faut neutraliser
    explicitement dans un test synthétique aussi court que celui-ci."""
    warmup_high = (5, 900.0, "high")  # évacue l'artefact de bord avant les vrais pivots
    p0 = (10, 90.0, "low")
    p1 = (20, 700.0, "high")   # doit dominer la rampe "high" locale (~500.1-500.2)
    p2 = (30, 80.0, "low")
    df = _pivot_series([warmup_high, p0, p1, p2])
    median, par1, par2 = compute_andrews_pitchfork_causal(df, order=ORDER)

    t = 30 + ORDER + 2  # bien après confirmation du 3e pivot (idx=30, confirmé à 33)
    expected_median, expected_par1, expected_par2 = pitchfork_lines(
        (p0[0], p0[1]), (p1[0], p1[1]), (p2[0], p2[1]), t
    )
    assert not np.isnan(median[t])
    assert np.isclose(median[t], expected_median)
    assert np.isclose(par1[t], expected_par1)
    assert np.isclose(par2[t], expected_par2)

def test_add_andrews_pitchfork_columns_matches():
    p0 = (10, 90.0, "low")
    p1 = (20, 700.0, "high")
    p2 = (30, 80.0, "low")
    df = _pivot_series([p0, p1, p2])
    out = add_andrews_pitchfork_columns(df, order=ORDER)
    median, par1, par2 = compute_andrews_pitchfork_causal(df, order=ORDER)
    assert np.allclose(out["pitchfork_median"].values, median, equal_nan=True)
    assert np.allclose(out["pitchfork_p1"].values, par1, equal_nan=True)
    assert np.allclose(out["pitchfork_p2"].values, par2, equal_nan=True)

def test_causal_no_future_leakage():
    p0 = (10, 90.0, "low")
    p1 = (20, 700.0, "high")
    p2 = (30, 80.0, "low")
    df = _pivot_series([p0, p1, p2])
    median_full, _, _ = compute_andrews_pitchfork_causal(df, order=ORDER)
    t = 30 + ORDER + 2
    truncated = df.iloc[: t + 1].reset_index(drop=True)
    median_trunc, _, _ = compute_andrews_pitchfork_causal(truncated, order=ORDER)
    assert np.isclose(median_trunc[-1], median_full[t]), (
        "la fourchette à l'instant t a changé selon que des barres futures "
        "sont présentes ou non -- régression causale"
    )

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} tests passés")
