/*
===========================================================================
  cl_boarding.qc -- the Boarding window.  Build 65.

      "seperate 'boarding' numbers with enter/leave values as a new seperate
       window.  allow the player to switch/add energy or unit values."
      "Set it to use the google font the default font for boarding info"

  WHAT WAS WRONG WITH WHERE THEY WERE.  Boarding a ramp produces four numbers
  worth knowing -- how fast you arrived, what the touchdown cost, how fast you
  left, what the ride gave back -- and until this build they were scattered across
  a panel that is mostly about something else.  `contact` shared a row with the
  touchdown's cost, `leaving` had a row of its own three lines below it, and the
  two halves of one comparison were never adjacent.  The ride's energy was not
  displayed at all: leave_de did not exist.

  So they move here, paired: enter above leave, the same two columns in both rows,
  and a fade that is theirs rather than the Board panel's.

  WHAT STAYS BEHIND.  The Board panel keeps the segment-gain line and the grade,
  and it loses the `contact` and `leaving` halves that move here -- deliberately,
  because two panels printing one number is the failure mode cl_hud.qc's own
  `cost` / `board` note is about.  One measurement, one place.

  THE NAME.  `board` already means two different things in this tree:
  cl_board.qc's ramp-contact grader (board_*, seg_*, gain_*) and cl_scores.qc's
  leaderboard (rec_sb_*).  A third would make every grep ambiguous, so the element
  id is "boarding", the cvars are hud_boarding_*, and every global in this file is
  prefixed bd_.  Nothing here shortens to `board`.

  WHERE IT SITS IN cl_progs.src.  After client/cl_hud.qc, because it uses
  HUD_Text*, HUD_Size, HUD_Rect, HUD_EnergyRef, ui_cv_scale and the font globals;
  after client/cl_board.qc for board_* / leave_* / seg_live_*; and BEFORE
  client/cl_hudedit.qc so the editor can list it.  cl_netmon.qc occupies the same
  slot for the same reasons and says so in the manifest.
===========================================================================
*/

float bd_cv_on;
float bd_cv_x, bd_cv_y;
float bd_cv_units;              // 0 u/s, 1 energy, 2 both (stacked)
float bd_cv_fade;
// Build 66: bd_cv_kept and bd_cv_ramp are gone -- those two rows moved to the
// Board panel, where the grade they belong to already lived.  See Boarding_Draw.
float bd_cv_enter, bd_cv_leave;

/*
  Published so the drawer in cl_hud.qc knows where this panel's top edge is when
  it is stacked -- the same handshake ui_strafe_bottom already performs between
  the strafe bar and the Board panel, one link further down the chain.
*/
float ui_bd_bottom;

void() Boarding_RegisterCvars =
{
	/*
	  Registered beside the read, which is this project's rule: cvar() auto-creates
	  a name as "" the first time it is read and registercvar then DECLINES, so a
	  non-zero default registered after a read never lands.  Three of the defaults
	  below are non-zero, so this is the case the rule exists for rather than a
	  formality.
	*/
	registercvar("hud_boarding",       "1", CVAR_ARCHIVE);

	/*
	  -1 IS A SENTINEL, NOT A COORDINATE, and it is hud_board_x's exactly: it means
	  "stay stacked under the Board panel".  That panel changes height as its rows
	  fade in and out, so a constant offset from hud_board_y would make this block
	  twitch every time one did -- the same argument build 31 makes one level up
	  about the strafe bar.

	  Dragging it in `hud_edit` writes real fractions and it stops following.  Both
	  axes are tested together; half-detached is not a state worth reaching.
	*/
	registercvar("hud_boarding_x",    "-1", CVAR_ARCHIVE);
	registercvar("hud_boarding_y",    "-1", CVAR_ARCHIVE);

	registercvar("hud_boarding_size",  "0", CVAR_ARCHIVE);

	/*
	  ITS OWN UNITS SWITCH, not hud_seq_units, and that is the ask rather than an
	  oversight ("allow the player to switch/add energy or unit values" is said
	  once about the segment rows and again about this window).  It is also right
	  on its own terms: the segment column is a list of energy DELTAS where u/s is
	  the translation, while this window's primary reading is a SPEED -- how fast
	  you arrived and left -- with energy as the translation.  The two panels want
	  opposite defaults, which one shared cvar cannot express.

	    0  u/s only
	    1  energy only
	    2  both, stacked top to bottom
	*/
	registercvar("hud_boarding_units", "2", CVAR_ARCHIVE);

	registercvar("hud_boarding_fade",  "3", CVAR_ARCHIVE);

	registercvar("hud_boarding_enter", "1", CVAR_ARCHIVE);
	registercvar("hud_boarding_leave", "1", CVAR_ARCHIVE);
	/*
	  BUILD 66: hud_boarding_kept and hud_boarding_ramp are NOT registered any
	  more -- their rows moved to the Board panel as hud_board_kept and
	  hud_board_ramp.  A config carrying the old pair keeps two dead names, which
	  costs nothing and is what every removed cvar in this tree has done; the
	  alternative is a registered cvar that controls nothing, which is worse.
	*/
};

