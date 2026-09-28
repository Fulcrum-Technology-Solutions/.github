# Fulcrum Shared Checks

Reusable GitHub Actions checks for Fulcrum repositories. Select checks according
to the repository's workload using the [repository profiles](docs/repository-profiles.md).
Documentation, skills, infrastructure, libraries, and applications can share this
library without adopting the Internal Applications (IA) development process.

## Available workflows

| Workflow | Behavior | Applicable workloads |
|---|---|---|
| `node-quality.yml` | One install for lint, optional types/tests, build and dependency audit | npm applications |
| `secrets-scan.yml` | TruffleHog scan for verified committed credentials | All profiles |
| `build.yml` | `npm ci` and `npm run build` | npm projects with a build script |
| `lint.yml` | `npm ci` and `npm run lint` | npm projects with a lint script |
| `dependency-audit.yml` | `npm audit`, default threshold `high` | npm projects with a lockfile |
| `semgrep.yml` | Static analysis with a selected rule profile | Supported source languages, with additional app-specific rules when selected |

The npm workflows are deliberately npm-specific. They do not provide universal
build, test, or dependency coverage. Add appropriate language-specific checks
for other stacks. A verified-secret scan is also not proof that no secret exists.

### Consolidated npm checks

Prefer `node-quality.yml` for applications that need lint and build. It performs
one strict `npm ci` (also checking lockfile consistency), then lint, optional
`typecheck`/`tests`, and build. Set those boolean inputs explicitly when the app
provides the scripts. `working-directory` supports monorepos. The older individual
workflows remain compatible for callers that need only one capability.

`run-checks: false` runs only the lockfile dependency audit, useful for schedules.
`audit-on-dependency-change: true` audits integration PRs only when npm manifests,
lockfiles, npm configuration or workflow definitions change anywhere in the repo.
Release PRs targeting `release-branch` (default `main`), schedules and non-PR events
always audit. Missing Git history is an error, not a reason to skip. The combined
workflow accepts blocking audit thresholds only; `none` is intentionally excluded.

The combined job reports `quality`; callers should choose a stable name such as
`node-quality / quality`. Before replacing old jobs, update any required-check
settings or external deployment-check consumers. Removing a workflow never updates
branch protection automatically. Consolidation trades some parallelism for fewer
installs and fewer separately rounded runner jobs; benchmark minutes and latency.
Checks run sequentially and stop on failure; an audit finding blocks installation
and build, so later diagnostics arrive after the earlier failure is fixed.

Cancel obsolete PR validation at the caller, using a workflow/PR-specific group.
Do not cancel push secret scans: their event ranges can contain different commits.
Retain push/PR secret scans until an equivalent current-revision coverage contract
exists. Deployment/migration concurrency belongs to separate workflows.

### Semgrep inputs

| Input | Default | Accepted values or use |
|---|---|---|
| `profile` | `legacy-ia` | `general`, `javascript`, `ia`, `legacy-ia` |
| `working-directory` | `.` | Directory within the consuming repository to scan |

`general` selects `p/default` and `p/secrets`. `javascript` also selects
`p/typescript` and `p/react`. `ia` and `legacy-ia` additionally include the
embedded FTSC Supabase public-environment-variable rule. `legacy-ia` preserves
existing callers that omit inputs. New callers should choose a profile explicitly.
These are scanner configurations, not repository classifications or approvals.

The scanner version is pinned in the workflow. Registry rule packs can still
change independently, so scanner pinning alone does not freeze rule content.
Semgrep runs with `--error`, so findings fail the job.

## Onboard a repository

1. Record an owner and select the applicable repository profiles. Review those
   choices with the repository's normal maintainers.
2. Add caller jobs for the relevant checks. Set `permissions: contents: read`
   for these checks and avoid passing unrelated secrets.
3. Reference shared workflows using a reviewed full commit SHA. Schedule reviewed
   updates to that reference. Existing `@main` callers receive changes immediately
   when this repository's main branch changes.
4. Validate both passing and failing cases in a trial PR. Verify the actual job
   names, event coverage, and fork behavior before making checks required.
5. Configure enforcement separately where the organization supports it.

