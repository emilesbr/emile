"""
Phase 2 — Money management réel (tables extraites du manuel, RULES_EXTRACTION.md),
appliqué sur H4/D1 (timeframes GO de la Phase 1), 4 profils de risque.

Table utilisée : TRADE SPÉCULATIF (range), car le manuel indique qu'on est
en range ~80% du temps et que c'est la table par défaut en cas de doute.
Notre proxy ne distingue pas fiablement range/tendance/accumulation — donc
CE N'EST PAS la table "trade de tendance", qui resterait à tester séparément.

Approximation documentée : les niveaux Validation/Confirmation/Limite/
Invalidation (bornes réelles de canaux dans le PDF) sont approximés par des
multiples d'ATR depuis l'entrée, faute d'accès au vrai canal PRO Framework :
  Validation = +1.0 x ATR   | Confirmation = +2.0 x ATR
  Limite     = +3.5 x ATR   | Invalidation = -2.0 x ATR (stop initial)
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

from emile.core.position_engine import run_position_engine

from emile.config.env_config import DATA_DIR
FEE = 0.0004
ATR_LEN = 14
EMA_FAST, EMA_MID, EMA_SLOW = 8, 21, 55

VALIDATION_MULT = 1.0
CONFIRMATION_MULT = 2.0
LIMITE_MULT = 3.5
INVALIDATION_MULT = -2.0

# Table "trade spéculatif" (range) — RULES_EXTRACTION.md section 3
# Chaque étape : (fraction du RESTANT à clôturer, nouvelle action sur le stop)
# stop_action: 'BE' = breakeven (entry), 'BE_PAYE' = approx. breakeven (simplification
# documentée de "SL payé", qui dans le PDF peut être financé au-delà du BE), None = inchangé
PROFILES = {
    "FAIBLE": {
        "risk_pct": 0.01,
        "validation":   {"close_frac": 0.50, "stop_action": "BE_PAYE"},
        "confirmation": {"close_frac": 0.00, "stop_action": "BE"},
        "invalidation": {"close_frac": 1.00, "stop_action": None},   # TP50%+TP BE -> reste clôturé à BE si atteint, sinon au stop
        "limite_reverse": False,
    },
    "MODERE": {
        "risk_pct": 0.02,
        "validation":   {"close_frac": 0.25, "stop_action": "BE_PAYE"},
        "confirmation": {"close_frac": 0.25, "stop_action": "BE"},
        "invalidation": {"close_frac": 1.00, "stop_action": None},   # TP BE
        "limite_reverse": False,
    },
    "AGRESSIF": {
        "risk_pct": 0.03,
        "validation":   {"close_frac": 0.00, "stop_action": "BE"},
        "confirmation": {"close_frac": 0.50, "stop_action": None},
        "invalidation": {"close_frac": 1.00, "stop_action": None},   # TP BE
        "limite_reverse": False,
    },
    "TRES_AGRESSIF": {
        "risk_pct": 0.05,
        "validation":   {"close_frac": 0.00, "stop_action": None},   # RIEN
        "confirmation": {"close_frac": 0.00, "stop_action": None},   # -
        "invalidation": {"close_frac": 1.00, "stop_action": None},   # RIEN -> stop initial tient lieu d'invalidation
        "limite_reverse": True,                                       # TP100%+Reverse
    },
}

_MIN_H1_ROWS = 1000  # ~6 semaines de bougies 1h -- une vraie serie BTC/ETH/BNB/SOL
                     # couvre des annees (dizaines de milliers de lignes) ; un
                     # stub/placeholder en a typiquement 1-2. Ce seuil ne peut
                     # mordre sur une vraie donnee, seulement sur un fichier
                     # degenere.

def load_h1(symbol: str) -> pd.DataFrame:
    """Trouve par audit (cycle CLAUDE.md "aucune donnee reelle disponible") :
    un fichier de donnees degenere (1 ligne, valeurs fabriquees) a ete commite
    par erreur et lu sans broncher par tous les moteurs -- resultats
    silencieusement vides/nuls, indiscernables a l'oeil d'un vrai "gate
    inerte"/"effet nul" deja frequent dans ce projet. Refuse maintenant
    explicitement plutot que de laisser un moteur produire une sortie
    degeneree qui pourrait ecraser un results/*.csv legitime sans que
    personne ne s'en aperçoive."""
    path = DATA_DIR / f"{symbol}_1h_processed.csv"
    df = pd.read_csv(path, usecols=["datetime", "open", "high", "low", "close"])
    if len(df) < _MIN_H1_ROWS:
        raise ValueError(
            f"{path} ne contient que {len(df)} ligne(s) (< {_MIN_H1_ROWS}) -- "
            f"donnee manifestement absente ou degeneree (stub/placeholder), "
            f"pas une vraie serie 1h. Refus explicite plutot qu'une sortie "
            f"degeneree silencieuse (0-1 trade) qui ressemblerait a un "
            f"resultat honnete. Voir CLAUDE.md, section donnees."
        )
    df["date"] = pd.to_datetime(df["datetime"])
    return df.sort_values("date")[["date", "open", "high", "low", "close"]].reset_index(drop=True)

_MIN_M15_ROWS = 4000  # meme principe que _MIN_H1_ROWS, mis a l'echelle : une
                      # bougie M15 dure 1/4 d'une bougie H1, donc une meme
                      # duree calendaire minimale se traduit par ~4x plus de
                      # lignes (verifie sur la vraie donnee restauree : BTC/
                      # ETH/BNB/SOL font 210 085-245 751 lignes M15 pour
                      # 52 521-61 439 lignes H1 sur la meme periode, ratio
                      # 4,00-4,01x, pas juste suppose). Valeur non inventee :
                      # 1000 x 4 = 4000, meme marge de securite que le seuil
                      # H1 (tres en dessous de tout fichier reel, tres au
                      # dessus d'un stub degenere) exprimee dans l'unite M15.

def load_m15(symbol: str) -> pd.DataFrame:
    """Analogue M15 de `load_h1` -- meme garde-fou anti-stub, seuil mis a
    l'echelle (cf. `_MIN_M15_ROWS`). Donnee M15 native disponible pour BTC/
    ETH/BNB/SOL uniquement (pas XRP) -- cf. `CLAUDE.md`, section donnees."""
    path = DATA_DIR / f"{symbol}_15m_processed.csv"
    df = pd.read_csv(path, usecols=["datetime", "open", "high", "low", "close"])
    if len(df) < _MIN_M15_ROWS:
        raise ValueError(
            f"{path} ne contient que {len(df)} ligne(s) (< {_MIN_M15_ROWS}) -- "
            f"donnee manifestement absente ou degeneree (stub/placeholder), "
            f"pas une vraie serie 15m. Refus explicite plutot qu'une sortie "
            f"degeneree silencieuse (0-1 trade) qui ressemblerait a un "
            f"resultat honnete. Voir CLAUDE.md, section donnees."
        )
    df["date"] = pd.to_datetime(df["datetime"])
    return df.sort_values("date")[["date", "open", "high", "low", "close"]].reset_index(drop=True)

def resample(df, rule):
    r = df.set_index("date").resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return r.reset_index()

def atr(df, length):
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()

def add_score(df):
    df = df.copy()
    close = df["close"]
    ema_f = close.ewm(span=EMA_FAST, adjust=False).mean()
    ema_m = close.ewm(span=EMA_MID, adjust=False).mean()
    ema_s = close.ewm(span=EMA_SLOW, adjust=False).mean()
    df["score"] = (close > ema_f).astype(int) + (ema_f > ema_m).astype(int) + (ema_m > ema_s).astype(int)
    df["atr"] = atr(df, ATR_LEN)
    return df

def run_backtest_mm(df: pd.DataFrame, profile_name: str, external_signal: np.ndarray = None) -> dict:
    """Backtest avec money management par étapes (table trade spéculatif).
    Si external_signal est fourni (array bool), il remplace le signal EMA
    interne (utilisé pour tester des cascades multi-timeframe externes).

    Boucle de gestion de tranche factorisée dans position_engine.py (cf.
    AUDIT_QUALITE_ET_CORRECTION_CYCLE.md, "logique dupliquée dans 3 fichiers"),
    seule la logique d'ENTRÉE (spécifique à ce moteur : stop et niveaux en
    multiples d'ATR, tranche unique, niveaux recalculés à chaque pas à partir
    de l'ATR courant) reste locale à ce fichier."""
    p = PROFILES[profile_name]
    df = add_score(df)
    long_signal = external_signal if external_signal is not None else (df["score"].values >= 2)
    atr_v = df["atr"].values
    high, low, o, c = df["high"].values, df["low"].values, df["open"].values, df["close"].values
    n = len(df)
    warmup = EMA_SLOW + ATR_LEN

    # CORRECTION (Trading Lessons #9/#11/#14, 3 sources convergentes) :
    # Validation/Confirmation/Limite se déclenchent sur CLÔTURES, pas sur
    # mèches ("considérées comme du bruit"). Le stop-loss reste sur mèche :
    # c'est un ordre réel qui se déclenche intrabar. Le passage au
    # break-even est interdit à la Validation (Trading Lessons #12/#13/#15/
    # #16, 7 sources convergentes), autorisé seulement à la Confirmation, et
    # seulement si le profil le prévoit (les profils AGRESSIF/TRES_AGRESSIF
    # de la table "trade spéculatif" ne remontent pas le stop).
    conf_to_be = p["confirmation"]["stop_action"] in ("BE", "BE_PAYE")

    def open_tranche_fn(i, tranches, win_streak):
        if len(tranches) > 0:
            return None
        if not (i > warmup and long_signal[i - 1] and not np.isnan(atr_v[i - 1])):
            return None
        entry_price = o[i]
        a = atr_v[i - 1]
        init_stop = entry_price + INVALIDATION_MULT * a  # a < entry car mult négatif
        stop_pct = (entry_price - init_stop) / entry_price
        size_frac = min(1.0, p["risk_pct"] / stop_pct) if stop_pct > 0 else 0.0
        if size_frac <= 0:
            return None
        return {
            "entry": entry_price, "stop": init_stop, "remaining": size_frac,
            "val_done": False, "conf_done": False, "pnl_accum": 0.0,
            "val_px": entry_price + VALIDATION_MULT * a,
            "conf_px": entry_price + CONFIRMATION_MULT * a,
            "lim_px": entry_price + LIMITE_MULT * a,
        }

    def update_levels_fn(tr, i):
        # Comportement d'origine : les niveaux sont recalculés à chaque pas
        # à partir de l'ATR courant (pas figés à l'entrée).
        a = atr_v[i - 1] if not np.isnan(atr_v[i - 1]) else atr_v[np.isfinite(atr_v)][0]
        tr["val_px"] = tr["entry"] + VALIDATION_MULT * a
        tr["conf_px"] = tr["entry"] + CONFIRMATION_MULT * a
        tr["lim_px"] = tr["entry"] + LIMITE_MULT * a

    raw = run_position_engine(
        n, o, high, low, c, long_signal, open_tranche_fn,
        val_close_frac=p["validation"]["close_frac"],
        conf_close_frac=p["confirmation"]["close_frac"],
        conf_to_be=conf_to_be,
        max_tranches=1,
        fee=FEE,
        update_levels_fn=update_levels_fn,
        mark_new_tranches=False,
        same_bar_reentry=False,
    )
    return {
        "n_trades": raw["n_trades"],
        "final_equity": raw["final_equity"],
        "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"],
        "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
        "avg_trade_%": raw["avg_trade_%"],
    }

def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        for tf_name, df in [("H4", resample(h1, "4h")), ("D1", resample(h1, "1D"))]:
            for profile in PROFILES:
                res = run_backtest_mm(df, profile)
                rows.append({"symbol": symbol, "tf": tf_name, "profile": profile, **res})

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("phase2_moneymanagement_results.csv", index=False)

if __name__ == "__main__":
    main()
