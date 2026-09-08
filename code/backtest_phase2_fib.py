"""
Phase 2 fib — ajoute le filtre Fibonacci retracement comme condition
d'ENTRÉE additionnelle (backlog `PLAN.md` item 4, `COUVERTURE_ENSEIGNEMENTS.md`
ligne Fibonacci), jamais implémenté jusqu'ici malgré les mentions répétées
du corpus. Règle exacte extraite et discutée dans `code/fibonacci.py`
(docstring de tête) — lire ce fichier avant d'interpréter les seuils utilisés
ici (23 %/50 %/61,8 %, PAS la "zone dorée 38-61,8 %" supposée au départ).

Ne touche à AUCUN fichier de production existant (même discipline que
`code/ablation_test_cycle.py`) : réutilise `prepare()`, `attach_higher_context()`,
`PROFILES_V4` et `run_v7()` de `backtest_phase2_v7.py` TELS QUELS (import, pas
copie du fichier), et `add_proxy_v2_score` de `proxy_v2.py` (via `prepare()`)
sans aucune modification — comme demandé. Duplique uniquement le CORPS de
`run_v7` dans une nouvelle fonction `run_v7_fib`, avec la condition Fibonacci
ajoutée à `open_tranche_fn` (entrée uniquement, cf. note ci-dessous).

Pourquoi le gate Fibonacci n'est PAS répercuté sur `gated_long_signal` (le
signal utilisé aussi pour la sortie "flip"), contrairement au gate MTF dans
v7 : le gate MTF (`use_mtf_gate`) reflète un état de RÉGIME qui reste valide
en continu (le contexte D1 est-il toujours aligné ?), donc `run_v7` le
réapplique légitimement à chaque bougie, y compris pour décider si le signal
de sortie doit se déclencher. Le retracement Fibonacci, lui, est par nature
une mesure de la PROFONDEUR DU PULLBACK AU MOMENT DE L'ENTRÉE — une fois la
tranche ouverte, le prix qui progresse vers le swing high fait mécaniquement
BAISSER le % de retracement (bonne nouvelle, pas un signal de sortie) ; le
traiter comme une condition de sortie ferait sortir des positions gagnantes
simplement parce qu'elles progressent. Le filtre Fibonacci ne s'applique donc
qu'à `open_tranche_fn` (par défaut : entrée fraîche SEULEMENT, pas les
renforts/pyramidalisation — cf. paramètre `fib_gate_pyramid` de `run_v7_fib`
pour la raison, structurelle et pas seulement empirique), jamais à la
définition du signal de sortie par flip.
"""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, ".")
from backtest_phase2 import FEE, load_h1, resample, EMA_SLOW
from backtest_phase2_v7 import prepare, attach_higher_context, run_v7, PROFILES_V4
from position_engine import run_position_engine, make_open_tranche_fn
from fibonacci import add_fibonacci_columns

MIN_BORDERS = 3
RULE3_STREAK = 3
RULE3_SIZE_MULT = 0.5
MAX_TRANCHES = 3


def prepare_fib(df: pd.DataFrame) -> pd.DataFrame:
    """Comme prepare() (backtest_phase2_v7.py), avec en plus les 5 colonnes
    Fibonacci (fib_retracement_pct/fib_favorable/fib_optimal/
    fib_context_position/fib_regle_50, cf. code/fibonacci.py). Appliqué au
    H4 (timeframe d'exécution) seulement — le D1 (contexte/référence) n'a
    pas besoin du retracement, il sert uniquement au score/régime/support
    déjà transmis par attach_higher_context."""
    df = prepare(df)
    df = add_fibonacci_columns(df)
    return df


