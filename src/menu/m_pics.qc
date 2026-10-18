/*
  Patch 789: Steam pictures in the menu, as cl_steampic.qc draws them in game.
  The game's disk copies first (cache/steampic/<sha256(lobby_dir "\n" mark)>.txt,
  "FTESURF-AVCACHE1 <key> <YYYYMMDD>" then the body), else one paced ask of
  <lobby_dir>/api/board?avatar=<mark> -- the board's shared budget, so one in
  flight, MP_GAP apart, only for a mark drawn within MP_SEEN.  No stoh in the
  menu VM: the hex is read a digit at a time.
*/
#define MP_MAX    24
#define MP_PX     32
#define MP_HEAD   23            // "FTESURF-AVATAR 1 32 32\n"
#define MP_ROW    257
#define MP_ROUND  6
#define MP_GAP    1.5
#define MP_SEEN   3
#define MP_MISS   900
#define MP_DAYS   30

#define MP_FREE   0
#define MP_WANT   1
#define MP_ASK    2
#define MP_HAVE   3
#define MP_NOPIC  4

float  mp_bmark;                // strbuf: each slot's mark
float  mp_st[MP_MAX];
float  mp_used[MP_MAX];
float  mp_at[MP_MAX];
float  mp_disked[MP_MAX];       // the disk was tried for this slot's mark
float  mp_req, mp_slot, mp_next, mp_asked, mp_got, mp_disk, mp_base;
string mp_origin;

float(string ch) MP_Hex1 = { return strstrofs("0123456789abcdef", ch, 0); };

int(string s) MP_Hex4 =
{
	return (int)(MP_Hex1(substring(s, 0, 1)) * 4096 + MP_Hex1(substring(s, 1, 1)) * 256
	           + MP_Hex1(substring(s, 2, 1)) * 16 + MP_Hex1(substring(s, 3, 1)));
};

string(string mark) MP_Key =
{
	local string key;
	key = strtolower(digest_hex("SHA256", strcat(mp_origin, "\n", mark)));
	return (strlen(key) == 64) ? key : "";
};

// Days since 1970-01-01 of a YYYYMMDD stamp, or -1 (cl_steampic.qc's SP_Day).
float(string ymd) MP_Day =
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

string(string mark) MP_DiskRead =
{
	local string key, hdr, body;
	local float fh, i, age;
	key = MP_Key(mark);
	if (key == "") return "";
	fh = fopen(strcat("cache/steampic/", key, ".txt"), FILE_READ);
	if (fh < 0) return "";
	if (fsize(fh) > MP_HEAD + MP_PX * MP_ROW + 128) { fclose(fh); return ""; }
	hdr = fgets(fh);
	age = -1;
	if (strlen(hdr) == 17 + 64 + 1 + 8)
	if (!strcmp(substring(hdr, 0, 17 + 64 + 1), strcat("FTESURF-AVCACHE1 ", key, " ")))
		age = MP_Day(strftime(TRUE, "%Y%m%d")) - MP_Day(substring(hdr, 17 + 64 + 1, 8));
	if (age < 0 || age > MP_DAYS) { fclose(fh); return ""; }
	body = "";
	for (i = 0; i <= MP_PX; i = i + 1)
		body = strcat(body, fgets(fh), "\n");
	fclose(fh);
	return body;                    // MP_Upload validates every byte
};

void(string mark, string body) MP_DiskStore =
{
	local string key, dst;
	local float fh;
	key = MP_Key(mark);
	if (key == "") return;
	// Written in place (fremove/frename are declared after this file); both
	// readers validate the whole body, so a torn write is only a miss.
	dst = strcat("cache/steampic/", key, ".txt");
	fh = fopen(dst, FILE_WRITE);
	if (fh < 0) return;
	fputs(fh, sprintf("FTESURF-AVCACHE1 %s %s\n%s", key, strftime(TRUE, "%Y%m%d"), body));
	fclose(fh);
};

