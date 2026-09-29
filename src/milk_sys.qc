/*
  milk_sys.qc -- the MilkDrop-style feedback renderer.  Patch 467.

  Compiled into menu.dat AND csprogs.dat, like sui_sys.qc.  Each VM runs one
  pipeline: the menu draws its 3D space ("mm", glsl/milk_scene.glsl), CSQC
  draws the in-game sky ("ms", glsl/milk_skygen.glsl).  The two never share
  state -- only the spectrum image, which the engine fills.

  One sim tick, at MILK_RATE Hz regardless of the display rate:

      scene   -> <p>_scene                  the 3D world / sky seed
      warp    -> <p>_f(1-k)  from <p>_f(k)  MilkDrop feedback: zoom, rot, decay
      sprites -> <p>_f(1-k)                 milk_sprites(): dots and bars, additive
      bright  -> <p>_b1a                    bloom source at 1/2
      blur    -> <p>_b1b -> <p>_b1a -> <p>_b2a -> <p>_b2b -> <p>_b2a
      comp    -> <p>_out                    tonemapped, what the screen or sky samples

  WHY A FIXED RATE.  MilkDrop applies its zoom and decay once per rendered
  frame, so its presets run 4x faster at 240 fps (MilkDrop3's README warns of
  it).  FTESurf ships cl_maxfps 1000, so per-frame would be both wrong and
  expensive; at 60 Hz the passes land on 6% of frames and the rest only sample
  <p>_out.

  RENDER TARGETS.  setproperty(VF_RT_DESTCOLOUR, name, fmt, size) creates the
  image the first time and is a no-op after (Image_Upload returns early on an
  unchanged size and format, image.c:15214), and a bound target is never
  cleared, which is what lets the feedback survive between ticks.  Every
  target is configured before any material that names it is drawn: drawpic
  falls back to no_texture while a shader's first image is missing.  The
  switch itself flushes pending 2D draws first (pr_csqc.c:2485), so polygons
  issued while a target is bound land in that target.

  Materials are built with shaderforname because their names carry the
  prefix and the ping-pong parity; the feedback always reads a FIXED $rt name,
  never $sourcecolour.
*/

#define MILK_RATE       60
#define MILK_STEP       (1 / MILK_RATE)
#define MILK_FMT_RGBA8  1       // IMGFMT_R8G8B8A8   (pr_cmds.c:14174)
#define MILK_FMT_RGBA16F 2      // IMGFMT_R16G16B16A16F
#define MILK_SPEC       "milk_spec"
#define MILK_SPECBANDS  128
#define MILK_UDBYTES    ((__uint)256)     // 16 vec4 -> w_user[16]

// Patch 467's engine half: analysis of the software mix.  Absent on an older
// engine, which checkbuiltin reports; the milk then runs without audio.
float(float *out, float count) snd_getvis = #0:snd_getvis;
float(string imagename, float bands) snd_visimage = #0:snd_visimage;

string milk_pre;                // target / material prefix
string milk_prog_scene, milk_prog_warp, milk_prog_comp;
vector milk_rtsize;             // internal size the targets were made at
vector milk_scsize;             // the scene target: milk_rtsize * milk_scenescale
float  milk_scenescale;         // < 1 renders the raymarch smaller; the trails hide it
float  milk_ready;
float  milk_cur;                // which feedback target holds the newest frame
float  milk_accum, milk_last, milk_simtime, milk_ticks, milk_scaled;
float  milk_hasvis;
float *milk_ud;                 // 16 vec4 for VF_USERDATA -> w_user[]
float *milk_vis;                // 16 floats from snd_getvis
float  milk_tickcost;           // wall time of the last tick's QC, seconds

