/*
===========================================================================
  m_main.qc -- FTESurf main menu.

  Deliberately two screens and nothing else:

      MAIN     create server
               exit

      CREATE   map picker (search + tier and gametype filters)
               public lobbies
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
  both reads "MOM CSS".

  BUILD 57: those two are the only sources LISTED.  The source strip is gone
  (Lex: "list only Momentum Mod and CS:S maps"), and a map in neither -- Half-
  Life 2's campaign and backdrops, a stray BSP in the gamedir -- is dropped in
  ui_load_maps' second pass.  The bits stay, because the row label and that
  test both read them.
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
//  actually draws.  Rebuilt only when the query or a filter changes, never
//  per frame.
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
float  ms_nsrc[SRC_COUNT];      // entries per SRC_*, for the load report

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

float  ms_selected;             // index into ms_name, -1 = nothing picked
vector ms_scroll;

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
    ms_modev   the gamemode id, as Momentum numbers it.  0 means unknown, and
               Momentum has no gamemode 0 either.  Read for the row's detail
               line and once per load by ui_cat_load; since build 57 the
               filter reads ms_catv, below, and not this.
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

/*
  ms_catv -- the GAMETYPE a map is filed under, one GC_* per map, as a string.
  Build 57.

  Not ms_modev, because 639 of the 1334 listed maps have no Momentum gamemode
  at all (measured 2026-09-12) -- nearly every CS:S-only map -- and the chips
  now start at surf and bhop rather than at "any".  Filtering on Momentum's id
  alone would have hidden 582 surf_ and bhop_ maps behind the default.  So
  ui_cat_load fills this once per load: Momentum's category where it has one,
  else the one the name prefix says (ui_name_cat), else GC_OTHER -- which is
  what makes "other" a gametype every map without one answers, rather than a
  hole maps fall into.
*/
strbuf ms_catv;

// Personal bests, indexed like the others: the full-run tick count for this map,
// as a string, or "" when neither data/runs/<map>/best.pb nor lobby.pb beside it
// has a `best 0 0` line.  See run_pb_load.
strbuf ms_pbv;
// "1" where the time in ms_pbv came from lobby.pb, "" where it is a local run.
strbuf ms_pblob;
// The personal-best report last printed, so reopening the screen stays quiet.
string ms_pbnote;
// gettime(0) when run_pb_load last ran, for ui_create_open's latch.  0 = never.
float  ui_pb_at;

// The tier filter, ANDed with the gametype set.  0 = any; otherwise the tier.
float  ms_tier;
float  ms_applied_tier;

/*
  The gametype SET, ANDed with the tier.  Build 57.

  One bit per GC_* category, GC_OTHER included (ui_cat_bit), where it used to
  be a single category with 0 for any.  Lex asked for two at once, surf and
  bhop by default, and a single-select strip cannot say that.

  NEVER 0.  The chips refuse to turn off the last lit one, and ui_modes_sane
  puts the default back over a saved 0 -- a set that lists nothing draws an
  empty list with no chip lit to explain why, which reads as a broken mount.

  Saved as ui_maps_modes: ui_create_open reads it, ui_modes_set writes it.
*/
float  ms_modes;
float  ms_applied_modes;

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

  Two strips use this, tier and gametype.  There were three, copies of the same
  twelve lines, until this existed; the third, source, went in build 57.  The
  gametype chips are toggles and the tier chips are not, and the difference is
  entirely in what the caller does with the click -- `on` is just a boolean.
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

  PATCH 270 ADDED A SECOND TIER RATHER THAN BUMPING THE VERSION, and the
  reasoning is at FS_TERMS_ONLINE in sh_defs.qc.  Short version: public lobbies
  made one sentence of the version-1 text false ("Nothing is sent anywhere"),
  but only for players who join one.  Bumping FS_TERMS_VERSION would have held
  every existing player at a screen whose only alternative was quitting, in
  order to re-agree to an offline game that had not changed.  The text below now
  covers both, an acceptance stamps the higher number, and only the paths that
  actually contact a server require it.

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
	if (i ==  7) return "^3Where it goes, playing on your own:";
	if (i ==  8) return "  files under this game's own data folder, on this machine.";
	if (i ==  9) return "  ^2Nothing about a run leaves this machine^7 -- there is no upload.";
	if (i == 10) return "";
	if (i == 11) return "^3Public lobbies, if you turn them on with the button below:";
	if (i == 12) return "  the other people on the map see your position and view angle,";
	if (i == 13) return "  and you see theirs. Voice and text chat reach everyone there.";
	if (i == 14) return "  The server times your run and shows you the time. It is not";
	if (i == 15) return "  uploaded or ranked anywhere. It sees your IP, as does any";
	if (i == 16) return "  server you join.";
	if (i == 17) return "  Lobby times are saved in this game's data folder on this PC.";
	if (i == 18) return "  The map picker asks ^9play.proto.bar^7 which lobbies are live";
	if (i == 19) return "  while it is open, which shows it your IP too.";
	if (i == 20) return "";
	if (i == 21) return "^3What it is for:";
	if (i == 22) return "  replaying your runs, and telling a real run from a scripted one.";
	if (i == 23) return "";
	if (i == 24) return "^3What is deliberately NOT recorded:";
	if (i == 25) return "  anything you type. While the console or a menu has focus the";
	if (i == 26) return "  journal keeps the timing of a keypress but drops which key it";
	if (i == 27) return "  was, so a password typed in the console cannot end up in a file.";
	if (i == 28) return "  Nothing outside this game's window is watched, ever.";
	if (i == 29) return "";
	if (i == 30) return "^3Turning it off:";
	// rec_hid, NOT fs_hid.  The cvar was renamed in build 46 with the rest of the
	// fs_ -> rec_ move (sh_defs.qc:1409 is the forward), and this line went on
	// naming the old one -- so the single actionable instruction on the consent
	// screen told the reader to set a cvar that nothing reads.  Found by looking
	// at the rendered screen, which is the only place it was visible.
	if (i == 31) return "  ^9rec_hid 0^7 stops the raw input journal. Runs recorded without it";
	if (i == 32) return "  are marked as such rather than passing as runs that had one.";
	return "";
};
/*
  29, not 30.  The line that used to sit at 16 read "lobby_dir is empty by
  default; while it is, nothing is sent."  It was removed in the same edit that
  gave lobby_dir a real default (menu/m_lobby.qc, Lob_Init), because the moment
  the cvar ships pointing at a directory that sentence is FALSE, and a false
  sentence on the consent screen is worse than no sentence at all.

  What replaces it is not another sentence: it is the FS_TERMS_ONLINE gate
  itself.  Nothing is sent before an acceptance at that tier; Lob_Poll checks
  it before it looks at lobby_dir at all, in that order, deliberately.

  TWO MORE LINES MOVED WITH IT, both for the same reason -- a review found them
  saying things the shipped defaults had made untrue:

    9   was "Playing offline sends nothing anywhere -- no server is involved".
        Not true of a player who accepts the online tier and then plays alone:
        opening the map picker polls the directory whether or not they ever
        join anything.  Narrowed to the claim that IS true and is the one this
        paragraph is about -- run data is not uploaded.

    11  was "which are OFF until you switch them on", which read as a promise
        of some later switch.  There is no later switch any more; the button at
        the foot of this screen IS it, so the line now points at the button.

  32 NOW, and the three added lines are the same lesson a third time.

  Lines 14-15 said "Your checkpoint and finish times go to that server so runs
  can be ranked."  NONE OF THAT HAPPENS.  A lobby finish takes the Lobby_NoPB()
  branch in sv_timer.qc and prints "ranked on the server, not saved here"; there
  is exactly one uri_post in the whole tree and it is the lobby heartbeat.  The
  sentence was written ahead of Stage 3's telemetry, the telemetry never came,
  and the text has been promising it since.  It now says what the server
  actually does, which is time your run and show you the time.

  THAT IS THE FAILURE MODE THIS FILE KEEPS REPEATING: a true-when-written
  sentence about a feature that was coming.  So the rule, and it is not
  negotiable on this screen -- DISCLOSE ONLY WHAT THE SHIPPED CODE DOES TODAY.
  Not what the next patch will do, however certain it is.

  The two new lines at 18-19 (17-18 until build 57) name the lobby directory,
  because polling it discloses an IP before any lobby is joined and the reader
  was never told which host that is.  play.proto.bar is written out rather than "a directory": a
  hostname the reader can look up is a disclosure, a category is not.

  ⚠ NOT MENTIONED, DELIBERATELY, AND IT MUST BE ADDED WITH THE CODE THAT MAKES
  IT TRUE: dl.proto.bar.  engine/common/qkupdate.c ships update_enabled 1,
  update_autocheck 1 and update_manifest_url https://dl.proto.bar/... -- but
  nothing anywhere calls `update_check`, so FTESurf contacts it zero times.
  Writing it here now would be the exact mistake above, in the same edit that
  fixes it.  Whoever wires the updater bumps FS_TERMS_ONLINE to 4 and adds the
  line in that change, not before.

  33 SINCE BUILD 57, and this line is that rule kept rather than broken: it
  arrived in the same change as the code that makes it true.  Line 17 says a
  lobby time is saved in this game's data folder on this PC, because build 57's
  client writes one into data/runs on the player's own disk when a run on a
  lobby beats their lobby best (Stage T, client/cl_lobbytime.qc).  Nothing new
  LEAVES the machine -- the lobby server already timed the run and sent the
  time to this client to print, and keeping it is local -- so FS_TERMS_ONLINE
  is not bumped, and 4 stays reserved for the updater.
*/
#define FS_TERMS_LINES 33

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

/*
  Record an acceptance at `tier` -- FS_TERMS_VERSION for the offline game,
  FS_TERMS_ONLINE to add public lobbies.

  IT TAKES A TIER BECAUSE THE FIRST VERSION DID NOT, AND THAT WAS A CONSENT BUG
  rather than an inconvenience.  It stamped FS_TERMS_ONLINE unconditionally,
  reasoning that one text covering both tiers makes accepting it an acceptance
  of both.  The text is indeed one text -- but the SCREEN offered a way to
  decline the online half only to someone who had already accepted the offline
  half (`ms_consent >= FS_TERMS_VERSION`, which is false on a fresh install).

  So a new player had exactly one button, and pressing it opted them into
  contacting a server.  Someone who only ever wanted to play offline had no way
  to say so and no indication they had agreed to anything else.  A tier scheme
  whose lower tier is unreachable is not a tier scheme.

  Both buttons are now always drawn, and the lower one is a real answer rather
  than a dismissal.  See screen_terms.
*/
void(float tier) ui_consent_write =
{
	local filestream fh;

	fh = fopen("data/consent.txt", FILE_WRITE);
	if (fh < 0)
	{
		print("^1could not write data/consent.txt\n");
		return;
	}

	// Never DOWNGRADE.  Someone who has already enabled lobbies and then
	// re-reads the terms and presses the offline button is asking to be left
	// alone on this screen, not to have an acceptance withdrawn behind their
	// back -- and a silent downgrade would empty the lobby list with nothing
	// said.  Turning lobbies back off is lobby_dir, which is a thing they can
	// see and set; see Lob_Blocked.
	if (tier < ms_consent)
		tier = ms_consent;

	fputs(fh, "FTESURF-CONSENT 1\n");
	fputs(fh, sprintf("version %g\n", tier));
	fputs(fh, sprintf("accepted %s\n", strftime(TRUE, "%Y%m%d-%H%M%S")));
	fclose(fh);

	ms_consent = tier;

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
	cvar_set("rec_terms", ftos(tier));
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

  BUILD 57: TEN CHIPS, AND THEY ARE TOGGLES.  "all", the eight categories, and
  "other" -- GC_OTHER, which Momentum does not have.  It is the gametype of a
  map with no Momentum gamemode and no movement prefix in its name: de_dust2,
  cs_office, ispy_*, the test maps -- 49 of the 1334 listed when measured.
  Each chip is one bit of ms_modes, so any set of them can be lit at once, and
  the strip still fits beside the tier chips at 1280 wide (~925 px of 1216).
*/
#define FS_NMODES   10          // "all", the eight gamemode CATEGORIES, "other"

// GamemodeCategory, gamemode.enum.ts.  Read through ui_mode_cat and ui_name_cat.
#define GC_SURF   1
#define GC_BHOP   2
#define GC_CLIMB  3
#define GC_RJ     4
#define GC_SJ     5
#define GC_AHOP   6
#define GC_CONC   7
#define GC_DEFRAG 8
/*
  Ours, not Momentum's: the gametype of a map that has none.  9 because
  Momentum's categories stop at 8, and it is a real category rather than 0 so
  that "other" is a chip that is lit or not like every other one.  ui_mode_cat
  never returns it; only ui_cat_load files a map under it.
*/
#define GC_OTHER  9

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
// which is nearly every CS:S-only row; ui_cat_load then files it by its name.
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
  because this is a surf trainer, then bhop, then the rest by population, and
  "other" last because it is the one nobody opens the picker looking for.
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
	case 9:  return GC_OTHER;   // no gamemode, no movement prefix
	}
	return 0;                   // slot 0 = "all"
};

