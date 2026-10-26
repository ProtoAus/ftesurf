/*
===========================================================================
  cl_savesync.qc -- Patch 811: a lobby's saves in this install, and this
  install's saves in the lobby.  The server half is sv_savesync.qc.

  In a lobby the server keeps this player's saves on ITS disk (data/saves/<map>/
  @<guid>); a local game reads data/saves/<map> on THIS one.  A few seconds into
  each lobby map the two lists are made one, by key (SS_Same), against the ledger
  of the keys both held after the last time:

      on both sides                    kept
      lobby only, not in the ledger    copied here
      lobby only, in the ledger        deleted here since: deleted there
      here only, not in the ledger     sent up (`savesync add`)
      here only, in the ledger         deleted there since: moved to deleted/

  A delete is carried only for a key one side has lost entirely, one row of it,
  from a listing that came back whole; more than 5 and over half of either list
  at once reads as a lost folder and is copied back instead.  After that, every
  save the lobby makes is copied here as it lands and a delete there moves this
  install's copy once no lobby row of that key is left.  The ledger is
  <the lobby root>/sync.txt, beside the lobby rows' pictures; none (the first visit)
  is a union.

  A copy here is a placement -- idle timer, no run, the velocity kept -- because
  the lobby's run and recording stay the lobby's; a row sent up is the same shape
  on the server.  Pictures (trail.txt) are copied both ways with their header
  made a placement's (ticks -1, Trail_Load's test) and only when they end at the
  row.  Nothing in this install is destroyed: a delete moves the files to
  deleted/.  A delete carried to the lobby is `sl_del`'s, files and all.  Where
  one side holds several rows at a key, only the first is paired; a delete moves
  one row here (a copy before an original), never every row at the key.
===========================================================================
*/
#define SS_ROWS    400          // a list longer than this on either side is not synced:
                                // the plan's pairwise work must stay far under QC's runaway budget
#define SS_LMAX    2000         // lobby rows held, gone ones included
#define SS_CMAX    4000         // rows here, copies made and moved ones included
#define SS_QMAX    4000
#define SS_ASK     3            // seconds into the map before the listing is asked for
#define SS_WAIT    4            // seconds an answer may take
#define SS_GAP     0.12         // seconds between two commands: under the server's 10 a second
#define SS_PICS    8
#define SS_PICNEAR 64           // a picture's last sample this close to its row's origin
#define SSQ_DOWN   1            // a lobby row copied here
#define SSQ_UP     2            // a row here sent up
#define SSQ_DEL    3            // a lobby row deleted (deleted here since)
#define SSQ_TRASH  4            // a row here moved to deleted/ (deleted there)

float  ss_state;                // 0 asking soon, 1 listing, 2 planning, 3 the queue, 4 live, -1 off
float  ss_at, ss_tries, ss_req, ss_page, ss_lcnt, ss_ldel;
float  ss_tag, ss_tagn;         // the queued command in flight; 0 none
string ss_map, ss_root;         // zoned: this map; the lobby root (STAT_FS_SAVEROOT) as listed
float  ss_alloc, ss_trashn;
vector *ss_lo; vector *ss_lv; float *ss_lp; float *ss_ly; float *ss_lid; float *ss_lf; float *ss_lm;
float  ss_ln;                   // lobby rows; ss_lid 0 = gone
vector *ss_co; vector *ss_cv; float *ss_cp; float *ss_cy; float *ss_cid; float *ss_cd; float *ss_cm;
float *ss_cmir;                 // a copy this sync wrote (`synced 1`)
float  ss_bad, ss_sawdelall;    // a state file here would not read; a delete-all was seen
float  ss_planwhole;            // the last plan could carry deletes
float  ss_cn, ss_cseq;          // rows here; ss_cid 0 = gone
vector *ss_mo; float *ss_mp; float *ss_my;
float  ss_mn;                   // the ledger
float *ss_qop; float *ss_qi;
float  ss_qn, ss_qh;
float  ss_ndown, ss_nup, ss_ndel, ss_ntrash, ss_nfail;
float  ss_pic_from[SS_PICS], ss_pic_to[SS_PICS], ss_pic_at[SS_PICS], ss_pic_n[SS_PICS];
vector ss_pic_o[SS_PICS];

float(string fname) fremove;
float(string src, string dst) frename = #0:frename;
float() WarpOp_Charge;          // cl_warpop.qc: SV_SaveLocRate's charge, mirrored

void() SaveSync_Register =
{
	registercommand("savesync");
	registercvar("cl_savesync", "1", CVAR_ARCHIVE);
};