// --- what the owner sets before each Milk_Frame; see glsl/milk_common.h ---
vector milk_campos, milk_camfwd, milk_camright, milk_camup;
float  milk_tanfov, milk_travel;
float  milk_zoom, milk_rot, milk_decay, milk_wobble;
float  milk_hue, milk_trails, milk_bloom, milk_exposure;
float  milk_flash, milk_liquid, milk_speed;
vector milk_focus;              // xy zoom centre in uv, z highlight / shock radius
float  milk_react, milk_quality, milk_kaleido;
vector milk_offset;             // present-time parallax, uv

// Audio, refreshed once per tick.
float milk_bass, milk_mid, milk_treb, milk_vol;
float milk_bass_att, milk_mid_att, milk_treb_att, milk_vol_att;
float milk_beat, milk_beat_bass, milk_beat_treb, milk_rms, milk_live;

void() milk_nosprites = {};
var void() milk_sprites = milk_nosprites;

// GL only, by construction: on Vulkan the 2D render-target switch is an empty
// function (vk_init.c:4095), so every pass would draw onto the screen instead.
// "" is the default and resolves to GL (renderer.c's priority order).
float() Milk_Supported =
{
	local string r;
	r = strtolower(cvar_string("vid_renderer"));
	return r == "" || substring(r, 0, 2) == "gl" || substring(r, 0, 6) == "opengl";
};

// One material.  `maps` is a run of "map ..." lines.
void(string name, string prog, string maps) Milk_Mat =
{
	shaderforname(name, sprintf("{\n{\nprogram %s\n%s}\n}\n", prog, maps));
};

string(string what) Milk_N = { return strcat(milk_pre, "_", what); };

void(string rt, float fmt, vector size) Milk_Target =
{
	setproperty(VF_RT_DESTCOLOUR, rt, fmt, size);
};

void(string pre, string scene, string warp, string comp) Milk_Init =
{
	milk_pre = pre;
	milk_prog_scene = scene;
	milk_prog_warp = warp;
	milk_prog_comp = comp;
	if (!milk_ud)
		milk_ud = (float*)memalloc(MILK_UDBYTES);
	if (!milk_vis)
		milk_vis = (float*)memalloc(16 * 4);
	milk_hasvis = checkbuiltin(snd_getvis) && checkbuiltin(snd_visimage);
	milk_ready = FALSE;

	milk_tanfov = 0.62;
	milk_zoom = 1.01;
	milk_decay = 0.90;
	milk_trails = 1;
	milk_bloom = 1;
	milk_exposure = 1;
	milk_react = 1;
	milk_quality = 2;
	milk_focus = '0.5 0.5 0';
	milk_scenescale = 1;
};

