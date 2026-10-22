// Patch 915: private stage archive rows, over the existing savesync transport.
// Handles belong to one connection/query for 60s; no request accepts a path.
#define AR_EV_ROW 40
#define AR_EV_END 41
#define AR_EV_DATA 42
#define AR_ROWS 128
#define AR_BYTES 8388608
.float ar_search, ar_scan, ar_listing, ar_rate, ar_rows, ar_query, ar_until, ar_fh, ar_size, ar_seq, ar_next, ar_deadline, ar_transfer;
.string ar_identity, ar_scratch;
float ar_checked_size;

// Lobbies share data/. Pin this transfer's port/query/generation namespace.
string(entity e) Archive_Scratch =
{
	local float port;
	if (!strcmp(e.ar_scratch, ""))
	{
		port = cvar("sv_port");
		if (!(port >= 1 && port <= 65535 && port == floor(port))) return "";
		e.ar_scratch = strzone(sprintf("data/parts/owner-archive-p%d-%d-%d-%d.rec",
		                               port, num_for_edict(e), e.ar_query, e.ar_transfer));
	}
	return e.ar_scratch;
};

void(entity e) Archive_Close =
{
	if (e.ar_fh > 0) fclose(e.ar_fh - 1);
	e.ar_fh = 0;
	if (strcmp(e.ar_scratch, ""))
	{
		fremove(e.ar_scratch);
		strunzone(e.ar_scratch);
		e.ar_scratch = "";
	}
};

void(entity e) Archive_Reset =
{
	if (e.ar_search > 0) search_end(e.ar_search - 1);
	Archive_Close(e);
	if (e.ar_rows > 0) buf_del(e.ar_rows);
	if (strcmp(e.ar_identity, "")) strunzone(e.ar_identity);
	e.ar_search = e.ar_listing = e.ar_rows = e.ar_query = e.ar_transfer = 0;
	e.ar_identity = "";
};

void(entity e, float ev) Archive_Event =
{
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, ev);
	WriteLong(MSG_MULTICAST, e.ar_query);
};

void(entity e) Archive_Send =
{
	msg_entity = e;
	multicast('0 0 0', SH_MC_ONE);
};

void(entity e, float status) Archive_End =
{
	Archive_Event(e, AR_EV_END);
	WriteLong(MSG_MULTICAST, e.ar_transfer);
	WriteByte(MSG_MULTICAST, status);
	Archive_Send(e);
};

string(string kind, void *data, int size) digest_ptr = #0:digest_ptr;

// GUIDs/userinfo and the eight-hex filename mark are NOT authentication.
// Account_ProvenKey is populated only by this connection's verified proof.
string(entity e) Archive_Identity =
{
	local string pub, id;
	pub = Account_ProvenKey(e);
	if (!SV_RecIsHex(pub, 64)) return "";
	id = strtolower(digest_hex("SHA256", "FTESurf owner-stage identity v1|", pub));
	if (!SV_RecIsHex(id, 64)) return "";
	return id;
};

string(string path) Archive_Digest =
{
	local float fh, size;
	local void *data;
	local string result;
	if (!checkbuiltin(digest_ptr)) return "";
	fh = fopen(path, FILE_READ);
	if (fh < 0) return "";
	size = fsize(fh);
	if (size < 1 || size > AR_BYTES) { fclose(fh); return ""; }
	data = memalloc((int)size);
	if (!data) { fclose(fh); return ""; }
	result = "";
	if (fread(fh, data, (int)size) == (int)size)
		result = strtolower(digest_ptr("SHA256", data, (int)size));
	memfree(data); fclose(fh);
	if (!SV_RecIsHex(result, 64)) return "";
	return result;
};

// Retention owns the recordings; discard only this module's orphan metadata.
void(string path) Archive_PruneSeals =
{
	local float h, i, fh;
	local string seal, record, version;
	h = search_begin(strcat(substring(path, 0, FS_LastOf(path, 47) + 1), "*.rec.owner"), 0, TRUE);
	if (h < 0) return;
	for (i = 0; i < search_getsize(h) && i < 4096; i = i + 1)
	{
		seal = search_getfilename(h, i);
		fh = fopen(seal, FILE_READ);
		if (fh < 0) continue;
		version = fgets(fh); fclose(fh);
		if (strcmp(version, "owner-stage-v2")) continue;
		record = substring(seal, 0, strlen(seal) - 6);
		fh = fopen(record, FILE_READ);
		if (fh >= 0) fclose(fh);
		else fremove(seal);
	}
	search_end(h);
};

