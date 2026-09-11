"""
Phase 2 UT+2 — validation multi-timeframe à N niveaux de contexte au lieu
d'un seul (backlog `PLAN.md` item 3 / `COUVERTURE_ENSEIGNEMENTS.md` ❌ "Règle
UT+2 exacte"). Généralise `attach_higher_context` de `backtest_phase2_v7.py`
(lu, JAMAIS modifié — fichier partagé avec 3 autres agents en parallèle sur
cette branche) à une liste de niveaux de contexte, toujours via la même
jointure `merge_asof` sans lookahead (dernière bougie du niveau supérieur
ENTIÈREMENT CLÔTURÉE à l'instant de la bougie d'exécution).

Règle exacte extraite du corpus — étape 1 de la tâche, PAS supposée
=====================================================================
6 sources citées dans `COUVERTURE_ENSEIGNEMENTS.md`/`TRADING_LESSONS_INDEX.md`
pour "UT+2" : #9 (`TRADING_LESSONS_MTF_SUIVI_TENDANCE.md`), #10
(`..._ZONE_ACCUMULATION.md`), #12 (`..._BREAKOUT_RATIO11.md`), #14
(`..._STRUCTURES_ALTERATIONS.md`), #15 (`..._PYRAMIDALISATION.md`), #16
(`..._CLUSTERS_PRIX.md`). Relecture précise (pas une supposition) :

- #9 : "tendance... impose... trois UT" — Référence/Contexte/Exécution.
  "Hiérarchie : nécessite validation sur 2 UT SUPÉRIEURES" mais la clause de
  transgression cite un SEUL niveau concret : *"vous ne pouvez transgresser
  la loi du range... QUE SI vous avez une tendance confirmée sur la 3ème
  unité de temps (Monthly)"* — pas "Daily ET Monthly", juste "Monthly" (donc
  2 niveaux au-dessus de l'UT tradée, Daily = UT+1 n'est pas mentionnée comme
  condition de cette clause précise).
- #10 : *"il est obligatoire de vérifier la tendance sur une unité de temps
  située DEUX DEGRÉS AU-DESSUS (ex: consulter le Mensuel pour un trade en
  Daily)"* — un seul niveau cité (2 degrés au-dessus), explicitement PAS "les
  deux niveaux immédiats". Spécifique aux trades de renversement.
- #12 : rôles DISTINCTS et non-cumulatifs par niveau — UT+1 = placement du
  stop (canal), UT+2 = confirmation/déblocage du breakeven (Ratio 1:1
  Contexte). La phrase "vérifier l'absence d'obstacles sur UT+1 ET UT+2" est
  un check d'obstacles (chemin libre), PAS une exigence que les deux niveaux
  montrent une TENDANCE alignée — un rôle différent de la clause de
  transgression de #9/#10.
- #14 : "Loi de l'Unité de Temps Supérieure" — générique ("l'unité de temps
  supérieure", singulier, pas de niveau précisé), cohérente avec #9/#10 mais
  n'ajoute pas de précision sur le nombre de niveaux.
- #15 (la plus littérale) : 3 niveaux à rôles fixes — Référence (Daily/Hebdo,
  tendance de fond), Contexte (4h, "identification des canaux... pivot
  visuel"), Exécution (Horaire, "on descend de DEUX NIVEAUX SOUS LA
  RÉFÉRENCE"). Le niveau intermédiaire (Contexte = UT+1 relatif à
  l'Exécution) sert un RÔLE DIFFÉRENT (canal/respiration), pas une 2e
  exigence de tendance alignée cumulative avec la Référence.
- #16 : même tableau que #15 (Daily→H1, "2 niveaux en dessous"), et nomme
  explicitement le rôle de l'UT+1 : "Extreme Channel (contexte de l'UT
  supérieure affiché sur l'UT de trading)" — un rôle de CANAL/STOP, tandis
  que la "Concordance Cyclique" (la condition de tendance/cycle aligné) est
  définie entre l'UT de trading et l'UT SUPÉRIEURE DE RÉFÉRENCE (2 niveaux
  au-dessus), pas l'UT+1.

**Conclusion retenue (pas une supposition)** : le corpus décrit un système
à 3 niveaux à RÔLES DISTINCTS, pas une règle cumulative "les 2 niveaux
immédiatement supérieurs doivent être alignés". Le niveau immédiatement
supérieur (D1 pour une exécution H4) garde son rôle déjà implémenté dans
`backtest_phase2_v7.py` (canal/stop "Extreme Channel", `ctx_support`) ; la
validation de TENDANCE proprement dite ("UT+2" au sens strict du corpus)
porte sur le niveau 2 crans au-dessus (Hebdomadaire pour une exécution H4),
EN SAUTANT le D1, pas en l'ajoutant en ET cumulatif. C'est le mode
`"ut2_strict"` ci-dessous, celui qui répond littéralement à la tâche.

Le mode `"d1_and_weekly"` (D1 ET Hebdo tous deux alignés) est implémenté et
mesuré EN PLUS, uniquement parce que la tâche demande explicitement la
comparaison à 3 configurations (H4 seul / H4+D1 / H4+D1+Hebdo) — mais il
FAUT être clair : ce n'est PAS la règle que le corpus décrit littéralement,
c'est une variante plus stricte (ET cumulatif) gardée à titre de comparaison
empirique, pas présentée comme "la règle UT+2".

Détail empirique non évident, vérifié avant usage (mode ingénieur senior,
point 1 — ne pas déduire, vérifier) : avec `resample()` de
`backtest_phase2.py`, une bougie Hebdomadaire ('W', ancrée dimanche,
label='right' par défaut de pandas) porte un `date` égal au dimanche
00:00:00 de la semaine qu'elle résume, et est entièrement close exactement
UN JOUR après ce `date` (comme une bougie D1), PAS sept jours après —
vérifié bit-à-bit sur BTC réel (`test_ut2.py`) et sur série synthétique
contrôlée. Utiliser `pd.Timedelta(weeks=1)` aurait été une erreur par excès
de prudence (pas un risque de lookahead, mais un retard artificiel de 6
jours dans la disponibilité du signal).

"UT+2 réservé aux trades de RENVERSEMENT, pas de CONTINUATION" — INVESTIGUÉ
(10e mobilisation multi-agents), DÉLIBÉRÉMENT PAS IMPLÉMENTÉ
=============================================================================
Bloc purement documentaire (ZÉRO comportement), placé ici parce que c'est CE
fichier qui possède le gate UT+2 ; même discipline que la note "Red Flags" en
tête de `position_engine.py` (9e application) et que la note H7 de
`trend_table.py`. Détail complet + mesures : `PLAN.md` section "10e
application" et `COUVERTURE_ENSEIGNEMENTS.md`.

Citation exacte, vérifiée mot pour mot (`TRADING_LESSONS_ZONE_ACCUMULATION.md`
ligne 7, la même que celle déjà résumée ligne 28 ci-dessus) : *"Typologies
d'accumulation : Continuation (2/3 des cas, sort dans le sens de la tendance
précédente) vs Renversement/Revers (1/3 des cas). Pour le trade en 'Revers',
une règle de prudence s'impose : il est obligatoire de vérifier la tendance sur
une unité de temps située deux degrés au-dessus..."* — et sa glose ligne 9 :
*"un trade de continuation est déjà aligné avec le TF supérieur (pas de
vérification supplémentaire nécessaire)"*. #9 va dans le même sens (la clause
de transgression ne concerne qu'un trade *"contre le flux"*). La citation est
donc EXACTE et le scope est bien la table RANGE (#10 gère son trade avec le
vocabulaire §3 : 4 bornes, Validation / Confirmation / Break-Even) — donc bien
le gate de CE fichier, pas une confusion d'UT comme au 7e round. Ce qui bloque
est ailleurs, en 4 points, chacun MESURÉ :

1. **Aucun état BAISSIER n'existe dans le projet.** Un "renversement" long =
   un long pris alors que la tendance précédente est baissière. Or
   `regime_classifier.add_regime` est structurellement asymétrique :
   `TENDANCE`/`RANGE_TENDANCIEL` exigent `slope_pct > 0`, si bien qu'une
   tendance baissière tombe dans le `else` = `RANGE_NEUTRE`, indiscernable
   d'un range plat. Mesuré (BTC/ETH/BNB/SOL, H4/D1/W, tout l'historique) :
   32-50% des barres ont `slope_pct < -1,5%` et **80-100% d'entre elles sont
   étiquetées RANGE_NEUTRE** (100% en Hebdomadaire). Verrouillé par
   `test_ut2.py::test_downtrend_and_flat_range_get_the_same_regime_label`
   (vérité terrain synthétique). Coder la distinction exige donc d'INVENTER un
   5e régime baissier — même risque de méthode que le gate Fibonacci RANGE, et
   avec un blast radius caché : 134 sites de comparaison de chaînes `regime`
   hors tests, dans 22 fichiers de production (30 fichiers `code/*.py` en
   comptant les 8 fichiers de tests concernés), dont `d1_not_range` de
   `backtest_phase2_faithful.py`
   (`not in ("RANGE_NEUTRE","RANGE_TENDANCIEL")`) qui laisserait PASSER un
   nouveau label baissier, ouvrant silencieusement des trades aujourd'hui
   bloqués.
2. **C'est la DÉFINITION, pas la règle, qui déciderait du résultat** — même
   schéma décisif que le choix du niveau pour Conflit MTF (89% vs 12-19%). 4
   définitions candidates, toutes construites sur des briques déjà en place,
   mesurées sur `faithful.py` (MODERE) : `regime_W != TENDANCE` = no-op exact
   (SOL 192 trades, 18,30%, bit-à-bit la référence) ; `regime_d1 != TENDANCE`
   = +48-58% de trades ; `close_H4 <= EMA55` (le propre filtre de tendance de
   fond de `proxy_v2.structure_favorable`) = gate encore actif sur **17-45
   barres seulement** sur 1051-1408 candidates, soit une quasi-suppression
   (SOL : 357 trades / 50,40%, exactement le résultat "gate retiré").
3. **La population "renversement" est déjà vide par construction dans les
   deux moteurs.** RANGE : le gate Conflit MTF (source #5, *"l'erreur numéro
   un"*, mieux établi que celui-ci) exige `regime_d1` hors range ; mesuré,
   **100%** des barres qui combinent contexte D1 baissier (détecteur miroir) +
   signal long H4 + Conflit MTF passé sont en `regime_d1 == EXCES`, l'état que
   le manuel interdit de trader (§1 *"Bulle/Excès -> NE PAS TRADER"*), et
   elles ne pèsent que 4,4-14,9% des candidates. TENDANCE : `trend_table.py`
   n'a qu'un seul chemin d'ouverture, `accumulation_active = regime_v[i-1] ==
   "TENDANCE" and ...` — toute campagne d'accumulation y est une continuation
   par construction, le cas "Revers" (1/3 des cas selon #10) n'y est jamais
   atteignable. Restreindre le gate aux renversements revient donc à le
   SUPPRIMER pour 85-95% des candidates.
4. **La justification que la source donne à l'exemption est FALSIFIÉE par nos
   briques.** #10:9 affirme qu'une continuation est *"déjà alignée avec le TF
   supérieur"* — mesuré, **32-42%** des candidates de continuation
   (`regime_d1 == TENDANCE`) ne sont PAS alignées Hebdomadaire (355 BTC / 387
   ETH / 336 BNB / 222 SOL barres). L'exemption ne serait donc pas le
   raffinement neutre que son propre raisonnement annonce, mais un vrai
   relâchement. Et le gate n'est pas "rarement actif" comme le supposait
   l'énoncé de l'item : il retire 36,1-48,8% des candidates restantes et
   DIVISE PAR ~2 le nombre de trades (BTC 256 vs 517).

Enfin, direction de l'effet, dite honnêtement : **toutes** les variantes
"renversement seulement" AUGMENTENT le rendement backtesté (BTC 15,60% ->
18,10/28,70% ; SOL 18,30% -> 25,10/50,40%). Un item dont le seul effet
mesurable est de relâcher une règle prudente et d'améliorer le backtest, avec
une amplitude fixée par une définition que le corpus ne tranche pas, est
exactement la tentation que la méthode de ce projet refuse. À noter aussi que
le corpus n'INTERDIT pas de vérifier l'UT+2 sur une continuation : il dit que
ce n'est *"pas nécessaire"*. L'application uniforme actuelle est donc de la
prudence EN TROP, pas une infidélité — et elle suit le défaut déjà arbitré
pour Conflit MTF (*"appliqué uniformément aux deux -- lecture la plus
conservatrice"*). NE PAS restreindre ce gate sans une nouvelle décision
explicite documentée.

Trouvaille annexe, ajoutée au backlog (pas traitée ici) : ce gate teste
`score >= 2` (proxy momentum/cycle/structure), pas `regime == "TENDANCE"`,
alors que #9 dit *"une tendance CONFIRMÉE sur la 3ème unité de temps"* et #10
*"vérifier la TENDANCE sur une unité de temps située deux degrés au-dessus"*.
Mesuré : parmi les barres qui passent aujourd'hui le gate, l'Hebdomadaire est
en `RANGE_NEUTRE` dans 77,5% (BTC 618/797), 85,5% (ETH), 65,0% (BNB), 85,4%
(SOL) des cas — une lecture littérale "régime Hebdo = TENDANCE" serait donc
BEAUCOUP plus stricte que le gate actuel (jusqu'à ~18x moins de barres sur
ETH), dans le sens inverse de l'item ci-dessus.
"""
import pandas as pd
import numpy as np
import sys

