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

  P1566 made it a mouse panel (Lex, 15 Nov 2026: "a proper click and drag
  menu with clickable options ... previous and next buttons, with readout of
  the option currently selected, maybe tooltips telling you the console
  command"): tabs by subject, < value > per row with the value's list one
  click away, and the console command in each row's tooltip. It was the
  save-lock menu's digit-driven shape (seven pages of six) until then.

  REBUILD/LOAD ROWS ARE MARKED, and that mark is load-bearing. Water's live
  policy rebuilds its shaders on the next frame; other generated-material
  policies need an explicit rebuild, and BSP-time settings need a fresh load.
  Seeing nothing happen is indistinguishable from a broken setting unless
  the menu says so first. Reload map retries, but may reuse cached BSP data.
===========================================================================
*/

float ui_gfx_open;              // the menu is up
float ui_gfx_page;              // P1566: the tab shown, 0-based
float ui_gfx_loadtime;          // cltime when this map's CSQC came up
float ui_gfx_mmrsent;           // P1382: this map's missing-material report went (or was not due)
float ui_gfx_waterbudget;       // LOCAL native renderer + loaded plugin capability
float ui_gfx_waterscreen;       // Patch 1020: hl2_water 5 (screen-space) on this native renderer + plugin
float gfx_movers_off;           // P1423: vbsp_movers 0, read once a frame (CSQC_UpdateView) by the mover predraws

#define GFX_ROWS     37         // highest row index (P1458 Light glows, P1459 Post-process)

void() Gfx_WaterSupport =
{
	ui_gfx_waterbudget = checkextension("FTE_CSQC_HL2_WATER_BUDGET");
	ui_gfx_waterscreen = checkextension("FTE_CSQC_HL2_WATER_SCREEN");
	if (!ui_gfx_waterscreen)
	if (cvar("hl2_water") == 5)
	{
		// Patch 1020: an archived 5 on an older client or plugin (which clamps it to 4).
		cvar_set("hl2_water", "0");
		localcmd("flushshaders\n");
		print("Water: Screen-space needs an updated OpenGL client/plugin; using Flat sheet and rebuilding shaders.\n");
	}
	if (!ui_gfx_waterbudget)
	if (cvar("hl2_water") == 4)
	{
		// An archived 4 can reach the BSP generator before downloaded CSQC.
		// Old natives lack the live-policy flag: rebuild that cached material.
		cvar_set("hl2_water", "0");
		localcmd("flushshaders\n");
		print("Water: Budget needs an updated OpenGL client/plugin; using Flat sheet and rebuilding shaders.\n");
	}
};

void() Gfx_RegisterCvars =
{
	registercvar("hud_gfx_x", "0.0333", CVAR_ARCHIVE);
	// Patch 637: 0.338, where the owner has it. P1566: the panel's top left; the title bar drags it.
	registercvar("hud_gfx_y", "0.338", CVAR_ARCHIVE);

	// Bindable, so it does not have to live on one key we chose.
	registercommand("gfx_menu");

	// See Gfx_DrawMissing.  On by default: the thing it warns about is
	// indistinguishable from a broken engine until you are told otherwise.
	// CVAR_ARCHIVE since build 33 -- turning the banner off and having it come
	// back on the next launch is the same defect the seta note on Gfx_Cycle
	// describes, in miniature.
	registercvar("fs_missingwarn", "1", CVAR_ARCHIVE);
	registercvar("cl_matreport", "1", CVAR_ARCHIVE);    // P1382: 0 = no missing-material reports
	registercvar("vbsp_movers", "1", CVAR_ARCHIVE);     // P1423: 0 = csprogs movers not posed or drawn

	// CSQC_Init runs once per map load, so this is the map's own zero.
	ui_gfx_loadtime = cltime;
	ui_gfx_mmrsent = FALSE;
	Gfx_WaterSupport();
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
/*
  P1382: once a map, when materials on drawn faces or props did not resolve, tell the lobby what this
  install could not find, so we can see what players are missing without asking them (sv_matreport.qc
  stores it). Names and counts only: the map, the plugin's counts and first name, what fs_automount did,
  the fs_addons.txt games that did not mount (engines from P1382); the lobby adds the engine (*ver). No paths.
  Waits 6 s for the plugin's numbers to settle; never from a local game.
*/
void() Gfx_MissingReport =
{
	local string s;

	if (ui_gfx_mmrsent || cltime - ui_gfx_loadtime < 6)
		return;
	ui_gfx_mmrsent = TRUE;
	if (!cvar("cl_matreport") || cvar("hl2_unresolved_visible") < 1 || !strncmp(serverkey("ip"), "QLoopBack", 9))
		return;
	s = sprintf("missing %g visible %g first %s automount %g spec %s nogame %s",
	            cvar("hl2_unresolved"), cvar("hl2_unresolved_visible"), cvar_string("hl2_unresolved_first"),
	            cvar("fs_automount_state"), cvar_string("fs_automount_spec"),
	            cvar_string("fs_addons_missing"));
	sendevent("mmr", "s", substring(strreplace("\n", " ", s), 0, 900));
};

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
	// P1382: an fs_addons.txt game that did not mount is the likelier cause (engines from P1382 say which).
	if (cvar_string("fs_addons_missing") != "")
		HUD_TextC([p_x, p_y + sz * 1.4],
		          sprintf("not found on this PC: %s  (another drive?  console: fs_steamlibs)", cvar_string("fs_addons_missing")),
		          sz * 0.85, '1.00 0.80 0.45', a * 0.9);
	else
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
      4  "*" when a rebuild/map load is needed (retry may reuse cached data)
      5  P1566: what it does, for the row's tooltip (one or two sentences)

  Field 3 is the whole reason the menu exists.  It is positional against field 2
  rather than threshold-tested against the cvar, which is what the old
  Gfx_ValueName did: a threshold chain is a second, independent encoding of the
  same list, and the two can disagree.

  P1566: the panel shows rows by Gfx_TabRows, so the page notes below are only history.

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
	// -- page 1: surface policy ---------------------------------------------
	// P1423: field 2 runs fastest -> fullest (the menu shows the position, "3/6"); costs from the
	// plugin's own descriptions (mod_vbsp.c hl2_water / hl2_refract). Rows without a cost keep their order.
	// Plugin_GetCvar drops CVAR_SHADERSYSTEM; the renderer re-registers the material rows
	// with it (Water, dither; Patch 894 the rest). `e` marks a row live only on such an engine.
	if (row == 1)
	{
		if (ui_gfx_waterscreen && ui_gfx_waterbudget)
			return "hl2_water|Water|3 0 4 5 1 2|Dithered;Flat sheet;Budget (no captures);Screen-space;Cheap reflect;Full reflect||How water surfaces draw, cheapest first. The reflection modes cost the most.";
		if (ui_gfx_waterbudget)
			return "hl2_water|Water|3 0 4 1 2|Dithered;Flat sheet;Budget (no captures);Cheap reflect;Full reflect||How water surfaces draw, cheapest first. The reflection modes cost the most.";
		return "hl2_water|Water|3 0 1 2|Dithered;Flat sheet;Cheap reflect;Full reflect|*|How water surfaces draw, cheapest first. The reflection modes cost the most.";
	}
	// Patch 900: 2 dithers only a pane with its own texture (P859); 879 of the 1,047 pak Refract
	// VMTs in the 1,926-map library have none -- surf_boreas's ice among them -- and draw as 0.
	if (row == 2)  return "hl2_refract|Glass|2 0 1|Dithered if textured;Translucent;Refracting|*|How refracting glass and ice draw. Dithered applies to panes with their own texture; the rest draw translucent.";
	if (row == 3)  return "hl2_translucent|Translucent|0 1|Opaque;As authored|e|See-through world materials: windows, grates, railings. Opaque stops sorting them, which is what they cost on maps with a lot of glass.";
	/*
	  BUILD 33, and it belongs on this page because it is the same kind of thing
	  as the three above it: one read at material generation (mat_vmt.c:1114).
	  Its requested CVAR_SHADERSYSTEM flag is masked by Plugin_GetCvar; Patch 894
	  gives it a renderer-owned one, but no flipbook was in its arm, so the `*` stays.

	  Patch 195 is what made it work -- img_vtf.c had `frames = 1;//vtf->numframes;`,
	  so a 331-frame flipbook like surf_demise's smoke could not cycle no matter
	  what the material asked for.  It defaults to 0, which means that until this
	  row existed the feature was both off and unreachable.
	*/
	if (row == 4)  return "hl2_animated|Animated|0 1|Off;On|*|Lets flipbook textures (smoke, screens, flowing sheets) play their frames.";
	if (row == 5)  return "hl2_dither_alpha|Dither scale|0.15 0.30 0.55 0.80 1|15%;30%;55%;80%;100%|*|How see-through dithered water and glass are, as a share of each material's own amount.";
	if (row == 6)  return "hl2_dither_force|Dither level|0 0.15 0.25 0.40 0.55 0.70 0.85 1|Per material;15%;25%;40%;55%;70%;85%;100%|*|One see-through level for every dithered material, replacing their own amounts.";
	/*
	  BUILD 20: marked map-latched, which it should always have been.

	  It clears $envmap while a material is GENERATED, so it takes effect only on
	  materials generated after the change -- and a shader that already loaded a
	  reflectcube keeps it across a regenerate, because Shader_Reset preserves
	  defaulttextures.  So "off" on an already-loaded map is partial at best, and
	  a row that claims to be instant when it is not is the exact failure this
	  whole `*` convention exists to prevent.  Reflections (row 8) is the one to
	  reach for if you want it off NOW.
	  Patch 894: with the renderer's flag a live 0 and 1 each matched a `retry` at surf_demise
	  save 3, but a retry keeps the BSP, and whether a batch keeps its cubemap is decided at
	  map load (Mod_Batches_Build) -- so a map loaded with it off still needs one.
	*/
	if (row == 7)  return "hl2_envmap|Env maps|0 1|Off;On|*|Materials' own reflections, decided when a material is built. Reflections switches them off at once.";

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
	if (row == 8)  return "r_reflectcube|Reflections|0 1|Off;On||Cubemap reflections on every surface, switched where they are drawn: applies on the next frame.";
	if (row == 9)  return "hl2_cubemaps|Cubemaps|0 1|Off;On|*|The map's baked env_cubemap reflections. Off leaves reflective surfaces flat, which is cheaper.";
	/*
	  Works, and stays ungreyed -- but it does NOT reach Water or Refract
	  surfaces: mat_vmt.c:984 excludes those two material types by name, so
	  glass and water keep their normal maps whatever this row says.  Noted
	  here and in default.cfg rather than dimmed. It controls ordinary materials
	  when they are generated; the masked shader-system flag means cached ones
	  need a rebuild, hence the *.
	*/
	if (row == 10) return "hl2_bumpmap|Bump maps|0 1|Off;On|*|Normal maps on ordinary materials. Water and glass keep theirs.";
	if (row == 11) return "vbsp_skyroom|3D skybox|0 1|Off;On||The map's 3D skybox: the miniature scene drawn behind the sky.";
	/*
	  BUILD 33: GAINED ITS `*`, which it should have had from the start.

	  Read once, at cl_decals.qc:195, during the entity-lump walk -- so at map
	  load.  The comment there says so outright ("vbsp_decals 0 no longer skips
	  the walk, it only skips the PLACING"), and this table went on claiming the
	  row was instant.  That is exactly the failure the `*` convention exists to
	  prevent, committed by the convention's own table.
	*/
	if (row == 12) return "vbsp_decals|Decals|0 1|Off;On|*|The map's decal entities: stains, sprays, signs.";

	// -- page 3: what the map LOAD builds -------------------------------------
	/*
	  OVERLAYS is the map's OTHER kind of decal -- the ones VBSP bakes into
	  lump 45 as oriented quads instead of writing as entities.  230 of the 1310
	  shipped maps carry them and none of them drew until Patch 246.

	  THE ROW IS ON vbsp_overlays, AND THAT IS DELIBERATE.  There are two switches
	  and only one of them can work from this menu:

	    vbsp_overlays   read by the CSQC entity walk, once per map load.  Reload map
	                  restarts the map, which re-initialises CSQC, so the walk
	                  runs again and the row applies.  Hence the `*`.
	    hl2_overlays  read inside the BSP loader, which Reload map does NOT re-run:
	                  `retry` is `map_restart`, and Mod_ForName hands back the
	                  CACHED world model unless the .bsp's mtime moved.  So no
	                  amount of pressing 7 can change it, and it is console-only
	                  for the same reason hl2_displacement_scale is.

	  Measured, not reasoned: with developer 1 the loader prints "VBSP: <map>:
	  N of N baked overlays synthesised", and that line appears exactly once --
	  on the first load -- however many times you press 7.  Which also means
	  every `*` row below that is read at BSP-load time has the same problem;
	  that is a separate defect and is not fixed here.
	  Patch 894: a toggle now re-runs Decal_LoadForMap on the same map (handles kept and
	  removed), measured live == a retry on surf_rise (103 of its 105 overlays placed).
	*/
	if (row == 13) return "vbsp_overlays|Overlays|0 1|Off;On||Decals baked into the map file (info_overlay): signs, trims, ground detail.";

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
	if (row == 14) return "vbsp_sprites|Sprites|0 1|Off;On||Lamp glows, fires and flat billboard sprites.";    // Patch 894: re-run live
	if (row == 15) return "vbsp_spotlights|Light shafts|0 1|Off;On|*|The large additive beams of the map's spotlights.";

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
	if (row == 16) return "hl2_propdist|Prop distance|4000 8000 12000 20000 0|4k;8k;12k;20k;Unlimited||How far away static props still draw. The biggest frame-rate setting on prop-heavy maps.";
	if (row == 17) return "hl2_hidetools|Tool brushes|1 0|Hidden;Shown|*|Clip, nodraw, skip and hint brushes, hidden as in Source. Shown helps work out why a route is blocked.";
	if (row == 18) return "hl2_areaportals|Areaportals|0 1|Closed;Open|*|How the map's areaportals start. Open is what Source does; Closed can seal whole areas off.";
	if (row == 19) return "hl2_propcollision|Prop collide|0 1 2 3|None;VPhysics;Bbox;Mesh|*|How props collide. The server decides this: it changes only with sv_cheats.";
	if (row == 20) return "hl2_dispcollision|Disp collide|0 1|None;Normal|*|Collision on displacement terrain. The server decides this: it changes only with sv_cheats.";
	// Which of a map's two lighting lumps the BSP parse READS, so it belongs
	// with the load rather than with the prop lighting on the next page.
	if (row == 21) return "hl2_favour_ldr|Lightmap|0 1|HDR;LDR|*|Which of the map's two lightmaps to load. LDR can look less washed out on brightly lit maps.";

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
	if (row == 22) return "hl2_lt_baked|Prop light|0 1 2|Ambient cube;Bake, one colour;Bake per vertex|*|How static props are lit: the area's ambient light, one colour from the map's bake, or the bake per vertex as Source draws it.";   // P1566: 2 (default) was unreachable
	if (row == 23) return "hl2_lt_baked_scale|Prop bright|1 2 3|Raw;x2;x3|*|Brightness of the baked prop lighting. x2 matches the world's lightmaps.";
	if (row == 24) return "hl2_lt_min|Prop ambient|0 8 16 32 64|Off;8;16;32;64|*|A floor under model lighting, so props in dark corners stay visible.";
	if (row == 25) return "hl2_lt_scale|Model light|160 200 255 320|160;200;255;320|*|Overall model brightness. 255 maps a fully lit model to white.";
	if (row == 26) return "hl2_lt_srgb_mag|Model gamma|0 1|Linear;sRGB|*|Whether model lighting gets the sRGB encode Source's lighting expects.";
	/*
	  The map's own fog.  Appended rather than slotted in next to `3D skybox`
	  where it belongs by subject, because these rows are addressed BY NUMBER --
	  `gfx_menu cycle N` takes one, and ui_gfx_page remembers a position across
	  builds -- so inserting in the middle silently moves every row below it
	  under someone's cursor.  Grouping is not worth that.
	*/
	if (row == 27) return "vbsp_fog|Map fog|0 1|Off;On||The map's own fog.";
	/*
	  Build 49.  Appended for the reason the block above gives, not slotted in
	  beside `Map fog` where it belongs by subject -- these rows are addressed
	  BY NUMBER and ui_gfx_page remembers a position across builds.
	*/
	if (row == 28) return "vbsp_emit|Map particles|0 1|Off;On||The map's dust motes, smoke stacks, steam and particle systems.";
	if (row == 29) return "vbsp_sun|Sun|0 1|Off;On||The map's sun disc and glow.";       // Patch 874, cl_sun.qc
	if (row == 30) return "vbsp_ropes|Ropes|0 1|Off;On||The map's ropes and cables.";   // cl_ropes.qc
	// Patch 898's 2x was the default until Patch 1376 made it 1x with MSAA.  Live, the next frame.
	if (row == 31) return "r_renderscale|Render scale|1 1.5 2|1x;1.5x;2x||Draws the scene at a multiple of the screen's resolution and scales it down: sharper, much slower.";
	// Patch 1376: P1260's scene target and P1276's capture target read these every frame.
	if (row == 32) return "vid_multisample|Anti-aliasing|0 2 4 8|Off;2x;4x;8x||Multisample anti-aliasing on the scene's edges.";
	if (row == 33) return "r_reflectmultisample|Reflection AA|0 2 4 -1|Off;2x;4x;As screen||Anti-aliasing on water and glass reflections.";
	// P1423: the movers csprogs poses every frame -- passable func_tracktrains and their riders (cl_trk.qc),
	// non-solid func_rotating / func_movelinear chains (cl_spin.qc). Off skips their posing and drawing;
	// solid movers are the server's and always draw (you can hit them). Live, the next frame.
	if (row == 34) return "vbsp_movers|Movers|0 1|Off;On||Decorative movers your game animates (passable trains, spinners). Solid movers are the server's and always draw.";
	// P1398's rate: how often a MOVING model re-samples the world's light (0 = every frame it moves). surf_centipedes
	// skull swarm (tools/p1423-gfxmenu.md): 0.25/s 2.40 ms, 1/s 2.38, 4/s 2.50, every frame 5.5 -- nothing below 1/s.
	if (row == 35) return "r_modellight_moverate|Mover light|1 4 0|1/s;4/s;Every frame||How often a moving model re-reads the world's light. Every frame costs the most.";
	// P1458: env_lightglow flares have their own switch (cl_main.qc), so Sprites off left them on and a
	// reload faded them back in. surf_fairy (460 glows): off 273/140/122 fps against 230/93/74 (P1456 notes).
	if (row == 36) return "vbsp_lightglow|Light glows|0 1|Off;On||Glow flares around lamps (env_lightglow).";
	// P1459: engine master switch; Off drops bloom, the map's colour grade, FXAA, r_postprocshader and
	// the underwater warp. Gamma is not a post effect here and stays. Live, the next frame.
	if (row == 37) return "r_postprocess|Post-process|0 1|Off;On||Bloom, the map's colour grade, FXAA and the underwater warp. Gamma stays.";

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

// Rows needing a material rebuild or fresh map/client load. Readback alone
// does not prove the cached appearance changed; retry may reuse BSP data.
#define GFX_TYPEFLAG_ENGINE 8	// CVAR_TYPEFLAG_ENGINE (pr_common.h): not user/plugin-created

float(float row) Gfx_NeedsReload =
{
	local string m;

	m = Gfx_Field(Gfx_Def(row), 4, "|");
	if (m == "e")
		return !(cvar_type(Gfx_Cvar(row)) & GFX_TYPEFLAG_ENGINE);
	return m == "*";
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

	// Build 49.  Roughly half the library carries none of the seven classes
	// cl_emit.qc draws, so on those maps this toggle has nothing to toggle.
	// em_any counts what the MAP holds rather than what is emitting, so the row
	// does not grey itself out the moment you switch the feature off.
	if (cv == "vbsp_emit" && !em_any)
		return "map has none";
	if (cv == "vbsp_sun" && !sun_have)
		return "map has no env_sun";
	if (cv == "vbsp_ropes" && !ropes_n)
		return "map has no ropes";
	if (cv == "vbsp_movers")
	if (!find(world, classname, "sp_mover") && !find(world, classname, "trk_train"))
		return "none near you";     // they are sent by PVS: nothing here to pose
	// Engines before P1398 have no such cvar (cvar_description: a seta'd one has none either).
	if (cv == "r_modellight_moverate" && cvar_description(cv) == "")
		return "needs update";
	if (cv == "r_postprocess" && cvar_description(cv) == "")
		return "needs update";
	if (cv == "vbsp_lightglow" && !vbsp_glow_seen)
		return "map has none";

	/*
	  THE TWO COLLISION ROWS ARE NOT THE PLAYER'S TO TURN OFF.  A surf map needs
	  its prop collision to be playable, and a client that disables it predicts a
	  world the server is not running -- so both cvars are CVAR_CHEAT in the plugin
	  now (mod_vbsp.c) and the engine latches them to their defaults, 1 and 1,
	  whenever it is connected without cheats (cvar.c:940).  Collision on, and not
	  switchable from here.

	  The ROWS STAY, at 19 and 20, rather than being deleted: the block above row 27
	  states the rule that these are addressed BY NUMBER -- `gfx_menu cycle N` takes
	  one and ui_gfx_page remembers a position across builds -- so removing two
	  would move every row below them under someone's cursor.  Saying "needs
	  sv_cheats" on the row is also the honest answer, and it is exactly what this
	  function exists for: without it the row would accept a keypress, redraw the
	  value the engine snapped back, and read as broken.

	  `*cheats` is the engine's OWN published signal, the same serverinfo key
	  cl_main.c:3246 reads to set cls.allow_cheats -- not a reimplementation of the
	  rule.  The local sv_cheats is checked too because a listen server allows
	  cheats from its own cvar (and at one slot allows them regardless), so reading
	  only the key would grey the row out for the person hosting.
	*/
	if (cv == "hl2_propcollision" || cv == "hl2_dispcollision")
		if (serverkey("*cheats") != "on")
		if (!cvar("sv_cheats"))
			return "needs sv_cheats";

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

// P1423: "(3/6)" -- the value's place in the row's fastest -> fullest list.
string(float row) Gfx_Position =
{
	local float i;
	i = Gfx_Index(row);
	if (i < 0)
		return "";
	return sprintf("(%g/%g)", i + 1, tokenize(Gfx_Field(Gfx_Def(row), 2, "|")));
};

/*
  How a row's value is set (Gfx_SetIndex below).

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
/*
  Set the row's value to entry i of its list. localcmd + seta for the reasons above; Gfx_Field splits
  without tokenize, so a caller's argv survives.
*/
void(float row, float i) Gfx_SetIndex =
{
	local string v;

	v = Gfx_Field(Gfx_Field(Gfx_Def(row), 2, "|"), i, " ");
	if (Gfx_Cvar(row) == "" || v == "")
		return;
	localcmd(sprintf("seta %s %s\n", Gfx_Cvar(row), v));
};

float(float row) Gfx_Count =
{
	return tokenize(Gfx_Field(Gfx_Def(row), 2, "|"));
};

// `gfx_menu cycle <n>`: the next entry, wrapping (the console's old digit behaviour).
void(float row) Gfx_Cycle =
{
	local float i, n;

	i = Gfx_Index(row);
	n = Gfx_Count(row);
	if (i < 0 || n < 1)
		return;
	i = i + 1;
	if (i >= n)
		i = 0;
	Gfx_SetIndex(row, i);
};

/*
  P1566: the panel's tabs, by subject. Rows keep their numbers (`gfx_menu cycle N`); a tab is a list of
  them. The two collision rows show only where cheats are on: anywhere else they are latched and inert.
*/
#define GFX_TABS 6

string(float tab) Gfx_TabName =
{
	if (tab == 0) return "Performance";
	if (tab == 1) return "Water and glass";
	if (tab == 2) return "Reflections";
	if (tab == 3) return "Atmosphere";
	if (tab == 4) return "Map detail";
	return "Lighting";
};

float() Gfx_Cheats =
{
	return serverkey("*cheats") == "on" || cvar("sv_cheats");
};

string(float tab) Gfx_TabRows =
{
	if (tab == 0) return "31 32 33 16 37 34 35";
	if (tab == 1) return "1 2 3 5 6";
	if (tab == 2) return "8 9 7 10";
	if (tab == 3) return "11 27 29 28 36 15";
	if (tab == 4)
	{
		if (Gfx_Cheats())
			return "14 12 13 30 4 17 18 19 20";
		return "14 12 13 30 4 17 18";
	}
	return "21 22 23 24 25 26";
};

float(float tab) Gfx_TabCount =
{
	local float n;
	local string s;

	s = Gfx_TabRows(tab);
	n = 0;
	while (Gfx_Field(s, n, " ") != "")
		n = n + 1;
	return n;
};

// The tooltip: what it does, the console command with its current value, every value, and why it may not show.
string(float row) Gfx_Tip =
{
	local string def, cv, vals, names, v, s, why;
	local float i;

	def = Gfx_Def(row);
	cv = Gfx_Field(def, 0, "|");
	vals = Gfx_Field(def, 2, "|");
	names = Gfx_Field(def, 3, "|");
	s = "";
	i = 0;
	v = Gfx_Field(vals, 0, " ");
	while (v != "")
	{
		s = strcat(s, (i > 0) ? ",  " : "", v, " ", Gfx_Field(names, i, ";"));
		i = i + 1;
		v = Gfx_Field(vals, i, " ");
	}
	s = sprintf("%s\n\nConsole:  %s %s\nValues:  %s", Gfx_Field(def, 5, "|"), cv, cvar_string(cv), s);
	if (Gfx_NeedsReload(row))
		s = strcat(s, "\n* Applies after Reload map (a fresh map load if it still does not show).");
	why = Gfx_Inert(row);
	if (why != "")
		s = strcat(s, "\nNot active here: ", why, ".");
	return s;
};

float sc_held;                          // cl_scores.qc's (fteqcc merges a repeated global): Tab is down
float gfx_drag, gfx_mx, gfx_my;         // P1566: the title bar is held; the last absolute mouse position
float gfx_drop;                         // the row whose value list is open, 0 none
float gfx_titleh;
vector gfx_pos, gfx_size, gfx_off, gfx_dpos, gfx_dsize;

void() Gfx_Close =
{
	ui_gfx_open = FALSE;
	gfx_drag = gfx_drop = 0;
	UI_CursorRelease(UIC_GFX);
	sui_reset_actions();
	sui_tooltip_reset();
};

// Over a replay is allowed: Watch_Draw hides its chrome while another cursor claim is held, so this
// bracket is the frame's last and owns the clicks.
float() Gfx_OthersHeld =
{
	local float held;

	held = UI_CursorHeld();
	if (held & UIC_WATCH) held = held - UIC_WATCH;
	if (held & UIC_GFX) held = held - UIC_GFX;
	return held || rec_sb_open;
};

void() Gfx_Open =
{
	if (Gfx_OthersHeld())
	{
		print("gfx_menu: close the other panel first\n");
		return;
	}
	ui_gfx_open = TRUE;
	gfx_drag = gfx_drop = 0;
	sui_reset_actions();
	UI_CursorClaim(UIC_GFX);
};

// A pill like Profile_Chip (cl_profile.qc compiles later), with a disabled look. -> clicked and let go over it.
float(string id, vector pos, vector sz, float rad, string label, float tsz, float on, float live) Gfx_Chip =
{
	local float hot, tw;

	sui_action_element(pos, sz, id, sui_noop);
	hot = live && sui_is_hovered(id);
	if (hot)
		sui_style_box(pos, sz, rad, on ? SUI_THEME_SELECTED : SUI_THEME_HOVER, SUI_THEME_EDGE_HI, 1);
	else
		sui_roundbox(pos, sz, rad, on ? SUI_THEME_SELECTED : SUI_THEME_CHIP, live ? 1 : 0.5);
	tw = stringwidth(label, TRUE, [tsz, tsz]);
	sui_text([pos_x + (sz_x - tw) * 0.5, pos_y + (sz_y - tsz) * 0.5], [tsz, tsz], label,
	         on ? SUI_THEME_ACCENT : (hot ? SUI_THEME_TEXT : SUI_THEME_DIM), live ? 1 : 0.35, 0);
	return live && sui_is_clicked(id);
};

void(vector scr) Gfx_Draw =
{
	local float sc, tsz, ttl, hint, pad, rh, bh, bw, tw, lw, vw, n, i, k, row, idx, cnt, maxrows, th, fh, gap, pw;
	local float dropseen, a, fs;
	local vector pos, size, at, x0, vc, dv;
	local string rows, label, val, why, rid, pid, vid, nid;

	if (!ui_gfx_open)
		return;
	if (Gfx_OthersHeld())
	{
		Gfx_Close();
		return;
	}
	if (sc_held)
		return;                         // the held board's bracket draws later and owns the clicks
	if (ui_gfx_page < 0 || ui_gfx_page >= GFX_TABS)
		ui_gfx_page = 0;

	maxrows = 0;
	for (i = 0; i < GFX_TABS; i = i + 1)
		maxrows = max(maxrows, Gfx_TabCount(i));

	Font_Set(ui_font_ui);
	sc = max(0.5, ui_cv_scale);
	while (sc > 0.5 && (Font_Px(8 * sc) * 52 > scr_x - 12 || Font_Px(8 * sc) * (maxrows * 2.3 + 11) > scr_y - 12))
		sc = max(0.5, sc - 0.5);
	tsz = Font_Px(8 * sc); ttl = Font_Px(11 * sc); hint = Font_Px(6.5 * sc);
	pad = tsz;
	rh = ceil(tsz * 2.3);                       // a setting row
	bh = rh - ceil(tsz * 0.5);                  // its buttons
	bw = ceil(bh * 1.25);
	tw = tsz * 10;                              // the tab column
	lw = tsz * 9;                               // a row's label
	vw = tsz * 11;                              // its value
	gap = ceil(tsz * 0.3);
	th = pad * 0.8 + ttl + hint * 1.5 + pad * 0.7;
	fh = pad * 0.6 + rh + hint * 1.6;
	size = [tsz * 52, th + max(maxrows * rh, GFX_TABS * (rh + gap)) + pad + fh, 0];
	gfx_titleh = th - pad * 0.5;

	pos = [cvar("hud_gfx_x") * scr_x, cvar("hud_gfx_y") * scr_y, 0];
	if (gfx_drag)
		pos = [gfx_mx, gfx_my, 0] - gfx_off;
	pos_x = bound(4, pos_x, max(4, scr_x - size_x - 4));
	pos_y = bound(4, pos_y, max(4, scr_y - size_y - 4));
	if (gfx_drag)
	{
		cvar_set("hud_gfx_x", ftos(pos_x / scr_x));
		cvar_set("hud_gfx_y", ftos(pos_y / scr_y));
	}
	gfx_pos = pos; gfx_size = size;

	sui_begin(scr_x, scr_y);
	sui_style_panel(pos, size, ceil(pad * 0.75), 0.97);
	sui_text(pos + [pad, pad * 0.8, 0], [ttl, ttl], "Graphics", SUI_THEME_TEXT, 1, 0);
	sui_text(pos + [pad, pad * 0.8 + ttl + hint * 0.4, 0], [hint, hint],
	         "Source renderer settings.  Hover a setting for what it does and its console command.  Drag here to move.",
	         SUI_THEME_MUTED, 1, 0);
	if (Gfx_Chip("gfx_close", pos + [size_x - pad - bh, pad * 0.7, 0], [bh, bh, 0], bh * 0.5, "X", tsz, FALSE, TRUE))
	{
		Gfx_Close(); sui_end(); Font_Reset(); return;
	}
	sui_tooltip_for("gfx_close", "Close (Esc, or the gfx_menu key again).", sc);
	drawfill(pos + [pad * 0.5, th - pad * 0.4, 0], [size_x - pad, 1, 0], SUI_THEME_EDGE_HI, 0.6, 0);

	// Tabs, down the left.
	at = pos + [pad, th, 0];
	for (i = 0; i < GFX_TABS; i = i + 1)
	{
		if (Gfx_Chip(sprintf("gfx_tab%g", i), at + [0, i * (rh + gap), 0], [tw, rh, 0], tsz * 0.6,
		             Gfx_TabName(i), tsz, i == ui_gfx_page, TRUE))
		{
			ui_gfx_page = i;
			gfx_drop = 0;
		}
	}
	drawfill(pos + [pad * 1.5 + tw, th, 0], [1, max(maxrows * rh, GFX_TABS * (rh + gap)), 0], SUI_THEME_EDGE_HI, 0.4, 0);

	// The tab's settings: label, < value >, where the value sits fastest -> fullest, and why it may do nothing.
	x0 = pos + [pad * 2 + tw, th, 0];
	rows = Gfx_TabRows(ui_gfx_page);
	dropseen = FALSE;
	k = 0;
	row = stof(Gfx_Field(rows, 0, " "));
	while (row >= 1)
	{
		at = x0 + [0, k * rh, 0];
		rid = sprintf("gfx_r%g", row);
		pid = sprintf("gfx_p%g", row);
		vid = sprintf("gfx_v%g", row);
		nid = sprintf("gfx_n%g", row);

		sui_action_element(at, [size_x - (at_x - pos_x) - pad, rh, 0], rid, sui_noop);
		if (sui_hover_index(rid) >= 0 || gfx_drop == row)
			sui_roundbox(at + [-gap, 0, 0], [size_x - (at_x - pos_x) - pad + gap * 2, rh, 0], tsz * 0.5, SUI_THEME_WELL, 0.8);
		else if (k & 1)
			sui_roundbox(at + [-gap, 0, 0], [size_x - (at_x - pos_x) - pad + gap * 2, rh, 0], tsz * 0.5, SUI_THEME_WELL, 0.3);

		why = Gfx_Inert(row);
		a = (why != "") ? 0.55 : 1;
		label = Gfx_Label(row);
		sui_text(at + [0, (rh - tsz) * 0.5, 0], [tsz, tsz], label, SUI_THEME_TEXT, a, 0);
		if (Gfx_NeedsReload(row))
			sui_text(at + [stringwidth(label, TRUE, [tsz, tsz]) + tsz * 0.3, (rh - tsz) * 0.5, 0], [tsz, tsz], "*",
			         SUI_THEME_FOCUS, a, 0);

		idx = Gfx_Index(row);
		cnt = Gfx_Count(row);
		at_x = at_x + lw;
		at_y = at_y + (rh - bh) * 0.5;
		if (Gfx_Chip(pid, at, [bw, bh, 0], bh * 0.5, "<", tsz, FALSE, idx > 0))
			Gfx_SetIndex(row, idx - 1);
		dv = at + [bw + gap, 0, 0];
		val = Gfx_ValueName(row);
		if (Gfx_Chip(vid, dv, [vw, bh, 0], tsz * 0.5, "", tsz, gfx_drop == row, TRUE))
			gfx_drop = (gfx_drop == row) ? 0 : row;
		vc = SUI_THEME_TEXT;
		if (val == "On")  vc = SUI_THEME_GOOD;
		if (val == "Off") vc = SUI_THEME_DIM;
		if (why != "")    vc = SUI_THEME_MUTED;
		fs = tsz;                               // "Budget (no captures)" shrinks to clear the arrow
		if (stringwidth(val, TRUE, [fs, fs]) > vw - hint * 3.2)
			fs = fs * (vw - hint * 3.2) / stringwidth(val, TRUE, [fs, fs]);
		sui_text(dv + [(vw - hint * 1.2 - stringwidth(val, TRUE, [fs, fs])) * 0.5, (bh - fs) * 0.5, 0], [fs, fs], val, vc, 1, 0);
		sui_text(dv + [vw - hint * 1.4, (bh - hint) * 0.5, 0], [hint, hint], "v", SUI_THEME_MUTED, 1, 0);
		if (gfx_drop == row)
		{
			dropseen = TRUE;
			gfx_dpos = dv + [-bw - gap, bh + 3, 0];       // the list spans < value >
		}
		if (Gfx_Chip(nid, dv + [vw + gap, 0, 0], [bw, bh, 0], bh * 0.5, ">", tsz, FALSE, idx >= 0 && idx < cnt - 1))
			Gfx_SetIndex(row, idx + 1);

		at_x = dv_x + vw + gap + bw + tsz;
		if (why != "")
			sui_text([at_x, at_y + (bh - hint) * 0.5], [hint, hint], why, SUI_THEME_MUTED, 1, 0);
		else if (idx >= 0)
		{
			pw = ceil(tsz * 0.6);
			for (i = 0; i < cnt; i = i + 1)
				sui_roundbox([at_x + i * (pw + gap), at_y + (bh - pw) * 0.5], [pw, pw, 0], pw * 0.3,
				             (i <= idx) ? SUI_THEME_ACCENT : SUI_THEME_EDGE_HI, (i == idx) ? 1 : 0.55);
			sui_text([at_x + cnt * (pw + gap) + gap, at_y + (bh - hint) * 0.5], [hint, hint],
			         sprintf("%g/%g", idx + 1, cnt), SUI_THEME_MUTED, 1, 0);
		}

		if (sui_is_hovered(rid) || sui_is_hovered(pid) || sui_is_hovered(vid) || sui_is_hovered(nid))
		{
			val = Gfx_Tip(row);
			sui_tooltip_for(rid, val, sc);
			sui_tooltip_for(pid, val, sc);
			sui_tooltip_for(vid, val, sc);
			sui_tooltip_for(nid, val, sc);
		}
		k = k + 1;
		row = stof(Gfx_Field(rows, k, " "));
	}
	if (!dropseen)
		gfx_drop = 0;

	// Footer: what * means, the cfg_save_auto trap, Reload map and Close.
	at = pos + [pad, size_y - fh, 0];
	drawfill(at + [-pad * 0.5, -pad * 0.4, 0], [size_x - pad, 1, 0], SUI_THEME_EDGE_HI, 0.6, 0);
	if (Gfx_Chip("gfx_retry", at + [size_x - pad * 2 - tsz * 16 - gap, 0, 0], [tsz * 9, rh, 0], rh * 0.5,
	             "Reload map", tsz, FALSE, TRUE))
	{
		Gfx_Close(); sui_end(); Font_Reset();
		localcmd("retry\n");
		return;
	}
	sui_tooltip_for("gfx_retry", "Console:  retry\nReloads the map you are hosting, or reconnects to a server. "
	                "It can reuse cached map data, so a * setting that still does not show needs the map loaded fresh.", sc);
	if (Gfx_Chip("gfx_done", at + [size_x - pad * 2 - tsz * 7, 0, 0], [tsz * 7, rh, 0], rh * 0.5, "Close", tsz, FALSE, TRUE))
	{
		Gfx_Close(); sui_end(); Font_Reset(); return;
	}
	sui_text(at + [0, (rh - hint) * 0.5 - hint * 0.6, 0], [hint, hint], "*", SUI_THEME_FOCUS, 1, 0);
	sui_text(at + [hint * 0.9, (rh - hint) * 0.5 - hint * 0.6, 0], [hint, hint],
	         "applies after Reload map", SUI_THEME_MUTED, 1, 0);
	if (cvar("cfg_save_auto"))
		sui_text(at + [hint * 0.9, (rh - hint) * 0.5 + hint * 0.7, 0], [hint, hint],
		         "settings save on quit", SUI_THEME_MUTED, 1, 0);
	else
		sui_text(at + [0, rh + hint * 0.4, 0], [hint, hint],
		         "cfg_save_auto is 0: changes here will not survive a quit (seta cfg_save_auto 1, or cfg_save).",
		         SUI_THEME_BAD, 1, 0);

	// The open value list, last so it owns the hit-tests over the rows it covers.
	if (gfx_drop)
	{
		n = Gfx_Count(gfx_drop);
		idx = Gfx_Index(gfx_drop);
		gfx_dsize = [vw + (bw + gap) * 2, n * (bh + 2) + pad * 0.6, 0];
		gfx_dpos_y = bound(4, gfx_dpos_y, max(4, scr_y - gfx_dsize_y - 4));
		sui_style_panel(gfx_dpos, gfx_dsize, ceil(pad * 0.5), 1);
		rows = Gfx_Def(gfx_drop);
		for (i = 0; i < n; i = i + 1)
		{
			at = gfx_dpos + [pad * 0.3, pad * 0.3 + i * (bh + 2), 0];
			if (Gfx_Chip(sprintf("gfx_o%g", i), at, [gfx_dsize_x - pad * 0.6, bh, 0], bh * 0.5,
			             Gfx_Field(Gfx_Field(rows, 3, "|"), i, ";"), tsz, i == idx, TRUE))
			{
				Gfx_SetIndex(gfx_drop, i);
				gfx_drop = 0;
				break;
			}
			val = Gfx_Field(Gfx_Field(rows, 2, "|"), i, " ");
			sui_text(at + [gfx_dsize_x - pad * 0.6 - stringwidth(val, TRUE, [hint, hint]) - hint, (bh - hint) * 0.5, 0], [hint, hint],
			         val, SUI_THEME_MUTED, 1, 0);
		}
	}
	sui_end();
	Font_Reset();
};

float(float evtype, float scanx, float chary, float devid) Gfx_Input =
{
	if (!ui_gfx_open || sc_held)
		return FALSE;
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE)
	{
		if (gfx_drop)
			gfx_drop = 0;
		else
			Gfx_Close();
		return TRUE;
	}
	if (evtype == IE_MOUSEABS)
	{
		gfx_mx = scanx; gfx_my = chary;
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE1)
	{
		if (evtype == IE_KEYUP && gfx_drag)
		{
			gfx_drag = FALSE;
			return TRUE;
		}
		// A press outside the open list closes it and still lands where it was aimed, except on the
		// list's own value box, whose click would open it again.
		if (evtype == IE_KEYDOWN && gfx_drop)
		if (gfx_mx < gfx_dpos_x || gfx_mx >= gfx_dpos_x + gfx_dsize_x || gfx_my < gfx_dpos_y || gfx_my >= gfx_dpos_y + gfx_dsize_y)
		{
			_sui_mouse_move(_cursor_position, FALSE);
			if (_hover_action_count > 0)
			if (_hover_actions[0] == sprintf("gfx_v%g", gfx_drop))
			{
				gfx_drop = 0;
				return TRUE;
			}
			gfx_drop = 0;
		}
		if (evtype == IE_KEYDOWN)
		if (gfx_mx >= gfx_pos_x && gfx_mx < gfx_pos_x + gfx_size_x - gfx_titleh * 1.2)
		if (gfx_my >= gfx_pos_y && gfx_my < gfx_pos_y + gfx_titleh)
		{
			gfx_drag = TRUE;
			gfx_off = [gfx_mx, gfx_my, 0] - gfx_pos;
			return TRUE;
		}
	}
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN)
			_sui_mouse_move(_cursor_position, FALSE);
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	// Over the panel the wheel is the panel's: surfers bind it to +jump.
	if (scanx == K_MWHEELUP || scanx == K_MWHEELDOWN)
	if (gfx_mx >= gfx_pos_x && gfx_mx < gfx_pos_x + gfx_size_x && gfx_my >= gfx_pos_y && gfx_my < gfx_pos_y + gfx_size_y)
		return TRUE;
	return FALSE;
};

/*
  THE CONSOLE HANDLE (build 33; P1566 tabs).

      gfx_menu             toggle the panel
      gfx_menu open|close
      gfx_menu page <n>    show tab n (1-based); `tab` is the same
      gfx_menu cycle <n>   step row n to its next value, wrapping
      gfx_menu status [n]  print every row (or row n): value, position, latch mark, why it is inert
      gfx_menu resetpos    put the panel back where it starts
      gfx_menu move|press|release|click <x> <y>
                           arms: the pointer at pixel x y through Gfx_Input (three moves first: sui's cursor
                           wakes after ~10 px of motion); prints what is under it
*/
float() Gfx_Console =
{
	local float i, n, t, k, hits, x, y;
	local string inert, a1, a2, a3;

	// Read the arguments before anything below tokenizes (Gfx_Index, Gfx_Count).
	a1 = argv(1);
	a2 = argv(2);
	a3 = argv(3);
	Gfx_WaterSupport();
	if (a1 == "move" || a1 == "press" || a1 == "release" || a1 == "click")
	{
		x = stof(a2);
		y = stof(a3);
		for (i = 3; i >= 0; i = i - 1)
			Gfx_Input(IE_MOUSEABS, x - i * 6, y - i * 4, 0);
		if (a1 == "press" || a1 == "click")
			Gfx_Input(IE_KEYDOWN, K_MOUSE1, 0, 0);
		if (a1 == "release" || a1 == "click")
			Gfx_Input(IE_KEYUP, K_MOUSE1, 0, 0);
		print(sprintf("gfx_menu %s %g %g: ", a1, x, y),
		      sprintf("open %g tab %g drop %g drag %g under %s\n", ui_gfx_open, ui_gfx_page + 1, gfx_drop, gfx_drag,
		              (_hover_action_count > 0) ? _hover_actions[0] : "-"));
		return TRUE;
	}
	if (a1 == "page" || a1 == "tab")
	{
		n = stof(a2) - 1;
		if (n < 0 || n >= GFX_TABS)
		{
			print(sprintf("gfx_menu %s: 1..%g\n", a1, GFX_TABS));
			return TRUE;
		}
		ui_gfx_page = n;
		gfx_drop = 0;
		if (!ui_gfx_open)
			Gfx_Open();
		return TRUE;
	}

	if (a1 == "cycle")
	{
		n = stof(a2);
		if (n < 1 || n > GFX_ROWS)
		{
			print(sprintf("gfx_menu cycle: 1..%g\n", GFX_ROWS));
			return TRUE;
		}
		Gfx_Cycle(n);
		// The set is deferred (localcmd): read it back from the far side of the queue (build 32's ghost speed trap).
		localcmd(sprintf("gfx_menu status %g\n", n));
		return TRUE;
	}

	if (a1 == "status")
	{
		if (a2 != "")
		{
			i = stof(a2);
			n = i;
		}
		else
		{
			i = 1;
			n = GFX_ROWS;
			print(sprintf("^5gfx_menu^7  %g settings in %g tabs  (tab %g shown, open %g)  panel %v size %v\n",
			              GFX_ROWS, GFX_TABS, ui_gfx_page + 1, ui_gfx_open, gfx_pos, gfx_size));
			for (t = 0; t < GFX_TABS; t = t + 1)
				print(sprintf("  tab %g %-16s rows %s\n", t + 1, Gfx_TabName(t), Gfx_TabRows(t)));
			// Every row on exactly one tab (19 and 20 only where cheats are on).
			for (k = 1; k <= GFX_ROWS; k = k + 1)
			{
				hits = 0;
				for (t = 0; t < GFX_TABS; t = t + 1)
					if (strstrofs(strcat(" ", Gfx_TabRows(t), " "), sprintf(" %g ", k), 0) >= 0)
						hits = hits + 1;
				if (hits != 1)
				if (!(hits == 0 && (k == 19 || k == 20) && !Gfx_Cheats()))
					print(sprintf("  ^1row %g is on %g tabs^7\n", k, hits));
			}

			// Build 33: seta only reaches ftesurf.cfg if something writes it; a saved 0 here keeps itself alive.
			if (!cvar("cfg_save_auto"))
				print("  ^1cfg_save_auto is 0^7 -- changes here will NOT survive a quit."
				      "  `seta cfg_save_auto 1` once, or `cfg_save` each time.\n");
		}

		for (; i <= n; i = i + 1)
		{
			inert = Gfx_Inert(i);
			print(sprintf("  %2g %-21s %-14s %-24s %-6s %s%s\n",
			              i, Gfx_Cvar(i), Gfx_Label(i), Gfx_ValueName(i), Gfx_Position(i),
			              Gfx_NeedsReload(i) ? "^3*needs rebuild/map load^7 " : "",
			              (inert != "") ? sprintf("^1inert^7: %s", inert) : ""));
		}
		return TRUE;
	}

	if (a1 == "open")
	{
		if (!ui_gfx_open)
			Gfx_Open();
		return TRUE;
	}
	if (a1 == "close")
	{
		if (ui_gfx_open)
			Gfx_Close();
		return TRUE;
	}
	if (a1 == "resetpos")
	{
		cvar_set("hud_gfx_x", "0.0333");
		cvar_set("hud_gfx_y", "0.338");
		return TRUE;
	}
	if (a1 != "")
	{
		print("gfx_menu [open | close | page|tab <n> | cycle <n> | status [n] | resetpos | move|press|release|click <x> <y>]\n");
		return TRUE;
	}

	if (ui_gfx_open)
		Gfx_Close();
	else
		Gfx_Open();
	return TRUE;
};
