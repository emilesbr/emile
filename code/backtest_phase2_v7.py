"""
Phase 2 v7 — première fusion réelle entre le moteur complet (v6 : proxy
TSI+cycle+structure, régime, risk management corrigé) ET la cascade
multi-timeframe (jamais faite jusqu'ici : v4/v5/v6 tournaient chacun sur UN
SEUL timeframe isolé, malgré le nom trompeur "Extreme Channel" qui n'était
qu'une bande de volatilité locale, PAS un vrai canal de l'UT supérieure).

Règle appliquée (cohérente avec les 7 sources du corpus sur le sujet) :
  - Exécution sur H4
  - Contexte/référence sur D1 : un signal H4 n'est validé que si le score
    proxy_v2 du D1 (dernière bougie D1 ENTIÈREMENT CLÔTURÉE, sans lookahead)
    est ÉGALEMENT >= 2. Le régime D1 doit aussi être différent d'EXCES.
"""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, ".")
from backtest_phase2 import FEE, load_h1, resample, atr, EMA_SLOW, ATR_LEN
from proxy_v2 import add_proxy_v2_score, compute_swing_low_confirmed
from position_engine import (
    run_position_engine, make_open_tranche_fn,
    context_channel_median, make_structural_conf_update_fn,
)
from regime_classifier import add_regime, compute_wide_channel

LOCAL_DURATION = "5D"
CONTEXT_DURATION = "15D"
SWING_ORDER = 3
MIN_BORDERS = 3
RULE3_STREAK = 3
RULE3_SIZE_MULT = 0.5
MAX_TRANCHES = 3

