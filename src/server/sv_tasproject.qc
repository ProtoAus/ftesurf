// P1082: TAS projects. A project = one ordinary TAS save (its base) + every input after it.
// Loading re-simulates from that save; checkpoint states say whether it reproduced. The engine
// keeps the connection's sub-tick ms carry into a replay, which QC cannot set (BACKLOG).
#define TASP_VERSION 2          // P1090: 2 adds `supply`; 1 still loads
#define TASP_LEGAL 3            // P1100: a legal start (`start`, `startat`) in place of a base save
#define TASP_MAX 96000          // ticks after the base, about 24 minutes at 15 ms
#define TASP_CPMAX 48           // checkpoints kept: auto, the head, named
#define TASP_CPEVERY 256        // auto spacing, doubled until about 32 fit
#define TASP_CPSTRIDE 8         // tick, named, origin xyz, velocity xyz
#define TASP_FILES 64           // projects per map

float *tasp_buf[FS_MAXPLAYERS + 1];      // inputs for ticks base+1.., TAS_INPUT_STRIDE each
float *tasp_cp[FS_MAXPLAYERS + 1];
string tasp_name[FS_MAXPLAYERS + 1], tasp_hash[FS_MAXPLAYERS + 1];
string tasp_parent[FS_MAXPLAYERS + 1], tasp_cpnames[FS_MAXPLAYERS + 1];
string tasp_revsha[FS_MAXPLAYERS + 1];   // P1089: this lineage's last saved/loaded revision hash
string tasp_parsha[FS_MAXPLAYERS + 1];   // P1090: that revision's parentsha, "" for a root
float *tasp_pbuf[FS_MAXPLAYERS + 1];     // P1090: that revision's own rows (tasp_pbase, tasp_pn)
.float tasp_on, tasp_n, tasp_cap, tasp_base, tasp_baseid, tasp_rev, tasp_serial, tasp_synced;
.float tasp_lasthead, tasp_filehead, tasp_ncp, tasp_load, tasp_stop, tasp_chead, tasp_cbase;
.float tasp_ccount, tasp_cpi, tasp_dev, tasp_devtick, tasp_result, tasp_next;
.vector tasp_bo, tasp_bv;      // the base tick's exact origin and velocity (state.txt rounds)
.float tasp_line;              // recorder line after tick tasp_synced's `in` row, -1 unknown
.float tasp_linemt;            // that row's move counter, -1 when the next row starts a branch
.float tasp_cut;               // lowest tick a TAS go replaced since the last save/load
.float tasp_gen;               // rec_rec_gen as this project last saw it
.float tasp_parentrev;         // the parent project's revision when this one forked
// P1090: the ticks the current revision supplies over its parent (0 none, -1 a version 1 file).
// The next save's supply is an exact diff against tasp_pbuf, whatever the working buffer went
// through; tasp_lineserial is the attempt that revision belongs to.
.float tasp_supa, tasp_supb, tasp_signed, tasp_pbase, tasp_pn, tasp_lineserial;
.float tasp_made;              // P1090 review 3: the current revision was saved here, not only loaded
.float tasp_legal, tasp_lzone, tasp_lstartat;  // P1100: this revision is a legal start (version 3)
.float tasp_lhead;              // its file's head, in ticks from the placement
.vector tasp_lo;                // its placement
float(entity e) SV_TASLegalValid;
void(entity e, string name, float force) SV_TASProjectSaveLegal;
void(entity e, string name, string cpname) SV_TASLegalLoad;

// One file read into temporaries; a load installs them only after every check passed.
float *tpr_buf;
float *tpr_cp;
float tpr_n, tpr_size, tpr_base, tpr_baseid, tpr_rev, tpr_ncp, tpr_parentrev;
vector tpr_bo, tpr_bv;
string tpr_revsha;              // P1089: the hash the file states for itself, "" if none
string tpr_parsha;              // P1090: its parentsha, "" for a root
float tpr_supa, tpr_supb;       // P1090: its supply line (tasp_supa's values)
float tpr_ver, tpr_zone, tpr_startat;   // P1100: version; a v3 file's start zone and start tick
string tpr_hash, tpr_parent, tpr_cpnames, tpr_why;
float tasp_hflags;
string tasp_why;

float(entity e) SV_TASPSlot =
{
	local float s;
	s = num_for_edict(e);
	if (s < 1 || s > FS_MAXPLAYERS) return 0;
	return s;
};

float(string n) SV_TASPNameOK =
{
	local float i, c;
	if (strlen(n) < 1 || strlen(n) > 32) return FALSE;
	for (i = 0; i < strlen(n); i = i + 1)
	{
		c = str2chr(n, i);
		if (!((c >= 97 && c <= 122) || (c >= 48 && c <= 57) || c == 95 || c == 45)) return FALSE;
	}
	return TRUE;
};

string(string n) SV_TASPPath = { return sprintf("data/tasproj/%s/%s.tasp", mapname, n); };

float(string n) SV_TASPExists =
{
	local filestream f;
	f = fopen(SV_TASPPath(n), FILE_READ);
	if (f < 0) return FALSE;
	fclose(f);
	return TRUE;
};

float() SV_TASPCount =
{
	local searchhandle h;
	local float n;
	h = search_begin(sprintf("data/tasproj/%s/*.tasp", mapname), 0, TRUE);
	if (h < 0) return 0;
	n = search_getsize(h);
	search_end(h);
	return n;
};

void(entity e) SV_TASProjectReset =
{
	local float s;
	s = SV_TASPSlot(e);
	e.tasp_on = e.tasp_load = e.tasp_n = e.tasp_cap = e.tasp_ncp = e.tasp_ccount = 0;
	e.tasp_result = e.tasp_dev = e.tasp_devtick = 0;
	e.tasp_line = e.tasp_linemt = -1;
	e.tasp_cut = 16000001; e.tasp_gen = e.tasp_parentrev = 0;
	e.tasp_supa = e.tasp_supb = e.tasp_signed = e.tasp_pn = e.tasp_lineserial = e.tasp_made = 0;
	if (!s) return;
	if (tasp_buf[s]) memfree(tasp_buf[s]);
	if (tasp_cp[s]) memfree(tasp_cp[s]);
	if (tasp_pbuf[s]) memfree(tasp_pbuf[s]);
	tasp_buf[s] = 0; tasp_cp[s] = 0; tasp_pbuf[s] = 0;
	if (tasp_name[s]) strunzone(tasp_name[s]);
	if (tasp_hash[s]) strunzone(tasp_hash[s]);
	if (tasp_parent[s]) strunzone(tasp_parent[s]);
	if (tasp_cpnames[s]) strunzone(tasp_cpnames[s]);
	if (tasp_revsha[s]) strunzone(tasp_revsha[s]);
	if (tasp_parsha[s]) strunzone(tasp_parsha[s]);
	tasp_name[s] = tasp_hash[s] = tasp_parent[s] = tasp_cpnames[s] = tasp_revsha[s] = tasp_parsha[s] = "";
};

void() SV_TASPReadFree =
{
	if (tpr_buf) memfree(tpr_buf);
	if (tpr_cp) memfree(tpr_cp);
	tpr_buf = 0; tpr_cp = 0;
	tpr_n = tpr_ncp = tpr_size = 0;
	if (tpr_hash) strunzone(tpr_hash);
	if (tpr_parent) strunzone(tpr_parent);
	if (tpr_cpnames) strunzone(tpr_cpnames);
	if (tpr_revsha) strunzone(tpr_revsha);
	if (tpr_parsha) strunzone(tpr_parsha);
	tpr_hash = tpr_parent = tpr_cpnames = tpr_revsha = tpr_parsha = "";
	tpr_supa = tpr_supb = 0;
};

// sha256 over state.txt's exact lines; also reads its `flags`.
string(float id) SV_TASPStateHash =
{
	local filestream f;
	local string l, all;
	tasp_hflags = 0;
	f = fopen(SL_StatePath(id), FILE_READ);
	if (f < 0) return "";
	all = "";
	while ((l = fgets(f)) != "")
	{
		all = strcat(all, l, "\n");
		if (substring(l, 0, 6) == "flags ") tasp_hflags = stof(substring(l, 6, -1));
	}
	fclose(f);
	if (all == "") return "";
	return strtolower(digest_hex("SHA256", all));
};

// The list position of save folder `id` in this player's block, 0 if absent.
float(entity e, float id) SV_TASPRow =
{
	local float blk, base, n;
	blk = SL_Blk(e); base = SL_Base(blk);
	for (n = 1; n <= rec_sl_nb[blk]; n = n + 1)
		if (rec_sl_id[base + n - 1] == id) return n;
	return 0;
};

// Name list "a;b;" -> the k-th entry, "" past the end.
string(string list, float k) SV_TASPNameAt =
{
	local float i, at, semi;
	at = 0;
	for (i = 0; i < k; i = i + 1)
	{
		semi = strstrofs(list, ";", at);
		if (semi < 0) return "";
		at = semi + 1;
	}
	semi = strstrofs(list, ";", at);
	if (semi < 0) return "";
	return substring(list, at, semi - at);
};

float(string list, string name) SV_TASPNameIndex =
{
	local float k;
	local string n;
	for (k = 0; k < TASP_CPMAX; k = k + 1)
	{
		n = SV_TASPNameAt(list, k);
		if (n == "") return -1;
		if (n == name) return k;
	}
	return -1;
};

float(string tok, float lo, float hi, float whole) SV_TASPNum =
{
	if (!FS_TASNumber(tok)) return FALSE;
	if (!(fs_tas_number >= lo && fs_tas_number <= hi)) return FALSE;
	if (whole && floor(fs_tas_number) != fs_tas_number) return FALSE;
	return TRUE;
};

// The native row validator needs TAS mode on this body (SV_TASRewindClient).
float(entity e, float *buf, float n) SV_TASPValidate =
{
	local float i, b;
	for (i = 0; i < n; i = i + 1)
	{
		b = i * TAS_INPUT_STRIDE;
		if (!tas_tape(e, 1, 0, 0, [buf[b], buf[b+1], buf[b+2]], [buf[b+3], buf[b+4], buf[b+5]], buf[b+6]))
			return i + 1;
	}
	return 0;
};

/*
  P1089 review 1: a revision's hash is evidence, so a project file must be EXACTLY what
  SV_TASPWrite writes: the writer's key order (only cp and i repeat), printable ASCII under
  3000 bytes a line (fgets splits a 4095-byte line in two), single spaces, and every value in
  the writer's own text -- %.0f integers, %.9g float32 values, lowercase hex, fixed words. A
  file that differs in any byte the game would ignore is refused, so one behaviour has one
  hash, and tools/tasrev.py can check the same bytes. Returns the key's rank, or -1.
*/
string(string line) SV_TASPCanon =
{
	local string k;
	tokenize(line);
	k = argv(0);
	if (k == "saved" || k == "revision" || k == "origin" || k == "parent" || k == "revsha" || k == "")
		return "";
	if (k == "base")
		return sprintf("base %s %s", argv(2), argv(3));
	return line;
};

float tpr_rank;
#define TASP_RANKCP 16          // the two keys that repeat
#define TASP_RANKI 17
float(string k) SV_TASPKeyRank =
{
	if (k == "tasproject") return 0; if (k == "map") return 1; if (k == "mapcrc") return 2;
	if (k == "zonecrc") return 3; if (k == "pmpin") return 4; if (k == "assist") return 5;
	if (k == "origin") return 6; if (k == "saved") return 7; if (k == "revision") return 8;
	if (k == "parent") return 9; if (k == "parentsha") return 10; if (k == "supply") return 11;
	// P1100: `start` takes base's rank (a file has one or the other); `startat` sits before head.
	if (k == "base" || k == "start") return 12; if (k == "baseat") return 13; if (k == "startat") return 14;
	if (k == "head") return 15;
	if (k == "cp") return TASP_RANKCP; if (k == "i") return TASP_RANKI; if (k == "end") return 18;
	if (k == "revsha") return 19;
	return -1;
};

// "-0" is refused: the writer writes zero for negative zero (SV_TASPZ), so it has one form.
float(string t, float whole) SV_TASPCanonNum =
{
	return (t != "" && t != "-0" && t == sprintf(whole ? "%.0f" : "%.9g", stof(t)));
};

float(float x) SV_TASPZ = { if (x == 0) return 0; return x; };

