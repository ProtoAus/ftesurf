# P1359 — ordinary recording-version numeral spelling

## Status

Implemented and source-verified. Independent final review, publication, ARM
qualification and installation are pending. The working P1356 deployment has not
been changed by this patch's source checks. This document separates those states;
a passing source test is not a live-process, native-engine or fleet claim.

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
and acting controls. Publication and deployment evidence will be recorded here
when completed; none is inferred from the source results above.
