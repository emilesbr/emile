"""
Tests unitaires de la table "trade de tendance" (trend_table.py), sur le
modèle de test_position_engine.py : cas calculés à la main (voir commentaires
"calcul attendu" + `fractions.Fraction` pour vérifier les calculs
indépendamment du code testé, pas en reformulant la même formule), aucune
donnée réelle. Exécution : `python3 test_trend_table.py`.

Les fonctions testées (`add_leg`, `make_campaign`, `step_campaign`,
`try_open_campaign`, `step_reverse`) ne recalculent AUCUN indicateur -- elles
reçoivent des événements déjà résolus (`ev`), exactement comme
`process_tranche` reçoit `long_signal_prev` déjà résolu. C'est ce qui permet
de leur fournir des scénarios entièrement maîtrisés ici.
"""
from fractions import Fraction as F

import numpy as np
import pytest

from emile.core.trend_table import (
    add_leg, make_campaign, step_campaign, try_open_campaign, step_reverse,
    PROFILES_TREND, MAX_CAMPAIGN_RISK_PCT,
    free_room_frac, breakout_space_ok, attach_obstacle_level, CLOSURE_DELAY,
    compute_suivi_conditions, SUIVI_MAX,
)

def fclose(a, b, tol=1e-9):
    return abs(a - b) < tol

# ---------------------------------------------------------------------------
# Test 1 : add_leg plafonne au risque de campagne (H3, 5% du capital)
# ---------------------------------------------------------------------------
def test_add_leg_risk_cap():
    """entry=100, stop=98 (distance 2%) -> max_total_remaining = 0.05/0.02 = 2.5
    (calcul indépendant via Fraction). Demander +1.0 (100% de U) doit être
    accepté intégralement (1.0 <= 2.5, pas de plafonnement). Demander ensuite
    +2.0 de plus (remaining passerait à 3.0 > 2.5) doit être RÉDUIT à 1.5
    (2.5 - 1.0), pas rejeté ni accepté en entier."""
    campaign = make_campaign(entry=100.0, stop=98.0)
    cap = F(5, 100) / (F(100 - 98, 1) / F(100, 1))
    assert cap == F(5, 2), f"cap attendu 2.5, calculé {cap}"

    actual1 = add_leg(campaign, 1.0, 100.0)
    assert fclose(actual1, 1.0), f"1re jambe attendue non plafonnée (1.0), obtenu {actual1}"
    assert fclose(campaign["remaining"], 1.0)
    assert fclose(campaign["entry"], 100.0)

    actual2 = add_leg(campaign, 2.0, 100.0)
    expected_actual2 = float(cap) - 1.0  # 2.5 - 1.0 = 1.5
    assert fclose(actual2, expected_actual2), f"2e jambe attendue plafonnée à {expected_actual2}, obtenu {actual2}"
    assert fclose(campaign["remaining"], float(cap)), f"remaining attendu {float(cap)}, obtenu {campaign['remaining']}"

    # Toute jambe supplémentaire est désormais intégralement bloquée (cap atteint)
    actual3 = add_leg(campaign, 0.5, 100.0)
    assert actual3 == 0.0, f"jambe attendue totalement bloquée (cap déjà atteint), obtenu {actual3}"

# ---------------------------------------------------------------------------
# Test 2 : add_leg calcule un prix d'entrée moyen pondéré (H2)
# ---------------------------------------------------------------------------
def test_add_leg_blended_entry_price():
    """Stop à 5% de distance (95) -> cap = 0.05/0.05 = 1.0 (pas de plafonnement
    pour ce test, jambes cumulées = 0.25+0.75=1.0 exactement).
    Jambe 1 : 0.25 à 100 puis jambe 2 : 0.75 à 110.
    Prix moyen pondéré attendu = (100*0.25 + 110*0.75) / 1.0 = 107.5
    (calcul Fraction indépendant : (25 + 82.5)/1 = 107.5)."""
    campaign = make_campaign(entry=100.0, stop=95.0)
    a1 = add_leg(campaign, 0.25, 100.0)
    assert fclose(a1, 0.25)
    assert fclose(campaign["entry"], 100.0)
    assert fclose(campaign["remaining"], 0.25)

    a2 = add_leg(campaign, 0.75, 110.0)
    expected_entry = float(F(100, 1) * F(25, 100) + F(110, 1) * F(75, 100)) / 1.0
    assert fclose(a2, 0.75), f"jambe 2 attendue non plafonnée (0.75), obtenu {a2}"
    assert fclose(campaign["remaining"], 1.0)
    assert fclose(campaign["entry"], expected_entry), f"entrée moyenne attendue {expected_entry}, obtenu {campaign['entry']}"
    assert fclose(campaign["entry"], 107.5)

