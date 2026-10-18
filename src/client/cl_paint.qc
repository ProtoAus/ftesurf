/*
===========================================================================
  cl_paint.qc -- Patch 772: `paint`, a coloured disc sprayed where you aim.

  Client side only: the disc is placed in the frame the key is down and
  nobody else sees it.  It is an adddecal_static (cl_decals.qc), so the
  engine clips it ONCE against the faces it touches (Mod_ClipDecal,
  q1bsp.c) and copies the cached triangles every frame.  Like a Source
  decal it lies flat on each face and stops at the face's edge; a face
  turned more than ~84 degrees from the hit face is left bare
  (r_decal_noperpendicular, Fragment_ClipPoly), so a ramp's ridge cuts it.

  The aim stops where a player would: solid and player clip.  On 116 of
  1,131 surf maps a quarter or more of the ramp area is a func_brush or
  func_illusionary over clip, and on 35 a displacement; an engine with
  FTESURF_DECAL_SOURCE clips to those too (srange_z 1), an older one to the
  world's faces only, and a hit on a brush entity paints nothing there.

      +paint / -paint     hold to spray, paint_rate discs a second
      paint               one disc; a key bound to it also sprays while held
      paint_clear         remove it all, yours and what others sent
      paint_save / paint_load [name]   this map's layout, data/paint/<map>[_name].txt
                          (Patch 777); paint_autoload 1 loads the unnamed one with the map
      paint_fill <n> [deg]  n discs in a cone, for the stress arm
      paint_status        counts, the last hit and the cvars

  Patch 777: every disc keeps what it was placed with (pt_dat), so it can be
  saved and sent; other players' discs arrive through cl_share.qc.  A disc
  whose face is not here yet -- a brush entity out of view is not in the
  packet the clip reads -- waits in pt_pend and is tried again near you.
===========================================================================
*/

void(float handle) removedecal = #0:removedecal;

#define PAINT_SHADER "ftesurf/paint"
#define PAINT_RANGE  32768
#define PAINT_CAP    60000      // the engine's store holds 0xFFFE, shared with the map's decals
#define PAINT_GAP    0.3        // of the size: a held key over one spot adds nothing
#define PAINT_BEHIND 32         // how far past an unpaintable collision hit a visible face may be

#define PD_N        12          // a disc: origin, normal, rgb 0..1, size, alpha, from (0 you, slot + 1)
#define PAINT_PEND  8192        // discs waiting for their face
#define PAINT_LOADF 400         // layout lines read a frame

float *pt_ring;                 // handles, oldest at pt_tail
float *pt_dat;                  // PD_N a ring cell
float *pt_pend;                 // PD_N a waiting disc
float pt_pn, pt_pnext, pt_pcur; // waiting; cltime of the next retry; its round-robin cursor
var filestream pt_ldf = -1;     // a layout being read, PAINT_LOADF lines a frame
string pt_ldpath;
float pt_ldn, pt_ldwait;
float pt_autoat;                // cltime this map's layout loads (0 none)
float pt_layn;                  // discs in this map's saved layout: -1 none, -2 not counted
float pt_rx;                    // discs other players sent
void(vector o, vector n, vector col, float size, float alpha) Share_OnPaint;
float pt_tail, pt_n;
float pt_plus, pt_once;         // +paint is down; a disc is asked for this frame
float pt_next;                  // cltime a still aim sprays again
float pt_downkey;               // a key bound to `paint` went down; its bind runs after
float pt_key, pt_key2;          // keys bound to `paint` holding the spray, each until its release
vector pt_lastcol, pt_lastorg;
float pt_filln, pt_filldeg;      // a paint_fill waiting for Paint_Frame's camera
float pt_placed, pt_nohit, pt_nonworld, pt_nogeom, pt_skipped;
vector pt_last, pt_lastn;
vector pt_missorg;              // the last miss: from where, and was it inside a solid
float pt_misssolid;
vector pt_noface, pt_nofacen;   // the last hit no face took, and its normal
float pt_lasth;
float pt_made;                  // the shader is registered for this renderer
entity pt_probe;                // the aim's trace mask: what a player collides with
float pt_source;                // the engine clips to brush entities and displacements

