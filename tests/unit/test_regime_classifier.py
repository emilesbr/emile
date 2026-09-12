"""
Tests pour regime_classifier.py (PLAN.md "Plan d'autonomie 8h", Vague 3,
point "Tests unitaires pour regime_classifier.py — zéro couverture malgré un
rôle central depuis v6"). `add_regime` conditionne les entrées de v6, v7,
trend_table et tous les moteurs récents, mais n'avait jamais eu de test
unitaire dédié avant celui-ci.

Structure (mode ingénieur senior, PLAN.md "Méthode de travail" — vérifier
empiriquement plutôt que relire le code) :
  1. 4 cas synthétiques à vérité terrain connue, un par régime
     (RANGE_NEUTRE / RANGE_TENDANCIEL / TENDANCE / EXCES), largeur de canal
     et pente contrôlées explicitement plutôt que déduites.
  2. La règle explicite du manuel "en cas de doute, toujours RANGE" (défaut
     documenté dans le docstring du module).
  3. Test de RÉGRESSION DE CAUSALITÉ des seuils adaptatifs (percentiles
     glissants), sur le modèle exact de
     `test_proxy_v2.py::test_cycle_phase_causal_matches_truncated_series` :
     tronquer la série et vérifier que la classification à l'instant t ne
     change pas, plus un contrôle négatif (une variante volontairement non
     causale DOIT échouer à ce même test).
  4. Vérification sur données réelles (BTC D1) que la distribution obtenue
     reste proche de celle documentée dans
     REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md (Range neutre 49,4% / Tendance
     30,5% / Excès 17,2% / Range tendanciel 2,8%) — garde-fou contre une
     régression silencieuse en amont (ex. changement du calcul EMA/ATR ou
     de la structure depuis P0-bis) qui décalerait la distribution sans que
     personne ne s'en aperçoive.
"""
import numpy as np
import pandas as pd
import sys

import pytest

# `append`, PAS `insert(0, ...)` : ce chemin absolu reste un SECOURS (pouvoir
# lancer ce fichier depuis n'importe quel répertoire), il ne doit pas PRIMER
# sur le répertoire courant. Avec `insert(0, ...)`, ce fichier chargeait le
# `regime_classifier.py` de `/home/user/emile/code` même en étant exécuté
# depuis un autre checkout (worktree) -- donc il testait un AUTRE code que
# celui d'à côté, et ne le voyait que par hasard selon l'ordre d'import de la
# suite. Corrigé ici parce que ce fichier importe désormais un symbole ajouté
# dans le même cycle (`compute_wide_channel`) : sans ce correctif, il échoue
# lancé seul et passe lancé dans la suite -- exactement le genre de test
# non déterministe que ce projet ne veut pas.

from emile.core.regime_classifier import (
    add_regime, PCTL_WINDOW, SQUEEZE_PCTL, EXCESS_PCTL, TREND_SLOPE_THRESHOLD,
    RECENT_WINDOW, compute_wide_channel, WIDE_PCTL, compute_squeeze,
    compute_range_precedes_by_trend, compute_use_neuneu, NEUNEU_MAX_BORDERS,
    compute_range_border_count,
)

N_WARMUP_MARGIN = 400  # >> PCTL_WINDOW (250) pour que les seuils adaptatifs soient toujours définis

def _make_regime_df(n=N_WARMUP_MARGIN, slope_target_pct=0.0, recent_frac_target=0.5,
                     width_val=10.0, width_override_last=None, seed=0):
    """Construit une série synthétique avec pente et fraction 'au-dessus de la
    médiane' CONTRÔLÉES explicitement sur les dernières bougies (celles
    testées), et une largeur de canal constante (donc des seuils de
    percentile adaptatif triviaux et exacts : squeeze_thresh == excess_thresh
    == width_val, cf. quantile d'un vecteur constant), sauf override explicite
    sur la toute dernière bougie pour forcer un EXCES.

    slope_target_pct : pente sur ~20 jours (SLOPE_WINDOW) telle que mesurée
      par add_regime, contrôlée en fixant directement la médiane à l'ancrage
      (n-1-20) et à la dernière bougie (n-1) — cf. docstring de add_regime :
      slope_pct = (median[t] - median[t-20j]) / median[t-20j] * 100, et sur
      un DatetimeIndex journalier sans trou, t-20j correspond exactement à
      la ligne t-20.
    recent_frac_target : fraction des RECENT_WINDOW dernières bougies où
      close > median (recent_above_frac), contrôlée directement plutôt que
      déduite d'un tirage aléatoire.
    """
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    base = 100.0
    median = np.full(n, base)
    anchor_idx = (n - 1) - 20  # ligne correspondant à "il y a ~20 jours" pour la dernière bougie
    assert anchor_idx > PCTL_WINDOW, "marge de warmup insuffisante pour ce test"
    median[anchor_idx] = base
    target_last = base * (1 + slope_target_pct / 100.0)
    ramp_len = (n - 1) - anchor_idx
    for k in range(ramp_len + 1):
        median[anchor_idx + k] = base + (target_last - base) * k / ramp_len

    close = median.copy()
    n_above = int(round(recent_frac_target * RECENT_WINDOW))
    for k in range(RECENT_WINDOW):
        idx = n - RECENT_WINDOW + k
        if k < n_above:
            close[idx] = median[idx] * 1.02  # strictement au-dessus
        else:
            close[idx] = median[idx] * 0.98  # strictement en-dessous

    width = np.full(n, width_val)
    if width_override_last is not None:
        width[-1] = width_override_last

    df = pd.DataFrame({
        "date": dates, "open": close, "high": close, "low": close, "close": close,
    })
    ctx_median = pd.Series(median)
    ctx_width_pct = pd.Series(width)
    return df, ctx_median, ctx_width_pct

