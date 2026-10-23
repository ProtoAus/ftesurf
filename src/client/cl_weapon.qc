/* Opt-in mounted CSS presentation; server owns selection and map-target shots. */
entity wp_ent;
float wp_weapon, wp_sequence, wp_until, wp_animat, wp_ready, wp_shots, wp_duration;
float wp_eventat, wp_drawing, wp_events, wp_sndnext, wp_callbacks;
float wp_scriptbytes, wp_scriptalias, wp_scripthits;
string wp_model, wp_frame, wp_soundlast;
float wp_motionvalid, wp_motiontime, wp_bobtime;
float wp_mode, wp_burstleft, wp_burstat, wp_kick, wp_kickvel, wp_kickdt;
vector wp_facing, wp_motionbody, wp_motionorg, wp_motionang;
// Existing DPEF_NOGUNBOB: replace Quake weapon-matrix bob for this entity only.
#define WP_EF_NOGUNBOB 256i
string wp_sndname[16], wp_sndpath[16];

void() WP_Register =
{
	registercvar("cl_viewweapon", "0", CVAR_ARCHIVE);
	registercvar("cl_viewweapon_left", "0", CVAR_ARCHIVE);
	registercvar("cl_viewweapon_bob", "0.2", CVAR_ARCHIVE);
	registercvar("cl_viewweapon_sway", "0.2", CVAR_ARCHIVE);
	registercvar("cl_weapon_sfx", "1", CVAR_ARCHIVE);
	// Existing independent projection, not a scale hack or a change to world FOV.
	if (!strcmp(cvar_string("r_viewmodel_fov"), "")) cvar_set("r_viewmodel_fov", "75");
	registercommand("surf_weapon");
	registercommand("give"); // Native give may forward instead; SSQC handles the same aliases.
	registercommand("weapon_info");
	registercommand("knife"); registercommand("usp");
	registercommand("scout"); registercommand("glock");
};

string(float w) WP_Model =
{
	if (w == FS_WEAPON_KNIFE) return "models/weapons/v_knife_t.mdl";
	if (w == FS_WEAPON_USP) return "models/weapons/v_pist_usp.mdl";
	if (w == FS_WEAPON_SCOUT) return "models/weapons/v_snip_scout.mdl";
	if (w == FS_WEAPON_GLOCK) return "models/weapons/v_pist_glock18.mdl";
	return "";
};

string(float w) WP_Idle =
{
	if (w == FS_WEAPON_SCOUT) return "idle1";
	if (w == FS_WEAPON_GLOCK) return "glock_idle";
	if (w == FS_WEAPON_USP && !wp_mode) return "idle_unsil";
	return "idle";
};

float(string name, float oneshot) WP_Animate =
{
	local float f, duration;

	f = frameforname(wp_ent.modelindex, name);
	if (f < 0) f = frameforname(wp_ent.modelindex, strcat("@", name));
	if (f < 0)
	{
		wp_ready = FALSE;
		print(sprintf("weapon: unavailable animation '%s' in '%s'\n", name, wp_model));
		return FALSE;
	}
	wp_ent.frame = f;
	wp_ent.frame2 = f;
	wp_ent.lerpfrac = 0;
	wp_animat = time;
	wp_eventat = -0.001;
	wp_drawing = FALSE;
	duration = frameduration(wp_ent.modelindex, f);
	wp_duration = duration;
	wp_until = oneshot ? time + bound(0.08, duration, 4) : 0;
	if (strcmp(wp_frame, "")) strunzone(wp_frame);
	wp_frame = strzone(frametoname(wp_ent.modelindex, f));
	return TRUE;
};

