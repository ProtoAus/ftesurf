# P1543 - TAS board-event restore continuity

Status: **source candidate, not deployed; real-socket recording acceptance pending**.
Native candidate source:422feac19667b9a1151eea57dd001b58c6d53066.
This fixes a recording-observer seam, not JARGON's final-ramp pathing or speed.
Do not call an in-game finish a valid/native-verified recording.

## Cause and bounded change

A native TAS checkpoint already owns and restores `pmsourcestate_t.boardcount`.
Previously, `SV_TASRewind` did not publish that restored value to QC immediately.
`SV_TASGo` places/cuts the recorder before applying the native checkpoint. A warm
buffer cut left `rec_rec_lastbc` at the abandoned future; a streamed cut reset it
from the still-stale public value. On resumption a counter change could therefore
be the restoration itself, not a new ramp arrival. A retained completed control
had the repeated board2 row near5.49 seconds.

The native restore now publishes its carried counter alongside its existing
fractional-carry publication. Only after native restore succeeds, QC aligns the
writer's board-change latch to that value, before freeze settlement and new TAS
head capture. A genuine subsequent arrival still increments the counter and is
recorded. Native count restoration and QC observer alignment are both necessary.
No recording reader, format, rank, simulation equation, scoring, search, clock or
Build change is included. Old recordings are neither edited nor regraded.

## Evidence and exact limits

- `tools/test_tas_board_restore.py` extracts the production native capture and
  carried-state restore block, and the complete `SV_TASGo` / `SV_RecBoard` QC
  functions. The native fixture passes24 count/optional-field combinations,
  including absent optional fields, unrelated carried state, plan rebind and
  unchanged connection tick/epoch. The actual QC functions pass29 assertions:
  observer alignment before head capture, no row for a resumed non-arrival,
  first genuine new arrival retained, skipped counters, zero-normal reset,
  closed recorder, and failed placement/native restore. Original engine47998d6e
  and QC15205167 each fail independently at the specific missing-publication or
  stale-latch assertion. Synthetic API/world/arrival stubs do **not** prove full
  restore admission, actual physics, warm/cold session transactions or complete
  recording/native verification. The original minimal fixture exposed its own
  unrecognized system header warning; using the actual unchanged system prefix
  then required the nine unused standard entrypoint bodies. Both failures were
  retained. The final fixture has recognized system defs and zero warnings;
  no warning was suppressed and no product source changed to accommodate it.
- Existing three-VM `build.ps1 -NoDeploy -Jobs 2`: zero warnings in each VM.
  Its first invocation refused before compiling because the isolated tool lookup
  lacked fteqcc. Adding the existing installed compiler directory to PATH fixed
  the supported discovery seam; no compiler/build-script change was made.
- Unchanged reader regression:949 checks /0 failures. The first wrapper timed
  out at120seconds; the live-log rerun completed. A subsequent log-decoding
  exception did not invalidate or rerun the completed tests; their949/0 footer
  was read directly. No reader code or validation rule was relaxed.
- Stable captured current corpus:570 recordings,173 associated views,352 faulty
  REC files and6 faulty VIEW files. The reader source is byte-identical to the
  published baseline; existing faults remain faults. No player files were
  changed. Private per-file evidence is not exported. Initial import/data-type
  observer errors occurred before a sweep and were corrected against the actual
  reader API; they are not reader failures or passes.

## Remaining acceptance and pathing work

The native gameplay guard currently refuses below2500MiB free RAM; a prior
continuation diagnostic refused before spawning any actors. No guard is weakened
and no other process is killed. Full native build/review and a fresh matched
same-image dedicated-socket TAS finish must establish strict complete-recording
acceptance before deployment. Native and QC deployment must be paired; the
ordinary dual-Windows and guarded fleet rules remain in force.

Separately, compare JARGON's *played* checkpoint endpoints with its predicted
endpoints. Only if those agree should the bounded entry-to-finish handoff
experiment compare several actually played final-ramp entries with the existing
finish continuation. The previous native-window candidate was slower and was
removed; simply searching more entries is not an improvement. No pathing or
performance win is claimed by this recorder fix.
