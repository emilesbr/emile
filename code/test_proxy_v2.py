"""
Tests de régression pour proxy_v2.py — lacune de process identifiée lors de
l'audit du [dernier cycle de travail] : le bug de signe du cycle
(AUDIT_QUALITE_ET_CORRECTION_CYCLE.md) n'a été trouvé QUE parce qu'un
contrôle aléatoire de bout en bout a, par chance, mis en évidence une
anti-corrélation. Aucun test unitaire n'aurait empêché une régression du
même type (ex. quelqu'un qui retire le "-" par erreur en refactorant).
Ce fichier comble cette lacune pour la composante la plus fragile : le
signe de la convention de phase.

Contrairement à test_position_engine.py (cas calculés à la main), ici on
teste une PROPRIÉTÉ statistique sur un signal synthétique dont le sens
"vérité terrain" est connu par construction (série purement cyclique, pas
de tendance), pas un résultat exact.

Note de scope, pour ne pas surinterpréter ce que ce fichier couvre : il
teste le SIGNE du niveau de `sinewave` (la grandeur diagnostiquée dans
AUDIT_QUALITE_ET_CORRECTION_CYCLE.md), pas la condition composite
`cycle_ascending` (dérivée du sinewave d'une barre à l'autre) réellement
utilisée dans `add_proxy_v2_score`. En creusant ce point pendant l'audit
de ce [dernier cycle de travail], `cycle_ascending` s'est révélée
anti-corrélée au rendement futur sur une sinusoïde synthétique pure et
sans bruit — à l'inverse de ce que montre la validation hors-échantillon
réelle sur XRP (`OOS_VALIDATION_CYCLE_SIGN.md`, test secondaire, positif
et significatif sur données réelles). Le désaccord entre les deux
suggère que la sinusoïde synthétique idéalisée (une seule fréquence, sans
bruit) n'est pas un terrain de test représentatif pour cette condition
dérivée-là, plutôt qu'une vraie régression de `cycle_ascending` — mais
ça reste une divergence non résolue, documentée ici et dans
COUVERTURE_ENSEIGNEMENTS.md plutôt que passée sous silence. Ce fichier ne
teste donc que la propriété la mieux établie (le niveau), pas la
condition composite complète.

Limite distincte, plus significative, découverte dans le même effort et
désormais TRAITÉE (P0, cf. COUVERTURE_ENSEIGNEMENTS.md/PLAN.md) : l'ancienne
`compute_cycle_phase` appelait `scipy.signal.hilbert` sur la série ENTIÈRE
d'un coup (non causal) — déjà documenté comme limite connue dans
`OOS_VALIDATION_CYCLE_SIGN.md` section 5, mais jamais remonté jusqu'ici
avant ce cycle de travail. `compute_cycle_phase_causal` (fenêtre glissante)
la remplace désormais dans `add_proxy_v2_score` ;
`test_cycle_phase_causal_matches_truncated_series` ci-dessous teste la
CAUSALITÉ elle-même (pas seulement le signe) pour garantir qu'on ne
réintroduit jamais ce bug. Sur données réelles (BTC/ETH/BNB/SOL), la
corrélation causale mesurée est proche de zéro et non significative, très
inférieure à la corrélation batch (~0,29) — voir COUVERTURE_ENSEIGNEMENTS.md
pour le détail chiffré et la conclusion honnête (edge causal non confirmé
sur les actifs testés).
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from proxy_v2 import compute_cycle_phase, compute_cycle_phase_causal, compute_tsi, CYCLE_CAUSAL_WINDOW


def _synthetic_cyclical_series(n=2000, period=40, amplitude=5.0, noise=0.05, seed=0):
    """Prix purement cyclique (pas de tendance) : close = 100 + A*sin(2*pi*t/T).
    Par construction, le NIVEAU de sinewave (proportionnel à sin(phase) à un
    signe près) doit être positivement corrélé au rendement qui suit —
    c'est la vérité terrain qu'un signe correct de compute_cycle_phase doit
    capturer, et c'est exactement la grandeur diagnostiquée lors de la
    découverte du bug de signe (corrélation composante-vs-rendement futur)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    close = 100 + amplitude * np.sin(2 * np.pi * t / period) + rng.normal(0, noise, n)
    return pd.Series(close)


def test_cycle_sign_matches_ground_truth_direction():
    """Régression du bug corrigé dans AUDIT_QUALITE_ET_CORRECTION_CYCLE.md :
    le NIVEAU de compute_cycle_phase doit être positivement corrélé au
    rendement des barres suivantes sur une série purement cyclique connue.
    Un signe inversé par erreur (retour à `sin(phase)` sans le `-`) ferait
    échouer ce test (corrélation négative)."""
    close = _synthetic_cyclical_series()
    sinewave = compute_cycle_phase(close)

    fwd_return = close.shift(-3).values - close.values  # rendement à 3 barres
    valid = ~np.isnan(fwd_return)
    assert valid.sum() > 100, "échantillon synthétique trop petit pour conclure"

    corr = np.corrcoef(sinewave[valid], fwd_return[valid])[0, 1]
    assert corr > 0.5, (
        f"RÉGRESSION DU BUG DE SIGNE : le niveau de sinewave devrait être "
        f"fortement corrélé (positivement) au rendement futur sur une série "
        f"synthétique purement cyclique, obtenu corr={corr:.3f} — vérifier le "
        f"signe dans compute_cycle_phase (cf. AUDIT_QUALITE_ET_CORRECTION_CYCLE.md)"
    )