// Resolve mounted Source sound-script names. Cache successes AND missing names.
string(string name) WP_SoundPath =
{
	local float i, f, count, k, depth, active, wave, p, n, comment;
	local string text, line, token, path;

	for (i = 0; i < 16; i = i + 1)
		if (!strcmp(wp_sndname[i], name)) return wp_sndpath[i];
	path = "";
	depth = 0;
	active = wave = FALSE;
	f = fopen("scripts/game_sounds_weapons.txt", FILE_READNL);
	if (f >= 0)
	{
		// Same blank-line-safe reader contract as Snds_ParseFile: READNL once.
		text = fgets(f);
		fclose(f);
		wp_scriptbytes = strlen(text);
		wp_scriptalias = strstrofs(text, name, 0); // exact-case diagnostic; never casefold the whole file
		wp_scripthits = 0;
		p = 0;
		for (i = 0; i < 40000; i = i + 1)
		{
			n = strstrofs(text, "\n", p);
			line = (n < 0) ? substring(text, p, -1) : substring(text, p, n - p);
			comment = strstrofs(line, "//", 0);
			if (comment >= 0) line = substring(line, 0, comment);
			count = tokenize(line);
			for (k = 0; k < count; k = k + 1)
			{
				token = argv(k);
				if (strlen(token) > 255) continue; // bounded names/paths, including on older clients
				if (!depth && !strcmp(strtolower(token), strtolower(name)))
				{
					active = TRUE;
					wp_scripthits = wp_scripthits + 1;
				}
				if (!strcmp(token, "{")) depth = depth + 1;
				else if (!strcmp(token, "}"))
				{
					depth = max(0, depth - 1);
					if (!depth) active = FALSE;
				}
				else if (active)
				{
					if (wave)
					{
						while (!strcmp(substring(token, 0, 1), "*") || !strcmp(substring(token, 0, 1), "#") || !strcmp(substring(token, 0, 1), "^"))
							token = substring(token, 1, -1);
						path = strzone(token);
						break;
					}
					wave = !strcmp(token, "wave");
				}
			}
			if (strcmp(path, "") || n < 0) break;
			p = n + 1;
		}
	}
	// Content-only CSS packs can have the WAV/model but no legacy sound script
	// (or a higher-priority game's script). Timing still comes from the MODEL.
	if (!strcmp(path, ""))
	{
		if (!strcmp(strtolower(name), "weapon_usp.slideback"))
			path = strzone("weapons/usp/usp_slideback.wav");
		if (!strcmp(strtolower(name), "weapon_glock.sliderelease"))
			path = strzone("weapons/glock/glock_sliderelease.wav");
		if (!strcmp(strtolower(name), "weapon_scout.bolt"))
			path = strzone("weapons/scout/scout_bolt.wav");
		if (!strcmp(strtolower(name), "weapon_usp.attachsilencer"))
			path = strzone("weapons/usp/usp_silencer_on.wav");
		if (!strcmp(strtolower(name), "weapon_usp.detachsilencer"))
			path = strzone("weapons/usp/usp_silencer_off.wav");
	}
	i = wp_sndnext;
	wp_sndnext = (wp_sndnext + 1) % 16;
	if (strcmp(wp_sndname[i], "")) strunzone(wp_sndname[i]);
	if (strcmp(wp_sndpath[i], "")) strunzone(wp_sndpath[i]);
	wp_sndname[i] = strzone(name);
	wp_sndpath[i] = path;
	return path;
};

void(float timestamp, int code, string data) WP_Event =
{
	local string path;

	wp_callbacks = wp_callbacks + 1;
	if (code != 5004i || !strcmp(data, "") || cvar("cl_weapon_sfx") <= 0) return;
	path = WP_SoundPath(data);
	if (!strcmp(path, "")) return;
	if (GA_Emit(path, cvar("cl_weapon_sfx") * 0.8))
	{
		wp_events = wp_events + 1;
		if (strcmp(wp_soundlast, "")) strunzone(wp_soundlast);
		wp_soundlast = strzone(data);
	}
};

// Exact critically damped update: a render-rate-independent, visual-only pulse.
void() WP_KickFrame =
{
	local float dt, decay, v;
	dt = max(0, frametime); wp_kickdt = dt;
	decay = pow(2.71828182846, -20 * dt);
	v = wp_kickvel + 20 * wp_kick;
	wp_kick = (wp_kick + v * dt) * decay;
	wp_kickvel = (wp_kickvel - 20 * v * dt) * decay;
};

