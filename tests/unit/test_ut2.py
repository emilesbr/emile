"""
Tests pour backtest_phase2_ut2.py (backlog PLAN.md item 3, "UT+2 exact").
Écrit directement (agent délégué interrompu par un rate-limit juste après
avoir terminé le module et le backtest complet, mais avant d'écrire ce
fichier — pourtant explicitement référencé dans la docstring du module
comme preuve empirique du point suivant, jamais créé). Comble ce manquant
plutôt que de laisser une affirmation non vérifiée dans le code.
"""
import numpy as np
import pandas as pd
import sys

from emile.backtests.backtest_phase2 import load_h1, resample, atr, ATR_LEN, EMA_SLOW
from emile.backtests.backtest_phase2_ut2 import attach_context_level, attach_multi_context, CLOSURE_DELAY, GATE_MODES
from emile.backtests.backtest_phase2_v7 import prepare
from emile.core.regime_classifier import add_regime

def test_weekly_closure_delay_is_one_day_not_one_week():
    """Régression de la découverte documentée en tête de
    backtest_phase2_ut2.py : une bougie 'W' (resample pandas, ancrée
    dimanche, label='right' par défaut) porte un `date` égal au dimanche
    00:00:00 de la semaine qu'elle résume, et est entièrement close UN
    JOUR après ce `date` -- PAS sept jours après. Vérifié ici sur BTC réel
    par comparaison directe avec le D1 : le close de la bougie D1 datée du
    même dimanche doit être identique au close de la bougie W correspondante
    (preuve que la bougie W couvre bien les données jusqu'à ce dimanche
    inclus, pas jusqu'au dimanche suivant)."""
    h1 = load_h1("BTCUSDT")
    d1 = resample(h1, "1D")
    weekly = resample(h1, "W")

    d1_by_date = d1.set_index("date")["close"]
    matched, total = 0, 0
    for _, row in weekly.head(50).iterrows():
        sunday = row["date"]
        if sunday in d1_by_date.index:
            total += 1
            if np.isclose(row["close"], d1_by_date.loc[sunday]):
                matched += 1
    assert total > 20, "échantillon trop petit pour conclure"
    assert matched == total, (
        f"seulement {matched}/{total} bougies W ont un close identique à la "
        f"bougie D1 du même dimanche -- la bougie W ne couvre PAS les données "
        f"jusqu'à son `date` inclus comme supposé, CLOSURE_DELAY=1 jour serait faux"
    )

def test_closure_delay_constant_is_one_day():
    """Garde-fou basique : si quelqu'un change CLOSURE_DELAY par erreur
    (ex. en réintroduisant `pd.Timedelta(weeks=1)` par excès de prudence,
    piège explicitement documenté et évité), ce test échoue et pointe vers
    la docstring du module."""
    assert CLOSURE_DELAY == pd.Timedelta(days=1), (
        "CLOSURE_DELAY a changé -- vérifier la note de la docstring de "
        "backtest_phase2_ut2.py avant de le modifier (piège 'weeks=1' déjà "
        "identifié et évité une fois)"
    )

def test_attach_context_level_no_lookahead():
    """Le score/régime attaché à une bougie H4 ne doit dépendre que de
    bougies de niveau supérieur ENTIÈREMENT closes à cet instant -- vérifié
    en ajoutant une bougie D1 supplémentaire tout à la fin de l'historique
    (donc dans le futur de toute bougie H4 déjà présente) et en s'assurant
    qu'aucune valeur attachée aux bougies H4 existantes ne change."""
    h1 = load_h1("BTCUSDT")
    h4 = resample(h1, "4h").iloc[:500].reset_index(drop=True)
    d1_full = resample(h1, "1D")
    # d1 tronqué à une date largement postérieure à la dernière bougie h4 testée
    cutoff = h4["date"].iloc[-1] + pd.Timedelta(days=5)
    d1_short = prepare(d1_full[d1_full["date"] <= cutoff].reset_index(drop=True))
    d1_long = prepare(d1_full[d1_full["date"] <= cutoff + pd.Timedelta(days=30)].reset_index(drop=True))

    ctx_short = attach_context_level(h4, d1_short)
    ctx_long = attach_context_level(h4, d1_long)

    assert np.array_equal(
        np.array(ctx_short["score"][:495], dtype=float),
        np.array(ctx_long["score"][:495], dtype=float),
        equal_nan=True,
    ), "des bougies D1 futures ont changé le score attaché à des bougies H4 déjà closes -- régression de lookahead"
    assert np.allclose(
        np.nan_to_num(ctx_short["ctx_support"][:495], nan=-1.0),
        np.nan_to_num(ctx_long["ctx_support"][:495], nan=-1.0),
    ), "des bougies D1 futures ont changé le contexte attaché à des bougies H4 déjà closes -- régression de lookahead"

