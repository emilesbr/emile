"""
Tests pour `context_bollinger.py` (`H-Context-BB-UT+1`, cf. docstring du
module et `docs/CONTEXT_CHANNEL_REVERSE_ENGINEERING.md` sections 10-11) :
  1. `compute_bollinger` sur une série constante (std=0 -> largeur nulle,
     médiane = prix) puis sur une série à volatilité connue (largeur
     vérifiée à la main).
  2. `attach_context_bb` : non-lookahead explicite -- une bougie H4 ne doit
     JAMAIS voir le Bollinger d'une bougie D1 pas encore close à cet
     instant (même famille de test que les jointures UT+1 déjà présentes
     ailleurs dans ce projet, ex. `test_backtest_phase2_v7.py`).
  3. `compute_regime_bb_context` : cas synthétique à vérité terrain connue
     (RANGE_NEUTRE quand le prix oscille dans la bande, EXCES quand la
     largeur de bande est extrême) -- même schéma que
     `test_regime_classifier.py`, réutilise `add_regime` inchangé.
"""
import numpy as np
import pandas as pd

from emile.core.context_bollinger import (
    compute_bollinger, attach_context_bb, compute_regime_bb_context, BB_PERIOD, BB_K, CLOSURE_DELAY,
)


def _daily_df(n, close_values, start="2020-01-01"):
    dates = pd.date_range(start, periods=n, freq="D")
    close = np.asarray(close_values, dtype=float)
    return pd.DataFrame({
        "date": dates, "open": close, "high": close, "low": close, "close": close,
    })


def test_compute_bollinger_constant_series_zero_width():
    df = _daily_df(30, np.full(30, 100.0))
    out = compute_bollinger(df, period=20, k=2)
    tail = out.iloc[-1]
    assert tail["bb_median"] == 100.0
    assert tail["bb_width_pct"] == 0.0


def test_compute_bollinger_known_volatility():
    # 20 bougies alternant 90/110 (moyenne=100, std population non biaisée
    # calculée à la main pour vérifier bb_width_pct sans dépendre de pandas)
    n = 25
    close = np.array([90.0 if i % 2 == 0 else 110.0 for i in range(n)])
    df = _daily_df(n, close)
    out = compute_bollinger(df, period=20, k=2)
    window = close[-20:]
    expected_sma = window.mean()
    expected_std = window.std(ddof=1)  # pandas .std() = ddof=1 par défaut
    tail = out.iloc[-1]
    assert np.isclose(tail["bb_median"], expected_sma)
    expected_width_pct = (2 * 2 * expected_std) / expected_sma * 100
    assert np.isclose(tail["bb_width_pct"], expected_width_pct)


def test_attach_context_bb_no_lookahead():
    """Une bougie H4 à la date D ne doit voir QUE le Bollinger D1 clôturé au
    plus tard à `D - CLOSURE_DELAY` -- vérifié en truffant la série D1 future
    d'une valeur aberrante et en confirmant qu'elle n'influence aucune
    bougie H4 antérieure à sa clôture."""
    n_d1 = 40
    close_d1 = np.linspace(100, 120, n_d1)
    d1 = _daily_df(n_d1, close_d1)
    bb_d1 = compute_bollinger(d1, period=20, k=2)

    # H4 : 4 bougies par jour, sur toute la période D1.
    h4_dates = pd.date_range("2020-01-01", periods=n_d1 * 6, freq="4h")
    h4 = pd.DataFrame({"date": h4_dates})

    joined_before = attach_context_bb(h4, bb_d1)

    # Modifie la DERNIÈRE bougie D1 (future par rapport à la plupart des H4)
    # à une valeur aberrante -- la jointure causale ne doit rien changer pour
    # les bougies H4 antérieures à la clôture de cette bougie D1.
    close_d1_mutated = close_d1.copy()
    close_d1_mutated[-1] = 99999.0
    d1_mutated = _daily_df(n_d1, close_d1_mutated)
    bb_d1_mutated = compute_bollinger(d1_mutated, period=20, k=2)
    joined_after = attach_context_bb(h4, bb_d1_mutated)

    last_d1_close_time = d1["date"].iloc[-1] + CLOSURE_DELAY
    unaffected = h4["date"] < last_d1_close_time
    assert unaffected.sum() > 0, "le scénario doit contenir des bougies H4 strictement avant la clôture"
    np.testing.assert_array_equal(
        joined_before["ctx_median"][unaffected.to_numpy()],
        joined_after["ctx_median"][unaffected.to_numpy()],
    )


def test_attach_context_bb_uses_most_recently_closed_bar():
    """Vérifie la valeur EXACTE jointe (pas seulement 'inchangée') : une
    bougie H4 à 00:00 le jour D doit recevoir le Bollinger de la bougie D1
    datée D-1 (la dernière close, `available_at = date + 1j <= D 00:00`
    n'est vrai que pour D-1, pas pour D lui-même, pas encore clos à cet
    instant)."""
    n_d1 = 30
    close_d1 = np.arange(n_d1, dtype=float) + 100.0
    d1 = _daily_df(n_d1, close_d1)
    bb_d1 = compute_bollinger(d1, period=5, k=2)

    probe_date = d1["date"].iloc[10]  # 00:00 du jour d'indice 10
    h4 = pd.DataFrame({"date": [probe_date]})
    joined = attach_context_bb(h4, bb_d1, closure_delay=CLOSURE_DELAY)

    expected = bb_d1["bb_median"].iloc[9]  # dernière bougie D1 CLOSE avant probe_date
    assert joined["ctx_median"][0] == expected


def test_compute_regime_bb_context_range_neutre_when_price_stays_in_band():
    """Prix H4 constant, D1 constant -> largeur de bande nulle -> `add_regime`
    classe RANGE_NEUTRE par défaut (pente nulle, w=0 n'est ni squeeze ni
    excès tant que les seuils percentiles glissants sont eux aussi à 0)."""
    n_d1 = 300
    d1 = _daily_df(n_d1, np.full(n_d1, 100.0))
    h4_dates = pd.date_range(d1["date"].iloc[0], periods=n_d1 * 6, freq="4h")
    h4 = pd.DataFrame({
        "date": h4_dates, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0,
    })
    regime = compute_regime_bb_context(h4, d1)
    assert regime[-1] == "RANGE_NEUTRE"


def test_compute_regime_bb_context_uses_add_regime_unchanged():
    """Contrôle négatif : si `ctx_width_pct` explose sur la toute dernière
    portion (volatilité D1 extrême après une longue période stable), le
    régime bascule en EXCES -- exactement le comportement documenté de
    `regime_classifier.add_regime`, non dupliqué ici."""
    n_d1 = 300
    close_d1 = np.full(n_d1, 100.0)
    # 20 dernières bougies D1 très volatiles -> bb_width_pct élevé seulement
    # sur la fin, largement au-dessus du percentile 95 des 250 précédentes.
    close_d1[-20:] = 100.0 + 40.0 * np.sin(np.arange(20))
    d1 = _daily_df(n_d1, close_d1)
    h4_dates = pd.date_range(d1["date"].iloc[0], periods=n_d1 * 6, freq="4h")
    h4_close = np.interp(
        np.arange(len(h4_dates)), np.linspace(0, len(h4_dates) - 1, n_d1), close_d1,
    )
    h4 = pd.DataFrame({
        "date": h4_dates, "open": h4_close, "high": h4_close, "low": h4_close, "close": h4_close,
    })
    regime = compute_regime_bb_context(h4, d1)
    assert regime[-1] == "EXCES"
