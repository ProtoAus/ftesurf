# P920 — paused-run selection and count-in view lock

## Contract and falsifiers (registered before runtime checks)

The existing local-player `*resume` O/R/C/A key, `cmd ms_resume`, F2 shortcut,
and server claim/apply transaction remain authoritative. No recorder, clock,
save format, acceptance or discard behavior changes. No new network channel.

- Old CSQC control: an offered pause draws centred text, not a selection box.
  During an actual C count-in, continuous native turning must positively change
  the server-reported view yaw, so silence cannot pass the lock check.
- New CSQC: the same offer draws a left box with map, saved time, stage/main or
  bonus track and session, plus 1. Yes and 2. No. No dismisses only that offer;
  the paused slot must remain byte-identical. Reconnect offers it again.
- Yes and F2 use the existing accept command, consume their own repeats and
  release even when the offer closes before release. The server must ACT the
  accept and produce a real C count-in; a swallowed key alone is not a pass.
- During C, pin both VF_CL_VIEWANGLES and outgoing input_angles; suppress game
  movement/buttons but retain command time. A hidden mouse/native-look turn
  must not accumulate and snap at GO. Spectating must not inherit the body pin.
  The resume SLOP event releases a stale C key before it can overwrite the
  restored view. Outside C the input hook must be inert.
- After GO, the same continuous native turn must change yaw again. Build all
  three progs to zero warnings. Screenshots, logs and generated profile data
  remain in the owned task root, not public test output.

Runtime checks use one isolated dedicated socket, fresh profile/data, the same
native binaries and SSQC, and a copied surf_dune BSP/start-zone fixture. Only
the start region is narrowed on its existing safe platform to prove walking
out starts a timer/recording without falling. Never alter installed zones or
player data. Baseline CSQC is rebuilt from the inspected pre-feature Git HEAD.
Native keyboard-look exercises the same angle accumulator, but is not a claim
of observed physical-mouse feel: that small owner check remains explicit.

## Implementation

`cl_resume.qc` owns presentation, modal-answer latches and count-in angle pin.
It follows the existing Timer/Font/Spec helpers in declaration order. Main input
routing leaves higher chat/board/dialog handlers first and places the offer's
number keys before save-lock digit keys. Owned releases are caught before
those handlers. Render-rate and input-rate pins mirror the existing save-lock
pattern. No is non-destructive; `!resume` remains available later.

## Results

Actual Windows dedicated-socket control/subject passed on port 27597, from
pre-feature source e002c598fd802720cb40d56ddc027b58e5d29972 and P919 native
0265ae46068d633e9779182f48a140f1c9bf2517. Both arms used the same SSQC,
map/zone fixture and byte-identical synthetic parked slot, restored without
redating its clock. A walked whole-main timer was positively running/recording
before parking. Reconnect waits past the dedicated server's zombie slot: this
non-lobby fixture uses the first client's local key, not the owner's profile.

- Old C yaws: 90.0 -> -25.2 (115.2 degrees of native turn). At GO: 90.0 ->
  -17.6 (107.6 degrees). The old control positively ACTED.
- New C yaws: 90.0 -> 90.0; still 90.0 at GO, then normal native turning to
  -17.5 (107.5 degrees). No banked turn in this case; actual server apply ran.
- New No consumed press/repeat/release and retained all three slot files byte
  for byte. A fresh reconnect offered the same pause. Yes accepted through the
  real input chain; F2 was untouched after the offer. The old F2 accept path was
  the acting control; the new F2 branch also retains its same accept command.
- A fake vote armed immediately after No accepted a fresh 2, proving observer
  releases still reach Vote_Track. Its required 0.75-second arm delay is not a
  regression: the initial 0.1-second test did not ACT, then the corrected
  0.9-second arm passed. An existing screenshot refusal was preserved, not
  overwritten; unchanged captures were reused.
- All three progs compile with zero warnings. Inspected screenshots show the
  left details/choices, its nondestructive dismissal, and count-in label. The
  minimal rig does not mount every map material; this is panel-layout evidence,
  not an asset/content render acceptance.

Reproduction/evidence remain in the owned source-polish task root:
controls/p920-prepare.py, controls/p920-arm.py control|subject,
artifacts/p920-{control,subject}-result.json, p920-build-checked.* and the
isolated controls/p920-ui screenshots/logs. Do not publish generated identities
or raw fixture logs. A key-up observer ordering fix and focus-loss latch reset
were included before the final build. Spectator/replay exclusion and stale-C
resume-event release were reviewed, not separately packet-race falsified.

Owner physical-mouse and aesthetic acceptance remain pending in lextest.md.
## Installed / remaining deployment

Clean inspected feature commit e7637907d7e369b594ca25ff45537001b716f907 was
rebuilt with the normal build entrypoint: all three progs, zero warnings. Both
Windows installs match its six DAT/LNO files as of 2026-10-22T10:14:33Z;
predecessors remain as .prev. CSQC SHA256:
`e9e220a5faa31b4aa5a861e73b6fd64e948145a46f790abceb4a6f19ce4b88c5`.
Native binaries/configs were not deployed by P920; the P919 native code remains.
Server/shared/menu source is identical to the already handed-off P915 source;
normal recompilation does not introduce another recorder change.

The build's Pi gate found one live player on surf_boreas. It refused before
copy/swap/restart, without override. Thus the Pi and lobby-served CSQC remain
on their predecessor; Windows installation is NOT a claim of what an occupied
lobby client runs. Complete the normal rollout and a fresh-client hash smoke
when the fleet is empty. Do not interrupt that run or repeatedly rebuild the
already verified artifacts. Local cache seeding was done only after confirming
no temporary downloads, without deleting another session's active download.
The owned artifacts/p920-windows-deployment.json and p920-commit-deploy.*
record this partial state. No Build bump or release.
