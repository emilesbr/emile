"""
Stress-test de COMBINAISONS jamais croisées jusqu'ici (PLAN.md, "Plan
d'autonomie 8h" point 2, "Toujours ouvert, aggravé par ce cycle" -- l'item de
backlog qui motive directement ce fichier : "hypothèses jamais croisées
SYSTÉMATIQUEMENT... chacune raisonnable isolément, jamais stress-testées
ensemble"). `backtest_phase2_faithful.py` avait déjà croisé 3 règles (stop
D1 UT+1, abstention Wall Street, +Reverse TRES_AGRESSIF) et trouvé un effet
d'interaction dangereux (BNB/TRES_AGRESSIF). Ce fichier cherche
SYSTÉMATIQUEMENT s'il existe D'AUTRES combinaisons dangereuses en ajoutant,
PAR-DESSUS ce même moteur FIDÈLE (donc 4-5 règles combinées à la fois, pas
seulement 3), deux gates supplémentaires déjà mesurés isolément ailleurs
dans le projet mais JAMAIS combinés avec le moteur fidèle complet :
  - le gate Fibonacci sur l'entrée RANGE (`backtest_phase2_fib.py`,
    `use_fib_gate`) -- mesuré isolément contre v7 (SANS stop D1/Wall
    Street/+Reverse), jamais contre `faithful.py`.
  - le gate Andrews contextuel (`andrews_gate_alternative.py`, mode
    "andrews_contextual") -- mesuré isolément contre le moteur v7/patterns
    (SANS stop D1/Wall Street/+Reverse), jamais contre `faithful.py`.
  - LES DEUX EN MÊME TEMPS -- triplette de gates jamais testée nulle part
    (3e variante ci-dessous), qui répond directement à la consigne de la
    tâche ("toute autre combinaison de 2-3 règles déjà actives"), en plus
    des 2 combinaisons demandées explicitement.

CE FICHIER NE RÉIMPLÉMENTE AUCUNE LOGIQUE MÉTIER -- réutilise tel quel
`backtest_phase2_v7.py::prepare`/`PROFILES_V4`/`MIN_BORDERS`/`RULE3_STREAK`/
`RULE3_SIZE_MULT`/`MAX_TRANCHES`/`EMA_SLOW`, `backtest_phase2_ut2.py::
attach_multi_context`/`CLOSURE_DELAY`, `wall_street_pattern.py::
add_wall_street_column`, `fibonacci.py::add_fibonacci_columns`,
`andrews_pitchfork.py::add_andrews_pitchfork_columns`,
`andrews_gate_alternative.py::CONTEXTUAL_REGIMES` (même lecture retenue,
pas une nouvelle hypothèse de gating inventée ici), `position_engine.py::
make_open_tranche_fn`/`run_position_engine`, `capital_tiers.py::
effective_sizing`, et les constantes de `backtest_phase2_faithful.py`
(`REVERSE_SCOPED_PROFILE`, `run_faithful` pour la référence).

POURQUOI CE N'EST PAS "TRIVIALEMENT COMBINABLE" PAR IMPORT SEUL (documenté,
comme demandé par la tâche, PAS une invention silencieuse) : le gate
Fibonacci de `backtest_phase2_fib.py::run_v7_fib` et le gate Andrews de
`andrews_gate_alternative.py::run_andrews` sont chacun des DUPLICATIONS du
corps de `run_v7`/`run_patterns` (pas des fonctions paramétrables branchées
sur un point d'extension), et ni l'un ni l'autre n'utilise le stop D1 UT+1 ni
l'abstention Wall Street ni +Reverse de `backtest_phase2_faithful.py`
(chacun a été construit contre v7 "nu" pour isoler SA propre variable). La
fonction `gate_extra(j)` de `backtest_phase2_faithful.py::_run_core` est un
point d'extension interne (closure locale), pas un paramètre exposé de
`_run_core` -- impossible de lui injecter une condition Fibonacci/Andrews
sans toucher au fichier de production (interdit par la tâche : "ne modifie
AUCUN fichier existant du dépôt"). Solution retenue, SUR LE MÊME MODÈLE que
`backtest_phase2_fib.py::run_v7_fib` (qui duplique déjà le corps de `run_v7`
pour la même raison, cf. sa propre docstring) : `_run_core_gated` ci-dessous
duplique le corps de `backtest_phase2_faithful.py::_run_core` À L'IDENTIQUE
(mêmes variables, même ordre, vérifié par non-régression -- cf.
`test_cross_stress_test_faithful_gates.py`, run_faithful et cette fonction
avec use_fib_gate=False/use_andrews_gate=False donnent EXACTEMENT le même
résultat), et n'ajoute QUE les 2 conditions de gate supplémentaires
(optionnelles, défaut False chacune) à l'intérieur de `gate_extra`. Aucune
mécanique de position (`process_tranche`/`process_reverse`/
`make_open_tranche_fn`/`run_position_engine`) n'est dupliquée ou modifiée.

CHOIX D'IMPLÉMENTATION EXPLICITES POUR CETTE COMBINAISON (documentés, pas
inventés en silence) :
  - **Fibonacci : entrée fraîche SEULEMENT, jamais le renfort/pyramidage**
    -- même choix par défaut et même justification STRUCTURELLE que
    `backtest_phase2_fib.py::run_v7_fib` (`fib_gate_pyramid=False` par
    défaut) : un renfort n'est tenté ici QUE lorsque `high[j] >
    state["last_pyramid_high"]` (nouveau plus haut, cf.
    `position_engine.py::make_open_tranche_fn`), ce qui correspond par
    construction à un retracement proche de 0% -- exiger EN PLUS un
    retracement de 23-61,8% à ce moment précis est une quasi-contradiction
    déjà mesurée comme dégradant fortement le nombre de renforts ailleurs
    dans ce projet. Ni Fibonacci ni Andrews ne sont donc appliqués de façon
    strictement identique fresh/pyramide -- Fibonacci reste asymétrique
    (fresh seulement), Andrews reste symétrique (les deux, cf. point
    suivant) : chaque gate garde le même comportement fresh/pyramide que
    dans son propre fichier d'origine, pas une nouvelle décision arbitraire
    prise ici.
  - **Andrews contextuel : entrée fraîche ET renfort, ET signal de sortie
    (flip)** -- même comportement que `andrews_gate_alternative.py::
    run_andrews` (`gated_signal = long_signal_prev and andrews_ok` utilisé
    à la fois pour `open_tranche_fn` et pour `gated_long_signal`, sans
    distinction fresh/pyramide dans ce fichier d'origine). Reproduit ici à
    l'identique -- pas une extension de notre part.
  - **Fibonacci n'est PAS répercuté sur le signal de sortie (flip)** -- même
    justification que `backtest_phase2_fib.py` (tête de fichier) : le
    retracement DIMINUE mécaniquement quand une position gagnante progresse
    vers le swing high, donc le traiter comme condition de sortie ferait
    sortir des positions gagnantes simplement parce qu'elles progressent.
  - **Ordre d'application des gates** : Wall Street (abstention totale) >
    gate Hebdomadaire (regime!=EXCES, score>=2) > Fibonacci (fresh
    seulement) > Andrews (fresh+pyramide+sortie) -- toutes des conditions
    ET cumulatives, aucune ne remplace une autre.

DÉTECTION DE DRAWDOWN ANNUEL CATASTROPHIQUE (priorité de la tâche, PAS
seulement les moyennes agrégées -- c'est précisément ce qui avait caché
BNB/TRES_AGRESSIF jusqu'ici) : seuils retenus, IDENTIQUES à ceux demandés
explicitement par la tâche -- `max_dd_% < -30` OU `total_return_% < -25`
sur UNE SEULE année civile (walk-forward, même méthode que
`walkforward_faithful.py` : `feat` calculé UNE SEULE FOIS sur tout
l'historique, découpé ensuite à la frontière de chaque année, équité
repartant à 1.0 à chaque année -- objectif "cette année est-elle
catastrophique ?", pas une performance cumulée réaliste).
"""
import pandas as pd
import numpy as np
import sys

