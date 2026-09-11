"""
Investigation dédiée de l'occurrence #3 du pattern récurrent (PLAN.md,
tableau "Méthode de travail") : la condition composite
`cycle_ascending = sinewave > sinewave_prev` (proxy_v2.py::add_proxy_v2_score)
s'est révélée anti-corrélée au rendement futur sur une sinusoïde synthétique
PURE et sans bruit (`code/test_proxy_v2.py`, docstring), à l'inverse de la
validation hors-échantillon réelle sur XRP (`OOS_VALIDATION_CYCLE_SIGN.md`,
positive et significative) — divergence jamais tranchée jusqu'ici.

Attention à une nuance importante avant de lire les chiffres ci-dessous :
`OOS_VALIDATION_CYCLE_SIGN.md` teste `cycle_favorable` (ascending ET pas
épuisé), pas `cycle_ascending` isolée — ce script mesure donc les DEUX
grandeurs séparément, sur synthétique ET sur réel, pour ne pas répéter cette
confusion.

Ce script ne modifie AUCUN fichier de production (import direct de
`proxy_v2.py` tel quel). Deux parties :

  PARTIE 1 — reproduit la mesure originale (corrélation cycle_ascending /
  rendement futur sur sinusoïde synthétique pure), avec (a) l'ancienne
  version BATCH (`compute_cycle_phase`, pour vérifier si la divergence
  d'origine — trouvée à l'époque de la version batch — persiste) et (b) la
  version CAUSALE actuellement en production (`compute_cycle_phase_causal`,
  depuis le traitement du P0) — pour vérifier si le passage au calcul causal
  a changé quoi que ce soit à CETTE divergence spécifique.

  PARTIE 2 — teste directement `cycle_ascending` (pas seulement le niveau du
  sinewave, déjà fait dans COUVERTURE_ENSEIGNEMENTS.md section P0) sur
  données RÉELLES BTC/ETH/BNB/SOL, H4 et D1, tout l'historique disponible,
  avec le calcul causal actuellement en production.

Conclusion (cf. PLAN.md occurrence #3 et code/test_proxy_v2.py pour le
résumé définitif) : la divergence persiste à l'identique sur synthétique pur
(causal ou batch, avec ou sans un léger bruit gaussien), mais NE SE
REPRODUIT PAS sur données réelles (corrélations proches de zéro, signes
incohérents d'un actif à l'autre, aucune significative après ajustement
implicite pour les tests multiples) — l'hypothèse posée à l'origine est
CONFIRMÉE : la sinusoïde synthétique idéalisée n'est pas un terrain de test
représentatif pour cette condition dérivée. Voir
`cycle_ascending_robustness.py` pour la démonstration complémentaire de
POURQUOI (l'artefact ne s'estompe qu'à un niveau de bruit/mélange de
fréquences bien supérieur à ce qu'un simple bruit gaussien standard capture).
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats

from emile.core.proxy_v2 import compute_cycle_phase, compute_cycle_phase_causal, CYCLE_MATURE_THRESHOLD
from emile.backtests.backtest_phase2 import load_h1, resample

def cycle_ascending_from_sinewave(sinewave: np.ndarray) -> np.ndarray:
    """Reproduit EXACTEMENT la logique de add_proxy_v2_score (proxy_v2.py,
    dans add_proxy_v2_score), appliquée à un sinewave déjà calculé — pour
    pouvoir la tester aussi bien sur sinusoïde synthétique que sur prix réels
    sans dépendre d'un DataFrame OHLC complet."""
    sinewave_prev = np.roll(sinewave, 1)
    sinewave_prev[0] = sinewave[0]
    return sinewave > sinewave_prev

def cycle_favorable_from_sinewave(sinewave: np.ndarray) -> np.ndarray:
    ascending = cycle_ascending_from_sinewave(sinewave)
    not_exhausted = np.abs(sinewave) < CYCLE_MATURE_THRESHOLD
    return ascending & not_exhausted

def synthetic_pure_sine(n=2000, period=40, amplitude=5.0, seed=0):
    """Sinusoïde PURE, sans bruit (contrairement à _synthetic_cyclical_series
    de test_proxy_v2.py, qui ajoute noise=0.05) — la variante "idéalisée"
    dont l'hypothèse en question. Variante bruitée incluse pour référence."""
    t = np.arange(n)
    close_pure = 100 + amplitude * np.sin(2 * np.pi * t / period)
    rng = np.random.default_rng(seed)
    close_noisy = close_pure + rng.normal(0, 0.05, n)
    return pd.Series(close_pure), pd.Series(close_noisy)

def corr_report(label, x, y):
    valid = ~(np.isnan(x) | np.isnan(y))
    x, y = x[valid], y[valid]
    if x.std() == 0 or y.std() == 0 or len(x) < 10:
        print(f"{label}: n={len(x)} — dégénéré (pas de variance), corrélation non définie")
        return None
    r, p = stats.pearsonr(x, y)
    print(f"{label}: n={len(x)}, r={r:+.4f}, p={p:.3g}")
    return r, p, len(x)

def ttest_report(label, group_true, group_false):
    if len(group_true) < 2 or len(group_false) < 2:
        print(f"{label}: échantillon insuffisant pour un test t (n_true={len(group_true)}, n_false={len(group_false)})")
        return None
    t, p = stats.ttest_ind(group_true, group_false, equal_var=False)
    print(f"{label}: True n={len(group_true)} mean={group_true.mean():+.5f} | "
          f"False n={len(group_false)} mean={group_false.mean():+.5f} | t={t:.3f} p={p:.3g}")
    return t, p