// A float already in %.9g form (which may have an exponent FS_TASNumber cannot read).
float(string t, float lo, float hi) SV_TASPFloat =
{
	local float x;
	x = stof(t);
	if (!(x >= lo && x <= hi)) return FALSE;
	fs_tas_number = x;
	return TRUE;
};

float(string t, float len) SV_TASPHex =
{
	local float i, c;
	if (strlen(t) < 1 || (len && strlen(t) != len)) return FALSE;
	for (i = 0; i < strlen(t); i = i + 1)
	{
		c = str2chr(t, i);
		if (!((c >= 48 && c <= 57) || (c >= 97 && c <= 102))) return FALSE;
	}
	return TRUE;
};

// The line as the writer would have written it, or FALSE. argv holds its tokens.
float(string l, string k, float argc) SV_TASPLineCanon =
{
	local float i, c, p, r, whole;
	// The raw bytes: printable, single spaces, none of tokenize's punctuation ("'/()[]{},;\)
	// and ':' only in `saved` -- so splitting on spaces is all tokenize did to this line.
	if (strlen(l) >= 3000 || strlen(l) < 1) return FALSE;
	p = 32;
	for (i = 0; i < strlen(l); i = i + 1)
	{
		c = str2chr(l, i);
		if (c < 32 || c > 126 || c == 34 || c == 39 || c == 47 || c == 40 || c == 41 || c == 91 ||
			c == 93 || c == 123 || c == 125 || c == 44 || c == 59 || c == 92) return FALSE;
		if (c == 58 && k != "saved") return FALSE;
		if (c == 32 && p == 32) return FALSE;   // a leading or a double space
		p = c;
	}
	if (p == 32) return FALSE;
	r = SV_TASPKeyRank(k);
	if (r < 0 || r < tpr_rank || (r == tpr_rank && r != TASP_RANKCP && r != TASP_RANKI)) return FALSE;
	tpr_rank = r;
	if (k == "assist") return (l == "assist tas");
	if (k == "origin") return (l == "origin local");
	if (k == "mapcrc" || k == "zonecrc") return (argc == 2 && SV_TASPHex(argv(1), 8));
	if (k == "parentsha" || k == "revsha") return (argc == 2 && SV_TASPHex(argv(1), 64));
	if (k == "supply") return (l == "supply none" || (argc == 3 && SV_TASPCanonNum(argv(1), TRUE) && SV_TASPCanonNum(argv(2), TRUE)));
	if (k == "base") return (argc == 4 && SV_TASPCanonNum(argv(1), TRUE) && SV_TASPHex(argv(2), 64) && SV_TASPCanonNum(argv(3), TRUE));
	if (k == "start" || k == "startat") return (argc == 2 && SV_TASPCanonNum(argv(1), TRUE));
	if (k == "saved")               // tokenize splits at ':', so the raw text: "saved " + 19
	{
		if (strlen(l) != 25 || substring(l, 0, 6) != "saved ") return FALSE;
		for (i = 0; i < 19; i = i + 1)
		{
			c = str2chr(l, 6 + i);
			if (i == 4 || i == 7) { if (c != 45) return FALSE; }
			else if (i == 10) { if (c != 84) return FALSE; }
			else if (i == 13 || i == 16) { if (c != 58) return FALSE; }
			else if (c < 48 || c > 57) return FALSE;
		}
		return TRUE;
	}
	if (k == "parent") return (argc == 3 && SV_TASPNameOK(argv(1)) && SV_TASPCanonNum(argv(2), TRUE));
	if (k == "cp")
	{
		if (argc != 10 || !SV_TASPCanonNum(argv(1), TRUE) || (argv(2) != "0" && argv(2) != "1")) return FALSE;
		if (argv(2) == "0" && argv(3) != "-") return FALSE;
		for (i = 4; i < 10; i = i + 1) if (!SV_TASPCanonNum(argv(i), FALSE)) return FALSE;
		return TRUE;
	}
	if (k == "baseat")
	{
		for (i = 1; i < argc; i = i + 1) if (!SV_TASPCanonNum(argv(i), FALSE)) return FALSE;
		return (argc == 7);
	}
	whole = (k == "tasproject" || k == "revision" || k == "head" || k == "i" || k == "end");
	if (whole)
	{
		for (i = 1; i < argc; i = i + 1) if (!SV_TASPCanonNum(argv(i), TRUE)) return FALSE;
		return (argc >= 2);
	}
	return TRUE;                    // map, pmpin: compared with this server's below
};

// Parse a project into tpr_*. Untrusted: every value is bounded; FALSE leaves tpr_why.
// `identity` also requires and compares the map, zone and movement-rule lines.
// P1089: tpr_h is the revision hash over the canonical lines (SV_TASPCanon); tpr_pathover
// reads another path (the writer's .new file) in place of the project's.
string tpr_h, tpr_pathover;
float(entity e, string name, float identity) SV_TASPRead =
{
	local filestream f;
	local string l, k, pin, hash, parent, names, z;
	local float argc, n, i, b, have, ended, named, ver;

	SV_TASPReadFree();
	tpr_rev = tpr_base = tpr_baseid = tpr_parentrev = 0; tpr_why = "";
	f = fopen((tpr_pathover != "") ? tpr_pathover : SV_TASPPath(name), FILE_READ);
	if (f < 0) { tpr_why = "no such project on this map"; return FALSE; }
	tpr_cp = (float*)memalloc(TASP_CPMAX * TASP_CPSTRIDE * 4);
	if (!tpr_cp) { fclose(f); tpr_why = "out of memory"; return FALSE; }
	have = ended = n = ver = 0;
	tpr_zone = tpr_startat = tpr_ver = 0;
	hash = parent = names = "";
	pin = SV_RecPinText(e, "*pmpin");
	tpr_rank = -1;
	if (tpr_h) strunzone(tpr_h);
	tpr_h = strzone(strtolower(digest_hex("SHA256", "FTESURF-TASREV-CANON 1")));
	while ((l = fgets(f)) != "")
	{
		argc = tokenize(l);
		k = argv(0);
		if (argc < 1 || !SV_TASPLineCanon(l, k, argc)) { tpr_why = "not a file the game wrote (P1089 canonical form)"; break; }
		if (ended && k != "revsha") { tpr_why = "data after end"; break; }
		z = SV_TASPCanon(l);
		if (z != "")
		{
			z = strzone(strtolower(digest_hex("SHA256", strcat(tpr_h, "\n", z))));
			strunzone(tpr_h); tpr_h = z;
		}
		argc = tokenize(l);         // SV_TASPCanon tokenized its own copy
		if (k == "i")
		{
			if (argc != 8 || !tpr_buf || n >= tpr_size) { tpr_why = "bad input row"; break; }
			b = n * TAS_INPUT_STRIDE;
			for (i = 0; i < 7; i = i + 1)
			{
				if (!SV_TASPNum(argv(i + 1), -32768, 32767, TRUE)) break;
				tpr_buf[b + i] = fs_tas_number;
			}
			if (i < 7 || tpr_buf[b + 6] < 0 || tpr_buf[b + 6] > 7) { tpr_why = sprintf("bad input row %.0f", n + 1); break; }
			n = n + 1;
			continue;
		}
		if (k == "cp")
		{
			// cp <tick> <named 0/1> <name or -> ox oy oz vx vy vz
			if (argc != 10 || tpr_ncp >= TASP_CPMAX || !SV_TASPNum(argv(1), 0, 16000000, TRUE)) { tpr_why = "bad checkpoint"; break; }
			b = tpr_ncp * TASP_CPSTRIDE;
			tpr_cp[b] = fs_tas_number;
			if (tpr_ncp > 0)  // && does not short-circuit: never index row -1
			if (tpr_cp[b] <= tpr_cp[b - TASP_CPSTRIDE]) { tpr_why = "checkpoints out of order"; break; }
			named = (argv(2) == "1");
			if (named && (!SV_TASPNameOK(argv(3)) || SV_TASPNameIndex(names, argv(3)) >= 0)) { tpr_why = "bad checkpoint name"; break; }
			tpr_cp[b + 1] = named;
			if (named) names = strcat(names, argv(3), ";");
			for (i = 0; i < 6; i = i + 1)
			{
				if (!SV_TASPFloat(argv(i + 4), -1000000, 1000000)) break;
				tpr_cp[b + 2 + i] = fs_tas_number;
			}
			if (i < 6) { tpr_why = "bad checkpoint state"; break; }
			tpr_ncp = tpr_ncp + 1;
			continue;
		}
		if (k == "assist") { have = have | 256; continue; }   // hashed, so required (P1089 review 3)
		if (k == "tasproject")
		{
			if (argc != 2 || (argv(1) != "1" && argv(1) != ftos(TASP_VERSION) && argv(1) != ftos(TASP_LEGAL))) { tpr_why = "unknown project version"; break; }
			ver = stof(argv(1)); have = have | 1; continue;
		}
		if (k == "parentsha") { tpr_parsha = strzone(argv(1)); continue; }
		if (k == "supply")
		{
			// supply none | supply <first> <last>: checked against base and head below
			if (ver == 1) { tpr_why = "a supply line in a version 1 file"; break; }
			if (argc == 3)
			{
				if (!SV_TASPNum(argv(1), 1, 16000000 + TASP_MAX, TRUE)) { tpr_why = "bad supply"; break; }
				tpr_supa = fs_tas_number;
				if (!SV_TASPNum(argv(2), 1, 16000000 + TASP_MAX, TRUE)) { tpr_why = "bad supply"; break; }
				tpr_supb = fs_tas_number;
			}
			have = have | 512; continue;
		}
		if (k == "map") { if (argc != 2 || argv(1) != mapname) { tpr_why = "made on another map"; break; } have = have | 2; continue; }
		if (k == "mapcrc")
		{
			if (identity && (argc != 2 || argv(1) != infokey(world, "*mapcrc"))) { tpr_why = "the map file changed"; break; }
			have = have | 32; continue;
		}
		if (k == "zonecrc")
		{
			z = (argc >= 2) ? argv(1) : "";
			if (identity && (argc > 2 || z != zone_crc)) { tpr_why = "the zones changed"; break; }
			have = have | 64; continue;
		}
		if (k == "pmpin")
		{
			if (identity && (pin == "" || substring(l, 6, -1) != pin)) { tpr_why = "the movement rules changed"; break; }
			have = have | 128; continue;
		}
		if (k == "start")
		{
			// P1100: start <zone> -- placed at that start zone's destination; ticks count from it.
			if (ver != TASP_LEGAL || argc != 2 || (have & 4) || !SV_TASPNum(argv(1), 0, 255, TRUE)) { tpr_why = "bad legal start"; break; }
			tpr_zone = fs_tas_number; tpr_base = 0;
			have = have | 4;
			continue;
		}
		if (k == "startat")
		{
			if (ver != TASP_LEGAL || argc != 2 || (have & 1024) || !SV_TASPNum(argv(1), 0, TASP_MAX, TRUE)) { tpr_why = "bad start tick"; break; }
			tpr_startat = fs_tas_number;
			have = have | 1024;
			continue;
		}
		if (k == "base")
		{
			// base <save folder id> <state.txt sha256> <tick>
			if (ver == TASP_LEGAL) { tpr_why = "a base save in a legal-start file"; break; }
			if (argc != 4 || (have & 4) || !SV_TASPNum(argv(1), 1, 99999, TRUE)) { tpr_why = "bad base"; break; }
			tpr_baseid = fs_tas_number;
			if (strlen(argv(2)) != 64) { tpr_why = "bad base hash"; break; }
			hash = argv(2);
			if (!SV_TASPNum(argv(3), 0, 16000000, TRUE)) { tpr_why = "bad base tick"; break; }
			tpr_base = fs_tas_number;
			have = have | 4;
			continue;
		}
		if (k == "head")
		{
			// Sizes the input buffer: exactly head - base rows must follow.
			if (argc != 2 || !(have & 4) || tpr_buf || !SV_TASPNum(argv(1), tpr_base + 1, tpr_base + TASP_MAX, TRUE)) { tpr_why = "bad head"; break; }
			tpr_size = fs_tas_number - tpr_base;
			tpr_buf = (float*)memalloc(tpr_size * TAS_INPUT_STRIDE * 4);
			if (!tpr_buf) { tpr_why = "out of memory"; break; }
			have = have | 8;
			continue;
		}
		if (k == "baseat")
		{
			if (argc != 7 || (have & 16)) { tpr_why = "bad base state"; break; }
			for (i = 0; i < 6; i = i + 1) if (!SV_TASPFloat(argv(i + 1), -1000000, 1000000)) break;
			if (i < 6) { tpr_why = "bad base state"; break; }
			tpr_bo = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
			tpr_bv = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
			if (ver == TASP_LEGAL && tpr_bv != '0 0 0') { tpr_why = "a legal start is placed standing still"; break; }
			have = have | 16;
			continue;
		}
		if (k == "revision") { if (argc != 2 || !SV_TASPNum(argv(1), 1, 16000000, TRUE)) { tpr_why = "bad revision"; break; } tpr_rev = fs_tas_number; continue; }
		if (k == "revsha")
		{
			if (argc == 2 && strlen(argv(1)) == 64 && tpr_revsha == "") tpr_revsha = strzone(argv(1));
			continue;
		}
		if (k == "parent")
		{
			if (argc == 3 && SV_TASPNameOK(argv(1)) && SV_TASPNum(argv(2), 0, 16000000, TRUE))
			{ parent = argv(1); tpr_parentrev = fs_tas_number; }
			continue;
		}
		if (k == "end")
		{
			if (argc != 2 || !SV_TASPNum(argv(1), 1, TASP_MAX, TRUE) || fs_tas_number != n || n != tpr_size) { tpr_why = "row count does not match its trailer"; break; }
			ended = 1;
			continue;
		}
		// assist/origin/saved lines are informational.
	}
	fclose(f);
	if (tpr_why == "" && !ended) tpr_why = "incomplete file (no end line)";
	if (tpr_why == "" && ((have & 31) != 31 || !(have & 256))) tpr_why = "missing header lines";
	if (tpr_why == "" && identity && (have & 224) != 224) tpr_why = "missing map, zone or movement-rule line";
	// P1090: what the writer writes -- a root supplies every tick, a child a span inside it.
	if (tpr_why == "" && ver >= 2 && !(have & 512)) tpr_why = "missing supply line";
	if (tpr_why == "" && tpr_supa > 0)
	if (tpr_supa < tpr_base + 1 || tpr_supb < tpr_supa || tpr_supb > tpr_base + n) tpr_why = "supply outside the project";
	if (tpr_why == "" && ver >= 2 && tpr_parsha == "")
	if (tpr_supa != tpr_base + 1 || tpr_supb != tpr_base + n) tpr_why = "a root's supply is not all of its ticks";
	if (ver == 1) tpr_supa = -1;
	if (tpr_why == "" && ver == TASP_LEGAL && !(have & 1024)) tpr_why = "missing start tick";
	if (tpr_why == "" && ver == TASP_LEGAL && tpr_startat > n) tpr_why = "the start tick is past the head";
	tpr_ver = ver;
	if (tpr_why == "" && tpr_ncp > 0)
	if (tpr_cp[0] <= tpr_base || tpr_cp[(tpr_ncp - 1) * TASP_CPSTRIDE] > tpr_base + n)
		tpr_why = "checkpoint outside the project";
	if (tpr_why == "" && e.run_tas_mode == 1 && e.run_tas_used == 1)
	{
		i = SV_TASPValidate(e, tpr_buf, n);
		if (i) tpr_why = sprintf("input row %.0f refused by the engine", i);
	}
	if (tpr_why != "") { SV_TASPReadFree(); return FALSE; }
	tpr_n = n;
	tpr_hash = strzone(hash); tpr_parent = strzone(parent); tpr_cpnames = strzone(names);
	return TRUE;
};

