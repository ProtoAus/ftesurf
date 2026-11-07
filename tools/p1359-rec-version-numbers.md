# P1359 — ordinary recording-version numeral spelling

## Status

Implemented, independently reviewed, published and installed on BOTH Windows
installs and the NanoPi. Owner executed the reviewed authenticated helper update;
the primary completed. Fresh7November07:02:30UTC readback binds the actual namespace
acceptance receipt to the current process PID/birth/CWD, verifies destination
hashes, OPEN admission, active backend/importer and health. Runtime84, namespace
configuration and current database were preserved. Source, native-engine and
whole-fleet claims remain separate.

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
- Source-time corpus: 554 REC and 178 VIEW files, including ten standalone views.
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
- NanoPi initial preflight: actual nsenter refused missing authentication BEFORE
  any resource hold/live mutation; original refusal/readback evidence is retained.
  It was not relabelled as namespace acceptance or bypassed.
- NanoPi delivery: owner then authenticated and executed the reviewed primary
  helper-only update. The guard actually reported CLOSED/draining then DRAINED;
  it waited for cooperative work rather than printing continuous progress. The
  primary completed without a fallback/recovery-failure artifact. BOTH actual
  helpers match the reviewed candidate hashes and all13 installed-reader cases
  pass, including module-origin assertions, CLI and collector controls.
- Fresh completion audit7November07:02:30UTC: current service PID/birth/CWD matches
  the actual default-namespace acceptance receipt; OPEN admission, backend and
  importer active, health OK. Unchanged runtime84/namespace configuration/held
  metadata helper and restored canonical launcher are verified. Current-data
  cutover audit retains schema26/all44 tables and the eight identity digests;
  no old database restore. Synthetic temporary fixtures are cleaned. The first
  observer compared a projected pid/birth record to the full process record and
  refused; corrected explicit PID/birth/CWD binding retained that refusal without
  weakening identity or freshness.
