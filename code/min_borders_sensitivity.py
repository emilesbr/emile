"""
Sensibilité du seuil de maturité de range `MIN_BORDERS` — tension "3 vs 4
bornes" (`PLAN.md` backlog item 11, catégorie B point (iii) ;
`COUVERTURE_ENSEIGNEMENTS.md` "Audit exhaustif du corpus complet",
catégorie B, 3e puce).

POURQUOI CE SCRIPT
-----------------------------------------------------------------------------
La tension est notée en commentaire depuis la v4 (`backtest_phase2_v4.py:32`
: `MIN_BORDERS = 3  # maturité minimale (règle des "3-4 bornes", sources
#9-#14)`) mais n'a JAMAIS été ni formellement tranchée ni testée en
sensibilité : `MIN_BORDERS=4` n'a jamais été essayé nulle part.

Relecture directe des sources (faite pour ce script, pas reprise d'un
résumé) — le corpus est réellement partagé, ce n'est pas une erreur de
lecture d'une seule source :

  Camp "4 bornes" :
   - `TRADING_LESSONS_ZONE_ACCUMULATION.md:24` (table "Critères de maturité
     d'une zone d'accumulation") : *"Maturité (bornes) | Minimum 4 bornes
     (points de contact) nettement visibles sur l'UT locale"*.
   - `TRADING_LESSONS_PULLBACK_MATURITE.md:33` : *"Maturité du range :
     minimum 4 bornes (oscillations) sur l'UT de tendance — sans ça,
     structure jugée immature, risque de 'fausse sortie' trop élevé."*
   - `TRADING_LESSONS_PULLBACK_MATURITE.md:50` (table go/no-go) :
     *"Maturité du range | 4 bornes identifiées | Moins de 4 bornes"*.

  Camp "3 bornes" :
   - `TRADING_LESSONS_BREAKOUT_RATIO11.md:27` : *"Maturité structurelle :
     minimum 3 bornes testées sur l'UT locale pour être exploitable"*
     — MÊME formulation ("UT locale") que la source #10 qui, elle, dit 4 :
     contradiction frontale, pas une différence de timeframe.
   - `TRADING_LESSONS_STRUCTURES_ALTERATIONS.md:13` : *"Conditions de
     validité avant d'engager du capital : maturité du range (min. 3 bornes
     testées) ..."*.
   - `RULES_EXTRACTION.md:19` (manuel PDF) : *"Range : max 3 bornes rejetées
     avant 'range mature' → arrêt"* — noter que le manuel formule un
     MAXIMUM (au-delà de 3 rejets, on arrête de trader le range), pas un
     minimum : ce n'est pas exactement le même objet que les "min. N bornes"
     des sources Trading Lessons, et `TRADING_LESSONS_PSYCHOLOGY.md:20` le
     relève déjà explicitement.

  Lecture qui réconcilie les deux camps (`TRADING_LESSONS_MTF_SUIVI_TENDANCE.md`
  :27-29, "Anatomie du basculement 3ème → 4ème borne") : la 3ème borne est
  *"le pivot qui stabilise le cadre et définit le risque initial"* et la 4ème
  borne *"l'outil de mesure de l'intention"*. Autrement dit 3 et 4 ne sont
  pas deux valeurs concurrentes du même seuil mais deux ÉTAPES successives —
  ce qui explique que les sources citent l'une ou l'autre selon ce qu'elles
  décrivent. Cette lecture n'est PAS tranchée ici (elle relève de la
  catégorie C, "décision de conception") ; ce script se limite à mesurer.

CE QUE CE SCRIPT EST / N'EST PAS
-----------------------------------------------------------------------------
C'EST un test de SENSIBILITÉ, calqué sur le précédent déjà établi dans ce
projet (`cluster_technique_threshold_robustness.py` : grille symétrique de
seuils autour de la valeur de production, fixée A PRIORI, rejouée sur
BTC/ETH/BNB/SOL). Ce N'EST PAS une recherche du "meilleur" seuil : aucune
valeur de la grille n'est présentée comme supérieure à 3, et un écart mesuré
ne serait pas en soi une raison de changer la production — cf. la règle
inviolable du projet (`PLAN.md` en tête) : "nous ne nous fions pas aux
résultats du Proxy pour décider d'utiliser ou non la propriété
intellectuelle de Philippe, nous l'utilisons dans tous les cas".

Grille fixée avant de lancer quoi que ce soit : 2 / 3 (référence, valeur de
production, INCHANGÉE) / 4 / 5. Elle déborde volontairement de part et
d'autre du couple 3-4 en litige, pour distinguer "3 et 4 donnent la même
chose" de "le seuil n'a aucun effet quel qu'il soit".

DISCIPLINE DE FICHIERS — ne modifie AUCUN fichier de production
-----------------------------------------------------------------------------
Même exigence que `cluster_technique_threshold_robustness.py` /
`ablation_test_cycle.py` / `andrews_gate_alternative.py` : script de mesure
séparé, `MIN_BORDERS=3` reste la valeur par défaut partout, aucun fichier de
production n'est édité.

Différence de TECHNIQUE avec le précédent Cluster Technique, et pourquoi :
là-bas, `proximity_pctl` était déjà un PARAMÈTRE de `add_cluster_signal` que
`diversification.py` ne propageait pas — il fallait donc dupliquer
`run_diversified` pour le faire passer, au prix d'un risque de dérive
couvert par un test de non-régression. Ici `MIN_BORDERS` est une CONSTANTE
DE MODULE, lue à chaque appel dans les globales du module qui l'utilise
(`backtest_phase2_v7.run_v7` la passe à `make_open_tranche_fn` ;
`trend_table.run_trend_table` la lit ligne 522). Un override de portée
limitée (`override_min_borders`, restauré en `finally`) fait donc tourner le
VRAI moteur de production, sans copie et donc sans aucun risque de dérive —
strictement mieux qu'une duplication de ~130 lignes. Rien n'est écrit sur
disque dans les fichiers de production, et la restauration est vérifiée par
test (`test_min_borders_sensitivity.py`), y compris en cas d'exception.

Note : `trend_table.py` fait `from backtest_phase2_v7 import ... MIN_BORDERS`
au moment de l'import, il possède donc sa PROPRE liaison — les deux modules
doivent être overridés séparément, ce qui est fait explicitement ci-dessous
(et vérifié par test). Les autres modules qui importent `MIN_BORDERS`
(`diversification.py`, `unified_protocol.py`, `risk_aggregation_triple_system.py`,
`andrews_gate_alternative.py`) ne sont PAS touchés : hors périmètre de cette
mesure, qui porte sur les deux moteurs les plus représentatifs (v7 = moteur
de range/spéculatif, `trend_table` = moteur de tendance).
"""
import contextlib
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
import backtest_phase2_v7
import trend_table
from backtest_phase2 import load_h1, resample, EMA_SLOW
from backtest_phase2_v7 import run_v7, prepare, attach_higher_context, PROFILES_V4
from trend_table import run_trend_table, load_volume, resample_volume, PROFILES_TREND

