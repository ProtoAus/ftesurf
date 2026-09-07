/*
===========================================================================
  m_main.qc -- FTESurf main menu.

  Deliberately two screens and nothing else:

      MAIN     create server
               exit

      CREATE   map picker (dropdown + search + source filter)
               server name
               start / back

  WHY THIS REPLACES FTE'S OWN MENU
  --------------------------------
  The engine picks its menu at menu.c:1490-1503.  If <gamedir>/menu.dat
  loads (pr_menu.c:3338) the built-in menu is torn down entirely
  (M_DeInit_Internal, pr_menu.c:3355) -- so shipping this file replaces
  the stock Quake menu with zero engine C.  `forceqmenu 1` or -qmenu on
  the command line gets the old one back if this ever breaks.

  UI SCALE
  --------
  Everything here is drawn in VIRTUAL screen units.  cfg/default.cfg sets
  vid_conautoscale 1 with conwidth/conheight 0, which makes
  R2D_Console_Resize (r_2d.c:1362-1436) set the virtual screen equal to
  the framebuffer -- one drawn unit == one physical pixel.  Do NOT add an
  autoscale override in m_draw the way nettest's menu does; 1:1 is the
  point.
===========================================================================
*/

// ---------------------------------------------------------------------------
//  Palette.  Flat and dark; the map list is the only thing worth looking at.
// ---------------------------------------------------------------------------
#define COL_TEXT        '1 1 1'
#define COL_DIM         '0.55 0.55 0.58'
#define COL_ACCENT      '0.35 0.75 1'
#define COL_PANEL       '0.06 0.06 0.08'
#define COL_ROW         '0.11 0.11 0.14'
#define COL_ROW_HOVER   '0.18 0.20 0.26'
#define COL_ROW_SEL     '0.10 0.30 0.45'
#define COL_BORDER      '0.28 0.30 0.36'

// ---------------------------------------------------------------------------
//  Font sizes.  MULTIPLES OF 8, ALWAYS.
//
//  FTE builds the default font's glyph atlas at exactly 8 px
//  (r_2d.c:1300, Font_LoadFont(gl_font.string, 8, ...)) and rescales it at
//  draw time.  Nothing else is available -- that 8 is a literal, not a cvar --
//  so any size that is not a whole multiple of 8 samples the atlas at a
//  fractional rate.  With r_font_linear 1 (the engine default) that is a
//  bilinear blur; with r_font_linear 0 it is uneven pixel columns, some
//  glyphs 2 px per source pixel and some 3.
//
//  So: 8, 16, 24, 32.  Nothing else, anywhere in this file.  cfg/default.cfg
//  sets r_font_linear 0 to go with it, and vid_conautoscale 1 means one drawn
//  unit is one physical pixel, so 16 here really is 16 screen pixels.
//
//  The _H twins exist because these are #defines, not vector variables --
//  `SZ_ITEM_y` would be a separate identifier, not a swizzle.
// ---------------------------------------------------------------------------
#define SZ_TITLE        '32 32 0'
#define SZ_ITEM         '24 24 0'       // main menu entries
#define SZ_ITEM_H       24
#define SZ_HEAD         '24 24 0'       // dialog headings
#define SZ_LABEL        '16 16 0'
#define SZ_LABEL_H      16
#define SZ_ROW          '16 16 0'       // map list rows
/*
  ROW_H is 48 because a 16:9 thumbnail is the point of the row.

  44 px of picture plus 2 px above and below gives a 78x44 thumb, and the 48 px
  that leaves also fits two 16 px text lines (name at +4, qualifiers at +26) with
  a 2 px gap.  It was 22 when the row was a tag and a name.
*/
#define ROW_H           48

#define SCREEN_MAIN     0
#define SCREEN_CREATE   1
/*
  The recording terms.  Build 22.

  Not reachable by a button: m_draw forces it whenever the accepted version in
  data/consent.txt is behind FS_TERMS_VERSION, and there is no way off it except
  accepting or quitting.  See ui_consent_read below and FS_TERMS_VERSION in
  shared/sh_defs.qc.
*/
#define SCREEN_TERMS    2

/*
  Map source, derived from the searchpath a BSP came out of.

  A map is tagged by EVERY source it appears in, so these are BITS in a mask
  rather than one value.  That is not tidiness -- it is the whole fix for
  "the Counter-Strike Source map list only has the default maps".  See
  ui_load_maps: the engine's search deduplicates by name, Momentum is mounted
  first, and CS:S's 1024 surf and bhop maps were being hidden behind Momentum's
  copies.  With duplicates allowed and the results coalesced, a map that is in
  both reads "MOM CSS" and appears under either filter.
*/
#define SRC_OTHER       0
#define SRC_MOMENTUM    1
#define SRC_CSS         2
/*
  SRC_ASSET: CS:GO and TF2, mounted for their materials and models because surf
  maps reference them (surf_sandtrap2's floor, surf_utopia's textures).  Their
  own maps come along whether we want them or not -- fs_addons.txt has no
  per-mount "assets only" flag, and FS_IndexAddonMaps walks every line of it --
  so 272 de_/cp_/pl_ maps would otherwise appear in the list.  They are hidden
  here rather than at the mount, which is the only place it can be done, and
  `ui_maps_assetmounts 1` brings them back.
*/
#define SRC_ASSET       3
#define SRC_COUNT       4

// The mask bits, one per SRC_*.  ms_src holds these, not a SRC_ value.
#define SRC_BIT_OTHER   1
#define SRC_BIT_MOM     2
#define SRC_BIT_CSS     4
#define SRC_BIT_ASSET   8

#define FILTER_ALL     -1               // ms_filter, when nothing is excluded

float menu_active;
float menu_screen;
float ui_bootframe;             // ui_bootcheck 2 frame counter

// ---------------------------------------------------------------------------
//  Builtins the MenuQC defs dump does not declare.
//
//  search_getpackagename IS in the menu builtin table (pr_menu.c:2560) but is
//  a name-resolved extension builtin (index 0), so pr_dumpplatform leaves it
//  out.  Declaring it by name here is the supported way to reach it.
//
//  search_begin's dumped prototype calls its second parameter
//  "caseinsensitive" -- a DarkPlaces-ism.  The engine actually reads it as a
//  flags word (pr_bgcmd.c:3651-3655); FTE searches are unconditionally
//  case-insensitive and that bit is a documented no-op (pr_bgcmd.c:3502).
// ---------------------------------------------------------------------------
string(searchhandle handle, float num) search_getpackagename = #0:search_getpackagename;
string(string key) serverkey = #354;    // pr_menu.c:2692

/*
  free_pic IS in the menu builtin table (pr_menu.c:2746, index 453) right next to
  precache_pic, but pr_dumpplatform emits only the latter, so m_defs.qc has no
  declaration for it.  Without it there is no way to release a pic, and the map
  background -- a different 1920x1080 JPEG on every selection change -- would
  accumulate one texture per map you clicked on for the life of the process.
*/
void(string name) free_pic = #453;

// m_defs.qc USES EV_FLOAT in the hashtable accessor sugar at :1037-1044 but
// never defines it -- only sv_defs.qc does (:716).  Declared here so the map
// coalescing hash can ask for a typed value.
const float EV_FLOAT = 2;

#define SB_FULLPACKAGEPATH  2   // QCSEARCH_FULLPACKAGE, pr_bgcmd.c:3503
#define SB_ALLOWDUPES       4   // QCSEARCH_ALLOWDUPES,  pr_bgcmd.c:3512
#define SB_NAMESORT        32   // QCSEARCH_NAMESORT,    pr_bgcmd.c:3506

// ---------------------------------------------------------------------------
//  Map list.
//
//  ms_name / ms_src are PARALLEL buffers -- entry i of one describes entry i
//  of the other.  That is why the search is asked to sort (flag 32,
//  QCSEARCH_NAMESORT, pr_bgcmd.c:3506) instead of calling buf_sort here:
//  buf_sort on one buffer alone would silently desync the pair.
//
//  ms_view holds INDICES into those buffers, as strings, and is what the list
//  actually draws.  Rebuilt only when the query or the source filter changes,
//  never per frame.
// ---------------------------------------------------------------------------
// Declared WITHOUT initialisers on purpose: fteqcc folds an initialised
// global scalar into a compile-time constant and then refuses every
// assignment to it (Q106).  They are seeded to -1 in m_init instead.
strbuf ms_name;
strbuf ms_src;
/*
  ms_lst -- WHICH LIST a map belongs to, which is not the same question as
  which mount it came from, and build 12 is where the two split.

  ms_src answers "where is this file", and it is what the MOM / CSS label on
  the row reads.  ms_lst answers "which of the three lists is this", and the
  rule is about the NAME: a map with a movement-gamemode prefix belongs to its
  source's list, and anything else -- de_dust2, cs_assault, Background01,
  d1_canals_02 -- belongs to Other no matter which mount happens to ship it.

  Keeping one mask for both is what made the CS:S list mean "everything in
  cstrike" rather than "the surf and bhop maps in cstrike", and put HL2's
  campaign in Other only by the accident of it being a separate mount.
*/
strbuf ms_lst;
strbuf ms_view;
float  ms_count;                // entries in ms_name
float  ms_viewcount;            // entries in ms_view
float  ms_nsrc[SRC_COUNT];      // entries per SRC_*, for the filter labels

string ms_query;                // live contents of the search field
float  ms_query_cursor;
string ms_applied_query;        // what ms_view was last built for

/*
  A map has been launched since the query was last touched, so the next click
  into the search field empties it.  Build 19.

  The menu VM is NOT torn down by a map load -- m_shutdown is empty and
  MP_Shutdown is not on the `map` path -- so ms_query survives, and until this
  the only thing that had ever cleared it was m_init.  Coming back to the
  browser after playing a map and finding it still filtered to the one you just
  played is the reported nuisance.

  DECLARED BARE, like its neighbours: fteqcc folds an initialised global scalar
  into a compile-time constant and then refuses every assignment to it (Q106).
  Seeded in m_init.
*/
float  ms_query_stale;

// The filter holds a SRC_* value directly, with FILTER_ALL (-1) meaning "no
// filter".  It used to hold `SRC_* + 1` with 0 for all, which read fine but
// meant the button at index 1 ("mom") selected `want = 1 - 1 = SRC_OTHER` --
// so picking Momentum showed the HL2 mount and nothing else.  Storing the
// source value itself removes the off-by-one rather than documenting it.
float  ms_filter;
float  ms_applied_filter;

float  ms_selected;             // index into ms_name, -1 = nothing picked
vector ms_scroll;

string sv_name;                 // server name field
float  sv_name_cursor;

/*
  ---------------------------------------------------------------------------
   Per-map metadata: tier, stage and bonus counts, and a thumbnail.
  ---------------------------------------------------------------------------

  WHERE IT COMES FROM.  data/mapmeta.txt, written by tools/mapmeta.py out of
  Momentum's own local cache (momentum/_cache/approved_*.dat -- an "MSML" header
  over a zlib'd JSON array).  QC cannot inflate zlib, and parsing 2200 map records
  at boot would be absurd even if it could, so the projection happens offline and
  this reads a flat table.  tools/mapthumbs.py then packs every map's screenshot
  into gfx/mapthumbs/atlas<N> and writes the page/cell back into the same file.

  Three parallel buffers again, for the same reason ms_name/ms_src are:

    ms_tierv   the tier alone, as a string.  Split out because ui_refilter runs
               over every map on every keystroke and must not tokenize 2200 rows
               to answer "is this tier 4".  0 means untiered -- there is no tier 0,
               so the sentinel cannot collide with a real value.
    ms_modev   the gamemode id, split out for exactly the same reason: it is the
               second thing ui_refilter tests per map per keystroke.  0 means
               unknown, and Momentum has no gamemode 0 either.
    ms_meta    the rest, packed as the file writes it: "linear stages bonuses
               page cell uuid".  Tokenized only for the dozen rows actually
               drawn.

  A map with no row at all gets "0" and "" and draws as untiered with a
  placeholder.  That is the honest answer for the 1084 CS:S-only maps Momentum
  has never indexed, and it is deliberately distinguishable from tier 0 / 0
  stages, which would be a lie.
*/
strbuf ms_tierv;
strbuf ms_modev;
strbuf ms_meta;

// Personal bests, indexed like the others: the full-run tick count for this map,
// as a string, or "" when data/runs/<map>.pb has no `best 0 0` line.
strbuf ms_pbv;

