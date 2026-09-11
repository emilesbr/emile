"""
Tests unitaires du moteur de position partagé (position_engine.py), sur des
séries de prix SYNTHÉTIQUES construites à la main -- le résultat attendu de
chaque cas est calculé AVANT d'exécuter le code (voir commentaires "calcul
attendu" dans chaque test).

Aucune donnée réelle n'est utilisée. Exécution : `python3 test_position_engine.py`.
Affiche PASS/FAIL par test et sort avec un code non-nul si un test échoue.

28 tests (5 historiques Validation/Confirmation/Limite/Invalidation/
pyramidalisation + 3 pour le mécanisme "+Reverse" du profil Très Agressif,
table RANGE, RULES_EXTRACTION.md §3 -- cf. le bloc dédié en tête de
`position_engine.py`, hypothèse H-Reverse-Range -- + 5 pour la règle de
volatilité "Stop Loss = taille du canal", TRADING_LESSONS_MAITRISE_GRADIENT_
RISQUE.md §5, hypothèses H-Canal-Large-1..4 du même fichier -- + 6 pour
"Confirmation = médiane du canal de contexte, clôturée", RULES_EXTRACTION.md
§3 ligne 41 et TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md ligne 55,
hypothèses H-Conf-Struct-1..5 du même fichier -- + 9 pour la variante
d'entrée "3ème borne squeezée", TRADING_LESSONS_PYRAMIDALISATION.md
Variante 2, hypothèses H-Squeeze-1..8 du même fichier).
"""
import numpy as np

import pandas as pd

from emile.core.position_engine import (
    process_tranche, process_reverse, run_position_engine, make_open_tranche_fn,
    WIDE_CHANNEL_STOP_FRAC, WIDE_CHANNEL_SIZE_FRAC,
    CONTEXT_MEDIAN_FRAC, context_channel_median, make_structural_conf_update_fn,
    compute_squeezed_third_border, SQUEEZE_LIFETIME,
)

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

# ---------------------------------------------------------------------------
# Tests 9-13 : règle de volatilité "Stop Loss = taille du canal"
# (TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md §5 -- cf. le bloc "STOP LOSS =
# TAILLE DU CANAL" en tête de `position_engine.py`, hypothèses
# H-Canal-Large-1..4). Vérité terrain calculée à la main dans chaque
# docstring, aucune donnée réelle, aucune propriété statistique.
# ---------------------------------------------------------------------------
def _open_once(risk_pct, wide_channel_v, ctx_support=90.0, entry=100.0, max_tranches=3):
    """Ouvre UNE tranche à i=1 (donc j=0) avec la factory réelle et retourne le
    dict de tranche. Tous les paramètres non pertinents ici sont neutralisés :
    `rule3_streak` inatteignable (Règle de Trois jamais déclenchée),
    `min_borders=1` avec `n_borders=1` (maturité toujours acquise),
    `warmup=0`, aucun gate additionnel."""
    n = 3
    o = np.full(n, entry)
    high = np.full(n, entry)
    state = {"last_pyramid_high": -np.inf}
    fn = make_open_tranche_fn(
        atr_v=np.full(n, 1.0), ctx_support_v=np.full(n, ctx_support),
        local_range_v=np.full(n, 5.0), context_range_v=np.full(n, 10.0),
        n_borders_v=np.full(n, 1.0), high=high, o=o, score=np.full(n, 2.0),
        warmup=0, min_borders=1, max_tranches=max_tranches,
        rule3_streak=10 ** 9, rule3_size_mult=1.0, risk_pct=risk_pct, state=state,
        wide_channel_v=wide_channel_v,
    )
    return fn(1, [], 0)

def test_wide_channel_halves_stop_and_leaves_exposure_constant():
    """Vérité terrain (H-Canal-Large-1), entrée=100, canal bas=90, risk=2% :

      RÈGLE STANDARD (canal pas très large)
        stop_pct = (100-90)/100 = 0.10 -> stop = 90.0
        size     = min(1/3, 0.02/0.10) = min(0.3333, 0.20) = 0.20
        capital risqué = 0.10 * 0.20 = 0.02 = risk_pct

      RÈGLE DE VOLATILITÉ (canal très large) -- les deux "/2" de la source
        "Taille du Canal / 2 = Taille du Stop Loss" : stop_pct = 0.05
                                                     -> stop = 100*(1-0.05) = 95.0
        "ET Taille de Position / 2" : size = min(1/3, (0.02/0.05) * 0.5)
                                           = min(0.3333, 0.20) = 0.20
        capital risqué = 0.05 * 0.20 = 0.01 = risk_pct / 2

    Donc : stop DEUX FOIS plus serré, position INCHANGÉE (= *"préserve une
    exposition capital constante"*, la parenthèse même de la source, qui est
    ce qui tranche entre les deux lectures possibles), capital risqué DIVISÉ
    PAR DEUX."""
    std = _open_once(0.02, wide_channel_v=None)
    wide = _open_once(0.02, wide_channel_v=np.array([True, True, True]))

    assert std["stop"] == 90.0, f"stop standard attendu 90.0, obtenu {std['stop']}"
    assert abs(std["remaining"] - 0.20) < 1e-12, (
        f"taille standard attendue 0.20, obtenue {std['remaining']}")

    assert abs(wide["stop"] - 95.0) < 1e-12, (
        f"stop 'canal très large' attendu 95.0 (moitié de la distance 100->90), "
        f"obtenu {wide['stop']}")
    assert abs(wide["remaining"] - 0.20) < 1e-12, (
        f"taille 'canal très large' attendue 0.20 (INCHANGÉE : les deux '/2' se "
        f"compensent dans un moteur dimensionné par le risque), obtenue "
        f"{wide['remaining']}")

    risk_std = (std["entry"] - std["stop"]) / std["entry"] * std["remaining"]
    risk_wide = (wide["entry"] - wide["stop"]) / wide["entry"] * wide["remaining"]
    assert abs(risk_std - 0.02) < 1e-12, f"capital risqué standard attendu 0.02, obtenu {risk_std}"
    assert abs(risk_wide - 0.01) < 1e-12, (
        f"capital risqué 'canal très large' attendu 0.01 (moitié), obtenu {risk_wide}")

