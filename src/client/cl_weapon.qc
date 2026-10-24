/* Opt-in mounted CSS presentation; server owns selection and map-target shots. */
entity wp_ent;
void() WPU_Apply; // cl_weaponui.qc, before the model is submitted
float wp_weapon, wp_sequence, wp_until, wp_animat, wp_ready, wp_shots, wp_duration;
float wp_eventat, wp_drawing, wp_events, wp_sndnext, wp_callbacks;
float wp_scriptbytes, wp_scriptalias, wp_scripthits;
string wp_model, wp_frame, wp_soundlast;
float wp_motionvalid, wp_motiontime, wp_bobtime, wp_mountnext;
float wp_mode, wp_burstleft, wp_burstat, wp_kick, wp_kickvel, wp_kickdt;
float wp_zoom, wp_scopepending, wp_rezoomat, wp_drawstarts;
entity wp_flashent;
float wp_flashuntil, wp_flashroll, wp_flashes, wp_muzzletag, wp_flashshot;
vector wp_muzzleorg;
vector wp_facing, wp_motionbody, wp_motionorg, wp_motionang;
// Existing DPEF_NOGUNBOB: replace Quake weapon-matrix bob for this entity only.
#define WP_EF_NOGUNBOB 256i
string wp_sndname[16], wp_sndpath[16];

void(float kind) WP_MountKnifeContent;

float wp_vmserial, wp_wasmirror, wp_ownzoom, wp_restorezoom;
void() WP_Inspect;
float() WP_LocalZoom = { return wp_zoom; };

