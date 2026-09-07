/*
===========================================================================
  cl_gfx.qc -- the Source-renderer settings, as a menu instead of as a list
  of cvars nobody can remember.

  Asked for as "a menu like the save lock menu, but for graphic settings
  off/on for these effects", alongside "I still don't know what 1 and 2 are".
  Those are the same request: the modes are not obscure because they are
  complicated, they are obscure because a number in a console tells you
  nothing about what it does.  Every row here spells its current mode out in
  words, so `hl2_water 1` is "Cheap reflection" rather than 1.

  It is deliberately the save-lock menu's shape -- same header, same rows,
  same digit-driven interaction, same colours -- because there is no reason
  for a second idiom, and because the muscle memory transfers.  The one
  difference is what a digit DOES: the save-lock menu's digits are verbs on
  one list, and these are one verb (cycle) on twenty-six different settings.

  MAP-LATCHED ROWS ARE MARKED, and that mark is load-bearing.  Some of these
  are CVAR_SHADERSYSTEM and apply on the next frame; the rest are read once
  while the BSP is being parsed, which no shader flush revisits.  Changing one
  of those and seeing nothing happen is indistinguishable from a broken
  setting unless the menu says so first -- and key 7 is the map load it is
  asking for.
===========================================================================
*/

float ui_gfx_open;              // the menu is up
float ui_gfx_page;              // 0-based; see the paging note below
float ui_gfx_loadtime;          // cltime when this map's CSQC came up

/*
  WHY THIS PAGES, when ten rows fit on screen perfectly well.

  The first cut put rows 1..9 on their own digit and hung the tenth on `-`,
  because ten settings do not fit in nine digits.  That row was Decals, and it
  was effectively unreachable: nothing on screen suggests `-`, and the digit it
  looks like it wants -- 0 -- is Close.  A row you cannot press is worse than a
  row that is not there, because it reads as a broken menu rather than a missing
  feature.

  So the digits get split by kind instead of by count: 1..6 act on the six rows
  of the current page, and 7/8/9 are the menu's own verbs on EVERY page.  A digit
  never means two different things depending on where you are, which is the
  property that lets this be driven without reading it.  The list has since grown
  from ten settings to twenty-six and cost four more keystrokes, which is the
  whole point of having paged rather than found a tenth key.
*/
#define GFX_ROWS     27         // highest row index (Patch 254 added Map fog)
#define GFX_PER_PAGE 6          // digits 1..6; 7 reloads, 8/9 page, 0 closes

void() Gfx_RegisterCvars =
{
	registercvar("hud_gfx_x", "0.018", CVAR_ARCHIVE);
	// Header + six rows + four verbs + a footer is a tall block; 0.10 is the
	// highest start that still clears the timer, and it has to clear the strafe
	// bar at the bottom.  Paging keeps this height fixed however many settings
	// the table grows to.
	registercvar("hud_gfx_y", "0.10", CVAR_ARCHIVE);

	// Bindable, so it does not have to live on one key we chose.
	registercommand("gfx_menu");

	// See Gfx_DrawMissing.  On by default: the thing it warns about is
	// indistinguishable from a broken engine until you are told otherwise.
	// CVAR_ARCHIVE since build 33 -- turning the banner off and having it come
	// back on the next launch is the same defect the seta note on Gfx_Cycle
	// describes, in miniature.
	registercvar("fs_missingwarn", "1", CVAR_ARCHIVE);

	// CSQC_Init runs once per map load, so this is the map's own zero.
	ui_gfx_loadtime = cltime;
};

