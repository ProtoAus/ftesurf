// Read-only public profile dialog. No signing keys, inventory writes or arbitrary URLs.
#define MFP_ROWS 12
#define MFP_TWOSIDED 1024     // same renderer polygon flag as CSQC's DRAWFLAG_TWOSIDED
float mfp_open, mfp_req, mfp_at, mfp_rows, mfp_init, mfp_n, mfp_ready;
float mfp_times, mfp_maps, mfp_first, mfp_items_known, mfp_play_known, mfp_play_seconds;
vector mfp_owned, mfp_kit;
string mfp_who, mfp_name, mfp_note;
int(int node) MFP_JsonInt = #0:json_get_integer;

void() MFP_Close = { mfp_open = FALSE; mfp_req = 0; };
float() MFP_IsOpen = { return mfp_open; };

void(string who, string name) MFP_Open =
{
	local string nextwho, nextname, dir;
	if (!MF_Online()) return;
	if (!MF_Hex(who, 12) && !MF_Hex(who, 8)) return;
	if (!mfp_init) { mfp_rows = buf_create(); mfp_init = TRUE; }
	nextwho = strzone(who); nextname = strzone(name);
	if (mfp_who != "") strunzone(mfp_who);
	if (mfp_name != "") strunzone(mfp_name);
	mfp_who = nextwho; mfp_name = nextname;
	mfp_open = TRUE;
	mfp_ready = mfp_items_known = mfp_play_known = FALSE;
	mfp_n = 0;
	mfp_owned = mfp_kit = '0 0 0';
	mfp_note = "Loading public profile...";
	mfp_req = Lob_NextReq();
	mfp_at = time;
	dir = cvar_string("lobby_dir");
	if (dir == "")
	{
		mfp_req = 0; mfp_note = "Profile service is not configured.";
		return;
	}
	if (!uri_get(strcat(dir, "/api/board?player=", who, "&limit=", ftos(MFP_ROWS)), mfp_req))
	{
		mfp_req = 0;
		mfp_note = "Profile service unavailable.";
	}
};

float(float reqid, float code, string body) MFP_Reply =
{
	local int root, rows, row, ms, cosmetics, items, activity;
	local float i, n, track, leg, item;
	local string label, name, canonical;
	if (!mfp_req || reqid != mfp_req) return FALSE;
	mfp_req = 0;
	if (!mfp_open || !MF_Online()) return TRUE;
	if (code || strlen(body) > 65536)
	{
		mfp_note = "Profile unavailable; try again shortly.";
		return TRUE;
	}
	root = json_parse(body);
	if (!root) { mfp_note = "Invalid profile reply."; return TRUE; }
	canonical = json_get_string(json_find_object_child(root, "who"));
	if (!MF_Hex(canonical, 12) || strcmp(substring(canonical, 0, strlen(mfp_who)), mfp_who))
	{
		mfp_note = "No public profile found for this player yet.";
		json_free(root);
		return TRUE;
	}
	name = strzone(substring(json_get_string(json_find_object_child(root, "name")), 0, 64));
	if (mfp_name != "") strunzone(mfp_name);
	mfp_name = name;
	name = strzone(canonical);
	strunzone(mfp_who); mfp_who = name;
	mfp_times = json_get_float(json_find_object_child(root, "n"));
	mfp_maps = json_get_float(json_find_object_child(root, "maps"));
	mfp_first = json_get_float(json_find_object_child(root, "wr"));
	cosmetics = json_find_object_child(root, "cosmetics");
	mfp_kit = [json_get_float(json_find_object_child(cosmetics, "roles")), json_get_float(json_find_object_child(cosmetics, "outline")), json_get_float(json_find_object_child(cosmetics, "hat"))];
	items = json_find_object_child(cosmetics, "items");
	mfp_items_known = (items != 0i);
	mfp_owned = '0 0 0';
	n = json_get_length(items);       // MENU min's tail is untyped varargs
	for (i = 0; i < min(16, n); i = i + 1)
	{
		row = json_get_child_at_index(items, i);
		item = json_get_float(json_find_object_child(row, "id"));
		if (item == 1) mfp_owned_x = 1;
		if (item == 2)
		{
			mfp_owned_y = 1;
			mfp_owned_z = bound(0, json_get_float(json_find_object_child(row, "colour")), 11);
		}
	}
	activity = json_find_object_child(root, "playtime");
	mfp_play_known = !strcmp(json_get_string(json_find_object_child(activity, "scope")), "steam_linked_game");
	mfp_play_seconds = max(0, json_get_float(json_find_object_child(activity, "seconds")));
	rows = json_find_object_child(root, "rows");
	n = json_get_length(rows);
	for (i = 0; i < min(MFP_ROWS, n); i = i + 1)
	{
		row = json_get_child_at_index(rows, i);
		label = json_get_string(json_find_object_child(row, "map"));
		track = json_get_float(json_find_object_child(row, "track"));
		leg = json_get_float(json_find_object_child(row, "leg"));
		if (track > 0) label = strcat(label, sprintf(" B%g", track));
		if (leg > 0) label = strcat(label, sprintf(" S%g", leg));
		bufstr_set(mfp_rows, i * 2, label);
		if (checkbuiltin(MFP_JsonInt))
		{
			ms = MFP_JsonInt(json_find_object_child(row, "ms"));
			bufstr_set(mfp_rows, i * 2 + 1, Time_MsString(ms));
		}
		else bufstr_set(mfp_rows, i * 2 + 1, "");
	}
	mfp_n = i;
	mfp_ready = TRUE;
	mfp_note = (mfp_times > i) ? sprintf("Best %g of %g public times", i, mfp_times) : "Public times";
	json_free(root);
	return TRUE;
};