void(float w, float alternate) WP_Bullet =
{
	local string snd;
	local vector src, fwd, right, up;
	local float reach;
	wp_shots = wp_shots + 1;
	if (w == FS_WEAPON_KNIFE) snd = (random() < 0.5) ? "weapons/knife/knife_slash1.wav" : "weapons/knife/knife_slash2.wav";
	else if (w == FS_WEAPON_USP) snd = wp_mode ? "weapons/usp/usp1.wav" : "weapons/usp/usp_unsil-1.wav";
	else if (w == FS_WEAPON_SCOUT) snd = "weapons/scout/scout_fire-1.wav";
	else snd = "weapons/glock/glock18-1.wav";
	if (w == FS_WEAPON_USP || w == FS_WEAPON_SCOUT) wp_kickvel = wp_kickvel - 108.73127; // two-degree peak
	else if (w == FS_WEAPON_GLOCK) wp_kickvel = wp_kickvel - 54.365635; // one degree per burst bullet too
	GA_Emit(snd, cvar("cl_weapon_sfx") * 0.8);
	if (w == FS_WEAPON_KNIFE && wp_mode)
	{
		// Server confirmed a PLAYER contact, not permission to harm them.
		snd = alternate ? "weapons/knife/knife_stab.wav" : sprintf("weapons/knife/knife_hit%g.wav", floor(random() * 4) + 1);
		GA_Emit(snd, cvar("cl_weapon_sfx") * 0.7);
		return;
	}
	// Unpunched aim is read only; this is cosmetic wall feedback, not authority.
	reach = (w == FS_WEAPON_KNIFE) ? (alternate ? 64 : 80) : 8192;
	src = pmove_org + [0, 0, getstatf(STAT_VIEWHEIGHT)];
	fwd = v_forward; right = v_right; up = v_up;
	makevectors(getproperty(VF_ANGLES));
	traceline(src, src + v_forward * reach, TRUE, world);
	v_forward = fwd; v_right = right; v_up = up;
	if (trace_fraction < 1)
	{
		if (w == FS_WEAPON_KNIFE) GA_Emit("weapons/knife/knife_hitwall1.wav", cvar("cl_weapon_sfx") * 0.6);
		else GA_Emit("physics/concrete/concrete_impact_bullet1.wav", cvar("cl_weapon_sfx") * 0.4);
	}
};

void(float w, float kind) WP_Shot =
{
	if (w == FS_WEAPON_KNIFE) WP_Animate((kind == FS_WEV_ALT) ? "stab_miss" : ((wp_shots % 2) ? "midslash2" : "midslash1"), TRUE);
	else if (w == FS_WEAPON_USP) WP_Animate(wp_mode ? "shoot1" : "shoot1_unsil", TRUE);
	else if (w == FS_WEAPON_SCOUT) WP_Animate("shoot", TRUE);
	else WP_Animate((kind == FS_WEV_BURST) ? "glock_fireburst1" : "glock_firesingle", TRUE);
	WP_Bullet(w, kind == FS_WEV_ALT);
	if (kind == FS_WEV_BURST)
	{
		wp_burstleft = 2;
		wp_burstat = cltime + 0.06;
	}
};

// Public Source SDK bob/facing-lag maths, confined to the render-only model.
void() WP_Motion =
{
	local float dt, speed, vbob, lbob, alpha, amount;
	local vector fwd, right, up, ofwd, oright, oup, delta, lag;
	ofwd = v_forward; oright = v_right; oup = v_up;
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward; right = v_right; up = v_up;
	v_forward = ofwd; v_right = oright; v_up = oup;
	dt = cltime - wp_motiontime;
	if (!wp_motionvalid || dt < 0 || dt > 0.1 || vlen(pmove_org - wp_motionbody) > 128)
	{
		wp_motionvalid = TRUE;
		wp_facing = fwd;
		wp_bobtime = 0;
		wp_motionorg = '0 0 0'; wp_motionang = '0 0 0';
	}
	else if (dt > 0)
	{
		speed = bound(0, vlen([pmove_vel_x, pmove_vel_y, 0]), 320);
		wp_bobtime = wp_bobtime + dt * speed / 320;
		wp_bobtime = wp_bobtime - floor(wp_bobtime / 0.9) * 0.9;
		vbob = speed * 0.005 * bound(0, cvar("cl_viewweapon_bob"), 1) * (0.3 + 0.7 * sin(wp_bobtime * 6.2831853 / 0.45));
		lbob = speed * 0.005 * bound(0, cvar("cl_viewweapon_bob"), 1) * (0.3 + 0.7 * sin(wp_bobtime * 6.2831853 / 0.9));
		delta = fwd - wp_facing;
		amount = 5;
		if (vlen(delta) > 1.5) amount = amount * vlen(delta) / 1.5;
		alpha = 1 - pow(2.7182818, -amount * dt);
		wp_facing = normalize(wp_facing + delta * alpha);
		lag = (fwd - wp_facing) * -5;
		if (vlen(lag) > 3) lag = normalize(lag) * 3;
		lag = lag * bound(0, cvar("cl_viewweapon_sway"), 1);
		wp_motionorg = [lag * fwd, -(lag * right), lag * up];
		wp_motionorg_x = wp_motionorg_x + vbob * 0.1 + vbob * 0.1 * fwd_z;
		wp_motionorg_y = wp_motionorg_y - lbob * 0.8 - vbob * 0.1 * right_z;
		wp_motionorg_z = wp_motionorg_z + vbob * 0.1 * up_z;
		// Alias pitch is inverted by the engine's r_meshpitch.
		wp_motionang = [vbob * 0.4, -lbob * 0.3, vbob * 0.5];
	}
	wp_motiontime = cltime;
	wp_motionbody = pmove_org;
	wp_ent.origin = wp_motionorg;
	wp_ent.angles = wp_motionang;
};

