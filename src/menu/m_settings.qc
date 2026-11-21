// P1638: Settings as a browser page like Lobbies/Maps: a section rail beside one pane of rows.
// It replaces MH_Settings (m_home.qc) and the VISUALS screen (m_milk.qc); every write is
// theirs, unchanged (cvar_set, MM_Seta, localcmd, localcmd_local). SCREEN_VISUALS still
// opens here, on the section mm_vispage names (milk_bootcheck sets both).

#define MSET_CONTROLS   0
#define MSET_AUDIO      1
#define MSET_SCENE      2
#define MSET_SPEED      3
#define MSET_SKY        4
#define MSET_ONLINE     5
#define MSET_COUNT      6
#define MSET_CH         32      // control height
#define MSET_GAP        8       // between rows
#define MSET_SENS_LO    0.05    // the slider's log travel, as config_menu's (cl_keycfg.qc)
#define MSET_SENS_HI    10

float mset_sec, mset_rows, mset_stacked, mset_contenth, mset_y;
float mset_w, mset_rh, mset_lw, mset_cx, mset_cw, mset_railw, mset_scrolling;
vector mset_scroll, mset_content, mset_panesize, mset_view;

string(float s) MSet_Name =
{
	if (s == MSET_CONTROLS) return "Controls";
	if (s == MSET_AUDIO) return "Audio";
	if (s == MSET_SCENE) return "Menu scene";
	if (s == MSET_SPEED) return "Performance";
	if (s == MSET_SKY) return "In-game sky";
	return "Online & privacy";
};

string(float s) MSet_Sub =
{
	if (s == MSET_CONTROLS) return "Mouse and keys";
	if (s == MSET_AUDIO) return "Volume and menu sound";
	if (s == MSET_SCENE) return "The world behind the menu";
	if (s == MSET_SPEED) return "What the menu's 3D costs";
	if (s == MSET_SKY) return "The visualizer sky";
	return "Terms, updates, journal";
};

string(float s) MSet_Blurb =
{
	if (s == MSET_CONTROLS) return "Sensitivity applies everywhere. Keys and turn speed are set in a game.";
	if (s == MSET_AUDIO) return "Changes apply at once.";
	if (s == MSET_SCENE) return "The sky reacts to your speed, landings and whatever is playing.";
	if (s == MSET_SPEED) return "The menu's alone: a map's sky never uses these.";
	if (s == MSET_SKY) return "Spatial depth and map colours apply when the visualizer sky is on.";
	return "Lobbies, the board and story need the online terms. F2 opens these pages anywhere.";
};

// `ui_settings <word>`'s names, in section order.
string(float s) MSet_Word =
{
	if (s == MSET_CONTROLS) return "controls";
	if (s == MSET_AUDIO) return "audio";
	if (s == MSET_SCENE) return "scene";
	if (s == MSET_SPEED) return "speed";
	if (s == MSET_SKY) return "sky";
	return "online";
};

void(float s) MSet_Open =
{
	mset_sec = bound(0, s, MSET_COUNT - 1);
	mset_scroll = '0 0 0';
	mset_contenth = 0;
	menu_screen = SCREEN_SETTINGS;
};

// The first key bound to `cmd` (-1 is none; other negatives are real keys), or "".
string(string cmd) MSet_Key =
{
	local float k;
	tokenize(findkeysforcommand(cmd));
	if (argv(0) == "") return "";
	k = stof(argv(0));
	if (k == -1) return "";
	return strtoupper(keynumtostring(k));
};

string(string opts, float i) MSet_Opt =
{
	tokenizebyseparator(opts, "|");
	return argv(i);
};

