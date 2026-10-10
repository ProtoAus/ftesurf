//Opt-in ranked table only; shell/room share the existing SUI bracket.
float scn_handle, scn_failed, scn_painted, scn_revision, scn_count, scn_oldcount;
//256 widgets at the bridge; this table budgets 24 nine-cell rows + 6 metadata.
#define SCN_ROWS 24
#define SCN_VALUES 1024
#define SCN_LABELS 256
float scn_page, scn_pagesize, scn_serial, scn_hover, scn_layoutchanged;
var float scn_pick = -1;
var float scn_labels = -1, scn_keys = -1, scn_rawlabels = -1;
float scn_plainchanged, scn_plainutf8;
var float scn_online_epoch = -1;
float *scn_cells;
float scn_tokens[48];
vector scn_pos, scn_size;
float scn_ref;		//Fastest online ms on the board, once a build.
string scn_context;	//map|leg|tab|filter the page number belongs to; outlives a close.
//Rebuilding ~220 labels every frame made five times legacy's temp-string garbage
//(5.4 against 1.05 MiB/s held open, tools/p603soak.py). Whatever moves a row,
//authority or input rebuilds at once (scn_sig*); a label that only reads
//differently waits SCN_PERIOD.
#define SCN_PERIOD 0.1
float scn_built, scn_stale;
vector scn_sig1, scn_sig2;

void() Scores_NativeClose =
{
	if (scn_handle) NUI_Close(scn_handle);
	scn_handle = 0;
	scn_painted = scn_hover = scn_revision = scn_count = scn_oldcount = 0;
	if (scn_labels >= 0) buf_del(scn_labels);
	if (scn_keys >= 0) buf_del(scn_keys);
	if (scn_rawlabels >= 0) buf_del(scn_rawlabels);
	scn_labels = scn_keys = scn_rawlabels = -1;
	scn_online_epoch = -1;
	if (scn_cells) memfree(scn_cells);
	scn_cells = __NULL__;
};

//A pin from the hold, chat, a focus blip or a rescan keeps the player's place, as
//legacy scroll does (Patch 357); a fresh gesture starts at the top.
void(float top) Scores_NativeReset =
{
	Scores_NativeClose();
	scn_failed = 0;
	scn_serial = 16;
	if (top) scn_page = 0;
};

float() Scores_NativeFront =
{
	local float held;
	if (!sui_style_focused) return FALSE;
	if (chat_typing) return FALSE;
	held = UI_CursorHeld();
	if (held & UIC_SCORES) held = held - UIC_SCORES;
	if (held) return FALSE; //Replay input precedes scores too.
	if (!NUI_GameFocus()) return FALSE;
	return TRUE;
};

void(float visible) Scores_NativeFrame =
{
	if (!visible) { Scores_NativeClose(); return; }
	if (!cvar("ui_native_scores")) { Scores_NativeClose(); return; }
	if (!sc_held && !rec_sb_open) { Scores_NativeClose(); return; }
	if (!Scores_NativeFront()) Scores_NativeClose();
};

//The engine refuses a snapshot holding a control byte or malformed UTF-8, and one
//refused label costs the whole table (a name such as ^U0001 decolorizes to one).
//Emit exactly what PlugUI_LabelValid accepts: bad bytes become '?', and the 95-byte
//cut lands on a sequence boundary.
//0 = the string builtins see bytes, 2 = code points, 1 = code points that chr2str
//writes back as raw bytes (utf8_enable without com_parseutf8). The engine reads both as ints.
float() Scores_NativePlainMode =
{
	if (fabs(cvar("utf8_enable")) < 1) return 0;
	return (cvar("com_parseutf8") >= 1) ? 2 : 1;
};

