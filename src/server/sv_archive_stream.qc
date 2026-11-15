// P1568: bounded owner Archive v2. Legacy clients retain the original 8MiB arm.
#define AR_EV_PROGRESS 44
#define AR_EV_STREAM 45
#define AR2_QUERY_WORK 262144i
#define AR2_WIN 8
#define AR2_PENDING "owner-stage-pending-v1"

.float ar2_mode, ar2_phase, ar2_rfh, ar2_wfh, ar2_hfh, ar2_sendfh, ar2_progress, ar2_ack;
.int ar2_size, ar2_copyat, ar2_hashat, ar2_bytes;
.string ar2_source, ar2_scratch, ar2_expected, ar2_digest, ar2_map, ar2_profile;
.float ar2_pending;

.float ar2_jobfh;
.int ar2_jobsize;
.string ar2_jobpath, ar2_jobid;
.entity ar2_jobnext;
entity ar2_jobs_first, ar2_jobs_last;
float ar2_jobs_count;
int ar2_work;
int ar2_checked_size;
string ar2_checked_hash;
float ar2_checked_pending;

string(string path) Ar2_PathKey =
{
	return digest_hex("SHA256", "FTESurf owner-stage path v1|", path);
};

string(string path, int size, string id) Ar2_PendingKey =
{
	return digest_hex("SHA256", AR2_PENDING, "|", id, "|", path, "|", itos(size));
};

float(string path, int size, string id) Ar2_Pending;

// Only a successful writer-completion hook creates this private ownership
// promise. It grants no retrieval/native trust; a full digest is still needed.
float(string path, int size, string id) Ar2_WritePending =
{
	local float fh, status;
	local string tmp;
	if (!SV_RecIsHex(id, 64) || size < 1i || size > FS_ARCHIVE_BYTES) return FALSE;
	if (FS_WritePathStatus(strcat(path, ".owner")) != 0) return FALSE;
	status = FS_WritePathStatus(strcat(path, ".owner.pending"));
	if (status == 1) return Ar2_Pending(path, size, id);
	if (status != 0) return FALSE;
	tmp = strzone(strcat(path, ".owner.pending.part"));
	if (FS_WritePathStatus(tmp) != 0) { strunzone(tmp); return FALSE; }
	fh = fopen(tmp, FILE_WRITE);
	if (fh < 0) { strunzone(tmp); return FALSE; }
	fputs(fh, strcat(AR2_PENDING, "\n", id, "\n", itos(size), "\n"));
	fputs(fh, strcat(Ar2_PendingKey(path, size, id), "\n")); fclose(fh);
	if (FS_WritePathStatus(strcat(path, ".owner.pending")) != 0)
	{ fremove(tmp); strunzone(tmp); return FALSE; }
	if (frename(tmp, strcat(path, ".owner.pending")) != 0)
	{ fremove(tmp); strunzone(tmp); return FALSE; }
	strunzone(tmp);
	return Ar2_Pending(path, size, id);
};

float(string path, int size, string id) Ar2_Pending =
{
	local float fh, ok;
	local string version, owner, count, bind;
	fh = fopen(strcat(path, ".owner.pending"), FS_FILE_READSTREAM);
	if (fh < 0) return FALSE;
	version = strzone(fgets(fh)); owner = strzone(fgets(fh));
	count = strzone(fgets(fh)); bind = strzone(fgets(fh)); fclose(fh);
	ok = (!strcmp(version, AR2_PENDING) && !strcmp(owner, id)
		&& FS_ArchiveSize(count) == size && !strcmp(bind, Ar2_PendingKey(path, size, id)));
	strunzone(version); strunzone(owner); strunzone(count); strunzone(bind);
	return ok;
};

float(string path, int size, string id, string hash) Ar2_SealMatches =
{
	local float fh, ok;
	local string version, owner, count, digest, bind;
	fh = fopen(strcat(path, ".owner"), FS_FILE_READSTREAM);
	if (fh < 0) return FALSE;
	version = strzone(fgets(fh)); owner = strzone(fgets(fh)); digest = strzone(fgets(fh));
	count = strzone(fgets(fh)); bind = strzone(fgets(fh)); fclose(fh);
	ok = (!strcmp(version, "owner-stage-v2") && !strcmp(owner, id) && !strcmp(digest, hash)
		&& FS_ArchiveSize(count) == size && !strcmp(bind, Ar2_PathKey(path)));
	strunzone(version); strunzone(owner); strunzone(count); strunzone(bind); strunzone(digest);
	return ok;
};

