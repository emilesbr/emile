"""
Variante d'entrée "3ème borne squeezée" -- TABLE RANGE
(`TRADING_LESSONS_PYRAMIDALISATION.md`, #15, "Patterns de pyramidalisation",
Variante 2). Item de catégorie C du backlog `PLAN.md`, traité à la
"18e application".

Citation exacte (ligne 24 de la source, vérifiée mot pour mot) :

    **Variante 2 -- 3ème borne "squeezée" (marché très volatil)** : si le
    marché explose et atteint le ratio 1:1 sans retracement préalable, la
    3ème borne théorique se situe au milieu (50%) de l'amplitude du
    mouvement -> ordre "Limite Achat" sur ce point médian. Stop loss sous le
    dernier support significatif. Le ratio 1:1 n'est pas un objectif de
    profit mais un **point de validation mathématique** du trade.

POURQUOI CE FICHIER PLUTÔT QUE `main()` DE backtest_phase2_v7.py
--------------------------------------------------------------------------
Même raison qu'à `backtest_phase2_v7_reverse.py` (précédent directement
applicable) : la boucle de `main()` dans `backtest_phase2_v7.py` compare des
dimensions MTF (gate/stop) sur les 4 profils, et son CSV
`phase2_v7_mtf_results.csv` est une série historique publiée qui doit rester
comparable ligne à ligne. La variante mesurée ici est une dimension
DIFFÉRENTE (un second chemin d'ENTRÉE), et elle a en plus un axe de
sensibilité propre (la durée de vie de l'ordre, H-Squeeze-6). D'où un script
dédié, qui importe `run_v7` tel quel -- aucune duplication de moteur.

Contrairement à "+Reverse" (spécifique au seul profil Très Agressif dans
`RULES_EXTRACTION.md` §3), rien dans #15 ne restreint cette variante à un
profil : les 4 sont donc mesurés.

MÉCANISME ET HYPOTHÈSES : `code/position_engine.py`, bloc "VARIANTE D'ENTRÉE
'3ÈME BORNE SQUEEZÉE'" en tête de fichier (H-Squeeze-1..8). La seule
hypothèse libre est la durée de vie de l'ordre (H-Squeeze-6, 30 bougies =
le seul délai chiffré du corpus, `RULES_EXTRACTION.md:20`) -- d'où la
colonne `lifetime` ci-dessous, qui la fait varier 10/30/90 pour montrer la
sensibilité de la conclusion à ce choix, JAMAIS pour retenir la meilleure.

Rappel du principe du projet, appliqué ici comme partout ailleurs : la
performance mesurée ci-dessous ne remet JAMAIS en cause l'implémentation
elle-même -- un résultat nul ou décevant reste un résultat honnête à
rapporter, pas un motif pour ne pas construire un élément documenté du
corpus.
"""
import pandas as pd
import sys

from emile.backtests.backtest_phase2 import load_h1, resample
from emile.backtests.backtest_phase2_v7 import run_v7, PROFILES_V4

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        for profile in PROFILES_V4:
            base = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True,
                          use_mtf_stop=False, use_squeezed_third_border=False)
            rows.append({"symbol": symbol, "profile": profile,
                         "squeeze": "off", "lifetime": 0, **base})
            for lifetime in (10, 30, 90):
                res = run_v7(h4.copy(), d1.copy(), profile, use_mtf_gate=True,
                             use_mtf_stop=False, use_squeezed_third_border=True,
                             squeeze_lifetime=lifetime)
                rows.append({"symbol": symbol, "profile": profile,
                             "squeeze": "on", "lifetime": lifetime, **res})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_v7_squeeze_results.csv", index=False)

    # Écart isolé (un seul paramètre change entre `off` et chaque `on`).
    ref = result[result["squeeze"] == "off"].set_index(["symbol", "profile"])
    print("\n=== Effet ISOLÉ de la variante (on - off) ===")
    for lifetime in (10, 30, 90):
        cur = result[(result["squeeze"] == "on") & (result["lifetime"] == lifetime)]
        cur = cur.set_index(["symbol", "profile"])
        d_ret = (cur["total_return_%"] - ref["total_return_%"])
        d_n = (cur["n_trades"] - ref["n_trades"])
        d_dd = (cur["max_dd_%"] - ref["max_dd_%"])
        print(f"  durée de vie {lifetime:>2} bougies : "
              f"trades {d_n.sum():+d} au total sur 16 configs, "
              f"retour moyen {d_ret.mean():+.3f} pt "
              f"(min {d_ret.min():+.2f} / max {d_ret.max():+.2f}), "
              f"drawdown moyen {d_dd.mean():+.3f} pt, "
              f"configs modifiées {int((d_n != 0).sum())}/16")

if __name__ == "__main__":
    main()