def test_wide_channel_halving_applies_before_the_per_tranche_cap():
    """Corollaire d'implémentation de H-Canal-Large-1, testé explicitement
    parce que c'est le point où les deux ordres possibles DIVERGENT.

    Vérité terrain, entrée=100, canal bas=90, risk=20% (choisi pour que le
    plafond `1/max_tranches` MORDE dans les deux cas), max_tranches=3 :
      standard : min(1/3, 0.20/0.10 = 2.0)                = 1/3
      RETENU   (réduction AVANT le plafond) :
                 min(1/3, (0.20/0.05) * 0.5 = 2.0)        = 1/3   <- constant
      ÉCARTÉ   (réduction APRÈS le plafond) :
                 0.5 * min(1/3, 0.20/0.05 = 4.0)          = 1/6   <- non constant
    Seul l'ordre retenu respecte *"(préserve une exposition capital
    constante)"* quand le plafond mord -- c'est-à-dire précisément dans les
    configurations les plus volatiles, celles que la règle vise."""
    std = _open_once(0.20, wide_channel_v=None)
    wide = _open_once(0.20, wide_channel_v=np.array([True, True, True]))
    assert abs(std["remaining"] - 1.0 / 3.0) < 1e-12, (
        f"taille standard attendue 1/3 (plafond), obtenue {std['remaining']}")
    assert abs(wide["remaining"] - 1.0 / 3.0) < 1e-12, (
        f"taille 'canal très large' attendue 1/3 (plafond, INCHANGÉE), obtenue "
        f"{wide['remaining']} -- 1/6 signifierait que la réduction de taille est "
        f"appliquée APRÈS le plafond (lecture explicitement écartée)")

def test_wide_channel_none_and_all_false_are_identical():
    """Non-régression : `wide_channel_v=None` (défaut des 9 moteurs déjà en
    place) et un array entièrement False doivent produire EXACTEMENT la même
    tranche que l'un l'autre -- la règle n'a aucun effet hors des bougies
    qu'elle vise."""
    default = _open_once(0.02, wide_channel_v=None)
    all_false = _open_once(0.02, wide_channel_v=np.array([False, False, False]))
    assert default == all_false, (
        f"comportement par défaut modifié : {default} != {all_false}")

def test_wide_channel_is_read_at_j_equals_i_minus_1_causal():
    """Causalité : la factory lit `wide_channel_v[j]` avec j = i-1, comme
    `ctx_support_v[j]`/`score[j]`. Une ouverture à i=1 doit donc consulter
    l'indice 0, JAMAIS l'indice 1 (la bougie en cours). Array
    [False, True, True] : la tranche ouverte à i=1 doit être dimensionnée par
    la RÈGLE STANDARD (stop 90), pas par la règle de volatilité (stop 95)."""
    tr = _open_once(0.02, wide_channel_v=np.array([False, True, True]))
    assert tr["stop"] == 90.0, (
        f"stop attendu 90.0 (règle standard : wide_channel_v[0] est False), "
        f"obtenu {tr['stop']} -- la factory lit la bougie en cours (lookahead) "
        f"au lieu de la précédente")

def test_wide_channel_fractions_are_the_two_halves_of_the_source():
    """Garde-fou de traçabilité : les deux constantes sont les deux "/2"
    littéraux de la phrase source (*"Taille du Canal / 2 = Taille du Stop Loss
    ET Taille de Position / 2"*). Si l'une d'elles change un jour, le calcul à
    la main des tests ci-dessus n'est plus valide -- l'échec doit être
    explicite, pas silencieux."""
    assert WIDE_CHANNEL_STOP_FRAC == 0.5, (
        f"WIDE_CHANNEL_STOP_FRAC={WIDE_CHANNEL_STOP_FRAC}, la source dit "
        f"'Taille du Canal / 2 = Taille du Stop Loss'")
    assert WIDE_CHANNEL_SIZE_FRAC == 0.5, (
        f"WIDE_CHANNEL_SIZE_FRAC={WIDE_CHANNEL_SIZE_FRAC}, la source dit "
        f"'ET Taille de Position / 2'")