# ---------------------------------------------------------------------------
# Test 3 : séquence complète Accumulation -> Breakout -> Divergence ->
# Pull-Back -> Excès final, profil AGRESSIF (le seul qui exerce une action
# non nulle à CHAQUE étape sauf +Reverse -- testé séparément, test 4).
# ---------------------------------------------------------------------------
def test_full_sequence_agressif():
    """Profil AGRESSIF : accum_frac=0.50, breakout_frac=1.50, div_close_frac=
    0.25 (pas de BE), pullback_frac=0.50. Stop fixé à l'Accumulation (98,
    depuis une entrée à 100) et jamais remonté (div_to_be=False pour ce
    profil) -- donc le risque de campagne (H3) est réévalué à chaque ajout
    contre ce MÊME stop fixe et l'entrée moyenne pondérée COURANTE (qui, elle,
    grimpe à mesure que des jambes sont ajoutées à des prix plus hauts).

    Étape 1 -- Accumulation (entrée 100, stop 98) :
      add_leg(0.50, 100) -> remaining=0.50, entry=100 (cap=0.05/0.02=2.5, pas
      de plafonnement, 0.50 <= 2.5).

    Étape 2 -- Breakout (open=110) :
      add_leg(1.50, 110) -> cap recalculé contre l'ENTRÉE D'AVANT l'ajout
      (100, puisque remaining>0 utilise l'entrée courante AVANT ce call) :
      cap=2.5, room=2.5-0.50=2.0, 1.50<=2.0 -> pas de plafonnement.
      remaining=0.50+1.50=2.00.
      entry = (100*0.50 + 110*1.50)/2.00 = (50+165)/2 = 107.5.
      swing_high fixé au high de la bougie de breakout = 112.0.

    Étape 3 -- Divergence (close=114, high=115 -> swing_high màj à 115) :
      close_amt = 2.00*0.25 = 0.50 (div_close_frac).
      pnl = (114-107.5)/107.5 = 6.5/107.5.
      contribution pnl_accum = pnl*0.50 = 3.25/107.5 = 0.0302325581395349...
      remaining = 2.00-0.50 = 1.50. stop INCHANGÉ (98, div_to_be=False).

    Étape 4 -- Pull-Back, repli observé (close=112.5) :
      impulse = swing_high(115) - entry(107.5) = 7.5.
      retracement = (115-112.5)/7.5 = 2.5/7.5 = 0.3333... -> dans [0.23,0.38]
      -> pullback_low_seen = True. recovery = (112.5-112.5)/2.5 = 0 -> pas
      encore déclenché.

    Étape 5 -- Pull-Back, reprise confirmée (close=114.0, open=114.2) :
      recovery = (114-112.5)/(115-112.5) = 1.5/2.5 = 0.6 >= 0.50 -> pullback
      event déclenché -> add_leg(0.50, 114.2). MAIS : cap recalculé contre
      l'entrée COURANTE (107.5, remaining>0) et le MÊME stop fixe (98) :
      stop_dist_pct = (107.5-98)/107.5 = 9.5/107.5 = 0.0883720930...
      cap = 0.05/0.0883720930... = 0.5658914728...
      room = cap - remaining(1.50) = NÉGATIF -> add_leg retourne 0.0 (jambe
      intégralement bloquée par le plafond de risque H3, malgré un profil qui
      prescrit "Renfort +50%") -- résultat honnête et attendu de H3, pas un
      bug : après un fort mouvement depuis l'entrée moyenne, le stop FIXE
      représente une distance relative bien plus grande qu'à l'origine,
      donc le plafond de 5% de risque global se resserre mécaniquement.
      remaining reste 1.50, entry reste 107.5. stage -> EXCESS_WATCH quand
      même (l'événement de marché a bien eu lieu, seule la taille est capée).

    Étape 6 -- Excès final (close=120.0) :
      pnl = (120-107.5)/107.5 = 12.5/107.5 = 0.1162790697...
      contribution = pnl*remaining(1.50) = 0.1744186046...
      pnl_accum TOTAL = 0.0302325581... + 0.1744186046... = 0.2046511627...
      remaining -> 0, campagne clôturée, reverse=False (profil AGRESSIF) ->
      pas de reverse_request.
    """
    p = PROFILES_TREND["AGRESSIF"]

    # --- Accumulation ---
    campaign, fee0 = try_open_campaign(
        i=0, o=[100.0], ctx_support_prev=98.0, accumulation_active=True, profile=p,
    )
    assert campaign is not None
    assert fclose(fee0, 0.50)
    assert fclose(campaign["remaining"], 0.50)
    assert fclose(campaign["entry"], 100.0)
    assert campaign["stop"] == 98.0
    assert campaign["stage"] == "ACCUMULATION"

    # --- Breakout ---
    ev = {"regime_excess": False, "breakout_raw": True}
    closed, fee_frac, realized, rev = step_campaign(
        campaign, 0, o=[110.0], high=[112.0], low=[109.0], c=[111.0], ev=ev, profile=p,
    )
    assert closed is False and realized is None and rev is None
    assert fclose(fee_frac, 1.50), f"fee_frac attendu 1.50, obtenu {fee_frac}"
    assert fclose(campaign["remaining"], 2.00)
    assert fclose(campaign["entry"], 107.5)
    assert campaign["stage"] == "POST_BREAKOUT"
    assert fclose(campaign["swing_high"], 112.0)

    # --- Divergence ---
    ev = {"regime_excess": False, "divergence_raw": True}
    closed, fee_frac, realized, rev = step_campaign(
        campaign, 0, o=[0.0], high=[115.0], low=[113.0], c=[114.0], ev=ev, profile=p,
    )
    assert closed is False and realized is None and rev is None
    expected_close_amt = 0.50
    assert fclose(fee_frac, expected_close_amt), f"fee_frac attendu {expected_close_amt}, obtenu {fee_frac}"
    expected_pnl_accum_1 = float(F(65, 10) / F(1075, 10) * F(1, 2))  # 6.5/107.5 * 0.5
    assert fclose(campaign["pnl_accum"], expected_pnl_accum_1), (
        f"pnl_accum attendu {expected_pnl_accum_1}, obtenu {campaign['pnl_accum']}"
    )
    assert fclose(campaign["remaining"], 1.50)
    assert campaign["stop"] == 98.0, "stop ne doit PAS bouger (div_to_be=False pour AGRESSIF)"
    assert campaign["stage"] == "PULLBACK_WATCH"
    assert fclose(campaign["swing_high"], 115.0)

    # --- Pull-Back : repli observé, pas encore de reprise ---
    ev = {"regime_excess": False}
    closed, fee_frac, realized, rev = step_campaign(
        campaign, 0, o=[0.0], high=[113.0], low=[112.0], c=[112.5], ev=ev, profile=p,
    )
    assert closed is False and fee_frac == 0.0 and realized is None
    assert campaign["pullback_low_seen"] is True
    assert campaign["stage"] == "PULLBACK_WATCH"
    assert fclose(campaign["remaining"], 1.50), "aucune taille ne doit bouger avant confirmation de la reprise"

    # --- Pull-Back : reprise confirmée -> add_leg capé à 0 par H3 (cf. docstring) ---
    ev = {"regime_excess": False}
    closed, fee_frac, realized, rev = step_campaign(
        campaign, 0, o=[114.2], high=[114.5], low=[113.8], c=[114.0], ev=ev, profile=p,
    )
    assert closed is False and realized is None and rev is None
    assert fee_frac == 0.0, f"fee_frac attendu 0.0 (jambe intégralement capée par H3), obtenu {fee_frac}"
    assert fclose(campaign["remaining"], 1.50), "remaining ne doit PAS changer (jambe capée à 0)"
    assert fclose(campaign["entry"], 107.5), "entrée moyenne inchangée (aucune jambe réellement ajoutée)"
    assert campaign["stage"] == "EXCESS_WATCH", "l'étape avance quand même (l'événement a eu lieu, seule la taille est capée)"

    # --- Excès final : clôture totale ---
    ev = {"regime_excess": False, "excess_raw": True, "reverse_stop": 130.0, "reverse_target": 100.0}
    closed, fee_frac, realized, rev = step_campaign(
        campaign, 0, o=[0.0], high=[121.0], low=[119.0], c=[120.0], ev=ev, profile=p,
    )
    assert closed is True
    assert rev is None, "AGRESSIF ne prévoit pas +Reverse"
    assert fclose(fee_frac, 1.50)
    expected_final_contrib = float(F(125, 10) / F(1075, 10) * F(3, 2))  # 12.5/107.5 * 1.50
    expected_total = expected_pnl_accum_1 + expected_final_contrib
    assert fclose(realized, expected_total), f"P&L total attendu {expected_total}, obtenu {realized}"
    assert fclose(campaign["remaining"], 0.0)