// (Re)create every target at `size` and clear it, then the materials.
void(vector size) Milk_Configure =
{
	local vector half, quarter;
	local float k;
	local string fk;

	size_x = floor(size_x);
	size_y = floor(size_y);
	half = [floor(size_x / 2), floor(size_y / 2)];
	quarter = [floor(size_x / 4), floor(size_y / 4)];

	// The spectrum first: every scene material names it, and if the engine
	// cannot fill it, it must still exist (and be black).
	Milk_Target(MILK_SPEC, MILK_FMT_RGBA8, [MILK_SPECBANDS, 2]);
	drawfill('0 0 0', [MILK_SPECBANDS, 2], '0 0 0', 1);

	milk_scsize = [floor(size_x * milk_scenescale), floor(size_y * milk_scenescale)];
	Milk_Target(Milk_N("scene"), MILK_FMT_RGBA16F, milk_scsize);
	drawfill('0 0 0', milk_scsize, '0 0 0', 1);
	Milk_Target(Milk_N("f0"), MILK_FMT_RGBA16F, size);
	drawfill('0 0 0', size, '0 0 0', 1);
	Milk_Target(Milk_N("f1"), MILK_FMT_RGBA16F, size);
	drawfill('0 0 0', size, '0 0 0', 1);
	Milk_Target(Milk_N("b1a"), MILK_FMT_RGBA16F, half);
	drawfill('0 0 0', half, '0 0 0', 1);
	Milk_Target(Milk_N("b1b"), MILK_FMT_RGBA16F, half);
	drawfill('0 0 0', half, '0 0 0', 1);
	Milk_Target(Milk_N("b2a"), MILK_FMT_RGBA16F, quarter);
	drawfill('0 0 0', quarter, '0 0 0', 1);
	Milk_Target(Milk_N("b2b"), MILK_FMT_RGBA16F, quarter);
	drawfill('0 0 0', quarter, '0 0 0', 1);
	Milk_Target(Milk_N("out"), MILK_FMT_RGBA8, size);
	drawfill('0 0 0', size, '0 0 0', 1);
	setproperty(VF_RT_DESTCOLOUR, "");

	for (k = 0; k < 2; k++)
	{
		fk = sprintf("map $rt:%s\n", Milk_N(strcat("f", ftos(k))));
		Milk_Mat(Milk_N(strcat("scene", ftos(k))), milk_prog_scene,
		         strcat(fk, sprintf("map $rt:%s\n", MILK_SPEC)));
		Milk_Mat(Milk_N(strcat("warp", ftos(k))), milk_prog_warp,
		         strcat(fk, sprintf("map $rt:%s\n", Milk_N("scene"))));
		Milk_Mat(Milk_N(strcat("bright", ftos(k))), "milk_bright",
		         strcat(sprintf("map $rt:%s\n", Milk_N("scene")), fk));
		Milk_Mat(Milk_N(strcat("comp", ftos(k))), milk_prog_comp,
		         sprintf("map $rt:%s\n%smap $rt:%s\nmap $rt:%s\n",
		                 Milk_N("scene"), fk, Milk_N("b1a"), Milk_N("b2a")));
	}
	Milk_Mat(Milk_N("bh1"), "milk_blur#H",    sprintf("map $rt:%s\n", Milk_N("b1a")));
	Milk_Mat(Milk_N("bv1"), "milk_blur#V",    sprintf("map $rt:%s\n", Milk_N("b1b")));
	Milk_Mat(Milk_N("dn2"), "milk_blur#DOWN", sprintf("map $rt:%s\n", Milk_N("b1a")));
	Milk_Mat(Milk_N("bh2"), "milk_blur#H",    sprintf("map $rt:%s\n", Milk_N("b2a")));
	Milk_Mat(Milk_N("bv2"), "milk_blur#V",    sprintf("map $rt:%s\n", Milk_N("b2b")));
	Milk_Mat(Milk_N("present"), "milk_present", sprintf("map $rt:%s\n", Milk_N("out")));

	milk_rtsize = size;
	milk_scaled = milk_scenescale;
	milk_cur = 0;
	milk_ready = TRUE;
};

// A renderer restart destroys every target; the next frame rebuilds them.
void() Milk_Invalidate = { milk_ready = FALSE; milk_rtsize = '0 0 0'; };

void() Milk_Audio =
{
	milk_live = 0;
	// Nested, not &&: QC does not short-circuit, and calling a #0: builtin the
	// engine lacks aborts the whole VM ("Builtin 0:snd_getvis not implemented").
	if (milk_hasvis)
	if (snd_getvis(milk_vis, 16) >= 14)
	if (milk_vis[13])
	{
		// Clamped: the ratios are relative to the track's own average, so a lone
		// hat after a quiet bar reads 28 (measured) and would blow the shaders out.
		milk_bass = bound(0, milk_vis[0], 3);      milk_mid = bound(0, milk_vis[1], 3);
		milk_treb = bound(0, milk_vis[2], 3);      milk_vol = bound(0, milk_vis[6], 3);
		milk_bass_att = bound(0, milk_vis[3], 2.5); milk_mid_att = bound(0, milk_vis[4], 2.5);
		milk_treb_att = bound(0, milk_vis[5], 2.5); milk_vol_att = bound(0, milk_vis[7], 2.5);
		milk_beat = bound(0, milk_vis[8], 1);      milk_beat_bass = bound(0, milk_vis[9], 1);
		milk_beat_treb = bound(0, milk_vis[10], 1);
		milk_rms = milk_vis[11];
		milk_live = 1;
		snd_visimage(MILK_SPEC, MILK_SPECBANDS);
		return;
	}
	// No audio (old engine, OpenAL, silence): let everything decay to rest so
	// a track stopping reads as the space going quiet, not freezing.
	milk_bass *= 0.9;      milk_mid *= 0.9;      milk_treb *= 0.9;      milk_vol *= 0.9;
	milk_bass_att *= 0.95; milk_mid_att *= 0.95; milk_treb_att *= 0.95; milk_vol_att *= 0.95;
	milk_beat *= 0.8;      milk_beat_bass *= 0.8; milk_beat_treb *= 0.8;
	milk_rms = 0;
};

