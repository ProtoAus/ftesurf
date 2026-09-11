/*
===========================================================================
  cl_zones.qc -- draw the Momentum timer zones as a world wireframe.

  The data and its schema are sh_zones.qc's problem; this file is only
  geometry, colour and culling.

  WHY GL_LINES AND NOT CAMERA-FACING QUADS
  ----------------------------------------
  R_BeginPolygon("") with EXACTLY TWO R_PolygonVertex calls before
  R_EndPolygon sets BEF_LINES (pr_csqc.c:1686-1690), and that path reaches
  gl_line_width: BE_GenPolyBatches picks buildmeshes = R_DB_Poly
  (gl_alias.c:3192), which is precisely what gl_backend.c:3385 tests before
  applying the width.  So a zone edge is four builtin calls and zero maths.

  The alternative -- nettest's camera-facing quad (cl_debuginfo.qc:194-207) --
  is two normalizes, a cross product and six calls per edge.  At 3N edges per
  zone and 162 zones on the worst map that is 2361 edges a frame; the cheap
  path is worth having.

  Consecutive polygons with the same flags batch into one draw call, so the
  whole overlay is typically one or two.

  CAVEAT: on a core-profile GL driver gl_maxlinewidth clamps to 1 px and the
  engine says so at startup (gl_backend.c:1746).  That is cosmetic.  If it
  bites, `zone_lines 0` switches to the quad path with zone_thickness in world
  units.

  Drawn BEFORE renderscene() and with the default shader, which is
  shader_draw_fill_trans (pr_csqc.c:1604-1607) -- it has no nodepthtest, so
  zones are correctly hidden by walls in front of them.
===========================================================================
*/

// Momentum's own shipped defaults (momentum/cfg/config.cfg:406-419), in 0-255,
// so muscle memory transfers.  Momentum's overbounce default collides with its
// bhop colour; yellow is used here instead so the two are distinguishable.
#define ZC_START        "0 255 0"
#define ZC_END          "255 0 0"
#define ZC_STAGE        "120 120 255"
#define ZC_CHECKPOINT   "255 150 0"
#define ZC_CANCEL       "255 100 255"
#define ZC_BHOP         "100 0 255"
#define ZC_OVERBOUNCE   "255 255 0"

float  zone_cv_draw, zone_cv_dist, zone_cv_alpha, zone_cv_bonus;
float  zone_cv_lines, zone_cv_thickness;

/*
  BUILD 40.  Read once per frame, like every other zone cvar.

  zone_cv_shader is the NAME handed to R_BeginPolygon, resolved here rather
  than at each of the three call sites so the whole overlay cannot end up half
  x-ray and half not within one frame.  "" is the engine's built-in
  shader_draw_fill_trans and is the depth-tested default; see
  scripts/zones.shader for the other one.
*/
string zone_cv_shader;
float  zone_cv_fill, zone_cv_fillalpha;
float  zone_cv_typedraw[ZONE_TYPES];
vector zone_cv_typecol[ZONE_TYPES];

string(float t) Zone_CvarStem = { return strcat("zonetype_", Zone_TypeName(t)); };

/*
  Accept a colour in either convention.  Momentum writes 0-255 and this is
  meant to be pasted from a Momentum config; QC and the renderer want 0-1.
  Any component above 1 means the whole triple is 0-255 -- "1 1 1" stays
  white either way, so there is no ambiguous case to get wrong.
*/
vector(string s) Zone_ParseColor =
{
	local vector c = stov(s);
	if (c_x > 1 || c_y > 1 || c_z > 1)
		c = c * (1 / 255);
	return c;
};