void() Boarding_ReadCvars =
{
	bd_cv_on    = cvar("hud_boarding");
	bd_cv_x     = cvar("hud_boarding_x");
	bd_cv_y     = cvar("hud_boarding_y");
	bd_cv_units = cvar("hud_boarding_units");
	bd_cv_fade  = cvar("hud_boarding_fade");
	if (bd_cv_fade <= 0) bd_cv_fade = 3;
	bd_cv_enter = cvar("hud_boarding_enter");
	bd_cv_leave = cvar("hud_boarding_leave");
};

/*
  One row: a right-aligned label in a fixed column, then its value.

  THE LABEL COLUMN IS FIXED AND THE VALUE COLUMN IS FIXED, because this face is
  fixed-pitch (Google Sans Code, 0.6 em for every glyph -- sh_font.qc) and that is
  the entire reason the ask names it.  "enter" and "leave" are five characters and
  "kept" and "ramp" are four, so right-aligning the label in five puts every colon
  and every first digit on the same two x's whatever the numbers do.  A
  proportional face would need the label measured per row and would still drift on
  the values.

  Returns the y to draw the next row at, so a caller that skips a row skips its
  space with it rather than leaving a gap where an option used to be.
*/
float(vector p, float y, float sz, float lh, string label, string val,
      vector col, float a) BD_Row =
{
	// 0.6 em per glyph, five glyphs of label plus one of gap: the value column
	// starts at 3.6 * sz.  Derived rather than eyeballed for the reason
	// Timer_DrawSplits' column table is: in this face a column's position IS a
	// character count, so it can be computed and then stops depending on which
	// digits happen to be on screen.
	// Build 65.1: the "%5s" the essay above describes, which was missing -- the
	// labels were being drawn LEFT-aligned from an unpadded string, so "kept" and
	// "ramp" stopped a character short of "enter" and "leave" and the gap to the
	// value column was four characters on two rows and three on the other two.
	// (An unlabelled row -- hud_boarding_units 2's second line -- pads to five
	// spaces and draws nothing, which is what it wants anyway.)
	HUD_Text([p_x, y, 0], sprintf("%5s", label), sz, '0.55 0.60 0.68', a * 0.85);
	HUD_Text([p_x + sz * 3.6, y, 0], val, sz, col, a);
	return y + lh;
};

