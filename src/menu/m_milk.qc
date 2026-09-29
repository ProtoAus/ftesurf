/*
  m_milk.qc -- the menu's 3D space and the VISUALS / MUSIC screens.  Patch 467.

  Melee's menu, abstractly: each screen is a place in one space and changing
  screen flies the camera there.  The space is raymarched by
  glsl/milk_scene.glsl through milk_sys.qc's feedback pipeline, so it costs no
  map and no server, and runs in menu.dat, where a BSP cannot be drawn.

      MAIN     the cube lattice            PLAY     the tower field (spectrum)
      VISUALS  the ring tunnel, folded     MUSIC    the liquid pool

  Only while DISCONNECTED.  Over a live game the old translucent backdrop
  stays: a run keeps recording while the menu is up (cl_main.qc:1338), and the
  menu must not take frames from it.

  Compiled after m_main.qc, which calls in through prototypes declared beside
  its SCREEN_* defines.
*/

#define MS_MAIN     0
#define MS_PLAY     1
#define MS_VIS      2
#define MS_MUSIC    3
#define MM_FLIGHT   1.7         // seconds per flight between stations
#define MM_TRACKS   48
#define MM_TITLE_SZ '80 80 0'
#define MM_ITEM_SZ  '48 48 0'
#define MM_ITEM_H   64

float  mm_station, mm_flight0;
vector mm_pos0, mm_tgt0;
float  mm_hue0, mm_liq0, mm_kal0;
vector mm_pos, mm_tgt;
float  mm_hue, mm_liq, mm_kal;
vector mm_ppos, mm_ptgt;        // MM_Pose's answer
float  mm_phue, mm_pliq, mm_pkal;
float  mm_yaw, mm_pitch, mm_yawv;
float  mm_nudgeyaw, mm_nudgepitch, mm_nudge;
vector mm_screen;
float  mm_last, mm_asp;
float  mm_hlon, mm_hlnext;
vector mm_titlepos, mm_titlecur;   // MM_Title's position last frame, for the feedback glow; x < 0 = none
vector mm_hlpos, mm_hlsize;
float  mm_itemx[4];             // eased hover offset per main item

string mm_track[MM_TRACKS];
float  mm_ntracks, mm_trackscan, mm_autoplayed;
string mm_playing;
float  mm_lowpassed;

float  mm_bc_step, mm_bc_t0, mm_bc_consent, mm_bc_frames;

vector(vector a, vector b) MM_Cross =
{
	return [a_y * b_z - a_z * b_y, a_z * b_x - a_x * b_z, a_x * b_y - a_y * b_x];
};

float(float n) MM_Hash =
{
	n = sin(n * 12.9898 + 4.1414) * 43758.5453;
	return n - floor(n);
};

// Camera pose, hue and feedback character for one station.
void(float st) MM_Pose =
{
	if (st == MS_PLAY)
	{
		mm_ppos = '44 5 -26';    mm_ptgt = '64 2 2';
		mm_phue = 0.30;          mm_pliq = 0;     mm_pkal = 0;
	}
	else if (st == MS_VIS)
	{
		mm_ppos = '0 3 55';      mm_ptgt = '0 3 72';
		mm_phue = 0.62;          mm_pliq = 0.2;   mm_pkal = 6;
	}
	else if (st == MS_MUSIC)
	{
		mm_ppos = '-64 3.4 -16'; mm_ptgt = '-64 1.7 4';
		mm_phue = 0.86;          mm_pliq = 0.85;  mm_pkal = 0;
	}
	else
	{
		mm_ppos = '1.6 2.7 -10'; mm_ptgt = '-1.9 3.1 0';
		mm_phue = 0.02;          mm_pliq = 0.1;   mm_pkal = 0;
	}
};

float() MM_StationFor =
{
	if (menu_screen == SCREEN_CREATE)  return MS_PLAY;
	if (menu_screen == SCREEN_VISUALS) return MS_VIS;
	if (menu_screen == SCREEN_MUSIC)   return MS_MUSIC;
	return MS_MAIN;
};

void(float st) MM_Go =
{
	if (st == mm_station)
		return;
	mm_pos0 = mm_pos;  mm_tgt0 = mm_tgt;
	mm_hue0 = mm_hue;  mm_liq0 = mm_liq;  mm_kal0 = mm_kal;
	mm_station = st;
	mm_flight0 = gettime(0);
};

