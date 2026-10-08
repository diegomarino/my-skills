"""Tests for scripts/work_packages.py. Run: python3 -m unittest discover -s tests -v"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPT = SKILL / "scripts" / "work_packages.py"
SAMPLE = SKILL / "examples" / "sample-feature"
sys.path.insert(0, str(SKILL / "scripts"))

import work_packages as wp  # noqa: E402

FEATURE = Path("specs/001-account-login")


class Workspace:
    """A temporary copy of the sample repository."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        shutil.copytree(SAMPLE, self.root)
        self.feature = self.root / FEATURE
        self.plan = self.feature / "tasks-packages.md"
        self.tasks = self.feature / "tasks.md"

    def edit(self, path: Path, old: str, new: str, count: int = 1):
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise AssertionError(f"fixture text not found: {old!r}")
        path.write_text(text.replace(old, new, count), encoding="utf-8")

    def validate(self, path: "Path | None" = None):
        return wp.validate(path or self.plan, self.root)

    def close(self):
        self.tmp.cleanup()


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def codes(self, result):
        return [d["code"] for d in result["diagnostics"]]

    def assertFails(self, code, result=None):
        result = result or self.ws.validate()
        self.assertFalse(result["ok"], "expected validation to fail")
        self.assertIn(code, self.codes(result), json.dumps(result["diagnostics"], indent=2))
        return result

    def test_sample_passes_with_size_warning(self):
        result = self.ws.validate()
        self.assertTrue(result["ok"], json.dumps(result["diagnostics"], indent=2))
        self.assertEqual(result["summary"]["source_task_count"], 13)
        self.assertEqual(result["summary"]["dependency_depth"], 3)
        self.assertEqual(result["summary"]["scheduling_conflicts"], ["F001-P02/F001-P03: src/accounts/cli.py"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["summary"]["justified_sizes"], ["F001-P04 (2)"])

    def test_missing_source_task(self):
        self.ws.edit(self.ws.plan, "- `T013` Run the full test suite and fix any failures\n", "")
        result = self.assertFails("MISSING_SOURCE_TASK")
        self.assertEqual(result["summary"]["missing_source_tasks"], ["T013"])

    def test_duplicate_source_task(self):
        self.ws.edit(self.ws.plan, "- `T001` Create", "- `T013` Run the full test suite and fix any failures\n- `T001` Create")
        self.assertFails("DUPLICATE_SOURCE_TASK")

    def test_unknown_source_task(self):
        self.ws.edit(self.ws.plan, "- `T013` Run", "- `T099` Invented work\n- `T013` Run")
        self.assertFails("UNKNOWN_SOURCE_TASK")

    def test_dependency_cycle(self):
        self.ws.edit(self.ws.plan, "**Blocked by**: None\n\n**Objective**: An importable",
                     "**Blocked by**:\n- `F001-P04`\n\n**Objective**: An importable")
        result = self.assertFails("DEPENDENCY_CYCLE")
        self.assertIn("BLOCKER_NOT_LOWER_NUMBERED", self.codes(result))

    def test_unknown_and_unquoted_blockers(self):
        self.ws.edit(self.ws.plan, "**Blocked by**:\n- `F001-P02`\n- `F001-P03`", "**Blocked by**:\n- `F001-P02`\n- F001-P03\n- `F001-P09`")
        result = self.assertFails("UNQUOTED_BLOCKER")
        self.assertIn("UNKNOWN_BLOCKER", self.codes(result))

    def test_explicit_dependency_order_within_package(self):
        self.ws.edit(self.ws.plan,
                     "- `T004` [GREEN] Implement the in-memory user store in `src/accounts/store.py`\n"
                     "- `T005` Add the password hashing helper in `src/accounts/hashing.py` (depends on T004)",
                     "- `T005` Add the password hashing helper in `src/accounts/hashing.py` (depends on T004)\n"
                     "- `T004` [GREEN] Implement the in-memory user store in `src/accounts/store.py`")
        self.assertFails("SOURCE_TASK_DEPENDENCY_UNORDERED")

    def test_prose_dependency_statement_is_enforced(self):
        self.ws.edit(self.ws.tasks, "US1 and US2 are independent", "US1 and US2 are independent, except T010 depends on T007")
        self._rehash()
        result = self.assertFails("SOURCE_TASK_DEPENDENCY_UNORDERED")
        self.assertIn("add `F001-P02` to Blocked by of F001-P03",
                      next(d["hint"] for d in result["diagnostics"] if d["code"] == "SOURCE_TASK_DEPENDENCY_UNORDERED"))

    def test_phase_barrier_requires_foundational_first(self):
        self.ws.edit(self.ws.plan, "**Blocked by**:\n- `F001-P01`\n\n**Objective**: A user can log in",
                     "**Blocked by**: None\n\n**Objective**: A user can log in")
        result = self.assertFails("PHASE_BARRIER_UNORDERED")
        hint = next(d["hint"] for d in result["diagnostics"] if d["code"] == "PHASE_BARRIER_UNORDERED")
        self.assertIn("add `F001-P01` to Blocked by of F001-P02", hint)

    def test_phase_barrier_polish_waits_on_every_story(self):
        self.ws.edit(self.ws.plan, "**Blocked by**:\n- `F001-P02`\n- `F001-P03`", "**Blocked by**:\n- `F001-P03`")
        result = self.assertFails("PHASE_BARRIER_UNORDERED")
        self.assertTrue(any(d["package"] == "F001-P04" and "F001-P02" in d["message"] for d in result["diagnostics"]))

    def test_polish_phase_with_story_label_still_barriers(self):
        self.ws.edit(self.ws.tasks, "- [ ] T012 [P] Document", "- [ ] T012 [P] [US1] Document")
        self.ws.edit(self.ws.plan, "- `T012` [P] Document", "- `T012` [P] [US1] Document")
        self.ws.edit(self.ws.plan, "**Blocked by**:\n- `F001-P02`\n- `F001-P03`", "**Blocked by**:\n- `F001-P03`")
        self._rehash()
        phase = next(p for p in wp.parse_source(self.ws.tasks.read_text())["phases"] if "Polish" in p["heading"])
        self.assertFalse(phase["story"])
        result = self.assertFails("PHASE_BARRIER_UNORDERED")
        self.assertTrue(any(d["package"] == "F001-P04" and "F001-P02" in d["message"] for d in result["diagnostics"]))

    def test_story_phases_stay_independent(self):
        # P02 and P03 are both User Story phases: neither needs the other.
        result = self.ws.validate()
        packages = {p["id"]: p for p in result["packages"]}
        self.assertEqual(packages["F001-P03"]["blocked_by"], ["F001-P01"])

    def test_red_must_precede_green_in_same_package(self):
        self.ws.edit(self.ws.plan,
                     "- `T006` [US1] [RED] Write failing login tests (valid password, wrong password, unknown user) in `tests/test_login.py`\n"
                     "- `T007` [US1] [GREEN] Implement `login(username, password)` in `src/accounts/login.py`",
                     "- `T007` [US1] [GREEN] Implement `login(username, password)` in `src/accounts/login.py`\n"
                     "- `T006` [US1] [RED] Write failing login tests (valid password, wrong password, unknown user) in `tests/test_login.py`")
        self.assertFails("RED_SEPARATED_FROM_GREEN")

    def test_red_with_dependents_in_several_packages_names_them_all(self):
        self.ws.edit(self.ws.tasks, "US1 and US2 are independent", "US1 and US2 are independent, except T010 depends on T006")
        self._rehash()
        result = self.assertFails("RED_SEPARATED_FROM_GREEN")
        red = next(d for d in result["diagnostics"] if d["code"] == "RED_SEPARATED_FROM_GREEN")
        self.assertIn("T010 (F001-P03)", red["message"])
        self.assertIn("stop for human judgment", red["hint"])
        self.assertIn("Split the test in tasks.md, or accept the large package", red["hint"])
        self.assertNotIn("merge the packages", red["hint"])

    def test_red_same_story_small_repair_keeps_merge_hint(self):
        self.ws.edit(self.ws.tasks, "[US2]", "[US1]", count=20)
        self.ws.edit(self.ws.plan, "[US2]", "[US1]", count=20)
        self.ws.edit(self.ws.tasks, "US1 and US2 are independent", "US1 and US2 are independent, except T010 depends on T006")
        self._rehash()
        result = self.assertFails("RED_SEPARATED_FROM_GREEN")
        hint = next(d["hint"] for d in result["diagnostics"] if d["code"] == "RED_SEPARATED_FROM_GREEN")
        self.assertIn("put T006, T010 in one package", hint)
        self.assertIn("merge the packages involved", hint)

    def test_red_repair_above_eight_tasks_stops_for_human_judgment(self):
        extra = ("- [ ] T014 [US1] Record login attempts in `src/accounts/login.py`\n"
                 "- [ ] T015 [US1] Record login lockouts in `src/accounts/login.py`\n"
                 "- [ ] T016 [US1] Record login notices in `src/accounts/login.py`\n\n")
        self.ws.edit(self.ws.tasks, "## Phase 4:", extra + "## Phase 4:")
        self.ws.edit(self.ws.tasks, "[US2]", "[US1]", count=20)
        self.ws.edit(self.ws.tasks, "US1 and US2 are independent", "US1 and US2 are independent, except T010 depends on T006")
        self.ws.edit(self.ws.plan, "[US2]", "[US1]", count=20)
        self.ws.edit(self.ws.plan, "- `T008` [US1] Add the `login` command to `src/accounts/cli.py`\n",
                     "- `T008` [US1] Add the `login` command to `src/accounts/cli.py`\n"
                     "- `T014` [US1] Record login attempts in `src/accounts/login.py`\n"
                     "- `T015` [US1] Record login lockouts in `src/accounts/login.py`\n"
                     "- `T016` [US1] Record login notices in `src/accounts/login.py`\n")
        self._rehash()
        result = self.assertFails("RED_SEPARATED_FROM_GREEN")
        hint = next(d["hint"] for d in result["diagnostics"] if d["code"] == "RED_SEPARATED_FROM_GREEN")
        self.assertIn("stop for human judgment", hint)
        self.assertIn("Split the test in tasks.md, or accept the large package", hint)
        self.assertNotIn("merge the packages", hint)

    def test_size_justification_silences_the_warning(self):
        self.ws.edit(self.ws.plan, "**Size justification**: the two polish tasks close the feature and neither stands alone.\n\n", "")
        warned = self.ws.validate()
        self.assertTrue(warned["ok"])
        self.assertTrue(any("F001-P04 (2)" in w for w in warned["warnings"]))
        self.ws.edit(self.ws.plan, "**Objective**: Users can find both commands documented",
                     "**Size justification**: both tasks close the feature and neither stands alone.\n\n**Objective**: Users can find both commands documented")
        result = self.ws.validate()
        self.assertTrue(result["ok"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["summary"]["justified_sizes"], ["F001-P04 (2)"])

    def test_placeholder_diagnostic_names_the_token(self):
        self.ws.edit(self.ws.plan, "**Objective**: A user can view their profile from the CLI.", "**Objective**: View <each profile> from the CLI.")
        result = self.assertFails("TEMPLATE_PLACEHOLDER")
        self.assertIn("<each profile>", next(d["message"] for d in result["diagnostics"] if d["code"] == "TEMPLATE_PLACEHOLDER"))

    def test_source_listing_is_paste_ready(self):
        listing = wp.source_listing(self.ws.tasks)
        self.assertIn("- `T005` Add the password hashing helper in `src/accounts/hashing.py` (depends on T004)", listing)
        self.assertIn("T005 <- T004", listing)
        self.assertIn("[shared phase]", listing)

    def test_tests_subsection_counts_as_red(self):
        self.ws.edit(self.ws.tasks, "## Phase 4: User Story 2 - View my profile (Priority: P2)\n\n",
                     "## Phase 4: User Story 2 - View my profile (Priority: P2)\n\n### Tests for User Story 2\n\n")
        self.ws.edit(self.ws.tasks, "- [ ] T010 [US2]", "\n### Implementation for User Story 2\n\n- [ ] T010 [US2]")
        source = wp.parse_source(self.ws.tasks.read_text())
        by_id = {t["id"]: t for t in source["tasks"]}
        self.assertTrue(by_id["T009"]["red"])
        self.assertFalse(by_id["T010"]["red"])

    def test_undeclared_scheduling_conflict(self):
        self.ws.edit(self.ws.plan, "- `F001-P02` / `F001-P03`: `src/accounts/cli.py` — both stories add a subcommand to the same CLI module", "- None")
        result = self.assertFails("PATH_CONFLICT_UNDECLARED")
        self.assertIn("add Blocked by only if tasks.md establishes a dependency",
                      next(d["hint"] for d in result["diagnostics"] if d["code"] == "PATH_CONFLICT_UNDECLARED"))

    def test_stale_scheduling_conflict(self):
        self.ws.edit(self.ws.plan, "**Blocked by**:\n- `F001-P01`\n\n**Objective**: A user can view",
                     "**Blocked by**:\n- `F001-P01`\n- `F001-P02`\n\n**Objective**: A user can view")
        self.assertFails("PATH_CONFLICT_STALE")

    def test_directory_path_overlaps_file(self):
        # P03 now names the package directory instead of cli.py; the overlap alone keeps the declared conflict valid.
        self.ws.edit(self.ws.plan, "- `src/accounts/profile.py`\n- `src/accounts/cli.py`\n- `tests/test_profile.py`",
                     "- `src/accounts`\n- `tests/test_profile.py`")
        result = self.ws.validate()
        self.assertTrue(result["ok"], json.dumps(result["diagnostics"], indent=2))
        self.assertEqual(result["summary"]["scheduling_conflicts"], ["F001-P02/F001-P03: src/accounts, src/accounts/cli.py, src/accounts/login.py"])

    def test_source_changed(self):
        self.ws.edit(self.ws.tasks, "Run the full test suite", "Run the complete test suite")
        self.assertFails("SOURCE_CHANGED")

    def test_source_task_text_must_be_verbatim(self):
        self.ws.edit(self.ws.plan, "Implement `login(username, password)`", "Implement login")
        result = self.assertFails("SOURCE_TASK_TEXT_MISMATCH")
        self.assertIn("copy verbatim", next(d["hint"] for d in result["diagnostics"] if d["code"] == "SOURCE_TASK_TEXT_MISMATCH"))

    def test_ready_package_needs_every_field(self):
        self.ws.edit(self.ws.plan, "**Verification**:\n- `python -m pytest tests/test_profile.py`\n\n", "")
        self.assertFails("READY_FIELDS_INCOMPLETE")

    def test_not_ready_needs_reason(self):
        self.ws.edit(self.ws.plan, "**Ready**: yes", "**Ready**: no")
        self.assertFails("NOT_READY_WITHOUT_REASON")

    def test_not_ready_with_reason_passes(self):
        self.ws.edit(self.ws.plan, "**Ready**: yes", "**Ready**: no — tasks.md does not say which hash algorithm to use")
        self.assertTrue(self.ws.validate()["ok"])

    def test_template_placeholder(self):
        self.ws.edit(self.ws.plan, "**Objective**: A user can view their profile from the CLI.", "**Objective**: <one verifiable outcome>")
        self.assertFails("TEMPLATE_PLACEHOLDER")

    def test_angle_brackets_in_verbatim_source_text_are_allowed(self):
        self.ws.edit(self.ws.tasks, "Implement `login(username, password)`", "Implement `login(username, password) -> Result<T>`")
        self.ws.edit(self.ws.plan, "Implement `login(username, password)`", "Implement `login(username, password) -> Result<T>`")
        self._rehash()
        result = self.ws.validate()
        self.assertTrue(result["ok"], json.dumps(result["diagnostics"], indent=2))

    def test_equivalent_paths_overlap(self):
        self.ws.edit(self.ws.plan, "- `src/accounts/profile.py`\n- `src/accounts/cli.py`", "- `src/accounts/profile.py`\n- `./src/accounts/cli.py`")
        result = self.ws.validate()
        self.assertTrue(result["ok"], json.dumps(result["diagnostics"], indent=2))
        self.assertEqual(result["summary"]["scheduling_conflicts"], ["F001-P02/F001-P03: src/accounts/cli.py"])

    def test_non_utf8_plan_is_a_diagnostic(self):
        self.ws.plan.write_bytes(b"---\nfeature: \"001\"\n\xff\n---\n")
        self.assertFails("ENCODING_INVALID")

    def test_embedded_path_metavariable_is_not_placeholder(self):
        self.assertFalse(wp.has_placeholder("write results to /tmp/run-<n>.json"))
        self.assertTrue(wp.has_placeholder("<Suite>"))

    def test_front_matter_must_start_file(self):
        text = self.ws.plan.read_text()
        self.ws.plan.write_text("\n" + text)
        self.assertFails("FRONT_MATTER_NOT_FIRST_LINE")

    def test_heading_requires_em_dash(self):
        self.ws.edit(self.ws.plan, "## F001-P04 — Documentation", "## F001-P04 - Documentation")
        self.assertFails("INVALID_PACKAGE_HEADING")

    def test_field_colon_outside_bold(self):
        self.ws.edit(self.ws.plan, "**Handoff**:\n- Terminal deliverable for the feature.", "**Handoff:**\n- Terminal deliverable for the feature.")
        self.assertFails("INVALID_FIELD_SYNTAX")

    def test_story_mix_justification_silences_the_warning(self):
        self.ws.edit(self.ws.tasks, "- [ ] T008 [US1]", "- [ ] T008 [US2]")
        self.ws.edit(self.ws.plan, "`T008` [US1]", "`T008` [US2]")
        self._rehash()
        warned = self.ws.validate()
        self.assertTrue(warned["ok"], json.dumps(warned["diagnostics"], indent=2))
        self.assertTrue(any("Story mix justification" in w and "F001-P02" in w for w in warned["warnings"]))
        self.ws.edit(self.ws.plan, "**Objective**: A user can log in with a password from the CLI.",
                     "**Story mix justification**: T008 stays here because the CLI command is the login story's handoff.\n\n"
                     "**Objective**: A user can log in with a password from the CLI.")
        self.assertEqual(self.ws.validate()["warnings"], [])

    def test_extra_blocker_warns_until_justified(self):
        self.ws.edit(self.ws.plan, "**Blocked by**:\n- `F001-P01`\n\n**Objective**: A user can view",
                     "**Blocked by**:\n- `F001-P01`\n- `F001-P02`\n\n**Objective**: A user can view")
        self.ws.edit(self.ws.plan,
                     "- `F001-P02` / `F001-P03`: `src/accounts/cli.py` — both stories add a subcommand to the same CLI module",
                     "- None")
        warned = self.ws.validate()
        self.assertTrue(warned["ok"], json.dumps(warned["diagnostics"], indent=2))
        self.assertTrue(any(w.startswith("EXTRA_BLOCKER:") and "F001-P03" in w and "`F001-P02`" in w for w in warned["warnings"]))
        self.ws.edit(self.ws.plan, "**Objective**: A user can view their profile from the CLI.",
                     "**Blocker justification**: tasks.md says US2 starts only after the US1 checkpoint, which the dependency list does not state.\n\n"
                     "**Objective**: A user can view their profile from the CLI.")
        self.assertFalse(any("EXTRA_BLOCKER" in w for w in self.ws.validate()["warnings"]))

    def test_task_dependency_justifies_blocker(self):
        self.ws.edit(self.ws.tasks, "US1 and US2 are independent", "US1 and US2 are independent, except T010 depends on T007")
        self.ws.edit(self.ws.plan, "**Blocked by**:\n- `F001-P01`\n\n**Objective**: A user can view",
                     "**Blocked by**:\n- `F001-P01`\n- `F001-P02`\n\n**Objective**: A user can view")
        self.ws.edit(self.ws.plan,
                     "- `F001-P02` / `F001-P03`: `src/accounts/cli.py` — both stories add a subcommand to the same CLI module",
                     "- None")
        self._rehash()
        result = self.ws.validate()
        self.assertTrue(result["ok"], json.dumps(result["diagnostics"], indent=2))
        self.assertFalse(any("EXTRA_BLOCKER" in w for w in result["warnings"]))

    def test_transitive_blocker_is_not_extra(self):
        self.ws.edit(self.ws.tasks, "## Phase 1: Setup (Shared Infrastructure)", "## Phase 1: User Story 0 - Skeleton")
        self.ws.edit(self.ws.tasks, "## Phase 2: Foundational (Blocking Prerequisites)", "## Phase 2: User Story 0 - Store")
        self.ws.edit(self.ws.tasks, "## Phase 5: Polish & Cross-Cutting Concerns", "## Phase 5: User Story 3 - Wrap up")
        self.ws.edit(self.ws.tasks, "US1 and US2 are independent",
                     "US1 and US2 are independent. T006 depends on T005. T009 depends on T005. T012 depends on T008 and T011")
        self.ws.edit(self.ws.plan, "**Blocked by**:\n- `F001-P02`\n- `F001-P03`",
                     "**Blocked by**:\n- `F001-P01`\n- `F001-P02`\n- `F001-P03`")
        self._rehash()
        result = self.ws.validate()
        self.assertTrue(result["ok"], json.dumps(result["diagnostics"], indent=2))
        self.assertFalse(any("EXTRA_BLOCKER" in w for w in result["warnings"]))

    def test_ownership_path_conflict_is_required(self):
        self.ws.edit(self.ws.plan, "- `src/accounts/login.py`\n- `src/accounts/cli.py`\n- `tests/test_login.py`",
                     "- `src/accounts/login.py`\n- `tests/test_login.py`")
        self.ws.edit(self.ws.plan, "- `src/accounts/profile.py`\n- `src/accounts/cli.py`\n- `tests/test_profile.py`",
                     "- `src/accounts/profile.py`\n- `tests/test_profile.py`")
        self.ws.edit(self.ws.plan,
                     "- `F001-P02` / `F001-P03`: `src/accounts/cli.py` — both stories add a subcommand to the same CLI module",
                     "- None")
        result = self.assertFails("PATH_CONFLICT_UNDECLARED")
        message = next(d["message"] for d in result["diagnostics"] if d["code"] == "PATH_CONFLICT_UNDECLARED")
        self.assertIn("src/accounts/cli.py", message)

    def test_ownership_exclusion_is_not_a_write(self):
        self.ws.edit(self.ws.plan, "- `src/accounts/login.py`\n- `src/accounts/cli.py`\n- `tests/test_login.py`",
                     "- `src/accounts/login.py`\n- `tests/test_login.py`")
        self.ws.edit(self.ws.plan, "- `src/accounts/profile.py`\n- `src/accounts/cli.py`\n- `tests/test_profile.py`",
                     "- `src/accounts/profile.py`\n- `tests/test_profile.py`")
        self.ws.edit(self.ws.plan, "adds only the login command to `src/accounts/cli.py`", "adds only the login command")
        self.ws.edit(self.ws.plan,
                     "- Owns `src/accounts/profile.py` and `tests/test_profile.py`; adds only the profile command to `src/accounts/cli.py`.",
                     "- Does not touch `src/accounts/cli.py`.\n- Do not edit `src/accounts/login.py`.\n- Must not write `tests/test_login.py`.\n- Never owns `src/accounts/login.py`.")
        self.ws.edit(self.ws.plan,
                     "- `F001-P02` / `F001-P03`: `src/accounts/cli.py` — both stories add a subcommand to the same CLI module",
                     "- None")
        result = self.ws.validate()
        self.assertTrue(result["ok"], json.dumps(result["diagnostics"], indent=2))
        self.assertEqual(result["summary"]["scheduling_conflicts"], [])

    def test_broad_path_warns_for_single_segment(self):
        self.ws.edit(self.ws.plan,
                     "- Owns `src/accounts/login.py` and `tests/test_login.py`; adds only the login command to `src/accounts/cli.py`.",
                     "- Owns `src/accounts/login.py` and `tests/test_login.py`; adds only the login command to `src/accounts/cli.py`.\n- Owns `src`.")
        result = self.ws.validate()
        self.assertTrue(result["ok"], json.dumps(result["diagnostics"], indent=2))
        self.assertTrue(any(w.startswith("BROAD_PATH:") and "F001-P02" in w and "`src`" in w for w in result["warnings"]))

    def test_checked_package_checkbox_is_an_error(self):
        self.ws.edit(self.ws.plan, "- [ ] F001-P04 ", "- [x] F001-P04 ")
        self.assertFails("PACKAGE_CHECKBOX_CHECKED")
        self.ws.edit(self.ws.plan, "- [x] F001-P04 ", "- [X] F001-P04 ")
        self.assertFails("PACKAGE_CHECKBOX_CHECKED")

    def test_package_numbering(self):
        self.ws.edit(self.ws.plan, "F001-P04", "F001-P05", count=10)
        self.assertFails("PACKAGE_NUMBERING")

    def test_crlf_line_endings(self):
        for path in (self.ws.plan, self.ws.tasks):
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self._rehash()
        result = self.ws.validate()
        self.assertTrue(result["ok"], json.dumps(result["diagnostics"], indent=2))

    def _rehash(self):
        import hashlib
        digest = hashlib.sha256(self.ws.tasks.read_bytes()).hexdigest()
        lines = self.ws.plan.read_bytes().decode().splitlines(keepends=True)
        lines = [f'source_sha256: "{digest}"' + ("\r\n" if l.endswith("\r\n") else "\n") if l.startswith("source_sha256:") else l for l in lines]
        self.ws.plan.write_bytes("".join(lines).encode())


class PromoteTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        subprocess.run(["git", "init", "-q"], cwd=str(self.ws.root), check=True)
        self.draft = self.ws.feature / "tasks-packages.draft.md"
        shutil.copy(self.ws.plan, self.draft)

    def tearDown(self):
        self.ws.close()

    def test_refuses_to_replace_without_regenerate(self):
        before = self.ws.plan.read_bytes()
        outcome = wp.promote(self.draft, regenerate=False)
        self.assertEqual(outcome["code"], "OUTPUT_EXISTS")
        self.assertEqual(outcome["exit"], 3)
        self.assertEqual(self.ws.plan.read_bytes(), before)
        self.assertTrue(self.draft.exists())

    def test_regenerate_keeps_a_backup(self):
        before = self.ws.plan.read_bytes()
        self.ws.edit(self.draft, "# Work packages: Account login", "# Work packages: Account login (regenerated)")
        first = wp.promote(self.draft, regenerate=True)
        self.assertTrue(first["ok"], first)
        self.assertEqual(Path(first["backup"]).read_bytes(), before)
        self.assertFalse(self.draft.exists())
        shutil.copy(self.ws.plan, self.draft)
        second = wp.promote(self.draft, regenerate=True)
        self.assertNotEqual(first["backup"], second["backup"], "a backup must never be overwritten")
        self.assertTrue(Path(first["backup"]).exists())

    def test_unjustified_warning_blocks_promote(self):
        before = self.ws.plan.read_bytes()
        self.ws.edit(self.draft, "**Size justification**: the two polish tasks close the feature and neither stands alone.\n\n", "")
        outcome = wp.promote(self.draft, regenerate=True)
        self.assertEqual(outcome["code"], "WARNINGS_UNJUSTIFIED")
        self.assertEqual(outcome["exit"], 1)
        self.assertEqual(self.ws.plan.read_bytes(), before)
        self.assertTrue(self.draft.exists())
        self.assertEqual(list(self.ws.feature.glob("*.bak.md")), [])

    def test_invalid_draft_changes_nothing(self):
        before = self.ws.plan.read_bytes()
        self.ws.edit(self.draft, "- `T013` Run the full test suite and fix any failures\n", "")
        outcome = wp.promote(self.draft, regenerate=True)
        self.assertEqual(outcome["code"], "DRAFT_INVALID")
        self.assertEqual(self.ws.plan.read_bytes(), before)
        self.assertEqual(list(self.ws.feature.glob("*.bak.md")), [])

    def test_first_promotion_creates_output(self):
        self.ws.plan.unlink()
        outcome = wp.promote(self.draft, regenerate=False)
        self.assertTrue(outcome["ok"])
        self.assertIsNone(outcome["backup"])
        self.assertTrue(self.ws.plan.exists())


class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        subprocess.run(["git", "init", "-q"], cwd=str(self.ws.root), check=True)

    def tearDown(self):
        self.ws.close()

    def test_explicit_path(self):
        info = wp.resolve_feature(self.ws.root, str(FEATURE), env={})
        self.assertEqual(info["resolved_from"], "explicit-path")
        self.assertEqual(info["feature"], "001")
        self.assertTrue(info["output_exists"])
        self.assertEqual(info["tasks_relative"], str(FEATURE / "tasks.md"))

    def test_environment_variable(self):
        info = wp.resolve_feature(self.ws.root, None, env={"SPECIFY_FEATURE_DIRECTORY": str(FEATURE)})
        self.assertEqual(info["resolved_from"], "SPECIFY_FEATURE_DIRECTORY")

    def test_feature_json(self):
        (self.ws.root / ".specify").mkdir()
        (self.ws.root / ".specify" / "feature.json").write_text(json.dumps({"feature_directory": str(FEATURE)}))
        info = wp.resolve_feature(self.ws.root, None, env={})
        self.assertEqual(info["resolved_from"], ".specify/feature.json")

    def test_spec_kit_helper_wins(self):
        helper = self.ws.root / ".specify" / "scripts" / "bash"
        helper.mkdir(parents=True)
        (helper / "check-prerequisites.sh").write_text(f"#!/bin/bash\necho '{{\"FEATURE_DIR\": \"{self.ws.feature}\"}}'\n")
        (self.ws.root / ".specify" / "feature.json").write_text(json.dumps({"feature_directory": "elsewhere"}))
        info = wp.resolve_feature(self.ws.root, None, env={})
        self.assertEqual(info["resolved_from"], "check-prerequisites")
        self.assertEqual(Path(info["feature_dir"]), self.ws.feature.resolve())

    def test_tasks_without_a_task_line(self):
        self.ws.tasks.write_text("# Tasks\n\n1. T001 Create the store\n")
        with self.assertRaises(wp.UsageError) as caught:
            wp.resolve_feature(self.ws.root, str(FEATURE), env={})
        self.assertEqual(caught.exception.code, "TASKS_FORMAT")

    def test_missing_tasks(self):
        self.ws.tasks.unlink()
        with self.assertRaises(wp.UsageError) as caught:
            wp.resolve_feature(self.ws.root, str(FEATURE), env={})
        self.assertEqual(caught.exception.code, "SOURCE_TASKS_NOT_FOUND")

    def test_nothing_to_resolve(self):
        with self.assertRaises(wp.UsageError) as caught:
            wp.resolve_feature(self.ws.root, None, env={})
        self.assertEqual(caught.exception.code, "FEATURE_DIR_NOT_FOUND")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.close()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(self.ws.root), capture_output=True, text=True,
                              env={**os.environ, "SPECIFY_FEATURE_DIRECTORY": ""})

    def test_exit_codes(self):
        ok = self.run_cli("validate", str(self.ws.plan), "--repo-root", str(self.ws.root))
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("PASS", ok.stdout)
        self.ws.edit(self.ws.plan, "- `T013` Run the full test suite and fix any failures\n", "")
        bad = self.run_cli("validate", str(self.ws.plan), "--repo-root", str(self.ws.root), "--json")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("MISSING_SOURCE_TASK", [d["code"] for d in json.loads(bad.stdout)["diagnostics"]])
        missing = self.run_cli("resolve", "--feature-dir", "specs/none")
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
