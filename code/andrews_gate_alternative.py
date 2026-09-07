"""
Fourchette d'Andrews — LECTURE ALTERNATIVE du gating d'entrée (vague 5,
`PLAN.md` "Plan d'autonomie 8h" : "autre hypothèse de gating Andrews
Pitchfork -- celle testée dégrade nettement, pas forcément la seule lecture
possible"). Nouveau fichier, ne modifie ni `andrews_pitchfork.py` (géométrie
et détection causale des pivots, inchangées) ni `backtest_phase2_patterns.py`
(l'hypothèse ORIGINALE y reste telle quelle, pour comparaison directe).

MISE EN GARDE explicite reçue et respectée : ce chantier est le plus à
risque de sur-ajustement de la session. Ce fichier retient UNE SEULE
lecture alternative, choisie a priori pour son adéquation au TEXTE du
corpus -- PAS par balayage de paramètres à la recherche du meilleur
résultat. Aucune variante de la lecture retenue n'a été essayée puis
écartée pour arriver à celle-ci ; si le chiffre mesuré est décevant, il est
rapporté tel quel (cf. principe de tête de `COUVERTURE_ENSEIGNEMENTS.md` :
la performance ne sert jamais à décider si un élément du corpus doit être
implémenté, seulement à documenter honnêtement l'effet mesuré d'UNE lecture
retenue).

RAPPEL DE L'HYPOTHÈSE ORIGINALE (`backtest_phase2_patterns.py`, mode
"andrews_gate", `COUVERTURE_ENSEIGNEMENTS.md` note "Andrews Pitchfork") :
gate d'ENTRÉE PERMANENT -- n'autoriser une entrée fraîche (ou un renfort)
que si `close > pitchfork_p1`, appliqué à CHAQUE bougie candidate, quel que
soit le régime de marché. Résultat mesuré : dégrade nettement le retour
total (médian 18% vs 212% référence, moyenne négative sur ETH -9,5% à
-21,9% selon profil) -- l'agent qui a posé cette hypothèse l'a lui-même
documentée comme "une hypothèse d'intégration, pas une règle du corpus".

LECTURE ALTERNATIVE RETENUE ICI (H-Andrews-Contextuel) -- justification
textuelle, pas empirique
-----------------------------------------------------------------------------
Citation exacte, reproduite dans `andrews_pitchfork.py` (sources #3/#4) :
la Fourchette d'Andrews "PREND LE RELAIS QUAND la tendance est BRISÉE.
Couvre ~90% des cas CORRECTIFS" -- listée au tableau §3 comme l'outil de
CORRECTION qui SUCCÈDE au Canal de Tendance une fois la tendance invalidée.

Deux mots que l'hypothèse originale ignore, littéralement :
  - "PREND LE RELAIS QUAND" -- un relais est par nature CONDITIONNEL à un
    état de marché précis, pas un filtre permanent appliqué à toute bougie
    candidate quel que soit le régime. L'hypothèse originale l'applique
    aussi en régime TENDANCE encore intact -- précisément le régime où le
    manuel dit que c'est le CANAL DE TENDANCE (déjà construit,
    `manual_trend_channel.py`), pas la fourchette, qui est l'outil de
    référence : la fourchette "n'a pas encore pris le relais" à ce moment.
  - "tendance BRISÉE" -- ce projet dispose déjà d'un classificateur de
    régime (`regime_classifier.py`, réutilisé TEL QUEL, jamais modifié) qui
    distingue explicitement TENDANCE (pente nette, prix majoritairement
    d'un côté) de RANGE_TENDANCIEL, décrit dans sa propre docstring de tête
    comme "range, mais le contexte de l'UT supérieure est
    directionnellement aligné" -- soit, en langage courant, une tendance
    qui a cessé de progresser (le prix ne fait plus régulièrement de
    nouveaux extrêmes) mais qui conserve un biais directionnel HÉRITÉ :
    exactement la situation qu'un outil "correctif" est censé traiter, ni
    une tendance encore intacte (TENDANCE), ni un renversement complet sans
    aucun biais hérité (RANGE_NEUTRE, jamais mentionné par le corpus comme
    terrain de cet outil), ni une zone à ne pas trader du tout (EXCES,
    déjà exclue ailleurs dans le projet).

Hypothèse retenue : le gate Andrews (`close > pitchfork_p1`) n'est appliqué
QUE lorsque le régime de la bougie précédente est RANGE_TENDANCIEL -- le
seul moment, par lecture littérale, où l'outil a "pris le relais". Dans
tout autre régime (TENDANCE, RANGE_NEUTRE, EXCES), le gate ne s'applique
PAS -- le signal proxy_v2 passe tel quel, exactement comme le mode "none"
de `backtest_phase2_patterns.py`.

Tout le reste (moteur v7 sans MTF, position_engine, profils, warmup,
maturité, sizing, formule du stop) est IDENTIQUE bit pour bit à
`backtest_phase2_patterns.py::run_patterns` -- seule la condition
`andrews_ok` change selon le mode. `mode="andrews_permanent"` REPRODUIT
l'hypothèse originale dans CE MÊME fichier (vérifié par test de
non-régression contre `backtest_phase2_patterns.py`, cf.
`test_andrews_gate_alternative.py`) pour garantir une comparaison
apples-to-apples à la lecture alternative, sans dépendre de deux moteurs
qui auraient pu dériver l'un de l'autre.
"""
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, ".")
from backtest_phase2 import FEE, load_h1, resample
from backtest_phase2_v7 import prepare, PROFILES_V4, MIN_BORDERS, RULE3_STREAK, RULE3_SIZE_MULT, MAX_TRANCHES, EMA_SLOW
from position_engine import run_position_engine
from andrews_pitchfork import add_andrews_pitchfork_columns