PROFILES_V4 = {
    "FAIBLE":        {"risk_pct": 0.01, "val_close": 0.50, "conf_close": 0.00},
    "MODERE":        {"risk_pct": 0.02, "val_close": 0.25, "conf_close": 0.25},
    "AGRESSIF":      {"risk_pct": 0.03, "val_close": 0.00, "conf_close": 0.50},
    "TRES_AGRESSIF": {"risk_pct": 0.05, "val_close": 0.00, "conf_close": 0.00},
}


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = add_proxy_v2_score(df)
    df["atr"] = atr(df, ATR_LEN)
    ema_slow = df["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    df["ctx_support"] = ema_slow - 2 * df["atr"]
    width_pct = (2 * 2 * df["atr"]) / ema_slow * 100
    df = add_regime(df, ema_slow, width_pct)
    # Largeur du canal "Extreme Channel" exposée en colonne (STRICTEMENT
    # ADDITIF : `add_regime` la recevait déjà en argument ci-dessus, elle
    # n'était simplement jamais conservée). Consommée par
    # `regime_classifier.compute_wide_channel` pour la règle de volatilité
    # "Stop Loss = taille du canal" -- cf. le bloc dédié en tête de
    # `position_engine.py`. Une SEULE définition de la largeur du canal dans
    # tout le projet, calculée ici, jamais recalculée ailleurs.
    df["ctx_width_pct"] = width_pct

    ts = df.set_index("date")
    df["local_range"] = (ts["high"].rolling(LOCAL_DURATION).max() - ts["low"].rolling(LOCAL_DURATION).min()).values
    df["context_range"] = (ts["high"].rolling(CONTEXT_DURATION).max() - ts["low"].rolling(CONTEXT_DURATION).min()).values
    # MÉDIANE du canal de contexte -- niveau structurel ABSOLU de l'étape
    # Confirmation (`RULES_EXTRACTION.md:41`, "médiane canal contexte,
    # clôturée" ; #5:55, "la médiane (50%) du contexte"). STRICTEMENT ADDITIF :
    # colonne nouvelle, aucun consommateur existant ne la lit, aucun résultat
    # numérique changé (vérifié par non-régression bit-à-bit). Consommée
    # uniquement quand `use_structural_confirmation=True` -- cf. le bloc
    # "CONFIRMATION = MÉDIANE DU CANAL DE CONTEXTE" en tête de
    # `position_engine.py` (hypothèses H-Conf-Struct-1..5).
    # À NE PAS CONFONDRE avec `context_range` juste au-dessus : celle-ci est
    # une AMPLITUDE (max-min, sans `.shift(1)`), celle-là un NIVEAU DE PRIX
    # (médiane des deux bornes, avec `.shift(1)` causal).
    df["ctx_median"] = context_channel_median(df, CONTEXT_DURATION)

    # CAUSAL depuis le traitement de la réserve P0-bis (COUVERTURE_ENSEIGNEMENTS.md
    # / PLAN.md occurrence #4) : un swing low n'entre dans le compte de bornes
    # qu'une fois confirmé (compute_swing_low_confirmed), pas au moment du creux
    # lui-même (qui dépendrait de SWING_ORDER barres futures).
    low_v = df["low"].values
    is_swing_low_confirmed = compute_swing_low_confirmed(low_v, order=SWING_ORDER)
    df["n_borders"] = pd.Series(is_swing_low_confirmed, index=ts.index).rolling(CONTEXT_DURATION).sum().values
    return df


def attach_higher_context(df_low: pd.DataFrame, df_high: pd.DataFrame, high_duration: pd.Timedelta,
                           extra_cols: tuple = ()) -> tuple:
    """Jointure sans lookahead : pour chaque bougie H4, le score, le régime ET
    le `ctx_support` (niveau de prix absolu, "Extreme Channel") de la DERNIÈRE
    bougie D1 entièrement close à cet instant. Même logique temporelle pour
    les trois colonnes (aucune n'utilise une bougie D1 pas encore close).

    `extra_cols` (défaut `()` -> tuple de retour à 3 éléments EXACTEMENT
    comme avant, aucun des 5 appelants existants n'est affecté) : noms de
    colonnes supplémentaires de `df_high` à joindre PAR LA MÊME jointure et à
    ajouter à la fin du tuple retourné, dans l'ordre demandé. Ajouté pour que
    la règle de volatilité "Stop Loss = taille du canal" puisse lire la
    LARGEUR du canal du même niveau que celui qui fournit le stop
    (`ctx_width_pct` du D1 quand `use_mtf_stop=True`) sans dupliquer la
    jointure ni en inventer une seconde -- cf. H-Canal-Large-2 dans
    `position_engine.py`."""
    cols = ["date", "score", "regime", "ctx_support"] + list(extra_cols)
    high = df_high[cols].copy()
    high["available_at"] = high["date"] + high_duration
    high = high.sort_values("available_at")
    merged = pd.merge_asof(
        df_low[["date"]].sort_values("date"), high, left_on="date", right_on="available_at", direction="backward"
    )
    base = (merged["score"].values, merged["regime"].values, merged["ctx_support"].values)
    return base + tuple(merged[name].values for name in extra_cols)


def run_v7(h4: pd.DataFrame, d1: pd.DataFrame, profile_name: str, use_mtf_gate: bool = True,
           use_mtf_stop: bool = False, record_trace: bool = False, reverse_at_limit: bool = False,
           use_wide_channel_halving: bool = False,
           use_structural_confirmation: bool = False) -> dict:
    """`use_mtf_stop` (défaut False, préserve le comportement historique de
    v7) : si True, le stop ("Extreme Channel") utilisé à l'entrée est celui
    calculé sur le VRAI D1 (`ctx_support` D1, transmis sans lookahead par
    `attach_higher_context`) plutôt que le `ctx_support` recalculé sur le H4
    lui-même. Les deux sont des niveaux de prix absolus (pas des distances),
    donc directement substituables dans le calcul de `stop_pct` ci-dessous.

    `reverse_at_limit` (défaut False, préserve le comportement historique de
    v7, même principe que `use_mtf_stop`) : transmis tel quel à
    `run_position_engine` -- si True, une tranche qui se clôture à la Limite
    ouvre en plus une jambe short "+Reverse" (RULES_EXTRACTION.md §3, profil
    Très Agressif uniquement au sens du manuel, mais le paramètre est
    utilisable avec n'importe quel profil ici -- c'est l'appelant qui décide
    à qui l'appliquer, cf. hypothèse H-Reverse-Range dans
    `position_engine.py`).

    `use_wide_channel_halving` (défaut False, préserve le comportement
    historique de v7, même pattern que `use_mtf_stop`/`reverse_at_limit`
    ci-dessus et que `use_fib_gate` de `backtest_phase2_fib.py`) : active la
    règle de volatilité "Stop Loss = taille du canal" de
    `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md` §5 -- si le canal est TRÈS
    LARGE, stop divisé par deux ET taille divisée par deux simultanément.
    Citation exacte, mécanique et hypothèses H-Canal-Large-1..4 : bloc dédié
    en tête de `position_engine.py`. Ce moteur-ci est le banc de MESURE de la
    règle (variante isolée, comparable au reste de l'historique v7) ; le
    moteur où elle est active SANS CONDITION parce que le corpus en fait une
    règle obligatoire est `backtest_phase2_faithful.py`, comme pour le stop
    UT+1 et l'abstention Wall Street.

    La largeur mesurée est celle du canal QUI PORTE LE STOP (H-Canal-Large-2)
    : `ctx_width_pct` du D1 quand `use_mtf_stop=True`, du H4 natif sinon.

    `use_structural_confirmation` (défaut False, préserve le comportement
    historique de v7 -- même pattern que les trois paramètres ci-dessus) :
    l'étape Confirmation devient le NIVEAU STRUCTUREL ABSOLU du manuel
    (`RULES_EXTRACTION.md:41`, *"Confirmation (médiane canal contexte,
    clôturée)"* ; #5:55, *"clôture d'une bougie sous/au-dessus la médiane
    (50%) du contexte"*), relu EN DIRECT à chaque bougie, au lieu de la
    distance `entry + context_range` figée à l'entrée (lecture #12:9, Ratio
    1:1 Contexte). Citations, décompte des sources, hypothèses
    H-Conf-Struct-1..5 et raison MESURÉE pour laquelle le défaut reste OFF
    (le niveau est déjà franchi à l'entrée dans 9 cas sur 10, ce qui
    collapserait Confirmation sur Validation et détruirait la règle du
    break-even différé) : bloc dédié en tête de `position_engine.py`.
    Ce moteur-ci est le banc de MESURE isolé de la règle."""
    p = PROFILES_V4[profile_name]
    h4 = prepare(h4)
    d1 = prepare(d1)
    ctx_score, ctx_regime, ctx_support_d1, ctx_width_d1 = attach_higher_context(
        h4, d1, pd.Timedelta(days=1), extra_cols=("ctx_width_pct",))

    score = h4["score"].values
    atr_v = h4["atr"].values
    ctx_support_v = ctx_support_d1 if use_mtf_stop else h4["ctx_support"].values
    ctx_width_v = ctx_width_d1 if use_mtf_stop else h4["ctx_width_pct"].values
    wide_channel_v = compute_wide_channel(ctx_width_v) if use_wide_channel_halving else None
    local_range_v = h4["local_range"].values
    context_range_v = h4["context_range"].values
    n_borders_v = h4["n_borders"].values
    high, low, o, c = h4["high"].values, h4["low"].values, h4["open"].values, h4["close"].values
    n = len(h4)
    warmup = EMA_SLOW + 20
    long_signal = score >= 2

    state = {"last_pyramid_high": -np.inf}

    def gate_extra(j):
        # Validation croisée D1 : le contexte (référence) doit être aligné,
        # et ni le H4 ni le D1 ne doivent être en régime EXCES. Même gate
        # pour l'entrée fraîche et le renfort (pas de distinction ici,
        # contrairement à v6/fib).
        d1_aligned = (ctx_score[j] >= 2) if use_mtf_gate else True
        d1_not_excess = (ctx_regime[j] != "EXCES") if use_mtf_gate else True
        g = d1_aligned and d1_not_excess
        return g, g

    open_tranche_fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v, high, o, score,
        warmup, MIN_BORDERS, MAX_TRANCHES, RULE3_STREAK, RULE3_SIZE_MULT, p["risk_pct"], state,
        extra_gate_fn=gate_extra, wide_channel_v=wide_channel_v,
    )

    # NB : la sortie de signal (flip) doit aussi respecter le gate MTF pour
    # être cohérente -> on passe le signal déjà gated à run_position_engine
    gated_long_signal = np.array([
        (score[i] >= 2) and ((ctx_score[i] >= 2) if use_mtf_gate else True)
        and ((ctx_regime[i] != "EXCES") if use_mtf_gate else True)
        for i in range(n)
    ])

    raw = run_position_engine(
        n, o, high, low, c, gated_long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=MAX_TRANCHES, fee=FEE,
        record_trace=record_trace, reverse_at_limit=reverse_at_limit,
        update_levels_fn=(
            make_structural_conf_update_fn(h4["ctx_median"].values)
            if use_structural_confirmation else None
        ),
    )
    result = {
        "n_trades": raw["n_trades"], "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"], "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
    }
    if record_trace:
        # dates H4 (une par bougie, même longueur que o/high/low/c) -- pour
        # que l'appelant (funding_rate_exact.py) puisse aligner chaque
        # instantané de trace["snapshots"] sur un timestamp réel et donc
        # sur les vrais événements de funding (toutes les 8h).
        result["trace"] = raw["trace"]
        result["dates"] = h4["date"].values
        result["final_equity"] = raw["final_equity"]
    return result


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        for profile in PROFILES_V4:
            res_mtf = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False)
            res_solo = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=False, use_mtf_stop=False)
            res_mtf_stopd1 = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=True)
            # Variante de MESURE de la règle de volatilité "Stop Loss = taille
            # du canal" (cf. `use_wide_channel_halving` / bloc dédié en tête de
            # `position_engine.py`) : STRICTEMENT le même moteur que la 1re
            # ligne ci-dessus, un seul paramètre change -- l'écart mesuré est
            # donc l'effet ISOLÉ de la règle, rien d'autre.
            res_mtf_wide = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True, use_mtf_stop=False,
                                  use_wide_channel_halving=True)
            rows.append({"symbol": symbol, "profile": profile, "gate": "H4_valide_par_D1", "stop": "H4_meme_UT", **res_mtf})
            rows.append({"symbol": symbol, "profile": profile, "gate": "H4_seul (=v6)", "stop": "H4_meme_UT", **res_solo})
            rows.append({"symbol": symbol, "profile": profile, "gate": "H4_valide_par_D1", "stop": "D1_reel", **res_mtf_stopd1})
            rows.append({"symbol": symbol, "profile": profile, "gate": "H4_valide_par_D1",
                         "stop": "H4_meme_UT + canal_large/2", **res_mtf_wide})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_v7_mtf_results.csv", index=False)


if __name__ == "__main__":
    main()
