"""
"Repli Neuneu" / "Dumb Zone" (moitié LONG du mécanisme Neuneu, `docs/GUIDE_
STRATEGIE_PRO_INDICATORS.md` section 3.3, écran `Repli-neuneu.png`) --
46e round (`docs/PLAN.md`), décision directe de l'utilisateur : "trouve une
solution", suivie d'une confirmation explicite (question posée item par
item) d'autoriser la réutilisation du détecteur de swing déjà existant
(`compute_swing_high_confirmed`) pour construire la "dumb zone", jusqu'ici
sans définition codable (32e/36e rounds : "AUCUN chiffre nulle part pour la
dumb zone").

Rappel de la source (citation exacte, `Repli-neuneu.png`, déjà transcrite
mot pour mot dans `docs/GUIDE_STRATEGIE_PRO_INDICATORS.md` section 3.3) :

  Pattern 1/2/3 :
    1. le prix fait un creux et a tenu plusieurs clôtures largement sous la
       zone d'achat fibo (14,6%-23,6%) -- "le creux ne doit pas forcément
       faire un nouveau plus bas"
    2. le prix rebondit et atteint la "dumb zone" où il tient plusieurs
       clôtures sans sortir du haut de la zone
    3. puis le prix rebaisse et revient chercher la zone d'achat Fibonacci
       -- dans ce cas on applique les règles de déclenchement :
         1. le prix est proche du contexte
         2. le prix est dans la zone fibo (14-23%)
         3. break sinewave optionnel
         4. signal momentum optionnel

  Gestion du risque, risque max 2% :
    Stoploss = taille du canal de tendance, au moins égal à la moitié du
    canal de contexte. Validation = retour au contexte opposé OU entrée
    dans la dumb-zone (SL déplacé au sommet récent). Objectif : viser le
    bas de la dumb zone pour un TP partiel, ne jamais viser au-delà de la
    zone fibo opposée.

HYPOTHÈSES D'IMPLÉMENTATION (le corpus ne chiffre ni "plusieurs clôtures",
ni la position exacte de la "dumb zone", ni la fraction du "TP partiel" --
chacune documentée séparément, aucune ne prétend être la seule lecture
possible) :

  H-Neuneu-Repli-1 (creux/dumb zone = swings confirmés) : "plusieurs
  clôtures... sans sortir du haut de la zone" est opérationnalisé en
  réutilisant TEL QUEL le détecteur de swing déjà établi dans ce projet
  (`compute_swing_low_confirmed`/`compute_swing_high_confirmed`,
  `proxy_v2.py`, `SWING_ORDER=3` -- MÊME primitive que "3ème borne"/
  `n_borders`/le routage Neuneu du 32e round), pas une nouvelle convention
  inventée pour ce mécanisme précis. Le "creux" = un swing low confirmé
  dont la CLÔTURE est sous la zone fibo basse ; la "dumb zone" = le swing
  high confirmé qui suit.

  H-Neuneu-Repli-2 (canal de tendance/contexte = local_range/context_range) :
  ces 2 termes sont DÉJÀ nommés et calculés ailleurs dans ce projet
  (`backtest_phase2_v7.py::prepare`, `LOCAL_DURATION`/`CONTEXT_DURATION`) --
  aucune nouvelle définition, simple réutilisation terminologique directe
  (même principe déjà établi : "même terme = même définition partout").

  H-Neuneu-Repli-3 (zone fibo "achat" = 14,6%-23,6% de la hauteur du
  canal de contexte, ancrée au BAS) : citation littérale des 2 pourcentages
  (`NEUNEU_FIB_LOW`/`NEUNEU_FIB_HIGH` ci-dessous) ; l'ancrage au bas (et non
  au haut) est déduit du sens du mécanisme (achat = LONG, la source dit "on
  place des fibos sur toute la hauteur du range", `Range-neuneu.png`) --
  cohérent avec le sens du chart annoté (les 2 bandes basses du guide) et
  avec la convention "achat" (Repli Neuneu = acheter le creux, symétrique de
  Borne Neuneu = vendre l'excès haut, 36e round).

  H-Neuneu-Repli-4 ("dumb zone" = un NIVEAU, pas une bande à 2 bornes) :
  le corpus décrit un plafond ("sans sortir du haut de la zone") mais ne
  chiffre jamais son plancher, alors que l'Objectif vise explicitement "le
  bas de la dumb zone". Approximation documentée (pas une invention de
  chiffre, une réduction de portée) : la dumb zone est traitée comme UN
  SEUL niveau (le swing high confirmé lui-même) -- servant à la fois de
  déclencheur de Validation (retour "dans" la zone) et de cible d'Objectif
  ("bas de la zone" = le niveau lui-même, approché par en dessous).

  H-Neuneu-Repli-5 ("proche du contexte", règle de déclenchement #1) :
  aucun seuil de proximité n'est chiffré. Lecture retenue : redondante avec
  la règle #2 (être dans la zone fibo 14-23% du bas du canal de contexte
  implique déjà d'être proche du contexte bas) -- pas un gate séparé, pas
  un chiffre inventé.

  H-Neuneu-Repli-6 (règles #3/#4 "optionnelles" = non bloquantes) : lues
  littéralement -- "optionnel" signifie que leur absence n'empêche PAS le
  déclenchement, donc aucun gate n'est construit pour elles (les construire
  comme gates obligatoires contredirait le mot "optionnel" du corpus).

  H-Neuneu-Repli-7 (fraction du "TP partiel", NON chiffrée par le corpus --
  EXTRAPOLATION SUPPLÉMENTAIRE, distincte de H-Neuneu-Repli-1) :
  `NEUNEU_OBJECTIF_CLOSE_FRAC = 0.50` réutilise la MÊME valeur déjà établie
  ailleurs dans ce projet pour une 1ère prise de profit partielle
  ("Validation" du profil FAIBLE, `PROFILES_V4`) -- pas un chiffre choisi
  au hasard, mais reste une extrapolation à part entière. C'est pourquoi ce
  mécanisme, comme "SL gain" (45e round), reste OPT-IN (`use_neuneu_repli`
  dans l'appelant), jamais activé par défaut.

Comme "SL gain" (45e round), la stratégie STANDALONE ci-dessous n'est PAS
encore câblée dans `faithful.py`/`unified_protocol.py` (le routage RANGE
existant, `regime_classifier.compute_use_neuneu`, décide QUAND appliquer
Neuneu plutôt que "3ème borne" -- brancher réellement ce choix dans les
moteurs de production est un chantier de câblage séparé, pas fait ici).
Ce module est un moteur COMPLET et TESTABLE en isolation (même statut que
`h1_timeframe_bench.py` avant son propre câblage), mesuré honnêtement
ci-dessous par `neuneu_repli_measure.py`.
"""
import numpy as np
import pandas as pd

