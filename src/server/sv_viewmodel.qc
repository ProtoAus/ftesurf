/* P970: cosmetic replication and account settings. The social capability stays
   on this lobby; playerinfo contains only a bounded numeric presentation setup. */
.float vm_req, vm_reqkind, vm_deadline, vm_generation, vm_revision;
.float vm_ready, vm_waitack, vm_dirty, vm_quiet;
.string vm_setup, vm_cloud, vm_saving;
.float vm_inspectevent, vm_inspectnext;
.float vm_showweapon, vm_showevent, vm_showinspect, vm_showmode;
.float vm_publishdirty, vm_publishnext;

void(entity e, float code) VM_SVError =
{
	e.vm_ready = FALSE;
	e.vm_waitack = FALSE;
	stuffcmd(e, sprintf("vm_profile error %.0f %.0f\n", e.vm_generation, code));
};
void(entity e) VM_SVAccountReset =
{
	if (e.vm_generation) stuffcmd(e, sprintf("vm_profile error %.0f 403\n", e.vm_generation));
	e.vm_req = 0;
	e.vm_ready = e.vm_waitack = e.vm_dirty = FALSE;
	e.vm_generation = 0;
	e.vm_revision = 0;
	if (strcmp(e.vm_cloud, "")) strunzone(e.vm_cloud);
	if (strcmp(e.vm_saving, "")) strunzone(e.vm_saving);
	e.vm_cloud = e.vm_saving = "";
};
void(entity e) VM_SVConnect =
{
	VM_SVAccountReset(e);
	if (strcmp(e.vm_setup, "")) strunzone(e.vm_setup);
	e.vm_setup = "";
	e.vm_inspectevent = e.vm_inspectnext = 0;
	e.vm_publishdirty = e.vm_publishnext = 0;
	e.vm_showweapon = e.vm_showevent = e.vm_showinspect = e.vm_showmode = 0;
	forceinfokey(e, "*vm", "");
};
void(entity e, string packed) VM_SVSetup =
{
	if (!strcmp(e.vm_setup, packed)) return;
	if (strcmp(e.vm_setup, "")) strunzone(e.vm_setup);
	e.vm_setup = strzone(packed);
	e.vm_dirty = TRUE;
	e.vm_quiet = time + 0.75;
	e.vm_publishdirty = TRUE;
};
void(entity e, float kind) VM_SVRequest =
{
	local string form;
	if (e.vm_req || e.acct_state != 2 || strlen(e.social_token) != 64)
	{
		VM_SVError(e, 403);
		return;
	}
	form = strcat(Social_Form(), "&game=1&token=", e.social_token);
	if (kind == 1)
	{
		if (!strcmp(e.vm_saving, "")) { VM_SVError(e, 400); return; }
		form = strcat(form, sprintf("&op=set&revision=%.0f&setup=%s", e.vm_revision, e.vm_saving));
	}
	else form = strcat(form, "&op=get");
	e.vm_req = Account_NextId();
	e.vm_reqkind = kind;
	e.vm_deadline = time + 15;
	uri_post(strcat(cvar_string("lobby_url"), "/api/social/viewmodel"), e.vm_req,
	         "application/x-www-form-urlencoded", form);
};
void(entity e) VM_SVSave =
{
	if (!strcmp(e.vm_setup, "")) return;
	if (strcmp(e.vm_saving, "")) strunzone(e.vm_saving);
	e.vm_saving = strzone(e.vm_setup);
	VM_SVRequest(e, 1);
};
void(entity e) VM_SVBind =
{
	VM_SVAccountReset(e);
	if (e.acct_state != 2 || strlen(e.social_token) != 64) return;
	e.vm_generation = Account_NextId();
	stuffcmd(e, sprintf("vm_profile begin %.0f %s\n", e.vm_generation, infokey(e, "*ahash")));
	VM_SVRequest(e, 0);
};