void() WP_Register =
{
	KCAT_Register();
	registercvar("cl_viewweapon", "0", CVAR_ARCHIVE);
	registercvar("cl_viewweapon_left", "0", CVAR_ARCHIVE);
	registercvar("cl_viewweapon_bob", "0.2", CVAR_ARCHIVE);
	registercvar("cl_viewweapon_sway", "0.2", CVAR_ARCHIVE);
	registercvar("cl_weapon_sfx", "1", CVAR_ARCHIVE);
	registercvar("cl_weapon_muzzleflash", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_model", "0", CVAR_ARCHIVE);
	registercommand("butterfly"); registercommand("m9"); registercommand("knife_css"); registercommand("inspect");
	registercommand("knife_mount_done");
	// Existing independent projection, not a scale hack or a change to world FOV.
	if (!strcmp(cvar_string("r_viewmodel_fov"), "")) cvar_set("r_viewmodel_fov", "75");
	registercommand("surf_weapon");
	registercommand("give"); // Native give may forward instead; SSQC handles the same aliases.
	registercommand("weapon_info");
	registercommand("drop");
	registercommand("knife"); registercommand("usp");
	registercommand("scout"); registercommand("glock");
};

string(float w) WP_Model =
{
	if (w == FS_WEAPON_KNIFE)
	{
		return KCAT_Get(KCAT_Knife(), KCAT_MODEL);
	}
	if (w == FS_WEAPON_USP) return "models/weapons/v_pist_usp.mdl";
	if (w == FS_WEAPON_SCOUT) return "models/weapons/v_snip_scout.mdl";
	if (w == FS_WEAPON_GLOCK) return "models/weapons/v_pist_glock18.mdl";
	return "";
};

string(float w) WP_Idle =
{
	if (w == FS_WEAPON_SCOUT) return "idle1";
	if (w == FS_WEAPON_KNIFE && KCAT_Knife() > 0) return KCAT_Get(KCAT_Knife(), KCAT_IDLE);
	if (w == FS_WEAPON_GLOCK) return "glock_idle";
	if (w == FS_WEAPON_USP && !wp_mode) return "idle_unsil";
	return "idle";
};

float(string name, float oneshot) WP_Animate =
{
	local float f, duration;
	local string candidate;

	f = frameforname(wp_ent.modelindex, name);
	if (f < 0) f = frameforname(wp_ent.modelindex, strcat("@", name));
	if (f < 0 && wp_weapon == FS_WEAPON_KNIFE && KCAT_Knife() > 0)
	{
		candidate = "";
		if (!strcmp(name, "draw")) candidate = KCAT_Get(KCAT_Knife(), KCAT_DRAW);
		if (strstrofs(name, "light_miss", 0) == 0) candidate = KCAT_Get(KCAT_Knife(), KCAT_LIGHT);
		if (strstrofs(name, "heavy_miss", 0) == 0) candidate = KCAT_Get(KCAT_Knife(), KCAT_HEAVY);
		if (strstrofs(name, "light_hit", 0) == 0) candidate = KCAT_Get(KCAT_Knife(), KCAT_LIGHTHIT);
		if (strstrofs(name, "heavy_hit", 0) == 0) candidate = KCAT_Get(KCAT_Knife(), KCAT_HEAVYHIT);
		if (strcmp(candidate, ""))
		{
			name = candidate;
			f = frameforname(wp_ent.modelindex, name);
			if (f < 0) f = frameforname(wp_ent.modelindex, strcat("@", name));
		}
	}
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

// Knife aliases come from the active CS:GO package, never by raising its VFS
// priority above CSS's shared models/materials. Caller owns the zoned result.
string() WP_WeaponScript =
{
	local float f, h, i, n;
	local int bytes;
	local void *buffer;
	local string text, package;
	f = -1;
	if (wp_weapon == FS_WEAPON_KNIFE && KCAT_Knife() > 0)
	if (checkbuiltin(GM_SearchPackage))
	if (checkbuiltin(GM_SearchOpen))
	{
		h = search_begin("scripts/game_sounds_weapons.txt", 6, TRUE);
		if (h >= 0)
		{
			n = bound(0, search_getsize(h), 64);
			for (i = 0; i < n; i = i + 1)
			{
				package = strtolower(GM_SearchPackage(h, i));
				if (strstrofs(package, "csgo", 0) < 0) continue;
				f = GM_SearchOpen(h, i);
				if (f >= 0) break;
			}
			search_end(h);
		}
	}
	if (f >= 0)
	{
		bytes = fsize(f);
		text = "";
		if (bytes > 0i && bytes <= 2097152i)
		{
			buffer = memalloc(bytes + 1i);
			memfill8(buffer, 0i, bytes + 1i);
			if (fread(f, buffer, bytes) == bytes) text = strzone((string)buffer);
			memfree(buffer);
		}
		fclose(f);
		return text;
	}
	f = fopen("scripts/game_sounds_weapons.txt", FILE_READNL);
	if (f < 0) return "";
	text = strzone(fgets(f));
	fclose(f);
	return text;
};

// Resolve mounted Source sound-script names. Cache successes AND missing names.
string(string name) WP_SoundPath =
{
	local float i, count, k, depth, active, wave, p, n, comment;
	local string text, line, token, path;

	for (i = 0; i < 16; i = i + 1)
		if (!strcmp(wp_sndname[i], name)) return wp_sndpath[i];
	path = "";
	depth = 0;
	active = wave = FALSE;
	text = WP_WeaponScript();
	if (strcmp(text, ""))
	{
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
						while (!strcmp(substring(token, 0, 1), "*") || !strcmp(substring(token, 0, 1), "#") || !strcmp(substring(token, 0, 1), "^") || !strcmp(substring(token, 0, 1), "~") || !strcmp(substring(token, 0, 1), ")"))
							token = substring(token, 1, -1);
						path = strzone(strreplace("\\", "/", token));
						break;
					}
					wave = !strcmp(token, "wave");
				}
			}
			if (strcmp(path, "") || n < 0) break;
			p = n + 1;
		}
	}
	if (strcmp(text, "")) strunzone(text);
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

// Attachment #1 is CSS's authored muzzle. Read its bone + local position;
// adding a fake bone would change the mesh's pose stride. Never mutate the rig.
void() WP_LoadMuzzle =
{
	local filestream f;
	local int *header;
	local int length, bones, offset;
	local vector pos;
	wp_muzzletag = 0; wp_muzzleorg = '0 0 0';
	if (wp_weapon == FS_WEAPON_KNIFE) return;
	f = fopen(wp_model, FILE_READ);
	if (f < 0) return;
	length = fsize(f);
	header = (int*)memalloc(248i);
	if (length >= 248i && length <= 16777216i)
	if (fread(f, header, 248i) == 248i)
	{
		bones = header[39i]; offset = header[61i];
		if (header[0i] == 0x54534449i && header[1i] >= 44i && header[1i] <= 49i && bones > 0i && bones <= 256i &&
			header[60i] > 0i && header[60i] <= 64i && offset >= 248i && offset <= length - 92i)
		{
			fseek(f, offset);
			if (fread(f, header, 92i) == 92i)
			{
				pos = [((float*)header)[6i], ((float*)header)[10i], ((float*)header)[14i]];
				if (header[2i] >= 0i && header[2i] < bones && fabs(pos_x) <= 4096 && fabs(pos_y) <= 4096 && fabs(pos_z) <= 4096)
				{
					wp_muzzletag = (float)(header[2i] + 1i);
					wp_muzzleorg = pos;
				}
			}
		}
	}
	fclose(f);
	memfree((void*)header);
};