/*
  "All of surf_utopia's textures are missing -- I believe the mount isn't
  working correctly."

  It is not.  surf_utopia is a TF2 map: thirteen of its materials live in
  Team Fortress 2's VPKs, which ftesurf/fs_addons.txt deliberately does not
  mount because CS:GO's and TF2's two big archives are 85% of everything the
  engine indexes and cost thirteen seconds of every launch for the benefit of
  two maps out of 1308.  The loader has said so by name since build 11 --
  it names the map, the materials and the one line that fixes it.

  It said so into a map load's several hundred lines of console output, which
  is not a place anyone reads.  The information was complete and the delivery
  was wrong, and the result was a correct symptom paired with the wrong cause.

  So the count comes out onto the screen, over the checkerboard it is
  explaining, for twenty seconds.  Time-limited rather than permanent because
  it is entirely reasonable to play a map you already know is missing textures,
  and a banner you cannot dismiss becomes a banner you stop reading -- which is
  the failure this is fixing, moved somewhere new.
*/
void(vector scr) Gfx_DrawMissing =
{
	local vector p;
	local float n, age, a, sz;

	if (!cvar("fs_missingwarn"))
		return;

	/*
	  FTESurf Build 38: the count that decides whether to draw is not the raw count.

	  hl2_unresolved counts every name the loader could not resolve, including names
	  that are in the map's texdata string table and on no surface at all -- nothing
	  a player can walk up to and see.  Patch 233 measures which of them are on a
	  drawn face or a prop and publishes that separately, and this banner is for the
	  player, so it draws on that one.

	  The console still lists everything either way, and `hl2_missing` says which is
	  which.  hl2_unresolved is still what the count on screen reports, because "3
	  materials did not resolve" and "1 of them is visible" are different claims and
	  the honest banner makes the first one.
	*/
	if (cvar("hl2_unresolved_visible") < 1)
		return;

	n = cvar("hl2_unresolved");     // set by the hl2 plugin at the end of load
	if (n < 1)
		return;

	age = cltime - ui_gfx_loadtime;
	if (age > 20)
		return;
	a = 1;
	if (age > 17)
		a = (20 - age) / 3;

	Font_Set(ui_font_ui);
	sz = Font_Px(10 * ui_cv_scale);
	// Below the timer block (which runs to ~0.10 with its "ready" line) and well
	// above the strafe bar at ~0.42.  Measured against a 1280x720 grab, not
	// guessed: the first placement sat exactly on top of "ready".
	p  = [scr_x * 0.5, scr_y * 0.20, 0];

	/*
	FTESurf Build 36: the banner stops naming asset packs.

	It carried the same two hardcoded fs_load lines the console used to, and Patch
	231 has just established how often that advice is wrong -- 593 of the library's
	1411 maps reference content that NO pack supplies, and surf_demise, whose three
	misses are a mistyped $bottommaterial and two prop skins that exist nowhere, was
	being told to mount CS:GO by both the console AND this banner.

	The console now works out which of four things is actually true, using what
	fs_automount published (fs_automount_state).  This has no business guessing a
	second, different answer three lines high in the middle of the screen -- so it
	says what it can see and points at the one place that knows.
	*/
	HUD_TextC(p, sprintf("%g material%s did not resolve on this map",
	                     n, (n == 1) ? "" : "s"),
	          sz, '1.00 0.45 0.35', a);
	HUD_TextC([p_x, p_y + sz * 1.4],
	          sprintf("first: %s", cvar_string("hl2_unresolved_first")),
	          sz * 0.85, '0.88 0.82 0.78', a * 0.9);
	HUD_TextC([p_x, p_y + sz * 2.6],
	          "console:  hl2_missing  lists every one and says what each of them is.",
	          sz * 0.72, '0.72 0.78 0.90', a * 0.85);
	HUD_TextC([p_x, p_y + sz * 3.5],
	          "fs_missingwarn 0 hides this.",
	          sz * 0.72, '0.60 0.64 0.70', a * 0.8);

	Font_Reset();
};

