# AGENTS.md

Mandatory startup contract for Pi and other coding agents. Read CONTRIBUTING.md
and CLAUDE.md before changes. Detailed subsystem rules and measured pitfalls live
in AGENT_NOTES.md: read the relevant sections BEFORE planning/editing/testing,
not only after a failure. That file is intentionally not auto-loaded in full.

## Start here

- Start Pi from `C:\FTESurf`, or use `pwsh -NoProfile -File
  C:\FTESurf\tools\pi-start.ps1`. This loads `.pi/settings.json` and this brief.
- Pi has NO built-in `/add-dir`. Tools accept absolute paths outside cwd, but
  sibling instructions do not auto-load. This is not a filesystem sandbox.
- `C:\msys64\home\Lex\fteqw` is the engine checkout (C/C++, mover, input journal,
  `pm_recsim`/`pm_verify`, ENGINE_PATCHES.md). It is REQUIRED for engine,
  movement, renderer or anti-cheat work. This repo ships a prebuilt binary only.
- `C:\FTESurf-private` holds the anti-cheat design, samples and reports. Before
  anti-cheat work, read its `anticheat-plan.md`; before client-security audit
  work, also read `ENGINE_SECURITY.md`. Neither document belongs in public Git.
- `C:\FTEQuake` is the second install for client/server controls and mandatory
  dual deployment. Use absolute paths when accessing any of these directories.
- At task start inspect Git status/branch/ref in every affected checkout; read
  any sibling instructions that exist. Do not assume a clean or single-user tree.
- Direct execution is the default. Delegate only when the operator asks for
  agents/review/parallel work. Native roles inherit the selected parent model;
  no silent provider/external-CLI fallback after a child failure. See .pi/README.md.

## Non-negotiable safety

- NEVER `git clean -x`, `git clean -X`, `git stash --all`, or blanket-clean an
  install/worktree: ignored paths include player data, content and build tools.
- Do not edit generated `ftesurf/*.dat`, `*.lno`, `src/defs/*.qc`, the owner's
  `ftesurf/ftesurf.cfg`, `ftesurf/data/**`, `installed.lst` or `crashaddr.txt`.
  Generated build artifacts may be produced/deployed by the build procedure.
- No private design, working exploit recipes, credentials, GUIDs or raw private
  tool output in public commits, agent reports, shared/exported sessions or logs.
  Read secrets inside scripts; never print them or put them in command arguments.
  Private checkpoints stay in the private tree. Pi sessions themselves may
  contain sensitive source/tool results; do not share them without review.
- Never kill the owner's game or another session's processes. Never stash or
  revert another session's files. Park/restore shared fixtures, coordinate use,
  and verify restoration. Data destruction and irreversible changes need asking.
- A failure in untouched code may belong to a peer. Preserve it; do not repair
  unrelated work just to make your build pass.
- No release or deployment of another session's uncommitted work. Use a clean
  worktree at an inspected commit for isolated verification and deployment.

## Layout, language and tooling

- `src/server` + `sv_progs.src` -> qwprogs.dat; `src/client` + cl_progs.src ->
  csprogs.dat; `src/menu` + m_progs.src -> menu.dat (client-local, never a lobby).
- QC compile order is declaration order; `.src` ordering/prototypes are
  load-bearing. Reuse existing interfaces before inventing commands/channels.
- QC style: tabs, local declarations first, module-prefixed globals, concise
  comments; long reasoning belongs in ENGINE_PATCHES.md. Compare dynamic strings
  with strcmp, not `==`. sprintf accepts at most eight values.
- QC `&&`/`||` do not short-circuit and bind BELOW assignment: write
  `x = (a && b);`. Gate optional builtins with nested ifs. Integer arithmetic
  needs `i`-suffixed literals or silently promotes to float32. Big tables belong
  in memalloc, not global arrays. See the measured cases in AGENT_NOTES.md.
- Use LSP definition/references/hover for engine navigation and diagnostics
  after edits. Regenerate clangd's database after build-flag changes:
  `python tools/clangdb.py`. Configuration and smoke checks: .pi/README.md.
- clangd does NOT parse QuakeC; use fteqcc and runtime falsifiers. LSP clean is
  not build clean, physics verified, or evidence of what the owner/fleet runs.

## Build, test, commit, deploy

1. Read the relevant notes below and pre-register predictions/falsifiers. Every
   arm needs a control that proves the subject ACTED; silence is not a pass.
2. Build from `src/` with pwsh 7, not Windows PowerShell:
   `pwsh -NoProfile -Command "./build.ps1 -Jobs 8"`.
   Default deploys to BOTH Windows installs. `-Engine` rebuilds engine/plugin;
   add `-Full` after engine-header changes. `-NoDeploy` is for isolated controls.
   Never invoke a .ps1 directly through Bash; verify the actual compiler output.
3. Build to zero NEW warnings, run the falsifier, inspect logs/screenshots.
   After evidence/reader changes run `python tools/test_reccheck.py` and sweep
   `ftesurf/data/runs`; the corpus fault count must not increase. Read the private
   design and the recorder/verifier contracts before changing evidence semantics.
