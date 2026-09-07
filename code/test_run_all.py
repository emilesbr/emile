"""
Tests pour run_all.py — pas des tests de la VALEUR des résultats de backtest
(déjà couverte par test_position_engine.py/test_proxy_v2.py/etc.), seulement
de la mécanique du point d'entrée unique lui-même :
  - l'inventaire des moteurs est cohérent (alias uniques, modules important
    réellement, chacun expose bien une fonction `main`) ;
  - un rejeu réel en mode `--only` sur les 2 moteurs les plus rapides (base,
    v4) fonctionne de bout en bout et produit les CSV attendus, dans un
    répertoire de sortie temporaire (jamais dans le dépôt).

Ne lance PAS `--confirm-full` ici (trop long pour une suite de tests
unitaires) — voir docstring de run_all.py pour l'estimation du temps complet.
"""
import importlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_all


def test_engine_aliases_unique():
    aliases = [e.alias for e in run_all.ENGINES]
    assert len(aliases) == len(set(aliases)), "alias en doublon dans ENGINES"


def test_fast_first_order_covers_all_aliases():
    assert set(run_all.FAST_FIRST_ORDER) == set(run_all.ENGINES_BY_ALIAS.keys())


def test_every_engine_module_importable_and_has_main():
    for engine in run_all.ENGINES:
        module = importlib.import_module(engine.module)
        assert hasattr(module, "main"), f"{engine.module}.main() introuvable"
        assert callable(module.main)


def test_only_rejects_unknown_alias():
    rc = run_all.main(["--only", "ce_moteur_n_existe_pas"])
    assert rc == 2


def test_no_args_refuses_to_run_everything():
    # Ni --only ni --confirm-full : ne doit RIEN exécuter (juste un message
    # d'erreur), pas déclencher un rejeu complet par défaut.
    rc = run_all.main([])
    assert rc == 2


def test_real_run_only_base_and_v4():
    """Rejeu réel (pas un mock) des 2 moteurs les plus rapides, dans un
    répertoire temporaire — vérifie que le pipeline complet (import direct,
    exécution de main(), redirection du CSV relatif) fonctionne vraiment."""
    with tempfile.TemporaryDirectory() as tmp:
        rc = run_all.main(["--only", "base,v4", "--output-dir", tmp])
        assert rc == 0
        base_csv = Path(tmp) / run_all.ENGINES_BY_ALIAS["base"].csv
        v4_csv = Path(tmp) / run_all.ENGINES_BY_ALIAS["v4"].csv
        assert base_csv.exists() and base_csv.stat().st_size > 0
        assert v4_csv.exists() and v4_csv.stat().st_size > 0


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"OK   {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passent")
    raise SystemExit(1 if failures else 0)