# Grille fixée A PRIORI (cf. docstring de tête), 3 = valeur de production.
MIN_BORDERS_GRID = (2, 3, 4, 5)
BASELINE_MIN_BORDERS = 3

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")


@contextlib.contextmanager
def override_min_borders(module, value: int):
    """Remplace TEMPORAIREMENT la constante `MIN_BORDERS` de `module`, puis la
    restaure systématiquement (`finally`, donc même si le moteur lève).

    Volontairement limité aux constantes de module : aucun fichier n'est
    modifié sur disque, et le moteur exécuté est bien le moteur de production
    lui-même (pas une copie), cf. docstring de tête."""
    if not hasattr(module, "MIN_BORDERS"):
        raise AttributeError(f"{module.__name__} n'expose pas MIN_BORDERS")
    previous = module.MIN_BORDERS
    module.MIN_BORDERS = value
    try:
        yield
    finally:
        module.MIN_BORDERS = previous


def run_v7_min_borders(h4: pd.DataFrame, d1: pd.DataFrame, profile_name: str, min_borders: int,
                       **kwargs) -> dict:
    """`backtest_phase2_v7.run_v7` (le VRAI moteur, non dupliqué) rejoué avec
    `MIN_BORDERS = min_borders`. `kwargs` transmis tels quels à `run_v7`."""
    with override_min_borders(backtest_phase2_v7, min_borders):
        return run_v7(h4, d1, profile_name, **kwargs)


def run_trend_table_min_borders(df: pd.DataFrame, vol: pd.DataFrame, profile_name: str,
                                min_borders: int) -> dict:
    """`trend_table.run_trend_table` (le VRAI moteur) rejoué avec
    `MIN_BORDERS = min_borders`. `trend_table` a sa propre liaison de la
    constante (import direct), c'est donc bien ce module qu'on override."""
    with override_min_borders(trend_table, min_borders):
        return run_trend_table(df, vol, profile_name)


