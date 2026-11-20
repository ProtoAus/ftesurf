/*
  P1658: GoldSrc (Half-Life 1 / Adrenaline Gamer / CS 1.6 KZ) maps in the map finder.

  The engine installs one package a map, <gamedir>/downloads/goldsrc/<id>.pk3 (<id> is the
  map's lower-case name plus "_gs"), and reads data/goldsrc.net.txt for its hash and
  address (fs.c FS_GoldSrc_Row, engine Patch 1656).  This file fetches that catalogue under
  m_mapmedia.qc's rules.

    FTESURF-GOLDSRC 1
    # stamp YYYYMMDDhhmmss
    gs <id> <kind> <xz bytes> <pk3 bytes> <pk3 sha256> <needs> <flags> <xz sha256>
    gx <id> <kind> <reason> <count>         a map that cannot be offered, and why
    # end <gs + gx rows>

  kind: bhop | kz | other.  needs (sum): 1 Half-Life, 2 Counter-Strike, 4 Condition Zero.
  A package's map is not in the file system until it loads: "installed" is mapfilekb(id).
*/
#ifndef MGS_URL       // an arm's build names a local stand-in (-DMGS_URL=...), as P1099's did MMM_BASE
#define MGS_URL       "https://maps.proto.bar/goldsrc/catalog.txt"
#endif
#define MGS_FILE      "data/goldsrc.net.txt"
#define MGS_TMP       "data/goldsrc.net.tmp"    // the reply as it came, then the checked table until its rename
#define MGS_HEAD      "FTESURF-GOLDSRC 1"
#define MGS_MAXLEN    1500000                   // 1,308 rows are 173 KB
#define MGS_MAXLINES  12000
#define MGS_MAXROWS   8000
#define MGS_MAXLINE   260                       // a gs row with a 60-character id is 227
#define MGS_IDCH      "abcdefghijklmnopqrstuvwxyz0123456789_-"
#define MGS_HEXCH     "0123456789abcdef"
#define MGS_SLICE     40                        // reply lines checked a frame

// The fetch: once a session, after consent.
float  mgs_req, mgs_sent, mgs_done;
float  mgs_job;                 // a reply is being checked, MGS_SLICE lines a frame
filestream mgs_in;
strbuf mgs_keep;
float  mgs_lines, mgs_seen, mgs_kept, mgs_endn;
string mgs_newst;               // the reply's stamp, strzoned; "" none

// An id as the engine takes one (fs.c FS_GoldSrc_Id: 60 of [a-z0-9_-]), ending "_gs" -- which
// is what keeps it apart from every Source map's name.
float(string id) Mgs_IdOK =
{
	local float n;
	n = strlen(id);
	if (n < 4 || n > 60)
		return FALSE;
	if (substring(id, n - 3, 3) != "_gs")
		return FALSE;
	return Mdl_Made(id, MGS_IDCH, 60);
};

/*
  One catalogue line, tokenized here (argv stays the caller's to read): 1 a gs row, 2 a gx
  row, 0 neither.  strict walks every field's characters: a reply, before it is written.
*/
float(string ln, float strict) Mgs_Line =
{
	local float n, gx;
	if (strlen(ln) > MGS_MAXLINE)
		return 0;
	n = tokenize(ln);
	gx = (argv(0) == "gx");
	if (!gx)
	if (argv(0) != "gs")
		return 0;
	if (n != (gx ? 5 : 9))
		return 0;
	n = strlen(argv(1));
	if (n < 4 || n > 60 || substring(argv(1), n - 3, 3) != "_gs")
		return 0;
	if (argv(2) != "bhop")
	if (argv(2) != "kz")
	if (argv(2) != "other")
		return 0;
	if (!gx)
	if (strlen(argv(5)) != 64 || strlen(argv(8)) != 64 || strlen(argv(6)) != 1 || strstrofs("01234567", argv(6)) < 0)
		return 0;
	if (!strict)
		return gx ? 2 : 1;
	if (!Mgs_IdOK(argv(1)))
		return 0;
	if (gx)
		return (Mdl_Made(argv(3), "abcdefghijklmnopqrstuvwxyz", 12) && Mdl_Made(argv(4), MDL_DIGITS, 6)) ? 2 : 0;
	if (!Mdl_Made(argv(3), MDL_DIGITS, 10) || !Mdl_Made(argv(4), MDL_DIGITS, 10) || !Mdl_Made(argv(7), MDL_DIGITS, 3))
		return 0;
	if (!Mdl_Made(argv(5), MGS_HEXCH, 64) || !Mdl_Made(argv(8), MGS_HEXCH, 64))
		return 0;
	return 1;
};

