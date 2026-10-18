/*
  Steam pictures (Patch 640).  A linked player's picture beside their name, by
  the 8-hex mark a lobby publishes as *phash and FS_GuidId of a board row's
  `player` gives.  surfd serves a 32 x 32 RGBA copy as hex text
  (/api/board?avatar=<mark>, Patch 639): uri_get hands QuakeC a string, and
  r_uploadimage takes the pixels.

  ASKS ARE PACED AND REMEMBERED.  Each one spends the board's own budget on
  surfd (120 a minute), so one is in flight at a time, SP_GAP apart, only for
  a mark something drew within SP_SEEN, and a mark with no picture is not
  asked again for SP_MISS.  A texture is named by its slot, so a reused slot
  uploads over the old picture and nothing accumulates.

  WHAT IS NOT AN ANSWER STOPS THE ASKING, not just the mark.  A 429 or a 5xx
  is the directory's trouble: the mark stays wanted and everything waits
  SP_PAUSE, and after SP_STRIKES of those in a row the map goes without.
  NOTHING IS ASKED WHILE ONE IS UNANSWERED, however long: the engine has
  four HTTP threads for the board, replays, zones and the menu together and
  no timeout of its own (httpclient.c), so each request given up on and
  replaced is one of the four.  A late answer is still taken.  One slower
  than SP_TIMEOUT also sets `_steampic_hold` (a console variable, so it
  outlives a map's VM; not saved): no asks before that engine time.

  The tables are memalloc'd: csprogs sits at fteqcc's global limit.
*/
#define SPIC_MAX  64            // every lobby slot; overhead labels must not thrash 32 slots
#define SP_PX     32
#define SP_HEAD   23            // "FTESURF-AVATAR 1 32 32\n"
#define SP_ROW    257           // 32 pixels of 8 hex, and the newline
#define SP_ROUND  6             // corner radius, px of SP_PX: the site's 4 of 20
#define SP_GAP    1.5
#define SP_SEEN   3
#define SP_MISS   900
#define SP_PAUSE  60
#define SP_STRIKES 3
#define SP_TIMEOUT 20

#define SP_FREE   0
#define SP_WANT   1
#define SP_ASK    2
#define SP_HAVE   3
#define SP_NOPIC  4
#define SP_HTTP   5             // wanted, and the disk had none: an ask's turn
#define SP_OLD    6             // drawn from a disk copy of an earlier day; refresh owed
#define SP_FRESH  7             // SP_OLD with its refresh in flight; still drawn
#define SP_DISKDAYS 30          // a disk copy older than this is not drawn
#define SP_DISKBURST 2          // disk loads a frame; only asks are paced

float  sp_bmark;                // strbuf: the mark each slot holds
float  *sp_st;                  // one declarator a line: `float *a, *b` makes b a float**
float  *sp_at;
float  *sp_used;
float  sp_req, sp_reqslot, sp_next;
float  sp_base;                 // this VM's request ids: see SteamPic_Alloc
float  sp_bad;                  // non-answers in a row; SP_STRIKES ends the asking this map
float  sp_slow;                 // the request in flight is past SP_TIMEOUT, and said so
float  sp_asked, sp_got, sp_disk; // counts, for `scores pics`
float  sp_dage;                 // age in days of the copy SP_DiskLoad last returned
string sp_origin;              // directory that owns these marks/pictures
float(float reqid, float code, string bdy) SteamPic_Reply;
float(float slot, string bdy) SP_Upload;

