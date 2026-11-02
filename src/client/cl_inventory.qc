/* Account inventory and procedural cosmetics. Only the lobby publishes *kit.
   The ice halo is depth-tested per pixel against the scene: no wallhack (P1230, Inv_GlowPass).
   Shaders travel in CSQC; the crown's texture is models/party_crown.png, with polygons without it. */
float inv_ready, inv_revision, inv_roles, inv_own1, inv_own2, inv_colour, inv_eq1, inv_eq2, inv_wait;
string inv_who;
entity inv_shell;
float inv_shader;

vector(float colour) Inv_Colour = { return sui_inventory_colour(colour); };

void() Inv_Init =
{
	registercommand("inventory");
	registercommand("inventory_clear");
	registercommand("inventory_state");
};

void() Inv_Clear =
{
	inv_ready = inv_roles = inv_own1 = inv_own2 = inv_eq1 = inv_eq2 = inv_wait = 0;
	if (inv_who != "") strunzone(inv_who);
	inv_who = "";
};

// Non-secret presentation only. Server keys never authorize a grant on backend.
vector(float slot) Inv_Public =
{
	local string packed;
	local vector result;
	packed = getplayerkeyvalue(slot, "*kit");
	result = [stof(Gfx_Field(packed, 0, " ")), stof(Gfx_Field(packed, 1, " ")), stof(Gfx_Field(packed, 2, " "))];
	if (result_x < 0 || result_x > 7 || result_x != floor(result_x)) return '0 0 0';
	if ((result_y != 0 && result_y != 1) || result_z < 0 || result_z > 12 || result_z != floor(result_z)) return '0 0 0';
	return result;
};

float() Inv_Valid =
{
	return inv_ready && inv_who != "" && !strcmp(inv_who, getplayerkeyvalue(player_localnum, "*ahash"));
};

float(float count) Inv_ConsoleCommand =
{
	local string command, who;
	local float revision, roles, own1, own2, colour, eq1, eq2;
	command = argv(0);
	if (!strcmp(command, "inventory_clear")) { Inv_Clear(); return TRUE; }
	if (!strcmp(command, "inventory_state"))
	{
		if (count != 9) return TRUE;
		who = argv(1); revision = stof(argv(2)); roles = stof(argv(3));
		own1 = stof(argv(4)); own2 = stof(argv(5)); colour = stof(argv(6)); eq1 = stof(argv(7)); eq2 = stof(argv(8));
		if (strcmp(who, getplayerkeyvalue(player_localnum, "*ahash")) || strlen(who) != 8) return TRUE;
		if (revision < 0 || revision > 16777215 || revision != floor(revision)) return TRUE;
		if (Inv_Valid() && revision < inv_revision) return TRUE;
		if (roles < 1 || roles > 7 || roles != floor(roles)) return TRUE;
		if ((own1 != 0 && own1 != 1) || (own2 != 0 && own2 != 1)) return TRUE;
		if ((eq1 != 0 && eq1 != 1) || (eq2 != 0 && eq2 != 1) || eq1 > own1 || eq2 > own2) return TRUE;
		if (colour < 0 || colour > 11 || colour != floor(colour)) return TRUE;
		if (inv_who != "") strunzone(inv_who);
		inv_who = strzone(who);
		inv_revision = revision; inv_roles = roles; inv_own1 = own1; inv_own2 = own2;
		inv_colour = colour; inv_eq1 = eq1; inv_eq2 = eq2; inv_ready = TRUE; inv_wait = 0;
		return TRUE;
	}
	if (strcmp(command, "inventory")) return FALSE;
	print(sprintf("Inventory: ready %g revision %.0f owned %g/%g equipped %g/%g hat colour %g\n",
	              Inv_Valid(), inv_revision, inv_own1, inv_own2, inv_eq1, inv_eq2, inv_colour));
	return TRUE;
};

float(float roles, float textsize) Inv_BadgeWidth =
{
	local float w;
	w = 0;
	if (roles & 4) w = w + stringwidth("Developer", TRUE, [textsize, textsize]) + textsize * 1.4;
	if (roles & 2) w = w + stringwidth("Zoner", TRUE, [textsize, textsize]) + textsize * 1.4;
	if (roles & 1) w = w + stringwidth("Tester", TRUE, [textsize, textsize]) + textsize * 1.4;
	return w;
};