float() MM_Active =
{
	return cvar("milk_menu") > 0 && clientstate() != 2 && Milk_Supported();
};

vector(vector p) MM_Project =
{
	local vector d;
	local float z;

	d = p - milk_campos;
	z = d * milk_camfwd;
	if (z < 0.1)
		return '0.5 0.5 0';
	return [0.5 + 0.5 * (d * milk_camright) / (z * milk_tanfov * mm_asp),
	        0.5 - 0.5 * (d * milk_camup) / (z * milk_tanfov), z];
};

// The hue walks the short way round the palette.
float(float a, float b, float e) MM_HueLerp =
{
	local float d;
	d = b - a;
	d = d - floor(d + 0.5);
	return a + d * e;
};

void(float now, float dt) MM_Camera =
{
	local float f, e, trav, k, ty, tp;
	local vector ctrl, m, fwd, right, up, sway, anchor, fc;

	MM_Pose(mm_station);
	trav = 0;
	if (mm_flight0)
	{
		f = (now - mm_flight0) / MM_FLIGHT;
		if (f >= 1)
		{
			f = 1;
			mm_flight0 = 0;
		}
		e = f * f * (3 - 2 * f);
		// Quadratic arc that lifts over the floor between two stations.
		ctrl = (mm_pos0 + mm_ppos) * 0.5 + [0, 6 + vlen(mm_ppos - mm_pos0) * 0.18, 0];
		mm_pos = mm_pos0 * ((1 - e) * (1 - e)) + ctrl * (2 * e * (1 - e)) + mm_ppos * (e * e);
		mm_tgt = mm_tgt0 + (mm_ptgt - mm_tgt0) * e;
		mm_hue = MM_HueLerp(mm_hue0, mm_phue, e);
		mm_liq = mm_liq0 + (mm_pliq - mm_liq0) * e;
		mm_kal = (e < 0.5) ? mm_kal0 : mm_pkal;
		trav = sin(f * 3.14159265);
	}
	else
	{
		mm_pos = mm_ppos;  mm_tgt = mm_ptgt;
		mm_hue = mm_phue;  mm_liq = mm_pliq;  mm_kal = mm_pkal;
	}

	// A slow sway so a settled view is never a still.
	sway = [sin(now * 0.13) * 0.7, sin(now * 0.17) * 0.3, cos(now * 0.11) * 0.5];
	fwd = normalize(mm_tgt - (mm_pos + sway * (1 - trav)));

	// Mouse look, plus the hovered item's nudge toward where it would fly.
	m = getmousepos();
	ty = (m_x / max(mm_screen_x, 1) - 0.5) * 16 + mm_nudgeyaw * mm_nudge;
	tp = (0.5 - m_y / max(mm_screen_y, 1)) * 8 + mm_nudgepitch * mm_nudge;
	k = 1 - pow(2.7182818, -dt * 3.5);
	mm_yawv = (ty - mm_yaw) * k;
	mm_yaw += mm_yawv;
	mm_pitch += (tp - mm_pitch) * k;

	right = normalize(MM_Cross('0 1 0', fwd));
	fwd = normalize(fwd * cos(mm_yaw * 0.01745) + right * sin(mm_yaw * 0.01745));
	right = normalize(MM_Cross('0 1 0', fwd));
	up = MM_Cross(fwd, right);
	fwd = normalize(fwd * cos(mm_pitch * 0.01745) + up * sin(mm_pitch * 0.01745));
	up = MM_Cross(fwd, right);

	milk_campos = mm_pos + sway * (1 - trav);
	milk_camfwd = fwd;
	milk_camright = right;
	milk_camup = up;
	milk_tanfov = 0.60;
	milk_travel = trav;
	milk_hue = mm_hue;
	milk_liquid = mm_liq;
	milk_kaleido = mm_kal;

	// Feedback character: calm when settled, hyperspace in flight.
	milk_zoom = 1.004 + 0.045 * trav + 0.012 * milk_beat_bass * milk_react;
	milk_rot = 0.0015 * sin(now * 0.05) - mm_yawv * 0.004;
	milk_decay = 0.84 + 0.11 * trav;
	milk_wobble = 0.4 + 0.9 * milk_mid_att * milk_react;
	milk_trails = cvar("milk_trails");
	milk_react = cvar("milk_react");
	milk_bloom = 1;
	milk_exposure = 1.1;
	milk_flash = milk_beat * milk_react;

	// Trails radiate from the landmark, not the middle of the screen.
	if (mm_station == MS_MAIN)
		anchor = '0 3.4 0';
	else if (mm_station == MS_PLAY)
		anchor = '64 3 0';
	else if (mm_station == MS_VIS)
		anchor = '0 3 90';
	else
		anchor = '-64 0 0';
	fc = MM_Project(anchor);
	fc_x = bound(0.15, fc_x, 0.85);
	fc_y = bound(0.15, fc_y, 0.85);
	milk_focus_x = fc_x * (1 - trav) + 0.5 * trav;
	milk_focus_y = fc_y * (1 - trav) + 0.5 * trav;

	// Present-time parallax: what the mouse did since the sim last looked.
	milk_offset = [(ty - mm_yaw) * 0.0007, (tp - mm_pitch) * -0.0007, 0];
};

