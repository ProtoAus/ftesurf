/*
  cl_profile.qc -- a player's breakdown and the player search (Patch 663).

  The site's player page, in the game.  surfd answers two asks on /api/board
  (Patch 662): `player=` is one player's figures and best rows, `players=` a
  name search.  This file holds both asks and their answers, and the three
  pieces a panel draws inside its own sui bracket: the search field, the list
  of names under it, and the breakdown.  hud_player (cl_avatar.qc) shows all
  three; the leaderboard (cl_scores.qc) has the field and hands a picked
  player over.

  THE FIELD'S KEYS ARE TAKEN AS THEY COME (sui_text_event), not from sui's
  buffer: see that function.  ROWS LIVE IN memalloc'd TABLES, as the board's
  do: this VM is near fteqcc's limit on globals (cl_online.qc, Online_Alloc).
*/

#define PF_HITS     12      // players one search answer names (surfd's GAME_SEARCH_MAX)
#define PF_ROWS     200     // rows held of one breakdown (surfd's GAME_PROFILE_MAX)
#define PF_PAGE     50      // ...and asked for at a time
#define PF_TIERS    12      // difficulty tiers a breakdown shows bars for
#define PF_QMAX     32      // characters of search text
#define PF_WAIT     0.3     // s the text rests before it is asked about
#define PF_DEADLINE 12      // s an ask may take: the proxy gives surfd 5, the engine nothing
#define PF_RETRY    2       // s before the one more ask a slow first answer gets
#define PF_MOREWAIT 2       // s between asks for a next page
#define PF_MORETRIES 3      // asks for a page that bring nothing, before it is left alone
#define PF_TEXT     64      // characters kept of a name or a map from an answer
#define PF_RF       7       // floats a row: track, leg, tier, ms, when, rank, of

#define PFS_NONE    0
#define PFS_ASK     1
#define PFS_OK      2
#define PFS_FAIL    3
#define PFS_NOTERMS 4       // the online terms have not been accepted
#define PFS_NODIR   5       // lobby_dir is empty

#define PFT_OURS    0
#define PFT_MOM     1
#define PFT_KSF     2

// ---- the search
string pf_q;                // the field's text
float  pf_q_caret;
float  pf_q_focus;          // the field has the keyboard
float  pf_q_open;           // its list is showing
string pf_q_id;             // the sui id of the field that has it (its owner's)
float  pf_q_t;              // cltime the text last changed
string pf_q_for;            // the text the ask in flight, or the list held, is for
float  pf_s_state, pf_s_req, pf_s_sent, pf_s_code, pf_s_n, pf_s_sel;
string pf_s_who[PF_HITS];
string pf_s_name[PF_HITS];
float  pf_s_cnt[PF_HITS];
float  pf_s_src[PF_HITS];
float  pf_s_av[PF_HITS];
string pf_pick;             // a player chosen from the list, until its owner takes it
vector pf_f_p, pf_f_sz;     // the field as last drawn, on the screen
vector pf_d_p, pf_d_sz;     // ...and the list

// ---- the breakdown
string pf_who;              // who was asked for: a search row's handle, or the game's 8-hex mark
float  pf_state, pf_req, pf_sent, pf_code, pf_again;
float  pf_more_req, pf_more_sent;
float  pf_more_at, pf_more_n;   // no next page before this time; asks since one brought rows
float  pf_got;                  // cltime the breakdown held landed
float  pf_base, pf_seq;         // this VM's request ids: Profile_Get
vector pf_f_scr;                // the screen the field was last drawn on
string pf_name, pf_handle;
float  pf_src, pf_n, pf_maps, pf_last, pf_wr, pf_wrc, pf_top10, pf_av, pf_total, pf_t;
float  pf_bt_ours, pf_bt_mom, pf_bt_ksf;
float  pf_c_has, pf_c_n, pf_c_done, pf_c_of, pf_c_unt;
float  pf_c_tier[PF_TIERS];
float  pf_c_td[PF_TIERS];
float  pf_c_to[PF_TIERS];
float  pf_rn;
float  pf_bmap;             // strbuf: a row's map
float *pf_rf;               // PF_ROWS * PF_RF
vector pf_scroll;
float  pf_said;             // the answer's own line was printed (once an answer)

// What the lobby last said of this install (cl_account.qc's `acct_is`, which
// compiles later): 1 not linked, 2 linked, 3 banned, 0 never said.  ANYONE CAN
// STUFF IT, so it only ever chooses words on the profile.
float  acct_cl_is;

void() Profile_Alloc =
{
	if (pf_rf)
		return;
	pf_rf = memalloc(sizeof(float) * PF_ROWS * PF_RF);
	pf_bmap = buf_create();
	pf_s_sel = -1;
};

// Anything that contacts a server needs the online terms: Online_Fetch has the essay.
float() Profile_Gate =
{
	if (ui_consent_ver < FS_TERMS_ONLINE)
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
		return PFS_NOTERMS;
	if (cvar_string("lobby_dir") == "")
		return PFS_NODIR;
	return PFS_NONE;
};

float(string s) Profile_Tier =
{
	if (s == "momentum") return PFT_MOM;
	if (s == "ksf") return PFT_KSF;
	return PFT_OURS;
};

string(float t) Profile_TierTag =
{
	if (t == PFT_MOM) return "MOM";
	if (t == PFT_KSF) return "KSF";
	return "FTE";
};

string(float track, float leg) Profile_Leg =
{
	if (track <= 0)
	{
		if (leg <= 0) return "Main";
		return sprintf("Stage %g", leg);
	}
	if (leg <= 0) return sprintf("Bonus %g", track);
	return sprintf("Bonus %g, stage %g", track, leg);
};

