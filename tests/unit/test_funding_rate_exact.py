"""
Tests unitaires du calcul de coût de funding EXACT par timestamp
(funding_rate_exact.py), sur des cas SYNTHÉTIQUES construits à la main --
le résultat attendu de chaque test est calculé AVANT d'exécuter le code
(même discipline que test_position_engine.py, test_proxy_v2.py).

Aucune donnée réelle n'est utilisée (pas d'accès disque). Exécution :
`python3 test_funding_rate_exact.py`. Affiche PASS/FAIL par test et sort
avec un code non-nul si un test échoue.
"""
import numpy as np
import pandas as pd

from emile.core.funding_rate_exact import (
    attach_funding_rate,
    compute_funding_cost_per_trade,
    apply_funding_to_equity,
)

# ---------------------------------------------------------------------------
# Test 1 : coût de funding d'un SEUL trade, taille connue, sorties partielles
# connues, événements de funding connus (certains bars ne sont PAS des
# événements de funding réel -> coût nul ce bar-là).
# ---------------------------------------------------------------------------
def test_single_trade_known_funding_events():
    """Trade ouvert en i=1 (taille 100%), avec une sortie partielle qui
    réduit la taille à 50% après le bar i=2. Taux de funding réel : bar 2
    (+0.10%, position à 100% -> le long paie), bar 4 (-0.05%, position à
    50% -> le long reçoit, taux négatif). Bars 3 et 5 : PAS des événements
    de funding réels (taux 0 dans `funding_rate_arr`) -> aucun coût, même
    si le trade est ouvert.

    Calcul attendu à la main :
      - bar 2 : coût = taille_avant(1.0) x taux(+0.001) = +0.001
        -> facteur multiplicatif (1 - 0.001) = 0.999
      - bar 4 : coût = taille_avant(0.5) x taux(-0.0005) = -0.00025
        -> facteur multiplicatif (1 - (-0.00025)) = 1.00025
      - multiplicateur total = 0.999 x 1.00025 = 0.99924975
      - funding_cost_%_of_capital = (1 - 0.99924975) x 100 = 0.075025
      - n_funding_events = 2 (bars 3 et 5 ont un taux nul -> exclus)
      - P&L brut du trade (réalisé par le moteur, SANS funding) = +5.0%
      - P&L net de funding = (1 + 0.05) x 0.99924975 - 1 = 0.0492122375
        (soit +4.92122375%, PAS +5.0% - 0.075025% = +4.924975% : la
        recombinaison est MULTIPLICATIVE, pas additive, cf. docstring de
        `compute_funding_cost_per_trade`)
    """
    trace = [{
        "trade_id": 0, "open_i": 1, "close_i": 6,
        "entry_price": 100.0, "entry_size": 1.0,
        "realized_pnl": 0.05,
        # (indice de bougie, taille RESTANTE avant traitement de cette bougie)
        "snapshots": [(2, 1.0), (3, 0.5), (4, 0.5), (5, 0.5)],
    }]
    # funding_rate_arr : seuls les indices 2 et 4 sont de VRAIS événements de
    # funding (taux non nul) ; 3 et 5 ne le sont pas (taux 0.0), simulant des
    # bougies H4 qui ne tombent pas sur 00:00/08:00/16:00 UTC.
    funding_rate_arr = np.zeros(7)
    funding_rate_arr[2] = 0.001
    funding_rate_arr[4] = -0.0005

    per_trade = compute_funding_cost_per_trade(trace, funding_rate_arr)
    assert len(per_trade) == 1
    t = per_trade[0]

    assert t["n_funding_events"] == 2, f"attendu 2 événements de funding, obtenu {t['n_funding_events']}"

    expected_multiplier = 0.999 * 1.00025
    assert abs(t["funding_multiplier"] - expected_multiplier) < 1e-12, (
        f"multiplicateur attendu {expected_multiplier}, obtenu {t['funding_multiplier']}"
    )

    expected_cost_pct = round((1 - expected_multiplier) * 100, 6)
    assert abs(t["funding_cost_%_of_capital"] - expected_cost_pct) < 1e-9, (
        f"coût attendu {expected_cost_pct}%, obtenu {t['funding_cost_%_of_capital']}%"
    )

    expected_net = (1 + 0.05) * expected_multiplier - 1
    assert abs(t["realized_pnl_net_of_funding"] - expected_net) < 1e-12, (
        f"P&L net attendu {expected_net}, obtenu {t['realized_pnl_net_of_funding']}"
    )
    # Contrôle négatif explicite : la recombinaison n'est PAS une simple
    # soustraction additive du coût au P&L brut.
    naive_additive = 0.05 - (1 - expected_multiplier)
    assert abs(t["realized_pnl_net_of_funding"] - naive_additive) > 1e-6, (
        "la recombinaison doit être multiplicative, pas additive -- "
        "ce test doit distinguer les deux méthodes"
    )

# ---------------------------------------------------------------------------
# Test 2 : trade SANS aucun événement de funding pendant sa détention ->
# coût nul, P&L net == P&L brut exactement.
# ---------------------------------------------------------------------------
def test_trade_with_no_funding_event_has_zero_cost():
    trace = [{
        "trade_id": 0, "open_i": 1, "close_i": 3,
        "entry_price": 100.0, "entry_size": 0.5,
        "realized_pnl": -0.02,
        "snapshots": [(2, 0.5)],
    }]
    funding_rate_arr = np.zeros(4)  # aucun événement de funding réel

    per_trade = compute_funding_cost_per_trade(trace, funding_rate_arr)
    t = per_trade[0]
    assert t["n_funding_events"] == 0
    assert abs(t["funding_multiplier"] - 1.0) < 1e-15
    assert abs(t["funding_cost_%_of_capital"] - 0.0) < 1e-9
    assert abs(t["realized_pnl_net_of_funding"] - (-0.02)) < 1e-12, (
        "sans événement de funding, le P&L net doit être identique au P&L brut"
    )