// The tier filter, ANDed with ms_filter.  0 = any; otherwise the tier itself.
float  ms_tier;
float  ms_applied_tier;

// The gamemode filter, ANDed with both of the above.  0 = any; otherwise one of
// Momentum's gamemode CATEGORIES (GC_*), not one of its gamemode ids -- climb
// and defrag are three ids each.  See ui_mode_cat.
float  ms_mode;
float  ms_applied_mode;

// The background pic currently held open, so it can be freed when the selection
// moves.  "" when nothing is loaded.  See ui_backdrop.
string ms_bgpic;
float  ms_bgfor;                // ms_selected the background was loaded for
float  ms_bgblind;              // warned once that no candidate path resolved

// mapmeta.txt column layout, and the atlas geometry tools/mapthumbs.py packs to.
// These two must agree with the tool; they are stated in its module docstring.
#define THUMB_W     128
#define THUMB_H     72
#define ATLAS_PX    2048
#define THUMB_COLS  16          // ATLAS_PX / THUMB_W

// ---------------------------------------------------------------------------
//  Small widgets.  sui_sys gives us hit-testing, clipping, scrolling and text
//  input; these are just the three shapes this menu draws.
// ---------------------------------------------------------------------------
void() ui_noop = {};

string(string s) ui_lower = { return strtolower(s); };

/*
  A left-aligned text row that highlights on hover.  Returns TRUE on release,
  which is the click that counts -- press-to-activate makes drags feel broken.

  The width is MEASURED, not passed in.  The default font is fixed-pitch, so a
  24 px "create server" is 13*24 = 312 px wide and the "> " marker adds 48 more
  -- a hand-guessed 220 px box left the highlight ending in the middle of the
  word.  `minw` only sets a floor so the two entries line up with each other.
*/
float(string id, vector pos, float minw, float h, string label, vector col) ui_option =
{
	string  shown = strcat("> ", label);        // measure the WIDEST state
	float   w     = stringwidth(shown, TRUE, SZ_ITEM) + 32;
	vector  size;

	if (w < minw)
		w = minw;
	size = [w, h];

	sui_action_element(pos, size, id, sui_noop);

	float hot = sui_is_hovered(id);
	if (hot)
		sui_fill(pos, size, COL_ROW_HOVER, 0.6, 0);

	sui_text([pos_x + 12, pos_y + (size_y - SZ_ITEM_H) * 0.5], SZ_ITEM,
	         hot ? shown : label,
	         hot ? COL_ACCENT : col, 1, 0);

	return sui_is_released(id);
};

/*
  A bordered box with a label, used for the buttons in the create dialog.

  It MEASURES its label, using the passed size only as a floor -- the same
  fix ui_option got for the main menu, and for the same reason.  The Start
  button carries two labels of very different widths ("start" and "pick a
  map"), so a box sized for one of them cuts the other in half; that it
  shipped is because the wide one only appears before a map is chosen, which
  is exactly the state you stop being in as soon as you test it.
*/
float(string id, vector pos, vector size, string label) ui_button =
{
	float w = stringwidth(label, TRUE, SZ_LABEL) + 16;
	if (w < size_x)
		w = size_x;
	size_x = w;

	sui_action_element(pos, size, id, sui_noop);

	float hot = sui_is_hovered(id);
	sui_fill(pos, size, hot ? COL_ROW_HOVER : COL_ROW, 1, 0);
	sui_border_box(pos, size, 1, hot ? COL_ACCENT : COL_BORDER, 1, 0);
	sui_text([pos_x + 8, pos_y + (size_y - SZ_LABEL_H) * 0.5], SZ_LABEL,
	         label, hot ? COL_ACCENT : COL_TEXT, 1, 0);

	return sui_is_released(id);
};

/*
  One filter chip: a small toggle that shows whether it is the active choice.

  Returns its WIDTH rather than whether it was clicked, because a strip of these
  has to be laid out left to right by measurement -- every label is a different
  length and hardcoding a column pitch either clips "parkour" or leaves a gap
  after "rj".  The caller tests sui_is_released(id) itself, which it can do at
  any point in the frame.

  Three strips use this: source, tier and gametype.  They were three copies of
  the same twelve lines before the gametype one made it three.
*/
#define CHIP_PAD    16          // horizontal padding, total, inside a chip
#define CHIP_H      26
#define CHIP_GAP    6

/*
  Does a readable file exist at this path?

  fopen is the only non-blocking way to ask this from menuQC.  drawgetimagesize
  would answer for images but BLOCKS on the load (pr_menu.c:1096), which is the
  one thing the backdrop must not do, and whichpack is not registered in this VM.

  Writes are sandboxed to data/ and cfg/ (QC_FixFileName, pr_bgcmd.c:2646); reads
  are not, so this can look straight into the mounted Momentum install.  If that
  ever stops being true this returns FALSE for everything, which is why
  ui_map_backdrop keeps a blind last resort rather than treating "" as "no
  picture".
*/
float(string path) ui_file_exists =
{
	local filestream fh;

	fh = fopen(path, FILE_READ);
	if (fh < 0)
		return FALSE;
	fclose(fh);
	return TRUE;
};

/*
===========================================================================
  THE RECORDING TERMS -- build 22.

  FTESurf writes a file for every timed run.  Until build 22 that was two files
  of derived movement data and nobody was ever told; from build 22 it can also
  include a journal of raw mouse and keyboard events, which is a materially
  different thing to be doing to somebody without asking.  So it asks.

  THE RECORD IS data/consent.txt, one key per line, unknown keys skipped -- the
  same additive grammar as state.txt and the .rec header, so a later build can
  add to it without invalidating this one:

      FTESURF-CONSENT 1
      version 1                    the FS_TERMS_VERSION that was accepted
      accepted 20260903-181500

  THE TERMS TEXT IS A CONSTANT IN THIS FILE, not a data file, and that is the
  point rather than laziness.  A terms file on disk could be emptied and still
  satisfy the gate; a constant means the text and the version it is stamped
  against cannot drift apart, and bumping FS_TERMS_VERSION is the one action
  that puts the screen back in front of everybody.

  IT IS NOT A LOCK, AND THE TEXT SAYS SO.  Anyone able to edit consent.txt could
  equally set rec_terms or the binary.  A consent record's job is to be an honest
  record that a person was shown something and agreed, not to be unforgeable.
  What it does do that matters: cl_replay.qc refuses to start a journal unless
  rec_terms is current, so somebody who has never seen this screen is not
  recorded.  Not collecting is the enforcement; the blocked button is only the
  reminder.
===========================================================================
*/
string(float i) rec_terms_line =
{
	if (i ==  0) return "FTESurf times your runs, and it keeps a file for each one.";
	if (i ==  1) return "";
	if (i ==  2) return "^3What is recorded, while a run's clock is going:";
	if (i ==  3) return "  your position, velocity and view angles, about 66 times a second";
	if (i ==  4) return "  which movement keys you are holding, once per drawn frame";
	if (i ==  5) return "  a journal of raw mouse and keyboard events, with timings";
	if (i ==  6) return "";
	if (i ==  7) return "^3Where it goes:";
	if (i ==  8) return "  files under this game's own data folder, on this machine.";
	if (i ==  9) return "  ^2Nothing is sent anywhere.^7 FTESurf has no server to send it to";
	if (i == 10) return "  and no code that uploads anything.";
	if (i == 11) return "";
	if (i == 12) return "^3What it is for:";
	if (i == 13) return "  replaying your runs, and being able to tell a real run from a";
	if (i == 14) return "  scripted one.";
	if (i == 15) return "";
	if (i == 16) return "^3What is deliberately NOT recorded:";
	if (i == 17) return "  anything you type. While the console or a menu has focus the";
	if (i == 18) return "  journal keeps the timing of a keypress but drops which key it";
	if (i == 19) return "  was, so a password typed in the console cannot end up in a file.";
	if (i == 20) return "  Nothing outside this game's window is watched, ever.";
	if (i == 21) return "";
	if (i == 22) return "^3Turning it off:";
	if (i == 23) return "  ^9fs_hid 0^7 stops the raw input journal. Runs recorded without it";
	if (i == 24) return "  are marked as such in their own file rather than passing as";
	if (i == 25) return "  runs that had one.";
	return "";
};
#define FS_TERMS_LINES 26

float ms_consent;       // the FS_TERMS_VERSION on disk; 0 = none

/*
  Read the accepted version.  Returns 0 for "no record", which is also what a
  torn or foreign file gets -- the safe direction, since the cost of asking
  again is one click and the cost of a false accept is recording somebody who
  never agreed.
*/
float() ui_consent_read =
{
	local filestream fh;
	local string l;
	local float v;

	v  = 0;
	fh = fopen("data/consent.txt", FILE_READ);
	if (fh < 0)
		return 0;

	for (l = fgets(fh); l != ""; l = fgets(fh))
	{
		tokenize(l);
		if (argv(0) == "version")
			v = stof(argv(1));
	}
	fclose(fh);
	return v;
};

void() ui_consent_write =
{
	local filestream fh;

	fh = fopen("data/consent.txt", FILE_WRITE);
	if (fh < 0)
	{
		print("^1could not write data/consent.txt\n");
		return;
	}

	fputs(fh, "FTESURF-CONSENT 1\n");
	fputs(fh, sprintf("version %g\n", FS_TERMS_VERSION));
	fputs(fh, sprintf("accepted %s\n", strftime(TRUE, "%Y%m%d-%H%M%S")));
	fclose(fh);

	ms_consent = FS_TERMS_VERSION;

	/*
	  BUILD 23: and LEAVE the screen.  Three sites set menu_screen to
	  SCREEN_TERMS and, until this line, nothing ever set it back -- so the
	  accept button wrote the file, cleared the m_draw gate, and then drew the
	  terms again on the very next frame because menu_screen still said to.  It
	  looked exactly like a dead button, and the only way out was to quit and
	  relaunch, at which point m_init read the file and never armed the gate.
	  Done here rather than at the call site so it cannot happen on the failed
	  fopen path above: if the write did not land, ms_consent is still 0 and
	  m_draw's gate puts the screen straight back.
	*/
	menu_screen = SCREEN_MAIN;

	/*
	  The mirror the other two VMs read.  Set AFTER the file, so a failed write
	  cannot leave the cvar claiming an acceptance that was never recorded.
	  Not archived: it is derived from the file every boot in m_init, and an
	  archived copy would be a second answer that could disagree with the first.
	*/
	cvar_set("rec_terms", ftos(FS_TERMS_VERSION));
};

float(string label) ui_chip_w =
{
	return stringwidth(label, TRUE, SZ_LABEL) + CHIP_PAD;
};

float(vector pos, string id, string label, float on) ui_chip =
{
	local float w, hot;
	local vector sz;

	w  = ui_chip_w(label);
	sz = [w, CHIP_H];

	sui_action_element(pos, sz, id, sui_noop);

	hot = sui_is_hovered(id);
	sui_fill(pos, sz, on ? COL_ROW_SEL : COL_ROW, 1, 0);
	sui_border_box(pos, sz, 1, (on || hot) ? COL_ACCENT : COL_BORDER, 1, 0);
	sui_text([pos_x + CHIP_PAD * 0.5, pos_y + (CHIP_H - SZ_LABEL_H) * 0.5],
	         SZ_LABEL, label, (on || hot) ? COL_TEXT : COL_DIM, 1, 0);

	return w;
};

// Single-line text field.  sui_text_input owns the caret and the keystrokes;
// all this adds is the box, the placeholder and a blinking caret.
void(string id, vector pos, vector size, __inout string text,
     __inout float cursor, string placeholder) ui_field =
{
	sui_text_input(id, pos, size, text, cursor);

	float focus = sui_is_last_clicked(id);
	sui_fill(pos, size, COL_ROW, 1, 0);
	sui_border_box(pos, size, 1, focus ? COL_ACCENT : COL_BORDER, 1, 0);

	vector tp = [pos_x + 6, pos_y + (size_y - SZ_LABEL_H) * 0.5];
	if (text == "" && !focus)
		sui_text(tp, SZ_LABEL, placeholder, COL_DIM, 1, 0);
	else
		sui_text(tp, SZ_LABEL, text, COL_TEXT, 1, 0);

	// Caret sits after the cursor'th character, measured with the same font
	// metrics the text was drawn with so it lands correctly on proportional
	// fonts too.
	if (focus && (floor(time * 2) & 1) == 0)
	{
		float cx = stringwidth(substring(text, 0, cursor), 1, SZ_LABEL);
		sui_fill([tp_x + cx, tp_y], [1, SZ_LABEL_H], COL_ACCENT, 1, 0);
	}
};