void() Paint_Shader =
{
	if (Milk_Supported())
		shaderforname(PAINT_SHADER,
			"{\nglslprogram\n{\n"
			"!!ver 110\n"
			"varying vec2 tc;\n"
			"varying vec4 vc;\n"
			"#ifdef VERTEX_SHADER\n"
			"attribute vec2 v_texcoord;\n"
			"attribute vec4 v_colour;\n"
			"uniform vec3 e_eyepos;\n"      // sys/defs.h declares it; this program does not include that
			"void main()\n{\n"
			" tc = v_texcoord;\n"
			" vc = v_colour;\n"
			// Patch 773: 0.125u toward the eye along its own ray (same pixel). polygonoffset
			// alone is depth-buffer steps, a few thousandths of a unit at arm's length.
			" vec3 d = e_eyepos - v_position;\n"
			" float l = max(length(d), 0.001);\n"
			" gl_Position = m_modelviewprojection * vec4(v_position + d * (min(0.125, l * 0.25) / l), 1.0);\n"
			"}\n#endif\n"
			"#ifdef FRAGMENT_SHADER\n"
			"void main()\n{\n"
			// The footprint is 0..1 square; a one-pixel rim at radius 1.
			" float r = length(tc - vec2(0.5)) * 2.0;\n"
			" float a = clamp((1.0 - r) / max(fwidth(r), 0.000001), 0.0, 1.0);\n"
			" if (a <= 0.0) discard;\n"
			" gl_FragColor = vec4(vc.rgb, vc.a * a);\n"
			"}\n#endif\n"
			"}\n"
			"polygonoffset\nsort decal\n"
			"{\nmap $whiteimage\nblendfunc blend\nrgbgen vertex\nalphagen vertex\n}\n"
			"surfaceparm noshadows\nsurfaceparm nodlight\n}\n");
	else    // no GLSL from us: a square, but still clipped to the faces
		shaderforname(PAINT_SHADER,
			"{\npolygonoffset\nsort decal\n"
			"{\nmap $whiteimage\nblendfunc blend\nrgbgen vertex\nalphagen vertex\n}\n}\n");
	pt_made = TRUE;
};

// The renderer went: the engine re-resolves each decal's shader by name on its
// next emit (cl_ents.c CL_EmitPersistentDecals), after this hook has run.
void() Paint_Lost =
{
	Paint_Shader();
};

void() Paint_RegisterCvars =
{
	registercommand("+paint");
	registercommand("-paint");
	registercommand("paint");
	registercommand("paint_clear");
	registercommand("paint_fill");
	registercommand("paint_status");
	registercommand("paint_save");
	registercommand("paint_load");
	registercvar("paint_color", "", CVAR_ARCHIVE);  // "r g b" 0..255; "" is your body colour; "random"
	registercvar("paint_size",  "16", CVAR_ARCHIVE);
	registercvar("paint_alpha", "0.9", CVAR_ARCHIVE);
	registercvar("paint_max",   "8192", CVAR_ARCHIVE);
	registercvar("paint_rate",  "20", CVAR_ARCHIVE);  // discs a second while held; 0 every frame
	registercvar("paint_autoload", "1", CVAR_ARCHIVE);  // Patch 777: this map's saved layout
};

// A saturated hue: h 0..1 round the wheel, s 0..1.
vector(float h, float s) Paint_Hue =
{
	local vector c;

	h = h * 6;
	c_x = bound(0, fabs(h - 3) - 1, 1);
	c_y = bound(0, 2 - fabs(h - 2), 1);
	c_z = bound(0, 2 - fabs(h - 4), 1);
	return c * s + '1 1 1' * (1 - s);
};

