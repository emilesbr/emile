"""
Banc de mesure -- "Confirmation (Ratio 1:1 Contexte) : utiliser l'UT+2 pour
projeter l'amplitude du range de contexte principal" (`TRADING_LESSONS_
BREAKOUT_RATIO11.md:9`, la citation qui justifie DÉJÀ le mécanisme en
production `conf_px = entry + context_range`, `position_engine.py`).

POURQUOI CE SCRIPT (39e round, `PLAN.md`)
-----------------------------------------------------------------------------
`context_range` (qui alimente `conf_px`) est calculé par `backtest_phase2_v7.
prepare()` sur H4 -- l'UT D'EXÉCUTION, jamais une vraie UT+2 -- alors que sa
propre citation source demande explicitement l'UT+2. Le 16e round avait déjà
mesuré 4 lectures alternatives du "canal de contexte" (`structural_
confirmation_measure.py`, variantes A-D) mais AUCUNE ne testait cette lecture
précise : l'AMPLITUDE (pas un niveau structurel absolu) sourcée sur une VRAIE
UT+2, en nombre de bougies UT-agnostique (`CONTEXT_DURATION_H4_BARS`, 39e
round -- le blocage architectural qui empêchait cette mesure avant).

CE QUE CE SCRIPT EST / N'EST PAS
-----------------------------------------------------------------------------
C'EST une mesure, sur les VRAIES tranches ouvertes par `backtest_phase2_
faithful.py` en production (même monkeypatch-et-observe que `structural_
confirmation_measure.py`, AUCUNE réimplémentation de `process_tranche`) :
si `conf_px` utilisait `entry + context_range` sourcé sur l'Hebdomadaire
(UT+2, fenêtre en bougies) plutôt que sur H4, le délai Validation->
Confirmation et le taux de collapse immédiat changeraient-ils ?
CE N'EST PAS un changement de comportement : aucun moteur de production
n'est modifié, `conf_px` réel reste calculé comme avant. Purement un
diagnostic, comme `min_borders_sensitivity.py`/`structural_confirmation_
measure.py` avant lui.
"""
import numpy as np
import pandas as pd

import emile.core.position_engine as pe
import emile.backtests.backtest_phase2_faithful as F
from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import prepare, CONTEXT_DURATION_H4_BARS
from emile.backtests.backtest_phase2_ut2 import CLOSURE_DELAY

ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
PROFILES = ["FAIBLE", "MODERE", "AGRESSIF", "TRES_AGRESSIF"]

def build_context_range_ut2(h4: pd.DataFrame, weekly: pd.DataFrame) -> np.ndarray:
    """`context_range` calculé sur l'Hebdomadaire LUI-MÊME (fenêtre en
    bougies, `CONTEXT_DURATION_H4_BARS` -- UT-agnostique, 39e round), joint
    sur H4 sans lookahead (même `merge_asof`+`CLOSURE_DELAY` que `attach_
    obstacle_level`/`attach_context_level`). C'est la première fois que ce
    projet calcule un `context_range` sur une VRAIE UT+2 plutôt que sur H4."""
    weekly_prepared = prepare(weekly.copy(), context_duration=CONTEXT_DURATION_H4_BARS)
    hi = weekly_prepared[["date", "context_range"]].copy()
    hi["available_at"] = hi["date"] + CLOSURE_DELAY
    hi = hi.sort_values("available_at")
    merged = pd.merge_asof(h4[["date"]].sort_values("date"), hi,
                           left_on="date", right_on="available_at", direction="backward")
    return merged["context_range"].values

