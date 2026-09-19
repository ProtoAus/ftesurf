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

/*
  BUILD 66 -- THE TOOLTIP, LATCHED PER FRAME.

  Cleared at the top of the draw and set by whichever chip reports itself hovered.
  A single string rather than a per-chip lookup because sui only ever has one
  topmost hovered element (sui_sys.qc:296), so there is only ever one answer.
*/
string ui_he_tip;

/*
  BUILD 66 -- `reset all` IS ARMED BEFORE IT FIRES.

  It sits next to `done` and it undoes every layout decision in the panel, so a
  single click cannot be allowed to do it: the two chips are the same size, a few
  pixels apart, and one of them is pressed at the end of every session.

  ui_he_armat is cltime rather than time -- this is a UI timer and it has to keep
  running while the game does not.  Three seconds is long enough to read the chip
  change to `sure?` and short enough that an arm you walked away from is gone.
*/
float  ui_he_armed;
float  ui_he_armat;

void(float r) HE_Default;       // defined at the bottom; the panel's reset chips
                                // call it, and QuakeC wants the name first
void() HE_ResetAll;             // build 66, and the same story

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

/*
  BUILD 65: 12 -> 16, and the pair still has to move together.

  The note this replaces is worth keeping, because it is the record of the trap.
  12, not 10: the table was exactly full at ten conventions and ten rows, so the
  map info block's HE_Add would have been dropped on the floor by HE_Add's own
  bounds check and the panel would simply not have listed it -- no error, no
  warning, an element that does not exist as far as the editor is concerned.
  HUDE_MAX in cl_hud.qc is the other half of this pair and had the room that time.

  This build adds four rows -- boarding, net, results, crosshair -- to eleven, so
  both constants go to 16 rather than to exactly 15.  One spare row is the cheap
  way to not find this out the same way twice.
*/
#define HE_MAX 20                // Patch 361: the banner makes 16 rows; spares kept

/*
  The chip rows below the element list that are always there.  Named because the
  height formula used to carry it as a bare `+ 7` that was wrong the moment
  anyone added a row -- and it had already drifted by two before build 65 found
  it.

  BUILD 66: four, not three.  The rate/step pair, the xhair/reset-all pair, the
  `done` row, and the hint line.  `done` is alone on its row now because the chip
  beside it used to be `scale` -- which is gone -- and pairing it with `reset all`
  instead would put the panel's most destructive button next to the one pressed
  at the end of every session.
*/
#define HE_FIXEDROWS 4

string he_id[HE_MAX];
string he_label[HE_MAX];
string he_cvx[HE_MAX];          // "" = listed but NOT draggable (the crosshair)
string he_cvy[HE_MAX];
string he_cvon[HE_MAX];         // "" = no on/off toggle of its own
float  he_ox[HE_MAX];           // x is an offset from the centre, not a fraction
float  he_an[HE_MAX];
float  he_nw[HE_MAX], he_nh[HE_MAX];

/*
  BUILD 65 -- THE TEXT COLUMNS, SET BY A SECOND CALL RATHER THAN BY TWO MORE
  PARAMETERS.

  HE_Add is already nine arguments.  Plain QuakeC's calling convention has eight
  parameter registers, and fteqcc's extension past that is not something this
  project leans on anywhere else -- so rather than find out at runtime what an
  eleventh argument does, the two text columns are a separate setter that writes
  the row HE_Add just appended.  It also reads better: the rows stay one line
  each, and only the elements that HAVE text of their own carry a second line.

  he_cvsize "" means the element draws no text it owns -- the two menus, the
  crosshair, the key block's boxes -- and so gets no size row in its pane.
*/
string he_cvsize[HE_MAX];
string he_sizes[HE_MAX];        // the offered rungs, e.g. "32 40 48 64"

/*
  The N in the drawer's own `N * hud_scale`, so the panel can say what the
  element is CURRENTLY drawing at when its size cvar is 0.

  Without it the size row has no lit box at the default -- 0 matches none of the
  four numbers -- and a picker that cannot tell you where you are is worse than no
  picker.  This is the number that answers it, and it is a duplicate of a constant
  in the drawer, which is a real cost: if a drawer's base changes, this has to
  change with it or the panel will misreport.  The alternative was for every
  drawer to publish its size through a second registry, which is nine new globals
  and a second thing to forget.  One number per row, named here, is the cheaper
  wrong-if-neglected.
*/
float  he_base[HE_MAX];

/*
  BUILD 66 -- LISTED, OR HIDDEN BUT STILL DRAGGABLE.

  "Remove the Keys / Debug / Save menu / Video menu / Map info / Net / Results
  buttons ... allow players to move the elements around still."  Those are two
  requirements and only one of them is "delete the row".  A panel that vanished
  from the list AND stopped being draggable could not be put back where it was,
  and the same ask ends by wanting a general reset for exactly the case where
  something has gone wrong -- which a deleted row could not reach either.

  So this column splits the LIST from the TABLE.  The list loop honours it; the
  pass that draws the world outlines, `hud_edit reset` and `hud_edit status` do
  not.  Seven rows leave the panel and nothing loses a position, a size, or a
  reset.

  TRUE by default in HE_Add rather than requiring every row to opt in, so a row
  that forgets to call HE_Hide shows up as a visible extra line rather than as an
  element nobody can find.
*/
float  he_listed[HE_MAX];

float  he_n;

/*
  BUILD 65 -- WHICH ROW'S OPTIONS ARE OPEN.  -1 is none, and it is the state the
  editor opens in: the first thing this panel has to show is the LIST, because
  the list is how you find out an element exists.
*/
float  ui_he_sel;

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
	he_cvsize[he_n] = "";
	he_sizes[he_n]  = "";
	he_listed[he_n] = TRUE;
	he_n = he_n + 1;
};

/*
  Build 66.  Takes the row HE_Add just appended out of the side panel's list and
  leaves everything else about it alone.  Guarded exactly as HE_Text is, and for
  the same reason: he_listed[-1] is a boundcheck failure in the client VM, which
  takes the renderer down with it rather than misdrawing.
*/
void() HE_Hide =
{
	if (he_n <= 0)
		return;
	he_listed[he_n - 1] = FALSE;
};

/*
  Applies to the row HE_Add just appended.  Guarded rather than trusting the call
  order: he_cvsize[-1] is a boundcheck failure in the CLIENT VM, which takes the
  renderer down with it -- the same hazard Seq_Push's nested-ifs note in
  cl_board.qc exists for.
*/
void(string cvsize, string sizes, float base) HE_Text =
{
	if (he_n <= 0)
		return;
	he_cvsize[he_n - 1] = cvsize;
	he_sizes[he_n - 1]  = sizes;
	he_base[he_n - 1]   = base;
};

