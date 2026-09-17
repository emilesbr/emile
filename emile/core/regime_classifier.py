"""
Classificateur de régime de marché — élément manquant identifié : aucun de
nos moteurs (v4, v5) ne distinguait Range vs Tendance vs Bulle avant
d'entrer, alors que c'est la règle de base n°1 du manuel PDF officiel
("TOUJOURS TRADER DANS UN CONTEXTE", RULES_EXTRACTION.md section 1).

4 régimes (fréquences approximatives du manuel : Range neutre ~50%, Range
tendanciel ~25%, Tendance ~20%, Bulle/Excès ~5%) :
  - RANGE_NEUTRE   : canal de contexte stable, pas de biais directionnel net
  - RANGE_TENDANCIEL : range, mais le contexte de l'UT supérieure est
    directionnellement aligné (approximé ici par la pente du canal lui-même,
    faute d'une vraie UT supérieure dans ce script autonome)
  - TENDANCE       : pente du canal marquée + prix majoritairement d'un côté
  - EXCES          : canal trop large (boîtes disjointes) OU trop étroit
    (squeeze) -> "NE PAS TRADER" selon le manuel

Règle du manuel explicitement respectée : "en cas de doute, toujours RANGE".

4e branche du guide officiel, "CHAOS" (61e round) : cf. le bloc dédié en bas
de fichier (`add_chaos_extrapolated`) -- EXTRAPOLATION EXPLICITE, modélisée
ici comme un sous-ensemble de RANGE_NEUTRE, jamais produite par `add_regime`
lui-même (inchangé) -- une 5e valeur de sortie possible pour QUI APPELLE
`add_chaos_extrapolated` en plus, pas un changement de `add_regime`.

AJOUT — détecteur "canal TRÈS LARGE" (`compute_wide_channel` en bas de
fichier), support de la règle de volatilité "Stop Loss = taille du canal"
de `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` §5. Placé ICI et pas
ailleurs pour une raison de principe déjà établie dans ce projet ("même
terme = même définition partout, pas une nouvelle par module") : ce fichier
est DÉJÀ celui qui possède le vocabulaire "canal trop large" (EXCES) et la
machinerie de percentile glissant causal qui le mesure. Le MÉCANISME de
sizing associé, lui, vit dans `position_engine.py` (qui possède le sizing) —
cf. le bloc "STOP LOSS = TAILLE DU CANAL" en tête de ce fichier-là pour la
citation exacte, les 4 hypothèses (H-Canal-Large-1..4) et la justification
complète du seuil retenu.
"""
import pandas as pd
import numpy as np

SLOPE_WINDOW = "20D"      # fenêtre réelle pour la pente du canal (calibrée en durée, pas en bougies)
RECENT_WINDOW = 10         # bougies pour la position récente du prix vs médiane
TREND_SLOPE_THRESHOLD = 1.5   # % , seuil de pente pour "tendance" (cf. manuel: slope_pct > 1.5)
# CALIBRATION : les seuils absolus du manuel (1%/12%) sont calibrés pour le
# vrai canal PRO Framework, pas pour notre approximation EMA+/-2xATR (dont la
# largeur médiane sur crypto est ~17%, bien au-dessus de 12%). On utilise donc
# des seuils PERCENTILES ADAPTATIFS (fenêtre glissante causale, pas de
# lookahead) plutôt que les valeurs absolues du manuel, pour cibler
# approximativement les mêmes fréquences relatives (squeeze/excès rares).
PCTL_WINDOW = 250          # bougies, fenêtre glissante pour les percentiles adaptatifs
SQUEEZE_PCTL = 0.05
EXCESS_PCTL = 0.95
# Seuil "canal TRÈS LARGE" (hypothèse H-Canal-Large-3, cf. position_engine.py) —
# strictement EN DESSOUS de EXCESS_PCTL : "très large" est un état de
# DIMENSIONNEMENT (le corpus dit "ajusté selon volatilité"), pas d'abstention
# ("Bulle/Excès -> NE PAS TRADER"). Les deux doivent rester distincts, sinon la
# règle de volatilité serait vacueuse dans tout moteur qui refuse déjà de
# trader en régime EXCES.
WIDE_PCTL = 0.80

