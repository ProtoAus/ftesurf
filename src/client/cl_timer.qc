/*
===========================================================================
  cl_timer.qc -- the run timer, drawn.

  This file owns NO state that matters.  Everything on screen comes out of
  eleven stats the server writes (sv_timer.qc, SV_RegisterStats), which is
  deliberate: a HUD that computed the time from its own view of the zones
  would sometimes disagree with the server about whether you had crossed the
  line, and a timer you cannot trust is worse than no timer at all.

  What IS local is two things, and both are presentation:

    * the split flash.  A split is a single stat change; how long its +/-
      stays on screen is a taste, and taste belongs on this side.
    * the "running" tick.  STAT_FS_TIMERTICKS arrives once per snapshot,
      which at 66.7 Hz updates against a 300 fps display -- so between
      snapshots the milliseconds would visibly stutter.  The digits are
      EXTRAPOLATED from the last stat and its arrival time, and snap back
      to the server's number every time one lands.  The last three digits
      of a running timer are decoration; the moment it stops they are the
      server's exact tick count again.
===========================================================================
*/

float  ui_tm_cv, ui_tm_x, ui_tm_y, ui_tm_splittime;

// Split flash.
float  ui_tm_lastseg;
float  ui_tm_splitat;           // cltime the last split landed; 0 = none

/*
  BUILD 43 -- THE STAGE RESET FLASH.

  A stage fail moves the clock a stage is being timed from and nothing else on
  screen changes: the big number keeps counting, because the RUN clock is
  deliberately not touched.  So without a word here the one thing that just
  happened is the one thing you cannot see, and you would go on running a stage
  whose split has silently gone back to zero.

  It is a FLASH and not a split row.  Timer_SplitsPush appends to the list down
  the left, and that list only ever holds segments that were COMPLETED -- a
  failed attempt is the opposite of one, and putting it there would make the
  column disagree with the file it is supposed to describe.  The flash reuses
  ui_tm_splittime, so one cvar still governs how long an event stays up.

  ui_tm_lastfails is seeded to -1 rather than 0 so the first snapshot after a
  connect is a SEED and not an event: the stat legitimately reads 0 there, and
  an edge test of "different from" would flash `stage 1 reset` at anyone who
  joins.  The test below is "greater than", which is also what makes the reset to
  zero at a genuine boundary silent -- a counter going backwards is not an event.
*/
float  ui_tm_lastfails;         // last STAT_FS_STAGEFAILS seen; -1 = seeding
float  ui_tm_failat;            // cltime the reset landed; 0 = none
float  ui_tm_failseg;           // the stage it was, for the text

// Extrapolation.
float  ui_tm_lastticks;         // the last DIFFERENT value the stat carried
float  ui_tm_lastat;            // cltime it changed
float  ui_tm_laststate;

/*
===========================================================================
  THE SPLIT LIST, down the left.

  NO SERVER CHANGE AND NO NEW PROTOCOL, which is worth saying because the
  obvious implementation is a new network message carrying the whole table.
  It is not needed: a split IS the segment stat changing, and the run time and
  the delta at that instant are already two of the eleven stats arriving every
  snapshot.  Watching the edge that this file ALREADY watches for the split
  flash, and keeping what it saw, is the entire feature.

  Rows are (stage, cumulative ticks, delta vs the pb split).  The stage a row
  is labelled with is the one that ENDED: crossing into segment N completes
  stage N, which is why the row says N and the panel above says N+1 for the
  stage you are now on.

  Cleared by a NEW RUN, not by finishing one -- so the board is still there
  while you walk back and read it -- and it goes out over a second rather than
  vanishing, for the same reason the sequence column does.
===========================================================================
*/
#define SP_MAX   32
#define SP_FADE  1.0

/*
  BUILD 19: three kinds of row, not two.

  Checkpoints join stages and the finish.  They arrive on their own stat triple
  (STAT_FS_TIMERCP / CPT / CPD) rather than on the segment stat, because a
  checkpoint does not end a segment -- on a linear map like surf_utopia there is
  only ever one segment and every gate lives inside it.  An explicit kind is
  clearer than overloading ui_sp_seg's -1 sentinel a second time, and it is what
  lets the row label itself.
*/
#define SPK_STAGE  0
#define SPK_CP     1
#define SPK_FINISH 2

float ui_sp_kind[SP_MAX];       // SPK_*
float ui_sp_seg[SP_MAX];        // the stage or checkpoint number; unused on finish
float ui_sp_ticks[SP_MAX];
float ui_sp_delta[SP_MAX];
/*
  What you were carrying as you crossed.  Build 19.

  Sampled by the CLIENT at the moment it sees the edge -- see HUD_SplitSample for
  why the energy in particular cannot come from the server.  Both are the numbers
  already on screen: the speedometer's horizontal speed and the `e` readout.

  Taken at the CROSSING and not afterwards, which is what makes them useful on
  both kinds of stage.  A map that teleports you to the stage end reads what you
  arrived with; a map that lets you surf straight through reads what you carried
  out of it, which is the whole reason you asked for them.
*/
float ui_sp_speed[SP_MAX];
float ui_sp_energy[SP_MAX];
float ui_sp_n;
float ui_sp_fadeat;             // cltime the clearing run started; 0 = not fading