/*
  The same field, with the current selection drawn right-aligned inside it.

  This is the "one box, not two" the create screen used to need two boxes for:
  the search query on the left, what you have actually picked on the right, both
  visible at the same time.  The alternative -- swapping the box's contents when
  it loses focus -- is fewer pixels but makes a field silently change meaning,
  and the one thing a map picker should never be is ambiguous about what is
  selected.

  It is drawn BEFORE the query so a very long query overlaps it rather than the
  other way round: what you are typing is the live thing and must stay readable.
*/
void(string id, vector pos, vector size, __inout string text,
     __inout float cursor, string placeholder, string sel) ui_field_sel =
{
	sui_text_input(id, pos, size, text, cursor);

	float focus = sui_is_last_clicked(id);
	sui_fill(pos, size, COL_ROW, 1, 0);
	sui_border_box(pos, size, 1, focus ? COL_ACCENT : COL_BORDER, 1, 0);

	vector tp = [pos_x + 6, pos_y + (size_y - SZ_LABEL_H) * 0.5];

	if (sel != "")
		sui_text([pos_x + size_x - 6 - stringwidth(sel, TRUE, SZ_LABEL), tp_y],
		         SZ_LABEL, sel, COL_ACCENT, 1, 0);

	if (text == "" && !focus)
		sui_text(tp, SZ_LABEL, placeholder, COL_DIM, 1, 0);
	else
		sui_text(tp, SZ_LABEL, text, COL_TEXT, 1, 0);

	if (focus && (floor(time * 2) & 1) == 0)
	{
		float cx = stringwidth(substring(text, 0, cursor), 1, SZ_LABEL);
		sui_fill([tp_x + cx, tp_y], [1, SZ_LABEL_H], COL_ACCENT, 1, 0);
	}
};

// ---------------------------------------------------------------------------
//  Map enumeration.
//
//  ONE search_begin sees every mounted searchpath -- the gamedir, every VPK,
//  and every fs_addons.txt mount (COM_EnumerateFilesPackage walks the whole
//  com_searchpaths chain, fs.c:3727-3755).  So Momentum's 1308 BSPs and CS:S's
//  1082 arrive from the same call; there is nothing per-game to do here beyond
//  working out which one each came from.
// ---------------------------------------------------------------------------
#define SB_NAMESORT 32          // QCSEARCH_NAMESORT, pr_bgcmd.c:3506

float(string pkg) ui_classify =
{
	string p = strtolower(pkg);

	if (strstrofs(p, "momentum") >= 0)
		return SRC_BIT_MOM;

	// Order matters: "Counter-Strike Global Offensive" contains
	// "counter-strike", so CS:GO has to be recognised BEFORE CS:S is.
	if (strstrofs(p, "global offensive") >= 0 || strstrofs(p, "/csgo") >= 0 ||
	    strstrofs(p, "team fortress") >= 0    || strstrofs(p, "/tf/") >= 0)
		return SRC_BIT_ASSET;

	if (strstrofs(p, "cstrike") >= 0 || strstrofs(p, "counter-strike") >= 0)
		return SRC_BIT_CSS;
	return SRC_BIT_OTHER;
};

// Every source the map is in, most interesting first.  A map in two mounts now
// reads "MOM CSS", which is honest in a way "MOM" was not: Momentum's copy is
// the one that loads, but CS:S has it too and you may have come looking for it
// there.
string(float mask) ui_srcname =
{
	string s = "";

	if (mask & SRC_BIT_MOM)   s = "MOM";
	if (mask & SRC_BIT_CSS)   s = (s == "") ? "CSS" : strcat(s, " CSS");
	if (mask & SRC_BIT_ASSET) s = (s == "") ? "MNT" : strcat(s, " MNT");
	if (s == "")              s = "---";
	return s;
};

/*
  ---------------------------------------------------------------------------
   Gamemodes.
  ---------------------------------------------------------------------------

  Momentum's gamemode ids, as they appear in the `mode` column of mapmeta.txt.
  These are ITS numbering, not ours.

  THIS TABLE WAS WRONG FOR EVERY ID FROM 3 UP, and so was the one in
  tools/mapmeta.py it was copied from.  Both were reconstructed by matching a
  population census to the modes we expected to be popular, and that guess
  produced a permutation that looked entirely plausible: 7 was named "ahop" and
  is RJ, 8 was "parkour" and is SJ, 9 was "conc" and is AHOP, 12 was "kz" and is
  DEFRAG_VQ3.  Nothing crashed, because a name is only ever displayed -- the
  browser simply labelled a third of the library with the wrong gamemode, and
  then FILTERED on the wrong id, so the "kz" chip showed defrag maps.

  Now taken from Momentum's own
  panorama/scripts/common/web/enums/gamemode.enum.ts, and independently
  confirmed against the cache: 251 of 251 `rj_` maps with a ranked main-track
  tier are gamemode 7, 185 of 195 `sj_` are 8, 26 of 27 `ahop_` are 9, 203 of
  254 `kz_` are 5.

  THE CHIPS ARE CATEGORIES, NOT MODES, which is also Momentum's own grouping
  (GamemodeCategoryToGamemodeMap, same file).  Three of the thirteen ids are
  climb variants and three are defrag variants, so filtering per id would need
  twelve chips for a strip that already documents what happens when it overruns
  the panel -- it draws straight off the screen with nothing to say it did.
  Nine chips is fewer than the eleven this had, every map is reachable, and
  "climb" means climb rather than one of the three spellings of it.

  Census over the 2194 rows in mapmeta.txt, with the ids finally read correctly:

      surf 557   bhop 531   rj 263   sj 256   kz 242   df-cpm 140
      conc 75    climb-16 57   ahop 32   bhop-hl1 15   df-vq3 4   unknown 22
*/
#define FS_NMODES   9           // "any", plus the eight gamemode CATEGORIES

// GamemodeCategory, gamemode.enum.ts.  Only used through ui_mode_cat.
#define GC_SURF   1
#define GC_BHOP   2
#define GC_CLIMB  3
#define GC_RJ     4
#define GC_SJ     5
#define GC_AHOP   6
#define GC_CONC   7
#define GC_DEFRAG 8

// The specific mode, for the per-row detail line.  4 (CLIMB_MOM) and 13
// (DEFRAG_VTG) have no maps in this library but are named anyway: a row that
// does turn up should say what it is, not fall back to blank.
string(float id) ui_mode_name =
{
	switch (id)
	{
	case 1:  return "surf";
	case 2:  return "bhop";
	case 3:  return "bhop-hl1";
	case 4:  return "climb";
	case 5:  return "kz";
	case 6:  return "climb-16";
	case 7:  return "rj";
	case 8:  return "sj";
	case 9:  return "ahop";
	case 10: return "conc";
	case 11: return "df-cpm";
	case 12: return "df-vq3";
	case 13: return "df-vtg";
	}
	return "";
};

// GamemodeToGamemodeCategory, ported.  0 for a map with no gamemode at all,
// which is every CS:S-only row and answers only "any".
float(float id) ui_mode_cat =
{
	switch (id)
	{
	case 1:  return GC_SURF;
	case 2:  case 3:            return GC_BHOP;
	case 4:  case 5:  case 6:   return GC_CLIMB;
	case 7:  return GC_RJ;
	case 8:  return GC_SJ;
	case 9:  return GC_AHOP;
	case 10: return GC_CONC;
	case 11: case 12: case 13:  return GC_DEFRAG;
	}
	return 0;
};

/*
  Strip SLOT to category, which is what lets the buttons be ordered by
  usefulness-to-this-game rather than by Momentum's numbering: surf first
  because this is a surf trainer, then bhop, then the rest by population.
*/
float(float slot) ui_mode_id =
{
	switch (slot)
	{
	case 1:  return GC_SURF;    // 557
	case 2:  return GC_BHOP;    // 546
	case 3:  return GC_RJ;      // 263
	case 4:  return GC_SJ;      // 256
	case 5:  return GC_CLIMB;   // 299
	case 6:  return GC_DEFRAG;  // 144
	case 7:  return GC_CONC;    // 75
	case 8:  return GC_AHOP;    // 32
	}
	return 0;                   // slot 0 = "any"
};

string(float slot) ui_mode_label =
{
	switch (slot)
	{
	case 0:  return "any";
	case 1:  return "surf";
	case 2:  return "bhop";
	case 3:  return "rj";
	case 4:  return "sj";
	case 5:  return "climb";
	case 6:  return "defrag";
	case 7:  return "conc";
	case 8:  return "ahop";
	}
	return "";
};

/*
  Is this the name of a MOVEMENT map?

  Censused rather than guessed, across all three mounts (1309 Momentum, 1083
  CS:S, 79 HL2):

    surf 2025   bhop 240   df 22   kz 18   rj 13   mg 10   ahop 4   conc 4
    de 15   cs 6   fy 2   d1/d2/d3 70   ispy 7   (no underscore at all) 24

  The first row is the movement gamemodes and goes to MOM/CSS; the second is
  Counter-Strike's own gamemodes, Half-Life 2's campaign, the menu backdrops
  and Momentum's handful of non-movement maps, and all of that is Other.

  A PREFIX TEST, not a lookup, and that is the honest limitation: a surf map
  someone named without the prefix lands in Other.  There is no other signal --
  the zone file only exists for maps Momentum has indexed, and 691 of these
  1309 have none.
*/
float(string nm) ui_isgamemode =
{
	string p = strtolower(nm);

	if (substring(p, 0, 5) == "surf_")  return TRUE;
	if (substring(p, 0, 5) == "bhop_")  return TRUE;
	if (substring(p, 0, 5) == "ahop_")  return TRUE;
	if (substring(p, 0, 3) == "kz_")    return TRUE;
	if (substring(p, 0, 3) == "df_")    return TRUE;
	if (substring(p, 0, 3) == "rj_")    return TRUE;
	if (substring(p, 0, 3) == "sj_")    return TRUE;
	if (substring(p, 0, 3) == "xc_")    return TRUE;
	if (substring(p, 0, 5) == "conc_")  return TRUE;
	if (substring(p, 0, 6) == "climb_") return TRUE;
	if (substring(p, 0, 6) == "trikz_") return TRUE;
	if (substring(p, 0, 7) == "defrag_")return TRUE;
	return FALSE;
};

// "maps/surf_kitsune.bsp" -> "surf_kitsune"
string(string f) ui_mapname =
{
	float len = strlen(f);

	if (len > 5 && strtolower(substring(f, 0, 5)) == "maps/")
	{
		f = substring(f, 5, len - 5);
		len = len - 5;
	}
	if (len > 4 && strtolower(substring(f, len - 4, 4)) == ".bsp")
		f = substring(f, 0, len - 4);

	return f;
};

/*
  ---------------------------------------------------------------------------
   data/mapmeta.txt -- tier, counts and thumbnail cell, joined onto the map list.
  ---------------------------------------------------------------------------

  Field order inside the packed ms_meta string.  The tier is NOT in here -- it
  lives in ms_tierv on its own so ui_refilter can read it without tokenizing.
*/
#define MT_LINEAR   0
#define MT_STAGES   1
#define MT_BONUS    2
#define MT_PAGE     3
#define MT_CELL     4
#define MT_UUID     5
/*
  Where the tier came from -- mapmeta.txt column 10, added in build 17.

  "rank" is a ranked leaderboard tier.

  "sugg" is a SUGGESTION, from a map still in Momentum's Unlisted or Beta
  sections, where no ranking exists yet and the number is what the submitter and
  the testers think the map is worth.  1020 of the 2271 rows are that, so it is
  not a rare case -- and drawing an estimate identically to a ranking would have
  the browser assert something the data does not.  Momentum keeps the two in
  separate tabs; we show one list, so the row has to carry the distinction.

  "alias" (build 18) is inherited from the same map without its port suffix --
  surf_aircontrol_ksf taking surf_aircontrol's tier.  Momentum has no record of
  the ported name at all, so without this the map reads untiered; but a port can
  carry real layout changes, so the tier is a strong guess and not a reading.
  76 rows.

  "over" is data/mapmeta_override.txt -- a human wrote it down deliberately, so
  it draws like a ranking rather than like a guess.  0 rows today; the file does
  not exist yet.

  "" for a file written before the column existed, which draws as a plain tier.
*/
#define MT_TSRC     6

