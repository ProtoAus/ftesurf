# P927 — mounted CS:S movement Foley

Local client presentation only: CS:S steps, landing impacts and water movement
from the owner's mounted packs. No Valve samples are copied into this repo or
redistributed. cl_game_sfx0 disables,1 is normal volume (intermediate values
scale it); gameaudio_info reports available packs and queued-effect counters.

## Implementation

The frame observer reads native pmove_org/simorg, not eye position, so visual
head duck does not move the sampled feet. Actual player-relative velocity gates
steps: a belt carrying a standing body is not walking. Flat travel accumulates
86units per step with a minimum.18second spacing; the observer samples at most
once/.03second, independent of render FPS. Genuine landings, water entry/exit
and water movement use mounted WAVs. Swims include vertical motion. Water depth
uses the current62/45-unit standing/duck hull's middle. Warps/disable/mode changes
reset latches rather than replaying accumulated travel.

Spectator ownership, watch, rewind, detached ghost and non-walking movement are
excluded. Nothing writes usercmds, server state, evidence or qualification. No
native rebuild/pin change and no Build number bump. Texture-name families
provide approximate concrete/metal/wood/tile/etc selection; this does NOT claim
to interpret every authored VMT $surfaceprop. Missing/partial packs stay silent
instead of making repeated missing-sample errors. A late mount can be refreshed
with gameaudio_info refresh.

## Acting checks

Native source/tagP924 and real dedicated sockets,100fps and normal extrapolation.
Three VMs compile0 warnings. In dune, cl_game_sfx0 moved about159units with no
new queued calls. Enabled moved152units and queued the mounted
player/footsteps/concrete3.wav once. One second of actual rest added nothing.
A real jump/land added one landing callback using concrete1. Availability probes
found both CSS samples and the shared HL2 fall-pain sample in the actual VFS.

In parc's real water brush at416..440Z, a normal zone-goto above the water,
crouch/fall and forward motion reached depth2, moved about47units and queued
one water-entry plus two swimming calls using mounted wade samples. Releasing
duck reached depth1, not0: EXIT WAS NOT ACTED or claimed passed. The owned test
zone was restored byte-for-byte with a current-hash ownership guard, and all
owned bridge processes stopped. Canonical zones/player data were never changed.

The background fixture used s_inactive0 to avoid interfering with the owner's
running game. Counters/file availability prove selected queued effects, not
speaker/headphone output, volume balance or subjective feel. Human acceptance
is deliberately small and pending in lextest.md: flat walk, jump/land, water
entry/movement/exit. Hard-fall voice and other materials remain untested.

The minor water refinement (correct duck middle and vertical swim speed) leaves
the dry step/landing path unchanged; its rebuilt three-VM subject passed the
water arm. Reader864/0 and identical-reader corpus checks from P924 remain valid:
this feature changes no writer/reader/evidence/native dependency.

## Delivery state

Implemented and fixture-verified, not yet installed or owner-accepted. Windows
was guarded by an active canonical game; Pi has occupied lobbies and an
independent P923 mainline-producer/native acceptance hold. Do not force either
or promote a partial producer set. Compatible fleet source, if used, needs its
own clean commit, acting smoke and provenance. Weapons/viewmodels remain a
separate active part of the original task, not excluded by this patch.