// One file per origin+mark SHA256 (P755). P715's 256 two-hex buckets evicted
// each other and expired every (local) day; they are still read, never written.
// The stamp is strftime(TRUE): the local date, read and written alike.
string(string mark) SP_DiskKey =
{
	local string key;
	key = strtolower(digest_hex("SHA256", strcat(sp_origin, "\n", mark)));
	if (strlen(key) != 64) return "";
	return key;
};
string(string key) SP_DiskPath =
{
	return strcat("cache/steampic/", key, ".txt");
};
string(string key) SP_DiskHeader =
{
	return sprintf("FTESURF-AVCACHE1 %s %s", key, strftime(TRUE, "%Y%m%d"));
};
// Days since 1970-01-01 of a YYYYMMDD stamp, or -1 (Hinnant's days_from_civil).
float(string ymd) SP_Day =
{
	local float i, y, m, d, era, yoe;
	if (strlen(ymd) != 8) return -1;
	for (i = 0; i < 8; i = i + 1)
		if (strstrofs("0123456789", substring(ymd, i, 1), 0) < 0)
			return -1;
	y = stof(substring(ymd, 0, 4));
	m = stof(substring(ymd, 4, 2));
	d = stof(substring(ymd, 6, 2));
	if (m < 1 || m > 12 || d < 1 || d > 31) return -1;
	if (m <= 2) y = y - 1;
	era = floor(y / 400);
	yoe = y - era * 400;
	if (m > 2) m = m - 3; else m = m + 9;
	return era * 146097 + yoe * 365 + floor(yoe / 4) - floor(yoe / 100)
	       + floor((153 * m + 2) / 5) + d - 1 - 719468;
};
string(string path, string key) SP_DiskRead =
{
	local string hdr, body, line;
	local float fh, i, age;
	fh = fopen(path, FILE_READ);
	if (fh < 0) return "";
	if (fsize(fh) > SP_HEAD + SP_PX * SP_ROW + 128)
	{
		fclose(fh);
		return "";
	}
	// "FTESURF-AVCACHE1 <key> <YYYYMMDD>": the key is the identity, the date its age.
	hdr = fgets(fh);
	age = -1;
	if (strlen(hdr) == 17 + 64 + 1 + 8)
	if (!strcmp(substring(hdr, 0, 17 + 64 + 1), strcat("FTESURF-AVCACHE1 ", key, " ")))
		age = SP_Day(strftime(TRUE, "%Y%m%d")) - SP_Day(substring(hdr, 17 + 64 + 1, 8));
	if (age < 0 || age > SP_DISKDAYS)
	{
		fclose(fh);
		return "";
	}
	body = "";
	for (i = 0; i <= SP_PX; i = i + 1)
	{
		line = fgets(fh);
		body = strcat(body, line, "\n");
	}
	fclose(fh);
	sp_dage = age;
	return body; // SP_Upload validates every byte before rendering or keeping it
};
string(string mark) SP_DiskLoad =
{
	local string key, body;
	key = SP_DiskKey(mark);
	if (!strlen(key)) return "";
	body = SP_DiskRead(SP_DiskPath(key), key);
	if (!strlen(body))
		body = SP_DiskRead(strcat("cache/steampic/", substring(key, 0, 2), ".txt"), key);
	return body;
};
void(string mark) SP_DiskForget =
{
	local string key;
	key = SP_DiskKey(mark);
	if (strlen(key)) fremove(SP_DiskPath(key));
};
void(string mark, string body) SP_DiskStore =
{
	local string key, dst, part;
	local float fh;
	key = SP_DiskKey(mark);
	if (!strlen(key)) return;
	dst = SP_DiskPath(key);
	part = strcat(dst, ".part");
	fh = fopen(part, FILE_WRITE);
	if (fh < 0) return;             // read-only installs still draw
	fputs(fh, strcat(SP_DiskHeader(key), "\n", body));
	fclose(fh);
	fremove(dst);                   // Windows rename cannot replace
	if (frename(part, dst) != 0) fremove(part);
};