void(entity e) SV_TASProjectEvent =
{
	local float s;
	s = SV_TASPSlot(e);
	if (!s || Lobby_Active()) return;   // a lobby's csprogs may predate event 51
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, TAS_EV_PROJECT);
	WriteString(MSG_MULTICAST, e.tasp_on ? tasp_name[s] : "");
	WriteLong(MSG_MULTICAST, e.tasp_rev);
	WriteLong(MSG_MULTICAST, e.tasp_base);
	WriteLong(MSG_MULTICAST, e.tasp_filehead);
	WriteByte(MSG_MULTICAST, e.tasp_load);
	WriteLong(MSG_MULTICAST, e.tasp_load ? e.tasp_stop : 0);
	WriteByte(MSG_MULTICAST, e.tasp_result);
	WriteFloat(MSG_MULTICAST, e.tasp_dev);
	WriteLong(MSG_MULTICAST, e.tasp_devtick);
	WriteByte(MSG_MULTICAST, e.tasp_ncp);
	// P1090: what the panel signs (tasp_supa > 0 only for a version 2 revision on disk).
	WriteString(MSG_MULTICAST, e.tasp_on ? tasp_revsha[s] : "");
	WriteString(MSG_MULTICAST, e.tasp_on ? tasp_parsha[s] : "");
	WriteString(MSG_MULTICAST, infokey(world, "*mapcrc"));
	WriteLong(MSG_MULTICAST, e.tasp_on ? e.tasp_supa : 0);
	WriteLong(MSG_MULTICAST, e.tasp_supb);
	WriteByte(MSG_MULTICAST, e.tasp_signed);
	WriteByte(MSG_MULTICAST, e.tasp_made);
	msg_entity = e;
	multicast('0 0 0', SH_MC_ONE);
};

// Grow the slot's input buffer to hold `ticks`, doubling.
float(entity e, float s, float ticks) SV_TASPEnsure =
{
	local float *nb;
	local float i, cap;
	if (ticks > TASP_MAX) return FALSE;
	if (ticks <= e.tasp_cap && tasp_buf[s]) return TRUE;
	cap = max(4096, e.tasp_cap);
	while (cap < ticks) cap = cap * 2;
	cap = min(cap, TASP_MAX);
	nb = (float*)memalloc(cap * TAS_INPUT_STRIDE * 4);
	if (!nb) return FALSE;
	if (tasp_buf[s])
	{
		for (i = 0; i < e.tasp_n * TAS_INPUT_STRIDE; i = i + 1) nb[i] = tasp_buf[s][i];
		memfree(tasp_buf[s]);
	}
	tasp_buf[s] = nb;
	e.tasp_cap = cap;
	return TRUE;
};

float(float deg) SV_TASPWord =
{
	local float w;
	w = rint(deg * 65536 / 360);
	if (w > 32767) w = w - 65536;
	if (w < -32768) w = w + 65536;
	return w;
};

// Anchor the harvest at recorder line `line`: the last `in` row before it is tick synced's.
// `branch`: that row's move counter does not continue into the next (a go or load between).
void(entity e, float line, float branch) SV_TASPAnchorLine =
{
	local float i, lo;
	local string l;
	line = min(line, e.rec_rec_lines);
	e.tasp_line = line; e.tasp_linemt = -1;
	if (branch || e.rec_rec_buf < 1) return;
	lo = max(0, line - 4096);
	for (i = line - 1; i >= lo; i = i - 1)
	{
		l = bufstr_get(e.rec_rec_buf, i);
		if (substring(l, 0, 7) == "resume " || substring(l, 0, 8) == "session " || substring(l, 0, 6) == "pause ")
			return;   // the next row starts a branch: the counter does not continue
		if (substring(l, 0, 3) == "in ")
		{
			tokenize(l);
			e.tasp_linemt = stof(argv(2));
			return;
		}
	}
};

// Inputs come from the recorder's `in` rows, one per simulated tick; the ring samples once per
// packet and has gaps. Each row's move counter must follow the last; every 16th tick and the
// last are also checked against the engine's own capture where the ring kept a row.
float(entity e, float s, float last) SV_TASPHarvest =
{
	local float t, i, n, b, argc, w, mt, oldest;
	local string l;
	local vector meta, mv, an, bits;

	tasp_why = "";
	if (last <= e.tasp_synced) return TRUE;
	if (e.rec_rec_stream || e.rec_rec_buf < 1) { tasp_why = "streamed recording"; return FALSE; }
	if (last - e.tasp_base > TASP_MAX) { tasp_why = "longer than a project holds"; return FALSE; }
	if (e.tasp_line < 0)
	{
		if (!SV_RewindFindTick(e, e.tasp_synced)) { tasp_why = sprintf("no exact row at tick %.0f to align with", e.tasp_synced); return FALSE; }
		SV_TASPAnchorLine(e, rw_slot[s][rw_statebase + 29], FALSE);
	}
	if (!SV_TASPEnsure(e, s, last - e.tasp_base)) { tasp_why = "out of memory"; return FALSE; }
	n = min(buf_getsize(e.rec_rec_buf), e.rec_rec_lines);
	i = e.tasp_line; t = e.tasp_synced; mt = e.tasp_linemt;
	oldest = 16000001;
	if (rw_slot[s] && e.rw_n > 0)
		oldest = rw_slot[s][((e.rw_head - e.rw_n + RW_CAP * 2) % RW_CAP) * RW_STRIDE];
	while (t < last)
	{
		l = "";
		for (; i < n; i = i + 1)
		{
			l = bufstr_get(e.rec_rec_buf, i);
			if (substring(l, 0, 3) == "in ") break;
			// A go or a load writes one of these at its cut; the counter does not continue.
			if (substring(l, 0, 7) == "resume " || substring(l, 0, 8) == "session " || substring(l, 0, 6) == "pause ")
				mt = -1;
		}
		if (i >= n) { tasp_why = sprintf("the recording has no input for tick %.0f", t + 1); return FALSE; }
		argc = tokenize(l);
		if (argc != 12 || (stof(argv(11)) & 8)) { tasp_why = sprintf("tick %.0f is not one whole recorded move", t + 1); return FALSE; }
		if (mt >= 0 && stof(argv(2)) != mt + 1) { tasp_why = sprintf("the recorded moves do not line up at tick %.0f", t + 1); return FALSE; }
		mt = stof(argv(2));
		b = (t - e.tasp_base) * TAS_INPUT_STRIDE;
		tasp_buf[s][b] = stof(argv(4)); tasp_buf[s][b+1] = stof(argv(5)); tasp_buf[s][b+2] = stof(argv(6));
		tasp_buf[s][b+3] = SV_TASPWord(stof(argv(7)));
		tasp_buf[s][b+4] = SV_TASPWord(stof(argv(8)));
		tasp_buf[s][b+5] = SV_TASPWord(stof(argv(9)));
		tasp_buf[s][b+6] = stof(argv(10));
		t = t + 1; i = i + 1;
		if ((t - e.tasp_base) % 16 == 0 || t == last)
		if (t >= oldest)
		if (SV_RewindFindTick(e, t))
		{
			meta = tas_input(e, rw_native_slot, rw_native_token, 0);
			if (meta_x == 1)
			{
				mv = tas_input(e, rw_native_slot, rw_native_token, 1);
				an = tas_input(e, rw_native_slot, rw_native_token, 2);
				bits = tas_input(e, rw_native_slot, rw_native_token, 3);
				w = (mv == [tasp_buf[s][b], tasp_buf[s][b+1], tasp_buf[s][b+2]] &&
					an == [tasp_buf[s][b+3], tasp_buf[s][b+4], tasp_buf[s][b+5]] && bits_x == tasp_buf[s][b+6]);
				if (!w) { tasp_why = sprintf("the recording and the engine disagree about tick %.0f", t); return FALSE; }
			}
		}
		e.tasp_synced = t; e.tasp_line = i; e.tasp_linemt = mt;
		if (t - e.tasp_base > e.tasp_n) e.tasp_n = t - e.tasp_base;
	}
	return TRUE;
};

// This attempt left the project's line: later saves need a new name or force.
void(entity e, string why) SV_TASPDetach =
{
	if (e.tasp_serial == -1) return;
	e.tasp_serial = -1;
	sprint(e, PRINT_HIGH, sprintf("tas project: %s left %s's line (%s); save under a new name, or with force\n",
		"this attempt", tasp_name[SV_TASPSlot(e)], why));
};

// Called from SV_TASGo after its restore: every tick after the new head is replaced.
void(entity e) SV_TASProjectTouch =
{
	local float h;
	if (!e.tasp_on || e.tasp_load || e.tasp_serial != e.rec_rec_serial) return;
	h = SV_TimerTicks(e);
	e.tasp_lasthead = h; e.tasp_gen = e.rec_rec_gen;
	e.tasp_cut = min(e.tasp_cut, h);
	if (h < e.tasp_base) { SV_TASPDetach(e, "went back before its base"); return; }
	if (h >= e.tasp_synced) return;
	e.tasp_synced = h;
	SV_TASPAnchorLine(e, e.rec_rec_lines, TRUE);   // the replayed ticks' counter continues on
};

