"""
Funding rate analysis — coût du funding Binance Futures pour une position longue permanente.

Source des données : dépôt public GitHub `SpaciousAbhi/binance-futures-backtest-research`
(fichiers `<ASSET>USDT_1h_processed.csv`, colonne `fundingRate`), cloné dans cette session à
/home/user/spaciousabhi/binance-futures-backtest-research/data/processed/.

Méthodologie :
- Le funding sur les perpétuels Binance est prélevé/versé toutes les 8h (~00:00/08:00/16:00 UTC),
  proportionnellement à la valeur notionnelle de la position. Un taux positif = les longs paient
  les shorts ; un taux négatif = les longs reçoivent.
- Dans les CSV sources, `fundingRate` est répété (forward-fill) sur chaque bougie horaire entre
  deux événements réels de funding. Sommer directement la colonne sur toutes les lignes horaires
  compterait chaque paiement ~8 fois. On déduplique donc sur (fundingTime, fundingRate) pour ne
  garder qu'une ligne par événement de funding réel avant de sommer.
- Position simulée : long permanent, taille = 100% du capital, sans levier (cohérent avec la
  convention utilisée dans RULES_EXTRACTION.md / BACKTEST_RESULTS_MTF.md), sans réinvestissement
  des gains (approximation au premier ordre — suffisante pour donner un ordre de grandeur).
- Coût cumulé sur la période = somme des fundingRate des événements réels, exprimé en % du
  capital initial. Le taux annualisé moyen = coût cumulé / nombre d'années couvertes.

Sortie : funding_rate_summary.csv (résumé par actif).
"""
import os
import pandas as pd

from emile.config.env_config import DATA_DIR
ASSETS = {
    "BTC": "BTCUSDT_1h_processed.csv",
    "ETH": "ETHUSDT_1h_processed.csv",
    "BNB": "BNBUSDT_1h_processed.csv",
    "SOL": "SOLUSDT_1h_processed.csv",
}

OUT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "funding_rate_summary.csv")

def analyze_asset(asset: str, fname: str) -> dict:
    path = os.path.join(DATA_DIR, fname)
    df = pd.read_csv(path, usecols=["fundingTime", "fundingRate", "datetime_str"])

    # Un événement de funding réel = un couple (fundingTime, fundingRate) distinct.
    events = df.drop_duplicates(subset=["fundingTime", "fundingRate"]).copy()
    events["datetime_str"] = pd.to_datetime(events["datetime_str"])

    start, end = events["datetime_str"].min(), events["datetime_str"].max()
    n_days = (end - start).days
    n_years = n_days / 365.25
    n_events = len(events)
    expected_events = n_days * 3  # 3 fenêtres de funding par jour (toutes les 8h)
    coverage_pct = 100 * n_events / expected_events if expected_events else float("nan")

    cum_funding_pct = events["fundingRate"].sum() * 100  # % du capital, long permanent 1x
    annualized_pct = cum_funding_pct / n_years

    pos_events = int((events["fundingRate"] > 0).sum())
    neg_events = int((events["fundingRate"] < 0).sum())

    return {
        "asset": asset,
        "start": start.date().isoformat(),
        "end": end.date().isoformat(),
        "years_covered": round(n_years, 2),
        "n_funding_events": n_events,
        "coverage_vs_expected_pct": round(coverage_pct, 1),
        "pct_events_long_pays": round(100 * pos_events / n_events, 1),
        "pct_events_long_receives": round(100 * neg_events / n_events, 1),
        "cumulative_funding_pct_of_capital": round(cum_funding_pct, 2),
        "annualized_pct_of_capital_per_year": round(annualized_pct, 2),
    }

def main():
    rows = [analyze_asset(asset, fname) for asset, fname in ASSETS.items()]
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(result.to_string(index=False))
    result.to_csv(OUT_CSV, index=False)
    print(f"\nRésumé écrit dans {OUT_CSV}")

if __name__ == "__main__":
    main()