/*
  Runs at the END of ui_load_maps, once ms_count is final.

  The two buffers are grown to exactly ms_count BEFORE the file is opened. A
  short buffer is survivable -- bufstr_get returns "" past the end -- but a
  misaligned one would put one map's tier on another's row, and that failure is
  silent and looks like bad data rather than a bug.  Establishing the length
  first makes misalignment impossible regardless of what the file contains.
*/
void() ui_meta_load =
{
	local filestream fh;
	local hashtable byname;
	local string ln, key;
	local float i, n, row, hit, maxpage;

	if (ms_tierv >= 0) buf_del(ms_tierv);
	if (ms_modev >= 0) buf_del(ms_modev);
	if (ms_meta  >= 0) buf_del(ms_meta);
	ms_tierv = buf_create();
	ms_modev = buf_create();
	ms_meta  = buf_create();

	for (i = 0; i < ms_count; i = i + 1)
	{
		bufstr_add(ms_tierv, "0", TRUE);
		bufstr_add(ms_modev, "0", TRUE);
		bufstr_add(ms_meta, "", TRUE);
	}

	fh = fopen("data/mapmeta.txt", FILE_READ);
	if (fh < 0)
	{
		print("^3FTESurf: data/mapmeta.txt missing -- run tools\\mapmeta.py then "
		      "tools\\mapthumbs.py.  No tiers, counts or thumbnails.\n");
		return;
	}

	byname = hash_createtab(4096, EV_FLOAT);
	for (i = 0; i < ms_count; i = i + 1)
		hash_add(byname, strtolower(bufstr_get(ms_name, i)), i,
		         HASH_REPLACE | EV_FLOAT);

	hit = 0;
	maxpage = -1;
	while ((ln = fgets(fh)) != "")
	{
		n = tokenize(ln);
		if (n < 10)
			continue;
		if (argv(0) != "meta")
			continue;

		key = strtolower(argv(1));
		row = hash_get(byname, key, -1, EV_FLOAT);
		if (row < 0)
			continue;               // metadata for a map that is not mounted

		// stof("-") is 0, and there is neither a tier 0 nor a gamemode 0, so the
		// sentinel is free in both columns.
		bufstr_set(ms_tierv, row, argv(2));
		bufstr_set(ms_modev, row, argv(9));

		// argv(10) only when it is there.  The `n < 10` guard above is what makes
		// the column additive: this menu reads a pre-build-17 mapmeta.txt exactly
		// as it always did and simply sees no provenance, which draws as a plain
		// tier -- the same rule the .rec header follows.  tokenize() returns ""
		// past the end anyway, so this is belt and braces, but the belt is the
		// documented contract and worth writing down.
		bufstr_set(ms_meta, row, sprintf("%s %s %s %s %s %s %s",
		                                 argv(3), argv(4), argv(5),
		                                 argv(6), argv(7), argv(8),
		                                 (n >= 11) ? argv(10) : "-"));

		if (argv(6) != "-")
			if (stof(argv(6)) > maxpage)
				maxpage = stof(argv(6));

		hit = hit + 1;
	}
	fclose(fh);
	hash_destroytab(byname);

	/*
	  Start the atlas loads NOW rather than on first draw.

	  Texture loads are asynchronous, and a page is only requested when a row
	  that lives on it first scrolls into view -- so opening the list showed
	  black where the thumbnails go until each page arrived.  Kicking all of them
	  off at load time hides the whole latency behind the menu opening, and the
	  cost is bounded and known: one page per 448 maps.

	  Only the pages some MOUNTED map actually references are touched, which is
	  why maxpage is tracked in the loop above rather than assumed -- mapmeta.txt
	  describes 2194 maps and most installs have far fewer.
	*/
	for (i = 0; i <= maxpage; i = i + 1)
		precache_pic(strcat("gfx/mapthumbs/atlas", ftos(i)));

	print(sprintf("FTESurf: mapmeta matched %g of %g maps, %g thumbnail page(s)\n",
	              hit, ms_count, maxpage + 1));

	/*
	  One probe against a file we know we wrote, so that a later "no backdrop"
	  cannot be blamed on the wrong thing.  ui_map_backdrop chooses its image by
	  asking fopen which files exist; this says whether fopen can answer at all.
	*/
	if (!ui_file_exists("gfx/mapthumbs/atlas0.png"))
		print("^3FTESurf: gfx/mapthumbs/atlas0.png not readable -- run "
		      "tools\\mapthumbs.py, and expect no thumbnails or backdrops.\n");
};

/*
  Personal bests, for the "have I run this" column.

  A single fopen per map is what data/runs/<map>.pb was shaped for
  (sv_timer.qc:424-432) -- but doing that for 2200 maps at menu open would be 2200
  failed opens for the ones never played.  So the search runs the other way round:
  enumerate the .pb files that EXIST, which is the handful of maps with a time on
  them, and open only those.

  `best 0 0` is the main track's full run.  A map with only stage times (surf_ace
  today has best 0 2 .. best 0 7 and no 0 0) correctly reads as unrun -- the column
  is about the full run, and claiming a time for one would be wrong.
*/
void() run_pb_load =
{
	local searchhandle h;
	local filestream fh;
	local hashtable byname;
	local string fn, ln, nm;
	local float i, n, row, cnt, best, pl, sl;

	if (ms_pbv >= 0) buf_del(ms_pbv);
	ms_pbv = buf_create();
	for (i = 0; i < ms_count; i = i + 1)
		bufstr_add(ms_pbv, "", TRUE);

	/*
	  BUILD 23: data/runs/<map>/best.pb, so the wildcard is a whole path
	  component and the map name is what it matches.

	  ONE wildcard, in a middle component -- the pattern SV_SaveLocScan has run
	  since build 17 and is therefore known to work in FTE's enumerator.  A
	  fixed leaf is why the name is best.pb rather than <map>.pb: the latter
	  would need two wildcards, which is a guess about Sys_EnumerateFiles2's
	  recursion that nothing on this disk currently proves.
	*/
	h = search_begin(strcat(FS_RUNS_ROOT, "*", FS_PB_LEAF), SB_NAMESORT, TRUE);
	if (h < 0)
		return;

	byname = hash_createtab(4096, EV_FLOAT);
	for (i = 0; i < ms_count; i = i + 1)
		hash_add(byname, strtolower(bufstr_get(ms_name, i)), i,
		         HASH_REPLACE | EV_FLOAT);

	cnt = search_getsize(h);
	for (i = 0; i < cnt; i = i + 1)
	{
		fn = search_getfilename(h, i);

		/*
		  "data/runs/surf_ace/best.pb" -> "surf_ace".  ui_mapname only knows
		  about maps/ and .bsp, so the trim is done here.

		  BOTH lengths are measured from the constants rather than typed.  The
		  previous version wrote the prefix out as a literal AND its length as a
		  bare 10 on the next line, which is two statements of one fact that a
		  rename silently desynchronises -- and this build renamed it.
		*/
		nm = fn;
		n = strlen(nm);
		pl = strlen(FS_RUNS_ROOT);
		sl = strlen(FS_PB_LEAF);
		if (n > pl)
			if (strtolower(substring(nm, 0, pl)) == FS_RUNS_ROOT)
			{
				nm = substring(nm, pl, n - pl);
				n = n - pl;
			}
		if (n > sl)
			if (strtolower(substring(nm, n - sl, sl)) == FS_PB_LEAF)
				nm = substring(nm, 0, n - sl);

		row = hash_get(byname, strtolower(nm), -1, EV_FLOAT);
		if (row < 0)
			continue;

		fh = fopen(fn, FILE_READ);
		if (fh < 0)
			continue;

		best = 0;
		while ((ln = fgets(fh)) != "")
		{
			if (tokenize(ln) < 4)
				continue;
			if (argv(0) != "best")
				continue;
			if (argv(1) != "0")
				continue;
			if (argv(2) != "0")
				continue;
			best = stof(argv(3));
		}
		fclose(fh);

		if (best > 0)
			bufstr_set(ms_pbv, row, ftos(best));
	}

	search_end(h);
	hash_destroytab(byname);

	// Counted separately from the file count: a .pb with only stage times has no
	// full run to show, and "4 files, 1 time" is the difference between "the
	// search found nothing" and "you have not finished one of these yet".
	local float times;
	times = 0;
	for (i = 0; i < ms_count; i = i + 1)
		if (bufstr_get(ms_pbv, i) != "")
			times = times + 1;
	print(sprintf("FTESurf: %g personal-best files, %g full-run times\n",
	              cnt, times));
};

/*
  One atlas cell, or a placeholder.

  page/cell are "-" for the ~750 maps with a thumbnail id whose JPEG was never
  cached locally, and for every CS:S-only map.  Those draw as a flat block rather
  than as some other map's picture.
*/
void(vector pos, vector size, float page, float cell) ui_thumb =
{
	local vector sp, ss;
	local float col, row;

	if (page < 0 || cell < 0)
	{
		sui_fill(pos, size, '0.05 0.05 0.07', 1, 0);
		sui_border_box(pos, size, 1, '0.14 0.14 0.18', 1, 0);
		return;
	}

	col = cell - floor(cell / THUMB_COLS) * THUMB_COLS;
	row = floor(cell / THUMB_COLS);

	// Normalised texture coordinates -- see the note on sui_subpic.
	sp = [col * THUMB_W / ATLAS_PX, row * THUMB_H / ATLAS_PX, 0];
	ss = [THUMB_W / ATLAS_PX, THUMB_H / ATLAS_PX, 0];

	sui_subpic(pos, size, strcat("gfx/mapthumbs/atlas", ftos(page)),
	           sp, ss, '1 1 1', 1, 0);
};

