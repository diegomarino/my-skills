"""Tests for scripts/ledger.py. Run: python3 -m unittest discover -s tests -v"""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
FIXTURE = SKILL / "examples" / "e2e-local" / "fixture"
E2E_PROFILE = SKILL / "examples" / "e2e-local" / "orchestration.md"
PROFILES = SKILL / "examples" / "profiles"
FEATURE = Path("specs/001-account-login")
sys.path.insert(0, str(SKILL / "scripts"))

import ledger  # noqa: E402

PROOF = ["--evidence", "observed"]


class Run:
    """A temporary repository holding the sample plan and a run profile."""

    def __init__(self, profile: Path = E2E_PROFILE):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        shutil.copytree(FIXTURE, self.root)
        subprocess.run(["git", "init", "-q"], cwd=str(self.root), check=True)
        self.feature = self.root / FEATURE
        shutil.copy(profile, self.feature / "orchestration.md")

    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ledger.main(["--json", "--feature-dir", str(self.feature), *[str(a) for a in args]])
        text = out.getvalue() or err.getvalue()
        return code, json.loads(text) if text.strip() else {}

    def ok(self, *args):
        code, data = self.call(*args)
        if code != 0:
            raise AssertionError(f"{args} failed: {data}")
        return data

    def edit(self, name: str, old: str, new: str):
        path = self.feature / name
        text = path.read_text()
        assert old in text, old
        path.write_text(text.replace(old, new, 1))

    # Shortcuts that walk one package through the lifecycle with local fake evidence.
    def implement(self, pid: str, head: str, purpose: str = "implement") -> str:
        op = self.ok("request", pid, purpose)["op"]
        self.ok("accepted", op, "--assignment", f"worker-{op}", "--via", "assign", *PROOF)
        self.ok("completed", op, "--outcome", "succeeded", "--head", head, "--via", "observe", *PROOF)
        return op

    def review(self, pid: str, head: str, verdict: str = "pass") -> str:
        op = self.ok("request", pid, "review")["op"]
        self.ok("accepted", op, "--assignment", f"reviewer-{op}", "--via", "assign", *PROOF)
        self.ok("reviewed", op, "--head", head, "--verdict", verdict, "--via", "observe", *PROOF)
        return op

    def deliver(self, pid: str, head: str):
        self.ok("delivered", pid, "--head", head, "--target", "main", "--via", "observe_delivery", *PROOF)

    def complete(self, pid: str, head: str):
        self.implement(pid, head)
        self.review(pid, head)
        self.deliver(pid, head)

    def close(self):
        self.tmp.cleanup()