// The checkpoint ordinal last seen, so the edge can be detected the same way the
// segment edge is.  Reset by a map change and by a new run.
float ui_tm_lastcp;

/*
  A SECOND state latch, and not a duplicate of ui_tm_laststate.

  That one is updated inside the extrapolation edge, which also fires whenever
  the tick count changes -- so by the time anything else looks at it, it has
  already been caught up and the state transition is gone.  This one is touched
  only here.
*/
float ui_tm_lastdrawstate;

// A map change clears the list outright -- its rows describe a map you are no
// longer on.  Watched here rather than hooked from HUD_UpdateAnchor's map-change
// block (which is where Board_Clear is called from) because cl_hud.qc compiles
// first and would need this forward-declared to reach it; one string compare a
// frame is cheaper than that coupling.
string ui_tm_map;

void() Timer_SplitsClear =
{
	ui_sp_n = 0;
	ui_sp_fadeat = 0;
};

/*
  BUILD 24 split this in two, and the seam is where the speed and energy come
  from.

  The live path samples them HERE, deliberately, so that every row -- stage,
  checkpoint and finish -- gets the same number taken the same way and no caller
  can forget to.  A replay cannot use that: it rebuilds the whole list at once
  when you scrub backwards, and HUD_SplitSample would then stamp every row with
  the speed at the seek target rather than the speed at its own split.  Twelve
  rows all reading 1204 u/s, which is a lie the row format cannot express as one.

  So the replay computes each row's pair from the .rec at that row's own tick and
  passes them in, and the live caller keeps the property that made sampling here
  right in the first place.
*/
void(float kind, float seg, float ticks, float delta,
     float speed, float energy) Timer_SplitsPushAt =
{
	local float i;

	if (ui_sp_fadeat > 0)
		Timer_SplitsClear();

	if (ui_sp_n >= SP_MAX)
	{
		for (i = 0; i < SP_MAX - 1; i = i + 1)
		{
			ui_sp_kind[i]   = ui_sp_kind[i + 1];
			ui_sp_seg[i]    = ui_sp_seg[i + 1];
			ui_sp_ticks[i]  = ui_sp_ticks[i + 1];
			ui_sp_delta[i]  = ui_sp_delta[i + 1];
			ui_sp_speed[i]  = ui_sp_speed[i + 1];
			ui_sp_energy[i] = ui_sp_energy[i + 1];
		}
		ui_sp_n = SP_MAX - 1;
	}

	ui_sp_kind[ui_sp_n]   = kind;
	ui_sp_seg[ui_sp_n]    = seg;
	ui_sp_ticks[ui_sp_n]  = ticks;
	ui_sp_delta[ui_sp_n]  = delta;
	ui_sp_speed[ui_sp_n]  = speed;
	ui_sp_energy[ui_sp_n] = energy;
	ui_sp_n = ui_sp_n + 1;
};

void(float kind, float seg, float ticks, float delta) Timer_SplitsPush =
{
	local vector s;
	s = HUD_SplitSample();
	Timer_SplitsPushAt(kind, seg, ticks, delta, s_x, s_y);
};

void() Timer_RegisterCvars =
{
	registercvar("hud_timer",   "1", CVAR_ARCHIVE);
	registercvar("hud_timer_x", "0.5", CVAR_ARCHIVE);
	registercvar("hud_timer_y", "0.035", CVAR_ARCHIVE);

	// Seconds a stage split stays up.  Four is about as long as a stage
	// transition takes to stop mattering.
	registercvar("hud_timer_split", "4");

	// Smooth the last three digits between snapshots.  0 shows the server's
	// number verbatim, which is exact and visibly steps at 66.7 Hz.
	registercvar("hud_timer_smooth", "1");

	/*
	  The split list, upper left.

	  BUILD 21 MOVED IT OFF THE SEQ COLUMN, and the collision was arithmetic
	  rather than taste.  At the default hud_scale 2 on a 1920 screen the block
	  ran from x=35 to x=530 -- five columns, the last of them starting 456 px in
	  -- while HUD_DrawSeq is right-aligned on x=480 and grows LEFTWARD from
	  there.  Both were centred on y 0.5.  So the energy rows did not merely
	  touch the split rows, they were drawn inside them.

	  0.20 clears it vertically for good, and it clears what is already down the
	  left as well: the debug block tops out at 0.30 and the save-lock list at
	  0.34, both TOP-anchored and growing down, so anything living above 0.30 has
	  the column to itself.  Still centred on the anchor rather than hung from
	  it, for build 13's reason -- the list grows a row per gate, and a
	  top-anchored block would walk down the screen into those two as the run
	  went on.  A block would have to reach ~10 rows before its top edge left the
	  screen, and 4 is a busy map.

	  0.045 rather than 0.018 is the "not the corner" half: at 1920 that is 86 px
	  of inset instead of 35, which reads as a block placed in the upper left
	  rather than one pushed against the frame.
	*/
	registercvar("hud_splits",   "1", CVAR_ARCHIVE);
	registercvar("hud_splits_x", "0.045", CVAR_ARCHIVE);	// build 21, was 0.018 (hard against the edge)
	registercvar("hud_splits_y", "0.20", CVAR_ARCHIVE);	// build 21, was 0.5; the block is CENTRED on this

	// Build 19: the speed and energy you crossed each gate with.  0 puts the
	// block back to three columns, which is the pre-19 width.
	registercvar("hud_splits_speed", "1", CVAR_ARCHIVE);
};

