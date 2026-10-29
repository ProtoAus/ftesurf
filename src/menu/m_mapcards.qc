// P1062: visible clean-main records, batched on the existing public board API.
// Local PB files are not official WOS records. Unknown is never "not complete".
float mcr_ready, mcr_count, mcr_qn, mcr_reqn, mcr_req, mcr_sent, mcr_next, mcr_failed;
float mcr_names, mcr_data, mcr_seen, mcr_queue, mcr_asked;
hashtable mcr_index;
string mcr_who;

void() MCard_Begin =
{
	local string who;
	who = strtolower(MH_Me());
	if (mcr_ready)
	if (strcmp(who, mcr_who))
	{
		buf_del(mcr_names); buf_del(mcr_data); buf_del(mcr_seen);
		buf_del(mcr_queue); buf_del(mcr_asked); hash_destroytab(mcr_index);
		strunzone(mcr_who);
		mcr_ready = FALSE; mcr_req = 0; mcr_next = 0; mcr_count = 0; mcr_reqn = 0;
	}
	if (!mcr_ready)
	{
		mcr_names = buf_create(); mcr_data = buf_create(); mcr_seen = buf_create();
		mcr_queue = buf_create(); mcr_asked = buf_create();
		mcr_index = hash_createtab(4096, EV_FLOAT);
		mcr_who = strzone(who); mcr_ready = TRUE; mcr_failed = FALSE;
	}
	mcr_qn = 0;
	if (mcr_req)
	if (gettime(0) - mcr_sent > 12)
	{
		mcr_req = 0; mcr_failed = TRUE; mcr_next = gettime(0) + 30;
	}
};

float(string name) MCard_Index =
{
	local float row;
	name = strtolower(name);
	row = hash_get(mcr_index, name, -1, EV_FLOAT);
	if (row >= 0) return row;
	row = mcr_count; mcr_count = mcr_count + 1;
	hash_add(mcr_index, name, row, HASH_REPLACE | EV_FLOAT);
	bufstr_set(mcr_names, row, name);
	return row;
};

void(float row) MCard_Want =
{
	local float i;
	if (mcr_qn >= 16) return;
	if (strcmp(bufstr_get(mcr_data, row), ""))
	if (gettime(0) - stof(bufstr_get(mcr_seen, row)) < 60) return;
	for (i = 0; i < mcr_qn; i = i + 1)
		if (stof(bufstr_get(mcr_queue, i)) == row) return;
	bufstr_set(mcr_queue, mcr_qn, ftos(row)); mcr_qn = mcr_qn + 1;
};

void() MCard_End =
{
	local float i;
	local string q, name;
	if (!mcr_qn || mcr_req || gettime(0) < mcr_next || !MF_Online()) return;
	q = "cards=";
	for (i = 0; i < mcr_qn; i = i + 1)
	{
		name = bufstr_get(mcr_names, stof(bufstr_get(mcr_queue, i)));
		q = strcat(q, i ? "," : "", uri_escape(name));
		bufstr_set(mcr_asked, i, bufstr_get(mcr_queue, i));
	}
	if (strcmp(mcr_who, "")) q = strcat(q, "&player=", uri_escape(mcr_who));
	mcr_reqn = mcr_qn;
	mcr_req = Sty_Get(q);
	mcr_sent = gettime(0);
	if (!mcr_req) { mcr_failed = TRUE; mcr_next = gettime(0) + 30; }
};