// Into the fresh feedback frame, once per tick: drifting motes around the
// station, and the highlight bar under whatever the menu has selected.
void() MM_Sprites =
{
	local float i, h1, h2, h3, t, rad, tw;
	local vector c, p, s, col, hp, hs;

	t = milk_simtime;
	c = mm_tgt;
	for (i = 0; i < 64; i++)
	{
		h1 = MM_Hash(i * 3.1 + 0.7);
		h2 = MM_Hash(i * 5.7 + 1.3);
		h3 = MM_Hash(i * 7.9 + 2.9);
		p_x = c_x + (h1 - 0.5) * 24 + sin(t * 0.21 + i) * 0.8;
		p_y = (h2 + t * (0.012 + 0.03 * h3)) - floor(h2 + t * (0.012 + 0.03 * h3));
		p_y = p_y * 10 - 1.5 + c_y;
		p_z = c_z + (h3 - 0.5) * 24 + cos(t * 0.17 + i * 1.7) * 0.8;
		s = MM_Project(p);
		if (s_z < 0.8 || s_x < -0.05 || s_x > 1.05 || s_y < -0.05 || s_y > 1.05)
			continue;
		rad = bound(1.5, 0.12 / (s_z * milk_tanfov) * milk_rtsize_y * 0.5, 22);
		tw = 0.5 + 0.5 * sin(t * (1.3 + h1 * 3.5) + i * 2.1);
		col = Milk_Pal(mm_hue + h2 * 0.35 + 0.2);
		Milk_Dot([s_x * milk_rtsize_x, s_y * milk_rtsize_y], rad, col,
		         0.07 + 0.16 * tw * (0.5 + milk_treb_att * milk_react));
	}

	// The title's halo: the same word, faint and additive, INTO the feedback
	// frame -- the trails and the bloom turn it into light.  Only the crisp copy
	// on top is at the font's native size.
	if (mm_titlecur_x >= 0)
	{
		Font_Set(ui_font_display);
		drawstring(Milk_ToRT(mm_titlecur, mm_screen), "FTESURF",
		           MM_TITLE_SZ * (milk_rtsize_y / mm_screen_y), Milk_Pal(mm_hue + 0.1),
		           0.10 + 0.12 * milk_beat * milk_react, 1);
		Font_Set(ui_font_ui);
	}

	if (mm_hlon)
	{
		hp = Milk_ToRT(mm_hlpos, mm_screen);
		hs = Milk_ToRT(mm_hlsize, mm_screen);
		Milk_Bar(hp, hs, Milk_Pal(mm_hue + 0.1), 0.22 + 0.35 * milk_beat * milk_react);
	}
};

// Menu music: whatever sits in music/, played with the engine's own `music`
// command (which loops it).  Only .ogg/.wav/.mp3 -- the extensions
// Media_NamedTrack resolves on a bare name.
void() MM_MusicScan =
{
	local searchhandle h;
	local float n, i;
	local string f, e;

	for (i = 0; i < mm_ntracks; i++)
		strunzone(mm_track[i]);
	mm_ntracks = 0;
	mm_trackscan = TRUE;

	h = search_begin("music/*", SB_NAMESORT, TRUE);
	if (h < 0)
		return;
	n = search_getsize(h);
	for (i = 0; i < n && mm_ntracks < MM_TRACKS; i++)
	{
		f = search_getfilename(h, i);
		e = strtolower(substring(f, strlen(f) - 4, 4));
		if (e != ".ogg" && e != ".wav" && e != ".mp3")
			continue;
		mm_track[mm_ntracks] = strzone(substring(f, 6, strlen(f) - 10));
		mm_ntracks++;
	}
	search_end(h);
};

