// Public profile preview in the browser's side panel. No capabilities, signing
// keys, arbitrary URLs or external-browser commands. Uses the existing game API.
#define MFP_ROWS 12
float mfp_open, mfp_req, mfp_at, mfp_rows, mfp_init, mfp_n, mfp_ready;
float mfp_times, mfp_maps, mfp_first;
string mfp_who, mfp_name, mfp_note;
int(int node) MFP_JsonInt = #0:json_get_integer;

void() MFP_Close = { mfp_open = FALSE; };
float() MFP_IsOpen = { return mfp_open; };

void(string who, string name) MFP_Open =
{
	if (!MF_Online() || !MF_WhoSafe(who)) return;
	if (mfp_req)
	{
		MF_Note("A profile is still loading; try again shortly.");
		return;
	}
	if (!mfp_init) { mfp_rows = buf_create(); mfp_init = TRUE; }
	if (mfp_who != "") strunzone(mfp_who);
	if (mfp_name != "") strunzone(mfp_name);
	mfp_who = strzone(who);
	mfp_name = strzone(name);
	mfp_open = TRUE;
	mfp_ready = FALSE;
	mfp_n = 0;
	mfp_note = "Loading public profile...";
	mfp_req = Lob_NextReq();
	mfp_at = time;
	if (!uri_get(strcat(MF_SITE, "/api/board?player=", who, "&limit=", ftos(MFP_ROWS)), mfp_req))
	{
		mfp_req = 0;
		mfp_note = "Profile service unavailable.";
	}
};

float(float reqid, float code, string body) MFP_Reply =
{
	local int root, rows, row, ms;
	local float i, n, track, leg;
	local string label, name;
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
	if (!MF_Hex(json_get_string(json_find_object_child(root, "who")), 12))
	{
		mfp_note = "No public runs found for this profile yet.";
		json_free(root);
		return TRUE;
	}
	name = json_get_string(json_find_object_child(root, "name"));
	if (mfp_name != "") strunzone(mfp_name);
	mfp_name = strzone(substring(name, 0, 64));
	mfp_times = json_get_float(json_find_object_child(root, "n"));
	mfp_maps = json_get_float(json_find_object_child(root, "maps"));
	mfp_first = json_get_float(json_find_object_child(root, "wr"));
	rows = json_find_object_child(root, "rows");
	// Patch 991: through a float first.  min is float(float, ...), and an int in
	// its untyped second slot arrived as a denormal: min(6, 3) read ~4e-45, one row.
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
};

// Patch 991: baked sizes only (14 px was a scaled 16 atlas), one row per time,
// times in the mono face right-aligned as on the leaderboard.
void(vector pos, vector size) MFP_Draw =
{
	local float i, y, tw;
	local string t;
	sui_style_panel(pos, size, 12, 1);
	sui_push_frame(pos, size);
	sui_text('16 12 0', SZ_HEAD, "profile", COL_ACCENT, 1, 0);
	if (ui_button("mfp_back", [size_x - 76, 12], [60, 28], "Back")) MFP_Close();
	if (!MP_Draw('16 62 0', 64, mfp_who, 1))
		sui_roundbox('16 62 0', '64 64 0', 8, SUI_THEME_CHIP, 1);
	sui_text('92 76 0', SZ_ROW, ui_fit_text(mfp_name, size_x - 108, SZ_ROW), COL_TEXT, 1, 0);
	if (mfp_ready)
	{
		sui_text('16 140 0', SZ_LABEL, sprintf("Public times: %g", mfp_times), COL_TEXT, 1, 0);
		sui_text('16 164 0', SZ_LABEL, sprintf("Maps: %g", mfp_maps), COL_TEXT, 1, 0);
		sui_text('16 188 0', SZ_LABEL, sprintf("First places: %g", mfp_first), COL_TEXT, 1, 0);
	}
	if (mfp_req && time - mfp_at > 8) mfp_note = "Profile is taking longer than usual.";
	sui_text('16 222 0', '12 12 0', ui_fit_text(mfp_note, size_x - 32, '12 12 0'), COL_DIM, 1, 0);
	for (i = 0; i < mfp_n; i = i + 1)
	{
		y = 246 + i * 26;
		if (y + 20 > size_y - 12) break;
		if (i & 1)
			sui_fill([12, y - 3], [size_x - 24, 26], COL_ROW, 0.6, 0);
		t = bufstr_get(mfp_rows, i * 2 + 1);
		Font_Set(ui_font_mono);
		tw = stringwidth(t, TRUE, SZ_LABEL);
		sui_text([size_x - 16 - tw, y], SZ_LABEL, t, SUI_THEME_GOOD, 1, 0);
		Font_Set(ui_font_ui);
		sui_text([16, y], SZ_LABEL, ui_fit_text(bufstr_get(mfp_rows, i * 2), size_x - 44 - tw, SZ_LABEL),
		         COL_TEXT, 1, 0);
	}
	sui_pop_frame();
};