# ---------------------------------------------------------------------------
# Test 3 : agrégation portefeuille (apply_funding_to_equity) sur PLUSIEURS
# trades -> le multiplicateur total est le PRODUIT des multiplicateurs par
# trade (pas leur somme), appliqué à l'équity finale déjà calculée SANS
# funding par le moteur.
# ---------------------------------------------------------------------------
def test_apply_funding_to_equity_multiple_trades():
    """Deux trades, chacun avec un multiplicateur de funding connu.
    Calcul attendu à la main :
      - trade A : multiplicateur 0.999 (un seul événement, coût +0.1% sur 100%)
      - trade B : multiplicateur 1.0002 (un seul événement, coût -0.02% sur 100%)
      - multiplicateur total du portefeuille = 0.999 x 1.0002 = 0.9991998
      - équity brute (SANS funding, déjà calculée par le moteur) = 1.20
      - équity nette de funding = 1.20 x 0.9991998 = 1.19903976
      - total_return_%_net_of_funding attendu = round((1.19903976-1)*100, 1) = 19.9
    """
    trace_a = [{
        "trade_id": 0, "open_i": 1, "close_i": 2,
        "entry_price": 100.0, "entry_size": 1.0, "realized_pnl": 0.01,
        "snapshots": [(2, 1.0)],
    }]
    trace_b = [{
        "trade_id": 1, "open_i": 3, "close_i": 4,
        "entry_price": 100.0, "entry_size": 1.0, "realized_pnl": 0.02,
        "snapshots": [(4, 1.0)],
    }]
    funding_rate_arr_a = np.zeros(3)
    funding_rate_arr_a[2] = 0.001
    funding_rate_arr_b = np.zeros(5)
    funding_rate_arr_b[4] = -0.0002

    per_trade = (
        compute_funding_cost_per_trade(trace_a, funding_rate_arr_a)
        + compute_funding_cost_per_trade(trace_b, funding_rate_arr_b)
    )
    assert abs(per_trade[0]["funding_multiplier"] - 0.999) < 1e-12
    assert abs(per_trade[1]["funding_multiplier"] - 1.0002) < 1e-12

    agg = apply_funding_to_equity(final_equity_gross=1.20, per_trade_costs=per_trade)

    expected_total_multiplier = 0.999 * 1.0002
    expected_equity_net = 1.20 * expected_total_multiplier
    assert abs(agg["final_equity_net_of_funding"] - expected_equity_net) < 1e-9, (
        f"équity nette attendue {expected_equity_net}, obtenu {agg['final_equity_net_of_funding']}"
    )
    expected_return_pct = round((expected_equity_net - 1) * 100, 1)
    assert agg["total_return_%_net_of_funding"] == expected_return_pct, (
        f"retour net attendu {expected_return_pct}, obtenu {agg['total_return_%_net_of_funding']}"
    )

# ---------------------------------------------------------------------------
# Test 4 : attach_funding_rate -- jointure EXACTE sur le timestamp, aucun
# rapprochement approximatif. Vérifie aussi le comportement tz-naive vs
# tz-aware (les deux doivent donner le même résultat, alignés en UTC).
# ---------------------------------------------------------------------------
def test_attach_funding_rate_exact_timestamp_match():
    """Bougies toutes les 4h sur une journée (6 bougies : 00,04,08,12,16,20h).
    Événements de funding réels (synthétiques) : 00h (+0.02%) et 16h (-0.01%).
    08h n'est PAS un événement de funding dans ce jeu de test (volontaire,
    pour vérifier qu'une heure "normalement" de funding mais absente de
    `funding_events` retourne bien 0.0, pas une valeur interpolée).

    Attendu : [0.0002, 0.0, 0.0, 0.0, -0.0001, 0.0] (dans l'ordre des
    bougies 00h/04h/08h/12h/16h/20h).
    """
    dates_naive = pd.Series(pd.date_range("2024-01-01", periods=6, freq="4h"))
    funding_events = pd.Series(
        [0.0002, -0.0001],
        index=pd.to_datetime(["2024-01-01 00:00:00", "2024-01-01 16:00:00"], utc=True),
    )

    rates_naive = attach_funding_rate(dates_naive, funding_events)
    expected = np.array([0.0002, 0.0, 0.0, 0.0, -0.0001, 0.0])
    assert np.allclose(rates_naive, expected), f"attendu {expected}, obtenu {rates_naive}"

    # Même résultat si les dates d'entrée sont déjà tz-aware (UTC).
    dates_aware = dates_naive.dt.tz_localize("UTC")
    rates_aware = attach_funding_rate(dates_aware, funding_events)
    assert np.allclose(rates_aware, expected), f"attendu {expected}, obtenu {rates_aware}"

TESTS = [
    test_single_trade_known_funding_events,
    test_trade_with_no_funding_event_has_zero_cost,
    test_apply_funding_to_equity_multiple_trades,
    test_attach_funding_rate_exact_timestamp_match,
]

def main():
    n_pass = 0
    n_fail = 0
    for test_fn in TESTS:
        name = test_fn.__name__
        try:
            test_fn()
        except AssertionError as e:
            print(f"FAIL  {name}: {e}")
            n_fail += 1
        except Exception as e:
            print(f"ERROR {name}: {type(e).__name__}: {e}")
            n_fail += 1
        else:
            print(f"PASS  {name}")
            n_pass += 1

    print(f"\n{n_pass}/{len(TESTS)} tests passés" + (f", {n_fail} échec(s)" if n_fail else ""))
    if n_fail:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