float(vector p, float roles, float textsize, float width) Inv_Badges =
{
	local float bit, w, x;
	local string label;
	local vector colour;
	x = p_x;
	for (bit = 4; bit >= 1; bit = bit / 2)
	{
		if (!(roles & bit)) continue;
		label = bit == 4 ? "Developer" : (bit == 2 ? "Zoner" : "Tester");
		colour = bit == 4 ? '0.86 0.55 1' : (bit == 2 ? '1 0.76 0.3' : '0.4 0.83 1');
		w = stringwidth(label, TRUE, [textsize, textsize]) + textsize;
		if (x + w > p_x + width) break;
		sui_roundbox([x, p_y], [w, textsize * 1.7], textsize * 0.5, colour * 0.19, 1);
		sui_text([x + textsize * 0.5, p_y + textsize * 0.3], [textsize, textsize], label, colour, 1, 0);
		x = x + w + textsize * 0.4;
	}
	return x - p_x;
};

// P1221: an item cell's ON / OWNED tag, a pill in its bottom-left corner (m_stats.qc draws the same).
void(vector at, float cell, float bsz, float on) Inv_Badge =
{
	local string s;
	local float bh;
	s = on ? "ON" : "OWNED";
	bh = ceil(bsz * 1.5);
	at = at + [3, cell - bh - 3];
	sui_roundbox(at, [stringwidth(s, TRUE, [bsz, bsz]) + bsz, bh], bh * 0.5, on ? SUI_THEME_GOOD_BG : SUI_THEME_CHIP, 0.92);
	sui_text(at + [bsz * 0.5, (bh - bsz) * 0.5 + bsz * FONT_CAPDROP], [bsz, bsz], s, on ? SUI_THEME_GOOD : SUI_THEME_DIM, 1, 0);
};

void(vector p, float width, float textsize, float editable, vector publickit, vector publicitems, float publicknown) Inv_Panel =
{
	local float cell, gap, i, j, x, owned, on, item, ready;
	local vector at, colour;
	local string id, label, note;
	gap = max(3, floor(textsize * 0.35));
	cell = floor((width - gap * 5) / 4);
	sui_style_panel(p, [width, cell * 4 + gap * 5 + textsize * 6], textsize * 0.75, 0.98);
	sui_text(p + [gap, gap], [textsize, textsize], "INVENTORY", SUI_THEME_TEXT, 1, 0);
	ready = Inv_Valid();
	for (i = 0; i < 16; i = i + 1)
	{
		at = p + [gap + (i % 4) * (cell + gap), textsize * 2 + gap + floor(i / 4) * (cell + gap)];
		item = i + 1;
		owned = editable ? (ready && (i == 0 ? inv_own1 : (i == 1 ? inv_own2 : 0))) : (publicknown ? (i == 0 ? publicitems_x : (i == 1 ? publicitems_y : 0)) : (i == 0 ? publickit_y : (i == 1 ? publickit_z : 0)));
		on = editable ? (i == 0 ? inv_eq1 : inv_eq2) : (i == 0 ? publickit_y : (i == 1 ? publickit_z : 0));
		id = sprintf("inv_slot%g", i);
		if (owned) sui_action_element(at, [cell, cell], id, sui_noop);
		sui_roundbox(at, [cell, cell], max(3, textsize * 0.4), (owned && on) ? SUI_THEME_SELECTED : SUI_THEME_WELL, 1);
		if (!owned) continue;
		colour = i == 0 ? '0.4 0.83 1' : Inv_Colour(editable ? inv_colour : (publicknown ? publicitems_z : publickit_z - 1));
		if (i == 0)
		{
			sui_roundbox(at + [cell * 0.28, cell * 0.18], [cell * 0.44, cell * 0.55], cell * 0.18, colour, 0.85);
			sui_roundbox(at + [cell * 0.34, cell * 0.24], [cell * 0.32, cell * 0.43], cell * 0.12, SUI_THEME_WELL, 1);
		}
		else
		{
			sui_roundbox(at + [cell * 0.18, cell * 0.46], [cell * 0.64, cell * 0.28], 0, colour * 0.85, 1);
			for (j = 0; j < 3; j = j + 1)
			{
				x = 0.28 + j * 0.22;
				R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
				R_PolygonVertex(at + [cell * (x - 0.1), cell * 0.5], '0 0 0', colour * 0.85, 1);
				R_PolygonVertex(at + [cell * x, cell * 0.18], '0 0 0', colour, 1);
				R_PolygonVertex(at + [cell * (x + 0.1), cell * 0.5], '0 0 0', colour * 0.85, 1);
				R_EndPolygon();
			}
		}
		Inv_Badge(at, cell, Font_Px(textsize * 0.8), on);
		label = i == 0 ? "Ice aura" : "Paper party crown";
		sui_tooltip_for(id, strcat(label, editable ? (on ? ": click to unequip" : ": click to equip") : (on ? ": equipped (read-only)" : ": owned (read-only)")), 2);
		if (editable && owned && sui_is_released(id) && cltime >= inv_wait)
		{
			localcmd(sprintf("cmd inventory_equip %g %g %.0f\n", item, !on, inv_revision));
			inv_wait = cltime + 1;
		}
	}
	note = editable ? (ready ? "Click an item to equip / remove" :
	       (getplayerkeyvalue(player_localnum, "*ahash") != "" ? "Waiting for lobby inventory service" : "Link Steam on a lobby to load items")) : (publicknown ? "Their owned items (read-only)" : "Inventory unavailable; equipped items only");
	sui_text(p + [gap, cell * 4 + gap * 5 + textsize * 2.1], [textsize, textsize],
	         Chat_Fit(note, width - gap * 2, textsize), SUI_THEME_MUTED, 1, 0);
};

