# lextest.md — things waiting on a human

Notes left for Lex. Everything here was either measured and needs a judgement
call, or cannot be measured headlessly at all. Nothing in this file is a bug
report: real defects go in BACKLOG.md, and this is the list of things a machine
could not settle.

Written 2026-09-27 by ftesurf-e0 (the run-line work, Patches 449-453).
Delete an item once you have tried it, or move it to BACKLOG.md if it turns out
to be wrong.

---

## 1. The run line, and whether the defaults are right

All of this is live on the fleet now, so it works on a lobby as well as on a
local replay. Open any recording (`replay <path>`, or a board row's replay
button) and look at the line.

**What you should see without touching anything:** chevrons on the path — `V`
where the run touched ground or a ramp, a single chevron where it left one, a
double chevron where you actually hopped, two grey bars where a segmented run
loaded a save — with speed and energy beside each one.

Two defaults were my choice and are worth disagreeing with if they read badly:

- `hud_lines_marks 1` and `hud_lines_nums 1`. You asked for both on. On a bhop
  line this is a LOT of chevrons: `bhop_monster_jam` main has 438 landings and
  330 jumps in one run. If that reads as clutter rather than information,
  `hud_lines_nums 0` first, and tell me — the defaults are one line to change.
- `hud_lines_size 4` and `hud_lines_gap 40`. The mark size and the least
  spacing between two marks, in pixels. Tuned by eye at one resolution on one
  monitor, which is exactly the kind of thing that is wrong somewhere else.

**Worth trying deliberately:**

| Try | What it should do |
|---|---|
| `hud_lines_win 6` then `hud_lines_winf 2` | show only 6 s of run behind you and 2 s ahead, instead of the whole line. This is the "follow the run, not the room" mode and it is OFF by default |
| `hud_watch_path_color 2` | ground amber, ramp cyan, air pale |
| `hud_watch_path_color 3` | energy gained or lost, green to red, against the most air strafing can physically add |
| `hud_watch_path_color 4` | air control: green where your turn rate matched the target for that moment, red where it did not, **grey where there is no answer** |
| `hud_lines_nums 2` | numbers at the peaks too (where vertical speed turns over). Dense on a bhop run |
| `c` (hud_edit) → "Run lines" | all 21 settings with tooltips, no console needed |

**The one to look at hardest is `hud_watch_path_color 4`.** It is the strafe
bar's own grade, computed per sample — so the line and the bar should never
disagree about one moment. If you find a stretch where the line says green and
the bar says otherwise while you sit on that frame, that is a real finding and
I want it.

## 2. Things a headless test cannot do (from ftesurf-a1's Patches 454/455)

These are the other session's work, not mine. The list SHRANK while you were
away, and the reason is worth a line: the first version of this section said the
refusal "has never once been exercised", and that turned out to be wrong. It had
been firing on every run of the existing test all along — silently, because that
branch printed nothing. A branch with no voice looks exactly like a branch with
no traffic. It prints its reason now, and a script covers most of what this
section used to ask you for.

**2a. Finish fast on a real track.** This item has shrunk twice while you were
away and what is left is genuinely yours.

A script now drives all of it but one: `cfg/test/p455hold.cfg` earns the tag,
crosses the line, freezes the body mid-flight and watches the gate refuse for
each reason in turn — not grounded, held, still settling — before it finally
lets the tag die. It even drives the too-fast refusal, but by moving the CAP
down under a body doing 260 rather than by making the body go faster. That
proves the branch works. It does NOT prove a player can reach it in play, and
that difference is the whole reason this item survives: the fixture's runs are
nine ticks long on a bhop map and cross at 244-260 u/s, so nothing headless has
ever crossed a real finish line above the cap. That wants a human, on a track
whose END sits within 64 units of its own START:

- `surf_bikini_bottom` **b1** — a bonus, one leg, 16 u gap. Far less track to
  cover.
- `surf_summer` **main** — eleven segments, 64 u gap.

(ftesurf-a1 measured the leg counts and gaps and deliberately did NOT guess
which is the easier run — a wrong "easier" sends you to the harder map.)

What to watch for, and the ORDER matters: finish fast with a hopped start
tagged, and at the moment of the finish the forgiveness should NOT be taken —
the tag stays up. Then coast to a stop. Once you are standing still it SHOULD be
taken, and you should see a `start re-armed` line. WHICH line depends on the
build, so check both before reporting it missing:

- live today (Patch 454): `start re-armed -- the hopped start died with that run`
- after 455 ships: `start re-armed -- the hopped start was forgiven once you settled`

The wording changed deliberately — "came to rest" was an overclaim on a gate
that admits a grounded body at 259 u/s under a 260 cap.

So a tag that dies a few seconds after you stop is correct, not a bug. The defect
to report is the tag dying while you are still moving fast, because that is the
one that hands the next run a clean slate with the speed still on it.