void() ui_load_maps =
{
	if (ms_name >= 0) buf_del(ms_name);
	if (ms_src  >= 0) buf_del(ms_src);
	if (ms_lst  >= 0) buf_del(ms_lst);

	ms_name  = buf_create();
	ms_src   = buf_create();
	ms_lst   = buf_create();
	ms_count = 0;

	/*
	  SB_FULLPACKAGEPATH makes search_getpackagename return the whole purepath
	  rather than the bare package leaf, which is the only way to tell a
	  Momentum map from a CS:S one.  SB_NAMESORT keeps the parallel buffers in a
	  stable, already-sorted order.

	  SB_ALLOWDUPES IS THE FIX FOR THE CS:S LIST.  Without it search_enumerate
	  drops any name it has already seen, case-insensitively
	  (pr_bgcmd.c:3605-3612) -- and Momentum is mounted first, so 1024 of CS:S's
	  surf and bhop maps were being hidden behind Momentum's copies and the cs:s
	  filter was left showing the ~20 stock maps nothing else ships.  That read
	  as a broken mount, and the old comment here explained it as if it were
	  correct behaviour.  With duplicates allowed each entry carries its own
	  searchpath handle, so classify-then-coalesce gives every map the full set
	  of sources it is actually in.
	*/
	searchhandle h = search_begin("maps/*.bsp",
	                              SB_FULLPACKAGEPATH | SB_ALLOWDUPES | SB_NAMESORT, TRUE);
	if (h < 0)
	{
		print("^1FTESurf: map search failed -- no maps mounted?\n");
		return;
	}

	ms_nsrc[SRC_OTHER] = ms_nsrc[SRC_MOMENTUM] = ms_nsrc[SRC_CSS] = ms_nsrc[SRC_ASSET] = 0;

	float showasset = cvar("ui_maps_assetmounts");
	float hidden = 0;
	float dupes  = 0;

	/*
	  Coalesce through a hash rather than by adjacency.  NAMESORT is an
	  explicitly unstable qsort (pr_bgcmd.c:3592-3598), so two entries for the
	  same map are not guaranteed to land next to each other even though they
	  almost always will.  Keyed on the lowercased name because the engine's own
	  dedup is case-insensitive and so should this be.
	*/
	hashtable seen = hash_createtab(1024, EV_FLOAT);

	float n = search_getsize(h);
	for (float i = 0; i < n; i++)
	{
		string nm = ui_mapname(search_getfilename(h, i));
		if (nm == "")
			continue;

		float bit = ui_classify(search_getpackagename(h, i));
		string key = strtolower(nm);

		// hash_get's default of -1 distinguishes "not seen" from row 0.
		float row = hash_get(seen, key, -1, EV_FLOAT);
		if (row >= 0)
		{
			bufstr_set(ms_src, row, ftos(stof(bufstr_get(ms_src, row)) | bit));
			dupes++;
			continue;
		}

		bufstr_add(ms_name, nm, TRUE);
		bufstr_add(ms_src, ftos(bit), TRUE);
		// Written once, from the NAME, so a second copy of the same map found in
		// another mount cannot change which list it is in -- only which sources
		// its label names.  See ms_lst.
		bufstr_add(ms_lst, ui_isgamemode(nm) ? "0" : ftos(SRC_BIT_OTHER), TRUE);
		hash_add(seen, key, ms_count, HASH_REPLACE | EV_FLOAT);
		ms_count++;
	}
	search_end(h);

	/*
	  The asset hide is a SECOND pass now, and it has to be: a map is only
	  hidden when CS:GO or TF2 is its ONLY source.  Testing the bit during the
	  loop would have dropped the nine maps CS:S and CS:GO both ship, and worse,
	  would have depended on which copy the sort happened to reach first.
	*/
	float w = 0;
	for (float i = 0; i < ms_count; i++)
	{
		float mask = stof(bufstr_get(ms_src, i));
		float lst  = stof(bufstr_get(ms_lst, i));

		if (mask == SRC_BIT_ASSET && !showasset)
		{
			hidden++;
			continue;
		}

		/*
		  Finish the list mask now that every source has been coalesced in.

		  0 was written above to mean "movement map, list still to be decided" --
		  it could not be decided in the first pass, because the second copy of
		  the same map may not have arrived yet.  A movement map lists under
		  every source it is really in; anything else is Other regardless.

		  The OTHER bit is dropped from a movement map's list mask on purpose: it
		  is in Momentum, or CS:S, or both, and having it also answer the Other
		  filter would put 2000 surf maps back in the list that exists to not
		  contain them.
		*/
		if (lst == 0)
		{
			lst = mask & (SRC_BIT_MOM | SRC_BIT_CSS | SRC_BIT_ASSET);
			if (!lst)
				lst = SRC_BIT_OTHER;    // a movement map from some other mount
		}

		if (w != i)
		{
			bufstr_set(ms_name, w, bufstr_get(ms_name, i));
			bufstr_set(ms_src,  w, ftos(mask));
		}
		bufstr_set(ms_lst, w, ftos(lst));

		if (lst & SRC_BIT_MOM)   ms_nsrc[SRC_MOMENTUM] = ms_nsrc[SRC_MOMENTUM] + 1;
		if (lst & SRC_BIT_CSS)   ms_nsrc[SRC_CSS]      = ms_nsrc[SRC_CSS] + 1;
		if (lst & SRC_BIT_ASSET) ms_nsrc[SRC_ASSET]    = ms_nsrc[SRC_ASSET] + 1;
		if (lst & SRC_BIT_OTHER) ms_nsrc[SRC_OTHER]    = ms_nsrc[SRC_OTHER] + 1;
		w++;
	}
	// Just move the count.  Every read of these buffers is bounded by ms_count,
	// so the entries past it are unreachable; bufstr_free's contract about
	// whether the buffer actually shrinks is not worth depending on for a
	// compaction that costs nothing this way.
	ms_count = w;

	if (hidden)
		print(sprintf("FTESurf: %g maps hidden from the CS:GO/TF2 asset mounts "
		              "(ui_maps_assetmounts 1 to list them)\n", hidden));

	// The counts overlap now, deliberately: a map in both Momentum and CS:S is
	// counted under both, because it is genuinely in both and either filter
	// should find it.  They no longer sum to the total, and that is the point.
	print(sprintf("FTESurf: %g maps (%g duplicate entries coalesced) -- "
	              "momentum %g, counter-strike %g, other %g\n",
	              ms_count, dupes,
	              ms_nsrc[SRC_MOMENTUM], ms_nsrc[SRC_CSS], ms_nsrc[SRC_OTHER]));

	// Both join onto ms_name, so they can only run once it is final.  Neither
	// can fail in a way that matters: a missing mapmeta.txt costs the metadata
	// columns, and no .pb files means no times to show.
	ui_meta_load();
	run_pb_load();
};

// Enumerate and report, without opening the menu.  This is the diagnostic for
// "is the CS:S mount actually visible", which is otherwise only observable by
// eye in the dropdown.
void(string filter) ui_maplist_print =
{
	ui_load_maps();

	string q = strtolower(filter);
	float mom = 0, css = 0, oth = 0, shown = 0;

	for (float i = 0; i < ms_count; i++)
	{
		float s = stof(bufstr_get(ms_src, i));
		float l = stof(bufstr_get(ms_lst, i));
		if (l & SRC_BIT_MOM)   mom++;
		if (l & SRC_BIT_CSS)   css++;
		if (l & SRC_BIT_OTHER) oth++;

		if (q != "" && shown < 20
		    && strstrofs(strtolower(bufstr_get(ms_name, i)), q) >= 0)
		{
			// Both masks, because they answer different questions and this is
			// the command you run when they disagree: the label is where the
			// file IS, the bracket is which list it is IN.
			print(sprintf("  %-8s [%s]  %s\n", ui_srcname(s), ui_srcname(l),
			              bufstr_get(ms_name, i)));
			shown++;
		}
	}

	print(sprintf("ui_maplist: %g total -- momentum %g, counter-strike %g, other %g\n",
	              ms_count, mom, css, oth));
};

// Rebuild ms_view from the query + filter.  O(ms_count), but only ever run on
// a keystroke or a filter change -- never from m_draw's steady state.
void() ui_refilter =
{
	if (ms_view >= 0) buf_del(ms_view);
	ms_view = buf_create();
	ms_viewcount = 0;

	string q = strtolower(ms_query);

	for (float i = 0; i < ms_count; i++)
	{
		// A BIT test, not equality -- a map in Momentum and CS:S must appear
		// under both filters, which is the whole point of the mask.
		//
		// ms_lst, not ms_src: the filter is about which LIST a map belongs to,
		// and since build 12 that is decided by its name.  ms_src still drives
		// the MOM / CSS label on the row.
		if (ms_filter != FILTER_ALL && !(stof(bufstr_get(ms_lst, i)) & ms_filter))
			continue;
		if (q != "" && strstrofs(strtolower(bufstr_get(ms_name, i)), q) < 0)
			continue;

		// Tier is a plain equality, and 0 in ms_tierv means UNTIERED rather than
		// tier zero -- so an untiered map answers only the "any" filter and never
		// gets swept into a numbered one.  This reads ms_tierv rather than
		// tokenizing ms_meta because it runs over every map on every keystroke.
		if (ms_tier != 0 && stof(bufstr_get(ms_tierv, i)) != ms_tier)
			continue;

		// Same shape, same reasoning: 0 in ms_modev is "no gamemode known", which
		// is every CS:S-only map, and those answer only "any".  Momentum has no
		// gamemode 0 to collide with, and ui_mode_cat returns 0 for it too.
		//
		// COMPARED AS A CATEGORY, not as an id -- the chip is "climb", and climb
		// is three different gamemode ids.  See ui_mode_cat.
		if (ms_mode != 0 && ui_mode_cat(stof(bufstr_get(ms_modev, i))) != ms_mode)
			continue;

		bufstr_add(ms_view, ftos(i), TRUE);
		ms_viewcount++;
	}

	ms_applied_query  = ms_query;
	ms_applied_filter = ms_filter;
	ms_applied_tier   = ms_tier;
	ms_applied_mode   = ms_mode;
	ms_scroll = '0 0 0';
};

string() ui_selected_name =
{
	if (ms_selected < 0 || ms_selected >= ms_count)
		return "";
	return bufstr_get(ms_name, ms_selected);
};

// ---------------------------------------------------------------------------
//  Launch.
//
//  maxclients 1 makes the engine freeze the listen server whenever a menu or
//  console is up (PAUSE_AUTO, sv_main.c:5584-5592), which on a surf map means
//  the world stops the instant you hit ESC.  Two slots sidesteps it entirely.
// ---------------------------------------------------------------------------
void() m_close;
void() m_open;

void() ui_launch =
{
	string mapname = ui_selected_name();
	if (mapname == "")
		return;

	/*
	  BUILD 22.  Belt and braces beside m_draw's screen override: this is the
	  single launch choke point -- the start button and the ui_bootcheck driver
	  both come through here -- and a gate that lives only in the drawing code
	  would be one refactor away from being bypassed by something that never
	  draws.

	  It deliberately does NOT gate the `map` console command.  That is the
	  developer surface, behind the console key, and anyone typing there could
	  equally edit consent.txt; pretending otherwise would make this look like
	  a security boundary, which it is not and does not claim to be.  The gate
	  that does real work is in cl_replay.qc, where no consent means no journal.
	*/
	if (ms_consent < FS_TERMS_VERSION)
	{
		menu_screen = SCREEN_TERMS;
		return;
	}

	cvar_set("hostname", sv_name != "" ? sv_name : "FTESurf");

	localcmd("sv_public 0\n");
	localcmd("deathmatch 1\n");
	localcmd("maxclients 2\n");
	localcmd("coop 0\n");
	localcmd(sprintf("map %S\n", mapname));

	// The search that found this map has done its job.  Arm the field to empty
	// itself the next time it is clicked -- not now, because ms_selected stays
	// and the box draws the selection right-aligned beside the query, so wiping
	// it here would blank the field while you are still looking at it.
	ms_query_stale = TRUE;

	m_close();
};

// ---------------------------------------------------------------------------
//  Headless self-check driver (ui_bootcheck >= 2).
//
//  Frame-driven rather than time-driven so it behaves identically on a slow
//  first load.  Steps past the launch run with the menu CLOSED, which is why
//  m_draw calls this before its own menu_active gate.
// ---------------------------------------------------------------------------
string bc_ang;          // scratch for ui_bootangles; a local would shadow per branch

