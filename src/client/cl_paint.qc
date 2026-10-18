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
      paint_clear         remove yours
      paint_fill <n> [deg]  n discs in a cone, for the stress arm
      paint_status        counts, the last hit and the cvars
===========================================================================
*/

void(float handle) removedecal = #0:removedecal;

#define PAINT_SHADER "ftesurf/paint"
#define PAINT_RANGE  32768
#define PAINT_CAP    60000      // the engine's store holds 0xFFFE, shared with the map's decals
#define PAINT_GAP    0.3        // of the size: a held key over one spot adds nothing
#define PAINT_BEHIND 32         // how far past an unpaintable collision hit a visible face may be

float *pt_ring;                 // handles, oldest at pt_tail
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
	registercvar("paint_color", "", CVAR_ARCHIVE);  // "r g b" 0..255; "" is your body colour; "random"
	registercvar("paint_size",  "16", CVAR_ARCHIVE);
	registercvar("paint_alpha", "0.9", CVAR_ARCHIVE);
	registercvar("paint_max",   "8192", CVAR_ARCHIVE);
	registercvar("paint_rate",  "20", CVAR_ARCHIVE);  // discs a second while held; 0 every frame
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

void() Paint_DropOldest =
{
	removedecal(pt_ring[pt_tail]);
	pt_tail = (pt_tail + 1) % PAINT_CAP;
	pt_n = pt_n - 1;
};

void() Paint_Clear =
{
	while (pt_n > 0)
		Paint_DropOldest();
	pt_tail = 0;
	pt_last = pt_lastn = '0 0 0';
};

// The engine dropped every decal with the old map (CL_ClearState).
void() Paint_WorldLoaded =
{
	pt_tail = pt_n = 0;
	pt_plus = pt_once = FALSE;
	pt_key = pt_key2 = pt_downkey = 0;
	pt_filln = 0;
	pt_last = pt_lastn = '0 0 0';
};

// The disc at a hit, or -1 when no face there takes it.
float(vector hit, vector n, entity e, vector col) Paint_Place =
{
	local vector tang;
	local float size, depth;

	if (e != world && !pt_source)
		return -1;
	size = Paint_Size();
	if (fabs(n_z) < 0.9)
		tang = normalize(crossproduct(n, '0 0 1'));
	else
		tang = normalize(crossproduct(n, '1 0 0'));
	// Alpha falls to 0 at depth/2 off the hit plane: a face bent toward the spray
	// fades out within half the disc, and a curved surface under flat clip is reached.
	depth = max(8, size);
	return adddecal_static(PAINT_SHADER, hit, n * (1 / depth), tang * (1 / size),
	                       col, [bound(0.05, cvar("paint_alpha"), 1), 1, 0], '0 1 1', '0 1 0');
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
	local float h;
	local entity e;

	if (!pt_ring)
	{
		pt_ring = memalloc(PAINT_CAP * 4);
		pt_probe = spawn();
		pt_probe.hitcontentsmaski = CONTENTBITS_BOXSOLID;
		pt_source = checkextension("FTESURF_DECAL_SOURCE");
	}
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
	h = Paint_Place(hit, n, e, col);
	if (h < 0)
	{
		traceline(org, org + dir * PAINT_RANGE, MOVE_NOMONSTERS, world);
		if (trace_fraction < 1 && !trace_allsolid && vlen(trace_endpos - hit) > 1)
		if (vlen(trace_endpos - hit) <= PAINT_BEHIND)
		{
			n = trace_plane_normal;
			hit = trace_endpos;
			e = trace_ent;
			h = Paint_Place(hit, n, e, col);
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
	pt_ring[(pt_tail + pt_n) % PAINT_CAP] = h;
	pt_n = pt_n + 1;
	while (pt_n > Paint_Max())
		Paint_DropOldest();
	pt_placed = pt_placed + 1;
	pt_lasth = h;
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

/*
  After the camera is final and before renderscene, so a disc is in this frame.
  A console command cannot aim: outside this window VF_ORIGIN is whichever scene
  set it last (a HUD preview, a portal), so the commands only ask.
*/
void() Paint_Frame =
{
	local vector org;
	local float r;

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
		return TRUE;
	}
	return FALSE;
};