void(string name) MM_Play =
{
	if (mm_playing != "")
		strunzone(mm_playing);
	mm_playing = strzone(name);
	if (name == "")
		localcmd("stopmusic\n");
	else
		localcmd(sprintf("music \"%s\"\n", name));
};

void() MM_MusicAuto =
{
	local string want;

	if (mm_autoplayed)
		return;
	mm_autoplayed = TRUE;
	want = cvar_string("milk_menumusic");
	if (want == "")
		return;
	if (!mm_trackscan)
		MM_MusicScan();
	if (want == "auto")
	{
		if (!mm_ntracks)
			return;
		want = mm_track[0];
	}
	MM_Play(want);
};

void() MM_Init =
{
	registercvar("milk_menu", "1", 32);         // 32 = CVAR_ARCHIVE
	registercvar("milk_quality", "2", 32);
	registercvar("milk_trails", "1", 32);
	registercvar("milk_react", "1", 32);
	registercvar("milk_sky", "0", 32);
	registercvar("milk_menumusic", "auto", 32);
	registercvar("milk_lowpass", "1", 32);
	registercvar("milk_bootcheck", "0", 0);

	Milk_Init("mm", "milk_scene", "milk_warp", "milk_comp");
	milk_sprites = MM_Sprites;
	mm_station = MS_MAIN;
	MM_Pose(MS_MAIN);
	mm_pos = mm_ppos;  mm_tgt = mm_ptgt;
	mm_hue = mm_phue;  mm_liq = mm_pliq;
	mm_playing = "";
};

// Before sui_begin every frame: the sim, if the backdrop wants it.
void(vector screensize) MM_Frame =
{
	local float now, dt, q, h;
	local vector size;

	mm_screen = screensize;
	mm_hlon = mm_hlnext;
	mm_hlnext = FALSE;
	mm_titlecur = mm_titlepos;
	mm_titlepos_x = -1;
	mm_nudge = mm_nudge * 0.9;

	// Disconnecting with the menu open never passes through m_close, so the
	// muffle from MM_Open would otherwise follow you onto the main menu.
	if (mm_lowpassed)
	if (clientstate() != 2)
		MM_Close();

	if (!MM_Active())
		return;

	if (clientstate() != 2)
		MM_MusicAuto();

	now = gettime(0);
	dt = bound(0, now - mm_last, 0.1);
	mm_last = now;

	MM_Go(MM_StationFor());

	// Internal height by quality: 360 / 540 / 720, width by aspect.
	q = bound(1, cvar("milk_quality"), 3);
	h = 180 + q * 180;
	if (h > screensize_y)
		h = screensize_y;
	size = [floor(h * screensize_x / screensize_y), h];
	mm_asp = size_x / size_y;
	milk_quality = q;
	milk_scenescale = (q >= 3) ? 1 : 0.75;   // the raymarch is the cost; see Patch 467 perf

	MM_Camera(now, dt);
	Milk_Frame(size, now);
};

// Readability: darken the left of the screen where the menu column sits.  One
// quad with alpha per vertex (milk_shade) -- flat strips band visibly over a
// bright station.  The mid vertex column bends the ramp toward the left.
void(vector screensize, float frac, float alpha) MM_Shade =
{
	local float w, h;

	// Only over the 3D space; and milk_shade is a GLSL program, which on a
	// non-GL renderer falls back to a hard black half-screen.
	if (!MM_Active())
		return;
	w = screensize_x * frac;
	h = screensize_y;
	R_BeginPolygon("milk_shade", 0, TRUE);
	R_PolygonVertex('0 0 0', '0 0 0', '0.01 0.01 0.03', alpha);
	R_PolygonVertex([w * 0.55, 0], '0 0 0', '0.01 0.01 0.03', alpha * 0.55);
	R_PolygonVertex([w * 0.55, h], '0 0 0', '0.01 0.01 0.03', alpha * 0.55);
	R_PolygonVertex([0, h], '0 0 0', '0.01 0.01 0.03', alpha);
	R_EndPolygon();
	R_BeginPolygon("milk_shade", 0, TRUE);
	R_PolygonVertex([w * 0.55, 0], '0 0 0', '0.01 0.01 0.03', alpha * 0.55);
	R_PolygonVertex([w, 0], '0 0 0', '0.01 0.01 0.03', 0);
	R_PolygonVertex([w, h], '0 0 0', '0.01 0.01 0.03', 0);
	R_PolygonVertex([w * 0.55, h], '0 0 0', '0.01 0.01 0.03', alpha * 0.55);
	R_EndPolygon();
};