def test_cycle_phase_bounded():
    """Garde-fou basique : sinewave doit toujours rester dans [-1, 1]
    (c'est un sinus), sinon une régression de calcul est passée inaperçue."""
    close = _synthetic_cyclical_series()
    sinewave = compute_cycle_phase(close)
    assert np.nanmax(np.abs(sinewave)) <= 1.0 + 1e-9


def test_cycle_phase_causal_matches_truncated_series():
    """Test de RÉGRESSION DE LA CAUSALITÉ elle-même (pas du signe) — le test
    qui aurait empêché la découverte tardive du problème P0
    (COUVERTURE_ENSEIGNEMENTS.md ⚠️) s'il avait existé plus tôt.

    Propriété attendue d'un calcul causal : la valeur de
    compute_cycle_phase_causal en un instant t donné ne doit PAS changer
    selon que la série contient ou non des barres futures après t. On calcule
    donc sinewave sur la série COMPLÈTE, puis sur la série TRONQUÉE à t
    (aucune barre après t), et on exige que la valeur en t soit identique
    (tolérance flottante) dans les deux cas — sinon des barres futures ont
    influencé le calcul en t, ce qui est exactement le bug qu'on corrige ici.

    Contre-exemple attendu : ce même test échouerait franchement (pas une
    tolérance flottante, un écart massif) si on l'appliquait à l'ancienne
    `compute_cycle_phase` (batch), ce qui est vérifié explicitement en
    seconde moitié de ce test — pour s'assurer que le test sait bien
    distinguer un calcul causal d'un calcul non causal, pas seulement
    toujours passer."""
    close = _synthetic_cyclical_series(n=500, seed=3)
    window = 60  # plus petit que CYCLE_CAUSAL_WINDOW pour un test rapide, sans perte de généralité
    full = compute_cycle_phase_causal(close, window=window)

    # Teste plusieurs instants t, bien après le warmup (>= window)
    checkpoints = [100, 200, 300, 400, 499]
    for t in checkpoints:
        truncated = close.iloc[: t + 1]  # aucune barre après t
        sinewave_truncated = compute_cycle_phase_causal(truncated, window=window)
        assert np.isclose(full[t], sinewave_truncated[-1], atol=1e-9), (
            f"RÉGRESSION DE CAUSALITÉ à t={t} : compute_cycle_phase_causal donne une "
            f"valeur différente selon que la série contient des barres futures "
            f"(full={full[t]:.6f}) ou non (tronquée={sinewave_truncated[-1]:.6f}) — "
            f"des barres futures influencent le calcul en t, ce qui est précisément "
            f"le bug P0 (cf. COUVERTURE_ENSEIGNEMENTS.md)."
        )

    # Contrôle négatif : la version BATCH (non causale) ne doit PAS passer ce
    # test — confirme que le test est capable de détecter le bug qu'il vise.
    t = 300
    full_batch = compute_cycle_phase(close)
    truncated_batch = compute_cycle_phase(close.iloc[: t + 1])
    assert not np.isclose(full_batch[t], truncated_batch[-1], atol=1e-9), (
        "Le test de causalité devrait détecter que compute_cycle_phase (batch) "
        "N'EST PAS causale (valeur différente sur série tronquée) — s'il ne le "
        "détecte plus, le test lui-même a régressé et ne protège plus rien."
    )


def test_tsi_favorable_on_synthetic_uptrend():
    """Sur une tendance haussière synthétique nette (pas de composante
    cyclique), le TSI doit finir par indiquer 'momentum favorable'
    (tsi > signal_line) — sinon la formule TSI elle-même est cassée."""
    n = 300
    close = pd.Series(100 + np.linspace(0, 50, n) + np.random.default_rng(1).normal(0, 0.2, n))
    tsi, signal_line = compute_tsi(close)
    tail_favorable = (tsi.iloc[-30:] > signal_line.iloc[-30:]).mean()
    assert tail_favorable > 0.5, (
        f"TSI devrait être majoritairement favorable en fin de tendance haussière "
        f"nette, obtenu seulement {tail_favorable:.0%} des 30 dernières barres"
    )


if __name__ == "__main__":
    test_cycle_sign_matches_ground_truth_direction()
    test_cycle_phase_bounded()
    test_cycle_phase_causal_matches_truncated_series()
    test_tsi_favorable_on_synthetic_uptrend()
    print("Tous les tests proxy_v2 passent (4/4).")
