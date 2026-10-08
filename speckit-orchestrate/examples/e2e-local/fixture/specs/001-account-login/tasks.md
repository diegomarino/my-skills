# Tasks: Account login

**Input**: Design documents from `specs/001-account-login/`

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create the `src/accounts/__init__.py` package skeleton
- [ ] T002 [P] Configure pytest discovery in `pyproject.toml`

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T003 [RED] Write failing tests for the in-memory user store in `tests/test_store.py`
- [ ] T004 [GREEN] Implement the in-memory user store in `src/accounts/store.py`
- [ ] T005 Add the password hashing helper in `src/accounts/hashing.py` (depends on T004)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

## Phase 3: User Story 1 - Log in with a password (Priority: P1) 🎯 MVP

- [ ] T006 [US1] [RED] Write failing login tests (valid password, wrong password, unknown user) in `tests/test_login.py`
- [ ] T007 [US1] [GREEN] Implement `login(username, password)` in `src/accounts/login.py`
- [ ] T008 [US1] Add the `login` command to `src/accounts/cli.py`

## Phase 4: User Story 2 - View my profile (Priority: P2)

- [ ] T009 [US2] [RED] Write failing profile tests (own profile, missing profile) in `tests/test_profile.py`
- [ ] T010 [US2] [GREEN] Implement `get_profile(username)` in `src/accounts/profile.py`
- [ ] T011 [US2] Add the `profile` command to `src/accounts/cli.py`

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T012 [P] Document the login and profile commands in `README.md`
- [ ] T013 Run the full test suite and fix any failures

## Dependencies & Execution Order

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3+)**: Depend on Foundational; US1 and US2 are independent
- **Polish (Phase 5)**: Depends on all user stories
