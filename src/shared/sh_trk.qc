/*
  P1378: a passable func_tracktrain on its path_tracks (trains.cpp), and the non-solid props that ride
  it. The server keeps each train's clock -- only an input changes it -- and sends it once as a CSQC
  entity (ENTWIRE_TRKSTATE, sv_entities.qc SV_TrkSend); csprogs (cl_trk.qc) draws the train and its
  props every frame from the same numbers, so nothing moves on the wire. Both progs build the same path
  from the same path_tracks with the code below.

  Census (2,206 maps): 438 passable on 51 maps, 369 moving at spawn, 403 on a loop; surf_centipedes'
  3D-sky birds are 105 props on 35. Not modelled: per-path_track speeds (32 trains on 8 maps keep their
  own), OnPass/OnTeleport and the train's own outputs, bank, velocitytype's accel. surf_colony's sky
  canisters loop by OnPass/OnTeleport and are solid, so they stay where they are.
*/
#define TRK_SF_ID       1       // ENTWIRE_TRKSTATE: model, spawn pose, path keys
#define TRK_SF_CLOCK    2       // ENTWIRE_TRKSTATE: s0, t0, speed, direction
#define SF_PATH_DISABLED            1   // pathtrack.h
#define SF_PATH_TELEPORT            16
#define SF_TRACKTRAIN_NOPITCH       1   // trains.h
#define SF_TRACKTRAIN_FIXEDORIENT   16

// path_track table, per map: sv fills it from path_track's spawn, cl from the entity lump.
float     trk_pn, trk_pcap;
vector   *trk_porg;
float    *trk_pfl;
float    *trk_pnext;            // next node, -1 none (Trk_TableLink)
strbuf    trk_pbuf;             // "name\ttarget" per node
hashtable trk_ptab;             // lowercased name -> index + 1, the first of that name (FindEntityByName)

// Every train's points in path order, appended by Trk_Walk.
float     trk_np, trk_cap;
vector   *trk_p;
float    *trk_s;                // arc length at each point
float    *trk_r;                // its path_track, for TeleportToPathTrack

.float  trk_i0, trk_n, trk_k, trk_len;      // points in the pool; loop re-entry or -1; length
.float  trk_s0, trk_t0, trk_spd, trk_dir;   // arc length s0 at t0, moving at spd * dir
.float  trk_old, trk_max;                   // Stop's speed for Resume; max speed (startspeed)
.float  trk_height, trk_wheels, trk_orient, trk_sflags;
.vector trk_o0, trk_a0;                     // spawn pose: the frame its props were placed in
.vector trk_alast;                          // facing; spawn angles until Trk_Pose faces it
.float  trk_faced;
.vector trk_wo, trk_wf, trk_wl, trk_wu;     // pose now (Trk_Place): origin, Source's basis
float   trk_end;                            // Trk_Wrap stopped at a dead end
vector  trk_o, trk_a;
vector  trk_bf, trk_bl, trk_bu;

void() Trk_TableReset =
{
	if (trk_porg)
	{
		memfree(trk_porg);
		memfree(trk_pfl);
	}
	if (trk_pnext)
		memfree(trk_pnext);
	if (trk_pbuf > 0)
		buf_del(trk_pbuf);
	if (trk_ptab)
		hash_destroytab(trk_ptab);
	if (trk_p)
	{
		memfree(trk_p);
		memfree(trk_s);
		memfree(trk_r);
	}
	trk_porg = 0;
	trk_pfl = 0;
	trk_pnext = 0;
	trk_pbuf = 0;
	trk_ptab = 0;
	trk_p = 0;
	trk_s = 0;
	trk_r = 0;
	trk_pn = trk_pcap = trk_np = trk_cap = 0;
};