float(float reqid, float code, string body) MCard_Reply =
{
	local int root, cards, card, a, b, c, d, complete;
	local float i, j, row, n, valid, known;
	local string name;
	if (!mcr_req || reqid != mcr_req) return FALSE;
	mcr_req = 0; mcr_failed = TRUE; mcr_next = gettime(0) + 30;
	if (code || strlen(body) > 131072) return TRUE;
	root = json_parse(body);
	if (!root) return TRUE;
	cards = json_find_object_child(root, "cards");
	n = json_get_length(cards);
	if (json_get_float(json_find_object_child(root, "v")) != 1
	    || strcmp(json_get_string(json_find_object_child(root, "requested_player")), mcr_who)
	    || strcmp(json_get_string(json_find_object_child(root, "style")), "clean")
	    || json_get_float(json_find_object_child(root, "track")) != 0
	    || json_get_float(json_find_object_child(root, "leg")) != 0
	    || n < 1 || n > 16)
	{ json_free(root); return TRUE; }
	known = json_get_float(json_find_object_child(root, "player_known"));
	valid = 0;
	for (i = 0; i < mcr_reqn; i = i + 1)
	{
		row = stof(bufstr_get(mcr_asked, i)); name = bufstr_get(mcr_names, row);
		for (j = 0; j < n; j = j + 1)
		{
			card = json_get_child_at_index(cards, (int)j);
			if (strcmp(json_get_string(json_find_object_child(card, "map")), name)) continue;
			a = json_find_object_child(card, "mine_wos"); b = json_find_object_child(card, "mine_all");
			c = json_find_object_child(card, "wr_wos"); d = json_find_object_child(card, "wr_all");
			complete = json_find_object_child(card, "complete");
			if (!a || !b || !c || !d || !complete) break;
			bufstr_set(mcr_data, row, sprintf("%s %s %s %s %g %g",
				Mlb_Itos(json_get_integer(a)), Mlb_Itos(json_get_integer(b)),
				Mlb_Itos(json_get_integer(c)), Mlb_Itos(json_get_integer(d)),
				json_get_float(complete), known));
			bufstr_set(mcr_seen, row, ftos(gettime(0)));
			valid = valid + 1;
			break;
		}
	}
	json_free(root);
	if (valid == mcr_reqn) { mcr_failed = FALSE; mcr_next = 0; }
	return TRUE;
};

// P1105: the player has a clean main finish of `name` (MCard_Draw's `done`), held now.
float(string name) MCard_Complete =
{
	local float row;
	row = MCard_Index(name);
	if (!strcmp(bufstr_get(mcr_data, row), "")) return FALSE;
	tokenize(bufstr_get(mcr_data, row));
	return stof(argv(5)) && stof(argv(4)) && Mlb_Stoi(argv(1)) > 0i;
};

/*
  P1105 (Lex, 29 Oct): a completed map's whole card, behind everything on it -- green fading
  in from the right, and a large Complete! crossing it right to left under the Play button.
  The text is clipped to the card within the list's own clip, which drawsetcliparea replaces
  rather than narrows, so the list's is put back after.
*/
void(vector pos, vector size, string name) MCard_Backdrop =
{
	local float i, n, x, edge, tsz, tw, period, off, was;
	local vector ap, cmin, cmax, omin, omax;
	if (!MCard_Complete(name)) return;
	n = 48;
	for (i = 0; i < n; i = i + 1)
	{
		x = floor(size_x * i / n); edge = floor(size_x * (i + 1) / n);
		sui_fill(pos + [x, 1], [edge - x, size_y - 2], '0.18 0.65 0.34', 0.30 * pow(i / (n - 1), 1.4), 0);
	}
	tsz = floor(size_y * 0.46);
	Font_Set(ui_font_display);
	tw = stringwidth("Complete!", TRUE, [tsz, tsz]);
	period = tw + size_x * 0.35;
	off = time * 42 - floor(time * 42 / period) * period;
	ap = pos;
	sui_transform_box(ap, size);
	was = sui_is_clipping(); omin = _sui_clip_area_mins; omax = _sui_clip_area_maxs;
	cmin = ap; cmax = ap + size;
	if (was)
	{
		cmin = [max(cmin_x, omin_x), max(cmin_y, omin_y)];
		cmax = [min(cmax_x, omax_x), min(cmax_y, omax_y)];
	}
	if (cmax_x > cmin_x && cmax_y > cmin_y)
	{
		drawsetcliparea(cmin_x, cmin_y, cmax_x - cmin_x, cmax_y - cmin_y);
		for (x = size_x - off; x > -tw; x = x - period)
			sui_text(pos + [x, size_y - tsz - floor(size_y * 0.06)], [tsz, tsz], "Complete!", '0.42 0.95 0.58', 0.20, 0);
		if (was) drawsetcliparea(omin_x, omin_y, omax_x - omin_x, omax_y - omin_y);
		else drawresetcliparea();
	}
	Font_Set(ui_font_ui);
};

