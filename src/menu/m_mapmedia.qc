/*
  P1099: map media between releases.  The PC's six-hourly refresh
  (tools/mapmedia_refresh.py) publishes data/mapmeta.txt, data/mapdeps.txt and a
  small JPEG per thumbnail id under MMM_BASE; the menu fetches the two tables once
  a session.  A reply is server text, so every line kept is rebuilt from fields
  that pass their own test (Mdl_Reply's rule) and the mount specs are a fixed list.
  Both land in .net.txt files: the shipped ones are launcher-managed, and a launch
  would "repair" an edited one.  The engine reads mapdeps.net.txt itself (fs.c).
  `# stamp YYYYMMDDHHMMSS` (UTC) picks the newer copy: a string, as a Unix time
  in a QC float resolves to 128 s.  `# end N` closes each table: a dropped
  connection still answers 200 with what arrived (httpclient.c).  Consent is
  ms_consent, the menu's own, not rec_terms, which a server can set.
*/
#define MMM_BASE      "https://play.proto.bar/ftesurf/media/"
#define MMM_META      "data/mapmeta.net.txt"
#define MMM_DEPS      "data/mapdeps.net.txt"
#define MMM_TMP       "data/mapmedia.tmp"
#define MMM_MAXLEN    2500000
#define MMM_MAXLINES  12000
#define MMM_VPAGE     1000      // ui_thumb: a page at or past this is mmm_urls[page - MMM_VPAGE]
#define MMM_MAXPAGES  64
#define MMM_FIELDCH   "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-."
#define MMM_SLICE     150       // P1116: lines checked a frame (~3 ms); the whole meta table was 55 ms

float mmm_req, mmm_kind, mmm_sent, mmm_done, mmm_took;
float mmm_fresh;                // a table was taken: the map list reloads once the menu is open
float mmm_urls, mmm_urlsok;     // strbuf, rebuilt by every ui_meta_load
float mmm_pagesz[MMM_MAXPAGES]; // the chosen table's "# atlas P bytes"; 0 = not listed
float mmm_pagehave[MMM_MAXPAGES];
float ms_consent;               // m_main.qc's: the terms version on disk
// P1116: the reply being checked, a slice a frame (Mmm_Step); its table is written in one frame
float mmm_job;                  // 0, or the kind being read
filestream mmm_in;
strbuf mmm_keep;
float mmm_rows, mmm_lines, mmm_st, mmm_seen, mmm_endn;

// A table's "# stamp" (14 digits), or "" for no file or none: "" sorts first.
string(string path) Mmm_Stamp =
{
	local filestream fh;
	local string ln, st;
	local float i;
	fh = fopen(path, FILE_READ);
	if (fh < 0)
		return "";
	st = "";
	for (i = 0; i < 40; i = i + 1)  // fs.c FS_MapDepsStamp's 40, so badges and mounts agree
	{
		ln = fgets(fh);
		if (ln == "")
			break;
		if (substring(ln, 0, 8) == "# stamp ")
		{
			st = substring(ln, 8, 14);
			if (!Mdl_Made(st, MDL_DIGITS, 14) || strlen(st) != 14)
				st = "";
			else if (MP_Day(substring(st, 0, 8)) < 0
			         || MP_Day(substring(st, 0, 8)) > MP_Day(strftime(FALSE, "%Y%m%d")) + 1)
				st = "";          // no date, or ahead of this clock: none, as fs.c reads it
			else if (stof(substring(st, 8, 2)) > 23 || stof(substring(st, 10, 2)) > 59
			         || stof(substring(st, 12, 2)) > 59)
				st = "";
			break;
		}
	}
	fclose(fh);
	return st;
};

// The fetched table when it is newer than the one the install shipped.
string() Mmm_MetaPath =
{
	if (strcmp(Mmm_Stamp(MMM_META), Mmm_Stamp("data/mapmeta.txt")) > 0)
		return MMM_META;
	return "data/mapmeta.txt";
};

// The same choice FS_AutoMountForMap makes, for the browser's mount badges.
string() Mmm_DepsPath =
{
	if (strcmp(Mmm_Stamp(MMM_DEPS), Mmm_Stamp("data/mapdeps.txt")) > 0)
		return MMM_DEPS;
	return "data/mapdeps.txt";
};

