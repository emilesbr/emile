"""
Phase 2 — configuration FIDÈLE (moteur RANGE), par opposition à la config
"recommandée" (`backtest_phase2_recommended.py` / `CONFIGURATION_RECOMMANDEE.md`).

RAPPEL DIRECT DE L'UTILISATEUR (en tant que directeur, ce cycle) : *"nous ne
nous fions pas aux résultats du Proxy [pour décider d']utiliser ou non la
propriété intellectuelle de Philippe, nous l'utilisons dans tous les cas."*
En creusant sérieusement ("que ferait un ingénieur senior ?", pas une réponse
de surface) plutôt que de s'arrêter au premier partage "2 cas clairs / 5
hypothèses" proposé : **4 des 5 "filtres" écartés par défaut dans
`CONFIGURATION_RECOMMANDEE.md` sont en réalité des RÈGLES LITTÉRALES du
corpus, pas des hypothèses d'implémentation à nous** — désactivées par erreur
sur la base de la performance du proxy, exactement le raisonnement interdit.
Ce fichier les active TOUTES sans condition.

VÉRIFIÉ SOURCE PAR SOURCE (pas supposé) :
  - **Stop cross-timeframe réel UT+1** (`use_mtf_stop` dans `recommended.py`,
    OFF là-bas) : `TRADING_LESSONS_BREAKOUT_RATIO11.md` (#12) — *"Stop-loss =
    clôture la plus basse (pour un achat) du canal de tendance de l'UT+1"*.
    Règle littérale, pas une hypothèse. **Activé ici sans condition.**
  - **Abstention Wall Street** (`use_wall_street_abstention`, absente des 10
    décisions ON/OFF, jamais activée par défaut) : `TRADING_LESSONS_
    ALTERNATIVE_MANUELLE.md`/`TRADING_LESSONS_ANALYSE_SANS_INDICATEURS.md`
    (#3/#4) — *"aucun outil ne fonctionne, arrêter tout"*. Abstention TOTALE
    prescrite (aucune des 2 sources ne mentionne de sizing réduit), pas une
    prudence optionnelle. Seule la définition NUMÉRIQUE du pattern (combien
    de bornes) est une hypothèse (H1 de `wall_street_pattern.py`) — le
    comportement une fois détecté (abstention totale), lui, ne l'est pas.
    **Activé ici sans condition.**
  - **+Reverse, profil TRES_AGRESSIF uniquement** (`reverse_at_limit`, OFF
    par défaut dans `recommended.py`) : `RULES_EXTRACTION.md` §3, ligne
    "Très agressif" de la table Money Management range — *"TP100%+Reverse"*
    à l'étape Limite, EXPLICITEMENT absent des 3 autres lignes de profil.
    Règle littérale, scopée à ce seul profil par le corpus lui-même (pas une
    extension arbitraire de notre part si on l'active SEULEMENT pour ce
    profil). **Activé ici sans condition POUR CE PROFIL SEULEMENT** — les 3
    autres gardent `reverse_at_limit=False`, cohérent avec le fait que le
    corpus ne mentionne "+Reverse" QUE sur cette ligne.

CE QUI RESTE VOLONTAIREMENT NON COMBINÉ ICI (limite documentée, pas une
invention silencieuse) :
  - **Canal manuel comme stop** (`manual_trend_channel.py`) : lecture
    littérale elle aussi (construction géométrique Supports->Apex->Tangente,
    `TRADING_LESSONS_ALTERNATIVE_MANUELLE.md` #3), mais mesurée jusqu'ici
    SUR LE MÊME TIMEFRAME que l'exécution (H4, `backtest_phase2_patterns.py`)
    -- alors que la règle du stop UT+1 ci-dessus dit d'utiliser le canal du
    TIMEFRAME SUPÉRIEUR (D1), pas une reconstruction géométrique sur le
    timeframe natif. Combiner les deux exigerait de reconstruire le canal
    manuel SUR D1 (jamais fait, jamais mesuré) et de trancher lequel des
    deux stops (D1 EMA+/-ATR vs D1 canal manuel reconstruit) prime si les
    deux diffèrent -- le corpus ne dit pas lequel choisir dans ce cas précis.
    Plutôt que d'inventer silencieusement cette résolution, ce fichier
    retient le stop UT+1 EMA+/-ATR (D1, `use_mtf_stop`) comme lecture la
    plus directement citée par le corpus pour LE RÔLE DU STOP précisément,
    et laisse le canal manuel comme piste ouverte non résolue (à traiter
    séparément si un jour reconstruit sur D1).
  - **Gate Fibonacci sur l'entrée RANGE** : la règle Fibonacci littérale
    existe (23-38%/38-61%) mais documentée pour valider un PULLBACK DE
    TENDANCE -- déjà implémentée sans condition dans `trend_table.py`
    (`ACCUM_RETRACEMENT_LOW/HIGH`, `PULLBACK_RETRACEMENT_LOW/HIGH`).
    L'appliquer EN PLUS comme filtre d'entrée sur la table RANGE (ce que
    fait `use_fib_gate` dans `backtest_phase2_fib.py`) reste une
    extrapolation À NOUS, pas ce que le corpus dit pour CE protocole précis
    -- laissé backtest-tunable, cohérent avec `CONFIGURATION_RECOMMANDEE.md`.
  - **Gate Andrews Pitchfork sur l'entrée** : le corpus documente le rôle et
    le chiffre de l'outil (90% des cas correctifs), jamais comment
    l'utiliser comme filtre d'entrée -- hypothèse de gating explicitement
    reconnue comme telle dans `andrews_pitchfork.py`/`andrews_gate_
    alternative.py` -- laissé backtest-tunable.

HORS PÉRIMÈTRE DE CE FICHIER (traités ailleurs, pas oubliés, déjà corrects) :
  - **Table de tendance** (`trend_table.py`) : déjà toujours active en
    parallèle du moteur RANGE via `unified_protocol.py` (RANGE+TENDANCE
    concurrents, indépendants, cf. sa correction "exclusivité mutuelle
    retirée") -- CE FICHIER couvre uniquement le moteur RANGE seul (comme
    `recommended.py`), pas le routeur unifié complet.
  - **Diversification 1%+1% / Cluster Technique** (`diversification.py`) :
    déjà un sleeve PARALLÈLE INDÉPENDANT par construction (risque fixe
    1%+1%, jamais modulé par profil, cf. sa propre docstring H3) -- tourne
    EN PLUS de ce moteur, jamais fusionné dedans (architecture déjà
    correcte dans `diversification.py`, rien à changer là-bas).

Ne réimplémente RIEN : réutilise `backtest_phase2_v7.py::prepare`/
`PROFILES_V4`, `backtest_phase2_ut2.py::attach_multi_context`/
`CLOSURE_DELAY`, `wall_street_pattern.py::add_wall_street_column`,
`position_engine.py::make_open_tranche_fn`/`run_position_engine`,
`capital_tiers.py::effective_sizing` tels quels -- même discipline que
`backtest_phase2_recommended.py`/`backtest_phase2_patterns.py`.

AJOUT CE CYCLE (OOS XRP, `code/oos_xrp_faithful.py`) : `run_faithful`/
`_prepare_features` acceptent désormais un paramètre optionnel
`use_mtf_gate: bool = True` qui neutralise UNIQUEMENT le gate Hebdomadaire
(jamais le stop D1 UT+1, littéral et inconditionnel dans tous les cas) --
STRICTEMENT ADDITIF : défaut `True` préserve EXACTEMENT le comportement
existant de tous les appelants déjà en place (dont `unified_protocol.py`,
qui n'utilise pas ce mot-clé). Raison d'être et procédure décidée AVANT
tout résultat : cf. tête de `code/oos_xrp_faithful.py`.
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
from backtest_phase2_recommended import run_recommended, WARMUP
from position_engine import run_position_engine, make_open_tranche_fn
from wall_street_pattern import add_wall_street_column
from capital_tiers import effective_sizing

# RULES_EXTRACTION.md §3, table Money Management range : "+Reverse" (Limite,
# TP100%+Reverse) n'apparaît QUE sur la ligne "Très agressif" -- scope
# littéral du corpus, pas une extension arbitraire de notre part.
REVERSE_SCOPED_PROFILE = "TRES_AGRESSIF"


def _prepare_features(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame,
                       use_mtf_gate: bool = True) -> dict:
    """Calcule toutes les colonnes une seule fois sur l'historique complet.
    `d1` : fournit le VRAI stop cross-timeframe UT+1 (littéral, cf. tête de
    fichier) -- rôle DIFFÉRENT du D1 dans `backtest_phase2_ut2.py` (qui s'en
    sert comme GATE optionnel, jamais comme stop). Ici D1 n'intervient QUE
    comme source du stop ; le gate reste Hebdomadaire seul ("UT+2 strict",
    décision #2 de `recommended.py`, inchangée -- déjà la lecture la plus
    littérale ET la plus performante mesurée, rien à revoir ici).

    `use_mtf_gate` (AJOUTÉ ce cycle -- STRICTEMENT ADDITIF : défaut `True`,
    préserve EXACTEMENT le comportement existant de tous les appelants déjà
    en place, dont `unified_protocol.py` qui appelle `run_faithful` sans ce
    mot-clé). Neutralise UNIQUEMENT le gate Hebdomadaire (score `+inf`,
    régime `RANGE_NEUTRE`, jamais NaN -- même convention que `use_mtf_gate`
    dans `backtest_phase2_recommended.py`, pour ne jamais se comparer
    silencieusement à NaN) -- le stop D1 (UT+1, règle littérale) N'EST PAS
    concerné et reste inconditionnel dans les deux cas, cf. tête de fichier.
    Raison d'être : `code/oos_xrp_faithful.py` (donnée disponible trop
    courte pour faire converger un niveau de gate placé DEUX crans au-dessus
    du niveau d'exécution)."""
    h4 = prepare(h4)
    h4 = add_wall_street_column(h4)
    d1 = prepare(d1)
    ctx_levels = [("D1", d1)]
    if use_mtf_gate:
        weekly = prepare(weekly)
        ctx_levels.append(("W", weekly))
    ctx = attach_multi_context(h4, ctx_levels, closure_delay=CLOSURE_DELAY)

    if use_mtf_gate:
        gate_score = ctx["W"]["score"]
        gate_regime = ctx["W"]["regime"]
    else:
        gate_score = np.full(len(h4), np.inf)
        gate_regime = np.full(len(h4), "RANGE_NEUTRE", dtype=object)

    return {
        "date": h4["date"].values,
        "open": h4["open"].values, "high": h4["high"].values,
        "low": h4["low"].values, "close": h4["close"].values,
        "score": h4["score"].values,
        "atr": h4["atr"].values,
        "ctx_support_d1": ctx["D1"]["ctx_support"],   # stop UT+1, littéral -- toujours utilisé ici
        "local_range": h4["local_range"].values,
        "context_range": h4["context_range"].values,
        "n_borders": h4["n_borders"].values,
        "gate_score": gate_score,
        "gate_regime": gate_regime,
        "wall_street_active": h4["wall_street_active"].values,
    }


