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
d'un cycle de travail antérieur, `cycle_ascending` s'était révélée
anti-corrélée au rendement futur sur une sinusoïde synthétique pure et
sans bruit — à l'inverse de ce que montre la validation hors-échantillon
réelle sur XRP (`OOS_VALIDATION_CYCLE_SIGN.md`, test secondaire, positif
et significatif sur données réelles, MAIS attention : ce test porte sur
`cycle_favorable`, pas sur `cycle_ascending` isolée — nuance qui n'avait
pas été relevée à l'époque). Cette divergence (occurrence #3 du pattern
récurrent, `PLAN.md`) est désormais TRANCHÉE (investigation dédiée,
`code/cycle_ascending_investigation.py` + `code/cycle_ascending_
robustness.py`) :

  - **L'artefact synthétique persiste à l'identique avec le calcul
    CAUSAL actuellement en production** (`compute_cycle_phase_causal`) :
    r(cycle_ascending, rendement futur) ≈ -0,41, p≈1e-74 sur sinusoïde
    pure, que le calcul soit batch ou causal, avec ou sans un léger bruit
    (0,05). Le passage du cycle au calcul causal (traitement du P0) n'a
    donc RIEN changé à CETTE divergence spécifique — elle ne concernait
    pas une propriété du calcul batch, contrairement à ce qu'on aurait pu
    supposer.
  - **Mesuré directement sur données RÉELLES** (BTC/ETH/BNB/SOL, H4 ET D1,
    tout l'historique disponible, `cycle_ascending_real_data.csv`) :
    aucune corrélation significative et cohérente. `|r|` entre 0,003 et
    0,045 sur les 8 séries testées, signe incohérent d'un actif à
    l'autre (négatif BTC/ETH, positif/nul BNB/SOL), et seulement 2/8
    tests sous p<0,05 — un taux compatible avec le hasard pur (8 tests
    indépendants, ~0,4 faux positif attendu à α=0,05), pas avec un effet
    réel et systématique.
  - **Robustesse** (`cycle_ascending_robustness.csv`) : l'artefact
    synthétique ne s'efface significativement qu'à un ratio bruit/
    amplitude d'environ 3-4× (bien au-delà du bruit=0,05 utilisé par
    défaut ci-dessous, qui ne change presque rien) ou par un mélange de
    plusieurs fréquences combiné à un bruit important — un niveau de
    désordre nettement supérieur à ce qu'un ajout de bruit gaussien
    standard capture d'ordinaire.

