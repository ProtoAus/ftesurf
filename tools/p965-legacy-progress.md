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

## Pending

The standard NoDeploy/Jobs8 build passes for all three VMs with zero warnings.
Both independent source reviews report no blockers; the parent recomputed the
frozen file's byte hash and accepted the match. Reviewers' hash attribution is
explicitly supplied-witness only. Publication and isolated cohort promotion
remain pending. P964 delivery is separate and retained; no live
install or lobby has received P965 merely because its native fixture passed.
No native pin/tag, Build or release change is claimed.
