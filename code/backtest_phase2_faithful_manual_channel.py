"""
Phase 2 FIDÈLE — canal manuel (Supports->Apex->Tangente) reconstruit SUR D1
comme stop RANGE, plutôt que la bande EMA+/-ATR D1 utilisée jusqu'ici dans
`backtest_phase2_faithful.py`.

PROBLÈME TRAITÉ (limite documentée explicitement en tête de
`backtest_phase2_faithful.py`, section "CE QUI RESTE VOLONTAIREMENT NON
COMBINÉ ICI", point "Canal manuel comme stop") : la règle littérale du stop
dit *"clôture la plus basse... du canal de tendance de l'UT+1"*
(`TRADING_LESSONS_BREAKOUT_RATIO11.md` #12) -- le TIMEFRAME SUPÉRIEUR (D1
quand l'exécution est H4). `manual_trend_channel.py` EST une reconstruction
géométrique littérale du "vrai" canal de tendance du corpus (Supports/Apex/
Tangente, `TRADING_LESSONS_ALTERNATIVE_MANUELLE.md` #3), mais n'avait
jusqu'ici jamais été calculée SUR D1 (`backtest_phase2_patterns.py` ne le
mesure que sur H4 -- le même timeframe que l'exécution, ce qui ne correspond
pas au rôle "UT+1" du stop). Ce fichier construit le canal manuel sur D1 et
l'utilise comme source du stop UT+1, EN PLUS du stop EMA+/-ATR D1 déjà en
place -- les deux sont mesurés côte à côte, aucun ne remplace silencieusement
l'autre (cf. section "CE QUE CE FICHIER NE TRANCHE PAS" ci-dessous).

VÉRIFICATION PRÉALABLE (étape 1 de la tâche) -- `add_manual_trend_channel_
columns` (`manual_trend_channel.py`) est-il applicable à un DataFrame D1 SANS
modification ?
  OUI, sans aucune modification. Vérifié, pas supposé :
  - `compute_manual_trend_channel` ne lit que les colonnes `low`/`high` d'un
    DataFrame générique (aucune colonne ni fréquence H4-spécifique).
  - Le swing low confirmé dont dépend la construction (`proxy_v2.
    compute_swing_low_confirmed`, réutilisé tel quel) compte des BARRES
    (`order=3` barres avant/après, `argrelextrema(..., order=order)`),
    jamais une durée calendaire -- documenté explicitement en tête de
    `proxy_v2.py` ("PAS besoin de recalculer... on décale seulement le
    moment où [le résultat] a le droit d'être consommé"). Le passage de H4
    à D1 change seulement CE QUE représentent 3 barres (12h -> 3 jours),
    jamais la mécanique de calcul elle-même.
  - Le fichier `manual_trend_channel.py` lui-même le démontre déjà dans son
    propre bloc `__main__` (`resample(load_h1("BTCUSDT"), "1D")` suivi
    directement de `add_manual_trend_channel_columns(df)`) -- preuve
    d'exécution existante, pas une supposition de notre part ce cycle.
  - Confirmé empiriquement sur les 4 actifs de ce fichier (cf. tableau de
    couverture ci-dessous) : le canal se construit sur D1 avec un taux de
    couverture élevé (97,8%-99,5% des bougies), pas d'échec structurel.
  Aucun changement n'est donc nécessaire à `manual_trend_channel.py` --
  utilisé ici strictement tel quel, seul le DataFrame passé en argument
  change (D1 au lieu de H4).

CE QUE CE FICHIER NE TRANCHE PAS (par construction, pas un oubli) : le
corpus ne précise PAS lequel des deux stops D1 (bande EMA+/-ATR vs canal
géométrique manuel) prime si les deux diffèrent une fois la tendance
haussière confirmée par 2 creux ascendants. Ce fichier ne choisit PAS
silencieusement -- il expose les deux variantes cote a cote
(`run_faithful_ema_atr_d1` = le stop déjà en place dans `faithful.py`,
inchangé ; `run_faithful_manual_channel_d1` = le nouveau stop géométrique)
et un `main()` qui les mesure HONNÊTEMENT l'une contre l'autre, walk-forward
annuel BTC/ETH/BNB/SOL x 4 profils, SANS que le résultat chiffré ne serve à
choisir un défaut -- rappel direct de l'utilisateur, ce cycle : *"nous ne
nous fions pas aux résultats du Proxy [pour décider d']utiliser ou non la
propriété intellectuelle de Philippe, nous l'utilisons dans tous les cas."*
Les deux stops sont des lectures littérales valides du même rôle (stop
UT+1) -- la performance mesurée ici documente ce qui se passe, elle ne
départage pas laquelle "est" la bonne lecture.

NE RÉIMPLÉMENTE RIEN : réutilise `backtest_phase2_faithful.py::_prepare_
features`/`_run_core` tels quels (la boucle de position, `run_position_
engine`/`make_open_tranche_fn`, N'EST PAS touchée -- seule la SOURCE du
stop D1 change, substituée dans une copie du dict `feat` avant l'appel à
`_run_core`, exactement le même dict que `faithful.py` construit et
consomme). `manual_trend_channel.py::add_manual_trend_channel_columns` et
`backtest_phase2_v7.py::prepare` sont réutilisés tels quels pour construire
le canal D1. La jointure cross-timeframe D1->H4 sans lookahead réutilise
EXACTEMENT le même mécanisme (`merge_asof`, `direction="backward"`,
`available_at = date + CLOSURE_DELAY`) que `backtest_phase2_ut2.py::
attach_context_level` -- non réutilisable telle quelle car elle est câblée
sur la colonne fixe `ctx_support` (bande EMA+/-ATR), alors qu'il faut ici
joindre `channel_support` (canal manuel) -- donc réécrite ici à l'identique
pour cette seule colonne, pas une nouvelle logique de jointure.

NE MODIFIE AUCUN FICHIER DE PRODUCTION EXISTANT : `backtest_phase2_
faithful.py`, `manual_trend_channel.py`, `unified_protocol.py` restent
inchangés."""
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, ".")