def add_regime(df: pd.DataFrame, ctx_median: pd.Series, ctx_width_pct: pd.Series) -> pd.DataFrame:
    """Ajoute la colonne 'regime' (RANGE_NEUTRE/RANGE_TENDANCIEL/TENDANCE/EXCES).
    ctx_median : médiane du canal de contexte (ex. EMA lente)
    ctx_width_pct : largeur du canal en % de la médiane"""
    df = df.copy()
    ts_median = ctx_median.copy()
    ts_median.index = pd.to_datetime(df["date"])
    slope_ref = ts_median.shift(freq=pd.Timedelta(SLOPE_WINDOW)).reindex(ts_median.index, method="nearest")
    # Pente réelle : comparaison directe avec la valeur d'il y a ~20 jours
    slope_pct = ((ts_median.values - slope_ref.values) / slope_ref.values * 100)

    close = df["close"].values
    above_median = close > ctx_median.values
    recent_above_frac = pd.Series(above_median).rolling(RECENT_WINDOW).mean().values

    # Seuils adaptatifs (percentiles glissants CAUSAUX, calculés sur le passé
    # uniquement -> shift(1) pour ne jamais inclure la bougie courante)
    width_series = ctx_width_pct.reset_index(drop=True)
    squeeze_thresh = width_series.shift(1).rolling(PCTL_WINDOW).quantile(SQUEEZE_PCTL).values
    excess_thresh = width_series.shift(1).rolling(PCTL_WINDOW).quantile(EXCESS_PCTL).values

    regimes = []
    for i in range(len(df)):
        w = ctx_width_pct.values[i]
        if (np.isnan(w) or np.isnan(slope_pct[i]) or np.isnan(recent_above_frac[i])
                or np.isnan(squeeze_thresh[i]) or np.isnan(excess_thresh[i])):
            regimes.append("RANGE_NEUTRE")  # "en cas de doute, range" (manuel)
            continue
        if w < squeeze_thresh[i] or w > excess_thresh[i]:
            regimes.append("EXCES")
            continue
        if slope_pct[i] > TREND_SLOPE_THRESHOLD and recent_above_frac[i] >= 0.7:
            regimes.append("TENDANCE")
        elif slope_pct[i] > TREND_SLOPE_THRESHOLD * 0.5 and recent_above_frac[i] >= 0.5:
            regimes.append("RANGE_TENDANCIEL")
        else:
            regimes.append("RANGE_NEUTRE")  # défaut = doute = range (règle explicite du manuel)
    df["regime"] = regimes
    return df

def compute_wide_channel(ctx_width_pct, pctl: float = WIDE_PCTL,
                          window: int = PCTL_WINDOW) -> np.ndarray:
    """"Canal TRÈS LARGE" — détecteur de la règle de volatilité de
    `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` §5 (citation exacte et
    hypothèses : bloc "STOP LOSS = TAILLE DU CANAL" en tête de
    `position_engine.py`). Retourne un array booléen aligné sur
    `ctx_width_pct`.

    Réutilise EXACTEMENT la machinerie déjà en place dans `add_regime`
    ci-dessus pour dire "canal trop large" — même série d'entrée
    (`ctx_width_pct`, la largeur du canal Extreme Channel en % de sa médiane,
    calculée une seule fois par `backtest_phase2_v7.py::prepare` puis
    transmise aux deux), même fenêtre (`PCTL_WINDOW`), même construction
    causale (`.shift(1)` avant le rolling : la bougie courante n'entre JAMAIS
    dans le calcul de son propre seuil), même comparaison stricte (`>`).
    Seul le percentile change (`WIDE_PCTL` au lieu de `EXCESS_PCTL`) — ce
    n'est donc pas une nouvelle définition du canal ni une nouvelle notion de
    "large", c'est la même graduée à un cran moins extrême.

    NaN (warmup : moins de `window` bougies d'historique, ou largeur non
    calculable) -> False, c'est-à-dire "pas très large" -> règle STANDARD
    ("Stop Loss = taille du canal"), jamais la règle de volatilité. Même
    esprit de défaut prudent que "en cas de doute, toujours RANGE" du manuel
    (ci-dessus) : en cas de doute, on ne modifie pas le dimensionnement."""
    w = pd.Series(np.asarray(ctx_width_pct, dtype=float)).reset_index(drop=True)
    thresh = w.shift(1).rolling(window).quantile(pctl)
    return (w > thresh).fillna(False).to_numpy(dtype=bool)