# ---------------------------------------------------------------------------
# "Confirmation = médiane du canal de contexte, clôturée"
# (RULES_EXTRACTION.md:41 ; TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md:55)
# Hypothèses H-Conf-Struct-1..5, cf. le bloc dédié en tête de
# `position_engine.py`. 5 tests, tous à vérité terrain CALCULÉE À LA MAIN.
# ---------------------------------------------------------------------------
def test_context_channel_median_is_the_midpoint_hand_computed():
    """Vérité terrain calculée à la main, avec le `.shift(1)` causal.

    5 bougies journalières, fenêtre "3D" :
      i=0 : pas d'historique antérieur -> NaN
      i=1 : fenêtre = {bougie 0}              -> high 10, low  2 -> médiane 6
      i=2 : fenêtre = {0,1}                   -> high 20, low  2 -> médiane 11
      i=3 : fenêtre = {0,1,2} (3 jours)       -> high 20, low  2 -> médiane 11
      i=4 : fenêtre = {1,2,3} (3 jours)       -> high 20, low  4 -> médiane 12
    """
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=5, freq="D"),
        "high": [10.0, 20.0, 12.0, 16.0, 30.0],
        "low":  [2.0,  6.0,  4.0,  9.0,  1.0],
    })
    med = context_channel_median(df, "3D")
    assert np.isnan(med[0]), f"i=0 doit être NaN (shift(1) sans historique), got {med[0]}"
    expected = [6.0, 11.0, 11.0, 12.0]
    for k, exp in zip(range(1, 5), expected):
        assert abs(med[k] - exp) < 1e-12, f"i={k} attendu {exp}, obtenu {med[k]}"
    # la bougie courante n'entre JAMAIS dans son propre canal : le high 30 de
    # i=4 (le plus haut de la série) ne remonte aucune médiane.
    assert max(med[1:]) == 12.0

def test_structural_conf_uses_moving_level_read_at_i_minus_1():
    """H-Conf-Struct-2 : le niveau est lu à `[i - 1]` et comparé à `c[i]`.

    Contrôle POSITIF et NÉGATIF sur la même tranche, à la main :
      conf_px figé (amplitude) = 200 -> jamais atteint par une clôture à 105.
      niveau structurel = [_, 300, 100, 100] -> à i=2 le hook lit
      ctx_median[1] = 300 > close 105 : PAS de Confirmation ; à i=3 il lit
      ctx_median[2] = 100 <= close 105 : Confirmation.
    """
    ctx_median_v = np.array([np.nan, 300.0, 100.0, 100.0])
    upd = make_structural_conf_update_fn(ctx_median_v)
    tr = make_tranche(100.0, 90.0, 1.0, val_px=101.0, conf_px=200.0, lim_px=999.0)
    tr["val_done"] = True     # Validation déjà acquise à une bougie antérieure
    c = np.array([100.0, 102.0, 105.0, 105.0])
    o = c.copy(); low = c.copy()

    upd(tr, 2)
    assert tr["conf_px"] == 300.0, tr["conf_px"]
    process_tranche(tr, 2, o, low, c, True, 0.0, 0.0, True)
    assert not tr["conf_done"], "contrôle NÉGATIF : 105 < 300, pas de Confirmation"

    upd(tr, 3)
    assert tr["conf_px"] == 100.0, tr["conf_px"]
    process_tranche(tr, 3, o, low, c, True, 0.0, 0.0, True)
    assert tr["conf_done"], "contrôle POSITIF : 105 >= 100, Confirmation atteinte"
    assert tr["stop"] == 100.0, f"break-even attendu à l'entrée, got {tr['stop']}"

def test_structural_conf_nan_level_is_unreachable():
    """H-Conf-Struct-3 : niveau inconnu (NaN) -> `+inf`, donc la Confirmation
    ne peut PAS être déclarée atteinte (convention "un niveau inconnu fait
    échouer le test", déjà retenue par H15 de `trend_table.py`)."""
    upd = make_structural_conf_update_fn(np.array([np.nan, np.nan, 50.0]))
    tr = make_tranche(100.0, 90.0, 1.0, val_px=101.0, conf_px=101.0, lim_px=999.0)
    tr["val_done"] = True
    c = np.array([100.0, 1e9, 1e9])
    o = c.copy(); low = np.array([100.0, 100.0, 100.0])
    upd(tr, 1)
    assert tr["conf_px"] == np.inf
    process_tranche(tr, 1, o, low, c, True, 0.0, 0.0, True)
    assert not tr["conf_done"], "un niveau NaN ne doit jamais être 'atteint'"