void(float i, float x, float y, float z, float w) Milk_U =
{
	milk_ud[i * 4] = x;
	milk_ud[i * 4 + 1] = y;
	milk_ud[i * 4 + 2] = z;
	milk_ud[i * 4 + 3] = w;
};

void() Milk_Pack =
{
	Milk_U(0, milk_simtime, MILK_STEP, milk_rtsize_x / max(milk_rtsize_y, 1), milk_ticks);
	Milk_U(1, milk_bass, milk_mid, milk_treb, milk_vol);
	Milk_U(2, milk_bass_att, milk_mid_att, milk_treb_att, milk_beat);
	Milk_U(3, milk_campos_x, milk_campos_y, milk_campos_z, milk_tanfov);
	Milk_U(4, milk_camfwd_x, milk_camfwd_y, milk_camfwd_z, milk_travel);
	Milk_U(5, milk_camright_x, milk_camright_y, milk_camright_z, 0);
	Milk_U(6, milk_camup_x, milk_camup_y, milk_camup_z, 0);
	Milk_U(7, milk_zoom, milk_rot, milk_decay, milk_wobble);
	Milk_U(8, milk_hue, milk_trails, milk_bloom, milk_exposure);
	Milk_U(9, milk_flash, milk_liquid, milk_speed, milk_beat_bass);
	Milk_U(10, milk_focus_x, milk_focus_y, milk_focus_z, milk_react);
	Milk_U(11, milk_offset_x, milk_offset_y, milk_quality, milk_kaleido);
	setproperty(VF_USERDATA, milk_ud, MILK_UDBYTES);
};

void(string rt, float fmt, vector size, string mat) Milk_Pass =
{
	setproperty(VF_RT_DESTCOLOUR, rt, fmt, size);
	drawpic('0 0 0', mat, size, '1 1 1', 1);
};

void() Milk_Tick =
{
	local float k, nk, t0;
	local vector s, h, q;
	local string sk, nks;

	t0 = gettime(1);
	milk_ticks++;
	milk_simtime += MILK_STEP;
	Milk_Audio();
	Milk_Pack();

	s = milk_rtsize;
	h = [floor(s_x / 2), floor(s_y / 2)];
	q = [floor(s_x / 4), floor(s_y / 4)];
	k = milk_cur;
	nk = 1 - k;
	sk = ftos(k);
	nks = ftos(nk);

	Milk_Pass(Milk_N("scene"), MILK_FMT_RGBA16F, milk_scsize, Milk_N(strcat("scene", sk)));
	Milk_Pass(Milk_N(strcat("f", nks)), MILK_FMT_RGBA16F, s, Milk_N(strcat("warp", sk)));
	milk_sprites();
	Milk_Pass(Milk_N("b1a"), MILK_FMT_RGBA16F, h, Milk_N(strcat("bright", nks)));
	Milk_Pass(Milk_N("b1b"), MILK_FMT_RGBA16F, h, Milk_N("bh1"));
	Milk_Pass(Milk_N("b1a"), MILK_FMT_RGBA16F, h, Milk_N("bv1"));
	Milk_Pass(Milk_N("b2a"), MILK_FMT_RGBA16F, q, Milk_N("dn2"));
	Milk_Pass(Milk_N("b2b"), MILK_FMT_RGBA16F, q, Milk_N("bh2"));
	Milk_Pass(Milk_N("b2a"), MILK_FMT_RGBA16F, q, Milk_N("bv2"));
	Milk_Pass(Milk_N("out"), MILK_FMT_RGBA8, s, Milk_N(strcat("comp", nks)));
	setproperty(VF_RT_DESTCOLOUR, "");

	milk_cur = nk;
	milk_tickcost = gettime(1) - t0;
};

