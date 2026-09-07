"""
Tests unitaires du moteur de position partagé (position_engine.py), sur des
séries de prix SYNTHÉTIQUES construites à la main -- le résultat attendu de
chaque cas est calculé AVANT d'exécuter le code (voir commentaires "calcul
attendu" dans chaque test).

Aucune donnée réelle n'est utilisée. Exécution : `python3 test_position_engine.py`.
Affiche PASS/FAIL par test et sort avec un code non-nul si un test échoue.

8 tests (5 historiques Validation/Confirmation/Limite/Invalidation/
pyramidalisation + 3 pour le mécanisme "+Reverse" du profil Très Agressif,
table RANGE, RULES_EXTRACTION.md §3 -- cf. le bloc dédié en tête de
`position_engine.py`, hypothèse H-Reverse-Range).
"""
import numpy as np

from position_engine import process_tranche, process_reverse, run_position_engine


def make_tranche(entry, stop, remaining, val_px, conf_px, lim_px):
    return {
        "entry": entry, "stop": stop, "remaining": remaining,
        "val_done": False, "conf_done": False, "pnl_accum": 0.0,
        "val_px": val_px, "conf_px": conf_px, "lim_px": lim_px,
    }


# ---------------------------------------------------------------------------
# Test 1 : montée en ligne droite -> Validation puis Confirmation puis Limite
# ---------------------------------------------------------------------------
def test_validation_confirmation_limite_sequence():
    """Prix qui monte et touche successivement Validation (105), Confirmation
    (110) puis Limite (120). Profil : 50% clôturé à Validation, 50% du
    restant à Confirmation (25% du total), le reste (25% du total) clôturé
    à la Limite.

    Calcul attendu à la main :
      - Validation (close=106) : clôture 50% à +6% -> contribution 0.5*0.06 = 0.03
      - Confirmation (close=111) : clôture 50% du restant (25% du total) à
        +11% -> contribution 0.25*0.11 = 0.0275
      - Limite (close=121) : clôture le reste (25% du total) à +21% ->
        contribution 0.25*0.21 = 0.0525
      - Total P&L du trade = 0.03 + 0.0275 + 0.0525 = 0.11 (+11%)
      - equity finale (fee=0, taille=100% du capital) = 1.11
      - total_return_% attendu = 11.0
    """
    n = 6
    o = np.array([100.0, 100.0, 102.0, 105.0, 109.0, 115.0])
    low = np.array([100.0, 99.0, 101.0, 104.0, 108.0, 115.0])
    c = np.array([100.0, 100.0, 102.0, 106.0, 111.0, 121.0])
    high = np.zeros(n)  # non utilisé par process_tranche
    long_signal = np.array([True] * n)

    def open_tranche_fn(i, tranches, win_streak):
        if i == 1 and len(tranches) == 0:
            return make_tranche(entry=100.0, stop=90.0, remaining=1.0,
                                 val_px=105.0, conf_px=110.0, lim_px=120.0)
        return None

    raw = run_position_engine(
        n, o, high, low, c, long_signal, open_tranche_fn,
        val_close_frac=0.5, conf_close_frac=0.5, conf_to_be=True,
        max_tranches=1, fee=0.0,
    )
    assert raw["n_trades"] == 1, f"n_trades attendu 1, obtenu {raw['n_trades']}"
    assert abs(raw["final_equity"] - 1.11) < 1e-9, f"final_equity attendu 1.11, obtenu {raw['final_equity']}"
    assert raw["total_return_%"] == 11.0, f"total_return_% attendu 11.0, obtenu {raw['total_return_%']}"
    assert raw["win_rate_%"] == 100.0


