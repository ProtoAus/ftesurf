/* Basic CSS presentation. Standard weapon/weaponframe stats remain authoritative. */
entity wp_ent;
float wp_weapon, wp_sequence, wp_animat, wp_until, wp_shots, wp_ready;
string wp_model;

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
	return "idle";
};

string(float w) WP_Fire =
{
	if (w == FS_WEAPON_KNIFE) return "midslash1";
	if (w == FS_WEAPON_USP) return "shoot1";
	if (w == FS_WEAPON_SCOUT) return "shoot";
	return "glock_firesingle";
};

void(string name, float oneshot) WP_Animate =
{
	local float f, duration;

	f = frameforname(wp_ent.modelindex, name);
	// The Source loader exposes sequence groups with an @ prefix.
	if (f < 0) f = frameforname(wp_ent.modelindex, strcat("@", name));
	if (f < 0)
	{
		wp_ready = FALSE;
		print(sprintf("weapon: unavailable animation '%s' in '%s'\n", name, wp_model));
		return;
	}
	wp_ent.frame = f;
	wp_ent.frame2 = f;
	wp_ent.lerpfrac = 0;
	wp_animat = time;
	duration = frameduration(wp_ent.modelindex, f);
	wp_until = oneshot ? time + bound(0.08, duration, 3) : 0;
};

void() WP_Register =
{
	registercvar("cl_viewweapon", "1", CVAR_ARCHIVE);
	registercvar("cl_viewweapon_left", "0", CVAR_ARCHIVE);
	registercommand("surf_weapon");
	registercommand("weapon_info");
};

void() WP_Shot =
{
	local string s;
	local vector src;
	local float reach;

	wp_shots = wp_shots + 1;
	if (wp_ready) WP_Animate(WP_Fire(wp_weapon), TRUE);
	s = "weapons/glock/glock18-1.wav";
	if (wp_weapon == FS_WEAPON_KNIFE) s = "weapons/knife/knife_slash1.wav";
	if (wp_weapon == FS_WEAPON_USP) s = "weapons/usp/usp1.wav";
	if (wp_weapon == FS_WEAPON_SCOUT) s = "weapons/scout/scout_fire-1.wav";
	GA_Play(s, 0.8);
	// Cosmetic wall feedback only, never a damage or hit-confirmation claim.
	reach = (wp_weapon == FS_WEAPON_KNIFE) ? 80 : 8192;
	src = pmove_org + [0, 0, getstatf(STAT_VIEWHEIGHT)];
	makevectors(getproperty(VF_ANGLES));
	traceline(src, src + v_forward * reach, TRUE, world);
	if (trace_fraction < 1)
	{
		if (wp_weapon == FS_WEAPON_KNIFE)
			GA_Play("weapons/knife/knife_hitwall1.wav", 0.6);
		else
			GA_Play("physics/concrete/concrete_impact_bullet1.wav", 0.4);
	}
};

void() WP_Frame =
{
	local float w, seq, f;
	local string modelname, drawname;

	w = getstatf(STAT_ACTIVEWEAPON);
	seq = getstatf(STAT_WEAPONFRAME);
	if (!LT_StatsAreMine() || rec_gh_on || rec_wt_on || rw_on ||
	    getstatf(STAT_FS_SPEC) || getstatf(STAT_FS_MOVETYPE) != MOVETYPE_WALK)
	{
		wp_sequence = seq;
		wp_weapon = 0;
		return;
	}
	if (w != wp_weapon)
	{
		wp_weapon = w;
		wp_sequence = seq;
		wp_ready = FALSE;
		modelname = WP_Model(w);
		if (strcmp(wp_model, "")) strunzone(wp_model);
		wp_model = strzone(modelname);
		if (strcmp(modelname, ""))
		{
			f = fopen(modelname, FILE_READ);
			if (f >= 0)
			{
				fclose(f);
				if (!wp_ent) wp_ent = spawn();
				setmodel(wp_ent, modelname);
				wp_ready = (wp_ent.modelindex != 0);
				if (wp_ready)
				{
					drawname = (w == FS_WEAPON_GLOCK) ? "glock_draw" : "draw";
					WP_Animate(drawname, TRUE);
				}
			}
		}
	}
	if (seq != wp_sequence)
	{
		wp_sequence = seq;
		if (w) WP_Shot();
	}
	if (!wp_ready) return;
	if (wp_until > 0 && time >= wp_until) WP_Animate(WP_Idle(w), FALSE);
	if (cvar("cl_viewweapon") <= 0) return;
	wp_ent.origin = '0 0 0';
	wp_ent.angles = '0 0 0';
	wp_ent.renderflags = RF_VIEWMODEL | RF_DEPTHHACK | RF_NOSHADOW;
	// CSS gun meshes are left-authored; the knife is right-authored.
	if (w == FS_WEAPON_KNIFE)
	{
		if (cvar("cl_viewweapon_left")) wp_ent.renderflags = wp_ent.renderflags | RF_XFLIP;
	}
	else if (!cvar("cl_viewweapon_left")) wp_ent.renderflags = wp_ent.renderflags | RF_XFLIP;
	wp_ent.alpha = 1;
	wp_ent.scale = 1;
	wp_ent.frame1time = time - wp_animat;
	wp_ent.frame2time = wp_ent.frame1time;
	addentity(wp_ent);
};

float() WP_Command =
{
	local string s;
	local float w;

	if (!strcmp(argv(0), "weapon_info"))
	{
		if (!strcmp(argv(1), "refresh")) wp_weapon = 0;
		print(sprintf("weapon: type %g sequence %g ready %g shots %g model '%s'\n",
			wp_weapon, wp_sequence, wp_ready, wp_shots, wp_model));
		if (wp_ready)
			print(sprintf("weapon: frame '%s' duration %g time %g\n",
				frametoname(wp_ent.modelindex, wp_ent.frame), frameduration(wp_ent.modelindex, wp_ent.frame), wp_ent.frame1time));
		return TRUE;
	}
	if (strcmp(argv(0), "surf_weapon")) return FALSE;
	s = strtolower(argv(1));
	w = 0;
	if (!strcmp(s, "knife")) w = FS_WEAPON_KNIFE;
	if (!strcmp(s, "usp")) w = FS_WEAPON_USP;
	if (!strcmp(s, "scout")) w = FS_WEAPON_SCOUT;
	if (!strcmp(s, "glock")) w = FS_WEAPON_GLOCK;
	if (w) localcmd(sprintf("cmd weapon %g\n", w));
	else print("surf_weapon knife | usp | scout | glock (existing binds unchanged)\n");
	return TRUE;
};