def test_gate_modes_are_exactly_four():
    assert set(GATE_MODES) == {"none", "d1_only", "ut2_strict", "d1_and_weekly"}

def _synthetic_drift_series(drift: float, n: int = 800, seed: int = 7) -> pd.DataFrame:
    """Série OHLC synthétique à dérive contrôlée — vérité terrain, pas de
    donnée réelle : on prouve une propriété du CLASSIFICATEUR, on ne mesure
    pas un marché. Le bruit (même graine pour toutes les dérives) est
    nécessaire : sans lui, `width_pct` est monotone et les seuils par
    percentile glissant de `add_regime` dégénèrent en EXCES partout, ce qui
    rendrait le test vide de sens (vérifié avant de l'écrire — une première
    version sans bruit ne produisait AUCUN TENDANCE même en hausse, donc ne
    prouvait rien sur l'asymétrie)."""
    rng = np.random.default_rng(seed)
    close = 100.0 * np.cumprod(1 + drift + rng.normal(0, 0.012, n))
    wick = np.abs(rng.normal(0, 0.008, n)) + 0.002
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=n, freq="1D"),
        "open": close, "high": close * (1 + wick), "low": close * (1 - wick),
        "close": close, "volume": np.full(n, 1000.0),
    })

def _regime_counts(df: pd.DataFrame) -> dict:
    """Mêmes 3 lignes que `backtest_phase2_v7.py::prepare` et que le
    `__main__` de `regime_classifier.py` (canal EMA lente ± 2×ATR), pas une
    variante locale."""
    ema = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    width_pct = (2 * 2 * atr(df, ATR_LEN)) / ema * 100
    return dict(add_regime(df, ema, width_pct)["regime"].value_counts())

def test_no_bearish_regime_exists_so_reversal_vs_continuation_is_undetectable():
    """Prémisse LOAD-BEARING de la décision "UT+2 réservé aux trades de
    renversement : investigué, PAS implémenté" (10e mobilisation ; bloc dédié
    en tête de `backtest_phase2_ut2.py`, `PLAN.md` section "10e application").

    Un trade de "renversement" au sens de `TRADING_LESSONS_ZONE_ACCUMULATION.
    md:7` est un trade pris CONTRE la tendance précédente. Or `add_regime` est
    structurellement asymétrique : TENDANCE et RANGE_TENDANCIEL exigent tous
    deux `slope_pct > 0`, donc une tendance BAISSIÈRE retombe dans le `else`
    = RANGE_NEUTRE, indiscernable d'un range plat. Le projet ne peut donc pas
    savoir si la tendance précédente était baissière, et n'a aucun moyen NON
    INVENTÉ de séparer renversement et continuation.

    Prouvé ici par contrôle positif + miroir exact (pas par lecture de la
    formule) : la MÊME série bruitée, avec la dérive inversée, produit des
    centaines de barres TENDANCE en hausse et ZÉRO en baisse. Si quelqu'un
    ajoute un jour un 5e régime baissier, ce test échoue et renvoie à la
    décision documentée — à relire AVANT, à cause du blast radius : les
    comparaisons de chaînes `regime` du projet (dont `d1_not_range` de
    `backtest_phase2_faithful.py`, `not in ("RANGE_NEUTRE",
    "RANGE_TENDANCIEL")`) laisseraient PASSER un label inconnu, ouvrant
    silencieusement des trades aujourd'hui bloqués."""
    up = _regime_counts(_synthetic_drift_series(+0.004))
    flat = _regime_counts(_synthetic_drift_series(0.0))
    down = _regime_counts(_synthetic_drift_series(-0.004))

    # Contrôle positif : sans lui, "aucun TENDANCE en baisse" ne prouverait rien.
    assert up.get("TENDANCE", 0) > 100, (
        f"contrôle positif cassé : une dérive de +0,4%/barre ne produit que "
        f"{up.get('TENDANCE', 0)} barres TENDANCE ({up}) -- le test ne peut "
        f"rien conclure sur l'asymétrie, le réparer avant de s'y fier"
    )
    # Le miroir exact de cette même série ne reçoit AUCUNE étiquette directionnelle.
    assert down.get("TENDANCE", 0) == 0 and down.get("RANGE_TENDANCIEL", 0) == 0, (
        f"add_regime a produit une étiquette directionnelle sur une dérive "
        f"strictement baissière ({down}) -- la prémisse de la décision "
        f"documentée en tête de backtest_phase2_ut2.py a changé, relire cette "
        f"décision avant d'aller plus loin"
    )
    # Et la baisse est étiquetée avec le même vocabulaire qu'un range plat.
    assert set(down) <= {"RANGE_NEUTRE", "EXCES"} <= set(flat) | {"EXCES"}, (
        f"tendance baissière {sorted(down)} vs range plat {sorted(flat)} : un "
        f"état directionnel baissier a peut-être été introduit"
    )

if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} tests passés")