void() SaveSync_Alloc =
{
	if (ss_alloc)
		return;
	ss_alloc = TRUE;
	ss_lo = memalloc(sizeof(vector) * SS_LMAX);
	ss_lv = memalloc(sizeof(vector) * SS_LMAX);
	ss_lp = memalloc(sizeof(float) * SS_LMAX);
	ss_ly = memalloc(sizeof(float) * SS_LMAX);
	ss_lid = memalloc(sizeof(float) * SS_LMAX);
	ss_lf = memalloc(sizeof(float) * SS_LMAX);
	ss_lm = memalloc(sizeof(float) * SS_LMAX);
	ss_co = memalloc(sizeof(vector) * SS_CMAX);
	ss_cv = memalloc(sizeof(vector) * SS_CMAX);
	ss_cp = memalloc(sizeof(float) * SS_CMAX);
	ss_cy = memalloc(sizeof(float) * SS_CMAX);
	ss_cid = memalloc(sizeof(float) * SS_CMAX);
	ss_cd = memalloc(sizeof(float) * SS_CMAX);
	ss_cm = memalloc(sizeof(float) * SS_CMAX);
	ss_cmir = memalloc(sizeof(float) * SS_CMAX);
	ss_mo = memalloc(sizeof(vector) * SS_CMAX);
	ss_mp = memalloc(sizeof(float) * SS_CMAX);
	ss_my = memalloc(sizeof(float) * SS_CMAX);
	ss_qop = memalloc(sizeof(float) * SS_QMAX);
	ss_qi = memalloc(sizeof(float) * SS_QMAX);
};

string(float id) SaveSync_Here = { return sprintf("data/saves/%s/save%s/", ss_map, FS_SaveSlotName(id)); };
string(float id) SaveSync_There = { return sprintf("%s/save%s/", ss_root, FS_SaveSlotName(id)); };

float(vector o, float p, float y) SaveSync_InLedger =
{
	local float i;
	local vector mo;

	for (i = 0; i < ss_mn; i = i + 1)
	{
		mo = ss_mo[i];
		if (SS_Same(mo, ss_mp[i], ss_my[i], o, p, y))
			return TRUE;
	}
	return FALSE;
};

void(vector o, float p, float y) SaveSync_LedgerAdd =
{
	if (ss_mn >= SS_CMAX || SaveSync_InLedger(o, p, y))
		return;
	ss_mo[ss_mn] = o;
	ss_mp[ss_mn] = p;
	ss_my[ss_mn] = y;
	ss_mn = ss_mn + 1;
};

void(vector o, float p, float y) SaveSync_LedgerDrop =
{
	local float i;
	local vector mo;

	for (i = 0; i < ss_mn; i = i + 1)
	{
		mo = ss_mo[i];
		if (SS_Same(mo, ss_mp[i], ss_my[i], o, p, y))
		{
			ss_mn = ss_mn - 1;
			ss_mo[i] = ss_mo[ss_mn];
			ss_mp[i] = ss_mp[ss_mn];
			ss_my[i] = ss_my[ss_mn];
			return;
		}
	}
};

void() SaveSync_LedgerRead =
{
	local float fh, n;
	local string l;

	ss_mn = 0;
	fh = fopen(strcat(ss_root, "/sync.txt"), FILE_READ);
	if (fh < 0)
		return;
	while ((l = fgets(fh)) != "")
	{
		n = tokenize(l);
		if (n >= 6 && argv(0) == "k")
			SaveSync_LedgerAdd([stof(argv(1)), stof(argv(2)), stof(argv(3))], stof(argv(4)), stof(argv(5)));
	}
	fclose(fh);
};

void() SaveSync_LedgerWrite =
{
	local float fh, i;
	local vector o;

	fh = fopen(strcat(ss_root, "/sync.txt"), FILE_WRITE);
	if (fh < 0)
		return;
	fputs(fh, sprintf("FTESURF-SYNC 1\nmap %s\n", ss_map));
	for (i = 0; i < ss_mn; i = i + 1)
	{
		o = ss_mo[i];
		fputs(fh, sprintf("k %.4f %.4f %.4f %.4f %.4f\n", o_x, o_y, o_z, ss_mp[i], ss_my[i]));
	}
	fclose(fh);
};

float(vector o, float p, float y) SaveSync_LobbyCount =
{
	local float i, n;
	local vector lo;

	n = 0;
	for (i = 0; i < ss_ln; i = i + 1)
	{
		lo = ss_lo[i];
		if (ss_lid[i])
		if (SS_Same(lo, ss_lp[i], ss_ly[i], o, p, y))
			n = n + 1;
	}
	return n;
};

float(vector o, float p, float y) SaveSync_HereCount =
{
	local float i, n;
	local vector co;

	n = 0;
	for (i = 0; i < ss_cn; i = i + 1)
	{
		co = ss_co[i];
		if (ss_cid[i])
		if (SS_Same(co, ss_cp[i], ss_cy[i], o, p, y))
			n = n + 1;
	}
	return n;
};

// The first live row here at that key; unmatched only, when `free`.
float(vector o, float p, float y, float free) SaveSync_FindHere =
{
	local float i;
	local vector co;

	for (i = 0; i < ss_cn; i = i + 1)
	{
		co = ss_co[i];
		if (ss_cid[i])
		if (!free || !ss_cm[i])
		if (SS_Same(co, ss_cp[i], ss_cy[i], o, p, y))
			return i;
	}
	return -1;
};