void() WP_Frame =
{
	local float w, seq, kind;
	local string mdl;
	local int i;

	w = getstatf(STAT_ACTIVEWEAPON);
	seq = getstatf(STAT_WEAPONFRAME);
	mdl = WP_Model(w);
	if (!strcmp(mdl, "") || cvar("cl_viewweapon") <= 0 || !LT_StatsAreMine() || rec_gh_on || rec_wt_on ||
	    getstatf(STAT_FS_SPEC) || rw_on || getstatf(STAT_FS_MOVETYPE) != MOVETYPE_WALK)
	{
		wp_weapon = 0;
		wp_ready = FALSE;
		wp_drawing = FALSE;
		wp_motionvalid = FALSE;
		wp_kick = wp_kickvel = wp_burstleft = 0;
		wp_sequence = seq;
		return;
	}
	if (!wp_ent) wp_ent = spawn();
	if (w != wp_weapon)
	{
		wp_weapon = w;
		wp_motionvalid = FALSE;
		wp_mode = floor(seq / 4) % 2;
		wp_kick = wp_kickvel = wp_burstleft = 0;
		wp_sequence = seq;
		wp_ready = FALSE;
		if (strcmp(wp_model, "")) strunzone(wp_model);
		wp_model = strzone(mdl);
		setmodel(wp_ent, wp_model);
		if (wp_ent.modelindex == 0) return; // CSQC's private model slots are NEGATIVE.
		wp_ready = WP_Animate((w == FS_WEAPON_GLOCK) ? "glock_draw" : ((w == FS_WEAPON_USP && !wp_mode) ? "draw_unsil" : "draw"), TRUE);
		wp_drawing = wp_ready;
	}
	if (!wp_ready) return;
	WP_KickFrame();
	if (seq != wp_sequence)
	{
		wp_sequence = seq;
		wp_mode = floor(seq / 4) % 2;
		kind = seq % 4;
		if (kind == FS_WEV_MODE)
		{
			if (w == FS_WEAPON_USP) WP_Animate(wp_mode ? "add_silencer" : "detach_silencer", TRUE);
			else print(wp_mode ? "Glock: burst fire\n" : "Glock: single fire\n");
		}
		else WP_Shot(w, kind);
	}
	for (i = 0i; i < 2i && wp_burstleft > 0; i += 1i)
	{
		if (cltime < wp_burstat) break;
		WP_Bullet(w, FALSE);
		wp_burstleft = wp_burstleft - 1;
		wp_burstat = wp_burstat + 0.06;
	}
	if (wp_until > 0)
	if (checkbuiltin(processmodelevents))
		processmodelevents(wp_ent.modelindex, wp_ent.frame, wp_eventat, time - wp_animat, WP_Event);
	if (wp_until > 0 && time >= wp_until) wp_ready = WP_Animate(WP_Idle(w), FALSE);
	wp_ent.origin = '0 0 0';
	wp_ent.angles = '0 0 0';
	wp_ent.effects = WP_EF_NOGUNBOB;
	WP_Motion();
	wp_ent.colormod = '1 1 1';
	wp_ent.alpha = 1;
	wp_ent.scale = 1;
	wp_ent.renderflags = RF_VIEWMODEL | RF_DEPTHHACK | RF_NOSHADOW;
	// CSS guns are left-authored; the knife is right-authored.
	if (w == FS_WEAPON_KNIFE)
	{
		if (cvar("cl_viewweapon_left")) wp_ent.renderflags |= RF_XFLIP;
	}
	else if (!cvar("cl_viewweapon_left")) wp_ent.renderflags |= RF_XFLIP;
	wp_ent.frame1time = max(0, time - wp_animat);
	// Raw MDL animation flags do not carry the sequence's idle-loop flag.
	if (wp_until <= 0 && wp_duration > 0)
		wp_ent.frame1time = wp_ent.frame1time - floor(wp_ent.frame1time / wp_duration) * wp_duration;
	wp_ent.frame2time = wp_ent.frame1time;
	addentity(wp_ent);
};

