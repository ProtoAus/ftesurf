// P1309: opt-in native sky-portal/frost meshes and cached-roof winter audio.
// No global sky override, lights, captures, runtime geometry walk or roof trace.
string wx_map;
float *wx_roof;
int wx_width, wx_height;
vector wx_min;
float wx_cell, wx_enabled, wx_ready, wx_audio, wx_audio_on;
entity wx_sky, wx_ice, wx_out, wx_in, wx_thunder;
float wx_outplay, wx_inplay, wx_outvol, wx_invol, wx_sentout, wx_sentin;
float wx_clock, wx_next, wx_flash, wx_thunderat, wx_outside;

float(float x) Weather_Finite =
{
	return (fabs(x) <= 262144); // comparison rejects NaN and infinity too
};

float(float x) Weather_Noise =
{
	local float n;
	n = sin(x * 12.9898 + 1309) * 43758.5453;
	return n - floor(n); // own deterministic schedule, not the game's random state
};

void() Weather_Free =
{
	if (wx_out) { stopsound(wx_out, CHAN_BODY); remove(wx_out); }
	if (wx_in) { stopsound(wx_in, CHAN_BODY); remove(wx_in); }
	if (wx_thunder) { stopsound(wx_thunder, CHAN_VOICE); remove(wx_thunder); }
	if (wx_sky) remove(wx_sky);
	if (wx_ice) remove(wx_ice);
	if (wx_roof) memfree(wx_roof);
	if (strlen(wx_map)) strunzone(wx_map);
	wx_map = "";
	wx_roof = 0;
	wx_out = wx_in = wx_thunder = wx_sky = wx_ice = world;
	wx_enabled = wx_ready = wx_audio = wx_audio_on = wx_outplay = wx_inplay = 0;
	wx_outvol = wx_invol = wx_sentout = wx_sentin = wx_flash = wx_thunderat = 0;
};

void() Weather_Init =
{
	registercvar("r_weather", "0", CVAR_ARCHIVE); // actual moving-view acceptance pending
	registercvar("r_weather_maps", "surf_christmas surf_frost surf_bluewinter", CVAR_ARCHIVE);
	registercvar("r_weather_audio", "1", CVAR_ARCHIVE);
	registercvar("r_weather_volume", "0.18", CVAR_ARCHIVE);
	registercvar("r_weather_ice", "1", CVAR_ARCHIVE);
	registercvar("r_weather_ice_shine", "0.12", CVAR_ARCHIVE);
	registercvar("r_weather_flash", "0.12", CVAR_ARCHIVE); // 0 disables flashes, not thunder
	registercvar("r_weather_test", "0"); // local visual/audio test, never an entitlement
};