# ---------------------------------------------------------------------------
# Test 4 : mécanisme "+Reverse" (H10, profil TRES_AGRESSIF uniquement)
# ---------------------------------------------------------------------------
def test_reverse_mechanism_tres_agressif():
    """Campagne déjà en EXCESS_WATCH (entry=100, remaining=1.0, pnl_accum=0
    -- comme si aucune clôture partielle n'avait eu lieu avant, pour isoler
    le mécanisme). Excès final à close=102 :
      pnl = (102-100)/100 = 0.02 -> pnl_accum final = 0.02.
      reverse : r_entry=102, r_stop=105 (fourni via ev), r_stop_dist =
      (105-102)/102 = 3/102 = 0.0294117647...
      r_frac = min(1.0, risk_pct(0.05)/0.0294117647...) = min(1.0, 1.7) = 1.0
      (plafonné à 100% du capital, pas au risk_pct brut).
      fee_frac total attendu = remaining(1.0) + r_frac(1.0) = 2.0."""
    p = PROFILES_TREND["TRES_AGRESSIF"]
    assert p["reverse"] is True
    campaign = make_campaign(entry=100.0, stop=90.0)
    campaign["stage"] = "EXCESS_WATCH"
    campaign["remaining"] = 1.0
    campaign["swing_high"] = 100.0  # non utilisé par ce test, requis par le champ interne

    ev = {"regime_excess": False, "excess_raw": True, "reverse_stop": 105.0, "reverse_target": 95.0}
    closed, fee_frac, realized, rev = step_campaign(
        campaign, 0, o=[0.0], high=[103.0], low=[101.0], c=[102.0], ev=ev, profile=p,
    )
    assert closed is True
    assert fclose(realized, 0.02), f"P&L attendu 0.02, obtenu {realized}"
    r_stop_dist = float(F(3, 102))
    raw_ratio = 0.05 / r_stop_dist
    expected_r_frac = min(1.0, raw_ratio)
    assert raw_ratio > 1.0, "cette configuration doit exercer le plafond à 100% (risk_pct brut > 1.0)"
    assert rev is not None
    assert fclose(rev["entry"], 102.0) and rev["stop"] == 105.0 and rev["target"] == 95.0
    assert fclose(rev["frac"], 1.0), f"frac de reverse attendue plafonnée à 1.0, obtenu {rev['frac']}"
    assert fclose(fee_frac, 1.0 + 1.0), f"fee_frac attendu 2.0, obtenu {fee_frac}"

    # step_reverse : le stop est touché en premier (mèche haute >= stop)
    closed_r, frac_r, pnl_r = step_reverse(rev, 0, high=[106.0], low=[104.0], c=[104.5])
    assert closed_r is True
    expected_pnl_stop = (rev["entry"] - rev["stop"]) / rev["entry"]  # (102-105)/102, négatif
    assert expected_pnl_stop < 0
    assert fclose(pnl_r, expected_pnl_stop)
    assert fclose(frac_r, 1.0)

    # step_reverse : la cible est touchée (stop jamais atteint)
    closed_r2, frac_r2, pnl_r2 = step_reverse(rev, 0, high=[103.0], low=[94.0], c=[95.0])
    assert closed_r2 is True
    expected_pnl_target = (rev["entry"] - 95.0) / rev["entry"]  # (102-95)/102, positif
    assert expected_pnl_target > 0
    assert fclose(pnl_r2, expected_pnl_target)

# ---------------------------------------------------------------------------
# Test 5 : le stop de protection (Extreme Channel, H4) se déclenche sur MÈCHE
# et clôture tout le restant, quelle que soit l'étape en cours.
# ---------------------------------------------------------------------------
def test_protective_stop_triggers_on_wick():
    """Campagne en POST_BREAKOUT, entry=107.5, stop=98, remaining=2.0,
    pnl_accum=0 (aucune clôture partielle avant). La mèche basse touche 97
    (<=98) -> clôture totale au niveau du STOP (98), pas au plus bas (97).
      pnl = (98-107.5)/107.5 = -9.5/107.5 = -0.0883720930...
      contribution = pnl*2.0 = -0.1767441860..."""
    p = PROFILES_TREND["AGRESSIF"]
    campaign = make_campaign(entry=107.5, stop=98.0)
    campaign["stage"] = "POST_BREAKOUT"
    campaign["remaining"] = 2.0
    campaign["swing_high"] = 112.0

    ev = {"regime_excess": False, "divergence_raw": False}
    closed, fee_frac, realized, rev = step_campaign(
        campaign, 0, o=[0.0], high=[108.0], low=[97.0], c=[99.0], ev=ev, profile=p,
    )
    assert closed is True
    assert rev is None
    expected_pnl = float((F(98, 1) - F(1075, 10)) / F(1075, 10) * F(2, 1))
    assert fclose(realized, expected_pnl), f"P&L attendu {expected_pnl}, obtenu {realized}"
    assert fclose(fee_frac, 2.0)
    assert fclose(campaign["remaining"], 0.0)

