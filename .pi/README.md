# Pi in FTESurf

Double-click **`C:\FTESurf\Start-Pi.cmd`** to open Pi in this checkout. It is also
a terminal command, including from another directory:

```powershell
C:\FTESurf\Start-Pi.cmd
C:\FTESurf\Start-Pi.cmd --continue
# Static preflight, no model call, build or deploy:
C:\FTESurf\Start-Pi.cmd -Check
```

The CMD wrapper forwards arguments to `tools/pi-start.ps1`. With no arguments,
an error stays visible until a keypress; terminal calls with arguments return
the exit code without pausing. PowerShell 7 is required. A desktop shortcut may
point to the CMD file with `C:\FTESurf` as its working directory.

Plain Pi must start from **C:\FTESurf**, not the engine checkout or `ftesurf/`.
The direct `pwsh -NoProfile -File C:\FTESurf\tools\pi-start.ps1` route still works.

The launcher changes cwd and supplies pi-lsp's agent-directory environment; it
never pins the model, changes permissions/trust, or starts a build/deploy.
Plain `pi` from this repo is also valid after opening a new terminal with the
configured PI_AGENT_DIR environment. Inspect the startup resource list and the
footer's model. Trust this known project when Pi asks; do not globally trust all
projects. Pi has no built-in `/add-dir` and cwd is not a sandbox: absolute engine
and private-tree paths work without adding them, but their instructions must be
read explicitly.

`AGENTS.md` is the short mandatory startup contract. `AGENT_NOTES.md` preserves
the detailed workflow rules and measured failures; read the relevant sections
before work. CONTRIBUTING.md and CLAUDE.md remain authoritative. No private plan
is auto-loaded; anti-cheat work reads the named private documents on demand.

## Packages and model routing

The project declares `npm:pi-subagents`, `npm:pi-lsp` and `npm:context-fold` in
`.pi/settings.json`. On a new machine, install those with `pi install npm:<name>`
and authenticate the desired model provider in Pi. Global/project resource
loading is managed by Pi; do not install duplicate manual extension copies.
After resource changes, restart Pi or use `/reload`.

Native roles inherit the model selected in the parent, including Sol 6.1 when
selected. Explicit role overrides prevent user settings pinning them to another
provider. Scout uses low thinking, workers/delegates/researchers medium, and
reviewers/auditors/oracle Xhigh. This workstation saves Xhigh specifically for
`openai/gpt-6.1-sol` at startup; other models keep their own/default effort.
Neither this project nor the launcher changes parent model selection. Explicit per-run overrides remain possible; fast/priority
billing is not enabled. External CLIs have their own auth/model rules and are
NOT automatic fallbacks. Installed is not authenticated or launch-tested.

## Engine LSP (Windows/MSYS2)

Installing clangd alone is insufficient: FTE uses a Makefile, Windows headers,
conditional defines and MSYS paths. Generate its local, ignored compilation db:

```powershell
cd C:\FTESurf
python tools/test_clangdb.py
python tools/clangdb.py
```

`clangdb.py` uses FTE's m-rel dry-run commands, normalizes MSYS paths and preserves
defines/includes. It overrides DO_LD because FTE marks its linker recipe with `+`
and otherwise links even under `make -n`. It does not rebuild/deploy the game.
An empty/foreign/incomplete database is refused. `--engine`, `--msys`,
`--compiler` select another checkout/toolchain; `--log` parses an existing log.
Regenerate after build-flag/header/toolchain changes. The generated
`<engine>/compile_commands.json` and clangd's `.cache/` stay ignored.

Machine configuration is **~/.pi/agent/lsp.json**, NOT tracked. The supplied
`.pi/lsp.example.json` documents this workstation's working configuration; copy
it there on a similar machine and adapt binary, GCC and environment paths. It
uses explicit extension globs (pi-lsp does not implement brace expansion),
root markers, two indexing workers, no include insertion, and an exact
`--query-driver` allowlist. Never allow every executable as a query driver.

The current pi-lsp release resolves its user config with PI_AGENT_DIR or the
HOME environment variable, not Pi core's Windows resolver. PowerShell's `$HOME`
is not necessarily `$env:HOME`. This workstation has a user PI_AGENT_DIR setting;
the launcher handles existing terminals immediately. If using a custom Pi core
agent dir, align PI_AGENT_DIR with PI_CODING_AGENT_DIR. GCC needs its DLLs on
PATH and a Windows TMP/TEMP; the LSP config supplies those ONLY to clangd.

Ask Pi to use **lsp_hover**, **lsp_definition** and **lsp_references** on an engine
symbol. The installed extension has these tools; do not rely on a `/lsp status`
command (its README advertises commands this installed version does not register).
`lsp_diagnostics` returns cached observations: "no diagnostics recorded" before
a document has opened is NOT a successful parse. A hover/navigation reply plus
real compiler checks proves more than that empty cache.

