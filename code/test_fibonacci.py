"""
Tests de régression pour fibonacci.py — cas synthétiques à vérité terrain
connue (swing haut/bas construits à la main, retracement calculé à la main),
dans le même esprit que test_position_engine.py (cas exacts, pas une
propriété statistique comme test_proxy_v2.py).

Données synthétiques communes à plusieurs tests : une baisse construite pour
former un swing low PROPRE à 90 (order=3 des deux côtés, strictement
monotone), suivie d'une hausse formant un swing high PROPRE à 190
(amplitude du mouvement = 100, valeur ronde pour des pourcentages de
retracement faciles à vérifier à la main), puis une baisse traversant des
paliers de retracement connus :
  190 -> 180  (10 % de retracement,   190-0.10*100=180)
  190 -> 167  (23 % de retracement,   190-0.23*100=167)
  190 -> 152  (38 % de retracement,   190-0.38*100=152)
  190 -> 140  (50 % de retracement,   190-0.50*100=140)
  190 -> 128.2 (61,8 % de retracement, 190-0.618*100=128.2)
  190 -> 120  (70 % de retracement,   190-0.70*100=120)
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from fibonacci import (
    compute_swing_highs_lows, compute_retracement, classify_retracement,
    add_fibonacci_columns, FAVORABLE_MIN, FAVORABLE_OPTIMAL_MAX, FAVORABLE_MAX,
)


def _synthetic_swing_df():
    down_to_low = [110, 108, 106, 104, 102, 100, 95, 90]   # swing low = 90, dernier élément (idx 7)
    up_to_high = [95, 105, 120, 140, 165, 190]             # swing high = 190, dernier élément (idx 13)
    # amplitude du mouvement = 190 - 90 = 100 -> paliers de retracement ronds
    decline_checkpoints = [180, 167, 152, 140, 128.2, 120, 100]
    closes = down_to_low + up_to_high + decline_checkpoints
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    lows[7] = 90     # force la valeur exacte du swing low attendu
    highs[13] = 190  # force la valeur exacte du swing high attendu
    return pd.DataFrame({"high": highs, "low": lows, "close": closes})


def test_swing_detection_finds_hand_placed_low_and_high():
    """Le swing low construit à la main (90, idx 7) et le swing high construit
    à la main (190, idx 13) doivent être détectés par argrelextrema — même
    détection que proxy_v2.py::compute_ascending_lows (order=3)."""
    df = _synthetic_swing_df()
    is_high, is_low = compute_swing_highs_lows(df)
    assert is_low[7], "le swing low construit à la main (90, idx 7) devrait être détecté"
    assert is_high[13], "le swing high construit à la main (190, idx 13) devrait être détecté"
    # Le creux à l'intérieur de la montée (idx 8-12) ne doit PAS être un swing low
    # (la série y est strictement croissante, pas d'extremum local)
    assert not any(is_low[8:13]), "aucun swing low ne devrait apparaître pendant la hausse monotone"


def test_retracement_matches_hand_calculated_percentages():
    """Vérifie, palier par palier, que compute_retracement retrouve le %
    calculé à la main : retracement = (high - close) / (high - low)."""
    df = _synthetic_swing_df()
    ret = compute_retracement(df)

    # idx 13 = le swing high lui-même -> 0 % de retracement
    assert np.isclose(ret[13], 0.0, atol=1e-9)
    # idx 14 = 180 -> (190-180)/100 = 10 %
    assert np.isclose(ret[14], 0.10, atol=1e-9)
    # idx 15 = 167 -> 23 % (seuil minimal de validation, source #13)
    assert np.isclose(ret[15], 0.23, atol=1e-9)
    # idx 16 = 152 -> 38 % (niveau "standard et optimal", source #13)
    assert np.isclose(ret[16], 0.38, atol=1e-9)
    # idx 17 = 140 -> 50 % ("exceptionnel", source #13 ; borne haute du cluster, source #10)
    assert np.isclose(ret[17], 0.50, atol=1e-9)
    # idx 18 = 128.2 -> 61,8 % (niveau d'intervention du pullback, source #11 ;
    # seuil de tolérance maximum, source #10)
    assert np.isclose(ret[18], 0.618, atol=1e-6)
    # idx 19 = 120 -> 70 % (au-delà du seuil de tolérance -> Red Flag, source #10)
    assert np.isclose(ret[19], 0.70, atol=1e-9)


def test_no_retracement_before_first_confirmed_up_move():
    """Avant que le premier mouvement complet (swing low PUIS swing high
    postérieur) ne soit confirmé, le retracement doit rester NaN — ni
    pendant la baisse initiale (avant même le swing low), ni pendant la
    remontée qui suit le swing low mais n'a pas encore formé de swing high."""
    df = _synthetic_swing_df()
    ret = compute_retracement(df)
    # Baisse initiale (idx 0-7) : aucun mouvement complet encore identifiable
    assert np.all(np.isnan(ret[0:8]))
    # Remontée en cours (idx 8-12) : swing low connu mais pas encore de swing high après lui
    assert np.all(np.isnan(ret[8:13]))