4. Every product change gets one Patch NNN entry (Problem / Change / Verified)
   in the engine's ENGINE_PATCHES.md and bumps ENGINE.txt's patch. Engine
   commit/tag pins move only for engine work; qcbuild ONLY on the user's Build NN
   decision. Tooling/docs-only setup does not claim an engine/product patch.
5. Before claiming a patch/committing, fetch both repos and take max+1 over patch
   headings AND untracked pNNN test files. Claim one number, not a range.
6. Commit and push each verified feature. Never `git add -A`. The index is shared:
   inspect it immediately before commit. `git commit -- <paths>` is for files
   wholly yours; shared-file hunks require a trimmed `git apply --cached` diff
   and a bare commit ONLY when the cached diff is exactly your set. Prefer an
   isolated index when staging a mixed/shared file. Verify the resulting commit.
   Format: subject <=72 chars, body Root cause / Fix / Verified, including limits.
7. The checked-out branch need not be main; local main is stale. Compare to
   origin/main. Push the exact INSPECTED SHA to main (`git push origin <sha>:main`)
   so a peer's later HEAD cannot race into your push. Never force-push/rewrite
   published history. Prove the commit alone in a clean worktree when peer source
   changes were present during your working-tree build.
8. Development fleet: tested changes normally get deployed so the owner can test.
   Read the full Pi-operations section FIRST. `build.ps1 -Pi` ships qwprogs and
   csprogs from the TREE, not a commit; configs/tools need separate copying.
   Verify destination hashes and live behavior, then record UTC provenance.
   Ordinary progs swaps keep .prev. Do not silently ship unapproved peer work.
   Releases are a separate operation; ALWAYS start with `-Bump patch -DryRun`,
   read all release notes, and verify the archive rather than only the build box.

## Harness essentials

- Test cfgs begin `cfg_save_auto 0`; set `cl_idlefps 0`, `cl_maxfps 100`, and
  every measured cvar explicitly. CWD is `C:\FTESurf`; pass WorkingDirectory.
- `menu_restart` before menu commands; `ui_close` closes the builtin menu so the
  HUD draws. Logs append: fresh names or controlled cleanup, never shared names.
- Client prediction requires a REAL dedicated socket, not a listen server.
  `C:\FTEQuake\fteqwsv64.exe` is the server; ftesurf64 -dedicated is unsuitable.
  After csprogs rebuild seed with `python tools/seed_csprogs.py`, restart server.
- Warp with `cmd zone_goto`, not setpos. Start by WALKING out of the start box;
  prove `cmd timer` says running/recording and measure body with `cmd viewpos`.
- QC print in SSQC goes to the SERVER log, not the client's; dprint also needs
  log_developer. A cvar read locked by a server has an Effective value separate
  from the first quoted value. Commands sent before spawn can vanish silently.
- A dedicated lobby port is 27510 or 27520..27620, NOT sweeper port 27698.
- Protect fixtures/player data; harness handles are registered cvars, not QC
  globals. Config files use // comments only. Read the run/test pitfalls first.

## Read-on-demand map for AGENT_NOTES.md

Locate headings with grep, then read the WHOLE relevant section(s). Notes are
operational constraints and recorded failed experiments, not optional background.

| Task | Required sections |
|---|---|
| Any implementation/test | Build; Run and test; Conventions; relevant Pitfalls |
| Movement/trigger/prediction | Boundaries and interfaces; Anti-cheat and run evidence; engine patch entries |
| Recorder/receipts/holds/rewind | Anti-cheat and run evidence; Rewind; private design |
| HUD/replay/run lines | The run line; Boundaries and interfaces; Rewind if relevant |
| Chat/votes/input | Chat and say; Map clock and votes; Pitfalls |
| Menu/maps/downloads/imports | Imported runs and its browser/roster/download subsections; Zone files |
| surfd/web/board import | Pi operations; public web surface; board freshness/top-up sections |
| Any deployment | Pi operations in full; Build; relevant generated-data/ship-set notes |
| Release/Linux | Linux build, test rig and release; ship set allowlist; Build; Pi operations |
| Milk/renderer/audio | The milk visualizer; relevant Pitfalls; engine patch entries |

Open bugs/follow-ups belong in BACKLOG.md (site/function + falsifier); remove
in the fixing commit. Human-only acceptance belongs in lextest.md. Requested
unbuilt features belong in ROADMAP.md. New historical findings go in
AGENT_NOTES.md, not back into this startup brief.

## Long sessions and context-fold

Defaults are intentional. Folding/compaction is not verification: reread source
citations before relying on them, especially claims that a document is wrong.
Use recall_folded only for a known folded detail needed now; rerun narrow commands
or reread the source when cheap. Do not permanently unfold broad logs by default.
At workstream boundaries record a checkpoint: inspected SHA, owned paths, exact
commands/results, control vs subject, remaining unknowns and next step. Keep
private anti-cheat checkpoints private. Never equate committed, built, pushed,
deployed and verified: they are separate states requiring separate evidence.
