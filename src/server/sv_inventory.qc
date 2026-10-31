/* Account-owned cosmetics, never client userinfo or gameplay privileges.
   Public *kit is roles/outline/hat-colour+1; private ownership stays on owner. */
.float inv_revision, inv_req, inv_deadline, inv_next;

void(entity e) Inv_SVReset =
{
	e.inv_req = 0;
	e.inv_revision = -1;
	e.inv_next = 0;
	forceinfokey(e, "*kit", "");
	stuffcmd(e, "inventory_clear\n");
};

void(entity e, float root) Inv_SVApply =
{
	local float revision, roles, outline, hat, items, i, row, id, colour, on;
	local float own1, own2, hatcolour, eq1, eq2;
	if (!root || e.acct_state != 2 || strlen(e.social_token) != 64) return;
	revision = json_get_float(json_find_object_child(root, "revision"));
	roles = json_get_float(json_find_object_child(root, "roles"));
	outline = json_get_float(json_find_object_child(root, "outline"));
	hat = json_get_float(json_find_object_child(root, "hat"));
	if (revision < 0 || revision > 16777215 || revision != floor(revision) || revision < e.inv_revision) return;
	if (roles < 1 || roles > 7 || roles != floor(roles) || !(roles & 1)) return;
	if ((outline != 0 && outline != 1) || hat < 0 || hat > 12 || hat != floor(hat)) return;
	items = json_find_object_child(root, "items");
	if (json_get_length(items) > 16) return;
	own1 = own2 = hatcolour = eq1 = eq2 = 0;
	for (i = 0; i < json_get_length(items); i = i + 1)
	{
		row = json_get_child_at_index(items, i);
		id = json_get_float(json_find_object_child(row, "id"));
		colour = json_get_float(json_find_object_child(row, "colour"));
		on = json_get_float(json_find_object_child(row, "equipped"));
		if ((on != 0 && on != 1) || colour < 0 || colour > 11 || colour != floor(colour)) return;
		if (id == 1) { if (own1) return; own1 = 1; eq1 = on; }
		else if (id == 2) { if (own2) return; own2 = 1; hatcolour = colour; eq2 = on; }
		else return;
	}
	if (outline != eq1 || hat != (eq2 ? hatcolour + 1 : 0)) return;
	e.inv_revision = revision;
	forceinfokey(e, "*kit", sprintf("%g %g %g", roles, outline, hat));
	stuffcmd(e, strcat(sprintf("inventory_state %s %.0f %g %g %g %g",
	         infokey(e, "*ahash"), revision, roles, own1, own2, hatcolour), sprintf(" %g %g\n", eq1, eq2)));
};

void(entity e, float count) Inv_SVCommand =
{
	local float item, on, revision;
	local string form;
	if (count != 4 || e.acct_state != 2 || strlen(e.social_token) != 64) return;
	if (e.inv_req && time < e.inv_deadline) return;
	if (time < e.inv_next) return;
	if (!VM_NumberToken(argv(1)) || !VM_NumberToken(argv(2)) || !VM_NumberToken(argv(3))) return;
	item = stof(argv(1)); on = stof(argv(2)); revision = stof(argv(3));
	if ((item != 1 && item != 2) || (on != 0 && on != 1)) return;
	if (revision < 0 || revision > 16777215 || revision != floor(revision)) return;
	e.inv_next = time + 0.25;
	e.inv_req = Account_NextId();
	e.inv_deadline = time + 15;
	form = strcat(Social_Form(), "&token=", e.social_token,
	              sprintf("&op=equip&item=%g&on=%g&revision=%.0f", item, on, revision));
	uri_post(strcat(cvar_string("lobby_master"), "/api/social/inventory"), e.inv_req,
	         "application/x-www-form-urlencoded", form);
};

float(float reqid, float code, string body) Inv_SVReply =
{
	local entity e;
	local float root, ok;
	e = findfloat(world, inv_req, reqid);
	if (!e || !reqid) return FALSE;
	e.inv_req = 0;
	if (e.acct_state != 2 || strlen(e.social_token) != 64) return TRUE;
	root = json_parse(body);
	ok = json_get_float(json_find_object_child(root, "ok"));
	if (!code && ok && json_get_float(json_find_object_child(root, "inventory")) == 1)
		Inv_SVApply(e, root);
	else
	{
		sprint(e, PRINT_HIGH, "Inventory: equipment was not confirmed. Refreshing; please try again.\n");
		social_next = 0;
	}
	if (root) json_free(root);
	return TRUE;
};