from backtest_phase2 import load_h1, resample
from backtest_phase2_v7 import prepare, PROFILES_V4, MAX_TRANCHES
from backtest_phase2_ut2 import CLOSURE_DELAY
from backtest_phase2_faithful import _prepare_features, _run_core
from manual_trend_channel import add_manual_trend_channel_columns, SWING_ORDER
from capital_tiers import effective_sizing

STOP_VARIANTS = ("ema_atr_d1", "manual_channel_d1")


def _attach_channel_support_d1(h4_dates: np.ndarray, d1_with_channel: pd.DataFrame,
                                closure_delay: pd.Timedelta = CLOSURE_DELAY) -> np.ndarray:
    """Jointure D1->H4 sans lookahead pour `channel_support` (canal manuel),
    même mécanique EXACTE que `backtest_phase2_ut2.py::attach_context_level`
    (`merge_asof`, `direction="backward"`, `available_at = date +
    closure_delay`) -- réécrite ici seulement parce que cette dernière est
    câblée sur la colonne fixe `ctx_support`, pas parce que la logique
    temporelle change. `h4_dates` : `feat["date"]` déjà calculé par
    `_prepare_features` (pas besoin de refournir tout le DataFrame H4)."""
    high = d1_with_channel[["date", "channel_support"]].copy()
    high["available_at"] = high["date"] + closure_delay
    high = high.sort_values("available_at")
    # `feat["date"]` (construit par `_prepare_features` via `h4["date"].values`)
    # perd le fuseau UTC porté par la colonne `date` d'origine (comportement
    # documenté de `.values` sur une Series tz-aware) -- remis en UTC ici
    # (mêmes instants, pas une conversion) pour que `merge_asof` compare des
    # types de clé homogènes avec `d1_with_channel["date"]`, resté tz-aware.
    h4_dates_utc = pd.to_datetime(h4_dates, utc=True)
    low = pd.DataFrame({"date": h4_dates_utc}).sort_values("date")
    merged = pd.merge_asof(
        low, high, left_on="date", right_on="available_at", direction="backward",
    )
    return merged["channel_support"].values


