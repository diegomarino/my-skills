---
feature: "001"
source: "specs/001-account-login/tasks.md"
source_sha256: "d281487888cac7ead24edde4e7ee941697abfd846222f5532396008e4f2a37a6"
---

# Work packages: Account login

## Summary

Four packages. `F001-P01` (setup and foundation) gates everything. The two user stories, `F001-P02` (login) and `F001-P03` (profile), are independent branches after it. `F001-P04` (polish) waits on both stories, as tasks.md requires. The two stories share `src/accounts/cli.py`, so they are a scheduling conflict rather than a dependency: run them in either order, never at the same time.

## Scheduling conflicts

- `F001-P02` / `F001-P03`: `src/accounts/cli.py` — both stories add a subcommand to the same CLI module

## F001-P01 — Account foundation

- [ ] F001-P01 Account foundation

**Ready**: yes

**Source tasks**:
- `T001` Create the `src/accounts/__init__.py` package skeleton
- `T002` [P] Configure pytest discovery in `pyproject.toml`
- `T003` [RED] Write failing tests for the in-memory user store in `tests/test_store.py`
- `T004` [GREEN] Implement the in-memory user store in `src/accounts/store.py`
- `T005` Add the password hashing helper in `src/accounts/hashing.py` (depends on T004)

**Blocked by**: None

**Objective**: An importable `accounts` package with a tested user store and password hashing helper that both user stories build on.

**Scope**:
- Package skeleton and pytest configuration.
- In-memory user store (create, look up by username) driven by its failing tests first.
- Password hashing helper used by the store.

**Constraints**:
- Standard library only; no persistence beyond memory.

**Ownership**:
- Owns `src/accounts/__init__.py`, `src/accounts/store.py`, `src/accounts/hashing.py`, `tests/test_store.py`, `pyproject.toml`.
- Does not touch any CLI or story module.

**Primary paths**:
- `src/accounts/__init__.py`
- `src/accounts/store.py`
- `src/accounts/hashing.py`
- `tests/test_store.py`
- `pyproject.toml`

**Acceptance criteria**:
- `tests/test_store.py` failed before the store existed and passes now.
- A stored password is never kept in plain text.

**Verification**:
- `python -m pytest tests/test_store.py`

**Handoff**:
- Stories may import `accounts.store` and `accounts.hashing`.

## F001-P02 — Password login

- [ ] F001-P02 [US1] Password login

**Ready**: yes

**Source tasks**:
- `T006` [US1] [RED] Write failing login tests (valid password, wrong password, unknown user) in `tests/test_login.py`
- `T007` [US1] [GREEN] Implement `login(username, password)` in `src/accounts/login.py`
- `T008` [US1] Add the `login` command to `src/accounts/cli.py`

**Blocked by**:
- `F001-P01`

**Objective**: A user can log in with a password from the CLI.

**Scope**:
- Failing login tests first, then `login()`, then the `login` CLI command.

**Constraints**:
- Must use `accounts.hashing` for password checks.

**Ownership**:
- Owns `src/accounts/login.py` and `tests/test_login.py`; adds only the login command to `src/accounts/cli.py`.

**Primary paths**:
- `src/accounts/login.py`
- `src/accounts/cli.py`
- `tests/test_login.py`

**Acceptance criteria**:
- Valid credentials succeed; a wrong password and an unknown user fail with distinct errors.
- `main(["login", username, password], store)` in `src/accounts/cli.py` returns 0 for valid credentials and non-zero otherwise, tested with an injected store (the store is memory-only, so a fresh process has no users); run the command as `python -m accounts.cli login`.

**Verification**:
- `python -m pytest tests/test_login.py`

**Handoff**:
- Terminal deliverable for User Story 1.

## F001-P03 — Profile view

- [ ] F001-P03 [US2] Profile view

**Ready**: yes

**Source tasks**:
- `T009` [US2] [RED] Write failing profile tests (own profile, missing profile) in `tests/test_profile.py`
- `T010` [US2] [GREEN] Implement `get_profile(username)` in `src/accounts/profile.py`
- `T011` [US2] Add the `profile` command to `src/accounts/cli.py`

**Blocked by**:
- `F001-P01`

**Objective**: A user can view their profile from the CLI.

**Scope**:
- Failing profile tests first, then `get_profile()`, then the `profile` CLI command.

**Constraints**: None

**Ownership**:
- Owns `src/accounts/profile.py` and `tests/test_profile.py`; adds only the profile command to `src/accounts/cli.py`.

**Primary paths**:
- `src/accounts/profile.py`
- `src/accounts/cli.py`
- `tests/test_profile.py`

**Acceptance criteria**:
- An existing user's profile is returned; a missing profile reports a not-found error.

**Verification**:
- `python -m pytest tests/test_profile.py`

**Handoff**:
- Terminal deliverable for User Story 2.

## F001-P04 — Documentation and full-suite pass

- [ ] F001-P04 Documentation and full-suite pass

**Ready**: yes

**Source tasks**:
- `T012` [P] Document the login and profile commands in `README.md`
- `T013` Run the full test suite and fix any failures

**Blocked by**:
- `F001-P02`
- `F001-P03`

**Size justification**: the two polish tasks close the feature and neither stands alone.

**Objective**: Users can find both commands documented, and the whole suite passes.

**Scope**:
- README usage section for `login` and `profile`; a full-suite run with fixes. Two tasks are kept together because both close the feature and neither stands alone.

**Constraints**:
- Fixes stay within files already owned by earlier packages' deliverables.

**Ownership**:
- Owns `README.md`.

**Primary paths**:
- `README.md`

**Acceptance criteria**:
- README shows one working example for each command.
- `python -m pytest` passes.

**Verification**:
- `python -m pytest`

**Handoff**:
- Terminal deliverable for the feature.