**2a-note. Two holes were found in that gate while you were away**, both by
ftesurf-a1's reviewers, both fixed before anything shipped: a jump pad's
vertical carrier could clear the tag and then launch you (1259 outputs carry a
vertical component, out of 2029 across 297 of 1316 shipped maps — measured by
`tools/census/basevel.py`, after the first figure quoted here turned out not to
reproduce), and a pad whose impulse arrives four to six
packets after you step off it could do the same with the speed in neither field
the gate was reading. I reviewed that gate and said the first one was covered.
It was not — I had confused two similarly-named fields — so if you want one
thing to poke at on a real map, a jump pad near a finish is it.

**2a-coming. What changes when Patch 455 ships, and one part will look like a
bug.** NOT LIVE YET — the fleet runs the older gate — so this is here to be read
before you meet it, not to be tested today. ftesurf-a1's constants as of its
round 8:

| | |
|---|---|
| wait | 0.25 s of the body reading clear before the tag dies |
| observations | 8 of them inside that wait, one per move packet received |
| gap | 0.1 s — a longer gap between two observations restarts the wait |

**The gap is the one you will notice.** A client sending fewer than about ten
packets a second can never finish the wait, so the hopped-start tag STAYS UP and
your next runs record as practice until you press `!r`. That is deliberate:
without the gap the wait can be banked — send seven clear packets, stop, and
both limits sit pre-paid indefinitely — which makes the whole thing decoration.
But on a bad connection it is indistinguishable from the tag being stuck. `!r`
is the escape, with the known caveat that `!r` with jump held re-tags you within
a tick or two (that one is in BACKLOG).

Two smaller differences from the gate you have now: the message wording changes
(see 2a above), and it arrives about a quarter second after you stop rather than
instantly — invisible next to coasting to a halt, but not nothing.

**2b. Four tracks may be impossible to set a time on.** `agtricks` main,
`surf_flyin_fortress` main, `surf_ethereal` b1 and `surf_quirky` b9 each have an
END region overlapping their own segment-0 START. Read but not run: re-entering
the START while running should re-arm and cancel, so no time can ever be set.
ftesurf-a1 has taken this one and is driving `agtricks` itself — if you happen
to load one of those maps, whether a time can be set at all is the question.

## 2c. Prop collision — FIXED in four patches, and the risky part needs your eyes

You asked for this to be accurate to Source and 100% consistent between client and
server. It is now, on every path I could find, and all four are verified headlessly
(`tools/p458prop.py`, `p458phy.py`, `p460lock.py`, `p461box.py` — all green). What a
machine cannot tell you is whether the maps still PLAY, and two of the four change
what a map feels like. **THIS IS LIVE ON ALL 12 LOBBIES as of 2026-09-28** — you
said not to be scared of restarting them, so engine Patches 458 and 460 and the
mod-side 459/461 went out together and every lobby restarted with nobody on. The
prop-collision changes below are what a lobby now does, not a plan.

**The one to check first, because it is the biggest change in the set.** Source
collides a prop against its `.phy` hull or against nothing at all; it never uses the
visible mesh. Static props already followed that rule; the props this mod spawns did
not, and fell back to the render mesh. They now follow it too, and on some maps that
is a lot of props:

| map | solid props before | after |
|---|---|---|
| `surf_spacemonkeys` | 177 | **0** |
| `surf_420` | 104 | **0** |
| `surf_bikini_bottom` | 269 | 91 |
| `surf_dune` | 176 | 145 |
| `ahop_coast` | 269 | 269 (unchanged) |

On `surf_spacemonkeys` all 177 were one model, `models/que/monkeys3_detail1.mdl`,
which ships no `.phy` — so in Source those props are not solid either, and the map was
built and played that way. That is the argument for the change. But if a route on one
of those maps depended on standing on or surfing off one of them, it will not work any
more, and that is exactly the kind of thing only playing it shows. `hl2_propcollision_nophy 1`
restores the old render-mesh collision if you need to compare, and needs `sv_cheats 1`
now (see below).

**The rubber-band should be gone.** `surf_spacemonkeys`, `surf_angelinaaa`,
`surf_diet_mountain_dew` had the most scaled props; the client used to predict against
a prop 1.3750 where the server moved you against 1.4000, so you were stopped a unit or
two short of a surface you could see and then released. Prop scale is now on the 1/16
grid the wire can carry, so all four readers agree. `cl_nopred 1` is still the
discriminator if you think you see one.

**`surf_lax`** is worth a look on its own: its 144 railings used to reach the client as
8x8 posts while the server kept a 138-unit fence. They now trace their real `.phy` on
both sides. If those railings feel different, that is why.

**The menu row.** `c` -> Graphics, page 4: "Prop collide" and "Disp collide" now read
`needs sv_cheats` and do nothing while you are connected. That is deliberate — a client
that turns prop collision off predicts a world the server is not running. With
`sv_cheats 1` they work as before.

**One caveat I could not remove, and it is worth knowing.** The lock does not engage on
a listen server with ONE player slot: the engine allows cheats unconditionally there
(`cl_main.c:3253`), so testing the lock solo will show it not locking. That is correct
behaviour, not a hole — it is your own server. A lobby runs 32 slots and locks.

## 2d. Props you walk straight through are probably CORRECT

