# P1159 — per-player lobby noclip and slow-flight presentation (active)

Claim: fetched both main branches and scanned tracked patch headings plus
untracked pNNN claims in owned/canonical source roots; maximum1158.

Owner clarified high-speed speedometer/energy flicker below1 is NOCLIP ONLY.
P1156 roof/duck is owner-confirmed and must remain unchanged for walking.

Implemented local candidate scope:
- Engine userinfo preference cl_noclipspeed (0=server default, .25..16 override),
  applied authoritatively ONLY to that player's Source noclip. Explicit server
  capability and native-client cvar capability; no global server cvar writes.
- Matching local-own-player prediction only; normal movement and actual
  spectators keep defaults. Existing noclip practice/run rules remain unchanged.
- Slow-camera admission for own noclip, type fences and high-speed tick allowance;
  no roof/collision clamp in noclip. Keep walking128 spherical fence unchanged.
- Stop the generic server Source velocity cap from truncating collision-free
  noclip while preserving finite sanitation, Source walking per-axis limits and
  non-Source behavior. Existing negotiated bigvelocity encoding already handles
  high speeds; no new protocol width/ABI/record format.

Local candidate only; NOT delivered. Literal old-source velocity/four-camera
counterexamples and candidate unit checks act. Official NoDeploy native/QC preview
build succeeds (only the existing warnings). Real remote UI-event-chain and
server-velocity preview passes: global16 held; wheel14.55 -> steady7566; preference2
->1040; invalid17 ->default8320. Old server ignores preference2 and alternates
3500/8320. These are not rendered HUD/camera, hardware-key or multiple-player
isolation proof. Final tagged/platform/native-bank, actual frame/role/practice
checks and two fresh whole reviews remain before guarded native+CSQC delivery.
Private raw/bindings stay under the owned task root; diagnosed fixture failures
remain retained. No owner data restoration, configuration edits or unrelated
runtime/menu activation. Preserve P1152/P1156.

First two WHOLE reviews requested changes, not acceptance. Source heads/index,
whole ranges and raw tracked bytes held; shared repository refs advanced for
published TAS clocks, so the original all-refs equality guard FAILED and remains
recorded. Integrated those published changes without rewriting their feature.
Client defaults now come from serverinfo, QW demo noclip and other actors use
authoritative interpolation, and diagnostic grace follows effective per-seat
speed. The fixture now compiles literal native Q_atof, retaining its actual
leading-number/hex semantics; no stricter parser policy was introduced. Literal
reviewed source exposes lifecycle failures; final re-review and actual listen,
demo, multiple-player/HUD/camera acceptance are still required.

The next two whole reviews also requested changes, retained without replacing
the original reports. Repaired newest replacement-entity demo type acquisition,
final fast-demo jump fence, default replacement-player lerp consumer and all
classic-QW receipt/setup/render paths. The new presentation fixture compiles
literal frame chooser, packet/classic transitions, renderer selection, decoder
and demo fresh-data/final blend consumers, with explicitly mocked animation,
collision/replay/network context; it is not a live renderer/physics proof.
Nonzero-seat wheel input is refused rather than modifying seat0's native cvar.
New internal client.h presentation declarations require one header-full SDK;
no plugin ABI/epoch or capture format change. Actual native/GUI/platform tests
and fresh whole acceptance are still pending.

Third pair also requested changes; all six reports and original bindings remain.
Held source/index/tree/ranges/raw bytes matched; unrelated shared refs advanced.
Fix own QW demo turning using packet-acknowledged recorded command endpoints,
with recorded-view fallback and priority for server fixed angles. Give locked
live/demo observers the same newest-actor/timestamp policy; free flight stays
unchanged. Map/point and angle-preserving trigger placements now emit the same
existing epoch as zone placements, only on actual origin change. Classic player
effects are only a byte: no invented teleport marker or protocol extension;
latest raw noclip pose is used rather than unsafe interpolation or viewer PM.
The widened fixture uses actual native byte serializer/parser and final render,
angle, snapshot and timestamp code. QC placement statements are adapted into C
for the producer counterexample, not executed in the QC VM. Reviewed source
fails11/31 with20 acting controls; repaired complete31 and preference/slow-camera
suites pass. Header-full SDK is already qualified before these C-only changes;
fresh incremental official NoDeploy native/QC compile succeeds, with existing
warnings only (zero SSQC warnings, unchanged two CSQC F333). Final whole review,
platform/live role/hardware acceptance and guarded delivery are still pending.

Fourth pair requested changes: two more unmarked placement producers and the
full-FTE MVD recorder's 16bit velocity mask. All8 original reports and exact
bindings remain; fourth review source/index/tree/ranges/raw/refs all held.
Censused every raw QC origin write. SV_SetPlayerOrigin now owns only origin and
its conditional spatial bit; all player non-movement placements retain existing
call order/policies and use it, including relative/public/save/resume paths.
Remaining raw calls are classified no-op relinks, non-player prop/avatar/eye
updates or the existing physical push lift. No new timer/bank/record operation.
Full-FTE replacement MVD selects existing BIGVELOCITY: literal recorder mask,
SV_EncodeVelocity, payload writer and decoder are exercised before the final
consumer. The narrow-width and replacement-disabled controls remain. No new
protocol bit, bank/.rec grammar or API epoch. Reviewed source fails5/38 and
33 existing controls act; corrected38 and slow-camera suites pass. Actual QWD
replay turns129 degrees and retains ~1040 native speed with viewer preference16
instead of recorded2, but its expected scale-stat assertion fails (observed0);
that retained trace is not a passing whole-demo/final-source acceptance. Official
NoDeploy source update succeeds: zero SSQC warnings and unchanged two CSQC F333,
no new native warnings, prior header-full cache still valid. Independent whole
review, platform/live roles/hardware and guarded delivery are still pending.