from emile.core.proxy_v2 import compute_swing_low_confirmed, compute_swing_high_confirmed, SWING_ORDER
from emile.core.position_engine import context_channel_bounds

NEUNEU_FIB_LOW, NEUNEU_FIB_HIGH = 0.146, 0.236   # littéral, Repli-neuneu.png
NEUNEU_RISK_PCT = 0.02                            # littéral, "risque max 2%"
NEUNEU_OBJECTIF_CLOSE_FRAC = 0.50                 # H-Neuneu-Repli-7, extrapolation


def _repli_neuneu_state_machine(close, swing_low, swing_high, ctx_low, ctx_high,
                                 local_low, local_high) -> dict:
    """Cœur PUR de la machine à états (aucun calcul de fenêtre glissante ici
    -- tous les arrays d'entrée sont déjà résolus par l'appelant). Séparée de
    `compute_repli_neuneu_signal` ci-dessous UNIQUEMENT pour être testable
    avec des arrays FABRIQUÉS À LA MAIN (sans avoir à reproduire un vrai
    canal glissant dans les tests, cf. `test_neuneu_repli.py`) -- même
    principe de séparation que `_prepare_features`/`_run_core` ailleurs
    dans ce projet.

    Machine à états causale : chaque décision à `i` ne consulte que des
    données jusqu'à `i-1` inclus (`j = i-1` partout ci-dessous)."""
    n = len(close)
    long_signal = np.zeros(n, dtype=bool)
    dumb_zone_level = np.full(n, np.nan)
    local_range_out = np.full(n, np.nan)
    context_range_out = np.full(n, np.nan)
    ctx_high_ref_out = np.full(n, np.nan)

    stage = "AWAITING_CREUX"
    dz_level = None

    for i in range(1, n):
        j = i - 1
        cl, ch = ctx_low[j], ctx_high[j]
        if np.isnan(cl) or np.isnan(ch) or ch <= cl:
            continue
        fib_low = cl + NEUNEU_FIB_LOW * (ch - cl)
        fib_high = cl + NEUNEU_FIB_HIGH * (ch - cl)

        if stage == "AWAITING_CREUX":
            if swing_low[j] and close[j] < fib_low:
                stage = "AWAITING_DUMBZONE"
        elif stage == "AWAITING_DUMBZONE":
            if swing_high[j]:
                dz_level = close[j]
                stage = "AWAITING_RETURN"
        elif stage == "AWAITING_RETURN":
            if fib_low <= close[j] <= fib_high:
                long_signal[i] = True
                dumb_zone_level[i] = dz_level
                ll, lh = local_low[j], local_high[j]
                local_range_out[i] = (lh - ll) if not (np.isnan(ll) or np.isnan(lh)) else np.nan
                context_range_out[i] = ch - cl
                ctx_high_ref_out[i] = ch
                stage = "AWAITING_CREUX"
                dz_level = None

    return {
        "long_signal": long_signal, "dumb_zone_level": dumb_zone_level,
        "local_range": local_range_out, "context_range": context_range_out,
        "ctx_high_ref": ctx_high_ref_out,
    }