void(vector screensize) MM_Backdrop =
{
	Milk_Present('0 0 0', screensize, 1);
};

/*
  One main-menu entry: Bebas at 48, an eased slide to the right on hover, a
  crisp accent bar, and the same bar mirrored into the feedback frame (where
  the warp smears it into the glow and the ghost trail).  Returns the click.
*/
float(float idx, string id, vector pos, string label, float nyaw, float npitch) MM_Item =
{
	local float w, hot, k;
	local vector acc, col;

	Font_Set(ui_font_display);
	w = stringwidth(label, TRUE, MM_ITEM_SZ);
	sui_action_element(pos, [w + 90, MM_ITEM_H - 6], id, sui_noop);
	hot = sui_is_hovered(id);

	k = hot ? 1 : 0;
	mm_itemx[idx] += (k - mm_itemx[idx]) * 0.2;
	acc = Milk_Pal(mm_hue + 0.1);

	if (hot)
	{
		mm_hlnext = TRUE;
		mm_hlpos = pos + [-20, 10];
		mm_hlsize = [w + 130, MM_ITEM_H - 18];
		mm_nudgeyaw = nyaw;
		mm_nudgepitch = npitch;
		mm_nudge = 1;
	}

	if (mm_itemx[idx] > 0.01)
		sui_fill(pos + [-16, 12], [4, MM_ITEM_H - 26], acc, mm_itemx[idx], 0);

	col = '0.70 0.72 0.80' * (1 - mm_itemx[idx]) + (acc * 0.45 + '0.6 0.6 0.6') * mm_itemx[idx];
	sui_text(pos + [floor(22 * mm_itemx[idx]), 4], MM_ITEM_SZ, label, col, 0.8 + 0.2 * k, 0);
	Font_Set(ui_font_ui);
	return sui_is_released(id);
};

// The title, with a halo of offset additive copies in the station colour.
void(vector pos) MM_Title =
{
	local float i;
	local vector acc;

	acc = Milk_Pal(mm_hue + 0.1);
	mm_titlepos = pos;
	Font_Set(ui_font_display);
	for (i = 0; i < 8; i++)
		drawstring(pos + [cos(i * 0.785) * 3, sin(i * 0.785) * 3], "FTESURF", MM_TITLE_SZ,
		           acc, 0.16 + 0.10 * milk_beat * milk_react, 1);
	sui_text(pos, MM_TITLE_SZ, "FTESURF", '0.95 0.97 1', 1, 0);
	Font_Set(ui_font_ui);
};

void(vector screensize) MM_ScreenMain =
{
	local float x, y;

	MM_Shade(screensize, 0.5, 0.75);

	x = floor(screensize_x * 0.075);
	y = floor(screensize_y * 0.5) - 110;

	MM_Title([x, y - 150]);
	sui_text([x + 4, y - 62], SZ_LABEL, "Counter-Strike: Source movement", COL_DIM, 1, 0);

	if (MM_Item(0, "mm_play", [x, y], "PLAY", 16, 0))
	{
		menu_screen = SCREEN_CREATE;
		ui_create_open();
		ui_refilter();
	}
	if (MM_Item(1, "mm_vis", [x, y + MM_ITEM_H], "VISUALS", 0, 6))
		menu_screen = SCREEN_VISUALS;
	if (MM_Item(2, "mm_music", [x, y + MM_ITEM_H * 2], "MUSIC", -16, 0))
	{
		menu_screen = SCREEN_MUSIC;
		MM_MusicScan();
	}
	if (MM_Item(3, "mm_quit", [x, y + MM_ITEM_H * 3], "QUIT", 0, -4))
		localcmd("quit\n");

	if (clientstate() == 2)
		sui_text([x + 4, y + MM_ITEM_H * 4 + 16], SZ_LABEL,
		         sprintf("^9esc  back to %s", serverkey("map")), COL_DIM, 1, 0);
	else if (MM_Active())
		sui_text([x + 4, screensize_y - 48], SZ_LABEL,
		         "^9move the mouse to look around", COL_DIM, 1, 0);
};

