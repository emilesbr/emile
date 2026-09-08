"""
Phase 2 — moteur RECOMMANDÉ (synthèse, vague 4 du "Plan d'autonomie 8h",
PLAN.md). Répond au constat d'ingénieur senior noté dans PLAN.md :
"personne n'a construit LA config recommandée combinant tout ce qui est
validé... en excluant ce qui dégrade... pas de chiffre de référence unique
à citer aujourd'hui." Ce fichier EST ce chiffre de référence, pas une 13e
variante de plus à côté des 12 déjà dans `run_all.py`.

Ne réimplémente AUCUNE logique de bas niveau : réutilise `proxy_v2.py`
(cycle+structure causaux, P0/P0-bis), `regime_classifier.py`,
`position_engine.py`, et `backtest_phase2_v7.py::prepare`/`PROFILES_V4` +
`backtest_phase2_ut2.py::attach_multi_context`/`CLOSURE_DELAY` tels quels.
Le détail des preuves citées ci-dessous (fichiers CSV/MD sources) est dans
`CONFIGURATION_RECOMMANDEE.md` -- ce docstring résume, ne duplique pas.

10 DÉCISIONS ON/OFF (résumé -- détail complet et preuves chiffrées :
CONFIGURATION_RECOMMANDEE.md, qui pointe lui-même vers COUVERTURE_ENSEIGNEMENTS.md)
--------------------------------------------------------------------------------
 1. Cycle causal + structure causale (P0/P0-bis)  : ON, non négociable --
    déjà la seule version en production (add_proxy_v2_score,
    compute_swing_low_confirmed).
 2. Gate MTF                                       : Hebdomadaire SEUL
    ("UT+2 strict"), D1 SAUTÉ comme gate de tendance -- lecture retenue
    dans `backtest_phase2_ut2.py` (système à 3 niveaux à rôles distincts,
    pas une règle cumulative). Chiffres (moyennes 16 combinaisons
    actif x profil, `phase2_ut2_results.csv`) : D1 seul WR 42,4%/PF
    1,81/retour +85,2% vs UT+2 strict WR 42,1%/PF 2,14/retour +133,2% --
    meilleur retour ET profit factor que D1 seul, sans sacrifier
    l'échantillon de trades (428 vs 446) contrairement à "D1 ET Hebdo"
    (193 trades, PF 2,43 mais retour +64,9% seulement, cumulatif -- PAS la
    règle littérale du corpus, gardé en comparaison uniquement dans
    ut2.py). Le rôle "canal/stop" du niveau D1 (immédiatement supérieur)
    n'est PAS répliqué en vrai stop cross-timeframe ici -- cf. point 3.
 3. Stop cross-timeframe réel (`use_mtf_stop`)      : OFF -- mesuré comme
    dégradant le ratio retour/drawdown dans 13/16 combinaisons
    actif x profil (`MTF_CROSS_VALIDATION_H4_D1.md`), malgré une réduction
    de drawdown absolu dans 16/16 (sizing à risque fixe, position plus
    petite). Le stop reste donc le canal natif H4 (ctx_support calculé sur
    le timeframe tradé lui-même), comportement déjà en place par défaut
    dans v7/ut2.
 4. Fibonacci gate                                 : OFF -- dégrade
    UNIFORMÉMENT la performance (32/32 configurations BTC/ETH/BNB/SOL x 4
    profils négatives, `phase2_fib_results.csv`), retour moyen -13,8% vs
    +107,8% baseline.
 5. Andrews Pitchfork gate                          : OFF -- dégrade
    nettement (retour médian 18% vs 212% référence, négatif sur ETH -9,5%
    à -21,9%, `phase2_patterns_results.csv`). Documenté explicitement :
    c'est L'HYPOTHÈSE de gating retenue ici qui est en cause (aucune règle
    d'entrée par Andrews n'est donnée par le corpus, seulement le rôle/le
    chiffre 90% des cas correctifs), PAS une conclusion sur le pattern
    géométrique lui-même -- piste ouverte, non refermée.
 6. Wall Street (abstention élargissement)           : OFF -- effet quasi
    neutre mesuré (WR 38,2% vs 38,9% référence, PF 1,57 vs 1,53,
    `phase2_patterns_results.csv`), donc ni gain ni coût à l'ajouter.
    Choix retenu ici : ne PAS l'ajouter, conforme au principe "moteur le
    plus simple compte tenu des choix" de la tâche -- un gate qui ne change
    rien en moyenne ajoute de la surface de code (et donc de maintenance/
    risque de bug futur) sans bénéfice net démontré. Paramétrable
    séparément si un jour souhaité (`code/wall_street_pattern.py` reste
    disponible), pas supprimé.
 7. Canal manuel comme stop                          : OFF -- change le
    profil risque/récompense (WR -9,5pt, retour total médian plus élevé)
    SANS être strictement meilleur -- un choix de style, pas un remplacement
    validé. Gardé optionnel, pas par défaut : le comportement le plus
    simple et le plus testé (canal EMA+/-ATR natif) reste la référence.
 8. Diversification / Cluster Technique              : OFF -- effet
    marginal isolé proche de zéro et mixte selon l'actif (+0,2/+0,3/-0,2/
    -0,1 pt BTC/ETH/BNB/SOL une fois la pyramidalisation neutralisée des
    deux côtés, `phase2_diversification_results.csv`) -- pas de bénéfice
    net démontré, donc pas ajouté à la config par défaut.
 9. Capital par palier                                : PAS une décision
    ON/OFF de signal -- paramètre de sizing selon le capital réel de
    l'utilisateur (`capital_eur`, optionnel, réutilise
    `capital_tiers.effective_sizing` tel quel). Absent (`capital_eur=None`)
    -> risk_pct du profil choisi, inchangé.
10. +Reverse (table range, TRES_AGRESSIF)             : OFF par défaut --
    résultat mixte (3/4 actifs améliorés +2,2 à +18,7 pts, 1/4 dégradé
    BNB -6,1 pts, `phase2_v7_reverse_results.csv`), et spécifique au seul
    profil TRES_AGRESSIF selon le corpus (RULES_EXTRACTION §3) -- pas un
    défaut applicable à tous les profils. Paramètre optionnel
    (`reverse_at_limit`) laissé disponible pour qui veut l'activer sur ce
    profil précis, en connaissance de cause.

HORS PÉRIMÈTRE DE CE MOTEUR (pas un oubli -- justifié)
-------------------------------------------------------
La table "trade de tendance" à 5 étapes (`trend_table.py`) n'est PAS
intégrée ici : structurellement incompatible avec `position_engine.py`
(justifié en tête de `trend_table.py` lui-même -- machine à états
différente), et son propre résultat mesuré (`phase2_trend_table_results.csv`)
montre que 100% des campagnes se referment en étape Accumulation sur ce
jeu de données -- les étapes 2-5 jamais exercées empiriquement. L'intégrer
à "la config recommandée" reviendrait à ajouter un second moteur parallèle
sans preuve d'apport, contraire au principe "un chiffre de référence
unique, pas une resucée à 15 flags" de cette tâche.

CONCEPTION -- pourquoi un seul point de préparation par historique complet
---------------------------------------------------------------------------
`_prepare_features()` calcule TOUTES les colonnes (score causal, régime,
n_borders, contexte Hebdomadaire) UNE SEULE FOIS sur l'historique complet
fourni. `_run_core()` ne fait ensuite que découper les tableaux numpy déjà
calculés sur une plage [start:end) et rejouer le moteur de position dessus
(équité repartant à 1.0 à chaque appel) -- condition nécessaire pour que
le walk-forward annuel (`code/walkforward_recommended.py`) puisse isoler
une année SANS réintroduire un warmup artificiel à chaque découpage (un an
de bougies Hebdomadaires, ~52, est trop court pour que `EMA_SLOW=55`
converge si on le recalculait par sous-fenêtre -- déjà vérifié comme piège
potentiel avant d'écrire ce code, pas découvert après coup).
"""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, ".")