float() Timer_Tick =
{
	local float t;
	t = serverkeyfloat("pm_ticrate");
	if (t <= 0)
		t = PM_TICK;
	return t;
};

/*
  The displayed tick count.

  While running, the stat is up to one snapshot stale, so add the time since
  it arrived.  Clamped to two snapshots' worth: a hitch or a pause must not
  let the readout run away from the server, and coming back to a number that
  jumps BACKWARDS is worse than one that briefly stops.
*/
float(float state, float ticks, float tick, float flags) Timer_Display =
{
	local float age;

	/*
	  A STOPPED CLOCK MUST NOT BE EXTRAPOLATED, and the failure without this is
	  not the obvious one.  The readout does not keep counting -- it parks at
	  ticks+6 and sits there, because the edge detector below only restamps
	  ui_tm_lastat when `ticks` CHANGES, and while frozen it never does.  The
	  age then saturates at the 0.1s clamp, which at a 0.015 tick is six.  So
	  the symptom of getting this wrong is a constant six-tick overshoot that
	  snaps away on release, not a running timer.
	*/
	if (flags & TF_FROZEN)
		return ticks;

	if (state != TS_RUNNING || !cvar("hud_timer_smooth") || tick <= 0)
		return ticks;

	age = cltime - ui_tm_lastat;
	if (age < 0)   age = 0;
	if (age > 0.1) age = 0.1;

	return ticks + floor(age / tick);
};

/*
  Shadow is tested BEFORE practice everywhere below, because TF_SHADOW implies
  TF_PRACTICE and the more specific answer is the useful one: yellow says "this
  will not be kept", cyan says "this clock came out of a save".  The label under
  the timer uses the same two colours for the same two words.
*/
#define TC_SHADOW   '0.45 0.85 1.00'
#define TC_PRACTICE '1.00 0.82 0.20'
/*
  BUILD 44.  A cheated run gets its own colour and it is the leaderboard's
  SBC_BAD, so the clock you are looking at and the row it will become are the
  same red.  Ranked ABOVE shadow below, because a run that both loaded a save and
  noclipped carries both bits and cyan is the gentler answer -- the same
  precedence FS_RunClass spells out, applied to a colour instead of a word.
*/
#define TC_CHEAT    '0.95 0.45 0.40'
/*
  A CLOCK THAT IS NOT MOVING.  Build 19.

  Ranked ABOVE practice and shadow, and that ordering is the point rather than a
  detail: "this number is not counting" is a more urgent fact about a readout
  than "this run would not have been kept", and a stopped clock that still looks
  live is exactly the thing a player reports as a bug.  It covers both ways a
  clock stops -- TF_STOPPED, where the run ended and this is where it got to, and
  TF_FROZEN, where a save-lock is holding it.  The two words under the timer keep
  them apart; the colour only says "stopped".
*/
#define TC_STOPPED  '0.55 0.58 0.62'

vector(float state, float ticks, float pb, float flags) Timer_Color =
{
	if (flags & (TF_STOPPED | TF_FROZEN))     return TC_STOPPED;
	if (state == TS_FINISHED)
	{
		if (flags & TF_CHEAT)                 return TC_CHEAT;
		if (flags & TF_SHADOW)                return TC_SHADOW;
		if (flags & TF_PRACTICE)              return TC_PRACTICE;
		if (!(flags & TF_HAVEPB) || ticks <= pb) return '0.45 1.00 0.45';
		return '1.00 0.55 0.45';
	}
	if (state == TS_ARMED)                    return '0.70 0.75 0.80';
	if (flags & TF_CHEAT)                     return TC_CHEAT;
	if (flags & TF_SHADOW)                    return TC_SHADOW;
	if (flags & TF_PRACTICE)                  return TC_PRACTICE;
	if (state == TS_RUNNING)                  return '1 1 1';
	return '0.55 0.58 0.62';
};

