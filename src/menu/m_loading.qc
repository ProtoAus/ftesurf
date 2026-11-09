/*
  P1244: the loading screen.  m_drawloading draws it under the loading plaque, and m_draw while a
  load runs without one (the connection stage), both through LS_Draw: black; the load's steps in
  white, newest on top, the older pushed down and fading; "Loading" at the bottom right with dots
  that grow and shrink; and a white wireframe spinning in place, seen orthographically from 45
  degrees up -- the lobby avatar (models/player.iqm: a five-sided prism) or a surf ramp (a
  right-angle prism 1.5x its legs long), picked per load.  Both are convex, so an edge is hidden
  exactly when both its faces look away, and the faces read as black without being drawn.
  The steps come from the engine's scr_loadingstep / scr_loadingseq (engine Patch 1244); an older
  engine gives none, and the rest still draws under the plaque.
  P1258: bottom left, what the legacy screen showed -- the address being tried, a download's file,
  percent, rate and size left, and the load percent -- from serverkey, which every engine has.
  Before engine P1258 a download mid-load ended the step, and the engine opened the menu instead.
*/
string(string key) serverkey = #354;    // pr_menu.c:2692; here because this is its first user

#define LS_LOG    8
string ls_log[LS_LOG];          // newest first, zoned; "" = empty
string ls_key[LS_LOG];          // a merged run's kind ("models"), zoned; "" = a single step
float  ls_cnt[LS_LOG];          // ...and how many steps it holds
float  ls_seq;                  // the last scr_loadingseq taken
float  ls_shape;                // 0 avatar, 1 ramp
float  ls_last;                 // when LS_Draw last ran (ls_debug)
var float ls_idle = 1;          // m_draw saw no load since: the next LS_Draw starts one (var: an initialised global is a constant)
string(string s) LS_Base;       // below
string ls_fkey;                 // LS_Friendly's merge key
string ls_fdet;                 // ...and the step's detail: a game, a file's name (P1453; temp string)
string ls_prev;                 // ls_debug: the step at the last redraw, zoned
vector ls_ring[5];              // the shape: a convex ring in one plane...
float  ls_rn;
vector ls_ext;                  // ...and the extrusion, perpendicular to it
float  ls_t0;                   // when this load started
float  ls_stept;                // when the newest step arrived
float  ls_cont0;                // when this connect attempt was first seen, 0 = none
string ls_dlname;               // the download being timed, zoned
float  ls_dlb, ls_dlt, ls_dlrate;   // its bytes and time at the last sample; bytes/s

#define LS_INFO 5
string ls_itext[LS_INFO];       // this frame's bottom-left lines, top to bottom (temp strings)
float  ls_ibar[LS_INFO];        // ...each one's bar, 0..1, or -1 for none
float  ls_in;

// P1265: the map card above them, for engine P1265's scr_loadingmap (none on an older engine).
string ls_cardmap, ls_cardinfo; // the map's name and its detail line, zoned
float  ls_cardpage, ls_cardcell;   // its thumbnail cell, -1 for none
string ls_cardpic;              // P1453: its real picture (local, or the R2 copy online), zoned; "" none
float  ls_cardpicown;           // ...TRUE when this screen loaded it (the browser's own is not ours to free)
float(string nm) ui_map_index;  // m_main.qc
void(float row) ui_load_card;   // m_main.qc: fills ls_cardinfo/page/cell
void(vector pos, vector size, float page, float cell) ui_thumb;  // m_main.qc

#define LS_TWOSIDED 1024        // DRAWFLAG_TWOSIDED (m_stats.qc's MS_TWOSIDED)

// A white line `w` wide: a quad, since the menu's drawline ignores its width (pr_menu.c).
void(vector a, vector c, float w) LS_Line =
{
	local vector d, n;
	d = c - a;
	if (vlen(d) < 0.01)
		return;
	d = normalize(d);
	n = [0 - d_y, d_x, 0] * (w * 0.5);
	R_BeginPolygon("", LS_TWOSIDED, TRUE);
	R_PolygonVertex(a + n, '0 0 0', '1 1 1', 1);
	R_PolygonVertex(c + n, '0 0 0', '1 1 1', 1);
	R_PolygonVertex(c - n, '0 0 0', '1 1 1', 1);
	R_PolygonVertex(a - n, '0 0 0', '1 1 1', 1);
	R_EndPolygon();
};

// The engine clears scr_loadingstep when no load is in progress (engine Patch 1244).
float() LS_Active = { return cvar_string("scr_loadingstep") != ""; };