void() ui_bootcheck_tick =
{
	ui_bootframe++;

	if (ui_bootframe == 30)
		localcmd("screenshot ui_menu_main\n");
	else if (ui_bootframe == 40)
	{
		menu_screen = SCREEN_CREATE;
		ui_load_maps();
		ui_refilter();
	}
	else if (ui_bootframe == 70)
		localcmd("screenshot ui_menu_create\n");
	else if (ui_bootframe == 75)
	{
		/*
		  Exercise the source filter for real.  The mapping from button slot to
		  SRC_* used to be off by one, so "momentum" showed the HL2 mount; a
		  screenshot of the filtered list is the only check that catches that
		  class of bug, because the counts on the buttons stay right.

		  And this line was itself an instance of it.  ms_filter holds a BIT
		  (SRC_BIT_*), not an index (SRC_*) -- ui_refilter masks against ms_lst --
		  and SRC_MOMENTUM is 1, which is SRC_BIT_OTHER.  So the "momentum"
		  screenshot has been a picture of the Other list since the bit split
		  landed, and the check that exists to catch an off-by-one had one.
		*/
		ms_filter = SRC_BIT_MOM;

		/*
		  Select a map too, because SELECTING is what loads the background, and
		  an unexercised backdrop is exactly the sort of thing that ships broken:
		  it draws behind the panel, so a wrong path or a failed decode looks
		  identical to "no map picked yet".  surf_ace is a safe target -- it is in
		  Momentum's cache with a tier, 8 stages, a bonus and a cached -large.jpg,
		  so this frame also covers the metadata join and the thumbnail cell.
		*/
		for (float bi = 0; bi < ms_count; bi++)
			if (bufstr_get(ms_name, bi) == "surf_ace")
			{
				ms_selected = bi;
				break;
			}
	}
	else if (ui_bootframe == 105)
		localcmd("screenshot ui_menu_mom\n");
	else if (ui_bootframe == 110)
		ms_tier = 3;                    // the tier strip, and a non-trivial refilter
	else if (ui_bootframe == 140)
		localcmd("screenshot ui_menu_tier\n");
	else if (ui_bootframe == 145)
	{
		/*
		  Now the gametype strip, on its own so the two filters are separable in
		  the screenshots.  kz rather than surf: it is the third-largest mode here
		  (287 maps) and shares no name prefix with the source filter above, so a
		  strip that silently did nothing would still change the count and the
		  rows visibly.  Tier goes back to any, or the two filters would AND down
		  to a handful and prove much less.
		*/
		ms_tier = 0;
		ms_mode = 12;                   // kz
	}
	else if (ui_bootframe == 175)
		localcmd("screenshot ui_menu_mode\n");
	else if (ui_bootframe == 180)
	{
		ms_filter = FILTER_ALL;
		ms_tier = 0;
		ms_mode = 0;

		if (cvar("ui_bootcheck") < 3)
		{
			localcmd("quit\n");
			return;
		}

		// Drive the REAL launch path rather than a shortcut localcmd, so this
		// covers ui_selected_name, the hostname write and the PAUSE_AUTO
		// guards -- not just the `map` command.
		string want = cvar_string("ui_bootmap");
		if (want == "")
			want = "surf_kitsune";

		for (float i = 0; i < ms_count; i++)
			if (bufstr_get(ms_name, i) == want)
			{
				ms_selected = i;
				break;
			}

		if (ms_selected < 0)
		{
			print(sprintf("^1bootcheck: %s not in the map list\n", want));
			localcmd("quit\n");
			return;
		}

		sv_name = "bootcheck";
		ui_launch();
	}
	/*
	  The Momentum chat commands.  They only print, so the log is the check --
	  but they are the one part of the game that can silently do NOTHING (a
	  wrong track/segment lookup just finds no zone) and never say so on screen.
	  Run before the screenshots so the teleports do not move the camera.
	*/
	else if (ui_bootframe == 705)
	{
		localcmd("cmd say !s 2\ncmd say !b 1\ncmd say !r\ncmd say !m\n");
		// ...and two that must NOT be intercepted.  A prefix match would read
		// "!rank" as "!r" and teleport instead of talking, which is the kind of
		// thing nobody finds until they type it in front of someone.
		localcmd("cmd say !rank\ncmd say hello\n");
	}
	// Stand in zone 0, which is the start zone on every map that has one, so
	// the in-game screenshot below covers zone_goto as well.  The angles matter:
	// without them the camera points wherever the spawn happened to face, and a
	// screenshot of a blank wall proves nothing about a rendering change.
	else if (ui_bootframe == 715)
		localcmd("cmd zone_goto 0 0 0\n");
	// The board maths the HUD rests on, checked in the real ClipVelocity.
	else if (ui_bootframe == 722)
		localcmd("pm_selftest\n");
	// Generous margin: a cold VBSP load with LZMA lumps is not fast.
	else if (ui_bootframe == 730)
	{
		// keydest matters: pr_csqc.c passes CSQC_UpdateView's `notmenu` as
		// !Key_Dest_Has(kdm_menu|kdm_cwindows), so a keydest still stuck on
		// the menu silently suppresses the entire HUD.
		print(sprintf("^2bootcheck: constate=%s map=%s clientstate=%g keydest=%g\n",
		              serverkey("constate"), serverkey("map"),
		              clientstate(), getkeydest()));
		localcmd("screenshot ui_ingame\n");
		localcmd("zone_list\n");
		// Where every leg's teleport actually lands, and how far that is from
		// the box floor we used to use.  A silent regression in the destination
		// lookup would otherwise only show as "!s 3 feels wrong".
		localcmd("cmd zone_dests\n");
		localcmd("ent_census\n");
	}
	// The physics column is off by default now, so it needs turning on to be
	// looked at -- and looking at it is the only way to see that its numeric
	// columns still line up under a proportional font.
	else if (ui_bootframe == 736)
		localcmd("hud_debug 1\n");
	else if (ui_bootframe == 742)
	{
		localcmd("screenshot ui_hud_debug\n");
		localcmd("hud_debug 0\n");
	}
	/*
	  A NOCLIP FLYTHROUGH, and two frames out of it.

	  One fixed camera is a poor sample of a map.  surf_null is what made that
	  obvious: its ramp clip brushes were rendering across the whole route, and
	  every still this driver could take was from inside the start zone -- a
	  sealed room facing a blank wall -- so the screenshot meant to show the bug
	  showed a blank wall instead.

	  So: stand in the start zone, aim down the track, and fly.  Two stills a
	  few hundred units apart cover more of a map than any number of angles from
	  one spot, and they are the check that a rendering change hid what it meant
	  to and nothing else.

	  ui_bootangles is "<yaw> <pitch>" and overrides the aim for a map whose
	  route leaves the start in some other direction.  The default 0 70 suits
	  surf_null, whose start sits 6232 units above its end and 2176 behind it.
	*/
	else if (ui_bootframe == 748)
	{
		bc_ang = cvar_string("ui_bootangles");
		if (bc_ang == "")
			bc_ang = "0 70";
		tokenize(bc_ang);
		localcmd(sprintf("cmd zone_goto 0 %s %s\n", argv(0), argv(1)));
		localcmd("cmd noclip\n+forward\n");
	}
	else if (ui_bootframe == 900)
		localcmd("screenshot ui_ingame_b\n");
	else if (ui_bootframe == 1150)
	{
		localcmd("screenshot ui_ingame_c\n");
		localcmd("-forward\ncmd noclip\n");
	}
	// ...and once more with the menu up, which is the only way to see that the
	// backdrop is actually translucent over a live map.
	else if (ui_bootframe == 1160)
		m_open();
	else if (ui_bootframe == 1185)
		localcmd("screenshot ui_menu_overlay\n");
	else if (ui_bootframe > 1200)
		localcmd("quit\n");
};

// ---------------------------------------------------------------------------
//  Screens
// ---------------------------------------------------------------------------
/*
  The backdrop.

  m_draw runs after the world has been rendered, so a translucent fill lets
  the map show through -- which is what you want when ESC is how you get back
  to a run.  Disconnected there is nothing behind it, so it goes solid.
*/
void(vector screensize) ui_backdrop =
{
	sui_fill('0 0 0', screensize, '0.02 0.02 0.03',
	         (clientstate() == 2) ? 0.55 : 1, 0);
};

/*
  The selected map's own screenshot, behind everything.

  This is the 1920x1080 `-large` JPEG out of Momentum's cache, drawn full-screen and
  heavily darkened so the panel on top of it stays readable.  It is the ONE place a
  full-size image is used; the rows draw from the atlas.

  ONE SLOT, freed on every change.  MenuQC has no eviction of its own -- free_pic is
  builtin #453 but undeclared, which is why this file declares it -- and a 1920x1080
  RGBA texture is 8 MB, so caching per map would cost gigabytes over a browsing
  session.  Holding exactly one and releasing it when the selection moves is the only
  bounded policy.

  drawpic returns 0 while the image is not resident (PF_CL_drawpic, pr_menu.c:610-641,
  which is non-blocking), so a miss simply leaves the flat backdrop showing and costs
  nothing.  drawgetimagesize would answer the same question but BLOCKS on the load
  (pr_menu.c:1096) and must not be used here.
*/
// Both places one of these images can live, preferred in that order: Momentum's
// own cache first, because that copy already existed and cost us nothing.
string(string uuid, string size) ui_bgprobe =
{
	local string p;
	p = sprintf("_cache/images/%s-%s.jpg", uuid, size);
	if (ui_file_exists(p))
		return p;
	p = sprintf("gfx/mapshots/%s-%s.jpg", uuid, size);
	if (ui_file_exists(p))
		return p;
	return "";
};

/*
  The backdrop file for one map, chosen for the SCREEN and not for sharpness.

  The CDN offers 480x270, 1280x720, 1920x1080 and 2560x1440 of every map.  The
  temptation is to always take the biggest one present, and it is wrong: the
  backdrop is re-decoded and re-uploaded on every arrow key, so at 1280x720 an
  xl costs a four-times-larger JPEG decode and a 14 MB texture upload to show
  the same picture.  So: smallest size that still covers the screen, then
  downward through whatever else is on disk.

  Which sizes exist is not uniform.  Momentum caches only small and large, and
  only for maps its own UI has shown you -- 1503 and 817 of 2172 here.  The rest
  come from tools/mapfetch.py.  So every rung has to be probed rather than
  assumed, and the order is a preference, not a plan.
*/
string(float scrw, float n) ui_bgsize =
{
	if (scrw > 1920)
	{
		if (n == 0) return "xl";
		if (n == 1) return "large";
		if (n == 2) return "medium";
	}
	else if (scrw > 1280)
	{
		if (n == 0) return "large";
		if (n == 1) return "xl";
		if (n == 2) return "medium";
	}
	else
	{
		if (n == 0) return "medium";
		if (n == 1) return "large";
		if (n == 2) return "xl";
	}
	return "small";
};

string(string uuid, float scrw) ui_bgpick =
{
	local string want;
	local float i;

	// Spelled out rather than tokenized into a list, because `uuid` upstream is
	// an argv() temp and a tokenize here would be one more thing between it and
	// the sprintf that consumes it.  Four fopens on a selection change is free.
	for (i = 0; i < 4; i = i + 1)
	{
		want = ui_bgprobe(uuid, ui_bgsize(scrw, i));
		if (want != "")
			return want;
	}
	return "";
};

void(vector screensize) ui_map_backdrop =
{
	local string uuid, want;

	if (ms_selected != ms_bgfor)
	{
		if (ms_bgpic != "")
		{
			free_pic(ms_bgpic);
			strunzone(ms_bgpic);
			ms_bgpic = "";
		}
		ms_bgfor = ms_selected;

		uuid = "";
		if (ms_selected >= 0)
			if (ms_selected < ms_count)
				if (tokenize(bufstr_get(ms_meta, ms_selected)) > MT_UUID)
					uuid = argv(MT_UUID);

		if (uuid != "" && uuid != "-")
		{
			want = ui_bgpick(uuid, screensize_x);

			// Every probe failed.  Either the map genuinely has no cached image,
			// or fopen cannot see outside data/ in this build -- and those two
			// are indistinguishable from here.  Ask for the sharp one blindly,
			// which is exactly what this did before the chain existed: drawpic
			// no-ops on a miss, so the cost of being wrong is a flat backdrop.
			//
			// Say so once, though.  If it is the second cause it applies to every
			// map, and a silent chain that never fires reads as "these maps have
			// no picture" rather than as a build difference.
			if (want == "")
			{
				want = sprintf("_cache/images/%s-large.jpg", uuid);
				if (!ms_bgblind)
				{
					ms_bgblind = TRUE;
					print("^9FTESurf: no readable image found for a selected map; "
					      "backdrops fall back to asking for -large blind.\n");
				}
			}

			ms_bgpic = strzone(want);
			precache_pic(ms_bgpic);
		}
	}

	if (ms_bgpic == "")
		return;

	// Cover, not fit: the image is 16:9 and the screen may not be, and a letterbox
	// bar behind a menu panel reads as a rendering fault rather than as an aspect
	// mismatch.  Overscan on the short axis instead.
	local vector sz;
	local float scale;
	scale = screensize_x / 1920;
	if (screensize_y / 1080 > scale)
		scale = screensize_y / 1080;
	sz = [1920 * scale, 1080 * scale, 0];

	drawpic([floor((screensize_x - sz_x) * 0.5), floor((screensize_y - sz_y) * 0.5)],
	        ms_bgpic, sz, '0.7 0.7 0.74', 1, 0);

	// A wash on top, so a bright desert map cannot compete with the panel text.
	// 0.4 rather than the 0.55 this started at: the panel covers most of the
	// screen already, and the two multiplied left the image too dark to read as a
	// picture of anything -- which defeats the point of showing it.
	sui_fill('0 0 0', screensize, '0.02 0.02 0.03', 0.4, 0);
};

/*
  The terms screen.  No "back", by design -- the only two ways off it are
  accepting and quitting, because "later" is not a state this can be in: the very
  next thing the player does is load a map, and that is the thing being consented
  to.
*/
void(vector screensize) screen_terms =
{
	local vector p;
	local float i, y;

	ui_backdrop(screensize);

	/*
	  The panel is sized FROM the text rather than guessed at: 26 lines at a 15 px
	  pitch is 390 px, and the first cut used a 500 px box, which put the accept
	  button straight through the last three lines of "Turning it off".  A terms
	  screen with its own text obscured by the button that accepts it is not a
	  detail -- it is the one screen where the reader has to be able to read
	  everything before the control that says they did.
	*/
	p = [floor(screensize_x * 0.5) - 320, floor(screensize_y * 0.5) - 290];

	sui_fill(p, [640, 580], COL_PANEL, 0.94, 0);
	sui_border_box(p, [640, 580], 1, COL_BORDER, 1, 0);

	Font_Set(ui_font_display);
	sui_text([p_x + 24, p_y + 22], SZ_TITLE, "Before you play", COL_ACCENT, 1, 0);
	Font_Set(ui_font_ui);

	y = p_y + 72;
	for (i = 0; i < FS_TERMS_LINES; i = i + 1)
	{
		sui_text([p_x + 24, y], SZ_LABEL, rec_terms_line(i), COL_TEXT, 1, 0);
		y = y + 15;
	}

	sui_text([p_x + 24, p_y + 486], SZ_LABEL,
	         "^9This is a record that you agreed, kept on your own machine. It is not a lock.",
	         COL_DIM, 1, 0);

	if (ui_button("tm_accept", [p_x + 24, p_y + 516], [200, 30],
	              "I understand -- continue"))
		ui_consent_write();

	if (ui_button("tm_exit", [p_x + 516, p_y + 516], [100, 30], "exit"))
		localcmd("quit\n");
};

