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
// Each is the shared theme's token (sh_ui.qc), so every screen in this VM follows it.
#define COL_TEXT        SUI_THEME_TEXT
#define COL_DIM         SUI_THEME_DIM
#define COL_ACCENT      SUI_THEME_ACCENT
#define COL_PANEL       SUI_THEME_PANEL
#define COL_ROW         SUI_THEME_CHIP
#define COL_ROW_HOVER   SUI_THEME_HOVER
#define COL_ROW_SEL     SUI_THEME_SELECTED
#define COL_BORDER      SUI_THEME_EDGE_HI
// The action column's Play button.  Green because it is the one control on
// this screen that starts something, and the only one that is safe on every
// row it appears on -- COL_ACCENT is already the tier chip and the panel edge.
#define COL_PLAY        SUI_THEME_GOOD
#define COL_PLAY_HOT    SUI_THEME_GOOD_BG

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
/*
  The gap between the right-aligned times and whatever is to their right -- the
  download gutter, or the row's edge where there is none.

  It was a bare 8 at four call sites.  20 because 8 put the times hard against
  the gutter's border and they read as part of the button ("move the times over
  to the left slightly"), and because the two numbers now stacked there are the
  row's answer to "should I play this" and deserve to be their own column.
*/
#define ROW_RPAD        20
// Horizontal padding inside the download button, each side.  Up here with the
// other layout constants because ui_browse_print reports the gutter and is
// defined long before the download block.
#define DL_PAD          6

// Explicit -ReleaseVersion builds retain automatic release installation.
#ifndef UI_MENU_DEVELOPMENT
#define UI_MENU_DEVELOPMENT 1
#endif

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
  The name gate.  Patch 340.

  Forced by ui_launch -- the single launch choke point -- whenever the engine's
  `name` cvar still holds a factory default ("Player", the collision-renamed
  "(1)Player", "unnamed", empty).  A default name on a public lobby is twelve
  "Player"s on one scoreboard and chat that cannot be attributed, and the
  engine's own default is literally "Player" (cl_main.c:174).  Not a consent
  screen: it has a real cancel, and it is skipped for ui_bootcheck, which is
  the developer surface and would otherwise deadlock headless runs.
*/
#define SCREEN_NAME     3

// Patch 467: the milk visualizer's screens and the 3D space behind the menu.
// m_milk.qc compiles AFTER this file (it uses the ui_* widgets defined here),
// so everything this file calls into it is prototyped here.
#define SCREEN_VISUALS  4
#define SCREEN_MUSIC    5
// Patch 647: the Steam sign-in, offered once, straight after the terms are
// taken with public lobbies on.  It has a "not now": an offer, not a gate.
#define SCREEN_STEAM    6
// 7 was the Updates screen until P823; the number is not reused.
#define SCREEN_JOURNAL  8
// Patch 854: Story and Event mode, in m_story.qc (compiled last).
#define SCREEN_STORY    9
#define SCREEN_CHAT    10
#define SCREEN_SETTINGS 11
#define SCREEN_STATS   12       // P1084: hud_player's Stats page (m_stats.qc)
void() MC_Init;
void() MC_Open;
void() MC_Send;
void() MC_Probe;
void(float visible) MC_Poll;
void(vector screensize) MC_Draw;
void() Sty_Open;
void() Sty_Esc;
void() Sty_Prefetch;
void(vector screensize) screen_story;
void(string what, string arg) Sty_Command;
void() MU_Init;
void() MU_Poll;
void() MU_Probe;
void(float on) MU_Consent;
float(vector pos, float w) MU_StatusAt;
void(vector pos, vector size) MU_NotesAt;
void(vector screensize) MU_Hint;
void(string what) MU_NotesCommand;
float() MF_Count;
float() MF_Fresh;
float() MF_Direct;
string() MF_ProbeNote;
void() MF_Init;
void(float visible) MF_Poll;
void() MF_ResumeJoin;
void(vector pos, vector size) MF_Draw;
void() MF_Open;
void() MFP_Close;
void(string mark, float boot) MC_SelfMark;
float() MFP_IsOpen;
void(string who, string name) MFP_Open;
void(vector pos, vector size) MFP_Draw;
float(float reqid, float code, string body) MFP_Reply;
void() MFP_Probe;
void() MM_Init;
float() MM_Active;
void(vector screensize) MM_Frame;
void(vector screensize) MM_Backdrop;
void(vector screensize) MM_DrawFps;
void(vector screensize) MM_ScreenMain;
void(vector screensize) MM_ScreenVisuals;
void(vector screensize) MM_ScreenMusic;
void() MM_Open;
void() MM_Close;
void() MM_BootTick;
void() MM_Invalidate;
vector(vector m) MM_MouseToUI;

// ROADMAP 9: the selected map's leaderboard panel over SCREEN_CREATE, in
// m_board.qc (compiled after this file, like m_milk.qc).
float() Mlb_IsOpen;
void(string mapname, float t) Mlb_Open;
void(string why) Mlb_Close;
void(vector screensize) Mlb_Draw;
void() Mlb_TestCommand;
void() Mlb_Command;
void() Mlb_Poll;
void() MCard_Begin;
void() MCard_End;
float mcd_ver;                  // m_mapcards.qc bumps it when the completed list changes
void() MCard_DoneWant;
void() MCard_DoneRefresh;
float(string name) MCard_Done;
float cltime;                   // P1084: client/cl_profile.qc's clock, set in m_draw
void() MStats_Open;
void() MStats_Close;
void(vector size) MStats_Draw;
void() MStats_Probe;
string() MCard_DoneNote;
void(vector pos, float width, float compact, string name, string id) MCard_Draw;
void() MCard_Probe;
void(string what) MM_BcPanel;

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
float() ui_browser_screen =
{
	return (menu_screen == SCREEN_MAIN || menu_screen == SCREEN_CREATE || menu_screen == SCREEN_STORY
	        || menu_screen == SCREEN_STATS);
};
float ui_bootframe;             // ui_bootcheck 2 frame counter
vector ui_cs_size;              // create-screen layout, mirrored for the bootcheck
float  ui_cs_lcols, ui_cs_lshow, ui_cs_rows;
float ui_cs_rowheight, ui_cs_list_top, ui_cs_list_bottom;

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
/*
  ms_have / ms_new / ms_dlkb -- build 58, and the reason the list can now hold a
  map that is not on this disk.

  Every other buffer here came from search_begin, so until now "listed" and
  "installed" were the same statement and ms_have would have been a column of
  ones.  ui_dl_load appends the maps data/mapdl.txt offers and this install does
  not have, with ms_have "0"; they draw a Download button instead of a time.

  ms_dlkb is the size in KiB from the same file rather than from the disk,
  because for those rows there is no file to ask.  It is what the button prints
  before the download starts, and the only honest figure available at that point
  -- the engine reports DLLF_SIZEUNKNOWN until the server answers.
*/
strbuf ms_have;
strbuf ms_new;
strbuf ms_dlkb;
strbuf ms_view;
float  ms_count;                // entries in ms_name
float  ms_viewcount;            // entries in ms_view
float  ms_dlcount;              // rows appended by ui_dl_load, for the report
float  ms_dlstale;              // installed rows whose BUILD differs from the Pi's (ms_have "2")
float  ms_nsrc[SRC_COUNT];      // entries per SRC_*, for the load report

string ms_query;                // live contents of the search field
float  ms_query_cursor;
string ms_applied_query;        // what ms_view was last built for

/*
  A map has been launched since the query was last touched, so the next click
  into the search field selects it (Build 19 emptied it; P974 keeps it so a
  double-click still selects all, and typing replaces it).

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

    ms_tierv   the legacy primary tier, including the collapsed download fallback,
               for quality and sort order. Independent ms_momtier/ms_ksftier
               buffers answer the filter without tokenizing every row.
               0 means untiered -- there is no tier 0.
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
// Independently sourced display/filter values; ms_tierv retains legacy quality/sort.
strbuf ms_momtier;
strbuf ms_ksftier;
strbuf ms_momtsrc; // Provenance of the selected MOM value, not a skipped suggestion.
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
/*
  The best MAIN-track time anyone is known to have set, in MILLISECONDS, or ""
  where nothing knows one.  Build 89, from data/mapwr.txt (tools/mapwr.py).

  MILLISECONDS AND NOT TICKS, which is the one thing about this column that is
  not arbitrary.  Every other time here is a tick count converted with the map's
  own rate, but these rows come from three archives with three different rates
  -- 66.6667, 100 and 125 all appear in surfd's `runs` -- so a tick count is not
  comparable between them and ms is the only field that is.

  586 of the 736 are Momentum's imported leaderboard and 150 are KSF's, so on
  most rows this is a real world record rather than anything set on this fleet.
  The provenance is in the file and in the load report, not on the row: "best"
  is true of all four sources, and a per-row badge would cost the width the
  times were just given.
*/
strbuf ms_wr;
float  ms_wrcount;
/*
  The tier data/mapdl.txt carries, as a string, "0" where it carries none.

  A SECOND TIER SOURCE, because mapmeta.txt is not the only one and reading only
  it left 462 maps drawn as untiered that we have a tier for.  mapmeta comes
  from Momentum's cache; maproster.py falls back to KSF's roster where Momentum
  has no record (`mtier if mtier != "-" else ktier`, maproster.py:413) and
  mapdl.txt inherits that.  So the 462 KSF-only maps have a real, sourced tier
  that the browser was throwing away -- measured 2026-09-28, against 128 that
  genuinely have none.

  Kept in its own buffer rather than written straight into ms_tierv because
  ui_dl_load runs BEFORE ui_meta_load (it appends rows, which ui_meta_load sizes
  itself from) and ui_meta_load rebuilds ms_tierv from scratch.  This survives
  that, and ui_meta_load consults it only where Momentum said nothing.
*/
strbuf ms_dltier;
/*
  Patch 652: two builds of one map on ONE row.  The list names a second build
  in a tenth column (`of`), and ui_dl_load folds it into the row of the map it
  is a build of.  ms_var, on the PLAIN row: the row index of its CS:S build.
  ms_varof, on that build's row: the plain row (ui_refilter then leaves the
  row out).  ms_pick, on the plain row: "1" where the player chose the CS:S
  build, kept in data/mapbuild.txt.  All "" where they do not apply.
*/
strbuf ms_var, ms_varof, ms_pick;
strbuf ms_enabled, ms_zoned;     // per BUILD; network state overrides local file probes
#define MAP_NOZONE_ESC "^xf66"
float  ms_nvar;                 // rows that carry a second build
float  ms_bswrow, ms_bswidx;    // the row whose switch was drawn last, and its
                                // place in the view: `ui_build` names the control
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

/*
  Which library the list is showing.  Build 89, asked for as "an option to
  switch between Momentum maps and CSS maps for map and download".

  0 = both, otherwise the single SRC_BIT_MOM or SRC_BIT_CSS wanted.  ONE value
  and not a set, unlike ms_modes: the question here is "which of the two am I
  browsing", and the answer "neither" is a list with nothing in it.

  IT READS ms_lst, NOT ms_src -- see ms_lst's own essay.  ms_src is where the
  file is and would file de_dust2 under Counter-Strike; ms_lst is which of the
  lists the map belongs to, and a movement map belongs to its source's.

  "and download" is the same switch and not a second one, because the rows a
  download is offered on live in this same list -- ui_dl_load appends them.  It
  is what makes them answer this filter at all, and fixing ms_lst for those rows
  was the work; see there.
*/
float  ms_srcf;
float  ms_applied_srcf;

/*
  ROADMAP 10: how complete each map's data is, one DQ_* per row (ui_data_load),
  which ui_refilter orders by before the tier.  A BARE map is hidden from an
  empty search unless the "show all" chip is lit (saved as ui_maps_showall).
*/
#define DQ_FULL     0           // a picture, a tier, and playable or downloadable
#define DQ_PICTURE  1           // a picture, short of a tier or a way to play it
#define DQ_TIER     2           // a tier and no picture
#define DQ_BARE     3           // neither
#define DQ_CLASSES  4
strbuf ms_dataq;
float  ms_showall;
float  ms_applied_showall;
// P1080: 0 tier order, 1 incomplete first, 2 completed first (ui_maps_compsort).
float  ms_compsort, ms_applied_compsort, ms_applied_donever;
float  ms_nhidden;              // BARE rows the last ui_refilter hid