# ---------------------------------------------------------------------------
# 1. Cas synthétiques à vérité terrain connue, un par régime
# ---------------------------------------------------------------------------

def test_regime_range_neutre_synthetic():
    """Canal stable (largeur constante, aucun EXCES), pente quasi nulle
    (bien en-dessous du seuil RANGE_TENDANCIEL de TREND_SLOPE_THRESHOLD*0.5
    = 0.75%), prix également réparti au-dessus/en-dessous de la médiane
    -> RANGE_NEUTRE sans ambiguïté."""
    df, ctx_median, ctx_width_pct = _make_regime_df(
        slope_target_pct=0.0, recent_frac_target=0.5, width_val=10.0,
    )
    scored = add_regime(df, ctx_median, ctx_width_pct)
    assert scored["regime"].iloc[-1] == "RANGE_NEUTRE", (
        f"attendu RANGE_NEUTRE (pente ~0%, largeur stable), obtenu "
        f"{scored['regime'].iloc[-1]!r}"
    )

def test_regime_range_tendanciel_synthetic():
    """Pente à 1,0% sur ~20 jours : au-dessus du seuil RANGE_TENDANCIEL
    (0,75%) mais en-dessous du seuil TENDANCE (1,5% = TREND_SLOPE_THRESHOLD),
    prix majoritairement au-dessus de la médiane (recent_above_frac=1.0,
    >= 0.5 requis) -> RANGE_TENDANCIEL sans ambiguïté."""
    slope = TREND_SLOPE_THRESHOLD * 0.5 + 0.25  # = 1.0% avec le seuil documenté (1.5%)
    assert TREND_SLOPE_THRESHOLD * 0.5 < slope < TREND_SLOPE_THRESHOLD, (
        "le slope choisi doit tomber strictement entre les deux seuils du "
        "manuel — sinon ce test ne prouve rien de spécifique à RANGE_TENDANCIEL"
    )
    df, ctx_median, ctx_width_pct = _make_regime_df(
        slope_target_pct=slope, recent_frac_target=1.0, width_val=10.0,
    )
    scored = add_regime(df, ctx_median, ctx_width_pct)
    assert scored["regime"].iloc[-1] == "RANGE_TENDANCIEL", (
        f"attendu RANGE_TENDANCIEL (pente {slope:.2f}% entre les deux seuils, "
        f"prix majoritairement au-dessus), obtenu {scored['regime'].iloc[-1]!r}"
    )

def test_regime_tendance_synthetic():
    """Pente à 3,0% sur ~20 jours (nettement > TREND_SLOPE_THRESHOLD=1,5%),
    prix quasi systématiquement au-dessus de la médiane (recent_above_frac
    = 1.0 >= 0.7 requis) -> TENDANCE sans ambiguïté."""
    slope = TREND_SLOPE_THRESHOLD * 2.0  # = 3.0%, nettement au-dessus du seuil
    df, ctx_median, ctx_width_pct = _make_regime_df(
        slope_target_pct=slope, recent_frac_target=1.0, width_val=10.0,
    )
    scored = add_regime(df, ctx_median, ctx_width_pct)
    assert scored["regime"].iloc[-1] == "TENDANCE", (
        f"attendu TENDANCE (pente {slope:.2f}% >> seuil, prix quasi "
        f"systématiquement au-dessus), obtenu {scored['regime'].iloc[-1]!r}"
    )

def test_regime_exces_synthetic_canal_trop_large():
    """Largeur de canal constante à 10% sur toute l'historique (donc
    squeeze_thresh == excess_thresh == 10.0 exactement, quantile d'un vecteur
    constant), sauf la toute dernière bougie dont la largeur explose à 40%
    -> largeur > excess_thresh -> EXCES, quelle que soit la pente (ici nulle),
    conformément au manuel ("canal trop large -> NE PAS TRADER")."""
    df, ctx_median, ctx_width_pct = _make_regime_df(
        slope_target_pct=0.0, recent_frac_target=0.5, width_val=10.0,
        width_override_last=40.0,
    )
    scored = add_regime(df, ctx_median, ctx_width_pct)
    assert scored["regime"].iloc[-1] == "EXCES", (
        f"attendu EXCES (canal anormalement large en fin de série), obtenu "
        f"{scored['regime'].iloc[-1]!r}"
    )

def test_regime_exces_synthetic_squeeze():
    """Même principe que ci-dessus mais dans l'autre sens : la toute
    dernière bougie a une largeur de canal anormalement ÉTROITE (1% contre
    10% partout ailleurs) -> largeur < squeeze_thresh -> EXCES ("squeeze",
    l'autre visage du régime Excès selon le manuel)."""
    df, ctx_median, ctx_width_pct = _make_regime_df(
        slope_target_pct=0.0, recent_frac_target=0.5, width_val=10.0,
        width_override_last=1.0,
    )
    scored = add_regime(df, ctx_median, ctx_width_pct)
    assert scored["regime"].iloc[-1] == "EXCES", (
        f"attendu EXCES (canal anormalement étroit -> squeeze), obtenu "
        f"{scored['regime'].iloc[-1]!r}"
    )

# ---------------------------------------------------------------------------
# 2. Règle explicite du manuel : "en cas de doute, toujours RANGE"
# ---------------------------------------------------------------------------

