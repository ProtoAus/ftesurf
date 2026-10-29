# P1118: prepare the selected saved state before placement

Claimed one max+1 patch after fetching both repositories and inspecting headings
and untracked claims. Runtime implementation is QC-only; native commit/tag pins,
state/capture formats, tier policy, KEEP speed, Build number and release unchanged.

## Change

Normal loading used a light identity read, placed the selected body, then reopened
the file for full application. A later rejection could retain the previous clean
admission at the new body. It now captures byte/row-confirmed rows and checks
selected identity plus the existing view-clock predicate before mode, recorder,
body or run-state changes. The prepared commit consumes those same rows.

The public three-argument apply API remains for retry/resume callers, preparing
and validating before application. Preserve valid loads, existing recorder-failure
containment, inherited classifications, zone-latch tail, legacy empty-line stop
and unread-tail suppression of an optional forgiveness grant. No new taint/reset
policy or data rewrite. This binds the state snapshot, not an atomic/authenticated
state-and-recording bundle or a general native writer/compiler audit.

## Verified

- An acting baseline reproduction and five production normal-load controls:
  rejected state leaves the previous body/admission untouched; valid moving/rest
  loads retain saved speed and existing classification. Retaining a clean old
  admission is correct when the old body did not move.
- Fourteen existing wrapper/grant/malformed/duplicate/empty-tail/upright cases,
  adapted to observe the current positive deferred request and call the actual
  FinishFrame helper. Synthetic empty-I/O phase, not native newmis-drain proof.
- One prepared-API unit reads valid rows, changes the real owned disk state,
  independently rejects its new rows, then commits the original valid buffer
  with saved speed and segmented classification. Not a measured automatic
  normal-entrypoint race/open count or a real ranked-finish acceptance.
- Two independent implementation reviews: OK with bounded evidence notes.
- Fixed full build: server/menu zero warnings; two unchanged upstream client
  F333 property227 warnings, zero NEW warnings. Initial source/fixture compiler
  and prediction failures remain retained, not relabelled as passes.
- Reader suite949 checks/zero failures. The same504 recordings and167 paired
  sidecars show no increased faults. Ten current orphan sidecars pass standalone
  structural checks; no missing recording or historical orphan cohort invented.

Private fixture code, raw observations and operational checkpoints stay private.
Human moving/rest load and retry/hold feel is pending in lextest.md. General
viewing/parked replay and the deferred general native writer/compiler audit are
not claimed complete.

## Delivery

Pending the inspected feature commit and ordinary dual-Windows/Pi progs promotion.
No native/backend/schema/threshold, Build or release action is part of this patch.