clangd is for **C/C++ only**, not QuakeC. A standalone `--check` can test parsing;
on clangd 23 use `--tweaks=` to omit unrelated refactoring self-test failures on
FTE macros. It must still report zero parser errors. Validate C++ plugins against
their own flags/database before relying on their diagnostics: m-rel covers the
engine C and statically included Quake3 sources, not every plugin or Linux target.
fteqcc and live falsifiers remain the QC authority; actual builds and physics/
evidence tests remain the engine authority.

## Context-fold and private work

Context-fold is intentionally at defaults; no aggressive custom budgets, forced
unfolding or provider/context-window overrides. Core compaction remains enabled
as a safety net. Large operational notes are on demand, not permanently stuffed
into every parent/child startup. The fold preview is not the original source.

Keep explicit long-task checkpoints with ref, owned diff, commands/results,
control/subject, unknowns and next step. Anti-cheat checkpoints stay private.
Do not share/export a session or agent report that includes private design,
exploit recipes, credentials or GUIDs. Filesystem access and instruction wording
are not isolation; trusted local processes and packages run with your permissions.

## Delegation safety and smoke test

- Work directly unless the operator requests delegation. Setup verification is
  authorized by the setup request, not standing permission to delegate all work.
- Prefer native scout/worker/fresh reviewer. Ordinary children are leaves, not
  orchestrators; use the native supervisor channel, no extra intercom needed.
- Use one async workflow for authorized multi-step/parallel work. Consume native
  completion notifications, not polling/bg_wait merely for a wake.
- One writer per checkout. Isolated worktrees require a clean source; never
  stash peers' work to get one. A clean worktree lacks ignored build/content
  inputs: prepare them explicitly, use -NoDeploy, never blindly dual-deploy it.
- Do not disable strict model verification/permission checks after failure.
  Report exact run/status/cwd/ref and partial diff; stop, repair the native path
  or ask the owner, never silently switch provider/CLI.

Useful installed subagent commands: `/subagents-doctor`, `/subagents-models`,
`/subagents-models worker`. Ask the parent to discover capabilities and run:

```js
subagent({ action: "list", capabilities: true });
subagent({ action: "validate", workflow: "./.pi/workflows/subagents-smoke.js" });
subagent({ workflow: "./.pi/workflows/subagents-smoke.js", async: true,
  mission: false, timeoutMs: 300000, globalConcurrencyLimit: 2 });
```

This read-only workflow runs a fresh scout and forked worker in parallel, then a
fresh reviewer. It exercises shell checks and the worker's non-blocking supervisor
channel. Checked smoke criteria are explicit because no implementation is asked
for; normal worker delivery gates are unchanged. Worker status can remain
`review-required`: the separate reviewer report must be consumed. `ok` alone is
not proof of every assertion; read model metadata, reports and command results.
It uses the selected model's normal quota and does not build/deploy/read secrets.

Only named setup files are allowlisted. LSP machine config, sessions, agent
memory, refinements, schedules and runtime reports stay ignored/private.

## Verified on this workstation — 2026-10-06 UTC

- Start-Pi.cmd passes -Check and --version from an unrelated TEMP cwd; a CLI
  validation error returns exit 1 with the wrapper's error message, without a
  terminal pause. The local desktop shortcut's target/arguments/cwd were read
  back and verified. Interactive drawing was not automated by these checks.
- Pi 1.0.4, clangd 23.1.2, UCRT64 GCC; 222 m-rel translation units generated.
  Four parser tests pass, including empty input refusal and MSYS path mapping.
  Before/after SHA256s of the installed exe, both lobby progs and built engine
  exe are identical across database generation: it did not rebuild/deploy them.
- clangd --check with the configured driver/environment and --tweaks= reports
  zero errors on pm_source.c, sv_user.c and in_generic.c. Default --check's
  refactoring self-tests fail on FTE macros; those are not parser diagnostics.
- A fresh Pi print-mode session through pi-start.ps1 successfully used hover on
  PMSrc_StartGravity and definition navigation to PMSrc_FinishGravity. The old
  already-running parent can still lack PI_AGENT_DIR: restart through the launcher.
- Native setup workflow dfd6bb1a completed: scout/worker/reviewer metadata names
  openai/gpt-6.1-sol at Low/Medium/High; read-only shell checks pass, independent
  setup review has no findings. Afterwards the operator's Xhigh preference was
  saved for Sol startup and review/oracle/audit roles; that effort change is
  configuration-checked, not a second full smoke run.
- The instruction split preserved every historical section from Repository
  layout onward exactly after newline normalization; always-loaded AGENTS.md
  shrank from about 247 KB to 10 KB. No private design was read or published.

These are setup checks, not a claim that engine C++ plugins, anti-cheat changes,
Linux targets or live lobbies were tested. No product/release/fleet changes here.
