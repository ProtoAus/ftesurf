/*
  m_milk.qc -- the menu's 3D spaces and the VISUALS / MUSIC screens.  Patch
  467, and the worlds and in-world panels after it.

  Melee's menu, abstractly: each screen is a place in a space and changing
  screen flies the camera there.  There are three spaces, each raymarched by
  its own shader through milk_sys.qc's feedback pipeline, so none costs a map
  or a server and all run in menu.dat, where a BSP cannot be drawn:

      world     shader                    MAIN / PLAY / VISUALS / MUSIC
      lattice   glsl/milk_scene.glsl      cube lattice, tower field, ring tunnel, pool
      monolith  glsl/milk_monolith.glsl   the void's balcony, forest terrace,
                                          endless corridor, PS2 towers
      vessel    glsl/milk_vessel.glsl     artery, darkfield, iris, leaf cells

  milk_world picks one ("shuffle" picks per launch); changing it dives out of
  one world and into the next.

  THE PANELS ARE IN THE WORLD.  MAIN, VISUALS and MUSIC draw their UI into a
  render target (mm_ui0 / mm_ui1) that the scene raymarches as the face of a
  slab standing at the station; the present pass then redraws that target
  crisply over the slab (glsl/milk_present.glsl #PANELS), and sui gets the
  cursor traced back through the camera into the target's pixels
  (MM_MouseToUI).  Each slab is laid out face-on to its station's resting
  camera at one texel per screen pixel, texel edges on pixel edges, so at rest
  the text is the font's own raster.  The camera orbits the slab only while
  the cursor is OFF it, and settles exactly when the cursor comes back.

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

#define MW_LATTICE  0
#define MW_MONOLITH 1
#define MW_VESSEL   2

#define MM_TRACKS   48
#define MM_TITLE_SZ '80 80 0'
#define MM_ITEM_SZ  '48 48 0'
#define MM_ITEM_H   64
#define MM_TANFOV   0.60
#define MM_CROP     0.97        // milk_present.glsl's overscan
#define MM_DIVE     2.4         // seconds for a dive between worlds

float  mm_world, mm_shuffle;
float  mm_dive0, mm_diveswapped, mm_diveto;
float  mm_station, mm_flight0, mm_flighttime, mm_stprev;
vector mm_pos0, mm_tgt0;
float  mm_hue0, mm_liq0, mm_kal0;
vector mm_pos, mm_tgt;
float  mm_hue, mm_liq, mm_kal;

// MM_Pose's answer: the resting camera, the look, the warp's anchor, the panel.
vector mm_ppos, mm_ptgt, mm_panchor;
float  mm_phue, mm_pliq, mm_pkal;
vector mm_prect0, mm_prect1;    // panel rectangle, screen fractions; x1 0 = no panel
float  mm_pdepth;               // how far in front of the camera the panel stands
// ...and the world's travel: flight seconds, how far a flight backs off and
// rises, how far a dive plunges.
float  mm_wflight, mm_wpull, mm_wlift, mm_wdive;

float  mm_yaw, mm_pitch, mm_yawv;
float  mm_nudgeyaw, mm_nudgepitch, mm_nudge;
vector mm_screen;
float  mm_last, mm_asp;
float  mm_hlon, mm_hlnext;
vector mm_titlepos, mm_titlecur;   // MM_Title's position last frame, for the feedback glow; x < 0 = none
vector mm_hlpos, mm_hlsize;
float  mm_itemx[4];             // eased hover offset per main item
float  mm_itemhot[4];           // hovered last frame, for the tick on entry

// The two panel slots.  mm_pslot holds the current station's; the other is
// the one the camera just left, collapsing.  Slot s draws $rt:mm_ui<s>.
float  mm_pslot;
float  mm_pst[2];               // station, -1 none
float  mm_pw[2];                // world the station is in
vector mm_pc[2];                // centre
vector mm_pang[2];              // yaw, pitch of the facing (radians)
vector mm_phalf[2];             // half-size, world units; x 0 = none
vector mm_ppx[2];               // size in screen pixels = the target's size
vector mm_prtsize[2];           // size the target was made at
float  mm_pon[2], mm_pdir[2];   // power 0..1, and which way it is going
float  mm_uiready, mm_presmat;
float  mm_drawpanel;            // TRUE while a screen draws into a panel

string mm_track[MM_TRACKS];
float  mm_ntracks, mm_trackscan, mm_autoplayed;
string mm_playing;
float  mm_lowpassed;
float  mm_sfx;
float  mm_films;                // the vessel's x-ray films found: bit 1 xray1, bit 2 xray2

float  mm_bc_step, mm_bc_t0, mm_bc_consent, mm_bc_frames, mm_bc_w0;
float  mm_bc_hits, mm_bc_hiton, mm_bc_kickpk;     // the big-hit gate, counted live
float  mm_art;                  // milk_bootcheck 7: the station being photographed bare, -1 off (MM_Init)
vector mm_fake;                 // milk_fakemouse, for the harness; x < 0 = the real cursor

void() MM_MusicAuto;

vector(vector a, vector b) MM_Cross =
{
	return [a_y * b_z - a_z * b_y, a_z * b_x - a_x * b_z, a_x * b_y - a_y * b_x];
};

float(float n) MM_Hash =
{
	n = sin(n * 12.9898 + 4.1414) * 43758.5453;
	return n - floor(n);
};

vector() MM_Mouse =
{
	if (mm_fake_x >= 0)
		return mm_fake;
	return getmousepos();
};

// The vessel's stations are separate places, one shader variant each (see
// glsl/milk_vessel.glsl): a shader holding all four ran at half the speed.
string(float w, float st) MM_WorldProg =
{
	if (w == MW_MONOLITH) return "milk_monolith";
	if (w == MW_VESSEL)   return strcat("milk_vessel#S", ftos(st));
	return "milk_scene";
};

string(float w) MM_WorldName =
{
	if (w == MW_MONOLITH) return "monolith";
	if (w == MW_VESSEL)   return "vessel";
	return "lattice";
};

string(float w) MM_WorldTrack =
{
	if (w == MW_MONOLITH) return "ftesurf_monolith";
	if (w == MW_VESSEL)   return "ftesurf_vessel";
	return "ftesurf_dream";
};

// milk_world, resolved: "shuffle" is decided once per launch.
float() MM_WorldWant =
{
	local string s;
	s = cvar_string("milk_world");
	if (s == "lattice")  return MW_LATTICE;
	if (s == "vessel")   return MW_VESSEL;
	if (s == "shuffle")  return mm_shuffle;
	return MW_MONOLITH;
};

// The panel's rectangle is the screen's, not the world's: the same layout
// stands wherever the world puts the station.
void(float st) MM_Rect =
{
	if (st == MS_MAIN)       { mm_prect0 = '0.05 0.14 0'; mm_prect1 = '0.39 0.86 0'; }
	else if (st == MS_VIS)   { mm_prect0 = '0.05 0.12 0'; mm_prect1 = '0.52 0.88 0'; }
	else if (st == MS_MUSIC) { mm_prect0 = '0.05 0.12 0'; mm_prect1 = '0.57 0.86 0'; }
	else                     { mm_prect0 = '0 0 0';       mm_prect1 = '0 0 0'; }
};

// Resting camera, look and anchor for one station of world w.  The anchor is
// the landmark the feedback trails radiate from.  Mirrored by the ST_* defines
// in the world's shader.
void(float w, float st) MM_PoseW =
{
	MM_Rect(st);
	if (w == MW_MONOLITH)
	{
		mm_pdepth = 3.2;
		mm_wflight = 2.6;  mm_wpull = 2;  mm_wlift = 30;  mm_wdive = 220;
		if (st == MS_PLAY)
		{
			mm_ppos = '140 -58.3 -20';  mm_ptgt = '217.26 -36.04 39.47';  mm_panchor = '198 -45 -12';
			mm_phue = 0.50;  mm_pliq = 0;    mm_pkal = 0;
		}
		else if (st == MS_VIS)
		{
			mm_ppos = '2.5 31.7 206';   mm_ptgt = '-43.79 33.3 294.63';   mm_panchor = '0 38 600';
			mm_phue = 0.66;  mm_pliq = 0.2;  mm_pkal = 6;
		}
		else if (st == MS_MUSIC)
		{
			mm_ppos = '30 -38.3 -62';   mm_ptgt = '48.22 -19.91 -158.59'; mm_panchor = '0 -18 -150';
			mm_phue = 0.62;  mm_pliq = 0.5;  mm_pkal = 0;
		}
		else
		{
			mm_ppos = '-178 11.7 -1';   mm_ptgt = '-80.19 -9.09 -1';      mm_panchor = '-100 -11 -25';
			mm_phue = 0.72;  mm_pliq = 0;    mm_pkal = 0;
		}
		return;
	}
	if (w == MW_VESSEL)
	{
		mm_pdepth = 3.6;
		mm_wflight = 2.0;  mm_wpull = 2;  mm_wlift = 20;  mm_wdive = 60;
		if (st == MS_PLAY)
		{
			mm_ppos = '392 0.5 0';      mm_ptgt = '394.67 -0.18 99.96';   mm_panchor = '404 1 36';
			mm_phue = 0.35;  mm_pliq = 0.1;  mm_pkal = 0;
		}
		else if (st == MS_VIS)
		{
			mm_ppos = '-418 0 -12';     mm_ptgt = '-438.42 0 85.89';      mm_panchor = '-400 0 100';
			mm_phue = 0.58;  mm_pliq = 0.2;  mm_pkal = 8;
		}
		else if (st == MS_MUSIC)
		{
			mm_ppos = '0 -284 -10';     mm_ptgt = '-6.3 -334.89 75.85';   mm_panchor = '8 -300 14';
			mm_phue = 0.48;  mm_pliq = 0.45; mm_pkal = 0;
		}
		else
		{
			mm_ppos = '0 0.4 0';        mm_ptgt = '-22.83 -1.29 97.35';   mm_panchor = '6 3 60';
			mm_phue = 0.17;  mm_pliq = 0.35; mm_pkal = 0;
		}
		return;
	}
	mm_pdepth = 4;
	mm_wflight = 1.7;  mm_wpull = 3;  mm_wlift = 12;  mm_wdive = 40;
	if (st == MS_PLAY)
	{
		mm_ppos = '44 5 -26';    mm_ptgt = '64 2 2';     mm_panchor = '64 3 0';
		mm_phue = 0.30;          mm_pliq = 0;     mm_pkal = 0;
	}
	else if (st == MS_VIS)
	{
		mm_ppos = '0 3 55';      mm_ptgt = '0 3 72';     mm_panchor = '0 3 90';
		mm_phue = 0.62;          mm_pliq = 0.2;   mm_pkal = 6;
	}
	else if (st == MS_MUSIC)
	{
		mm_ppos = '-64 3.4 -16'; mm_ptgt = '-64 1.7 4';  mm_panchor = '-64 0 0';
		mm_phue = 0.86;          mm_pliq = 0.85;  mm_pkal = 0;
	}
	else
	{
		mm_ppos = '1.6 2.7 -10'; mm_ptgt = '-1.9 3.1 0'; mm_panchor = '0 3.4 0';
		mm_phue = 0.02;          mm_pliq = 0.1;   mm_pkal = 0;
	}
};

void(float st) MM_Pose = { MM_PoseW(mm_world, st); };

float() MM_StationFor =
{
	if (mm_art >= 0)                   return mm_art;
	if (menu_screen == SCREEN_CREATE)  return MS_PLAY;
	if (menu_screen == SCREEN_VISUALS) return MS_VIS;
	if (menu_screen == SCREEN_MUSIC)   return MS_MUSIC;
	return MS_MAIN;
};

float() MM_Active =
{
	return cvar("milk_menu") > 0 && clientstate() != 2 && Milk_Supported();
};

// ------------------------------------------------------------------ panels --

float() MM_InWorld = { return cvar("milk_panels") > 0; };

float() MM_PanelScreen =
{
	return menu_screen == SCREEN_MAIN || menu_screen == SCREEN_VISUALS || menu_screen == SCREEN_MUSIC;
};

// Is the cursor going to a panel this frame (and must be traced onto it)?
float() MM_PanelInput =
{
	if (!mm_uiready || !milk_ready)
		return FALSE;
	return MM_Active() && MM_InWorld() && MM_PanelScreen();
};

string(float s) MM_UIName = { return (s == 0) ? "mm_ui0" : "mm_ui1"; };

// Half-width of slot s's panel; 0 = none.
float(float s) MM_PanelW = { local vector h; h = mm_phalf[s]; return h_x; };

/*
  Where slot s's panel stands: face-on to its station's resting camera, over
  an integer pixel rectangle of the screen, at mm_pdepth.  The world size
  follows from one texel per pixel through the present's projection --
  tan(fov/2) * MM_CROP per half screen height, the milk targets' aspect
  across -- so it depends on the resolution, and is redone every frame.
*/
void(float s) MM_PanelPlace =
{
	local vector P, F, R, U, r0, r1, px, h;
	local float tf, nx, ny, wx, wy;

	h = '0 0 0';
	if (mm_pst[s] >= 0 && mm_pw[s] == mm_world)
	{
		MM_Pose(mm_pst[s]);
		if (mm_prect1_x > 0)
		{
			P = mm_ppos;
			F = normalize(mm_ptgt - mm_ppos);
			R = normalize(MM_Cross('0 1 0', F));
			U = MM_Cross(F, R);
			tf = MM_TANFOV * MM_CROP;
			r0 = [rint(mm_prect0_x * mm_screen_x), rint(mm_prect0_y * mm_screen_y)];
			r1 = [rint(mm_prect1_x * mm_screen_x), rint(mm_prect1_y * mm_screen_y)];
			px = r1 - r0;
			wx = 2 * mm_pdepth * tf * mm_asp / mm_screen_x;
			wy = 2 * mm_pdepth * tf / mm_screen_y;
			h = [px_x * wx * 0.5, px_y * wy * 0.5];
			nx = ((r0_x + px_x * 0.5) / mm_screen_x * 2 - 1) * MM_CROP;
			ny = -((r0_y + px_y * 0.5) / mm_screen_y * 2 - 1) * MM_CROP;
			mm_pc[s] = P + (F + R * (nx * mm_asp * MM_TANFOV) + U * (ny * MM_TANFOV)) * mm_pdepth;
			mm_pang[s] = [atan2(-F_x, -F_z), asin(-F_y), 0];
			mm_ppx[s] = px;
		}
	}
	mm_phalf[s] = h;
};