float(string path, int size, string id, string hash) Ar2_Publish =
{
	local float fh;
	local string tmp;
	if (!SV_RecIsHex(id, 64) || !SV_RecIsHex(hash, 64) || size < 1i || size > FS_ARCHIVE_BYTES) return FALSE;
	if (FS_WritePathStatus(strcat(path, ".owner")) != 0) return FALSE;
	if (!Ar2_Pending(path, size, id)) return FALSE;
	tmp = strzone(strcat(path, ".owner.part"));
	if (FS_WritePathStatus(tmp) != 0) { strunzone(tmp); return FALSE; }
	fh = fopen(tmp, FILE_WRITE);
	if (fh < 0) { strunzone(tmp); return FALSE; }
	// Exactly the existing v2 seal: version, proven owner, full hash, size, path.
	fputs(fh, strcat("owner-stage-v2\n", id, "\n", hash, "\n", itos(size), "\n"));
	fputs(fh, strcat(Ar2_PathKey(path), "\n")); fclose(fh);
	if (FS_WritePathStatus(strcat(path, ".owner")) != 0)
	{ fremove(tmp); strunzone(tmp); return FALSE; }
	if (frename(tmp, strcat(path, ".owner")) != 0)
	{ fremove(tmp); strunzone(tmp); return FALSE; }
	strunzone(tmp);
	if (!Ar2_SealMatches(path, size, id, hash)) return FALSE;
	fremove(strcat(path, ".owner.pending"));
	return TRUE;
};

float(entity e, string path) Ar2_Authority =
{
	local float fh, ok;
	local int size;
	local __int64 disk;
	local string version, owner, count, hash, bind, id;
	ar2_checked_size = 0i; ar2_checked_pending = FALSE;
	if (strcmp(ar2_checked_hash, "")) strunzone(ar2_checked_hash);
	ar2_checked_hash = "";
	id = Archive_Identity(e);
	if (!SV_RecIsHex(id, 64) || strcmp(id, e.ar_identity)) return FALSE;
	id = e.ar_identity;
	fh = fopen(path, FS_FILE_READSTREAM);
	if (fh < 0) return FALSE;
	disk = FS_StreamSize(fh); fclose(fh);
	if (disk < (__int64)1i || disk > (__int64)FS_ARCHIVE_BYTES) return FALSE;
	size = (int)disk;
	if (FS_WritePathStatus(strcat(path, ".owner")) == 0)
	{
		if (!Ar2_Pending(path, size, id)) return FALSE;
		ar2_checked_size = size; ar2_checked_pending = TRUE;
		return TRUE;
	}
	fh = fopen(strcat(path, ".owner"), FS_FILE_READSTREAM);
	if (fh < 0) return FALSE;
	version = strzone(fgets(fh)); owner = strzone(fgets(fh)); hash = strzone(fgets(fh));
	count = strzone(fgets(fh)); bind = strzone(fgets(fh)); fclose(fh);
	ok = (!strcmp(version, "owner-stage-v2") && !strcmp(owner, id)
		&& FS_ArchiveSize(count) == size && SV_RecIsHex(hash, 64) && !strcmp(bind, Ar2_PathKey(path)));
	if (ok) { ar2_checked_size = size; ar2_checked_hash = strzone(hash); }
	strunzone(version); strunzone(owner); strunzone(count); strunzone(bind); strunzone(hash);
	return ok;
};

void(entity e) Ar2_Close =
{
	if (e.ar2_rfh > 0) fclose(e.ar2_rfh - 1);
	if (e.ar2_wfh > 0) fclose(e.ar2_wfh - 1);
	if (e.ar2_hfh > 0) fclose(e.ar2_hfh - 1);
	if (e.ar2_sendfh > 0) fclose(e.ar2_sendfh - 1);
	e.ar2_rfh = e.ar2_wfh = e.ar2_hfh = e.ar2_sendfh = e.ar2_phase = 0;
	if (strcmp(e.ar2_scratch, "")) { fremove(e.ar2_scratch); strunzone(e.ar2_scratch); }
	if (strcmp(e.ar2_source, "")) strunzone(e.ar2_source);
	if (strcmp(e.ar2_expected, "")) strunzone(e.ar2_expected);
	if (strcmp(e.ar2_digest, "")) strunzone(e.ar2_digest);
	e.ar2_scratch = e.ar2_source = e.ar2_expected = e.ar2_digest = "";
	e.ar2_size = e.ar2_copyat = e.ar2_hashat = e.ar2_bytes = 0i;
	e.ar2_pending = FALSE;
};

