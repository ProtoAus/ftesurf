/* Opt-in local CSS movement Foley. No movement or recording writes. */
float ga_valid, ga_next, ga_ground, ga_water, ga_stride, ga_stepat, ga_variant;
float ga_steps, ga_lands, ga_splashes, ga_swims, ga_calls, ga_jumps;
float ga_css, ga_fall, ga_jumpseq, ga_volume, ga_speed, ga_walking;
vector ga_pos, ga_vel;
string ga_last;
float ga_footvariant, ga_footat, ga_merged;
int ga_pickhistory;
void() GM_Clear;
void() GM_Info;
void(string texture) GM_Inspect;
string(vector org, float step) GM_Sound;

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
	GM_Clear();
	ga_footvariant = 0;
	ga_css = GA_Exists("player/footsteps/concrete1.wav");
	// CSS Player.FallDamage (game_sounds.txt), not HL2's pl_fallpain.
	ga_fall = (GA_Exists("player/damage1.wav") && GA_Exists("player/damage2.wav") && GA_Exists("player/damage3.wav"));
};

void() GA_Register =
{
	registercvar("cl_game_sfx", "0", CVAR_ARCHIVE);
	registercommand("gameaudio_info");
	registercommand("gameaudio_material");
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
	// Shipped walk cap is 260 * 0.52 = 135.2; allow 0.05 for float noise.
	if (speed <= 135.25) return 0;
	return 0.2 + 0.4 * bound(0, (speed - 135.25) / 114.75, 1);
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

float(vector feet, float water, float volume) GA_Foot =
{
	local float emitted;
	local int pick;
	if (!ga_css || volume <= 0 || cvar("cl_game_sfx") <= 0) return FALSE;
	// Coalesce a step/landing followed immediately by the jump-contact edge.
	if (time - ga_footat < 0.12) { ga_merged = ga_merged + 1; return FALSE; }
	pick = (int)(ga_footvariant % 2);
	if (random() < 0.5) pick += 2i;
	if (water) emitted = GA_Play(sprintf("player/footsteps/slosh%g.wav", ga_variant), volume);
	else emitted = GA_Play(GM_Sound(feet, (float)pick), volume);
	if (emitted)
	{
		ga_footvariant = (ga_footvariant + 1) % 2;
		ga_pickhistory = ((ga_pickhistory << 2i) | pick) & 65535i;
		ga_footat = time;
	}
	return emitted;
};

void() GA_InputFrame =
{
	// Read only: walk intent also stays quiet during steering velocity overshoot.
	ga_walking = ((input_buttons & BTN_SPEED) != 0);
};

void() GA_Frame =
{
	local vector feet, vel, delta;
	local float grounded, water, speed, swimspeed, jumpseq, jumped, volume, ducked;

	if (cvar("cl_game_sfx") <= 0 || !LT_StatsAreMine() || rec_gh_on || rec_wt_on ||
	    getstatf(STAT_FS_SPEC) || rw_on || getstatf(STAT_FS_MOVETYPE) != MOVETYPE_WALK)
	{
		ga_valid = FALSE;
		ga_footat = time - 1;
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
		ga_footat = time - 1;
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
	volume = (ducked || ga_walking) ? 0 : GA_StepVolume(speed);
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
			if (GA_Play(sprintf("player/damage%g.wav", floor(random() * 3) + 1), 0.7)) ga_lands = ga_lands + 1;
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
	if (!strcmp(argv(0), "gameaudio_material"))
	{
		GM_Inspect(argv(1));
		return TRUE;
	}
	if (strcmp(argv(0), "gameaudio_info")) return FALSE;
	if (!strcmp(argv(1), "refresh")) GA_Assets();
	if (!strcmp(argv(1), "fall")) GA_Play(sprintf("player/damage%g.wav", floor(random() * 3) + 1), 0.7);
	print(sprintf("gameaudio: css %g css-fall %g calls %g steps %g land %g water %g swim %g\n",
		ga_css, ga_fall, ga_calls, ga_steps, ga_lands, ga_splashes, ga_swims));
	print(sprintf("gameaudio: last '%s' active %g ground %g depth %g\n", ga_last, ga_valid, ga_ground, ga_water));
	print(sprintf("gameaudio: speed %g volume %g hop-cues %g contact-seq %g\n", ga_speed, ga_volume, ga_jumps, ga_jumpseq));
	print(sprintf("gameaudio: merged %g picks(last8,2bits) %04lx\n", ga_merged, ga_pickhistory));
	GM_Info();
	return TRUE;
};
