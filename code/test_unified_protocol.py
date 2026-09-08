"""
Tests unitaires du protocole unifié (`unified_protocol.py`, PLAN.md section
"Protocole unifié -- routeur de régime range <-> tendance").

RÉVISÉ (8 sept. 2026) suite à la correction de l'exclusivité mutuelle par
actif (cf. "CORRECTION" en tête de `unified_protocol.py`) : les anciens tests
1/2 vérifiaient explicitement l'exclusivité ("le routeur ne bascule PAS",
"préemption tendance") -- ce comportement a été retiré parce que le corpus
ne le justifie pas (au contraire, `TRADING_LESSONS_CLUSTERS_PRIX.md` #16 et
`TRADING_LESSONS_PYRAMIDALISATION.md` #15 documentent explicitement des
positions multiples simultanées). Ces deux tests sont remplacés par des
tests de CONCURRENCE : un signal tendance qui survient PENDANT qu'une
tranche range est déjà ouverte doit maintenant ouvrir la campagne tendance
EN PLUS de la tranche range (pas à sa place, pas bloqué).

Teste la boucle d'ORCHESTRATION (`_run_core_unified`) sur des `feat` dicts
CONSTRUITS À LA MAIN (scénarios synthétiques à vérité terrain connue),
exactement comme `test_trend_table.py` teste `step_campaign`/
`try_open_campaign` avec des `ev` déjà résolus, et comme
`test_backtest_phase2_recommended.py` teste `_run_core` indépendamment de
`_prepare_features`. `_run_core_unified` ne recalcule AUCUN indicateur
(cf. `unified_protocol.py`) -- ce qui rend ces scénarios synthétiques
possibles sans passer par le vrai pipeline `proxy_v2`/`regime_classifier`.

RÉVISÉ À NOUVEAU (8 sept. 2026, CONSOLIDATION) : le côté RANGE de ce routeur
applique désormais les mêmes règles littérales que `backtest_phase2_faithful.py`
(stop D1 UT+1, abstention Wall Street, +Reverse scopé TRES_AGRESSIF), pas
celles de `recommended.py`. `_make_base_feat` expose donc `ctx_support_d1`
et `wall_street_active` en plus de `ctx_support` (toujours utilisé côté
TENDANCE, cf. hypothèse H4 de `trend_table.py` -- stop natif H4, PAS le même
stop que RANGE). Le test de non-régression (test 3) compare désormais
`_run_core_unified` à `_run_core` de `backtest_phase2_faithful.py` (pas
`recommended.py`) sur le MÊME `feat` dict synthétique -- deux moteurs réels
appelés sur les mêmes données, pas une réimplémentation d'un des deux pour
la comparaison.

Le test `decide_now` (test 4) est le seul à repasser par le VRAI pipeline
(`_prepare_unified`) sur un historique H1 synthétique construit à la main
(prix + volume) -- il vérifie la COHÉRENCE structurelle de la sortie
(valeurs mutuellement compatibles, jamais un prix chiffré sur une action
"pas de position"), pas un scénario de régime précis (trop fragile à
garantir à travers tout le pipeline causal réel, cf. discussion dans le
rapport de tâche).

Exécution : `python3 test_unified_protocol.py`.
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")

from backtest_phase2_v7 import MIN_BORDERS
from backtest_phase2_recommended import WARMUP
from backtest_phase2_faithful import _run_core as _run_core_faithful
from unified_protocol import _run_core_unified, _accumulation_active, decide_now


N = WARMUP + 25   # marge suffisante après warmup pour dérouler un scénario complet


def _make_base_feat(n=N):
    """Feat dict 'neutre' : rien ne se déclenche par défaut, ni côté RANGE
    (score=0 partout, gate Hebdo toujours ouvert) ni côté TENDANCE (régime
    RANGE_NEUTRE partout, retracement hors zone [0.38,0.61], pas de rejet de
    canal, pas d'expansion de volume, cycle toujours favorable donc jamais
    de divergence) -- chaque test override une tranche d'indices précise
    pour injecter SON scénario, sans toucher au reste."""
    dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    close = np.full(n, 100.0)
    return {
        "date": dates.values,
        "open": close.copy(), "high": close.copy(), "low": close.copy(), "close": close.copy(),
        "score": np.zeros(n),
        "atr": np.full(n, 1.0),
        "ctx_support": np.full(n, 90.0),
        "ctx_support_d1": np.full(n, 90.0),
        "wall_street_active": np.full(n, False),
        "local_range": np.full(n, 5.0),
        "context_range": np.full(n, 10.0),
        "n_borders": np.full(n, float(MIN_BORDERS)),
        "gate_score": np.full(n, np.inf),
        "gate_regime": np.full(n, "RANGE_NEUTRE", dtype=object),
        "regime": np.full(n, "RANGE_NEUTRE", dtype=object),
        "regime_d1": np.full(n, "TENDANCE", dtype=object),   # jamais en range par défaut -- isole les tests du gate CONFLIT MTF (cf. tête de unified_protocol.py), overridé explicitement par les tests dédiés
        "ctx_resistance": np.full(n, 110.0),
        "ctx_high": np.full(n, 105.0),
        "local_high": np.full(n, 102.0),
        "accum_retracement_frac": np.full(n, 0.0),
        "cycle_favorable": np.full(n, True),
        "ema_trend": np.full(n, 95.0),
        "volume_expansion": np.full(n, False),
    }


# ---------------------------------------------------------------------------
# Test 1 (décision #1 révisée, indépendance) : accumulation_active devient
# vrai PENDANT qu'une tranche range est déjà ouverte -> le routeur ouvre la
# campagne tendance EN PLUS (pas à la place, pas bloqué) -- preuve directe
# que l'ancienne exclusivité mutuelle a bien été retirée, pas seulement
# renommée.
# ---------------------------------------------------------------------------
def test_accumulation_during_open_range_opens_trend_concurrently():
    feat = _make_base_feat()
    entry_i = WARMUP + 2
    j_open = entry_i - 1

    # Signal RANGE valide sur la bougie j_open -> ouverture d'une tranche à
    # entry_i. Score maintenu à 2 sur tout le reste de l'historique pour que
    # la tranche ne se referme jamais sur la règle "sortie de signal" (flip)
    # de process_tranche -- on veut qu'elle reste OUVERTE pendant tout le
    # scénario, condition même du test.
    feat["score"][j_open:] = 2

    # Juste après l'ouverture (bougie j_accum = entry_i), on fait basculer
    # accumulation_active à True (régime TENDANCE + rejet canal +
    # retracement 38-61%) -- exactement la condition que
    # `trend_table.try_open_campaign` exigerait pour ouvrir une campagne --
    # et on la maintient vraie sur le reste de l'historique.
    j_accum = entry_i
    feat["regime"][j_accum:] = "TENDANCE"
    feat["ctx_support"][j_accum:] = 99.5
    feat["low"][j_accum:] = 99.0
    feat["close"][j_accum:] = 100.0
    feat["accum_retracement_frac"][j_accum:] = 0.5

    # Garde-fou : le scénario doit être réellement "vivant" -- si aucune
    # tranche range n'était déjà ouverte, accumulation_active(entry_i+1)
    # doit valoir True (sinon ce test ne prouverait rien).
    assert _accumulation_active(feat, entry_i + 1) is True, (
        "scénario invalide : accumulation_active devrait être vrai à cette bougie "
        "si aucune position n'était déjà ouverte (sinon le test ne prouve rien)"
    )

    res = _run_core_unified(feat, "MODERE", record_state=True)
    live = res["live_state"]
    assert live["range_active"] is True, "la tranche range ouverte à l'entrée doit rester active"
    assert len(live["range_tranches"]) >= 1, "la tranche range ouverte à l'entrée doit toujours être présente"
    assert live["trend_active"] is True, (
        "accumulation_active était vrai pendant que la tranche range était déjà ouverte -- "
        "le routeur aurait dû ouvrir une campagne tendance EN PLUS (indépendance des deux "
        "systèmes, décision #1 révisée), pas rester bloqué par une exclusivité qui n'est plus "
        "de mise"
    )
    assert live["trend_campaign"] is not None
    assert res["n_trend_campaigns_opened"] >= 1


# ---------------------------------------------------------------------------
# Test 2 (décision #1 révisée, indépendance) : aucune position ouverte et
# accumulation_active devient vrai en même temps qu'un signal range éligible
# -> le routeur ouvre LES DEUX (campagne tendance ET tranche range), aucune
# préemption d'un système sur l'autre.
# ---------------------------------------------------------------------------
def test_opens_both_systems_concurrently_when_both_signals_fire():
    feat = _make_base_feat()
    entry_i = WARMUP + 2
    j = entry_i - 1

    # Signal RANGE éligible dès la bougie j (score>=2 maintenu ensuite pour
    # que la tranche ne se referme pas sur un flip de signal)...
    feat["score"][j:] = 2
    # ...ET accumulation_active vrai à l'ouverture, les deux lus sur la MÊME
    # bougie j (`open_tranche_fn`/`try_open_campaign` lisent tous deux les
    # features de la bougie i-1 pour une ouverture à i=entry_i). Modifié
    # UNIQUEMENT à la bougie j (pas en slice jusqu'à la fin, contrairement au
    # test 1) : `ctx_support[j]`=99.5 devient AUSSI le stop de la tranche
    # range ouverte à entry_i (calculé à l'entrée à partir de cette même
    # bougie j) -- si `low` restait à 99.0 sur tout le reste de l'historique,
    # cette tranche serait stoppée dès la bougie suivante (99.0 <= 99.5),
    # rouvrirait, serait re-stoppée, etc. (scénario dégénéré, pas celui
    # qu'on veut tester). En ne modifiant que la bougie j, `low` revient à
    # son défaut (100.0, au-dessus du stop) dès la bougie suivante -- la
    # tranche survit, comme on veut le vérifier.
    feat["regime"][j] = "TENDANCE"
    feat["ctx_support"][j] = 99.5
    feat["low"][j] = 99.0
    feat["close"][j] = 100.0
    feat["accum_retracement_frac"][j] = 0.5

    assert _accumulation_active(feat, entry_i) is True, "scénario invalide : accumulation_active doit être vrai à l'ouverture"

    res = _run_core_unified(feat, "MODERE", record_state=True)
    live = res["live_state"]
    assert live["trend_active"] is True, "une campagne tendance doit avoir été ouverte (accumulation_active vrai)"
    assert live["trend_campaign"] is not None
    assert live["trend_campaign"]["stage"] in ("ACCUMULATION", "POST_BREAKOUT", "PULLBACK_WATCH", "EXCESS_WATCH")
    assert live["range_active"] is True, (
        "une tranche range aurait dû être ouverte EN PLUS de la campagne tendance -- le signal "
        "range (score>=2 + gate Hebdo) était éligible à la même bougie et rien ne doit plus "
        "l'en empêcher (indépendance des deux systèmes, décision #1 révisée)"
    )
    assert len(live["range_tranches"]) >= 1
    assert res["n_trend_campaigns_opened"] == 1
    assert res["n_range_fresh_entries"] == 1


# ---------------------------------------------------------------------------
# Test 3 (décision #5, non-régression) : séquence complète RANGE
# (Validation -> Confirmation -> Limite) sans jamais croiser une condition
# tendance -> P&L identique à recommended.py (_run_core) seul sur le MÊME
# feat dict. Toujours valide après la correction : en l'absence de tout
# signal tendance, l'indépendance des deux systèmes ne change rien au
# comportement RANGE seul.
# ---------------------------------------------------------------------------
def test_pure_range_sequence_matches_faithful_engine():
    feat = _make_base_feat()
    entry_i = WARMUP + 2
    j_open = entry_i - 1
    feat["score"][j_open:] = 2   # signal long maintenu (pas de flip-exit)

    # Prix : plat jusqu'à l'entrée, puis rampe linéaire +2/bougie -- traverse
    # val_px=105 (entrée+local_range=100+5), conf_px=110 (entrée+context_range
    # =100+10), lim_px=115 (entrée+1.5*context_range=100+15), dans cet ordre
    # (Validation avant Confirmation avant Limite, cf. process_tranche).
    for k in range(0, N - entry_i):
        idx = entry_i + k
        price = 100.0 + 2 * k
        feat["open"][idx] = price
        feat["high"][idx] = price
        feat["low"][idx] = price
        feat["close"][idx] = price

    # Aucune condition tendance n'est jamais franchie ici : regime reste
    # RANGE_NEUTRE partout (jamais modifié), accum_retracement_frac reste à
    # 0.0 (hors zone [0.38,0.61]) -- accumulation_active est donc FAUX à
    # chaque bougie, vérifié explicitement plutôt que supposé.
    for i in range(1, N):
        assert _accumulation_active(feat, i) is False, (
            f"scénario invalide pour un test de RÉGRESSION pure range : "
            f"accumulation_active(feat, {i}) est vrai, une condition tendance a été croisée par accident"
        )

    range_keys = [
        "date", "open", "high", "low", "close", "score", "atr", "ctx_support_d1",
        "local_range", "context_range", "n_borders", "gate_score", "gate_regime",
        "wall_street_active",
    ]
    feat_range_only = {k: feat[k] for k in range_keys}
    # "regime" (unified) et "regime_h4" (faithful) désignent la MÊME grandeur
    # (régime H4 natif) sous deux noms différents -- cf. CORRECTION EXCES H4
    # dans les deux fichiers. "regime_d1" porte le même nom dans les deux
    # fichiers (cf. CORRECTION CONFLIT MTF) -- copié tel quel.
    feat_range_only["regime_h4"] = feat["regime"]
    feat_range_only["regime_d1"] = feat["regime_d1"]

    for profile in ("FAIBLE", "MODERE", "AGRESSIF", "TRES_AGRESSIF"):
        res_unified = _run_core_unified(feat, profile)
        res_faithful = _run_core_faithful(feat_range_only, profile)
        for key in ("n_trades", "max_dd_%", "total_return_%", "win_rate_%", "profit_factor"):
            assert res_unified[key] == res_faithful[key], (
                f"profil {profile}, champ {key} : unifié={res_unified[key]!r} != "
                f"faithful={res_faithful[key]!r} -- régression du protocole unifié en "
                "l'absence de toute condition tendance (devrait être identique à "
                "backtest_phase2_faithful.py seul, MÊMES règles littérales côté RANGE)"
            )
        assert res_unified["n_trend_campaigns_opened"] == 0
        # Vérifie que la séquence a bien exercé les 3 étapes (test non vacueux :
        # au moins un trade a eu lieu, sinon la comparaison serait triviale).
        assert res_unified["n_trades"] > 0


# ---------------------------------------------------------------------------
# Test 4 : decide_now sur un historique H1 synthétique construit à la main
# -- vérifie la COHÉRENCE structurelle de la sortie (pas un scénario de
# régime précis, trop fragile à garantir à travers tout le pipeline causal
# réel proxy_v2/regime_classifier -- cf. docstring de ce fichier). RÉVISÉ :
# `range`/`trend` sont désormais deux sous-dicts indépendants (plus de
# clé `action`/`system` unique au niveau racine).
# ---------------------------------------------------------------------------
def _make_synthetic_h1(n_hours, seed=0, start_price=100.0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n_hours, freq="1h", tz="UTC")
    steps = rng.normal(0, 0.3, n_hours)
    close = start_price + np.cumsum(steps)
    close = np.clip(close, 1.0, None)
    open_ = np.roll(close, 1)
    open_[0] = start_price
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.1, n_hours))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.1, n_hours))
    volume = rng.uniform(50, 150, n_hours)
    return pd.DataFrame({"date": dates, "open": open_, "high": high, "low": low, "close": close, "volume": volume})


# ---------------------------------------------------------------------------
# CORRECTION PYRAMIDALISATION-RÉGIME (cf. tête de fichier) : côté RANGE, le
# renfort ne doit s'ouvrir QUE si le régime H4 natif (`feat["regime"]`) est
# TENDANCE/RANGE_TENDANCIEL -- `RULES_EXTRACTION.md` §3 n'a jamais de
# cellule "Renfort". Scénario synthétique entièrement favorable au
# pyramidage (hausse continue, jamais de stop/cible touché sur la fenêtre),
# aucune condition tendance jamais croisée (accumulation_active resterait
# fausse), pour isoler l'effet de cette correction.
# ---------------------------------------------------------------------------
def _make_pyramid_range_feat(regime_value, n=N):
    feat = _make_base_feat(n)
    entry_i = WARMUP + 2
    j_open = entry_i - 1
    feat["score"][j_open:] = 2
    for k in range(0, n - j_open):
        idx = j_open + k
        price = 100.0 * (1 + 0.001 * k)
        feat["open"][idx] = price; feat["high"][idx] = price
        feat["low"][idx] = price; feat["close"][idx] = price
        feat["ctx_support_d1"][idx] = price - 5.0
    feat["regime"][j_open:] = regime_value
    return feat


def test_range_pyramid_renfort_blocked_when_h4_regime_range_neutre():
    feat = _make_pyramid_range_feat("RANGE_NEUTRE")
    res = _run_core_unified(feat, "MODERE", record_state=True)
    n_open = len(res["live_state"]["range_tranches"])
    assert n_open == 1, (
        f"{n_open} tranche(s) RANGE ouverte(s) en régime RANGE_NEUTRE, attendu exactement 1 "
        "(entrée fraîche seule -- le renfort doit être bloqué par pyramiding_allowed)"
    )


def test_range_pyramid_renfort_allowed_when_h4_regime_tendance():
    feat = _make_pyramid_range_feat("TENDANCE")
    res = _run_core_unified(feat, "MODERE", record_state=True)
    n_open = len(res["live_state"]["range_tranches"])
    assert n_open > 1, (
        f"{n_open} tranche(s) RANGE ouverte(s) en régime TENDANCE, attendu plusieurs "
        "(contrôle positif : le renfort doit rester possible quand le corpus l'autorise)"
    )


# ---------------------------------------------------------------------------
# CORRECTION CONFLIT MTF (cf. tête de fichier) : côté RANGE, aucune tranche
# (entrée fraîche ou renfort) ne doit s'ouvrir si le régime D1 (`feat
# ["regime_d1"]`) est lui-même RANGE_NEUTRE/RANGE_TENDANCIEL -- source #5,
# "l'erreur numéro un". Même scénario synthétique que la pyramidalisation-
# régime (favorable à l'ouverture), régime H4 natif toujours TENDANCE (pour
# isoler l'effet du D1 spécifiquement, indépendamment de EXCES-H4/
# pyramidalisation-régime).
# ---------------------------------------------------------------------------
def _make_conflict_mtf_range_feat(regime_d1_value, n=N):
    feat = _make_base_feat(n)
    entry_i = WARMUP + 2
    j_open = entry_i - 1
    feat["score"][j_open:] = 2
    for k in range(0, n - j_open):
        idx = j_open + k
        price = 100.0 * (1 + 0.001 * k)
        feat["open"][idx] = price; feat["high"][idx] = price
        feat["low"][idx] = price; feat["close"][idx] = price
        feat["ctx_support_d1"][idx] = price - 5.0
    feat["regime"][j_open:] = "TENDANCE"   # H4 natif jamais EXCES/RANGE_NEUTRE -- isole le test
    feat["regime_d1"][j_open:] = regime_d1_value
    return feat


def test_range_entry_blocked_when_d1_regime_is_range():
    feat = _make_conflict_mtf_range_feat("RANGE_NEUTRE")
    res = _run_core_unified(feat, "MODERE", record_state=True)
    n_open = len(res["live_state"]["range_tranches"])
    assert n_open == 0, (
        f"{n_open} tranche(s) RANGE ouverte(s) alors que le régime D1 est RANGE_NEUTRE, attendu 0 "
        "(le gate Conflit MTF doit bloquer TOUTE ouverture, entrée fraîche incluse)"
    )


def test_range_entry_allowed_when_d1_regime_is_tendance():
    feat = _make_conflict_mtf_range_feat("TENDANCE")
    res = _run_core_unified(feat, "MODERE", record_state=True)
    n_open = len(res["live_state"]["range_tranches"])
    assert n_open >= 1, (
        "aucune tranche RANGE ouverte alors que le régime D1 est TENDANCE (scénario par ailleurs "
        "entièrement favorable) -- le gate Conflit MTF bloque aussi le cas où il ne devrait pas"
    )


def test_decide_now_insufficient_data_is_coherent():
    """Historique H1 délibérément trop court (moins que WARMUP+1 bougies H4)
    -> INSUFFICIENT_DATA, avec range/trend/regime à None."""
    h1 = _make_synthetic_h1(n_hours=200, seed=1)   # 200/4 = 50 bougies H4 < WARMUP+1=76
    d = decide_now(h1, "MODERE")
    assert d["action"] == "INSUFFICIENT_DATA"
    assert d["range"] is None and d["trend"] is None and d["regime"] is None
    assert "bougies H4" in d["reason"]


def _assert_system_desc_coherent(desc: dict, label: str):
    for key in ("action", "entry_price", "stop_price", "targets", "reason"):
        assert key in desc, f"champ manquant dans la sortie {label} de decide_now : {key}"
    assert desc["action"] in ("HOLD", "OPEN_LONG", "NO_POSITION")
    assert isinstance(desc["reason"], str) and len(desc["reason"]) > 0
    if desc["action"] == "NO_POSITION":
        assert desc["entry_price"] is None and desc["stop_price"] is None and desc["targets"] is None
    else:
        assert desc["entry_price"] is not None and desc["stop_price"] is not None and desc["targets"] is not None


def test_decide_now_structured_output_is_coherent():
    """Historique H1 synthétique assez long (plusieurs années) pour couvrir
    largement le warmup H4 ET le warmup Hebdomadaire -- vérifie que la
    sortie structurée de `decide_now` est INTERNEMENT cohérente pour CHAQUE
    système (range ET trend indépendamment), quel que soit l'état réel
    qu'un pipeline synthétique aléatoire produit (pas un scénario ciblé,
    cf. docstring)."""
    h1 = _make_synthetic_h1(n_hours=24 * 400, seed=42)   # ~400 jours, ~90 bougies hebdo
    d = decide_now(h1, "AGRESSIF")

    for key in ("range", "trend", "regime", "weekly_gate_reliable", "n_h4_bars", "n_weekly_bars"):
        assert key in d, f"champ manquant dans la sortie de decide_now : {key}"

    assert isinstance(d["weekly_gate_reliable"], bool)
    assert d["n_h4_bars"] == len(h1) // 4  # resample('4h') sur un H1 sans trou
    assert d["regime"] in ("RANGE_NEUTRE", "RANGE_TENDANCIEL", "TENDANCE", "EXCES")

    _assert_system_desc_coherent(d["range"], "range")
    _assert_system_desc_coherent(d["trend"], "trend")
    if d["range"]["action"] == "HOLD":
        assert "tranches" in d["range"]["targets"] or "reverses" in d["range"]["targets"]
    elif d["range"]["action"] == "OPEN_LONG":
        assert {"val_px", "conf_px", "lim_px"} <= set(d["range"]["targets"])
    if d["trend"]["action"] in ("HOLD", "OPEN_LONG"):
        assert "stage" in d["trend"]["targets"] or "target" in d["trend"]["targets"]


def test_decide_now_requires_volume_column():
    h1 = _make_synthetic_h1(n_hours=200, seed=2).drop(columns=["volume"])
    try:
        decide_now(h1, "MODERE")
    except ValueError as e:
        assert "volume" in str(e)
    else:
        raise AssertionError("decide_now aurait dû lever ValueError sans colonne 'volume'")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failures += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passent")
    raise SystemExit(1 if failures else 0)