// A table file's gs + gx rows when its header and "# end" agree with them, else -1.
float(string path) Mgs_FileRows =
{
	local filestream fh;
	local string ln, p;
	local float rows, endn, lines;
	fh = fopen(path, FILE_READ);
	if (fh < 0)
		return -1;
	rows = lines = 0;
	endn = -1;
	if (substring(fgets(fh), 0, strlen(MGS_HEAD)) == MGS_HEAD)
		for (ln = fgets(fh); ln != ""; ln = fgets(fh))
		{
			lines = lines + 1;
			if (lines > MGS_MAXLINES)
				break;
			p = substring(ln, 0, 3);
			if (p == "gs " || p == "gx ")
				rows = rows + 1;
			else if (substring(ln, 0, 6) == "# end ")
				endn = stof(substring(ln, 6, 8));
		}
	fclose(fh);
	return (endn == rows) ? rows : -1;
};

// ---- the fetch ---------------------------------------------------------------------------

// One line of the reply: a row rebuilt from fields that each passed (Mdl_Reply's rule).
void(string ln) Mgs_ReplyLine =
{
	local string p;
	local float k;
	p = substring(ln, 0, 3);
	if (p == "gs " || p == "gx ")
	{
		mgs_seen = mgs_seen + 1;
		if (mgs_kept >= MGS_MAXROWS)
			return;
		k = Mgs_Line(ln, TRUE);
		// In pieces: a varargs call carries eight parameters.
		if (k == 1)
			bufstr_add(mgs_keep, strcat(sprintf("gs %s %s %s %s %s", argv(1), argv(2), argv(3), argv(4), argv(5)),
			                            sprintf(" %s %s %s", argv(6), argv(7), argv(8))), TRUE);
		else if (k == 2)
			bufstr_add(mgs_keep, sprintf("gx %s %s %s %s", argv(1), argv(2), argv(3), argv(4)), TRUE);
		if (k)
			mgs_kept = mgs_kept + 1;
		return;
	}
	if (substring(ln, 0, 2) != "# " || strlen(ln) > 40)
		return;
	if (tokenize(ln) != 3)
		return;
	if (argv(1) == "end")
	{
		if (Mdl_Made(argv(2), MDL_DIGITS, 6))
			mgs_endn = stof(argv(2));
	}
	else if (argv(1) == "stamp")
	if (mgs_newst == "")
	if (Mdl_Made(argv(2), MDL_DIGITS, 14))
	if (strlen(argv(2)) == 14)
		mgs_newst = strzone(argv(2));
};

// The checked table, whole, to `path`.  FALSE: it could not be opened.
float(string path) Mgs_Write =
{
	local filestream out;
	out = fopen(path, FILE_WRITE);
	if (out < 0)
		return FALSE;
	fputs(out, strcat(MGS_HEAD, "\n# stamp ", mgs_newst, "\n"));
	buf_writefile(out, mgs_keep);               // each row and a newline
	fputs(out, sprintf("# end %g\n", mgs_kept));
	fclose(out);
	return TRUE;
};

// The checked rows written beside the saved table and renamed over it.  TRUE: a new table.
float() Mgs_Put =
{
	local string st, had;
	local float hadrows;
	if (!mgs_kept || mgs_newst == "" || mgs_endn != mgs_seen)
	{
		print(sprintf("^5goldsrc:^7 a catalogue of %g rows (%g of %g at its end line) is not one -- the saved one stands\n",
		              mgs_kept, mgs_seen, mgs_endn));
		return FALSE;
	}
	if (!Mgs_Write(MGS_TMP))                    // over the spooled reply
		return FALSE;
	st = Mmm_Stamp(MGS_TMP);                    // "" for a date no table may carry (m_mapmedia.qc)
	had = Mmm_Stamp(MGS_FILE);
	hadrows = Mgs_FileRows(MGS_FILE);
	if (st == "")
	{
		print("^5goldsrc:^7 the catalogue's stamp is not a date -- the saved one stands\n");
		return FALSE;
	}
	// A saved table that reads whole is replaced only by a later one; a torn one by any.
	if (hadrows >= 0)
	if (strcmp(st, had) <= 0)
	{
		if (strcmp(st, had) < 0 || hadrows != mgs_kept)
			print(sprintf("^5goldsrc:^7 the catalogue served (%s) is not newer than the saved one (%s)\n", st, had));
		else
			print(sprintf("^5goldsrc:^7 the catalogue served is the one saved (%s, %g rows)\n", st, hadrows));
		return FALSE;
	}
	fremove(MGS_FILE);                          // a Windows rename cannot replace
	if (frename(MGS_TMP, MGS_FILE) != 0)
	if (!Mgs_Write(MGS_FILE))                   // the old table is gone by now: in place, rather than none
	{
		print(strcat("^5goldsrc:^7 could not write ", MGS_FILE, "\n"));
		return FALSE;
	}
	print(sprintf("^5goldsrc:^7 catalogue %s saved, %g rows (%g not kept)\n", st, mgs_kept, mgs_seen - mgs_kept));
	return TRUE;
};