void(vector screensize) screen_main =
{
	ui_backdrop(screensize);

	vector p = [floor(screensize_x * 0.5) - 200, floor(screensize_y * 0.5) - 48];

	Font_Set(ui_font_display);
	sui_text([p_x + 12, p_y - 96], SZ_TITLE, "FTESurf", COL_ACCENT, 1, 0);
	Font_Set(ui_font_ui);
	sui_text([p_x + 12, p_y - 44], SZ_LABEL,
	         "Counter-Strike: Source movement", COL_DIM, 1, 0);

	if (ui_option("mm_create", p, 400, 34, "create server", COL_TEXT))
	{
		menu_screen = SCREEN_CREATE;
		if (ms_count == 0)
			ui_load_maps();
		ui_refilter();
	}

	if (ui_option("mm_exit", [p_x, p_y + 42], 400, 34, "exit", COL_TEXT))
		localcmd("quit\n");

	if (clientstate() == 2)
		sui_text([p_x + 12, p_y + 100], SZ_LABEL,
		         sprintf("^9esc  back to %s", serverkey("map")), COL_DIM, 1, 0);
};

// The four source filters, in the order they are drawn.  Kept as a function
// rather than an array because fteqcc folds an initialised global array into
// constants and then refuses to read it back reliably.
float(float slot) ui_filter_src =
{
	if (slot == 1) return SRC_BIT_MOM;
	if (slot == 2) return SRC_BIT_CSS;
	if (slot == 3) return SRC_BIT_OTHER;
	return FILTER_ALL;
};

string(float slot) ui_filter_label =
{
	// The counts are ON the buttons because "css 20" reads as a broken mount
	// without them -- see the note in ui_load_maps.
	if (slot == 1) return sprintf("momentum %g", ms_nsrc[SRC_MOMENTUM]);
	if (slot == 2) return sprintf("cs:s %g",     ms_nsrc[SRC_CSS]);
	if (slot == 3) return sprintf("other %g",    ms_nsrc[SRC_OTHER]);
	return sprintf("all %g", ms_count);
};

void(vector screensize) screen_create =
{
	ui_backdrop(screensize);
	ui_map_backdrop(screensize);

	// Sized so the OPEN dropdown fits INSIDE the panel with the start/back row
	// still below it.  An overlay list that spilled past the border covered
	// those buttons entirely, which is how the first version shipped.
	//
	// The width used to be set by the SOURCE ROW -- four measured buttons at 16 px
	// come to 680 px, and at 560 the last one hung outside the border, invisibly,
	// because sui_push_frame does not clip fills.  Since build 14 the ROW is what
	// sets it: a 78 px thumbnail, a tier chip, a name column wide enough for
	// surf_colin_blaster_69000, and a right-aligned time.  980 also leaves the
	// eleven-button tier strip room to fit on one line at 16 px.
	//
	// 760 tall rather than 600 because rows went from 22 px to ROW_H, and a list
	// that shows four maps is not a list.
	//
	// CLAMPED to the screen, which 760 tall is not on a 1280x720 desktop: at
	// vid_conautoscale 1 one unit is one pixel, so a fixed panel taller than the
	// framebuffer hangs its title off the top and its start/back row off the
	// bottom, and sui_push_frame does not clip, so nothing says so.  32 px of
	// margin also leaves the map backdrop something to show through.
	// 1060 rather than 980 so the gametype strip fits beside the tier strip at
	// 1280 wide, which is the common case; below that the clamp takes over and
	// the strip drops to its own line by itself.
	vector size = [1060, 760];
	if (size_x > screensize_x - 32) size_x = screensize_x - 32;
	if (size_y > screensize_y - 32) size_y = screensize_y - 32;

	vector pos  = [floor((screensize_x - size_x) * 0.5),
	               floor((screensize_y - size_y) * 0.5)];

	float inner = size_x - 32;      // content width inside the 16px margins

	sui_fill(pos, size, COL_PANEL, 1, 0);
	sui_border_box(pos, size, 1, COL_BORDER, 1, 0);
	sui_text([pos_x + 16, pos_y + 12], SZ_HEAD, "create server", COL_ACCENT, 1, 0);

	sui_push_frame(pos, size);

	float y = 56;

	// ---- server name --------------------------------------------------
	sui_text([16, y], SZ_LABEL, "server name", COL_DIM, 1, 0);
	ui_field("cs_name", [16, y + 20], [inner, 28], sv_name, sv_name_cursor, "FTESurf");
	y += 60;

	// ---- source filter ------------------------------------------------
	sui_text([16, y], SZ_LABEL, "source", COL_DIM, 1, 0);
	float fx = 16;
	float f;
	for (f = 0; f < 4; f++)
	{
		string flabel = ui_filter_label(f);
		float  fsrc   = ui_filter_src(f);
		string fid    = strcat("cs_flt", ftos(f));

		fx += ui_chip([fx, y + 20], fid, flabel, ms_filter == fsrc) + CHIP_GAP;

		if (sui_is_released(fid))
			ms_filter = fsrc;
	}
	y += 56;

	/*
	  ---- tier and gametype filters -------------------------------------

	  Two strips on one row: tier on the left, gametype to its right, both
	  ANDed into ui_refilter along with source and the search text.  Twenty-two
	  more action elements against sui's MAX_ACTION_ELEMENTS 256
	  (sui_sys.qc:194); the create screen is nowhere near it.

	  "To its right" is MEASURED, not assumed.  Every chip is sized from its own
	  label, the panel clamps itself to the framebuffer, and sui_push_frame does
	  not clip -- so a strip that overruns the panel does not wrap and does not
	  get cut off, it draws straight over the border and off the screen with
	  nothing to say it did.  (That exact failure ate the whole bottom of this
	  panel once already, at 980x760 on a 720p framebuffer.)  So the gametype
	  strip is measured first and drops to its own line when it will not fit,
	  which is what happens in a narrow window or with a wider font.
	*/
	float mw = 0;
	for (f = 0; f < FS_NMODES; f++)
		mw += ui_chip_w(ui_mode_label(f)) + CHIP_GAP;

	sui_text([16, y], SZ_LABEL, "tier", COL_DIM, 1, 0);
	fx = 16;
	for (f = 0; f <= 10; f++)
	{
		string tlabel = (f == 0) ? "any" : ftos(f);
		string tid    = strcat("cs_tier", ftos(f));

		fx += ui_chip([fx, y + 20], tid, tlabel, ms_tier == f) + CHIP_GAP;

		if (sui_is_released(tid))
			ms_tier = f;
	}

	float mx   = fx + 18;           // a wider gap than CHIP_GAP: these are two
	float mrow = y;                 // separate questions, not one long strip
	if (mx + mw > inner + 16)
	{
		mx    = 16;
		mrow  = y + 46;
		y    += 46;
	}

	sui_text([mx, mrow], SZ_LABEL, "gametype", COL_DIM, 1, 0);
	for (f = 0; f < FS_NMODES; f++)
	{
		float  mgm  = ui_mode_id(f);
		string mlbl = ui_mode_label(f);
		string mcid = strcat("cs_mode", ftos(f));

		mx += ui_chip([mx, mrow + 20], mcid, mlbl, ms_mode == mgm) + CHIP_GAP;

		if (sui_is_released(mcid))
			ms_mode = mgm;
	}
	y += 56;

	/*
	  ---- map picker: ONE box, and the list is always open ----------------

	  There used to be two 28px boxes at the same x and the same width, one
	  showing the selected map and toggling a dropdown, the other taking the
	  search text.  Two boxes for one question, and the list hid itself the
	  moment you answered it -- which is exactly when you want to see the
	  neighbours you might have wanted instead.

	  Now: the query goes in on the left, and the current selection is drawn
	  right-aligned in the SAME box.  Both are visible at once, which is the
	  version that does not silently change meaning when the field loses focus.
	  Deleting the button also gives the list back 56 px of height.
	*/
	string sel = ui_selected_name();

	sui_text([16, y], SZ_LABEL,
	         sprintf("map  ^9(%g of %g)", ms_viewcount, ms_count), COL_DIM, 1, 0);

	/*
	  Consumed HERE, before the field is drawn, so the box comes up empty on the
	  same frame rather than one frame later.

	  sui_is_clicked is true for exactly one frame, on the mouse-UP that landed
	  on this element, and it fires again on every re-click of an already-focused
	  box (sui_sys.qc:264-267) -- which is precisely "the next time you click on
	  the search".  It lives in m_main.qc and not in sui_sys.qc because that file
	  is shared with csprogs and has no notion of maps.

	  m_draw's ms_query != ms_applied_query test then refilters and scrolls to
	  the top on the next frame for free; nothing else has to be called.
	*/
	if (ms_query_stale)
		if (sui_is_clicked("cs_search"))
		{
			ms_query = "";
			ms_query_cursor = 0;
			ms_query_stale = FALSE;
		}

	ui_field_sel("cs_search", [16, y + 20], [inner, 28],
	             ms_query, ms_query_cursor, "search maps...", sel);
	y += 56;

	// ---- the list ------------------------------------------------------
	float by = size_y - 46;         // top of the start/back row
	vector ls = [inner, by - y - 12];

	{
		sui_fill([16, y], ls, '0.03 0.03 0.04', 1, 0);
		sui_border_box([16, y], ls, 1, COL_ACCENT, 1, 0);

		if (ms_viewcount == 0)
			sui_text([24, y + 10], SZ_ROW, "no matches", COL_DIM, 1, 0);
		else
		{
			// sui_list_view only emits rows inside the visible window, so this
			// loop costs per VISIBLE row -- about a dozen -- not per map.  That
			// is what lets a 1400-entry list scroll for nothing.
			sui_list_view_begin("cs_list", [17, y + 1], [ls_x - 2, ls_y - 2],
			                    [ls_x - 14, ROW_H], ms_viewcount, ms_scroll, [0, 10]);

			vector rp = '0 0 0';
			for (float idx = sui_list_item(rp); idx > -1; idx = sui_list_item(rp))
			{
				float real = stof(bufstr_get(ms_view, idx));
				string rid = strcat("cs_row", ftos(idx));
				vector rs  = [ls_x - 14, ROW_H];

				sui_action_element(rp, rs, rid, sui_noop);

				float on  = (real == ms_selected);
				float hot = sui_is_hovered(rid);
				if (on || hot)
					sui_fill(rp, rs, on ? COL_ROW_SEL : COL_ROW_HOVER, 1, 0);

				/*
				  Two lines per row, not one.

				  ROW_H is 48 to hold a 16:9 thumbnail, which leaves room for the
				  name on one line and everything qualifying it on a second --
				  source, layout, counts.  Putting all of that on one line was
				  tried first and needed six columns across 900 px, which reads
				  as a spreadsheet; the map name is the thing being looked for
				  and it should be the only thing at full brightness.

				  Tokenizing ms_meta HERE is affordable precisely because
				  sui_list_item only emits visible rows -- about a dozen -- so
				  this is a dozen tokenize calls a frame, not 2200.
				*/
				local float mn, mpage, mcell, mstages, mbonus, mlinear;
				local string mtier, mpb, mtsrc;

				mn = tokenize(bufstr_get(ms_meta, real));
				mpage = mcell = -1;
				mstages = mbonus = mlinear = -1;
				mtsrc = "";
				if (mn > MT_UUID)
				{
					mlinear = (argv(MT_LINEAR) == "-") ? -1 : stof(argv(MT_LINEAR));
					mstages = (argv(MT_STAGES) == "-") ? -1 : stof(argv(MT_STAGES));
					mbonus  = (argv(MT_BONUS)  == "-") ? -1 : stof(argv(MT_BONUS));
					mpage   = (argv(MT_PAGE)   == "-") ? -1 : stof(argv(MT_PAGE));
					mcell   = (argv(MT_CELL)   == "-") ? -1 : stof(argv(MT_CELL));
				}
				if (mn > MT_TSRC)
					mtsrc = argv(MT_TSRC);

				ui_thumb([rp_x + 3, rp_y + 2], [78, 44], mpage, mcell);

				/*
				  Tier chip.  "--" for untiered, never "T0": 649 of the installed
				  maps are CS:S community maps Momentum has no record of, and
				  saying nothing is the honest answer for them.

				  A MARK RATHER THAN A COLOUR ALONE, in both non-ranked cases:
				  the distinction has to survive a screenshot and a colour-blind
				  reader, and "what does the dim one mean" is a question a
				  punctuation mark answers on its own.

				    T9   ranked, or an override -- someone stated it
				    T9?  a SUGGESTION, from the Unlisted/Beta sections
				    T9~  inherited from this map without its port suffix
				    --   nothing knows

				  The two marks are deliberately different shapes: "?" is "nobody
				  has ranked this yet", "~" is "this is probably that map".  See
				  MT_TSRC.
				*/
				mtier = bufstr_get(ms_tierv, real);
				if (stof(mtier) > 0 && mtsrc == "alias")
					sui_text([rp_x + 90, rp_y + 6], SZ_ROW,
					         strcat("T", mtier, "~"), COL_DIM, 0.85, 0);
				else if (stof(mtier) > 0 && mtsrc == "sugg")
					sui_text([rp_x + 90, rp_y + 6], SZ_ROW,
					         strcat("T", mtier, "?"), COL_DIM, 0.85, 0);
				else if (stof(mtier) > 0)
					sui_text([rp_x + 90, rp_y + 6], SZ_ROW,
					         strcat("T", mtier), COL_ACCENT, 1, 0);
				else
					sui_text([rp_x + 90, rp_y + 6], SZ_ROW, "--", COL_DIM, 0.6, 0);

				sui_text([rp_x + 126, rp_y + 4], SZ_ROW, bufstr_get(ms_name, real),
				         (on || hot) ? COL_ACCENT : COL_TEXT, 1, 0);

				// Second line: where it came from, what it is, then how it is
				// laid out.  The gamemode is here rather than in a column of its
				// own because it is the same word the filter chip above says, so
				// once a mode is picked it is redundant -- and a column that is
				// usually redundant still costs width on every row.
				local string sub, smode;
				sub = ui_srcname(stof(bufstr_get(ms_src, real)));
				smode = ui_mode_name(stof(bufstr_get(ms_modev, real)));
				if (smode != "")
					sub = sprintf("%s  ^9|^7  %s", sub, smode);
				if (mstages > 0)
					sub = sprintf("%s  ^9|^7  %g stages", sub, mstages);
				else if (mlinear == 1)
					sub = strcat(sub, "  ^9|^7  linear");
				if (mbonus > 0)
					sub = sprintf("%s, %g bonus", sub, mbonus);
				sui_text([rp_x + 126, rp_y + 26], SZ_ROW, sub, COL_DIM, 1, 0);

				// The time, right-aligned against the row's own right edge.
				// sui_text measures and offsets, so the anchor is the text end.
				mpb = bufstr_get(ms_pbv, real);
				if (mpb != "")
					sui_text([rp_x + rs_x - 8 - stringwidth(Time_TickString(stof(mpb), PM_TICK), TRUE, SZ_ROW),
					          rp_y + 14], SZ_ROW,
					         Time_TickString(stof(mpb), PM_TICK), COL_TEXT, 1, 0);
				else
					sui_text([rp_x + rs_x - 8 - stringwidth("--:--.---", TRUE, SZ_ROW),
					          rp_y + 14], SZ_ROW, "--:--.---", COL_DIM, 0.5, 0);

				if (sui_is_released(rid))
					ms_selected = real;
			}
			sui_list_view_end();
		}
	}

	// ---- start / back -------------------------------------------------
	if (ui_button("cs_start", [16, by], [150, 30],
	              sel == "" ? "pick a map" : "start"))
		ui_launch();

	if (ui_button("cs_back", [size_x - 116, by], [100, 30], "back"))
		menu_screen = SCREEN_MAIN;

	sui_pop_frame();
};