void() Zone_RegisterCvars =
{
	registercvar("zone_draw",      "1");
	/*
	  BUILD 40: 0, WHICH THIS TEST HAS ALWAYS MEANT AS "NO LIMIT".

	  4096 units is about 78 metres, and a surf map is tens of thousands of
	  units end to end -- so the end zone, and every stage past the first,
	  were silently never drawn.  That is the larger half of "make the zones
	  fully visible", and it needs no new code at all: the gate below is
	  already written as `if (maxdist > 0 && ...)`.

	  Nothing is saved by the cull.  The whole overlay is a handful of
	  two-vertex polygons that batch into one or two draw calls (see this
	  file's header), and the worst shipped map is 162 regions.  Set it back
	  to 4096 if a map ever proves otherwise.
	*/
	registercvar("zone_draw_dist", "0");
	registercvar("zone_alpha",     "0.9");
	registercvar("zone_bonus",     "1");
	registercvar("zone_lines",     "1");
	registercvar("zone_thickness", "1.5");
	registercvar("zone_debug",     "0");

	/*
	  BUILD 40 -- the other half of "fully visible", and it is a separate
	  question from range.

	  zone_xray 1 draws the zones through the world.  The default stays 0
	  because being hidden by walls is not a bug: it is what makes the overlay
	  read as geometry in the map rather than as an annotation floating over
	  it, and cl_main.qc:552 orders the draw before renderscene() to get it.
	  See scripts/zones.shader for how the material is reached and what it
	  costs (overlapping zones resolve by table order, not by depth).

	  zone_fill 1 adds the side faces, so a zone reads as Momentum's
	  translucent volume instead of a wire cage.  Off by default because at
	  162 regions it is 162 more batches and because the cage is what the
	  colours were tuned against; zone_fill_alpha is deliberately much lower
	  than zone_alpha, since a face covers hundreds of times the pixels an
	  edge does.
	*/
	registercvar("zone_xray",       "0");
	registercvar("zone_fill",       "0");
	registercvar("zone_fill_alpha", "0.10");

	/*
	  BUILD 40 -- THERE IS NO zone_pvs, AND THAT IS A MEASURED RESULT.

	  "quake/source uses BSP and can you use PVS to decide if they are
	  rendered?"  Two answers, and the first one is the important one:

	  PVS WAS NEVER WHAT WAS HIDING THEM.  The zones are not entities and are
	  never networked -- both VMs parse the same Momentum JSON independently at
	  map load (sv_zones.qc:5-7), nothing in this game sets .SendEntity, so no
	  server-side PVS test has ever been applied to a single one of them, and
	  .pvsflags is declared in the defs and assigned nowhere.  What was hiding
	  them was a 4096-unit distance gate and the depth test, both above.

	  And a CLIENT-side gate was built, tested, and removed.  checkpvs (#240) is
	  registered for CSQC and takes its world from the client's own
	  (pr_bgcmd.c:1412-1433), so it looked like a free companion to zone_xray --
	  show the zones in rooms you could see into, through whatever is in front.
	  It culled EVERY zone on the map, including the four in front of the
	  camera, in both of its forms: with a SOLID_NOT probe (never linked into
	  the leaf tree, so pvsinfo is empty) and with a SOLID_BBOX one that is
	  linked.  `zone_debug` says `0 of 19 zones passed the cull` on
	  surf_aesthetic either way, against `4 of 19` with it off.

	  It is not shipped disabled, it is not shipped at all.  A visibility switch
	  that hides everything is worse than no switch, and one that is present but
	  known-broken is worse than both -- somebody would find it in a config dump
	  in six months and turn it on.  If it is ever wanted, the thing to chase is
	  PF_checkpvs passing a NULL buffer to ClusterPVS and VBSP_EdictInFatPVS's
	  area test, neither of which was run down here.
	*/

	// Cancel / bhop / overbounce default OFF: allowBhop reaches 68 regions on
	// a single map and would bury the timer zones you actually came to see.
	registercvar("zonetype_start_draw",      "1");
	registercvar("zonetype_end_draw",        "1");
	registercvar("zonetype_stage_draw",      "1");
	registercvar("zonetype_checkpoint_draw", "1");
	registercvar("zonetype_cancel_draw",     "0");
	registercvar("zonetype_bhop_draw",       "0");
	registercvar("zonetype_overbounce_draw", "0");

	registercvar("zonetype_start_color",      ZC_START);
	registercvar("zonetype_end_color",        ZC_END);
	registercvar("zonetype_stage_color",      ZC_STAGE);
	registercvar("zonetype_checkpoint_color", ZC_CHECKPOINT);
	registercvar("zonetype_cancel_color",     ZC_CANCEL);
	registercvar("zonetype_bhop_color",       ZC_BHOP);
	registercvar("zonetype_overbounce_color", ZC_OVERBOUNCE);

	registercommand("zone_list");
	registercommand("zone_reload");

	// Pure geometry, so it runs perfectly well on this side and needs no map
	// -- see Zone_SelfTest.
	registercommand("zone_selftest");

	// zone_goto and ent_census do their work on the SERVER, but an unknown
	// console command does NOT reach SV_ParseClientCommand -- Cmd_ExecuteString
	// offers it to SSQC's SV_ParseServerCommand hook instead (cmd.c:3167-3169),
	// where `self` is world and there is no player to move.  Registering them
	// here and forwarding with `cmd` puts them back on the client-command path,
	// which is the one that runs as the player.
	registercommand("zone_goto");
	registercommand("ent_census");
};

