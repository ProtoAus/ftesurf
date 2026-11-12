# P1518 — input IDs have namespaces, not global hardware ownership

## Problem and bounded change

The actual native pointer, keyboard and joystick allocators search independent
arrays. Keyboard0, mouse0 and joy0 can coexist. The reader instead keyed every
claim by its numeric string, producing false duplicate-identity faults. It also
counted `j` joystick axes as pointer motion, so joystick1 could falsely exceed a
touchpad1 accepted-report budget or account for an otherwise missing pointer.

Claims now include the actual input namespace. Mouse, touchpad, tablet and XTest
route to the pointer array; keyboards and joysticks have their own namespace.
Conflicting names within one namespace still fault. Tagged joystick axes are
counted independently; another namespace cannot account for an unclaimed stream.
The new local axis count is not a new durable receipt metric or captured field.

Raw-key identity remains unavailable where it was unavailable. Legacy keyboard
input uses a hardcoded0; non-keyboard keys can have their own IDs, and devices can
vanish. Neither table presence nor absence invents keyboard/hardware provenance.
This is bookkeeping/data quality, not physical-device attestation or player guilt.

No native code, producer, grammar, capture/consent policy, calibrated threshold,
angle equation, signature-verdict, ranking rule, native pin/tag or QC Build change.
No historical file, stored observation or player grade was modified.

## Acting evidence

- Literal native `Joy_AllocateDevID`, `Mouse_AllocateDevID` and
  `Keyboard_AllocateDevID`, compiled in minimal declared arrays: **5 actual rows**,
  zero compiler warnings. Fresh IDs0/0/0; reserve mouse0 then pointer1/keyboard0/
  joy0; reserve touchpad1 then2/0/0; reserve keyboard0 then2/1/0; reserve joy0
  then2/1/1. This is allocation-contract proof, not a live-device capture.
- Exact published P1516 reader with added fixtures: **570 checks,20 failed**.
- Subject HID suite: **570/0 on Windows and ARM**,35 new assertions. Shared-ID
  arms contain actual pointer/key/axis records and19 mouse-angle comparisons;
  same-namespace conflict, unclaimed cross-class and real pad-budget controls act.
- Actual standalone CLI: both healthy arms fault on the old reader and pass on
  the subject. Same-pointer conflict and actual20pad-motion/zero-accepted controls
  still fault. Joystick axes cannot mask or spend the pointer counter.
- Windows receipt suite: **408/0**, including20 new captured-byte consumer checks.
  Actual digest checking and20view/19judged-yaw metrics act; healthy measured-zero
  input counters are retained, faulted input counters withheld, signature state
  unchanged. These content joins do not verify a new signature.
- The original P1516 withholding test inspected the outer versioned wrapper and
  could silently pass. It now inspects `journal_metrics["metrics"]` with paired
  healthy-zero controls. Early new fixture assertions also used the wrong wrapper;
  failures were retained and fixed at that seam, not by changing the schema.
- ARM actual captured-byte smoke: **4 cases**, both healthy content statuses OK,
  both conflict/pad controls FAULT; real digest and20/19 metrics act, input-counter
  withholding/signature separation preserved. Full ARM receipt suite was **not
  run**: flat HID stage lacks the backend `test_sweep` fixture. Missing pure-reader
  supports were copied explicitly for the smoke; no replacement test framework.
- Recording suite **949/0**. All existing136HID/568REC/183VIEW bytes unchanged.
  HID retains3faulty files and identical fault lists. The supported REC main pairs
  existing sidecars and retains349REC/7VIEW faulty reports,356 total. Two custom
  corpus callers incorrectly used unpaired views/assumed all views had recordings;
  their failed comparisons are not product regressions or parity evidence.

Supported QC NoDeploy metadata build and exact scoped source publication are
recorded with the feature. Native commit/tag and Build remain unchanged.

## Delivery limits

Source-qualified does not mean independently reviewed, deployed, complete capture,
real-device acceptance or human calibration. The installed shared reader has peer
work and was not overwritten. Existing independent final-source review and normal
guarded deployment requirements remain; they block promotion, not continued work
on actual independent anti-cheat defects. Legacy capture completeness and the
non-default console codec limitations from P1515/P1516 remain open.