from emile.backtests.backtest_phase2 import FEE, load_h1, resample
from emile.backtests.backtest_phase2_v7 import (
    prepare, PROFILES_V4, LOCAL_DURATION, CONTEXT_DURATION,
    MIN_BORDERS, RULE3_STREAK, RULE3_SIZE_MULT, MAX_TRANCHES, EMA_SLOW,
)
from emile.core.position_engine import run_position_engine, make_open_tranche_fn

# Délai de clôture réelle d'une bougie de niveau supérieur, relatif à son
# `date` (voir note ci-dessus) : 1 jour, identique pour D1 ET Hebdomadaire
# avec la convention `resample()` de ce projet — PAS "1 semaine" pour 'W'.
CLOSURE_DELAY = pd.Timedelta(days=1)

GATE_MODES = ("none", "d1_only", "ut2_strict", "d1_and_weekly")

def attach_context_level(df_low: pd.DataFrame, df_high: pd.DataFrame,
                          closure_delay: pd.Timedelta = CLOSURE_DELAY) -> dict:
    """Un seul niveau de contexte, factorisé pour être appelé N fois (une
    par niveau supérieur voulu) — même jointure `merge_asof` sans lookahead
    que `backtest_phase2_v7.py::attach_higher_context`, pour UNE colonne de
    contexte à la fois plutôt que les 3 colonnes fixes de la version v7.

    `ctx_width_pct` (largeur du canal Extreme Channel de ce niveau, produite
    par `backtest_phase2_v7.py::prepare`) est joint EN PLUS depuis l'ajout de
    la règle de volatilité "Stop Loss = taille du canal" -- STRICTEMENT
    ADDITIF (une clé de plus dans le dict retourné, aucun appelant existant
    n'en dépend), par LA MÊME jointure sans lookahead que les 3 autres
    colonnes, pour que la largeur lue soit toujours celle du MÊME niveau que
    le `ctx_support` qui porte le stop (H-Canal-Large-2, cf.
    `position_engine.py`)."""
    high = df_high[["date", "score", "regime", "ctx_support", "ctx_width_pct"]].copy()
    high["available_at"] = high["date"] + closure_delay
    high = high.sort_values("available_at")
    merged = pd.merge_asof(
        df_low[["date"]].sort_values("date"), high,
        left_on="date", right_on="available_at", direction="backward",
    )
    return {
        "score": merged["score"].values,
        "regime": merged["regime"].values,
        "ctx_support": merged["ctx_support"].values,
        "ctx_width_pct": merged["ctx_width_pct"].values,
    }