// Server-private adjacent metadata, never included in a list or transfer.
// A failed seal leaves the original stage intact but grants no retrieval.
void(entity e, string path, float buf) Archive_Seal =
{
	local string id, hash, content, partial;
	local float fh, size, n, i, actual;
	id = Archive_Identity(e);
	if (!strcmp(id, "") || buf < 1) return;
	id = strzone(id);
	n = buf_getsize(buf); size = 0;
	for (i = 0; i < n; i = i + 1)
	{
		size = size + strlen(bufstr_get(buf, i)) + 1;
		if (size > AR_BYTES) { strunzone(id); return; }
	}
	if (size < 1) { strunzone(id); return; }
	// Hash the actual writer-owned rows, not whoever later occupies a PB path.
	// One digest argument avoids the native variadic-string concatenation cap.
	bufstr_set(buf, n, "");
	content = buf_implode(buf, "\n");
	if (strlen(content) != size) { strunzone(id); return; }
	hash = strzone(strtolower(digest_hex("SHA256", content)));
	if (strcmp(hash, Archive_Digest(path))) { strunzone(hash); strunzone(id); return; }
	fh = fopen(path, FILE_READ);
	if (fh < 0) { strunzone(hash); strunzone(id); return; }
	actual = fsize(fh); fclose(fh);
	if (actual != size) { strunzone(hash); strunzone(id); return; }
	Archive_PruneSeals(path);
	partial = strzone(sprintf("%s.owner-p%d-%d.part", path, cvar("sv_port"), num_for_edict(e)));
	fh = fopen(partial, FILE_WRITE);
	if (fh >= 0)
	{
		fputs(fh, strcat("owner-stage-v2\n", id, "\n", hash, "\n"));
		fputs(fh, sprintf("%d\n", size));
		fputs(fh, strcat(digest_hex("SHA256", "FTESurf owner-stage path v1|", path), "\n"));
		fclose(fh);
		fremove(strcat(path, ".owner"));
		if (frename(partial, strcat(path, ".owner")) != 0) fremove(partial);
	}
	strunzone(partial); strunzone(hash); strunzone(id);
};

// One captured seal supplies identity/path AND the copied-content expectation.
string(entity e, string path) Archive_CheckedSeal =
{
	local float fh, size;
	local string id, version, owner, hash, binding;
	ar_checked_size = 0;
	id = Archive_Identity(e);
	if (!strcmp(id, "")) return "";
	fh = fopen(strcat(path, ".owner"), FILE_READ);
	if (fh < 0) return "";
	version = fgets(fh); owner = fgets(fh); hash = fgets(fh);
	size = stof(fgets(fh)); binding = fgets(fh); fclose(fh);
	if (strcmp(version, "owner-stage-v2") || strcmp(owner, id)) return "";
	if (strcmp(binding, digest_hex("SHA256", "FTESurf owner-stage path v1|", path))) return "";
	if (!SV_RecIsHex(hash, 64)) return "";
	if (!(size >= 1 && size <= AR_BYTES && size == floor(size))) return "";
	ar_checked_size = size;
	return hash;
};

// A full FILE_READ materializes into private memory on its first fread.
// Return that SAME verified handle; header consumers must not reopen the path.
float(entity e, string path) Archive_VerifiedOpen =
{
	local float fh, size, ok;
	local string hash;
	local void *data;
	if (!checkbuiltin(digest_ptr)) return -1;
	hash = Archive_CheckedSeal(e, path); size = ar_checked_size;
	if (!strcmp(hash, "")) return -1;
	hash = strzone(hash);
	fh = fopen(path, FILE_READ);
	if (fh < 0) { strunzone(hash); return -1; }
	if (fsize(fh) != size) { fclose(fh); strunzone(hash); return -1; }
	data = memalloc((int)size);
	if (!data) { fclose(fh); strunzone(hash); return -1; }
	ok = FALSE;
	if (fread(fh, data, (int)size) == (int)size)
		ok = !strcmp(hash, digest_ptr("SHA256", data, (int)size));
	memfree(data); strunzone(hash);
	if (!ok) { fclose(fh); return -1; }
	fseek(fh, 0i);
	return fh;
};

float(entity e, string path) Archive_Authorized =
{
	local float fh;
	fh = Archive_VerifiedOpen(e, path);
	if (fh < 0) return FALSE;
	fclose(fh);
	return TRUE;
};

