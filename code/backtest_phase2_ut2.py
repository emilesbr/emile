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
"""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, ".")
from backtest_phase2 import FEE, load_h1, resample
from backtest_phase2_v7 import (
    prepare, PROFILES_V4, LOCAL_DURATION, CONTEXT_DURATION,
    MIN_BORDERS, RULE3_STREAK, RULE3_SIZE_MULT, MAX_TRANCHES, EMA_SLOW,
)
from position_engine import run_position_engine

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
    contexte à la fois plutôt que les 3 colonnes fixes de la version v7."""
    high = df_high[["date", "score", "regime", "ctx_support"]].copy()
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

    def open_tranche_fn(i, tranches, win_streak):
        long_signal_prev = score[i - 1] >= 2
        mature = (not np.isnan(n_borders_v[i - 1])) and n_borders_v[i - 1] >= MIN_BORDERS
        gated_signal = long_signal_prev and gate(i - 1)

        valid_inputs = (
            not np.isnan(atr_v[i - 1]) and not np.isnan(ctx_support_v[i - 1])
            and not np.isnan(local_range_v[i - 1]) and local_range_v[i - 1] > 0
            and not np.isnan(context_range_v[i - 1]) and context_range_v[i - 1] > 0
        )
        is_fresh_entry = (i > warmup and len(tranches) == 0 and gated_signal and mature and valid_inputs)
        is_pyramid_add = (
            i > warmup and 0 < len(tranches) < MAX_TRANCHES and gated_signal and valid_inputs
            and high[i - 1] > state["last_pyramid_high"]
        )
        if not (is_fresh_entry or is_pyramid_add):
            return None

        entry_price = o[i]
        stop_price = min(ctx_support_v[i - 1], entry_price * 0.999)
        stop_pct = (entry_price - stop_price) / entry_price
        risk_pct = p["risk_pct"]
        if win_streak >= RULE3_STREAK:
            risk_pct *= RULE3_SIZE_MULT
        size_frac = min(1.0 / MAX_TRANCHES, risk_pct / stop_pct) if stop_pct > 0 else 0.0
        if size_frac <= 0:
            return None
        state["last_pyramid_high"] = max(state["last_pyramid_high"], high[i - 1]) if is_pyramid_add else high[i - 1]
        return {
            "entry": entry_price, "stop": stop_price, "remaining": size_frac,
            "val_done": False, "conf_done": False, "pnl_accum": 0.0,
            "val_px": entry_price + local_range_v[i - 1],
            "conf_px": entry_price + context_range_v[i - 1],
            "lim_px": entry_price + 1.5 * context_range_v[i - 1],
        }

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