string(string s) Scores_NativePlain =
{
	local float i, n, c, b, k, need, low, code, used, utf8, good;
	local string out;
	s = strdecolorize(s);
	utf8 = Scores_NativePlainMode();	//str2chr reads code points when set, bytes otherwise
	n = strlen(s);
	//Printable ASCII is nearly every label and needs nothing; rebuilding it below
	//costs two temp strings a character. Sound only after strdecolorize, which
	//re-encodes: a raw overlong sequence would otherwise read as ASCII here.
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (c < 32 || c > 126) break;
	}
	if (i == n && n <= 95) return s;
	out = "";
	used = 0;
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		need = 0;
		if (c == 9 || c == 10 || c == 13) c = 32;
		if (c < 32 || c == 127) c = 63;
		else if (c >= 128)
		{
			if (utf8)
			{
				//chr2str re-encodes a code point; only its range can be wrong.
				if (utf8 == 1 || c > 0x10ffff) c = 63;
				else if (c >= 0xd800 && c <= 0xdfff) c = 63;
				else if (c >= 0x10000) need = 3;
				else if (c >= 0x800) need = 2;
				else need = 1;
			}
			else
			{
				low = code = 0;
				if (c >= 0xc2 && c <= 0xdf) { need = 1; low = 0x80; code = c & 31; }
				else if (c >= 0xe0 && c <= 0xef) { need = 2; low = 0x800; code = c & 15; }
				else if (c >= 0xf0 && c <= 0xf4) { need = 3; low = 0x10000; code = c & 7; }
				good = (need > 0);
				if (i + need >= n) good = FALSE;
				if (good)
					for (k = 1; k <= need; k = k + 1)
					{
						b = str2chr(s, i + k);
						if (b < 0x80 || b > 0xbf) good = FALSE;
						code = code * 64 + (b & 63);
					}
				if (code < low || code > 0x10ffff) good = FALSE;
				if (code >= 0xd800 && code <= 0xdfff) good = FALSE;
				if (!good) { c = 63; need = 0; }
			}
		}
		if (used + 1 + need > 95) break;
		if (need && !utf8)
		{
			out = strcat(out, substring(s, i, need + 1));
			i = i + need;
		}
		else out = strcat(out, chr2str(c));
		used = used + 1 + need;
	}
	return out;
};

void(float id, float row, float type, float value, string label) Scores_NativeCell =
{
	local float at;
	at = scn_count * 4;
	scn_cells[SCN_VALUES + at] = id;
	scn_cells[SCN_VALUES + 1 + at] = row;
	scn_cells[SCN_VALUES + 2 + at] = type;
	scn_cells[SCN_VALUES + 3 + at] = value;
	//The same static cell otherwise decolorizes and replaces three control
	//characters every frame. Cache only this pure transform, not live metadata.
	if (scn_plainchanged || strcmp(label, bufstr_get(scn_rawlabels, scn_count)))
	{
		bufstr_set(scn_rawlabels, scn_count, label);
		bufstr_set(scn_labels, SCN_LABELS + scn_count, Scores_NativePlain(label));
	}
	scn_count = scn_count + 1;
};

string() Scores_NativeContext =
{
	return sprintf("%s|%g|%g|%g|%g", rec_sb_legmap, rec_sb_leg, rec_sb_tab,
		rec_sb_filter, Scores_IsOnline() ? 0 : rec_sb_rowgen);
};

string(float row) Scores_NativeKey =
{
	local string key;
	if (!Scores_IsOnline())
	{
		key = bufstr_get(rec_sb_bpath, row);
		if (!strcmp(key, "")) key = sprintf("lobby:%g:%s:%g", row,
			bufstr_get(rec_sb_bowner, row), rec_sb_rowticks[row]);
	}
	else
	{
		key = Scores_LineKey(row);
		if (!strcmp(key, "")) key = sprintf("missing:%s:%g:%g", bufstr_get(ob_bplayer, row),
			ob_ticks[row], ob_rank[row]);
	}
	return strcat(Scores_NativeContext(), "|", key);
};