float() WP_Command =
{
	local string cmd, arg, eventname, resolved;
	local float w, giving, f, eventframe, timestamp;
	local int code, i;
	local int *header;

	cmd = argv(0);
	if (!strcmp(cmd, "weapon_info"))
	{
		if (!strcmp(argv(1), "refresh")) wp_weapon = 0;
		if (!strcmp(argv(1), "events") && wp_ready)
		{
			f = fopen(wp_model, FILE_READ);
			if (f >= 0)
			{
				header = memalloc(196i);
				if (fread(f, header, 196) == 196)
					print(sprintf("weapon: MDL version %g sequences %g offset %g bytes %g\n", (float)header[1i], (float)header[47i], (float)header[48i], (float)header[19i]));
				memfree(header);
				fclose(f);
			}
			print(sprintf("weapon: event API %g indexed API %g\n", checkbuiltin(processmodelevents), checkbuiltin(getmodeleventidx)));
			eventframe = frameforname(wp_ent.modelindex, (wp_weapon == FS_WEAPON_GLOCK) ? "@glock_draw" : "@draw");
			if (checkbuiltin(getmodeleventidx))
			for (i = 0i; i < 16i; i += 1i)
			{
				if (!getmodeleventidx(wp_ent.modelindex, eventframe, i, timestamp, code, eventname)) break;
				print(sprintf("weapon: event %g time %g code %g '%s'\n", (float)i, timestamp, (float)code, eventname));
				resolved = WP_SoundPath(eventname);
				print(sprintf("weapon: resolved '%s' present %g\n", resolved, GA_Exists(resolved)));
			}
			print(sprintf("weapon: sound-script bytes %g exact-name-offset %g definition-hits %g\n", wp_scriptbytes, wp_scriptalias, wp_scripthits));
		}
		print(sprintf("weapon: type %g sequence %g ready %g shots %g model '%s'\n", wp_weapon, wp_sequence, wp_ready, wp_shots, wp_ready ? wp_model : ""));
		if (wp_ready)
		{
			print(sprintf("weapon: frame '%s' duration %g time %g\n", wp_frame, frameduration(wp_ent.modelindex, wp_ent.frame), wp_ent.frame1time));
			print(sprintf("weapon: pose-time %g age %g bob %g sway %g\n", wp_ent.frame1time, time - wp_animat, cvar("cl_viewweapon_bob"), cvar("cl_viewweapon_sway")));
		}
		print(sprintf("weapon: enabled %g sfx %g fov %g event-sounds %g callbacks %g last '%s'\n", cvar("cl_viewweapon"), cvar("cl_weapon_sfx"), cvar("r_viewmodel_fov"), wp_events, wp_callbacks, wp_soundlast));
		print(sprintf("weapon: motion valid %g offset %v angles %v\n", wp_motionvalid, wp_motionorg, wp_motionang));
		print(sprintf("weapon: mode %g burst-pending %g kick %g velocity %g render-dt %g\n", wp_mode, wp_burstleft, wp_kick, wp_kickvel, wp_kickdt));
		print(sprintf("weapon: view %v render-angles %v input-angles %v\n", getproperty(VF_ORIGIN), getproperty(VF_ANGLES), getproperty(VF_CL_VIEWANGLES)));
		return TRUE;
	}
	giving = !strcmp(cmd, "give");
	if (!strcmp(cmd, "knife") || !strcmp(cmd, "usp") || !strcmp(cmd, "scout") || !strcmp(cmd, "glock"))
	{
		if (strcmp(argv(1), "")) return TRUE;
		arg = cmd;
	}
	else
	{
		if (strcmp(cmd, "surf_weapon") && !giving) return FALSE;
		arg = strtolower(argv(1));
	}
	if (!strcmp(substring(arg, 0, 7), "weapon_")) arg = substring(arg, 7, -1);
	w = 0;
	if (!strcmp(arg, "knife")) w = FS_WEAPON_KNIFE;
	if (!strcmp(arg, "usp")) w = FS_WEAPON_USP;
	if (!strcmp(arg, "scout")) w = FS_WEAPON_SCOUT;
	if (!strcmp(arg, "glock")) w = FS_WEAPON_GLOCK;
	if (!giving)
	{
		if (!strcmp(arg, "1")) w = FS_WEAPON_KNIFE;
		if (!strcmp(arg, "2")) w = FS_WEAPON_USP;
		if (!strcmp(arg, "4")) w = FS_WEAPON_SCOUT;
		if (!strcmp(arg, "8")) w = FS_WEAPON_GLOCK;
	}
	if (!w || strcmp(argv(2), ""))
	{
		if (giving) return FALSE;
		print("surf_weapon knife|usp|scout|glock (or give weapon_glock / give scout)\n");
		return TRUE;
	}
	cvar_set("cl_viewweapon", "1");
	localcmd(sprintf("cmd weapon %g\n", w));
	return TRUE;
};