def test_structural_conf_only_moves_conf_px():
    """Le hook ne touche QUE `conf_px` -- `val_px`, `lim_px`, `stop`,
    `remaining` restent ceux posés par `make_open_tranche_fn` (aucun autre
    niveau du manuel n'est structurel : Validation et Limite sont des
    projections, #12:8 et #5:56)."""
    upd = make_structural_conf_update_fn(np.array([1.0, 7.0]))
    tr = make_tranche(100.0, 90.0, 0.5, val_px=105.0, conf_px=110.0, lim_px=120.0)
    before = {k: tr[k] for k in ("entry", "stop", "remaining", "val_px", "lim_px")}
    upd(tr, 1)
    assert tr["conf_px"] == 1.0
    for k, v in before.items():
        assert tr[k] == v, f"{k} modifié : {before[k]} -> {tr[k]}"

def test_structural_conf_off_by_default_is_bit_identical():
    """Non-régression : `update_levels_fn=None` (le défaut) doit produire un
    résultat STRICTEMENT identique à un appel sans le paramètre -- garde-fou
    direct contre une activation accidentelle du mécanisme."""
    n = 40
    o = np.linspace(100.0, 140.0, n)
    c = o + 0.5
    high = c + 1.0
    low = o - 1.0
    long_signal = np.ones(n, dtype=bool)

    def make_engine(**kw):
        state = {"last_pyramid_high": -np.inf}
        fn = make_open_tranche_fn(
            np.full(n, 2.0), o * 0.9, np.full(n, 5.0), np.full(n, 12.0),
            np.full(n, 9.0), high, o, np.full(n, 3.0), 3, 3, 1, 3, 0.5, 0.02, state,
        )
        return run_position_engine(n, o, high, low, c, long_signal, fn,
                                   val_close_frac=0.25, conf_close_frac=0.25,
                                   conf_to_be=True, max_tranches=1, fee=0.0004, **kw)

    a = make_engine()
    b = make_engine(update_levels_fn=None)
    for k in ("n_trades", "final_equity", "max_dd_%", "total_return_%"):
        assert a[k] == b[k], f"{k} : {a[k]} != {b[k]}"
    assert np.array_equal(a["equity_curve"], b["equity_curve"])

def test_context_median_frac_is_the_literal_50_percent():
    """Garde-fou de traçabilité, même esprit que
    `test_wide_channel_fractions_are_the_two_halves_of_the_source` : le 0,5
    n'est pas un réglage à nous, c'est le chiffre littéral de
    `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md:55` (*"la médiane (50%) du
    contexte"*), cohérent avec *"médiane canal contexte"* du manuel §3."""
    assert CONTEXT_MEDIAN_FRAC == 0.5, (
        f"CONTEXT_MEDIAN_FRAC={CONTEXT_MEDIAN_FRAC}, la source dit "
        f"'la médiane (50%) du contexte'")
# ===========================================================================
# Variante d'entrée "3ème borne squeezée" (#15 Variante 2) -- hypothèses
# H-Squeeze-1..8 en tête de `position_engine.py`. Tous les cas ci-dessous
# sont calculés À LA MAIN dans les docstrings AVANT d'exécuter le code.
# ===========================================================================

# Série synthétique commune aux tests du détecteur, `swing_order = 1`.
#
#   i | low | high | commentaire
#   --+-----+------+-------------------------------------------------------
#   0 | 100 | 105  | avant le creux
#   1 |  90 |  95  | LE CREUX (trough), L = 90
#   2 |  96 | 100  | confirmation du creux (k = trough_idx + swing_order = 2)
#   3 | 105 | 110  |
#   4 | 112 | 120  |
#   5 | 118 | 125  |
_SQ_LOW = [100.0, 90.0, 96.0, 105.0, 112.0, 118.0]
_SQ_HIGH = [105.0, 95.0, 100.0, 110.0, 120.0, 125.0]
_SQ_CONF = [False, False, True, False, False, False]
_SQ_ORDER = 1

def test_squeezed_third_border_positive_case_hand_computed():
    """Cas POSITIF, calculé à la main barre par barre (H-Squeeze-1..4).

    Le creux est en i=1 (L = 90), confirmé en i=2. Le suivi du repli démarre
    APRÈS la barre du creux (le `peak` est initialisé à high[1] = 95) :

      i=2 : peak = max(95, 100) = 100 ; repli = 100 - 96 = 4
            mouvement = 100 - 90 = 10 ; 10 >= local_range(20) ? NON -> pas armé
      i=3 : peak = 110 ; repli = max(4, 110 - 105) = 5
            mouvement = 20 ; 20 >= 20 OUI ; 5/20 = 0,250 >= 0,23 -> PAS armé
      i=4 : peak = 120 ; repli = max(5, 120 - 112) = 8
            mouvement = 30 ; 8/30 = 0,2667 >= 0,23 -> PAS armé
      i=5 : peak = 125 ; repli = max(8, 125 - 118 = 7) = 8
            mouvement = 35 ; 8/35 = 0,22857 < 0,23 -> ARMÉ

    Le seuil 0,23 est donc franchi entre i=4 et i=5, et la valeur attendue du
    point médian (H-Squeeze-4) est L + 0,50 x 35 = 90 + 17,5 = 107,5, le stop
    (H-Squeeze-5) valant le creux lui-même, 90."""
    lr = [20.0] * 6
    armed, mid, sup = compute_squeezed_third_border(
        _SQ_LOW, _SQ_HIGH, lr, _SQ_CONF, _SQ_ORDER)

    assert list(armed) == [False, False, False, False, False, True], list(armed)
    assert mid[5] == 107.5, mid[5]
    assert sup[5] == 90.0, sup[5]
    # Là où la configuration n'est pas réunie, les deux niveaux sont NaN --
    # aucun ordre ne peut être posé par erreur sur une valeur résiduelle.
    assert all(np.isnan(mid[k]) for k in range(5)), mid
    assert all(np.isnan(sup[k]) for k in range(5)), sup

