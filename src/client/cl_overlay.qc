/*
  cl_overlay.qc -- P1439: env_screenoverlay, as c_env_screenoverlay.cpp.

  StartOverlays shows OverlayName1 for OverlayTime1 seconds, then the next, until a blank name; -1 holds one for
  good.  When the run ends the LAST overlay stays on screen: Source's StopOverlays clears the view only on an
  active-to-inactive update, which only the StopOverlays input sends.  SwitchOverlay N jumps to overlay N.  A
  second StartOverlays while an overlay is up changes nothing (Source starts only with no overlay up), and
  StartOverlays deactivates the map's other overlays without clearing what is shown.  The view has one overlay
  (FL_EDICT_ALWAYS: everyone sees it, as in Source multiplayer).

  Only shaders FTE draws as a picture with a $basetexture are shown (UnlitGeneric and kin): Refract, screen-space
  and YUV ones would paste a flat texture -- or, with no base texture, solid white -- over the screen; such a step
  shows nothing for its time and the run goes on.  A run advances whatever menu is up (Ov_Think, every frame).
  Times are SendPropFloat's 11 bits over -1..63, rounded down.  Not as Source: one run at a time (a SwitchOverlay
  on another overlay takes the view over), and StartOverlays on an overlay with no OverlayName1 still deactivates
  the others (the server does not know the names).
  The state rides ENTWIRE_FXSTATE2 class FX_CLS_OVERLAY: on = 0 after StopOverlays, else 128 if active plus the
  wanted overlay + 1; StartOverlays is the event.
*/

#define OV_MAX        32
#define OV_N          10

float  ov_n;
vector ov_korg[OV_MAX];
float  ov_tnc[OV_MAX];
string ov_name[OV_MAX * OV_N];  // strzone'd stems, "" none
float  ov_time[OV_MAX * OV_N];
float  ov_act[OV_MAX];
float  ov_was[OV_MAX];
float  ov_des[OV_MAX];
float  ov_cdes[OV_MAX];
float  ov_ent;                  // whose overlays the view is showing, -1 none
float  ov_cur;
float  ov_end;                  // when the current one ends, -1 never
float  ov_think;
string ov_mat;                  // the view's overlay (a sprmat stem), "" none
float  vbsp_ov_n;
string ov_loadmap;              // a reload on the same map (a cvar toggle) keeps the state

// A material the view can show, as a sprmat index, or -1 (missing, or a screen-space shader drawn flat here).
float(string nm) Ov_Mat =
{
	local string stem, l, sh;
	local float f, m, k, base;
	stem = Sprite_MatStem(nm);
	if (stem == "")
		return -1;
	f = fopen(strcat("materials/", stem, ".vmt"), FILE_READ);
	if (f < 0)
		return -1;
	sh = "";
	base = FALSE;
	for (k = 0; k < 48; k = k + 1)
	{	// a fixed budget: fgets' EOF and a blank line are both ""
		l = strtolower(strreplace("\"", "", strtrim(fgets(f))));
		if (l == "" || substring(l, 0, 2) == "//")
			continue;
		if (sh == "")
			sh = l;             // the shader: the first line that says anything
		if (strstrofs(l, "$basetexture", 0) >= 0)
			base = TRUE;
	}
	fclose(f);
	if (sh != "patch")
	if (!base || (sh != "unlitgeneric" && sh != "vertexlitgeneric" && sh != "lightmappedgeneric" &&
	              sh != "sprite" && sh != "unlittwotexture" && sh != "modulate"))
		return -1;
	m = Sprite_Material(stem, 0);
	return m;
};

void(float i) Ov_StartCurrent =
{
	local string nm;
	local float m;
	nm = (ov_cur < OV_N) ? ov_name[i * OV_N + ov_cur] : "";
	if (nm == "")
	{	// the end: Source's StopOverlays clears only on an active-to-inactive update
		ov_think = FALSE;
		if (ov_was[i] && !ov_act[i])
			ov_mat = "";
		return;
	}
	ov_end = (ov_time[i * OV_N + ov_cur] == -1) ? -1 : time + ov_time[i * OV_N + ov_cur];
	m = Ov_Mat(nm);
	if (m < 0)
	{	// a screen effect FTE cannot draw (or missing): nothing for its time, then the run goes on
		ov_mat = "";
		if (cvar("vbsp_fx_debug"))
			print(sprintf("overlay: %s not drawn (missing or a screen effect)\n", nm));
		return;
	}
	ov_mat = sprmat_name[m];
	if (cvar("vbsp_fx_debug"))
		print(sprintf("overlay: %g shows %g \"%s\" until %g (now %g)\n", i, ov_cur, ov_mat, ov_end, time));
};

void(float i) Ov_Switch =
{
	if (ov_cdes[i] == ov_des[i])
		return;
	ov_cdes[i] = ov_des[i];
	ov_cur = ov_des[i];
	if (ov_ent != i)
		ov_think = FALSE;       // its own think has not started
	ov_ent = i;
	Ov_StartCurrent(i);
};