/*
  THE OFFERED SIZES ARE LADDER RUNGS, NOT ROUND NUMBERS.

  Each string below is a subset of the ladder the element's own FACE is baked at
  (sh_font.qc): display "24 32 40 48 64 80" for the timer and the speedometer,
  mono "8 10 12 ... 32" for the four number blocks, UI "8 12 16 ... 32" for the
  rest.  Font_Px snaps to the nearest rung, so an off-ladder size is not an error
  -- it is a resample, and a resample is the one thing a size picker must not be
  able to produce.

  The value named in each trailing comment is what build 64 drew at hud_scale 2,
  so it is always in the list: picking it is a no-op, and the shipped look stays
  reachable from the panel rather than only from `hud_edit reset`.
*/
void() HE_BuildTable =
{
	if (he_n)
		return;

	//      id         label         x cvar           y cvar           on cvar        ox  anchor    nw   nh
	HE_Add("timer",   "Timer",      "hud_timer_x",   "hud_timer_y",   "hud_timer",    0, HEA_CT,   90,  32);
	HE_Text("hud_timer_size",    "32 48 64 80", 32);     // display; 64 from build 66
	HE_Add("splits",  "Splits",     "hud_splits_x",  "hud_splits_y",  "hud_splits",   0, HEA_LC,  201,  40);
	HE_Text("hud_splits_size",   "12 14 16 20",  7);     // mono; 14 today
	HE_Add("seq",     "Segments",   "hud_seq_x",     "hud_seq_y",     "hud_seq",      1, HEA_RC,  110, 100);
	HE_Text("hud_seq_size",      "12 14 16 20",  8);     // mono; 16 today
	HE_Add("strafe",  "Strafe bar", "hud_strafe_x",  "hud_strafe_y",  "hud_strafe",   0, HEA_CT,  260,  40);
	HE_Text("hud_strafe_size",   "16 20 24 28", 10);     // mono from build 65; 20 today
	HE_Add("board",   "Board",      "hud_board_x",   "hud_board_y",   "hud_board",    0, HEA_CT,  120,  52);
	HE_Text("hud_board_size",    "16 20 24 28", 10);     // mono from build 65; 20 today
	HE_Add("boarding","Boarding",   "hud_boarding_x","hud_boarding_y","hud_boarding", 0, HEA_CT,  150,  44);
	HE_Text("hud_boarding_size", "16 20 24 28", 10);     // mono; 20 shipped
	HE_Add("speed",   "Speed",      "hud_speed_x",   "hud_speed_y",   "hud_speed",    0, HEA_CT,   70,  40);
	HE_Text("hud_speed_size",    "40 48 64 80", 24);     // display; 48 today
	HE_Add("banner",  "Banner",     "hud_banner_x",  "hud_banner_y",  "hud_banner",   0, HEA_CT,  300,  50);
	HE_Text("hud_banner_size",   "40 48 64 80", 32);     // the unit (hero = 32u); 64 at scale 2
	/*
	  BUILD 66 -- FROM HERE DOWN, EVERY ROW IS HIDDEN FROM THE LIST.

	  Seven panels nobody customises, named one by one in the ask.  They keep
	  their outlines, their drag, their reset and their line in `hud_edit status`;
	  they lose the button.  See he_listed.

	  The ORDER matters and is why they are all at the bottom: the list loop skips
	  them, so a hidden row in the middle would leave no visible gap -- but the
	  world pass and both console subcommands still walk the table in order, and
	  keeping the listed seven contiguous at the top means the two orders agree.
	*/
	HE_Add("keys",    "Keys",       "hud_keys_x",    "hud_keys_y",    "hud_keys",     0, HEA_LT,   64,  50);
	HE_Hide();
	HE_Add("debug",   "Debug",      "hud_debug_x",   "hud_debug_y",   "hud_debug",    0, HEA_LT,  110, 130);
	HE_Text("hud_debug_size",    "12 16 20 24",  8);     // UI; 16 today
	HE_Hide();
	HE_Add("saveloc", "Save menu",  "hud_saveloc_x", "hud_saveloc_y", "",             0, HEA_LT,   84, 145);
	HE_Hide();
	HE_Add("gfx",     "Video menu", "hud_gfx_x",     "hud_gfx_y",     "",             0, HEA_LT,  150, 180);
	HE_Hide();
	HE_Add("vote",    "Vote",       "hud_vote_x",    "hud_vote_y",    "",             0, HEA_LT,  110, 108);
	HE_Hide();
	HE_Add("mapinfo", "Map info",   "hud_mapinfo_x", "hud_mapinfo_y", "hud_mapinfo",  0, HEA_RT,   96,  56);
	HE_Text("hud_mapinfo_size",  "12 16 20 24",  8);     // UI; 16 today
	HE_Hide();

	/*
	  BUILD 65 -- THREE THAT WERE ALWAYS MISSING, AND ONE THAT CANNOT MOVE.

	  net and results have owned hud_*_x / hud_*_y since they were written
	  (cl_netmon.qc:122-124, cl_results.qc:189-192) and have simply never been
	  listed here, so the only way to move either was to type a cvar name -- which
	  is the exact complaint `hud_edit` was built to answer, left half-answered.
	  results already publishes its rect (cl_results.qc:927); net gets one in
	  NM_Draw with this build.

	  THE CROSSHAIR IS LISTED WITH NO POSITION CVARS -- he_cvx "" -- because it is
	  screen centre by definition, and a draggable one would be a bug you could
	  set and then have to find again.  It is here for its OPTIONS, which is what
	  this panel is now for; the pass that draws outlines skips it.

	  BUILD 66 REVISITS THAT LAST PARAGRAPH.  "Remove the crosshair button and
	  replace it with a single cycling button that switches between the three
	  crosshairs + off" -- so it keeps its table row (HE_Rect and the reset walk
	  still want it) and loses both its list line and its pane.  Three option rows
	  for what is one four-state choice was the wrong shape; the choice moved to a
	  chip in the fixed block, and size and opacity are pinned at 32 and 1 rather
	  than being offered.
	*/
	HE_Add("net",      "Net",       "hud_net_x",     "hud_net_y",     "hud_net",      0, HEA_LT,  128,  64);
	HE_Hide();
	HE_Add("results",  "Results",   "hud_results_x", "hud_results_y", "hud_results",  0, HEA_LT,  180, 120);
	HE_Hide();
	HE_Add("crosshair","Crosshair",  "",              "",             "",             0, HEA_CT,   32,  32);
	HE_Hide();
};