void() SteamPic_Alloc =
{
	if (sp_st)
		return;
	sp_bmark = buf_create();
	sp_st = memalloc(sizeof(float) * SPIC_MAX);   // zeroed (pr_bgcmd.c PF_memalloc)
	sp_at = memalloc(sizeof(float) * SPIC_MAX);
	sp_used = memalloc(sizeof(float) * SPIC_MAX);
	// Ids of our own, from a base drawn per VM.  Online_NextReq restarts at 1
	// with every map, the engine's stale test does not cover CSQC, and a reply
	// names no mark: the last map's late answer with this map's id would be
	// kept as somebody else's picture.
	sp_base = 1000000 + floor(random() * 1000) * 4000;
};

/*
  Patch 781: THE MARKS A PREFETCHED BOARD WILL SHOW (cl_online.qc), asked while
  nothing on screen wants one and kept on disk only -- no slot, so they never
  push a drawn picture out.  A mark with a copy from today is skipped; the
  first draw then loads it from disk in a frame.
*/
#define SP_WARMMAX 64
float  sp_warm;                 // strbuf of marks, in the order the boards gave them
float  sp_warmn, sp_warmi, sp_wreq, sp_wat, sp_wgot;
string sp_wmark;

void(string mark) SteamPic_Warm =
{
	local float i;

	if (strlen(mark) != 8)
		return;
	for (i = 0; i < 8; i = i + 1)
		if (strstrofs("0123456789abcdef", substring(mark, i, 1), 0) < 0)
			return;
	SteamPic_Alloc();
	if (!sp_warm)
		sp_warm = buf_create();
	if (sp_warmn >= SP_WARMMAX)
		return;
	for (i = 0; i < sp_warmn; i = i + 1)
		if (!strcmp(bufstr_get(sp_warm, i), mark))
			return;
	bufstr_set(sp_warm, sp_warmn, mark);
	sp_warmn = sp_warmn + 1;
};

// The next warm mark without a copy from today, asked; SP_DISKBURST disk looks a frame.
void() SP_WarmAsk =
{
	local string mark;
	local float n;

	for (n = 0; n < SP_DISKBURST && sp_warmi < sp_warmn; n = n + 1)
	{
		mark = bufstr_get(sp_warm, sp_warmi);
		sp_warmi = sp_warmi + 1;
		if (strlen(SP_DiskLoad(mark)))
		if (sp_dage == 0)
			continue;
		sp_next = cltime + SP_GAP;
		sp_wat = cltime;
		sp_wreq = sp_base + sp_asked - floor(sp_asked / 4000) * 4000;
		sp_asked = sp_asked + 1;
		if (sp_wmark != "") strunzone(sp_wmark);
		sp_wmark = strzone(mark);
		if (!uri_get(sprintf("%s/api/board?avatar=%s", cvar_string("lobby_dir"), mark), sp_wreq))
		{
			sp_wreq = 0;
			sp_next = cltime + SP_PAUSE;
			sp_bad = sp_bad + 1;
		}
		return;
	}
};

// The image to draw for a mark, or "" while there is none: then the mark is
// noted, and asked for when its turn comes.
string(string mark) SteamPic_Of =
{
	local float i, old;

	if (mark == "")
		return "";
	SteamPic_Alloc();
	old = -1;
	for (i = 0; i < SPIC_MAX; i = i + 1)
		if (sp_st[i])
		if (!strcmp(bufstr_get(sp_bmark, i), mark))
		{
			old = i;
			break;
		}
	if (old < 0)
	{
		// A mark reaches a URL, and *phash is whatever the server says it is.
		if (strlen(mark) != 8)
			return "";
		for (i = 0; i < 8; i = i + 1)
			if (strstrofs("0123456789abcdef", substring(mark, i, 1), 0) < 0)
				return "";
		// A free slot, else the one drawn longest ago; never the one in flight,
		// and never one still on screen (more marks in view than slots would
		// otherwise fetch each other out for ever).
		for (i = 0; i < SPIC_MAX; i = i + 1)
		{
			if (!sp_st[i])
			{
				old = i;
				break;
			}
			if (sp_st[i] == SP_ASK || sp_st[i] == SP_FRESH)
				continue;
			if (old < 0)
				old = i;
			else if (sp_used[i] < sp_used[old])
				old = i;
		}
		if (old < 0)
			return "";
		if (sp_st[old])
		if (cltime - sp_used[old] < SP_SEEN)
			return "";
		bufstr_set(sp_bmark, old, mark);
		sp_st[old] = SP_WANT;
		sp_at[old] = 0;
	}
	sp_used[old] = cltime;
	if (sp_st[old] != SP_HAVE)
	if (sp_st[old] != SP_OLD)
	if (sp_st[old] != SP_FRESH)
		return "";
	return sprintf("steampic/%g", old);
};