def compute_squeeze(ctx_width_pct, pctl: float = SQUEEZE_PCTL,
                     window: int = PCTL_WINDOW) -> np.ndarray:
    """"SQUEEZE" (canal TRÈS ÉTROIT) — miroir exact de `compute_wide_channel`
    ci-dessus, même machinerie, seule la direction de la comparaison change
    (`<` au lieu de `>`) puisqu'un squeeze est un canal trop ÉTROIT, pas trop
    large. Retourne un array booléen aligné sur `ctx_width_pct`.

    Ajouté pour le mécanisme "invalidation 3BR par squeeze sur l'UT+1"
    (`docs/GUIDE_STRATEGIE_PRO_INDICATORS.md` section 3.2, citation exacte :
    *"Si le range se forme juste après un SQUEEZE sur l'unité de temps
    supérieure, il faudra alors éviter de trader cette 3BR"*, `PLAN.md`
    "31e application") -- ce niveau ("l'UT propre est en squeeze") est déjà
    plié dans `add_regime` (régime `EXCES`, ligne `w < squeeze_thresh[i] or w
    > excess_thresh[i]`), mais `add_regime` ne permet pas de savoir SI un
    `EXCES` donné vient d'un squeeze ou d'un canal trop large -- exactement le
    même besoin de granularité que celui qui a motivé `compute_wide_channel`
    (une fonction dédiée, pas une nouvelle définition de canal).

    H-Squeeze-UT1-1 (hypothèse d'opérationnalisation, le corpus ne chiffre
    pas "juste après") : le squeeze D1 est lu de façon CONTEMPORAINE (même
    jointure causale que `regime_d1`, aucun délai supplémentaire inventé) --
    pas une fenêtre de recul explicite, le percentile glissant de 250 bougies
    fait déjà persister l'état "squeeze" sur plusieurs bougies consécutives
    de façon causale, ce qui capture "juste après" sans ajouter de paramètre.

    NaN (warmup) -> False ("pas squeeze"), même convention prudente que
    `compute_wide_channel`/`add_regime`."""
    w = pd.Series(np.asarray(ctx_width_pct, dtype=float)).reset_index(drop=True)
    thresh = w.shift(1).rolling(window).quantile(pctl)
    return (w < thresh).fillna(False).to_numpy(dtype=bool)

# NB (borne max des bornes) réutilisé tel quel par les fonctions de routage
# RANGE ci-dessous -- même chiffre que la citation du guide, "range avec
# plus de 4 bornes -> Neuneu" (`docs/GUIDE_STRATEGIE_PRO_INDICATORS.md`
# section 3.1), PAS le même chiffre que `MIN_BORDERS` (maturité minimale
# pour trader DU TOUT, 3, défini dans `backtest_phase2_v7.py` -- deux seuils
# distincts qui répondent à deux questions différentes du corpus).
NEUNEU_MAX_BORDERS = 4

