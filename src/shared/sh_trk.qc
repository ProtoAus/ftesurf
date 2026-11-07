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
#define SF_TRACKTRAIN_NOCONTROL     2           // P1388: No User Control (path_track speeds apply)
#define TRK_E                       2.718281828

// path_track table, per map: sv fills it from path_track's spawn, cl from the entity lump.
float     trk_pn, trk_pcap;
vector   *trk_porg;
float    *trk_pfl;
float    *trk_pspd;             // P1388: its speed key, 0 none
float    *trk_pnext;            // next node, -1 none (Trk_TableLink)
float    *trk_plk;              // P1390: where its OnPass teleports a train, -1 none (Trk_TableLink)
strbuf    trk_plkt;             // ...which train: its lowercased name, or !activator
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
// P1388: path_track speeds (ArriveAtNode / UpdateTrainVelocity). trk_vmode 0 one speed, 1 each node's on
// arrival (No User Control), 2 linear blend between nodes, 3 ease in/out (four linear pieces). Trk_S steps
// a checkpoint -- piece trk_vs..trk_ve from time trk_vt at speeds trk_va..trk_vb, segment trk_vj, piece
// trk_vm (-1 at a dead end) -- for the clock in trk_vk*; a loop is timed over one steady lap (trk_vper).
.float  trk_vmode;
.float  trk_vk0, trk_vk1, trk_vk2, trk_vk3;
.float  trk_vj, trk_vm, trk_vt, trk_vs, trk_ve, trk_va, trk_vb, trk_vsa, trk_vsb;
.float  trk_vlap, trk_vpt, trk_vper;
float   trk_vnow;                           // Trk_S's speed then
.vector trk_wo, trk_wf, trk_wl, trk_wu;     // pose now (Trk_Place): origin, Source's basis
.vector trk_wa;                             // ...and its angles
.float  trk_placet;                         // the time trk_w* are for
float   trk_end;                            // Trk_Wrap stopped at a dead end
vector  trk_o, trk_a;
vector  trk_bf, trk_bl, trk_bu;

void() Trk_TableReset =
{
	if (trk_porg)
	{
		memfree(trk_porg);
		memfree(trk_pfl);
		memfree(trk_pspd);
	}
	if (trk_pnext)
		memfree(trk_pnext);
	if (trk_plk)
		memfree(trk_plk);
	if (trk_plkt > 0)
		buf_del(trk_plkt);
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
	trk_pspd = 0;
	trk_pnext = 0;
	trk_plk = 0;
	trk_plkt = 0;
	trk_pbuf = 0;
	trk_ptab = 0;
	trk_p = 0;
	trk_s = 0;
	trk_r = 0;
	trk_pn = trk_pcap = trk_np = trk_cap = 0;
};

// P1390: one OnPass output's value -> "train\tnode" when it is TeleportToPathTrack with no delay, every pass
// (surf_colony's sky trains loop so); "" otherwise. Shared so both progs read a lump the same way.
string(string v) Trk_PassLink =
{
	local float n;
	local string sep;

	sep = ",";
	if (strstrofs(v, chr2str(27), 0) >= 0)
		sep = chr2str(27);
	n = tokenizebyseparator(v, sep);
	if (n < 3 || strtolower(argv(1)) != "teleporttopathtrack" || argv(2) == "")
		return "";
	if (n > 3 && stof(argv(3)) > 0.1)
		return "";
	if (n > 4 && stof(argv(4)) > 0)
		return "";
	return strcat(strtolower(argv(0)), "\t", argv(2));
};