void() Weather_Load =
{
	local float fh, n, i, allowed, w, h, sky, ice;
	local int bytes;
	local string line, path;
	Weather_Free();
	wx_enabled = (cvar("r_weather") != 0);
	wx_map = strzone(serverkey("map"));
	if (!wx_enabled) return;
	allowed = FALSE;
	n = tokenize(cvar_string("r_weather_maps"));
	for (i = 0; i < n; i = i + 1)
		if (!strcmp(argv(i), wx_map)) allowed = TRUE;
	if (!allowed) return;
	fh = fopen(sprintf("gfx/weather/%s.roof", wx_map), FILE_READ);
	if (fh < 0) return;
	line = fgets(fh);
	n = tokenize(line);
	if (n != 10) { fclose(fh); return; }
	if (strcmp(argv(0), "weather") || strcmp(argv(1), "1") || strcmp(argv(2), wx_map)) { fclose(fh); return; }
	wx_min = [stof(argv(3)), stof(argv(4)), 0];
	wx_cell = stof(argv(5)); w = stof(argv(6)); h = stof(argv(7));
	sky = stof(argv(8)); ice = stof(argv(9));
	if (!Weather_Finite(wx_min_x) || !Weather_Finite(wx_min_y) || !Weather_Finite(wx_cell) || !Weather_Finite(w) || !Weather_Finite(h)) { fclose(fh); return; }
	if (wx_cell <= 0 || w < 1 || h < 1 || w > 256 || h > 256 || w != floor(w) || h != floor(h)) { fclose(fh); return; }
	if (!Weather_Finite(sky) || !Weather_Finite(ice) || sky < 0 || sky > 4096 || ice < 0 || ice > 8192) { fclose(fh); return; }
	wx_width = (int)w; wx_height = (int)h;
	bytes = wx_width * wx_height * 4i;
	wx_roof = memalloc(bytes);
	if (!wx_roof) { fclose(fh); return; }
	if (fread(fh, wx_roof, bytes) != bytes) { fclose(fh); memfree(wx_roof); wx_roof = 0; return; }
	fclose(fh);
	if (sky > 0)
	{
		if (Snow_Exists("glsl/ftesurf_weather_sky_v1.glsl"))
		{
			if (Snow_Exists("gfx/weather/lightning.png"))
			{
				path = sprintf("models/gibs/winterweather/%s-sky.iqm", wx_map);
				if (Snow_Exists(path))
				{
					shaderforname("ftesurf_weather_sky_v1", "{\ndepthpush -2\ncull none\nsort decal\n{\nprogram ftesurf_weather_sky_v1\nclampmap $nosrgb:gfx/weather/lightning.png\nblendfunc gl_src_alpha gl_one\nrgbgen entity\nalphagen entity\n}\n}\n");
					precache_model(path); wx_sky = spawn(); setmodel(wx_sky, path);
					wx_sky.effects = EF_FULLBRIGHT | EF_NOSHADOW;
					wx_sky.colormod = '1 1 1'; wx_sky.alpha = 0.000001; wx_sky.scale = 1;
				}
			}
		}
	}
	if (ice > 0)
	{
		if (Snow_Exists("glsl/ftesurf_ice_v1.glsl"))
		{
			if (Snow_Exists("gfx/weather/ice-noise.png"))
			{
				path = sprintf("models/gibs/winterweather/%s-ice.iqm", wx_map);
				if (Snow_Exists(path))
				{
					shaderforname("ftesurf_weather_ice_v1", "{\ndepthpush -2\ncull none\nsort blend\n{\nprogram ftesurf_ice_v1\nblendfunc gl_src_alpha gl_one_minus_src_alpha\nmap $nosrgb:gfx/weather/ice-noise.png\nrgbgen entity\nalphagen entity\n}\n}\n");
					precache_model(path); wx_ice = spawn(); setmodel(wx_ice, path);
					wx_ice.effects = EF_FULLBRIGHT | EF_NOSHADOW;
					wx_ice.colormod = '1 1 1'; wx_ice.alpha = 1; wx_ice.scale = 1;
				}
			}
		}
	}
	wx_audio = TRUE;
	if (!Snow_Exists("sound/winter/wind-out.wav")) wx_audio = FALSE;
	if (!Snow_Exists("sound/winter/wind-in.wav")) wx_audio = FALSE;
	if (!Snow_Exists("sound/winter/thunder-out.wav")) wx_audio = FALSE;
	if (!Snow_Exists("sound/winter/thunder-in.wav")) wx_audio = FALSE;
	if (wx_audio)
	{
		precache_sound("winter/wind-out.wav"); precache_sound("winter/wind-in.wav");
		precache_sound("winter/thunder-out.wav"); precache_sound("winter/thunder-in.wav");
		wx_out = spawn(); wx_in = spawn(); wx_thunder = spawn();
	}
	wx_clock = time; wx_next = time + 30 + Weather_Noise(time) * 40;
	wx_ready = TRUE;
	print(sprintf("weather: %s assets sky %g / ice %g tris, audio %g; %g roof cells (opt-in, visual only)\n", wx_map, wx_sky ? sky : 0, wx_ice ? ice : 0, wx_audio, w * h));
};

float(vector eye) Weather_Outside =
{
	local float x, y, roof;
	local int index;
	if (!wx_roof) return 0;
	x = floor((eye_x - wx_min_x) / wx_cell);
	y = floor((eye_y - wx_min_y) / wx_cell);
	if (x < 0 || y < 0 || x >= (float)wx_width || y >= (float)wx_height) return 0;
	index = (int)y * wx_width + (int)x;
	roof = wx_roof[index];
	if (!Weather_Finite(roof)) return 0;
	return bound(0, (eye_z - roof + 32) / 64, 1);
};

