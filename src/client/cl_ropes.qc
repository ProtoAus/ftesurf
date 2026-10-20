/*
===========================================================================
  cl_ropes.qc -- move_rope / keyframe_rope (Patch 874).  135 maps.

  A rope runs from a move_rope through the keyframe_ropes its NextKey chain
  names.  Source simulates each span (c_rope.cpp); a static rope at rest is the
  curve that simulation settles to, so each span is drawn once-computed: a
  parabola through both ends whose arc length is the straight distance plus
  Slack (sag h from L ~ D + 8h^2 / 3D).  Wind, collision, breaking, dangling and
  parented (moving) ropes are not simulated.  One camera-facing strip per
  segment (one per 48 units, 4 to 16) with the span's RopeMaterial, Width
  wide, lit once at load from the lightgrid; spans past vbsp_ropes_dist are
  skipped.  vbsp_ropes 0 hides them (gfx menu).  Each span is a CSQC entity,
  so no global arrays.
===========================================================================
*/
.vector rope_p0, rope_p1;
.float  rope_sag, rope_w, rope_n, rope_tex;     // rope_tex: V per segment
.string rope_mat;
.vector rope_col;

float  ropes_n;
string ropes_map;

string(string m) Rope_Shader =
{
	m = strtolower(m);
	if (substring(m, strlen(m) - 4, 4) == ".vmt")
		m = substring(m, 0, strlen(m) - 4);
	if (m == "")
		m = "cable/cable";
	return m;
};

void() Ropes_LoadForMap =
{
	local string tok, key, cn, tname, next, mat;
	local vector org;
	local float slack, width, tscale, i, j, n, d, th;
	local strbuf names, recs;
	local entity e;
	local string rec;

	ropes_map = serverkey("map");
	for (e = find(world, classname, "rope_span"); e; e = find(world, classname, "rope_span"))
		remove(e);
	ropes_n = 0;

	// One record per rope point: "nextkey\torigin\tslack\twidth\tmaterial\ttexscale"
	names = buf_create();
	recs = buf_create();
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = tname = next = mat = "";
		org = '0 0 0';
		slack = 25;
		width = 2;
		tscale = 1;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")    cn = tok;
			else if (key == "targetname")   tname = tok;
			else if (key == "nextkey")      next = tok;
			else if (key == "origin")       org = stov(tok);
			else if (key == "slack")        slack = stof(tok);
			else if (key == "width")        width = stof(tok);
			else if (key == "ropematerial") mat = tok;
			else if (key == "texturescale") tscale = stof(tok);
		}
		if (cn != "move_rope" && cn != "keyframe_rope")
			continue;
		bufstr_add(names, strtolower(tname), TRUE);
		bufstr_add(recs, sprintf("%s\t%v\t%g\t%g\t%s\t%g", strtolower(next), org, slack, width,
		                         Rope_Shader(mat), tscale), TRUE);
	}

	// A span from every point that names a NextKey to the point carrying that name.
	n = buf_getsize(recs);
	for (i = 0; i < n; i = i + 1)
	{
		rec = bufstr_get(recs, i);
		tokenizebyseparator(rec, "\t");
		next = argv(0);
		if (next == "")
			continue;
		for (j = 0; j < n; j = j + 1)
			if (bufstr_get(names, j) == next)
				break;
		if (j >= n)
			continue;
		e = spawn();
		e.classname = "rope_span";
		e.rope_p0 = stov(argv(1));
		slack = stof(argv(2));
		e.rope_w = max(0.5, stof(argv(3)));
		e.rope_mat = strzone(argv(4));
		tscale = max(0.01, stof(argv(5)));
		tokenizebyseparator(bufstr_get(recs, j), "\t");
		e.rope_p1 = stov(argv(1));
		d = vlen(e.rope_p1 - e.rope_p0);
		// Source splines its nodes; straight pieces this long read as kinks (Subdiv+2 did).
		e.rope_n = bound(4, ceil((d + slack) / 48), 16);
		// c_rope.cpp:1756-1759: 4/TextureScale pixels a unit of rope, over the texture's height.
		th = drawgetimagesize(e.rope_mat) * '0 1 0';
		if (th <= 0)
			th = 64;
		e.rope_tex = (d + slack) / e.rope_n * 4 / (tscale * th);
		e.rope_sag = (d > 1 && slack > 0) ? sqrt(3 * d * slack / 8) : 0;
		e.rope_col = getlight((e.rope_p0 + e.rope_p1) * 0.5 - '0 0 1' * e.rope_sag * 0.5) * (1 / 255);
		if (e.rope_col == '0 0 0')
			e.rope_col = '0.5 0.5 0.5';
		e.rope_col_x = min(1, e.rope_col_x);
		e.rope_col_y = min(1, e.rope_col_y);
		e.rope_col_z = min(1, e.rope_col_z);
		ropes_n = ropes_n + 1;
	}
	buf_del(names);
	buf_del(recs);
	if (ropes_n)
		dprint(sprintf("ropes: %g span(s)\n", ropes_n));
};

vector(entity e, float t) Rope_Point =
{
	return e.rope_p0 + (e.rope_p1 - e.rope_p0) * t - '0 0 4' * (e.rope_sag * t * (1 - t));
};

void() Ropes_Draw =
{
	local entity e;
	local vector eye, fwd, a, b, sa, sb;
	local float k, n, maxd, v0, v1;

	if (serverkey("map") != ropes_map)
		Ropes_LoadForMap();
	if (!ropes_n || !cvar("vbsp_ropes"))
		return;
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	maxd = cvar("vbsp_ropes_dist");
	for (e = find(world, classname, "rope_span"); e; e = find(e, classname, "rope_span"))
	{
		a = (e.rope_p0 + e.rope_p1) * 0.5;
		if (maxd > 0 && vlen(a - eye) > maxd + vlen(e.rope_p1 - e.rope_p0) * 0.5)
			continue;
		// Behind the camera, both ends and the middle.
		if ((e.rope_p0 - eye) * fwd < 0 && (e.rope_p1 - eye) * fwd < 0 && (a - eye) * fwd < 0)
			continue;
		n = e.rope_n;
		v0 = 0;
		b = e.rope_p0;
		for (k = 1; k <= n; k = k + 1)
		{
			a = b;
			b = Rope_Point(e, k / n);
			v1 = v0 + e.rope_tex;
			sa = normalize(crossproduct(b - a, eye - a)) * (e.rope_w * 0.5);
			sb = normalize(crossproduct(b - a, eye - b)) * (e.rope_w * 0.5);
			R_BeginPolygon(e.rope_mat, 0);
			R_PolygonVertex(a - sa, [0, v0, 0], e.rope_col, 1);
			R_PolygonVertex(a + sa, [1, v0, 0], e.rope_col, 1);
			R_PolygonVertex(b + sb, [1, v1, 0], e.rope_col, 1);
			R_PolygonVertex(b - sb, [0, v1, 0], e.rope_col, 1);
			R_EndPolygon();
			v0 = v1;
		}
	}
};

void() Ropes_RegisterCvars =
{
	registercvar("vbsp_sun", "1");
	registercvar("vbsp_ropes", "1");
	registercvar("vbsp_ropes_dist", "4096");
};
