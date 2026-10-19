// Map-centered analytic sky layers; feedback supplies only their emission.

float ms_ground, ms_vz, ms_shock;
vector ms_center;
float ms_scale, ms_palette_next, ms_thumb_next, ms_thumb_rows, ms_thumb_peak;
var filestream ms_thumb_file = -1;
#define MILK_META_ROWS 64
var float ms_thumb_page = -1;
var float ms_thumb_cell = -1;
string ms_thumb_map;

void() MilkSky_Pack =
{
	local vector eye;
	eye = getproperty(VF_ORIGIN);
	Milk_U(12, ms_center_x, ms_center_y, ms_center_z, ms_scale);
	Milk_U(13, eye_x, eye_y, eye_z, bound(0, cvar("milk_sky_parallax"), 1));
	Milk_U(14, bound(0, cvar("milk_sky_palette"), 1), 0, 0, 0);
	Milk_U(15, 0, 0, 0, 0);
};

void() MilkSky_ThumbnailClose =
{
	if (ms_thumb_file >= 0)
		fclose(ms_thumb_file);
	ms_thumb_file = -1;
};

void() MilkSky_Thumbnail =
{
	local string want;
	MilkSky_ThumbnailClose();
	ms_thumb_rows = ms_thumb_peak = 0;
	ms_thumb_next = gettime(0) + 5;
	want = strzone(serverkey("map"));
	if (strcmp(want, ms_thumb_map))
	{
		ms_thumb_page = ms_thumb_cell = -1;
		ms_palette_next = 0;
	}
	strunzone(ms_thumb_map);
	ms_thumb_map = want;
	if (want != "")
		ms_thumb_file = fopen("data/mapmeta.txt", FILE_READ);
	if (ms_thumb_file < 0)
	{
		ms_thumb_page = ms_thumb_cell = -1;
		ms_palette_next = 0;
	}
};

void(float page, float cell, float now) MilkSky_ThumbnailDone =
{
	MilkSky_ThumbnailClose();
	if (page != ms_thumb_page || cell != ms_thumb_cell)
		ms_palette_next = 0;
	ms_thumb_page = page;
	ms_thumb_cell = cell;
	ms_thumb_next = now + ((page >= 0) ? 30 : 5);
};

float(string s) MilkSky_Index =
{
	local float i, c, v;
	if (s == "" || strlen(s) > 8) return -1;
	for (i = 0; i < strlen(s); i += 1)
	{
		c = str2chr(s, i);
		if (c < 48 || c > 57) return -1;
	}
	v = stof(s);
	if (v > 16777215) return -1;     // exact float integer range
	return v;
};

// Bound file work per view; retry misses and notice regenerated atlas coordinates.
void(float now) MilkSky_Metadata =
{
	local string ln;
	local float i, n, page, cell;
	if (ms_thumb_file < 0)
	{
		if (now < ms_thumb_next) return;
		MilkSky_Thumbnail();
	}
	if (ms_thumb_file < 0) return;
	for (i = 0; i < MILK_META_ROWS; i += 1)
	{
		ln = fgets(ms_thumb_file);
		if not (ln)  // raw null handle: !ln also treats a blank line as false
		{
			MilkSky_ThumbnailDone(-1, -1, now);
			return;
		}
		ms_thumb_rows += 1;
		ms_thumb_peak = max(ms_thumb_peak, i + 1);
		n = tokenize(ln);
		if (n < 8) continue;
		if (argv(0) != "meta") continue;
		if (strcmp(argv(1), ms_thumb_map)) continue;
		page = MilkSky_Index(argv(6));
		cell = MilkSky_Index(argv(7));
		if (page < 0 || cell < 0 || cell >= 448)
			page = cell = -1;
		MilkSky_ThumbnailDone(page, cell, now);
		return;
	}
};

void() MilkSky_Info =
{
	if (argv(1) == "refresh")
		MilkSky_Thumbnail();
	print(sprintf("milk_skyinfo: map %s page %g cell %g scanning %g rows %g maxbatch %g\n",
	              ms_thumb_map, ms_thumb_page, ms_thumb_cell, ms_thumb_file >= 0, ms_thumb_rows, ms_thumb_peak));
};

// Redraw once a second: late asynchronous loads and vid_restart replace fallback.
void(float now) MilkSky_Palette =
{
	local string pic;
	local vector sp;
	local float col, row;
	if (now < ms_palette_next) return;
	ms_palette_next = now + 1;
	setproperty(VF_RT_DESTCOLOUR, "ms_palette", MILK_FMT_RGBA8, '32 18 0');
	drawfill('0 0 0', '32 18 0', '0.42 0.44 0.46', 1);
	if (ms_thumb_page >= 0)
	{
		pic = strcat("gfx/mapthumbs/atlas", ftos(ms_thumb_page));
		col = ms_thumb_cell - floor(ms_thumb_cell / 16) * 16;
		row = floor(ms_thumb_cell / 16);
		sp = [(col * 128 + 0.5) / 2048, (row * 72 + 0.5) / 2048];
		// Like ui_bgatlas: absent/pending drawsubpic is a no-op, not error art.
		drawsubpic('0 0 0', '32 18 0', pic, sp, '0.06201171875 0.03466796875 0', '1 1 1', 1);
	}
	setproperty(VF_RT_DESTCOLOUR, "");
};

