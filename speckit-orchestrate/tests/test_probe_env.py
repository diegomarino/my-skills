"""Tests for scripts/probe_env.py and the e2e example. Run: python3 -m unittest discover -s tests -v"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL / "scripts"))

import probe_env  # noqa: E402


def git(repo: Path, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class ProbeTests(unittest.TestCase):
    def test_git_repository_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            git(repo, "init", "-q", "-b", "main")
            (repo / "a.txt").write_text("a\n")
            git(repo, "add", "-A")
            git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "init")
            git(repo, "worktree", "add", "-q", "-b", "wp/x", str(Path(tmp) / "wt-x"))
            git(repo, "remote", "add", "origin", "https://user:secret-token@example.com/org/repo.git")
            before = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout
            report = probe_env.probe(repo)
            g = report["git"]
            self.assertEqual(g["branch"], "main")
            self.assertTrue(g["clean"])
            self.assertTrue(g["worktree_supported"])
            self.assertIn("wp/x", [w.get("branch") for w in g["worktrees"]])
            self.assertNotIn("secret-token", str(g["remotes"]))
            self.assertIn("***@", g["remotes"][0]["url"])
            after = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout
            self.assertEqual(before, after, "the probe must not change the repository")

    def test_outside_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = probe_env.probe(Path(tmp))
            self.assertIsNone(report["git"])
            self.assertTrue(any("not inside a git repository" in n for n in report["notes"]))
            self.assertTrue(any("presence on PATH only" in n for n in report["notes"]))


class EndToEndExample(unittest.TestCase):
    def test_local_example_reaches_a_passing_gate(self):
        out = subprocess.run([sys.executable, str(SKILL / "examples" / "e2e-local" / "run_e2e.py")], capture_output=True, text=True, timeout=300)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("gate: PASS", out.stdout)
        self.assertIn("UNCERTAIN_OPERATION", out.stdout)


if __name__ == "__main__":
    unittest.main()