// One row: its well, label and hint. Returns the y its control is drawn at.
float(string label, string hint) MSet_Row =
{
	local float y, cy, tw;
	y = mset_y;
	sui_roundbox([0, y], [mset_w, mset_rh], 8, SUI_THEME_WELL, 0.9);
	tw = mset_stacked ? mset_w - 28 : mset_lw - 28;
	sui_text([14, y + 10], SZ_LABEL, ui_fit_text(label, tw, SZ_LABEL), COL_TEXT, 1, 0);
	sui_text([14, y + 31], '12 12 0', ui_fit_text(hint, tw, '12 12 0'), COL_DIM, 1, 0);
	cy = mset_stacked ? y + 48 : y + floor((mset_rh - MSET_CH) * 0.5);
	mset_y = y + mset_rh + MSET_GAP;
	mset_rows = mset_rows + 1;
	return cy;
};

// A wrapped note under the rows.
void(string text, vector colour) MSet_Note =
{
	mset_y = mset_y + ui_para([4, mset_y + 2], mset_w - 8, '12 12 0', 18, text, colour, TRUE) + 10;
};

/*
  The choices as one segmented row (ids id0..idN-1, as MM_ChipRow named them), or a
  [<] choice [>] stepper (id_prev, id_next) where they do not fit. Returns the index
  clicked, the current one included, or -1.
*/
float(string id, float y, string opts, float cur) MSet_Seg =
{
	local float n, i, x, w, total, hit;
	local string cid;
	n = tokenizebyseparator(opts, "|");
	total = -4;
	for (i = 0; i < n; i = i + 1)
		total = total + max(52, ceil(MT_Width(MSet_Opt(opts, i), 16, 0)) + 24) + 4;
	hit = -1;
	if (total + 8 <= mset_cw)
	{
		x = mset_cx + 4;
		sui_style_box([mset_cx, y - 4], [total + 8, MSET_CH + 8], 10, SUI_THEME_WELL, SUI_THEME_EDGE_HI, 1);
		for (i = 0; i < n; i = i + 1)
		{
			w = max(52, ceil(MT_Width(MSet_Opt(opts, i), 16, 0)) + 24);
			cid = sprintf("%s%g", id, i);
			if (MT_Button(cid, [x, y], [w, MSET_CH], MSet_Opt(opts, i), 0, TRUE, i == cur)) hit = i;
			x = x + w + 4;
		}
	}
	else
	{
		w = min(mset_cw, 300);
		if (MT_Button(strcat(id, "_prev"), [mset_cx, y], [MSET_CH, MSET_CH], "<")) hit = (cur <= 0) ? n - 1 : cur - 1;
		sui_style_box([mset_cx + MSET_CH + 4, y], [w - 2 * MSET_CH - 8, MSET_CH], 7, SUI_THEME_SELECTED, SUI_THEME_ACCENT, 1);
		MT_Place([mset_cx + MSET_CH + 12, y], [w - 2 * MSET_CH - 24, MSET_CH], MSet_Opt(opts, cur), 16, COL_TEXT, 1);
		if (MT_Button(strcat(id, "_next"), [mset_cx + w - MSET_CH, y], [MSET_CH, MSET_CH], ">")) hit = (cur >= n - 1) ? 0 : cur + 1;
	}
	if (hit >= 0)
	{
		MM_Sfx("click", 0.4);
		dprint(sprintf("settings: %s -> %g (%s)\n", id, hit, MSet_Opt(opts, hit)));
	}
	return hit;
};