/*
  ONE LINE PER SETTING.

  This was four parallel if-chains -- cvar, label, values, value-names -- and at
  ten rows that was merely repetitive.  At twenty-three it stops being
  checkable: the
  failure mode is a row whose names have drifted out of step with its values, and
  nothing about four chains in four functions makes that visible.  Here a row is
  one line and the drift is a mismatched count you can see.

  Fields, separated by `|`:

      0  cvar
      1  label
      2  the values it cycles through, space-separated
      3  what each value MEANS, `;`-separated, in the same order as field 2
      4  "*" when the value only takes effect on the next map load

  Field 3 is the whole reason the menu exists.  It is positional against field 2
  rather than threshold-tested against the cvar, which is what the old
  Gfx_ValueName did: a threshold chain is a second, independent encoding of the
  same list, and the two can disagree.

  ORDER IS BY WHAT YOU ARE LOOKING AT, not by which file owns the cvar: page 1
  is the surfaces you can see change while you watch, page 2 is reflections and
  detail, page 3 is what the map LOAD builds, page 4 is how props and models are
  lit.  The `*` rows cluster towards the back because that ordering happens to be
  the same as instant-to-latched.

  Build 20 inserted Reflections at the head of page 2 and pushed the rest down
  one, which moved Lightmap onto the lighting page and Areaportals onto the last
  one -- both of which read better where they now are.

  BUILD 33 AUDITED THE WHOLE TABLE AGAINST THE PLUGIN, twice: once by reading
  VBSP_Init (mod_vbsp.c:6064-6346, where every hl2_* cvar in existence is
  registered, in that one function), and once by pulling the cvar name strings
  straight out of the shipped fteplug_hl2_x64.dll, so the list could not be a
  source-tree fiction.  Three results, and the first is the surprising one:

    1. NOTHING HERE IS A NO-OP.  Every row's cvar has a live read; none is
       behind an #if 0, none is D3D-only.  The brief was "remove the ones that
       don't work" and the honest answer is that there were none to remove.

    2. Two real settings were MISSING -- hl2_animated (row 4) and hl2_propdist
       (row 13).  Both shipped, both measured (Patch 195 and Patch 193), and
       neither reachable without typing the cvar.  hl2_animated defaults to 0,
       so the feature was off AND unreachable.

    3. One row LIED about when it applies: Decals was unmarked, and is read
       during the map-load entity walk.  See row 12.

  Excluded on purpose, so "all of them" has a boundary that can be defended:
  hl2_lt_face (its description and its group are both the string "TEST", and it
  has no up-front registration at all, so it does not exist until a Source map
  has loaded), hl2_displacement_scale (CVAR_CHEAT), hl2_contents_remap (a
  bit-name table, not a cyclable value), hl2_unresolved/_first (status OUTPUTS
  the plugin writes -- Gfx_DrawMissing above already consumes them), and
  r_novis/r_texdiag (engine diagnostics the plugin borrows rather than owns:
  the plugin's `hl2_novis` C variable registers the console name `r_novis`, so
  there is no hl2_ cvar there to expose).
*/
string(float row) Gfx_Def =
{
	// -- page 1: the look, all CVAR_SHADERSYSTEM, all instant -----------------
	if (row == 1)  return "hl2_water|Water|0 1 2 3|Flat sheet;Cheap reflect;Full reflect;Dithered|";
	if (row == 2)  return "hl2_refract|Glass|0 1 2|Opaque;Refracting;Dithered|";
	if (row == 3)  return "hl2_translucent|Translucent|0 1|Opaque;As authored|";
	/*
	  BUILD 33, and it belongs on this page because it is the same kind of thing
	  as the three above it: CVAR_SHADERSYSTEM, one read at material generation
	  (mat_vmt.c:1114), applied on the next frame.

	  Patch 195 is what made it work -- img_vtf.c had `frames = 1;//vtf->numframes;`,
	  so a 331-frame flipbook like surf_demise's smoke could not cycle no matter
	  what the material asked for.  It defaults to 0, which means that until this
	  row existed the feature was both off and unreachable.
	*/
	if (row == 4)  return "hl2_animated|Animated|0 1|Off;On|";
	if (row == 5)  return "hl2_dither_alpha|Dither scale|0.15 0.30 0.55 0.80 1|15%;30%;55%;80%;100%|";
	if (row == 6)  return "hl2_dither_force|Dither level|0 0.15 0.25 0.40 0.55 0.70 0.85 1|Per material;15%;25%;40%;55%;70%;85%;100%|";
	/*
	  BUILD 20: marked map-latched, which it should always have been.

	  It clears $envmap while a material is GENERATED, so it takes effect only on
	  materials generated after the change -- and a shader that already loaded a
	  reflectcube keeps it across a regenerate, because Shader_Reset preserves
	  defaulttextures.  So "off" on an already-loaded map is partial at best, and
	  a row that claims to be instant when it is not is the exact failure this
	  whole `*` convention exists to prevent.  Reflections (row 8) is the one to
	  reach for if you want it off NOW.
	*/
	if (row == 7)  return "hl2_envmap|Env maps|0 1|Off;On|*";

	// -- page 2: reflections and surface detail -------------------------------
	/*
	  The master of the two rows below it, and it sits above them for that reason.

	  Env maps and Cubemaps both act while the map or the material is being
	  BUILT, so neither can reach a material that is already built -- which is
	  what "both off and one map still reflects" turned out to be.  This one is
	  in the renderer, at the point of use, so it applies to the next frame and
	  cannot be outrun by a cached BSP or a stale shader.  Not latched, and the
	  missing `*` is the honest claim rather than an omission.
	*/
	if (row == 8)  return "r_reflectcube|Reflections|0 1|Off;On|";
	if (row == 9)  return "hl2_cubemaps|Cubemaps|0 1|Off;On|*";
	/*
	  Works, and stays ungreyed -- but it does NOT reach Water or Refract
	  surfaces: mat_vmt.c:984 excludes those two material types by name, so
	  glass and water keep their normal maps whatever this row says.  Noted
	  here and in default.cfg rather than dimmed, because the row IS live on
	  every ordinary material, and dimming a working row would put a new lie
	  where build 33 removed an old one.
	*/
	if (row == 10) return "hl2_bumpmap|Bump maps|0 1|Off;On|";
	if (row == 11) return "vbsp_skyroom|3D skybox|0 1|Off;On|";
	/*
	  BUILD 33: GAINED ITS `*`, which it should have had from the start.

	  Read once, at cl_decals.qc:195, during the entity-lump walk -- so at map
	  load.  The comment there says so outright ("vbsp_decals 0 no longer skips
	  the walk, it only skips the PLACING"), and this table went on claiming the
	  row was instant.  That is exactly the failure the `*` convention exists to
	  prevent, committed by the convention's own table.
	*/
	if (row == 12) return "vbsp_decals|Decals|0 1|Off;On|*";

	// -- page 3: what the map LOAD builds -------------------------------------
	/*
	  OVERLAYS is the map's OTHER kind of decal -- the ones VBSP bakes into
	  lump 45 as oriented quads instead of writing as entities.  230 of the 1310
	  shipped maps carry them and none of them drew until Patch 246.

	  THE ROW IS ON vbsp_overlays, AND THAT IS DELIBERATE.  There are two switches
	  and only one of them can work from this menu:

	    vbsp_overlays   read by the CSQC entity walk, once per map load.  Key 7
	                  restarts the map, which re-initialises CSQC, so the walk
	                  runs again and the row applies.  Hence the `*`.
	    hl2_overlays  read inside the BSP loader, which key 7 does NOT re-run:
	                  `retry` is `map_restart`, and Mod_ForName hands back the
	                  CACHED world model unless the .bsp's mtime moved.  So no
	                  amount of pressing 7 can change it, and it is console-only
	                  for the same reason hl2_displacement_scale is.

	  Measured, not reasoned: with developer 1 the loader prints "VBSP: <map>:
	  N of N baked overlays synthesised", and that line appears exactly once --
	  on the first load -- however many times you press 7.  Which also means
	  every `*` row below that is read at BSP-load time has the same problem;
	  that is a separate defect and is not fixed here.
	*/
	if (row == 13) return "vbsp_overlays|Overlays|0 1|Off;On|*";

	/*
	  SPRITES and SPOTLIGHTS, Patch 248.  Source's sprite entities, which were
	  point entities and so were being dropped whole -- 34909 of them across 551
	  maps, none of which had ever drawn.

	  Both are read by the CSQC entity walk, exactly like Overlays above, so key
	  7 genuinely applies them and the `*` is honest on both rows.

	  TWO ROWS AND NOT ONE, because they are different purchases.  Sprites are
	  11232 small quads -- the lamp glows, the fires, the flat billboard trees --
	  and mostly cost fill.  Spotlights are 23677 LARGE additive light shafts,
	  the single biggest class in the family, on 413 maps; they are much more
	  likely to be the thing somebody wants gone, and folding them into one
	  switch would have meant losing every glow to turn off the shafts.
	*/
	if (row == 14) return "vbsp_sprites|Sprites|0 1|Off;On|*";
	if (row == 15) return "vbsp_spotlights|Light shafts|0 1|Off;On|*";

	/*
	  BUILD 33, and the one row on this page that is NOT map-latched: read per
	  prop per frame in VBSP_PrepareFrame (mod_vbsp.c:4790), so it bites at once.

	  It is also the largest framerate dial in the family, which is why it was
	  worth finding.  Patch 193 measured surf_demise's start: 2350 static props,
	  every one declaring FadeMaxDist 0, median distance 24,185 units -- 4.11M of
	  the frame's 5.2M draw indices, 25.6ms of its 26.9ms.  Opaque batches across
	  this row's own value list, from the same viewpoint:

	      Unlimited  27163      12k  15618      4k  5923
	          20k    20227       8k  11590

	  CVAR_ARCHIVE in the plugin, and the ONLY member of the family that is --
	  see the seta note on Gfx_Cycle for what build 33 did about the other 22.
	*/
	if (row == 16) return "hl2_propdist|Prop distance|0 20000 12000 8000 4000|Unlimited;20k;12k;8k;4k|";
	if (row == 17) return "hl2_hidetools|Tool brushes|0 1|Shown;Hidden|*";
	if (row == 18) return "hl2_areaportals|Areaportals|0 1|Closed;Open|*";
	if (row == 19) return "hl2_propcollision|Prop collide|0 1 2 3|None;VPhysics;Bbox;Mesh|*";
	if (row == 20) return "hl2_dispcollision|Disp collide|0 1|None;Normal|*";
	// Which of a map's two lighting lumps the BSP parse READS, so it belongs
	// with the load rather than with the prop lighting on the next page.
	if (row == 21) return "hl2_favour_ldr|Lightmap|0 1|HDR;LDR|*";

	// -- page 4: prop and model lighting --------------------------------------
	/*
	  All five are marked `*` and all five deserve it -- but only one for the
	  reason you would guess.  hl2_lt_baked_scale is read at BSP load.  The other
	  four are read PER MODEL PER FRAME (VBSP_LightPointValues), so on the
	  plugin's own account they ought to apply instantly, and its registration
	  comment at mod_vbsp.c:6283 still says they do.

	  They do not, and the reason is on this side of the fence: r_modellight_cache
	  (default 1, renderer.c:187) reuses a prop's light sample until the prop
	  moves or r_modellight_seq bumps, and NOTHING bumps that when an hl2_lt_*
	  cvar changes.  So on a map with no animated lightstyles they sit visibly
	  still until a reload.  The `*` is right; the plugin's comment is what is
	  wrong.  Recorded because a future reader will otherwise "correct" the mark
	  and make the menu lie again.
	*/
	if (row == 22) return "hl2_lt_baked|Prop light|0 1|Ambient cube;VRAD bake|*";
	if (row == 23) return "hl2_lt_baked_scale|Prop bright|1 2 3|Raw;x2;x3|*";
	if (row == 24) return "hl2_lt_min|Prop ambient|0 8 16 32 64|Off;8;16;32;64|*";
	if (row == 25) return "hl2_lt_scale|Model light|160 200 255 320|160;200;255;320|*";
	if (row == 26) return "hl2_lt_srgb_mag|Model gamma|0 1|Linear;sRGB|*";
	/*
	  The map's own fog.  Appended rather than slotted in next to `3D skybox`
	  where it belongs by subject, because these rows are addressed BY NUMBER --
	  `gfx_menu cycle N` takes one, and ui_gfx_page remembers a position across
	  builds -- so inserting in the middle silently moves every row below it
	  under someone's cursor.  Grouping is not worth that.
	*/
	if (row == 27) return "vbsp_fog|Map fog|0 1|Off;On|";

	return "";
};

