"""
Canal de tendance manuel (Supports -> Apex -> Tangente) — backlog `PLAN.md`
item 7, `COUVERTURE_ENSEIGNEMENTS.md` ligne "Canal de tendance manuel"
(source #3, confirmée par #4).

Définition exacte extraite, PAS supposée (`TRADING_LESSONS_ALTERNATIVE_
MANUELLE.md`, §4, "Construction manuelle du canal de tendance (méthode
précise, codable)") :
  > "Pour un mouvement haussier, dans cet ordre strict :
  >  1. Supports : relier les deux creux les plus significatifs de la
  >     tendance actuelle
  >  2. Apex : identifier le sommet le plus élevé situé *entre* ces deux
  >     points de support
  >  3. Tangente : tracer une parallèle au support passant précisément par
  >     l'apex -> cadre complet : Support / Ligne Médiane (50%) /
  >     Résistance"

Confirmée par #4 (`TRADING_LESSONS_ANALYSE_SANS_INDICATEURS.md`,
"Confirmations") sans détail supplémentaire ("Canal de tendance manuel
(Supports->Apex->Tangente)" cité tel quel parmi les éléments déjà connus).
Aucune des 2 sources ne précise de formule numérique pour la "Ligne
Médiane (50%)" au-delà du mot "médiane" -> implémentée ici comme le
milieu EXACT (50%) entre support et résistance à chaque instant, lecture
la plus littérale de "50%" (pas une pondération différente).

Traduction géométrique exacte des 3 étapes (pas d'invention au-delà de ce
qui est écrit) :
  1. Support = droite passant par les 2 creux (idx1, prix1) et (idx2,
     prix2), idx1 < idx2, prix2 > prix1 (mouvement HAUSSIER, cf. l'énoncé
     "pour un mouvement haussier").
  2. Apex = (idx_a, prix_a) où prix_a = max(high) STRICTEMENT ENTRE idx1
     et idx2 (bornes exclues, lecture littérale de "situé *entre* ces
     deux points").
  3. Résistance = droite PARALLÈLE au support (même pente), décalée
     verticalement pour passer EXACTEMENT par l'apex. Médiane = milieu
     support/résistance (50%) à chaque instant.

HYPOTHÈSES D'IMPLÉMENTATION explicites (le corpus ne précise ni la
sélection algorithmique des "deux creux les plus significatifs" ni la
durée de vie du canal une fois tracé — documentées ici plutôt que
laissées implicites, même discipline que `fibonacci.py`/`trend_table.py`) :
  H1 : "les deux creux les plus significatifs de la tendance actuelle" =
       les 2 DERNIERS swing lows CONFIRMÉS (réutilisation EXACTE de
       `proxy_v2.compute_swing_low_confirmed`, même `SWING_ORDER` que le
       reste du projet), à condition qu'ils soient ASCENDANTS (2e > 1er --
       même condition et même primitive que `compute_ascending_lows`,
       cohérent avec "mouvement haussier"). Choix motivé par la cohérence
       du projet (une seule détection de swing partout) plutôt qu'une
       nouvelle notion de "significativité" ad hoc.
  H2 : le canal une fois construit (support/apex/résistance) reste actif
       et s'EXTRAPOLE linéairement (même pente) jusqu'à ce qu'une paire
       plus récente de swing lows ascendants confirmés le remplace --
       nécessaire pour produire une valeur de support/résistance à CHAQUE
       bougie (utilisable comme alternative au stop EMA+/-ATR,
       `ctx_support` de `backtest_phase2_v7.py`), pas seulement aux 2
       instants de construction.
  H3 : si aucun sommet n'existe strictement entre les 2 creux (idx2 =
       idx1+1, pas de bougie intermédiaire), aucun canal n'est construit
       pour cette paire (l'étape "Apex" est structurellement impossible) --
       le canal précédent (s'il existe) reste actif inchangé.

CAUSALITÉ : idx1, idx2 et l'apex (borné par idx1 et idx2) sont TOUS
strictement dans le passé au moment où le canal devient utilisable (à
partir de idx2, lui-même confirmé à idx2+SWING_ORDER) -- aucune barre
future n'entre jamais dans la construction, vérifié par construction (pas
besoin d'un test de troncature séparé comme pour le cycle/la structure :
il n'y a ici aucun appel batch sur toute la série, seulement des maxima
sur des tranches déjà closes)."""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from proxy_v2 import compute_swing_low_confirmed