void(vector o, vector v, float p, float y, float fl, float id) SaveSync_LobbyAdd =
{
	local float i;

	for (i = 0; i < ss_ln; i = i + 1)
		if (ss_lid[i] == id)
			return;                 // a page asked twice
	if (ss_ln >= SS_LMAX)
		return;
	ss_lo[ss_ln] = o;
	ss_lv[ss_ln] = v;
	ss_lp[ss_ln] = p;
	ss_ly[ss_ln] = y;
	ss_lf[ss_ln] = fl;
	ss_lid[ss_ln] = id;
	ss_lm[ss_ln] = FALSE;
	ss_ln = ss_ln + 1;
};

void(float id) SaveSync_LobbyDrop =
{
	local float i;

	for (i = 0; i < ss_ln; i = i + 1)
		if (ss_lid[i] == id)
			ss_lid[i] = 0;
};

/*
  A picture copied whole, its header made a placement's: the copy loads with
  SAVETICKS -1, and Trail_Load takes only a picture saved at the ticks loaded.
  Refused unless its last sample is at the row (`o`): a folder number the lobby
  reused may still hold another save's picture on this disk.
*/
float(string src, string dst, vector o) SaveSync_CopyPic =
{
	local float b, fh, n, i, ok;
	local string s;

	b = buf_create_ex("string", 0);
	if (b < 1)
		return FALSE;
	ok = FALSE;
	if (buf_loadfile(src, b))
	{
		n = buf_getsize(b);
		while (n > 1 && bufstr_get(b, n - 1) == "")
			n = n - 1;
		tokenize(bufstr_get(b, 0));
		if (argv(0) == "FTESURF-TRAIL" && n > 1)
		{
			s = argv(2);
			tokenize(bufstr_get(b, n - 1));
			if (vlen([stof(argv(1)), stof(argv(2)), stof(argv(3))] - o) <= SS_PICNEAR)
			{
				fh = fopen(dst, FILE_WRITE);
				if (fh >= 0)
				{
					fputs(fh, sprintf("FTESURF-TRAIL 1 %s -1 0\n", s));
					for (i = 1; i < n; i = i + 1)
						fputs(fh, strcat(bufstr_get(b, i), "\n"));
					fclose(fh);
					ok = TRUE;
				}
			}
		}
	}
	buf_del(b);
	return ok;
};

// The lobby row's picture is written when this client handles the save's answer,
// which can trail the push: try again.  to > 0 here, < 0 there.
void(float from, float to, vector o) SaveSync_PicLater =
{
	local float i;

	for (i = 0; i < SS_PICS; i = i + 1)
		if (!ss_pic_at[i])
		{
			ss_pic_from[i] = from;
			ss_pic_to[i] = to;
			ss_pic_at[i] = cltime + 1;
			ss_pic_n[i] = 0;
			ss_pic_o[i] = o;
			return;
		}
};

void() SaveSync_PicFrame =
{
	local float i, ok;
	local vector o;

	for (i = 0; i < SS_PICS; i = i + 1)
	{
		if (!ss_pic_at[i] || cltime < ss_pic_at[i])
			continue;
		o = ss_pic_o[i];
		if (ss_pic_to[i] > 0)
			ok = SaveSync_CopyPic(strcat(SaveSync_There(ss_pic_from[i]), "trail.txt"),
			                      strcat(SaveSync_Here(ss_pic_to[i]), "trail.txt"), o);
		else
			ok = SaveSync_CopyPic(strcat(SaveSync_Here(ss_pic_from[i]), "trail.txt"),
			                      strcat(SaveSync_There(-ss_pic_to[i]), "trail.txt"), o);
		ss_pic_n[i] = ss_pic_n[i] + 1;
		ss_pic_at[i] = (ok || ss_pic_n[i] >= 3) ? 0 : cltime + 2;
	}
};

// This install's list, as the local game's scan reads it (SV_SaveLocScanBlk).
float(string fn, float id) SaveSync_ReadHere =
{
	local float fh, n, seq, rwd, have, mir, tas;
	local string k, l;
	local vector o, v, rv;
	local float p, y, d;

	fh = fopen(fn, FILE_READ);
	if (fh < 0)
	{
		frename(fn, fn);            // Patch 751's adopt: the listing read the disk
		fh = fopen(fn, FILE_READ);
	}
	if (fh < 0)
		return FALSE;
	seq = -1;
	rwd = have = mir = tas = FALSE;
	o = v = rv = '0 0 0';
	p = y = d = 0;
	while ((l = fgets(fh)) != "")
	{
		n = tokenize(l);
		if (n < 2)
			continue;
		k = argv(0);
		if (k == "seq")      seq = stof(argv(1));
		if (k == "duck")     d = stof(argv(1));
		if (k == "rewound")  rwd = stof(argv(1));
		if (k == "synced")   mir = TRUE;
		if (k == "flags")
		if (stof(argv(1)) & TF_TAS) tas = TRUE;
		if (k == "origin" && n >= 4)   { o = [stof(argv(1)), stof(argv(2)), stof(argv(3))]; have = TRUE; }
		if (k == "velocity" && n >= 4) v = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
		if (k == "rwvel" && n >= 4)    rv = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
		if (k == "angles" && n >= 3)   { p = stof(argv(1)); y = stof(argv(2)); }
	}
	fclose(fh);
	// P1052: preserve the file locally; ListHere's protected-row path also
	// blocks deletion. Do not upload TAS through the old position-only format.
	if (tas) return FALSE;
	if (seq < 0 || !have || ss_cn >= SS_CMAX)
		return FALSE;
	ss_co[ss_cn] = o;
	ss_cv[ss_cn] = rwd ? rv : v;
	ss_cp[ss_cn] = p;
	ss_cy[ss_cn] = y;
	ss_cd[ss_cn] = d;
	ss_cid[ss_cn] = id;
	ss_cm[ss_cn] = FALSE;
	ss_cmir[ss_cn] = mir;
	ss_cn = ss_cn + 1;
	if (seq > ss_cseq)
		ss_cseq = seq;
	return TRUE;
};

