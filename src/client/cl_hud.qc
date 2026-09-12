/*
===========================================================================
  cl_hud.qc -- the surf HUD.

  Five things on screen, and each one answers a question you would otherwise
  have to guess at:

    speed / energy    what have I got, and what is it worth
    strafe bar        am I turning at the rate that adds the most of it
    board panel       what did that ramp just cost me
    contact/leaving   what did I arrive with, what did I leave with
    keys              what did my hands actually do

  The maths is in shared/sh_strafe.qc and client/cl_board.qc; this file is
  layout.  Keeping that split matters because the maths is testable and the
  layout is not.
===========================================================================
*/

// --- cached cvars -----------------------------------------------------------
float  ui_cv_scale;
float  ui_cv_speed, ui_cv_keys, ui_cv_debug, ui_cv_energy, ui_cv_energyref;
float  ui_cv_predicted;     // build 39: read the predicted state, not the stats
float  ui_cv_strict;        // build 39: no ramp plane means no target, not a wrong one
float  ui_cv_strafe, ui_cv_board, ui_cv_boardfade;
float  ui_cv_seqlive;       // build 34: provisional rows for the OPEN segment
float  ui_cv_mapinfo, ui_cv_mappos_x, ui_cv_mappos_y;   // build 34: the top-right block
float  ui_cv_smooth, ui_cv_window, ui_cv_band, ui_cv_curve, ui_cv_minspeed;
vector ui_cv_speedpos, ui_cv_keyspos, ui_cv_debugpos, ui_cv_strafepos;

/*
===========================================================================
  BUILD 31 -- THE LAYOUT REGISTRY.

  Nothing on this HUD has ever published where it drew.  Every drawer computes
  its coordinates from its own two cvars, draws, and throws the numbers away --
  which is fine for drawing and useless for an editor, because "what can I grab"
  and "what is this overlapping" are questions about a box nobody keeps.

  So each drawer now says, at the end of its own body, exactly what it just
  covered.  Read from the drawer rather than recomputed by the editor on purpose:
  the two would drift the first time a panel gained a row, and an editor whose
  hit rectangle is a stale guess at someone else's layout is worse than no editor.

  THE ANCHOR IS SEPARATE FROM THE BOX, and that is the load-bearing part.

  Three different conventions coexist -- centre-x/top-y for the timer, left-x
  with a vertically CENTRED block for the split list, an offset-from-centre with
  a RIGHT-aligned block for the segment column -- and two panels have sentinel
  values on top of that (hud_keys_x 0 = auto-right, hud_board_x -1 = stacked
  under the bar).  Inverting a box back into cvars would need every one of those
  cases and would get them subtly wrong; the strafe panel alone extends 15*scale
  ABOVE the y its cvar names, because the two rate cells are drawn over the bar.

  Publishing the anchor POINT means the editor never inverts anything.  It moves
  the anchor by the same pixel delta it moved the box by, and one division per
  axis writes the cvar back.  The box is then only ever used for hit-testing,
  outlining and snapping -- three jobs that want the visible extent and do not
  care what convention produced it.

  COLLECTED ONLY WHILE THE EDITOR IS OPEN.  ui_he_open is declared here, in the
  first file that tests it, rather than in cl_hudedit.qc -- which compiles last
  because it needs rec_wt_open and rec_sb_open, both of which come from files after
  this one.  Same declaration-order constraint the two blocks at the top of
  cl_keys.qc exist for.  The cost when closed is one float test per panel.
===========================================================================
*/
#define HUDE_MAX 12
string hude_id[HUDE_MAX];
vector hude_pos[HUDE_MAX];      // top-left of what was drawn, pixels
vector hude_size[HUDE_MAX];     // pixels
vector hude_anchor[HUDE_MAX];   // the pixel point the element's two cvars encode
float  hude_n;

float  ui_he_open;              // the layout editor is up

/*
  AND THE LEADERBOARD'S FLAG, HERE FOR THE SAME REASON.  Build 47.

  cl_watch.qc has to test this before it lets the cursor go, and until now it
  could not: it compiles BEFORE cl_scores.qc, where this used to be declared, so
  the test was unwritable and the only honest thing there was an unconditional
  setcursormode(FALSE).

  What that cost is the exact sequence Scores_Close's own comment calls the
  ordinary way to use the two together -- open the board, click a row to watch
  it, stop the replay -- which turned the cursor off underneath a board still on
  screen, with nothing able to press anything on it.  Scores_Close has always
  tested for the mirror case; this is the half that was missing.

  Declared HERE rather than moved into cl_watch.qc because cl_hudedit.qc tests
  it too, and this is the one file all three of them compile after.
*/
float  rec_sb_open;             // the leaderboard is up

/*
===========================================================================
  THE CURSOR CLAIM REGISTER.  Build 55.

  THE PATTERN THIS ENDS.  The two blocks above are the same fix applied twice:
  a panel could not release the mouse correctly because the flag it needed to
  test was declared in a file that compiles later, so the flag got moved up
  here.  Build 47 did it for rec_sb_open, build 48 for ui_rs_cursor.  Each
  owner has to test EVERY other owner, so N owners need N*(N-1) tests and every
  new panel silently invalidates the ones already written.

  IT HAD ALREADY GONE WRONG, in the direction the pattern predicts.  Before
  this block there were four owners and the tests read:

    Results_Close  (cl_results.qc)  !rec_wt_open && !rec_sb_open && !ui_he_open
    HUD_EditClose  (cl_hudedit.qc)  !rec_wt_open && !rec_sb_open && !ui_rs_cursor
    Scores_Close   (cl_scores.qc)   !rec_wt_open && !ui_he_open
    Watch_Close    (cl_watch.qc)    !rec_sb_open && !ui_he_open

  The bottom two are missing ui_rs_cursor, and NOT because anybody forgot: it
  is declared at cl_results.qc:58, which compiles AFTER both of them, so the
  test was literally unwritable.  cl_scores.qc's own comment says "all three
  now ask the same question" -- there were four by then, and they did not.
  The reachable symptom is the one those comments already describe: take the
  cursor with the results card, open the leaderboard, close it, and the mouse
  is handed back to the game with the card still drawn and nothing able to
  press anything on it.

  A FIFTH owner (cl_entview.qc, build 54) and a sixth (the avatar customizer)
  would each have to edit all the previous ones.  That is the thing to stop.

  WHAT THIS DOES.  One bitmask, declared in the one file everybody compiles
  after, so no owner ever needs to name another.  Claim when you take the
  mouse, release when you are done, and the cursor goes back to the game
  exactly when the last claim drops -- which is the property all four sites
  above were separately trying and failing to express.

  The panel flags (ui_he_open, rec_sb_open, rec_wt_open, ui_rs_cursor) STAY.
  They answer "is this panel up", which drawing and input still ask, and that
  is a different question from "does it want the mouse" -- the results card
  spends most of its life drawn and passive, which is exactly why build 48 had
  to introduce ui_rs_cursor separately from ui_rs_open.

  NUMBERING IS FIXED AND SHARED.  UIC_ENTVIEW = 16 is reserved for
  cl_entview.qc by the session that owns that file; do not renumber these to
  close a gap.
===========================================================================
*/
#define UIC_WATCH    1          // cl_watch.qc     -- replay chrome
#define UIC_SCORES   2          // cl_scores.qc    -- leaderboard
#define UIC_HUDEDIT  4          // cl_hudedit.qc   -- layout editor
#define UIC_RESULTS  8          // cl_results.qc   -- the run card
#define UIC_ENTVIEW  16         // cl_entview.qc   -- entity inspector (build 54)
#define UIC_AVATAR   32         // cl_avatar.qc    -- customizer (not built yet)

float ui_cursor_claims;         // bitmask of UIC_*; 0 means the game has the mouse

/*
  Take the mouse for `who`.  Idempotent: claiming twice is a no-op, so a panel
  that re-opens without closing cannot leave a claim it will never drop.
*/
void(float who) UI_CursorClaim =
{
	if (ui_cursor_claims & who)
		return;
	ui_cursor_claims = ui_cursor_claims | who;

	// Only the FIRST claim touches the engine. setcursormode(TRUE) is not free
	// -- it moves kdm_game into key_dest_absolutemouse (cl_watch.qc:3897) --
	// and calling it again while already in that mode is a no-op that hides
	// which panel actually owns the state.
	if (ui_cursor_claims == who)
		setcursormode(TRUE, "", '0 0 0', 1);
};

/*
  Give it back.  The cursor returns to the game ONLY when the last claim drops.
*/
void(float who) UI_CursorRelease =
{
	if (!(ui_cursor_claims & who))
		return;

	// Subtraction, not &~. The guard above proves the bit is set, so this is
	// exact, and it does not depend on how fteqcc lowers a bitwise complement
	// of a float -- which is the sort of thing that works until it does not.
	ui_cursor_claims = ui_cursor_claims - who;

	if (!ui_cursor_claims)
		setcursormode(FALSE);
};

/*
  For a panel that wants to know whether ANYONE holds the mouse -- e.g. to
  refuse to open on top of another modal. Returns the raw mask.
*/
float() UI_CursorHeld =
{
	return ui_cursor_claims;
};

void(string id, vector pos, vector size, vector anchor) HUD_Rect =
{
	if (!ui_he_open)
		return;
	if (hude_n >= HUDE_MAX)
		return;

	// A DEGENERATE BOX IS NOT A REGISTRATION.  Several panels fade out entirely
	// -- the board rows on a three-second timer, the split list and the segment
	// column on their own -- and a drawer that reaches its HUD_Rect having drawn
	// no text hands over a zero width.  Refusing it lets the editor tell "drew
	// nothing" apart from "drew something tiny" and put up its own nominal rect,
	// which is what makes a faded panel still draggable.
	if (size_x < 1 || size_y < 1)
		return;

	hude_id[hude_n]     = id;
	hude_pos[hude_n]    = pos;
	hude_size[hude_n]   = size;
	hude_anchor[hude_n] = anchor;
	hude_n = hude_n + 1;
};

/*
===========================================================================
  BUILD 31 -- CALM NUMBERS: THE DISPLAY LATCH AND THE ROUNDING STEP.

  "The energy and velocity numbers flash by as a blur at 1000fps."  They do, and
  ONE CORRECTION IS WORTH WRITING DOWN BEFORE THE FIX, because it changes what
  the fix has to be: velocity and energy are NOT per-frame data and never were.
  Both come from STAT_FS_VELOCITY, delivered at cl_netfps 66.6667, so they
  already change at most 66.7 times a second no matter how fast you draw.
  Re-sampling them per tick removes nothing.  67 changes a second IS the blur.

  So there are two independent knobs, because there are two different causes:

    hud_round   quantisation.  The fix for velocity and energy.  A number that
                steps in 5s is legible at any rate; a number that steps in 1s is
                not, however slowly you sample it.

    hud_update  cadence.  The fix for the two strafe-rate cells and the `best`
                line, which genuinely ARE recomputed every rendered frame from
                time-windowed rings (HUD_UpdateTurn, Strafe_PlaneBest).

  hud_update -1, the default, latches once per INPUT FRAME -- a clientcommandframe
  edge, which advances at cl_netfps 66.6667, the same rate the player's body
  advances and the same rate the stats come back at.  So all four readouts change
  together instead of two of them running ahead of the other two.  0 is the old
  per-frame behaviour.  N > 0 is N times a second, for calmer still.

  IT WAS servercommandframe FIRST, AND THAT WAS WRONG.  The measurement is in
  `hud_edit status`, which is exactly why it is there: the first run of it read
  `latch 4.0 Hz` instead of ~67, meaning the edge never fired and every number on
  the HUD was being carried by the stall floor below.  servercommandframe is "the
  input frame the server last acknowledged", and a client of this mod is
  `isindependant` (sv_user.c:8507) with no SV_RunClientCommand, so nothing in
  this build drives the acknowledgement CSQC can see.  clientcommandframe is the
  client's own outgoing sequence and always advances; it is also the literal
  reading of "per tick", which is what was asked for.

  THE 0.25s FLOOR IS NOT DECORATION.  The counter stops during demo playback and
  between servers, and without the floor every latched number would freeze at its
  last value with nothing on screen saying why.  A forced latch four times a
  second is slow enough to still read as calm and fast enough that a stall looks
  like a stall -- and, as above, distinctive enough in the diagnostic to identify
  on sight.

  WHAT IS DELIBERATELY *NOT* GATED: the computation.  Only the displayed value is
  held.  Gating Strafe_PlaneBest's 98-evaluation heading search to the latch was
  the obvious saving and is wrong -- the same call returns `cscale`, which scales
  the strafe bar's own error term, so latching the search latches the BAR.  The
  ask was for calm numbers over a live bar, not a stepping one.  The rings also
  keep sampling every frame, so the windows stay honest and turning the latch off
  shows the same history it always did.
===========================================================================
*/
float  ui_hl_tick;              // TRUE on frames the display may re-sample
float  ui_hl_lastsc;            // last servercommandframe seen
float  ui_hl_lastt;             // cltime of the last latch
float  ui_hl_speed, ui_hl_e;    // the held speedometer and energy readings
float  ui_hl_turn, ui_hl_ideal; // the two rate cells above the strafe bar
float  ui_hl_best;              // the "u/s per tick at best" line
float  ui_hl_have;              // a value has been latched at least once
/*
  BUILD 47: the hud_debug velocity rows, which had never been latched at all.

  Every other panel here goes through ui_hl_tick.  HUD_DrawDebug did not, so its
  numbers printed the live per-RENDERED-FRAME value at two decimals whatever
  hud_update said -- and the value they print is pmove_vel, which really does
  change per rendered frame, because prediction re-runs every frame and lands a
  whole tick ahead or not depending on where the frame falls.  That is the
  "0-4 units per frame at 1000 fps" report: an unlatched readout of a quantity
  that is only defined per tick.

  The underlying oscillation is a separate bug and is fixed separately (the
  interpolation back-date uses cl_netfps raw while the send interval is snapped
  to the tick -- see Net_MatchTicrate in cl_main.qc).  This half is correct on
  its own: a per-tick quantity should be sampled on the tick.
*/
float  ui_hl_dbgxy, ui_hl_dbgz; // the hud_debug xy/z velocity rows

/*
  THE MEASURED LATCH RATE, for `hud_edit status`.

  hud_update -1 is the only setting whose behaviour cannot be read off a
  screenshot or derived from the cvar: it depends on servercommandframe actually
  advancing, and the whole point of the 0.25s floor is that there are states
  where it does not.  Counting the latches and dividing turns "is this doing what
  it says" into a number in the console, which is the same reason every other
  diagnostic in this project prints its columns even when they are boring.

  A count and a one-second window, not a running average: the answer wanted is
  "about 67" or "about 4", and either is legible to one decimal.
*/
float  ui_hl_n;                 // latches since the window opened
float  ui_hl_rate;              // the last full window's answer, Hz
float  ui_hl_ratet;             // cltime the window opened
float  ui_hl_lastm;             // hud_update as of that window; a change restarts it

/*
  BUILD 40.  The wire and the keyboard disagree about the save-lock RIGHT NOW.

  True for the two or three frames of a press or a release during which
  rec_sl_holding (set on the key edge, cl_keys.qc) and STAT_FS_HOLD (set on the
  server, a round trip later) describe different worlds.  Computed and acted on
  in HUD_UpdateLatch immediately below -- which is the one place that CAN act on
  it, and where the essay lives -- and published for the debug panel's `hold`
  row, which is how you tell a guard that armed from one that never disarmed.

  Declared here rather than beside rec_sl_held, which is its natural home, for
  the ordinary QC reason: that block is further down the file and a global has
  to exist before the function that reads it.
*/
float  rec_sl_settle;

void() HUD_UpdateLatch =
{
	local float m;

	m = cvar("hud_update");

	/*
	  ONE EXIT, and the per-frame case does NOT return early.

	  It used to, which cost nothing on screen and broke the diagnostic: the
	  counting below never ran at hud_update 0, so `hud_edit status` went on
	  reporting whatever rate the PREVIOUS setting had measured.  It showed
	  `latch 67.0 Hz  (every frame)` next to a 473 fps counter, which is a
	  measurement disagreeing with the thing in the corner of the same screenshot.
	  A diagnostic that is wrong in one of its three modes is worse than none.
	*/
	if (m == 0)
		ui_hl_tick = TRUE;                  // per rendered frame -- build 30 exactly
	else if (m < 0)
	{
		// clientcommandframe, NOT servercommandframe -- see the essay above.  The
		// latter never advances in this build and the whole thing silently ran on
		// the stall floor.
		ui_hl_tick   = (clientcommandframe != ui_hl_lastsc);
		ui_hl_lastsc = clientcommandframe;
	}
	else
		ui_hl_tick = (cltime - ui_hl_lastt) >= (1 / m);

	/*
	  BUILD 40: DO NOT TAKE A SAMPLE ACROSS A SAVE-LOCK EDGE.

	  The press and the release each have a window in which the two halves of
	  the player's state describe different worlds, and a sample taken inside it
	  is a number that is neither the parked state nor the live one:

	  * PRESS.  The key goes to the server as a client command, so the client
	    knows a full round trip before STAT_FS_HOLD can answer.  Worse, the
	    zeroed .velocity rides the player delta while HOLD (stat 76) and HOLDVEL
	    (77-79) are the highest-numbered stats in the mod, and
	    SV_UpdateClientStats walks ascending and breaks out at 32 tracked
	    entries or a full datagram (sv_send.c:2359-2374) -- deferring the rest
	    to a later packet.  A load-plus-hold is the largest stat storm here, so
	    the snapshot that says "velocity 0" can arrive before the one that says
	    "you are parked", and HUD_LiveVel's substitution does not fire.  That is
	    build 30's original bug reappearing for a single frame.
	  * RELEASE.  See Patch 243: CL_PredictMove decides whether to predict from
	    a pv->pmovetype it only assigns LATER in the same function, so the frame
	    a hold ends still interpolates and hands pmove_vel a blend between the
	    frozen state and the released one.

	  rec_sl_holding is the client's own answer, set on the key-down edge in
	  CSQC_InputEvent and cleared on the key-up (cl_saveloc.qc), and it has
	  never been read here.  While it disagrees with the wire, the readouts
	  simply do not re-sample: the speedometer, `e` and both rate cells hold
	  their last COHERENT sample rather than printing an incoherent one.
	  Nothing is invented, nothing is smoothed, and nothing is drawn that was
	  not measured -- which is the only reading of "accurate numbers over fake
	  numbers" available to a client that cannot yet know the answer.

	  ARMED BY THE EDGE, DISARMED BY EVIDENCE -- the shape of ui_rs_armed, whose
	  header records that a one-frame exemption was tried, measured and found
	  insufficient because the event and the state it implies need not share a
	  snapshot.  But UNLIKE ui_rs_armed this one is also bounded, and by the
	  stall floor immediately below rather than by a new constant: a hold the
	  server REFUSES (`save: nothing saved on this map`, sv_saveloc.qc:1299)
	  leaves rec_sl_holding true against a stat that will never rise, and a guard
	  waiting on evidence that is not coming would freeze the HUD for as long as
	  the key was held.  0.25s is already this function's answer to "how long
	  may a reading stand", so it is this one's too.
	*/
	rec_sl_settle = (rec_sl_holding != (getstatf(STAT_FS_HOLD) != 0));
	if (rec_sl_settle)
		ui_hl_tick = FALSE;

	// The stall floor, and the first frame of the map.  cltime runs backwards
	// across a map change, so the subtraction is guarded rather than trusted.
	// It is also what bounds the settle guard above; see its last paragraph.
	if (!ui_hl_have || cltime < ui_hl_lastt || (cltime - ui_hl_lastt) >= 0.25)
		ui_hl_tick = TRUE;

	if (ui_hl_tick)
	{
		ui_hl_lastt = cltime;
		ui_hl_have  = TRUE;
		ui_hl_n     = ui_hl_n + 1;
	}

	/*
	  The measured rate, over a one-second window.

	  THE WINDOW IS RESTARTED WHEN hud_update CHANGES, and that is not tidiness --
	  a window that straddles the change measures neither mode.  Going from 0 to
	  10 at 751 fps, the first third of the window was still per-frame and the
	  reading came out at 277.8 Hz: a number that is a true average of two modes
	  and a correct answer to no question anyone would ask.  Anyone reading this
	  line is asking "what is it doing NOW".

	  cltime runs backwards across a map change, so the window start is guarded
	  rather than trusted.
	*/
	if (m != ui_hl_lastm || cltime < ui_hl_ratet)
	{
		ui_hl_lastm = m;
		ui_hl_ratet = cltime;
		ui_hl_n     = 0;
	}
	else if (cltime - ui_hl_ratet >= 1)
	{
		ui_hl_rate  = ui_hl_n / (cltime - ui_hl_ratet);
		ui_hl_n     = 0;
		ui_hl_ratet = cltime;
	}
};

/*
  The quantisation step: 0 off, or 1 / 2 / 5.

  1 is the default and is a NO-OP on everything it is applied to -- every one of
  those readouts already prints through rint or %.0f -- so this ships changing
  nothing and only starts to matter when it is raised.  Anything else falls back
  to 1 rather than being honoured, because a step of 3 or 7 produces a sequence
  that reads as a fault in the game rather than as a setting.
*/
float(float v) HUD_Round =
{
	local float s;

	s = cvar("hud_round");
	if (s <= 0)
		return v;
	if (s != 1 && s != 2 && s != 5)
		s = 1;
	return s * rint(v / s);
};

// --- per-frame state --------------------------------------------------------
float  ui_prev_speed;       // last frame's horizontal speed, for the colour only
float  ui_lasttime;         // cltime of the previous HUD frame
float  ui_lastyaw;
float  ui_turnrate;         // windowed, degrees/second, unsigned
float  ui_turnsign;         // +1 turning right, -1 turning left (coherence-gated)

/*
  The TARGET rate, low-passed.

  ui_turnrate is a window average over hud_strafe_smooth; `ideal` was recomputed
  from scratch every rendered frame.  Comparing a smoothed number against an
  unsmoothed one puts all of the second one's noise straight into the error, and
  on a ramp `ideal` is a function of a normal that can change every frame -- so
  the bar churned even with a perfectly steady hand.  Same time constant as the
  numerator, so the two sides of the comparison are measured alike.

  ui_ideal_regime is which of air / ramp / ground produced the last value.  A
  regime change is a discontinuity, not noise, and smoothing across it would
  drag a flat-air target into the first quarter second of a ramp.
*/
float  ui_ideal_lp;
float  ui_ideal_regime;     // -1 none, 0 air, 1 ramp, 2 ground

/*
  Where the strafe panel finished drawing, in screen y.

  The board panel stacks under it, and it must not be computed independently or
  the two drift apart the moment the bar's contents change -- which they do,
  every time it says "too slow to grade" instead of a pair of rate cells.
  HUD_DrawStrafe publishes this on EVERY path, and the frame function seeds it
  first so the board still has somewhere to go when the bar is switched off.
*/
float  ui_strafe_bottom;

/*
  The ramp plane, held.

  See HUD_DrawStrafe.  ui_ramp_norm is the last plane the ENGINE actually
  clipped against (STAT_FS_BOARDNORM), and ui_ramp_time is when we last saw
  STAT_FS_RAMPCONTACT set, so a one-frame dropout does not throw the panel back
  to the flat-air target -- which is between 1.8x and 6x larger.
*/
vector ui_ramp_norm;
float  ui_ramp_time;

/*
  BUILD 39.  WHY the plane above is what it is -- because "returned '0 0 0'" is
  two entirely different answers and the caller could not tell them apart.

  Not riding is not the same as riding with no usable plane.  The first means
  the flat-air formula is CORRECT and the panel should use it; the second means
  there is no right answer and the panel has been substituting one that
  sh_strafe.qc:289 says is between 1.8x and 6x too big.  Same return value,
  opposite meanings, and the strafe target has been reported wrong on ramps for
  as long as anyone has looked at it.

  RW_FLIPPED is here because of a specific suspicion, not for symmetry -- see
  the orientation block in HUD_RampNormal.
*/
#define RW_NONE     0   // nothing asked yet this frame
#define RW_FRESH    1   // the stat gave us a plane on this frame
#define RW_HELD     2   // inside RAMPHOLD of one, and using it
#define RW_FREEAIR  3   // not riding at all: flat IS the answer
#define RW_NOPLANE  4   // riding, and both normals read '0 0 0'
#define RW_FLIPPED  5   // riding, and the orientation test inverted the plane
float  ui_ramp_why;