def main():
    print("=" * 100)
    print("PARTIE 1 — Reproduction de la mesure originale (sinusoïde synthétique PURE)")
    print("=" * 100)

    close_pure, close_noisy = synthetic_pure_sine()
    synth_rows = []

    for label, close_syn in [("pure", close_pure), ("bruit_0.05", close_noisy)]:
        print(f"\n--- Sinusoïde {label} ---")
        fwd_return = close_syn.shift(-1).values / close_syn.values - 1.0

        for fn_name, fn, warmup in [("batch", compute_cycle_phase, 20),
                                     ("causal", compute_cycle_phase_causal, 150)]:
            sinewave = fn(close_syn)
            ascending = cycle_ascending_from_sinewave(sinewave)
            favorable = cycle_favorable_from_sinewave(sinewave)

            valid = np.zeros(len(close_syn), dtype=bool)
            valid[warmup:] = True
            valid &= ~np.isnan(fwd_return)

            print(f"  [{fn_name}]")
            r_level = corr_report("    niveau sinewave vs rendement futur", sinewave[valid], fwd_return[valid])
            r_asc = corr_report("    cycle_ascending (0/1) vs rendement futur", ascending[valid].astype(float), fwd_return[valid])
            asc_v, fwd_v, fav_v = ascending[valid], fwd_return[valid], favorable[valid]
            t_asc = ttest_report("    cycle_ascending True vs False (rendement moyen)", fwd_v[asc_v], fwd_v[~asc_v])
            t_fav = ttest_report("    cycle_favorable True vs False (rendement moyen)", fwd_v[fav_v], fwd_v[~fav_v])

            synth_rows.append({
                "serie": label, "calcul": fn_name,
                "r_level": r_level[0] if r_level else np.nan, "p_level": r_level[1] if r_level else np.nan,
                "r_ascending": r_asc[0] if r_asc else np.nan, "p_ascending": r_asc[1] if r_asc else np.nan,
                "t_ascending": t_asc[0] if t_asc else np.nan, "p_ascending_ttest": t_asc[1] if t_asc else np.nan,
                "t_favorable": t_fav[0] if t_fav else np.nan, "p_favorable_ttest": t_fav[1] if t_fav else np.nan,
            })

    pd.DataFrame(synth_rows).to_csv("../cycle_ascending_synthetic.csv", index=False)

    print()
    print("=" * 100)
    print("PARTIE 2 — Test direct de cycle_ascending sur DONNÉES RÉELLES (BTC/ETH/BNB/SOL, H4/D1)")
    print("=" * 100)

    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []

    for symbol in symbols:
        h1 = load_h1(symbol)
        for tf_name, rule in [("H4", "4h"), ("D1", "1D")]:
            df = resample(h1, rule)
            close = df["close"]
            sinewave = compute_cycle_phase_causal(close)  # version en production
            ascending = cycle_ascending_from_sinewave(sinewave)
            favorable = cycle_favorable_from_sinewave(sinewave)
            fwd_return = close.shift(-1).values / close.values - 1.0

            warmup = 150 + 5
            valid = np.zeros(len(close), dtype=bool)
            valid[warmup:] = True
            valid &= ~np.isnan(fwd_return)

            asc_v, fav_v, fwd_v = ascending[valid], favorable[valid], fwd_return[valid]

            print(f"\n--- {symbol} {tf_name} (n_bars={len(df)}, n_valid={valid.sum()}) ---")
            r_level = corr_report("  niveau sinewave vs rendement futur (référence, cf. COUVERTURE_ENSEIGNEMENTS.md P0)", sinewave[valid], fwd_return[valid])
            r_asc = corr_report("  cycle_ascending (0/1) vs rendement futur", asc_v.astype(float), fwd_v)
            t_asc = ttest_report("  cycle_ascending True vs False (rendement moyen)", fwd_v[asc_v], fwd_v[~asc_v])
            t_fav = ttest_report("  cycle_favorable True vs False (rendement moyen, = signal production)", fwd_v[fav_v], fwd_v[~fav_v])

            rows.append({
                "symbol": symbol, "tf": tf_name, "n_valid": int(valid.sum()),
                "r_level": r_level[0] if r_level else np.nan,
                "p_level": r_level[1] if r_level else np.nan,
                "r_ascending": r_asc[0] if r_asc else np.nan,
                "p_ascending": r_asc[1] if r_asc else np.nan,
                "mean_ret_ascending_true": fwd_v[asc_v].mean() if asc_v.any() else np.nan,
                "mean_ret_ascending_false": fwd_v[~asc_v].mean() if (~asc_v).any() else np.nan,
                "t_ascending": t_asc[0] if t_asc else np.nan,
                "p_ascending_ttest": t_asc[1] if t_asc else np.nan,
                "mean_ret_favorable_true": fwd_v[fav_v].mean() if fav_v.any() else np.nan,
                "mean_ret_favorable_false": fwd_v[~fav_v].mean() if (~fav_v).any() else np.nan,
                "t_favorable": t_fav[0] if t_fav else np.nan,
                "p_favorable_ttest": t_fav[1] if t_fav else np.nan,
            })

    res = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print("\n\n=== TABLEAU RÉCAPITULATIF (réel, cycle_ascending isolé) ===")
    print(res[["symbol", "tf", "n_valid", "r_ascending", "p_ascending", "t_ascending", "p_ascending_ttest"]].to_string(index=False))
    print("\n=== TABLEAU RÉCAPITULATIF (réel, cycle_favorable = signal production) ===")
    print(res[["symbol", "tf", "n_valid", "mean_ret_favorable_true", "mean_ret_favorable_false", "t_favorable", "p_favorable_ttest"]].to_string(index=False))

    res.to_csv("../cycle_ascending_real_data.csv", index=False)
    print("\nSauvegardé : cycle_ascending_synthetic.csv, cycle_ascending_real_data.csv")

if __name__ == "__main__":
    main()