// The two UI targets, made (or remade) at their panels' sizes.  Before the
// first Milk_Frame: the scene material names both.
void() MM_PanelTargets =
{
	local float s, bnd;
	local vector sz;

	bnd = FALSE;
	for (s = 0; s < 2; s++)
	{
		sz = mm_ppx[s];
		if (sz_x < 16 || sz_y < 16)
			sz = '16 16 0';
		if (mm_uiready && sz == mm_prtsize[s])
			continue;
		setproperty(VF_RT_DESTCOLOUR, MM_UIName(s), MILK_FMT_RGBA8, sz);
		drawpic('0 0 0', "milk_clear", sz, '1 1 1', 1);
		mm_prtsize[s] = sz;
		bnd = TRUE;
	}
	if (bnd)
		setproperty(VF_RT_DESTCOLOUR, "");
	mm_uiready = TRUE;
};

// milk_packextra: w_user[12..15], see glsl/milk_panel.h.
void() MM_PanelPack =
{
	local float s, lit;
	local vector c, a, h;

	for (s = 0; s < 2; s++)
	{
		c = mm_pc[s];
		a = mm_pang[s];
		h = mm_phalf[s];
		lit = (mm_pdir[s] > 0) ? mm_pon[s] : -mm_pon[s];
		if (!MM_InWorld())
			h = '0 0 0';
		Milk_U(12 + s * 2, c_x, c_y, c_z, lit);
		Milk_U(13 + s * 2, a_x, a_y, h_x, h_y);
	}
};

