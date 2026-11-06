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
float wx_pending, wx_retry, wx_tinted;
float wx_flashesleft, wx_nextflash, wx_burstid, wx_previewnext, wx_flashcount, wx_thundercount, wx_loopmode;
string wx_style;
vector wx_stylecolour, wx_boltaxis;

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
	if (wx_tinted)
	{
		// Never restore a previous map's style over the newly loaded world.
		if (!strcmp(wx_map, serverkey("map"))) lightstyle(0, wx_style, wx_stylecolour);
		strunzone(wx_style); wx_style = ""; wx_tinted = FALSE;
	}
	if (strlen(wx_map)) strunzone(wx_map);
	wx_map = "";
	wx_roof = 0;
	wx_out = wx_in = wx_thunder = wx_sky = wx_ice = world;
	wx_enabled = wx_ready = wx_audio = wx_audio_on = wx_outplay = wx_inplay = wx_pending = 0;
	wx_outvol = wx_invol = wx_sentout = wx_sentin = wx_flash = wx_thunderat = 0;
	wx_flashesleft = wx_nextflash = wx_burstid = wx_previewnext = wx_flashcount = wx_thundercount = wx_loopmode = 0;
	wx_boltaxis = '1 0.5 0.5';
};

vector() Weather_SnowTint =
{
	if (wx_tinted) return '0.78 0.86 1';
	return '1 1 1';
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
	registercvar("r_weather_interval", "60", CVAR_ARCHIVE); // seconds, bounded5..900 with jitter
	registercvar("r_weather_loop", "snow", CVAR_ARCHIVE); // snow or rain, audio only
	registercvar("r_weather_test", "0"); //1 once,2 repeat preview;0 stops preview
	registercommand("weather_info");
};

