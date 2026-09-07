"""
Coût de funding EXACT par timestamp — item 5 du backlog (`PLAN.md`), succède
à `funding_rate_analysis.py` (racine du dépôt) qui ne donnait qu'un ordre de
grandeur ANNUALISÉ (position longue permanente, 100% du capital, sans lien
avec les trades réels du moteur de risque).

Ce module calcule le coût RÉEL, événement par événement (funding réel toutes
les 8h, dédupliqué comme dans `funding_rate_analysis.py`), appliqué à la
taille RÉELLE de chaque trade individuel à chaque instant (donc réduite par
les sorties partielles Validation/Confirmation), en s'appuyant sur la trace
optionnelle ajoutée à `position_engine.run_position_engine`
(`record_trace=True`, cf. sa docstring) exposée par `backtest_phase2_v7.run_v7`.

Convention explicite (documentée, pas cachée) : le coût de funding d'un
événement est calculé comme
    taille_restante_avant_la_bougie × taux_de_funding_réel_de_cet_événement
où `taille_restante` est exprimée dans la MÊME unité que `remaining` dans
position_engine.py (fraction du capital total alloué au trade à l'entrée,
PAS une valeur notionnelle remarquée au prix courant). C'est la même
convention que celle déjà utilisée pour les frais de transaction dans
position_engine.py (`fee * fee_frac`, sur `remaining`, sans reprix au
marché) -- on ne réinvente donc pas une deuxième convention de sizing dans
ce fichier. Limite explicitement assumée : le funding réel s'applique en
pratique à une valeur notionnelle qui croît/décroît avec le prix (nombre de
contrats fixe, valeur = contrats × prix) ; l'approximation ici revient à
identifier `remaining` à un montant constant plutôt qu'à un notionnel
remarqué -- écart mineur pour des rendements bornés (<< 100%) sur la durée
d'un seul trade, mais à ne pas prétendre nul.

Une bougie H4 correspond à un événement de funding réel si et seulement si
son timestamp (heure UTC) tombe sur 00:00/08:00/16:00 -- vérifié
empiriquement : le nombre de bougies H4 BTC à heure%8==0 sur toute la
période (7120) correspond EXACTEMENT au nombre d'événements de funding réels
dédupliqués rapporté dans FUNDING_RATE_ANALYSIS.md (7120) -- donc aucun
recalage/tolérance n'est nécessaire, une simple jointure exacte sur le
timestamp suffit.
"""
import os
from collections import defaultdict

import numpy as np
import pandas as pd

DATA_DIR = "/home/user/spaciousabhi/binance-futures-backtest-research/data/processed"


def load_funding_events(symbol: str, data_dir: str = DATA_DIR) -> pd.Series:
    """Événements de funding RÉELS pour `symbol` (ex. "BTCUSDT"), dédupliqués
    sur (fundingTime, fundingRate) -- même méthode que `funding_rate_analysis.py`
    (le CSV source répète `fundingRate` en forward-fill sur chaque bougie
    horaire entre deux événements réels : sommer/appliquer sans dédupliquer
    compterait chaque paiement ~8 fois).

    Retourne une pd.Series indexée par timestamp UTC tz-aware (issu de
    `fundingTime`, en ms), valeurs = taux de funding réel de l'événement.
    """
    path = os.path.join(data_dir, f"{symbol}_1h_processed.csv")
    df = pd.read_csv(path, usecols=["fundingTime", "fundingRate"])
    events = df.drop_duplicates(subset=["fundingTime", "fundingRate"]).copy()
    events["ts"] = pd.to_datetime(events["fundingTime"], unit="ms", utc=True)
    events = events.sort_values("ts")
    return events.set_index("ts")["fundingRate"]


def attach_funding_rate(dates, funding_events: pd.Series) -> np.ndarray:
    """Pour chaque timestamp de bougie `dates` (H4 ou D1), renvoie le taux de
    funding réel si ce timestamp correspond EXACTEMENT à un événement de
    funding réel, sinon 0.0. `dates` peut être tz-naive (alors supposé UTC,
    convention du reste du projet -- `load_h1` construit `date` depuis une
    colonne déjà UTC) ou tz-aware (alors converti en UTC).
    """
    s = pd.to_datetime(pd.Series(np.asarray(dates)))
    if s.dt.tz is None:
        s = s.dt.tz_localize("UTC")
    else:
        s = s.dt.tz_convert("UTC")
    rates = s.map(funding_events)
    return rates.fillna(0.0).values


