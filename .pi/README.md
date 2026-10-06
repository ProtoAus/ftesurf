# Pi subagents in FTESurf

The project declares `npm:pi-subagents` in `.pi/settings.json`. On a new machine,
install it with `pi install npm:pi-subagents` and authenticate the model provider
in Pi. Project configuration contains no credentials or machine-specific paths.
Open Pi with this repository as its working directory. After installing or
changing settings, use `/reload` (or restart Pi) and inspect `/subagents-models`.

## Model routing

Native roles inherit the model selected in the parent Pi session, including
Sol 6.1 when the parent selects it. Explicit role overrides are needed because
user-level settings can otherwise pin roles to another provider. Scout uses low
thinking, workers/delegates/researchers medium, reviewers/auditors/oracle high.
The project settings do not change user-wide settings or parent model selection.
Per-run explicit model overrides remain possible; fast/priority billing is not
enabled here. External CLI agents use their own authentication and model rules,
are not selected by this setup, and are not automatic failure fallbacks.

## Delegation and repository safety

- Work directly unless the operator requests delegation. Setup verification is
  authorized by the setup request, not standing permission to delegate all work.
- Prefer native `scout`, `worker`, and fresh-context `reviewer` roles. Ordinary
  children are leaves, not orchestrators. Use the native supervisor channel for
  decisions; no separate intercom package is required.
- Use one async workflow for authorized multi-step/parallel work, await child
  results at dependencies, and consume the completion notification. Do not poll
  or use `bg_wait` merely to wait for native completion.
- Keep one writer per checkout. Concurrent writers need isolated worktrees,
  which require a clean source tree. Do not stash someone else's work to get one.
- Children inherit project context. `AGENTS.md`, `CONTRIBUTING.md`, and `CLAUDE.md`
  remain authoritative: no `git clean -x`, no generated-file edits, no private
  anti-cheat material in public outputs, and no blind staging or deployment.
- A clean worktree lacks ignored compilers, content mounts, and player data.
  Prepare required build inputs explicitly; do not run a default build/deploy
  from an isolated child against the owner's installs. Use the project's
  `-NoDeploy` control-build procedure when appropriate.
- Do not disable strict model verification or permission checks to hide a
  failure. Report the exact run, status, cwd, branch/ref, and any partial diff;
  repair the native path rather than silently switching to another CLI.

## Diagnostics and smoke test

Useful Pi commands:

```text
/subagents-doctor
/subagents-models
/subagents-models worker
/run scout Describe the QuakeC source/build layout without changing files
```

Ask the parent to run this repeatable, read-only workflow:

```js
subagent({ action: "validate", workflow: "./.pi/workflows/subagents-smoke.js" });
subagent({ workflow: "./.pi/workflows/subagents-smoke.js", async: true,
  mission: false, timeoutMs: 300000, globalConcurrencyLimit: 2 });
```

The workflow runs a fresh scout and a forked worker in parallel, exercises the
worker's shell and non-blocking supervisor channel, then runs a fresh reviewer.
The worker uses explicit checked smoke-test criteria rather than the automatic
implementation criteria, because it is not being asked to implement anything.
Normal worker delivery gates are unchanged. The worker's status may remain
`review-required`: the reviewer is a separate workflow step, so the parent must
consume that report rather than claiming an automatically attached review gate.
Reports are bound through the runtime's `output` field; the result returns the
actual report references rather than assuming filenames. Read the reports and
check model metadata and command results before claiming success: `ok` alone
proves execution, not every behavioral assertion. It performs no game build or
deploy and uses the selected model's normal quota.

Only these setup files are allowlisted in Git. `.pi/subagents/`, agent memory,
sessions, refinements, schedules, and other local Pi state remain ignored.
Runtime reports may contain project context; do not publish/share them by default.