from backtest_phase2 import FEE, load_h1, resample
from backtest_phase2_v7 import (
    prepare, PROFILES_V4, MIN_BORDERS, RULE3_STREAK, RULE3_SIZE_MULT,
    MAX_TRANCHES, EMA_SLOW,
)
from backtest_phase2_ut2 import attach_multi_context, CLOSURE_DELAY
from position_engine import run_position_engine, make_open_tranche_fn
from capital_tiers import effective_sizing

# Même définition que backtest_phase2_v7.py::run_v7 (i > warmup avant toute
# tentative d'ouverture) -- ici exprimée en index ABSOLU dans l'historique
# complet, pour pouvoir être ajustée correctement lors d'un découpage
# (cf. _run_core : local_warmup = max(0, WARMUP - start)).
WARMUP = EMA_SLOW + 20


def _prepare_features(h4: pd.DataFrame, higher: pd.DataFrame, use_mtf_gate: bool = True) -> dict:
    """Calcule une fois toutes les colonnes nécessaires sur l'historique
    COMPLET fourni. `higher` : dataframe de niveau supérieur pour le gate
    MTF (Hebdomadaire par défaut -- UT+2 strict, décision #2 ci-dessus).

    `use_mtf_gate=False` neutralise le gate (toujours vrai) plutôt que de
    le supprimer du code -- utile quand aucun niveau supérieur n'est
    exploitable faute d'historique suffisant (cf. OOS XRP D1,
    `code/oos_xrp_recommended.py` : un an de données ne suffit pas à faire
    converger un contexte Hebdomadaire ou Mensuel, EMA_SLOW=55 exigerait
    55+ semaines/mois d'historique). Documenté ici, pas un raccourci
    silencieux : le score `+inf`/régime `RANGE_NEUTRE` neutres sont
    délibérément non-NaN pour ne jamais se comparer à NaN (qui donnerait
    silencieusement `False`, l'inverse de l'effet voulu)."""
    h4 = prepare(h4)
    if use_mtf_gate:
        higher = prepare(higher)
        ctx = attach_multi_context(h4, [("H", higher)], closure_delay=CLOSURE_DELAY)
        gate_score = ctx["H"]["score"]
        gate_regime = ctx["H"]["regime"]
    else:
        gate_score = np.full(len(h4), np.inf)
        gate_regime = np.full(len(h4), "RANGE_NEUTRE", dtype=object)

    return {
        "date": h4["date"].values,
        "open": h4["open"].values, "high": h4["high"].values,
        "low": h4["low"].values, "close": h4["close"].values,
        "score": h4["score"].values,
        "atr": h4["atr"].values,
        "ctx_support": h4["ctx_support"].values,
        "local_range": h4["local_range"].values,
        "context_range": h4["context_range"].values,
        "n_borders": h4["n_borders"].values,
        "gate_score": gate_score,
        "gate_regime": gate_regime,
    }