vector() Paint_RGB =
{
	local vector v;
	local string s;

	s = cvar_string("paint_color");
	if (!strcmp(s, "random"))
		return Paint_Hue(random(), 0.75 + random() * 0.25);
	v = Av_Parse255(s);
	if (v_x >= 0)
		return v / 255;
	return Av_MyBody();
};

float() Paint_Rate = { return bound(0, cvar("paint_rate"), 1000); };
float() Paint_Held = { return pt_plus || pt_key || pt_key2; };

float() Paint_Count = { return pt_n; };
float() Paint_Size = { return bound(2, cvar("paint_size"), 256); };
float() Paint_Max = { return bound(1, floor(cvar("paint_max")), PAINT_CAP); };

void() Paint_Init =
{
	if (pt_ring)
		return;
	pt_ring = memalloc(PAINT_CAP * 4);
	pt_dat = memalloc(PAINT_CAP * PD_N * 4);
	pt_pend = memalloc(PAINT_PEND * PD_N * 4);
	pt_probe = spawn();
	pt_probe.hitcontentsmaski = CONTENTBITS_BOXSOLID;
	pt_source = checkextension("FTESURF_DECAL_SOURCE");
};

void() Paint_DropOldest =
{
	removedecal(pt_ring[pt_tail]);
	pt_tail = (pt_tail + 1) % PAINT_CAP;
	pt_n = pt_n - 1;
};

void() Paint_LoadEnd =
{
	if (pt_ldf >= 0)
		fclose(pt_ldf);
	pt_ldf = -1;
};

void() Paint_Clear =
{
	while (pt_n > 0)
		Paint_DropOldest();
	pt_tail = 0;
	pt_pn = 0;
	pt_rx = 0;
	Paint_LoadEnd();
	pt_last = pt_lastn = '0 0 0';
};

// The engine dropped every decal with the old map (CL_ClearState).
void() Paint_WorldLoaded =
{
	pt_tail = pt_n = 0;
	pt_pn = pt_rx = 0;
	Paint_LoadEnd();
	pt_plus = pt_once = FALSE;
	pt_key = pt_key2 = pt_downkey = 0;
	pt_filln = 0;
	pt_last = pt_lastn = '0 0 0';
	pt_layn = -2;
	// Late: the brush entities a layout's discs lie on arrive with the first packets.
	pt_autoat = cvar("paint_autoload") ? cltime + 3 : 0;
};

// The disc at a hit, or -1 when no face there takes it.
float(vector hit, vector n, entity e, vector col, float size, float alpha) Paint_Place =
{
	local vector tang;
	local float depth;

	if (e != world && !pt_source)
		return -1;
	if (fabs(n_z) < 0.9)
		tang = normalize(crossproduct(n, '0 0 1'));
	else
		tang = normalize(crossproduct(n, '1 0 0'));
	// Alpha falls to 0 at depth/2 off the hit plane: a face bent toward the spray
	// fades out within half the disc, and a curved surface under flat clip is reached.
	depth = max(8, size);
	return adddecal_static(PAINT_SHADER, hit, n * (1 / depth), tang * (1 / size),
	                       col, [alpha, 1, 0], '0 1 1', '0 1 0');
};

void(float *d, float j, vector o, vector n, vector col, float size, float alpha, float from) Paint_Put =
{
	d[j] = o_x; d[j + 1] = o_y; d[j + 2] = o_z;
	d[j + 3] = n_x; d[j + 4] = n_y; d[j + 5] = n_z;
	d[j + 6] = col_x; d[j + 7] = col_y; d[j + 8] = col_z;
	d[j + 9] = size; d[j + 10] = alpha; d[j + 11] = from;
};

void(float h, vector o, vector n, vector col, float size, float alpha, float from) Paint_Push =
{
	local float i;

	i = (pt_tail + pt_n) % PAINT_CAP;
	pt_ring[i] = h;
	Paint_Put(pt_dat, i * PD_N, o, n, col, size, alpha, from);
	pt_n = pt_n + 1;
	while (pt_n > Paint_Max())
		Paint_DropOldest();
};