/*
  Build 39.  RIDING, as Board_RampHold answered it this frame -- kept apart from
  ui_ramp_why on purpose.

  The two holds have different lengths: Board_RampHold bridges RAMP_GAP (0.08s,
  the engine's own PMSRC_BOARD_AIRGATE) while the PLANE is held for RAMPHOLD
  (0.25s).  So for up to about a sixth of a second after leaving a ramp the
  plane is still available and you are not on it any more, and "which plane are
  we using" and "are we on a ramp" are genuinely two questions.  The strict
  branch in HUD_DrawStrafe has to ask the second one -- refusing to draw a flat
  target for a quarter second after every ramp exit would be a new bug wearing
  the old one's clothes.
*/
float  ui_ramp_riding;

// Build 39: which branch HUD_DrawStrafe took and what it fed the plane maths,
// published for the debug panel.  See the regime block in that function.
float  ui_strafe_regime, ui_strafe_nz, ui_strafe_wn;

/*
  BUILD 40: what HUD_WishDir was handed and what it made of it.

  Published because the bug it exists to fix is INVISIBLE otherwise.  A strafe
  target that is briefly wrong needs a ramp to observe, and a ramp entry cannot
  be scripted -- but the cause is a zeroed usercmd, which shows up standing on
  flat ground with one key held, at any frame rate, in one row.

  ui_wish_raw is what the engine handed over AFTER getinputstate: on the old
  path this read 0/0 for about one frame in five with the key still down, and
  the whole of report A follows from that.  ui_wish_kb says the keyboard
  fallback supplied the answer instead, which should be rare -- if it is on
  every frame, getinputstate is failing and the reason is worth finding.
*/
vector ui_wish_raw;
vector ui_wish_dir;
float  ui_wish_kb;

// Build 39: whether HUD_Feet returned the predicted origin, and how far that
// was from the answer build 38 would have given.  See HUD_Feet.
float  ui_src_pred, ui_src_disagree;

/*
  Build 30.  A save-lock hold is parked RIGHT NOW.

  Set once per frame from STAT_FS_HOLD, at the top of HUD_Draw, so everything
  below can ask the question without each panel reading the stat for itself.
  Two things use it: the velocity source (the freeze zeroes .velocity, so the
  live number has to come from STAT_FS_HOLDVEL instead) and the energy-history
  push, which must not sample a frozen player -- see HUD_Draw.

  It is deliberately NOT the same thing as TF_FROZEN.  That bit says the run
  CLOCK is stopped, which is also true while the console has focus and during a
  replay; this one says the player's velocity has been replaced by a zero, which
  is the specific condition the readouts have to work around.
*/
float  rec_sl_held;
// Its build 40 companion, rec_sl_settle, is declared up with the latch state it
// suppresses -- HUD_UpdateLatch is above this line and QC needs the global
// first.  The two are read together everywhere else.

// --- energy -----------------------------------------------------------------
float  ui_anchor_z;         // the height everything is measured from
float  ui_anchor_zone;      // which zone set it; -1 = none yet
float  ui_anchor_manual;    // set by hand with `ui_anchor`; zones will not move it
string ui_anchor_map;

/*
  MOMENTUM'S REFERENCE, which is a different one and is quoted:

      "Gets the player or spec target's current mechanical energy, expressed
       as the height (in units) reachable above their last jump position"
                    -- momentum/panorama/scripts/types-mom/apis.d.ts:158

  So their zero is the ground you last jumped from, not the start of the leg.
  On a surf map the two agree for the whole run -- you jump off the block once
  and never touch ground again -- and they diverge exactly where you land and
  jump again, which is where "how am I doing against the start" and "what did
  I make since takeoff" genuinely are different questions.

  It is the default because it is the one that can be COMPARED: the same test
  in both games has to produce the same number or it is not a measurement.  It
  also works on a map with no zone file, where the zone anchor has nothing to
  say and the readout goes grey.
*/
/*
  ui_jump_z, ui_jump_have, ui_ground_z, ui_was_onground and ui_jump_lastorg are
  DECLARED IN cl_board.qc, which compiles first -- build 26 moved them there so
  the save-lock's seq.txt writer could see them, because a load used to destroy
  the reference and that is the whole of "the anchor is useless after a save".
  The essay is beside them.  Every reader here is unchanged; they were always
  cl_board.qc's rule anyway, since the teleport guard below is SEG_JUMPDIST.
*/

// Energy history ring.  256 SAMPLES, deliberately no longer 256 FRAMES -- see
// the rate limiter in HUD_EnergyRate, which is what makes the span a function
// of hud_strafe_window instead of a function of your frame rate.
#define EWIN 256
float  ui_ehist_e[EWIN];
float  ui_ehist_t[EWIN];
float  ui_ehist_head;       // next slot to write, wrapped -- NOT a total count,
float  ui_ehist_len;        // because a float counter loses integer precision
                            // past 2^24 and this runs every frame
float  ui_ehist_lastt;      // cltime of the newest stored sample
float  ui_eta;              // dE/dt as a fraction of the physical ceiling

void() HUD_ClearEnergyHistory;      // defined below; the anchor reset calls it
void() HUD_ClearTurnHistory;        // likewise

void() HUD_ReadCvars =
{
	ui_cv_scale     = cvar("hud_scale");        if (!ui_cv_scale) ui_cv_scale = 2;

	ui_cv_speed     = cvar("hud_speed");
	ui_cv_energy    = cvar("hud_energy");
	ui_cv_energyref = cvar("hud_energy_ref");
	ui_cv_predicted = cvar("hud_predicted");
	ui_cv_strict    = cvar("hud_strafe_strict");
	ui_cv_strafe    = cvar("hud_strafe");
	ui_cv_board     = cvar("hud_board");
	ui_cv_keys      = cvar("hud_keys");
	ui_cv_debug     = cvar("hud_debug");

	ui_cv_boardfade = cvar("hud_board_fade");   if (ui_cv_boardfade <= 0) ui_cv_boardfade = 3;
	ui_cv_seqlive   = cvar("hud_seq_live");

	ui_cv_mapinfo   = cvar("hud_mapinfo");
	ui_cv_mappos_x  = cvar("hud_mapinfo_x");
	ui_cv_mappos_y  = cvar("hud_mapinfo_y");

	// CLAMPED, not just defaulted.  hud_strafe_smooth had no guard at all, and
	// at 0 HUD_UpdateTurn's window collapses to a single frame -- which is
	// exactly the per-frame ratio buzz the windowed rewrite existed to remove.
	// 0.02 is one 66.7 Hz tick, the shortest window that can mean anything.
	ui_cv_smooth    = cvar("hud_strafe_smooth"); if (ui_cv_smooth < 0.02) ui_cv_smooth = 0.2;
	ui_cv_window    = cvar("hud_strafe_window"); if (ui_cv_window <= 0) ui_cv_window = 2;
	ui_cv_band      = cvar("hud_strafe_band");   if (ui_cv_band <= 0)   ui_cv_band = 1.0;
	ui_cv_curve     = cvar("hud_strafe_curve");
	if (ui_cv_curve < 0.2) ui_cv_curve = 1;
	if (ui_cv_curve > 2)   ui_cv_curve = 1;
	ui_cv_minspeed  = cvar("hud_strafe_minspeed");
	if (ui_cv_minspeed < 0) ui_cv_minspeed = 200;

	// Fractions of the screen, so a layout survives a resolution change.
	ui_cv_speedpos_x  = cvar("hud_speed_x");   ui_cv_speedpos_y  = cvar("hud_speed_y");
	ui_cv_keyspos_x   = cvar("hud_keys_x");    ui_cv_keyspos_y   = cvar("hud_keys_y");
	ui_cv_debugpos_x  = cvar("hud_debug_x");   ui_cv_debugpos_y  = cvar("hud_debug_y");
	ui_cv_strafepos_x = cvar("hud_strafe_x");  ui_cv_strafepos_y = cvar("hud_strafe_y");
};

void() HUD_RegisterCvars =
{
	registercvar("hud_scale",   "2", CVAR_ARCHIVE);
	registercvar("hud_speed",   "1", CVAR_ARCHIVE);
	registercvar("hud_energy",  "1", CVAR_ARCHIVE);
	registercvar("hud_energy_ref", "1");
	/*
	  Build 39.  All four default on and all four exist to be turned OFF: the
	  numbers they change are numbers you have been reading for months, so there
	  has to be a way back to the old ones.  See HUD_Feet and the regime block
	  in HUD_DrawStrafe.

	  BUILD 40 ADDED THE ARCHIVE FLAG, which build 39 left off all four while
	  every cvar around them has it.  A revert switch that forgets itself on the
	  next launch is not a revert switch -- you would set hud_predicted 0 to
	  compare a reading, alt-tab, come back tomorrow and be silently on the new
	  path again with no way to tell from the screen.
	*/
	registercvar("hud_predicted", "1", CVAR_ARCHIVE);
	registercvar("hud_strafe_strict", "1", CVAR_ARCHIVE);
	registercvar("hud_strafe_orient", "1", CVAR_ARCHIVE);
	registercvar("hud_board_exact", "1", CVAR_ARCHIVE);
	// Build 40: a self-clearing frame counter, not a mode -- see HUD_WishDir.
	// Deliberately NOT archived: leaving it set across a restart would be a
	// console full of trace lines with no memory of asking for them.
	registercvar("hud_wishtrace", "0");
	registercvar("hud_eyetrace", "0");
	// Build 47, and NOT archived for the same reason as the two above -- see
	// HUD_VelTrace.  At 1400 fps this is the one of the three that would fill a
	// log fastest, and it is the one you most want to leave on by accident.
	registercvar("hud_veltrace", "0");
	registercvar("hud_strafe",  "1", CVAR_ARCHIVE);
	registercvar("hud_board",   "1", CVAR_ARCHIVE);
	registercvar("hud_keys",    "1", CVAR_ARCHIVE);

	// OFF by default now.  It is a physics debugger, not a surf HUD, and it
	// sits over the left third of the screen.
	registercvar("hud_debug",   "0", CVAR_ARCHIVE);

	registercvar("hud_board_fade", "3");

	/*
	  BUILD 34 -- the open segment's provisional rows.

	  1 (default): the moment you touch a ramp the column shows the touchdown's
	  cost and the ride's running total, instead of both appearing together when
	  you leave.  The rows are drawn dimmer, are not in the ring, and are replaced
	  by the identical committed rows at segment end -- see HUD_DrawSeq.

	  0 is build 33 byte for byte, which is the bisection rule this project's
	  behaviour changes follow.  It is also the switch to reach for if a live row
	  ever disagrees with the committed row that replaces it: that would mean the
	  two spellings of Board_SegmentEnd's arithmetic have drifted, and seg_live_de
	  in cl_board.qc is the one to read.
	*/
	registercvar("hud_seq_live", "1", CVAR_ARCHIVE);

	/*
	  BUILD 34 -- the top-right block: FTESurf / map / tier / stages.

	  Its x is the block's RIGHT edge and its y is its TOP, because it is
	  right-aligned and grows downward -- the HEA_RT anchor cl_hudedit.qc gained
	  for it.  0.99 rather than 1.0 so the longest line has a margin off the edge
	  of the screen on any aspect ratio.

	  The tier comes from serverinfo and needs no cvar; see HUD_DrawMapInfo for
	  why it is published by the engine rather than parsed here.
	*/
	registercvar("hud_mapinfo",   "1",    CVAR_ARCHIVE);
	registercvar("hud_mapinfo_x", "0.99", CVAR_ARCHIVE);
	registercvar("hud_mapinfo_y", "0.02", CVAR_ARCHIVE);

	/*
	  The sequence column (build 12): the launch, then every ramp and every air
	  time of the run, in order, beside the crosshair.

	  x is an OFFSET FROM THE SCREEN CENTRE, not a fraction of the width, so it
	  stays the same distance from the crosshair on any aspect ratio.  Negative
	  is left.  y is the BOTTOM of the column -- rows stack upward from it, so
	  the newest one is always in the same place under your eye however many
	  there are.
	*/
	registercvar("hud_seq",      "1", CVAR_ARCHIVE);
	registercvar("hud_seq_x",    "-0.25", CVAR_ARCHIVE);	// offset from screen centre; build 13, was -0.055 (on the strafe bar)
	registercvar("hud_seq_y",    "0.5", CVAR_ARCHIVE);	// the block is CENTRED on this, not hung below it
	registercvar("hud_seq_rows", "10");
	// Build 18: the % of the available air gain each airtime took.  Air rows
	// only -- see the note in HUD_DrawSeq.
	registercvar("hud_seq_pct",  "1", CVAR_ARCHIVE);

	/*
	  BUILD 20 -- what the rows are measured in.

	    0   u/s, the build 19 string exactly.  What that energy was WORTH at the
	        speed you left with, which is the honest way to compare a gain
	        against a speedometer.
	    1   energy, in world units of height (default).

	  Energy is the default because it is what the row is actually made of: the
	  percentage beside it has always been an energy ratio, and the figure to its
	  left is now literally that fraction's numerator.  Before this the row
	  printed a speed next to a percentage of an energy and invited you to relate
	  them, which cannot be done.  Same unit as the `e` readout by the crosshair
	  at hud_energy 1, so the two can be added.

	  Two values and not three: Strafe_EquivSpeed(dE) -- what the energy is worth
	  from a standstill -- is a third encoding of one fact, and this readout
	  already has two too many.

	  It covers the single-line readout under the strafe bar as well.  Two
	  readouts of the same measurement disagreeing about their unit is worse than
	  either choice of unit.
	*/
	registercvar("hud_seq_units", "1", CVAR_ARCHIVE);

	/*
	  BUILD 20 -- joining rows that were one thing.

	    0   off; build 19 exactly.
	    1   join across an ARTIFACT only (default).
	    2   join always, so the column strictly alternates air/ramp/air/ramp.

	  "Follow a ramp around a bend and you get two board reports in a row."  The
	  state machine cannot emit two of a kind directly; what happens is that the
	  segment between them was refused -- a few ticks of lost contact, a bounce
	  off a lip -- and its neighbours ended up adjacent with nothing between.
	  Mode 1 repairs exactly that and no more.

	  It stops at a REAL gap: a genuine grounded phase, or a teleport.  The merge
	  exists to put back a row that was lost, and a grounded phase is not lost --
	  it is deliberately excluded (the ground has its own readout under the bar).
	  Sewing across it would claim a continuity the design refuses to measure and
	  would swallow a landing and a jump into one row claiming to be one thing.
	  Mode 2 is there for anyone who wants the alternation more than the honesty.
	*/
	registercvar("hud_seq_merge", "1", CVAR_ARCHIVE);

	/*
	  BUILD 25 -- the touchdown as its own row.

	    0   build 24 exactly: the board's cost is folded into the ramp row.
	    1   air / board / ramp, three rows (default).

	  The three still sum to what the two summed to -- the split moves one value,
	  it does not create or destroy any -- so the column's accounting is the same
	  either way and only its resolution changes.  0 is here because every
	  behaviour change in this project ships with a way to bisect it, and because
	  a column that gains half again as many rows is a preference as well as a
	  measurement.  See SEG_BOARD in cl_board.qc.
	*/
	registercvar("hud_seq_board", "1", CVAR_ARCHIVE);

	// SECONDS, not frames -- deliberately.  A frame count means two entirely
	// different windows at 60fps and at 300fps, and the movement it is
	// filtering runs at a fixed 66.7Hz regardless of either.
	//
	// 0.2s is about thirteen ticks.  It was 0.12, which was too short for what
	// the filter is now: this is a WINDOW AVERAGE of the yaw path, not an
	// exponential filter on a per-frame ratio, so the whole window contributes
	// equally and a short one still carries the sampling noise it was meant to
	// remove.  Half a strafe half-cycle is roughly 0.33s, so 0.2 stays well
	// inside one and still feels like your hand.
	registercvar("hud_strafe_smooth", "0.2");

	// The efficiency gauge's window.  Two seconds is not caution, it is the
	// measurement: dE/dt over a shorter window is dominated by the ramp you
	// happen to be on rather than by how you are strafing.
	registercvar("hud_strafe_window", "2");

	/*
	  Full deflection of the bar = this fraction off the ideal rate.

	  1.0, and the number is not a taste: Strafe_Quality is defined and non-zero
	  over r in [0, 2] (sh_strafe.qc), i.e. exactly |err| <= 1.  At the old 0.5
	  the bar reached its stop while the grade was still 0.75, so three quarters
	  of the grading range lived off the end of the scale and a real hand
	  strafing 100-150 deg/s against a 45-60 deg/s target sat pinned.  Now the
	  bar ends where the grade ends: empty is "not turning", full is "turning
	  twice as fast as you should", and the middle is right.
	*/
	registercvar("hud_strafe_band", "1.0");

	/*
	  Shape of the axis.  1 is linear; below 1 bends travel towards the centre.

	  It was a hard-coded signed square root, which at band 0.5 spent a fifth of
	  the bar's travel on the first 2% of error -- 52 px at hud_scale 2 for
	  2.3 deg/s at 1000 u/s, which is inside a hand's own noise and inside the
	  quantisation of a windowed yaw measurement.  That is the whole of "way too
	  sensitive".  Linear by default; 0.5 restores the old feel exactly.
	*/
	registercvar("hud_strafe_curve", "1");

	/*
	  Below this speed the bar refuses.

	  The ideal rate is atan2(gain, speed) per tick, so it grows without bound
	  as speed falls: ~115 deg/s at 1000 u/s, 456 at 250, and 6000 at a dead
	  stop -- which is what the readout showed standing still.  The number is
	  correct and useless; no one strafes at a stop, and printing a four-digit
	  target next to your actual rate reads as an error.  200 is a little under
	  sv_maxspeed, so it clears the moment you are genuinely moving.
	*/
	registercvar("hud_strafe_minspeed", "200");

	// CVAR_ARCHIVE from build 31 on every value the layout editor can write.
	// See the essay beside registercvar in cl_defs.qc: on an install that has a
	// default.cfg the flag is inert and `seta` from the editor is what actually
	// persists these, but a cvar that is MEANT to survive a quit should say so
	// where it is declared rather than only in the code that happens to write it.
	registercvar("hud_speed_x",  "0.5",   CVAR_ARCHIVE); registercvar("hud_speed_y",  "0.68", CVAR_ARCHIVE);
	registercvar("hud_strafe_x", "0.5",   CVAR_ARCHIVE); registercvar("hud_strafe_y", "0.42", CVAR_ARCHIVE);
	registercvar("hud_debug_x",  "0.012", CVAR_ARCHIVE); registercvar("hud_debug_y",  "0.30", CVAR_ARCHIVE);

	// x = 0 means "auto": right-hand side, with the gap to the screen edge
	// measured from the gap to the floor rather than guessed as a fraction.
	// Any non-zero value is a left-edge fraction, like the other panels.
	registercvar("hud_keys_x",   "0", CVAR_ARCHIVE); registercvar("hud_keys_y",   "0.84", CVAR_ARCHIVE);

	/*
	  BUILD 31 -- THE BOARD PANEL GETS A POSITION OF ITS OWN.

	  It never had one: it is drawn at hud_strafe_x and at whatever y the bar
	  finished on, which is the right default and was the only option.  The
	  editor needs somewhere to write a dragged position to.

	  -1 IS A SENTINEL, NOT A COORDINATE, and it means "stay stacked under the
	  bar" -- build 30's behaviour exactly, including the part that matters,
	  which is that the panel follows the bar's own bottom edge as the bar
	  changes height rather than sitting at a constant offset from it.  Dragging
	  it writes real fractions and detaches it; `hud_edit` offers re-attach, and
	  setting either back to -1 by hand does the same thing.

	  Both axes share one test.  Detaching only the y would leave the panel
	  tracking a bar it is no longer under, which is not a state worth being
	  able to reach by accident.
	*/
	registercvar("hud_board_x",  "-1", CVAR_ARCHIVE); registercvar("hud_board_y",  "-1", CVAR_ARCHIVE);

	/*
	  BUILD 31 -- how often the four live numbers are allowed to CHANGE, and in
	  what step.  The essay is above HUD_UpdateLatch; the short version is that
	  hud_round is the fix for velocity and energy (which arrive at 66.7 Hz and
	  blur because that rate is a blur, not because they are sampled too often)
	  and hud_update is the fix for the strafe cells (which really are recomputed
	  every rendered frame).

	    hud_update   0 = every frame, -1 = per server snapshot (default), N = N Hz
	    hud_round    0 = off, or 1 (default, a no-op) / 2 / 5
	*/
	registercvar("hud_update",   "-1", CVAR_ARCHIVE);
	registercvar("hud_round",    "1",  CVAR_ARCHIVE);
};

/*
===========================================================================
  Text helpers.

  HUD_TextR is new and is not a nicety: the readouts used to line their
  columns up with printf padding ("%8.2f"), which only works in a
  fixed-pitch font.  Now that they are drawn in Roboto, a right edge has to
  be measured rather than counted.
===========================================================================
*/
/*
  All three snap the size to the current face's baked ladder (Font_Px).  Doing
  it here rather than at the call sites means every readout is drawn at a size
  the font was actually rendered at, whatever hud_scale is set to -- including
  the 9*scale = 18px cells, which were resampling off the 16 and 20 bakes and
  were the one visibly soft thing on the HUD.
*/
void(vector pos, string s, float sz, vector rgb, float a) HUD_Text =
{
	sz = Font_Px(sz);
	drawstring(pos, s, [sz, sz], rgb, a, 0);
};

void(vector pos, string s, float sz, vector rgb, float a) HUD_TextC =
{
	sz = Font_Px(sz);
	pos_x = pos_x - stringwidth(s, TRUE, [sz, sz]) * 0.5;
	drawstring(pos, s, [sz, sz], rgb, a, 0);
};

void(vector pos, string s, float sz, vector rgb, float a) HUD_TextR =
{
	sz = Font_Px(sz);
	pos_x = pos_x - stringwidth(s, TRUE, [sz, sz]);
	drawstring(pos, s, [sz, sz], rgb, a, 0);
};

/*
  Speed colour.  The same idea as Momentum's range colour profiles
  (momentum/cfg/speedometer/speedometer_colorprof*.kv3): flat white, gain
  blue-green, loss orange -- so the eye reads gain/loss before it reads the
  number.
*/
vector(float gain) HUD_GainColor =
{
	if (gain >  1.0)  return '0.34 0.78 1.00';
	if (gain >  0.05) return '0.48 0.93 0.48';
	if (gain < -1.0)  return '1.00 0.34 0.34';
	if (gain < -0.05) return '1.00 0.74 0.00';
	return '1 1 1';
};

// Green through red, for a 0..1 quality.
vector(float q) HUD_QualityColor =
{
	if (q < 0)    return '0.65 0.65 0.65';      // no answer
	if (q > 0.96) return '0.30 1.00 0.45';
	if (q > 0.85) return '0.70 0.95 0.35';
	if (q > 0.65) return '1.00 0.85 0.25';
	if (q > 0.40) return '1.00 0.55 0.20';
	return '1.00 0.30 0.30';
};

