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
qui N'EST PAS testée ici (nécessiterait un vrai recalcul causal/rolling,
hors scope de ce fichier) : `compute_cycle_phase` appelle
`scipy.signal.hilbert` sur la série ENTIÈRE d'un coup (non causal) — déjà
documenté comme limite connue dans `OOS_VALIDATION_CYCLE_SIGN.md` section
5, mais jamais remonté jusqu'ici dans `COUVERTURE_ENSEIGNEMENTS.md`/
`PLAN.md`. Sur une sinusoïde synthétique propre, la corrélation
sinewave/rendement-futur mesurée en mode batch (0,93) est très supérieure
à la même corrélation recalculée en fenêtre expansive causale (0,38) —
l'ordre de grandeur de l'inflation n'est pas nul. Voir
COUVERTURE_ENSEIGNEMENTS.md pour le suivi de ce point en tant que lacune
prioritaire.
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from proxy_v2 import compute_cycle_phase, compute_tsi


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
    test_tsi_favorable_on_synthetic_uptrend()
    print("Tous les tests proxy_v2 passent (3/3).")