// A body's pixels into slot `slot`'s texture.  TRUE only for a whole, valid picture.
float(float slot, string bdy) MP_Upload =
{
	local float i, o, x, y;
	local int hi, lo, a, seen;
	local int *px;

	if (strlen(bdy) != MP_HEAD + MP_PX * MP_ROW) return FALSE;
	if (strcmp(substring(bdy, 0, MP_HEAD), "FTESURF-AVATAR 1 32 32\n")) return FALSE;
	for (i = MP_HEAD; i < strlen(bdy); i = i + 1)
	{
		if (floor((i - MP_HEAD + 1) / MP_ROW) * MP_ROW == i - MP_HEAD + 1)
		{
			if (strcmp(substring(bdy, i, 1), "\n")) return FALSE;
		}
		else if (MP_Hex1(substring(bdy, i, 1)) < 0) return FALSE;
	}
	px = memalloc(MP_PX * MP_PX * 4);
	seen = 0;
	for (i = 0; i < MP_PX * MP_PX; i = i + 1)
	{
		y = floor(i / MP_PX);
		x = i - y * MP_PX;
		o = MP_HEAD + y * MP_ROW + x * 8;
		hi = MP_Hex4(substring(bdy, o, 4));
		lo = MP_Hex4(substring(bdy, o + 4, 4));
		seen = seen | (lo & 255);
		x = max(MP_ROUND - x - 0.5, x + 0.5 - (MP_PX - MP_ROUND));
		y = max(MP_ROUND - y - 0.5, y + 0.5 - (MP_PX - MP_ROUND));
		o = 1;
		if (x > 0)
		if (y > 0)
			o = bound(0, MP_ROUND + 0.5 - sqrt(x * x + y * y), 1);
		a = (int)((lo & 255) * o);
		px[i] = (hi >> 8) | ((hi & 255) << 8) | ((lo >> 8) << 16) | (a << 24);
	}
	if (!seen) { memfree(px); return FALSE; }
	r_uploadimage(sprintf("menupic/%g", slot), MP_PX, MP_PX, px);
	memfree(px);
	shaderforname(sprintf("menupic/%g", slot),
	              sprintf("{\naffine\nnomipmaps\nprogram default2d\n{\nclampmap menupic/%g\nblendfunc blend\n}\nsort additive\n}\n", slot));
	return TRUE;
};

string(string mark) MP_Of =
{
	local float i, old;

	if (strlen(mark) != 8 || mp_origin == "") return "";
	if (mp_bmark <= 0) mp_bmark = buf_create();
	old = -1;
	for (i = 0; i < MP_MAX; i = i + 1)
		if (mp_st[i])
		if (!strcmp(bufstr_get(mp_bmark, i), mark)) { old = i; break; }
	if (old < 0)
	{
		for (i = 0; i < 8; i = i + 1)
			if (MP_Hex1(substring(mark, i, 1)) < 0) return "";
		for (i = 0; i < MP_MAX; i = i + 1)
		{
			if (!mp_st[i]) { old = i; break; }
			if (mp_st[i] == MP_ASK) continue;
			// Nested: QC's || evaluates both sides, and mp_used[-1] fails the bound check (P795).
			if (old < 0)
				old = i;
			else if (mp_used[i] < mp_used[old])
				old = i;
		}
		if (old < 0) return "";
		if (mp_st[old])
		if (time - mp_used[old] < MP_SEEN) return "";        // all on screen: no thrash
		bufstr_set(mp_bmark, old, mark);
		mp_st[old] = MP_WANT;
		mp_at[old] = 0;
		mp_disked[old] = FALSE;     // MP_Frame tries the disk, two a frame
	}
	mp_used[old] = time;
	return (mp_st[old] == MP_HAVE) ? sprintf("menupic/%g", old) : "";
};

// A mark's picture at `pos`, `px` square (a frame position, like sui_text's).
float(vector pos, float px, string mark, float a) MP_Draw =
{
	local string img;
	img = MP_Of(mark);
	if (img == "") return FALSE;
	sui_pic(pos, [px, px], img, '1 1 1', a, 0);
	return TRUE;
};