/*
  Advance the sim to `now` in whole ticks.  At most two ticks per frame: a
  long hitch (a map load, a breakpoint) is dropped rather than replayed as a
  burst of catch-up ticks that would stall the next frame too.
*/
void(vector size, float now) Milk_Frame =
{
	local float n, dt, maxn;

	if (!milk_ready || size_x != milk_rtsize_x || size_y != milk_rtsize_y
	    || milk_scenescale != milk_scaled)
		Milk_Configure(size);

	if (!milk_last)
		milk_last = now;
	dt = now - milk_last;
	milk_last = now;
	milk_accum += bound(0, dt, 0.25);

	// A GPU that is already behind (a frame past 25 ms) gets one tick per
	// frame, not a catch-up pair: the sim slows a little instead of the
	// frame rate collapsing under two ticks a frame.
	maxn = (dt > 0.025) ? 1 : 2;
	n = 0;
	while (milk_accum >= MILK_STEP && n < maxn)
	{
		Milk_Tick();
		milk_accum -= MILK_STEP;
		n++;
	}
	if (milk_accum > MILK_STEP)
		milk_accum = 0;
};

// Map a point in the owner's screen space to the target's pixel space.
vector(vector p, vector screensize) Milk_ToRT =
{
	return [p_x * milk_rtsize_x / screensize_x, p_y * milk_rtsize_y / screensize_y];
};

// The latest out image, full screen; the only per-frame pass.
void(vector pos, vector size, float alpha) Milk_Present =
{
	Milk_U(11, milk_offset_x, milk_offset_y, milk_quality, milk_kaleido);
	setproperty(VF_USERDATA, milk_ud, MILK_UDBYTES);
	drawpic(pos, Milk_N("present"), size, '1 1 1', alpha);
};

// A soft additive dot / bar into the target that is currently bound (only
// valid inside milk_sprites).  Target pixel coordinates.
void(vector c, float rad, vector rgb, float alpha) Milk_Dot =
{
	R_BeginPolygon("milk_dot", 0, TRUE);
	R_PolygonVertex([c_x - rad, c_y - rad], '0 0 0', rgb, alpha);
	R_PolygonVertex([c_x + rad, c_y - rad], '1 0 0', rgb, alpha);
	R_PolygonVertex([c_x + rad, c_y + rad], '1 1 0', rgb, alpha);
	R_PolygonVertex([c_x - rad, c_y + rad], '0 1 0', rgb, alpha);
	R_EndPolygon();
};

void(vector pos, vector size, vector rgb, float alpha) Milk_Bar =
{
	R_BeginPolygon("milk_bar", 0, TRUE);
	R_PolygonVertex(pos, '0 0 0', rgb, alpha);
	R_PolygonVertex([pos_x + size_x, pos_y], '1 0 0', rgb, alpha);
	R_PolygonVertex([pos_x + size_x, pos_y + size_y], '1 1 0', rgb, alpha);
	R_PolygonVertex([pos_x, pos_y + size_y], '0 1 0', rgb, alpha);
	R_EndPolygon();
};

// The palette, identical to milk_pal in glsl/milk_common.h, so UI colour
// matches the light in the scene.
vector(float t) Milk_Pal =
{
	return [0.50 + 0.45 * cos(6.2831853 * (t + 0.62)),
	        0.46 + 0.42 * cos(6.2831853 * (t + 0.40)),
	        0.62 + 0.40 * cos(6.2831853 * (t + 0.18))];
};