def _run_core(feat: dict, profile_name: str, risk_pct: float = None,
              start: int = 0, end: int = None, record_trace: bool = False) -> dict:
    """Même structure que `backtest_phase2_recommended.py::_run_core`, avec
    3 différences NON CONDITIONNELLES (cf. tête de fichier) : stop = D1
    (UT+1, jamais le canal H4 natif), abstention Wall Street (bloque entrée
    fraîche ET renfort, cf. `backtest_phase2_patterns.py` -- même
    comportement, pas réinventé), et `reverse_at_limit=True` SEULEMENT si
    `profile_name == "TRES_AGRESSIF"` (scope littéral du corpus)."""
    p = PROFILES_V4[profile_name]
    if risk_pct is None:
        risk_pct = p["risk_pct"]
    end = len(feat["open"]) if end is None else end
    start_ = start

    o = feat["open"][start_:end]; high = feat["high"][start_:end]
    low = feat["low"][start_:end]; c = feat["close"][start_:end]
    score = feat["score"][start_:end]
    atr_v = feat["atr"][start_:end]
    ctx_support_v = feat["ctx_support_d1"][start_:end]   # UT+1, non conditionnel
    local_range_v = feat["local_range"][start_:end]
    context_range_v = feat["context_range"][start_:end]
    n_borders_v = feat["n_borders"][start_:end]
    gate_score = feat["gate_score"][start_:end]
    gate_regime = feat["gate_regime"][start_:end]
    wall_street_v = feat["wall_street_active"][start_:end]
    n = end - start_

    local_warmup = max(0, WARMUP - start_)

    def gate(i: int) -> bool:
        return bool(gate_score[i] >= 2 and gate_regime[i] != "EXCES")

    def gate_extra(j):
        # Abstention Wall Street NON CONDITIONNELLE (littérale, cf. tête de
        # fichier) : bloque entrée fraîche ET renfort, même comportement que
        # le mode "wall_street_abstention" de `backtest_phase2_patterns.py`
        # (réutilisé à l'identique, pas réinventé).
        abstain = bool(wall_street_v[j])
        g = gate(j) and not abstain
        return g, g

    state = {"last_pyramid_high": -np.inf}
    open_tranche_fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v, high, o, score,
        local_warmup, MIN_BORDERS, MAX_TRANCHES, RULE3_STREAK, RULE3_SIZE_MULT, risk_pct, state,
        extra_gate_fn=gate_extra,
    )

    gated_long_signal = np.array([
        (score[i] >= 2) and gate(i) and not bool(wall_street_v[i]) for i in range(n)
    ])

    reverse_at_limit = (profile_name == REVERSE_SCOPED_PROFILE)   # littéral, RULES_EXTRACTION §3

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


