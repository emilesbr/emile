"""
run_all.py — point d'entrée unique pour rejouer les moteurs de backtest
Phase 2 du projet, sans lancer chaque script `backtest_phase2_*.py` à la main.

CONTEXTE (voir PLAN.md, critères de sortie Phase 2 -> Phase 3, item 4) :
jusqu'ici, "refaire un backtest avec le moteur actuel" était un geste ad hoc
répété à chaque fois (cascade3, rejeu structure causale, MTF_CROSS_VALIDATION,
etc.), chaque script produisant son propre CSV, lancé manuellement. Ce fichier
ne réécrit AUCUN moteur existant : il se contente d'importer chaque script
`backtest_phase2_*.py` du dossier `code/` et d'appeler sa fonction `main()`
directement (pas de sous-processus), de chronométrer chacun, et d'agréger un
résumé final succès/échec/durée/CSV produit.

CE QUE CE SCRIPT N'EST PAS
--------------------------
- Ce n'est PAS un rejeu automatique de tout l'historique du projet. Les CSV
  déjà commités à la racine du dépôt (phase2_v7_mtf_results.csv,
  phase2_v5_causal_results.csv, MTF_CROSS_VALIDATION_H4_D1.md, etc.) restent
  la référence citée par les .md tant que ce script n'a pas été relancé pour
  de vrai et ses sorties comparées/promues à la main. Lancer `run_all.py` ne
  met à jour aucun document.
- Pour ne surtout pas écraser silencieusement ces CSV de référence, ce script
  n'écrit JAMAIS dans le dossier racine du dépôt : chaque moteur est exécuté
  avec pour répertoire de travail `code/run_all_output/` (créé au besoin), où
  ses CSV relatifs (ex. `phase2_v7_mtf_results.csv`) atterrissent. Comparer
  ces fichiers aux CSV commités avant de considérer un rejeu comme "à jour".
- Ce n'est pas un remplacement des scripts individuels : chacun reste
  exécutable seul (`python code/backtest_phase2_v7.py`) exactement comme
  avant ; ce script les appelle sans les modifier.
- Aucune automatisation d'exécution réelle : uniquement du backtest sur
  données historiques déjà téléchargées (principe acté, PLAN.md en tête de
  document).

MOTEURS COUVERTS (13 scripts `backtest_phase2_*.py` de `code/`)
----------------------------------------------------------------
Alias utilisable avec --only, module, description, CSV produit :

  base           backtest_phase2       Money management de base (table "trade
                                        spéculatif" range), signal EMA confluence,
                                        H4+D1, 4 profils (FAIBLE/MODERE/AGRESSIF/
                                        TRES_AGRESSIF) x BTC/ETH/BNB/SOL.
                                        -> phase2_moneymanagement_results.csv
  v4             backtest_phase2_v4    + Règle de Trois, amplitude en durée,
                                        maturité swing (causale, P0-bis), pyramidalisation.
                                        H4+D1 x 4 profils x 4 symboles.
                                        -> phase2_v4_results.csv
                                        (PLAN.md : corrigé P0-bis dans le code mais pas
                                        encore rejoué "pour de vrai" avant ce script)
  v5             backtest_phase2_v5    Signal remplacé par proxy_v2 (TSI+cycle+structure).
                                        H4+D1 x 4 profils x 4 symboles.
                                        -> phase2_v5_results.csv
  v6             backtest_phase2_v6    + classification de régime (Range/Tendance/Excès),
                                        interdiction EXCES. Chaque profil rejoué
                                        avec ET sans gate régime.
                                        -> phase2_v6_regime_results.csv
  v7             backtest_phase2_v7    + validation croisée réelle H4 execution / D1
                                        référence (sans lookahead). 3 variantes par
                                        profil x symbole (gate MTF, solo H4, + stop D1 réel).
                                        -> phase2_v7_mtf_results.csv
  v7_reverse     backtest_phase2_v7_reverse  Mécanisme "+Reverse" (table range, profil
                                        TRES_AGRESSIF uniquement) x 4 symboles,
                                        avec/sans reverse_at_limit.
                                        -> phase2_v7_reverse_results.csv
  capital_tiers  backtest_phase2_capital_tiers  v7 paramétré par capital de départ
                                        absolu (5k/50k/500k EUR, un montant par
                                        palier) x 4 profils x 4 symboles.
                                        -> phase2_capital_tiers_results.csv
                                        (même réserve P0-bis que v4 : pas encore rejoué)
  diversification  backtest_phase2_diversification  Diversification "1%+1%"
                                        (proxy_v2 + cluster_technique, Pattern A+B)
                                        x 4 symboles, comparaison naïve + isolée.
                                        -> phase2_diversification_results.csv
  fib            backtest_phase2_fib   Filtre Fibonacci retracement sur l'entrée
                                        fraîche (variantes favorable/optimal/incl.
                                        pyramide) x 4 profils x 4 symboles.
                                        -> phase2_fib_results.csv
  patterns       backtest_phase2_patterns  Wall Street (abstention élargissement),
                                        canal manuel (stop), Andrews Pitchfork (gate)
                                        x 4 profils x 4 symboles, mode "none" en référence.
                                        -> phase2_patterns_results.csv
  trend          backtest_phase2_trend  Table "trade de tendance" à 5 étapes,
                                        H4 x profils PROFILES_TREND x 4 symboles.
                                        -> phase2_trend_table_results.csv
  ut2            backtest_phase2_ut2   Validation multi-timeframe à N niveaux
                                        (none/d1_only/ut2_strict/d1_and_weekly,
                                        D1+Hebdomadaire) x 4 profils x 4 symboles.
                                        -> phase2_ut2_results.csv
  recommended    backtest_phase2_recommended  LA config recommandée (synthèse,
                                        vague 4 -- cf. CONFIGURATION_RECOMMANDEE.md) :
                                        cycle+structure causaux, gate Hebdo seul
                                        (UT+2 strict), sans Fibonacci/Andrews/
                                        Wall Street/canal manuel/diversification/
                                        reverse. H4 x 4 profils x 4 symboles.
                                        -> phase2_recommended_results.csv

Volontairement HORS PÉRIMÈTRE de ce script (pas des moteurs de backtest
indépendants, mais des analyses dérivées qui lisent/comparent des CSV déjà
produits par les moteurs ci-dessus) : `ablation_test_cycle.py`,
`funding_rate_exact.py`, `structure_causal_vs_batch_comparison.py`,
`replay_structure_causal_v5_v6_v7.py`, `cycle_causal_window_selection.py`.
Ces scripts peuvent toujours être relancés à la main comme avant.

UTILISATION
-----------
  # Lister les moteurs disponibles sans rien exécuter
  python code/run_all.py --list

  # Rejouer seulement 1-2 moteurs rapides (recommandé pour vérifier que
  # tout fonctionne, ou pour un rejeu ciblé après une modif du moteur)
  python code/run_all.py --only base,v4

  # Rejouer TOUT (long, cf. estimation ci-dessous) -- nécessite --confirm-full
  # pour éviter un déclenchement accidentel d'une exécution complète
  python code/run_all.py --confirm-full

  # Choisir un répertoire de sortie différent (par défaut : code/run_all_output/)
  python code/run_all.py --only v7 --output-dir /tmp/mon_rejeu

TEMPS D'EXÉCUTION MESURÉ (2026-09-07, `--confirm-full` réellement exécuté
sur cette machine, pas une estimation)
---------------------------------------------------------------------------
  base             2.1s      v7_reverse        3.8s
  v4               3.8s      capital_tiers    18.3s
  v5               4.9s      diversification   7.0s
  v6              13.2s      fib              24.8s
  v7              18.7s      trend             7.2s
                              ut2              27.4s
                              patterns         27.7s

  recommended       7.0s (ajouté après ce chronométrage initial -- moteur
                    le plus simple des 13 : H4+Hebdo seulement, pas de D1)

  TOTAL des 12 moteurs pré-existants : 158.8s (~2,6 min) -- BTC/ETH/BNB/SOL,
  plusieurs années de H1 rééchantillonné en H4/D1/Hebdo (~50-57k bougies H1
  par actif). +7.0s pour "recommended" (mesuré séparément, cf. ci-dessus),
  soit ~166s (~2,8 min) pour les 13 moteurs.

Nettement plus rapide qu'on ne le craignait a priori : ces moteurs sont tous
vectorisés (pandas/numpy), pas de boucle Python coûteuse par bougie. Les
moteurs qui ajoutent une 3e série temporelle (v7, capital_tiers, fib, ut2 --
tous basés sur run_v7/attach_higher_context) ou qui rejouent plusieurs
variantes par profil (patterns : 4 modes, ut2 : 4 gate_modes, fib : 4
variantes) sont les plus longs, mais restent de l'ordre de 15-30s chacun.
Ce chiffre (2,6 min) date de ce commit ; à remesurer si un moteur devient
significativement plus lourd (ex. ajout d'une grille de paramètres plus large).

TESTS
-----
`code/test_run_all.py` vérifie l'inventaire des moteurs et un rejeu réel en
mode `--only` sur les 2 moteurs les plus rapides (base, v4).
"""
from __future__ import annotations