void(entity e) Archive_StreamReset =
{
	Ar2_Close(e);
	if (strcmp(e.ar2_map, "")) strunzone(e.ar2_map);
	if (strcmp(e.ar2_profile, "")) strunzone(e.ar2_profile);
	e.ar2_map = e.ar2_profile = ""; e.ar2_mode = e.ar2_progress = e.ar2_ack = 0;
};

float(entity e) Archive_StreamBusy = { return (e.ar2_phase != 0); };

void(entity job) Ar2_EndJob =
{
	if (job.ar2_jobfh > 0) fclose(job.ar2_jobfh - 1);
	ar2_jobs_first = job.ar2_jobnext;
	if (ar2_jobs_last == job) ar2_jobs_last = world;
	strunzone(job.ar2_jobpath); strunzone(job.ar2_jobid);
	ar2_jobs_count = ar2_jobs_count - 1; remove(job);
};

// One 64KiB step/frame. Map/queue overflow retains the private promise on disk
// for a future authenticated list2; never manufacture one for an older REC.
void() Ar2_SealFrame =
{
	local entity job;
	local float fh;
	local string hash;
	job = ar2_jobs_first;
	if (job == world) return;
	if (job.ar2_jobfh == 0)
	{
		if (!Ar2_Pending(job.ar2_jobpath, job.ar2_jobsize, job.ar2_jobid)) { Ar2_EndJob(job); return; }
		fh = fopen(job.ar2_jobpath, FS_FILE_READSTREAM);
		if (fh < 0) { Ar2_EndJob(job); return; }
		job.ar2_jobfh = fh + 1;
		if (FS_StreamSize(fh) != (__int64)job.ar2_jobsize) { Ar2_EndJob(job); return; }
	}
	hash = FS_FileSHA256Step(job.ar2_jobfh - 1, FS_ARCHIVE_WORK);
	if (!strcmp(hash, "")) return;
	if (SV_RecIsHex(hash, 64))
	{
		hash = strzone(hash); Ar2_Publish(job.ar2_jobpath, job.ar2_jobsize, job.ar2_jobid, hash); strunzone(hash);
	}
	Ar2_EndJob(job);
};

float(entity e, string path) Archive_StreamSealLarge =
{
	local float fh;
	local __int64 disk;
	local entity job, scan;
	local string id;
	if (!FS_StreamFiles()) return FALSE;
	fh = fopen(path, FS_FILE_READSTREAM);
	if (fh < 0) return TRUE;
	disk = FS_StreamSize(fh); fclose(fh);
	if (disk >= (__int64)1i && disk <= (__int64)8388608i) return FALSE;
	if (disk < (__int64)1i || disk > (__int64)FS_ARCHIVE_BYTES) return TRUE;
	id = strzone(Archive_Identity(e));
	if (!SV_RecIsHex(id, 64) || !Ar2_WritePending(path, (int)disk, id)) { strunzone(id); return TRUE; }
	for (scan = ar2_jobs_first; scan != world; scan = scan.ar2_jobnext)
		if (!strcmp(scan.ar2_jobpath, path)) { strunzone(id); return TRUE; }
	if (ar2_jobs_count >= 64) { strunzone(id); return TRUE; }
	job = spawn(); job.classname = "archive-seal-job";
	job.ar2_jobpath = strzone(path); job.ar2_jobid = id; job.ar2_jobsize = (int)disk;
	if (ar2_jobs_last != world) ar2_jobs_last.ar2_jobnext = job;
	else ar2_jobs_first = job;
	ar2_jobs_last = job; ar2_jobs_count = ar2_jobs_count + 1;
	return TRUE;
};