void() Zone_ReadCvars =
{
	local float t;

	zone_cv_draw      = cvar("zone_draw");
	zone_cv_dist      = cvar("zone_draw_dist");
	zone_cv_alpha     = cvar("zone_alpha");
	zone_cv_bonus     = cvar("zone_bonus");
	zone_cv_lines     = cvar("zone_lines");
	zone_cv_thickness = cvar("zone_thickness");

	// Build 40.  An unregistered cvar reads 0, which is this file's default for
	// all three, so no cvar_string guard is needed the way hud_strafe_orient
	// wanted one -- there the default was 1 and 0 was indistinguishable from
	// "not registered yet".
	zone_cv_fill      = cvar("zone_fill");
	zone_cv_fillalpha = cvar("zone_fill_alpha");
	zone_cv_shader    = cvar("zone_xray") ? "ftesurf_zone_xray" : "";

	for (t = 0; t < ZONE_TYPES; t = t + 1)
	{
		zone_cv_typedraw[t] = cvar(strcat(Zone_CvarStem(t), "_draw"));
		zone_cv_typecol[t]  = Zone_ParseColor(cvar_string(strcat(Zone_CvarStem(t), "_color")));
	}
};

/*
===========================================================================
  Loading
===========================================================================
*/

/*
  The legacy BSP path.

  Seventeen maps predate the zone editor and carry trigger_momentum_timer_*
  brush entities instead.  getentitytoken walks the raw entity lump
  (pr_csqc.c:4366-4398), and a temporary entity with the submodel bound gives
  us the AABB -- which is already the extruded-polygon shape the tables hold,
  so nothing downstream needs to know where a zone came from.
*/
float() Zone_LoadFromBsp =
{
	local string tok, key, cn, mdl;
	local entity probe;
	local float type, stage, n;

	Zone_Clear();
	n = 0;

	probe = spawn();

	getentitytoken(0);				// reset to the start of the lump
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;

		cn = mdl = "";
		stage = 0;

		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			if      (key == "classname") cn = tok;
			else if (key == "model")     mdl = tok;
			else if (key == "stage")     stage = stof(tok);
		}

		type = Zone_LegacyType(cn);
		if (type < 0 || mdl == "" || substring(mdl, 0, 1) != "*")
			continue;

		setmodel(probe, mdl);
		Zone_AddBox(probe.mins, probe.maxs, type, stage);
		n = n + 1;
	}

	remove(probe);

	if (n)
		zone_source = ZSRC_BSP;
	return n > 0;
};

void() Zone_LoadForMap =
{
	local string map;

	map = serverkey("map");
	zone_mapname = map;
	Zone_Clear();

	if (map == "")
		return;

	// local BEFORE online: dropping a file in ftesurf/maps/zones/local/ has to
	// override Momentum's shipped copy, which is the whole point of the
	// directory.  (surf_drift is the test: local says 10 regions, online 12.)
	if (Zone_LoadJson(strcat("maps/zones/local/",  map, ".json"), ZSRC_LOCAL))
		;
	else if (Zone_LoadJson(strcat("maps/zones/online/", map, ".json"), ZSRC_ONLINE))
		;
	else
		Zone_LoadFromBsp();

	// SILENT when there is nothing -- 783 Momentum maps and every one of the
	// 1082 CS:S maps have no zone data at all, so this is the common case and
	// must not print.
	if (zone_count)
		print(sprintf("zones: %g on %s (%s)\n",
		              zone_count, map, Zone_SourceName(zone_source)));
	else
		dprint(sprintf("zones: none for %s\n", map));
};

/*
===========================================================================
  Drawing
===========================================================================
*/
void(vector a, vector b, vector col, float alpha) Zone_Line =
{
	// Exactly two vertices between Begin and End is what selects BEF_LINES.
	// Build 40: the shader name, so zone_xray reaches the lines and not only
	// the quads.  "" is the built-in depth-tested fill and is the default.
	R_BeginPolygon(zone_cv_shader);
	R_PolygonVertex(a, '0 0 0', col, alpha);
	R_PolygonVertex(b, '0 0 0', col, alpha);
	R_EndPolygon();
};