void(vector pos, float width, float compact, string name, string id) MCard_Draw =
{
	local float row, have, done, known, stale, i, x, y, cw;
	local int wos, alltime, wrwos, wrall, ms;
	local string label, status, value;
	row = MCard_Index(name); MCard_Want(row);
	have = (strcmp(bufstr_get(mcr_data, row), "") != 0);
	wos = alltime = wrwos = wrall = 0i; known = done = 0;
	if (have)
	{
		tokenize(bufstr_get(mcr_data, row));
		wos = Mlb_Stoi(argv(0)); alltime = Mlb_Stoi(argv(1));
		wrwos = Mlb_Stoi(argv(2)); wrall = Mlb_Stoi(argv(3));
		done = stof(argv(4)); known = stof(argv(5));
	}
	done = (known && done && alltime > 0i);
	stale = (have && (gettime(0) - stof(bufstr_get(mcr_seen, row)) >= 60 || !MF_Online()));
	if (done)
		status = stale ? "(cached)" : "";       // P1105: the card's backdrop says Complete!
	else if (!MF_Online()) status = have ? "Cached records" : "Records offline";
	else if (!strcmp(mcr_who, "") || (have && !known)) status = "Link Steam for your times";
	else if (have) status = stale ? "No clean main finish  (cached)" : "No clean main finish";
	else status = mcr_failed ? "Records unavailable" : "Loading records...";
	sui_text(pos, '12 12 0', status, done ? SUI_THEME_GOOD : COL_DIM, 1, 0);
	sui_tooltip_for(id, "Main track, clean style. WOS = ranked public lobbies; overall = WOS + Momentum Mod + KSF. Local/community PBs are separate. Cached values may be older.", 2);
	cw = floor(width / (compact ? 2 : 4));
	for (i = 0; i < 4; i = i + 1)
	{
		x = pos_x + (compact ? (i - floor(i / 2) * 2) : i) * cw;
		y = pos_y + (compact ? 30 + floor(i / 2) * 36 : 36);
		label = i == 0 ? "Your WOS" : (i == 1 ? "Your overall" : (i == 2 ? "WOS WR" : "Overall WR"));
		ms = i == 0 ? wos : (i == 1 ? alltime : (i == 2 ? wrwos : wrall));
		value = ms > 0i ? Time_MsString(ms) : "--";
		sui_text([x, y], '12 12 0', label, COL_DIM, 1, 0);
		sui_text([x, y + 15], '16 16 0', value, ms > 0i ? COL_TEXT : COL_DIM, ms > 0i ? 1 : 0.65, 0);
	}
};

// P1080: the player's completed main maps (the cards' `complete`, all at once)
// for the Maps list's sort. State 1 known, 2 player unknown, 3 unavailable, 0 not yet.
float mcd_req, mcd_sent, mcd_next, mcd_at, mcd_state, mcd_count, mcd_zoned;
hashtable mcd_set;
string mcd_who;

void(float state) MCard_DoneState =
{
	if (state == mcd_state) return;
	mcd_state = state;
	mcd_ver = mcd_ver + 1;
};

void() MCard_DoneWant =
{
	if (!mcr_ready) return;
	if (!mcd_zoned || strcmp(mcd_who, mcr_who))
	{
		if (mcd_set) hash_destroytab(mcd_set);
		mcd_set = 0; mcd_req = 0; mcd_at = 0; mcd_next = 0; mcd_count = 0;
		if (mcd_zoned) strunzone(mcd_who);
		mcd_who = strzone(mcr_who); mcd_zoned = TRUE;
		mcd_state = -1; MCard_DoneState(0);
	}
	if (mcd_req)
	if (gettime(0) - mcd_sent > 12)
	{
		mcd_req = 0; mcd_next = gettime(0) + 30;
		if (mcd_state != 1) MCard_DoneState(3);
	}
	if (mcd_req || gettime(0) < mcd_next) return;
	if (!MF_Online()) { if (mcd_state != 1) MCard_DoneState(3); return; }
	if (!strcmp(mcd_who, "")) { MCard_DoneState(2); return; }
	if (mcd_at)
	if (gettime(0) - mcd_at < 60) return;
	mcd_req = Sty_Get(strcat("completed=", uri_escape(mcd_who)));
	mcd_sent = gettime(0);
	if (!mcd_req) { mcd_next = gettime(0) + 30; if (mcd_state != 1) MCard_DoneState(3); }
};