def test_squeezed_third_border_negative_case_retracement_invalidates():
    """Cas NÉGATIF (contrôle) : même série, mais la barre i=4 creuse à 105 au
    lieu de 112 -- un vrai repli au milieu du mouvement.

      i=4 : peak = 120 ; repli = 120 - 105 = 15 ; mouvement = 30 -> 0,50
      i=5 : peak = 125 ; repli = max(15, 125 - 118 = 7) = 15
            mouvement = 35 ; 15/35 = 0,4286 >= 0,23 -> JAMAIS armé

    C'est exactement la clause *"sans retracement préalable"* (H-Squeeze-3) :
    un mouvement de même amplitude, mais qui a rendu 43% de son avance en
    route, n'est PAS une 3ème borne squeezée."""
    low = list(_SQ_LOW)
    low[4] = 105.0
    lr = [20.0] * 6
    armed, mid, sup = compute_squeezed_third_border(
        low, _SQ_HIGH, lr, _SQ_CONF, _SQ_ORDER)

    assert not armed.any(), list(armed)
    assert all(np.isnan(v) for v in mid), mid

def test_squeezed_third_border_requires_the_1_to_1_ratio():
    """Second contrôle négatif, sur l'AUTRE moitié de la condition
    (H-Squeeze-2) : série identique au cas positif, mais `local_range` porté
    de 20 à 40. Le mouvement maximal atteint 35 < 40, donc le ratio 1:1
    n'est jamais atteint et rien n'est armé, alors même que le critère
    "sans retracement" reste satisfait en i=5. Les deux conditions sont bien
    cumulatives, pas alternatives."""
    armed, _, _ = compute_squeezed_third_border(
        _SQ_LOW, _SQ_HIGH, [40.0] * 6, _SQ_CONF, _SQ_ORDER)
    assert not armed.any(), list(armed)

# --- Branche "Limite Achat" de make_open_tranche_fn ------------------------
#
# Scénario synthétique commun, construit pour ISOLER le nouveau chemin : on
# force `n_borders = 0` partout, donc `mature` est FAUX et l'entrée standard
# (`is_fresh_entry`) ne peut JAMAIS s'ouvrir. Toute tranche produite ci-dessous
# vient donc nécessairement de l'ordre "Limite Achat" -- c'est précisément la
# situation que décrit la source (la 3ème borne ne s'est jamais formée).
_SQ_N = 40

def _squeeze_factory(mid=100.0, sup=90.0, arm_at=1, o_fill=102.0, low_fill=99.0,
                     fill_bar=3, enabled=True, lifetime=None, risk_pct=0.02):
    """Fabrique un `open_tranche_fn` sur des tableaux synthétiques constants.
    `arm_at` est l'indice `j` où la configuration est armée (donc l'ordre est
    posé à l'appel `i = arm_at + 1`)."""
    n = _SQ_N
    o = np.full(n, 200.0)
    high = np.full(n, 200.0)
    low = np.full(n, 200.0)
    o[fill_bar] = o_fill
    low[fill_bar] = low_fill
    atr_v = np.full(n, 1.0)
    ctx_support_v = np.full(n, 150.0)
    local_range_v = np.full(n, 10.0)
    context_range_v = np.full(n, 20.0)
    n_borders_v = np.zeros(n)          # -> `mature` toujours FAUX
    score = np.full(n, 2.0)            # -> signal long toujours actif
    state = {"last_pyramid_high": -np.inf}

    armed = np.zeros(n, dtype=bool)
    armed[arm_at] = True
    mid_v = np.full(n, np.nan)
    sup_v = np.full(n, np.nan)
    mid_v[arm_at] = mid
    sup_v[arm_at] = sup

    kwargs = {}
    if enabled:
        kwargs = {"squeeze_armed_v": armed, "squeeze_mid_v": mid_v,
                  "squeeze_sup_v": sup_v, "low_v": low}
        if lifetime is not None:
            kwargs["squeeze_lifetime"] = lifetime
    fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v,
        high, o, score, warmup=0, min_borders=3, max_tranches=3,
        rule3_streak=3, rule3_size_mult=0.5, risk_pct=risk_pct, state=state,
        **kwargs)
    return fn, state

