"""
"Borne Neuneu" (moitié SHORT du mécanisme Neuneu, `docs/GUIDE_STRATEGIE_
PRO_INDICATORS.md` section 3.3, écran `Borne-neuneu.png`) -- 47e round
(`docs/PLAN.md`), suite directe de "trouve une solution" : construction
d'une table RANGE symétrique côté short, jusqu'ici absente de
`position_engine.py` (dont la seule jambe short, "+Reverse"/H-Reverse-
Range, est explicitement BORNÉE -- un seul stop/une seule cible, jamais
une table à étapes).

Rappel de la source (citation exacte, `Borne-neuneu.png`, déjà transcrite
mot pour mot dans `docs/GUIDE_STRATEGIE_PRO_INDICATORS.md` section 3.3) :

  Zone spéculative (entrée) :
    1. le prix est au-delà des contextes
    2. le prix est au-delà du fibo 76%
    3. break sinewave optionnel
    4. signal momentum optionnel

  Gestion du risque, risque max 2% :
    Stoploss = au-dessus du plus haut du range et au moins égal à la
    moitié de la taille du canal de tendance. Validation = retour au
    canal de tendance opposé (parfois la confirmation arrivera avant) --
    déplacement du stoploss au sommet récent. Confirmation = le prix
    revient dans le milieu du range (50% contexte, 50% fibo ou moyenne) --
    TP 50% et NE PAS déplacer le stoploss. Objectif : sortir TOUS les
    profits restants dès que le prix atteint le contexte opposé ou la
    zone fibo 76% opposée.

Contrairement à "Repli Neuneu" (46e round), cet écran NE DÉCRIT AUCUN
pattern 1/2/3 (creux -> dumb zone -> retour) -- l'entrée est un gate DIRECT
(Zone Spéculative), pas une machine à états. Plus simple à construire, mais
la table de gestion du risque exige une lecture plus attentive (les 2
clauses de chaque ligne ne portent pas toujours sur le MÊME canal -- cf.
hypothèses ci-dessous, vérifiées mot pour mot contre l'écran).

HYPOTHÈSES D'IMPLÉMENTATION (aucune ne prétend être la seule lecture
possible ; H-Neuneu-Repli-1/2 du module frère `neuneu_repli.py` sont
réutilisées telles quelles, pas redéfinies ici) :

  H-Borne-1 (entrée = gate direct, pas de machine à états) : "au-delà des
  contextes" = clôture strictement au-dessus de `ctx_high` (canal de
  CONTEXTE, H-Neuneu-Repli-2) ; "au-delà du fibo 76%" = clôture au-dessus
  de `ctx_low + 0,76*(ctx_high-ctx_low)`. Ce 2e critère est REDONDANT avec
  le 1er dès lors que les deux sont mesurés sur le MÊME canal (tout point
  au-dessus de `ctx_high`, soit 100% du canal, est TRIVIALEMENT au-dessus
  de 76%) -- même type de redondance que H-Neuneu-Repli-5 pour l'écran
  frère, gardé néanmoins EXPLICITEMENT dans le code (calculé, documenté)
  par fidélité littérale à la citation plutôt que silencieusement omis.

  H-Borne-2 (Stoploss, lecture des 2 clauses) : "au-dessus du plus haut du
  range" ancre le stop à `ctx_high` (PAS à l'entrée -- puisque l'entrée
  elle-même est déjà au-delà de `ctx_high`, cf. H-Borne-1, ancrer au range
  donne un stop plus SERRÉ, donc plus efficient en risque, que d'ajouter
  une distance depuis l'entrée) ; "au moins égal à la moitié de la taille
  du canal de tendance" est un PLANCHER sur cette distance (`entry -
  ctx_high`), pas une 2e formule concurrente -- même structure "distance
  X, au moins égale à Y" que `neuneu_repli.py` (H-Neuneu-Repli, stop =
  MAX(canal de tendance, 0,5*canal de contexte)), ici avec les rôles des 2
  canaux échangés et une valeur ancrée plutôt que relative :
    stop_distance = MAX(entry - ctx_high, 0,5 * local_range)
    stop_price    = entry + stop_distance

  H-Borne-3 ("canal de tendance opposé", Validation -- DIFFÉRENT de
  "contexte opposé" de Repli Neuneu, vérifié mot pour mot sur l'écran) :
  "canal de tendance" = `local_range`/`local_low` (H-Neuneu-Repli-2, même
  terminologie), donc la Validation compare au canal LOCAL, pas au canal
  de CONTEXTE (contrairement à l'Objectif, qui lui cite explicitement "le
  CONTEXTE opposé"). Une vraie distinction du corpus, pas une négligence.

  H-Borne-4 ("sommet récent", Validation -- MÊME primitif que Repli Neuneu,
  MIROIR de direction) : le corpus réutilise mot pour mot "sommet récent"
  pour les 2 écrans (long ET short) -- lu ici comme un artefact de gabarit
  (même auteur, même tournure copiée) plutôt qu'une prescription littérale
  de remonter le stop d'un SHORT vers un sommet (ce qui dégraderait sa
  protection). Lecture retenue, MIROIR exact de `_max_high_since_entry` du
  module frère : `_min_low_since_entry` (plus bas observé depuis
  l'ouverture), qui resserre le stop vers le bas à mesure que le short
  devient gagnant -- cohérent avec le sens du mécanisme et avec
  l'observation explicite de l'écran "il est également essentiel de ne
  jamais déplacer le stop à breakeven" (remonter au lieu de resserrer
  contredirait cette mise en garde).

  H-Borne-5 ("milieu du range", Confirmation) : 3 lectures données par le
  corpus lui-même ("50% contexte", "50% fibo", "moyenne") sans trancher --
  retenue : `context_channel_median` (DÉJÀ construite et testée dans
  `position_engine.py`, littéralement "50% contexte"), pas une nouvelle
  primitive ni un choix arbitraire entre les 3 lectures équivalentes.

Comme `neuneu_repli.py`, ce module est STANDALONE (PAS câblé dans
`faithful.py`/`unified_protocol.py`), mesuré isolément par
`neuneu_borne_measure.py`.
"""
import numpy as np
import pandas as pd

