# P734 — opt-in recurring Source diagnostics

## Behavior

`developer 2` no longer prints the routine Source area-reachability report,
`mark/300f` leaf-walk statistics, area-cull census or successful jump-height
normalizations unless explicitly requested:

```text
developer 2
hl2_visdebug 1
pm_jumpzdebug 1
```

Both debug switches default to **0**, are not archived or latched, and work
independently. Return either to zero to stop that diagnostic. Their output
still requires `developer`; no global warning filter was added. The movement
trace/origin update and the actual visibility/culling paths are unchanged.

**Steam account window:** join a lobby, type `link` in the console, close the
console, then press Enter in the box to open Steam sign-in. Existing flow only;
no Steam/account implementation changed in this patch.

## Pre-registered falsifier and executed controls

At `developer 2`, visibility marking and successful normalized jumps must ACT
while the three reported diagnostics stay absent with the switches off. Enabling
them must emit those same messages; disabling must stop them again. An original
control must reproduce the spam, so an unloaded map or inactive mover cannot
pass. Self-test and real-map determinism output must remain unchanged.

Clean starting refs:
- Product `5d31a0a5b1b4222be41526c992af93aa868d51d6`.
- Engine `93255c77848a49fd516295e09f34c960450e5ca4`.
- Feature engine `94ce3efb419e6e5b75e033eeb4ecd3c0ccdde1a4`, annotated `patch-734`.

Runtime driver: `tools/p734devquiet.py`. An explicitly owned root contains a
private writable gamedir and read-only installed-content junctions. It runs
only its own dedicated socket on27590 and client, obtains real body-position
replies, repeatedly jumps on surf_kitsune, then maps bhop_eazy locally for the
engine's server-world determinism command. Running `pm_dettest` merely while
connected has no local server world and is NOT evidence; that initial harness
mistake was corrected before the recorded control/subject comparison.

Original control2 (ten-second measured phase):5 area,26 mark and29 jump lines.
Initial subject1 off/on/off_again counts (area/mark/jump):0/0/0,5/27/27,0/0/0;
the enabled arm also emitted the area-cull census. Each phase received two body
replies. Both clients pass `pm_selftest`; their complete actual-map
`pm_dettest` transcripts are identical, including the existing hull-floor
warning, all trace/tick rows, tick census and hashes:

```text
mapcrc   7f53da5d
libm     5e749b8a83b44107
trace    f7958b04dbcd1008
mover    3d136f8de25c9c2c
tick     93e8615d81c26325  ticks 2048/2048
srctrace de0ed3421db7e9d1
srcmover 3d136f8de25c9c2c
```

Final clean-commit build uses the normal `src/build.ps1 -Engine -Full -NoDeploy
-Jobs 8 -FteRoot <owned-engine> -QuakeDir <owned-unused-path>`, PowerShell7,
pre-existing linked native dependencies and the installed fteqcc. Supply
`SVN_VERSION=git-7343-patch-734-0-g94ce3efb4` and
`SVNREVISION=-DSVNREVISION=<that-version>` for a worktree; `.git` is a file.
Owned TMP/TEMP/TMPDIR avoid the initial ancillary UI metadata ZIP failure;
that target was explicitly rebuilt and all final plugin archives validate.

Final full native/QC build completes. All three QC VMs have zero warnings;
57 distinct existing native compiler warnings match the original full control,
with **zero NEW warnings**. Database regenerated after the stamp/flag change.
Touched-file LSP shows no parser errors, only pre-existing warnings. Screenshots
of original spam and the quiet subject were inspected; unrelated fixture
texture warnings remain visible and were not repaired or filtered.

Example runtime command (run from the checked-out product tree):

```text
python tools/p734devquiet.py --root C:/FTESurf-worktrees/<owned-task> --client <native-exe> --plugin <hl2-dll> --label subject
```

Add `--control` only for original binaries; `--direct` executes the specified
installed client in place while retaining the private gamedir. Logs must be
fresh. The driver leaves evidence and its rig for the verified owner's cleanup;
never recursively remove its content junction targets.

## Delivery status

Engine source and annotated tag are pushed. Final stamped-source runtime passes:
off/on/off_again counts0/0/0,5/26/25,0/0/0 (area/mark/jump); the enabled cull
census also acts. Both default-zero cvar readbacks are checked before setting
them. `pm_selftest` passes and the complete original determinism transcript is
still an exact match; all owned processes exit normally.

Native-only dual Windows deployment, **2026-10-16T04:04:48Z**:

| File | SHA256 |
| --- | --- |
| Both clients (`ftesurf64.exe` / `fteqw64.exe`) | `c18e91c8781e11bfd6580be18618512f1d90f16148d02331409f0f2b34cbe6e4` |
| Both `fteplug_hl2_x64.dll` | `b950fde7eb090aea0c5e6a505b77eaaf68c08af80ff2e835d90a73eee981ed73` |
| FTEQuake `fteqwsv64.exe` | `69891fd12d66ff6bdc2a1d48acc37538deca2f0fd3b03a824250092f94ffb7b1` |

All five destination hashes match; each `.prev` matches its recorded predecessor.
Exclusive-open checks precede the swap; no owner game was killed/restarted.
Other native plugins, progs and configs were not shipped. Published source/pin
lives on origin/main; the stale shared canonical source branches and peer edits
were deliberately not reset or overwritten.

Both **actual installed client paths** then pass the same native socket and
local-world controls via `--direct` (not merely another executable copy):

| Client | Off | On (area/mark/jump) | Off again |
| --- | --- | --- | --- |
| `C:/FTESurf/ftesurf64.exe` | 0/0/0 | 5/27/24 | 0/0/0 |
| `C:/FTEQuake/fteqw64.exe` | 0/0/0 | 5/27/25 | 0/0/0 |

Both enabled arms include the cull census. Both installed clients pass the
self-test and exact original full determinism transcript; there are no VM or
process-cleanup errors. Before/after snapshots of both installs' owner configs,
console histories and data trees cover11,751 entries with **zero changes**.
Screenshots and count/hash JSONs are local evidence; raw session logs are not a
public export. Workspace ownership/retirement is recorded at
`C:/FTESurf-worktrees/devquiet-01a142cc/OWNER.md`.

No public release/feed, QC Build-number, generated-program shipping, Linux
binary deployment or live lobby restart is part of this patch. No owner gameplay,
account acceptance or public-fleet behavior is claimed by the isolated tests.