void() SaveSync_ListHere =
{
	local float h, i, cnt, pl, id;
	local string pre, fn;

	ss_cn = ss_cseq = ss_bad = 0;
	pre = strtolower(sprintf("data/saves/%s/save", ss_map));
	pl = strlen(pre);
	h = search_begin(sprintf("data/saves/%s/*/state.txt", ss_map), FS_NAMESORT, TRUE);
	if (h < 0)
		return;
	cnt = search_getsize(h);
	for (i = 0; i < cnt; i = i + 1)
	{
		fn = strtolower(search_getfilename(h, i));
		if (strcmp(substring(fn, 0, pl), pre))
			continue;
		id = stof(substring(fn, pl, FS_SAVENAMELEN));
		if (id < 1 || id > FS_MAXSAVES)
			continue;
		if (!SaveSync_ReadHere(search_getfilename(h, i), id))
		if (ss_cn < SS_CMAX)
		{
			// Not read, not absent: its folder stays taken and nothing is deleted
			// on either side this visit.
			ss_bad = ss_bad + 1;
			ss_cid[ss_cn] = id;
			ss_co[ss_cn] = '0 0 -999999';
			ss_cm[ss_cn] = TRUE;
			ss_cmir[ss_cn] = FALSE;
			ss_cn = ss_cn + 1;
		}
	}
	search_end(h);
};

float(float id) SaveSync_Used =
{
	local float i;

	for (i = 0; i < ss_cn; i = i + 1)
		if (ss_cid[i] == id)
			return TRUE;
	return FALSE;
};

// Not one still holding a recording or a sidecar: a move that took the state only.
float() SaveSync_FreeHere =
{
	local float id, fh, fv;

	for (id = 1; id <= FS_MAXSAVES; id = id + 1)
		if (!SaveSync_Used(id))
		{
			fh = fopen(strcat(SaveSync_Here(id), "run.rec"), FILE_READ);
			fv = fopen(strcat(SaveSync_Here(id), "run.view"), FILE_READ);
			if (fh >= 0)
				fclose(fh);
			if (fv >= 0)
				fclose(fv);
			if (fh < 0 && fv < 0)
				return id;
		}
	return 0;
};

// A lobby row copied into this install: the placement shape the server's
// SV_SaveWriteAt writes for a row with no ring sample.
float(vector o, vector v, float p, float y, float d, float lid, float later) SaveSync_WriteHere =
{
	local float id, fh;
	local string dir;

	if (ss_cn >= SS_CMAX)
		return FALSE;
	id = SaveSync_FreeHere();
	if (id < 1)
		return FALSE;
	dir = SaveSync_Here(id);
	// An emptied folder's leftovers would pair with this state (SV_SaveLocDeleteRow).
	fremove(strcat(dir, "seq.txt"));
	fremove(strcat(dir, "run.view"));
	fremove(strcat(dir, "run.rec"));
	fremove(strcat(dir, "trail.txt"));
	fh = fopen(strcat(dir, "state.txt"), FILE_WRITE);
	if (fh < 0)
		return FALSE;
	ss_cseq = ss_cseq + 1;
	fputs(fh, sprintf("FTESURF-SAVE 1\nmap %s\nseq %d\ncreated %s\n", ss_map, ss_cseq,
	                  strftime(TRUE, "%Y%m%d-%H%M%S")));
	fputs(fh, sprintf("origin %.4f %.4f %.4f\nvelocity 0 0 0\nrwvel %.4f %.4f %.4f\n",
	                  o_x, o_y, o_z, v_x, v_y, v_z));
	fputs(fh, sprintf("angles %.4f %.4f\nduck %d\ndemoted 1\nrewound 1\nsynced 1\n", p, y, d ? 1 : 0));
	fclose(fh);
	ss_co[ss_cn] = o;
	ss_cv[ss_cn] = v;
	ss_cp[ss_cn] = p;
	ss_cy[ss_cn] = y;
	ss_cd[ss_cn] = d;
	ss_cid[ss_cn] = id;
	ss_cm[ss_cn] = TRUE;
	ss_cmir[ss_cn] = TRUE;
	ss_cn = ss_cn + 1;
	if (later || !SaveSync_CopyPic(strcat(SaveSync_There(lid), "trail.txt"), strcat(dir, "trail.txt"), o))
		SaveSync_PicLater(lid, id, o);
	return TRUE;
};

