# Fulcrum Technology Solutions — Org Workflows

Central home for reusable GitHub Actions workflows. Every FTSC tool repo calls
these instead of copy-pasting YAML. Update a workflow here once and every repo
picks it up on its next run.

## What's here

| Workflow | Purpose | Trigger in consuming repo |
|----------|---------|---------------------------|
| `secrets-scan.yml` | TruffleHog verified-secret scan | every push + PR |
| `build.yml` | `npm ci && npm run build` | PR |
| `lint.yml` | ESLint (`npm run lint`) | PR |
| `dependency-audit.yml` | `npm audit` (level: high) | PR + weekly |
| `semgrep.yml` | SAST + FTSC Supabase rules | PR |

Custom Semgrep rules (canonical source): `semgrep-rules/supabase.yml`.

## How a repo consumes these

Add `.github/workflows/security-checks.yml` to the tool repo. See the reference
file in `consuming-repo-example/`. It calls each reusable workflow with `uses:`.

## Required setup for private repos

Reusable workflows in a private repo are not callable by other private repos
until you allow it:

**This repo → Settings → Actions → General → Access →**
"Accessible from repositories in the `<org>` organization."

Without this, callers fail with a "workflow not found / not accessible" error.

## Notes

- On the **Free** plan these checks run and report but cannot *block* merges on
  private repos (branch protection requires Team+). They become enforceable
  required status checks once the org upgrades.
- Pin actions to a tag/SHA over time; `@main` is used here for test-org speed.