def test_squeeze_limit_order_fills_with_hand_computed_levels():
    """Chemin nominal, entièrement calculé à la main.

    i=2 : l'ordre est POSÉ (configuration armée en j=1), aucune tranche ouverte.
    i=3 : la mèche descend à 99 <= 100 -> l'ordre se remplit.
          prix de remplissage = min(médian 100 ; open 102) = 100 (H-Squeeze-4)
          stop = min(support 90 ; 100 x 0,999 = 99,9) = 90       (H-Squeeze-5)
          stop_pct = (100 - 90) / 100 = 0,10
          taille = min(1/3 ; 0,02 / 0,10) = min(0,3333 ; 0,20) = 0,20
          val_px  = 100 + local_range(10)        = 110
          conf_px = 100 + context_range(20)      = 120
          lim_px  = 100 + 1,5 x context_range(20) = 130
    Rien n'aurait pu s'ouvrir par le chemin standard : `n_borders = 0` donc
    `mature` est faux (H-Squeeze-7)."""
    fn, state = _squeeze_factory()

    assert fn(2, [], 0) is None, "l'ordre est seulement POSÉ à i=2, pas rempli"
    assert state["squeeze_pending"] is not None
    assert state["squeeze_pending"]["expires_at"] == 2 + 30 - 1

    tr = fn(3, [], 0)
    assert tr is not None, "l'ordre aurait dû se remplir à i=3"
    assert tr["entry"] == 100.0, tr["entry"]
    assert tr["stop"] == 90.0, tr["stop"]
    assert abs(tr["remaining"] - 0.20) < 1e-12, tr["remaining"]
    assert tr["val_px"] == 110.0, tr["val_px"]
    assert tr["conf_px"] == 120.0, tr["conf_px"]
    assert tr["lim_px"] == 130.0, tr["lim_px"]
    assert state["squeeze_pending"] is None, "l'ordre doit être consommé"
    # H-Squeeze-8 : ce chemin ne nourrit PAS le compteur de pyramidage.
    assert state["last_pyramid_high"] == -np.inf, state["last_pyramid_high"]

def test_squeeze_limit_order_fills_at_the_open_on_a_gap():
    """Cas du gap : l'open (98) est DÉJÀ sous le point médian (100). Un ordre
    limite réel est alors exécuté au prix de marché, meilleur que le prix
    demandé -> remplissage à 98, pas à 100 (H-Squeeze-4).
      stop_pct = (98 - 90)/98 = 0,081632... ; taille = min(1/3 ; 0,02/0,081632)
      = min(0,3333 ; 0,245) = 0,245 exactement 0,02 x 98 / 8 = 0,245
      val_px = 98 + 10 = 108."""
    fn, _ = _squeeze_factory(o_fill=98.0, low_fill=97.0)
    assert fn(2, [], 0) is None
    tr = fn(3, [], 0)
    assert tr is not None
    assert tr["entry"] == 98.0, tr["entry"]
    assert tr["stop"] == 90.0, tr["stop"]
    assert abs(tr["remaining"] - 0.245) < 1e-12, tr["remaining"]
    assert tr["val_px"] == 108.0, tr["val_px"]

def test_squeeze_limit_order_not_filled_when_price_stays_above():
    """Contrôle négatif : la mèche la plus basse (101) ne touche jamais le
    point médian (100) -> aucun remplissage, l'ordre reste posé."""
    fn, state = _squeeze_factory(low_fill=101.0)
    assert fn(2, [], 0) is None
    assert fn(3, [], 0) is None
    assert state["squeeze_pending"] is not None

def test_squeeze_order_expires_after_SQUEEZE_LIFETIME_bars():
    """H-Squeeze-6, la seule hypothèse libre du mécanisme : l'ordre vit
    `SQUEEZE_LIFETIME` = 30 bougies. Posé à l'appel i=2, il porte
    `expires_at = 2 + 30 - 1 = 31`.

    - à i=31 (dernière bougie valide) une mèche à 50 DOIT encore remplir ;
    - à i=32 la même mèche à 50 ne doit PLUS rien remplir.
    Les deux moitiés sont testées, sinon un ordre qui n'expirerait jamais
    passerait le premier test."""
    assert SQUEEZE_LIFETIME == 30, SQUEEZE_LIFETIME

    fn, state = _squeeze_factory(fill_bar=31, low_fill=50.0, o_fill=200.0)
    assert fn(2, [], 0) is None
    tr = fn(31, [], 0)
    assert tr is not None, "à i=31 l'ordre est encore vivant"
    assert tr["entry"] == 100.0, tr["entry"]

    fn2, state2 = _squeeze_factory(fill_bar=32, low_fill=50.0, o_fill=200.0)
    assert fn2(2, [], 0) is None
    assert fn2(32, [], 0) is None, "à i=32 l'ordre a expiré, il ne doit plus remplir"
    assert state2["squeeze_pending"] is None, "l'ordre expiré doit être retiré"

def test_squeeze_disabled_by_default_no_behavior_change():
    """Non-régression explicite (le défaut est OFF) : sur EXACTEMENT le même
    scénario que le test nominal, mais sans passer les tableaux de la
    variante, la factory ne produit RIEN -- ni à la bougie d'armement ni à
    celle qui aurait rempli l'ordre. Confirme que la tranche obtenue dans le
    test nominal vient bien du nouveau chemin, et que les 19 appelants
    existants (qui n'passent aucun de ces tableaux) sont inchangés."""
    fn, state = _squeeze_factory(enabled=False)
    assert fn(2, [], 0) is None
    assert fn(3, [], 0) is None
    assert "squeeze_pending" not in state, state