// A mark's picture at `pos`, `px` square.  TRUE if there was one to draw.
// sui_pic and not drawpic: a list row's position is its frame's, not the
// screen's (the first cut drew nothing a screenshot could find).
float(vector pos, float px, string mark, float a) SteamPic_Draw =
{
	mark = SteamPic_Of(mark);
	if (mark == "")
		return FALSE;
	sui_pic(pos, [px, px], mark, '1 1 1', a, 0);
	return TRUE;
};

// The renderer restarted (vid_restart, F11): its textures and shaders are
// gone.  A held name drawn now would get drawpic's default shader, and keep
// it (a name is never redefined): fetch them again first.
void() SteamPic_Lost =
{
	local float i;

	if (!sp_st)
		return;
	for (i = 0; i < SPIC_MAX; i = i + 1)
	{
		if (sp_st[i] == SP_HAVE || sp_st[i] == SP_OLD)
			sp_st[i] = SP_WANT;     // the disk copy uploads again at once
		if (sp_st[i] == SP_FRESH)
			sp_st[i] = SP_ASK;      // in flight, and nothing left to draw meanwhile
	}
};

// Once a frame: disk copies of marks being drawn, SP_DISKBURST at once, then at
// most one paced ask: a mark the disk had none of, else a refresh of an old copy.
// The consent and lobby_dir rules are Online_Fetch's.
void() SteamPic_Frame =
{
	local float i, n;
	local string cached, base;

	if (!sp_st)
		return;                             // nothing has wanted one yet
	if (sp_req)
	if (!sp_slow)
	if (cltime - sp_at[sp_reqslot] > SP_TIMEOUT)
	{
		// Still out past SP_TIMEOUT: tell the maps after this one too.
		// gettime(0) is the engine's clock; cltime restarts each map.
		sp_slow = TRUE;
		localcmd(sprintf("set _steampic_hold %g\n", gettime(0) + SP_MISS));
	}
	if (ui_consent_ver < FS_TERMS_ONLINE)
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
		return;
	base = cvar_string("lobby_dir");
	if (base == "")
		return;
	if (strcmp(base, sp_origin))
	{
		if (sp_req)
			return;                         // the answer out belongs to the old origin
		if (sp_origin != "") strunzone(sp_origin);
		sp_origin = strzone(base);
		for (i = 0; i < SPIC_MAX; i = i + 1)
			if (sp_st[i]) sp_st[i] = SP_WANT;
	}

	n = 0;
	for (i = 0; i < SPIC_MAX; i = i + 1)
	{
		if (n >= SP_DISKBURST)
			break;
		if (sp_st[i] != SP_WANT)
			continue;
		if (cltime - sp_used[i] > SP_SEEN)
			continue;
		n = n + 1;
		cached = SP_DiskLoad(bufstr_get(sp_bmark, i));
		if (strlen(cached))
		if (SP_Upload(i, cached))
		{
			sp_st[i] = SP_HAVE;
			if (sp_dage > 0)
				sp_st[i] = SP_OLD;
			sp_disk = sp_disk + 1;
			continue;
		}
		sp_st[i] = SP_HTTP;                 // none, or corrupt: an ordinary miss
	}

	if (n >= SP_DISKBURST)
		return;                             // the disk first: more may be waiting
	if (sp_req)
		return;
	if (sp_wreq)
	{
		if (cltime - sp_wat > SP_TIMEOUT)
			sp_wreq = 0;               // written off; its late answer matches nothing
		return;
	}
	if (sp_bad >= SP_STRIKES)
		return;
	if (cltime < sp_next)
		return;
	if (gettime(0) < cvar("_steampic_hold"))
		return;
	for (i = 0; i < SPIC_MAX; i = i + 1)
	{
		if (cltime - sp_used[i] > SP_SEEN)
			continue;
		if (sp_st[i] == SP_NOPIC)
		if (cltime - sp_at[i] > SP_MISS)
			sp_st[i] = SP_HTTP;
		if (sp_st[i] == SP_HTTP)
			break;
	}
	if (i >= SPIC_MAX)
		for (i = 0; i < SPIC_MAX; i = i + 1)
			if (sp_st[i] == SP_OLD)
			if (cltime - sp_used[i] <= SP_SEEN)
				break;
	if (i >= SPIC_MAX)
	{
		SP_WarmAsk();                   // nothing drawn wants one
		return;
	}

	sp_next = cltime + SP_GAP;
	sp_at[i] = cltime;
	sp_req = sp_base + sp_asked - floor(sp_asked / 4000) * 4000;
	sp_reqslot = i;
	if (!uri_get(sprintf("%s/api/board?avatar=%s", cvar_string("lobby_dir"),
	                     bufstr_get(sp_bmark, i)), sp_req))
	{
		sp_req = 0;
		sp_next = cltime + SP_PAUSE;
		sp_bad = sp_bad + 1;
		return;
	}
	if (sp_st[i] == SP_OLD)
		sp_st[i] = SP_FRESH;
	else
		sp_st[i] = SP_ASK;
	sp_asked = sp_asked + 1;
};