// How long ago, by surfd's own clock (`t`): a float holds a date to two minutes.
string(float when) Profile_Age =
{
	local float a;
	if (when <= 0 || pf_t <= 0)
		return "";
	a = pf_t - when;
	if (a < 3600)        return "today";
	if (a < 86400)       return sprintf("%gh", floor(a / 3600));
	if (a < 86400 * 365) return sprintf("%gd", floor(a / 86400));
	return sprintf("%gy", floor(a / (86400 * 365)));
};

// ---- asking -------------------------------------------------------------

// A handle (12 hex) or a mark (8): what surfd answers for.  Nothing else is asked about.
float(string s) Profile_IsWho =
{
	local float i, n, c;

	n = strlen(s);
	if (n != 8 && n != 12)
		return FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')))
			return FALSE;
	}
	return TRUE;
};

/*
  REQUEST IDS RESTART WITH THE VM, and a reply to the last map's ask can land
  in this one's (cl_steampic.qc has the note).  A base drawn per VM, clear of
  the board's small numbers and of the pictures' range.
*/
float(string url) Profile_Get =
{
	if (!pf_base)
		pf_base = 8000000 + floor(random() * 1000) * 4000;
	pf_seq = pf_seq + 1;
	if (pf_seq >= 4000)
		pf_seq = 1;
	if (!uri_get(url, pf_base + pf_seq))
		return 0;
	return pf_base + pf_seq;
};

void() Profile_Ask =
{
	local float g;

	pf_req = 0;
	pf_more_req = 0;
	pf_more_at = 0;
	pf_more_n = 0;
	if (!Profile_IsWho(pf_who))
	{
		pf_state = PFS_FAIL;            // nobody surfd could know by that
		pf_code = 404;
		return;
	}
	g = Profile_Gate();
	if (g)
	{
		pf_state = g;
		return;
	}
	pf_req = Profile_Get(sprintf("%s/api/board?player=%s&limit=%g", cvar_string("lobby_dir"),
	                             pf_who, PF_PAGE));
	pf_state = pf_req ? PFS_ASK : PFS_FAIL;
	pf_code = 0;
	pf_sent = cltime;
};

// `who`: a search row's handle, or the 8-hex mark the game knows a player by.
void(string who) Profile_Show =
{
	Profile_Alloc();
	// Called every frame the breakdown is up: a failed ask is not asked again here.
	if (who == pf_who)
	if (pf_state != PFS_NONE)
		return;
	pf_who = who;
	pf_rn = 0;
	pf_total = 0;
	pf_name = "";
	pf_handle = "";
	pf_scroll = '0 0 0';
	pf_again = 0;
	pf_said = FALSE;
	Profile_Ask();
};

// A panel opening again: a breakdown held longer than `age` is asked for anew
// (a run since changes it), and so is one that failed for want of an answer.
void(float age) Profile_Stale =
{
	if (pf_state == PFS_OK && cltime - pf_got > age)
		pf_state = PFS_NONE;
	if (pf_state == PFS_FAIL && pf_code != 404)
		pf_state = PFS_NONE;
};

/*
  The next page, as the list's end comes near.  AT MOST ONE ASK EVERY
  PF_MOREWAIT, AND PF_MORETRIES THAT BRING NOTHING: the first cut asked again
  the moment an ask failed or brought no new row, for as long as the tail was
  on screen, out of the bucket the board and the pictures share (its review).
*/
void() Profile_More =
{
	if (pf_state != PFS_OK || pf_more_req)
		return;
	if (pf_rn >= pf_total || pf_rn >= PF_ROWS)
		return;
	if (pf_more_n >= PF_MORETRIES || cltime < pf_more_at)
		return;
	if (Profile_Gate())
		return;
	pf_more_n = pf_more_n + 1;
	pf_more_at = cltime + PF_MOREWAIT;
	pf_more_req = Profile_Get(sprintf("%s/api/board?player=%s&offset=%g&limit=%g",
	                                  cvar_string("lobby_dir"), pf_handle,
	                                  pf_rn, min(PF_PAGE, PF_ROWS - pf_rn)));
	pf_more_sent = cltime;
};

void() Profile_SearchAsk =
{
	local float g;

	pf_q_for = pf_q;
	pf_s_req = 0;
	g = Profile_Gate();
	if (g)
	{
		pf_s_state = g;
		return;
	}
	pf_s_req = Profile_Get(sprintf("%s/api/board?players=%s", cvar_string("lobby_dir"),
	                               uri_escape(pf_q)));
	pf_s_state = pf_s_req ? PFS_ASK : PFS_FAIL;
	pf_s_code = 0;
	pf_s_sent = cltime;
};

// ---- answers --------------------------------------------------------------
// An answer is somebody's text: a `who` is hex or it is nothing, a name and a
// map are cut to PF_TEXT, and a map's colour codes are taken out (a name's are
// UI_NameShow's when it is drawn).

// -> rows taken.
float(float root) Profile_Rows =
{
	local float rows, n, i, row, at, took;
	local float *f;

	rows = json_find_object_child(root, "rows");
	n = json_get_length(rows);
	took = 0;
	for (i = 0; i < n && pf_rn < PF_ROWS; i = i + 1)
	{
		row = json_get_child_at_index(rows, i);
		at = pf_rn * PF_RF;
		f = pf_rf;
		f[at]     = json_get_float(json_find_object_child(row, "track"));
		f[at + 1] = json_get_float(json_find_object_child(row, "leg"));
		f[at + 2] = Profile_Tier(json_get_string(json_find_object_child(row, "tr")));
		f[at + 3] = json_get_float(json_find_object_child(row, "ms"));
		f[at + 4] = json_get_float(json_find_object_child(row, "when"));
		f[at + 5] = json_get_float(json_find_object_child(row, "r"));
		f[at + 6] = json_get_float(json_find_object_child(row, "of"));
		bufstr_set(pf_bmap, pf_rn, strdecolorize(substring(
			json_get_string(json_find_object_child(row, "map")), 0, PF_TEXT)));
		pf_rn = pf_rn + 1;
		took = took + 1;
	}
	return took;
};