def compute_range_precedes_by_trend(regime) -> tuple:
    """Routage RANGE "3ème borne" vs "Neuneu" (`docs/GUIDE_STRATEGIE_PRO_
    INDICATORS.md` section 3.1, citation exacte du guide officiel PRO
    Indicators, `PLAN.md` "32e application") :
    *"RANGE PRÉCÉDÉ D'UNE TENDANCE ? (moyenne hors des contextes = tendance)
    Si la réponse est OUI alors on applique la structure de '3EME BORNE'.
    Pour tous les autres cas (pas assez d'historique, range avec plus de 4
    bornes ou forex au delà de l'UT hebdo) nous appliquons la structure
    'NEUNEU'."*

    "Range précédé d'une tendance" est ici lu littéralement, sans rien
    inventer : le régime H4 natif (`regime_classifier.add_regime`) DÉJÀ en
    place classe explicitement un état "TENDANCE" (pente marquée + prix
    majoritairement d'un côté) distinct des 2 états RANGE -- c'est très
    exactement la définition que le guide donne lui-même entre parenthèses
    ("moyenne hors des contextes = tendance"). Pour chaque bougie en RANGE,
    on cherche le DERNIER régime NON-range qui précède le début du "run" de
    RANGE courant (`ffill` causal, aucune bougie future consultée) et on
    regarde s'il vaut "TENDANCE".

    Retourne `(precedes_by_trend, no_prior_regime)`, deux arrays booléens
    alignés sur `regime` :
      - `precedes_by_trend[i]` : True si le dernier régime non-RANGE avant
        le run de RANGE en cours (ou avant la bougie i elle-même, si i n'est
        pas en RANGE) était TENDANCE. False s'il était EXCES, ou si aucun
        régime non-RANGE n'a encore été observé (warmup -- cf.
        `no_prior_regime` ci-dessous, qui distingue ce 2e cas).
      - `no_prior_regime[i]` : True tant qu'AUCUNE bougie non-RANGE n'a
        encore été observée depuis le début de la série -- correspond à
        "pas assez d'historique" (une des 3 conditions littérales du guide
        pour router vers Neuneu, cf. `compute_use_neuneu` ci-dessous). Ce
        n'est PAS un warmup au sens habituel (ATR/EMA non calculables) --
        une série qui commence DÉJÀ en RANGE_NEUTRE reste `no_prior_regime`
        jusqu'à la première bougie TENDANCE ou EXCES, même après des
        milliers de bougies de warmup ATR/EMA passé."""
    regime_s = pd.Series(np.asarray(regime, dtype=object)).reset_index(drop=True)
    is_range = regime_s.isin(("RANGE_NEUTRE", "RANGE_TENDANCIEL"))
    non_range_regime = regime_s.where(~is_range)
    last_non_range = non_range_regime.ffill()
    precedes_by_trend = (last_non_range == "TENDANCE").to_numpy(dtype=bool)
    no_prior_regime = last_non_range.isna().to_numpy(dtype=bool)
    return precedes_by_trend, no_prior_regime

def compute_range_border_count(regime, is_swing_low_confirmed) -> np.ndarray:
    """Nombre de bornes (swings bas confirmés) DEPUIS LE DÉBUT du "run" de
    RANGE en cours -- remis à zéro à chaque nouvelle entrée en RANGE depuis
    un état non-range, PAS un compte glissant perpétuel.

    VÉRIFIÉ SUR DONNÉES RÉELLES avant de choisir cette définition (pas
    supposée) : `n_borders` (`backtest_phase2_v7.py::prepare`, déjà utilisé
    pour `MIN_BORDERS`) est un compte GLISSANT sur une fenêtre calendaire
    fixe (`CONTEXT_DURATION`) recalculé à CHAQUE bougie, jamais remis à
    zéro -- sa médiane sur BTC H4 réel est 9, et il vaut plus de 4 sur
    99,7% des bougies. Le réutiliser tel quel pour "range avec plus de 4
    bornes" (routage NEUNEU, cf. `compute_use_neuneu` ci-dessous) rendrait
    ce routage VRAI presque partout -- pas une lecture fidèle de la
    citation ("range avec plus de 4 bornes" désigne le nombre de bornes de
    CE range précis, qui grandit depuis 0 à chaque nouveau range, pas un
    compte perpétuel sur une fenêtre glissante). D'où cette fonction
    dédiée plutôt qu'une réutilisation de `n_borders` -- même swing
    (`compute_swing_low_confirmed`, MÊME primitive causale que `n_borders`
    et que la variante "3ème borne squeezée"), mais agrégé PAR ÉPISODE de
    range, pas sur une fenêtre glissante perpétuelle.

    `is_swing_low_confirmed` : booléen déjà calculé par
    `emile.core.proxy_v2.compute_swing_low_confirmed(low, order=SWING_ORDER)`
    -- passé en paramètre plutôt que recalculé ici (même donnée que
    `n_borders`/le mécanisme "3ème borne squeezée", jamais une 2e version)."""
    regime_s = pd.Series(np.asarray(regime, dtype=object)).reset_index(drop=True)
    is_range = regime_s.isin(("RANGE_NEUTRE", "RANGE_TENDANCIEL")).to_numpy()
    swing = np.asarray(is_swing_low_confirmed, dtype=bool)
    # Identifiant de "run" de RANGE contigu : incrémenté à chaque transition
    # non-range -> range (donc constant sur un run de range donné, différent
    # d'un run à l'autre) -- cumsum causal standard, aucune bougie future lue.
    entering_range = is_range & ~np.concatenate(([False], is_range[:-1]))
    run_id = np.cumsum(entering_range)
    # Compte cumulatif de bornes confirmées PAR run (groupby causal) : le
    # cumsum global des bornes, moins sa valeur au DÉBUT du run courant --
    # donc remis à 0 à chaque nouveau run, jamais un compte perpétuel.
    cum_borders = np.cumsum(swing & is_range)
    run_start_cum = np.zeros(len(regime_s), dtype=float)
    # valeur du cumul juste AVANT le début de chaque run, reportée sur tout le run
    start_idx = np.where(entering_range)[0]
    if len(start_idx) > 0:
        prior_cum = np.concatenate(([0], cum_borders))[start_idx]  # cum juste avant chaque début de run
        run_start_cum_per_run = dict(zip(run_id[start_idx], prior_cum))
        run_start_cum = np.array([run_start_cum_per_run.get(r, 0) for r in run_id], dtype=float)
    border_count = cum_borders - run_start_cum
    border_count[~is_range] = 0.0   # hors RANGE, la question ne se pose pas -- valeur neutre
    return border_count