/*
  Drawn down the left, in order, complete time last and emphasised.

  The delta is coloured against the personal-best split, which is the only
  comparison that means anything here -- a raw split tells you what the clock
  said, not whether that was good.
*/
void(vector scr, float tick) Timer_DrawSplits =
{
	local float i, sz, big, lh, a, spd, bt;
	local vector p, col, bp;
	local string label;

	if (!cvar("hud_splits") || ui_sp_n <= 0)
		return;

	a = 1;
	if (ui_sp_fadeat > 0)
	{
		a = 1 - (cltime - ui_sp_fadeat) / SP_FADE;
		if (a <= 0)
			return;
	}

	/*
	  BUILD 21: MONOSPACED, AND SMALLER TO PAY FOR IT.

	  Every glyph in ui_font_mono advances exactly 0.6 em, so a column's worst
	  case is a character COUNT rather than a measurement -- which is what makes
	  the offsets below derivable instead of tuned.

	  The sizes are cut because the face is wider, not for effect.  Roboto spends
	  0.562 em on a digit and 0.264 on a '.'; this face charges 0.6 for both, so
	  keeping 9/11 would have made the block bigger while the request was to make
	  it smaller.  7 and 9 land on 14 px and 18 px at hud_scale 2 -- rungs that
	  exist only because the mono ladder steps in twos (sh_font.qc) -- against 16
	  and 20 before.  At hud_scale 1 the dense ladder has nothing below 8, so
	  both fall back to 8 and the size is unchanged there; the offsets still
	  shrink, which is where most of the width was.
	*/
	Font_Set(ui_font_mono);
	sz  = Font_Px(7 * ui_cv_scale);
	big = Font_Px(9 * ui_cv_scale);
	lh  = sz + 3 * ui_cv_scale;

	/*
	  BUILD 13: vertically CENTRED on hud_splits_y rather than starting there.

	  The list grows a row per stage, so a top-anchored block drifts down the
	  screen as the run goes on and sits in a different place on every map --
	  six stages on surf_666, two on a linear one.  Centring it keeps the block
	  put and moves only its ends, which is what "align it to the middle" asks
	  for and is easier to read at a glance mid-run.

	  ui_sp_n+1 rather than ui_sp_n because the finish row takes a few extra
	  pixels of air above it, so the drawn block is one notch taller than the
	  row count.
	*/
	p = [scr_x * cvar("hud_splits_x"),
	     scr_y * cvar("hud_splits_y") - (ui_sp_n + 1) * lh * 0.5, 0];

	// The anchor is the LEFT edge at the block's vertical CENTRE -- the block is
	// centred on hud_splits_y and grows both ways from it, which is the build 13
	// fix and is not recoverable from the drawn box.  Kept before the loop moves p.
	bp = [p_x, scr_y * cvar("hud_splits_y"), 0];
	bt = p_y;

	spd = cvar("hud_splits_speed");

	for (i = 0; i < ui_sp_n; i = i + 1)
	{
		local float fin;
		fin = (ui_sp_kind[i] == SPK_FINISH);

		if (fin)
		{
			label = "finish";
			col   = '0.95 0.97 1.00';
			p_y   = p_y + 3 * ui_cv_scale;   // a little air above the total
		}
		else if (ui_sp_kind[i] == SPK_CP)
		{
			/*
			  Dimmer, and ORANGE, keyed to the colour the checkpoint box is drawn
			  in (ZC_CHECKPOINT, cl_zones.qc) -- so a row matches the gate you flew
			  through, and reads as subordinate to a stage rather than as a
			  differently-named one.  A staged map can show both at once.
			*/
			label = sprintf("cp %g", ui_sp_seg[i]);
			col   = '0.85 0.60 0.30';
		}
		else
		{
			label = sprintf("stage %g", ui_sp_seg[i]);
			col   = '0.70 0.73 0.78';
		}

		/*
		  THE COLUMNS, DERIVED.  Build 21; they were 0 / 52 / 116 / 170 / 228.

		  A monospaced face makes each column's worst case a character count, so
		  these are computed rather than eyeballed.  One character advances
		  0.6 * size, and the offsets are in units of ui_cv_scale, so the advance
		  in those units is 0.6 * (rendered px / ui_cv_scale):

		      hud_scale 1   sz  8 px -> 4.8 units    big  8 px -> 4.8
		      hud_scale 2   sz 14 px -> 4.2 units    big 18 px -> 5.4

		  Each column is sized at whichever scale is worse for it -- 1 for the
		  sz columns, 2 for the big one -- so both are correct from one set:

		      col  content      worst        chars   needs   at
		       0   label        "stage 12"     8      38.4    0
		       1   time (big)   "0:12.345"     8      43.2   38
		       2   delta        "+0:00.087"    9      43.2   84
		       3   speed        "1204 u/s"     8      38.4  130
		       4   energy       "e -312"       6      28.8  172

		  Every column clears the next by 2-3 units, and the block ends at ~201
		  against ~253 before -- a fifth narrower, on top of the smaller glyphs.
		  At hud_scale 2 on 1920 that puts its right edge at 481 px, which is
		  where HUD_DrawSeq's right-aligned anchor sits: the two now ABUT in the
		  worst case instead of overlapping, and in practice never share a row at
		  all because this block lives at y 0.20 and that one at 0.5.

		  The one string that can overrun is an hour-plus run, where
		  Time_TickString grows to "1:02:03.456" and takes 11 characters into a
		  column sized for 8.  That was equally true of the old layout and a
		  surf leg is minutes; it is a note, not a defect to design around.
		*/
		HUD_Text([p_x, p_y], label, sz, col, a * 0.9);
		HUD_Text([p_x + 38 * ui_cv_scale, p_y],
		         Time_TickString(ui_sp_ticks[i], tick),
		         fin ? big : sz, fin ? '1.00 1.00 1.00' : '0.88 0.90 0.94', a);

		if (ui_sp_delta[i] != 0)
			HUD_Text([p_x + 84 * ui_cv_scale, p_y],
			         Time_DeltaString(ui_sp_delta[i], tick), sz,
			         (ui_sp_delta[i] < 0) ? '0.45 1.00 0.45' : '1.00 0.55 0.45', a);

		/*
		  What you were carrying through the gate.  Dimmer than the time, because
		  the time is what the row is FOR and these are context for it -- and
		  quieter still for the energy, which is the one you glance at rather than
		  read.
		*/
		if (spd)
		{
			HUD_Text([p_x + 130 * ui_cv_scale, p_y],
			         sprintf("%d u/s", rint(ui_sp_speed[i])), sz,
			         '0.72 0.78 0.86', a * 0.85);
			HUD_Text([p_x + 172 * ui_cv_scale, p_y],
			         sprintf("e %d", rint(ui_sp_energy[i])), sz,
			         '0.62 0.70 0.82', a * 0.75);
		}

		p_y = p_y + (fin ? (big + 3 * ui_cv_scale) : lh);
	}

	Font_Reset();

	/*
	  Build 31: the box.  201*scale is the block's derived width, not a guess --
	  the column table in the essay above puts the last column at 172 and gives it
	  29 units of worst-case content, and the whole point of the mono face is that
	  those add rather than needing measuring.  Measuring the widest ROW would
	  give a narrower box that changed size as rows arrived, which is worse for a
	  hit target than a stable one that matches the layout's own reasoning.
	*/
	HUD_Rect("splits", [bp_x, bt, 0], [201 * ui_cv_scale, p_y - bt, 0], bp);
};

