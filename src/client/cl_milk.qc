/*
  cl_milk.qc -- the visualizer as the map's sky.  Patch 467.

  On while r_skybox is "milk": scripts/milk.shader's skybox_milk then draws
  every sky surface from $rt:ms_out, which this file refreshes through
  milk_sys.qc's pipeline once per sim tick, before renderscene.  The seed is
  2D (glsl/milk_skygen.glsl), not the menu's raymarch: the sky is on screen
  for most of a surf run, so it gets the cheap path -- about nine small
  passes at 60 Hz, and one texture tap per sky pixel per frame.

  What drives it: the software mix (music AND the game's own sounds, via
  snd_getvis), your horizontal speed, and landings.  Visual only: nothing here
  reads or writes input, angles or the recording.

  milk_sky (archived, set from the menu's VISUALS screen) is the setting;
  r_skybox is not archived, so it is re-applied at every map load.
*/

float ms_ground, ms_vz, ms_shock;

void() MilkSky_Init =
{
	registercvar("milk_sky", "0", CVAR_ARCHIVE);        // the menu registers it first
	Milk_Init("ms", "milk_skygen", "milk_warp#SKY", "milk_comp#SKY");
};

void() MilkSky_WorldLoaded =
{
	if (cvar("milk_sky"))
	if (Milk_Supported())
	if (cvar_string("r_skybox") != "milk")
		localcmd("r_skybox milk\n");
};

void(string rendererdescription) CSQC_RendererRestarted =
{
	Milk_Invalidate();
};

// Before renderscene, every frame; ticks only when the sim is due.
void() MilkSky_Frame =
{
	local float now, q, s;

	if (cvar_string("r_skybox") != "milk")
		return;
	if (!Milk_Supported())
		return;

	now = gettime(0);

	// A landing launches a ring from the zenith: grounded now, falling fast a
	// frame ago.  The ring's radius is its age.
	if (pmove_onground)
	if (!ms_ground)
	if (ms_vz < -300)
		ms_shock = 0.02;
	ms_ground = pmove_onground;
	ms_vz = pmove_vel_z;
	if (ms_shock > 0)
	{
		ms_shock += clframetime * 0.9;
		if (ms_shock > 1.3)
			ms_shock = 0;
	}

	milk_speed = bound(0, vlen([pmove_vel_x, pmove_vel_y, 0]) / 3500, 1);
	milk_react = cvar("milk_react");
	milk_trails = 0.6 * cvar("milk_trails");
	milk_focus = [0.5, 0.5, ms_shock];
	milk_hue = 0.62 + 0.12 * sin(now * 0.021);
	milk_zoom = 1.005 + 0.03 * milk_speed + 0.012 * milk_beat_bass * milk_react;
	milk_rot = 0.0015 + 0.005 * milk_speed;
	milk_decay = 0.93 + 0.03 * milk_speed;
	milk_wobble = 0.3 + 0.8 * milk_mid_att * milk_react;
	milk_liquid = 0.35;
	milk_kaleido = 0;
	milk_bloom = 0.8;
	milk_exposure = 1.3;
	milk_flash = milk_beat * milk_react * 0.6;

	q = bound(1, cvar("milk_quality"), 3);
	milk_quality = q;
	s = 256 + q * 128;          // 384 / 512 / 640 square
	Milk_Frame([s, s], now);
};