/*
===========================================================================
  BUILD 65 -- THE PER-ELEMENT OPTIONS.

  Everything an element knows about itself other than where it is: what unit it
  counts in, which of its parts are drawn, how many rows it keeps.  Until this
  build five of these sat in one shared block at the bottom of the panel with
  nothing saying which element they belonged to (hud_seq_units next to
  hud_splits_speed next to hud_scale), and hud_seq_rows was not reachable at all.

  PACKED STRINGS, NOT A PARALLEL ARRAY, and the reason is measured rather than
  stylistic: a QC array costs roughly eight times its data in progs size, so a
  string[6][40] table for forty options would cost more than the whole of this
  file.  An if-chain of literals costs the literals.  It is also the existing
  house idiom -- Gfx_Def in cl_gfx.qc:230 is the same shape for the same reason,
  and Gfx_Field is reused below rather than copied, so there is one parser.

      "cvar|Label|kind|values|names|tip"

    kind  t   toggle.  values and names unused; the chip lights or does not.
          c   cycle.  values "0 1 2", names "u/s;energy;both" -- the chip prints
              which one it is on, because a slider over three named states is
              worse than a button that says where it is (the argument the
              calm-numbers pair already makes below).

  Returns "" to end the element's list.  Rows are asked for in order and the
  first "" stops the walk, so a gap in the numbering would silently truncate a
  pane -- keep them contiguous.

  BUILD 66 -- THE SIXTH FIELD IS THE TOOLTIP, AND IT COST NOTHING TO ADD.

  "Pretty much all of these settings need a tooltip of some sort, idk what they
  mean."  Gfx_Field is arity-agnostic: it walks separators and returns "" when it
  runs out (cl_gfx.qc:425-426), so Gfx_Field(def, 5, "|") already answered ""
  for every row written before this build.  No parser change, no array, and the
  rows that do not want a tip simply do not carry one.

  ONE LINE, AND WRITE IT TIGHT.  The box is drawn unwrapped next to the cursor,
  so a sentence that runs past the window edge gets clamped against it rather
  than folded.  Say what the setting DOES, not what it is called -- the label
  already says that, and "Band: the band" is the tooltip nobody needs.

  The tip must not contain '|'.  It may contain spaces and ';' (only the names
  field is split on ';', and it is split before this one is read).
===========================================================================
*/
string(string id, float row) HE_OptDef =
{
	if (id == "seq")
	{
		/*
		  The four parts of a row, then the three that decide which rows exist at
		  all.  Build 65's row is
		      Air: 345e +100e 1.45s 80%
		  and every column in it can go, which is what "turn parts off and leave
		  parts on" means for this element.
		*/
		if (row == 0) return "hud_seq_name|Row label|t||"
		                     "|The Jump: / Bhop: / Air: / Board: / Ramp: word at the start of each row.";
		if (row == 10) return "hud_seq_hopname|Jump/Bhop|t||"
		                      "|Name air rows by how you left the ground. Off calls them all Air. Ramp exits stay Air either way.";
		if (row == 1) return "hud_seq_abs|Energy now|t||"
		                     "|Where that segment left you. The bottom row matches the e by the crosshair.";
		if (row == 2) return "hud_seq_delta|Gain/loss|t||"
		                     "|What that segment was worth on its own: the change across it.";
		if (row == 3) return "hud_seq_time|Duration|t||"
		                     "|How long the segment lasted, in seconds.";
		if (row == 4) return "hud_seq_pct|Air %|t||"
		                     "|Share of the gain your strafing alone could have made. Ramp energy is not in the divisor, so it can pass 100%.";
		if (row == 5) return "hud_seq_units|Units|c|0 1 2|u/s;energy;both"
		                     "|Count in speed, in height, or both stacked.";
		if (row == 6) return "hud_seq_board|Board rows|t||"
		                     "|The one-tick clip where you touch a ramp, as its own row.";
		if (row == 7) return "hud_seq_live|Live rows|t||"
		                     "|Show the segment you are in now, before it is finished.";
		if (row == 8) return "hud_seq_merge|Merge|c|0 1 2|off;artifacts;always"
		                     "|Join neighbouring rows of the same kind. artifacts repairs brief lost contact only.";
		if (row == 9) return "hud_seq_rows|Rows kept|c|5 10 15 24|5;10;15;24"
		                     "|How many finished segments stay on screen.";
		return "";
	}

	if (id == "boarding")
	{
		if (row == 0) return "hud_boarding_enter|Enter|t||"
		                     "|What you arrived at the ramp with.";
		if (row == 1) return "hud_boarding_leave|Leave|t||"
		                     "|What you came off it with.";
		// Build 66: Kept % and Ramp angle moved to the Board pane with their rows.
		if (row == 2) return "hud_boarding_units|Units|c|0 1 2|u/s;energy;both"
		                     "|Read the pair as speed, as height, or both stacked.";
		/*
		  NO ZERO IN THE FADE LISTS, and it is not an oversight.  Board_Alpha is
		  `if (when <= 0 || life <= 0.1) return 0`, so a fade of 0 does not mean
		  "never fade" -- it means the panel is permanently invisible, which is the
		  opposite of what a chip labelled "never" would promise.  999 s is longer
		  than any run and is the honest spelling of "stays up".
		*/
		if (row == 3) return "hud_boarding_fade|Fade|c|3 6 999|3s;6s;stay"
		                     "|How long a reading stays up after the ramp. stay never fades.";
		return "";
	}

	if (id == "board")
	{
		if (row == 0) return "hud_board_seg|Segment line|t||"
		                     "|What the flight before the touchdown was worth.";
		if (row == 1) return "hud_board_grade|Grade word|t||"
		                     "|perfect / good / okay / bad / terrible.";
		if (row == 2) return "hud_board_kept|Kept %|t||"
		                     "|How much of your speed survived the plane.";
		if (row == 3) return "hud_board_cost|Cost line|t||"
		                     "|What the touchdown itself took off you.";
		if (row == 4) return "hud_board_ramp|Ramp angle|t||"
		                     "|How steep the face was, in degrees off flat.";
		if (row == 5) return "hud_board_words|Wording|c|0 1|short;full"
		                     "|short drops the label words -- kept, board, deg -- and leaves the numbers.";
		if (row == 6) return "hud_board_fade|Fade|c|3 6 999|3s;6s;stay"
		                     "|How long a reading stays up after the ramp. stay never fades.";
		if (row == 7) return "hud_seq_units|Units|c|0 1 2|u/s;energy;both"
		                     "|Shared with the segment column, so the two never disagree.";
		return "";
	}

	if (id == "speed")
	{
		/*
		  Energy is the speedometer's second line and stays welded to it, so its
		  three-state and its reference live in THIS pane rather than in a row of
		  their own.  hud_energy_size is the one size in the tree that is not on
		  he_cvsize, for exactly that reason: one element, two text sizes.
		*/
		if (row == 0) return "hud_energy|Energy line|c|0 1 2|off;units;u/s"
		                     "|The e figure under the speedometer: height you could still trade for speed.";
		/*
		  Build 66: 64 added -- "make energy be allowed to switch to 64 font size".
		  It is a rung of FONT_DISPLAY_SIZES, so it snaps rather than resampling.

		  AND `auto` IS IN THE LIST NOW, which build 65 left out and the first
		  capture run of this build caught on screen.  The default is 0, meaning
		  "follow hud_scale"; 0 matched none of the offered values, so HE_OptIndex
		  returned -1 and the chip fell back to printing the raw number -- a button
		  reading `0` under a line drawn at 32 px.  That fallback is right for a
		  value somebody typed at the console and wrong for the shipped default,
		  and the fix is to stop pretending 0 is not one of the choices.
		*/
		if (row == 1) return "hud_energy_size|Energy size|c|0 32 40 48 64|auto;32;40;48;64"
		                     "|Text size of that second line. auto follows the HUD scale.";
		if (row == 2) return "hud_energy_ref|Zero at|c|0 1|start zone;last jump"
		                     "|What counts as zero energy: where the run began, or where you last left the ground.";
		return "";
	}

	if (id == "splits")
	{
		if (row == 0) return "hud_splits_speed|Speed column|t||"
		                     "|How fast you crossed each checkpoint.";
		if (row == 1) return "hud_splits_energy|Energy column|t||"
		                     "|The e figure at each checkpoint. Slides left when the speed column is off.";
		if (row == 2) return "hud_splits_class|Class column|t||"
		                     "|A mark in the left gutter per stage: ! you cheated in it, ~ you loaded a save in it.";
		return "";
	}

	if (id == "strafe")
	{
		if (row == 0) return "hud_strafe_strict|Strict ramp|t||"
		                     "|On a ramp with no usable plane, show nothing rather than a flat-air target.";
		if (row == 1) return "hud_strafe_orient|Orient plane|t||"
		                     "|Work out which way the ramp faces before grading. Off uses the raw plane.";
		if (row == 2) return "hud_strafe_band|Band|c|0.5 1 2|0.5;1.0;2.0"
		                     "|How far off the ideal rate fills the bar completely. Smaller is twitchier.";
		if (row == 3) return "hud_strafe_curve|Curve|c|0.5 1|sqrt;linear"
		                     "|Shape of the fill. sqrt magnifies small errors near the centre.";
		if (row == 4) return "hud_strafe_groundhold|Hop hold|c|0 0.12 0.25|off;0.12s;0.25s"
		                     "|Ignore ground contact shorter than this, so a bhop landing does not flicker the bar.";
		if (row == 5) return "hud_strafe_rates|Rate digits|t||"
		                     "|The two numbers above the bar: what you are turning at, and what you should be.";
		if (row == 6) return "hud_strafe_why|Reason text|t||"
		                     "|The sentence that appears when there is no target -- ramp: no plane held, and so on.";
		if (row == 7) return "hud_strafe_best|Best line|c|0 1 2|off;short;full"
		                     "|The line under the bar. short says u/s/tick instead of u/s per tick at best.";
		return "";
	}

	/*
	  BUILD 66.  The timer had no pane at all until now -- "never had a setting to
	  change the font size of the Subtext".  It is a cycle rather than a second
	  he_cvsize row for the reason hud_energy_size is: one element, two text
	  sizes, and he_cvsize holds one.
	*/
	if (id == "banner")
	{
		if (row == 0) return "hud_banner_stages|Stage banners|t||"
		                     "|A strip for each stage you pass in a full run. Off shows the one-line toast.";
		if (row == 1) return "hud_banner_hold|Hold|c|2 3.5 5|2s;3.5s;5s"
		                     "|How long it stays up. Stage strips stay 70% as long.";
		if (row == 2) return "hud_banner_sound|Sound|t||"
		                     "|Plays sound/ftesurf/complete, pb or wr .wav if you add them; a missing file is skipped.";
		if (row == 3) return "hud_banner_chat|Chat line|t||"
		                     "|One chatbox line per finish: your time, the delta to your PB and the placement.";
		return "";
	}

	if (id == "timer")
	{
		// `auto` first, and it is the default -- see the note on hud_energy_size
		// about why leaving 0 out of the list makes the chip print a bare `0`.
		if (row == 0) return "hud_timer_sub_size|Subtext size|c|0 12 16 20 24|auto;12;16;20;24"
		                     "|Size of the status and pb lines under the clock. auto follows the HUD scale.";
		// BUILD 86: the pace colour.  A row here and not only a cvar, because
		// HE_ResetAll walks these rows -- a switch left out of the list is one the
		// reset button cannot recover.
		if (row == 1) return "hud_timer_pace|PB pace colour|t||"
		                     "|Colour the running clock green while you are ahead of your own PB at the last checkpoint or stage, red once you are behind. Needs a PB on the leg; public lobbies do not keep one.";
		return "";
	}

	if (id == "mapinfo")
	{
		if (row == 0) return "hud_mapinfo_timeleft|Time left|t||"
		                     "|On a server with a time limit: the time left on this map, then the next map.";
		return "";
	}

	return "";
};