// Pin and verify persisted bytes, never reopen a second unchecked owner seal.
float(entity e, string path) Archive_Snapshot =
{
	local float fh, out, size, wrote, ok;
	local void *data;
	local string hash, scratch;
	if (!checkbuiltin(digest_ptr)) return -1;
	hash = Archive_CheckedSeal(e, path); size = ar_checked_size;
	if (!strcmp(hash, "")) return -1;
	hash = strzone(hash);
	fh = fopen(path, FILE_READ);
	if (fh < 0) { strunzone(hash); return -1; }
	if (fsize(fh) != size) { fclose(fh); strunzone(hash); return -1; }
	data = memalloc((int)size);
	if (!data) { fclose(fh); strunzone(hash); return -1; }
	ok = FALSE;
	if (fread(fh, data, (int)size) == (int)size)
		ok = !strcmp(hash, digest_ptr("SHA256", data, (int)size));
	fclose(fh);
	out = -1;
	if (ok)
	{
		scratch = Archive_Scratch(e);
		if (strcmp(scratch, "")) out = fopen(scratch, FILE_WRITE);
		if (out >= 0)
		{
			wrote = (fwrite(out, data, (int)size) == (int)size);
			fclose(out); out = -1;
			if (wrote) out = fopen(scratch, FILE_READ);
			if (out >= 0)
			{
				ok = FALSE;
				if (fsize(out) == size)
				if (fread(out, data, (int)size) == (int)size)
					ok = !strcmp(hash, digest_ptr("SHA256", data, (int)size));
				if (ok) { fseek(out, 0i); e.ar_size = size; }
				else { fclose(out); out = -1; }
			}
		}
	}
	memfree(data); strunzone(hash);
	if (out < 0) Archive_Close(e);
	return out;
};

float(entity e, string fn) Archive_Row =
{
	local float fh, j, flags, version, row;
	local string leaf, line, owner, date;
	fn = strzone(fn);
	fh = Archive_VerifiedOpen(e, fn);
	if (fh < 0) { strunzone(fn); return FALSE; }
	flags = -1; version = 0; owner = date = "";
	for (j = 0; j < 48; j = j + 1)
	{
		line = fgets(fh);
		if (!line || !strcmp(line, "begin")) break;
		tokenize(line);
		if (!strcmp(argv(0), "flags")) flags = stof(argv(1));
		if (!strcmp(argv(0), "FTESURF-REC")) version = stof(argv(1));
		if (!strcmp(argv(0), "owner")) owner = substring(line, 6, 120);
		if (!strcmp(argv(0), "runid")) date = substring(argv(1), 0, 15);
	}
	fclose(fh);
	if (flags < 0 || FS_RunClass(flags) != RC_CLEAN || version != 5)
	{
		strunzone(fn); return FALSE;
	}
	row = buf_getsize(e.ar_rows) + 1;
	bufstr_set(e.ar_rows, row - 1, fn);
	leaf = substring(fn, FS_LastOf(fn, 47) + 1, strlen(fn));
	Archive_Event(e, AR_EV_ROW);
	WriteShort(MSG_MULTICAST, row);
	WriteString(MSG_MULTICAST, leaf);
	WriteString(MSG_MULTICAST, owner);
	WriteString(MSG_MULTICAST, date);
	WriteLong(MSG_MULTICAST, flags);
	Archive_Send(e);
	strunzone(fn);
	return TRUE;
};

void(entity e, float query, float track, float leg) Archive_List =
{
	local float h;
	local string id;
	Archive_Reset(e);
	e.ar_query = query;
	id = Archive_Identity(e);
	if (!Lobby_Active() || !strcmp(id, "") || leg < 1 || leg > 128 || track < 0 || track > 64)
	{
		Archive_End(e, 1);
		return;
	}
	e.ar_identity = strzone(id);
	e.ar_rows = buf_create_ex("string", 0);
	if (e.ar_rows < 1) { Archive_End(e, 2); return; }
	e.ar_until = time + 60;
	h = search_begin(strcat(FS_RunDir(mapname, track, leg), "*.rec"), FS_NAMESORT, TRUE);
	e.ar_search = h + 1;
	e.ar_scan = 0;
	e.ar_listing = 1;
};

void(entity e, float row) Archive_Get =
{
	local float fh;
	Archive_Close(e);
	if (!e.ar_rows || e.ar_listing || time > e.ar_until || row < 1 || row > buf_getsize(e.ar_rows))
	{
		Archive_End(e, 2);
		return;
	}
	if (!strcmp(bufstr_get(e.ar_rows, row - 1), "")) { Archive_End(e, 2); return; }
	fh = Archive_Snapshot(e, bufstr_get(e.ar_rows, row - 1));
	if (fh < 0) { Archive_End(e, 2); return; }
	if (fsize(fh) != e.ar_size || e.ar_size < 1 || e.ar_size > AR_BYTES)
	{
		fclose(fh); Archive_Close(e); Archive_End(e, 2); return;
	}
	e.ar_fh = fh + 1;
	e.ar_seq = 0;
	e.ar_next = time;
	e.ar_deadline = time + 600;
};