# ---------------------------------------------------------------------------
# Test 2 : le prix descend immédiatement et touche le stop -> perte exacte
# ---------------------------------------------------------------------------
def test_immediate_stop_loss():
    """Entrée à 100, stop initial à 95. Le prix chute dès la bougie suivante
    et la mèche basse (94) touche le stop.

    Calcul attendu à la main :
      - Sortie au niveau du stop (95), pas au plus bas de la mèche (94) :
        pnl = (95-100)/100 = -0.05, sur 100% du capital -> -5%
      - equity finale (fee=0) = 0.95
      - total_return_% attendu = -5.0
    """
    n = 3
    o = np.array([100.0, 100.0, 90.0])
    low = np.array([100.0, 99.0, 88.0])
    c = np.array([100.0, 100.0, 92.0])
    high = np.zeros(n)
    long_signal = np.array([True] * n)

    def open_tranche_fn(i, tranches, win_streak):
        if i == 1 and len(tranches) == 0:
            return make_tranche(entry=100.0, stop=95.0, remaining=1.0,
                                 val_px=110.0, conf_px=120.0, lim_px=130.0)
        return None

    raw = run_position_engine(
        n, o, high, low, c, long_signal, open_tranche_fn,
        val_close_frac=0.5, conf_close_frac=0.5, conf_to_be=True,
        max_tranches=1, fee=0.0,
    )
    assert raw["n_trades"] == 1
    assert abs(raw["final_equity"] - 0.95) < 1e-9, f"final_equity attendu 0.95, obtenu {raw['final_equity']}"
    assert raw["total_return_%"] == -5.0, f"total_return_% attendu -5.0, obtenu {raw['total_return_%']}"
    assert raw["win_rate_%"] == 0.0


# ---------------------------------------------------------------------------
# Test 3 : le stop ne passe JAMAIS au break-even avant la Confirmation
# ---------------------------------------------------------------------------
def test_no_breakeven_before_confirmation():
    """Validation atteinte (105) mais PAS Confirmation (115, jamais touchée),
    puis le prix redescend sous le stop INITIAL (95). Le stop doit rester à
    95 (pas remonté à l'entrée=100 par la Validation) : le trade doit se
    clôturer au niveau 95, pas 100.

    Calcul attendu à la main :
      - Validation (close=106) : clôture 50% à +6% -> 0.5*0.06 = 0.03
      - Le stop reste à 95 (la Confirmation à 115 n'est jamais atteinte)
      - Stop touché (low=94 <= 95) : clôture le reste (50%) à
        (95-100)/100 = -5% -> 0.5*(-0.05) = -0.025
      - Total P&L = 0.03 - 0.025 = 0.005 (+0.5%)
      - total_return_% attendu = 0.5

      Si un bug remontait (à tort) le stop à l'entrée (100) dès la
      Validation, la clôture au stop donnerait (100-100)/100=0 et le total
      serait 0.03 (soit total_return_% = 3.0, pas 0.5) -- ce test
      distingue explicitement les deux comportements.
    """
    n = 4
    o = np.array([100.0, 100.0, 102.0, 90.0])
    low = np.array([100.0, 99.0, 101.0, 94.0])
    c = np.array([100.0, 100.0, 106.0, 92.0])
    high = np.zeros(n)
    long_signal = np.array([True] * n)

    def open_tranche_fn(i, tranches, win_streak):
        if i == 1 and len(tranches) == 0:
            return make_tranche(entry=100.0, stop=95.0, remaining=1.0,
                                 val_px=105.0, conf_px=115.0, lim_px=130.0)
        return None

    raw = run_position_engine(
        n, o, high, low, c, long_signal, open_tranche_fn,
        val_close_frac=0.5, conf_close_frac=0.5, conf_to_be=True,
        max_tranches=1, fee=0.0,
    )
    assert raw["n_trades"] == 1
    assert abs(raw["final_equity"] - 1.005) < 1e-9, f"final_equity attendu 1.005, obtenu {raw['final_equity']}"
    assert raw["total_return_%"] == 0.5, (
        f"total_return_% attendu 0.5 (stop resté à 95) -- obtenu {raw['total_return_%']} "
        "(3.0 indiquerait un breakeven appliqué à tort dès la Validation)"
    )


