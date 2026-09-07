"""
Fourchette d'Andrews ("Inside Pitchfork") — backlog `PLAN.md` item 7,
`COUVERTURE_ENSEIGNEMENTS.md` ligne "Fourchette d'Andrews" (sources #3,
#4).

Définition exacte extraite, PAS supposée :
  - #3 (`TRADING_LESSONS_ALTERNATIVE_MANUELLE.md`, §3-4) : "Fourchette
    d'Andrews ('Inside Pitchfork') : prend le relais quand la tendance est
    brisée. Couvre ~90% des cas correctifs (recommandé plutôt que la
    version standard, trop large)." Listée aussi dans le tableau §3 comme
    l'outil de correction pour une tendance invalidée (succède au Canal de
    Tendance).
  - #4 (`TRADING_LESSONS_ANALYSE_SANS_INDICATEURS.md`, "Confirmations") :
    cite "Fourchette d'Andrews 'Inside Pitchfork' (90% des cas)" --
    confirme le chiffre et le nom, sans détail géométrique supplémentaire.

Ni #3 ni #4 ne donnent la construction géométrique complète de la
fourchette (contrairement au canal manuel, §4 de la source #3, qui lui est
détaillé pas à pas) -- seuls le NOM ("Inside Pitchfork"), le RÔLE (relais
du canal de tendance une fois la tendance brisée) et un CHIFFRE (~90% des
cas correctifs, "recommandé plutôt que la version standard, trop large")
sont donnés. La tâche demande "3 points pivots, ligne médiane + 2
parallèles" -- c'est la définition CANONIQUE, publique, de l'outil Andrews
Pitchfork (Alan Andrews), cohérente avec ce que #3/#4 nomment sans
redéfinir : le corpus présuppose la définition standard de l'outil
(comme il présuppose la définition standard du TSI(14,7,9) sans la
réexpliquer, source #3 §5) et n'en documente que la VARIANTE choisie
("Inside", pas "standard") et le CONTEXTE d'usage.

HYPOTHÈSES D'IMPLÉMENTATION explicites (le corpus ne redéfinit pas la
géométrie standard ni ne précise la différence exacte "Inside" vs
"standard" au-delà de "trop large" -- documentées plutôt que masquées) :
  H1 (géométrie, définition publique standard de l'outil, pas une
      invention) : 3 points pivots chronologiques P0 (idx0, prix0), P1
      (idx1, prix1), P2 (idx2, prix2) avec idx0 < idx1 < idx2, alternant
      creux/sommet (ex. creux-sommet-creux ou sommet-creux-sommet).
      - Ligne Médiane : part de P0, passe par M = milieu(P1, P2) (moyenne
        des index ET des prix), extrapolée dans les 2 sens.
      - 2 parallèles : même pente que la Médiane, l'une passant
        EXACTEMENT par P1, l'autre EXACTEMENT par P2 -- "ligne médiane + 2
        parallèles" au sens strict de l'énoncé.
  H2 ("Inside Pitchfork", sélection causale des 3 pivots) : le corpus ne
      précise pas comment choisir P0/P1/P2 en continu sur une série de
      prix -- traduit ici par les 3 DERNIERS points de swing CONFIRMÉS
      dont le TYPE ALTERNE (creux/sommet/creux ou l'inverse), réutilisant
      EXACTEMENT `proxy_v2.compute_swing_low_confirmed`/
      `compute_swing_high_confirmed` (même SWING_ORDER que le reste du
      projet) -- pas une nouvelle détection de pivot ad hoc. L'alternance
      stricte (un swing de type différent du précédent pour être accepté
      dans le triplet, sinon ignoré) reflète le principe de la variante
      "Inside" : construire la fourchette sur les pivots les plus RÉCENTS
      et les plus RESSERRÉS (donc "moins large" que la version standard,
      qui utiliserait typiquement 3 points plus espacés/plus anciens) --
      lecture cohérente avec "recommandé... trop large" pour la version
      standard, mais une hypothèse de traduction, pas une formule donnée
      par le corpus.
  H3 : comme pour le canal manuel (`manual_trend_channel.py`), le triplet
      de pivots, une fois complet, reste actif et les 3 droites
      s'extrapolent linéairement jusqu'à ce qu'un nouveau pivot alterné
      confirmé remplace le plus ancien des 3 (fenêtre glissante de pivots,
      pas une fourchette figée une fois pour toutes) -- nécessaire pour
      produire une valeur exploitable à chaque bougie, pas seulement aux 3
      instants de construction.

CAUSALITÉ : les 3 pivots sont, par construction, toujours des swings déjà
CONFIRMÉS (donc strictement dans le passé) au moment où le triplet devient
utilisable -- aucune barre future n'entre jamais dans le calcul."""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from proxy_v2 import compute_swing_low_confirmed, compute_swing_high_confirmed

