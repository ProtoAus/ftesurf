/*
  milk_sys.qc -- the MilkDrop-style feedback renderer.  Patch 467.

  Compiled into menu.dat AND csprogs.dat, like sui_sys.qc.  Each VM runs one
  pipeline: the menu draws its 3D space ("mm", glsl/milk_scene.glsl), CSQC
  draws the in-game sky ("ms", glsl/milk_skygen.glsl).  The two never share
  state -- only the spectrum image, which the engine fills.

  One sim tick, at MILK_RATE Hz regardless of the display rate:

      cone    -> <p>_cone                   1/4-size pre-pass, milk_cone only
      scene   -> <p>_scene                  the 3D world / sky seed (milk_checker: half of
                                            it -> <p>_sch, resolved with <p>_scp)
      warp    -> <p>_f(1-k)  from <p>_f(k)  MilkDrop feedback: zoom, rot, decay
      sprites -> <p>_f(1-k)                 milk_sprites(): dots and bars, additive
      bright  -> <p>_b1a                    bloom source at 1/2
      blur    -> <p>_b1b -> <p>_b1a -> <p>_b2a -> <p>_b2b -> <p>_b2a
      shafts  -> <p>_b3                     light shafts at 1/4, only while milk_shafts > 0
      comp    -> <p>_out                    tonemapped, what the screen or sky samples
      fsr     -> <p>_up -> <p>_up2          FSR 1 to milk_upsize, milk_upsize only

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
string milk_scenemaps;          // extra "map" lines for the scene pass (the menu's panel UIs)
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
float  milk_inject, milk_knee;  // warp seeding threshold, bloom knee; 0 = the shaders' defaults
float  milk_scenediv;           // raymarch every Nth tick (0/1 = every tick); the feedback runs every tick
float  milk_grade;              // the cool colour grade, 0 none .. 1 (milk_common.h, milk_grade())
float  milk_shafts;             // light shafts toward milk_focus, 0 = no pass; the menu packs it as milk_focus_z
// The menu's speed options; the sky leaves them 0.  Each only changes which
// passes run and which program variant draws the scene, so off is the
// pipeline as it was.
float  milk_checker;            // raymarch half the scene's pixels, glsl/milk_resolve.glsl the rest
float  milk_cone;               // a 1/4-size pass first finds where each 4x4 block's rays can start
vector milk_upsize;             // FSR 1 up to this size each tick; '0 0 0' = the present stretches out
float  milk_cfgopts;            // milk_checker + 2 * milk_cone, as the targets were made
vector milk_cfgup;              // milk_upsize, likewise
float  milk_cbpar;              // the checkerboard's parity, flipped every raymarch

// Audio, refreshed once per tick.
float milk_bass, milk_mid, milk_treb, milk_vol;
float milk_bass_att, milk_mid_att, milk_treb_att, milk_vol_att;
float milk_beat, milk_beat_bass, milk_beat_treb, milk_rms, milk_live;
// The big hits only: milk_kick is a bass onset well above the track's own
// average bass, milk_hit that or a snare (a treble onset with real body in the
// mids).  Hats and small ticks pulse milk_beat and nothing else; flashes and
// the shaders' beat pulse (M_AUDIOATT.w) use milk_hit.
float milk_kick, milk_hit;

// The reactivity cvar (0 off, 1 normal, 2 wild) to the scale everything is
// multiplied by: "wild" is what "normal" was before 2026-09-30.
float(float r) Milk_ReactCurve = { return (r <= 1) ? 0.6 * max(r, 0) : min(1.2, 0.6 + 0.4 * (r - 1)); };

void() milk_nosprites = {};
var void() milk_sprites = milk_nosprites;
var void() milk_packextra = milk_nosprites;     // fills w_user[12..15] before the upload

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

// The scene pass's material for program `prog` and ping-pong parity k.  Named
// per program because shaderforname never redefines a name it already has.
string(float k, string prog) Milk_SceneMat =
{
	return Milk_N(sprintf("scene%g_%s", k, strreplace("#", "_", prog)));
};

// The scene pass's program: the world's, with the speed options' variants.
string() Milk_SceneProg =
{
	return strcat(milk_prog_scene, milk_checker ? "#CHECKER" : "", milk_cone ? "#CONED" : "");
};

// With milk_cone the scene pass reads the coarse pass's target last (s_cone,
// milk_common.h).
void() Milk_SceneMats =
{
	local float k;
	local string maps;
	for (k = 0; k < 2; k++)
	{
		maps = sprintf("map $rt:%s\nmap $rt:%s\n%s", Milk_N(strcat("f", ftos(k))), MILK_SPEC, milk_scenemaps);
		if (milk_cone)
		{
			Milk_Mat(Milk_SceneMat(k, strcat(milk_prog_scene, "#CONE")), strcat(milk_prog_scene, "#CONE"), maps);
			maps = strcat(maps, sprintf("map $rt:%s\n", Milk_N("cone")));
		}
		Milk_Mat(Milk_SceneMat(k, Milk_SceneProg()), Milk_SceneProg(), maps);
	}
};

// Switch the raymarched world.  Materials are made on first use, so a world
// that is never shown never compiles.
// Zoned: the menu builds per-station names ("milk_vessel#S2") in temp strings.
void(string prog) Milk_SetScene =
{
	if (!strcmp(prog, milk_prog_scene))
		return;
	strunzone(milk_prog_scene);
	milk_prog_scene = strzone(prog);
	if (milk_ready)
		Milk_SceneMats();
};

void(string pre, string scene, string warp, string comp) Milk_Init =
{
	milk_pre = pre;
	milk_prog_scene = strzone(scene);
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

// The coarse pass's target: a quarter of the scene, rounded up so every 4x4
// block has a texel.
vector() Milk_ConeSize = { return [ceil(milk_scsize_x / 4), ceil(milk_scsize_y / 4)]; };

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
	if (milk_checker)
		milk_scsize_x = 2 * floor(milk_scsize_x / 2);
	Milk_Target(Milk_N("scene"), MILK_FMT_RGBA16F, milk_scsize);
	drawfill('0 0 0', milk_scsize, '0 0 0', 1);
	if (milk_checker)
	{
		Milk_Target(Milk_N("sch"), MILK_FMT_RGBA16F, [milk_scsize_x / 2, milk_scsize_y]);
		drawfill('0 0 0', [milk_scsize_x / 2, milk_scsize_y], '0 0 0', 1);
		Milk_Target(Milk_N("scp"), MILK_FMT_RGBA16F, milk_scsize);
		drawfill('0 0 0', milk_scsize, '0 0 0', 1);
	}
	if (milk_cone)
	{
		Milk_Target(Milk_N("cone"), MILK_FMT_RGBA16F, Milk_ConeSize());
		drawfill('0 0 0', Milk_ConeSize(), '0 0 0', 1);
	}
	if (milk_upsize_x > 0)
	{
		Milk_Target(Milk_N("up"), MILK_FMT_RGBA8, milk_upsize);
		drawfill('0 0 0', milk_upsize, '0 0 0', 1);
		Milk_Target(Milk_N("up2"), MILK_FMT_RGBA8, milk_upsize);
		drawfill('0 0 0', milk_upsize, '0 0 0', 1);
	}
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
	Milk_Target(Milk_N("b3"), MILK_FMT_RGBA16F, quarter);
	drawfill('0 0 0', quarter, '0 0 0', 1);
	Milk_Target(Milk_N("out"), MILK_FMT_RGBA8, size);
	drawfill('0 0 0', size, '0 0 0', 1);
	setproperty(VF_RT_DESTCOLOUR, "");

	Milk_SceneMats();
	for (k = 0; k < 2; k++)
	{
		fk = sprintf("map $rt:%s\n", Milk_N(strcat("f", ftos(k))));
		Milk_Mat(Milk_N(strcat("warp", ftos(k))), milk_prog_warp,
		         strcat(fk, sprintf("map $rt:%s\n", Milk_N("scene"))));
		Milk_Mat(Milk_N(strcat("bright", ftos(k))), "milk_bright",
		         strcat(sprintf("map $rt:%s\n", Milk_N("scene")), fk));
		Milk_Mat(Milk_N(strcat("comp", ftos(k))), milk_prog_comp,
		         sprintf("map $rt:%s\n%smap $rt:%s\nmap $rt:%s\nmap $rt:%s\n",
		                 Milk_N("scene"), fk, Milk_N("b1a"), Milk_N("b2a"), Milk_N("b3")));
	}
	Milk_Mat(Milk_N("bh1"), "milk_blur#H",    sprintf("map $rt:%s\n", Milk_N("b1a")));
	Milk_Mat(Milk_N("bv1"), "milk_blur#V",    sprintf("map $rt:%s\n", Milk_N("b1b")));
	Milk_Mat(Milk_N("dn2"), "milk_blur#DOWN", sprintf("map $rt:%s\n", Milk_N("b1a")));
	Milk_Mat(Milk_N("bh2"), "milk_blur#H",    sprintf("map $rt:%s\n", Milk_N("b2a")));
	Milk_Mat(Milk_N("bv2"), "milk_blur#V",    sprintf("map $rt:%s\n", Milk_N("b2b")));
	Milk_Mat(Milk_N("present"), "milk_present", sprintf("map $rt:%s\n", Milk_N("out")));
	Milk_Mat(Milk_N("shafts"), "milk_shafts", sprintf("map $rt:%s\n", Milk_N("scene")));
	// The kick streaks: added, and uncull'd -- a ribbon winds whichever way it
	// travels, and culling dropped every line and half the comets.  The scene is
	// read for the models to hide behind, out only for its size.
	shaderforname(Milk_N("wave"), sprintf("{\ncull none\n{\nprogram milk_wave\nblendfunc add\nmap $rt:%s\nmap $rt:%s\nmap $rt:%s\n}\n}\n",
	              MILK_SPEC, Milk_N("scene"), Milk_N("out")));
	if (milk_checker)
	{
		Milk_Mat(Milk_N("resolve"), "milk_resolve", sprintf("map $rt:%s\nmap $rt:%s\n", Milk_N("sch"), Milk_N("scp")));
		Milk_Mat(Milk_N("scopy"), "milk_resolve#COPY", sprintf("map $rt:%s\n", Milk_N("scene")));
	}
	if (milk_upsize_x > 0)
	{
		Milk_Mat(Milk_N("easu"), "milk_fsr#EASU", sprintf("map $rt:%s\n", Milk_N("out")));
		Milk_Mat(Milk_N("rcas"), "milk_fsr#RCAS", sprintf("map $rt:%s\n", Milk_N("up")));
		Milk_Mat(Milk_N("presentu"), "milk_present", sprintf("map $rt:%s\n", Milk_N("up2")));
	}

	milk_rtsize = size;
	milk_scaled = milk_scenescale;
	milk_cfgopts = milk_checker + 2 * milk_cone;
	milk_cfgup = milk_upsize;
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
		milk_kick = max(milk_kick * 0.86, milk_beat_bass * bound(0, (milk_bass - 1.3) / 0.9, 1));
		milk_hit = max(milk_hit * 0.86, max(milk_kick, 0.8 * milk_beat_treb * bound(0, (milk_mid - 1.2) / 0.8, 1)));
		return;
	}
	// No audio (old engine, OpenAL, silence): let everything decay to rest so
	// a track stopping reads as the space going quiet, not freezing.
	milk_bass *= 0.9;      milk_mid *= 0.9;      milk_treb *= 0.9;      milk_vol *= 0.9;
	milk_bass_att *= 0.95; milk_mid_att *= 0.95; milk_treb_att *= 0.95; milk_vol_att *= 0.95;
	milk_beat *= 0.8;      milk_beat_bass *= 0.8; milk_beat_treb *= 0.8;
	milk_kick *= 0.8;      milk_hit *= 0.8;
	milk_rms = 0;
};

void(float i, float x, float y, float z, float w) Milk_U =
{
	milk_ud[i * 4] = x;
	milk_ud[i * 4 + 1] = y;
	milk_ud[i * 4 + 2] = z;
	milk_ud[i * 4 + 3] = w;
};

// `scene` FALSE on a tick that reuses the last raymarch: the camera and the
// owner's slots then keep the values that image was drawn with, because the
// menu's present and its cursor trace read them back to line up with it.
void(float scene) Milk_Pack =
{
	Milk_U(0, milk_simtime, milk_grade, milk_rtsize_x / max(milk_rtsize_y, 1), milk_ticks);
	Milk_U(1, milk_bass, milk_mid, milk_treb, milk_vol);
	Milk_U(2, milk_bass_att, milk_mid_att, milk_treb_att, milk_hit);
	if (scene)
	{
		Milk_U(3, milk_campos_x, milk_campos_y, milk_campos_z, milk_tanfov);
		Milk_U(4, milk_camfwd_x, milk_camfwd_y, milk_camfwd_z, milk_travel);
		Milk_U(5, milk_camright_x, milk_camright_y, milk_camright_z, milk_inject);
		Milk_U(6, milk_camup_x, milk_camup_y, milk_camup_z, milk_knee);
	}
	Milk_U(7, milk_zoom, milk_rot, milk_decay, milk_wobble);
	Milk_U(8, milk_hue, milk_trails, milk_bloom, milk_exposure);
	Milk_U(9, milk_flash, milk_liquid, milk_checker ? milk_cbpar : milk_speed, milk_kick);
	Milk_U(10, milk_focus_x, milk_focus_y, milk_focus_z, milk_react);
	Milk_U(11, milk_offset_x, milk_offset_y, milk_quality, milk_kaleido);
	if (scene)
		milk_packextra();
	setproperty(VF_USERDATA, milk_ud, MILK_UDBYTES);
};

void(string rt, float fmt, vector size, string mat) Milk_Pass =
{
	setproperty(VF_RT_DESTCOLOUR, rt, fmt, size);
	drawpic('0 0 0', mat, size, '1 1 1', 1);
};

// ------------------------------------------------------------ kick streaks --
// MilkDrop's waves, on the big hits: a ribbon per wave drawn INTO the fresh
// feedback frame after the owner's sprites, so the warp carries each one off
// as a trail.  A kick throws an arc out from milk_wavec, a snare a comet
// spiralling round it, a hard kick now and then the waveform line; the mix's
// waveform bends every line (glsl/milk_wave.glsl).
#define MILK_WAVES 5
float  milk_waves;              // strength, 0 = off: the owner's switch
vector milk_wavec;              // centre, target uv: the menu's landmark, the sky's zenith
float  milk_waver;              // how far an arc flies, in target heights
float  milk_wavedepth;          // how far from the camera they fly: nearer models hide them; 0 = in front of all
float  milk_wavetest;           // harness: throw one every this many seconds, music or not...
float  milk_wavekind;           // ...of this kind, or cycling through them (-1)
float  milk_wv_t0[MILK_WAVES], milk_wv_kind[MILK_WAVES], milk_wv_str[MILK_WAVES], milk_wv_id[MILK_WAVES];
float  milk_wv_n, milk_wv_count, milk_wv_last, milk_wv_kick, milk_wv_hit;
vector milk_rb_p, milk_rb_n, milk_rb_c;         // Milk_RibbonTo's last point
float  milk_rb_wx, milk_rb_on, milk_rb_hw, milk_rb_vt, milk_rb_amp;
float  milk_rb_code;            // the waveform's gain in quarters, x1000, riding on the swing

float(float n) Milk_Hash = { n = sin(n * 12.9898 + 4.1414) * 43758.5453; return n - floor(n); };

vector(float h) Milk_Rainbow =
{
	h *= 6.2831853;
	return [0.5 + 0.5 * cos(h), 0.5 + 0.5 * cos(h - 2.0944), 0.5 + 0.5 * cos(h - 4.1888)];
};

void(float kind, float str) Milk_WaveAdd =
{
	local float i;
	i = milk_wv_n;
	milk_wv_n = (i + 1 >= MILK_WAVES) ? 0 : i + 1;
	milk_wv_t0[i] = milk_simtime;
	milk_wv_kind[i] = kind;
	milk_wv_str[i] = str;
	milk_wv_id[i] = milk_wv_count;
	milk_wv_count++;
	milk_wv_last = milk_simtime;
};

// Once a tick, after Milk_Audio.  Either pulse rises only on a new onset (they
// decay otherwise); the gate can lift a kick over two ticks, hence the 0.1 s.
void() Milk_WaveSpawn =
{
	local float dk, dh;
	dk = milk_kick - milk_wv_kick;
	dh = milk_hit - milk_wv_hit;
	milk_wv_kick = milk_kick;
	milk_wv_hit = milk_hit;
	if (milk_waves <= 0)
		return;
	if (milk_wavetest > 0)
	{
		if ((milk_simtime - milk_wv_last) >= milk_wavetest)
			Milk_WaveAdd((milk_wavekind >= 0) ? milk_wavekind : milk_wv_count - floor(milk_wv_count / 3) * 3, 1);
		return;
	}
	if ((dh < 0.2) || ((milk_simtime - milk_wv_last) < 0.1))
		return;
	if (dk >= 0.2)
		Milk_WaveAdd(((milk_kick > 0.85) && (Milk_Hash(milk_wv_count + 0.37) < 0.3)) ? 2 : 0, min(1, 0.2 + dk * 1.25));
	else
		Milk_WaveAdd(1, min(1, 0.2 + dh * 1.25));
};

// The next point of the current ribbon: a quad from the last one.  p and n
// (unit, across) in target pixels, wx the waveform read, c the light.
void(vector p, vector n, float wx, vector c) Milk_RibbonTo =
{
	if (milk_rb_on)
	{
		R_PolygonVertex(milk_rb_p + milk_rb_n * milk_rb_hw, [milk_rb_wx, milk_rb_vt], milk_rb_c, milk_rb_code + milk_rb_amp);
		R_PolygonVertex(p + n * milk_rb_hw, [wx, milk_rb_vt], c, milk_rb_code + milk_rb_amp);
		R_PolygonVertex(p - n * milk_rb_hw, [wx, -milk_rb_vt], c, milk_rb_code + milk_rb_amp);
		R_PolygonVertex(milk_rb_p - milk_rb_n * milk_rb_hw, [milk_rb_wx, -milk_rb_vt], milk_rb_c, milk_rb_code + milk_rb_amp);
		R_EndPolygon();
	}
	milk_rb_p = p;
	milk_rb_n = n;
	milk_rb_wx = wx;
	milk_rb_c = c;
	milk_rb_on = TRUE;
};

// A ribbon's line width and swing, the swing in target pixels.
void(float thick, float swing) Milk_RibbonBegin =
{
	milk_rb_on = FALSE;
	milk_rb_amp = swing / thick;
	milk_rb_vt = milk_rb_amp + 6;       // the halo is gone 6 widths out
	milk_rb_hw = milk_rb_vt * thick;
};

void() Milk_WavesDraw =
{
	local float i, j, H, th, gc, age, life, a, env, id, h1, h2, h3, h4, h5, h6, h7, h8;
	local float u, r, r0, r1, span, t0, k, w, sp, dir, tau, len;
	local vector c, p, nn, tg, dv, o, col;

	if (milk_waves <= 0)
		return;
	H = milk_rtsize_y;
	th = max(1, 1.25 * H / 540);
	c = [milk_wavec_x * milk_rtsize_x, milk_wavec_y * H];
	// The waveform's gain levels the swing to the mix's RMS, whatever the
	// volume; it rides in the vertex alpha's thousands.  The depth, whole
	// metres, rides in texcoord.x's integer part (glsl/milk_wave.glsl).
	milk_rb_code = floor(bound(1, 0.3 / max(milk_rms, 0.002), 12) * 4) * 1000;
	gc = floor(bound(0, milk_wavedepth, 8000));
	R_BeginPolygon(Milk_N("wave"), 0, TRUE);
	for (i = 0; i < MILK_WAVES; i++)
	{
		if (milk_wv_str[i] <= 0)
			continue;
		age = milk_simtime - milk_wv_t0[i];
		id = milk_wv_id[i] * 7.13;
		h1 = Milk_Hash(id + 0.1);  h2 = Milk_Hash(id + 0.2);  h3 = Milk_Hash(id + 0.3);
		h4 = Milk_Hash(id + 0.4);  h5 = Milk_Hash(id + 0.5);  h6 = Milk_Hash(id + 0.6);
		h7 = Milk_Hash(id + 0.7);  h8 = Milk_Hash(id + 0.8);

		if (milk_wv_kind[i] == 0)
		{
			// The arc: most of a circle round the landmark, flung outward.
			life = 0.7 + 0.25 * h1;
			a = age / life;
			if (a >= 1)
			{
				milk_wv_str[i] = 0;
				continue;
			}
			env = milk_wv_str[i] * pow(1 - a, 1.4) * 2.4 * milk_waves;
			r0 = 0.05 + 0.05 * h2;
			r1 = milk_waver * (0.75 + 0.35 * h3);
			r = H * (r0 + (r1 - r0) * (1 - pow(1 - a, 2.4)));
			span = 3.14159 * (0.75 + 0.55 * h4);
			t0 = 6.2831853 * h5 + (h6 - 0.5) * 1.4 * age;
			w = 0.7 * (1 - a) * (1 - a);
			Milk_RibbonBegin(th, H * (0.012 + 0.018 * h7) * (1 - 0.4 * a));
			for (j = 0; j <= 28; j++)
			{
				u = j / 28;
				nn = [cos(t0 + span * u), sin(t0 + span * u)];
				p = c + nn * (r * (1 + 0.04 * sin(u * 12.566 + h8 * 6.283 + age * 3)));
				k = min(1, min(u, 1 - u) * 7);
				col = (Milk_Rainbow(h1 + 0.8 * a + 0.25 * u) * (1 - w) + '1 1 1' * w) * (env * k);
				Milk_RibbonTo(p, nn, gc + 0.02 + 0.3 * h2 + 0.6 * u, col);
			}
		}
		else if (milk_wv_kind[i] == 1)
		{
			// The comet: a head on a spiral round the landmark -- out from it, or
			// down into it -- trailing its last 0.16 s.
			life = 0.55 + 0.35 * h1;
			a = age / life;
			if (a >= 1)
			{
				milk_wv_str[i] = 0;
				continue;
			}
			env = milk_wv_str[i] * min(1, a * 12) * pow(1 - a, 1.2) * 2.8 * milk_waves;
			dir = (h3 < 0.5) ? -1 : 1;
			sp = 2.2 + 1.3 * h4;                // angular speed, rad/s
			if (h2 < 0.6)
			{
				r0 = 0.06 + 0.1 * h5;
				k = 1.4 + 0.8 * h6;
			}
			else
			{
				r0 = milk_waver * (0.6 + 0.3 * h5);
				k = -1.6 - 0.6 * h6;
			}
			t0 = 6.2831853 * h7;
			Milk_RibbonBegin(th * 1.1, H * 0.006);
			for (j = 0; j <= 12; j++)
			{
				u = j / 12;                     // 0 tail .. 1 head
				tau = max(0, age - 0.16 * (1 - u));
				r = t0 + dir * sp * tau;
				nn = [cos(r), sin(r)];
				tg = [-nn_y, nn_x];
				p = c + nn * (H * r0 * pow(2.7182818, k * tau));
				// Across the path: the spiral's tangent is k radially, dir*sp round.
				dv = normalize(nn * (dir * sp) - tg * k);
				w = u * u * 0.8;
				col = (Milk_Rainbow(h8 + 0.5 * (1 - u) + 0.6 * a) * (1 - w) + '1 1 1' * w) * (env * u * u);
				Milk_RibbonTo(p, dv, gc + 0.2 + 0.2 * h5 + 0.5 * u, col);
			}
		}
		else
		{
			// The waveform line, MilkDrop's oldest trick: across the screen by
			// the landmark, thrown up or down.
			life = 0.5 + 0.15 * h1;
			a = age / life;
			if (a >= 1)
			{
				milk_wv_str[i] = 0;
				continue;
			}
			env = milk_wv_str[i] * pow(1 - a, 1.6) * 2.2 * milk_waves;
			r = (h2 - 0.5) * 0.6;
			dv = [cos(r), sin(r)];
			nn = [-dv_y, dv_x];
			dir = (h3 < 0.5) ? -1 : 1;
			o = c + nn * (H * ((h4 - 0.5) * 0.25 + dir * 0.45 * pow(a, 0.8)));
			len = milk_rtsize_x * 1.3;
			w = 0.75 * (1 - a) * (1 - a);
			Milk_RibbonBegin(th, H * (0.03 + 0.02 * h5));
			for (j = 0; j <= 24; j++)
			{
				u = j / 24;
				p = o + dv * (len * (u - 0.5));
				k = min(1, min(u, 1 - u) * 5);
				col = (Milk_Rainbow(h6 + 0.7 * a + 0.3 * u) * (1 - w) + '1 1 1' * w) * (env * k);
				Milk_RibbonTo(p, nn, gc + 0.02 + 0.96 * u, col);
			}
		}
	}
};

void() Milk_Tick =
{
	local float k, nk, t0, scene;
	local vector s, h, q;
	local string sk, nks;

	t0 = gettime(1);
	milk_ticks++;
	milk_simtime += MILK_STEP;
	// Spelled out: fteqcc's precedence made `div <= 1 || t - f * div == 0` never
	// true, and the world silently stopped drawing.
	scene = TRUE;
	if (milk_scenediv > 1)
		scene = (milk_ticks - floor(milk_ticks / milk_scenediv) * milk_scenediv) == 0;
	Milk_Audio();
	Milk_WaveSpawn();
	if (scene && milk_checker)
		milk_cbpar = 1 - milk_cbpar;
	Milk_Pack(scene);

	s = milk_rtsize;
	h = [floor(s_x / 2), floor(s_y / 2)];
	q = [floor(s_x / 4), floor(s_y / 4)];
	k = milk_cur;
	nk = 1 - k;
	sk = ftos(k);
	nks = ftos(nk);

	if (scene)
	{
		if (milk_cone)
			Milk_Pass(Milk_N("cone"), MILK_FMT_RGBA16F, Milk_ConeSize(), Milk_SceneMat(k, strcat(milk_prog_scene, "#CONE")));
		if (milk_checker)
		{
			Milk_Pass(Milk_N("sch"), MILK_FMT_RGBA16F, [milk_scsize_x / 2, milk_scsize_y], Milk_SceneMat(k, Milk_SceneProg()));
			Milk_Pass(Milk_N("scene"), MILK_FMT_RGBA16F, milk_scsize, Milk_N("resolve"));
			Milk_Pass(Milk_N("scp"), MILK_FMT_RGBA16F, milk_scsize, Milk_N("scopy"));
		}
		else
			Milk_Pass(Milk_N("scene"), MILK_FMT_RGBA16F, milk_scsize, Milk_SceneMat(k, Milk_SceneProg()));
	}
	Milk_Pass(Milk_N(strcat("f", nks)), MILK_FMT_RGBA16F, s, Milk_N(strcat("warp", sk)));
	milk_sprites();
	Milk_WavesDraw();
	Milk_Pass(Milk_N("b1a"), MILK_FMT_RGBA16F, h, Milk_N(strcat("bright", nks)));
	Milk_Pass(Milk_N("b1b"), MILK_FMT_RGBA16F, h, Milk_N("bh1"));
	Milk_Pass(Milk_N("b1a"), MILK_FMT_RGBA16F, h, Milk_N("bv1"));
	Milk_Pass(Milk_N("b2a"), MILK_FMT_RGBA16F, q, Milk_N("dn2"));
	Milk_Pass(Milk_N("b2b"), MILK_FMT_RGBA16F, q, Milk_N("bh2"));
	Milk_Pass(Milk_N("b2a"), MILK_FMT_RGBA16F, q, Milk_N("bv2"));
	if (milk_shafts > 0)
		Milk_Pass(Milk_N("b3"), MILK_FMT_RGBA16F, q, Milk_N("shafts"));
	Milk_Pass(Milk_N("out"), MILK_FMT_RGBA8, s, Milk_N(strcat("comp", nks)));
	if (milk_upsize_x > 0)
	{
		Milk_Pass(Milk_N("up"), MILK_FMT_RGBA8, milk_upsize, Milk_N("easu"));
		Milk_Pass(Milk_N("up2"), MILK_FMT_RGBA8, milk_upsize, Milk_N("rcas"));
	}
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
	    || milk_scenescale != milk_scaled || milk_checker + 2 * milk_cone != milk_cfgopts
	    || milk_upsize != milk_cfgup)
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

// The latest out image, full screen; the only per-frame pass.  The menu passes
// its own material, which also draws the panels.  The rest of w_user is still
// the last tick's, which is what keeps a panel drawn here registered with the
// slab that tick raymarched.
void(vector pos, vector size, float alpha, string mat) Milk_PresentMat =
{
	Milk_U(11, milk_offset_x, milk_offset_y, milk_quality, milk_kaleido);
	setproperty(VF_USERDATA, milk_ud, MILK_UDBYTES);
	drawpic(pos, mat, size, '1 1 1', alpha);
};

void(vector pos, vector size, float alpha) Milk_Present =
{
	Milk_PresentMat(pos, size, alpha, Milk_N((milk_cfgup_x > 0) ? "presentu" : "present"));
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