void() WP_Muzzle =
{
	if (wp_muzzletag <= 0 || VM_Cvar("cl_weapon_muzzleflash") <= 0) return;
	if (wp_weapon == FS_WEAPON_USP && wp_mode) return;
	if (wp_flashshot == wp_shots) return;
	wp_flashshot = wp_shots;
	wp_flashuntil = cltime + 0.04;
	wp_flashroll = random() * 360;
	wp_flashes = wp_flashes + 1;
};

void() WP_FlashFrame =
{
	local vector pos, right, forward, up;
	if (cltime >= wp_flashuntil || wp_muzzletag <= 0) return;
	if (!wp_flashent)
	{
		wp_flashent = spawn();
		precache_model("models/ftesurf/muzzle.md3");
		setmodel(wp_flashent, "models/ftesurf/muzzle.md3");
		wp_flashent.forceshader = shaderforname("ftesurf/muzzleflash", "{\nprogram default2d\nsort additive\ncull none\n{ map materials/effects/muzzleflash4.vtf\nblendfunc add\nrgbgen entity\nalphagen entity\n}\n}\n");
	}
	forward = v_forward; right = v_right; up = v_up;
	makevectors(wp_ent.angles);
	pos = v_right; // reflect about the animated entity's own side axis
	wp_flashent.origin = gettaginfo(wp_ent, wp_muzzletag);
	wp_flashent.origin = wp_flashent.origin + v_forward * wp_muzzleorg_x - v_right * wp_muzzleorg_y + v_up * wp_muzzleorg_z;
	if ((int)wp_ent.renderflags & RF_XFLIP)
		wp_flashent.origin = wp_flashent.origin - 2 * ((wp_flashent.origin - wp_ent.origin) * pos) * pos;
	v_forward = forward; v_right = right; v_up = up;
	wp_flashent.angles = [0, 0, wp_flashroll];
	wp_flashent.renderflags = RF_VIEWMODEL | RF_DEPTHHACK | RF_NOSHADOW;
	wp_flashent.effects = WP_EF_NOGUNBOB;
	wp_flashent.scale = 1.75;
	wp_flashent.alpha = bound(0, (wp_flashuntil - cltime) / 0.04, 1);
	wp_flashent.colormod = '1 1 1';
	addentity(wp_flashent);
};