def instrument(sym, profile, feat, context_range_ut2_v, rows):
    """Rejoue le VRAI moteur (`backtest_phase2_faithful._run_core`, OFF --
    comportement de production totalement inchangé) en observant, sans rien
    modifier, où se situerait un `conf_px` alternatif sourcé UT+2. Monkeypatch
    strictement local, restauré en `finally` -- même patron que `structural_
    confirmation_measure.py::instrument`."""
    real_make = pe.make_open_tranche_fn
    real_proc = pe.process_tranche
    counter = {"n": 0}
    entries, seen = {}, {}

    def patched_make(*a, **k):
        fn = real_make(*a, **k)

        def wrapped(i, tranches, win_streak):
            tr = fn(i, tranches, win_streak)
            if tr is not None:
                tr["_id"] = counter["n"]
                counter["n"] += 1
                j = i - 1
                entries[tr["_id"]] = {
                    "entry": tr["entry"], "val_px": tr["val_px"], "conf_px_h4": tr["conf_px"],
                    "conf_px_ut2": tr["entry"] + context_range_ut2_v[j] if not np.isnan(context_range_ut2_v[j]) else np.nan,
                }
            return tr
        return wrapped

    def patched_proc(tr, i, o, low, c, lsp, vcf, ccf, ctb, reverse_at_limit=False):
        st = seen.setdefault(tr.get("_id"), {"val": None, "conf_h4": None, "conf_ut2": None})
        if st["val"] is None and tr["val_done"]:
            st["val"] = i
        if tr["val_done"]:
            e = entries[tr["_id"]]
            if st["conf_h4"] is None and c[i] >= e["conf_px_h4"]:
                st["conf_h4"] = i
            lvl = e["conf_px_ut2"]
            if st["conf_ut2"] is None and not np.isnan(lvl) and c[i] >= lvl:
                st["conf_ut2"] = i
        return real_proc(tr, i, o, low, c, lsp, vcf, ccf, ctb,
                         reverse_at_limit=reverse_at_limit)

    F.make_open_tranche_fn = patched_make
    pe.process_tranche = patched_proc
    try:
        F._run_core(feat, profile)
    finally:
        F.make_open_tranche_fn = real_make
        pe.process_tranche = real_proc

    for tid, st in seen.items():
        e = entries[tid]
        rows.append({
            "asset": sym, "profile": profile, "entry": e["entry"], "val_px": e["val_px"],
            "conf_px_h4": e["conf_px_h4"], "conf_px_ut2": e["conf_px_ut2"],
            "val_i": st["val"], "conf_h4_i": st["conf_h4"], "conf_ut2_i": st["conf_ut2"],
        })

def main():
    diag_rows = []
    for sym in ASSETS:
        h1 = load_h1(sym)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        wk = resample(h1, "1W")
        context_range_ut2_v = build_context_range_ut2(h4.copy(), wk.copy())
        feat = F._prepare_features(h4.copy(), d1.copy(), wk.copy())
        for profile in PROFILES:
            instrument(sym, profile, feat, context_range_ut2_v, diag_rows)
        print(f"  {sym} ok", flush=True)

    d = pd.DataFrame(diag_rows)
    d.to_csv("confirmation_ut2_amplitude_diagnostic.csv", index=False)

    sub = d[d["val_i"].notna()]
    rows = []
    for label, col in (("H4 (production actuelle)", "conf_h4_i"), ("UT+2 réelle (Hebdomadaire, bougies)", "conf_ut2_i")):
        delay = (sub[col] - sub["val_i"]).dropna()
        rows.append({
            "variante": label,
            "n_val_reached": int(len(sub)),
            "n_conf_reached": len(delay),
            "delai_median_bougies": float(delay.median()) if len(delay) else None,
            "pct_delai_<=1_bougie": round(100 * float((delay <= 1).mean()), 1) if len(delay) else None,
        })
    summary = pd.DataFrame(rows)
    print("\n=== DIAGNOSTIC -- délai Validation -> Confirmation, H4 (actuel) vs UT+2 réelle ===")
    print(summary.to_string(index=False))

    # Distance des 2 conf_px l'un par rapport à l'autre (en % du prix
    # d'entrée), pour juger si la différence de fenêtre déplace réellement
    # le niveau ou si c'est un quasi no-op (même mesure que H14 pour ctx_high
    # vs ctx_resistance au 10e round).
    dist = ((sub["conf_px_ut2"] - sub["conf_px_h4"]) / sub["entry"] * 100).dropna()
    print(f"\nDistance conf_px_UT+2 vs conf_px_H4 (% du prix d'entrée) : "
          f"médiane {dist.median():.2f}%, min {dist.min():.2f}%, max {dist.max():.2f}% "
          f"(sur {len(dist)} tranches où les deux sont calculables)")

if __name__ == "__main__":
    main()
