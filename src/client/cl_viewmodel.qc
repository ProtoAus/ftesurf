/* P970: own archived setup, account transport and a separate watched render
   context. Never write watched values into the observer's preferences. */
#define VM_FOVPROPERTY 227
float() WP_LocalZoom;
float vm_active, vm_target, vm_serial, vm_capfov, vm_fovwarned;
float *vm_values;
string vm_watchraw, vm_own, vm_sent, vm_notice;
float vm_nextpoll, vm_publishat, vm_unsaved, vm_generation, vm_loading;
string vm_before, vm_account;
float vm_loadkeep, vm_inspect, vm_pendinginspect, vm_replaying;

string(float field) VM_CvarName =
{
	if (field == VM_ENABLED) return "cl_viewweapon";
	if (field == VM_ARMS) return "cl_knife_arms";
	if (field == VM_FINISH) return "cl_knife_finish";
	if (field == VM_SEED) return "cl_knife_seed";
	if (field == VM_SCALE) return "cl_knife_scale";
	if (field == VM_ROTATION) return "cl_knife_rotation";
	if (field == VM_FADE) return "cl_knife_fade";
	if (field == VM_WEAR) return "cl_knife_wear";
	if (field == VM_LEFT) return "cl_viewweapon_left";
	if (field == VM_BOB) return "cl_viewweapon_bob";
	if (field == VM_SWAY) return "cl_viewweapon_sway";
	if (field == VM_FOV) return "r_viewmodel_fov";
	if (field == VM_LEGACYFOV) return "r_viewmodel_fov_csgo";
	if (field == VM_MUZZLE) return "cl_weapon_muzzleflash";
	if (field == VM_SFX) return "cl_weapon_sfx";
	if (field == VM_UIX) return "hud_knife_x";
	if (field == VM_UIY) return "hud_knife_y";
	return "";
};

float() VM_IsMirroring = { return vm_active; };
float(float field) VM_ViewValue =
{
	if (field < 0 || field >= VM_FIELDS) return 0;
	return vm_values[(int)field];
};
float(string name) VM_Cvar =
{
	local float i;
	if (vm_active)
		for (i = 1; i < VM_FIELDS; i = i + 1)
			if (!strcmp(name, VM_CvarName(i))) return VM_ViewValue(i);
	return cvar(name);
};
float() VM_Weapon =
{
	if (vm_active) return getstatf(STAT_VM_WEAPON);
	return getstatf(STAT_ACTIVEWEAPON);
};
float() VM_Event =
{
	if (vm_active) return getstatf(STAT_VM_EVENT);
	return getstatf(STAT_WEAPONFRAME);
};
float() VM_Mode =
{
	if (vm_active) return getstatf(STAT_VM_MODE);
	return WP_LocalZoom();
};
void(string note) VM_Notice =
{
	if (strcmp(vm_notice, "")) strunzone(vm_notice);
	vm_notice = strzone(note);
};
string() VM_Status =
{
	if (vm_loading) return "Loading linked-account setup...";
	if (strcmp(vm_notice, "")) return vm_notice;
	return "Link Steam on this lobby to sync this setup.";
};

string() VM_OwnSetup =
{
	local float i, value;
	local vector limits;
	local string packed;
	packed = "";
	for (i = 0; i < VM_FIELDS; i = i + 1)
	{
		if (i == 0) value = VM_VERSION;
		else if (i == VM_KNIFE) value = KCAT_LocalKnife();
		else if (i == VM_HANDS) value = KCAT_LocalHands();
		else if (i == VM_LAYER) value = KCAT_LocalLayer();
		else value = cvar(VM_CvarName(i));
		limits = VM_Range(i);
		if (!(value >= limits_x && value <= limits_y))
		{
			if (value != value) value = limits_x;
			value = bound(limits_x, value, limits_y);
		}
		if (limits_z) value = floor(value);
		packed = strcat(packed, i ? "," : "", VM_Number(value));
	}
	return packed;
};
void(string packed) VM_ApplyOwn =
{
	local float i;
	local string name;
	// Caller validated the ENTIRE payload first. Restore only this account's
	// own settings; no remote render-context path calls this function.
	KCAT_ApplyChoice(VM_Get(packed, VM_KNIFE));
	KCAT_ApplyChoice(VM_Get(packed, VM_HANDS));
	KCAT_ApplyChoice(VM_Get(packed, VM_LAYER));
	for (i = 1; i < VM_FIELDS; i = i + 1)
	{
		name = VM_CvarName(i);
		if (strcmp(name, "")) cvar_set(name, VM_Number(VM_Get(packed, i)));
	}
};
void(string packed) VM_RememberOwn =
{
	if (strcmp(vm_own, "")) strunzone(vm_own);
	vm_own = strzone(packed);
};
void() VM_PollOwn =
{
	local string packed;
	if (cltime < vm_nextpoll) return;
	vm_nextpoll = cltime + 0.2;
	packed = VM_OwnSetup();
	if (strcmp(packed, vm_own))
	{
		if (strcmp(vm_own, "")) vm_unsaved = TRUE;
		VM_RememberOwn(packed);
	}
	if (strcmp(serverkey("*vmsetup"), "1")) return;
	// A first command can precede spawn; periodically republish the same setup.
	if (!strcmp(packed, vm_sent) && cltime < vm_publishat) return;
	vm_publishat = cltime + 5;
	localcmd(strcat("cmd vm_setup \"", packed, "\"\n"));
	if (strcmp(vm_sent, "")) strunzone(vm_sent);
	vm_sent = strzone(packed);
};
void(string action) VM_ProfileAction =
{
	if (strcmp(serverkey("*vmsetup"), "1"))
	{
		VM_Notice("This lobby does not support account setups yet.");
		return;
	}
	localcmd(strcat("cmd vm_setup \"", VM_OwnSetup(), "\"\ncmd vm_profile ", action, "\n"));
};