# ---------------------------------------------------------------------------
# Test 6 : abandon en Accumulation si le régime bascule en EXCES (règle
# transverse "ne pas trader en excès") -- deux cas, rien engagé vs. déjà
# engagé (profils FAIBLE vs MODERE).
# ---------------------------------------------------------------------------
def test_regime_excess_abandons_accumulation():
    # FAIBLE : accum_frac=0.0 -> rien n'était jamais engagé -> abandon "silencieux"
    p_faible = PROFILES_TREND["FAIBLE"]
    assert p_faible["accum_frac"] == 0.0
    campaign, fee0 = try_open_campaign(0, o=[100.0], ctx_support_prev=98.0, accumulation_active=True, profile=p_faible)
    assert fclose(fee0, 0.0)
    assert fclose(campaign["remaining"], 0.0)

    ev = {"regime_excess": True}
    closed, fee_frac, realized, rev = step_campaign(campaign, 0, o=[0.0], high=[0.0], low=[200.0], c=[100.0], ev=ev, profile=p_faible)
    assert closed is True
    assert fee_frac == 0.0 and realized is None and rev is None, "rien n'était engagé -- pas un trade"

    # MODERE : accum_frac=0.25 -> déjà engagé -> abandon RÉALISE le P&L courant
    p_modere = PROFILES_TREND["MODERE"]
    campaign2, fee1 = try_open_campaign(0, o=[100.0], ctx_support_prev=98.0, accumulation_active=True, profile=p_modere)
    assert fclose(fee1, 0.25)
    assert fclose(campaign2["remaining"], 0.25)
    ev = {"regime_excess": True}
    closed2, fee_frac2, realized2, rev2 = step_campaign(campaign2, 0, o=[0.0], high=[0.0], low=[200.0], c=[103.0], ev=ev, profile=p_modere)
    assert closed2 is True
    expected_pnl = float((F(103, 1) - F(100, 1)) / F(100, 1) * F(1, 4))  # (103-100)/100 * 0.25
    assert fclose(realized2, expected_pnl), f"P&L attendu {expected_pnl}, obtenu {realized2}"
    assert fclose(fee_frac2, 0.25)

# ---------------------------------------------------------------------------
# Test 7 : sémantique de `free_room_frac` (H16) -- un niveau DÉJÀ SOUS le prix
# n'est pas un obstacle (marge non bornée), un niveau inconnu reste inconnu.
# ---------------------------------------------------------------------------
def test_free_room_frac_semantics():
    """prix=100 : niveau 110 -> marge 10/100 = 0.10 (vérifié par Fraction,
    pas en reformulant la formule) ; niveau 95 ou 100 -> déjà franchi ->
    +inf ; niveau NaN -> NaN (vérification impossible, PAS 'espace libre')."""
    assert fclose(free_room_frac(110.0, 100.0), float(F(10, 100)))
    assert fclose(free_room_frac(101.5, 100.0), float(F(15, 1000)))
    assert free_room_frac(95.0, 100.0) == float("inf"), "niveau sous le prix = plus un obstacle"
    assert free_room_frac(100.0, 100.0) == float("inf"), "niveau AU prix = déjà atteint, plus un obstacle"
    nan_room = free_room_frac(float("nan"), 100.0)
    assert nan_room != nan_room, "niveau inconnu -> NaN, jamais +inf"
    nan_room2 = free_room_frac(110.0, 0.0)
    assert nan_room2 != nan_room2, "prix invalide -> NaN"

# ---------------------------------------------------------------------------
# Test 8 : gate "espace libre" MTF avant breakout (H13-H16), Ratio 1:1
# ---------------------------------------------------------------------------
def test_breakout_space_ok_ratio_1_1():
    """Prix de cassure 100, amplitude du range local 8 -> rendement escompté
    = 8/100 = 0.08 (H15). Au Ratio 1:1 (mult=1.0) il faut donc >= 8% de
    marge SUR CHACUN des deux niveaux supérieurs. Tous les seuils ci-dessous
    sont calculés à la main via Fraction, pas repris de la fonction."""
    exp_ret = float(F(8, 100))
    needed = exp_ret  # mult = 1.0

    # UT+1 à 110 (marge 10%) et UT+2 à 130 (marge 30%) : 10% et 30% >= 8% -> OK
    assert float(F(10, 100)) >= needed and float(F(30, 100)) >= needed
    assert breakout_space_ok(100.0, exp_ret, (110.0, 130.0)) is True

    # UT+1 à 107 (marge 7% < 8%) : bloqué, même si l'UT+2 est très dégagée
    assert float(F(7, 100)) < needed
    assert breakout_space_ok(100.0, exp_ret, (107.0, 130.0)) is False

    # UT+2 à 105 (marge 5% < 8%) : bloqué aussi -> la condition est bien un ET
    assert breakout_space_ok(100.0, exp_ret, (130.0, 105.0)) is False

    # Niveau déjà franchi (95 < 100) : ce n'est plus un obstacle (H16) -> OK
    assert breakout_space_ok(100.0, exp_ret, (95.0, 130.0)) is True
    assert breakout_space_ok(100.0, exp_ret, (95.0, 92.0)) is True

    # Donnée manquante sur un niveau -> ÉCHEC (on ne peut pas "vérifier")
    assert breakout_space_ok(100.0, exp_ret, (float("nan"), 130.0)) is False
    # Rendement escompté inexploitable -> ÉCHEC
    assert breakout_space_ok(100.0, float("nan"), (110.0, 130.0)) is False
    assert breakout_space_ok(100.0, 0.0, (110.0, 130.0)) is False

    # Sensibilité du multiplicateur : à 1.5x il faut 12% -> 10% ne suffit plus
    assert breakout_space_ok(100.0, exp_ret, (110.0, 130.0), mult=1.5) is False
    assert breakout_space_ok(100.0, exp_ret, (113.0, 130.0), mult=1.5) is True
    # À 0.5x il faut 4% -> 105 (5%) suffit
    assert breakout_space_ok(100.0, exp_ret, (105.0, 130.0), mult=0.5) is True