def _prepare_features_manual_channel_d1(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame,
                                         use_mtf_gate: bool = True, order: int = SWING_ORDER) -> dict:
    """Même dict `feat` que `backtest_phase2_faithful.py::_prepare_features`
    (score/atr/gate/Wall Street/stop D1 EMA+/-ATR -- calculés à l'identique,
    par appel direct, PAS recopiés), avec une clé ADDITIONNELLE : `ctx_
    support_d1_manual_channel`, le canal manuel (Supports->Apex->Tangente)
    calculé SUR D1 (`order` barres D1, pas H4) puis joint au H4 sans
    lookahead. Les deux sources de stop D1 coexistent dans le même dict --
    aucune des deux n'écrase l'autre ici (cf. `_run_core_manual_channel`
    pour la bascule explicite vers l'une ou l'autre)."""
    feat = _prepare_features(h4, d1, weekly, use_mtf_gate=use_mtf_gate)
    d1_channel = add_manual_trend_channel_columns(prepare(d1.copy()), order=order)
    feat = dict(feat)
    feat["ctx_support_d1_manual_channel"] = _attach_channel_support_d1(feat["date"], d1_channel)
    feat["_d1_channel_coverage_pct"] = float(d1_channel["channel_support"].notna().mean() * 100)
    return feat


def _run_core_manual_channel(feat: dict, profile_name: str, risk_pct: float = None,
                              start: int = 0, end: int = None, record_trace: bool = False) -> dict:
    """`_run_core` de `faithful.py`, INCHANGÉ, appelé sur une copie du dict
    `feat` où SEULE la clé `ctx_support_d1` (consommée par `_run_core`
    comme stop UT+1) est remplacée par le canal manuel D1 --
    `make_open_tranche_fn`/`run_position_engine` ne sont jamais réimportés
    ni réécrits ici, la boucle de position est celle de `faithful.py`."""
    feat_manual = dict(feat)
    feat_manual["ctx_support_d1"] = feat["ctx_support_d1_manual_channel"]
    return _run_core(feat_manual, profile_name, risk_pct=risk_pct, start=start, end=end, record_trace=record_trace)


def run_faithful_ema_atr_d1(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame, profile_name: str,
                             capital_eur: float = None, record_trace: bool = False,
                             use_mtf_gate: bool = True) -> dict:
    """Stop D1 EMA+/-ATR déjà en place -- alias direct de `backtest_phase2_
    faithful.py::run_faithful`, gardé ici sous ce nom pour que le `main()`
    de ce fichier compare deux fonctions au nom symétrique (`..._ema_atr_d1`
    vs `..._manual_channel_d1`), pas pour changer son comportement."""
    feat = _prepare_features(h4, d1, weekly, use_mtf_gate=use_mtf_gate)
    risk_pct = None
    if capital_eur is not None:
        sizing = effective_sizing(capital_eur, profile_name, PROFILES_V4, MAX_TRANCHES)
        risk_pct = sizing.risk_pct
    return _run_core(feat, profile_name, risk_pct=risk_pct, record_trace=record_trace)


def run_faithful_manual_channel_d1(h4: pd.DataFrame, d1: pd.DataFrame, weekly: pd.DataFrame, profile_name: str,
                                    capital_eur: float = None, record_trace: bool = False,
                                    use_mtf_gate: bool = True, order: int = SWING_ORDER) -> dict:
    """Point d'entrée principal de ce fichier -- même moteur RANGE que
    `run_faithful` (`faithful.py`), SEULE différence : le stop UT+1 vient du
    canal manuel (Supports->Apex->Tangente) construit SUR D1, pas de la
    bande EMA+/-ATR D1."""
    feat = _prepare_features_manual_channel_d1(h4, d1, weekly, use_mtf_gate=use_mtf_gate, order=order)
    risk_pct = None
    if capital_eur is not None:
        sizing = effective_sizing(capital_eur, profile_name, PROFILES_V4, MAX_TRANCHES)
        risk_pct = sizing.risk_pct
    return _run_core_manual_channel(feat, profile_name, risk_pct=risk_pct, record_trace=record_trace)


