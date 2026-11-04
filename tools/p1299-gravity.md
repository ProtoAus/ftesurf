# P1299 — normalized takeoff-offset observation

Native source: `9d0a294bd0d60f4f119b3b4c9e79747cf4fbf429`, tag `patch-1299`.
Published via `c387062f9449ba344dcef11e789c49e342b06953`; that merge preserves
concurrent P1298/P1300 journals and differs from the built source only in the
journal, not compiled code.

## Implementation

The existing early gravity-use observer now accepts finite nonnegative jump-height
offsets in supported normalized jumps. Stock nonzero offsets, negative offsets and
nonfinite settings remain excluded. It uses the actual accepted native takeoff
origin and the existing clear-path proof. No movement, recorder/API/version, new
signal, tier, badge or ranking policy change; broader provenance coverage remains
partial. Build number and release version are unchanged.

## Verification so far

- Untreated production passes all 1,448 older native controls and fails the 36
  expected new admission/use assertions with the acting physical controls passing.
- Subject passes all 2,888 native checks: 1,448 older, 1,416 additional private
  controls and 24 public admission/negative checks.
- Standing, ducked and transitioning postures; normalized additive/nonadditive;
  stamina off and finite enabled; stationary/rising input; successful, missing-DOWN
  and blocked-UP relocation; clear and blocked accepted paths. Actual native
  relocation agrees between gravity alternatives. Observer off/on preserves the
  entire player body and movement configuration byte-for-byte.
- Original fixture expectations about collision contact margin and stamina cost
  were wrong; failed logs were retained and only those test expectations repaired.
- Official `build.ps1 -Jobs 8 -Engine -Full -NoDeploy` passes: client, dedicated
  server, HL2 and other plugins. Final clean Windows source passes 1,472 public
  native checks. The same 2,888 expanded checks and 1,472 final public checks pass
  on a clean ARM64 server/HL2 build; all 1,127 canonical source blobs verified.
- Six-map movement comparison: 90 exact rows per arm between untreated Windows,
  subject Windows and subject ARM64. Prop contacts act on all four prop maps;
  native processes exit naturally. Same test progs on both platforms, no live
  fixture/player data edits.
- Changed code has no new compiler warning. Full server baseline has 21 existing
  warnings; the official QC build retains the same two pre-existing client F333
  diagnostics, SSQC/menu zero. Reader suite: 949 checks, zero failed. Corpus
  baseline: 541 recordings, 341 existing structural faults; not a clean-corpus claim.
- Original build/transport/setup/parser failures remain failures. The full build
  needed a populated dependency cache, not the empty canonical placeholder. The
  ARM transfer uses individually verified raw Git blobs, not CRLF-converted
  archive output. The first map parser looked for contacts on the wrong row;
  corrected reader reused its already-passed native exits rather than rerunning
  them or changing native output.

## Delivery status

Native source/tag are published. Builds and native/platform checks above are
verified. **Not deployed:** dual Windows installation is blocked by an active
owner/peer game process; no process is stopped. The read-only Pi preparation
failed its recorder-stability gate, and a separate diagnostic confirms a current
open recorder FD and changing parts across the strict 13-actor scope. No archive,
staging, gate, swap or restart was performed, and the failure is not regraded.
The live backend is `collectors84-v1` (84 files), not the old 81-file helper
profile; activation must use the actual current profile without weakening it.
Windows/Pi activation, historical verifier compatibility and actual live-client
readback remain pending. No deployment is claimed by source publication.
Private source/evidence, raw runtime data and outstanding historical failures stay
private. This patch does not close the wider anti-cheat bank or the deferred native
file-writer audit.
