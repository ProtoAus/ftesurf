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