string(float slot) ui_mode_label =
{
	switch (slot)
	{
	case 0:  return "all";
	case 1:  return "surf";
	case 2:  return "bhop";
	case 3:  return "rj";
	case 4:  return "sj";
	case 5:  return "climb";
	case 6:  return "defrag";
	case 7:  return "conc";
	case 8:  return "ahop";
	case 9:  return "other";
	}
	return "";
};

// The slot a category's chip sits in, or 0.  For the bootcheck driver, which
// toggles chips by what they mean rather than by where they happen to be drawn.
float(float cat) ui_mode_slot =
{
	local float s;

	for (s = 1; s < FS_NMODES; s = s + 1)
		if (ui_mode_id(s) == cat)
			return s;
	return 0;
};

/*
  One category's bit in ms_modes: 1 << (category - 1), so GC_SURF is 1, GC_BHOP
  2, GC_CLIMB 4, and so on to GC_OTHER at 256.  From 1 rather than from the
  category itself so the saved numbers stay short enough to read in ftesurf.cfg
  and to type at the console: surf and bhop is 3, everything is 511.

  0 for anything that is not a category, so a stray value is listed under no
  chip rather than shifting by a negative count.
*/
float(float cat) ui_cat_bit =
{
	if (cat < 1 || cat > GC_OTHER)
		return 0;
	return (int)1 << (int)(cat - 1);
};

// Both follow from ui_cat_bit and GC_OTHER; change either and change these.
#define FS_MODES_ALL      511   // (1 << GC_OTHER) - 1: every chip lit
#define FS_MODES_DEFAULT  3     // GC_SURF | GC_BHOP, what Lex asked to open on

/*
  Which gametype does this NAME say, or 0.  Build 57.

  ui_cat_load files a map Momentum has no gamemode for by its name, and the
  names that mean a gamemode are exactly the prefixes ui_isgamemode below
  already listed -- so that list became this function, and ui_isgamemode asks
  it.  ONE list, so a prefix added for the gametype filter cannot go missing
  from the Other-list test, or the other way round.

  Two prefixes have no Momentum category of their own and are filed where they
  play: xc_ is Xtreme-Climb, a KZ community, so climb; trikz_ is CS:S's
  two-player boosting mode on bhop movement, so bhop (one such map is in the
  CS:S library here, measured 2026-09-12).
*/
float(string nm) ui_name_cat =
{
	string p = strtolower(nm);

	if (substring(p, 0, 5) == "surf_")  return GC_SURF;
	if (substring(p, 0, 5) == "bhop_")  return GC_BHOP;
	if (substring(p, 0, 6) == "trikz_") return GC_BHOP;
	if (substring(p, 0, 5) == "ahop_")  return GC_AHOP;
	if (substring(p, 0, 3) == "kz_")    return GC_CLIMB;
	if (substring(p, 0, 3) == "xc_")    return GC_CLIMB;
	if (substring(p, 0, 6) == "climb_") return GC_CLIMB;
	if (substring(p, 0, 3) == "df_")    return GC_DEFRAG;
	if (substring(p, 0, 7) == "defrag_")return GC_DEFRAG;
	if (substring(p, 0, 3) == "rj_")    return GC_RJ;
	if (substring(p, 0, 3) == "sj_")    return GC_SJ;
	if (substring(p, 0, 5) == "conc_")  return GC_CONC;
	return 0;
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
	// The prefix list lives in ui_name_cat above; see why there.
	return ui_name_cat(nm) != 0;
};

/*
  How long ONE TICK of this map's stored times is, in seconds.  Build 57.

  THE .pb FILES HOLD TICKS AND NAME NO RATE.  A tick count is only a time once
  something says how long a tick is, and neither writer says: SV_PBSave
  (sv_timer.qc) and the client's LT_PBWrite (cl_lobbytime.qc) both write the
  header, the `#` line and `best <track> <leg> <ticks>`, and nothing else.  The
  server counted them at its own pm_ticrate (run_t_tick, SV_TimerMapInit), and
  the in-game board sidesteps the whole question by reading that live off the
  server (Timer_Tick, cl_scores.qc).  THIS VM CANNOT: the map list draws with no
  game running and no server to ask.  So the rate is worked out from the map,
  the same way the engine works out which ruleset to load in the first place.

  BHOP RUNS AT 100 Hz.  cfg/mode_bhop.cfg sets pm_ticrate 0.01 and the engine
  loads it for every bhop map (SV_ApplyGamemodeModes, sv_phys.c), so 30.000 s of
  bhop is 3000 ticks -- which PM_TICK would draw as 0:45.000, half again as long,
  with nothing on the row to say which of the two numbers is wrong.  Two of the
  five lobbies are bhop (cfg/lobby4.cfg, lobby5.cfg), so for a bhop map somebody
  has only ever played online this column is the ONLY time they are shown.

  THE RULE IS THE ENGINE'S, IN THE ENGINE'S ORDER: mapmeta's gamemode id where
  the map has one, else the name prefix (SV_MapMetaLookup then
  SV_GamemodeFromName).  Ids 2 and 3 are bhop and bhop-hl1 and BOTH end at
  cfg/mode_bhop.cfg -- there is no mode_bhop-hl1.cfg, so 3 falls through to its
  category, which is bhop (SV_GamemodeCategory).

  DELIBERATELY NOT ms_catv.  That is the FILTER's category, and it answers a
  different question: ui_name_cat files trikz_ under GC_BHOP because trikz is
  played on bhop movement, while the engine's own prefix table calls trikz_ mode
  5, kz -- which has no ruleset file at all, so a trikz map really does run at
  0.015.  Reading ms_catv here would fix the bhop rows and break that one.

  sv_gamemode is not consulted, though the engine checks it before either of
  these.  It pins the ruleset on the machine running the server, and a lobby time
  was counted on the Pi, whose cvars this menu cannot see.  It is empty on both
  by default, so this parts company with the engine only for someone who has
  deliberately forced a mode -- and then only on times set under that force.
*/
#define UI_TICK_BHOP 0.01       // cfg/mode_bhop.cfg's pm_ticrate