/*
===========================================================================
  Energy anchor.

  Energy is only meaningful against a reference height, and the right one is
  the floor of the start zone of the leg you are on -- main track, each
  stage and each bonus having its own.  So: whenever you are standing in a
  start-type zone, that zone becomes the anchor, and it then STAYS until you
  enter a different one.

  IT MUST NOT MOVE BY ITSELF.  wrlines originally re-armed its anchor from a
  "settled on ground" test (|vz| < 30 held three frames inside a six-unit
  band) and that condition is satisfied at the APEX OF EVERY ARC -- at
  g = 800 the vertical speed crawls through zero slowly enough to hold for
  about a quarter of a second.  The zero point silently re-based itself on
  every single jump.  Zones only.
===========================================================================
*/
void(vector org) HUD_UpdateAnchor =
{
	local float z;

	if (zone_mapname != ui_anchor_map)
	{
		ui_anchor_map    = zone_mapname;
		ui_anchor_zone   = -1;
		ui_anchor_z      = 0;
		ui_anchor_manual = 0;           // a new map is a new question
		ui_jump_have     = 0;           // and so is where the last jump was: the
		                                // 512-unit teleport guard below cannot be
		                                // relied on to notice a spawn that happens
		                                // to be near the last map's exit
		Board_Clear();
		HUD_ClearEnergyHistory();
		HUD_ClearTurnHistory();
		Keys_Clear();               // a key held through a map change never sends its release
	}

	// A hand-set anchor outranks the zones, the way wrlines' WR_ANCHOR_MANUAL
	// does: you asked for a reference, so nothing should quietly replace it.
	if (ui_anchor_manual)
		return;

	for (z = 0; z < zone_count; z = z + 1)
	{
		if (zone_type[z] != ZONE_START && zone_type[z] != ZONE_STAGE)
			continue;
		if (!Zone_PointInside(z, org))
			continue;
		if (z != ui_anchor_zone)
		{
			ui_anchor_zone = z;
			ui_anchor_z    = zone_bottom[z];
		}
		return;
	}
};

/*
  Are you standing in a START zone?  Build 47.

  START only, not START-or-STAGE like HUD_UpdateAnchor above: this answers
  "is this a fresh start" for the energy re-base, and a stage boundary is a
  place you fly through rather than a place you pick a start from.  The server
  asks the same question with SV_ZoneStartAt and gets the same answer, because
  both VMs parse the same zone file with the same code.

  A point test, matching HUD_UpdateAnchor and matching the server's arm scan at
  run_zone_hull 1 -- occupancy is a point question.
*/
float(vector org) HUD_InStartZone =
{
	local float z;

	for (z = 0; z < zone_count; z = z + 1)
	{
		if (zone_type[z] != ZONE_START)
			continue;
		if (Zone_PointInside(z, org))
			return TRUE;
	}
	return FALSE;
};

/*
  Momentum's reference height: the ground you last jumped from.

  A jump is "was on the ground last frame, is not now, and is going UP".  The
  velocity test is the whole of the difference between a jump and walking off
  a ledge, and Momentum's own wording -- last JUMP position -- says a ledge
  must not move it.

  What gets latched is ui_ground_z, the last z seen while standing, and NOT
  the origin at the frame the transition is noticed.  By then the jump tick
  has already run and the player is up to 268 * 0.015 = 4 units clear, which
  would be a silent 4-unit error in a number whose whole job here is to be
  compared against another game.

  Before the first jump the reference tracks the ground, so standing still
  reads 0 and a prestrafe reads its own v^2/2g -- which is the 52 case.  A
  teleport re-bases it: the run-voiding kind moves z by thousands and would
  otherwise read as the jump of a lifetime, the same trap cl_board.qc guards
  with the same 512-unit rule.
*/
void(vector org, vector vel, float onground) HUD_UpdateJumpRef =
{
	/*
	  BUILD 26: A RESTORE IN FLIGHT SUSPENDS THE GUARD UNTIL IT ARRIVES.

	  A save-lock load moves you further than SEG_JUMPDIST in almost every real
	  case, so without this the branch below re-bases the reference to wherever
	  you landed -- which is what it did, and which is the whole of "loading a
	  save-lock completely forgets your energy anchor".

	  NOT A ONE-SHOT, and that distinction was measured rather than reasoned.
	  Build 25 gave the segment machine's copy of this same guard a one-frame
	  exemption, and loading a save from ~580 units away spent it on a quiet frame
	  before the position step arrived -- the open segment came back with valid 0
	  and the anchor came back re-based.  The save event and the teleported origin
	  do not have to reach the client in the same snapshot.  So the exemption is
	  held until the position is actually within reach of where the save was
	  taken; Board_Frame disarms it, last in the frame, after both guards have
	  read it.  See ui_rs_armed.

	  ui_jump_lastorg is still updated below, so the guard is armed correctly for
	  ordinary movement the moment the restore lands.
	*/
	if (!ui_rs_armed)
	if (!ui_jump_have || vlen(org - ui_jump_lastorg) > SEG_JUMPDIST)
	{
		ui_ground_z  = org_z;
		ui_jump_z    = org_z;
		ui_jump_have = TRUE;
	}
	ui_jump_lastorg = org;

	if (onground)
	{
		ui_ground_z     = org_z;
		ui_was_onground = TRUE;

		/*
		  BUILD 47: STANDING IN A START BOX, THE FLOOR IS THE REFERENCE.

		  This is the fix for "I made a save that teleports me to the start
		  zone, and instead of 0 the readout says e -65 until I press +jump".

		  Everything above conspires to produce that.  Seq_AnchorRestore puts
		  the SAVE'S ui_jump_z back and arms ui_rs_armed, which suppresses the
		  teleport re-base at the top of this function; the block below only
		  runs on the jump EDGE; and standing still returns here without ever
		  touching ui_jump_z.  So the anchor stays wherever the save's last jump
		  was -- 65 units up, in the report -- and the first +jump is the only
		  thing that can move it.

		  Re-basing while grounded in a start box with the clock stopped is not
		  a new rule, it is the one this function's own header already claims:
		  "before the first jump the reference tracks the ground, so standing
		  still reads 0".  A save-lock load at a start box IS before the first
		  jump of that attempt.

		  GATED ON THE CLOCK, because a running route may pass back through a
		  start box -- surf_doodles' overlaps its stage 1 by 480 units, and five
		  legs in the library put the END zone inside the START zone -- and
		  re-basing mid-run would throw away a live measurement.
		*/
		if (getstatf(STAT_FS_TIMERSTATE) != TS_RUNNING)
		if (HUD_InStartZone(org))
		{
			ui_jump_z    = org_z;
			ui_jump_have = TRUE;
		}
		return;
	}

	// Left the ground.  Only a jump moves the reference; a ledge does not.
	if (ui_was_onground && vel_z > 0)
		ui_jump_z = ui_ground_z;
	ui_was_onground = FALSE;
};

/*
  Push one energy sample and return dE/dt across the window, or 0 if the
  history does not span enough of it to be honest.

  The window is in SECONDS and the samples carry real timestamps, which is
  the whole point: at 300fps a 256-frame ring spans 0.85s and at 60fps it
  spans over four, so a frame count would silently mean a different
  measurement on every machine.  Asking for time and checking what you
  actually got is the only version of this that is comparable.
*/
float(float e, float now, float window) HUD_EnergyRate =
{
	local float i, slot, old_t, old_e, span, interval;

	/*
	  RATE-LIMITED SAMPLING, and this is the fix for a readout that was dead.

	  The ring took one sample per RENDERED FRAME, so it spanned EWIN/fps
	  seconds -- 0.85 s at 300 fps, 0.26 s at the shipped cl_maxfps 1000 --
	  against the guard below, which demands half of hud_strafe_window: one
	  full second.  Above about 255 fps that can never be satisfied, so this
	  returned 0 on every frame, and HUD_QualityColor(0) draws red.  The
	  percentage under the strafe bar has been a permanent red "0%" on any
	  machine fast enough to matter, which is why nobody could tell what it was.

	  Spacing the samples window/(EWIN-1) apart makes the ring span the window
	  BY CONSTRUCTION at any frame rate -- which is what the comment on
	  hud_strafe_window always claimed it did.  Below ~130 fps every frame is
	  still taken, so a slow machine sees no change at all.
	*/
	interval = window / (EWIN - 1);

	if (!ui_ehist_len || now - ui_ehist_lastt >= interval || now < ui_ehist_lastt)
	{
		ui_ehist_e[ui_ehist_head] = e;
		ui_ehist_t[ui_ehist_head] = now;
		ui_ehist_lastt = now;
		ui_ehist_head = ui_ehist_head + 1;
		if (ui_ehist_head >= EWIN)
			ui_ehist_head = 0;
		if (ui_ehist_len < EWIN)
			ui_ehist_len = ui_ehist_len + 1;
	}

	// Walk back for the newest sample that is already older than the window.
	// The recent end of the measurement is the LIVE value rather than a stored
	// one, so it does not matter whether this frame pushed a sample or not.
	old_t = now;
	old_e = e;
	for (i = 0; i < ui_ehist_len; i = i + 1)
	{
		slot = ui_ehist_head - 1 - i;
		while (slot < 0)
			slot = slot + EWIN;
		old_t = ui_ehist_t[slot];
		old_e = ui_ehist_e[slot];
		if (now - old_t >= window)
			break;
	}

	span = now - old_t;
	if (span < window * 0.5 || span <= 0)
		return 0;
	return (e - old_e) / span;
};

void() HUD_ClearEnergyHistory =
{
	ui_ehist_head  = 0;
	ui_ehist_len   = 0;
	ui_ehist_lastt = 0;
	ui_eta         = 0;
};

/*
  Build 30.  Drop the held ramp plane, and the target that was derived from it.

  Called from Board_ResetContact, which is cl_board.qc's answer to a save-lock
  load; forward-declared there because that file compiles first.  The two halves
  of "forget the surface you were on" live in the files that own the state, and
  there is one caller so they cannot get out of step.

  ui_ramp_norm is held for RAMPHOLD (0.25 s) after contact is lost, so that a
  one-frame dropout does not throw the strafe bar back to the flat-air target.
  Across a teleport that hold is the bug rather than the feature: for a quarter
  of a second after a load the bar is graded against the plane of a ramp that is
  now somewhere else entirely, via Strafe_IdealTurnPlane.

  The low pass goes with it.  ui_ideal_lp is a smoothed ramp target and
  ui_ideal_regime is what produced it; leaving them would drag the old plane's
  answer into the first frames after the load through HUD_SmoothIdeal, which is
  the same discontinuity the regime snap exists to prevent.  -1 is "none", so
  the next frame snaps rather than smooths.
*/
void() HUD_ClearRampHold =
{
	ui_ramp_norm   = '0 0 0';
	ui_ramp_time   = 0;
	ui_ideal_lp    = 0;
	ui_ideal_regime = -1;
};

/*
  WHICH ZERO the energy readout is measured from.

  A hand-set anchor wins in both modes -- you asked for a reference and a jump is
  not permission to replace it -- and `ui_anchor clear` is the way back out.
  Otherwise hud_energy_ref picks: 1 is Momentum's last-jump reference and always
  has an answer, 0 is the floor of the leg's start zone.

  Factored out in build 19 because the split list samples the SAME number, and
  two copies of this choice would drift the moment either was touched.  The
  caller decides what "there is no start zone" should look like; this only picks.
*/
float() HUD_EnergyRef =
{
	if (ui_anchor_manual)
		return ui_anchor_z;
	if (ui_cv_energyref)
		return ui_jump_z;
	return ui_anchor_z;
};

/*
===========================================================================
  BUILD 39 -- ONE CLOCK.

  Everything this HUD says about physics is built from two quantities: where
  your feet are, and how fast you are going.  Until build 39 they came from
  three different clocks, in two places, spelled the same way twice:

      vel = getstatf(STAT_FS_VELOCITY)          the SERVER's velocity, one
                                                snapshot old
      org = getproperty(VF_ORIGIN)              the renderer's PREDICTED eye
      org_z -= getstatf(STAT_VIEWHEIGHT)        ...minus the SERVER's eye height

  VF_ORIGIN is not the eye either, quite.  V_CalcRefdef (view.c:1677-1707)
  builds it as

      simorg_z + 1/16 + pv->viewheight + bob + pv->crouch

  and pv->viewheight is the PREDICTED eye height (cl_pred.c:1388, Patch 132b)
  while STAT_VIEWHEIGHT is the server's.  So the subtraction did not cancel.
  What it left behind, all of it landing in a readout that is z + |v|^2/2g:

    * up to 18 units through any crouch transition -- the hull delta, the thing
      Patch 132b exists because of.  On an `e` of 300 that is 6%, and it is the
      "-20 down" while a save-lock load is held.
    * pv->crouch, FTE's stair-step smoothing, up to 15 units and decaying at
      150 u/s -- a monotonic climb for the first fraction of a second of a jump.
    * a term linear in v_z from the org/vel time skew, which sweeps one way
      across a whole jump arc: the "starts at 45~ and counts up to 50".
    * the 1/16 lift, and bob if cl_bob is ever turned on.

  pmove_org and pmove_vel have none of that.  pmove_org IS the feet -- no eye
  height, no bob, no smoothing -- and CL_PredictMove writes it and pmove_vel
  from the same predicted state at the same simulation time (cl_pred.c:1394-1427,
  both from to.state or both lerped with one fraction).  A matched pair, by
  construction rather than by care.

  hud_predicted 0 puts the old three-clock path back, unchanged, so the two can
  be compared in the same session.  The fallback is automatic as well: untrusted
  CSQC gets these globals NULLed (pr_csqc.c:230-243), and an all-zero pmove_org
  is not a place a player can stand.
===========================================================================
*/
float ui_pred_warned;

vector() HUD_Feet =
{
	local vector ref;

	/*
	  Build 38's answer, computed first and unconditionally.  It is the fallback,
	  and it is also the only thing there is to check the new source AGAINST --
	  a silent fallback that fires on one map and not another is how a fix like
	  this becomes a mystery six builds later, so the debug panel gets both.

	  A ghost overrides VF_ORIGIN with the flying camera and Ghost_Frame captures
	  the body's own eye before it does, which is why this branch exists at all.
	  pmove_org is the body either way -- setproperty writes r_refdef.vieworg and
	  never pv->simorg -- so the comparison below is body against body.
	*/
	if (rec_gh_on)
		ref = rec_gh_bodyfeet;
	else
	{
		ref = getproperty(VF_ORIGIN);
		ref_z = ref_z - getstatf(STAT_VIEWHEIGHT);
	}

	ui_src_pred     = FALSE;
	ui_src_disagree = 0;

	if (!ui_cv_predicted)
		return ref;

	/*
	  An all-zero pmove_org is not a place a player can stand, and it is what
	  you get before the first prediction and from a csprogs the engine has
	  decided not to trust (pr_csqc.c:230-243, where these three are NULLed
	  alongside CSQC_UpdateView itself -- so in practice this HUD is not drawing
	  at all in that state, and the test is cheap insurance rather than a
	  reachable path).
	*/
	if (pmove_org == '0 0 0')
	{
		if (!ui_pred_warned)
		{
			ui_pred_warned = TRUE;
			dprint("hud: pmove_org is empty; falling back to VF_ORIGIN - STAT_VIEWHEIGHT\n");
		}
		return ref;
	}

	ui_src_pred     = TRUE;
	ui_src_disagree = vlen(pmove_org - ref);
	return pmove_org;
};

/*
  The matching half.  CALL HUD_Feet FIRST: this reads ui_src_pred rather than
  deciding for itself, and that is the whole point of the pair.  pmove_vel and
  STAT_FS_VELOCITY legitimately differ by a snapshot of prediction -- 45 units
  of it at 3000 u/s -- so there is no tolerance that could validate one against
  the other, and taking one source for the origin and the other for the velocity
  would put back exactly the skew this build exists to remove.  They are matched
  or neither.

  The save-lock substitution stays and has to.  The server writes '0 0 0' into
  .velocity every tick you are parked (SV_SaveLocHoldFrame) and the client
  predicts PM_NONE, so pmove_vel is a true zero for the same reason the stat is
  -- and STAT_FS_HOLDVEL is the only place the speed you are holding still
  exists.  Applied AFTER the choice, to whichever it was.
*/
vector() HUD_LiveVel =
{
	local vector vel;

	if (getstatf(STAT_FS_HOLD))
	{
		vel_x = getstatf(STAT_FS_HOLDVEL + 0);
		vel_y = getstatf(STAT_FS_HOLDVEL + 1);
		vel_z = getstatf(STAT_FS_HOLDVEL + 2);
		return vel;
	}

	if (ui_src_pred)
		return pmove_vel;

	vel_x = getstatf(STAT_FS_VELOCITY + 0);
	vel_y = getstatf(STAT_FS_VELOCITY + 1);
	vel_z = getstatf(STAT_FS_VELOCITY + 2);
	return vel;
};

/*
  BUILD 47: hud_veltrace <N> -- the per-RENDERED-FRAME predicted state.

  Third of its family, and written for the same reason as the other two:
  hud_wishtrace exists because a HUD row could not prove a claim about one frame
  in five, and hud_eyetrace because a row can say the answer is wrong but only a
  dump can say which term is.  This one is for the reported jitter -- "at 1400fps
  tap a direction key and wait, the speedometer flickers 0-4, at 60 it doesn't
  appear, moving the mouse stops it" -- where the whole question is what changes
  BETWEEN two rendered frames that share one command frame.

  So clientcommandframe is the first column and it is the point of the thing.
  The engine runs one extra EXTRAPOLATED partial command per rendered frame
  (cl_pred.c, the `if (simtime > to.time)` block) whose duration sawtooths across
  a send cycle, so consecutive frames on the SAME command frame can carry
  different amounts of extra simulation.  If the numbers move while that column
  does not, the movement is extrapolation and not input -- and the input half is
  already ruled out, since hud_wishtrace shows fore/side decaying to 0 within
  about four frames of a release rather than sticking.

  Self-clearing and NOT archived, exactly like hud_wishtrace: at 1400 fps an
  unbounded version writes a hundred thousand lines a minute.

  Deliberately reads through HUD_LiveVel and HUD_Feet rather than pmove_vel and
  pmove_org directly, so it reports what the READOUTS report -- including the
  save-lock hold substitution and the hud_predicted 0 fallback.  A trace that
  bypassed those would answer a question nobody asked.
*/
void() HUD_VelTrace =
{
	local float  n;
	local vector vel, org, eye;

	n = cvar("hud_veltrace");
	if (n <= 0)
		return;
	cvar_set("hud_veltrace", ftos(n - 1));

	vel = HUD_LiveVel();
	org = HUD_Feet();
	eye = getproperty(VF_ORIGIN);   // a call result is not swizzleable in place

	// Two prints rather than one: QC's sprintf takes at most eight parameters
	// INCLUDING the format string, and the horizontal pair and the vertical pair
	// are each worth full precision.
	print(sprintf("vel cmd %g: spd %.4f  vxy %.3f %.3f  oxy %.3f %.3f\n",
	              clientcommandframe, vlen([vel_x, vel_y, 0]),
	              vel_x, vel_y, org_x, org_y));
	print(sprintf("            vz %.3f  oz %.3f  eye %.3f  onground %g\n",
	              vel_z, org_z, eye_z,
	              (getstatf(STAT_FS_FLAGS) & FL_ONGROUND) ? 1 : 0));
};

/*
  Speed and energy RIGHT NOW, for the split list.  Build 19.

  Returned as a vector because QC has no out-parameters and no structures:
  x = the speedometer's speed (horizontal, which is what a surfer means by
  speed), y = the `e` readout's energy, and both are deliberately the numbers
  already on screen rather than fresh definitions -- a split row that disagreed
  with the crosshair would be worse than no split row.

  Reads its stats fresh rather than taking HUD_Draw's, so it does not care
  whether Timer_Draw runs before or after HUD_Draw in the frame.

  HONEST LAG: the server crosses the gate inside a physics tick and the client
  sees the stat on its next RENDERED frame, so this is up to one frame late --
  a few u/s at surf speeds, and effectively exact for the energy, which is
  conserved in flight.  The alternative is sending both from the server, and
  that cannot work for the energy: the reference above is client-side and moving.
*/
vector() HUD_SplitSample =
{
	local vector vel, org;
	local float gravity;

	/*
	  BUILD 39: THE SHARED PAIR, not a second copy of it.

	  Build 30 duplicated HUD_Draw's two substitutions here and said, in the
	  comment this replaces, that a copy which quietly stops matching its
	  original is how the contract gets broken by an edit somewhere else.  That
	  was exactly right and it is what happened -- both copies were wrong the
	  same way for the same reason, which is not the same thing as agreeing.
	  Both callers now go through HUD_Feet and HUD_LiveVel, so there is one
	  answer to "where am I" in this file and the drift is not possible.
	*/
	org = HUD_Feet();       // FIRST: it decides the source for both
	vel = HUD_LiveVel();

	gravity = serverkeyfloat("sv_gravity");
	if (gravity < 1) gravity = 800;

	return [vlen([vel_x, vel_y, 0]),
	        Strafe_Energy(org, vel, gravity) - HUD_EnergyRef(),
	        0];
};

/*
===========================================================================
  Panels
===========================================================================
*/
void(vector scr, vector vel, vector org) HUD_DrawSpeed =
{
	local float sp, sz, e, erel, veq, gravity, gain, ref, nozone;
	local float bw, bh, tw, esz;
	local vector p, bp;
	local string s;

	sp   = vlen([vel_x, vel_y, 0]);

	/*
	  THE COLOUR STILL COMES FROM THE RAW, PER-FRAME DELTA.  Build 31 latches and
	  quantises the number you READ, and deliberately not the number the colour
	  is computed from: HUD_GainColor is a continuous ramp, nobody has reported it
	  as a blur, and rounding its input to a step of 5 would make it jump between
	  three colours instead of sliding between them.
	*/
	gain = sp - ui_prev_speed;
	ui_prev_speed = sp;

	sz = 24 * ui_cv_scale;
	p  = [scr_x * ui_cv_speedpos_x, scr_y * ui_cv_speedpos_y, 0];
	bp = p;                     // the anchor, kept -- p walks down the panel

	if (ui_hl_tick)
		ui_hl_speed = sp;

	// Bebas for the one number you look at while moving.  The "+0.0" delta
	// and the peak are gone, but the delta still COLOURS the number -- that
	// was never the thing in the way, and it is how Momentum's own
	// speedometer reads too.
	Font_Set(ui_font_display);
	s  = sprintf("%d", rint(HUD_Round(ui_hl_speed)));
	bw = stringwidth(s, TRUE, [Font_Px(sz), Font_Px(sz)]);
	bh = sz;
	HUD_TextC(p, s, sz, HUD_GainColor(gain), 1);
	p_y = p_y + sz;

	if (ui_cv_energy)
	{
		gravity = serverkeyfloat("sv_gravity");
		if (gravity < 1) gravity = 800;

		/*
		  WHICH ZERO.  A hand-set anchor wins in both modes -- you asked for a
		  reference and a jump is not permission to replace it -- and `ui_anchor
		  clear` is the way back out.  Otherwise hud_energy_ref picks: 1 is
		  Momentum's last-jump reference and always has an answer, 0 is the
		  floor of the leg's start zone and says so when there isn't one.
		*/
		nozone = FALSE;
		ref = HUD_EnergyRef();
		if (!ui_anchor_manual && !ui_cv_energyref)
			nozone = (ui_anchor_zone < 0);

		e    = Strafe_Energy(org, vel, gravity);
		erel = e - ref;

		/*
		  THE READOUT IS THE ENERGY ITSELF, IN UNITS.

		  It used to print Strafe_EquivSpeed(erel), which is sqrt(2*g*erel) --
		  the exact inverse of the v^2/2g that built the number in the first
		  place.  On flat ground the height term is zero, so the two cancelled
		  and it printed your own speed straight back at you: 289 at a 289
		  prestrafe, every time.  It was indistinguishable from the speedometer
		  directly above it because it WAS the speedometer directly above it,
		  and only away from the anchor's height did the two ever differ.

		  Energy is a height -- see Strafe_Energy -- and Momentum reads it as
		  one, so the same prestrafe now says 52 in both games and a jump adds
		  its own height on top of whatever you were standing on.

		  The equivalent speed is still worth having: it is what that energy is
		  WORTH, which is the honest way to compare a gain against a speedometer.
		  So it is `hud_energy 2` rather than deleted.

		  Build 20: the board rows were the other reason to keep it, and they are
		  in ENERGY now by default (hud_seq_units).  At the shipped settings this
		  readout and that column finally share a unit and can be added.

		  Sign-carried, never clamped: below the start you ARE below the start,
		  and on a descending map that is where everyone finishes.
		*/
		// Build 31: latched and quantised like the speedometer above it, and out
		// of the same pair of knobs, so the two numbers in this panel never
		// disagree about when they last changed.  The RELATIVE energy is what is
		// held, not the absolute -- the anchor can move under it (a jump, a zone
		// crossing), and holding the wrong side of that subtraction would show a
		// stale offset from a reference that no longer exists.
		if (ui_hl_tick)
			ui_hl_e = erel;

		if (nozone)
			s = "-- no start zone";
		else if (ui_cv_energy >= 2)
		{
			veq = Strafe_EquivSpeed(ui_hl_e, gravity);
			s   = sprintf("e %d u/s", rint(HUD_Round(veq)));
		}
		else
			s = sprintf("e %d", rint(HUD_Round(ui_hl_e)));

		esz = 16 * ui_cv_scale;
		tw  = stringwidth(s, TRUE, [Font_Px(esz), Font_Px(esz)]);
		if (tw > bw) bw = tw;
		bh = bh + esz;

		HUD_TextC(p, s, esz,
		          nozone ? '0.5 0.5 0.5' : '0.75 0.85 1.00',
		          nozone ? 0.5 : 0.9);
	}
	Font_Reset();

	// Build 31: what this just covered, for the layout editor.  Centre-anchored
	// in x, top-anchored in y -- so the box hangs from bp and is centred on it.
	HUD_Rect("speed", [bp_x - bw * 0.5, bp_y, 0], [bw, bh, 0], bp);
};