void(string bdy) Profile_Parse =
{
	local float root, c, tiers, i, t;
	local string h;

	root = json_parse(bdy);
	h = json_get_string(json_find_object_child(root, "who"));
	// The player asked for: a handle, and the one `pf_who` is or begins.
	if (!root || strlen(h) != 12 || !Profile_IsWho(h) || substring(h, 0, strlen(pf_who)) != pf_who)
	{
		if (root)
			json_free(root);
		pf_state = PFS_FAIL;
		pf_code = -1;
		return;
	}
	pf_handle = h;
	pf_name   = substring(json_get_string(json_find_object_child(root, "name")), 0, PF_TEXT);
	pf_src    = Profile_Tier(json_get_string(json_find_object_child(root, "src")));
	pf_t      = json_get_float(json_find_object_child(root, "t"));
	pf_n      = json_get_float(json_find_object_child(root, "n"));
	pf_maps   = json_get_float(json_find_object_child(root, "maps"));
	pf_last   = json_get_float(json_find_object_child(root, "last"));
	pf_wr     = json_get_float(json_find_object_child(root, "wr"));
	pf_wrc    = json_get_float(json_find_object_child(root, "wrc"));
	pf_top10  = json_get_float(json_find_object_child(root, "top10"));
	pf_av     = json_get_float(json_find_object_child(root, "av"));
	pf_total  = json_get_float(json_find_object_child(root, "total"));
	c = json_find_object_child(root, "by_tier");
	pf_bt_ours = json_get_float(json_find_object_child(c, "ranked"));
	pf_bt_mom  = json_get_float(json_find_object_child(c, "momentum"));
	pf_bt_ksf  = json_get_float(json_find_object_child(c, "ksf"));
	// No catalogue on the server is `null`, and reads as a table of nothing.
	c = json_find_object_child(root, "completion");
	tiers = json_find_object_child(c, "tiers");
	pf_c_of   = json_get_float(json_find_object_child(c, "of"));
	pf_c_done = json_get_float(json_find_object_child(c, "done"));
	pf_c_unt  = json_get_float(json_find_object_child(c, "untiered"));
	pf_c_has  = (pf_c_of > 0);
	pf_c_n = min(PF_TIERS, json_get_length(tiers));
	for (i = 0; i < pf_c_n; i = i + 1)
	{
		t = json_get_child_at_index(tiers, i);
		pf_c_tier[i] = json_get_float(json_find_object_child(t, "tier"));
		pf_c_td[i]   = json_get_float(json_find_object_child(t, "done"));
		pf_c_to[i]   = json_get_float(json_find_object_child(t, "of"));
	}
	pf_rn = 0;
	Profile_Rows(root);
	json_free(root);
	if (pf_total < pf_rn)
		pf_total = pf_rn;
	pf_state = PFS_OK;
	pf_got = cltime;
	if (!pf_said)
	{
		pf_said = TRUE;
		dprint(sprintf("profile: %s is %s, %g times, %g firsts, %g rows of %g held\n",
		               pf_who, pf_handle, pf_n, pf_wr, pf_rn, pf_total));
	}
};

void(string bdy) Profile_ParseMore =
{
	local float root;

	root = json_parse(bdy);
	if (!root)
		return;
	// Only the page that follows what is held, of the player it is held for.
	if (json_get_string(json_find_object_child(root, "who")) == pf_handle)
	if (json_get_float(json_find_object_child(root, "offset")) == pf_rn)
	{
		// What is there NOW; and a page of nothing was the end, whatever it says.
		pf_total = json_get_float(json_find_object_child(root, "total"));
		if (Profile_Rows(root) > 0)
		{
			pf_more_n = 0;
			pf_more_at = 0;
		}
		else
			pf_total = pf_rn;
		if (pf_total < pf_rn)
			pf_total = pf_rn;
		dprint(sprintf("profile: a page landed, %g rows of %g held\n", pf_rn, pf_total));
	}
	json_free(root);
};

void(string bdy) Profile_ParseHits =
{
	local float root, list, n, i, row, k;
	local string h;

	root = json_parse(bdy);
	if (!root)
	{
		pf_s_state = PFS_FAIL;
		pf_s_code = -1;
		return;
	}
	list = json_find_object_child(root, "players");
	n = json_get_length(list);
	k = 0;
	for (i = 0; i < n && k < PF_HITS; i = i + 1)
	{
		row = json_get_child_at_index(list, i);
		h = json_get_string(json_find_object_child(row, "who"));
		if (strlen(h) != 12 || !Profile_IsWho(h))
			continue;
		pf_s_who[k]  = h;
		pf_s_name[k] = substring(json_get_string(json_find_object_child(row, "name")), 0, PF_TEXT);
		pf_s_cnt[k]  = json_get_float(json_find_object_child(row, "n"));
		pf_s_src[k]  = Profile_Tier(json_get_string(json_find_object_child(row, "src")));
		pf_s_av[k]   = json_get_float(json_find_object_child(row, "av"));
		k = k + 1;
	}
	json_free(root);
	pf_s_n = k;
	pf_s_sel = -1;
	pf_s_state = PFS_OK;
	dprint(sprintf("profile: search \"%s\" found %g, first %s\n", pf_q_for, k,
	               (k > 0) ? pf_s_who[0] : "-"));
};