/*
  The nth `sep`-separated field of s.

  Hand-rolled rather than tokenize()d because tokenize splits on whitespace and
  two of the five fields contain spaces on purpose.  A dozen lines buys the
  one-line row definitions above, which is a trade worth making once.

  strstrofs rather than a substring(s,i,1) scan: this runs six times a frame
  while the menu is up, and a per-character scan would mint ninety temporary
  strings per field where one builtin call per separator does.  The end of the
  string terminates the last field, so a definition needs no trailing separator
  and row 20 reads the same as row 1.
*/
string(string s, float n, string sep) Gfx_Field =
{
	local float start, e;

	start = 0;
	while (n > 0)
	{
		e = strstrofs(s, sep, start);
		if (e < 0)
			return "";          // fewer fields than asked for
		start = e + 1;
		n = n - 1;
	}

	e = strstrofs(s, sep, start);
	if (e < 0)
		return substring(s, start, -1);
	return substring(s, start, e - start);
};

string(float row) Gfx_Cvar  = { return Gfx_Field(Gfx_Def(row), 0, "|"); };
string(float row) Gfx_Label = { return Gfx_Field(Gfx_Def(row), 1, "|"); };

// Rows whose value is read once while the map loads: the cvar takes the new
// value, the LOOK does not, until there is another load to read it.
float(float row) Gfx_NeedsReload =
{
	return Gfx_Field(Gfx_Def(row), 4, "|") == "*";
};

