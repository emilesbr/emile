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

================================================================================
"+Reverse" du profil Très Agressif à la Limite -- TABLE RANGE (RULES_EXTRACTION
§3, "Money management -- Trade spéculatif (range)"), PAS le mécanisme +Reverse
de la table TENDANCE (§4, `trend_table.py::step_reverse`, profil Très Agressif,
étape Excès final -- structurellement différent, ne pas confondre : celui-là
inverse après une campagne à jambes multiples avec renfort progressif, celui-ci
inverse après la clôture d'une simple tranche long au niveau Limite).
================================================================================
Rappel de la source, reproduit ici pour traçabilité (RULES_EXTRACTION.md §3) :

    4 étapes : Validation -> Confirmation -> Invalidation -> Limite (target)

    | Profil         | Validation | Confirmation | Invalidation | Limite         |
    |----------------|------------|--------------|--------------|----------------|
    | Très agressif  | RIEN       | —            | RIEN         | TP100%+Reverse |

"RIEN"/"—" pour Très Agressif à Validation/Confirmation/Invalidation ne change
rien au comportement déjà en place (val_close_frac=0, conf_close_frac=0 dans
PROFILES_V4 de backtest_phase2_v7.py ; Invalidation reste, comme pour tous les
profils, la clôture totale au stop déjà codée en dur). Le seul comportement
manquant est "TP100%+Reverse" : au lieu de simplement clôturer la tranche
long à la Limite (ce que fait déjà l'étape 1 de `process_tranche`), le profil
Très Agressif ouvre EN PLUS une position short au même instant.

HYPOTHÈSE D'IMPLÉMENTATION (H-Reverse-Range -- le manuel ne donne AUCUN
paramètre pour cette jambe short : ni taille, ni stop, ni cible ; documenté
explicitement ici, sur le modèle de `code/capital_tiers.py` pour une règle
source sous-spécifiée, PAS inventé en silence) :
  - **Taille** : identique à la taille (fraction du capital) qui vient de se
    clôturer sur la jambe long (`tr["remaining"]` juste avant la mise à zéro).
    Aucune indication contraire dans la source ; une taille "miroir" est la
    lecture la plus neutre de "Reverse" (inverser la même exposition).
  - **Prix d'entrée** : le prix de clôture (`c[i]`) qui a déclenché la Limite
    -- l'inversion est immédiate, pas différée à la bougie suivante (cohérent
    avec le principe "reverse AU MOMENT de la clôture" du libellé "TP100%+
    Reverse", une seule action combinée dans la source, pas deux évènements
    séparés dans le temps).
  - **Stop de la jambe reverse** : MIROIR de la distance (en %) entre l'entrée
    long et son stop initial, reportée au-dessus du nouveau prix d'entrée
    short. Ex. : le long avait un stop à -5% de son entrée -> le short a un
    stop à +5% de sa propre entrée. Choix motivé par l'absence de toute autre
    référence dans la source, et par cohérence avec le principe du profil (le
    même risque nominal en % est repris, pas un risque arbitraire différent).
  - **Cible de la jambe reverse** : MIROIR de la distance (en %) entre l'entrée
    long et son propre niveau Limite, reportée en dessous du nouveau prix
    d'entrée short. Même justification que pour le stop.
  - **Portée** : jambe short BORNÉE (un seul stop, une seule cible), PAS une
    réplique complète de la table à 4 étapes côté short (la source ne décrit
    aucune sous-étape Validation/Confirmation pour la jambe reverse) -- même
    esprit de simplification assumée que H10 de `trend_table.py` pour son
    propre "+Reverse" (table tendance), documentée là comme "implémentation
    SIMPLIFIÉE ... PAS une table symétrique côté short".
  - **Déclenchement de sortie** : stop touché sur la MÈCHE (`high[i] >=
    stop`, ordre réel intrabar, même convention que l'Invalidation long) ;
    cible atteinte sur la CLÔTURE (`c[i] <= target`, même convention que la
    Limite long). Choix : réutiliser EXACTEMENT les deux conventions de
    déclenchement déjà établies pour la jambe long dans ce même fichier,
    plutôt que d'en inventer une troisième pour la jambe short.
  - **Non-goal explicite (documenté, pas caché)** : le moteur ne force AUCUNE
    exclusion mutuelle entre une jambe reverse ouverte et l'ouverture d'une
    NOUVELLE tranche long (par ex. via la pyramidalisation `max_tranches>1`
    d'un autre appelant) -- chaque tranche/jambe reste gérée indépendamment,
    exactement comme les tranches pyramidées entre elles sont déjà
    indépendantes les unes des autres (aucune ne connaît l'état des autres,
    cf. `process_tranche`). Gérer une éventuelle règle "pas de long tant
    qu'un reverse est ouvert" est laissé à la charge de l'appelant (sa propre
    logique de signal dans `open_tranche_fn`/`long_signal`), pas à ce moteur
    générique. De même, `record_trace=True` ne trace PAS les jambes reverse
    (reste un non-goal de ce cycle, `funding_rate_exact.py` n'est pas mis à
    jour pour un coût de funding sur une position short).
"""
import numpy as np
import pandas as pd


def process_tranche(tr, i, o, low, c, long_signal_prev, val_close_frac, conf_close_frac, conf_to_be,
                     reverse_at_limit=False):
    """Fait progresser une tranche ouverte d'un pas de temps `i`. Mute `tr` en place.

    `tr` doit exposer les clés : entry, stop, remaining, val_done, conf_done,
    pnl_accum, val_px, conf_px, lim_px.

    Retourne (closed: bool, fee_frac: float, realized_pnl: float|None).
    `fee_frac` est la fraction du capital (par rapport à la taille initiale
    de la tranche) sur laquelle des frais doivent être prélevés ce pas-ci
    (clôture totale ou partielle). `realized_pnl` est le P&L total de la
    tranche (fraction), renseigné seulement si la tranche se ferme ce pas-ci.

    `reverse_at_limit` (défaut False, AUCUN changement de comportement pour
    tous les appels existants) : si True et que la clôture se fait par la
    Limite, `tr["reverse_request"]` est rempli avec les paramètres de la
    jambe short "+Reverse" (hypothèse H-Reverse-Range, cf. tête de fichier)
    -- charge à l'appelant (`run_position_engine`) de la lire et de l'ouvrir.
    """
    # 1) Limite atteinte -> clôture totale (sur CLÔTURE)
    if c[i] >= tr["lim_px"]:
        remaining_before = tr["remaining"]
        pnl = (c[i] - tr["entry"]) / tr["entry"]
        tr["pnl_accum"] += pnl * remaining_before
        fee_frac = remaining_before
        realized = tr["pnl_accum"]
        tr["remaining"] = 0.0
        if reverse_at_limit:
            stop_pct = (tr["entry"] - tr["stop"]) / tr["entry"]        # H-Reverse-Range : miroir du stop
            gain_pct = (tr["lim_px"] - tr["entry"]) / tr["entry"]      # H-Reverse-Range : miroir de la cible
            r_entry = c[i]
            tr["reverse_request"] = {
                "entry": r_entry,
                "stop": r_entry * (1 + stop_pct),
                "target": r_entry * (1 - gain_pct),
                "remaining": remaining_before,
            }
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


def process_reverse(rp, i, high, low, c):
    """Fait progresser une jambe short "+Reverse" (hypothèse H-Reverse-Range,
    cf. tête de fichier) d'un pas de temps `i`. `rp` (dict avec les clés
    entry/stop/target/remaining) n'est PAS muté -- jambe unique bornée, sans
    état à accumuler entre pas de temps (pas de clôture partielle, contraire
    à `process_tranche`/`tr`).

    Retourne (closed: bool, fee_frac: float, realized_pnl: float|None), même
    convention que `process_tranche`. Short : le P&L est positif quand le
    prix BAISSE (entry - prix_de_sortie).
    """
    # Stop touché -- sur MÈCHE (ordre réel, intrabar), miroir de l'Invalidation long
    if high[i] >= rp["stop"]:
        pnl = (rp["entry"] - rp["stop"]) / rp["entry"]
        return True, rp["remaining"], pnl
    # Cible atteinte -- sur CLÔTURE, miroir de la Limite long
    if c[i] <= rp["target"]:
        pnl = (rp["entry"] - c[i]) / rp["entry"]
        return True, rp["remaining"], pnl
    return False, 0.0, None


def run_position_engine(n, o, high, low, c, long_signal, open_tranche_fn,
                         val_close_frac, conf_close_frac, conf_to_be, max_tranches, fee,
                         update_levels_fn=None, mark_new_tranches=True, same_bar_reentry=True,
                         record_trace=False, reverse_at_limit=False):
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
    - record_trace : si True (défaut False, AUCUN changement de comportement
      ni de résultat numérique pour les appelants existants -- bookkeeping
      additive uniquement), le moteur enregistre en plus une trace par
      trade : bougie d'ouverture, prix d'entrée, et pour chaque bougie où
      le trade est DÉJÀ ouvert (donc PAS sa propre bougie d'ouverture : la
      taille exposée à l'instant même de l'entrée n'est pas retenue comme
      pertinente pour un coût qui suppose une position déjà détenue, ex. le
      funding) un instantané (indice de bougie, taille RESTANTE avant que
      cette bougie ne déclenche une éventuelle clôture partielle
      Validation/Confirmation/stop). Conçu pour `funding_rate_exact.py` :
      la taille exposée à un événement qui tombe pile sur cette bougie est
      exactement cette valeur.
    - reverse_at_limit : défaut False, AUCUN changement de comportement ni de
      résultat numérique pour les appelants existants. Si True, une tranche
      qui se clôture à la Limite ouvre EN PLUS une jambe short "+Reverse"
      (hypothèse H-Reverse-Range, cf. le bloc dédié en tête de fichier). Les
      jambes reverse ouvertes sont gérées dans une liste séparée des tranches
      long, chacune indépendamment (pas de sous-étapes Validation/
      Confirmation, une seule sortie possible : stop ou cible) ; leurs P&L
      réalisés sont ajoutés aux MÊMES statistiques agrégées (n_trades,
      win_rate_%, profit_factor...) que les tranches long, comme des trades
      distincts. `record_trace` ne couvre PAS les jambes reverse (non-goal
      documenté, cf. tête de fichier).

    Retourne un dict avec : n_trades, final_equity, max_dd_%, total_return_%,
    win_rate_%, profit_factor, avg_trade_%, equity_curve (array numpy, pour
    usage interne/diagnostic -- pas forcément exportée en CSV par l'appelant).
    Si `record_trace=True`, ajoute la clé "trace" : liste de dicts
    {trade_id, open_i, close_i, entry_price, realized_pnl, snapshots}, où
    `snapshots` est une liste de tuples (i, remaining_before_bar_i).
    """
    equity = 1.0
    equity_curve = np.empty(n)
    equity_curve[0] = equity
    tranches = []
    reverses = []
    trades = []
    win_streak = 0
    trace = [] if record_trace else None

    for i in range(1, n):
        long_signal_prev = bool(long_signal[i - 1])
        had_open_at_start = len(tranches) > 0
        process_this_step = same_bar_reentry or had_open_at_start

        # Jambes "+Reverse" en cours (indépendant de process_this_step : ce
        # sont des positions short bornées, sans la nuance historique
        # same_bar_reentry/mark_new_tranches propre aux tranches long -- cf.
        # hypothèse H-Reverse-Range en tête de fichier).
        remaining_reverses = []
        for rp in reverses:
            closed_r, fee_frac_r, realized_r = process_reverse(rp, i, high, low, c)
            if closed_r:
                equity *= (1 + realized_r)
            if fee_frac_r > 0:
                equity *= (1 - fee * fee_frac_r)
            if closed_r:
                trades.append(realized_r)
                win_streak = win_streak + 1 if realized_r > 0 else 0
            else:
                remaining_reverses.append(rp)
        reverses = remaining_reverses

        if process_this_step:
            if record_trace:
                for tr in tranches:
                    trace[tr["_trade_id"]]["snapshots"].append((i, tr["remaining"]))
            remaining_tranches = []
            new_reverses = []
            for tr in tranches:
                if update_levels_fn is not None:
                    update_levels_fn(tr, i)
                closed, fee_frac, realized = process_tranche(
                    tr, i, o, low, c, long_signal_prev, val_close_frac, conf_close_frac, conf_to_be,
                    reverse_at_limit=reverse_at_limit,
                )
                if closed:
                    equity *= (1 + realized)
                if fee_frac > 0:
                    equity *= (1 - fee * fee_frac)
                if closed:
                    trades.append(realized)
                    win_streak = win_streak + 1 if realized > 0 else 0
                    if record_trace:
                        trace[tr["_trade_id"]]["close_i"] = i
                        trace[tr["_trade_id"]]["realized_pnl"] = realized
                    rr = tr.get("reverse_request")
                    if rr is not None:
                        new_reverses.append(rr)
                        equity *= (1 - fee * rr["remaining"])  # frais d'ouverture de la jambe reverse
                else:
                    remaining_tranches.append(tr)
            tranches = remaining_tranches
            reverses.extend(new_reverses)
        still_open = list(tranches)  # survivants AVANT l'ouverture éventuelle d'une nouvelle tranche ce pas-ci

        can_open_this_step = (same_bar_reentry or not had_open_at_start) and len(tranches) < max_tranches
        if can_open_this_step:
            new_tr = open_tranche_fn(i, tranches, win_streak)
            if new_tr is not None:
                if record_trace:
                    new_tr["_trade_id"] = len(trace)
                    trace.append({
                        "trade_id": new_tr["_trade_id"], "open_i": i,
                        "entry_price": new_tr["entry"], "entry_size": new_tr["remaining"],
                        "close_i": None, "realized_pnl": None, "snapshots": [],
                    })
                tranches.append(new_tr)
                equity *= (1 - fee * new_tr["remaining"])

        mtm_tranches = tranches if mark_new_tranches else still_open
        unrealized = sum(tr["pnl_accum"] + (c[i] - tr["entry"]) / tr["entry"] * tr["remaining"] for tr in mtm_tranches)
        unrealized += sum((rp["entry"] - c[i]) / rp["entry"] * rp["remaining"] for rp in reverses)
        equity_curve[i] = equity * (1 + unrealized)

    trades_arr = np.array(trades) if trades else np.array([])
    eq_series = pd.Series(equity_curve)
    max_dd = (eq_series / eq_series.cummax() - 1).min()
    result = {
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
    if record_trace:
        result["trace"] = trace
    return result
