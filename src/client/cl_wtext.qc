/*
  cl_wtext.qc -- P1438: point_worldtext (CS:GO / Momentum), drawn from the lump.

  The font is a sheet of 16 x 16 cells, ASCII 32-127 from the top-left (CS:GO's editor/worldtextsheet, Momentum's
  editor/worldtextsheet_* -- read off the sheets).  Each character is one cell drawn textsize square; they advance
  0.6 x textsize along the entity's right, from its origin at the bottom-left, readable from behind its forward
  (the material is $nocull, so mirrored from the front).  Momentum's source is not public: the advance and the
  anchor are read off how mappers placed texts beside each other (bhop_bowling's "Round" then "1": 14 units of
  gap at 0.6; Momentum's training maps' titles centred over their subtitles: 0.45-0.56), the side off which way
  the text runs.  A font that does not resolve falls back to editor/worldtext, then Momentum's Roboto-Mono.

  ENTWIRE_WTEXT (sv_entities.qc SV_WtSend) carries Enable/Disable/Toggle, SetMessage and AddOutput's message,
  color and textsize for a named one.  Drawn when in the view cone and within vbsp_sprite_dist and ~400 x textsize.
*/

#define WT_MAX        512       // the library's most on a map is 157 (bhop_2shiny2shuckle)
#define WT_ADV        0.6

vector *wt_org;
vector *wt_r;
vector *wt_u;
float  *wt_s;
vector *wt_col;
float  *wt_mat;
float  *wt_on;
float  *wt_tnc;
string wt_msg[WT_MAX];          // strzone'd
float  vbsp_wt_n, vbsp_wt_skip;

void() Wt_Alloc =
{
	if (wt_org)
		return;
	wt_org = memalloc(sizeof(vector) * WT_MAX);
	wt_r = memalloc(sizeof(vector) * WT_MAX);
	wt_u = memalloc(sizeof(vector) * WT_MAX);
	wt_s = memalloc(sizeof(float) * WT_MAX);
	wt_col = memalloc(sizeof(vector) * WT_MAX);
	wt_mat = memalloc(sizeof(float) * WT_MAX);
	wt_on = memalloc(sizeof(float) * WT_MAX);
	wt_tnc = memalloc(sizeof(float) * WT_MAX);
};

void(float i, string s) Wt_SetMsg =
{
	if (wt_msg[i] != "")
		strunzone(wt_msg[i]);
	wt_msg[i] = "";
	if (s != "")
		wt_msg[i] = strzone(s);
};

// ENTWIRE_WTEXT (cl_body.qc): shown or not, and the message once SetMessage has set one.
void(entity e) Wt_Net =
{
	local float i;
	if (cvar("vbsp_fx_debug"))
		print(sprintf("wtext: net at %v name %g on %g message set %g \"%s\"\n", e.origin, e.fx_ntnc, e.fx_non, e.wt_nset, e.wt_nmsg));
	for (i = 0; i < wt_n; i = i + 1)
	{
		if (wt_tnc[i] != e.fx_ntnc || vlen(wt_org[i] - e.origin) > 0.1)
			continue;
		wt_on[i] = e.fx_non;
		if (e.wt_nset & WT_SET_MSG)
			Wt_SetMsg(i, e.wt_nmsg);
		if (e.wt_nset & WT_SET_COL)
			wt_col[i] = e.wt_ncol * (1 / 255);
		if (e.wt_nset & WT_SET_SIZE)
		if (e.wt_nsize > 0)
			wt_s[i] = e.wt_nsize;
	}
};