void(entity e, float argc) Archive_Command =
{
	local string verb;
	local float query, track, leg, row, transfer;
	verb = argv(1); query = stof(argv(2)); track = stof(argv(3)); leg = stof(argv(4)); row = track; transfer = leg;
	if (clienttype(e) != CLIENTTYPE_REAL) return;
	if (!(query >= 1 && query <= 16000000 && query == floor(query))) return;
	if (!strcmp(verb, "list") && argc == 5)
	{
		if (time < e.ar_until - 58)
		{
			WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
			WriteByte(MSG_MULTICAST, AR_EV_END);
			WriteLong(MSG_MULTICAST, query);
			WriteLong(MSG_MULTICAST, 0);
			WriteByte(MSG_MULTICAST, 3);
			Archive_Send(e);
			return;
		}
		if (track != floor(track) || leg != floor(leg)) return;
		Archive_List(e, query, track, leg);
		return;
	}
	if (query != e.ar_query) return;
	if (strcmp(e.ar_identity, Archive_Identity(e))) { Archive_Reset(e); return; }
	if (!strcmp(verb, "get") && argc == 5 && row == floor(row))
	{
		if (!(transfer >= 1 && transfer <= 16000000 && transfer == floor(transfer))) return;
		if (transfer <= e.ar_transfer) return;
		Archive_Close(e); e.ar_transfer = transfer;
		if (time < e.ar_rate) { Archive_End(e, 2); return; }
		e.ar_rate = time + 0.2;
		Archive_Get(e, row);
	}
	if (!strcmp(verb, "cancel")) Archive_Reset(e);
};

void() Archive_Frame =
{
	local entity e;
	local float fh, i, pos, done, h;
	local string data, line, path;
	e = world;
	while ((e = findfloat(e, acct_here, TRUE)))
	{
		if (!e.ar_rows) continue;
		if (strcmp(e.ar_identity, Archive_Identity(e))) { Archive_Reset(e); continue; }
		if (e.ar_listing)
		{
			h = e.ar_search - 1;
			for (i = 0; i < 8 && e.ar_listing; i = i + 1)
			{
				if (h < 0 || e.ar_scan >= 4096 || buf_getsize(e.ar_rows) >= AR_ROWS)
				{
					if (h >= 0) search_end(h);
					e.ar_search = e.ar_listing = 0;
					Archive_End(e, 0); break;
				}
				if (e.ar_scan >= search_getsize(h))
				{
					search_end(h); e.ar_search = e.ar_listing = 0;
					Archive_End(e, 0); break;
				}
				path = search_getfilename(h, e.ar_scan);
				e.ar_scan = e.ar_scan + 1;
				if (!Archive_Row(e, path)) continue;
				break; // at most one owner row/hash per client/frame
			}
			continue;
		}
		if (!e.ar_fh)
		{
			if (time > e.ar_until) Archive_Reset(e);
			continue;
		}
		if (time < e.ar_next) continue;
		if (time > e.ar_deadline) { Archive_End(e, 2); Archive_Reset(e); continue; }
		fh = e.ar_fh - 1; data = ""; done = 0;
		for (i = 0; i < 16; i = i + 1)
		{
			pos = fseek(fh);
			if (pos >= e.ar_size) { done = 1; break; }
			line = fgets(fh);
			if (strlen(line) > 880) { done = 2; break; }
			if (strlen(data) + strlen(line) + 1 > 900) { fseek(fh, (int)pos); break; }
			data = strcat(data, line, "\n");
		}
		if (done == 2) { Archive_End(e, 2); Archive_Reset(e); continue; }
		Archive_Event(e, AR_EV_DATA);
		WriteLong(MSG_MULTICAST, e.ar_transfer);
		WriteLong(MSG_MULTICAST, e.ar_size);
		WriteLong(MSG_MULTICAST, e.ar_seq);
		WriteByte(MSG_MULTICAST, done);
		WriteString(MSG_MULTICAST, data);
		Archive_Send(e);
		e.ar_seq = e.ar_seq + 1;
		e.ar_next = time + 0.05;
		if (done) Archive_Close(e);
	}
};