// A row here the lobby deleted: moved, never removed.  FALSE (the row stays) when
// its state file would not move.
float(float c) SaveSync_Trash =
{
	local string src, dst;
	local float fh;

	src = SaveSync_Here(ss_cid[c]);
	do
	{
		ss_trashn = ss_trashn + 1;
		dst = sprintf("data/saves/%s/deleted/save%s-%s-%g/", ss_map, FS_SaveSlotName(ss_cid[c]),
		              strftime(TRUE, "%Y%m%d%H%M%S"), ss_trashn);
		fh = fopen(strcat(dst, "state.txt"), FILE_READ);
		if (fh >= 0)
			fclose(fh);
	} while (fh >= 0);
	if (frename(strcat(src, "state.txt"), strcat(dst, "state.txt")) != 0)   // first: the scan keys on it
		return FALSE;
	frename(strcat(src, "run.rec"), strcat(dst, "run.rec"));
	frename(strcat(src, "run.view"), strcat(dst, "run.view"));
	frename(strcat(src, "seq.txt"), strcat(dst, "seq.txt"));
	frename(strcat(src, "trail.txt"), strcat(dst, "trail.txt"));
	ss_cid[c] = 0;
	return TRUE;
};

// The row here paired with a lobby key that has gone: one, a copy before an
// original.  The key leaves the ledger, so any other row here at it is sent up
// next visit rather than read as deleted there.
void(vector o, float p, float y) SaveSync_TrashKey =
{
	local float c, pick;
	local vector co;

	pick = -1;
	for (c = 0; c < ss_cn; c = c + 1)
	{
		co = ss_co[c];
		if (ss_cid[c])
		if (SS_Same(co, ss_cp[c], ss_cy[c], o, p, y))
		if (pick < 0 || (ss_cmir[c] && !ss_cmir[pick]))
			pick = c;
	}
	if (pick >= 0)
	{
		if (SaveSync_Trash(pick))
			ss_ntrash = ss_ntrash + 1;
		else
			ss_nfail = ss_nfail + 1;
	}
	SaveSync_LedgerDrop(o, p, y);
};

void(float op, float i) SaveSync_Queue =
{
	if (ss_qn >= SS_QMAX)
		return;
	ss_qop[ss_qn] = op;
	ss_qi[ss_qn] = i;
	ss_qn = ss_qn + 1;
};

void() SaveSync_Ask =
{
	ss_tries = ss_tries + 1;
	ss_req = ss_req + 1;
	ss_ln = ss_ldel = ss_lcnt = 0;
	ss_tag = ss_qn = ss_qh = 0;
	ss_state = 1;
	ss_page = 1;
	ss_at = cltime + SS_WAIT;
	localcmd(sprintf("cmd savesync list 1 %d\n", ss_req));
};