/*
  The board panel -- now UNDER THE STRAFE BAR, not under the speedometer.

  It moved by request, and the move is right on its own terms: everything in
  this block is about a ramp, and so is the bar it now sits beneath, while the
  speedometer above answers "how fast am I" and has nothing to do with either.

  `y` comes from HUD_DrawStrafe rather than from hud_strafe_y plus a constant,
  because the panel above changes height -- the two rate cells appear and
  disappear, and so does the `best` line -- and a constant would make this block
  twitch every time the bar changed its mind.  Draw order matters: the strafe
  panel has to run FIRST to publish it.

  Rows: the segment gain, then what the board cost as a grade with the kept
  percentage, then contact, then leaving.  Every row keeps its slot whether or
  not it has anything in it, so nothing below shuffles when something above
  fades out.  The signed XYZ row is gone (build 6) -- board_dv's z is large and
  positive and is not a loss at all, it is the ramp handing you height for the
  speed it took, which is the opposite of what three numbers under "cost" read
  as.
*/
void(vector scr, float y) HUD_DrawBoard =
{
	local vector p, col, bp;
	local float sz, lh, a, la, ga, bx, by, bw, tw;
	local float gk, gd, gs, gu;     // build 34: the gain row's four fields, live or latched
	local string s;

	sz = 10 * ui_cv_scale;
	lh = sz + 3 * ui_cv_scale;

	/*
	  BUILD 31: A POSITION OF ITS OWN, OR THE STACK IT HAS ALWAYS HAD.

	  -1 on either axis means stacked -- the x of the strafe bar, and the y the
	  bar published this frame.  That is not the same as a constant offset from
	  hud_strafe_y and the difference is the reason `y` is a parameter at all:
	  the bar changes height as its rate cells and its `best` line come and go,
	  and a constant would make this block twitch every time it did.

	  Anything else is a plain screen fraction, like every other panel, and the
	  panel stops following the bar.  Both axes are tested together; see the
	  registration essay for why half-detached is not a state worth reaching.
	*/
	bx = cvar("hud_board_x");
	by = cvar("hud_board_y");
	if (bx < 0 || by < 0)
		p = [scr_x * ui_cv_strafepos_x, y, 0];
	else
		p = [scr_x * bx, scr_y * by, 0];
	bp = p;
	bw = 0;

	Font_Set(ui_font_ui);

	/*
	  What the last ramp, or the last air time, was worth.  See cl_board.qc:
	  this is an ENERGY difference, so gravity contributes exactly zero and the
	  number is what your hands added.  Printed with its duration because "+77"
	  over two seconds and "+77" over half a second are not the same ride.
	*/
	/*
	  BUILD 34: while a RAMP is open, this reads the ride you are on rather than
	  the one before it.

	  gain_* is set only by Board_SegmentEnd, so this line had the same wait the
	  column did -- and worse, during a ride it was showing the PREVIOUS segment's
	  finished figure, which is a number about a different piece of the map. The
	  live values come from the same seg_live_* the column's provisional rows use,
	  so the two readouts cannot disagree about a measurement they share; that is
	  the whole argument the hud_seq_units essay in default.cfg makes.

	  Full alpha rather than Board_Alpha's fade: a live number is not aging.
	*/
	gk = gain_kind;
	gd = gain_de;
	gs = gain_speed;
	gu = gain_dur;
	ga = Board_Alpha(gain_time, ui_cv_boardfade);
	if (ui_cv_seqlive)
	if (!rec_wt_on)
	if (seg_live_kind == SEG_RAMP)
	{
		gk = seg_live_kind;
		gd = seg_live_de;
		gs = seg_live_gain;
		gu = seg_live_dur;
		ga = 1;
	}

	if (ga > 0 && gk != SEG_NONE)
	{
		// Build 20: the same switch as the column, so the two never disagree
		// about what they are measuring.  The colour keys off the sign, which is
		// the same sign either way -- a gain in energy is a gain in u/s.
		if (seq_units)
			s = sprintf("%s  %+.0f e   %.1fs",
			            (gk == SEG_RAMP) ? "ramp" : "air",
			            gd, gu);
		else
			s = sprintf("%s  %+.0f u/s   %.1fs",
			            (gk == SEG_RAMP) ? "ramp" : "air",
			            gs, gu);


		tw = stringwidth(s, TRUE, [Font_Px(sz), Font_Px(sz)]);
		if (tw > bw) bw = tw;

		HUD_TextC(p, s, sz,
		          (gs >= 0) ? '0.55 0.95 0.55' : '1.00 0.55 0.20',
		          ga * 0.95);
	}
	p_y = p_y + lh;

	a = Board_Alpha(board_time, ui_cv_boardfade);
	if (a > 0)
	{
		col = Board_GradeColor(board_grade);

		s  = sprintf("%s  %.1f%% kept", Board_GradeName(board_grade), board_kept);
		tw = stringwidth(s, TRUE, [Font_Px(sz), Font_Px(sz)]);
		if (tw > bw) bw = tw;
		HUD_TextC(p, s, sz, col, a);
		p_y = p_y + lh;

		/*
		  The signed XYZ row is GONE, by request, and it was the right thing to
		  drop.  board_dv is the CHANGE the clip made to your velocity -- with
		  the normal oriented back at you, v' = v + into*n -- so its z term is
		  large and positive and is not a loss at all: it is the ramp handing
		  you height in exchange for the speed it took.  Three signed numbers
		  that mostly mean "the ramp worked" are noise beside the one scalar
		  that says what it cost.

		  board_dv is still COMPUTED (cl_board.qc) because it is one multiply
		  and the board maths reads better with the vector named; it simply is
		  not drawn.  Two rows here now, so the empty-state skip below is lh*2.
		*/
		/*
		  BUILD 25 -- THE TOUCHDOWN, IN THE COLUMN'S OWN UNIT.

		  "Report this energy on the middle vertical."  board_losse is
		  (v.n)^2 / 2g, world units of height, and it is exactly the magnitude of
		  the SEG_BOARD row the column now carries -- the same measurement, drawn
		  in the place you are already looking.  Switched on hud_seq_units like
		  every other energy readout on this HUD, so the panel and the row can
		  never disagree about what they are counting in.

		  SIGNED, and negative, unlike the u/s form beside it.  `cost 23` reads as
		  a magnitude and always has; the column's row says `-23 e` because it is
		  an energy DELTA and its sign is what makes the rows sum.  Printing the
		  same number two ways one line apart would be worse than either.

		  `contact` stays as it was: it is a speed, it is the number that says how
		  fast you arrived, and it has no energy form worth having.
		*/
		if (seq_units)
			s = sprintf("board %+d e   contact %d",
			            rint(0 - board_losse), rint(board_speedin_h));
		else
			s = sprintf("cost %d   contact %d",
			            rint(board_loss), rint(board_speedin_h));

		tw = stringwidth(s, TRUE, [Font_Px(sz), Font_Px(sz)]);
		if (tw > bw) bw = tw;
		HUD_TextC(p, s, sz, '0.8 0.8 0.8', a * 0.9);
		p_y = p_y + lh;
	}
	else
		p_y = p_y + lh * 2;

	la = Board_Alpha(leave_time, ui_cv_boardfade);
	if (la > 0)
		HUD_TextC(p, sprintf("leaving %d", rint(leave_speed)), sz, '0.85 0.90 1.00', la);
	p_y = p_y + lh;

	Font_Reset();

	/*
	  Build 31: the box, for the layout editor.

	  FLOORED AT 120*scale, and that is not cosmetic.  Every row here is on a
	  three-second fade, so a panel nobody has boarded in a while draws NOTHING
	  and would publish a zero-width box -- which HUD_Rect refuses, and the editor
	  would then have to fall back to a guess.  The four row slots are always
	  reserved (the else branch above steps p_y past them whether or not they were
	  filled), so the HEIGHT is honest at any fade; only the width goes away, and
	  120 is about what "ramp  +77 e   1.2s" measures.
	*/
	if (bw < 120 * ui_cv_scale)
		bw = 120 * ui_cv_scale;
	HUD_Rect("board", [bp_x - bw * 0.5, bp_y, 0], [bw, p_y - bp_y, 0], bp);
};

/*
  The sequence column, floating to the left of the crosshair.

  Placed relative to the SCREEN CENTRE rather than to an edge, because that is
  what "beside the crosshair" means on any aspect ratio -- an edge-anchored
  panel drifts across the screen as the window changes shape, and this one is
  meant to be readable without looking away from where you are going.

  Newest at the BOTTOM.  The column grows downward toward the crosshair, so the
  row that just landed is always in the same place relative to your eye and the
  history scrolls up away from it.  Reading order matches the order it happened.
*/
vector(float kind, float launch) HUD_SeqColor =
{
	if (launch)          return '0.62 1.00 0.62';   // the launch, light green
	/*
	  BUILD 25 -- the touchdown, orange.

	  Deliberately NOT a shade of the ramp's grey, which was the first thing to
	  try and is wrong: the whole point of splitting the row is that the landing
	  and the ride are two different things to practise, and a colour that says
	  "this is a sort of ramp" would undo that at a glance.  Orange is the same
	  hue the board panel's own cost readout and the negative gain colour already
	  use for "this took something off you", so the column and the panel under the
	  strafe bar say it the same way.
	*/
	if (kind == SEG_BOARD) return '1.00 0.62 0.34';
	if (kind == SEG_RAMP) return '0.72 0.74 0.76';  // on a ramp, grey
	return '1.00 0.96 0.62';                        // in the air, light yellow
};

void(vector scr) HUD_DrawSeq =
{
	local float i, sz, lh, a, rows, first, pct, pw, bw, bt;
	local float nlive, liveb, la;
	local vector p, col, bp;
	local string s, ps;

	/*
	  BUILD 34 -- THE OPEN SEGMENT GETS PROVISIONAL ROWS.

	      "when you board, present the board energy display on the energy loss/gain
	       display as soon as you make contact and it's recorded, for some reason
	       it waits for you to leave the ramp"

	  Two rows, drawn under the committed ones, from cl_board.qc's seg_live_*:

	    board   FROZEN.  seg_bd_de is final on the contact frame -- it is
	            -(v.n)^2/2g, the bite the plane took -- so this row never moves
	            once it appears.  Only while the touchdown is still held, which is
	            exactly while its committed twin has not been pushed yet.
	    ramp    LIVE.  The ride's running total, ticking up as you carry.

	  NOTHING IS PUSHED INTO THE RING.  The essay on seg_bd_pend in cl_board.qc is
	  why -- a board row committed at the boundary would sit between two air rows
	  and stop them merging, and a ramp too short to become a row would leave junk
	  behind.  All of that still holds, and none of it is about drawing.  When the
	  segment closes these two vanish and the identical committed pair appears in
	  their place; the numbers are the same numbers, computed by the same lines.

	  RAMP ONLY.  Air already reads its whole story off the speedometer, and a
	  permanently-present live air row would make the column never sit still.
	  "As soon as you make contact" is the thing that was asked for.
	*/
	nlive = 0;
	liveb = FALSE;
	if (ui_cv_seqlive)
	if (!rec_wt_on)                  // a replay's column is the ring, and only the ring
	if (seg_live_kind == SEG_RAMP)
	{
		nlive = 1;
		if (seg_bd_pend)
		if (seq_board)              // hud_seq_board 0 has no board rows at all, live or not
		{
			liveb = TRUE;
			nlive = 2;
		}
	}

	// The early-out has to survive a live row, or the first ramp of a run -- the
	// one case where the ring really is empty -- would show nothing at all.
	if (seq_n <= 0 && !nlive)
		return;

	// The gentle exit a new run gets.  Solid until it starts, then linear to
	// nothing over SEQ_FADE -- the list does not vanish under you the instant
	// you cross the line.
	a = 1;
	if (seq_fadeat > 0)
	{
		a = 1 - (cltime - seq_fadeat) / SEQ_FADE;
		if (a <= 0)
			return;
	}

	/*
	  BUILD 21: MONOSPACED -- AND Font_Set MOVED ABOVE Font_Px, WHICH IS A FIX.

	  Font_Px snaps against whichever face is CURRENTLY selected; it has no other
	  way to know which ladder to consult.  This function asked for its size here
	  and did not call Font_Set until just before the loop, ~25 lines below, so
	  the snap ran while ui_font_cur was still FONT_DEFAULT from the previous
	  block's Font_Reset -- which matches no ladder, so Font_Px handed back the
	  request unchanged.  At hud_scale 2 that is 18 px asked of a face baked at
	  8/12/16/20/...: ChooseFont picks 16 or 20 and RESAMPLES to 18.  So this
	  column has been the one visibly soft block on the HUD, for exactly the
	  reason sh_font.qc's ladder essay describes, and Timer_Draw already carries
	  a comment warning about this ordering.  Selecting the face first is the
	  whole fix.

	  8 rather than 9 because the mono ladder steps in twos: 9 * 2 would snap to
	  a real 18 px here, and this face is wider per character than Roboto, so
	  holding the requested size would have widened every row.  16 px keeps the
	  block within a few pixels of the width it has always had while making it
	  exact, and it is the same rung Timer_DrawSplits' rows sit near -- the two
	  read as a pair now that they no longer overlap.
	*/
	Font_Set(ui_font_mono);
	sz = Font_Px(8 * ui_cv_scale);
	lh = sz + 2 * ui_cv_scale;

	rows = cvar("hud_seq_rows");
	if (rows < 1) rows = 10;
	if (rows > seq_n) rows = seq_n;
	first = seq_n - rows;

	/*
	  BUILD 13: centred vertically, and moved well clear of the strafe bar.

	  It used to hang at 0.445 of the width with its last row on 0.47, which put
	  it right on top of the strafe meter and pinned the block's BOTTOM rather
	  than its middle -- so the column crept upward as rows accumulated.

	  hud_seq_x is an offset from the screen centre, so -0.25 lands it a quarter
	  of the way across: halfway between the middle and the left edge, which is
	  the gap between the strafe bar and the split list.  Still right-aligned, so
	  the numbers stack against a clean edge facing the crosshair.
	*/
	// Build 34: the live rows are part of the block, so they are part of what it
	// is centred on -- otherwise the whole column would jump half a row up and
	// back down on every ramp, which is a worse fidget than the one being fixed.
	p = [scr_x * (0.5 + cvar("hud_seq_x")),
	     scr_y * cvar("hud_seq_y") - (rows + nlive) * lh * 0.5, 0];

	// The anchor the two cvars encode: the column's RIGHT edge, and the vertical
	// CENTRE of the block -- not the top-left p walks from.  Kept before the loop
	// moves p_y.  See the layout registry essay for why the editor is handed this
	// rather than left to invert the box.
	bp = [p_x, scr_y * cvar("hud_seq_y"), 0];
	bt = p_y;
	bw = 0;

	pct = cvar("hud_seq_pct");

	// The face is already selected -- see the note above sz; selecting it here
	// was what made the snap above run against the wrong ladder.
	for (i = first; i < seq_n; i = i + 1)
	{
		col = HUD_SeqColor(seq_kind[i], seq_launch[i]);
		/*
		  Build 20.  `e` is world units of height, the same unit as the `e`
		  readout by the crosshair and as the numerator of the % to the right --
		  so the row is internally consistent for the first time.  u/s is one
		  cvar away and is the build 19 string unchanged.
		*/
		if (seq_units)
			s = sprintf("%+.0f e  %.2fs", seq_de[i], seq_dur[i]);
		else
			s = sprintf("%+.0f u/s  %.2fs", seq_gain[i], seq_dur[i]);

		/*
		  BUILD 18 -- how much of the available gain that airtime took.

		  DRAWN AS A SECOND STRING IN ITS OWN COLOUR, not appended to the one
		  above, because the two answer different questions and colouring the
		  whole row by the percentage would lose the launch/ramp/air distinction
		  that the row colour already carries.  So the row keeps saying WHAT the
		  segment was and the suffix says HOW WELL it went.

		  Only air rows have one (seq_pct is -1 on a ramp): the ramp optimum has
		  no closed form -- wishdir is horizontal so the perpendicular heading is
		  generally unreachable on a plane -- and Strafe_PlaneBest has to search
		  for it.  A number that is exact is worth more here than one that is
		  available everywhere.

		  Right-aligned like the rest, so the suffix hangs to the RIGHT of the
		  main string: measure it and shift the row left by its width, or the
		  two would overlap on the same anchor.
		*/
		if (pct && seq_pct[i] >= 0)
		{
			ps = sprintf("  %.0f%%", seq_pct[i]);
			pw = stringwidth(ps, TRUE, [sz, sz]);
			HUD_TextR([p_x, p_y], ps, sz,
			          HUD_QualityColor(seq_pct[i] * 0.01), a * 0.95);
			HUD_TextR([p_x - pw, p_y], s, sz, col, a * 0.95);
		}
		else
		{
			pw = 0;
			HUD_TextR([p_x, p_y], s, sz, col, a * 0.95);
		}

		pw = pw + stringwidth(s, TRUE, [sz, sz]);
		if (pw > bw) bw = pw;

		p_y = p_y + lh;
	}

	/*
	  BUILD 34: the provisional pair, under the committed rows.

	  Drawn in the same colours HUD_SeqColor gives their committed twins -- orange
	  for the board, grey for the ramp -- at a lower alpha.  Not a different
	  colour: the row has to be recognisable as the one it is about to become, or
	  the swap at segment end reads as two separate things happening rather than
	  one thing settling.  Alpha is the only thing that says "not final yet".

	  No percentage column.  seq_pct is an AIR-row figure and these are ramp rows,
	  so there was never one to show; the ramp optimum has no closed form (see the
	  hud_seq_pct essay in default.cfg).
	*/
	if (nlive)
	{
		la = a * 0.55;

		if (liveb)
		{
			s = seq_units ? sprintf("%+.0f e  board", seg_bd_de)
			              : sprintf("%+.0f u/s  board", seg_live_bdgain);
			HUD_TextR([p_x, p_y], s, sz, HUD_SeqColor(SEG_BOARD, FALSE), la);
			pw = stringwidth(s, TRUE, [sz, sz]);
			if (pw > bw) bw = pw;
			p_y = p_y + lh;
		}

		s = seq_units ? sprintf("%+.0f e  %.2fs", seg_live_de, seg_live_dur)
		              : sprintf("%+.0f u/s  %.2fs", seg_live_gain, seg_live_dur);
		HUD_TextR([p_x, p_y], s, sz, HUD_SeqColor(seg_live_kind, FALSE), la);
		pw = stringwidth(s, TRUE, [sz, sz]);
		if (pw > bw) bw = pw;
		p_y = p_y + lh;
	}

	Font_Reset();

	// Build 31: right-aligned, so the box hangs to the LEFT of the anchor's x.
	HUD_Rect("seq", [bp_x - bw, bt, 0], [bw, p_y - bt, 0], bp);
};

/*
===========================================================================
  BUILD 34 -- WHAT MAP IS THIS.  Top right, four lines.

      "The top right of the screen of the HUD, can you display game name, (next
       line) map name, (next line) map tier, and stage count or linear."

  WHERE EACH LINE COMES FROM, because they come from four different places and
  three of them have a wrong answer that looks right:

    game    the literal, from default.fmf's GAME "FTESurf".  Not `hostname`,
            which is the SERVER's name and is whatever the user called it.

    map     serverkey("map"), the short name.  NOT the `mapname` global -- in
            CSQC that is the world MODEL, "maps/surf_kitsune.bsp", slashes and
            extension included.  cl_replay.qc:131 has the same warning written
            out at length; this is the third reader to need it.

    tier    serverinfo, published by the engine at map load (Patch 227).  It
            lives in data/mapmeta.txt, which until now only the MAP BROWSER read
            -- and the browser is menu.dat while this is csprogs.dat, two
            separate progs with no way to hand a value between them.  Reading the
            file again from here would have been a second parser of a format that
            already has two; asking the server means it is also right in a demo
            and right for a client whose own mapmeta.txt does not match the
            server's, which is the case that matters once sessions are P2P.

    stages  Zone_TrackSegs(0) -- the END zone's segment index IS the count, and
            sh_zones.qc:194 is emphatic about there being exactly one speller of
            that rule after it was reimplemented wrongly twice in one build.
            The zone file describes THIS map as loaded, so it outranks mapmeta;
            mapmeta answers only when there is no zone file at all.

  A TIER OF 0 IS NOT A TIER.  There is no tier 0 and '-' in the file means
  unknown, so 649 of the installed maps genuinely have no answer -- they are CS:S
  community maps Momentum has never indexed.  Those draw "--".  Writing "Tier 0"
  would be asserting something the data does not say, which is the same rule the
  map browser follows (m_main.qc:2159).

  The provenance suffix comes with it: a submitter's SUGGESTION and an INHERITED
  tier are estimates, and 1020 and 76 rows respectively are exactly that.
===========================================================================
*/
string() HUD_MapTier =
{
	local float t;
	local string src;

	t = serverkeyfloat("maptier");
	if (t <= 0)
		return "Tier --";

	src = serverkey("maptiersrc");
	if (src == "sugg")              // an estimate from an unranked submission
		return sprintf("Tier %g?", t);
	if (src == "alias")             // inherited from the same map without its port suffix
		return sprintf("Tier %g~", t);
	return sprintf("Tier %g", t);   // rank, over, or a file written before the column
};

string() HUD_MapStages =
{
	local float segs;

	// The zone file first: it describes the map that is actually loaded.
	if (zone_count > 0)
	{
		segs = Zone_TrackSegs(0);
		if (segs > 1)
			return sprintf("%g stages", segs);
		return "linear";
	}

	// No zone file.  mapmeta's own columns, which are '-' (0) when unknown -- and
	// unknown has to stay silent rather than claim the map is linear.
	segs = serverkeyfloat("mapstages");
	if (segs > 1)
		return sprintf("%g stages", segs);
	if (serverkeyfloat("maplinear") == 1)
		return "linear";
	return "";
};

