# Repository Profiles

Use a shared baseline plus the profiles that match a repository's contents and
deployment model. Profiles are composable. A skills repository containing Python
tools, for example, needs both skills validation and suitable software checks.

This guide defines the shared-checks architecture and recommended onboarding
controls. It does not establish a new mandatory corporate policy or prove that
organization-wide controls are configured.

## Shared baseline

For each maintained repository, identify its owner, supported workloads, lifecycle
status, and applicable checks. Include secret scanning, use restricted workflow
permissions, review changes through the repository's agreed PR process, and pin
external automation to reviewed revisions. Define who reviews failures and any
exceptions. Archive or retirement decisions remain separate from classification.

Review workflow and classification changes like other security-relevant changes.
Selecting a different profile must not become an unreviewed way to remove required
checks. Do not impose the IA review board, branch model, or hosting stack on other
Fulcrum repositories.

## Profile selection

| Profile | Apply when | Checks and supporting practices | Shared library support |
|---|---|---|---|
| `docs` | Repository contains documentation or reference material | Validate relevant links, document structure, and formats. Build published documentation when applicable. | Secret scan. Content validators remain repository-specific. |
| `skills` | Repository distributes AI skills, agent guidance, or related assets | Validate skill metadata, referenced resources, packaging, and executable helpers. Review changes to tool permissions and instructions. | Secret scan. Add `software` for executable code. No universal npm requirement. |
| `software` | Repository contains an application, library, CLI, or other executable code | Language-appropriate static analysis, dependency scanning, build/lint where applicable, and meaningful tests. | Semgrep with appropriate coverage. Existing build/lint/audit workflows support npm only. Tests remain caller-owned. |
| `infrastructure` | Repository manages infrastructure, configuration, or deployment automation | Validate syntax and schemas, scan applicable infrastructure code, and review proposed deployment changes. Test automation and restrict deployment credentials. | Secret scan. Semgrep may supplement supported languages, but does not replace stack-specific infrastructure validation. |
| `web-api` | Repository deploys a web application or HTTP API | Add `software`, identify a safe test environment, and plan scoped runtime security testing appropriate to the application. | Static checks available. ZAP remains a future staged addition. |
| `ia` | Repository implements an approved Internal Application | Add `software` and `web-api` where applicable. Follow IA-specific ownership, approval, authentication, environment, and release documentation. | Semgrep `ia` adds the FTSC Supabase rule to the JavaScript configuration. It does not enforce the full IA process. |

Profiles identify capabilities to consider, not a claim that this library
already supplies every check. A monorepo can apply different checks to different
directories. The same workflow must not be treated as sufficient coverage for
unrelated languages or deployment types.

### Examples of classification

- `ftsc-skills`: `skills` plus `docs`, with `software` checks for executable helpers.
- A Python service: `software` plus `web-api`, with Python dependency and test jobs.
- Terraform and deployment scripts: `infrastructure` plus `software` for scripts.
- An IA application: `ia`, `software`, and `web-api`.
- `ftsc-app-template`: template source with software checks and IA configuration
  validation. Template maintenance does not itself adopt an application's
  `develop` → `main` release process.

## Classification and enforcement

Start with a reviewed record of profile choices, owner, runtime/language, deployment
status, and any exceptions in the repository. As administration capabilities are
confirmed, use organization custom properties to make classification searchable
and target repository groups. Keep property changes under appropriate review.
GitHub supports repository custom properties for organization management and
ruleset targeting. [GitHub custom properties](https://docs.github.com/en/organizations/managing-organization-settings/managing-custom-properties-for-repositories-in-your-organization)

There are three distinct configuration layers:

1. This library provides reusable implementation.
2. Repository callers select suitable checks and events.
3. Organization or repository rules and security settings enforce the agreed
   coverage where supported.

Do not assume a caller cannot be removed merely because it uses a central
workflow. Verify required status checks or required workflows against the actual
repository group, branch rules, bypass permissions, and plan capabilities. These
settings are outside this refactor and have not been verified. Native GitHub
security configurations are also separate from these Actions workflows.

Keep required jobs compatible with event and path filtering so legitimate PRs
do not wait indefinitely for checks that never run. Confirm that changes to
workflow files, security rules, and classification receive appropriate review.

## Selecting Semgrep coverage

| Scanner profile | Rule packs | Use |
|---|---|---|
| `general` | `p/default`, `p/secrets` | Broad starting point for supported source languages. Confirm actual rule coverage. |
| `javascript` | General plus `p/typescript`, `p/react` | JavaScript/TypeScript/React software. |
| `ia` | JavaScript plus embedded FTSC Supabase rule | Current IA application stack. |
| `legacy-ia` | Same as `ia` | Compatibility default for existing callers. |

Choose `working-directory` for the intended component. Use additional jobs when
multiple directories require coverage. Changing from `legacy-ia` to `general`
removes the TypeScript, React, and custom Supabase additions, so review that change
explicitly. Choosing `general` does not automatically supply useful rules for
every language or infrastructure format.

## Staged ZAP onboarding

ZAP will be a separate capability for suitable `web-api` repositories. It is not
implemented or required by this refactor. Before a pilot:

1. Verify an isolated, authorized test deployment with suitable test data. For IA,
   confirm the release preview and integration-managed environment are ready.
2. Tie the scan target and result to the exact deployment and current commit.
3. Define allowed URLs and exclude third-party identity providers, destructive
   routes, and operations that cause expensive or unwanted side effects.
4. Configure restricted authentication where needed and prove the scan reaches
   protected application pages. Authentication failure or incomplete coverage
   must be reported as a failed/incomplete scan, not a clean result.
5. Begin with passive baseline scanning, tune findings, and explicitly configure
   blocking rules before making a check required. Store sanitized private reports
   and avoid creating public or automatic issue content containing sensitive data.

Passive scanning still crawls the application and sends requests. Active scanning
needs separately approved scope and isolation. ZAP does not replace authorization
tests, Semgrep, normal PR review, or targeted human validation of significant
findings and sensitive changes. [ZAP baseline behavior](https://www.zaproxy.org/docs/docker/baseline-scan/)

## Adoption sequence

1. Inventory repositories and review classifications with their owners.
2. Pilot applicable callers in a skills repository and an IA application.
3. Confirm passing, failing, and unsupported-input behavior and record gaps.
4. Confirm GitHub access and plan capabilities, then configure enforcement for
   the selected repository groups.
5. Expand by workload. Add language-specific workflows as real consumers need
   them, and review shared-workflow updates through PRs.

Keep future ZAP implementation and corporate policy reconciliation visible as
separate work. Neither is completed by introducing these profiles.
