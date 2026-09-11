"""
Tests unitaires de .claude/hooks/test_claim_check.py::check_command.

Version adaptee du garde-fou ideeri-v2 (meme incident d'origine, 3 aout
2026, commit f35a559 : "N tests rouge/vert" annonces sans correspondre au
reel) mais motif de declenchement different -- la formulation "rouge/vert"
n'est jamais utilisee dans l'historique emile ; la convention reelle est un
delta explicite par fichier ("test_x.py 8->13") ou un compte absolu qualifie
("3 nouveaux tests"). Voir la docstring du hook pour le detail complet.

Utilise de vrais depots git temporaires (subprocess), pas de mock sur
git status/diff -- meme discipline que le reste de ce depot ("verifier
empiriquement plutot qu'affirmer").
"""

import importlib.util
import subprocess
from pathlib import Path

_HOOK_PATH = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "test_claim_check.py"
_spec = importlib.util.spec_from_file_location("test_claim_check", _HOOK_PATH)
test_claim_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(test_claim_check)

check_command = test_claim_check.check_command


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(tmp_path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "tests").mkdir()
    return repo


def _commit_baseline(repo, test_file_content="") -> None:
    (repo / "tests" / "test_example.py").write_text(test_file_content, encoding="utf-8")
    _git(repo, "add", "tests/test_example.py")
    _git(repo, "commit", "-q", "-m", "baseline")


def _commit_command(repo, message, add_files):
    files_str = " ".join(add_files)
    return f"cd {repo}\ngit add {files_str}\ngit commit -m \"$(cat <<'EOF'\n{message}\nEOF\n)\""


def _commit_command_no_cd(message, add_files):
    files_str = " ".join(add_files)
    return f"git add {files_str}\ngit commit -m \"$(cat <<'EOF'\n{message}\nEOF\n)\""


class TestAvantLeGateAllowSilencieux:
    def test_pas_de_git_commit_allow(self):
        assert check_command("echo hello") is None

    def test_commit_sans_message_extractible_allow(self):
        assert check_command("git commit --amend --no-edit") is None

    def test_message_sans_nom_de_fichier_allow(self):
        cmd = "git commit -m \"$(cat <<'EOF'\n9 tests ajoutes ce cycle.\nEOF\n)\""
        assert check_command(cmd) is None

    def test_pas_de_fichier_de_test_dans_git_add_allow(self):
        cmd = (
            "git add emile/core/foo.py\n"
            "git commit -m \"$(cat <<'EOF'\ntest_foo.py 4->8, tests ajoutes.\nEOF\n)\""
        )
        assert check_command(cmd) is None

    def test_fichier_nomme_mais_pas_git_add_allow(self, tmp_path):
        """Le message cite un fichier de test qui n'est pas dans le git add
        de cette commande -- rien a verifier, allow (ex. mention d'un
        fichier de test deja existant, pas modifie par ce commit)."""
        repo = _init_repo(tmp_path)
        _commit_baseline(repo)
        cmd = _commit_command(
            repo, "test_position_engine.py 8->13, deja couvert ailleurs.", ["tests/test_example.py"]
        )
        assert check_command(cmd) is None


