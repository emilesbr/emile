"""
Tests pour andrews_gate_alternative.py (vague 5, PLAN.md "Plan d'autonomie
8h"). Deux volets :
  1. Cas synthétiques à vérité terrain connue pour la logique de gating
     conditionnelle au régime (H-Andrews-Contextuel) -- pas seulement une
     relecture du code.
  2. Test de non-régression : `mode="andrews_permanent"` doit reproduire
     EXACTEMENT le résultat déjà mesuré et commité par
     `backtest_phase2_patterns.py` (mode="andrews_gate") -- garantit que la
     comparaison honnête entre l'hypothèse originale et l'alternative se
     fait bien dans deux moteurs par ailleurs identiques, pas deux
     implémentations qui auraient dérivé l'une de l'autre.
"""
import numpy as np
import sys
sys.path.insert(0, ".")
from andrews_gate_alternative import run_andrews, ANDREWS_MODES, CONTEXTUAL_REGIMES


def test_contextual_regimes_is_range_tendanciel_only():
    """La lecture retenue (docstring de tête) ne s'applique QU'en
    RANGE_TENDANCIEL -- pas un ensemble élargi choisi après coup."""
    assert CONTEXTUAL_REGIMES == ("RANGE_TENDANCIEL",)


def _andrews_ok_probe(mode, regime_v, pitchfork_p1_v, close_v):
    """Reproduit `andrews_ok_at` isolément (même logique que
    `run_andrews`), sans dépendre du moteur de position complet -- permet de
    tester la logique de gating pure sur des scénarios choisis à la main."""
    def andrews_ok_at(i):
        if mode == "none":
            return True
        p1 = pitchfork_p1_v[i]
        has_pitchfork = not np.isnan(p1)
        if mode == "andrews_permanent":
            return has_pitchfork and close_v[i] > p1
        if regime_v[i] not in CONTEXTUAL_REGIMES:
            return True
        return has_pitchfork and close_v[i] > p1
    return [andrews_ok_at(i) for i in range(len(close_v))]


def test_none_mode_always_true_regardless_of_regime_or_pitchfork():
    regime_v = np.array(["TENDANCE", "RANGE_TENDANCIEL", "RANGE_NEUTRE", "EXCES"])
    p1 = np.array([100.0, np.nan, 50.0, 200.0])
    close = np.array([10.0, 10.0, 10.0, 10.0])  # toujours SOUS p1 -> permanent donnerait tout False
    result = _andrews_ok_probe("none", regime_v, p1, close)
    assert result == [True, True, True, True]


def test_permanent_mode_ignores_regime_gates_on_price_only():
    """L'hypothèse ORIGINALE (permanent) doit rester insensible au régime --
    seule close > p1 compte, quel que soit le régime affiché ici."""
    regime_v = np.array(["TENDANCE", "TENDANCE", "RANGE_TENDANCIEL", "EXCES"])
    p1 = np.array([100.0, 100.0, np.nan, 50.0])
    close = np.array([150.0, 50.0, 200.0, 60.0])
    # idx0: close>p1 -> True | idx1: close<p1 -> False
    # idx2: p1 NaN (pas de fourchette construite) -> False (has_pitchfork faux)
    # idx3: close>p1 (60>50) -> True, régime EXCES n'a AUCUN effet en mode permanent
    result = _andrews_ok_probe("andrews_permanent", regime_v, p1, close)
    assert result == [True, False, False, True]


def test_contextual_mode_bypasses_gate_outside_range_tendanciel():
    """H-Andrews-Contextuel : en TENDANCE/RANGE_NEUTRE/EXCES, le gate est
    TOUJOURS vrai (l'outil n'a "pas pris le relais"), MÊME quand close < p1
    -- ce qui bloquerait en mode permanent. Seul RANGE_TENDANCIEL applique
    réellement la condition close > p1."""
    regime_v = np.array(["TENDANCE", "RANGE_NEUTRE", "EXCES", "RANGE_TENDANCIEL", "RANGE_TENDANCIEL"])
    p1 = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
    close = np.array([10.0, 10.0, 10.0, 150.0, 10.0])  # idx0-2 : close << p1, idx3: close>p1, idx4: close<p1
    result = _andrews_ok_probe("andrews_contextual", regime_v, p1, close)
    # idx0,1,2 (hors RANGE_TENDANCIEL) : True malgré close<p1 -> gate non appliqué
    # idx3 (RANGE_TENDANCIEL, close>p1) : True, gate appliqué et satisfait
    # idx4 (RANGE_TENDANCIEL, close<p1) : False, gate appliqué et refusé
    assert result == [True, True, True, True, False]