# Cohérent avec proxy_v2.SWING_ORDER (même détection de swing réutilisée).
SWING_ORDER = 3


def pitchfork_lines(p0: tuple, p1: tuple, p2: tuple, t) -> tuple:
    """Géométrie Andrews Pitchfork standard (H1) à partir de 3 pivots
    `(idx, prix)` chronologiques P0 < P1 < P2 : retourne (median,
    parallel_p1, parallel_p2), les 3 droites évaluées aux instants `t`
    (scalaire ou array) :
      - `median`      : part de P0, passe par le milieu de P1 et P2.
      - `parallel_p1`  : parallèle à la médiane, passant par P1.
      - `parallel_p2`  : parallèle à la médiane, passant par P2.
    Fonction purement géométrique (ne fait aucune hypothèse sur quel
    pivot est un creux ou un sommet) -- réutilisable indépendamment de la
    détection causale ci-dessous, ce qui permet de la tester isolément
    avec des pivots choisis à la main."""
    idx0, price0 = p0
    idx1, price1 = p1
    idx2, price2 = p2
    mid_idx = (idx1 + idx2) / 2.0
    mid_price = (price1 + price2) / 2.0
    slope = 0.0 if mid_idx == idx0 else (mid_price - price0) / (mid_idx - idx0)
    t = np.asarray(t, dtype=float)
    median = price0 + slope * (t - idx0)
    parallel_p1 = price1 + slope * (t - idx1)
    parallel_p2 = price2 + slope * (t - idx2)
    return median, parallel_p1, parallel_p2


def compute_andrews_pitchfork_causal(df: pd.DataFrame, order: int = SWING_ORDER) -> tuple:
    """Version CAUSALE, auto-sélection des pivots (H2/H3) : retourne
    (median, parallel_p1, parallel_p2), 3 arrays de prix absolus (NaN tant
    qu'un triplet alterné de 3 pivots confirmés n'a pas encore été formé).
    Cf. docstring de tête pour la sélection des pivots et l'extrapolation."""
    high_v = df["high"].values
    low_v = df["low"].values
    n = len(df)

    is_high_confirmed = compute_swing_high_confirmed(high_v, order=order)
    is_low_confirmed = compute_swing_low_confirmed(low_v, order=order)

    median = np.full(n, np.nan)
    parallel_p1 = np.full(n, np.nan)
    parallel_p2 = np.full(n, np.nan)

    pivots = []  # [(idx_réel, prix, kind)], kind in {"low", "high"}, alternance imposée (H2)

    for i in range(n):
        new_points = []
        if is_low_confirmed[i]:
            new_points.append((i - order, low_v[i - order], "low"))
        if is_high_confirmed[i]:
            new_points.append((i - order, high_v[i - order], "high"))
        new_points.sort(key=lambda pt: pt[0])  # ordre chronologique de la barre swing réelle

        for (idx, price, kind) in new_points:
            if pivots and pivots[-1][2] == kind:
                continue  # H2 : alternance stricte, ignore un swing du même type que le précédent
            pivots.append((idx, price, kind))
            if len(pivots) > 3:
                pivots.pop(0)  # H3 : fenêtre glissante des 3 derniers pivots alternés

        if len(pivots) == 3:
            (i0, pr0, _), (i1, pr1, _), (i2, pr2, _) = pivots
            med, par1, par2 = pitchfork_lines((i0, pr0), (i1, pr1), (i2, pr2), i)
            median[i], parallel_p1[i], parallel_p2[i] = med, par1, par2

    return median, parallel_p1, parallel_p2


def add_andrews_pitchfork_columns(df: pd.DataFrame, order: int = SWING_ORDER) -> pd.DataFrame:
    """Ajoute `pitchfork_median`/`pitchfork_p1`/`pitchfork_p2` à `df`."""
    df = df.copy()
    median, p1, p2 = compute_andrews_pitchfork_causal(df, order=order)
    df["pitchfork_median"] = median
    df["pitchfork_p1"] = p1
    df["pitchfork_p2"] = p2
    return df


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from backtest_phase2 import load_h1, resample

    df = resample(load_h1("BTCUSDT"), "1D")
    scored = add_andrews_pitchfork_columns(df)
    print(scored[["date", "close", "pitchfork_median", "pitchfork_p1", "pitchfork_p2"]].tail(40).to_string(index=False))
    print("\n% de bougies avec une fourchette construite (BTC D1) :", round(scored["pitchfork_median"].notna().mean() * 100, 2), "%")