void(float timestamp, int code, string data) WP_Event =
{
	local string path;

	wp_callbacks = wp_callbacks + 1;
	if (code == 5001i) { WP_Muzzle(); return; }
	if (code != 5004i || !strcmp(data, "") || VM_Cvar("cl_weapon_sfx") <= 0) return;
	path = WP_SoundPath(data);
	if (!strcmp(path, "")) return;
	if (GA_Emit(path, VM_Cvar("cl_weapon_sfx") * 0.8))
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
	WP_Muzzle(); // CSS game code flashes on a confirmed bullet, not a clip event.
	if (w == FS_WEAPON_KNIFE) snd = (random() < 0.5) ? "weapons/knife/knife_slash1.wav" : "weapons/knife/knife_slash2.wav";
	else if (w == FS_WEAPON_USP) snd = wp_mode ? "weapons/usp/usp1.wav" : "weapons/usp/usp_unsil-1.wav";
	else if (w == FS_WEAPON_SCOUT) snd = "weapons/scout/scout_fire-1.wav";
	else snd = "weapons/glock/glock18-1.wav";
	if (w == FS_WEAPON_USP || w == FS_WEAPON_SCOUT) wp_kickvel = wp_kickvel - 108.73127; // two-degree peak
	else if (w == FS_WEAPON_GLOCK && wp_mode) wp_kickvel = wp_kickvel - 54.365635; // burst only; CSS single has no view punch
	GA_Emit(snd, VM_Cvar("cl_weapon_sfx") * 0.8);
	if (w == FS_WEAPON_KNIFE && wp_mode)
	{
		// Server confirmed a PLAYER contact, not permission to harm them.
		snd = alternate ? "weapons/knife/knife_stab.wav" : sprintf("weapons/knife/knife_hit%g.wav", floor(random() * 4) + 1);
		GA_Emit(snd, VM_Cvar("cl_weapon_sfx") * 0.7);
		return;
	}
	// Unpunched aim is read only; this is cosmetic wall feedback, not authority.
	reach = (w == FS_WEAPON_KNIFE) ? (alternate ? 64 : 80) : 8192;
	src = pmove_org + [0, 0, getstatf(STAT_VIEWHEIGHT)];
	if (VM_IsMirroring()) src = getproperty(VF_ORIGIN);
	fwd = v_forward; right = v_right; up = v_up;
	makevectors(getproperty(VF_ANGLES));
	traceline(src, src + v_forward * reach, TRUE, world);
	v_forward = fwd; v_right = right; v_up = up;
	if (trace_fraction < 1)
	{
		if (w == FS_WEAPON_KNIFE) GA_Emit("weapons/knife/knife_hitwall1.wav", VM_Cvar("cl_weapon_sfx") * 0.6);
		else GA_Emit("physics/concrete/concrete_impact_bullet1.wav", VM_Cvar("cl_weapon_sfx") * 0.4);
	}
};

void(float w, float kind) WP_Shot =
{
	if (w == FS_WEAPON_KNIFE)
	{
		if (KCAT_Knife() > 0)
		{
			if (kind == FS_WEV_ALT) WP_Animate(wp_mode ? "heavy_hit1" : "heavy_miss1", TRUE);
			else WP_Animate(strcat(wp_mode ? "light_hit" : "light_miss", (wp_shots % 2) ? "2" : "1"), TRUE);
		}
		else WP_Animate((kind == FS_WEV_ALT) ? "stab_miss" : ((wp_shots % 2) ? "midslash2" : "midslash1"), TRUE);
	}
	else if (w == FS_WEAPON_USP) WP_Animate(wp_mode ? "shoot1" : "shoot1_unsil", TRUE);
	else if (w == FS_WEAPON_SCOUT)
	{
		WP_Animate("shoot", TRUE);
		wp_scopepending = wp_zoom;
		wp_zoom = 0;
		wp_rezoomat = cltime + 1.25;
	}
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
	local vector fwd, right, up, ofwd, oright, oup, delta, lag, body, vel;
	ofwd = v_forward; oright = v_right; oup = v_up;
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward; right = v_right; up = v_up;
	v_forward = ofwd; v_right = oright; v_up = oup;
	body = pmove_org; vel = pmove_vel;
	if (VM_IsMirroring())
	{
		body = getproperty(VF_ORIGIN);
		vel = [getstatf(STAT_FS_VELOCITY), getstatf(STAT_FS_VELOCITY + 1), getstatf(STAT_FS_VELOCITY + 2)];
		if (spc_hkok) vel = spc_hvel;
	}
	dt = cltime - wp_motiontime;
	if (!wp_motionvalid || dt < 0 || dt > 0.1 || vlen(body - wp_motionbody) > 128)
	{
		wp_motionvalid = TRUE;
		wp_facing = fwd;
		wp_bobtime = 0;
		wp_motionorg = '0 0 0'; wp_motionang = '0 0 0';
	}
	else if (dt > 0)
	{
		speed = bound(0, vlen([vel_x, vel_y, 0]), 320);
		wp_bobtime = wp_bobtime + dt * speed / 320;
		wp_bobtime = wp_bobtime - floor(wp_bobtime / 0.9) * 0.9;
		vbob = speed * 0.005 * bound(0, VM_Cvar("cl_viewweapon_bob"), 1) * (0.3 + 0.7 * sin(wp_bobtime * 6.2831853 / 0.45));
		lbob = speed * 0.005 * bound(0, VM_Cvar("cl_viewweapon_bob"), 1) * (0.3 + 0.7 * sin(wp_bobtime * 6.2831853 / 0.9));
		delta = fwd - wp_facing;
		amount = 5;
		if (vlen(delta) > 1.5) amount = amount * vlen(delta) / 1.5;
		alpha = 1 - pow(2.7182818, -amount * dt);
		wp_facing = normalize(wp_facing + delta * alpha);
		lag = (fwd - wp_facing) * -5;
		if (vlen(lag) > 3) lag = normalize(lag) * 3;
		lag = lag * bound(0, VM_Cvar("cl_viewweapon_sway"), 1);
		wp_motionorg = [lag * fwd, -(lag * right), lag * up];
		wp_motionorg_x = wp_motionorg_x + vbob * 0.1 + vbob * 0.1 * fwd_z;
		wp_motionorg_y = wp_motionorg_y - lbob * 0.8 - vbob * 0.1 * right_z;
		wp_motionorg_z = wp_motionorg_z + vbob * 0.1 * up_z;
		// Alias pitch is inverted by the engine's r_meshpitch.
		wp_motionang = [vbob * 0.4, -lbob * 0.3, vbob * 0.5];
	}
	wp_motiontime = cltime;
	wp_motionbody = body;
	wp_ent.origin = wp_motionorg;
	wp_ent.angles = wp_motionang;
};