void(entity e, string why) SV_TASPAbort =
{
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE) tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
	e.tasp_load = 0; e.tasp_ccount = 0; e.tasp_result = 3;
	e.tasp_serial = -1;
	sprint(e, PRINT_HIGH, sprintf("tas project: load stopped at tick %.0f: %s; load it again to continue\n",
		SV_TimerTicks(e), why));
	SV_TASProjectEvent(e);
};

// Drives a load one <=128-tick chunk at a time: from the load command, then the settled hook.
void(entity e) SV_TASProjectDrive =
{
	local float s, head, count, i, b, k, tx, ok, d, nextcp;
	local vector o, v;

	s = SV_TASPSlot(e);
	if (!s) return;
	if (!e.run_tas_paused) { SV_TASPAbort(e, "TAS play/off"); return; }
	if (e.run_tas_replaystate == TAS_TAPE_ACTIVE) return;
	if (e.tasp_ccount)
	{
		if (e.run_tas_replaystate == TAS_TAPE_CANCELLED || e.run_tas_replaystate == TAS_TAPE_FAULT)
		{
			SV_TASPAbort(e, "the engine stopped the input tape"); return;
		}
		if (e.run_tas_replaystate != TAS_TAPE_DONE) return;
		ok = (e.run_t_state == TS_RUNNING && (e.run_t_flags & TF_RECORDING) &&
			e.rec_rec_serial == e.tasp_serial && SV_TimerTicks(e) == e.tasp_chead &&
			e.run_tas_pending == 0 && e.run_tas_done - e.tasp_cbase == e.tasp_ccount);
		if (!ok) { SV_TASPAbort(e, "a chunk did not land on its expected tick"); return; }
		e.tasp_ccount = 0;
	}
	head = SV_TimerTicks(e);
	e.tasp_synced = head; e.tasp_lasthead = head;
	SV_TASPAnchorLine(e, e.rec_rec_lines, FALSE);
	// Checkpoints at this head: exact float compare against the stored state.
	while (e.tasp_cpi < e.tasp_ncp)
	{
		b = e.tasp_cpi * TASP_CPSTRIDE;
		if (tasp_cp[s][b] > head) break;
		if (tasp_cp[s][b] == head)
		{
			o = [tasp_cp[s][b+2], tasp_cp[s][b+3], tasp_cp[s][b+4]];
			v = [tasp_cp[s][b+5], tasp_cp[s][b+6], tasp_cp[s][b+7]];
			d = max(vlen(e.origin - o), vlen(e.velocity - v));
			if (d > 0 && !e.tasp_devtick) e.tasp_devtick = head;
			e.tasp_dev = max(e.tasp_dev, d);
			// From here on the stored state describes THIS load's trajectory.
			tasp_cp[s][b+2] = e.origin_x; tasp_cp[s][b+3] = e.origin_y; tasp_cp[s][b+4] = e.origin_z;
			tasp_cp[s][b+5] = e.velocity_x; tasp_cp[s][b+6] = e.velocity_y; tasp_cp[s][b+7] = e.velocity_z;
		}
		e.tasp_cpi = e.tasp_cpi + 1;
	}
	if (head >= e.tasp_stop)
	{
		e.tasp_load = 0;
		if (e.tasp_legal) e.tasp_serial = -1;   // its line is the session's (SV_TASProjectSaveLegal), not this attempt's
		e.tasp_result = e.tasp_devtick ? 2 : 1;
		if (e.tasp_devtick)
			sprint(e, PRINT_HIGH, sprintf("tas project: loaded %s to tick %.0f; DIVERGED from its saved states at tick %.0f (max %.4f); paused\n",
				tasp_name[s], head + (e.tasp_legal ? e.tasp_lstartat : 0), e.tasp_devtick + (e.tasp_legal ? e.tasp_lstartat : 0), e.tasp_dev));
		else
			sprint(e, PRINT_HIGH, sprintf("tas project: loaded %s to tick %.0f; reproduced every saved state exactly; paused\n",
				tasp_name[s], head + (e.tasp_legal ? e.tasp_lstartat : 0)));
		SV_TASProjectEvent(e);
		return;
	}
	count = min(TAS_TAPE_MAX, e.tasp_stop - head);
	nextcp = 0;
	for (k = e.tasp_cpi; k < e.tasp_ncp; k = k + 1)
		if (tasp_cp[s][k * TASP_CPSTRIDE] > head) { nextcp = tasp_cp[s][k * TASP_CPSTRIDE]; break; }
	if (nextcp > head) count = min(count, nextcp - head);
	if (!tas_tape(e, 2, count, 0, '0 0 0', '0 0 0', 0)) { SV_TASPAbort(e, "engine execution headroom"); return; }
	tx = tas_tape(e, 3, count, 0, '0 0 0', '0 0 0', 0);
	ok = tx > 0;
	for (i = 0; i < count && ok; i = i + 1)
	{
		b = (head - e.tasp_base + i) * TAS_INPUT_STRIDE;
		ok = tas_tape(e, 4, tx, i, [tasp_buf[s][b], tasp_buf[s][b+1], tasp_buf[s][b+2]],
			[tasp_buf[s][b+3], tasp_buf[s][b+4], tasp_buf[s][b+5]], tasp_buf[s][b+6]);
	}
	if (ok) ok = tas_tape(e, 5, tx, 0, '0 0 0', '0 0 0', 0);
	if (!ok)
	{
		tas_tape(e, 0, 0, 0, '0 0 0', '0 0 0', 0);
		SV_TASPAbort(e, "staging the input tape failed");
		return;
	}
	// SV_TASReplayFrame cancels an active tape whose serial is not this one.
	e.run_tas_replayserial = e.rec_rec_serial;
	e.tasp_chead = head + count; e.tasp_cbase = e.run_tas_done; e.tasp_ccount = count;
};

// The settled hook: the next load chunk, and a rewind outside a TAS go detaches.
void(entity e) SV_TASProjectFrame =
{
	local float head;
	if (!e.tasp_on || !SV_TASPSlot(e)) return;
	if (e.tasp_load) { SV_TASProjectDrive(e); return; }
	if (e.run_t_state != TS_RUNNING || e.rec_rec_serial != e.tasp_serial) return;
	head = SV_TimerTicks(e);
	if (head < e.tasp_lasthead || e.rec_rec_gen != e.tasp_gen) { SV_TASPDetach(e, "rewound or loaded outside the TAS controls"); return; }
	e.tasp_lasthead = head;
};

// The stored state of tick t in the slot's checkpoint list, into rw_o/rw_v; FALSE if absent.
float(float s, float n, float t) SV_TASPOldState =
{
	local float k, b;
	if (!tasp_cp[s]) return FALSE;
	for (k = 0; k < n; k = k + 1)
	{
		b = k * TASP_CPSTRIDE;
		if (tasp_cp[s][b] == t)
		{
			rw_o = [tasp_cp[s][b+2], tasp_cp[s][b+3], tasp_cp[s][b+4]];
			rw_v = [tasp_cp[s][b+5], tasp_cp[s][b+6], tasp_cp[s][b+7]];
			return TRUE;
		}
	}
	return FALSE;
};

// Rebuild checkpoints for (base, head]: auto every `every`, the named ones, the head. Only those
// ticks are visited. States come from the ring, else the old list; a state found nowhere drops.
void(entity e, float s, float head) SV_TASPCheckpoints =
{
	local float *nc;
	local float n, t, j, b, at, nt, named, oldn, nk, every, found;
	local string names;

	nc = (float*)memalloc(TASP_CPMAX * TASP_CPSTRIDE * 4);
	if (!nc) return;
	every = TASP_CPEVERY;
	while ((head - e.tasp_base) / every > 32) every = every * 2;
	oldn = tasp_cp[s] ? e.tasp_ncp : 0;
	n = 0; names = ""; j = 0; nk = 0;
	at = e.tasp_base + every;
	while (n < TASP_CPMAX)
	{
		// The next named row of the old list that still lies in (base, head].
		nt = 16000001;
		for (; j < oldn; j = j + 1)
		{
			b = j * TASP_CPSTRIDE;
			if (!tasp_cp[s][b+1]) continue;
			if (tasp_cp[s][b] > e.tasp_base && tasp_cp[s][b] <= head) { nt = tasp_cp[s][b]; break; }
			nk = nk + 1;   // a named row dropped here still owns a name slot
		}
		t = min(min(nt, at < head ? at : 16000001), head);
		named = (t == nt);
		if (n == TASP_CPMAX - 1 && t != head) t = head;   // the last slot is the head's
		found = FALSE;
		if (SV_RewindFindTick(e, t)) found = TRUE;
		else if (t <= e.tasp_cut)
		{
			if (SV_TASPOldState(s, oldn, t)) found = TRUE;
		}
		if (!found && t == head) { rw_o = e.origin; rw_v = e.velocity; found = TRUE; }
		if (found)
		{
			b = n * TASP_CPSTRIDE;
			nc[b] = t; nc[b+1] = named && t == nt;
			nc[b+2] = rw_o_x; nc[b+3] = rw_o_y; nc[b+4] = rw_o_z;
			nc[b+5] = rw_v_x; nc[b+6] = rw_v_y; nc[b+7] = rw_v_z;
			if (nc[b+1]) names = strcat(names, SV_TASPNameAt(tasp_cpnames[s], nk), ";");
			n = n + 1;
		}
		if (t == head) break;
		if (t == nt) { j = j + 1; nk = nk + 1; }
		if (t == at) at = at + every;
	}
	if (tasp_cp[s]) memfree(tasp_cp[s]);
	tasp_cp[s] = nc; e.tasp_ncp = n;
	if (tasp_cpnames[s]) strunzone(tasp_cpnames[s]);
	tasp_cpnames[s] = strzone(names);
};

/*
  P1089: a revision's identity (TAS plan 5.1). A hash chain over the file's canonical lines,
  so a long project needs no one huge string: h0 = sha256("FTESURF-TASREV-CANON 1"), then
  h = sha256(h + "\n" + line) per line, lowercase hex. Local-only lines are left out (saved,
  revision, origin, parent, revsha) and `base` loses its local save id. tools/tasrev.py is
  the twin surfd uses; keep the two in step.
*/
// P1089: every line of a revision but its revsha, as the reader requires them.
void(filestream f, entity e, float s, string parent) SV_TASPEmit =
{
	local float i, b, nm;
	fputs(f, sprintf("tasproject %.0f\n", e.tasp_legal ? TASP_LEGAL : TASP_VERSION));
	fputs(f, sprintf("map %s\n", mapname));
	fputs(f, sprintf("mapcrc %s\n", infokey(world, "*mapcrc")));
	fputs(f, sprintf("zonecrc %s\n", zone_crc));
	fputs(f, sprintf("pmpin %s\n", SV_RecPinText(e, "*pmpin")));
	fputs(f, "assist tas\norigin local\n");
	fputs(f, sprintf("saved %s\n", strftime(FALSE, "%Y-%m-%dT%H:%M:%S")));
	fputs(f, sprintf("revision %.0f\n", e.tasp_rev));
	if (parent != "") fputs(f, sprintf("parent %s %.0f\n", parent, e.tasp_parentrev));
	if (tasp_revsha[s] != "") fputs(f, sprintf("parentsha %s\n", tasp_revsha[s]));   // P1089
	if (e.tasp_supa > 0) fputs(f, sprintf("supply %.0f %.0f\n", e.tasp_supa, e.tasp_supb));   // P1090
	else fputs(f, "supply none\n");
	if (e.tasp_legal)
	{
		// P1100: placed at a start zone's destination, standing still; ticks count from there.
		fputs(f, sprintf("start %.0f\n", e.tasp_lzone));
		fputs(f, sprintf("baseat %.9g %.9g %.9g 0 0 0\n", SV_TASPZ(e.tasp_lo_x), SV_TASPZ(e.tasp_lo_y), SV_TASPZ(e.tasp_lo_z)));
		fputs(f, sprintf("startat %.0f\n", e.tasp_lstartat));
	}
	else
	{
		fputs(f, sprintf("base %.0f %s %.0f\n", e.tasp_baseid, tasp_hash[s], SV_TASPZ(e.tasp_base)));
		fputs(f, sprintf("baseat %.9g %.9g %.9g ", SV_TASPZ(e.tasp_bo_x), SV_TASPZ(e.tasp_bo_y), SV_TASPZ(e.tasp_bo_z)));
		fputs(f, sprintf("%.9g %.9g %.9g\n", SV_TASPZ(e.tasp_bv_x), SV_TASPZ(e.tasp_bv_y), SV_TASPZ(e.tasp_bv_z)));
	}
	fputs(f, sprintf("head %.0f\n", e.tasp_base + e.tasp_n));
	nm = 0;
	for (i = 0; i < e.tasp_ncp; i = i + 1)
	{
		b = i * TASP_CPSTRIDE;
		fputs(f, sprintf("cp %.0f %.0f %s ", SV_TASPZ(tasp_cp[s][b]), tasp_cp[s][b+1],
			tasp_cp[s][b+1] ? SV_TASPNameAt(tasp_cpnames[s], nm) : "-"));
		fputs(f, sprintf("%.9g %.9g %.9g %.9g %.9g %.9g\n",
			SV_TASPZ(tasp_cp[s][b+2]), SV_TASPZ(tasp_cp[s][b+3]), SV_TASPZ(tasp_cp[s][b+4]),
			SV_TASPZ(tasp_cp[s][b+5]), SV_TASPZ(tasp_cp[s][b+6]), SV_TASPZ(tasp_cp[s][b+7])));
		if (tasp_cp[s][b+1]) nm = nm + 1;
	}
	for (i = 0; i < e.tasp_n; i = i + 1)
	{
		b = i * TAS_INPUT_STRIDE;
		fputs(f, sprintf("i %.0f %.0f %.0f %.0f ", SV_TASPZ(tasp_buf[s][b]), SV_TASPZ(tasp_buf[s][b+1]),
			SV_TASPZ(tasp_buf[s][b+2]), SV_TASPZ(tasp_buf[s][b+3])));
		fputs(f, sprintf("%.0f %.0f %.0f\n", SV_TASPZ(tasp_buf[s][b+4]), SV_TASPZ(tasp_buf[s][b+5]), SV_TASPZ(tasp_buf[s][b+6])));
	}
	fputs(f, sprintf("end %.0f\n", e.tasp_n));
};