from emile.core.position_engine import context_channel_bounds, context_channel_median
from emile.core.neuneu_repli import NEUNEU_RISK_PCT

NEUNEU_FIB_76 = 0.76                        # littéral, "fibo 76%"
NEUNEU_CONFIRMATION_CLOSE_FRAC = 0.50        # littéral, "TP 50%"


def _borne_neuneu_state_machine(close, ctx_low, ctx_high, local_low, local_high, regime=None) -> dict:
    """Cœur PUR (aucun calcul de fenêtre glissante) -- gate DIRECT (H-Borne-1),
    pas de machine à états à proprement parler (nommée ainsi par symétrie
    avec `neuneu_repli.py`, pour la même raison de testabilité avec des
    arrays fabriqués à la main).

    `regime` (optionnel, défaut `None` -> AUCUN filtre, comportement de la
    citation brute) : array de régimes (`regime_classifier.add_regime`,
    DÉJÀ calculé partout ailleurs dans ce projet, jamais recalculé ici).
    TROUVAILLE FAITE EN MESURANT ce mécanisme sur données réelles (H-Borne-6,
    cf. `docs/PLAN.md` section "47e application") : le gate brut ("au-delà
    des contextes") se déclenche aussi souvent PENDANT une TENDANCE établie
    (nouveaux plus hauts locaux = condition normale d'une tendance, pas un
    excès) que dans un vrai RANGE en excès (mesuré : 54% des signaux BTC en
    régime TENDANCE) -- alors que "Neuneu" est explicitement une famille de
    la branche RANGE du guide officiel (jamais Tendance), pas une nuance
    ajoutée après coup pour améliorer un chiffre. Restreindre aux régimes
    RANGE_NEUTRE/RANGE_TENDANCIEL (le régime EXCES est déjà, comme partout
    ailleurs dans ce projet, une abstention -- "ne pas trader en Excès")
    n'invente aucun seuil : réutilisation directe d'une classification déjà
    établie, pour un mécanisme qui n'a jamais eu vocation à s'appliquer
    ailleurs que dans un RANGE."""
    n = len(close)
    short_signal = np.zeros(n, dtype=bool)
    context_range_out = np.full(n, np.nan)
    local_range_out = np.full(n, np.nan)
    ctx_high_ref_out = np.full(n, np.nan)
    ctx_low_ref_out = np.full(n, np.nan)
    local_low_ref_out = np.full(n, np.nan)

    for i in range(1, n):
        j = i - 1
        if regime is not None and regime[j] not in ("RANGE_NEUTRE", "RANGE_TENDANCIEL"):
            continue
        cl, ch = ctx_low[j], ctx_high[j]
        if np.isnan(cl) or np.isnan(ch) or ch <= cl:
            continue
        fib76 = cl + NEUNEU_FIB_76 * (ch - cl)
        if close[j] > ch and close[j] > fib76:
            short_signal[i] = True
            context_range_out[i] = ch - cl
            ctx_high_ref_out[i] = ch
            ctx_low_ref_out[i] = cl
            ll, lh = local_low[j], local_high[j]
            local_range_out[i] = (lh - ll) if not (np.isnan(ll) or np.isnan(lh)) else np.nan
            local_low_ref_out[i] = ll

    return {
        "short_signal": short_signal, "context_range": context_range_out,
        "ctx_high_ref": ctx_high_ref_out, "ctx_low_ref": ctx_low_ref_out,
        "local_range": local_range_out, "local_low_ref": local_low_ref_out,
    }


