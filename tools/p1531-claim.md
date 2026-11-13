# P1531 claim (ftesurf-16, Claude Code, 13 Nov 2026)

Jargon, Lex's 13 Nov follow-ups to P1528 ("do the next patch"): take over from here (a third take-over: a key or the
panel's button, from wherever an armed run is, the course from the start zone it left); live waypoint edits (a moved
point ahead of the one being searched takes effect without stopping); "Redo from this waypoint" on a table row; Continue
honouring edits made after its save; the panel's Options (effort restored, path width, boarding, finish, behaviour
switches, experiments). QC only. The search work (boarding windows from all demos, a ride-after-board lookahead) is the
patch after this one.
After fetch: origin/main has P1530 (2f889242); no P153x in remotes, worktrees, nested worktrees or private => 1531.
Root C:\FTESurf-worktrees\jargon-courses-1111a (qc5 jargon-catch).

Delivered 13 Nov 01:47Z from p1531 rebased on main 65469918 (compiler 1f2efd06, 0 warnings): take over from here (When I press,
Take over now / tas jargon takeover, the course from the stage the run is in), live waypoint edits (moves at once, air
points from the next waypoint), Redo from a waypoint by its demo time, Continue with the player's moves and air points
(the notes' airsig line), the panel's Options (effort restored, path, boarding, finish, behaviour switches, folded
experiments and the two crouch test switches), every run's plan sent to the panel, and the panel's project poll let
through the optimizer gate (three refusal lines a second while Jargon ran after a save -- in P1528 too).
Reviews: round 1 (server, client) found 10 + 11 defects; the critical one -- a takeover pause written with `&&`, which
paused and TAS-marked every plain start's live run, lobbies included -- was fixed and a focused round 2 found no
integrity defect and 12 smaller ones (a refused takeover corrupted the arm, among them); fixed, the rest in BACKLOG.
Checks on these bytes (cs 3a52a7c9 / qw 3fb10353): jgp1531 22 pass / 1 fail (R1, a valid third answer the pattern did
not list) / 2 skip (a stage-1 retry, a first walk) -- options words, live move and air point, take over mid-course and
from a live armed run, Continue with a new air point, redo from a reached waypoint, no refusal spam; the panel test 27/27
on the 0.1.44 release exe.
Deployed: both installs via install_qc.sh (.prev/.pre1531 = P1528's qw 9693e177 / cs 2bfa1db8; C:/FTEQuake's .prev
restored from .pre1531 after -Pi's sync), 12 lobbies via build.ps1 -Pi (one player on lobby 5 got the script's warning
and countdown), live qw 3fb10353 / cs 3a52a7c9 on both sides; tasrevd codes.txt 128 -> 129 (.pre1531).
