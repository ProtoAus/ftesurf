/*
===========================================================================
  cl_ptrail.qc -- Patch 772: the player trail as a line.

  Replaces the particle trail (tools/mkavatarfx.py's ftesurf_avtrail blocks),
  which read as a scatter of dots.  Each trail is a ring of recent positions
  drawn as one camera-facing ribbon (R_EndPolygonRibbon) that fades with age
  and is cut at a teleport.  Slots: your own, and one per streamed body by
  owner slot.  The length stops keep the particle trail's lifetimes.
===========================================================================
*/

void(float radius, vector texcoordbias) R_EndPolygonRibbon = #0:R_EndPolygonRibbon;

#define PT_SHADER   "ftesurf/ptrail"
#define PT_SLOTS    66          // PT_SELF, then PT_BODY + owner slot 0..63
#define PT_SELF     0
#define PT_BODY     2
#define PT_RING     256
#define PT_STEP     16          // units between kept points...
#define PT_DT       0.0156      // ...and at most 64 a second: 3 s fits the ring
#define PT_HALFW    2           // half the line's width, units
#define PT_ALPHA    0.85
#define PT_LIFT     '0 0 8'     // off the feet, so a standing trail clears the floor

// Per slot.
#define PM_HEAD     0           // newest point's index
#define PM_N        1           // points held
#define PM_FED      2           // cltime of the last feed
#define PM_X        3           // where the body is now
#define PM_R        6
#define PM_LIFE     9
#define PM_SHOW     10
#define PM_CUT      11          // the body is cut off from the newest point
#define PT_META     12

float *ptr_pts;                 // PT_SLOTS * PT_RING * 4: x y z t, t < 0 where the line breaks before it
float *ptr_meta;                // PT_SLOTS * PT_META
float ptr_made;                 // the shader is registered for this renderer
float ptr_drawn, ptr_verts;     // last frame's ribbons and points, for `trail_status`

// The four length stops, seconds: the particle blocks' mean lives (0.575 x 1, 2, 3, 5).
float(float stop) PTrail_Life =
{
	if (stop <= 0) return 0.6;
	if (stop == 1) return 1.2;
	if (stop == 2) return 1.8;
	return 3.0;
};

void() PTrail_Shader =
{
	ptr_made = TRUE;
	if (!Milk_Supported())
	{
		shaderforname(PT_SHADER, "{\ncull disable\n{\nmap $whiteimage\nblendfunc blend\nrgbgen vertex\nalphagen vertex\n}\n}\n");
		return;
	}
	shaderforname(PT_SHADER,
		"{\nglslprogram\n{\n"
		"!!ver 110\n"
		"varying vec2 tc;\n"
		"varying vec4 vc;\n"
		"#ifdef VERTEX_SHADER\n"
		"attribute vec2 v_texcoord;\n"
		"attribute vec4 v_colour;\n"
		"void main()\n{\n"
		" tc = v_texcoord;\n"
		" vc = v_colour;\n"
		" gl_Position = ftetransform();\n"
		"}\n#endif\n"
		"#ifdef FRAGMENT_SHADER\n"
		"void main()\n{\n"
		// t runs 0..1 across the width: a one-pixel antialiased edge, and a line
		// thinner than a pixel fades by its width instead of breaking into dashes.
		" float dt = max(fwidth(tc.y), 0.000001);\n"
		" float a = clamp((1.0 - abs(tc.y * 2.0 - 1.0)) * 0.5 / dt, 0.0, 1.0) * min(1.0 / dt, 1.0);\n"
		" if (a <= 0.0) discard;\n"
		" gl_FragColor = vec4(vc.rgb, vc.a * a);\n"
		"}\n#endif\n"
		"}\n"
		"cull disable\nsort additive\n"
		"{\nmap $whiteimage\nblendfunc blend\nrgbgen vertex\nalphagen vertex\n}\n"
		"surfaceparm noshadows\nsurfaceparm nodlight\n}\n");
};

void() PTrail_Lost = { PTrail_Shader(); };

void() PTrail_RegisterCvars =
{
	registercommand("trail_status");
};

float() PTrail_Alloc =
{
	if (!ptr_pts)
	{
		ptr_pts  = memalloc(PT_SLOTS * PT_RING * 4 * 4);
		ptr_meta = memalloc(PT_SLOTS * PT_META * 4);
	}
	return ptr_pts != 0;
};

// Every slot empty: a new map, so no line spans the load.
void() PTrail_Reset =
{
	local float i;

	if (!ptr_meta)
		return;
	for (i = 0; i < PT_SLOTS * PT_META; i = i + 1)
		ptr_meta[i] = 0;
};