void(vector scr) HUD_DrawMapInfo =
{
	local vector p, bp;
	local float sz, tsz, lh, bw, bt, tw;
	local string s;

	if (serverkey("map") == "")
		return;                     // no map: nothing here is answerable

	Font_Set(ui_font_ui);
	tsz = Font_Px(10 * ui_cv_scale);
	sz  = Font_Px(8 * ui_cv_scale);
	lh  = sz + 3 * ui_cv_scale;

	// Right-aligned, so the block stacks against the screen edge rather than
	// ragged-right off a left margin.  x is the RIGHT edge, y the top.
	p  = [scr_x * ui_cv_mappos_x, scr_y * ui_cv_mappos_y, 0];
	bp = p;
	bt = p_y;
	bw = 0;

	s = "FTESurf";
	tw = stringwidth(s, TRUE, [tsz, tsz]);  if (tw > bw) bw = tw;
	HUD_TextR(p, s, 10 * ui_cv_scale, '0.88 0.92 0.98', 0.95);
	p_y = p_y + tsz + 3 * ui_cv_scale;

	s = serverkey("map");
	tw = stringwidth(s, TRUE, [sz, sz]);    if (tw > bw) bw = tw;
	HUD_TextR(p, s, 8 * ui_cv_scale, '0.70 0.75 0.84', 0.95);
	p_y = p_y + lh;

	s = HUD_MapTier();
	tw = stringwidth(s, TRUE, [sz, sz]);    if (tw > bw) bw = tw;
	HUD_TextR(p, s, 8 * ui_cv_scale, '0.55 0.70 0.90', 0.95);
	p_y = p_y + lh;

	s = HUD_MapStages();
	if (s != "")
	{
		tw = stringwidth(s, TRUE, [sz, sz]); if (tw > bw) bw = tw;
		HUD_TextR(p, s, 8 * ui_cv_scale, '0.55 0.60 0.68', 0.95);
		p_y = p_y + lh;
	}

	Font_Reset();

	// Right-aligned and top-anchored, so the box hangs LEFT of the anchor's x and
	// DOWN from its y -- the HEA_RT convention cl_hudedit.qc gained for this.
	HUD_Rect("mapinfo", [bp_x - bw, bt, 0], [bw, p_y - bt, 0], bp);
};

/*
  "YOUR RUNS WILL NOT SUBMIT", said where it can actually be seen.

  The submission rule is "no input journal, no rank" -- a run is only accepted
  with its .hid recording attached.  That rule is enforced at submission, which
  means the player finds out at the END of a run that the last however-many
  minutes were never going to count.  This is the same fact, delivered before
  the run instead of after it.

  NOT DISMISSIBLE AND NOT BEHIND A CVAR, deliberately.  It says a thing the
  player needs in order to not waste their time, and the two states it reports
  are both states the player themselves chose; a warning you can turn off is one
  the person who most needs it has already turned off.

  WHY THE TEST IS REBUILT FROM CVARS HERE rather than calling Rec_HidOK.
  cl_hud.qc compiles BEFORE cl_replay.qc (cl_progs.src, lines 47 and 55), so
  neither Rec_HidOK nor rec_rp_consent is in scope in this file, and QC has no
  forward declaration.  Declaring a global here for cl_replay.qc to fill is the
  usual way out of that (see rec_sb_open) and is NOT used, because it would mean
  editing a file another session currently has open.

  AND IT MUST READ BOTH SOURCES, WHICH THE FIRST VERSION OF THIS DID NOT.
  Reading only cvar("rec_terms") looked safe -- m_lobby.qc:292 gates the lobby
  list on exactly that -- and it is wrong here.  cl_replay.qc:252-263 records
  why: a headless launch that execs a config containing `map` reaches a loaded
  map with rec_terms still UNREGISTERED, so the cvar reads 0 while the player
  has in fact accepted.  That is why Rec_ConsentRead exists at all.  Measured:
  data/consent.txt on this machine says `version 3` and the banner still fired.

  A quiet gate can survive that (a hidden lobby row is a feature that does not
  work); a banner across the top of the screen cannot, because it is an
  ACCUSATION -- it tells a player who did accept that they did not.  So the test
  is the same OR that Rec_HidOK uses: the disk record, published into
  ui_consent_ver below, or the cvar, whichever is current.
*/
float ui_consent_ver;   // set by cl_replay.qc's Rec_Init from data/consent.txt.
                        // Declared HERE because cl_hud.qc compiles before
                        // cl_replay.qc (cl_progs.src 47 vs 55) and QC has no
                        // forward declaration -- the same arrangement rec_sb_open
                        // has for cl_watch.qc.  Zero until the first CSQC_Init,
                        // which is long before any map is drawn.

void(vector scr) HUD_DrawSubmitWarn =
{
	local string why, fix;
	local float tsz;
	local vector p;

	if (rec_wt_on)
		return;                     // a replay is not a run being set
	if (serverkey("map") == "")
		return;                     // no map: nothing here is answerable

	if (!cvar("rec_hid"))
	{
		why = "INPUT RECORDING IS OFF - RUNS WILL NOT SUBMIT";
		fix = "rec_hid 1 to record.  A run with no input journal cannot be ranked.";
	}
	else if (ui_consent_ver < FS_TERMS_ONLINE && cvar("rec_terms") < FS_TERMS_ONLINE)
	{
		why = "TERMS NOT ACCEPTED - RUNS WILL NOT SUBMIT";
		fix = "Accept them from the main menu to rank.  Play stays unranked until you do.";
	}
	else
		return;

	Font_Set(ui_font_ui);
	tsz = Font_Px(9 * ui_cv_scale);

	// Centred, top-anchored.  Not registered with HUD_Rect: it is not a panel
	// the layout editor should let you drag off screen.
	p = [scr_x * 0.5, 6 * ui_cv_scale, 0];
	HUD_TextC(p, why, 9 * ui_cv_scale, '1.00 0.58 0.22', 0.95);
	p_y = p_y + tsz + 2 * ui_cv_scale;
	HUD_TextC(p, fix, 7 * ui_cv_scale, '0.78 0.80 0.86', 0.85);

	Font_Reset();
};

/*
  WHICH PLANE THE RAMP MATHS SHOULD BE EVALUATED ON.

  Not run_groundnorm.  That is QC's guess: PlayerPostThink traces one tick
  FORWARD ALONG VELOCITY and reports whatever the swept box meets first
  (sv_player.qc) -- a different question from "what did the move actually clip
  against", and it answers '0 0 0' whenever the sweep misses.  Every miss
  dropped HUD_DrawStrafe back to the FLAT ideal, which sh_strafe.qc's own
  measurements put at 1.8x to 6x the plane ideal.  So the target jumped between
  two very different numbers frame to frame and the grade colour went with it.
  That is the whole of "very colourful when strafing on a ramp".

  In preference order: the plane THIS tick clipped (STAT_FS_RAMPNORM, engine
  Patch 137), then the last board entry plane (STAT_FS_BOARDNORM, latched on
  entry so it goes stale down a curved ramp), then the last good answer for
  RAMPHOLD seconds -- so a one-tick gap in a long ride does not flip the regime.

  ORIENTED back at the player, dot(vel, n) <= 0, before it is returned.
  sh_strafe.qc's plane formulas are signed in wn and say plainly that an
  unoriented normal gives a confidently wrong answer rather than a slightly
  wrong one; cl_board.qc has always oriented its own, and the strafe panel never
  did -- it tested fabs(nz) in the gate and then handed the maths the signed
  value.  If the engine's traces already guarantee the orientation this costs
  one dot product and changes nothing, which is the right way round for a
  guarantee nobody has written down.
*/
#define RAMPHOLD 0.25

vector(vector vel) HUD_RampNormal =
{
	local vector n;
	local float riding, now;

	/*
	  BUILD 24.  During a replay the two stats come from the .rec instead: bit 16
	  of the flags column is the ramp contact and the sample's own plane is the
	  normal, which is run_rampnormal when that bit is set (SV_RecNormal).  So the
	  first preference below is the one the file carries and the BOARDNORM
	  fallback has nothing to fall back to -- correctly, because the file already
	  resolved that choice at the moment it had both.

	  The hold below runs on board_now rather than cltime for the same reason
	  Board_Alpha does: at 4x a quarter-second hold would be sixty milliseconds of
	  run, and a one-tick gap in a long ride would flip the regime after all.
	*/
	riding = rec_wt_on ? rec_wt_rc : getstatf(STAT_FS_RAMPCONTACT);
	now    = board_now;

	/*
	  BUILD 25 -- the same held answer Board_Frame's segment kind uses.

	  This function has held its PLANE for RAMPHOLD seconds since build 21 and
	  nothing held the CONTACT, so the two could disagree: the plane said "the
	  ramp is still there" while the segment machine said "you left it", within
	  one frame of each other, several times a second.  Board_RampHold is the one
	  answer, gated at the engine's own PMSRC_BOARD_AIRGATE -- see its essay.

	  Calling it here as well as in Board_Frame is safe and is why it was written
	  to be idempotent: same frame, same board_now, same branch.  During a replay
	  Board_Frame does not run and this is the only caller.
	*/
	riding = Board_RampHold(riding, now);

	ui_ramp_riding = riding;
	ui_ramp_why    = RW_FREEAIR;

	if (riding)
	{
		if (rec_wt_on)
			n = rec_wt_gnorm;
		else
		{
			n_x = getstatf(STAT_FS_RAMPNORM + 0);
			n_y = getstatf(STAT_FS_RAMPNORM + 1);
			n_z = getstatf(STAT_FS_RAMPNORM + 2);

			if (n == '0 0 0')
			{
				n_x = getstatf(STAT_FS_BOARDNORM + 0);
				n_y = getstatf(STAT_FS_BOARDNORM + 1);
				n_z = getstatf(STAT_FS_BOARDNORM + 2);
			}
		}

		ui_ramp_why = (n == '0 0 0') ? RW_NOPLANE : RW_FRESH;

		if (n != '0 0 0')
		{
			/*
			  BUILD 39 -- ORIENT BY THE PLANE, NOT BY THE VELOCITY, AND THIS IS
			  THE MOST LIKELY ANSWER TO "THE TARGET IS WRONG ON RAMPS".

			  The essay above got the risk exactly backwards.  It supposed that
			  if the engine already guaranteed the orientation, this dot product
			  "costs one dot product and changes nothing".  It changes plenty.

			  cl_board.qc:584 uses the identical idiom and is CORRECT there,
			  because it orients against vin -- the PRE-clip velocity, for which
			  dot(vin, n) <= 0 is guaranteed by the fact that the trace hit the
			  plane at all.  This function is handed the POST-clip, post-
			  FinishGravity velocity, where nothing of the kind is guaranteed:
			  dot(vel, n) > 0 means "rising away from the face", which is a ramp
			  exit at the lip, or any frame in AirAccelerate that has pushed you
			  off the plane -- both extremely ordinary on a surf ramp.

			  The flip then stores a normal with n_z < 0.  The gate in
			  HUD_DrawStrafe wants nz in [0.05, PM_STANDABLE], a negative nz
			  fails it, and the panel substitutes the flat-air target -- for the
			  whole of RAMPHOLD, a quarter of a second, because the inverted
			  value is what the hold hands back afterwards.

			  The engine's own band is on fabs(nz) (pm_source.c:1132), which is
			  what admits a down-wound displacement triangle in the first place,
			  and a down-wound triangle is the ONLY thing the flip was ever
			  needed for.  So test the geometry, which cannot be transiently
			  wrong, instead of the kinematics, which can.

			  hud_strafe_orient 0 restores the velocity test; RW_FLIPPED is
			  published either way, so the debug row says how often it fires and
			  the question is settled by a ride rather than by this comment.
			*/
			if (!cvar_string("hud_strafe_orient") || cvar("hud_strafe_orient"))
			{
				if (n_z < 0)
				{
					n = '0 0 0' - n;
					ui_ramp_why = RW_FLIPPED;
				}
			}
			else if (vel * n > 0)       // vector*vector is dot
			{
				n = '0 0 0' - n;
				ui_ramp_why = RW_FLIPPED;
			}

			ui_ramp_norm = n;
			ui_ramp_time = now;
		}
	}

	// The clock going backwards is a map change, or a backwards scrub; the anchor
	// reset clears the rest.
	if (ui_ramp_time > 0 && now >= ui_ramp_time && now - ui_ramp_time <= RAMPHOLD)
	{
		// Build 39: a plane from an earlier frame is HELD, not FRESH, and the
		// difference is worth seeing -- a target computed off a quarter-second-old
		// plane is a different claim from one computed off this frame's.
		if (ui_ramp_why != RW_FRESH && ui_ramp_why != RW_FLIPPED)
			ui_ramp_why = RW_HELD;
		return ui_ramp_norm;
	}
	return '0 0 0';
};

/*
  Low-pass the TARGET with the same time constant as the measurement.

  ui_turnrate is a window average over hud_strafe_smooth and `ideal` was
  recomputed from scratch every rendered frame, so the error being drawn was a
  smoothed number minus an unsmoothed one and carried all of the second one's
  noise.  A regime change (air <-> ramp <-> ground) is a discontinuity rather
  than noise, so it snaps instead of blending -- otherwise the first quarter
  second of every ramp would be graded against a flat-air target.
*/
float(float want, float regime, float dt) HUD_SmoothIdeal =
{
	local float a;

	if (regime != ui_ideal_regime || want <= 0.001 || ui_ideal_lp <= 0.001 || dt <= 0)
	{
		ui_ideal_regime = regime;
		ui_ideal_lp     = want;
		return want;
	}

	// Exponential with time constant hud_strafe_smooth.  Clamped so a hitch
	// cannot overshoot past the target and ring.
	a = dt / ui_cv_smooth;
	if (a > 1) a = 1;
	ui_ideal_lp = ui_ideal_lp + (want - ui_ideal_lp) * a;
	return ui_ideal_lp;
};

/*
  BUILD 40: WHY THE PLANE MATHS COULD NOT RUN, ASKED IN A USEFUL ORDER.

  The old chain asked about the plane once (RW_NOPLANE), about the strafe key
  second, and about the BAND -- the gate that actually rejects most of them --
  not at all.  So any frame with both an empty wishdir and an unusable plane
  reported "no strafe key", and with the wishdir strobing at the send rate (see
  HUD_WishDir) that was one frame in five.  RW_FLIPPED, which this file calls
  the strongest remaining suspect for the original ramp report, could never
  reach the screen at all: it was always shadowed by the key string.

  So the plane is asked about FIRST -- a bad plane is a bad plane whether or
  not you are also pressing something -- and the key case is split into the
  three genuinely different things an empty wishdir means, read off the
  keyboard rather than off the wish vector, because the wish vector is exactly
  what is missing:

  * both strafe keys held AND they cancelled.  CL_BaseMove computes sidemove as
    right MINUS left (cl_input.c:1479), so two keys that are both down are
    exactly zero.  Whether they ARE both down depends on cl_iDrive, which
    defaults to 1 and which nothing in default.cfg overrides: with it on,
    KeyDown_Scan auto-releases the opposing key (cl_input.c:206-212) and the
    later press simply wins, so this case does not arise and the widget keeps
    a real target.  MEASURED, not assumed -- hud_wishtrace over A+D held
    together reads 0/450 on the shipped config, and would read 0/0 at
    cl_iDrive 0.  So this string is reachable only with iDrive off, which is
    the configuration where the reading is genuinely undefined.
  * only the turn keys held.  +left/+right have no usercmd movement component
    at all: they feed CL_AdjustAngles and reach sidemove only under +strafe
    (cl_input.c:1480-1481), which nothing in default.cfg binds.  default.cfg
    puts them on q/e, right beside the strafe keys, so calling them strafe
    keys is a fair mistake to make and worth answering precisely.
  * nothing held, which is the only case the old string was ever right about.

  RW_FLIPPED is reported as a qualifier on the band rather than as a cause,
  because the flip is a CORRECTION -- HUD_RampNormal inverts the plane and then
  uses it.  Reaching here with it set means the flipped plane failed the band,
  which is a different sentence from "the flip broke it", and only measurement
  can say which.
*/
string(vector wishdir, float nz, vector rnorm) HUD_StrafeWhy =
{
	if (ui_ramp_why == RW_NOPLANE)
		return "ramp: no plane";
	if (rnorm == '0 0 0')
		return "ramp: no plane held";
	if (nz < 0.05 || nz > PM_STANDABLE)
	{
		if (ui_ramp_why == RW_FLIPPED)
			return sprintf("ramp: nz %.2f flipped", nz);
		return sprintf("ramp: nz %.2f out of band", nz);
	}

	if (wishdir == '0 0 0')
	{
		if (Keys_Held(FSK_LEFT) && Keys_Held(FSK_RIGHT))
			return "strafe keys cancel";
		if (Keys_Held(FSK_TLEFT) || Keys_Held(FSK_TRIGHT))
			return "turn keys do not strafe";
		return "no strafe key held";
	}

	return "ramp: no target";
};

