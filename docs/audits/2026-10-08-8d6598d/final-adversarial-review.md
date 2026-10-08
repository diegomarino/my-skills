# Final adversarial review: setup-github-runner

## Verdict

**SHIP the current skill content. No actionable findings identified.**

Independent final review covers the skill and its supporting resources, not an installed runner or proven live deployment. Deferred and dropped audit recommendations were not revived as generic requirements.

## Scope and source integrity

The reviewer read every shipped file in `setup-github-runner/**` fully: entrypoint, Codex metadata, README, six references, four helpers, workflow template, four test modules and behavioral scenarios. The introduced root README integration was inspected; other skills were outside scope.

Historical practical triage and fixes reports supplied context, with claims checked against current code. All 20 source files matched the parent-recorded SHA-256 manifest `/private/tmp/setup-github-runner-final-review-snapshot.json` after review; no snapshot drift occurred. Existing bytecode was excluded from shipped-source coverage.

## Adversarial checks

- Explicit-only invocation is present in both client controls and the entrypoint. Client-specific compatibility caveats are stated.
- Empty-start instructions establish connectivity, dedicated account, toolchain, credentials, registration, services and CI bootstrap without treating inaccessible evidence as absence.
- Preparation supports contained official Node symlinks while refusing escaping links, linked parents, hardlinks, collisions and reused instance directories.
- Interrupted extraction remains inspectable with scoped, preservation-first recovery.
- Credentials remain separated by purpose; registration and selector permissions are not interchangeable.
- Persistent runners require a dedicated standard account without claiming account separation is a sandbox.
- Linux privileged installation uses verified initial resources; subsequent management uses an independently verified systemd unit.
- macOS GUI-session dependence, root-level runsvc entry-point preparation, target plist staging, `.path` precedence and LaunchAgent conversion boundaries agree across instructions and generated plan.
- SSH rendering preserves both shell boundaries and does not execute commands.
- The trusted selector enforces byte-exact refs, verifies runner labels/state and avoids API calls on forced, untrusted and missing-configuration paths.
- Hosted-label collision preflight includes the PAT-bearing selector; the allowlist does not claim to guarantee collision absence.
- Empty-repository bootstrap supplies the trusted helper before hosted checks and accounts for default-branch dispatch availability.
- Preferred and forced-hosted acceptance runs are sequential on the same final candidate and require terminal evidence.
- The failing workflow placeholder prevents routing-only success from masquerading as product acceptance.
- macOS/Linux target scope is consistent; hosted Windows choices do not imply Windows provisioning support.
- Rename and catalog links consistently use `setup-github-runner`.

## Checks actually run by the reviewer

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s setup-github-runner/tests -v`: 35 tests passed.
- `actionlint setup-github-runner/assets/ci.yml`: passed.
- SHA-256 source comparison: 20/20 unchanged.
- Read-only Git diff/status inspection.

No source edits or Git mutations were performed by the reviewer.

## Untested boundaries

No live registration, credential provisioning, SSH, account creation, native service installation/conversion, CI dispatch or reboot was performed. Client installation/activation, Linux release extraction and live production runner transitions were not independently exercised during this review.

Operational safety still depends on the documented real-host/account/trust/inventory gates. Label inventory is not continuously enforced; a selected job does not automatically migrate when its runner becomes unavailable.