def attach_multi_context(df_low: pd.DataFrame, levels: list,
                          closure_delay: pd.Timedelta = CLOSURE_DELAY) -> dict:
    """Généralisation à N niveaux de contexte. `levels` = [(nom, df_high), ...].
    Retourne {nom: {"score": ..., "regime": ..., "ctx_support": ...}, ...},
    chaque niveau joint indépendamment (aucune barre future, quel que soit
    le nombre de niveaux)."""
    return {name: attach_context_level(df_low, df_high, closure_delay) for name, df_high in levels}

def _aligned(ctx: dict, i: int) -> bool:
    """Signal >= 2 ET régime != EXCES sur un niveau de contexte donné, à
    l'index i (déjà décalé d'une barre par l'appelant — cf. `[i - 1]` dans
    run_ut2). NaN (warmup du niveau supérieur) se traduit en False via les
    comparaisons numpy, comme dans backtest_phase2_v7.py."""
    return bool(ctx["score"][i] >= 2 and ctx["regime"][i] != "EXCES")

def run_ut2(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame, profile_name: str,
            gate_mode: str = "ut2_strict", use_mtf_stop: bool = False,
            record_trace: bool = False) -> dict:
    """Même moteur que `backtest_phase2_v7.py::run_v7`, généralisé pour
    accepter un 3e niveau (Hebdomadaire) et choisir le mode de validation :
      - "none"          : H4 seul, aucune validation croisée (référence)
      - "d1_only"        : validé par D1 seul (= règle v7 existante, niveau
                           immédiatement supérieur)
      - "ut2_strict"     : validé par l'Hebdomadaire SEUL, D1 sauté — lecture
                           retenue comme la règle "UT+2" littérale du corpus
      - "d1_and_weekly"  : validé par D1 ET Hebdomadaire (cumulatif) — PAS la
                           règle littérale du corpus, gardée pour comparaison
                           demandée explicitement par la tâche
    """
    if gate_mode not in GATE_MODES:
        raise ValueError(f"gate_mode inconnu: {gate_mode!r}, attendu parmi {GATE_MODES}")

    p = PROFILES_V4[profile_name]
    h4 = prepare(h4)
    d1 = prepare(d1)
    weekly = prepare(weekly)
    ctx = attach_multi_context(h4, [("D1", d1), ("W", weekly)])

    score = h4["score"].values
    atr_v = h4["atr"].values
    ctx_support_v = ctx["D1"]["ctx_support"] if use_mtf_stop else h4["ctx_support"].values
    local_range_v = h4["local_range"].values
    context_range_v = h4["context_range"].values
    n_borders_v = h4["n_borders"].values
    high, low, o, c = h4["high"].values, h4["low"].values, h4["open"].values, h4["close"].values
    n = len(h4)
    warmup = EMA_SLOW + 20

    def gate(i: int) -> bool:
        if gate_mode == "none":
            return True
        if gate_mode == "d1_only":
            return _aligned(ctx["D1"], i)
        if gate_mode == "ut2_strict":
            return _aligned(ctx["W"], i)
        return _aligned(ctx["D1"], i) and _aligned(ctx["W"], i)  # d1_and_weekly

    state = {"last_pyramid_high": -np.inf}

    def gate_extra(j):
        # Même gate pour l'entrée fraîche et le renfort dans ce moteur
        # (aucun des 4 gate_mode ne distingue les deux, contrairement à v6/fib).
        g = gate(j)
        return g, g

    open_tranche_fn = make_open_tranche_fn(
        atr_v, ctx_support_v, local_range_v, context_range_v, n_borders_v, high, o, score,
        warmup, MIN_BORDERS, MAX_TRANCHES, RULE3_STREAK, RULE3_SIZE_MULT, p["risk_pct"], state,
        extra_gate_fn=gate_extra,
    )

    gated_long_signal = np.array([(score[i] >= 2) and gate(i) for i in range(n)])

    raw = run_position_engine(
        n, o, high, low, c, gated_long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=MAX_TRANCHES, fee=FEE,
        record_trace=record_trace,
    )
    result = {
        "n_trades": raw["n_trades"], "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"], "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
    }
    if record_trace:
        result["trace"] = raw["trace"]
        result["dates"] = h4["date"].values
        result["final_equity"] = raw["final_equity"]
    return result

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        weekly = resample(h1, "W")
        print(f"{symbol}: n_h4={len(h4)} n_d1={len(d1)} n_weekly={len(weekly)}", flush=True)
        for profile in PROFILES_V4:
            for gate_mode in GATE_MODES:
                res = run_ut2(h4.copy(), d1.copy(), weekly.copy(), profile, gate_mode=gate_mode)
                rows.append({"symbol": symbol, "profile": profile, "gate_mode": gate_mode, **res})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_ut2_results.csv", index=False)

if __name__ == "__main__":
    main()