void(string nm, string tgt, vector o, float fl) Trk_TableAdd =
{
	local vector *no;
	local float *nf;
	local float i;

	if (trk_pn >= trk_pcap)
	{
		trk_pcap = max(64, trk_pcap * 2);
		no = memalloc(sizeof(vector) * trk_pcap);
		nf = memalloc(sizeof(float) * trk_pcap);
		for (i = 0; i < trk_pn; i = i + 1)
		{
			no[i] = trk_porg[i];
			nf[i] = trk_pfl[i];
		}
		if (trk_porg)
		{
			memfree(trk_porg);
			memfree(trk_pfl);
		}
		trk_porg = no;
		trk_pfl = nf;
	}
	if (trk_pbuf <= 0)
		trk_pbuf = buf_create();
	trk_porg[trk_pn] = o;
	trk_pfl[trk_pn] = fl;
	bufstr_set(trk_pbuf, trk_pn, strcat(nm, "\t", tgt));
	trk_pn = trk_pn + 1;
};

// Names to indices, once the table is complete.
void() Trk_TableLink =
{
	local float i, c;
	local string nm;

	if (trk_pnext)
		memfree(trk_pnext);
	if (trk_ptab)
		hash_destroytab(trk_ptab);
	trk_ptab = hash_createtab(trk_pn * 2 + 16, EV_FLOAT);
	trk_pnext = memalloc(sizeof(float) * max(1, trk_pn));
	for (i = 0; i < trk_pn; i = i + 1)
	{
		tokenizebyseparator(bufstr_get(trk_pbuf, i), "\t");
		nm = strtolower(argv(0));
		c = 0;
		if (nm != "")
			c = hash_get(trk_ptab, nm, 0);
		if (nm != "" && !c)
			hash_add(trk_ptab, nm, i + 1);
	}
	for (i = 0; i < trk_pn; i = i + 1)
	{
		tokenizebyseparator(bufstr_get(trk_pbuf, i), "\t");
		nm = strtolower(argv(1));
		c = 0;
		if (nm != "")
			c = hash_get(trk_ptab, nm, 0);
		trk_pnext[i] = c - 1;
	}
	buf_del(trk_pbuf);                      // the names live on in trk_ptab
	trk_pbuf = 0;
};

float(string nm) Trk_Find =
{
	local float c;

	if (!trk_ptab || nm == "")
		return -1;
	c = hash_get(trk_ptab, strtolower(nm), 0);
	return c - 1;
};

void(float n) Trk_PoolGrow =
{
	local vector *np;
	local float *ns;
	local float *nr;
	local float i;

	if (trk_np + n <= trk_cap)
		return;
	trk_cap = max(trk_np + n, trk_cap * 2);
	np = memalloc(sizeof(vector) * trk_cap);
	ns = memalloc(sizeof(float) * trk_cap);
	nr = memalloc(sizeof(float) * trk_cap);
	for (i = 0; i < trk_np; i = i + 1)
	{
		np[i] = trk_p[i];
		ns[i] = trk_s[i];
		nr[i] = trk_r[i];
	}
	if (trk_p)
	{
		memfree(trk_p);
		memfree(trk_s);
		memfree(trk_r);
	}
	trk_p = np;
	trk_s = ns;
	trk_r = nr;
};