// The renderer restarted (vid_restart, F11): every uploaded picture went with it.
void() MP_Lost =
{
	local float i;
	for (i = 0; i < MP_MAX; i = i + 1)
		if (mp_st[i] == MP_HAVE)
			mp_st[i] = MP_FREE;
};

// Once a menu frame (m_draw).  The consent and lobby_dir rules are the game's.
void() MP_Frame =
{
	local float i, n;
	local string base, body;

	if (cvar("rec_terms") < FS_TERMS_ONLINE) return;
	base = cvar_string("lobby_dir");
	if (base == "") return;
	// The engine's HTTP client has no timeout: give up on an answer after 20 s.
	if (mp_req)
	if (time - mp_at[mp_slot] > 20)
	{
		mp_req = 0;
		if (mp_st[mp_slot] == MP_ASK) mp_st[mp_slot] = MP_WANT;
		mp_next = time + 60;
	}
	if (strcmp(base, mp_origin))
	{
		if (mp_req) return;                 // the answer out belongs to the old origin
		if (mp_origin != "") strunzone(mp_origin);
		mp_origin = strzone(base);
		for (i = 0; i < MP_MAX; i = i + 1)
			mp_st[i] = MP_FREE;
		return;
	}
	// Disk copies first, two a frame (cl_steampic.qc's SP_DISKBURST).
	n = 0;
	for (i = 0; i < MP_MAX && n < 2; i = i + 1)
	{
		if (mp_st[i] != MP_WANT || mp_disked[i]) continue;
		mp_disked[i] = TRUE;
		n = n + 1;
		body = MP_DiskRead(bufstr_get(mp_bmark, i));
		if (body != "")
		if (MP_Upload(i, body))
		{
			mp_st[i] = MP_HAVE;
			mp_disk = mp_disk + 1;
		}
	}
	if (mp_req || time < mp_next) return;
	for (i = 0; i < MP_MAX; i = i + 1)
	{
		if (time - mp_used[i] > MP_SEEN) continue;
		if (mp_st[i] == MP_NOPIC)
		if (time - mp_at[i] > MP_MISS)
			mp_st[i] = MP_WANT;
		if (mp_st[i] == MP_WANT && mp_disked[i]) break;
	}
	if (i >= MP_MAX) return;
	// Ids of this menu VM's own: a late answer to the last VM's ask is not ours.
	if (!mp_base) mp_base = 900000 + floor(random() * 90000) * 10;
	mp_next = time + MP_GAP;
	mp_at[i] = time;
	mp_slot = i;
	mp_asked = mp_asked + 1;
	mp_req = mp_base + mp_asked;
	if (!uri_get(sprintf("%s/api/board?avatar=%s", base, bufstr_get(mp_bmark, i)), mp_req))
	{
		mp_req = 0;
		mp_next = time + 60;            // the directory's trouble: the mark stays wanted
		return;
	}
	mp_st[i] = MP_ASK;
};

float(float reqid, float code, string bdy) MP_Reply =
{
	if (!mp_req || reqid != mp_req) return FALSE;
	mp_req = 0;
	if (mp_st[mp_slot] != MP_ASK) return TRUE;                 // the origin changed under it
	if (code == 0)
	if (MP_Upload(mp_slot, bdy))
	{
		mp_st[mp_slot] = MP_HAVE;
		mp_got = mp_got + 1;
		MP_DiskStore(bufstr_get(mp_bmark, mp_slot), substring(bdy, 0, MP_HEAD + MP_PX * MP_ROW));
		return TRUE;
	}
	// A 429 or a 5xx is the directory's trouble, not the mark's: wait, keep it wanted.
	if (code >= 500 || code == 429 || code < 0)
	{
		mp_st[mp_slot] = MP_WANT;
		mp_next = time + 60;
		return TRUE;
	}
	mp_st[mp_slot] = MP_NOPIC;
	return TRUE;
};