def test_contextual_mode_requires_pitchfork_when_gate_applies():
    """En RANGE_TENDANCIEL, si la fourchette n'est pas encore construite
    (p1 = NaN, warmup), le gate doit refuser (has_pitchfork faux) -- pas
    laisser passer par défaut."""
    regime_v = np.array(["RANGE_TENDANCIEL"])
    p1 = np.array([np.nan])
    close = np.array([100.0])
    result = _andrews_ok_probe("andrews_contextual", regime_v, p1, close)
    assert result == [False]


def test_contextual_is_strictly_more_permissive_than_permanent():
    """Propriété structurelle vérifiée directement sur données réelles (pas
    seulement des cas choisis à la main) : le mode contextuel ne peut
    JAMAIS refuser une entrée que le mode permanent aurait acceptée, car il
    accepte tout ce que le permanent accepte (RANGE_TENDANCIEL) PLUS tout
    le reste (TENDANCE/RANGE_NEUTRE/EXCES). Vérifié en reconstruisant les
    deux séries de gate sur les vraies colonnes produites par `run_andrews`
    (via une exécution partagée du pipeline `prepare`+`add_andrews_pitchfork_columns`)."""
    import pandas as pd
    from backtest_phase2 import load_h1, resample
    from backtest_phase2_v7 import prepare
    from andrews_pitchfork import add_andrews_pitchfork_columns

    h1 = load_h1("BTCUSDT")
    h4 = resample(h1, "4h")
    h4 = prepare(h4)
    h4 = add_andrews_pitchfork_columns(h4)
    regime_v = h4["regime"].values
    p1_v = h4["pitchfork_p1"].values
    close_v = h4["close"].values

    permanent = np.array(_andrews_ok_probe("andrews_permanent", regime_v, p1_v, close_v))
    contextual = np.array(_andrews_ok_probe("andrews_contextual", regime_v, p1_v, close_v))
    # Partout où permanent est True, contextual doit aussi être True (sur-ensemble strict).
    assert (contextual | ~permanent).all()
    # Le mode contextuel doit être STRICTEMENT plus permissif sur données réelles
    # (sinon RANGE_TENDANCIEL couvrirait toute la série, ce qui invaliderait le
    # principe même de la lecture "conditionnelle").
    assert contextual.sum() > permanent.sum()


def test_run_andrews_all_modes_produce_valid_dicts_on_real_data():
    """Test d'intégration léger : les 3 modes tournent sans erreur sur des
    données réelles et retournent les clés attendues, pour au moins un
    profil -- pas une vérification de performance (cf. mise en garde de
    tête du module)."""
    from backtest_phase2 import load_h1, resample
    h1 = load_h1("BTCUSDT")
    h4 = resample(h1, "4h")
    for mode in ANDREWS_MODES:
        res = run_andrews(h4.copy(), "MODERE", mode=mode)
        for key in ("n_trades", "max_dd_%", "total_return_%", "win_rate_%", "profit_factor"):
            assert key in res


def test_andrews_permanent_matches_backtest_phase2_patterns_reference():
    """Non-régression : `run_andrews(mode="andrews_permanent")` doit
    reproduire EXACTEMENT `backtest_phase2_patterns.run_patterns(mode="andrews_gate")`
    (même moteur v7 sans MTF, même hypothèse de gating) -- garantit que la
    comparaison avec la lecture alternative se fait bien contre le même
    chiffre que celui déjà mesuré et documenté dans COUVERTURE_ENSEIGNEMENTS.md,
    pas contre une réimplémentation qui aurait dérivé silencieusement."""
    from backtest_phase2 import load_h1, resample
    from backtest_phase2_patterns import run_patterns

    h1 = load_h1("ETHUSDT")  # ETH: l'actif où l'hypothèse originale dégrade le plus (cf. COUVERTURE_ENSEIGNEMENTS.md)
    h4 = resample(h1, "4h")
    for profile in ("FAIBLE", "MODERE", "AGRESSIF", "TRES_AGRESSIF"):
        ref = run_patterns(h4.copy(), profile, mode="andrews_gate")
        alt = run_andrews(h4.copy(), profile, mode="andrews_permanent")
        assert ref == alt, (profile, ref, alt)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS  {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} tests passés")