# ---------------------------------------------------------------------------
# Test 9 : effet du gate DANS la machine à états, et non-régression de tout
# appelant qui ne fournit pas la clé (H13 : `unified_protocol.py` réplique ce
# dict `ev` sans elle et doit rester bit-à-bit identique)
# ---------------------------------------------------------------------------
def test_step_campaign_breakout_space_gate():
    p = PROFILES_TREND["MODERE"]  # accum_frac=0.25, breakout_frac=1.00

    def fresh():
        campaign = make_campaign(entry=100.0, stop=95.0)
        add_leg(campaign, p["accum_frac"], 100.0)
        assert fclose(campaign["remaining"], 0.25)
        return campaign

    base_ev = {"regime_excess": False, "breakout_raw": True}

    # (a) Gate ABSENT de `ev` -> comportement historique : le breakout passe.
    c_a = fresh()
    closed, fee_a, realized, rev = step_campaign(
        c_a, 0, o=[102.0], high=[103.0], low=[101.0], c=[102.5], ev=dict(base_ev), profile=p)
    assert closed is False and realized is None and rev is None
    assert c_a["stage"] == "POST_BREAKOUT", "sans la clé, le gate ne doit RIEN changer"
    assert fee_a > 0.0

    # (b) Gate présent et VRAI -> strictement identique à (a)
    c_b = fresh()
    _, fee_b, _, _ = step_campaign(
        c_b, 0, o=[102.0], high=[103.0], low=[101.0], c=[102.5],
        ev={**base_ev, "breakout_space_ok": True}, profile=p)
    assert c_b["stage"] == "POST_BREAKOUT"
    assert fclose(fee_b, fee_a) and fclose(c_b["remaining"], c_a["remaining"])
    assert fclose(c_b["entry"], c_a["entry"])

    # (c) Gate présent et FAUX -> le breakout est REFUSÉ : l'étape ne change
    #     pas, aucune jambe n'est ajoutée, aucun frais n'est payé, et la
    #     campagne reste vivante en Accumulation (pas clôturée).
    c_c = fresh()
    closed_c, fee_c, realized_c, rev_c = step_campaign(
        c_c, 0, o=[102.0], high=[103.0], low=[101.0], c=[102.5],
        ev={**base_ev, "breakout_space_ok": False}, profile=p)
    assert closed_c is False and realized_c is None and rev_c is None
    assert c_c["stage"] == "ACCUMULATION", "breakout sans espace libre -> on reste en Accumulation"
    assert fee_c == 0.0, "aucun frais quand aucune jambe n'est ajoutée"
    assert fclose(c_c["remaining"], 0.25) and fclose(c_c["entry"], 100.0)
    assert "swing_high" not in c_c, "swing_high ne doit être initialisé qu'au vrai passage du breakout"

# ---------------------------------------------------------------------------
# Test 10 : `attach_obstacle_level` ne regarde JAMAIS une bougie supérieure
# non encore clôturée (série synthétique à vérité terrain connue)
# ---------------------------------------------------------------------------
def test_attach_obstacle_level_no_lookahead():
    """3 bougies "UT supérieure" datées 01/01, 02/01, 03/01 avec des
    `ctx_resistance` distincts (10, 20, 30) et un délai de clôture de 1 jour
    (CLOSURE_DELAY, cf. `backtest_phase2_ut2.py`) -> disponibles à partir du
    02/01, 03/01, 04/01 respectivement. Vérité terrain attendue, calculée à
    la main pour 5 instants de l'UT d'exécution."""
    import pandas as pd
    df_high = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        "ctx_resistance": [10.0, 20.0, 30.0],
    })
    low_dates = pd.to_datetime([
        "2024-01-01 12:00",   # aucune bougie supérieure encore close -> NaN
        "2024-01-02 00:00",   # la 1re devient disponible pile maintenant -> 10
        "2024-01-02 20:00",   # toujours la 1re -> 10
        "2024-01-03 04:00",   # la 2e est close depuis 03/01 00:00 -> 20
        "2024-01-05 00:00",   # la 3e (disponible 04/01) -> 30
    ])
    df_low = pd.DataFrame({"date": low_dates})
    got = attach_obstacle_level(df_low, df_high, CLOSURE_DELAY)
    assert got[0] != got[0], f"attendu NaN avant toute clôture supérieure, obtenu {got[0]}"
    assert list(got[1:]) == [10.0, 10.0, 20.0, 30.0], f"vérité terrain violée : {got}"

# ---------------------------------------------------------------------------
# Test 11 : la réplique vectorisée utilisée par le DIAGNOSTIC du gate est
# bien la même condition que celle du moteur (sur données réelles, bougie par
# bougie -- pas une reformulation approchée)
# ---------------------------------------------------------------------------
@pytest.mark.data_dependent
def test_raw_breakout_candidates_matches_engine_expression():
    import numpy as np
    from emile.backtests.backtest_phase2 import load_h1, resample
    from emile.backtests.backtest_phase2_v7 import prepare
    from emile.core.trend_table import (add_trend_context, load_volume, resample_volume,
                              raw_breakout_candidates, VOLUME_MA_WINDOW, VOLUME_EXPANSION_MULT)
    import pandas as pd

    h1 = load_h1("BTCUSDT")
    h4 = add_trend_context(prepare(resample(h1, "4h")))
    vol = resample_volume(load_volume("BTCUSDT"), "4h")
    got = raw_breakout_candidates(h4, vol)

    # Vérité terrain = l'expression LITTÉRALE du moteur (`ev["breakout_raw"]`
    # dans run_trend_table), réécrite ici en boucle scalaire.
    c = h4["close"].values
    local_high_v = h4["local_high"].values
    score_v = h4["score"].values
    vol_v = vol["volume"].values
    vol_ma = pd.Series(vol_v).rolling(VOLUME_MA_WINDOW).mean().values
    volume_expansion = vol_v > VOLUME_EXPANSION_MULT * np.roll(vol_ma, 1)
    volume_expansion[0] = False
    n_true = 0
    for i in range(1, len(h4)):
        expected = bool(c[i - 1] > local_high_v[i - 1] and volume_expansion[i - 1]
                        and score_v[i - 1] >= 2)
        assert bool(got[i]) == expected, f"divergence à i={i}: {got[i]} vs {expected}"
        n_true += expected
    assert n_true > 0, "aucune bougie candidate trouvée -- le test ne vérifierait rien"

# ---------------------------------------------------------------------------
# Test 12 : le gate exige EXPLICITEMENT les deux niveaux supérieurs -- il ne
# se dégrade pas silencieusement en "un seul niveau" ou en "pas de gate"
# (la citation porte sur UT+1 ET UT+2, cf. H13)
# ---------------------------------------------------------------------------
def test_breakout_space_gate_requires_both_levels():
    import pandas as pd
    from emile.core.trend_table import run_trend_table
    df = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "open": [1.0],
                       "high": [1.0], "low": [1.0], "close": [1.0]})
    vol = pd.DataFrame({"date": df["date"], "volume": [1.0]})
    for kwargs in ({}, {"df_ut1": df}, {"df_ut2": df}):
        try:
            run_trend_table(df.copy(), vol.copy(), "MODERE",
                            use_breakout_space_gate=True, **kwargs)
        except ValueError as e:
            assert "df_ut1" in str(e) and "df_ut2" in str(e)
        else:
            raise AssertionError(f"ValueError attendue pour kwargs={list(kwargs)}")