def run_faithful(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame, profile_name: str,
                  capital_eur: float = None, record_trace: bool = False,
                  use_mtf_gate: bool = True) -> dict:
    """Point d'entrée principal -- moteur RANGE avec les 3 règles littérales
    du corpus activées SANS CONDITION (cf. tête de fichier). `capital_eur`
    (optionnel) : même paramètre de sizing que `recommended.py`, décision #9,
    inchangée. `use_mtf_gate` (AJOUTÉ ce cycle, additif, défaut `True` =
    comportement inchangé) : cf. docstring de `_prepare_features` --
    neutralise SEULEMENT le gate Hebdomadaire, jamais le stop D1 littéral."""
    feat = _prepare_features(h4, d1, weekly, use_mtf_gate=use_mtf_gate)
    risk_pct = None
    if capital_eur is not None:
        sizing = effective_sizing(capital_eur, profile_name, PROFILES_V4, MAX_TRANCHES)
        risk_pct = sizing.risk_pct
    return _run_core(feat, profile_name, risk_pct=risk_pct, record_trace=record_trace)


def main():
    """Mesure honnête, comparée côte à côte à `recommended.py` (MÊME
    historique) : n'importe quel écart est rapporté tel quel, meilleur ou
    pire -- la performance de ce backtest ne change RIEN à la décision
    d'activer ces règles (déjà actées ci-dessus comme littérales), elle
    documente juste ce qui se passe une fois qu'on les active vraiment."""
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        weekly = resample(h1, "W")
        for profile in PROFILES_V4:
            res_faithful = run_faithful(h4.copy(), d1.copy(), weekly.copy(), profile)
            res_reco = run_recommended(h4.copy(), weekly.copy(), profile)
            rows.append({
                "symbol": symbol, "profile": profile,
                "faithful_n_trades": res_faithful["n_trades"],
                "faithful_max_dd_%": res_faithful["max_dd_%"],
                "faithful_total_return_%": res_faithful["total_return_%"],
                "faithful_win_rate_%": res_faithful["win_rate_%"],
                "faithful_profit_factor": res_faithful["profit_factor"],
                "recommended_n_trades": res_reco["n_trades"],
                "recommended_max_dd_%": res_reco["max_dd_%"],
                "recommended_total_return_%": res_reco["total_return_%"],
                "recommended_win_rate_%": res_reco["win_rate_%"],
                "recommended_profit_factor": res_reco["profit_factor"],
            })
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    print(result.to_string(index=False))
    result.to_csv("backtest_phase2_faithful_results.csv", index=False)


if __name__ == "__main__":
    main()