def compute_use_neuneu(regime, range_border_count, max_borders: int = NEUNEU_MAX_BORDERS) -> np.ndarray:
    """Combine les 2 conditions littérales du guide qui sont dans le
    périmètre crypto de ce projet (la 3e, "forex au delà de l'UT hebdo",
    est hors-scope -- ce projet ne trade que BTC/ETH/BNB/SOL) avec le repli
    "pas assez d'historique" pour produire la décision de routage finale :
    `True` -> appliquer la structure NEUNEU (`range_neuneu.py`) au lieu de
    la structure 3ème borne (déjà celle codée sans condition dans
    `faithful.py`/`position_engine.py`, §3/§3bis de `RULES_EXTRACTION.md`).

    `range_border_count` : PAR ÉPISODE de range (cf. `compute_range_border_
    count` ci-dessus), PAS le `n_borders` glissant perpétuel déjà utilisé
    pour `MIN_BORDERS` -- vérifié sur données réelles que réutiliser ce
    dernier rendrait ce routage vrai presque partout (cf. docstring de
    `compute_range_border_count`)."""
    precedes_by_trend, no_prior_regime = compute_range_precedes_by_trend(regime)
    borders_arr = np.asarray(range_border_count, dtype=float)
    too_many_borders = borders_arr > max_borders   # NaN -> False (comparaison numpy), jamais "trop de bornes" par défaut
    return (~precedes_by_trend) | too_many_borders | no_prior_regime