// One labelled row of chips; returns the index clicked, or -1.
float(vector pos, string id, string label, string opts, float cur) MM_ChipRow =
{
	local float n, i, x, hit;
	local string cid;

	sui_text(pos + '0 5 0', SZ_LABEL, label, COL_TEXT, 1, 0);
	n = tokenizebyseparator(opts, "|");
	x = pos_x + 340;
	hit = -1;
	for (i = 0; i < n; i++)
	{
		cid = sprintf("%s%g", id, i);
		x += ui_chip([x, pos_y], cid, argv(i), i == cur) + CHIP_GAP;
		if (sui_is_released(cid))
			hit = i;
		n = tokenizebyseparator(opts, "|");     // ui_chip's text draw may retokenize
	}
	return hit;
};

void(string name, string val) MM_Seta =
{
	localcmd(sprintf("seta %s \"%s\"\n", name, val));
	cvar_set(name, val);
};

void(vector screensize) MM_ScreenVisuals =
{
	local float x, y, cur, hit, sky;

	MM_Shade(screensize, 0.62, 0.85);
	x = floor(screensize_x * 0.075);
	y = floor(screensize_y * 0.5) - 170;

	Font_Set(ui_font_display);
	sui_text([x, y - 70], '64 64 0', "VISUALS", '0.95 0.97 1', 1, 0);
	Font_Set(ui_font_ui);

	cur = cvar("milk_menu") ? bound(1, cvar("milk_quality"), 3) : 0;
	hit = MM_ChipRow([x, y], "mv_q", "Menu scene", "off|low|medium|high", cur);
	if (hit == 0)
		MM_Seta("milk_menu", "0");
	else if (hit > 0)
	{
		MM_Seta("milk_menu", "1");
		MM_Seta("milk_quality", ftos(hit));
	}

	cur = cvar("milk_trails");
	hit = MM_ChipRow([x, y + 44], "mv_t", "Light trails", "off|soft|full",
	                 cur <= 0 ? 0 : (cur < 0.9 ? 1 : 2));
	if (hit >= 0)
		MM_Seta("milk_trails", (hit == 0) ? "0" : ((hit == 1) ? "0.6" : "1"));

	cur = cvar("milk_react");
	hit = MM_ChipRow([x, y + 88], "mv_r", "Audio reactivity", "off|normal|wild",
	                 cur <= 0 ? 0 : (cur < 1.5 ? 1 : 2));
	if (hit >= 0)
		MM_Seta("milk_react", (hit == 0) ? "0" : ((hit == 1) ? "1" : "2"));

	sky = cvar("milk_sky");
	hit = MM_ChipRow([x, y + 132], "mv_s", "In-game sky", "map's own|visualizer", sky ? 1 : 0);
	if (hit >= 0)
	{
		MM_Seta("milk_sky", ftos(hit));
		// r_skybox is not archived: csprogs re-applies milk_sky at every map.
		localcmd(hit ? "r_skybox milk\n" : "r_skybox \"\"\n");
	}

	sui_text([x, y + 186], SZ_LABEL,
	         "^9the sky reacts to your speed, landings and whatever is playing", COL_DIM, 1, 0);
	if (!milk_hasvis)
		sui_text([x, y + 212], SZ_LABEL,
		         "^3this engine has no audio analysis -- visuals run without the music", COL_DIM, 1, 0);

	if (ui_option("mv_back", [x, y + 260], 200, 34, "back", COL_TEXT))
		menu_screen = SCREEN_MAIN;
};

void(float v) MM_VolumeSet = { cvar_set("musicvolume", ftos(v)); };