def test_classify_retracement_boundaries_hand_calculated():
    """Teste les bornes de classification indépendamment du calcul de prix
    (pour ne pas mêler une éventuelle imprécision flottante du calcul de
    retracement à la logique de classification elle-même) : valeurs
    scalaires connues, comparées aux constantes FAVORABLE_MIN/
    FAVORABLE_OPTIMAL_MAX/FAVORABLE_MAX du module."""
    values = np.array([0.10, FAVORABLE_MIN, 0.38, FAVORABLE_OPTIMAL_MAX,
                        FAVORABLE_MAX, 0.70, np.nan])
    favorable, optimal = classify_retracement(values)

    # 10 % : trop peu profond -> défavorable (simple pause, pas un pullback, source #13)
    assert not favorable[0] and not optimal[0]
    # 23 % (FAVORABLE_MIN) : borne basse incluse -> favorable ET optimal
    assert favorable[1] and optimal[1]
    # 38 % : "standard et optimal" (source #13) -> favorable ET optimal
    assert favorable[2] and optimal[2]
    # 50 % (FAVORABLE_OPTIMAL_MAX) : borne haute de la sous-zone optimale, incluse
    assert favorable[3] and optimal[3]
    # 61,8 % (FAVORABLE_MAX) : favorable (tolérance maximum, source #10/#11)
    # mais plus dans la sous-zone optimale
    assert favorable[4] and not optimal[4]
    # 70 % : au-delà du seuil de tolérance -> défavorable (Red Flag, source #10)
    assert not favorable[5] and not optimal[5]
    # NaN (pas de mouvement confirmé) -> ni favorable ni optimal
    assert not favorable[6] and not optimal[6]


def test_add_fibonacci_columns_integration():
    """Vérifie que add_fibonacci_columns ajoute les 3 colonnes attendues et
    qu'elles sont cohérentes avec compute_retracement/classify_retracement
    appelés séparément (pas de logique dupliquée/divergente)."""
    df = _synthetic_swing_df()
    out = add_fibonacci_columns(df)
    assert {"fib_retracement_pct", "fib_favorable", "fib_optimal"} <= set(out.columns)

    ret_direct = compute_retracement(df)
    fav_direct, opt_direct = classify_retracement(ret_direct)
    assert np.allclose(out["fib_retracement_pct"].values, ret_direct, equal_nan=True)
    assert np.array_equal(out["fib_favorable"].values, fav_direct)
    assert np.array_equal(out["fib_optimal"].values, opt_direct)
    # idx 16 (152, 38 % de retracement) doit être marqué favorable dans le dataframe
    assert bool(out["fib_favorable"].iloc[16])


if __name__ == "__main__":
    test_swing_detection_finds_hand_placed_low_and_high()
    test_retracement_matches_hand_calculated_percentages()
    test_no_retracement_before_first_confirmed_up_move()
    test_classify_retracement_boundaries_hand_calculated()
    test_add_fibonacci_columns_integration()
    print("Tous les tests fibonacci passent (5/5).")