/*
  The strafe bar, above the crosshair.

  ITS CENTRE IS THE IDEAL RATE, NOT ZERO.  The axis unit is hud_strafe_band,
  so full deflection is that fraction off the ideal.  The fill runs the way
  you are turning: reaching the centre is right, past it is too fast, short
  of it is too slow.  That is the same in both mirror images, which is what
  makes it readable without thinking about which way you are facing.

  It refuses to answer on the ground, and refuses when the wishspeed cap
  does not bind -- in that regime the gain is pinned by the acceleration
  rather than by where you are pointing, so a turn rate grades the server
  and not the player.
*/
void(vector scr, float speed, float onground, vector gnorm, vector wishdir,
     vector vel, float dt) HUD_DrawStrafe =
{
	local float tick, airaccel, accel, maxspeed, aircap, gravity, fric, wishspeed;
	local float gfric, stopspeed, vf, best, havebest;
	local float gain, ideal, q, cscale, frac, err, nz, wn, regime;
	local float w, h, bx, by, fillfrom, fillto, t, ty;
	local vector p, col, rnorm;
	local string msg;

	p = [scr_x * ui_cv_strafepos_x, scr_y * ui_cv_strafepos_y, 0];
	w = 260 * ui_cv_scale;
	h = 6 * ui_cv_scale;
	bx = p_x - w * 0.5;
	by = p_y;

	// The SERVER's tick, not the compile-time default.  This read PM_TICK, so
	// every number on the strafe bar silently assumed 0.015 -- right on this
	// install and wrong on any server running a different pm_ticrate, where the
	// bar would grade a correct strafe as a miss.  cl_timer.qc has always read
	// the serverinfo for the same value; these two now agree.
	tick      = serverkeyfloat("pm_ticrate");      if (tick      <= 0) tick      = PM_TICK;
	airaccel  = serverkeyfloat("sv_airaccelerate");
	accel     = serverkeyfloat("sv_accelerate");   if (accel     <= 0) accel     = 5;
	maxspeed  = serverkeyfloat("sv_maxspeed");     if (maxspeed  <= 0) maxspeed  = PM_RUN_SPEED;
	aircap    = serverkeyfloat("pm_maxairspeed");  if (aircap    <= 0) aircap    = 30;
	gravity   = serverkeyfloat("sv_gravity");      if (gravity   <  1) gravity   = 800;
	gfric     = serverkeyfloat("sv_friction");     if (gfric     <  0) gfric     = 4;
	stopspeed = serverkeyfloat("sv_stopspeed");    if (stopspeed <  0) stopspeed = 75;

	/*
	  DEADSTRAFE -- surfacefriction, which this used to hardcode to 1.

	  The rule is real: PMSrc_CategorizePosition quarters surfacefriction while
	  you are airborne AND RISING, and it multiplies straight into accelspeed in
	  PMSrc_AirAccelerate (`accel * wishspeed * frametime * surfacefriction`).
	  Read it in the order pm_source.c writes it:

	      surfacefriction = 1
	      if (vel_z > 140)          -> not on ground, friction STAYS 1
	      else if (no standable plane under you)
	          not on ground; if (vel_z > 0) friction = 0.25

	  So: quartered strictly inside 0 < vel_z <= 140, off the ground.  The upper
	  bound is not decoration -- above 140 Source stops tracing for ground at
	  all, so the quarter never applies, and a jump leaves at 268 u/s.

	  AND AT CS:S SETTINGS IT CHANGES NOTHING, which is worth writing down
	  rather than discovering twice.  accelspeed is clamped to addspeed, and
	  addspeed can never exceed the 30 u/s air cap:

	      accelspeed = 150 * 250 * 0.015 * 0.25 = 140.6   vs  addspeed <= 30

	  so the cap binds at either friction and the gain is 30 both ways.  The
	  crossover is sv_airaccelerate 32 (30 / (0.25 * 250 * 0.015)); below that
	  the quarter starts to bind and this line starts to matter.  It is here
	  because the model should be the engine's, not because the bar was lying --
	  pm_selftest pins both halves of exactly that statement.
	*/
	fric = 1;
	if (!onground && vel_z > 0 && vel_z <= PM_NONJUMP_VEL)
		fric = 0.25;

	Font_Set(ui_font_ui);

	/*
	  CROUCHING crops the wishspeed -- ON THE GROUND ONLY, which is what this
	  was missing.  PMSrc_HandleDuckingSpeedCrop is
	  `if (pmove.ducked && pmove.onground)`; in the air the crop does not happen
	  and a crouched airborne player still has the full 250 to spend.

	  Same story as the friction above, and the same conclusion: at CS:S
	  settings it changes no displayed number.  Strafe_AirGain is
	  min(150*ws*0.015, 30) and that is 30 for ws = 85 as much as for ws = 250,
	  and Strafe_PlaneBest's `rate` argument only ever competes with a value
	  bounded by the same 30.  What the crop really drives is the GROUND gain
	  (5 * 0.015 * ws, so 6.4 crouched against 18.8 standing) -- and on the
	  ground it was already being applied, correctly.

	  So: crouching does not change surf air-acceleration, here or in Source.
	  What it does change is the HULL, and therefore which part of the ramp
	  clips you -- and that arrives through HUD_RampNormal, which reports the
	  plane the engine really used, so it has always been accounted for.
	*/
	wishspeed = maxspeed;
	// The duck STATE, which during a replay is the .rec's flags bit 2 rather
	// than the frozen player's -- see the override block in cl_keys.qc.
	if (onground)
	if (rec_wt_on ? rec_wt_ducked : (getstatf(STAT_FS_PMFLAGS) & PMF_DUCKED))
		wishspeed = maxspeed * serverkeyfloat("pm_duckspeed");
	if (wishspeed <= 0)
		wishspeed = maxspeed;

	best     = 0;
	havebest = FALSE;
	msg      = "";
	cscale   = aircap;

	// Build 39: seeded because the debug row publishes them unconditionally and
	// only the plane branch assigns them.  QC locals are a reused stack slot,
	// not zeroed storage, so an unassigned read is the PREVIOUS caller's value
	// -- which on this panel would be last frame's plane, printed as if it were
	// this one's.
	nz = 0;
	wn = 0;

	// Seeded before anything can leave, so the board panel underneath always has
	// a y even on the paths that draw the least.
	ui_strafe_bottom = by + h + 4 * ui_cv_scale;

	if (onground)
	{
		/*
		  THE GROUND IS A DIFFERENT PROBLEM, not a disabled one.

		  This used to say "not while standing", which was the easy answer and
		  the wrong one: ground strafing is real, it is how you leave a start
		  zone and how you carry speed across a flat between ramps, and the air
		  formula does not describe it.  Accelerate has no 30 u/s cap -- it adds
		  a CONSTANT A = accel*tick*wishspeed -- so the optimum sits at
		  dot(v,wishdir) = wishspeed - A rather than at zero, i.e. wishdir nearly
		  ALONG the velocity.  See sh_strafe.qc, and pm_selftest, which checks
		  these numbers against the real Friction/Accelerate pair.

		  Friction runs first each tick and only shrinks the velocity, so it
		  changes the speed the formula is evaluated at and nothing else.
		*/
		regime = 2;
		gain  = Strafe_GroundGain(accel, wishspeed, tick, fric);
		vf    = Strafe_AfterFriction(speed, gfric, stopspeed, tick);
		ideal = Strafe_IdealTurnGround(vf, gain, wishspeed, tick);
		best     = Strafe_GroundBest(speed, gain, wishspeed, gfric, stopspeed, tick);
		havebest = TRUE;

		/*
		  Below wishspeed - A the optimum is unreachable and the answer is
		  "point where you are going", so there is no target to grade against.

		  The threshold is 10 deg/s rather than 0.5, and the extra 9.5 buys
		  something specific.  The ground optimum has a SQUARE-ROOT shoulder at
		  |v| = wishspeed - A = 231.25: cos(theta) = 231.25/vf, so sin has
		  infinite slope there and a 1 u/s change in speed swings the target by
		  about 15 deg/s.  Prestrafing sits exactly on that shoulder, so the old
		  cut showed you a target thrashing between 0 and 50 deg/s and a bar
		  chasing it.  Hiding the unstable region says one true thing instead of
		  two flickering ones; above it the answer is well conditioned again.

		  ZEROED RATHER THAN RETURNED FROM.  This used to print "straight ahead"
		  and bail, which is gone by request -- and bailing was the worse half:
		  it skipped the `best` line, which is the ONE number that matters down
		  here (it is where you find out the ground ceiling has gone negative),
		  and it skipped publishing ui_strafe_bottom, so the board panel jumped
		  every time you crossed 231 u/s.  An empty bar says "no target" on its
		  own.
		*/
		if (ideal <= 10)
			ideal = 0;
	}
	else if (!Strafe_CapBinds(airaccel, maxspeed, tick, fric, aircap))
	{
		// Not a player problem and not gradeable: with the cap slack the gain is
		// accelspeed wherever you point, so a turn rate grades the server.
		regime = -1;
		ideal  = 0;
		msg    = "air cap does not bind";
	}
	else
	{
		gain = Strafe_AirGain(airaccel, wishspeed, tick, fric, aircap);

		/*
		  On a ramp the ideal is a DIFFERENT number, not an adjusted one -- the
		  clip couples gravity into the rotating component.  On a 53-degree face
		  it is 55% of the flat ideal one way and 17% the other, so reusing the
		  flat figure would overstate the target by up to 6x.

		  The plane comes from HUD_RampNormal -- the one the engine actually
		  clipped, oriented and held -- rather than from run_groundnorm, whose
		  dropouts were doing that 6x jump several times a second.
		*/
		regime = 0;
		rnorm  = HUD_RampNormal(vel);
		nz     = rnorm_z;

		if (rnorm != '0 0 0' && nz >= 0.05 && nz <= PM_STANDABLE && wishdir != '0 0 0')
		{
			regime = 1;
			wn     = wishdir * rnorm;
			ideal  = Strafe_IdealTurnPlane(speed, tick, gain, gravity, nz, wn);
			cscale = Strafe_CScale(gravity, tick, nz, wn, aircap);

			/*
			  3D and gravity-inclusive, unlike the other two -- see
			  Strafe_PlaneBest.  On a ramp gravity IS the gain, and a ceiling
			  with it removed would read near zero exactly where the map is
			  fastest.

			  It wants the RAW acceleration rate, not `gain`.  gain is already
			  min(rate, aircap); the plane search needs to redo that min against
			  aircap - dot(v, w) for every candidate heading, so it has to be
			  handed both halves.  They differ only on a server running a low
			  sv_airaccelerate -- 150*250*0.015 is 562.5 against a cap of 30 --
			  but "only on a badly configured server" is where a readout is least
			  scrutinised and most likely to mislead.
			*/
			best     = Strafe_PlaneBest(vel, tick, airaccel * wishspeed * tick * fric,
			                            aircap, gravity, rnorm);
			havebest = TRUE;

			// The plane model has no answer here (see Strafe_IdealTurnPlane):
			// the ramp is doing the turning, not you.  Show neutral rather than
			// inventing a target.
			if (ideal <= 0.001)
				cscale = aircap;
		}
		else
		{
			/*
			  BUILD 39 -- TWO SITUATIONS, AND THIS BRANCH USED TO TREAT THEM ALIKE.

			  Reaching here means the plane maths could not run, and there are
			  two entirely different reasons for that:

			    * you are not on a ramp at all.  The flat-air formula is then
			      the CORRECT answer and always was.
			    * you are riding one, and we could not get a usable plane for
			      it.  sh_strafe.qc:289 puts the flat figure at between 1.8x and
			      6x the real target on a ramp, and that is the whole of "the
			      ideal strafe speed doesn't update correctly when on ramps, it
			      tells you the correct non-ramp speed".

			  The test is ui_ramp_riding, not ui_ramp_why: see its declaration.
			  The plane outlives the ride by the difference between RAMPHOLD and
			  RAMP_GAP, so keying on "is a plane still held" would blank the
			  target for a sixth of a second after every single ramp exit.

			  Drawing the flat number in the second case is not a degraded
			  answer, it is a confident wrong one, and it also mis-scales the bar
			  underneath it because cscale falls back to bare aircap.  So say
			  nothing and say why -- the widget already has that path for "air
			  cap does not bind" and "too slow to grade", and an empty bar with a
			  reason on it is a reading.

			  hud_strafe_strict 0 restores the unconditional flat fallback.
			*/
			if (ui_cv_strict && ui_ramp_riding)
			{
				// Build 40: the reason, in the order that is useful -- see
				// HUD_StrafeWhy, which is where all four gates are now asked.
				ideal = 0;
				msg   = HUD_StrafeWhy(wishdir, nz, rnorm);
			}
			else
			{
				ideal    = Strafe_IdealTurn(speed, gain, tick);
				best     = Strafe_AirBest(speed, gain);
				havebest = TRUE;
			}
		}

		/*
		  See hud_strafe_minspeed.  AIR ONLY: the air ideal is atan2(gain, speed)
		  and diverges as speed falls, which is what put a four-digit target on
		  screen at a standstill.  The ground formula has no such pole -- it goes
		  to zero instead -- so the gate would only hide a good answer.

		  Tested AFTER the ideal rather than before it, which costs two multiplies
		  and buys the `best` line: the ceiling is perfectly well defined at
		  180 u/s even though the target rate is not, and it is worth seeing while
		  you build speed out of a start zone.
		*/
		if (speed < ui_cv_minspeed)
		{
			ideal = 0;
			msg   = "too slow to grade";
		}
	}

	// Build 39: published for the debug panel.  Which branch this function took
	// is the single most useful thing it knows and nothing could ask it.
	ui_strafe_regime = regime;
	ui_strafe_nz     = nz;
	ui_strafe_wn     = wn;

	// Smoothed with the same time constant as ui_turnrate, so both sides of the
	// comparison below are measured alike.
	ideal = HUD_SmoothIdeal(ideal, regime, dt);

	q = Strafe_Quality(ui_turnrate, ideal, cscale, aircap);
	col = HUD_QualityColor(q);

	/*
	  Above the bar: either why there is no grade, or two cells straddling the
	  centre -- what you ARE turning at, then what you SHOULD be.  The target is
	  in a fixed blue that is deliberately not part of the grading ramp, so it
	  reads as a target rather than as a score; the graded colour is the left
	  cell's job, and the bar's.
	*/
	/*
	  BUILD 31 -- AND THIS PAIR IS WHAT hud_update IS ACTUALLY FOR.

	  Unlike the speedometer, these two are genuinely recomputed from scratch on
	  every rendered frame: ui_turnrate is a window average over a ring that is
	  fed per frame, and `ideal` comes out of Strafe_PlaneBest's search against a
	  normal that can change every tick.  At 1000 fps the cells are unreadable
	  even though the underlying measurement is steady, which is exactly the
	  complaint.  Latched together with the speedometer so all four numbers on the
	  HUD change on the same edge.

	  The BAR is not latched, and must not be -- see HUD_UpdateLatch.  It reads
	  ui_turnrate directly below, and a bar that stepped 67 times a second would
	  be a worse instrument than a number that does.
	*/
	if (ui_hl_tick)
	{
		ui_hl_turn  = ui_turnrate;
		ui_hl_ideal = ideal;
	}

	/*
	  BUILD 40: THE MEASUREMENT IS ALWAYS DRAWN.  ONLY THE TARGET CAN BE ABSENT.

	  These were if / else-if, so a frame with no TARGET also stopped drawing
	  what you are actually turning at -- and that number is measured from your
	  own view angles, is never unavailable, and is the half of the pair you
	  steer by.  In its place went a message, centred across the same y so it
	  crossed both cells, in 50% grey at alpha 0.5 against their 0.95: "it says
	  over the text of the ideal strafe speed in a really faded font I can
	  barely read" is precisely that, and the strobe HUD_WishDir now fixes is
	  why it was there at all.

	  So the live rate keeps its cell unconditionally, and the message takes the
	  TARGET's cell -- the one slot that genuinely has nothing to show -- at the
	  same alpha as the numbers beside it.  A size smaller, because it is a
	  sentence next to two three-character readings, and neutral grey rather
	  than a graded colour, because it is a reason and not a score.
	*/
	HUD_TextR([p_x - 8 * ui_cv_scale, by - 15 * ui_cv_scale],
	          sprintf("%.0f/s", HUD_Round(ui_hl_turn)), 10 * ui_cv_scale, col, 0.95);

	if (msg != "")
		HUD_Text ([p_x + 8 * ui_cv_scale, by - 14 * ui_cv_scale], msg,
		          8 * ui_cv_scale, '0.74 0.74 0.74', 0.95);
	else if (ideal > 0.001)
		HUD_Text ([p_x + 8 * ui_cv_scale, by - 15 * ui_cv_scale],
		          sprintf("%.0f/s", HUD_Round(ui_hl_ideal)), 10 * ui_cv_scale, '0.45 0.70 1.00', 0.95);

	// --- the track ---
	drawfill([bx, by], [w, h], '0.05 0.06 0.08', 0.55, 0);

	if (ideal > 0.001)
	{
		/*
		  ONE SCALE FOR THE FILL AND FOR THE COLOUR.

		  The fill used err/hud_strafe_band with the band a constant, while the
		  colour used Strafe_Quality, whose falloff is scaled by cscale -- which
		  varies over a factor of eight on a ramp.  Two indicators, two
		  normalisations, one bar: it could sit pinned while the colour said
		  green, or read near the centre while the colour said red.

		  Strafe_Quality is q = 1 - m^2 with m = (1 - r)(cscale/aircap), so the
		  signed error it is really grading is -m.  Using that here makes the
		  bar's stop and the grade's zero the SAME POINT by construction at
		  hud_strafe_band 1: full deflection is exactly q = 0.  On flat ground
		  cscale == aircap and this is identical to the old expression.
		*/
		err  = ((ui_turnrate / ideal) - 1) * (cscale / aircap);
		frac = err / ui_cv_band;
		if (frac >  1) frac =  1;
		if (frac < -1) frac = -1;

		/*
		  hud_strafe_curve shapes the axis.  1 is linear and is the default.

		  This used to be a hard-coded signed square root, which at the old band
		  of 0.5 spent a fifth of the bar's travel on the first 2% of error --
		  52 px at hud_scale 2 for 2.3 deg/s at 1000 u/s.  That is inside a
		  hand's own noise and inside the quantisation of a windowed yaw
		  measurement, so the bar twitched at things you had not done.  Set
		  hud_strafe_curve 0.5 to get the old response back exactly.
		*/
		if (ui_cv_curve != 1)
			frac = (frac < 0) ? -pow(-frac, ui_cv_curve) : pow(frac, ui_cv_curve);

		// Follow mode: fill from the edge you are turning away from, so the
		// leading edge always moves the way your mouse is moving.
		if (ui_turnsign >= 0)
		{
			fillfrom = 0;
			fillto   = 0.5 + 0.5 * frac;
		}
		else
		{
			fillfrom = 1;
			fillto   = 0.5 - 0.5 * frac;
		}
		if (fillfrom > fillto) { t = fillfrom; fillfrom = fillto; fillto = t; }

		drawfill([bx + fillfrom * w, by], [(fillto - fillfrom) * w, h], col, 0.85, 0);
	}

	// Centre tick -- this is the ideal, and hitting it is the whole game.
	drawfill([bx + w * 0.5 - ui_cv_scale * 0.5, by - 2 * ui_cv_scale],
	         [ui_cv_scale, h + 4 * ui_cv_scale], '1 1 1', 0.9, 0);

	/*
	  Under the bar: what a PERFECT turn is actually worth, per tick.

	  IN ALL THREE REGIMES now, not just standing.  It used to be `if (onground)`
	  and therefore appeared in the one place a surfer never is.  The three
	  numbers are genuinely different functions -- Strafe_GroundBest carries
	  friction and goes negative, Strafe_AirBest is pure Pythagoras and cannot,
	  Strafe_PlaneBest folds in gravity along the ramp and is 3D -- and each is
	  derived and checked in sh_strafe.qc rather than fitted here.

	  The ground one goes negative above about 270 u/s and stays there: friction
	  takes |v|*friction*tick and acceleration can only ever add A, so past that
	  speed the best available turn still loses speed.  A bar that grades you out
	  of ten without saying so implies a gain that is not on offer; "you are
	  bleeding as slowly as it is possible to bleed" is the true reading and is
	  worth knowing before you blame your hands.

	  The energy `%` that used to sit here is GONE by request.  It measured
	  something real -- dE/dt over two seconds against the physical ceiling --
	  but per build 6's finding it had been showing a hard red 0 at any framerate
	  above ~256 fps for as long as it existed, so it never had a chance to mean
	  anything.  The measurement survives in `hud_debug`, where an unlabelled
	  diagnostic belongs.
	*/
	ty = by + h + 4 * ui_cv_scale;
	if (havebest)
	{
		local float bsz, blw, bnw, bsplit;
		local vector bcol;

		bsz  = 10 * ui_cv_scale;
		bcol = (best >= 0) ? '0.48 0.93 0.48' : '0.70 0.70 0.72';

		/*
		  TWO FIXED ANCHORS, NOT ONE CENTRED STRING.  This is why it used to
		  shuffle sideways as the number changed.

		  It was one HUD_TextC of "%+.1f u/s per tick at best".  Centring means
		  the line's position is a function of its WIDTH, so every time the
		  number gained or lost a character -- +3.5 to +18.7, or crossing zero
		  into -12.2 -- the whole string, label included, slid by half that
		  character.  Twenty stationary letters moving because one digit changed.

		  A MONOSPACE FONT WOULD NOT HAVE FIXED IT, which is worth saying since
		  that was the obvious idea: a centred string still moves by half a glyph
		  whenever the character COUNT changes, and the count is exactly what
		  changes here.  (Roboto's digits are already tabular, so same-length
		  values were never the problem.)

		  So the number is right-aligned to a fixed x and the label is
		  left-aligned from that same fixed x.  The label cannot move at all now,
		  and the only thing that ever moves is the number's own left edge, which
		  is the one thing that has to.  The split is placed so a typical
		  five-character reading sits centred on the bar.
		*/
		blw    = stringwidth(" u/s per tick at best", TRUE, [bsz, bsz]);
		bnw    = stringwidth("+00.0", TRUE, [bsz, bsz]);
		bsplit = p_x - (bnw + blw) * 0.5 + bnw;

		if (ui_hl_tick)
			ui_hl_best = best;

		/*
		  BUILD 31 -- AND THE FORMAT CHANGES WITH THE STEP, DELIBERATELY.

		  This line is %+.1f, so at hud_round 1 or above the decimal would always
		  print as .0 -- a dead digit that makes a quantised number look like a
		  precise one that has stopped moving.  Dropping to %+.0f above the step
		  makes the quantisation visible instead of disguised, which is the whole
		  point of asking for it.  hud_round 0 keeps the tenth.
		*/
		if (cvar("hud_round") >= 1)
			HUD_TextR([bsplit, ty], sprintf("%+.0f", HUD_Round(ui_hl_best)), bsz, bcol, 0.75);
		else
			HUD_TextR([bsplit, ty], sprintf("%+.1f", ui_hl_best), bsz, bcol, 0.75);
		HUD_Text ([bsplit, ty], " u/s per tick at best", bsz, bcol, 0.75);

		ty = ty + 13 * ui_cv_scale;
	}

	ui_strafe_bottom = ty;

	Font_Reset();

	/*
	  Build 31: the box, for the layout editor.

	  It starts 15*scale ABOVE the anchor, because the two rate cells are drawn
	  over the bar and hud_strafe_y names the bar's own top edge.  That asymmetry
	  is exactly why HUD_Rect is handed the anchor separately instead of the
	  editor inverting the box: there is no general rule that recovers it.
	*/
	HUD_Rect("strafe", [bx, by - 15 * ui_cv_scale, 0],
	         [w, ty - (by - 15 * ui_cv_scale), 0], [p_x, by, 0]);
};

/*
  Keypress block, right-hand side.

  Reads the KEYBOARD (cl_keys.qc), not the outbound command, so it responds
  with zero latency -- which is the whole point of a key display when you are
  learning strafe timing, and which is only true now that it is not resampling
  a 66.7 Hz command from a 300 Hz draw.  See cl_keys.qc for why that showed up
  as a held key flickering.

  +left / +right are the two vertical bars flanking A and D, and they light
  from the BINDS.  They used to light from the measured turn instead, which
  meant they came on whenever you moved the mouse -- they had no choice, since
  +left and +right set no usercmd button bit for anything to read.
*/
/*
  `held` is a FOUR-state, not a boolean:
     0  not pressed
     1  pressed
     2  the game is holding it for you   -- filled yellow, as Momentum does
     3  the game is letting go for you   -- yellow on dark

  Two and three are the same statement -- "this is not your hand" -- so they
  share the yellow, and they are inverted against each other because they are
  opposite: FORCED is a key you are not pressing that is going out anyway, and
  RELEASED is a key you ARE pressing that is not.  Filled means "the game is
  sending this", which is true of one and false of the other, so the fill is
  doing the work and the hue only says who decided.

  FORCED is the crouch case: ducked without asking, because PMSrc_CanUnduck
  traced the standing hull and it did not fit, so your hull stays 45 tall until
  you are clear.  RELEASED is run_prestrafe dropping W for the flight.  Telling
  either apart from a stuck key by feel alone is most of a confusing minute.
*/
#define KEY_UP       0
#define KEY_DOWN     1
#define KEY_FORCED   2
#define KEY_RELEASED 3

void(vector pos, vector sz, float held, string label, float lsz) HUD_Key =
{
	local vector bg, fg;
	local float  a;

	if (held == KEY_FORCED)        { bg = '1.00 0.82 0.20'; fg = '0.10 0.08 0.02'; a = 0.85; }
	else if (held == KEY_RELEASED) { bg = '0.16 0.13 0.03'; fg = '1.00 0.82 0.20'; a = 0.85; }
	else if (held)                 { bg = '1 1 1';          fg = '0.06 0.09 0.11'; a = 0.85; }
	else                           { bg = '0 0 0';          fg = '0.75 0.75 0.75'; a = 0.35; }

	drawfill(pos, sz, bg, a, 0);
	pos_x = pos_x + (sz_x - stringwidth(label, TRUE, [lsz, lsz])) * 0.5;
	pos_y = pos_y + (sz_y - lsz) * 0.5;
	drawstring(pos, label, [lsz, lsz], fg, 1, 0);
};

void(vector scr) HUD_DrawKeys =
{
	local vector p, sz;
	local float k, gap, lsz, bw, pad;
	local float kw, ks, ka, kd, jump, duck, tl, tr;

	p   = '0 0 0';              // set component-wise below; keep fteqcc happy
	k   = 16 * ui_cv_scale;
	lsz = Font_Px(8 * ui_cv_scale);
	gap = 2 * ui_cv_scale;
	bw  = 4 * ui_cv_scale;          // the +left / +right bars
	sz  = [k, k];

	/*
	  BUILD 24: THE REPLAYED KEYS, and the reason the .view exists at all.

	  Its sixth column is this exact mask, written by Rec_ViewKeys from the same
	  Keys_Held calls below -- so a replay does not approximate the key block,
	  it reproduces it, +left and +right included.  Those two have no usercmd bit
	  at any sample rate, so no amount of server-side recording could ever have
	  got them back; they are here only because the client wrote them down.

	  rec_wt_psrel is FSI_PSREL lifted out of the same mask, so the yellow-on-dark
	  released-W state below replays as it happened rather than as a plain lit W.
	*/
	if (rec_wt_on)
	{
		kw   = (rec_wt_keys & FSI_FWD)    ? TRUE : FALSE;
		ks   = (rec_wt_keys & FSI_BACK)   ? TRUE : FALSE;
		ka   = (rec_wt_keys & FSI_LEFT)   ? TRUE : FALSE;
		kd   = (rec_wt_keys & FSI_RIGHT)  ? TRUE : FALSE;
		jump = (rec_wt_keys & FSI_JUMP)   ? TRUE : FALSE;
		duck = (rec_wt_keys & FSI_DUCK)   ? TRUE : FALSE;
		tl   = (rec_wt_keys & FSI_TLEFT)  ? TRUE : FALSE;
		tr   = (rec_wt_keys & FSI_TRIGHT) ? TRUE : FALSE;
	}
	else
	{
		kw   = Keys_Held(FSK_FWD);
		ks   = Keys_Held(FSK_BACK);
		ka   = Keys_Held(FSK_LEFT);
		kd   = Keys_Held(FSK_RIGHT);
		jump = Keys_Held(FSK_JUMP);
		duck = Keys_Held(FSK_DUCK);
		tl   = Keys_Held(FSK_TLEFT);
		tr   = Keys_Held(FSK_TRIGHT);
	}

	/*
	  FORCED CROUCH.  Ducked without holding the key means the mover is refusing
	  to stand you up -- PMSrc_CanUnduck traced the standing hull and it did not
	  fit, so you keep the 45-unit box and the 47-unit eye until you are clear.

	  The two halves come from different places on purpose, and that is the whole
	  test: PMF_DUCKED is the ENGINE's carried duck state, arriving as a stat,
	  while Keys_Held reads the KEYBOARD directly (see cl_keys.qc).  Neither can
	  answer this alone -- the stat cannot tell you why, and the key cannot tell
	  you that it took.

	  BUILD 41: this was unreachable until now.  PMSrc_CanUnduck was tracing
	  pms_standmaxs, which carries the DUCKED height for the whole time the test
	  matters (the entity gets resized by the previous move's writeback), so it
	  always "fitted" and you stood straight into the ceiling instead.  The cell
	  below has been correct and dark since build 30.
	*/
	if (duck)
		duck = KEY_DOWN;
	else if (rec_wt_on ? rec_wt_ducked : (getstatf(STAT_FS_PMFLAGS) & PMF_DUCKED))
		duck = KEY_FORCED;

	/*
	  BUILD 14.  W held, W not being sent -- run_prestrafe took it for the
	  flight (cl_main.qc).  Order matters: the release only exists while the
	  key is down, so this can only ever downgrade a KEY_DOWN, never light a
	  key nobody is touching.
	*/
	if (kw)
	if (rec_wt_on ? rec_wt_psrel : run_ps_release)
		kw = KEY_RELEASED;

	p_y = scr_y * ui_cv_keyspos_y;

	/*
	  The right-hand gap is MEASURED from the bottom one rather than guessed
	  at as a screen fraction, because "the same padding it has against the
	  floor" is only true at one aspect ratio and one hud_scale if you write
	  it as a fraction.  The block's own bottom edge is
	  y + 2*(k+gap) + lsz*2, so the floor gap falls out of hud_keys_y, and
	  the same number then positions the right edge.

	  hud_keys_x overrides it if you want the block somewhere else: non-zero
	  is taken as a left-edge screen fraction, the way the other panels work.
	*/
	pad = scr_y - (p_y + 2 * (k + gap) + lsz * 2);
	if (pad < 0)
		pad = 0;

	if (ui_cv_keyspos_x > 0)
		p_x = scr_x * ui_cv_keyspos_x;
	else
		p_x = scr_x - pad - 3 * (k + gap) - bw;

	Font_Set(ui_font_ui);

	// row 1:  W
	HUD_Key([p_x + k + gap, p_y], sz, kw, "W", lsz);

	// row 2:  |  A S D  |   -- the flanking bars are +left and +right
	drawfill([p_x - bw - gap, p_y + k + gap], [bw, k],
	         tl ? '0.45 0.70 1.00' : '0 0 0', tl ? 0.85 : 0.35, 0);
	HUD_Key([p_x,               p_y + k + gap], sz, ka, "A", lsz);
	HUD_Key([p_x + k + gap,     p_y + k + gap], sz, ks, "S", lsz);
	HUD_Key([p_x + 2*(k + gap), p_y + k + gap], sz, kd, "D", lsz);
	drawfill([p_x + 3*(k + gap), p_y + k + gap], [bw, k],
	         tr ? '0.45 0.70 1.00' : '0 0 0', tr ? 0.85 : 0.35, 0);

	// row 3:  duck + jump
	HUD_Key([p_x,           p_y + 2*(k + gap)], [k, lsz * 2], duck, "C", lsz);
	HUD_Key([p_x + k + gap, p_y + 2*(k + gap)], [k * 2 + gap, lsz * 2], jump, "Jump", lsz);

	Font_Reset();

	/*
	  Build 31: the box, and the anchor is p_x -- the block's own left origin,
	  which is what a non-zero hud_keys_x encodes.  While the cvar is 0 the value
	  above is the AUTO-RIGHT result rather than a fraction, and publishing it
	  anyway is what lets the editor drag the block off auto without a special
	  case: it moves the pixel it is given and divides once.

	  The drawn extent is wider than the anchor on both sides -- the +left bar
	  hangs bw+gap to the left of p_x, and the +right bar sits past the third key
	  column -- so the box is stated from those edges rather than from p.
	*/
	HUD_Rect("keys",
	         [p_x - bw - gap, p_y, 0],
	         [3 * (k + gap) + 2 * bw + gap, 2 * (k + gap) + lsz * 2, 0],
	         [p_x, p_y, 0]);
};