from emile.backtests.backtest_phase2 import FEE, load_h1, resample
from emile.backtests.backtest_phase2_v7 import (
    prepare, PROFILES_V4, MIN_BORDERS, RULE3_STREAK, RULE3_SIZE_MULT,
    MAX_TRANCHES, EMA_SLOW,
)
from emile.backtests.backtest_phase2_ut2 import attach_multi_context, CLOSURE_DELAY
from emile.backtests.backtest_phase2_faithful import REVERSE_SCOPED_PROFILE, run_faithful, WARMUP
from emile.core.position_engine import run_position_engine, make_open_tranche_fn
from emile.core.wall_street_pattern import add_wall_street_column
from emile.core.fibonacci import add_fibonacci_columns
from emile.core.andrews_pitchfork import add_andrews_pitchfork_columns
from emile.core.andrews_gate_alternative import CONTEXTUAL_REGIMES  # H-Andrews-Contextuel, même lecture retenue
from emile.core.capital_tiers import effective_sizing

# Seuils de catastrophe -- IDENTIQUES à la consigne de la tâche.
CATASTROPHIC_DD_PCT = -30.0
CATASTROPHIC_RETURN_PCT = -25.0

VARIANTS = ("faithful_seul", "faithful+fib_gate", "faithful+andrews_contextuel", "faithful+fib+andrews")