/*
  Which atlas pages this install can draw: present, and the size the chosen table
  lists for it (a page regenerated since is another page).  Called by ui_meta_load
  with the table it is about to read.
*/
void(string path) Mmm_Pages =
{
	local filestream fh;
	local searchhandle sh;
	local string ln, nm;
	local float i, n, p;
	for (i = 0; i < MMM_MAXPAGES; i = i + 1)
		mmm_pagesz[i] = mmm_pagehave[i] = 0;
	fh = fopen(path, FILE_READ);
	if (fh >= 0)
	{
		for (i = 0; i < 80; i = i + 1)
		{
			ln = fgets(fh);
			if (ln == "")
				break;
			if (substring(ln, 0, 8) != "# atlas ")
				continue;
			n = tokenize(ln);
			p = stof(argv(2));
			if (n == 4 && p >= 0 && p < MMM_MAXPAGES && p == floor(p))
				mmm_pagesz[p] = stof(argv(3));
		}
		fclose(fh);
	}
	sh = search_begin("gfx/mapthumbs/atlas*.png", TRUE, TRUE);
	if (sh < 0)
		return;
	n = search_getsize(sh);
	for (i = 0; i < n; i = i + 1)
	{
		nm = strtolower(search_getfilename(sh, i));
		p = stof(substring(nm, strlen("gfx/mapthumbs/atlas"), -1));
		if (p < 0 || p >= MMM_MAXPAGES || nm != strcat("gfx/mapthumbs/atlas", ftos(p), ".png"))
			continue;
		mmm_pagehave[p] = 1;
		if (mmm_pagesz[p] > 0)
		if (checkbuiltin(search_getfilesize))
		if (search_getfilesize(sh, i) != mmm_pagesz[p])
			mmm_pagehave[p] = 0;
	}
	search_end(sh);
};

float(float page) Mmm_PageOK =
{
	if (page < 0 || page >= MMM_MAXPAGES || page != floor(page))
		return FALSE;
	return mmm_pagehave[page];
};

// A row's picture from the Pi when no local atlas has it: its virtual page, or -1.
float(string uuid) Mmm_UrlPage =
{
	if (strlen(uuid) != 36 || !Mdl_Made(uuid, "0123456789abcdef-", 36))
		return -1;
	if (ms_consent < FS_TERMS_ONLINE)
		return -1;                  // drawing it is a request to the Pi
	if (!mmm_urlsok)
	{
		mmm_urls = buf_create();
		mmm_urlsok = TRUE;
	}
	return MMM_VPAGE + bufstr_add(mmm_urls, strcat(MMM_BASE, "thumbs/", uuid, ".jpg"), TRUE);
};

string(float page) Mmm_UrlFor =
{
	if (!mmm_urlsok || page < MMM_VPAGE)
		return "";
	return bufstr_get(mmm_urls, page - MMM_VPAGE);
};

float() Mmm_UrlCount =
{
	return mmm_urlsok ? buf_getsize(mmm_urls) : 0;
};

void() Mmm_UrlReset =
{
	if (mmm_urlsok)
		buf_del(mmm_urls);
	mmm_urlsok = FALSE;
};

void(float kind) Mmm_Get =
{
	mmm_kind = kind;
	mmm_sent = time;
	mmm_req = Lob_NextReq();
	if (!uri_get(strcat(MMM_BASE, (kind == 1) ? "mapmeta.txt" : "mapdeps.txt"), mmm_req))
		mmm_req = 0;
};

// Every frame, beside Mdl_Ask: once a session, after consent.
void() Mmm_Step;
void() Mmm_Ask =
{
	if (mmm_done)
		return;
	if (mmm_job)
	{
		Mmm_Step();
		return;
	}
	if (mmm_req)
	{
		if (time - mmm_sent > 20)
		{
			mmm_req = 0;                // no answer: what was taken stands
			if (mmm_kind == 1)
				Mmm_Get(2);
			if (!mmm_req)
			{
				mmm_done = TRUE;
				mmm_fresh = mmm_took;
			}
		}
		return;
	}
	if (ms_consent < FS_TERMS_ONLINE)
		return;
	Mmm_Get(1);
	if (!mmm_req)
		mmm_done = TRUE;
};

