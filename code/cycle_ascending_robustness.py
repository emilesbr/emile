"""
Complément à `cycle_ascending_investigation.py` (occurrence #3, PLAN.md) :
identifie à quel point de bruit/mélange de fréquences l'artefact synthétique
(cycle_ascending fortement anti-corrélée au rendement futur sur sinusoïde
pure) s'estompe — pour expliquer POURQUOI les données réelles ne le
reproduisent pas, pas seulement CONSTATER qu'elles ne le reproduisent pas.

Deux axes, sans bruit gaussien pur d'abord puis combinés :
  A. Bruit gaussien croissant sur une sinusoïde à une seule fréquence.
  B. Mélange de plusieurs fréquences (harmoniques superposées), sans bruit.
  C. Combinaison des deux.

Conclusion (cf. cycle_ascending_investigation.py et PLAN.md occurrence #3
pour le résumé complet) : l'artefact ne s'efface significativement qu'à un
ratio bruit/amplitude d'environ 3-4x (bien au-delà du bruit=0.05 utilisé par
défaut dans test_proxy_v2.py, qui ne change presque rien) ou par un mélange
de fréquences à très forte pondération du bruit — un niveau de "désordre"
largement supérieur à ce qu'un ajout de bruit gaussien standard sur une
sinusoïde capture d'ordinaire. Cohérent avec le fait que les prix crypto
réels sont dominés par une variation non cyclique (tendance, sauts,
non-stationnarité, changements de régime) plutôt que par un signal
sinusoïdal propre à une ou plusieurs fréquences fixes — la sinusoïde
synthétique, même bruitée légèrement ou multi-fréquence modérément, reste
un terrain de test structurellement différent des séries réelles.
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, ".")
from proxy_v2 import compute_cycle_phase_causal


def cycle_ascending_from_sinewave(sinewave):
    sinewave_prev = np.roll(sinewave, 1)
    sinewave_prev[0] = sinewave[0]
    return sinewave > sinewave_prev


def measure(close, warmup=150):
    fwd_return = close.shift(-1).values / close.values - 1.0
    sinewave = compute_cycle_phase_causal(close)
    ascending = cycle_ascending_from_sinewave(sinewave)
    valid = np.zeros(len(close), dtype=bool)
    valid[warmup:] = True
    valid &= ~np.isnan(fwd_return)
    x, y = ascending[valid].astype(float), fwd_return[valid]
    if x.std() == 0:
        return np.nan, np.nan, valid.sum()
    r, p = stats.pearsonr(x, y)
    return r, p, valid.sum()


def main():
    n = 2000
    t = np.arange(n)
    period, amplitude = 40, 5.0
    rows = []

    print("=== A. Bruit croissant (une seule fréquence, période=40, amplitude=5) ===")
    for noise_std in [0.0, 0.05, 0.25, 1.0, 2.5, 5.0, 10.0, 20.0]:
        rng = np.random.default_rng(0)
        close = pd.Series(100 + amplitude * np.sin(2 * np.pi * t / period) + rng.normal(0, noise_std, n))
        r, p, n_obs = measure(close)
        ratio = noise_std / amplitude
        print(f"  noise_std={noise_std:6.2f} (bruit/amplitude={ratio:5.2f}x)  r_ascending={r:+.4f}  p={p:.3g}  n={n_obs}")
        rows.append({"axe": "A_bruit", "config": f"noise_std={noise_std}", "bruit_sur_amplitude": ratio, "r_ascending": r, "p_ascending": p, "n": n_obs})

    print("\n=== B. Mélange de fréquences (sans bruit gaussien) ===")
    configs_b = [
        ("1 fréquence (période=40)", [(40, 5.0)]),
        ("2 fréquences proches (40+55, amplitudes égales)", [(40, 5.0), (55, 5.0)]),
        ("2 fréquences éloignées (40+200, amplitudes égales)", [(40, 5.0), (200, 5.0)]),
        ("3 fréquences (40+90+250, amplitudes décroissantes)", [(40, 5.0), (90, 3.0), (250, 1.5)]),
        ("5 fréquences (multi-échelle)", [(20, 2.0), (40, 4.0), (90, 3.0), (180, 2.0), (400, 1.0)]),
    ]
    for label, harmonics in configs_b:
        close_vals = 100 + sum(a * np.sin(2 * np.pi * t / p) for p, a in harmonics)
        close = pd.Series(close_vals)
        r, p, n_obs = measure(close)
        print(f"  {label:55s} r_ascending={r:+.4f}  p={p:.3g}  n={n_obs}")
        rows.append({"axe": "B_frequences", "config": label, "bruit_sur_amplitude": 0.0, "r_ascending": r, "p_ascending": p, "n": n_obs})

    print("\n=== C. Bruit + mélange de fréquences combinés ===")
    configs_c = [
        ("2 fréquences + bruit modéré", [(40, 5.0), (90, 3.0)], 1.0),
        ("3 fréquences + bruit modéré", [(40, 5.0), (90, 3.0), (250, 1.5)], 1.0),
        ("5 fréquences + bruit réaliste", [(20, 2.0), (40, 4.0), (90, 3.0), (180, 2.0), (400, 1.0)], 2.0),
    ]
    for label, harmonics, noise_std in configs_c:
        rng = np.random.default_rng(1)
        close_vals = 100 + sum(a * np.sin(2 * np.pi * t / p) for p, a in harmonics) + rng.normal(0, noise_std, n)
        close = pd.Series(close_vals)
        r, p, n_obs = measure(close)
        print(f"  {label:55s} r_ascending={r:+.4f}  p={p:.3g}  n={n_obs}")
        rows.append({"axe": "C_combine", "config": label, "bruit_sur_amplitude": np.nan, "r_ascending": r, "p_ascending": p, "n": n_obs})

    pd.DataFrame(rows).to_csv("../cycle_ascending_robustness.csv", index=False)
    print("\nSauvegardé : cycle_ascending_robustness.csv")


if __name__ == "__main__":
    main()
