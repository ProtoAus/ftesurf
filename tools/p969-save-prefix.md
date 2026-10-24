# P969 — buffered save confirmation is not a memory mark

## Implemented

`SV_RecWritePrefix` now reads the native file back into a separate string buffer
and compares the exact logical count and every row against the requested prefix.
A successful open, nonzero size or matching count alone is not confirmation.
The existing mark still describes live memory: losing a disk copy must not cancel
a valid matching same-attempt rewind.

The additive save key `recprefixok` carries disk confirmation (0/1) separately.
The key reader defaults absent metadata to historical uncertainty. Rewind consumes
this metadata like the existing byte-count metadata, tries valid warm lineage
first, then refuses an explicitly unconfirmed cold buffered copy. Newly confirmed
cold copies must still have their stated row count. Multi-Session clears this
plain-save metadata before using its own contract. The seven-argument interface,
stream snapshot/copy path and recording formats remain unchanged. A failed
confirmation warns without dropping the current recording.

No native code/pin/tag, input collection, detector threshold, Build or release
change. Save metadata is not a signed statement or a new trusted input source.

## Verified so far

Preregistered actual native production writer, save-key writer/parser and Rewind
API: 12 controls and 12 subjects on the same retained dedicated image; both
compile with zero warnings. File and buffer IO are real; only sprint output is
intercepted for the synthetic entity.

- Normal, first-two-row subset, empty middle row and 6000-byte row act.
- Blocked/stale physical outputs retain matching warm memory. New failed disk
  confirmation refuses cold use rather than accepting the stale rows.
- A file confirmed at write time but later changed to a different row count is
  refused cold, while the original warm memory remains usable.
- The no-key/legacy context remains unbound. A separately reset caller does not
  inherit a poisoned plain-save status; per-save output is consumed once.
- Deliberately inconsistent/sparse synthetic memory keeps its old warm behavior;
  this is not a memory-integrity validator. Its disk copy is not confirmed.

The initial return-zero-on-failure draft was rejected in review for breaking the
warm path. It was preserved, not published/deployed. Compiler diagnosis also
corrected an implicitly constant initialized global: per-call outputs must be
mutable and are initialized by the writer. No compiler modification was needed.

The existing standard NoDeploy build compiles all three VMs with zero warnings.
The required reader suite passes 924 checks, zero failed. The actual runs sweep
checks 430 recordings and 126 paired views: the same 294 existing rec/view faults,
with all 556 original hashes unchanged, not a clean corpus. The known protected
save-prefix/default-sweep read failure remains separate and unwaived. An initial
concurrent reader run hit MemoryError; the unchanged suite passed when serialized
after compiler exit. No reader/resource guard was relaxed. A manifest-domain
mismatch was corrected to the original recordings-plus-paired-views domain;
orphan views, HID and PB files were not modified, deleted or called newly added.

Two fresh independent source reviews of candidate `0e172504d1a7` found no
introduced issues: control-flow/compatibility verdict OK; storage/evidence and
model-scope verdict OK with notes. These bounded recorder reviews do not close
the broader anti-cheat rule8 audit or remove the limits below.

## Limits and delivery

These are writer/key/Rewind API controls, not an actual full saved-state load,
engine/push simulation, signed recording, verifier/posting, performance measure
or owner acceptance. Logical readback is not a byte seal, durable/atomic pair of
state and prefix, protection against later same-count content changes, or
plaintext-save authentication. The remaining pair/binding issue stays in
BACKLOG.md. Old slots are not retroactively confirmed or rewritten. Stream-copy
completeness and unrelated recorder-state bugs are outside this bounded fix.

Main source/review records are published. Clean compatible Windows source
`7ea12fb6` is published and its server DAT/LNO are actually installed in BOTH
Windows installs: four destination hashes, .prev/older-prev history and 21 fresh
protected native/client/menu/plugin/config/tool hashes were verified unchanged.
No process was signalled or existing owner session claimed reloaded. Normal
save/warm-load/cold-load human acceptance is requested in lextest.md, pending.

The Pi directory recovered with 12 rows/one player at the new read-only boundary;
there was no stage, restart, phase or backend action. The cumulative compatible
source builds without warnings, matches qualified main QW and has no client code
change. Its client differs from the retained live file only in one compiler-banner
local-date byte after midnight. The full client hash guard was retained; no banner
was edited or clock changed. The owner was asked whether to allow the date-only
refresh or retain exact current client bytes. Pi promotion remains pending that
choice and fresh empty/ownership/pin gates. An earlier source composition being
published does not mean it was applied. This is not a Build or release.
