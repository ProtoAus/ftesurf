// P1568: full-byte integrity before promotion; no whole-record client buffer.
float(string s) Ar2_ClientHash =
{
	local float i, c;
	if (strlen(s) != 64) return FALSE;
	for (i = 0; i < 64; i = i + 1)
	{
		c = str2chr(s, i);
		if (!(c >= 48 && c <= 57) && !(c >= 97 && c <= 102)) return FALSE;
	}
	return TRUE;
};

void() Archive_StreamClientCancel =
{
	if (ar2_verifyfh > 0) fclose(ar2_verifyfh - 1);
	ar2_verifyfh = 0; ar2_total = ar2_written = ar2_verifysteps = 0i;
	if (strcmp(ar2_hash, "")) strunzone(ar2_hash);
	ar2_hash = "";
};

void() Ar2_ClientFail =
{
	localcmd(sprintf("cmd archive cancel %d\n", ar_query));
	Archive_ClientCancel(); ar_state = 0;
	if (ar_auto) History_Received(FALSE);
	else print("scores: recording integrity check failed; original files retained, reopen Local to retry.\n");
};

void() Ar2_ClientPromote =
{
	local float fh, automatic;
	local string path, count;
	// Check the writer's namespace again, uncached. This excludes known
	// occupants/errors, not arbitrary external-writer races.
	if (FS_WritePathStatus(ar_path) != 0) { Ar2_ClientFail(); return; }
	fh = fopen(ar_path, FILE_READ);
	if (fh >= 0) { fclose(fh); Ar2_ClientFail(); return; }
	if (frename(strcat(ar_path, ".part"), ar_path) != 0) { Ar2_ClientFail(); return; }
	ar_part_owned = 0;
	path = strzone(ar_path); count = strzone(itos(ar2_written)); automatic = ar_auto;
	rec_sb_legbuilt = -2;
	Archive_ClientCancel(); ar_state = 0;
	if (automatic) History_Received(TRUE);
	else
	{
		print(strcat("scores: owner archive received and SHA256-verified ", count, " bytes\n"));
		Scores_Close(); Watch_Open(path);
	}
	strunzone(path); strunzone(count);
};

void(float ev, float query) Archive_StreamClientEvent =
{
	local float transfer, phase, seq, done, fh;
	local int total, bytes;
	local string hash, data;
	if (ev == AR_EV_PROGRESS)
	{
		transfer = readlong(); phase = readbyte();
		if (!ar2_clientmode || query != ar_query || !ar_state) return;
		if (strcmp(ar_map, serverkey("map")) || strcmp(ar_profile, serverkey("*movementprofile"))) return;
		if (ar_state == 1 && transfer != 0) return;
		if (ar_state >= 2 && transfer != ar_transfer) return;
		if (phase < 1 || phase > 4) return;
		ar_at = cltime + 15;
		return;
	}
	transfer = readlong(); total = FS_ArchiveSize(readstring()); seq = readlong(); done = readbyte();
	hash = strzone(readstring()); data = readstring(); bytes = (int)memstrsize(data);
	if (!ar2_clientmode || query != ar_query || transfer != ar_transfer || ar_state != 2
		|| strcmp(ar_map, serverkey("map")) || strcmp(ar_profile, serverkey("*movementprofile")))
	{ strunzone(hash); return; }
	if (!ar2_total)
	{
		ar2_total = total;
		ar2_hash = strzone(hash);
	}
	if (total < 1i || total != ar2_total || !Ar2_ClientHash(hash) || strcmp(hash, ar2_hash)
		|| seq != ar_seq || bytes < 0i || bytes > 900i || bytes > ar2_total - ar2_written
		|| done > 1 || (!done && bytes == 0i))
	{ strunzone(hash); Ar2_ClientFail(); return; }
	strunzone(hash);
	fputs(ar_fh - 1, data);
	ar2_written = ar2_written + bytes; ar_bytes = itof(ar2_written);
	ar_seq = ar_seq + 1; ar_at = cltime + 15;
	localcmd(sprintf("cmd archive ack2 %d %d %d\n", ar_query, ar_transfer, ar_seq));
	if (!done) return;
	fclose(ar_fh - 1); ar_fh = 0;
	if (ar2_written != ar2_total) { Ar2_ClientFail(); return; }
	fh = fopen(strcat(ar_path, ".part"), FS_FILE_READSTREAM);
	if (fh < 0) { Ar2_ClientFail(); return; }
	ar2_verifyfh = fh + 1;
	if (FS_StreamSize(fh) != (__int64)ar2_total) { Ar2_ClientFail(); return; }
	ar_state = 3; ar2_verifysteps = 0i;
};

void() Archive_StreamClientFrame =
{
	local string hash;
	if (ar_state != 3 || ar2_verifyfh < 1) return;
	ar2_verifysteps = ar2_verifysteps + 1i;
	if (ar2_verifysteps > ar2_total / FS_ARCHIVE_WORK + 2i) { Ar2_ClientFail(); return; }
	hash = FS_FileSHA256Step(ar2_verifyfh - 1, FS_ARCHIVE_WORK);
	ar_at = cltime + 15;
	if (!strcmp(hash, "")) return;
	if (!Ar2_ClientHash(hash) || strcmp(hash, ar2_hash)) { Ar2_ClientFail(); return; }
	fclose(ar2_verifyfh - 1); ar2_verifyfh = 0;
	Ar2_ClientPromote();
};
