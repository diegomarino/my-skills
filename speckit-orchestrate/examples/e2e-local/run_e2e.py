#!/usr/bin/env python3
"""End-to-end local example: orchestrate the sample feature in a temporary git repository.

The coordinator steps follow SKILL.md. worker.sh is the executor and makes real commits in real
worktrees; every piece of evidence recorded is actual local git output. Nothing outside the
temporary directory is touched.

Usage: python3 run_e2e.py [--keep]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parents[1]
LEDGER = SKILL / "scripts" / "ledger.py"
WORKER = HERE / "worker.sh"
VALIDATOR = SKILL.parent / "speckit-package-tasks" / "scripts" / "work_packages.py"  # optional sibling
FEATURE = Path("specs/001-account-login")
sys.path.insert(0, str(SKILL / "scripts"))
import ledger as ledger_module  # noqa: E402  (same skill folder)


class Coordinator:
    def __init__(self, repo: Path):
        self.repo = repo
        self.feature = repo / FEATURE
        self.plan = ledger_module.parse_plan(self.feature / "tasks-packages.md")
        self.refusals = []

    def git(self, *args, check=True) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=check)

    def ledger(self, *args, expect_refusal: "str | None" = None) -> dict:
        out = subprocess.run([sys.executable, str(LEDGER), "--json", "--feature-dir", str(self.feature), *args],
                             capture_output=True, text=True)
        if expect_refusal:
            data = json.loads(out.stderr or "{}")
            assert out.returncode != 0 and data.get("code") == expect_refusal, f"expected {expect_refusal}, got {out.returncode} {out.stdout} {out.stderr}"
            self.refusals.append(expect_refusal)
            print(f"  refused as expected: {expect_refusal}: {data['message']}")
            return data
        if out.returncode not in (0,) and args[0] != "gate":
            raise SystemExit(f"ledger {' '.join(args)} failed: {out.stderr}")
        return json.loads(out.stdout)

    def worktree(self, pid: str) -> Path:
        return self.repo / ".worktrees" / pid

    def run_worker(self, pid: str, op: str, purpose: str) -> str:
        paths = self.plan["packages"][pid]["paths"]
        out = subprocess.run(["bash", str(WORKER), str(self.repo), str(self.worktree(pid)), f"wp/{pid}", "main", op, purpose, *paths],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()

    def head(self, pid: str) -> str:
        return subprocess.run(["git", "-C", str(self.worktree(pid)), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    # Assign one operation; the first implementation simulates a lost acceptance receipt.
    def assign(self, item: dict, lose_receipt: bool) -> "tuple[str, str]":
        pid, purpose = item["package"], item["purpose"]
        op = self.ledger("request", pid, purpose)["op"]
        print(f"  request {op}" + (f" pinned to {item['head'][:10]}" if item.get("head") else ""))
        if purpose == "review":
            assignment = f"review-{op.replace(':', '-')}"
            self.ledger("accepted", op, "--assignment", assignment, "--via", "assign", "--evidence", f"scripted reviewer started as {assignment}")
            return op, assignment
        existed = self.worktree(pid).exists()
        run_id = self.run_worker(pid, op, purpose)
        if lose_receipt:
            print(f"  (coordinator lost the receipt for {op}; acceptance is now uncertain)")
            self.ledger("request", pid, purpose, expect_refusal="UNCERTAIN_OPERATION")
            found = self.git("log", "--format=%H", "--grep", f"Orchestration-Op: {op}", f"wp/{pid}").stdout.strip()
            assert found, "find must locate the assignment before it is recorded"
            self.ledger("accepted", op, "--assignment", run_id, "--via", "find", "--evidence", f"git log --grep found commit {found} carrying {op}")
            print(f"  reconciled {op} through find: commit {found[:10]}")
        else:
            self.ledger("accepted", op, "--assignment", run_id, "--via", "assign", "--evidence", f"worker.sh exit 0, run id {run_id}")
        if not existed:
            listing = self.git("worktree", "list", "--porcelain").stdout
            assert str(self.worktree(pid)) in listing
            self.ledger("resource", str(self.worktree(pid)), "--action", "created", "--owner", "coordinator", "--package", pid,
                        "--via", "assign", "--evidence", "listed by git worktree list")
        return op, run_id

    def observe(self, item: dict, op: str, assignment: str, review_round: dict):
        pid, purpose = item["package"], item["purpose"]
        if purpose == "review":
            head = item["head"]
            stat = self.git("diff", "--stat", f"main...{head}").stdout.strip().splitlines()[-1]
            # The scripted reviewer asks for one change on F001-P02's first review to exercise the fix loop.
            verdict = "changes-requested" if pid == "F001-P02" and review_round.get(pid, 0) == 0 else "pass"
            review_round[pid] = review_round.get(pid, 0) + 1
            self.ledger("reviewed", op, "--head", head, "--verdict", verdict, "--via", "observe",
                        "--evidence", f"scripted reviewer read diff ({stat}) and returned {verdict}")
            print(f"  reviewed {pid} at {head[:10]}: {verdict}")
            return
        head = self.head(pid)
        self.ledger("completed", op, "--outcome", "succeeded", "--head", head, "--via", "observe", "--evidence", f"git rev-parse HEAD = {head}")
        print(f"  completed {op} at {head[:10]}")

    def deliver(self, item: dict):
        pid, head = item["package"], item["head"]
        if "WRONG_OPERATION" not in self.refusals:  # a merge receipt is not delivery evidence
            self.ledger("delivered", pid, "--head", head, "--target", "main", "--via", "deliver", "--evidence", "merge receipt",
                        expect_refusal="WRONG_OPERATION")
        merge = self.git("-c", "user.name=coordinator", "-c", "user.email=coordinator@example.invalid",
                         "merge", "--no-ff", "-q", f"wp/{pid}", "-m", f"Deliver {pid}")
        merged = self.git("rev-parse", "HEAD").stdout.strip()
        ancestor = self.git("merge-base", "--is-ancestor", head, "main", check=False)
        assert merge.returncode == 0 and ancestor.returncode == 0
        self.ledger("delivered", pid, "--head", head, "--target", "main", "--via", "observe_delivery",
                    "--evidence", f"git merge-base --is-ancestor {head} main exit 0 (merge commit {merged})")
        wt = str(self.worktree(pid))
        self.git("worktree", "remove", wt)
        self.git("branch", "-d", f"wp/{pid}")
        assert wt not in self.git("worktree", "list", "--porcelain").stdout
        self.ledger("resource", wt, "--action", "released", "--via", "release", "--evidence", "git worktree remove exit 0; absent from git worktree list")
        print(f"  delivered {pid} ({head[:10]}) in merge {merged[:10]}; worktree released")


def setup(tmp: Path) -> Path:
    repo = tmp / "repo"
    shutil.copytree(HERE / "fixture", repo)
    shutil.copy(HERE / "orchestration.md", repo / FEATURE / "orchestration.md")
    (repo / ".gitignore").write_text(".worktrees/\nspecs/*/orchestration-ledger.jsonl\n")
    for args in (["init", "-q", "-b", "main"], ["add", "-A"],
                 ["-c", "user.name=setup", "-c", "user.email=setup@example.invalid", "commit", "-q", "-m", "Approved feature plan"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True)
    return repo


def main() -> int:
    keep = "--keep" in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="speckit-orchestrate-e2e-"))
    try:
        repo = setup(tmp)
        c = Coordinator(repo)
        print(f"repository: {repo}")
        if VALIDATOR.is_file():
            out = subprocess.run([sys.executable, str(VALIDATOR), "validate", str(repo / FEATURE / "tasks-packages.md")], capture_output=True, text=True)
            print(f"package validator (sibling skill): {out.stdout.strip().splitlines()[-1]}")
            assert out.returncode == 0
        else:
            print("package validator not installed next to this skill; relying on ledger init checks")
        assert c.ledger("check-profile", str(repo / FEATURE / "orchestration.md"))["ok"]
        c.ledger("init")
        c.ledger("request", "F001-P02", "implement", expect_refusal="NOT_ELIGIBLE")
        assert not c.ledger("gate")["ok"]

        review_round, first = {}, True
        for round_number in range(1, 30):
            nxt = c.ledger("next")
            if not nxt["start"] and not nxt["deliver"]:
                break
            print(f"round {round_number}: start={[i['package'] + ':' + i['purpose'] for i in nxt['start']]} "
                  f"deliver={[i['package'] for i in nxt['deliver']]}")
            for wait in nxt["waiting"]:
                print(f"  waiting {wait['package']}: {wait['reason']}")
            assigned = []
            for item in nxt["start"]:  # assign everything selected, then observe: concurrent from the ledger's view
                op, assignment = c.assign(item, lose_receipt=first and item["purpose"] == "implement")
                first = False
                assigned.append((item, op, assignment))
            if len(assigned) > 1:
                print(f"  {len(assigned)} operations open at once: {[op for _, op, _ in assigned]}")
            for item, op, assignment in assigned:
                c.observe(item, op, assignment, review_round)
            for item in nxt["deliver"]:
                c.deliver(item)

        gate = c.ledger("gate")
        status = c.ledger("status")
        print("final states:", {row["package"]: row["state"] for row in status["packages"]})
        print("gate:", "PASS" if gate["ok"] else f"FAIL {gate['blockers']}")
        print("refusals exercised:", ", ".join(sorted(set(c.refusals))))
        lines = (repo / FEATURE / "orchestration-ledger.jsonl").read_text().count("\n")
        print(f"ledger records: {lines}")
        assert gate["ok"]
        return 0
    finally:
        if keep:
            print(f"kept {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