/*
  A screen position to the current panel's pixels, through the camera the
  last tick drew with -- read back out of milk_ud, the very numbers the
  present is using, so the cursor lands on what is on screen.  Off the plane
  (or behind it) is far off the target, which hovers nothing.
*/
vector(vector m) MM_MouseToUI =
{
	local vector ro, F, R, U, rd, C, N, PR, PU, d, sz;
	local float s, i, tf, asp, nx, ny, yaw, pit, hw, hh, den, t;

	if (!MM_PanelInput())
		return m;
	s = mm_pslot;
	i = (12 + s * 2) * 4;
	hw = milk_ud[i + 6];
	hh = milk_ud[i + 7];
	if (hw <= 0 || hh <= 0)
		return '-9999 -9999 0';
	ro = [milk_ud[12], milk_ud[13], milk_ud[14]];
	tf = milk_ud[15];
	F = [milk_ud[16], milk_ud[17], milk_ud[18]];
	R = [milk_ud[20], milk_ud[21], milk_ud[22]];
	U = [milk_ud[24], milk_ud[25], milk_ud[26]];
	asp = milk_ud[2];
	nx = (m_x / mm_screen_x * 2 - 1) * MM_CROP + milk_ud[44] * 2;
	ny = -((m_y / mm_screen_y * 2 - 1) * MM_CROP + milk_ud[45] * 2);
	rd = F + R * (nx * asp * tf) + U * (ny * tf);

	C = [milk_ud[i], milk_ud[i + 1], milk_ud[i + 2]];
	yaw = milk_ud[i + 4];
	pit = milk_ud[i + 5];
	N = [sin(yaw) * cos(pit), sin(pit), cos(yaw) * cos(pit)];
	PR = [-cos(yaw), 0, sin(yaw)];
	PU = MM_Cross('0 0 0' - N, PR);
	den = rd * N;
	if (den > -0.0001)
		return '-9999 -9999 0';
	t = ((C - ro) * N) / den;
	d = ro + rd * t - C;
	sz = mm_prtsize[s];
	return [(0.5 + 0.5 * (d * PR) / hw) * sz_x, (0.5 - 0.5 * (d * PU) / hh) * sz_y];
};

// sui computes hovers only when the cursor moves, but a panel moves under a
// still cursor (the orbit, a flight): re-trace it once a frame, after the
// screen has registered this frame's elements.
void() MM_PanelHover =
{
	if (!MM_PanelInput())
		return;
	if (mm_fake_x >= 0)
		activate_mouse_cursor();
	if (!_cursor_is_mouse_active)
		return;
	_sui_mouse_move(MM_MouseToUI(MM_Mouse()), TRUE);
};

// Binds and wipes the current panel's target; FALSE = draw the screen flat.
float() MM_PanelDraw =
{
	local vector sz;

	if (!MM_PanelInput() || MM_PanelW(mm_pslot) <= 0)
		return FALSE;
	sz = mm_prtsize[mm_pslot];
	setproperty(VF_RT_DESTCOLOUR, MM_UIName(mm_pslot), MILK_FMT_RGBA8, sz);
	drawpic('0 0 0', "milk_clear", sz, '1 1 1', 1);
	mm_drawpanel = TRUE;
	return TRUE;
};

void() MM_PanelDone =
{
	setproperty(VF_RT_DESTCOLOUR, "");
	mm_drawpanel = FALSE;
	MM_PanelHover();
};

// Power: the current station's panel comes up as the camera arrives, the one
// left behind collapses.  A screen that is not on a panel powers it down.
void(float now, float dt) MM_PanelPower =
{
	local float s, arrive, want;

	arrive = 1;
	if (mm_flight0)
		arrive = (now - mm_flight0) / mm_flighttime;
	if (mm_dive0)
		arrive = (now - mm_dive0) / MM_DIVE * 2 - 1;
	for (s = 0; s < 2; s++)
	{
		want = (s == mm_pslot) && MM_PanelScreen() && arrive > 0.6;
		if (want)
		{
			mm_pdir[s] = 1;
			mm_pon[s] = min(1, mm_pon[s] + dt / 0.45);
		}
		else
		{
			if (mm_pdir[s] > 0 && mm_pon[s] > 0)
				mm_pdir[s] = -1;
			if (mm_pdir[s] < 0)
				mm_pon[s] = max(0, mm_pon[s] - dt / 0.5);
		}
	}
};

void() MM_Invalidate =
{
	Milk_Invalidate();
	mm_uiready = FALSE;
	mm_presmat = FALSE;
};

// ---------------------------------------------------------------- sound fx --

void(string name, float vol) MM_Sfx =
{
	if (mm_sfx && cvar("milk_sfx"))
		localsound(strcat("milk/", name, ".wav"), 0, vol);
};

// ------------------------------------------------------------------ flight --

void(float st) MM_Go =
{
	local float o;

	if (st == mm_station)
		return;
	// From wherever the camera really is (orbit included), so nothing jumps.
	mm_pos0 = milk_campos;
	mm_tgt0 = milk_campos + milk_camfwd * 12;
	mm_hue0 = mm_hue;  mm_liq0 = mm_liq;  mm_kal0 = mm_kal;
	mm_stprev = mm_station;
	mm_station = st;
	mm_flight0 = gettime(0);
	MM_Pose(st);
	mm_flighttime = mm_wflight;
	mm_yaw = 0;
	mm_pitch = 0;

	o = mm_pslot;
	if (mm_pdir[o] > 0 && mm_pon[o] > 0)
		mm_pdir[o] = -1;
	mm_pslot = 1 - o;
	mm_pst[mm_pslot] = st;
	mm_pw[mm_pslot] = mm_world;
	mm_pon[mm_pslot] = 0;
	mm_pdir[mm_pslot] = 1;
	MM_Sfx("whoosh", 0.55);
};

// A new world: the camera plunges on along its view, the scene is swapped at
// the bottom of the plunge, and it comes to rest at the same station there.
void() MM_WorldSwap =
{
	local float o;

	mm_world = mm_diveto;
	Milk_SetScene(MM_WorldProg(mm_world, mm_station));
	o = 1 - mm_pslot;
	mm_pst[o] = -1;
	mm_pon[o] = 0;
	mm_pst[mm_pslot] = mm_station;
	mm_pw[mm_pslot] = mm_world;
	mm_pon[mm_pslot] = 0;
	mm_pdir[mm_pslot] = 1;
	if (cvar_string("milk_menumusic") == "auto")
	{
		mm_autoplayed = FALSE;
		MM_MusicAuto();
	}
};