float(float reqid, float code, string body) VM_SVReply =
{
	local entity e;
	local float root, ok, status, revision, kind;
	local string packed, normalized;
	e = findfloat(world, vm_req, reqid);
	if (!e || reqid == 0) return FALSE;
	kind = e.vm_reqkind;
	e.vm_req = 0;
	// Disconnect, account reset and token refresh cancel the id before an answer.
	if (e.acct_state != 2 || strlen(e.social_token) != 64) return TRUE;
	root = json_parse(body);
	ok = json_get_float(json_find_object_child(root, "ok"));
	status = json_get_float(json_find_object_child(root, "status"));
	if (code || !ok || json_get_float(json_find_object_child(root, "viewmodel")) != 1)
	{
		if (root) json_free(root);
		if (code) status = code;
		if (!status) status = 503;
		VM_SVError(e, status);
		return TRUE;
	}
	revision = json_get_float(json_find_object_child(root, "revision"));
	packed = strzone(json_get_string(json_find_object_child(root, "setup")));
	json_free(root);
	normalized = VM_Normalize(packed);
	if (!(revision >= 0 && revision <= 16777215) || revision != floor(revision) ||
	    (revision == 0 && strcmp(packed, "")) ||
	    (revision > 0 && (!strcmp(normalized, "") || strcmp(packed, normalized))))
	{
		strunzone(packed);
		VM_SVError(e, 400);
		return TRUE;
	}
	if (kind == 1 && (revision < 1 || strcmp(packed, e.vm_saving)))
	{
		strunzone(packed);
		VM_SVError(e, 400);
		return TRUE;
	}
	e.vm_revision = revision;
	if (strcmp(e.vm_cloud, "")) strunzone(e.vm_cloud);
	e.vm_cloud = packed;
	if (kind == 1)
	{
		stuffcmd(e, sprintf("vm_profile saved %.0f %.0f \"%s\"\n", e.vm_generation, revision, packed));
		e.vm_ready = TRUE;
		e.vm_dirty = (strcmp(e.vm_setup, packed) != 0);
		e.vm_quiet = time + 0.75;
	}
	else if (kind == 2)
	{
		// Explicit Save fetches only the current revision, not somebody else's UI.
		VM_SVSave(e);
	}
	else
	{
		e.vm_ready = TRUE;
		e.vm_waitack = TRUE;
		e.vm_deadline = time + 15;
		if (revision) stuffcmd(e, sprintf("vm_profile load %.0f %.0f \"%s\"\n", e.vm_generation, revision, packed));
		else stuffcmd(e, sprintf("vm_profile none %.0f 0\n", e.vm_generation));
	}
	return TRUE;
};

void(entity e, string command, float count) VM_SVCommand =
{
	local string action, packed;
	local float generation, inspectkind;
	if (!strcmp(command, "vm_setup"))
	{
		if (count != 2) return;
		packed = VM_Normalize(argv(1));
		if (strcmp(packed, "")) VM_SVSetup(e, packed);
		return;
	}
	if (!strcmp(command, "vm_inspect"))
	{
		if (count != 2) return;
		if (!VM_NumberToken(argv(1))) return;
		inspectkind = stof(argv(1));
		if (inspectkind < 0 || inspectkind > 3 || inspectkind != floor(inspectkind)) return;
		if (e.run_sp_phase || e.weapon != FS_WEAPON_KNIFE || time < e.vm_inspectnext) return;
		if (!strcmp(e.vm_setup, "")) return;
		if (!VM_Get(e.vm_setup, VM_ENABLED)) return;
		e.vm_inspectevent = ((floor(e.vm_inspectevent / 4) + 1) % 4096) * 4 + inspectkind;
		e.vm_inspectnext = time + 0.2;
		return;
	}
	action = argv(1); generation = stof(argv(2)); packed = argv(3);
	if (!strcmp(action, "ack"))
	{
		if (count != 4 || !e.vm_waitack || generation != e.vm_generation || e.acct_state != 2) return;
		packed = VM_Normalize(packed);
		if (!strcmp(packed, "")) return;
		VM_SVSetup(e, packed);
		e.vm_waitack = FALSE;
		e.vm_dirty = (strcmp(e.vm_setup, e.vm_cloud) != 0);
		return;
	}
	if (count != 2) return;
	if (e.vm_req || e.vm_waitack) { sprint(e, PRINT_HIGH, "Account setup is busy; try shortly.\n"); return; }
	if (!strcmp(action, "reload")) VM_SVBind(e);
	else if (!strcmp(action, "save"))
	{
		if (!e.vm_generation) e.vm_generation = Account_NextId();
		// No automatic conflict overwrite. Only this explicit button asks for a
		// fresh revision followed by a CAS save of current local choices.
		VM_SVRequest(e, 2);
	}
};

void() VM_SVFrame =
{
	local entity e, source;
	e = find(world, classname, "player");
	while (e)
	{
		if (e.vm_publishdirty && time >= e.vm_publishnext)
		{
			// Rendering data only; editor position remains account-private.
			forceinfokey(e, "*vm", VM_PublicSetup(e.vm_setup));
			e.vm_publishdirty = FALSE;
			e.vm_publishnext = time + 0.2;
		}
		source = e;
		if (e.run_sp_phase == 1)
			if (e.pb_watch && e.pb_watch.run_inserver) source = e.pb_watch;
		e.vm_showweapon = source.weapon;
		e.vm_showevent = source.weaponframe;
		e.vm_showinspect = source.vm_inspectevent;
		e.vm_showmode = source.vbsp_weaponmode;
		if ((e.vm_req || e.vm_waitack) && time > e.vm_deadline)
		{
			e.vm_req = 0;
			VM_SVError(e, 504);
		}
		if (e.vm_ready && e.vm_dirty && !e.vm_waitack && !e.vm_req && time >= e.vm_quiet)
			VM_SVSave(e);
		e = find(e, classname, "player");
	}
};

void() VM_SVRegister =
{
	forceinfokey(world, "*vmsetup", "1");
	clientstat(STAT_VM_WEAPON, EV_FLOAT, vm_showweapon);
	clientstat(STAT_VM_EVENT, EV_FLOAT, vm_showevent);
	clientstat(STAT_VM_INSPECT, EV_FLOAT, vm_showinspect);
	clientstat(STAT_VM_MODE, EV_FLOAT, vm_showmode);
};
