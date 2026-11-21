/*
  P1658: GoldSrc (Half-Life 1 / Adrenaline Gamer / CS 1.6 KZ) maps in the map finder.

  The engine installs one package a map, <gamedir>/downloads/goldsrc/<id>.pk3 (<id> is the
  map's lower-case name plus "_gs"), and reads data/goldsrc.net.txt for its hash and
  address (fs.c FS_GoldSrc_Row, engine Patch 1656).  This file fetches that catalogue under
  m_mapmedia.qc's rules and lists its rows after the Source ones (Mgs_Append).

    FTESURF-GOLDSRC 1
    # stamp YYYYMMDDhhmmss
    gs <id> <kind> <xz bytes> <pk3 bytes> <pk3 sha256> <needs> <flags> <xz sha256>
    gx <id> <kind> <reason> <count>         a map that cannot be offered, and why
    # end <gs + gx rows>

  kind: bhop | kz | other.  needs (sum): 1 Half-Life, 2 Counter-Strike, 4 Condition Zero.
  flags (sum): 1 KZ timer, 2 ladders, 4 water; P1669: 8 sky, 16 textures, 32 models, 64 sounds missing -- the row
  still downloads and plays, with a red "warning" and a tooltip naming what is missing (Mgs_Warn).
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
#define MGS_ESC       "^xfc9"                   // the GoldSrc tag (SUI_THEME_FOCUS)

// The fetch: once a session, after consent.
float  mgs_req, mgs_sent, mgs_done, mgs_fresh;
float  mgs_parses, mgs_putat;   // Mgs_Load's parses; the count when the last table was written
float  mgs_job;                 // a reply is being checked, MGS_SLICE lines a frame
filestream mgs_in;
strbuf mgs_keep;
float  mgs_lines, mgs_seen, mgs_kept, mgs_endn;
string mgs_newst;               // the reply's stamp, strzoned; "" none

/*
  The saved catalogue, parsed: kept while the file's second line (its stamp) stays the same.
  The gs rows first, in file order, then the gx rows -- the order the finder lists them in, so
  row r of the list is entry r - mgs_row0 of these.
*/
var float mgs_tid = -1;         // strbufs: the id
var float mgs_tshow = -1;       // the name shown (no "_gs")
var float mgs_tcat = -1;        // GC_BHOP | GC_CLIMB | GC_OTHER
var float mgs_tkb = -1;         // gs: the download in KB, as mapdl.txt sizes are (a float holds 2^24 exactly)
var float mgs_tneed = -1;       // gs: the needs sum
var float mgs_twhy = -1;        // gx: why not; gs: what it lacks (P1669, Mgs_Warn); in words
float  mgs_tn, mgs_tgx;         // rows; how many of them are gx
float  mgs_tnb, mgs_tnk;        // gs rows that are bhop, kz
string mgs_tkey;                // strzoned
hashtable mgs_byid;             // id -> index + 1

float  mgs_row0, mgs_rows, mgs_ninst;   // ms_name[mgs_row0 .. ms_count) are the catalogue's rows
float  mgs_need[3];             // fs_addonstate of valve, cstrike, czero, asked once a load
float  mgs_needforce;           // `ui_goldsrc need`: 1 + a mask of games to draw as missing
float  mgs_kind;                // the Mode chips under the GoldSrc library: 0 all, 1 bhop, 2 kz, 3 installed
float  mgs_loadms, mgs_parsems; // the last Mgs_Append, and its Mgs_Load share

float() Mgs_Count = { return mgs_rows; };
float() Mgs_First = { return mgs_rows ? min(mgs_row0, ms_count) : ms_count; };
float(float row) Mgs_Row = { return (mgs_rows > 0 && row >= mgs_row0 && row < ms_count); };
float(float row) Mgs_Gx = { return (Mgs_Row(row) && row - mgs_row0 >= mgs_tn - mgs_tgx); };

// ui_cat_load: the catalogue's kind as a gametype, 0 for a row that is not GoldSrc.
float(float row) Mgs_Cat =
{
	if (!Mgs_Row(row))
		return 0;
	return stof(bufstr_get(mgs_tcat, row - mgs_row0));
};