void(float now) MM_WorldCheck =
{
	local float w;

	w = MM_WorldWant();
	if (mm_dive0 || w == mm_world)
		return;
	mm_diveto = w;
	mm_dive0 = now;
	mm_diveswapped = FALSE;
	mm_flight0 = 0;
	mm_pos0 = milk_campos;
	mm_tgt0 = milk_campos + milk_camfwd * 12;
	mm_hue0 = mm_hue;
	mm_yaw = 0;
	mm_pitch = 0;
	if (mm_pon[mm_pslot] > 0)
		mm_pdir[mm_pslot] = -1;
	MM_Sfx("dive", 0.7);
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
	local float f, e, u, trav, k, ty, tp, L, dx, dy, w, a, b, oF, oR, oU, orbit, dive;
	local vector c1, c2, m, fwd, right, up, P, C, F1, R1, F2, U2, o, sway, fc;

	MM_Pose(mm_station);
	trav = 0;
	dive = FALSE;
	if (mm_dive0)
	{
		dive = TRUE;
		f = (now - mm_dive0) / MM_DIVE;
		if (f >= 0.5 && !mm_diveswapped)
		{
			mm_diveswapped = TRUE;
			MM_WorldSwap();
			MM_Pose(mm_station);
		}
		if (f >= 1)
		{
			f = 1;
			mm_dive0 = 0;
		}
		if (f < 0.5)
		{
			e = f * 2;
			fwd = normalize(mm_tgt0 - mm_pos0);
			mm_pos = mm_pos0 + fwd * (e * e * e * mm_wdive);
			mm_tgt = mm_pos + fwd * 12;
			mm_hue = mm_hue0;
		}
		else
		{
			e = (f - 0.5) * 2;
			u = 1 - e;
			fwd = normalize(mm_ptgt - mm_ppos);
			mm_pos = mm_ppos - fwd * (u * u * u * mm_wdive);
			mm_tgt = mm_ptgt + mm_pos - mm_ppos;
			mm_hue = mm_phue;
		}
		mm_liq = mm_pliq * f;
		mm_kal = (f < 0.5) ? mm_kal0 : mm_pkal;
		trav = sin(f * 3.14159265);
	}
	else if (mm_flight0)
	{
		f = (now - mm_flight0) / mm_flighttime;
		if (f >= 1)
		{
			f = 1;
			mm_flight0 = 0;
		}
		e = f * f * (3 - 2 * f);
		// A cubic that backs off the panel being left, and glides into the
		// next station along its own view.
		L = vlen(mm_ppos - mm_pos0);
		c1 = mm_pos0 + normalize(mm_pos0 - mm_tgt0) * min(L * 0.15, mm_wpull) + '0 1 0' * min(L * 0.12, mm_wlift);
		c2 = mm_ppos - normalize(mm_ptgt - mm_ppos) * (L * 0.3) + '0 1 0' * min(L * 0.08, mm_wlift);
		u = 1 - e;
		mm_pos = mm_pos0 * (u * u * u) + c1 * (3 * u * u * e) + c2 * (3 * u * e * e) + mm_ppos * (e * e * e);
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

	P = mm_pos;
	fwd = normalize(mm_tgt - P);
	right = normalize(MM_Cross('0 1 0', fwd));
	up = MM_Cross(fwd, right);

	// The look.  With a panel here the camera ORBITS the panel's centre, and
	// only while the cursor is outside the panel; otherwise it turns its head
	// (the pre-panel mouse look).  Nothing while travelling.
	m = MM_Mouse();
	orbit = MM_InWorld() && mm_prect1_x > 0 && MM_PanelW(mm_pslot) > 0;
	ty = 0;
	tp = 0;
	sway = '0 0 0';
	if (!mm_flight0 && !dive)
	{
		if (orbit)
		{
			dx = (m_x - bound(mm_prect0_x * mm_screen_x, m_x, mm_prect1_x * mm_screen_x)) / max(mm_screen_x, 1);
			dy = (m_y - bound(mm_prect0_y * mm_screen_y, m_y, mm_prect1_y * mm_screen_y)) / max(mm_screen_y, 1);
			w = bound(0, (fabs(dx) + fabs(dy)) * 6, 1);
			ty = dx * 30 + sin(now * 0.13) * 1.6 * w;
			tp = -dy * 24 + sin(now * 0.17) * 0.8 * w;
		}
		else
		{
			ty = (m_x / max(mm_screen_x, 1) - 0.5) * 16 + mm_nudgeyaw * mm_nudge;
			tp = (0.5 - m_y / max(mm_screen_y, 1)) * 8 + mm_nudgepitch * mm_nudge;
			sway = [sin(now * 0.13) * 0.7, sin(now * 0.17) * 0.3, cos(now * 0.11) * 0.5];
		}
	}
	k = 1 - pow(2.7182818, -dt * 3.5);
	mm_yawv = (ty - mm_yaw) * k;
	mm_yaw += mm_yawv;
	mm_pitch += (tp - mm_pitch) * k;
	// Settle EXACTLY: the panel's 1:1 raster needs the resting camera, not
	// one a thousandth of a degree off it.
	if (ty == 0 && fabs(mm_yaw) < 0.004)
		mm_yaw = 0;
	if (tp == 0 && fabs(mm_pitch) < 0.004)
		mm_pitch = 0;

	a = mm_yaw * 0.01745329;
	b = mm_pitch * 0.01745329;
	if (orbit && !mm_flight0 && !dive)
	{
		// Rigid rotation about the panel's centre: the centre keeps its place
		// on screen, the world swings behind it.
		C = mm_pc[mm_pslot];
		F1 = fwd * cos(a) + right * sin(a);
		R1 = right * cos(a) - fwd * sin(a);
		F2 = F1 * cos(b) + up * sin(b);
		U2 = up * cos(b) - F1 * sin(b);
		o = P - C;
		oF = o * fwd;
		oR = o * right;
		oU = o * up;
		P = C + F2 * oF + R1 * oR + U2 * oU;
		fwd = F2;
		right = R1;
		up = U2;
	}
	else
	{
		P = P + sway * (1 - trav);
		fwd = normalize(mm_tgt - P);
		right = normalize(MM_Cross('0 1 0', fwd));
		fwd = normalize(fwd * cos(a) + right * sin(a));
		right = normalize(MM_Cross('0 1 0', fwd));
		up = MM_Cross(fwd, right);
		fwd = normalize(fwd * cos(b) + up * sin(b));
		up = MM_Cross(fwd, right);
	}

	milk_campos = P;
	milk_camfwd = fwd;
	milk_camright = right;
	milk_camup = up;
	milk_tanfov = MM_TANFOV;
	milk_travel = trav;
	milk_hue = mm_hue;
	milk_liquid = mm_liq;
	milk_kaleido = mm_kal;

	// Feedback character: calm when settled, hyperspace in flight.  The music
	// moves it on the big hits only (milk_kick, milk_hit), not on every hat.
	milk_react = Milk_ReactCurve(cvar("milk_react"));
	milk_grade = bound(0, cvar("milk_grade"), 1);
	milk_zoom = 1.004 + 0.045 * trav + 0.008 * milk_kick * milk_react;
	milk_rot = 0.0015 * sin(now * 0.05) - mm_yawv * 0.004;
	milk_decay = 0.84 + 0.11 * trav;
	milk_wobble = 0.3 + 0.45 * milk_bass_att * milk_react;
	milk_trails = cvar("milk_trails");
	milk_bloom = 1;
	milk_exposure = 1.1;
	milk_flash = milk_hit * milk_react;
	// A daylit world: only its lights may seed the trails and bloom, or the
	// haze would smear across the whole frame.
	if (mm_world == MW_MONOLITH)
	{
		milk_inject = 1.1;
		milk_knee = 0.9;
		milk_exposure = 1.45;
	}
	else if (mm_world == MW_VESSEL)
	{
		milk_inject = 0.55;
		milk_knee = 0.5;
	}
	else
	{
		milk_inject = 0;
		milk_knee = 0;
	}

	// Trails radiate from the landmark, not the middle of the screen.
	fc = MM_Project(mm_panchor);
	fc_x = bound(0.15, fc_x, 0.85);
	fc_y = bound(0.15, fc_y, 0.85);
	milk_focus_x = fc_x * (1 - trav) + 0.5 * trav;
	milk_focus_y = fc_y * (1 - trav) + 0.5 * trav;

	// Present-time parallax: what the mouse did since the sim last looked.
	// Never with panels: the present must map exactly what the tick drew.
	if (MM_InWorld())
		milk_offset = '0 0 0';
	else
		milk_offset = [(ty - mm_yaw) * 0.0007, (tp - mm_pitch) * -0.0007, 0];
};

// Into the fresh feedback frame, once per tick: drifting motes around the
// station, and -- flat panels only -- the highlight bar and the title's halo.
// In the world, the slab's own face feeds the trails and the bloom.
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
		           0.10 + 0.12 * milk_hit * milk_react, 1);
		Font_Set(ui_font_ui);
	}

	if (mm_hlon)
	{
		hp = Milk_ToRT(mm_hlpos, mm_screen);
		hs = Milk_ToRT(mm_hlsize, mm_screen);
		Milk_Bar(hp, hs, Milk_Pal(mm_hue + 0.1), 0.22 + 0.35 * milk_hit * milk_react);
	}
};

// ------------------------------------------------------------------- music --

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

// "auto" is the world's own track when it is there, else the first found.
void() MM_MusicAuto =
{
	local string want;
	local float i;

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
		for (i = 0; i < mm_ntracks; i++)
			if (!strcmp(mm_track[i], MM_WorldTrack(mm_world)))
				want = mm_track[i];
		if (!strcmp(want, mm_playing))
			return;
	}
	MM_Play(want);
};

// -------------------------------------------------------------------- frame --

void() MM_Init =
{
	registercvar("milk_menu", "1", 32);         // 32 = CVAR_ARCHIVE
	registercvar("milk_quality", "2", 32);
	registercvar("milk_trails", "1", 32);
	registercvar("milk_react", "1", 32);
	registercvar("milk_sky", "0", 32);
	registercvar("milk_menumusic", "auto", 32);
	registercvar("milk_lowpass", "1", 32);
	registercvar("milk_world", "monolith", 32);
	registercvar("milk_panels", "1", 32);
	registercvar("milk_sfx", "1", 32);
	registercvar("milk_grade", "1", 32);
	registercvar("milk_bootcheck", "0", 0);
	registercvar("milk_fakemouse", "", 0);
	registercvar("milk_bcstation", "0", 0);
	registercvar("milk_bcworld", "vessel", 0);
	registercvar("milk_bcdiv", "0", 0);

	mm_shuffle = floor(random() * 3);
	if (mm_shuffle > 2)
		mm_shuffle = 2;
	mm_world = MM_WorldWant();
	Milk_Init("mm", MM_WorldProg(mm_world, MS_MAIN), "milk_warp", "milk_comp");
	// The vessel's x-ray films are local images, never shipped: a black film
	// without them (milk_vessel.glsl, film()).  "map $clamp:", never
	// "clampmap": in a program pass only "map" opens the next texture unit
	// (Shaderpass_DefineMap), so a clampmap overwrote mm_ui1 and left 4-5 empty.
	mm_films = ui_file_exists("gfx/env/xray1.png") + 2 * ui_file_exists("gfx/env/xray2.png");
	milk_scenemaps = strzone(sprintf("map $rt:mm_ui0\nmap $rt:mm_ui1\n%s\n%s\n",
	                         (mm_films & 1) ? "map $clamp:gfx/env/xray1.png" : "map $blackimage",
	                         (mm_films & 2) ? "map $clamp:gfx/env/xray2.png" : "map $blackimage"));
	milk_sprites = MM_Sprites;
	milk_packextra = MM_PanelPack;
	mm_station = MS_MAIN;
	MM_Pose(MS_MAIN);
	mm_pos = mm_ppos;  mm_tgt = mm_ptgt;
	mm_hue = mm_phue;  mm_liq = mm_pliq;
	mm_playing = "";
	mm_pslot = 0;
	mm_pst[0] = MS_MAIN;
	mm_pw[0] = mm_world;
	mm_pdir[0] = 1;
	mm_pst[1] = -1;
	mm_fake = '-1 -1 0';
	mm_art = -1;

	mm_sfx = ui_file_exists("sound/milk/click.wav");
	if (mm_sfx)
	{
		precache_sound("milk/hover.wav");
		precache_sound("milk/click.wav");
		precache_sound("milk/back.wav");
		precache_sound("milk/whoosh.wav");
		precache_sound("milk/dive.wav");
	}
};