void(vector screensize) MM_ScreenMusic =
{
	local float x, y, i, rows, hit, vol, w;
	local string name, lbl;
	local vector sp;

	MM_Shade(screensize, 0.62, 0.85);
	x = floor(screensize_x * 0.075);
	y = floor(screensize_y * 0.5) - 250;

	Font_Set(ui_font_display);
	sui_text([x, y - 70], '64 64 0', "MUSIC", '0.95 0.97 1', 1, 0);
	Font_Set(ui_font_ui);
	sui_text([x + 2, y - 8], SZ_LABEL, "^9drop .ogg or .wav files into ftesurf/music/", COL_DIM, 1, 0);

	// The spectrum, straight off the engine's image.
	sp = [x, y + 22];
	sui_fill(sp, [520, 96], '0.02 0.02 0.04', 0.6, 0);
	if (milk_ready)
		drawpic(sp + '6 6 0', "milk_specview", [508, 84], Milk_Pal(mm_hue + 0.1), 1);

	rows = min(mm_ntracks, 9);
	if (!mm_ntracks)
		sui_text([x, y + 140], SZ_LABEL, "no tracks found", COL_DIM, 1, 0);
	for (i = 0; i < rows; i++)
	{
		name = mm_track[i];
		lbl = strcmp(name, mm_playing) ? name : strcat(name, "   ^2playing");
		if (ui_option(sprintf("mu_t%g", i), [x, y + 132 + i * 36], 520, 32, lbl, COL_TEXT))
		{
			MM_Play(name);
			MM_Seta("milk_menumusic", name);
		}
	}

	y = y + 140 + max(rows, 1) * 36;
	if (ui_button("mu_stop", [x, y], '120 30 0', "stop"))
		MM_Play("");
	if (ui_button("mu_next", [x + 132, y], '120 30 0', "next") && mm_ntracks)
	{
		hit = 0;
		for (i = 0; i < mm_ntracks; i++)
			if (!strcmp(mm_track[i], mm_playing))
				hit = i + 1;
		MM_Play(mm_track[hit - floor(hit / mm_ntracks) * mm_ntracks]);
	}

	sui_text([x + 280, y + 7], SZ_LABEL, "volume", COL_DIM, 1, 0);
	vol = cvar("musicvolume");
	w = 170;
	sui_fill([x + 350, y + 12], [w, 6], COL_ROW, 1, 0);
	sui_fill([x + 350, y + 12], [w * vol, 6], Milk_Pal(mm_hue + 0.1), 1, 0);
	sui_slidercontrol("mu_vol", [x + 350, y + 2], [w, 26], '0 1 20', vol, MM_VolumeSet);

	hit = MM_ChipRow([x, y + 48], "mu_m", "Menu music", "off|on",
	                 cvar_string("milk_menumusic") != "");
	if (hit == 0)
		MM_Seta("milk_menumusic", "");
	else if (hit == 1)
		MM_Seta("milk_menumusic", (mm_playing != "") ? mm_playing : "auto");

	hit = MM_ChipRow([x, y + 92], "mu_l", "Muffle game in menu", "off|on",
	                 cvar("milk_lowpass") ? 1 : 0);
	if (hit >= 0)
		MM_Seta("milk_lowpass", ftos(hit));

	if (ui_option("mu_back", [x, y + 148], 200, 34, "back", COL_TEXT))
		menu_screen = SCREEN_MAIN;
};

// Muffle the game while the menu is over it -- the engine's low-pass on the
// final mix (snd_fx_lowpass, Patch 467), gliding in and out.
void() MM_Open =
{
	if (clientstate() == 2 && cvar("milk_lowpass"))
	{
		cvar_set("snd_fx_lowpass", "900");
		mm_lowpassed = TRUE;
	}
};

void() MM_Close =
{
	if (mm_lowpassed)
	{
		cvar_set("snd_fx_lowpass", "0");
		mm_lowpassed = FALSE;
	}
};