// The background pic currently held open, so it can be freed when the selection
// moves.  "" when nothing is loaded.  See ui_backdrop.
string ms_bgpic;
// Optional menu-only engine capability: zero dimensions while decoding/HTTP is pending.
vector(string pic) drawgetimagesize_async = #0;
float ms_bgremote;
float  ms_bgfor;                // ms_selected the background was loaded for
// ms_bgblind went with the blind fallback it latched: there is nothing left to
// warn about once "no readable image" is an ordinary answer with a backdrop of
// its own rather than a guess that might be a build difference.
// The selected row's atlas cell, read when the selection moves rather than on
// every frame, for the blurred fallback in ui_bgatlas.  -1 = this map has no
// thumbnail either, and then the screen gets the flat backdrop and nothing else.
float  ms_bgpage, ms_bgcell;

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
		sui_roundbox(pos, size, 8, COL_ROW_HOVER, 0.8);

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
// `primary` marks the one button that moves you forward.
float(string id, vector pos, vector size, string label, float primary = FALSE) ui_button =
{
	float w = stringwidth(label, TRUE, SZ_LABEL) + 16;
	if (w < size_x)
		w = size_x;
	size_x = w;

	sui_action_element(pos, size, id, sui_noop);

	float hot = sui_is_hovered(id);
	if (primary)
		sui_style_box(pos, size, 7, hot ? SUI_THEME_GOOD : SUI_THEME_GOOD_BG, SUI_THEME_GOOD, 1);
	else
		sui_style_box(pos, size, 7,
		              sui_is_held(id) ? SUI_THEME_PRESSED : (hot ? COL_ROW_HOVER : COL_ROW),
		              hot ? COL_ACCENT : SUI_THEME_EDGE, 1);
	sui_text([pos_x + 10, pos_y + (size_y - SZ_LABEL_H) * 0.5], SZ_LABEL, label,
	         primary ? (hot ? SUI_THEME_WELL : SUI_THEME_GOOD) : (hot ? COL_ACCENT : COL_TEXT),
	         1, 0);

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
  Vertical pitch when a filter strip WRAPS to its own line.

  It was 46, which is exactly the height a strip occupies -- a 20 px gap to
  its heading plus a CHIP_H of 26 -- so the next heading started on the pixel
  the chips above it ended.  Invisible until build 89 added a third strip and
  made a wrap the normal case rather than the narrow-window one; "library" sat
  on the tier chips.  52 gives the 6 px CHIP_GAP already puts between chips
  horizontally.
*/
#define STRIP_PITCH 52

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
/*
  Patch 647: the text is two columns now (ui_terms_col, over screen_terms).
  The essay below is about the 35 lines it was, and numbers them so; its rule
  is the new text's rule.
*/
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

  Automatic updates now have their own explicit permission, shared with the
  launcher. No update request occurs before that choice. They check proto.bar
  and download from dl.proto.bar; the screen names both hosts and says what is
  sent. FS_TERMS_ONLINE takes 5 with this new optional endpoint disclosure.

  33 SINCE BUILD 57, and this line is that rule kept rather than broken: it
  arrived in the same change as the code that makes it true.  Line 17 says a
  lobby time is saved in this game's data folder on this PC, because build 57's
  client writes one into data/runs on the player's own disk when a run on a
  lobby beats their lobby best (Stage T, client/cl_lobbytime.qc).  Nothing new
  LEAVES the machine -- the lobby server already timed the run and sent the
  time to this client to print, and keeping it is local -- so FS_TERMS_ONLINE
  is not bumped.

  35 SINCE BUILD 77, AND THIS ONE IS THE RULE ABOVE BEING BROKEN IN THE OTHER
  DIRECTION -- which is the direction that matters, because the text promised the
  reader LESS than the code does.

  Lines 14-16 said "The server times your run and shows you the time.  It is not
  uploaded or ranked anywhere."  That was true when it was written, and Patch
  285's essay above is the record of it being NARROWED to the truth after an
  earlier version over-promised.  It then stopped being true and nobody moved it.
  Every lobby finish calls Lobby_SubmitRun (sv_timer.qc, at the foot of
  SV_TimerFinish), which posts map, leg, tick count, flags and the player's id to
  play.proto.bar; the row appears on a public board; and since build 66 the lobby
  also writes a .rec of the run, which /api/replay serves to anybody who asks.

  So the screen where a player decides whether to switch public lobbies on told
  them their run stayed private, at the moment the decision was made, while the
  shipped code uploaded it and published a downloadable recording of it.  That is
  the worst version of this defect the file has had: the previous ones promised a
  feature that did not exist, and this one concealed one that does.

  WHAT IS ADDED IS ALSO WHAT IS NOT UPLOADED, and that line is not padding.  The
  .hid journal is the most sensitive thing this game records -- it is raw mouse
  and keyboard timing, which Part 7 of the plan flags as behavioural biometrics --
  and it does NOT leave the machine today.  A reader told "your run is uploaded"
  and nothing else would reasonably assume the journal went with it.

  IT COST A LINE FROM THE SAME SECTION rather than a taller panel, because the
  note below is right that ~34 is the ceiling: at 35 the panel is 715 px and the
  button row sits at 651, so 720p still reaches the control with the bottom edge
  5 px clear.  The IP disclosure used to be made twice (once for the lobby, once
  for the picker) and is now made once, which paid for two of the three new lines.
*/
// (FS_TERMS_LINES was here until Patch 647.)

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
// P1101: rec_terms is the engine's CVAR_NOTFROMSERVER cvar now (a server's `seta` set an
// override cvar() read), which cvar_set refuses; localcmd_local runs at local level.
// Queued, so it lands before the next frame; nothing reads it inside m_init.
void(float tier) ui_terms_publish =
{
	if (checkbuiltin(localcmd_local))
		localcmd_local(sprintf("rec_terms %g\n", tier));
	else
		cvar_set("rec_terms", ftos(tier));      // an engine before P1101: a plain cvar
};

float(float tier) ui_consent_write =
{
	local filestream fh;

	fh = fopen("data/consent.txt", FILE_WRITE);
	if (fh < 0)
	{
		print("^1could not write data/consent.txt\n");
		return FALSE;
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
	// FILE_WRITE may buffer successfully and fail only when closed.
	if (ui_consent_read() != tier)
	{
		print("^1could not write data/consent.txt\n");
		return FALSE;
	}

	ms_consent = tier;
	ms_bgfor = -2;                 // re-evaluate online image permission

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
	ui_terms_publish(tier);
	return TRUE;
};

// A tier's colour on a map row: mint at the easy end through to rose.
vector(float t) ui_tier_col =
{
	if (t <= 2) return SUI_THEME_GOOD;
	if (t <= 4) return SUI_THEME_INFO;
	if (t <= 6) return SUI_THEME_ACCENT;
	if (t <= 8) return SUI_THEME_FOCUS;
	return SUI_THEME_BAD;
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
	// A pill: lit by its fill and accent text, outlined only under the cursor.
	if (hot)
		sui_style_box(pos, sz, CHIP_H * 0.5, on ? COL_ROW_SEL : COL_ROW_HOVER, SUI_THEME_EDGE_HI, 1);
	else
		sui_roundbox(pos, sz, CHIP_H * 0.5, on ? COL_ROW_SEL : COL_ROW, 1);
	sui_text([pos_x + CHIP_PAD * 0.5, pos_y + (CHIP_H - SZ_LABEL_H) * 0.5],
	         SZ_LABEL, label, on ? COL_ACCENT : (hot ? COL_TEXT : COL_DIM), 1, 0);

	return w;
};

// A text field's box: a recessed well.
void(vector pos, vector size, float focus) ui_field_box =
{
	sui_style_box(pos, size, 7, SUI_THEME_WELL, focus ? COL_ACCENT : SUI_THEME_EDGE, 1);
};

// Single-line text field.  sui_text_input owns the caret and the keystrokes;
// all this adds is the box, the placeholder and a blinking caret.
void(string id, vector pos, vector size, __inout string text,
     __inout float cursor, string placeholder) ui_field =
{
	sui_text_metrics(6, SZ_LABEL);  // Patch 655: the caret goes where the click was, and a drag selects
	sui_text_input(id, pos, size, text, cursor);

	float focus = sui_text_has_focus(id);
	ui_field_box(pos, size, focus);

	vector tp = [pos_x + 6, pos_y + (size_y - SZ_LABEL_H) * 0.5];
	if (focus)
		sui_text_selection(id, tp, SZ_LABEL, text, cursor, SUI_THEME_SELECTED, 1);
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
	sui_text_metrics(6, SZ_LABEL);
	sui_text_input(id, pos, size, text, cursor);

	float focus = sui_text_has_focus(id);
	ui_field_box(pos, size, focus);

	vector tp = [pos_x + 6, pos_y + (size_y - SZ_LABEL_H) * 0.5];
	if (focus)
		sui_text_selection(id, tp, SZ_LABEL, text, cursor, SUI_THEME_SELECTED, 1);

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
  The library switch's three chips, in strip order.  Build 89.

  A BIT AND NOT A SRC_* INDEX, because that bit is ANDed straight against
  ms_lst in ui_refilter and 0 is a real answer there -- "do not test this at
  all" -- rather than a missing one.  Two functions over one table of two
  entries is the shape every other strip on this screen uses (ui_mode_label /
  ui_mode_id), and the strip is drawn from the same loop.
*/
float(float slot) ui_srcf_bit =
{
	if (slot == 1) return SRC_BIT_MOM;
	if (slot == 2) return SRC_BIT_CSS;
	return 0;
};

string(float slot) ui_srcf_label =
{
	if (slot == 1) return "momentum";
	if (slot == 2) return "cs:s";
	return "both";
};

#define SRCF_NCHIPS 3

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
  five lobbies are bhop (cfg/lobby/lobby4.cfg, lobby5.cfg), so for a bhop map somebody
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

  Field order inside the packed ms_meta string. The primary tier is NOT in here;
  it lives in ms_tierv, with independently sourced filter values kept alongside.
*/
#define MT_LINEAR   0
#define MT_STAGES   1
#define MT_BONUS    2
#define MT_PAGE     3
#define MT_CELL     4
#define MT_UUID     5
/*
  Where the tier came from -- mapmeta.txt column 10, added in build 17.

  "rank" is a ranked leaderboard tier. Source provenance stays in the tooltip;
  both source labels use fixed colours, without punctuation marks.

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

  "ksf" (build 89) does NOT come from this file at all -- it is written by the
  fallback at the end of ui_meta_load for a map Momentum has no record of but
  KSF's roster does, and it is here because it shares the row's mark.  462 rows,
  every one of them a map that read untiered before.
*/
#define MT_TSRC     6
// KSF's own tier, mapmeta.txt column 11 (ROADMAP 7), "-" when KSF has none or
// the file predates it. Captured in ms_ksftier, never merged into ms_tierv.
#define MT_KTIER    7

/*
  Runs at the END of ui_load_maps, once ms_count is final.

  The two buffers are grown to exactly ms_count BEFORE the file is opened. A
  short buffer is survivable -- bufstr_get returns "" past the end -- but a
  misaligned one would put one map's tier on another's row, and that failure is
  silent and looks like bad data rather than a bug.  Establishing the length
  first makes misalignment impossible regardless of what the file contains.
*/
// Independent source tiers have no zero, fractional or out-of-range values.
string(string value) ui_source_tier =
{
	local float tier;
	tier = stof(value);
	if (tier >= 1 && tier <= 10 && tier == floor(tier))
		return ftos(tier);
	return "0";
};

void() ui_meta_load =
{
	local filestream fh;
	local hashtable byname;
	local string ln, key;
	local float i, n, row, hit, maxpage, vp;
	local string pth, pg, cl;

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

	pth = Mmm_MetaPath();       // P1099: the Pi's copy when it is the newer
	Mmm_Pages(pth);
	Mmm_UrlReset();
	fh = fopen(pth, FILE_READ);
	if (fh < 0)
	{
		print("^3WOS: data/mapmeta.txt missing -- run tools\\mapmeta.py then "
		      "tools\\mapthumbs.py.  No metadata counts or thumbnails.\n");
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
		// Local roster aliases inherit a different map's tier; network rows name
		// their own catalogue map. Neither alias metadata nor local inference is MOM.
		if (!strcmp(argv(10), "alias"))
		{
			if (!strcmp(bufstr_get(ms_momtsrc, row), "local"))
			{
				bufstr_set(ms_momtier, row, "0");
				bufstr_set(ms_momtsrc, row, "");
			}
		}
		else if (stof(ui_source_tier(argv(2))) > 0)
		{
			if (n >= 11 && !strcmp(argv(10), "ksf"))
				bufstr_set(ms_ksftier, row, ui_source_tier(argv(2)));
			else
			{
				local float usemom;
				usemom = TRUE;
				if (!strcmp(argv(10), "sugg"))
					usemom = (stof(bufstr_get(ms_momtier, row)) <= 0);
				if (usemom)
				{
					bufstr_set(ms_momtier, row, ui_source_tier(argv(2)));
					bufstr_set(ms_momtsrc, row, (n >= 11) ? argv(10) : "-");
				}
			}
		}
		if (n >= 12)
			if (stof(ui_source_tier(argv(11))) > 0)
				bufstr_set(ms_ksftier, row, ui_source_tier(argv(11)));
		bufstr_set(ms_modev, row, argv(9));

		// argv(10) only when it is there.  The `n < 10` guard above is what makes
		// the column additive: this menu reads a pre-build-17 mapmeta.txt exactly
		// as it always did and simply sees no provenance, which draws as a plain
		// tier -- the same rule the .rec header follows.  tokenize() returns ""
		// past the end anyway, so this is belt and braces, but the belt is the
		// documented contract and worth writing down.
		// strcat for the tail: a builtin takes 8 parameters, and sprintf drops a 9th.
		// P1099: a cell on a page this install lacks (or has another build of) is the
		// row's own small JPEG from the Pi instead, on a virtual page.
		pg = argv(6);
		cl = argv(7);
		if (pg != "-")
		if (!Mmm_PageOK(stof(pg)))
			pg = "-";
		if (pg == "-")
		{
			vp = Mmm_UrlPage(argv(8));
			if (vp >= 0)
			{
				pg = ftos(vp);
				cl = "0";
			}
		}
		bufstr_set(ms_meta, row, strcat(sprintf("%s %s %s %s %s %s ",
		                                        argv(3), argv(4), argv(5),
		                                        pg, cl, argv(8)),
		                                (n >= 11) ? argv(10) : "-", " ",
		                                (n >= 12) ? argv(11) : "-"));

		if (pg != "-")
			if (stof(pg) < MMM_VPAGE)
			if (stof(pg) > maxpage)
				maxpage = stof(pg);

		hit = hit + 1;
	}
	fclose(fh);
	hash_destroytab(byname);

	/*
	  THE SECOND TIER SOURCE, and the reason "a lot of maps don't have their
	  tiers" was true of the browser and not of the data.

	  mapmeta.txt is Momentum's cache and describes only maps Momentum knows.
	  data/mapdl.txt carries a tier too, and maproster.py fills that from KSF's
	  roster wherever Momentum has nothing (maproster.py:413) -- so 462 maps had
	  a real tier sitting in a file this menu already opens, and drew "--".
	  Measured 2026-09-28: 590 listed maps have no mapmeta row, 462 of them have
	  a KSF tier, 128 have none from anywhere and still draw "--".

	  ONLY WHERE MOMENTUM SAID NOTHING.  Where both have a tier the loop above
	  has already written Momentum's, which is the ranking this browser's chips
	  are numbered for; this never overwrites it.  The row is marked "ksf" rather
	  than drawn as a plain tier because it is another community's ranking of the
	  same map and the two scales are not the same scale.
	*/
	local float fb;
	fb = 0;
	if (ms_dltier >= 0)
		for (i = 0; i < ms_count; i = i + 1)
		{
			if (stof(bufstr_get(ms_tierv, i)) > 0)
				continue;
			if (stof(bufstr_get(ms_dltier, i)) <= 0)
				continue;

			bufstr_set(ms_tierv, i, bufstr_get(ms_dltier, i));
			// Only the provenance changes.  A row with no tier lands here too
			// (7 today: surf_omnibus's 11 stages, and the cell mapthumbs gives
			// it), so what mapmeta knew is kept; no row at all is all "-".
			n = tokenize(bufstr_get(ms_meta, i));
			if (n > MT_UUID)
				bufstr_set(ms_meta, i, strcat(sprintf("%s %s %s %s %s %s ksf ",
				                                      argv(MT_LINEAR), argv(MT_STAGES),
				                                      argv(MT_BONUS), argv(MT_PAGE),
				                                      argv(MT_CELL), argv(MT_UUID)),
				                              (n > MT_KTIER) ? argv(MT_KTIER) : "-"));
			else
				bufstr_set(ms_meta, i, "- - - - - - ksf -");
			fb = fb + 1;
		}

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

	print(sprintf("WOS: %s matched %g of %g maps, %g thumbnail page(s)"
	              ", %g picture(s) from the Pi, %g tier(s) from KSF's roster\n",
	              pth, hit, ms_count, maxpage + 1, Mmm_UrlCount(), fb));

	/*
	  One probe against a file we know we wrote, so that a later "no backdrop"
	  cannot be blamed on the wrong thing.  ui_map_backdrop chooses its image by
	  asking fopen which files exist; this says whether fopen can answer at all.
	*/
	if (!ui_file_exists("gfx/mapthumbs/atlas0.png"))
		print("^3WOS: gfx/mapthumbs/atlas0.png not readable -- run "
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
	print(sprintf("WOS: gametypes --%s\n", rep));
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

  THE HEADER IS CHECKED, AND ALL THREE VERSIONS PASS.  best.pb is "FTESURF-PB 1"
  as SV_PBSave once wrote it, "FTESURF-PB 2" once tools/migrate_runs.py legs1 has
  renumbered its stage legs, or "FTESURF-PB 3" as SV_PBSave writes it today;
  lobby.pb is always 2.  Version 2 changed what a STAGE key means (stage k is leg
  k, where version 1 keyed by start segment) and left `best 0 0` meaning the full
  run, so for this column the two read alike.

  3 WAS MISSING AND IT WAS A LIVE REGRESSION, NOT A GAP LEFT FOR LATER.  Build 76
  moved the run clock onto the mover's tick counter and bumped this header to 3
  because the VALUES are no longer comparable with a v2 file -- but the key layout
  did not move at all, `best 0 0` still means the full run, and this reader went
  on rejecting it.  The effect on screen was not a blank: run_pb_best returned 0,
  so the map list fell through to the slower lobby time and drew THAT instead, and
  every player who had set a personal best since build 76 was shown a worse number
  with nothing to say it had happened.  The bump was the safe half of the
  migration and this reader turned it into the unsafe one.

  Which is the rule below working exactly as written, and the rule is still right:
  skipping an unknown version is correct, and the cost of that correctness is that
  every version bump has to visit the readers.  This one was not visited.  The
  writer is SV_PBSave (sv_timer.qc) and the readers are here and SV_PBLoad, which
  keeps any version it is given and only branches on `ver < 2`.

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
				if (v != 1 && v != 2 && v != 3)
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
	note = sprintf("WOS: %g personal-best files, %g lobby-best files, "
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
  data/mapwr.txt -> ms_wr: the best known main-track time, in milliseconds.

  Same shape as ui_meta_load, and for the same reason -- the buffer is grown to
  exactly ms_count before the file is opened, so a row can be missing but never
  misaligned onto its neighbour.

  A MISSING FILE IS SILENT.  Every other table here says so when it is absent,
  but this one is optional by design: an install with no mapwr.txt draws the
  rows it drew before, with no best line, and that is a column not being offered
  rather than anything being wrong.  Saying "missing" would send people looking
  for a tool they do not need to run.

  The holder's name is the last field and is NOT read.  It can hold spaces and
  colour codes, which is why the writer puts it last; the row has no width for
  it, and tokenize past argv(3) would be paid on every map for nothing.
*/
void() ui_wr_load =
{
	local filestream fh;
	local hashtable byname;
	local string ln;
	local float i, n, row, hit;

	if (ms_wr >= 0) buf_del(ms_wr);
	ms_wr = buf_create();
	ms_wrcount = 0;
	for (i = 0; i < ms_count; i = i + 1)
		bufstr_add(ms_wr, "", TRUE);

	fh = fopen("data/mapwr.txt", FILE_READ);
	if (fh < 0)
		return;

	byname = hash_createtab(4096, EV_FLOAT);
	for (i = 0; i < ms_count; i = i + 1)
		hash_add(byname, strtolower(bufstr_get(ms_name, i)), i,
		         HASH_REPLACE | EV_FLOAT);

	hit = 0;
	while ((ln = fgets(fh)) != "")
	{
		n = tokenize(ln);
		if (n < 3)
			continue;
		if (argv(0) != "wr")
			continue;

		row = hash_get(byname, strtolower(argv(1)), -1, EV_FLOAT);
		if (row < 0)
			continue;               // a time for a map this install cannot list

		// > 0 and not >= 0: the writer already excludes millis 0, and a zero
		// here would draw "0:00.000" as though somebody had set it.
		if (stof(argv(2)) <= 0)
			continue;

		bufstr_set(ms_wr, row, argv(2));
		hit = hit + 1;
	}
	fclose(fh);
	hash_destroytab(byname);

	ms_wrcount = hit;
	print(sprintf("WOS: %g map(s) have a best time on record\n", hit));
};

/*
  data/mapdeps.txt -> ms_deps (ROADMAP 6): the games a map needs beyond the packs
  mounted at boot, as indices into a small spec table whose state comes from
  Patch 480's fs_addonstate -- asked once per spec, at load: 0 not installed,
  1 installed, 2 mounted, -1 cannot tell (an engine without the builtin, or a
  spec it cannot check).  Optional like
  mapwr.txt: no file, no badges.
*/
#define DEP_MAX 8
strbuf ms_deps;
string dep_spec[DEP_MAX];
string dep_lbl[DEP_MAX];
float  dep_state[DEP_MAX];
float  dep_n;
float  ms_depcount;

// "steam:Team Fortress 2/tf" -> "TF2": the game's own short name where it has one.
string(string spec) ui_dep_label =
{
	local string g;
	local float p;
	g = spec;
	if (substring(g, 0, 6) == "steam:")
		g = substring(g, 6, strlen(g) - 6);
	p = strstrofs(g, "/", 0);
	if (p > 0)
		g = substring(g, 0, p);
	if (g == "Team Fortress 2") return "TF2";
	if (g == "Counter-Strike Global Offensive") return "CS:GO";
	if (g == "Counter-Strike Source") return "CS:S";
	if (g == "Half-Life 2") return "HL2";
	if (g == "Momentum Mod Playtest") return "MOM mount";   // its mount/ folder: content it ships for other games
	return substring(g, 0, 14);
};

float(string spec) ui_dep_index =
{
	local float i;
	for (i = 0; i < dep_n; i = i + 1)
		if (dep_spec[i] == spec)
			return i;
	if (dep_n >= DEP_MAX)
		return -1;
	dep_spec[dep_n] = strzone(spec);
	dep_lbl[dep_n]  = strzone(ui_dep_label(spec));
	dep_state[dep_n] = checkbuiltin(fs_addonstate) ? fs_addonstate(spec) : -1;
	dep_n = dep_n + 1;
	return dep_n - 1;
};

void() ui_deps_load =
{
	local filestream fh;
	local hashtable byname;
	local string ln, nm, spec, cur, say;
	local float i, p, row, k, hit, drop;

	if (ms_deps >= 0) buf_del(ms_deps);
	ms_deps = buf_create();
	for (i = 0; i < ms_count; i = i + 1)
		bufstr_add(ms_deps, "", TRUE);
	for (i = 0; i < dep_n; i = i + 1)
	{
		strunzone(dep_spec[i]);
		strunzone(dep_lbl[i]);
	}
	dep_n = 0;
	ms_depcount = 0;

	fh = fopen(Mmm_DepsPath(), FILE_READ);  // P1099
	if (fh < 0)
		return;

	byname = hash_createtab(4096, EV_FLOAT);
	for (i = 0; i < ms_count; i = i + 1)
		hash_add(byname, strtolower(bufstr_get(ms_name, i)), i,
		         HASH_REPLACE | EV_FLOAT);

	hit = drop = 0;
	while ((ln = fgets(fh)) != "")
	{
		// "dep <map> <spec>": the spec has spaces ("steam:Team Fortress 2/tf"),
		// so it is the rest of the line, not a token.
		if (substring(ln, 0, 4) != "dep ")
			continue;
		p = strstrofs(ln, " ", 4);
		if (p < 0)
			continue;
		nm = substring(ln, 4, p - 4);
		spec = substring(ln, p + 1, strlen(ln) - p - 1);
		if (substring(spec, strlen(spec) - 1, 1) == "\r")
			spec = substring(spec, 0, strlen(spec) - 1);
		row = hash_get(byname, strtolower(nm), -1, EV_FLOAT);
		if (row < 0 || spec == "")
			continue;
		k = ui_dep_index(spec);
		if (k < 0)
		{
			drop = drop + 1;        // a game past the table: said below, not lost silently
			continue;
		}
		cur = bufstr_get(ms_deps, row);
		bufstr_set(ms_deps, row, (cur == "") ? ftos(k) : strcat(cur, " ", ftos(k)));
		hit = hit + 1;
	}
	fclose(fh);
	hash_destroytab(byname);

	ms_depcount = hit;
	say = "";
	for (i = 0; i < dep_n; i = i + 1)
		say = sprintf("%s %s=%g", say, dep_lbl[i], dep_state[i]);
	if (drop > 0)
		say = sprintf("%s  (%g line(s) name a game past the %g-game table)", say, drop, DEP_MAX);
	print(sprintf("WOS: %g map need(s) for an extra game;%s\n", hit, say));
};

// The row's "needs" text: each game red when this PC lacks it, plain when it has
// it, dim when the engine cannot say.  "" for a map that needs nothing.
string(float row) ui_deps_text =
{
	local string s, d;
	local float n, i, k;
	d = bufstr_get(ms_deps, row);
	if (d == "")
		return "";
	n = tokenize(d);
	s = "";
	for (i = 0; i < n; i = i + 1)
	{
		k = stof(argv(i));
		s = strcat(s, (s == "") ? "" : " ",
		           (dep_state[k] == 0) ? "^1" : ((dep_state[k] > 0) ? "^7" : "^9"),
		           dep_lbl[k]);
	}
	return s;
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
	if (page >= MMM_VPAGE)
	{
		sui_fill(pos, size, '0.05 0.05 0.07', 1, 0);    // until the download lands
		sui_subpic(pos, size, Mmm_UrlFor(page), '0 0 0', '1 1 0', '1 1 1', 1, 0);
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

/*
  data/mapdl.txt -- the maps the Pi will hand out, appended to the list as rows
  this install does not have.  Written by tools/mapscan.py every six hours.

  THE LIST COULD NOT SHOW A MAP YOU DO NOT HAVE, and that is the actual reason
  the download button did not exist: ui_load_maps builds every row from
  search_begin, so "in the list" and "on the disk" were the same fact and there
  was nothing for a button to act on.  This is the other half.

  It is the PI'S inventory, not the catalogue.  1748 maps are catalogued and the
  Pi serves 1239 of them; offering the other 509 would draw a button that 404s,
  which is worse than no button.  mapscan.py takes that intersection so this
  does not have to guess.

  A missing file is not an error and not a warning.  It means downloads are not
  set up on this install, and the list behaves exactly as it did before.
*/
// Up here, away from the rest of the download block, because ui_dl_load is its
// first caller and QuakeC has no forward references.
//
// Separate from ui_dl_ready because the two arrived in different patches: a 465
// binary can download a map it does not have and cannot size one it does, so
// the wrong-build check has to go quiet on its own rather than take the whole
// Download button down with it.
float  dl_have_kb;      // 1 if the engine has mapfilekb (Patch 466), -1 unasked

float() ui_dl_kb_ready =
{
	if (dl_have_kb == 0)
		dl_have_kb = checkbuiltin(mapfilekb) ? 1 : -1;
	return dl_have_kb > 0;
};

void() ui_pool_load =
{
	local float i, d, j, found;
	local string pat, nm;
	local searchhandle h;
	local hashtable zones;

	if (ms_enabled >= 0) buf_del(ms_enabled);
	if (ms_zoned >= 0) buf_del(ms_zoned);
	ms_enabled = buf_create();
	ms_zoned = buf_create();
	zones = hash_createtab(4096, EV_FLOAT);
	for (d = 0; d < 2; d++)
	{
		pat = (d == 0) ? "maps/zones/local/*.json" : "maps/zones/online/*.json";
		h = search_begin(pat, 0, TRUE);
		if (h < 0) continue;
		for (j = 0; j < search_getsize(h); j++)
		{
			// Search returns paths: remove the known directory and .json suffix.
			nm = strtolower(search_getfilename(h, j));
			nm = substring(nm, strlen(pat) - 6, strlen(nm) - strlen(pat) + 1);
			hash_add(zones, nm, 1, HASH_REPLACE | EV_FLOAT);
		}
		search_end(h);
	}
	for (i = 0; i < ms_count; i++)
	{
		bufstr_set(ms_enabled, i, "1");
		found = hash_get(zones, strtolower(bufstr_get(ms_name, i)), 0, EV_FLOAT);
		bufstr_set(ms_zoned, i, found ? "1" : "0");
	}
	hash_destroytab(zones);
};

/*
  Patch 999 (Lex: the game lags loading the update data at launch): mapfilekb was 457
  of the load's 818 ms on the install's 2,324 maps, all in one frame -- mostly misses
  through every mount for offered maps not on disk, now skipped when the boot search
  never listed the name (ui_mapseen).  The installed rows' wrong-build checks run
  UI_DLKB_STEP a frame after the load (ui_dlkb_step); a reader that acts on ms_have
  at once -- a join, the probes -- drains the rest first (ui_dlkb_finish).
*/
#define UI_DLKB_STEP 64
var float ui_dlkb_q = -1;   // strbuf of "row kb name" still owed the check
float ui_dlkb_bare;         // a bare entry turned out a wrong build: refilter when drained
hashtable ui_mapseen;       // ui_load_maps' search, by lowercased name
float ui_dlkb_i;

void() ui_dl_load =
{
	local filestream fh;
	local hashtable byname;
	local string ln, nm, key, of;
	local float i, n, row, appended, badged, stale, network, older;

	if (ui_dlkb_q >= 0)
		buf_del(ui_dlkb_q);
	ui_dlkb_q = buf_create();
	ui_dlkb_i = 0;
	ui_dlkb_bare = FALSE;

	// Patch 652: the list fetched from the directory (m_lobby.qc Mdl_Reply,
	// which wrote it row by row), else the one the release shipped.
	// Patch 781: not when the shipped one is newer (offline after an update).
	older = Mdl_NetOlder();
	fh = -1;
	if (!older)
		fh = fopen(MDL_FILE, FILE_READ);
	else
		print("^5maplist:^7 the shipped list is newer than the saved directory list -- reading it\n");
	network = (fh >= 0);
	if (fh < 0)
		fh = fopen("data/mapdl.txt", FILE_READ);
	if (fh < 0)
		return;

	byname = hash_createtab(4096, EV_FLOAT);
	for (i = 0; i < ms_count; i = i + 1)
		hash_add(byname, strtolower(bufstr_get(ms_name, i)), i,
		         HASH_REPLACE | EV_FLOAT);

	appended = 0;
	badged = 0;
	stale = 0;
	while ((ln = fgets(fh)) != "")
	{
		n = tokenize(ln);
		if (n < 8)
			continue;
		if (argv(0) != "dl")
			continue;

		nm = argv(1);
		key = strtolower(nm);
		// The map this row is a second build OF (Patch 652); read now, argv
		// does not survive the calls below.
		of = "";
		if (n >= 11)
		if (argv(10) != "-")
			of = argv(10);
		row = hash_get(byname, key, -1, EV_FLOAT);
		if (row < 0) row = ms_count;
		bufstr_set(ms_enabled, row, (n >= 13) ? argv(12) : "1");
		if (n >= 13) bufstr_set(ms_zoned, row, argv(11));

		if (row < ms_count)
		{
			bufstr_set(ms_varof, row, of);
			// Already on disk.  Whether it turned up recently enough to badge.
			if (argv(7) == "1")
			{
				bufstr_set(ms_new, row, "1");
				badged = badged + 1;
			}

			/*
			  HAVING A FILE OF THAT NAME AND HAVING THE RIGHT BUILD ARE DIFFERENT
			  FACTS, and only the first was ever checked -- so the one case the
			  Download button could not help with was a WRONG build, which is
			  exactly what a server kicks you for (mapcrc mismatch, cl_parse.c:
			  7669 "being modfied").  Reported from a laptop whose Momentum copy
			  of surf_666 differed from the Pi's.

			  mapfilekb resolves through the MOUNT ORDER.  search_getfilesize
			  cannot: it answers for whichever duplicate the search listed first
			  and NAMESORT is explicitly unstable, so with the same map in two
			  mounts it can describe the copy the engine will NOT load -- which
			  is precisely the case this is for.

			  A SIZE DIFFERENCE IS CONCLUSIVE PROOF of a different build; equal
			  sizes prove nothing at all.  So this under-reports by construction
			  and never accuses a correct install, which is the right way round
			  for a check whose action is a re-download.
			*/
			if (ui_dl_kb_ready())
			if (stof(argv(5)) > 0)
				bufstr_set(ui_dlkb_q, buf_getsize(ui_dlkb_q), sprintf("%g %s %s", row, argv(5), nm));
			// The tier travels whether the map is here or not: an INSTALLED map
			// Momentum has no record of has the same hole, and this file is the
			// only place a tier for it exists.  ui_meta_load picks it up.
			bufstr_set(ms_dltier, row, argv(4));
			bufstr_set(ms_momtier, row, (n >= 9) ? ui_source_tier(argv(8)) : "0");
			bufstr_set(ms_ksftier, row, (n >= 10) ? ui_source_tier(argv(9)) : "0");
			bufstr_set(ms_momtsrc, row, network ? "network" : "local");

			/*
			  AND SO DOES THE LIBRARY, which is the fix for "I see like 30 surf
			  maps in the CS:S list".

			  ms_lst was taken from the MOUNT alone -- where the file happens to
			  sit -- and this column is asked "which library is this map in".
			  Those are different questions for exactly the maps the switch
			  exists to separate: 463 of the offerable maps are in BOTH
			  catalogues (`km`), and every one of them that Momentum also ships
			  read as Momentum-only and disappeared from the CS:S side. The
			  KSF-only maps you have already downloaded are worse off still --
			  they land in ftesurf/maps/, which is neither mount, so they answer
			  neither chip.

			  OR, NOT REPLACE. A map in the Momentum mount really is available
			  from Momentum; the catalogue adds that KSF lists it too. Both are
			  true and the row already says "MOM CSS" when they are.

			  ui_isgamemode gates it for the same reason the passes above do: a
			  catalogue letter must not pull de_dust2 out of Other.
			*/
			if (ui_isgamemode(nm))
			{
				local float cbit;
				cbit = 0;
				if (strstrofs(argv(3), "k") >= 0) cbit = cbit | SRC_BIT_CSS;
				if (strstrofs(argv(3), "m") >= 0) cbit = cbit | SRC_BIT_MOM;
				if (cbit)
					bufstr_set(ms_lst, row,
					           ftos(stof(bufstr_get(ms_lst, row)) | cbit));
			}
			continue;
		}

		/*
		  A row for a map that is not here.  Every parallel buffer gets an entry
		  or they desync -- ms_tierv, ms_modev and ms_meta are filled by
		  ui_meta_load, which runs next and sizes itself from ms_count.

		  ms_lst IS RESOLVED HERE, not left at "0" for the second pass in
		  ui_load_maps to finish -- that pass has already run by the time this is
		  called, so a "0" written here was never resolved and stayed 0.  It cost
		  nothing while nothing read ms_lst for these rows; the source switch
		  reads it, and with "0" every downloadable map answered neither side of
		  it and the list went empty.  Same rule the second pass applies: a
		  movement map is filed under its source's list, anything else under
		  Other.
		*/
		/*
		  BOTH LETTERS, TESTED SEPARATELY.  mapscan.py writes four values in
		  this column -- "k", "m", "km" and "-" -- and the old reading was
		  `== "k" ? CSS : MOM`, which filed all 463 "km" maps as Momentum-only
		  and all 128 "-" maps as Momentum as well.  That was invisible while the
		  bit only picked the row's label; the switch turns it into maps missing
		  from a list they are in.
		*/
		local float dbit;
		dbit = 0;
		if (strstrofs(argv(3), "k") >= 0) dbit = dbit | SRC_BIT_CSS;
		if (strstrofs(argv(3), "m") >= 0) dbit = dbit | SRC_BIT_MOM;
		if (!dbit)
			dbit = SRC_BIT_OTHER;   // in neither catalogue; ms_lst is never 0
		/*
		  bufstr_set AT ms_count, NOT bufstr_add -- and this is a FIX, not a
		  style preference.  It was bufstr_add from build 58 to 87.

		  bufstr_add appends at the buffer's physical `used`
		  (PF_bufstr_add_internal, pr_bgcmd.c: `index = strbuflist[bufno].used`),
		  and ms_count is NOT that.  ui_load_maps' compaction pass moves the rows
		  it keeps down and then "just moves the count" -- the dropped rows are
		  still physically in the buffer past ms_count.  81 of them on this
		  install; the "maps not listed" line above is their count.

		  So every appended row was written 81 slots past the index the hash one
		  line below recorded for it -- and that hash has always been right.
		  Name, source, list, size and NEW badge all landed on a row 81 later
		  than the map they describe, while 81 rows the compaction had dropped
		  stayed inside the list at the indices the appends should have taken.

		  MEASURED at the tier column, which is the one that had an independent
		  count to disagree with: the engine reported 550 KSF tiers where the
		  data files allow 469, and 550 - 469 is 81 exactly.  With bufstr_set the
		  two agree at 469.  The other columns were wrong in the same way and had
		  nothing to notice it -- ms_have, ms_new and ms_dlkb are uniform over
		  the search-derived rows, so a displaced write was invisible.

		  Writing the index rather than trusting a length makes the
		  parallel-buffer invariant something the code states instead of
		  something it inherits.
		*/
		/*
		  NOT IN ms_name DOES NOT MEAN NOT ON DISK, so ask the filesystem.

		  ui_load_maps drops every map whose only mount is neither Momentum nor
		  CS:S -- and the GAMEDIR is one of those. A map fetched by this very
		  button lands in ftesurf/maps/, is dropped from the search list on the
		  next load, falls through to here, and was offered for download again
		  with a size next to it. The one thing a Download button must never do
		  is come back after it worked.

		  mapfilekb because it is already the wrong-build check's reader and it
		  resolves through the mount order; ui_file_exists is the fallback for a
		  pre-466 engine, which can answer "is it there" but not "how big".
		  Either way this is one lookup per OFFERED row -- 464 here, not 1833.
		*/
		local float hkb, listed;
		// Patch 999: a name the boot search never listed is on no mount -- asking cost a
		// miss through every one (~1 ms each, 377 rows here).  A listed one asks, exactly.
		hkb = 0;
		listed = hash_get(ui_mapseen, key, 0, EV_FLOAT);
		if (ui_dl_kb_ready())
		if (listed)
			hkb = mapfilekb(nm);
		// mapfilekb already reports absence. Only older engines need an open probe.
		if (!ui_dl_kb_ready())
			if (ui_file_exists(strcat("maps/", nm, ".bsp")))
				hkb = -1;               // present; size unknown on this engine

		bufstr_set(ms_name, ms_count, nm);
		bufstr_set(ms_src, ms_count, ftos(dbit));
		bufstr_set(ms_lst, ms_count, ui_isgamemode(nm) ? ftos(dbit) : ftos(SRC_BIT_OTHER));
		// "1" have it, "2" have the wrong build, "0" do not have it.  Same three
		// states the installed branch above writes, decided the same way.
		bufstr_set(ms_have, ms_count,
		           (hkb == 0) ? "0"
		                      : ((hkb > 0 && stof(argv(5)) > 0 && hkb != stof(argv(5)))
		                         ? "2" : "1"));
		bufstr_set(ms_new, ms_count, argv(7));
		bufstr_set(ms_dlkb, ms_count, argv(5));
		bufstr_set(ms_dltier, ms_count, argv(4));
		bufstr_set(ms_momtier, ms_count, (n >= 9) ? ui_source_tier(argv(8)) : "0");
		bufstr_set(ms_ksftier, ms_count, (n >= 10) ? ui_source_tier(argv(9)) : "0");
		bufstr_set(ms_momtsrc, ms_count, network ? "network" : "local");
		bufstr_set(ms_var, ms_count, "");
		bufstr_set(ms_varof, ms_count, of);
		bufstr_set(ms_pick, ms_count, "");
		hash_add(byname, key, ms_count, HASH_REPLACE | EV_FLOAT);
		ms_count = ms_count + 1;
		// COUNTED BY WHAT THE ROW WILL DRAW, not by "a line was read".  ms_dlcount
		// is the offer count the report prints and the gutter used to be gated on,
		// so a row that turned out to be on disk must not inflate it -- that is how
		// "offers 464" would keep saying 464 after you had downloaded them all.
		if (hkb == 0)
			appended = appended + 1;
		else if (hkb > 0 && stof(argv(5)) > 0 && hkb != stof(argv(5)))
			stale = stale + 1;
		if (argv(7) == "1")
			badged = badged + 1;
	}
	fclose(fh);

	/*
	  Patch 652: fold a second build into the row of the map it is a build of.
	  ms_varof holds that map's NAME until here and its row from here on.  A
	  build whose map is not in the list, or is itself a second build, keeps a
	  row of its own.  The plain row answers the CS:S library too: that is the
	  build the switch on it offers.
	*/
	ms_nvar = 0;
	for (i = 0; i < ms_count; i = i + 1)
	{
		nm = bufstr_get(ms_varof, i);
		if (nm == "")
			continue;
		row = hash_get(byname, strtolower(nm), -1, EV_FLOAT);
		if (row < 0 || row == i || row >= ms_count)
			row = -1;
		else if (bufstr_get(ms_varof, row) != "" || bufstr_get(ms_var, row) != "")
			row = -1;
		if (row < 0)
		{
			bufstr_set(ms_varof, i, "");
			continue;
		}
		bufstr_set(ms_varof, i, ftos(row));
		bufstr_set(ms_var, row, ftos(i));
		if (ui_isgamemode(bufstr_get(ms_name, row)))
			bufstr_set(ms_lst, row, ftos(stof(bufstr_get(ms_lst, row)) | SRC_BIT_CSS));
		ms_nvar = ms_nvar + 1;
	}
	// Which build each such row plays: the player's own choices.
	fh = fopen("data/mapbuild.txt", FILE_READ);
	if (fh >= 0)
	{
		while ((ln = fgets(fh)) != "")
		{
			if (tokenize(ln) != 2)
				continue;
			if (argv(0) != "css")
				continue;
			// Kept on a row with no second build today (ui_eff ignores it
			// there): the choice then outlives a list that lacks the build.
			row = hash_get(byname, strtolower(argv(1)), -1, EV_FLOAT);
			if (row >= 0)
				bufstr_set(ms_pick, row, "1");
		}
		fclose(fh);
	}
	hash_destroytab(byname);
	if (ms_nvar > 0)
		print(sprintf("WOS: %g map(s) have a CS:S build beside Momentum's -- one row, a switch\n",
		              ms_nvar));

	ms_dlcount = appended;
	ms_dlstale = stale;             // the offered rows'; ui_dlkb_step adds the installed ones
	print(sprintf("WOS: mapdl offers %g map(s) not installed here, %g new\n",
	              appended, badged));
};

void() ui_refilter;
// Patch 999: `max` of the installed rows' wrong-build checks.  A wrong build of a bare
// entry is hidden (ui_refilter), so the list is refiltered once, when drained, scroll kept.
void(float max) ui_dlkb_run =
{
	local float end, row, lkb;
	local vector keep;

	if (ui_dlkb_q < 0)
		return;
	end = min(ui_dlkb_i + max, buf_getsize(ui_dlkb_q));
	while (ui_dlkb_i < end)
	{
		tokenize(bufstr_get(ui_dlkb_q, ui_dlkb_i));
		ui_dlkb_i = ui_dlkb_i + 1;
		row = stof(argv(0));
		if (row >= ms_count)
			continue;
		lkb = mapfilekb(argv(2));
		if (lkb > 0)
		if (lkb != stof(argv(1)))
		{
			bufstr_set(ms_have, row, "2");
			bufstr_set(ms_dlkb, row, argv(1));
			ms_dlstale = ms_dlstale + 1;
			if (stof(bufstr_get(ms_dataq, row)) == DQ_BARE)
				ui_dlkb_bare = TRUE;
		}
	}
	if (ui_dlkb_i < buf_getsize(ui_dlkb_q))
		return;
	buf_del(ui_dlkb_q);
	ui_dlkb_q = -1;
	if (ui_dlkb_bare)
	{
		keep = ms_scroll;
		ui_refilter();
		ms_scroll = keep;
		ui_dlkb_bare = FALSE;
	}
	if (ms_dlstale > 0)
		print(sprintf("WOS: %g installed map(s) are a DIFFERENT BUILD from the server's -- offering a re-get\n",
		              ms_dlstale));
};

void() ui_dlkb_step = { ui_dlkb_run(UI_DLKB_STEP); };     // m_draw: a frame's share
void() ui_dlkb_finish = { ui_dlkb_run(1000000); };        // before acting on ms_have now

// Defined with the backdrop and the download block, far below.
string(string uuid, float scrw) ui_bgpick;
float() ui_dl_ready;

/*
  ms_dataq, once per load and after ui_meta_load: the picture test tokenizes
  ms_meta, which ui_refilter must not do per keystroke.  A picture is the atlas
  cell the row draws, else a full-size image on disk -- probed only for a row
  with a thumbnail id and no cell (6 of 2271 mapmeta rows on 2026-10-04).
*/
void() ui_data_load =
{
	local float i, pic, tier, play, dl, q;
	local float n[DQ_CLASSES];
	local string h;

	if (ms_dataq >= 0) buf_del(ms_dataq);
	ms_dataq = buf_create();
	dl = ui_dl_ready();
	for (q = 0; q < DQ_CLASSES; q++)
		n[q] = 0;

	for (i = 0; i < ms_count; i++)
	{
		pic = FALSE;
		if (tokenize(bufstr_get(ms_meta, i)) > MT_UUID)
		{
			if (argv(MT_PAGE) != "-")
			if (argv(MT_CELL) != "-")
				pic = TRUE;
			if (!pic)
			if (argv(MT_UUID) != "-")
				pic = (ui_bgpick(argv(MT_UUID), 0) != "");
		}
		tier = (stof(bufstr_get(ms_tierv, i)) > 0);

		// "1" here, "2" the wrong build of it; "0" is data/mapdl.txt's offer,
		// which only an engine with the downloadmap builtin can take up.
		h = bufstr_get(ms_have, i);
		play = FALSE;
		if (h == "1" || h == "2")
			play = TRUE;
		else if (h == "0")
			play = dl;

		if (pic && tier && play) q = DQ_FULL;
		else if (pic)            q = DQ_PICTURE;
		else if (tier)           q = DQ_TIER;
		else                     q = DQ_BARE;
		bufstr_set(ms_dataq, i, ftos(q));
		n[q] += 1;
	}
	print(sprintf("WOS: data -- %g full, %g picture only, %g tier only, %g "
	              "neither (listed when searched or under show all)\n",
	              n[DQ_FULL], n[DQ_PICTURE], n[DQ_TIER], n[DQ_BARE]));
};

void() ui_load_maps =
{
	if (ms_name >= 0) buf_del(ms_name);
	if (ms_src  >= 0) buf_del(ms_src);
	if (ms_lst  >= 0) buf_del(ms_lst);
	if (ms_have >= 0) buf_del(ms_have);
	if (ms_new  >= 0) buf_del(ms_new);
	if (ms_dlkb >= 0) buf_del(ms_dlkb);

	ms_name  = buf_create();
	ms_src   = buf_create();
	ms_lst   = buf_create();
	ms_have  = buf_create();
	ms_new   = buf_create();
	ms_dlkb  = buf_create();
	ms_count = 0;
	ms_dlcount = 0;
	ms_dlstale = 0;

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
		print("^1WOS: map search failed -- no maps mounted?\n");
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
	// Patch 999: every name on any mount, for ui_dl_load's offered rows.
	if (ui_mapseen)
		hash_destroytab(ui_mapseen);
	ui_mapseen = hash_createtab(4096, EV_FLOAT);

	float n = search_getsize(h);
	for (float i = 0; i < n; i++)
	{
		string nm = ui_mapname(search_getfilename(h, i));
		if (nm == "")
			continue;

		float bit = ui_classify(search_getpackagename(h, i));
		string key = strtolower(nm);
		hash_add(ui_mapseen, key, 1, HASH_REPLACE | EV_FLOAT);

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
		// Everything this loop sees came out of a filesystem search, so it is on
		// disk by construction.  ui_dl_load is the only thing that adds a "0".
		bufstr_add(ms_have, "1", TRUE);
		bufstr_add(ms_new,  "0", TRUE);
		bufstr_add(ms_dlkb, "0", TRUE);
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
		print(sprintf("WOS: %g maps hidden from the CS:GO/TF2 asset mounts "
		              "(ui_maps_assetmounts 1 to list them)\n", hidden));
	if (unlisted)
		print(sprintf("WOS: %g maps not listed -- in neither Momentum nor "
		              "Counter-Strike: Source\n", unlisted));

	// The counts overlap now, deliberately: a map in both Momentum and CS:S is
	// counted under both, because it is genuinely in both.  They no longer sum
	// to the total, and that is the point.
	print(sprintf("WOS: %g maps (%g duplicate entries coalesced) -- "
	              "momentum %g, counter-strike %g, other %g\n",
	              ms_count, dupes,
	              ms_nsrc[SRC_MOMENTUM], ms_nsrc[SRC_CSS], ms_nsrc[SRC_OTHER]));

	// All three join onto ms_name, so they can only run once it is final, and
	// ui_cat_load reads what ui_meta_load wrote.  None can fail in a way that
	// matters: a missing mapmeta.txt costs the metadata columns and files every
	// map by its name, and no .pb files means no times to show.
	/*
	  ms_dltier, created here rather than up with the others because the
	  compaction above is what settles ms_count.

	  It holds exactly ms_count entries, and so does every index ui_dl_load
	  writes -- see the bufstr_set block there, which is where this buffer's
	  first cut went wrong, and where finding out why turned up a build-58 defect.  The
	  five buffers created BEFORE the search do not: they still carry the rows
	  the compaction dropped, past ms_count.  Nothing may assume those lengths
	  agree.
	*/
	if (ms_dltier >= 0) buf_del(ms_dltier);
	ms_dltier = buf_create();
	// Independent manifest columns are indexed after compaction, just like ms_dltier.
	if (ms_momtier >= 0) buf_del(ms_momtier);
	if (ms_ksftier >= 0) buf_del(ms_ksftier);
	if (ms_momtsrc >= 0) buf_del(ms_momtsrc);
	ms_momtier = buf_create();
	ms_ksftier = buf_create();
	ms_momtsrc = buf_create();
	for (float t = 0; t < ms_count; t++)
	{
		bufstr_add(ms_dltier, "0", TRUE);
		bufstr_add(ms_momtier, "0", TRUE);
		bufstr_add(ms_ksftier, "0", TRUE);
		bufstr_add(ms_momtsrc, "", TRUE);
	}
	// Patch 652, sized the same way and for the same reason.
	if (ms_var >= 0)   buf_del(ms_var);
	if (ms_varof >= 0) buf_del(ms_varof);
	if (ms_pick >= 0)  buf_del(ms_pick);
	ms_var = buf_create();
	ms_varof = buf_create();
	ms_pick = buf_create();
	for (float t = 0; t < ms_count; t++)
	{
		bufstr_add(ms_var, "", TRUE);
		bufstr_add(ms_varof, "", TRUE);
		bufstr_add(ms_pick, "", TRUE);
	}

	// BEFORE ui_meta_load, not after: it appends rows to ms_name, and
	// ui_meta_load builds its byname hash from ms_name and then fills the tier
	// and gamemode columns.  Run the other way round and every downloadable map
	// would list as untiered, which is how a real tier 1 and "we have no idea"
	// come to look identical.
	ui_pool_load();
	ui_dl_load();

	ui_meta_load();
	ui_cat_load();
	ui_data_load();             // reads ms_tierv after ui_meta_load's KSF fallback
	run_pb_load();
	ui_wr_load();
	ui_deps_load();
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

// The headless reading of build 89's four changes.  Defined below ui_refilter,
// which it drives; this is the PROTOTYPE, which is how a call ahead of a
// definition is written here -- see m_close above and Lob_Poll in m_lobby.qc.
void(string arg) ui_browse_print;


// Rebuild ms_view from the query and the two filters.  O(ms_count), but only
// ever run on a keystroke or a filter change -- never from m_draw's steady state.
/*
  A map's place in tier order: tier 1 is 0, tier 10 is 9, and anything nothing
  knows a tier for is TIER_UNKNOWN -- last, and one bucket rather than ten holes.

  ELEVEN BUCKETS IS THE WHOLE RANGE.  mapmeta.txt's tiers run 1..10 (measured:
  458 at 1 down to 10 at 10, none outside), but the fallback in ui_meta_load now
  also writes KSF's, and nothing in this menu constrains what a data file says.
  An out-of-range tier lands with the untiered rather than off the end of the
  count array, which is the difference between a map drawn in the wrong place
  and a stray write.
*/
#define TIER_BUCKETS  11
#define TIER_UNKNOWN  10

float(float row) ui_tier_rank =
{
	local float t;
	t = stof(bufstr_get(ms_tierv, row));
	if (t >= 1 && t <= TIER_UNKNOWN)
		return t - 1;
	return TIER_UNKNOWN;
};

// ROADMAP 10: the list's sort key, the data class (DQ_*) and then the tier.
#define VIEW_BUCKETS  44        // DQ_CLASSES * TIER_BUCKETS

float(float row) ui_view_rank =
{
	return bound(0, stof(bufstr_get(ms_dataq, row)), DQ_CLASSES - 1) * TIER_BUCKETS
	       + ui_tier_rank(row);
};

// P1080: completion outside the view rank; unknown is its own last bucket.
// Keyed on the effective build, the name the row's card asks about.
#define SORT_BUCKETS  132       // 3 * VIEW_BUCKETS
float(float row) ui_eff;

float(float row) ui_sort_rank =
{
	local float d;
	if (!ms_compsort) return ui_view_rank(row);
	d = MCard_Done(bufstr_get(ms_name, ui_eff(row)));
	d = d < 0 ? 2 : (ms_compsort == 1 ? d : 1 - d);
	return d * VIEW_BUCKETS + ui_view_rank(row);
};

void() ui_refilter =
{
	if (ms_view >= 0) buf_del(ms_view);
	ms_view = buf_create();
	ms_viewcount = 0;
	ms_nhidden = 0;

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
		// Patch 652: a second build is on its map's row, behind the switch.
		if (bufstr_get(ms_varof, i) != "")
			continue;
		if (bufstr_get(ms_enabled, i) == "0")
		{
			if (bufstr_get(ms_var, i) == "") continue;
			if (bufstr_get(ms_enabled, stof(bufstr_get(ms_var, i))) == "0") continue;
		}
		if (q != "" && strstrofs(strtolower(bufstr_get(ms_name, i)), q) < 0)
		{
			// ...unless it is the name of the build folded into this row.
			if (bufstr_get(ms_var, i) == "")
				continue;
			if (strstrofs(strtolower(bufstr_get(ms_name, stof(bufstr_get(ms_var, i)))), q) < 0)
				continue;
		}

		// Either independently sourced tier matches; legacy collapsed values name neither.
		if (ms_tier != 0 && stof(bufstr_get(ms_momtier, i)) != ms_tier
		    && stof(bufstr_get(ms_ksftier, i)) != ms_tier)
			continue;

		// The library switch.  ms_lst, not ms_src -- see ms_srcf.
		if (ms_srcf != 0 && !(stof(bufstr_get(ms_lst, i)) & ms_srcf))
			continue;

		// Installed surf/bhop maps remain playable without metadata. Other bare
		// rows wait behind show all/search; the intentional filters above still apply.
		if (q == "")
		if (!ms_showall)
		if (stof(bufstr_get(ms_dataq, i)) == DQ_BARE)
		{
			local string movementname;
			movementname = strtolower(bufstr_get(ms_name, i));
			if (!(bufstr_get(ms_have, i) == "1"
			      && (stof(bufstr_get(ms_src, i)) & (SRC_BIT_MOM | SRC_BIT_CSS))
			      && (substring(movementname, 0, 5) == "surf_"
			          || substring(movementname, 0, 5) == "bhop_")))
			{
				ms_nhidden++;
				continue;
			}
		}

		bufstr_add(ms_view, ftos(i), TRUE);
		ms_viewcount++;
	}

	/*
	  ---- data class, then tier order --------------------------------------

	  ROADMAP 10: full data first, then a picture without the rest, then a tier
	  without a picture, then neither (ui_view_rank) -- and within each class
	  the tier order below, so VIEW_BUCKETS rather than TIER_BUCKETS buckets.

	  Tier 1 first, then 2, and everything nothing knows a tier for at the
	  BOTTOM rather than scattered alphabetically through the middle.  Asked for
	  as "make sure the map selection is pretty".

	  A COUNTING SORT, and specifically NOT buf_sort (#444).  Two reasons, and
	  the second is the one that decides it:

	    * the key is not the string.  ms_view holds "417"; sorting those as text
	      puts 1000 before 2, and sorting them as numbers is not what buf_sort
	      does either -- it has a sortprefixlen and nothing else.
	    * within a tier the order must stay the name order the list is already
	      in, so the sort has to be STABLE, and nothing specifies that buf_sort
	      is.  The engine's own NAMESORT next door is an explicitly unstable
	      qsort (pr_bgcmd.c:3592-3598) and this file already carries one fix for
	      having assumed otherwise.  A counting sort is stable by construction,
	      which is a property of the algorithm rather than of the engine.

	  Two passes over the FILTERED rows, not over all 2270: on a typed query
	  that is a handful.  bufstr_set past the end grows the buffer, so ms_view is
	  written in final position directly and never shuffled.
	*/
	if (ms_viewcount > 1)
	{
		local strbuf flt;
		local float k, r, idx;
		local float tcnt[SORT_BUCKETS], toff[SORT_BUCKETS];

		flt = buf_create();
		if (flt >= 0)
		{
			buf_copy(ms_view, flt);

			for (k = 0; k < SORT_BUCKETS; k++)
				tcnt[k] = 0;
			for (k = 0; k < ms_viewcount; k++)
				tcnt[ui_sort_rank(stof(bufstr_get(flt, k)))] += 1;

			// Running total: rank r starts where every earlier rank ended.
			toff[0] = 0;
			for (k = 1; k < SORT_BUCKETS; k++)
				toff[k] = toff[k - 1] + tcnt[k - 1];

			for (k = 0; k < ms_viewcount; k++)
			{
				idx = stof(bufstr_get(flt, k));
				r   = ui_sort_rank(idx);
				bufstr_set(ms_view, toff[r], ftos(idx));
				toff[r] += 1;
			}
			buf_del(flt);
		}
	}

	ms_applied_query = ms_query;
	ms_applied_tier  = ms_tier;
	ms_applied_modes = ms_modes;
	ms_applied_srcf  = ms_srcf;
	ms_applied_showall = ms_showall;
	ms_applied_compsort = ms_compsort;
	ms_applied_donever = mcd_ver;
	ms_scroll = '0 0 0';
};

/*
  `ui_browse [map]` -- what build 89 actually did, in numbers a config can grade.

  EVERY LINE IS THE SUBJECT'S OWN ACTION, not a consequence of it: the tier
  counts are read back out of ms_tierv after ui_meta_load's fallback ran, the
  order line walks the ms_view ui_refilter just built, and the gutter line is
  the same stringwidth call the row draws with.  An arm that checked the screen
  instead would pass on a build where all four were compiled out.

  ui_load_maps FIRST, and that is not incidental -- ui_load_maps is lazy, so a
  reading taken before the browser has opened is a reading of an empty list.
  That is exactly how p466reget's first cut came to pass while measuring
  nothing.
*/
// Defined with the download block far below; the gutter is one of the four
// things ui_browse reports, so it needs a prototype up here.
float() ui_dl_gutter;

void(string arg) ui_browse_print =
{
	local float i, r, prev, bad, known, unk, ksf, wr, n0, nm, nc;
	local float gw, w1, w2, wasall;
	local float dqn[DQ_CLASSES];

	ui_load_maps();
	ui_dlkb_finish();

	known = unk = ksf = wr = 0;
	for (r = 0; r < DQ_CLASSES; r++)
		dqn[r] = 0;
	for (i = 0; i < ms_count; i++)
	{
		dqn[bound(0, stof(bufstr_get(ms_dataq, i)), DQ_CLASSES - 1)] += 1;
		if (stof(bufstr_get(ms_tierv, i)) > 0) known++; else unk++;
		if (tokenize(bufstr_get(ms_meta, i)) > MT_TSRC)
			if (argv(MT_TSRC) == "ksf")
			{
				// The first few BY NAME.  A count that disagrees with the data
				// files cannot be argued about from either end -- the rows have
				// to be nameable before anyone can say which side is wrong.
				if (ksf < 12)
					print(sprintf("ui_browse:   ksf %S tier %s\n",
					              bufstr_get(ms_name, i),
					              bufstr_get(ms_tierv, i)));
				ksf++;
			}
		if (bufstr_get(ms_wr, i) != "")
			wr++;
	}
	print(sprintf("ui_browse: maps %g -- tiered %g, untiered %g, %g of them "
	              "from ksf\n", ms_count, known, unk, ksf));
	print(sprintf("ui_browse: best times %g\n", wr));

	/*
	  The three settings of the library switch, counted through the real filter
	  rather than by re-deriving it here.  A count taken any other way would
	  agree with a broken ui_refilter.

	  ROADMAP 10: taken with "show all" lit, so they and the order below are of
	  the whole list, as in build 89; the hidden count is read after them.
	*/
	wasall = ms_showall;
	ms_showall = TRUE;
	ms_srcf = 0;            ui_refilter();  n0 = ms_viewcount;
	ms_srcf = SRC_BIT_MOM;  ui_refilter();  nm = ms_viewcount;
	ms_srcf = SRC_BIT_CSS;  ui_refilter();  nc = ms_viewcount;
	ms_srcf = 0;            ui_refilter();
	print(sprintf("ui_browse: library both %g, momentum %g, cs:s %g\n",
	              n0, nm, nc));

	// Tier order, walked.  `bad` is the first index that goes backwards, so a
	// failure names a row instead of just saying no.  On ui_view_rank since
	// ROADMAP 10: tier order within each data class, the classes in order.
	prev = -1;
	bad  = -1;
	for (i = 0; i < ms_viewcount; i++)
	{
		r = ui_sort_rank(stof(bufstr_get(ms_view, i)));      // = ui_view_rank with P1080's sort off
		if (r < prev && bad < 0)
			bad = i;
		prev = r;
	}
	print(sprintf("ui_browse: view %g, tier order %s\n", ms_viewcount,
	              (bad < 0) ? "ascending" : sprintf("BROKEN at %g", bad)));

	/*
	  THE HISTOGRAM IS PART OF THE ORDER CHECK, not decoration.  "Ascending" is
	  trivially true of a list whose rows are all one rank, so the verdict above
	  says nothing without the spread beside it -- an arm that passes because
	  its condition never occurred proves nothing.  Printed as ranks so it lines
	  up with the sort: rank 0 is tier 1, rank 10 is untiered.
	*/
	local string hist;
	hist = "";
	for (r = 0; r < TIER_BUCKETS; r++)
	{
		local float rn;
		rn = 0;
		for (i = 0; i < ms_viewcount; i++)
			if (ui_tier_rank(stof(bufstr_get(ms_view, i))) == r)
				rn++;
		hist = sprintf("%s%s%g", hist, (r == 0) ? "" : " ", rn);
	}
	print(sprintf("ui_browse: ranks %s (rank 0 = tier 1, rank %g = untiered)\n",
	              hist, TIER_UNKNOWN));
	if (ms_viewcount > 0)
		print(sprintf("ui_browse: first rank %g, last rank %g\n",
		              ui_tier_rank(stof(bufstr_get(ms_view, 0))),
		              ui_tier_rank(stof(bufstr_get(ms_view, ms_viewcount - 1)))));

	// The chip off, through the real filter, then the player's own setting back.
	ms_showall = FALSE;     ui_refilter();
	print(sprintf("ui_browse: data full %g, picture %g, tier %g, bare %g -- "
	              "show all off hides %g, lists %g\n", dqn[DQ_FULL], dqn[DQ_PICTURE],
	              dqn[DQ_TIER], dqn[DQ_BARE], ms_nhidden, ms_viewcount));
	ms_showall = wasall;    ui_refilter();

	/*
	  The gutter, measured the way the row measures it.  Font_Set first: this
	  runs from the console between frames, and stringwidth reads `drawfont` --
	  m_draw sets it every frame, but a reading taken before the first frame
	  would be of the bitmap font and would silently be the wrong number.
	*/
	Font_Set(ui_font_ui);
	w1 = stringwidth("Wrong build", TRUE, SZ_ROW);
	w2 = stringwidth("re-get 999.9 MB", TRUE, SZ_ROW);
	gw = ui_dl_gutter();
	print(sprintf("ui_browse: gutter %g px (label %g, re-get %g, pad %g)\n",
	              gw, w1, w2, DL_PAD * 2 + 4));

	// One named map, all the way through, for the cases where a count agrees
	// and the row is still wrong.
	if (arg != "")
	{
		// Scanned rather than ui_map_index'd: that lives 600 lines below and a
		// prototype for a diagnostic is not worth the header noise.
		local string want;
		want = strtolower(arg);
		i = ms_count;
		while (i > 0)
		{
			i = i - 1;
			if (strtolower(bufstr_get(ms_name, i)) == want)
				break;
			if (i == 0)
				i = -1;
		}
		if (i < 0)
			print(sprintf("ui_browse: %S is not listed\n", arg));
		else
			print(sprintf("ui_browse: %S tier %s src %s lst %s wr %s pb %s meta %S\n",
			              arg, bufstr_get(ms_tierv, i), bufstr_get(ms_src, i),
			              bufstr_get(ms_lst, i),
			              (bufstr_get(ms_wr, i) == "") ? "-" : bufstr_get(ms_wr, i),
			              (bufstr_get(ms_pbv, i) == "") ? "-" : bufstr_get(ms_pbv, i),
			              bufstr_get(ms_meta, i)));
		if (i >= 0)
		{
			local string ds;
			local float dn, dj, dk;
			ds = "";
			dn = tokenize(bufstr_get(ms_deps, i));
			for (dj = 0; dj < dn; dj = dj + 1)
			{
				dk = stof(argv(dj));
				ds = sprintf("%s %s=%g", ds, dep_lbl[dk], dep_state[dk]);
			}
			print(sprintf("ui_browse: %S needs%s\n", arg, ds));
		}
	}
};

/*
  Patch 652.  THE ROW WHOSE FILE A ROW'S ACTIONS ARE ABOUT: its CS:S build
  where one is folded in and chosen, else itself.  What a row SHOWS -- name,
  tier, picture, the best known time -- stays the plain map's; what it PLAYS,
  fetches, hosts and counts players on goes through here.
*/
float(float row) ui_eff =
{
	if (row < 0 || row >= ms_count)
		return row;
	if (bufstr_get(ms_var, row) != "")
	if (bufstr_get(ms_pick, row) == "1" || bufstr_get(ms_enabled, row) == "0")
	if (bufstr_get(ms_enabled, stof(bufstr_get(ms_var, row))) != "0")
		return stof(bufstr_get(ms_var, row));
	return row;
};

// Story sets this around its launch: a level is its exact map (medals count
// only there), never the row's chosen or fallback CS:S build.
float ui_plain_only;
float ui_launch_plain;          // ...kept for a launch the name screen resumes

string() ui_selected_name =
{
	local float row;
	if (ms_selected < 0 || ms_selected >= ms_count)
		return "";
	row = ui_plain_only ? ms_selected : ui_eff(ms_selected);
	if (bufstr_get(ms_enabled, row) == "0") return "";
	return bufstr_get(ms_name, row);
};

// Choose a row's build (css 1, Momentum's 0) and remember every choice.
void(float row, float css) ui_pick_set =
{
	local filestream fh;
	local float i;

	if (row < 0 || row >= ms_count)
		return;
	if (bufstr_get(ms_var, row) == "")
		return;
	if (bufstr_get(ms_enabled, css ? stof(bufstr_get(ms_var, row)) : row) == "0")
		return;
	bufstr_set(ms_pick, row, css ? "1" : "");
	if (ms_compsort) mcd_ver = mcd_ver + 1;     // P1080 sorts by the effective build
	fh = fopen("data/mapbuild.txt", FILE_WRITE);
	if (fh >= 0)
	{
		fputs(fh, "# the build the map list plays where a map has two; written by the menu\n");
		for (i = 0; i < ms_count; i = i + 1)
			if (bufstr_get(ms_pick, i) == "1")
				fputs(fh, sprintf("css %s\n", bufstr_get(ms_name, i)));
		fclose(fh);
	}
	print(sprintf("ui_build: %s plays %s\n", bufstr_get(ms_name, row),
	              bufstr_get(ms_name, ui_eff(row))));
};

// `ui_build <map> [mom|css]`: the switch's headless twin, and its report.
void(string mp, string pick) ui_build_print =
{
	local float i, row, v, j, visible;

	if (ms_name < 0 || !ms_count)
		ui_load_maps();             // only when nothing is loaded: a reload moves rows
	ui_dlkb_finish();
	row = -1;
	for (i = 0; i < ms_count; i = i + 1)
		if (strtolower(bufstr_get(ms_name, i)) == strtolower(mp))
			row = i;
	if (row < 0)
	{
		print(sprintf("ui_build: %s is not in the list (%g rows, %g with two builds)\n",
		              mp, ms_count, ms_nvar));
		return;
	}
	visible = FALSE;
	for (j = 0; j < ms_viewcount; j++)
		if (stof(bufstr_get(ms_view, j)) == row) visible = TRUE;
	print(sprintf("ui_pool: %s enabled %s zones %s visible %g\n",
	              bufstr_get(ms_name, row), bufstr_get(ms_enabled, row),
	              bufstr_get(ms_zoned, row), visible));
	if (bufstr_get(ms_var, row) != "")
	{
		v = stof(bufstr_get(ms_var, row));
		print(sprintf("ui_pool: %s enabled %s zones %s linked %s\n",
		              bufstr_get(ms_name, v), bufstr_get(ms_enabled, v),
		              bufstr_get(ms_zoned, v), bufstr_get(ms_name, row)));
	}
	if (bufstr_get(ms_var, row) == "")
	{
		print(sprintf("ui_build: %s has one build%s (%g rows, %g with two builds)\n",
		              bufstr_get(ms_name, row),
		              (bufstr_get(ms_varof, row) != "") ? ", and is folded into another row" : "",
		              ms_count, ms_nvar));
		return;
	}
	if (pick == "css")
		ui_pick_set(row, 1);
	else if (pick == "mom")
		ui_pick_set(row, 0);
	v = stof(bufstr_get(ms_var, row));
	// Two prints: a varargs call carries eight parameters.
	print(sprintf("ui_build: %s builds mom have %s, css %s have %s kb %s;",
	              bufstr_get(ms_name, row), bufstr_get(ms_have, row),
	              bufstr_get(ms_name, v), bufstr_get(ms_have, v), bufstr_get(ms_dlkb, v)));
	if (ms_bswrow == row)
		print(sprintf(" switch [cs_bmom%g] [cs_bcss%g];", ms_bswidx, ms_bswidx));
	print(sprintf(" pick %s; plays %s; lists %g\n",
	              (ui_eff(row) != row) ? "css" : "mom",
	              bufstr_get(ms_name, ui_eff(row)), stof(bufstr_get(ms_lst, row))));
	// P980: what a Story launch of this row would play, through the same read.
	j = ms_selected;
	ms_selected = row;
	ui_plain_only = TRUE;
	print(sprintf("ui_build: story plays %s\n", ui_selected_name()));
	ui_plain_only = FALSE;
	ms_selected = j;
};

/*
  The switch itself: two cells on the row's second line, the chosen build
  filled.  Registered after the row's own element, so a click here is the
  switch's and not the row's (the action column's rule).  -> the width taken.
*/
#define BSW_W   44
#define BSW_H   18
#define BSW_SZ  '12 12 0'

float(vector pos, float row, float idx) ui_build_switch =
{
	local float css, k, hov;
	local string id, lbl;
	local vector p;

	css = (ui_eff(row) != row);
	ms_bswrow = row;
	ms_bswidx = idx;
	for (k = 0; k < 2; k = k + 1)
	{
		p = [pos_x + k * (BSW_W + 2), pos_y];
		id = strcat(k ? "cs_bcss" : "cs_bmom", ftos(idx));
		lbl = k ? "CS:S" : "MOM";
		sui_action_element(p, [BSW_W, BSW_H], id, sui_noop);
		hov = sui_is_hovered(id);
		sui_roundbox(p, [BSW_W, BSW_H], 5,
		             (k == css) ? COL_ACCENT : (hov ? COL_ROW_HOVER : COL_ROW), 1);
		sui_text([p_x + (BSW_W - stringwidth(lbl, TRUE, BSW_SZ)) * 0.5, p_y + 3], BSW_SZ,
		         lbl, (k == css) ? SUI_THEME_WELL : COL_DIM, 1, 0);
		if (bufstr_get(ms_enabled, k ? stof(bufstr_get(ms_var, row)) : row) == "0")
		{
			sui_text([p_x + 2, p_y + 3], BSW_SZ, "off", COL_DIM, 1, 0);
			continue;
		}
		if (hov)
			sui_tooltip_for(id, k ? "Play KSF's Counter-Strike: Source build of this map."
			                      : "Play Momentum Mod's build of this map.", 2);
		if (sui_is_released(id))
		{
			ms_selected = row;
			if (k != css)
				ui_pick_set(row, k);
		}
	}
	return 2 * BSW_W + 2 + 10;
};

// m_lobby.qc's Mdl_Reply saved a new list: read it, and keep what was picked.
void() ui_maplist_changed =
{
	local string keep;
	local float i;

	if (ms_name < 0 || !ms_count)
		return;                     // never loaded: the next open reads the new file
	keep = "";
	if (ms_selected >= 0 && ms_selected < ms_count)
		keep = strzone(bufstr_get(ms_name, ms_selected));
	ui_load_maps();
	ui_refilter();
	// Each lobby's cached row was an index into the old list.
	for (i = 0; i < Lob_Count(); i = i + 1)
		Lob_SetRow(i, -2);
	ms_selected = -1;
	if (keep != "")
	{
		for (i = 0; i < ms_count; i = i + 1)
			if (bufstr_get(ms_name, i) == keep)
				ms_selected = i;
		strunzone(keep);
	}
	ms_bgfor = -2;
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

// ROADMAP 10: the "show all" chip, applied and saved the same way.
void(float on) ui_showall_set =
{
	ms_showall = on;
	localcmd(sprintf("seta ui_maps_showall %g\n", on));
};

// P1080: the completed sort, saved the same way.
void(float mode) ui_compsort_set =
{
	ms_compsort = mode;
	localcmd(sprintf("seta ui_maps_compsort %g\n", mode));
};

// `ui_compsort`: the view as sorted. The counts say whether "ascending" had
// more than one bucket to order.
void() ui_compsort_print =
{
	local float i, r, row, prev, bad, d, nc, ni, nu;
	prev = -1; bad = -1; nc = ni = nu = 0;
	for (i = 0; i < ms_viewcount; i++)
	{
		row = stof(bufstr_get(ms_view, i));
		r = ui_sort_rank(row);
		if (r < prev && bad < 0) bad = i;
		prev = r;
		d = MCard_Done(bufstr_get(ms_name, ui_eff(row)));
		if (d > 0) nc++; else if (d == 0) ni++; else nu++;
	}
	row = ms_viewcount ? stof(bufstr_get(ms_view, 0)) : -1;
	print(sprintf("ui_compsort: mode %g view %g order %s complete %g incomplete %g unknown %g\n",
	              ms_compsort, ms_viewcount, (bad < 0) ? "ascending" : sprintf("BROKEN at %g", bad),
	              nc, ni, nu));
	print(sprintf("ui_compsort: first %s done %g scroll %g\n", (row >= 0) ? bufstr_get(ms_name, row) : "-",
	              (row >= 0) ? MCard_Done(bufstr_get(ms_name, ui_eff(row))) : -2, ms_scroll_y));
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
	MF_Open();
	registercvar("ui_maps_modes", ftos(FS_MODES_DEFAULT), 32);
	ms_modes = ui_modes_sane(cvar("ui_maps_modes"));
	registercvar("ui_maps_showall", "0", 32);       // ROADMAP 10, same rules
	ms_showall = (cvar("ui_maps_showall") != 0);
	registercvar("ui_maps_compsort", "0", 32);      // P1080, same rules
	ms_compsort = bound(0, rint(cvar("ui_maps_compsort")), 2);

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

/*
  Start the map here, on a listen server.  The original body of ui_launch,
  split out because build 67 gave it a second caller: the fallback when the
  directory cannot put us on a real server.  Nothing about it changed.
*/
void(string mapname) ui_launch_local =
{
	Mzd_Play(mapname);
};

void(string mapname) ui_playlocal_now =
{
	// The name field went in build 57 (Lex).  This is a private, unlisted
	// practice game, so a name had nowhere to be read.  Still SET rather than
	// left alone, because the engine's own default is "unnamed".
	cvar_set("hostname", "World of Surf");

	localcmd("sv_public 0\n");
	localcmd("deathmatch 1\n");
	localcmd("maxclients 2\n");
	localcmd("coop 0\n");
	// P815: this game reads the curated copy Mzd_Play just refreshed (sv_zones.qc).
	localcmd("set sv_zones_curated 1\n");
	localcmd(sprintf("map %S\n", mapname));

	// The search that found this map has done its job.  Arm the field to select
	// itself the next time it is clicked -- not now, because ms_selected stays
	// and the box draws the selection right-aligned beside the query.
	ms_query_stale = TRUE;

	m_close();
};

/*
===========================================================================
  PLAY IT ON A REAL SERVER IF THERE IS ONE.  Build 67.

  THE PROBLEM, WHICH IS THE PLAN'S LAYER 0 AND NOT A NICETY.  Every map started
  from this screen has been a LISTEN server, and on a listen server the host
  owns sv.time, the movement cvars, the progs and the timer -- so beating a
  world record there is a cvar edit, not a cheat.  sv_lobby.qc already knows
  this and refuses to submit those runs: `board "local"`, times stay on this
  machine, and the leaderboard never hears about them.  Which means the honest
  summary of the game before this change is that THE ONLY RUNS THAT COUNT ARE
  THE ONES SET ON THE THREE-OR-SO MAPS THE FIVE LOBBIES HAPPENED TO BE ON.

  Asking the directory first is what makes the other 528 timeable maps count.

  IT IS A TRY, NOT A REQUIREMENT, AND THAT IS DELIBERATE.  Every failure here
  falls through to the local map: no directory configured, consent not given at
  the online tier, the Pi down, every server busy, the map not installed there,
  a malformed or untrusted address, or simply no answer in LJ_DEADLINE.  The
  offline game is not a degraded mode to apologise for -- it is the game as it
  shipped and it must keep working on a train.  What the fallback owes the
  player is a SENTENCE, because "your time did not go up" with no explanation
  is the exact report that made Lobby_BoardState exist.

  WHY IT NEEDS A TICK AT ALL.  uri_get is asynchronous, so the answer arrives
  several frames after the button.  The alternative -- blocking -- is not
  available in QuakeC and would be wrong if it were.  So the press starts an
  ask and ui_join_tick finishes it, which is the same two-phase shape
  cl_scores.qc's rec_sb_wantrep uses for the replay click, and it has the same
  hazard: an answer that arrives after the player has changed their mind must
  not act.  ui_join_pending is that intent, and ESC clears it.
===========================================================================
*/
// The intent itself lives here, above ui_launch which sets it.  The two
// functions that ACT on it are further down, immediately above ui_connect,
// because they need ui_addr_ok and ui_host_allowed and QuakeC has no forward
// references -- the same reason Lobby_Heartbeat sits where it does in
// sv_lobby.qc rather than beside its caller.
float ui_join_pending;

/*
  ROADMAP 1: the status strip's last outcome, held for ST_HOLD seconds after the
  thing itself is over, and the pulse it gives the PLAY station.  m_milk.qc's
  MM_Camera reads ui_charge_on/ui_charge (set by ui_status_update every frame)
  and ui_pulse: +1 a completion, -1 a failure, at ui_pulse_t0 (gettime(0)).
*/
#define ST_HOLD 6
string ui_st_msg;               // strzoned; "" none
float  ui_st_msgok;             // 1 good, -1 bad, 0 neither
float  ui_st_msgat, ui_st_msguntil;     // time
float  ui_charge_on, ui_charge;
float  ui_pulse, ui_pulse_t0;

void(float kind) ui_st_pulse =
{
	ui_pulse = kind;
	ui_pulse_t0 = gettime(0);
};

void(string msg, float ok) ui_st_result =
{
	if (ui_st_msg)
		strunzone(ui_st_msg);
	ui_st_msg = strzone(msg);
	ui_st_msgok = ok;
	ui_st_msgat = time;
	ui_st_msguntil = time + ST_HOLD;
	if (ok)
		ui_st_pulse(ok);
};

/*
  ---------------------------------------------------------------------------
   The pre-join map check: fetch the server's build BEFORE connecting.
  ---------------------------------------------------------------------------

  Lex, kicked from a lobby on surf_rookie: "can it just download the latest to
  the game directory automatically when connecting to a public lobby and there's
  a disagreement on map files".

  WHY THIS IS THE RIGHT PLACE and not a reaction to the kick.  The kick happens
  at prespawn -- the server compares the client's BSP checksum against its own
  (sv_user.c:2305-2320) and drops the client -- so by the time anything is known
  the connection is gone.  Here we have not connected yet, and data/mapdl.txt is
  an inventory OF THE PI, so the size in it IS the build the lobby will serve.

  WHAT IT CAN AND CANNOT SEE, stated because the difference bit us the same day:
  ms_have is "0" when the map is missing and "2" when its size differs, and both
  are repaired here.  Two builds of the SAME SIZE are indistinguishable to it --
  measured: the Pi's surf_rookie and this workstation's are byte-identical, so a
  laptop that disagrees with both is a third build this check may or may not see.
  Closing that needs the server's own answer, which is the `//kickfile` stufftext
  the engine currently only prints.

  The connect is PARKED rather than issued, and the menu stays open so the row's
  own progress bar is the progress bar.  A failed fetch does NOT connect: joining
  with a map we already know is wrong is the thing this exists to stop.
*/
string pj_addr;         // the connect being held, "" when nothing is held
string pj_map;
float  pj_until;        // gettime(0) to give up at

// Defined below ui_dl_start, which they drive; these are the prototypes,
// the way m_close and Lob_Poll are declared ahead of their definitions.
float(string addr, string mapname) ui_prejoin;
void() ui_prejoin_tick;
float() ui_join_busy;           // ROADMAP 1, beside the status strip

/*
  ui_play_online, READ THROUGH ONE FUNCTION -- build 70, and it is a bug fix.

  The essay in ui_launch below is right about the trap and was defeated by a
  SECOND reader 2,500 lines away: `ui_join`'s status report printed
  cvar("ui_play_online") with no registercvar beside it.  So running the
  DIAGNOSTIC before ever pressing Start auto-created the cvar as "", ui_launch's
  registercvar then declined to overwrite it, and online play was off for the
  rest of that session -- silently, and with the report itself cheerfully
  displaying the 0 it had just caused.  Measured, not reasoned about: a live run
  logged `Created QC Cvar ui_play_online` on the report line and
  `ui_play_online 0` in the same breath, on an install that had never opted out.

  A tool that breaks what it measures is worse than no tool, and "remember to
  register beside every read" is the instruction that has now failed four times
  in this tree.  So there is one reader and the registration is inside it.  New
  callers get it right by having nowhere else to go.
*/
float() ui_online_opt =
{
	registercvar("ui_play_online", "1", 0);
	return cvar("ui_play_online");
};

/*
===========================================================================
  THE NAME GATE.  Patch 340.

  Twelve "Player"s on one lobby scoreboard is not a cosmetic problem: chat
  cannot be attributed, the player list cannot be read, and every default
  name looks like every other.  So ui_launch refuses to start or join while
  the engine's `name` cvar still holds a factory default, and SCREEN_NAME
  asks for a real one first.  The screen is drawn below, beside screen_terms;
  the TEST lives here because ui_launch is the single launch choke point and
  QuakeC has no forward references.

  WHAT COUNTS AS DEFAULT, and the list is the engine's own shapes rather than
  a guess: "Player" is the literal default (cl_main.c:174, capital P), and
  the QW collision rename wraps it as "(1)Player", "(2)Player" -- so the test
  strips a "(digits)" prefix, strips whitespace, lowercases, and compares
  against {"", "player", "unnamed", "quake"}.  A name of "player!!" is a name
  somebody chose; a name of "(3)PLAYER" is a name nobody chose.
===========================================================================
*/
string ui_name_field;           // what the field holds, strzone-free: sui owns it
float  ui_name_caret;
string ui_name_err;
float  ui_name_back;            // the screen to return to on cancel
float  ui_launch_maxfog;        // retained only across this launch's name gate
float  ui_name_resume;          // 1 = ui_launch, 2 = ui_connect(ui_name_arg)
float  ui_name_arg;

#define UI_NAME_MAX 15          // the scoreboard's own limit; longer truncates

/*
  Strip one "(digits)" prefix, whitespace on both ends, and lowercase.  Pure
  string arithmetic with str2chr: no regexes in QC and no engine helper that
  does this shape.
*/
string(string s) ui_name_norm =
{
	local float n, c, d;

	s = strtolower(s);

	// "(1)player" -> "player"
	if (strlen(s) > 2 && str2chr(s, 0) == 40)      // '('
	{
		d = strstrofs(s, ")", 0);
		if (d > 0 && d < 8)                        // a sane collision counter
			s = substring(s, d + 1, strlen(s));
	}

	// trim
	while (strlen(s) > 0 && (str2chr(s, 0) == 32 || str2chr(s, 0) == 9))
		s = substring(s, 1, strlen(s));
	n = strlen(s);
	while (n > 0 && ((c = str2chr(s, n - 1)) == 32 || c == 9))
	{
		s = substring(s, 0, n - 1);
		n = n - 1;
	}

	return s;
};

float(string s) ui_name_default =
{
	s = ui_name_norm(s);
	if (s == "")          return TRUE;
	if (s == "player")    return TRUE;
	if (s == "unnamed")   return TRUE;
	if (s == "quake")     return TRUE;
	return FALSE;
};

/*
  The gate itself, called from ui_launch.  TRUE means "the name screen is now
  up and the launch must stop".  ui_bootcheck walks straight through: it is
  the headless developer surface, and a name dialog no script can answer
  would deadlock every bootcheck run ever taken.
*/
float ui_name_skip;     // Patch 647: one connect goes through as it is (ui_steam_go)
float(float resume, float arg) ui_name_gate =
{
	if (cvar("ui_bootcheck"))
		return FALSE;
	if (ui_name_skip)
	{
		ui_name_skip = FALSE;
		return FALSE;
	}
	if (!ui_name_default(cvar_string("name")))
		return FALSE;

	ui_name_back   = menu_screen;
	ui_name_field  = "";
	ui_name_caret  = 0;
	ui_name_err    = "";
	ui_name_resume = resume;
	ui_name_arg    = arg;
	menu_screen    = SCREEN_NAME;
	return TRUE;
};

/*
  Validate and take the name.  Returns "" on success, or the sentence to show
  on the screen.  cvar_set and NOT `localcmd("name ...")`: name is
  CVAR_USERINFO, so setting the cvar updates userinfo for the connect that
  follows, and there is no console-parse of a stranger-proof string to get
  wrong.  Colour codes are deliberately ALLOWED -- ^1lex is a name somebody
  chose, and the chat colour rule (engine CL_PlayerColor / our tc key) already
  yields to codes in the name.
*/
string(string s) ui_name_take =
{
	local float i, n, c;

	// trim, then judge
	s = ui_name_norm(s);
	n = strlen(s);

	if (n == 0)
		return "type a name first";
	if (n > UI_NAME_MAX)
		return sprintf("keep it to %g characters -- longer is cut off everywhere it is shown", UI_NAME_MAX);

	// no control characters, ever: a name goes into chat lines, filenames
	// and the console, and a newline in any of those is an injection.
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (c < 32 || c == 127)
			return "no control characters";
	}

	if (ui_name_default(s))
		return "that is still the default -- pick a name of your own";

	cvar_set("name", s);
	return "";
};

void(string target) ui_eventfog_target =
{
	local float serial;

	registercvar("fs_eventfog_map", "", 0);
	registercvar("fs_eventfog_until", "0", 0);
	registercvar("fs_eventfog_serial", "0", 0);
	cvar_set("fs_eventfog_map", target);
	cvar_set("fs_eventfog_until", "0");
	if (!strlen(target)) return;
	serial = cvar("fs_eventfog_serial") + 1;
	if (serial > 1000000) serial = 1;
	cvar_set("fs_eventfog_serial", ftos(serial));
	cvar_set("fs_eventfog_until", ftos(gettime(0) + 300));
};

void(float eventmax) ui_launch_mode =
{
	string mapname = ui_selected_name();
	if (mapname == "")
		return;

	// ROADMAP 1: one join at a time; the status strip's cancel (or ESC) ends it.
	// The start button and the rows' Play come through here; a lobby cell is
	// ui_connect, which has its own rule.
	if (ui_join_busy())
		return;
	ui_launch_maxfog = eventmax;
	ui_launch_plain = ui_plain_only;

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

	/*
	  PATCH 340: the name gate, and it sits in the SAME choke point as the
	  consent gate for the same reason -- every launch route (start button,
	  bootcheck, the ui_join twin's fallback) comes through here, so there is
	  no refactor that walks past it.  Continuing after the screen closes is
	  screen_name's job: its continue button calls ui_launch again, which
	  re-runs this gate and passes.
	*/
	if (ui_name_gate(1, 0))
		return;

	/*
	  REGISTERED BESIDE THE READ, not in m_init, and this tree has lost three
	  features to getting that backwards: cvar() on an unregistered name
	  AUTO-CREATES it as "" and a later registercvar() then declines to
	  overwrite it, so a non-zero default registered anywhere that can be
	  reached second never lands.  Here that would mean online play silently
	  defaulting OFF.

	  WHY IT EXISTS.  Online is the default because a run that cannot be
	  submitted is most of this game's point, but a player practising a trick a
	  hundred times does not want a lobby, a stranger watching, or a round trip
	  before every attempt.  `ui_play_online 0` is that, and it is a preference
	  rather than a consent gate -- the consent gate is rec_terms and it is
	  checked separately, inside Lob_JoinAsk.
	*/
	// Only a data-marked Story Play passes eventmax. Ordinary launches clear
	// earlier requests, including another attempt on the exact same map.
	ui_eventfog_target(eventmax ? mapname : "");
	if (ui_online_opt())
	if (Lob_JoinAsk(mapname))
	{
		/*
		  The answer is several frames away, so the menu STAYS OPEN and
		  ui_join_tick finishes the job.  Not closing is what makes the wait
		  legible: the screen the player pressed the button on is still there,
		  the button reads as busy, and ESC cancels.
		*/
		ui_join_pending = TRUE;
		print(sprintf("^5online:^7 asking %s for a server on %s...\n",
		              cvar_string("lobby_dir"), mapname));
		return;
	}

	ui_launch_local(mapname);
};

void() ui_launch = { ui_launch_mode(FALSE); };

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

	// tokenize() clobbers argv globally. Its callers (ui_connect, the join
	// tick, ui_steam_pick) do not read argv afterwards; ui_para tokenizes its
	// own text after any of them.
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
  what the in-game arm of cfg/test/b66who.cfg is for.
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

/*
  The two halves of the deferred launch, placed HERE rather than beside
  ui_launch because they call ui_addr_ok and ui_host_allowed, which are defined
  above this point and below that one.  See the essay over ui_launch_local for
  what they are for.
*/
void() ui_join_cancel =
{
	if (!ui_join_pending)
		return;
	ui_eventfog_target("");
	ui_join_pending = FALSE;
	Lob_JoinClear();
};

void() ui_join_tick =
{
	local string addr, mapname;
	local float  st;

	if (!ui_join_pending)
		return;

	Lob_JoinPoll();                 // may time the ask out
	st = Lob_JoinState();
	if (st == LJ_ASK || st == LJ_WAIT)
		return;                     // still waiting; the button stays busy

	ui_join_pending = FALSE;
	addr    = Lob_JoinAddr();
	mapname = Lob_JoinMap();

	if (st == LJ_READY)
	if (ui_addr_ok(addr))
	if (ui_host_allowed(addr))
	{
		/*
		  The same two gates ui_connect applies to a lobby picked by hand, and
		  for the same reason: this address came off the network from whoever
		  answers lobby_dir, and it is about to go to localcmd, which is the
		  console.  A directory that is compromised, substituted or typo'd into
		  a hostile host is the threat, and it does not become less of one
		  because the player pressed Start rather than Join.
		*/
		if (!Lob_JoinTimed())
			print(sprintf("^3online:^7 %s has no zone file, so nothing on it "
			              "can be timed -- you are playing, not racing.\n",
			              mapname));
		print(sprintf("^5online:^7 joining %s for %s (%s)\n",
		              addr, mapname, Lob_JoinWhy()));
		// Seen only when the connect is held below: a direct one closes the menu.
		ui_st_pulse(1);
		// Lob_JoinClear frees the strings addr and mapname point at, so it
		// has to come after ui_prejoin has strzoned its own copies of both.
		if (ui_prejoin(addr, mapname))
		{
			Lob_JoinClear();
			return;
		}

		localcmd(sprintf("connect %S\n", addr));
		ms_query_stale = TRUE;
		Lob_JoinClear();
		m_close();
		return;
	}

	/*
	  EVERY OTHER OUTCOME PLAYS LOCALLY AND SAYS WHY.  Three shapes of refusal
	  reach here and they are deliberately not collapsed: the directory said no
	  (and its own sentence is the useful part), the directory said yes but to
	  somewhere this build will not connect, or nothing answered at all.
	*/
	if (st == LJ_READY)
	{
		print(sprintf("^1online:^7 the directory offered %S, which this build "
		              "will not connect to -- playing locally instead.\n", addr));
		ui_st_result("No lobby: the directory offered a server this build will "
		             "not join -- playing locally", -1);
	}
	else
	{
		print(sprintf("^3online:^7 %s -- playing locally, so this run will not "
		              "reach the leaderboard.\n", Lob_JoinWhy()));
		ui_st_result(sprintf("No lobby: %s -- playing locally", Lob_JoinWhy()), -1);
	}

	// The string is read BEFORE the clear that frees it, which is the ordering
	// cl_scores.qc's hand-off had to get right for the same reason: mapname
	// points into m_lobby.qc's strzone.
	ui_launch_local(mapname);
	Lob_JoinClear();
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

	// Patch 340: the name gate, for the ui_launch reason -- this is the OTHER
	// door onto a public lobby, and it is the door where being called
	// "Player" matters most.  Resume 2 re-enters HERE with the same row.
	if (ui_name_gate(2, i))
		return;

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
	// ROADMAP 1: a lobby picked by hand replaces a directory ask in flight, but
	// not a connect already held for a download -- ui_prejoin holds one only,
	// and an ask's local fallback would leave that one to connect later.
	// After the address checks, so a refused click leaves the ask alone.
	ui_eventfog_target("");
	ui_join_cancel();
	if (ui_join_busy())
		return;

	// The map first, when we can see it is missing or the wrong build.
	// TRUE means the fetch owns the connect and ui_prejoin_tick issues it.
	if (ui_prejoin(addr, Lob_Map(i)))
		return;

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
	{
		print(sprintf("bootcheck: layout panel %gx%g  lcols %g  lshow %g  rows %g\n",
		              ui_cs_size_x, ui_cs_size_y, ui_cs_lcols, ui_cs_lshow, ui_cs_rows));
		localcmd("screenshot ui_menu_lobbyrow\n");
	}
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
		/*
		  BUILD 86: `say`, NOT `cmd say`, and the two with a NUMBER are why.

		  SV_ParseClientCommand reads the whole message out of argv(1) and splits it
		  on the first space itself (sv_player.qc:1030-1042), so the message has to
		  arrive as ONE argument.  `cmd say !s 2` forwards it as two -- argv(1) is
		  "!s" and the tail is empty -- so stof("") made it stage 0 and this
		  self-test has been proving `!s 2` works by running `!s` with no number.
		  `!b 1` was bonus 0 the same way.  b48d.cfg:5-6 records the same trap from
		  the harness side ("the cmd route drops the stage number").

		  Plain `say` is the route that quotes: CL_Say wraps the whole message in the
		  one pair SV_Say strips, so the number survives.  It reaches CSQC's chat
		  hook first, which declines anything with text (cl_chat.qc CSQC_ChatSay) --
		  before build 86 that hook swallowed these into the typing line instead,
		  which is the bug that made `bind r "say !r"` dead.
		*/
		localcmd("say !s 2\nsay !b 1\nsay !r\nsay !m\n");
		// ...and two that must NOT be intercepted.  A prefix match would read
		// "!rank" as "!r" and teleport instead of talking, which is the kind of
		// thing nobody finds until they type it in front of someone.
		localcmd("say !rank\nsay hello\n");
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

  m_draw owns one full-screen pass before any shell frame. Screens must not
  paint panel-sized backdrops: those leak square corners and compound opacity.
  A live map remains behind the menu; Milk stays disconnected-only.
*/
void(vector screensize) ui_backdrop =
{
	if (MM_Active())
	{
		MM_Backdrop(screensize);
		return;
	}
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

/*
  THE BACKDROP EVERY MAP HAS: its own atlas thumbnail, blown up and blurred.

  gfx/mapshots is 269 MB at 1280x720 and 876 MB at 1920x1080 against a 33 MB
  installer, which is why no release has ever carried one and why this screen
  had nothing to draw for anybody who does not also own Momentum.  gfx/mapthumbs
  DOES ship -- six 2048x2048 atlases, 28 MB, one 128x72 cell per map -- and the
  rows beside this already draw from it.  So the picture was distributed all
  along, at 1/225th of the pixels.

  128x72 to 1920x1080 is a 15x upscale and bilinear at 15x does not read as a
  photograph, it reads as a grid of soft squares.  A gaussian on top removes the
  frequency that grid lives at, and what is left reads as a deliberately
  defocused still rather than as a broken texture.  Zero distributed bytes.

  NINE TAPS, 3x3, offsets in SOURCE TEXELS so the blur is the same strength at
  every resolution.  Weights are the separable {1,2,1} kernel, and tap i is
  composited at alpha w_i / (w_0 + .. + w_i), which makes the running result the
  exact weighted average rather than nine layers of paint: out = out*(1-a) + c*a
  with a = w_i/W_i telescopes to sum(w*c)/W.  The first tap therefore draws
  opaque, which is what establishes the base.

  drawsubpic is also the safer builtin here: unlike drawpic it has no
  R2D_SafeCachePic("no_texture") substitution (pr_menu.c:688-712 against
  :622-632), so a missing atlas draws nothing rather than an error texture.
*/
#define BG_BLUR_TEXELS  1.5

void(vector screensize, float page, float cell) ui_bgatlas =
{
	local vector sp, ss, base, sz;
	local float col, row, d, i, gx, gy, w, acc, scale;
	local string pic;

	if (page < 0 || cell < 0)
		return;

	col = cell - floor(cell / THUMB_COLS) * THUMB_COLS;
	row = floor(cell / THUMB_COLS);

	// HALF A TEXEL IN FROM EVERY EDGE.  At this magnification bilinear reaches
	// into the neighbouring cell, and an atlas neighbour is a different map --
	// so without the inset a thin band of some unrelated surf map runs down the
	// side of the screen.
	sp = [(col * THUMB_W + 0.5) / ATLAS_PX, (row * THUMB_H + 0.5) / ATLAS_PX, 0];
	ss = [(THUMB_W - 1) / ATLAS_PX, (THUMB_H - 1) / ATLAS_PX, 0];
	pic = strcat("gfx/mapthumbs/atlas", ftos(page));
	if (page >= MMM_VPAGE)
	{
		sp = '0 0 0';
		ss = '1 1 0';
		pic = Mmm_UrlFor(page);
	}

	// Cover, not fit -- the same rule and the same reason as the full-size path
	// below -- then grow by the blur offset so no shifted tap can pull an empty
	// edge into view.
	scale = screensize_x / 1920;
	if (screensize_y / 1080 > scale)
		scale = screensize_y / 1080;
	sz = [1920 * scale, 1080 * scale, 0];

	d = (sz_x / THUMB_W) * BG_BLUR_TEXELS;      // one texel, in screen pixels
	sz = sz + [d * 2, d * 2, 0];
	base = [floor((screensize_x - sz_x) * 0.5),
	        floor((screensize_y - sz_y) * 0.5), 0];

	acc = 0;
	for (i = 0; i < 9; i = i + 1)
	{
		gx = (i - floor(i / 3) * 3) - 1;        // -1, 0, 1
		gy = floor(i / 3) - 1;
		w  = (2 - fabs(gx)) * (2 - fabs(gy));   // {1,2,1} x {1,2,1}, sums to 16
		acc = acc + w;
		// FULL BRIGHTNESS, unlike the full-size path's 0.7 dim, and the caller
		// washes this one lighter too.  Measured, not guessed: at the sharp
		// path's 0.7 tint and 0.4 wash the top-left 500x300 of the frame came
		// out at mean luma 9.7 of 255 -- a backdrop nobody can see is not a
		// backdrop.  A blur that has already destroyed every edge cannot
		// compete with panel text the way a sharp photograph can, so the
		// dimming the sharp path needs is dimming this one only pays for.
		sui_subpic([base_x + gx * d, base_y + gy * d], sz,
		           pic,
		           sp, ss, '1 1 1', w / acc, 0);
	}
};

float(string uuid) ui_bguuid =
{
	local float i;
	local string c;
	if (strlen(uuid) != 36) return FALSE;
	for (i = 0; i < 36; i = i + 1)
	{
		c = substring(uuid, i, 1);
		if (i == 8 || i == 13 || i == 18 || i == 23)
		{
			if (strcmp(c, "-") != 0) return FALSE;
		}
		else if (strstrofs("0123456789abcdef", c) < 0) return FALSE;
	}
	return TRUE;
};

void(vector screensize) ui_map_backdrop =
{
	local string uuid, want;
	local vector ready;

	// Keep the live world behind every tab; photos are disconnected fallbacks.
	if (clientstate() == 2) return;
	if (MM_Active()) return;       // caller already drew the shared scene

	if (ms_selected != ms_bgfor)
	{
		if (ms_bgpic != "")
		{
			free_pic(ms_bgpic);
			strunzone(ms_bgpic);
			ms_bgpic = "";
		}
		ms_bgfor = ms_selected;
		ms_bgremote = FALSE;

		uuid = "";
		ms_bgpage = ms_bgcell = -1;
		if (ms_selected >= 0)
			if (ms_selected < ms_count)
				if (tokenize(bufstr_get(ms_meta, ms_selected)) > MT_UUID)
				{
					uuid = argv(MT_UUID);
					// The same row the thumbnail is drawn from, read here so the
					// atlas fallback below costs no second tokenize per frame.
					ms_bgpage = (argv(MT_PAGE) == "-") ? -1 : stof(argv(MT_PAGE));
					ms_bgcell = (argv(MT_CELL) == "-") ? -1 : stof(argv(MT_CELL));
				}

		want = "";
		if (strlen(uuid) && strcmp(uuid, "-") != 0)
		{
			// NO BLIND LAST RESORT.  What stood here asked for
			// _cache/images/<uuid>-large.jpg after ui_bgprobe had already
			// established no such file was readable, on the stated grounds that
			// "drawpic no-ops on a miss, so the cost of being wrong is a flat
			// backdrop".  THAT IS NOT WHAT drawpic DOES.  PF_CL_drawpic,
			// pr_menu.c:622-632:
			//
			//     p = R2D_SafeCachePic(picname);
			//     if (!p || !R_GetShaderSizes(p, NULL, NULL, false))
			//         p = R2D_SafePicFromWad(picname);
			//     if (!p) {
			//         if (!CL_IsDownloading(picname))
			//             p = R2D_SafeCachePic("no_texture");
			//         G_FLOAT(OFS_RETURN) = 0;
			//     }
			//     ...
			//     R2D_Image(... p);       // drawn on every path
			//
			// It returns 0 AND substitutes no_texture, then draws it.  So on
			// every install that has neither gfx/mapshots nor a Momentum
			// _cache -- which is every shipped install, since release.ps1
			// carries neither -- this painted a full-screen error texture
			// behind the panel.  Reported as "we don't distribute them and
			// show as error".
			//
			// The CL_IsDownloading test is why a download in flight shows
			// nothing: "don't draw it until it has arrived" already exists in
			// the engine, just not for a file that is never arriving.
			//
			// precache_pic is NOT implicated -- PF_CL_precache_pic (:820-861)
			// only calls R2D_SafeCachePic and never draws -- so the fault was
			// the draw, and the fix is to keep an unverified path out of
			// ms_bgpic rather than to stop precaching one.
			want = ui_bgpick(uuid, screensize_x);
		}
		// A bundled medium is a thumbnail, not a full-screen backdrop. Keep
		// it offline/on old engines; online, prefer the bounded R2 derivative.
		if (ms_consent >= FS_TERMS_ONLINE)
		if (checkbuiltin(drawgetimagesize_async))
		if (strcmp(substring(want, strlen(want) - 11, 11), "-medium.jpg") == 0) want = "";
		if (!strlen(want) && ms_consent >= FS_TERMS_ONLINE)
		if (checkbuiltin(drawgetimagesize_async))
		if (ms_selected >= 0 && ms_selected < ms_count)
		{
			if (ui_bguuid(uuid))
				want = strcat("https://dl.proto.bar/ftesurf/mapshots/", uuid, "-bg.jpg");
			else if (Mdl_Made(bufstr_get(ms_name, ms_selected), MDL_NAMECH, 64))
				want = strcat("https://dl.proto.bar/ftesurf/mapshots/", bufstr_get(ms_name, ms_selected), ".jpg");
			if (strlen(want)) ms_bgremote = TRUE;
		}
		if (strlen(want))
		{
			ms_bgpic = strzone(want);
			precache_pic(ms_bgpic, 0);
		}
	}

	// The selector is a photo backdrop; other screens retain the 3D space.
	if (MM_Active() && menu_screen != SCREEN_CREATE) return;
	ready = '1 1 0';
	if (ms_bgremote && strlen(ms_bgpic))
		ready = drawgetimagesize_async(ms_bgpic);
	if (!strlen(ms_bgpic) || ready_x <= 0 || ready_y <= 0)
	{
		// No full-size image on this machine, which is the normal case. Draw
		// the thumbnail we DID ship, blurred, and then the same wash -- so the
		// screen looks the same shape either way and only the sharpness says
		// which one you got.
		if (ms_bgpage >= 0)
		{
			ui_bgatlas(screensize, ms_bgpage, ms_bgcell);
			sui_fill('0 0 0', screensize, '0.02 0.02 0.03', 0.25, 0);
		}
		return;
	}

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
  A paragraph wrapped to `w` px.  Returns its height; with `draw` FALSE it only
  measures, so a panel can be sized from its text before anything is drawn.
  The lines are gathered and then drawn: argv is tokenize's, not ours to hold
  across other calls.
*/
#define UI_PARA_MAX 12
string ui_para_ln[UI_PARA_MAX];
float(vector pos, float w, vector sz, float pitch, string text, vector col, float draw) ui_para =
{
	local float n, i, k;
	local string line, next;

	n = tokenizebyseparator(text, " ");
	line = "";
	k = 0;
	for (i = 0; i < n; i = i + 1)
	{
		next = (line == "") ? argv(i) : strcat(line, " ", argv(i));
		if (line != "")
		if (k < UI_PARA_MAX - 1)
		if (stringwidth(next, TRUE, sz) > w)
		{
			ui_para_ln[k] = line;
			k = k + 1;
			next = argv(i);
		}
		line = next;
	}
	if (line != "")
	{
		ui_para_ln[k] = line;
		k = k + 1;
	}
	if (draw)
		for (i = 0; i < k; i = i + 1)
			sui_text([pos_x, pos_y + i * pitch], sz, ui_para_ln[i], col, 1, 0);
	return k * pitch;
};

// The two screens' text size.  16 px, or 12 where 16 does not fit the window:
// both are on the UI face's baked ladder (sh_font.qc); the first cut's 15 was
// drawn resampled, and at 15 the panel was 790 px tall in a 720 px window.
vector tm_sz;
float  tm_pitch;
void(float big) ui_tm_size =
{
	tm_sz    = big ? '16 16 0' : '12 12 0';
	tm_pitch = big ? 20 : 15;
};

#define TM_GAP    7             // under a paragraph
#define TM_HEAD   10            // over a heading that is not a column's first

float tm_y;                     // how far down its column the text has got

void(vector p, float draw, string h) ui_tm_head =
{
	if (tm_y > 0)
		tm_y = tm_y + TM_HEAD;
	if (draw)
		sui_text([p_x, p_y + tm_y], tm_sz, h, COL_ACCENT, 1, 0);
	tm_y = tm_y + tm_pitch + 3;
};

void(vector p, float w, float draw, string t, vector col) ui_tm_par =
{
	tm_y = tm_y + ui_para([p_x, p_y + tm_y], w, tm_sz, tm_pitch, t, col, draw) + TM_GAP;
};

void(vector p, float w, float draw, string t) ui_tm_dot =
{
	if (draw)
		sui_roundbox([p_x + 3, p_y + tm_y + floor(tm_pitch * 0.5) - 3], '4 4 0', 2, SUI_THEME_MUTED, 1);
	tm_y = tm_y + ui_para([p_x + 16, p_y + tm_y], w - 16, tm_sz, tm_pitch, t, COL_TEXT, draw) + 3;
};

/*
  THE TERMS (Patch 647: two columns of wrapped paragraphs; they were 35
  hand-broken lines).  Column 0 is the game on its own, column 1 what public
  lobbies add.  Returns the column's height; `draw` FALSE measures.

  The rule is the essay's over FS_TERMS_LINES: DISCLOSE ONLY WHAT THE SHIPPED
  CODE DOES TODAY.  What this cut changed, each because the code had:
    - "about 66 times a second": a bhop map ticks at 100 (sv_main.qc);
    - "under the name you are playing as": since Patches 629 and 638 a ranked
      time is filed under a linked Steam account, by its Steam name;
    - the Steam paragraphs: what a link stores (surfd's `accounts`, `keylinks`
      and `installs`) and shows (638 the name, 639 and 640 the picture, 636
      the profile link and the other games' records);
    - "the leaderboards and players' pictures": the game asks play.proto.bar
      for both (cl_online.qc, cl_steampic.qc), not for the map picker only.
  FS_TERMS_ONLINE is NOT bumped: nothing new leaves the machine of a player
  who does not link, and linking is its own act on its own page.
*/
float(float c, vector p, float w, float draw) ui_terms_col =
{
	tm_y = 0;
	if (c == 0)
	{
		ui_tm_head(p, draw, "What is recorded, while a run's clock is going");
		ui_tm_dot(p, w, draw, "your position, velocity and view angles, on every tick of the game's clock (66 or 100 a second)");
		ui_tm_dot(p, w, draw, "which movement keys you are holding, once per drawn frame");
		ui_tm_dot(p, w, draw, "a journal of raw mouse and keyboard events, with timings");
		ui_tm_head(p, draw, "Where it goes");
		ui_tm_par(p, w, draw, "Files under this game's own data folder, on this machine.", COL_TEXT);
		ui_tm_par(p, w, draw, "Playing on your own, nothing about a run leaves this machine: there is no upload.", SUI_THEME_GOOD);
		ui_tm_head(p, draw, "What it is for");
		ui_tm_par(p, w, draw, "Replaying your runs, and telling a real run from a scripted one.", COL_TEXT);
		ui_tm_head(p, draw, "What is never recorded");
		ui_tm_par(p, w, draw, "Anything you type. While the console or a menu has focus the journal keeps the timing of a keypress and drops which key it was, so a password typed in the console cannot end up in a file. Nothing outside this game's window is watched, ever.", COL_TEXT);
		ui_tm_head(p, draw, "Updates");
		ui_tm_par(p, w, draw, "Choosing Play online also turns on automatic updates: World of Surf checks proto.bar and downloads game-owned files from dl.proto.bar. Those services see your IP address; settings, recordings and mounted game assets are not uploaded. Play offline does not turn them on. F2's Updates page turns them off.", COL_TEXT);
		ui_tm_head(p, draw, "Turning it off");
		ui_tm_par(p, w, draw, "rec_hid 0 stops the raw input journal. Runs recorded without it are marked as such, rather than passing as runs that had one.", COL_TEXT);
	}
	else
	{
		ui_tm_head(p, draw, "What the other players get");
		ui_tm_par(p, w, draw, "The people on the map see your position and view angle, and you see theirs. Voice and text chat reach everyone there.", COL_TEXT);
		ui_tm_head(p, draw, "What is uploaded");
		ui_tm_par(p, w, draw, "Your finish time goes to play.proto.bar and appears on a public leaderboard. That server also keeps its own recording of the run (positions, velocities and angles), which anyone can download from the board.", SUI_THEME_WARN);
		ui_tm_par(p, w, draw, "Public server replays can also include limited pause-check timing and order, movement settings, physical state and clock snapshots. This adds no raw paused input to those replays and no new player or device identifiers. The same public downloads and replay retention apply.", SUI_THEME_WARN);
		ui_tm_par(p, w, draw, "Detailed pause-check records appear only for qualifying intervals. Their presence indicates the permitted movement/jump mode and absence of relevant use actions, unmodeled transitions and effects. Other intervals receive only a generic unsupported or incomplete result.", SUI_THEME_WARN);
		ui_tm_par(p, w, draw, "Your client's view-angle sidecar also goes to that server for anti-cheat review (rec_upload controls it). Choosing play online includes raw mouse and keyboard event journals, with timings, sent to play.proto.bar over HTTPS for private review, not public replays. Untick the journal box on the summary to opt out, or stop uploads later with F2. Stopping does not delete evidence already received.", COL_TEXT);
		ui_tm_par(p, w, draw, "With online features enabled, play.proto.bar refreshes the map list at startup and serves zones, leaderboards and player pictures. Selecting a map can fetch its backdrop from dl.proto.bar. These services see your IP address, as does any lobby you join.", COL_TEXT);
		ui_tm_par(p, w, draw, "A zone admin can upload saved zones to play.proto.bar. They are stored with the linked account and go live on the lobbies once none of them has the map loaded; existing times stay.", COL_TEXT);
		ui_tm_head(p, draw, "Steam");
		ui_tm_par(p, w, draw, "A ranked time needs a Steam account linked to this game. You sign in on Steam's own page in your browser; the game never sees your password. play.proto.bar keeps your Steam ID, name and profile picture and, for this install, the key and id that name it, where and when it was linked, and when and how often it sends ranked runs.", COL_TEXT);
		ui_tm_par(p, w, draw, "Once linked, your Steam name is your name on lobbies, and it and your picture are shown with your times, in the game and on proto.bar, where they link to your Steam profile and sit beside your Momentum Mod and KSF records.", COL_TEXT);
		ui_tm_par(p, w, draw, "Without a link your lobby times are still kept and shown, unranked, under this install's own id and the name you are playing as.", COL_TEXT);
		ui_tm_par(p, w, draw, "Opening Friends in the map picker asks play.proto.bar for your linked account's private friends list. This install's public signing key proves the account, without loading a map. Only lobby connections publish where you are playing; sitting in the menu does not make you joinable.", COL_TEXT);
	}
	return tm_y - TM_GAP;
};

/*
  The terms screen.  No "back", by design -- the only ways off it are an
  answer and quitting (P902: opened from F2, also a Back to it), because
  "later" is not a state this can be in: the very
  next thing the player does is load a map, and that is the thing being
  consented to.

  Patch 647 redrew it: one panel, two cards, sized FROM the wrapped text
  (measured, then drawn), three buttons.  What build 22 to 270 learned here
  still holds and is kept in the layout rather than in essays:
    - both answers are always drawn; "offline" is a real answer and is the
      first element, so it is the keyboard's default;
    - the buttons are ALWAYS on screen.  The text drops to 12 px where 16 does
      not fit; in a window too short even for that the buttons and the
      footnote sit on a strip of their own along the bottom edge (there is no
      ESC off this screen);
    - AN ANSWER IS THE PLAYER'S HAND.  `ui_key` and `ui_click` are console
      commands, and a console line can be somebody else's: for a moment after
      either the answers do nothing and say why;
    - taking the online answer goes on to the Steam offer (screen_steam).
  Patch 796 (Lex: "way too long ... make it shorter and sweet"): a first boot
  shows ui_terms_short; the two cards are behind "Full details".  The input
  journal upload, P774's separate consent, is a box here, not a menu button.
*/
#define TM_PAD   16             // P823: the Dusk panels' margin
#define TM_TOP   48             // under the 24 px heading at 12, as on the other panels
#define TM_CARD  16
#define TM_JBOX  34             // P796: the journal box's row and the gap under it
float ui_steam_t0;      // when the Steam offer went up: how long to wait for the lobby list
float ui_synth_t;       // when a helper last fed the menu an event; 0 never
float ui_synth_pending; // survives suspended drawing and held clicks
float ui_synth_aim;     // helper-selected focus needs real motion/navigation
float ui_tm_ph, ui_tm_w, ui_tm_two, ui_tm_sx, ui_tm_sy;     // the terms as last laid out, for ui_strip_test
float ui_tm_full;               // P796: the cards are up instead of the summary
float ui_tm_jbox, ui_tm_jtouched;   // P796: the journal box; the player changed it on this visit
float ui_tm_f2;                     // P902: opened from F2's Terms page; reset on leaving

float() ui_synth =
{
	if (ui_synth_pending || ui_synth_aim)
		return TRUE;
	if (ui_synth_t > 0)
	if (time - ui_synth_t < 1.5)
		return TRUE;
	return FALSE;
};

// P796: the summary.  It says nothing ui_terms_col does not.
float(vector p, float w, float draw) ui_terms_short =
{
	tm_y = 0;
	ui_tm_dot(p, w, draw, "Each run is recorded on this PC: your position, speed and view, and your mouse and keyboard input.");
	ui_tm_dot(p, w, draw, "Offline, nothing about a run leaves your PC.");
	ui_tm_dot(p, w, draw, "Online, times and server replays are public. Your view-angle file and, unless you untick below, input journal go to play.proto.bar for anti-cheat review. Playing online also turns on automatic updates from proto.bar. Players see your play and chat; servers see your IP address.");
	ui_tm_dot(p, w, draw, "Public replays can also include pause-check timing, order, movement settings and physical/clock snapshots, but no raw paused input or new player/device identifiers.");
	ui_tm_dot(p, w, draw, "Detailed pause checks mean the interval qualified: they indicate the allowed movement/jump mode and absence of relevant use actions or unmodeled effects/transitions. Other intervals get only a generic unsupported/incomplete result.");
	ui_tm_dot(p, w, draw, "Never recorded: what you type (only that a key was pressed, and when), or anything outside the game.");
	return tm_y - 3;
};

// Uploading needs the engine's HTTPS sender: without it there is no box.
float() ui_tm_jcan =
{
	if (!checkextension("FTESURF_HID_HTTP"))
		return FALSE;
	return checkbuiltin(localcmd_local);
};

string(string s, float w, vector sz) ui_fit_text;

// This is the next online answer's choice, not permission before that answer.
// New online terms include journals by default; a real untick remains an opt-out.
void(vector pos, float w) ui_tm_jdraw =
{
	local float hot;
	local string s;

	sui_action_element(pos, [w, 26], "tm_journal", sui_noop);
	hot = sui_is_hovered("tm_journal");
	sui_style_box(pos + '0 3 0', '20 20 0', 5, ui_tm_jbox ? SUI_THEME_GOOD_BG : SUI_THEME_WELL,
	              hot ? COL_ACCENT : SUI_THEME_EDGE, 1);
	if (ui_tm_jbox)
		sui_roundbox(pos + '5 8 0', '10 10 0', 3, SUI_THEME_GOOD, 1);
	s = ui_fit_text("Include input journal with online play (untick to opt out; F2 changes it)",
	                w - 30, tm_sz);
	sui_text(pos + [30, floor((26 - tm_sz_y) * 0.5)], tm_sz, s, hot ? COL_ACCENT : COL_TEXT, 1, 0);
	if (sui_is_released("tm_journal"))
	{
		if (ui_tm_jbox)
		{
			ui_tm_jbox = FALSE;
			ui_tm_jtouched = TRUE;
		}
		else if (ui_synth())
			print("menu: journal upload consent takes a real click or key, not ui_key/ui_click\n");
		else
		{
			ui_tm_jbox = TRUE;
			ui_tm_jtouched = TRUE;
		}
	}
};

// Only a saved real answer applies the choice. Offline never enables uploads.
// P823: Play online also turns updates on, as the text above says; offline leaves them.
float(float tier) ui_tm_answer =
{
	if (!ui_consent_write(tier))
		return FALSE;
	if (tier >= FS_TERMS_ONLINE)
		MU_Consent(TRUE);
	if (ui_tm_jcan())
	{
		if (tier >= FS_TERMS_ONLINE && ui_tm_jbox)
			localcmd_local("rec_hid_upload 1\n");
		else
			localcmd_local("rec_hid_upload 0\n");
	}
	ui_tm_jtouched = FALSE;
	ui_tm_full = FALSE;
	return TRUE;
};

void(vector screensize) screen_terms =
{
	local vector p, q;
	local float w, colw, two, ha, hb, cards, ph, by, x, head, big, strip, jb, fh;
	local string lab, lead, foot;

	if (!ui_tm_jtouched)
	{
		if (ms_consent < FS_TERMS_ONLINE)
			ui_tm_jbox = TRUE;              // a proposed choice, never a native setter
		else
			ui_tm_jbox = (cvar("rec_hid_upload") != 0);
	}
	jb = (ui_tm_jcan() && !ui_tm_full) ? TM_JBOX : 0;  // the summary's: the cards have no room
	fh = 0;                                 // the footnote's line, under the cards only

	if (ui_tm_full)
	{
		lead = "World of Surf times your runs and keeps a file for each one. This is what is recorded, and where it goes.";
		w = min(1240, screensize_x - 32);
	}
	else
	{
		lead = "The short version. Choosing below means you have read it.";
		w = min(700, screensize_x - 32);
	}
	foot = "Your answer is kept in a file on this machine. It is a record that you agreed, not a lock.";
	two = (ui_tm_full && w >= 700);
	colw = two ? floor((w - TM_PAD * 2 - 16) * 0.5) - TM_CARD * 2 : w - TM_PAD * 2 - TM_CARD * 2;
	// At 16 px, and again at 12 where that is taller than the window.
	ha = hb = ph = head = cards = 0;
	for (big = 1; big >= 0; big = big - 1)
	{
		ui_tm_size(big);
		head = TM_TOP + ui_para('0 0 0', w - TM_PAD * 2, tm_sz, tm_pitch, lead, COL_DIM, FALSE) + 14;
		if (ui_tm_full)
		{
			fh = tm_pitch + 14;
			ha = ui_terms_col(0, '0 0 0', colw, FALSE);
			hb = ui_terms_col(1, '0 0 0', colw, FALSE);
			x = tm_pitch + 14 + TM_CARD * 2;           // a card's own title and padding
			cards = two ? max(ha, hb) + x : ha + hb + 2 * x + 12;
		}
		else
			cards = ui_terms_short('0 0 0', w - TM_PAD * 2, FALSE);
		ph = head + cards + 12 + fh + jb + 30 + 16;
		if (ph <= screensize_y - 16)
			break;
	}
	ui_tm_ph = ph;
	ui_tm_w = w;
	ui_tm_two = two;
	ui_tm_sx = screensize_x;
	ui_tm_sy = screensize_y;

	p = [floor((screensize_x - w) * 0.5), floor((screensize_y - ph) * 0.5)];
	if (p_y < 8)
		p_y = 8;

	sui_style_panel(p, [w, ph], 12, 1);

	Font_Set(ui_font_ui);
	sui_text([p_x + 16, p_y + 12], SZ_HEAD, (ui_tm_f2 && ms_consent >= FS_TERMS_ONLINE) ? "the current terms" : "before you play", COL_ACCENT, 1, 0);
	ui_para([p_x + TM_PAD, p_y + TM_TOP], w - TM_PAD * 2, tm_sz, tm_pitch, lead, COL_DIM, TRUE);

	if (!ui_tm_full)
		ui_terms_short([p_x + TM_PAD, p_y + head], w - TM_PAD * 2, TRUE);
	else
	{
		// The two cards: side by side, or one under the other in a narrow window.
		q = [p_x + TM_PAD, p_y + head];
		x = tm_pitch + 14;
		by = two ? max(ha, hb) : ha;
		sui_style_box(q, [colw + TM_CARD * 2, by + x + TM_CARD * 2], 9, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
		sui_text([q_x + TM_CARD, q_y + TM_CARD], tm_sz, "ON THIS MACHINE", COL_DIM, 1, 0);
		ui_terms_col(0, [q_x + TM_CARD, q_y + TM_CARD + x], colw, TRUE);
		if (two)
			q = [q_x + colw + TM_CARD * 2 + 16, q_y];
		else
			q = [q_x, q_y + ha + x + TM_CARD * 2 + 12];
		by = two ? max(ha, hb) : hb;
		sui_style_box(q, [colw + TM_CARD * 2, by + x + TM_CARD * 2], 9, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
		sui_text([q_x + TM_CARD, q_y + TM_CARD], tm_sz, "PUBLIC LOBBIES", COL_DIM, 1, 0);
		sui_text([q_x + TM_CARD + stringwidth("PUBLIC LOBBIES", TRUE, tm_sz) + 10, q_y + TM_CARD],
		         tm_sz, (ui_tm_f2 && ms_consent >= FS_TERMS_ONLINE) ? "chosen with Play online; switches in F2"
		         : "only if you turn them on below", SUI_THEME_MUTED, 1, 0);
		ui_terms_col(1, [q_x + TM_CARD, q_y + TM_CARD + x], colw, TRUE);
	}

	// The journal box, the footnote and the buttons' row; on a strip of their
	// own where the panel runs off the screen even at 12 px.
	by = p_y + ph - 16 - 30;
	strip = (by + 30 + 10 > screensize_y);
	if (strip)
	{
		by = screensize_y - 30 - 10;
		sui_fill([p_x, by - fh - jb - 4], [w, fh + jb + 44], SUI_THEME_PANEL, 1, 0);
		sui_fill([p_x, by - fh - jb - 4], [w, 1], SUI_THEME_EDGE, 1, 0);
	}
	if (ui_tm_full)
		sui_text([p_x + TM_PAD, by - tm_pitch - 10], tm_sz, foot, SUI_THEME_MUTED, 1, 0);

	// P902: read from F2 at the top tier, there is nothing to answer -- Back, and no write.
	if (ui_tm_f2 && ms_consent >= FS_TERMS_ONLINE)
	{
		if (ui_button("tm_back", [p_x + w - TM_PAD - 100, by], [100, 30], "Back", TRUE))
			menu_screen = SCREEN_JOURNAL;
		return;
	}
	// Placed from their labels' widths (ui_button grows to fit one): at fixed
	// widths the first cut drew one over the other.
	lab = (ms_consent >= FS_TERMS_VERSION) ? "Stay offline" : "Play offline";
	ha = stringwidth("Play online", TRUE, SZ_LABEL) + 28;
	hb = stringwidth(lab, TRUE, SZ_LABEL) + 28;
	if (ui_button("tm_accept", [p_x + w - TM_PAD - ha - 12 - hb, by], [hb, 30], lab))
	{
		if (ui_synth())
			print("menu: the terms take a real key or click, not ui_key or ui_click\n");
		else
			ui_tm_answer(FS_TERMS_VERSION);
	}

	if (ui_button("tm_online", [p_x + w - TM_PAD - ha, by], [ha, 30], "Play online", TRUE))
	{
		if (ui_synth())
			print("menu: the terms take a real key or click, not ui_key or ui_click\n");
		else
		{
			if (ui_tm_answer(FS_TERMS_ONLINE))
			{
				if (!cvar("ui_bootcheck"))
				{
					menu_screen = SCREEN_STEAM;
					ui_steam_t0 = time;
					print("menu: the terms are taken with lobbies on; the Steam sign-in is offered\n");
				}
			}
		}
	}

	// P902: from F2 (so past the first boot), Back to it writes nothing; Quit otherwise.
	if (ui_tm_f2 && ms_consent >= FS_TERMS_VERSION)
	{
		if (ui_button("tm_exit", [p_x + TM_PAD, by], [72, 30], "Back"))
			menu_screen = SCREEN_JOURNAL;
	}
	else if (ui_button("tm_exit", [p_x + TM_PAD, by], [72, 30], "Quit"))
		localcmd("quit\n");
	if (ui_button("tm_more", [p_x + TM_PAD + 84, by], [120, 30], ui_tm_full ? "Summary" : "Full details"))
		ui_tm_full = !ui_tm_full;
	// Last, so an answer stays the keyboard's default element, not the box.
	if (jb)
		ui_tm_jdraw([p_x + TM_PAD, by - fh - jb], w - TM_PAD * 2);
};

/*
  Patch 647: the Steam sign-in, offered where the owner asked for it, "when you
  first boot the game, like the screen that tells you, you will be recorded".

  A LINK IS MADE IN THE GAME, ON A LOBBY, UNDER A KEY PRESS (cl_account.qc,
  Patch 625): the lobby asks surfd whose install this is, and the engine signs
  only while a real key is going down.  The menu has neither.  So this screen
  does the part it can: it says what a link is and what the steps are, joins a
  lobby, and the box that comes up there by itself ("press Enter to link your
  Steam account") is the next thing the player sees.  From there it is the
  flow as it was: Enter opens the sign-in page, Steam's own page is a click
  on from it, and the number that page shows is typed back into the game.

  The lobby is the directory's first with room whose address this build would
  join by hand anyway; the screen's sentence and the button's deed ask the
  same function.  The name gate is waved through for this one connect: the
  Steam name becomes the name once linked (Patch 638).
*/
float() ui_steam_pick =
{
	local float i, full;

	for (i = 0; i < Lob_Count(); i = i + 1)
	{
		full = (Lob_Max(i) > 0);
		if (full)
			full = (Lob_Players(i) >= Lob_Max(i));
		if (!full)
		if (ui_addr_ok(Lob_Addr(i)))
		if (ui_host_allowed(Lob_Addr(i)))
			return i;
	}
	return -1;
};

void() ui_steam_go =
{
	local float i;

	i = ui_steam_pick();
	if (i < 0)
		return;
	// The map list is PLAY's to load and a first boot has not been there:
	// without it ui_connect cannot see that the lobby's map is missing here,
	// and would connect without fetching it (ui_prejoin).
	if (ms_count == 0)
		ui_load_maps();
	print(sprintf("menu: Steam sign-in: joining %s, %g maps known, where the game asks for Enter\n",
	              Lob_Addr(i), ms_count));
	menu_screen = SCREEN_MAIN;      // what ESC out of the game comes back to
	ui_name_skip = TRUE;
	ui_connect(i);
	ui_name_skip = FALSE;
};

// "Not now", and ESC.  Declining an offer that could be taken also tells the
// game not to raise its own box this session (cl_account.qc offers a link once
// a session, on the first lobby).  With no lobby to sign in on nothing was
// declined, and the game still offers it: the screen says so.
void() ui_steam_later =
{
	menu_screen = SCREEN_MAIN;
	if (ui_steam_pick() < 0)
	{
		print("menu: Steam sign-in: no lobby to sign in on; the game offers it on the first one\n");
		return;
	}
	print("menu: Steam sign-in: not now\n");
	// `set`, since the game has not registered the cvar yet.
	localcmd("set _acct_prompted 1\n");
};

// What a link gets the player, as the offer's card.  Returns its height; `draw`
// FALSE measures (ui_terms_col's way).
float(vector p, float w, float draw) ui_steam_card =
{
	tm_y = 0;
	ui_tm_head(p, draw, "Your times are ranked");
	ui_tm_par(p, w, draw, "Runs on public lobbies count on the leaderboard, under your account.", COL_TEXT);
	ui_tm_head(p, draw, "Your Steam name and picture");
	ui_tm_par(p, w, draw, "Shown with your times, in the game and on proto.bar, beside your Momentum Mod and KSF records.", COL_TEXT);
	return tm_y - TM_GAP;
};

void(vector screensize) screen_steam =
{
	local vector p;
	local float w, ph, y, pick, waited, card, noteh;
	local string note;

	ui_tm_size(screensize_y >= 560);

	// What happens on the press, said before it; or why there is no press.
	pick = ui_steam_pick();
	waited = time - ui_steam_t0;
	if (pick >= 0)
		note = "You join a lobby, and the game asks you to press Enter there. That opens proto.bar in your browser, where you sign in on Steam's own page and are given a number to type back into the game. The game never sees your password.";
	else if (Lob_Count() == 0 && waited < 8)
		note = "Looking for a lobby to sign in on...";
	else
		note = "No lobby can take you just now. The game offers this again the first time you join one.";

	w = min(620, screensize_x - 32);
	card = ui_steam_card('0 0 0', w - TM_PAD * 2 - TM_CARD * 2, FALSE) + TM_CARD * 2;
	noteh = ui_para('0 0 0', w - TM_PAD * 2, tm_sz, tm_pitch, note, SUI_THEME_MUTED, FALSE);
	ph = TM_TOP + tm_pitch + 16 + card + 14 + max(noteh, tm_pitch * 3) + 18 + 30 + 16;
	p = [floor((screensize_x - w) * 0.5), floor((screensize_y - ph) * 0.5)];
	if (p_y < 8)
		p_y = 8;

	sui_style_panel(p, [w, ph], 12, 1);

	Font_Set(ui_font_ui);
	sui_text([p_x + 16, p_y + 12], SZ_HEAD, "sign in with Steam", COL_ACCENT, 1, 0);
	sui_text([p_x + TM_PAD, p_y + TM_TOP], tm_sz,
	         "Link this game to your Steam account, once.", COL_DIM, 1, 0);

	y = p_y + TM_TOP + tm_pitch + 16;
	sui_style_box([p_x + TM_PAD, y], [w - TM_PAD * 2, card], 9, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	ui_steam_card([p_x + TM_PAD + TM_CARD, y + TM_CARD], w - TM_PAD * 2 - TM_CARD * 2, TRUE);
	ui_para([p_x + TM_PAD, y + card + 14], w - TM_PAD * 2, tm_sz, tm_pitch, note,
	        (pick < 0 && waited >= 8) ? SUI_THEME_WARN : SUI_THEME_MUTED, TRUE);

	y = p_y + ph - 16 - 30;
	if (pick >= 0)
	{
		if (ui_button("st_later", [p_x + w - TM_PAD - 200 - 12 - 100, y], [100, 30], "Not now"))
			ui_steam_later();
		if (ui_button("st_go", [p_x + w - TM_PAD - 200, y], [200, 30], "Sign in with Steam", TRUE))
		{
			if (ui_synth())
				print("menu: the sign-in takes a real key or click, not ui_key or ui_click\n");
			else
				ui_steam_go();
		}
	}
	else if (ui_button("st_later", [p_x + w - TM_PAD - 120, y], [120, 30],
	                   (Lob_Count() == 0 && waited < 8) ? "Not now" : "Continue"))
		ui_steam_later();
};

/*
  PATCH 340: the name gate's screen.  Forced by ui_name_gate from the two
  launch doors (ui_launch, ui_connect); the essays are there.  The shape is
  screen_terms' -- one panel, one decision, no ESC hole that skips it -- with
  two differences that matter: it HAS a cancel (choosing a name is not a
  consent), and its continue button RESUMES the launch it interrupted rather
  than dropping the player back at a menu with a start button to find again.
*/
void(vector screensize) screen_name =
{
	local vector p;
	local string err;
	local float  ph, btn;

	ph  = 224;
	btn = 168;
	p = [floor(screensize_x * 0.5) - 260, floor(screensize_y * 0.5 - ph * 0.5)];
	if (p_y < 0)
		p = [p_x, 0];

	sui_fill(p, [520, ph], COL_PANEL, 0.94, 0);
	sui_border_box(p, [520, ph], 1, COL_BORDER, 1, 0);

	Font_Set(ui_font_display);
	sui_text([p_x + 24, p_y + 20], SZ_TITLE, "Choose your name", COL_ACCENT, 1, 0);
	Font_Set(ui_font_ui);

	sui_text([p_x + 24, p_y + 66], SZ_LABEL,
	         "You are still on the factory default. On a public lobby that is", COL_TEXT, 1, 0);
	sui_text([p_x + 24, p_y + 84], SZ_LABEL,
	         "twelve \"Player\"s on one scoreboard -- pick something of your own.", COL_TEXT, 1, 0);

	ui_field("nm_field", [p_x + 24, p_y + 112], [472, 30],
	         ui_name_field, ui_name_caret, "your name");

	if (ui_name_err != "")
		sui_text([p_x + 24, p_y + 148], SZ_LABEL, ui_name_err, '1 0.55 0.35', 1, 0);
	else
		sui_text([p_x + 24, p_y + 148], SZ_LABEL,
		         "^ codes allowed. Your times follow your id, not this name.",
		         COL_DIM, 1, 0);

	if (ui_button("nm_go", [p_x + 24, p_y + btn], [230, 30], "continue"))
	{
		err = ui_name_take(ui_name_field);
		if (err != "")
		{
			ui_name_err = err;
		}
		else
		{
			// The launch this screen interrupted, resumed.  Both callees
			// re-run their gates; the name gate now passes.
			menu_screen = ui_name_back;
			if (ui_name_resume == 1)
			{
				ui_plain_only = ui_launch_plain;
				ui_launch_mode(ui_launch_maxfog);
				ui_plain_only = FALSE;
			}
			else if (ui_name_resume == 2)
				ui_connect(ui_name_arg);
			else if (ui_name_resume == 3)
				MF_ResumeJoin();
			ui_name_resume = 0;
		}
	}

	if (ui_button("nm_back", [p_x + 396, p_y + btn], [100, 30], "back"))
	{
		ui_name_resume = 0;
		menu_screen = ui_name_back;
	}
};

// Patch 467: PLAY / VISUALS / MUSIC / QUIT, drawn by m_milk.qc -- PLAY is the
// old "create server".
// P902 (Lex): F2 holds what the title screen used to show -- the patch notes and the
// updater -- with the input journal and the terms, one page each behind tabs: a 1600x900
// window here is ~690x390 menu units, and the four did not fit one panel. The title screen
// keeps a hint line (MU_Hint); the first boot's terms screen is still the gate.
float ui_f2_tab;                    // 0 patch notes, 1 updates, 2 input journal, 3 terms

// "" keeps the last page, or Updates while an update waits for a restart.
void(string pg) ui_f2_open =
{
	if (pg == "updates") ui_f2_tab = 1;
	else if (pg == "notes") ui_f2_tab = 0;
	else if (pg == "journal") ui_f2_tab = 2;
	else if (pg == "terms") ui_f2_tab = 3;
	else if (cvar_string("update_state") == "restart" || cvar_string("update_state") == "launcher") ui_f2_tab = 1;
	menu_screen = SCREEN_JOURNAL;
};
void(vector screensize) screen_journal =
{
	local vector p;
	local float w, h, lw, x, y, k, have, enabled;
	local string body, note, label, terms, rid;

	w = min(760, screensize_x - 32);
	h = min(560, screensize_y - 32);
	p = [floor((screensize_x - w) * 0.5), floor((screensize_y - h) * 0.5)];
	sui_style_panel(p, [w, h], 12, 1);
	Font_Set(ui_font_ui);
	// P796: first, so Back and not Allow is the keyboard's default.
	if (ui_button("journal_back", [p_x + w - 16 - 90, p_y + 12], [90, 30], "Back"))
	{
		menu_screen = SCREEN_MAIN;
		return;
	}
	x = p_x + 16;
	for (k = 0; k < 4; k = k + 1)
	{
		rid = strcat("f2_tab", ftos(k));
		label = (k == 0) ? "Patch notes" : (k == 1) ? "Updates" : (k == 2) ? "Input journal" : "Terms";
		x = x + ui_chip([x, p_y + 14], rid, label, ui_f2_tab == k) + 8;
		if (sui_is_released(rid)) ui_f2_tab = k;
	}
	lw = w - 32;
	y = p_y + 14 + CHIP_H + 18;

	if (ui_f2_tab == 0)
		MU_NotesAt([p_x + 16, y], [lw, p_y + h - 16 - y]);
	else if (ui_f2_tab == 1)
		MU_StatusAt([p_x + 16, y], lw);
	else if (ui_f2_tab == 2)
	{
		body = "Accepting online play allows a public lobby to request your run's raw mouse and keyboard event journal, with timings. It is sent to play.proto.bar over HTTPS for private anti-cheat review, not as a public replay. Console/menu text and activity outside the game window are not recorded.";
		note = "New online acceptance includes journals unless you opt out. Uploads also require the online terms; this page can allow or stop them. Stopping cancels an active upload and prevents new ones, without deleting evidence already received. rec_hid 0 stops local recording too.";
		y = y + ui_para([p_x + 16, y], lw, SZ_LABEL, 20, body, COL_TEXT, TRUE) + 14;
		y = y + ui_para([p_x + 16, y], lw, SZ_LABEL, 20, note, COL_DIM, TRUE) + 18;
		have = checkextension("FTESURF_HID_HTTP");
		if (have)
			have = checkbuiltin(localcmd_local);
		enabled = cvar("rec_hid_upload");
		label = enabled ? "Stop journal uploads" : "Allow journal uploads";
		if (have)
		{
			if (ui_button("journal_choice", [p_x + 16, y], [240, 30], label, TRUE))
			{
				if (enabled)
				{
					ui_tm_jbox = FALSE;
					ui_tm_jtouched = TRUE;
					localcmd_local("rec_hid_upload 0\n");
				}
				else if (ui_synth())
					print("menu: journal upload consent takes a real click or key, not ui_key/ui_click\n");
				else
				{
					ui_tm_jbox = TRUE;
					ui_tm_jtouched = TRUE;
					localcmd_local("rec_hid_upload 1\n");
				}
			}
		}
		else
			sui_text([p_x + 16, y + 7], SZ_LABEL, "Update the native client to enable uploads", SUI_THEME_WARN, 1, 0);
	}
	else
	{
		// Below the online tier the button opens the terms screen itself, on the summary
		// where the journal box is; at it, the full text to read.
		if (ms_consent >= FS_TERMS_ONLINE)
			terms = "You have accepted the terms for offline and online play. The Updates and Input journal pages turn updates and journal uploads off.";
		else
			terms = "You have accepted the terms for offline play. Public lobbies, the board, story and updates need the online terms: Play online or the button below shows them, and nothing changes until you choose.";
		y = y + ui_para([p_x + 16, y], lw, SZ_LABEL, 20, terms, COL_TEXT, TRUE) + 18;
		if (ui_button("journal_terms", [p_x + 16, y], [170, 30], "Read the terms"))
		{
			ui_tm_full = (ms_consent >= FS_TERMS_ONLINE);
			ui_tm_f2 = TRUE;
			menu_screen = SCREEN_TERMS;
		}
	}
};

void(vector screensize) screen_home;
void(vector screensize) MH_Tabs;
vector(vector screensize) MH_ShellSize;
vector(vector screensize) MH_ShellOrigin;
vector(vector screensize) MH_ContentSize;
void(vector size) MH_Sidebar;
void(vector screensize) MH_Settings;
void() MH_Poll;
void() MH_Probe;
void(vector screensize) screen_main =
{
	screen_home(screensize);
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

// The narrowest a lobby cell may be before the grid drops a column (90 px of
// thumbnail and gutter + 8 margin leaves 102 px of text).
#define LOB_MIN_COL 200

// The lobby grid: 4 across, at most 3 rows -- the 12-lobby fleet exactly.
// LOB_ROWS_MAX is a DRAW cap, not LB_MAX (m_lobby.qc), which is the PARSE cap
// and must cover the whole fleet or ui_map_players under-counts (build 67).
#define LOB_COLS     4
#define LOB_ROWS_MAX 3

// ---------------------------------------------------------------------------
//  Map downloads.  Needs engine Patch 465 -- `downloadmap` is a menu builtin
//  there, because menuqc's localcmd runs at RESTRICT_INSECURE and the console
//  `download` command treats that as a SERVER asking, which refuses a bare map
//  (cl_download_redirection defaults to 2) and ignores sv_dlURL even when it
//  does not.  checkbuiltin() is what keeps this file loadable on an older
//  engine: with no builtin the button simply never draws.
//
//  Progress comes from serverkey("dlstate"), which is VM-agnostic in the engine
//  (PF_cl_serverkey_internal reads cls.download directly), so the menu can read
//  it without being the csqc.  Its nine fields are, in order:
//    files-remaining total-size unknown-sizes-flag localname remotename
//    percent rate received-bytes total-bytes
// ---------------------------------------------------------------------------
#define DL_IDLE     0
#define DL_ACTIVE   1
#define DL_OK       2
#define DL_FAIL     3

#define DL_HOLD     6   // seconds a finished/failed row keeps saying so

float  dl_have_bi;      // 1 if the engine has the builtin, -1 unasked
                        // dl_have_kb and ui_dl_kb_ready live up beside
                        // ui_dl_load, which is their first caller and runs long
                        // before this block -- QuakeC has no forward references.
float  dl_state;
string dl_name;         // the map we asked for, "" when idle
float  dl_pct;
float  dl_rate;         // bytes/sec, the engine's own figure
float  dl_done;
float  dl_total;
float  dl_until;
float  dl_t0;           // when it started (time), for the status strip
// P1094: 1 (2 = force) while a download waits for this client's local game to
// end -- the engine refuses every download while it hosts one (sv.state in
// CL_CheckOrEnqueDownloadFile) -- and Dl_Tick asks for it once the game is gone.
float  dl_afterlocal;

/*
  THE MAP MIRROR, AND WHY THIS FUNCTION HAS TO EXIST.

  cfg/default.cfg sets sv_dlURL, and on this box it was EMPTY at runtime
  anyway -- because ftesurf/ftesurf.cfg, the config the engine writes on
  quit, holds `sv_dlURL ""` and is exec'd AFTER default.cfg.  A saved empty
  value silently wins over the shipped one, and then every download fails
  with no message at all: CL_CheckOrEnqueDownloadFile finds no url, never
  reaches CL_EnqueDownload, and returns "nothing to wait for", which
  ui_dl_start can only read as a failure.

  MEASURED, three ways, because the first two explanations were wrong.  It
  is not the map (bhop_rbs failed and succeeded in different runs), and it
  is not elapsed time (+2 s, +18 s and +38 s all failed).  The one success
  in every probe followed a runtime `set sv_dlURL`, and printing the cvar
  showed "" as shipped and the download starting on the very next line once
  it was set to the same string it was supposed to already hold.

  The rule is lobby_dir's, one file over (Lob_MigrateDir), for the same
  reason: repair an EMPTY value, leave somebody's own choice alone and say
  so, and stamp a generation so it is a one-shot either way.  A player who
  points this at their own mirror must not have it taken back every launch.
*/
#define FS_MAPDL_URL      "https://play.proto.bar"
#define FS_MAPDL_URL_GEN  1

void() ui_dl_migrate_url =
{
	local string cur;

	if (cvar("ui_mapdl_gen") >= FS_MAPDL_URL_GEN)
		return;

	cur = cvar_string("sv_dlURL");
	if (cur == "")
	{
		localcmd(strcat("seta sv_dlURL \"", FS_MAPDL_URL, "\"\n"));
		print(strcat("^3WOS: sv_dlURL was empty -- map downloads could "
		             "not have worked.  Set to ", FS_MAPDL_URL, "^7\n"));
	}
	else if (cur != FS_MAPDL_URL)
		print(strcat("^3WOS: sv_dlURL is ", cur, "^3 -- leaving it alone. "
		             "Reset it with: sv_dlURL \"", FS_MAPDL_URL, "\"^7\n"));

	// Stamped whichever branch ran, so this is a one-shot either way.
	localcmd(strcat("seta ui_mapdl_gen \"", ftos(FS_MAPDL_URL_GEN), "\"\n"));
};

float() ui_dl_ready =
{
	if (dl_have_bi == 0)
		dl_have_bi = checkbuiltin(downloadmap) ? 1 : -1;
	return dl_have_bi > 0;
};

// ROADMAP 1: no engine has this yet.  It stops the transfer in flight and
// returns 1 if it did; probed like downloadmap, and absent there is no Cancel
// for a download (a held join's Cancel still drops the join).
float() downloadcancel = #0:downloadcancel;
float  dl_have_cancel;          // 1 present, -1 absent, 0 unasked

float() ui_dl_cancel_ready =
{
	if (dl_have_cancel == 0)
		dl_have_cancel = checkbuiltin(downloadcancel) ? 1 : -1;
	return dl_have_cancel > 0;
};


// "1.4 MB/s" / "812 KB/s".  Below a megabyte the round number is the one that
// moves, and a player watching a bar wants to see it move.
string(float bps) ui_dl_rate =
{
	if (bps >= 1048576)
		return sprintf("%.1f MB/s", bps / 1048576);
	return sprintf("%g KB/s", floor(bps / 1024));
};

string(float kb) ui_dl_size =
{
	if (kb >= 1024)
		return sprintf("%.1f MB", kb / 1024);
	return sprintf("%g KB", kb);
};

/*
  How wide the download gutter has to be, MEASURED rather than declared.

  It was a flat 92, and "re-get 149.0 MB" does not fit in 92 px -- the size was
  cut off on exactly the rows that had most to say, which is what was reported.
  A character count would not have caught it either: the UI face is Roboto
  (sh_font.qc), it is proportional, and "Wrong build" and "re-get 999.9 MB" are
  11 and 15 characters but nothing like 11/15ths of each other in pixels.

  So ask the font.  The two strings below are the widest the gutter ever draws
  -- the longest label, and the longest size line -- and a face or a size change
  re-measures instead of re-clipping.  Nothing is cached: it is two stringwidth
  calls once per frame, against a dozen per row inside the loop it feeds.

  Called only from inside the draw, which is where m_draw has set the UI font;
  measuring anywhere else would measure whatever font happened to be current.
*/
float() ui_dl_gutter =
{
	local float w;
	w = stringwidth("Wrong build", TRUE, SZ_ROW);
	// 999.9 MB rather than the widest size actually offered: the digits are the
	// same width in this face, and pinning it to today's largest map would make
	// the layout depend on the map list.
	w = max(w, stringwidth("re-get 999.9 MB", TRUE, SZ_ROW));
	return ceil(w) + DL_PAD * 2 + 4;        // +4: the gutter's own right margin
};

// `force` re-gets a map we hold the wrong BUILD of.  It cannot touch a Steam
// install: the download's fsroot is FS_GAMEONLY on this path, so the file lands
// in ftesurf/maps/ and shadows the lower mount, and Patch 465's .tmp-then-rename
// means a failed re-get leaves the old build rather than no map at all.
void(string name, optional float force) ui_dl_start =
{
	if (!ui_dl_ready())
		return;
	if (dl_state == DL_ACTIVE)
		return;                 // the engine does one at a time; so do we

	if (isserver())
	{
		dl_name  = name;
		dl_state = DL_ACTIVE;
		dl_pct = dl_rate = dl_done = dl_total = 0;
		dl_t0 = 0;              // set at the real start; until then the strip shows the message
		dl_afterlocal = force ? 2 : 1;
		ui_st_result(sprintf("%s downloads when you leave this game", name), 0);
		return;
	}
	float r = downloadmap(name, force);
	if (r == 1)
	{
		dl_name  = name;
		dl_state = DL_ACTIVE;
		dl_pct = dl_rate = dl_done = dl_total = 0;
		dl_t0 = time;
		Mzd_Fetch(name);
	}
	else if (r == 2)
	{
		// Already present -- the list is stale rather than the map missing.
		Mzd_Fetch(name);
		ui_load_maps();
		ui_refilter();
	}
	else
	{
		dl_name  = name;
		dl_state = DL_FAIL;
		dl_until = time + DL_HOLD;
		ui_st_result(sprintf("Download of %s failed", name), -1);
	}
};

/*
  Polled from m_draw beside Lob_Poll.

  The finish test asks the FILESYSTEM, not the engine: dlstate goes empty both
  when a download completed and when it failed, and those must not read the
  same.  A 404 on the http mirror is not even a failure -- the engine re-queues
  it over the game netchan (cl_parse.c:719-724) and dlstate stays busy -- so the
  only thing that settles it is whether the bsp is on disk afterwards.
*/
void() Dl_Tick =
{
	if (dl_state == DL_OK || dl_state == DL_FAIL)
	{
		if (time > dl_until)
		{
			dl_state = DL_IDLE;
			dl_name = "";
		}
		return;
	}

	if (dl_state != DL_ACTIVE)
		return;

	if (dl_afterlocal)
	{
		// Not during a connect either: `connect` ends the local game, and a download
		// started in its handshake holds that join's signon until it finishes
		// (CL_RequestNextDownload waits on cls.download).
		if (isserver() || serverkey("transferring") != "" || serverkey("constate") == "connecting")
			return;
		float f = dl_afterlocal - 1;
		dl_afterlocal = 0;
		dl_state = DL_IDLE;     // ui_dl_start refuses while one is active
		ui_dl_start(dl_name, f);
		if (dl_state == DL_IDLE)
		{
			dl_state = DL_OK;   // on disk after all (2): a held join reads that as done
			dl_until = time + DL_HOLD;
		}
		return;
	}

	string s = serverkey("dlstate");
	if (s == "")
	{
		dl_state = ui_file_exists(strcat("maps/", dl_name, ".bsp")) ? DL_OK : DL_FAIL;
		dl_until = time + DL_HOLD;
		if (dl_state == DL_OK)
		{
			ui_st_result(sprintf("Installed %s", dl_name), 1);
			// It is on the disk now, so it is no longer a downloadable row.
			ui_load_maps();
			ui_refilter();
		}
		else
			ui_st_result(sprintf("Download of %s failed", dl_name), -1);
		return;
	}

	float n = tokenize(s);
	if (n < 9)
		return;                 // queued but not started; keep the last numbers

	dl_pct   = stof(argv(5));
	dl_rate  = stof(argv(6));
	dl_done  = stof(argv(7));
	dl_total = stof(argv(8));
};

/*
  How long a HELD connect waits with NOTHING HAPPENING.  Not a download
  budget: ui_prejoin_tick pushes this forward on every frame the transfer is
  alive, so a 150 MB map on a slow line never trips it and a dead one gives
  up in a minute.  A budget sized for the biggest map would be fifteen
  minutes of silence after a fetch that died in its first second.
*/
#define PJ_STALL  60

void() ui_prejoin_clear =
{
	if (pj_addr != "") strunzone(pj_addr);
	if (pj_map  != "") strunzone(pj_map);
	pj_addr = pj_map = "";
	pj_until = 0;
};

/*
  TRUE when the connect has been HELD and this owns it now.

  EVERY UNCERTAIN CASE RETURNS FALSE and connects as before.  Refusing to
  join over a map this cannot judge would be a worse failure than the kick it
  exists to avoid -- the server is the authority on its own map and gets the
  last word either way.  See the essay over pj_addr for what it cannot see.
*/
float(string addr, string mapname) ui_prejoin =
{
	local float row;
	local string have;

	if (pj_addr != "")
		return TRUE;            // one is already held; it owns the connect
	if (!ui_dl_ready())
		return FALSE;           // no downloadmap builtin: nothing to offer

	row = ui_map_index(mapname);
	if (row < 0)
		return FALSE;           // not in the list, so nothing is known of it

	ui_dlkb_finish();           // Patch 999 review: a wrong build must not just connect
	have = bufstr_get(ms_have, row);
	if (have == "1")
		return FALSE;           // agrees with the Pi as far as a size can say

	ui_dl_start(mapname, have == "2");
	// P1094: the join ends a local game anyway; ending it first lets the download start.
	if (dl_afterlocal && dl_name == mapname && isserver())
		localcmd("disconnect\n");

	// ui_dl_start is quiet about declining: it refuses while another transfer
	// is in flight, and reloads the list when the file turns out to be there
	// after all.  Both leave this map not downloading, and both mean connect.
	if (dl_state != DL_ACTIVE || dl_name != mapname)
		return FALSE;

	pj_addr  = strzone(addr);
	pj_map   = strzone(mapname);
	pj_until = gettime(0) + PJ_STALL;

	print(sprintf("^5online:^7 holding the join -- fetching the server's "
	              "build of %s first (%s)\n", mapname,
	              (have == "2") ? "yours is a different build"
	                            : "you do not have this map"));
	return TRUE;
};

// Polled from m_draw beside Dl_Tick, which is what moves dl_state.
void() ui_prejoin_tick =
{
	if (pj_addr == "")
		return;

	if (dl_name == pj_map)
	{
		if (dl_state == DL_OK)
		{
			print(sprintf("^5online:^7 got it -- connecting to %s\n",
			              pj_addr));
			localcmd(sprintf("connect %S\n", pj_addr));
			ms_query_stale = TRUE;
			ui_prejoin_clear();
			m_close();
			return;
		}
		if (dl_state == DL_FAIL)
		{
			// NOT connecting anyway.  Joining on a map we have just been told
			// is the wrong build is the kick this path exists to avoid, and
			// reaching it the slow way is worse than reaching it at once.
			print(sprintf("^1online:^7 could not fetch %s -- not connecting. "
			              "Use the button on its row in the list.\n",
			              pj_map));
			ui_st_result(sprintf("Download of %s failed -- not joining", pj_map), -1);
			ui_prejoin_clear();
			return;
		}
		if (dl_state == DL_ACTIVE)
			pj_until = gettime(0) + PJ_STALL;      // alive; keep waiting
	}

	if (gettime(0) > pj_until)
	{
		print(sprintf("^1online:^7 the fetch of %s stalled -- not connecting.\n",
		              pj_map));
		ui_st_result(sprintf("Download of %s stalled -- not joining", pj_map), -1);
		ui_prejoin_clear();
	}
};

/*
  ROADMAP 1: the status strip (screen_create's footer) and the toast (SCREEN_MAIN)
  say one line about what is in flight -- a join's ask, the lobby's switch, a
  connect held for a download, a download -- or the last outcome for ST_HOLD s.
  ui_status_update fills these once a frame, before MM_Frame.
*/
#define ST_NONE     0
#define ST_ASK      1
#define ST_WAIT     2
#define ST_HELD     3
#define ST_DL       4
#define ST_RESULT   5
#define COL_FAIL    SUI_THEME_BAD

float  ui_st_kind;
string ui_st_text;              // the line, cut from its end to fit
string ui_st_figs;              // the numbers after it, never cut
float  ui_st_frac;              // the bar, 0..1; -1 a moving segment
float  ui_st_cancel;            // draw a Cancel
vector ui_st_col;

// ui_strip_test's fake state (0 = the real one), when it began, and dl/held's
// percent: -1 animates, -2 is "size not known yet".
float  ui_stt, ui_stt_t0, ui_stt_pct;
#define ST_FAKEMAP    "surf_kitsune"
#define ST_FAKEADDR   "203.0.113.7:27501"
#define ST_FAKETOTAL  45613056      // 43.5 MB
#define ST_FAKERATE   2202010       // 2.1 MB/s

// "42%  18.3 of 43.5 MB  2.1 MB/s  12 s left".  The engine reports 0 for the
// size and the rate until it knows them, and nothing is estimated before that.
string(float pct, float done, float total, float rate) ui_dl_figs =
{
	local string s;
	local float secs;

	if (total <= 0)
	{
		if (done <= 0)
			return "starting...";
		s = sprintf("%.1f MB", done / 1048576);
	}
	else
		s = sprintf("%g%%  %.1f of %.1f MB", floor(pct), done / 1048576, total / 1048576);
	if (rate <= 0)
		return s;
	s = strcat(s, "  ", ui_dl_rate(rate));
	if (total <= 0)
		return s;
	secs = ceil(max(0, total - done) / rate);
	if (secs < 90)
		return sprintf("%s  %g s left", s, secs);
	return sprintf("%s  %g min left", s, ceil(secs / 60));
};

// Stop the engine's transfer.  The row and the strip drop it at once, so the
// dlstate it leaves behind is not read as a failure.  TRUE if it stopped.
float() ui_dl_cancel =
{
	if (dl_afterlocal)
	{
		dl_afterlocal = 0;      // never asked of the engine: nothing to stop there
		ui_st_result(sprintf("Download of %s cancelled", dl_name), 0);
		dl_state = DL_IDLE;
		dl_name = "";
		return TRUE;
	}
	if (!ui_dl_cancel_ready())
		return FALSE;
	if (!downloadcancel())
		return FALSE;
	print(sprintf("^5online:^7 cancelled the download of %s\n", dl_name));
	ui_st_result(sprintf("Download of %s cancelled", dl_name), 0);
	dl_state = DL_IDLE;
	dl_name = "";
	return TRUE;
};

// End a join in flight -- the ask, the lobby's switch, or a connect held for a
// download -- with a word on the strip.  TRUE if there was one.  withdl: the
// held join's download goes too, if the engine can stop it (the Cancel button;
// ESC and back leave it running).
float(float withdl) ui_strip_cancel_join =
{
	if (ui_stt == ST_ASK || ui_stt == ST_WAIT || ui_stt == ST_HELD)
	{
		ui_stt = 0;
		ui_st_result("Join cancelled (ui_strip_test)", 0);
		return TRUE;
	}
	if (ui_join_pending)
	{
		print("^5online:^7 join cancelled\n");
		ui_st_result(sprintf("Stopped looking for a server for %s", Lob_JoinMap()), 0);
		ui_join_cancel();
		return TRUE;
	}
	if (pj_addr == "")
		return FALSE;

	ui_eventfog_target("");
	print(sprintf("^5online:^7 join cancelled -- not connecting to %s\n", pj_addr));
	ui_st_result(sprintf("Join cancelled -- %s keeps downloading", pj_map), 0);
	if (withdl)
	if (dl_state == DL_ACTIVE)
	if (dl_name == pj_map)
		ui_dl_cancel();
	ui_prejoin_clear();
	return TRUE;
};

// A join in flight, real or ui_strip_test's: start reads "joining..." meanwhile.
float() ui_join_busy =
{
	if (ui_join_pending || pj_addr != "")
		return TRUE;
	return (ui_stt == ST_ASK || ui_stt == ST_WAIT || ui_stt == ST_HELD);
};

// The strip's Cancel.
void() ui_status_cancel =
{
	if (ui_strip_cancel_join(TRUE))
		return;
	if (ui_stt == ST_DL)
	{
		ui_stt = 0;
		ui_st_result("Download cancelled (ui_strip_test)", 0);
		return;
	}
	ui_dl_cancel();
};

void() ui_status_update =
{
	local float kind, el, lim, pct, done, total, rate, st;
	local string map, addr;

	kind = ST_NONE;
	el = lim = pct = done = total = rate = 0;
	map = addr = "";

	if (ui_stt)
	{
		kind = ui_stt;
		map  = ST_FAKEMAP;
		addr = ST_FAKEADDR;
		el   = time - ui_stt_t0;
		lim  = (kind == ST_ASK) ? LJ_DEADLINE : LJ_WAITCAP;
		if (ui_stt_pct != -2)
		{
			pct   = (ui_stt_pct >= 0) ? ui_stt_pct : min(99, el * 4);
			total = ST_FAKETOTAL;
			done  = total * pct / 100;
			rate  = ST_FAKERATE;
		}
	}
	else if (ui_join_pending)
	{
		// LJ_READY and LJ_FAIL never reach here: ui_join_tick settles them first.
		st = Lob_JoinState();
		if (st == LJ_ASK)
		{
			kind = ST_ASK;
			map  = Lob_JoinMap();
			el   = time - Lob_JoinAt();
			lim  = LJ_DEADLINE;
		}
		else if (st == LJ_WAIT)
		{
			kind = ST_WAIT;
			map  = Lob_JoinMap();
			addr = Lob_JoinAddr();
			el   = time - Lob_JoinWaitAt();
			lim  = Lob_JoinUntil() - Lob_JoinWaitAt();
		}
	}
	if (kind == ST_NONE)
	{
		if (pj_addr != "")
		{
			kind = ST_HELD;
			map  = pj_map;
		}
		else if (dl_state == DL_ACTIVE)
		{
			kind = ST_DL;
			map  = dl_name;
		}
		if (kind != ST_NONE)
		if (dl_state == DL_ACTIVE)
		if (dl_name == map)
		{
			pct   = dl_pct;
			done  = dl_done;
			total = dl_total;
			rate  = dl_rate;
		}
	}

	ui_charge_on = (kind != ST_NONE);
	if (kind == ST_ASK || kind == ST_WAIT)
		ui_charge = bound(0, el / max(lim, 1), 1);
	else if (total > 0)
		ui_charge = bound(0, pct / 100, 1);
	else
		ui_charge = 0;

	// An outcome newer than a running download outranks it for its hold: a held
	// join cancelled mid-fetch says so, then the fetch's own line comes back.
	if (kind == ST_DL)
	if (ui_st_msg)
	if (time < ui_st_msguntil)
	if (ui_st_msgat > (ui_stt ? ui_stt_t0 : dl_t0))
		kind = ST_NONE;

	ui_st_kind   = kind;
	ui_st_text   = "";
	ui_st_figs   = "";
	ui_st_frac   = -1;
	ui_st_cancel = FALSE;
	ui_st_col    = COL_TEXT;

	if (kind == ST_ASK)
	{
		ui_st_text   = sprintf("Finding a server for %s...", map);
		ui_st_figs   = sprintf("  %g s", floor(el));
		ui_st_cancel = TRUE;
	}
	else if (kind == ST_WAIT)
	{
		ui_st_text   = sprintf("%s is switching to %s", addr, map);
		ui_st_figs   = sprintf(" -- %g s", floor(el));
		ui_st_frac   = ui_charge;
		ui_st_cancel = TRUE;
	}
	else if (kind == ST_HELD || kind == ST_DL)
	{
		if (kind == ST_HELD)
			ui_st_text = sprintf("Downloading %s before joining", map);
		else if (dl_afterlocal)
			ui_st_text = sprintf("%s downloads when you leave this game", map);
		else
			ui_st_text = sprintf("Downloading %s", map);
		ui_st_figs = dl_afterlocal ? "" : strcat(" -- ", ui_dl_figs(pct, done, total, rate));
		if (total > 0)
			ui_st_frac = ui_charge;
		ui_st_cancel = (kind == ST_HELD);
		if (kind == ST_DL)
		if (dl_afterlocal || ui_dl_cancel_ready())
			ui_st_cancel = TRUE;
	}
	else if (ui_st_msg)
	if (time < ui_st_msguntil)
	{
		ui_st_kind = ST_RESULT;
		ui_st_text = ui_st_msg;
		if (ui_st_msgok > 0)
			ui_st_col = COL_PLAY;
		else if (ui_st_msgok < 0)
			ui_st_col = COL_FAIL;
		else
			ui_st_col = COL_DIM;
	}
};

// The space's own light while it is drawn (MM_Camera walks milk_hue with the
// charge), else the accent.
vector() ui_status_barcol =
{
	if (MM_Active())
		return Milk_Pal(milk_hue + 0.1);
	return COL_ACCENT;
};

void(vector pos, float w) ui_status_line =
{
	local float fw;
	local string s;

	fw = stringwidth(ui_st_figs, TRUE, SZ_LABEL);
	s  = ui_fit_text(ui_st_text, max(40, w - fw), SZ_LABEL);
	sui_text(pos, SZ_LABEL, s, ui_st_col, 1, 0);
	if (ui_st_figs != "")
		sui_text([pos_x + stringwidth(s, TRUE, SZ_LABEL), pos_y], SZ_LABEL,
		         ui_st_figs, COL_DIM, 1, 0);
};

void(vector pos, float w, float h) ui_status_bar =
{
	local float a, x0, x1;

	sui_fill(pos, [w, h], COL_BORDER, 0.5, 0);
	if (ui_st_kind == ST_RESULT)
	{
		// The outcome's colour, fading over its hold.
		sui_fill(pos, [w, h], ui_st_col, bound(0, (ui_st_msguntil - time) / ST_HOLD, 1), 0);
		return;
	}
	if (ui_st_frac >= 0)
	{
		sui_fill(pos, [w * ui_st_frac, h], ui_status_barcol(), 1, 0);
		return;
	}
	// No share to show: a third of the bar sweeping across every 1.4 s.
	a  = time / 1.4;
	a  = a - floor(a);
	x0 = w * (a * 1.3 - 0.3);
	x1 = min(w, x0 + w * 0.3);
	x0 = max(0, x0);
	if (x1 > x0)
		sui_fill([pos_x + x0, pos_y], [x1 - x0, h], ui_status_barcol(), 1, 0);
};

// Between the start and back buttons; nothing at all when nothing is in flight.
void(vector pos, float w) ui_status_strip =
{
	local float tw;

	if (ui_st_kind == ST_NONE || w < 160)
		return;
	tw = w;
	if (ui_st_cancel)
	{
		tw = w - 100;
		if (ui_button("cs_cancel", [pos_x + w - 84, pos_y], [84, 30], "cancel"))
			ui_status_cancel();
	}
	ui_status_line([pos_x, pos_y + 2], tw);
	ui_status_bar([pos_x, pos_y + 24], tw, 3);
};

// SCREEN_MAIN's copy of the strip, without a button, so leaving the create
// screen does not hide it.  Drawn flat after the in-world panel, above the
// "move the mouse" hint (MM_ScreenMain) and below the panel at 720p and up.
void(vector screensize) ui_status_toast =
{
	local float w;
	local vector p;

	if (ui_st_kind == ST_NONE)
		return;
	w = stringwidth(ui_st_text, TRUE, SZ_LABEL) + stringwidth(ui_st_figs, TRUE, SZ_LABEL) + 32;
	w = min(screensize_x - 32, max(360, w));
	p = [floor((screensize_x - w) * 0.5), screensize_y - 96];
	sui_style_panel(p, [w, 44], 10, 0.94);
	ui_status_line(p + '16 9 0', w - 32);
	ui_status_bar(p + '16 32 0', w - 32, 3);
};

/*
  ESC on the create screen takes one step a press: the leaderboard panel
  (ROADMAP 9), then a join in flight, then the screen.  Menu_InputEvent and the
  two test twins share it.  Returns the step: 1, 2, 3 (back to main) or 4
  (Patch 991: in a game the menu opens on this screen, so ESC returns to the
  game; the Friends panel no longer takes a press of its own).
*/
float() ui_create_esc =
{
	if (Mlb_IsOpen())
	{
		Mlb_Close("esc");
		return 1;
	}
	if (ui_strip_cancel_join(FALSE))
		return 2;
	if (clientstate() == 2)
	{
		m_close();
		return 4;
	}
	menu_screen = SCREEN_MAIN;
	return 3;
};

/*
  ui_strip_test <ask|wait|held|dl> [pct|start] -- fakes that state on the strip,
  the toast and the PLAY station's charge.  Nothing is asked, downloaded or
  connected.  dl/held run 0-99% over 25 s unless given a percent; "start" is the
  line before the engine knows the size.
  ui_strip_test <ok|fail|nolobby> -- that outcome and its pulse.
  ui_strip_test <esc|back> -- what that key or button does on the create screen.
  ui_strip_test screen <create|main|terms|steam|fit>, ui_strip_test off.
*/
void(string what, string arg) ui_strip_test =
{
	local float k;

	k = ST_NONE;
	if (what == "ask")       k = ST_ASK;
	else if (what == "wait") k = ST_WAIT;
	else if (what == "held") k = ST_HELD;
	else if (what == "dl")   k = ST_DL;

	if (k != ST_NONE)
	{
		// Over a real one, Cancel and ESC would act on what the fake hides.
		if (ui_join_pending || pj_addr != "" || dl_state == DL_ACTIVE)
		{
			print("ui_strip_test: a real join or download is in flight -- not faking over it\n");
			return;
		}
		ui_stt     = k;
		ui_stt_t0  = time;
		ui_stt_pct = -1;
		if (arg == "start")
			ui_stt_pct = -2;
		else if (arg != "")
			ui_stt_pct = bound(0, stof(arg), 100);
	}
	else if (what == "ok" || what == "fail" || what == "nolobby")
	{
		ui_stt = 0;
		if (what == "ok")
			ui_st_result(strcat("Installed ", ST_FAKEMAP), 1);
		else if (what == "fail")
			ui_st_result(strcat("Download of ", ST_FAKEMAP, " failed"), -1);
		else
			ui_st_result("No lobby: the directory did not answer -- playing locally", -1);
	}
	else if (what == "off")
	{
		ui_stt = 0;
		ui_st_msguntil = 0;
	}
	else if (what == "esc" || what == "back")
	{
		// Menu_InputEvent's ESC (ui_create_esc) and screen_create's back, without
		// a key or a click.
		if (menu_screen != SCREEN_CREATE)
			print("ui_strip_test: not on the create screen\n");
		else if (what == "esc")
		{
			k = ui_create_esc();
			if (k == 1)
				print("ui_strip_test: esc closed the leaderboard; still on the create screen\n");
			else if (k == 2)
				print("ui_strip_test: esc ended the join; still on the create screen\n");
			else if (k == 4)
				print("ui_strip_test: esc -- closed the menu\n");
			else if (k == 5)
				print("ui_strip_test: esc hid the Friends drawer; still on the create screen\n");
			else
				print("ui_strip_test: esc -- back to main\n");
		}
		else
		{
			k = ui_strip_cancel_join(FALSE);
			menu_screen = SCREEN_MAIN;
			print(sprintf("ui_strip_test: back%s -- back to main\n",
			              k ? " ended the join" : ""));
		}
	}
	else if (what == "screen")
	{
		// Patch 647: the two first-boot screens, to look at.  Neither word
		// answers a screen: an answer is a click or a key on it.
		if (arg == "terms" || arg == "termsfull" || arg == "steam")
		{
			print(sprintf("ui_strip_test: screen %s\n", arg));
			menu_screen = (arg == "steam") ? SCREEN_STEAM : SCREEN_TERMS;
			ui_tm_full = (arg == "termsfull");      // P796: the summary, or the cards
			ui_steam_t0 = time;
			return;
		}
		// ...and how the terms were last laid out: the panel against the window.
		if (arg == "fit")
		{
			print(sprintf("ui_strip_test: terms panel %g x %g, text %g px, %s, window %g x %g\n",
			              ui_tm_w, ui_tm_ph, tm_sz_x, ui_tm_two ? "two columns" : "one column",
			              ui_tm_sx, ui_tm_sy));
			print(sprintf("ui_strip_test: terms %s, journal box %g\n",
			              ui_tm_full ? "full" : "summary", ui_tm_jbox));
			return;
		}
		print(sprintf("ui_strip_test: screen %s\n", (arg == "create") ? "create" : "main"));
		if (arg == "create")
		{
			menu_screen = SCREEN_CREATE;
			ui_create_open();
			ui_refilter();
		}
		else
			menu_screen = SCREEN_MAIN;
		return;
	}
	else
	{
		print("ui_strip_test <ask|wait|held|dl [pct|start]|ok|fail|nolobby|off|screen create|main>\n");
		return;
	}

	// The line the strip will draw, from the same function that draws it.
	ui_status_update();
	print(sprintf("ui_strip_test: kind %g  %s%s\n", ui_st_kind, ui_st_text, ui_st_figs));
	print(sprintf("ui_strip_test: bar %g  cancel %g  charge %g on %g  pulse %g\n",
	              ui_st_frac, ui_st_cancel, ui_charge, ui_charge_on, ui_pulse));
};

// ROADMAP 9: the picked map's leaderboard, right of the field that names it --
// not in the footer, where it cost the status strip its Cancel below ~650 px.
// Dim and deaf with no map picked.  ui_button's look, but off the keyboard
// path: `d` or an arrow typed into the field moves sui's cursor (BACKLOG), and
// it would land here for Enter to open the panel.
void(vector pos, vector sz, string sel) ui_board_button =
{
	local float hot;

	if (sel == "")
	{
		sui_style_box(pos, sz, 7, COL_ROW, SUI_THEME_EDGE, 0.5);
		sui_text([pos_x + 8, pos_y + (sz_y - SZ_LABEL_H) * 0.5], SZ_LABEL,
		         "leaderboard", COL_DIM, 0.5, 0);
		return;
	}
	sui_action_element(pos, sz, "cs_board", sui_noop, TRUE);
	hot = sui_is_hovered("cs_board");
	sui_style_box(pos, sz, 7, hot ? COL_ROW_HOVER : COL_ROW, hot ? COL_ACCENT : SUI_THEME_EDGE, 1);
	sui_text([pos_x + 8, pos_y + (sz_y - SZ_LABEL_H) * 0.5], SZ_LABEL, "leaderboard",
	         hot ? COL_ACCENT : COL_TEXT, 1, 0);
	sui_tooltip_for("cs_board", "The picked map's main-track times: KSF, Momentum Mod and World of Surf's own lobbies.", 2);
	if (sui_is_released("cs_board"))
		Mlb_Open(sel, -1);
};

float(string label) ui_filter_chip_w =
{
	return stringwidth(label, TRUE, '12 12 0') + 12;
};

float(vector pos, string id, string label, float on) ui_filter_chip =
{
	local float w, hot;
	w = ui_filter_chip_w(label);
	sui_action_element(pos, [w, 24], id, sui_noop);
	hot = sui_is_hovered(id);
	sui_roundbox(pos, [w, 24], 7, on ? COL_ROW_SEL : COL_ROW, 1);
	if (hot) sui_style_box(pos, [w, 24], 7, COL_ROW_SEL, SUI_THEME_EDGE_HI, 1);
	sui_text(pos + '6 6 0', '12 12 0', label, on ? COL_ACCENT : COL_TEXT, 1, 0);
	return w;
};

string(float group, float f) ui_filter_label =
{
	if (group == 0) return f == 0 ? "any" : ftos(f);
	if (group == 1) return ui_mode_label(f);
	if (group == 2) return ui_srcf_label(f);
	if (group == 3) return "show all";
	return f == 0 ? "tier" : (f == 1 ? "incomplete first" : "completed first");
};

string(float group, float f) ui_filter_id =
{
	if (group == 0) return strcat("cs_tier", ftos(f));
	if (group == 1) return strcat("cs_mode", ftos(f));
	if (group == 2) return strcat("cs_srcf", ftos(f));
	if (group == 3) return "cs_showall";
	return strcat("cs_sort", ftos(f));
};

float(float width, float y) ui_map_filters =
{
	local float group, f, n, x, gw, cw, on, bit, next;
	local string heading, label, id, note;
	x = 16;
	note = ms_compsort ? MCard_DoneNote() : "";
	for (group = 0; group < 5; group = group + 1)
	{
		heading = group == 0 ? "Tier" : (group == 1 ? "Mode" : (group == 2 ? "Library" : (group == 3 ? "Extra" : "Sort")));
		n = group == 0 ? 11 : (group == 1 ? FS_NMODES : (group == 2 ? SRCF_NCHIPS : (group == 3 ? 1 : 3)));
		gw = stringwidth(heading, TRUE, '12 12 0') + 8;
		for (f = 0; f < n; f = f + 1)
			gw = gw + ui_filter_chip_w(ui_filter_label(group, f)) + 4;
		if (group == 4 && note != "") gw = gw + stringwidth(note, TRUE, '12 12 0') + 6;
		if (x > 16 && x + gw > width + 16) { x = 16; y = y + 30; }
		sui_text([x, y + 6], '12 12 0', heading, COL_DIM, 1, 0);
		x = x + stringwidth(heading, TRUE, '12 12 0') + 8;
		for (f = 0; f < n; f = f + 1)
		{
			label = ui_filter_label(group, f);
			id = ui_filter_id(group, f);
			bit = group == 1 ? ui_cat_bit(ui_mode_id(f)) : (group == 2 ? ui_srcf_bit(f) : 0);
			on = group == 0 ? (ms_tier == f) : (group == 1 ? (f == 0 ? ms_modes == FS_MODES_ALL : (ms_modes & bit) != 0) : (group == 2 ? ms_srcf == bit : (group == 3 ? ms_showall : ms_compsort == f)));
			cw = ui_filter_chip_w(label);
			if (x + cw > width + 16) { x = 16; y = y + 30; }
			x = x + ui_filter_chip([x, y], id, label, on) + 4;
			if (group == 0) sui_tooltip_for(id, f == 0 ? "Every tier, including untiered maps." : sprintf("MOM or KSF tier %g.", f), 2);
			if (group == 1) sui_tooltip_for(id, "Show/hide this gametype. The last selected type stays on.", 2);
			if (group == 2) sui_tooltip_for(id, "Map library for installed and downloadable maps.", 2);
			if (group == 3) sui_tooltip_for(id, "Also show maps without a picture or tier. Search always finds them.", 2);
			if (group == 4) sui_tooltip_for(id, "Your clean main finishes (WOS, Momentum Mod or KSF), tier order within each. Needs a linked account online; while unknown the list stays in tier order.", 2);
			if (!sui_is_released(id)) continue;
			if (group == 0) ms_tier = f;
			else if (group == 1) { next = ui_modes_click(ms_modes, f); if (next != ms_modes) ui_modes_set(next); }
			else if (group == 2) ms_srcf = bit;
			else if (group == 3) ui_showall_set(!ms_showall);
			else ui_compsort_set(f);
		}
		if (group == 4 && note != "")
		{
			sui_text([x + 2, y + 6], '12 12 0', note, COL_DIM, 1, 0);
			x = x + stringwidth(note, TRUE, '12 12 0') + 6;
		}
		x = x + 12;
	}
	return y + 34;
};

void(vector screensize) screen_create =
{
	local float rh, nx, inner, y, compact, actiony;
	local vector size, pos, namesize;
	MCard_Begin();
	if (ms_compsort) MCard_DoneWant();

	// The shared shell already reserved Friends/chat. Fill the remainder.
	size = screensize; pos = '0 0 0';
	inner = size_x - 32;
	compact = (inner < 760);
	rh = compact ? 160 : 128;
	nx = compact ? 140 : 176;
	actiony = compact ? 108 : 28;
	namesize = '20 20 0';
	ui_cs_size = size;
	ui_cs_lcols = ui_cs_lshow = 0;
	sui_style_panel(pos, size, 12, 1);
	sui_text('16 12 0', SZ_HEAD, "Maps", COL_ACCENT, 1, 0);
	sui_push_frame(pos, size);
	// Always visible: only the old collapse button is retired.
	y = ui_map_filters(inner, 48);

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

	string mhd;
	if (ms_nhidden > 0)
		mhd = sprintf("map  %s(%g of %g -- %g more searchable)", SUI_ESC_MUTED,
		              ms_viewcount, ms_count - ms_nvar, ms_nhidden);
	else
		mhd = sprintf("map  %s(%g of %g)", SUI_ESC_MUTED, ms_viewcount, ms_count - ms_nvar);
	sui_text([16, y], SZ_LABEL, mhd, COL_DIM, 1, 0);

	float lbw = max(120, stringwidth("leaderboard", TRUE, SZ_LABEL) + 16);
	ui_field_sel("cs_search", [16, y + 20], [inner - lbw - 8, 28],
	             ms_query, ms_query_cursor, "search maps...", sel);
	// The old search is selected, not wiped: typing replaces it and a
	// double-click on it still selects all.  After the field, which would
	// otherwise put the caret under the click.
	if (ms_query_stale)
		if (sui_is_clicked("cs_search"))
		{
			sui_text_select_all("cs_search", ms_query, ms_query_cursor);
			ms_query_stale = FALSE;
		}
	ui_board_button([16 + inner - lbw, y + 20], [lbw, 28], sel);
	y += 56;

	/*
	  ---- optional legacy lobby strip (off in the tabbed layout) -----------

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
	ui_cs_lcols = ui_cs_lshow = 0;
	if (cvar("ui_maps_lobbies"))
	{
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
		sui_roundbox(cp, crs, 8, sui_is_hovered("cs_lobterms") ? COL_ROW_HOVER : COL_ROW,
		             sui_is_hovered("cs_lobterms") ? 1 : 0.6);
		ui_thumb([cp_x + 3, cp_y + 2], [78, 44], -1, -1);
		sui_text([cp_x + 90, cp_y + 5], SZ_ROW,
		         "public lobbies are off", COL_TEXT, 1, 0);
		sui_text([cp_x + 90, cp_y + 26], SZ_ROW,
		         strcat(SUI_ESC_MUTED, "they send data to a server -- click to read what, and choose"),
		         COL_DIM, 1, 0);
		if (sui_is_released("cs_lobterms"))
			menu_screen = SCREEN_TERMS;

		y += ROW_H + 8;
	}
	else if (Lob_Count() > 0)
	{
		/*
		  A GRID, LOB_COLS across and at most LOB_ROWS_MAX down.  The list below
		  is derived from y, so every grid row costs it a row and needs no edit.

		  CELLS STAY PUT: Lob_Parse orders lobbies by port, so a click cannot
		  land on a neighbour that slid into place between two polls.  Narrow
		  screens drop columns below LOB_MIN_COL rather than squeezing names.
		*/
		float lgap  = 8;
		float lcols = min(LOB_COLS, Lob_Count());
		float lcolw = (inner - lgap * (lcols - 1)) / lcols;
		if (lcolw < LOB_MIN_COL)
		{
			// Fewer than Lob_Count() by construction: the test above just failed.
			lcols = floor((inner + lgap) / (LOB_MIN_COL + lgap));
			if (lcols < 1)
				lcols = 1;
			lcolw = (inner - lgap * (lcols - 1)) / lcols;
		}

		// Bounded by ROWS, not cells (build 67): a narrow screen that dropped to
		// fewer columns still spends at most LOB_ROWS_MAX list rows.  Port order
		// stays -- hiding empty lobbies would reorder cells every poll.
		float lshow = Lob_Count();
		if (lshow > lcols * LOB_ROWS_MAX)
			lshow = lcols * LOB_ROWS_MAX;
		ui_cs_lcols = lcols;
		ui_cs_lshow = lshow;

		/*
		  THE HEADING SAYS WHAT IS NOT BEING SHOWN, which is why it is drawn
		  here rather than above the essay where it used to be: it needs lshow.

		  A dropped row that nothing mentions is the same defect as the
		  under-count this build just fixed, one level up -- the picker would
		  show ten lobbies out of twelve and read exactly like a picker showing
		  all twelve.  m_lobby.qc's own note that extras are "dropped here rather
		  than drawn somewhere unreachable" was written when the cap was the
		  whole fleet and dropping meant nothing was lost; now something is, so
		  it gets a word.  The count is of lobbies, not of players, because
		  players is the number the MAP rows carry and saying it twice in
		  different units invites reading one as the other.
		*/
		string llbl = "public lobbies";
		if (lshow < Lob_Count())
			llbl = sprintf("public lobbies%s  -- showing %g of %g", SUI_ESC_MUTED, lshow,
			               Lob_Count());
		sui_text([16, y], SZ_LABEL, llbl, COL_DIM, 1, 0);
		y += 20;

		for (float li = 0; li < lshow; li = li + 1)
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
			sui_roundbox(lp, lrs, 8, sui_is_hovered(lid) ? COL_ROW_HOVER : COL_ROW,
			             sui_is_hovered(lid) ? 1 : 0.6);

			ui_thumb([lp_x + 3, lp_y + 2], [78, 44], lpage, lcell);

			// Text column: the cell less thumbnail, gutter and an 8 px margin.
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
				         ui_fit_text(strcat(SUI_ESC_BAD, "not"), 70, SZ_ROW), COL_DIM, 1, 0);
				sui_text([lp_x + 8, lp_y + 24], SZ_ROW,
				         ui_fit_text(strcat(SUI_ESC_BAD, "installed"), 70, SZ_ROW), COL_DIM, 1, 0);
			}

			/*
			  Line 2: the map, and "n / 32".  The count is RIGHT-ALIGNED and
			  fitted first, and the map gets what is left.  ui_fit_text cuts from
			  the end, so one "map  n / 32" string would lose the count -- the half
			  of the line a player choosing between five lobbies reads -- to any
			  long map name.
			*/
			string lcnt = ui_fit_text(sprintf("%s%g%s / %g", SUI_ESC_GOOD, Lob_Players(li),
			                                  SUI_ESC_MUTED, Lob_Max(li)), ltw, SZ_ROW);
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
		// lshow, not Lob_Count(): with the fleet larger than the grid the two
		// differ, and measuring the reserved height off the count rather than
		// off what was drawn would reserve rows nothing occupies and push the
		// map list down for empty space.
		float lrows = ceil(lshow / lcols);
		y += lrows * ROW_H + (lrows - 1) * lgap + 8;
	}

	}
	// ---- the list ------------------------------------------------------
	float by = size_y - 46;         // top of the start/back row
	vector ls = [inner, by - y - 12];
	ui_cs_rows = floor((ls_y - 2) / rh);
	ui_cs_rowheight = rh; ui_cs_list_top = y; ui_cs_list_bottom = y + ls_y;

	{
		sui_style_box([16, y], ls, 9, SUI_THEME_WELL, SUI_THEME_EDGE, 1);

		if (ms_viewcount == 0)
			sui_text([24, y + 10], SZ_ROW, "no matches", COL_DIM, 1, 0);
		else
		{
			// sui_list_view only emits rows inside the visible window, so this
			// loop costs per VISIBLE row -- about a dozen -- not per map.  That
			// is what lets a 1400-entry list scroll for nothing.
			sui_list_view_begin("cs_list", [17, y + 1], [ls_x - 2, ls_y - 2],
			                    [ls_x - 14, rh], ms_viewcount, ms_scroll, [0, 10]);

			// One fixed action block per card: beside its times when wide,
			// below its thumbnail when compact. Downloading never means Play.
			float dlg = compact ? 132 : 148;

			vector rp = '0 0 0';
			for (float idx = sui_list_item(rp); idx > -1; idx = sui_list_item(rp))
			{
				float real = stof(bufstr_get(ms_view, idx));
				float er = ui_eff(real);           // Patch 652: the build this row plays
				string rid = strcat("cs_row", ftos(idx));
				vector rs  = [ls_x - 14, rh];

				sui_action_element(rp, rs, rid, sui_noop);

				float on  = (real == ms_selected);
				float hot = sui_is_hovered(rid);
				if (on || hot)
					sui_roundbox(rp + '1 1 0', rs - '2 2 0', 7, on ? COL_ROW_SEL : COL_ROW_HOVER, 1);

				// Metadata is parsed only for visible cards. Keep times source-separated.
				{
					local float mn, mpage, mcell, mstages, mbonus, mlinear, cw, neww, pop;
					local string mtier, mktier, mnmf, sub, mode, dep;
					mn = tokenize(bufstr_get(ms_meta, real));
					mpage = mcell = -1; mstages = mbonus = mlinear = -1;
					if (mn > MT_UUID)
					{
						mlinear = strcmp(argv(MT_LINEAR), "-") ? stof(argv(MT_LINEAR)) : -1;
						mstages = strcmp(argv(MT_STAGES), "-") ? stof(argv(MT_STAGES)) : -1;
						mbonus = strcmp(argv(MT_BONUS), "-") ? stof(argv(MT_BONUS)) : -1;
						mpage = strcmp(argv(MT_PAGE), "-") ? stof(argv(MT_PAGE)) : -1;
						mcell = strcmp(argv(MT_CELL), "-") ? stof(argv(MT_CELL)) : -1;
					}
					ui_thumb([rp_x + 4, rp_y + 8], compact ? '128 72 0' : '160 90 0', mpage, mcell);
					cw = rs_x - nx - (compact ? 8 : 164);
					neww = !strcmp(bufstr_get(ms_new, real), "1") ? stringwidth("NEW", TRUE, namesize) + 4 : 0;
					mnmf = ui_fit_text(bufstr_get(ms_name, real), cw - neww, namesize);
					if (strcmp(bufstr_get(ms_zoned, er), "1")) mnmf = strcat(MAP_NOZONE_ESC, mnmf);
					sui_text([rp_x + nx, rp_y + 8], namesize, mnmf, (on || hot) ? COL_ACCENT : COL_TEXT, 1, 0);
					// NEW still means a sweep saw this name appear, not a recent release.
					if (neww)
						sui_text([rp_x + nx + 4 + stringwidth(mnmf, TRUE, namesize), rp_y + 8], namesize,
						         strcat(SUI_ESC_GOOD, "NEW"), COL_TEXT, 1, 0);
					mtier = bufstr_get(ms_momtier, real); mktier = bufstr_get(ms_ksftier, real);
					sub = sprintf("MOM %s | KSF %s", stof(mtier) > 0 ? strcat("T", mtier) : "-", stof(mktier) > 0 ? strcat("T", mktier) : "-");
					if (!strcmp(bufstr_get(ms_var, real), ""))
						sub = strcat(ui_srcname(stof(bufstr_get(ms_src, real))), " | ", sub);
					mode = ui_mode_name(stof(bufstr_get(ms_modev, real)));
					if (strcmp(mode, "")) sub = strcat(sub, " | ", mode);
					if (mstages > 0) sub = sprintf("%s | %g stages", sub, mstages);
					else if (mlinear == 1) sub = strcat(sub, " | linear");
					if (mbonus > 0) sub = sprintf("%s, %g bonus", sub, mbonus);
					pop = ui_map_players(er);
					if (pop >= 0) sub = sprintf("%s | %g playing", sub, pop);
					dep = ui_deps_text(real);
					if (strcmp(dep, "")) sub = strcat(sub, " | needs ", dep);
					if (strcmp(bufstr_get(ms_zoned, er), "1")) sub = strcat(MAP_NOZONE_ESC, "zones not listed^7 | ", sub);
					sui_text([rp_x + nx, rp_y + 50], '12 12 0', ui_fit_text(sub, cw, '12 12 0'), COL_DIM, 1, 0);
					if (strcmp(bufstr_get(ms_var, real), ""))
						ui_build_switch(compact ? rp + '4 84 0' : [rp_x + rs_x - 130, rp_y + 88], real, idx);
					MCard_Draw([rp_x + nx, rp_y + 32], cw, compact, bufstr_get(ms_name, er), rid);
				}

				/*
				  The download gutter.

				  Registered AFTER the row's own action element, which is what
				  makes the click land here and not on the row: the hit test
				  walks _action_elements back to front and sui_is_released only
				  fires for the topmost id (sui_sys.qc:409-418, 345-348).

				  Four states share the gutter.  A map being downloaded shows the
				  bar and the rate wherever it is in the list, so scrolling away
				  from it does not lose the progress; the button is only offered
				  when nothing is in flight, because the engine serialises
				  downloads anyway and two buttons that both do nothing is worse
				  than one that is plainly unavailable.
				*/
				/*
				  AN ACTION COLUMN, NOT A DOWNLOAD GUTTER.  Build 89.

				  It was reserved for the whole list and drawn on only the rows
				  that needed a download, so on a complete install it was 127 px
				  of nothing down every row -- "it looks so empty when no
				  download button is there".  Now the settled case has the
				  obvious action in it: Play.

				  ONE COLUMN, ONE QUESTION -- "what can I do with this row" --
				  and the answer is mutually exclusive by construction, because
				  ms_have is one value: "1" plays, "2" replaces, "0" fetches.
				*/
				if (dlg > 0 && bufstr_get(ms_have, er) == "1")
				{
					vector pp = [rp_x + (compact ? 4 : rs_x - 4 - dlg), rp_y + actiony];
					vector ps = [dlg - 4, compact ? 40 : 48];
					string pid = strcat("cs_play", ftos(idx));
					float  ph, pb;

					// ROADMAP 1: dimmed and deaf while a join is in flight, as
					// ui_launch refuses one then.
					pb = ui_join_busy();
					sui_action_element(pp, ps, pid, sui_noop);
					ph = sui_is_hovered(pid);
					if (pb)
						ph = FALSE;
					// A pill, filled under the cursor. One centred word, not two lines:
					// there is no second fact to say about a map you already have.
					sui_roundbox(pp, ps, ps_y * 0.5, ph ? COL_PLAY : COL_PLAY_HOT, pb ? 0.3 : 1);
					sui_text([pp_x + (ps_x - stringwidth("Play", TRUE, namesize)) * 0.5, pp_y + floor((ps_y - 20) * 0.5)],
					         namesize, "Play", ph ? SUI_THEME_WELL : COL_PLAY, pb ? 0.3 : 1, 0);

					/*
					  THROUGH ui_launch, not around it.  Selecting first and then
					  calling the single launch choke point is what keeps the
					  consent gate and the name gate in front of this button --
					  a direct ui_launch_local here would walk past both, which
					  is exactly the refactor ui_launch's own essay warns about.
					*/
					if (sui_is_released(pid))
					if (!pb)
					{
						ms_selected = real;
						ui_launch();
					}
				}
				else if (dlg > 0 && bufstr_get(ms_have, er) != "1")
				{
					vector gp = [rp_x + (compact ? 4 : rs_x - 4 - dlg), rp_y + actiony];
					vector gs = [dlg - 4, compact ? 40 : 48];
					string gid = strcat("cs_dl", ftos(idx));
					string mnm = bufstr_get(ms_name, er);
					float  mine = (dl_name == mnm);
					float  wrong = (bufstr_get(ms_have, er) == "2");

					if (mine && dl_afterlocal)
						sui_text([gp_x, gp_y + 4], SZ_ROW, strcat(SUI_ESC_MUTED, "after this game"), COL_DIM, 1, 0);
					else if (mine && dl_state == DL_ACTIVE)
					{
						// Track, then fill -- the scrubber idiom from
						// cl_watch.qc:3867.  The percentage is the engine's, and
						// it is 0 until the size is known, so the bar can sit at
						// zero while the rate already reads: that is honest, the
						// bytes are moving and the total is not yet agreed.
						sui_roundbox(gp, [gs_x, 6], 3, COL_ROW_HOVER, 1);
						if (dl_pct > 0)
							sui_roundbox(gp, [max(6, gs_x * bound(0, dl_pct / 100, 1)), 6], 3,
							             COL_ACCENT, 1);
						sui_text([gp_x, gp_y + 10], SZ_ROW,
						         (dl_rate > 0) ? ui_dl_rate(dl_rate) : "...",
						         COL_DIM, 1, 0);
					}
					else if (mine && dl_state == DL_OK)
						sui_text([gp_x, gp_y + 4], SZ_ROW, strcat(SUI_ESC_GOOD, "installed"), COL_TEXT, 1, 0);
					else if (mine && dl_state == DL_FAIL)
						sui_text([gp_x, gp_y + 4], SZ_ROW, strcat(SUI_ESC_BAD, "failed"), COL_TEXT, 1, 0);
					else if (dl_state == DL_ACTIVE)
						sui_text([gp_x, gp_y + 4], SZ_ROW, strcat(SUI_ESC_MUTED, "queued"), COL_DIM, 0.5, 0);
					else
					{
						sui_action_element(gp, gs, gid, sui_noop);
						float gh = sui_is_hovered(gid);
						sui_style_box(gp, gs, 7, gh ? COL_ROW_HOVER : COL_ROW,
						              gh ? COL_ACCENT : SUI_THEME_EDGE, 1);
						// A re-get is not the same offer as a download and must
						// not read like one: this row already has a playable
						// map, it is just the wrong cut of it.
						sui_text([gp_x + DL_PAD, gp_y + 2], SZ_ROW,
						         wrong ? "Wrong build" : "Download",
						         gh ? COL_TEXT : COL_ACCENT, 1, 0);
						sui_text([gp_x + DL_PAD, gp_y + 23], '12 12 0',
						         wrong ? strcat(SUI_ESC_WARN, "re-get ",
						                        ui_dl_size(stof(bufstr_get(ms_dlkb, er))))
						               : ui_dl_size(stof(bufstr_get(ms_dlkb, er))),
						         COL_DIM, 1, 0);
						if (sui_is_released(gid))
							ui_dl_start(mnm, wrong);
					}
				}

				if (sui_is_released(rid))
					ms_selected = real;
			}
			sui_list_view_end();
		}
	}

	MCard_End();

	// ---- start / status / back ----------------------------------------
	float  busy  = ui_join_busy();
	string stlbl = busy ? "joining..." : ((sel == "") ? "pick a map" : "start");
	float  sbw   = max(150, stringwidth(stlbl, TRUE, SZ_LABEL) + 16);   // ui_button's width
	if (ui_button("cs_start", [16, by], [150, 30], stlbl, (sel != "" && !busy)))
	if (!busy)
		ui_launch();

	ui_status_strip([16 + sbw + 24, by], size_x - 116 - 24 - (16 + sbw + 24));

	// ROADMAP 1: leaving ends a join -- one nobody can see must not connect later.
	// A download keeps going.
	if (ui_button("cs_back", [size_x - 116, by], [100, 30], "back"))
	{
		ui_strip_cancel_join(FALSE);
		menu_screen = SCREEN_MAIN;
	}

	sui_pop_frame();
};

// ---------------------------------------------------------------------------
//  Engine entry points.
//
//  m_display / m_hide / m_newmap do NOT exist in FTE -- they are DarkPlaces
//  only.  The set the engine actually looks up is at pr_menu.c:3386-3403.
// ---------------------------------------------------------------------------
float ui_boot_at, ui_boot_done, ui_boot_begin, ui_boot_init_ms;
float ui_boot_measured, ui_boot_first_ms, ui_boot_wait_ms, ui_boot_catalogue_ms;

void() m_init =
{
	ui_boot_begin = gettime(1);
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
	sui_style_init();

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
	registercvar("rec_hid_upload", "0", 0);
	ms_consent = ui_consent_read();
	ui_terms_publish(ms_consent);
	MU_Init();
	MF_Init();
	MC_Init();
	// Patch 1000: this install's account mark, as a proving lobby or the menu's signed
	// chat last said it; sent as userinfo `smark` so a private game can show profiles.
	registercvar("cl_self_mark", "", 32);
	MC_SelfMark(cvar_string("cl_self_mark"), TRUE);
	registercvar("ui_maps_filters", "0", 32);
	registercvar("ui_maps_large", "1", 32);
	registercvar("ui_maps_friends", "0", 32);
	registercvar("ui_maps_lobbies", "0", 0);
	registercvar("ui_friends_activity", "-1", 0);
	// Repair P731's level30 ui_updates bind too; menu commands reject that level.
	// P823: F2 opens the journal panel (ui_journal); ui_updates was its name before.
	if (checkbuiltin(localcmd_local))
	if (getkeybind(K_F2) == "" || getkeybind(K_F2) == "menu_save" || getkeybind(K_F2) == "ui_updates")
		localcmd_local("bind F2 ui_journal\n");
	if (ms_consent < FS_TERMS_VERSION)
		menu_screen = SCREEN_TERMS;

	// Patch 270.  Creates the public-lobby buffers and registers lobby_dir,
	// which SHIPS WITH A DIRECTORY URL -- the empty default was removed once it
	// became clear it was a step to be told about rather than a decision anyone
	// made.  Nothing is polled before an FS_TERMS_ONLINE acceptance either way;
	// see the consent essay at the top of m_lobby.qc.
	Lob_Init();

	ms_name = ms_src = ms_lst = -1;
	ms_tierv = ms_momtier = ms_ksftier = ms_momtsrc = ms_modev = ms_meta = ms_pbv = -1;
	ms_catv = ms_pblob = -1;
	ms_have = ms_new = ms_dlkb = -1;
	ms_wr = ms_dltier = ms_dataq = ms_deps = -1;
	ms_var = ms_varof = ms_pick = -1;
	ms_enabled = ms_zoned = -1;
	ms_bswrow = -1;
	// The saved value is read in ui_create_open, beside its registercvar.
	ms_showall = ms_applied_showall = 0;
	ms_compsort = ms_applied_compsort = 0;
	ms_selected = -1;
	ms_tier = ms_applied_tier = 0;
	// Both libraries, which is the state that lists everything.  Not saved, like
	// the tier chips it sits beside and unlike the gametype set.
	ms_srcf = ms_applied_srcf = 0;
	// The SAVED set is read when the create screen opens, beside its
	// registercvar (ui_create_open); this only keeps the set from being empty
	// before then.
	ms_modes = ms_applied_modes = FS_MODES_DEFAULT;
	ms_view = buf_create();

	// ms_bgfor must not start equal to ms_selected, or the first frame would
	// skip the load and the backdrop would stay flat until you picked twice.
	ms_bgpic = "";
	ms_bgfor = -2;

	// Declared bare and seeded here, the reason ms_query is: fteqcc folds
	// an initialised global scalar into a constant and refuses assignment.
	pj_addr = pj_map = "";

	// Absolute cursor: getmousepos then returns virtual-screen coordinates
	// rather than a delta (pr_menu.c:1116-1140), which is what sui expects.
	setcursormode(TRUE, "", '0 0 0', 1);

	// BESIDE ITS READER, not in some other file: cvar() on an unregistered
	// name auto-creates it as "" and a later registercvar declines to
	// overwrite, which is the trap this file has lost three features to.
	registercvar("ui_mapdl_gen", "0", 32);
	ui_dl_migrate_url();

	registercommand("ui_updates");
	registercommand("ui_journal");
	registercommand("ui_story");
	registercommand("ui_update_probe");
	registercommand("ui_notes");
	registercommand("ui_menu_probe");
	registercommand("ui_home_probe");
	registercommand("ui_profile_probe");
	registercommand("ui_maplist");
	registercommand("ui_browse");
	registercommand("ui_compsort");
	registercommand("ui_stats");
	registercommand("ui_build");
	registercommand("ui_mapnet");
	registercommand("ui_find");
	registercommand("ui_prejoin");
	registercommand("ui_join");
	registercommand("ui_strip_test");
	registercommand("ui_board_test");
	registercommand("ui_board");
	registercvar("ui_board_request", "", 0);
	cvar_set("ui_board_request", "");
	// Patch 498.  THE KEYBOARD CANNOT REACH A TEXT FIELD: sui moves its cursor by
	// hit test, so with the mouse parked off a field no key this VM consumes can
	// focus one -- and sui_text_input_focused, the flag that suppresses the WASD
	// navigation keys while a field is focused, is set from a MOUSE hit, so it
	// reads FALSE and w/a/s/d keep moving the cursor.  The field is therefore
	// unreachable, and once focused by mouse the keys are not given back to a
	// panel that is no longer up.  The focus is recorded by whoever typed last
	// and asked for here, where the screens are known.
	registercommand("ui_key");
	registercommand("ui_zonefetch");
	registercommand("ui_zoneprobe");
	registercommand("ui_bginfo");
	registercommand("ui_focus");
	registercommand("ui_cursor");
	registercommand("ui_click");
	registercommand("ui_hover");
	registercommand("ui_mouse");

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

	MM_Init();

	if (cvar("ui_bootcheck"))
	{
		print("^2World of Surf: menu.dat loaded\n");
		ui_maplist_print("surf_kitsune");

		if (cvar("ui_bootcheck") < 2)
			localcmd("quit\n");
		else
			m_open();
	}
	ui_boot_init_ms = rint((gettime(1) - ui_boot_begin) * 1000);
};

/*
  Patch 781 (Lex): the picker's list -- and its thumbnail atlases, which
  ui_meta_load starts -- is built half a second into the menu rather than on
  the first PLAY, so the picker opens loaded.  Not while in a game with the
  menu shut: there the load would be a hitch mid-run, and PLAY still loads it.
*/
void() ui_boot_preload =
{
	local float t;

	if (ui_boot_done)
		return;
	if (ms_count)
	{
		ui_boot_done = TRUE;
		return;
	}
	if (!ui_boot_at)
	{
		ui_boot_at = time + 0.5;
		return;
	}
	if (time < ui_boot_at)
		return;
	if (clientstate() != 1)
	if (!menu_active)
		return;
	ui_boot_done = TRUE;
	t = gettime(1);
	ui_create_open();
	ui_boot_catalogue_ms = rint((gettime(1) - t) * 1000);
	print(sprintf("^5maplist:^7 %g maps loaded at boot in %g ms\n", ms_count, ui_boot_catalogue_ms));
};

// screensize is the VIRTUAL screen -- equal to the framebuffer at
// vid_conautoscale 1.  Declaring this with a vector parameter matters: two
// float parameters would make the engine assume a DarkPlaces menu and hand
// over physical pixel sizes instead (pr_menu.c:3391-3395).
void(vector screensize) m_draw =
{
	local float shell, shellhead, bootstart;
	local vector fullsize, shellsize, shellpos, content;
	fullsize = screensize;
	cltime = gettime(0);            // P1084: client/cl_profile.qc's clock
	bootstart = 0;
	if (!ui_boot_measured) bootstart = gettime(1);
	// The bootcheck driver runs OUTSIDE the menu_active gate on purpose: past
	// the launch step the menu is closed and in-game, and it still has to take
	// the last screenshot and quit.
	if (cvar("ui_bootcheck") >= 2)
		ui_bootcheck_tick();

	// OUTSIDE THE menu_active GATE, like the bootcheck driver above and for a
	// related reason: a join in flight has to be able to TIME OUT and fall back
	// to a local map even if the menu stopped drawing, or the failure mode is a
	// button that did nothing and no message anywhere.  It is a no-op whenever
	// nothing is pending, which m_close guarantees after an ESC.
	ui_join_tick();

	// OUTSIDE THE GATE for the same reason again, and here it is load-bearing: a
	// map download keeps running in the engine after an ESC, and the only thing
	// that notices it FINISHED is this tick.  Gated, the player would close the
	// menu on a half-drawn bar, come back to a completed download still reading
	// as in-flight, and the row would never turn back into a playable map.
	Dl_Tick();
	ui_prejoin_tick();

	MF_Poll(menu_active && ui_browser_screen());
	MC_Poll(menu_active && (menu_screen == SCREEN_CHAT || ui_browser_screen()));
	MH_Poll();
	MP_Frame();                     // Patch 789: the menu's pictures
	Mlb_Poll();
	// Warm the catalogue on boot, even before the picker is opened. Mdl_Ask
	// owns consent, in-flight and one-minute refresh guards.
	Mdl_Ask();
	Mmm_Ask();                      // P1099
	if (mmm_fresh)
	if (menu_active)
	{
		mmm_fresh = FALSE;
		ui_maplist_changed();       // keeps the selection, resets the backdrop
	}
	Mzd_Pump();
	ui_boot_preload();
	ui_dlkb_step();                 // Patch 999

	// m_draw is called EVERY frame whether or not the menu has focus
	// (menu.c:168-176), so the gate is ours to enforce.
	if (!menu_active)
		return;
	if (!ui_boot_measured) ui_boot_wait_ms = max(0, rint((bootstart - ui_boot_begin) * 1000) - ui_boot_init_ms);

	// Re-filter only on an actual change.  ms_query is mutated by
	// sui_text_input during the previous frame's draw, so comparing against
	// the applied copy here is the cheapest place to notice.
	if (ms_query != ms_applied_query || ms_tier != ms_applied_tier
	    || ms_modes != ms_applied_modes || ms_srcf != ms_applied_srcf
	    || ms_showall != ms_applied_showall || ms_compsort != ms_applied_compsort)
		ui_refilter();
	else if (ms_compsort && mcd_ver != ms_applied_donever)
	{
		// New completion data or a build switch re-sorts in place, like ui_dlkb_step.
		local vector keepscroll;
		keepscroll = ms_scroll;
		ui_refilter();
		ms_scroll = keepscroll;
	}

	// ROADMAP 1: the strip's line, and the charge MM_Frame's camera reads.
	ui_status_update();

	// Patch 467.  Before sui_begin: the sim draws into render targets, and
	// nothing sui sets up (clipping, the hit list) may apply to those passes.
	if (cvar("milk_bootcheck"))
		MM_BootTick();
	MM_Frame(screensize);
	// MENU glass also belongs over a hosted/live world; HUD keeps its default.
	sui_style_glass = TRUE;

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
	if (menu_screen != SCREEN_TERMS)
	{
		ui_tm_jtouched = FALSE;         // P796: left unanswered, the box mirrors the cvar again
		ui_tm_f2 = FALSE;
		ui_tm_full = FALSE;             // P902: so the next entry opens on the summary and its box
	}

	// ROADMAP 9: the leaderboard panel lives only over the create screen.
	if (menu_screen != SCREEN_CREATE)
	if (Mlb_IsOpen())
		Mlb_Close("left the create screen");

	MU_Poll();
	// Root coordinates, exactly once; no panel may darken its own rectangle.
	ui_backdrop(fullsize);
	if (menu_screen == SCREEN_CREATE) ui_map_backdrop(fullsize);
	shell = (menu_screen == SCREEN_MAIN || menu_screen == SCREEN_CREATE || menu_screen == SCREEN_STORY
	         || menu_screen == SCREEN_VISUALS || menu_screen == SCREEN_MUSIC || menu_screen == SCREEN_CHAT || menu_screen == SCREEN_SETTINGS
	         || menu_screen == SCREEN_STATS);
	if (shell)
	{
		shellsize = MH_ShellSize(screensize);
		shellpos = MH_ShellOrigin(screensize);
		shellhead = shellsize_x < 900 ? 32 : 40;
		sui_push_frame(shellpos + [0, shellhead + 12], [shellsize_x, shellsize_y - shellhead - 12]);
		screensize = [shellsize_x, shellsize_y - shellhead - 12];
	}
	if (menu_screen == SCREEN_TERMS)
		screen_terms(screensize);
	else if (menu_screen == SCREEN_STEAM)
	{
		Lob_Poll();                 // Patch 647: the offer joins one (consent is online by now)
		screen_steam(screensize);
	}
	else if (menu_screen == SCREEN_JOURNAL)
		screen_journal(screensize);
	else if (menu_screen == SCREEN_NAME)
		screen_name(screensize);
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
		float acts = _action_elements_index;
		content = MH_ContentSize(screensize);
		screen_create(content);

		// ROADMAP 9: under the panel the screen is drawn but struck from sui's
		// hit list, or its rows would take hovers, clicks and the wheel (a
		// scroll view reads any hover, not only the topmost).
		if (Mlb_IsOpen())
		{
			_action_elements_index = acts;
			Mlb_Draw(content);
		}
	}
	else if (menu_screen == SCREEN_CHAT)
		MC_Draw(screensize);
	else if (menu_screen == SCREEN_SETTINGS)
		MH_Settings(screensize);
	else if (menu_screen == SCREEN_STORY)
		screen_story(MH_ContentSize(screensize));
	else if (menu_screen == SCREEN_STATS)
		MStats_Draw(MH_ContentSize(screensize));
	else if (menu_screen == SCREEN_VISUALS)
		MM_ScreenVisuals(screensize);
	else if (menu_screen == SCREEN_MUSIC)
	{
		menu_screen = SCREEN_VISUALS;
		MM_ScreenVisuals(screensize);
	}
	else
	{
		screen_main(screensize);
		Sty_Prefetch();             // P905: the ladder before the first STORY click
		ui_status_toast(screensize);
	}

	if (ui_browser_screen()) MH_Sidebar(screensize);
	if (shell)
	{
		sui_pop_frame();
		screensize = fullsize;
		MH_Tabs(screensize);
	}
	MU_Hint(screensize);
	MM_DrawFps(screensize);
	sui_menu_nav();
	Font_Reset();
	sui_end();
	// Queued releases are now consumed; a held synthetic click may release later.
	if (!sui_click_held())
		ui_synth_pending = FALSE;
	if (!ui_boot_measured)
	{
		ui_boot_first_ms = rint((gettime(1) - bootstart) * 1000);
		ui_boot_measured = TRUE;
	}
};

void() m_open =
{
	setkeydest(2);
	menu_active = TRUE;
	sui_keys_forget();      // Patch 655: a modifier let go while the game had the keys
	MM_Open();

	// The list is always open now (there is no ms_open any more), so all this
	// has to do is make sure there is something in it -- and, since build 57,
	// that the time column and the gametype set are current.  This is the door
	// ESC out of a game uses, and it lands straight on the create screen.
	if (menu_screen == SCREEN_CREATE)
		ui_create_open();
};

void() m_close =
{
	/*
	  CLOSING THE MENU ABANDONS A PENDING JOIN.  Build 67: the answer to
	  /api/join arrives several frames after the button, and without this an ESC
	  during that window would leave the intent standing -- so the reply would
	  land seconds later and `connect` somewhere the player had already decided
	  against.  The same hazard cl_scores.qc's rec_sb_wantrep documents for the
	  replay click, and the same answer.

	  Safe on the success path, which clears the intent and then closes: the
	  cancel finds nothing pending and returns.
	*/
	ui_join_cancel();
	Mlb_Close("menu closed");
	MM_Close();

	setkeydest(0);
	menu_active = FALSE;
	sui_keys_forget();
};

// A renderer restart destroys every render target (pr_menu.c:3499 looks this
// up by name); the milk rebuilds its targets on the next frame.
void() Menu_RendererRestarted =
{
	MM_Invalidate();
	_sui_rnd_forget();              // Patch 642: the corner masks went with the renderer
	MP_Lost();                      // Patch 789: and the pictures
};

float(float evtype, float scanx, float chary, float devid) Menu_InputEvent =
{
	// Native motion/navigation replaces helper focus only after SUI draws it.
	// A confirmation in this input batch can still name the old selection.
	if (!ui_synth_pending)
	if (ui_synth_aim)
	{
		if (evtype == IE_MOUSEABS)
			ui_synth_aim = FALSE;
		if (evtype == IE_MOUSEDELTA)
		if (scanx != 0 || chary != 0)
			ui_synth_aim = FALSE;
		if (evtype == IE_KEYDOWN)
		if (sui_input_dir(scanx) != '0 0 0')
			ui_synth_aim = FALSE;
		if (!ui_synth_aim)
			ui_synth_pending = TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_F2)
	if (ms_consent >= FS_TERMS_VERSION)
	{
		sui_text_unfocus();
		ui_f2_open("");
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_ENTER && (menu_screen == SCREEN_CHAT || menu_screen == SCREEN_MAIN))
	if (sui_text_has_focus("mc_text"))
	{
		MC_Send();
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE && menu_screen == SCREEN_CHAT)
	{
		menu_screen = SCREEN_MAIN;
		sui_text_unfocus();
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE && menu_screen == SCREEN_JOURNAL)
	{
		menu_screen = SCREEN_MAIN;
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE && menu_screen == SCREEN_STATS)
	{
		MStats_Close();
		return TRUE;
	}
	// Patch 667: paste.  ASKED FOR UNDER THE KEY, where a field had the keyboard
	// on the last frame: the engine is the judge of the chord, and the line
	// comes as IE_PASTE events, at once with no server connected and after its
	// own question to the player otherwise (sui_sys.qc has the rest).
	if (evtype == IE_PASTE)
	{
		sui_paste_char(chary);
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && (scanx == 'v' || scanx == K_INS))
	if (sui_text_focus())
	if (checkbuiltin(clipboard_paste))
	if (clipboard_paste())
		return TRUE;                    // a paste chord: not also a letter

	// The in-world panels: sui hit-tests in the panel's own pixels, so the
	// cursor is traced through the 3D camera onto the panel first.  A no-op on
	// every screen that is not on a panel.
	if (evtype == IE_MOUSEABS)
	{
		vector mp = MM_MouseToUI([scanx, chary]);
		scanx = mp_x;
		chary = mp_y;
	}
	float used = sui_input_event(evtype, scanx, chary, devid);

	/*
	  TAB MOVES THE TEXT FOCUS, BECAUSE NOTHING ELSE CAN (Patch 498).

	  The engine gives every non-F1..F15 key to Menu_KeyEvent and returns
	  (keys.c:4056-4063), so with the menu up a bind never runs: navigation here
	  is menuqc reading the bind STRING (sui_input_dir -> getkeybind) and moving
	  sui's cursor itself.  That cursor moves by HIT TEST, and a text field is not
	  an element it can land on and click -- so w/a/s/d/arrows can never reach one,
	  and the only focus route was the mouse.

	  TAB is sui's own text-focus key, bound to nothing in this game (no bind, no
	  handler anywhere in src/), so it is free and it is the key a player expects.
	  ONE FIELD PER SCREEN, and a ring over one element means "focus the field",
	  which is all a one-field screen can do honestly -- a shift+TAB backwards
	  walk over a ring of one would be a claim the code cannot keep (sui tracks
	  Shift since Patch 655; nothing here reads it).  A screen with no field
	  leaves the focus alone rather than clearing it, so TAB is inert there.
	*/
	if (evtype == IE_KEYDOWN && !used && scanx == K_TAB)
	{
		local string id = "";

		/*
		  ONE FIELD PER SCREEN, because that is how many there are: the create
		  screen's search box and the name screen's name box, and no other screen
		  has one at all (the address a create-screen join uses is picked from
		  /lobbies.json, not typed -- ui_addr_ok validates what the directory gave
		  it).  A ring over one element means "focus the field", and a screen with
		  none leaves the claim alone rather than clearing it, so TAB is inert
		  where there is nothing to type into.
		*/
		if (menu_screen == SCREEN_CREATE)
			id = "cs_search";
		else if (menu_screen == SCREEN_NAME)
			id = "nm_field";

		if (id != "")
			// Re-pressing TAB on a one-field screen re-claims that field, which is
			// what a ring of one means; the caret stays where the player left it,
			// because a key that cannot move focus anywhere else must not move the
			// text either.
			sui_field_focus(id);
		print(sprintf("ui_tab: focus %s\n", (id != "") ? id : "none"));
		return TRUE;
	}

	/*
	  THE MOUSE CURSOR IS THE ONLY THING THAT CAN CLICK AN ELEMENT, AND A
	  HEADLESS RUN HAS NO MOUSE.

	  sui's click path is _sui_mouse1_up, which hit-tests _cursor_position against
	  the elements and fires the topmost one's action; a key is turned into that by
	  sui_input_event, which synthesises a down on ENTER (+attack, K_GP_A) and an up
	  on its release.  So ENTER *should* activate the hovered element -- and it does
	  not reach anything here, for a reason worth having measured rather than
	  assumed: `ui_cursor` prints the UNTRANSFORMED cursor position while
	  _action_elements hold TRANSFORMED ones (sui_action_element calls
	  sui_transform_box on its own pos before storing it), and the same mismatch is
	  inside _cursor_kb_move, which compares the two.  Whether that is a real defect
	  in keyboard navigation or only in the diagnostic is NOT settled here -- the
	  cursor demonstrably moves for arrow keys, and ENTER demonstrably reaches no
	  element on two different screens -- and it is in BACKLOG with both readings.

	  What this arm needs is a click that does not depend on either: ui_click
	  delivers the same two events at an ABSOLUTE position, which is what the engine
	  gives for a real mouse (IE_MOUSEABS), and it fires the element whose stored
	  box contains that point.  It is a harness handle, registered like the others.
	*/

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
			{
				if (ui_tm_f2 && ms_consent >= FS_TERMS_VERSION)
					menu_screen = SCREEN_JOURNAL;   // P902: opened from F2, not the gate
				return TRUE;
			}

			// Patch 647: the Steam offer is an offer; ESC is its "not now".
			if (menu_screen == SCREEN_STEAM)
			{
				ui_steam_later();
				return TRUE;
			}

			// Patch 340: the name screen HAS a cancel -- unlike the terms --
			// and ESC is it.  Back to the screen the gate interrupted; the
			// launch stays interrupted, which is the point of a gate.
			if (menu_screen == SCREEN_NAME)
			{
				ui_name_resume = 0;
				menu_screen = ui_name_back;
				// The name field is sui's (ui_field -> sui_text_input), so its
				// focus flag is sui's too and it does not know the screen is
				// gone: without this the navigation keys stay dead on the screen
				// ESC just returned to.
				sui_text_unfocus();
				return TRUE;
			}

			// ROADMAP 9 and 1: the leaderboard panel, then a join in flight,
			// then the screen -- one per press (ui_create_esc).
			if (menu_screen == SCREEN_CREATE)
			{
				ui_create_esc();
				// THE FOCUS LEAVES WITH THE PANEL IT BELONGED TO: the create
				// screen's search field is the one that had it, and a flag that
				// outlived its panel would leave w/a/s/d dead in whatever is up
				// next -- the second half of the 498 defect.
				sui_text_unfocus();
				return TRUE;
			}

			if (menu_screen == SCREEN_STORY)
			{
				Sty_Esc();
				return TRUE;
			}
			if (menu_screen == SCREEN_VISUALS || menu_screen == SCREEN_MUSIC || menu_screen == SCREEN_SETTINGS)
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
	if (!strcmp(argv(0), "ui_chat"))
	{
		MC_Open();
		return TRUE;
	}

	// P902: ui_journal [notes|updates|journal|terms]; ui_updates is the Updates page.
	if (strcmp(argv(0), "ui_journal") == 0 || strcmp(argv(0), "ui_updates") == 0)
	{
		ui_f2_open((argv(0) == "ui_updates") ? "updates" : argv(1));
		m_open();
		return TRUE;
	}
	if (strcmp(argv(0), "ui_story") == 0)
	{
		Sty_Command(argv(1), argv(2));
		return TRUE;
	}
	if (!strcmp(argv(0), "ui_home_probe"))
	{
		MH_Probe();
		return TRUE;
	}
	if (strcmp(argv(0), "ui_menu_probe") == 0)
	{
		if (argv(1) == "boot")
		{
			print(sprintf("boot: MENU init %g ms; post-init wait %g ms; first draw %g ms; catalogue %g ms; maps %g\n",
				ui_boot_init_ms, ui_boot_wait_ms, ui_boot_first_ms, ui_boot_catalogue_ms, ms_count));
			return TRUE;
		}
		// `stale` arms the search as a launch from the picker does; `search` reads it.
		if (argv(1) == "stale")
			ms_query_stale = TRUE;
		if (argv(1) == "stale" || argv(1) == "search")
		{
			print(sprintf("ui_menu_probe: search %S caret %g sel %g stale %g\n", ms_query,
			              ms_query_cursor, strcmp(_sui_sel_id, "cs_search") ? -1 : _sui_sel_anchor,
			              ms_query_stale));
			return TRUE;
		}
		MC_Probe(); MCard_Probe(); MM_BcPanel("menu");
		print(sprintf("ui_menu_probe: glass %g\n", sui_style_glass));
		print(sprintf("browser_maps: selected %g frame %gx%g row %g list %g..%g name20 cards\n", ms_selected, ui_cs_size_x, ui_cs_size_y, ui_cs_rowheight, ui_cs_list_top, ui_cs_list_bottom));
		print(sprintf("ui_menu_probe: filters=%g large=%g friends=%g rows=%g maps=%g tier=%g scroll=%.1f\n",
			cvar("ui_maps_filters"), cvar("ui_maps_large"), cvar("ui_maps_friends"), ui_cs_rows,
			ms_viewcount, ms_tier, ms_scroll_y));
		print(sprintf("ui_menu_probe: friends_count=%g client=%g screen=%g friends_draw=%g friends_fresh=%g\n", cvar("ui_friends_count"), clientstate(), menu_screen, MF_Count(), MF_Fresh()));
		print(sprintf("ui_menu_probe: friends_direct=%g board=%S %s active=%g\n", MF_Direct(), serverkey("board"), MF_ProbeNote(), menu_active));
		return TRUE;
	}
	if (strcmp(argv(0), "ui_profile_probe") == 0)
	{
		// <8hex> opens that profile in the Friends panel; bare, reports what it holds.
		if (argv(1) != "")
		{
			menu_screen = SCREEN_CREATE;
			cvar_set("ui_maps_friends", "1");
			MFP_Open(argv(1), "probe");
		}
		MFP_Probe();
		return TRUE;
	}
	if (strcmp(argv(0), "ui_notes") == 0)
	{
		MU_NotesCommand(argv(1));
		return TRUE;
	}
	if (strcmp(argv(0), "ui_update_probe") == 0)
	{
		print(sprintf("ui_update_probe: consent=%g state=%s screen=%g client=%g\n", cvar("update_consent"), cvar_string("update_state"), menu_screen, clientstate()));
		MU_Probe();
		return TRUE;
	}
	if (argv(0) == "ui_maplist")
	{
		ui_maplist_print(argv(1));
		return TRUE;
	}

	if (argv(0) == "ui_browse")
	{
		ui_browse_print(argv(1));
		return TRUE;
	}

	if (argv(0) == "ui_compsort")
	{
		if (argv(1) == "refresh") MCard_DoneRefresh();
		ui_compsort_print();
		return TRUE;
	}

	if (argv(0) == "ui_stats")
	{
		if (argv(1) == "open") MStats_Open();
		else if (argv(1) == "close") MStats_Close();
		MStats_Probe();
		return TRUE;
	}

	if (argv(0) == "ui_build")
	{
		// strzoned: ui_build_print loads the list, which tokenizes.
		local string bmap, bpick;
		bmap = strzone(argv(1));
		bpick = strzone(argv(2));
		ui_build_print(bmap, bpick);
		strunzone(bmap);
		strunzone(bpick);
		return TRUE;
	}

	if (argv(0) == "ui_find")
	{
		// The search box's test twin: what the list holds for a query.
		ms_query = strzone(argv(1));
		ui_refilter();
		print(sprintf("ui_find: %s view %g first %s\n", ms_query, ms_viewcount,
		              (ms_viewcount > 0) ? bufstr_get(ms_name, stof(bufstr_get(ms_view, 0))) : "-"));
		strunzone(ms_query);
		ms_query = "";
		ui_refilter();
		return TRUE;
	}

	if (argv(0) == "ui_mapnet")
	{
		// The directory's list: where the fetch stands, and `ui_mapnet ask`.
		// `ui_mapnet sel`: the map `start` would launch (ui_launch's own reader).
		if (argv(1) == "sel")
		{
			print(sprintf("ui_mapnet: start plays %s\n", ui_selected_name()));
			return TRUE;
		}
		if (argv(1) == "ask")
		{
			mdl_state = MDLS_IDLE;
			mdl_next = 0;
			Mdl_Ask();
		}
		print(sprintf("ui_mapnet: state %g rows %g not kept %g\n", Mdl_State(), Mdl_Rows(), mdl_bad));
		return TRUE;
	}

	/*
	  ui_prejoin <map> [addr] -- THE HEADLESS TWIN OF CLICKING A LOBBY, the way
	  ui_dlmap is the Download button's.  It calls the REAL ui_prejoin rather
	  than reporting what it would decide: a second copy of the rule would agree
	  with a broken first one.  The address defaults to a port nothing listens
	  on, so a held join that completes proves the hold and the hand-off without
	  putting a test run on a public lobby.
	*/
	if (argv(0) == "ui_prejoin")
	{
		/*
		  BOTH ARGUMENTS STRZONED BEFORE ui_load_maps, and this is a bug fix
		  rather than caution.  argv() hands back a slot tokenize owns, and
		  ui_load_maps tokenizes every line of three data files -- so by the time
		  the call below ran, argv(1) was a word out of mapmeta.txt.  The first
		  cut of this arm ran all three cases against "surf_zor" and reported
		  held=0 for every one, which looks exactly like a feature that does
		  nothing.
		*/
		local string pjaddr, pjmap;
		pjmap  = strzone(argv(1));
		pjaddr = strzone((argv(2) != "") ? argv(2) : "127.0.0.1:27699");
		ui_load_maps();
		print(sprintf("ui_prejoin: %S held=%g state=%g name=%S\n", pjmap,
		              ui_prejoin(pjaddr, pjmap), dl_state, dl_name));
		strunzone(pjmap);
		strunzone(pjaddr);
		return TRUE;
	}

	if (argv(0) == "ui_lobbypop")
	{
		ui_lobbypop_print();
		return TRUE;
	}

	if (argv(0) == "ui_strip_test")
	{
		// Patch 642: the menu VM's own count of corner masks, as `hud_edit ui` prints the game's.
		if (argv(1) == "masks")
			print(sprintf("menu sui_masks made %g off %g last %g gen %g\n", sui_rnd_n, sui_rnd_off, sui_rnd_last, sui_rnd_gen));
		else
			ui_strip_test(argv(1), argv(2));
		return TRUE;
	}

	// ROADMAP 9: the leaderboard button's twin; m_board.qc has the forms.
	if (argv(0) == "ui_board") { Mlb_Command(); return TRUE; }
	if (argv(0) == "ui_board_test")
	{
		Mlb_TestCommand();
		return TRUE;
	}

	/*
	  ui_join <map> -- THE HEADLESS TWIN OF THE START BUTTON.  Build 67.

	  The button itself cannot be tested: it is a sui element picked with the
	  mouse, and no cfg in this tree can drive a cursor -- the same limit
	  cl_scores.qc records for the online row, which is why `board_replay` was
	  built as its twin.  This drives the identical path: the same Lob_JoinAsk,
	  the same ui_join_tick, the same ui_addr_ok/ui_host_allowed gates and the
	  same fallback to a local map.  What it skips is exactly the pick.

	  `ui_join` WITH NO ARGUMENT REPORTS instead of asking, so a config can
	  observe the state machine between waits without starting a second request
	  -- which is what makes the whole sequence falsifiable from a cfg.
	*/
	if (argv(0) == "ui_close")
	{
		/*
		  Patch 340's harness door, and a config one generally: the menu VM's
		  toggle entry only ever OPENS (m_toggle's wantmode 1 is "toggle on",
		  and `togglemenu` always sends 1), so a headless run that loaded the
		  menu had no console route back to the game -- and notmenu=0 skips the
		  whole in-game HUD stack, which is everything a screenshot harness
		  wants to see.  m_close is safe when already closed: it drops the key
		  dest and the active flag, which is exactly the state asked for.
		*/
		m_close();
		return TRUE;
	}

	/*
	  ui_dlmap <map> -- THE HEADLESS TWIN OF THE DOWNLOAD BUTTON, the same way
	  ui_join below is the start button's.  The button is a sui element picked
	  with the mouse and no cfg in this tree can drive a cursor, so without this
	  the only falsifiable claim about the whole download path would be "it
	  compiles".  It calls ui_dl_start, which is exactly what the button calls.

	  `ui_dlmap` WITH NO ARGUMENT REPORTS instead of starting, so a config can
	  watch the state machine across waits without kicking off a second
	  download -- the same split ui_join uses and for the same reason.  It also
	  prints whether the builtin resolved at all, which is the one failure that
	  looks identical to "nothing happened" from the outside: a #0 with no
	  :name compiles perfectly and binds to nothing.
	*/
	if (argv(0) == "ui_dlmap")
	{
		if (argv(1) == "")
		{
			// Two prints, not one: fteqcc caps a varargs call at 8 parameters
			// and the single-line version tripped it (Q302-class warning).
			print(sprintf("ui_dlmap: builtin %s, state %g (%s), map %S\n",
			              ui_dl_ready() ? "present" : "MISSING",
			              dl_state,
			              (dl_state == DL_IDLE)   ? "idle" :
			              (dl_state == DL_ACTIVE) ? "active" :
			              (dl_state == DL_OK)     ? "ok" : "failed",
			              dl_name));
			print(sprintf("ui_dlmap: %g%% at %g B/s, %g of %g bytes, after local %g\n",
			              dl_pct, dl_rate, dl_done, dl_total, dl_afterlocal));
			print(sprintf("ui_dlmap: dlstate %S\n", serverkey("dlstate")));
			ui_dlkb_finish();
			print(sprintf("ui_dlmap: offerable %g, wrongbuild %g, list %g\n",
			              ms_dlcount, ms_dlstale, ms_count));
		}
		else
		{
			// `ui_dlmap <map> force` is the headless twin of the Wrong build
			// button, the way `ui_dlmap <map>` is the Download one's. localkb
			// is the engine's mount-resolved answer and -1 means the binary
			// predates Patch 466.
			print(sprintf("ui_dlmap: asking for %S (have=%s, localkb=%g, force=%g)\n",
			              argv(1),
			              ui_file_exists(strcat("maps/", argv(1), ".bsp"))
			                  ? "yes" : "no",
			              ui_dl_kb_ready() ? mapfilekb(argv(1)) : -1,
			              (argv(2) == "force") ? 1 : 0));
			ui_dl_start(argv(1), (argv(2) == "force") ? 1 : 0);
			print(sprintf("ui_dlmap: state %g, map %S\n", dl_state, dl_name));
		}
		return TRUE;
	}

	if (argv(0) == "ui_name")
	{
		/*
		  Patch 340's headless surface.  `ui_name` alone reports what the gate
		  sees; `ui_name test <s>` judges a string WITHOUT setting it, which is
		  the interesting arm -- the defaults the gate exists for ("Player",
		  "(1)Player") are shapes no test can otherwise reach without editing
		  the config between runs.
		*/
		if (argv(1) == "test")
			print(sprintf("ui_name: %S -- %s\n", argv(2),
			              ui_name_default(argv(2)) ? "default" : "chosen"));
		else if (argv(1) == "field")
			/*
			  THE FIELD'S OWN TEXT, which is not what `ui_name` alone prints: that
			  reports the committed `name` cvar, so a keystroke that reached the
			  field and one that did not look identical there.  Grading typing needs
			  this one, and it is the only observable that separates "the focus claim
			  worked" from "the field is focused and the buffer was already drained".
			*/
			print(sprintf("ui_name: field %S caret %g\n", ui_name_field,
			              ui_name_caret));
		else if (argv(1) == "sel")
			// Patch 655: sui's one selection (its anchor, -1 none) and the
			// modifiers it believes are down.
			print(sprintf("ui_name: sel %g mods %g\n", _sui_sel_anchor, _sui_mods));
		else if (argv(1) == "screen")
		{
			// Force the screen up regardless of the current name, for the
			// screenshot harness: the gate's PREDICATE is testable from a log,
			// its LAYOUT is not.
			ui_name_back   = SCREEN_MAIN;
			ui_name_field  = "";
			ui_name_caret  = 0;
			ui_name_err    = "";
			ui_name_resume = 0;
			menu_screen    = SCREEN_NAME;
			print("ui_name: SCREEN_NAME forced\n");
		}
		else
			print(sprintf("ui_name: name %S -- %s\n", cvar_string("name"),
			              ui_name_default(cvar_string("name")) ? "default"
			                                                  : "chosen"));
		return TRUE;
	}

	if (argv(0) == "ui_key")
	{
		ui_synth_t = time;
		ui_synth_pending = TRUE;
		ui_synth_aim = TRUE;
		/*
		  ONE SYNTHETIC KEYPRESS THROUGH THE MENU'S OWN HANDLER.

		  A real key cannot reach a minimized harness (AGENTS.md) and the engine
		  has no builtin that runs Menu_KeyEvent, so this is the only way to drive
		  it headlessly -- and the more honest route for what is graded here,
		  because `ui_key enter` reaches the SAME code a real press reaches: the
		  verdict is about the handler, not about a duplicate of it.  The scan
		  comes from the engine's own table, so a name the bind layer would not
		  resolve does not resolve here either.

		    ui_key <name>          a press and a release of one key
		    ui_key <name> up       the release only
		    ui_key <name> down 65  a press carrying that unicode character

		  Prints `ui_key: <name> <scan> <unicode> took <n>`, `took` being what the
		  menu VM returned -- the same value keys.c reads out of Menu_KeyEvent.

		  NO argc() HERE: the menu VM has argv (#59) and no argc at all, so the
		  optional arguments are tested by argv() == "" the way every other
		  command in this file tests them.
		*/
		local float sc, uni, took;
		local string a1, a2, a3;

		a1  = argv(1);
		a2  = argv(2);
		a3  = argv(3);
		uni = (a3 != "") ? stof(a3) : 0;
		if (a1 == "")
		{
			print("ui_key: needs a key name (`ui_key enter`, `ui_key w`, "
			      "`ui_key w down 119`)\n");
			return TRUE;
		}
		sc = stringtokeynum(a1);
		if (sc <= 0)
		{
			print(sprintf("ui_key: no such key '%s'\n", a1));
			return TRUE;
		}
		took = Menu_InputEvent((a2 == "up") ? IE_KEYUP : IE_KEYDOWN, sc, uni, 0);
		print(sprintf("ui_key: %s %g %g took %g\n", a1, sc, uni, took));
		if (a2 != "up")
			Menu_InputEvent(IE_KEYUP, sc, uni, 0);
		return TRUE;
	}

	if (argv(0) == "ui_zonefetch")
	{
		if (argv(2) == "force") mzd_at = -60;
		Mzd_Fetch(argv(1));
		return TRUE;
	}
	if (argv(0) == "ui_zoneprobe")
	{
		print(sprintf("^5zones:^7 map %s pending %g ok %g play %s\n", mzd_map, mzd_req, mzd_ok, mzd_play));
		return TRUE;
	}
	if (argv(0) == "ui_bginfo")
	{
		local vector bgready;
		bgready = '0 0 0';
		if (ms_bgpic != "")
		if (checkbuiltin(drawgetimagesize_async)) bgready = drawgetimagesize_async(ms_bgpic);
		print(sprintf("^5backdrop:^7 selected %g remote %g ready %g %g pic %s\n", ms_selected, ms_bgremote, bgready_x, bgready_y, ms_bgpic));
		return TRUE;
	}
	if (argv(0) == "ui_focus")
	{
		/*
		  WHAT THE TEXT FIELD THINKS.  `ui_focus` prints it; `ui_focus <id>`
		  claims it, which is the keyboard route sui cannot provide and the reason
		  the panel's own handler has to ask: with the focus claimed, w/a/s/d go
		  to the field's text and the arrows still navigate.
		*/
		if (argv(1) != "")
			sui_field_focus(argv(1));
		// `flag` is sui's per-frame record and `held` is what gates the navigation
		// keys, so the pair is the whole observable; the text is not printed here
		// because the fields' contents are the screens' business (ui_name prints
		// the name one, and the create screen's query is in `ui_maplist`'s report).
		// keydest IS printed, and it is the one figure that explains a focus that
		// reads held 1 and then goes stale: m_draw returns at its `!menu_active`
		// gate before sui_begin, so when the engine has taken the key destination
		// away (a console, a prompt) nothing draws and sui_pre_draw never clears
		// the flag -- a focused field then keeps the navigation keys for as long as
		// the menu is not drawing them, which is the opposite failure from the one
		// being fixed and would otherwise read as this patch not working.
		print(sprintf("ui_focus: field '%s'  flag %g  held %g  keydest %g\n",
		              sui_field_focused(), sui_text_input_focused,
		              sui_text_focus(), getkeydest()));
		return TRUE;
	}

	if (argv(0) == "ui_cursor")
	{
		/*
		  WHERE sui's CURSOR IS, AND WHAT IT IS ON.

		  _cursor_position is what a navigation key moves and _cursor_relative_hover
		  is what a click would press, so the pair is the whole observable for "did
		  this key navigate": a WASD press that the focus flag suppressed leaves both
		  exactly where they were.  The engine has no builtin for either -- getmousepos
		  is the REAL cursor, which setcursormode parks -- and nothing else prints
		  them, which is why no arm in this tree has ever graded a menu navigation key.
		*/
		print(sprintf("ui_cursor: %g %g  hover %g %g  elements %g\n",
		              _cursor_position_x, _cursor_position_y,
		              _cursor_relative_hover_x, _cursor_relative_hover_y,
		              _action_elements_index));
		/*
		  THE BOXES, IN THE SAME SPACE THE HIT TEST USES.

		  _action_elements hold TRANSFORMED positions (sui_action_element calls
		  sui_transform_box on its own pos before storing it) while _cursor_position
		  is not transformed, and `ui_cursor` prints the latter -- so the two cannot
		  be compared from a log, and neither can an aim be computed from the panel
		  geometry a screen lays out.  This prints the pair a hit test actually
		  uses, which is the only way to aim `ui_click` at an element without
		  guessing: the first two cuts of this arm aimed at the field's authored box
		  and at a transformed estimate of it and hit nothing either time, with
		  `down 0 up 0` as the whole evidence.

		  NOT a loop over the element array with a `for` initializer: that exact
		  spelling segfaulted fteqcc (git-6681-5662b3a23), twice, with no message
		  and no output file -- once here and once inside sui_sys.qc.  The same loop
		  with the initializer hoisted compiles, so this is the compiler's and not
		  the code's; noted because a silent crash of the compiler reads as a hung
		  build rather than as a rejected construct.
		*/
		local int ei;
		int en = (int)min(MAX_ACTION_ELEMENTS, _action_elements_index);
		/*
		  BRACES ROUND THE LOOP BODY, and this one was learned by crashing the
		  compiler rather than by reading anything.  A braceless `for` binds ONE
		  statement (AGENTS.md records the trap for `if`), so the second print ran
		  outside the loop with `ei` at its end value -- past the array -- and
		  fteqcc (git-6681-5662b3a23) SEGFAULTED on it: no message, no output file,
		  exit 139, which reads as a hung build and not as a rejected construct.
		  The index is `int` for the same reason an out-of-range one is a crash
		  rather than a compile error.
		*/
		for (ei = 0; ei < en; ei++)
		{
			vector eb = _action_elements[ei].pos;
			vector es = _action_elements[ei].size;
			// SIX SPECIFIERS AND NOT EIGHT: sprintf drops everything past its
			// eighth argument with only a warning, so the id and the box go on one
			// line and kb_nav_disabled and the hit test on the next.
			print(sprintf("ui_element %g [%s] %g %g %g %g\n",
			              (float)ei, _action_elements[ei].id, eb_x, eb_y, es_x, es_y));
			print(sprintf("ui_element %g kbdis %g inside %g\n", (float)ei,
			              _action_elements[ei].kb_nav_disabled,
			              is_2dpoint_in_bbox(_cursor_position, eb, es)));
		}
		return TRUE;
	}

	if (argv(0) == "ui_click")
	{
		ui_synth_t = time;
		ui_synth_pending = TRUE;
		ui_synth_aim = TRUE;
		/*
		  ONE MOUSE CLICK AT AN ABSOLUTE POSITION.

		  The pair a real mouse delivers: IE_MOUSEABS to move the cursor (which
		  sets both _cursor_position and _cursor_relative_hover, the latter being
		  what a click's action callback receives), then KEYDOWN/KEYUP of K_MOUSE1
		  so sui_input_event runs _sui_mouse1_down and _sui_mouse1_up.  Absolute is
		  the point: it is the one route that does not depend on where the keyboard
		  cursor happens to be, so it clicks the element it is aimed at.

		    ui_click <x> <y>

		  Prints the click and the focus it left behind, because "the click focused
		  the field" and "the click hit nothing" are otherwise the same silence.
		*/
		local float x, y, d1, u1;

		x = stof(argv(1));
		y = stof(argv(2));
		/*
		  THE CURSOR HAS TO BE MOVED THROUGH sui's OWN MOVER, NOT THROUGH AN EVENT,
		  AND THE MODE HAS TO BE PUT BACK.

		  IE_MOUSEABS sets _cursor_position and nothing else, while the hover set
		  (_hover_actions, which _sui_mouse1_down copies into the hold set that a
		  release is matched against) is filled by _sui_mouse_move -- so an
		  absolute-position event alone leaves hold 0 and the release hits nothing.
		  Measured, not reasoned about: `ui_element 0 [nm_field] ... inside 1` at the
		  same instant the click reported `down 0 up 0`.  There is no setcursormove
		  in the menu VM either, so the mover is called directly -- with is_mouse
		  TRUE and _cursor_is_mouse_active set first, because with either missing it
		  returns before the hover pass, and the frame's sui_end then calls
		  _retarget_kb_cursor, which moves the cursor back to the element nearest the
		  keyboard's last one.

		  AND IT LEAVES THE CURSOR IN MOUSE MODE unless the mode is put back, which
		  is not a detail: while _cursor_is_mouse_active is set, sui_end skips
		  _retarget_kb_cursor and _cursor_kb_move's own activate is a no-op, so the
		  navigation keys stop moving the cursor altogether -- and "the focus
		  suppressed them" would then be indistinguishable from "the click parked
		  the cursor".  C6 in the arm is the check that it was put back.
		*/
		activate_mouse_cursor();
		_sui_mouse_move([x, y, 0], TRUE);
		d1 = Menu_InputEvent(IE_KEYDOWN, K_MOUSE1, 0, 0);
		u1 = Menu_InputEvent(IE_KEYUP, K_MOUSE1, 0, 0);
		deactivate_mouse_cursor();
		print(sprintf("ui_click: %g %g  down %g up %g  cursor %g %g\n",
		              x, y, d1, u1, _cursor_position_x, _cursor_position_y));
		// Separate print, and not a seventh specifier on the line above: sprintf
		// drops everything past its eighth argument with only a warning, and a
		// print that reports the wrong value under the right label is worse than
		// two prints.
		print(sprintf("ui_click: focus '%s' held %g\n",
		              sui_text_input_focused_id, sui_text_focus()));
		return TRUE;
	}

	if (argv(0) == "ui_hover")
	{
		/*
		  A MOUSE HOVER THAT STAYS (Patch 606). Tooltips answer a mouse hover only,
		  and `ui_click` above ends in keyboard mode, so without this no cfg could
		  put one on screen.

		    ui_hover <x> <y>   park the mouse cursor there, in mouse mode
		    ui_hover           report it, and whether a tip is up and whose
		    ui_hover @<id> [dx dy]   Patch 610: the middle of that control as last
		                       drawn, plus an offset. With `ui_mouse` this is a drag,
		                       aimed without a pixel in the cfg.
		*/
		if (substring(argv(1), 0, 1) == "@")
		{
			local int hi;
			local float found;
			int hn = (int)min(MAX_ACTION_ELEMENTS, _action_elements_index);
			found = FALSE;
			for (hi = 0; hi < hn; hi++)
			{
				if (strcmp(_action_elements[hi].id, substring(argv(1), 1, -1)) == 0)
				{
					activate_mouse_cursor();
					_sui_mouse_move(_action_elements[hi].pos + _action_elements[hi].size * 0.5
					                + [stof(argv(2)), stof(argv(3)), 0], TRUE);
					ui_synth_t = time;
					ui_synth_aim = TRUE;
					found = TRUE;
				}
			}
			if (!found)
				print(sprintf("ui_hover: no control [%s]\n", substring(argv(1), 1, -1)));
		}
		else if (argv(1) != "")
		{
			activate_mouse_cursor();
			_sui_mouse_move([stof(argv(1)), stof(argv(2)), 0], TRUE);
			ui_synth_t = time;
			ui_synth_aim = TRUE;
		}
		print(sprintf("ui_hover: %g %g  mouse %g  tip %g [%s] aim %g pending %g\n", _cursor_position_x,
		              _cursor_position_y, _cursor_is_mouse_active, sui_tip_visible, sui_tip_id,
		              ui_synth_aim, ui_synth_pending));
		return TRUE;
	}

	// Patch 610: the button alone, where `ui_hover` parked the cursor. Down, a
	// move, up is a drag, which `ui_click` (both at once) cannot be.
	if (argv(0) == "ui_mouse")
	{
		local float mtook;
		// Patch 655: a click by this command is no more the player's hand than
		// ui_click's (Patch 647 stamped that one and ui_key, and left this door).
		ui_synth_t = time;
		ui_synth_pending = TRUE;
		ui_synth_aim = TRUE;
		mtook = Menu_InputEvent((argv(1) == "down") ? IE_KEYDOWN : IE_KEYUP, K_MOUSE1, 0, 0);
		print(sprintf("ui_mouse: %s took %g  cursor %g %g\n", argv(1), mtook,
		              _cursor_position_x, _cursor_position_y));
		return TRUE;
	}

	if (argv(0) == "ui_join")
	{
		if (argv(1) == "")
		{
			print(sprintf("ui_join: state %g (0 idle 1 asking 2 ready 3 failed)"
			              " req %g map %S\n",
			              Lob_JoinState(), ui_join_pending, Lob_JoinMap()));
			print(sprintf("  addr %S timed %g why %S\n",
			              Lob_JoinAddr(), Lob_JoinTimed(), Lob_JoinWhy()));
			// ui_online_opt(), NOT cvar(): reading it bare here is what
			// switched online play off just by asking about it.  See the
			// essay over that function.
			print(sprintf("  lobby_dir %S  ui_play_online %g  rec_terms %g\n",
			              cvar_string("lobby_dir"), ui_online_opt(),
			              cvar("rec_terms")));
			return TRUE;
		}

		if (!Lob_JoinAsk(argv(1)))
		{
			print("ui_join: nothing to ask -- no lobby_dir, or the online tier "
			      "has not been accepted\n");
			return TRUE;
		}
		ui_join_pending = TRUE;
		print(sprintf("ui_join: asked %S for %S\n",
		              cvar_string("lobby_dir"), argv(1)));
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