/*
  WHY THIS IS A FUNCTION AND NOT A SIXTH FIELD.

  Three rows in this table can be set, read back correctly, and still do
  nothing, because something ELSE decides whether they are consulted at all.
  That is the same class of confusion `*` exists for -- a setting that appears
  not to work is indistinguishable from a broken one -- so it gets the same
  treatment: say so, on the row, at the moment it is true.

  A field would have to carry the reason AND the condition, and one of the three
  has two different reasons depending on which condition fires.  Worse, the
  condition would then live in code while its text lived in the table, which is
  the "second, independent encoding that can disagree" the header condemns.  So
  both live here, together, where they cannot drift apart.

  Returns "" when the row is live, otherwise the reason it is not.
*/
string(float row) Gfx_Inert =
{
	local string cv;

	cv = Gfx_Cvar(row);

	/*
	  The dither pair only reaches a material that is BEING dithered, and that
	  is decided by the two rows above them: hl2_water 3 is the dithered water
	  mode, hl2_refract 2 the dithered glass one.  In any other mode
	  VMT_DitherScale is never reached (mat_vmt.c:219, :1461) and both rows are
	  inert whatever they read.
	*/
	if (cv == "hl2_dither_alpha" || cv == "hl2_dither_force")
	{
		if (cvar("hl2_water") != 3 && cvar("hl2_refract") != 2)
			return "needs dithered";

		// And once Dither level is set at all it replaces the per-material
		// alpha outright (mat_vmt.c:196-199), so Dither scale is not consulted.
		// Two rows, one of which silently wins.
		if (cv == "hl2_dither_alpha" && cvar("hl2_dither_force") > 0)
			return "set by Dither level";

		return "";
	}

	// No sky_camera in the entity lump means there is no second scene to draw
	// and the toggle has nothing to toggle.  vbsp_skyroom_have is set during the
	// same walk that reads vbsp_decals (cl_decals.qc:242-249).
	if (cv == "vbsp_skyroom" && !vbsp_skyroom_have)
		return "no sky_camera";

	// Same treatment: only ~201 of the 1337 maps author any fog at all, so on
	// the rest the toggle has nothing to toggle and should say so rather than
	// look broken.  Both counters are set by Fog_LoadFromWorld (cl_fog.qc).
	if (cv == "vbsp_fog" && !vbsp_fog_count && !vbsp_fog_skyhave)
		return "map has no fog";

	return "";
};