// ENTWIRE_FXSTATE2 class FX_CLS_OVERLAY (Fx_Net forwards it): PostDataUpdate's three steps.
void(entity e) Ov_FxNet =
{
	local float i, stop;
	for (i = 0; i < ov_n; i = i + 1)
	{
		if (ov_tnc[i] != e.fx_ntnc || vlen(ov_korg[i] - e.origin) > 0.1)
			continue;
		ov_was[i] = ov_act[i];
		stop = (e.fx_non == 0);
		ov_act[i] = (e.fx_non & 128) != 0;
		if (!stop)
		if (ov_name[i * OV_N + bound(0, (e.fx_non & 127) - 1, OV_N - 1)] != "")
			ov_des[i] = bound(0, (e.fx_non & 127) - 1, OV_N - 1);   // Source ignores a switch to an empty slot
		if (ov_act[i] && ov_mat == "")
		if (e.fx_nfire || !ov_was[i])
		{	// StartOverlays
			ov_ent = i;
			ov_cur = 0;
			ov_cdes[i] = 0;
			ov_think = TRUE;
			Ov_StartCurrent(i);
		}
		if (stop)
		{
			if (ov_ent == i)
				ov_think = FALSE;
			if (ov_was[i])
				ov_mat = "";
		}
		Ov_Switch(i);
	}
};

// Called from Sprite_LoadForMap.
void() Ov_LoadForMap =
{
	local string tok, key, cn, tn;
	local vector org;
	local float i, k, n;
	local string nm[OV_N];
	local float tm[OV_N];
	local entity net;

	if (ov_n && ov_loadmap == CL_LumpMapName())	// P1489
		return;                 // a cvar toggle re-ran the load: keep what is showing
	if (ov_loadmap != "")
		strunzone(ov_loadmap);
	ov_loadmap = strzone(CL_LumpMapName());
	for (i = 0; i < ov_n * OV_N; i = i + 1)
		if (ov_name[i] != "")
		{
			strunzone(ov_name[i]);
			ov_name[i] = "";
		}
	ov_n = vbsp_ov_n = 0;
	ov_mat = "";
	ov_ent = -1;
	ov_think = FALSE;
	if (!vbsp_ov_seen_n)
		return;
	getentitytoken(0);
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		cn = tn = "";
		org = '0 0 0';
		for (k = 0; k < OV_N; k = k + 1)
		{
			nm[k] = "";
			tm[k] = 0;
		}
		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")  cn = tok;
			else if (key == "origin")     org = Sprite_ParseVec(tok);
			else if (key == "targetname") tn = tok;
			else if (substring(key, 0, 11) == "overlayname")
			{
				n = stof(substring(key, 11, -1)) - 1;
				if (n >= 0 && n < OV_N)
					nm[n] = tok;
			}
			else if (substring(key, 0, 11) == "overlaytime")
			{
				n = stof(substring(key, 11, -1)) - 1;
				if (n >= 0 && n < OV_N)
					tm[n] = stof(tok);
			}
		}
		if (cn != "env_screenoverlay" || tn == "" || ov_n >= OV_MAX)
			continue;
		if (nm[0] == "")
			continue;               // Source ignores every input of one with no OverlayName1
		i = ov_n;
		ov_korg[i] = org;
		ov_tnc[i] = crc16(TRUE, tn);
		ov_act[i] = ov_was[i] = ov_des[i] = ov_cdes[i] = 0;
		for (k = 0; k < OV_N; k = k + 1)
		{
			ov_name[i * OV_N + k] = (nm[k] != "") ? strzone(nm[k]) : "";
			// SendPropFloat(11 bits, -1..63, SPROP_ROUNDDOWN)
			ov_time[i * OV_N + k] = floor((bound(-1, tm[k], 63) + 1) / 64 * 2047) * 64 / 2047 - 1;
		}
		ov_n = ov_n + 1;
	}
	vbsp_ov_n = ov_n;
	print(sprintf("overlays: %g of %g env_screenoverlay kept for their inputs\n", ov_n, vbsp_ov_seen_n));
	for (net = find(world, classname, "fx_net"); net; net = find(net, classname, "fx_net"))
		if (net.fx_ncls == FX_CLS_OVERLAY)
			Ov_FxNet(net);      // states that arrived before this load (their start events spent)
};

// ClientThink: the current one ran out, on to the next.  Every frame (cl_main.qc), menu or not.
void() Ov_Think =
{
	if (ov_think && ov_ent >= 0)
	if (ov_end != -1 && time > ov_end)
	{
		ov_cur = ov_cur + 1;
		Ov_StartCurrent(ov_ent);
	}
};

// The view's overlay, over the world and under the HUD (cl_main.qc, beside MapMsg_DrawFade).
void(vector scr) Ov_Draw =
{
	if (ov_mat == "")
		return;
	if (!cvar("vbsp_overlays_screen"))
		return;
	R_BeginPolygon(ov_mat, 0, TRUE);
	R_PolygonVertex('0 0 0', '0 0 0', '1 1 1', 1);
	R_PolygonVertex([scr_x, 0, 0], '1 0 0', '1 1 1', 1);
	R_PolygonVertex([scr_x, scr_y, 0], '1 1 0', '1 1 1', 1);
	R_PolygonVertex([0, scr_y, 0], '0 1 0', '1 1 1', 1);
	R_EndPolygon();
};