def yearly_breakdown_both(symbol: str) -> list:
    """Walk-forward annuel, MÊME méthode que `walkforward_faithful.py`
    (équité repartant à 1.0 chaque année civile, objectif "année
    catastrophique ?", pas un cumul réaliste) -- les DEUX variantes de stop
    D1 sont calculées UNE SEULE FOIS sur tout l'historique puis découpées
    aux mêmes frontières d'année, pour les 4 profils."""
    h1 = load_h1(symbol)
    h4 = resample(h1, "4h")
    d1 = resample(h1, "1D")
    weekly = resample(h1, "W")
    feat_ema = _prepare_features(h4.copy(), d1.copy(), weekly.copy())
    feat_manual = _prepare_features_manual_channel_d1(h4.copy(), d1.copy(), weekly.copy())
    coverage_pct = feat_manual["_d1_channel_coverage_pct"]

    dates = pd.to_datetime(feat_ema["date"])
    years = sorted(dates.year.unique())
    rows = []
    for profile in PROFILES_V4:
        for y in years:
            idx = np.where(dates.year == y)[0]
            if len(idx) == 0:
                continue
            start, end = int(idx[0]), int(idx[-1]) + 1
            res_ema = _run_core(feat_ema, profile, start=start, end=end)
            res_manual = _run_core_manual_channel(feat_manual, profile, start=start, end=end)
            rows.append({
                "symbol": symbol, "profile": profile, "year": int(y), "n_bars": end - start,
                "d1_channel_coverage_%": round(coverage_pct, 2),
                "ema_atr_d1_n_trades": res_ema["n_trades"],
                "ema_atr_d1_max_dd_%": res_ema["max_dd_%"],
                "ema_atr_d1_total_return_%": res_ema["total_return_%"],
                "ema_atr_d1_win_rate_%": res_ema["win_rate_%"],
                "ema_atr_d1_profit_factor": res_ema["profit_factor"],
                "manual_channel_d1_n_trades": res_manual["n_trades"],
                "manual_channel_d1_max_dd_%": res_manual["max_dd_%"],
                "manual_channel_d1_total_return_%": res_manual["total_return_%"],
                "manual_channel_d1_win_rate_%": res_manual["win_rate_%"],
                "manual_channel_d1_profit_factor": res_manual["profit_factor"],
            })
    return rows


def main():
    """Mesure honnête, walk-forward annuel BTC/ETH/BNB/SOL x 4 profils,
    stop D1 EMA+/-ATR vs stop D1 canal manuel, côte à côte -- AUCUNE
    conclusion de ce `main()` ne sert à choisir un défaut (cf. tête de
    fichier) : le résultat est rapporté tel quel, meilleur ou pire pour
    l'une ou l'autre variante, pas maquillé ni tranché silencieusement."""
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        rows.extend(yearly_breakdown_both(symbol))
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    print(result.to_string(index=False))
    result.to_csv("backtest_phase2_faithful_manual_channel_walkforward_results.csv", index=False)

    print("\nCouverture du canal manuel D1 (% de bougies D1 avec un canal construit), par actif :")
    for symbol in symbols:
        sub = result[result["symbol"] == symbol]
        if len(sub) == 0:
            continue
        print(f"  {symbol}: {sub['d1_channel_coverage_%'].iloc[0]}%")

    print("\n% d'années négatives par variante de stop, par actif x profil (agrégé profils) :")
    for symbol in symbols:
        sub = result[result["symbol"] == symbol]
        neg_ema = (sub["ema_atr_d1_total_return_%"] < 0).sum()
        neg_manual = (sub["manual_channel_d1_total_return_%"] < 0).sum()
        print(f"  {symbol}: EMA+/-ATR D1 {neg_ema}/{len(sub)} négative(s) -- Canal manuel D1 {neg_manual}/{len(sub)} négative(s)")

    print("\nRetour total moyen (toutes années x profils confondus) :")
    print(f"  EMA+/-ATR D1     : {result['ema_atr_d1_total_return_%'].mean():.2f}%")
    print(f"  Canal manuel D1  : {result['manual_channel_d1_total_return_%'].mean():.2f}%")
    print("\nDrawdown max moyen (toutes années x profils confondus) :")
    print(f"  EMA+/-ATR D1     : {result['ema_atr_d1_max_dd_%'].mean():.2f}%")
    print(f"  Canal manuel D1  : {result['manual_channel_d1_max_dd_%'].mean():.2f}%")


if __name__ == "__main__":
    main()