**Conclusion de l'occurrence #3 : hypothèse CONFIRMÉE, refermée comme
"expliquée, pas un bug"** — la sinusoïde synthétique pure produit un
artefact déterministe (dérivée d'un signal lisse à une seule fréquence),
mathématiquement réel mais qui ne se reproduit pas sur des prix réels
dominés par une variation non cyclique (tendance, sauts, non-
stationnarité, changements de régime). Ce n'est donc PAS un terrain de
test représentatif pour cette condition dérivée-là — sans que cela remette
en cause `test_cycle_sign_matches_ground_truth_direction` ci-dessous, qui
teste une propriété différente (le NIVEAU du sinewave, pas sa dérivée) et
reste valide. Aucune modification de `proxy_v2.py` n'a été faite ni jugée
nécessaire : `cycle_ascending` continue d'être utilisée telle quelle en
production. Détail complet des mesures : `code/cycle_ascending_
investigation.py`, `code/cycle_ascending_robustness.py`, `PLAN.md`
occurrence #3, `COUVERTURE_ENSEIGNEMENTS.md`. Ce fichier ne teste donc
toujours que la propriété la mieux établie (le niveau du signe), pas la
condition composite dérivée — mais cette dernière n'a plus besoin d'un
test de régression dédié puisqu'aucun bug n'a été confirmé, seulement un
terrain de test synthétique non représentatif pour elle.

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

Même lacune de process, trouvée une 2e fois (P0-bis, même
COUVERTURE_ENSEIGNEMENTS.md/PLAN.md, occurrence #4 du tableau) : la
détection de swing lows de `compute_ascending_lows` appelait elle aussi
`scipy.signal.argrelextrema` en batch, avec une classification en t qui
dépend des SWING_ORDER barres suivantes. Traité ce cycle-ci :
`compute_ascending_lows` ne consomme plus un swing qu'une fois confirmé
(`compute_swing_low_confirmed`) ; `test_ascending_lows_causal_matches_truncated_series`
ci-dessous en est le test de régression, sur le même modèle que
`test_cycle_phase_causal_matches_truncated_series`. Ampleur mesurée
nettement plus petite que le P0 du cycle (fenêtre fixe de 3 barres, pas la
série entière) — voir COUVERTURE_ENSEIGNEMENTS.md pour les chiffres.
"""
import numpy as np
import pandas as pd
import sys

from scipy.signal import argrelextrema
from emile.core.proxy_v2 import (
    compute_cycle_phase, compute_cycle_phase_causal, compute_tsi, CYCLE_CAUSAL_WINDOW,
    compute_ascending_lows, SWING_ORDER,
)

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

def _synthetic_swing_df(n=300, seed=2):
    """Série OHLC synthétique bruitée (marche aléatoire), pour tester la
    causalité de la détection de swing indépendamment de toute propriété
    statistique du signal (contrairement à `_synthetic_cyclical_series`,
    utile ici seulement pour avoir des creux/sommets locaux variés)."""
    rng = np.random.default_rng(seed)
    low = 100 + np.cumsum(rng.normal(0, 1, n))
    high = low + rng.uniform(0.1, 2.0, n)
    close = (low + high) / 2
    return pd.DataFrame({"low": low, "high": high, "close": close})

def test_ascending_lows_causal_matches_truncated_series():
    """Test de RÉGRESSION DE LA CAUSALITÉ de `compute_ascending_lows` — le
    même test que `test_cycle_phase_causal_matches_truncated_series`
    ci-dessus, appliqué à la réserve P0-bis (COUVERTURE_ENSEIGNEMENTS.md ⚠️,
    PLAN.md occurrence #4) plutôt qu'au cycle.

    `compute_ascending_lows` appelle `scipy.signal.argrelextrema(...,
    order=SWING_ORDER)` : la classification "swing low" à l'instant t ne
    dépend, par construction, que des `SWING_ORDER` barres avant/après t —
    jamais de la série entière (vérifié empiriquement sur BTC H4 réel et sur
    séries synthétiques, cf. `code/structure_causal_vs_batch_comparison.py`)
    — mais la VALEUR "creux ascendants" utilisée par la stratégie ne doit
    être exploitable qu'une fois ce swing réellement CONFIRMÉ (à t +
    SWING_ORDER), pas au moment du creux lui-même. Ce test vérifie
    exactement cette propriété : la valeur en t ne doit PAS changer selon
    que la série contient ou non des barres après t."""
    df = _synthetic_swing_df()
    full = compute_ascending_lows(df)

    checkpoints = [50, 100, 150, 200, 250, 299]
    for t in checkpoints:
        truncated = df.iloc[: t + 1]  # aucune barre après t
        ascending_truncated = compute_ascending_lows(truncated)
        assert full[t] == ascending_truncated[-1], (
            f"RÉGRESSION DE CAUSALITÉ (P0-bis) à t={t} : compute_ascending_lows "
            f"donne une valeur différente selon que la série contient des barres "
            f"futures (full={full[t]}) ou non (tronquée={ascending_truncated[-1]}) — "
            f"des barres futures influencent le calcul en t, cf. "
            f"COUVERTURE_ENSEIGNEMENTS.md ⚠️ P0-bis."
        )

    # Contrôle négatif : la classification BATCH brute (is_swing[t], SANS le
    # décalage de confirmation à t+SWING_ORDER) ne doit PAS passer ce test —
    # confirme que le test détecte bien le bug qu'il vise, pas seulement
    # qu'il passe toujours.
    def _raw_batch_ascending(df):
        low_v = df["low"].values
        idx = argrelextrema(low_v, np.less_equal, order=SWING_ORDER)[0]
        is_swing = np.zeros(len(df), dtype=bool)
        is_swing[idx] = True
        ascending = np.zeros(len(df), dtype=bool)
        last_lows = []
        for i in range(len(df)):
            if is_swing[i]:
                last_lows.append(low_v[i])
                if len(last_lows) > 2:
                    last_lows.pop(0)
            if len(last_lows) == 2:
                ascending[i] = last_lows[1] > last_lows[0]
        return ascending

    full_batch = _raw_batch_ascending(df)
    negative_control_checkpoints = range(10, len(df) - 1)  # balayage large, pas quelques points choisis à la main
    mismatch_found = any(
        full_batch[tt] != _raw_batch_ascending(df.iloc[: tt + 1])[-1] for tt in negative_control_checkpoints
    )
    assert mismatch_found, (
        "Le test de causalité devrait détecter que la classification BATCH brute "
        "(sans décalage de confirmation) N'EST PAS causale sur au moins un des "
        "checkpoints testés — s'il ne le détecte plus, le test lui-même a régressé "
        "et ne protège plus rien."
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
    test_ascending_lows_causal_matches_truncated_series()
    test_tsi_favorable_on_synthetic_uptrend()
    print("Tous les tests proxy_v2 passent (5/5).")
