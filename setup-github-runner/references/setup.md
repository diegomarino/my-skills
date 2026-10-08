# Prepare and register an instance

Read when installation or registration is authorized, after [discovery](discovery.md), [credentials](credentials.md) and account preparation in [platforms](platforms.md). Start with no assumptions about installed tools, accounts, runner files or access. Prefer verified existing resources; create missing prerequisites before dependent steps. Use one separate directory and repository registration per repository; sharing a runtime account does not isolate instances.

## Official release and preparation

Use the current [runner setup UI](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners) or [official releases](https://github.com/actions/runner/releases) to select the supported target OS/architecture and version. On the operator workstation, an authenticated `gh` can list official asset metadata without downloading binaries:

```bash
gh api repos/actions/runner/releases/latest \
  --jq '{tag_name,html_url,assets:[.assets[]|{name,browser_download_url,digest,size}]}'
```

Use the matching asset's official SHA256 digest (when published) or that release's authoritative checksum table. If no authoritative checksum is available, stop before execution. Record URL, version, OS/architecture and digest. Download using the setup UI commands, `curl --fail --location --proto '=https' --proto-redir '=https'` on the selected macOS/Linux host. Confirm HTTPS official download provenance and transfer integrity; do not substitute a checksum calculated only from the downloaded file as its authority.

Provision prerequisites if missing: download/SSH utilities, unpacking tools, host dependencies and the project's real toolchain, under administrator scope. Linux runner `config.sh` diagnoses runtime dependencies; inspect the verified distribution's `bin/installdependencies.sh` and prepare an authorized administrator provisioning step if needed. Keep runtime account nonprivileged. Python helpers require **Python 3.9+**: discover an existing interpreter or provision one from the platform's official package/download procedure outside CI. The hosted selector uses its hosted interpreter; it does not depend on Python already being installed on the target.

Prepare a runtime-owned parent outside the checkout, with no conflicting directories, symlinks or unsafe ACLs. Transfer the verified archive and bundled helper into a private task staging directory. Run this helper **as the dedicated runtime account**, supplying actual discovered values:

```bash
python3 scripts/prepare_runner.py prepare --archive "$ARCHIVE" \
  --sha256 "$OFFICIAL_SHA256" --version "$RUNNER_VERSION" \
  --directory "$INSTANCE_DIR" --expected-user "$RUNNER_ACCOUNT"
```

[prepare_runner.py](../scripts/prepare_runner.py) checks SHA256, archive paths/entry points and account/path guards, reserves a new directory exclusively, and records `.preparation.json`. It accepts the official Node layout's contained relative symlinks, creating links after regular files. It refuses absolute/escaping/dangling/cyclic links, writes through linked parent directories, hardlinks, special entries, duplicate paths, existing instances and archives over 3 GiB expanded/100,000 entries. It does not download, create accounts, grant privileges or establish that the supplied digest is authoritative.

`--archive` is the downloaded official macOS/Linux tar archive; `--sha256` accepts 64 hex characters or `sha256:` followed by them; `--version` records the selected release; `--expected-user` must match the actual OS runtime account; `--directory` is a new absolute resolved path whose parent already belongs to that account. On macOS, `/tmp` and `/var` aliases resolve under `/private`; use the resolved path printed by a refusal. Success prints a JSON receipt; failures print a reason to stderr and exit nonzero. Run `prepare --help` or `inspect --help` for flags. Inspection accepts runner state with a UTF-8 BOM and prints identity/preparation only, never credentials.

If extraction is interrupted, `inspect --directory "$INSTANCE_DIR"` reports `incomplete` and the next action. Preserve the directory and receipt while diagnosing the complete error. The simplest retry uses a different new instance directory with the same verified archive; do not register the partial instance. If the original path is required, first verify its resolved path/owner, incomplete receipt, absence of `.runner` and `.credentials`, and absence of any service or process using it. Under the user's scoped recovery authorization, rename only that confirmed partial instance to a collision-free sibling backup, then prepare anew at the original path. Retain the backup until acceptance; never recursively delete or overwrite it as incidental cleanup. Completion: one fully prepared instance with a `prepared` receipt, and any prior partial instance preserved.

## Register

As that account on macOS/Linux, run the selected distribution's `config.sh`. Use the actual repository URL and a stable unique name; supply a verified unique custom routing label while retaining default labels. Inspect current `--help`; omit `--replace`. Choose the instance work directory explicitly or accept the documented default. Let the user enter the token privately when prompted. Check registration identity against GitHub before installing its service. A name collision or partial registration requires inspection; preserve unrelated instances.

After registration, prepare the [platform service](platforms.md), [real CI integration](ci.md) and [independent verification](verification.md). Service success does not imply CI success.

## Persistent toolchain

Verify actual tools as the runtime account using the service's explicit environment, rather than the administrator's shell. Provision missing tools outside CI; never grant administrator rights to the runner to satisfy an installer. On self-hosted macOS, [setup-python distributions can require a fixed tool-cache path](https://github.com/actions/setup-python/blob/main/docs/advanced-usage.md#macos). Writable cache is not proof that a package installer is privilege-free. Prefer a compatible verified existing Python executable when appropriate, and make intentional hosted/local version differences explicit; validate the same project checks in job-owned environments under `RUNNER_TEMP`. No specific Python version or Homebrew location is a default here.

For Xcode/iOS, verify SDK/runtime and signing/keychain access separately. Use actual simulator UUIDs where names are ambiguous, scoped to that host/account; keep DerivedData/build products job-owned. Linux container checks may need a separate hosted Linux job. Avoid collisions or broad deletion of persistent checkouts/caches.
