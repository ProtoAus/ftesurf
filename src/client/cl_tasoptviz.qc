/*
  P1449: tas optimize's candidates drawn where they fly (TAS_EV_OPTVIZ, sv_tasoptimize.qc
  SV_TASOptVizSend): the recent ones fading -- green reached the target, red met a trigger,
  blue missed -- the best so far bright yellow, the target a cross. `tas_viz 0` hides them.
*/
#define TOV_LINES 64
#define TOV_PTS   32
vector tov_pt[TOV_LINES * TOV_PTS];
float tov_n[TOV_LINES];
float tov_t[TOV_LINES];
float tov_kind[TOV_LINES];
float tov_head;
vector tov_best[TOV_PTS];
float tov_bestn, tov_bestt, tov_final;
vector tov_tgt;
float tov_tgton, tov_tgtt;
var float autocvar_tas_viz = 1;

void() TASOptViz_Event =
{
	local float kind, n, i, slot;
	local vector p;
	kind = readbyte(); n = readbyte();
	if (cvar("developer") && kind != 1 && kind != 2 && kind != 3) print(sprintf("tas_viz: event %g, %g points\n", kind, n));
	if (kind == 0)
	{	// a new search: its start, and its target when one is set
		for (i = 0; i < TOV_LINES; i = i + 1) tov_n[i] = 0;
		tov_bestn = 0; tov_final = 0; tov_tgton = 0; tov_tgtt = cltime;
		for (i = 0; i < n; i = i + 1)
		{
			p_x = readfloat(); p_y = readfloat(); p_z = readfloat();
			if (i == 1) { tov_tgt = p; tov_tgton = 1; }
		}
		return;
	}
	if (kind == 4 || kind == 5)
	{	// the best so far (5), or the one played (4)
		for (i = 0; i < n; i = i + 1)
		{
			p_x = readfloat(); p_y = readfloat(); p_z = readfloat();
			if (i < TOV_PTS) tov_best[i] = p;
		}
		tov_bestn = min(n, TOV_PTS); tov_bestt = cltime; tov_final = (kind == 4);
		return;
	}
	slot = tov_head; tov_head = (tov_head + 1) % TOV_LINES;
	for (i = 0; i < n; i = i + 1)
	{
		p_x = readfloat(); p_y = readfloat(); p_z = readfloat();
		if (i < TOV_PTS) tov_pt[slot * TOV_PTS + i] = p;
	}
	tov_n[slot] = min(n, TOV_PTS); tov_t[slot] = cltime; tov_kind[slot] = kind;
};

// A camera-facing strip, so the best line reads at any distance (GL line width is often 1).
void(vector a, vector b, vector col, float alpha, vector eye, float w) TASOptViz_Strip =
{
	local vector dir, side;
	dir = b - a;
	if (dir == '0 0 0') return;
	side = normalize(crossproduct(normalize(dir), normalize((a + b) * 0.5 - eye))) * (w * 0.5);
	R_BeginPolygon("", DRAWFLAG_TWOSIDED);
	R_PolygonVertex(a - side, '0 0 0', col, alpha);
	R_PolygonVertex(a + side, '0 0 0', col, alpha);
	R_PolygonVertex(b + side, '0 0 0', col, alpha);
	R_PolygonVertex(b - side, '0 0 0', col, alpha);
	R_EndPolygon();
};

// In the depth-tested world pass beside Zone_Draw.
void() TASOptViz_Draw =
{
	local float i, j, age, a, n;
	local vector col, eye;
	if (!autocvar_tas_viz) return;
	eye = getproperty(VF_ORIGIN);
	for (i = 0; i < TOV_LINES; i = i + 1)
	{
		n = tov_n[i];
		if (n < 2) continue;
		age = cltime - tov_t[i];
		if (age > 3) { tov_n[i] = 0; continue; }
		a = 0.6 * (1 - age / 3);
		col = (tov_kind[i] == 2) ? '0.3 1 0.4' : ((tov_kind[i] == 3) ? '1 0.3 0.3' : '0.5 0.7 1');
		for (j = 0; j + 1 < n; j = j + 1)
			TASOptViz_Strip(tov_pt[i * TOV_PTS + j], tov_pt[i * TOV_PTS + j + 1], col, a, eye, 2);
	}
	if (tov_bestn >= 2 && (tov_final ? cltime - tov_bestt < 20 : cltime - tov_bestt < 60))
		for (j = 0; j + 1 < tov_bestn; j = j + 1)
			TASOptViz_Strip(tov_best[j], tov_best[j + 1], tov_final ? '1 1 1' : '1 0.9 0.2', 0.95, eye, 5);
	if (tov_tgton && cltime - tov_tgtt < 120)
	{
		TASOptViz_Strip(tov_tgt - '24 0 0', tov_tgt + '24 0 0', '1 0.4 1', 0.9, eye, 4);
		TASOptViz_Strip(tov_tgt - '0 24 0', tov_tgt + '0 24 0', '1 0.4 1', 0.9, eye, 4);
		TASOptViz_Strip(tov_tgt - '0 0 24', tov_tgt + '0 0 24', '1 0.4 1', 0.9, eye, 4);
	}
};