# ---------------------------------------------------------------------------
# Test 4 : Validation/Confirmation/Limite se déclenchent sur la CLÔTURE, pas
# sur la mèche (high) -- process_tranche testé directement, en isolation.
# ---------------------------------------------------------------------------
def test_trigger_on_close_not_on_wick():
    """La mèche haute dépasse la Validation (108 > 105) mais la clôture
    reste dessous (103 < 105) : la Validation ne doit PAS se déclencher ce
    jour-là. Le lendemain, la clôture dépasse réellement (106 >= 105) : la
    Validation doit alors se déclencher.

    process_tranche ne reçoit même pas le array `high` en paramètre -- ce
    test vérifie explicitement qu'un dépassement en mèche seule (simulé ici
    en construisant le cas où high[i] > val_px mais close[i] < val_px) ne
    produit aucun effet.
    """
    tr = make_tranche(entry=100.0, stop=90.0, remaining=1.0,
                       val_px=105.0, conf_px=115.0, lim_px=130.0)
    o = np.array([100.0, 102.0, 104.0])
    low = np.array([99.0, 101.0, 103.0])
    c = np.array([100.0, 103.0, 106.0])
    # high[1] = 108 dépasserait la Validation (105) si le déclenchement se
    # faisait sur la mèche -- non utilisé par process_tranche, gardé ici en
    # documentation du scénario testé.
    high_wick_that_should_be_ignored = 108.0
    assert high_wick_that_should_be_ignored > tr["val_px"]
    assert c[1] < tr["val_px"]

    closed, fee_frac, realized = process_tranche(
        tr, 1, o, low, c, long_signal_prev=True,
        val_close_frac=0.5, conf_close_frac=0.5, conf_to_be=True,
    )
    assert closed is False
    assert tr["val_done"] is False, "la Validation ne doit pas se déclencher sur une mèche, seulement sur la clôture"
    assert tr["remaining"] == 1.0

    # Jour suivant : la clôture dépasse réellement le seuil -> déclenchement
    closed2, fee_frac2, realized2 = process_tranche(
        tr, 2, o, low, c, long_signal_prev=True,
        val_close_frac=0.5, conf_close_frac=0.5, conf_to_be=True,
    )
    assert closed2 is False
    assert tr["val_done"] is True, "la Validation doit se déclencher quand la clôture dépasse le seuil"
    assert abs(tr["remaining"] - 0.5) < 1e-12


# ---------------------------------------------------------------------------
# Test 5 : pyramidalisation à 2 tranches
# ---------------------------------------------------------------------------
def test_pyramiding_two_tranches():
    """Une tranche A ouverte en i=1 (entrée 100, limite 120, taille 50% du
    capital), puis une tranche B ouverte en i=2 en renfort (entrée 110,
    limite 130, taille 50% du capital) pendant que A est encore ouverte.
    Validation/Confirmation désactivées (seuils à 99999, inatteignables) --
    seules Limite/Stop ferment une tranche ici, pour un calcul simple.

    Calcul attendu à la main :
      - A clôturée à la Limite (close=121) : pnl = (121-100)/100 = 0.21,
        sur 50% du capital -> 0.105
      - B clôturée à la Limite (close=131) : pnl = (131-110)/110 = 0.190909...,
        sur 50% du capital -> 0.0954545...
      - equity finale (fee=0) = (1+0.105) * (1+0.0954545454545...)
                              = 1.105 * 1.0954545454545... = 1.2104772727...
      - total_return_% attendu (arrondi à 1 décimale) = 21.0
      - n_trades attendu = 2 (les deux tranches se clôturent séparément)
    """
    n = 5
    o = np.array([100.0, 100.0, 110.0, 120.0, 130.0])
    low = np.array([100.0, 99.0, 105.0, 115.0, 125.0])
    c = np.array([100.0, 100.0, 112.0, 121.0, 131.0])
    high = np.zeros(n)
    long_signal = np.array([True] * n)

    def open_tranche_fn(i, tranches, win_streak):
        if i == 1 and len(tranches) == 0:
            return make_tranche(entry=100.0, stop=80.0, remaining=0.5,
                                 val_px=99999.0, conf_px=99999.0, lim_px=120.0)
        if i == 2 and len(tranches) == 1:
            return make_tranche(entry=110.0, stop=80.0, remaining=0.5,
                                 val_px=99999.0, conf_px=99999.0, lim_px=130.0)
        return None

    raw = run_position_engine(
        n, o, high, low, c, long_signal, open_tranche_fn,
        val_close_frac=0.0, conf_close_frac=0.0, conf_to_be=True,
        max_tranches=2, fee=0.0,
    )
    expected_equity = 1.105 * (1 + (21.0 / 110.0) * 0.5)
    assert raw["n_trades"] == 2, f"n_trades attendu 2 (une tranche pyramidée), obtenu {raw['n_trades']}"
    assert abs(raw["final_equity"] - expected_equity) < 1e-9, (
        f"final_equity attendu {expected_equity}, obtenu {raw['final_equity']}"
    )
    assert raw["total_return_%"] == 21.0, f"total_return_% attendu 21.0, obtenu {raw['total_return_%']}"
    assert raw["win_rate_%"] == 100.0


