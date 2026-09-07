"""
Moteur de position partagé (Validation / Confirmation / Limite / Invalidation).

Factorise la boucle de gestion de tranche(s) auparavant copiée-collée à la
main dans trois fichiers :
  - backtest_phase2.py   (run_backtest_mm, tranche unique)
  - backtest_phase2_v4.py (run_v4, jusqu'à 3 tranches, pyramidalisation)
  - backtest_phase2_v5.py (run_v5, identique à v4, proxy de signal différent)

Règles de gestion (dérivées du corpus Trading Lessons, cf. RULES_EXTRACTION.md
et PHASE2_CORRECTION_BREAKEVEN.md / PHASE2_CORRECTION_CLOSES.md) :
  1. Limite atteinte  -> clôture totale de la tranche (déclenchée sur CLÔTURE).
  2. Invalidation (stop) touchée -> clôture totale (déclenchée sur la MÈCHE,
     c'est un ordre réel qui s'exécute intrabar).
  3. Sortie de signal (flip) AVANT toute étape (ni Validation ni Confirmation
     atteintes) -> sortie au marché (open de la bougie suivante).
  4. Confirmation atteinte (seulement si Validation déjà faite, séquentiel,
     déclenchée sur CLÔTURE) -> clôture partielle éventuelle + c'est le SEUL
     point où le stop peut être remonté au break-even (si le profil l'autorise).
  5. Validation atteinte (déclenchée sur CLÔTURE) -> clôture partielle
     éventuelle. Le stop n'est JAMAIS remonté à cette étape (interdit avant
     Confirmation, cf. correction du 2025 : l'ancienne approximation qui
     remontait le stop dès la Validation était une lecture erronée du corpus).

Les niveaux de Validation/Confirmation/Limite ainsi que le stop initial sont
calculés par le script appelant (ils diffèrent entre moteurs : multiples
d'ATR fixes dans backtest_phase2.py, vs. amplitude réelle en durée +
Extreme Channel dans v4/v5) et injectés via `open_tranche_fn`. Un hook
optionnel `update_levels_fn` permet de reproduire le comportement spécifique
de backtest_phase2.py, où Validation/Confirmation/Limite sont RECALCULÉS
à chaque pas de temps à partir de l'ATR courant (et non figés à l'entrée
comme dans v4/v5) — un comportement pré-existant, conservé tel quel pour ne
pas changer les résultats numériques du refactoring.
"""
import numpy as np
import pandas as pd


def process_tranche(tr, i, o, low, c, long_signal_prev, val_close_frac, conf_close_frac, conf_to_be):
    """Fait progresser une tranche ouverte d'un pas de temps `i`. Mute `tr` en place.

    `tr` doit exposer les clés : entry, stop, remaining, val_done, conf_done,
    pnl_accum, val_px, conf_px, lim_px.

    Retourne (closed: bool, fee_frac: float, realized_pnl: float|None).
    `fee_frac` est la fraction du capital (par rapport à la taille initiale
    de la tranche) sur laquelle des frais doivent être prélevés ce pas-ci
    (clôture totale ou partielle). `realized_pnl` est le P&L total de la
    tranche (fraction), renseigné seulement si la tranche se ferme ce pas-ci.
    """
    # 1) Limite atteinte -> clôture totale (sur CLÔTURE)
    if c[i] >= tr["lim_px"]:
        pnl = (c[i] - tr["entry"]) / tr["entry"]
        tr["pnl_accum"] += pnl * tr["remaining"]
        fee_frac = tr["remaining"]
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        return True, fee_frac, realized

    # 2) Invalidation (stop) touchée -- sur MÈCHE (ordre réel, intrabar)
    if low[i] <= tr["stop"]:
        pnl = (tr["stop"] - tr["entry"]) / tr["entry"]
        tr["pnl_accum"] += pnl * tr["remaining"]
        fee_frac = tr["remaining"]
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        return True, fee_frac, realized

    # 3) Sortie de signal (flip) avant toute étape -> sortie au marché (open)
    if not long_signal_prev and not tr["val_done"] and not tr["conf_done"]:
        pnl = (o[i] - tr["entry"]) / tr["entry"]
        tr["pnl_accum"] += pnl * tr["remaining"]
        fee_frac = tr["remaining"]
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        return True, fee_frac, realized

    fee_frac = 0.0

    # 4) Confirmation atteinte (seulement si validation déjà faite, séquentiel)
    if tr["val_done"] and not tr["conf_done"] and c[i] >= tr["conf_px"]:
        close_amt = tr["remaining"] * conf_close_frac
        if close_amt > 0:
            pnl = (c[i] - tr["entry"]) / tr["entry"]
            tr["pnl_accum"] += pnl * close_amt
            fee_frac += close_amt
            tr["remaining"] -= close_amt
        if conf_to_be:
            tr["stop"] = max(tr["stop"], tr["entry"])
        tr["conf_done"] = True

    # 5) Validation atteinte -- PAS de breakeven ici (interdit avant Confirmation)
    if not tr["val_done"] and c[i] >= tr["val_px"]:
        close_amt = tr["remaining"] * val_close_frac
        if close_amt > 0:
            pnl = (c[i] - tr["entry"]) / tr["entry"]
            tr["pnl_accum"] += pnl * close_amt
            fee_frac += close_amt
            tr["remaining"] -= close_amt
        tr["val_done"] = True

    if tr["remaining"] <= 1e-9:
        realized = tr["pnl_accum"]
        return True, fee_frac, realized

    return False, fee_frac, None