void(string nm, string tgt, vector o, float fl, float spd, string lk) Trk_TableAdd =
{
	local vector *no;
	local float *nf;
	local float *nv;
	local float i;

	if (trk_pn >= trk_pcap)
	{
		trk_pcap = max(64, trk_pcap * 2);
		no = memalloc(sizeof(vector) * trk_pcap);
		nf = memalloc(sizeof(float) * trk_pcap);
		nv = memalloc(sizeof(float) * trk_pcap);
		for (i = 0; i < trk_pn; i = i + 1)
		{
			no[i] = trk_porg[i];
			nf[i] = trk_pfl[i];
			nv[i] = trk_pspd[i];
		}
		if (trk_porg)
		{
			memfree(trk_porg);
			memfree(trk_pfl);
			memfree(trk_pspd);
		}
		trk_porg = no;
		trk_pfl = nf;
		trk_pspd = nv;
	}
	if (trk_pbuf <= 0)
		trk_pbuf = buf_create();
	trk_porg[trk_pn] = o;
	trk_pfl[trk_pn] = fl;
	spd = fabs(spd);
	if (!(spd <= 100000))
		spd = (spd > 100000) ? 100000 : 0;  // review 2: an "inf" key looped Trk_Ln; NaN reads as none
	trk_pspd[trk_pn] = spd;
	bufstr_set(trk_pbuf, trk_pn, strcat(nm, "\t", tgt, "\t", lk));
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
	if (trk_plk)
		memfree(trk_plk);
	if (trk_plkt > 0)
		buf_del(trk_plkt);
	trk_plk = memalloc(sizeof(float) * max(1, trk_pn));
	trk_plkt = buf_create();
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
		bufstr_set(trk_plkt, i, argv(2));   // already lowercased by Trk_PassLink
		nm = strtolower(argv(3));
		c = 0;
		if (argv(2) != "" && nm != "")
			c = hash_get(trk_ptab, nm, 0);
		trk_plk[i] = c - 1;
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
// teleport node is a jump: that segment has no length. P1390: so is a node's OnPass TeleportToPathTrack
// on this train (named nm), which wins over its target. Sets trk_i0/n/k/len; returns the point count.
.float  trk_kjump;                          // P1390: the loop closes by such a jump
float(entity e, string target, string nm) Trk_Walk =
{
	local float i, j, c, last, jump;
	local string lt;
	local float *seen;              // one pointer per line: fteqcc reads `float *a, *b` as float **b
	local float *pos;

	e.trk_i0 = trk_np;
	e.trk_n = 0;
	e.trk_k = -1;
	e.trk_len = 0;
	e.trk_vk1 = -1;                 // P1388: a new pool range: Trk_S starts again
	i = Trk_Find(target);
	if (i < 0)
		return 0;
	seen = memalloc(sizeof(float) * trk_pn);
	pos = memalloc(sizeof(float) * trk_pn);
	for (j = 0; j < trk_pn; j = j + 1)
		seen[j] = 0;
	c = 0;
	jump = FALSE;
	nm = strtolower(nm);
	e.trk_kjump = FALSE;
	while (i >= 0)
	{
		if (seen[i])
		{
			e.trk_k = pos[i];
			e.trk_kjump = jump;
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
			if (!jump && !(trk_pfl[i] & SF_PATH_TELEPORT))
				trk_s[trk_np] = trk_s[trk_np] + vlen(trk_porg[i] - trk_p[trk_np - 1]);
		}
		trk_np = trk_np + 1;
		c = c + 1;
		j = trk_pnext[i];
		jump = FALSE;
		if (trk_plk[i] >= 0)
		{
			lt = bufstr_get(trk_plkt, i);
			if ((nm != "" && lt == nm) || lt == "!activator")
			{
				j = trk_plk[i];
				jump = TRUE;
			}
		}
		if (j >= 0 && !jump)
		if (trk_pfl[j] & SF_PATH_DISABLED)
			break;
		i = j;
	}
	memfree(seen);
	memfree(pos);
	e.trk_n = c;
	last = e.trk_i0 + c - 1;
	e.trk_len = trk_s[last];
	if (e.trk_k >= 0 && !e.trk_kjump)
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

// P1388: the speed of segment j (point j to the next) for carried speed c, into trk_sa..trk_sb: a node's
// own speed from arrival (mode 1, ArriveAtNode), or blended toward the next node's (UpdateTrainVelocity).
float trk_sa, trk_sb;
void(entity e, float j, float c) Trk_VSeg =
{
	local float jn, nv;

	nv = trk_pspd[trk_r[e.trk_i0 + j]];
	trk_sa = nv ? nv : c;
	trk_sb = trk_sa;
	jn = (j < e.trk_n - 1) ? j + 1 : e.trk_k;
	if (e.trk_vmode >= 2 && jn >= 0)
	{
		nv = trk_pspd[trk_r[e.trk_i0 + jn]];
		if (nv)
			trk_sb = nv;
	}
};

// Piece m of K of segment j; ease in/out is SimpleSplineRemapVal's 3p^2 - 2p^3, linear within a piece.
void(entity e, float j, float m, float K) Trk_VPiece =
{
	local float a, l, p0, p1;

	a = trk_s[e.trk_i0 + j];
	l = ((j < e.trk_n - 1) ? trk_s[e.trk_i0 + j + 1] : e.trk_len) - a;
	p0 = m / K;
	p1 = (m + 1) / K;
	e.trk_vs = a + l * p0;
	e.trk_ve = a + l * p1;
	if (K > 1)
	{
		p0 = p0 * p0 * (3 - 2 * p0);
		p1 = p1 * p1 * (3 - 2 * p1);
	}
	e.trk_va = e.trk_vsa + (e.trk_vsb - e.trk_vsa) * p0;
	e.trk_vb = e.trk_vsa + (e.trk_vsb - e.trk_vsa) * p1;
};

// Natural log, x > 0: into [1, 2) by halving, then 2 atanh((x-1)/(x+1)). Not the `log` builtin: #532 is
// MVDSV's precache_vwep_model on the server ("bad string"), and both progs must agree to the bit.
float(float x) Trk_Ln =
{
	local float e, z, z2, t, s, k;

	if (x <= 0)
		return 0;
	e = 0;
	while (x >= 2 && e < 256)
	{
		x = x * 0.5;
		e = e + 1;
	}
	while (x < 1 && e > -256)
	{
		x = x * 2;
		e = e - 1;
	}
	z = (x - 1) / (x + 1);
	z2 = z * z;
	t = z;
	s = 0;
	for (k = 1; k < 24; k = k + 2)
	{
		s = s + t / k;
		t = t * z2;
	}
	return 2 * s + e * 0.6931471806;
};

// Time to cover l with speed linear in distance from a to b (both > 0), and the distance covered in dt.
float(float l, float a, float b) Trk_VTime =
{
	if (l <= 0)
		return 0;
	if (fabs(b - a) < 0.001 * a)
		return 2 * l / (a + b);
	return l * Trk_Ln(b / a) / (b - a);
};

float(float l, float a, float b, float dt) Trk_VDist =
{
	local float k, d;

	if (fabs(b - a) < 0.001 * a)
	{
		trk_vnow = a;
		return min(l, 0.5 * (a + b) * dt);
	}
	k = (b - a) / l;
	d = bound(0, (a / k) * (pow(TRK_E, k * dt) - 1), l);
	trk_vnow = a + k * d;
	return d;
};

// The checkpoint at the clock: the segment holding s0, as one piece from s0 to its end.
void(entity e) Trk_VReset =
{
	local float s, i0, last, lo, hi, mid, j, l, p;

	e.trk_vk0 = e.trk_s0;
	e.trk_vk1 = e.trk_t0;
	e.trk_vk2 = e.trk_spd;
	e.trk_vk3 = e.trk_dir;
	e.trk_vlap = e.trk_vper = 0;
	e.trk_vt = e.trk_t0;
	s = Trk_Wrap(e, e.trk_s0);
	i0 = e.trk_i0;
	last = i0 + e.trk_n - 1;
	if (s >= trk_s[last])
		j = e.trk_n - 1;
	else
	{
		lo = i0;
		hi = last;
		while (hi - lo > 1)
		{
			mid = floor((lo + hi) / 2);
			if (trk_s[mid] <= s)
				lo = mid;
			else
				hi = mid;
		}
		j = lo - i0;
	}
	e.trk_vj = j;
	if (j == e.trk_n - 1 && e.trk_k < 0)
	{
		e.trk_vm = -1;                      // already at its dead end
		e.trk_vb = e.trk_spd;
		return;
	}
	if (e.trk_vmode == 1)
		e.trk_vsa = e.trk_vsb = e.trk_spd;  // what the clock says, until the next node
	else
		Trk_VSeg(e, j, e.trk_spd);
	if (e.trk_vmode >= 2)
	{
		e.trk_vsa = trk_sa;
		e.trk_vsb = trk_sb;
	}
	Trk_VPiece(e, j, 0, 1);
	l = e.trk_ve - e.trk_vs;
	p = (l > 0) ? (s - e.trk_vs) / l : 1;
	e.trk_va = e.trk_vsa + (e.trk_vsb - e.trk_vsa) * p;
	e.trk_vs = s;
	e.trk_vm = (e.trk_vmode == 3) ? 3 : 0;  // the last piece: the next step arrives at a node
};

float(entity e, float t) Trk_SProfile =
{
	local float n, K, l, dt, steps, jn;

	n = e.trk_n;
	K = (e.trk_vmode == 3) ? 4 : 1;
	if (e.trk_vk0 != e.trk_s0 || e.trk_vk1 != e.trk_t0 || e.trk_vk2 != e.trk_spd || e.trk_vk3 != e.trk_dir
	    || t < e.trk_vt)
		Trk_VReset(e);
	// A lead-in, three laps to time one, and the last part-lap: K steps a segment (review 2: 4n cut the
	// server's rare fresh evaluations short, 477 units on bhop_furret, thousands on 20-node loops).
	for (steps = 0; steps < K * (6 * n + 16); steps = steps + 1)
	{
		if (e.trk_vm < 0)
		{
			trk_end = TRUE;
			trk_vnow = e.trk_vb;
			return e.trk_len;
		}
		l = e.trk_ve - e.trk_vs;
		dt = Trk_VTime(l, e.trk_va, e.trk_vb);
		if (t < e.trk_vt + dt)
		{
			trk_end = FALSE;
			return e.trk_vs + max(0, Trk_VDist(l, e.trk_va, e.trk_vb, t - e.trk_vt));
		}
		e.trk_vt = e.trk_vt + dt;
		if (e.trk_vm < K - 1)
		{
			e.trk_vm = e.trk_vm + 1;
			Trk_VPiece(e, e.trk_vj, e.trk_vm, K);
			continue;
		}
		if (e.trk_vj == n - 1)
		{
			// Round to the loop's first node. The third arrival ends a lap that began at the steady speed.
			e.trk_vlap = e.trk_vlap + 1;
			if (e.trk_vper > 0)
			{
				// On the lap grid, so a client summing every segment and a server skipping laps agree
				// after hours (review 1); whole laps skipped, never backwards -- a lap's float32 sum can
				// fall short of the period, putting the grid point just past t (review 2: the train
				// then waits on the node for those milliseconds, the clamp below).
				e.trk_vt = e.trk_vpt + e.trk_vper * floor((e.trk_vt - e.trk_vpt) / e.trk_vper + 0.5);
				e.trk_vt = e.trk_vt + e.trk_vper * max(0, floor((t - e.trk_vt) / e.trk_vper));
			}
			else if (e.trk_vlap == 2)
				e.trk_vpt = e.trk_vt;
			else if (e.trk_vlap == 3)
			{
				e.trk_vper = e.trk_vt - e.trk_vpt;
				if (e.trk_vper <= 0)
				{
					e.trk_vm = -1;          // a loop that takes no time: held, as at a dead end (review 2)
					continue;
				}
				e.trk_vt = e.trk_vt + e.trk_vper * max(0, floor((t - e.trk_vt) / e.trk_vper));
			}
			jn = e.trk_k;
		}
		else
			jn = e.trk_vj + 1;
		e.trk_vj = jn;
		if (jn == n - 1 && e.trk_k < 0)
		{
			e.trk_vm = -1;                  // DeadEnd: stopped at the last node
			continue;
		}
		Trk_VSeg(e, jn, e.trk_vb);
		e.trk_vsa = trk_sa;
		e.trk_vsb = trk_sb;
		e.trk_vm = 0;
		Trk_VPiece(e, jn, 0, K);
	}
	trk_end = FALSE;                        // more steps than one call takes: on from here next time
	trk_vnow = e.trk_va;
	return Trk_Wrap(e, e.trk_vs + e.trk_va * (t - e.trk_vt));
};

float(entity e, float t) Trk_S =
{
	if (e.trk_vmode && e.trk_dir > 0 && e.trk_spd > 0)
		return Trk_SProfile(e, t);
	trk_vnow = e.trk_spd;                   // P1388: one speed backwards (not modelled), stopped, or none set
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
	e.trk_faced = TRUE;
	if (xy < 0.001)
	{
		// Straight up or down: VectorAngles' pitch 270 / 90 with yaw 0 (review 3), or 0 0 0 with NOPITCH.
		e.trk_alast = '0 0 0';
		if (!(e.trk_sflags & SF_TRACKTRAIN_NOPITCH))
			e.trk_alast_x = (d_z > 0) ? 270 : 90;
		return;
	}
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

// Once per train per time: its riders all ask (P1385: 105 riders recomputed 35 poses ~140 times a frame).
void(entity e, float t) Trk_Place =
{
	if (e.trk_placet == t && t > 0)
		return;
	e.trk_placet = t;
	Trk_Pose(e, t);
	Trk_Basis(trk_a);
	e.trk_wo = trk_o;
	e.trk_wa = trk_a;
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
