"""
Gate d'entrée RANGE — UNE SEULE implémentation, réutilisée par
`backtest_phase2_faithful.py` (moteur RANGE seul) ET `unified_protocol.py`
(routeur RANGE+TENDANCE) ET `risk_aggregation_triple_system.py`.

CHANTIER D'ARCHITECTURE (suite du 24e round, cf. PLAN.md) : `_range_gate`/
`_range_gate_extra` vivaient jusqu'ici comme fermetures imbriquées DANS
`backtest_phase2_faithful.py::_run_core` (une copie) ET comme fonctions de
module dans `unified_protocol.py` (une AUTRE copie, texte identique mais
maintenue séparément) -- même risque que la duplication éliminée au 24e
round pour `risk_aggregation_triple_system.py`, jamais traité pour CE
côté-ci. Preuve concrète que la copie de `faithful.py` avait bien dérivé du
texte au moins une fois : les commentaires différaient légèrement d'un
fichier à l'autre bien que la LOGIQUE soit restée identique -- un pur hasard
qu'aucun comportement n'ait divergé, pas une garantie structurelle.

Extraites ICI (module neutre, sans dépendance vers `backtest_phase2_
faithful.py` NI `unified_protocol.py`) pour casser le cycle d'import qui
empêchait `faithful.py` d'importer directement la version de
`unified_protocol.py` (celui-ci importe déjà plusieurs symboles de
`faithful.py` -- `REVERSE_SCOPED_PROFILE`, `run_faithful`, `_add_squeeze_
columns`, `range_money_management_fracs`).

Fonctionne sur un `feat` dict indexé de façon ABSOLUE (mêmes clés dans les
deux appelants -- `regime_d1`/`regime`/`pitchfork_p1`/`close`/`gate_score`/
`gate_regime`/`wall_street_active`) : `backtest_phase2_faithful.py` expose
désormais un alias `feat["regime"]` (MÊME array que `feat["regime_h4"]`,
jamais recalculé) pour que cette fonction n'ait pas besoin de connaître les
deux noms.
"""
import numpy as np


def range_gate(feat: dict, i: int) -> bool:
    """Gate d'entrée RANGE (entrée fraîche ET renfort) -- CORRECTION EXCES H4
    (le régime EXCES du H4 natif, `feat["regime"]`, doit bloquer -- "Bulle/
    Excès -> NE PAS TRADER", RULES_EXTRACTION.md §1) + CORRECTION CONFLIT MTF
    (ne jamais ouvrir si le contexte D1 est lui-même en régime range, source
    #5 "l'erreur numéro un") + Fourchette d'Andrews contextuelle ("prend le
    relais" seulement en régime RANGE_TENDANCIEL, cf. `backtest_phase2_
    faithful.py`/`andrews_gate_alternative.py`)."""
    d1_not_range = feat["regime_d1"][i] not in ("RANGE_NEUTRE", "RANGE_TENDANCIEL")
    andrews_ok = (
        feat["regime"][i] != "RANGE_TENDANCIEL"
        or (not np.isnan(feat["pitchfork_p1"][i]) and feat["close"][i] > feat["pitchfork_p1"][i])
    )
    return bool(
        feat["gate_score"][i] >= 2 and feat["gate_regime"][i] != "EXCES"
        and feat["regime"][i] != "EXCES" and d1_not_range and andrews_ok
    )


def range_gate_extra(feat: dict, j: int) -> tuple:
    """Abstention Wall Street NON CONDITIONNELLE (bloque entrée fraîche ET
    renfort) + CORRECTION PYRAMIDALISATION-RÉGIME (le renfort, pas l'entrée
    fraîche, exige EN PLUS le régime H4 natif TENDANCE/RANGE_TENDANCIEL --
    "Renfort" n'apparaît jamais dans la table Money Management RANGE, §3,
    réservé à la table TENDANCE, §4). Renvoie `(fresh_extra, pyramid_extra)`,
    cf. `position_engine.make_open_tranche_fn`."""
    abstain = bool(feat["wall_street_active"][j])
    g = range_gate(feat, j) and not abstain
    pyramiding_allowed = feat["regime"][j] in ("TENDANCE", "RANGE_TENDANCIEL")
    return g, (g and pyramiding_allowed)