// The listing is in: decide every row, the lobby's and this install's.
void() SaveSync_Plan =
{
	local float i, c, n, whole, nl, nc, ndel, ntr;
	local vector o;

	if (ss_root != "")
		strunzone(ss_root);
	ss_root = strzone(getstats(STAT_FS_SAVEROOT));
	if (strstrofs(ss_root, sprintf("data/saves/%s/@", ss_map), 0) != 0)
	{
		ss_state = -1;              // not a lobby block this client can name
		return;
	}
	SaveSync_ListHere();
	SaveSync_LedgerRead();
	c = fopen(strcat(ss_root, "/delall.txt"), FILE_READ);
	if (c >= 0)
	{
		fclose(c);
		ss_sawdelall = TRUE;
	}
	nl = nc = 0;
	for (i = 0; i < ss_ln; i = i + 1)
		if (ss_lid[i])
			nl = nl + 1;
	nc = ss_cn;
	if (nl > SS_ROWS || nc > SS_ROWS)
	{
		print(sprintf("^3saves:^7 %s has more than %g saves (lobby %g, here %g) -- not kept the same\n",
		              ss_map, SS_ROWS, nl, nc));
		ss_state = -1;
		return;
	}
	// Whole: every row the server counted came, and nothing was deleted meanwhile
	// (a delete shifts the rows under a page).  Otherwise no delete either way.
	whole = (nl == ss_lcnt && !ss_ldel && !ss_bad);
	ss_planwhole = whole;
	for (i = 0; i < ss_ln; i = i + 1)
	{
		o = ss_lo[i];
		ss_lm[i] = FALSE;
		if (!ss_lid[i])
			continue;
		c = SaveSync_FindHere(o, ss_lp[i], ss_ly[i], TRUE);
		if (c >= 0)
		{
			ss_cm[c] = TRUE;
			ss_lm[i] = TRUE;
		}
	}
	ss_qn = ss_qh = ndel = ntr = 0;
	for (i = 0; i < ss_ln; i = i + 1)
	{
		o = ss_lo[i];
		if (!ss_lid[i] || ss_lm[i])
			continue;
		if (SaveSync_HereCount(o, ss_lp[i], ss_ly[i]))
			continue;               // a second lobby row of a key this install has
		if (!SaveSync_InLedger(o, ss_lp[i], ss_ly[i]))
			SaveSync_Queue(SSQ_DOWN, i);
		else if (whole && SaveSync_LobbyCount(o, ss_lp[i], ss_ly[i]) == 1)
		{
			SaveSync_Queue(SSQ_DEL, i);
			ndel = ndel + 1;
		}
	}
	for (c = 0; c < ss_cn; c = c + 1)
	{
		o = ss_co[c];
		if (ss_cm[c] || SaveSync_LobbyCount(o, ss_cp[c], ss_cy[c]))
			continue;
		if (!SaveSync_InLedger(o, ss_cp[c], ss_cy[c]))
			SaveSync_Queue(SSQ_UP, c);
		else if (whole && SaveSync_FindHere(o, ss_cp[c], ss_cy[c], FALSE) == c)
		{
			SaveSync_Queue(SSQ_TRASH, c);       // once a key: SaveSync_TrashKey picks the row
			ntr = ntr + 1;
		}
	}
	// Most of a list gone from one side at once is a folder lost, not a decision.
	if (ndel > 5 && ndel * 2 > nl)
	{
		print(sprintf("^3saves:^7 %g lobby saves on %s are missing here -- copying them back rather than deleting them\n",
		              ndel, ss_map));
		for (i = 0; i < ss_qn; i = i + 1)
			if (ss_qop[i] == SSQ_DEL)
				ss_qop[i] = SSQ_DOWN;
	}
	if (ntr > 5 && ntr * 2 > nc && !ss_sawdelall)
	{
		print(sprintf("^3saves:^7 %g saves here are missing from the lobby on %s -- sending them back rather than moving them\n",
		              ntr, ss_map));
		for (i = 0; i < ss_qn; i = i + 1)
			if (ss_qop[i] == SSQ_TRASH)
				ss_qop[i] = SSQ_UP;
	}
	// The new ledger: the old keys either side still has (a delete still owed, or
	// one this listing could not decide), and every key both sides hold now.
	n = ss_mn;
	for (i = n - 1; i >= 0; i = i - 1)
	{
		o = ss_mo[i];
		if (!SaveSync_LobbyCount(o, ss_mp[i], ss_my[i]))
		if (!SaveSync_HereCount(o, ss_mp[i], ss_my[i]))
			SaveSync_LedgerDrop(o, ss_mp[i], ss_my[i]);
	}
	for (i = 0; i < ss_ln; i = i + 1)
	{
		o = ss_lo[i];
		if (ss_lm[i])
			SaveSync_LedgerAdd(o, ss_lp[i], ss_ly[i]);
	}
	ss_ndown = ss_nup = ss_ndel = ss_ntrash = ss_nfail = 0;
	ss_state = 3;
	ss_at = cltime;
};

void() SaveSync_Done =
{
	SaveSync_LedgerWrite();
	if (ss_sawdelall && ss_planwhole)
	{
		fremove(strcat(ss_root, "/delall.txt"));    // the delete-all is carried out now
		ss_sawdelall = FALSE;
	}
	ss_state = 4;
	if (ss_ndown || ss_nup || ss_ndel || ss_ntrash || ss_nfail)
		print(sprintf("^7saves: %s -- %g copied here, %g sent to the lobby, %g deleted there, %g moved to deleted/%s\n",
		              ss_map, ss_ndown, ss_nup, ss_ndel, ss_ntrash,
		              ss_nfail ? sprintf(", %g not done (next visit)", ss_nfail) : ""));
};

void() SaveSync_Step =
{
	local float op, i;
	local vector o, v;

	if (ss_tag)
	{
		if (cltime < ss_at)
			return;
		ss_tag = 0;                 // no answer: next visit
		ss_nfail = ss_nfail + 1;
		ss_qh = ss_qh + 1;
	}
	if (cltime < ss_at)
		return;
	if (ss_qh >= ss_qn)
	{
		SaveSync_Done();
		return;
	}
	op = ss_qop[ss_qh];
	i = ss_qi[ss_qh];
	if (op == SSQ_DOWN || op == SSQ_DEL)
		o = ss_lo[i];
	else
		o = ss_co[i];
	// Each step is checked again: a push, a delete or a delete-all may have
	// landed since the plan.
	if (op == SSQ_DOWN)
	{
		v = ss_lv[i];
		if (ss_lid[i])
		if (!SaveSync_HereCount(o, ss_lp[i], ss_ly[i]))
		{
			if (SaveSync_WriteHere(o, v, ss_lp[i], ss_ly[i], ss_lf[i] & SSF_DUCK, ss_lid[i], FALSE))
			{
				SaveSync_LedgerAdd(o, ss_lp[i], ss_ly[i]);
				ss_ndown = ss_ndown + 1;
			}
			else
				ss_nfail = ss_nfail + 1;
		}
		ss_qh = ss_qh + 1;
		ss_at = cltime + SS_GAP;
		return;
	}
	if (op == SSQ_TRASH)
	{
		if (ss_cid[i])
		if (SaveSync_InLedger(o, ss_cp[i], ss_cy[i]))     // a delete-all may have moved it since
		if (!SaveSync_LobbyCount(o, ss_cp[i], ss_cy[i]))
			SaveSync_TrashKey(o, ss_cp[i], ss_cy[i]);
		ss_qh = ss_qh + 1;
		ss_at = cltime + SS_GAP;
		return;
	}
	if (op == SSQ_UP)
	if (!ss_cid[i] || SaveSync_LobbyCount(o, ss_cp[i], ss_cy[i]))
	{
		ss_qh = ss_qh + 1;
		return;
	}
	if (op == SSQ_DEL)
	if (!ss_lid[i] || SaveSync_HereCount(o, ss_lp[i], ss_ly[i]))
	{
		ss_qh = ss_qh + 1;
		return;
	}
	ss_tagn = ss_tagn + 1;
	ss_tag = ss_tagn;
	ss_at = cltime + SS_WAIT;
	WarpOp_Charge();                // the server charges it as an sl_ command
	if (op == SSQ_UP)
	{
		v = ss_cv[i];
		localcmd(strcat(sprintf("cmd savesync add %d %.4f %.4f %.4f ", ss_tag, o_x, o_y, o_z),
		                sprintf("%.4f %.4f %.4f %.4f %.4f %d\n", v_x, v_y, v_z, ss_cp[i], ss_cy[i],
		                        ss_cd[i] ? 1 : 0)));
	}
	else
		localcmd(strcat(sprintf("cmd savesync del %d %d %.4f %.4f %.4f ", ss_tag, ss_lid[i], o_x, o_y, o_z),
		                sprintf("%.4f %.4f\n", ss_lp[i], ss_ly[i])));
};