Still true, and now more so, because the rule above extends it. A prop whose model
ships no `.phy` is non-solid because Source does not collide with it either — that was
**34,514 of 110,959 solid props across 380 maps** before this change, and after it the
props this mod spawns are counted the same way. So "this prop has no collision" is
usually the intended answer, and on the maps in the table above it is now the answer a
lot more often.

The inconsistency I flagged last time is GONE: a model used as a `prop_dynamic` no
longer collides against its visible mesh while the same model as a `prop_static` is
walk-through. Both paths now ask the same question.

Each map prints its own numbers at `developer 1`, on one line, so you can check any map
yourself without me:

```
props: 534 spawned (200 solid, 486 scaled), 29 requantised, 3 non-solid (no .phy), 144 bbox->phy
```

## 2e. Momentum's zones now reach 66 maps that had no clock at all

You asked for Momentum's zones to be copied over, applied to the CS:S and `_ksf`
builds, and made editable. **All three are done and the fleet has them** as of
2026-09-28: 66 donated zone files are on all 12 lobbies and verified loading there
(`zones(sv): 6 on surf_utopia_njv (maps/zones/local) crc 4260ad9c`, the same crc
the local arm measured), and 609 files — 543 mirrors plus the 66 — are in
`maps/zones/local/` on this disk for you to edit.

**The mirrors are LOCAL ONLY, deliberately.** They are byte copies, so they change
nothing; their whole point is that you can edit them. When you edit one and want it
live, it is one `scp` to
`proto@192.168.1.102:/srv/nvme/ftesurf-server/game/ftesurf/maps/zones/local/`.
Pushing all 543 would have added risk for no behaviour change.

**If you break one while editing, it costs you the edit and not the map.** A zone
file that parses but yields no zones used to wipe the table, report success and
block the fallback — so the map went silently untimeable. It now says `loaded no
zones -- ignoring it and trying the next source` and falls back to Momentum's copy.

**What changed.** The zone loader keys on the bare map name and does not alias, so
`surf_aircontrol_ksf` had no start, no end and no timer while `surf_aircontrol.json`
sat installed one directory away. `tools/zoneinstall.py` writes the donor's file as
`maps/zones/local/<target>.json`, which is all it takes — no QC, no engine. 66 maps
went from untimeable to timed.

**The list is `ftesurf/maps/zones/manifest.txt`**, and `python tools/zoneinstall.py
--verify` prints it with a note for any file you have since edited (it will never
overwrite one of yours).

**What only playing them will tell you.** A zone is an absolute world polygon, so a
donated file is only right if the two builds share a coordinate frame. I measured
that (`tools/census/zonefit.py`: start/end polygons inside the target's world, and
the two worldspawn mins agreeing) and 61 of the 66 were clean on every check. Load a
few and see whether the start and finish boxes are where the map clearly wants them.

**Five maps I refused, and they are worth a second opinion because a false refusal
costs you a map.** These share a stem with their donor and measured as different
maps, so they still have no zones:

| map | why |
|---|---|
| `surf_derpis_ksf` | world mins 15,344 units from `surf_derpis` |
| `surf_sequoia_fix` | world mins differ by 2,368 |
| `surf_ravine_csgo` | world mins differ by 320 |
| `bhop_eazy_v2` | 5 start/end regions fall outside the target's world |
| `surf_lullaby_ksf` | same, 5 regions |

`surf_ravine_csgo` at 320 units is the one I would look at first — that is small
enough to be a re-origin rather than a different map, and if the layout is really the
same it could be donated with an offset. The other four look decisive.

**Four that work but whose restart is approximate.** `bhop_arcane_v1`,
`surf_cinnamon_fix`, `surf_medley_fix` and `surf_minuet_ksf` name an
`info_teleport_destination` their build does not carry, so `!r` falls back to the
start polygon's floor centroid instead of the authored spot (`sv_zones.qc:340`, and
it prints the missing name at `developer 1`). The map times correctly; the respawn
point may just be a bit off. On about 4% of the library that centroid is outside its
own polygon, so if one of these four drops you somewhere silly, that is why and it is
fixable by hand-editing the file.

**`surf_kitsune_mom` is the interesting one.** `surf_kitsune` is the map
`tools/mapsync.py` uses as its worked example of one name shipping at two builds, and
it now has a donated zone file under the `_mom` name. If any map is going to show a
difference between builds, it is that one.

**The other 543 maps are NOT copied, and that is deliberate.** Mirroring every map's
own zones into the editable folder is what you asked for and it is written and
verified — but it only becomes safe once the fleet runs engine Patch 463. Before that
patch, moving a byte-identical zone table from `online/` to `local/` made `pm_verify`
refuse every existing recording of that map, because the pin compared the directory
name. Measured, not guessed: on a pre-463 build all five of the existing arm's
recordings refused with the crc and the rule identical on both sides. So the mirror
is one `build.ps1 -Pi` behind, and that restarts all 12 lobbies, which is your call.

**One thing to decide.** `ftesurf/` is gitignored, so your edits to those 66 files
are not in git. If you want them versioned, say so and I will add a negation rule for
`maps/zones/local/` — worth doing before you spend an evening tuning a start box.

## 2f. The strafe trainer (Patch 462) — nobody has ever used it