/*
  Physics readout.  Off by default now (hud_debug 0) -- it is a debugger,
  not part of the HUD -- but every line it ever had is still here, because
  the one time you want it is the time something is wrong.
*/
void(vector scr, vector vel, float onground, vector gnorm, float mtype) HUD_DrawDebug =
{
	local vector p, bp;
	local float sz, lh, rx;
	local string state;
	local vector col;

	sz = 8 * ui_cv_scale;
	lh = sz + 2 * ui_cv_scale;
	p  = [scr_x * ui_cv_debugpos_x, scr_y * ui_cv_debugpos_y, 0];
	bp = p;
	rx = p_x + 110 * ui_cv_scale;       // the column the numbers END on

	Font_Set(ui_font_ui);

	// The 0.7 gate is the whole of surfing: normal_z >= 0.7 is ground,
	// anything steeper leaves you airborne and sliding.
	if (mtype == MOVETYPE_NOCLIP)      { state = "NOCLIP";  col = '0.6 0.6 1.0'; }
	else if (onground)                 { state = "GROUND";  col = '0.5 0.9 0.5'; }
	else if (gnorm != '0 0 0' && gnorm_z < PM_STANDABLE && gnorm_z > 0.05)
	                                   { state = "SURFING"; col = '0.34 0.78 1.0'; }
	else                               { state = "AIR";     col = '0.9 0.9 0.6'; }

	HUD_Text(p, state, sz, col, 1);                                    p_y += lh;

	/*
	  BUILD 47: latched, like every other panel, and RENAMED.

	  The row said `xy` and printed a SPEED -- vlen of the horizontal velocity.
	  There is no position readout anywhere in this tree, so anyone reading `xy`
	  as a coordinate and watching it "jump 0-4 units per frame" was chasing a
	  position bug that does not exist.  `xyspd` costs three characters and
	  ends that.
	*/
	if (ui_hl_tick)
	{
		ui_hl_dbgxy = vlen([vel_x, vel_y, 0]);
		ui_hl_dbgz  = vel_z;
	}

	HUD_Text(p, "xyspd", sz, '1 1 1', 0.8);
	HUD_TextR([rx, p_y], sprintf("%.2f", ui_hl_dbgxy), sz, '1 1 1', 0.8); p_y += lh;
	HUD_Text(p, "zspd", sz, '1 1 1', 0.8);
	HUD_TextR([rx, p_y], sprintf("%.2f", ui_hl_dbgz), sz, '1 1 1', 0.8);  p_y += lh;

	if (gnorm != '0 0 0')
	{
		local vector nc;
		nc = (gnorm_z < PM_STANDABLE) ? '0.34 0.78 1.0' : '0.5 0.9 0.5';
		HUD_Text(p, "n.z", sz, nc, 0.9);
		HUD_TextR([rx, p_y], sprintf("%.4f", gnorm_z), sz, nc, 0.9);
	}
	else
	{
		HUD_Text(p, "n.z", sz, '0.5 0.5 0.5', 0.6);
		HUD_TextR([rx, p_y], "--", sz, '0.5 0.5 0.5', 0.6);
	}
	p_y += lh * 1.5;

	HUD_Text(p, "turn", sz, '0.6 0.6 0.6', 0.7);
	HUD_TextR([rx, p_y], sprintf("%.0f/s", ui_turnrate), sz, '0.6 0.6 0.6', 0.7); p_y += lh;

	/*
	  BUILD 30: THE STATE THAT MADE A SAVE-LOCK LOAD READ WRONG, on screen.

	  Three rows, and each one answers a question this panel could not previously
	  be asked.  Printed even when clear -- this is the diagnostic that is meant
	  to say why the readouts say what they say, and a row that vanishes when the
	  answer is "nothing" cannot distinguish that from "not implemented".

	    hold   the save-lock freeze.  `park` means the numbers above are coming
	           from STAT_FS_HOLDVEL rather than STAT_FS_VELOCITY, which is the
	           whole of build 30's first fix -- if the speed reads 0 while this
	           says park, the substitution is what is broken, not the server.
	    ramp   age of the held ramp plane, in seconds, against RAMPHOLD.  A load
	           used to leave this counting up from BEFORE the teleport; it should
	           read `--` the instant you land somewhere new.
	    ehist  samples in the energy ring.  Drops to 0 on a load now, and stops
	           growing while parked.
	*/
	if (rec_sl_held)
	{
		HUD_Text(p, "hold", sz, '1.00 0.82 0.20', 0.9);
		HUD_TextR([rx, p_y], "park", sz, '1.00 0.82 0.20', 0.9);
	}
	else
	{
		HUD_Text(p, "hold", sz, '0.5 0.5 0.5', 0.6);
		HUD_TextR([rx, p_y], "--", sz, '0.5 0.5 0.5', 0.6);
	}
	p_y += lh;

	if (ui_ramp_time > 0 && board_now >= ui_ramp_time)
	{
		HUD_Text(p, "ramp", sz, '0.6 0.6 0.6', 0.7);
		HUD_TextR([rx, p_y], sprintf("%.2fs", board_now - ui_ramp_time), sz, '0.6 0.6 0.6', 0.7);
	}
	else
	{
		HUD_Text(p, "ramp", sz, '0.5 0.5 0.5', 0.6);
		HUD_TextR([rx, p_y], "--", sz, '0.5 0.5 0.5', 0.6);
	}
	p_y += lh;

	HUD_Text(p, "ehist", sz, '0.6 0.6 0.6', 0.7);
	HUD_TextR([rx, p_y], sprintf("%g", ui_ehist_len), sz, '0.6 0.6 0.6', 0.7); p_y += lh;

	/*
	  BUILD 39: THE THREE ROWS THAT ANSWER "WHY DOES IT SAY THAT".

	    src    which clock the numbers above came from, and how far the other
	           one was.  It must read `pred` in ordinary play; `stat` means the
	           fallback in HUD_Feet fired and every reading on screen is the
	           build-38 quantity.  The disagreement is legitimately non-zero --
	           1/16 of a unit standing still, up to 15 on stairs from
	           pv->crouch, and up to 18 for a snapshot after a save-lock load
	           into a crouch.  A large steady number means something else.

	    str    which branch HUD_DrawStrafe took.  `plane` is the only one that
	           uses the ramp maths; the three flat: rows are the ones that used
	           to silently substitute a target up to 6x too big.

	    plane  where that plane came from and what was fed to the formula.
	           `flipped` is the one to watch -- see the orientation block in
	           HUD_RampNormal, which is the strongest candidate for the ramp
	           report and is deliberately visible rather than assumed.

	    hold   build 40.  the keyboard's answer to "is the save-lock down"
	           against the wire's.  `settling` is the guard in HUD_UpdateLatch
	           holding the readouts still across the edge; it should be visible
	           for two or three frames and never longer.

	    wish   build 40.  the forward/side the engine handed the strafe target,
	           and the yaw built from it.  Hold one strafe key on flat ground:
	           the left half must be STEADY.  It used to read 0/0 on about one
	           frame in five -- see HUD_WishDir -- and that is the whole of "it
	           says no strafe key but I definitely am pressing one".

	  Printed even when clear, per the rule the build 30 rows above are written
	  to: a row that vanishes when the answer is "nothing" cannot be told apart
	  from a row that was never implemented.
	*/
	if (ui_src_pred)
	{
		HUD_Text(p, "src", sz, '0.5 0.9 0.5', 0.9);
		HUD_TextR([rx, p_y], sprintf("pred %.2f", ui_src_disagree), sz, '0.5 0.9 0.5', 0.9);
	}
	else
	{
		HUD_Text(p, "src", sz, '1.00 0.55 0.35', 0.9);
		HUD_TextR([rx, p_y], "stat", sz, '1.00 0.55 0.35', 0.9);
	}
	p_y += lh;

	if      (ui_strafe_regime ==  1) state = "plane";
	else if (ui_strafe_regime ==  2) state = "ground";
	else if (ui_strafe_regime == -1) state = "cap slack";
	else if (!ui_ramp_riding)           state = "flat: free air";
	else if (ui_ramp_why == RW_NOPLANE) state = "flat: no plane";
	else                                state = "flat: on a ramp";

	col = (ui_strafe_regime == 1 || !ui_ramp_riding)
	      ? '0.6 0.6 0.6' : '1.00 0.82 0.20';
	HUD_Text(p, "str", sz, col, 0.8);
	HUD_TextR([rx, p_y], state, sz, col, 0.8); p_y += lh;

	if      (ui_ramp_why == RW_FRESH)   state = "fresh";
	else if (ui_ramp_why == RW_HELD)    state = "held";
	else if (ui_ramp_why == RW_FLIPPED) state = "flipped";
	else if (ui_ramp_why == RW_NOPLANE) state = "none";
	else                                state = "--";

	if (ui_ramp_why == RW_FRESH || ui_ramp_why == RW_HELD || ui_ramp_why == RW_FLIPPED)
		state = sprintf("%s %.3f/%.2f", state, ui_strafe_nz, ui_strafe_wn);

	col = (ui_ramp_why == RW_FLIPPED) ? '1.00 0.45 0.45' : '0.6 0.6 0.6';
	HUD_Text(p, "plane", sz, col, 0.8);
	HUD_TextR([rx, p_y], state, sz, col, 0.8); p_y += lh;

	/*
	  BUILD 40: the save-lock edge, which is the one place the readouts above
	  are deliberately allowed to stand still.

	  Left of the slash is the keyboard (rec_sl_holding, known on the key edge);
	  right of it is the wire (STAT_FS_HOLD, a round trip later).  They agree
	  except for the two or three frames the settle guard exists for, and the
	  row turns amber for exactly those frames.  An amber that STAYS on is the
	  failure worth catching: it means the guard armed and its evidence never
	  arrived -- a refused hold, or a lost stat -- and HUD_UpdateLatch's stall
	  floor is releasing the display every 0.25s rather than the stat doing it.
	*/
	state = sprintf("%s / %s%s",
	                rec_sl_holding ? "key" : "--",
	                rec_sl_held    ? "wire" : "--",
	                rec_sl_settle  ? "  settling" : "");
	col = rec_sl_settle ? '1.00 0.82 0.20' : '0.6 0.6 0.6';
	HUD_Text(p, "hold", sz, col, 0.8);
	HUD_TextR([rx, p_y], state, sz, col, 0.8); p_y += lh;

	/*
	  BUILD 40: the usercmd the strafe target is built from, and the row that
	  makes report A visible without a ramp.

	  Left of the arrow is what the ENGINE handed over -- forward/side out of
	  the usercmd, after getinputstate has substituted the last sent command for
	  a cleared pending one.  Hold one strafe key on flat ground and watch it:
	  before this build it dropped to `0/0` on roughly one frame in five, at
	  cl_netfps/framerate, and every one of those frames told the strafe widget
	  you were pressing nothing.  It must now be steady.

	  Right of the arrow is the resulting wishdir as a yaw, or `--` for none.
	  `kb` means the keyboard fallback answered because the engine had nothing;
	  expected only while paused, and a permanent `kb` means getinputstate is
	  failing for a reason worth finding.
	*/
	if (ui_wish_dir == '0 0 0')
		state = sprintf("%.0f/%.0f -> --", ui_wish_raw_x, ui_wish_raw_y);
	else
		state = sprintf("%.0f/%.0f -> %.0f%s", ui_wish_raw_x, ui_wish_raw_y,
		                vectoyaw(ui_wish_dir), ui_wish_kb ? " kb" : "");
	col = (ui_wish_raw == '0 0 0' && ui_wish_dir != '0 0 0')
	      ? '1.00 0.82 0.20' : '0.6 0.6 0.6';
	HUD_Text(p, "wish", sz, col, 0.8);
	HUD_TextR([rx, p_y], state, sz, col, 0.8); p_y += lh;

	/*
	  BUILD 41: EYE HEIGHT, MEASURED RATHER THAN ARGUED ABOUT.

	  Reported as "viewhight is like 32units to high?".  Reading the code says it
	  is not: VF_ORIGIN is simorg + 1/16 + pv->viewheight (+bob, +crouch, both 0
	  here), simorg is the FEET because the hull mins.z is 0, and viewheight is 64
	  standing -- which is exactly Momentum's VEC_VIEW.  But "the code says so" is
	  what was said about the crouch-jump too, and that was wrong twice, so this
	  row puts the actual number on screen.

	  eye  = camera above the traced floor, which is the number the report is
	         about.  Momentum standing: 64.  Ducked: 47.
	  hull = feet-to-crown right now.  62 standing, 45 ducked.  This is the one
	         that genuinely differs from Momentum if it ever does, and being 10
	         units taller than Momentum reads a lot like "too high" even when the
	         eye is identical.

	  THE QUANTITY IS cam_z - pmove_org_z, AND A FLOOR TRACE IS NOT A SUBSTITUTE.

	  The first version of this row traced down from the camera to "the floor",
	  on the reasoning that it needed no origin and so could not be fooled by a
	  bad one.  It read 80.6 and went amber, which looked like proof the report
	  was right.  It was not: on surf_aesthetic's spawn the player stands on a
	  BRUSH ENTITY, which CSQC's traceline did not collide, so the trace fell
	  through it and found world geometry 16.5 units lower.  The eye was 64.06
	  the whole time.

	  BUILD 53 CHANGES THE SECOND HALF OF THAT AND NOT THE FIRST.  cl_sprites.qc
	  now instantiates client-side copies of the map's solid brush entities so
	  the glare and spotlight traces can hit them (vbsp_glare_brush), and this
	  trace shares csqc_world with them, so it lands on the brush now.  That
	  makes the cross-check better, and it does NOT make it the right answer:
	  the floor trace still measures camera-to-floor, which is a different
	  quantity from camera-to-feet whenever the player is not standing on the
	  surface directly below the camera -- mid-air, on a ramp, on a ledge edge.
	  It also silently depends on a cvar someone may have set to 0.

	  So the floor trace stays only as a cross-check, clearly labelled, and never
	  as the headline.  pmove_org is the feet and is what the question is about;
	  hud_eyetrace prints STAT_VIEWHEIGHT beside it so the two can be seen to
	  agree rather than assumed to.
	*/
	{
		local vector cam, hullv, viewv;
		local float floorz, eyeh, gap, ducked;

		cam = getproperty(VF_ORIGIN);
		ducked = rec_wt_on ? rec_wt_ducked
		                  : (getstatf(STAT_FS_PMFLAGS) & PMF_DUCKED);

		// A vector constant is not swizzleable in place -- see sv_zones.qc:410.
		hullv = ducked ? PM_DUCK_MAXS : PM_HULL_MAXS;
		viewv = ducked ? PM_DUCK_VIEW_OFS : PM_VIEW_OFS;

		eyeh = cam_z - pmove_org_z;

		traceline(cam, cam - '0 0 8192', TRUE, world);
		floorz = (trace_fraction < 1) ? trace_endpos_z : cam_z;
		gap = cam_z - floorz;

		/*
		  hud_eyetrace <N> dumps the next N frames of every term to the console
		  and counts itself down, like hud_wishtrace.  A HUD row can say the
		  answer is wrong; only this can say WHICH term is wrong, and the whole
		  point of this block is that reading the code got it wrong twice.
		*/
		{
			local float t;
			t = cvar("hud_eyetrace");
			if (t > 0)
			{
				cvar_set("hud_eyetrace", ftos(t - 1));
				// Split in two: fteqcc caps a varargs call at 8 parameters
				// INCLUDING the format string.
				print(sprintf("eye: cam %.3f org %.3f -> eye %.3f | stat %.3f | ducked %g\n",
				              cam_z, pmove_org_z, eyeh,
				              getstatf(STAT_VIEWHEIGHT), ducked));
				print(sprintf("eye: floortrace %.3f frac %.3f gap %.3f (brush ents hit: %g)\n",
				              floorz, trace_fraction, gap, cvar("vbsp_glare_brush")));
			}
		}

		// Amber when the eye is not where the shipped constants say it should be.
		// Driven by eyeh (cam - feet), NOT by the floor gap -- see above.
		col = (fabs(eyeh - viewv_z) > 1.5) ? '1.00 0.82 0.20' : '0.6 0.6 0.6';
		HUD_Text(p, "eye", sz, col, 0.8);
		HUD_TextR([rx, p_y], sprintf("%.2f  hull %g%s", eyeh, hullv_z,
		                             ducked ? " duck" : ""), sz, col, 0.8);
		p_y += lh;
	}

	/*
	  The efficiency gauge, which used to live under the strafe bar.

	  dE/dt over hud_strafe_window seconds as a fraction of the most air strafing
	  can physically add (ws^2 / 2*g*tick = 37.5 u/s).  100% means "for two
	  seconds you added energy as fast as it is possible to".  It is a real
	  measurement and it is worth keeping -- but it answers a slower question
	  than the bar does, it was never labelled clearly enough to be read at
	  speed, and per build 6's finding it had been showing a hard red 0 above
	  ~256 fps for its entire life.  Here it is optional and next to the other
	  raw numbers, which is where it belongs.
	*/
	if (fabs(ui_eta) <= STRAFE_ETA_NOT_PLAYER)
	{
		HUD_Text(p, "eta", sz, '0.6 0.6 0.6', 0.7);
		HUD_TextR([rx, p_y], sprintf("%.0f%%", ui_eta * 100), sz, '0.6 0.6 0.6', 0.7);
	}
	else
	{
		// Off the scale on the gain side is a booster or a teleport, not you.
		HUD_Text(p, "eta", sz, '0.5 0.5 0.5', 0.6);
		HUD_TextR([rx, p_y], "--", sz, '0.5 0.5 0.5', 0.6);
	}
	p_y += lh;

	HUD_Text(p, "anchor", sz, '0.6 0.6 0.6', 0.7);
	HUD_TextR([rx, p_y], (ui_anchor_zone < 0 && !ui_anchor_manual)
	          ? "--" : sprintf("%.0f", ui_anchor_z),
	          sz, '0.6 0.6 0.6', 0.7);                                  p_y += lh;
	HUD_Text(p, "tick", sz, '0.6 0.6 0.6', 0.7);
	HUD_TextR([rx, p_y], sprintf("%.4f", PM_TICK), sz, '0.6 0.6 0.6', 0.7); p_y += lh;
	HUD_Text(p, "aacc", sz, '0.6 0.6 0.6', 0.7);
	HUD_TextR([rx, p_y], sprintf("%.1f", serverkeyfloat("sv_airaccelerate")), sz, '0.6 0.6 0.6', 0.7); p_y += lh;
	HUD_Text(p, "fric", sz, '0.6 0.6 0.6', 0.7);
	HUD_TextR([rx, p_y], sprintf("%.1f", serverkeyfloat("sv_friction")), sz, '0.6 0.6 0.6', 0.7); p_y += lh;
	HUD_Text(p, "grav", sz, '0.6 0.6 0.6', 0.7);
	HUD_TextR([rx, p_y], sprintf("%.1f", serverkeyfloat("sv_gravity")), sz, '0.6 0.6 0.6', 0.7); p_y += lh;

	if (serverkeyfloat("pm_stamina"))
	{
		HUD_Text(p, "stam", sz, '0.6 0.6 0.6', 0.7);
		HUD_TextR([rx, p_y], sprintf("%.0f/%.0f", serverkeyfloat("pm_staminajumpcost"),
		          serverkeyfloat("pm_staminalandcost")), sz, '0.6 0.6 0.6', 0.7);
	}
	else
	{
		HUD_Text(p, "stam", sz, '0.5 0.5 0.5', 0.6);
		HUD_TextR([rx, p_y], "off", sz, '0.5 0.5 0.5', 0.6);
	}

	Font_Reset();

	// Build 31.  Left/top anchored, and the width is the column the right-aligned
	// numbers end on rather than a measurement -- rx is where every value in the
	// block lines up, so it IS the block's right edge by construction.
	HUD_Rect("debug", bp, [rx - bp_x, p_y + lh - bp_y, 0], bp);
};

/*
===========================================================================
  Turn rate.

  Measured from the view yaw rather than from the mouse, so it is the same
  number whatever the sensitivity, and averaged over SECONDS rather than
  frames -- see hud_strafe_smooth.

  WHY THIS IS A WINDOW AND NOT A FILTER.  It used to exponentially smooth
  |d_yaw / dt| computed once per rendered frame.  At 300+ fps a frame receives
  two or three mouse reports, sometimes four, sometimes one -- so the ratio
  being filtered carried +-30% quantisation noise that no time constant short
  enough to feel live could remove, and the bar buzzed.  Total angle travelled
  divided by total time has no such term: the quantisation cancels in the sum
  instead of being averaged.  It is also exactly what "smoothing window" ought
  to have meant, and it costs the same ring HUD_EnergyRate already uses.

  Two accumulators, and the pair is the point:

    path    sum of |d_yaw|, the distance your hand travelled
    net     sum of  d_yaw,  where it ended up

  RATE comes from path, so a direction change still reads as a real turn rate
  instead of collapsing to zero the moment the window straddles the reversal --
  which a signed average would do at the exact moment the bar matters most.
  DIRECTION comes from net, and comparing it against path is the hysteresis:
  a committed turn has |net| ~= path, a wobble has |net| ~= 0.  That replaces
  the old 100 ms timer with something that measures coherence rather than
  guessing at it.
===========================================================================
*/
// 192 SAMPLES, spaced hud_strafe_smooth/(TWIN-1) apart -- not 192 frames.  As
// frames it capped the window at 0.1910 s at the shipped cl_maxfps 1000 and
// saturated from 955 fps up, so the window silently stopped being the one you
// configured.  Unlike the energy ring that degraded quietly rather than dying
// (HUD_UpdateTurn has no span guard at all), but it still has to be right
// before `ideal` is low-passed through "the same window" below.
#define TWIN 192
float ui_thist_p[TWIN];         // cumulative |d_yaw|
float ui_thist_n[TWIN];         // cumulative  d_yaw
float ui_thist_t[TWIN];
float ui_thist_head, ui_thist_len, ui_thist_lastt;
float ui_yawpath, ui_yawnet;    // running totals, degrees

void() HUD_ClearTurnHistory =
{
	ui_thist_head  = 0;
	ui_thist_len   = 0;
	ui_thist_lastt = 0;
	ui_yawpath     = 0;
	ui_yawnet      = 0;
	ui_turnrate    = 0;
	ui_ideal_lp    = 0;
	ui_ideal_regime = -1;

	// The held ramp plane goes with them: a plane from the previous map is
	// worse than no plane, and cltime restarting would otherwise leave the
	// hold looking fresh.
	ui_ramp_norm = '0 0 0';
	ui_ramp_time = 0;
};