def test_regime_defaults_to_range_on_doubt_during_warmup():
    """Pendant la période de warmup (avant que les PCTL_WINDOW=250 bougies
    nécessaires au calcul causal des seuils adaptatifs soient disponibles),
    squeeze_thresh/excess_thresh valent NaN -> add_regime doit retomber sur
    le défaut documenté RANGE_NEUTRE, MÊME si la pente construite est
    délibérément extrême (ce qui, hors warmup, donnerait TENDANCE) — preuve
    que "en cas de doute" l'emporte bien sur toute autre condition, pas
    seulement dans le cas trivial où tout est neutre."""
    df, ctx_median, ctx_width_pct = _make_regime_df(
        n=N_WARMUP_MARGIN, slope_target_pct=0.0, recent_frac_target=0.5, width_val=10.0,
    )
    # Force une pente extrême sur les toutes premières bougies (bien avant
    # que PCTL_WINDOW bougies d'historique soient disponibles), en réécrivant
    # directement la médiane des lignes concernées.
    ctx_median = ctx_median.copy()
    ctx_median.iloc[:5] = [100.0, 100.0, 100.0, 100.0, 200.0]  # +100% sur 5 bougies
    scored = add_regime(df, ctx_median, ctx_width_pct)
    warmup_regimes = scored["regime"].iloc[:5]
    assert (warmup_regimes == "RANGE_NEUTRE").all(), (
        f"pendant le warmup (seuils adaptatifs indéfinis), le défaut "
        f"documenté ('en cas de doute, toujours RANGE') doit s'appliquer "
        f"MÊME avec une pente extrême — obtenu {warmup_regimes.tolist()}"
    )

def test_regime_defaults_to_range_on_nan_width():
    """Si ctx_width_pct est NaN à un instant donné (ex. ATR indisponible en
    tout début de série réelle), add_regime doit défaut à RANGE_NEUTRE à cet
    instant précis, même quand la pente et la position récente du prix
    seraient sans ambiguïté celles d'une TENDANCE."""
    df, ctx_median, ctx_width_pct = _make_regime_df(
        slope_target_pct=TREND_SLOPE_THRESHOLD * 2.0,  # tendance nette
        recent_frac_target=1.0, width_val=10.0,
    )
    ctx_width_pct = ctx_width_pct.copy()
    ctx_width_pct.iloc[-1] = np.nan
    scored = add_regime(df, ctx_median, ctx_width_pct)
    assert scored["regime"].iloc[-1] == "RANGE_NEUTRE", (
        f"largeur de canal NaN -> défaut RANGE_NEUTRE attendu même avec une "
        f"pente de tendance nette, obtenu {scored['regime'].iloc[-1]!r}"
    )

# ---------------------------------------------------------------------------
# 3. Régression de causalité des seuils adaptatifs (percentiles glissants)
#    — sur le modèle de
#    test_proxy_v2.py::test_cycle_phase_causal_matches_truncated_series
# ---------------------------------------------------------------------------