float(float row, float slot) Scores_NativeToken =
{
	local float j, k, token;
	local string key;
	token = 0;
	key = Scores_NativeKey(row);
	//A row usually keeps its slot: look there before copying out every key.
	if (strcmp(key, bufstr_get(scn_keys, slot)) == 0)
	{
		token = scn_tokens[slot];
		for (k = 0; k < slot; k = k + 1)
			if (scn_tokens[SCN_ROWS + k] == token) token = 0;
	}
	if (!token)
	for (j = 0; j < SCN_ROWS; j = j + 1)
		if (strcmp(key, bufstr_get(scn_keys, j)) == 0)
		{
			token = scn_tokens[j];
			for (k = 0; k < slot; k = k + 1)
				if (scn_tokens[SCN_ROWS + k] == token) token = 0;
			if (token) break;
		}
	if (!token)
	{
		if (scn_serial >= 1048574) return 0; //Exact QC IDs; validation then selects fallback.
		scn_serial = scn_serial + 1;
		token = scn_serial;
	}
	bufstr_set(scn_keys, SCN_ROWS + slot, key);
	scn_tokens[SCN_ROWS + slot] = token;
	return token;
};

void(float row, float slot) Scores_NativeRow =
{
	local float token, ref, tick, usable, line, selected, type, classification;
	local string name, age, runword, why, replay, lineword, gap, timeword, key;
	ref = 0;
	token = Scores_NativeToken(row, slot);
	gap = "";
	if (!Scores_IsOnline())
	{
		tick = Timer_Tick();
		name = bufstr_get(rec_sb_bowner, row);
		age = bufstr_get(rec_sb_bdate, row);
		classification = Scores_Clean(row);
		runword = classification == RC_UNKNOWN ? "--" : FS_RunClassName(classification);
		if (classification == RC_CLEAN)
			if (rec_sb_rowflags[row] > 0) runword = FS_RunKindName(rec_sb_rowflags[row]);
		why = "";
		replay = "";
		if (rec_sb_rowtag[row] == RT_LOBBY)
		{
			if (rec_sb_rowflags[row] > 0) why = FS_CertWhy(rec_sb_rowflags[row]);
			if (!strcmp(why, "")) why = "lobby";
		}
		else if (rec_sb_rowtag[row] == RT_LAST || rec_sb_rowtag[row] == RT_CHEAT) why = "latest";
		else if (rec_sb_rowver[row] > 0 && rec_sb_rowver[row] < 5) why = "old clock";
		usable = Scores_Passes(row);
		if (!usable) name = strcat(name, " [filtered]");
		timeword = rec_sb_rowticks[row] > 0 ? Time_TickString(rec_sb_rowticks[row], tick) : "--:--.---";
		if (rec_sb_best > 0 && rec_sb_rowticks[row] > 0)
		{
			if (rec_sb_rowticks[row] == rec_sb_best) gap = "best";
			else gap = strcat("+", Time_TickString(rec_sb_rowticks[row] - rec_sb_best, tick));
		}
		Scores_NativeCell(token * 16 + 1, token, 1, 0, ftos(row + 1));
	}
	else
	{
		ref = scn_ref;
		name = bufstr_get(ob_bname, row);
		if (row == ob_mine) name = strcat(name, " (you)");
		age = Online_AgeString(row);
		runword = FS_RunClassName(FS_RunClass(ob_flags[row]));
		why = Online_WhyString(row);
		usable = TRUE; //Missing replay clicks retain the existing explanatory hand-off.
		replay = Online_RepString(row);
		if (Online_RowRep(row) < 1)
			if (strcmp(bufstr_get(ob_bget, row), ""))
			{
				replay = "Get demo";
				line = Scores_LineFind(Scores_LineKey(row));
				if (line >= 0) replay = sb_ln_st[line] == SBL_FAIL ? "retry" : "queued";
				if (!strcmp(bufstr_get(ob_bget, row), om_token))
				{
					if (om_state == OM_WAIT) replay = "queued";
					if (om_state == OM_FAIL) replay = "retry";
				}
			}
		if (ob_ver[row] > 0) replay = strcat(replay, " (verified)");
		timeword = Time_TickString(ob_ticks[row], 1 / ob_rate[row]);
		if (ref > 0)
		{
			if (ob_ms[row] == ref) gap = "best";
			else if (ob_ms[row] > ref) gap = strcat("+", Time_MsString((int)ob_ms[row] - (int)ref));
		}
		Scores_NativeCell(token * 16 + 1, token, 1, 0, ftos(ob_rank[row]));
	}
	if (!strcmp(name, "")) name = "unknown";
	if (!strcmp(age, "")) age = "--";
	Scores_NativeCell(token * 16 + 2, token, 1, 0, timeword);
	Scores_NativeCell(token * 16 + 3, token, 1, 0, gap);
	Scores_NativeCell(token * 16 + 4, token, usable ? 2 : 1, 0, name);
	Scores_NativeCell(token * 16 + 5, token, 1, 0, replay);
	Scores_NativeCell(token * 16 + 6, token, 1, 0, age);
	Scores_NativeCell(token * 16 + 7, token, 1, 0, runword);
	Scores_NativeCell(token * 16 + 8, token, 1, 0, why);
	key = Scores_LineKey(row);
	line = Scores_LineFind(key);
	selected = (line >= 0);
	lineword = "off";
	if (line >= 0)
	{
		if (sb_ln_st[line] == SBL_ON) lineword = "on";
		else if (sb_ln_st[line] == SBL_FAIL) lineword = "failed";
		else lineword = "queued";
	}
	type = 3;
	if (!strcmp(key, "") || !usable) { type = 1; selected = 0; lineword = "--"; }
	Scores_NativeCell(token * 16 + 9, token, type, selected, lineword);
};

