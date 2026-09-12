"""
Tests pour `backtest_phase2_faithful_manual_channel.py` -- ce module n'avait
AUCUNE couverture dédiée avant ce round (trouvé en le rejouant sur la donnée
réelle actuelle, cf. `PLAN.md` "36e application" : un bug de fuseau horaire
dans `_attach_channel_support_d1` -- non détecté par aucun test, seulement en
exécutant le script contre de vraies données -- gisait sans surveillance).

Se concentre sur `_attach_channel_support_d1`, la seule fonction propre à ce
fichier qui ne soit pas une simple délégation à `backtest_phase2_faithful.py`/
`manual_trend_channel.py` : jointure D1->H4 sans lookahead du niveau
`channel_support`.
"""
import numpy as np
import pandas as pd

from emile.backtests.backtest_phase2_faithful_manual_channel import _attach_channel_support_d1

def test_attach_channel_support_d1_works_with_naive_dates():
    """BUG TROUVÉ ET CORRIGÉ (36e round) : cette fonction forçait `h4_dates`
    en UTC tz-aware en supposant `d1_with_channel["date"]` tz-aware -- vrai
    sur l'ancienne donnée (sandbox disparu), FAUX sur la donnée restaurée
    (`load_h1` produit des dates NAIVES de bout en bout, comme partout
    ailleurs dans ce projet). `pd.merge_asof` refusait alors de comparer un
    côté naive à un côté tz-aware (`MergeError`). Ce test reproduit
    exactement le cas réel : dates NAIVES des deux côtés, comme aujourd'hui."""
    d1 = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        "channel_support": [100.0, 101.0, 102.0],
    })
    h4_dates = pd.to_datetime([
        "2024-01-01 04:00", "2024-01-02 04:00", "2024-01-03 04:00", "2024-01-04 04:00",
    ]).values
    assert h4_dates.dtype == np.dtype("datetime64[us]") or "datetime64" in str(h4_dates.dtype)
    # Ne doit PAS lever MergeError -- c'est précisément ce que le bug cassait.
    result = _attach_channel_support_d1(h4_dates, d1, closure_delay=pd.Timedelta(hours=1))
    assert len(result) == 4

def test_attach_channel_support_d1_no_lookahead_ground_truth():
    """Vérité terrain calculée à la main : `closure_delay` retarde la
    disponibilité d'une bougie D1 (elle n'est utilisable qu'APRÈS sa clôture
    + le délai), donc la bougie H4 du jour J ne doit voir QUE le
    `channel_support` du jour précédent (J-1), jamais celui du jour J
    lui-même tant que le délai n'est pas écoulé."""
    d1 = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        "channel_support": [100.0, 200.0, 300.0],
    })
    closure_delay = pd.Timedelta(hours=1)
    # available_at : 2024-01-01 01:00, 2024-01-02 01:00, 2024-01-03 01:00
    h4_dates = pd.to_datetime([
        "2024-01-01 00:30",  # avant même que la bougie du 01/01 soit disponible -> NaN
        "2024-01-02 00:30",  # bougie du 01/01 déjà disponible (01:00 <= 00:30 du 02 ? oui) -> 100.0
        "2024-01-03 00:30",  # bougie du 02/01 disponible -> 200.0
    ]).values
    result = _attach_channel_support_d1(h4_dates, d1, closure_delay=closure_delay)
    assert np.isnan(result[0]), "aucune bougie D1 encore disponible à cet instant"
    assert result[1] == 100.0, "seule la bougie du 01/01 (J-1) est disponible, pas celle du 02/01 (jour même)"
    assert result[2] == 200.0, "seule la bougie du 02/01 (J-1) est disponible, pas celle du 03/01 (jour même)"

TESTS = [
    test_attach_channel_support_d1_works_with_naive_dates,
    test_attach_channel_support_d1_no_lookahead_ground_truth,
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
