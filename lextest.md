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

One bookkeeping note for whoever next checks the release: 0.1.14 shipped hours
before this, and its commit records that the progs in the drop were byte-identical
to the pair on the lobbies. That is no longer true -- the fleet is one patch ahead
of the download. Nothing is wrong with either, but do not re-quote that line
without re-hashing.

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