void(entity e) Ar2_Progress =
{
	if (time < e.ar2_progress) return;
	e.ar2_progress = time + 1;
	Archive_Event(e, AR_EV_PROGRESS);
	WriteLong(MSG_MULTICAST, e.ar_transfer); WriteByte(MSG_MULTICAST, e.ar2_phase);
	Archive_Send(e);
};

void(entity e, float status) Ar2_Fail =
{
	local float getting;
	getting = (e.ar2_phase == 2 || e.ar2_phase == 4 || e.ar2_sendfh > 0);
	Ar2_Close(e);
	if (getting) Archive_End(e, status);
};

float(entity e, string path, float getting) Ar2_Begin =
{
	local float fh;
	local string scratch;
	if (!Ar2_Authority(e, path)) return FALSE;
	e.ar2_size = ar2_checked_size; e.ar2_pending = ar2_checked_pending;
	e.ar2_expected = strzone(ar2_checked_hash); e.ar2_source = strzone(path);
	fh = fopen(path, FS_FILE_READSTREAM);
	if (fh < 0) { Ar2_Close(e); return FALSE; }
	e.ar2_rfh = fh + 1;
	if (FS_StreamSize(fh) != (__int64)e.ar2_size) { Ar2_Close(e); return FALSE; }
	scratch = strzone(sprintf("data/parts/p1568-archive-%d-%d-%d-%d-%d.rec",
		cvar("sv_port"), num_for_edict(e), e.ar_query, e.ar_transfer, e.ar_scan));
	if (FS_WritePathStatus(scratch) != 0) { strunzone(scratch); Ar2_Close(e); return FALSE; }
	fh = fopen(scratch, FS_FILE_WRITESTREAM);
	if (fh < 0) { strunzone(scratch); Ar2_Close(e); return FALSE; }
	e.ar2_scratch = scratch; e.ar2_wfh = fh + 1;
	e.ar2_phase = getting ? 2 : 1; e.ar2_progress = 0;
	e.ar2_copyat = e.ar2_hashat = 0i;
	return TRUE;
};

float(entity e, string path) Archive_StreamRow =
{
	if (!e.ar2_mode) return -1;
	Ar2_Begin(e, path, FALSE);
	return 0;
};

void(entity e) Ar2_RowReady =
{
	local float fh, j, flags, version, row;
	local string line, owner, date, leaf;
	fh = e.ar2_hfh - 1; fseek(fh, 0i);
	flags = -1; version = 0; owner = date = "";
	for (j = 0; j < 48; j = j + 1)
	{
		line = fgets(fh);
		if (!line || !strcmp(line, "begin")) break;
		tokenize(line);
		if (!strcmp(argv(0), "flags")) flags = stof(argv(1));
		if (!strcmp(argv(0), "FTESURF-REC")) version = stof(argv(1));
		if (!strcmp(argv(0), "owner"))
		{ if (strcmp(owner, "")) strunzone(owner); owner = strzone(substring(line, 6, 120)); }
		if (!strcmp(argv(0), "runid"))
		{ if (strcmp(date, "")) strunzone(date); date = strzone(substring(argv(1), 0, 15)); }
	}
	leaf = substring(e.ar2_source, FS_LastOf(e.ar2_source, 47) + 1, strlen(e.ar2_source));
	if (flags >= 0 && FS_HistoryLeaf(leaf) && version >= 4 && version <= 15 && version == floor(version))
	{
		e.ar_seen = e.ar_seen + 1;
		if (e.ar_seen > e.ar_offset)
		{
			row = buf_getsize(e.ar_rows) + 1; bufstr_set(e.ar_rows, row - 1, e.ar2_source);
			Archive_Event(e, AR_EV_ROW); WriteShort(MSG_MULTICAST, row);
			WriteString(MSG_MULTICAST, leaf); WriteString(MSG_MULTICAST, owner);
			WriteString(MSG_MULTICAST, date); WriteLong(MSG_MULTICAST, flags); Archive_Send(e);
		}
	}
	if (strcmp(owner, "")) strunzone(owner);
	if (strcmp(date, "")) strunzone(date);
	Ar2_Close(e);
};