/*
  A disc from a layout or another player: placed now, or kept until its face is
  here.  TRUE when it was placed.
*/
float(vector o, vector n, vector col, float size, float alpha, float from) Paint_Add =
{
	local float h;

	Paint_Init();
	if (!pt_made)
		Paint_Shader();
	size = bound(2, size, 256);
	alpha = bound(0.05, alpha, 1);
	if (pt_n >= PAINT_CAP)
		Paint_DropOldest();
	h = Paint_Place(o, n, world, col, size, alpha);
	if (h >= 0)
	{
		Paint_Push(h, o, n, col, size, alpha, from);
		return TRUE;
	}
	if (pt_pn < PAINT_PEND - 1)       // the last cell is Paint_LoadStep's scratch
	{
		Paint_Put(pt_pend, pt_pn * PD_N, o, n, col, size, alpha, from);
		pt_pn = pt_pn + 1;
	}
	return FALSE;
};

vector(float *d, float j) Paint_O = { return [d[j], d[j + 1], d[j + 2]]; };
vector(float *d, float j) Paint_N = { return [d[j + 3], d[j + 4], d[j + 5]]; };
vector(float *d, float j) Paint_C = { return [d[j + 6], d[j + 7], d[j + 8]]; };

// Once a second, up to 64 waiting discs within 4096u of the camera.
void(vector cam) Paint_Retry =
{
	local float k, tries, j, h, last;

	if (!pt_pn || cltime < pt_pnext)
		return;
	pt_pnext = cltime + 1;
	tries = 0;
	for (k = 0; k < pt_pn && tries < 64; k = k + 1)
	{
		if (pt_pcur >= pt_pn)
			pt_pcur = 0;
		j = pt_pcur * PD_N;
		if (vlen(Paint_O(pt_pend, j) - cam) > 4096)
		{
			pt_pcur = pt_pcur + 1;
			continue;
		}
		tries = tries + 1;
		if (pt_n >= PAINT_CAP)
			Paint_DropOldest();
		h = Paint_Place(Paint_O(pt_pend, j), Paint_N(pt_pend, j), world, Paint_C(pt_pend, j),
		                pt_pend[j + 9], pt_pend[j + 10]);
		if (h < 0)
		{
			pt_pcur = pt_pcur + 1;
			continue;
		}
		Paint_Push(h, Paint_O(pt_pend, j), Paint_N(pt_pend, j), Paint_C(pt_pend, j),
		           pt_pend[j + 9], pt_pend[j + 10], pt_pend[j + 11]);
		// The last waiting disc fills the hole; the cursor stays to try it next.
		pt_pn = pt_pn - 1;
		last = pt_pn * PD_N;
		Paint_Put(pt_pend, j, Paint_O(pt_pend, last), Paint_N(pt_pend, last), Paint_C(pt_pend, last),
		          pt_pend[last + 9], pt_pend[last + 10], pt_pend[last + 11]);
	}
};

// A disc another player sent (cl_share.qc).
void(vector o, vector n, vector col, float size, float alpha, float from) Paint_Receive =
{
	Paint_Add(o, n, col, size, alpha, from);
	pt_rx = pt_rx + 1;
};

