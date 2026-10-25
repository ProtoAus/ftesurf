# P1003 authored material no-fog — implementation and delivery

Source: engine `b44dde08ec1892895b56723b02243c6d57f31206`, tag `patch-1003`;
QC metadata/control commit `ea2d8d68b2aa3a478e31b84e7e5ca4593b92cbac`.
No Build bump. This is a development-native update, not a release.

## What changed

Source `$nofog` now reaches plain GL passes as an appended `materialnofog` policy,
via `fte_materialnofog`; it does not consume an occupied flag bit or move the
plugin-visible shader prefix. Both fixed-function fog setup and the GL fog
permutation respect it, including automatic-program fallback. Existing explicit
program `#NOFOG` and Wireframe's intentionally forced no-fog remain. A numeric
`$nofog 0` now means false. Ordinary fog and the legacy ignored RTCW directive
remain unchanged. No movement/input/evidence/schema change or new collection.

## Verification and limits

- Existing `build.ps1 -Engine -Full -NoDeploy`, Jobs8, on a clean published baseline
  and the subject: 74 existing compiler diagnostics each, zero new diagnostics.
- Actual-source C controls compile with `-Werror`: baseline32, subject33 checks.
  Both ordinary-fog arms ACT; baseline incorrectly fogs the no-fog material while
  subject does not. These are C/source controls, not a real-window/fog image proof.
- Final published-source build compiled the matching engine/plugin set, but the
  parallel ZIP metadata step failed for cod/ImGui (resource busy / permission).
  Failure/log/partial cod image retained; absent failed outputs were not invented.
  Removed only the verified owned partial target, then finished missing targets
  through the same build entrypoint with Jobs1, no source change, no new warnings.
  Both exe stamps are clean `patch-1003-0-gb44dde08e`; all five plugin ZIP metadata
  archives validate. This records a packaging failure and repair, not a causal
  claim about an antivirus or a general parallel-build defect.
- Regenerated the owned clangd database. Standalone plugin/header inference remains
  incomplete; actual full compiler results take precedence over those LSP errors.
- Fresh isolated lobby2 client from the installed spare native: exit0, downloaded
  the served CSQC `2e6801f9bd10de27`, board cols9/type14, no QC error, screenshot
  captured and inspected. The panel was consent-blocked (terms not accepted); no
  claim of online times, run submission, consent or no-fog visual acceptance.

## Windows deployment — 25 October 2026, UTC

- `C:\FTEQuake`: seven official native files updated at06:11:55Z.
- `C:\FTESurf`: seven official native files updated at06:28:31Z, once exclusive
  file leases succeeded. No owner/peer process was stopped.
- All fourteen destination hashes match the seven sealed outputs below. Current
  and older `.prev` images were preserved for rollback. No QC/config/player data
  was changed. Extra legacy `C:\FTEQuake\ftesurf64.exe` is not an official build
  destination and was left untouched.
- These native outputs include main's published P987/P988/P989/P995 source, unlike
  the earlier P990 install branch that held those files back. Only relevant stock
  Windows paths run here; this is not Linux DBus or SDL desktop qualification.
- No Pi native, backend, scheduler, gate, DB migration or release was performed.

| Source output / official destination name | SHA-256 prefix |
|---|---|
| fteqw64.exe / primary ftesurf64.exe | 57060bff52891bd1 |
| fteqwsv64.exe | 09a13f1aec3227b3 |
| fteplug_hl2_x64.dll | 0cc86b08088ac814b |
| fteplug_cod_x64.dll | 89082bce0fe91eb73 |
| fteplug_box3d_x64.dll | d0978ddf0eb64758 |
| fteplug_ode_x64.dll | 82d1c995b3114ea8 |
| fteplug_ui_imgui_x64.dll | 58841b0b75683b94 |

Human GL/no-fog and live material-reload acceptance remain **pending** in
`lextest.md`; other rendering backends are not qualified by these checks.