/*
  Which entry of the row's value list the cvar is currently sitting on.

  NEAREST, not equal, because the cvar can hold anything -- someone may have
  typed hl2_dither_alpha 0.42 -- and an exact match would then never be found,
  so the row would read as its first entry and cycle from there forever.
*/
float(float row) Gfx_Index =
{
	local string vals;
	local float n, i, cur, best, bestd, d;

	// The cvar read comes FIRST: Gfx_Cvar goes through Gfx_Field, and while that
	// does not tokenize today, reading it before the split removes the question
	// entirely -- argv() is only valid until the next tokenize.
	cur  = cvar(Gfx_Cvar(row));
	vals = Gfx_Field(Gfx_Def(row), 2, "|");
	n = tokenize(vals);
	if (n < 1)
		return -1;

	best  = 0;
	bestd = 1000000000;
	for (i = 0; i < n; i = i + 1)
	{
		d = stof(argv(i)) - cur;
		if (d < 0) d = 0 - d;
		if (d < bestd) { bestd = d; best = i; }
	}
	return best;
};

// What the current value MEANS.  This is the whole point of the menu: the
// numbers are cheap to set and impossible to remember.
string(float row) Gfx_ValueName =
{
	local float i;
	i = Gfx_Index(row);
	if (i < 0)
		return "";
	return Gfx_Field(Gfx_Field(Gfx_Def(row), 3, "|"), i, ";");
};

/*
  Cycle to the next value in the row's list.

  localcmd rather than cvar_set: these are engine and plugin cvars with latch
  and shader-flush flags on them, and the console path is the one those flags
  were written for.  It is also the path the user would have taken by hand, so
  the menu cannot behave differently from the thing it is a front end for.

  BUILD 33: `seta`, NOT a bare set, AND THAT IS THE BIGGEST FIX IN THIS BUILD.

  Nineteen of the twenty-one rows this menu shipped with were thrown away every
  time the game closed.  hl2_propdist is the only cvar in the whole hl2_* family
  registered CVAR_ARCHIVE, and default.cfg seeds just two of the rest -- so
  everything you set here reverted to the plugin's compiled-in default on the
  next launch, silently, with the menu cheerfully redrawing the value you did
  not choose.

  Measured rather than assumed: the saved ftesurf.cfg carries 308 archived cvars
  and exactly two of this menu's, `seta r_reflectcube "1"` and
  `seta hl2_propdist "0"`.

  `seta` forces CVAR_ARCHIVE when the command did not come from gamecode
  (cmd.c:4134), and CSQC's localcmd submits at RESTRICT_INSECURE, below
  RESTRICT_SERVER, so the flag is granted.  cfg_save_auto is already 1, so the
  file is written on quit.  This is the same mechanism build 31 used for the
  hud_edit layout cvars, and it is proven on a PLUGIN cvar specifically -- that
  `seta hl2_propdist` line is what it looks like when it works.

  It stays on the console path, so nothing above changes: latch and
  shader-flush flags are still honoured exactly as they were.
*/
void(float row) Gfx_Cycle =
{
	local string vals;
	local float n, i;

	if (Gfx_Cvar(row) == "")
		return;

	i = Gfx_Index(row);
	if (i < 0)
		return;

	// Re-split rather than trust the one Gfx_Index left behind.  It would be
	// the same split, but "the tokenizer still holds what the last call put
	// there" is exactly the assumption that breaks the first time a helper
	// grows a tokenize of its own.
	vals = Gfx_Field(Gfx_Def(row), 2, "|");
	n = tokenize(vals);

	i = i + 1;
	if (i >= n)
		i = 0;

	localcmd(sprintf("seta %s %s\n", Gfx_Cvar(row), argv(i)));
};

float() Gfx_Pages =
{
	return floor((GFX_ROWS - 1) / GFX_PER_PAGE) + 1;
};

float(float scan, float down) Gfx_Key =
{
	local float row, pages;

	if (!ui_gfx_open)
		return FALSE;
	if (!down)
		return FALSE;

	pages = Gfx_Pages();

	if (scan == '0') { ui_gfx_open = FALSE; return TRUE; }

	/*
	  7 is the map reload, and it is on this menu rather than on a bind because
	  the rows marked `*` only take effect on a map load: the footer has always
	  said so, and until now the menu could not provide one.  Setting a latched
	  row and pressing 7 is the whole interaction.

	  `retry` is the engine command added for this (P167).  It reloads the
	  current map when we are hosting it -- which, on a listen server, is always
	  -- and reconnects otherwise, matching Source.
	*/
	if (scan == '7') { localcmd("retry\n"); ui_gfx_open = FALSE; return TRUE; }

	// Both directions wrap, so 9 alone reaches every page and 8 is a shortcut
	// rather than a necessity.
	if (scan == '8')
	{
		ui_gfx_page = ui_gfx_page - 1;
		if (ui_gfx_page < 0)
			ui_gfx_page = pages - 1;
		return TRUE;
	}
	if (scan == '9')
	{
		ui_gfx_page = ui_gfx_page + 1;
		if (ui_gfx_page >= pages)
			ui_gfx_page = 0;
		return TRUE;
	}

	if (scan >= '1' && scan <= ('0' + GFX_PER_PAGE))
	{
		row = ui_gfx_page * GFX_PER_PAGE + (scan - '0');
		// The last page is short.  Swallow the key anyway: it belongs to this
		// menu whether or not the slot is occupied, and letting it fall through
		// to the save-lock menu underneath would be a surprise.
		if (row <= GFX_ROWS)
			Gfx_Cycle(row);
		return TRUE;
	}

	return FALSE;
};