// URI_Get_Callback's (cl_online.qc).  -> the reply was one of this file's.
float(float reqid, float code, string bdy) Profile_Reply =
{
	if (pf_req)
	if (reqid == pf_req)
	{
		pf_req = 0;
		if (code)
		{
			pf_state = PFS_FAIL;
			pf_code = code;
		}
		else
			Profile_Parse(bdy);
		return TRUE;
	}
	if (pf_more_req)
	if (reqid == pf_more_req)
	{
		pf_more_req = 0;                // a failure waits out Profile_More's clock
		if (!code)
			Profile_ParseMore(bdy);
		return TRUE;
	}
	if (pf_s_req)
	if (reqid == pf_s_req)
	{
		pf_s_req = 0;
		if (code)
		{
			pf_s_state = PFS_FAIL;
			pf_s_code = code;
		}
		else
			Profile_ParseHits(bdy);
		return TRUE;
	}
	return FALSE;
};

// Once a frame from whichever panel shows a piece of this: the search's rest,
// and asks that never came back.
void() Profile_Frame =
{
	Profile_Alloc();
	if (pf_q_open)
	if (pf_s_state == PFS_NONE || pf_q != pf_q_for)
	if (cltime - pf_q_t >= PF_WAIT)
		Profile_SearchAsk();
	if (pf_s_state == PFS_ASK)
	if (cltime - pf_s_sent > PF_DEADLINE)
	{
		pf_s_req = 0;
		pf_s_state = PFS_FAIL;
		pf_s_code = 0;
	}
	if (pf_state == PFS_ASK)
	if (cltime - pf_sent > PF_DEADLINE)
	{
		pf_req = 0;
		pf_state = PFS_FAIL;
		pf_code = 0;
	}
	/*
	  ONE MORE ASK, BY ITSELF, after an answer the proxy gave up on: a wide
	  profile's first answer is seconds of ranking on the Pi and the proxy
	  allows five, but surfd finishes and keeps it, so the second is quick.
	*/
	if (pf_state == PFS_FAIL)
	if (!pf_again)
	if (pf_code <= 0 || pf_code >= 500)
	if (cltime - pf_sent > PF_RETRY)
	{
		pf_again = TRUE;
		Profile_Ask();
	}
	if (pf_more_req)
	if (cltime - pf_more_sent > PF_DEADLINE)
		pf_more_req = 0;
	// The terms accepted since: what was refused for want of them is asked now.
	if (pf_state == PFS_NOTERMS || pf_state == PFS_NODIR)
	if (!Profile_Gate())
		Profile_Ask();
	if (pf_q_open)
	if (pf_s_state == PFS_NOTERMS || pf_s_state == PFS_NODIR)
	if (!Profile_Gate())
		Profile_SearchAsk();
};

// ---- the pieces a panel draws ------------------------------------------------

// A pill.  -> it was let go of.
float(string id, vector pos, vector sz, string label, float tsz, float on) Profile_Chip =
{
	local float tw, hot;

	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	if (hot)
		sui_style_box(pos, sz, sz_y * 0.5, on ? SUI_THEME_SELECTED : SUI_THEME_HOVER, SUI_THEME_EDGE_HI, 1);
	else
		sui_roundbox(pos, sz, sz_y * 0.5, on ? SUI_THEME_SELECTED : SUI_THEME_CHIP, 1);
	tw = stringwidth(label, TRUE, [tsz, tsz]);
	sui_text([pos_x + (sz_x - tw) * 0.5, pos_y + (sz_y - tsz) * 0.5], [tsz, tsz], label,
	         on ? SUI_THEME_ACCENT : (hot ? SUI_THEME_TEXT : SUI_THEME_DIM), 1, 0);
	return sui_is_released(id);
};

// One half of a two-way switch, on a WELL pill its owner drew.  -> let go of.
float(string id, vector pos, vector sz, string label, float tsz, float on) Profile_Seg =
{
	local float hot, tw;

	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	if (on)
		sui_roundbox(pos + '2 2 0', sz - '4 4 0', (sz_y - 4) * 0.5, SUI_THEME_SELECTED, 1);
	else if (hot)
		sui_roundbox(pos + '2 2 0', sz - '4 4 0', (sz_y - 4) * 0.5, SUI_THEME_HOVER, 1);
	tw = stringwidth(label, TRUE, [tsz, tsz]);
	sui_text([pos_x + (sz_x - tw) * 0.5, pos_y + (sz_y - tsz) * 0.5], [tsz, tsz], label,
	         on ? SUI_THEME_ACCENT : (hot ? SUI_THEME_TEXT : SUI_THEME_DIM), 1, 0);
	return sui_is_released(id);
};

// A text field's box, selection, text and caret, after its sui_text_input.
// `inset` is where its text starts (what sui_text_metrics was told).
void(string id, vector p, vector sz, float tsz, string text, float caret, string ghost, float focus,
     float round, float inset) Profile_FieldLook =
{
	local vector tp;

	sui_style_box(p, sz, round, SUI_THEME_WELL,
	              focus ? SUI_THEME_ACCENT : (sui_is_hovered(id) ? SUI_THEME_EDGE_HI : SUI_THEME_EDGE), 1);
	tp = [p_x + inset, p_y + (sz_y - tsz) * 0.5];
	if (focus)
		sui_text_selection(id, tp, [tsz, tsz], text, caret, SUI_THEME_SELECTED, 1);
	if (text == "")
		sui_text(tp, [tsz, tsz], ghost, SUI_THEME_MUTED, 1, 0);
	else
		sui_text(tp, [tsz, tsz], text, SUI_THEME_TEXT, 1, 0);
	if (focus)
	if (cltime - floor(cltime) < 0.5)
		sui_fill([tp_x + stringwidth(substring(text, 0, caret), TRUE, [tsz, tsz]), tp_y - 1],
		         [1, tsz + 2], SUI_THEME_ACCENT, 1, 0);
};