// The engine's step names, as a player reads them; models, sounds and the like merge into one line.
string(string s) LS_Friendly =
{
	local float n;
	local string e;
	ls_fkey = ls_fdet = "";
	n = strlen(s);
	e = (n > 4) ? strtolower(substring(s, n - 4, 4)) : "";
	if (s == "waiting for connection...")
		return "Connecting to the server";
	if (s == "starting server...")
		return "Starting the server";
	if (s == "receiving map info")
		return "Receiving map info";
	if (s == "receiving game state")
		return "Receiving the game state";
	if (s == "csqc init")
		return "Starting the game code";
	// A game this PC hosts: the server's own steps (sv_init.c).
	if (s == "spawnserver")
		return "Starting the server";
	if (s == "map")
		return "The server is loading the map";
	if (s == "phs")
		return "Working out what can be heard where";
	if (s == "gamecode")
		return "Starting the server's game code";
	if (s == "clients")
		return "Making room for players";
	if (s == "entities")
		return "Placing the map's entities";
	if (s == "finalize server")
		return "Finishing the server";
	if (s == "server spawned")
		return "Server ready";
	if (s == "loading data")
		return "Loading game data";
	if (s == "csprogs" || s == "csprogs world" || s == "hlclient")
	{
		ls_fkey = "code";
		return "Loading the game code";
	}
	if (s == "prenewmap" || s == "newmap")
	{
		ls_fkey = "prep";
		return "Preparing the map";
	}
	// P1453: "wads" is the entity lump's parse for a Source map (Quake's wad list); textures are named
	// by the game they come from (engine P1453: "textures CS:S"), mounts by the game mounted.
	if (s == "wads")
		return "Reading the map's entities";
	if (s == "external textures")
	{
		ls_fkey = "tex";
		return "Loading textures";
	}
	if (substring(s, 0, 9) == "textures ")
	{
		ls_fkey = "tex";
		ls_fdet = substring(s, 9, n - 9);
		return "Loading textures";
	}
	if (substring(s, 0, 6) == "mount ")
	{
		if (substring(s, n - 7, 7) == " cached")
			return sprintf("Mounting %s content (cached copy)", substring(s, 6, n - 13));
		return sprintf("Mounting %s content", substring(s, 6, n - 6));
	}
	if (s == "automount")
		return "Finding the content the map needs";
	if (s == "loading content")
	{
		ls_fkey = "content";
		return "Loading map content";
	}
	if (substring(s, 0, 9) == "download ")     // engine P1258, one per file
	{
		ls_fkey = "dl";
		ls_fdet = LS_Base(substring(s, 9, n - 9));
		return "Downloading files";
	}
	if (e == ".bsp")
		return strcat("Loading the map ", (substring(s, 0, 5) == "maps/") ? substring(s, 5, n - 9) : substring(s, 0, n - 4));
	if (substring(s, 0, 1) == "*")
	{
		ls_fkey = "brush";
		return "Loading map pieces";
	}
	if (e == ".mdl" || e == ".iqm" || e == ".md3" || e == ".md2" || e == ".spr" || e == ".obj" || e == ".dpm")
	{
		ls_fkey = "models";
		ls_fdet = LS_Base(substring(s, 0, n - 4));
		return "Loading models";
	}
	if (e == ".wav" || e == ".ogg" || e == ".mp3" || e == "flac")
	{
		ls_fkey = "sounds";
		ls_fdet = LS_Base(substring(s, 0, (e == "flac") ? n - 5 : n - 4));
		return "Loading sounds";
	}
	return s;
};

void() LS_Clear =
{
	local float i;
	for (i = 0; i < LS_LOG; i = i + 1)
	{
		if (ls_log[i] != "")
			strunzone(ls_log[i]);
		if (ls_key[i] != "")
			strunzone(ls_key[i]);
		ls_log[i] = ls_key[i] = "";
		ls_cnt[i] = 0;
	}
};

// A merged run's line (P1453).
string(string line, float cnt) LS_RunLine =
{
	if (ls_fkey == "tex")       // the engine's step carries this load's games so far
		return (ls_fdet != "") ? strcat("Loading textures: ", ls_fdet) : "Loading textures";
	if (ls_fkey == "models" || ls_fkey == "sounds" || ls_fkey == "dl" || ls_fkey == "brush")
	{
		if (cnt > 1)
			line = sprintf("%s (%g)", line, cnt);
		return (ls_fdet != "") ? strcat(line, ": ", ls_fdet) : line;
	}
	return line;
};