float() Scores_NativeFontPx =
{
	local float px;
	px = cvar("ui_native_scores_font");
	//Bound requests before snapping; NaN/Inf/out-of-range use the default bake.
	if (!(px > 0 && px <= 128)) return 13;
	if (px > 22) return 24;
	if (px > 18) return 20;
	if (px > 14.5) return 16;
	return 13;
};

float() Scores_NativePublish =
{
	local float i, j, changed;
	local vector widget;
	changed = (scn_count != scn_oldcount || scn_layoutchanged);
	for (i = 0; i < scn_count; i = i + 1)
	{
		for (j = 0; j < 4; j = j + 1)
			if (scn_cells[i * 4 + j] != scn_cells[SCN_VALUES + i * 4 + j]) changed = TRUE;
		if (strcmp(bufstr_get(scn_labels, i), bufstr_get(scn_labels, SCN_LABELS + i)) != 0) changed = TRUE;
	}
	if (!changed) return TRUE;
	scn_revision = scn_revision + 1;
	if (!NUI_ModelBegin(scn_handle, scn_revision, scn_count)) return FALSE;
	for (i = 0; i < scn_count; i = i + 1)
	{
		widget = [scn_cells[SCN_VALUES + i * 4], scn_cells[SCN_VALUES + 1 + i * 4], scn_cells[SCN_VALUES + 2 + i * 4]];
		if (!NUI_ModelWidget(scn_handle, i, widget, scn_cells[SCN_VALUES + 3 + i * 4],
			bufstr_get(scn_labels, SCN_LABELS + i))) return FALSE;
	}
	if (!NUI_ModelCommit(scn_handle)) return FALSE;
	for (i = 0; i < scn_count; i = i + 1)
	{
		for (j = 0; j < 4; j = j + 1) scn_cells[i * 4 + j] = scn_cells[SCN_VALUES + i * 4 + j];
		bufstr_set(scn_labels, i, bufstr_get(scn_labels, SCN_LABELS + i));
	}
	scn_oldcount = scn_count;
	for (i = 0; i < SCN_ROWS; i = i + 1)
	{
		bufstr_set(scn_keys, i, bufstr_get(scn_keys, SCN_ROWS + i));
		scn_tokens[i] = scn_tokens[SCN_ROWS + i];
	}
	return TRUE;
};