def compute_funding_cost_per_trade(trace: list, funding_rate_arr: np.ndarray) -> list:
    """Coût de funding exact par trade, à partir de la trace de
    `run_position_engine(..., record_trace=True)` et du taux de funding réel
    par bougie (`attach_funding_rate`).

    Pour chaque trade, combine MULTIPLICATIVEMENT (pas additivement) les
    facteurs (1 - taille_avant_bougie × taux) de chaque événement de funding
    réel qui tombe pendant sa détention -- cohérent avec la façon dont
    `position_engine.py` applique déjà les frais (`equity *= (1 - fee *
    fee_frac)`), et exact (pas juste une approximation au premier ordre) :
    l'écart entre "multiplier" et "sommer les coûts" est le terme croisé
    (produit de deux coûts), totalement négligeable ici (taux de funding
    réels de l'ordre de 0,01%-0,05%, tailles de position de quelques % du
    capital -> terme croisé de l'ordre de 1e-8 ou moins) mais on ne prend
    pas ce raccourci par principe : le calcul exact ne coûte rien de plus.

    Retourne une liste de dicts : trade_id, open_i, close_i, realized_pnl
    (SANS funding, déjà calculé par le moteur), funding_cost_%_of_capital
    (coût cumulé du trade, en % du capital, pour lecture directe -- calculé
    en 1 - multiplicateur, donc lui aussi exact), n_funding_events,
    funding_multiplier, realized_pnl_net_of_funding (le vrai P&L net, en
    recombinant multiplicativement avec le P&L brut : (1+réalisé) ×
    multiplicateur - 1).
    """
    out = []
    for tr in trace:
        multiplier = 1.0
        n_events = 0
        for i, size_before in tr["snapshots"]:
            rate = funding_rate_arr[i]
            if rate != 0.0:
                multiplier *= (1 - size_before * rate)
                n_events += 1
        realized = tr["realized_pnl"] if tr["realized_pnl"] is not None else 0.0
        realized_net = (1 + realized) * multiplier - 1
        out.append({
            "trade_id": tr["trade_id"],
            "open_i": tr["open_i"],
            "close_i": tr["close_i"],
            "entry_size": tr.get("entry_size"),
            "realized_pnl": realized,
            "n_funding_events": n_events,
            "funding_multiplier": multiplier,
            "funding_cost_%_of_capital": round((1 - multiplier) * 100, 6),
            "realized_pnl_net_of_funding": realized_net,
        })
    return out


def apply_funding_to_equity(final_equity_gross: float, per_trade_costs: list) -> dict:
    """Recombine le coût de funding exact (par trade, `compute_funding_cost_per_trade`)
    à l'équity finale déjà calculée SANS funding par `run_position_engine`/`run_v7`.

    Légitime par simple multiplication de scalaires (résultat EXACT, pas une
    approximation) : chaque coût de funding est appliqué comme un facteur
    multiplicatif supplémentaire sur l'équity (`equity *= (1 - coût)`), tout
    comme les frais de transaction déjà présents dans le moteur. Le sizing
    de ce moteur (`risk_pct / stop_pct`, cf. `backtest_phase2_v7.py`) ne
    dépend PAS de l'équity courante (fraction fixe du capital ORIGINAL à
    chaque trade, pas de compounding réinjecté dans la taille des trades
    suivants) -- donc le produit de tous les facteurs multiplicatifs
    (trades + frais + funding) est commutatif/associatif : l'équity finale
    nette de funding est EXACTEMENT
        équity_finale_brute × produit_sur_tous_les_trades(funding_multiplier)
    quel que soit l'ordre chronologique réel d'application des événements de
    funding entre trades (produit de scalaires). SEUL le retour TOTAL est
    donc recalculé de façon exacte ici -- la courbe d'équity intermédiaire
    (et donc `max_dd_%`) n'est PAS recalculée avec le funding interpolé
    chronologiquement dans la boucle du moteur (limite déclarée, cf.
    FUNDING_RATE_ANALYSIS.md, section funding exact) : la reconstituer
    demanderait de faire tourner le funding DANS `run_position_engine`
    lui-même plutôt qu'en post-traitement de sa trace, hors scope de ce
    chantier (aucune campagne de résultats du projet ne rapporte le max_dd
    comme un chiffre déjà "net de funding").
    """
    total_multiplier = 1.0
    for t in per_trade_costs:
        total_multiplier *= t["funding_multiplier"]
    final_equity_net = final_equity_gross * total_multiplier
    return {
        "total_funding_cost_%_of_capital": round((1 - total_multiplier) * 100, 3),
        "final_equity_net_of_funding": final_equity_net,
        "total_return_%_net_of_funding": round((final_equity_net - 1) * 100, 1),
    }


