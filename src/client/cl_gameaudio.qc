/* Opt-in local CSS movement Foley. No movement or recording writes. */
float ga_valid, ga_next, ga_ground, ga_water, ga_stride, ga_stepat, ga_variant;
float ga_steps, ga_lands, ga_splashes, ga_swims, ga_calls, ga_jumps;
float ga_css, ga_fall, ga_jumpseq, ga_volume, ga_speed;
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
	registercvar("cl_game_sfx", "0", CVAR_ARCHIVE);
	registercommand("gameaudio_info");
	GA_Assets();
};

// Shared safe emitter; weapons have their OWN opt-in/volume, not the feet gate.
float(string path, float volume) GA_Emit =
{
	if (volume <= 0) return FALSE;
	if (!GA_Exists(path)) return FALSE;
	localsound(path, 0, bound(0, volume, 1));
	if (strcmp(ga_last, "")) strunzone(ga_last);
	ga_last = strzone(path);
	ga_volume = bound(0, volume, 1);
	ga_calls = ga_calls + 1;
	return TRUE;
};

float(string path, float volume) GA_Play =
{
	if (!ga_css || cvar("cl_game_sfx") <= 0) return FALSE;
	return GA_Emit(path, cvar("cl_game_sfx") * volume);
};

float(float speed) GA_StepVolume =
{
	if (speed <= 135) return 0;
	return 0.2 + 0.4 * bound(0, (speed - 135) / 115, 1);
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

float(vector feet, float water, float volume) GA_Foot =
{
	local string material;

	material = water ? "slosh" : GA_Surface(feet);
	return GA_Play(sprintf("player/footsteps/%s%g.wav", material, ga_variant), volume);
};

void() GA_Frame =
{
	local vector feet, vel, delta;
	local float grounded, water, speed, swimspeed, jumpseq, jumped, volume, ducked;

	if (cvar("cl_game_sfx") <= 0 || !LT_StatsAreMine() || rec_gh_on || rec_wt_on ||
	    getstatf(STAT_FS_SPEC) || rw_on || getstatf(STAT_FS_MOVETYPE) != MOVETYPE_WALK)
	{
		ga_valid = FALSE;
		ga_next = time;
		return;
	}
	if (time < ga_next) return;
	ga_next = time + 0.03;
	feet = pmove_org;
	vel = [getstatf(STAT_FS_VELOCITY), getstatf(STAT_FS_VELOCITY + 1), getstatf(STAT_FS_VELOCITY + 2)];
	grounded = ((getstatf(STAT_FS_FLAGS) & FL_ONGROUND) != 0);
	ducked = ((getstatf(STAT_FS_PMFLAGS) & PMF_DUCKED) != 0);
	jumpseq = getstatf(STAT_FS_FOLEYJUMP);
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
		ga_jumpseq = jumpseq;
		return;
	}
	ga_variant = (ga_variant % 4) + 1;
	jumped = (jumpseq != ga_jumpseq);
	swimspeed = vlen(vel);
	vel_z = 0;
	speed = vlen(vel);
	ga_speed = speed;
	volume = ducked ? 0 : GA_StepVolume(speed);
	if ((water > 0) != (ga_water > 0))
	{
		if (GA_Play(sprintf("player/footsteps/wade%g.wav", ga_variant), 0.65))
			ga_splashes = ga_splashes + 1;
	}
	// Jump contact is not walking: even a standing/crouch jump has a cue.
	// The authoritative edge survives a land+jump between render samples.
	if (jumped && water < 2)
	{
		if (GA_Foot(feet, water, 0.35 + 0.25 * bound(0, speed / 250, 1))) ga_jumps = ga_jumps + 1;
		ga_stride = 0;
		ga_stepat = time + 0.18;
	}
	else if (grounded && !ga_ground && ga_vel_z < -160 && !water)
	{
		if (ga_vel_z < -580 && ga_fall)
		{
			if (GA_Play("player/pl_fallpain1.wav", 0.7)) ga_lands = ga_lands + 1;
		}
		else if (GA_Foot(feet, water, volume)) ga_lands = ga_lands + 1;
		ga_stepat = time + 0.15;
	}
	delta_z = 0;
	if (water >= 2 && swimspeed > 30 && time >= ga_stepat)
	{
		if (GA_Play(sprintf("player/footsteps/wade%g.wav", ga_variant), 0.55))
			ga_swims = ga_swims + 1;
		ga_stepat = time + 0.65;
	}
	else if (grounded && volume > 0)
	{
		ga_stride = ga_stride + vlen(delta);
		if (ga_stride >= 86 && time >= ga_stepat)
		{
			if (GA_Foot(feet, water, volume)) ga_steps = ga_steps + 1;
			ga_stride = 0;
			ga_stepat = time + 0.18;
		}
	}
	else ga_stride = 0;
	ga_ground = grounded;
	ga_water = water;
	ga_pos = feet;
	ga_vel = [getstatf(STAT_FS_VELOCITY), getstatf(STAT_FS_VELOCITY + 1), getstatf(STAT_FS_VELOCITY + 2)];
	ga_jumpseq = jumpseq;
};

float() GA_Command =
{
	if (strcmp(argv(0), "gameaudio_info")) return FALSE;
	if (!strcmp(argv(1), "refresh")) GA_Assets();
	print(sprintf("gameaudio: css %g shared-fall %g calls %g steps %g land %g water %g swim %g\n",
		ga_css, ga_fall, ga_calls, ga_steps, ga_lands, ga_splashes, ga_swims));
	print(sprintf("gameaudio: last '%s' active %g ground %g depth %g\n", ga_last, ga_valid, ga_ground, ga_water));
	print(sprintf("gameaudio: speed %g volume %g hop-cues %g contact-seq %g\n", ga_speed, ga_volume, ga_jumps, ga_jumpseq));
	return TRUE;
};