ANDREWS_MODES = ("none", "andrews_permanent", "andrews_contextual")
# Cf. section "Lecture alternative retenue" ci-dessus : RANGE_TENDANCIEL est
# la SEULE lecture retenue de "tendance brisée mais pas un renversement
# neutre" -- pas un ensemble élargi après avoir regardé ce qui marche mieux.
CONTEXTUAL_REGIMES = ("RANGE_TENDANCIEL",)


def run_andrews(h4: pd.DataFrame, profile_name: str, mode: str = "none") -> dict:
    if mode not in ANDREWS_MODES:
        raise ValueError(f"mode inconnu: {mode!r}, attendu parmi {ANDREWS_MODES}")

    p = PROFILES_V4[profile_name]
    h4 = prepare(h4)  # ajoute déjà 'regime' (add_regime, réutilisé tel quel, jamais modifié)
    h4 = add_andrews_pitchfork_columns(h4)

    score = h4["score"].values
    atr_v = h4["atr"].values
    ctx_support_v = h4["ctx_support"].values
    local_range_v = h4["local_range"].values
    context_range_v = h4["context_range"].values
    n_borders_v = h4["n_borders"].values
    regime_v = h4["regime"].values
    pitchfork_p1_v = h4["pitchfork_p1"].values
    high, low, o, c = h4["high"].values, h4["low"].values, h4["open"].values, h4["close"].values
    n = len(h4)
    warmup = EMA_SLOW + 20
    long_signal = score >= 2

    def andrews_ok_at(i: int) -> bool:
        """Condition Andrews évaluée à l'index `i` (l'appelant passe soit
        `i` soit `i-1` selon la convention déjà en place dans
        `backtest_phase2_patterns.py` -- signal de la bougie précédente pour
        les décisions d'entrée, signal courant pour `gated_long_signal`)."""
        if mode == "none":
            return True
        p1 = pitchfork_p1_v[i]
        has_pitchfork = not np.isnan(p1)
        if mode == "andrews_permanent":
            # Reproduction EXACTE de l'hypothèse originale
            # (backtest_phase2_patterns.py, mode="andrews_gate"), gardée ici
            # pour comparaison directe dans le MÊME fichier/moteur.
            return has_pitchfork and c[i] > p1
        # mode == "andrews_contextual" (H-Andrews-Contextuel)
        if regime_v[i] not in CONTEXTUAL_REGIMES:
            return True  # l'outil "n'a pas encore pris le relais" -- signal proxy_v2 inchangé
        return has_pitchfork and c[i] > p1

    state = {"last_pyramid_high": -np.inf}

    def open_tranche_fn(i, tranches, win_streak):
        long_signal_prev = score[i - 1] >= 2
        mature = (not np.isnan(n_borders_v[i - 1])) and n_borders_v[i - 1] >= MIN_BORDERS
        andrews_ok = andrews_ok_at(i - 1)

        valid_inputs = (
            not np.isnan(atr_v[i - 1]) and not np.isnan(ctx_support_v[i - 1])
            and not np.isnan(local_range_v[i - 1]) and local_range_v[i - 1] > 0
            and not np.isnan(context_range_v[i - 1]) and context_range_v[i - 1] > 0
        )
        gated_signal = long_signal_prev and andrews_ok
        is_fresh_entry = (i > warmup and len(tranches) == 0 and gated_signal and mature and valid_inputs)
        is_pyramid_add = (
            i > warmup and 0 < len(tranches) < MAX_TRANCHES and gated_signal and valid_inputs
            and high[i - 1] > state["last_pyramid_high"]
        )
        if not (is_fresh_entry or is_pyramid_add):
            return None

        entry_price = o[i]
        stop_price = min(ctx_support_v[i - 1], entry_price * 0.999)
        stop_pct = (entry_price - stop_price) / entry_price
        risk_pct = p["risk_pct"]
        if win_streak >= RULE3_STREAK:
            risk_pct *= RULE3_SIZE_MULT
        size_frac = min(1.0 / MAX_TRANCHES, risk_pct / stop_pct) if stop_pct > 0 else 0.0
        if size_frac <= 0:
            return None
        state["last_pyramid_high"] = max(state["last_pyramid_high"], high[i - 1]) if is_pyramid_add else high[i - 1]
        return {
            "entry": entry_price, "stop": stop_price, "remaining": size_frac,
            "val_done": False, "conf_done": False, "pnl_accum": 0.0,
            "val_px": entry_price + local_range_v[i - 1],
            "conf_px": entry_price + context_range_v[i - 1],
            "lim_px": entry_price + 1.5 * context_range_v[i - 1],
        }

    gated_long_signal = np.array([long_signal[i] and andrews_ok_at(i) for i in range(n)])

    raw = run_position_engine(
        n, o, high, low, c, gated_long_signal, open_tranche_fn,
        val_close_frac=p["val_close"], conf_close_frac=p["conf_close"],
        conf_to_be=True, max_tranches=MAX_TRANCHES, fee=FEE,
    )
    return {
        "n_trades": raw["n_trades"], "max_dd_%": raw["max_dd_%"],
        "total_return_%": raw["total_return_%"], "win_rate_%": raw["win_rate_%"],
        "profit_factor": raw["profit_factor"],
    }


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    rows = []
    for symbol in symbols:
        h1 = load_h1(symbol)
        h4 = resample(h1, "4h")
        for profile in PROFILES_V4:
            for mode in ANDREWS_MODES:
                res = run_andrews(h4.copy(), profile, mode=mode)
                rows.append({"symbol": symbol, "profile": profile, "mode": mode, **res})
    result = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 20)
    print(result.to_string(index=False))
    result.to_csv("andrews_gate_alternative_results.csv", index=False)

    print("\n--- Comparaison honnête : moyennes sur les 16 combinaisons actif×profil ---")
    summary = result.groupby("mode")[["total_return_%", "win_rate_%", "profit_factor", "n_trades"]].mean().round(2)
    print(summary)


if __name__ == "__main__":
    main()
