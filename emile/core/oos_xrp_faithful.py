"""
Validation hors-échantillon (OOS) de la config FIDÈLE (`backtest_phase2_
faithful.py`) sur XRP -- sur le modèle exact de `oos_xrp_recommended.py`
(lui-même sur le modèle de `OOS_VALIDATION_CYCLE_SIGN.md` section 2,
"procédure décidée à l'avance"), pour éviter le biais rétrospectif déjà
identifié comme risque dans ce projet (`AUDIT_QUALITE_ET_CORRECTION_CYCLE.md`,
réserve méthodologique). `CONFIGURATION_RECOMMANDEE.md` section 5ter notait
ce point comme "reste ouvert" : l'OOS XRP de `faithful.py` est PLUS COMPLEXE
que celui de `recommended.py` car ce moteur a besoin de 3 niveaux de
timeframe distincts (exécution / stop UT+1 / gate UT+2), alors que XRP n'a
qu'une seule résolution disponible dans cet environnement. Ce script résout
ce problème et documente le raisonnement AVANT tout résultat chiffré.

1. DONNÉE DISPONIBLE (vérifiée AVANT toute décision de procédure)
--------------------------------------------------------------------
Même source, même vérification que `oos_xrp_recommended.py` -- refaite ici,
pas supposée : `/home/user/http-kaijin/crypto-decision-bi/01_data/02_staging/
cleaned/ohlcv_cleaned.csv` (chemin vérifié existant), filtré
`symbol == "XRPUSDT"` -> **365 lignes exactement** (`wc`/`awk` sur le CSV
brut, avant tout chargement pandas), confirmant le chiffre déjà documenté
dans `oos_xrp_recommended.py`. Aucune donnée H1/H4 pour XRP dans cet
environnement -- seule résolution disponible : **D1, 365 barres,
2025-06-03 -> 2026-06-02**.

2. LE PROBLÈME À 3 NIVEAUX, PROPRE À `faithful.py` (absent de l'OOS recommended)
--------------------------------------------------------------------------------
`run_faithful(h4, d1, weekly, profile, ...)` a besoin de 3 niveaux DISTINCTS
(contrairement à `run_recommended` qui n'en utilise que 2) :
  - `h4`     : exécution (score, ATR, n_borders, Wall Street, +Reverse)
  - `d1`     : stop cross-timeframe réel UT+1 (`ctx_support`, littéral,
               INCONDITIONNEL dans `faithful.py` -- aucun paramètre pour le
               désactiver, contrairement au gate)
  - `weekly` : gate Hebdomadaire ("UT+2 strict", décision #2 de
               `recommended.py`, reprise inchangée par `faithful.py`)

Avec UNE SEULE résolution XRP disponible (D1), il faut décaler les 3 rôles
d'un cran vers le haut par rapport à l'OOS `recommended.py` (qui, lui,
n'avait qu'un rôle "exécution" + un rôle "gate" à décaler) :
  - `h4`     -> XRP D1 (365 barres) -- le "timeframe disponible", comme dans
               l'OOS `recommended.py`
  - `d1`     -> XRP Hebdomadaire, resamplé depuis le D1 XRP (**53 barres**,
               vérifié : `resample(xrp_d1, "W")` -> 53 lignes, IDENTIQUE au
               chiffre déjà mesuré dans `oos_xrp_recommended.py` puisque
               c'est le même XRP D1 source)
  - `weekly` -> XRP Mensuel, resamplé depuis le D1 XRP (**13 barres**,
               vérifié : `resample(xrp_d1, "ME")` -> 13 lignes)

3. PROCÉDURE DÉCIDÉE À L'AVANCE (avant tout calcul de performance)
--------------------------------------------------------------------
Deux décisions séparées, sur le stop (UT+1, devenu Hebdomadaire) et sur le
gate (UT+2, devenu Mensuel) -- prises sur la seule base d'une contrainte de
longueur de série et de ce que le code calcule réellement à partir de
chaque niveau, JAMAIS en regardant un résultat de performance :

a) GATE (Mensuel, 13 barres) -- DÉSACTIVÉ (`use_mtf_gate=False`)
   `faithful.py` N'AVAIT PAS de paramètre pour neutraliser ce gate
   (contrairement à `recommended.py` qui a déjà `use_mtf_gate=False`) --
   AJOUTÉ ce cycle à `backtest_phase2_faithful.py`, de façon STRICTEMENT
   ADDITIVE (nouveau paramètre optionnel, défaut `True` = comportement
   inchangé pour tous les appelants existants, dont `unified_protocol.py` ;
   preuve de non-régression : diff + suite de tests 19/19 verts, section 4
   ci-dessous). Deux raisons cumulatives, chacune suffisante seule, vérifiées
   dans le code AVANT d'écrire cette section :
     - `add_proxy_v2_score` (`proxy_v2.py::compute_cycle_phase_causal`,
       CYCLE_CAUSAL_WINDOW=150) a le même garde-fou déjà identifié dans
       `oos_xrp_recommended.py` : `if n >= window: ... ` SANS `else`, sortie
       initialisée à des ZÉROS. 13 barres Mensuelles << 150 -> composante
       cycle du `gate_score` forcée à zéro sur toute la série (silencieux,
       pas une erreur).
     - `regime_classifier.py::add_regime` calcule les seuils adaptatifs
       (`squeeze_thresh`/`excess_thresh`, utilisés pour `gate_regime`) via
       `rolling(PCTL_WINDOW=250).quantile(...)` -- **250 barres**, encore
       plus strict que les deux points ci-dessus. Avec 13 barres Mensuelles,
       ces seuils sont NaN sur TOUTE la série (rolling(250) sur 13 lignes
       ne peut jamais produire une fenêtre pleine) -- `gate_regime` ne
       distinguerait donc jamais correctement "EXCES" du reste, un gate
       structurellement non calculable, pas seulement bruité.
   Un gate calculé sur seulement 13 bougies serait donc un gate cassé de
   DEUX façons indépendantes (cycle forcé à zéro ET seuils de régime
   NaN), pire encore que le cas déjà documenté (Hebdomadaire, 53 barres)
   de l'OOS `recommended.py`. **Décision retenue, avant tout résultat** :
   le gate Mensuel est désactivé pour cet OOS. Conséquence assumée :
   cet OOS valide le signal + le stop UT+1 réel + l'abstention Wall Street +
   le risk management + le position engine de la config fidèle, PAS le
   composant gate MTF (décision #2), structurellement intestable ici --
   exactement la même limite déjà actée pour l'OOS `recommended.py`,
   transposée d'un cran.

b) STOP (Hebdomadaire, 53 barres) -- CONSERVÉ ACTIF SANS CONDITION
   Contrairement au gate, `faithful.py` ne fournit ET NE DOIT PAS fournir de
   paramètre pour désactiver ce stop : c'est une règle LITTÉRALE du corpus
   (`TRADING_LESSONS_BREAKOUT_RATIO11.md` #12), pas une hypothèse
   d'implémentation -- le désactiver ici PARCE QUE la donnée est courte
   reproduirait exactement le raisonnement interdit par ce projet ("la
   performance/la commodité ne décide jamais d'utiliser ou non l'IP de
   Philippe"). Aucun nouveau paramètre n'est donc ajouté pour ce rôle.
   Limite honnêtement documentée, PAS corrigée ni masquée (cf. section 5) :
   `ctx_support` (le niveau de stop) = `ema_slow(EMA_SLOW=55) - 2*ATR`,
   calculé DIRECTEMENT sur le niveau Hebdomadaire (53 barres) -- 53 < 55,
   l'EMA n'a donc pas atteint son régime stationnaire au sens strict.
   Différence importante avec le gate ci-dessus, vérifiée avant d'écrire
   cette phrase : `ctx_support` ne dépend NI de la fenêtre cycle (150) NI
   des seuils de régime (250) -- seulement de l'EMA(55), qui produit une
   valeur DÉGRADÉE (moins d'historique que l'idéal) mais PAS un artefact
   catégoriquement cassé comme les zéros forcés du cycle ou les seuils NaN
   du régime. C'est une dégradation continue, pas un mode de défaillance
   binaire -- ce qui justifie de la documenter comme limite plutôt que de
   l'utiliser comme motif pour désactiver une règle littérale.

Les 4 profils (FAIBLE/MODERE/AGRESSIF/TRES_AGRESSIF) sont testés, pas
seulement MODERE, par souci de complétude -- décidé avant résultat. Aucune
itération après coup : ce script n'a été exécuté qu'une seule fois et le
résultat ci-dessous (section 6, à mettre à jour par quiconque le relance)
est rapporté tel quel, qu'il confirme ou non les attentes.

4. NON-RÉGRESSION DE `backtest_phase2_faithful.py` (avant d'utiliser le nouveau paramètre)
--------------------------------------------------------------------------------------------
`use_mtf_gate` a été ajouté à `_prepare_features`/`run_faithful` avec une
valeur par défaut `True` qui reproduit EXACTEMENT l'ancien code (même appel
`attach_multi_context(h4, [("D1", d1), ("W", weekly)], ...)`, mêmes clés
`gate_score`/`gate_regime` venant de `ctx["W"]`) -- diff strictement additif
(aucune ligne existante supprimée, seulement des branches `if use_mtf_gate`
ajoutées). Suite de tests relancée IMMÉDIATEMENT après la modification :
19/19 fichiers `test_*.py` verts, dont `test_backtest_phase2_faithful.py`
(5/5, inchangé) et `test_unified_protocol.py` (6/6, inchangé -- ce module
importe `run_faithful` sans jamais passer `use_mtf_gate`, donc invisible à
son comportement).

5. LIMITES À NE PAS MINIMISER (mêmes catégories que les OOS précédents)
--------------------------------------------------------------------------
- Un seul actif, une seule fenêtre d'un an, D1 comme "exécution" -- ne
  couvre pas le H4 (timeframe de référence de ce projet), par construction.
- Le composant gate MTF (Mensuel ici) N'EST PAS testé (cf. section 3a) --
  limite structurelle de donnée, pas un choix de méthode.
- Le stop UT+1 (Hebdomadaire, 53 barres) tourne sur un historique plus court
  que sa fenêtre EMA(55) nominale -- dégradation documentée en section 3b,
  pas corrigée (aucun paramètre pour la désactiver n'existe ni ne devrait
  exister pour une règle littérale).
- Échantillon potentiellement très mince sur un an de D1 pour un seul actif
  -- un résultat honnête peut très bien être "trop peu de trades pour
  conclure quoi que ce soit", rapporté tel quel, pas maquillé.
- Comme pour `recommended.py`, ceci ne valide qu'UNE combinaison
  actif/fenêtre -- pas une preuve de robustesse générale du moteur fidèle.

6. RÉSULTAT (rempli par l'exécution unique du script, pas retouché après coup)
--------------------------------------------------------------------------------
Voir `oos_xrp_faithful_results.csv` et la sortie console -- rapportée telle
quelle dans le rapport de tâche, y compris si elle est décevante.
"""
import pandas as pd
import sys