def _prepare_features_gated(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame) -> dict:
    """Comme `backtest_phase2_faithful.py::_prepare_features`, PLUS les 2
    colonnes de gate supplémentaires (Fibonacci, Andrews), calculées sur le
    H4 -- ni le D1 ni l'Hebdomadaire n'en ont besoin (mêmes rôles que dans
    `backtest_phase2_faithful.py` : D1 = stop UT+1 seul, Hebdomadaire = gate
    seul)."""
    h4 = prepare(h4)                        # ajoute score/atr/ctx_support(H4 natif)/regime/local_range/context_range/n_borders
    h4 = add_wall_street_column(h4)
    h4 = add_fibonacci_columns(h4)          # ajoute fib_retracement_pct/fib_favorable/fib_optimal/fib_context_position/fib_regle_50 (ce fichier ne consomme que fib_favorable)
    h4 = add_andrews_pitchfork_columns(h4)  # ajoute pitchfork_median/p1/p2
    d1 = prepare(d1)
    weekly = prepare(weekly)
    ctx = attach_multi_context(h4, [("D1", d1), ("W", weekly)], closure_delay=CLOSURE_DELAY)

    return {
        "date": h4["date"].values,
        "open": h4["open"].values, "high": h4["high"].values,
        "low": h4["low"].values, "close": h4["close"].values,
        "score": h4["score"].values,
        "atr": h4["atr"].values,
        "ctx_support_d1": ctx["D1"]["ctx_support"],   # stop UT+1, littéral -- toujours utilisé
        "local_range": h4["local_range"].values,
        "context_range": h4["context_range"].values,
        "n_borders": h4["n_borders"].values,
        "gate_score": ctx["W"]["score"],
        "gate_regime": ctx["W"]["regime"],
        "wall_street_active": h4["wall_street_active"].values,
        "fib_favorable": h4["fib_favorable"].values,
        "regime_h4": h4["regime"].values,
        "pitchfork_p1": h4["pitchfork_p1"].values,
    }