/*
===========================================================================
  The window.
===========================================================================
*/
void(vector scr, float stacky) Boarding_Draw =
{
	local vector p, bp, col;
	// Build 66: eref is gone.  It was computed with a three-line essay and never
	// referenced -- this window prints deltas and raw speeds, so there was no
	// absolute for a reference to be subtracted from.  The essay had been copied
	// from HUD_DrawSeq, where the value IS used.
	local float sz, lh, y, a, la, bw;
	local float haveenter, haveleave;
	local string s;

	if (!bd_cv_on)
		return;

	sz = HUD_Size("hud_boarding_size", 10 * ui_cv_scale);
	lh = sz * 1.3;

	/*
	  Stacked under the Board panel, or a position of its own.  See the sentinel
	  essay beside the cvar; `stacky` is what the caller published, exactly as the
	  Board panel takes ui_strafe_bottom from the strafe bar.
	*/
	if (bd_cv_x < 0 || bd_cv_y < 0)
		p = [scr_x * ui_cv_strafepos_x, stacky, 0];
	else
		p = [scr_x * bd_cv_x, scr_y * bd_cv_y, 0];

	bp = p;
	y  = p_y;
	bw = 0;

	/*
	  THE TWO FADES ARE SEPARATE, because the two edges are.

	  board_time is stamped when you touch down and leave_time when you come off,
	  and on a long ride those are seconds apart.  One fade over both would either
	  take the enter row away while you are still on the ramp it describes, or hold
	  the leave row from the PREVIOUS ramp alongside this one's enter row -- and the
	  second is worse, because two rows that look like a pair would be about two
	  different ramps.
	*/
	a  = Board_Alpha(board_time, bd_cv_fade);
	la = Board_Alpha(leave_time, bd_cv_fade);

	haveenter = (bd_cv_enter && a  > 0);
	haveleave = (bd_cv_leave && la > 0);

	// Nothing to say.  Registering a zero-height box would be refused by HUD_Rect
	// anyway; returning early also keeps the font unset, which matters because
	// drawfont is a global and leaving it selected would follow the next drawer.
	if (!haveenter && !haveleave)
	{
		ui_bd_bottom = y;
		return;
	}

	Font_Set(ui_font_mono);

	/*
	  ENTER.  The speed you arrived at, and what the touchdown took off you.

	  board_speedin_h is horizontal, matching the speedometer rather than the 3D
	  speed the energy is built from -- "how fast was I going" is the horizontal
	  question on a surf map.  board_losse is a MAGNITUDE and is negated here,
	  because on this row it is a change and its sign is the information: every
	  touchdown costs, and a column of unsigned numbers under a heading that also
	  carries gains would read as if some of them were gains.
	*/
	if (haveenter)
	{
		if (bd_cv_units != 1)
		{
			s = sprintf("%du/s", rint(HUD_Round(board_speedin_h)));
			y = BD_Row(p, y, sz, lh, "enter", s, '0.85 0.90 1.00', a);
			if (stringwidth(s, TRUE, [sz, sz]) > bw) bw = stringwidth(s, TRUE, [sz, sz]);
		}
		if (bd_cv_units >= 1)
		{
			s = sprintf("%+de", rint(0 - board_losse));
			/*
			  The label is blank on the second line of a stacked pair: it is the
			  same row in a second unit, not a second row, and repeating "enter"
			  would make the window look like it had four readings instead of two.
			*/
			y = BD_Row(p, y, sz, lh, (bd_cv_units >= 2) ? "" : "enter", s,
			           '1.00 0.62 0.34', a * ((bd_cv_units >= 2) ? 0.75 : 1));
			if (stringwidth(s, TRUE, [sz, sz]) > bw) bw = stringwidth(s, TRUE, [sz, sz]);
		}
	}

	/*
	  LEAVE.  The speed you came off at, and what the whole ride was worth.

	  leave_de is signed and can genuinely be either: a good line on a steep face
	  gains, and a ride taken too flat loses.  Coloured by its sign for that reason
	  rather than fixed like the enter row, which cannot be positive.
	*/
	if (haveleave)
	{
		if (bd_cv_units != 1)
		{
			s = sprintf("%du/s", rint(HUD_Round(leave_speed)));
			y = BD_Row(p, y, sz, lh, "leave", s, '0.85 0.90 1.00', la);
			if (stringwidth(s, TRUE, [sz, sz]) > bw) bw = stringwidth(s, TRUE, [sz, sz]);
		}
		if (bd_cv_units >= 1)
		{
			col = (leave_de >= 0) ? '0.55 0.95 0.55' : '1.00 0.55 0.20';
			s   = sprintf("%+de", rint(leave_de));
			y = BD_Row(p, y, sz, lh, (bd_cv_units >= 2) ? "" : "leave", s, col,
			           la * ((bd_cv_units >= 2) ? 0.75 : 1));
			if (stringwidth(s, TRUE, [sz, sz]) > bw) bw = stringwidth(s, TRUE, [sz, sz]);
		}
	}

	/*
	  BUILD 66 -- `kept` AND `ramp` ARE GONE FROM HERE.

	      "I think this one is a little confused, all it is supposed to be is the
	       'enter' and 'leave' values, the rest are unnessisary."

	  Right, and the duplication was worse than redundant.  This window drew

	      kept  83.9% good

	  while the Board panel two lines above it drew

	      good  83.9% kept

	  -- the same board_kept and the same Board_GradeName, twice, with the label
	  and the word swapped so it read as two different measurements that happened
	  to agree.  That is precisely what build 65 moved `contact` and `leaving` OUT
	  of the Board panel to avoid, applied in one direction and not the other.

	  So the grade stays there, where the percentage has something to be a
	  percentage of, and the ramp angle joins it (it is a property of the plane,
	  like the grade and the cost).  This window is the enter/leave pair and
	  nothing else, which is what it was for.

	  hud_boarding_kept and hud_boarding_ramp go with them.  Nothing is lost: both
	  readings are still switchable, as hud_board_kept and hud_board_ramp.
	*/
	Font_Reset();

	ui_bd_bottom = y;

	/*
	  The box, for the layout editor.

	  bw is the widest VALUE, so the block's real width is the label column plus
	  that; floored at ten characters for the reason the Board panel's own box is
	  floored, which is that every row here is on a fade and a window nobody has
	  boarded in a while would otherwise publish a degenerate box that HUD_Rect
	  refuses -- leaving the editor to fall back to a guess for a panel that IS on
	  screen.

	  Centre-anchored in x to match the stack it sits in.
	*/
	bw = bw + sz * 3.6;
	if (bw < sz * 10)
		bw = sz * 10;
	HUD_Rect("boarding", [bp_x - bw * 0.5, bp_y, 0], [bw, y - bp_y, 0], bp);
};