// ui_refilter, with the GoldSrc library picked: the Mode chips' test.
float(float row) Mgs_Keep =
{
	if (mgs_kind == 1) return bufstr_get(mgs_tcat, row - mgs_row0) == "2";      // GC_BHOP
	if (mgs_kind == 2) return bufstr_get(mgs_tcat, row - mgs_row0) == "3";      // GC_CLIMB
	if (mgs_kind == 3) return bufstr_get(ms_have, row) == "1";
	return TRUE;
};

// A catalogue id's index, or -1.
float(string id) Mgs_Find =
{
	if (!mgs_byid)
		return -1;
	return hash_get(mgs_byid, id, 0, EV_FLOAT) - 1;
};

// Dl_Tick: -1 not a GoldSrc id, else whether its package is installed now.
float(string id) Mgs_Installed =
{
	if (Mgs_Find(id) < 0)
		return -1;
	if (!ui_dl_kb_ready())
		return 0;
	return mapfilekb(id) > 0;
};

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
  row, 0 neither.  strict walks every field's characters: a reply, before it is written.  The
  saved file is read on its shape alone -- with the walk, reading its 1,308 rows was 13-15 ms
  where this is 5 -- and an id is walked where it is used (Mgs_Launch; the engine's own tests).
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
	mgs_putat = mgs_parses;
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
	mgs_fresh = Mgs_Put();
	Mgs_JobEnd();
	mgs_done = TRUE;
};