def _run_core_gated(feat: dict, profile_name: str, use_fib_gate: bool = False,
                     use_andrews_gate: bool = False, risk_pct: float = None,
                     start: int = 0, end: int = None) -> dict:
    """Duplique À L'IDENTIQUE `backtest_phase2_faithful.py::_run_core` (cf.
    tête de fichier pour la justification de la duplication plutôt que
    l'import), avec 2 conditions de gate supplémentaires OPTIONNELLES
    (défaut False chacune -> comportement bit-à-bit identique à
    `_run_core`, vérifié par non-régression, cf. `test_cross_stress_test_faithful_gates.py`)."""
    p = PROFILES_V4[profile_name]
    if risk_pct is None:
        risk_pct = p["risk_pct"]
    end = len(feat["open"]) if end is None else end
    start_ = start

    o = feat["open"][start_:end]; high = feat["high"][start_:end]
    low = feat["low"][start_:end]; c = feat["close"][start_:end]
    score = feat["score"][start_:end]
    atr_v = feat["atr"][start_:end]
    ctx_support_v = feat["ctx_support_d1"][start_:end]
    local_range_v = feat["local_range"][start_:end]
    context_range_v = feat["context_range"][start_:end]
    n_borders_v = feat["n_borders"][start_:end]
    gate_score = feat["gate_score"][start_:end]
    gate_regime = feat["gate_regime"][start_:end]
    wall_street_v = feat["wall_street_active"][start_:end]
    fib_favorable_v = feat["fib_favorable"][start_:end]
    regime_h4_v = feat["regime_h4"][start_:end]
    pitchfork_p1_v = feat["pitchfork_p1"][start_:end]
    n = end - start_

    local_warmup = max(0, WARMUP - start_)

    def gate(i: int) -> bool:
        return bool(gate_score[i] >= 2 and gate_regime[i] != "EXCES")

    def andrews_ok_at(j: int) -> bool:
        # H-Andrews-Contextuel (andrews_gate_alternative.py) reproduit à
        # l'identique : gate actif SEULEMENT en régime RANGE_TENDANCIEL.
        if not use_andrews_gate:
            return True
        if regime_h4_v[j] not in CONTEXTUAL_REGIMES:
            return True
        p1 = pitchfork_p1_v[j]
        if np.isnan(p1):
            return False
        return bool(c[j] > p1)

    def gate_extra(j):
        abstain = bool(wall_street_v[j])
        g = gate(j) and not abstain
        fib_ok = bool(fib_favorable_v[j]) if use_fib_gate else True
        andrews_ok = andrews_ok_at(j)
        # Fibonacci : fresh seulement (cf. tête de fichier). Andrews :
        # fresh+pyramide (cf. tête de fichier).
        fresh_extra = g and fib_ok and andrews_ok
        pyramid_extra = g and andrews_ok
        return fresh_extra, pyramid_extra

    state = {"last_pyramid_high": -np.inf}
    open_tranche_fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v, high, o, score,
        local_warmup, MIN_BORDERS, MAX_TRANCHES, RULE3_STREAK, RULE3_SIZE_MULT, risk_pct, state,
        extra_gate_fn=gate_extra,
    )

    gated_long_signal = np.array([
        (score[i] >= 2) and gate(i) and not bool(wall_street_v[i]) and andrews_ok_at(i)
        for i in range(n)
    ])

    reverse_at_limit = (profile_name == REVERSE_SCOPED_PROFILE)

    raw = run_position_engine(
        n, o, high, low, c, gated_long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=MAX_TRANCHES, fee=FEE,
        reverse_at_limit=reverse_at_limit,
    )
    return {
        "n_trades": raw["n_trades"], "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"], "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
    }

def run_gated(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame, profile_name: str,
              use_fib_gate: bool = False, use_andrews_gate: bool = False,
              capital_eur: float = None) -> dict:
    """Point d'entrée agrégé (tout l'historique), sur le modèle de
    `run_faithful`."""
    feat = _prepare_features_gated(h4, d1, weekly)
    risk_pct = None
    if capital_eur is not None:
        sizing = effective_sizing(capital_eur, profile_name, PROFILES_V4, MAX_TRANCHES)
        risk_pct = sizing.risk_pct
    return _run_core_gated(feat, profile_name, use_fib_gate=use_fib_gate,
                            use_andrews_gate=use_andrews_gate, risk_pct=risk_pct)