/*
  P1230: the Ice aura is a glow in screen space. P1163's sixteen normal-pushed shells split into floating
  panels along the low-poly body's hard edges and cost sixteen skinned draws a wearer. Now each wearer
  is drawn once into a half-size mask (pixels behind the scene's depth discarded: no wallhack), the
  mask is blurred by milk_blur, and the blur is added around the visible silhouette. Engines without
  r_scenedepth (0.1.37 and older) and non-GL renderers keep the shells.
*/
#define INV_GLOWMAX 16
entity inv_glowe[INV_GLOWMAX];
float inv_glown;            // wearers queued since the last pass
float inv_glowok;           // 1 glow, -1 shells, 0 not asked yet
float inv_glowmat;          // bit 1: the main view's materials exist, bit 2: the preview's
float inv_maskd, inv_mask;  // the mask: tested against the scene's depth, and not (the preview)
float inv_hatok;            // 1 models/party_crown.png loads, -1 it does not, 0 not asked yet
float inv_gen;              // renderer generation: a restart drops targets and materials (Inv_GlowLost)
const vector INV_ICE = '0.3 0.75 1.0';
#ifndef VF_RT_COVERAGE
#define VF_RT_COVERAGE  226     // engine Patch 871; not in fteqcc's table (cl_hudcache.qc)
#endif

// Named per generation: a name drawn after a restart is a missing file for good (cl_hudcache.qc).
string(string what) Inv_N = { return sprintf("%s_%g", what, inv_gen); };
string(string k, string what) Inv_RT = { return sprintf("inv/%s%s_%g", k, what, inv_gen); };

// CSQC_RendererRestarted (cl_milk.qc).
void() Inv_GlowLost =
{
	inv_gen = inv_gen + 1;
	inv_glowmat = 0;
	inv_hatok = 0;
	inv_glowok = 0;
	inv_shader = 0;
};

