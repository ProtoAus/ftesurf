# P931 — basic mounted CS:S held weapons

## Use

Default is knife. `surf_weapon knife`, `surf_weapon usp`, `surf_weapon scout` and
`surf_weapon glock` select the four choices; `cmd weapon <name>` is the validated
server equivalent. Existing binds are UNCHANGED:1/2/4 are save controls here,
not free inventory keys. Existing +attack fires once per press. cl_viewweapon0
hides the model; cl_viewweapon_left1 swaps to the other hand. weapon_info reports
active model/frame and shot sequence; weapon_info refresh retries a late mount.

Uses the player's mounted v_knife_t, v_pist_usp, v_snip_scout and v_pist_glock18
models and CSS/shared fire/impact sounds. NO Valve assets are redistributed.
Missing model/animation stays hidden instead of displaying a wrong fallback.
Sound volume follows cl_game_sfx. Usual local-owner/watch/ghost/rewind/non-walking
gates apply; no cosmetic shot is inferred from an unconfirmed local click.

## Basic, not full Counter-Strike combat

Standard weapon/weaponframe stats, bit-valued1/2/4/8 and byte shot sequence,
carry authoritative selection and press edges. No new protocol channel/schema.
Server refuses invalid/non-WALK/held selections. Existing callback held checks
remain first. Draw/idle/fire timing uses authored named sequences; FTE exposes
Source sequence names with an @ prefix. Gun meshes need mirroring for default
right hand, unlike the right-authored knife. No native rebuild/pin/tag or Build
number change.

The existing map-target dispatcher is reused: only supported damage buttons and
breakables, never PvP. Knife reach80 and damage capped25; guns retain the existing
8192 trace and run_shoot_damage setting. Press cadence is.45/.15/1.25/.15seconds
for knife/USP/Scout/Glock. NO ammo/reload, penetration, spread/recoil simulation,
zoom, weapon movement-speed tuning or complete CS:S ballistics is claimed.

Both run_shoot and existing lobby_shoot policy remain in force. Cosmetic firing
works with damage off. This patch does NOT silently enable shared-lobby damage;
that is an explicit owner decision. Existing held/evidence coverage remains
closed: no whitelist or qualification relaxation and no new evidence semantics.
Wall sounds are local cosmetic traces, not damage/hit confirmation.

## Acting checks

Real dedicated sockets, normal extrapolation,100fps, native source/tagP924.
Three VMs compile0 warnings. Actual CSS MDLs loaded from the VFS; all four real
screenshots were inspected. Right-handed USP/Glock/Scout screenshots after the
mirror correction show intact textured models, not checker placeholders.
Native named-frame readbacks prove each idle/fire and positive duration:
@idle/@midslash1, @idle/@shoot1, @idle1/@shoot, @glock_idle/@glock_firesingle.
The original raw-name lookup incorrectly fell back to idle, was retained as a
failed arm, and was fixed rather than called a successful shoot animation.

USP held press: sequence1 then still1, release/repress2. Scout early repress
leaves1, later press2. Invalid99 leaves the selected Glock8 unchanged. In actual
noclip, requesting Glock while Scout is selected is refused: returning to WALK
still reports Scout4. This is the non-WALK guard control, not a claim to exercise
every held/evidence mode. Existing held callback ordering is also source-checked.

Real bhop_badges button*98 has DamageActivates and an OnDamaged output that gives
!activator targetname upboost. A normal zone-goto above it, view-down and actual
knife swipe with run_shoot0 advances cosmetic sequence but leaves targetname
empty. Gate1 at the same pose gives upboost: real map dispatcher ACTED. A second
actual button*100 is200units away: knife swing leaves the map's default name,
USP at the same pose gives sideboost. This proves bounded melee versus gun reach
without faking a test damage command. Only the isolated rig's lobby_shoot was1;
no fleet/owner config or player data was changed. No terms were accepted and no
leaderboard acceptance is claimed. Own bridge processes stopped after checks.

All sound selections resolve in the actual VFS; weapon_info/gameaudio_info and
screenshots are not speaker/headphone listening. Owner feel/audio balance is a
small pending check in lextest.md. No device-capture harness is required.

## Delivery

Implemented/acting-verified; final clean build, publish and destination readback
are recorded separately. Native source/tag remains a0ebb9d06/patch-924, while
ENGINE.txt's product ledger advances. Mainline producer is still subject to the
independent P923 fleet gate. Do not force a partial producer/native swap; a
compatible fleet build would require separately inspected clean source/proof.