float(vector p, vector sz) Scores_NativeDraw =
{
	local float n, rows, i, r, more, actionid, actionrow, role, pick, highlight, seekdone, fontpx, pagesize, pagechanged, fresh;
	local vector action, sig1, sig2;
	local string context, message, standing;
	scn_painted = FALSE;
	scn_pick = -1;
	if (!cvar("ui_native_scores")) return FALSE;
	if (scn_failed) return FALSE;
	if (!Scores_NativeFront()) { Scores_NativeClose(); return FALSE; }
	if (!NUI_ModelAvailable()) { Scores_NativeClose(); return FALSE; }
	pagesize = NUI_ModelLimit() >= 256 ? SCN_ROWS : 6;
	pagechanged = (pagesize != scn_pagesize);
	if (pagechanged) scn_page = floor(scn_page / pagesize) * pagesize;
	scn_pagesize = pagesize;
	if (Scores_IsOnline())
	{
		//Transient loading must not open/upload/close a native context every
		//frame. Readiness precedes allocation; legacy owns the explanation.
		if (rec_sb_leg < 0 || rec_sb_leg >= rec_sb_legn) { Scores_NativeClose(); return FALSE; }
		if (!Online_Shows(rec_sb_legtrack[rec_sb_leg], rec_sb_legnum[rec_sb_leg],
			Scores_TierOf(), Scores_StyleOf())) { Scores_NativeClose(); return FALSE; }
	}
	context = sprintf("%s|%g|%g|%g", rec_sb_legmap, rec_sb_leg, rec_sb_tab, rec_sb_filter);
	if (strcmp(context, scn_context) != 0)
	{
		if (strcmp(scn_context, "")) strunzone(scn_context);
		scn_context = strzone(context);
		scn_page = 0;
		scn_stale = TRUE;
	}
	if (!scn_handle)
	{
		scn_handle = NUI_Open(205);
		if (!scn_handle) { scn_failed = TRUE; return FALSE; }
		scn_cells = (float *)memalloc(SCN_VALUES * 2 * 4);
		scn_labels = buf_create();
		scn_keys = buf_create();
		scn_rawlabels = buf_create();
		if (!scn_cells) { Scores_NativeClose(); scn_failed = TRUE; return FALSE; }
		if (scn_labels < 0) { Scores_NativeClose(); scn_failed = TRUE; return FALSE; }
		if (scn_keys < 0) { Scores_NativeClose(); scn_failed = TRUE; return FALSE; }
		if (scn_rawlabels < 0) { Scores_NativeClose(); scn_failed = TRUE; return FALSE; }
		for (i = 0; i < SCN_ROWS * 2; i = i + 1) scn_tokens[i] = 0;
		if (scn_serial < 16) scn_serial = 16;
	}
	n = rec_sb_rown;
	message = "";
	if (Scores_IsOnline()) n = ob_n;
	highlight = -1;
	seekdone = FALSE;
	standing = "";
	if (Scores_IsOnline())
	{
		highlight = ob_mine;
		if (n > 0)
		if (Scores_OnlineSeekReady())
		{
			if (ob_mine >= 0) scn_page = floor(ob_mine / scn_pagesize) * scn_pagesize;
			seekdone = TRUE;
		}
		if (Scores_StandingOutside())
		{
			standing = sprintf("Your standing #%g", rec_sb_finrank);
			if (rec_sb_finbest > 0) standing = strcat(standing, "  ", Time_MsString((int)rec_sb_finbest));
			standing = strcat(standing, "  ", getplayerkeyvalue(player_localnum, "name"));
		}
	}
	else if (Scores_FinishedLeg())
	{
		for (i = 0; i < n; i = i + 1)
			if (rec_sb_rowticks[i] == rec_sb_finticks) { highlight = i; break; }
		if (rec_sb_seek)
		if (n > 0)
		{
			if (highlight >= 0) scn_page = floor(highlight / scn_pagesize) * scn_pagesize;
			seekdone = TRUE;
		}
	}
	if (scn_page >= n) scn_page = max(0, floor((n - 1) / scn_pagesize) * scn_pagesize);
	rows = min(scn_pagesize, max(0, n - scn_page));
	more = (scn_page + rows < n);
	if (Scores_IsOnline())
		if (ob_more) more = TRUE;
	//The room's docked rect may cover the right edge. Keep the entire native
	//viewport (including its scrollbar) in the remaining visible run area.
	if (pl_panelsize_y > 0)
		if (pl_panelpos_x > p_x && pl_panelpos_x < p_x + sz_x)
			if (pl_panelpos_y < p_y + sz_y && pl_panelpos_y + pl_panelsize_y > p_y)
				sz_x = pl_panelpos_x - p_x - 1;
	fontpx = Scores_NativeFontPx();
	sig1 = [scn_page, n, highlight];
	sig2 = [pagesize + fontpx * 1000, (rec_sb_open != 0) * 2 + more, Scores_IsOnline() ? ob_epoch : rec_sb_rowgen];
	fresh = (!scn_count || scn_stale || seekdone || pagechanged || p != scn_pos || sz != scn_size);
	if (sig1 != scn_sig1 || sig2 != scn_sig2) fresh = TRUE;
	if (cltime < scn_built || cltime >= scn_built + SCN_PERIOD) fresh = TRUE;
	if (fresh)
	{
		scn_stale = FALSE; scn_built = cltime; scn_sig1 = sig1; scn_sig2 = sig2;
		if (n == 0) message = Scores_IsOnline() ?
			sprintf("no %s times on this leg yet", Scores_StyleOf()) : "no runs recorded on this leg yet";
		else message = sprintf("runs %g-%g of %g", scn_page + 1, scn_page + rows, n);
		scn_ref = 0;
		if (Scores_IsOnline())
			for (i = 0; i < ob_n; i = i + 1)
				if (ob_ms[i] > 0)
					if (scn_ref == 0 || ob_ms[i] < scn_ref) scn_ref = ob_ms[i];
		scn_plainchanged = (scn_plainutf8 != Scores_NativePlainMode());
		scn_plainutf8 = Scores_NativePlainMode();
		scn_count = 0;
		Scores_NativeCell(1, 1, 3, rec_sb_open != 0, rec_sb_open ? "pinned" : "peek");
		Scores_NativeCell(2, 1, 1, 0, message);
		Scores_NativeCell(3, 1, scn_page > 0 ? 2 : 1, 0, "Previous");
		Scores_NativeCell(4, 1, more ? 2 : 1, 0, "Next");
		//Display-only checkbox metadata: row token highlights, label pins a standing.
		Scores_NativeCell(5, 1, 3, 0, standing);
		//Keep the original schema/default compatible; older providers reject the
		//optional font metadata and get the same gesture-latched legacy cover.
		if (fontpx != 13) Scores_NativeCell(6, 1, 1, 0, ftos(fontpx));
		for (i = 0; i < SCN_ROWS; i = i + 1)
		{
			bufstr_set(scn_keys, SCN_ROWS + i, "");
			scn_tokens[SCN_ROWS + i] = 0;
			if (i < rows) Scores_NativeRow(scn_page + i, i);
		}
		if (highlight >= scn_page && highlight < scn_page + rows)
		{
			scn_cells[SCN_VALUES + 17] = scn_tokens[SCN_ROWS + highlight - scn_page];
			scn_cells[SCN_VALUES + 19] = 1;
		}
		scn_layoutchanged = (p != scn_pos || sz != scn_size || pagechanged);
		//Even identical rows are a new snapshot: cancel a held pre-reply click.
		if (Scores_IsOnline())
			if (scn_online_epoch != ob_epoch) scn_layoutchanged = TRUE;
		if (!Scores_NativePublish()) { Scores_NativeClose(); scn_failed = TRUE; return FALSE; }
		if (Scores_IsOnline()) scn_online_epoch = ob_epoch;
		scn_pos = p; scn_size = sz;
	}
	drawsetcliparea(p_x, p_y, sz_x, sz_y);
	i = NUI_Draw(scn_handle);
	drawresetcliparea();
	if (!i) { Scores_NativeClose(); scn_failed = TRUE; return FALSE; }
	scn_painted = TRUE;
	//Leave legacy its one-shot seek if publishing/drawing failed this frame.
	if (seekdone) rec_sb_seek = FALSE;
	if (!rec_sb_open) return TRUE;
	for (i = 0; i < 16; i = i + 1)
	{
		action = NUI_ModelPoll(scn_handle, scn_revision);
		if (action == '0 0 0') break;
		scn_stale = TRUE;	//whatever it does shows on the next frame
		actionid = action_x; actionrow = action_y;
		if (actionrow == 1)
		{
			if (actionid == 3) scn_page = max(0, scn_page - scn_pagesize);
			else if (actionid == 4)
			{
				if (scn_page + scn_pagesize < n) scn_page = scn_page + scn_pagesize;
				else if (Scores_IsOnline()) Online_FetchMore();
			}
			break;
		}
		pick = -1;
		//The token names a slot of the page published this frame. Its stored key
		//must still be that row's key in CURRENT data, so a row elsewhere with an
		//equal key cannot answer. Native never supplies an index, path or command.
		for (r = 0; r < rows; r = r + 1)
			if (actionrow == scn_tokens[r])
			{
				if (strcmp(Scores_NativeKey(scn_page + r), bufstr_get(scn_keys, r)) == 0) pick = scn_page + r;
				break;
			}
		if (pick < 0) continue;
		role = actionid - actionrow * 16;
		if (role == 4) { scn_pick = pick; break; }
		if (role == 9)
		{
			rec_sb_lnpick = pick + 1;
			break;
		}
	}
	return TRUE;
};