`hud_trainer 1`. Off by default. Written 2026-09-28 by ftesurf-a1.

**It is live on all 12 lobbies as of 2026-09-28**, so you can try it on a real
server and not only on this PC -- which is worth doing, because the two are
genuinely different paths: the speed it grades against is the SERVER's, arriving
in a snapshot, and on a lobby that snapshot has your actual ping on it. It was
verified in both configurations before it shipped, but only by a config driving
known inputs, never by a hand.

**This is the item on this page that most needs you**, because every other thing
here was at least driven by a human once. This was driven entirely by a config:
`+right` turns at exactly `cl_yawspeed`, which is what let an arm author a known
turn rate and a known key/flick offset. No hand has touched it. It is measured
but not *used*, and those are different claims.

**What it is.** The last jump, broken into individual strafes. A timeline where
left strafes sit above the line and right below, a white tick where your mouse
actually reversed, a per-tick trace of your turn rate against the ideal, and a
row per strafe with a grade and the key/flick offset in milliseconds. One named
fault per jump, ranked worst-first.

**The number that is new** is the sync column: `+45` means the key swap landed
45 ms AFTER the flick (late, red), `-60` means it led the flick (early, amber),
`0` is green. On the timeline it is the horizontal gap between a band's edge and
its white tick, so you can see it rather than read it.

**What I would like you to disagree with, because these were my choices:**

| Thing | Why it might be wrong |
|---|---|
| `hud_trainer_x 0.28 / _y 0.27` | placed off screenshots to clear the speedometer and the Segments column at `hud_scale 2` on a 2560x1494 buffer. Another scale or aspect may collide. `c` (hud_edit) -> "Strafe trainer" drags it |
| the S/A/B/C/D/E letters | boundaries are `Strafe_Quality`'s own shape (0.96 is the +-20% band, 0.84 is +-40%), not taste — but whether an "A" *feels* like an A on a real strafe is a human question |
| `hud_trainer_rows 6` | six rows plus the timeline may be too much to read mid-jump. `hud_trainer_rows 0` is timeline-only and the box shrinks to match |
| `hud_trainer_trace 1` | the per-tick graph. Turn it off if it reads as noise |
| the coach line | one sentence, worst fault first: "key fights your turn", then "mouse N% too fast/slow", then "keys N ms late/early". If it keeps telling you something unhelpful, that ranking is one function (`Trn_Coach`) |

**The one to look at hardest.** The trainer and the strafe bar grade the same
quantity through the same `Strafe_Quality`, so a strafe the bar called good must
not come out a D here. If you find a jump where the bar sat green and the
trainer rows say otherwise, that is a real finding and I want it — they are
supposed to be incapable of disagreeing.

**Known limits, stated up front so they do not read as bugs:**

- **Flat air only.** On a ramp the ideal turn rate is a different function of the
  plane normal (between 1.8x and 6x away), and that normal is not available at
  the cadence this samples at. Ramp ticks count toward a strafe's *duration* but
  not its *grade*, and the coach line says "on a ramp — the bar grades that". So
  on a surf map the trainer is for the airtime between ramps, and on a bhop map
  it is for everything. It was built for your bhop description.
- **The panel lags by your ping.** Speed comes from the server's own velocity
  stat rather than from prediction, deliberately — prediction jitters by a whole
  tick and a per-tick speed change is one tick tall. Live steering is the strafe
  bar's job; this is the review.
- **"+N u/s" in the header is not the grade.** It is two velocity samples either
  end of the airtime, so a ramp or a booster is in it as much as your hands are.
  The grade beside it is the part that is only about your hands.
- **Both strafe keys held reads the same as neither.** The usercmd carries right
  minus left, so it is one zero and the trainer does not guess — the strafe just
  ends and the timeline shows a gap.

**If it looks wrong**, `developer 1; log_developer 1` makes it print a line per
strafe carrying every number behind the display (`trainer: R dur 345ms graded
345ms q 0.926 rate 480.0 ideal 412.1 sync +0ms wrong 0ms v 260->294`), which is
what `cfg/test/p462trn.cfg` grades. Send me that alongside what you saw.

## 2g. The segment percentage, and the air rows are yellow now (Patch 464)

Two things changed in the Segments column, one cosmetic and one arithmetic.

**The colour.** Jump / Bhop / Air rows are lemon yellow now instead of the mint
green, because you did not like the teal. The one real constraint was that the
percentage at the right of the SAME row is drawn in `HUD_QualityColor`, whose
65-85% step is an amber -- a gold air row would have matched its own figure -- so
the yellow is pushed bright and pure (`1.00 0.98 0.40`) to stay clear of it, and
clear of the launch row's pale green on the red channel. **Tell me if it fights
with the percentage anyway at your HUD scale**, because that is the thing I chose
by eye rather than measured, and it is one number to change.

**The percentage.** You were right that over 100% was impossible and the calc was
off, and you were right about where: *"anchor each energy on the previous hop...
you can only gain so much per hop."*

What I could establish without a hand on the game, and what I could not:

*Established.* The per-hop maths was already correct. A tick-accurate simulator of
the engine's own air movement, driving a PERFECT strafe, reads 100.0% through the
old code -- so build 88's anchoring (launch point on one side, jump energy on the
other) telescopes exactly, and the tickrate was already handled. That part was
never broken.

*Established.* Over-100% was real and common -- 217 distinct rows in your 463
saved `seq.txt` files, worst 8800%, and the median **Jump** row was 125%. Walking
300 `.rec` files tick by tick found the cause: 17021 air ticks move the energy
further than air strafing physically can. 8755 of those are jump impulses inside
an air run, because `pm_autobunny` re-jumps on the same tick it lands so the
client never sees a hop touch down and `hud_seq_hopbreak` -- which exists to split
the column per hop -- had never once fired. The other 7504 are boosters, push
triggers and teleports, the largest at 13407 units of height in 0.45 s.

*Established, and it killed my first theory.* The recorder's RAMP bit appears on
**none** of those ticks, so the ramp was never the cause. I had told you it was
and asked you to choose on that basis; the tick-walk said otherwise, so I built
what the data supported instead. Grading ramp rows is still worth doing and is in
BACKLOG.md as its own job -- it would give you a number where you currently get a
dash -- but it would not have moved a single over-100% row.

*The fix.* Any rise the flat-air ceiling cannot explain is added to the ceiling,
against a running high-water mark. Both sides of the fraction then contain the
booster or the unseen hop, so it is neutral, the row reads as the quality of the
strafing either side of it, and `seq_de` still holds the true energy so the column
still sums to the run. My first cut of this compared one frame at a time and was
WRONG -- it credited gains and never gave anything back on losses, so a perfect
strafe read 48.8%; the simulator caught that, not me reading it.

*What it measures.* Across perfect, sloppy, autobunny and boosted flights at two
tickrates and two frame rates: zero rows over 100%, and the sloppy rows are
byte-identical to what build 88 printed (78.9% and 69.9%). That last part is the
one I most wanted -- the new term must not be a way to earn credit for strafing
badly, and it is not.

**It is live on all 12 lobbies as of 2026-09-28**, so try it on a real server as
well as here. The two are different paths: the energy a row is built from arrives
in a snapshot with your actual ping on it, and the frame-vs-tick slack the new
rule leans on is exactly the thing a network makes messier. Verified after the
deploy by reading the host rather than the deploy script's own line -- both progs
hashes match the local build and all 12 units restarted inside twelve seconds.

One bookkeeping note for whoever next checks the release: re-measured when
0.1.15 was cut, and the drop's SERVER progs are byte-identical to the pair on the
lobbies again -- csprogs ae498503, qwprogs 8f74c5f9. menu.dat differs, and should:
it is the client menu and a dedicated server never loads it. Re-hash rather than
re-quoting this line -- it has now been wrong once in each direction.

**NOT established: no human has used any of this.** Everything above is a
simulator and a corpus of files. What I would like you to look at:

1. Does a good bhop chain read near 100% now, per hop, rather than one merged row
   with a silly number? That is the whole change.
2. Does a bad hop still read low? If a sloppy chain reads 100% the rule is being
   used as credit and I want to know immediately.
3. On a map with a booster, the boosted row should read about your strafing
   quality rather than 400%. It will still not be very informative on a row that
   is mostly booster -- there is little strafing in it to grade.
4. Any row still over 100%. There is one known way left (a purely HORIZONTAL push
   spread thin enough to hide under one tick of ceiling per frame) and it is in
   BACKLOG.md; a screenshot would tell me whether it happens in practice.

## 2h. Momentum and KSF runs are LIVE — six things need your eyes

The board went from **172 rows on 36 maps** to **85,768 on 608**: every surf
and bhop leaderboard Momentum publishes (main, every stage, every bonus, top
25 each), plus 5,281 of your own demos converted so they are watchable, plus
511 KSF times. 4,791 rows can be watched; the rest are times, which is what a
leaderboard mostly is.

Everything below is a judgement call I made for you and could not settle by
measuring.

**a) The blue tint reads as lavender, not as a glow, and I am not sure it is
enough.** `hud_watch_path_foreign 0.55` pulls an imported line's colour toward
blue. It composes with `hud_watch_path_color` rather than replacing it, which is
the part I am confident about — a Momentum line can still be read for speed or
contact AND say where it came from. But blending red toward blue makes mud
rather than light, and against `surf_4am`'s orange it is subtle. Compare
`screenshots/momline_a5_tinted.png` with `_untinted.png`: the difference is
clear side by side and less obvious in motion. Try `hud_watch_path_foreign 0.8`.
If it still reads as "slightly odd colour" rather than "someone else's line", a
real glow is a wider or additive draw pass, not a hue blend, and it wants its
own patch — say the word.

**b) The replay camera is pointed by a number nobody recorded.** Momentum demos
contain NO view angles at all — not missing, not lossy, absent — so the camera
follows the direction of travel instead. On a surf line that is close to what a
player looks at; through a teleport or a slow section it will not be. You asked
for it to look as smooth as possible, and this is the part that decides that.
Watch `replay data/momentum/surf_ruse/main/0018126_doobie-1acfa76f_run.rec` and
tell me whether it feels like watching a run or like a camera on rails. (No
`.view` sidecar is written for these, deliberately: that file is mouse evidence
and a derived angle filed there would be a measurement that never happened.)