class ProfileTests(unittest.TestCase):
    def check(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orchestration.md"
            path.write_text(text)
            return ledger.parse_profile(path)

    def test_shipped_profiles_pass(self):
        for path in list(PROFILES.glob("*.md")) + [E2E_PROFILE]:
            with self.subTest(profile=path.name):
                self.assertEqual(ledger.parse_profile(path)["errors"], [])

    def test_meaningful_failures(self):
        base = E2E_PROFILE.read_text()
        cases = {
            "undeclared operation": (base.replace("- find: supported", "- lookup: supported"), "executor.find: not declared"),
            "required op unsupported": (base.replace("- assign: supported — evidence: worker.sh exit 0 and its printed run id", "- assign: unsupported"), "executor.assign: required"),
            "parallel without isolation": (base.replace('isolation: "worktree"', 'isolation: "checkout"'), "max_parallel > 1 needs per-worker isolation"),
            "agent merge without deliver": (base.replace("- deliver: supported", "- deliver: human"), "merge_by agent needs delivery.deliver: supported"),
            "no authorization boundary": (base.replace('authorized: "assign, review, merge, release"\n', ""), "missing setting: authorized"),
            "unknown authorized token": (base.replace('authorized: "assign, review, merge, release"', 'authorized: "assign, deploy"'), "unknown token"),
            "agent merge without merge token": (base.replace('authorized: "assign, review, merge, release"', 'authorized: "assign, review"'), "merge token"),
            "evidence missing": (base.replace("- observe: supported — evidence: `git -C <worktree> rev-parse HEAD`", "- observe: supported"), "must say what evidence"),
            "tracker without section": (base.replace('tracker: "none"', 'tracker: "linear"'), "missing section: ## Tracker"),
        }
        for name, (text, expected) in cases.items():
            with self.subTest(case=name):
                errors = self.check(text)["errors"]
                self.assertTrue(any(expected in e for e in errors), errors)
        empty = (PROFILES / "codex-cli-github-pr.md").read_text().replace('authorized: "assign, review, push"', 'authorized: ""')
        self.assertEqual(self.check(empty)["errors"], [])


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.run_ = Run()
        self.run_.ok("init")

    def tearDown(self):
        self.run_.close()

    def refused(self, code, *args):
        status, data = self.run_.call(*args)
        self.assertNotEqual(status, 0, f"{args} unexpectedly succeeded")
        self.assertEqual(data.get("code"), code, data)
        return data

    def states(self):
        return {row["package"]: row["state"] for row in self.run_.ok("status")["packages"]}

    def test_init_refuses_existing_ledger(self):
        self.refused("LEDGER_EXISTS", "init")

    def test_dependencies_gate_selection(self):
        nxt = self.run_.ok("next")
        self.assertEqual([(i["package"], i["purpose"]) for i in nxt["start"]], [("F001-P01", "implement")])
        self.refused("NOT_ELIGIBLE", "request", "F001-P02", "implement")

    def test_duplicate_execution_guards(self):
        op = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.refused("UNCERTAIN_OPERATION", "request", "F001-P01", "implement")
        self.run_.ok("accepted", op, "--assignment", "w1", "--via", "assign", *PROOF)
        self.refused("DUPLICATE_EXECUTION", "request", "F001-P01", "implement")
        self.refused("OPERATION_STATE", "absent", op, "--via", "find", *PROOF)

    def test_absent_allows_a_clean_retry(self):
        op = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.run_.ok("absent", op, "--via", "find", "--evidence", "no commit carries the key")
        second = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.assertEqual(second, "F001-P01:implement:2")

    def test_assignment_reference_is_unique(self):
        op = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.run_.ok("accepted", op, "--assignment", "w1", "--via", "assign", *PROOF)
        self.run_.ok("completed", op, "--outcome", "failed", "--via", "observe", *PROOF)
        retry = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.refused("DUPLICATE_ASSIGNMENT", "accepted", retry, "--assignment", "w1", "--via", "assign", *PROOF)

    def test_completion_requires_acceptance_and_head(self):
        op = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.refused("OPERATION_STATE", "completed", op, "--outcome", "succeeded", "--head", "a1", "--via", "observe", *PROOF)
        self.run_.ok("accepted", op, "--assignment", "w1", "--via", "assign", *PROOF)
        self.refused("HEAD_REQUIRED", "completed", op, "--outcome", "succeeded", "--via", "observe", *PROOF)
        self.assertEqual(self.states()["F001-P01"], "implement-assigned")

    def test_evidence_and_capability_rules(self):
        op = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.refused("EVIDENCE_REQUIRED", "accepted", op, "--assignment", "w1", "--via", "assign", "--evidence", " ")
        self.refused("WRONG_OPERATION", "accepted", op, "--assignment", "w1", "--via", "observe", *PROOF)
        self.refused("WRONG_OPERATION", "absent", op, "--via", "lookup", *PROOF)

    def test_review_must_be_independent(self):
        self.run_.implement("F001-P01", "a1")
        op = self.run_.ok("request", "F001-P01", "review")["op"]
        self.refused("REVIEW_NOT_INDEPENDENT", "accepted", op, "--assignment", "worker-F001-P01:implement:1", "--via", "assign", *PROOF)

    def test_fresh_review_after_the_implementation_changes(self):
        self.run_.implement("F001-P01", "a1")
        self.run_.review("F001-P01", "a1", verdict="changes-requested")
        self.assertEqual(self.states()["F001-P01"], "changes-requested")
        self.run_.implement("F001-P01", "b2", purpose="fix")
        self.assertEqual(self.states()["F001-P01"], "needs-review")
        op = self.run_.ok("request", "F001-P01", "review")["op"]
        self.run_.ok("accepted", op, "--assignment", "reviewer-2", "--via", "assign", *PROOF)
        self.refused("STALE_REVIEW", "reviewed", op, "--head", "a1", "--verdict", "pass", "--via", "observe", *PROOF)
        self.run_.ok("reviewed", op, "--head", "b2", "--verdict", "pass", "--via", "observe", *PROOF)
        self.assertEqual(self.states()["F001-P01"], "ready-to-deliver")

    def test_delivery_needs_observation_in_expected_target(self):
        self.run_.implement("F001-P01", "a1")
        self.refused("WRONG_OPERATION", "delivered", "F001-P01", "--head", "a1", "--target", "main", "--via", "deliver", *PROOF)
        self.refused("WRONG_TARGET", "delivered", "F001-P01", "--head", "a1", "--target", "develop", "--via", "observe_delivery", *PROOF)
        self.refused("EVIDENCE_REQUIRED", "delivered", "F001-P01", "--head", "a1", "--target", "main", "--via", "observe_delivery", "--evidence", "")
        self.assertNotEqual(self.states()["F001-P01"], "delivered")

    def test_unreviewed_delivery_is_recorded_as_a_gap(self):
        self.run_.implement("F001-P01", "a1")
        self.refused("REVIEW_REQUIRED", "delivered", "F001-P01", "--head", "a1", "--target", "main", "--via", "observe_delivery", *PROOF)
        result = self.run_.ok("delivered", "F001-P01", "--head", "a1", "--target", "main", "--via", "observe_delivery",
                              "--attested-by", "diego", "--evidence", "merged on the forge")
        self.assertIn("no passing review", result["warning"])
        status = self.run_.ok("status")
        self.assertTrue(next(r for r in status["packages"] if r["package"] == "F001-P01")["review_gap"])

    def test_gate_fails_until_everything_is_verified(self):
        gate = self.run_.ok("next")  # noqa: F841 - selection does not change state
        code, data = self.run_.call("gate")
        self.assertEqual(code, 1)
        self.assertTrue(any("not delivered" in b for b in data["blockers"]))
        self.run_.ok("resource", "wt-P01", "--action", "created", "--owner", "coordinator", "--package", "F001-P01", "--via", "assign", *PROOF)
        for pid, head in (("F001-P01", "a1"), ("F001-P02", "b1"), ("F001-P03", "c1"), ("F001-P04", "d1")):
            self.run_.complete(pid, head)
        code, data = self.run_.call("gate")
        self.assertEqual(code, 1)
        self.assertEqual(data["blockers"], ["resource wt-P01 is neither released nor retained"])
        self.run_.ok("resource", "wt-P01", "--action", "released", "--via", "release", *PROOF)
        code, data = self.run_.call("gate")
        self.assertEqual(code, 0, data)

    def test_resource_ownership_and_use(self):
        self.run_.ok("resource", "user-wt", "--action", "created", "--owner", "user", "--via", "observe", *PROOF)
        self.refused("OWNERSHIP_UNPROVEN", "resource", "user-wt", "--action", "released", "--via", "release", *PROOF)
        self.run_.ok("resource", "user-wt", "--action", "retained", "--evidence", "belongs to the user")
        op = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.run_.ok("accepted", op, "--assignment", "w1", "--via", "assign", *PROOF)
        self.run_.ok("resource", "wt-P01", "--action", "created", "--owner", "coordinator", "--package", "F001-P01", "--via", "assign", *PROOF)
        self.refused("RESOURCE_IN_USE", "resource", "wt-P01", "--action", "released", "--via", "release", *PROOF)

    def test_plan_drift_stops_new_requests(self):
        op = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.run_.edit("tasks-packages.md", "# Work packages: Account login", "# Work packages: Account login (edited)")
        self.refused("UNCERTAIN_OPERATIONS", "init", "--rebind")
        self.run_.ok("accepted", op, "--assignment", "w1", "--via", "assign", *PROOF)  # facts are still recorded
        self.refused("PLAN_DRIFT", "request", "F001-P02", "implement")
        code, data = self.run_.call("gate")
        self.assertTrue(any("tasks-packages.md changed" in b for b in data["blockers"]))
        self.run_.ok("init", "--rebind")
        self.assertEqual(self.run_.ok("status")["drift"], [])

    def test_ledger_corruption_is_refused(self):
        self.run_.ok("request", "F001-P01", "implement")
        path = self.run_.feature / ledger.LEDGER
        good = path.read_text()
        path.write_text(good + '{"seq": 3, "type": "absent"')
        self.refused("LEDGER_CORRUPT", "status")
        lines = good.splitlines(keepends=True)
        path.write_text(lines[0] + lines[1].replace('"seq": 2', '"seq": 5'))
        self.refused("LEDGER_CORRUPT", "status")

    def test_shared_paths_serialize_but_independent_work_runs_in_parallel(self):
        self.run_.complete("F001-P01", "a1")
        start = [i["package"] for i in self.run_.ok("next")["start"]]
        self.assertEqual(start, ["F001-P02"], "P03 shares src/accounts/cli.py with P02")
        # Remove the shared path: the stories become genuinely parallel.
        self.run_.close()
        self.run_ = Run()
        self.run_.edit("tasks-packages.md", "- `src/accounts/profile.py`\n- `src/accounts/cli.py`", "- `src/accounts/profile.py`")
        self.run_.edit("tasks-packages.md",
                       "- Owns `src/accounts/profile.py` and `tests/test_profile.py`; adds only the `profile` command to `src/accounts/cli.py`.",
                       "- Owns `src/accounts/profile.py` and `tests/test_profile.py`.")
        self.run_.edit("tasks-packages.md", "- `F001-P02` / `F001-P03`: `src/accounts/cli.py` — both stories add a subcommand to the same CLI module", "- None")
        self.run_.ok("init")
        self.run_.complete("F001-P01", "a1")
        start = [i["package"] for i in self.run_.ok("next")["start"]]
        self.assertEqual(start, ["F001-P02", "F001-P03"])
        for pid in start:
            self.run_.ok("request", pid, "implement")
        self.assertEqual(len(self.run_.ok("status")["open_operations"]), 2)

    def test_bound_tasks_path_is_repo_relative(self):
        event = json.loads((self.run_.feature / ledger.LEDGER).read_text().splitlines()[0])
        self.assertEqual(event["tasks_path"], "specs/001-account-login/tasks.md")
        self.assertIs(event["plan_validated"], True)
        self.assertEqual(self.run_.ok("status")["drift"], [])
        absolute = str((self.run_.root / event["tasks_path"]).resolve())
        event["tasks_path"] = absolute
        path = self.run_.feature / ledger.LEDGER
        lines = path.read_text().splitlines()
        lines[0] = json.dumps(event, sort_keys=True)
        path.write_text("\n".join(lines) + "\n")
        self.assertEqual(self.run_.ok("status")["drift"], [], "an absolute stored path is hashed as itself")

    def test_ready_no_after_a_successful_head_is_not_reviewable(self):
        self.run_.implement("F001-P01", "a1")
        self.assertEqual(self.states()["F001-P01"], "needs-review")
        self.run_.edit("tasks-packages.md", "**Ready**: yes", "**Ready**: no — hashing algorithm undecided")
        self.run_.ok("init", "--rebind")
        self.assertEqual(self.states()["F001-P01"], "not-ready")
        self.refused("NOT_ELIGIBLE", "request", "F001-P01", "review")

    def test_rebind_refuses_dropping_a_blocker_and_accepts_adding_one(self):
        for pid, head in (("F001-P01", "a1"), ("F001-P02", "b1"), ("F001-P03", "c1")):
            self.run_.complete(pid, head)
        self.run_.implement("F001-P04", "d1")
        blocked = "**Blocked by**:\n- `F001-P02`\n- `F001-P03`\n\n**Objective**: Users can find both commands documented"
        self.run_.edit("tasks-packages.md", blocked, blocked.replace("- `F001-P03`\n", ""))
        self.refused("REBIND_LOOSENS", "init", "--rebind")
        self.run_.edit("tasks-packages.md",
                       "**Blocked by**:\n- `F001-P02`\n\n**Objective**: Users can find both commands documented",
                       "**Blocked by**:\n- `F001-P01`\n- `F001-P02`\n- `F001-P03`\n\n**Objective**: Users can find both commands documented")
        self.run_.ok("init", "--rebind")
        self.run_.edit("tasks-packages.md", "- `pyproject.toml`\n", "")
        self.refused("REBIND_LOOSENS", "init", "--rebind")
        self.run_.ok("init", "--rebind", "--attested-by", "diego", "--evidence", "pyproject.toml left the package on purpose")

    def test_halt_stops_requests_and_the_gate_until_resume(self):
        self.run_.ok("halt", "--reason", "base branch is red")
        self.refused("LINE_STOPPED", "request", "F001-P01", "implement")
        code, data = self.run_.call("gate")
        self.assertEqual(code, 1)
        self.assertTrue(any("halt" in blocker for blocker in data["blockers"]), data["blockers"])
        nxt = self.run_.ok("next")
        self.assertTrue(nxt["halted"])
        self.assertIn("base branch is red", nxt["halt_reason"])
        status = self.run_.ok("status")
        self.assertTrue(status["halted"])
        self.assertIn("HALTED:", ledger.render_status(status))
        self.run_.ok("resume", "--attested-by", "diego", "--evidence", "base is green again")
        self.assertFalse(self.run_.ok("next")["halted"])
        self.run_.ok("request", "F001-P01", "implement")

    def test_max_parallel_counts_implement_not_review(self):
        self.run_.close()
        self.run_ = Run()
        self.run_.edit("tasks-packages.md", "- `src/accounts/profile.py`\n- `src/accounts/cli.py`", "- `src/accounts/profile.py`")
        self.run_.edit("tasks-packages.md",
                       "- Owns `src/accounts/profile.py` and `tests/test_profile.py`; adds only the `profile` command to `src/accounts/cli.py`.",
                       "- Owns `src/accounts/profile.py` and `tests/test_profile.py`.")
        self.run_.edit("tasks-packages.md",
                       "- `F001-P02` / `F001-P03`: `src/accounts/cli.py` — both stories add a subcommand to the same CLI module",
                       "- None")
        self.run_.edit("orchestration.md", 'max_parallel: "2"', 'max_parallel: "1"')
        self.run_.ok("init")
        self.run_.complete("F001-P01", "a1")
        op = self.run_.ok("request", "F001-P02", "implement")["op"]
        refused = self.refused("NOT_ELIGIBLE", "request", "F001-P03", "implement")
        self.assertIn("max_parallel", refused["message"])
        self.run_.ok("absent", op, "--via", "find", *PROOF)
        self.run_.implement("F001-P03", "c1")
        self.run_.ok("request", "F001-P02", "implement")
        self.run_.ok("request", "F001-P03", "review")


class HardeningTests(unittest.TestCase):
    """Regression tests for guard bypasses found in review."""

    def setUp(self):
        self.run_ = Run()

    def tearDown(self):
        self.run_.close()

    def refused(self, code, *args):
        status, data = self.run_.call(*args)
        self.assertNotEqual(status, 0, f"{args} unexpectedly succeeded")
        self.assertEqual(data.get("code"), code, data)

    def state(self, pid):
        return {r["package"]: r["state"] for r in self.run_.ok("status")["packages"]}[pid]

    def test_blank_assignment_is_refused(self):
        self.run_.ok("init")
        op = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.refused("ASSIGNMENT_REQUIRED", "accepted", op, "--assignment", "  ", "--via", "assign", *PROOF)

    def test_editing_the_profile_does_not_grant_capabilities(self):
        run = Run(PROFILES / "claude-code-subagents-local-git.md")
        try:
            run.ok("init")
            op = run.ok("request", "F001-P01", "implement")["op"]
            run.edit("orchestration.md", "- find: unsupported", "- find: supported — evidence: invented lookup")
            code, data = run.call("absent", op, "--via", "find", *PROOF)
            self.assertEqual(data["code"], "UNSUPPORTED_CAPABILITY")
        finally:
            run.close()

    def test_plan_with_unquoted_blocker_or_no_source_is_refused(self):
        self.run_.edit("tasks-packages.md", "**Blocked by**:\n- `F001-P01`\n\n**Objective**: A user can log in",
                       "**Blocked by**:\n- F001-P01\n\n**Objective**: A user can log in")
        self.refused("PLAN_INVALID", "init")
        other = Run()
        try:
            other.edit("tasks-packages.md", 'source: "specs/001-account-login/tasks.md"\n', "")
            code, data = other.call("init")
            self.assertEqual(data["code"], "PLAN_INVALID")
        finally:
            other.close()

    def test_readiness_wins_over_a_past_failure(self):
        self.run_.ok("init")
        op = self.run_.ok("request", "F001-P01", "implement")["op"]
        self.run_.ok("accepted", op, "--assignment", "w1", "--via", "assign", *PROOF)
        self.run_.ok("completed", op, "--outcome", "failed", "--via", "observe", *PROOF)
        self.assertEqual(self.state("F001-P01"), "failed")
        self.run_.edit("tasks-packages.md", "**Ready**: yes", "**Ready**: no — hashing algorithm undecided")
        self.run_.ok("init", "--rebind")
        self.assertEqual(self.state("F001-P01"), "not-ready")
        self.refused("NOT_ELIGIBLE", "request", "F001-P01", "implement")

    def test_rebind_refuses_moving_history_to_other_tasks(self):
        self.run_.ok("init")
        self.run_.implement("F001-P01", "a1")
        self.run_.edit("tasks-packages.md", "- `T005` Add the password hashing helper in `src/accounts/hashing.py` (depends on T004)\n", "")
        self.refused("REBIND_MOVES_HISTORY", "init", "--rebind")

    def test_resource_generations_and_release_timing(self):
        self.run_.ok("init")
        self.run_.ok("resource", "wt", "--action", "created", "--owner", "coordinator", "--package", "F001-P01", "--via", "assign", *PROOF)
        self.run_.implement("F001-P01", "a1")
        self.refused("RESOURCE_IN_USE", "resource", "wt", "--action", "released", "--via", "release", *PROOF)
        self.run_.ok("resource", "wt", "--action", "retained", "--evidence", "holds the undelivered change")
        self.run_.review("F001-P01", "a1")
        self.run_.deliver("F001-P01", "a1")
        self.run_.ok("resource", "wt", "--action", "released", "--via", "release", *PROOF)
        self.run_.ok("resource", "wt", "--action", "created", "--owner", "coordinator", "--package", "F001-P02", "--via", "assign", *PROOF)
        self.refused("UNKNOWN_PACKAGE", "resource", "wt2", "--action", "created", "--owner", "coordinator", "--package", "f001-p01", "--via", "assign", *PROOF)
        self.refused("PACKAGE_REQUIRED", "resource", "wt3", "--action", "created", "--owner", "coordinator", "--via", "assign", *PROOF)

    def test_attempt_caps_hand_the_decision_to_the_user(self):
        self.run_.ok("init")
        for n in (1, 2):
            op = self.run_.ok("request", "F001-P01", "implement")["op"]
            self.run_.ok("accepted", op, "--assignment", f"w{n}", "--via", "assign", *PROOF)
            self.run_.ok("completed", op, "--outcome", "failed", "--via", "observe", *PROOF)
        self.refused("ATTEMPT_CAP", "request", "F001-P01", "implement")
        op = self.run_.ok("request", "F001-P01", "implement", "--attested-by", "diego", "--evidence", "retry once on a stronger model")["op"]
        self.assertEqual(op, "F001-P01:implement:3")

    def test_fix_may_resume_the_settled_implementer(self):
        self.run_.ok("init")
        self.run_.implement("F001-P01", "a1")
        self.run_.review("F001-P01", "a1", verdict="changes-requested")
        op = self.run_.ok("request", "F001-P01", "fix")["op"]
        self.run_.ok("accepted", op, "--assignment", "worker-F001-P01:implement:1", "--via", "assign", *PROOF)
        self.run_.ok("completed", op, "--outcome", "succeeded", "--head", "b2", "--via", "observe", *PROOF)
        review = self.run_.ok("request", "F001-P01", "review")["op"]
        self.refused("REVIEW_NOT_INDEPENDENT", "accepted", review, "--assignment", "worker-F001-P01:implement:1", "--via", "assign", *PROOF)

    def test_assignment_cannot_move_to_another_package(self):
        self.run_.ok("init")
        self.run_.complete("F001-P01", "a1")
        op = self.run_.ok("request", "F001-P02", "implement")["op"]
        self.refused("DUPLICATE_ASSIGNMENT", "accepted", op, "--assignment", "worker-F001-P01:implement:1", "--via", "assign", *PROOF)

    def test_missing_or_failing_package_validator(self):
        saved = ledger.VALIDATOR
        try:
            ledger.VALIDATOR = self.run_.root / "missing-validator.py"
            data = self.run_.ok("init")
            self.assertIs(data["plan_validated"], False)
            self.assertTrue(any("package validator is not installed" in warning for warning in data["warnings"]))
            self.assertIs(self.run_.ok("status")["plan_validated"], False)
            self.run_.close()
            self.run_ = Run()
            stub = self.run_.root / "failing-validator.py"
            stub.write_text("import sys\nprint('task coverage is broken')\nsys.exit(1)\n")
            ledger.VALIDATOR = stub
            code, data = self.run_.call("init")
            self.assertEqual(data.get("code"), "PLAN_INVALID", data)
            self.assertIn("task coverage is broken", data.get("message", ""))
            self.assertNotEqual(code, 0)
        finally:
            ledger.VALIDATOR = saved

    def test_check_completion_reads_the_worktree_even_while_halted(self):
        self.run_.ok("init")
        repo = self.run_.root
        git = ["git", "-C", str(repo)]
        (repo / ".gitignore").write_text("specs/*/orchestration-ledger.jsonl\n")
        subprocess.run([*git, "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
        (repo / "README.md").write_text("base\n")
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "base"], check=True)
        subprocess.run([*git, "checkout", "-q", "-b", "wp/F001-P01"], check=True)
        target = repo / "src" / "accounts" / "store.py"
        target.parent.mkdir(parents=True)
        target.write_text("store\n")
        subprocess.run([*git, "add", "-A"], check=True)
        op = "F001-P01:implement:1"
        subprocess.run([*git, "-c", "user.name=w", "-c", "user.email=w@example.invalid", "commit", "-q",
                        "-m", "implement", "-m", f"Orchestration-Op: {op}"], check=True)
        head = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        self.run_.ok("halt", "--reason", "look only")
        self.run_.ok("check-completion", "--package", "F001-P01", "--worktree", str(repo), "--head", head, "--op", op)
        target.write_text("dirty\n")
        self.refused("DIRTY_WORKTREE", "check-completion", "--package", "F001-P01", "--worktree", str(repo), "--head", head, "--op", op)
        subprocess.run([*git, "checkout", "-q", "--", "src/accounts/store.py"], check=True)
        outside = repo / "notes" / "extra.txt"
        outside.parent.mkdir()
        outside.write_text("nope\n")
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "-c", "user.name=w", "-c", "user.email=w@example.invalid", "commit", "-q",
                        "-m", "stray", "-m", f"Orchestration-Op: {op}"], check=True)
        stray = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        self.refused("PATH_OUTSIDE_OWNERSHIP", "check-completion", "--package", "F001-P01", "--worktree", str(repo),
                     "--head", stray, "--op", op)

    def test_malformed_records_are_refused_cleanly(self):
        self.run_.ok("init")
        path = self.run_.feature / ledger.LEDGER
        path.write_text(path.read_text() + "[]\n")
        status, data = self.run_.call("status")
        self.assertEqual((status, data["code"]), (2, "LEDGER_CORRUPT"))
        path.write_bytes(b"\xff\xfe\n")
        status, data = self.run_.call("status")
        self.assertEqual((status, data["code"]), (2, "LEDGER_CORRUPT"))