// The job's buffers and its spool, gone (after a rename there is no spool left).
void() Mgs_JobEnd =
{
	buf_del(mgs_keep);
	if (mgs_newst != "")
		strunzone(mgs_newst);
	mgs_newst = "";
	mgs_job = FALSE;
	fremove(MGS_TMP);
};

void() Mgs_Step =
{
	local string ln;
	local float i;
	for (i = 0; i < MGS_SLICE; i = i + 1)
	{
		ln = (mgs_lines < MGS_MAXLINES) ? fgets(mgs_in) : "";
		if (ln == "")
			break;
		mgs_lines = mgs_lines + 1;
		Mgs_ReplyLine(ln);
	}
	if (i == MGS_SLICE)
		return;
	fclose(mgs_in);                             // before Mgs_Put writes over it
	Mgs_Put();
	Mgs_JobEnd();
	mgs_done = TRUE;
};

// Every frame, beside Mmm_Ask (m_draw): the fetch and its check.
void() Mgs_Ask =
{
	if (mgs_done)
		return;
	if (mgs_job)
	{
		Mgs_Step();
		return;
	}
	if (mgs_req)
	{
		if (time - mgs_sent > 20)
		{
			mgs_req = 0;            // no answer: the saved catalogue stands
			mgs_done = TRUE;
		}
		return;
	}
	if (ms_consent < FS_TERMS_ONLINE)
		return;
	mgs_sent = time;
	mgs_req = Lob_NextReq();
	// The UTC hour as a query: Cloudflare may hold the bare address for a while.
	if (!uri_get(strcat(MGS_URL, "?t=", strftime(FALSE, "%Y%m%d%H")), mgs_req))
	{
		mgs_req = 0;
		mgs_done = TRUE;
	}
};

// From URI_Get_Callback.  TRUE when the id was this request's.
float(float reqid, float code, string body) Mgs_Reply =
{
	local filestream fh;
	if (!mgs_req || reqid != mgs_req)
		return FALSE;
	mgs_req = 0;
	mgs_done = TRUE;
	if (code != 0 && code != 200)
	{
		print(sprintf("^5goldsrc:^7 the catalogue's host answered %g -- the saved one stands\n", code));
		return TRUE;
	}
	// The header line whole; CRLF passes, as every row is rebuilt from its tokens and written with LF.
	if (strlen(body) > MGS_MAXLEN || strcmp(substring(body, 0, strlen(MGS_HEAD)), MGS_HEAD)
	    || strstrofs("\r\n", substring(body, strlen(MGS_HEAD), 1)) < 0)
	{
		print("^5goldsrc:^7 a reply that is not a catalogue -- the saved one stands\n");
		return TRUE;
	}
	// Through a file: one write, then the engine's line reader (Mdl_Reply's reason).
	fh = fopen(MGS_TMP, FILE_WRITE);
	if (fh < 0)
		return TRUE;
	fputs(fh, body);
	fclose(fh);
	mgs_in = fopen(MGS_TMP, FILE_READ);
	if (mgs_in < 0)
	{
		fremove(MGS_TMP);
		return TRUE;
	}
	fgets(mgs_in);                              // the header, tested above
	mgs_keep = buf_create();
	mgs_lines = mgs_seen = mgs_kept = 0;
	mgs_endn = -1;
	mgs_newst = "";
	mgs_job = TRUE;
	mgs_done = FALSE;                           // Mgs_Ask steps it from the next frame
	return TRUE;
};

// m_shutdown: a reply mid-check is not left on disk.
void() Mgs_Shutdown =
{
	if (!mgs_job)
		return;
	fclose(mgs_in);
	Mgs_JobEnd();
};

// `ui_goldsrc`: where the fetch stands; `ui_goldsrc fetch` asks again.
void() Mgs_Command =
{
	if (argv(1) == "fetch")
	if (!mgs_job)
		mgs_done = mgs_req = 0;
	print(sprintf("ui_goldsrc: fetch req %g job %g done %g consent %g; saved %s, %g rows\n",
	              mgs_req, mgs_job, mgs_done, ms_consent, Mmm_Stamp(MGS_FILE), Mgs_FileRows(MGS_FILE)));
};