**c) You chose "import untouched, flag only" for the 7.6 % with spiky
velocity — and it costs less than I warned.** 225 of 2,961 files have velocity
that exceeds the demo's own speed ceiling, up to 24x, because the extractor's
point array has gaps and a central difference across one divides a longer
distance by the same two ticks. I expected bright speed spikes on those lines.
Measured: the line's colour range is mean ± 2 sd clamped into min..max, so an
outlier never reaches the colour ramp. `surf_4am`'s worst file has a raw peak of
7,976 u/s against the demo's own 3,130 and the line still colours from 282 to
3,358. So the spike is real, in the data, in the header as `momquality`, and
mostly invisible. It WILL show in the live speedometer at that instant. If you
ever see a replay flash an absurd speed for one frame, that is this and it is
not a bug in the mover.

**d) Is the KSF tier worth keeping at all?** Honest answer: much less than
Momentum. 85,085 Momentum rows across 608 maps, 4,791 of them watchable. KSF gives **times only** — that network publishes no replay anything
here can fetch — and their per-map leaderboard route is one I could not find, so
it imports one player at a time, 25 records each. It is real and it works: on
`surf_garden` the combined board now reads KSF 79.884, Momentum 95.745, ours
152.115. But a row you cannot watch may be worth less to you than a clean board.
Seed it from a file of SteamID64s and see; if it reads as clutter, the tier
drops out without touching anything else.

**e) Five wrong records were on the board and I found one of them by eye.**
`surf_utopia`'s #1 read 26.565s against a #2 of 53.565s. That is not a record,
it is a broken extraction — the demo's own header reports a 10,073 u/s peak,
about 3x anything real on surf. Because the API sweep and the demo corpus now
answer for the same boards, they can be checked against each other: 5 of 4,743
demo rows beat Momentum's own #1, including a 0.405s "run" where the real
record is 92.565s. All five are gone. **The check only exists because I looked
at one board by eye** — nothing I had built would have caught them, and I do
not know what else is in there that a different glance would find. If a time
ever looks impossible to you, it probably is, and I would like to hear about it.

**f) THE COMBINED VIEW DOES NOT WORK AT REAL SCALE, and I need you to pick the
fix.** You asked for a separate tier plus a combined view, and the combined view
is built and correct: all tiers, ranked by time. At test scale that read
beautifully -- your 7.125s, your Momentum 7.320s, borobongo's 7.635s, one list.

On the live board it is useless. `surf_utopia` main has 271 imported rows and 2
of ours, and **221 of theirs are faster than your best**, so your row is at rank
222 while the client only ever fetches the first 64. You would scroll a page of
strangers and never find yourself. That is not a bug in the merge; it is the
merge doing exactly what it says on a map where you are not competitive yet.

Three ways out, and it is a question about what "compare" should mean rather
than one I can measure:

  1. **Cap the foreign rows.** Combined shows the top N imported plus ALL of
     ours. You see the best few of theirs and every one of yours. Best for
     "how far off am I", worst if you want to browse their board.
  2. **Always include your own row.** Keep the merge, but pin the local
     player's row into the page wherever it really ranks, with the rank shown.
     Honest about position, needs the client to say who it is -- /api/board
     currently has no idea who is asking.
  3. **Page it.** The board fetches one page of 64 and has no offset; adding
     paging fixes this and every other long board at once, and is the most work.

My instinct is 1 for the combined tab specifically, because the tab exists to
read one against the other, and 3 separately because the ranked board will hit
this too one day. But you are the one who will use it.

**One thing I would like you to look at that is not a judgement call:** the
`why` column on the board. It has been empty by construction since Patch 355 and
now carries `momentum` or `ksf` on exactly the rows that are foreign. If that
column ever shows a word on a ranked row, something is wrong and I want to know.

## 2i. The map roster — two decisions only you can make

There is now one list of every surf and bhop map either catalogue knows about,
pinned to the exact build this install would load: `ftesurf/data/maproster.txt`,
1748 maps, 1280 of them on a local mount and hashed -- which is NOT the number
the Pi serves (1743), nor the number the browser offers. `python tools/maproster.py check
<map>` explains any single row in English. Nothing about it is deployed and it
changes no game behaviour — it is a file on disk and a tool that writes it.

**First decision: `surf_dune` and `surf_fantasy` in `ftesurf/maps/`.**

Your gamedir wins the mount, ahead of both Steam installs. Those two files are
byte-identical to the **CS:S** builds, and they override Momentum's cuts of the
same maps. So anyone playing either one on this install is on geometry no
leaderboard knows: 45 imported runs attest to a different `surf_dune` and 5 to a
different `surf_fantasy`. They are the only two maps out of 1748 whose loaded
build contradicts the evidence — everything else is either confirmed or has no
evidence either way.

Deleting those two files makes the roster clean in one step. I have not touched
them because I cannot tell from here whether they are deliberate fixtures — 
`poop` and `surf_raqbonus3ramp` beside them clearly are, and have no upstream
build at all, so they are unaffected either way. If you put those two there on
purpose, say so and I will record why rather than keep flagging them.