void() MilkSky_Init =
{
	registercommand("milk_skyinfo");
	registercvar("milk_sky", "0", CVAR_ARCHIVE);        // the menu registers these first
	registercvar("milk_sky_parallax", "1", CVAR_ARCHIVE);
	registercvar("milk_sky_palette", "1", CVAR_ARCHIVE);
	registercvar("milk_grade", "0", CVAR_ARCHIVE);
	registercvar("milk_streaks", "2", CVAR_ARCHIVE);
	Milk_Init("ms", "milk_skygen", "milk_warp#SKY", "milk_comp#SKY");
	milk_packextra = MilkSky_Pack;
};

void() MilkSky_WorldLoaded =
{
	local vector extent;
	// Engine binds world model bounds before calling CSQC_WorldLoaded.
	ms_center = (world.mins + world.maxs) * 0.5;
	extent = world.maxs - world.mins;
	ms_scale = max(4096, vlen(extent));
	ms_ground = ms_vz = ms_shock = 0;
	ms_palette_next = 0;
	MilkSky_ThumbnailClose();
	strunzone(ms_thumb_map);
	ms_thumb_map = "";
	ms_thumb_page = ms_thumb_cell = -1;
	ms_thumb_next = 0;
	// The map key may still be empty; start lookup only in an active sky frame.
	if (cvar("milk_sky"))
	if (Milk_Supported())
	if (cvar_string("r_skybox") != "milk")
		localcmd("r_skybox milk\n");
};

void(string rendererdescription) CSQC_RendererRestarted =
{
	Milk_Invalidate();
	MilkSky_ThumbnailClose();
	ms_thumb_next = ms_palette_next = 0;
	Gfx_WaterSupport();
	_sui_rnd_forget();              // Patch 642: the corner masks went with the renderer
	SteamPic_Lost();                // Patch 640: its textures and shaders went with it
	Paint_Lost();                   // Patch 772: re-register before the decals re-resolve
	PTrail_Lost();
	LineGraph_CacheLost();         // Patch 837
};

// Before renderscene, every frame; ticks only when the sim is due.
void() MilkSky_Frame =
{
	local float now, q, s;

	if (cvar_string("r_skybox") != "milk" || !Milk_Supported())
	{
		if (ms_thumb_file >= 0)
		{
			MilkSky_ThumbnailClose();
			ms_thumb_next = 0;
		}
		return;
	}

	now = gettime(0);
	if (strcmp(serverkey("map"), ms_thumb_map))
	{
		MilkSky_Thumbnail();
		ms_palette_next = 0;
	}
	MilkSky_Metadata(now);
	MilkSky_Palette(now);

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
	milk_react = Milk_ReactCurve(cvar("milk_react"));
	milk_grade = bound(0, cvar("milk_grade"), 1);
	milk_trails = 0.6 * cvar("milk_trails");
	milk_focus = [0.5, 0.5, ms_shock];
	milk_hue = 0.62 + 0.12 * sin(now * 0.021);
	milk_zoom = 1.005 + 0.03 * milk_speed + 0.008 * milk_kick * milk_react;
	milk_rot = 0.0015 + 0.005 * milk_speed;
	milk_decay = 0.93 + 0.03 * milk_speed;
	milk_wobble = 0.3 + 0.45 * milk_bass_att * milk_react;
	milk_liquid = 0.35;
	milk_kaleido = 0;
	milk_bloom = 0.8;
	milk_exposure = 1.3;
	milk_flash = milk_hit * milk_react * 0.6;
	// Kick streaks only when asked for the sky too (milk_streaks 2): they fly
	// from the zenith out to the horizon ring.
	milk_waves = (cvar("milk_streaks") >= 2) ? milk_react : 0;
	milk_wavec = '0.5 0.5 0';
	milk_waver = 0.44;
	milk_wavetest = cvar("milk_bcwaves");       // harness only (the menu registers it)

	q = bound(1, cvar("milk_quality"), 3);
	milk_quality = q;
	s = 256 + q * 128;          // 384 / 512 / 640 square
	Milk_Frame([s, s], now);
	// Camera must update even on frames between fixed-rate feedback ticks.
	MilkSky_Pack();
	setproperty(VF_USERDATA, milk_ud, MILK_UDBYTES);
};