def compute_repli_neuneu_signal(df: pd.DataFrame, context_duration, local_duration) -> dict:
    """Détecte causalement le pattern 1/2/3 et produit :
      - `long_signal` (bool, indexé comme `df` -- signal résolu à `i-1`,
        consommé à `i`, MÊME convention que tout le reste du projet) ;
      - `dumb_zone_level` (float, niveau enregistré au moment du signal --
        NaN si `long_signal[i]` est faux) ;
      - `local_range`/`context_range` (float, hauteur des 2 canaux au
        moment du signal -- réutilisés tels quels pour le stop) ;
      - `ctx_high_ref` (float, borne haute du canal de contexte au moment
        du signal -- "contexte opposé" pour la Validation/l'Objectif).

    Calcule les arrays causaux (swings, bornes de canaux) puis délègue à
    `_repli_neuneu_state_machine` ci-dessus."""
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values

    swing_low = compute_swing_low_confirmed(low, order=SWING_ORDER)
    swing_high = compute_swing_high_confirmed(high, order=SWING_ORDER)
    ctx_low, ctx_high = context_channel_bounds(df, context_duration)
    local_low, local_high = context_channel_bounds(df, local_duration)

    return _repli_neuneu_state_machine(close, swing_low, swing_high, ctx_low, ctx_high,
                                        local_low, local_high)


def process_repli_neuneu_tranche(tr, i, high, low, c):
    """Fait progresser une tranche Repli Neuneu ouverte, MÊME esprit que
    `position_engine.py::process_tranche` mais structure DIFFÉRENTE (2
    étapes, pas 3 : Objectif = TP partiel, Validation = stop remonté SANS
    clôture -- l'ordre inverse de `process_tranche`, où Validation ferme
    et Confirmation remonte le stop) : les 2 mécanismes ne partagent pas la
    même séquence, donc pas la même fonction (jamais forcer un mécanisme
    dans le moule d'un autre juste pour réutiliser du code, cf. discipline
    déjà établie -- "+Reverse"/"H-Reverse-Range" est un précédent du même
    principe).

    `tr` doit exposer : entry, stop, remaining, pnl_accum, objectif_target,
    dumb_zone_level, ctx_high_ref, `_max_high_since_entry` (tracé par
    l'appelant, cf. `run_repli_neuneu` -- même bookkeeping que "SL gain",
    45e round)."""
    fee_frac = 0.0
    # 1) Objectif (TP partiel, une seule fois) -- jamais au-delà de la zone
    # fibo opposée (`objectif_target` déjà plafonné à l'ouverture, cf.
    # `run_repli_neuneu`).
    if not tr.get("objectif_done", False) and c[i] >= tr["objectif_target"]:
        close_amt = tr["remaining"] * NEUNEU_OBJECTIF_CLOSE_FRAC
        pnl = (c[i] - tr["entry"]) / tr["entry"]
        tr["pnl_accum"] += pnl * close_amt
        fee_frac += close_amt
        tr["remaining"] -= close_amt
        tr["objectif_done"] = True
        if tr["remaining"] <= 1e-9:
            tr["remaining"] = 0.0
            return True, fee_frac, tr["pnl_accum"]

    # 2) Validation (stop remonté au sommet récent, une seule fois, AUCUNE
    # clôture -- citation littérale, contrairement à "SL gain"/Target 1 qui
    # combine les deux).
    if not tr.get("validated", False) and (
        c[i] >= tr["dumb_zone_level"] or c[i] >= tr["ctx_high_ref"]
    ):
        tr["stop"] = max(tr["stop"], tr.get("_max_high_since_entry", tr["entry"]))
        tr["validated"] = True

    # 3) Stop (sur mèche, ordre réel intrabar -- même convention que partout
    # ailleurs dans ce projet).
    if low[i] <= tr["stop"]:
        pnl = (tr["stop"] - tr["entry"]) / tr["entry"]
        tr["pnl_accum"] += pnl * tr["remaining"]
        fee_frac += tr["remaining"]
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        return True, fee_frac, realized

    return False, fee_frac, None


