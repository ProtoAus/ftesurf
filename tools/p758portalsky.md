# P758 — Kitsune: the sky through a door, doors by PVS, bhop through a door, frame times

The owner (17 Oct, after P748/P752/P756 were confirmed): the door in the `!m` room
appears only when close and then flashes in; the background of the room behind a
door is missing or broken until you walk through (saves 12-15, screenshots
surf_kitsune_173-176); bhopping through the portals sometimes stops you; the fps
stutters periodically and the 1% lows are bad.

## Sky through a door (engine + QC)

CSQC sets the 3D sky camera (`VF_SKYROOM_CAMERA`) once a frame from the player's eye
(`cl_main.qc`, sky_camera origin + eye / scale), and every recursive view inherited
it. Saves 12-14 look through a door at a room about 4,300 units away (save 15 is
past it), so the far room's sky was drawn from the wrong place: none at save 12,
red bar fragments at 13 and 14, right at 15 (crossed). The QC now passes the scale
as a fifth argument and engine 758 moves the camera by (each view's eye - the
setter's eye) / scale.

Measured (subject basedir, 1920x1111, the saves' own positions and angles; crops
of the doorway): the old build reproduces the report exactly (12 none, 13 and 14
fragments, 15 grid); engine 758 shows at 12-14 the grid the crossed view shows.

## The `!m` room's door (QC)

`!m` puts you at (-9152, -5039); stage 1's exit door is 3,599 units from there,
past `vbsp_portal_dist`'s 3000, so it was drawn shut until you came within 3000.
Doors are now offered by facing and PVS alone: `vbsp_portal_dist` became
`vbsp_portal_maxdist`, default 0 (off), so an install's older default.cfg setting
3000 cannot bring the cap back. Measured at the `!m` spot: offered doors go from
`portal_s1_entry` to `portal_s1_entry portal_s1_exit portal_s2_exit`, and the
3,599-unit door shows stage 2 instead of a shut door. From the hub spawn (760
units) both builds already drew the hub door.

## Bhop through a door: mover 6 (engine)

20 crossings of the hub door at 700 and 1000 u/s with autohop held, start offset in
9-unit steps so the door is met at every phase of the hop (`cmd viewpos` every
100 ms, a stop is a crossing that loses half its speed):

| Build | stops |
| --- | --- |
| mover 4 (`fb3c90bf`, P754) | 8 of 20 |
| mover 5 (`f669bc11`, P756) | 8 of 20, the same crossings |
| mover 6 (P758) | 0 of 20, every review round's build |

A per-tick diagnostic build (mover prints, never shipped) showed the cause: the tick
after the transform starts with the hull 9.5 units into the wall behind the exit
(at bhop speed a tick is 10-15 units), the carve clips it where the hull's back
clears the door plane (y -15335.906 = plane + 16 + 3/32) and reports that boundary
as a wall facing back (normal -y, ent 0); ClipVelocity zeroes the forward speed and
autohop keeps hopping in place. A crossing whose tick started 0.5 units into the
wall did not stop. P756's review had found this edge and recorded it as unseen on
Kitsune, from a walk (3.4 units a tick).

Mover 6 treats that boundary as a waypoint and traces the rest of the move from it,
moved 1/16 along the door's forward. Four review rounds: round 1 found a rest that
started in solid passed on as a move (a non-upright exit tunnelled through a wall;
now it keeps mover 5's stop); round 2 found that restarting on the move's own line
left most of a grazing move untraced (through a jamb or a corridor wall beside the
door, 0.4-1.5% of exit states; now only the 1/16 nudge is untraced); round 3 found
a blocked rest reported as a full move (now below 1); round 4 found nothing. Each
defect is a check with a control in `tools/test_portal_carveexit.py`. A walk
through the hub door and back still crosses unbroken (timeline arm).

## Stutter and fps (diagnosis, open)

`frametimes` (engine 758) prints the frame pacing since the last call. Arms at the
owner's resolution (2560x1600 windowed, cl_maxfps 0, vsync off), 8-s turns, avg /
1% low fps:

| Hub turn | renderscale 2 | renderscale 1 |
| --- | --- | --- |
| r_portalrecursion 2 | 752 / 305 | 817 / 283 |
| r_portalrecursion 1 | 931 / 488 | |
| r_portalrecursion 0 | 1055 / 537 | |

So depth 2 roughly halves the 1% low against depth 0 and renderscale barely
matters here. The stutter: once a run is going, a ~17.5 ms frame every 413-417
frames (fixed in frames, not time), and the average fps falls the longer the run
lasts (918 -> 486 over ~30 s in one arm). Not the trail, the race ghost or portal
rendering (each switched off, spikes stay). A stage-timer diagnostic build puts the
whole 17 ms inside the client QC's view function and outside `renderscene`
(0.2-0.5 ms) and the swap (0.2 ms), so in a builtin `CSQC_UpdateView` calls
itself. Open: BACKLOG's stutter item.