def compute_borne_neuneu_signal(df: pd.DataFrame, context_duration, local_duration,
                                 regime=None) -> dict:
    """Calcule les arrays causaux réels (bornes de canaux) puis délègue à
    `_borne_neuneu_state_machine` ci-dessus. `regime` : cf. sa docstring."""
    close = df["close"].values
    ctx_low, ctx_high = context_channel_bounds(df, context_duration)
    local_low, local_high = context_channel_bounds(df, local_duration)
    return _borne_neuneu_state_machine(close, ctx_low, ctx_high, local_low, local_high, regime=regime)


def process_borne_neuneu_tranche(tr, i, high, low, c):
    """Fait progresser une tranche Borne Neuneu (SHORT) ouverte. MIROIR
    structurel de `neuneu_repli.py::process_repli_neuneu_tranche` (mêmes 3
    familles d'étapes : sortie totale au meilleur cas, clôture partielle
    "milieu de range", ajustement de stop sans clôture) mais PAS identique :
    ici Confirmation (TP 50%) et Validation (stop) sont INDÉPENDANTES l'une
    de l'autre (citation explicite : "parfois la confirmation arrivera
    avant"), alors que `process_tranche` général les enchaîne
    séquentiellement -- encore une raison de ne pas réutiliser cette
    dernière fonction telle quelle.

    `tr` doit exposer : entry, stop, remaining, pnl_accum, objectif_target
    (contexte opposé OU fibo 76% opposée, cf. `run_borne_neuneu`),
    confirmation_target (médiane du canal de contexte), validation_target
    (canal de tendance opposé, H-Borne-3), `_min_low_since_entry` (tracé
    par l'appelant, MIROIR de `_max_high_since_entry`)."""
    fee_frac = 0.0
    # 1) Objectif -- sortie TOTALE (citation : "sortir TOUS les profits
    # restants", pas une fraction à inventer, contrairement à Repli Neuneu).
    if not tr.get("objectif_done", False) and c[i] <= tr["objectif_target"]:
        pnl = (tr["entry"] - c[i]) / tr["entry"]
        tr["pnl_accum"] += pnl * tr["remaining"]
        fee_frac += tr["remaining"]
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        return True, fee_frac, realized

    # 2) Confirmation -- TP 50%, NE PAS déplacer le stop (littéral),
    # indépendante de la Validation (H-Borne, "parfois la confirmation
    # arrivera avant").
    if not tr.get("confirmation_done", False) and c[i] <= tr["confirmation_target"]:
        close_amt = tr["remaining"] * NEUNEU_CONFIRMATION_CLOSE_FRAC
        pnl = (tr["entry"] - c[i]) / tr["entry"]
        tr["pnl_accum"] += pnl * close_amt
        fee_frac += close_amt
        tr["remaining"] -= close_amt
        tr["confirmation_done"] = True
        if tr["remaining"] <= 1e-9:
            tr["remaining"] = 0.0
            realized = tr["pnl_accum"]
            return True, fee_frac, realized

    # 3) Validation -- stop resserré vers le plus bas depuis l'ouverture
    # (H-Borne-4), AUCUNE clôture, indépendante de la Confirmation.
    if not tr.get("validated", False) and c[i] <= tr["validation_target"]:
        tr["stop"] = min(tr["stop"], tr.get("_min_low_since_entry", tr["entry"]))
        tr["validated"] = True

    # 4) Stop (SHORT : touché si le HIGH atteint/dépasse le stop, ordre réel
    # intrabar -- même convention que partout ailleurs dans ce projet).
    if high[i] >= tr["stop"]:
        pnl = (tr["entry"] - tr["stop"]) / tr["entry"]
        tr["pnl_accum"] += pnl * tr["remaining"]
        fee_frac += tr["remaining"]
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        return True, fee_frac, realized

    return False, fee_frac, None