# ==============================================================================
# CHAOS -- 4e état, EXTRAPOLATION EXPLICITE (61e round, `docs/PLAN.md`)
# ==============================================================================
# Décision DIRECTE de l'utilisateur (question posée en clair : "comment traiter
# Chaos, sachant qu'il est indiscernable de RANGE_NEUTRE sans inventer un
# seuil ?" -- réponse choisie : "inventer un seuil explicitement marqué comme
# extrapolation"). Ceci RENVERSE la conclusion du 44e round ("Chaos reste
# catégorie A, pas implémenté") -- pas parce que le corpus aurait changé
# (il n'a pas changé), mais parce que l'utilisateur a explicitement choisi
# d'accepter une extrapolation non corroborée, exactement le même statut que
# `use_sl_gain`/`use_mtf_cascade` avant lui.
#
# Écran source (`docs/GUIDE_STRATEGIE_PRO_INDICATORS.md` section 1,
# `Chaos/Chaos.png`), 3 critères CUMULATIFS (convention "cases numérotées =
# critères cumulatifs" déjà observée sur d'autres écrans du même guide) :
# **Contextes irréguliers**, **Moyenne plate**, **Momentum bruyant** ->
# action "PARTEZ" (changer d'actif, aucune règle de trading proposée).
#
# 1. "Moyenne plate" -- AUCUNE invention : c'est DÉJÀ, dans `add_regime`
#    ci-dessus, la condition par défaut de RANGE_NEUTRE (pente en dessous de
#    `TREND_SLOPE_THRESHOLD * 0.5`). Chaos est donc modélisé ici comme un
#    SOUS-ENSEMBLE de RANGE_NEUTRE (H-Chaos-Scope-1 -- hypothèse de
#    conception assumée, pas une règle du corpus) : seuls les bars déjà
#    classés RANGE_NEUTRE sont éligibles à devenir CHAOS, TENDANCE/
#    RANGE_TENDANCIEL/EXCES ne sont jamais réécrits.
# 2. "Momentum bruyant" -- AUCUNE primitive de bruit/oscillation/whipsaw
#    n'existe ailleurs dans ce projet (grep exhaustif confirmé au 44e round).
#    H-Chaos-Momentum-1 (EXTRAPOLATION) : taux de retournement de signe des
#    variations de clôture sur une fenêtre glissante de `CHAOS_MOMENTUM_
#    WINDOW` bougies (fenêtre INVENTÉE), comparé à un seuil PERCENTILE
#    ADAPTATIF (même machinerie causale que squeeze/excès/canal large
#    ci-dessus -- `CHAOS_MOMENTUM_NOISE_PCTL` INVENTÉ).
# 3. "Contextes irréguliers" -- H-Chaos-Context-1 (EXTRAPOLATION) : réutilise
#    `n_borders` (le compte glissant DÉJÀ calculé par l'appelant, ex.
#    `backtest_phase2_v7.py::prepare` -- MÊME primitive que celle qui sert
#    déjà `MIN_BORDERS`, jamais recalculée), mais avec un NOUVEAU seuil
#    percentile INVENTÉ (`CHAOS_IRREGULAR_BORDERS_PCTL`), DISTINCT de
#    `NEUNEU_MAX_BORDERS=4` (calibré pour une question totalement
#    différente -- routage 3ème borne/Neuneu, pas irrégularité de contexte --
#    cf. 44e round, qui avait explicitement rejeté cette confusion).
#
# `add_chaos_extrapolated` NE MODIFIE PAS `add_regime` (inchangé, réutilisé
# tel quel) -- prend son résultat déjà calculé et le SURCHARGE en "CHAOS"
# uniquement là où les 3 critères sont réunis. Strictement additif : tout
# appelant qui n'invoque pas cette fonction voit un comportement RIGOUREUSEMENT
# inchangé.

CHAOS_MOMENTUM_WINDOW = 20            # H-Chaos-Momentum-1 -- fenêtre INVENTÉE
CHAOS_MOMENTUM_NOISE_PCTL = 0.90       # H-Chaos-Momentum-1 -- percentile INVENTÉ
CHAOS_IRREGULAR_BORDERS_PCTL = 0.90    # H-Chaos-Context-1 -- percentile INVENTÉ

def compute_momentum_noise_rate(close, window: int = CHAOS_MOMENTUM_WINDOW) -> np.ndarray:
    """Taux de retournement de signe des variations de clôture (close[i] -
    close[i-1]) sur une fenêtre glissante de `window` bougies -- proxy de
    "momentum bruyant" (H-Chaos-Momentum-1, EXTRAPOLATION, cf. bloc CHAOS
    ci-dessus). Une variation nulle (`sign == 0`) ne compte ni comme
    retournement ni comme continuation -- ignorée du dénominateur implicite
    en ne matchant ni l'une ni l'autre condition. NaN pour les `window`
    premières bougies (rolling), converti en 0.0 par l'appelant si besoin
    (`compute_chaos_momentum_noisy` le traite comme "non bruyant" via le
    comportement standard NaN->False de la comparaison percentile)."""
    close_arr = np.asarray(close, dtype=float)
    returns = np.diff(close_arr, prepend=close_arr[0])
    sign = np.sign(returns)
    reversal = np.zeros(len(sign), dtype=float)
    valid = (sign[1:] != 0) & (sign[:-1] != 0)
    reversal[1:] = np.where(valid & (sign[1:] != sign[:-1]), 1.0, 0.0)
    return pd.Series(reversal).rolling(window).mean().to_numpy()