def run_repli_neuneu(df: pd.DataFrame, context_duration, local_duration,
                      fee: float = 0.0004, record_trace: bool = False) -> dict:
    """Moteur COMPLET, mono-tranche (le corpus ne décrit aucune
    pyramidalisation pour ce mécanisme) : détecte le pattern, ouvre/gère une
    tranche à la fois, agrège les statistiques standard du projet
    (n_trades/max_dd_%/total_return_%/win_rate_%/profit_factor)."""
    n = len(df)
    o = df["open"].values
    high = df["high"].values
    low = df["low"].values
    c = df["close"].values

    sig = compute_repli_neuneu_signal(df, context_duration, local_duration)
    long_signal = sig["long_signal"]

    equity = 1.0
    equity_curve = np.empty(n)
    equity_curve[0] = equity
    tr = None
    trades = []
    trace = [] if record_trace else None

    for i in range(1, n):
        if tr is not None:
            tr["_max_high_since_entry"] = max(tr.get("_max_high_since_entry", tr["entry"]), high[i])
            if record_trace:
                trace[tr["_trade_id"]]["snapshots"].append((i, tr["remaining"]))
            closed, fee_frac, realized = process_repli_neuneu_tranche(tr, i, high, low, c)
            if closed:
                equity *= (1 + realized)
            if fee_frac > 0:
                equity *= (1 - fee * fee_frac)
            if closed:
                trades.append(realized)
                if record_trace:
                    trace[tr["_trade_id"]]["close_i"] = i
                    trace[tr["_trade_id"]]["realized_pnl"] = realized
                tr = None
        elif long_signal[i]:
            entry_price = o[i]
            local_r = sig["local_range"][i]
            context_r = sig["context_range"][i]
            if np.isnan(local_r) or np.isnan(context_r) or context_r <= 0:
                equity_curve[i] = equity
                continue
            stop_distance = max(local_r, 0.5 * context_r)
            stop_price = entry_price - stop_distance
            stop_pct = stop_distance / entry_price
            size_frac = min(1.0, NEUNEU_RISK_PCT / stop_pct) if stop_pct > 0 else 0.0
            if size_frac > 0:
                dz_level = sig["dumb_zone_level"][i]
                ctx_high_ref = sig["ctx_high_ref"][i]
                opposite_fib_low = ctx_high_ref - NEUNEU_FIB_HIGH * context_r
                objectif_target = min(dz_level, opposite_fib_low)
                tr = {
                    "entry": entry_price, "stop": stop_price, "remaining": size_frac,
                    "pnl_accum": 0.0, "dumb_zone_level": dz_level,
                    "ctx_high_ref": ctx_high_ref, "objectif_target": objectif_target,
                    "_max_high_since_entry": entry_price,
                }
                equity *= (1 - fee * size_frac)
                if record_trace:
                    tr["_trade_id"] = len(trace)
                    trace.append({
                        "trade_id": tr["_trade_id"], "open_i": i,
                        "entry_price": entry_price, "entry_size": size_frac,
                        "close_i": None, "realized_pnl": None, "snapshots": [],
                    })
        equity_curve[i] = equity

    max_dd = 0.0
    peak = equity_curve[0]
    for v in equity_curve:
        peak = max(peak, v)
        max_dd = min(max_dd, (v - peak) / peak if peak > 0 else 0.0)

    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    win_rate = 100.0 * len(wins) / len(trades) if trades else 0.0
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)

    result = {
        "n_trades": len(trades),
        "max_dd_%": round(max_dd * 100, 2),
        "total_return_%": round((equity - 1) * 100, 2),
        "win_rate_%": round(win_rate, 2),
        "profit_factor": round(profit_factor, 4) if np.isfinite(profit_factor) else profit_factor,
    }
    if record_trace:
        result["trace"] = trace
    return result