def _run_core(feat: dict, profile_name: str, risk_pct: float = None,
              start: int = 0, end: int = None,
              reverse_at_limit: bool = False, record_trace: bool = False) -> dict:
    """Rejoue le moteur de position sur la plage [start:end) des colonnes
    déjà préparées par `_prepare_features`. `risk_pct=None` -> risk_pct du
    profil (PROFILES_V4) ; sinon override explicite (cf. `run_recommended`,
    décision #9 -- capital par palier)."""
    p = PROFILES_V4[profile_name]
    if risk_pct is None:
        risk_pct = p["risk_pct"]
    end = len(feat["open"]) if end is None else end
    start_ = start

    o = feat["open"][start_:end]; high = feat["high"][start_:end]
    low = feat["low"][start_:end]; c = feat["close"][start_:end]
    score = feat["score"][start_:end]
    atr_v = feat["atr"][start_:end]
    ctx_support_v = feat["ctx_support"][start_:end]
    local_range_v = feat["local_range"][start_:end]
    context_range_v = feat["context_range"][start_:end]
    n_borders_v = feat["n_borders"][start_:end]
    gate_score = feat["gate_score"][start_:end]
    gate_regime = feat["gate_regime"][start_:end]
    n = end - start_

    # cf. docstring module : warmup exprimé en index ABSOLU de l'historique
    # complet, ramené à l'index LOCAL de cette plage. Si la plage démarre
    # déjà après le warmup réel (cas du walk-forward annuel, une année qui
    # n'est pas la première de l'historique), local_warmup <= 0 -> aucune
    # bougie de la plage n'est artificiellement bloquée.
    local_warmup = max(0, WARMUP - start_)

    def gate(i: int) -> bool:
        return bool(gate_score[i] >= 2 and gate_regime[i] != "EXCES")

    def gate_extra(j):
        # Même gate pour l'entrée fraîche et le renfort (config recommandée :
        # pas de distinction régime/fib comme v6/fib, cf. position_engine.py).
        g = gate(j)
        return g, g

    state = {"last_pyramid_high": -np.inf}

    # NB : `local_warmup` joue ici le rôle de `warmup` de make_open_tranche_fn
    # -- comparaison `i > warmup` équivalente à l'ancien early-return
    # `if i <= local_warmup: return None` (is_fresh_entry/is_pyramid_add
    # exigeaient déjà i > local_warmup de toute façon, même effet net).
    open_tranche_fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v, high, o, score,
        local_warmup, MIN_BORDERS, MAX_TRANCHES, RULE3_STREAK, RULE3_SIZE_MULT, risk_pct, state,
        extra_gate_fn=gate_extra,
    )

    gated_long_signal = np.array([(score[i] >= 2) and gate(i) for i in range(n)])

    raw = run_position_engine(
        n, o, high, low, c, gated_long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=MAX_TRANCHES, fee=FEE,
        record_trace=record_trace, reverse_at_limit=reverse_at_limit,
    )
    result = {
        "n_trades": raw["n_trades"], "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"], "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
    }
    if record_trace:
        result["trace"] = raw["trace"]
        result["dates"] = feat["date"][start_:end]
        result["final_equity"] = raw["final_equity"]
    return result