// A space-joined line from tokens a..n-1 of the last tokenize.
string(float a, float n) Mmm_Join =
{
	local string s;
	local float i;
	s = argv(a);
	for (i = a + 1; i < n; i = i + 1)
		s = strcat(s, " ", argv(i));
	return s;
};

// "# end <rows>": the table's last line, the count of its meta or dep lines.
float(float n) Mmm_EndLine =
{
	if (n != 3 || argv(0) != "#" || argv(1) != "end" || !Mdl_Made(argv(2), MDL_DIGITS, 6))
		return -1;
	return stof(argv(2));
};

// "# stamp <14 digits>", tokenized into n tokens.
float(float n) Mmm_StampLine =
{
	if (n != 3 || argv(0) != "#" || argv(1) != "stamp")
		return FALSE;
	return Mdl_Made(argv(2), MDL_DIGITS, 14) && strlen(argv(2)) == 14;
};

// The reply written once and read back with fgets (Mdl_Reply's reason); -1 when it is not one.
float(string body, string head) Mmm_Spool =
{
	local filestream fh;
	if (strlen(body) > MMM_MAXLEN || substring(body, 0, strlen(head)) != head)
		return -1;
	fh = fopen(MMM_TMP, FILE_WRITE);
	if (fh < 0)
		return -1;
	fputs(fh, body);
	fclose(fh);
	return fopen(MMM_TMP, FILE_READ);
};

// A stranger's table is not left on disk (Mdl_Reply's rule); QC cannot delete it.
void() Mmm_Unspool =
{
	local filestream fh;
	fh = fopen(MMM_TMP, FILE_WRITE);
	if (fh >= 0)
		fclose(fh);
};

// One line of a mapmeta reply, into mmm_keep.
void(string ln) Mmm_MetaLine =
{
	local float n, i, ok;
	n = tokenize(ln);
	if (n >= 1 && argv(0) == "meta")
		mmm_seen = mmm_seen + 1;
	if (Mmm_EndLine(n) >= 0)
		mmm_endn = Mmm_EndLine(n);
	else if (Mmm_StampLine(n))
	{
		if (!mmm_st)
			bufstr_add(mmm_keep, strcat("# stamp ", argv(2)), TRUE);
		mmm_st = TRUE;
	}
	else if (n == 4 && argv(0) == "#" && argv(1) == "atlas"
	         && Mdl_Made(argv(2), MDL_DIGITS, 2) && Mdl_Made(argv(3), MDL_DIGITS, 10))
		bufstr_add(mmm_keep, strcat("# atlas ", argv(2), " ", argv(3)), TRUE);
	else if (n >= 10 && n <= 16 && argv(0) == "meta" && Mdl_Made(argv(1), MDL_NAMECH, 64))
	{
		ok = TRUE;
		for (i = 2; i < n; i = i + 1)
			if (!Mdl_Made(argv(i), MMM_FIELDCH, 64))
				ok = FALSE;
		if (ok)
		{
			bufstr_add(mmm_keep, Mmm_Join(0, n), TRUE);
			mmm_rows = mmm_rows + 1;
		}
	}
};

// The checked rows written out: the table the browser reads.
float() Mmm_PutMeta =
{
	local filestream out;
	if (mmm_rows < 100 || !mmm_st || mmm_endn != mmm_seen)
	{
		print(sprintf("^5mapmedia:^7 a table of %g rows (%g of %g at its end line) is not one -- the installed tiers stand\n",
		              mmm_rows, mmm_seen, mmm_endn));
		return FALSE;
	}
	out = fopen(MMM_META, FILE_WRITE);
	if (out < 0)
		return FALSE;
	fputs(out, "FTESURF-MAPMETA 1\n");
	buf_writefile(out, mmm_keep);   // each row and a newline: a QC loop of fputs was 37 ms
	fclose(out);
	print(sprintf("^5mapmedia:^7 %g map rows from the Pi\n", mmm_rows));
	return TRUE;
};

// The mounts mapdeps.py writes (its ADDONS); a line naming anything else is dropped.
float(string spec) Mmm_KnownMount =
{
	return spec == "steam:Team Fortress 2/tf" || spec == "steam:Counter-Strike Global Offensive/csgo"
	    || spec == "steam:Portal 2/portal2" || spec == "steam:Portal/portal";
};