/*
  BUILD 66 -- WHAT EACH ELEMENT IS, for the name chip in the list.

  Separate from HE_OptDef because the list rows have no option row to hang a
  sixth field on, and separate from he_label because a label is a name and this
  is a sentence.  Same if-chain-of-literals idiom and the same reason: an array
  of sixteen strings costs about eight times what the strings do.

  The seven listed elements answer; the hidden ones do not need to, because the
  only way to see their name chip is to unhide them.
*/
string(string id) HE_Tip =
{
	if (id == "timer")    return "The run clock, and the status line under it.";
	if (id == "splits")   return "Checkpoint times against your best, as you pass each one.";
	if (id == "seq")      return "One row per segment of flight: what each was worth.";
	if (id == "strafe")   return "How close your turn rate is to the ideal one, right now.";
	if (id == "board")    return "How well the last ramp contact went.";
	if (id == "boarding") return "What you entered and left the last ramp with.";
	if (id == "speed")    return "Horizontal speed, and the energy line under it.";
	if (id == "banner")   return "Across the screen when you finish the map, a bonus or a stage.";
	return "";
};

float(string id) HE_OptCount =
{
	local float n;
	n = 0;
	while (HE_OptDef(id, n) != "")
		n = n + 1;
	return n;
};

/*
  The index of the value `cv` currently holds within a cycle's value list, or -1.

  COMPARED AS FLOATS, NOT AS STRINGS.  "1" and "1.0" and "1.000000" are the same
  setting and cvar_string hands back whichever spelling was last written -- a
  string compare would show the chip as "not on any of these" for a value that is
  exactly one of them, which is how a working setting reads as a broken one.
*/
float(string values, float v) HE_OptIndex =
{
	local float i, n;

	n = tokenize(values);
	for (i = 0; i < n; i = i + 1)
		if (stof(argv(i)) == v)
			return i;
	return -1;
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

	// Build 66: never reopen already armed.  An arm that survived a close would
	// make the FIRST click of the next session destroy the layout.
	ui_he_armed = FALSE;
	ui_he_tip   = "";

	// Build 65: opens on the LIST, never on a pane.  Which element you want is the
	// first question, and a panel that reopened onto whatever you last expanded
	// would answer a question you had not asked yet.
	ui_he_sel   = -1;

	UI_CursorClaim(UIC_HUDEDIT);

	print("^5hud_edit^7: drag a panel to move it.  SHIFT suspends snapping.\n");
	print("           click a name for its settings, the box on the right to show/hide.\n");
	print("           ESC, `done` or `hud_edit` to finish.\n");
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

/*
  A labelled chip.  Returns TRUE on the frame it is released.

  BUILD 66 -- THE SEVENTH ARGUMENT IS ITS TOOLTIP, and it is a parameter rather
  than a second call beside each site because the id is built with strcat at most
  of them: a separate HE_TipFor(id, tip) would rebuild that string a second time
  every frame for every chip, to say something only one chip at a time can use.

  Seven is under the eight-register ceiling that HE_Add's note describes, with
  one slot left.  Pass "" for a chip whose label already says everything.

  The tip is LATCHED, not drawn -- ui_he_tip is painted once at the end of the
  panel, because a box drawn here would be covered by every chip registered after
  it.  Hover is sui's, already consulted twice above for the border colour.
*/
float(string id, vector pos, vector sz, string label, float on, float sc,
      string tip) HE_Chip =
{
	sui_action_element(pos, sz, id, sui_noop);
	sui_fill(pos, sz, on ? '0.16 0.30 0.44' : '0.12 0.13 0.16', 1, 0);
	sui_border_box(pos, sz, 1,
	               sui_is_hovered(id) ? HEC_HOT : (on ? HEC_LINE : HEC_GHOST),
	               sui_is_hovered(id) ? 1.0 : 0.5, 0);
	HUD_Text([pos_x + 4 * sc, pos_y + (sz_y - 8 * sc) * 0.5, 0], label,
	         8 * sc, on ? HEC_TEXT : HEC_DIM, 1);

	if (tip != "")
	if (sui_is_hovered(id))
		ui_he_tip = tip;

	return sui_is_released(id);
};

/*
  BUILD 66 -- WHAT THE CURSOR IS OVER, SAID IN WORDS.

  sui has no tooltip widget and the menu has no prior art for one -- the closest
  thing in the tree is m_main.qc:3131, which is a permanently-drawn second line
  rather than anything hover-gated.  So this is the whole mechanism: one latched
  string and one box.

  DRAWN WITH drawfill/HUD_Text RATHER THAN sui, and after every sui_action_element
  the panel registers.  It is not a control -- it must never take a click, and it
  must never be hit-tested, or hovering a chip would move the hover to the tip and
  the tip would vanish, which oscillates at frame rate.

  Clamped against all four edges.  Below-right of the cursor by default, flipped
  ABOVE it when that would run off the bottom -- flipping to the left instead
  would put the box under the panel it is describing.
*/
void(vector scr, float psc) HE_DrawTip =
{
	local vector tp, ts;
	local float tsz;

	if (ui_he_tip == "")
		return;

	tsz = 7 * psc;
	ts  = [stringwidth(ui_he_tip, TRUE, [tsz, tsz]) + 10 * psc, tsz + 8 * psc, 0];
	tp  = _cursor_position + [14 * psc, 18 * psc, 0];

	if (tp_x + ts_x > scr_x) tp_x = scr_x - ts_x;
	if (tp_y + ts_y > scr_y) tp_y = _cursor_position_y - ts_y - 6 * psc;
	if (tp_x < 0) tp_x = 0;
	if (tp_y < 0) tp_y = 0;

	drawfill(tp, ts, '0.03 0.04 0.06', 0.95, 0);
	drawfill(tp, [ts_x, psc, 0], HEC_HOT, 0.75, 0);
	HUD_Text([tp_x + 5 * psc, tp_y + 4 * psc, 0], ui_he_tip, tsz, HEC_TEXT, 1);
};

void(vector scr) HUD_EditDraw =
{
	local float i, k, r, sc, psc, lim, held, mode, x, y, w, rowh, panw;
	local vector p, sz, a, b, np, fix, op, os;
	local string s;

	// Build 65: the list rows and the options pane.  `j` is the pane's own loop and
	// must not be `i` -- the pane is drawn INSIDE the element loop, so reusing the
	// outer counter would end the list at the first element with options.
	local float  j, n, nopt, selrow, on, cur, ox, ow, bx, panh;
	local string def, ocv, olab, okind, oval, onam, otip;

	// Build 66: the list row's three boxes.  sqw is square by construction -- it is
	// the row's own inner height -- and namew is what is left after the other two.
	local float  sqw, rstw, namew, nlist;

	if (!ui_he_open)
		return;

	// Either of these can be opened from a bind while this is up.  They own the
	// cursor and draw over everything; step aside rather than fight for it.
	if (rec_wt_open || rec_sb_open)
	{
		HUD_EditClose();
		return;
	}

	// Build 66.  Rebuilt every frame from whatever is hovered NOW: a latch that
	// persisted would keep describing a chip the cursor had left.
	ui_he_tip = "";

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
		/*
		  BUILD 65: a row with no position cvars is listed in the panel and has no
		  presence out in the world.  The crosshair is screen centre by definition,
		  so there is nothing to outline, nothing to snap to and nothing to drag --
		  and a placeholder box drawn dead centre would sit on top of the strafe
		  bar and the speedometer, which are the two things you most need to see
		  while laying a HUD out.
		*/
		if (he_cvx[i] == "")
			continue;

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

	/*
	  BUILD 65 -- AND IT SHRINKS RATHER THAN RUNNING OFF THE BOTTOM.

	  The list is five rows longer than build 64's and an open pane adds up to
	  twelve more, so the worst case is roughly twice the old height.  The clamp
	  below only ever MOVED the panel, which cannot help once it is taller than the
	  window: the `done` chip would sit past the bottom edge with no way to press
	  it, and this panel is modal.

	  Halving psc is the whole fix and it is honest about what it costs -- the
	  chips get small, but small and reachable beats crisp and off-screen.  Tested
	  against the real worst case (16 rows, the segment pane's ten options, four
	  fixed) rather than against the current one, because the current one is what
	  the `+ 7` was fitted to and that is how it drifted.
	*/
	rowh = 15 * psc;
	panw = 170 * psc;

	/*
	  BUILD 65 -- THE HEIGHT IS COMPUTED, NOT CONSTANT.

	  It used to be `rowh * (he_n + 7)`, with the 7 a hand-count of the fixed chip
	  rows at the bottom.  Both halves of that have moved: the list is five rows
	  longer, and the fixed block is shorter because the five orphaned switches
	  went into their owners' panes -- but the real change is that the panel now
	  GROWS when a pane is open, by exactly the number of options that element has.

	  nopt is counted once here and reused below rather than asked for twice: it
	  walks HE_OptDef, which is an if-chain over string literals, and the draw
	  loop would otherwise pay for it per frame per row.

	  The four fixed rows are: the two calm-numbers chips, the scale/done pair,
	  and the hint line.  Named rather than a bare constant so the next person to
	  add one has somewhere to look.
	*/
	/*
	  NESTED IFS, NOT `&&`, AND THIS ONE WAS MEASURED RATHER THAN REASONED.

	  QuakeC's && is OP_AND and evaluates BOTH sides, and fteqcc's ternary
	  evaluates both branches -- so `(sel >= 0 && sel < he_n) ? he_id[sel] : 0`
	  reads he_id[-1] whenever nothing is selected, which is the state the editor
	  OPENS in.  That is a boundcheck failure in the client VM, and a boundcheck
	  failure takes the renderer down with it: the first capture run of this build
	  died on the frame `hud_edit on` was issued, with

	      Progs boundcheck failed. Value is -1. Must be 0<=value<16
	      CSQC_Abort -> Shutting down csqc -> Host_EndGame

	  i.e. the editor did not misdraw, it ended the session.  cl_board.qc's
	  Seq_Push carries the same warning about the same operator for the same
	  reason, and this is the second time it has been earned.
	*/
	nopt = 0;
	if (ui_he_sel >= 0)
	if (ui_he_sel < he_n)
	if (he_listed[ui_he_sel])
	{
		// Build 66: no `+ 1` for a reset row any more -- that row moved onto the
		// list line, where it costs no height at all.  And a HIDDEN row's pane is
		// never drawn, so it must not be paid for either -- the list loop skips it
		// before it reaches the pane, and a height that counted it would open a
		// gap the panel could not fill.
		nopt = HE_OptCount(he_id[ui_he_sel]);
		if (he_cvsize[ui_he_sel] != "")
			nopt = nopt + 1;                        // the size row
	}

	// Build 66: the LIST is shorter than the table now.  Counted rather than
	// tracked in HE_Add, because he_listed is the authority and a second counter
	// is a second thing to get out of step.
	nlist = 0;
	for (i = 0; i < he_n; i = i + 1)
		if (he_listed[i])
			nlist = nlist + 1;

	// Its own local rather than writing sz_y early: `sz` still holds the last
	// element's box from pass one, and assigning one component of a vector the
	// compiler thinks is unset is a warning that would be right in general.
	panh = rowh * (nlist + nopt + HE_FIXEDROWS) + 26 * psc;
	if (panh > scr_y && psc > 1)
	{
		psc  = 1;
		rowh = 15 * psc;
		panw = 170 * psc;
		panh = rowh * (nlist + nopt + HE_FIXEDROWS) + 26 * psc;
	}

	p    = [scr_x * cvar("hud_edit_panel_x"), scr_y * cvar("hud_edit_panel_y"), 0];
	sz   = [panw, panh, 0];

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

	/*
	===========================================================================
	  BUILD 65 -- THE LIST, AND THE PANE THAT OPENS UNDER IT.

	  Build 31's row was one chip that did one thing: the name WAS the on/off
	  switch, with `reset` beside it.  That was right when position and visibility
	  were all an element had.  Now that each one carries between two and ten
	  settings of its own, the name has to become the way IN to them, and the
	  show/hide has to move somewhere it can still be reached in one click.

	      [ Segments                  ] [x]
	          Text size  12 [14] 16  20
	          Row label            [on]
	          ...

	  So: the wide chip SELECTS, the narrow box on the right SHOWS/HIDES, and the
	  selected element's options are drawn inline underneath it, pushing the rows
	  below down.

	  AN ACCORDION AND NOT A FLOATING DROPDOWN, deliberately.  sui has no dropdown
	  widget, and the map browser DELETED the one it had (m_main.qc:3048-3061,
	  "ONE box, and the list is always open") after the floating version proved to
	  be a second thing to dismiss.  A pane that is part of the panel also cannot
	  fall outside it, which matters here because this panel is the only thing on
	  screen that must never let a click through to the world behind it.
	===========================================================================
	*/
	for (i = 0; i < he_n; i = i + 1)
	{
		// Build 66.  Hidden rows keep everything except the line in this list --
		// see he_listed.  Skipped BEFORE selrow is computed, so a hidden element
		// that hud_edit <id> selected cannot leave an invisible pane open.
		if (!he_listed[i])
			continue;

		selrow = (ui_he_sel == i);

		/*
		  BUILD 66 -- THREE CONTROLS, AND THE TOGGLE IS A SQUARE.

		      [ Segments            ][ ][reset]

		  The toggle used to print a lowercase `x` when the element was on.  Two
		  things were wrong with that: `x` is the glyph every UI in the world uses
		  for CLOSE, so the state it marked read as the opposite of what it meant;
		  and HE_Chip left-aligns its label at +4*sc, which in a box that narrow
		  put it visibly off centre.  The fill already says on or off -- it is the
		  same lit/unlit that every other chip in this panel uses -- so the glyph
		  was never carrying the signal anyway.

		  SQUARE means width equal to height, derived rather than a fraction of w:
		  at 0.15w it was a rectangle that got wider as the panel did.

		  `reset` returns to the row, where build 64 had it.  Build 65 moved it
		  into the pane to stop it competing with the name for width -- true, but
		  it also meant the fix for "I dragged this somewhere silly" was three
		  clicks deep, and that is the one thing you reach for in a hurry.
		*/
		sqw   = rowh - 2 * psc;
		rstw  = 28 * psc;                   // "reset" at 8*psc, plus HE_Chip's 4 pad
		namew = w - sqw - rstw - 4 * psc;

		if (HE_Chip(strcat("he_sel_", he_id[i]), [x, y, 0],
		            [namew, rowh - 2 * psc, 0],
		            he_label[i], selrow, psc, HE_Tip(he_id[i])))
		{
			// Click the open one to close it.  A pane you can only swap and never
			// dismiss makes the list unreadable.
			ui_he_sel = selrow ? -1 : i;
		}

		/*
		  An element with no hud_<id> cvar draws the box dim and unclickable --
		  HE_Chip would happily register a hit rect for it, and a control that
		  responds and changes nothing is worse than one that visibly cannot.
		*/
		if (he_cvon[i] != "")
		{
			on = cvar(he_cvon[i]);
			if (HE_Chip(strcat("he_on_", he_id[i]),
			            [x + namew + 2 * psc, y, 0], [sqw, sqw, 0],
			            "", on, psc, "Show or hide this element."))
				localcmd(sprintf("seta %s %g\n", he_cvon[i], on ? 0 : 1));
		}
		else
		{
			sui_border_box([x + namew + 2 * psc, y, 0], [sqw, sqw, 0],
			               1, HEC_GHOST, 0.3, 0);
		}

		/*
		  An element with no position cvars has nothing to reset, so it gets a dim
		  box rather than a chip that does nothing.  Nothing in the list reaches
		  that branch today -- the crosshair was the only such row and it is
		  hidden -- but the table still allows one.
		*/
		if (he_cvx[i] != "")
		{
			if (HE_Chip(strcat("he_rst_", he_id[i]),
			            [x + namew + sqw + 4 * psc, y, 0],
			            [rstw, rowh - 2 * psc, 0],
			            "reset", FALSE, psc,
			            "Put this element back where it shipped."))
				HE_Default(i);
		}
		else
			sui_border_box([x + namew + sqw + 4 * psc, y, 0],
			               [rstw, rowh - 2 * psc, 0], 1, HEC_GHOST, 0.3, 0);

		y = y + rowh;

		if (!selrow)
			continue;

		/*
		  ---- the pane ----

		  Indented, and on a dimmer ground, so the list stays readable as a list
		  with eight rows of settings sitting in the middle of it.
		*/
		ox = x + 8 * psc;
		ow = w - 8 * psc;

		/*
		  THE SIZE ROW FIRST, because it is the one option every text element has
		  and the one the ask was most specific about: "3-4 selectable boxes with
		  the font size written in them".  So the boxes carry the PIXEL SIZE and
		  nothing else.

		  THE LABEL CARRIES THE SIZE IN FORCE, and that is not decoration.  At the
		  default -- hud_<id>_size 0, "follow hud_scale" -- NONE of the four boxes
		  is lit, because 0 matches none of them.  That is correct (no size has
		  been chosen) and it is also unreadable: four numbers with nothing lit
		  cannot tell you where you are, which is the one thing a picker has to do.
		  Lighting the nearest box instead would be worse -- at hud_scale 1 the
		  segment column draws at 8 px and the nearest offered rung is 12, so the
		  panel would be pointing at a size the element is not using.

		  So the label says it outright: "size 16 auto" when it is derived, "size
		  20" when it was picked.  he_base is the drawer's own N in N*hud_scale;
		  the drawn value can still differ by a rung where Font_Px snaps (splits at
		  hud_scale 1 asks for 7 and is baked at 8), which is why it reads `auto`
		  rather than claiming to be exact.
		*/
		if (he_cvsize[i] != "")
		{
			sui_fill([x, y, 0], [w, rowh, 0], HEC_PANEL, 0.5, 0);

			cur = cvar(he_cvsize[i]);
			if (cur >= 1) s = sprintf("size %g", cur);
			else          s = sprintf("size %g auto", he_base[i] * sc);

			HUD_Text([ox, y + (rowh - 7 * psc) * 0.5, 0], s,
			         7 * psc, HEC_DIM, 0.9);

			k = tokenize(he_sizes[i]);
			if (k > 4) k = 4;               // the layout below is cut for four

			for (j = 0; j < k; j = j + 1)
			{
				/*
				  RE-TOKENIZED EVERY ITERATION, on purpose.

				  The token list is a single global, and this loop calls HE_Chip
				  between one argv() and the next.  HE_Chip does not tokenize today
				  -- but three functions in sui_sys.qc do (sui_binder and the two
				  bind helpers), that file is shared with menu.dat, and a widget
				  gaining a keybind hint later would silently rewrite this list
				  mid-loop.  The failure would be size chips labelled with each
				  other's numbers, which looks like a layout bug and is not one.

				  One builtin call per chip against a four-entry string.  Cheaper
				  than the note explaining why it was safe.
				*/
				tokenize(he_sizes[i]);
				s  = argv(j);
				bx = ox + ow * 0.30 + (ow * 0.70 / k) * j;
				if (HE_Chip(strcat("he_sz_", he_id[i], s),
				            [bx, y + 1 * psc, 0],
				            [ow * 0.70 / k - 2 * psc, rowh - 4 * psc, 0],
				            s, cur == stof(s), psc,
				            "Text size in pixels. Click the lit one to go back to auto."))
				{
					// Clicking the lit box clears back to 0 -- "follow hud_scale",
					// which is build 64's look and is otherwise unreachable from
					// the panel once a size has been picked.
					localcmd(sprintf("seta %s %s\n", he_cvsize[i],
					                 (cur == stof(s)) ? "0" : s));
					ui_he_dirty = TRUE;
				}
			}
			y = y + rowh;
		}

		/*
		  THEN THE ELEMENT'S OWN OPTIONS, straight out of HE_OptDef.  One row each,
		  label on the left and the control right-aligned, so a pane of ten reads
		  as a column rather than as ten differently-shaped rows.
		*/
		nopt = HE_OptCount(he_id[i]);
		for (j = 0; j < nopt; j = j + 1)
		{
			def  = HE_OptDef(he_id[i], j);
			ocv  = Gfx_Field(def, 0, "|");
			olab = Gfx_Field(def, 1, "|");
			okind= Gfx_Field(def, 2, "|");
			oval = Gfx_Field(def, 3, "|");
			onam = Gfx_Field(def, 4, "|");
			otip = Gfx_Field(def, 5, "|");     // build 66; "" on rows without one

			sui_fill([x, y, 0], [w, rowh, 0], HEC_PANEL, 0.5, 0);
			HUD_Text([ox, y + (rowh - 7 * psc) * 0.5, 0], olab,
			         7 * psc, HEC_DIM, 0.9);

			if (okind == "t")
			{
				on = cvar(ocv);
				if (HE_Chip(strcat("he_o_", ocv), [ox + ow * 0.62, y + 1 * psc, 0],
				            [ow * 0.38, rowh - 4 * psc, 0],
				            on ? "on" : "off", on, psc, otip))
				{
					localcmd(sprintf("seta %s %g\n", ocv, on ? 0 : 1));
					ui_he_dirty = TRUE;
				}
			}
			else
			{
				/*
				  A CYCLE, AND IT SHOWS THE NAME RATHER THAN THE NUMBER.  Same
				  argument the calm-numbers pair below has always made: these are
				  small enumerations, and a button that says "energy" beats a
				  slider that says 1.

				  An index of -1 is a value nobody offered -- somebody typed it at
				  the console -- and it prints as the raw number rather than being
				  silently snapped, because a picker that rewrites a setting just
				  for being unfamiliar is how a deliberate value disappears.  The
				  next click moves to the first offered one.
				*/
				cur = cvar(ocv);
				k   = HE_OptIndex(oval, cur);

				if (k < 0) s = ftos(cur);
				else       s = Gfx_Field(onam, k, ";");

				if (HE_Chip(strcat("he_o_", ocv), [ox + ow * 0.62, y + 1 * psc, 0],
				            [ow * 0.38, rowh - 4 * psc, 0],
				            s, cur != 0, psc, otip))
				{
					// tokenize AFTER the chip has been drawn: HE_Chip calls
					// HUD_Text, and a tokenize between argv() reads is exactly the
					// bug HUD_EditConsoleCommand's header warns about.
					n = tokenize(oval);
					if (n > 0)
					{
						k = (k < 0) ? 0 : ((k + 1) % n);
						localcmd(sprintf("seta %s %s\n", ocv, argv(k)));
						ui_he_dirty = TRUE;
					}
				}
			}
			y = y + rowh;
		}

		/*
		  Build 66: the pane ENDS here.  `reset pos` was its last row and is now a
		  chip on the list row itself -- see the three-control note above.
		*/
	}

	y = y + 5 * psc;
	drawfill([x, y, 0], [w, 1, 0], HEC_GHOST, 0.3, 0);
	y = y + 5 * psc;

	/*
	  THE CALM-NUMBERS PAIR.  Both cycle rather than sliding, because both are
	  small enumerations and a slider over four values is worse than a button that
	  says which one it is on.  The essay is above HUD_UpdateLatch in cl_hud.qc.
	*/
	mode = cvar("hud_update");
	if (mode < 0)       s = "rate: tick";
	else if (mode == 0) s = "rate: frame";
	else                s = sprintf("rate: %gHz", mode);
	if (HE_Chip("he_upd", [x, y, 0], [w * 0.48, rowh - 2 * psc, 0], s, mode != 0, psc,
	            "How often the speed, energy and turn-rate numbers re-read. Not the timer."))
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
	            mode ? sprintf("step %g", mode) : "step off", mode, psc,
	            "Round those same numbers to the nearest 1, 2 or 5 u/s. 1 changes nothing."))
	{
		if (mode == 1)      localcmd("seta hud_round 2\n");
		else if (mode == 2) localcmd("seta hud_round 5\n");
		else if (mode == 5) localcmd("seta hud_round 0\n");
		else                localcmd("seta hud_round 1\n");
		ui_he_dirty = TRUE;
	}
	y = y + rowh;

	/*
	  BUILD 66 -- THE CROSSHAIR IS ONE CHIP.

	  "Remove the crosshair button and replace it with a single cycling button
	  that switches between the three crosshairs + off."  It is in the fixed block
	  rather than the list because it is the one HUD element with no position and
	  no size to pick -- there is nothing for a pane to hold.

	  0 IS OFF, and that is a change of meaning from build 65, where 0 meant "let
	  the engine draw its own".  A four-state cycle cannot express both, and the
	  ask names off.  The engine's is still reachable as -1, which prints as its
	  own label if anyone sets it.
	*/
	mode = cvar("hud_crosshair");
	if (mode < 0)       s = "xhair engine";
	else if (mode < 1)  s = "xhair off";
	else                s = sprintf("xhair %g", mode);
	if (HE_Chip("he_xhair", [x, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            s, mode >= 1, psc,
	            "Cycle the three crosshairs and off. 32 px, fully opaque."))
	{
		if (mode >= 1 && mode < 3) localcmd(sprintf("seta hud_crosshair %g\n", mode + 1));
		else if (mode >= 3)        localcmd("seta hud_crosshair 0\n");
		else                       localcmd("seta hud_crosshair 1\n");
		ui_he_dirty = TRUE;
	}

	/*
	  BUILD 66 -- `reset all`, AND IT ASKS FIRST.

	  "Hit a general reset if anything goes really bad."  It undoes every position,
	  every size, every show/hide and every option in every pane -- so it is the
	  one chip in this panel a mis-click cannot be allowed to fire, and it sits one
	  row above `done`, which is pressed at the end of every session.

	  ARMED, NOT CONFIRMED BY A DIALOG: a modal over a modal is worse, and this
	  panel already owns the cursor.  The chip says `sure?` in the armed state and
	  disarms itself after three seconds.
	*/
	if (ui_he_armed)
	if (cltime - ui_he_armat > 3)
		ui_he_armed = FALSE;

	if (HE_Chip("he_rstall", [x + w * 0.52, y, 0], [w * 0.48, rowh - 2 * psc, 0],
	            ui_he_armed ? "sure?" : "reset all", ui_he_armed, psc,
	            ui_he_armed
	              ? "Click again to undo every position, size, toggle and option."
	              : "Put the whole HUD back to how it shipped. Asks before it does."))
	{
		if (ui_he_armed)
		{
			HE_ResetAll();
			ui_he_armed = FALSE;
			print("^5hud_edit^7: the whole HUD is back to its shipped settings\n");
		}
		else
		{
			ui_he_armed = TRUE;
			ui_he_armat = cltime;
		}
	}
	y = y + rowh;

	held = HE_Chip("he_done", [x, y, 0], [w, rowh - 2 * psc, 0],
	               "done", TRUE, psc, "");
	y = y + rowh + 3 * psc;

	HUD_Text([x, y, 0], "drag to move   SHIFT: no snap", 7 * psc, HEC_DIM, 0.8);

	// LAST, over everything: it is not a control and registers no hit rect, so
	// nothing it covers becomes unclickable.
	HE_DrawTip(scr, psc);

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
	if (id == "banner")  localcmd("seta hud_banner_x 0.5\nseta hud_banner_y 0.25\n");
	if (id == "keys")    localcmd("seta hud_keys_x 0\nseta hud_keys_y 0.84\n");
	if (id == "debug")   localcmd("seta hud_debug_x 0.012\nseta hud_debug_y 0.30\n");
	if (id == "saveloc") localcmd("seta hud_saveloc_x 0.018\nseta hud_saveloc_y 0.34\n");
	if (id == "gfx")     localcmd("seta hud_gfx_x 0.018\nseta hud_gfx_y 0.10\n");
	if (id == "vote")    localcmd("seta hud_vote_x 0.018\nseta hud_vote_y 0.30\n");
	if (id == "mapinfo") localcmd("seta hud_mapinfo_x 0.99\nseta hud_mapinfo_y 0.02\n");

	/*
	  BUILD 65.  boarding's pair is the -1 SENTINEL and not a coordinate, exactly as
	  board's is: it means "stay stacked under the board panel", which is where it
	  belongs and which no fraction can express, because the panel above it changes
	  height as its rows fade in and out.  Both axes together -- half-detached is
	  not a state worth being able to reach.

	  crosshair has no position and so has no reset; HUD_EditDraw does not offer the
	  chip for it, and this is the other half of that.
	*/
	if (id == "boarding") localcmd("seta hud_boarding_x -1\nseta hud_boarding_y -1\n");
	if (id == "net")      localcmd("seta hud_net_x 0.78\nseta hud_net_y 0.30\n");
	if (id == "results")  localcmd("seta hud_results_x 0.72\nseta hud_results_y 0.50\n");

	ui_he_dirty = TRUE;
};