# ---------------------------------------------------------------------------
# Test 13 : "Règle de l'Overlap" (#14 `STRUCTURES_ALTERATIONS.md:28`) — le
# NIVEAU est tracé par les EXTRÊMES, la CLÔTURE est le TEST, les mèches sont
# tolérées. Vérifie que c'est DÉJÀ la convention de `breakout_raw` (via sa
# réplique certifiée `raw_breakout_candidates`), pas une règle à ajouter.
#
# Citation vérifiée mot pour mot :
#   "Règle de l'Overlap : l'ancienne résistance devient support. C'est une
#    zone de tolérance, pas une ligne mathématique — les mèches peuvent
#    pénétrer l'ancien territoire, mais les clôtures de bougies doivent
#    rester à l'extérieur pour valider la structure."
#
# Trois assertions, dont un CONTRÔLE POSITIF explicite (sans lui, un test qui
# ne déclenche jamais passerait pour la mauvaise raison — même discipline que
# `test_ut2.py::test_no_bearish_regime_exists...` au round précédent) :
#   (a) niveau = extrêmes : `local_high` est le max glissant des HAUTS
#       décalé de 1, jamais un max de clôtures ;
#   (b) tolérance des mèches (contrôle NÉGATIF) : une bougie dont le HAUT
#       dépasse le niveau mais dont la CLÔTURE reste en dessous ne déclenche
#       RIEN ;
#   (c) contrôle POSITIF : la même bougie, clôture portée au-dessus du
#       niveau, déclenche bien.
# ---------------------------------------------------------------------------
def test_overlap_convention_already_in_breakout_raw():
    import numpy as np
    import pandas as pd
    from emile.core.trend_table import (add_trend_context, raw_breakout_candidates,
                              VOLUME_MA_WINDOW, VOLUME_EXPANSION_MULT)

    n = 120
    dates = pd.date_range("2024-01-01", periods=n, freq="4h")

    def frame(close_at_breakout: float) -> tuple:
        """Série synthétique plate, puis UNE bougie qui pique au-dessus du
        plus-haut local. `close_at_breakout` décide si la CLÔTURE dépasse ou
        non le niveau — c'est la seule chose qui change entre (b) et (c)."""
        high = np.full(n, 100.0)
        low = np.full(n, 99.0)
        close = np.full(n, 99.5)
        # i = 100 : mèche à 110 (bien au-dessus du plus-haut local = 100),
        # clôture pilotée par l'argument.
        i = 100
        high[i] = 110.0
        close[i] = close_at_breakout
        df = pd.DataFrame({
            "date": dates, "open": close, "high": high, "low": low, "close": close,
            # colonnes normalement posées par `prepare`, fournies directement
            # ici : ce test porte sur la CONVENTION de validation, pas sur le
            # proxy. `score >= 2` et l'expansion de volume sont donc rendus
            # vrais partout pour les neutraliser.
            "atr": np.full(n, 1.0),
            "ctx_support": np.full(n, 90.0),
            "score": np.full(n, 2.0),
        })
        df = add_trend_context(df)
        vol = pd.DataFrame({"date": dates, "volume": np.full(n, 1.0)})
        # expansion de volume : volume[i] > 1.5 * moyenne mobile décalée
        vol.loc[i, "volume"] = 10.0
        return df, vol, i

    # --- (a) le niveau vient des EXTRÊMES, pas des clôtures ---
    df, vol, i = frame(close_at_breakout=99.5)
    ts = df.set_index("date")
    expected_level = ts["high"].rolling("5D").max().shift(1).values
    got_level = df["local_high"].values
    m = np.isfinite(expected_level) & np.isfinite(got_level)
    assert m.sum() > 0, "aucun niveau calculé -- le test ne vérifierait rien"
    assert np.allclose(got_level[m], expected_level[m]), \
        "`local_high` n'est pas le max glissant des HAUTS décalé de 1"
    # et il vaut bien 100 (le haut), pas 99,5 (la clôture), avant la cassure
    assert fclose(float(df["local_high"].values[i]), 100.0), \
        f"niveau attendu 100.0 (extrême), obtenu {df['local_high'].values[i]}"

    # --- (b) contrôle NÉGATIF : mèche à 110 mais clôture à 99,5 -> rien ---
    cand_wick_only = raw_breakout_candidates(df, vol)
    assert not bool(cand_wick_only[i + 1]), (
        "une mèche qui pénètre le niveau ne doit RIEN déclencher "
        "(#14:28, 'les mèches peuvent pénétrer l'ancien territoire')")
    assert not cand_wick_only.any(), \
        "aucune autre bougie ne devait déclencher dans ce scénario"

    # --- (c) contrôle POSITIF : même bougie, clôture à 105 -> déclenche ---
    df2, vol2, i2 = frame(close_at_breakout=105.0)
    cand_close = raw_breakout_candidates(df2, vol2)
    assert bool(cand_close[i2 + 1]), (
        "une CLÔTURE au-dessus du niveau doit déclencher -- sans ce contrôle "
        "positif, l'assertion (b) passerait pour la mauvaise raison")
    assert cand_close.sum() == 1, \
        f"exactement 1 déclenchement attendu, obtenu {int(cand_close.sum())}"

    # Les deux scénarios ne diffèrent QUE par la clôture : le haut, le bas et
    # le volume sont identiques. C'est donc bien la clôture, et elle seule,
    # qui valide la structure -- la règle de l'Overlap, déjà implémentée.
    assert np.array_equal(df["high"].values, df2["high"].values)
    assert np.array_equal(df["low"].values, df2["low"].values)
    assert np.array_equal(vol["volume"].values, vol2["volume"].values)