void(entity body) Inv_Shells =
{
	local float i, t, u;
	if (!inv_shader)
		inv_shader = shaderforname(Inv_N("ftesurf/ice_aura"), "{\n cull back\n sort additive\n glslprogram\n{\n"
			"!!ver 110\n!!permu FRAMEBLEND\n!!permu SKELETAL\n"
			"#include \"sys/defs.h\"\n"
			"#ifdef VERTEX_SHADER\n#include \"sys/skeletal.h\"\n"
			"void main() {\n vec3 w,n,s,t;\n skeletaltransform_wnst(w,n,s,t);\n"
			" w+=normalize(n)*e_colourident.r;\n"
			" gl_Position=m_modelviewprojection*vec4(w,1.0);\n}\n#endif\n"
			"#ifdef FRAGMENT_SHADER\nvoid main() {\n"
			" gl_FragColor=vec4(0.3,0.75,1.0,e_colourident.a);\n}\n#endif\n"
			"}\n {\n map $whiteimage\n blendfunc GL_SRC_ALPHA GL_ONE\n }\n}\n");
	if (!inv_shell) { inv_shell = spawn(); inv_shell.effects = EF_NOSHADOW; }
	setmodel(inv_shell, body.model);
	setorigin(inv_shell, body.origin);
	inv_shell.angles = body.angles;
	inv_shell.frame = body.frame;
	inv_shell.frame2 = body.frame2;
	inv_shell.lerpfrac = body.lerpfrac;
	inv_shell.forceshader = inv_shader;
	inv_shell.scale = 1;
	// Integrated shell weights approximate a squared fade, not bright rings.
	// Radius travels in colour.r; the program emits a fixed ice-blue colour.
	for (i = 0; i < 16; i = i + 1)
	{
		t = i / 16;
		u = (i + 1) / 16;
		inv_shell.colormod = [u * 8, 1, 1];
		inv_shell.alpha = 0.65 * ((1 - t) * (1 - t) - (1 - u) * (1 - u));
		addentity(inv_shell);
	}
};

// The mask program; `extra` adds the depth test (the 3D view) or nothing (the preview).
string(string extra) Inv_MaskCode =
{
	return strcat("!!ver 130\n!!permu FRAMEBLEND\n!!permu SKELETAL\n", extra,
		"#include \"sys/defs.h\"\nvarying vec4 cp;\n"
		"#ifdef VERTEX_SHADER\n#include \"sys/skeletal.h\"\n"
		"void main() { gl_Position = skeletaltransform(); cp = gl_Position; }\n#endif\n"
		"#ifdef FRAGMENT_SHADER\nvoid main() {\n"
		"#ifdef DEPTH\n"
		// Distance along the view from each depth: the scene's (rt/$lastgameviewdepth, this frame's
		// main view) against this body's; nearer than the slack below is something in front of it.
		// One texel, unfiltered: screen-space depth is linear across a face, so the body meets its
		// own depth to within half a texel of slope, and nothing blends an occluder's edge. A filtered
		// sample (visual4) and the nearest of five (visual5-7, slack 1.5 x slope) both let edge-on
		// strips of a covered body through.
		// The engine draws the main view into its target the GL way up; CSQC's 3D views into a
		// target (this mask) are drawn flipped so 2D reads them upright: rows mirror (depthdbg2).
		" ivec2 dsz = textureSize(s_depth, 0);\n"
		" vec2 uv = cp.xy / cp.w * 0.5 + 0.5;\n"
		" uv.y = 1.0 - uv.y;\n"
		" float zs = texelFetch(s_depth, clamp(ivec2(uv * vec2(dsz)), ivec2(0), dsz - 1), 0).r;\n"
		" float ds = m_projection[3][2] / (zs * 2.0 - 1.0 + m_projection[2][2]);\n"
		" float df = m_projection[3][2] / (gl_FragCoord.z * 2.0 - 1.0 + m_projection[2][2]);\n"
		// fwidth outside the branch (derivatives in non-uniform flow are undefined); the slack capped
		// so an edge-on face cannot carry a wide one (review 1).
		" float slack = 1.0 + min(0.25 * fwidth(df), 6.0);\n"
		" if (zs < 0.99999 && ds < df - slack) discard;\n"
		"#endif\n"
		" gl_FragColor = vec4(1.0);\n}\n#endif\n");
};