// P1089 review 2: an empty identity value would end its line in a space the reader refuses.
float(entity e) SV_TASPIdentityOK =
{
	if (infokey(world, "*mapcrc") == "" || zone_crc == "" || SV_RecPinText(e, "*pmpin") == "")
	{
		sprint(e, PRINT_HIGH, "tas project: this map has no checksum, zones or movement pin to bind a project to\n");
		return FALSE;
	}
	return TRUE;
};

/*
  P1089 reviews 3-4: the real file is never written in place. FILE_WRITE buffers in memory and
  replaces the file at fclose, so an abort with the buffer open (the runaway counter) would
  leave a truncated revision. The revision goes to <path>.new (removed first and checked gone,
  so a stale one is never validated), is read back with the identity lines, gets its revsha,
  and only then replaces the real file: remove, then rename (Windows will not rename over a
  file). A failed rename keeps the complete .new and says so.
  P1090 review 3: the revsha goes on in a copy (<path>.new2); FILE_APPEND reloads the whole
  file and rewrites it at fclose, so a failed reload would leave only the appended line.
*/
// `n` lines, the last of them `last`: a written file is whole (FILE_WRITE fails silently at fclose).
float(string path, float n, string last) SV_TASPLinesAre =
{
	local filestream f;
	local string l, z;
	local float k;
	f = fopen(path, FILE_READ);
	if (f < 0) return FALSE;
	k = 0; z = "";
	while ((l = fgets(f)) != "") { k = k + 1; z = l; }
	fclose(f);
	return (k == n && z == last);
};

// `src`'s lines but any revsha, then `revsha <sha>`, into a fresh `dst`, read back whole.
// `stated`: refuse unless src's own revsha line is `sha` (it is that revision). FALSE leaves
// no dst behind.
float(string src, string dst, string sha, float stated) SV_TASPCopy =
{
	local filestream f, o;
	local string l;
	local float ok, n;
	fremove(dst);
	f = fopen(src, FILE_READ);
	if (f < 0) return FALSE;
	o = fopen(dst, FILE_WRITE);
	if (o < 0) { fclose(f); return FALSE; }
	ok = !stated; n = 1;
	while ((l = fgets(f)) != "")
	{
		if (substring(l, 0, 7) != "revsha ") { fputs(o, strcat(l, "\n")); n = n + 1; }
		else if (l == strcat("revsha ", sha)) ok = TRUE;
	}
	fputs(o, sprintf("revsha %s\n", sha));
	fclose(o); fclose(f);
	if (ok) ok = SV_TASPLinesAre(dst, n, strcat("revsha ", sha));
	if (!ok) fremove(dst);
	return ok;
};

float(entity e, float s, string name, string parent) SV_TASPWrite =
{
	local filestream f;
	local string h, tmp, tmp2, real;
	if (!SV_TASPIdentityOK(e)) return FALSE;
	real = strzone(SV_TASPPath(name));
	tmp = strzone(strcat(real, ".new"));
	fremove(tmp);
	f = fopen(tmp, FILE_READ);
	if (f >= 0)
	{
		fclose(f);
		sprint(e, PRINT_HIGH, sprintf("tas project: cannot clear %s; the last revision is kept\n", tmp));
		strunzone(tmp); strunzone(real); return FALSE;
	}
	f = fopen(tmp, FILE_WRITE);
	if (f < 0) { strunzone(tmp); strunzone(real); return FALSE; }
	SV_TASPEmit(f, e, s, parent);
	fclose(f);
	tpr_pathover = tmp;
	if (!SV_TASPRead(e, name, TRUE))
	{
		tpr_pathover = "";
		sprint(e, PRINT_HIGH, sprintf("tas project: the new revision would not load (%s); the last one is kept\n", tpr_why));
		SV_TASPReadFree(); fremove(tmp); strunzone(tmp); strunzone(real);
		return FALSE;
	}
	tpr_pathover = "";
	h = strzone(tpr_h);
	SV_TASPReadFree();
	tmp2 = strzone(strcat(real, ".new2"));
	if (!SV_TASPCopy(tmp, tmp2, h, FALSE))
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: could not write %s; the last revision is kept\n", tmp2));
		fremove(tmp); strunzone(tmp); strunzone(tmp2); strunzone(real); strunzone(h); return FALSE;
	}
	fremove(real);
	if (frename(tmp2, real) != 0)
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: could not move %s into place; the revision is in that file\n", tmp2));
		strunzone(tmp); strunzone(tmp2); strunzone(real); strunzone(h);
		return FALSE;
	}
	fremove(tmp);
	strunzone(tmp); strunzone(tmp2); strunzone(real);
	if (tasp_parsha[s]) strunzone(tasp_parsha[s]);
	tasp_parsha[s] = tasp_revsha[s];   // the parent this revision names, or ""
	tasp_revsha[s] = h;
	return TRUE;
};

float(entity e) SV_TASPLocalOnly =
{
	if (Lobby_Active())
	{
		sprint(e, PRINT_HIGH, "tas project: projects are local-only for now (this is a lobby)\n");
		return FALSE;
	}
	if (e.rec_rec_stream)
	{
		sprint(e, PRINT_HIGH, "tas project: needs a buffered recording (rec_stream 0)\n");
		return FALSE;
	}
	return TRUE;
};

// The oldest dense ring row this attempt captured natively, that is warm and reachable over
// short packet gaps -- one pass over the ring (SV_RewindFindTick per tick would search it).
// Returns its tick, -1 for none; leaves its row base in rw_statebase.
float(entity e, float head) SV_TASPOldestBase =
{
	local float *m;
	local float k, idx, b, t, prev, best, bestb;
	m = rw_slot[num_for_edict(e)];
	if (!m) return -1;
	best = -1; bestb = -1; prev = head + 1;
	for (k = 0; k < e.rw_n; k = k + 1)
	{
		idx = (e.rw_head - 1 - k + RW_CAP * 2) % RW_CAP;
		b = idx * RW_STRIDE;
		t = m[b];
		if (t >= prev || prev - t > 9 || head - t >= TASP_MAX) break;
		if (m[b+33] != e.rec_rec_serial || m[b+RW_NATIVEBASE] <= 0) break;
		rw_statebase = b;
		if (!SV_RewindWarmReady(e)) break;
		best = t; bestb = b; prev = t;
	}
	rw_statebase = bestb;
	return best;
};

/*
  P1090: the author statement (TAS plan 5.2). The client's tasrev_sign (engine, cl_receipt.c)
  signs FTESURF-TASREV 1 over sha, parent, mapcrc, `ticks <supply>` and the game code's
  sha256. Every revision saved or loaded is kept as rev/<sha>.tasp (rev/<sha>.made if it was
  saved here: only those are signed), and each statement as its own rev/<sha>.<id>.tasrev,
  one line `tasrev 1 sha parent|- mapcrc first last code pub sig`: every field of the
  statement. The named <name>.tasp is only the working copy. tools/tasrev.py rebuilds and
  checks a statement, and a child's supply against its kept parent.
*/
string(string sha, string ext) SV_TASPRevPath = { return sprintf("data/tasproj/%s/rev/%s.%s", mapname, sha, ext); };

float(string path) SV_TASPFileIs =
{
	local filestream f;
	f = fopen(path, FILE_READ);
	if (f < 0) return FALSE;
	fclose(f);
	return TRUE;
};

// A copy of a revision the strict reader accepted, its revsha line (outside the hash) set to
// the computed hash. A copy already there is trusted here and checked when it is signed.
// `replace`: put a checked copy over an existing one (only once the copy is whole).
float(string src, string sha, float stated, float replace) SV_TASPKeep =
{
	local string dst, tmp;
	local float ok;
	if (sha == "") return FALSE;
	if (!replace && SV_TASPFileIs(SV_TASPRevPath(sha, "tasp"))) return TRUE;
	dst = strzone(SV_TASPRevPath(sha, "tasp")); tmp = strzone(strcat(dst, ".new"));
	ok = SV_TASPCopy(src, tmp, sha, stated);
	if (ok)
	{
		fremove(dst);
		ok = (frename(tmp, dst) == 0);   // a failed rename leaves the whole copy in .new
	}
	strunzone(dst); strunzone(tmp);
	return ok;
};

// Statements: one write-once file each, rev/<sha>.<16 hex of the line's sha256>.tasrev, so no
// write ever rewrites another. On file is not verified (QC has no Ed25519; tasrev.py does).
string(string sha, string line) SV_TASPStmtPath =
{
	return sprintf("data/tasproj/%s/rev/%s.%s.tasrev", mapname, sha, substring(strtolower(digest_hex("SHA256", line)), 0, 16));
};
float(string sha) SV_TASPSignedFor =
{
	local searchhandle h;
	local float n;
	h = search_begin(sprintf("data/tasproj/%s/rev/%s.*.tasrev", mapname, sha), TRUE, TRUE);
	if (h < 0) return FALSE;
	n = search_getsize(h);
	search_end(h);
	return (n > 0);
};

// The kept copy reads back strictly as this revision.
float(entity e, string sha) SV_TASPKeptOK =
{
	local float ok;
	tpr_pathover = strzone(SV_TASPRevPath(sha, "tasp"));
	ok = SV_TASPRead(e, "", FALSE);
	if (ok) ok = (tpr_h == sha);
	SV_TASPReadFree();
	strunzone(tpr_pathover); tpr_pathover = "";
	return ok;
};

// The slot's buffer becomes the current revision's own rows. The copy is installed only once
// complete, so an abort part-way leaves no rows (claim nothing), never short ones.
void(entity e, float s) SV_TASPParentKeep =
{
	local float i, n;
	local float *nb;
	if (tasp_pbuf[s]) memfree(tasp_pbuf[s]);
	tasp_pbuf[s] = 0;
	e.tasp_pn = 0; e.tasp_lineserial = e.rec_rec_serial;   // the lineage holds without the rows
	n = e.tasp_n * TAS_INPUT_STRIDE;
	nb = (float*)memalloc(max(1, n) * 4);
	if (!nb)
	{
		sprint(e, PRINT_HIGH, "tas project: out of memory for this revision's rows; the next save will claim no ticks\n");
		return;
	}
	for (i = 0; i < n; i = i + 1) nb[i] = tasp_buf[s][i];
	tasp_pbuf[s] = nb; e.tasp_pbase = e.tasp_base; e.tasp_pn = e.tasp_n;
};

