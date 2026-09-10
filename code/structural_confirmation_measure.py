"""
Banc de mesure de "Confirmation = médiane du canal de contexte, clôturée"
(`RULES_EXTRACTION.md:41` + `TRADING_LESSONS_MAITRISE_GRADIENT_RISQUE.md:55`)
-- le NIVEAU STRUCTUREL ABSOLU relu en direct, par opposition à la distance
`entry + context_range` figée à l'entrée (lecture #12:9, actuellement codée).

Citations exactes, décompte des sources (4 structurelles contre 2 en amplitude
projetée), hypothèses H-Conf-Struct-1..5 et raison MESURÉE pour laquelle le
défaut reste OFF : bloc dédié en tête de `code/position_engine.py`.

Script de MESURE séparé, aucun moteur de production modifié par lui -- même
discipline que `min_borders_sensitivity.py` et
`cluster_technique_threshold_robustness.py`.

Produit deux CSV :
  - `structural_confirmation_results.csv`   : effet backtest complet, OFF vs
    ON, sur les DEUX moteurs concernés (`backtest_phase2_faithful.py`, le
    moteur de fidélité, et `backtest_phase2_v7.py`, le banc isolé), 4 actifs
    x 4 profils.
  - `structural_confirmation_diagnostic.csv` : le diagnostic qui porte
    réellement la décision -- où se situe le niveau structurel au moment de
    l'entrée, et quel délai Validation -> Confirmation il produit, pour les
    4 lectures possibles de "canal de contexte" présentes dans ce projet.
    Indispensable ici pour la même raison qu'au 10e round : un chiffre de
    performance ne dit rien du pouvoir discriminant d'une règle.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

import position_engine as pe
import backtest_phase2_faithful as F
from backtest_phase2 import load_h1, resample, atr, EMA_SLOW, ATR_LEN
from backtest_phase2_v7 import CONTEXT_DURATION, prepare, run_v7
from backtest_phase2_ut2 import CLOSURE_DELAY
from position_engine import context_channel_median

ASSETS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
PROFILES = ["FAIBLE", "MODERE", "AGRESSIF", "TRES_AGRESSIF"]

# Les 4 lectures possibles de "canal de contexte" DÉJÀ présentes dans ce
# projet. Le corpus ne NOMME pas laquelle ; on les mesure toutes plutôt que
# d'en retenir une et de conclure sur elle seule (H-Conf-Struct-1/5).
VARIANTS = ("A_hl_H4", "B_ema_H4", "C_ema_D1", "D_hl_D1")


def build_variants(h4: pd.DataFrame, d1: pd.DataFrame) -> dict:
    out = {}
    # A -- la lecture RETENUE : médiane de [ctx_low, ctx_high], 15D, .shift(1),
    # exactement le canal de `trend_table.py::add_trend_context` et de
    # `fibonacci.py::compute_context_position` (H-Conf-Struct-1).
    out["A_hl_H4"] = context_channel_median(h4, CONTEXT_DURATION)
    # B -- médiane du canal "Extreme Channel" H4 : c'est EMA(55) par
    # construction (`ctx_support = ema_slow - 2*ATR`), et `regime_classifier`
    # nomme déjà cette grandeur "ctx_median : médiane du canal de contexte".
    out["B_ema_H4"] = h4["close"].ewm(span=EMA_SLOW, adjust=False).mean().values
    # C/D -- les mêmes, mais sur l'UT+1 (D1), jointes sans lookahead (même
    # merge_asof + CLOSURE_DELAY que `attach_context_level`). #16:12 appelle
    # l'Extreme Channel "le contexte de l'UT SUPÉRIEURE".
    d1 = d1.copy()
    d1["ema_slow"] = d1["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    d1["ctx_med_hl"] = context_channel_median(d1, CONTEXT_DURATION)
    hi = d1[["date", "ema_slow", "ctx_med_hl"]].copy()
    hi["available_at"] = hi["date"] + CLOSURE_DELAY
    hi = hi.sort_values("available_at")
    merged = pd.merge_asof(h4[["date"]].sort_values("date"), hi,
                           left_on="date", right_on="available_at", direction="backward")
    out["C_ema_D1"] = merged["ema_slow"].values
    out["D_hl_D1"] = merged["ctx_med_hl"].values
    return out


def instrument(sym, profile, feat, variants, rows):
    """Rejoue le VRAI moteur `faithful._run_core` (mode OFF, comportement de
    production inchangé) en observant, sans rien modifier, où se situerait le
    niveau structurel. Monkeypatch strictement local, restauré en `finally`."""
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
                entries[tr["_id"]] = {
                    "entry": tr["entry"], "val_px": tr["val_px"],
                    **{v: variants[v][i - 1] for v in VARIANTS},
                }
            return tr
        return wrapped

    def patched_proc(tr, i, o, low, c, lsp, vcf, ccf, ctb, reverse_at_limit=False):
        st = seen.setdefault(tr.get("_id"), {"val": None, "amp": None,
                                             **{v: None for v in VARIANTS}})
        if st["val"] is None and tr["val_done"]:
            st["val"] = i
        if tr["val_done"]:
            if st["amp"] is None and c[i] >= tr["conf_px"]:
                st["amp"] = i
            for v in VARIANTS:
                lvl = variants[v][i - 1]
                if st[v] is None and not np.isnan(lvl) and c[i] >= lvl:
                    st[v] = i
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
        rows.append({"asset": sym, "profile": profile,
                     "entry": e["entry"], "val_px": e["val_px"],
                     **{f"lvl_{v}": e[v] for v in VARIANTS},
                     "val_i": st["val"], "amp_i": st["amp"],
                     **{f"i_{v}": st[v] for v in VARIANTS}})


def main():
    res_rows, diag_rows = [], []

    for sym in ASSETS:
        h1 = load_h1(sym)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        wk = resample(h1, "1W")
        variants = build_variants(h4.copy(), d1.copy())
        feat = F._prepare_features(h4.copy(), d1.copy(), wk.copy())

        for profile in PROFILES:
            off = F._run_core(feat, profile, use_structural_confirmation=False)
            on = F._run_core(feat, profile, use_structural_confirmation=True)
            v7_off = run_v7(h4.copy(), d1.copy(), profile)
            v7_on = run_v7(h4.copy(), d1.copy(), profile, use_structural_confirmation=True)
            for engine, a, b in (("faithful", off, on), ("v7", v7_off, v7_on)):
                res_rows.append({
                    "engine": engine, "asset": sym, "profile": profile,
                    "n_trades_off": a["n_trades"], "n_trades_on": b["n_trades"],
                    "return_off_%": a["total_return_%"], "return_on_%": b["total_return_%"],
                    "delta_return_pt": round(b["total_return_%"] - a["total_return_%"], 1),
                    "max_dd_off_%": a["max_dd_%"], "max_dd_on_%": b["max_dd_%"],
                    "delta_dd_pt": round(b["max_dd_%"] - a["max_dd_%"], 1),
                    "win_rate_off_%": a["win_rate_%"], "win_rate_on_%": b["win_rate_%"],
                    "pf_off": a["profit_factor"], "pf_on": b["profit_factor"],
                })
            instrument(sym, profile, feat, variants, diag_rows)
        print(f"  {sym} ok", flush=True)

    res = pd.DataFrame(res_rows)
    res.to_csv("structural_confirmation_results.csv", index=False)

    d = pd.DataFrame(diag_rows)
    out = []
    for v in VARIANTS:
        lv = d[f"lvl_{v}"]
        ok = lv.notna()
        sub = d[d["val_i"].notna()]
        delay = (sub[f"i_{v}"] - sub["val_i"]).dropna()
        out.append({
            "variante": v,
            "n_tranches": int(ok.sum()),
            "pct_niveau_sous_entry": round(100 * (lv[ok] <= d["entry"][ok]).mean(), 1),
            "pct_niveau_sous_val_px": round(100 * (lv[ok] <= d["val_px"][ok]).mean(), 1),
            "dist_mediane_%": round(float(((lv[ok] - d["entry"][ok]) / d["entry"][ok] * 100).median()), 2),
            "n_val": int(len(sub)),
            "n_conf_atteinte": int(len(delay)),
            "delai_val_conf_median": float(delay.median()) if len(delay) else None,
            "pct_delai_<=1_bougie": round(100 * float((delay <= 1).mean()), 1) if len(delay) else None,
        })
    sub = d[d["val_i"].notna()]
    delay_amp = (sub["amp_i"] - sub["val_i"]).dropna()
    out.insert(0, {
        "variante": "REFERENCE_amplitude_figee",
        "n_tranches": int(len(d)),
        "pct_niveau_sous_entry": 0.0,
        "pct_niveau_sous_val_px": 0.0,
        "dist_mediane_%": None,
        "n_val": int(len(sub)),
        "n_conf_atteinte": int(len(delay_amp)),
        "delai_val_conf_median": float(delay_amp.median()),
        "pct_delai_<=1_bougie": round(100 * float((delay_amp <= 1).mean()), 1),
    })
    diag = pd.DataFrame(out)
    diag.to_csv("structural_confirmation_diagnostic.csv", index=False)

    print("\n=== DIAGNOSTIC (le chiffre qui porte la décision) ===")
    print(diag.to_string(index=False))
    print("\n=== EFFET BACKTEST (OFF -> ON) ===")
    print(res.groupby("engine")[["delta_return_pt", "delta_dd_pt"]].mean().round(2).to_string())
    for eng in ("faithful", "v7"):
        s = res[res["engine"] == eng]
        print(f"  {eng:9s} : {(s['delta_return_pt'] > 0).sum()} améliorés / "
              f"{(s['delta_return_pt'] < 0).sum()} dégradés / "
              f"{(s['delta_return_pt'] == 0).sum()} inchangés (sur {len(s)})")


if __name__ == "__main__":
    main()