/*
  One disc along `dir` from `org`.  `spaced`: skip a hit within PAINT_GAP of the
  last; a held key repeats on one spot at paint_rate instead (Paint_Frame).  TRUE
  when a disc was tried.
  The aim stops at player collision first -- a func_illusionary ramp is drawn over
  clip, at the clip -- and when no face is there, at the first visible solid along
  the same line if that is within PAINT_BEHIND of it.  Further than that, the
  collision belonged to something with no faces to paint (a static prop, an
  invisible wall) and painting what lies beyond it would mark the wrong place.
*/
float(vector org, vector dir, float spaced) Paint_At =
{
	local vector n, hit, col;
	local float h, size, alpha;
	local entity e;

	Paint_Init();
	if (!pt_made)
		Paint_Shader();

	traceline(org, org + dir * PAINT_RANGE, MOVE_NOMONSTERS, pt_probe);
	// A camera inside an invisible solid (noclip, a spectator) still sees past it.
	if (trace_fraction >= 1 || trace_allsolid)
	{
		pt_nohit = pt_nohit + 1;
		pt_missorg = org;
		pt_misssolid = trace_startsolid;
		return FALSE;
	}
	n = trace_plane_normal;
	hit = trace_endpos;
	e = trace_ent;
	col = Paint_RGB();
	if (spaced)
	if (n * pt_lastn > 0.99)
	if (vlen(hit - pt_last) < Paint_Size() * PAINT_GAP)
	{
		pt_skipped = pt_skipped + 1;
		return FALSE;
	}

	// Spaced whether or not it lands: a key held on an unpaintable spot tries once.
	pt_last = hit;
	pt_lastorg = org;
	pt_lastn = n;
	pt_lastcol = col;
	if (pt_n >= PAINT_CAP)
		Paint_DropOldest();
	size = Paint_Size();
	alpha = bound(0.05, cvar("paint_alpha"), 1);
	h = Paint_Place(hit, n, e, col, size, alpha);
	if (h < 0)
	{
		traceline(org, org + dir * PAINT_RANGE, MOVE_NOMONSTERS, world);
		if (trace_fraction < 1 && !trace_allsolid && vlen(trace_endpos - hit) > 1)
		if (vlen(trace_endpos - hit) <= PAINT_BEHIND)
		{
			n = trace_plane_normal;
			hit = trace_endpos;
			e = trace_ent;
			h = Paint_Place(hit, n, e, col, size, alpha);
		}
	}
	if (h < 0)
	{
		if (e != world && !pt_source)
			pt_nonworld = pt_nonworld + 1;
		else
			pt_nogeom = pt_nogeom + 1;  // sky, a nodraw face, or no face in reach
		pt_noface = hit;
		pt_nofacen = n;
		return TRUE;
	}
	Paint_Push(h, hit, n, col, size, alpha, 0);
	pt_placed = pt_placed + 1;
	pt_lasth = h;
	Share_OnPaint(hit, n, col, size, alpha);
	return TRUE;
};

// n discs in a cone of `deg` around the view: a sunflower spiral, each in a new spot.
void(vector org, float n, float deg) Paint_Fill =
{
	local vector fw, rt, up;
	local float i, a, r;

	fw = v_forward;
	rt = v_right;
	up = v_up;
	r = tan(bound(0, deg, 80) * (M_PI / 180));
	for (i = 0; i < n; i = i + 1)
	{
		a = i * 2.39996;
		Paint_At(org, normalize(fw + (rt * cos(a) + up * sin(a)) * (r * sqrt((i + 0.5) / n))), FALSE);
	}
	print(sprintf("paint: fill %g, %g live\n", n, pt_n));
};

// Letters, digits, _ and - only: nothing a server or a console line could steer.
string(string m) Paint_FileWord =
{
	local string c, o;
	local float i;

	o = "";
	for (i = 0; i < strlen(m) && i < 64; i = i + 1)
	{
		c = substring(m, i, 1);
		if (strstrofs("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-", c, 0) < 0)
			c = "_";
		o = strcat(o, c);
	}
	return o;
};

// data/paint/<map>.txt, or <map>_<name>.txt for a named one (`paint_save <name>`).
string(string name) Paint_LayoutPath =
{
	local string m;

	m = Paint_FileWord(serverkey("map"));
	if (m == "")
		return "";
	if (name != "")
		return sprintf("data/paint/%s_%s.txt", m, Paint_FileWord(name));
	return sprintf("data/paint/%s.txt", m);
};