def borders_binding_stats(h4: pd.DataFrame, d1: pd.DataFrame) -> dict:
    """DIAGNOSTIC — à quelle fréquence le gate de maturité MORD-il réellement ?

    Sans cette mesure, un résultat "aucun écart entre 3 et 4" serait
    ininterprétable : impossible de distinguer "le seuil est robuste" de "le
    seuil ne sert à rien parce qu'il n'est presque jamais atteint par le
    bas". On mesure donc, pour chaque valeur de la grille :
      - `pct_bars_mature_k`  : % de bougies H4 (hors NaN) où `n_borders >= k` ;
      - `pct_candidates_mature_k` : idem, restreint aux bougies qui satisfont
        DÉJÀ toutes les AUTRES conditions d'entrée fraîche de v7 (score >= 2,
        gate D1 score >= 2 et régime D1 != EXCES, inputs valides, hors
        warmup) — c'est la population réellement concernée par le gate ;
      - `first_binding_threshold` : la plus petite valeur entière de
        `MIN_BORDERS` qui rejetterait ne serait-ce QU'UNE bougie candidate
        (= `min(n_borders sur les candidates) + 1`). Si elle est très
        au-dessus de la grille testée, alors tout écart nul mesuré ci-dessous
        est une NON-MESURE (gate inerte), pas une preuve de robustesse.
    """
    h4p = prepare(h4.copy())
    d1p = prepare(d1.copy())
    ctx_score, ctx_regime, _ = attach_higher_context(h4p, d1p, pd.Timedelta(days=1))

    n_borders = h4p["n_borders"].values
    score = h4p["score"].values
    atr_v = h4p["atr"].values
    ctx_support_v = h4p["ctx_support"].values
    local_range_v = h4p["local_range"].values
    context_range_v = h4p["context_range"].values
    n = len(h4p)
    warmup = EMA_SLOW + 20

    # Mêmes conditions que make_open_tranche_fn/run_v7 (évaluées en j = i - 1
    # dans le moteur ; ici on raisonne sur la population de bougies, le
    # décalage d'un cran ne change pas les proportions).
    after_warmup = np.arange(n) >= warmup
    valid_inputs = (
        ~np.isnan(atr_v) & ~np.isnan(ctx_support_v)
        & ~np.isnan(local_range_v) & (np.nan_to_num(local_range_v) > 0)
        & ~np.isnan(context_range_v) & (np.nan_to_num(context_range_v) > 0)
    )
    ctx_ok = (np.nan_to_num(ctx_score.astype(float), nan=-1.0) >= 2) & (ctx_regime != "EXCES")
    candidates = after_warmup & valid_inputs & (score >= 2) & ctx_ok

    known = ~np.isnan(n_borders)
    out = {
        "n_bars": int(known.sum()),
        "n_candidates": int((candidates & known).sum()),
        "n_borders_min": float(np.nanmin(n_borders)),
        "n_borders_p05": float(np.nanpercentile(n_borders, 5)),
        "n_borders_median": float(np.nanmedian(n_borders)),
    }
    pool = candidates & known
    out["n_borders_min_on_candidates"] = float(np.min(n_borders[pool])) if pool.any() else None
    out["first_binding_threshold"] = int(np.min(n_borders[pool])) + 1 if pool.any() else None
    for k in MIN_BORDERS_GRID:
        mature = known & (np.nan_to_num(n_borders, nan=-1.0) >= k)
        out[f"pct_bars_mature_{k}"] = round(float(mature[known].mean() * 100), 2)
        out[f"pct_candidates_mature_{k}"] = (
            round(float(mature[pool].mean() * 100), 2) if pool.any() else None
        )
    return out