/*
  BUILD 40.  One side face of a zone, from the two ends of a bottom edge.

  The quad is a0 -> b0 -> b1 -> a1, i.e. up the far corner and back down the
  near one, so it is planar by construction whatever the ring does.  DRAWFLAG_
  TWOSIDED (0x400, pr_common.h:447) is not decoration: without it
  PF_R_PolygonBegin leaves the batch single-sided (pr_csqc.c:1640-1641) and the
  face would vanish from inside the zone -- which is precisely where a player
  stands when they most want to see where the box ends.

  Drawn at zone_fill_alpha rather than zone_alpha, because a face covers some
  hundreds of times the pixels an edge does and the two want completely
  different numbers to read as the same strength.
*/
void(vector a0, vector b0, vector a1, vector b1, vector col, float alpha) Zone_Face =
{
	R_BeginPolygon(zone_cv_shader, DRAWFLAG_TWOSIDED);
	R_PolygonVertex(a0, '0 0 0', col, alpha);
	R_PolygonVertex(b0, '0 0 0', col, alpha);
	R_PolygonVertex(b1, '0 0 0', col, alpha);
	R_PolygonVertex(a1, '0 0 0', col, alpha);
	R_EndPolygon();
};

// The fallback for drivers that clamp line width to 1: a camera-facing quad
// of zone_thickness world units.  More expensive, but it is per EDGE and only
// when asked for.
void(vector a, vector b, vector col, float alpha, vector eye) Zone_Quad =
{
	local vector dir, side, off;

	dir = b - a;
	if (dir == '0 0 0')
		return;

	side = normalize(crossproduct(normalize(dir), normalize(((a + b) * 0.5) - eye)));
	off = side * (zone_cv_thickness * 0.5);

	R_BeginPolygon(zone_cv_shader);
	R_PolygonVertex(a - off, '0 0 0', col, alpha);
	R_PolygonVertex(a + off, '0 0 0', col, alpha);
	R_PolygonVertex(b + off, '0 0 0', col, alpha);
	R_PolygonVertex(b - off, '0 0 0', col, alpha);
	R_EndPolygon();
};

void(float z, vector col, float alpha, vector eye) Zone_DrawOne =
{
	local float i, n, first;
	local vector a, b, a0, b0, a1, b1;

	first = zone_first[z];
	n = zone_npts[z];

	for (i = 0; i < n; i = i + 1)
	{
		a = zone_pt[first + i];
		b = zone_pt[first + ((i + 1) % n)];

		a0 = [a_x, a_y, zone_bottom[z]];
		b0 = [b_x, b_y, zone_bottom[z]];
		a1 = [a_x, a_y, zone_top[z]];
		b1 = [b_x, b_y, zone_top[z]];

		// Build 40: the face first, so the edges land on top of their own fill
		// rather than being half-swallowed by it.  Same ring, same two heights;
		// no extra geometry is derived, only submitted.
		if (zone_cv_fill)
			Zone_Face(a0, b0, a1, b1, col, zone_cv_fillalpha);

		if (zone_cv_lines)
		{
			Zone_Line(a0, b0, col, alpha);   // bottom ring
			Zone_Line(a1, b1, col, alpha);   // top ring
			Zone_Line(a0, a1, col, alpha);   // the vertical at this corner
		}
		else
		{
			Zone_Quad(a0, b0, col, alpha, eye);
			Zone_Quad(a1, b1, col, alpha, eye);
			Zone_Quad(a0, a1, col, alpha, eye);
		}
	}
};

void() Zone_Draw =
{
	local float z, t, maxdist, dbg, drawn;
	local vector eye, fwd, d;

	if (serverkey("map") != zone_mapname)
		Zone_LoadForMap();

	Zone_ReadCvars();

	if (!zone_cv_draw || !zone_count)
		return;

	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;

	maxdist = zone_cv_dist;
	drawn = 0;

	// Cull trace: why a zone you expected is not on screen.  Set zone_debug 1
	// and it dumps ONE frame and clears itself -- a latch would still be one
	// bool away from filling the console at 600 fps, and this is a tool you
	// reach for when something is already confusing.
	dbg = cvar("zone_debug");
	if (dbg)
	{
		cvar_set("zone_debug", "0");
		print(sprintf("zone_debug: eye %.0f %.0f %.0f  fwd %.2f %.2f %.2f  maxdist %g\n",
		              eye_x, eye_y, eye_z, fwd_x, fwd_y, fwd_z, maxdist));
		// Build 40: the new gates get a line too, so "I set zone_xray and
		// nothing changed" is answerable without reading this file.
		print(sprintf("zone_debug: xray %s  fill %g@%.2f\n",
		              (zone_cv_shader == "") ? "off (depth-tested)" : zone_cv_shader,
		              zone_cv_fill, zone_cv_fillalpha));
	}

	for (z = 0; z < zone_count; z = z + 1)
	{
		t = zone_type[z];
		if (!zone_cv_typedraw[t])
			continue;
		if (!zone_cv_bonus && zone_track[z] != 0)
			continue;

		d = zone_centre[z] - eye;

		if (dbg)
			print(sprintf("  %3g %-10s dist %8.0f radius %7.0f dot %9.0f\n",
			              z, Zone_TypeName(t), vlen(d), zone_radius[z], fwd * d));

		// Distance and behind-camera, both off the precomputed centre/radius.
		// Deliberately NO traceline occlusion test: a zone you are about to
		// surf into is legitimately behind the ramp you are on, and hiding it
		// would defeat the point of drawing it at all.
		if (maxdist > 0 && vlen(d) - zone_radius[z] > maxdist)
			continue;
		if (fwd * d < -zone_radius[z])
			continue;

		Zone_DrawOne(z, zone_cv_typecol[t], zone_cv_alpha, eye);
		drawn = drawn + 1;
	}

	if (dbg)
		print(sprintf("zone_debug: %g of %g zones passed the cull\n", drawn, zone_count));
};