/*
  One `d` line: origin, normal, rgb 0..255, size, alpha.  Lines that do not
  parse are skipped, so a hand-edited file loses only what it broke.
*/
float(string l, float *d, float j) Paint_ParseLine =
{
	local vector o, n, c;

	if (tokenize(l) != 12 || argv(0) != "d")
		return FALSE;
	o = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
	n = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
	c = [stof(argv(7)), stof(argv(8)), stof(argv(9))] * (1 / 255);
	if (!(vlen(n) > 0.9 && vlen(n) < 1.1))
		return FALSE;
	if (!(fabs(o_x) < 65536 && fabs(o_y) < 65536 && fabs(o_z) < 65536))
		return FALSE;
	Paint_Put(d, j, o, normalize(n), [bound(0, c_x, 1), bound(0, c_y, 1), bound(0, c_z, 1)],
	          bound(2, stof(argv(10)), 256), bound(0.05, stof(argv(11)), 1), 0);
	return TRUE;
};

void(filestream f, float *d, float j) Paint_WriteLine =
{
	fputs(f, sprintf("d %.2f %.2f %.2f %.4f %.4f %.4f", d[j], d[j + 1], d[j + 2], d[j + 3], d[j + 4], d[j + 5]),
	      sprintf(" %g %g %g %g %.2f\n", rint(d[j + 6] * 255), rint(d[j + 7] * 255), rint(d[j + 8] * 255),
	              d[j + 9], d[j + 10]));
};

// Everything on the map, waiting discs included.
void(string name) Paint_Save =
{
	local string p;
	local filestream f;
	local float k;

	p = Paint_LayoutPath(name);
	if (p == "")
		return;
	if (pt_ldf >= 0)
	{
		print("paint: still loading; save when it is done\n");
		return;
	}
	f = fopen(p, FILE_WRITE);
	if (f < 0)
	{
		print(sprintf("paint: cannot write %s\n", p));
		return;
	}
	fputs(f, "FTESURF-PAINT 1\n", sprintf("map %s\n", serverkey("map")));
	for (k = 0; k < pt_n; k = k + 1)
		Paint_WriteLine(f, pt_dat, ((pt_tail + k) % PAINT_CAP) * PD_N);
	for (k = 0; k < pt_pn; k = k + 1)
		Paint_WriteLine(f, pt_pend, k * PD_N);
	fclose(f);
	if (name == "")
		pt_layn = pt_n + pt_pn;
	print(sprintf("paint: saved %g to %s\n", pt_n + pt_pn, p));
};

// Replaces what is up; the lines are read PAINT_LOADF a frame by Paint_Frame.
void(string name, float quiet) Paint_Load =
{
	local string p;
	local filestream f;

	p = Paint_LayoutPath(name);
	if (p == "")
		return;
	f = fopen(p, FILE_READ);
	if (f < 0)
	{
		if (name == "")
			pt_layn = -1;
		if (!quiet)
			print(sprintf("paint: no layout saved for this map (%s)\n", p));
		return;
	}
	if (strncmp(fgets(f), "FTESURF-PAINT ", 14))
	{
		fclose(f);
		print(sprintf("paint: %s is not a paint layout\n", p));
		return;
	}
	Paint_Clear();
	pt_ldf = f;
	pt_ldn = pt_ldwait = 0;
	if (pt_ldpath)
		strunzone(pt_ldpath);
	pt_ldpath = strzone(p);
};

void() Paint_LoadStep =
{
	local string l;
	local float i;
	local filestream f;

	f = pt_ldf;
	for (i = 0; i < PAINT_LOADF; i = i + 1)
	{
		l = fgets(f);
		if not (l)
		{
			Paint_LoadEnd();
			if (!strcmp(pt_ldpath, Paint_LayoutPath("")))
				pt_layn = pt_ldn;
			print(sprintf("paint: loaded %g from %s%s\n", pt_ldn, pt_ldpath,
			              pt_ldwait ? sprintf(", %g waiting for their surface to come into view", pt_ldwait) : ""));
			return;
		}
		if (Paint_ParseLine(l, pt_pend, PAINT_PEND * PD_N - PD_N))   // the spare last cell as scratch
		{
			pt_ldn = pt_ldn + 1;
			if (!Paint_Add(Paint_O(pt_pend, PAINT_PEND * PD_N - PD_N), Paint_N(pt_pend, PAINT_PEND * PD_N - PD_N),
			               Paint_C(pt_pend, PAINT_PEND * PD_N - PD_N), pt_pend[PAINT_PEND * PD_N - PD_N + 9],
			               pt_pend[PAINT_PEND * PD_N - PD_N + 10], 0))
				pt_ldwait = pt_ldwait + 1;
		}
	}
};

