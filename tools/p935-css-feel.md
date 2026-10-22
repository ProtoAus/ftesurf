# P935 — opt-in Source presentation and map-target weapon feel

## Requested end state / preregistered checks

- Weapons and movement Foley default OFF. Explicit give weapon_knife/usp/scout/glock
  and short forms opt into held presentation; original save binds remain intact.
  Unknown give commands must not be silently treated as one of these weapons.
- Movement footsteps silent at <=135u/s and crouching; above that, quieter with
  slower horizontal motion.135 is the selected CSS-style boundary, not a claim
  to have measured the proprietary game's exact sound code. Stationary conveyor
  carry remains silent. Every acted fast bhop gets a contact cue despite a
  landing shorter than the old30ms sampler. Fall/water coverage stays explicit.
- Weapon sounds are independent of foot-noise preference. Mounted model sound
  events drive draw sounds (not guessed equip timers); USP slide-back/forward
  events must actually queue. Independent viewmodel FOV must leave world FOV
  unchanged. Off must also skip weapon model/event work, not just hide its mesh.
- Rendering: reproduce sprite-over-weapon, compare normal/weapon draw ordering,
  retain world sprite behavior. Improve lighting only from a diagnosed lighting
  seam, not an unexplained global brightness tweak. Owner visual acceptance is
  the quickest adequate gate for final FOV/light feel.
- Diagnose the Goldsrc2 save2 stall, distinguishing repeated/cold asset work from
  server restore time. Do not change save bytes, restoration/held validation,
  evidence policy or owner files just to remove a delay. Owner confirms the old
  collision/prederror case and surf_me are now good: record those as human-only
  acceptance, not new performance evidence.
- Map-target dispatcher remains bounded to supported buttons/breakables and
  existing policy, NEVER players. No PvP/complete combat/ammo economy requested.

Control predictions: baseline emits footsteps below135 and can miss short hop
contacts; baseline has no USP draw event sound and shares its weapon-sound gate
with foot sounds. Subject needs positive queued cues above threshold, genuine
silent controls below/crouched/disabled, monotonic speed-volume samples, real
jump/contact edges and visible authored draw/fire. Renderer controls need an
actual overlapping sprite and drawn weapon, not an empty scene. Save latency
requires actual load acknowledgement and unchanged body/clock guards.

## Evidence so far (not deployed)

- New native Full and subsequent v44-loader build succeed; all three product
  VMs compile with0warnings. Existing ODE/COD/zlib/mathlib/VMT warnings remain;
  edited native files add none. LSP's plugin header errors are a main-engine
  database limitation, not used as compile proof.
- Factory resets prove both presentation and feet default OFF. All four models
  reach their proper named idle/ready state. CSQC-private model indices are
  negative and valid; a zero index alone is missing.
- Real dedicated actor: actual135u/s, ground1,0steps;250u/s, ground1,2steps at
  gain.6. Three authoritative jump contacts produce three queued hop cues.
  The initial contact3/cue1 arm failed: applying the walking quiet threshold to
  standing/slow jumps was wrong. Jump contact now keeps an audible gain floor.
- Actual mounted MDLs are v44, not the assumed v48. The loader supports both
  layouts and its actual source passes18focused timing/bounds/alignment/dedup
  checks. Legacy native has the event API but did not expose embedded events.
- USP draw has ONE actual event, Weapon_USP.Slideback, at native clip time.552951;
  Glock has Weapon_Glock.Sliderelease at.385648. The initial back/forward wording
  above was a tentative expectation, not two actual USP events; no second sound
  is fabricated. The mounted26181-byte weapon script has no matching definition
  for either alias. Known mounted WAV fallbacks preserve model-event timing.
  With feet OFF, actual callbacks2 ->queued draw cues2, both WAVs present, feet
  inactive/steps0. This proves emission, not human listening or sound balance.
- Owner ME and Goldsrc2 collision/movement acceptance is recorded in lextest.md.
  Machine-measured load latency is fixed below; owner load-feel acceptance is
  still pending after matching delivery.

Next rendering falsifier (registered before the probe): use the existing actual
sprites/light_glow03 world-polygon shader behind a frozen USP, compare billboard
OFF/ON in the same native client, then the matching pre-feedback native control.
The billboard must visibly act on unobstructed pixels. Where the opaque held
mesh covers it, the subject should preserve the weapon-only pixels, while the
old native must demonstrate the reported overlay. Temporary instrumentation is
owned, isolated and restored byte-for-byte before product builds; no test hook
is shipped. World FOV and viewmodel FOV are set explicitly and independently.
Owner FOV/lighting feel remains manual; no exact CS:S ambient-light model claim.

Additional runtime results:
- Held-jump standing bhops: contact sequence1->5 and cues0->4, with body still
  airborne at successive1s samples. This proves actual repeated hops, not just
  three separately pulsed presses. No footsteps/landing cues masked it.
- Giving knife when already selected still opts its hidden model in.
- Native render controls distinguish sprite-over-weapon ordering and eye-based
  cubemap/fog samples. Product source was restored after temporary probes.
- Actual Goldsrc2 slot data was copied intact into a separate private minimal
  rig. Cold control18.05s -> subject.23s to the saved body acknowledgment, both
  including100ms explicit query delay. SSQC load17.925780s -> .120870s; same
  saved clock, checkpoints and running shadow recorder. The hotspot was
  buf_loadfile's byte-at-a-time VFS reads, not the weapon renderer. This is one
  measured local fixture, not a universal timing/native qualification claim.
- tools/p935-bufload.py compiles actual control/candidate native C functions:
  160 edge/short-read cases and all137016 recording rows agree exactly,
  including append holes, blanks, NULs,8191-byte splits and CR-at-EOF. Backend
  requests fall from9335807 to144. Originals/private copied inputs remain
  byte-identical after both arms. Raw data and profiles remain private.
- Reader regression:864 checks,0 failed. Required runs corpus:419 recordings,
  283 faulting files, unchanged from the pre-P935 P924 baseline. The broader
  default sweep hit a deliberately access-denied kept save fixture; no
  permission was changed and that failed invocation is not called a pass.

Status: implemented/isolated-verified, not yet delivered. Independent frozen
review, final clean-commit build, guarded dual Windows and compatible fleet
progs remain in scope. Human visual/aural feel remains in lextest.md. No full
combat/ammo simulation, qualifying-recording claim or NanoPi native promotion
is implied. P935 was reserved before P936; highest-applied patch stays936 while
the native source pin moves for P935. A passed actor is not task completion.