/*
  `inert` is "" for a live row, or the reason it currently does nothing.

  An inert row keeps its key and its label -- it is still pressable, and cycling
  it is still the right thing to do while you are on your way to making it
  matter -- but it dims, and the reason takes the value column.  The value is
  the one thing worth suppressing: reading `55%` off a row that is not being
  consulted is how you conclude the setting is broken.
*/
void(vector p, float w, float h, string key, string label, string val,
     float latched, string inert, float lsz) Gfx_Row =
{
	local float a;

	drawfill(p, [w, h], '0 0 0', 0.55, 0);

	a = (inert != "") ? 0.45 : 1;

	HUD_Text([p_x + h * 0.35, p_y + (h - lsz) * 0.5], key, lsz, '0.80 0.83 0.88', a);
	HUD_Text([p_x + h * 1.25, p_y + (h - lsz) * 0.5], label, lsz, '0.72 0.75 0.80', a);

	if (inert != "")
	{
		// Full alpha on the reason: it is dimmer than a value by colour, not by
		// transparency, because it is the row's most useful text right now.
		HUD_TextR([p_x + w - h * 0.35, p_y + (h - lsz) * 0.5],
		          inert, lsz, '0.50 0.54 0.60', 1);
		return;
	}

	// The value is the thing you came to read, so it gets the highlight the
	// save-lock menu gives its cursor row.
	HUD_TextR([p_x + w - h * 0.35, p_y + (h - lsz) * 0.5],
	          latched ? strcat(val, " *") : val, lsz, '1.00 0.90 0.55', 1);
};

/*
  THE CONSOLE HANDLE (build 33).

  `gfx_menu` on its own still just toggles, as it has since build 14.  The
  arguments exist because everything this menu does was previously reachable
  only by pressing a digit while looking at it, and a thing that can only be
  driven by hand can only be checked by hand.  A cfg can now open it, walk it,
  cycle a row through the REAL Gfx_Cycle path -- seta and all -- and print the
  whole table for a condump, which is what let build 33's audit be verified
  rather than asserted.

      gfx_menu             toggle
      gfx_menu page <n>    show page n (1-based)
      gfx_menu cycle <n>   cycle row n, exactly as pressing its digit would
      gfx_menu status      print every row: value, latch mark, and whether it
                           is inert right now and why

  `status` is also the answer to "is this setting doing anything?" without
  opening anything, and it prints the inert reason for every row at once, which
  the menu itself can only show six at a time.
*/
float() Gfx_Console =
{
	local float i, n;
	local string inert;

	if (argv(1) == "page")
	{
		n = stof(argv(2)) - 1;
		if (n < 0 || n >= Gfx_Pages())
		{
			print(sprintf("gfx_menu page: 1..%g\n", Gfx_Pages()));
			return TRUE;
		}
		ui_gfx_page = n;
		ui_gfx_open = TRUE;
		return TRUE;
	}

	if (argv(1) == "cycle")
	{
		n = stof(argv(2));
		if (n < 1 || n > GFX_ROWS)
		{
			print(sprintf("gfx_menu cycle: 1..%g\n", GFX_ROWS));
			return TRUE;
		}
		Gfx_Cycle(n);
		// The set is deferred (localcmd), so read it back from the far side of
		// the queue rather than printing the value we are in the middle of
		// replacing -- the same trap `ghost speed <n>` fell into in build 32.
		localcmd(sprintf("gfx_menu status %g\n", n));
		return TRUE;
	}

	if (argv(1) == "status")
	{
		// An optional row number, so `cycle` above can report just its own row.
		if (argv(2) != "")
		{
			i = stof(argv(2));
			n = i;
		}
		else
		{
			i = 1;
			n = GFX_ROWS;
		}

		if (argv(2) == "")
		{
			print(sprintf("^5gfx_menu^7  %g settings, %g pages  (page %g shown)\n",
			              GFX_ROWS, Gfx_Pages(), ui_gfx_page + 1));

			/*
			  Build 33 made every row archive itself with `seta`.  That only
			  reaches ftesurf.cfg if something writes ftesurf.cfg, and
			  cfg_save_auto 0 means nothing does until you type cfg_save.

			  Worth saying out loud because the failure is invisible and looks
			  exactly like the bug this build fixed: you set a row, you quit,
			  it is back where it was.  The cvar defaults to 1 and default.cfg
			  sets it to 1, but a saved config execs later and wins -- and a
			  config that once saved a 0 keeps that 0 alive forever.
			*/
			if (!cvar("cfg_save_auto"))
				print("  ^1cfg_save_auto is 0^7 -- changes here will NOT survive a quit."
				      "  `seta cfg_save_auto 1` once, or `cfg_save` each time.\n");
		}

		for (; i <= n; i = i + 1)
		{
			inert = Gfx_Inert(i);
			print(sprintf("  %2g %-18s %-14s %-13s %s%s\n",
			              i, Gfx_Cvar(i), Gfx_Label(i), Gfx_ValueName(i),
			              Gfx_NeedsReload(i) ? "^3*needs map load^7 " : "",
			              (inert != "") ? sprintf("^1inert^7: %s", inert) : ""));
		}
		return TRUE;
	}

	if (argv(1) != "")
	{
		print("gfx_menu [page <n> | cycle <n> | status]\n");
		return TRUE;
	}

	ui_gfx_open = !ui_gfx_open;
	return TRUE;
};

