"""
Tests unitaires du protocole unifié (`unified_protocol.py`, PLAN.md section
"Protocole unifié -- routeur de régime range <-> tendance").

Teste la boucle d'ORCHESTRATION (`_run_core_unified`) sur des `feat` dicts
CONSTRUITS À LA MAIN (scénarios synthétiques à vérité terrain connue),
exactement comme `test_trend_table.py` teste `step_campaign`/
`try_open_campaign` avec des `ev` déjà résolus, et comme
`test_backtest_phase2_recommended.py` teste `_run_core` indépendamment de
`_prepare_features`. `_run_core_unified` ne recalcule AUCUN indicateur
(cf. `unified_protocol.py`) -- ce qui rend ces scénarios synthétiques
possibles sans passer par le vrai pipeline `proxy_v2`/`regime_classifier`.

Le test de non-régression (test 3) compare directement `_run_core_unified`
à `_run_core` (recommended.py) sur le MÊME `feat` dict synthétique -- deux
moteurs réels appelés sur les mêmes données, pas une réimplémentation d'un
des deux pour la comparaison.

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
from backtest_phase2_recommended import _run_core as _run_core_recommended, WARMUP
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
        "local_range": np.full(n, 5.0),
        "context_range": np.full(n, 10.0),
        "n_borders": np.full(n, float(MIN_BORDERS)),
        "gate_score": np.full(n, np.inf),
        "gate_regime": np.full(n, "RANGE_NEUTRE", dtype=object),
        "regime": np.full(n, "RANGE_NEUTRE", dtype=object),
        "ctx_resistance": np.full(n, 110.0),
        "ctx_high": np.full(n, 105.0),
        "local_high": np.full(n, 102.0),
        "accum_retracement_frac": np.full(n, 0.0),
        "cycle_favorable": np.full(n, True),
        "ema_trend": np.full(n, 95.0),
        "volume_expansion": np.full(n, False),
    }


# ---------------------------------------------------------------------------
# Test 1 (décision #2, exclusivité mutuelle) : accumulation_active devient
# vrai PENDANT qu'une tranche range est déjà ouverte -> le routeur ne
# bascule PAS vers tendance tant que cette position n'est pas close.
# ---------------------------------------------------------------------------
def test_accumulation_during_open_range_does_not_switch():
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
    # `trend_table.try_open_campaign` exigerait pour ouvrir une campagne.
    j_accum = entry_i
    feat["regime"][j_accum] = "TENDANCE"
    feat["ctx_support"][j_accum] = 99.5
    feat["low"][j_accum] = 99.0
    feat["close"][j_accum] = 100.0
    feat["accum_retracement_frac"][j_accum] = 0.5

    # Garde-fou : le scénario doit être réellement "vivant" -- si aucune
    # tranche range n'était ouverte, accumulation_active(entry_i+1) doit
    # valoir True (sinon ce test ne prouverait rien).
    assert _accumulation_active(feat, entry_i + 1) is True, (
        "scénario invalide : accumulation_active devrait être vrai à cette bougie "
        "si aucune position n'était déjà ouverte (sinon le test ne prouve rien)"
    )

    res = _run_core_unified(feat, "MODERE", record_state=True)
    live = res["live_state"]
    assert live["active_system"] == "range", (
        f"le routeur a basculé vers {live['active_system']!r} alors qu'une tranche range "
        "était déjà ouverte -- viole l'exclusivité mutuelle (décision #2 de PLAN.md)"
    )
    assert live["trend_campaign"] is None, "aucune campagne tendance ne doit avoir été ouverte"
    assert len(live["range_tranches"]) >= 1, "la tranche range ouverte à l'entrée doit toujours être présente"


# ---------------------------------------------------------------------------
# Test 2 (décision #1, priorité de régime) : aucune position ouverte et
# accumulation_active devient vrai -> le routeur ouvre une campagne
# TENDANCE, PAS une tranche range (même si le signal range serait lui aussi
# éligible à la même bougie -- preuve d'une vraie préemption, pas d'un
# signal range absent par accident).
# ---------------------------------------------------------------------------
def test_opens_trend_when_flat_and_accumulation_active():
    feat = _make_base_feat()
    entry_i = WARMUP + 2
    j = entry_i - 1

    # Signal RANGE éligible à la même bougie (pour prouver que la tendance
    # PRÉEMPTE, pas seulement "range n'avait rien à ouvrir")...
    feat["score"][j] = 2
    # ...ET accumulation_active vrai simultanément.
    feat["regime"][j] = "TENDANCE"
    feat["ctx_support"][j] = 99.5
    feat["low"][j] = 99.0
    feat["close"][j] = 100.0
    feat["accum_retracement_frac"][j] = 0.5

    assert _accumulation_active(feat, entry_i) is True, "scénario invalide : accumulation_active doit être vrai à l'ouverture"

    res = _run_core_unified(feat, "MODERE", record_state=True)
    live = res["live_state"]
    assert live["active_system"] == "trend", (
        f"le routeur a ouvert {live['active_system']!r} au lieu de 'trend' alors "
        "qu'accumulation_active était vrai et qu'aucune position n'était ouverte "
        "-- viole la priorité de régime (décision #1 de PLAN.md)"
    )
    assert live["trend_campaign"] is not None, "une campagne tendance doit avoir été ouverte"
    assert live["trend_campaign"]["stage"] in ("ACCUMULATION", "POST_BREAKOUT", "PULLBACK_WATCH", "EXCESS_WATCH")
    assert live["range_tranches"] == [], "aucune tranche range ne doit avoir été ouverte (préemption tendance)"
    assert res["n_trend_campaigns_opened"] == 1
    assert res["n_range_fresh_entries"] == 0


# ---------------------------------------------------------------------------
# Test 3 (décision #5, non-régression) : séquence complète RANGE
# (Validation -> Confirmation -> Limite) sans jamais croiser une condition
# tendance -> P&L identique à recommended.py (_run_core) seul sur le MÊME
# feat dict.
# ---------------------------------------------------------------------------
def test_pure_range_sequence_matches_recommended_engine():
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
        "date", "open", "high", "low", "close", "score", "atr", "ctx_support",
        "local_range", "context_range", "n_borders", "gate_score", "gate_regime",
    ]
    feat_range_only = {k: feat[k] for k in range_keys}

    for profile in ("FAIBLE", "MODERE", "AGRESSIF", "TRES_AGRESSIF"):
        res_unified = _run_core_unified(feat, profile)
        res_reco = _run_core_recommended(feat_range_only, profile)
        for key in ("n_trades", "max_dd_%", "total_return_%", "win_rate_%", "profit_factor"):
            assert res_unified[key] == res_reco[key], (
                f"profil {profile}, champ {key} : unifié={res_unified[key]!r} != "
                f"recommended={res_reco[key]!r} -- régression du protocole unifié en "
                "l'absence de toute condition tendance (devrait être identique à recommended.py seul)"
            )
        assert res_unified["n_trend_campaigns_opened"] == 0
        # Vérifie que la séquence a bien exercé les 3 étapes (test non vacueux :
        # au moins un trade a eu lieu, sinon la comparaison serait triviale).
        assert res_unified["n_trades"] > 0


# ---------------------------------------------------------------------------
# Test 4 : decide_now sur un historique H1 synthétique construit à la main
# -- vérifie la COHÉRENCE structurelle de la sortie (pas un scénario de
# régime précis, trop fragile à garantir à travers tout le pipeline causal
# réel proxy_v2/regime_classifier -- cf. docstring de ce fichier).
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


def test_decide_now_insufficient_data_is_coherent():
    """Historique H1 délibérément trop court (moins que WARMUP+1 bougies H4)
    -> INSUFFICIENT_DATA, avec tous les champs de niveaux/prix à None."""
    h1 = _make_synthetic_h1(n_hours=200, seed=1)   # 200/4 = 50 bougies H4 < WARMUP+1=76
    d = decide_now(h1, "MODERE")
    assert d["action"] == "INSUFFICIENT_DATA"
    assert d["system"] is None
    assert d["entry_price"] is None and d["stop_price"] is None and d["targets"] is None
    assert "bougies H4" in d["reason"]


def test_decide_now_structured_output_is_coherent():
    """Historique H1 synthétique assez long (plusieurs années) pour couvrir
    largement le warmup H4 ET le warmup Hebdomadaire -- vérifie que la
    sortie structurée de `decide_now` est INTERNEMENT cohérente, quel que
    soit l'état réel qu'un pipeline synthétique aléatoire produit (pas un
    scénario ciblé, cf. docstring)."""
    h1 = _make_synthetic_h1(n_hours=24 * 400, seed=42)   # ~400 jours, ~90 bougies hebdo
    d = decide_now(h1, "AGRESSIF")

    for key in ("action", "system", "regime", "entry_price", "stop_price", "targets",
                "reason", "weekly_gate_reliable", "n_h4_bars", "n_weekly_bars"):
        assert key in d, f"champ manquant dans la sortie de decide_now : {key}"

    assert d["action"] in ("HOLD_RANGE", "HOLD_TREND", "OPEN_LONG", "NO_POSITION", "INSUFFICIENT_DATA")
    assert isinstance(d["weekly_gate_reliable"], bool)
    assert d["n_h4_bars"] == len(h1) // 4  # resample('4h') sur un H1 sans trou
    assert isinstance(d["reason"], str) and len(d["reason"]) > 0

    if d["action"] in ("NO_POSITION", "INSUFFICIENT_DATA"):
        assert d["system"] is None
        assert d["entry_price"] is None and d["stop_price"] is None and d["targets"] is None
    else:
        assert d["system"] in ("range", "trend")
        assert d["entry_price"] is not None and d["stop_price"] is not None and d["targets"] is not None
        if d["system"] == "range":
            assert "tranches" in d["targets"] or {"val_px", "conf_px", "lim_px"} <= set(d["targets"])
        else:
            assert "stage" in d["targets"] or "target" in d["targets"]


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