from emile.backtests.backtest_phase2 import resample
from emile.backtests.backtest_phase2_v7 import PROFILES_V4
from emile.backtests.backtest_phase2_faithful import run_faithful

XRP_CSV = "/home/user/http-kaijin/crypto-decision-bi/01_data/02_staging/cleaned/ohlcv_cleaned.csv"

def load_xrp_d1() -> pd.DataFrame:
    df = pd.read_csv(XRP_CSV)
    df = df[df["symbol"] == "XRPUSDT"].copy()
    df["date"] = pd.to_datetime(df["open_time_dt"])
    df = df.rename(columns={
        "open_price": "open", "high_price": "high", "low_price": "low", "close_price": "close",
    })
    return df.sort_values("date")[["date", "open", "high", "low", "close"]].reset_index(drop=True)

def main():
    xrp_d1 = load_xrp_d1()
    print(f"XRP D1 (exécution) : {len(xrp_d1)} barres, {xrp_d1['date'].min()} -> {xrp_d1['date'].max()}")

    # Stop UT+1 -- Hebdomadaire dérivé du D1 XRP (littéral, INCONDITIONNEL,
    # cf. section 3b : conservé actif malgré la longueur limitée).
    xrp_weekly = resample(xrp_d1, "W")
    print(f"XRP Hebdomadaire (stop UT+1, actif sans condition) : {len(xrp_weekly)} barres")

    # Gate UT+2 -- Mensuel dérivé du D1 XRP. Passé tel quel à `run_faithful`
    # (argument requis par la signature) mais son contenu n'est JAMAIS
    # exploité côté calcul puisque `use_mtf_gate=False` (cf. section 3a) --
    # `_prepare_features` saute même son `prepare()` dans ce cas.
    xrp_monthly = resample(xrp_d1, "ME")
    print(f"XRP Mensuel (gate UT+2, désactivé -- use_mtf_gate=False) : {len(xrp_monthly)} barres")

    rows = []
    for profile in PROFILES_V4:
        res = run_faithful(
            xrp_d1.copy(), xrp_weekly.copy(), xrp_monthly.copy(), profile,
            use_mtf_gate=False,
        )
        rows.append({
            "symbol": "XRPUSDT", "timeframe_exec": "D1", "timeframe_stop": "Hebdomadaire (UT+1, actif)",
            "timeframe_gate": "Mensuel (UT+2, DESACTIVE -- donnee insuffisante)",
            "profile": profile, **res,
        })

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("oos_xrp_faithful_results.csv", index=False)

if __name__ == "__main__":
    main()