// A body's pixels into slot `slot`'s texture.  TRUE only for a whole, valid picture.
float(float slot, string bdy) SP_Upload =
{
	local float i, o, x, y;
	local string digit;
	local int hi, lo, a, seen;
	local int *px;

	if (strlen(bdy) != SP_HEAD + SP_PX * SP_ROW)
		return FALSE;
	if (strcmp(substring(bdy, 0, SP_HEAD), "FTESURF-AVATAR 1 32 32\n"))
		return FALSE;

	// A damaged disk file must not be silently interpreted as black pixels.
	for (i = SP_HEAD; i < strlen(bdy); i = i + 1)
	{
		digit = substring(bdy, i, 1);
		if (floor((i - SP_HEAD + 1) / SP_ROW) * SP_ROW == i - SP_HEAD + 1)
		{
			if (strcmp(digit, "\n")) return FALSE;
		}
		else if (strstrofs("0123456789abcdef", digit, 0) < 0) return FALSE;
	}

	// "rrggbbaa" a pixel; memory order is r, g, b, a.  Four hex digits at a
	// time: eight would not fit a signed int.  The corners are rounded here,
	// in the alpha: how far a pixel's centre is past the corner's arc.
	px = memalloc(SP_PX * SP_PX * 4);
	seen = 0;
	for (i = 0; i < SP_PX * SP_PX; i = i + 1)
	{
		y = floor(i / SP_PX);
		x = i - y * SP_PX;
		o = SP_HEAD + y * SP_ROW + x * 8;
		hi = stoh(substring(bdy, o, 4));
		lo = stoh(substring(bdy, o + 4, 4));
		seen = seen | (lo & 255);
		x = max(SP_ROUND - x - 0.5, x + 0.5 - (SP_PX - SP_ROUND));
		y = max(SP_ROUND - y - 0.5, y + 0.5 - (SP_PX - SP_ROUND));
		o = 1;
		if (x > 0)
		if (y > 0)
			o = bound(0, SP_ROUND + 0.5 - sqrt(x * x + y * y), 1);
		a = (int)((lo & 255) * o);
		px[i] = (hi >> 8) | ((hi & 255) << 8) | ((lo >> 8) << 16) | (a << 24);
	}
	if (!seen)
	{
		memfree(px);                        // nothing opaque: junk of the right length
		return FALSE;
	}
	r_uploadimage(sprintf("steampic/%g", slot), SP_PX, SP_PX, px);
	memfree(px);
	// A shader of our own, once per slot.  drawpic's default loads its picture
	// PREMULTIPLIED (gl_shader.c Shader_Default2D), which is another texture
	// than the one just uploaded: it drew the engine's missing-texture checker.
	shaderforname(sprintf("steampic/%g", slot),
	              sprintf("{\naffine\nnomipmaps\nprogram default2d\n{\nclampmap steampic/%g\nblendfunc blend\n}\nsort additive\n}\n",
	                      slot));
	return TRUE;
};