// A player's picture, or the first letter of their name on a disc.
void(vector pos, float px, string mark, float has, string name) Profile_Face =
{
	local string s;

	if (has)
	if (SteamPic_Draw(pos, px, mark, 1))
		return;
	sui_roundbox(pos, [px, px], px * 0.5, SUI_THEME_CHIP, 1);
	s = strtoupper(substring(strdecolorize(name), 0, 1));
	if (s == "")
		s = "?";
	sui_text([pos_x + (px - stringwidth(s, TRUE, [px * 0.5, px * 0.5])) * 0.5, pos_y + px * 0.25],
	         [px * 0.5, px * 0.5], s, SUI_THEME_DIM, 1, 0);
};

/*
  THE KEYS A FIELD TOOK THE PRESS OF: only their releases are the field's too.
  The engine returns before a bind's release when game code takes a key-up
  (keys.c:3860), so a key already down as a field took the keyboard (a strafe
  key, the scoreboard's) must have its release let through, or it stays down.
*/
#define PF_TOOK 8
float pf_took[PF_TOOK];
void(float scanx) Profile_Took =
{
	local float i;
	for (i = 0; i < PF_TOOK; i = i + 1)
		if (pf_took[i] == scanx)
			return;
	for (i = 0; i < PF_TOOK; i = i + 1)
		if (!pf_took[i])
		{
			pf_took[i] = scanx;
			return;
		}
};
float(float scanx) Profile_TookUp =
{
	local float i;
	for (i = 0; i < PF_TOOK; i = i + 1)
		if (pf_took[i] == scanx)
		{
			pf_took[i] = 0;
			return TRUE;
		}
	return FALSE;
};
void() Profile_TookNone =
{
	local float i;
	for (i = 0; i < PF_TOOK; i = i + 1)
		pf_took[i] = 0;
};

void() Profile_Unfocus =
{
	pf_q_focus = FALSE;
	pf_q_open = FALSE;
	pf_s_sel = -1;
	if (pf_s_state == PFS_FAIL)
		pf_s_state = PFS_NONE;          // a list that failed is asked for when it next opens
	Profile_TookNone();
	sui_text_unfocus();
};

// A panel opening or closing: the field is nobody's, and so is a pick not taken.
void() Profile_Reset =
{
	Profile_Unfocus();
	pf_pick = "";
};

// The search field, in its owner's bracket and the UI face.  `id` is the
// owner's name for it.
void(string id, vector p, vector sz, float tsz) Profile_Field =
{
	local vector o, s;
	local float inset;

	inset = ceil(sz_y * 0.45);
	sui_text_metrics(inset, [tsz, tsz]);
	sui_text_input(id, p, sz, pf_q, pf_q_caret);
	if (sui_is_held(id) || sui_is_clicked(id))
	{
		if (!pf_q_focus || pf_q_id != id)
		{
			pf_q_t = cltime - PF_WAIT;      // the list for what is already typed, at once
			Profile_TookNone();
		}
		pf_q_focus = TRUE;
		pf_q_open = TRUE;
		pf_q_id = id;
		sui_field_focus(id);
	}
	o = p;
	s = sz;
	sui_transform_box(o, s);
	pf_f_p = o;
	pf_f_sz = s;
	pf_f_scr = sui_style_screen;
	Profile_FieldLook(id, p, sz, tsz, pf_q, pf_q_caret, "Search players", pf_q_focus && pf_q_id == id,
	                  sz_y * 0.5, inset);
};

// The list under the field.  Drawn LAST in its owner's bracket: it lies over
// whatever is below the field, and the last element under the cursor is the
// one sui answers for.  A click on a name sets pf_pick.
void(vector p, float w, float tsz, float hint) Profile_Drop =
{
	local float i, rowh, h, pad, n, y, hot;
	local string s, rid;
	local vector o, sz;

	if (!pf_q_open)
	{
		pf_d_sz = '0 0 0';
		return;
	}
	pad = ceil(tsz * 0.5);
	rowh = ceil(tsz * 2.1);
	n = (pf_s_state == PFS_OK && pf_q == pf_q_for) ? pf_s_n : 0;
	h = pad * 2 + max(1, n) * rowh;
	o = p;
	sz = [w, h];
	sui_transform_box(o, sz);
	pf_d_p = o;
	pf_d_sz = sz;
	sui_action_element(p, [w, h], "pf_drop", sui_noop);
	sui_style_panel(p, [w, h], ceil(tsz * 0.6), 0.98);
	if (!n)
	{
		s = "Searching...";
		if (pf_s_state == PFS_NOTERMS) s = "Accept the online terms to search";
		else if (pf_s_state == PFS_NODIR) s = "No leaderboard to search here";
		else if (pf_s_state == PFS_FAIL) s = (pf_s_code == 429) ? "Too many asks, try in a minute" : "The leaderboard did not answer";
		else if (pf_s_state == PFS_OK && pf_q == pf_q_for) s = "No player by that name";
		sui_text([p_x + pad * 2, p_y + pad + (rowh - hint) * 0.5], [hint, hint], s, SUI_THEME_MUTED, 1, 0);
		return;
	}
	y = p_y + pad;
	for (i = 0; i < n; i = i + 1)
	{
		rid = sprintf("pf_h%g", i);
		sui_action_element([p_x + pad, y], [w - pad * 2, rowh], rid, sui_noop);
		hot = sui_is_hovered(rid);
		if (hot || pf_s_sel == i)
			sui_roundbox([p_x + pad, y], [w - pad * 2, rowh], ceil(tsz * 0.4),
			             hot ? SUI_THEME_HOVER : SUI_THEME_SELECTED, 1);
		Profile_Face([p_x + pad * 2, y + 3], rowh - 6, substring(pf_s_who[i], 0, 8), pf_s_av[i], pf_s_name[i]);
		s = sprintf("%g %s", pf_s_cnt[i], (pf_s_cnt[i] == 1) ? "time" : "times");
		sui_text([p_x + w - pad * 2 - stringwidth(s, TRUE, [hint, hint]), y + (rowh - hint) * 0.5],
		         [hint, hint], s, SUI_THEME_MUTED, 1, 0);
		sui_text([p_x + pad * 3 + rowh - 6, y + (rowh - tsz) * 0.5], [tsz, tsz],
		         Chat_Fit(UI_NameShow(pf_s_name[i], 0),
		                  w - pad * 6 - rowh - stringwidth(s, TRUE, [hint, hint]), tsz),
		         SUI_THEME_TEXT, 1, 0);
		if (sui_is_released(rid))
			pf_pick = pf_s_who[i];
		y = y + rowh;
	}
};

