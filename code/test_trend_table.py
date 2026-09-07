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

from trend_table import (
    add_leg, make_campaign, step_campaign, try_open_campaign, step_reverse,
    PROFILES_TREND, MAX_CAMPAIGN_RISK_PCT,
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


TESTS = [
    test_add_leg_risk_cap,
    test_add_leg_blended_entry_price,
    test_full_sequence_agressif,
    test_reverse_mechanism_tres_agressif,
    test_protective_stop_triggers_on_wick,
    test_regime_excess_abandons_accumulation,
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