def _synthetic_varied_series(n=450, seed=7):
    """Série synthétique avec médiane (marche aléatoire) ET largeur de canal
    (bruit avec quelques pics) réellement VARIABLES dans le temps — condition
    nécessaire pour que ce test soit probant : si la largeur était constante,
    un calcul causal et un calcul batch (percentile sur toute la série)
    donneraient le même résultat par coïncidence, et le test ne prouverait
    rien. Les pics occasionnels de largeur garantissent aussi que des
    instants EXCES apparaissent réellement dans l'échantillon testé."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
    median = 100 + np.cumsum(rng.normal(0, 0.3, n))
    width = np.abs(rng.normal(10, 3, n)) + 1.0
    spike_idx = rng.choice(n, size=max(1, n // 40), replace=False)
    width[spike_idx] *= rng.uniform(2.5, 4.0, size=len(spike_idx))
    close = median + rng.normal(0, 1.0, n)
    df = pd.DataFrame({
        "date": dates, "open": close, "high": close, "low": close, "close": close,
    })
    return df, pd.Series(median), pd.Series(width)

def test_regime_causal_matches_truncated_series():
    """Test de RÉGRESSION DE LA CAUSALITÉ, sur le modèle exact de
    test_proxy_v2.py::test_cycle_phase_causal_matches_truncated_series :
    add_regime en un instant t donné ne doit PAS dépendre de la présence ou
    non de bougies futures après t (les seuils adaptatifs de
    regime_classifier.py sont explicitement documentés comme "percentiles
    glissants CAUSAUX", cf. commentaire au-dessus de leur calcul dans
    add_regime). On calcule le régime sur la série COMPLÈTE, puis sur la
    série TRONQUÉE à t, et on exige un résultat identique en t."""
    df, ctx_median, ctx_width_pct = _synthetic_varied_series()
    full = add_regime(df, ctx_median, ctx_width_pct)["regime"]

    checkpoints = [260, 300, 350, 400, len(df) - 1]
    for t in checkpoints:
        df_trunc = df.iloc[: t + 1].reset_index(drop=True)
        median_trunc = ctx_median.iloc[: t + 1].reset_index(drop=True)
        width_trunc = ctx_width_pct.iloc[: t + 1].reset_index(drop=True)
        truncated = add_regime(df_trunc, median_trunc, width_trunc)["regime"]
        assert full.iloc[t] == truncated.iloc[-1], (
            f"RÉGRESSION DE CAUSALITÉ à t={t} : add_regime donne une "
            f"classification différente selon que la série contient des "
            f"bougies futures (full={full.iloc[t]!r}) ou non "
            f"(tronquée={truncated.iloc[-1]!r}) — les seuils adaptatifs ne "
            f"sont plus purement causaux."
        )

    # Confirme qu'au moins une classification EXCES apparaît réellement dans
    # l'échantillon testé (sinon le test pourrait passer trivialement sans
    # jamais exercer la branche EXCES des seuils adaptatifs).
    assert (full.iloc[250:] == "EXCES").any(), (
        "aucun régime EXCES observé dans l'échantillon synthétique testé — "
        "les pics de largeur ne suffisent pas à exercer cette branche, "
        "le test de causalité ne couvrirait alors pas les seuils EXCES"
    )

def test_regime_causal_check_detects_noncausal_regression():
    """Contrôle négatif, sur le modèle exact du contrôle négatif de
    test_proxy_v2.py::test_cycle_phase_causal_matches_truncated_series :
    ce test vérifie que le test de causalité ci-dessus est réellement
    capable de DÉTECTER une régression, pas seulement qu'il passe toujours.
    On reproduit ici une variante volontairement NON causale des seuils
    adaptatifs (percentile calculé sur TOUTE la série, y compris les bougies
    futures, sans shift(1)/rolling causal) et on montre que sa classification
    à un instant t CHANGE selon que la série est tronquée ou non — la
    signature exacte du bug que le test positif est censé empêcher."""
    df, ctx_median, ctx_width_pct = _synthetic_varied_series()

    # Pour une bougie fixe `cut`, le flag EXCES (batch, non causal) obtenu en
    # tronquant pile à `cut` (donc SANS aucune bougie future) doit être
    # comparé à celui obtenu à partir de la série COMPLÈTE mais évalué à
    # cette même position d'index `cut` (donc AVEC le futur, puisque le
    # quantile batch de la série complète intègre les bougies après `cut`) —
    # seule comparaison valide "même bougie, deux contextes différents".
    def _noncausal_excess_flag_series(width_pct: pd.Series) -> np.ndarray:
        w = width_pct.values
        squeeze_thresh = np.quantile(w, SQUEEZE_PCTL)
        excess_thresh = np.quantile(w, EXCESS_PCTL)
        return (w < squeeze_thresh) | (w > excess_thresh)

    flags_full_series = _noncausal_excess_flag_series(ctx_width_pct)
    for cut in range(260, len(df) - 1):
        trunc_flags = _noncausal_excess_flag_series(ctx_width_pct.iloc[: cut + 1])
        if trunc_flags[-1] != flags_full_series[cut]:
            mismatch_found = True
            break
    assert mismatch_found, (
        "le contrôle négatif devrait détecter qu'un percentile BATCH "
        "(sans shift(1)/rolling causal) N'EST PAS causal sur au moins un "
        "point de troncature testé — s'il ne le détecte plus, le test de "
        "causalité ci-dessus ne protège plus rien."
    )

# ---------------------------------------------------------------------------
# 4. Données réelles (BTC D1) : distribution proche de celle documentée
#    (REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md), garde-fou contre une
#    régression silencieuse en amont (ex. depuis P0-bis)
# ---------------------------------------------------------------------------

# Distribution documentée dans REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md
# ("Distribution obtenue (BTC D1)"), en % du temps.
DOCUMENTED_DISTRIBUTION_PCT = {
    "RANGE_NEUTRE": 49.4,
    "TENDANCE": 30.5,
    "EXCES": 17.2,
    "RANGE_TENDANCIEL": 2.8,
}
# Tolérance large (points de %) : ce test ne vise pas à figer le chiffre au
# point près (le classificateur reste documenté comme perfectible, cf.
# "Limites documentées" du .md), seulement à attraper une régression
# silencieuse (ex. distribution qui bascule à 90% EXCES ou disparaît
# totalement d'un régime) depuis un changement en amont (P0-bis ou autre).
TOLERANCE_PCT = 10.0

@pytest.mark.data_dependent
def test_real_btc_d1_distribution_close_to_documented():
    """Reproduit exactement le calcul du bloc __main__ de
    regime_classifier.py (EMA_SLOW, ATR(14), canal EMA +/- 2*ATR) sur BTC D1
    réel, et vérifie que chacun des 4 régimes reste proche (± TOLERANCE_PCT
    points) de la distribution documentée dans
    REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md — garde-fou contre une régression
    silencieuse en amont (ex. le calcul de n_borders/structure modifié par
    P0-bis, cf. PLAN.md occurrence #4) qui déplacerait cette distribution
    sans que personne ne le remarque, faute de test."""
    from emile.backtests.backtest_phase2 import load_h1, resample, atr, EMA_SLOW

    df = resample(load_h1("BTCUSDT"), "1D")
    ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    atr_v = atr(df, 14)
    width_pct = (2 * 2 * atr_v) / ema_slow * 100
    scored = add_regime(df, ema_slow, width_pct)

    obtained_pct = (scored["regime"].value_counts(normalize=True) * 100)
    for regime, documented in DOCUMENTED_DISTRIBUTION_PCT.items():
        obtained = obtained_pct.get(regime, 0.0)
        diff = abs(obtained - documented)
        assert diff <= TOLERANCE_PCT, (
            f"RÉGRESSION DE DISTRIBUTION possible pour {regime} : documenté "
            f"{documented:.1f}% (REGIME_CLASSIFIER_RANGE_VS_TENDANCE.md), "
            f"obtenu {obtained:.1f}% (écart {diff:.1f} pts > tolérance "
            f"{TOLERANCE_PCT:.0f} pts) — vérifier si un changement en amont "
            f"(ex. P0-bis / n_borders / structure) a modifié silencieusement "
            f"le calcul du canal EMA/ATR consommé par add_regime."
        )
    # Les 4 régimes doivent tous être représentés (aucun n'a disparu).
    for regime in DOCUMENTED_DISTRIBUTION_PCT:
        assert regime in obtained_pct.index and obtained_pct[regime] > 0, (
            f"le régime {regime} n'apparaît plus du tout sur BTC D1 réel — "
            f"régression probable en amont"
        )

# ---------------------------------------------------------------------------
# compute_wide_channel — détecteur "canal TRÈS LARGE" de la règle de volatilité
# "Stop Loss = taille du canal" (TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md
# §5). Tests À VÉRITÉ TERRAIN : quantiles calculés à la main sur une série de
# 6 valeurs, pas une propriété statistique sur données réelles.
# ---------------------------------------------------------------------------
def test_wide_channel_ground_truth_hand_computed_quantile():
    """Série choisie pour que le seuil glissant soit calculable À LA MAIN.

    width  = [1, 2, 3, 4, 100, 0.5], window=4, pctl=0.50.
    shift(1) -> [nan, 1, 2, 3, 4, 100]. Une fenêtre de 4 n'a 4 valeurs non-NaN
    qu'à partir de l'indice 4 :
      i=4 : fenêtre [1,2,3,4]    -> médiane linéaire = (2+3)/2 = 2.5
            width[4]=100  > 2.5  -> TRÈS LARGE
      i=5 : fenêtre [2,3,4,100]  -> médiane linéaire = (3+4)/2 = 3.5
            width[5]=0.5  > 3.5  -> FAUX
      i=0..3 : seuil NaN (warmup) -> FAUX (défaut prudent = règle standard)
    """
    width = np.array([1.0, 2.0, 3.0, 4.0, 100.0, 0.5])
    got = compute_wide_channel(width, pctl=0.50, window=4)
    expected = np.array([False, False, False, False, True, False])
    assert got.dtype == bool, f"doit retourner un array de bool, obtenu {got.dtype}"
    assert np.array_equal(got, expected), (
        f"vérité terrain calculée à la main : attendu {expected.tolist()}, "
        f"obtenu {got.tolist()} (seuils glissants attendus : NaN,NaN,NaN,NaN,2.5,3.5)"
    )

def test_wide_channel_nan_width_is_not_wide():
    """NaN en entrée (largeur non calculable, ex. warmup ATR/EMA) -> JAMAIS
    "très large" -> règle STANDARD "Stop Loss = taille du canal", jamais la
    règle de volatilité. Même esprit de défaut prudent que "en cas de doute,
    toujours RANGE" du manuel (déjà testé plus haut pour `add_regime`)."""
    width = np.array([np.nan] * 5 + [1.0, 2.0, 3.0, 4.0] + [np.nan])
    got = compute_wide_channel(width, pctl=0.50, window=4)
    assert not got[:5].any(), "les NaN de warmup ne doivent jamais être classés très larges"
    assert not got[-1], "un NaN de largeur ne doit jamais être classé très large"

def test_wide_channel_is_causal_truncating_future_changes_nothing():
    """Régression de CAUSALITÉ, même protocole que
    `test_regime_causal_matches_truncated_series` ci-dessus : la classification
    à l'instant t ne doit dépendre d'AUCUNE bougie postérieure. On tronque la
    série et on vérifie que rien ne bouge sur la partie commune."""
    rng = np.random.default_rng(20260908)
    width = np.abs(rng.normal(10.0, 4.0, size=300)) + 1.0
    full = compute_wide_channel(width)
    cut = 240
    truncated = compute_wide_channel(width[:cut])
    assert np.array_equal(full[:cut], truncated), (
        "compute_wide_channel n'est pas causal : la classification des bougies "
        "déjà passées change quand on ajoute des bougies futures"
    )

def test_wide_channel_threshold_strictly_between_median_and_exces():
    """Garde-fou sur H-Canal-Large-3 (cf. `position_engine.py`), les deux
    contraintes de conception qui justifient le chiffre retenu :
      1. WIDE_PCTL < EXCESS_PCTL — "très large" (dimensionnement) doit rester
         un état DISTINCT d'EXCES (abstention totale), sinon la règle de
         volatilité serait vacueuse dans tout moteur qui refuse déjà d'entrer
         en régime EXCES.
      2. WIDE_PCTL > 0.50 — un canal "très large" doit être plus large que la
         *"largeur moyenne du canal de tendance récent"*, seule autre référence
         de largeur du corpus (TRADING_LESSONS_ZONE_ACCUMULATION.md)."""
    assert WIDE_PCTL < EXCESS_PCTL, (
        f"WIDE_PCTL={WIDE_PCTL} doit rester strictement sous EXCESS_PCTL="
        f"{EXCESS_PCTL} (sinon 'canal très large' se confond avec EXCES et la "
        f"règle de volatilité devient inapplicable)"
    )
    assert WIDE_PCTL > 0.50, (
        f"WIDE_PCTL={WIDE_PCTL} doit rester strictement au-dessus de la médiane"
    )

def test_wide_channel_stricter_percentile_selects_a_subset():
    """Conséquence directe de la contrainte 1 ci-dessus, vérifiée sur une série
    concrète plutôt que supposée : l'ensemble des bougies détectées au
    percentile EXCES est INCLUS dans celui détecté au percentile "très large"
    — donc il existe bien des bougies très larges qui ne sont PAS en excès (le
    scénario que la règle de volatilité vise), et le test serait non-vacueux."""
    rng = np.random.default_rng(4242)
    width = np.abs(rng.normal(10.0, 4.0, size=600)) + 1.0
    loose = compute_wide_channel(width, pctl=WIDE_PCTL)
    strict = compute_wide_channel(width, pctl=EXCESS_PCTL)
    assert np.all(loose[strict]), (
        "toute bougie détectée au percentile EXCES doit l'être aussi au "
        "percentile 'très large' (percentile plus bas = ensemble plus large)"
    )
    assert loose.sum() > strict.sum() > 0, (
        f"test vacueux : loose={loose.sum()} strict={strict.sum()} — il doit "
        f"exister des bougies 'très larges' qui ne sont pas en EXCES"
    )

# ---------------------------------------------------------------------------
# compute_squeeze — détecteur "canal TRÈS ÉTROIT" pour l'invalidation 3BR par
# squeeze UT+1 (guide officiel PRO Indicators, cf. `range_gates.py`). Miroir
# exact de `compute_wide_channel` ci-dessus (même patron de tests).
# ---------------------------------------------------------------------------
def test_squeeze_ground_truth_hand_computed_quantile():
    """Série choisie pour que le seuil glissant soit calculable À LA MAIN.

    width  = [100, 4, 3, 2, 1, 0.5], window=4, pctl=0.50.
    shift(1) -> [nan, 100, 4, 3, 2, 1]. Une fenêtre de 4 n'a 4 valeurs
    non-NaN qu'à partir de l'indice 4 :
      i=4 : fenêtre [100,4,3,2] -> médiane linéaire = (3+4)/2 = 3.5
            width[4]=1   < 3.5  -> SQUEEZE
      i=5 : fenêtre [4,3,2,1]   -> médiane linéaire = (2+3)/2 = 2.5
            width[5]=0.5 < 2.5  -> SQUEEZE
      i=0..3 : seuil NaN (warmup) -> FAUX (défaut prudent = pas squeeze)
    """
    width = np.array([100.0, 4.0, 3.0, 2.0, 1.0, 0.5])
    got = compute_squeeze(width, pctl=0.50, window=4)
    expected = np.array([False, False, False, False, True, True])
    assert got.dtype == bool, f"doit retourner un array de bool, obtenu {got.dtype}"
    assert np.array_equal(got, expected), (
        f"vérité terrain calculée à la main : attendu {expected.tolist()}, "
        f"obtenu {got.tolist()} (seuils glissants attendus : NaN,NaN,NaN,NaN,3.5,2.5)"
    )

def test_squeeze_nan_width_is_not_squeeze():
    """NaN en entrée -> JAMAIS squeeze (défaut prudent, même esprit que
    `compute_wide_channel`/"en cas de doute, toujours RANGE")."""
    width = np.array([np.nan] * 5 + [4.0, 3.0, 2.0, 1.0] + [np.nan])
    got = compute_squeeze(width, pctl=0.50, window=4)
    assert not got[:5].any(), "les NaN de warmup ne doivent jamais être classés squeeze"
    assert not got[-1], "un NaN de largeur ne doit jamais être classé squeeze"

def test_squeeze_is_causal_truncating_future_changes_nothing():
    """Régression de CAUSALITÉ, même protocole que
    `test_wide_channel_is_causal_truncating_future_changes_nothing`."""
    rng = np.random.default_rng(20260912)
    width = np.abs(rng.normal(10.0, 4.0, size=300)) + 1.0
    full = compute_squeeze(width)
    cut = 240
    truncated = compute_squeeze(width[:cut])
    assert np.array_equal(full[:cut], truncated), (
        "compute_squeeze n'est pas causal : la classification des bougies "
        "déjà passées change quand on ajoute des bougies futures"
    )

def test_squeeze_is_subset_of_exces_regime():
    """Garde-fou : `SQUEEZE_PCTL` est l'un des deux percentiles qui composent
    `EXCES` dans `add_regime` (`w < squeeze_thresh OR w > excess_thresh`) --
    donc toute bougie détectée `compute_squeeze` doit AUSSI être classée
    `EXCES` par `add_regime` sur la MÊME série (même fenêtre, même
    percentile). Vérifié directement plutôt que supposé, pour ne pas
    reposer sur une coïncidence de constantes qui pourrait diverger un jour.

    `_make_regime_df` construit par défaut une largeur CONSTANTE (seuils
    triviaux, aucune bougie squeeze possible en comparaison stricte) --
    remplacée ici par une largeur variable (même patron que les tests de
    causalité ci-dessus), df/ctx_median réutilisés tels quels (leur valeur
    ne conditionne pas ce garde-fou, seule la largeur compte pour EXCES)."""
    df, ctx_median, _ = _make_regime_df(seed=7)
    rng = np.random.default_rng(7)
    ctx_width_pct = pd.Series(np.abs(rng.normal(10.0, 4.0, size=len(df))) + 1.0)
    squeezed = compute_squeeze(ctx_width_pct)
    regime_df = add_regime(df, ctx_median, ctx_width_pct)
    is_exces = (regime_df["regime"] == "EXCES").to_numpy()
    assert np.all(is_exces[squeezed]), (
        "une bougie détectée squeeze par compute_squeeze n'est pas classée EXCES "
        "par add_regime -- les deux fonctions doivent utiliser exactement le "
        "même seuil (SQUEEZE_PCTL, même fenêtre PCTL_WINDOW, même construction causale)"
    )
    assert squeezed.sum() > 0, "test vacueux : aucune bougie squeeze détectée sur ce scénario"

# ---------------------------------------------------------------------------
# compute_range_precedes_by_trend / compute_use_neuneu — routage RANGE
# "3ème borne" vs "Neuneu" (guide officiel PRO Indicators, cf. `PLAN.md`
# "32e application"). Tests À VÉRITÉ TERRAIN sur une séquence de régimes
# choisie à la main, pas une propriété statistique.
# ---------------------------------------------------------------------------
def test_precedes_by_trend_ground_truth_hand_computed():
    """Séquence :
      idx  0    1    2         3         4         5         6
      reg TEND EXCES RANGE_NEU RANGE_TEN TEND      RANGE_NEU RANGE_TEN
    Dernier régime non-RANGE avant chaque bougie (une bougie non-range EST
    son propre "dernier régime non-range" -- la fonction est calculée pour
    toutes les bougies, seule sa valeur sur les bougies RANGE sert au
    routage, mais son comportement sur les bougies non-range est vérifié
    explicitement ici plutôt que laissé non spécifié) :
      idx 0 (TENDANCE, non-range) -> dernier non-range = lui-même = TENDANCE -> True
      idx 1 (EXCES, non-range) -> dernier non-range = lui-même = EXCES -> False
      idx 2,3 (RANGE) -> dernier non-range = idx 1 = EXCES -> precedes_by_trend=False
      idx 4 (TENDANCE, non-range) -> dernier non-range = idx 4 lui-même = TENDANCE
      idx 5,6 (RANGE) -> dernier non-range = idx 4 = TENDANCE -> precedes_by_trend=True
    """
    regime = np.array([
        "TENDANCE", "EXCES", "RANGE_NEUTRE", "RANGE_TENDANCIEL",
        "TENDANCE", "RANGE_NEUTRE", "RANGE_TENDANCIEL",
    ], dtype=object)
    precedes, no_prior = compute_range_precedes_by_trend(regime)
    expected_precedes = np.array([True, False, False, False, True, True, True])
    expected_no_prior = np.array([False] * 7)
    assert np.array_equal(precedes, expected_precedes), (
        f"attendu {expected_precedes.tolist()}, obtenu {precedes.tolist()}"
    )
    assert np.array_equal(no_prior, expected_no_prior), (
        f"attendu {expected_no_prior.tolist()}, obtenu {no_prior.tolist()} "
        "(un régime non-range a déjà été vu dès idx 0, no_prior_regime doit rester faux partout)"
    )

def test_precedes_by_trend_no_prior_regime_at_series_start():
    """Une série qui commence DÉJÀ en RANGE (aucun régime non-range observé
    avant) doit être `no_prior_regime=True` sur toute cette première
    séquence, quel que soit le régime qui suit -- "pas assez d'historique",
    une des 3 conditions littérales du guide pour router vers Neuneu."""
    regime = np.array([
        "RANGE_NEUTRE", "RANGE_TENDANCIEL", "RANGE_NEUTRE",  # aucun non-range encore vu
        "TENDANCE",                                            # 1er non-range
        "RANGE_NEUTRE",                                        # précédé par TENDANCE désormais
    ], dtype=object)
    precedes, no_prior = compute_range_precedes_by_trend(regime)
    assert np.array_equal(no_prior, [True, True, True, False, False]), (
        f"obtenu {no_prior.tolist()}"
    )
    # Les 3 premières bougies : precedes_by_trend doit être FAUX (pas juste
    # "on ne sait pas") -- le routage vers Neuneu passe par `no_prior_regime`
    # explicitement, pas par une valeur ambiguë de `precedes_by_trend`.
    assert not precedes[:3].any(), "precedes_by_trend doit être faux quand aucun régime antérieur n'existe"
    assert precedes[4], "la 5e bougie, précédée d'une TENDANCE réelle, doit être precedes_by_trend=True"

def test_range_border_count_ground_truth_hand_computed():
    """Séquence choisie à la main :
      idx    0    1    2    3    4    5    6    7    8    9
      reg  TEND RANGE RANGE RANGE RANGE TEND RANGE RANGE RANGE RANGE
      swng    F    F    T    F    T    F    F    T    T    F
    Run 1 (idx 1-4, entrée en range à idx 1) : bornes confirmées à idx 2 et
    4 -> compte 0,0,1,1 sur idx 1,2,3,4 (la borne d'une bougie compte à
    PARTIR de cette bougie, pas avant).
    Run 2 (idx 6-9, nouveau run après idx 5=TENDANCE) : remis à 0. Bornes à
    idx 7,8 -> compte 0,1,2,2 sur idx 6,7,8,9.
    Hors range (idx 0, 5) : valeur neutre 0."""
    regime = np.array(["TENDANCE", "RANGE_NEUTRE", "RANGE_NEUTRE", "RANGE_NEUTRE", "RANGE_NEUTRE",
                        "TENDANCE", "RANGE_NEUTRE", "RANGE_NEUTRE", "RANGE_NEUTRE", "RANGE_NEUTRE"], dtype=object)
    swing = np.array([False, False, True, False, True, False, False, True, True, False])
    got = compute_range_border_count(regime, swing)
    expected = np.array([0.0, 0.0, 1.0, 1.0, 2.0, 0.0, 0.0, 1.0, 2.0, 2.0])
    assert np.array_equal(got, expected), f"attendu {expected.tolist()}, obtenu {got.tolist()}"

def test_range_border_count_is_not_perpetually_high_on_real_btc_data():
    """Garde-fou motivant CETTE fonction plutôt que la réutilisation de
    `n_borders` (cf. sa docstring) : sur des données réelles, le compte par
    ÉPISODE doit redescendre à 0 régulièrement (à chaque nouveau range),
    contrairement à `n_borders` (glissant, médian=9, >4 sur 99,7% des
    bougies BTC H4 réel -- mesuré, cf. PLAN.md). Vérifié ici sur un
    scénario synthétique avec des runs de range COURTS (moins de 4 bornes
    chacun) : le compte ne doit JAMAIS dépasser le nombre de swings dans le
    run le plus long, pas continuer à grimper sans fin."""
    rng = np.random.default_rng(20260912)
    n = 500
    # Alterne runs courts de RANGE (5-8 bougies) et bougies isolées de TENDANCE
    regimes = []
    while len(regimes) < n:
        regimes += ["TENDANCE"]
        regimes += ["RANGE_NEUTRE"] * int(rng.integers(5, 9))
    regime = np.array(regimes[:n], dtype=object)
    swing = rng.random(n) < 0.3   # ~30% des bougies sont un swing confirmé
    got = compute_range_border_count(regime, swing)
    max_run_len = 8
    assert got.max() <= max_run_len, (
        f"compte de bornes par épisode = {got.max()}, ne devrait jamais dépasser la longueur "
        f"du plus long run ({max_run_len}) si le compte est bien remis à 0 à chaque nouveau range"
    )
    assert (got[np.array(regime) == "TENDANCE"] == 0).all(), (
        "hors RANGE, le compte doit rester à la valeur neutre 0"
    )

def test_use_neuneu_routes_on_not_preceded_by_trend():
    """Contrôle direct de la 1ère condition de routage : un range précédé
    d'un EXCES (pas d'une TENDANCE), avec peu de bornes et un historique
    suffisant, doit quand même router vers Neuneu."""
    regime = np.array(["TENDANCE"] * 10 + ["EXCES"] + ["RANGE_NEUTRE"] * 5, dtype=object)
    border_count = np.full(len(regime), 1.0)   # loin sous le seuil
    use_neuneu = compute_use_neuneu(regime, border_count)
    assert use_neuneu[-5:].all(), "range précédé d'un EXCES (pas d'une TENDANCE) doit router vers Neuneu"

def test_use_neuneu_routes_on_too_many_borders():
    """Contrôle direct de la 2e condition : un range précédé d'une
    TENDANCE réelle, mais avec `border_count > NEUNEU_MAX_BORDERS`, doit
    quand même router vers Neuneu."""
    regime = np.array(["TENDANCE"] * 10 + ["RANGE_NEUTRE"] * 5, dtype=object)
    border_count = np.full(len(regime), float(NEUNEU_MAX_BORDERS) + 1.0)
    use_neuneu = compute_use_neuneu(regime, border_count)
    assert use_neuneu[-5:].all(), (
        f"border_count={NEUNEU_MAX_BORDERS + 1} > NEUNEU_MAX_BORDERS={NEUNEU_MAX_BORDERS} "
        "doit router vers Neuneu même si précédé d'une tendance"
    )

def test_use_neuneu_false_when_preceded_by_trend_and_few_borders():
    """Contrôle POSITIF des deux tests ci-dessus (sinon ils pourraient
    passer trivialement sur une fonction qui route toujours vers Neuneu) :
    précédé d'une TENDANCE réelle, peu de bornes, historique suffisant ->
    NE PAS router vers Neuneu (structure 3ème borne standard)."""
    regime = np.array(["TENDANCE"] * 10 + ["RANGE_NEUTRE"] * 5, dtype=object)
    border_count = np.full(len(regime), 1.0)
    use_neuneu = compute_use_neuneu(regime, border_count)
    assert not use_neuneu[-5:].any(), (
        "précédé d'une tendance réelle + peu de bornes ne doit PAS router vers Neuneu"
    )

def test_use_neuneu_nan_border_count_does_not_trigger_too_many_borders():
    """`border_count` NaN (warmup, ex. tout début de série) ne doit JAMAIS
    être lu comme "trop de bornes" -- comparaison
    numpy `NaN > seuil` vaut déjà `False`, vérifié explicitement plutôt que
    supposé (le routage retombe alors sur les 2 autres conditions)."""
    regime = np.array(["TENDANCE"] * 10 + ["RANGE_NEUTRE"] * 5, dtype=object)
    border_count = np.full(len(regime), np.nan)
    use_neuneu = compute_use_neuneu(regime, border_count)
    assert not use_neuneu[-5:].any(), (
        "border_count=NaN ne doit pas, à lui seul, router vers Neuneu (précédé d'une tendance réelle par ailleurs)"
    )

if __name__ == "__main__":
    tests = [
        test_regime_range_neutre_synthetic,
        test_regime_range_tendanciel_synthetic,
        test_regime_tendance_synthetic,
        test_regime_exces_synthetic_canal_trop_large,
        test_regime_exces_synthetic_squeeze,
        test_regime_defaults_to_range_on_doubt_during_warmup,
        test_regime_defaults_to_range_on_nan_width,
        test_regime_causal_matches_truncated_series,
        test_regime_causal_check_detects_noncausal_regression,
        test_real_btc_d1_distribution_close_to_documented,
        test_wide_channel_ground_truth_hand_computed_quantile,
        test_wide_channel_nan_width_is_not_wide,
        test_wide_channel_is_causal_truncating_future_changes_nothing,
        test_wide_channel_threshold_strictly_between_median_and_exces,
        test_wide_channel_stricter_percentile_selects_a_subset,
        test_squeeze_ground_truth_hand_computed_quantile,
        test_squeeze_nan_width_is_not_squeeze,
        test_squeeze_is_causal_truncating_future_changes_nothing,
        test_squeeze_is_subset_of_exces_regime,
        test_precedes_by_trend_ground_truth_hand_computed,
        test_precedes_by_trend_no_prior_regime_at_series_start,
        test_range_border_count_ground_truth_hand_computed,
        test_range_border_count_is_not_perpetually_high_on_real_btc_data,
        test_use_neuneu_routes_on_not_preceded_by_trend,
        test_use_neuneu_routes_on_too_many_borders,
        test_use_neuneu_false_when_preceded_by_trend_and_few_borders,
        test_use_neuneu_nan_border_count_does_not_trigger_too_many_borders,
    ]
    for t in tests:
        t()
        print(f"OK  {t.__name__}")
    print(f"\nTous les tests regime_classifier passent ({len(tests)}/{len(tests)}).")