def main():
    rows_v7, rows_trend, rows_diag = [], [], []

    for symbol in SYMBOLS:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        d1 = resample(h1, "1D")
        vol_h4 = resample_volume(load_volume(symbol), "4h")

        rows_diag.append({"symbol": symbol, **borders_binding_stats(h4, d1)})

        for profile in PROFILES_V4:
            for mb in MIN_BORDERS_GRID:
                # Configuration de référence de v7 (celle de son propre main() :
                # gate MTF actif, stop H4 -- ligne "H4_valide_par_D1 / H4_meme_UT").
                res = run_v7_min_borders(h4.copy(), d1.copy(), profile, mb,
                                         use_mtf_gate=True, use_mtf_stop=False)
                rows_v7.append({"symbol": symbol, "profile": profile, "min_borders": mb, **res})

        for profile in PROFILES_TREND:
            for mb in MIN_BORDERS_GRID:
                res = run_trend_table_min_borders(h4.copy(), vol_h4.copy(), profile, mb)
                res.pop("stage_time_%", None)
                res.pop("final_equity", None)
                rows_trend.append({"symbol": symbol, "profile": profile, "min_borders": mb, **res})

    df_v7 = pd.DataFrame(rows_v7)
    df_trend = pd.DataFrame(rows_trend)
    df_diag = pd.DataFrame(rows_diag)

    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", 40)

    print("=" * 110)
    print("DIAGNOSTIC — le gate de maturité mord-il ? (n_borders = swings bas confirmés, fenêtre 15D glissante)")
    print("=" * 110)
    print(df_diag.to_string(index=False))

    print("\n" + "=" * 110)
    print(f"MOTEUR v7 (range/spéculatif, gate MTF D1 actif) — grille MIN_BORDERS {MIN_BORDERS_GRID}")
    print("=" * 110)
    print(df_v7.to_string(index=False))

    print("\n" + "=" * 110)
    print(f"MOTEUR trend_table (table de tendance 5 étapes) — grille MIN_BORDERS {MIN_BORDERS_GRID}")
    print("=" * 110)
    print(df_trend.to_string(index=False))

    df_v7.to_csv("min_borders_sensitivity_v7_results.csv", index=False)
    df_trend.to_csv("min_borders_sensitivity_trend_results.csv", index=False)
    df_diag.to_csv("min_borders_sensitivity_diagnostic.csv", index=False)

    _report(df_v7, "v7")
    _report(df_trend, "trend_table")

    print("\n" + "=" * 110)
    print("CONSTAT HONNÊTE (non maquillé) — écarts entre la valeur de production (3) et la valeur contestée (4)")
    print("=" * 110)
    n_diff = 0
    for df, name in ((df_v7, "v7"), (df_trend, "trend_table")):
        for (sym, prof), sub in df.groupby(["symbol", "profile"]):
            base = sub[sub.min_borders == BASELINE_MIN_BORDERS].iloc[0]
            alt = sub[sub.min_borders == 4].iloc[0]
            if (int(base["n_trades"]) != int(alt["n_trades"])
                    or abs(float(base["total_return_%"]) - float(alt["total_return_%"])) > 1e-9
                    or abs(float(base["max_dd_%"]) - float(alt["max_dd_%"])) > 1e-9):
                n_diff += 1
                print(f"  ECART — {name:<12} {sym:<9} {prof:<14} "
                      f"trades {base['n_trades']}->{alt['n_trades']}  "
                      f"retour {base['total_return_%']}% -> {alt['total_return_%']}%  "
                      f"DD {base['max_dd_%']}% -> {alt['max_dd_%']}%")
    total_pairs = len(SYMBOLS) * (len(PROFILES_V4) + len(PROFILES_TREND))
    print(f"\n  {n_diff}/{total_pairs} couples (moteur x actif x profil) montrent un écart QUELCONQUE "
          f"entre MIN_BORDERS=3 et MIN_BORDERS=4.")
    print("  Rappel : un écart nul ne valide PAS le choix de 3 sur le fond -- il signifie que le gate "
          "n'est pas discriminant tel qu'il est actuellement calculé (cf. diagnostic ci-dessus).")


def _report(df: pd.DataFrame, name: str):
    print("\n" + "-" * 110)
    print(f"LECTURE DE ROBUSTESSE — {name} (amplitude sur la grille {MIN_BORDERS_GRID}, "
          f"référence = {BASELINE_MIN_BORDERS})")
    print("-" * 110)
    for (sym, prof), sub in df.groupby(["symbol", "profile"]):
        ret = sub["total_return_%"].astype(float)
        tr = sub["n_trades"].astype(int)
        print(f"  {sym:<9} {prof:<14} n_trades {tr.min()}..{tr.max()} "
              f"| retour {ret.min():+.1f}%..{ret.max():+.1f}% (amplitude {ret.max() - ret.min():.1f} pt)")


if __name__ == "__main__":
    main()