**Second decision: three maps still missing, and whether to spend the bandwidth.**

28 of the 31 KSF maps you did not have are now in your Momentum install.
`surf_tycho2`, `surf_weirdcore` and `surf_yolo` are not: the fetch was stopped
partway through the 29th because the machine ran critically low on memory. That
was not a failure of the download, and re-running picks up exactly those three
(the roster recomputes what is missing from what is on disk). I have not
restarted it on my own because memory may still be tight — tell me when it suits.

Worth knowing what that cost: these are big. `surf_expel` is 335 MB unpacked,
`surf_crank` 216 MB, `surf_starvald` 195 MB. The 28 added roughly 2.5 GB.

**And one thing that is not a decision, just worth your eyes.**

The 28 new maps are CS:S builds sitting in a Momentum mount. That is fine — none
of them exists in the Momentum install, so nothing is shadowed, and I checked
that per file rather than assuming it. But they have never been loaded by this
engine. Pick two or three at random, load them, and see that they come up and are
solid. If a CS:S-built map needs content the Momentum mount does not carry, that
is where it will show, and it will show as missing textures or props you fall
through rather than as an error.

## 2j. Map downloads — shipped in 0.1.15, and the library is now complete

### Get 0.1.15 first. 0.1.14 cannot show you this feature at all.

You downloaded a build and there was no Download button. That was not the
feature failing — it was never in a release. Two separate faults:

1. **0.1.14 was built at 13:33 and the map-download work landed 19:41–20:17.**
   Six hours later. The source was pushed; no release contained it.
2. **Rebuilding alone would still have shipped a button-less list.**
   `data/mapdl.txt` is gitignored, and the release ships a *named* list of data
   files that did not include it. Without that file the map list is built purely
   from what is already on your disk, so every row is an installed map and
   **nothing draws a button**. The feature was compiled in, working, invisible.

Both fixed. `https://proto.bar/ftesurf` now serves **0.1.15**. If the button is
missing, check the version before anything else — that is by far the likeliest
cause, and `data/mapdl.txt` should exist in your install with ~1743 lines.

### What you have now

    bhop      131 -> 574 of 574     100%
    surf     1146 -> 1169 of 1174    99.6%
    offerable 1277 -> 1743 of 1748

463 maps were pulled from Momentum's CDN straight onto the Pi, each checked
against the publisher's own sha1 before being installed. The Pi holds 1813 bsp.

**The five that are left are not a backlog — they cannot be got.** Four are KSF
names with no archive behind them and no Momentum record (`surf_disappointed_fix`,
`surf_junglepics_ksf`, `surf_race_final`, `surf_vestige_fix`); the fifth,
`surf_solipsism`, has a Momentum record whose download URL 404s on their side.
Nothing to do about any of them from here.

KSF is finished: 931 Drive archives indexed, not one for a map we lack.

### What to test in game

Launch `ftesurf.bat` from the 0.1.15 install.

1. **The list is much longer** — 1743 maps, the ones the Pi can actually serve.
   The ones you do not have carry a **Download** button on the right with the
   file size under it.
2. **Click one.** The button becomes a progress bar with a live KB/s figure.
   Other rows say `queued`; the engine does one at a time, deliberately.
3. **Press ESC mid-download.** It should keep going and still say `installed`
   when you come back. The tick that notices completion runs outside the menu
   gate on purpose. **This is the bit most likely to be wrong and no human has
   ever done it** — the harness drives `ui_dlmap`, which cannot press ESC.
4. **The row should become a normal map** once it lands, without a restart.

Expect roughly 1 MB/s. That is the cap you asked for, applied on the Pi.

### Do not expect NEW badges on these 463

They will not badge, and that is correct. `NEW` means "a sweep saw this name
appear in the catalogue", not "recently downloadable". These maps have been in
the catalogue all along — what changed is that the Pi can now serve them. A
badge here would mean the opposite of what it says everywhere else.

The six-hourly scan is registered and healthy (last run 18:07, result 0, next
00:07). New Momentum or KSF releases picked up by a future sweep *will* badge.

### What is already proven, so you need not re-check it

- **The Pi serves the right bytes.** `bhop_pandora`, fetched an hour before the
  release, pulled over https at 1,041,220 B/s with a sha1 identical to the Pi's
  copy. Both url layouts resolve; directory listing and `../` traversal 404.
- **An interrupted download cannot corrupt a map.** This was a real bug and you
  would have hit it: a part-way http transfer used to leave a TRUNCATED .bsp
  under the real name, which looks installed, stops the button offering it, and
  mismatches mapcrc — silently demoting every run played on it. Downloads now
  land in a `.tmp` and are renamed only once whole. Same discipline on the Pi
  side: 464 transfers, zero leftovers.
- **Six maps could never have downloaded** — the catalogues lowercase names and
  the Pi does not, and Linux paths are case-sensitive. Now matched by fold.
- **The published archive is the right one.** Re-downloaded from dl.proto.bar
  after publishing: sha256 matches and `mapdl.txt` inside carries 1743 rows.

