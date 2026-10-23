# P943 — Source weapon controls and Foley follow-up

Reserved after fetching both repos, max942; owned source-polish root reused.
Bases QC b5965bf0 / engine3c224b2aa; canonical peer changes/index untouched.
Owner confirms P941 bob/sway look much more accurate (human acceptance for that
observation only). The new controls below still need human feel/ear acceptance.

## Scope / pre-registered falsifiers

- Foley: replace deterministic0,1,2,3 cycle with random choice within each authored
  foot side. Adjacent walk/jump/landing cues inside120ms coalesce. Actual movement
  must emit; quiet walk stays silent; metadata cache must still act.
- Held primary knife repeats; alternate stabs on +attack2. P941 control must act
  once, then NOT repeat. Cooldowns bound both; no player damage/pushing.
- USP starts unsilenced using real idle/draw/shoot *_unsil clips; secondary
  attach/detach uses authored3.108s animation/events and blocks firing meanwhile.
  Its silencer is an animated bone, NOT a model bodygroup.
- Glock secondary toggles single/burst:3authoritative map traces60ms apart,
 500ms repeat cooldown; cosmetics schedule matching three cues from one event.
- Bare knife/usp/scout/glock equip like give aliases. Default viewmodel FOV75
  when unset; preserve an explicit value and ALL personal keybindings.
- Scout shoot5004 Weapon_Scout.Bolt at .289*1.314s must actually emit. Old code
  discarded non-draw events. Use existing native inout cursor, only5004 sounds,
  not numeric5001 muzzle events as sound names.
- Shot punch is render-only: exact critical damping per real render delta, not
  66Hz/network angle steps. VF_CL_VIEWANGLES/input/body/aim/sidecars unchanged;
  restore VF_ANGLES immediately after main scene. Compare100Hz/1000Hz math and
  actual motion/return. Sustained1000FPS is NOT assumed or claimed.

## Implementation boundary

Server owns selection, mode, cooldowns and map damage. Existing byte
STAT_WEAPONFRAME packs5-bit event serial,1-bit mode/player-contact,2-bit kind.
No new stat/channel/native protocol. Burst follow-ups cancel on equip/spawn/hold;
no firing while unarmed. Existing shared-map damage permission is retained.

Client model, authored sound events and visual punch are presentation only;
replay/hold/spectator gates remain. Only USP/Scout receive the two-degree-peak
pulse. Recording reads VF_CL_VIEWANGLES, not temporary scene VF_ANGLES.
No mover/input journal/recorder/evidence/collector/PvP/Build/release change.

Owner heard our FIRST draft's wrong flesh impact on an empty alt-stab during
native testing: valid rejection. Corrected swings use knife_slash1/2 whoosh;
knife_stab/hit sounds require server-confirmed PLAYER contact. The knife's
read-only ray temporarily includes PLAYER dimension2, then restores original
mask/dimensions/vectors. Player classification returns BEFORE any damage call,
independent of map damage policy; no health/velocity/origin is written. Impact
feedback is local to the attacker. Empty wall swings retain the existing wall
cue. Personal mouse2 is NOT rebound (default surf controls use it for turning).

## Actual controls and limits

- Baseline native P941: primary held1450ms ->1slash, secondary1400ms ->still1.
  Candidate: primary ->4slashes; secondary ->2stabs, source/client counts agree.
- Native USP screenshots inspected: no silencer initially, attached after authored
  mode clip, removed again.5004 attach/detach cues emitted. Shot paths switch
  usp_unsil-1/usp1; no fake bodygroup or new assets shipped.
- Glock single ->1projectile; one brief burst press ->3both client and server,
  pending0 afterward; secondary returned to single. Only one authored burst
  animation starts, not three restarting animations.
- Scout emitted weapons/scout/scout_bolt.wav from the actual shot event.
- Native punch reached-1.99448degrees, then-1.20083, then-0.0023153; returned
  render/input angle storage stayed0. At cap1000 the observed delta was about
 1.5ms, NOT measured sustained1000FPS. Analytic100/1000Hz samples agree in
  artifacts/p943-kick-math.json, peak-1.99999994, without a frame-rate-dependent
  Euler integrator. This is cosmetic Source-like recoil, not ballistics/spread.
- Actual Momentum Axiom samples varied while retaining14metadata reads/1surface
  scan; one running-jump edge coalesced into its preceding step (merged1,
  contact-seq1), rather than a second cue. An earlier quiet arm overlapped a
  landing and is NOT a pass. Corrected settled135.2u/s arm kept total calls5 ->5.
- Fresh no-FOV-override client printed75; explicit startup91 printed91. A quoted
  empty command-line override had produced0; that was an invalid default control,
  not a product defect. A reconnect info command issued before CSQC loaded was
  lost and is NOT preference evidence.
- Two actual placed clients: an aimed chest stab returned contact1, played
  knife_stab.wav; both health100/dimensions2/1, target origin unchanged. Empty
  stab produced only knife_slash1/2 and contact0. That acting pair used map damage
  policy0. Policy1 attempts had either unplaced peer or an off-ray random spawn:
  NOT policy1 contact passes. Unconditional early player return + unchanged
  no-player-damage policy are the code safety boundary; no stronger measurement
  or owner multiplayer acceptance is claimed.
- This is not every map. Generic material lookup, bounded metadata caching,
  authored left/right aliases and missing-content fallbacks are map-independent;
  actual traversal controls cover Axiom and existing material selectors only.

## Failed controls / preparation

First draft did not compile: exp()/argc() are not QC builtins. Fixed with pow()
and argv checking. Eight sprintf VALUES plus format exceeded the compiler's
varargs limit; split diagnostic lines, then three VMs0warnings. An overlong341B
bridge line refused before write; split to supported<240B lines, no wrapper chain.
Minimal peer initially missed default.fmf, then native HL2 loader/assets, reporting
world as corrupt. Compared the proven cold-smoke preparation seam, added matching
native loaders/public assets to SAME owned peer root. Actual placement/health100
then acted. Timed waits are not readiness; later external-peer readiness used the
same observed nonzero-position contract as conbridge.connect, bounded60s.
All these failures remain in owned artifacts, not relabeled passes.

## Lighting remains a separate in-scope continuation

CSS screenshot cl_showpos: pos -2752,0,-31.97; angles .45,.08,0. Owner's new FTE
view loads surf_axiom_css (CSS BSP under a different name), at a different spot.
Converted TGA under owned artifacts only. Native cubemap loader currently builds
materials/maps/<LOADED basename>/cX_Y_Z.vtf; a renamed BSP's authored namespace
must be checked, in addition to matched map/camera/FOV/idle phase, before judging
remaining shading. No global brightness hack or lighting-parity pass is claimed.
Continue this after gameplay delivery; this is NOT permission to stop that work.

## Final source / delivery

Final exact hashes/clean commit/dual Windows/Pi/cold-client provenance are in
p943-delivery.md after verification. Native939 unchanged for this QC feature;
no owner process/config/map/player data touched. Owned fixture actors stopped;
failed history and needed immutable control files retained in the task root.