float() WP_IsScoped =
{
	local float eligible;
	eligible = (VM_IsMirroring() || (LT_StatsAreMine() && !getstatf(STAT_FS_SPEC) && getstatf(STAT_FS_MOVETYPE) == MOVETYPE_WALK));
	return (wp_zoom > 0 && wp_ready && wp_weapon == FS_WEAPON_SCOUT &&
		VM_Weapon() == FS_WEAPON_SCOUT && VM_Cvar("cl_viewweapon") > 0 &&
		eligible && !rec_gh_on && !rec_wt_on && !rw_on);
};

void() WP_ScopeView =
{
	if (!WP_IsScoped()) return;
	setproperty(VF_AFOV, (wp_zoom == 1) ? 40 : 15);
	setproperty(VF_DRAWCROSSHAIR, FALSE);
};

void(vector scr) WP_ScopeDraw =
{
	local float radius, left, top, cx, cy;
	if (!WP_IsScoped()) return;
	radius = min(scr_x, scr_y) * 0.5;
	cx = scr_x * 0.5; cy = scr_y * 0.5;
	left = cx - radius; top = cy - radius;
	if (left > 0)
	{
		drawfill('0 0 0', [left, scr_y, 0], '0 0 0', 1);
		drawfill([cx + radius, 0, 0], [left, scr_y, 0], '0 0 0', 1);
	}
	if (top > 0)
	{
		drawfill('0 0 0', [scr_x, top, 0], '0 0 0', 1);
		drawfill([0, cy + radius, 0], [scr_x, top, 0], '0 0 0', 1);
	}
	// CSS supplies one quadrant; mirrored UVs form its circular mask.
	drawsubpic([left, top, 0], [radius, radius, 0], "sprites/scope_arc", '1 1 0', '-1 -1 0', '1 1 1', 1);
	drawsubpic([cx, top, 0], [radius, radius, 0], "sprites/scope_arc", '0 1 0', '1 -1 0', '1 1 1', 1);
	drawsubpic([left, cy, 0], [radius, radius, 0], "sprites/scope_arc", '1 0 0', '-1 1 0', '1 1 1', 1);
	drawsubpic([cx, cy, 0], [radius, radius, 0], "sprites/scope_arc", '0 0 0', '1 1 0', '1 1 1', 1);
	drawfill([cx, top, 0], [1, radius * 2, 0], '0 0 0', 1);
	drawfill([left, cy, 0], [radius * 2, 1, 0], '0 0 0', 1);
};

float wp_texturewarned;
float() WP_KnifeTexturePending =
{
	local float kind;
	kind = KCAT_Knife();
	if (kind <= 0) return FALSE;
	if (strcmp(KCAT_Get(kind, KCAT_BASE), "materials/models/weapons/v_models/knife_t/knife_t.vtf")) return FALSE;
	if (!cvar_type("fs_knife_texture"))
	{
		if (!wp_texturewarned) print("Original/default T textures need the updated native client.\n");
		wp_texturewarned = TRUE;
		return FALSE;
	}
	if (cvar("fs_knife_texture") > 0) return FALSE;
	WP_MountKnifeContent(-1);
	return TRUE;
};