float(float row) ui_map_tick =
{
	local float mode;

	// "-" and a missing row both stof to 0, and there is no gamemode 0.
	mode = stof(bufstr_get(ms_modev, row));
	if (!mode)
		if (substring(strtolower(bufstr_get(ms_name, row)), 0, 5) == "bhop_")
			mode = 2;

	if (mode == 2 || mode == 3)
		return UI_TICK_BHOP;
	return PM_TICK;
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
  ms_catv, from ms_modev and the names.  Build 57.

  AFTER ui_meta_load and never inside it: that function returns early when
  mapmeta.txt is missing, and whether a surf_ map is a surf map must not depend
  on whether a metadata file exists.  With no file every map falls through to
  its name, which is the right answer for every one that has a prefix.

  Momentum's category wins where both exist, because it is a statement about
  the map rather than a reading of how somebody named it.
*/
void() ui_cat_load =
{
	local float i, c, s, k;
	local string rep;

	if (ms_catv >= 0) buf_del(ms_catv);
	ms_catv = buf_create();

	for (i = 0; i < ms_count; i = i + 1)
	{
		c = ui_mode_cat(stof(bufstr_get(ms_modev, i)));
		if (!c)
			c = ui_name_cat(bufstr_get(ms_name, i));
		if (!c)
			c = GC_OTHER;
		bufstr_add(ms_catv, ftos(c), TRUE);
	}

	/*
	  The census, in chip order.  One walk per chip -- nine walks of the list
	  at load and nothing afterwards -- rather than a counter array, which
	  would be a new global, and fteqcc charges an array about eight times its
	  length in progs size, to save a loop that runs once.  This line is what
	  "(N of M)" and the default surf + bhop are checked against.
	*/
	rep = "";
	for (s = 1; s < FS_NMODES; s = s + 1)
	{
		c = ui_mode_id(s);
		k = 0;
		for (i = 0; i < ms_count; i = i + 1)
			if (stof(bufstr_get(ms_catv, i)) == c)
				k = k + 1;
		rep = sprintf("%s  %s %g", rep, ui_mode_label(s), k);
	}
	print(sprintf("FTESurf: gametypes --%s\n", rep));
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

  BUILD 57: TWO FILES PER MAP, AND THE COLUMN SHOWS THE BETTER ONE.

  best.pb is what a run on this PC writes (SV_PBSave).  lobby.pb beside it is
  what the client writes when a run on a public lobby beats the player's lobby
  best (Stage T): a lobby server cannot write to this disk and saves nothing of
  its own, so the time is kept here.  Both use `best <track> <leg> <ticks>`, and
  `best 0 0` is the main track's full run in both.

  A lobby time is MARKED when it is the one shown, because nothing is behind it
  on this PC -- no replay, no splits -- and a number that looks like every other
  personal best invites clicking in to watch a run that is not there.  A tie
  shows the local time, which does have one.

  RUN AGAIN EVERY TIME THE CREATE SCREEN OPENS (ui_create_open).  It used to run
  only when the map list was built, which is once a session, so a time set in a
  lobby was missing from the list until a relaunch.  It stays cheap enough for
  that: two searches that find only the maps with a time, a hash of the names,
  and one small read per file found.  The report prints only when it changes,
  so reopening the screen does not fill the console.
*/

// The leaf itself is FS_LOBBYPB_LEAF, from shared/sh_defs.qc -- which is the
// second entry in m_progs.src and therefore in scope here, exactly as FS_PB_LEAF
// is on the line that reads best.pb.  There was a second #define of it here; two
// statements of one fact in the same build, and the one that would have gone
// stale is this one: the writer follows sh_defs.qc, so a moved leaf would have
// left the map list searching the old name, finding nothing, and showing no
// lobby times at all -- with no error and a clean compile.

/*
  The `best 0 0` ticks in one .pb file, or 0.

  THE HEADER IS CHECKED, AND BOTH VERSIONS PASS.  best.pb is "FTESURF-PB 1" as
  SV_PBSave writes it, or "FTESURF-PB 2" once tools/migrate_runs.py legs1 has
  renumbered its stage legs; lobby.pb is always 2.  Version 2 changed what a
  STAGE key means (stage k is leg k, where version 1 keyed by start segment) and
  left `best 0 0` meaning the full run, so for this column the two read alike.

  A version this build has never heard of is SKIPPED rather than guessed at.
  The column promises a full-run time, and a later format is precisely the thing
  that could change what 0 0 means.  A file with no header line at all is read
  as before: no build has written one, and refusing it would blank a time over a
  missing line rather than over a wrong one.
*/
float(string fn) run_pb_best =
{
	local filestream fh;
	local string ln;
	local float best, first, v;

	fh = fopen(fn, FILE_READ);
	if (fh < 0)
		return 0;

	best  = 0;
	first = TRUE;
	while ((ln = fgets(fh)) != "")
	{
		if (first)
		{
			first = FALSE;
			tokenize(ln);
			if (argv(0) == "FTESURF-PB")
			{
				v = stof(argv(1));
				if (v != 1 && v != 2)
					break;              // best is still 0: not read
				continue;
			}
		}

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
	return best;
};

/*
  Every data/runs/<map><leaf>, folded into ms_pbv.  Returns the files found.

  `lobby` says what this pass writes into ms_pblob.  run_pb_load calls it for
  best.pb first and lobby.pb second, and a row is replaced only by a STRICTLY
  faster time -- which is what makes a tie keep the local run.
*/
float(hashtable byname, string leaf, float lobby) run_pb_scan =
{
	local searchhandle h;
	local string fn, nm;
	local float i, n, row, cnt, best, have, pl, sl;

	h = search_begin(strcat(FS_RUNS_ROOT, "*", leaf), SB_NAMESORT, TRUE);
	if (h < 0)
		return 0;

	pl = strlen(FS_RUNS_ROOT);
	sl = strlen(leaf);

	cnt = search_getsize(h);
	for (i = 0; i < cnt; i = i + 1)
	{
		fn = search_getfilename(h, i);

		/*
		  "data/runs/surf_ace/best.pb" -> "surf_ace".  ui_mapname only knows
		  about maps/ and .bsp, so the trim is done here.

		  BOTH lengths are measured from the constants rather than typed.  An
		  earlier version wrote the prefix out as a literal AND its length as a
		  bare 10 on the next line, which is two statements of one fact that a
		  rename silently desynchronises -- and build 23 renamed it.
		*/
		nm = fn;
		n = strlen(nm);
		if (n > pl)
			if (strtolower(substring(nm, 0, pl)) == FS_RUNS_ROOT)
			{
				nm = substring(nm, pl, n - pl);
				n = n - pl;
			}
		if (n > sl)
			if (strtolower(substring(nm, n - sl, sl)) == leaf)
				nm = substring(nm, 0, n - sl);

		row = hash_get(byname, strtolower(nm), -1, EV_FLOAT);
		if (row < 0)
			continue;

		best = run_pb_best(fn);
		if (best <= 0)
			continue;

		have = stof(bufstr_get(ms_pbv, row));
		if (have > 0 && have <= best)
			continue;               // what is held is as fast or faster

		bufstr_set(ms_pbv,   row, ftos(best));
		bufstr_set(ms_pblob, row, lobby ? "1" : "");
	}

	search_end(h);
	return cnt;
};

void() run_pb_load =
{
	local hashtable byname;
	local string note;
	local float i, cnt, lcnt, times, ltimes;

	if (ms_pbv   >= 0) buf_del(ms_pbv);
	if (ms_pblob >= 0) buf_del(ms_pblob);
	ms_pbv   = buf_create();
	ms_pblob = buf_create();
	for (i = 0; i < ms_count; i = i + 1)
	{
		bufstr_add(ms_pbv,   "", TRUE);
		bufstr_add(ms_pblob, "", TRUE);
	}

	/*
	  BUILD 23: data/runs/<map>/best.pb, so the wildcard is a whole path
	  component and the map name is what it matches.

	  ONE wildcard, in a middle component -- the pattern SV_SaveLocScan has run
	  since build 17 and is therefore known to work in FTE's enumerator.  A
	  fixed leaf is why the name is best.pb rather than <map>.pb: the latter
	  would need two wildcards, which is a guess about Sys_EnumerateFiles2's
	  recursion that nothing on this disk currently proves.
	*/
	// Both searches are run_pb_scan's, and lobby.pb is a fixed leaf for the
	// reason above.
	byname = hash_createtab(4096, EV_FLOAT);
	for (i = 0; i < ms_count; i = i + 1)
		hash_add(byname, strtolower(bufstr_get(ms_name, i)), i,
		         HASH_REPLACE | EV_FLOAT);

	// best.pb FIRST.  run_pb_scan replaces a row only on a strictly faster time,
	// so this order is what makes a tie keep the local run.
	cnt  = run_pb_scan(byname, FS_PB_LEAF, FALSE);
	lcnt = run_pb_scan(byname, FS_LOBBYPB_LEAF, TRUE);
	hash_destroytab(byname);

	// Counted separately from the file count: a .pb with only stage times has no
	// full run to show, and "4 files, 1 time" is the difference between "the
	// search found nothing" and "you have not finished one of these yet".
	times = ltimes = 0;
	for (i = 0; i < ms_count; i = i + 1)
		if (bufstr_get(ms_pbv, i) != "")
		{
			times = times + 1;
			if (bufstr_get(ms_pblob, i) != "")
				ltimes = ltimes + 1;
		}

	// Once per CHANGE, not once per call: this now runs every time the create
	// screen opens, and the same line every ESC is noise that buries the line
	// that differs.
	note = sprintf("FTESurf: %g personal-best files, %g lobby-best files, "
	               "%g full-run times (%g of them from a lobby)\n",
	               cnt, lcnt, times, ltimes);
	if (note != ms_pbnote)
	{
		print(note);
		if (ms_pbnote != "")
			strunzone(ms_pbnote);
		ms_pbnote = strzone(note);
	}
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
	float unlisted = 0;
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
		  BUILD 57: MOMENTUM AND CS:S ONLY.  Lex: "list only Momentum Mod and
		  CS:S maps".  A map in neither -- Half-Life 2's campaign and its
		  background01/02, a stray BSP in the gamedir -- is not listed at all,
		  where it used to wait under the source strip's "other".

		  ms_src, the MOUNT, and not ms_lst.  ms_lst is decided by the NAME and
		  files every unprefixed map under Other whatever mount it came from, so
		  testing it would hide Momentum's own unprefixed maps (agtricks) while
		  catching nothing extra.  The question here is where the file is.

		  The asset mounts keep their own switch: with ui_maps_assetmounts 1 a
		  CS:GO or TF2 map is listed although it is in neither, which is what that
		  cvar has always meant.  Dropped in this compaction, so ms_count -- the M
		  in "(N of M)" -- counts only maps that can be listed.
		*/
		if (!(mask & (SRC_BIT_MOM | SRC_BIT_CSS)))
			if (!(showasset && (mask & SRC_BIT_ASSET)))
			{
				unlisted++;
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
	if (unlisted)
		print(sprintf("FTESurf: %g maps not listed -- in neither Momentum nor "
		              "Counter-Strike: Source\n", unlisted));

	// The counts overlap now, deliberately: a map in both Momentum and CS:S is
	// counted under both, because it is genuinely in both.  They no longer sum
	// to the total, and that is the point.
	print(sprintf("FTESurf: %g maps (%g duplicate entries coalesced) -- "
	              "momentum %g, counter-strike %g, other %g\n",
	              ms_count, dupes,
	              ms_nsrc[SRC_MOMENTUM], ms_nsrc[SRC_CSS], ms_nsrc[SRC_OTHER]));

	// All three join onto ms_name, so they can only run once it is final, and
	// ui_cat_load reads what ui_meta_load wrote.  None can fail in a way that
	// matters: a missing mapmeta.txt costs the metadata columns and files every
	// map by its name, and no .pb files means no times to show.
	ui_meta_load();
	ui_cat_load();
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


// Rebuild ms_view from the query and the two filters.  O(ms_count), but only
// ever run on a keystroke or a filter change -- never from m_draw's steady state.
void() ui_refilter =
{
	if (ms_view >= 0) buf_del(ms_view);
	ms_view = buf_create();
	ms_viewcount = 0;

	string q = strtolower(ms_query);

	for (float i = 0; i < ms_count; i++)
	{
		/*
		  The gametype set first, in the place the source filter had: with surf
		  and bhop lit it is the test that turns most maps away, and it costs one
		  bufstr_get.

		  A BIT test against the map's CATEGORY -- ms_catv, not ms_modev.  The
		  chip is "climb" and climb is three Momentum ids; and a map Momentum has
		  no id for still has a category (ui_cat_load), so there is no "unknown"
		  left for this to special-case.  That special case was the old rule
		  "0 answers only any", and with any no longer the default it would have
		  hidden every CS:S-only surf map.
		*/
		if (!(ms_modes & ui_cat_bit(stof(bufstr_get(ms_catv, i)))))
			continue;
		if (q != "" && strstrofs(strtolower(bufstr_get(ms_name, i)), q) < 0)
			continue;

		// Tier is a plain equality, and 0 in ms_tierv means UNTIERED rather than
		// tier zero -- so an untiered map answers only the "any" filter and never
		// gets swept into a numbered one.  This reads ms_tierv rather than
		// tokenizing ms_meta because it runs over every map on every keystroke.
		if (ms_tier != 0 && stof(bufstr_get(ms_tierv, i)) != ms_tier)
			continue;

		bufstr_add(ms_view, ftos(i), TRUE);
		ms_viewcount++;
	}

	ms_applied_query = ms_query;
	ms_applied_tier  = ms_tier;
	ms_applied_modes = ms_modes;
	ms_scroll = '0 0 0';
};

string() ui_selected_name =
{
	if (ms_selected < 0 || ms_selected >= ms_count)
		return "";
	return bufstr_get(ms_name, ms_selected);
};

/*
  ---------------------------------------------------------------------------
   The gametype set: click, save, open.  Build 57.
  ---------------------------------------------------------------------------
*/

// A saved or typed value made usable: real category bits only, and never the
// empty set -- see ms_modes for why that is not a state worth drawing.
float(float m) ui_modes_sane =
{
	m = m & FS_MODES_ALL;
	if (!m)
		m = FS_MODES_DEFAULT;
	return m;
};

/*
  What clicking chip `slot` makes of `mask`.  PURE -- it neither assigns nor
  saves -- so the bootcheck driver can put the chips' own rule through its paces
  without writing the player's config.

  "all" sets every bit, and is not a toggle, because "all off" is the empty set.
  Any other chip flips its own bit, EXCEPT the last lit one, which stays on:
  with nothing lit the list would be empty and no chip would say why.
*/
float(float mask, float slot) ui_modes_click =
{
	local float b;

	if (slot == 0)
		return FS_MODES_ALL;

	b = ui_cat_bit(ui_mode_id(slot));
	if (!(mask & b))
		return mask | b;
	if (mask == b)
		return mask;                // the last lit chip will not switch off
	return mask - b;
};

/*
  Apply and SAVE.  `seta`, for the reason at the top of client/cl_hudedit.qc and
  in m_lobby.qc's lobby_dir migration: Cmd_set_f's not-from-gamecode branch
  (cmd.c:4266) is the only path that puts CVAR_ARCHIVE on a cvar that already
  exists, so a cvar_set here would hold for the session and be gone after a quit.
  Queued by localcmd, which runs long before the one reader -- ui_create_open,
  the next time the screen opens -- can look.
*/
void(float mask) ui_modes_set =
{
	ms_modes = mask;
	localcmd(sprintf("seta ui_maps_modes %g\n", mask));
};

/*
  Everything that has to happen when the create screen comes up.  Build 57.

  THREE DOORS lead to that screen and they did three different things: the
  create button (load if empty, refilter), m_open reopening the menu on the
  screen it was left on (load if empty), and the bootcheck driver (load,
  refilter).  All three come through here now.  That is what makes "the list
  shows a time set since the screen was last open" true on the door players use
  most -- ESC out of a lobby, which lands straight back on this screen -- and not
  only on the button.

  THE CVAR IS REGISTERED BESIDE ITS READ, for the trap that has silently killed
  three features in this tree: cvar() on an unregistered name auto-creates it as
  "", and a later registercvar() declines to overwrite it.  32 is CVAR_ARCHIVE,
  a literal for the reason Lob_Init gives; it matters only on the very first
  run, where this is the creating call, and ui_modes_set's `seta` is what keeps
  it archived after that.

  READ EVERY TIME, not once, so `ui_maps_modes 2` typed at the console shows the
  next time the screen opens.  A changed ms_modes is picked up by m_draw's
  change check, so this does not refilter -- except after loading the list, when
  there is no view yet and nothing else would notice.
*/
void() ui_create_open =
{
	registercvar("ui_maps_modes", ftos(FS_MODES_DEFAULT), 32);
	ms_modes = ui_modes_sane(cvar("ui_maps_modes"));

	if (ms_count == 0)
	{
		ui_load_maps();             // which runs run_pb_load itself
		ui_refilter();
		ui_pb_at = gettime(0);
		return;
	}

	/*
	  BUILD 57: RESCANNED ON A LATCH, because m_open routes through here and ESC
	  is the key players press most.

	  The rescan is two directory enumerations plus one open-and-read per .pb
	  found, synchronous inside the menu frame, and it scales with the size of
	  data/runs -- a few hundred map folders for anyone who has played a while.
	  The plan asked for it "when the create screen opens", which it still is; what
	  it must not become is per-ESC work proportional to the player's records.

	  Two seconds is chosen against what the rescan is FOR: a time set since the
	  screen was last open.  Setting one takes a run, so no real sequence can beat
	  the latch -- while ESC-in, ESC-out, ESC-in does, every time.
	*/
	if (ui_pb_at != 0 && gettime(0) - ui_pb_at < 2)
		return;

	ui_pb_at = gettime(0);
	run_pb_load();
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

	// The name field went in build 57 (Lex).  This is a private, unlisted
	// practice game, so a name had nowhere to be read.  Still SET rather than
	// left alone, because the engine's own default is "unnamed".
	cvar_set("hostname", "FTESurf");

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

/*
  Patch 270 -- joining a public lobby.

  IS THE ADDRESS SAFE TO PUT IN A CONSOLE COMMAND?  No, not without this.

  The string came off the network from whatever host lobby_dir names.  It goes
  to localcmd, which is the console -- so an address of
  "1.2.3.4:1\nquit\n" or "1.2.3.4:1; exec something" is remote code execution
  against anyone whose picker is open, from a directory that is compromised, is
  someone else's, or is simply typo'd into a hostile host.  %S quotes and
  escapes for the QC parser and is worth having, but it is not the thing being
  relied on here.

  An allow-list, not a deny-list.  Deny-lists on shell-ish input are how this
  goes wrong: enumerate the characters an address may contain, reject
  everything else, and no new metacharacter anybody thinks of later gets
  through.  Numeric codes because 'x' in QuakeC is a VECTOR literal, not a
  character.

    48-57  0-9        46  .        (dotted quad, and the decimal in a port)
    97-122 a-z        58  :        (host:port separator)
    65-90  A-Z        45  -        (hostnames)
*/
float(string a) ui_addr_ok =
{
	local float i, n, c;

	n = strlen(a);
	if (n < 3 || n > 64)
		return FALSE;

	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(a, i);
		if (c >= 48 && c <= 57)  continue;
		if (c >= 97 && c <= 122) continue;
		if (c >= 65 && c <= 90)  continue;
		if (c == 46 || c == 58 || c == 45) continue;
		return FALSE;
	}
	return TRUE;
};

/*
===========================================================================
  THE LOBBY HOST ALLOW-LIST.  Build 55, plan Stage 8b.

  WHAT IT IS FOR.  ui_addr_ok above proves an address is well FORMED; it says
  nothing about WHERE it points.  The address comes from /lobbies.json, which
  comes from whoever answers lobby_dir -- so today the operator of that one
  service chooses, for every player, what host their game runs `connect` at.
  A compromised or substituted directory redirects the entire player base
  somewhere else and nothing in the client objects.

  This turns "anywhere" into "one of these".  It is the difference between
  trusting a service and trusting a service to stay honest.

  NOT CVAR_ARCHIVE, AND THAT IS THE WHOLE POINT.  lobby_dir is archived and it
  is why Stage 8c needs a migration: an install that saved the old value never
  sees a new default again.  For an allow-list that is exactly backwards -- a
  list that can never be updated is a list that goes stale and starts refusing
  the servers it is supposed to permit.  Shipping it unarchived means it
  arrives with the game and the updater can change it, which is what Stage 7's
  updater is for.  Someone who wants to override it can still set it from a
  cfg; it just does not persist by accident.

  THE LAN ADDRESS IS IN THE DEFAULT ON PURPOSE.  The lobbies advertise
  192.168.1.102:275x0 today and will until DNS, the port forwards and
  SURFD_PUBLIC_HOST are all in place.  A default of only the public names would
  refuse every lobby that currently exists, which is a regression shipped in
  the name of security.  Remove it when play.proto.bar actually resolves.

  EMPTY MEANS DISABLED, deliberately, so a player on a private server or a LAN
  party is never stuck behind a list they cannot reach a developer about.
===========================================================================
*/
#define FS_LOBBY_HOSTS_DEFAULT "play.proto.bar proto.bar 180.150.62.57 192.168.1.102"

/*
  The host half of "host" or "host:port", lowercased.

  FIRST colon, not last.  The menu does not accept bracketed IPv6 -- ui_addr_ok
  has no brackets in its character set and surfd refuses to emit one for the
  same reason -- so a colon here is always the port separator.
*/
string(string a) ui_host_of =
{
	local float p;

	p = strstrofs(a, ":");
	if (p < 0)
		return strtolower(a);
	return strtolower(substring(a, 0, p));
};

float(string a) ui_host_allowed =
{
	local string list, h;
	local float n, i;

	/*
	  REGISTERED BESIDE THE READ, and not up in Lob_Init with the other lobby_
	  cvars, for the reason that has silently killed three features in this
	  tree already: cvar_string() on an unregistered name AUTO-CREATES it as
	  "", and a later registercvar() then declines to overwrite it.  If any
	  path reached this function before Lob_Init ran, the list would be
	  permanently empty -- which this function reads as "disabled" and would
	  turn the whole allow-list off without a word.  Registering here makes
	  that ordering impossible to get wrong.
	*/
	registercvar("lobby_hosts", FS_LOBBY_HOSTS_DEFAULT, 0);

	list = cvar_string("lobby_hosts");
	if (list == "")
		return TRUE;                 // explicitly disabled by the operator

	h = ui_host_of(a);
	if (h == "")
		return FALSE;

	// tokenize() clobbers argv globally. Safe here: ui_connect is the only
	// caller and does not read argv afterwards.
	n = tokenize(list);
	for (i = 0; i < n; i = i + 1)
		if (strtolower(argv(i)) == h)
			return TRUE;
	return FALSE;
};

/*
  The map-list index for a map name, or -1.

  A linear scan, called at most LB_MAX (five) times a poll and only when a
  lobby cell is first drawn -- the answer is cached back into the lobby list by
  the caller.  There is no production name->index map in this file to reuse
  and building one for five lookups a poll would cost more than it saved.

  CASE-INSENSITIVE since build 66, and that is not tidiness.  ms_name holds the
  case the file has ON DISK and the installed library is not all lowercase
  (Bhop_Mukiology is the one that has already cost a wrong answer elsewhere),
  while the name a lobby reports is whatever its server was handed.  An exact
  compare therefore returns -1 for a map that IS installed, and -1 is not an
  inert answer in either caller: the lobby cell draws it as a red "not
  installed", and ui_map_players below reads it as "no lobby is on this map" and
  so draws no headcount.  Both are wrong, both are silent, and both land only on
  the capitalised minority nobody thinks to check.

  strcasecmp is a builtin comparison that allocates nothing, so this costs the
  same as the == it replaces.  Lowercasing every name instead would have meant
  2200 tempstrings per lookup, five times a poll, to answer one question.
*/
float(string nm) ui_map_index =
{
	local float i;

	for (i = 0; i < ms_count; i = i + 1)
		if (!strcasecmp(bufstr_get(ms_name, i), nm))
			return i;
	return -1;
};

/*
  How many players are on one map right now, or -1 if no lobby is on it.

  THE TWO ANSWERS ARE DIFFERENT AND MUST STAY DIFFERENT.  0 means "a lobby is
  running this map and nobody is on it".  -1 means "no lobby the directory has
  told us about is on this map" -- which covers the directory not having
  answered yet, consent never given so it was never asked, the directory being
  down, and the ordinary case of a map with nothing running on it.  Every one of
  those is "we do not know", and a caller that folded them into 0 would print a
  headcount against 2200 maps that nobody has claimed anything about.  That is
  the same rule the results card's world row settles on in build 65: silence is
  what you draw when you have not been told, and it is not the same glyph as a
  measured zero.

  It reads Lob_Row's cache rather than comparing names, so a row costs five
  float compares and the 2200-name scan still happens at most five times a poll
  -- the contract the lobby cells already have.  It resolves that cache itself
  when the cells have not, because the whole grid is skipped when the directory
  holds no rows, and a helper that only works if something else drew first is a
  helper that breaks the next time the layout moves.

  The mapidx < 0 guard is load-bearing rather than defensive: -1 is also what
  Lob_Row stores for "that lobby's map is not installed here", so without it a
  caller passing a bad index would be told the headcount of every uninstalled
  lobby, summed.
*/
float(float mapidx) ui_map_players =
{
	local float i, n, lrow, sum, found;

	if (mapidx < 0)
		return -1;

	sum   = 0;
	found = FALSE;
	n     = Lob_Count();

	for (i = 0; i < n; i = i + 1)
	{
		lrow = Lob_Row(i);
		if (lrow == -2)
		{
			lrow = ui_map_index(Lob_Map(i));
			Lob_SetRow(i, lrow);
		}
		if (lrow == mapidx)
		{
			sum   = sum + Lob_Players(i);
			found = TRUE;
		}
	}

	if (!found)
		return -1;
	return sum;
};

/*
  The headless twin of the headcount the map list draws.  Build 66.

  The row itself needs the create screen open and a pointer on it, and neither
  is reachable from a config -- so without this the only way to check the
  feature is to look at it, which is the standard this tree holds itself to
  everywhere else.  It prints the directory's own rows AND what each map row
  would draw from them, because those are two different claims: the first is the
  input and the second is the thing under test, and a bug in the join between
  them shows up as the two disagreeing.

  IT POLLS AS WELL AS REPORTS.  Lob_Poll runs only from m_draw while the create
  screen is up, so a first call from a cold console would report an empty
  directory forever and read as "the feature does not work".  Calling it here
  makes the shape `ui_lobbypop`, wait, `ui_lobbypop` -- the first call is what
  gives the second one something to say.  Lob_Poll rate-limits itself, so
  calling it twice costs one request.

  The "has NOT answered" line is deliberately separate from "0 lobbies": they
  look identical in a list and they are opposite diagnoses.
*/
void() ui_lobbypop_print =
{
	local float i, n, lrow, pop, drawn;
	local string nm;

	ui_load_maps();
	Lob_Poll();

	n = Lob_Count();
	print(sprintf("ui_lobbypop: directory %s -- %g lobbies, %g maps installed\n",
	              Lob_Ready() ? "has answered" : "has NOT answered yet",
	              n, ms_count));
	if (Lob_Blocked())
		print("  the online tier has not been accepted, so nothing is asked "
		      "for and no count can exist\n");

	for (i = 0; i < n; i = i + 1)
	{
		lrow = Lob_Row(i);
		if (lrow == -2)
		{
			lrow = ui_map_index(Lob_Map(i));
			Lob_SetRow(i, lrow);
		}
		nm = (lrow >= 0) ? bufstr_get(ms_name, lrow)
		                 : "^1not installed here^7";
		print(sprintf("  lobby %-22s %g/%g  row %g  %s\n",
		              Lob_Map(i), Lob_Players(i), Lob_Max(i), lrow, nm));
	}

	drawn = 0;
	for (i = 0; i < ms_count; i = i + 1)
	{
		pop = ui_map_players(i);
		if (pop >= 0)
		{
			print(sprintf("  row %-5g %-22s draws \"%g playing\"\n",
			              i, bufstr_get(ms_name, i), pop));
			drawn = drawn + 1;
		}
	}
	print(sprintf("  %g of %g rows draw a count; every other row draws nothing\n",
	              drawn, ms_count));
};

/*
  The falsifier for engine Patch 316 -- does a write actually reach the disk
  before fclose?

  IT IS HERE, IN THE MENU, FOR ONE REASON: this is the only VM whose sources
  this session owns outright, so menu.dat can be rebuilt without compiling a
  concurrent session's half-finished client and server code into the result.
  The consumer of the patch is the run recorder in sv_timer.qc, and that is a
  separate change -- it should not be the thing that first discovers whether the
  builtin works.

  THE TEST CANNOT BE COMPLETED FROM INSIDE THE ENGINE, and that is the whole
  design problem.  Every number QC can ask for is identical under both modes:
  fseek reports the same position, the same lines went in, and a readback after
  close succeeds either way -- because the buffered mode produces a perfectly
  good file that simply has not been handed to the OS yet.  The single
  observable difference is THE SIZE ON DISK WHILE THE HANDLE IS STILL OPEN, and
  nothing inside this process can read that.

  So this writes, then HOLDS the handle open and announces it, and the run
  script measures the file from the shell during that window:

      stream   -> already its full size while held
      buffered -> 0 bytes or absent while held, whole the instant it is closed

  The buffered arm is not decoration.  It reproduces on purpose exactly what the
  build-15 comment over rec_rec_buf describes discovering the hard way --
  "that looked like streaming and never was ... the .part file was zero bytes
  until the moment it was closed" -- so a run in which both arms read the same
  is a broken harness, not a passing patch.

  IT IS TWO COMMANDS AND NOT ONE, and the reason is not style.  The obvious
  shape -- open, write, wait a few seconds, close -- cannot be written here: a
  QC VM aborts on a runaway loop, so a busy wait long enough for the shell to
  look is a wait long enough to kill the VM, and a menu console command has
  nothing to yield to in any case.  So the handle is parked in a global and the
  cfg's own `waitms` provides the window, which is what waitms is for.

  b316_held is a separate flag rather than a sentinel in the handle itself,
  because a QC global starts at 0 and 0 is not a value fopen can return:
  FIRST_QC_FILE_INDEX is 1000 (pr_bgcmd.c), so every real handle is >= 1000 and
  a `b316_fh >= 0` test would read an untouched global as an open file.
*/
filestream b316_fh;
float      b316_held;
string     b316_path;

void(string verb, string mode) ui_fstream_test =
{
	local float i, mv, pos;
	local string ln;

	if (verb == "open")
	{
		if (b316_held)
		{
			print("^1b316: a handle is already held; close it first^7\n");
			return;
		}

		mv        = (mode == "buffered") ? FILE_WRITE : FS_FILE_WRITESTREAM;
		b316_path = (mode == "buffered") ? "data/b316_buffered.txt"
		                                 : "data/b316_stream.txt";

		b316_fh = fopen(b316_path, mv);
		if (b316_fh < 0)
		{
			print(sprintf("^1b316: fopen(\"%s\", %g) FAILED^7\n", b316_path, mv));
			return;
		}
		b316_held = TRUE;

		// Enough bytes to be well clear of the 8 KB the buffered mode starts
		// with, so "nothing on disk" and "not grown yet" cannot read the same.
		for (i = 0; i < 2000; i = i + 1)
			fputs(b316_fh, sprintf("%05g this is a recorded sample line, padded "
			                       "out so that it resembles a real one\n", i));

		/*
		  Reserve-and-correct, which is the recorder's actual requirement: the
		  `flags` header line cannot be known until the run has ended.  Seek to
		  the start, overwrite line 0 IN PLACE at the same width, and put the
		  position back.  If seek silently does nothing on a stream, the readback
		  prints the original line 0 -- a fault, not a warning.
		*/
		pos = fseek(b316_fh);
		fseek(b316_fh, 0);
		fputs(b316_fh, "XXXXX this is a recorded sample line, padded ");
		fseek(b316_fh, pos);

		print(sprintf("b316: HOLDING %s mode %g, %g bytes written -- "
		              "measure the file NOW\n", b316_path, mv, pos));
		return;
	}

	if (verb == "close")
	{
		if (!b316_held)
		{
			print("^1b316: nothing is open^7\n");
			return;
		}
		fclose(b316_fh);
		b316_held = FALSE;
		print(sprintf("b316: CLOSED %s\n", b316_path));

		b316_fh = fopen(b316_path, FILE_READ);
		if (b316_fh < 0)
		{
			print("^1b316: could not reopen for read -- nothing was written^7\n");
			return;
		}
		ln = fgets(b316_fh);
		print(sprintf("b316: line 0 reads \"%s\"\n", ln));
		for (i = 1; i < 2000; i = i + 1)
			ln = fgets(b316_fh);
		print(sprintf("b316: line 1999 reads \"%s\"\n", ln));
		fclose(b316_fh);
		return;
	}

	print("b316: usage -- ui_fstream open <stream|buffered> / ui_fstream close\n");
};

/*
  ---- `ui_who` -- the build 66 filename grammar, falsified headlessly. -------

  The player segment (FS_PlayerSeg / FS_NameSlug, shared/sh_defs.qc) takes
  ARBITRARY TEXT FROM A STRANGER and turns it into part of a path.  That is the
  one piece of this build where being approximately right is a security bug
  rather than a cosmetic one, and it is also the piece an in-game test reaches
  worst: a run takes a map load and a flight to the end zone to produce ONE
  name, and the interesting inputs are the ones no player will type by accident.

  So the arms are a TABLE IN THE SOURCE rather than arguments at a prompt, and
  each row checks itself.  Four properties, and every one of them is a failure
  this build could actually have:

    1. THE SEGMENT CANNOT LEAVE THE DIRECTORY.  `../../autoexec` is two
       keystrokes in a name field.  A slug that kept '.' or '/' would write
       outside data/runs, and nothing downstream would notice.
    2. THE SEGMENT CANNOT CONTAIN '_'.  The name is parsed by taking the tag
       from the LAST underscore and the stamp from the FIRST, so an underscore
       inside the middle field silently moves both boundaries.  An unknown tag
       word does not mislabel a row, it DROPS it (FS_TagFromName) -- so the
       symptom would be lobby times that are simply not on the board.
    3. IT ROUND-TRIPS.  Whatever FS_RunLeaf writes, FS_NameTicks / FS_NameWho /
       FS_NameTag must read back unchanged.  This is the property the three
       client readers depend on and none of them can check.
    4. THE ID IS REAL.  digest_hex is called here for the first time anywhere in
       this tree; a build where it is missing or does not know "SHA256" returns
       a short string, FS_PlayerSeg refuses, and every lobby run falls back to
       the slot.  That degrades quietly, so it is asserted loudly.

  Menu-side because the menu compiles the same shared/sh_defs.qc the server
  does, and because it needs no map: `menu_restart` then `ui_who` answers in
  one launch.  What it does NOT cover is the half only the server knows --
  Lobby_Active(), the GUID actually arriving, and the slot fallback -- which is
  what the in-game arm of cfg/testrun/b66who.cfg is for.
*/
float b66_fail;

void(string label, string nm, string guid, float ticks, string tag) ui_who_row =
{
	local string seg, leaf, stem;
	local float  bad;

	seg  = FS_PlayerSeg(nm, guid);
	leaf = FS_RunLeaf(ticks, seg, tag, "rec");
	stem = substring(leaf, 0, strlen(leaf) - 4);    // drop ".rec"

	bad = 0;

	// 1 and 2: what the segment may not contain.  '.' is checked as well as the
	// separators because a leading ".." is the traversal and a trailing "." is a
	// Windows filename that does not exist once it is created.
	if (FS_FirstOf(seg, 95) >= 0)  bad = bad + 1;   // '_'
	if (FS_FirstOf(seg, 47) >= 0)  bad = bad + 2;   // '/'
	if (FS_FirstOf(seg, 92) >= 0)  bad = bad + 4;   // '\'
	if (FS_FirstOf(seg, 46) >= 0)  bad = bad + 8;   // '.'
	if (FS_FirstOf(seg, 32) >= 0)  bad = bad + 16;  // ' '

	// 3: the round trip.  An unstamped leaf (ticks < 0) reads back as 0, which
	// is the "not archived, go and read the trailer" answer and not a mismatch.
	if (FS_NameTicks(stem) != ((ticks < 0) ? 0 : ticks))  bad = bad + 32;
	if (FS_NameWho(stem)   != seg)    bad = bad + 64;
	if (FS_NameTag(stem)   != tag)    bad = bad + 128;

	// 4: a real guid must produce a real id.  FS_WHO_IDLEN hex characters, plus
	// the slug and its '-' when the name had any letters in it at all.
	if (guid != "")
	if (strlen(seg) < FS_WHO_IDLEN)   bad = bad + 256;

	if (bad)
		b66_fail = b66_fail + 1;

	print(sprintf("%s %-22s seg \"%s\"\n", bad ? "^1FAIL^7" : "^2ok  ^7",
	              label, seg));
	print(sprintf("       leaf %s  -> ticks %g who \"%s\" tag \"%s\"%s\n",
	              leaf, FS_NameTicks(stem), FS_NameWho(stem), FS_NameTag(stem),
	              bad ? sprintf("   ^1[bad %g]^7", bad) : ""));
};

void() ui_who_print =
{
	local string g;

	g = "0123456789abcdef0123456789abcdef";   // a guid-shaped constant

	b66_fail = 0;

	print("ui_who: digest_hex(\"SHA256\", \"\") = \"");
	print(digest_hex("SHA256", ""));
	print("\"\n");

	ui_who_row("plain",        "lex",                  g, 279, "pb");
	ui_who_row("mixed case",   "LeX",                  g, 279, "pb");
	ui_who_row("colour codes", "^1l^2e^3x",            g, 279, "pb");
	ui_who_row("underscored",  "l_e_x",                g, 279, "pb");
	ui_who_row("traversal",    "../../autoexec",       g, 279, "pb");
	ui_who_row("backslash",    "..\\..\\autoexec",     g, 279, "pb");
	ui_who_row("spaces+punct", "Lex the Great!",       g, 279, "pb");
	ui_who_row("very long",    "abcdefghijklmnopqrstuvwxyz", g, 279, "pb");
	ui_who_row("no letters",   "!!!",                  g, 279, "pb");
	ui_who_row("empty name",   "",                     g, 279, "pb");
	ui_who_row("other guid",   "lex",  "ffffffffffffffffffffffffffffffff", 279, "pb");
	ui_who_row("no guid",      "lex",                  "", 279, "pb");
	ui_who_row("unstamped",    "lex",                  g,  -1, "last");
	ui_who_row("no guid, unst","lex",                  "", -1, "last");

	/*
	  THE AMBIGUOUS PAIR.  `0000279_pb` and `lex-a3f19c2b_last` both carry
	  exactly one underscore and mean opposite things, so the parse recognises a
	  stamp by SHAPE -- seven digits then '_'.  These two rows are the adversary
	  for that rule: a name that slugs to seven digits, stamped and unstamped.
	  If FS_NameStamped ever went back to counting underscores, the unstamped one
	  would read its own player segment as a tick count of 279.
	*/
	ui_who_row("7-digit name",   "0000279",            g, 279, "pb");
	ui_who_row("7-digit, unst",  "0000279",            g,  -1, "last");

	/*
	  THE SAME NAME UNDER TWO GUIDS MUST DIFFER, and the same guid under two
	  names must share its id.  That pair is the whole point of carrying both
	  fields, and neither half is visible in a row-by-row check: the first is the
	  collision the build exists to fix, the second is what lets a player's runs
	  still group after they rename themselves.
	*/
	if (FS_PlayerSeg("lex", g) == FS_PlayerSeg("lex", "ffffffffffffffffffffffffffffffff"))
	{
		b66_fail = b66_fail + 1;
		print("^1FAIL^7  two guids, one segment -- the collision is not fixed\n");
	}

	// An empty name yields the id ALONE, which is what makes this readable: the
	// two named forms must be exactly that id with their slug and a '-' in
	// front, so the join is checked here as well as the stability.
	if (FS_PlayerSeg("lex", g) != strcat("lex-", FS_PlayerSeg("", g))
	 || FS_PlayerSeg("bob", g) != strcat("bob-", FS_PlayerSeg("", g)))
	{
		b66_fail = b66_fail + 1;
		print("^1FAIL^7  one guid, two ids -- a rename would orphan the runs\n");
	}

	print(sprintf("ui_who: %s\n",
	              b66_fail ? sprintf("^1%g FAILURES^7", b66_fail) : "^2all rows pass^7"));
};

/*
  ---- `ui_who glob` -- THE PRUNER'S PATTERN, WHICH DELETES FILES. ------------

  SV_RecPrune holds the archive to rec_runs_keep files per leg per tag and
  sweeps SLOWEST FIRST, which is safe on a single-player disk for one reason:
  the names begin with a zero-padded tick count, so an ascending NAME sort is an
  ascending TIME sort and the entries past the quota are the slowest ones.  On a
  lobby that same rule becomes "delete the slowest PLAYER" -- one quota shared
  by thirty-two people, and twenty-five fast runs from a regular would evict
  every recording a newcomer had ever set.  So build 66 puts `who` in the
  pattern.

  THIS IS THE ONE CHANGE IN THE BUILD THAT DESTROYS DATA IF IT IS WRONG, and it
  is the one a scripted run cannot reach: the pruner fires only for an ARCHIVED
  tag, every finish a config can produce is a `cheated` one (the flight to the
  end zone is under noclip), and a cheated run is deliberately never archived.
  So the pattern is falsified directly instead -- against real files, through
  the engine's own enumerator, with the answers stated up front.

  The legacy arm is here as the BUG rather than as a control: `*_pb.rec` is what
  the pruner globbed before this build, and seeing it return every player's runs
  is what makes the per-player quota a fix rather than a preference.
*/
float(string pat, float want, string what) ui_who_glob1 =
{
	local float h, n;

	h = search_begin(pat, FS_NAMESORT, TRUE);
	n = (h < 0) ? 0 : search_getsize(h);

	if (n != want)
	{
		b66_fail = b66_fail + 1;
		print(sprintf("^1FAIL^7 %-26s %s -> %g, wanted %g\n", what, pat, n, want));
	}
	else
		print(sprintf("^2ok  ^7 %-26s %s -> %g\n", what, pat, n));

	// Printed in the order the pruner would walk them, because "slowest first"
	// is a claim about THIS order and nothing else checks it.
	for (n = 0; n < ((h < 0) ? 0 : search_getsize(h)); n = n + 1)
		print(sprintf("         [%g] %s\n", n, search_getfilename(h, n)));

	if (h >= 0)
		search_end(h);
	return n;
};

/*
  DECLARED HERE, not in defs/m_defs.qc.  The engine registers fremove for the
  menu VM (pr_menu.c: {"fremove", PF_fremove, 652}) and the generated defs file
  simply does not list it -- and those files are the engine's output, so a hand
  edit is lost the next time they are regenerated.  `#0:fremove` resolves it by
  NAME rather than by number, which is how sv_timer.qc and cl_replay.qc already
  spell the same builtin and is what keeps this independent of 652 staying 652.
*/
float(string fname) fremove = #0:fremove;

void(string p) ui_who_touch =
{
	local float fh;

	fh = fopen(p, FILE_WRITE);
	if (fh < 0)
	{
		b66_fail = b66_fail + 1;
		print(sprintf("^1FAIL^7 cannot create probe file %s\n", p));
		return;
	}
	fputs(fh, "FTESURF-REC 4\n");
	fclose(fh);
};

void() ui_who_glob =
{
	local string dir;

	dir = "data/probe/prune/";
	b66_fail = 0;

	// Two players on one leg, plus a pre-build-66 file with no segment at all
	// and one archived file under a DIFFERENT tag.  Both of the last two are
	// traps: the legacy file must still be swept by the legacy pattern, and the
	// shadow must never be swept by the pb one (the per-tag-class quota, which
	// this build must not have broken on its way past).
	ui_who_touch(strcat(dir, "0000100_alpha-11111111_pb.rec"));
	ui_who_touch(strcat(dir, "0000200_alpha-11111111_pb.rec"));
	ui_who_touch(strcat(dir, "0000150_beta-22222222_pb.rec"));
	ui_who_touch(strcat(dir, "0000050_pb.rec"));
	ui_who_touch(strcat(dir, "0000300_alpha-11111111_shadow.rec"));

	ui_who_glob1(strcat(dir, "*_alpha-11111111_pb.rec"), 2, "alpha's pb runs");
	ui_who_glob1(strcat(dir, "*_beta-22222222_pb.rec"),  1, "beta's pb runs");
	ui_who_glob1(strcat(dir, "*_alpha-11111111_shadow.rec"), 1, "alpha's shadows");
	ui_who_glob1(strcat(dir, "*_pb.rec"),                4, "THE OLD PATTERN");

	// Every probe file removed, whether or not the arms passed.  This command
	// can be run in the player's own gamedir and data/ is theirs.
	fremove(strcat(dir, "0000100_alpha-11111111_pb.rec"));
	fremove(strcat(dir, "0000200_alpha-11111111_pb.rec"));
	fremove(strcat(dir, "0000150_beta-22222222_pb.rec"));
	fremove(strcat(dir, "0000050_pb.rec"));
	fremove(strcat(dir, "0000300_alpha-11111111_shadow.rec"));

	print(sprintf("ui_who glob: %s\n",
	              b66_fail ? sprintf("^1%g FAILURES^7", b66_fail) : "^2all arms pass^7"));
};

void(float i) ui_connect =
{
	local string addr;

	/*
	  The same consent gate ui_launch has, and it is here for the reason the
	  comment there gives: that gate is the single launch choke point, and a
	  second entry point that skipped it would quietly reopen what build 22
	  closed.  Joining a lobby is MORE of a disclosure than starting a local
	  map, not less, so this is the last place it should be omitted.

	  FS_TERMS_ONLINE, not FS_TERMS_VERSION -- this is the tier that exists.  A
	  version-1 player reaches the terms screen here and gets a "not now" button
	  there, because they have already agreed to everything the offline game
	  does and declining has to leave them able to keep playing it.
	*/
	if (ms_consent < FS_TERMS_ONLINE)
	{
		menu_screen = SCREEN_TERMS;
		return;
	}

	addr = Lob_Addr(i);
	if (!ui_addr_ok(addr))
	{
		print(sprintf("^1lobby:^7 refusing to connect to a malformed address %S\n", addr));
		return;
	}

	/*
	  AND WHERE it points, not just that it is well formed.  See the essay over
	  ui_host_allowed: without this, whoever answers lobby_dir chooses what host
	  every player's game connects to.  Named in the message, because "refused"
	  with no host is a bug report nobody can act on.
	*/
	if (!ui_host_allowed(addr))
	{
		print(sprintf("^1lobby:^7 refusing to connect to %S -- %S is not in "
		              "lobby_hosts\n", addr, ui_host_of(addr)));
		print(sprintf("^1lobby:^7 the directory at %S offered a host this build "
		              "was not shipped trusting.\n", cvar_string("lobby_dir")));
		return;
	}

	/*
	  Deliberately NOT copying ui_launch's sv_public / deathmatch / maxclients
	  lines.  Those configure a LISTEN server about to be started here; on a
	  connect path they would be changing local server cvars for no reason,
	  and maxclients in particular would be actively wrong.
	*/
	localcmd(sprintf("connect %S\n", addr));

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
float  bc_consent;      // Patch 270: ms_consent parked across the terms screenshot

void() ui_bootcheck_tick =
{
	ui_bootframe++;

	if (ui_bootframe == 30)
		localcmd("screenshot ui_menu_main\n");
	/*
	  PATCH 270, STAGE 2 -- the terms screen, which had never once been looked
	  at.  Everything claimed about it was arithmetic: derived panel height, line
	  count, button rects.  Arithmetic is what said the panel fit, and arithmetic
	  is also what missed that centring a 625 px panel in a shorter window puts
	  the accept button off the bottom of a screen that has no other way out.

	  Driven by setting menu_screen directly rather than by clearing consent,
	  because the alternative is moving the player's own data/consent.txt aside
	  and hoping to put it back.  This costs one frame and touches no files.

	  What it shows depends on the machine it runs on, and BOTH cases are worth
	  seeing: a fresh install draws "I understand -- play offline", an install
	  that already cleared FS_TERMS_VERSION draws "not now -- keep playing
	  offline".  ui_bootterms forces the first without writing anything, by
	  lying about ms_consent for exactly one screenshot and putting it back.
	*/
	else if (ui_bootframe == 33)
	{
		bc_consent = ms_consent;
		if (cvar("ui_bootterms"))
			ms_consent = 0;             // draw it as a fresh install
		menu_screen = SCREEN_TERMS;
	}
	else if (ui_bootframe == 36)
		localcmd("screenshot ui_menu_terms\n");
	else if (ui_bootframe == 38)
	{
		ms_consent  = bc_consent;       // never persisted; the file is untouched
		menu_screen = SCREEN_MAIN;
	}
	else if (ui_bootframe == 40)
	{
		// Through the door the create button uses, so the saved gametype set
		// is read exactly as a player gets it, and the log says what it read.
		menu_screen = SCREEN_CREATE;
		ui_create_open();
		ui_refilter();
		print(sprintf("bootcheck: ui_maps_modes %g -- %g of %g maps listed\n",
		              ms_modes, ms_viewcount, ms_count));
	}
	else if (ui_bootframe == 70)
		localcmd("screenshot ui_menu_create\n");
	else if (ui_bootframe == 75)
	{
		/*
		  The gametype toggles, where the source strip used to be exercised.
		  Build 57.

		  Through ui_modes_click, the function the chips themselves call, so the
		  rule under test is the shipped one and not a copy typed here.  From a
		  known surf + bhop, whatever this install saved: bhop off must leave
		  surf alone, and then surf off must be REFUSED, because it is the last
		  lit chip.  The log line checks both; the screenshot at 105 is the
		  surf-only list.

		  NOT SAVED.  ui_modes_set would `seta` the player's own config, and a
		  self-check that rewrites the setting it checks leaves the next launch
		  testing its own leftovers.  So this assigns ms_modes directly, and
		  frame 180 puts back what the cvar says.
		*/
		ms_modes = ui_modes_click(FS_MODES_DEFAULT, ui_mode_slot(GC_BHOP));
		float bcl = ui_modes_click(ms_modes, ui_mode_slot(GC_SURF));
		print(sprintf("bootcheck: bhop off leaves %g (want %g), the last lit "
		              "chip off leaves %g (want %g) -- %s\n",
		              ms_modes, ui_cat_bit(GC_SURF), bcl, ui_cat_bit(GC_SURF),
		              (ms_modes == ui_cat_bit(GC_SURF) && bcl == ms_modes)
		                  ? "^2ok^7" : "^1FAILED^7"));

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
	{
		print(sprintf("bootcheck: surf only -- %g of %g maps\n",
		              ms_viewcount, ms_count));
		localcmd("screenshot ui_menu_toggle\n");
	}
	else if (ui_bootframe == 110)
		ms_tier = 3;                    // the tier strip, and a non-trivial refilter
	else if (ui_bootframe == 140)
		localcmd("screenshot ui_menu_tier\n");
	else if (ui_bootframe == 145)
	{
		/*
		  Two gametypes at once -- the thing the single-select strip could not
		  say -- and neither of them the default.  Climb and other: both small
		  (13 and 49 maps when measured), so "(N of M)" reads distinctly, and
		  other is GC_OTHER, which exists only as ui_cat_load's last resort; a
		  fallback that matched nothing would show here as climb's count alone.
		  Built from frame 75's surf through the chips' own function: climb on,
		  other on, surf off.  Tier goes back to any, or the two filters would
		  AND down to a handful and prove much less.

		  THIS FRAME WAS BROKEN FOR AS LONG AS IT EXISTED.  It set ms_mode = 12
		  with the comment "kz": 12 is a Momentum gamemode ID, df-vq3 at that,
		  while ms_mode held a CATEGORY and ui_mode_cat never returns 12 -- and
		  the source filter from frame 75 was still on Momentum.  So
		  ui_menu_mode.png has always been a picture of "no matches", "0 of
		  1414", and an empty list cannot tell a broken strip from a correct one.
		*/
		ms_tier  = 0;
		ms_modes = ui_modes_click(ms_modes, ui_mode_slot(GC_CLIMB));
		ms_modes = ui_modes_click(ms_modes, ui_mode_slot(GC_OTHER));
		ms_modes = ui_modes_click(ms_modes, ui_mode_slot(GC_SURF));
	}
	else if (ui_bootframe == 175)
	{
		// Counted here rather than at 145: m_draw runs this driver BEFORE its
		// change check, so on the frame that changes the set the view is stale.
		print(sprintf("bootcheck: climb + other (modes %g) -- %g of %g maps%s\n",
		              ms_modes, ms_viewcount, ms_count,
		              ms_viewcount ? "" : "  ^1EMPTY^7"));
		localcmd("screenshot ui_menu_mode\n");
	}
	/*
	  THE FIVE-LOBBY ROW, REPORTED AS A NUMBER RATHER THAN AS A READING OF A
	  PICTURE.

	  Build 57 raised LB_MAX from 3 to 5, and until the Pi actually ran five
	  lobbies a fourth and fifth cell had never been drawn at all.  Nothing
	  reported the row: no lobby console command is registered anywhere in
	  src/menu or src/client, and this driver said nothing about it either -- so
	  the only evidence was a screenshot, and this session already spent four
	  runs believing screenshots were 720p when every one of them was 1920x1111.

	  Lob_Ready IS PRINTED BESIDE THE COUNT DELIBERATELY.  A count of 0 means
	  either "the directory reports no lobbies" or "the poll has not answered
	  yet", and those are opposite conclusions -- the first is a fault in the
	  fleet, the second is an impatient test.  Only Lob_Ready separates them, and
	  without it a slow WAN fetch reads exactly like five dead servers.

	  The saved gametype set is restored FIRST, so the screenshot shows what a
	  player actually opens the screen to rather than frame 175's climb+other
	  probe.  Frame 178 because 180 either quits or launches a map.
	*/
	else if (ui_bootframe == 177)
	{
		ms_tier  = 0;
		ms_modes = ui_modes_sane(cvar("ui_maps_modes"));

		print(sprintf("bootcheck: lobbies ready %g count %g of LB_MAX %g%s\n",
		              Lob_Ready(), Lob_Count(), LB_MAX,
		              Lob_Ready() ? "" : "  ^3poll unanswered^7"));

		for (float li = 0; li < Lob_Count(); li = li + 1)
			print(sprintf("bootcheck:   lobby %g  %s  %s  %g/%g\n",
			              li + 1, Lob_Addr(li), Lob_Map(li),
			              Lob_Players(li), Lob_Max(li)));
	}
	/*
	  THE CAPTURE IS TWO FRAMES AFTER THE RESTORE, NOT IN THE SAME FRAME.

	  `screenshot` reads the backbuffer, so it lands a frame behind the QC that
	  asked for it, and m_draw runs this driver BEFORE its own change check --
	  the same reason frame 175 counts at 175 rather than at 145.  Asking for the
	  restore and the shot on ONE frame produced a PNG byte-identical to
	  ui_menu_mode.png: same sha256, same 271,074 bytes, still showing
	  climb+other and "62 of 1334".  It was read as proof of the lobby row only
	  because the row does not depend on the gametype filter and so is identical
	  in both frames -- which is luck, not method.  Splitting the two costs one
	  frame and makes the artifact say what it claims to say.
	*/
	else if (ui_bootframe == 179)
		localcmd("screenshot ui_menu_lobbyrow\n");
	else if (ui_bootframe == 180)
	{
		// Back to the SAVED set, which nothing above wrote to.
		ms_tier  = 0;
		ms_modes = ui_modes_sane(cvar("ui_maps_modes"));

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
	local float i, y, ph, foot, btn;

	ui_backdrop(screensize);

	/*
	  The panel is sized FROM the text rather than guessed at: 26 lines at a 15 px
	  pitch is 390 px, and the first cut used a 500 px box, which put the accept
	  button straight through the last three lines of "Turning it off".  A terms
	  screen with its own text obscured by the button that accepts it is not a
	  detail -- it is the one screen where the reader has to be able to read
	  everything before the control that says they did.

	  PATCH 270 MADE THAT COMMENT TRUE.  It described a panel that had been sized
	  from the text ONCE, by hand, and then written down as the constants 580,
	  486 and 516 -- so adding the four lines about public lobbies would have
	  reproduced the exact bug the comment exists to warn about, and reproduced
	  it in the one screen where it matters most.  Derived now, so the next
	  person to add a line gets a taller box instead of a covered sentence:

	      text     starts at +72, FS_TERMS_LINES at a 15 px pitch
	      footer   24 px below the last line
	      button   30 px below the footer
	      panel    34 px below the button

	  At 33 lines (build 57) that is 685 px, leaving a 35 px margin at 720p --
	  the smallest window this is expected to run in, and the case the map
	  picker's own clamp exists for.  Anything much past ~34 lines needs a
	  scroll rather than a bigger box, and the honest fix at that point is
	  shorter terms; there is room for about one more.

	  The three buttons are 24..254, 270..500 and 516..616 inside a 640 px
	  panel, so they do not overlap and the rightmost keeps a 24 px margin.
	*/
	foot = 72 + FS_TERMS_LINES * 15 + 24;
	btn  = foot + 30;
	ph   = btn + 30 + 34;

	p = [floor(screensize_x * 0.5) - 320, floor(screensize_y * 0.5 - ph * 0.5)];

	/*
	  CLAMPED, because deriving the height from the text made this reachable.

	  Centring a 625 px panel in a window shorter than that puts p_y negative,
	  which pushes the BUTTON ROW below the bottom edge.  On this screen that is
	  not a cosmetic clip: there is deliberately no ESC route out of the terms,
	  and m_draw forces the screen back every frame while consent is missing --
	  so a fresh install in a short window has no reachable control at all and
	  the game cannot be started.  Quitting and editing a config is not a way
	  out for the player this screen exists to protect.

	  Two clamps.  The first pins the panel to the top so the text is read from
	  its beginning rather than its middle; the second floats the buttons up
	  from the bottom edge if the panel still overflows.  Text can be clipped --
	  the reader can resize -- but the control that accepts must always be
	  on screen, and must never sit ON the text it is accepting.
	*/
	if (p_y < 0)
		p = [p_x, 0];

	if (p_y + btn + 30 > screensize_y)
	{
		btn = screensize_y - 30 - 8 - p_y;
		if (btn < foot + 8)
			btn = foot + 8;         // never over the last line of the terms
	}

	sui_fill(p, [640, ph], COL_PANEL, 0.94, 0);
	sui_border_box(p, [640, ph], 1, COL_BORDER, 1, 0);

	Font_Set(ui_font_display);
	sui_text([p_x + 24, p_y + 22], SZ_TITLE, "Before you play", COL_ACCENT, 1, 0);
	Font_Set(ui_font_ui);

	y = p_y + 72;
	for (i = 0; i < FS_TERMS_LINES; i = i + 1)
	{
		sui_text([p_x + 24, y], SZ_LABEL, rec_terms_line(i), COL_TEXT, 1, 0);
		y = y + 15;
	}

	sui_text([p_x + 24, p_y + foot], SZ_LABEL,
	         "^9This is a record that you agreed, kept on your own machine. It is not a lock.",
	         COL_DIM, 1, 0);

	/*
	  TWO ACCEPT BUTTONS, ALWAYS BOTH DRAWN, and the left one is the default.

	  There used to be one accept plus a "not now" that appeared only for
	  someone who had already accepted an earlier version.  On a fresh install
	  that condition is false, so a new player had a single button -- and it
	  stamped FS_TERMS_ONLINE, opting them into contacting a server.  The lower
	  tier existed in the file format and in three gates and was unreachable
	  from the only screen that can grant it.

	  Now the tier is the choice, not a side effect of which button happened to
	  be visible.  Left grants the offline game and nothing else; right adds
	  lobbies.  A player who takes the left one keeps playing immediately, with
	  every online path still shut, and can come back through the row
	  Lob_Blocked draws in the map picker whenever they want the other half.

	  For a version-1 player arriving here from a lobby row, the left button is
	  still the "not now" it was: ui_consent_write refuses to downgrade, so it
	  writes nothing new and just closes the screen.  The label says so.
	*/
	if (ui_button("tm_accept", [p_x + 24, p_y + btn], [230, 30],
	              (ms_consent >= FS_TERMS_VERSION) ? "not now -- keep playing offline"
	                                               : "I understand -- play offline"))
		ui_consent_write(FS_TERMS_VERSION);

	if (ui_button("tm_online", [p_x + 270, p_y + btn], [230, 30],
	              "...and turn on public lobbies"))
		ui_consent_write(FS_TERMS_ONLINE);

	if (ui_button("tm_exit", [p_x + 516, p_y + btn], [100, 30], "exit"))
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
		ui_create_open();
		ui_refilter();
	}

	if (ui_option("mm_exit", [p_x, p_y + 42], 400, 34, "exit", COL_TEXT))
		localcmd("quit\n");

	if (clientstate() == 2)
		sui_text([p_x + 12, p_y + 100], SZ_LABEL,
		         sprintf("^9esc  back to %s", serverkey("map")), COL_DIM, 1, 0);
};

/*
  Shorten a string until it fits `w` pixels at `sz`, ending it with ".." so the
  truncation is visible rather than looking like a map whose name really is
  "surf_colin_blaster_6".

  Needed only since the lobby rows went side by side: at full width a name had
  938 px and the longest in the library wants 384, so nothing could overflow and
  nothing measured.  In five columns (build 57) a cell has 139 px of text on a
  1280 desktop and 169 at the 1400 cap -- roughly seventeen and twenty
  characters at 16 px, estimated rather than measured -- so a long lobby name
  or surf_colin_blaster_69000 needs it, and without this either would draw
  straight through the neighbouring lobby's thumbnail.

  Binary search rather than a per-character walk: stringwidth is a builtin call
  per invocation and this runs for a few strings per lobby cell a frame, but the
  loop bound matters more than the constant here -- a while() that shortens by
  one is O(n) calls on exactly the pathological names this exists for.
*/
string(string s, float w, vector sz) ui_fit_text =
{
	if (stringwidth(s, TRUE, sz) <= w)
		return s;

	float lo = 0, hi = strlen(s);
	while (lo < hi)
	{
		float mid = floor((lo + hi + 1) * 0.5);
		if (stringwidth(strcat(substring(s, 0, mid), ".."), TRUE, sz) <= w)
			lo = mid;
		else
			hi = mid - 1;
	}
	return strcat(substring(s, 0, lo), "..");
};

/*
  The narrowest a lobby cell may be before the grid wraps.  Build 57.

  A cell spends 90 px on its thumbnail and gutter and 8 on a right margin, so
  200 leaves 102 px of text at 16 px -- enough for a short lobby name whole and
  a map name for ui_fit_text to shorten.  Five columns clear it from a 1064 px
  panel (a screen about 1100 wide) up; at 1280 they are 236 px.  The 300 it
  replaces would have put a 1280 screen's five lobbies in one column.
*/
#define LOB_MIN_COL 200

void(vector screensize) screen_create =
{
	ui_backdrop(screensize);
	ui_map_backdrop(screensize);

	/*
	  THE PANEL.  760 tall and up to 1400 wide, clamped to the screen.

	  HEIGHT.  Sized so the list fits INSIDE the panel with the start/back row
	  still below it -- an overlay list that spilled past the border covered those
	  buttons entirely, which is how the first version shipped -- and 760 rather
	  than 600 because rows went from 22 px to ROW_H, and a list that shows four
	  maps is not a list.

	  WIDTH, BUILD 57: SET BY FIVE LOBBY CELLS.  It was set in turn by the source
	  row (four buttons, 680 px), by the map row's name column (980), and by the
	  gametype strip fitting beside the tier strip at 1280 wide (1060).  Five
	  lobbies in one row set it now.  A cell spends 98 px on its thumbnail, gutter
	  and right margin before any text, so five across a 1060 panel would leave a
	  lobby's name 107 px, about a dozen characters.  At 1400 a cell has 169 px of
	  text; on a 1280 desktop the clamp makes the panel 1248 and a cell 139.
	  Wider than 1400 buys nothing -- the map rows already have more room than any
	  name wants -- and a panel that fills a 2560 screen puts the start button a
	  long way from the list it acts on.

	  The tier and gametype strips still share a row at 1248: about 925 px of the
	  1216 inside it, from the 865 measured before build 57 plus ~59 for "other".
	  Below that the gametype strip drops to its own line by itself, and at 720p
	  that costs a map row -- see the header budget at `y` below.

	  CLAMPED both ways: at vid_conautoscale 1 one unit is one pixel, so a panel
	  bigger than the framebuffer hangs its title off the top and its start/back
	  row off the bottom, and sui_push_frame does not clip, so nothing says so.
	  32 px of margin also leaves the map backdrop something to show through.
	*/
	vector size = [min(screensize_x - 32, 1400), 760];
	if (size_y > screensize_y - 32) size_y = screensize_y - 32;

	vector pos  = [floor((screensize_x - size_x) * 0.5),
	               floor((screensize_y - size_y) * 0.5)];

	float inner = size_x - 32;      // content width inside the 16px margins

	sui_fill(pos, size, COL_PANEL, 1, 0);
	sui_border_box(pos, size, 1, COL_BORDER, 1, 0);
	sui_text([pos_x + 16, pos_y + 12], SZ_HEAD, "create server", COL_ACCENT, 1, 0);

	sui_push_frame(pos, size);

	/*
	  THE HEADER BUDGET, and 720p has none to spare.

	  The list below takes whatever height is left, in whole ROW_H steps: it
	  shows floor((size_y - 60 - y) / 48) rows, y being where it starts.  With the
	  filter row (56), the search (56) and one row of lobby cells (76), y is 244:
	  9 rows in a 760 panel, and EXACTLY 8 in 720p's 688 -- 384 px, none left
	  over.  So one more pixel of header costs a 720p player a whole map row.
	  The server name field (60) and the source strip (56) went in build 57, and
	  they are the two rows the list got back.
	*/
	float y = 56;
	float fx, f;

	/*
	  ---- tier and gametype filters -------------------------------------

	  Two strips on one row: tier on the left, gametype to its right, both
	  ANDed into ui_refilter along with the search text.  Twenty-one action
	  elements against sui's MAX_ACTION_ELEMENTS 256 (sui_sys.qc:206); the
	  create screen is nowhere near it.

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

	/*
	  TOGGLES, build 57.  A chip is lit when its bit is in ms_modes, and "all"
	  only when every bit is.  The click goes through ui_modes_click, which holds
	  the rules (all sets everything; the last lit chip stays on), and a click
	  that changed the set is saved at once, the way the HUD editor saves a drag.
	  sui_is_released is true for one frame -- sui_end clears it -- which is
	  what makes a toggle safe here where the old strip only ever assigned.
	*/
	sui_text([mx, mrow], SZ_LABEL, "gametype", COL_DIM, 1, 0);
	for (f = 0; f < FS_NMODES; f++)
	{
		string mlbl = ui_mode_label(f);
		string mcid = strcat("cs_mode", ftos(f));
		float  mlit;

		if (f == 0)
			mlit = (ms_modes == FS_MODES_ALL);
		else
			mlit = (ms_modes & ui_cat_bit(ui_mode_id(f))) != 0;

		mx += ui_chip([mx, mrow + 20], mcid, mlbl, mlit) + CHIP_GAP;

		if (sui_is_released(mcid))
		{
			float mnew = ui_modes_click(ms_modes, f);
			if (mnew != ms_modes)
				ui_modes_set(mnew);
		}
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

	/*
	  ---- public lobbies (Patch 270) -------------------------------------

	  A FIXED section above the list, not rows inside it, and that is a
	  correctness decision rather than a layout preference.  The list's row ids
	  are keyed to the view index (`cs_row<idx>`) and every row does
	  `real = stof(bufstr_get(ms_view, idx))` -- so it assumes every index in
	  the window is a map index.  Prepending pseudo-rows would mean offsetting
	  that everywhere, and sui_list_view_begin's visible-window arithmetic
	  assumes a uniform item height as well.  Mixing row kinds in there is
	  where this would get fragile.

	  Costs the list nothing to give back, because the list geometry two blocks
	  down is DERIVED from y (`by = size_y - 46; ls = [inner, by - y - 12]`) --
	  it shrinks by itself and needs no matching edit.

	  The whole section disappears when there are no lobbies and none are
	  blocked, which is what a player who has cleared lobby_dir gets: exactly
	  the screen they saw before.  Since lobby_dir now ships with a default,
	  that is a deliberate opt-out rather than the out-of-the-box state.
	*/
	if (Lob_Blocked())
	{
		/*
		  The online terms have not been accepted, so the
		  directory is deliberately not being polled.  Say so, and make the row
		  the way to fix it -- see Lob_Blocked for why silence here would be the
		  worse failure.
		*/
		sui_text([16, y], SZ_LABEL, "public lobbies", COL_DIM, 1, 0);
		y += 20;

		vector cp = [16, y], crs = [inner, ROW_H];
		sui_action_element(cp, crs, "cs_lobterms", sui_noop);
		if (sui_is_hovered("cs_lobterms"))
			sui_fill(cp, crs, COL_ROW_HOVER, 1, 0);
		ui_thumb([cp_x + 3, cp_y + 2], [78, 44], -1, -1);
		sui_text([cp_x + 90, cp_y + 5], SZ_ROW,
		         "public lobbies are off", COL_TEXT, 1, 0);
		sui_text([cp_x + 90, cp_y + 26], SZ_ROW,
		         "^9they send data to a server -- click to read what, and choose",
		         COL_DIM, 1, 0);
		if (sui_is_released("cs_lobterms"))
			menu_screen = SCREEN_TERMS;

		y += ROW_H + 8;
	}
	else if (Lob_Count() > 0)
	{
		sui_text([16, y], SZ_LABEL, "public lobbies", COL_DIM, 1, 0);
		y += 20;

		/*
		  SIDE BY SIDE (Patch 287), FIVE ACROSS (build 57).  Lex: "can you put
		  the server lobbies side by side in the create server menu for more space
		  saving?", and later five lobbies, in one row.

		  Five lobbies stacked would cost 5*ROW_H = 240 px of a 760 px panel to
		  say five short things.  Across, they cost 48 -- and every pixel saved
		  goes straight to the map list underneath, because the list geometry
		  below is DERIVED from y (`by = size_y - 46; ls = [inner, by - y - 12]`).
		  So this needs no matching edit down there.

		  The column count is Lob_Count() rather than a constant: with two lobbies
		  live they take half the width each and there are no empty slots.
		  LB_MAX is 5 (m_lobby.qc), so this is bounded, and the row/column
		  arithmetic below is written to survive that changing.

		  CELLS STAY PUT.  Lob_Parse orders lobbies by port rather than by the
		  directory's busiest-first, so a lobby keeps its cell as people join and
		  leave, and a click cannot land on a neighbour that slid into place
		  between two polls.

		  NARROW SCREENS GET FEWER COLUMNS, NOT ONE.  inner comes from the panel
		  and the panel is clamped to the screen, so a small desktop narrows every
		  cell; below LOB_MIN_COL the grid takes as many columns as still clear it
		  and wraps the rest onto another row.  Each extra grid row costs the list
		  a row, which a small screen trades for names it can read.  This used to
		  drop straight to one column below 300 px, which with five lobbies would
		  spend 5*ROW_H at exactly the sizes least able to afford it.
		*/
		float lgap  = 8;
		float lcols = Lob_Count();
		float lcolw = (inner - lgap * (lcols - 1)) / lcols;
		if (lcolw < LOB_MIN_COL)
		{
			// Fewer than Lob_Count() by construction: the test above just failed.
			lcols = floor((inner + lgap) / (LOB_MIN_COL + lgap));
			if (lcols < 1)
				lcols = 1;
			lcolw = (inner - lgap * (lcols - 1)) / lcols;
		}

		for (float li = 0; li < Lob_Count(); li = li + 1)
		{
			// Column and row within the grid.  QC has no integer modulo, hence
			// the subtraction; with lcols == 1 this degenerates to the old
			// one-per-line layout exactly, which is what the fallback relies on.
			float lgr  = floor(li / lcols);
			float lgc  = li - lgr * lcols;

			vector lp  = [16 + lgc * (lcolw + lgap), y + lgr * (ROW_H + lgap)];
			vector lrs = [lcolw, ROW_H];
			string lid = strcat("cs_lob", ftos(li));

			/*
			  Resolve this lobby's map against the installed list ONCE and cache
			  it back.  -2 is "not looked up yet", -1 is "looked up, not
			  installed" -- a real answer that gets drawn, and re-deriving it
			  every frame would mean scanning 2200 names three times a frame.
			*/
			float lrow = Lob_Row(li);
			if (lrow == -2)
			{
				lrow = ui_map_index(Lob_Map(li));
				Lob_SetRow(li, lrow);
			}

			float lpage = -1, lcell = -1;
			if (lrow >= 0)
				if (tokenize(bufstr_get(ms_meta, lrow)) > MT_UUID)
				{
					lpage = (argv(MT_PAGE) == "-") ? -1 : stof(argv(MT_PAGE));
					lcell = (argv(MT_CELL) == "-") ? -1 : stof(argv(MT_CELL));
				}

			sui_action_element(lp, lrs, lid, sui_noop);
			if (sui_is_hovered(lid))
				sui_fill(lp, lrs, COL_ROW_HOVER, 1, 0);

			ui_thumb([lp_x + 3, lp_y + 2], [78, 44], lpage, lcell);

			// The text column is what is left of the cell after the thumbnail and
			// its gutter, less 8 px so a truncated name cannot touch the next
			// cell's border: 139 px at 1280 wide, 169 at the 1400 cap.
			float ltw = lcolw - 90 - 8;

			/*
			  Line 1: WHICH lobby -- its name with "FTESurf -- " stripped
			  (Lob_Title).  It was the map, and two lobbies on one map were two
			  identical cells.

			  An uninstalled map is shown, dimmed, rather than hidden.  Hiding it
			  makes a lobby with people in it silently absent and looks like the
			  directory is broken; saying "not installed" is the honest answer and
			  tells the player what to do about it.  It is said where the picture
			  would be, so the map's name keeps its place on line 2 -- which is
			  the name the player has to go and find.
			*/
			sui_text([lp_x + 90, lp_y + 5], SZ_ROW,
			         ui_fit_text(Lob_Title(li), ltw, SZ_ROW),
			         (lrow >= 0) ? COL_TEXT : COL_DIM, 1, 0);

			if (lrow < 0)
			{
				sui_text([lp_x + 8, lp_y + 5], SZ_ROW,
				         ui_fit_text("^1not", 70, SZ_ROW), COL_DIM, 1, 0);
				sui_text([lp_x + 8, lp_y + 24], SZ_ROW,
				         ui_fit_text("^1installed", 70, SZ_ROW), COL_DIM, 1, 0);
			}

			/*
			  Line 2: the map, and "n / 32".  The count is RIGHT-ALIGNED and
			  fitted first, and the map gets what is left.  ui_fit_text cuts from
			  the end, so one "map  n / 32" string would lose the count -- the half
			  of the line a player choosing between five lobbies reads -- to any
			  long map name.
			*/
			string lcnt = ui_fit_text(sprintf("^2%g^9 / %g", Lob_Players(li), Lob_Max(li)),
			                          ltw, SZ_ROW);
			float  lcw  = stringwidth(lcnt, TRUE, SZ_ROW);

			sui_text([lp_x + 90 + ltw - lcw, lp_y + 26], SZ_ROW, lcnt, COL_DIM, 1, 0);
			sui_text([lp_x + 90, lp_y + 26], SZ_ROW,
			         ui_fit_text(Lob_Map(li), ltw - lcw - 8, SZ_ROW), COL_DIM, 1, 0);

			if (lrow >= 0)
				if (sui_is_released(lid))
					ui_connect(li);
		}

		// Advanced once for the whole grid rather than once per lobby -- the loop
		// above places each cell absolutely from its own row/column, so y must not
		// move underneath it.
		float lrows = ceil(Lob_Count() / lcols);
		y += lrows * ROW_H + (lrows - 1) * lgap + 8;
	}

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
				local string mtier, mpb, mtsrc, mtime;

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

				/*
				  The time, right-aligned against the row's own right edge.
				  sui_text measures and offsets, so the anchor is the text end.

				  A LOBBY time says so in a word and not a colour alone -- the
				  rule the tier chip above follows, for the same readers.  It is
				  the one shown only when it beats this PC's own time; see
				  run_pb_load.

				  THE MAP'S OWN TICK, not PM_TICK: a bhop map's ticks were
				  counted at 100 Hz, and 0.015 draws them half again as long.
				  See ui_map_tick, which is why this is a call and not a
				  constant.

				  BUILT BEFORE IT IS DRAWN, since build 66, because the headcount
				  below sits immediately to its left and the sub line has to be
				  fitted around both.  The placeholder is a string on the same
				  footing as a real time rather than a second draw call, so its
				  width is available to the same arithmetic -- a row with no time
				  reserves exactly as much room as one with a time, which is what
				  stops the headcount jumping sideways as you scroll.
				*/
				local float mtw, mpop, mpopw;
				local string mpopt;

				mpb = bufstr_get(ms_pbv, real);
				if (mpb != "")
				{
					mtime = Time_TickString(stof(mpb), ui_map_tick(real));
					if (bufstr_get(ms_pblob, real) != "")
						mtime = strcat("^9lobby  ^7", mtime);
				}
				else
					mtime = "--:--.---";
				mtw = stringwidth(mtime, TRUE, SZ_ROW);

				/*
				  The live headcount, from the lobby directory this screen is
				  already polling.

				  NOTHING IS DRAWN WHEN NOBODY HAS SAID ANYTHING ABOUT THIS MAP,
				  and that is the whole of the honesty here -- see the essay over
				  ui_map_players for why -1 and 0 are different facts.  On a
				  library of 2200 maps and five lobbies this is silent on all but
				  a handful of rows, which is correct and is also why it costs
				  nothing to read.

				  The colour carries the difference between "people are here" and
				  "a server is here and it is empty" while the WORDS stay the
				  same, so the eye parses one shape down the list and the number
				  is the thing that changes.  Same reasoning as the tier chip's
				  "T9?" -- except here the two states are a measured count and
				  another measured count, so a punctuation mark would be
				  inventing a distinction the data does not have.

				  IT IS LEFT OF THE TIME, ON THE TIME'S OWN LINE, not right-
				  aligned on the sub line.  The sub line sits at +26 and the time
				  at +14; at SZ_ROW those two bands overlap, so a second
				  right-aligned item on the lower line would draw through the
				  time on exactly the rows that have both.
				*/
				mpop  = ui_map_players(real);
				mpopt = "";
				mpopw = 0;
				if (mpop >= 0)
				{
					mpopt = sprintf("%s%g^9 playing", (mpop > 0) ? "^2" : "^9",
					                mpop);
					mpopw = stringwidth(mpopt, TRUE, SZ_ROW) + 16;
					sui_text([rp_x + rs_x - 8 - mtw - mpopw,
					          rp_y + 14], SZ_ROW, mpopt, COL_DIM, 1, 0);
				}

				/*
				  Second line, fitted into what the right-hand column actually
				  leaves -- which it was not before build 66.  `sub` was drawn
				  unbounded, so a long "COUNTER-STRIKE | surf | 12 stages, 3
				  bonus" already ran under the time on a narrow window; adding a
				  headcount would have made that the common case rather than the
				  rare one.  ui_fit_text cuts from the end, so the source word --
				  the half that answers "why is this map here at all" -- is the
				  half that survives.
				*/
				sui_text([rp_x + 126, rp_y + 26], SZ_ROW,
				         ui_fit_text(sub, rs_x - 134 - mtw - mpopw, SZ_ROW),
				         COL_DIM, 1, 0);

				if (mpb != "")
					sui_text([rp_x + rs_x - 8 - mtw, rp_y + 14], SZ_ROW,
					         mtime, COL_TEXT, 1, 0);
				else
					sui_text([rp_x + rs_x - 8 - mtw, rp_y + 14], SZ_ROW,
					         mtime, COL_DIM, 0.5, 0);

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

	// Patch 270.  Creates the public-lobby buffers and registers lobby_dir,
	// which SHIPS WITH A DIRECTORY URL -- the empty default was removed once it
	// became clear it was a step to be told about rather than a decision anyone
	// made.  Nothing is polled before an FS_TERMS_ONLINE acceptance either way;
	// see the consent essay at the top of m_lobby.qc.
	Lob_Init();

	ms_name = ms_src = ms_lst = -1;
	ms_tierv = ms_modev = ms_meta = ms_pbv = -1;
	ms_catv = ms_pblob = -1;
	ms_selected = -1;
	ms_tier = ms_applied_tier = 0;
	// The SAVED set is read when the create screen opens, beside its
	// registercvar (ui_create_open); this only keeps the set from being empty
	// before then.
	ms_modes = ms_applied_modes = FS_MODES_DEFAULT;
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

	// Patch 270: 1 makes the terms screenshot draw as a FRESH INSTALL, by
	// zeroing ms_consent for that one frame and restoring it after.  Nothing is
	// written -- data/consent.txt is not touched -- so the two variants of the
	// screen can both be photographed on a machine that has already consented.
	// Safe to register here despite the read-before-register trap: its default
	// is "0" and an auto-created "" reads as 0 as well, so the two agree.
	registercvar("ui_bootterms", "0", 0);

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
	if (ms_query != ms_applied_query || ms_tier != ms_applied_tier
	    || ms_modes != ms_applied_modes)
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
	{
		/*
		  Patch 270.  Polled only while the picker is actually on screen, so
		  sitting in the main menu or in a game makes no request at all -- and
		  without an FS_TERMS_ONLINE acceptance Lob_Poll returns before touching
		  the network.  It is BEFORE screen_create rather than inside it so the
		  poll does not depend on where in the layout the rows ended up.
		*/
		Lob_Poll();
		screen_create(screensize);
	}
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
	// has to do is make sure there is something in it -- and, since build 57,
	// that the time column and the gametype set are current.  This is the door
	// ESC out of a game uses, and it lands straight on the create screen.
	if (menu_screen == SCREEN_CREATE)
		ui_create_open();
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

	if (argv(0) == "ui_lobbypop")
	{
		ui_lobbypop_print();
		return TRUE;
	}

	// ui_fstream <stream|buffered> [hold-seconds] -- engine Patch 316.
	if (argv(0) == "ui_fstream")
	{
		ui_fstream_test(argv(1), argv(2));
		return TRUE;
	}

	// ui_who [glob] -- the build 66 run-filename grammar, self-checking.
	if (argv(0) == "ui_who")
	{
		if (argv(1) == "glob")
			ui_who_glob();
		else
			ui_who_print();
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