// The train's path from the path_track `target` names: Find (trains.cpp:2517) to the first node, then
// each `target` until none, a disabled one (ValidPath) or one already passed (a loop). Arriving at a
// teleport node is a jump: that segment has no length. Sets trk_i0/n/k/len; returns the point count.
float(entity e, string target) Trk_Walk =
{
	local float i, j, c, last;
	local float *seen;              // one pointer per line: fteqcc reads `float *a, *b` as float **b
	local float *pos;

	e.trk_i0 = trk_np;
	e.trk_n = 0;
	e.trk_k = -1;
	e.trk_len = 0;
	i = Trk_Find(target);
	if (i < 0)
		return 0;
	seen = memalloc(sizeof(float) * trk_pn);
	pos = memalloc(sizeof(float) * trk_pn);
	for (j = 0; j < trk_pn; j = j + 1)
		seen[j] = 0;
	c = 0;
	while (i >= 0)
	{
		if (seen[i])
		{
			e.trk_k = pos[i];
			break;
		}
		seen[i] = 1;
		pos[i] = c;
		Trk_PoolGrow(1);
		trk_p[trk_np] = trk_porg[i];
		trk_r[trk_np] = i;
		trk_s[trk_np] = 0;
		if (c)
		{
			trk_s[trk_np] = trk_s[trk_np - 1];
			if (!(trk_pfl[i] & SF_PATH_TELEPORT))
				trk_s[trk_np] = trk_s[trk_np] + vlen(trk_porg[i] - trk_p[trk_np - 1]);
		}
		trk_np = trk_np + 1;
		c = c + 1;
		j = trk_pnext[i];
		if (j >= 0)
		if (trk_pfl[j] & SF_PATH_DISABLED)
			break;
		i = j;
	}
	memfree(seen);
	memfree(pos);
	e.trk_n = c;
	last = e.trk_i0 + c - 1;
	e.trk_len = trk_s[last];
	if (e.trk_k >= 0)
	if (!(trk_pfl[trk_r[e.trk_i0 + e.trk_k]] & SF_PATH_TELEPORT))
		e.trk_len = e.trk_len + vlen(trk_p[e.trk_i0 + e.trk_k] - trk_p[last]);
	return c;
};

// Arc length kept on the path: a loop wraps (backwards too when the train starts on it); anything
// else stops at its end and sets trk_end.
float(entity e, float s) Trk_Wrap =
{
	local float a, l;

	trk_end = FALSE;
	if (e.trk_k >= 0)
	{
		a = trk_s[e.trk_i0 + e.trk_k];
		l = e.trk_len - a;
		if (l > 0)
		if (s >= e.trk_len || (s < a && !e.trk_k))
			s = s - l * floor((s - a) / l);
	}
	if (s < 0)
	{
		s = 0;
		trk_end = TRUE;
	}
	else if (s > e.trk_len)
	{
		s = e.trk_len;
		trk_end = TRUE;
	}
	return s;
};

float(entity e, float t) Trk_S =
{
	return Trk_Wrap(e, e.trk_s0 + e.trk_dir * e.trk_spd * (t - e.trk_t0));
};

vector(entity e, float s) Trk_Point =
{
	local float i0, last, lo, hi, mid, seg;

	i0 = e.trk_i0;
	last = i0 + e.trk_n - 1;
	if (s >= trk_s[last])
	{
		seg = e.trk_len - trk_s[last];          // a loop's closing segment
		if (e.trk_k < 0 || seg <= 0)
			return trk_p[last];
		return trk_p[last] + (trk_p[i0 + e.trk_k] - trk_p[last]) * ((s - trk_s[last]) / seg);
	}
	lo = i0;
	hi = last;
	while (hi - lo > 1)                     // s[lo] <= s < s[hi]
	{
		mid = floor((lo + hi) / 2);
		if (trk_s[mid] <= s)
			lo = mid;
		else
			hi = mid;
	}
	seg = trk_s[hi] - trk_s[lo];
	if (seg <= 0)
		return trk_p[hi];
	return trk_p[lo] + (trk_p[hi] - trk_p[lo]) * ((s - trk_s[lo]) / seg);
};