float() Scores_NativePick = { return scn_pick; };

float(float evtype, float scanx, float chary, float devid) Scores_NativeInput =
{
	local vector physical, virtualsize, point;
	local float inside, event, a, b;
	event = a = b = 0;
	if (!scn_painted) return FALSE;
	if (!rec_sb_open)
	{
		//Passive peek never joins mouse capture, even though the table renders.
		if (evtype == IE_MOUSEABS) return -1;
		if (evtype == IE_KEYDOWN || evtype == IE_KEYUP)
			if (scanx == K_MOUSE1) return -1;
		return FALSE;
	}
	if (!Scores_NativeFront()) { Scores_NativeClose(); return FALSE; }
	//SUI's cursor sees every position, including those sent while this table was
	//not painting; a private copy went stale and clicked the row it last saw.
	point = _cursor_position;
	if (evtype == IE_MOUSEABS) point = [scanx, chary, 0];
	inside = (point_x >= scn_pos_x && point_y >= scn_pos_y &&
		point_x < scn_pos_x + scn_size_x && point_y < scn_pos_y + scn_size_y);
	if (point_x >= pl_panelpos_x && point_y >= pl_panelpos_y &&
		point_x < pl_panelpos_x + pl_panelsize_x && point_y < pl_panelpos_y + pl_panelsize_y) inside = FALSE;
	if (!inside)
	{
		if (scn_hover) NUI_Input(scn_handle, 6, 0, 0);
		scn_hover = FALSE;
		return FALSE;
	}
	scn_hover = TRUE;
	if (evtype == IE_MOUSEABS)
	{
		physical = getproperty(VF_SCREENPSIZE);
		virtualsize = getproperty(VF_SCREENVSIZE);
		if (virtualsize_x <= 0 || virtualsize_y <= 0) return FALSE;
		event = 1; a = scanx * physical_x / virtualsize_x; b = chary * physical_y / virtualsize_y;
	}
	else if (evtype == IE_KEYDOWN || evtype == IE_KEYUP)
	{
		if (scanx == K_MOUSE1) { event = 2; a = 0; b = (evtype == IE_KEYDOWN); }
		else if (evtype == IE_KEYDOWN)
		{
			if (scanx == K_MWHEELUP) { event = 3; b = 1; }
			else if (scanx == K_MWHEELDOWN) { event = 3; b = -1; }
		}
	}
	if (!event) return FALSE;
	if (event != 1)
	{
		physical = getproperty(VF_SCREENPSIZE);
		virtualsize = getproperty(VF_SCREENVSIZE);
		if (virtualsize_x <= 0 || virtualsize_y <= 0) return FALSE;
		if (!NUI_Input(scn_handle, 1, point_x * physical_x / virtualsize_x,
			point_y * physical_y / virtualsize_y)) { Scores_NativeClose(); scn_failed = TRUE; return TRUE; }
	}
	if (!NUI_Input(scn_handle, event, a, b)) { Scores_NativeClose(); scn_failed = TRUE; }
	//Keep SUI's mouse state current, but there are no SUI run hitboxes here.
	sui_input_event(evtype, scanx, chary, devid);
	return TRUE;
};