void() SaveSync_Frame =
{
	local string map;

	if (ss_state < 0)
		return;
	map = serverkey("map");
	if (map == "")
		return;
	if (ss_map == "")
	{
		ss_map = strzone(map);
		ss_at = cltime + SS_ASK;
	}
	SaveSync_PicFrame();
	if (ss_state == 0)
	{
		if (cltime < ss_at || !cvar("cl_savesync") || !LT_StatsAreMine())
			return;
		SaveSync_Alloc();
		SaveSync_Ask();
	}
	else if (ss_state == 1)
	{
		if (cltime < ss_at)
			return;
		if (ss_lcnt < 0)
		{
			// a page asked for after the gap (SaveSync_Event)
			ss_lcnt = 0;
			ss_at = cltime + SS_WAIT;
			localcmd(sprintf("cmd savesync list %d %d\n", ss_page, ss_req));
			return;
		}
		if (ss_tries < 3)
			SaveSync_Ask();
		else
			ss_state = -1;          // an older lobby, or one that never answers
	}
	else if (ss_state == 2)
	{
		if (cltime >= ss_at)
			SaveSync_Plan();        // after the last page
	}
	else if (ss_state == 3)
		SaveSync_Step();
};

// A row the lobby made just now.
void(vector o, vector v, float p, float y, float fl, float id) SaveSync_Pushed =
{
	SaveSync_LobbyAdd(o, v, p, y, fl, id);
	if (ss_state < 3)
		return;                     // the listing decides it
	if (!SaveSync_HereCount(o, p, y))
	{
		if (!SaveSync_WriteHere(o, v, p, y, fl & SSF_DUCK, id, TRUE))
		{
			ss_nfail = ss_nfail + 1;
			return;                 // not in the ledger, or the next visit deletes it there
		}
		ss_ndown = ss_ndown + 1;
	}
	SaveSync_LedgerAdd(o, p, y);
	if (ss_state == 4)
		SaveSync_LedgerWrite();
};

void(float id, vector o, float p, float y) SaveSync_Gone =
{
	SaveSync_LobbyDrop(id);
	if (ss_state == 1 || ss_state == 2)
	{
		ss_ldel = TRUE;
		return;
	}
	if (ss_state < 3 || SaveSync_LobbyCount(o, p, y))
		return;
	SaveSync_TrashKey(o, p, y);
	if (ss_state == 4)
		SaveSync_LedgerWrite();
};