void(entity e) Ar2_Work =
{
	local int count, got;
	local float fh, getting;
	local void *chunk;
	local string hash;
	if (!e.ar2_phase) return;
	e.ar_until = time + 60; Ar2_Progress(e);
	if (ar2_work < 1i) return;
	getting = (e.ar2_phase == 2 || e.ar2_phase == 4);
	if (e.ar2_phase <= 2)
	{
		count = min(FS_ARCHIVE_WORK, e.ar2_size - e.ar2_copyat); count = min(count, ar2_work);
		if (count < 1i) { Ar2_Fail(e, 2); return; }
		if (FS_StreamSize(e.ar2_rfh - 1) != (__int64)e.ar2_size) { Ar2_Fail(e, 2); return; }
		chunk = memalloc(count);
		got = fread(e.ar2_rfh - 1, chunk, count); ar2_work = ar2_work - count;
		if (got == count) got = fwrite(e.ar2_wfh - 1, chunk, count);
		memfree(chunk);
		if (got != count) { Ar2_Fail(e, 2); return; }
		e.ar2_copyat = e.ar2_copyat + got;
		if (e.ar2_copyat < e.ar2_size) return;
		fclose(e.ar2_rfh - 1); e.ar2_rfh = 0;
		fclose(e.ar2_wfh - 1); e.ar2_wfh = 0;
		fh = fopen(e.ar2_scratch, FS_FILE_READSTREAM);
		if (fh < 0) { Ar2_Fail(e, 2); return; }
		e.ar2_hfh = fh + 1;
		if (FS_StreamSize(fh) != (__int64)e.ar2_size) { Ar2_Fail(e, 2); return; }
		e.ar2_phase = getting ? 4 : 3; return;
	}
	count = min(FS_ARCHIVE_WORK, e.ar2_size - e.ar2_hashat); count = min(count, ar2_work);
	if (count < 1i) { Ar2_Fail(e, 2); return; }
	hash = FS_FileSHA256Step(e.ar2_hfh - 1, count); ar2_work = ar2_work - count;
	e.ar2_hashat = e.ar2_hashat + count;
	if (!strcmp(hash, "")) return;
	if (!SV_RecIsHex(hash, 64)) { Ar2_Fail(e, 2); return; }
	e.ar2_digest = strzone(hash);
	if (strcmp(e.ar2_expected, "") && strcmp(e.ar2_expected, e.ar2_digest)) { Ar2_Fail(e, 2); return; }
	if (e.ar2_pending)
	{
		Ar2_Publish(e.ar2_source, e.ar2_size, e.ar_identity, e.ar2_digest);
		if (!Ar2_Authority(e, e.ar2_source)) { Ar2_Fail(e, 2); return; }
		if (ar2_checked_pending || strcmp(e.ar2_digest, ar2_checked_hash)) { Ar2_Fail(e, 2); return; }
	}
	if (!getting) { Ar2_RowReady(e); return; }
	fseek(e.ar2_hfh - 1, 0i);
	e.ar2_sendfh = e.ar2_hfh; e.ar2_hfh = 0; e.ar2_phase = 0;
	e.ar2_bytes = 0i; e.ar_seq = e.ar2_ack = 0; e.ar_next = 0; e.ar_deadline = time + 15;
};

void(entity e, float row, float transfer) Ar2_Get =
{
	local string path;
	if (!e.ar_rows || e.ar_listing || time > e.ar_until || row < 1 || row != floor(row)
		|| row > buf_getsize(e.ar_rows)) { Archive_End(e, 2); return; }
	path = strzone(bufstr_get(e.ar_rows, row - 1));
	Ar2_Close(e); e.ar_transfer = transfer;
	if (!Ar2_Begin(e, path, TRUE)) Archive_End(e, 2);
	strunzone(path);
};