class ExecutorModelWalkthrough(unittest.TestCase):
    """Different executor models, exercised locally (not against live services)."""

    def test_subagents_without_find_need_a_person(self):
        run = Run(PROFILES / "claude-code-subagents-local-git.md")
        try:
            run.ok("init")
            op = run.ok("request", "F001-P01", "implement")["op"]
            # The Agent call's result was lost: the system cannot say whether the subagent exists.
            code, data = run.call("absent", op, "--via", "find", *PROOF)
            self.assertEqual(data["code"], "UNSUPPORTED_CAPABILITY")
            code, data = run.call("absent", op, "--via", "user", "--evidence", "user: no subagent is running")
            self.assertEqual(data["code"], "ATTESTATION_REQUIRED")
            run.ok("absent", op, "--via", "user", "--attested-by", "diego", "--evidence", "user: no subagent is running")
            self.assertEqual(run.ok("request", "F001-P01", "implement")["op"], "F001-P01:implement:2")
        finally:
            run.close()

    def test_people_and_tracker_need_attestation(self):
        run = Run(PROFILES / "humans-github-issues.md")
        try:
            run.ok("init")
            op = run.ok("request", "F001-P01", "implement")["op"]
            code, data = run.call("accepted", op, "--assignment", "issue-12", "--via", "assign", *PROOF)
            self.assertEqual(data["code"], "ATTESTATION_REQUIRED")
            run.ok("accepted", op, "--assignment", "issue-12", "--via", "assign", "--attested-by", "alice", "--evidence", "issue #12 comment: taking it")
            run.ok("completed", op, "--outcome", "succeeded", "--head", "a1", "--via", "observe", "--attested-by", "alice", *PROOF)
            # release is unsupported for people: a resource can only be retained.
            run.ok("resource", "alice-laptop-branch", "--action", "created", "--owner", "user", "--via", "observe", "--attested-by", "alice", *PROOF)
            code, data = run.call("resource", "alice-laptop-branch", "--action", "released", "--via", "release", *PROOF)
            self.assertEqual(data["code"], "OWNERSHIP_UNPROVEN")
        finally:
            run.close()


if __name__ == "__main__":
    unittest.main()
