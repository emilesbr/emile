"""
Tests pour manual_trend_channel.py (canal Supports->Apex->Tangente,
backlog PLAN.md item 7). Écrit directement (agent délégué interrompu par
un rate-limit après avoir fini le module lui-même, sans le temps
d'écrire ses tests) -- cas calculé à la main pour vérifier la géométrie
exacte, pas seulement "ça tourne sans erreur".
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from manual_trend_channel import compute_manual_trend_channel, add_manual_trend_channel_columns

ORDER = 3


def _channel_series(low1_idx, low1_price, low2_idx, low2_price, apex_idx, apex_price, order=ORDER):
    n = low2_idx + order + 10
    low_v = 1000.0 + np.arange(n) * 0.01   # rampe stricte -> aucun swing low parasite
    high_v = 500.0 + np.arange(n) * 0.01   # rampe basse -> aucun swing high parasite (jamais > low ramp)
    low_v[low1_idx] = low1_price
    low_v[low2_idx] = low2_price
    high_v[apex_idx] = apex_price
    return pd.DataFrame({"low": low_v, "high": high_v})


APEX_PRICE = 600.0  # doit dominer la rampe "high" (~500.1-500.3 dans la fenêtre interne testée)


def test_channel_geometry_hand_computed():
    """2 creux (idx1=10, prix1=100) et (idx2=30, prix2=140) -- mouvement
    haussier (H1) -- apex = plus haut entre les deux, à idx=20, prix=600
    (doit dominer la rampe "high" ~500.1-500.3 utilisée comme bruit de fond
    sans quoi ce n'est plus l'apex réel -- piège rencontré et corrigé en
    écrivant ce test, laissé en commentaire pour la prochaine relecture).
    Calcul à la main :
      pente support = (140-100)/(30-10) = 2.0
      support(20)   = 100 + 2.0*(20-10) = 120
      offset        = apex_price - support(20) = 600 - 120 = 480
      support(idx)  = 100 + 2.0*(idx-10)
      resistance(idx) = support(idx) + 480
      median(idx)   = (support+resistance)/2"""
    df = _channel_series(10, 100.0, 30, 140.0, 20, APEX_PRICE)
    support, median, resistance = compute_manual_trend_channel(df, order=ORDER)

    t = 30 + ORDER + 2  # bien après la confirmation du 2e creux (idx=30 confirmé à 33)
    expected_support = 100.0 + 2.0 * (t - 10)
    expected_resistance = expected_support + 480.0
    expected_median = (expected_support + expected_resistance) / 2.0

    assert not np.isnan(support[t]), "canal devrait être construit à cet instant"
    assert np.isclose(support[t], expected_support), f"support={support[t]} attendu={expected_support}"
    assert np.isclose(resistance[t], expected_resistance), f"resistance={resistance[t]} attendu={expected_resistance}"
    assert np.isclose(median[t], expected_median), f"median={median[t]} attendu={expected_median}"


def test_no_channel_before_second_low_confirmed():
    """Avant que le 2e creux ne soit confirmé (idx=30, confirmé à 33), le
    canal ne doit pas encore exister (NaN) -- pas de canal prématuré."""
    df = _channel_series(10, 100.0, 30, 140.0, 20, APEX_PRICE)
    support, _, _ = compute_manual_trend_channel(df, order=ORDER)
    assert np.isnan(support[32]), "le canal ne doit pas exister avant la confirmation du 2e creux"


def test_no_channel_if_second_low_not_higher():
    """H1 (mouvement haussier) : si le 2e creux n'est PAS plus haut que le
    1er, aucun canal ne doit être construit pour cette paire."""
    df = _channel_series(10, 140.0, 30, 100.0, 20, APEX_PRICE)  # 2e creux plus BAS
    support, median, resistance = compute_manual_trend_channel(df, order=ORDER)
    t = 30 + ORDER + 2
    assert np.isnan(support[t]), "2e creux plus bas que le 1er -> pas un mouvement haussier, pas de canal (H1)"


def test_add_manual_trend_channel_columns_matches():
    df = _channel_series(10, 100.0, 30, 140.0, 20, APEX_PRICE)
    out = add_manual_trend_channel_columns(df, order=ORDER)
    support, median, resistance = compute_manual_trend_channel(df, order=ORDER)
    assert np.allclose(out["channel_support"].values, support, equal_nan=True)
    assert np.allclose(out["channel_median"].values, median, equal_nan=True)
    assert np.allclose(out["channel_resistance"].values, resistance, equal_nan=True)


def test_causal_no_future_leakage():
    df = _channel_series(10, 100.0, 30, 140.0, 20, APEX_PRICE)
    support_full, _, _ = compute_manual_trend_channel(df, order=ORDER)
    t = 30 + ORDER + 2
    truncated = df.iloc[: t + 1].reset_index(drop=True)
    support_trunc, _, _ = compute_manual_trend_channel(truncated, order=ORDER)
    assert np.isclose(support_trunc[-1], support_full[t]), (
        "le canal à l'instant t a changé selon que des barres futures sont "
        "présentes ou non -- régression causale"
    )


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} tests passés")