float(float reqid, float code, string body) MCard_DoneReply =
{
	local int root, maps;
	local float i, n, known, same, hit;
	local hashtable fresh;
	local string name;
	if (!mcd_req || reqid != mcd_req) return FALSE;
	mcd_req = 0; mcd_next = gettime(0) + 30;
	// A failed refresh keeps a known list (stale beats unknown); otherwise unavailable.
	if (code || strlen(body) > 262144) { if (mcd_state != 1) MCard_DoneState(3); return TRUE; }
	root = json_parse(body);
	if (!root) { if (mcd_state != 1) MCard_DoneState(3); return TRUE; }
	maps = json_find_object_child(root, "maps");
	n = json_get_length(maps);
	if (json_get_float(json_find_object_child(root, "v")) != 1
	    || strcmp(json_get_string(json_find_object_child(root, "requested_player")), mcd_who)
	    || strcmp(json_get_string(json_find_object_child(root, "style")), "clean")
	    || json_get_float(json_find_object_child(root, "track")) != 0
	    || json_get_float(json_find_object_child(root, "leg")) != 0
	    || !maps || n > 16384)
	{ json_free(root); if (mcd_state != 1) MCard_DoneState(3); return TRUE; }
	// Refreshes that change nothing must not bump mcd_ver: it re-sorts the list.
	known = json_get_float(json_find_object_child(root, "player_known")) ? 1 : 2;
	same = (known == mcd_state && n == mcd_count);
	fresh = hash_createtab(4096, EV_FLOAT);
	for (i = 0; i < n; i = i + 1)
	{
		name = strtolower(json_get_string(json_get_child_at_index(maps, (int)i)));
		hash_add(fresh, name, 1, HASH_REPLACE | EV_FLOAT);
		if (same)
		{
			hit = hash_get(mcd_set, name, 0, EV_FLOAT);
			if (!hit) same = FALSE;
		}
	}
	if (mcd_set) hash_destroytab(mcd_set);
	mcd_set = fresh;
	mcd_count = n;
	mcd_at = gettime(0); mcd_next = 0;
	if (!same) { mcd_state = known; mcd_ver = mcd_ver + 1; }
	json_free(root);
	return TRUE;
};

// `ui_compsort refresh`: expire the list now instead of after 60 s.
void() MCard_DoneRefresh =
{
	mcd_at = 0; mcd_next = 0;
};

// 1 complete, 0 known incomplete, -1 unknown (never folded into incomplete).
float(string name) MCard_Done =
{
	local float hit;
	if (mcd_state != 1) return -1;
	hit = hash_get(mcd_set, strtolower(name), 0, EV_FLOAT);
	return hit ? 1 : 0;
};

string() MCard_DoneNote =
{
	if (mcd_state == 1) return "";
	if (mcd_state == 2) return "link Steam to sort";
	if (mcd_state == 3) return "records unavailable";
	return "loading...";
};

void() MCard_Probe =
{
	local float i, row;
	print(sprintf("mapdone: state %g count %g pending %g ver %g\n", mcd_state, mcd_count, mcd_req != 0, mcd_ver));
	print(sprintf("mapcards: ready %g keys %g requested %g pending %g failed %g queued %g\n",
		mcr_ready, mcr_count, mcr_reqn, mcr_req != 0, mcr_failed, mcr_qn));
	if (!mcr_ready) return;
	for (i = 0; i < mcr_reqn; i = i + 1)
	{
		row = stof(bufstr_get(mcr_asked, i));
		print(sprintf("mapcard: %s %s\n", bufstr_get(mcr_names, row), bufstr_get(mcr_data, row)));
	}
};
