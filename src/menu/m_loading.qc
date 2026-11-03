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
*/
#define LS_LOG    8
string ls_log[LS_LOG];          // newest first, zoned; "" = empty
string ls_key[LS_LOG];          // a merged run's kind ("models"), zoned; "" = a single step
float  ls_cnt[LS_LOG];          // ...and how many steps it holds
float  ls_seq;                  // the last scr_loadingseq taken
float  ls_shape;                // 0 avatar, 1 ramp
float  ls_last;                 // when LS_Draw last ran (ls_debug)
var float ls_idle = 1;          // m_draw saw no load since: the next LS_Draw starts one (var: an initialised global is a constant)
string ls_fkey;                 // LS_Friendly's merge key
string ls_prev;                 // ls_debug: the step at the last redraw, zoned
vector ls_ring[5];              // the shape: a convex ring in one plane...
float  ls_rn;
vector ls_ext;                  // ...and the extrusion, perpendicular to it

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
	ls_fkey = "";
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
	if (s == "wads" || s == "external textures")
	{
		ls_fkey = "tex";
		return "Loading textures";
	}
	if (s == "automount" || s == "loading content")
	{
		ls_fkey = "content";
		return "Loading map content";
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
		return "Loading models";
	}
	if (e == ".wav" || e == ".ogg" || e == ".mp3" || e == "flac")
	{
		ls_fkey = "sounds";
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

// One step (`steps` of them since the last draw, if several passed unseen).
void(string raw, float steps) LS_Step =
{
	local string line, top;
	local float i;
	line = LS_Friendly(raw);
	if (ls_fkey != "" && ls_key[0] == ls_fkey)
	{
		ls_cnt[0] = ls_cnt[0] + steps;
		top = sprintf("%s (%g)", line, ls_cnt[0]);
		strunzone(ls_log[0]);
		ls_log[0] = strzone(top);
		return;
	}
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

void(vector scr) LS_Draw =
{
	local float i, seq, px, y, dots;
	local string raw, word;
	if (ls_idle || time < ls_last)
	{	// a new load
		ls_idle = FALSE;
		LS_Clear();
		ls_shape = (random() < 0.5) ? 0 : 1;
		ls_seq = -1;
		ls_last = time;
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
	seq = cvar("scr_loadingseq");
	if (raw != "" && seq != ls_seq)
	{
		LS_Step(raw, (ls_seq < 0 || seq < ls_seq) ? 1 : seq - ls_seq);
		ls_seq = seq;
	}

	drawfill('0 0 0', scr, '0 0 0', 1, 0);
	LS_DrawShape(scr);

	Font_Set(ui_font_ui);
	px = max(10, scr_y / 40);
	y = scr_y * 0.07;
	for (i = 0; i < LS_LOG; i = i + 1)
	{
		if (ls_log[i] == "")
			break;
		drawstring([scr_x * 0.05, y, 0], ls_log[i], [px, px, 0], '1 1 1', max(0.12, 1 - i * 0.15), 0);
		y = y + px * 1.5;
	}
	// "Loading" with 0..3 dots and back, the text held still (it starts where "Loading..." would)
	dots = floor(time * 4.5);
	dots = dots - floor(dots / 6) * 6;
	dots = (dots > 3) ? 6 - dots : dots;
	word = strcat("Loading", substring("...", 0, dots));
	px = max(12, scr_y / 30);
	drawstring([scr_x - scr_x * 0.05 - stringwidth("Loading...", TRUE, [px, px, 0]), scr_y - scr_y * 0.06 - px, 0],
	           word, [px, px, 0], '1 1 1', 1, 0);
	Font_Reset();
};

void(vector screensize, float opaque) m_drawloading =
{
	LS_Draw(screensize);
};