/*
  [-] track [+] value. The track is sui_slidercontrol (drag, or left/right while
  hovered) writing through `slide` with t in 0..1; returns -1/+1 for the buttons.
*/
float(string id, string downid, string upid, float y, float t, float steps, string value,
      void(float t) slide) MSet_Slider =
{
	local float x, tw, r, kx;
	r = 0;
	x = mset_cx;
	tw = bound(80, mset_cw - 2 * MSET_CH - 104, 360);
	if (MT_Button(downid, [x, y], [MSET_CH, MSET_CH], "-")) r = -1;
	x = x + MSET_CH + 8;
	t = bound(0, t, 1);
	sui_roundbox([x, y + 13], [tw, 6], 3, SUI_THEME_EDGE_HI, 1);
	sui_roundbox([x, y + 13], [max(6, tw * t), 6], 3, COL_ACCENT, 1);
	kx = x + floor(tw * t) - 8;
	sui_slidercontrol(id, [x, y], [tw, MSET_CH], [0, 1, steps], t, slide);
	sui_roundbox([kx, y + 8], '16 16 0', 8, (sui_is_hovered(id) || sui_is_held(id)) ? COL_ACCENT : COL_TEXT, 1);
	x = x + tw + 8;
	if (MT_Button(upid, [x, y], [MSET_CH, MSET_CH], "+")) r = 1;
	x = x + MSET_CH + 8;
	sui_style_box([x, y], [72, MSET_CH], 7, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	MT_Place([x, y], [72, MSET_CH], value, 16, COL_TEXT, 1);
	return r;
};

// A key cap; returns its width.
float(vector pos, string key) MSet_Keycap =
{
	local float w;
	w = max(MSET_CH, ceil(MT_Width(key, 16, 0)) + 20);
	sui_style_box(pos, [w, MSET_CH], 6, SUI_THEME_CHIP, SUI_THEME_EDGE_HI, 1);
	MT_Place(pos, [w, MSET_CH], key, 16, COL_TEXT, 1);
	return w;
};

// Read-only text in the control column, after an optional key cap.
void(float y, string key, string text, vector colour) MSet_Info =
{
	local float x;
	x = mset_cx;
	if (key != "") x = x + MSet_Keycap([x, y], key) + 10;
	MT_Place([x, y], [mset_cx + mset_cw - x, MSET_CH], text, 16, colour);
};

// A status pill after a button, where it fits.
void(float x, float y, string text, vector colour) MSet_PillAt =
{
	if (x + MT_Width(text, 12, 0) + 16 <= mset_cx + mset_cw)
		MT_Pill([x, y + 6], text, colour);
};

// ---------------------------------------------------------------- writes --

float(float v) MSet_SensT = { return log(max(v, MSET_SENS_LO) / MSET_SENS_LO) / log(MSET_SENS_HI / MSET_SENS_LO); };

void(float v) MSet_SensSet =
{
	v = bound(0.05, floor(v * 100 + 0.5) / 100, 100);
	if (v == cvar("sensitivity"))
		return;                             // a held drag lands here every frame
	cvar_set("sensitivity", ftos(v));       // as MH_Settings wrote it (engine-archived)
	dprint(sprintf("settings: sensitivity -> %s\n", ftos(v)));
};

void(float t) MSet_SensSlide = { MSet_SensSet(MSET_SENS_LO * pow(MSET_SENS_HI / MSET_SENS_LO, t)); };

void(float t) MSet_VolSlide =
{
	t = bound(0, t, 1);
	if (t == cvar("volume"))
		return;
	cvar_set("volume", ftos(t));
	dprint(sprintf("settings: volume -> %s\n", ftos(t)));
};

// ---------------------------------------------------------------- sections --

void() MSet_Controls =
{
	local float cy, v, r;
	local string k;
	cy = MSet_Row("Mouse sensitivity", "Drag, or step by 0.05");
	v = cvar("sensitivity");
	r = MSet_Slider("set_sens", "home_sens_down", "home_sens_up", cy, MSet_SensT(v), 0, sprintf("%.2f", v), MSet_SensSlide);
	if (r) MSet_SensSet(v + r * 0.05);
	cy = MSet_Row("Keys and turn speed", "Rebind every action, set turn speed");
	k = MSet_Key("config_menu");
	MSet_Info(cy, k, (k != "") ? "in a game" : "config_menu in a game (no key bound)", COL_DIM);
	cy = MSet_Row("HUD layout", "Move, resize and switch HUD parts");
	k = MSet_Key("hud_edit");
	MSet_Info(cy, k, (k != "") ? "in a game" : "hud_edit in a game (no key bound)", COL_DIM);
};

void() MSet_Audio =
{
	local float cy, v, r, hit;
	cy = MSet_Row("Effects volume", "Every game sound");
	v = cvar("volume");
	r = MSet_Slider("set_vol", "home_vol_down", "home_vol_up", cy, v, 20, sprintf("%g%%", floor(v * 100 + 0.5)), MSet_VolSlide);
	// MH_Settings' steps and bounds.
	if (r < 0) { cvar_set("volume", ftos(max(0, v - 0.05))); dprint("settings: volume down\n"); }
	if (r > 0) { cvar_set("volume", ftos(min(1, v + 0.05))); dprint("settings: volume up\n"); }
	cy = MSet_Row("Menu sounds", "Hover ticks, clicks and flights");
	hit = MSet_Seg("mv_x", cy, "off|on", cvar("milk_sfx") ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_sfx", ftos(hit));
	cy = MSet_Row("Muffle game in menu", "Low-pass a game behind the menu");
	hit = MSet_Seg("mu_l", cy, "off|on", cvar("milk_lowpass") ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_lowpass", ftos(hit));
};

void() MSet_Scene =
{
	local float cy, cur, hit;
	cy = MSet_Row("Menu world", "Changing it dives to the new one");
	hit = MSet_Seg("mv_w", cy, "lattice|monolith|vessel|fractal|shuffle", MM_WorldCur());
	if (hit >= 0)
		MM_Seta("milk_world", (hit == 0) ? "lattice" : ((hit == 1) ? "monolith" : ((hit == 2) ? "vessel" : ((hit == 3) ? "fractal" : "shuffle"))));
	cy = MSet_Row("Light trails", "Feedback trails behind moving light");
	cur = cvar("milk_trails");
	hit = MSet_Seg("mv_t", cy, "off|soft|full", cur <= 0 ? 0 : (cur < 0.9 ? 1 : 2));
	if (hit >= 0) MM_Seta("milk_trails", (hit == 0) ? "0" : ((hit == 1) ? "0.6" : "1"));
	cy = MSet_Row("Colour grade", "The scene's final tint");
	hit = MSet_Seg("mv_g", cy, "natural|cool", cvar("milk_grade") ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_grade", ftos(hit));
	cy = MSet_Row("Kick streaks", "Flashes on the beat");
	hit = MSet_Seg("mv_k", cy, "off|menu|menu + sky", bound(0, cvar("milk_streaks"), 2));
	if (hit >= 0) MM_Seta("milk_streaks", ftos(hit));
	cy = MSet_Row("Audio reactivity", "How hard it follows the sound");
	cur = cvar("milk_react");
	hit = MSet_Seg("mv_r", cy, "off|normal|wild", cur <= 0 ? 0 : (cur < 1.5 ? 1 : 2));
	if (hit >= 0) MM_Seta("milk_react", (hit == 0) ? "0" : ((hit == 1) ? "1" : "2"));
	cy = MSet_Row("Menu panels", "Flat, or on a slab in the 3D scene");
	hit = MSet_Seg("mv_p", cy, "flat|in the world", MM_InWorld() ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_panels", ftos(hit));
	cy = MSet_Row("Loading-screen models", "Models drawn while a map loads");
	hit = MSet_Seg("home_lwire", cy, "side on|from above", cvar("ls_wireangle") >= 22.5);
	if (hit >= 0) MM_Seta("ls_wireangle", hit ? "45" : "0");     // P1453
	if (!milk_hasvis)
		MSet_Note("This engine has no audio analysis -- the scene runs without the music.", SUI_THEME_WARN);
};

void() MSet_Speed =
{
	local float cy, cur, hit;
	local string fsr;
	cy = MSet_Row("Menu scene", "Off is the menu without its 3D world");
	cur = cvar("milk_menu") ? bound(1, cvar("milk_quality"), 4) : 0;
	hit = MSet_Seg("mv_q", cy, "off|low|medium|high|ultra", cur);
	if (hit == 0)
		MM_Seta("milk_menu", "0");
	else if (hit > 0)
	{
		MM_Seta("milk_menu", "1");
		MM_Seta("milk_quality", ftos(hit));
	}
	cy = MSet_Row("Resolution", "Native renders at the screen's size");
	hit = MSet_Seg("mv_res", cy, "by quality|native", cvar("milk_res") ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_res", ftos(hit));
	cy = MSet_Row("Upscaler", "How a smaller render is stretched");
	hit = MSet_Seg("mv_fsr", cy, "bilinear|FSR 1", cvar("milk_fsr") ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_fsr", ftos(hit));
	cy = MSet_Row("Checkerboard", "Raymarch half the pixels a frame");
	hit = MSet_Seg("mv_cb", cy, "off|on", cvar("milk_checker") ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_checker", ftos(hit));
	cy = MSet_Row("Coarse pass", "A cheap pre-pass before the march");
	hit = MSet_Seg("mv_cp", cy, "off|on", cvar("milk_cone") ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_cone", ftos(hit));
	cy = MSet_Row("Right now", "Live, as the scene draws");
	fsr = "";
	if (milk_cfgup_x > 0) fsr = sprintf(", FSR to %gx%g", milk_cfgup_x, milk_cfgup_y);
	MSet_Info(cy, "", sprintf("renders %gx%g, the 3D %gx%g%s, %g fps", milk_rtsize_x, milk_rtsize_y,
	          milk_scsize_x, milk_scsize_y, fsr, rint(1 / max(mm_ftime, 0.0005))), COL_TEXT);
};

void() MSet_Sky =
{
	local float cy, hit, supported;
	cy = MSet_Row("In-game sky", "A map's own sky, or the visualizer");
	hit = MSet_Seg("mv_s", cy, "map's own|visualizer", cvar("milk_sky") ? 1 : 0);
	if (hit >= 0)
	{
		MM_Seta("milk_sky", ftos(hit));
		// r_skybox is not archived: csprogs re-applies milk_sky at every map. P1683: so with no map there is
		// no sky to change (each change re-parsed every shader before the engine's P1683: a menu hitch).
		if (clientstate() == 2)
			localcmd(hit ? "r_skybox milk\n" : "r_skybox \"\"\n");
	}
	cy = MSet_Row("Sky perspective", "Spatial gives the sky depth");
	hit = MSet_Seg("mv_depth", cy, "fixed|spatial", cvar("milk_sky_parallax") ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_sky_parallax", ftos(hit));
	cy = MSet_Row("Sky colours", "Palette from the map's picture");
	hit = MSet_Seg("mv_pal", cy, "original|map thumbnail", cvar("milk_sky_palette") ? 1 : 0);
	if (hit >= 0) MM_Seta("milk_sky_palette", ftos(hit));
	supported = cvar_type("snd_vis_source");
	if (supported)
		supported = cvar("snd_vis_loopback_supported");
	cy = MSet_Row("Audio source", "What the visualizer listens to");
	if (supported)
	{
		hit = MSet_Seg("mv_source", cy, "game mix|desktop audio", cvar("snd_vis_source") == 1 ? 1 : 0);
		if (hit >= 0)
		if (checkbuiltin(localcmd_local))
		{
			localcmd_local(sprintf("seta snd_vis_source %g\n", hit));
			if (hit == 1)
				MM_Play("");
			else
				mm_autoplayed = FALSE;
		}
		MSet_Note("Desktop audio is what your speakers play: your music and the game. Nothing is recorded or sent.", COL_DIM);
	}
	else
		MSet_Info(cy, "", (cvar_defstring("snd_vis_source") == "1") ? "the game's own sound (desktop audio needs PulseAudio or PipeWire)"
		          : "the game's own sound (update the game for desktop audio)", COL_DIM);
};

void() MSet_Online =
{
	local float cy, w, online;
	online = (ms_consent >= FS_TERMS_ONLINE);
	cy = MSet_Row("Online play", online ? "Lobbies, boards and story are on" : "Offline only until you accept");
	w = ceil(MT_Width("Privacy & online terms", 16, 0)) + 32;
	// P1703 review 2: through F2's Terms page (Back returns here), not the bare first-boot screen
	if (MT_Button("home_privacy", [mset_cx, cy], [w, MSET_CH], "Privacy & online terms")) { ui_f2_open("terms"); ui_f2_back = SCREEN_SETTINGS; }
	MSet_PillAt(mset_cx + w + 12, cy, online ? "ONLINE" : "OFFLINE", online ? SUI_THEME_GOOD : SUI_THEME_WARN);
	// F2's pages; Back there returns here (ui_f2_back).
	cy = MSet_Row("Patch notes", "What changed in each build");
	if (MT_Button("set_notes", [mset_cx, cy], [96, MSET_CH], "Open")) { ui_f2_open("notes"); ui_f2_back = SCREEN_SETTINGS; }
	cy = MSet_Row("Updates", "Check for and install a release");
	if (MT_Button("set_updates", [mset_cx, cy], [96, MSET_CH], "Open")) { ui_f2_open("updates"); ui_f2_back = SCREEN_SETTINGS; }
	cy = MSet_Row("Input journal", "Uploads for private anti-cheat review");
	if (MT_Button("set_journal", [mset_cx, cy], [96, MSET_CH], "Open")) { ui_f2_open("journal"); ui_f2_back = SCREEN_SETTINGS; }
	MSet_PillAt(mset_cx + 108, cy, cvar("rec_hid_upload") ? "UPLOADS ON" : "UPLOADS OFF", cvar("rec_hid_upload") ? SUI_THEME_GOOD : COL_DIM);
};

// ---------------------------------------------------------------- layout --

// The section rail, a panel at pos.
void(vector pos, vector size) MSet_Rail =
{
	local float i, y, ih, on, hot;
	local string id, ver;
	sui_style_panel(pos, size, 12, 1);
	sui_push_frame(pos, size);
	sui_text('16 12 0', SZ_HEAD, "Settings", COL_ACCENT, 1, 0);
	ih = (size_y >= 480) ? 52 : 36;
	y = 52;
	for (i = 0; i < MSET_COUNT; i = i + 1)
	{
		id = sprintf("set_sec%g", i);
		sui_action_element([8, y], [size_x - 16, ih], id, sui_noop);
		on = (mset_sec == i);
		hot = sui_is_hovered(id);
		if (on || hot) sui_roundbox([8, y], [size_x - 16, ih], 8, on ? COL_ROW_SEL : COL_ROW_HOVER, 1);
		if (on) sui_roundbox([8, y + 10], [3, ih - 20], 1, COL_ACCENT, 1);
		sui_text([22, y + (ih >= 52 ? 9 : 10)], SZ_LABEL, ui_fit_text(MSet_Name(i), size_x - 40, SZ_LABEL), on ? COL_ACCENT : COL_TEXT, 1, 0);
		if (ih >= 52)
			sui_text([22, y + 31], '12 12 0', ui_fit_text(MSet_Sub(i), size_x - 40, '12 12 0'), COL_DIM, 1, 0);
		if (sui_is_released(id)) MSet_Open(i);
		y = y + ih + 4;
	}
	ver = cvar_string("ui_menu_version");
	if (ver != "")
	if (size_y - 28 > y)
		sui_text([16, size_y - 28], '12 12 0', ui_fit_text(strcat("World of Surf ", ver), size_x - 32, '12 12 0'), SUI_THEME_MUTED, 1, 0);
	sui_pop_frame();
};

// Narrow: the sections as a wrapping row of buttons; returns the height used.
float(float width) MSet_Strip =
{
	local float i, x, y, w;
	x = y = 0;
	for (i = 0; i < MSET_COUNT; i = i + 1)
	{
		w = ceil(MT_Width(MSet_Name(i), 16, 0)) + 28;
		if (x > 0 && x + w > width) { x = 0; y = y + MSET_CH + 6; }
		if (MT_Button(sprintf("set_sec%g", i), [x, y], [w, MSET_CH], MSet_Name(i), 0, TRUE, mset_sec == i)) MSet_Open(i);
		x = x + w + 6;
	}
	return y + MSET_CH;
};

void(vector pos, vector size) MSet_Pane =
{
	local float top;
	sui_style_panel(pos, size, 12, 1);
	sui_push_frame(pos, size);
	sui_text('16 12 0', SZ_HEAD, MSet_Name(mset_sec), COL_ACCENT, 1, 0);
	sui_text('16 44 0', SZ_LABEL, ui_fit_text(MSet_Blurb(mset_sec), size_x - 32, SZ_LABEL), COL_DIM, 1, 0);
	top = 76;
	mset_view = [size_x - 32, size_y - top - 12];
	// Last frame's height decides the gutter, so a section change settles in one frame.
	mset_scrolling = (mset_contenth > mset_view_y);
	mset_w = mset_view_x - (mset_scrolling ? 14 : 0);
	mset_stacked = (mset_w < 560);
	mset_rh = mset_stacked ? 90 : 56;
	mset_lw = bound(200, floor(mset_w * 0.34), 300);
	mset_cx = mset_stacked ? 14 : mset_lw;
	mset_cw = mset_w - mset_cx - 12;
	sui_scroll_view_begin("set_rows", [16, top], mset_view, [mset_w, max(1, mset_contenth)], mset_scroll,
	                      [0, mset_scrolling ? 14 : 0], 40);
	mset_y = 0;
	mset_rows = 0;
	if (mset_sec == MSET_CONTROLS) MSet_Controls();
	else if (mset_sec == MSET_AUDIO) MSet_Audio();
	else if (mset_sec == MSET_SCENE) MSet_Scene();
	else if (mset_sec == MSET_SPEED) MSet_Speed();
	else if (mset_sec == MSET_SKY) MSet_Sky();
	else MSet_Online();
	mset_contenth = mset_y - MSET_GAP;
	sui_scroll_view_end();
	sui_pop_frame();
};

void(vector size) MSet_Draw =
{
	local float h;
	mt_fit_used = 0;                // MT_Place's per-frame cache slots, as MT_Draw resets them
	if (menu_screen == SCREEN_VISUALS)
		mset_sec = (mm_vispage == 1) ? MSET_SPEED : ((mm_vispage == 2) ? MSET_SKY : MSET_SCENE);
	mset_content = size;
	if (size_x >= 700)
	{
		mset_railw = bound(196, floor(size_x * 0.22), 250);
		MSet_Rail('0 0 0', [mset_railw, size_y]);
		mset_panesize = [size_x - mset_railw - 12, size_y];
		MSet_Pane([mset_railw + 12, 0], mset_panesize);
	}
	else
	{
		mset_railw = 0;
		h = MSet_Strip(size_x);
		mset_panesize = [size_x, size_y - h - 12];
		MSet_Pane([0, h + 12], mset_panesize);
	}
};

void() MSet_Probe =
{
	print(sprintf("settings: screen %g section %g %s content %gx%g rail %g\n", menu_screen, mset_sec,
	              MSet_Word(mset_sec), mset_content_x, mset_content_y, mset_railw));
	print(sprintf("settings: pane %gx%g view %gx%g rows %g height %g\n", mset_panesize_x, mset_panesize_y,
	              mset_view_x, mset_view_y, mset_rows, mset_contenth));
	print(sprintf("settings: scroll %g scrolling %g stacked %g label %g control %g+%g\n", mset_scroll_y,
	              mset_scrolling, mset_stacked, mset_lw, mset_cx, mset_cw));
};

// ui_settings [controls|audio|scene|speed|sky|online|probe]
void(string arg) MSet_Command =
{
	local float i;
	if (arg == "probe") { MSet_Probe(); return; }
	if (menu_screen != SCREEN_SETTINGS) MSet_Open(mset_sec);
	for (i = 0; i < MSET_COUNT; i = i + 1)
		if (arg == MSet_Word(i)) MSet_Open(i);
	print(sprintf("ui_settings: open %s\n", MSet_Word(mset_sec)));
};