void() MFP_Probe =
{
	print(sprintf("ui_profile_probe: open %g ready %g rows %g times %g req %g note %S\n",
	              mfp_open, mfp_ready, mfp_n, mfp_times, mfp_req, mfp_note));
	print(sprintf("ui_profile_inventory: known %g owned %g/%g equipped %g/%g playtime %g seconds %g\n",
	              mfp_items_known, mfp_owned_x, mfp_owned_y, mfp_kit_y, mfp_kit_z > 0, mfp_play_known, mfp_play_seconds));
};

void(vector pos, vector size) MFP_Draw =
{
	local float i, j, y, tw, cell, ix, left, owned, on, x;
	local string t, id;
	local vector at, colour, a, b, c;
	sui_style_panel(pos, size, 12, 1);
	sui_push_frame(pos, size);
	sui_text('16 12 0', SZ_HEAD, "Player profile", COL_ACCENT, 1, 0);
	if (ui_button("mfp_back", [size_x - 76, 12], [60, 28], "Back")) MFP_Close();
	if (!MP_Draw('16 58 0', 64, mfp_who, 1))
		sui_roundbox('16 58 0', '64 64 0', 8, SUI_THEME_CHIP, 1);
	sui_text('92 66 0', SZ_ROW, ui_fit_text(mfp_name, size_x - 108, SZ_ROW), COL_TEXT, 1, 0);
	t = mfp_play_known ? sprintf("Tracked playtime: %gh %gm", floor(mfp_play_seconds / 3600), floor(mfp_play_seconds / 60) % 60) : "Playtime: not recorded yet";
	if (mfp_ready) sui_text('92 94 0', SZ_LABEL, ui_fit_text(t, size_x - 108, SZ_LABEL), COL_DIM, 1, 0);
	if (mfp_req && time - mfp_at > 8) { mfp_req = 0; mfp_note = "Profile request timed out; reopen to try again."; }
	cell = min(52, floor((size_x - 48) / 8));
	ix = size_x - 16 - cell * 4 - 12;
	left = ix - 28;
	if (mfp_ready)
	{
		sui_text('16 140 0', SZ_LABEL, sprintf("Public times: %g", mfp_times), COL_TEXT, 1, 0);
		sui_text('16 164 0', SZ_LABEL, sprintf("Maps: %g  |  First places: %g", mfp_maps, mfp_first), COL_TEXT, 1, 0);
		sui_text([ix, 140], SZ_LABEL, "INVENTORY (read-only)", COL_DIM, 1, 0);
		for (i = 0; i < 16; i = i + 1)
		{
			at = [ix + (i % 4) * (cell + 4), 168 + floor(i / 4) * (cell + 4)];
			owned = mfp_items_known ? (i == 0 ? mfp_owned_x : (i == 1 ? mfp_owned_y : 0)) : (i == 0 ? mfp_kit_y : (i == 1 ? mfp_kit_z : 0));
			on = i == 0 ? mfp_kit_y : (i == 1 ? mfp_kit_z : 0);
			sui_roundbox(at, [cell, cell], 4, owned ? (on ? SUI_THEME_SELECTED : SUI_THEME_CHIP) : SUI_THEME_WELL, 1);
			if (!owned) continue;
			colour = i == 0 ? '0.4 0.83 1' : sui_inventory_colour(mfp_items_known ? mfp_owned_z : mfp_kit_z - 1);
			if (i == 0)
				sui_roundbox(at + [cell * 0.3, cell * 0.15], [cell * 0.4, cell * 0.48], cell * 0.18, colour, 1);
			else
			{
				sui_fill(at + [cell * 0.18, cell * 0.42], [cell * 0.64, cell * 0.22], colour * 0.85, 1, 0);
				for (j = 0; j < 3; j = j + 1)
				{
					x = 0.28 + j * 0.22;
					a = at + [cell * (x - 0.1), cell * 0.45];
					b = at + [cell * x, cell * 0.15];
					c = at + [cell * (x + 0.1), cell * 0.45];
					sui_transform_point(a); sui_transform_point(b); sui_transform_point(c);
					R_BeginPolygon("", MFP_TWOSIDED, TRUE);
					R_PolygonVertex(a, '0 0 0', colour, 1);
					R_PolygonVertex(b, '0 0 0', colour, 1);
					R_PolygonVertex(c, '0 0 0', colour, 1);
					R_EndPolygon();
				}
			}
			sui_text(at + [4, cell - 13], '10 10 0', on ? "ON" : "OWNED", colour, 1, 0);
			id = sprintf("mfp_item%g", i);
			sui_action_element(at, [cell, cell], id, sui_noop);
			sui_tooltip_for(id, i == 0 ? "Ice aura (read-only)" : "Paper party crown (read-only)", 2);
		}
		if (!mfp_items_known)
			sui_text([ix, 172 + 4 * (cell + 4)], '10 10 0', "Owned items unavailable; equipped only", COL_DIM, 1, 0);
	}
	sui_text('16 204 0', '12 12 0', ui_fit_text(mfp_note, left, '12 12 0'), COL_DIM, 1, 0);
	for (i = 0; i < mfp_n; i = i + 1)
	{
		y = 230 + i * 26;
		if (y + 20 > size_y - 12) break;
		if (i & 1) sui_fill([12, y - 3], [left + 8, 26], COL_ROW, 0.6, 0);
		t = bufstr_get(mfp_rows, i * 2 + 1);
		Font_Set(ui_font_mono); tw = stringwidth(t, TRUE, SZ_LABEL);
		sui_text([left + 16 - tw, y], SZ_LABEL, t, SUI_THEME_GOOD, 1, 0);
		Font_Set(ui_font_ui);
		sui_text([16, y], SZ_LABEL, ui_fit_text(bufstr_get(mfp_rows, i * 2), left - 16 - tw, SZ_LABEL), COL_TEXT, 1, 0);
	}
	sui_pop_frame();
};