// Per view kind k ("g" the 3D view, "p" the preview): mask -> b1 (horizontal) -> b2 (vertical) -> screen.
void(string k) Inv_GlowMats =
{
	local float bit;
	bit = (k == "g") ? 1 : 2;
	if (inv_glowmat & bit) return;
	inv_glowmat = inv_glowmat | bit;
	if (bit == 1)
		inv_maskd = shaderforname(Inv_N("ftesurf/aura_maskd"), strcat("{\n glslprogram\n{\n",
			Inv_MaskCode("!!samps depth=0\n#define DEPTH\n"),
			"}\n {\n map $rt:rt/$lastgameviewdepth\n }\n}\n"));
	else
		inv_mask = shaderforname(Inv_N("ftesurf/aura_mask"), strcat("{\n glslprogram\n{\n",
			Inv_MaskCode(""), "}\n {\n map $whiteimage\n }\n}\n"));
	shaderforname(Inv_N("ftesurf/aura_clr"),
		"{\nprogram default2d\n{\nmap $whiteimage\nblendfunc gl_zero gl_zero\nrgbgen vertex\nalphagen vertex\n}\n}\n");
	shaderforname(Inv_N(strcat("ftesurf/aura_blurh_", k)), sprintf("{\n{\nprogram milk_blur#H\nmap $rt:%s\n}\n}\n", Inv_RT(k, "mask")));
	shaderforname(Inv_N(strcat("ftesurf/aura_blurv_", k)), sprintf("{\n{\nprogram milk_blur#V\nmap $rt:%s\n}\n}\n", Inv_RT(k, "b1")));
	// A target drawn by a 3D view reads the same way up as one drawn in 2D (GL_Set2D flips 2D into targets).
	shaderforname(Inv_N(strcat("ftesurf/aura_comp_", k)), strcat("{\n glslprogram\n{\n"
		"!!ver 110\n!!samps glow=0 mask=1\n#include \"sys/defs.h\"\nvarying vec2 tc;\nvarying vec4 vc;\n"
		"#ifdef VERTEX_SHADER\nvoid main() { tc = v_texcoord; vc = v_colour; gl_Position = ftetransform(); }\n#endif\n"
		"#ifdef FRAGMENT_SHADER\nvoid main() {\n"
		" float g = texture2D(s_glow, tc).r;\n"
		" float m = texture2D(s_mask, tc).r;\n"
		" float a = clamp(g * 2.5, 0.0, 1.0) * (1.0 - m) * vc.a;\n"
		" gl_FragColor = vec4(vc.rgb * a, 1.0);\n}\n#endif\n}\n",
		// A shader-level program takes one texture per pass (one pass with two maps bound only the last).
		sprintf(" {\n map $rt:%s\n blendfunc gl_one gl_one\n rgbgen vertex\n alphagen vertex\n }\n {\n map $rt:%s\n }\n}\n",
		        Inv_RT(k, "b2"), Inv_RT(k, "mask"))));
};

// The engine's own r_scenedepth (CVAR_TYPEFLAG_ENGINE, 8), on GL. Only the type is asked: on an engine
// without it, cvar() creates a user cvar of that name, which a plain cvar_type() then reports as present
// (fallback037b: a 0.1.37 client queued glows it could not draw and lost the shells).
float() Inv_GlowCan =
{
	if (!(cvar_type("r_scenedepth") & 8))
		return FALSE;
	if (!(cvar_type("r_scenedepth_drawn") & 8))     // an engine with the first but not the second (review 2)
		return FALSE;
	return Milk_Supported();
};

// Just before the main renderscene: this frame's pass needs the scene's depth kept as a texture.
void() Inv_GlowPre =
{
	local float want;
	inv_glowok = Inv_GlowCan() ? 1 : -1;
	if (inv_glowok > 0)
	{
		want = (inv_glown > 0);
		// Against the cvar itself, not a copy: CSQC restarts at every map while the cvar lives on,
		// and the console can set it (review 1: left on after a map change, or set off under a pass).
		if (cvar("r_scenedepth") != want)
			cvar_set("r_scenedepth", want ? "1" : "0");
	}
};

