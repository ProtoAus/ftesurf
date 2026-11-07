# P1359 — ordinary recording-version numeral spelling

## Status

Implemented, independently reviewed and published. Both Windows reader installs
and ARM source qualification are verified. NanoPi live helper installation is
pending its required actual-process namespace authentication; P1356 helpers remain
live there. No NanoPi fence, service, namespace configuration or database was
changed by this patch's preparation. A passing source test is not a live-process,
native-engine or fleet claim.

## Root cause and change

The two ordinary recording consumers delegated a version token to Python's
integer parser. Python-only numeral notation could therefore publish accepted
version metadata or reach a scored similarity stream. In the similarity reader,
raising an ordinary conversion error inside the old try block would not close
that path: the handler assigns version zero and can continue comparing moves.

The change rejects underscore/non-ASCII version tokens before integer conversion.
Similarity reaches the existing malformed-recording refusal outside that fallback,
including version-bearing lines its existing pre-body branch recognizes. Recording
checks use their existing version fault and return before publishing version or
held-status metadata. No magic, whitespace or tokenization rule is tightened.

ASCII signs/zero padding, other malformed-ASCII fallback and unsupported-version
dispatch are preserved. Native held records still require their existing exact
framing, hashes and structural rules; this patch does not make alternative signed
headers valid native records. Ordinary input-number compatibility remains as in
P1356. View/ramp-special parsing and whole-header grammar are outside this patch.

## Acting source evidence

- Published reader control: 13 methods run, 24 failing subcases across the changed
  admission/CLI/collector cases, no loader errors. ASCII compatibility acts and
  passes on that control. The candidate passes all 13 methods.
- Normal actual subprocess CLI compares 80 inputs; the header-malformed arm exits
  1 with the existing unavailable explanation and no metrics. Both source files
  remain byte-identical before/after. This tests argument parsing and launch, not
  merely a helper function.
- Both pair orientations; standalone and bounded reads; repeated pre-body version
  branch; source bytes unchanged; withheld version/held status; ordinary positive,
  real unequal, compatibility, native 13/15 and collector capture controls act.
- Legacy partial-reader tests: 23 pass. Held tests: 39 run, 38 pass and one skip
  because the paired native-source root was not supplied to that invocation.
  Supplying the inspected paired source separately exposes the same existing
  hardcoded version12-versus10 assertion on the published control and candidate.
  The untouched check is retained, not repaired or called a native-pin pass.
- Recording-reader suite: 949 checks, zero failures.
- Current corpus: 554 REC and 178 VIEW files, including ten standalone views.
  Both checkers' entire output is identical; 351 existing faults remain unchanged.
  All swept raw input bytes are identical before/after. This is preservation,
  not a calibration, authenticity, or genuine-device measurement.

Run the focused cases with `python tools/test_input_numeric_spelling.py -v` and
the grammar suite with `python tools/test_reccheck.py`. Existing source-path
selectors let the same controls bind explicitly to reviewed installed artifacts;
that is not by itself proof of a production process's default module resolution.

## Scope and limits

No recording writer/capture format, metadata ABI, clock-model expansion, stored
observation rewrite, threshold/default/ranking policy, native source/tag/pin,
VM layout or QC Build number changes. The version-token guard is structural
input admission, not proof that an accepted record is native or authentic.
Other malformed-ASCII fallback, whole-header grammar and special view/ramp paths
remain separate work. No historical scores are reclassified or backfilled.

Delivery must preserve original helper bytes/metadata, bind the actual current
runtime and namespace, retain current-data rollback, and verify destination hashes
and acting controls. No installed state is inferred from source results alone.

## Delivery evidence — 7 November 2026

- Public implementation `9aed683a86f3f800b3c0e26506274ff827ab1eef`;
  engine ledger `f67cbeed8ffa255cf193790808586f682e47539d`. Two independent final
  reviews cleared the frozen narrow source diff, with no must-fix findings.
- Both Windows installs: four actual helper hashes and ACLs verified; original
  files retained. Thirteen methods pass on EACH install with explicit module-path
  assertions, real CLI and collector calls. Shared Git index unchanged. An initial
  PowerShell null-string ReplaceFile refusal occurred before the first swap;
  the same four staged artifacts/backups were verified and continued after an
  isolated API smoke check, not discarded or replaced with another transaction.
- ARM aarch64: 13 focused methods, eight parsing plus 15 held-reader methods, and
  949 recording checks pass. The original small overlay was completed with two
  missing source-only test dependencies; loader/ownership-marker/writer-contract
  refusals remain retained. Previously passed arms were reused, not rerun to
  manufacture a clean uninterrupted invocation. All 15 staged source hashes and
  synthetic-fixture cleanup were verified.
- NanoPi: the actual intended helper-only preflight reaches the required nsenter
  operation and refuses missing authentication BEFORE any resource hold or live
  mutation. Fresh readback confirms the same OPEN runtime, process and 158 bound
  files, with both P1356 helpers unchanged. Host-only qualification is not actual
  namespace acceptance. The pending update will keep the existing runtime84,
  namespace configuration, cron routing and current database; no old DB restore.