// Pose at time t into trk_o / trk_a. Facing as UpdateOrientationAtPathTracks: toward the point
// `wheels` along the path (back along it when reversing, still facing path-forward).
void(entity e, float t) Trk_Pose =
{
	local float s, l, xy;
	local vector o, d;

	s = Trk_S(e, t);
	o = Trk_Point(e, s);
	trk_o = o + '0 0 1' * e.trk_height;
	trk_a = e.trk_alast;
	if (e.trk_sflags & SF_TRACKTRAIN_FIXEDORIENT)
		return;
	if (!e.trk_orient && e.trk_faced)
		return;                             // orientationtype 0: faced once, by Find
	l = (e.trk_wheels > 0) ? e.trk_wheels : 100;
	if (e.trk_dir < 0)
		d = o - Trk_Point(e, Trk_Wrap(e, s - l));
	else
		d = Trk_Point(e, Trk_Wrap(e, s + l)) - o;
	xy = sqrt(d_x * d_x + d_y * d_y);
	if (xy < 0.001)
		return;                             // straight up or nowhere to go: keep the last facing
	trk_a_x = (e.trk_sflags & SF_TRACKTRAIN_NOPITCH) ? 0 : atan2(0 - d_z, xy) * (180 / M_PI);
	trk_a_y = atan2(d_y, d_x) * (180 / M_PI);
	trk_a_z = 0;
	e.trk_alast = trk_a;
	e.trk_faced = TRUE;
};

// Find's facing (trains.cpp:2536): at the first path_track, `wheels` forward whatever the speed's sign.
// orientationtype 0 keeps it; call once at setup on both sides, so every client agrees (review 1).
void(entity e) Trk_FaceStart =
{
	local float l, xy;
	local vector o, d;

	if (e.trk_sflags & SF_TRACKTRAIN_FIXEDORIENT)
		return;
	l = (e.trk_wheels > 0) ? e.trk_wheels : 100;
	o = Trk_Point(e, 0);
	d = Trk_Point(e, Trk_Wrap(e, l)) - o;
	xy = sqrt(d_x * d_x + d_y * d_y);
	if (xy < 0.001)
		return;
	e.trk_alast_x = (e.trk_sflags & SF_TRACKTRAIN_NOPITCH) ? 0 : atan2(0 - d_z, xy) * (180 / M_PI);
	e.trk_alast_y = atan2(d_y, d_x) * (180 / M_PI);
	e.trk_alast_z = 0;
	e.trk_faced = TRUE;
};

// Source's AngleMatrix columns (forward, left, up) and MatrixAngles, as sv_entities.qc SV_SpBasis/SV_SpAngles.
void(vector a) Trk_Basis =
{
	makevectors(a);
	trk_bf = v_forward;
	trk_bl = '0 0 0' - v_right;
	trk_bu = v_up;
};

vector(vector f, vector l, vector u) Trk_Angles =
{
	local float xy;
	local vector a;

	xy = sqrt(f_x * f_x + f_y * f_y);
	a_x = atan2(0 - f_z, xy);
	if (xy > 0.001)
	{
		a_y = atan2(f_y, f_x);
		a_z = atan2(l_z, u_z);
	}
	else
		a_y = atan2(0 - l_x, l_y);
	return a * (180 / M_PI);
};

void(entity e, float t) Trk_Place =
{
	Trk_Pose(e, t);
	Trk_Basis(trk_a);
	e.trk_wo = trk_o;
	e.trk_wf = trk_bf;
	e.trk_wl = trk_bl;
	e.trk_wu = trk_bu;
};

// A rider's pose (lo, la in its train's spawn frame) on the train as placed: into trk_o / trk_a.
void(entity p, vector lo, vector la) Trk_Ride =
{
	local vector cf, cl, cu;

	Trk_Basis(la);
	cf = trk_bf;
	cl = trk_bl;
	cu = trk_bu;
	trk_o = p.trk_wo + p.trk_wf * lo_x + p.trk_wl * lo_y + p.trk_wu * lo_z;
	trk_bf = p.trk_wf * cf_x + p.trk_wl * cf_y + p.trk_wu * cf_z;
	trk_bl = p.trk_wf * cl_x + p.trk_wl * cl_y + p.trk_wu * cl_z;
	trk_bu = p.trk_wf * cu_x + p.trk_wl * cu_y + p.trk_wu * cu_z;
	trk_a = Trk_Angles(trk_bf, trk_bl, trk_bu);
};