// The cursor is on the field or its list, as last drawn.
float() Profile_Over =
{
	if (_cursor_position_x >= pf_f_p_x && _cursor_position_x < pf_f_p_x + pf_f_sz_x)
	if (_cursor_position_y >= pf_f_p_y && _cursor_position_y < pf_f_p_y + pf_f_sz_y)
		return TRUE;
	if (pf_q_open)
	if (_cursor_position_x >= pf_d_p_x && _cursor_position_x < pf_d_p_x + pf_d_sz_x)
	if (_cursor_position_y >= pf_d_p_y && _cursor_position_y < pf_d_p_y + pf_d_sz_y)
		return TRUE;
	return FALSE;
};

// The owner's input handler asks this first.  A press beside the field and its
// list gives the keyboard back; while the field has it every key is the
// field's (binds would run on what is typed).  -> the event was the field's.
float(float evtype, float scanx, float chary) Profile_FieldEvent =
{
	local string was;

	if (!pf_q_focus && !pf_q_open)
		return FALSE;
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN)
		if (!Profile_Over())
			Profile_Unfocus();
		return FALSE;                   // sui's, either way
	}
	if (scanx == K_MWHEELUP || scanx == K_MWHEELDOWN)
		return pf_q_open && Profile_Over();
	if (!pf_q_focus)
		return FALSE;
	if (evtype == IE_KEYUP)
	{
		sui_text_event(evtype, scanx, chary, pf_q_id, pf_q, pf_q_caret);    // a modifier let go
		return Profile_TookUp(scanx);
	}
	Profile_Took(scanx);
	if (evtype == IE_KEYDOWN)
	{
		if (scanx == K_ESCAPE)
		{
			Profile_Unfocus();
			return TRUE;
		}
		if (scanx == K_ENTER || scanx == K_KP_ENTER)
		{
			if (pf_s_state == PFS_OK && pf_q == pf_q_for && pf_s_n > 0)
				pf_pick = pf_s_who[max(0, pf_s_sel)];
			return TRUE;
		}
		if (scanx == K_DOWNARROW || scanx == K_UPARROW)
		{
			if (pf_s_n > 0)
				pf_s_sel = bound(0, pf_s_sel + ((scanx == K_DOWNARROW) ? 1 : -1), pf_s_n - 1);
			return TRUE;
		}
	}
	was = pf_q;
	sui_text_event(evtype, scanx, chary, pf_q_id, pf_q, pf_q_caret);
	if (strlen(pf_q) > PF_QMAX)
	{
		pf_q = substring(pf_q, 0, PF_QMAX);
		pf_q_caret = min(pf_q_caret, PF_QMAX);
	}
	if (pf_q != was)
	{
		pf_q_t = cltime;
		pf_q_open = TRUE;
		pf_s_sel = -1;
	}
	return TRUE;
};

// The console's twin of typing into the field, for a headless arm: the text
// and its list.  NOT THE KEYBOARD: a console line can be a server's, and a
// field that took it would take whatever the player typed next (its review).
// Only a press on the field gives that.
void(string text) Profile_Type =
{
	pf_q = substring(text, 0, PF_QMAX);
	pf_q_caret = strlen(pf_q);
	pf_q_t = cltime - PF_WAIT;
	pf_q_open = TRUE;
};

// The player chosen from the list since the last ask, or "".  The field lets go.
string() Profile_TakePick =
{
	local string s;

	s = pf_pick;
	if (s == "")
		return "";
	pf_pick = "";
	Profile_Unfocus();
	pf_q = "";                      // the field is the next search's
	pf_q_caret = 0;
	return s;
};

// One headline figure, and a note beside it.
void(vector p, vector sz, string big, string note, string small, float tsz, float hint, vector col) Profile_Tile =
{
	sui_roundbox(p, sz, ceil(hint * 0.6), SUI_THEME_WELL, 1);
	Font_Set(ui_font_mono);
	sui_text([p_x + hint, p_y + ceil(hint * 0.7)], [tsz, tsz], big, col, 1, 0);
	p_z = stringwidth(big, TRUE, [tsz, tsz]);
	Font_Set(ui_font_ui);
	if (note != "")
		sui_text([p_x + hint * 1.6 + p_z, p_y + ceil(hint * 0.7) + tsz - hint - 1], [hint, hint],
		         Chat_Fit(note, sz_x - hint * 2.6 - p_z, hint), SUI_THEME_MUTED, 1, 0);
	sui_text([p_x + hint, p_y + sz_y - hint - ceil(hint * 0.6)], [hint, hint], small, SUI_THEME_MUTED, 1, 0);
};