float() VM_ConsoleCommand =
{
	local string command, action, data, who, current;
	local float generation, revision;
	command = argv(0);
	if (!strcmp(command, "viewmodel_setup"))
	{
		action = argv(1);
		if (!strcmp(action, "save") || !strcmp(action, "reload")) VM_ProfileAction(action);
		else if (!strcmp(action, "check"))
		{
			data = VM_Normalize(argv(2));
			if (!strcmp(data, "")) print("viewmodel_setup: REFUSED\n");
			else print(strcat("viewmodel_setup: canonical ", data, "\n"));
		}
		else
		{
			print(strcat("viewmodel_setup: ", VM_Status(), "\n"));
			print(strcat("viewmodel_setup: own ", VM_OwnSetup(), "\n"));
			print(sprintf("viewmodel_setup: mirror %g target %g serial %g\n", vm_active, vm_target, vm_serial));
			print(sprintf("viewmodel_setup: cap '%s' published '%s' watched '%s' decoded %g,%g sent '%s'\n", serverkey("*vmsetup"), getplayerkeyvalue(player_localnum, "*vm"), vm_watchraw, VM_ViewValue(0), VM_ViewValue(VM_ENABLED), vm_sent));
			if (vm_active) print(strcat("viewmodel_setup: watched ", vm_watchraw, "\n"));
			print(sprintf("viewmodel_setup: weapon %g event %g inspect %g\n", VM_Weapon(), VM_Event(), vm_inspect));
			if (vm_capfov) print(sprintf("viewmodel_setup: render FOV override %g world %v\n", getproperty(VM_FOVPROPERTY), getproperty(VF_FOV)));
		}
		return TRUE;
	}
	if (strcmp(command, "vm_profile")) return FALSE;
	// Copy ALL argv before the common numeric codec reuses tokenize.
	action = argv(1); generation = stof(argv(2));
	revision = stof(argv(3)); data = argv(4); who = argv(3);
	if (!strcmp(action, "begin"))
	{
		if (generation < 1) return TRUE;
		if (strcmp(vm_account, "") && strcmp(vm_account, who)) vm_unsaved = FALSE;
		if (strcmp(vm_account, "")) strunzone(vm_account);
		vm_account = strzone(who);
		vm_generation = generation;
		vm_loading = TRUE;
		vm_loadkeep = vm_unsaved;
		if (strcmp(vm_before, "")) strunzone(vm_before);
		vm_before = strzone(VM_OwnSetup());
		return TRUE;
	}
	if (generation != vm_generation) return TRUE;
	if (!strcmp(action, "load") || !strcmp(action, "none"))
	{
		if (!vm_loading) return TRUE;
		current = VM_OwnSetup();
		if (!strcmp(action, "load"))
		{
			data = VM_Normalize(data);
			if (!strcmp(data, ""))
			{
				vm_loading = FALSE;
				VM_Notice("Account setup refused; local settings kept.");
				return TRUE;
			}
			if (!vm_loadkeep && !strcmp(current, vm_before))
			{
				VM_ApplyOwn(data);
				current = VM_OwnSetup();
				vm_unsaved = FALSE;
				VM_RememberOwn(current);
				VM_Notice("Linked-account setup restored.");
			}
			else VM_Notice("New local edits kept; syncing those to your account.");
		}
		else VM_Notice("No account setup yet; saving your current setup.");
		vm_loading = FALSE;
		localcmd(sprintf("cmd vm_profile ack %.0f \"%s\"\n", generation, current));
		return TRUE;
	}
	if (!strcmp(action, "saved"))
	{
		if (!strcmp(VM_OwnSetup(), data)) vm_unsaved = FALSE;
		if (vm_unsaved) VM_Notice("New local edits pending account save.");
		else VM_Notice("Linked-account setup saved.");
		return TRUE;
	}
	if (!strcmp(action, "error"))
	{
		vm_loading = FALSE;
		VM_Notice(sprintf("Account setup unavailable (%g); local settings kept.", revision));
	}
	return TRUE;
};

