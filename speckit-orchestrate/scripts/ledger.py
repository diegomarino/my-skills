#!/usr/bin/env python3
"""Append-only evidence ledger for orchestrating approved work packages (Python 3.9+, stdlib only).

The ledger records facts that the coordinator observed through its integrations. It never contacts
an executor, tracker, or delivery system; it only refuses records that the plan, the run profile,
or earlier records make unsafe.

Files (all inside the feature directory):
  tasks-packages.md            approved plan (read only)
  orchestration.md            run profile: settings + integration capabilities (read only)
  orchestration-ledger.jsonl  append-only ledger written by this script

Commands:
  check-profile PATH                       validate a run profile
  init [--rebind] [--attested-by NAME --evidence TEXT]
                                           bind the ledger to the current plan and profile
  status | next | gate                     derived state, eligible actions, completion gate
  request PKG implement|review|fix         reserve an operation key before contacting the executor
  accepted OP --assignment REF ...         executor accepted the assignment
  absent OP ...                            reconciliation proved no assignment exists
  completed OP --outcome ... [--head SHA]  worker finished (succeeded or failed)
  reviewed OP --head SHA --verdict ...     independent review result pinned to a head
  delivered PKG --head SHA --target BRANCH verified delivery of the current head into base_branch
  halt --reason TEXT                       stop the line (request then returns LINE_STOPPED; gate stays blocked)
  resume --attested-by NAME --evidence TEXT
                                           clear a halt
  check-completion --package PKG --worktree PATH --head SHA --op OPKEY
                                           read-only worktree check; does not write the ledger
  resource REF --action created|released|retained   resource accounting

`delivered` refuses unless every direct blocker is already delivered (BLOCKERS_UNDELIVERED), --head is
the package's current head (WRONG_HEAD), no operation on the package is open, and the state is
ready-to-deliver (REVIEW_REQUIRED). --attested-by and --evidence together record an external merge from
needs-review, changes-requested or ready-to-deliver; any other state is NOT_DELIVERABLE. A head with no
passing review is still recorded on that attested path and returned with the review-gap warning.

`check-completion` exits 0 only when HEAD equals --head (else HEAD_MISMATCH), the worktree is clean
(DIRTY_WORKTREE), the commit message contains a line `Orchestration-Op: OPKEY` (TRAILER_MISSING), and
every path in `git diff --name-only <base_branch>...HEAD` is inside the package Ownership write-paths
(PATH_OUTSIDE_OWNERSHIP). Unknown package: UNKNOWN_PACKAGE. No parseable write-path: OWNERSHIP_UNPARSEABLE.
It still runs while the line is halted. Write-paths are backticked Ownership paths, skipping bullets that
start with "Does not", "Do not", "Must not" or "Never"; a file matches a path when it equals it or is under it.

`max_parallel` counts open implement and fix operations only. An open review does not take a slot.

`init` runs the sibling speckit-package-tasks validator (../speckit-package-tasks/scripts/work_packages.py
next to this skill) on tasks-packages.md. Exit 0 is success, warnings included. Any other exit is
PLAN_INVALID and includes the tail of the validator's stdout. If that file is absent, init warns and
records plan_validated false. `init --rebind` refuses REBIND_LOOSENS when a package that already has an
operation or a delivery loses a blocker id or a primary path, unless --attested-by and --evidence are
passed. Adding a blocker or a path is allowed. Old ledgers without stored edges skip that check.
New bindings store tasks_path relative to the git root; an absolute stored path (old ledgers) is hashed
as that absolute path.

`authorized` in a profile is a comma-separated subset of: assign, review, push, merge, tracker, release.
Empty is allowed. Unknown tokens are a profile error. merge_by agent requires the merge token. The ledger
does not intercept git.

Evidence-bearing records need --via <operation> (declared supported or human in the profile) and
--evidence TEXT describing the external proof; human operations also need --attested-by. When the
system cannot answer whether an assignment exists, `accepted|absent --via user --attested-by NAME`
records a person's decision as an attestation, never as a system receipt.
Exit codes: 0 ok, 1 refused or gate failed, 2 usage error or unreadable files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None

PLAN, PROFILE, LEDGER = "tasks-packages.md", "orchestration.md", "orchestration-ledger.jsonl"
PURPOSES = ("implement", "review", "fix")
CAPS = {"implement": 2, "fix": 3}  # failed implementations / fix rounds before the user must decide
OPERATIONS = {
    "executor": ("assign", "observe", "find", "release"),
    "delivery": ("submit", "observe_delivery", "deliver"),
    "tracker": ("project_status",),
}
MUST_WORK = {("executor", "assign"), ("executor", "observe"), ("delivery", "observe_delivery")}
SETTINGS = ("harness", "implement_model", "review_model", "isolation", "base_branch", "max_parallel",
            "review_by", "delivery_mode", "merge_by", "tracker", "on_finish", "authorized")
AUTHORIZED = ("assign", "review", "push", "merge", "tracker", "release")
VIA = {"accepted": ("assign", "find"), "absent": ("find",), "completed": ("observe",), "reviewed": ("observe",),
       "delivered": ("observe_delivery",), "created": ("assign", "observe"), "released": ("release",)}
PKG = r"F\d+-P\d+"
EVENT_KEYS = {"bound": ("plan_sha256", "profile_sha256", "settings", "roles"), "request": ("op", "package", "purpose"),
              "accepted": ("op", "assignment"), "absent": ("op",), "completed": ("op", "outcome"),
              "reviewed": ("op", "head", "verdict"), "delivered": ("package", "head", "target"),
              "halt": ("reason",), "resume": ("attested_by", "evidence"), "resource": ("ref", "action")}
# Sibling skill, installed next to this one. Tests monkeypatch this path.
VALIDATOR = Path(__file__).resolve().parents[1].parent / "speckit-package-tasks" / "scripts" / "work_packages.py"
_SKIP_OWNERSHIP = re.compile(r"^(?:does not|do not|must not|never)\b", re.IGNORECASE)
ATTESTED_DELIVERY = ("needs-review", "changes-requested", "ready-to-deliver")
VALIDATOR_MISSING = ("package validator is not installed; init did not check task coverage, "
                     "phase barriers, or RED/GREEN grouping")


def norm_path(path: str) -> str:
    path = path.strip().rstrip("/")
    return posixpath.normpath(path) if path else path


def authorized_tokens(value: str) -> list:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def ownership_write_paths(pkg: dict) -> list:
    """Backticked Ownership paths, excluding bullets that deny a write."""
    found = []
    for item in pkg["fields"].get("Ownership", []):
        if _SKIP_OWNERSHIP.match(item.strip()):
            continue
        for path in re.findall(r"`([^`]+)`", item):
            path = norm_path(path)
            if path and path not in found:
                found.append(path)
    return found


def path_inside(file_path: str, owned: str) -> bool:
    file_path, owned = norm_path(file_path), norm_path(owned)
    return bool(owned) and (file_path == owned or file_path.startswith(owned + "/"))


def git_text(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)


class Refused(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def sha256(path: Path) -> "str | None":
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def lines_of(text: str) -> list:
    return re.split(r"\r\n|\n|\r", text)


def front_matter(lines: list, what: str) -> "tuple[dict, int]":
    if not lines or lines[0] != "---":
        raise Refused("FRONT_MATTER_INVALID", f"{what}: front matter must begin on line 1")
    data = {}
    for index in range(1, len(lines)):
        if lines[index] == "---":
            return data, index
        match = re.match(r'^([A-Za-z][A-Za-z0-9_-]*): "([^"]*)"$', lines[index])
        if not match:
            raise Refused("FRONT_MATTER_INVALID", f"{what}: line {index + 1} must be key: \"value\"")
        data[match.group(1)] = match.group(2)
    raise Refused("FRONT_MATTER_INVALID", f"{what}: front matter is not terminated")


# --------------------------------------------------------------------------- profile

def parse_profile(path: Path) -> dict:
    if not path.is_file():
        raise Refused("PROFILE_NOT_FOUND", f"run profile not found: {path}")
    lines = lines_of(path.read_text(encoding="utf-8"))
    settings, end = front_matter(lines, path.name)
    roles, errors, role = {}, [], None
    for line in lines[end + 1:]:
        heading = re.match(r"^## (Executor|Delivery|Tracker)\b(?::\s*(.*))?\s*$", line)
        if heading:
            role = heading.group(1).lower()
            roles[role] = {"name": (heading.group(2) or "").strip(), "identity": None, "ops": {}}
            continue
        if line.startswith("## "):
            role = None
            continue
        if role is None:
            continue
        identity = re.match(r"^- identity:\s*(.+)$", line)
        if identity:
            roles[role]["identity"] = identity.group(1).strip()
            continue
        op = re.match(r"^- ([a-z_]+):\s*(\S+)\s*(?:[—–-]+\s*evidence:\s*(.*))?$", line)
        if op:
            name, status, evidence = op.group(1), op.group(2), (op.group(3) or "").strip()
            if name not in OPERATIONS[role]:
                errors.append(f"{role}: unknown operation '{name}' (expected one of {', '.join(OPERATIONS[role])})")
            elif status not in ("supported", "human", "unsupported"):
                errors.append(f"{role}.{name}: status must be supported, human or unsupported")
            else:
                roles[role]["ops"][name] = {"status": status, "evidence": evidence}
    for key in SETTINGS:
        if key == "authorized":
            if key not in settings:
                errors.append("missing setting: authorized")
            continue
        if not settings.get(key, "").strip():
            errors.append(f"missing setting: {key}")
    tokens = authorized_tokens(settings.get("authorized", ""))
    unknown = [token for token in tokens if token not in AUTHORIZED]
    if unknown:
        errors.append(f"authorized: unknown token {', '.join(unknown)}; allowed: {', '.join(AUTHORIZED)}")
    if settings.get("merge_by") == "agent" and "merge" not in tokens:
        errors.append("merge_by agent needs the merge token in authorized")
    if settings.get("isolation") not in (None, "worktree", "checkout", "external"):
        errors.append("isolation must be worktree, checkout or external")
    if settings.get("isolation") == "worktree":
        for key in ("worktree_pattern", "branch_pattern"):
            if not settings.get(key, "").strip():
                errors.append(f"isolation worktree needs setting: {key}")
    try:
        parallel = int(settings.get("max_parallel", "0"))
        if parallel < 1:
            raise ValueError
        if parallel > 1 and settings.get("isolation") == "checkout":
            errors.append("max_parallel > 1 needs per-worker isolation (worktree or external), not a shared checkout")
    except ValueError:
        errors.append("max_parallel must be a positive integer")
    for key, allowed in (("review_by", ("agent", "human")), ("merge_by", ("agent", "human"))):
        if settings.get(key) and settings[key] not in allowed:
            errors.append(f"{key} must be one of {', '.join(allowed)}")
    needed = ["executor", "delivery"] + ([] if settings.get("tracker", "none") == "none" else ["tracker"])
    for name in needed:
        if name not in roles:
            errors.append(f"missing section: ## {name.capitalize()}")
            continue
        if name != "tracker" and not roles[name]["identity"]:
            errors.append(f"{name}: missing '- identity: ...' line")
        for op in OPERATIONS[name]:
            entry = roles[name]["ops"].get(op)
            if entry is None:
                errors.append(f"{name}.{op}: not declared (write '- {op}: unsupported' if the system cannot do it)")
            elif entry["status"] != "unsupported" and not entry["evidence"]:
                errors.append(f"{name}.{op}: {entry['status']} operations must say what evidence they produce")
            elif (name, op) in MUST_WORK and entry["status"] == "unsupported":
                errors.append(f"{name}.{op}: required; orchestration cannot proceed without it")
    deliver = roles.get("delivery", {}).get("ops", {}).get("deliver", {}).get("status")
    if settings.get("merge_by") == "agent" and deliver != "supported":
        errors.append("merge_by agent needs delivery.deliver: supported")
    warnings = []
    if roles.get("executor", {}).get("ops", {}).get("find", {}).get("status") == "unsupported":
        warnings.append("executor.find is unsupported: an assignment whose acceptance is uncertain needs a human decision")
    if roles.get("executor", {}).get("ops", {}).get("release", {}).get("status") == "unsupported":
        warnings.append("executor.release is unsupported: created resources can only be retained, never released through the ledger")
    return {"settings": settings, "roles": roles, "errors": errors, "warnings": warnings}


def op_status(profile: dict, via: str) -> "str | None":
    for role in profile["roles"].values():
        if via in role["ops"]:
            return role["ops"][via]["status"]
    return None


# --------------------------------------------------------------------------- plan

def parse_plan(path: Path) -> dict:
    if not path.is_file():
        raise Refused("PLAN_NOT_FOUND", f"plan not found: {path}")
    lines = lines_of(path.read_text(encoding="utf-8"))
    front, end = front_matter(lines, path.name)
    packages, current, field, section, conflicts = {}, None, None, None, []
    for line in lines[end + 1:]:
        heading = re.match(rf"^## ({PKG}) — (.+?)\s*$", line)
        if heading:
            if heading.group(1) in packages:
                raise Refused("PLAN_INVALID", f"duplicate package id: {heading.group(1)}")
            current = {"id": heading.group(1), "title": heading.group(2), "fields": {}}
            packages[current["id"]] = current
            field, section = None, None
            continue
        if line.startswith("## "):
            if re.match(r"^## F\d", line):
                raise Refused("PLAN_INVALID", f"malformed package heading: {line.strip()}")
            current, field, section = None, None, line[3:].strip().lower()
            continue
        if current is None:
            if section == "scheduling conflicts" and line.lstrip().startswith("- "):
                pair = re.findall(rf"`({PKG})`", line)
                if len(pair) >= 2:
                    conflicts.append(tuple(pair[:2]))
            continue
        named = re.match(r"^\*\*([A-Za-z ]+)\*\*:\s*(.*)$", line)
        if named:
            field = named.group(1)
            current["fields"][field] = [named.group(2).strip()] if named.group(2).strip() else []
        elif field and re.match(r"^\s*-\s", line):
            current["fields"][field].append(line.strip()[1:].strip())
    if not packages:
        raise Refused("PLAN_INVALID", "plan has no packages")
    for pkg in packages.values():
        joined = " ".join(pkg["fields"].get("Blocked by", [])).strip()
        pkg["blocked_by"] = re.findall(rf"`({PKG})`", joined)
        bare = re.findall(rf"(?<!`)\b{PKG}\b(?!`)", joined)
        if bare or (joined.lower().rstrip(".") != "none" and not pkg["blocked_by"]):
            raise Refused("PLAN_INVALID", f"{pkg['id']}: Blocked by must be None or backticked package ids: {joined or '(empty)'}")
        pkg["source_tasks"] = re.findall(r"\bT\d{3,}\b", " ".join(re.match(r"^`?(T\d{3,})", item).group(1)
                                         for item in pkg["fields"].get("Source tasks", []) if re.match(r"^`?(T\d{3,})", item)))
        ready = " ".join(pkg["fields"].get("Ready", [])).strip().lower()
        pkg["ready"] = ready.startswith("yes")
        pkg["paths"] = sorted({norm_path(p) for item in pkg["fields"].get("Primary paths", []) for p in re.findall(r"`([^`]+)`", item)})
        for blocker in pkg["blocked_by"]:
            if blocker not in packages:
                raise Refused("PLAN_INVALID", f"{pkg['id']} is blocked by unknown package {blocker}")
    cycle = _cycle({pid: p["blocked_by"] for pid, p in packages.items()})
    if cycle:
        raise Refused("PLAN_INVALID", f"dependency cycle: {' -> '.join(cycle)}")
    reach = {pid: _closure(pid, packages) for pid in packages}
    pairs = set()
    for a, b in conflicts:
        if a in packages and b in packages:
            pairs.add(frozenset((a, b)))
    ids = list(packages)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if a in reach[b] or b in reach[a]:
                continue
            if any(x == y or x.startswith(y + "/") or y.startswith(x + "/") for x in packages[a]["paths"] for y in packages[b]["paths"]):
                pairs.add(frozenset((a, b)))
    return {"front": front, "packages": packages, "conflicts": pairs, "reach": reach}


def _cycle(edges: dict) -> "list | None":
    color, stack = {k: 0 for k in edges}, []

    def visit(node):
        color[node] = 1
        stack.append(node)
        for nxt in edges.get(node, []):
            if color.get(nxt) == 1:
                return stack[stack.index(nxt):] + [nxt]
            if color.get(nxt) == 0:
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


def _closure(pid: str, packages: dict) -> set:
    seen, pending = set(), list(packages[pid]["blocked_by"])
    while pending:
        nxt = pending.pop()
        if nxt not in seen:
            seen.add(nxt)
            pending.extend(packages[nxt]["blocked_by"])
    return seen


# --------------------------------------------------------------------------- ledger storage

class Ledger:
    def __init__(self, feature_dir: Path):
        self.dir = feature_dir.resolve()
        self.path = self.dir / LEDGER
        self.events = []
        self.size = 0

    def load(self) -> "Ledger":
        if not self.path.exists():
            raise Refused("LEDGER_NOT_FOUND", f"no ledger at {self.path}; run init first")
        data = self.path.read_bytes()
        self.size = len(data)
        try:
            raw = data.decode("utf-8")
        except UnicodeDecodeError:
            raise Refused("LEDGER_CORRUPT", f"{self.path} is not valid UTF-8")
        if raw and not raw.endswith("\n"):
            raise Refused("LEDGER_CORRUPT", f"{self.path} ends with a partial record; repair it by hand, never by truncating evidence")
        for number, line in enumerate(raw.splitlines(), start=1):
            try:
                event = json.loads(line)
            except ValueError:
                raise Refused("LEDGER_CORRUPT", f"{self.path}:{number} is not valid JSON")
            if not isinstance(event, dict) or event.get("type") not in EVENT_KEYS or any(k not in event for k in EVENT_KEYS[event["type"]]):
                raise Refused("LEDGER_CORRUPT", f"{self.path}:{number} is not a well-formed ledger record")
            if event.get("seq") != number:
                raise Refused("LEDGER_CORRUPT", f"{self.path}:{number} has seq {event.get('seq')}; records were removed or reordered")
            self.events.append(event)
        if not self.events or self.events[0].get("type") != "bound":
            raise Refused("LEDGER_CORRUPT", f"{self.path} must start with a bound record")
        return self

    def append(self, event: dict) -> dict:
        event = {"seq": len(self.events) + 1, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **event}
        line = (json.dumps(event, sort_keys=True) + "\n").encode("utf-8")
        with open(self.path, "ab") as handle:
            if fcntl:
                fcntl.flock(handle, fcntl.LOCK_EX)
            if handle.seek(0, os.SEEK_END) != self.size:
                raise Refused("LEDGER_CHANGED", "the ledger changed while this command ran; rerun it")
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self.size += len(line)
        self.events.append(event)
        return event


# --------------------------------------------------------------------------- derived state

class Run:
    def __init__(self, feature_dir: Path, ledger: Ledger):
        self.dir = feature_dir.resolve()
        self.ledger = ledger
        self.bound = [e for e in ledger.events if e["type"] == "bound"][-1]
        self.plan = parse_plan(self.dir / PLAN)
        # Capabilities and settings come from the bound snapshot: editing orchestration.md changes nothing until rebind.
        self.profile = {"settings": self.bound["settings"], "roles": self.bound["roles"], "warnings": self.bound.get("warnings", [])}
        self.settings = self.profile["settings"]
        self.ops, self.delivered, self.resources = {}, {}, {}
        for event in ledger.events:
            kind = event["type"]
            if kind in ("accepted", "absent", "completed", "reviewed") and event["op"] not in self.ops:
                raise Refused("LEDGER_CORRUPT", f"record {event['seq']} refers to unknown operation {event['op']}")
            if kind == "request":
                self.ops[event["op"]] = {"op": event["op"], "package": event["package"], "purpose": event["purpose"],
                                         "pinned_head": event.get("pinned_head"), "status": "requested",
                                         "assignment": None, "outcome": None, "head": None, "verdict": None, "seq": event["seq"]}
            elif kind == "accepted":
                self.ops[event["op"]].update(status="accepted", assignment=event["assignment"])
            elif kind == "absent":
                self.ops[event["op"]].update(status="absent")
            elif kind == "completed":
                self.ops[event["op"]].update(status="settled", outcome=event["outcome"], head=event.get("head"), seq=event["seq"])
            elif kind == "reviewed":
                self.ops[event["op"]].update(status="settled", outcome="succeeded", head=event["head"], verdict=event["verdict"], seq=event["seq"])
            elif kind == "delivered":
                self.delivered[event["package"]] = event
            elif kind == "resource":
                if event["action"] == "created":
                    self.resources[event["ref"]] = {"ref": event["ref"], "owner": event.get("owner"), "package": event.get("package")}
                self.resources.setdefault(event["ref"], {"ref": event["ref"], "owner": None, "package": None})["state"] = event["action"]

    # Drift: the plan, profile or source changed after binding.
    def drift(self) -> list:
        changed = []
        if sha256(self.dir / PLAN) != self.bound["plan_sha256"]:
            changed.append(PLAN)
        if sha256(self.dir / PROFILE) != self.bound["profile_sha256"]:
            changed.append(PROFILE)
        tasks = self.bound.get("tasks_path")
        # Absolute tasks_path values are legacy bindings; relative ones are repo-root paths.
        if tasks and sha256(Path(tasks) if Path(tasks).is_absolute() else git_root(self.dir) / tasks) != self.bound.get("tasks_sha256"):
            changed.append("tasks.md")
        return changed

    def package_ops(self, pid: str) -> list:
        return sorted((o for o in self.ops.values() if o["package"] == pid), key=lambda o: o["seq"])

    def open_ops(self, pid: "str | None" = None) -> list:
        return [o for o in self.ops.values() if o["status"] in ("requested", "accepted") and (pid is None or o["package"] == pid)]

    def current_head(self, pid: str) -> "str | None":
        heads = [o["head"] for o in self.package_ops(pid) if o["purpose"] in ("implement", "fix") and o["status"] == "settled" and o["outcome"] == "succeeded"]
        return heads[-1] if heads else None

    def review_on(self, pid: str, head: "str | None") -> "dict | None":
        reviews = [o for o in self.package_ops(pid) if o["purpose"] == "review" and o["verdict"] and o["head"] == head]
        return reviews[-1] if reviews else None

    def state(self, pid: str) -> str:
        if pid in self.delivered:
            return "delivered"
        # An open operation stays visible so it can be reconciled; Ready: no applies once it settles.
        open_ops = self.open_ops(pid)
        if open_ops:
            op = open_ops[-1]
            return f"{op['purpose']}-{'requested' if op['status'] == 'requested' else 'assigned'}"
        pkg = self.plan["packages"].get(pid)
        if pkg is None or not pkg["ready"]:
            return "not-ready"
        head = self.current_head(pid)
        if head is None:
            if any(b not in self.delivered for b in pkg["blocked_by"]):
                return "blocked"
            settled = [o for o in self.package_ops(pid) if o["purpose"] == "implement" and o["status"] == "settled"]
            return "failed" if settled and settled[-1]["outcome"] == "failed" else "ready"
        review = self.review_on(pid, head)
        if review is None:
            return "needs-review"
        return "changes-requested" if review["verdict"] == "changes-requested" else "ready-to-deliver"

    def halt_reason(self) -> "str | None":
        """The line is stopped when the latest halt/resume event is a halt."""
        last = None
        for event in self.ledger.events:
            if event["type"] in ("halt", "resume"):
                last = event
        if last and last["type"] == "halt":
            return last.get("reason") or ""
        return None

    def slot_count(self) -> int:
        """Open implement and fix operations. Reviews do not consume a max_parallel slot."""
        return sum(1 for op in self.open_ops() if op["purpose"] in ("implement", "fix"))

    def review_gap(self, pid: str) -> bool:
        event = self.delivered.get(pid)
        if not event:
            return False
        review = self.review_on(pid, event["head"])
        return review is None or review["verdict"] != "pass"

    def partners(self, pid: str) -> list:
        return sorted(next(iter(pair - {pid})) for pair in self.plan["conflicts"] if pid in pair)

    def conflict_holder(self, pid: str, extra: "set | None" = None) -> "str | None":
        """A shared-path partner that is editing or holds an undelivered change blocks implement/fix."""
        for other in self.partners(pid):
            if extra and other in extra:
                return other
            if other in self.delivered:
                continue
            if any(o["purpose"] in ("implement", "fix") for o in self.open_ops(other)) or self.current_head(other):
                return other
        return None

    def eligibility(self, pid: str, purpose: str, extra: "set | None" = None, active: "int | None" = None) -> "str | None":
        """Return None when PURPOSE may start for PID, else the refusal reason."""
        if pid not in self.plan["packages"]:
            return f"unknown package {pid}"
        state = self.state(pid)
        expected = {"implement": ("ready", "failed"), "review": ("needs-review",), "fix": ("changes-requested",)}[purpose]
        if state not in expected:
            return f"{pid} is {state}; {purpose} needs {' or '.join(expected)}"
        if purpose in ("implement", "fix"):
            holder = self.conflict_holder(pid, extra)
            if holder:
                return f"{pid} shares primary paths with {holder}, which is in progress or undelivered"
            limit = int(self.settings.get("max_parallel", "1"))
            active = self.slot_count() if active is None else active
            if active >= limit:
                return f"max_parallel {limit} reached ({active} open implement or fix operations)"
        return None

    def next_actions(self) -> dict:
        start, deliver, waiting, chosen = [], [], [], set()
        active = self.slot_count()
        for pid in self.plan["packages"]:
            state = self.state(pid)
            purpose = {"ready": "implement", "failed": "implement", "needs-review": "review", "changes-requested": "fix"}.get(state)
            if state == "ready-to-deliver":
                deliver.append({"package": pid, "head": self.current_head(pid),
                                "by": self.settings.get("merge_by"), "target": self.settings.get("base_branch")})
                continue
            if purpose is None:
                if state.endswith("-requested"):
                    waiting.append({"package": pid, "state": state, "reason": "acceptance unconfirmed: reconcile with find/observe before anything else"})
                elif state.endswith("-assigned"):
                    waiting.append({"package": pid, "state": state, "reason": "worker active: observe it"})
                elif state == "blocked":
                    pending = [b for b in self.plan["packages"][pid]["blocked_by"] if b not in self.delivered]
                    waiting.append({"package": pid, "state": state, "reason": f"waiting for delivery of {', '.join(pending)}"})
                elif state == "not-ready":
                    waiting.append({"package": pid, "state": state, "reason": "plan marks it Ready: no; needs a human decision"})
                continue
            reason = self.eligibility(pid, purpose, extra=chosen if purpose in ("implement", "fix") else None, active=active)
            if reason:
                waiting.append({"package": pid, "state": state, "reason": reason})
                continue
            start.append({"package": pid, "purpose": purpose, "head": self.current_head(pid) if purpose != "implement" else None})
            if purpose in ("implement", "fix"):
                chosen.add(pid)
                active += 1
        reason = self.halt_reason()
        return {"start": start, "deliver": deliver, "waiting": waiting, "drift": self.drift(),
                "halted": reason is not None, "halt_reason": reason}

    def gate(self) -> dict:
        blockers, warnings = [], []
        halted = self.halt_reason()
        if halted is not None:
            blockers.append(f"line halted: {halted}")
        for pid in self.plan["packages"]:
            if pid not in self.delivered:
                blockers.append(f"{pid} not delivered ({self.state(pid)})")
            elif self.review_gap(pid):
                warnings.append(f"{pid} was delivered at {self.delivered[pid]['head']} without a passing review of that head")
        for op in self.open_ops():
            blockers.append(f"operation {op['op']} is {op['status']} and unsettled")
        for res in self.resources.values():
            if res["state"] == "created" and res.get("owner") == "coordinator":
                blockers.append(f"resource {res['ref']} is neither released nor retained")
            elif res["state"] == "created":
                warnings.append(f"resource {res['ref']} (owner {res.get('owner')}) left untouched; not the coordinator's to release")
        for name in self.drift():
            blockers.append(f"{name} changed after the ledger was bound")
        return {"ok": not blockers, "blockers": blockers, "warnings": warnings}

    def status(self) -> dict:
        rows = []
        for pid, pkg in self.plan["packages"].items():
            rows.append({"package": pid, "title": pkg["title"], "state": self.state(pid), "head": self.current_head(pid),
                         "blocked_by": pkg["blocked_by"], "conflicts_with": self.partners(pid),
                         "delivered": self.delivered.get(pid, {}).get("head"), "review_gap": self.review_gap(pid)})
        reason = self.halt_reason()
        return {"packages": rows, "open_operations": self.open_ops(), "resources": list(self.resources.values()),
                "drift": self.drift(), "settings": self.settings, "warnings": self.profile["warnings"],
                "halted": reason is not None, "halt_reason": reason,
                "plan_validated": self.bound.get("plan_validated", True)}


# --------------------------------------------------------------------------- commands

def git_root(path: Path) -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(path), capture_output=True, text=True, check=False)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except OSError:
        pass
    return path.resolve()


def package_validator_status(plan_path: Path) -> "tuple[bool, list]":
    """Return (validated, warnings). A missing sibling warns; a failing one refuses."""
    if not VALIDATOR.is_file():
        return False, [VALIDATOR_MISSING]
    proc = subprocess.run([sys.executable, str(VALIDATOR), "validate", str(plan_path)], capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout or "").splitlines()[-20:])
        detail = tail or (proc.stderr or "").strip() or f"exit {proc.returncode}"
        raise Refused("PLAN_INVALID", f"package validator failed:\n{detail}")
    return True, []


def _loosened(before: dict, after: dict, history: set) -> list:
    lost = []
    for pid in sorted(history):
        old, new = before.get(pid) or {}, after.get(pid) or {}
        blockers = [item for item in old.get("blocked_by", []) if item not in new.get("blocked_by", [])]
        paths = [item for item in old.get("paths", []) if item not in new.get("paths", [])]
        bits = []
        if blockers:
            bits.append("blockers " + ", ".join(blockers))
        if paths:
            bits.append("paths " + ", ".join(paths))
        if bits:
            lost.append(f"{pid} ({'; '.join(bits)})")
    return lost


def cmd_init(feature_dir: Path, rebind: bool, attested_by: "str | None" = None, evidence: "str | None" = None) -> dict:
    plan = parse_plan(feature_dir / PLAN)
    profile = parse_profile(feature_dir / PROFILE)
    if profile["errors"]:
        raise Refused("PROFILE_INVALID", "; ".join(profile["errors"]))
    source = plan["front"].get("source")
    if not source or not plan["front"].get("source_sha256"):
        raise Refused("PLAN_INVALID", "plan front matter needs source and source_sha256; validate it with speckit-package-tasks")
    root = git_root(feature_dir)
    source_path = Path(source)
    if source_path.is_absolute():
        tasks_path, stored_tasks = source_path, str(source_path)
    else:
        tasks_path, stored_tasks = (root / source).resolve(), posixpath.normpath(source)
    if not tasks_path.is_file():
        raise Refused("PLAN_INVALID", f"plan source not found: {source}")
    if plan["front"]["source_sha256"] != sha256(tasks_path):
        raise Refused("SOURCE_CHANGED", "tasks.md changed after the plan was made; regenerate and revalidate the packages first")
    sources = {pid: pkg["source_tasks"] for pid, pkg in plan["packages"].items()}
    edges = {pid: {"blocked_by": list(pkg["blocked_by"]), "paths": list(pkg["paths"])} for pid, pkg in plan["packages"].items()}
    ledger = Ledger(feature_dir)
    attested = (attested_by or "").strip()
    proof = (evidence or "").strip()
    if ledger.path.exists():
        if not rebind:
            raise Refused("LEDGER_EXISTS", f"{ledger.path} already exists; use --rebind after changing the plan or profile")
        ledger.load()
        run = Run(feature_dir, ledger)
        uncertain = [o["op"] for o in run.ops.values() if o["status"] == "requested"]
        if uncertain:
            raise Refused("UNCERTAIN_OPERATIONS", f"reconcile before rebinding: {', '.join(uncertain)}")
        history = {o["package"] for o in run.ops.values()} | set(run.delivered)
        dropped = sorted(history - set(plan["packages"]))
        if dropped:
            raise Refused("REBIND_DROPS_HISTORY", f"the new plan drops packages with recorded history: {', '.join(dropped)}")
        before = run.bound.get("sources", {})
        moved = sorted(pid for pid in history if pid in before and before[pid] != sources.get(pid))
        if moved:
            raise Refused("REBIND_MOVES_HISTORY", f"packages with recorded history changed their source tasks: {', '.join(moved)}; "
                                                  "keep their ids and tasks stable or start a new ledger")
        # History checks run before the sibling validator so a moved package still reports REBIND_MOVES_HISTORY.
        previous_edges = run.bound.get("edges")
        if previous_edges is not None:
            lost = _loosened(previous_edges, edges, history)
            if lost and not (attested and proof):
                raise Refused("REBIND_LOOSENS", "rebind drops blockers or primary paths from packages with history: "
                               + "; ".join(lost) + "; pass --attested-by and --evidence to record that decision")
    elif rebind:
        raise Refused("LEDGER_NOT_FOUND", "nothing to rebind; run init")
    plan_validated, validator_warnings = package_validator_status(feature_dir / PLAN)
    warnings = list(profile["warnings"]) + validator_warnings
    record = {"type": "bound", "plan_sha256": sha256(feature_dir / PLAN), "profile_sha256": sha256(feature_dir / PROFILE),
              "tasks_path": stored_tasks, "tasks_sha256": sha256(tasks_path), "packages": list(plan["packages"]),
              "sources": sources, "edges": edges, "plan_validated": plan_validated,
              "settings": profile["settings"], "roles": profile["roles"], "warnings": warnings}
    if attested and proof:
        record["attested_by"] = attested
        record["evidence"] = proof
    if rebind:
        event = ledger.append(record)
    else:
        event = {"seq": 1, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
        draft = ledger.path.with_name(LEDGER + ".new")
        draft.write_bytes((json.dumps(event, sort_keys=True) + "\n").encode("utf-8"))
        try:
            os.link(draft, ledger.path)  # fails if another init won the race; never overwrites
        except FileExistsError:
            raise Refused("LEDGER_EXISTS", f"{ledger.path} already exists")
        finally:
            draft.unlink()
    return {"ok": True, "bound": event["seq"], "packages": list(plan["packages"]), "warnings": warnings,
            "plan_validated": plan_validated}


def require_evidence(run: Run, kind: str, args) -> dict:
    via = args.via
    if via == "user":
        # A person's answer when the system cannot tell (e.g. find unsupported): recorded as attested, never as a receipt.
        if kind not in ("accepted", "absent"):
            raise Refused("WRONG_OPERATION", "a user attestation can settle only whether an assignment exists (accepted/absent)")
        if not (args.attested_by or "").strip() or not (args.evidence or "").strip():
            raise Refused("ATTESTATION_REQUIRED", "--via user needs --attested-by and --evidence quoting the person's answer")
        return {"via": "user", "evidence": args.evidence.strip(), "attested_by": args.attested_by.strip()}
    allowed = VIA.get(kind)
    if allowed and via not in allowed:
        raise Refused("WRONG_OPERATION", f"{kind} evidence must come from {' or '.join(allowed)}, not {via}")
    status = op_status(run.profile, via)
    if status is None:
        raise Refused("UNKNOWN_CAPABILITY", f"operation {via} is not declared in {PROFILE}")
    if status == "unsupported":
        raise Refused("UNSUPPORTED_CAPABILITY", f"{via} is unsupported in {PROFILE}; no evidence can come from it. Escalate the decision to a human")
    if not (args.evidence or "").strip():
        raise Refused("EVIDENCE_REQUIRED", "--evidence must describe the external proof (receipt id, command output, URL)")
    if status == "human" and not (args.attested_by or "").strip():
        raise Refused("ATTESTATION_REQUIRED", f"{via} is performed by a human; pass --attested-by with who confirmed it")
    record = {"via": via, "evidence": args.evidence.strip()}
    if args.attested_by:
        record["attested_by"] = args.attested_by.strip()
    return record


def get_op(run: Run, key: str, *states: str) -> dict:
    op = run.ops.get(key)
    if op is None:
        raise Refused("UNKNOWN_OPERATION", f"no requested operation {key}")
    if states and op["status"] not in states:
        raise Refused("OPERATION_STATE", f"{key} is {op['status']}; expected {' or '.join(states)}")
    return op


def cmd_record(feature_dir: Path, args) -> dict:
    ledger = Ledger(feature_dir).load()
    run = Run(feature_dir, ledger)
    kind = args.command
    if kind == "request":
        halted = run.halt_reason()
        if halted is not None:
            raise Refused("LINE_STOPPED", f"the line is halted: {halted}")
        drift = run.drift()
        if drift:
            raise Refused("PLAN_DRIFT", f"{', '.join(drift)} changed since binding; review the change and run init --rebind")
        uncertain = [o["op"] for o in run.open_ops(args.package) if o["status"] == "requested"]
        if uncertain:
            raise Refused("UNCERTAIN_OPERATION", f"{uncertain[0]} has no confirmed outcome; reconcile it (find/observe) instead of requesting again")
        if run.open_ops(args.package):
            raise Refused("DUPLICATE_EXECUTION", f"{args.package} already has an active operation: {run.open_ops(args.package)[0]['op']}")
        reason = run.eligibility(args.package, args.purpose)
        if reason:
            raise Refused("NOT_ELIGIBLE", reason)
        ops = run.package_ops(args.package)
        spent = (sum(1 for o in ops if o["purpose"] == "implement" and o["outcome"] == "failed") if args.purpose == "implement"
                 else sum(1 for o in ops if o["purpose"] == "fix" and o["status"] == "settled") if args.purpose == "fix" else 0)
        decision = {}
        if args.purpose in CAPS and spent >= CAPS[args.purpose]:
            if not (args.attested_by or "").strip() or not (args.evidence or "").strip():
                raise Refused("ATTEMPT_CAP", f"{args.package} already used {spent} {args.purpose} attempts; bring the user a decision brief, "
                                             "then pass --attested-by and --evidence with their decision")
            decision = {"decision_by": args.attested_by.strip(), "decision": args.evidence.strip()}
        attempt = 1 + sum(1 for o in run.ops.values() if o["package"] == args.package and o["purpose"] == args.purpose)
        op = f"{args.package}:{args.purpose}:{attempt}"
        pinned = run.current_head(args.package) if args.purpose != "implement" else None
        ledger.append({"type": "request", "op": op, "package": args.package, "purpose": args.purpose, "pinned_head": pinned, **decision})
        return {"ok": True, "op": op, "pinned_head": pinned}
    if kind == "accepted":
        op = get_op(run, args.op, "requested")
        args.assignment = (args.assignment or "").strip()
        if not args.assignment:
            raise Refused("ASSIGNMENT_REQUIRED", "--assignment must be the executor-issued reference")
        evidence = require_evidence(run, kind, args)
        if op["purpose"] == "review":
            authors = {o["assignment"] for o in run.package_ops(op["package"]) if o["purpose"] in ("implement", "fix") and o["assignment"]}
            if args.assignment in authors:
                raise Refused("REVIEW_NOT_INDEPENDENT", "the reviewer assignment must differ from every implementation assignment")
        holders = [o for o in run.ops.values() if o["assignment"] == args.assignment]
        resumable = op["purpose"] == "fix" and all(
            o["package"] == op["package"] and o["purpose"] in ("implement", "fix") and o["status"] == "settled" for o in holders)
        if holders and not resumable:
            raise Refused("DUPLICATE_ASSIGNMENT", f"assignment {args.assignment} already belongs to {holders[0]['op']}; "
                                                  "only a fix may resume this package's settled implementer")
        ledger.append({"type": "accepted", "op": args.op, "assignment": args.assignment, **evidence})
        return {"ok": True, "op": args.op, "status": "accepted"}
    if kind == "absent":
        get_op(run, args.op, "requested")
        evidence = require_evidence(run, kind, args)
        ledger.append({"type": "absent", "op": args.op, **evidence})
        return {"ok": True, "op": args.op, "status": "absent"}
    if kind == "completed":
        op = get_op(run, args.op, "accepted")
        if op["purpose"] == "review" and args.outcome == "succeeded":
            raise Refused("USE_REVIEWED", "a successful review is recorded with the reviewed command")
        if op["purpose"] != "review" and args.outcome == "succeeded" and not args.head:
            raise Refused("HEAD_REQUIRED", "a successful implementation or fix must report the head (commit) it produced")
        evidence = require_evidence(run, kind, args)
        record = {"type": "completed", "op": args.op, "outcome": args.outcome, **evidence}
        if args.head:
            record["head"] = args.head
        if args.change:
            record["change"] = args.change
        ledger.append(record)
        return {"ok": True, "op": args.op, "outcome": args.outcome}
    if kind == "reviewed":
        op = get_op(run, args.op, "accepted")
        if op["purpose"] != "review":
            raise Refused("NOT_A_REVIEW", f"{args.op} is a {op['purpose']} operation")
        if args.head != op["pinned_head"]:
            raise Refused("STALE_REVIEW", f"review covered {args.head} but was pinned to {op['pinned_head']}; request a fresh review")
        if run.current_head(op["package"]) != op["pinned_head"]:
            raise Refused("STALE_REVIEW", "the implementation changed after this review was requested; request a fresh review")
        evidence = require_evidence(run, kind, args)
        ledger.append({"type": "reviewed", "op": args.op, "head": args.head, "verdict": args.verdict, **evidence})
        return {"ok": True, "op": args.op, "verdict": args.verdict}
    if kind == "delivered":
        if args.package not in run.plan["packages"]:
            raise Refused("UNKNOWN_PACKAGE", f"unknown package {args.package}")
        if args.package in run.delivered:
            raise Refused("ALREADY_DELIVERED", f"{args.package} delivery is already recorded")
        if args.target != run.settings.get("base_branch"):
            raise Refused("WRONG_TARGET", f"delivery target {args.target} is not the expected {run.settings.get('base_branch')}")
        evidence = require_evidence(run, kind, args)
        attested = bool((args.attested_by or "").strip()) and bool((args.evidence or "").strip())
        pending = [blocker for blocker in run.plan["packages"][args.package]["blocked_by"] if blocker not in run.delivered]
        if pending:
            raise Refused("BLOCKERS_UNDELIVERED", f"{args.package} is still blocked by {', '.join(pending)}")
        if args.head != run.current_head(args.package):
            raise Refused("WRONG_HEAD", f"delivery head {args.head} is not {args.package}'s current head {run.current_head(args.package)}")
        state = run.state(args.package)
        if run.open_ops(args.package) or (attested and state not in ATTESTED_DELIVERY) or (not attested and state != "ready-to-deliver"):
            code = "NOT_DELIVERABLE" if attested else "REVIEW_REQUIRED"
            raise Refused(code, f"{args.package} is {state}; delivery needs ready-to-deliver"
                                + (" or an attested external merge of the current head" if not attested else
                                   " (attested merge allows needs-review, changes-requested or ready-to-deliver)"))
        record = {"type": "delivered", "package": args.package, "head": args.head, "target": args.target, **evidence}
        if args.change:
            record["change"] = args.change
        ledger.append(record)
        gap = run.review_on(args.package, args.head)
        return {"ok": True, "package": args.package,
                "warning": None if gap and gap["verdict"] == "pass" else "delivered head has no passing review; report the evidence gap"}
    if kind == "resource":
        current = run.resources.get(args.ref)
        if args.package and args.package not in run.plan["packages"]:
            raise Refused("UNKNOWN_PACKAGE", f"unknown package {args.package}")
        if args.action == "created":
            if current and current["state"] != "released":
                raise Refused("RESOURCE_EXISTS", f"{args.ref} is already recorded ({current['state']})")
            if args.owner not in ("coordinator", "user", "unknown"):
                raise Refused("OWNER_REQUIRED", "--owner must be coordinator, user or unknown")
            if args.owner == "coordinator" and not args.package:
                raise Refused("PACKAGE_REQUIRED", "a coordinator-owned resource must name the package it serves (--package)")
            evidence = require_evidence(run, "created", args)
            ledger.append({"type": "resource", "ref": args.ref, "action": "created", "owner": args.owner, "package": args.package, **evidence})
            return {"ok": True, "ref": args.ref, "state": "created"}
        allowed_from = ("created",) if args.action == "retained" else ("created", "retained")
        if not current or current["state"] not in allowed_from:
            raise Refused("RESOURCE_STATE", f"{args.ref} is {current['state'] if current else 'unknown'}; cannot mark it {args.action}")
        holder = current.get("package")
        if args.action == "released" and holder:
            state = run.state(holder)
            if state not in ("delivered", "failed", "ready", "blocked", "not-ready"):
                raise Refused("RESOURCE_IN_USE", f"{args.ref} serves {holder}, which is {state}; release it after delivery or retain it")
        if args.action == "released":
            if current.get("owner") != "coordinator":
                raise Refused("OWNERSHIP_UNPROVEN", f"{args.ref} is owned by {current.get('owner')}; only coordinator-owned resources may be released")
            evidence = require_evidence(run, "released", args)
        else:
            if not (args.evidence or "").strip():
                raise Refused("EVIDENCE_REQUIRED", "--evidence must give the retention reason")
            evidence = {"evidence": args.evidence.strip()}
        ledger.append({"type": "resource", "ref": args.ref, "action": args.action, **evidence})
        return {"ok": True, "ref": args.ref, "state": args.action}
    raise Refused("USAGE", f"unknown command {kind}")


def cmd_halt(feature_dir: Path, reason: str) -> dict:
    reason = (reason or "").strip()
    if not reason:
        raise Refused("REASON_REQUIRED", "halt needs --reason")
    ledger = Ledger(feature_dir).load()
    ledger.append({"type": "halt", "reason": reason})
    return {"ok": True, "halted": True, "halt_reason": reason}


def cmd_resume(feature_dir: Path, attested_by: str, evidence: str) -> dict:
    attested, proof = (attested_by or "").strip(), (evidence or "").strip()
    if not attested or not proof:
        raise Refused("ATTESTATION_REQUIRED", "resume needs --attested-by and --evidence quoting the decision to restart")
    ledger = Ledger(feature_dir).load()
    run = Run(feature_dir, ledger)
    if run.halt_reason() is None:
        raise Refused("NOT_HALTED", "the line is not halted")
    ledger.append({"type": "resume", "attested_by": attested, "evidence": proof})
    return {"ok": True, "halted": False}


def cmd_check_completion(feature_dir: Path, package: str, worktree: str, head: str, op: str) -> dict:
    """Read-only. Exit is the caller's; this raises Refused or returns ok."""
    run = Run(feature_dir, Ledger(feature_dir).load())
    pkg = run.plan["packages"].get(package)
    if pkg is None:
        raise Refused("UNKNOWN_PACKAGE", f"unknown package {package}")
    owned = ownership_write_paths(pkg)
    if not owned:
        raise Refused("OWNERSHIP_UNPARSEABLE", f"{package} has no Ownership write-paths")
    tree = Path(worktree)
    rev = git_text(tree, "rev-parse", "HEAD")
    actual = rev.stdout.strip()
    if rev.returncode != 0 or actual != head:
        raise Refused("HEAD_MISMATCH", f"worktree HEAD is {actual or '(unreadable)'}, not {head}")
    status = git_text(tree, "status", "--porcelain")
    if status.returncode != 0:
        raise Refused("DIRTY_WORKTREE", f"git status failed: {(status.stderr or '').strip()}")
    if status.stdout.strip():
        raise Refused("DIRTY_WORKTREE", "worktree has uncommitted changes")
    message = git_text(tree, "log", "-1", "--format=%B", head)
    trailer = f"Orchestration-Op: {op}"
    if message.returncode != 0 or trailer not in message.stdout.splitlines():
        raise Refused("TRAILER_MISSING", f"commit {head} has no trailer line {trailer}")
    base = run.settings.get("base_branch")
    diff = git_text(tree, "diff", "--name-only", f"{base}...HEAD")
    if diff.returncode != 0:
        raise Refused("PATH_OUTSIDE_OWNERSHIP", f"could not diff {base}...HEAD: {(diff.stderr or '').strip()}")
    names = [line.strip() for line in diff.stdout.splitlines() if line.strip()]
    outside = [name for name in names if not any(path_inside(name, path) for path in owned)]
    if outside:
        raise Refused("PATH_OUTSIDE_OWNERSHIP", f"outside ownership: {', '.join(outside)}")
    return {"ok": True, "package": package, "head": head, "changed": names}


