#!/usr/bin/env python3
"""Read-only probe of the local environment for orchestration setup (Python 3.9+, stdlib only).

Reports git facts, worktree support, remotes, CLIs present on PATH, Spec Kit files, and an existing
run profile. It never authenticates, calls a network service, or changes anything. A CLI found on
PATH is reported as present, never as working or authenticated.

Usage: probe_env.py [--repo DIR] [--feature-dir DIR] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS = ("git", "claude", "codex", "gemini", "opencode", "gh", "gh-delta", "glab", "linear", "jira", "python3", "node", "specify", "uv")
HARNESS_ENV = {"CLAUDECODE": "claude-code", "CODEX_SANDBOX": "codex", "CODEX_HOME": "codex", "GEMINI_CLI": "gemini-cli"}


def git(args: list, cwd: Path) -> "tuple[int, str]":
    try:
        out = subprocess.run(["git", "--no-optional-locks", *args], cwd=str(cwd), capture_output=True, text=True, check=False, timeout=20)
        return out.returncode, out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def redact(url: str) -> str:
    """Remove credentials embedded in remote URLs."""
    return re.sub(r"(://)[^/@\s]+@", r"\1***@", url)


def probe(repo: Path, feature_dir: "Path | None" = None) -> dict:
    report = {"cwd": str(repo.resolve()), "git": None, "tools": {}, "harness_hints": [], "speckit": {}, "profile": None, "notes": []}
    for name in TOOLS:
        report["tools"][name] = shutil.which(name)
    report["harness_hints"] = sorted({label for key, label in HARNESS_ENV.items() if os.environ.get(key)})

    code, root = git(["rev-parse", "--show-toplevel"], repo)
    if code == 0 and root:
        root_path = Path(root)
        _, branch = git(["branch", "--show-current"], root_path)
        _, head = git(["rev-parse", "HEAD"], root_path)
        _, porcelain = git(["status", "--porcelain"], root_path)
        _, origin_head = git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], root_path)
        wt_code, wt_out = git(["worktree", "list", "--porcelain"], root_path)
        worktrees, current = [], None
        for line in wt_out.splitlines():
            if line.startswith("worktree "):
                current = {"path": line[9:]}
                worktrees.append(current)
            elif current is not None and line.startswith("branch "):
                current["branch"] = line[7:].replace("refs/heads/", "")
            elif current is not None and line.split(" ")[0] in ("detached", "locked", "prunable"):
                current[line.split(" ")[0]] = True
        _, remotes_out = git(["remote", "-v"], root_path)
        remotes = sorted({(r.split()[0], redact(r.split()[1])) for r in remotes_out.splitlines() if len(r.split()) >= 2})
        report["git"] = {
            "root": root,
            "branch": branch or None,
            "head": head or None,
            "clean": porcelain == "",
            "changed_paths": len(porcelain.splitlines()) if porcelain else 0,
            "default_branch_guess": origin_head.split("/", 1)[1] if origin_head and "/" in origin_head else None,
            "worktree_supported": wt_code == 0,
            "worktrees": worktrees,
            "remotes": [{"name": n, "url": u} for n, u in remotes],
        }
        base = root_path
    else:
        report["notes"].append("not inside a git repository: worktree isolation and git delivery are unavailable")
        base = repo
    specify = base / ".specify"
    report["speckit"] = {
        "specify_dir": specify.is_dir(),
        "check_prerequisites": (specify / "scripts" / "bash" / "check-prerequisites.sh").is_file(),
        "feature_json": (specify / "feature.json").is_file(),
    }
    if feature_dir:
        fd = (repo / feature_dir).resolve() if not feature_dir.is_absolute() else feature_dir
        report["feature"] = {
            "dir": str(fd),
            "tasks_packages": (fd / "tasks-packages.md").is_file(),
            "profile": (fd / "orchestration.md").is_file(),
            "ledger": (fd / "orchestration-ledger.jsonl").is_file(),
        }
    report["notes"].append("tools are reported by presence on PATH only; verify authentication and behavior with a dry operation before relying on them")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--feature-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = probe(Path(args.repo), Path(args.feature_dir) if args.feature_dir else None)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    g = report["git"]
    lines = []
    if g:
        lines.append(f"git: {g['root']} on {g['branch']} ({'clean' if g['clean'] else str(g['changed_paths']) + ' changed paths'})")
        lines.append(f"worktrees: {'supported' if g['worktree_supported'] else 'unsupported'}; {len(g['worktrees'])} listed")
        lines += [f"  {w['path']} [{w.get('branch', 'detached')}]" for w in g["worktrees"]]
        lines.append("remotes: " + (", ".join(f"{r['name']}={r['url']}" for r in g["remotes"]) or "none"))
    lines.append("tools on PATH: " + (", ".join(k for k, v in report["tools"].items() if v) or "none"))
    lines.append("harness hints: " + (", ".join(report["harness_hints"]) or "none detected"))
    if "feature" in report:
        f = report["feature"]
        lines.append(f"feature: {f['dir']} tasks-packages={f['tasks_packages']} profile={f['profile']} ledger={f['ledger']}")
    lines += [f"note: {n}" for n in report["notes"]]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
