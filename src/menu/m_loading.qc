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
string ls_fkey;                 // LS_Friendly's merge key
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
	if (substring(s, 0, 9) == "download ")     // engine P1258, one per file
	{
		ls_fkey = "dl";
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

void(vector scr) LS_Draw =
{
	local float i, seq, px, y, dots, bw, bh;
	local string raw, word;
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
	seq = cvar("scr_loadingseq");
	if (raw != "" && seq != ls_seq)
	{
		LS_Step(raw, (ls_seq < 0 || seq < ls_seq) ? 1 : seq - ls_seq);
		ls_seq = seq;
		ls_stept = time;
	}
	LS_Gather();

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
		if (i == 0 && time - ls_stept >= 1)     // how long the newest step has run
			drawstring([scr_x * 0.05 + stringwidth(ls_log[0], TRUE, [px, px, 0]) + px, y, 0],
			           sprintf("%.0f s", time - ls_stept), [px, px, 0], '1 1 1', 0.45, 0);
		y = y + px * 1.5;
	}
	// The bottom-left lines, upward from the line "Loading" sits on, a bar under its line
	px = max(9, scr_y / 50);
	bw = scr_x * 0.3;
	bh = max(2, px * 0.25);
	y = scr_y - scr_y * 0.06;
	for (i = ls_in - 1; i >= 0; i = i - 1)
	{
		if (ls_ibar[i] >= 0)
		{
			y = y - bh;
			drawfill([scr_x * 0.05, y, 0], [bw, bh, 0], '0.25 0.25 0.25', 1, 0);
			drawfill([scr_x * 0.05, y, 0], [bw * ls_ibar[i], bh, 0], '1 1 1', 1, 0);
			y = y - px * 0.4;
		}
		y = y - px;
		drawstring([scr_x * 0.05, y, 0], ls_itext[i], [px, px, 0], '1 1 1', 0.85, 0);
		y = y - px * 0.5;
	}
	if (time - ls_t0 >= 1)                  // the whole load, under "Loading"
	{
		word = sprintf("%.0f s", time - ls_t0);
		drawstring([scr_x - scr_x * 0.05 - stringwidth(word, TRUE, [px, px, 0]), scr_y - scr_y * 0.06 + px * 0.5, 0],
		           word, [px, px, 0], '1 1 1', 0.45, 0);
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