def test_squeeze_half_configured_raises():
    """Une variante activée à moitié doit échouer explicitement plutôt que de
    se dégrader en silence en un mécanisme qui n'est plus celui du corpus
    (même discipline que le gate "espace libre" de `trend_table.py`)."""
    n = 8
    arrays = dict(
        atr_v=np.ones(n), ctx_support_v=np.full(n, 1.0), local_range_v=np.ones(n),
        context_range_v=np.ones(n), n_borders_v=np.zeros(n), high=np.ones(n),
        o=np.ones(n), score=np.full(n, 2.0))
    try:
        make_open_tranche_fn(
            arrays["atr_v"], arrays["ctx_support_v"], arrays["local_range_v"],
            arrays["context_range_v"], arrays["n_borders_v"], arrays["high"],
            arrays["o"], arrays["score"], 0, 3, 3, 3, 0.5, 0.02,
            {"last_pyramid_high": -np.inf},
            squeeze_armed_v=np.zeros(n, dtype=bool))   # les 3 autres manquent
    except ValueError:
        return
    raise AssertionError("un armement sans mid/sup/low doit lever ValueError")

# ---------------------------------------------------------------------------
# Chantier d'architecture (cf. PLAN.md, section dédiée) : `val_close_frac`/
# `conf_close_frac` PAR TRANCHE (`tr.get(...)`) et `risk_pct` en array,
# strictement additifs -- débloque le tableau Range Tendanciel (§3bis) et le
# sizing par confiance sans changer le comportement d'aucun appelant existant.
# ---------------------------------------------------------------------------
def test_process_tranche_reads_val_conf_close_frac_from_tr_when_present():
    """Si `tr` porte ses PROPRES `val_close_frac`/`conf_close_frac`, ils
    priment sur les paramètres scalaires passés à `process_tranche` --
    prouvé en passant des scalaires OPPOSÉS (0.0) à ceux stockés dans `tr`
    (1.0) : si `tr` ne primait pas, rien ne se clôturerait à la Validation."""
    tr = make_tranche(entry=100.0, stop=90.0, remaining=1.0,
                       val_px=105.0, conf_px=115.0, lim_px=130.0)
    tr["val_close_frac"] = 1.0
    tr["conf_close_frac"] = 1.0
    o = np.array([100.0, 106.0])
    low = np.array([99.0, 105.0])
    c = np.array([100.0, 106.0])
    closed, fee_frac, realized = process_tranche(
        tr, 1, o, low, c, long_signal_prev=True,
        val_close_frac=0.0, conf_close_frac=0.0, conf_to_be=True,
    )
    assert tr["val_done"] is True
    assert abs(fee_frac - 1.0) < 1e-9, (
        f"fee_frac={fee_frac}, attendu 1.0 -- tr['val_close_frac']=1.0 aurait dû primer "
        "sur le paramètre scalaire val_close_frac=0.0"
    )
    assert closed is True and abs(tr["remaining"] - 0.0) < 1e-9

def test_process_tranche_falls_back_to_scalar_args_when_tr_has_no_override():
    """Non-régression explicite : un `tr` SANS ces 2 clés (comportement de
    TOUS les appelants existants, `make_open_tranche_fn` compris tant que
    `val_close_frac_v`/`conf_close_frac_v` ne sont pas fournis) doit se
    comporter EXACTEMENT comme avant ce chantier -- paramètres scalaires
    utilisés tels quels."""
    tr = make_tranche(entry=100.0, stop=90.0, remaining=1.0,
                       val_px=105.0, conf_px=115.0, lim_px=130.0)
    assert "val_close_frac" not in tr and "conf_close_frac" not in tr
    o = np.array([100.0, 106.0])
    low = np.array([99.0, 105.0])
    c = np.array([100.0, 106.0])
    closed, fee_frac, realized = process_tranche(
        tr, 1, o, low, c, long_signal_prev=True,
        val_close_frac=0.5, conf_close_frac=0.5, conf_to_be=True,
    )
    assert tr["val_done"] is True
    assert abs(fee_frac - 0.5) < 1e-9, f"fee_frac={fee_frac}, attendu 0.5 (paramètre scalaire, tr sans clé)"

def _confidence_factory(risk_pct, val_close_frac_v=None, conf_close_frac_v=None):
    n = 6
    atr_v = np.ones(n)
    ctx_support_v = np.full(n, 90.0)
    local_range_v = np.full(n, 10.0)
    context_range_v = np.full(n, 20.0)
    n_borders_v = np.full(n, 5.0)
    high = np.full(n, 101.0)
    o = np.full(n, 100.0)
    score = np.full(n, 3.0)
    state = {"last_pyramid_high": -np.inf}
    fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v,
        high, o, score, 0, 3, 3, 99, 1.0, risk_pct, state,
        val_close_frac_v=val_close_frac_v, conf_close_frac_v=conf_close_frac_v,
    )
    return fn, state