void() WP_Frame =
{
	local float w, seq, kind, file;
	local string mdl;
	local int i;

	if (wp_vmserial != vm_serial)
	{
		if (VM_IsMirroring() && !wp_wasmirror) wp_ownzoom = wp_zoom;
		if (!VM_IsMirroring() && wp_wasmirror) wp_restorezoom = TRUE;
		wp_wasmirror = VM_IsMirroring();
		wp_vmserial = vm_serial;
		wp_weapon = 0;
		wp_ready = wp_motionvalid = FALSE;
		wp_until = wp_flashuntil = wp_kick = wp_kickvel = wp_burstleft = 0;
		wp_zoom = wp_scopepending = 0;
	}
	w = VM_Weapon();
	seq = VM_Event();
	mdl = WP_Model(w);
	if (!strcmp(mdl, "") || VM_Cvar("cl_viewweapon") <= 0 ||
	    (!VM_IsMirroring() && (!LT_StatsAreMine() || getstatf(STAT_FS_SPEC))) ||
	    rec_gh_on || rec_wt_on || rw_on)
	{
		wp_weapon = 0;
		wp_ready = FALSE;
		wp_drawing = FALSE;
		wp_motionvalid = FALSE;
		wp_kick = wp_kickvel = wp_burstleft = 0;
		wp_zoom = wp_scopepending = 0;
		wp_sequence = seq;
		return;
	}
	if (w == FS_WEAPON_KNIFE)
		if (WP_KnifeTexturePending()) return;
	if (!VM_IsMirroring() && getstatf(STAT_FS_MOVETYPE) != MOVETYPE_WALK && getstatf(STAT_FS_MOVETYPE) != MOVETYPE_NOCLIP)
	{
		// Hold is temporary: suppress queued motion/fire, but still submit its retained model.
		wp_motionvalid = FALSE;
		wp_kick = wp_kickvel = wp_burstleft = 0;
		wp_sequence = seq;
		if (getstatf(STAT_FS_MOVETYPE) != MOVETYPE_NONE) return;
	}
	if (!wp_ent) wp_ent = spawn();
	if (w != wp_weapon || strcmp(mdl, wp_model))
	{
		wp_weapon = w;
		wp_motionvalid = FALSE;
		wp_mode = floor(seq / 4) % 2;
		wp_kick = wp_kickvel = wp_burstleft = 0;
		wp_sequence = seq;
		wp_ready = FALSE;
		if (strcmp(wp_model, "")) strunzone(wp_model);
		wp_model = strzone(mdl);
		if (w == FS_WEAPON_KNIFE && KCAT_Knife() > 0)
		{
			file = fopen(wp_model, FILE_READ);
			if (file < 0)
			{
				if (VM_IsMirroring()) WP_MountKnifeContent(-1);
				else WP_MountKnifeContent(KCAT_Knife());
				return;
			}
			fclose(file);
		}
		setmodel(wp_ent, wp_model);
		wp_ent.skeletonindex = 0;
		wp_flashuntil = 0;
		if (wp_ent.modelindex == 0) return;
		WP_LoadMuzzle(); // CSQC's private model slots are NEGATIVE.
		wp_ready = WP_Animate((w == FS_WEAPON_GLOCK) ? "glock_draw" : ((w == FS_WEAPON_USP && !wp_mode) ? "draw_unsil" : "draw"), TRUE);
		wp_drawing = wp_ready;
		if (wp_ready) wp_drawstarts = wp_drawstarts + 1;
		wp_zoom = wp_scopepending = 0;
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
			else if (w == FS_WEAPON_SCOUT)
			{
				wp_zoom = (wp_zoom + 1) % 3;
				wp_scopepending = 0;
				GA_Emit("weapons/zoom.wav", VM_Cvar("cl_weapon_sfx") * 0.8);
			}
			else print(wp_mode ? "Glock: burst fire\n" : "Glock: single fire\n");
		}
		else WP_Shot(w, kind);
	}
	if (VM_IsMirroring()) wp_zoom = VM_Mode();
	else if (wp_restorezoom)
	{
		if (w == FS_WEAPON_SCOUT) wp_zoom = wp_ownzoom;
		wp_restorezoom = FALSE;
	}
	if (VM_IsMirroring() && vm_pendinginspect)
	{
		vm_pendinginspect = FALSE;
		vm_replaying = TRUE;
		WP_Inspect();
		vm_replaying = FALSE;
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
	if (wp_until > 0 && time >= wp_until)
	{
		wp_ready = WP_Animate(WP_Idle(w), FALSE);
		wp_drawing = FALSE;
	}
	if (wp_scopepending > 0 && cltime >= wp_rezoomat)
	{
		wp_zoom = wp_scopepending;
		wp_scopepending = 0;
	}
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
		if (VM_Cvar("cl_viewweapon_left")) wp_ent.renderflags |= RF_XFLIP;
	}
	else if (!VM_Cvar("cl_viewweapon_left")) wp_ent.renderflags |= RF_XFLIP;
	wp_ent.frame1time = max(0, time - wp_animat);
	// Raw MDL animation flags do not carry the sequence's idle-loop flag.
	if (wp_until <= 0 && wp_duration > 0)
		wp_ent.frame1time = wp_ent.frame1time - floor(wp_ent.frame1time / wp_duration) * wp_duration;
	wp_ent.frame2time = wp_ent.frame1time;
	WPU_Apply();
	if (!WP_IsScoped())
	{
		addentity(wp_ent);
		WP_FlashFrame();
	}
};