// What the revision being saved supplies: from the first to the last tick after the parent's
// base whose row differs from the parent's own (or that is past the parent's head); a root
// supplies every tick. A tick at or before the parent's base is an older ancestor's or
// unknown, and is never claimed (P1090 review 3).
void(entity e, float s, float head) SV_TASPSupply =
{
	local float t, b, pb, k, d, a, z;
	if (tasp_revsha[s] == "") { e.tasp_supa = e.tasp_base + 1; e.tasp_supb = head; return; }
	e.tasp_supa = e.tasp_supb = 0;
	if (!tasp_pbuf[s]) return;   // a parent without its rows: claim nothing rather than everything
	a = z = 0;
	for (t = max(e.tasp_base, e.tasp_pbase) + 1; t <= head; t = t + 1)
	{
		b = (t - e.tasp_base - 1) * TAS_INPUT_STRIDE;
		d = TRUE;
		if (t <= e.tasp_pbase + e.tasp_pn)
		{
			pb = (t - e.tasp_pbase - 1) * TAS_INPUT_STRIDE;
			d = FALSE;
			for (k = 0; k < 7; k = k + 1) if (tasp_buf[s][b + k] != tasp_pbuf[s][pb + k]) d = TRUE;
		}
		if (d) { if (!a) a = t; z = t; }
	}
	e.tasp_supa = a; e.tasp_supb = z;
};

void(entity e) SV_TASPSupplyNote =
{
	if (e.tasp_supa > 0)
		sprint(e, PRINT_HIGH, sprintf("tas project: rev %.0f supplies ticks %.0f..%.0f%s\n", e.tasp_rev,
			e.tasp_supa, e.tasp_supb, (tasp_parsha[SV_TASPSlot(e)] == "") ? " (a root: all of them)" : " over its parent"));
	else if (e.tasp_supa == 0)
		sprint(e, PRINT_HIGH, sprintf("tas project: rev %.0f changes no inputs of its parent; nothing to sign\n", e.tasp_rev));
};

// `name` is a zoned copy owned by the caller ("" = the attached project's).
void(entity e, string name, float force) SV_TASProjectSave =
{
	local float s, head, attached, B, id, t, exists, oldidx, row, fork, prev, oldrev;
	local filestream f;
	local float *m;
	local string hash, parent;
	local vector bo, bv;

	s = SV_TASPSlot(e);
	if (!s || !SV_TASPLocalOnly(e) || !SV_TASInputReady(e)) return;
	if (e.tasp_load) { sprint(e, PRINT_HIGH, "tas project: a load is still running\n"); return; }
	if (e.tasp_legal)
	{
		// P1100: a version 3 line counts ticks from a placement, so it is never a base save's parent.
		e.tasp_on = 0; e.tasp_serial = -1; e.tasp_legal = 0;
		if (tasp_revsha[s] != "") { strunzone(tasp_revsha[s]); tasp_revsha[s] = ""; }
	}
	oldrev = e.tasp_rev;
	SV_RewindTASHead(e);
	head = SV_TimerTicks(e);
	attached = (e.tasp_on && e.tasp_serial == e.rec_rec_serial && e.tasp_base < head);
	if (attached)
	{
		row = SV_TASPRow(e, e.tasp_baseid);
		if (!row) attached = FALSE;
		else if (SV_TASPStateHash(e.tasp_baseid) != tasp_hash[s]) attached = FALSE;
	}
	if (name == "")
	{
		if (e.tasp_on) name = tasp_name[s];
		else for (t = 1; t < 1000; t = t + 1)
		{
			name = sprintf("tas%.0f", t);
			if (!SV_TASPExists(name)) break;
		}
	}
	exists = SV_TASPExists(name);
	if (exists && !force && !(attached && name == tasp_name[s]))
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: %s already exists; tas project load %s, or save under a new name, or tas project save %s force\n",
			name, name, name));
		return;
	}
	if (attached && name == tasp_name[s] && head < e.tasp_filehead && !force)
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: %s has ticks to %.0f and you are at %.0f; saving would cut them. Save under a new name, or tas project save %s force\n",
			name, e.tasp_filehead, head, name));
		return;
	}
	if (!exists && SV_TASPCount() >= TASP_FILES)
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: %.0f projects on this map is the limit\n", TASP_FILES));
		return;
	}
	if (!SV_TASPIdentityOK(e)) return;   // before a base save exists (P1089 review 4)
	if (!SV_SaveLocRate(e)) return;
	name = strzone(name);
	if (!attached)
	{
		B = SV_TASPOldestBase(e, head);
		if (B < 0 || B >= head)
		{
			sprint(e, PRINT_HIGH, "tas project: no retained exact tick to start a project from\n");
			strunzone(name); return;
		}
		m = rw_slot[s];
		bo = [m[rw_statebase+1], m[rw_statebase+2], m[rw_statebase+3]];
		bv = [m[rw_statebase+4], m[rw_statebase+5], m[rw_statebase+6]];
		// Every input first: a refusal must not leave a base save behind.
		fork = (tasp_name[s] != "" && name != tasp_name[s]);   // tasp_on is down after a failed try
		prev = e.tasp_rev;
		parent = strzone(fork ? tasp_name[s] : tasp_parent[s]);
		if (tasp_buf[s]) memfree(tasp_buf[s]);
		if (tasp_cp[s]) memfree(tasp_cp[s]);
		tasp_buf[s] = 0; tasp_cp[s] = 0;
		e.tasp_n = e.tasp_cap = e.tasp_ncp = 0;
		if (tasp_cpnames[s]) strunzone(tasp_cpnames[s]);
		tasp_cpnames[s] = "";
		e.tasp_on = 0;
		e.tasp_base = B; e.tasp_synced = B; e.tasp_rev = 0;
		SV_TASPAnchorLine(e, m[rw_statebase + 29], FALSE);
		if (!SV_TASPHarvest(e, s, head))
		{
			sprint(e, PRINT_HIGH, sprintf("tas project: cannot save: %s; nothing written\n", tasp_why));
			e.tasp_rev = prev; strunzone(name); strunzone(parent); SV_TASProjectEvent(e); return;
		}
		oldidx = e.rec_sl_index;
		if (!SV_SaveLocCreateAtMode(e, B, '0 0 0', FALSE, FALSE, FALSE, 2))
		{
			e.tasp_rev = prev; strunzone(name); strunzone(parent); SV_TASProjectEvent(e); return;
		}
		id = rec_sl_id[SL_Base(SL_Blk(e)) + e.rec_sl_index - 1];
		if (oldidx >= 1) e.rec_sl_index = oldidx;   // keep the player's own cursor
		hash = SV_TASPStateHash(id);
		if (hash == "" || !(tasp_hflags & TF_TAS))
		{
			sprint(e, PRINT_HIGH, sprintf("tas project: save #%.0f did not read back as a TAS save; project not written\n", id));
			e.tasp_rev = prev; strunzone(name); strunzone(parent); SV_TASProjectEvent(e); return;
		}
		e.tasp_baseid = id; e.tasp_bo = bo; e.tasp_bv = bv;
		if (fork) e.tasp_parentrev = prev;   // only once the new project exists
		if (tasp_hash[s]) strunzone(tasp_hash[s]);
		tasp_hash[s] = strzone(hash);
		e.tasp_serial = e.rec_rec_serial;
	}
	else
	{
		parent = strzone(name != tasp_name[s] ? tasp_name[s] : tasp_parent[s]);
		if (!SV_TASPHarvest(e, s, head))
		{
			sprint(e, PRINT_HIGH, sprintf("tas project: cannot save: %s; nothing written\n", tasp_why));
			strunzone(name); strunzone(parent); return;
		}
		if (name != tasp_name[s]) { e.tasp_parentrev = e.tasp_rev; e.tasp_rev = 0; }
	}
	e.tasp_n = head - e.tasp_base;
	SV_TASPCheckpoints(e, s, head);
	e.tasp_rev = e.tasp_rev + 1;
	if (tasp_name[s]) strunzone(tasp_name[s]);
	tasp_name[s] = name;
	if (tasp_parent[s]) strunzone(tasp_parent[s]);
	tasp_parent[s] = parent;
	// P1090 reviews 1-2: the last revision stays the parent through a detach or a close in its
	// own attempt (P1089 review 1 cleared it on any detach, which made a stopped load's rows a root's).
	if (e.tasp_lineserial != e.rec_rec_serial && tasp_revsha[s] != "")
	{
		strunzone(tasp_revsha[s]); tasp_revsha[s] = "";
	}
	SV_TASPSupply(e, s, head);
	if (!SV_TASPWrite(e, s, name, parent))
	{
		sprint(e, PRINT_HIGH, "tas project: cannot write the project file\n");
		e.tasp_rev = oldrev; e.tasp_on = 0; SV_TASProjectEvent(e); return;
	}
	e.tasp_on = 1; e.tasp_synced = head; e.tasp_lasthead = head; e.tasp_filehead = head;
	e.tasp_result = 0; e.tasp_dev = e.tasp_devtick = 0;
	e.tasp_cut = 16000001; e.tasp_gen = e.rec_rec_gen;
	SV_TASPParentKeep(e, s);
	if (!SV_TASPKeep(SV_TASPPath(name), tasp_revsha[s], FALSE, FALSE))
		sprint(e, PRINT_HIGH, "tas project: could not keep this revision under its hash; Sign will try again\n");
	// Only the host's own client marks a revision as made here (a guest's save shares this folder).
	if (strstrofs(infokey(e, "ip"), "LoopBack", 0) >= 0 && !SV_TASPFileIs(SV_TASPRevPath(tasp_revsha[s], "made")))
	{
		f = fopen(SV_TASPRevPath(tasp_revsha[s], "made"), FILE_WRITE);
		if (f >= 0) { fputs(f, "saved here\n"); fclose(f); }
	}
	e.tasp_made = SV_TASPFileIs(SV_TASPRevPath(tasp_revsha[s], "made"));
	e.tasp_signed = SV_TASPSignedFor(tasp_revsha[s]);
	sprint(e, PRINT_HIGH, sprintf("tas project: saved %s rev %.0f: base save #%.0f at tick %.0f, inputs to tick %.0f, %.0f checkpoints\n",
		name, e.tasp_rev, e.tasp_baseid, e.tasp_base, head, e.tasp_ncp));
	SV_TASPSupplyNote(e);
	SV_TASProjectEvent(e);
};