void(vector scr) Gfx_Draw =
{
	local vector p;
	local float w, h, lsz, gap, y, i, row, pages;

	if (!ui_gfx_open)
		return;

	Font_Set(ui_font_ui);
	lsz = Font_Px(8 * ui_cv_scale);
	h   = 13 * ui_cv_scale;
	// Widened from 132 with the twenty-row list: "Prop collide" beside
	// "VPhysics *" is the longest pair, and it did not fit.  Build 33's
	// "Prop distance" / "Unlimited" and "Dither scale" / "set by Dither level"
	// are the two to re-check if this is ever narrowed again.
	w   = 150 * ui_cv_scale;
	gap = 1 * ui_cv_scale;

	pages = Gfx_Pages();
	// A page the row count no longer reaches -- someone deleted a setting while
	// this was open, or GFX_ROWS shrank across a build.  Snap back rather than
	// draw an empty page and look broken.
	if (ui_gfx_page >= pages)
		ui_gfx_page = 0;

	p = [scr_x * cvar("hud_gfx_x"), scr_y * cvar("hud_gfx_y"), 0];
	y = p_y;

	drawfill([p_x, y], [w, h + gap], '0.10 0.13 0.17', 0.85, 0);
	HUD_Text([p_x + h * 0.35, y + (h - lsz) * 0.5], "Source Renderer", lsz, '1 1 1', 1);
	HUD_TextR([p_x + w - h * 0.35, y + (h - lsz) * 0.5],
	          sprintf("page %g/%g", ui_gfx_page + 1, pages), lsz,
	          '0.55 0.58 0.62', 1);
	y = y + h + gap * 2;

	// Always draw GFX_PER_PAGE slots, even when the last page is short: the
	// footer keeps its position, and the block does not change height as you
	// page, which is what makes 7/8/9 stay under the same finger.
	for (i = 1; i <= GFX_PER_PAGE; i = i + 1)
	{
		row = ui_gfx_page * GFX_PER_PAGE + i;
		if (row > GFX_ROWS)
		{
			drawfill([p_x, y], [w, h], '0 0 0', 0.25, 0);
			y = y + h + gap;
			continue;
		}
		Gfx_Row([p_x, y], w, h, sprintf("%g", i),
		        Gfx_Label(row), Gfx_ValueName(row), Gfx_NeedsReload(row),
		        Gfx_Inert(row), lsz);
		y = y + h + gap;
	}

	// The menu's own verbs, one per row like everything above them.  "8/9 Page"
	// on a single row read as one control with two keys, which is not what it is:
	// they are two separate moves in opposite directions, and the value column
	// says where each one lands.
	y = y + gap;
	Gfx_Row([p_x, y], w, h, "7", "Reload map", "retry", FALSE, "", lsz);
	y = y + h + gap;
	Gfx_Row([p_x, y], w, h, "8", "Previous page",
	        sprintf("%g", ((ui_gfx_page + pages - 1) % pages) + 1), FALSE, "", lsz);
	y = y + h + gap;
	Gfx_Row([p_x, y], w, h, "9", "Next page",
	        sprintf("%g", ((ui_gfx_page + 1) % pages) + 1), FALSE, "", lsz);
	y = y + h + gap;
	Gfx_Row([p_x, y], w, h, "0", "Close", "", FALSE, "", lsz);
	y = y + h + gap;

	y = y + gap * 2;
	HUD_Text([p_x + h * 0.35, y], "* needs a map load -- press 7", lsz * 0.9,
	         '0.55 0.58 0.62', 1);
	y = y + lsz;

	Font_Reset();

	// Build 31: the box, for `hud_edit`.
	HUD_Rect("gfx", p, [w, y - p_y, 0], p);
};
