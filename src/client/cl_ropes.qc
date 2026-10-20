/*
===========================================================================
  cl_ropes.qc -- move_rope / keyframe_rope (Patch 874).  181 maps.

  A rope runs from a move_rope through the keyframe_ropes its NextKey chain
  names.  Source simulates each span (c_rope.cpp); a static rope at rest is the
  curve that simulation settles to, so each span is drawn once-computed: a
  parabola through both ends whose arc length is the straight distance plus
  Slack (sag h from L ~ D + 8h^2 / 3D).  Wind, collision, breaking, dangling and
  parented (moving) ropes are not simulated.  One camera-facing strip per
  segment (one per 48 units, 4 to 16) with the span's RopeMaterial, Width
  wide, lit once at load from the lightgrid; spans past vbsp_ropes_dist or
  behind the eye are skipped.  vbsp_ropes 0 hides them (gfx menu).

  A frame builds one side vector per point and one polygon begin per span.
  bhop_canals (235 spans, the library's most) measured +0.24-0.49 ms of CSQC at
  its densest heading with two per segment.  A point array would cost 3 globals
  a vector, and csprogs is near fteqcc's 131072.
===========================================================================
*/
.vector rope_p0, rope_dp, rope_mid;
.float  rope_sag, rope_rad, rope_w, rope_n, rope_tex;   // rope_tex: V per segment
.string rope_mat;
.vector rope_col;
.entity rope_next;

float  ropes_n;
entity ropes_head;

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
	local vector org, p0, p1;
	local float slack, width, tscale, i, j, n, d, th, k, sag;
	local strbuf names, recs;
	local entity e;
	local string rec;

	while (ropes_head)
	{
		e = ropes_head;
		ropes_head = e.rope_next;
		strunzone(e.rope_mat);
		remove(e);
	}
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
		p0 = stov(argv(1));
		slack = stof(argv(2));
		width = max(0.5, stof(argv(3)));
		mat = argv(4);
		tscale = max(0.01, stof(argv(5)));
		tokenizebyseparator(bufstr_get(recs, j), "\t");
		p1 = stov(argv(1));
		d = vlen(p1 - p0);
		// Source splines its nodes; straight pieces this long read as kinks (Subdiv+2 did).
		k = bound(4, ceil((d + slack) / 48), 16);
		sag = (d > 1 && slack > 0) ? sqrt(3 * d * slack / 8) : 0;

		e = spawn();
		e.rope_w = width;
		e.rope_n = k;
		e.rope_mat = strzone(mat);
		e.rope_p0 = p0;
		e.rope_dp = p1 - p0;
		e.rope_sag = sag;
		e.rope_mid = (p0 + p1) * 0.5 - '0 0 1' * sag * 0.5;
		e.rope_rad = d * 0.5 + sag;
		// c_rope.cpp:1756-1759: 4/TextureScale pixels a unit of rope, over the texture's height.
		th = drawgetimagesize(e.rope_mat) * '0 1 0';
		if (th <= 0)
			th = 64;
		e.rope_tex = (d + slack) / k * 4 / (tscale * th);
		e.rope_col = getlight(e.rope_mid) * (1 / 255);
		if (e.rope_col == '0 0 0')
			e.rope_col = '0.5 0.5 0.5';
		e.rope_col_x = min(1, e.rope_col_x);
		e.rope_col_y = min(1, e.rope_col_y);
		e.rope_col_z = min(1, e.rope_col_z);
		e.rope_next = ropes_head;
		ropes_head = e;
		ropes_n = ropes_n + 1;
	}
	buf_del(names);
	buf_del(recs);
	if (ropes_n)
		dprint(sprintf("ropes: %g span(s)\n", ropes_n));
};

void() Ropes_Draw =
{
	local entity e;
	local vector eye, fwd, d, a, b, sa, sb, t;
	local float k, n, f, maxd, v0, hw, sag;
	local vector p0, dp;

	if (!ropes_n || !cvar("vbsp_ropes"))
		return;
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	maxd = cvar("vbsp_ropes_dist");
	for (e = ropes_head; e; e = e.rope_next)
	{
		d = e.rope_mid - eye;
		if (d * fwd < -e.rope_rad)
			continue;               // wholly behind the eye
		if (maxd > 0 && vlen(d) > maxd + e.rope_rad)
			continue;
		n = e.rope_n;
		p0 = e.rope_p0;
		dp = e.rope_dp;
		sag = e.rope_sag * 4;
		hw = e.rope_w * 0.5;
		// One side vector per point, shared by the two segments that meet there;
		// the tangent at a point is the parabola's derivative.
		b = p0;
		t = dp - '0 0 1' * sag;
		sb = normalize(crossproduct(t, eye - b)) * hw;
		v0 = 0;
		R_BeginPolygon(e.rope_mat, 0);
		for (k = 1; k <= n; k = k + 1)
		{
			a = b;
			sa = sb;
			f = k / n;
			b = p0 + dp * f - '0 0 1' * (sag * f * (1 - f));
			t = dp - '0 0 1' * (sag * (1 - 2 * f));
			sb = normalize(crossproduct(t, eye - b)) * hw;
			R_PolygonVertex(a - sa, [0, v0, 0], e.rope_col, 1);
			R_PolygonVertex(a + sa, [1, v0, 0], e.rope_col, 1);
			R_PolygonVertex(b + sb, [1, v0 + e.rope_tex, 0], e.rope_col, 1);
			R_PolygonVertex(b - sb, [0, v0 + e.rope_tex, 0], e.rope_col, 1);
			R_EndPolygon();
			v0 = v0 + e.rope_tex;
		}
	}
};

void() Ropes_RegisterCvars =
{
	registercvar("vbsp_sun", "1");
	registercvar("vbsp_ropes", "1");
	registercvar("vbsp_ropes_dist", "4096");
};
