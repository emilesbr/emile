"""
Réserve P0-bis (COUVERTURE_ENSEIGNEMENTS.md ⚠️, PLAN.md occurrence #4) —
script ponctuel qui compare v5/v6/v7 AVANT/APRÈS le passage de
`compute_ascending_lows`/`n_borders` sur la version causale, en partant de
l'état déjà causal pour le cycle (P0, `phase2_v{5,6,7}_*causal_results.csv`)
— donc "cycle causal + structure batch" (référence, déjà trackée) vs
"cycle causal + structure ÉGALEMENT causale" (nouveau, ce script régénère
les fichiers `phase2_v{5,6,7}_*structure_causal_results.csv` en relançant
les moteurs avec le code de production actuel).

Ne fait partie d'aucun pipeline de production — script d'analyse ponctuel,
comme `cycle_causal_window_selection.py`/`ablation_test_cycle.py`.
"""
import sys
import pandas as pd

sys.path.insert(0, ".")


def regenerate_results():
    """ATTENTION : v5/v6/v7 `main()` écrivent respectivement dans
    `phase2_v5_results.csv`, `phase2_v6_regime_results.csv` et
    `phase2_v7_mtf_results.csv` — CES DEUX DERNIERS SONT DES FICHIERS
    TRACKÉS (référence batch historique). On les sauvegarde donc AVANT
    d'appeler main() et on les restaure juste après avoir copié le résultat
    vers le nom dédié `*_structure_causal_results.csv`, pour ne jamais les
    écraser silencieusement (erreur commise une fois pendant la
    construction de ce script — corrigée avant tout commit)."""
    import shutil
    import os
    import backtest_phase2_v5 as v5
    import backtest_phase2_v6 as v6
    import backtest_phase2_v7 as v7

    TRACKED = ["phase2_v6_regime_results.csv", "phase2_v7_mtf_results.csv"]
    backups = {}
    for f in TRACKED:
        if os.path.exists(f):
            backups[f] = f + ".bak_before_replay"
            shutil.copy(f, backups[f])

    try:
        v5.main()
        pd.read_csv("phase2_v5_results.csv").to_csv("phase2_v5_structure_causal_results.csv", index=False)
        os.remove("phase2_v5_results.csv")  # jamais tracké : pas de référence à préserver, on nettoie

        v6.main()
        pd.read_csv("phase2_v6_regime_results.csv").to_csv("phase2_v6_regime_structure_causal_results.csv", index=False)

        v7.main()
        pd.read_csv("phase2_v7_mtf_results.csv").to_csv("phase2_v7_mtf_structure_causal_results.csv", index=False)
    finally:
        for f, backup in backups.items():
            shutil.move(backup, f)


def compare(old_path, new_path, keys, label):
    old = pd.read_csv(old_path)
    new = pd.read_csv(new_path)
    merged = old.merge(new, on=keys, suffixes=("_batch_struct", "_causal_struct"))
    merged["d_return"] = merged["total_return_%_causal_struct"] - merged["total_return_%_batch_struct"]
    merged["d_winrate"] = merged["win_rate_%_causal_struct"] - merged["win_rate_%_batch_struct"]
    merged["d_trades"] = merged["n_trades_causal_struct"] - merged["n_trades_batch_struct"]
    merged["sign_flip"] = (merged["total_return_%_batch_struct"] > 0) != (merged["total_return_%_causal_struct"] > 0)

    print(f"--- {label} ({len(merged)} configs) ---")
    if "tf" in merged.columns:
        for tf, g in merged.groupby("tf"):
            print(f"  {tf}: sign flips {g['sign_flip'].sum()}/{len(g)} | "
                  f"moy retour batch={g['total_return_%_batch_struct'].mean():.1f}% "
                  f"causal={g['total_return_%_causal_struct'].mean():.1f}% | "
                  f"moy winrate batch={g['win_rate_%_batch_struct'].mean():.2f} "
                  f"causal={g['win_rate_%_causal_struct'].mean():.2f}")
    else:  # v7 : H4 uniquement, pas de colonne tf
        print(f"  sign flips {merged['sign_flip'].sum()}/{len(merged)} | "
              f"moy retour batch={merged['total_return_%_batch_struct'].mean():.1f}% "
              f"causal={merged['total_return_%_causal_struct'].mean():.1f}% | "
              f"moy winrate batch={merged['win_rate_%_batch_struct'].mean():.2f} "
              f"causal={merged['win_rate_%_causal_struct'].mean():.2f}")
    merged.to_csv(f"{label}_comparison.csv", index=False)
    return merged


def main():
    regenerate_results()
    compare("phase2_v5_causal_results.csv", "phase2_v5_structure_causal_results.csv",
            ["symbol", "tf", "profile"], "v5_structure_causal_vs_batch")
    compare("phase2_v6_regime_causal_results.csv", "phase2_v6_regime_structure_causal_results.csv",
            ["symbol", "tf", "profile", "gate"], "v6_structure_causal_vs_batch")
    compare("phase2_v7_mtf_causal_results.csv", "phase2_v7_mtf_structure_causal_results.csv",
            ["symbol", "profile", "gate", "stop"], "v7_structure_causal_vs_batch")


if __name__ == "__main__":
    main()
