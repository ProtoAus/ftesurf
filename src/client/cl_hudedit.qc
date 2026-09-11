/*
===========================================================================
  cl_hudedit.qc -- the HUD layout editor.  Build 31.

  Ten panels have had hud_*_x / hud_*_y cvars since build 13 and there has never
  been a way to move one except by typing a cvar name you had to already know,
  guessing a fraction, and looking.  `hud_edit` makes the layout the thing you
  manipulate: drag a panel where you want it and it stays there across a quit.

  THIS FILE OWNS NO LAYOUT.  It never computes where a panel is; it reads the
  boxes the panels themselves published through HUD_Rect (see the registry essay
  in cl_hud.qc) and writes their cvars back.  That split is the whole design.  An
  editor that reproduced each drawer's positioning maths would be a second copy
  of ten layouts, and the first panel to gain a row would silently start being
  edited through a rectangle that is no longer where it draws.

  WHY IT IS LAST IN cl_progs.src.  It needs rec_wt_open (cl_watch.qc) and
  rec_sb_open (cl_scores.qc) to refuse to share the screen with a replay or the
  leaderboard, and both compile after cl_hud.qc.  ui_he_open itself is declared
  over in cl_hud.qc, because the drawers test it and they compile first.

  PERSISTENCE IS `seta`, NOT registercvar.  The full argument is beside
  registercvar in cl_defs.qc; the short version is that cfg/default.cfg creates
  every hud_* cvar before this VM exists, registercvar refuses to touch a cvar
  that already exists, and Cmd_set_f's not-from-gamecode branch (cmd.c:4266) is
  the only path that adds CVAR_ARCHIVE to one that does.  So every write here
  goes out as `seta`, cfg_save_auto 1 writes ftesurf.cfg on quit, and
  ftesurf.cfg is exec'd after default.cfg on the next launch.
===========================================================================
*/

float  ui_he_drag;              // an element is being dragged right now
float  ui_he_dirty;             // something was written; save on close
float  ui_he_shift;             // a shift key is down -- snapping suspended
string ui_he_held;              // the id being dragged, "" if none
vector ui_he_grab;              // cursor position when the drag started
vector ui_he_anchor0;           // that element's anchor when the drag started
float  ui_he_snapx, ui_he_snapy;// the lines snapped to this frame, -1 = none

/*
  THE TOOL PANEL MOVES TOO, and that is a fix rather than a flourish.

  It has to block clicks -- a click that fell through it into the world behind
  would start dragging whatever panel happens to be under the cursor, which is
  the opposite of what pressing a button should do.  But four of the ten
  elements live in the left margin (splits 0.045, debug 0.012, and both menus at
  0.018) and the panel has to live somewhere, so with it fixed in place those
  four were unreachable: the first run of this editor could not drag the split
  list, the save menu or the video menu at all.

  Every side of the screen has the same problem -- the key block owns the right,
  the timer the top, the speedometer the centre -- so there is no free corner to
  move it to.  Dragging it by its title bar is the answer every editor of
  anything has arrived at, and the machinery is already here.
*/
float  ui_he_pdrag;
vector ui_he_pgrab, ui_he_p0;

void(float r) HE_Default;       // defined at the bottom; the panel's reset chips
                                // call it, and QuakeC wants the name first

/*
  THE ELEMENT TABLE.

  Parallel arrays rather than a struct array because every other table in this
  project is written that way (ui_sp_*, seq_*, hude_*) and mixing the two styles
  in one VM is worse than either.

  `ox` is the one genuine irregularity and it is worth naming rather than
  hiding: hud_seq_x is an OFFSET FROM THE SCREEN CENTRE, not a fraction of the
  width, so that the segment column stays the same distance from the crosshair
  on any aspect ratio (build 13).  Every other x is a plain fraction.  One flag,
  one addition, at the two points the cvar is read and written.

  `nw`/`nh` are the NOMINAL size, in hud_scale units, used when the panel drew
  nothing this frame -- a faded split list, a menu that is closed, a readout
  switched off.  Being unable to move a panel because it happens to be invisible
  is exactly the situation an editor exists to fix, so those get a dim
  placeholder at their cvars' own position and drag identically.

  `an` is which of the three anchor conventions the placeholder has to reproduce.
  A panel that DID draw hands over its real anchor and this is not consulted.
*/
#define HEA_LT  0               // left-x,   top-y
#define HEA_CT  1               // centre-x, top-y
#define HEA_LC  2               // left-x,   centre-y
#define HEA_RC  3               // right-x,  centre-y   (the segment column)
#define HEA_RT  4               // right-x,  top-y      (build 34: the map info block)

// 12, not 10.  It was exactly full: ten conventions and ten rows, so the map info
// block's HE_Add would have been dropped on the floor by HE_Add's own bounds
// check and the panel would simply not have listed it.  HUDE_MAX in cl_hud.qc is
// the other half of this pair and already had the room.
#define HE_MAX 12

string he_id[HE_MAX];
string he_label[HE_MAX];
string he_cvx[HE_MAX];
string he_cvy[HE_MAX];
string he_cvon[HE_MAX];         // "" = no on/off toggle of its own
float  he_ox[HE_MAX];           // x is an offset from the centre, not a fraction
float  he_an[HE_MAX];
float  he_nw[HE_MAX], he_nh[HE_MAX];
float  he_n;