# ---------------------------------------------------------------------------
# Test 14 : "limites de range" et niveau cassé ne sont PAS deux informations
#           indépendantes dans ce projet (prémisse du refus d'implémenter le
#           "Cluster technique" de #12, cf. note dédiée en tête de
#           `trend_table.py` et `PLAN.md` section "15e application").
#
# `local_high` (max glissant LOCAL_DURATION des HAUTS) et `ctx_high` (max
# glissant CONTEXT_DURATION des mêmes HAUTS) sont deux maxima de LA MÊME
# SÉRIE sur des fenêtres EMBOÎTÉES (5D ⊂ 15D) : `local_high <= ctx_high`
# est vrai par construction, et les deux sont EXACTEMENT ÉGAUX dès que le
# plus-haut des 15 jours tombe dans les 5 derniers -- ce qui est le cas
# typique d'une bougie de cassure. Un gate de "convergence" qui compterait
# `ctx_high` comme une structure convergeant vers `local_high` compterait
# donc le niveau de référence avec lui-même.
#
# Ce test échouera si la définition de l'une des deux fenêtres change au
# point de rompre l'emboîtement -- c'est voulu : la note de `trend_table.py`
# s'appuie sur cette propriété.
# ---------------------------------------------------------------------------
def test_range_limit_is_not_independent_of_the_broken_level():
    import numpy as np
    import pandas as pd
    from emile.core.trend_table import add_trend_context

    n = 150                                    # 25 jours en H4 (6 bougies/jour)
    dates = pd.date_range("2024-01-01", periods=n, freq="4h")
    high = np.full(n, 100.0)
    spike = 60                                 # jour 10 : un plus-haut isolé
    high[spike] = 200.0

    df = pd.DataFrame({
        "date": dates, "open": high, "high": high,
        "low": np.full(n, 99.0), "close": np.full(n, 99.5),
        "atr": np.full(n, 1.0), "ctx_support": np.full(n, 90.0),
    })
    df = add_trend_context(df)

    lh = df["local_high"].values
    ch = df["ctx_high"].values
    both = ~np.isnan(lh) & ~np.isnan(ch)
    assert both.sum() > 0, "aucune barre exploitable -- test vide"

    # (a) L'invariant d'emboîtement, sur toutes les barres définies.
    assert np.all(lh[both] <= ch[both] + 1e-12), (
        "local_high > ctx_high sur au moins une barre : les fenêtres "
        "LOCAL_DURATION/CONTEXT_DURATION ne sont plus emboîtées")

    # (b) Égalité EXACTE tant que le pic est dans les deux fenêtres : c'est le
    #     cas dégénéré qui rend la "convergence" triviale.
    equal_at_spike = both & (lh == 200.0) & (ch == 200.0)
    assert equal_at_spike.sum() > 0, (
        "aucune barre où local_high == ctx_high == 200 : le cas dégénéré "
        "que la note documente n'est plus reproduit")

    # (c) CONTRÔLE POSITIF -- sans lui, (a) passerait pour la mauvaise raison
    #     (par exemple si les deux colonnes étaient partout identiques).
    #     Il existe bien des barres où le pic a quitté la fenêtre LOCALE mais
    #     pas la fenêtre CONTEXTE : les deux grandeurs sont alors distinctes.
    strictly_below = both & (lh == 100.0) & (ch == 200.0)
    assert strictly_below.sum() > 0, (
        "aucune barre où local_high (100) < ctx_high (200) : le test ne "
        "distingue pas réellement les deux fenêtres, il est vacant")

def test_cassure_3br_arms_then_fills_adds_a_leg_without_moving_stop():
    """Branche "Cassure de 3BR" (34e round) -- scénario à vérité terrain
    construit à la main, bougie par bougie, via `step_campaign` directement
    (même patron que `test_step_campaign_breakout_space_gate`) :
      i=0 : swing bas confirmé (`ev["swing_low_confirmed"]=True`) -> arme un
            niveau au `swing_high` courant (110.0). Prix ne dépasse pas ce
            niveau -> rien ne se remplit.
      i=1 : le prix dépasse enfin le niveau armé (high > 110.0) -> la jambe
            se remplit à l'open (ou au niveau armé si pas de gap), stop
            INCHANGÉ (H-Suivi-Cassure3BR-1), n_suivis passe à 1.

    `breakout_frac` volontairement réduit à 0.2 (plutôt que le 1.0 du profil
    MODERE) : sinon la 1ère jambe sature déjà, seule, le plafond de risque
    de campagne (H3, MAX_CAMPAIGN_RISK_PCT=5%) et ne laisse aucune place à
    la jambe "suivi" -- ce test vérifie le REMPLISSAGE, pas le plafond
    (déjà couvert par `test_add_leg_risk_cap`)."""
    p = PROFILES_TREND["MODERE"]
    campaign = make_campaign(entry=100.0, stop=95.0)
    campaign["stage"] = "POST_BREAKOUT"
    campaign["swing_high"] = 110.0
    add_leg(campaign, 0.2, 100.0)
    stop_before = campaign["stop"]

    # i=0 : swing bas confirmé, prix encore sous le niveau armé (110.0) -> arme, ne remplit pas
    ev0 = {"regime_excess": False, "divergence_raw": False, "suivi_ok": True, "swing_low_confirmed": True}
    closed0, fee0, realized0, rev0 = step_campaign(
        campaign, 0, o=[105.0], high=[108.0], low=[104.0], c=[106.0], ev=ev0, profile=p)
    assert closed0 is False and fee0 == 0.0 and realized0 is None
    assert campaign.get("suivi_armed_level") == 110.0, "doit armer exactement au swing_high courant"
    assert campaign.get("n_suivis", 0) == 0

    remaining_before_fill = campaign["remaining"]
    # bougie suivante : le prix dépasse le niveau armé -> remplissage (même
    # convention que le reste de ce fichier : chaque appel de step_campaign
    # utilise i=0 sur un array à un seul élément représentant CETTE bougie,
    # l'état de la campagne persistant entre les appels).
    ev1 = {"regime_excess": False, "divergence_raw": False, "suivi_ok": True, "swing_low_confirmed": False}
    closed1, fee1, realized1, rev1 = step_campaign(
        campaign, 0, o=[111.0], high=[113.0], low=[110.5], c=[112.0], ev=ev1, profile=p)
    assert closed1 is False and realized1 is None
    assert fee1 > 0.0, "une jambe doit avoir été ajoutée (fee_frac = fraction ajoutée)"
    assert campaign["remaining"] > remaining_before_fill, "la jambe doit augmenter la taille de la campagne"
    assert campaign.get("n_suivis") == 1
    assert campaign.get("suivi_armed_level") is None, "le niveau armé doit être consommé après remplissage"
    assert fclose(campaign["stop"], stop_before), (
        "H-Suivi-Cassure3BR-1 : le stop de campagne ne doit PAS bouger au remplissage"
    )

def test_cassure_3br_does_not_arm_when_suivi_not_ok():
    """Contrôle négatif : `suivi_ok=False` (moyenne baissière ou squeeze,
    cf. `compute_suivi_conditions`) doit empêcher l'armement, même si un
    swing bas se confirme."""
    p = PROFILES_TREND["MODERE"]
    campaign = make_campaign(entry=100.0, stop=95.0)
    campaign["stage"] = "POST_BREAKOUT"
    campaign["swing_high"] = 110.0
    add_leg(campaign, p["breakout_frac"], 100.0)

    ev = {"regime_excess": False, "divergence_raw": False, "suivi_ok": False, "swing_low_confirmed": True}
    step_campaign(campaign, 0, o=[105.0], high=[108.0], low=[104.0], c=[106.0], ev=ev, profile=p)
    assert campaign.get("suivi_armed_level") is None, "suivi_ok=False doit empêcher tout armement"

