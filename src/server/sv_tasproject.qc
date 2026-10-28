// P1082: TAS projects. A project = one ordinary TAS save (its base) + every input after it.
// Loading re-simulates from that save; checkpoint states say whether it reproduced. The engine
// keeps the connection's sub-tick ms carry into a replay, which QC cannot set (BACKLOG).
#define TASP_VERSION 1
#define TASP_MAX 96000          // ticks after the base, about 24 minutes at 15 ms
#define TASP_CPMAX 48           // checkpoints kept: auto, the head, named
#define TASP_CPEVERY 256        // auto spacing, doubled until about 32 fit
#define TASP_CPSTRIDE 8         // tick, named, origin xyz, velocity xyz
#define TASP_FILES 64           // projects per map

float *tasp_buf[FS_MAXPLAYERS + 1];      // inputs for ticks base+1.., TAS_INPUT_STRIDE each
float *tasp_cp[FS_MAXPLAYERS + 1];
string tasp_name[FS_MAXPLAYERS + 1], tasp_hash[FS_MAXPLAYERS + 1];
string tasp_parent[FS_MAXPLAYERS + 1], tasp_cpnames[FS_MAXPLAYERS + 1];
.float tasp_on, tasp_n, tasp_cap, tasp_base, tasp_baseid, tasp_rev, tasp_serial, tasp_synced;
.float tasp_lasthead, tasp_filehead, tasp_ncp, tasp_load, tasp_stop, tasp_chead, tasp_cbase;
.float tasp_ccount, tasp_cpi, tasp_dev, tasp_devtick, tasp_result, tasp_next;
.vector tasp_bo, tasp_bv;      // the base tick's exact origin and velocity (state.txt rounds)
.float tasp_line;              // recorder line after tick tasp_synced's `in` row, -1 unknown
.float tasp_linemt;            // that row's move counter, -1 when the next row starts a branch
.float tasp_cut;               // lowest tick a TAS go replaced since the last save/load
.float tasp_gen;               // rec_rec_gen as this project last saw it
.float tasp_parentrev;         // the parent project's revision when this one forked

// One file read into temporaries; a load installs them only after every check passed.
float *tpr_buf;
float *tpr_cp;
float tpr_n, tpr_size, tpr_base, tpr_baseid, tpr_rev, tpr_ncp, tpr_parentrev;
vector tpr_bo, tpr_bv;
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
	if (!s) return;
	if (tasp_buf[s]) memfree(tasp_buf[s]);
	if (tasp_cp[s]) memfree(tasp_cp[s]);
	tasp_buf[s] = 0; tasp_cp[s] = 0;
	if (tasp_name[s]) strunzone(tasp_name[s]);
	if (tasp_hash[s]) strunzone(tasp_hash[s]);
	if (tasp_parent[s]) strunzone(tasp_parent[s]);
	if (tasp_cpnames[s]) strunzone(tasp_cpnames[s]);
	tasp_name[s] = tasp_hash[s] = tasp_parent[s] = tasp_cpnames[s] = "";
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
	tpr_hash = tpr_parent = tpr_cpnames = "";
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

// Parse a project into tpr_*. Untrusted: every value is bounded; FALSE leaves tpr_why.
// `identity` also requires and compares the map, zone and movement-rule lines.
float(entity e, string name, float identity) SV_TASPRead =
{
	local filestream f;
	local string l, k, pin, hash, parent, names, z;
	local float argc, n, i, b, have, ended, named;

	SV_TASPReadFree();
	tpr_rev = tpr_base = tpr_baseid = tpr_parentrev = 0; tpr_why = "";
	f = fopen(SV_TASPPath(name), FILE_READ);
	if (f < 0) { tpr_why = "no such project on this map"; return FALSE; }
	tpr_cp = (float*)memalloc(TASP_CPMAX * TASP_CPSTRIDE * 4);
	if (!tpr_cp) { fclose(f); tpr_why = "out of memory"; return FALSE; }
	have = ended = n = 0;
	hash = parent = names = "";
	pin = SV_RecPinText(e, "*pmpin");
	while ((l = fgets(f)) != "")
	{
		argc = tokenize(l);
		if (argc < 1) continue;
		k = argv(0);
		if (ended) { tpr_why = "data after end"; break; }
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
				if (!SV_TASPNum(argv(i + 4), -1000000, 1000000, FALSE)) break;
				tpr_cp[b + 2 + i] = fs_tas_number;
			}
			if (i < 6) { tpr_why = "bad checkpoint state"; break; }
			tpr_ncp = tpr_ncp + 1;
			continue;
		}
		if (k == "tasproject") { if (argc != 2 || argv(1) != ftos(TASP_VERSION)) { tpr_why = "unknown project version"; break; } have = have | 1; continue; }
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
		if (k == "base")
		{
			// base <save folder id> <state.txt sha256> <tick>
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
			for (i = 0; i < 6; i = i + 1) if (!SV_TASPNum(argv(i + 1), -1000000, 1000000, FALSE)) break;
			if (i < 6) { tpr_why = "bad base state"; break; }
			tpr_bo = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
			tpr_bv = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
			have = have | 16;
			continue;
		}
		if (k == "revision") { if (argc != 2 || !SV_TASPNum(argv(1), 1, 16000000, TRUE)) { tpr_why = "bad revision"; break; } tpr_rev = fs_tas_number; continue; }
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
	if (tpr_why == "" && (have & 31) != 31) tpr_why = "missing header lines";
	if (tpr_why == "" && identity && (have & 224) != 224) tpr_why = "missing map, zone or movement-rule line";
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
		e.tasp_result = e.tasp_devtick ? 2 : 1;
		if (e.tasp_devtick)
			sprint(e, PRINT_HIGH, sprintf("tas project: loaded %s to tick %.0f; DIVERGED from its saved states at tick %.0f (max %.4f); paused\n",
				tasp_name[s], head, e.tasp_devtick, e.tasp_dev));
		else
			sprint(e, PRINT_HIGH, sprintf("tas project: loaded %s to tick %.0f; reproduced every saved state exactly; paused\n",
				tasp_name[s], head));
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