void(string id, string label, string cvx, string cvy, string cvon,
     float ox, float an, float nw, float nh) HE_Add =
{
	if (he_n >= HE_MAX)
		return;
	he_id[he_n]    = id;
	he_label[he_n] = label;
	he_cvx[he_n]   = cvx;
	he_cvy[he_n]   = cvy;
	he_cvon[he_n]  = cvon;
	he_ox[he_n]    = ox;
	he_an[he_n]    = an;
	he_nw[he_n]    = nw;
	he_nh[he_n]    = nh;
	he_n = he_n + 1;
};

void() HE_BuildTable =
{
	if (he_n)
		return;

	//      id         label         x cvar           y cvar           on cvar        ox  anchor    nw   nh
	HE_Add("timer",   "Timer",      "hud_timer_x",   "hud_timer_y",   "hud_timer",    0, HEA_CT,   90,  32);
	HE_Add("splits",  "Splits",     "hud_splits_x",  "hud_splits_y",  "hud_splits",   0, HEA_LC,  201,  40);
	HE_Add("seq",     "Segments",   "hud_seq_x",     "hud_seq_y",     "hud_seq",      1, HEA_RC,  110, 100);
	HE_Add("strafe",  "Strafe bar", "hud_strafe_x",  "hud_strafe_y",  "hud_strafe",   0, HEA_CT,  260,  40);
	HE_Add("board",   "Board",      "hud_board_x",   "hud_board_y",   "hud_board",    0, HEA_CT,  120,  52);
	HE_Add("speed",   "Speed",      "hud_speed_x",   "hud_speed_y",   "hud_speed",    0, HEA_CT,   70,  40);
	HE_Add("keys",    "Keys",       "hud_keys_x",    "hud_keys_y",    "hud_keys",     0, HEA_LT,   64,  50);
	HE_Add("debug",   "Debug",      "hud_debug_x",   "hud_debug_y",   "hud_debug",    0, HEA_LT,  110, 130);
	HE_Add("saveloc", "Save menu",  "hud_saveloc_x", "hud_saveloc_y", "",             0, HEA_LT,   84, 145);
	HE_Add("gfx",     "Video menu", "hud_gfx_x",     "hud_gfx_y",     "",             0, HEA_LT,  150, 180);
	HE_Add("mapinfo", "Map info",   "hud_mapinfo_x", "hud_mapinfo_y", "hud_mapinfo",  0, HEA_RT,   96,  56);
};

// Which registered rect belongs to this id.  -1 when the panel drew nothing this
// frame -- see he_nw/he_nh.
float(string id) HE_Rect =
{
	local float i;
	for (i = 0; i < hude_n; i = i + 1)
		if (hude_id[i] == id)
			return i;
	return -1;
};

/*
  Where a row's cvars say its anchor is, in pixels.

  Used only for a row with no registered rect.  A row that DID draw hands over
  its own anchor, which is authoritative and can differ from this: hud_keys_x 0
  is auto-right, hud_board_x -1 is stacked under the strafe bar, and the timer is
  pushed down when the replay chrome is up.  This is the placeholder's best
  guess, and it is exact for the case it exists for -- a panel that is simply
  switched off, whose cvars are ordinary fractions nobody has overridden.
*/
vector(float r, vector scr) HE_AnchorOf =
{
	local float x, y;

	x = cvar(he_cvx[r]);
	y = cvar(he_cvy[r]);

	if (he_ox[r])
		x = x + 0.5;

	// The two sentinels.  Neither is a coordinate, so neither can be scaled;
	// park the placeholder somewhere visible and let the first drag write real
	// values, which is the documented way out of both.  hud_keys_x 0 is put
	// where auto-right actually lands rather than at the left edge.
	if (he_id[r] == "keys" && x == 0)
		x = 0.86;
	if (x < 0) x = 0.5;
	if (y < 0) y = 0.5;

	return [scr_x * x, scr_y * y, 0];
};

// The placeholder's top-left, from its anchor and its convention.
vector(float r, vector a, vector sz) HE_BoxOf =
{
	local vector p;
	p = a;
	if (he_an[r] == HEA_CT) p_x = a_x - sz_x * 0.5;
	// Build 34: HEA_RT reuses HEA_RC's x rule exactly -- the anchor is the RIGHT
	// edge in both -- and takes no y offset, because its anchor is already the top.
	if (he_an[r] == HEA_RC || he_an[r] == HEA_RT) p_x = a_x - sz_x;
	if (he_an[r] == HEA_LC || he_an[r] == HEA_RC) p_y = a_y - sz_y * 0.5;
	return p;
};

/*
  Write an anchor back.  ONE PLACE, so the offset-from-centre case and the `seta`
  rule each exist exactly once.

  %.4f rather than %g: %g gives six significant figures and turns 0.42 into
  0.419999987, which is correct, saved, and unreadable when you later open
  ftesurf.cfg to see what your layout is.  Four decimals is under a pixel at 4K
  on both axes.
*/
void(float r, vector px, vector scr) HE_Write =
{
	local float x, y;

	x = px_x / scr_x;
	y = px_y / scr_y;
	if (he_ox[r])
		x = x - 0.5;

	localcmd(sprintf("seta %s %.4f\n", he_cvx[r], x));
	localcmd(sprintf("seta %s %.4f\n", he_cvy[r], y));
	ui_he_dirty = TRUE;
};

