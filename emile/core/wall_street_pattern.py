"""
Règle "Wall Street" (structure en élargissement = abstention totale) —
backlog `PLAN.md` item 7, `COUVERTURE_ENSEIGNEMENTS.md` ligne "Règle Wall
Street" (sources #3, #4).

Définition exacte extraite des 2 sources (pas supposée) :
  - #3 (`TRADING_LESSONS_ALTERNATIVE_MANUELLE.md`, §3, "Règle d'arrêt
    global (NOUVELLE, absente du PDF officiel)") : structure "en
    élargissement" — "le marché casse résistances PUIS supports
    successivement. Dans ce cas, aucun algorithme ne fonctionne ; si les
    outils de tendance ET de range sont invalidés successivement, tout
    arrêter. Le fait que l'outil échoue est lui-même un signal."
  - #4 (`TRADING_LESSONS_ANALYSE_SANS_INDICATEURS.md`, "Nouveauté 2",
    nomme le pattern) : "Scénario Wall Street" = "Structure en
    élargissement (cassure successive résistances PUIS supports) = aucun
    outil, algorithmique ou manuel, ne peut naviguer sereinement. Seule
    réponse : abstention totale."

Les 2 sources décrivent le MÊME pattern de marché sous 2 formulations
(#3 sans nom, #4 le nomme "Wall Street") : le marché casse un plus haut
significatif ET, dans la même période, casse aussi un plus bas
significatif — les deux bornes du "canal" (range ou tendance) explosent
simultanément vers l'extérieur. C'est la définition d'une structure
"broadening"/"megaphone" (sommets de plus en plus hauts ET creux de plus
en plus bas EN MÊME TEMPS) — ni les outils de range (Bollinger/Pitchfork,
aveugles si une tendance s'en extrait, §3) ni les outils de tendance
(canaux/Supply Channels, faux signaux de sortie en compression, §3) ne
peuvent alors fonctionner, d'où l'abstention totale prescrite (pas une
simple prudence — aucune des 2 sources ne mentionne de sizing réduit ou
de condition partielle, seulement un arrêt complet).

Aucune des 2 sources ne donne de définition NUMÉRIQUE (combien de bornes,
sur quelle fenêtre) — HYPOTHÈSE D'IMPLÉMENTATION explicite (H1, comme les
autres agents du projet documentent leurs hypothèses quand le corpus est
sous-spécifié) : "sommets de plus en plus hauts ET creux de plus en plus
bas simultanément" est traduit ici par la comparaison des 2 DERNIERS swing
highs confirmés (2e > 1er) ET des 2 DERNIERS swing lows confirmés (2e <
1er), en réutilisant EXACTEMENT la même détection causale de swing que
`proxy_v2.py::compute_ascending_lows` (`compute_swing_high_confirmed`/
`compute_swing_low_confirmed`, même `SWING_ORDER`) — pas une nouvelle
détection de pivot ad hoc. C'est la traduction la plus littérale possible
de "casse résistances PUIS supports successivement" : le prix vient de
franchir son swing high précédent (nouvelle résistance cassée) ET son
swing low précédent (nouveau support cassé), au sens de la structure de
marché confirmée la plus récente des deux côtés — pas nécessairement dans
un ordre chronologique strict alterné (le corpus ne précise pas cet
ordre), mais la conjonction des deux élargissements simultanés.
"""
import numpy as np
import pandas as pd
import sys

from emile.core.proxy_v2 import compute_swing_low_confirmed, compute_swing_high_confirmed

# Cohérent avec proxy_v2.SWING_ORDER (même détection de swing réutilisée).
SWING_ORDER = 3

def compute_broadening_structure(df: pd.DataFrame, order: int = SWING_ORDER) -> tuple:
    """Calcule, bougie par bougie, 3 arrays booléens CAUSAUX :
      - `higher_highs[t]` : vrai ssi les 2 derniers swing highs CONFIRMÉS à
        l'instant t forment une séquence ascendante (2e > 1er) — même
        principe que `compute_ascending_lows`, appliqué aux sommets.
      - `lower_lows[t]` : vrai ssi les 2 derniers swing lows CONFIRMÉS à
        l'instant t forment une séquence descendante (2e < 1er).
      - `broadening[t]` = `higher_highs[t]` ET `lower_lows[t]` — la
        structure en élargissement elle-même (cf. docstring de tête).

    CAUSAL : ne consomme que des swings déjà CONFIRMÉS
    (`compute_swing_high_confirmed`/`compute_swing_low_confirmed`, cf.
    réserve P0-bis, `COUVERTURE_ENSEIGNEMENTS.md`) — aucune barre future
    n'entre jamais dans le calcul à l'instant t."""
    high_v = df["high"].values
    low_v = df["low"].values
    n = len(df)

    is_high_confirmed = compute_swing_high_confirmed(high_v, order=order)
    is_low_confirmed = compute_swing_low_confirmed(low_v, order=order)

    higher_highs = np.zeros(n, dtype=bool)
    lower_lows = np.zeros(n, dtype=bool)
    last_highs = []
    last_lows = []
    for i in range(n):
        if is_high_confirmed[i]:
            last_highs.append(high_v[i - order])
            if len(last_highs) > 2:
                last_highs.pop(0)
        if is_low_confirmed[i]:
            last_lows.append(low_v[i - order])
            if len(last_lows) > 2:
                last_lows.pop(0)
        if len(last_highs) == 2:
            higher_highs[i] = last_highs[1] > last_highs[0]
        if len(last_lows) == 2:
            lower_lows[i] = last_lows[1] < last_lows[0]

    broadening = higher_highs & lower_lows
    return broadening, higher_highs, lower_lows

def add_wall_street_column(df: pd.DataFrame, order: int = SWING_ORDER) -> pd.DataFrame:
    """Ajoute `wall_street_active` (bool, CAUSAL) à `df` — vrai ssi la
    structure en élargissement (règle "Wall Street", cf. docstring de tête)
    est détectée à cet instant. Usage prescrit par le corpus : ABSTENTION
    TOTALE (aucune entrée, fraîche ou renfort) tant que ce booléen est vrai
    — pas une réduction de taille, un arrêt complet (cf. citation exacte
    des sources #3/#4 en tête de fichier)."""
    df = df.copy()
    broadening, higher_highs, lower_lows = compute_broadening_structure(df, order=order)
    df["wall_street_active"] = broadening
    df["wall_street_higher_highs"] = higher_highs
    df["wall_street_lower_lows"] = lower_lows
    return df

if __name__ == "__main__":
    import sys
    
    from emile.backtests.backtest_phase2 import load_h1, resample

    df = resample(load_h1("BTCUSDT"), "1D")
    scored = add_wall_street_column(df)
    print(scored[["date", "close", "wall_street_higher_highs", "wall_street_lower_lows", "wall_street_active"]].tail(40).to_string(index=False))
    print("\n% du temps en structure Wall Street (BTC D1) :", round(scored["wall_street_active"].mean() * 100, 2), "%")
