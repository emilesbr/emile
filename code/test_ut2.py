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
sys.path.insert(0, ".")
from backtest_phase2 import load_h1, resample
from backtest_phase2_ut2 import attach_context_level, attach_multi_context, CLOSURE_DELAY, GATE_MODES
from backtest_phase2_v7 import prepare


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


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} tests passés")
