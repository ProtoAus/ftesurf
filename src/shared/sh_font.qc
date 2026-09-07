/*
===========================================================================
  sh_font.qc -- real fonts, shared by CSQC and MenuQC.

  THE PROBLEM.  The engine builds exactly one glyph atlas, at eight pixels:

      font_default = Font_LoadFont(gl_font.string, 8, 1, ...)   r_2d.c:1300

  and every drawstring at any other size rescales that one bitmap.  Build 2
  worked around it by keeping every size a whole multiple of 8, which makes
  the upscale an exact nearest-neighbour and stops it going soft -- but a
  32 px glyph is still an 8 px glyph blown up 4x, and at that size there is
  no arrangement of eight pixels that looks like a letter.  No choice of
  size fixes this; the atlas is the ceiling.

  THE FIX.  loadfont (#357, present in BOTH modules -- cl_defs.qc:1616 and
  m_defs.qc:642) bakes a TrueType face at each size you name, and the draw
  path then picks the baked size closest to the one asked for
  (PR_CL_ChooseFont, pr_menu.c:114-132) and scales from THAT.  Bake the
  sizes actually drawn and the scale factor is 1.0 everywhere.

  FreeType is statically linked in this build -- AVAIL_FREETYPE at
  config_fteqw.h:114, -DLINK_FREETYPE at :227, and there is no freetype DLL
  beside the exe -- so this needs no extra runtime.  Font_LoadFreeTypeFont
  locates the face with a plain FS_FLocateFile (gl_font.c:1910), so a
  gamedir-relative path is all it wants.

  FAILURE IS NOT FATAL.  loadfont returns 0 -- "return default on failure",
  pr_menu.c:259 -- and 0 is FONT_DEFAULT, the bitmap font.  So a missing or
  unreadable .ttf degrades to exactly what build 2 shipped rather than to a
  blank screen.  Font_Set is written so that path needs no caller changes.
===========================================================================
*/

float ui_font_ui;               // Roboto           -- labels, rows, readouts
float ui_font_display;          // Bebas Neue       -- title, the big speed number
float ui_font_mono;             // Google Sans Code -- the left-hand number columns
float ui_font_ready;            // all three loaded; false = something is on the bitmap

/*
  The size ladders.

  Only sizes that are actually drawn belong here: each one is a separate
  baked atlas, and ChooseFont picks by nearest, so an unbaked size is not an
  error -- just a scale.  FONT_SIZES caps a slot at 16 (pr_menu.c:101).

  The UI ladder covers hud_scale 1 and 2 (8/16 and 16/32) plus the menu's
  16/24/32, with 12/20/28 for the in-between scales.
*/
#define FONT_UI_SIZES       "8 12 16 20 24 28 32"
#define FONT_DISPLAY_SIZES  "24 32 40 48 64 80"

/*
  BUILD 21 -- THE MONOSPACED FACE, AND WHY ITS LADDER IS DENSER THAN THE OTHERS.

  gfx/fonts/GoogleMed.ttf is Google Sans Code Medium, and it is genuinely fixed
  pitch: every glyph in the face advances exactly 0.6 em -- digits, letters,
  '+', '-', '.' and the space alike.  (Its `post` table claims isFixedPitch 0,
  which is simply wrong in the file and is why you cannot trust that flag; the
  hmtx advances are the measurement that counts.)  Roboto has TABULAR digits --
  all ten are 0.562 em -- but proportional everything else, so a column of rows
  like "-37 e  0.66s" lines up on the numerals and then drifts on the units.

  That uniformity is the whole point for the two left-hand blocks: a row is as
  wide as its CHARACTER COUNT and nothing else, so a column's worst case can be
  computed rather than measured, and the layout stops depending on which digits
  happen to be on screen.

  IT IS ALSO WIDER.  0.6 em against Roboto's 0.562 for a digit, and much wider
  for narrow glyphs -- Roboto's '.' is 0.264 em and its 'i' 0.243, where this
  face charges 0.6 for both.  So switching a block to this face and changing
  nothing else makes it BIGGER, which is the opposite of what build 21 was asked
  for.  The size constants at the two call sites are cut to pay for it, and the
  column offsets in Timer_DrawSplits are re-derived from 0.6 em rather than
  inherited.

  THE DENSE LADDER is what makes that possible.  The UI ladder steps in fours
  below 32, so at hud_scale 2 the only sizes reachable near the splits block are
  12, 16 and 20 -- there is no "a little smaller than 16".  Font_Px snaps to the
  nearest RUNG, so asking for 15 on the UI ladder gets you 16 and the request is
  silently dropped.  Ten rungs of two make "squish it a little" an operation
  that exists.  FONT_SIZES caps a slot at 16 (pr_menu.c:101) and this is 11.

  CONSEQUENCE FOR CALLERS, and it is the trap in this change: the SAME requested
  size can snap to a different rung on this ladder than it did on the UI one.
  Font_Px(18) was 16 as UI text and is 18 here.  So a call site moved to this
  face must have its constant re-checked against the rendered pixel size, not
  copied across.
*/
#define FONT_MONO_SIZES     "8 10 12 14 16 18 20 22 24 28 32"

float ui_font_tries;