/*
===========================================================================
  Snapping.

  Candidate lines are the four screen edges INSET BY 64, the two centre axes,
  and the matching edges of every other element on screen.  The inset is the
  number that was asked for and it is a better default than the frame itself:
  nothing on this HUD is meant to touch the edge, and a panel snapped hard to
  x = 0 is off the safe area on a TV and under the notch on a laptop.

  The dragged box offers three points per axis -- its two edges and its centre --
  so a panel can be aligned by whichever of its own features you are thinking
  about.  Nearest wins; the winning line is drawn, so it is visible WHY the drag
  stopped where it did.

  HE_Snap returns the CORRECTION to add, not the snapped position, because the
  caller is moving an anchor and the anchor is generally none of the three points
  that snapped.
===========================================================================
*/
#define HE_CANDS 64
float he_cand[HE_CANDS];
float he_ncand;

void(float v) HE_Cand =
{
	if (he_ncand >= HE_CANDS)
		return;
	he_cand[he_ncand] = v;
	he_ncand = he_ncand + 1;
};

// axis 0 = x, 1 = y -- which of the two "line we snapped to" globals to write.
float(float lo, float mid, float hi, float lim, float axis) HE_Snap =
{
	local float i, j, v, d, ad, bestd, bestfix, bestline;

	bestd    = -1;
	bestfix  = 0;
	bestline = -1;

	for (j = 0; j < 3; j = j + 1)
	{
		v = (j == 0) ? lo : ((j == 1) ? mid : hi);
		for (i = 0; i < he_ncand; i = i + 1)
		{
			d  = he_cand[i] - v;
			ad = (d < 0) ? (0 - d) : d;
			if (ad > lim)
				continue;
			if (bestd >= 0 && bestd <= ad)
				continue;
			bestd    = ad;
			bestfix  = d;
			bestline = he_cand[i];
		}
	}

	if (axis == 0) ui_he_snapx = bestline;
	else           ui_he_snapy = bestline;
	return bestfix;
};

/*
===========================================================================
  Opening and closing
===========================================================================
*/
void() HUD_EditClose =
{
	if (!ui_he_open)
		return;
	ui_he_open = FALSE;
	ui_he_drag = FALSE;
	ui_he_held = "";

	/*
	  The cursor goes back to the game ONLY if nothing else still wants it.
	  Copied from Scores_Close and for the same reason: the leaderboard and the
	  replay chrome share this cursor, and turning it off underneath one of them
	  leaves a panel up with nothing able to press anything on it.
	*/
	// BUILD 48: and the results card, once it has actually TAKEN the cursor.
	// ui_rs_cursor and not ui_rs_open -- the card spends most of its life drawn
	// and passive, and a panel merely on screen has no claim on the mouse.
	//
	// BUILD 55: that distinction was the right one and it is preserved -- the
	// card claims UIC_RESULTS only in Results_TakeCursor, not when it is merely
	// drawn. What changed is that this file no longer enumerates the others.
	UI_CursorRelease(UIC_HUDEDIT);

	/*
	  cfg_save_auto 1 means the engine writes ftesurf.cfg on a clean quit, so this
	  is belt to that braces -- and the braces are worth having, because the
	  session most likely to end in a crash is the one where you were fiddling
	  with settings.  Only when something was actually written.
	*/
	if (ui_he_dirty)
	{
		ui_he_dirty = FALSE;
		localcmd("cfg_save\n");
		print("^5hud_edit^7: layout saved to ftesurf.cfg\n");
	}
};

void() HUD_EditOpen =
{
	if (ui_he_open)
		return;

	// It would draw over both and take their clicks; rather than layer three
	// owners of one cursor, refuse and say which one is in the way.
	if (rec_wt_open || rec_sb_open)
	{
		print("^3hud_edit^7: close the replay or the scoreboard first\n");
		return;
	}

	HE_BuildTable();
	ui_he_open  = TRUE;
	ui_he_drag  = FALSE;
	ui_he_shift = FALSE;
	ui_he_held  = "";
	UI_CursorClaim(UIC_HUDEDIT);

	print("^5hud_edit^7: drag a panel to move it.  SHIFT suspends snapping.\n");
	print("           click a name to toggle it; ESC, `done` or `hud_edit` to finish.\n");
};

/*
===========================================================================
  Drawing, and the interaction that goes with it.

  sui provides the whole interaction model -- sui_action_element registers a hit
  rect, sui_is_held reports the drag, sui_is_released the click -- so this is
  wiring rather than new machinery.  sui_begin / sui_end MUST bracket it:
  cl_watch.qc:2477 records what a missing sui_end latches.
===========================================================================
*/
#define HEC_PANEL  '0.07 0.09 0.12'
#define HEC_LINE   '0.35 0.70 1.00'
#define HEC_HOT    '1.00 0.80 0.35'
#define HEC_GHOST  '0.45 0.48 0.55'
#define HEC_TEXT   '0.88 0.92 0.98'
#define HEC_DIM    '0.55 0.60 0.68'

// A labelled chip.  Returns TRUE on the frame it is released.
float(string id, vector pos, vector sz, string label, float on, float sc) HE_Chip =
{
	sui_action_element(pos, sz, id, sui_noop);
	sui_fill(pos, sz, on ? '0.16 0.30 0.44' : '0.12 0.13 0.16', 1, 0);
	sui_border_box(pos, sz, 1,
	               sui_is_hovered(id) ? HEC_HOT : (on ? HEC_LINE : HEC_GHOST),
	               sui_is_hovered(id) ? 1.0 : 0.5, 0);
	HUD_Text([pos_x + 4 * sc, pos_y + (sz_y - 8 * sc) * 0.5, 0], label,
	         8 * sc, on ? HEC_TEXT : HEC_DIM, 1);
	return sui_is_released(id);
};