/*
  BUILD 66 -- ONE CVAR BACK TO ITS SHIPPED VALUE.

  AND HERE cvar_defstring IS THE RIGHT ANSWER, which is not a contradiction of
  the paragraph above HE_Default -- it is the other side of the same distinction.
  A POSITION carries history: hud_splits_y 0.20 and hud_seq_x -0.25 were placed
  by hand to stop two panels overlapping, and re-reading a default that a later
  cfg edit had moved would undo a fix.  A TOGGLE has no history: `on` is `on`,
  and "shipped" is exactly what registercvar was given.

  So positions stay a literal list and everything else is read back.  It also
  means a cvar added in a later build is reset without anyone remembering to add
  it here, which is the failure this function would otherwise have.

  AN EMPTY DEFAULT IS SKIPPED RATHER THAN WRITTEN.  "" is what cvar() leaves
  behind when a name is read before it is registered -- the trap the
  registercvar-beside-the-read rule exists for -- and writing it back would turn
  a cvar that merely has a wrong default into one with no value at all.
*/
void(string cv) HE_ResetCvar =
{
	local string d;

	if (cv == "")
		return;

	d = cvar_defstring(cv);
	if (d == "")
		return;

	localcmd(sprintf("seta %s %s\n", cv, d));
};

/*
  Everything this panel can write, back to how it shipped.

  The walk is over the TABLE and not the list, so the seven hidden elements are
  reset too -- they are still draggable, so they are still losable, and "if
  anything goes really bad" is the case this exists for.
*/
void() HE_ResetAll =
{
	local float i, j, nopt;

	HE_BuildTable();

	for (i = 0; i < he_n; i = i + 1)
	{
		HE_Default(i);
		HE_ResetCvar(he_cvon[i]);
		HE_ResetCvar(he_cvsize[i]);

		nopt = HE_OptCount(he_id[i]);
		for (j = 0; j < nopt; j = j + 1)
			HE_ResetCvar(Gfx_Field(HE_OptDef(he_id[i], j), 0, "|"));
	}

	// The fixed block's own four, which belong to no element.  hud_scale is here
	// even though build 66 took its chip away: it is still what every panel sizes
	// itself from, so a value typed at the console is exactly the kind of "really
	// bad" this button is for.
	HE_ResetCvar("hud_update");
	HE_ResetCvar("hud_round");
	HE_ResetCvar("hud_scale");
	HE_ResetCvar("hud_crosshair");

	// And the panel itself, which can be dragged into a corner like anything else.
	HE_ResetCvar("hud_edit_panel_x");
	HE_ResetCvar("hud_edit_panel_y");

	ui_he_sel   = -1;
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

		/*
		  BUILD 65: a row with no position cvars prints dashes rather than two
		  zeroes.  cvar("") returns 0, which would read as "this element is pinned
		  at the top-left corner" -- a plausible-looking number for a question that
		  has no answer, which is the one thing a status dump must not print.
		*/
		if (he_cvx[i] == "")
			print(sprintf("  %-9s %-3s x %8s y %8s  ",
			              he_id[i],
			              (he_cvon[i] == "") ? "--" : (cvar(he_cvon[i]) ? "on" : "off"),
			              "--", "--"));
		else
			print(sprintf("  %-9s %-3s x %8.4f y %8.4f  ",
			              he_id[i],
			              (he_cvon[i] == "") ? "--" : (cvar(he_cvon[i]) ? "on" : "off"),
			              cvar(he_cvx[i]), cvar(he_cvy[i])));

		if (r < 0)
			print("not drawn");
		else
		{
			rp = hude_pos[r];
			rs = hude_size[r];
			print(sprintf("drawn %gx%g at %g,%g", rs_x, rs_y, rp_x, rp_y));
		}

		/*
		  BUILD 66.  This dump walks the TABLE, so it still has fifteen lines while
		  the panel shows seven -- and those two disagreeing with nothing to explain
		  it would read as a bug in one of them.  It owns the newline now, which is
		  why neither branch above ends its line.
		*/
		print(he_listed[i] ? "\n" : "   ^9(unlisted)^7\n");
	}

	print(sprintf("  hud_update %g   hud_round %g   hud_scale %g   hud_crosshair %g\n",
	              cvar("hud_update"), cvar("hud_round"), cvar("hud_scale"),
	              cvar("hud_crosshair")));

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

	/*
	  BUILD 66.  `reset` has always meant POSITIONS and still does -- changing what
	  an existing verb destroys is not a thing to do quietly.  This is the wider
	  one, and it is the console form of the panel's `reset all` chip.

	  No arming here: typing eight more characters is the confirmation, and a
	  console command cannot be mis-clicked.
	*/
	if (argv(1) == "resetall")
	{
		HE_ResetAll();
		print("^5hud_edit^7: positions, sizes, toggles and options all back to shipped\n");
		return TRUE;
	}

	if (argv(1) == "save")
	{
		localcmd("cfg_save\n");
		ui_he_dirty = FALSE;
		print("^5hud_edit^7: written to ftesurf.cfg\n");
		return TRUE;
	}

	/*
	  BUILD 65 -- `hud_edit <id>` OPENS STRAIGHT ONTO THAT ELEMENT'S SETTINGS.

	  LAST OF THE SUBCOMMANDS, and that ordering is the whole of its correctness:
	  it matches any word at all, so placed above `reset` it would swallow it and
	  report "no element `reset`" -- turning a working command into a confusing
	  error message.  Anything added after this line is unreachable.

	  It exists because the options pane is the one part of this editor a script
	  cannot reach: panes open by CLICKING a row, and a capture run has no hand.
	  Without it every pane in this build could only ever be checked by a person.

	  It is not only a test hook, which is why it is a real subcommand rather than
	  something hidden.  `hud_edit seq` is a faster way to reach the segment
	  column's ten switches than opening the editor and hunting down the list, and
	  it is the obvious thing to bind.

	  An unknown id lists the real ones rather than opening onto nothing.
	*/
	if (argv(1) != "")
	{
		HE_BuildTable();
		for (i = 0; i < he_n; i = i + 1)
		{
			if (he_id[i] != argv(1))
				continue;

			/*
			  BUILD 66.  A hidden element has no list row, so it has nowhere to draw
			  a pane -- the draw loop skips it before it reaches one.  Selecting it
			  anyway would leave ui_he_sel pointing at an element whose settings
			  never appear, which looks like the command silently failing.

			  Said rather than ignored, and it names the cvars, because the settings
			  themselves are still perfectly real.
			*/
			if (!he_listed[i])
			{
				print(sprintf("^3hud_edit^7: `%s` has no panel row in this build.\n",
				              he_id[i]));
				print("           it still draws, still drags and still resets --\n");
				print("           set its cvars directly, or use `hud_edit reset`.\n");
				return TRUE;
			}

			if (!ui_he_open)
				HUD_EditOpen();
			// Still closed means it REFUSED -- a replay or the scoreboard is up,
			// and it has already said so.  Selecting into an editor that is not
			// open would leave the selection armed for whenever it next was.
			if (ui_he_open)
				ui_he_sel = i;
			return TRUE;
		}

		print(sprintf("^3hud_edit^7: no element `%s`.  Known ids:\n", argv(1)));
		for (i = 0; i < he_n; i = i + 1)
			print(sprintf("  %s%s", he_id[i], he_listed[i] ? "" : "^9*^7"));
		print("\n           ^9* no panel row; drags and resets but has no list line^7\n");
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