/*
  milk_bootcheck 1: fly every station and photograph it, then quit.
  milk_bootcheck 2: the same, but stay up.
  Consent is satisfied IN MEMORY for the run, the way ui_bootterms fakes the
  opposite; data/consent.txt is never touched.
*/
void() MM_BootTick =
{
	local float t;

	if (!mm_bc_step)
	{
		mm_bc_t0 = gettime(0);
		mm_bc_consent = ms_consent;
		ms_consent = FS_TERMS_VERSION;
		menu_screen = SCREEN_MAIN;
		mm_bc_step = 1;
		print(sprintf("milk_bootcheck: start, engine audio %s\n", milk_hasvis ? "yes" : "no"));
		return;
	}
	t = gettime(0) - mm_bc_t0;
	mm_bc_frames++;

	// milk_bootcheck 4: frame rate with the space on (t 3..8) and off (9..14) at
	// the main station, for whatever milk_quality the run set.  Run it
	// uncapped (cl_maxfps 0, vid_wait 0): the difference is the milk's cost.
	if (cvar("milk_bootcheck") == 4)
	{
		if (mm_bc_step == 1 && t > 3)
		{
			mm_bc_frames = 0;
			mm_bc_step = 2;
		}
		else if (mm_bc_step == 2 && t > 8)
		{
			print(sprintf("milk_bootcheck: perf q%g rt %v on  %g fps (%g ms)\n", milk_quality,
			              milk_rtsize, mm_bc_frames / 5, 5000 / max(mm_bc_frames, 1)));
			cvar_set("milk_menu", "0");
			mm_bc_step = 3;
		}
		else if (mm_bc_step == 3 && t > 9)
		{
			mm_bc_frames = 0;
			mm_bc_step = 4;
		}
		else if (mm_bc_step == 4 && t > 14)
		{
			print(sprintf("milk_bootcheck: perf q%g off %g fps (%g ms)\n", milk_quality,
			              mm_bc_frames / 5, 5000 / max(mm_bc_frames, 1)));
			cvar_set("milk_menu", "1");
			localcmd("quit\n");
			mm_bc_step = 5;
		}
		return;
	}

	// milk_bootcheck 3: two shots of the SAME station 3 s apart.  The cube turns
	// ~36 degrees in that time, so identical frames mean the sim froze.
	if (cvar("milk_bootcheck") == 3)
	{
		if (mm_bc_step == 1 && t > 5)
		{
			print(sprintf("milk_bootcheck: A simtime %g ticks %g\n", milk_simtime, milk_ticks));
			localcmd("screenshot milk_diag_a\n");
			mm_bc_step = 2;
		}
		else if (mm_bc_step == 2 && t > 11)
		{
			print(sprintf("milk_bootcheck: B simtime %g ticks %g\n", milk_simtime, milk_ticks));
			localcmd("screenshot milk_diag_b\n");
			mm_bc_step = 3;
		}
		else if (mm_bc_step == 3 && t > 15)
		{
			print(sprintf("milk_bootcheck: C simtime %g ticks %g\n", milk_simtime, milk_ticks));
			localcmd("quit\n");
			mm_bc_step = 4;
		}
		return;
	}

	if (mm_bc_step == 1 && t > 6)
	{
		localcmd("screenshot milk_main\n");
		print(sprintf("milk_bootcheck: main, rt %v, %g fps, tick %g ms, audio live %g bass %g\n",
		              milk_rtsize, mm_bc_frames / t, milk_tickcost * 1000, milk_live, milk_bass));
		print(sprintf("milk_bootcheck: step %g simtime %g ticks %g ud0 %g ud12 %g campos %v station %g\n",
		              MILK_STEP, milk_simtime, milk_ticks, milk_ud[0], milk_ud[12], milk_campos, mm_station));
		mm_bc_step = 2;
	}
	else if (mm_bc_step == 2 && t > 6.5)
	{
		menu_screen = SCREEN_VISUALS;
		mm_bc_step = 3;
	}
	else if (mm_bc_step == 3 && t > 7.3)
	{
		localcmd("screenshot milk_flight\n");
		mm_bc_step = 4;
	}
	else if (mm_bc_step == 4 && t > 10)
	{
		print(sprintf("milk_bootcheck: visuals, simtime %g ticks %g ud0 %g campos %v station %g flight %g\n",
		              milk_simtime, milk_ticks, milk_ud[0], milk_campos, mm_station, mm_flight0));
		localcmd("screenshot milk_visuals\n");
		menu_screen = SCREEN_MUSIC;
		MM_MusicScan();
		mm_bc_step = 5;
	}
	else if (mm_bc_step == 5 && t > 13.5)
	{
		localcmd("screenshot milk_music\n");
		menu_screen = SCREEN_CREATE;
		ui_create_open();
		ui_refilter();
		mm_bc_step = 6;
	}
	else if (mm_bc_step == 6 && t > 17)
	{
		localcmd("screenshot milk_play\n");
		print(sprintf("milk_bootcheck: done, %g frames in %g s = %g fps, %g ticks, audio live %g\n",
		              mm_bc_frames, t, mm_bc_frames / t, milk_ticks, milk_live));
		ms_consent = mm_bc_consent;
		menu_screen = SCREEN_MAIN;
		mm_bc_step = 7;
	}
	else if (mm_bc_step == 7 && t > 18)
	{
		mm_bc_step = 8;
		if (cvar("milk_bootcheck") == 1)
			localcmd("quit\n");
	}
};
