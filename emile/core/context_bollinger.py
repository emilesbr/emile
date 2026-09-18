"""
Canal de "contexte" candidat -- bande de Bollinger calculée sur l'UT
IMMÉDIATEMENT SUPÉRIEURE à celle du moteur d'exécution, jointe de façon
causale (aucune bougie future consultée).

ORIGINE -- hypothèse formulée par l'utilisateur en conversation (pas une
citation du corpus, à distinguer des autres hypothèses de ce projet) :
*"le contexte est dérivé des unités temporelles supérieures à la timeframe
étudiée. C'est déjà un peu comme les bandes de Bollinger et non les moyennes
mobiles... c'est pour ça que les boîtes sont plates, car c'est le prix de
l'UT au-dessus qui est mesuré, et nous sommes dans l'UT inférieur."*
Testée rigoureusement (période=20, k=2 -- PRÉ-ENREGISTRÉS, PAS une recherche
libre sur l'espace des paramètres, cf. l'auto-correction méthodologique du
54e round) contre 3 points mesurés par pixels/légendes réelles de
l'indicateur PRO Framework de Philippe Roux (`docs/CONTEXT_CHANNEL_REVERSE_
ENGINEERING.md`, rounds 51/52/54/56/57) : 2 corroborations fortes (round 54,
ETH 4h -> contexte D1, écart -0,34%/+0,31% simultanément sur les 2 bornes ;
round 52, BTC 15 min -> contexte H1, écart -0,07%), 1 désaccord non résolu
(round 51, ETH 1D -> contexte Semaine, potentiellement une mesure pixel
contaminée par une 2e construction grise superposée, cf. section 11 du même
document). Nommée `H-Context-BB-UT+1`.

CE MODULE construit ce candidat de façon réutilisable et l'injecte dans
`regime_classifier.add_regime` -- AUCUNE modification de ce fichier, qui
accepte déjà `ctx_median`/`ctx_width_pct` en paramètres génériques -- à la
place du proxy EMA+/-ATR historique (`backtest_phase2_v7.py::prepare`),
pour permettre de COMPARER les deux classifications de régime et mesurer si
la stratégie Neuneu (`neuneu_repli.py`/`neuneu_borne.py`, gouvernée par ce
régime via `unified_protocol.py::use_neuneu`) devient plus rentable avec ce
candidat -- demande explicite de l'utilisateur, "en tant qu'ingénieur
senior... vérifie notamment sur sa capacité à rendre la stratégie de
trading de range neuneu rentable".

PORTÉE -- ce que ce module NE fait PAS : produit les 3 régimes déjà couverts
par `add_regime` (RANGE_NEUTRE/RANGE_TENDANCIEL/TENDANCE/EXCES), PAS un 4e
état "KO"/Chaos -- resté délibérément non défini depuis le 44e round
(`docs/PLAN.md`), le corpus ne le chiffre nulle part et ce round n'invente
rien de plus qu'alors.

STATUT -- strictement additif : `H-Context-BB-UT+1` reste À UN SEUL point
défavorable sur 3 encore inexpliqué (cf. ci-dessus) -- ce module et son
câblage dans `unified_protocol.py` sont donc opt-in (`use_bb_context_for_
neuneu=False` par défaut), jamais appelés par un chemin existant, pour ne
changer AUCUN résultat déjà publié.
"""
import pandas as pd
import numpy as np

from emile.core.regime_classifier import add_regime

BB_PERIOD = 20      # "20" du triplet confirmé "(1, 20, 2)" (docs/CONTEXT_CHANNEL_REVERSE_ENGINEERING.md)
BB_K = 2.0          # "2" du même triplet
CLOSURE_DELAY = pd.Timedelta(days=1)   # même convention que backtest_phase2_v7.py::attach_higher_context


def compute_bollinger(df_higher: pd.DataFrame, period: int = BB_PERIOD, k: float = BB_K) -> pd.DataFrame:
    """Bollinger(period, k) du close, calculé NATIVEMENT sur l'UT supérieure
    (`df_higher`, ex. D1 pour un moteur H4) -- pas de jointure ici, cf.
    `attach_context_bb` ci-dessous pour la jointure causale vers l'UT
    d'exécution. Retourne `df_higher` + 3 colonnes ("bb_median"/"bb_width_pct"
    ajoutées ; "bb_median" = SMA(period), pas la borne haute/basse -- même
    convention que `ctx_median`/`ctx_width_pct` déjà utilisés par
    `regime_classifier.add_regime`)."""
    df = df_higher.copy()
    sma = df["close"].rolling(period).mean()
    std = df["close"].rolling(period).std()
    df["bb_median"] = sma
    df["bb_width_pct"] = (2 * k * std) / sma * 100
    return df


def attach_context_bb(df_low: pd.DataFrame, df_higher_bb: pd.DataFrame,
                       closure_delay: pd.Timedelta = CLOSURE_DELAY) -> dict:
    """Jointure causale (merge_asof, direction='backward') de bb_median/
    bb_width_pct depuis l'UT supérieure vers l'UT d'exécution -- MÊME
    construction que `backtest_phase2_v7.py::attach_higher_context` (délai de
    clôture de 1 jour, identique pour D1 ET Hebdomadaire avec la convention
    `resample()` de ce projet), pas une jointure inventée séparément."""
    high = df_higher_bb[["date", "bb_median", "bb_width_pct"]].copy()
    high["available_at"] = high["date"] + closure_delay
    high = high.sort_values("available_at")
    merged = pd.merge_asof(
        df_low[["date"]].sort_values("date"), high,
        left_on="date", right_on="available_at", direction="backward",
    )
    return {"ctx_median": merged["bb_median"].values, "ctx_width_pct": merged["bb_width_pct"].values}


def compute_regime_bb_context(df_low: pd.DataFrame, df_higher: pd.DataFrame,
                               period: int = BB_PERIOD, k: float = BB_K,
                               closure_delay: pd.Timedelta = CLOSURE_DELAY) -> np.ndarray:
    """Régime RANGE_NEUTRE/RANGE_TENDANCIEL/TENDANCE/EXCES (`regime_classifier.
    add_regime`, INCHANGÉ) calculé à partir du candidat `H-Context-BB-UT+1`
    (Bollinger de l'UT supérieure, joint sans lookahead) au lieu du proxy
    EMA+/-ATR historique. Retourne un array aligné sur `df_low`, jamais une
    colonne ajoutée en place (l'appelant décide où la stocker -- cf.
    `unified_protocol.py::_prepare_unified`, clé `feat["regime_bb"]`)."""
    bb_higher = compute_bollinger(df_higher, period, k)
    joined = attach_context_bb(df_low, bb_higher, closure_delay)
    scored = add_regime(df_low.reset_index(drop=True),
                         pd.Series(joined["ctx_median"]), pd.Series(joined["ctx_width_pct"]))
    return scored["regime"].to_numpy()
