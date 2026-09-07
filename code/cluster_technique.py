"""
"Cluster Technique" — second pattern indépendant du proxy_v2 existant, extrait
de `TRADING_LESSONS_CLUSTERS_PRIX.md` (source #16, cf. `TRADING_LESSONS_INDEX.md`
et `COUVERTURE_ENSEIGNEMENTS.md`, ligne "Diversification 1%+1% + Cluster
Technique"). Backlog `PLAN.md`, item 7 de la liste "Patterns/outils jamais
construits".

CE QUE LA SOURCE #16 DIT LITTÉRALEMENT (citations exactes, pour traçabilité)
-----------------------------------------------------------------------------
    "Nouveau pattern : le 'Cluster Technique'. Distinct du 'Trade du Jour'
    (communiqué sur Discord) : le Cluster Technique exige impérativement un
    flux tendanciel établi (post-breakout), alors que le Trade du Jour peut
    survenir hors de toute tendance.

    Composants :
    - Moyenne Mobile (MA 20) : zone d'attractivité des prix (mean reversion)
      au sein de la tendance — 'en dehors des phases de flux, elle n'est que
      du bruit ; en tendance, elle devient redoutable, agissant comme point
      de gravité'
    - Zone de Demande (Support) : interaction entre le support du canal de
      contexte et le prix
    - Signal de Momentum (optionnel) : filtre de qualité pour moduler
      l'exposition, non strictement requis pour valider le setup

    Règles de positionnement (Extreme Channel) :
    - Stop Loss : placé sous l'Extreme Channel (le contexte de l'UT
      supérieure)
    - Validation : atteinte du contexte vendeur opposé (résistance)
    - Gestion du stop après validation : remonté sous le dernier creux
      structurel (bas de clôture ou mèche)"

CE QUE LA SOURCE NE DIT PAS (ambigu, sous-spécifié) — HYPOTHÈSES EXPLICITES
-----------------------------------------------------------------------------
La source décrit le principe et les composants, mais AUCUNE formule
numérique précise pour "interaction entre le support ... et le prix" ni pour
"MA20 comme point de gravité" (à quelle distance/quel motif de bougie
signale le "rebond" ?). Ce module documente chaque choix comme hypothèse
explicite, pas comme une déduction silencieuse :

H1. **Rebond MA20** : on modélise "point de gravité" comme un rebond
    intrabar — la MÈCHE basse touche/traverse la MA20 (`low <= ma20`) MAIS
    la CLÔTURE reste au-dessus (`close > ma20`), i.e. le marché a testé la
    zone d'attractivité et l'a rejetée à la clôture (cohérent avec la
    convention déjà en place dans ce projet : les clôtures, pas les mèches,
    valident un franchissement — cf. `position_engine.py`). PAS de fenêtre
    de tolérance en % : un contact direct de la mèche est exigé, faute
    d'un chiffre donné par la source.
H2. **Interaction avec le Support (Zone de Demande)** : la source ne
    précise pas quel "support" — on réutilise `ctx_support` (convention
    déjà en place dans `backtest_phase2_v7.py::prepare`, EMA_SLOW - 2*ATR,
    documentée dans ce projet comme approximation de l'"Extreme Channel").
    "Interaction" = le prix n'a PAS invalidé la zone de demande
    (`close > ctx_support`) ET se trouve PROCHE du support par rapport à sa
    PROPRE histoire récente.

    CORRECTION FAITE APRÈS VÉRIFICATION EMPIRIQUE (pas une hypothèse
    silencieuse) : une première version de ce module définissait "proche"
    comme une fraction FIXE de la largeur du canal (distance <= 0.5 x 2*ATR
    au-dessus de `ctx_support`). Mesuré sur BTC/ETH/BNB/SOL H4 réels avant
    d'aller plus loin (discipline "mode ingénieur senior", `PLAN.md`) :
    cette définition ne se déclenche JAMAIS (0 occurrence sur ~14 000
    bougies x 4 actifs) — en régime TENDANCE (tel que classé par
    `regime_classifier`, qui exige `recent_above_frac >= 0.7`, donc le prix
    structurellement LOIN au-dessus du support), la distance médiane
    observée au support est d'environ 6 largeurs de canal, avec un MINIMUM
    de ~0.42 sur toute la période — la borne 0.5 était donc, par
    construction du classificateur de régime déjà en production
    (lui-même documenté comme approximation EMA+/-ATR imparfaite du vrai
    canal PRO Framework, cf. `PLAN.md`), quasiment inatteignable. Plutôt
    que de forcer un chiffre absolu qui ne convient pas à cette
    approximation de canal, on reprend la MÊME solution déjà adoptée par
    `regime_classifier.py` pour un problème identique (seuils absolus du
    manuel incompatibles avec l'échelle de notre canal) : un seuil
    PERCENTILE ADAPTATIF, calculé sur une fenêtre glissante CAUSALE (pas de
    lookahead, `shift(1)` avant le `rolling`) — "proche du support" =
    distance actuelle au support parmi les `SUPPORT_PROXIMITY_PCTL` (20%)
    PLUS FAIBLES observées sur les `PCTL_WINDOW` (250) dernières bougies.
    Revérifié empiriquement : produit désormais un signal rare mais réel
    (14/3/17/14 occurrences sur BTC/ETH/BNB/SOL H4 sur l'historique
    complet) — cohérent avec la description de la source ("Cluster
    Technique" présenté comme un pattern plus spécifique/plus rare que le
    "Trade du Jour" générique).
    C'est cette conjonction (rebond MA20 ET support relativement proche)
    qui constitue le "CLUSTER" (confluence de deux techniques au même
    endroit), pas seulement l'une ou l'autre isolément — cohérent avec le
    nom du pattern.
H3. **"Flux tendanciel établi (post-breakout)"** : traduit par
    `regime == "TENDANCE"` du classificateur déjà en production
    (`regime_classifier.add_regime`), qui distingue explicitement TENDANCE
    de RANGE_TENDANCIEL/RANGE_NEUTRE/EXCES — c'est la seule notion de
    "tendance établie" qui existe déjà dans ce projet, pas une nouvelle
    détection ad hoc.
H4. **Signal de Momentum (optionnel)** : la source dit explicitement
    "non strictement requis" — implémenté comme un filtre OPTIONNEL
    (`use_momentum_filter=False` par défaut), réutilisant le momentum TSI
    déjà calculé par `proxy_v2.compute_tsi` (`tsi > tsi_signal`) plutôt que
    d'inventer un second indicateur de momentum redondant.
H5. **"Gestion du stop après validation : remonté sous le dernier creux
    structurel"** — PAS implémenté dans ce module (qui ne fait QUE la
    détection du signal d'entrée, pas la gestion de position). Documenté
    ici comme un ÉCART CONNU avec la source : `code/diversification.py`
    (le moteur qui consomme ce signal) réutilise le mécanisme de gestion
    déjà en production (`position_engine.process_tranche` : stop remonté au
    BREAKEVEN à la Confirmation, pas "sous le dernier creux structurel") —
    par souci de cohérence avec le reste du projet et pour éviter un second
    moteur de gestion de position dupliqué, PAS parce que la règle de la
    source aurait été jugée incorrecte. Voir le commentaire correspondant
    dans `diversification.py` pour la justification complète du choix de
    scope.

Ce module ne fait QUE PRODUIRE LE SIGNAL D'ENTRÉE causal (booléen par
bougie) — comme `proxy_v2.add_proxy_v2_score` et `fibonacci.
add_fibonacci_columns` — il ne gère aucune position (cf. H5 ci-dessus).
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from proxy_v2 import compute_tsi

MA20_LEN = 20
# Cf. H2 (docstring module) : seuil PERCENTILE ADAPTATIF, pas une fraction fixe
# de la largeur du canal -- même solution que `regime_classifier.py` pour le
# même problème (canal EMA+/-ATR d'échelle incompatible avec un seuil absolu).
PCTL_WINDOW = 250              # bougies, fenêtre glissante causale (identique à regime_classifier.PCTL_WINDOW)
SUPPORT_PROXIMITY_PCTL = 0.20  # "proche du support" = parmi les 20% de distances les plus faibles récentes

# Valeurs par défaut réutilisées UNIQUEMENT si l'appelant ne fournit pas déjà
# ces colonnes (usage standalone/tests) — cohérentes avec
# `backtest_phase2_v7.py::prepare` pour ne pas introduire une 2e convention.
_DEFAULT_EMA_SLOW = 55
_DEFAULT_ATR_LEN = 14


def _default_atr(df: pd.DataFrame, length: int) -> pd.Series:
    """ATR causal standard (Wilder), identique en esprit à
    `backtest_phase2.py::atr` — dupliqué ici en 4 lignes plutôt qu'importé
    pour garder ce module utilisable sans dépendre du chemin de données de
    `backtest_phase2.py` (qui lit un DATA_DIR fixe au chargement)."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