// Reuse the native loop/update/stop interface used by cl_soundscape, on OUR entities.
float(entity e, string wave, float volume, float playing) Weather_Loop =
{
	if (volume <= 0.002)
	{
		if (playing) stopsound(e, CHAN_BODY);
		return FALSE;
	}
	if (!playing)
		sound(e, CHAN_BODY, wave, volume, ATTN_NONE, 100, SOUNDFLAG_FORCELOOP | SOUNDFLAG_NOSPACIALISE | SOUNDFLAG_FOLLOW);
	else
		soundupdate(e, CHAN_BODY, "", volume, ATTN_NONE, 100, SOUNDFLAG_FORCELOOP | SOUNDFLAG_NOSPACIALISE | SOUNDFLAG_FOLLOW, 0);
	return TRUE;
};

void() Weather_Frame =
{
	local float enabled, dt, outside, vol, outvol, invol, step, pulse, targetout, targetin;
	local vector eye;
	enabled = (cvar("r_weather") != 0);
	if (!enabled)
	{
		if (wx_enabled) Weather_Free();
		return;
	}
	// CSQC_WorldLoaded is authoritative; don't allocate a map tempstring per frame.
	if (enabled != wx_enabled) Weather_Load();
	if (!wx_ready) return;
	eye = getproperty(VF_ORIGIN);
	dt = bound(0, time - wx_clock, 0.1);
	if (time < wx_clock) { wx_next = time + 30; wx_flash = wx_thunderat = 0; }
	wx_clock = time;
	outside = Weather_Outside(eye);
	wx_outside = outside;
	vol = bound(0, cvar("r_weather_volume"), 0.35);
	if (cvar("r_weather_test"))
	{
		wx_next = time; cvar_set("r_weather_test", "0");
	}
	if (time >= wx_next)
	{
		wx_flash = time + 0.12;
		wx_thunderat = time + 0.9 + Weather_Noise(time + 17) * 2.3;
		wx_next = time + 35 + Weather_Noise(time + 71) * 45;
	}
	if (wx_sky)
	{
		if (time < wx_flash)
		{
			pulse = bound(0, (wx_flash - time) / 0.12, 1);
			wx_sky.alpha = pulse * bound(0, cvar("r_weather_flash"), 0.25);
			if (wx_sky.alpha > 0) addentity(wx_sky);
		}
	}
	if (wx_ice)
		if (cvar("r_weather_ice")) addentity(wx_ice);
	if (!wx_audio) return;
	wx_out.origin = wx_in.origin = wx_thunder.origin = eye;
	if (!cvar("r_weather_audio") || vol <= 0)
	{
		if (wx_audio_on)
		{
			stopsound(wx_out, CHAN_BODY); stopsound(wx_in, CHAN_BODY); stopsound(wx_thunder, CHAN_VOICE);
			wx_outplay = wx_inplay = wx_audio_on = 0;
			wx_outvol = wx_invol = wx_sentout = wx_sentin = 0;
		}
		wx_thunderat = 0;
		return;
	}
	wx_audio_on = TRUE;
	targetout = vol * (0.18 + 0.82 * outside);
	targetin = vol * 0.65 * (1 - outside);
	step = dt * 0.5;
	outvol = wx_outvol + bound(-step, targetout - wx_outvol, step);
	invol = wx_invol + bound(-step, targetin - wx_invol, step);
	if (fabs(outvol - wx_sentout) >= 0.002 || (!wx_outplay && outvol > 0.002) || (wx_outplay && outvol <= 0.002))
	{
		wx_outplay = Weather_Loop(wx_out, "winter/wind-out.wav", outvol, wx_outplay);
		wx_sentout = outvol;
	}
	if (fabs(invol - wx_sentin) >= 0.002 || (!wx_inplay && invol > 0.002) || (wx_inplay && invol <= 0.002))
	{
		wx_inplay = Weather_Loop(wx_in, "winter/wind-in.wav", invol, wx_inplay);
		wx_sentin = invol;
	}
	wx_outvol = outvol; wx_invol = invol;
	if (wx_thunderat > 0)
	{
		if (time >= wx_thunderat)
		{
			wx_thunderat = 0;
			if (vol > 0)
				sound(wx_thunder, CHAN_VOICE, outside > 0.5 ? "winter/thunder-out.wav" : "winter/thunder-in.wav", bound(0, vol * (outside > 0.5 ? 3 : 1.4), 0.9), ATTN_NONE, 100, SOUNDFLAG_NOSPACIALISE);
		}
	}
};
