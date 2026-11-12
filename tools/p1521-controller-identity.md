# P1521 - Controller turn is outside the recorded keyboard term

## Problem and bounded change

The client taps the keyboard contribution before calling the movement input
backends. Native joystick movement subsequently changes the view accumulator;
those changes are not present in the existing journal's keyboard-turn columns.
A namespace-correct device table alone does not make that angle reconstructible.

Keep the control arithmetic and existing record meanings unchanged. Native
observation marks an actual change to the primary view accumulator during
joystick movement and uses its existing skipped-frame counter. Begin and normal
or quiet view emission reset the private marker. Other seats and inputs that
make no actual accumulator change do not mark it. Inactive/full capture does not
acquire new controller state.

Offline analysis has neither the controller mapping nor its persistent initial
axis state. Assigned controller entries in either device table, or actual axis
records, therefore use the existing unsupported-profile exclusions for BOTH
axes. No axis record during a capture is not proof that an assigned controller
was idle. Empty unassigned slots alone do not disable mouse comparisons.

The existing receipt consumer reports this content BLIND, not OK. Judged metrics
are absent, not measured zero. Existing parse/capture-quality, device-namespace,
pad-budget, digest and signature-separation checks remain effective. No new
capture, wire/schema, threshold, policy, ranking decision or historical regrading.
QC Build remains 89.

## Acting controls and qualification

- Parent literal native controller arithmetic produced a turn absent from the
  keyboard term; the prior live observer and offline comparison both failed
  29/29 relevant frames. Unmapped/zero/null controls actually judged 29 clean.
- Subject literal native deadzone, joystick movement, identity and view-emission
  functions executed 300 rows in a declared minimal context, zero compiler
  warnings. The original 120 motion rows are identical. Look/pitch/roll each skip
  29 with zero bad. Unmapped/zero/null/zero-scale/other-seat controls each judge
  29 clean. Inactive/full captures emit no views or new controller markers.
- Actual view quiet/normal reset and the following mouse frame act. The begin
  reset was inspected in source, not executed as the whole begin transaction.
  Callback/time services and clamp folding are adapters: this is NOT a full-game
  lifecycle or real-hardware/controller calibration result.
- Windows HID 606 checks, receipt 413 checks, recording reader 949 checks: all
  pass. Actual captured-byte receipt controls retain BLIND/FAULT/OK distinctions,
  digest checks, withheld invalid input totals and independent signature status.
- Same-byte 136-HID corpus: three faulty files, identical fault lists. Supported
  recording-reader main over 568 REC arguments automatically pairs VIEW files:
  356 faulty reports unchanged; all 751 REC/VIEW input hashes remain unchanged.
  Invoke the supported main in-process for this existing large argument set;
  Windows CreateProcess exceeds its command-line limit. No replacement parser.
- Supported isolated `src/build.ps1 -Jobs 8 -Engine -Full -NoDeploy` succeeds:
  three QCs have zero warnings; native warning messages remain 74 in both actual
  baseline and subject (zero new). Neither Windows install was changed. Missing
  local compiler/dependency inputs were repaired in the owned staging area, not
  by disabling codecs or borrowing another task's source changes.
- clangd database regenerated for this engine; diagnostics retain six existing
  warnings outside the change and no new errors. LSP is not runtime evidence.

## Delivery and remaining limits

Source qualification is not deployment or independent review. Required final
native/reader/consumer reviews and real-controller checks remain pending. No
installation, lobby, backend, player data or runtime configuration was changed.
No ARM/full-game/human result is claimed by this packet. The native audit lane
remains separately deferred; this change is an observer-attribution correction,
not a claim that input provenance or human-vs-script classification is solved.