void() WP_Inspect =
{
	local string clip;
	local float inspectkind;
	if (VM_IsMirroring() && !vm_replaying) return;
	if (wp_weapon != FS_WEAPON_KNIFE || !wp_ready || KCAT_Knife() <= 0)
	{
		if (!vm_replaying) print("inspect: select an installed Legacy knife first\n");
		return;
	}
	clip = KCAT_Get(KCAT_Knife(), KCAT_INSPECT);
	if (!strcmp(clip, ""))
	{
		if (!vm_replaying) print("inspect: this model has no inspect animation\n");
		return;
	}
	inspectkind = 0;
	if (KCAT_Knife() == 1)
	{
		if (vm_replaying) inspectkind = bound(1, vm_inspect % 4, 3);
		else inspectkind = floor(random() * 3) + 1;
		clip = sprintf("lookat0%g", inspectkind);
	}
	if (WP_Animate(clip, TRUE))
	{
		wp_until = time + bound(0.08, wp_duration, 20);
		if (!VM_IsMirroring())
			if (!strcmp(serverkey("*vmsetup"), "1"))
				localcmd(sprintf("cmd vm_inspect %g\n", inspectkind));
	}
};

void(float kind) WP_MountKnifeContent =
{
	// The native action accepts no path and never changes saved mounts.
	if (time < wp_mountnext)
	{
		// The first synchronous native mount is already ahead in this queue.
		// Preserve later choices/order instead of silently swallowing a click.
		localcmd(sprintf("knife_mount_done %g\n", kind));
		return;
	}
	wp_mountnext = time + 5;
	if (!cvar_type("r_viewmodel_fov_csgo"))
	{
		print("Knife workshop: update the client for automatic mounting. Manual console: fs_load \"steam:Counter-Strike Global Offensive/csgo\"\n");
		return;
	}
	print("Knife workshop: requesting installed Legacy assets...\n");
	localcmd(sprintf("fs_knife_mount\nknife_mount_done %g\n", kind));
};

void(float kind) WP_ChooseKnifeReady =
{
	local entity probe;
	local float frame, skeleton;
	local string model;
	if (!KCAT_Valid(kind)) { print("Knife workshop: invalid catalog choice\n"); return; }
	if (!KCAT_Available(kind))
	{
		print("Knife content unavailable. Install CS:GO Legacy and use the updated client; selection unchanged.\n");
		return;
	}
	model = KCAT_Get(kind, KCAT_MODEL);
	if (kind > 0 && strcmp(model, ""))
	{
		probe = spawn();
		precache_model(model); setmodel(probe, model);
		frame = -1;
		if (probe.modelindex)
		{
			if (kind < kcat_knives)
			{
				frame = frameforname(probe.modelindex, KCAT_Get(kind, KCAT_DRAW));
				if (frame < 0) frame = frameforname(probe.modelindex, strcat("@", KCAT_Get(kind, KCAT_DRAW)));
			}
			else
			{
				skeleton = skel_create(probe.modelindex, TRUE);
				if (skeleton) { frame = skel_get_numbones(skeleton); skel_delete(skeleton); }
				if (frame <= 0) frame = -1;
			}
		}
		remove(probe);
		if (frame < 0) { print("Knife workshop: model is unsupported by this client; selection unchanged\n"); return; }
	}
	KCAT_ApplyChoice(kind);
	if (kind >= (float)KCAT_ARMS) return;
	// Retry a previously missing model after an explicit operator mount.
	if (strcmp(wp_model, "")) strunzone(wp_model);
	wp_model = "";
	wp_ready = FALSE;
	cvar_set("cl_viewweapon", "1");
	localcmd("cmd weapon knife\n");
};