Reusable workflows are called at the job level using `uses`. A private workflow
repository must allow access from the intended consuming repositories in
**Settings → Actions → General → Access**, and callers' Actions policies must
permit it. See [GitHub workflow reuse](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).

## Enforcement and rollout

Keeping workflows here does not automatically run them in every repository or
protect any branch. Callers select events, and administrators configure rulesets,
required checks, and security settings separately. Organization permissions,
licensing, and effective enforcement have not been verified by this change.

Existing workflow filenames, job IDs, and input names are retained. The audit
workflow now defaults to Node 24 LTS. It retains npm thresholds
`info`, `low`, `moderate`, `high`, `critical`, and `none`. The default is `high`.
`none` is advisory for vulnerability findings and should not be used for a
blocking security gate. Semgrep fails on findings through `--error`; `--strict` is not enabled. All jobs have bounded run times. Validate these
changes before merging because existing `@main` callers adopt them immediately. Review Semgrep
profile changes as coverage changes. Pilot new profiles before enforcing them
across a repository group. Do not change required job names without coordinating
the associated rules.

ZAP is not implemented in this library yet. The profile guide describes the
prerequisites for a future web/API pilot, not an active security check or a claim
of policy compliance.

## Examples and maintenance

Start with the [documentation/skills caller](docs/examples/documentation.yml.example)
or [JavaScript caller](docs/examples/javascript.yml.example). Replace
`REVIEWED_COMMIT_SHA` before use. Add repository-owned validators and tests.
These examples do not implement branch protection or a complete release pipeline.

Run validation locally with Python and Go installed:

```sh
python -m pip install -r tests/requirements.txt semgrep==1.177.0
python -m unittest discover -s tests -v
go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
"$(go env GOPATH)/bin/actionlint" -shellcheck= -pyflakes= .github/workflows/*.yml docs/examples/*.yml.example
```

CI runs both input/failure tests and real Semgrep positive/negative fixtures.
The local scanner test is skipped if Semgrep is absent. Registry pack resolution
and cross-repository private access require an online consumer pilot as well.
Dependabot proposes monthly GitHub Actions updates. Maintainers also review
Semgrep and TruffleHog scanner versions and registry rule changes. The TruffleHog
scanner is release-version pinned, not image-digest pinned. No auto-merge is set.

## Runtime and compiler standards

The approved shared policy lives in [IA Standards & Architecture](https://fulcrumlibrary.atlassian.net/wiki/spaces/IA/pages/1433993222).
New Node applications use Node 24 LTS. Existing supported exceptions must be
documented with an owner and review date. Use one runtime per ordinary PR;
compatibility matrices belong on upgrade PRs or explicitly multi-runtime projects.

For `node-quality`, commit `.node-version` with the selected major (`24`),
`engines.node: "24.x"`, an exact `packageManager: "npm@11.19.0"` and matching
`engines.npm`. CI checks runtime alignment and installs that npm version before
audit/install. Use npm `devEngines` with `onFail: "error"` locally, and run
`npm install --global npm@11.19.0` once after selecting Node 24. Deployment
builds must use the same npm version and Node major. No fallback from failed
`npm ci` to `npm install` is permitted in validation or deployment.

TypeScript applications must type-check the actual application sources in this
job (`typecheck: true`) or through a verified build that invokes the checker.
Vite transpilation alone does not meet this requirement. Keep the compiler in
the application lockfile; TypeScript 7 adoption requires a compatibility and
timing pilot, including ESLint/framework compiler API users. Retain the existing
compiler until that pilot passes. This does not require an extra install/job.

Actions are pinned to reviewed immutable commits. Dependabot reviews action
updates monthly; review Node support, npm pins and compiler compatibility at
least quarterly and ahead of end-of-support dates. Application Node versions
and JavaScript action runtimes are separate: current action pins use Node 24.

Legacy `build`, `lint` and `dependency-audit` entrypoints also honor an exact
`packageManager` npm declaration. For compatibility, an absent declaration
retains the npm bundled with Node. Only `node-quality` requires the complete
runtime contract; migrate callers to it for the enforced baseline.
