# Credentials and secret delivery

Read when operator authentication, registration or selector credentials are missing. Refresh [runner API permissions](https://docs.github.com/en/rest/actions/self-hosted-runners) and [fine-grained PAT guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) for the actual GitHub host. Never install the operator's personal login/PAT in the runtime account.

| Credential | Purpose and boundary |
| --- | --- |
| Operator authentication | Existing GitHub connector or authenticated `gh` on the administrator workstation. Repository registration-token creation needs admin access; fine-grained **Administration: write**. Creating secrets/variables requires its own capability. |
| Registration token | Short-lived token for `config.sh`/`config.cmd`, obtained just before use from repository Settings → Actions → Runners or POST `/repos/{owner}/{repo}/actions/runners/registration-token`. Currently expires in one hour. It does not provide ongoing workflow discovery. |
| `RUNNER_READ_TOKEN` | Finite-expiry fine-grained PAT, resource owner and selected repository only, **Administration: read**. Used solely by the hosted workflow selector; it cannot register or administer the repo. Ordinary workflow `GITHUB_TOKEN` lacks this Administration capability. |

## Missing operator access

Inspect authentication for the resolved host without printing tokens. If neither CLI nor connector access exists, install `gh` from its [official installation instructions](https://cli.github.com/) on the operator workstation or use the authenticated browser. Use interactive `gh auth login --hostname ACTUAL_HOST` there, with the required organization/SSO approval. Ask for the exact missing capability rather than requesting a broad PAT. Authenticated identity still needs repository authorization.

## Missing selector PAT/secret

In GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens, choose the actual resource owner, a finite expiration, **Only select repositories** and the intended repository, then repository Administration **Read-only**. Complete any organization approval. Put its value directly into repository Settings → Secrets and variables → Actions → New repository secret named `RUNNER_READ_TOKEN`, or let the user enter it into `gh secret set RUNNER_READ_TOKEN --repo ACTUAL_REPOSITORY` privately. The user never pastes it into chat. List/read secret names only; record expiry/rotation responsibility without its value. Configure non-secret variables using [CI](ci.md). Expired/missing/denied discovery credentials use the configured hosted fallback, without silently widening permissions.

## Registration input and temporary files

Prefer private interactive input at the target's official configuration prompt. Enter the freshly obtained token locally; omit `--token` from recorded command lines. Disable shell tracing and keep tokens out of logs, history, screenshots, tracked files, PRs and clipboard payloads. Confirm the installed version's prompt handling before using another mechanism.

If automation needs a file, prepare a secret-safe operator-side script that redirects the token endpoint's filtered response directly into an exclusively created file inside a private task directory (0700, file 0600). Check API success, valid nonempty token/expiry and target identity before transfer. Transfer only through authenticated encrypted access into a private directory owned by the intended runtime account. Fail on every transfer/permission error. Do not feed a token to an unverified script or print it; consume through a mechanism supported by that runner version. Remove both temporary copies after successful registration and verify removal without reading contents. On interruption, inspect registration first and restrict retained files; expire/remove residual tokens rather than blindly registering twice. Generate near use rather than storing for later.

Administrator passwords and service-account passwords stay in the user's terminal/OS UI. Preserve interactive sudo authentication; prepare concrete scripts/data before asking for privileged execution. Never change sudoers or grant runner sudo to make CI provisioning work.