import argparse
import importlib
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    # Les scripts backtest_phase2_*.py font `from backtest_phase2 import ...`
    # (import absolu par nom de module) : il faut que code/ soit sur
    # sys.path, comme c'est le cas naturellement quand on lance
    # `python code/backtest_phase2_v7.py` directement (sys.path[0] =
    # dossier du script). Ici on l'ajoute explicitement pour que
    # run_all.py fonctionne aussi bien en `python run_all.py` (depuis
    # code/) qu'en `python code/run_all.py` (depuis la racine du dépôt),
    # ou importé comme module par un test.
    sys.path.insert(0, str(CODE_DIR))

DEFAULT_OUTPUT_DIR = CODE_DIR / "run_all_output"


@dataclass
class Engine:
    alias: str
    module: str
    description: str
    csv: str


ENGINES: list[Engine] = [
    Engine("base", "backtest_phase2",
           "Money management de base (table range), signal EMA confluence, "
           "H4+D1 x 4 profils x BTC/ETH/BNB/SOL",
           "phase2_moneymanagement_results.csv"),
    Engine("v4", "backtest_phase2_v4",
           "+ Regle de Trois, amplitude en duree, maturite swing causale, "
           "pyramidalisation. H4+D1 x 4 profils x 4 symboles",
           "phase2_v4_results.csv"),
    Engine("v5", "backtest_phase2_v5",
           "Signal remplace par proxy_v2 (TSI+cycle+structure). "
           "H4+D1 x 4 profils x 4 symboles",
           "phase2_v5_results.csv"),
    Engine("v6", "backtest_phase2_v6",
           "+ classification de regime (Range/Tendance/Exces), interdiction "
           "EXCES. Chaque profil rejoue avec ET sans gate regime",
           "phase2_v6_regime_results.csv"),
    Engine("v7", "backtest_phase2_v7",
           "+ validation croisee reelle H4 execution / D1 reference. "
           "3 variantes (gate MTF / solo H4 / + stop D1 reel) x 4 profils x 4 symboles",
           "phase2_v7_mtf_results.csv"),
    Engine("v7_reverse", "backtest_phase2_v7_reverse",
           "Mecanisme +Reverse (table range, profil TRES_AGRESSIF) x 4 symboles, "
           "avec/sans reverse_at_limit",
           "phase2_v7_reverse_results.csv"),
    Engine("capital_tiers", "backtest_phase2_capital_tiers",
           "v7 parametre par capital absolu (5k/50k/500k EUR) x 4 profils x 4 symboles",
           "phase2_capital_tiers_results.csv"),
    Engine("diversification", "backtest_phase2_diversification",
           "Diversification 1%+1% (proxy_v2 + cluster_technique) x 4 symboles",
           "phase2_diversification_results.csv"),
    Engine("fib", "backtest_phase2_fib",
           "Filtre Fibonacci retracement sur l'entree fraiche (variantes "
           "favorable/optimal/incl. pyramide) x 4 profils x 4 symboles",
           "phase2_fib_results.csv"),
    Engine("patterns", "backtest_phase2_patterns",
           "Wall Street / canal manuel / Andrews Pitchfork x 4 modes x 4 "
           "profils x 4 symboles",
           "phase2_patterns_results.csv"),
    Engine("trend", "backtest_phase2_trend",
           "Table 'trade de tendance' a 5 etapes, H4 x profils PROFILES_TREND "
           "x 4 symboles",
           "phase2_trend_table_results.csv"),
    Engine("ut2", "backtest_phase2_ut2",
           "Validation multi-timeframe a N niveaux (D1+Hebdomadaire) x 4 "
           "gate_modes x 4 profils x 4 symboles",
           "phase2_ut2_results.csv"),
    Engine("recommended", "backtest_phase2_recommended",
           "LA config recommandee (synthese) : cycle+structure causaux, "
           "gate Hebdo seul (UT+2 strict), sans Fibonacci/Andrews/Wall "
           "Street/canal manuel/diversification/reverse. "
           "H4 x 4 profils x 4 symboles",
           "phase2_recommended_results.csv"),
]