def _default_regime(df: pd.DataFrame, ema_slow: pd.Series, atr_v: pd.Series) -> np.ndarray:
    """Calcule un régime standalone (mêmes conventions que
    `backtest_phase2_v7.py::prepare`) SEULEMENT si l'appelant n'a pas déjà
    fourni de colonne 'regime' — cf. docstring module, H3."""
    from regime_classifier import add_regime
    width_pct = (2 * 2 * atr_v) / ema_slow * 100
    return add_regime(df, ema_slow, width_pct)["regime"].values


def compute_ma20_rebound(df: pd.DataFrame, ma_len: int = MA20_LEN) -> tuple:
    """H1 : rebond MA20. Retourne (ma20, rebound_bool). Causal — `rolling`
    ne regarde que le passé (fenêtre [t-ma_len+1, t]), aucune barre future."""
    ma20 = df["close"].rolling(ma_len).mean()
    rebound = (df["low"].values <= ma20.values) & (df["close"].values > ma20.values)
    return ma20.values, rebound


def compute_support_confluence(close: np.ndarray, ctx_support: np.ndarray, atr_v: np.ndarray,
                                pctl_window: int = PCTL_WINDOW,
                                proximity_pctl: float = SUPPORT_PROXIMITY_PCTL) -> np.ndarray:
    """H2 (révisée après vérification empirique, cf. docstring module) :
    interaction prix/support = le prix n'a pas invalidé le support
    (`close > ctx_support`) ET la distance actuelle au support est parmi
    les plus faibles observées récemment (percentile adaptatif, CAUSAL :
    `shift(1)` avant le `rolling`, aucune bougie courante ni future
    n'entre dans le calcul du seuil lui-même). `ctx_support`/`atr_v` sont
    supposés déjà causaux (cas de `backtest_phase2_v7.py::prepare`)."""
    width = 2 * atr_v
    valid = ~np.isnan(ctx_support) & ~np.isnan(atr_v) & (width > 0)
    dist_frac = pd.Series(np.where(valid, (close - ctx_support) / np.where(width > 0, width, np.nan), np.nan))
    threshold = dist_frac.shift(1).rolling(pctl_window).quantile(proximity_pctl)
    not_invalidated = close > ctx_support
    close_enough = (dist_frac <= threshold).values
    return valid & not_invalidated & close_enough & ~threshold.isna().values