# ---------------------------------------------------------------------------
# Test 6 : "+Reverse" du profil Très Agressif (table RANGE) -- séquence
# complète Validation -> Confirmation -> Limite -> Reverse, P&L exact pour
# la jambe long ET pour la jambe short (hypothèse H-Reverse-Range, cf. tête
# de position_engine.py). Profil Très Agressif réel : val_close_frac=0.0,
# conf_close_frac=0.0 ("RIEN"/"—") -- la Validation/Confirmation sont
# atteintes dans la série de prix (pour exercer la machine à états au
# complet) mais ne clôturent rien, la totalité de la tranche reste ouverte
# jusqu'à la Limite.
# ---------------------------------------------------------------------------
def test_reverse_at_limit_sequence():
    """Jambe long : entrée 100, stop 90, val_px 105, conf_px 110, lim_px 120.
    Validation touchée (close=106, i=3) puis Confirmation (close=111, i=4)
    -- aucune des deux ne clôture rien (fractions à 0, profil Très Agressif).
    Limite touchée (close=121, i=5) : clôture totale + ouverture immédiate
    d'une jambe reverse (short) au même prix de clôture.

    Calcul attendu à la main :
      - Jambe long : pnl = (121-100)/100 = 0.21 -> equity = 1.21
      - Jambe reverse (H-Reverse-Range) : stop_pct = (100-90)/100 = 0.10,
        gain_pct = (120-100)/100 = 0.20 -> entry=121, stop=121*1.10=133.1,
        target=121*0.80=96.8
      - i=6 : close=90 <= target(96.8) -> cible atteinte, pnl reverse =
        (121-90)/121 = 31/121
      - equity finale = 1.21 * (1 + 31/121) = (121/100)*(152/121) = 152/100
        = 1.52 (calcul exact, pas d'arrondi intermédiaire)
      - total_return_% attendu = 52.0, n_trades attendu = 2 (jambe long +
        jambe reverse), win_rate_% attendu = 100.0 (les deux gagnantes)
    """
    n = 7
    o = np.array([100.0, 100.0, 102.0, 105.0, 109.0, 115.0, 115.0])
    high = np.array([100.0, 101.0, 103.0, 107.0, 112.0, 122.0, 116.0])
    low = np.array([100.0, 99.0, 101.0, 104.0, 108.0, 115.0, 85.0])
    c = np.array([100.0, 100.0, 102.0, 106.0, 111.0, 121.0, 90.0])
    long_signal = np.array([True] * n)

    def open_tranche_fn(i, tranches, win_streak):
        if i == 1 and len(tranches) == 0:
            return make_tranche(entry=100.0, stop=90.0, remaining=1.0,
                                 val_px=105.0, conf_px=110.0, lim_px=120.0)
        return None

    raw = run_position_engine(
        n, o, high, low, c, long_signal, open_tranche_fn,
        val_close_frac=0.0, conf_close_frac=0.0, conf_to_be=True,
        max_tranches=1, fee=0.0, reverse_at_limit=True,
    )
    assert raw["n_trades"] == 2, f"n_trades attendu 2 (long + reverse), obtenu {raw['n_trades']}"
    assert abs(raw["final_equity"] - 1.52) < 1e-9, f"final_equity attendu 1.52, obtenu {raw['final_equity']}"
    assert raw["total_return_%"] == 52.0, f"total_return_% attendu 52.0, obtenu {raw['total_return_%']}"
    assert raw["win_rate_%"] == 100.0


