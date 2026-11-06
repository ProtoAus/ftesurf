# P1343 — relative teleport enable, lookahead and report parity

## Problem / change

Relative teleports did not save vbsp_io_solid at spawn. An Enable before any
Disable therefore restored SOLID_BSP instead of SOLID_BSPTRIGGER, changing a
pass-through clip trigger into a blocking brush. Save its original solidity.
Generic Enable also cleared EF_NODRAW: preserve invisibility for BSP clip triggers
without Alpha owning that flag; ordinary brushes still unhide normally. Admission/
banking branches are unchanged.

Their deterministic destination (trigger world-space center + teleportoffset)
was also absent from the extra-PVS eye and server-only teleport registry. Reuse
one server point helper in the authoritative touch and PVS, include ordinary AND
relative touch callbacks in the lookahead chain, and retain disabled/rewind/PVS-
off/fallback gates. Client touch, registry and report ambiguity checks share the
same point helper. Existing optional floor lift and strict2-unit distance remain.

PE_ServerTele must REFUSE quieting if any predicted ordinary OR relative teleport
can land there. Adding relative destinations without this guard would hide a
real misprediction; the acting counterfactual specifically detects that failure.
No blanket threshold/quiet-window change, no report/evidence/save format or raw
capture, native, backend, Build or release change. No historical report-cause or
measured FPS/hitch claim.

## Verified

Exact production relative spawn, generic SV_IOEnable, key handling, PVS chain/
eye/detach and client registry/PE_ServerTele execute in a real dedicated CPU-only
QC VM. Dependencies (touch callbacks, zone fallback, rendering/banking side
helpers, cvars/ping and target-name resolution) are explicit synthetic stubs.
24checks: baseline7intended failures, subject0, compiler0warnings, exit0.

Controls ACT: invisible spawn postcondition acts, Enable preserves clip hiding,
ordinary brush Enable still unhides, both spawn callbacks increment the count, Disable-first/Enable
works, ordinary eye is placed then actually detached by PVS-off/rewind gates,
disabled relative is skipped, missing model is removed, ordinary/landmark/nontele/
registry-cap behavior stays intact. Relative server-only snap is recognized only
inside the unchanged strict2-unit bound; same-point predicted relative/ordinary
candidates refuse quieting, while a different relative destination is not falsely
ambiguous. Point helpers are used by the real touch paths; the fixture does NOT
execute teleport collision physics or real PVS network visibility.

Both main/Pi-profile standard three-VM NoDeploy builds have0warnings. Reader949
checks pass; mandatory primary RUNS548/351fault-count incl paired views is the
actual predeployment baseline, not fault-free. Reader matches prework source.
Independent reviews, native smoke and paired deployment remain pending here. Small owner check after delivery: a familiar relative teleport (for example
surf_4am) should still pass through after enable/toggle and land at the same place;
lookahead should avoid an unnecessary destination flash. Record actual human
feedback in lextest.md, not measured performance or historical-report closure.