// Every frame, beside Mmm_Ask (m_draw): the fetch, its check, and the list's reload.
void() Mgs_Ask =
{
	if (mgs_fresh)
	{
		if (!menu_active)
			return;                 // Mmm's rule: no list load under a game
		mgs_fresh = FALSE;
		if (mgs_parses == mgs_putat)    // else a list load since the write already read it (the boot preload)
			ui_maplist_changed();
		return;
	}
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

// ---- the saved catalogue, parsed ---------------------------------------------------------

void() Mgs_TableClear =
{
	if (mgs_tid >= 0)
	{
		buf_del(mgs_tid); buf_del(mgs_tshow); buf_del(mgs_tcat);
		buf_del(mgs_tkb); buf_del(mgs_tneed); buf_del(mgs_twhy);
	}
	if (mgs_byid) hash_destroytab(mgs_byid);
	if (mgs_tkey != "") strunzone(mgs_tkey);
	mgs_tid = -1;
	mgs_byid = 0;
	mgs_tkey = "";
	mgs_tn = mgs_tgx = mgs_tnb = mgs_tnk = 0;
};

string(string why, float n) Mgs_Why =
{
	if (why == "sky")   return sprintf("sky textures missing (%g file%s)", n, (n == 1) ? "" : "s");
	if (why == "tex")   return "textures missing";
	if (why == "model") return "models missing";
	if (why == "sound") return "sounds missing";
	if (why == "kind")  return "not a bhop or kz map";
	if (why == "bsp")   return "the map file does not read";      // P1669: the two reasons left
	if (why == "name")  return "its name cannot be used";
	return "files missing";
};

// P1669: what a gs row's flags say is missing (8 sky, 16 textures, 32 models, 64 sounds), in words; "" when complete.
string(float flags) Mgs_Missing =
{
	local string s;
	s = "";
	if (flags & 8)  s = "its custom sky";
	if (flags & 16) s = strcat(s, (s == "") ? "" : ", ", "textures");
	if (flags & 32) s = strcat(s, (s == "") ? "" : ", ", "models");
	if (flags & 64) s = strcat(s, (s == "") ? "" : ", ", "sounds");
	return s;
};

void(string id, float cat, string kb, string need, string why) Mgs_TableAdd =
{
	bufstr_set(mgs_tid, mgs_tn, id);
	bufstr_set(mgs_tshow, mgs_tn, substring(id, 0, strlen(id) - 3));
	bufstr_set(mgs_tcat, mgs_tn, ftos(cat));
	bufstr_set(mgs_tkb, mgs_tn, kb);
	bufstr_set(mgs_tneed, mgs_tn, need);
	bufstr_set(mgs_twhy, mgs_tn, why);
	hash_add(mgs_byid, id, mgs_tn + 1, HASH_REPLACE | EV_FLOAT);
	mgs_tn = mgs_tn + 1;
};

// No file, another header, or rows that disagree with "# end": no table, and no error.
void() Mgs_Load =
{
	local filestream fh;
	local strbuf xid, xcat, xwhy;
	local string ln, key;
	local float k, i, lines, seen, endn, cat, dup;

	fh = fopen(MGS_FILE, FILE_READ);
	if (fh < 0)
	{
		Mgs_TableClear();
		return;
	}
	ln = fgets(fh);
	key = fgets(fh);
	if (substring(ln, 0, strlen(MGS_HEAD)) != MGS_HEAD || key == "")
	{
		fclose(fh);
		Mgs_TableClear();
		return;
	}
	if (mgs_tn > 0)
	if (!strcmp(key, mgs_tkey))
	{
		fclose(fh);
		return;                                 // the table already parsed
	}
	Mgs_TableClear();
	mgs_parses = mgs_parses + 1;
	mgs_tkey = strzone(key);
	mgs_tid = buf_create(); mgs_tshow = buf_create(); mgs_tcat = buf_create();
	mgs_tkb = buf_create(); mgs_tneed = buf_create(); mgs_twhy = buf_create();
	mgs_byid = hash_createtab(4096, EV_FLOAT);
	xid = buf_create();                         // the gx rows, held until the gs rows are all in
	xcat = buf_create();
	xwhy = buf_create();
	lines = seen = 0;
	endn = -1;
	for (ln = fgets(fh); ln != ""; ln = fgets(fh))
	{
		lines = lines + 1;
		if (lines > MGS_MAXLINES)
			break;
		if (substring(ln, 0, 6) == "# end ")
			endn = stof(substring(ln, 6, 8));
		if (substring(ln, 0, 3) == "gs " || substring(ln, 0, 3) == "gx ")
			seen = seen + 1;
		if (mgs_tn + mgs_tgx >= MGS_MAXROWS)
			continue;                           // past the cap: counted for "# end", not listed
		k = Mgs_Line(ln, FALSE);
		if (!k)
			continue;
		dup = hash_get(mgs_byid, argv(1), 0, EV_FLOAT);
		if (dup)
			continue;                           // a second row for one id
		cat = (argv(2) == "bhop") ? GC_BHOP : ((argv(2) == "kz") ? GC_CLIMB : GC_OTHER);
		if (k == 2)
		{
			hash_add(mgs_byid, argv(1), -1, HASH_REPLACE | EV_FLOAT);   // seen; its index comes below
			bufstr_set(xid, mgs_tgx, argv(1));
			bufstr_set(xcat, mgs_tgx, ftos(cat));
			bufstr_set(xwhy, mgs_tgx, Mgs_Why(argv(3), stof(argv(4))));
			mgs_tgx = mgs_tgx + 1;
			continue;
		}
		Mgs_TableAdd(argv(1), cat, ftos(ceil(stof(argv(3)) / 1024)), argv(6), Mgs_Missing(stof(argv(7))));
		if (cat == GC_BHOP) mgs_tnb = mgs_tnb + 1;
		if (cat == GC_CLIMB) mgs_tnk = mgs_tnk + 1;
	}
	fclose(fh);
	for (i = 0; i < mgs_tgx; i = i + 1)
		Mgs_TableAdd(bufstr_get(xid, i), stof(bufstr_get(xcat, i)), "0", "", bufstr_get(xwhy, i));
	buf_del(xid);
	buf_del(xcat);
	buf_del(xwhy);
	if (endn != seen)
	{
		print(sprintf("^5goldsrc:^7 %s holds %g rows where its end line says %g -- not listed\n", MGS_FILE, seen, endn));
		Mgs_TableClear();
	}
};

/*
  ui_load_maps, after ui_dl_load and before ui_meta_load (which sizes itself from ms_count):
  the catalogue's rows appended to every buffer that exists by then.  Installed is one search
  of downloads/goldsrc and the engine's own answer for each hit: asking mapfilekb of every row
  is a miss through every mount each (Patch 999).
*/
void() Mgs_Append =
{
	local searchhandle sh;
	local hashtable inst;
	local float i, n, t, ngs, have, t0;
	local string id, gsbit;

	t0 = gettime(1);
	Mgs_Load();
	mgs_parsems = (gettime(1) - t0) * 1000;
	mgs_row0 = ms_count;
	mgs_rows = mgs_ninst = 0;
	if (!mgs_tn)
	{
		if (ms_srcf == SRC_BIT_GS)
			ms_srcf = 0;                        // its list is gone: back to the Source ones
		return;
	}

	for (i = 0; i < 3; i = i + 1)
	{
		id = (i == 0) ? "steam:Half-Life/valve" : ((i == 1) ? "steam:Half-Life/cstrike" : "steam:Half-Life/czero");
		mgs_need[i] = checkbuiltin(fs_addonstate) ? fs_addonstate(id) : -1;
		if (mgs_needforce)
			mgs_need[i] = ((mgs_needforce - 1) & ((i == 0) ? 1 : ((i == 1) ? 2 : 4))) ? 0 : 1;
	}

	inst = hash_createtab(256, EV_FLOAT);
	sh = search_begin("goldsrc/*.pk3", 0, TRUE);
	if (sh >= 0)
	{
		n = search_getsize(sh);
		for (i = 0; i < n; i = i + 1)
		{
			id = strtolower(search_getfilename(sh, i));
			id = substring(id, 8, strlen(id) - 12);     // "goldsrc/" <id> ".pk3"
			if (Mgs_Installed(id) > 0)
				hash_add(inst, id, 1, HASH_REPLACE | EV_FLOAT);
		}
		search_end(sh);
	}

	gsbit = ftos(SRC_BIT_GS);
	ngs = mgs_tn - mgs_tgx;
	for (t = 0; t < mgs_tn; t = t + 1)
	{
		id = bufstr_get(mgs_tid, t);
		have = FALSE;
		if (t < ngs)
			have = hash_get(inst, id, 0, EV_FLOAT);
		// At ms_count, never bufstr_add: see ui_dl_load.
		bufstr_set(ms_name, ms_count, id);
		bufstr_set(ms_src, ms_count, gsbit);
		bufstr_set(ms_lst, ms_count, gsbit);
		bufstr_set(ms_have, ms_count, (t >= ngs) ? "x" : (have ? "1" : "0"));
		bufstr_set(ms_new, ms_count, "0");
		bufstr_set(ms_dlkb, ms_count, bufstr_get(mgs_tkb, t));
		bufstr_set(ms_dltier, ms_count, "0");
		bufstr_set(ms_momtier, ms_count, "0");
		bufstr_set(ms_ksftier, ms_count, "0");
		bufstr_set(ms_momtsrc, ms_count, "");
		bufstr_set(ms_var, ms_count, "");
		bufstr_set(ms_varof, ms_count, "");
		bufstr_set(ms_pick, ms_count, "");
		bufstr_set(ms_enabled, ms_count, "1");
		bufstr_set(ms_zoned, ms_count, "0");
		if (have)
			mgs_ninst = mgs_ninst + 1;
		ms_count = ms_count + 1;
	}
	mgs_rows = mgs_tn;
	hash_destroytab(inst);
	mgs_loadms = (gettime(1) - t0) * 1000;
	print(sprintf("WOS: goldsrc -- %g maps (%s), %g installed, %g not available; %.1f ms (%.1f reading)\n",
	              ngs, sprintf("%g bhop, %g kz, %g other", mgs_tnb, mgs_tnk, ngs - mgs_tnb - mgs_tnk),
	              mgs_ninst, mgs_tgx, mgs_loadms, mgs_parsems));
};

// ---- what the finder draws: read for the visible rows only ------------------------------

string(float row) Mgs_Show = { return bufstr_get(mgs_tshow, row - mgs_row0); };

string(float row) Mgs_Kind =
{
	local float cat;
	cat = stof(bufstr_get(mgs_tcat, row - mgs_row0));
	return (cat == GC_BHOP) ? "bhop" : ((cat == GC_CLIMB) ? "kz" : "other");
};

// "installed", or the download's size; nothing for a row that cannot be offered.
string(float row) Mgs_Size =
{
	if (Mgs_Gx(row))
		return "";
	if (bufstr_get(ms_have, row) == "1")
		return "installed";
	return ui_dl_size(stof(bufstr_get(ms_dlkb, row)));
};

// P1669: a playable row whose catalogue flags name missing files: what they are, else "".
string(float row) Mgs_Warn = { return Mgs_Gx(row) ? "" : bufstr_get(mgs_twhy, row - mgs_row0); };
// The tooltip names only what this map lacks (Mgs_Missing's words).
string(float row) Mgs_WarnTip =
{
	local string w, s;
	w = Mgs_Warn(row);
	s = "";
	if (strstrofs(w, "sky") >= 0)      s = "a stand-in sky draws in its place";	// P1695: Half-Life's desert, else ours
	if (strstrofs(w, "textures") >= 0) s = strcat(s, (s == "") ? "" : ", ", "surfaces without their texture draw dark");
	if (strstrofs(w, "models") >= 0)   s = strcat(s, (s == "") ? "" : ", ", "some models are left out");
	if (strstrofs(w, "sounds") >= 0)   s = strcat(s, (s == "") ? "" : ", ", "some sounds are silent");
	return strcat("Warning: files this map uses were never found, so they are not in its download: ", w,
	              ". It still downloads and plays; ", s, ".");
};

// A gx row's reason; else a red "warning" for missing files (P1669) and "needs Half-Life" for each game the row
// names that Steam does not have (fs_addonstate 0), or nothing.
string(float row) Mgs_Note =
{
	local string s;
	local float i, bit, needs;
	if (Mgs_Gx(row))
		return bufstr_get(mgs_twhy, row - mgs_row0);
	needs = stof(bufstr_get(mgs_tneed, row - mgs_row0));
	s = "";
	for (i = 0; i < 3; i = i + 1)
	{
		bit = (i == 0) ? 1 : ((i == 1) ? 2 : 4);
		if (!(needs & bit) || mgs_need[i] != 0)
			continue;
		s = strcat(s, (s == "") ? "needs ^1" : "^7, ^1",
		           (i == 0) ? "Half-Life" : ((i == 1) ? "Counter-Strike" : "Condition Zero"));
	}
	if (s != "")
		s = strcat(s, "^7");
	if (Mgs_Warn(row) != "")
		s = strcat(MGS_WARN_ESC, "warning^7", (s == "") ? "" : " | ", s);
	return s;
};

// The detail line: the tag, the kind, the size or "installed", and what is missing.
string(float row) Mgs_Sub =
{
	local string s, t;
	s = strcat(MGS_ESC, "GoldSrc^7 | ", Mgs_Kind(row));
	t = Mgs_Size(row);
	if (t != "")
		s = strcat(s, " | ", t);
	t = Mgs_Note(row);
	if (t != "")
		s = strcat(s, " | ", Mgs_Gx(row) ? "not available: " : "", t);
	return s;
};

#define MGS_GXTIP "Listed so you know why it is missing: this map cannot be offered, for the reason on its line."

// A GoldSrc row as a card: no picture and no record cells (no board has these maps).
void(vector rp, vector rs, float nx, float compact, float real, float lit, string rid) Mgs_Card =
{
	local float gx, cw, a;
	local vector ts;
	gx = Mgs_Gx(real);
	a = gx ? 0.5 : 1;
	ts = compact ? '128 72 0' : '160 90 0';
	ui_thumb([rp_x + 4, rp_y + 8], ts, -1, -1);
	sui_text([rp_x + 4 + (ts_x - stringwidth("GoldSrc", TRUE, '16 16 0')) * 0.5, rp_y + 8 + (ts_y - 16) * 0.5],
	         '16 16 0', "GoldSrc", COL_DIM, 0.45 * a, 0);
	cw = rs_x - nx - (compact ? 8 : 164);
	sui_text([rp_x + nx, rp_y + 8], '20 20 0', ui_fit_text(Mgs_Show(real), cw, '20 20 0'),
	         gx ? COL_DIM : (lit ? COL_ACCENT : COL_TEXT), a, 0);
	sui_text([rp_x + nx, rp_y + 50], '12 12 0', ui_fit_text(Mgs_Sub(real), cw, '12 12 0'), COL_DIM, a, 0);
	if (gx)
		sui_tooltip_for(rid, MGS_GXTIP, 2);
	else if (Mgs_Warn(real) != "" && sui_is_hovered(rid))     // the text only for the hovered row
		sui_tooltip_for(rid, Mgs_WarnTip(real), 2);
};

// The Mode group while the GoldSrc library is picked: its own kinds, not Surf | Bhop.
string(float k) Mgs_KindLabel =
{
	return (k == 0) ? "all" : ((k == 1) ? "bhop" : ((k == 2) ? "kz" : "installed"));
};

float() Mgs_KindW =
{
	local float k, w;
	w = 0;
	for (k = 0; k < 4; k = k + 1)
		w = w + ui_filter_chip_w(Mgs_KindLabel(k)) + 4;
	return w;
};

float(vector pos) Mgs_KindChips =
{
	local float k, x;
	local string id;
	x = 0;
	for (k = 0; k < 4; k = k + 1)
	{
		id = strcat("cs_gsk", ftos(k));
		x = x + ui_filter_chip(pos + [x, 0], id, Mgs_KindLabel(k), mgs_kind == k) + 4;
		sui_tooltip_for(id, (k == 0) ? "Every GoldSrc map. The ones that cannot be offered are last, with the reason."
		                    : ((k == 1) ? "Bhop maps." : ((k == 2) ? "KZ (climb) maps." : "The GoldSrc maps on this PC.")), 2);
		if (sui_is_released(id))
		if (mgs_kind != k)
		{
			mgs_kind = k;
			ui_refilter();              // before the list draws, further down this frame
		}
	}
	return x;
};

// ui_launch_mode, past its gates: no lobby hosts these maps, so the local game -- with no
// zone fetch (no zone file exists for a _gs id) -- or the download a missing one needs first.
void(float row) Mgs_Launch =
{
	local string id, h;
	id = bufstr_get(ms_name, row);
	h = bufstr_get(ms_have, row);
	if (!Mgs_IdOK(id))
		return;                         // the saved file is read on its shape; an id is walked here
	if (h == "1")
	{
		if (strlen(mzd_play))           // a Source map waiting on its zone refresh would start over this one
		{
			strunzone(mzd_play);
			mzd_play = "";
		}
		ui_playlocal_now(id);
	}
	else if (h == "0")
		ui_dl_start(id, FALSE);
	else
		ui_st_result(sprintf("%s is not available: %s", Mgs_Show(row), Mgs_Note(row)), -1);
};

// `ui_goldsrc`: the catalogue and its rows.  `fetch` asks again; `lib [0-3]` picks the library
// and a Mode chip as a click does; `need <mask>` draws those games as missing (-1: Steam's answer).
void() Mgs_Command =
{
	local float r;
	if (argv(1) == "fetch")
	{
		if (!mgs_job)
			mgs_done = mgs_req = 0;
	}
	else if (argv(1) == "lib")
	{
		if (mgs_rows)
		{
			ms_srcf = SRC_BIT_GS;
			ms_tier = 0;
			mgs_kind = bound(0, floor(stof(argv(2))), 3);
			ui_refilter();
		}
	}
	else if (argv(1) == "need")
	{
		mgs_needforce = (stof(argv(2)) < 0) ? 0 : 1 + (stof(argv(2)) & 7);
		ui_maplist_changed();
	}
	else if (argv(1) != "")
	{
		r = ui_map_index(argv(1));
		if (Mgs_Row(r))
			print(sprintf("ui_goldsrc: %s row %g have %s kb %s cat %s -- %s\n", bufstr_get(ms_name, r), r,
			              bufstr_get(ms_have, r), bufstr_get(ms_dlkb, r), bufstr_get(ms_catv, r), Mgs_Sub(r)));
		else
			print(sprintf("ui_goldsrc: %S is not a GoldSrc row\n", argv(1)));
		return;
	}
	print(sprintf("ui_goldsrc: table %g rows (%g gx) %S; list rows %g from %g, installed %g, %.1f ms\n",
	              mgs_tn, mgs_tgx, mgs_tkey, mgs_rows, mgs_row0, mgs_ninst, mgs_loadms));
	print(sprintf("ui_goldsrc: fetch req %g job %g done %g fresh %g consent %g\n",
	              mgs_req, mgs_job, mgs_done, mgs_fresh, ms_consent));
	print(sprintf("ui_goldsrc: lib %g kind %g view %g\n", ms_srcf == SRC_BIT_GS, mgs_kind, ms_viewcount));
	if (mgs_rows)       // asked only when there are rows to say it on
		print(sprintf("ui_goldsrc: steam valve %g cstrike %g czero %g (0 missing, 1 installed, 2 mounted, -1 unknown)\n",
		              mgs_need[0], mgs_need[1], mgs_need[2]));
};