void(float kind) WP_ChooseKnife =
{
	if (!KCAT_Valid(kind)) { print("Knife workshop: invalid catalog choice\n"); return; }
	// Use the same command queue for warm and cold choices. A later CSS/hand
	// choice must not be overwritten by an earlier queued mount completion.
	if (KCAT_Available(kind)) localcmd(sprintf("knife_mount_done %g\n", kind));
	else WP_MountKnifeContent(kind);
};

float() WP_Command =
{
	local string cmd, arg, eventname, resolved;
	local float w, giving, f, eventframe, timestamp;
	local int code, i;
	local int *header;

	cmd = argv(0);
	if (!strcmp(cmd, "knife_mount_done"))
	{
		if (stof(argv(1)) >= 0) WP_ChooseKnifeReady(stof(argv(1)));
		else
		{
			f = fopen("models/weapons/v_knife_butterfly.mdl", FILE_READ);
			if (f >= 0) { fclose(f); print("Knife workshop: installed Legacy assets ready for this session.\n"); }
			else print("Knife workshop: Legacy content unavailable; install it and use the updated client.\n");
		}
		return TRUE;
	}
	if (!strcmp(cmd, "inspect")) { WP_Inspect(); return TRUE; }
	if (!strcmp(cmd, "butterfly")) { WP_ChooseKnife(1); return TRUE; }
	if (!strcmp(cmd, "m9")) { WP_ChooseKnife(2); return TRUE; }
	if (!strcmp(cmd, "knife_css")) { WP_ChooseKnife(0); return TRUE; }
	if (!strcmp(cmd, "drop")) { localcmd("cmd drop\n"); return TRUE; }
	if (!strcmp(cmd, "weapon_info"))
	{
		if (!strcmp(argv(1), "refresh")) wp_weapon = 0;
		if (!strcmp(argv(1), "events") && wp_ready)
		{
			f = fopen(wp_model, FILE_READ);
			if (f >= 0)
			{
				header = (int*)memalloc(196i);
				if (fread(f, header, 196) == 196)
					print(sprintf("weapon: MDL version %g sequences %g offset %g bytes %g\n", (float)header[1i], (float)header[47i], (float)header[48i], (float)header[19i]));
				memfree((void*)header);
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
			print(sprintf("weapon: pose-time %g age %g bob %g sway %g\n", wp_ent.frame1time, time - wp_animat, VM_Cvar("cl_viewweapon_bob"), VM_Cvar("cl_viewweapon_sway")));
		}
		print(sprintf("weapon: enabled %g sfx %g fov %g event-sounds %g callbacks %g last '%s'\n", VM_Cvar("cl_viewweapon"), VM_Cvar("cl_weapon_sfx"), VM_Cvar("r_viewmodel_fov"), wp_events, wp_callbacks, wp_soundlast));
		print(sprintf("weapon: motion valid %g offset %v angles %v\n", wp_motionvalid, wp_motionorg, wp_motionang));
		print(sprintf("weapon: mode %g burst-pending %g kick %g velocity %g render-dt %g\n", wp_mode, wp_burstleft, wp_kick, wp_kickvel, wp_kickdt));
		print(sprintf("weapon: muzzle attachment %g flashes %g\n", wp_muzzletag, wp_flashes));
		print(sprintf("weapon: draw-starts %g zoom %g scoped %g rezoom %g movetype %g\n", wp_drawstarts, wp_zoom, WP_IsScoped(), wp_scopepending, getstatf(STAT_FS_MOVETYPE)));
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