ENGINES_BY_ALIAS = {e.alias: e for e in ENGINES}

# Ordre de rapidité constaté empiriquement (les plus rapides d'abord), pour
# que --confirm-full donne des résultats utiles le plus tôt possible même
# si on interrompt en cours de route.
FAST_FIRST_ORDER = [
    "base", "v4", "v5", "v6", "v7", "v7_reverse",
    "capital_tiers", "diversification", "fib", "trend", "ut2", "patterns",
    "recommended",
]


@dataclass
class RunResult:
    alias: str
    ok: bool
    seconds: float
    csv_path: Path | None
    error: str = ""


def list_engines() -> None:
    print(f"{'alias':<16} {'module':<32} description")
    print("-" * 100)
    for e in ENGINES:
        print(f"{e.alias:<16} {e.module:<32} {e.description}")
    print(f"\n{len(ENGINES)} moteurs inventoriés.")


def run_one(engine: Engine, output_dir: Path) -> RunResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    prev_cwd = Path.cwd()
    try:
        # Import APRES avoir garanti code/ sur sys.path (voir plus haut).
        # importlib.import_module (pas __import__ direct) pour pouvoir
        # re-appeler proprement si le module était déjà importé par un
        # moteur précédent partageant des dépendances (ex. backtest_phase2).
        module = importlib.import_module(engine.module)
        import os
        os.chdir(output_dir)
        try:
            module.main()
        finally:
            os.chdir(prev_cwd)
        elapsed = time.monotonic() - start
        csv_path = output_dir / engine.csv
        if not csv_path.exists():
            return RunResult(engine.alias, False, elapsed, None,
                              error=f"main() a tourné sans erreur mais {engine.csv} est absent de {output_dir}")
        return RunResult(engine.alias, True, elapsed, csv_path)
    except Exception:
        elapsed = time.monotonic() - start
        return RunResult(engine.alias, False, elapsed, None, error=traceback.format_exc())
    finally:
        import os
        if Path.cwd() != prev_cwd:
            os.chdir(prev_cwd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rejoue un ou plusieurs moteurs backtest_phase2_*.py d'un coup "
                    "(voir docstring du fichier pour le détail complet).")
    parser.add_argument("--only", type=str, default=None,
                         help="liste d'alias séparés par des virgules (ex. v7,ut2). "
                              "Sans cette option, --confirm-full est requis pour tout lancer.")
    parser.add_argument("--confirm-full", action="store_true",
                         help="confirme explicitement un rejeu de TOUS les moteurs "
                              "(peut prendre 15-40 min, cf. docstring).")
    parser.add_argument("--list", action="store_true",
                         help="affiche l'inventaire des moteurs disponibles et quitte, "
                              "sans rien exécuter.")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR),
                         help=f"répertoire où les CSV de ce rejeu atterrissent "
                              f"(défaut: {DEFAULT_OUTPUT_DIR}). Ne touche JAMAIS aux CSV "
                              f"commités à la racine du dépôt.")
    args = parser.parse_args(argv)

    if args.list:
        list_engines()
        return 0

    if args.only:
        aliases = [a.strip() for a in args.only.split(",") if a.strip()]
        unknown = [a for a in aliases if a not in ENGINES_BY_ALIAS]
        if unknown:
            print(f"Alias inconnu(s): {unknown}. Utilise --list pour voir les alias valides.",
                  file=sys.stderr)
            return 2
        selected = [ENGINES_BY_ALIAS[a] for a in aliases]
    elif args.confirm_full:
        selected = [ENGINES_BY_ALIAS[a] for a in FAST_FIRST_ORDER]
    else:
        print("Aucun --only fourni et --confirm-full absent : rien à faire.\n"
              "Utilise --only alias1,alias2 pour un sous-ensemble (recommandé), "
              "ou --confirm-full pour rejouer les 13 moteurs (long, cf. docstring).\n"
              "Utilise --list pour voir les alias disponibles.", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir).resolve()
    print(f"Rejeu de {len(selected)} moteur(s) -> sortie dans {output_dir}")
    print("Rappel : ceci ne remplace PAS les CSV déjà commités à la racine du dépôt, "
          "qui restent la référence citée par les .md tant que ces sorties n'ont pas "
          "été comparées et promues manuellement.\n")

    results: list[RunResult] = []
    total_start = time.monotonic()
    for engine in selected:
        print(f"--- [{engine.alias}] {engine.module} ---", flush=True)
        res = run_one(engine, output_dir)
        results.append(res)
        status = "OK" if res.ok else "ECHEC"
        print(f"[{engine.alias}] {status} en {res.seconds:.1f}s"
              + (f" -> {res.csv_path}" if res.ok else f"\n{res.error}"))
        print()
    total_elapsed = time.monotonic() - total_start

    print("=" * 100)
    print("RÉSUMÉ")
    print("=" * 100)
    print(f"{'alias':<16} {'statut':<8} {'durée (s)':>10}  CSV")
    n_ok = 0
    for res in results:
        status = "OK" if res.ok else "ECHEC"
        n_ok += int(res.ok)
        csv_repr = str(res.csv_path) if res.ok else "-"
        print(f"{res.alias:<16} {status:<8} {res.seconds:>10.1f}  {csv_repr}")
    print("-" * 100)
    print(f"{n_ok}/{len(results)} moteur(s) réussi(s) — durée totale {total_elapsed:.1f}s "
          f"({total_elapsed/60:.1f} min)")
    if n_ok < len(results):
        print("\nDétail des échecs :")
        for res in results:
            if not res.ok:
                print(f"\n### {res.alias} ###\n{res.error}")

    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
