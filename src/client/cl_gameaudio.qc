/* Local body Foley from the player's mounted CS:S content. No movement writes. */
float ga_valid, ga_next, ga_ground, ga_water, ga_stride, ga_stepat, ga_variant;
float ga_steps, ga_lands, ga_splashes, ga_swims, ga_calls;
float ga_css, ga_fall;
vector ga_pos, ga_vel;
string ga_last;

float(string path) GA_Exists =
{
	local float f;

	f = fopen(strcat("sound/", path), FILE_READ);
	if (f < 0) return FALSE;
	fclose(f);
	return TRUE;
};

void() GA_Assets =
{
	ga_css = GA_Exists("player/footsteps/concrete1.wav");
	ga_fall = GA_Exists("player/pl_fallpain1.wav");
};

void() GA_Register =
{
	registercvar("cl_game_sfx", "1", CVAR_ARCHIVE);
	registercommand("gameaudio_info");
	GA_Assets();
};

void(string path, float volume) GA_Play =
{
	if (!ga_css || cvar("cl_game_sfx") <= 0) return;
	// A partly mounted pack must not produce a missing-sound storm.
	if (!GA_Exists(path)) return;
	localsound(path, 0, bound(0, cvar("cl_game_sfx") * volume, 1));
	if (strcmp(ga_last, "")) strunzone(ga_last);
	ga_last = strzone(path);
	ga_calls = ga_calls + 1;
};

float(vector feet) GA_Water =
{
	local float c, level;

	c = pointcontents(feet + '0 0 2');
	if (c != CONTENT_WATER && c != CONTENT_SLIME && c != CONTENT_LAVA) return 0;
	level = 1;
	if (getstatf(STAT_FS_PMFLAGS) & PMF_DUCKED)
		c = pointcontents(feet + '0 0 22.5');
	else
		c = pointcontents(feet + '0 0 31');
	if (c == CONTENT_WATER || c == CONTENT_SLIME || c == CONTENT_LAVA) level = 2;
	return level;
};

string(vector feet) GA_Surface =
{
	local string s;

	// Texture families are a conservative fallback, not Source surfaceprops.
	s = "";
	traceline(feet + '0 0 4', feet - '0 0 12', TRUE, world);
	if (trace_surface_id > 0)
	if (checkbuiltin(getsurfacetexture))
		s = strtolower(getsurfacetexture(trace_ent, trace_surface_id - 1));
	if (strstrofs(s, "grate", 0) >= 0) return "metalgrate";
	if (strstrofs(s, "metal", 0) >= 0) return "metal";
	if (strstrofs(s, "wood", 0) >= 0) return "wood";
	if (strstrofs(s, "tile", 0) >= 0) return "tile";
	if (strstrofs(s, "grass", 0) >= 0) return "grass";
	if (strstrofs(s, "sand", 0) >= 0) return "sand";
	if (strstrofs(s, "dirt", 0) >= 0) return "dirt";
	if (strstrofs(s, "gravel", 0) >= 0) return "gravel";
	return "concrete";
};

void() GA_Frame =
{
	local vector feet, vel, delta;
	local float grounded, water, speed, swimspeed;
	local string material;

	if (cvar("cl_game_sfx") <= 0 || !LT_StatsAreMine() || rec_gh_on || rec_wt_on ||
	    getstatf(STAT_FS_SPEC) || rw_on || getstatf(STAT_FS_MOVETYPE) != MOVETYPE_WALK)
	{
		ga_valid = FALSE;
		ga_next = time;
		return;
	}
	if (time < ga_next) return;
	ga_next = time + 0.03;
	// Native simorg, not the camera: visual head duck must not lower the feet.
	feet = pmove_org;
	vel = [getstatf(STAT_FS_VELOCITY), getstatf(STAT_FS_VELOCITY + 1), getstatf(STAT_FS_VELOCITY + 2)];
	grounded = ((getstatf(STAT_FS_FLAGS) & FL_ONGROUND) != 0);
	water = GA_Water(feet);
	delta = feet - ga_pos;
	if (!ga_valid || vlen(delta) > 256)
	{
		ga_valid = TRUE;
		ga_stride = 0;
		ga_stepat = time;
		ga_ground = grounded;
		ga_water = water;
		ga_pos = feet;
		ga_vel = vel;
		return;
	}
	ga_variant = (ga_variant % 4) + 1;
	if ((water > 0) != (ga_water > 0))
	{
		GA_Play(sprintf("player/footsteps/wade%g.wav", ga_variant), 0.65);
		ga_splashes = ga_splashes + 1;
	}
	if (grounded && !ga_ground && ga_vel_z < -160 && !water)
	{
		if (ga_vel_z < -580 && ga_fall)
			GA_Play("player/pl_fallpain1.wav", 0.7);
		else
			GA_Play(sprintf("player/footsteps/%s%g.wav", GA_Surface(feet), ga_variant), 0.75);
		ga_lands = ga_lands + 1;
		ga_stepat = time + 0.15;
	}
	delta_z = 0;
	swimspeed = vlen(vel);
	vel_z = 0;
	speed = vlen(vel);
	if (water >= 2 && swimspeed > 30 && time >= ga_stepat)
	{
		GA_Play(sprintf("player/footsteps/wade%g.wav", ga_variant), 0.55);
		ga_swims = ga_swims + 1;
		ga_stepat = time + 0.65;
	}
	else if (grounded && speed > 30)
	{
		ga_stride = ga_stride + vlen(delta);
		if (ga_stride >= 86 && time >= ga_stepat)
		{
			material = water ? "slosh" : GA_Surface(feet);
			GA_Play(sprintf("player/footsteps/%s%g.wav", material, ga_variant), 0.6);
			ga_steps = ga_steps + 1;
			ga_stride = 0;
			ga_stepat = time + 0.18;
		}
	}
	else ga_stride = 0;
	ga_ground = grounded;
	ga_water = water;
	ga_pos = feet;
	ga_vel = [getstatf(STAT_FS_VELOCITY), getstatf(STAT_FS_VELOCITY + 1), getstatf(STAT_FS_VELOCITY + 2)];
};

float() GA_Command =
{
	if (strcmp(argv(0), "gameaudio_info")) return FALSE;
	if (!strcmp(argv(1), "refresh")) GA_Assets();
	print(sprintf("gameaudio: css %g shared-fall %g calls %g steps %g land %g water %g swim %g\n",
		ga_css, ga_fall, ga_calls, ga_steps, ga_lands, ga_splashes, ga_swims));
	print(sprintf("gameaudio: last '%s' active %g ground %g depth %g\n", ga_last, ga_valid, ga_ground, ga_water));
	return TRUE;
};