float(entity e, float argc) Archive_StreamCommand =
{
	local string verb;
	local float query, row, transfer, seq, track, leg, offset;
	verb = argv(1);
	if (strcmp(verb, "list2") && strcmp(verb, "get2") && strcmp(verb, "ack2")) return FALSE;
	if (!FS_StreamFiles() || clienttype(e) != CLIENTTYPE_REAL || argc < 3) return TRUE;
	query = stof(argv(2));
	if (!(query >= 1 && query <= 16000000 && query == floor(query))) return TRUE;
	if (!strcmp(verb, "list2"))
	{
		if (argc != 5 && argc != 6) return TRUE;
		if (time < e.ar_until - 58)
		{
			WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET); WriteByte(MSG_MULTICAST, AR_EV_END);
			WriteLong(MSG_MULTICAST, query); WriteLong(MSG_MULTICAST, 0);
			WriteByte(MSG_MULTICAST, 3); Archive_Send(e); return TRUE;
		}
		track = stof(argv(3)); leg = stof(argv(4)); offset = (argc == 6) ? stof(argv(5)) : 0;
		if (track != floor(track) || leg != floor(leg)) return TRUE;
		if (!(offset >= 0 && offset <= 16000000 && offset == floor(offset))) return TRUE;
		Archive_List(e, query, track, leg, offset);
		if (e.ar_query == query && e.ar_listing)
		{ e.ar2_mode = TRUE; e.ar2_map = strzone(mapname); e.ar2_profile = strzone(infokey(world, "*movementprofile")); }
		return TRUE;
	}
	if (query != e.ar_query || !e.ar2_mode) return TRUE;
	if (strcmp(e.ar_identity, Archive_Identity(e))) { Archive_Reset(e); return TRUE; }
	if (!strcmp(verb, "get2"))
	{
		if (argc != 5) return TRUE;
		row = stof(argv(3)); transfer = stof(argv(4));
		if (!(transfer >= 1 && transfer <= 16000000 && transfer == floor(transfer)) || transfer <= e.ar_transfer) return TRUE;
		Ar2_Close(e); e.ar_transfer = transfer;
		if (time < e.ar_rate) { Archive_End(e, 2); return TRUE; }
		e.ar_rate = time + 0.2; Ar2_Get(e, row, transfer); return TRUE;
	}
	if (argc != 5) return TRUE;
	transfer = stof(argv(3)); seq = stof(argv(4));
	if (transfer == e.ar_transfer && seq == floor(seq) && seq > e.ar2_ack && seq <= e.ar_seq)
	{ e.ar2_ack = seq; e.ar_deadline = time + 15; }
	return TRUE;
};

void() Archive_StreamFrame =
{
	local entity e;
	local float fh, done, burst;
	local int count, got;
	local void *chunk;
	local string data;
	if (!FS_StreamFiles()) return;
	Ar2_SealFrame(); ar2_work = AR2_QUERY_WORK;
	e = world;
	while ((e = SV_AcNext(e)))
	{
		if (!e.ar2_mode) continue;
		if (strcmp(e.ar_identity, Archive_Identity(e)) || strcmp(e.ar2_map, mapname)
			|| strcmp(e.ar2_profile, infokey(world, "*movementprofile"))) { Archive_Reset(e); continue; }
		if (e.ar2_phase) Ar2_Work(e);
		if (!e.ar2_sendfh) continue;
		if (time > e.ar_deadline) { Ar2_Close(e); Archive_End(e, 2); continue; }
		if (time < e.ar_next || e.ar_seq - e.ar2_ack >= AR2_WIN) continue;
		e.ar_until = time + 60; e.ar_next = time + 0.05;
		// At most four fragments this tick/eight unacknowledged: bounded
		// reliable occupancy without the old one-fragment throughput ceiling.
		for (burst = 0; burst < 4; burst = burst + 1)
		{
			if (e.ar_seq - e.ar2_ack >= AR2_WIN) break;
			fh = e.ar2_sendfh - 1; count = min(880i, e.ar2_size - e.ar2_bytes);
			chunk = memalloc(884i); got = fread(fh, chunk, count); data = (string)chunk;
			done = (e.ar2_bytes + got == e.ar2_size);
			if (got != count || memstrsize(data) != (float)got || (!done && got == 0i))
			{ memfree(chunk); Ar2_Close(e); Archive_End(e, 2); break; }
			Archive_Event(e, AR_EV_STREAM); WriteLong(MSG_MULTICAST, e.ar_transfer);
			WriteString(MSG_MULTICAST, itos(e.ar2_size)); WriteLong(MSG_MULTICAST, e.ar_seq);
			WriteByte(MSG_MULTICAST, done); WriteString(MSG_MULTICAST, e.ar2_digest);
			WriteString(MSG_MULTICAST, data); Archive_Send(e); memfree(chunk);
			e.ar_seq = e.ar_seq + 1; e.ar2_bytes = e.ar2_bytes + got;
			if (done) { Ar2_Close(e); break; }
		}
	}
};