/*
===========================================================================
  Commands
===========================================================================
*/
void() Zone_List =
{
	local float z;

	if (serverkey("map") != zone_mapname)
		Zone_LoadForMap();

	Zone_ReadCvars();

	print(sprintf("zone_list: %g zones, %g points, source %s%s\n",
	              zone_count, zone_ptcount, Zone_SourceName(zone_source),
	              zone_overflow ? " ^1(TRUNCATED -- hit a cap)" : ""));

	/*
	  BUILD 47: SAY WHERE THE TRIGGER IS, BECAUSE IT IS NO LONGER THE CAGE.

	  Under run_zone_hull the effective trigger is the Minkowski sum of the drawn
	  ring with the player's hull rectangle -- so the wireframe you can see stops
	  being the boundary things fire on.  That is exactly the class of invisible
	  mismatch the essay on Zone_PointInside warns about ("the renderer only
	  draws the ring and never tests a point against it"), so it gets said out
	  loud here rather than left for someone to rediscover from a split that
	  fired early.

	  A line rather than a second wireframe: the offset is a CONSTANT, and one
	  sentence carries it exactly.  Drawing it needs the ring's winding and is
	  only exact away from a reflex vertex, so it is a separate job.
	*/
	if (serverkeyfloat("run_zone_hull") >= 1)
		print("  trigger = the drawn cage plus 16 units horizontally and 62 units DOWNWARD\n"
		      "           (origin is at the feet, so it never grows upward).  run_zone_hull 0 to compare.\n");
	else
		print("  trigger = the drawn cage exactly (run_zone_hull 0 -- the point test)\n");

	// The resolved draw flag and colour per type.  Worth printing: a wrong
	// colour looks identical to a wrong TYPE in the world, and this is what
	// separates the two.
	for (z = 0; z < ZONE_TYPES; z = z + 1)
	{
		local vector tc = zone_cv_typecol[z];
		print(sprintf("  %-11s draw %g  rgb %.2f %.2f %.2f  (%s)\n",
		              Zone_TypeName(z), zone_cv_typedraw[z], tc_x, tc_y, tc_z,
		              cvar_string(strcat(Zone_CvarStem(z), "_color"))));
	}

	if (!zone_count)
		return;

	print("  idx  type        trk  seg  pts       bottom..top   centre\n");
	for (z = 0; z < zone_count; z = z + 1)
	{
		// Two prints because fteqcc caps varargs at 8 and SILENTLY drops the
		// rest -- it warns, but the dropped arguments still format as zeroes.
		local vector c = zone_centre[z];
		print(sprintf("  %3g  %-10s  %3g  %3g  %3g  ",
		              z, Zone_TypeName(zone_type[z]),
		              zone_track[z], zone_seg[z], zone_npts[z]));
		print(sprintf("%7.0f..%-7.0f  %.0f %.0f %.0f\n",
		              zone_bottom[z], zone_top[z], c_x, c_y, c_z));
	}
};

float(string cmd) Zone_ConsoleCommand =
{
	tokenize(cmd);

	if (argv(0) == "zone_list")
	{
		Zone_List();
		return TRUE;
	}

	if (argv(0) == "zone_reload")
	{
		zone_mapname = "";
		Zone_LoadForMap();
		return TRUE;
	}

	if (argv(0) == "zone_selftest")
	{
		Zone_SelfTest();
		return TRUE;
	}

	if (argv(0) == "zone_goto")
	{
		if (argv(1) == "")
		{
			print("zone_goto <n> -- stand in zone n.  See zone_list.\n");
			return TRUE;
		}
		localcmd(sprintf("cmd zone_goto %s\n", argv(1)));
		return TRUE;
	}

	if (argv(0) == "ent_census")
	{
		localcmd("cmd ent_census\n");
		return TRUE;
	}

	return FALSE;
};