// Before sui_begin every frame: the sim, if the backdrop wants it.
void(vector screensize) MM_Frame =
{
	local float now, dt, q, h;
	local vector size;
	local string fm;

	mm_screen = screensize;
	mm_hlon = mm_hlnext;
	mm_hlnext = FALSE;
	mm_titlecur = mm_titlepos;
	mm_titlepos_x = -1;
	mm_nudge = mm_nudge * 0.9;

	fm = cvar_string("milk_fakemouse");
	if (fm == "")
		mm_fake = '-1 -1 0';
	else
		mm_fake = stov(fm);

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

	MM_WorldCheck(now);
	if (!mm_dive0)
		MM_Go(MM_StationFor());

	// Internal height by quality: 360 / 540 / 720, width by aspect.  4, ultra,
	// is high's resolution raymarched every tick (below).
	q = bound(1, cvar("milk_quality"), 3);
	h = 180 + q * 180;
	if (h > screensize_y)
		h = screensize_y;
	size = [floor(h * screensize_x / screensize_y), h];
	mm_asp = size_x / size_y;
	milk_quality = q;
	// The raymarch is the cost (Patch 467 perf); the monolith's is the dearest,
	// and its haze hides a softer scene.
	if (mm_world == MW_LATTICE)
		milk_scenescale = (q >= 3) ? 1 : 0.75;
	else if (mm_world == MW_VESSEL)
		milk_scenescale = (q >= 3) ? 0.9 : ((q >= 2) ? 0.7 : 0.55);
	else
		milk_scenescale = (q >= 3) ? 0.8 : ((q >= 2) ? 0.58 : 0.5);
	// The raymarch runs every other tick (the feedback every tick) except at
	// ultra, and for the lattice at high.  The monolith at 720p on the N100:
	// 55 fps every other tick, 17 and 24 (two runs) every tick.
	if (cvar("milk_quality") >= 4 || (q >= 3 && mm_world == MW_LATTICE))
		milk_scenediv = 1;
	else
		milk_scenediv = 2;
	if (cvar("milk_bcdiv") > 0)         // harness: pin it, to time the raymarch alone
		milk_scenediv = cvar("milk_bcdiv");

	MM_PanelPlace(0);
	MM_PanelPlace(1);
	MM_PanelPower(now, dt);
	MM_PanelTargets();
	MM_Camera(now, dt);
	// A vessel flight draws the place it left for its first half, the place
	// it is going for the second -- the swap lands in the middle of the blur.
	if (mm_flight0 && (now - mm_flight0) < mm_flighttime * 0.5)
		Milk_SetScene(MM_WorldProg(mm_world, mm_stprev));
	else if (!mm_dive0 || mm_diveswapped)
		Milk_SetScene(MM_WorldProg(mm_world, mm_station));
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

// The present.  With panels, its #PANELS material draws them over their slabs
// (made here, once the targets it names exist).
void(vector screensize) MM_Backdrop =
{
	if (MM_InWorld() && mm_uiready && milk_ready)
	{
		if (!mm_presmat)
		{
			Milk_Mat("mm_presentp", "milk_present#PANELS",
			         "map $rt:mm_out\nmap $rt:mm_scene\nmap $rt:mm_ui0\nmap $rt:mm_ui1\n");
			mm_presmat = TRUE;
		}
		Milk_PresentMat('0 0 0', screensize, 1, "mm_presentp");
		return;
	}
	Milk_Present('0 0 0', screensize, 1);
};

// ----------------------------------------------------------------- screens --

/*
  One main-menu entry: Bebas at 48, an eased slide to the right on hover, a
  crisp accent bar, and -- flat -- the same bar mirrored into the feedback
  frame, where the warp smears it into the glow and the ghost trail.  On a
  panel the slab's face does that job.  Returns the click.
*/
float(float idx, string id, vector pos, string label, float nyaw, float npitch) MM_Item =
{
	local float w, hot, k;
	local vector acc, col;

	Font_Set(ui_font_display);
	w = stringwidth(label, TRUE, MM_ITEM_SZ);
	sui_action_element(pos, [w + 90, MM_ITEM_H - 6], id, sui_noop);
	hot = sui_is_hovered(id);
	if (hot && !mm_itemhot[idx])
		MM_Sfx("hover", 0.35);
	mm_itemhot[idx] = hot;

	k = hot ? 1 : 0;
	mm_itemx[idx] += (k - mm_itemx[idx]) * 0.2;
	acc = Milk_Pal(mm_hue + 0.1);

	if (hot && !mm_drawpanel)
	{
		mm_hlnext = TRUE;
		mm_hlpos = pos + [-20, 10];
		mm_hlsize = [w + 130, MM_ITEM_H - 18];
		mm_nudgeyaw = nyaw;
		mm_nudgepitch = npitch;
		mm_nudge = 1;
	}

	if (mm_itemx[idx] > 0.01)
	{
		sui_fill(pos + [-16, 12], [4, MM_ITEM_H - 26], acc, mm_itemx[idx], 0);
		// On a panel the bar is also a glow strip across the row: bright in
		// the target, so the slab's face blooms under the hovered entry.
		if (mm_drawpanel)
			sui_fill(pos + [-8, MM_ITEM_H - 12], [(w + 70) * mm_itemx[idx], 2], acc, 0.8 * mm_itemx[idx], 0);
	}

	col = '0.70 0.72 0.80' * (1 - mm_itemx[idx]) + (acc * 0.45 + '0.6 0.6 0.6') * mm_itemx[idx];
	sui_text(pos + [floor(22 * mm_itemx[idx]), 4], MM_ITEM_SZ, label, col, 0.8 + 0.2 * k, 0);
	Font_Set(ui_font_ui);
	if (sui_is_released(id))
	{
		MM_Sfx("click", 0.6);
		return TRUE;
	}
	return FALSE;
};

// The title, with a halo of offset additive copies in the station colour.
void(vector pos) MM_Title =
{
	local float i;
	local vector acc;

	acc = Milk_Pal(mm_hue + 0.1);
	if (!mm_drawpanel)
		mm_titlepos = pos;
	Font_Set(ui_font_display);
	for (i = 0; i < 8; i++)
		drawstring(pos + [cos(i * 0.785) * 3, sin(i * 0.785) * 3], "FTESURF", MM_TITLE_SZ,
		           acc, 0.16 + 0.10 * milk_hit * milk_react, 1);
	sui_text(pos, MM_TITLE_SZ, "FTESURF", '0.95 0.97 1', 1, 0);
	Font_Set(ui_font_ui);
};

// The four entries, from `y` down at `pitch`.
void(float x, float y, float pitch) MM_MainItems =
{
	if (MM_Item(0, "mm_play", [x, y], "PLAY", 16, 0))
	{
		menu_screen = SCREEN_CREATE;
		ui_create_open();
		ui_refilter();
	}
	if (MM_Item(1, "mm_vis", [x, y + pitch], "VISUALS", 0, 6))
		menu_screen = SCREEN_VISUALS;
	if (MM_Item(2, "mm_music", [x, y + pitch * 2], "MUSIC", -16, 0))
	{
		menu_screen = SCREEN_MUSIC;
		MM_MusicScan();
	}
	if (MM_Item(3, "mm_quit", [x, y + pitch * 3], "QUIT", 0, -4))
		localcmd("quit\n");
};

// The analyser strip, straight off the engine's image.
void(vector pos, vector size) MM_Spectrum =
{
	sui_fill(pos, size, '0.02 0.02 0.04', 0.6, 0);
	if (milk_ready)
		drawpic(pos + '6 6 0', "milk_specview", size - '12 12 0', Milk_Pal(mm_hue + 0.1), 1);
};

void(vector sz) MM_MainPanel =
{
	local float x, y, fy, pitch;
	local vector acc;

	acc = Milk_Pal(mm_hue + 0.1);
	x = 48;
	y = 40;
	pitch = (sz_y >= 720) ? MM_ITEM_H : 56;

	MM_Title([x, y]);
	sui_text([x + 4, y + 88], SZ_LABEL, "Counter-Strike: Source movement", COL_DIM, 1, 0);
	sui_fill([x, y + 122], [sz_x - x * 2, 2], acc, 0.45, 0);
	MM_MainItems(x, y + 150, pitch);

	// The foot: what is playing, the world, and the one hint.
	fy = sz_y - 40;
	sui_text([x, fy - 18], SZ_LABEL,
	         sprintf("^9world  ^7%s     ^9move off the panel to look around", MM_WorldName(mm_world)), COL_DIM, 1, 0);
	if (mm_playing != "")
		sui_text([x, fy - 48], SZ_LABEL, sprintf("^9playing  ^7%s", mm_playing), COL_DIM, 1, 0);
	if (sz_y - (y + 150 + pitch * 4) > 170)
		MM_Spectrum([x, fy - 130], [sz_x - x * 2, 70]);
	if (clientstate() == 2)
		sui_text([x + 4, y + 150 + pitch * 4 + 8], SZ_LABEL,
		         sprintf("^9esc  back to %s", serverkey("map")), COL_DIM, 1, 0);
};

void(vector screensize) MM_ScreenMain =
{
	local float x, y;

	if (mm_art >= 0)
		return;
	if (MM_PanelDraw())
	{
		MM_MainPanel(mm_prtsize[mm_pslot]);
		MM_PanelDone();
		return;
	}

	MM_Shade(screensize, 0.5, 0.75);

	x = floor(screensize_x * 0.075);
	y = floor(screensize_y * 0.5) - 110;

	MM_Title([x, y - 150]);
	sui_text([x + 4, y - 62], SZ_LABEL, "Counter-Strike: Source movement", COL_DIM, 1, 0);
	MM_MainItems(x, y, MM_ITEM_H);

	if (clientstate() == 2)
		sui_text([x + 4, y + MM_ITEM_H * 4 + 16], SZ_LABEL,
		         sprintf("^9esc  back to %s", serverkey("map")), COL_DIM, 1, 0);
	else if (MM_Active())
		sui_text([x + 4, screensize_y - 48], SZ_LABEL,
		         "^9move the mouse to look around", COL_DIM, 1, 0);
};

// One labelled row of chips; returns the index clicked, or -1.
float(vector pos, string id, string label, string opts, float cur, float labelw) MM_ChipRow =
{
	local float n, i, x, hit;
	local string cid;

	sui_text(pos + '0 5 0', SZ_LABEL, label, COL_TEXT, 1, 0);
	n = tokenizebyseparator(opts, "|");
	x = pos_x + labelw;
	hit = -1;
	for (i = 0; i < n; i++)
	{
		cid = sprintf("%s%g", id, i);
		x += ui_chip([x, pos_y], cid, argv(i), i == cur) + CHIP_GAP;
		if (sui_is_released(cid))
			hit = i;
		n = tokenizebyseparator(opts, "|");     // ui_chip's text draw may retokenize
	}
	if (hit >= 0)
		MM_Sfx("click", 0.4);
	return hit;
};

void(string name, string val) MM_Seta =
{
	localcmd(sprintf("seta %s \"%s\"\n", name, val));
	cvar_set(name, val);
};

float() MM_WorldCur =
{
	local string s;
	s = cvar_string("milk_world");
	if (s == "lattice")  return 0;
	if (s == "vessel")   return 2;
	if (s == "shuffle")  return 3;
	return 1;
};

// The VISUALS rows, from `y` down; returns where they end.
float(float x, float y, float pitch, float labelw) MM_VisualsRows =
{
	local float cur, hit, sky;

	hit = MM_ChipRow([x, y], "mv_w", "Menu world", "lattice|monolith|vessel|shuffle", MM_WorldCur(), labelw);
	if (hit >= 0)
		MM_Seta("milk_world", (hit == 0) ? "lattice" : ((hit == 1) ? "monolith" : ((hit == 2) ? "vessel" : "shuffle")));
	y += pitch;

	cur = cvar("milk_menu") ? bound(1, cvar("milk_quality"), 4) : 0;
	hit = MM_ChipRow([x, y], "mv_q", "Menu scene", "off|low|medium|high|ultra", cur, labelw);
	if (hit == 0)
		MM_Seta("milk_menu", "0");
	else if (hit > 0)
	{
		MM_Seta("milk_menu", "1");
		MM_Seta("milk_quality", ftos(hit));
	}
	y += pitch;

	hit = MM_ChipRow([x, y], "mv_p", "Menu panels", "flat|in the world", MM_InWorld() ? 1 : 0, labelw);
	if (hit >= 0)
		MM_Seta("milk_panels", ftos(hit));
	y += pitch;

	cur = cvar("milk_trails");
	hit = MM_ChipRow([x, y], "mv_t", "Light trails", "off|soft|full",
	                 cur <= 0 ? 0 : (cur < 0.9 ? 1 : 2), labelw);
	if (hit >= 0)
		MM_Seta("milk_trails", (hit == 0) ? "0" : ((hit == 1) ? "0.6" : "1"));
	y += pitch;

	hit = MM_ChipRow([x, y], "mv_g", "Colour grade", "natural|cool", cvar("milk_grade") ? 1 : 0, labelw);
	if (hit >= 0)
		MM_Seta("milk_grade", ftos(hit));
	y += pitch;

	cur = cvar("milk_react");
	hit = MM_ChipRow([x, y], "mv_r", "Audio reactivity", "off|normal|wild",
	                 cur <= 0 ? 0 : (cur < 1.5 ? 1 : 2), labelw);
	if (hit >= 0)
		MM_Seta("milk_react", (hit == 0) ? "0" : ((hit == 1) ? "1" : "2"));
	y += pitch;

	sky = cvar("milk_sky");
	hit = MM_ChipRow([x, y], "mv_s", "In-game sky", "map's own|visualizer", sky ? 1 : 0, labelw);
	if (hit >= 0)
	{
		MM_Seta("milk_sky", ftos(hit));
		// r_skybox is not archived: csprogs re-applies milk_sky at every map.
		localcmd(hit ? "r_skybox milk\n" : "r_skybox \"\"\n");
	}
	y += pitch;

	hit = MM_ChipRow([x, y], "mv_x", "Menu sounds", "off|on", cvar("milk_sfx") ? 1 : 0, labelw);
	if (hit >= 0)
		MM_Seta("milk_sfx", ftos(hit));
	y += pitch;

	sui_text([x, y + 8], SZ_LABEL,
	         "^9the sky reacts to your speed, landings and whatever is playing", COL_DIM, 1, 0);
	if (!milk_hasvis)
		sui_text([x, y + 34], SZ_LABEL,
		         "^3this engine has no audio analysis -- visuals run without the music", COL_DIM, 1, 0);
	return y + 60;
};

void(vector screensize) MM_ScreenVisuals =
{
	local float x, y;
	local vector sz;

	if (MM_PanelDraw())
	{
		sz = mm_prtsize[mm_pslot];
		x = 48;
		y = 40;
		Font_Set(ui_font_display);
		sui_text([x, y], '64 64 0', "VISUALS", '0.95 0.97 1', 1, 0);
		Font_Set(ui_font_ui);
		sui_fill([x, y + 80], [sz_x - x * 2, 2], Milk_Pal(mm_hue + 0.1), 0.45, 0);
		MM_VisualsRows(x, y + 108, (sz_y >= 760) ? 50 : 42, min(300, floor(sz_x * 0.3)));
		if (ui_option("mv_back", [x, sz_y - 40 - 34], 200, 34, "back", COL_TEXT))
		{
			MM_Sfx("back", 0.5);
			menu_screen = SCREEN_MAIN;
		}
		MM_PanelDone();
		return;
	}

	MM_Shade(screensize, 0.62, 0.85);
	x = floor(screensize_x * 0.075);
	y = floor(screensize_y * 0.5) - 210;

	Font_Set(ui_font_display);
	sui_text([x, y - 70], '64 64 0', "VISUALS", '0.95 0.97 1', 1, 0);
	Font_Set(ui_font_ui);

	y = MM_VisualsRows(x, y, 44, 340);
	if (ui_option("mv_back", [x, y + 10], 200, 34, "back", COL_TEXT))
	{
		MM_Sfx("back", 0.5);
		menu_screen = SCREEN_MAIN;
	}
};

void(float v) MM_VolumeSet = { cvar_set("musicvolume", ftos(v)); };

// The track list at (x, y), `rows` long and `w` wide.
void(float x, float y, float w, float rows) MM_TrackList =
{
	local float i;
	local string name, lbl;

	rows = min(mm_ntracks, rows);
	if (!mm_ntracks)
		sui_text([x, y + 8], SZ_LABEL, "no tracks found", COL_DIM, 1, 0);
	for (i = 0; i < rows; i++)
	{
		name = mm_track[i];
		lbl = strcmp(name, mm_playing) ? name : strcat(name, "   ^2playing");
		if (ui_option(sprintf("mu_t%g", i), [x, y + i * 36], w, 32, lbl, COL_TEXT))
		{
			MM_Sfx("click", 0.4);
			MM_Play(name);
			MM_Seta("milk_menumusic", name);
		}
	}
};

// Transport, volume and the two switches, from `y` down; returns where they end.
float(float x, float y, float labelw) MM_MusicControls =
{
	local float i, hit, vol, w;

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
	                 cvar_string("milk_menumusic") != "", labelw);
	if (hit == 0)
		MM_Seta("milk_menumusic", "");
	else if (hit == 1)
		MM_Seta("milk_menumusic", (mm_playing != "") ? mm_playing : "auto");

	hit = MM_ChipRow([x, y + 92], "mu_l", "Muffle game in menu", "off|on",
	                 cvar("milk_lowpass") ? 1 : 0, labelw);
	if (hit >= 0)
		MM_Seta("milk_lowpass", ftos(hit));
	return y + 136;
};