/*
  The panel itself -- the clock, the line under it and the pb line.

  BUILD 24 split this out of Timer_Draw so a replay can draw the identical panel
  from a file.  Everything it needs is a parameter and nothing in it reads a stat
  or a global that only a live run has, which is the property that makes it
  reusable and the one to preserve if it grows a line.

  `segv` packs seg/segs/track because QuakeC's parameter list stops at eight and
  this was going to be nine.  It returns the running y so the caller can carry on
  down the same column -- the live path draws its split flash there, and a replay
  has no flash to draw.

  BUILD 43: `stv` packs the stage state the same way and for the same reason --
  [fails, SF_* word, 0].  A REPLAY PASSES '0 0 0' AND THAT IS CORRECT, not a
  stub: a .rec carries no stage-arm state, so a replay honestly has nothing to
  say about it, and inventing `attempt 1` from a file that never recorded the
  number would be worse than the line being absent.

  Leaves the UI face selected; the caller calls Font_Reset.
*/
float(vector scr, float state, float ticks, float flags, float pb,
      float tick, vector segv, vector stv) Timer_DrawPanel =
{
	local float big, small, y, disp, seg, segs, track;
	local float bw, tw, bt;
	local vector p, col, bp;
	local string s;

	seg   = segv_x;
	segs  = segv_y;
	track = segv_z;

	ui_tm_x = cvar("hud_timer_x");
	ui_tm_y = cvar("hud_timer_y");
	ui_tm_splittime = cvar("hud_timer_split");
	if (ui_tm_splittime <= 0)
		ui_tm_splittime = 4;

	p = [scr_x * ui_tm_x, scr_y * ui_tm_y, 0];

	/*
	  BUILD 24: OUT FROM UNDER THE PLAYBACK CHROME.

	  hud_timer_y is 0.035, so the clock sits about 38 px down on a 1080p window
	  and the replay bar occupies the top ~70 -- the run clock and the "stage 5/6"
	  line underneath it were being drawn straight through the scrub bar.

	  Pushed down by the chrome's measured bottom rather than by a constant,
	  because that panel's height is derived from the font now and any constant
	  would be wrong again at the next hud_scale.  rec_wt_chromebot is 0 whenever
	  the chrome is not up, so the live HUD is byte-identical.

	  The whole column moves, not just the clock: `y` accumulates downward from
	  here through the sub-label, the pb line and the split flash, so one term
	  here carries all of them.
	*/
	if (rec_wt_chromebot > p_y)
		p_y = rec_wt_chromebot + 8;

	y  = p_y;
	bp = p;                     // the anchor, AFTER the chrome push -- what the
	bt = p_y;                   // editor drags is where the panel really is
	bw = 0;

	disp = Timer_Display(state, ticks, tick, flags);
	col  = Timer_Color(state, ticks, pb, flags);

	/*
	  Font_Px snaps to the CURRENT face's baked ladder, so it has to be asked
	  after Font_Set and not before -- the display and UI faces are baked at
	  different sizes and asking the wrong one gives a size that then gets
	  resampled.  Same reason HUD_Text calls it internally.
	*/
	Font_Set(ui_font_display);
	big = Font_Px(20 * ui_cv_scale);
	s   = Time_TickString(disp, tick);
	bw  = stringwidth(s, TRUE, [big, big]);
	HUD_TextC([p_x, y], s, big, col, 1);
	y = y + big + 2 * ui_cv_scale;

	Font_Set(ui_font_ui);
	small = Font_Px(8 * ui_cv_scale);

	/*
	  The line under the clock, and it answers "what am I timing" -- which is
	  not obvious on a staged map where !s 3 arms a stage run rather than the
	  track.  A linear map (one segment) says nothing at all; there is only
	  one thing it could be.
	*/
	s = "";
	if (track > 0)
		s = sprintf("bonus %g", track);
	if (segs > 1)
	{
		if (state != TS_IDLE && state != TS_FINISHED && seg > 0)
			s = strcat(s, (s != "") ? "  " : "", sprintf("stage %g/%g", seg + 1, segs));
		else if (s == "")
			s = sprintf("%g stages", segs);
	}
	/*
	  BUILD 19: "stopped" replaces "ready", not both.

	  Both are true while a stopped time is on screen -- you are armed AND the
	  number above is the last run's -- but "ready" beside a non-zero clock reads
	  as a clock that is about to keep going from there, which is exactly the
	  wrong thing to suggest.  The time you are looking at is over; say so.
	*/
	if (flags & TF_STOPPED)
		s = strcat(s, (s != "") ? "  " : "", "^9stopped^7");
	else if (state == TS_ARMED)
		s = strcat(s, (s != "") ? "  " : "", "ready");
	/*
	  ONE WORD FOR WHY THIS RUN IS NOT CLEAN, never two.

	  A run can carry three of these bits at once and every one of them means
	  "this will not be kept" to a reader, so drawing them together says the same
	  thing three times and buries the specific answer in the middle.  The most
	  specific one wins.

	  THE ORDER IS FS_RunClass's, WITH SHADOW SPLICED IN, and the splice is the
	  only thing here that is not simply the shared rule:

	    cheated   the run's physics were not the ruleset's -- red, matching the
	              board row it becomes
	    shadow    strictly narrower than segmented: the CLOCK came out of the save
	              too, so the number above you is not a time you ran from the
	              start.  Drawn instead of `segmented` because it is the more
	              specific claim about the same gesture, which is exactly the
	              argument build 17 made for it against `practice`.
	    segmented a save state was used and the clock is your own
	    practice   the residual -- today that is a hopped start and nothing else

	  Colours: red and amber for the taints, cyan for shadow, which this file has
	  used for it since build 17 and which `armed`, `held` and `ghost` share --
	  cyan is a mode on this line, amber is a verdict.
	*/
	if (flags & TF_CHEAT)
		s = strcat(s, (s != "") ? "  " : "", "^1cheated^7");
	else if (flags & TF_SHADOW)
		s = strcat(s, (s != "") ? "  " : "", "^5shadow^7");
	else if (flags & TF_SEGMENT)
		s = strcat(s, (s != "") ? "  " : "", "^3segmented^7");
	else if (flags & TF_PRACTICE)
		s = strcat(s, (s != "") ? "  " : "", "^3practice^7");

	/*
	  BUILD 43 -- THE STAGE, AND IT IS DELIBERATELY TWO DIFFERENT WORDS.

	  `armed` says the stage clock has not started yet: you crossed the boundary,
	  you are standing in its box, and the split begins when you leave.  It is
	  shown because the arm rule is otherwise invisible and its whole effect is on
	  a number that has not started moving -- "why is my stage split zero" has
	  exactly one answer and this is it.

	  `attempt N` counts from the fail counter and is the answer to "am I still on
	  the run I think I am".  N is fails + 1 because the first attempt is attempt
	  one, not attempt zero.

	  RUNNING-gated, unlike the words above: an armed or finished player has no
	  stage in progress and a stale `attempt 4` beside a finished time would read
	  as a fact about the run that was just completed.

	  ^3 amber for the attempt count, matching `practice` -- both mean "something
	  about this attempt is not the clean case" -- and ^5 cyan for `armed`,
	  matching `held` and `ghost`, which are modes rather than taints.
	*/
	if (state == TS_RUNNING)
	{
		if (stv_y & SF_ARMED)
			s = strcat(s, (s != "") ? "  " : "", "^5armed^7");
		if (stv_x > 0)
			s = strcat(s, (s != "") ? "  " : "",
			           sprintf("^3attempt %g^7", stv_x + 1));

		/*
		  BUILD 44 -- "THE RUN IS GONE BUT THIS STAGE IS STILL WORTH SOMETHING."

		  Build 43's whole per-stage feature is invisible from the HUD: the taint
		  word above says the RUN will not be kept, and there was nothing on screen
		  to say that the stage inside it still would.  Which is the half people
		  act on -- knowing the current stage is still being timed for the board is
		  the difference between finishing the section and resetting.

		  Only ever drawn when the two disagree, so it is news rather than noise:
		  a clean run's stages are all clean and saying so on every stage of every
		  attempt would train people to stop reading the line.

		  Green, alone on this line, and that is deliberate -- it is the only word
		  here that says something is going RIGHT.

		  It assumes run_stageclean 1, which is the default and which the client
		  cannot see.  With that cvar at 0 this would promise a recording that the
		  server then refuses; `cmd timer` prints the rule and is the answer if
		  they ever disagree.
		*/
		if (segs > 1)
		if (seg > 0)
		if (flags & TF_PRACTICE)
		if (!(stv_y & SF_DIRTY))
			s = strcat(s, (s != "") ? "  " : "", "^2stage clean^7");
	}

	/*
	  As WELL as those two, not instead: a stopped clock is a different fact
	  from a tainted run, and a timer that has simply stopped moving is exactly
	  the thing a player would otherwise report as a bug.  It is also the only
	  visible confirmation that the hold took, since the position freeze looks
	  identical whether or not the clock stopped with it.
	*/
	if (state == TS_RUNNING)
		if (flags & TF_FROZEN)
			s = strcat(s, (s != "") ? "  " : "", "^5held^7");

	/*
	  GHOST, build 30, and it is an ADDED state rather than a rename.

	  The ask was "where it says practice mode, maybe make it say Ghost", and the
	  literal reading of that is wrong now: ghosting does not mark a run
	  practice, so the two words are not alternatives.  `practice` still has to
	  mean what it means for setpos, a save-lock load and a hopped start, and a
	  run can be both at once.

	  Last on the line and unconditional on the timer state, because unlike every
	  word above it this one is not a fact about the RUN -- it is a fact about
	  where you are looking from, and it is just as true standing in the start
	  zone with no clock going.  It is also the only thing on screen that says
	  why your body is drifting off without you.

	  ^5 is the cyan `shadow` and `held` already use: this is the same family of
	  "a mode is on" rather than the ^3 amber of "this attempt is tainted".
	*/
	if (rec_gh_on)
		s = strcat(s, (s != "") ? "  " : "", "^5ghost^7");

	if (s != "")
	{
		tw = stringwidth(s, TRUE, [small, small]);
		if (tw > bw) bw = tw;
		HUD_TextC([p_x, y], s, small, '0.70 0.73 0.78', 1);
		y = y + small + 2 * ui_cv_scale;
	}

	// The personal best for the leg currently armed or running.
	if (flags & TF_HAVEPB)
	{
		HUD_TextC([p_x, y], strcat("pb ", Time_TickString(pb, tick)),
		          small, '0.55 0.70 0.90', 1);
		y = y + small + 2 * ui_cv_scale;
	}

	// Build 31: centre-anchored in x, top in y, like the speedometer.  The colour
	// codes in the sub-label ("^5ghost^7") are counted by stringwidth as drawn,
	// which is what TRUE in the second argument is for -- so the box matches the
	// glyphs rather than the source string.
	HUD_Rect("timer", [bp_x - bw * 0.5, bt, 0], [bw, y - bt, 0], bp);

	return y;
};