// The lump.  Called from Sprite_LoadForMap.
void() Wt_LoadForMap =
{
	local string tok, key, cn, tn, pn, msg, font, scol;
	local vector org, ang;
	local float sf, sz, i, m;
	local entity net;

	Wt_Alloc();
	for (i = 0; i < wt_n; i = i + 1)
		Wt_SetMsg(i, "");
	wt_n = vbsp_wt_n = vbsp_wt_skip = 0;
	if (!vbsp_wt_seen)
		return;
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = tn = pn = msg = font = scol = "";
		org = ang = '0 0 0';
		sf = 0;
		sz = 10;
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")  cn = tok;
			else if (key == "origin")     org = Sprite_ParseVec(tok);
			else if (key == "angles")     ang = Sprite_ParseVec(tok);
			else if (key == "targetname") tn = tok;
			else if (key == "parentname") pn = tok;
			else if (key == "message")    msg = tok;
			else if (key == "textsize")   sz = stof(tok);
			else if (key == "color")      scol = tok;
			else if (key == "font")       font = tok;
			else if (key == "spawnflags") sf = stof(tok);
		}
		if (cn != "point_worldtext")
			continue;
		if (pn != "" || wt_n >= WT_MAX || sz <= 0)
		{	// a moving parent takes it somewhere the lump does not know
			vbsp_wt_skip = vbsp_wt_skip + 1;
			continue;
		}
		m = -1;
		if (font != "")
			m = Sprite_Material(font, 0);
		if (m < 0)
			m = Sprite_Material("editor/worldtext", 0);
		if (m < 0)
			m = Sprite_Material("editor/worldtext_roboto-mono", 0);
		if (m < 0)
		{
			vbsp_wt_skip = vbsp_wt_skip + 1;
			continue;
		}
		i = wt_n;
		makevectors(ang);
		wt_org[i] = org;
		wt_r[i] = v_right;
		wt_u[i] = v_up;
		wt_s[i] = sz;
		wt_col[i] = (scol != "") ? Sprite_ParseColor(scol) : '1 1 1';
		wt_mat[i] = m;
		wt_on[i] = !(sf & 1);           // SF 1: Start Disabled
		wt_tnc[i] = crc16(TRUE, tn);
		Wt_SetMsg(i, msg);
		wt_n = wt_n + 1;
	}
	vbsp_wt_n = wt_n;
	print(sprintf("worldtext: %g of %g point_worldtext drawn (%g declined: parented, no font, over the cap)\n",
	              wt_n, vbsp_wt_seen, vbsp_wt_skip));
	for (net = find(world, classname, "wtext_net"); net; net = find(net, classname, "wtext_net"))
		Wt_Net(net);            // states that arrived before this load
};

// Called from Sprite_Draw; returns the texts drawn.
float(vector eye, vector fwd, float maxdist) Wt_Draw =
{
	local float i, k, n, s, a, c, col, row, drawn, rad, x0, len;
	local vector o, r, u, mid, p, q, cl;
	local string msg, mat;

	if (!wt_n || !cvar("vbsp_worldtext"))
		return 0;
	drawn = 0;
	for (i = 0; i < wt_n; i = i + 1)
	{
		if (!wt_on[i])
			continue;
		msg = wt_msg[i];
		n = strlen(msg);
		if (!n)
			continue;
		s = wt_s[i];
		a = s * WT_ADV;
		o = wt_org[i];
		r = wt_r[i];
		u = wt_u[i];
		mid = o + r * (n * a * 0.5) + u * (s * 0.5);
		rad = n * a * 0.5 + s;
		len = vlen(mid - eye);
		if (fwd * (mid - eye) < len * 0.259 - rad)
			continue;                   // outside a 75-degree cone round the view (a 16:9 fov of 130 reaches 68 at its corners)
		if (len - rad > s * 400)
			continue;                   // under a couple of pixels tall
		if (maxdist > 0 && len - rad > maxdist)
			continue;
		mat = sprmat_name[wt_mat[i]];
		cl = wt_col[i];
		for (k = 0; k < n; k = k + 1)
		{
			c = str2chr(msg, k);
			if (c < 33 || c > 126)
				continue;
			col = (c - 32) - 16 * floor((c - 32) / 16);
			row = floor((c - 32) / 16);
			x0 = k * a + a * 0.5 - s * 0.5;     // the cell centred on its advance
			p = o + r * x0;
			q = p + r * s;
			R_BeginPolygon(mat, 0);
			R_PolygonVertex(p + u * s, [col / 16, row / 16, 0], cl, 1);
			R_PolygonVertex(q + u * s, [(col + 1) / 16, row / 16, 0], cl, 1);
			R_PolygonVertex(q, [(col + 1) / 16, (row + 1) / 16, 0], cl, 1);
			R_PolygonVertex(p, [col / 16, (row + 1) / 16, 0], cl, 1);
			R_EndPolygon();
		}
		drawn = drawn + 1;
	}
	return drawn;
};
