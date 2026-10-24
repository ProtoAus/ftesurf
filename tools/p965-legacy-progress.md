# P965 — bounded older-save progress fallback

`SV_SaveApplyState` has an explicit compatibility path for states predating
Momentum progress records. Its old single boolean combined a nonnegative
armed-zone test with zone-table accesses. QC does not short-circuit boolean
operands, so the supposedly protective test still permitted an invalid table
read and a native VM stop.

The fallback now validates the armed-zone scalar's range and integer shape
before entering a separate table-reading condition. A matching region of the
saved leg still wins (including twin regions); otherwise the existing ordinary
leg lookup and final fallback remain. This is not a general save-file validator,
new recording format, changed clean/practice eligibility or capture feature.

## Acting evidence

- The retained old-code native compatibility control actually stopped at the
  negative table lookup. Its exact faulty basic block remained unchanged
  through P964, so that control is reused rather than gratuitously rerun.
- Actual native production save parsing, restore and progress functions execute
  eight cases: absent metadata, negative indices, current-count and backing-array
  overruns, fractional index, matching twin and a valid index on another leg.
- Every case completes its restore, acts its recorder rewind/append doubles,
  and reopens the expected post-append stage slice. The positive twin control
  selects the saved twin rather than blindly choosing the first region.
- Recording rewind/writes are test doubles. These are NOT signed receipt,
  actual cold reconstruction, posted stage, native movement or human acceptance.
- Existing reader regression evidence remains applicable: this patch changes
  neither Python reader code nor historical recordings or evidence grammar.

## Verification and delivery

The standard NoDeploy/Jobs8 build passes for all three VMs with zero warnings.
Both independent source reviews report no blockers; the parent recomputed the
frozen file's byte hash and accepted the match. Reviewers' hash attribution is
explicitly supplied-witness only. Source8a86dc3d is published via inspected
merge ebbb1aff; engine record2e6a5b1c via3befcd32. Concurrent P966 work and
highest patch metadata were preserved, not included in the server promotions.

Windows delivery at2026-10-24T11:39:26Z: qualified public composition26f20a55
installed server DAT/LNO in BOTH installs, checking exact P964 predecessors.
All11fresh current native/client/menu/config hashes remained unchanged; ordinary
.prev and prior history retained. No Windows process was signalled; installation
is not a claim that an already-running process reloaded or owner play passed.

Pi public composition0577d431 qualifies3VMs/0warnings: server is byte-identical
to reviewed main production output and client is byte-identical to the actual
fleet. NOT DEPLOYED: real boundary directory connection was refused before any
retention/staging/swap/restart. Actual progs remain P964, no .new exists, no P965
remote phase was created. The intentionally dead systemd surfd unit is not its
process authority; actual pidfile is absent and local directory unavailable.
Do not restart a peer backend or reuse an old guarded transaction. Resume this
ordinary promotion only after directory/ownership recovery and fresh canonical
witness, paired hashes, native/reader pins and empty-socket/directory checks.
No native pin/tag, Build or release change is claimed.