// One step (`steps` of them since the last draw, if several passed unseen).
void(string raw, float steps) LS_Step =
{
	local string line, top;
	local float i;
	line = LS_Friendly(raw);
	if (ls_fkey != "" && ls_key[0] == ls_fkey)
	{
		ls_cnt[0] = ls_cnt[0] + steps;
		top = LS_RunLine(line, ls_cnt[0]);
		if (cvar("ls_debug") >= 2 && top != ls_log[0])
			print(sprintf("loadscreen line: %s  (step %s)\n", top, raw));
		strunzone(ls_log[0]);
		ls_log[0] = strzone(top);
		return;
	}
	line = LS_RunLine(line, 1);
	if (ls_log[LS_LOG - 1] != "")
		strunzone(ls_log[LS_LOG - 1]);
	if (ls_key[LS_LOG - 1] != "")
		strunzone(ls_key[LS_LOG - 1]);
	for (i = LS_LOG - 1; i > 0; i = i - 1)
	{
		ls_log[i] = ls_log[i - 1];
		ls_key[i] = ls_key[i - 1];
		ls_cnt[i] = ls_cnt[i - 1];
	}
	ls_log[0] = strzone(line);
	ls_key[0] = (ls_fkey != "") ? strzone(ls_fkey) : "";
	ls_cnt[0] = 1;
	if (cvar("ls_debug") >= 2)
		print(sprintf("loadscreen line: %s  (step %s)\n", line, raw));
};

void() LS_Shape =
{
	if (ls_shape == 0)
	{	// models/player.iqm welded: its bottom ring, extruded 62 up
		ls_rn = 5;
		ls_ring[0] = '-16 16 0';
		ls_ring[1] = '16 16 0';
		ls_ring[2] = '23.255 0 0';
		ls_ring[3] = '16 -16 0';
		ls_ring[4] = '-16 -16 0';
		ls_ext = '0 0 62';
	}
	else
	{	// a right-angle triangle 40 on its legs, extruded 60 (1.5x) along y
		ls_rn = 3;
		ls_ring[0] = '0 0 0';
		ls_ring[1] = '40 0 0';
		ls_ring[2] = '0 0 40';
		ls_ext = '0 60 0';
	}
};

// Orthographic, 45 degrees down, the shape spun `a` radians about the vertical.
vector ls_cen, ls_org;
float ls_k, ls_sa, ls_ca;
vector(vector p) LS_Rot =
{
	p = p - ls_cen;
	return [p_x * ls_ca - p_y * ls_sa, p_x * ls_sa + p_y * ls_ca, p_z];
};
vector(vector p) LS_Proj =
{
	p = LS_Rot(p);
	return [ls_org_x + ls_k * p_x, ls_org_y - ls_k * (p_y * 0.70710678 + p_z * 0.70710678), 0];
};
// The camera looks along (0, c, -s); a face looks at it when its spun normal has a positive
// share of (0, -c, s).
float(vector n) LS_Faces =
{
	n = [n_x * ls_ca - n_y * ls_sa, n_x * ls_sa + n_y * ls_ca, n_z];
	return n_z * 0.70710678 - n_y * 0.70710678 > 0.0001;
};

void(vector scr) LS_DrawShape =
{
	local float i, j, lw, visa, visb, vi, vj;
	local vector c, e, n, m, ni, na, nb;
	LS_Shape();
	c = '0 0 0';
	for (i = 0; i < ls_rn; i = i + 1)
		c = c + ls_ring[i];
	c = c * (1 / ls_rn);
	ls_cen = c + ls_ext * 0.5;
	ls_org = [scr_x * 0.5, scr_y * 0.5, 0];
	ls_k = scr_y * 0.32 / 62;
	ls_sa = sin(time * 0.8);
	ls_ca = cos(time * 0.8);
	lw = max(1.5, scr_y / 300);
	na = normalize(ls_ext) * -1;
	nb = normalize(ls_ext);
	visa = LS_Faces(na);
	visb = LS_Faces(nb);
	for (i = 0; i < ls_rn; i = i + 1)
	{
		j = (i + 1 < ls_rn) ? i + 1 : 0;
		// side i (ring[i] to ring[j]): outward normal, away from the ring's centre
		e = ls_ring[j] - ls_ring[i];
		n = normalize(crossproduct(e, ls_ext));
		m = (ls_ring[i] + ls_ring[j]) * 0.5 - c;
		if (n * m < 0)
			n = n * -1;
		vi = LS_Faces(n);
		// the side before i, for the lateral edge at ring[i]
		j = (i > 0) ? i - 1 : ls_rn - 1;
		e = ls_ring[i] - ls_ring[j];
		ni = normalize(crossproduct(e, ls_ext));
		m = (ls_ring[i] + ls_ring[j]) * 0.5 - c;
		if (ni * m < 0)
			ni = ni * -1;
		vj = LS_Faces(ni);
		j = (i + 1 < ls_rn) ? i + 1 : 0;
		if (visa || vi)
			LS_Line(LS_Proj(ls_ring[i]), LS_Proj(ls_ring[j]), lw);
		if (visb || vi)
			LS_Line(LS_Proj(ls_ring[i] + ls_ext), LS_Proj(ls_ring[j] + ls_ext), lw);
		if (vi || vj)
			LS_Line(LS_Proj(ls_ring[i]), LS_Proj(ls_ring[i] + ls_ext), lw);
	}
};

