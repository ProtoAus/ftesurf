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
#define SP_MAX    32
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

float  sp_bmark;                // strbuf: the mark each slot holds
float  *sp_st;                  // one declarator a line: `float *a, *b` makes b a float**
float  *sp_at;
float  *sp_used;
float  sp_req, sp_reqslot, sp_next;
float  sp_base;                 // this VM's request ids: see SteamPic_Alloc
float  sp_bad;                  // non-answers in a row; SP_STRIKES ends the asking this map
float  sp_slow;                 // the request in flight is past SP_TIMEOUT, and said so
float  sp_asked, sp_got;        // counts, for `scores pics`

void() SteamPic_Alloc =
{
	if (sp_st)
		return;
	sp_bmark = buf_create();
	sp_st = memalloc(sizeof(float) * SP_MAX);   // zeroed (pr_bgcmd.c PF_memalloc)
	sp_at = memalloc(sizeof(float) * SP_MAX);
	sp_used = memalloc(sizeof(float) * SP_MAX);
	// Ids of our own, from a base drawn per VM.  Online_NextReq restarts at 1
	// with every map, the engine's stale test does not cover CSQC, and a reply
	// names no mark: the last map's late answer with this map's id would be
	// kept as somebody else's picture.
	sp_base = 1000000 + floor(random() * 1000) * 4000;
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
	for (i = 0; i < SP_MAX; i = i + 1)
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
		for (i = 0; i < SP_MAX; i = i + 1)
		{
			if (!sp_st[i])
			{
				old = i;
				break;
			}
			if (sp_st[i] == SP_ASK)
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
	for (i = 0; i < SP_MAX; i = i + 1)
		if (sp_st[i] == SP_HAVE)
			sp_st[i] = SP_WANT;
};

// Once a frame: at most one ask, for a mark still being drawn.  The consent
// and lobby_dir rules are Online_Fetch's.
void() SteamPic_Frame =
{
	local float i;

	if (!sp_st)
		return;                             // nothing has wanted one yet
	if (sp_req)
	{
		// Still out: wait for it, and past SP_TIMEOUT tell the maps after this
		// one too.  gettime(0) is the engine's clock; cltime restarts each map.
		if (!sp_slow)
		if (cltime - sp_at[sp_reqslot] > SP_TIMEOUT)
		{
			sp_slow = TRUE;
			localcmd(sprintf("set _steampic_hold %g\n", gettime(0) + SP_MISS));
		}
		return;
	}
	if (sp_bad >= SP_STRIKES)
		return;
	if (cltime < sp_next)
		return;
	if (gettime(0) < cvar("_steampic_hold"))
		return;
	if (ui_consent_ver < FS_TERMS_ONLINE)
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
		return;
	if (cvar_string("lobby_dir") == "")
		return;

	for (i = 0; i < SP_MAX; i = i + 1)
	{
		if (cltime - sp_used[i] > SP_SEEN)
			continue;
		if (sp_st[i] == SP_NOPIC)
		if (cltime - sp_at[i] > SP_MISS)
			sp_st[i] = SP_WANT;
		if (sp_st[i] == SP_WANT)
			break;
	}
	if (i >= SP_MAX)
		return;

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
	sp_st[i] = SP_ASK;
	sp_asked = sp_asked + 1;
};

// Its answer (URI_Get_Callback).  TRUE when the id was this request's.
float(float reqid, float code, string bdy) SteamPic_Reply =
{
	local float i, o, x, y;
	local int hi, lo, a, seen;
	local int *px;

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
		sp_st[sp_reqslot] = SP_WANT;
		sp_next = cltime + SP_PAUSE;
		sp_bad = sp_bad + 1;
		return TRUE;
	}
	sp_bad = 0;
	sp_st[sp_reqslot] = SP_NOPIC;           // a 404, or a body that is no picture
	if (code)
		return TRUE;
	if (strlen(bdy) != SP_HEAD + SP_PX * SP_ROW)
		return TRUE;
	if (substring(bdy, 0, SP_HEAD) != "FTESURF-AVATAR 1 32 32\n")
		return TRUE;

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
		return TRUE;
	}
	r_uploadimage(sprintf("steampic/%g", sp_reqslot), SP_PX, SP_PX, px);
	memfree(px);
	// A shader of our own, once per slot.  drawpic's default loads its picture
	// PREMULTIPLIED (gl_shader.c Shader_Default2D), which is another texture
	// than the one just uploaded: it drew the engine's missing-texture checker.
	shaderforname(sprintf("steampic/%g", sp_reqslot),
	              sprintf("{\naffine\nnomipmaps\nprogram default2d\n{\nclampmap steampic/%g\nblendfunc blend\n}\nsort additive\n}\n",
	                      sp_reqslot));
	sp_st[sp_reqslot] = SP_HAVE;
	sp_got = sp_got + 1;
	return TRUE;
};

// `scores pics`: what the cache holds, for an arm to grade.
void() SteamPic_Status =
{
	local float i;

	print(sprintf("steampic: asked %g got %g inflight %g strikes %g hold %g\n", sp_asked, sp_got,
	              sp_req ? 1 : 0, sp_bad, max(0, cvar("_steampic_hold") - gettime(0))));
	if (sp_st)
	for (i = 0; i < SP_MAX; i = i + 1)
		if (sp_st[i])
			print(sprintf("steampic: slot %g mark %s state %g\n", i, bufstr_get(sp_bmark, i), sp_st[i]));
};