def run_recommended(execution_df: pd.DataFrame, higher_df: pd.DataFrame, profile_name: str,
                     capital_eur: float = None, reverse_at_limit: bool = False,
                     record_trace: bool = False, use_mtf_gate: bool = True) -> dict:
    """Point d'entrée principal -- LA config recommandée (cf. tête de
    fichier pour les 10 décisions). `execution_df` : timeframe tradé (H4
    dans toutes les mesures de référence de ce projet, mais le moteur ne
    suppose rien de spécifique à H4 -- cf. OOS XRP D1). `higher_df` :
    niveau de contexte pour le gate MTF (Hebdomadaire par défaut, décision
    #2). `capital_eur` (décision #9, optionnel) : si fourni, le risk_pct du
    profil est remplacé par `capital_tiers.effective_sizing(...)`."""
    feat = _prepare_features(execution_df, higher_df, use_mtf_gate=use_mtf_gate)
    risk_pct = None
    if capital_eur is not None:
        sizing = effective_sizing(capital_eur, profile_name, PROFILES_V4, MAX_TRANCHES)
        risk_pct = sizing.risk_pct
    return _run_core(feat, profile_name, risk_pct=risk_pct,
                      reverse_at_limit=reverse_at_limit, record_trace=record_trace)


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        weekly = resample(h1, "W")
        for profile in PROFILES_V4:
            res = run_recommended(h4.copy(), weekly.copy(), profile)
            rows.append({"symbol": symbol, "profile": profile, **res})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_recommended_results.csv", index=False)


if __name__ == "__main__":
    main()