/*
  Up to `cap` discs into `d` (PD_N each) for cl_share.qc to stream: this map's saved
  layout when `layout` and there is one, else what is up (`mine`: only yours).
*/
float(float *d, float cap, float layout, float mine) Paint_Copy =
{
	local float n, k, j;
	local filestream f;
	local string l;

	n = 0;
	if (layout)
	{
		f = fopen(Paint_LayoutPath(""), FILE_READ);
		if (f >= 0)
		{
			while (n < cap)
			{
				l = fgets(f);
				if not (l)
					break;
				if (Paint_ParseLine(l, d, n * PD_N))
					n = n + 1;
			}
			fclose(f);
			return n;
		}
	}
	for (k = 0; k < pt_n && n < cap; k = k + 1)
	{
		j = ((pt_tail + k) % PAINT_CAP) * PD_N;
		if (mine && pt_dat[j + 11])
			continue;
		Paint_Put(d, n * PD_N, Paint_O(pt_dat, j), Paint_N(pt_dat, j), Paint_C(pt_dat, j),
		          pt_dat[j + 9], pt_dat[j + 10], 0);
		n = n + 1;
	}
	for (k = 0; k < pt_pn && n < cap; k = k + 1)
	{
		j = k * PD_N;
		if (mine && pt_pend[j + 11])
			continue;
		Paint_Put(d, n * PD_N, Paint_O(pt_pend, j), Paint_N(pt_pend, j), Paint_C(pt_pend, j),
		          pt_pend[j + 9], pt_pend[j + 10], 0);
		n = n + 1;
	}
	return n;
};

// Discs in this map's saved layout (-1 none), counted once a map and on save/load.
float() Paint_LayoutCount =
{
	local float n;
	local filestream f;
	local string l;

	if (pt_layn != -2)
		return pt_layn;
	f = fopen(Paint_LayoutPath(""), FILE_READ);
	if (f < 0)
	{
		pt_layn = -1;
		return -1;
	}
	n = 0;
	while (TRUE)
	{
		l = fgets(f);
		if not (l)
			break;
		if (substring(l, 0, 2) == "d ")
			n = n + 1;
	}
	fclose(f);
	pt_layn = n;
	return n;
};

float() Paint_Waiting = { return pt_pn; };
float() Paint_Received = { return pt_rx; };

/*
  After the camera is final and before renderscene, so a disc is in this frame.
  A console command cannot aim: outside this window VF_ORIGIN is whichever scene
  set it last (a HUD preview, a portal), so the commands only ask.
*/
void() Paint_Frame =
{
	local vector org;
	local float r;

	if (pt_autoat && cltime >= pt_autoat)
	{
		pt_autoat = 0;
		if (pt_ring && pt_n)
			pt_layn = -2;               // painting already: the layout waits for paint_load
		else
			Paint_Load("", TRUE);
	}
	if (pt_ldf >= 0)
		Paint_LoadStep();
	if (pt_pn)
		Paint_Retry(getproperty(VF_ORIGIN));
	if (!Paint_Held() && !pt_once && !pt_filln)
		return;
	org = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	r = Paint_Rate();
	/*
	  Held: a disc every frame the aim has moved PAINT_GAP of a disc (a sweep draws
	  a line), and on one spot a disc every 1/paint_rate s (every frame at 0), so a
	  still spray builds up and a random colour keeps changing.
	*/
	if (pt_filln)
		Paint_Fill(org, pt_filln, pt_filldeg);
	else if (pt_once || r <= 0 || cltime >= pt_next)
	{
		Paint_At(org, v_forward, FALSE);
		pt_next = (pt_once || r <= 0) ? cltime + ((r > 0) ? 1 / r : 0) : max(pt_next + 1 / r, cltime);
	}
	else if (Paint_At(org, v_forward, TRUE))
		pt_next = cltime + 1 / r;
	pt_once = FALSE;
	pt_filln = 0;
};