// CSQC_Parse_Event, for SS_EV_*.
void(float t) SaveSync_Event =
{
	local float tag, id, fl, next, cnt, st, c, req, kind;
	local vector o, v, co;
	local float p, y;

	if (t == SS_EV_ROW)
	{
		tag = readlong();
		id = readshort();
		readlong();                 // seq: the lobby's order, not this list's
		o_x = readfloat(); o_y = readfloat(); o_z = readfloat();
		v_x = readfloat(); v_y = readfloat(); v_z = readfloat();
		p = readfloat();
		y = readfloat();
		fl = readbyte();
		if (!ss_alloc)
			return;
		if (tag && tag == ss_tag)
		{
			// The answer to an `add`: id 0 refused (a full list, a bad number).
			ss_tag = 0;
			ss_qh = ss_qh + 1;
			ss_at = cltime + SS_GAP;
			if (!id)
			{
				ss_nfail = ss_nfail + 1;
				return;
			}
			ss_nup = ss_nup + 1;
			SaveSync_LobbyAdd(o, v, p, y, fl, id);
			SaveSync_LedgerAdd(o, p, y);
			if (!(fl & SSF_NEW))
				return;             // a row the lobby had: its files here are its own
			// A new placement: no sidecar or column of an older save at this folder
			// number on this disk may stand for it.
			fremove(strcat(SaveSync_There(id), "run.view"));
			fremove(strcat(SaveSync_There(id), "seq.txt"));
			fremove(strcat(SaveSync_There(id), "trail.txt"));
			c = SaveSync_FindHere(o, p, y, FALSE);
			if (c >= 0)
			if (!SaveSync_CopyPic(strcat(SaveSync_Here(ss_cid[c]), "trail.txt"), strcat(SaveSync_There(id), "trail.txt"), o))
				SaveSync_PicLater(ss_cid[c], -id, o);
			return;
		}
		if (!tag && id)
			SaveSync_Pushed(o, v, p, y, fl, id);
		return;
	}
	if (t == SS_EV_END)
	{
		next = readshort();
		cnt = readshort();
		st = readbyte();
		req = readlong();
		kind = readbyte();
		if (!ss_alloc)
			return;
		if (kind == 1)              // an add's or a del's
		{
			if (ss_state != 3 || !ss_tag || req != ss_tag)
				return;
			if (st == 2)
			{
				ss_tag = 0;         // the save rate: the same step again, a second on
				ss_at = cltime + 1;
				return;
			}
			ss_tag = 0;             // the lobby turned saves off, or a delete-all is sweeping
			for (c = ss_qh; c < ss_qn; c = c + 1)
				if (ss_qop[c] == SSQ_TRASH)
					ss_planwhole = FALSE;   // a move it left undone is the next visit's
			ss_nfail = ss_nfail + ss_qn - ss_qh;
			ss_qh = ss_qn;
			return;
		}
		if (ss_state != 1 || req != ss_req)
			return;                 // an earlier listing's
		if (st == 1)
		{
			ss_state = -1;
			return;
		}
		if (next > 0)
		{
			ss_page = next;
			ss_lcnt = -1;           // SaveSync_Frame asks for it after the gap
			ss_at = cltime + SS_GAP;
			return;
		}
		ss_lcnt = cnt;
		ss_state = 2;
		ss_at = cltime + 0.25;
		return;
	}
	if (t == SS_EV_DEL)
	{
		tag = readlong();
		id = readshort();
		o_x = readfloat(); o_y = readfloat(); o_z = readfloat();
		p = readfloat();
		y = readfloat();
		if (!ss_alloc)
			return;
		if (tag && tag == ss_tag)
		{
			ss_tag = 0;
			ss_qh = ss_qh + 1;
			ss_at = cltime + SS_GAP;
			if (id)
			{
				ss_ndel = ss_ndel + 1;
				SaveSync_LobbyDrop(id);
				if (!SaveSync_LobbyCount(o, p, y) && !SaveSync_HereCount(o, p, y))
					SaveSync_LedgerDrop(o, p, y);
			}
			return;
		}
		if (!tag && id)
			SaveSync_Gone(id, o, p, y);
		return;
	}
	if (t == SS_EV_DELALL)
	{
		// Not carried out here yet (before the plan): the next plan -- this map's or a
		// later visit's, through the marker beside the ledger -- may move more than the
		// lost-folder guard allows, which is what the player asked for.  Live, it is
		// carried out below and leaves no marker.
		if (ss_state < 3)
		if (strstrofs(getstats(STAT_FS_SAVEROOT), sprintf("data/saves/%s/@", serverkey("map")), 0) == 0)
		{
			ss_sawdelall = TRUE;
			c = fopen(strcat(getstats(STAT_FS_SAVEROOT), "/delall.txt"), FILE_WRITE);
			if (c >= 0)
			{
				fputs(c, "delall\n");
				fclose(c);
			}
		}
		if (!ss_alloc)
			return;
		for (c = 0; c < ss_ln; c = c + 1)
			ss_lid[c] = 0;
		if (ss_state == 1 || ss_state == 2)
		{
			ss_ldel = TRUE;
			return;
		}
		if (ss_state < 3)
			return;
		fremove(strcat(ss_root, "/delall.txt"));
		ss_sawdelall = FALSE;
		for (c = ss_mn - 1; c >= 0; c = c - 1)
		{
			co = ss_mo[c];
			SaveSync_TrashKey(co, ss_mp[c], ss_my[c]);
		}
		ss_mn = 0;
		if (ss_state == 4)
			SaveSync_LedgerWrite();
	}
};

float(string cmd) SaveSync_ConsoleCommand =
{
	if (argv(0) != "savesync")
		return FALSE;
	if (argv(1) == "now")
	{
		if (ss_map != "" && cvar("cl_savesync"))
		{
			SaveSync_Alloc();
			ss_tries = 0;
			SaveSync_Ask();
		}
		return TRUE;
	}
	print(sprintf("savesync: state %g map %s root %s\n", ss_state, ss_map, ss_root));
	print(sprintf("savesync: lobby %g here %g ledger %g  queue %g/%g\n", ss_ln, ss_cn, ss_mn, ss_qh, ss_qn));
	print(sprintf("savesync: copied here %g sent up %g deleted there %g moved %g not done %g\n",
	              ss_ndown, ss_nup, ss_ndel, ss_ntrash, ss_nfail));
	return TRUE;
};