void(vector scr) HUD_EditDraw =
{
	local float i, k, r, sc, psc, lim, held, mode, x, y, w, rowh, panw;
	local vector p, sz, a, b, np, fix, op, os;
	local string s;

	if (!ui_he_open)
		return;

	// Either of these can be opened from a bind while this is up.  They own the
	// cursor and draw over everything; step aside rather than fight for it.
	if (rec_wt_open || rec_sb_open)
	{
		HUD_EditClose();
		return;
	}

	sc = ui_cv_scale;
	if (sc <= 0) sc = 2;

	lim = cvar("hud_edit_snap");
	if (lim < 0) lim = 0;

	ui_he_snapx = -1;
	ui_he_snapy = -1;

	sui_begin(scr_x, scr_y);

	// The world stays visible.  You are laying out a HUD against the thing it
	// goes over, and dimming it to a menu grey would be laying it out against
	// something you will never see it on.
	sui_fill('0 0 0', [scr_x, scr_y, 0], '0 0 0', 0.25, 0);

	// The six fixed snap lines, drawn faintly the whole time so the targets are
	// visible before you are near them.
	drawfill([64, 0, 0],           [1, scr_y, 0], HEC_GHOST, 0.18, 0);
	drawfill([scr_x - 64, 0, 0],   [1, scr_y, 0], HEC_GHOST, 0.18, 0);
	drawfill([0, 64, 0],           [scr_x, 1, 0], HEC_GHOST, 0.18, 0);
	drawfill([0, scr_y - 64, 0],   [scr_x, 1, 0], HEC_GHOST, 0.18, 0);
	drawfill([scr_x * 0.5, 0, 0],  [1, scr_y, 0], HEC_GHOST, 0.25, 0);
	drawfill([0, scr_y * 0.5, 0],  [scr_x, 1, 0], HEC_GHOST, 0.25, 0);

	Font_Set(ui_font_ui);

	/*
	  PASS ONE -- one hit rect per element, and the drag.

	  Registered in table order, so sui's front-to-back iteration makes the LAST
	  row win an overlap.  The two menus are last in the table and are also the
	  two most likely to be sitting on top of something, which is the order you
	  want.
	*/
	for (i = 0; i < he_n; i = i + 1)
	{
		r = HE_Rect(he_id[i]);
		if (r >= 0)
		{
			p  = hude_pos[r];
			sz = hude_size[r];
			a  = hude_anchor[r];
		}
		else
		{
			// Drew nothing this frame: a nominal box at the cvars' own position,
			// so a switched-off or faded-out panel is still something you can grab.
			a  = HE_AnchorOf(i, scr);
			sz = [he_nw[i] * sc, he_nh[i] * sc, 0];
			p  = HE_BoxOf(i, a, sz);
		}

		// The hit rect is padded outward: several of these boxes are a few pixels
		// of text, and grabbing one exactly would be a game rather than an editor.
		sui_action_element([p_x - 4, p_y - 4, 0], [sz_x + 8, sz_y + 8, 0],
		                   he_id[i], sui_noop);

		held = sui_is_held(he_id[i]);

		if (held && !ui_he_drag)
		{
			ui_he_drag    = TRUE;
			ui_he_held    = he_id[i];
			ui_he_grab    = _cursor_position;
			ui_he_anchor0 = a;
		}

		if (ui_he_drag && held && ui_he_held == he_id[i])
		{
			np = ui_he_anchor0 + (_cursor_position - ui_he_grab);

			/*
			  SNAPPING OPERATES ON THE BOX, NOT ON THE ANCHOR.

			  You are aligning a panel's visible edge against another panel's
			  visible edge; the anchor is an implementation detail of that panel's
			  own convention, and lining two anchors up would line up nothing you
			  can see.  So the box is moved by the same delta, snapped there, and
			  the correction is added back onto the anchor.

			  SHIFT suspends it, per the ask -- held rather than toggled, because
			  it is wanted for one placement at a time.  Tracked in the input
			  handler: Keys_Held only knows the eight MOVEMENT binds (cl_keys.qc),
			  and +speed is not one of them.
			*/
			fix = '0 0 0';
			if (lim > 0 && !ui_he_shift)
			{
				b = p + (np - a);

				he_ncand = 0;
				HE_Cand(64); HE_Cand(scr_x - 64); HE_Cand(scr_x * 0.5);
				for (k = 0; k < hude_n; k = k + 1)
				{
					if (hude_id[k] == he_id[i])
						continue;
					op = hude_pos[k];  os = hude_size[k];
					HE_Cand(op_x);
					HE_Cand(op_x + os_x);
					HE_Cand(op_x + os_x * 0.5);
				}
				fix_x = HE_Snap(b_x, b_x + sz_x * 0.5, b_x + sz_x, lim, 0);

				he_ncand = 0;
				HE_Cand(64); HE_Cand(scr_y - 64); HE_Cand(scr_y * 0.5);
				for (k = 0; k < hude_n; k = k + 1)
				{
					if (hude_id[k] == he_id[i])
						continue;
					op = hude_pos[k];  os = hude_size[k];
					HE_Cand(op_y);
					HE_Cand(op_y + os_y);
					HE_Cand(op_y + os_y * 0.5);
				}
				fix_y = HE_Snap(b_y, b_y + sz_y * 0.5, b_y + sz_y, lim, 1);
			}

			np = np + fix;

			/*
			  Clamped on the ANCHOR rather than on the box.  A box clamp would
			  fight the snap, and a panel dragged past the bottom would stick to
			  the edge instead of following the mouse back up.

			  ONE PIXEL IN, NOT ZERO, and that is a trap rather than a nicety:
			  hud_keys_x 0 is the auto-right SENTINEL, so a key block dragged hard
			  against the left edge would write exactly 0, re-enter auto mode, and
			  jump to the far right of the screen the moment you let go.  Keeping
			  the anchor off the axis makes the fraction non-zero for every panel
			  and costs a pixel of reach nobody wants.
			*/
			if (np_x < 1) np_x = 1;
			if (np_y < 1) np_y = 1;
			if (np_x > scr_x - 1) np_x = scr_x - 1;
			if (np_y > scr_y - 1) np_y = scr_y - 1;

			HE_Write(i, np, scr);

			// The box as it will be NEXT frame, so the outline leads the panel
			// rather than trailing it by one.
			p = p + (np - a);
		}

		// Solid outline for a panel that drew, a dim filled one for a placeholder.
		mode = (ui_he_drag && ui_he_held == he_id[i]) ? 2 : ((r >= 0) ? 1 : 0);
		if (mode == 0)
			sui_fill(p, sz, HEC_GHOST, 0.08, 0);
		sui_border_box(p, sz, (mode == 2) ? 2 : 1,
		               (mode == 2) ? HEC_HOT : ((mode == 1) ? HEC_LINE : HEC_GHOST),
		               (mode == 0) ? 0.35 : 0.9, 0);

		HUD_Text([p_x + 2, p_y - 10 * sc, 0], he_label[i], 8 * sc,
		         (mode == 2) ? HEC_HOT : ((mode == 1) ? HEC_LINE : HEC_GHOST), 0.9);
	}

	if (ui_he_drag && !sui_click_held())
	{
		ui_he_drag = FALSE;
		ui_he_held = "";
	}

	// The lines we snapped to, over the boxes, so the alignment that stopped the
	// drag is the thing you see.
	if (ui_he_snapx >= 0)
		drawfill([ui_he_snapx, 0, 0], [1, scr_y, 0], HEC_HOT, 0.7, 0);
	if (ui_he_snapy >= 0)
		drawfill([0, ui_he_snapy, 0], [scr_x, 1, 0], HEC_HOT, 0.7, 0);

	/*
	  PASS TWO -- the side panel.

	  On the left, because eight of the ten elements live at or right of centre
	  and a panel that covered them would be an editor you have to close in order
	  to see your work.  Registered AFTER the elements so it wins every overlap: a
	  click meant for a chip must never fall through and start dragging the panel
	  behind it.
	*/
	/*
	  ITS OWN SCALE, CAPPED AT 2.  This panel is chrome for a tool, not part of
	  the HUD, so it has no reason to grow with hud_scale -- and at hud_scale 3 it
	  would be 843 px tall on a 720-line window and run off the bottom, taking the
	  `done` button with it.  The outlines and labels out in the world still use
	  the real scale, because those ARE the HUD.
	*/
	psc = sc;
	if (psc > 2) psc = 2;

	rowh = 15 * psc;
	panw = 150 * psc;
	p    = [scr_x * cvar("hud_edit_panel_x"), scr_y * cvar("hud_edit_panel_y"), 0];
	sz   = [panw, rowh * (he_n + 7) + 26 * psc, 0];

	// Kept on screen whatever the window is and wherever it was left.
	if (p_x > scr_x - sz_x) p_x = scr_x - sz_x;
	if (p_y > scr_y - sz_y) p_y = scr_y - sz_y;
	if (p_x < 0) p_x = 0;
	if (p_y < 0) p_y = 0;

	sui_action_element(p, sz, "he_panel", sui_noop);
	sui_fill(p, sz, HEC_PANEL, 0.92, 0);
	sui_border_box(p, sz, 1, HEC_LINE, 0.7, 0);

	/*
	  THE TITLE BAR IS THE HANDLE, and it is a separate hit rect registered after
	  the body so it wins.  Dragging by the body would mean every miss between two
	  chips moved the panel.
	*/
	sui_action_element(p, [panw, 16 * psc, 0], "he_panelbar", sui_noop);
	if (sui_is_held("he_panelbar"))
	{
		if (!ui_he_pdrag)
		{
			ui_he_pdrag = TRUE;
			ui_he_pgrab = _cursor_position;
			ui_he_p0    = p;
		}
		np = ui_he_p0 + (_cursor_position - ui_he_pgrab);
		if (np_x < 0) np_x = 0;
		if (np_y < 0) np_y = 0;
		if (np_x > scr_x - sz_x) np_x = scr_x - sz_x;
		if (np_y > scr_y - sz_y) np_y = scr_y - sz_y;
		localcmd(sprintf("seta hud_edit_panel_x %.4f\n", np_x / scr_x));
		localcmd(sprintf("seta hud_edit_panel_y %.4f\n", np_y / scr_y));
		ui_he_dirty = TRUE;
	}
	else
		ui_he_pdrag = FALSE;

	sui_fill(p, [panw, 16 * psc, 0],
	         sui_is_hovered("he_panelbar") ? '0.16 0.30 0.44' : '0.10 0.13 0.18', 1, 0);

	x = p_x + 6 * psc;
	y = p_y + 6 * psc;
	w = panw - 12 * psc;

	HUD_Text([x, y, 0], "HUD layout", 10 * psc, HEC_TEXT, 1);
	HUD_Text([p_x + panw - 34 * psc, y + psc, 0], "move", 7 * psc, HEC_DIM, 0.8);
	y = y + 14 * psc;

	for (i = 0; i < he_n; i = i + 1)
	{
		/*
		  The name IS the on/off chip.  Elements with no toggle of their own -- the
		  save-lock and video menus, which are opened by a bind -- get a plain
		  label, because a chip that cannot be clicked is worse than no chip.
		*/
		if (he_cvon[i] != "")
		{
			if (HE_Chip(strcat("he_on_", he_id[i]), [x, y, 0],
			            [w * 0.62, rowh - 2 * psc, 0],
			            he_label[i], cvar(he_cvon[i]), psc))
				localcmd(sprintf("seta %s %g\n", he_cvon[i], cvar(he_cvon[i]) ? 0 : 1));
		}
		else
			HUD_Text([x + 4 * psc, y + (rowh - 8 * psc) * 0.5, 0], he_label[i],
			         8 * psc, HEC_DIM, 1);

		/*
		  Reset, PER ELEMENT and deliberately so.  The usual way to get lost is to
		  drag one panel somewhere silly, and having to reset the whole layout to
		  undo that is a reason not to try things.  `hud_edit reset` does all ten.
		*/
		if (HE_Chip(strcat("he_rst_", he_id[i]),
		            [x + w * 0.66, y, 0], [w * 0.34, rowh - 2 * psc, 0],
		            "reset", FALSE, psc))
			HE_Default(i);

		y = y + rowh;
	}

	y = y + 5 * psc;
	drawfill([x, y, 0], [w, 1, 0], HEC_GHOST, 0.3, 0);
	y = y + 5 * psc;

	/*
	  THE UNIT SWITCHES.

	  hud_seq_units has existed since build 20 and has never been reachable
	  without typing it: "change energy back to the original u/s" is one chip, and
	  this is it.  It covers the segment column AND the board panel's own rows,
	  which read the same cvar precisely so that the two can never disagree about
	  what they are counting in.
	*/
	if (HE_Chip("he_units", [x, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            cvar("hud_seq_units") ? "seg: e" : "seg: u/s",
	            cvar("hud_seq_units"), psc))
		localcmd(sprintf("seta hud_seq_units %g\n", cvar("hud_seq_units") ? 0 : 1));

	// hud_energy is a three-state (off / units / u/s equivalent), so the chip
	// prints which one it is on rather than only being lit or not.
	mode = cvar("hud_energy");
	if (HE_Chip("he_energy", [x + w * 0.52, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            (mode >= 2) ? "e: u/s" : (mode ? "e: units" : "e: off"), mode, psc))
		localcmd(sprintf("seta hud_energy %g\n", (mode >= 2) ? 0 : mode + 1));
	y = y + rowh;

	if (HE_Chip("he_pct", [x, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            "seg %", cvar("hud_seq_pct"), psc))
		localcmd(sprintf("seta hud_seq_pct %g\n", cvar("hud_seq_pct") ? 0 : 1));
	if (HE_Chip("he_sboard", [x + w * 0.52, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            "seg board", cvar("hud_seq_board"), psc))
		localcmd(sprintf("seta hud_seq_board %g\n", cvar("hud_seq_board") ? 0 : 1));
	y = y + rowh;

	if (HE_Chip("he_smerge", [x, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            "seg merge", cvar("hud_seq_merge"), psc))
		localcmd(sprintf("seta hud_seq_merge %g\n", cvar("hud_seq_merge") ? 0 : 1));
	if (HE_Chip("he_spspeed", [x + w * 0.52, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            "split u/s", cvar("hud_splits_speed"), psc))
		localcmd(sprintf("seta hud_splits_speed %g\n", cvar("hud_splits_speed") ? 0 : 1));
	y = y + rowh + 5 * psc;

	/*
	  THE CALM-NUMBERS PAIR.  Both cycle rather than sliding, because both are
	  small enumerations and a slider over four values is worse than a button that
	  says which one it is on.  The essay is above HUD_UpdateLatch in cl_hud.qc.
	*/
	mode = cvar("hud_update");
	if (mode < 0)       s = "rate: tick";
	else if (mode == 0) s = "rate: frame";
	else                s = sprintf("rate: %gHz", mode);
	if (HE_Chip("he_upd", [x, y, 0], [w * 0.48, rowh - 2 * psc, 0], s, mode != 0, psc))
	{
		// tick -> 10 -> 20 -> 30 -> frame -> tick.  It passes through "every
		// frame" so build 30's behaviour is reachable from anywhere in the cycle.
		if (mode < 0)        localcmd("seta hud_update 10\n");
		else if (mode == 10) localcmd("seta hud_update 20\n");
		else if (mode == 20) localcmd("seta hud_update 30\n");
		else if (mode == 0)  localcmd("seta hud_update -1\n");
		else                 localcmd("seta hud_update 0\n");
		ui_he_dirty = TRUE;
	}

	mode = cvar("hud_round");
	if (HE_Chip("he_round", [x + w * 0.52, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            mode ? sprintf("step %g", mode) : "step off", mode, psc))
	{
		if (mode == 1)      localcmd("seta hud_round 2\n");
		else if (mode == 2) localcmd("seta hud_round 5\n");
		else if (mode == 5) localcmd("seta hud_round 0\n");
		else                localcmd("seta hud_round 1\n");
		ui_he_dirty = TRUE;
	}
	y = y + rowh;

	// hud_scale LAST, because it resizes everything above it -- this panel
	// included -- so putting it at the top would move the button out from under
	// the cursor that just pressed it.
	mode = cvar("hud_scale");
	if (HE_Chip("he_scale", [x, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            sprintf("scale %g", mode), TRUE, psc))
	{
		if (mode < 1.5)      localcmd("seta hud_scale 1.5\n");
		else if (mode < 2)   localcmd("seta hud_scale 2\n");
		else if (mode < 2.5) localcmd("seta hud_scale 2.5\n");
		else if (mode < 3)   localcmd("seta hud_scale 3\n");
		else                 localcmd("seta hud_scale 1\n");
		ui_he_dirty = TRUE;
	}

	held = HE_Chip("he_done", [x + w * 0.52, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	               "done", TRUE, psc);
	y = y + rowh + 3 * psc;

	HUD_Text([x, y, 0], "drag to move   SHIFT: no snap", 7 * psc, HEC_DIM, 0.8);

	sui_end();
	Font_Reset();

	// AFTER sui_end, for the reason Scores_Draw's own hand-off note gives: acting
	// on the click inside the draw would tear down the cursor with sui's
	// click-once actions still latched, and the next frame would see the same
	// release again.
	if (held)
		HUD_EditClose();
};

/*
===========================================================================
  Defaults, the command, and input.
===========================================================================
*/
/*
  The shipped position of one element.

  A LITERAL LIST, not a re-read of anything.  registercvar cannot be asked what
  default it was given, and cvar_defstring would hand back whatever
  cfg/default.cfg last `set` -- the same number today and not the same THING.
  Two of these carry history that must not be quietly undone: hud_splits_y 0.20
  and hud_seq_x -0.25 are where builds 13 and 21 put them BY HAND to stop the
  split list and the segment column overlapping, and a "reset" that restored an
  older layout would recreate a bug that was fixed once already.
*/
void(float r) HE_Default =
{
	local string id;
	id = he_id[r];

	if (id == "timer")   localcmd("seta hud_timer_x 0.5\nseta hud_timer_y 0.035\n");
	if (id == "splits")  localcmd("seta hud_splits_x 0.045\nseta hud_splits_y 0.20\n");
	if (id == "seq")     localcmd("seta hud_seq_x -0.25\nseta hud_seq_y 0.5\n");
	if (id == "strafe")  localcmd("seta hud_strafe_x 0.5\nseta hud_strafe_y 0.42\n");
	if (id == "board")   localcmd("seta hud_board_x -1\nseta hud_board_y -1\n");
	if (id == "speed")   localcmd("seta hud_speed_x 0.5\nseta hud_speed_y 0.68\n");
	if (id == "keys")    localcmd("seta hud_keys_x 0\nseta hud_keys_y 0.84\n");
	if (id == "debug")   localcmd("seta hud_debug_x 0.012\nseta hud_debug_y 0.30\n");
	if (id == "saveloc") localcmd("seta hud_saveloc_x 0.018\nseta hud_saveloc_y 0.34\n");
	if (id == "gfx")     localcmd("seta hud_gfx_x 0.018\nseta hud_gfx_y 0.10\n");
	if (id == "mapinfo") localcmd("seta hud_mapinfo_x 0.99\nseta hud_mapinfo_y 0.02\n");

	ui_he_dirty = TRUE;
};

void() HUD_EditRegisterCvars =
{
	/*
	  `hud_edit` is a new name and nothing in the engine or the mod claims it --
	  CHECKED rather than assumed, because PF_cs_registercommand is
	  `if (!Cmd_Exists(...))` and returns nothing, so a collision is a silent
	  no-op and the command simply never arrives.  cl_watch.qc:2620 records the
	  same check for `replay`, and sv_player.qc:621 records this project already
	  losing time to a name that was taken.
	*/
	registercommand("hud_edit");

	/*
	  How close an edge has to be, in PIXELS and not in hud_scale units, before it
	  snaps.  Pixels because this is a mouse tolerance and a mouse does not know
	  what hud_scale is: 8 px is about a third of a fingertip's worth of hand
	  jitter at any resolution, and scaling it would make snapping sticky at
	  hud_scale 3 and useless at 1.  0 turns it off, which is the same as holding
	  SHIFT for the whole session.
	*/
	registercvar("hud_edit_snap", "8", CVAR_ARCHIVE);

	// Where the tool panel sits, as screen fractions.  Saved, because a panel you
	// have to move out of the way of your own layout every session is a panel you
	// have to move out of the way every session.  See the drag essay at the top.
	registercvar("hud_edit_panel_x", "0.010", CVAR_ARCHIVE);
	registercvar("hud_edit_panel_y", "0.080", CVAR_ARCHIVE);
};

void() HUD_EditStatus =
{
	local float i, r;
	local vector rp, rs;

	HE_BuildTable();
	print(sprintf("^5hud_edit^7: %s   snap %g px   %g rect(s) live\n",
	              ui_he_open ? "^2open^7" : "closed",
	              cvar("hud_edit_snap"), hude_n));

	/*
	  SPLIT IN TWO PRINTS, and that is not style.  fteqcc caps a varargs call at
	  eight arguments and SILENTLY DROPS the rest -- cl_main.qc's bootcheck block
	  carries the same note for the same reason.  Nine would have compiled with a
	  warning and printed a row with a missing number in it.
	*/
	for (i = 0; i < he_n; i = i + 1)
	{
		r = HE_Rect(he_id[i]);

		print(sprintf("  %-8s %-3s x %8.4f y %8.4f  ",
		              he_id[i],
		              (he_cvon[i] == "") ? "--" : (cvar(he_cvon[i]) ? "on" : "off"),
		              cvar(he_cvx[i]), cvar(he_cvy[i])));

		if (r < 0)
			print("not drawn\n");
		else
		{
			rp = hude_pos[r];
			rs = hude_size[r];
			print(sprintf("drawn %gx%g at %g,%g\n", rs_x, rs_y, rp_x, rp_y));
		}
	}

	print(sprintf("  hud_update %g   hud_round %g   hud_scale %g\n",
	              cvar("hud_update"), cvar("hud_round"), cvar("hud_scale")));

	/*
	  THE MEASURED LATCH RATE, and it is here because it is the one thing in this
	  build a screenshot cannot settle -- hud_update -1 is a claim about a counter
	  actually advancing, not a value you can read off the HUD.

	  IT EARNED ITS PLACE ON ITS FIRST RUN.  The latch was written against
	  servercommandframe, which reads perfectly plausibly and never advances in
	  this build; this line printed `4.0 Hz` -- the 0.25s stall floor -- instead of
	  the ~67 it should have, and that is the entire reason the source is
	  clientcommandframe now.  ~67 says the input frames are ticking; ~4 says only
	  the floor is firing and something upstream has stopped.
	*/
	print(sprintf("  latch %.1f Hz measured   (%s)\n", ui_hl_rate,
	              (cvar("hud_update") < 0) ? "per input frame"
	                : (cvar("hud_update") == 0 ? "every frame" : "fixed rate")));
};

/*
  tokenize FIRST.  CSQC_ConsoleCommand is handed the WHOLE COMMAND LINE, not the
  verb -- `cmd` for `hud_edit status` is the string "hud_edit status", so
  comparing cmd against "hud_edit" fails for every form that takes an argument
  and argv() then reads whatever the last tokenize left behind.  Build 30 shipped
  exactly that bug in Ghost_ConsoleCommand, and it presented as the command
  silently doing nothing at all, with no "unknown command" to go on.
*/
float(string cmd) HUD_EditConsoleCommand =
{
	local float i;

	tokenize(cmd);

	if (argv(0) != "hud_edit")
		return FALSE;

	if (argv(1) == "status") { HUD_EditStatus(); return TRUE; }
	if (argv(1) == "on")     { HUD_EditOpen();   return TRUE; }
	if (argv(1) == "off")    { HUD_EditClose();  return TRUE; }

	if (argv(1) == "reset")
	{
		HE_BuildTable();
		for (i = 0; i < he_n; i = i + 1)
			HE_Default(i);
		print("^5hud_edit^7: every panel back to its shipped position\n");
		return TRUE;
	}

	if (argv(1) == "save")
	{
		localcmd("cfg_save\n");
		ui_he_dirty = FALSE;
		print("^5hud_edit^7: written to ftesurf.cfg\n");
		return TRUE;
	}

	if (ui_he_open)
		HUD_EditClose();
	else
		HUD_EditOpen();
	return TRUE;
};

/*
  Input.

  IE_MOUSEABS RETURNS TRUE UNCONDITIONALLY, for the reason Scores_InputEvent
  documents: setcursormode(TRUE) makes the engine send absolute positions and it
  zeroes the accumulated delta ONLY when CSQC returns TRUE, so a handler that
  forgets leaves the view spinning under the cursor while you drag.

  MOUSE1 AND MOUSE2 ARE SWALLOWED because default.cfg binds them to +duck and
  +jump.  Returning TRUE also keeps them out of Keys_Edge in cl_main.qc, so the
  key block does not light the duck box every time you grab a panel.

  SHIFT IS OBSERVED AND PASSED ON.  It is the snap suspend, and it is watched
  here because Keys_Held only knows the eight movement binds -- +speed is not one
  of them (cl_keys.qc).  Returning FALSE keeps the engine's own shift behaviour
  intact, which matters for the console and for ESCAPE.

  ESCAPE closes, which the engine permits -- keys.c:3205, "csqc is allowed to
  steal the escape key (unless shift)" -- and is worth having because this opens
  from the console, and a modal you can only leave the way you came in is a trap.
*/
float(float evtype, float scanx, float chary, float devid) HUD_EditInputEvent =
{
	if (!ui_he_open)
		return FALSE;

	if (evtype == IE_MOUSEABS)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}

	if (evtype == IE_KEYDOWN || evtype == IE_KEYUP)
	{
		if (scanx == K_LSHIFT || scanx == K_RSHIFT)
		{
			ui_he_shift = (evtype == IE_KEYDOWN);
			return FALSE;
		}

		if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
		{
			sui_input_event(evtype, scanx, chary, devid);
			return TRUE;
		}

		if (evtype == IE_KEYDOWN && scanx == K_ESCAPE)
		{
			HUD_EditClose();
			return TRUE;
		}
	}

	return FALSE;
};