### Still waiting on you

- **`surf_dune` / `surf_fantasy` from §2i** — unchanged by any of this, and
  still the only two of 1748 whose loaded build contradicts the evidence.

## 3. Known limits of the line, so they do not surprise you

These are in BACKLOG.md with the detail; the short version:

- **A hop whose ground contact falls between two network packets has no mark,
  and cannot have one.** Samples arrive 43-65 times a second against a 66.67 Hz
  tick, and a bhop's contact is one tick. The Segments panel misses exactly the
  same hops, which is why the two never disagree — but a chevron count on a bhop
  line is an undercount, not a total.
- **Air control is graded against the settings of the server you are ON**, not
  the one the recording was made on. The strafe bar has the same limitation, so
  they agree with each other; they would be wrong together on a recording from a
  differently-configured server.
- **The mark cap (4096 a run) has never been reached by any test.** The policy
  for exceeding it — drop the peak markers first, then stop and say so — is
  written but unexercised, because the longest recording available produces
  2158. If you ever watch a run and the console says marks were dropped, that
  path has run for the first time and I would like to know what it looked like.

## 4. If something looks wrong, what to send

`replay marks` (the mark table), `replay colours 0 32` (the colour of every
32nd point plus the movement settings it was graded against) and `replay
marktrace 2` (what the next two frames actually drew, including each label's
text and screen position) all print to the console, and `ftesurf/logs/` keeps
them with `log_enable 1`. Any one of those plus the recording is enough to
reproduce a bad line exactly.

## 5. The website, and what I want you to look at

`proto.bar/ftesurf/board/` is live with all of this on it. It reads the real
database, so every number below is one you can click.

- **The map list** now says 766 maps, 740 with times, 4,791 runs to watch. Tier
  chips (T1-T10) filter by Momentum's own difficulty rating; 380 of your 536
  playable maps are rated, the rest say Unrated rather than pretending to be
  tier 0.
- **Any row with a demo has a Watch button.** That opens the run: the path
  coloured by speed, a dot you can play and scrub with the u/s it was carrying
  at that instant, and a speed strip you can click to seek. Pausing puts the
  moment in the address bar, so `#r=5&at=31` shares the exact frame.
- **Player search and profiles.** Click any name. ~5,000 people, times,
  records, top tens, maps finished, and a completion bar per difficulty tier.

### Judgement calls for you (2h continues)

- **(g) Is "records" the right word for the contested count?** Your Momentum
  profile has 35 first places and 0 of them contested -- every one is a stage
  board nobody else in the archive has a time on. The page leads with 0 and
  puts 35 in the tooltip. That is honest and it is also a profile that says
  zero. Tell me if you would rather lead with 35 and footnote the caveat.
- **(h) DONE -- imported dates are real now.** 81,290 rows backfilled from
  Momentum's own `created`; the board reads 2025-10-07, 2026-06-20 and so on
  instead of one afternoon. Nothing of ours moved (checked row by row against
  the pre-backfill database: 0 ranked/community/ksf rows changed). ~3,795 rows
  sit below the cached top-25 and still show the import date; they are counted,
  not guessed at. Say if you would rather they showed nothing than show a date
  that is ours.
- **(l) surf_utopia's #1 on the public board is 0.060 s faster than
  Momentum's own #1.** It is a demo-corpus row with no matching board entry.
  The existing "impossible time" check passes it because 0.5% of 53 s is
  0.268 s. That tolerance was chosen when the bad rows being hunted were a
  0.405 s "run" against a 92 s record -- it was never meant to cover a tenth
  of a percent. I have not deleted anything. Your call: tighten the check with
  an absolute floor, drop that row, or leave it and accept that our top line
  can disagree with theirs by a hair.
- **(i) The imported tint is 0.45 on the web line** against 0.55 in the game.
  Look at a MOM run and an OURS run side by side and tell me whether the blue
  reads as "different source" or just as "blue".
- **(j) Momentum profiles link out to momentum-mod.org.** Your own guid never
  leaves the server -- the site's player ids are a hash -- but an imported
  player's steamid is published, because their own leaderboard publishes it.
  Say if you would rather it did not.
- **(k) 740 of 766 maps now have times on a public page**, most of them other
  people's. You said yes to this; it is worth seeing at full size before it is
  indexed by anything.

### The admin page, and the prestrafe

- **Your run-review page folds up now.** Verdicts, Receipt, Key and the raw
  recording header are behind dropdowns, but each one still says its state on
  the closed line -- `[PASS] 1 current`, `[FIRST KEY]`, `[UNREADABLE] no file
  on this node` -- and anything flagged opens itself. It also has the same
  moving dot the public page does. Nothing about approving or rejecting a run
  changed; that was checked line by line.
- **(m) The public viewer could not reach the prestrafe and now can.** A
  recording starts about two to four seconds before the timer does, and the
  scrubber used to start at 0:00.000 with that span drawn off the edge. It
  opens at `-0:02.130` on your surf_utopia run, standing still, and the speed
  strip shades the pre-timer part. Tell me if you would rather it opened at
  0:00 and treated the prestrafe as an extra you scrub back into.
