"""
Backtest combiné pour les 3 patterns géométriques du backlog PLAN.md item 7
(Wall Street, canal manuel, Andrews Pitchfork) — écrit directement (pas par
l'agent délégué, interrompu par un rate-limit juste après avoir fini les 3
modules détecteurs eux-mêmes, sans le temps de construire ce moteur de
mesure prévu par la tâche d'origine).

Chacun des 3 patterns est intégré comme gate/filtre OPTIONNEL, indépendant,
sur le moteur v7 (proxy_v2 causal + régime + validation D1) :
  - Wall Street (`use_wall_street_abstention`) : ABSTENTION totale (aucune
    entrée fraîche NI renfort) quand `wall_street_active` est vrai — lecture
    littérale du corpus ("aucun outil ne fonctionne, arrêter tout").
  - Canal manuel (`use_manual_channel_stop`) : substitue `ctx_support` (bande
    EMA±ATR) par `channel_support` (construction géométrique réelle) quand ce
    dernier est disponible (NaN sinon → fallback silencieux sur ctx_support,
    pas de trou de warmup).
  - Andrews Pitchfork (`use_andrews_gate`) : HYPOTHÈSE D'INTÉGRATION explicite
    posée ici (le corpus documente le NOM/RÔLE/CHIFFRE de l'outil, pas
    comment l'utiliser comme filtre d'entrée, cf. andrews_pitchfork.py tête
    de fichier) — n'autorise une entrée fraîche que si close > `pitchfork_p1`
    (lecture : rester du bon côté de la parallèle basse de la fourchette,
    cohérent avec son rôle de relais correctif après tendance brisée). Cette
    hypothèse d'intégration est nouvelle par rapport à ce que le corpus dit
    explicitement — documentée comme telle, pas comme une règle établie.

Chaque gate mesuré indépendamment (jamais tous en même temps) pour isoler
son effet propre, comme fait pour `use_mtf_stop`/`use_fib_gate` par les
agents précédents.
"""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, ".")
from backtest_phase2 import FEE, load_h1, resample
from backtest_phase2_v7 import prepare, PROFILES_V4, MIN_BORDERS, RULE3_STREAK, RULE3_SIZE_MULT, MAX_TRANCHES, EMA_SLOW
from position_engine import run_position_engine, make_open_tranche_fn
from wall_street_pattern import add_wall_street_column
from manual_trend_channel import add_manual_trend_channel_columns
from andrews_pitchfork import add_andrews_pitchfork_columns

PATTERN_MODES = ("none", "wall_street_abstention", "manual_channel_stop", "andrews_gate")


def run_patterns(h4: pd.DataFrame, profile_name: str, mode: str = "none") -> dict:
    if mode not in PATTERN_MODES:
        raise ValueError(f"mode inconnu: {mode!r}, attendu parmi {PATTERN_MODES}")

    p = PROFILES_V4[profile_name]
    h4 = prepare(h4)
    h4 = add_wall_street_column(h4)
    h4 = add_manual_trend_channel_columns(h4)
    h4 = add_andrews_pitchfork_columns(h4)

    score = h4["score"].values
    atr_v = h4["atr"].values
    ctx_support_v = h4["ctx_support"].values
    if mode == "manual_channel_stop":
        channel_support_v = h4["channel_support"].values
        ctx_support_v = np.where(np.isnan(channel_support_v), ctx_support_v, channel_support_v)
    local_range_v = h4["local_range"].values
    context_range_v = h4["context_range"].values
    n_borders_v = h4["n_borders"].values
    wall_street_v = h4["wall_street_active"].values
    pitchfork_p1_v = h4["pitchfork_p1"].values
    high, low, o, c = h4["high"].values, h4["low"].values, h4["open"].values, h4["close"].values
    n = len(h4)
    warmup = EMA_SLOW + 20
    long_signal = score >= 2

    state = {"last_pyramid_high": -np.inf}

    def gate_extra(j):
        # Même condition pour entrée fraîche et renfort dans ce moteur
        # (contrairement à v6/fib) -> couple identique (g, g).
        abstain = mode == "wall_street_abstention" and bool(wall_street_v[j])
        andrews_ok = True
        if mode == "andrews_gate":
            p1 = pitchfork_p1_v[j]
            andrews_ok = (not np.isnan(p1)) and c[j] > p1
        g = (not abstain) and andrews_ok
        return g, g

    open_tranche_fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v, high, o, score,
        warmup, MIN_BORDERS, MAX_TRANCHES, RULE3_STREAK, RULE3_SIZE_MULT, p["risk_pct"], state,
        extra_gate_fn=gate_extra,
    )

    if mode == "wall_street_abstention":
        gated_long_signal = np.array([
            long_signal[i] and not bool(wall_street_v[i]) for i in range(n)
        ])
    elif mode == "andrews_gate":
        gated_long_signal = np.array([
            long_signal[i] and (not np.isnan(pitchfork_p1_v[i])) and c[i] > pitchfork_p1_v[i]
            for i in range(n)
        ])
    else:
        gated_long_signal = long_signal

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
        for profile in PROFILES_V4:
            for mode in PATTERN_MODES:
                res = run_patterns(h4.copy(), profile, mode=mode)
                rows.append({"symbol": symbol, "profile": profile, "mode": mode, **res})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_patterns_results.csv", index=False)


if __name__ == "__main__":
    main()