void() VM_Frame =
{
	local float st, target, previous, i, event, fov;
	local string raw, packed;
	previous = vm_active;
	target = -1;
	vm_active = FALSE;
	VM_PollOwn();
	if (vm_capfov) setproperty(VM_FOVPROPERTY, 0);
	st = getstatf(STAT_FS_SPEC);
	if (!rec_gh_on && !rec_wt_on && !rec_wt_open && !rw_on && cvar("cl_spec_viewweapon"))
	{
		if (spc_cam && spc_mode == SPM_FIRST && st > 0 && !spc_handover) target = st - 1;
		// Native QW first-person tracking changes viewentity; its wall/free
		// camera keeps our own viewentity even while receiving target stats.
		else if (!spc_cam && st == 0 && player_localentnum > 0 && player_localentnum <= 32 &&
		         player_localentnum != player_localnum + 1 && getstatf(STAT_FS_STATOWNER) == player_localentnum)
			target = player_localentnum - 1;
	}
	if (target >= 0)
	{
		raw = getplayerkeyvalue(target, "*vm");
		if (target != vm_target || strcmp(raw, vm_watchraw))
		{
			packed = VM_Normalize(raw);
			if (strcmp(vm_watchraw, "")) strunzone(vm_watchraw);
			vm_watchraw = strzone(raw);
			if (vm_target != target)
			{
				vm_serial = vm_serial + 1;
				vm_pendinginspect = FALSE;
				vm_inspect = getstatf(STAT_VM_INSPECT);
			}
			vm_target = target;
			for (i = 0; i < VM_FIELDS; i = i + 1) vm_values[(int)i] = 0;
			if (strcmp(packed, ""))
				for (i = 0; i < VM_FIELDS; i = i + 1) vm_values[(int)i] = VM_Get(packed, i);
		}
		if (VM_ViewValue(0) == VM_VERSION && VM_ViewValue(VM_ENABLED)) vm_active = TRUE;
	}
	if (vm_active)
	{
		if (!previous)
		{
			vm_serial = vm_serial + 1;
			vm_inspect = getstatf(STAT_VM_INSPECT);
		}
		event = getstatf(STAT_VM_INSPECT);
		if (event != vm_inspect) vm_pendinginspect = TRUE;
		vm_inspect = event;
		cvar_set("cl_vm_seed", VM_Number(VM_ViewValue(VM_SEED)));
		cvar_set("cl_vm_scale", VM_Number(VM_ViewValue(VM_SCALE)));
		cvar_set("cl_vm_rotation", VM_Number(VM_ViewValue(VM_ROTATION)));
		cvar_set("cl_vm_fade", VM_Number(VM_ViewValue(VM_FADE)));
		cvar_set("cl_vm_wear", VM_Number(VM_ViewValue(VM_WEAR)));
		if (vm_capfov)
		{
			fov = VM_ViewValue(VM_FOV);
			if (VM_Weapon() == FS_WEAPON_KNIFE && KCAT_Knife() > 0 && VM_ViewValue(VM_LEGACYFOV) > 0)
				fov = VM_ViewValue(VM_LEGACYFOV);
			setproperty(VM_FOVPROPERTY, fov ? fov : -1);
		}
		else if (!vm_fovwarned)
		{
			print("Spectator weapon FOV needs the updated native client.\n");
			vm_fovwarned = TRUE;
		}
	}
	else
	{
		if (previous) vm_serial = vm_serial + 1;
		if (target < 0) vm_target = -1;
		vm_pendinginspect = FALSE;
	}
};

void() VM_Register =
{
	vm_values = (float*)memalloc((int)VM_FIELDS * 4i);
	vm_target = -1;
	vm_capfov = checkextension("FTESURF_VIEWMODEL_FOV");
	registercommand("viewmodel_setup");
	registercommand("vm_profile");
	registercvar("cl_spec_viewweapon", "1", CVAR_ARCHIVE);
	registercvar("cl_vm_seed", "0", 0);
	registercvar("cl_vm_scale", "1", 0);
	registercvar("cl_vm_rotation", "0", 0);
	registercvar("cl_vm_fade", "1", 0);
	registercvar("cl_vm_wear", "0", 0);
};