void(vector scr) Timer_Draw =
{
	local float state, ticks, seg, segs, track, flags, split, delta, pb, cp;
	local float tick, small, y;
	local float fails;
	local vector p;

	if (zone_mapname != ui_tm_map)
	{
		ui_tm_map = zone_mapname;
		Timer_SplitsClear();
		ui_tm_lastdrawstate = -1;
		ui_tm_lastseg = 0;
		ui_tm_lastcp  = 0;

		// Build 43.  -1 and not 0: a fresh map legitimately reports 0 fails, and
		// seeding to 0 would be indistinguishable from having seen that value --
		// which is fine here and is NOT fine on connect, where the first snapshot
		// would otherwise flash a reset at you.  One sentinel, used both places.
		ui_tm_lastfails = -1;
		ui_tm_failat    = 0;
	}

	ui_tm_cv = cvar("hud_timer");
	if (!ui_tm_cv)
		return;

	// Nothing to time on a map with no zone file.  CSQC has the same tables
	// the server does (sh_zones.qc parses both), so this costs one compare
	// and keeps the panel off 773 of the 1308 installed maps.
	if (zone_count <= 0)
		return;

	/*
	  BUILD 24: a replay drives the panel from the file instead of the stats.

	  IT ALSO OWNS THE SPLIT LIST, which is why this returns early rather than
	  merely swapping the sources.  Every edge detector below turns a CHANGE into
	  an event, and a scrub runs the clock backwards -- so seeking from 1:20 to
	  0:05 would walk the segment counter down and fire a "split" for each step,
	  filling the list with rows for stages the run had not reached yet.  The
	  replay pushes the rows it can prove from the .rec's own stage/cp records
	  and rebuilds them wholesale on a seek; see Watch_Splits.

	  The extrapolation latch is still fed, because Timer_Display uses it to
	  smooth between ticks and a stale ui_tm_lastat would make the first frame
	  after the replay ends jump.
	*/
	if (rec_wt_on)
	{
		tick = rec_wt_tickrate > 0 ? rec_wt_tickrate : Timer_Tick();

		ui_tm_lastticks = rec_wt_ticks;
		ui_tm_lastat    = cltime;
		ui_tm_laststate = rec_wt_state;

		// '0 0 0' for the stage state: a .rec carries no arm/fail record, so a
		// replay has nothing honest to say about it.  See Timer_DrawPanel.
		Timer_DrawPanel(scr, rec_wt_state, rec_wt_ticks, rec_wt_flags, rec_wt_pb,
		                tick, [rec_wt_seg, rec_wt_segs, rec_wt_track], '0 0 0');
		Font_Reset();
		Timer_DrawSplits(scr, tick);
		return;
	}

	state = getstatf(STAT_FS_TIMERSTATE);
	ticks = getstatf(STAT_FS_TIMERTICKS);
	seg   = getstatf(STAT_FS_TIMERSEG);
	segs  = getstatf(STAT_FS_TIMERSEGS);
	track = getstatf(STAT_FS_TIMERTRACK);
	flags = getstatf(STAT_FS_TIMERFLAGS);
	split = getstatf(STAT_FS_TIMERSPLIT);
	delta = getstatf(STAT_FS_TIMERDELTA);
	pb    = getstatf(STAT_FS_TIMERPB);

	tick = Timer_Tick();

	// Edge-detect the two things that are events rather than values.
	if (ticks != ui_tm_lastticks || state != ui_tm_laststate)
	{
		ui_tm_lastticks = ticks;
		ui_tm_lastat    = cltime;
		ui_tm_laststate = state;
	}
	if (seg != ui_tm_lastseg)
	{
		// A split, not a reset: arming sets seg back to the leg's own start
		// and there is nothing to flash about that.
		if (state == TS_RUNNING && split > 0)
		{
			ui_tm_splitat = cltime;
			Timer_SplitsPush(SPK_STAGE, seg, split, delta);
		}
		ui_tm_lastseg = seg;
	}

	/*
	  The checkpoint edge.  Build 19, and the same shape as the split edge above
	  for the same reason: the ordinal is strictly increasing within a run and is
	  zeroed by the arm, so a change in it IS the event, and CPT and CPD were
	  written by the server in the same tick so they are safe to read here.

	  cp > 0 excludes the arm's reset to zero, exactly as `split > 0` excludes it
	  on the stage edge.  There is no flash: a checkpoint is not a stage, and
	  interrupting the panel above for one would bury the stage flashes on a map
	  that has both.
	*/
	cp = getstatf(STAT_FS_TIMERCP);
	if (cp != ui_tm_lastcp)
	{
		if (state == TS_RUNNING && cp > 0)
			Timer_SplitsPush(SPK_CP, cp,
			                 getstatf(STAT_FS_TIMERCPT),
			                 getstatf(STAT_FS_TIMERCPD));
		ui_tm_lastcp = cp;
	}

	/*
	  BUILD 43 -- THE STAGE RESET EDGE.

	  GREATER THAN, not different from, and the asymmetry is the whole detector.
	  The counter is zeroed at a genuine boundary and by the arm, and neither of
	  those is an event -- a reset that flashed when you SUCCEEDED at a stage
	  would be exactly backwards.  Only going up is the fail.

	  The -1 seed makes the first snapshot after a connect or a map change a seed
	  rather than an event; see the field block.  `seg` is captured with the flash
	  because by the time it is drawn the player may have crossed into the next
	  stage, and the flash has to keep saying which stage it was about.
	*/
	fails = getstatf(STAT_FS_STAGEFAILS);
	if (fails != ui_tm_lastfails)
	{
		if (ui_tm_lastfails >= 0)
		if (fails > ui_tm_lastfails)
		if (state == TS_RUNNING)
		{
			ui_tm_failat  = cltime;
			ui_tm_failseg = seg + 1;
		}
		ui_tm_lastfails = fails;
	}

	/*
	  The state edges the list cares about, and they are two different things.

	  RUNNING arriving is a NEW run: start fading the old list out.  FINISHED
	  arriving is this run ending: append the total, which is the row you
	  actually came to read.  Both are read from the same stat and neither needs
	  the server to say anything it was not already saying.
	*/
	if (state != ui_tm_lastdrawstate)
	{
		if (state == TS_RUNNING && ui_sp_n > 0)
			ui_sp_fadeat = cltime;
		if (state == TS_FINISHED)
			Timer_SplitsPush(SPK_FINISH, -1, ticks,
			                 (flags & TF_HAVEPB) ? (ticks - pb) : 0);
		ui_tm_lastdrawstate = state;
	}
	if (ui_sp_fadeat > 0)
		if (cltime - ui_sp_fadeat >= SP_FADE)
			Timer_SplitsClear();

	y = Timer_DrawPanel(scr, state, ticks, flags, pb, tick, [seg, segs, track],
	                    [fails, getstatf(STAT_FS_STAGEST), 0]);
	p = [scr_x * ui_tm_x, scr_y * ui_tm_y, 0];
	small = Font_Px(8 * ui_cv_scale);

	/*
	  BUILD 43 -- THE RESET FLASH, AND IT OUTRANKS THE SPLIT FLASH.

	  They share one line, so one of them has to win, and it is this one on both
	  counts: it is strictly newer (a fail cannot happen on the same tick as the
	  split that ended the previous stage, because a split OPENS the stage this
	  can then fail), and it is the one carrying information the player does not
	  otherwise have.  A split delta is a nicety; a silently rebased clock is not.

	  It fades on the same curve and the same cvar as the split flash rather than
	  a second constant -- one setting still governs how long an event stays up.
	*/
	if (ui_tm_failat > 0 && cltime - ui_tm_failat < ui_tm_splittime)
	{
		local float fa;
		fa = 1 - (cltime - ui_tm_failat) / ui_tm_splittime;
		fa = fa * 2;  if (fa > 1) fa = 1;

		HUD_TextC([p_x, y], sprintf("stage %g reset", ui_tm_failseg), small,
		          '1.00 0.55 0.45', fa);
	}
	/*
	  The split flash.  It stays OUT of Timer_DrawPanel because only the live
	  path has one: it is driven by ui_tm_splitat, which the edge detectors above
	  set and a replay never does.

	  Shown only when there is something to compare against: a split with no
	  personal-best split behind it is just the running time again, which is
	  already the big number two lines up.
	*/
	else if (ui_tm_splitat > 0 && cltime - ui_tm_splitat < ui_tm_splittime)
	{
		local float a;
		a = 1 - (cltime - ui_tm_splitat) / ui_tm_splittime;
		a = a * 2;  if (a > 1) a = 1;

		if (delta != 0)
			HUD_TextC([p_x, y], Time_DeltaString(delta, tick), small,
			          (delta < 0) ? '0.45 1.00 0.45' : '1.00 0.55 0.45', a);
		else
			HUD_TextC([p_x, y], Time_TickString(split, tick), small,
			          '0.85 0.85 0.85', a);
	}

	Font_Reset();

	Timer_DrawSplits(scr, tick);
};