// Names are zoned copies owned by the caller.
void(entity e, string name, string cpname) SV_TASProjectLoad =
{
	local float s, row, r, stop, k, named, bad;
	local vector d, dv;

	s = SV_TASPSlot(e);
	if (!s || !SV_TASPLocalOnly(e)) return;
	if (!e.run_tas_incap || !checkbuiltin(tas_input) || !checkbuiltin(tas_tape) || e.run_tas_ready != 1)
	{
		sprint(e, PRINT_HIGH, "tas project: needs the P1065 native TAS engine\n");
		return;
	}
	if (e.tasp_load || e.run_tas_pending || e.run_tas_replaystate == TAS_TAPE_ACTIVE)
	{
		sprint(e, PRINT_HIGH, "tas project: wait for queued TAS work first\n");
		return;
	}
	if (!SV_TASPRead(e, name, TRUE))
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: cannot load %s: %s; nothing changed\n", name, tpr_why));
		return;
	}
	// P1100: a legal start has no base save; it never takes the base-save path below.
	if (tpr_ver == TASP_LEGAL) { SV_TASLegalLoad(e, name, cpname); return; }
	e.tasp_legal = 0;
	stop = tpr_base + tpr_n;
	if (cpname != "")
	{
		k = SV_TASPNameIndex(tpr_cpnames, cpname);
		stop = -1; named = 0;
		if (k >= 0)
		for (row = 0; row < tpr_ncp; row = row + 1)
			if (tpr_cp[row * TASP_CPSTRIDE + 1])
			{
				if (named == k) { stop = tpr_cp[row * TASP_CPSTRIDE]; break; }
				named = named + 1;
			}
		if (stop < 0)
		{
			sprint(e, PRINT_HIGH, sprintf("tas project: %s has no checkpoint %s; nothing changed\n", name, cpname));
			SV_TASPReadFree(); return;
		}
	}
	// Every check the save row allows before anything moves: present, unchanged, TAS, the
	// base's tick and (within state.txt's rounding) its position and velocity.
	if (!SV_SaveLocBegin(e, TRUE)) { SV_TASPReadFree(); return; }
	row = SV_TASPRow(e, tpr_baseid);
	r = SL_Base(SL_Blk(e)) + row - 1;
	bad = (!row);
	if (!bad) bad = (SV_TASPStateHash(tpr_baseid) != tpr_hash || !(tasp_hflags & TF_TAS) || rec_sl_tick[r] != tpr_base);
	if (!bad)
	{
		d = rec_sl_org[r] - tpr_bo; dv = rec_sl_vel[r] - tpr_bv;
		bad = (fabs(d_x) > 0.0002 || fabs(d_y) > 0.0002 || fabs(d_z) > 0.0002 ||
			fabs(dv_x) > 0.0002 || fabs(dv_y) > 0.0002 || fabs(dv_z) > 0.0002);
	}
	if (bad)
	{
		sprint(e, PRINT_HIGH, sprintf("tas project: the base save #%.0f of %s is missing or changed; nothing changed\n", tpr_baseid, name));
		SV_TASPReadFree(); return;
	}
	if (!SV_SaveLocRate(e)) { SV_TASPReadFree(); return; }
	SV_TASCancel(e);
	e.rec_sl_index = row;
	SV_SaveLocGo(e);
	if (FS_SlopOp(e.rec_sl_slop) != SLOP_LOADED || !e.rec_sl_hold)
	{
		sprint(e, PRINT_HIGH, "tas project: the base save did not load\n");
		SV_TASPReadFree(); return;
	}
	SV_SaveLocRelease(e);
	d = e.origin - tpr_bo; dv = e.velocity - tpr_bv;
	if (SV_TimerTicks(e) != tpr_base || e.run_t_state != TS_RUNNING || !(e.run_t_flags & TF_RECORDING) ||
		fabs(d_x) > 0.0002 || fabs(d_y) > 0.0002 || fabs(d_z) > 0.0002 ||
		fabs(dv_x) > 0.0002 || fabs(dv_y) > 0.0002 || fabs(dv_z) > 0.0002)
	{
		sprint(e, PRINT_HIGH, "tas project: the base did not load as a running, recorded attempt at its state; not replaying\n");
		SV_TASPReadFree(); return;
	}
	// state.txt keeps 4 decimals; restore the exact floats (only a rounding-sized correction).
	setorigin(e, tpr_bo);
	e.velocity = tpr_bv;
	// P1085: the base is a native checkpoint, so never mid func_bhop dwell (see SV_TASGo).
	e.vbsp_bhop_on = world; e.vbsp_bhop_since = 0;
	SV_TASHistoryReset(e);
	SV_TASProjectReset(e);
	SV_TASMark(e);
	e.run_tas_mode = TRUE;
	e.run_tas_paused = TRUE; e.run_tas_pending = 0; e.run_tas_fault = 0;
	e.run_tas_seen = e.run_tas_done;
	if (e.run_tas_req < 16000000) e.run_tas_req = e.run_tas_req + 1;  // stale timeline pages refuse
	SV_TimerFreezeFrame(e);
	SV_RewindTASHead(e);
	tasp_buf[s] = tpr_buf; tasp_cp[s] = tpr_cp; tpr_buf = 0; tpr_cp = 0;
	tasp_name[s] = strzone(name);
	tasp_hash[s] = tpr_hash; tasp_parent[s] = tpr_parent; tasp_cpnames[s] = tpr_cpnames;
	tpr_hash = tpr_parent = tpr_cpnames = "";
	// P1089: the lineage continues from the content's own hash; the stated one only warns.
	tasp_revsha[s] = strzone(tpr_h);
	if (tpr_revsha != "" && tpr_revsha != tasp_revsha[s])
		sprint(e, PRINT_HIGH, "tas project: this file was changed after it was saved (its revsha does not match)\n");
	tasp_parsha[s] = tpr_parsha; tpr_parsha = "";   // P1090
	e.tasp_supa = tpr_supa; e.tasp_supb = tpr_supb;
	e.tasp_signed = SV_TASPSignedFor(tasp_revsha[s]);
	e.tasp_made = SV_TASPFileIs(SV_TASPRevPath(tasp_revsha[s], "made"));
	e.tasp_n = tpr_n; e.tasp_cap = tpr_size; e.tasp_ncp = tpr_ncp; e.tasp_rev = tpr_rev;
	e.tasp_base = tpr_base; e.tasp_baseid = tpr_baseid; e.tasp_bo = tpr_bo; e.tasp_bv = tpr_bv;
	e.tasp_on = 1; e.tasp_load = 1; e.tasp_stop = stop; e.tasp_cpi = 0;
	e.tasp_serial = e.rec_rec_serial; e.tasp_synced = tpr_base; e.tasp_lasthead = tpr_base;
	e.tasp_filehead = tpr_base + tpr_n;
	e.tasp_cut = stop;   // ticks after a checkpoint stop belong to the file's line, not this one
	e.tasp_gen = e.rec_rec_gen; e.tasp_parentrev = tpr_parentrev;
	SV_TASPReadFree();
	SV_TASPParentKeep(e, s);
	SV_TASPKeep(SV_TASPPath(name), tasp_revsha[s], FALSE, FALSE);
	// A body that was not in TAS mode could not have the rows checked before the load.
	bad = SV_TASPValidate(e, tasp_buf[s], e.tasp_n);
	if (bad) { SV_TASPAbort(e, sprintf("input row %.0f refused by the engine", bad)); return; }
	sprint(e, PRINT_HIGH, sprintf("tas project: loading %s rev %.0f from tick %.0f to %.0f\n", name, e.tasp_rev, e.tasp_base, stop));
	SV_TASProjectEvent(e);
	SV_TASProjectDrive(e);   // first chunk now: the release above settled the frame
};

// A project's row count from its header (`base` and `head` come within the first lines), or
// TASP_MAX when it cannot tell: an upper bound for budgeting strict reads.
float(string n) SV_TASPHeadRows =
{
	local filestream f;
	local string l;
	local float k, base, rows;
	f = fopen(SV_TASPPath(n), FILE_READ);
	if (f < 0) return 0;
	base = -1; rows = TASP_MAX;
	for (k = 0; k < 64; k = k + 1)
	{
		l = fgets(f);
		if (l == "") break;
		if (tokenize(l) == 4 && argv(0) == "base") base = stof(argv(3));
		else if (argv(0) == "head")
		{
			if (base >= 0 && stof(argv(1)) > base) rows = min(TASP_MAX, stof(argv(1)) - base);
			break;
		}
	}
	fclose(f);
	return rows;
};

void(entity e, string a, string b) SV_TASProjectDiff =
{
	local float *ab;
	local float an, abase, aid, j, first, diff, lo, hi, t;

	// P1090 review 5: two strict reads in one call cost about 570 counted ops a row each, and
	// past the runaway limit (100M) the server stops: about 87k rows each, any client's command.
	if (SV_TASPHeadRows(a) + SV_TASPHeadRows(b) > 120000)
	{
		sprint(e, PRINT_HIGH, "tas project diff: these two are too long to compare in one step\n");
		return;
	}
	if (!SV_TASPRead(e, a, FALSE)) { sprint(e, PRINT_HIGH, sprintf("tas project: %s: %s\n", a, tpr_why)); return; }
	ab = tpr_buf; tpr_buf = 0; an = tpr_n; abase = tpr_base; aid = tpr_baseid;
	SV_TASPReadFree();
	if (!SV_TASPRead(e, b, FALSE)) { memfree(ab); sprint(e, PRINT_HIGH, sprintf("tas project: %s: %s\n", b, tpr_why)); return; }
	if (abase != tpr_base || aid != tpr_baseid)
		sprint(e, PRINT_HIGH, sprintf("tas project diff: different bases (%s save #%.0f tick %.0f, %s save #%.0f tick %.0f); shared ticks compared\n",
			a, aid, abase, b, tpr_baseid, tpr_base));
	first = 0; diff = 0;
	lo = max(abase, tpr_base) + 1; hi = min(abase + an, tpr_base + tpr_n);
	for (t = lo; t <= hi; t = t + 1)
	{
		for (j = 0; j < TAS_INPUT_STRIDE; j = j + 1)
			if (ab[(t - abase - 1) * TAS_INPUT_STRIDE + j] != tpr_buf[(t - tpr_base - 1) * TAS_INPUT_STRIDE + j]) break;
		if (j < TAS_INPUT_STRIDE)
		{
			diff = diff + 1;
			if (!first) first = t;
		}
	}
	memfree(ab);
	sprint(e, PRINT_HIGH, sprintf("tas project diff %s %s: %.0f differing ticks, first at %.0f; ", a, b, diff, first));
	sprint(e, PRINT_HIGH, sprintf("%s ends at %.0f, %s at %.0f\n", a, abase + an, b, tpr_base + tpr_n));
	SV_TASPReadFree();
};

void(entity e) SV_TASProjectList =
{
	local searchhandle h;
	local float i, n;
	h = search_begin(sprintf("data/tasproj/%s/*.tasp", mapname), SL_NAMESORT, TRUE);
	n = (h < 0) ? 0 : search_getsize(h);
	sprint(e, PRINT_HIGH, sprintf("tas project: %.0f on %s\n", n, mapname));
	for (i = 0; i < n; i = i + 1)
		sprint(e, PRINT_HIGH, sprintf("  %s\n", search_getfilename(h, i)));
	if (h >= 0) search_end(h);
};

void(entity e, string sub, string a1, string a2, float argc) SV_TASCheckpointCommand =
{
	local float s, k, b, named, i;
	local string acc, nm;

	s = SV_TASPSlot(e);
	if (!e.tasp_on || e.tasp_load) { sprint(e, PRINT_HIGH, "tas cp: save or load a project first\n"); return; }
	if (e.tasp_legal) { sprint(e, PRINT_HIGH, "tas cp: named checkpoints on a legal start are not built yet\n"); return; }
	if (sub == "list" && argc == 3)
	{
		named = 0;
		for (i = 0; i < e.tasp_ncp; i = i + 1)
			if (tasp_cp[s][i * TASP_CPSTRIDE + 1])
			{
				sprint(e, PRINT_HIGH, sprintf("tas cp %s: tick %.0f\n", SV_TASPNameAt(tasp_cpnames[s], named), tasp_cp[s][i * TASP_CPSTRIDE]));
				named = named + 1;
			}
		return;
	}
	if (!((sub == "add" || sub == "del") && argc == 4 && SV_TASPNameOK(a1)))
	{
		sprint(e, PRINT_HIGH, "tas cp add name | del name | list\n");
		return;
	}
	k = SV_TASPNameIndex(tasp_cpnames[s], a1);
	if (sub == "del")
	{
		if (k < 0) { sprint(e, PRINT_HIGH, "tas cp: no such checkpoint\n"); return; }
		named = 0;
		for (i = 0; i < e.tasp_ncp; i = i + 1)
			if (tasp_cp[s][i * TASP_CPSTRIDE + 1])
			{
				if (named == k) { tasp_cp[s][i * TASP_CPSTRIDE + 1] = 0; break; }
				named = named + 1;
			}
		acc = "";
		for (i = 0; i < TASP_CPMAX; i = i + 1)
		{
			nm = SV_TASPNameAt(tasp_cpnames[s], i);
			if (nm == "") break;
			if (i != k) acc = strcat(acc, nm, ";");
		}
		strunzone(tasp_cpnames[s]); tasp_cpnames[s] = strzone(acc);
		sprint(e, PRINT_HIGH, sprintf("tas cp: removed %s (kept on disk until the next project save)\n", a1));
		return;
	}
	if (k >= 0) { sprint(e, PRINT_HIGH, "tas cp: that name is taken\n"); return; }
	if (!SV_TASInputReady(e)) return;
	b = SV_TimerTicks(e);
	if (b <= e.tasp_base) { sprint(e, PRINT_HIGH, "tas cp: the head is at the project base\n"); return; }
	if (!tasp_cp[s]) tasp_cp[s] = (float*)memalloc(TASP_CPMAX * TASP_CPSTRIDE * 4);
	if (!tasp_cp[s] || e.tasp_ncp >= TASP_CPMAX - 1) { sprint(e, PRINT_HIGH, "tas cp: checkpoint list full\n"); return; }
	for (i = 0; i < e.tasp_ncp; i = i + 1) if (tasp_cp[s][i * TASP_CPSTRIDE] >= b) break;
	if (i < e.tasp_ncp)
	if (tasp_cp[s][i * TASP_CPSTRIDE] == b && tasp_cp[s][i * TASP_CPSTRIDE + 1])
	{ sprint(e, PRINT_HIGH, "tas cp: this tick already has a named checkpoint\n"); return; }
	if (i >= e.tasp_ncp || tasp_cp[s][min(i, TASP_CPMAX - 1) * TASP_CPSTRIDE] != b)
	{
		for (k = e.tasp_ncp * TASP_CPSTRIDE - 1; k >= i * TASP_CPSTRIDE; k = k - 1)
			tasp_cp[s][k + TASP_CPSTRIDE] = tasp_cp[s][k];
		e.tasp_ncp = e.tasp_ncp + 1;
	}
	k = i * TASP_CPSTRIDE;
	tasp_cp[s][k] = b; tasp_cp[s][k+1] = 1;
	tasp_cp[s][k+2] = e.origin_x; tasp_cp[s][k+3] = e.origin_y; tasp_cp[s][k+4] = e.origin_z;
	tasp_cp[s][k+5] = e.velocity_x; tasp_cp[s][k+6] = e.velocity_y; tasp_cp[s][k+7] = e.velocity_z;
	named = 0;  // the new name's position among the named rows before it
	for (b = 0; b < i; b = b + 1) if (tasp_cp[s][b * TASP_CPSTRIDE + 1]) named = named + 1;
	acc = "";
	for (b = 0; b <= TASP_CPMAX; b = b + 1)
	{
		if (b == named) acc = strcat(acc, a1, ";");
		nm = SV_TASPNameAt(tasp_cpnames[s], b);
		if (nm == "") break;
		acc = strcat(acc, nm, ";");
	}
	if (tasp_cpnames[s]) strunzone(tasp_cpnames[s]);
	tasp_cpnames[s] = strzone(acc);
	sprint(e, PRINT_HIGH, sprintf("tas cp: %s at tick %.0f (written with the next project save)\n", a1, tasp_cp[s][k]));
};