// ---------------------------------------------------------------------------
//  Engine entry points.
//
//  m_display / m_hide / m_newmap do NOT exist in FTE -- they are DarkPlaces
//  only.  The set the engine actually looks up is at pr_menu.c:3386-3403.
// ---------------------------------------------------------------------------
void() m_init =
{
	/*
	  BUILD 46: FIRST, AND THE ORDER IS THE WHOLE OF WHY IT WORKS.  m_init is the
	  earliest QC of any kind on a launch, so a value the player saved under an
	  old fs_ name is carried across BEFORE the registercvar below and before
	  csprogs or the server has registered anything.  cvar_set creates the new
	  name with the saved value; registercvar then declines to overwrite it,
	  which is the same FTE behaviour the rec_terms note below is about.
	  Run it after anything registers and the default would win instead.
	*/
	FS_CvarsMoved();

	Font_Init();

	menu_screen = SCREEN_MAIN;
	ms_query = "";
	ms_applied_query = "";
	ms_query_stale = FALSE;
	sv_name = "";

	/*
	  BUILD 22.  Read the acceptance and publish it for the other two VMs before
	  anything else can run: m_init is the earliest QC of any kind on a launch,
	  so csprogs cannot observe rec_terms before this has set it.

	  Registered here rather than relied on to exist, and set unconditionally --
	  including to 0 -- because an auto-created cvar from a previous session's
	  reference would otherwise persist as the empty string and read as accepted
	  by a >= test.  That is the build 20 trap, and it costs one line to not
	  repeat it.
	*/
	registercvar("rec_terms", "0", 0);
	ms_consent = ui_consent_read();
	cvar_set("rec_terms", ftos(ms_consent));
	if (ms_consent < FS_TERMS_VERSION)
		menu_screen = SCREEN_TERMS;

	ms_name = ms_src = ms_lst = -1;
	ms_tierv = ms_modev = ms_meta = ms_pbv = -1;
	ms_selected = -1;
	ms_filter = ms_applied_filter = FILTER_ALL;
	ms_tier = ms_applied_tier = 0;
	ms_mode = ms_applied_mode = 0;
	ms_view = buf_create();

	// ms_bgfor must not start equal to ms_selected, or the first frame would
	// skip the load and the backdrop would stay flat until you picked twice.
	ms_bgpic = "";
	ms_bgfor = -2;

	// Absolute cursor: getmousepos then returns virtual-screen coordinates
	// rather than a delta (pr_menu.c:1116-1140), which is what sui expects.
	setcursormode(TRUE, "", '0 0 0', 1);

	registercommand("ui_maplist");

	localcmd("bind escape togglemenu\n");

	// Headless self-check.  Command-line `+ui_maplist` cannot work: the
	// command buffer drains during startup, before M_Init has registered
	// anything.  A cvar read from here is the only hook that runs late
	// enough.
	//   ui_bootcheck 1  enumerate maps, report, quit
	//   ui_bootcheck 2  as 1, but stay up, screenshot the menu, then quit
	//                   (the only way to check the menu DRAWS without a human)
	//   ui_bootcheck 3  as 2, then drive the real launch path -- pick
	//                   surf_kitsune, press start, screenshot in-game, quit
	registercvar("ui_bootcheck", "0", 0);
	registercvar("ui_bootmap", "", 0);      // which map ui_bootcheck 3 loads

	// CS:GO and TF2 are mounted for their materials and models; their 272 maps
	// are not the point and are hidden.  See SRC_ASSET.
	registercvar("ui_maps_assetmounts", "0", 0);

	// "<yaw> <pitch> <yaw2> <pitch2>" for ui_bootcheck 3's two extra in-game
	// screenshots, taken from the start zone.  Empty uses a sane default.
	registercvar("ui_bootangles", "", 0);
	if (cvar("ui_bootcheck"))
	{
		print("^2FTESurf: menu.dat loaded\n");
		ui_maplist_print("surf_kitsune");

		if (cvar("ui_bootcheck") < 2)
			localcmd("quit\n");
		else
			m_open();
	}
};

// screensize is the VIRTUAL screen -- equal to the framebuffer at
// vid_conautoscale 1.  Declaring this with a vector parameter matters: two
// float parameters would make the engine assume a DarkPlaces menu and hand
// over physical pixel sizes instead (pr_menu.c:3391-3395).
void(vector screensize) m_draw =
{
	// The bootcheck driver runs OUTSIDE the menu_active gate on purpose: past
	// the launch step the menu is closed and in-game, and it still has to take
	// the last screenshot and quit.
	if (cvar("ui_bootcheck") >= 2)
		ui_bootcheck_tick();

	// m_draw is called EVERY frame whether or not the menu has focus
	// (menu.c:168-176), so the gate is ours to enforce.
	if (!menu_active)
		return;

	// Re-filter only on an actual change.  ms_query is mutated by
	// sui_text_input during the previous frame's draw, so comparing against
	// the applied copy here is the cheapest place to notice.
	if (ms_query != ms_applied_query || ms_filter != ms_applied_filter
	    || ms_tier != ms_applied_tier || ms_mode != ms_applied_mode)
		ui_refilter();

	sui_begin(screensize_x, screensize_y);

	// m_init can run before the renderer is up, in which case loadfont
	// allocates the slot but bakes nothing.  This retries, bounded.
	Font_Check();

	// Roboto is the baseline for the whole menu; the two places that want the
	// display face set it themselves and put this back.  Restored to
	// FONT_DEFAULT on the way out so nothing else on screen inherits it.
	Font_Set(ui_font_ui);

	/*
	  BUILD 22: the terms outrank whatever screen was selected, and they are
	  tested here rather than only at m_init so that bumping FS_TERMS_VERSION
	  takes effect on the next frame rather than the next launch.  There is no
	  route past this that does not go through ui_consent_write.
	*/
	if (ms_consent < FS_TERMS_VERSION)
		menu_screen = SCREEN_TERMS;

	if (menu_screen == SCREEN_TERMS)
		screen_terms(screensize);
	else if (menu_screen == SCREEN_CREATE)
		screen_create(screensize);
	else
		screen_main(screensize);

	sui_menu_nav();
	Font_Reset();
	sui_end();
};

void() m_open =
{
	setkeydest(2);
	menu_active = TRUE;

	// The list is always open now (there is no ms_open any more), so all this
	// has to do is make sure there is something in it.
	if (menu_screen == SCREEN_CREATE && ms_count == 0)
		ui_load_maps();
};

void() m_close =
{
	setkeydest(0);
	menu_active = FALSE;
};

float(float evtype, float scanx, float chary, float devid) Menu_InputEvent =
{
	float used = sui_input_event(evtype, scanx, chary, devid);

	if (evtype == IE_KEYDOWN && !used)
	{
		if (getkeybind(scanx) == "toggleconsole")
		{
			localcmd("toggleconsole\n");
			return TRUE;
		}

		if (scanx == K_ESCAPE || getkeybind(scanx) == "togglemenu")
		{
			// The first stage of this used to close the map dropdown, which is
			// gone: the list is permanent.  Leaving it in would have made the
			// first ESC press on the create screen look dead.
			/*
			  BUILD 23: ESC does nothing at all on the terms screen.  Without
			  this, a player already in a game when FS_TERMS_VERSION is bumped
			  could dismiss the screen with ESC -- the enforcement is in
			  Rec_HidOK() either way, so nothing would be recorded, but a
			  consent screen you can wave away is not one worth drawing.
			*/
			if (menu_screen == SCREEN_TERMS)
				return TRUE;

			if (menu_screen == SCREEN_CREATE)
				menu_screen = SCREEN_MAIN;
			else if (clientstate() == 2)
				m_close();          // in a game: ESC returns to it
			// Disconnected on the main menu: stay put.  Closing would leave
			// the user staring at an empty renderer with no way back except
			// the console.
			return TRUE;
		}
	}

	return FALSE;
};

float(string cmd) m_consolecommand =
{
	tokenize(cmd);

	if (argv(0) == "ui_maplist")
	{
		ui_maplist_print(argv(1));
		return TRUE;
	}

	return FALSE;
};

// wantmode comes from the engine's MP_Toggle chain.  0 means it wants us
// CLOSED -- and if we are already closed we must do nothing, because
// re-grabbing kdm_menu after the engine unlinked it trips its "Menuqc retook
// key grabs when ordered to yield. Killing." guard (pr_menu.c:3157) and
// unloads this whole VM.
void(float wantmode) m_toggle =
{
	if (wantmode == 0)
	{
		if (menu_active) m_close();
		return;
	}
	if (wantmode == 1)
	{
		if (!menu_active) m_open();
		return;
	}

	if (menu_active) m_close();
	else m_open();
};

void() m_shutdown =
{
};