/*
  P1453: the map's own model in the middle, when tools/loadwire.py made one for it (gfx/loadwire/<map>.txt,
  format 2, described in the tool; picks in tools/loadwire_picks.txt; one model at random if it has several).
  Painted: black fills hide what is behind, white edges go on top.  The order is the BSP walk the tool built,
  exact from any side, so lines do not fight as it turns (a depth-bucket sort did).  A node's triangles share
  a plane, so its fills all go before its lines: a sibling's fill would shave half of each shared edge.  A
  closed model skips the triangles facing away.
*/
string(string s, float n) LS_Tok;   // below
#define LW_V 1024
#define LW_T 1024
#define LW_N 1024
vector lw_v[LW_V];
vector lw_p[LW_V];              // this frame: screen position
float  lw_ta[LW_T], lw_tb[LW_T], lw_tc[LW_T], lw_tf[LW_T];  // tf: 1 ab, 2 bc, 4 ca drawn; 8 faces against its plane
vector lw_nn[LW_N];             // node: plane normal
float  lw_nf[LW_N], lw_nb[LW_N], lw_n0[LW_N], lw_nc[LW_N];  // front and back child (-1 none), its triangles
float  lw_nv, lw_nt, lw_nnum, lw_closed, lw_ok, lw_bad;
float  lw_es, lw_ec;    // sin, cos of the view's elevation (ls_wireangle: 0 side on, 45 as the shapes)
vector lw_dir;          // this frame: the view direction in model space
float  lw_lw;           // this frame: the line width, whole physical pixels (a fractional one shimmers)
string lw_map;                  // the map the model is for (zoned); "" none tried

float(float i, float n) LW_In = { return i >= 0 && i < n && i == floor(i); };

// Read model `want` (0-based) of the file; -> how many models the file holds.  LS_Tok, not tokenize (see it).
float(string path, float want) LW_Read =
{
	local float f, models, a, b, c;
	local string l, k;
	f = fopen(path, FILE_READ);
	if (f < 0)
		return 0;
	l = fgets(f);
	if (LS_Tok(l, 0) != "FTESURF-LOADWIRE" || LS_Tok(l, 1) != "2")
	{
		fclose(f);
		lw_bad = TRUE;
		return 0;
	}
	models = 0;
	while ((l = fgets(f)) != __NULL__)
	{
		k = LS_Tok(l, 0);
		if (k == "model")
		{
			models = models + 1;
			continue;
		}
		if (want < 0 || models - 1 != want)
			continue;
		if (k == "closed")
			lw_closed = (LS_Tok(l, 1) == "1");
		else if (k == "v")
		{
			if (lw_nv >= LW_V)
			{
				lw_bad = TRUE;
				continue;
			}
			lw_v[lw_nv] = [stof(LS_Tok(l, 1)), stof(LS_Tok(l, 2)), stof(LS_Tok(l, 3))];
			lw_nv = lw_nv + 1;
		}
		else if (k == "t")
		{
			a = stof(LS_Tok(l, 1));
			b = stof(LS_Tok(l, 2));
			c = stof(LS_Tok(l, 3));
			if (lw_nt >= LW_T || !LW_In(a, lw_nv) || !LW_In(b, lw_nv) || !LW_In(c, lw_nv))
			{
				lw_bad = TRUE;
				continue;
			}
			lw_ta[lw_nt] = a;
			lw_tb[lw_nt] = b;
			lw_tc[lw_nt] = c;
			lw_tf[lw_nt] = stof(LS_Tok(l, 4));
			lw_nt = lw_nt + 1;
		}
		else if (k == "n")
		{
			if (lw_nnum >= LW_N)
			{
				lw_bad = TRUE;
				continue;
			}
			lw_nn[lw_nnum] = [stof(LS_Tok(l, 1)), stof(LS_Tok(l, 2)), stof(LS_Tok(l, 3))];
			lw_nf[lw_nnum] = stof(LS_Tok(l, 5));
			lw_nb[lw_nnum] = stof(LS_Tok(l, 6));
			lw_n0[lw_nnum] = stof(LS_Tok(l, 7));
			lw_nc[lw_nnum] = stof(LS_Tok(l, 8));
			lw_nnum = lw_nnum + 1;
		}
	}
	fclose(f);
	return models;
};