/*
  Right after a renderscene that queued wearers, with that view's properties still set: main is the 3D
  view (its depth tests the mask), otherwise the profile preview (no world). Draws only inside the
  wearers' projected box; leaves the view properties as it found them. A second clearscene per frame
  also decays fading dynamic lights a second time, as the preview's own clearscene already does.
*/
#pragma warning disable F333        // VF_RT_COVERAGE is not in fteqcc's table (cl_hudcache.qc)
void(float main) Inv_GlowPass =
{
	local float n, i, j, behind, dw, dc, ds, mind, maxd, persp, fs;
	local vector vmin, vsz, vs, ps, ms, fov, org, ang, lo, hi, p, c, pad, a, s;
	local string k;
	local entity b;
	n = inv_glown;
	inv_glown = 0;
	if (n <= 0 || inv_glowok <= 0)
		return;
	// Fail closed: only on depth this frame's view wrote (an old frame's could show a wearer the
	// scene now hides: r_projection's cubemap path, a loading world, r_scenedepth just switched on).
	if (main && cvar("r_scenedepth_drawn") != 1)
		return;
	// Not under an engine target (screenshot_mega) or a demo capture: the pass ends on the screen.
	if (getproperty(VF_RT_COVERAGE) < 0 || (isdemo() && cvar("capturedemowidth") && cvar("capturedemoheight")))
		return;
	vmin = getproperty(VF_MIN);
	vsz = getproperty(VF_SIZE);
	vs = getproperty(VF_SCREENVSIZE);
	ps = getproperty(VF_SCREENPSIZE);
	if (vsz_x < 2 || vsz_y < 2 || vs_x < 1 || vs_y < 1)
		return;
	// The wearers' box on screen, padded by the blur's reach (about 16 physical pixels).
	lo = vmin + vsz;
	hi = vmin;
	behind = FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		b = inv_glowe[i];
		for (j = 0; j < 8; j = j + 1)
		{
			c = b.origin + [(j & 1) ? 26 : -26, (j & 2) ? 26 : -26, (j & 4) ? 80 : -6];
			p = project(c);
			if (p_z <= -1)
				behind = TRUE;          // behind the eye: project mirrors it, so take the whole view
			lo_x = min(lo_x, p_x);
			lo_y = min(lo_y, p_y);
			hi_x = max(hi_x, p_x);
			hi_y = max(hi_y, p_y);
		}
	}
	pad = [16 * vs_x / ps_x, 16 * vs_y / ps_y, 0];
	lo = lo - pad;
	hi = hi + pad;
	if (behind)
	{
		lo = vmin;
		hi = vmin + vsz;
	}
	lo_x = max(lo_x, vmin_x);
	lo_y = max(lo_y, vmin_y);
	hi_x = min(hi_x, vmin_x + vsz_x);
	hi_y = min(hi_y, vmin_y + vsz_y);
	if (hi_x - lo_x < 1 || hi_y - lo_y < 1)
		return;                         // none of them on screen
	k = main ? "g" : "p";
	Inv_GlowMats(k);
	ms = [max(2, floor(vsz_x * ps_x / vs_x * 0.5)), max(2, floor(vsz_y * ps_y / vs_y * 0.5)), 0];
	// The box in the view's 0..1 (a) and its size (s); the mask/blur rows are a, s scaled by ms.
	a = [(lo_x - vmin_x) / vsz_x, (lo_y - vmin_y) / vsz_y, 0];
	s = [(hi_x - lo_x) / vsz_x, (hi_y - lo_y) / vsz_y, 0];

	fov = getproperty(VF_FOV);
	org = getproperty(VF_ORIGIN);
	ang = getproperty(VF_ANGLES);
	mind = getproperty(VF_MINDIST);
	maxd = getproperty(VF_MAXDIST);
	persp = getproperty(VF_PERSPECTIVE);
	dw = getproperty(VF_DRAWWORLD);
	dc = getproperty(VF_DRAWCROSSHAIR);
	ds = getproperty(VF_DRAWENGINESBAR);

	setproperty(VF_RT_COVERAGE, 0);     // the screen's queued 2D first
	setproperty(VF_RT_DESTCOLOUR, Inv_RT(k, "mask"), 1, ms);
	drawsubpic('0 0 0', ms, Inv_N("ftesurf/aura_clr"), '0 0 0', '1 1 0', '0 0 0', 0, 0);
	setproperty(VF_RT_COVERAGE, 0);     // the clear before the 3D
	// After the 2D: a target's 2D leaves the scene clock on realtime until clearscene (P1235's
	// measurement), and the mask's poses must use the clock the bodies were drawn with.
	clearscene();
	setproperty(VF_MIN, '0 0 0');
	setproperty(VF_SIZE, ms);
	setproperty(VF_FOV, fov);
	setproperty(VF_ORIGIN, org);
	setproperty(VF_ANGLES, ang);
	setproperty(VF_MINDIST, mind);
	setproperty(VF_MAXDIST, maxd);
	setproperty(VF_PERSPECTIVE, persp);
	setproperty(VF_DRAWWORLD, 0);
	// A depth TEXTURE, like the main view's under r_scenedepth: GLBE_FBO_Update destroys and rebuilds
	// the shared game-view FBO whenever the depth kind changes, which cost 0.66 ms a frame (perf3).
	setproperty(VF_RT_DEPTH, Inv_RT(k, "depth"), 4, ms);
	for (i = 0; i < n; i = i + 1)
	{
		b = inv_glowe[i];
		fs = b.forceshader;
		b.forceshader = main ? inv_maskd : inv_mask;
		addentity(b);
		b.forceshader = fs;
	}
	renderscene();
	setproperty(VF_RT_DEPTH, "");

	// Horizontal, over the box and 8 mask rows above and below it (the vertical pass reads them).
	setproperty(VF_RT_DESTCOLOUR, Inv_RT(k, "b1"), 1, ms);
	c = [a_x * ms_x, a_y * ms_y - 8, 0];
	p = [s_x * ms_x, s_y * ms_y + 16, 0];
	drawsubpic(c, p, Inv_N(strcat("ftesurf/aura_blurh_", k)), [c_x / ms_x, c_y / ms_y, 0],
	           [p_x / ms_x, p_y / ms_y, 0], '1 1 1', 1, 0);
	setproperty(VF_RT_COVERAGE, 0);
	setproperty(VF_RT_DESTCOLOUR, Inv_RT(k, "b2"), 1, ms);
	c = [a_x * ms_x, a_y * ms_y, 0];
	p = [s_x * ms_x, s_y * ms_y, 0];
	drawsubpic(c, p, Inv_N(strcat("ftesurf/aura_blurv_", k)), a, s, '1 1 1', 1, 0);
	setproperty(VF_RT_COVERAGE, 0);

	// Restored while a target is still bound: the engine then leaves the player's stair smoothing.
	setproperty(VF_MIN, vmin);
	setproperty(VF_SIZE, vsz);
	setproperty(VF_FOV, fov);
	setproperty(VF_ORIGIN, org);
	setproperty(VF_ANGLES, ang);
	setproperty(VF_MINDIST, mind);
	setproperty(VF_MAXDIST, maxd);
	setproperty(VF_PERSPECTIVE, persp);
	setproperty(VF_DRAWWORLD, dw);
	setproperty(VF_DRAWCROSSHAIR, dc);
	setproperty(VF_DRAWENGINESBAR, ds);
	setproperty(VF_RT_DESTCOLOUR, "");
	drawsubpic(lo, hi - lo, Inv_N(strcat("ftesurf/aura_comp_", k)), a, s, INV_ICE, 1, 0);
};
#pragma warning enable F333