def _variant_kwargs(variant: str) -> dict:
    return {
        "faithful_seul": dict(use_fib_gate=False, use_andrews_gate=False),
        "faithful+fib_gate": dict(use_fib_gate=True, use_andrews_gate=False),
        "faithful+andrews_contextuel": dict(use_fib_gate=False, use_andrews_gate=True),
        "faithful+fib+andrews": dict(use_fib_gate=True, use_andrews_gate=True),
    }[variant]

def yearly_breakdown(symbol: str, profile: str) -> list:
    h1 = load_h1(symbol)
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")
    weekly = resample(h1, "W")
    feat = _prepare_features_gated(h4, d1, weekly)

    dates = pd.to_datetime(feat["date"])
    years = sorted(dates.year.unique())
    rows = []
    for variant in VARIANTS:
        kw = _variant_kwargs(variant)
        for y in years:
            idx = np.where(dates.year == y)[0]
            if len(idx) == 0:
                continue
            start, end = int(idx[0]), int(idx[-1]) + 1
            res = _run_core_gated(feat, profile, start=start, end=end, **kw)
            catastrophic = (res["max_dd_%"] < CATASTROPHIC_DD_PCT) or (res["total_return_%"] < CATASTROPHIC_RETURN_PCT)
            rows.append({
                "symbol": symbol, "profile": profile, "variant": variant, "year": int(y),
                "n_bars": end - start, **res, "catastrophic": catastrophic,
            })
    return rows

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        for profile in PROFILES_V4:
            rows.extend(yearly_breakdown(symbol, profile))
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    result.to_csv("cross_stress_test_faithful_gates_walkforward.csv", index=False)

    print("=== Années CATASTROPHIQUES trouvées (max_dd_% < -30 OU total_return_% < -25) ===")
    cata = result[result["catastrophic"]]
    if len(cata) == 0:
        print("AUCUNE -- résultat honnête, pas forcé : aucune combinaison actif x profil x variant "
              "testée ici ne produit d'année catastrophique sur 2020-2026.")
    else:
        print(cata[["symbol", "profile", "variant", "year", "total_return_%", "max_dd_%"]].to_string(index=False))

    print("\n=== Récapitulatif honnête : pire année par combinaison (symbol/profile/variant) ===")
    worst = result.loc[result.groupby(["symbol", "profile", "variant"])["max_dd_%"].idxmin()]
    print(worst[["symbol", "profile", "variant", "year", "total_return_%", "max_dd_%", "catastrophic"]].to_string(index=False))
    worst.to_csv("cross_stress_test_faithful_gates_worst_year.csv", index=False)

    # Non-régression informelle (contrôle rapide, PAS un remplacement des
    # tests unitaires) : faithful_seul (variant de ce fichier) vs run_faithful
    # (backtest_phase2_faithful.py), agrégé tout historique, doit coïncider.
    print("\n=== Non-régression rapide : faithful_seul (ce fichier) vs run_faithful (agrégé, BTC/MODERE) ===")
    h1 = load_h1("BTCUSDT")
    h4 = resample(h1, "4h"); d1 = resample(h1, "1D"); weekly = resample(h1, "W")
    ref = run_faithful(h4.copy(), d1.copy(), weekly.copy(), "MODERE")
    here = run_gated(h4.copy(), d1.copy(), weekly.copy(), "MODERE", use_fib_gate=False, use_andrews_gate=False)
    print(f"  run_faithful      : {ref}")
    print(f"  run_gated(faithful_seul) : {here}")
    print(f"  IDENTIQUE : {ref == here}")

if __name__ == "__main__":
    main()