/*
  The breakdown of whoever Profile_Show last named, in its owner's bracket.
  `ttl` the headline figures' size, `tsz` the rows', `hint` the small labels'.
  The site's page in its order: figures, maps finished by difficulty, results
  best first.
*/
void(vector p, vector sz, float ttl, float tsz, float hint) Profile_DrawStats =
{
	local float i, x, y, w, tw, th, n, cols, rowh, lh, c0, c1, c2, c3, bw, at, r, retry;
	local float *f;
	local string s;
	local vector lp, col;

	if (pf_state != PFS_OK)
	{
		s = "Asking the leaderboard...";
		if (pf_who == "") s = "";
		else if (pf_state == PFS_NOTERMS) s = "Accept the online terms (in the main menu) to see this";
		else if (pf_state == PFS_NODIR) s = "This game has no leaderboard address";
		retry = FALSE;
		if (pf_state == PFS_FAIL)
		{
			if (pf_code == 404) s = "No times on the leaderboard yet";
			else if ((pf_code <= 0 || pf_code >= 500) && !pf_again)
				s = "Asking the leaderboard...";    // Profile_Frame's one more ask is coming
			else
			{
				s = (pf_code == 429) ? "Too many asks: wait a minute, then try again"
				                     : "The leaderboard did not answer";
				retry = TRUE;
			}
		}
		sui_text([p_x, p_y + hint], [tsz, tsz], s, SUI_THEME_DIM, 1, 0);
		if (retry)
		if (Profile_Chip("pf_retry", [p_x, p_y + hint + tsz * 2], [tsz * 6, tsz * 1.9], "Try again", hint, FALSE))
		{
			pf_again = TRUE;                // by hand from here: no ask follows by itself
			Profile_Ask();
		}
		return;
	}

	// ---- the figures
	n = 4 + (pf_c_has ? 1 : 0);
	th = ceil(ttl + hint * 3.2);
	tw = floor((sz_x - (n - 1) * hint) / n);
	x = p_x;
	y = p_y;
	Profile_Tile([x, y], [tw, th], ftos(pf_n), "", (pf_n == 1) ? "time" : "times", ttl, hint, SUI_THEME_TEXT);
	x = x + tw + hint;
	// A first place on a board of one is not a record: the site leads with the same note.
	s = "";
	if (pf_wr > 0)
		s = (pf_wrc == pf_wr) ? "all contested" : sprintf("%g contested", pf_wrc);
	Profile_Tile([x, y], [tw, th], ftos(pf_wr), s, (pf_wr == 1) ? "first place" : "first places", ttl, hint,
	             (pf_wrc > 0) ? SUI_THEME_WARN : SUI_THEME_TEXT);
	x = x + tw + hint;
	Profile_Tile([x, y], [tw, th], ftos(pf_top10), "", "top tens", ttl, hint, SUI_THEME_TEXT);
	x = x + tw + hint;
	Profile_Tile([x, y], [tw, th], ftos(pf_maps), "", (pf_maps == 1) ? "map" : "maps", ttl, hint, SUI_THEME_TEXT);
	if (pf_c_has)
	{
		x = x + tw + hint;
		Profile_Tile([x, y], [tw, th], sprintf("%g/%g", pf_c_done, pf_c_of), "", "maps finished", ttl, hint,
		             SUI_THEME_GOOD);
	}
	y = y + th + hint;

	// ---- maps finished, by difficulty: two columns of bars
	if (pf_c_has && pf_c_n > 0)
	{
		cols = (sz_x > tsz * 34) ? 2 : 1;
		lh = ceil(hint * 1.7);
		w = floor((sz_x - (cols - 1) * tsz * 1.5) / cols);
		c0 = ceil(hint * 4.2);                              // "Tier 10"
		c1 = ceil(hint * 4.5);                              // "123/456"
		Font_Set(ui_font_ui);
		for (i = 0; i < pf_c_n; i = i + 1)
		{
			x = p_x + (i - floor(i / cols) * cols) * (w + tsz * 1.5);
			lp = [x, y + floor(i / cols) * lh];
			sui_text(lp, [hint, hint], sprintf("Tier %g", pf_c_tier[i]), SUI_THEME_DIM, 1, 0);
			bw = w - c0 - c1 - hint;
			sui_roundbox([lp_x + c0, lp_y + hint * 0.25], [bw, ceil(hint * 0.5)], hint * 0.25, SUI_THEME_WELL, 1);
			if (pf_c_td[i] > 0 && pf_c_to[i] > 0)
				sui_roundbox([lp_x + c0, lp_y + hint * 0.25],
				             [max(ceil(hint * 0.5), bw * min(1, pf_c_td[i] / pf_c_to[i])), ceil(hint * 0.5)],
				             hint * 0.25, (pf_c_td[i] >= pf_c_to[i]) ? SUI_THEME_GOOD : SUI_THEME_ACCENT, 1);
			s = sprintf("%g/%g", pf_c_td[i], pf_c_to[i]);
			sui_text([lp_x + w - stringwidth(s, TRUE, [hint, hint]), lp_y], [hint, hint], s, SUI_THEME_MUTED, 1, 0);
		}
		y = y + ceil(pf_c_n / cols) * lh + hint;
	}

	// ---- results, best first
	rowh = ceil(tsz * 1.75);
	Font_Set(ui_font_mono);
	c0 = ceil(tsz * 0.6 * 11);                              // "#1234 /5678"
	c2 = ceil(tsz * 0.6 * 10);                              // "12:34.567"
	c3 = ceil(tsz * 0.6 * 5);                               // "365d"
	Font_Set(ui_font_ui);
	c1 = sz_x - c0 - c2 - c3 - tsz * 2;                     // map and leg
	sui_text([p_x, y], [hint, hint], "PLACE", SUI_THEME_MUTED, 1, 0);
	sui_text([p_x + c0, y], [hint, hint],
	         (pf_rn >= PF_ROWS && pf_total > pf_rn) ? sprintf("MAP   the first %g of %g", pf_rn, pf_total) : "MAP",
	         SUI_THEME_MUTED, 1, 0);
	sui_text([p_x + c0 + c1 + c2 - stringwidth("TIME", TRUE, [hint, hint]), y], [hint, hint], "TIME", SUI_THEME_MUTED, 1, 0);
	sui_text([p_x + sz_x - tsz - stringwidth("AGO", TRUE, [hint, hint]), y], [hint, hint], "AGO", SUI_THEME_MUTED, 1, 0);
	y = y + hint + ceil(hint * 0.5);
	sui_fill([p_x, y], [sz_x, 1], SUI_THEME_EDGE, 1, 0);
	y = y + 2;
	if (pf_rn <= 0)
	{
		sui_text([p_x, y + hint], [tsz, tsz], "No times yet", SUI_THEME_DIM, 1, 0);
		return;
	}
	sui_list_view_begin("pf_rows", [p_x, y], [sz_x, p_y + sz_y - y], [sz_x - tsz, rowh], pf_rn, pf_scroll,
	                    [0, ceil(tsz * 0.6)]);
	f = pf_rf;
	lp = '0 0 0';
	for (i = sui_list_item(lp); i > -1; i = sui_list_item(lp))
	{
		at = i * PF_RF;
		r = f[at + 5];
		if (i - floor(i / 2) * 2)
			sui_fill(lp, [sz_x - tsz, rowh], SUI_THEME_WELL, 0.45, 0);
		Font_Set(ui_font_mono);
		col = (r == 1) ? SUI_THEME_WARN : ((r <= 10) ? SUI_THEME_TEXT : SUI_THEME_DIM);
		s = sprintf("#%g", r);
		sui_text([lp_x + tsz * 0.3, lp_y + (rowh - tsz) * 0.5], [tsz, tsz], s, col, 1, 0);
		sui_text([lp_x + tsz * 0.3 + stringwidth(s, TRUE, [tsz, tsz]) + tsz * 0.3, lp_y + (rowh - hint) * 0.5 + 1],
		         [hint, hint], sprintf("/%g", f[at + 6]), SUI_THEME_MUTED, 1, 0);
		s = Time_MsString((int)f[at + 3]);
		sui_text([lp_x + c0 + c1 + c2 - stringwidth(s, TRUE, [tsz, tsz]), lp_y + (rowh - tsz) * 0.5],
		         [tsz, tsz], s, SUI_THEME_TEXT, 1, 0);
		Font_Set(ui_font_ui);
		s = Profile_Age(f[at + 4]);
		sui_text([lp_x + sz_x - tsz * 2 - stringwidth(s, TRUE, [hint, hint]), lp_y + (rowh - hint) * 0.5],
		         [hint, hint], s, SUI_THEME_MUTED, 1, 0);
		// the map, then its leg where it is not the main track, then the game where there are several
		s = Chat_Fit(bufstr_get(pf_bmap, i), c1 - tsz * 9, tsz);
		sui_text([lp_x + c0, lp_y + (rowh - tsz) * 0.5], [tsz, tsz], s, SUI_THEME_TEXT, 1, 0);
		x = lp_x + c0 + stringwidth(s, TRUE, [tsz, tsz]) + tsz * 0.6;
		if (f[at] > 0 || f[at + 1] > 0)
		{
			s = Profile_Leg(f[at], f[at + 1]);
			sui_text([x, lp_y + (rowh - hint) * 0.5 + 1], [hint, hint], s, SUI_THEME_DIM, 1, 0);
			x = x + stringwidth(s, TRUE, [hint, hint]) + tsz * 0.6;
		}
		if ((pf_bt_ours > 0) + (pf_bt_mom > 0) + (pf_bt_ksf > 0) > 1)
			sui_text([x, lp_y + (rowh - hint) * 0.5 + 1], [hint, hint], Profile_TierTag(f[at + 2]),
			         (f[at + 2] == PFT_OURS) ? SUI_THEME_ACCENT : SUI_THEME_ACCENT2, 1, 0);
		if (i >= pf_rn - 10)
			Profile_More();
	}
	sui_list_view_end();
};

// The wheel over the results, for an owner whose bracket is not the frame's
// only one (the board's wheel has the note).  -> it scrolled.
float(float evtype, float scanx, float rowh) Profile_Wheel =
{
	if (scanx != K_MWHEELUP && scanx != K_MWHEELDOWN)
		return FALSE;
	_sui_mouse_move(_cursor_position, FALSE);
	if (sui_hover_index("pf_rows") < 0)
		return FALSE;
	if (evtype == IE_KEYDOWN)
		pf_scroll_y = max(0, pf_scroll_y + ((scanx == K_MWHEELUP) ? 0 - rowh * 3 : rowh * 3));
	return TRUE;
};