class TestDeltaExplicite:
    def test_delta_correct_allow(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit_baseline(repo, "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n\n\ndef test_c():\n    pass\n\n\ndef test_d():\n    pass\n\n\ndef test_e():\n    pass\n\n\ndef test_f():\n    pass\n\n\ndef test_g():\n    pass\n\n\ndef test_h():\n    pass\n")
        content = (repo / "tests" / "test_example.py").read_text(encoding="utf-8")
        content += "\n\ndef test_i():\n    pass\n\n\ndef test_j():\n    pass\n\n\ndef test_k():\n    pass\n\n\ndef test_l():\n    pass\n\n\ndef test_m():\n    pass\n"
        (repo / "tests" / "test_example.py").write_text(content, encoding="utf-8")
        cmd = _commit_command(repo, "test_example.py 8->13, calculs a la main.", ["tests/test_example.py"])
        assert check_command(cmd) is None

    def test_delta_incorrect_deny(self, tmp_path):
        """8->13 annonce 5 nouveaux tests, un seul reellement ajoute."""
        repo = _init_repo(tmp_path)
        _commit_baseline(repo, "def test_a():\n    pass\n")
        content = (repo / "tests" / "test_example.py").read_text(encoding="utf-8")
        content += "\n\ndef test_new_one():\n    pass\n"
        (repo / "tests" / "test_example.py").write_text(content, encoding="utf-8")
        cmd = _commit_command(repo, "test_example.py 8->13, calculs a la main.", ["tests/test_example.py"])
        reason = check_command(cmd)
        assert reason is not None
        assert "annonce 5" in reason
        assert "1 reellement" in reason

    def test_deux_fichiers_deux_deltas_agreges_correctement(self, tmp_path):
        """Reproduit le motif reel 'test_position_engine.py 8->13,
        test_regime_classifier.py 10->15' -- chaque delta doit etre
        rattache a SON fichier, pas confondu avec l'autre."""
        repo = _init_repo(tmp_path)
        _commit_baseline(repo)
        (repo / "tests" / "test_position_engine.py").write_text(
            "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n\n\ndef test_c():\n    pass\n\n\n"
            "def test_d():\n    pass\n\n\ndef test_e():\n    pass\n",
            encoding="utf-8",
        )
        (repo / "tests" / "test_regime_classifier.py").write_text(
            "def test_f():\n    pass\n\n\ndef test_g():\n    pass\n\n\ndef test_h():\n    pass\n\n\n"
            "def test_i():\n    pass\n\n\ndef test_j():\n    pass\n",
            encoding="utf-8",
        )
        cmd = _commit_command(
            repo,
            "test_position_engine.py 8->13, test_regime_classifier.py 10->15, calculs a la main.",
            ["tests/test_position_engine.py", "tests/test_regime_classifier.py"],
        )
        assert check_command(cmd) is None

    def test_un_des_deux_fichiers_faux_detecte(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit_baseline(repo)
        (repo / "tests" / "test_position_engine.py").write_text(
            "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n\n\ndef test_c():\n    pass\n\n\n"
            "def test_d():\n    pass\n\n\ndef test_e():\n    pass\n",
            encoding="utf-8",
        )
        (repo / "tests" / "test_regime_classifier.py").write_text(
            "def test_f():\n    pass\n",  # 1 seul, pas 5
            encoding="utf-8",
        )
        cmd = _commit_command(
            repo,
            "test_position_engine.py 8->13, test_regime_classifier.py 10->15, calculs a la main.",
            ["tests/test_position_engine.py", "tests/test_regime_classifier.py"],
        )
        reason = check_command(cmd)
        assert reason is not None
        assert "test_regime_classifier.py" in reason
        assert "annonce 5" in reason


class TestCompteAbsoluQualifie:
    def test_nouveaux_tests_correct_allow(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit_baseline(repo)
        (repo / "tests" / "test_fibonacci.py").write_text(
            "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n\n\ndef test_c():\n    pass\n",
            encoding="utf-8",
        )
        cmd = _commit_command(repo, "3 nouveaux tests (test_fibonacci.py, 8/8).", ["tests/test_fibonacci.py"])
        assert check_command(cmd) is None

    def test_tests_ajoutes_incorrect_deny(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit_baseline(repo)
        (repo / "tests" / "test_fibonacci.py").write_text(
            "def test_a():\n    pass\n", encoding="utf-8"
        )
        cmd = _commit_command(repo, "3 tests ajoutes (test_fibonacci.py).", ["tests/test_fibonacci.py"])
        reason = check_command(cmd)
        assert reason is not None
        assert "annonce 3" in reason
        assert "1 reellement" in reason

    def test_nombre_seul_sans_qualificatif_ignore(self, tmp_path):
        """'9 tests' seul (sans 'nouveaux'/'ajoutes'/delta) est trop ambigu
        (souvent un total de suite, pas un delta de cette commande) --
        volontairement pas traite comme un claim, allow."""
        repo = _init_repo(tmp_path)
        _commit_baseline(repo)
        (repo / "tests" / "test_fibonacci.py").write_text("x = 1\n", encoding="utf-8")
        cmd = _commit_command(repo, "9 tests (test_fibonacci.py, 8/8).", ["tests/test_fibonacci.py"])
        assert check_command(cmd) is None


class TestRenommageCompteCommeUneAddition:
    def test_renommage_simple_ne_declenche_pas_de_faux_ecart(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit_baseline(repo, "def test_old_name():\n    pass\n")
        (repo / "tests" / "test_example.py").write_text(
            "def test_new_name():\n    pass\n", encoding="utf-8"
        )
        cmd = _commit_command(repo, "1 nouveau test (test_example.py).", ["tests/test_example.py"])
        assert check_command(cmd) is None


class TestPayloadCwd:
    def test_payload_cwd_evite_le_faux_ecart_sans_cd(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit_baseline(repo)
        (repo / "tests" / "test_example.py").write_text(
            "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n", encoding="utf-8"
        )
        cmd = _commit_command_no_cd("2 nouveaux tests (test_example.py).", ["tests/test_example.py"])
        assert check_command(cmd, payload_cwd=str(repo)) is None

    def test_payload_cwd_detecte_un_vrai_ecart_sans_cd(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit_baseline(repo)
        (repo / "tests" / "test_example.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
        cmd = _commit_command_no_cd("4 nouveaux tests (test_example.py).", ["tests/test_example.py"])
        reason = check_command(cmd, payload_cwd=str(repo))
        assert reason is not None
        assert "annonce 4" in reason and "1 reellement" in reason

    def test_cd_explicite_prioritaire_sur_payload_cwd(self, tmp_path):
        repo = _init_repo(tmp_path)
        _commit_baseline(repo)
        (repo / "tests" / "test_example.py").write_text(
            "def test_a():\n    pass\n\n\ndef test_b():\n    pass\n", encoding="utf-8"
        )
        cmd = _commit_command(repo, "2 nouveaux tests (test_example.py).", ["tests/test_example.py"])
        assert check_command(cmd, payload_cwd="/nonexistent/path/xyz") is None