// Its answer (URI_Get_Callback).  TRUE when the id was this request's.
float(float reqid, float code, string bdy) SteamPic_Reply =
{
	if (sp_wreq)
	if (reqid == sp_wreq)
	{
		sp_wreq = 0;
		if (code)
		if (code != 404)
		{
			sp_next = cltime + SP_PAUSE;
			sp_bad = sp_bad + 1;
			return TRUE;
		}
		sp_bad = 0;
		if (!code)
		if (strlen(bdy) == SP_HEAD + SP_PX * SP_ROW)
		if (!strcmp(substring(bdy, 0, SP_HEAD), "FTESURF-AVATAR 1 32 32\n"))
		{
			SP_DiskStore(sp_wmark, bdy);
			sp_wgot = sp_wgot + 1;
		}
		return TRUE;
	}
	if (!sp_req)
		return FALSE;
	if (reqid != sp_req)
		return FALSE;
	sp_req = 0;
	sp_at[sp_reqslot] = cltime;
	if (sp_slow)
	{
		sp_slow = FALSE;                    // late, but an answer: the hold comes off
		localcmd("set _steampic_hold 0\n");
	}
	if (code)                               // 0 is success (cl_online.qc, trap 1)
	if (code != 404)
	{
		// Not an answer: ask again later; an old copy stays on screen meanwhile.
		if (sp_st[sp_reqslot] == SP_FRESH)
			sp_st[sp_reqslot] = SP_OLD;
		else
			sp_st[sp_reqslot] = SP_WANT;    // the disk first: after vid_restart a copy is there
		sp_next = cltime + SP_PAUSE;
		sp_bad = sp_bad + 1;
		return TRUE;
	}
	sp_bad = 0;
	if (!code)
	if (SP_Upload(sp_reqslot, bdy))
	{
		SP_DiskStore(bufstr_get(sp_bmark, sp_reqslot), bdy);
		sp_st[sp_reqslot] = SP_HAVE;
		sp_got = sp_got + 1;
		return TRUE;
	}
	if (code == 404)
		SP_DiskForget(bufstr_get(sp_bmark, sp_reqslot));
	sp_st[sp_reqslot] = SP_NOPIC;           // a 404, or a body that is no picture
	return TRUE;
};

// `scores pics`: what the cache holds, for an arm to grade.
void() SteamPic_Status =
{
	local float i;

	print(sprintf("steampic: asked %g got %g inflight %g strikes %g hold %g\n", sp_asked, sp_got,
	              sp_req ? 1 : 0, sp_bad, max(0, cvar("_steampic_hold") - gettime(0))));
	print(sprintf("steampic: disk hits %g (a file a mark, %g days)\n", sp_disk, SP_DISKDAYS));
	print(sprintf("steampic: ahead of the board %g queued, %g looked at, %g kept\n", sp_warmn, sp_warmi, sp_wgot));
	if (sp_st)
	for (i = 0; i < SPIC_MAX; i = i + 1)
		if (sp_st[i])
			print(sprintf("steampic: slot %g mark %s state %g\n", i, bufstr_get(sp_bmark, i), sp_st[i]));
};
