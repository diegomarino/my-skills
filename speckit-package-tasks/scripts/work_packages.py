#!/usr/bin/env python3
"""Resolve, validate, and promote a Spec Kit tasks-packages.md (Python 3.9+, stdlib only).

Commands:
  resolve  [--feature-dir DIR] [--json]       locate the feature directory and its tasks.md
  validate [PATH] [--feature-dir DIR] [--repo-root DIR] [--json]
                                               deterministic audit of a tasks-packages file
  source-tasks [--feature-dir DIR]             print verbatim Source tasks entries by phase (drafting aid)
  promote  DRAFT [--regenerate] [--repo-root DIR] [--json]
                                               validate a draft, then move it to tasks-packages.md

Exit codes: 0 ok (validate stays 0 when only warnings remain), 1 validation failed
               or promote refused for unjustified warnings, 2 usage or resolution error,
               3 refused to replace output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_NAME = "tasks-packages.md"
REQUIRED_WHEN_READY = [
    "Source tasks", "Objective", "Scope", "Constraints", "Ownership", "Primary paths",
    "Acceptance criteria", "Verification", "Handoff",
]
ALWAYS_REQUIRED = ["Ready", "Source tasks", "Blocked by"]
NONE_ALLOWED = ("Source tasks", "Constraints")
SIZE_MIN, SIZE_MAX = 3, 8

PKG = r"F\d+-P\d+"
HEADING = re.compile(rf"^## ({PKG}) — (.+?)\s*$")
CHECKBOX = re.compile(rf"^- \[([ xX])\] ({PKG})((?: \[[^\]]+\])*) (.+?)\s*$")
FIELD = re.compile(r"^\*\*([A-Za-z ]+)\*\*:\s*(.*)$")
BAD_FIELD = re.compile(r"^\*\*([A-Za-z ]+):\*\*")
FRONT = re.compile(r'^([A-Za-z][A-Za-z0-9_-]*): "([^"]*)"$')
BACKTICK_ID = re.compile(rf"`({PKG})`")
BARE_ID = re.compile(rf"(?<!`)\b({PKG})\b(?!`)")
SOURCE_ENTRY = re.compile(r"^`?(T\d{3,})`?(?:\s+(.*))?$")
TASK_LINE = re.compile(r"^\s*- \[[ xX]\] (T\d{3,})\b\s*(.*)$")
DEPENDS = re.compile(r"\(depends on ([^)]*)\)", re.IGNORECASE)
# Prose statements such as "T011 depends on T008/T010" in the Dependencies section.
PROSE_DEPENDS = re.compile(r"\b(T\d{3,}) depends on (T\d{3,}(?:\s*(?:/|,|\+|and)\s*T\d{3,})*)", re.IGNORECASE)
TASK_ID = re.compile(r"\bT\d{3,}\b")
LABEL = re.compile(r"^\[([^\]]+)\]\s*")
PHASE = re.compile(r"^##\s+Phase\s+\S+", re.IGNORECASE)
SHARED_PHASE = re.compile(r"\b(setup|foundational|polish)\b", re.IGNORECASE)
EXCLUDED_OWNERSHIP = re.compile(r"^(does not|do not|must not|never)\b", re.IGNORECASE)


class UsageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_lines(text: str) -> list:
    return re.split(r"\r\n|\n|\r", text)


def norm(text: str) -> str:
    return " ".join(text.split())


def git_root(start: Path) -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(start),
                             capture_output=True, text=True, check=False)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except OSError:
        pass
    return start.resolve()


# --------------------------------------------------------------------------- resolve

def resolve_feature(cwd: Path, feature_dir: "str | None" = None, env=None) -> dict:
    """Resolution order: explicit dir, Spec Kit check-prerequisites helper, env var, .specify/feature.json."""
    env = os.environ if env is None else env
    if feature_dir:
        path = Path(feature_dir)
        path = (path if path.is_absolute() else cwd / path).resolve()
        if not path.is_dir():
            raise UsageError("FEATURE_DIR_NOT_FOUND", f"feature directory does not exist: {path}")
        return _feature_result(git_root(path), path, "explicit-path")
    root = git_root(cwd)
    for rel in (".specify/scripts/bash/check-prerequisites.sh", ".specify/scripts/sh/check-prerequisites.sh"):
        helper = root / rel
        if not helper.is_file():
            continue
        try:
            out = subprocess.run(["bash", str(helper), "--json", "--paths-only"], cwd=str(root),
                                 capture_output=True, text=True, check=False, env=dict(env))
            value = json.loads(out.stdout).get("FEATURE_DIR") if out.returncode == 0 else None
        except (OSError, ValueError, AttributeError):
            value = None
        if isinstance(value, str) and value:
            source = "check-prerequisites (SPECIFY_FEATURE_DIRECTORY)" if env.get("SPECIFY_FEATURE_DIRECTORY") else "check-prerequisites"
            return _feature_result(root, _abs(root, value), source)
        break
    if env.get("SPECIFY_FEATURE_DIRECTORY"):
        return _feature_result(root, _abs(root, env["SPECIFY_FEATURE_DIRECTORY"]), "SPECIFY_FEATURE_DIRECTORY")
    feature_json = root / ".specify" / "feature.json"
    if feature_json.is_file():
        try:
            value = json.loads(feature_json.read_text(encoding="utf-8")).get("feature_directory")
        except (ValueError, AttributeError):
            value = None
        if isinstance(value, str) and value:
            return _feature_result(root, _abs(root, value), ".specify/feature.json")
    raise UsageError("FEATURE_DIR_NOT_FOUND",
                     "feature directory not found; pass --feature-dir, set SPECIFY_FEATURE_DIRECTORY, "
                     "or ensure .specify/feature.json contains feature_directory")


def _abs(root: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _feature_result(root: Path, feature_dir: Path, resolved_from: str) -> dict:
    if not feature_dir.is_dir():
        raise UsageError("FEATURE_DIR_NOT_FOUND", f"feature directory does not exist: {feature_dir} (resolved from {resolved_from})")
    tasks = feature_dir / "tasks.md"
    if not tasks.is_file():
        raise UsageError("SOURCE_TASKS_NOT_FOUND", f"tasks.md not found in {feature_dir}")
    output = feature_dir / OUTPUT_NAME
    return {
        "repo_root": str(root),
        "feature_dir": str(feature_dir),
        "tasks": str(tasks),
        "tasks_relative": os.path.relpath(tasks, root),
        "tasks_sha256": sha256_file(tasks),
        "feature": _feature_number(feature_dir),
        "output": str(output),
        "output_exists": output.exists(),
        "resolved_from": resolved_from,
    }


def _feature_number(feature_dir: Path) -> "str | None":
    match = re.match(r"^(\d+)-", feature_dir.name)
    return match.group(1) if match else None


# --------------------------------------------------------------------------- source tasks.md

def parse_source(text: str) -> dict:
    """Parse Spec Kit tasks.md: tasks, phases, test subsections, labels, explicit dependencies."""
    tasks, phases, prose = [], [], []
    phase, tests_section, current = None, False, None
    for line in split_lines(text):
        prose.extend((m.group(1), TASK_ID.findall(m.group(2))) for m in PROSE_DEPENDS.finditer(line))
        task = TASK_LINE.match(line)
        if task:
            body = task.group(2).strip()
            labels, rest = [], body
            while True:
                label = LABEL.match(rest)
                if not label:
                    break
                labels.append(label.group(1))
                rest = rest[label.end():]
            current = {
                "id": task.group(1), "text": body, "labels": labels,
                "phase": phase, "tests_section": tests_section,
                "deps": [], "order": len(tasks),
            }
            tasks.append(current)
            continue
        if current is not None and line.strip() and line[:1] in (" ", "\t") and not line.lstrip().startswith("- "):
            current["text"] = f"{current['text']} {line.strip()}"
            continue
        current = None
        if line.startswith("## "):
            tests_section = False
            if PHASE.match(line):
                phase = len(phases)
                phases.append({"index": phase, "heading": line[3:].strip(), "story": bool(re.search(r"user story", line, re.I))})
            else:
                phase = None
        elif line.startswith("### "):
            heading = line[4:]
            tests_section = bool(re.search(r"\btests?\b", heading, re.I)) and not re.search(r"implementation", heading, re.I)
    stated = {}
    for subject, deps in prose:
        stated.setdefault(subject, []).extend(deps)
    for task in tasks:
        task["text"] = norm(task["text"])
        inline = [d for clause in DEPENDS.findall(task["text"]) for d in TASK_ID.findall(clause)]
        task["deps"] = [d for d in dict.fromkeys(inline + stated.get(task["id"], [])) if d != task["id"]]
        task["story"] = next((l for l in task["labels"] if re.fullmatch(r"US\d+", l)), None)
        upper = [l.upper() for l in task["labels"]]
        task["red_green"] = any(("RED" in l and "GREEN" in l) for l in upper)
        task["green"] = "GREEN" in upper
        task["red"] = not task["red_green"] and ("RED" in upper or (task["tests_section"] and not task["green"]))
        task["explicit_red"] = "RED" in upper
        if task["story"] and task["phase"] is not None:
            phases[task["phase"]]["story"] = True
    for phase in phases:
        # A [USn] label must not turn Setup, Foundational, or Polish into a story phase.
        if SHARED_PHASE.search(phase["heading"]):
            phase["story"] = False
    return {"tasks": tasks, "phases": phases}


# --------------------------------------------------------------------------- tasks-packages.md

class Doc:
    def __init__(self):
        self.front = {}
        self.packages = []
        self.sections = {}
        self.conflicts = []
        self.conflicts_section = False


def parse_packages(raw: bytes, diagnostics: list) -> "Doc | None":
    if raw.startswith(b"\xef\xbb\xbf"):
        diagnostics.append(diag("BOM_AT_START", None, "front matter must begin on line 1; UTF-8 BOM is not allowed"))
        return None
    try:
        lines = split_lines(raw.decode("utf-8"))
    except UnicodeDecodeError:
        diagnostics.append(diag("ENCODING_INVALID", None, "tasks-packages file is not valid UTF-8"))
        return None
    doc = Doc()
    if not lines or lines[0] != "---":
        diagnostics.append(diag("FRONT_MATTER_NOT_FIRST_LINE", None, "front matter must begin on line 1"))
        return None
    end = None
    for index in range(1, len(lines)):
        if lines[index] == "---":
            end = index
            break
        entry = FRONT.match(lines[index])
        if not entry:
            diagnostics.append(diag("FRONT_MATTER_VALUE_INVALID", None, f"front matter line {index + 1} must be key: \"value\""))
            return None
        doc.front[entry.group(1)] = entry.group(2)
    if end is None:
        diagnostics.append(diag("FRONT_MATTER_UNTERMINATED", None, "front matter closing delimiter is missing"))
        return None

    current, last_field, section = None, None, None
    for line in lines[end + 1:]:
        heading = HEADING.match(line)
        if heading:
            current = {"id": heading.group(1), "title": heading.group(2), "checkbox": None, "fields": {}, "markers": []}
            doc.packages.append(current)
            last_field, section = None, None
            continue
        if line.startswith("## "):
            candidate = re.match(r"^## (F\d\S*)", line)
            if candidate:
                if not re.fullmatch(PKG, candidate.group(1)):
                    diagnostics.append(diag("INVALID_PACKAGE_IDENTIFIER", candidate.group(1), f"invalid package identifier: {candidate.group(1)}"))
                else:
                    diagnostics.append(diag("INVALID_PACKAGE_HEADING", candidate.group(1), f"package heading must be '## <id> — <title>' with U+2014: {candidate.group(1)}"))
                current, section = None, None
                continue
            current, last_field = None, None
            section = line[3:].strip().lower()
            doc.sections[section] = []
            if section == "scheduling conflicts":
                doc.conflicts_section = True
            continue
        if current is None:
            if section is not None:
                doc.sections[section].append(line)
                if section == "scheduling conflicts" and re.match(r"^\s*-\s", line):
                    doc.conflicts.append(line.strip()[1:].strip())
            stray = re.match(rf"^- \[[ xX]\] ({PKG})(?:\s|$)", line)
            if stray:
                diagnostics.append(diag("PACKAGE_CHECKBOX_WITHOUT_HEADING", stray.group(1), f"package checkbox has no matching heading: {stray.group(1)}"))
            continue
        check = CHECKBOX.match(line)
        if check:
            if check.group(2) != current["id"]:
                diagnostics.append(diag("PACKAGE_CHECKBOX_MISMATCH", current["id"], f"package checkbox {check.group(2)} does not match heading {current['id']}"))
            current["checkbox"] = check.group(4)
            current["checkbox_mark"] = check.group(1)
            current["markers"] = re.findall(r"\[([^\]]+)\]", check.group(3))
            continue
        bad_box = re.match(r"^- \[[ xX]\] (F\S+)", line)
        if bad_box and not re.fullmatch(PKG, bad_box.group(1)):
            diagnostics.append(diag("INVALID_PACKAGE_IDENTIFIER", bad_box.group(1), f"invalid package identifier: {bad_box.group(1)}"))
            continue
        named = FIELD.match(line)
        if named:
            name, value = named.group(1), named.group(2).strip()
            current["fields"][name] = [value] if value else []
            last_field = name
            continue
        if BAD_FIELD.match(line):
            diagnostics.append(diag("INVALID_FIELD_SYNTAX", current["id"], f"{current['id']}: field colon must be outside the bold name: {line.strip()}"))
            continue
        if last_field and re.match(r"^\s*-\s", line):
            current["fields"][last_field].append(line.strip()[1:].strip())
        elif last_field and current["fields"][last_field] and line[:1] in (" ", "\t") and line.strip():
            current["fields"][last_field][-1] = f"{current['fields'][last_field][-1]} {line.strip()}"
    return doc


def diag(code: str, package, message: str, hint: "str | None" = None) -> dict:
    item = {"code": code, "package": package, "message": message}
    if hint:
        item["hint"] = hint
    return item


def values(pkg: dict, name: str) -> list:
    return pkg["fields"].get(name, [])


def is_none(items: list) -> bool:
    return not items or (len(items) == 1 and items[0].strip().lower() in ("none", "none."))


def backtick_paths(items: list, skip_excluded: bool = False) -> list:
    found = []
    for item in items:
        if skip_excluded and EXCLUDED_OWNERSHIP.match(item.strip()):
            continue
        for path in re.findall(r"`([^`]+)`", item):
            path = path.strip().rstrip("/")
            path = posixpath.normpath(path) if path else path
            if path and path not in found:
                found.append(path)
    return found


def primary_paths(pkg: dict) -> list:
    return backtick_paths(values(pkg, "Primary paths"))


def ownership_paths(pkg: dict) -> list:
    """Write-paths named in Ownership. Leading exclusion bullets are not writes."""
    return backtick_paths(values(pkg, "Ownership"), skip_excluded=True)


def conflict_paths(pkg: dict) -> list:
    found = []
    for path in primary_paths(pkg) + ownership_paths(pkg):
        if path not in found:
            found.append(path)
    return found


def paths_overlap(a: str, b: str) -> bool:
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def has_placeholder(text: str) -> bool:
    return find_placeholder(text) is not None


def find_placeholder(text: str) -> "str | None":
    for match in re.finditer(r"<[^>\r\n]+>", text):
        token, start = match.group(0), match.start()
        seg_start = max(text.rfind(" ", 0, start), text.rfind("`", 0, start), text.rfind("\n", 0, start)) + 1
        tail = re.search(r"[\s`]", text[start:])
        segment = text[seg_start: len(text) if tail is None else start + tail.start()]
        embedded = (re.fullmatch(r"<[a-z]>", token) is not None and "/" in segment
                    and segment.index(token) > 0 and segment.index(token) + len(token) < len(segment))
        if not embedded:
            return token
    return None


def find_cycle(edges: dict) -> "list | None":
    color = {node: 0 for node in edges}
    stack = []

    def visit(node):
        color[node] = 1
        stack.append(node)
        for nxt in edges.get(node, []):
            if nxt not in color:
                continue
            if color[nxt] == 1:
                return stack[stack.index(nxt):] + [nxt]
            if color[nxt] == 0:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        color[node] = 2
        return None

    for node in edges:
        if color[node] == 0:
            found = visit(node)
            if found:
                return found
    return None


def closure(node: str, edges: dict) -> set:
    seen, pending = set(), list(edges.get(node, []))
    while pending:
        nxt = pending.pop()
        if nxt in seen or nxt not in edges:
            continue
        seen.add(nxt)
        pending.extend(edges.get(nxt, []))
    return seen


def levels(ids: list, edges: dict) -> dict:
    memo = {}

    def depth(node):
        if node not in memo:
            memo[node] = 0  # guards recursion; graph is acyclic when called
            blockers = [b for b in edges.get(node, []) if b in edges]
            memo[node] = 1 + (max(depth(b) for b in blockers) if blockers else 0)
        return memo[node]

    return {node: depth(node) for node in ids}


def ready_state(pkg: dict) -> "tuple[str | None, str]":
    raw = " ".join(values(pkg, "Ready")).strip()
    match = re.match(r"^(yes|no)\b\s*(?:[—\-:]+\s*)?(.*)$", raw, re.I)
    if not match:
        return None, raw
    return match.group(1).lower(), match.group(2).strip()


# --------------------------------------------------------------------------- validate

def validate(path: Path, repo_root: "Path | None" = None) -> dict:
    path = path.resolve()
    diagnostics, warnings = [], []
    if not path.is_file():
        return _result(False, [diag("WORK_PACKAGES_NOT_FOUND", None, f"file not found: {path}")], [], {}, [])
    feature_dir = path.parent
    root = (repo_root or git_root(feature_dir)).resolve()
    doc = parse_packages(path.read_bytes(), diagnostics)
    if doc is None:
        return _result(False, diagnostics, warnings, {}, [])

    # Front matter and source binding.
    dir_feature = _feature_number(feature_dir)
    feature = doc.front.get("feature")
    if dir_feature and feature and feature != dir_feature:
        diagnostics.append(diag("FEATURE_PREFIX_MISMATCH", None, f'front matter feature "{feature}" disagrees with directory prefix "{dir_feature}"'))
    feature = feature or dir_feature
    if not feature or not re.fullmatch(r"\d+", feature):
        diagnostics.append(diag("FEATURE_REQUIRED", None, 'front matter needs feature: "NNN" when the directory has no NNN- prefix'))
        feature = None
    source_text, source = None, None
    declared = doc.front.get("source")
    expected_tasks = feature_dir / "tasks.md"
    if not declared:
        diagnostics.append(diag("SOURCE_REQUIRED", None, 'front matter needs source: "<repo-relative path to tasks.md>"'))
    elif os.path.isabs(declared) or declared.startswith("../") or "/../" in declared:
        diagnostics.append(diag("SOURCE_PATH_INVALID", None, f"source must be a repository-relative path: {declared}"))
    elif (root / declared).resolve() != expected_tasks.resolve():
        diagnostics.append(diag("SOURCE_PATH_MISMATCH", None, f"source {declared} is not this feature's tasks.md ({os.path.relpath(expected_tasks, root)})"))
    elif not expected_tasks.is_file():
        diagnostics.append(diag("SOURCE_TASKS_NOT_FOUND", None, f"source tasks.md not found: {declared}"))
    else:
        source_bytes = expected_tasks.read_bytes()
        try:
            source_text = source_bytes.decode("utf-8")
        except UnicodeDecodeError:
            diagnostics.append(diag("ENCODING_INVALID", None, "tasks.md is not valid UTF-8"))
            return _result(False, diagnostics, warnings, {}, [])
        digest = hashlib.sha256(source_bytes).hexdigest()
        if doc.front.get("source_sha256") != digest:
            diagnostics.append(diag("SOURCE_CHANGED", None,
                                    f"source_sha256 does not match current tasks.md ({digest})",
                                    "tasks.md changed after packaging: re-derive affected packages in a draft (a promoted file needs an explicit regenerate request), then update source_sha256"))
        source = parse_source(source_text)

    # Package structure.
    packages = doc.packages
    by_id = {}
    for pkg in packages:
        if pkg["id"] in by_id:
            diagnostics.append(diag("DUPLICATE_PACKAGE_ID", pkg["id"], f"duplicate package identifier: {pkg['id']}"))
        by_id.setdefault(pkg["id"], pkg)
    if not packages:
        diagnostics.append(diag("NO_PACKAGES", None, "no packages found"))
    ids = [pkg["id"] for pkg in packages]
    if feature:
        expected = [f"F{feature}-P{n:02d}" for n in range(1, len(packages) + 1)]
        if ids != expected:
            diagnostics.append(diag("PACKAGE_NUMBERING", None, f"package ids must be unique, contiguous and ordered from F{feature}-P01: {', '.join(ids)}"))
    incomplete = []
    for pkg in packages:
        pid = pkg["id"]
        if pkg["checkbox"] is None:
            diagnostics.append(diag("MISSING_PACKAGE_CHECKBOX", pid, f"{pid}: missing '- [ ] {pid} <title>' checkbox"))
        else:
            if pkg["checkbox"] != pkg["title"]:
                diagnostics.append(diag("PACKAGE_TITLE_MISMATCH", pid, f"{pid}: heading title != checkbox title"))
            if pkg.get("checkbox_mark") in ("x", "X"):
                diagnostics.append(diag("PACKAGE_CHECKBOX_CHECKED", pid, f"{pid}: package checkbox must stay unchecked [ ]",
                                        "leave the marker as [ ]; ticking a package checkbox is an error"))
        for name in ALWAYS_REQUIRED:
            if name not in pkg["fields"]:
                diagnostics.append(diag("MISSING_FIELD", pid, f"{pid}: missing {name} field"))
        ready, reason = ready_state(pkg)
        if "Ready" in pkg["fields"]:
            if ready is None:
                diagnostics.append(diag("INVALID_READY_VALUE", pid, f"{pid}: Ready must be 'yes' or 'no — <reason>'"))
            elif ready == "no" and not reason:
                diagnostics.append(diag("NOT_READY_WITHOUT_REASON", pid, f"{pid}: Ready: no needs the precise blocker"))
            elif ready == "yes":
                empty = [name for name in REQUIRED_WHEN_READY if not any(v.strip() for v in values(pkg, name)) or (name not in NONE_ALLOWED and is_none(values(pkg, name)))]
                if empty:
                    incomplete.append(f"{pid} ({', '.join(empty)})")
                    diagnostics.append(diag("READY_FIELDS_INCOMPLETE", pid, f"ready package has incomplete fields: {pid} ({', '.join(empty)})"))
        # Source tasks are verbatim source text (e.g. `Result<T>`), so they are exempt from the placeholder scan.
        text = " ".join([pkg["title"], pkg["checkbox"] or ""] + [v for name, vs in pkg["fields"].items() if name != "Source tasks" for v in vs])
        token = find_placeholder(text)
        if token:
            diagnostics.append(diag("TEMPLATE_PLACEHOLDER", pid, f"{pid}: unfilled template placeholder {token}",
                                    f"replace {token} with the real value; write literal syntax such as a CLI argument in backticks with a concrete name"))

    # Dependency graph.
    edges = {}
    for pkg in packages:
        blockers = []
        items = values(pkg, "Blocked by")
        if not is_none(items):
            joined = " ".join(items)
            blockers = BACKTICK_ID.findall(joined)
            for bare in BARE_ID.findall(joined):
                diagnostics.append(diag("UNQUOTED_BLOCKER", pkg["id"], f"{pkg['id']}: Blocked by must backtick package ids: {bare}"))
            if not blockers and not BARE_ID.findall(joined):
                diagnostics.append(diag("INVALID_BLOCKED_BY", pkg["id"], f"{pkg['id']}: Blocked by must be None or backticked package ids"))
        edges[pkg["id"]] = blockers
        for blocker in blockers:
            if blocker not in by_id:
                diagnostics.append(diag("UNKNOWN_BLOCKER", pkg["id"], f"{pkg['id']}: Blocked by unknown package {blocker}"))
            elif _number(blocker) >= _number(pkg["id"]):
                diagnostics.append(diag("BLOCKER_NOT_LOWER_NUMBERED", pkg["id"], f"{pkg['id']}: Blocked by {blocker}, which is not lower-numbered",
                                        "number packages in a topological order of the dependency graph"))
    cycle = find_cycle(edges)
    if cycle:
        diagnostics.append(diag("DEPENDENCY_CYCLE", cycle[0], f"dependency cycle: {' -> '.join(cycle)}"))
    reach = {pid: closure(pid, edges) for pid in edges}

    def ordered(a: str, b: str) -> bool:
        return a in reach.get(b, set()) or b in reach.get(a, set())

    # Source coverage and source-derived ordering.
    owner, oversized, undersized, missing, duplicate, unknown, justified = {}, [], [], [], [], [], []
    source_ids = []
    for pkg in packages:
        pkg["source"] = []
        for item in values(pkg, "Source tasks"):
            if is_none([item]):
                continue
            entry = SOURCE_ENTRY.match(item.strip())
            if not entry:
                diagnostics.append(diag("INVALID_SOURCE_TASK_ENTRY", pkg["id"], f"{pkg['id']}: Source tasks entry must start with a task id: {item}"))
                continue
            pkg["source"].append((entry.group(1), norm(entry.group(2) or "")))
        if not pkg["source"] and "Source tasks" in pkg["fields"]:
            diagnostics.append(diag("EMPTY_PACKAGE", pkg["id"], f"{pkg['id']}: a package must own at least one source task"))
    if source is not None:
        by_task = {task["id"]: task for task in source["tasks"]}
        source_ids = [task["id"] for task in source["tasks"]]
        mapped = [tid for pkg in packages for tid, _ in pkg["source"]]
        missing = sorted(set(source_ids) - set(mapped))
        unknown = sorted(set(mapped) - set(source_ids))
        duplicate = sorted({tid for tid in mapped if mapped.count(tid) > 1})
        for tid in missing:
            diagnostics.append(diag("MISSING_SOURCE_TASK", None, f"missing source task: {tid}"))
        for tid in duplicate:
            diagnostics.append(diag("DUPLICATE_SOURCE_TASK", None, f"duplicate source task: {tid}"))
        for tid in unknown:
            diagnostics.append(diag("UNKNOWN_SOURCE_TASK", None, f"unknown source task: {tid}"))
        for pkg in packages:
            for index, (tid, text) in enumerate(pkg["source"]):
                owner.setdefault(tid, (pkg["id"], index))
                if tid in by_task and text != by_task[tid]["text"]:
                    diagnostics.append(diag("SOURCE_TASK_TEXT_MISMATCH", pkg["id"],
                                            f"{pkg['id']}: {tid} text differs from tasks.md",
                                            f"copy verbatim: `{tid}` {by_task[tid]['text']}"))
            count = len(pkg["source"])
            if _justified(pkg, "Size justification"):
                justified.append(f"{pkg['id']} ({count})")
            elif count > SIZE_MAX:
                oversized.append(f"{pkg['id']} ({count})")
            elif count < SIZE_MIN:
                undersized.append(f"{pkg['id']} ({count})")
            stories = sorted({by_task[tid]["story"] for tid, _ in pkg["source"] if tid in by_task and by_task[tid]["story"]})
            if len(stories) > 1 and not _justified(pkg, "Story mix justification"):
                warnings.append(f"{pkg['id']} mixes user stories {', '.join(stories)}; independent stories usually belong in separate packages "
                                "(split them, or add a Story mix justification field)")
        if not (missing or duplicate or unknown):
            if not cycle:
                diagnostics.extend(_ordering_checks(source, owner, reach))
            warnings.extend(_extra_blocker_warnings(packages, edges, source, owner))

    # Primary paths.
    for pkg in packages:
        for p in primary_paths(pkg):
            candidate = (root / p).resolve()
            if os.path.isabs(p) or not (candidate == root or str(candidate).startswith(str(root) + os.sep)):
                diagnostics.append(diag("PRIMARY_PATH_OUTSIDE_REPOSITORY", pkg["id"], f"primary path escapes repository: {pkg['id']}: {p}"))
            elif source_text is not None and not candidate.exists() and p not in source_text:
                diagnostics.append(diag("PRIMARY_PATH_NOT_DECLARED", pkg["id"], f"primary path neither exists nor is named in tasks.md: {pkg['id']}: {p}"))

    # Scheduling conflicts: unordered packages sharing primary paths or ownership write-paths.
    for pkg in packages:
        for path in conflict_paths(pkg):
            # A dotted single segment is a root file (README.md, pyproject.toml). A bare
            # segment (src, tests) covers an unbounded tree.
            if "/" not in path and "." not in path:
                warnings.append(f"BROAD_PATH: {pkg['id']}: `{path}` is a single path segment; narrow the path")
    computed = {}
    for i, a in enumerate(packages):
        for b in packages[i + 1:]:
            if ordered(a["id"], b["id"]):
                continue
            paths_a, paths_b = conflict_paths(a), conflict_paths(b)
            shared = sorted({x for x in paths_a for y in paths_b if paths_overlap(x, y)} |
                            {y for x in paths_a for y in paths_b if paths_overlap(x, y)})
            if shared:
                computed[frozenset((a["id"], b["id"]))] = (a["id"], b["id"], shared)
    declared_pairs = set()
    if not doc.conflicts_section:
        diagnostics.append(diag("MISSING_CONFLICTS_SECTION", None, "missing '## Scheduling conflicts' section (use '- None' when empty)"))
    for entry in doc.conflicts:
        if is_none([entry]):
            continue
        if has_placeholder(entry):
            diagnostics.append(diag("TEMPLATE_PLACEHOLDER", None, f"unfilled template placeholder in scheduling conflict: {entry}"))
        pair = BACKTICK_ID.findall(entry)
        if len(pair) < 2 or len(set(pair[:2])) != 2:
            diagnostics.append(diag("INVALID_CONFLICT_ENTRY", None, f"scheduling conflict entry needs two backticked package ids: {entry}"))
            continue
        declared_pairs.add(frozenset(pair[:2]))
    for key, (a, b, shared) in computed.items():
        if key not in declared_pairs:
            diagnostics.append(diag("PATH_CONFLICT_UNDECLARED", f"{a}/{b}",
                                    f"{a} and {b} can run concurrently and share paths: {', '.join(shared)}",
                                    f"add '- `{a}` / `{b}`: {', '.join('`' + s + '`' for s in shared)} — <why>' under Scheduling conflicts; "
                                    "add Blocked by only if tasks.md establishes a dependency"))
    for key in declared_pairs - set(computed):
        pair = sorted(key)
        diagnostics.append(diag("PATH_CONFLICT_STALE", "/".join(pair),
                                f"declared scheduling conflict {pair[0]}/{pair[1]} is not a shared-path pair of concurrently runnable packages"))

    # Summary.
    depth_info = {"depth": None, "chain_end": None, "widest": None}
    if not cycle and packages:
        lv = levels(ids, edges)
        counts = {}
        for value in lv.values():
            counts[value] = counts.get(value, 0) + 1
        chain_end = max(lv, key=lambda k: lv[k])
        widest_level = max(counts, key=lambda k: (counts[k], -k))
        depth_info = {"depth": lv[chain_end], "chain_end": chain_end, "widest": [counts[widest_level], widest_level]}
    if oversized:
        warnings.append(f"packages above {SIZE_MAX} source tasks (split, or add a Size justification field): {', '.join(oversized)}")
    if undersized:
        warnings.append(f"packages below {SIZE_MIN} source tasks (merge, or add a Size justification field): {', '.join(undersized)}")
    ready_count = sum(1 for pkg in packages if ready_state(pkg)[0] == "yes")
    summary = {
        "feature_dir": os.path.relpath(feature_dir, root),
        "source_task_count": len(source_ids) if source else None,
        "covered_source_task_count": len(set(source_ids) - set(missing)) if source else None,
        "missing_source_tasks": missing, "duplicate_source_tasks": duplicate, "unknown_source_tasks": unknown,
        "package_count": len(packages), "ready_package_count": ready_count,
        "dependency_depth": depth_info["depth"], "longest_chain_ends_at": depth_info["chain_end"],
        "widest_level": depth_info["widest"],
        "dependency_cycle": cycle,
        "scheduling_conflicts": [f"{a}/{b}: {', '.join(s)}" for a, b, s in computed.values()],
        "packages_outside_size_range": oversized + undersized,
        "justified_sizes": justified,
        "ready_packages_with_incomplete_fields": incomplete,
    }
    graph = [{"id": pkg["id"], "title": pkg["title"], "ready": ready_state(pkg)[0], "blocked_by": edges.get(pkg["id"], []),
              "source_tasks": [tid for tid, _ in pkg.get("source", [])], "primary_paths": primary_paths(pkg)} for pkg in packages]
    return _result(not diagnostics, diagnostics, warnings, summary, graph)


def _number(pid: str) -> int:
    return int(pid.rsplit("-P", 1)[1])


def _justified(pkg: dict, field: str) -> bool:
    return any(v.strip() for v in values(pkg, field))


def phases_barrier(phases: list, earlier: dict, later: dict) -> bool:
    """True when the shared-phase barrier requires earlier to precede later."""
    if earlier["phase"] is None or later["phase"] is None or earlier["phase"] >= later["phase"]:
        return False
    return not (phases[earlier["phase"]]["story"] and phases[later["phase"]]["story"])


def _edge_is_shortcut(pkg_id: str, blocker: str, edges: dict) -> bool:
    """True when blocker is already reached from pkg through other Blocked-by edges."""
    alt = dict(edges)
    alt[pkg_id] = [item for item in edges.get(pkg_id, []) if item != blocker]
    return blocker in closure(pkg_id, alt)


def _extra_blocker_warnings(packages: list, edges: dict, source: dict, owner: dict) -> list:
    by_id = {task["id"]: task for task in source["tasks"]}
    phases = source["phases"]
    owned = {}
    for tid, (pid, _) in owner.items():
        owned.setdefault(pid, []).append(tid)
    out = []
    for pkg in packages:
        if _justified(pkg, "Blocker justification"):
            continue
        pid = pkg["id"]
        for blocker in edges.get(pid, []):
            if blocker not in edges:
                continue
            later = [by_id[tid] for tid in owned.get(pid, []) if tid in by_id]
            earlier = [by_id[tid] for tid in owned.get(blocker, []) if tid in by_id]
            dep = any(dep_id in set(owned.get(blocker, [])) for task in later for dep_id in task["deps"])
            barrier = any(phases_barrier(phases, a, b) for a in earlier for b in later)
            if dep or barrier or _edge_is_shortcut(pid, blocker, edges):
                continue
            out.append(f"EXTRA_BLOCKER: {pid}: Blocked by `{blocker}` is not required by a task dependency, a phase barrier, "
                       "or another blocker path; remove the edge or quote the tasks.md sentence in Blocker justification")
    return out


def _ordering_checks(source: dict, owner: dict, reach: dict) -> list:
    """Explicit dependencies, phase barriers, and RED-before-GREEN co-location."""
    out = []
    tasks = source["tasks"]
    phases = source["phases"]

    def satisfied(pre: str, post: str) -> bool:
        (pp, pi), (qp, qi) = owner[pre], owner[post]
        return pi < qi if pp == qp else pp in reach.get(qp, set())

    # 1. Explicit "(depends on T...)" edges.
    for task in tasks:
        for dep in task["deps"]:
            if dep not in owner or task["id"] not in owner or satisfied(dep, task["id"]):
                continue
            (dp, _), (tp, _) = owner[dep], owner[task["id"]]
            if dp == tp:
                out.append(diag("SOURCE_TASK_DEPENDENCY_UNORDERED", tp, f"{task['id']} in {tp} lists dependency {dep} after it in Source tasks",
                                f"move {dep} before {task['id']} in {tp}"))
            else:
                out.append(diag("SOURCE_TASK_DEPENDENCY_UNORDERED", tp, f"{task['id']} in {tp} depends on {dep} in {dp} without a Blocked by path",
                                f"add `{dp}` to Blocked by of {tp}, or move the tasks into one package"))

    # 2. Phase barriers: a non-story phase blocks every later phase and waits on every earlier phase.
    seen = set()
    for a in tasks:
        for b in tasks:
            if not phases_barrier(phases, a, b):
                continue
            if a["id"] not in owner or b["id"] not in owner or satisfied(a["id"], b["id"]):
                continue
            (ap, _), (bp, _) = owner[a["id"]], owner[b["id"]]
            key = (ap, bp)
            if key in seen:
                continue
            seen.add(key)
            pa, pb = phases[a["phase"]]["heading"], phases[b["phase"]]["heading"]
            if ap == bp:
                out.append(diag("PHASE_BARRIER_UNORDERED", bp, f"{bp}: {b['id']} ({pb}) is listed before {a['id']} ({pa})",
                                f"order Source tasks of {bp} by phase"))
            else:
                out.append(diag("PHASE_BARRIER_UNORDERED", bp, f"{bp} ({b['id']}, {pb}) can start before {ap} ({a['id']}, {pa})",
                                f"add `{ap}` to Blocked by of {bp}; stop for human judgment only if tasks.md explicitly allows this overlap"))

    # 3. RED tests stay in the package of the GREEN implementation they govern.
    for index, red in enumerate(tasks):
        if not red["red"] or red["id"] not in owner:
            continue
        rp = owner[red["id"]][0]
        same_phase = [t for t in tasks[index + 1:] if t["phase"] == red["phase"] and not t["red"]]
        problem = None
        dependents = [t for t in tasks if red["id"] in t["deps"] and not t["red"] and t["id"] in owner]
        outside = [d for d in dependents if owner[d["id"]][0] != rp]
        if dependents:
            if outside:
                listed = ", ".join("{} ({})".format(d["id"], owner[d["id"]][0]) for d in outside)
                together_ids = [red["id"]] + [d["id"] for d in outside]
                together = ", ".join(together_ids)
                involved = {rp} | {owner[d["id"]][0] for d in outside}
                owned_ids = [tid for tid, (pid, _) in owner.items() if pid in involved]
                story_labels = sorted({task["story"] for task in tasks if task["id"] in set(owned_ids) and task["story"]})
                if len(owned_ids) > SIZE_MAX or len(story_labels) > 1:
                    hint = ("stop for human judgment: the repair would put more than 8 source tasks in one package "
                            "or combine tasks that carry more than one distinct user-story label. "
                            "Split the test in tasks.md, or accept the large package. Do not merge automatically")
                else:
                    hint = ("a failing test ships together with every implementation that depends on it: "
                            f"put {together} in one package (merge the packages involved). "
                            "If that package becomes large, add a Size justification field")
                problem = (f"test {red['id']} is a prerequisite of {listed}, outside its package", hint)
        elif red["explicit_red"]:
            governed = next((t for t in same_phase if t["green"]), None) or (same_phase[0] if same_phase else None)
            if governed and governed["id"] in owner and not (owner[governed["id"]][0] == rp and satisfied(red["id"], governed["id"])):
                problem = (f"{red['id']} [RED] must precede {governed['id']} in the same package", f"put {red['id']} immediately before {governed['id']} in {owner[governed['id']][0]}")
        else:
            candidates = [t for t in same_phase if red["story"] is None or t["story"] == red["story"]]
            if candidates and not any(c["id"] in owner and owner[c["id"]][0] == rp and satisfied(red["id"], c["id"]) for c in candidates):
                problem = (f"test task {red['id']} is not packaged before any implementation task it governs",
                           f"move {red['id']} into the package that implements its behavior, ahead of that implementation")
        if problem:
            out.append(diag("RED_SEPARATED_FROM_GREEN", rp, f"{rp}: {problem[0]}", problem[1]))
    return out


def _result(ok: bool, diagnostics: list, warnings: list, summary: dict, packages: list) -> dict:
    return {"ok": ok, "diagnostics": diagnostics, "warnings": warnings, "summary": summary, "packages": packages}


def render(result: dict) -> str:
    s = result["summary"]
    none = lambda items: ", ".join(items) if items else "None"
    lines = []
    if s:
        na = s["source_task_count"] is None
        lines += [
            f"- Feature directory: {s['feature_dir']}",
            f"- Source task count: {'N/A' if na else s['source_task_count']}",
            f"- Covered source task count: {'N/A' if na else s['covered_source_task_count']}",
            f"- Missing source tasks: {none(s['missing_source_tasks'])}",
            f"- Duplicate source tasks: {none(s['duplicate_source_tasks'])}",
            f"- Unknown source tasks: {none(s['unknown_source_tasks'])}",
            f"- Package count: {s['package_count']} ({s['ready_package_count']} ready)",
            f"- Dependency depth: {s['dependency_depth']} (longest chain ends at {s['longest_chain_ends_at']})",
            f"- Widest level: {s['widest_level'][0] if s['widest_level'] else 'N/A'} packages"
            + (f" at depth {s['widest_level'][1]}" if s["widest_level"] else ""),
            f"- Dependency cycles: {' -> '.join(s['dependency_cycle']) if s['dependency_cycle'] else 'None'}",
            f"- Scheduling conflicts: {none(s['scheduling_conflicts'])}",
            f"- Packages outside size range: {none(s['packages_outside_size_range'])}"
            + (f" (justified: {', '.join(s['justified_sizes'])})" if s.get("justified_sizes") else ""),
            f"- Ready packages with incomplete fields: {none(s['ready_packages_with_incomplete_fields'])}",
        ]
    lines += [f"WARN: {w}" for w in result["warnings"]]
    for d in result["diagnostics"]:
        lines.append(f"ERROR {d['code']}: {d['message']}" + (f"\n  fix: {d['hint']}" if d.get("hint") else ""))
    lines.append("PASS: deterministic checks passed (semantic review still required)" if result["ok"] else "FAIL")
    return "\n".join(lines)


# --------------------------------------------------------------------------- promote

def promote(draft: Path, regenerate: bool, repo_root: "Path | None" = None) -> dict:
    draft = draft.resolve()
    target = draft.parent / OUTPUT_NAME
    if draft == target:
        raise UsageError("DRAFT_IS_OUTPUT", f"draft must not be {OUTPUT_NAME} itself")
    if target.exists() and not regenerate:
        return {"ok": False, "code": "OUTPUT_EXISTS", "exit": 3,
                "message": f"{target} exists; replacing it needs an explicit regenerate request (--regenerate)"}
    result = validate(draft, repo_root)
    if not result["ok"]:
        return {"ok": False, "code": "DRAFT_INVALID", "exit": 1, "message": "draft failed validation; nothing was changed", "validation": result}
    if result["warnings"]:
        return {"ok": False, "code": "WARNINGS_UNJUSTIFIED", "exit": 1,
                "message": "draft has unjustified warnings; nothing was changed", "validation": result}
    backup = None
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = target.with_name(f"tasks-packages.{stamp}.bak.md")
        suffix = 1
        while backup.exists():
            backup = target.with_name(f"tasks-packages.{stamp}-{suffix}.bak.md")
            suffix += 1
        shutil.copy2(target, backup)
        if backup.read_bytes() != target.read_bytes():
            raise UsageError("BACKUP_FAILED", f"backup verification failed: {backup}")
    os.replace(draft, target)
    return {"ok": True, "exit": 0, "output": str(target), "backup": str(backup) if backup else None}


def source_listing(tasks_path: Path) -> str:
    source = parse_source(tasks_path.read_text(encoding="utf-8"))
    out, phase = [], object()
    for task in source["tasks"]:
        if task["phase"] != phase:
            phase = task["phase"]
            heading = source["phases"][phase]["heading"] if phase is not None else "(no phase)"
            kind = "" if phase is None else (" [story phase]" if source["phases"][phase]["story"] else " [shared phase]")
            out.append(f"\n# {heading}{kind}")
        out.append(f"- `{task['id']}` {task['text']}")
    deps = [f"{t['id']} <- {', '.join(t['deps'])}" for t in source["tasks"] if t["deps"]]
    reds = [t["id"] for t in source["tasks"] if t["red"]]
    out.append("\n# Explicit dependencies (task <- prerequisites)\n" + ("\n".join(deps) or "None"))
    out.append("\n# RED test tasks\n" + (", ".join(reds) or "None"))
    return "\n".join(out).lstrip("\n")


# --------------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("--feature-dir")
    p_resolve.add_argument("--json", action="store_true")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("path", nargs="?")
    p_validate.add_argument("--feature-dir")
    p_validate.add_argument("--repo-root", help="override git detection of the repository root")
    p_validate.add_argument("--json", action="store_true")
    p_source = sub.add_parser("source-tasks")
    p_source.add_argument("--feature-dir")
    p_promote = sub.add_parser("promote")
    p_promote.add_argument("draft")
    p_promote.add_argument("--regenerate", action="store_true")
    p_promote.add_argument("--repo-root", help="override git detection of the repository root")
    p_promote.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "resolve":
            info = resolve_feature(Path.cwd(), args.feature_dir)
            print(json.dumps(info, indent=2) if args.json else "\n".join(f"{k}: {v}" for k, v in info.items()))
            return 0
        if args.command == "validate":
            path = Path(args.path) if args.path else Path(resolve_feature(Path.cwd(), args.feature_dir)["output"])
            result = validate(path, Path(args.repo_root) if args.repo_root else None)
            print(json.dumps(result, indent=2) if args.json else render(result))
            return 0 if result["ok"] else 1
        if args.command == "source-tasks":
            print(source_listing(Path(resolve_feature(Path.cwd(), args.feature_dir)["tasks"])))
            return 0
        outcome = promote(Path(args.draft), args.regenerate, Path(args.repo_root) if args.repo_root else None)
        if args.json:
            print(json.dumps(outcome, indent=2))
        elif outcome["ok"]:
            print(f"promoted: {outcome['output']}" + (f" (previous kept at {outcome['backup']})" if outcome["backup"] else ""))
        else:
            print(f"{outcome['code']}: {outcome['message']}", file=sys.stderr)
            if "validation" in outcome:
                print(render(outcome["validation"]))
        return outcome["exit"]
    except UsageError as error:
        print(json.dumps({"error": {"code": error.code, "message": str(error)}}) if getattr(args, "json", False)
              else f"{error.code}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