def open_borne_neuneu_tranche(entry_price, local_r, context_r, ctx_high_ref, ctx_low_ref,
                               local_low_ref, confirmation_target):
    """Construit le dict de tranche Borne Neuneu (sizing/stop/objectif/
    confirmation/validation) -- UNE SEULE implémentation, réutilisée par
    `run_borne_neuneu` (moteur STANDALONE ci-dessous) ET par le câblage
    dans `unified_protocol.py` (48e round, canal indépendant Neuneu),
    jamais dupliquée. Retourne `None` si les canaux/la médiane de
    confirmation sont inconnus (warmup) ou si la taille calculée est nulle."""
    if (np.isnan(local_r) or np.isnan(context_r) or context_r <= 0
            or np.isnan(confirmation_target)):
        return None
    stop_distance = max(entry_price - ctx_high_ref, 0.5 * local_r)
    stop_price = entry_price + stop_distance
    stop_pct = stop_distance / entry_price
    size_frac = min(1.0, NEUNEU_RISK_PCT / stop_pct) if stop_pct > 0 else 0.0
    if size_frac <= 0:
        return None
    opposite_fib_level = ctx_low_ref + (1 - NEUNEU_FIB_76) * context_r
    objectif_target = max(ctx_low_ref, opposite_fib_level)
    return {
        "entry": entry_price, "stop": stop_price, "remaining": size_frac,
        "pnl_accum": 0.0, "objectif_target": objectif_target,
        "confirmation_target": confirmation_target, "validation_target": local_low_ref,
        "_min_low_since_entry": entry_price,
    }


def run_borne_neuneu(df: pd.DataFrame, context_duration, local_duration,
                      fee: float = 0.0004, record_trace: bool = False,
                      regime=None) -> dict:
    """Moteur COMPLET, mono-tranche SHORT (le corpus ne décrit aucune
    pyramidalisation), MIROIR de `neuneu_repli.py::run_repli_neuneu`.
    `regime` : cf. docstring de `_borne_neuneu_state_machine` (H-Borne-6)."""
    n = len(df)
    o = df["open"].values
    high = df["high"].values
    low = df["low"].values
    c = df["close"].values

    sig = compute_borne_neuneu_signal(df, context_duration, local_duration, regime=regime)
    short_signal = sig["short_signal"]
    ctx_median = context_channel_median(df, context_duration)

    equity = 1.0
    equity_curve = np.empty(n)
    equity_curve[0] = equity
    tr = None
    trades = []
    trace = [] if record_trace else None

    for i in range(1, n):
        if tr is not None:
            tr["_min_low_since_entry"] = min(tr.get("_min_low_since_entry", tr["entry"]), low[i])
            if record_trace:
                trace[tr["_trade_id"]]["snapshots"].append((i, tr["remaining"]))
            closed, fee_frac, realized = process_borne_neuneu_tranche(tr, i, high, low, c)
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
        elif short_signal[i]:
            entry_price = o[i]
            local_r = sig["local_range"][i]
            context_r = sig["context_range"][i]
            ctx_high_ref = sig["ctx_high_ref"][i]
            ctx_low_ref = sig["ctx_low_ref"][i]
            local_low_ref = sig["local_low_ref"][i]
            conf_j = ctx_median[i - 1]
            tr = open_borne_neuneu_tranche(entry_price, local_r, context_r, ctx_high_ref,
                                            ctx_low_ref, local_low_ref, conf_j)
            if tr is None:
                equity_curve[i] = equity
                continue
            equity *= (1 - fee * tr["remaining"])
            if record_trace:
                tr["_trade_id"] = len(trace)
                trace.append({
                    "trade_id": tr["_trade_id"], "open_i": i,
                    "entry_price": entry_price, "entry_size": tr["remaining"],
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