def test_open_tranche_fn_risk_pct_accepts_per_bar_array():
    """`risk_pct` en array : la taille de la tranche ouverte à la bougie `i`
    doit utiliser `risk_pct[i-1]` (résolu à l'ouverture), PAS une moyenne ni
    une valeur d'une autre bougie -- comparé au calcul manuel exact."""
    n = 6
    risk_pct_v = np.array([0.01, 0.01, 0.05, 0.01, 0.01, 0.01])   # 0.05 à j=2
    fn, state = _confidence_factory(risk_pct_v)
    tr = fn(3, [], 0)   # j = i-1 = 2 -> risk_pct[2] = 0.05
    assert tr is not None
    stop_pct = (100.0 - 90.0) / 100.0   # ctx_support_v=90, entry=o[3]=100
    expected_size = min(1.0 / 3, 0.05 / stop_pct)
    assert abs(tr["remaining"] - expected_size) < 1e-9, (
        f"remaining={tr['remaining']}, attendu {expected_size} (risk_pct[j=2]=0.05, pas le "
        "scalaire ni une autre bougie de l'array)"
    )

def test_open_tranche_fn_stores_val_conf_close_frac_when_arrays_given():
    """Si `val_close_frac_v`/`conf_close_frac_v` sont fournis, la tranche
    ouverte doit porter EXACTEMENT `array[j]` dans ses propres clés -- pour
    que `process_tranche` les lise ensuite via `tr.get(...)` toute la vie de
    la tranche (cf. tête de fichier de `position_engine.py`)."""
    n = 6
    vcf_v = np.array([0.1, 0.1, 0.3, 0.1, 0.1, 0.1])
    ccf_v = np.array([0.2, 0.2, 0.4, 0.2, 0.2, 0.2])
    fn, state = _confidence_factory(0.02, val_close_frac_v=vcf_v, conf_close_frac_v=ccf_v)
    tr = fn(3, [], 0)   # j = 2
    assert tr is not None
    assert abs(tr["val_close_frac"] - 0.3) < 1e-9, tr.get("val_close_frac")
    assert abs(tr["conf_close_frac"] - 0.4) < 1e-9, tr.get("conf_close_frac")

def test_open_tranche_fn_scalar_risk_pct_and_no_frac_arrays_unchanged():
    """Non-régression explicite : sans `val_close_frac_v`/`conf_close_frac_v`
    et avec `risk_pct` scalaire (les 9+ appelants existants), la tranche
    ouverte ne doit PORTER AUCUNE des 2 nouvelles clés -- `process_tranche`
    retombera donc sur ses paramètres scalaires, comportement historique
    inchangé."""
    fn, state = _confidence_factory(0.02)
    tr = fn(3, [], 0)
    assert tr is not None
    assert "val_close_frac" not in tr and "conf_close_frac" not in tr

TESTS = [
    test_validation_confirmation_limite_sequence,
    test_immediate_stop_loss,
    test_no_breakeven_before_confirmation,
    test_trigger_on_close_not_on_wick,
    test_pyramiding_two_tranches,
    test_reverse_at_limit_sequence,
    test_reverse_disabled_by_default_no_behavior_change,
    test_process_reverse_stop_on_wick_and_target_on_close,
    test_wide_channel_halves_stop_and_leaves_exposure_constant,
    test_wide_channel_halving_applies_before_the_per_tranche_cap,
    test_wide_channel_none_and_all_false_are_identical,
    test_wide_channel_is_read_at_j_equals_i_minus_1_causal,
    test_wide_channel_fractions_are_the_two_halves_of_the_source,
    test_context_channel_median_is_the_midpoint_hand_computed,
    test_structural_conf_uses_moving_level_read_at_i_minus_1,
    test_structural_conf_nan_level_is_unreachable,
    test_structural_conf_only_moves_conf_px,
    test_structural_conf_off_by_default_is_bit_identical,
    test_context_median_frac_is_the_literal_50_percent,
    test_squeezed_third_border_positive_case_hand_computed,
    test_squeezed_third_border_negative_case_retracement_invalidates,
    test_squeezed_third_border_requires_the_1_to_1_ratio,
    test_squeeze_limit_order_fills_with_hand_computed_levels,
    test_squeeze_limit_order_fills_at_the_open_on_a_gap,
    test_squeeze_limit_order_not_filled_when_price_stays_above,
    test_squeeze_order_expires_after_SQUEEZE_LIFETIME_bars,
    test_squeeze_disabled_by_default_no_behavior_change,
    test_squeeze_half_configured_raises,
    test_process_tranche_reads_val_conf_close_frac_from_tr_when_present,
    test_process_tranche_falls_back_to_scalar_args_when_tr_has_no_override,
    test_open_tranche_fn_risk_pct_accepts_per_bar_array,
    test_open_tranche_fn_stores_val_conf_close_frac_when_arrays_given,
    test_open_tranche_fn_scalar_risk_pct_and_no_frac_arrays_unchanged,
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