# Cohérent avec proxy_v2.SWING_ORDER (même détection de swing réutilisée).
SWING_ORDER = 3


def compute_manual_trend_channel(df: pd.DataFrame, order: int = SWING_ORDER) -> tuple:
    """Retourne (support, median, resistance), 3 arrays de prix absolus
    (NaN tant qu'aucun canal n'a encore pu être construit), cf. docstring
    de tête pour la construction géométrique exacte et les hypothèses."""
    low_v = df["low"].values
    high_v = df["high"].values
    n = len(df)

    is_low_confirmed = compute_swing_low_confirmed(low_v, order=order)

    support = np.full(n, np.nan)
    median = np.full(n, np.nan)
    resistance = np.full(n, np.nan)

    last_lows = []  # [(idx, prix)] des 2 derniers swing lows confirmés
    channel = None  # dict {idx1, p1, slope, offset} une fois construit (étapes 1-3)

    for i in range(n):
        if is_low_confirmed[i]:
            idx = i - order
            last_lows.append((idx, low_v[idx]))
            if len(last_lows) > 2:
                last_lows.pop(0)
            if len(last_lows) == 2:
                (idx1, p1), (idx2, p2) = last_lows
                # Étape 1 (Supports) : n'accepte la paire que si elle décrit
                # bien un mouvement haussier (H1, cohérent avec l'énoncé
                # "pour un mouvement haussier")
                if idx2 > idx1 and p2 > p1:
                    interior_high = high_v[idx1 + 1: idx2]
                    if len(interior_high) > 0:
                        # Étape 2 (Apex) : sommet le plus élevé STRICTEMENT
                        # entre les 2 points de support (H3 : sinon, pas de
                        # canal pour cette paire, cf. docstring de tête)
                        apex_rel = int(np.argmax(interior_high))
                        apex_idx = idx1 + 1 + apex_rel
                        apex_price = interior_high[apex_rel]
                        slope = (p2 - p1) / (idx2 - idx1)
                        support_at_apex = p1 + slope * (apex_idx - idx1)
                        # Étape 3 (Tangente) : parallèle au support passant
                        # exactement par l'apex -> décalage vertical constant
                        offset = apex_price - support_at_apex
                        channel = {"idx1": idx1, "p1": p1, "slope": slope, "offset": offset}

        if channel is not None:
            supp_i = channel["p1"] + channel["slope"] * (i - channel["idx1"])
            res_i = supp_i + channel["offset"]
            support[i] = supp_i
            resistance[i] = res_i
            median[i] = (supp_i + res_i) / 2.0  # Ligne Médiane (50%), lecture littérale

    return support, median, resistance


def add_manual_trend_channel_columns(df: pd.DataFrame, order: int = SWING_ORDER) -> pd.DataFrame:
    """Ajoute `channel_support`/`channel_median`/`channel_resistance` à
    `df` -- alternative à la bande EMA+/-ATR (`ctx_support` de
    `backtest_phase2_v7.py::prepare`), construction géométrique réelle
    Supports->Apex->Tangente (cf. docstring de tête)."""
    df = df.copy()
    support, median, resistance = compute_manual_trend_channel(df, order=order)
    df["channel_support"] = support
    df["channel_median"] = median
    df["channel_resistance"] = resistance
    return df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from backtest_phase2 import load_h1, resample

    df = resample(load_h1("BTCUSDT"), "1D")
    scored = add_manual_trend_channel_columns(df)
    print(scored[["date", "close", "channel_support", "channel_median", "channel_resistance"]].tail(40).to_string(index=False))
    print("\n% de bougies avec un canal construit (BTC D1) :", round(scored["channel_support"].notna().mean() * 100, 2), "%")