def add_cluster_signal(df: pd.DataFrame, ma_len: int = MA20_LEN,
                        pctl_window: int = PCTL_WINDOW,
                        proximity_pctl: float = SUPPORT_PROXIMITY_PCTL,
                        use_momentum_filter: bool = False) -> pd.DataFrame:
    """Ajoute 'ma20', 'ma20_rebound', 'support_confluence', 'trend_established'
    et 'cluster_signal' (ET logique des trois premières, + momentum optionnel
    si `use_momentum_filter=True`) à `df`.

    Réutilise 'regime'/'ctx_support'/'atr' déjà présents dans `df` s'ils
    existent (cas d'usage réel : `df` préparé par
    `backtest_phase2_v7.py::prepare`, pour ne jamais recalculer deux
    conventions différentes de la même grandeur) ; les calcule lui-même avec
    les mêmes conventions sinon (cas d'usage standalone/tests unitaires,
    cf. `test_cluster_technique.py`). Entièrement causal (H1/H2/H3 ci-dessus
    ne consomment que des grandeurs déjà causales).

    NB : si 'regime' n'est pas déjà présent, `regime_classifier.add_regime`
    (réutilisé tel quel) exige une colonne 'date' dans `df` (pente du canal
    mesurée en durée réelle, pas en nombre de bougies) — fournir 'date' dans
    tout appel standalone, comme le fait déjà `backtest_phase2_v7.py::prepare`."""
    df = df.copy().reset_index(drop=True)

    if "atr" in df.columns:
        atr_v = df["atr"].values
    else:
        atr_v = _default_atr(df, _DEFAULT_ATR_LEN).values
        df["atr"] = atr_v

    if "ctx_support" in df.columns:
        ctx_support = df["ctx_support"].values
    else:
        ema_slow = df["close"].ewm(span=_DEFAULT_EMA_SLOW, adjust=False).mean()
        ctx_support = (ema_slow - 2 * pd.Series(atr_v)).values
        df["ctx_support"] = ctx_support

    if "regime" in df.columns:
        regime = df["regime"].values
    else:
        ema_slow_for_regime = df["close"].ewm(span=_DEFAULT_EMA_SLOW, adjust=False).mean()
        regime = _default_regime(df, ema_slow_for_regime, pd.Series(atr_v))
        df["regime"] = regime

    ma20, ma20_rebound = compute_ma20_rebound(df, ma_len=ma_len)
    support_confluence = compute_support_confluence(df["close"].values, ctx_support, atr_v, pctl_window, proximity_pctl)
    trend_established = (regime == "TENDANCE")

    cluster_signal = trend_established & ma20_rebound & support_confluence

    if use_momentum_filter:
        tsi, tsi_signal = compute_tsi(df["close"])
        momentum_favorable = (tsi > tsi_signal).values
        cluster_signal = cluster_signal & momentum_favorable
        df["momentum_favorable"] = momentum_favorable

    df["ma20"] = ma20
    df["ma20_rebound"] = ma20_rebound
    df["support_confluence"] = support_confluence
    df["trend_established"] = trend_established
    df["cluster_signal"] = cluster_signal
    return df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from backtest_phase2 import load_h1, resample

    df = resample(load_h1("BTCUSDT"), "4h")
    scored = add_cluster_signal(df)
    print(scored[["date", "close", "ma20", "ma20_rebound", "support_confluence",
                  "trend_established", "cluster_signal"]].tail(40).to_string(index=False))
    print("\nFréquence du signal Cluster Technique (BTC H4) :", scored["cluster_signal"].mean().round(4))