// Every node's children come after it (the walk cannot loop) and its triangles are in range.
float() LW_Valid =
{
	local float k;
	for (k = 0; k < lw_nnum; k = k + 1)
	{
		if (lw_nf[k] != -1 && (!LW_In(lw_nf[k], lw_nnum) || lw_nf[k] <= k))
			return FALSE;
		if (lw_nb[k] != -1 && (!LW_In(lw_nb[k], lw_nnum) || lw_nb[k] <= k))
			return FALSE;
		if (!LW_In(lw_n0[k], lw_nt + 1) || !LW_In(lw_nc[k], lw_nt + 1) || lw_n0[k] + lw_nc[k] > lw_nt)
			return FALSE;
	}
	return TRUE;
};

// For the card's map: its model, if gfx/loadwire has one.  Once a map.
void(string mp) LW_Load =
{
	local string path;
	local float models;
	if (mp == lw_map)
		return;
	if (lw_map != "")
		strunzone(lw_map);
	lw_map = (mp != "") ? strzone(mp) : "";
	lw_ok = lw_bad = lw_closed = FALSE;
	lw_nv = lw_nt = lw_nnum = 0;
	if (mp == "")
		return;
	path = strcat("gfx/loadwire/", mp, ".txt");
	models = LW_Read(path, -1);
	if (models > 0)
		LW_Read(path, floor(random() * models));
	lw_ok = (lw_nt > 0 && lw_nnum > 0 && !lw_bad && LW_Valid());
	if (models > 0 && !lw_ok)
		print(sprintf("loadscreen: %s is malformed, over the limits or not format 2; the shape draws\n", path));
};

void(float a, float b) LW_Seg =
{
	LS_Line(lw_p[a], lw_p[b], lw_lw);
};

// One node's triangles, in its plane: every fill, then every drawn edge.
void(float k) LW_Here =
{
	local float i, e, s, f;
	e = lw_n0[k] + lw_nc[k];
	s = lw_nn[k] * lw_dir;          // < 0: the plane's front side faces the camera
	for (i = lw_n0[k]; i < e; i = i + 1)
	{
		if (lw_closed && ((lw_tf[i] & 8) ? 0 - s : s) >= 0)
			continue;
		R_BeginPolygon("", LS_TWOSIDED, TRUE);
		R_PolygonVertex(lw_p[lw_ta[i]], '0 0 0', '0 0 0', 1);
		R_PolygonVertex(lw_p[lw_tb[i]], '0 0 0', '0 0 0', 1);
		R_PolygonVertex(lw_p[lw_tc[i]], '0 0 0', '0 0 0', 1);
		R_EndPolygon();
	}
	for (i = lw_n0[k]; i < e; i = i + 1)
	{
		if (lw_closed && ((lw_tf[i] & 8) ? 0 - s : s) >= 0)
			continue;
		f = lw_tf[i];
		if (f & 1)
			LW_Seg(lw_ta[i], lw_tb[i]);
		if (f & 2)
			LW_Seg(lw_tb[i], lw_tc[i]);
		if (f & 4)
			LW_Seg(lw_tc[i], lw_ta[i]);
	}
};

// Far side of each plane first, then the plane, then the near side.
void(float k) LW_Walk =
{
	if (k < 0)
		return;
	if (lw_nn[k] * lw_dir < 0)
	{
		LW_Walk(lw_nb[k]);
		LW_Here(k);
		LW_Walk(lw_nf[k]);
	}
	else
	{
		LW_Walk(lw_nf[k]);
		LW_Here(k);
		LW_Walk(lw_nb[k]);
	}
};

void(vector scr) LW_Draw =
{
	local float i;
	local vector p;
	ls_cen = '0 0 0';
	ls_org = [scr_x * 0.5, scr_y * 0.5, 0];
	ls_k = scr_y * 0.42 / 62;    // 1.3x the shapes: models are thin, and a 62 box still projects inside +-44
	ls_sa = sin(time * 0.8);
	ls_ca = cos(time * 0.8);
	i = bound(0, cvar("ls_wireangle"), 90) * 0.017453293;    // degrees to radians
	lw_es = sin(i);
	lw_ec = cos(i);
	lw_dir = [ls_sa * lw_ec, ls_ca * lw_ec, 0 - lw_es];      // the camera's (0, ec, -es), unspun
	lw_lw = max(1, rint(scr_y * sui_style_pixel_ratio_y / 540)) / sui_style_pixel_ratio_y;
	for (i = 0; i < lw_nv; i = i + 1)
	{
		p = LS_Rot(lw_v[i]);
		lw_p[i] = [ls_org_x + ls_k * p_x, ls_org_y - ls_k * (p_y * lw_es + p_z * lw_ec), 0];
	}
	LW_Walk(0);
};