def test_cassure_3br_respects_suivi_max():
    """Contrôle négatif : une campagne ayant déjà atteint `SUIVI_MAX` suivis
    ne doit plus jamais armer de nouveau niveau, même avec toutes les
    conditions par ailleurs réunies."""
    p = PROFILES_TREND["MODERE"]
    campaign = make_campaign(entry=100.0, stop=95.0)
    campaign["stage"] = "POST_BREAKOUT"
    campaign["swing_high"] = 110.0
    campaign["n_suivis"] = SUIVI_MAX
    add_leg(campaign, p["breakout_frac"], 100.0)

    ev = {"regime_excess": False, "divergence_raw": False, "suivi_ok": True, "swing_low_confirmed": True}
    step_campaign(campaign, 0, o=[105.0], high=[108.0], low=[104.0], c=[106.0], ev=ev, profile=p)
    assert campaign.get("suivi_armed_level") is None, f"n_suivis déjà à SUIVI_MAX={SUIVI_MAX} doit bloquer l'armement"

def test_cassure_3br_absent_ev_keys_preserve_historical_behavior():
    """Garde-fou de non-régression : un `ev` qui ne fournit PAS `suivi_ok`/
    `swing_low_confirmed` (tous les appelants historiques) doit se comporter
    EXACTEMENT comme avant ce round -- `.get(..., False)` retombe sur False,
    donc jamais d'armement ni de remplissage, quel que soit le prix."""
    p = PROFILES_TREND["MODERE"]
    campaign = make_campaign(entry=100.0, stop=95.0)
    campaign["stage"] = "POST_BREAKOUT"
    campaign["swing_high"] = 110.0
    add_leg(campaign, p["breakout_frac"], 100.0)
    remaining_before = campaign["remaining"]

    ev = {"regime_excess": False, "divergence_raw": False}   # ni suivi_ok ni swing_low_confirmed
    closed, fee, realized, rev = step_campaign(
        campaign, 0, o=[200.0], high=[300.0], low=[100.0], c=[250.0], ev=ev, profile=p)
    assert closed is False and fee == 0.0 and realized is None
    assert fclose(campaign["remaining"], remaining_before), "sans les clés, aucune jambe suivi ne doit s'ajouter"
    assert "suivi_armed_level" not in campaign

def test_suivi_conditions_ema_rising_ground_truth_short_series():
    """Sur une série COURTE (moins que la fenêtre `PCTL_WINDOW`=250 de
    `compute_squeeze`), le seuil de squeeze reste NaN partout -> `compute_
    squeeze` retombe sur son défaut prudent (jamais squeeze, cf. sa propre
    docstring) -- `compute_suivi_conditions` se réduit alors exactement à
    la pente de l'EMA, vérifiée à la main :
      ema_trend = [1, 2, 3, 2, 3] -> rising = [F, T, T, F, T] (idx0 -> False
      par convention, aucune bougie antérieure)."""
    ema_trend = np.array([1.0, 2.0, 3.0, 2.0, 3.0])
    width = np.array([1.0, 4.0, 3.0, 2.0, 1.0])   # trop court pour que le squeeze morde -- warmup
    got = compute_suivi_conditions(ema_trend, width)
    expected = np.array([False, True, True, False, True])
    assert np.array_equal(got, expected), f"attendu {expected.tolist()}, obtenu {got.tolist()}"

def test_suivi_conditions_squeeze_blocks_even_when_ema_rising():
    """Contrôle que le squeeze BLOQUE réellement la condition, même quand
    l'EMA monte -- sur une série assez longue pour que `compute_squeeze`
    sorte de son warmup (>250 bougies), avec une chute nette et récente de
    la largeur du canal (squeeze réel, pas juste warmup) pendant que l'EMA
    continue de monter partout."""
    n = 300
    ema_trend = np.linspace(1.0, 2.0, n)   # monte strictement partout
    width = np.full(n, 10.0)
    width[-10:] = 0.1   # chute nette et récente -> squeeze sur les 10 dernières bougies
    got = compute_suivi_conditions(ema_trend, width)
    assert got[200:-10].all(), "avant la chute de largeur, EMA montante + pas de squeeze -> True partout"
    assert not got[-10:].any(), "pendant le squeeze, même avec l'EMA montante, la condition doit être False"

def test_suivi_conditions_false_on_first_bar():
    """Pas de bougie précédente pour juger la pente à l'indice 0 -> False
    par convention, jamais une comparaison hors limites."""
    ema_trend = np.array([1.0, 2.0, 3.0])
    width = np.array([10.0, 10.0, 10.0])
    got = compute_suivi_conditions(ema_trend, width)
    assert not got[0], "idx 0 doit être False (aucune bougie antérieure pour juger la pente)"

def test_suivi_max_is_two():
    """Garde-fou documentaire : la citation exacte du guide est "pas plus de
    2 suivis dans une tendance" -- verrouille la constante contre une
    modification accidentelle."""
    assert SUIVI_MAX == 2

TESTS = [
    test_add_leg_risk_cap,
    test_add_leg_blended_entry_price,
    test_full_sequence_agressif,
    test_reverse_mechanism_tres_agressif,
    test_protective_stop_triggers_on_wick,
    test_regime_excess_abandons_accumulation,
    test_free_room_frac_semantics,
    test_breakout_space_ok_ratio_1_1,
    test_step_campaign_breakout_space_gate,
    test_attach_obstacle_level_no_lookahead,
    test_raw_breakout_candidates_matches_engine_expression,
    test_breakout_space_gate_requires_both_levels,
    test_overlap_convention_already_in_breakout_raw,
    test_range_limit_is_not_independent_of_the_broken_level,
    test_suivi_conditions_ema_rising_ground_truth_short_series,
    test_suivi_conditions_squeeze_blocks_even_when_ema_rising,
    test_suivi_conditions_false_on_first_bar,
    test_suivi_max_is_two,
    test_cassure_3br_arms_then_fills_adds_a_leg_without_moving_stop,
    test_cassure_3br_does_not_arm_when_suivi_not_ok,
    test_cassure_3br_respects_suivi_max,
    test_cassure_3br_absent_ev_keys_preserve_historical_behavior,
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
