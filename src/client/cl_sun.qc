/*
===========================================================================
  cl_sun.qc -- env_sun (Patch 874).  247 maps carry one.

  Source's C_Sun is two directional glow overlays drawn 100 units in front of
  the eye along the sun's direction (glow_overlay.cpp CalcBasis):
    core   size `size`, colour rendercolor scaled so its brightest channel is 1
           (c_sun.cpp:60-76), full strength while the sky is visible;
    glow   size `overlaysize` (-1 = size) x6, colour overlaycolor (or the core's
           when 0 0 0), alpha 0.75 looking straight at the sun falling to 0 at a
           dot of 0.9 (c_sun.h C_SunGlowOverlay).
  Visibility is UpdateGlowObstruction's trace (CONTENTS_SOLID): a ray along the
  direction that hits anything but a sky side hides it, faded over
  cl_sun_decay_rate's 0.05 s.  Drawn without depth, as light_glow02_add_noz is.
  Direction: use_angles takes angles with the pitch key's override
  (SetupLightNormalFromProps), else the sun's origin minus its target's (the
  first, any case); no target, or one that is not there, keeps CSun's (0,0,1).
  vbsp_sun 0 hides it (gfx menu).
===========================================================================
*/
float  sun_have;
vector sun_dir;
vector sun_col, sun_ocol;
float  sun_size, sun_osize;
string sun_mat, sun_omat;
float  sun_vis;                 // 0..1, the obstruction fade
entity sun_probe;               // the trace's mask: CONTENTBIT_SOLID, so glass shows the sun
float  sun_seen;                // the last visibility printed: -1 none yet

string(string m) Sun_Shader =
{
	m = strtolower(m);
	if (substring(m, strlen(m) - 4, 4) == ".vmt")
		m = substring(m, 0, strlen(m) - 4);
	if (m == "")
		m = "sprites/light_glow02_add_noz";
	return m;
};

void() Sun_LoadForMap =
{
	local string tok, key, cn, tname, target, mat, omat;
	local vector org, ang, rgb, orgb, torg;
	local float  size, osize, useang, pitch, yaw, found, maxc;
	local vector h;
	local string want;

	sun_have = FALSE;
	sun_vis = 0;
	sun_seen = -1;
	if (sun_mat != "") strunzone(sun_mat);
	if (sun_omat != "") strunzone(sun_omat);
	sun_mat = sun_omat = "";
	found = FALSE;
	want = "";

	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = tname = target = mat = omat = "";
		org = ang = rgb = orgb = '0 0 0';
		size = 16;
		osize = -1;
		useang = 0;
		pitch = yaw = 0;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")       cn = tok;
			else if (key == "targetname")      tname = tok;
			else if (key == "target")          target = tok;
			else if (key == "origin")          org = stov(tok);
			else if (key == "angles")          ang = stov(tok);
			else if (key == "rendercolor")     rgb = stov(tok);
			else if (key == "overlaycolor")    orgb = stov(tok);
			else if (key == "size")            size = stof(tok);
			else if (key == "overlaysize")     osize = stof(tok);
			else if (key == "material")        mat = tok;
			else if (key == "overlaymaterial") omat = tok;
			else if (key == "use_angles")      useang = stof(tok);
			else if (key == "pitch")           pitch = stof(tok);
			else if (key == "angle")           yaw = stof(tok);
		}
		if (cn != "env_sun" || found)
			continue;
		found = TRUE;
		if (useang)
		{
			// SetupLightNormalFromProps (map_utils.cpp): z is +sin(pitch), not makevectors'
			// -sin; angle -1/-2 (up/down) zero the horizontal.  The sun is the light's reverse.
			if (yaw == -1 || yaw == -2)
				h = '0 0 0';
			else
			{
				if (!yaw)
					yaw = ang_y;
				h = [cos(yaw * M_PI / 180), sin(yaw * M_PI / 180), 0];
			}
			if (!pitch)
				pitch = ang_x;
			sun_dir = -[h_x * cos(pitch * M_PI / 180), h_y * cos(pitch * M_PI / 180), sin(pitch * M_PI / 180)];
		}
		else if (target != "")
		{
			want = strzone(strtolower(target));
			sun_dir = org;       // resolved against the target below
		}
		else
			sun_dir = '0 0 1';   // CSun's default: an empty name finds nothing
		maxc = max(rgb_x, max(rgb_y, rgb_z));
		sun_col = (maxc > 0) ? rgb * (1 / maxc) : '1 1 1';
		sun_ocol = (orgb != '0 0 0') ? orgb * (1 / 255) : sun_col;
		sun_size = size;
		sun_osize = (osize == -1) ? size : osize;
		sun_mat = strzone(Sun_Shader(mat));
		sun_omat = strzone(Sun_Shader(omat));
	}
	if (!found)
		return;
	if (want != "")
	{
		// A second walk for the target: it may come before or after the sun.
		found = FALSE;
		torg = '0 0 0';
		getentitytoken(0);
		while (!found && (tok = getentitytoken()) != "")
		{
			if (tok != "{")
				continue;
			tname = "";
			org = '0 0 0';
			while ((key = getentitytoken()) != "" && key != "}")
			{
				tok = getentitytoken();
				key = strtolower(key);
				if (key == "targetname") tname = tok;
				else if (key == "origin") org = stov(tok);
			}
			if (strtolower(tname) == want)
			{
				torg = org;
				found = TRUE;
			}
		}
		strunzone(want);
		sun_dir = found ? sun_dir - torg : '0 0 1';
		if (sun_dir == '0 0 0')
			sun_dir = '0 0 1';
	}
	sun_dir = normalize(sun_dir);
	sun_have = TRUE;
	dprint(sprintf("env_sun: dir %v size %g/%g %s\n", sun_dir, sun_size, sun_osize, sun_mat));
};