string(float b) LS_Bytes =
{
	if (b < 1048576)
		return sprintf("%.0f KB", b / 1024);
	return sprintf("%.1f MB", b / 1048576);
};

string(string s) LS_Base =
{
	local float i, n;
	n = strlen(s);
	for (i = n - 1; i >= 0; i = i - 1)
		if (str2chr(s, i) == 47)    // '/'
			return substring(s, i + 1, n - i - 1);
	return s;
};

void(string s, float bar) LS_Info =
{
	if (ls_in >= LS_INFO)
		return;
	ls_itext[ls_in] = s;
	ls_ibar[ls_in] = bar;
	ls_in = ls_in + 1;
};

// Field n of s (space-separated, a quoted field whole).  Not tokenize: its buffer is shared by every
// VM, and this draws inside their builtins (a loading pump during a CSQC model wait).
string(string s, float n) LS_Tok =
{
	local float i, len, k, q, start;
	len = strlen(s);
	i = 0;
	k = 0;
	while (1)
	{
		while (i < len && str2chr(s, i) == 32)
			i = i + 1;
		if (i >= len)
			return "";
		q = (str2chr(s, i) == 34);
		if (q)
			i = i + 1;
		start = i;
		while (i < len && str2chr(s, i) != (q ? 34 : 32))
			i = i + 1;
		if (k == n)
			return substring(s, start, i - start);
		if (q)
			i = i + 1;
		k = k + 1;
	}
	return "";
};

// The bottom-left lines.  The rate is timed here: the engine refreshes cls.download->rate only
// when the legacy screen or the console asks (CL_DownloadRate).
void() LS_Gather =
{
	local string s, l, name;
	local float i, pct, got, left, stage, tot, more;
	ls_in = 0;
	s = serverkey("transferring");      // the address while the handshake runs, a status line may follow
	if (s == "")
		ls_cont0 = 0;
	else
	{
		if (!ls_cont0)
			ls_cont0 = time;
		i = strstrofs(s, "\n");
		l = strcat("Connecting to ", (i < 0) ? s : substring(s, 0, i));
		if (time - ls_cont0 >= 2)
			l = sprintf("%s (%.0f s)", l, time - ls_cont0);
		LS_Info(l, -1);
		if (i >= 0)
		{
			s = substring(s, i + 1, strlen(s) - i - 1);
			i = strstrofs(s, "\n");
			LS_Info((i < 0) ? s : substring(s, 0, i), -1);
		}
	}
	s = serverkey("dlstate");           // fields as m_main.qc's map downloads read them
	more = stof(LS_Tok(s, 0));
	if (LS_Tok(s, 8) != "")             // a file in flight
	{
		name = LS_Tok(s, 3);
		pct = bound(0, stof(LS_Tok(s, 5)), 100);
		got = stof(LS_Tok(s, 7));
		if (name != ls_dlname || got < ls_dlb)
		{
			if (ls_dlname != "")
				strunzone(ls_dlname);
			ls_dlname = strzone(name);
			ls_dlb = got;
			ls_dlt = time;
			ls_dlrate = 0;
		}
		else if (time - ls_dlt >= 1)
		{
			ls_dlrate = (got - ls_dlb) / (time - ls_dlt);
			ls_dlb = got;
			ls_dlt = time;
		}
		LS_Info(sprintf("Downloading %s  %.0f%%", LS_Base(name), pct), pct / 100);
		left = max(0, stof(LS_Tok(s, 1)) - got);
		l = sprintf("%s%s left", LS_Bytes(left), (stof(LS_Tok(s, 2)) != 0) ? "+" : "");
		if (more > 0)
			l = sprintf("%s, %g more file%s", l, more, (more == 1) ? "" : "s");
		if (ls_dlrate > 0)
			l = sprintf("%s/s, %s", LS_Bytes(ls_dlrate), l);
		LS_Info(l, -1);
	}
	else if (more > 0)
		LS_Info(sprintf("Waiting to download %g file%s", more, (more == 1) ? "" : "s"), -1);
	s = serverkey("loadstate");         // stage current total levelshot (pr_clcmd.c)
	stage = stof(LS_Tok(s, 0));
	tot = stof(LS_Tok(s, 2));
	if (stage >= 2 && tot > 0)          // LS_SERVER, LS_CLIENT
	{
		pct = bound(0, stof(LS_Tok(s, 1)) / tot, 1);
		LS_Info(sprintf("%s %.0f%%", (stage == 2) ? "Server" : "Game", pct * 100), pct);
	}
};