// One line of a mapdeps reply, into mmm_keep.
void(string ln) Mmm_DepsLine =
{
	local string spec, nm;
	local float n, p;
	n = tokenize(ln);
	if (Mmm_EndLine(n) >= 0)
	{
		mmm_endn = Mmm_EndLine(n);
		return;
	}
	if (Mmm_StampLine(n))
	{
		if (!mmm_st)
			bufstr_add(mmm_keep, strcat("# stamp ", argv(2)), TRUE);
		mmm_st = TRUE;
		return;
	}
	// Cut, not tokenized: tokenize makes "steam:X" three tokens (ui_deps_load reads it so too).
	if (substring(ln, 0, 4) != "dep ")
		return;
	mmm_seen = mmm_seen + 1;
	p = strstrofs(ln, " ", 4);
	if (p < 0)
		return;
	nm = substring(ln, 4, p - 4);
	spec = substring(ln, p + 1, -1);
	if (substring(spec, strlen(spec) - 1, 1) == "\r")
		spec = substring(spec, 0, strlen(spec) - 1);
	if (Mdl_Made(nm, MDL_NAMECH, 64))
	if (Mmm_KnownMount(spec))
	{
		bufstr_add(mmm_keep, strcat("dep ", nm, " ", spec), TRUE);
		mmm_rows = mmm_rows + 1;
	}
};

float() Mmm_PutDeps =
{
	local filestream out;
	if (mmm_rows < 50 || !mmm_st || mmm_endn != mmm_seen)
	{
		print(sprintf("^5mapmedia:^7 a mount table of %g lines (%g of %g at its end line) is not one -- the installed one stands\n",
		              mmm_rows, mmm_seen, mmm_endn));
		return FALSE;
	}
	out = fopen(MMM_DEPS, FILE_WRITE);
	if (out < 0)
		return FALSE;
	fputs(out, "FTESURF-MAPDEPS 1\n# fetched from the Pi by the menu (P1099); the engine prefers it while its stamp is newer\n");
	buf_writefile(out, mmm_keep);
	fclose(out);
	print(sprintf("^5mapmedia:^7 %g mount lines from the Pi\n", mmm_rows));
	return TRUE;
};

// After a table, taken or not: the next fetch, or done.
void(float took) Mmm_Next =
{
	if (took)
		mmm_took = TRUE;
	if (mmm_kind == 1)
		Mmm_Get(2);
	if (!mmm_req)
	{
		mmm_done = TRUE;
		mmm_fresh = mmm_took;
	}
};

// A slice of the job's lines; at the end, the table written or refused.
void() Mmm_Step =
{
	local string ln;
	local float i, took;
	for (i = 0; i < MMM_SLICE; i = i + 1)
	{
		ln = (mmm_lines < MMM_MAXLINES) ? fgets(mmm_in) : "";
		if (ln == "")
			break;
		mmm_lines = mmm_lines + 1;
		if (mmm_job == 1)
			Mmm_MetaLine(ln);
		else
			Mmm_DepsLine(ln);
	}
	if (i == MMM_SLICE)
		return;
	fclose(mmm_in);
	Mmm_Unspool();
	took = (mmm_job == 1) ? Mmm_PutMeta() : Mmm_PutDeps();
	buf_del(mmm_keep);
	mmm_job = 0;
	Mmm_Next(took);
};

float(float reqid, float code, string body) Mmm_Reply =
{
	if (!mmm_req || reqid != mmm_req)
		return FALSE;
	mmm_req = 0;
	if (code == 0 || code == 200)
	{
		mmm_in = Mmm_Spool(body, (mmm_kind == 1) ? "FTESURF-MAPMETA 1" : "FTESURF-MAPDEPS 1");
		if (mmm_in >= 0)
		{
			fgets(mmm_in);              // the magic line
			mmm_keep = buf_create();
			mmm_rows = mmm_lines = mmm_st = mmm_seen = 0;
			mmm_endn = -1;
			mmm_job = mmm_kind;         // Mmm_Ask steps it from the next frame
			return TRUE;
		}
	}
	else
		print(sprintf("^5mapmedia:^7 the Pi answered %g -- the installed tables stand\n", code));
	Mmm_Next(FALSE);
	return TRUE;
};