def run_with_exact_funding(symbol: str, h4, d1, profile_name: str, run_v7_fn) -> dict:
    """Rejoue `run_v7_fn(h4, d1, profile_name, record_trace=True)` (typiquement
    `backtest_phase2_v7.run_v7`) et lui applique le coût de funding exact.

    Retourne un dict comparant : retour SANS funding (déjà rapporté partout
    ailleurs dans le projet), retour AVEC funding exact (ce module), et
    l'estimation grossière ANNUALISÉE précédente (FUNDING_RATE_ANALYSIS.md)
    reproduite ici pour comparaison directe -- même actif, même profil, même
    durée moyenne de détention MESURÉE sur CE run (pas approximée comme dans
    le document d'origine).
    """
    r = run_v7_fn(h4, d1, profile_name, record_trace=True)
    funding_events = load_funding_events(f"{symbol}USDT")
    funding_rate_arr = attach_funding_rate(r["dates"], funding_events)
    per_trade = compute_funding_cost_per_trade(r["trace"], funding_rate_arr)
    agg = apply_funding_to_equity(r["final_equity"], per_trade)

    n_trades = len(per_trade)
    avg_size = float(np.mean([t["entry_size"] for t in per_trade])) if n_trades else 0.0
    holding_bars = [t["close_i"] - t["open_i"] for t in per_trade if t["close_i"] is not None]
    avg_holding_h4_bars = float(np.mean(holding_bars)) if holding_bars else 0.0
    avg_holding_days = avg_holding_h4_bars * 4 / 24.0

    # Estimation grossière ANNUALISÉE (méthode de FUNDING_RATE_ANALYSIS.md,
    # section "Rapprochement") -- calculée ici avec le vrai taux annualisé
    # de l'actif (funding_events, tout l'historique dispo) et la vraie durée
    # moyenne de détention MESURÉE sur ce run (pas une approximation
    # `durée_totale/n_trades`, déjà plus fine que le document d'origine sur
    # ce point précis), mais reste une approximation au 1er ordre : taux
    # annualisé moyen constant, appliqué uniforme à chaque trade au prorata
    # de sa durée, sans tenir compte du taux RÉEL en vigueur pendant CHAQUE
    # fenêtre de détention ni des sorties partielles qui réduisent la taille
    # en cours de route -- exactement ce que ce module corrige.
    n_years = (funding_events.index.max() - funding_events.index.min()).days / 365.25
    annualized_rate_pct = funding_events.sum() * 100 / n_years
    rough_cost_pct_per_trade = annualized_rate_pct / 365.0 * avg_holding_days * avg_size
    rough_total_cost_pct = rough_cost_pct_per_trade * n_trades
    rough_equity_net = r["final_equity"] * (1 - rough_total_cost_pct / 100.0)
    rough_return_pct = round((rough_equity_net - 1) * 100, 1)

    return {
        "symbol": symbol, "profile": profile_name,
        "n_trades": n_trades,
        "avg_position_size_%_of_capital": round(avg_size * 100, 3),
        "avg_holding_days": round(avg_holding_days, 2),
        "annualized_funding_rate_%_per_year": round(annualized_rate_pct, 2),
        "total_return_%_sans_funding": r["total_return_%"],
        "total_return_%_funding_exact": agg["total_return_%_net_of_funding"],
        "total_funding_cost_%_of_capital_exact": agg["total_funding_cost_%_of_capital"],
        "total_return_%_estimation_grossiere_annualisee": rough_return_pct,
        "ecart_exact_vs_grossier_pts": round(
            agg["total_return_%_net_of_funding"] - rough_return_pct, 1
        ),
    }


def main():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from backtest_phase2 import load_h1, resample
    from backtest_phase2_v7 import run_v7, PROFILES_V4

    symbols = ["BTC", "ETH", "BNB", "SOL"]
    profiles = list(PROFILES_V4.keys())
    rows = []
    for symbol in symbols:
        h1 = load_h1(f"{symbol}USDT")
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        for profile in profiles:
            rows.append(run_with_exact_funding(symbol, h4.copy(), d1.copy(), profile, run_v7))

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "funding_rate_exact_vs_v7_results.csv")
    result.to_csv(out_path, index=False)
    print(f"\nRésultats écrits dans {out_path}")


if __name__ == "__main__":
    main()