// The card is looked up once a map: ui_map_index scans the whole list.
// ls_debug 3 (P1453): the centre drawing's QC time and the frame rate, every 2 s.
float ls_pfn, ls_pft, ls_pf0;
void(float dt) LS_Perf =
{
	local float now;
	now = gettime(1);
	if (!ls_pf0)
		ls_pf0 = now;
	ls_pfn = ls_pfn + 1;
	ls_pft = ls_pft + dt;
	if (now - ls_pf0 < 2)
		return;
	print(sprintf("loadscreen perf: %s %.1f fps, centre %.3f ms a frame\n", lw_ok ? "wire" : "shape",
	              ls_pfn / (now - ls_pf0), ls_pft * 1000 / ls_pfn));
	ls_pf0 = now;
	ls_pfn = ls_pft = 0;
};

void() LS_Card =
{
	local string m;
	m = cvar_string("scr_loadingmap");
	if (m == "" && !LS_Active())
		m = cvar_string("ls_preview");     // P1453: set ls_preview <map> -- this screen, no load (screenshots)
	if (m == ls_cardmap)
		return;
	if (ls_cardmap != "")
		strunzone(ls_cardmap);
	ls_cardmap = (m != "") ? strzone(m) : "";
	ui_load_card((m != "") ? ui_map_index(m) : -1);
	LW_Load(m);     // P1453
};

// P1453: the picture cropped to 16:9 into the card's box (the R2 copy is 16:9; a local one may not be).
vector(string pic) drawgetimagesize_async;     // m_main.qc
void(vector pos, vector size, vector isz) LS_CardPic =
{
	local float ar, u0, v0, u1, v1;
	ar = isz_x / isz_y;
	u0 = v0 = 0;
	u1 = v1 = 1;
	if (ar > 16 / 9)
	{
		u0 = (1 - (16 / 9) / ar) * 0.5;
		u1 = 1 - u0;
	}
	else if (ar < 16 / 9)
	{
		v0 = (1 - ar / (16 / 9)) * 0.5;
		v1 = 1 - v0;
	}
	drawsubpic(pos, size, ls_cardpic, [u0, v0, 0], [u1 - u0, v1 - v0, 0], '1 1 1', 1, 0);
};