/*
  Where body `id` is this frame.  `cut`: it did not travel here (a teleport, a
  load, a respawn), so the line breaks.  A slot not fed for 0.25 s breaks too,
  or switching the trail back on would join it to where it was switched off.
*/
void(float id, vector pos, float cut, vector rgb, float life, float show) PTrail_Feed =
{
	local float m, b, h, n, t;
	local vector lp;

	if (id < 0 || id >= PT_SLOTS || !PTrail_Alloc())
		return;
	m = id * PT_META;
	pos = pos + PT_LIFT;
	n = ptr_meta[m + PM_N];
	if (cltime - ptr_meta[m + PM_FED] > 0.25)
		cut = TRUE;
	h = ptr_meta[m + PM_HEAD];
	b = (id * PT_RING + h) * 4;
	lp = [ptr_pts[b], ptr_pts[b + 1], ptr_pts[b + 2]];
	t = fabs(ptr_pts[b + 3]);
	if (n == 0 || ptr_meta[m + PM_CUT])
		cut = TRUE;
	if (cut || (vlen(pos - lp) >= PT_STEP && cltime - t >= PT_DT))
	{
		h = (h + 1) % PT_RING;
		b = (id * PT_RING + h) * 4;
		ptr_pts[b] = pos_x;
		ptr_pts[b + 1] = pos_y;
		ptr_pts[b + 2] = pos_z;
		ptr_pts[b + 3] = cut ? -cltime : cltime;
		ptr_meta[m + PM_HEAD] = h;
		ptr_meta[m + PM_N] = min(n + 1, PT_RING);
	}
	ptr_meta[m + PM_CUT] = FALSE;
	ptr_meta[m + PM_FED] = cltime;
	ptr_meta[m + PM_X] = pos_x;
	ptr_meta[m + PM_X + 1] = pos_y;
	ptr_meta[m + PM_X + 2] = pos_z;
	ptr_meta[m + PM_R] = rgb_x;
	ptr_meta[m + PM_R + 1] = rgb_y;
	ptr_meta[m + PM_R + 2] = rgb_z;
	ptr_meta[m + PM_LIFE] = life;
	ptr_meta[m + PM_SHOW] = show;
};

// The trail is off: the next feed starts a new line.
void(float id) PTrail_Cut =
{
	if (id >= 0 && id < PT_SLOTS && ptr_meta)
		ptr_meta[id * PT_META + PM_CUT] = TRUE;
};

void(float id) PTrail_DrawOne =
{
	local float m, n, h, k, i, b, t, age, life, open, now;
	local vector rgb, p, head;

	m = id * PT_META;
	n = ptr_meta[m + PM_N];
	life = ptr_meta[m + PM_LIFE];
	if (n < 1 || life <= 0 || !ptr_meta[m + PM_SHOW])
		return;
	now = cltime;
	h = ptr_meta[m + PM_HEAD];
	if (now - fabs(ptr_pts[(id * PT_RING + h) * 4 + 3]) >= life && now - ptr_meta[m + PM_FED] > 0.1)
		return;                         // all faded, and the body is gone
	rgb = [ptr_meta[m + PM_R], ptr_meta[m + PM_R + 1], ptr_meta[m + PM_R + 2]];
	open = FALSE;
	p = '0 0 0';
	for (k = n - 1; k >= 0; k = k - 1)
	{
		i = (h - k + PT_RING) % PT_RING;
		b = (id * PT_RING + i) * 4;
		t = ptr_pts[b + 3];
		if (t < 0 && open)
		{
			R_EndPolygonRibbon(PT_HALFW, '0 1 0');
			open = FALSE;
		}
		age = now - fabs(t);
		if (age >= life)
			continue;
		if (!open)
		{
			R_BeginPolygon(PT_SHADER, 0);
			open = TRUE;
			ptr_drawn = ptr_drawn + 1;
		}
		p = [ptr_pts[b], ptr_pts[b + 1], ptr_pts[b + 2]];
		R_PolygonVertex(p, '0.5 0 0', rgb, PT_ALPHA * (1 - age / life));
		ptr_verts = ptr_verts + 1;
	}
	// The newest point is up to PT_STEP behind the body: join it while it is here.
	head = [ptr_meta[m + PM_X], ptr_meta[m + PM_X + 1], ptr_meta[m + PM_X + 2]];
	if (open && now - ptr_meta[m + PM_FED] <= 0.1 && !ptr_meta[m + PM_CUT])
	if (vlen(head - p) >= 1)
	{
		R_PolygonVertex(head, '0.5 0 0', rgb, PT_ALPHA);
		ptr_verts = ptr_verts + 1;
	}
	if (open)
		R_EndPolygonRibbon(PT_HALFW, '0 1 0');
};

// After addentities (the bodies' predraws feed) and before renderscene.
void() PTrail_DrawAll =
{
	local float id;

	ptr_drawn = ptr_verts = 0;
	if (!ptr_meta || !checkbuiltin(R_EndPolygonRibbon))
		return;
	if (!ptr_made)
		PTrail_Shader();
	for (id = 0; id < PT_SLOTS; id = id + 1)
		PTrail_DrawOne(id);
};

float(string cmd) PTrail_ConsoleCommand =
{
	local float id, m, live;

	if (argv(0) != "trail_status")
		return FALSE;
	live = 0;
	if (ptr_meta)
	for (id = 0; id < PT_SLOTS; id = id + 1)
	{
		m = id * PT_META;
		if (ptr_meta[m + PM_N] < 1 || cltime - ptr_meta[m + PM_FED] > 1)
			continue;
		live = live + 1;
		print(sprintf("trail: slot %g points %g life %g show %g at %v colour %v\n", id,
		              ptr_meta[m + PM_N], ptr_meta[m + PM_LIFE], ptr_meta[m + PM_SHOW],
		              [ptr_meta[m + PM_X], ptr_meta[m + PM_X + 1], ptr_meta[m + PM_X + 2]],
		              [ptr_meta[m + PM_R], ptr_meta[m + PM_R + 1], ptr_meta[m + PM_R + 2]] * 255));
	}
	print(sprintf("trail: %g fed, last frame %g lines of %g points, ribbon builtin %g\n",
	              live, ptr_drawn, ptr_verts, checkbuiltin(R_EndPolygonRibbon)));
	return TRUE;
};
