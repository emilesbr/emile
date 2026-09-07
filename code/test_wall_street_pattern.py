"""
Tests pour wall_street_pattern.py (règle "Wall Street", backlog PLAN.md
item 7). Écrit directement (pas par un agent délégué) suite à l'incident
de rate-limit qui a interrompu les 4 agents de la vague 2 juste après
qu'ils aient fini les modules eux-mêmes (fichiers présents, non testés) --
ce fichier comble le manquant plutôt que de laisser le module non vérifié.
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from wall_street_pattern import compute_broadening_structure, add_wall_street_column

ORDER = 3


def _swing_series(lows, highs, order=ORDER):
    """Construit une série synthétique dont les swings low/high (au sens
    argrelextrema order=`order`) sont exactement `lows`/`highs` aux index
    donnés. Base = rampe STRICTEMENT monotone (pas de plateau -> pas de
    swing parasite par égalité, vérifié empiriquement : une rampe stricte
    n'a aucun extremum local intérieur), les points imposés dominent
    localement (valeurs loin de la rampe)."""
    n = max(max(i for i, _ in lows), max(i for i, _ in highs)) + order + 5
    low_v = 1000.0 + np.arange(n) * 0.01  # rampe stricte, aucun plateau
    high_v = 1000.0 + np.arange(n) * 0.01
    for i, v in lows:
        low_v[i] = v
    for i, v in highs:
        high_v[i] = v
    return pd.DataFrame({"low": low_v, "high": high_v})


def test_broadening_detected_when_highs_rise_and_lows_fall():
    """2 swing highs ascendants ET 2 swing lows descendants simultanément
    -> broadening vrai une fois les deux confirmés (H1, docstring)."""
    lows = [(10, 90.0), (30, 80.0)]      # 2e creux plus bas (descendant), sous la rampe (~1000)
    highs = [(15, 1100.0), (35, 1200.0)]  # 2e sommet plus haut (ascendant), au-dessus de la rampe
    df = _swing_series(lows, highs)
    broadening, higher_highs, lower_lows = compute_broadening_structure(df, order=ORDER)
    # Confirmation du 2e low à idx=30+ORDER, du 2e high à idx=35+ORDER ->
    # broadening seulement possible à partir du dernier des deux.
    t_ready = max(30, 35) + ORDER
    assert lower_lows[t_ready], "2e creux plus bas que le 1er -> lower_lows doit être vrai"
    assert higher_highs[t_ready], "2e sommet plus haut que le 1er -> higher_highs doit être vrai"
    assert broadening[t_ready], "les deux ensemble -> broadening (Wall Street) doit être vrai"


def test_no_broadening_when_only_highs_rise():
    """Sommets ascendants mais creux ASCENDANTS aussi (pas de creux qui
    baisse) -> pas de structure en élargissement, juste une tendance
    haussière normale."""
    lows = [(10, 90.0), (30, 95.0)]      # 2e creux plus HAUT (pas Wall Street), toujours sous la rampe
    highs = [(15, 1100.0), (35, 1200.0)]
    df = _swing_series(lows, highs)
    broadening, higher_highs, lower_lows = compute_broadening_structure(df, order=ORDER)
    t_ready = max(30, 35) + ORDER
    assert higher_highs[t_ready]
    assert not lower_lows[t_ready]
    assert not broadening[t_ready], "creux ascendants -> pas Wall Street même si sommets ascendants"


def test_wall_street_column_matches_broadening():
    lows = [(10, 90.0), (30, 80.0)]
    highs = [(15, 1100.0), (35, 1200.0)]
    df = _swing_series(lows, highs)
    out = add_wall_street_column(df, order=ORDER)
    broadening, _, _ = compute_broadening_structure(df, order=ORDER)
    assert (out["wall_street_active"].values == broadening).all()


def test_causal_no_future_leakage():
    """Régression de causalité (même famille que le P0/P0-bis) : la
    classification à l'instant t ne doit pas changer si on tronque la
    série juste après que les swings pertinents à t soient confirmés."""
    lows = [(10, 90.0), (30, 80.0)]
    highs = [(15, 1100.0), (35, 1200.0)]
    df = _swing_series(lows, highs)
    broadening_full, _, _ = compute_broadening_structure(df, order=ORDER)
    t = max(30, 35) + ORDER
    truncated = df.iloc[: t + 1].reset_index(drop=True)
    broadening_trunc, _, _ = compute_broadening_structure(truncated, order=ORDER)
    assert broadening_trunc[-1] == broadening_full[t], (
        "la classification Wall Street à l'instant t a changé selon que "
        "des barres futures sont présentes ou non -- régression causale"
    )


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} tests passés")