def run_position_engine(n, o, high, low, c, long_signal, open_tranche_fn,
                         val_close_frac, conf_close_frac, conf_to_be, max_tranches, fee,
                         update_levels_fn=None, mark_new_tranches=True, same_bar_reentry=True):
    """Boucle générique de gestion de position, à tranche unique ou multiple.

    - n : nombre de bougies.
    - o, high, low, c : arrays numpy des prix (open/high/low/close).
    - long_signal : array bool (indexé normalement ; le moteur utilise
      long_signal[i-1], cohérent avec la convention "signal de la bougie
      précédente" des scripts d'origine).
    - open_tranche_fn(i, tranches, win_streak) : callback fourni par le
      script appelant, encapsulant SA logique d'éligibilité à l'entrée
      (warmup, maturité, pyramidalisation, Règle de Trois, calcul du stop
      initial et des niveaux Validation/Confirmation/Limite...). Doit
      retourner soit None (pas d'ouverture ce pas-ci), soit un nouveau
      dict tranche prêt à l'emploi (voir `process_tranche`). N'est appelé
      que lorsque `len(tranches) < max_tranches`.
    - val_close_frac, conf_close_frac : fractions du RESTANT à clôturer à
      Validation / Confirmation (mêmes valeurs pour toutes les tranches
      d'un même appel : ce sont des paramètres de profil de risque).
    - conf_to_be : bool, si True le stop est remonté au break-even (max
      avec l'entrée) à la Confirmation ; certains profils du moteur
      "trade spéculatif" d'origine (AGRESSIF/TRES_AGRESSIF dans
      backtest_phase2.py) désactivent explicitement ce comportement.
    - max_tranches : nombre maximal de tranches simultanément ouvertes
      (1 = pas de pyramidalisation, comme dans backtest_phase2.py).
    - fee : frais proportionnels (fraction) appliqués sur chaque montant
      ouvert ou clôturé.
    - update_levels_fn(tr, i) : hook optionnel, appelé pour chaque tranche
      ouverte avant `process_tranche`, pour recalculer ses niveaux
      Validation/Confirmation/Limite si le moteur appelant les fait
      dériver dans le temps (cas de backtest_phase2.py, qui les recalcule
      à partir de l'ATR courant plutôt que de les figer à l'entrée).
    - mark_new_tranches : si True (comportement d'origine de v4/v5), une
      tranche ouverte à ce pas `i` est immédiatement incluse dans le
      mark-to-market (equity_curve) du même pas. Si False (comportement
      d'origine de backtest_phase2.py, dont la structure en `continue`
      sautait le calcul de mark-to-market le jour même de l'entrée), une
      tranche fraîchement ouverte au pas `i` n'entre dans l'equity_curve
      qu'à partir du pas suivant. Conservé tel quel pour ne pas changer
      les résultats numériques du refactoring (max_dd_% dépend de la
      equity_curve).
    - same_bar_reentry : si True (comportement d'origine de v4/v5), une
      tranche qui se clôture totalement au pas `i` peut être immédiatement
      remplacée par une nouvelle entrée AU MÊME pas `i` (le code d'origine
      v4/v5 n'a jamais de `continue` : gestion des tranches existantes et
      tentative d'ouverture ont toujours lieu dans la même itération). Si
      False (comportement d'origine de backtest_phase2.py, structuré en
      `if not in_position: ...; continue`), une entrée n'est tentée QUE
      lorsqu'aucune tranche n'était déjà ouverte au DÉBUT du pas `i` (donc
      jamais le même pas qu'une clôture) -- et dans ce cas les tranches
      existantes ne sont pas non plus re-traitées ce pas-ci (il n'y en a
      pas). Conservé tel quel pour ne pas changer les résultats numériques
      du refactoring.

    Retourne un dict avec : n_trades, final_equity, max_dd_%, total_return_%,
    win_rate_%, profit_factor, avg_trade_%, equity_curve (array numpy, pour
    usage interne/diagnostic -- pas forcément exportée en CSV par l'appelant).
    """
    equity = 1.0
    equity_curve = np.empty(n)
    equity_curve[0] = equity
    tranches = []
    trades = []
    win_streak = 0

    for i in range(1, n):
        long_signal_prev = bool(long_signal[i - 1])
        had_open_at_start = len(tranches) > 0
        process_this_step = same_bar_reentry or had_open_at_start

        if process_this_step:
            remaining_tranches = []
            for tr in tranches:
                if update_levels_fn is not None:
                    update_levels_fn(tr, i)
                closed, fee_frac, realized = process_tranche(
                    tr, i, o, low, c, long_signal_prev, val_close_frac, conf_close_frac, conf_to_be
                )
                if closed:
                    equity *= (1 + realized)
                if fee_frac > 0:
                    equity *= (1 - fee * fee_frac)
                if closed:
                    trades.append(realized)
                    win_streak = win_streak + 1 if realized > 0 else 0
                else:
                    remaining_tranches.append(tr)
            tranches = remaining_tranches
        still_open = list(tranches)  # survivants AVANT l'ouverture éventuelle d'une nouvelle tranche ce pas-ci

        can_open_this_step = (same_bar_reentry or not had_open_at_start) and len(tranches) < max_tranches
        if can_open_this_step:
            new_tr = open_tranche_fn(i, tranches, win_streak)
            if new_tr is not None:
                tranches.append(new_tr)
                equity *= (1 - fee * new_tr["remaining"])

        mtm_tranches = tranches if mark_new_tranches else still_open
        unrealized = sum(tr["pnl_accum"] + (c[i] - tr["entry"]) / tr["entry"] * tr["remaining"] for tr in mtm_tranches)
        equity_curve[i] = equity * (1 + unrealized)

    trades_arr = np.array(trades) if trades else np.array([])
    eq_series = pd.Series(equity_curve)
    max_dd = (eq_series / eq_series.cummax() - 1).min()
    return {
        "n_trades": len(trades_arr),
        "final_equity": equity,
        "max_dd_%": round(max_dd * 100, 1),
        "total_return_%": round((equity - 1) * 100, 1),
        "win_rate_%": round((trades_arr > 0).mean() * 100, 1) if len(trades_arr) else None,
        "profit_factor": round(trades_arr[trades_arr > 0].sum() / abs(trades_arr[trades_arr < 0].sum()), 2)
        if len(trades_arr) and (trades_arr < 0).any() else None,
        "avg_trade_%": round(trades_arr.mean() * 100, 3) if len(trades_arr) else None,
        "equity_curve": equity_curve,
    }
