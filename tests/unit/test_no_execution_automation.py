"""
GARDE-FOU MÉCANIQUE anti-automatisation-prématurée -- construit ce cycle
(mobilisation multi-agents, bilan directeur "regard neuf", PLAN.md section
"Garde-fou mécanique").

Ce projet est Phase 1/2 par engagement explicite en tête de `PLAN.md` :
signal + décision HUMAINE uniquement, aucune automatisation d'exécution.
Jusqu'ici cet engagement reposait UNIQUEMENT sur l'accord verbal/textuel --
`ideeri-v2` (`CLAUDE.md` §16.4, même utilisateur, même pattern déjà documenté
dans ce projet pour d'autres risques : "un texte seul ne suffit pas à
garantir qu'il soit respecté au bon moment") avait déjà construit un
garde-fou mécanique équivalent pour ses propres actions à fort impact.

Ce test ne bloque RIEN aujourd'hui par la NÉGATIVE -- il échoue seulement si
un pattern d'automatisation d'exécution (clé API d'exchange, appel de
passage d'ordre, client d'exchange) apparaît un jour dans `code/`, pour
qu'un futur changement qui franchirait cette limite soit détecté à la
prochaine exécution de la suite de tests, pas découvert après coup. Coût de
construction jugé trivial par le bilan qui l'a recommandé -- exécuté à
chaque suite de tests comme les 20 autres fichiers, pas un script à part
qu'on pourrait oublier de lancer.

Volontairement GROSSIER (une liste de motifs textuels, pas une analyse
statique complète) -- l'objectif est un filet de sécurité qui se déclenche
sur l'ajout évident d'une dépendance d'exécution, pas une preuve formelle
d'absence totale d'automatisation. À faire évoluer si une future
bibliothèque légitime (ex. un client HTTP générique) déclenche un faux
positif -- ajouter une exception ciblée et documentée, pas relâcher le
motif en général.
"""
import os
import re
import sys

# Motifs qui indiqueraient une dépendance d'exécution réelle (passage
# d'ordre, credentials d'exchange) -- PAS une simple mention de "trading"/
# "position"/"risk" (omniprésentes dans ce projet, qui reste un backtest).
_FORBIDDEN_PATTERNS = [
    r"\bplace_order\b", r"\bcreate_order\b", r"\bcancel_order\b",
    r"\bccxt\b", r"\bpython[-_]binance\b",
    r"binance\.client\b", r"from binance\.", r"import binance\b",
    r"\bAPI_KEY\b", r"\bapi_secret\b", r"\bAPI_SECRET\b",
]
_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN_PATTERNS))

# Ce fichier lui-même contient les motifs interdits (dans _FORBIDDEN_PATTERNS
# et cette docstring) -- exclu explicitement de son propre scan, pas une
# faille du test.
_SELF = os.path.basename(__file__)

def _iter_production_py_files():
    here = os.path.dirname(os.path.abspath(__file__)) or "."
    for name in sorted(os.listdir(here)):
        if not name.endswith(".py"):
            continue
        if name == _SELF:
            continue
        yield os.path.join(here, name)

def test_no_exchange_execution_dependency_in_code():
    """Aucun fichier de production (`code/*.py`, hors ce test lui-même) ne
    doit contenir de motif de passage d'ordre ou de credentials d'exchange
    -- ce projet reste Phase 1/2 (signal + décision humaine), tant que ce
    test n'a pas été explicitement mis à jour pour refléter un changement
    de phase délibéré."""
    offenders = []
    for path in _iter_production_py_files():
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        m = _FORBIDDEN_RE.search(content)
        if m:
            offenders.append((os.path.basename(path), m.group(0)))
    assert not offenders, (
        "dépendance d'exécution d'exchange détectée -- ce projet est Phase 1/2 "
        "(signal + décision humaine uniquement, cf. tête de PLAN.md) : "
        f"{offenders}. Si ce changement de phase est délibéré (Phase 4/5), "
        "mettre à jour PLAN.md explicitement AVANT de faire évoluer ce test, "
        "pas l'inverse."
    )

def test_guard_is_actually_non_vacuous():
    """Contrôle positif : le motif de détection doit vraiment matcher sur un
    exemple délibérément fabriqué, sinon le test ci-dessus passerait
    trivialement sur une regex cassée."""
    assert _FORBIDDEN_RE.search("client.place_order(symbol='BTCUSDT')")
    assert _FORBIDDEN_RE.search("import ccxt")
    assert _FORBIDDEN_RE.search("API_KEY = 'abc'")
    assert not _FORBIDDEN_RE.search("risk_pct = compute_position_size(entry, stop)")

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