// P1090: the host's own client's signature over the current revision. Not checked here (QC
// has no Ed25519; tools/tasrev.py does); the statement's other fields are the server's.
string(string path) SV_TASPFirstLine =
{
	local filestream f;
	local string l;
	f = fopen(path, FILE_READ);
	if (f < 0) return "";
	l = fgets(f);
	fclose(f);
	return l;
};

void(entity e, string sha, string par, string a, string b, string code, string pub, string sig) SV_TASProjectSigned =
{
	local float s;
	local filestream f;
	local string line, path;
	s = SV_TASPSlot(e);
	if (!s || !SV_TASPLocalOnly(e)) return;
	if (strstrofs(infokey(e, "ip"), "LoopBack", 0) < 0)
	{
		sprint(e, PRINT_HIGH, "tas project: only the host's own client keeps signatures here\n");
		return;
	}
	if (!e.tasp_on || sha != tasp_revsha[s] || e.tasp_supa <= 0)
	{
		sprint(e, PRINT_HIGH, "tas project: that is not the current revision, or it supplies nothing; nothing kept\n");
		return;
	}
	if (par != ((tasp_parsha[s] != "") ? tasp_parsha[s] : "-") || a != sprintf("%.0f", e.tasp_supa) || b != sprintf("%.0f", e.tasp_supb))
	{
		sprint(e, PRINT_HIGH, "tas project: the panel signed another claim than this revision's; nothing kept\n"); return;
	}
	if (!SV_TASPHex(code, 64) || !SV_TASPHex(pub, 64) || !SV_TASPHex(sig, 128))
	{
		sprint(e, PRINT_HIGH, "tas project: not a signature; nothing kept\n"); return;
	}
	if (!e.tasp_made)
	{
		sprint(e, PRINT_HIGH, "tas project: this revision was loaded, not saved here; edit and save to sign your changes\n"); return;
	}
	line = strzone(strcat(sprintf("tasrev 1 %s %s %s %.0f %.0f ", sha, (tasp_parsha[s] != "") ? tasp_parsha[s] : "-",
		infokey(world, "*mapcrc"), e.tasp_supa, e.tasp_supb), sprintf("%s %s %s", code, pub, sig)));
	path = strzone(SV_TASPStmtPath(sha, line));
	if (SV_TASPFirstLine(path) != line)
	{
		// One strict read per press at most (two can pass the runaway limit near 87k rows): a
		// kept copy that does not read back is replaced by a checked copy of the working copy,
		// if that file states this hash, and the next press checks it.
		if (!SV_TASPKeptOK(e, sha))
		{
			if (SV_TASPKeep(SV_TASPPath(tasp_name[s]), sha, TRUE, TRUE))
				sprint(e, PRINT_HIGH, "tas project: this revision's kept copy did not read back; it was kept again, press Sign again\n");
			else
				sprint(e, PRINT_HIGH, "tas project: this revision's kept copy did not read back, and the working copy is no longer it; nothing kept\n");
			strunzone(line); strunzone(path); return;
		}
		f = fopen(path, FILE_WRITE);
		if (f >= 0) { fputs(f, strcat(line, "\n")); fclose(f); }
		if (!SV_TASPLinesAre(path, 1, line))
		{
			fremove(path); strunzone(line); strunzone(path);
			sprint(e, PRINT_HIGH, "tas project: cannot write the signature file\n"); return;
		}
	}
	strunzone(line); strunzone(path);
	e.tasp_signed = 1;
	sprint(e, PRINT_HIGH, sprintf("tas project: signed %s rev %.0f, ticks %.0f..%.0f, key %s\n", tasp_name[s], e.tasp_rev,
		e.tasp_supa, e.tasp_supb, substring(pub, 0, 8)));
	SV_TASProjectEvent(e);
};

// P1090 review 2: closing keeps the lineage (the last revision's hash and rows) for the rest of
// this attempt, so a save after it is that revision's child, not a root claiming its rows.
void(entity e) SV_TASProjectClose =
{
	local float s, pb, pn, ls;
	local float *rows;
	local string sha;
	s = SV_TASPSlot(e);
	sha = tasp_revsha[s]; rows = tasp_pbuf[s];
	pb = e.tasp_pbase; pn = e.tasp_pn; ls = e.tasp_lineserial;
	tasp_revsha[s] = ""; tasp_pbuf[s] = 0;
	SV_TASProjectReset(e);
	tasp_revsha[s] = sha; tasp_pbuf[s] = rows;
	e.tasp_pbase = pb; e.tasp_pn = pn; e.tasp_lineserial = ls;
};

void(entity e, float argc, string action, string sub, string a1, string a2, string a3, string a4) SV_TASProjectArgs =
{
	if (action == "cp") { SV_TASCheckpointCommand(e, sub, a1, a2, argc); return; }
	if (sub == "save" && argc >= 3 && argc <= 5)
	{
		if (argc >= 4 && a1 != "force" && !SV_TASPNameOK(a1)) goto bad;
		if (argc == 5 && a2 != "force") goto bad;
		// P1100: in a legal-start session the project starts at the start zone, not a base save.
		if (SV_TASLegalValid(e))
		{
			if (a1 == "force") SV_TASProjectSaveLegal(e, "", TRUE);
			else SV_TASProjectSaveLegal(e, argc >= 4 ? a1 : "", argc == 5);
			return;
		}
		if (a1 == "force") SV_TASProjectSave(e, "", TRUE);
		else SV_TASProjectSave(e, argc >= 4 ? a1 : "", argc == 5);
		return;
	}
	if (sub == "load" && (argc == 4 || argc == 5) && SV_TASPNameOK(a1) && (argc == 4 || SV_TASPNameOK(a2)))
	{
		SV_TASProjectLoad(e, a1, argc == 5 ? a2 : "");
		return;
	}
	if (sub == "diff" && argc == 5 && SV_TASPNameOK(a1) && SV_TASPNameOK(a2)) { SV_TASProjectDiff(e, a1, a2); return; }
	if (sub == "list" && argc == 3) { SV_TASProjectList(e); return; }
	if (sub == "hash" && argc == 4 && SV_TASPNameOK(a1))    // P1089: only a file the reader accepts
	{
		if (SV_TASPRead(e, a1, TRUE))
		{
			sprint(e, PRINT_HIGH, sprintf("tas project hash %s: %s\n", a1, tpr_h));
			if (tpr_supa > 0) sprint(e, PRINT_HIGH, sprintf("tas project supply %s: ticks %.0f..%.0f, %s\n", a1, tpr_supa, tpr_supb,
				SV_TASPSignedFor(tpr_h) ? "signed" : "unsigned"));
			else sprint(e, PRINT_HIGH, sprintf("tas project supply %s: %s\n", a1, tpr_supa ? "not recorded (version 1)" : "none"));
		}
		else sprint(e, PRINT_HIGH, sprintf("tas project hash %s: refused: %s\n", a1, tpr_why));
		SV_TASPReadFree();
		return;
	}
	if (sub == "event" && argc == 3) { SV_TASProjectEvent(e); return; }  // the panel's quiet status
	if (sub == "close" && argc == 3 && !e.tasp_load)
	{
		SV_TASProjectClose(e);
		sprint(e, PRINT_HIGH, "tas project: detached; files and saves are kept\n");
		SV_TASProjectEvent(e);
		return;
	}
	if (sub == "status" && argc == 3)
	{
		if (e.tasp_on && e.tasp_legal)
		{
			sprint(e, PRINT_HIGH, sprintf("tas project: %s rev %.0f legal start zone %.0f, clock on tick %.0f, file to tick %.0f, ",
				tasp_name[SV_TASPSlot(e)], e.tasp_rev, e.tasp_lzone, e.tasp_lstartat, e.tasp_lhead));
			sprint(e, PRINT_HIGH, sprintf("loading %.0f, result %.0f dev %.6f\n", e.tasp_load, e.tasp_result, e.tasp_dev));
		}
		else if (e.tasp_on)
		{
			sprint(e, PRINT_HIGH, sprintf("tas project: %s rev %.0f base save #%.0f tick %.0f, file to %.0f, synced %.0f, ",
				tasp_name[SV_TASPSlot(e)], e.tasp_rev, e.tasp_baseid, e.tasp_base, e.tasp_filehead, e.tasp_synced));
			sprint(e, PRINT_HIGH, sprintf("%.0f checkpoints, loading %.0f, result %.0f dev %.6f at %.0f\n",
				e.tasp_ncp, e.tasp_load, e.tasp_result, e.tasp_dev, e.tasp_devtick));
		}
		else sprint(e, PRINT_HIGH, "tas project: none attached\n");
		SV_TASProjectEvent(e);
		return;
	}
:bad
	sprint(e, PRINT_HIGH, "tas project save [name] [force] | load name [checkpoint] | list | diff a b | status | close; names a-z 0-9 _ -\n");
};

// tas project ... | tas cp ...: arguments are zoned first; saves and project files tokenize.
void(entity e, float argc) SV_TASProjectCommand =
{
	local string action, sub, a1, a2, a3, a4, a5;
	if (!SV_TASPSlot(e)) return;
	if (time < e.tasp_next)
	{
		sprint(e, PRINT_HIGH, "tas project: one request at a time; try again\n");
		return;
	}
	e.tasp_next = time + 0.25;
	// P1090, from the panel: tas project signed <sha> <parent|-> <first> <last> <code> <pub> <sig>
	if (argc == 10 && argv(1) == "project" && argv(2) == "signed")
	{
		a1 = strzone(argv(3)); a2 = strzone(argv(4)); a3 = strzone(argv(5)); a4 = strzone(argv(6));
		action = strzone(argv(7)); sub = strzone(argv(8)); a5 = strzone(argv(9));
		SV_TASProjectSigned(e, a1, a2, a3, a4, action, sub, a5);
		strunzone(a1); strunzone(a2); strunzone(a3); strunzone(a4); strunzone(action); strunzone(sub); strunzone(a5);
		return;
	}
	action = strzone(argv(1)); sub = strzone(argv(2)); a1 = strzone(argv(3)); a2 = strzone(argv(4));
	a3 = strzone(argv(5)); a4 = strzone(argv(6));
	SV_TASProjectArgs(e, argc, action, sub, a1, a2, a3, a4);
	strunzone(action); strunzone(sub); strunzone(a1); strunzone(a2); strunzone(a3); strunzone(a4);
};