/*
  Every key event, before anything can take it: a key bound to plain `paint`
  (a one-shot command, so the engine sends nothing on release) holds the spray
  from the bind's `paint` until this key comes back up.
*/
void(float evtype, float scanx) Paint_InputEvent =
{
	if (evtype == IE_KEYDOWN)
	{
		// The bind the engine runs for the modifiers held (cl_keys.qc), first command only.
		if (!strcmp(strtrim(Gfx_Field(Keys_BindNow(scanx), 0, ";")), "paint"))
			pt_downkey = scanx;
	}
	else if (evtype == IE_KEYUP)
	{
		if (scanx == pt_downkey)
			pt_downkey = 0;
		if (pt_key && scanx == pt_key)
			pt_key = 0;
		if (pt_key2 && scanx == pt_key2)
			pt_key2 = 0;
	}
};

float(string cmd) Paint_ConsoleCommand =
{
	local string c;

	c = argv(0);
	if (c == "+paint")
	{
		pt_plus = TRUE;
		pt_once = TRUE;     // the press itself always lands
		return TRUE;
	}
	if (c == "-paint")
	{
		pt_plus = FALSE;
		return TRUE;
	}
	if (c == "paint")
	{
		if (pt_downkey)
		{
			if (pt_downkey == pt_key || pt_downkey == pt_key2)
				return TRUE;    // that key is holding already
			if (!pt_key)
				pt_key = pt_downkey;
			else
				pt_key2 = pt_downkey;
		}
		pt_once = TRUE;
		return TRUE;
	}
	if (c == "paint_save")
	{
		Paint_Save(argv(1));
		return TRUE;
	}
	if (c == "paint_load")
	{
		Paint_Load(argv(1), FALSE);
		return TRUE;
	}
	if (c == "paint_clear")
	{
		Paint_Clear();
		print("paint: cleared\n");
		return TRUE;
	}
	if (c == "paint_fill")
	{
		pt_filln = bound(1, stof(argv(1)), PAINT_CAP);
		pt_filldeg = (argv(2) == "") ? 30 : stof(argv(2));
		return TRUE;
	}
	if (c == "paint_status")
	{
		print(sprintf("paint: %g live (max %g), placed %g, no hit %g, brush entity %g, no face %g, spaced %g\n",
		              pt_n, Paint_Max(), pt_placed, pt_nohit, pt_nonworld, pt_nogeom, pt_skipped));
		// Looked up here, not per miss: getsurfacenearpoint walks every world triangle.
		print(sprintf("paint: last miss from %v, start solid %g; last no face at %v normal %v \"%s\"\n",
		              pt_missorg, pt_misssolid, pt_noface, pt_nofacen,
		              (pt_noface == '0 0 0') ? "" : getsurfacetexture(world, getsurfacenearpoint(world, pt_noface))));
		print(sprintf("paint: last aim %v normal %v, handle %g, size %g colour %v alpha %g, source clip %g\n",
		              pt_last, pt_lastn, pt_lasth, Paint_Size(), pt_lastcol * 255, cvar("paint_alpha"), pt_source));
		print(sprintf("paint: rate %g, held %g key %g, aimed from %v\n", Paint_Rate(), Paint_Held(), pt_key, pt_lastorg));
		print(sprintf("paint: received %g, waiting %g, layout %g, loading %g\n", pt_rx, pt_pn, Paint_LayoutCount(),
		              pt_ldf >= 0));
		return TRUE;
	}
	return FALSE;
};