/*
  THE LADDERS, READ BACK.

  ChooseFont picks the baked size nearest the one asked for and scales from it,
  so drawing at a size that is not on the ladder is not an error -- it is a
  resample, and it looks like one.  hud_scale 2 with a 9 px constant asks for
  18 against a ladder whose neighbours are 16 and 20: a 0.9x downscale of an
  antialiased glyph, which is exactly the soft, slightly-wrong text you notice
  next to the crisp text beside it.

  Rather than hand-pick constants that happen to land at hud_scale 1 and 2 --
  which is what the HUD was doing, correctly by coincidence in every place but
  one -- snap at draw time.  Then hud_scale 1.5, or any size anyone adds later,
  is right by construction.

  Parsed from the same string that was handed to loadfont, so there is one
  definition of the ladder rather than two that can drift apart.  Both ladders
  live in one array so Font_Px can select a range instead of duplicating its
  loop per face (a QC array cannot be passed by name).
*/
float ui_lad[32];
float ui_lad_ui_first,   ui_lad_ui_n;
float ui_lad_disp_first, ui_lad_disp_n;
float ui_lad_mono_first, ui_lad_mono_n;
float ui_font_cur;              // the slot Font_Set last selected

float(string sizes, float first) Font_ParseLadder =
{
	local float i, n;

	n = tokenize(sizes);
	if (first + n > 32)
		n = 32 - first;
	for (i = 0; i < n; i = i + 1)
		ui_lad[first + i] = stof(argv(i));
	return n;
};

/*
  Font_Px -- the nearest baked size, or `want` unchanged when there is nothing
  to snap to.

  Returning `want` for the bitmap fallback is deliberate: that atlas is a single
  8 px bake and every size is a scale of it, so snapping would change the layout
  without improving anything.  cfg/default.cfg's r_font_linear 0 plus whole
  multiples of 8 is what handles that case, and it still does.

  BUILD 21: the gate is PER FACE, not the blanket ui_font_ready it used to be.
  With three faces the old test made one missing .ttf stop the other two
  snapping -- so deleting the mono file would have quietly made the menu and the
  timer resample, a regression with no visible cause.  Each branch now requires
  its own slot to be non-zero, which is the same test one face at a time and
  also stops ui_font_cur == 0 (Font_Reset, the bitmap) matching a face whose
  load returned 0.  ui_font_ready is left to drive the retry and the warning,
  where wanting all three IS the right question.
*/
float(float want) Font_Px =
{
	local float i, first, n, best, bd, d;

	if (ui_font_display && ui_font_cur == ui_font_display) { first = ui_lad_disp_first; n = ui_lad_disp_n; }
	else if (ui_font_ui && ui_font_cur == ui_font_ui)      { first = ui_lad_ui_first;   n = ui_lad_ui_n;   }
	else if (ui_font_mono && ui_font_cur == ui_font_mono)  { first = ui_lad_mono_first; n = ui_lad_mono_n; }
	else                                                   return want;

	if (n <= 0)
		return want;

	best = ui_lad[first];
	bd   = fabs(want - best);
	for (i = 1; i < n; i = i + 1)
	{
		d = fabs(want - ui_lad[first + i]);
		if (d < bd)
		{
			bd   = d;
			best = ui_lad[first + i];
		}
	}
	return best;
};

void() Font_Init =
{
	ui_font_ui      = loadfont("fsui",   "gfx/fonts/Roboto.ttf",
	                           FONT_UI_SIZES, -1, 0, 0);
	ui_font_display = loadfont("fsdisp", "gfx/fonts/BebasNeueRegular.ttf",
	                           FONT_DISPLAY_SIZES, -1, 0, 0);
	ui_font_mono    = loadfont("fsmono", "gfx/fonts/GoogleMed.ttf",
	                           FONT_MONO_SIZES, -1, 0, 0);

	ui_lad_ui_first   = 0;
	ui_lad_ui_n       = Font_ParseLadder(FONT_UI_SIZES, 0);
	ui_lad_disp_first = ui_lad_ui_n;
	ui_lad_disp_n     = Font_ParseLadder(FONT_DISPLAY_SIZES, ui_lad_disp_first);
	ui_lad_mono_first = ui_lad_disp_first + ui_lad_disp_n;
	ui_lad_mono_n     = Font_ParseLadder(FONT_MONO_SIZES, ui_lad_mono_first);

	// 7 + 6 + 11 = 24 rungs against ui_lad[32].  Font_ParseLadder clamps rather
	// than overruns, but a silently truncated ladder is a face that snaps to the
	// wrong size, so the headroom is worth stating where the ladders are added.
	ui_font_ready = (ui_font_ui != 0 && ui_font_display != 0 && ui_font_mono != 0);
	ui_font_tries = ui_font_tries + 1;

	if (!ui_font_ready && ui_font_tries >= 3)
	{
		// Worth a real print rather than a dprint: everything still works,
		// but it looks like build 2 and the reason is not otherwise visible.
		print("^3FTESurf: TrueType fonts unavailable -- falling back to the 8px bitmap.\n");
		print("^3         expected gfx/fonts/Roboto.ttf, BebasNeueRegular.ttf and GoogleMed.ttf\n");
	}
};

/*
  Font_Check -- retry, at most twice, then stop asking.

  loadfont only actually bakes anything when the renderer is up
  (pr_menu.c:334, `if (qrenderer > QR_NONE)`); called earlier it allocates
  the slot, loads nothing, and hands back a handle that draws as the default
  font.  m_init in particular runs early enough for that to be a real
  possibility, and the failure would be invisible -- the menu would simply
  look like it did before.

  Bounded because loadfont re-bakes every size on each call, so an
  unconditional per-frame retry would be a per-frame font rebuild.
*/
void() Font_Check =
{
	if (ui_font_ready || ui_font_tries >= 3)
		return;
	Font_Init();
};

/*
  Font_Set / Font_Reset.

  drawfont is a global the engine reads on the next draw call, so these are
  bracketing calls rather than a parameter.  Passing a slot of 0 is
  harmless -- it IS the default font -- which is what makes the failed-load
  path need no special casing at any call site.
*/
void(float slot) Font_Set  = { drawfont = slot; ui_font_cur = slot; };
void()           Font_Reset = { drawfont = FONT_DEFAULT; ui_font_cur = FONT_DEFAULT; };