void(vector scr) LS_Draw =
{
	local float i, seq, y, dots, bw, bh, phys, x0, th, t0;
	local string raw, word;
	local vector sz, nsz, pic;
	if (ls_idle || time < ls_last)
	{	// a new load
		ls_idle = FALSE;
		LS_Clear();
		ls_shape = (random() < 0.5) ? 0 : 1;
		ls_seq = -1;
		ls_last = ls_t0 = ls_stept = time;
		ls_cont0 = 0;
	}
	raw = cvar_string("scr_loadingstep");
	if (cvar("ls_debug") && time - ls_last > 0.05)   // set ls_debug 1: every stall
		print(sprintf("loadscreen: %.0f ms without a redraw, from %s to %s\n", (time - ls_last) * 1000, ls_prev, raw));
	ls_last = time;
	if (raw != ls_prev)
	{
		if (ls_prev != "")
			strunzone(ls_prev);
		ls_prev = (raw != "") ? strzone(raw) : "";
	}
	if (raw == "" && cvar_string("ls_preview") != "" && ls_log[0] == "")
	{	// P1453: ls_preview's sample, the engine's own strings in a typical order
		LS_Step("receiving map info", 1);
		LS_Step("automount", 1);
		LS_Step("mount CS:GO", 1);
		LS_Step("wads", 1);
		LS_Step("textures World of Surf", 1);
		LS_Step("textures World of Surf, CS:S", 1);
		LS_Step("textures World of Surf, CS:S, HL2", 1);
		LS_Step("textures World of Surf, CS:S, HL2, the map", 1);
		LS_Step("models/props/de_dust/dust_crate.mdl", 1);
		LS_Step("models/disres_models/dagger.mdl", 1);
	}
	seq = cvar("scr_loadingseq");
	if (raw != "" && seq != ls_seq)
	{
		LS_Step(raw, (ls_seq < 0 || seq < ls_seq) ? 1 : seq - ls_seq);
		ls_seq = seq;
		ls_stept = time;
	}
	LS_Gather();

	drawfill('0 0 0', scr, '0 0 0', 1, 0);
	LS_Card();      // P1453: before the shape, which may be the card's map's model
	t0 = gettime(1);
	if (lw_ok)
		LW_Draw(scr);
	else
		LS_DrawShape(scr);
	if (cvar("ls_debug") >= 3)
		LS_Perf(gettime(1) - t0);

	// Text on the UI face's physical (pixels=1) bake at a baked size, on whole pixels: a size between
	// rungs is a resample.  Physical sizes from the screen's height; 1080 p: steps and the map's name
	// 20, lines 16, "Loading" 28.
	sui_style_hud(scr);
	phys = scr_y * sui_style_pixel_ratio_y;
	Font_Set(ui_font_ui);
	drawfont = Font_NativeSlot(ui_font_ui);
	x0 = scr_x * 0.05;
	sz = sui_native_text_size(bound(12, phys / 54, 32));
	nsz = sz;
	y = scr_y * 0.07;
	for (i = 0; i < LS_LOG; i = i + 1)
	{
		if (ls_log[i] == "")
			break;
		drawstring(_sui_pixel_align([x0, y]), ls_log[i], sz, '1 1 1', max(0.12, 1 - i * 0.15), 0);
		if (i == 0 && time - ls_stept >= 1)     // how long the newest step has run
			drawstring(_sui_pixel_align([x0 + stringwidth(ls_log[0], TRUE, sz) + sz_y, y]),
			           sprintf("%.0f s", time - ls_stept), sz, '1 1 1', 0.45, 0);
		y = y + sz_y * 1.5;
	}
	// The bottom-left lines, upward from the line "Loading" sits on, a bar under its line
	sz = sui_native_text_size(bound(12, phys / 68, 32));
	bw = scr_x * 0.3;
	bh = max(2, floor(sz_y * 0.25 * sui_style_pixel_ratio_y)) / sui_style_pixel_ratio_y;
	y = scr_y - scr_y * 0.06;
	for (i = ls_in - 1; i >= 0; i = i - 1)
	{
		if (ls_ibar[i] >= 0)
		{
			y = y - bh;
			drawfill(_sui_pixel_align([x0, y]), [bw, bh, 0], '0.25 0.25 0.25', 1, 0);
			drawfill(_sui_pixel_align([x0, y]), [bw * ls_ibar[i], bh, 0], '1 1 1', 1, 0);
			y = y - sz_y * 0.4;
		}
		y = y - sz_y;
		drawstring(_sui_pixel_align([x0, y]), ls_itext[i], sz, '1 1 1', 0.85, 0);
		y = y - sz_y * 0.5;
	}
	// P1265: the map's card above them: name, the map list's detail line, thumbnail (1080 p: 160 px tall)
	LS_Card();
	if (ls_cardmap != "")
	{
		y = y - sz_y * 0.75;
		pic = (ls_cardpic != "" && checkbuiltin(drawgetimagesize_async)) ? drawgetimagesize_async(ls_cardpic) : '0 0 0';
		if ((ls_cardpage >= 0 && ls_cardcell >= 0) || (pic_x > 0 && pic_y > 0))
		{
			th = floor(phys / 6.75) / sui_style_pixel_ratio_y;
			y = y - th;
			if (pic_x > 0 && pic_y > 0)
				LS_CardPic(_sui_pixel_align([x0, y]), [th * 16 / 9, th], pic);
			else
				ui_thumb(_sui_pixel_align([x0, y]), [th * 16 / 9, th], ls_cardpage, ls_cardcell);
			y = y - sz_y * 0.6;
		}
		if (ls_cardinfo != "")
		{
			y = y - sz_y;
			drawstring(_sui_pixel_align([x0, y]), ls_cardinfo, sz, '1 1 1', 0.6, 0);
			y = y - sz_y * 0.35;
		}
		y = y - nsz_y;
		drawstring(_sui_pixel_align([x0, y]), ls_cardmap, nsz, '1 1 1', 1, 0);
	}
	if (time - ls_t0 >= 1)                  // the whole load, under "Loading"
	{
		word = sprintf("%.0f s", time - ls_t0);
		drawstring(_sui_pixel_align([scr_x - x0 - stringwidth(word, TRUE, sz), scr_y - scr_y * 0.06 + sz_y * 0.5]),
		           word, sz, '1 1 1', 0.45, 0);
	}
	// "Loading" with 0..3 dots and back, the text held still (it starts where "Loading..." would)
	dots = floor(time * 4.5);
	dots = dots - floor(dots / 6) * 6;
	dots = (dots > 3) ? 6 - dots : dots;
	word = strcat("Loading", substring("...", 0, dots));
	sz = sui_native_text_size(bound(16, phys / 38, 32));
	drawstring(_sui_pixel_align([scr_x - x0 - stringwidth("Loading...", TRUE, sz), scr_y - scr_y * 0.06 - sz_y]),
	           word, sz, '1 1 1', 1, 0);
	Font_Reset();
};

void(vector screensize, float opaque) m_drawloading =
{
	LS_Draw(screensize);
};
