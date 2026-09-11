"""
Banc de mesure ISOLÉ pour `trade_confidence.py` (cf. sa tête de fichier pour
le design complet) -- même discipline que `andrews_gate_alternative.py`/
`backtest_phase2_v7_squeeze.py` avant leur intégration dans `faithful.py`/
`unified_protocol.py` : mesure honnête AVANT toute décision de câblage.

Ne modifie AUCUN moteur existant. Répond à 3 questions, sur données réelles
(BTC/ETH/BNB/SOL H4), AVANT de décider si ce score mérite d'être câblé dans
le sizing réel des moteurs opérationnels :
  1. Le score n'est-il pas DÉGÉNÉRÉ (toujours la même valeur) ?
  2. Où se situent les bougies où `faithful.py` ouvre RÉELLEMENT une tranche
     aujourd'hui (gate() vrai) sur cette distribution -- le score a-t-il un
     pouvoir discriminant sur les entrées déjà prises, ou est-il indépendant
     du gate existant (ce qui serait un signal complémentaire, pas redondant) ?
  3. Quel `risk_pct` moyen en résulterait si ce score pilotait le sizing,
     comparé aux profils fixes actuels ?
"""
import numpy as np
import pandas as pd

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_faithful import _prepare_features, _run_core
from emile.core.fibonacci import add_fibonacci_columns
from emile.backtests.backtest_phase2_v7 import prepare, PROFILES_V4
from emile.core.trade_confidence import (
    compute_range_confidence_score, confidence_to_risk_pct, CONFIDENCE_RISK_PCT,
)


def measure(symbol: str) -> dict:
    h1 = load_h1(symbol)
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")
    weekly = resample(h1, "W")

    feat = _prepare_features(h4.copy(), d1.copy(), weekly.copy())

    fib_df = add_fibonacci_columns(prepare(h4.copy()))
    fib_favorable = fib_df["fib_favorable"].values

    score = compute_range_confidence_score(feat["regime_d1"], feat["n_borders"], fib_favorable)

    valid = ~np.isnan(score)
    dist = {k: float(np.mean(score[valid] == k)) for k in (0, 1, 2, 3)}

    # Bougies où faithful.py ouvrirait RÉELLEMENT une tranche aujourd'hui
    # (gated_long_signal, reconstruit à l'identique de _run_core::gate(),
    # sans toucher au moteur -- juste pour croiser avec le score).
    d1_not_range = np.array([
        feat["regime_d1"][i] not in ("RANGE_NEUTRE", "RANGE_TENDANCIEL") for i in range(len(feat["close"]))
    ])
    andrews_ok = np.array([
        feat["regime_h4"][i] != "RANGE_TENDANCIEL" or
        (not np.isnan(feat["pitchfork_p1"][i]) and feat["close"][i] > feat["pitchfork_p1"][i])
        for i in range(len(feat["close"]))
    ])
    gate_today = (
        (feat["score"] >= 2) & (feat["gate_score"] >= 2) & (feat["gate_regime"] != "EXCES")
        & (feat["regime_h4"] != "EXCES") & d1_not_range & andrews_ok
        & (~feat["wall_street_active"])
    )
    gated_valid = gate_today & valid
    dist_when_gated = (
        {k: float(np.mean(score[gated_valid] == k)) for k in (0, 1, 2, 3)}
        if gated_valid.sum() > 0 else {k: float("nan") for k in (0, 1, 2, 3)}
    )

    risk_pcts = np.array([confidence_to_risk_pct(s) or 0.0 for s in score[gated_valid]])
    mean_risk_pct = float(risk_pcts.mean()) if len(risk_pcts) else float("nan")
    abstain_frac = float(np.mean(risk_pcts == 0.0)) if len(risk_pcts) else float("nan")

    return {
        "symbol": symbol,
        "n_bars_valid_score": int(valid.sum()),
        "dist_all": dist,
        "n_gated_today": int(gate_today.sum()),
        "dist_when_gated": dist_when_gated,
        "mean_risk_pct_if_wired": mean_risk_pct,
        "abstain_frac_among_gated": abstain_frac,
    }


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = [measure(s) for s in symbols]
    for r in rows:
        print(f"\n=== {r['symbol']} ===")
        print(f"  bougies avec score valide : {r['n_bars_valid_score']}")
        print(f"  distribution du score (toutes bougies)     : "
              f"0={r['dist_all'][0]:.3f} 1={r['dist_all'][1]:.3f} "
              f"2={r['dist_all'][2]:.3f} 3={r['dist_all'][3]:.3f}")
        print(f"  bougies où faithful.py ouvre AUJOURD'HUI (gate réel) : {r['n_gated_today']}")
        print(f"  distribution du score PARMI ces bougies    : "
              f"0={r['dist_when_gated'][0]:.3f} 1={r['dist_when_gated'][1]:.3f} "
              f"2={r['dist_when_gated'][2]:.3f} 3={r['dist_when_gated'][3]:.3f}")
        print(f"  fraction qui serait mise en ABSTENTION si ce score pilotait le sizing : "
              f"{r['abstain_frac_among_gated']:.3f}")
        print(f"  risk_pct moyen résultant si câblé : {r['mean_risk_pct_if_wired']:.4f} "
              f"(pour comparaison : FAIBLE={PROFILES_V4['FAIBLE']['risk_pct']}, "
              f"MODERE={PROFILES_V4['MODERE']['risk_pct']}, "
              f"AGRESSIF={PROFILES_V4['AGRESSIF']['risk_pct']}, "
              f"TRES_AGRESSIF={PROFILES_V4['TRES_AGRESSIF']['risk_pct']})")


if __name__ == "__main__":
    main()
