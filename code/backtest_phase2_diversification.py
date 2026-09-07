"""
Phase 2 diversification — compare UN SEUL pattern (référence, `run_v7` non
modifié) contre la diversification "1%+1%" (`diversification.run_diversified`,
Pattern A `proxy_v2` + Pattern B `cluster_technique`) sur BTC/ETH/BNB/SOL.
`PLAN.md` backlog item 7 (cf. `code/diversification.py` pour toutes les
hypothèses d'implémentation détaillées, H1-H6).

Choix de la référence (documenté, pas une évidence) : le principe même de la
règle "1%+1%" (source #16, `TRADING_LESSONS_CLUSTERS_PRIX.md`) est de
diviser un BUDGET DE RISQUE TOTAL entre deux patterns plutôt que de le
concentrer sur un seul ("Logique du dénominateur"). Pour une comparaison
apples-to-apples du DRAWDOWN (pas juste du rendement brut), la référence la
plus honnête est donc UN SEUL pattern (proxy_v2/Pattern A) risquant LE MÊME
BUDGET TOTAL que les deux patterns diversifiés réunis :
  - 1% + 1% = 2% de risque total -> référence = `run_v7(..., "MODERE")`
    (PROFILES_V4["MODERE"]["risk_pct"] = 0.02, correspondance EXACTE, pas
    approximée)
Une seconde référence, à titre de contrôle secondaire (PAS le point
principal de comparaison), est ajoutée par transparence : `run_v7(...,
"FAIBLE")` (risk_pct=0.01, MÊME risque qu'UNE SEULE jambe de la
diversification) -- utile pour distinguer "l'edge vient-il du 2ème pattern
lui-même" de "l'edge vient-il simplement d'un risk_pct différent".

VÉRIFICATION EMPIRIQUE FAITE AVANT DE CONCLURE (discipline "mode ingénieur
senior", `PLAN.md`) -- CONFUSION À NE PAS COMMETTRE : `run_diversified`
(Pattern A y compris) ne pyramidalise JAMAIS (H4 de `diversification.py`,
1 seule tranche par pattern), alors que la référence `run_v7` pyramidalise
(jusqu'à 3 tranches, déjà documenté ailleurs dans ce projet comme "le
principal moteur de rendement", cf. `backtest_phase2_fib.py`). Comparer
directement "référence `run_v7` (avec pyramide)" à "diversifié (sans
pyramide)" mélangerait donc deux effets et attribuerait à tort au 2e
pattern une baisse de drawdown venant en réalité surtout de la suppression
de la pyramidalisation. Une 3e variante (`enable_pattern_b=False`, Pattern
A SEUL mais DANS LE MÊME moteur sans pyramide) isole donc l'effet MARGINAL
réel de l'ajout du Cluster Technique, indépendamment de cet effet confondu.

Ne touche à AUCUN fichier de production existant (même discipline que
`backtest_phase2_fib.py`) : réutilise `run_v7`/`PROFILES_V4` de
`backtest_phase2_v7.py`, `run_diversified` de `diversification.py`.
"""
import pandas as pd
import sys
sys.path.insert(0, ".")
from backtest_phase2 import load_h1, resample
from backtest_phase2_v7 import run_v7
from diversification import run_diversified, RISK_PCT_PATTERN_A, RISK_PCT_PATTERN_B


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")

        ref_2pct = run_v7(h4.copy(), d1.copy(), "MODERE", use_mtf_gate=True, use_mtf_stop=False)
        ref_1pct = run_v7(h4.copy(), d1.copy(), "FAIBLE", use_mtf_gate=True, use_mtf_stop=False)
        # Isole l'effet marginal du Cluster Technique : MÊME moteur (sans
        # pyramide) que le diversifié, Pattern B désactivé -- cf. docstring
        # de tête pour la confusion que cette variante permet d'éviter.
        pattern_a_alone_no_pyramid = run_diversified(h4.copy(), d1.copy(), management_profile="MODERE",
                                                      use_mtf_gate=True, enable_pattern_b=False)
        div = run_diversified(h4.copy(), d1.copy(), management_profile="MODERE", use_mtf_gate=True)

        rows.append({
            "symbol": symbol, "variant": "reference_1_pattern_2pct (MODERE, proxy_v2 seul)",
            "n_trades": ref_2pct["n_trades"], "max_dd_%": ref_2pct["max_dd_%"],
            "total_return_%": ref_2pct["total_return_%"], "win_rate_%": ref_2pct["win_rate_%"],
            "profit_factor": ref_2pct["profit_factor"],
        })
        rows.append({
            "symbol": symbol, "variant": "reference_1_pattern_1pct (FAIBLE, proxy_v2 seul, controle secondaire)",
            "n_trades": ref_1pct["n_trades"], "max_dd_%": ref_1pct["max_dd_%"],
            "total_return_%": ref_1pct["total_return_%"], "win_rate_%": ref_1pct["win_rate_%"],
            "profit_factor": ref_1pct["profit_factor"],
        })
        rows.append({
            "symbol": symbol,
            "variant": "pattern_a_seul_sans_pyramide_1pct (meme moteur que diversifie, Pattern B desactive)",
            "n_trades": pattern_a_alone_no_pyramid["n_trades"], "max_dd_%": pattern_a_alone_no_pyramid["max_dd_%"],
            "total_return_%": pattern_a_alone_no_pyramid["total_return_%"],
            "win_rate_%": pattern_a_alone_no_pyramid["win_rate_%"],
            "profit_factor": pattern_a_alone_no_pyramid["profit_factor"],
            "n_trades_pattern_a": pattern_a_alone_no_pyramid["n_trades_pattern_a"],
            "n_trades_pattern_b": pattern_a_alone_no_pyramid["n_trades_pattern_b"],
        })
        rows.append({
            "symbol": symbol, "variant": "diversifie_1pct_plus_1pct (proxy_v2 + cluster_technique)",
            "n_trades": div["n_trades"], "max_dd_%": div["max_dd_%"],
            "total_return_%": div["total_return_%"], "win_rate_%": div["win_rate_%"],
            "profit_factor": div["profit_factor"],
            "n_trades_pattern_a": div["n_trades_pattern_a"], "n_trades_pattern_b": div["n_trades_pattern_b"],
        })

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_diversification_results.csv", index=False)

    def _dd(symbol, prefix):
        return result[(result.symbol == symbol) & (result.variant.str.startswith(prefix))]["max_dd_%"].iloc[0]

    print("\n--- Comparaison NAÏVE (mélange 2 effets, cf. docstring de tête) : "
          "diversifié vs référence run_v7 2% (AVEC pyramide) ---")
    deltas_naifs = []
    for symbol in symbols:
        dd_ref, dd_div = _dd(symbol, "reference_1_pattern_2pct"), _dd(symbol, "diversifie")
        delta = dd_div - dd_ref
        deltas_naifs.append(delta)
        verdict = "REDUIT" if delta > 0 else ("INCHANGE" if delta == 0 else "AGGRAVE")
        print(f"  {symbol:<10} référence={dd_ref:>6.1f}%  diversifié={dd_div:>6.1f}%  delta={delta:>+6.1f}pt  -> drawdown {verdict}")

    print("\n--- Comparaison ISOLÉE (effet MARGINAL réel du Cluster Technique, MÊME moteur "
          "sans pyramide des deux côtés) : diversifié vs Pattern A seul (1%, sans pyramide) ---")
    deltas_isoles = []
    for symbol in symbols:
        dd_a_alone, dd_div = _dd(symbol, "pattern_a_seul"), _dd(symbol, "diversifie")
        delta = dd_div - dd_a_alone
        deltas_isoles.append(delta)
        verdict = "REDUIT" if delta > 0 else ("INCHANGE" if delta == 0 else "AGGRAVE")
        print(f"  {symbol:<10} pattern_A_seul={dd_a_alone:>6.1f}%  diversifié={dd_div:>6.1f}%  delta={delta:>+6.1f}pt  -> drawdown {verdict}")

    print(
        "\nCONSTAT HONNÊTE (à ne pas maquiller) : la comparaison NAÏVE ci-dessus montre une "
        f"réduction de drawdown massive (+{min(deltas_naifs):.1f} à +{max(deltas_naifs):.1f}pt "
        "selon l'actif), mais elle mélange 2 effets. Une fois la pyramidalisation neutralisée "
        "des DEUX côtés (comparaison ISOLÉE), l'effet MARGINAL réel de l'ajout du Cluster "
        f"Technique est {'/'.join(f'{d:+.1f}' for d in deltas_isoles)} pt selon l'actif "
        "(BTC/ETH/BNB/SOL) -- MIXTE et proche de zéro (2/4 actifs légèrement réduits, 2/4 "
        "légèrement aggravés), PAS une réduction consistante. La quasi-totalité de la "
        "réduction de drawdown observée dans la comparaison naïve provient donc de la "
        "suppression de la pyramidalisation (déjà documentée ailleurs dans ce projet comme "
        "le principal moteur de RENDEMENT -- ici on découvre qu'elle est aussi le principal "
        "moteur du DRAWDOWN), PAS de la diversification 1%+1% elle-même. Conclusion : "
        "'mitigé', pas 'résolu' -- l'implémentation est fidèle au corpus et fonctionnelle "
        "(les deux patterns tournent bien simultanément et indépendamment), mais l'avantage "
        "en drawdown promis par la source #16 pour CETTE diversification précise n'est PAS "
        "confirmé empiriquement sur BTC/ETH/BNB/SOL une fois l'effet confondu retiré."
    )


if __name__ == "__main__":
    main()