void() Weather_Load =
{
	local float fh, n, i, allowed, w, h, sky, ice;
	local int bytes;
	local string line, path, native;
	Weather_Free();
	wx_enabled = (cvar("r_christmas") != 0 && (cvar("r_weather") != 0 || Winter_ThemeActive()));
	wx_map = strzone(serverkey("map"));
	if (!wx_enabled) return;
	// Like CL_RenderMapFrame: WorldLoaded can precede THIS world's live key.
	native = mapname;
	if (!strcmp(substring(native, 0, 5), "maps/")) native = substring(native, 5, -1);
	n = strlen(native);
	if (n >= 4)
		if (!strcasecmp(substring(native, n - 4, 4), ".bsp")) native = substring(native, 0, n - 4);
	if (!strlen(wx_map) || strcasecmp(native, wx_map))
	{
		wx_pending = TRUE; wx_retry = time + 0.25; return;
	}
	allowed = !strcmp(wx_map, "surf_colin_blaster_69000");
	n = tokenize(cvar_string("r_weather_maps"));
	for (i = 0; i < n; i = i + 1)
		if (!strcmp(argv(i), wx_map)) allowed = TRUE;
	if (!allowed) { print(sprintf("weather: %s not enabled in r_weather_maps\n", wx_map)); return; }
	fh = fopen(sprintf("gfx/weather/%s.roof", wx_map), FILE_READ);
	if (fh < 0) { print(sprintf("weather: missing gfx/weather/%s.roof\n", wx_map)); return; }
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
		if (Snow_Exists("glsl/ftesurf_weather_sky_v3.glsl"))
		{
			if (Snow_Exists("gfx/weather/lightning.png"))
			{
				path = sprintf("models/gibs/winterweather/%s-sky.iqm", wx_map);
				if (Snow_Exists(path))
				{
					precache_model(path); wx_sky = spawn(); setmodel(wx_sky, path);
					wx_sky.forceshader = shaderforname("ftesurf_weather_sky_v3", "{\ndepthpush -2\ncull none\nsort decal\n{\nprogram ftesurf_weather_sky_v3\nclampmap $nosrgb:gfx/weather/lightning.png\nmap $nosrgb:models/christmas/mist-noise.png\nblendfunc blend\nrgbgen entity\nalphagen entity\n}\n}\n");
					wx_sky.effects = EF_FULLBRIGHT | EF_NOSHADOW;
					wx_sky.colormod = '1 1 1'; wx_sky.alpha = 0.65; wx_sky.scale = 1;
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
	if (!Snow_Exists("sound/winter/rainloop.ogg")) wx_audio = FALSE;
	if (!Snow_Exists("sound/winter/snowloop.ogg")) wx_audio = FALSE;
	if (!Snow_Exists("sound/winter/thunder.ogg")) wx_audio = FALSE;
	if (wx_audio)
	{
		precache_sound("winter/rainloop.ogg"); precache_sound("winter/snowloop.ogg");
		precache_sound("winter/thunder.ogg");
		wx_out = spawn(); wx_in = spawn(); wx_thunder = spawn();
	}
	// One reversible base-style tint, not dynamic lights/shadows or per-frame
	// lightmap changes. Preserve the map's brightness/animation and restore OFF.
	if (checkbuiltin(getlightstyle))
	{
		wx_style = strzone(getlightstyle(0, wx_stylecolour));
		lightstyle(0, wx_style, [wx_stylecolour_x * 0.78, wx_stylecolour_y * 0.86, wx_stylecolour_z]);
		wx_tinted = TRUE;
	}
	wx_clock = time; wx_next = time + 8 + Weather_Noise(time) * 8;
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

void() Weather_StartBurst =
{
	local float yaw;
	local vector angles;
	wx_burstid = wx_burstid + 1;
	wx_flashesleft = 3 + floor(Weather_Noise(time + wx_burstid * 13) * 4);
	wx_nextflash = time; wx_thunderat = 0;
	wx_next = time + bound(5, cvar("r_weather_interval"), 900) * (0.65 + Weather_Noise(time + 71) * 0.7);
	wx_previewnext = time + 8;
	// Cache a WORLD direction at event start, not a bolt that follows the camera.
	angles = getproperty(VF_ANGLES);
	yaw = (angles_y + Weather_Noise(time + 39) * 70 - 35) * (M_PI / 180);
	wx_boltaxis = [0.5 + 0.5 * cos(yaw), 0.5 + 0.5 * sin(yaw), 0.5];
};

void() Weather_Frame =
{
	local float enabled, dt, outside, vol, outvol, invol, step, pulse, targetout, targetin, preview, duration, mode;
	local string wave;
	local vector eye;
	enabled = (cvar("r_christmas") != 0 && (cvar("r_weather") != 0 || Winter_ThemeActive()));
	if (!enabled)
	{
		if (wx_enabled) Weather_Free();
		return;
	}
	// CSQC_WorldLoaded is authoritative; don't allocate a map tempstring per frame.
	if (enabled != wx_enabled) Weather_Load();
	if (wx_pending)
		if (time >= wx_retry) Weather_Load();
	if (!wx_ready) return;
	eye = getproperty(VF_ORIGIN);
	dt = bound(0, time - wx_clock, 0.1);
	if (time < wx_clock) { wx_next = time + 8; wx_flash = wx_thunderat = wx_flashesleft = wx_previewnext = 0; }
	wx_clock = time;
	outside = Weather_Outside(eye);
	wx_outside = outside;
	vol = bound(0, cvar("r_weather_volume"), 0.35);
	preview = cvar("r_weather_test");
	if (preview == 1)
	{
		Weather_StartBurst(); cvar_set("r_weather_test", "0");
	}
	else if (wx_flashesleft <= 0 && wx_thunderat <= 0)
	{
		if ((preview >= 2 && time >= wx_previewnext) || time >= wx_next) Weather_StartBurst();
	}
	if (wx_flashesleft > 0)
	{
		if (time >= wx_nextflash)
		{
			// P1332: 3x faster pulse and gap; matched fade keeps the same brightness.
			duration = (0.05 + Weather_Noise(time + wx_flashesleft * 31) * 0.1) / 3;
			wx_flash = time + duration; wx_flashcount = wx_flashcount + 1;
			wx_flashesleft = wx_flashesleft - 1;
			if (wx_flashesleft > 0)
				wx_nextflash = wx_flash + (0.06 + Weather_Noise(time + 83) * 0.28) / 3;
			else
				wx_thunderat = wx_flash + 0.8 + Weather_Noise(time + 17) * 2.3;
		}
	}
	if (wx_sky)
	{
		pulse = bound(0, (wx_flash - time) / 0.04, 1);
		wx_sky.colormod = wx_boltaxis;
		wx_sky.alpha = 0.65 + pulse * bound(0, cvar("r_weather_flash"), 0.25) * 1.4;
		addentity(wx_sky); // persistent moving storm clouds; flashes are additional
	}
	if (wx_ice)
		if (cvar("r_weather_ice")) addentity(wx_ice);
	if (!wx_audio)
	{
		if (wx_thunderat > 0 && time >= wx_thunderat) wx_thunderat = 0;
		return; // missing audio must not stall later visual bursts
	}
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
	mode = !strcasecmp(cvar_string("r_weather_loop"), "rain") ? 2 : 1;
	wave = mode == 2 ? "winter/rainloop.ogg" : "winter/snowloop.ogg";
	if (wx_loopmode != mode)
	{
		stopsound(wx_out, CHAN_BODY); stopsound(wx_in, CHAN_BODY);
		wx_outplay = wx_inplay = 0; wx_sentout = wx_sentin = -1;
		wx_loopmode = mode;
	}
	wx_audio_on = TRUE;
	targetout = vol * (0.18 + 0.82 * outside);
	targetin = vol * 0.65 * (1 - outside);
	step = dt * 0.5;
	outvol = wx_outvol + bound(-step, targetout - wx_outvol, step);
	invol = wx_invol + bound(-step, targetin - wx_invol, step);
	if (fabs(outvol - wx_sentout) >= 0.002 || (!wx_outplay && outvol > 0.002) || (wx_outplay && outvol <= 0.002))
	{
		wx_outplay = Weather_Loop(wx_out, wave, outvol, wx_outplay);
		wx_sentout = outvol;
	}
	if (fabs(invol - wx_sentin) >= 0.002 || (!wx_inplay && invol > 0.002) || (wx_inplay && invol <= 0.002))
	{
		wx_inplay = Weather_Loop(wx_in, wave, invol, wx_inplay);
		wx_sentin = invol;
	}
	wx_outvol = outvol; wx_invol = invol;
	if (wx_thunderat > 0)
	{
		if (time >= wx_thunderat)
		{
			wx_thunderat = 0; wx_thundercount = wx_thundercount + 1;
			if (vol > 0)
				sound(wx_thunder, CHAN_VOICE, "winter/thunder.ogg", bound(0, vol * (outside > 0.5 ? 3 : 1.4), 0.9), ATTN_NONE, 100, SOUNDFLAG_NOSPACIALISE);
		}
	}
};

float(string command) Weather_ConsoleCommand =
{
	if (strcmp(command, "weather_info")) return FALSE;
	print(sprintf("weather: %s ready %g pending %g sky %g ice %g\n", wx_map, wx_ready, wx_pending, wx_sky != world, wx_ice != world));
	print(sprintf("weather: audio %g tint %g outside %.2f\n", wx_audio, wx_tinted, wx_outside));
	print(sprintf("weather: burst %g flashes %g thunder %g remaining %g interval %gs loop %s\n", wx_burstid, wx_flashcount, wx_thundercount, wx_flashesleft, bound(5, cvar("r_weather_interval"), 900), wx_loopmode == 2 ? "rain" : "snow"));
	print("weather: r_weather_test 1 once / 2 repeat / 0 stops preview; r_weather_interval seconds; r_weather_loop snow|rain (audio only)\n");
	print("weather: r_weather 0 restores lighting (also r_colin_winter 0 on Colin)\n");
	return TRUE;
};
