#!/usr/bin/env python3
"""PreToolUse hook (Bash) -- verifie qu'une affirmation de tests ajoutes dans
un message `git commit` correspond au nombre reel de nouvelles fonctions de
test ajoutees par les fichiers que la meme commande passe a `git add`.

Adapte depuis ideeri-v2 (`.claude/hooks/test_claim_check.py`, incident du
3 aout 2026, commit f35a559 : "4 tests rouge/vert dedies" annonces, 3 reels).
Le mecanisme de comptage (compter les lignes `+def test_...` du diff pour les
fichiers `git add`es dans la meme commande) est generique et reste identique.
Ce qui a du etre change : le motif de declenchement. La version ideeri-v2
cherche les mots "rouge" ET "vert" dans le meme paragraphe -- verifie sur
l'historique complet de emile (`git log --all --grep=rouge`) : cette
formulation n'est JAMAIS utilisee ici. La convention reelle de ce depot,
observee dans docs/PLAN.md et docs/STATUS.md, est soit un delta explicite
par fichier ("test_position_engine.py 8->13, test_regime_classifier.py
10->15", "13->22 dans test_position_engine.py"), soit un compte absolu
qualifie ("3 nouveaux tests (test_fibonacci.py, 8/8)", "4 tests ajoutes").
Une version copiee telle quelle serait restee aussi inerte que les hooks
day_mode_*/pre_deploy_check/worktree_path_guard retires du depot le meme
jour (voir git log) -- jamais un vrai garde-fou, juste un fichier present.

Portee volontairement etroite, meme politique que l'original (et que
pre_deploy_check.py) : mieux vaut un faux negatif (phrasing non reconnu,
message sans nombre, pas de `git add` de fichier de test) qu'un faux positif
qui bloque a tort une commande qui ne suit pas le motif attendu. Un claim
n'est verifie QUE s'il est rattache sans ambiguite (meme paragraphe, fichier
le plus proche) a un fichier de test qui est a la fois nomme dans le message
ET reellement present dans le `git add` de la commande.

Limite de conception assumee : ce hook compte les lignes ajoutees
`+def test_...`/`+async def test_...`, pas une notion plus fine de
"vraiment nouveau vs renomme/deplace" -- un renommage produit une ligne +
qui compte comme une addition (meme limite que l'original, voir ses tests).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

TEST_FILE_RE = re.compile(r"tests?/.*\.py$")
DEF_TEST_DIFF_RE = re.compile(r"^\+\s*(?:async\s+def|def)\s+test_\w+")
DEF_TEST_PLAIN_RE = re.compile(r"^\s*(?:async\s+def|def)\s+test_\w+", re.MULTILINE)

# Nom de fichier de test mentionne en toutes lettres dans le message
# (avec ou sans backticks/chemin devant, ex. "test_fibonacci.py",
# "`test_position_engine.py`", "tests/unit/test_ut2.py").
FILENAME_RE = re.compile(r"(test_\w+\.py)")
# Delta explicite "8->13" / "8→13" -- claim = after - before.
DELTA_RE = re.compile(r"(\d+)\s*(?:->|→)\s*(\d+)")
# Compte absolu qualifie explicitement comme NOUVEAU/AJOUTE -- claim = N.
# (glossaire volontairement etroit, celui deja observe dans ce depot ;
# ne pas elargir a "N tests" seul, trop ambigu -- ce serait souvent le
# total de la suite, pas un delta de cette commande.)
ABSOLUTE_NEW_RE = re.compile(
    r"(\d+)\s+(?:nouveaux?\s+tests?|nouvelles?\s+tests?|tests?\s+ajout[ée]s?|"
    r"tests?\s+suppl[ée]mentaires?)",
    re.IGNORECASE,
)

_MAX_PROXIMITY_CHARS = 80  # fenetre max entre un claim et le nom de fichier associe


def _extract_cwd(command: str) -> str | None:
    m = re.search(r"^\s*cd\s+(\S+)", command, re.MULTILINE)
    return m.group(1) if m else None


def _extract_commit_message(command: str) -> str | None:
    # Motif systematique de ce depot : git commit -m "$(cat <<'EOF' ... EOF )"
    m = re.search(r"<<'EOF'\n(.*?)\nEOF", command, re.DOTALL)
    if m:
        return m.group(1)
    # Repli : -m "..." ou -m '...' sur une seule ligne.
    m = re.search(r"""-m\s+(["'])(.*?)\1""", command, re.DOTALL)
    if m:
        return m.group(2)
    return None


def _extract_added_test_files(command: str) -> list[str]:
    files: list[str] = []
    for m in re.finditer(r"^\s*git add\s+(.+)$", command, re.MULTILINE):
        for tok in m.group(1).split():
            if TEST_FILE_RE.search(tok):
                files.append(tok)
    return files


def _find_claims_per_file(message: str) -> dict[str, int]:
    """Associe a chaque fichier de test NOMME dans le message le nombre de
    tests que le message affirme y avoir ajoutes -- delta explicite en
    priorite, sinon compte absolu qualifie "nouveau/ajoute". Un claim n'est
    retenu que s'il existe un nom de fichier dans une fenetre de
    _MAX_PROXIMITY_CHARS caracteres (le plus proche gagne). Si un meme
    fichier recoit plusieurs claims dans le message (ex. un chiffre corrige
    en cours de paragraphe), le DERNIER l'emporte -- meme raison que
    l'original : une correction cite d'abord l'ancien chiffre errone."""
    claims: dict[str, int] = {}

    filename_matches = list(FILENAME_RE.finditer(message))
    if not filename_matches:
        return claims

    def _nearest_filename(pos: int) -> str | None:
        best = None
        best_dist = _MAX_PROXIMITY_CHARS + 1
        for fm in filename_matches:
            dist = min(abs(fm.start() - pos), abs(fm.end() - pos))
            if dist < best_dist:
                best_dist = dist
                best = fm.group(1)
        return best if best_dist <= _MAX_PROXIMITY_CHARS else None

    for dm in DELTA_RE.finditer(message):
        fname = _nearest_filename(dm.start())
        if fname is None:
            continue
        before, after = int(dm.group(1)), int(dm.group(2))
        claims[fname] = after - before

    for am in ABSOLUTE_NEW_RE.finditer(message):
        fname = _nearest_filename(am.start())
        if fname is None:
            continue
        claims[fname] = int(am.group(1))

    return claims


def _count_new_tests_in_file(cwd: str, file: str) -> int | None:
    """Compte les fonctions test_* ajoutees par CE fichier. None si le
    compte n'a pas pu etre etabli avec confiance -- l'appelant doit alors
    s'abstenir de comparer, pas conclure a un ecart."""
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", file],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if status.returncode != 0:
        return None
    out = status.stdout.strip()
    if out.startswith("??"):
        try:
            with open(f"{cwd}/{file}", encoding="utf-8") as fh:
                content = fh.read()
        except Exception:
            return None
        return len(DEF_TEST_PLAIN_RE.findall(content))

    try:
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--", file],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if diff.returncode != 0:
        return None
    total = 0
    for line in diff.stdout.splitlines():
        if line.startswith("+++"):
            continue
        if DEF_TEST_DIFF_RE.match(line):
            total += 1
    return total


def check_command(command: str, payload_cwd: str | None = None) -> str | None:
    """Coeur testable du hook. Retourne une raison de deni (str) si un
    ecart est detecte sur au moins un fichier, None si le commit doit etre
    autorise (y compris toute ambiguite -- allow silencieux)."""
    if "git commit" not in command:
        return None
    message = _extract_commit_message(command)
    if not message:
        return None
    claims = _find_claims_per_file(message)
    if not claims:
        return None
    added_files = set(_extract_added_test_files(command))
    if not added_files:
        return None
    cwd = _extract_cwd(command) or payload_cwd or "/home/emilesbr/emile"

    mismatches = []
    for fname, claimed in claims.items():
        matching_added = [f for f in added_files if f.endswith(fname)]
        if not matching_added:
            continue  # fichier nomme dans le message mais pas git add -- rien a verifier
        for f in matching_added:
            actual = _count_new_tests_in_file(cwd, f)
            if actual is None or actual == claimed:
                continue
            mismatches.append((f, claimed, actual))

    if not mismatches:
        return None

    details = "\n".join(
        f"  - {f} : message annonce {claimed} nouveau(x) test(s), "
        f"{actual} reellement trouve(s) (def test_ ajoutees)"
        for f, claimed, actual in mismatches
    )
    return (
        f"Ecart detecte entre l'affirmation de tests ajoutes et le nombre "
        f"reel de nouvelles fonctions def test_ :\n{details}\n\n"
        f"Verifier avant de commiter (garde-fou adapte de l'incident "
        f"ideeri-v2 du 3 aout 2026, commit f35a559 -- une affirmation "
        f"similaire etait fausse, trouvee seulement par une revue "
        f"independante) : soit corriger le chiffre dans le message, soit "
        f"confirmer manuellement que le compte automatique se trompe "
        f"(ex. fonction renommee plutot qu'ajoutee) avant de recommiter."
    )


def _deny(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        tool_name = payload.get("tool_name")
        tool_input = payload.get("tool_input") or {}
        command = tool_input.get("command")
        payload_cwd = payload.get("cwd")
    except Exception:
        return

    if tool_name != "Bash" or not isinstance(command, str):
        return

    reason = check_command(command, payload_cwd if isinstance(payload_cwd, str) else None)
    if reason is not None:
        _deny(reason)


if __name__ == "__main__":
    main()
    sys.exit(0)