void(string mat, vector eye, float hs, vector col, float a) Sun_Quad =
{
	local vector base, rt, up;

	if (a <= 0)
		return;
	base = eye + sun_dir * 100;
	rt = normalize(crossproduct(sun_dir, '0 0 1'));
	if (rt == '0 0 0')
		rt = '1 0 0';
	up = normalize(crossproduct(rt, sun_dir));
	rt = rt * hs;
	up = up * hs;
	R_BeginPolygon(mat, DRAWFLAG_ADD | DRAWFLAG_NODEPTHTEST);
	R_PolygonVertex(base - rt + up, '0 0 0', col, a);
	R_PolygonVertex(base + rt + up, '1 0 0', col, a);
	R_PolygonVertex(base + rt - up, '1 1 0', col, a);
	R_PolygonVertex(base - rt - up, '0 1 0', col, a);
	R_EndPolygon();
};

void() Sun_Draw =
{
	local vector eye, fwd;
	local float dot, ga, target;

	if (!sun_have || !cvar("vbsp_sun"))
		return;
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	dot = fwd * sun_dir;
	if (dot <= 0)
	{
		sun_vis = 0;
		return;                 // behind the view: nothing of it is on screen
	}
	if (!sun_probe)
	{
		sun_probe = spawn();
		sun_probe.hitcontentsmaski = CONTENTBIT_SOLID;
	}
	traceline(eye, eye + sun_dir * 32768, MOVE_NOMONSTERS, sun_probe);
	// SURF_SKY does not come through a VBSP trace; the side's name does (cl_emit.qc's rain).
	target = (trace_fraction >= 1 || substring(strtolower(trace_surfacename), 0, 4) == "sky/") ? 1 : 0;
	if (target != sun_seen)
	{
		sun_seen = target;
		dprint(sprintf("env_sun: %s\n", target ? "visible" : strcat("hidden by ", trace_surfacename)));
	}
	sun_vis = target ? min(1, sun_vis + frametime / 0.05) : max(0, sun_vis - frametime / 0.05);
	if (sun_vis <= 0)
		return;
	Sun_Quad(sun_mat, eye, sun_size, sun_col, sun_vis);
	ga = bound(0, (dot - 0.9) / 0.1 * 0.75, 0.75);
	Sun_Quad(sun_omat, eye, sun_osize * 6, sun_ocol, ga * sun_vis);
};