/*
  The paper crown: one cylinder, 32 sides, 11 around and 14 tall, wearing models/party_crown.png once
  around (512x128, its top row at the top), alpha-tested so it writes depth and sorts against itself.
  The texture is tinted by the chosen colour: paint it white/grey. Without the file, the old polygons.
*/
void(entity body, float hat, float duck) Inv_Hat =
{
	local vector base, tip, a, b, colour, sz;
	local float i, t, u;
	base = body.origin + [0, 0, duck ? 45 : 62];
	colour = Inv_Colour(hat - 1);
	if (!inv_hatok)
	{
		sz = drawgetimagesize("models/party_crown.png");
		inv_hatok = (sz_x > 0) ? 1 : -1;
		if (inv_hatok > 0)
			shaderforname(Inv_N("ftesurf/party_crown"),
				"{\n cull disable\n {\n map models/party_crown.png\n alphafunc GE128\n rgbgen vertex\n }\n}\n");
	}
	if (inv_hatok > 0)
	{
		for (i = 0; i < 32; i = i + 1)
		{
			t = (i / 32) * 6.2831853 + body.angles_y * (3.14159265 / 180);
			u = ((i + 1) / 32) * 6.2831853 + body.angles_y * (3.14159265 / 180);
			a = base + [cos(t) * 11, sin(t) * 11, 0];
			b = base + [cos(u) * 11, sin(u) * 11, 0];
			R_BeginPolygon(Inv_N("ftesurf/party_crown"), DRAWFLAG_TWOSIDED);
			R_PolygonVertex(a, [i / 32, 1, 0], colour * (0.8 + 0.2 * cos(t)), 1);
			R_PolygonVertex(b, [(i + 1) / 32, 1, 0], colour * (0.8 + 0.2 * cos(u)), 1);
			R_PolygonVertex(b + '0 0 14', [(i + 1) / 32, 0, 0], colour * (0.8 + 0.2 * cos(u)), 1);
			R_PolygonVertex(a + '0 0 14', [i / 32, 0, 0], colour * (0.8 + 0.2 * cos(t)), 1);
			R_EndPolygon();
		}
		return;
	}
	for (i = 0; i < 16; i = i + 1)
	{
		t = (i / 16) * 6.2831853 + body.angles_y * (3.14159265 / 180);
		u = ((i + 1) / 16) * 6.2831853 + body.angles_y * (3.14159265 / 180);
		a = base + [cos(t) * 11, sin(t) * 11, 0];
		b = base + [cos(u) * 11, sin(u) * 11, 0];
		R_BeginPolygon("", DRAWFLAG_TWOSIDED);
		R_PolygonVertex(a, '0 0 0', colour * (0.8 + 0.2 * cos(t)), 1);
		R_PolygonVertex(b, '0 0 0', colour * (0.8 + 0.2 * cos(u)), 1);
		R_PolygonVertex(b + '0 0 6', '0 0 0', colour * (0.8 + 0.2 * cos(u)), 1);
		R_PolygonVertex(a + '0 0 6', '0 0 0', colour * (0.8 + 0.2 * cos(t)), 1);
		R_EndPolygon();
		if (i % 2) continue;
		// Eight paper points around an open cylindrical band, not one cone tip.
		a = a + '0 0 6';
		b = base + [cos(t + 0.78539816) * 11, sin(t + 0.78539816) * 11, 6];
		tip = base + [cos(u) * 11, sin(u) * 11, 14];
		R_BeginPolygon("", DRAWFLAG_TWOSIDED);
		R_PolygonVertex(a, '0 0 0', colour * (0.8 + 0.2 * cos(t)), 1);
		R_PolygonVertex(b, '0 0 0', colour * (0.8 + 0.2 * cos(t + 0.78539816)), 1);
		R_PolygonVertex(tip, '0 0 0', colour, 1);
		R_EndPolygon();
	}
};

// The preview queues its own wearer; nothing the 3D view left behind belongs in its pass.
void() Inv_GlowReset = { inv_glown = 0; };

void(entity body, float outline, float hat, float duck) Inv_Draw =
{
	if (outline)
	{
		if (!inv_glowok)
			inv_glowok = Inv_GlowCan() ? 1 : -1;
		if (inv_glowok > 0)
		{
			if (inv_glown < INV_GLOWMAX)
			{
				inv_glowe[inv_glown] = body;
				inv_glown = inv_glown + 1;
			}
			else
				Inv_Shells(body);       // past the queue: the old look rather than none
		}
		else
			Inv_Shells(body);
	}
	if (hat >= 1 && hat <= 12)
		Inv_Hat(body, hat, duck);
};
