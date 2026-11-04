// FTESurf P1278: ramp wear. tools/rampwear.py bakes, per map, the ridden ramps' triangles
// (gfx/rampwear/<map>.txt) and their mask (gfx/rampwear/<map>.png; P1293: gfx/ is a path every launcher
// updates) from replays; this draws
// them as polygons with glsl/ftesurf_rampwear.glsl and a multiply blend, so the ramp's own lighting
// carries it. Polygons, not a model entity: one map-sized OBJ entity was never drawn (P1278 notes).
// The normal rides in the vertex colour. r_rampwear 0 hides it; r_rampwear_dirt / r_rampwear_scratch
// scale the looks; r_rampwear_debug 1 shows the mask.

string rw_map;                  // the map the overlay was looked up for
string rw_shader;               // its shader name, "" when the map has none
float  rw_n;                    // surfaces
float  rw_ntri;
vector *rw_cen;                 // per surface: centre, radius, first triangle, triangles
float  *rw_rad;
float  *rw_first;
float  *rw_cnt;
vector *rw_pos;                 // per triangle corner
vector *rw_st;
vector *rw_nrm;                 // per triangle

void() RampWear_Init =
{
	registercvar("r_rampwear", "1", 0);
	registercvar("r_rampwear_dirt", "1", 0);
	registercvar("r_rampwear_scratch", "1.5", 0);
	registercvar("r_rampwear_distance", "12000", CVAR_ARCHIVE);
	registercvar("r_rampwear_shine", "0.15", CVAR_ARCHIVE);
	registercvar("r_rampwear_debug", "0", 0);     // 1: show the mask itself
};

float  rw_alloc;                // the arrays above hold memory, and rw_shader is zoned

void() RampWear_Free =
{
	if (rw_alloc)
	{
		memfree(rw_cen);
		memfree(rw_rad);
		memfree(rw_first);
		memfree(rw_cnt);
		memfree(rw_pos);
		memfree(rw_st);
		memfree(rw_nrm);
		strunzone(rw_shader);
	}
	rw_alloc = FALSE;
	rw_n = rw_ntri = 0;
	rw_shader = "";
};

void() RampWear_Load =
{
	local string mname, line;
	local float fh, ns, nt, s, t, k, j, skip, modern;

	RampWear_Free();
	if (rw_map)
		strunzone(rw_map);
	mname = serverkey("map");
	rw_map = strzone(mname);
	if (mname == "")
		return;
	fh = fopen(sprintf("gfx/rampwear/%s.txt", mname), FILE_READ);
	if (fh < 0)
		return;
	line = fgets(fh);
	if (tokenize(line) != 5 || argv(0) != "rampwear" || argv(1) != "1")
	{
		print(sprintf("^3rampwear: gfx/rampwear/%s.txt: not a version 1 file\n", mname));
		fclose(fh);
		return;
	}
	ns = stof(argv(3));
	nt = stof(argv(4));
	if (ns <= 0 || nt <= 0)
	{
		fclose(fh);
		return;
	}
	rw_cen   = memalloc(sizeof(vector) * ns);
	rw_rad   = memalloc(sizeof(float) * ns);
	rw_first = memalloc(sizeof(float) * ns);
	rw_cnt   = memalloc(sizeof(float) * ns);
	rw_pos   = memalloc(sizeof(vector) * nt * 3);
	rw_st    = memalloc(sizeof(vector) * nt * 3);
	rw_nrm   = memalloc(sizeof(vector) * nt);
	s = t = 0;
	skip = TRUE;            // triangles before any surface line, or after a bad one, belong to nothing
	while ((line = fgets(fh)))
	{
		k = tokenize(line);
		if (argv(0) == "c")
		{
			skip = (k != 6 || s >= ns);
			if (skip)
				continue;
			rw_cen[s] = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
			rw_rad[s] = stof(argv(4));
			rw_first[s] = t;
			rw_cnt[s] = 0;
			s = s + 1;
		}
		else if (argv(0) == "t" && k == 19 && !skip && t < nt)
		{
			for (j = 0; j < 3; j = j + 1)
			{
				rw_pos[t * 3 + j] = [stof(argv(1 + j * 5)), stof(argv(2 + j * 5)), stof(argv(3 + j * 5))];
				rw_st[t * 3 + j]  = [stof(argv(4 + j * 5)), stof(argv(5 + j * 5)), 0];
			}
			rw_nrm[t] = [stof(argv(16)), stof(argv(17)), stof(argv(18))];
			rw_cnt[s - 1] = rw_cnt[s - 1] + 1;
			t = t + 1;
		}
	}
	fclose(fh);
	rw_n = s;
	rw_ntri = t;
	// P1307: code/assets and cached materials can update independently. The v2
	// half-output shader MUST pair with double modulation, never legacy filter.
	// Probe once at map load; clients without the new file retain the old look.
	fh = fopen("glsl/ftesurf_rampwear_v2.glsl", FILE_READ);
	modern = (fh >= 0);
	if (modern) fclose(fh);
	rw_shader = strzone(sprintf("ftesurf_rampwear_%s/%s", modern ? "v2" : "legacy", mname));
	rw_alloc = TRUE;
	// exactvertex: vertex colour encodes a normal, not HDR-scaled brightness.
	// $nosrgb: mask data; no cross-chart mips or grazing-angle slope bias.
	shaderforname(rw_shader, sprintf("{\ndepthpush -2\nnomipmaps\nnopicmip\nsort decal\n{\nprogram %s\nblendfunc %s\nclampmap $nosrgb:gfx/rampwear/%s.png\nrgbgen exactvertex\nalphagen vertex\n}\n}\n",
	              modern ? "ftesurf_rampwear_v2" : "ftesurf_rampwear",
	              modern ? "gl_dst_color gl_src_color" : "gl_dst_color gl_zero", mname));
	print(sprintf("rampwear: %s, %g surfaces, %g triangles\n", mname, rw_n, rw_ntri));
	print(sprintf("rampwear: shader %s\n", modern ? "v2" : "legacy (new asset not installed)"));
};

// Before renderscene, beside Emit_Frame: the map latch, then the surfaces in front within reach.
void() RampWear_Frame =
{
	local float i, t, e, j, reach;
	local vector eye, fwd, d, col;

	if (serverkey("map") != rw_map)
		RampWear_Load();
	if (!rw_n || !cvar("r_rampwear"))
		return;
	eye = getproperty(VF_ORIGIN);
	reach = bound(1024, cvar("r_rampwear_distance"), 24000);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	// One begin a frame: R_EndPolygon keeps the shader for the next polygon (pr_csqc.c
	// PF_R_PolygonEnd), and each begin is a shader lookup that counts a use.
	R_BeginPolygon(rw_shader, 0, FALSE);
	for (i = 0; i < rw_n; i = i + 1)
	{
		d = rw_cen[i] - eye;
		if (vlen(d) - rw_rad[i] > reach || d * fwd < -rw_rad[i])
			continue;
		e = rw_first[i] + rw_cnt[i];
		for (t = rw_first[i]; t < e; t = t + 1)
		{
			col = rw_nrm[t] * 0.5 + '0.5 0.5 0.5';
			for (j = 0; j < 3; j = j + 1)
				R_PolygonVertex(rw_pos[t * 3 + j], rw_st[t * 3 + j], col, 1);
			R_EndPolygon();
		}
	}
};