def test_reverse_disabled_by_default_no_behavior_change():
    """Même scénario que ci-dessus mais SANS `reverse_at_limit` (comportement
    par défaut) : la jambe long se clôture à la Limite exactement pareil
    (pnl=+21%), mais AUCUNE jambe reverse ne doit s'ouvrir -- n_trades doit
    rester à 1, pas 2, et le mouvement de prix après la Limite (bar i=6, qui
    aurait déclenché la cible reverse) ne doit avoir AUCUN effet sur l'equity.
    """
    n = 7
    o = np.array([100.0, 100.0, 102.0, 105.0, 109.0, 115.0, 115.0])
    high = np.array([100.0, 101.0, 103.0, 107.0, 112.0, 122.0, 116.0])
    low = np.array([100.0, 99.0, 101.0, 104.0, 108.0, 115.0, 85.0])
    c = np.array([100.0, 100.0, 102.0, 106.0, 111.0, 121.0, 90.0])
    long_signal = np.array([True] * n)

    def open_tranche_fn(i, tranches, win_streak):
        if i == 1 and len(tranches) == 0:
            return make_tranche(entry=100.0, stop=90.0, remaining=1.0,
                                 val_px=105.0, conf_px=110.0, lim_px=120.0)
        return None

    raw = run_position_engine(
        n, o, high, low, c, long_signal, open_tranche_fn,
        val_close_frac=0.0, conf_close_frac=0.0, conf_to_be=True,
        max_tranches=1, fee=0.0,
        # reverse_at_limit omis -> défaut False
    )
    assert raw["n_trades"] == 1, f"n_trades attendu 1 (pas de reverse), obtenu {raw['n_trades']}"
    assert abs(raw["final_equity"] - 1.21) < 1e-9, f"final_equity attendu 1.21, obtenu {raw['final_equity']}"
    assert raw["total_return_%"] == 21.0, f"total_return_% attendu 21.0, obtenu {raw['total_return_%']}"


# ---------------------------------------------------------------------------
# Test 7 : process_reverse en isolation -- stop touché sur la MÈCHE (comme
# l'Invalidation long) même si la clôture reste au-dessus du stop ; et cible
# atteinte sur la CLÔTURE (comme la Limite long), P&L exact des deux côtés.
# ---------------------------------------------------------------------------
def test_process_reverse_stop_on_wick_and_target_on_close():
    """Jambe reverse : entry=100, stop=110, target=80.

    Cas A (stop, sur la mèche) : high=115 (>= stop=110) alors que close=105
    reste EN DESSOUS du stop -- doit tout de même se déclencher (ordre réel
    intrabar, même convention que l'Invalidation long).
      pnl attendu = (100-110)/100 = -0.10

    Cas B (cible, sur la clôture) : high=105 (< stop=110, pas de mèche
    dangereuse) et close=79 (<= target=80) -- doit se déclencher sur la
    clôture, comme la Limite long.
      pnl attendu = (100-79)/100 = 0.21
    """
    rp_a = {"entry": 100.0, "stop": 110.0, "target": 80.0, "remaining": 1.0}
    high_a = np.array([0.0, 115.0])
    low_a = np.array([0.0, 95.0])
    c_a = np.array([0.0, 105.0])
    closed_a, fee_frac_a, realized_a = process_reverse(rp_a, 1, high_a, low_a, c_a)
    assert closed_a is True
    assert fee_frac_a == 1.0
    assert abs(realized_a - (-0.10)) < 1e-9, f"pnl attendu -0.10, obtenu {realized_a}"

    rp_b = {"entry": 100.0, "stop": 110.0, "target": 80.0, "remaining": 1.0}
    high_b = np.array([0.0, 105.0])
    low_b = np.array([0.0, 78.0])
    c_b = np.array([0.0, 79.0])
    closed_b, fee_frac_b, realized_b = process_reverse(rp_b, 1, high_b, low_b, c_b)
    assert closed_b is True
    assert fee_frac_b == 1.0
    assert abs(realized_b - 0.21) < 1e-9, f"pnl attendu 0.21, obtenu {realized_b}"


TESTS = [
    test_validation_confirmation_limite_sequence,
    test_immediate_stop_loss,
    test_no_breakeven_before_confirmation,
    test_trigger_on_close_not_on_wick,
    test_pyramiding_two_tranches,
    test_reverse_at_limit_sequence,
    test_reverse_disabled_by_default_no_behavior_change,
    test_process_reverse_stop_on_wick_and_target_on_close,
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