/*
  BUILD 24: THIS RUNS ON board_now, NOT ON cltime, AND dt ARRIVES SCALED.

  It measures degrees per second, and during a replay both halves of that
  fraction have to be in the same clock or the answer is the playback speed times
  the truth.  The numerator already is: getproperty(VF_ANGLES) is the recorded
  camera, written by Watch_Camera earlier in the same frame, so the yaw it
  differences is the yaw the run had.  The denominator was wall time, so at 4x a
  300 deg/s strafe read 1200 and the bar graded it against a target for 300.

  board_now is the HUD's frame clock -- cltime live, the recording's own run clock
  during a replay -- and HUD_Draw scales dt to match before calling.  Live, both
  are exactly what they were.

  A backwards scrub makes board_now jump back, which the ring push below already
  handles (it has always had to, for a map change).  ui_yawpath keeps accumulating
  across it and reads high for one window; that is a quarter second after a
  deliberate jump, and the alternative -- clearing the history on every seek --
  would blank the bar on every frame of a scrub-bar drag, which is worse.
*/
void(float dt) HUD_UpdateTurn =
{
	local float yaw, d, i, slot, old_t, old_p, old_n, span, net, interval;
	local vector ang;

	// fteqcc cannot swizzle a call's return value -- it needs a real lvalue.
	ang = getproperty(VF_ANGLES);
	yaw = ang_y;

	d = yaw - ui_lastyaw;
	while (d >  180) d -= 360;          // yaw wraps; the delta must not
	while (d < -180) d += 360;
	ui_lastyaw = yaw;

	if (dt <= 0)
		return;

	ui_yawpath = ui_yawpath + fabs(d);
	ui_yawnet  = ui_yawnet + d;

	// Spaced by time, not by frame -- see the note on TWIN.  The running totals
	// above still accumulate EVERY frame, so nothing is lost by storing fewer
	// checkpoints; the window just gets a coarser floor on its own length.
	interval = ui_cv_smooth / (TWIN - 1);

	if (!ui_thist_len || board_now - ui_thist_lastt >= interval || board_now < ui_thist_lastt)
	{
		ui_thist_p[ui_thist_head] = ui_yawpath;
		ui_thist_n[ui_thist_head] = ui_yawnet;
		ui_thist_t[ui_thist_head] = board_now;
		ui_thist_lastt = board_now;
		ui_thist_head = ui_thist_head + 1;
		if (ui_thist_head >= TWIN)
			ui_thist_head = 0;
		if (ui_thist_len < TWIN)
			ui_thist_len = ui_thist_len + 1;
	}

	// Walk back for the newest sample already older than the window.  As with
	// the energy ring, the recent end is the live running total.
	old_t = board_now;  old_p = ui_yawpath;  old_n = ui_yawnet;
	for (i = 0; i < ui_thist_len; i = i + 1)
	{
		slot = ui_thist_head - 1 - i;
		while (slot < 0)
			slot = slot + TWIN;
		old_t = ui_thist_t[slot];
		old_p = ui_thist_p[slot];
		old_n = ui_thist_n[slot];
		if (board_now - old_t >= ui_cv_smooth)
			break;
	}

	span = board_now - old_t;
	if (span <= 0.0001)
		return;                         // one frame's worth; keep the last answer

	ui_turnrate = (ui_yawpath - old_p) / span;
	net         = (ui_yawnet - old_n) / span;

	/*
	  Source measures yaw as atan2(y,x), so a POSITIVE rate is turning LEFT and
	  the bar's "turning right" is a negative yaw rate.

	  Only adopt a direction when the window says the turn was coherent -- at
	  least three quarters of the distance travelled went one way.  Below that
	  you were wobbling, and the last committed direction is the better answer.
	*/
	if (ui_turnrate > 5 && fabs(net) > ui_turnrate * 0.75)
		ui_turnsign = (net < 0) ? 1 : -1;   // +1 = right, -1 = left
	if (!ui_turnsign)
		ui_turnsign = 1;
};

// The horizontal wishdir, rebuilt the way AirMove builds it: forward and
// right flattened to the horizontal plane BEFORE being normalised, which is
// why looking up a ramp does not change where you accelerate.
/*
  BUILD 40: WHY THIS NOW ASKS THE ENGINE INSTEAD OF READING THE GLOBAL.

  input_movevalues is not, at draw time, what its name suggests.  The engine
  republishes it on EVERY rendered frame from cl_pendingcmd -- the usercmd
  currently being ACCUMULATED, not the last one sent (CSQC_ChangeLocalPlayer,
  pr_csqc.c:159-172, which CSQC_DrawView calls immediately before running
  CSQC_UpdateView, pr_csqc.c:8951-8973).  And Host_Frame runs CL_SendCmd BEFORE
  the screen update (cl_main.c:7575 against :7661), while every full send ends
  in CL_ClearPendingCommands -- which memsets forwardmove, sidemove and upmove
  to ZERO (cl_input.c:1346-1358, called from :2780).

  So every rendered frame that happened to follow a send read '0 0 0' with the
  key still physically held.  The duty cycle is cl_netfps/framerate: about one
  frame in five at the shipped 66.6667/340, and approaching EVERY frame as the
  frame rate falls toward the send rate.  That is the whole of "it says no
  strafe key but I definitely am pressing a strafe key" -- a message strobing
  at 20%, drawn at half the alpha of the numbers it was replacing, which is
  also why it read as a faint ghost OVER them rather than instead of them.

  cl_keys.qc's header caught the symptom for the key lights ("strobe on a held
  key") and blamed CSQC_Input_Frame's rate.  Right symptom, wrong mechanism:
  anything CSQC_Input_Frame writes is overwritten from cl_pendingcmd before the
  next draw, so the replay-zeroing this function's own comment used to cite
  cannot reach here either.  The rate is the send rate; the value is the clear.

  getinputstate(clientcommandframe) is the engine's own answer and it already
  carries exactly the fallback this needs.  pr_csqc.c:4217-4224 copies the
  pending command to a LOCAL -- so cl_pendingcmd itself is not disturbed -- and
  when that command has been cleared, substitutes the last one actually sent:

      cmd = &cl_pendingcmd[seat];
      tmp = *cmd;  cmd = &tmp;
      if (!cmd->msec)
          *cmd = cl.outframes[(f-1)&UPDATE_MASK].cmd[seat];

  clientcommandframe is current at draw time (pr_csqc.c:8951), so one call is
  the entire fix.  It returns FALSE while paused (:4207) and then leaves the
  globals untouched, which the keyboard fallback below covers.

  WHY NOT SIMPLY READ THE KEYBOARD, the way the key block does.  Keys_Held is
  exact for keys and blind to everything else: a gamepad stick, a joystick,
  in_xflip, cl_forwardspeed, and the prestrafe W-release this mod performs in
  CSQC_Input_Frame.  The engine's resolved move values are the right primary
  source; the keyboard is the fallback for frames the engine has nothing to
  give, and it fires only when BOTH axes are empty so nothing analog is ever
  overridden by a boolean.
*/
vector() HUD_WishDir =
{
	local vector fwd, rgt, wish;
	local float fore, side, trace;
	local string keys;

	/*
	  BUILD 24: a replay has already built it, from the .rec's usercmd columns
	  against the .rec's own yaw -- see Watch_Sample.  It cannot be built here:
	  a replay is drawing a recorded player and the live input is the wrong
	  question, whatever it currently reads.
	*/
	if (rec_wt_on)
		return rec_wt_wish;

	getinputstate(clientcommandframe);

	fore = input_movevalues_x;
	side = input_movevalues_y;

	// Published before the fallback can hide it -- this is the number the whole
	// diagnosis rests on.  See the ui_wish_* declarations.
	ui_wish_raw = [fore, side, 0];
	ui_wish_kb  = FALSE;

	/*
	  Magnitudes are nominal because only the DIRECTION survives the normalise
	  below.  The sign convention is CL_BaseMove's: sidemove is right MINUS left
	  (cl_input.c:1479), forward is forward minus back.

	  NOT WHILE A GHOST IS UP.  Ghost_InputFrame sends a deliberately EMPTY
	  usercmd so the body keeps its momentum and takes no steering, and it
	  writes that zero into the outgoing command -- which is the very command
	  getinputstate substitutes.  So a zero read is the TRUTH there, and the
	  keyboard would be reporting a wish the body is not being given.  The
	  keys are still going somewhere, but they are flying the camera.

	  AND NOT +forward WHILE PRESTRAFE HAS IT.  run_prestrafe drops +forward for
	  you on a pre-strafe jump, so the key is down and the game is not sending
	  it -- the same reason the key block draws W released rather than lit.
	*/
	if (!fore && !side && !rec_gh_on)
	{
		fore = (Keys_Held(FSK_FWD)   ? 1 : 0) - (Keys_Held(FSK_BACK) ? 1 : 0);
		side = (Keys_Held(FSK_RIGHT) ? 1 : 0) - (Keys_Held(FSK_LEFT) ? 1 : 0);
		if (run_ps_release && fore > 0)
			fore = 0;
		ui_wish_kb = (fore || side);
	}

	/*
	  BUILD 40: hud_wishtrace <N> dumps the next N frames of this to the console
	  and counts itself down.

	  The `wish` row says the same thing, but a HUD row is only as readable as
	  what is behind it -- on surf_aesthetic's white floor and blue sky the value
	  column is washed out in a screenshot, which is no way to prove a claim
	  about one frame in five.  This reaches the log, where it can be counted.

	  A cvar rather than a command so a testrun cfg can arm it, and self-clearing
	  so it cannot be left on: at 340 fps an unbounded version would write tens
	  of thousands of lines a minute.  Same shape as zone_debug, for the same
	  reason.
	*/
	trace = cvar("hud_wishtrace");
	if (trace > 0)
	{
		cvar_set("hud_wishtrace", ftos(trace - 1));
		// The key state as a four-character word rather than four floats:
		// QC's sprintf takes at most eight parameters INCLUDING the format,
		// and it is easier to scan a column of `-a--` than of `0 0 1 0`.
		keys = strcat(Keys_Held(FSK_FWD)   ? "w" : "-",
		              Keys_Held(FSK_BACK)  ? "s" : "-",
		              Keys_Held(FSK_LEFT)  ? "a" : "-",
		              Keys_Held(FSK_RIGHT) ? "d" : "-");
		print(sprintf("wish cmd %g: raw %.0f/%.0f  kb %g  keys %s\n",
		              clientcommandframe, fore, side, ui_wish_kb, keys));
	}

	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;  fwd_z = 0;
	rgt = v_right;    rgt_z = 0;
	if (vlen(fwd) > 0.001) fwd = normalize(fwd);
	if (vlen(rgt) > 0.001) rgt = normalize(rgt);

	wish = fwd * fore + rgt * side;
	wish_z = 0;
	if (vlen(wish) < 0.001)
	{
		ui_wish_dir = '0 0 0';
		return '0 0 0';
	}
	ui_wish_dir = normalize(wish);
	return ui_wish_dir;
};

/*
===========================================================================
  Entry point, called from CSQC_UpdateView after renderscene().
===========================================================================
*/
void(vector scr) HUD_Draw =
{
	local vector vel, gnorm, org, wishdir;
	local float onground, mtype, dt, e, gravity;

	HUD_ReadCvars();
	Font_Check();

	/*
	  BUILD 31.  Two frame-level jobs, both of which have to happen before any
	  panel draws and neither of which belongs to a panel.

	  The registry is emptied HERE, and not in the editor that consumes it,
	  because the editor is drawn LAST -- after Timer_Draw, SaveLoc_Draw and
	  Gfx_Draw have each added their own rect.  Clearing it there would clear the
	  list a frame after it was filled and the editor would always be one frame
	  behind the layout it is editing.  Emptied unconditionally rather than under
	  ui_he_open so a stale list cannot survive the editor being closed.

	  The latch decides, once, whether the four live numbers may re-sample this
	  frame; every reader below tests ui_hl_tick rather than asking again, so they
	  cannot disagree about which frame it was.
	*/
	hude_n = 0;
	HUD_UpdateLatch();

	// Build 47.  AFTER the latch, so a traced frame reports the same numbers the
	// rows on screen are about to; and here rather than inside HUD_UpdateLatch
	// because that function is defined above HUD_LiveVel and QC has no forward
	// declaration.  Costs one cvar read per frame when off.
	HUD_VelTrace();

	dt = cltime - ui_lasttime;
	if (dt < 0 || dt > 0.5)             // first frame, or a hitch/loading pause
		dt = 0;
	ui_lasttime = cltime;

	/*
	  BUILD 24 -- THE HUD'S FRAME CLOCK, AND WHY IT IS NOT ALWAYS cltime.

	  Everything on this HUD that fades, averages or differentiates does it over
	  time: the turn-rate window, the ideal-angle low pass, the board panel's
	  three-second fade, the segment machine's per-frame ceiling integral.  Live,
	  that time is cltime and always was.

	  During a replay it has to be the RECORDING's clock instead, or every one of
	  those is multiplied by the playback speed.  At 4x a 300 deg/s strafe reads
	  1200 and grades as a catastrophe; at 0.1x the board panel never clears.  The
	  numerators are already in the run's frame -- the camera is the recorded
	  camera -- so only the denominator was wrong.

	  ONE global, set once, here, before anything reads it.  It is declared in
	  cl_board.qc because that file compiles first and its segment machine is the
	  other consumer; Board_Frame re-asserts it, to the same value, so a caller
	  that reaches it by some other route is still right.

	  dt is scaled by the same factor.  rec_wt_rate is 1 when nothing is playing.
	*/
	if (rec_wt_on)
	{
		board_now = rec_wt_time;
		dt = dt * rec_wt_rate;
	}
	else
		board_now = cltime;

	/*
	  BUILD 24: one question at the top, and the whole panel stack below it is
	  unchanged.  When a replay is being drawn the four quantities every panel
	  is built out of come from the recording instead of from the stats -- see
	  the override block in cl_keys.qc for why it is done this way round.

	  rec_wt_org is already FEET.  The live branch has to subtract the eye offset
	  because VF_ORIGIN is the camera; the .rec stores the entity origin, which
	  IS the feet, so subtracting again would sink every replayed energy reading
	  by 22 units and nothing on screen would say so.
	*/
	if (rec_wt_on)
	{
		vel      = rec_wt_vel;
		org      = rec_wt_org;
		gnorm    = rec_wt_gnorm;
		onground = rec_wt_onground;
		mtype    = MOVETYPE_WALK;

		// A recording is never parked.  Cleared rather than left alone because a
		// replay opened while holding a save would otherwise keep the flag set
		// for the whole playback -- the server pin releases the hold, but this
		// branch never reads the stat that would say so.
		rec_sl_held = FALSE;
	}
	else
	{
		/*
		  BUILD 30: WHAT THE SAVE IS HOLDING, NOT THE ZERO THE FREEZE WROTE.

		  A save-lock hold parks the player with MOVETYPE_NONE and .velocity
		  '0 0 0' (SV_SaveLocHold, and re-zeroed every tick by
		  SV_SaveLocHoldFrame), so for as long as the load key is down the stat
		  above reads zero.  Read straight, that made the speedometer print 0 and
		  collapsed `e` to bare height -- because Strafe_Energy's |v|^2/2g term
		  vanishes with it, which is not a stale reading but a different quantity.

		  The server publishes the parked velocity alongside the zero precisely so
		  this branch can exist.  One substitution, at the single point every panel
		  takes its velocity from, so the speedometer, the energy readout, the
		  strafe bar, HUD_SplitSample and Board_Frame all agree on the press
		  without any of them knowing a hold is a thing.

		  ui_prev_speed needs no special case either: it tracks whatever this
		  produces, so it holds the parked speed through the hold and the frame
		  after release compares like with like instead of flashing a 1200-0 gain.
		*/
		// BUILD 39: the substitution itself now lives in HUD_LiveVel, called
		// below, so the split list gets it too without a second copy.  The flag
		// is still read here because half the panels below test it directly.
		rec_sl_held = getstatf(STAT_FS_HOLD);

		/*
		  BUILD 39: ONE CLOCK.  See HUD_Feet, which carries what these two lines
		  used to be and why the subtraction they performed did not cancel.

		  The ghost case that build 30 put here has moved in there with them: a
		  ghost overrides VF_ORIGIN with a flying camera, this runs after that
		  override, and read straight every panel below would compute your speed,
		  your energy and your anchor from wherever the camera happens to be.
		  Fly upward and `e` would climb with it.
		*/
		org = HUD_Feet();       // FIRST: it decides the source for both
		vel = HUD_LiveVel();

		/*
		  BUILD 39: THE PREDICTED GROUND FLAG, matched to the pair above it.

		  STAT_FS_FLAGS is the server's, one snapshot old, and HUD_UpdateJumpRef
		  latches ui_jump_z on its rising edge against an origin that was already
		  predicted forward -- so the reference the whole `e` readout is measured
		  from was taken from two different instants.  Its own essay admits to
		  four units of this and only fixed one frame of it.

		  STAT_FS_FLAGS is still read for everything else it carries.

		  BUILD 40 -- AND NOT WHILE PARKED.  pv->onground is assigned only
		  INSIDE CL_PredictMove's prediction branch (cl_pred.c:1387), and a
		  save-lock hold is MOVETYPE_NONE, which is exactly what turns that
		  branch off.  So for the whole duration of a park pmove_onground is
		  frozen at whatever prediction last computed -- typically "airborne",
		  because you pressed the key mid-flight -- while the server has you
		  standing on the saved spot.  HUD_UpdateJumpRef latches ui_jump_z off
		  this flag, and ui_jump_z is the reference the entire `e` readout is
		  measured from, so a stuck flag there moves every energy number on the
		  screen by an anchor rather than by a sample.  The stat is the server's
		  and the server is the only one simulating you right now, so while the
		  hold is up the stat IS the fresher answer.
		*/
		onground = getstatf(STAT_FS_FLAGS) & FL_ONGROUND;
		if (ui_src_pred && !rec_sl_held)
			onground = pmove_onground;

		mtype    = getstatf(STAT_FS_MOVETYPE);

		gnorm_x = getstatf(STAT_FS_GROUNDNORM + 0);
		gnorm_y = getstatf(STAT_FS_GROUNDNORM + 1);
		gnorm_z = getstatf(STAT_FS_GROUNDNORM + 2);
	}

	HUD_UpdateTurn(dt);
	HUD_UpdateAnchor(org);
	HUD_UpdateJumpRef(org, vel, onground);

	/*
	  Needs the origin and velocity now: as well as the two ramp edges it has
	  always watched, it tracks the ENERGY across each ramp ride and each air
	  time, which is what the gain readout is measuring.  onground closes a
	  segment without reporting it.

	  BUILD 24: STILL NOT DURING A REPLAY, but for a different reason than before.

	  It used to be a refusal -- the .rec carried no ramp contact and no pre-clip
	  velocity, so there was nothing honest to feed this with.  v4 records both,
	  and the column is drawn now.  What has NOT changed is that this machine must
	  not be run live from the file: it is an accumulator, a scrub runs its clock
	  backwards, and the jump back to your own body when the replay ends would
	  close a segment with a map-sized energy delta and put that row on the
	  player's own column.

	  So the replay's column is built ONCE, at load, by Watch_BuildSeq -- which
	  calls this same function with the same state, brackets itself in a snapshot
	  of the live list, and puts it back on stop.  Watch_SeqApply then fills the
	  ring from that table for whichever tick the clock is on, which is what makes
	  a backwards scrub free.  One implementation, two drivers.

	  The energy-rate chain below it stays skipped outright: ui_eta is a dE/dt
	  over a two-second wall-clock window and is debug-only, and feeding it a
	  scrubbed clock would produce a number nobody could interpret.
	*/
	if (!rec_wt_on)
	{
		Board_Frame(org, vel, onground);

		// Feed the energy history even when the readout is hidden, so turning it
		// on does not then need two seconds before it says anything.
		gravity = serverkeyfloat("sv_gravity");
		if (gravity < 1) gravity = 800;
		e = Strafe_Energy(org, vel, gravity);

		/*
		  BUILD 30: BUT NOT WHILE PARKED.

		  dE/dt over a wall-clock window is a rate of doing something, and a
		  frozen player is not doing anything -- park for two seconds and every
		  sample in the window is the same energy at a stationary origin, so the
		  rate reads a flat zero and HUD_QualityColor paints it red.  Worse, the
		  samples SURVIVE the hold: the window still spans them after release, so
		  the first two seconds of the section you parked to practise are
		  differenced against a stretch of time that had no movement in it.

		  Skipping the push leaves the ring holding the approach you actually
		  flew, which is the measurement the readout is for.  ui_eta is left at
		  its last live value for the same reason -- it is a debug readout and a
		  held number is more honest than a manufactured zero.
		*/
		if (!rec_sl_held)
		{
			local float rate, ceiling, aircap;
			aircap  = serverkeyfloat("pm_maxairspeed");  if (aircap <= 0) aircap = 30;
			rate    = HUD_EnergyRate(e, cltime, ui_cv_window);
			ceiling = Strafe_PowerCeiling(aircap, gravity, PM_TICK);
			ui_eta  = (ceiling > 0.0001) ? (rate / ceiling) : 0;
		}
	}

	wishdir = HUD_WishDir();

	if (ui_cv_speed)  HUD_DrawSpeed(scr, vel, org);

	/*
	  STRAFE BEFORE BOARD, and it is not a preference.  The board panel stacks
	  under the bar and takes its y from ui_strafe_bottom, which HUD_DrawStrafe
	  publishes -- so drawing the board first would lay it out against last
	  frame's bar.  Seeded here as well, for the frames where the bar does not
	  run at all (hud_strafe 0, or noclip).
	*/
	ui_strafe_bottom = scr_y * ui_cv_strafepos_y + 23 * ui_cv_scale;

	/*
	  BUILD 24, AND THE PANEL STACK IS NOW THE SAME ONE IN BOTH DIRECTIONS.

	  Build 23 returned here, drawing only the key block and the debug list,
	  because the strafe bar, the board panel and the segment column needed board
	  telemetry the .rec did not carry.  v4 carries it, so the early return is
	  gone and there is one draw path again -- which was the point of the override
	  block in the first place.

	  ONE EXCEPTION REMAINS, and it is a v3 file.  Every recording made before
	  this build has no ramp contact and no pre-clip velocity; rec_wt_v4 is false
	  for those and the three panels stay off, exactly as they did in build 23,
	  with Watch_Open having said so in the console.  Drawing them from zeros
	  would produce a bar graded against a plane that is not there.
	*/
	// Build 34: what map this is, BEFORE the v3-replay early-out below -- it reads
	// serverinfo and the zone table, neither of which is part of the strafe/board
	// chain that early-out exists to protect.
	if (ui_cv_mapinfo)
		HUD_DrawMapInfo(scr);

	// BEFORE the v3-replay early-out below, for the same reason the map info is:
	// it reads cvars and serverinfo, not the strafe/board telemetry that early-out
	// exists to protect.  It has its own rec_wt_on guard.
	HUD_DrawSubmitWarn(scr);

	if (rec_wt_on && !rec_wt_v4)
	{
		if (ui_cv_keys)  HUD_DrawKeys(scr);
		if (ui_cv_debug) HUD_DrawDebug(scr, vel, onground, gnorm, mtype);
		return;
	}

	if (ui_cv_strafe && mtype != MOVETYPE_NOCLIP)
		HUD_DrawStrafe(scr, vlen([vel_x, vel_y, 0]), onground, gnorm, wishdir, vel, dt);
	if (ui_cv_board)  HUD_DrawBoard(scr, ui_strafe_bottom);
	if (ui_cv_keys)   HUD_DrawKeys(scr);
	if (ui_cv_debug)  HUD_DrawDebug(scr, vel, onground, gnorm, mtype);
	if (cvar("hud_seq")) HUD_DrawSeq(scr);
};