def render_status(data: dict) -> str:
    out = []
    if data.get("halted"):
        out.append(f"HALTED: {data.get('halt_reason')}")
    if data.get("plan_validated") is False:
        out.append("WARN: plan_validated is false")
    for row in data["packages"]:
        extra = []
        if row["head"]:
            extra.append(f"head {row['head'][:12]}")
        if row["review_gap"]:
            extra.append("REVIEW GAP")
        if row["conflicts_with"]:
            extra.append(f"shares paths with {', '.join(row['conflicts_with'])}")
        out.append(f"{row['package']:<10} {row['state']:<20} {row['title']}" + (f"  [{'; '.join(extra)}]" if extra else ""))
    for op in data["open_operations"]:
        out.append(f"OPEN {op['op']} {op['status']}" + (f" assignment={op['assignment']}" if op["assignment"] else " (acceptance unconfirmed)"))
    for res in data["resources"]:
        out.append(f"RESOURCE {res['ref']} {res['state']} owner={res.get('owner')}")
    for name in data["drift"]:
        out.append(f"DRIFT: {name} changed since binding")
    out += [f"WARN: {w}" for w in data["warnings"]]
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--feature-dir", default=".", help="directory holding tasks-packages.md and orchestration.md")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check-profile").add_argument("path")
    init = sub.add_parser("init")
    init.add_argument("--rebind", action="store_true")
    init.add_argument("--attested-by", help="who approved a rebind that drops a blocker or primary path")
    init.add_argument("--evidence", help="that decision, required with --attested-by on a loosening rebind")
    for name in ("status", "next", "gate"):
        sub.add_parser(name)
    sub.add_parser("halt").add_argument("--reason", required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("--attested-by", required=True)
    resume.add_argument("--evidence", required=True)
    check = sub.add_parser("check-completion")
    check.add_argument("--package", required=True)
    check.add_argument("--worktree", required=True)
    check.add_argument("--head", required=True)
    check.add_argument("--op", required=True)

    def evidence(p):
        p.add_argument("--via", required=True)
        p.add_argument("--evidence", required=True)
        p.add_argument("--attested-by")
        return p

    p = sub.add_parser("request")
    p.add_argument("package")
    p.add_argument("purpose", choices=PURPOSES)
    p.add_argument("--attested-by", help="who decided to continue past an attempt cap")
    p.add_argument("--evidence", help="the user's decision when continuing past an attempt cap")
    p = evidence(sub.add_parser("accepted"))
    p.add_argument("op")
    p.add_argument("--assignment", required=True)
    evidence(sub.add_parser("absent")).add_argument("op")
    p = evidence(sub.add_parser("completed"))
    p.add_argument("op")
    p.add_argument("--outcome", required=True, choices=("succeeded", "failed"))
    p.add_argument("--head")
    p.add_argument("--change")
    p = evidence(sub.add_parser("reviewed"))
    p.add_argument("op")
    p.add_argument("--head", required=True)
    p.add_argument("--verdict", required=True, choices=("pass", "changes-requested"))
    p = evidence(sub.add_parser("delivered"))
    p.add_argument("package")
    p.add_argument("--head", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--change")
    p = sub.add_parser("resource")
    p.add_argument("ref")
    p.add_argument("--action", required=True, choices=("created", "released", "retained"))
    p.add_argument("--owner")
    p.add_argument("--package")
    p.add_argument("--via", default="")
    p.add_argument("--evidence", default="")
    p.add_argument("--attested-by")
    args = parser.parse_args(argv)
    feature_dir = Path(args.feature_dir)

    def emit(data, text=None):
        print(json.dumps(data, indent=2) if args.json or text is None else text)

    try:
        if args.command == "check-profile":
            profile = parse_profile(Path(args.path))
            ok = not profile["errors"]
            emit({"ok": ok, "errors": profile["errors"], "warnings": profile["warnings"], "settings": profile["settings"]},
                 "\n".join([f"ERROR: {e}" for e in profile["errors"]] + [f"WARN: {w}" for w in profile["warnings"]] + ["PASS" if ok else "FAIL"]))
            return 0 if ok else 1
        if args.command == "init":
            emit(cmd_init(feature_dir, args.rebind, args.attested_by, args.evidence))
            return 0
        if args.command == "halt":
            emit(cmd_halt(feature_dir, args.reason))
            return 0
        if args.command == "resume":
            emit(cmd_resume(feature_dir, args.attested_by, args.evidence))
            return 0
        if args.command == "check-completion":
            emit(cmd_check_completion(feature_dir, args.package, args.worktree, args.head, args.op))
            return 0
        if args.command in ("status", "next", "gate"):
            run = Run(feature_dir, Ledger(feature_dir).load())
            if args.command == "status":
                data = run.status()
                emit(data, render_status(data))
                return 0
            if args.command == "next":
                emit(run.next_actions())
                return 0
            data = run.gate()
            emit(data, "\n".join([f"BLOCKED: {b}" for b in data["blockers"]] + [f"WARN: {w}" for w in data["warnings"]] + ["PASS" if data["ok"] else "FAIL"]))
            return 0 if data["ok"] else 1
        emit(cmd_record(feature_dir, args))
        return 0
    except UnicodeDecodeError as error:
        print(json.dumps({"ok": False, "code": "ENCODING_INVALID", "message": str(error)}) if args.json else f"REFUSED ENCODING_INVALID: {error}", file=sys.stderr)
        return 2
    except Refused as error:
        print(json.dumps({"ok": False, "code": error.code, "message": str(error)}) if args.json else f"REFUSED {error.code}: {error}", file=sys.stderr)
        return 2 if error.code in ("PLAN_NOT_FOUND", "PROFILE_NOT_FOUND", "LEDGER_NOT_FOUND", "LEDGER_CORRUPT", "FRONT_MATTER_INVALID") else 1


if __name__ == "__main__":
    sys.exit(main())