def run_v7_fib(h4: pd.DataFrame, d1: pd.DataFrame, profile_name: str, use_mtf_gate: bool = True,
               use_mtf_stop: bool = False, use_fib_gate: bool = False, use_fib_optimal: bool = False,
               use_fib_regle_50: bool = False, fib_gate_pyramid: bool = False) -> dict:
    """Duplique le corps de run_v7 (backtest_phase2_v7.py) à l'identique,
    seules différences : `prepare_fib()` au lieu de `prepare()` pour le H4,
    et la condition Fibonacci ajoutée à `open_tranche_fn` (cf. docstring de
    tête pour la justification de ne pas la répercuter sur le signal de
    sortie).

    `use_fib_gate` (défaut False, comme `use_mtf_stop` dans v7 : préserve la
    comparabilité avec le comportement historique) : si True, une ENTRÉE
    FRAÎCHE n'est ouverte que si le retracement de la bougie H4 PRÉCÉDENTE
    est dans la zone favorable [23 %, 61,8 %] (`fib_favorable`), cf.
    code/fibonacci.py pour la règle exacte.
    `use_fib_optimal` (défaut False) : si True (et use_fib_gate=True),
    resserre la condition à la sous-zone optimale [23 %, 50 %]
    (`fib_optimal`) plutôt que la zone favorable large.
    `use_fib_regle_50` (défaut False) : si True (et use_fib_gate=True,
    prioritaire sur `use_fib_optimal` s'ils sont combinés par erreur — cf.
    ci-dessous), utilise à la place la "Règle des 50%" COMPLÈTE de #13
    (`fib_regle_50`, code/fibonacci.py) : les DEUX conditions cumulatives du
    corpus (retracement >= 23 % ET pénétration dans les 50 % inférieurs du
    canal de contexte), plutôt que la seule zone de retracement
    (`fib_favorable`/`fib_optimal` ne testent que le retracement, jamais la
    position dans le contexte — gap comblé dans `fibonacci.py`, cf. sa
    MISE À JOUR de tête, ce chantier).

    `fib_gate_pyramid` (défaut False) : si True, applique EN PLUS le même
    filtre aux renforts/pyramidalisation. Défaut False délibéré, découvert
    et documenté honnêtement pendant ce chantier (pas une régression
    corrigée après coup pour arranger le chiffre) : dans ce moteur, un
    renfort n'est tenté QUE lorsque `high[i-1] > state["last_pyramid_high"]`
    — c'est-à-dire au moment précis où le prix fait un NOUVEAU PLUS HAUT
    (poursuite de cassure), ce qui correspond à un retracement proche de
    0 % par construction. Exiger simultanément un retracement de 23-61,8 %
    et un nouveau plus haut est une contradiction quasi structurelle (les
    deux conditions se vérifient rarement ensemble) qui a été mesurée
    (cf. `phase2_fib_results.csv`, colonne `variant`,
    "fib_favorable_incl_pyramide") : le nombre de renforts s'effondre d'un
    facteur ~9 (BTC/MODERE : 193 -> 21) alors que les entrées fraîches ne
    baissent que d'un facteur ~2,5 (311 -> 122), ce qui écrase la
    performance globale (la pyramidalisation étant le principal moteur de
    rendement du moteur, cf. `TRADING_LESSONS_PYRAMIDALISATION.md`,
    "×5 le rendement"). Ce n'est pas un artefact arrangé pour améliorer le
    chiffre : le corpus lui-même distingue les deux phases (source #9,
    `TRADING_LESSONS_MTF_SUIVI_TENDANCE.md` : "Trade d'accumulation... on
    charge la position" [pullback, la zone que Fibonacci décrit] vs "Trade
    de cassure (Breakout) : entrée pure sur la VERTICALITÉ, renfort de
    position" [nouveau plus haut, pas un retracement]) — le réglage par
    défaut (fib_gate_pyramid=False) applique donc le filtre à la phase du
    corpus qu'il est censé décrire (l'entrée/pullback), pas à la phase où
    le corpus décrit explicitement autre chose (le renfort sur verticalité).
    Les deux réglages sont mesurés et rapportés, aucun n'est caché."""
    p = PROFILES_V4[profile_name]
    h4 = prepare_fib(h4)
    d1 = prepare(d1)
    ctx_score, ctx_regime, ctx_support_d1 = attach_higher_context(h4, d1, pd.Timedelta(days=1))

    score = h4["score"].values
    atr_v = h4["atr"].values
    ctx_support_v = ctx_support_d1 if use_mtf_stop else h4["ctx_support"].values
    local_range_v = h4["local_range"].values
    context_range_v = h4["context_range"].values
    n_borders_v = h4["n_borders"].values
    if use_fib_regle_50:
        fib_favorable_v = h4["fib_regle_50"].values
    elif use_fib_optimal:
        fib_favorable_v = h4["fib_optimal"].values
    else:
        fib_favorable_v = h4["fib_favorable"].values
    high, low, o, c = h4["high"].values, h4["low"].values, h4["open"].values, h4["close"].values
    n = len(h4)
    warmup = EMA_SLOW + 20
    long_signal = score >= 2

    state = {"last_pyramid_high": -np.inf}

    def gate_extra(j):
        # Validation croisée D1 : le contexte (référence) doit être aligné,
        # et ni le H4 ni le D1 ne doivent être en régime EXCES
        d1_aligned = (ctx_score[j] >= 2) if use_mtf_gate else True
        d1_not_excess = (ctx_regime[j] != "EXCES") if use_mtf_gate else True
        # Filtre Fibonacci (cf. docstring de tête) : condition d'ENTRÉE
        # seulement, jamais de sortie. Asymétrique entrée fraîche/renfort
        # (contrairement à v6, mais pour une raison différente) :
        # `fib_gate_pyramid` décide si le renfort y est aussi soumis.
        fib_ok = bool(fib_favorable_v[j]) if use_fib_gate else True
        base = d1_aligned and d1_not_excess
        fresh_extra = base and fib_ok
        pyramid_extra = base and (fib_ok if fib_gate_pyramid else True)
        return fresh_extra, pyramid_extra

    open_tranche_fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v, high, o, score,
        warmup, MIN_BORDERS, MAX_TRANCHES, RULE3_STREAK, RULE3_SIZE_MULT, p["risk_pct"], state,
        extra_gate_fn=gate_extra,
    )

    # NB : PAS de fib_ok ici (cf. docstring de tête) — seul le gate MTF est
    # répercuté sur le signal de sortie, comme dans v7 ; le gate Fibonacci ne
    # s'applique qu'à l'ouverture de tranche ci-dessus.
    gated_long_signal = np.array([
        (score[i] >= 2) and ((ctx_score[i] >= 2) if use_mtf_gate else True)
        and ((ctx_regime[i] != "EXCES") if use_mtf_gate else True)
        for i in range(n)
    ])

    raw = run_position_engine(
        n, o, high, low, c, gated_long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=MAX_TRANCHES, fee=FEE,
    )
    return {
        "n_trades": raw["n_trades"], "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"], "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
    }


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        for profile in PROFILES_V4:
            # Référence = v7 tel quel (réglage par défaut des campagnes :
            # use_mtf_gate=True, use_mtf_stop=False), sans le filtre Fibonacci
            baseline = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False)
            # Réglage par défaut retenu : filtre Fibonacci sur l'ENTRÉE FRAÎCHE
            # seulement (zone favorable large [23%,61.8%]), renforts non gatés
            # (cf. docstring de run_v7_fib pour la justification)
            fib_favorable = run_v7_fib(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False,
                                        use_fib_gate=True, use_fib_optimal=False, fib_gate_pyramid=False)
            # Variante resserrée à la sous-zone optimale [23%,50%], renforts non gatés
            fib_optimal = run_v7_fib(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False,
                                      use_fib_gate=True, use_fib_optimal=True, fib_gate_pyramid=False)
            # Variante "Règle des 50%" complète (#13, 2 conditions cumulatives :
            # retracement >= 23% ET pénétration dans les 50% inférieurs du
            # canal de contexte, cf. fibonacci.py MISE À JOUR de tête) — pas
            # mesurée jusqu'ici (gap comblé ce chantier), renforts non gatés
            fib_regle_50 = run_v7_fib(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False,
                                       use_fib_gate=True, use_fib_regle_50=True, fib_gate_pyramid=False)
            # Variante "filtre appliqué aussi aux renforts" — mesurée et
            # rapportée pour transparence (cf. docstring run_v7_fib), pas
            # cachée parce que le résultat est mauvais
            fib_favorable_incl_pyramide = run_v7_fib(h4.copy(), d1.copy(), profile, use_mtf_gate=True,
                                                      use_mtf_stop=False, use_fib_gate=True,
                                                      use_fib_optimal=False, fib_gate_pyramid=True)
            rows.append({"symbol": symbol, "profile": profile, "variant": "baseline_v7 (sans_fibonacci)", **baseline})
            rows.append({"symbol": symbol, "profile": profile, "variant": "fib_favorable [23%,61.8%] (entree_fraiche_seule)", **fib_favorable})
            rows.append({"symbol": symbol, "profile": profile, "variant": "fib_optimal [23%,50%] (entree_fraiche_seule)", **fib_optimal})
            rows.append({"symbol": symbol, "profile": profile, "variant": "fib_regle_50 [retr>=23%_ET_contexte<=50%] (entree_fraiche_seule)", **fib_regle_50})
            rows.append({"symbol": symbol, "profile": profile, "variant": "fib_favorable_incl_pyramide [23%,61.8%]", **fib_favorable_incl_pyramide})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_fib_results.csv", index=False)


if __name__ == "__main__":
    main()