void(vector screensize) MM_ScreenMusic =
{
	local float x, y, x2, cw, rows;
	local vector sz;

	if (MM_PanelDraw())
	{
		// Two columns: the tracks, and everything that acts on them.
		sz = mm_prtsize[mm_pslot];
		x = 48;
		y = 40;
		x2 = floor(sz_x * 0.52);
		cw = x2 - x - 32;
		Font_Set(ui_font_display);
		sui_text([x, y], '64 64 0', "MUSIC", '0.95 0.97 1', 1, 0);
		Font_Set(ui_font_ui);
		sui_text([x + 2, y + 72], SZ_LABEL, "^9drop .ogg or .wav files into ftesurf/music/", COL_DIM, 1, 0);
		sui_fill([x, y + 100], [sz_x - x * 2, 2], Milk_Pal(mm_hue + 0.1), 0.45, 0);
		rows = floor((sz_y - (y + 124) - 40) / 36);
		MM_TrackList(x, y + 124, cw, rows);

		MM_Spectrum([x2, y + 124], [sz_x - x2 - x, 120]);
		y = MM_MusicControls(x2, y + 268, 180);
		if (ui_option("mu_back", [x2, sz_y - 40 - 34], 200, 34, "back", COL_TEXT))
		{
			MM_Sfx("back", 0.5);
			menu_screen = SCREEN_MAIN;
		}
		MM_PanelDone();
		return;
	}

	MM_Shade(screensize, 0.62, 0.85);
	x = floor(screensize_x * 0.075);
	y = floor(screensize_y * 0.5) - 250;

	Font_Set(ui_font_display);
	sui_text([x, y - 70], '64 64 0', "MUSIC", '0.95 0.97 1', 1, 0);
	Font_Set(ui_font_ui);
	sui_text([x + 2, y - 8], SZ_LABEL, "^9drop .ogg or .wav files into ftesurf/music/", COL_DIM, 1, 0);

	MM_Spectrum([x, y + 22], [520, 96]);
	rows = min(mm_ntracks, 9);
	MM_TrackList(x, y + 132, 520, rows);
	y = MM_MusicControls(x, y + 140 + max(rows, 1) * 36, 340);
	if (ui_option("mu_back", [x, y + 12], 200, 34, "back", COL_TEXT))
	{
		MM_Sfx("back", 0.5);
		menu_screen = SCREEN_MAIN;
	}
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

// ----------------------------------------------------------------- harness --

// Where the centre of main-menu entry `idx` is on screen, at rest: the
// inverse of MM_MouseToUI, for the harness to aim a fake cursor with.
vector(float idx) MM_BcItemScreen =
{
	local vector r0, px, uiy;
	local float pitch;

	MM_Rect(MS_MAIN);
	r0 = [rint(mm_prect0_x * mm_screen_x), rint(mm_prect0_y * mm_screen_y)];
	px = mm_prtsize[mm_pslot];
	pitch = (px_y >= 720) ? MM_ITEM_H : 56;
	uiy = [48 + 60, 40 + 150 + idx * pitch + 29];
	return r0 + uiy;
};

void(string what) MM_BcPanel =
{
	local vector c, h;
	c = mm_pc[mm_pslot];
	h = mm_phalf[mm_pslot];
	print(sprintf("milk_bootcheck: %s world %s station %g panel slot %g",
	              what, MM_WorldName(mm_world), mm_station, mm_pslot));
	print(sprintf(" centre %v half %v px %v lit %g\n", c, h, mm_prtsize[mm_pslot],
	              (mm_pdir[mm_pslot] > 0) ? mm_pon[mm_pslot] : -mm_pon[mm_pslot]));
};

/*
  milk_bootcheck 1: fly every station and photograph it, then quit.
  milk_bootcheck 2: the same, but stay up.
  milk_bootcheck 5: the panels -- at rest, over an entry, orbited, picked.
  Consent is satisfied IN MEMORY for the run, the way ui_bootterms fakes the
  opposite; data/consent.txt is never touched.
*/
void() MM_BootTick =
{
	local float t, w;
	local vector sp, ui;

	if (!mm_bc_step)
	{
		if (!mm_bc_t0)
			mm_bc_consent = ms_consent;
		mm_bc_t0 = -1;
		ms_consent = FS_TERMS_VERSION;
		menu_screen = SCREEN_MAIN;
		// The clock starts once the world has drawn: a first compile of a
		// world's shader can hold the first frame for seconds.
		if (milk_ticks < 5)
			return;
		mm_bc_t0 = gettime(0);
		mm_bc_step = 1;
		print(sprintf("milk_bootcheck: start, engine audio %s, world %s, panels %g, films %g, grade %g\n",
		              milk_hasvis ? "yes" : "no", MM_WorldName(mm_world), cvar("milk_panels"), mm_films, milk_grade));
		return;
	}
	t = gettime(0) - mm_bc_t0;
	mm_bc_frames++;
	mm_bc_kickpk = max(mm_bc_kickpk, milk_kick);
	if (milk_hit >= 0.5 && !mm_bc_hiton)
		mm_bc_hits++;
	mm_bc_hiton = milk_hit >= 0.5;

	// milk_bootcheck 4: frame rate with the space on, then off, over 5 s each,
	// at the station milk_bcstation names (0 main, 1 play, 2 visuals, 3 music)
	// and whatever milk_quality the run set.  Run it uncapped (cl_maxfps 0,
	// vid_wait 0): the difference is the milk's cost.
	if (cvar("milk_bootcheck") == 4)
	{
		if (mm_bc_step == 1 && t > 0.5)
		{
			w = cvar("milk_bcstation");
			if (w == 1)
			{
				menu_screen = SCREEN_CREATE;
				ui_create_open();
			}
			else
				menu_screen = (w == 2) ? SCREEN_VISUALS : ((w == 3) ? SCREEN_MUSIC : SCREEN_MAIN);
			mm_bc_step = 2;
		}
		else if (mm_bc_step == 2 && t > 4.5)
		{
			mm_bc_frames = 0;
			mm_bc_w0 = gettime(0);
			mm_bc_step = 3;
		}
		else if (mm_bc_step == 3 && gettime(0) - mm_bc_w0 > 5)
		{
			w = gettime(0) - mm_bc_w0;
			print(sprintf("milk_bootcheck: perf %s station %g q%g div %g rt %v on  %g fps (%g ms)\n", MM_WorldName(mm_world),
			              mm_station, cvar("milk_quality"), milk_scenediv, milk_rtsize, mm_bc_frames / w, w * 1000 / max(mm_bc_frames, 1)));
			cvar_set("milk_menu", "0");
			mm_bc_w0 = gettime(0);
			mm_bc_step = 4;
		}
		else if (mm_bc_step == 4 && gettime(0) - mm_bc_w0 > 1)
		{
			mm_bc_frames = 0;
			mm_bc_w0 = gettime(0);
			mm_bc_step = 5;
		}
		else if (mm_bc_step == 5 && gettime(0) - mm_bc_w0 > 5)
		{
			w = gettime(0) - mm_bc_w0;
			print(sprintf("milk_bootcheck: perf q%g off %g fps (%g ms)\n", milk_quality,
			              mm_bc_frames / w, w * 1000 / max(mm_bc_frames, 1)));
			cvar_set("milk_menu", "1");
			localcmd("quit\n");
			mm_bc_step = 6;
		}
		return;
	}

	// milk_bootcheck 8: a dive between worlds.  From VISUALS in the world the
	// run started in, milk_world is set to milk_bcworld; a shot in the middle
	// of the plunge and one after it has settled, each with the program drawn.
	if (cvar("milk_bootcheck") == 8)
	{
		if (mm_bc_step == 1 && t > 0.5)
		{
			menu_screen = SCREEN_VISUALS;
			mm_bc_step = 2;
		}
		else if (mm_bc_step == 2 && t > 5)
		{
			print(sprintf("milk_bootcheck: dive from %s (%s)\n", MM_WorldName(mm_world), milk_prog_scene));
			cvar_set("milk_world", cvar_string("milk_bcworld"));
			mm_bc_step = 3;
		}
		else if (mm_bc_step == 3 && t > 6.3)
		{
			print(sprintf("milk_bootcheck: mid-dive world %s prog %s swapped %g\n", MM_WorldName(mm_world), milk_prog_scene, mm_diveswapped));
			localcmd("screenshot milk_dive_mid\n");
			mm_bc_step = 4;
		}
		else if (mm_bc_step == 4 && t > 10)
		{
			print(sprintf("milk_bootcheck: after dive world %s prog %s playing %s\n", MM_WorldName(mm_world), milk_prog_scene, mm_playing));
			MM_BcPanel("dived");
			localcmd("screenshot milk_dive_after\n");
			mm_bc_step = 5;
		}
		else if (mm_bc_step == 5 && t > 11)
		{
			ms_consent = mm_bc_consent;
			localcmd("quit\n");
			mm_bc_step = 6;
		}
		return;
	}

	// milk_bootcheck 7: every station of the world, bare -- no panels, no UI --
	// 4.5 s apart, for looking at the art.  Run with milk_panels 0.
	if (cvar("milk_bootcheck") == 7)
	{
		if (mm_bc_step >= 1 && mm_bc_step <= 4 && t > 0.5 + (mm_bc_step - 1) * 4.5)
		{
			if (mm_bc_step > 1)
				localcmd(sprintf("screenshot milk_art_%s_%g\n", MM_WorldName(mm_world), mm_art));
			mm_art = (mm_bc_step == 1) ? MS_MAIN : ((mm_bc_step == 2) ? MS_PLAY : ((mm_bc_step == 3) ? MS_VIS : MS_MUSIC));
			mm_bc_step++;
		}
		else if (mm_bc_step == 5 && t > 0.5 + 4 * 4.5)
		{
			localcmd(sprintf("screenshot milk_art_%s_%g\n", MM_WorldName(mm_world), mm_art));
			mm_bc_step = 6;
		}
		else if (mm_bc_step == 6 && t > 1.0 + 4 * 4.5)
		{
			// The image list says whether the vessel's films really loaded.
			ms_consent = mm_bc_consent;
			localcmd("r_imagelist\nquit\n");
			mm_bc_step = 7;
		}
		return;
	}

	// milk_bootcheck 5: the panel.  At rest with the cursor over VISUALS (the
	// entry should light), then the cursor far right (the camera orbits; the
	// trace must still land on the same entry), then back.  Each step prints
	// the fake cursor, where MM_MouseToUI put it, and what sui hovers.
	if (cvar("milk_bootcheck") == 5)
	{
		if (mm_bc_step == 1 && t > 4)
		{
			sp = MM_BcItemScreen(1);
			cvar_set("milk_fakemouse", sprintf("%g %g", sp_x, sp_y));
			MM_BcPanel("rest");
			mm_bc_step = 2;
		}
		else if (mm_bc_step == 2 && t > 6)
		{
			sp = MM_Mouse();
			ui = MM_MouseToUI(sp);
			print(sprintf("milk_bootcheck: pick rest mouse %v -> ui %v hover %s yaw %g pitch %g\n",
			              sp, ui, (_hover_action_count > 0) ? _hover_actions[0] : "-", mm_yaw, mm_pitch));
			localcmd("screenshot milk_panel_rest\n");
			mm_bc_step = 3;
		}
		else if (mm_bc_step == 3 && t > 7)
		{
			cvar_set("milk_fakemouse", sprintf("%g %g", mm_screen_x * 0.97, mm_screen_y * 0.25));
			mm_bc_step = 4;
		}
		else if (mm_bc_step == 4 && t > 10)
		{
			sp = MM_Mouse();
			ui = MM_MouseToUI(sp);
			print(sprintf("milk_bootcheck: pick orbit mouse %v -> ui %v yaw %g pitch %g campos %v\n",
			              sp, ui, mm_yaw, mm_pitch, milk_campos));
			localcmd("screenshot milk_panel_orbit\n");
			// Aim at VISUALS again WITHOUT letting the orbit settle: the trace
			// must follow the moved panel.
			sp = MM_BcItemScreen(1);
			ui = MM_MouseToUI(sp);
			print(sprintf("milk_bootcheck: pick orbited-at-rest-coords mouse %v -> ui %v\n", sp, ui));
			mm_bc_step = 5;
		}
		else if (mm_bc_step == 5 && t > 11)
		{
			sp = MM_BcItemScreen(2);
			cvar_set("milk_fakemouse", sprintf("%g %g", sp_x, sp_y));
			mm_bc_step = 6;
		}
		else if (mm_bc_step == 6 && t > 14)
		{
			sp = MM_Mouse();
			ui = MM_MouseToUI(sp);
			print(sprintf("milk_bootcheck: pick back mouse %v -> ui %v hover %s yaw %g pitch %g\n",
			              sp, ui, (_hover_action_count > 0) ? _hover_actions[0] : "-", mm_yaw, mm_pitch));
			localcmd("screenshot milk_panel_back\n");
			mm_bc_step = 7;
		}
		else if (mm_bc_step == 7 && t > 15)
		{
			cvar_set("milk_fakemouse", "");
			ms_consent = mm_bc_consent;
			localcmd("quit\n");
			mm_bc_step = 8;
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
		localcmd("screenshot milk_main\nsnd_visinfo\n");
		print(sprintf("milk_bootcheck: main, rt %v, %g fps, tick %g ms, audio live %g bass %g\n",
		              milk_rtsize, mm_bc_frames / t, milk_tickcost * 1000, milk_live, milk_bass));
		print(sprintf("milk_bootcheck: playing %s\n", mm_playing));
		MM_BcPanel("main");
		mm_bc_step = 2;
	}
	else if (mm_bc_step == 2 && t > 6.5)
	{
		menu_screen = SCREEN_VISUALS;
		mm_bc_step = 3;
	}
	else if (mm_bc_step == 3 && t > 7.5)
	{
		localcmd("screenshot milk_flight\n");
		mm_bc_step = 4;
	}
	else if (mm_bc_step == 4 && t > 11)
	{
		print(sprintf("milk_bootcheck: visuals, simtime %g ticks %g campos %v station %g flight %g\n",
		              milk_simtime, milk_ticks, milk_campos, mm_station, mm_flight0));
		MM_BcPanel("visuals");
		localcmd("screenshot milk_visuals\n");
		menu_screen = SCREEN_MUSIC;
		MM_MusicScan();
		mm_bc_step = 5;
	}
	else if (mm_bc_step == 5 && t > 15)
	{
		MM_BcPanel("music");
		localcmd("screenshot milk_music\n");
		menu_screen = SCREEN_CREATE;
		ui_create_open();
		ui_refilter();
		mm_bc_step = 6;
	}
	else if (mm_bc_step == 6 && t > 19)
	{
		localcmd("screenshot milk_play\n");
		print(sprintf("milk_bootcheck: done, %g frames in %g s = %g fps, %g ticks, audio live %g\n",
		              mm_bc_frames, t, mm_bc_frames / t, milk_ticks, milk_live));
		print(sprintf("milk_bootcheck: big hits %g in %g s, kick peak %g\n", mm_bc_hits, t, mm_bc_kickpk));
		ms_consent = mm_bc_consent;
		menu_screen = SCREEN_MAIN;
		mm_bc_step = 7;
	}
	else if (mm_bc_step == 7 && t > 20)
	{
		mm_bc_step = 8;
		if (cvar("milk_bootcheck") == 1)
			localcmd("quit\n");
	}
};