float(entity e, float s, string name, string parent) SV_TASPWrite =
{
	local filestream f;
	local float i, b, nm;
	f = fopen(SV_TASPPath(name), FILE_WRITE);
	if (f < 0) return FALSE;
	fputs(f, sprintf("tasproject %.0f\n", TASP_VERSION));
	fputs(f, sprintf("map %s\n", mapname));
	fputs(f, sprintf("mapcrc %s\n", infokey(world, "*mapcrc")));
	fputs(f, sprintf("zonecrc %s\n", zone_crc));
	fputs(f, sprintf("pmpin %s\n", SV_RecPinText(e, "*pmpin")));
	fputs(f, "assist tas\norigin local\n");
	fputs(f, sprintf("saved %s\n", strftime(FALSE, "%Y-%m-%dT%H:%M:%S")));
	fputs(f, sprintf("revision %.0f\n", e.tasp_rev));
	if (parent != "") fputs(f, sprintf("parent %s %.0f\n", parent, e.tasp_parentrev));
	fputs(f, sprintf("base %.0f %s %.0f\n", e.tasp_baseid, tasp_hash[s], e.tasp_base));
	fputs(f, sprintf("baseat %.9g %.9g %.9g ", e.tasp_bo_x, e.tasp_bo_y, e.tasp_bo_z));
	fputs(f, sprintf("%.9g %.9g %.9g\n", e.tasp_bv_x, e.tasp_bv_y, e.tasp_bv_z));
	fputs(f, sprintf("head %.0f\n", e.tasp_base + e.tasp_n));
	nm = 0;
	for (i = 0; i < e.tasp_ncp; i = i + 1)
	{
		b = i * TASP_CPSTRIDE;
		fputs(f, sprintf("cp %.0f %.0f %s ", tasp_cp[s][b], tasp_cp[s][b+1],
			tasp_cp[s][b+1] ? SV_TASPNameAt(tasp_cpnames[s], nm) : "-"));
		fputs(f, sprintf("%.9g %.9g %.9g %.9g %.9g %.9g\n",
			tasp_cp[s][b+2], tasp_cp[s][b+3], tasp_cp[s][b+4], tasp_cp[s][b+5], tasp_cp[s][b+6], tasp_cp[s][b+7]));
		if (tasp_cp[s][b+1]) nm = nm + 1;
	}
	for (i = 0; i < e.tasp_n; i = i + 1)
	{
		b = i * TAS_INPUT_STRIDE;
		fputs(f, sprintf("i %.0f %.0f %.0f %.0f %.0f %.0f %.0f\n", tasp_buf[s][b], tasp_buf[s][b+1], tasp_buf[s][b+2],
			tasp_buf[s][b+3], tasp_buf[s][b+4], tasp_buf[s][b+5], tasp_buf[s][b+6]));
	}
	fputs(f, sprintf("end %.0f\n", e.tasp_n));
	fclose(f);
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

// `name` is a zoned copy owned by the caller ("" = the attached project's).
void(entity e, string name, float force) SV_TASProjectSave =
{
	local float s, head, attached, B, id, t, exists, oldidx, row, fork, prev;
	local float *m;
	local string hash, parent;
	local vector bo, bv;

	s = SV_TASPSlot(e);
	if (!s || !SV_TASPLocalOnly(e) || !SV_TASInputReady(e)) return;
	if (e.tasp_load) { sprint(e, PRINT_HIGH, "tas project: a load is still running\n"); return; }
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
		fork = (e.tasp_on && name != tasp_name[s]);
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
			strunzone(name); strunzone(parent); return;
		}
		oldidx = e.rec_sl_index;
		if (!SV_SaveLocCreateAtMode(e, B, '0 0 0', FALSE, FALSE, FALSE, 2)) { strunzone(name); strunzone(parent); return; }
		id = rec_sl_id[SL_Base(SL_Blk(e)) + e.rec_sl_index - 1];
		if (oldidx >= 1) e.rec_sl_index = oldidx;   // keep the player's own cursor
		hash = SV_TASPStateHash(id);
		if (hash == "" || !(tasp_hflags & TF_TAS))
		{
			sprint(e, PRINT_HIGH, sprintf("tas project: save #%.0f did not read back as a TAS save; project not written\n", id));
			strunzone(name); strunzone(parent); return;
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
	if (!SV_TASPWrite(e, s, name, parent))
	{
		sprint(e, PRINT_HIGH, "tas project: cannot write the project file\n");
		e.tasp_on = 0; return;
	}
	e.tasp_on = 1; e.tasp_synced = head; e.tasp_lasthead = head; e.tasp_filehead = head;
	e.tasp_result = 0; e.tasp_dev = e.tasp_devtick = 0;
	e.tasp_cut = 16000001; e.tasp_gen = e.rec_rec_gen;
	sprint(e, PRINT_HIGH, sprintf("tas project: saved %s rev %.0f: base save #%.0f at tick %.0f, inputs to tick %.0f, %.0f checkpoints\n",
		name, e.tasp_rev, e.tasp_baseid, e.tasp_base, head, e.tasp_ncp));
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
	// P1085: a save holds no func_bhop dwell; start every load at none, not at the last one.
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
	e.tasp_n = tpr_n; e.tasp_cap = tpr_size; e.tasp_ncp = tpr_ncp; e.tasp_rev = tpr_rev;
	e.tasp_base = tpr_base; e.tasp_baseid = tpr_baseid; e.tasp_bo = tpr_bo; e.tasp_bv = tpr_bv;
	e.tasp_on = 1; e.tasp_load = 1; e.tasp_stop = stop; e.tasp_cpi = 0;
	e.tasp_serial = e.rec_rec_serial; e.tasp_synced = tpr_base; e.tasp_lasthead = tpr_base;
	e.tasp_filehead = tpr_base + tpr_n;
	e.tasp_cut = stop;   // ticks after a checkpoint stop belong to the file's line, not this one
	e.tasp_gen = e.rec_rec_gen; e.tasp_parentrev = tpr_parentrev;
	SV_TASPReadFree();
	// A body that was not in TAS mode could not have the rows checked before the load.
	bad = SV_TASPValidate(e, tasp_buf[s], e.tasp_n);
	if (bad) { SV_TASPAbort(e, sprintf("input row %.0f refused by the engine", bad)); return; }
	sprint(e, PRINT_HIGH, sprintf("tas project: loading %s rev %.0f from tick %.0f to %.0f\n", name, e.tasp_rev, e.tasp_base, stop));
	SV_TASProjectEvent(e);
	SV_TASProjectDrive(e);   // first chunk now: the release above settled the frame
};

void(entity e, string a, string b) SV_TASProjectDiff =
{
	local float *ab;
	local float an, abase, aid, j, first, diff, lo, hi, t;

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

void(entity e, float argc, string action, string sub, string a1, string a2) SV_TASProjectArgs =
{
	if (action == "cp") { SV_TASCheckpointCommand(e, sub, a1, a2, argc); return; }
	if (sub == "save" && argc >= 3 && argc <= 5)
	{
		if (argc >= 4 && a1 != "force" && !SV_TASPNameOK(a1)) goto bad;
		if (argc == 5 && a2 != "force") goto bad;
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
	if (sub == "event" && argc == 3) { SV_TASProjectEvent(e); return; }  // the panel's quiet status
	if (sub == "close" && argc == 3 && !e.tasp_load)
	{
		SV_TASProjectReset(e);
		sprint(e, PRINT_HIGH, "tas project: detached; files and saves are kept\n");
		SV_TASProjectEvent(e);
		return;
	}
	if (sub == "status" && argc == 3)
	{
		if (e.tasp_on)
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
	local string action, sub, a1, a2;
	if (!SV_TASPSlot(e)) return;
	if (time < e.tasp_next)
	{
		sprint(e, PRINT_HIGH, "tas project: one request at a time; try again\n");
		return;
	}
	e.tasp_next = time + 0.25;
	action = strzone(argv(1)); sub = strzone(argv(2)); a1 = strzone(argv(3)); a2 = strzone(argv(4));
	SV_TASProjectArgs(e, argc, action, sub, a1, a2);
	strunzone(action); strunzone(sub); strunzone(a1); strunzone(a2);
};