def compute_chaos_momentum_noisy(close, window: int = CHAOS_MOMENTUM_WINDOW,
                                  pctl: float = CHAOS_MOMENTUM_NOISE_PCTL,
                                  pctl_window: int = PCTL_WINDOW) -> np.ndarray:
    """"Momentum bruyant" (H-Chaos-Momentum-1, EXTRAPOLATION) : `True` quand
    le taux de retournement de signe (`compute_momentum_noise_rate`) dépasse
    son propre percentile adaptatif glissant -- MÊME construction causale
    (`.shift(1)` avant le rolling) que `compute_wide_channel`/`compute_
    squeeze` ci-dessus. NaN (warmup) -> False, même convention prudente que
    le reste de ce fichier."""
    rate = pd.Series(compute_momentum_noise_rate(close, window))
    thresh = rate.shift(1).rolling(pctl_window).quantile(pctl)
    return (rate > thresh).fillna(False).to_numpy(dtype=bool)

def compute_chaos_irregular_context(n_borders, pctl: float = CHAOS_IRREGULAR_BORDERS_PCTL,
                                     pctl_window: int = PCTL_WINDOW) -> np.ndarray:
    """"Contextes irréguliers" (H-Chaos-Context-1, EXTRAPOLATION) : `True`
    quand `n_borders` (le compte glissant DÉJÀ calculé par l'appelant, MÊME
    primitive que `MIN_BORDERS`, jamais recalculée) dépasse son propre
    percentile adaptatif glissant -- seuil DISTINCT de `NEUNEU_MAX_BORDERS`
    (question différente, cf. bloc CHAOS ci-dessus). NaN (warmup) -> False."""
    n = pd.Series(np.asarray(n_borders, dtype=float))
    thresh = n.shift(1).rolling(pctl_window).quantile(pctl)
    return (n > thresh).fillna(False).to_numpy(dtype=bool)

def add_chaos_extrapolated(df: pd.DataFrame, regime, n_borders,
                            momentum_window: int = CHAOS_MOMENTUM_WINDOW,
                            momentum_pctl: float = CHAOS_MOMENTUM_NOISE_PCTL,
                            borders_pctl: float = CHAOS_IRREGULAR_BORDERS_PCTL,
                            pctl_window: int = PCTL_WINDOW) -> np.ndarray:
    """4e état "CHAOS" -- EXTRAPOLATION EXPLICITE (cf. bloc CHAOS en tête de
    cette section pour la citation exacte et les 3 hypothèses H-Chaos-*).

    Ne modifie PAS `add_regime` : prend son résultat déjà calculé (`regime`,
    un array/Series RANGE_NEUTRE/RANGE_TENDANCIEL/TENDANCE/EXCES) et retourne
    une COPIE où "CHAOS" remplace "RANGE_NEUTRE" partout où les 3 critères
    cumulatifs sont réunis (`compute_chaos_momentum_noisy` ET `compute_chaos_
    irregular_context`, "moyenne plate" étant déjà la définition de
    RANGE_NEUTRE -- H-Chaos-Scope-1). Jamais TENDANCE/RANGE_TENDANCIEL/EXCES,
    quels que soient les 2 autres critères."""
    regime_arr = np.asarray(regime, dtype=object).copy()
    is_range_neutre = regime_arr == "RANGE_NEUTRE"
    noisy = compute_chaos_momentum_noisy(df["close"].to_numpy(), momentum_window, momentum_pctl, pctl_window)
    irregular = compute_chaos_irregular_context(n_borders, borders_pctl, pctl_window)
    chaos_mask = is_range_neutre & noisy & irregular
    regime_arr[chaos_mask] = "CHAOS"
    return regime_arr

if __name__ == "__main__":
    import sys

    from emile.backtests.backtest_phase2 import load_h1, resample, atr, EMA_SLOW

    df = resample(load_h1("BTCUSDT"), "1D")
    ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    atr_v = atr(df, 14)
    width_pct = (2 * 2 * atr_v) / ema_slow * 100  # canal EMA +/- 2*ATR
    scored = add_regime(df, ema_slow, width_pct)
    print(scored["regime"].value_counts())
    print("\n% du temps par régime :")
    print((scored["regime"].value_counts(normalize=True) * 100).round(1))
