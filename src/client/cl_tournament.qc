// Tournament alpha: server-owned state, atomically published at tourney_end.
#define UIC_TOURNAMENT 65536
#define TOUR_PLAYERS 72
#define TOUR_MAPS 24
float tour_open, tour_stage, tour_revision, tour_stage_revision;
float tour_np, tour_nm, tour_sp, tour_sm, tour_competitors, tour_spectators;
float tour_round, tour_rounds, tour_seconds, tour_remaining, tour_clock_at;
float tour_received, tour_stage_at, tour_create_at, tour_entered, tour_next_action, tour_spec_page, tour_request_at, tour_cards_page;
string tour_id, tour_phase, tour_host, tour_me, tour_turn, tour_kind, tour_map, tour_reserve, tour_note;
string tour_header;
strbuf tour_players, tour_maps, tour_stage_players, tour_stage_maps;
float tour_page[TOUR_MAPS], tour_cell[TOUR_MAPS];
string tour_mapname[TOUR_MAPS], tour_pic[TOUR_MAPS];
var filestream tour_meta = -1;
float tour_meta_rows;
float tour_create_seats, tour_create_seconds, tour_openat;
// P1649: map play order (0 = unscheduled), the leave confirmation, and the centre announcement.
float tour_mapord[TOUR_MAPS];
float tour_leaveat, tour_evtat, tour_evtfor;
string tour_evt, tour_evtsub;
vector tour_evtcolour;
// Keys pressed while the panel is open; only their releases are the panel's, so a key
// held when it opened (+forward, +duck) still gets its release (as cl_report.qc's Rp_Took).
#define TOUR_KN 8
float tour_kd[TOUR_KN];

float(string s, float limit) Tour_Token =
{
	local float i, c;
	if (s == "" || strlen(s) > limit) return FALSE;
	for (i = 0; i < strlen(s); i += 1)
	{
		c = str2chr(s, i);
		if (c >= 'a' && c <= 'z') continue;
		if (c >= 'A' && c <= 'Z') continue;
		if (c >= '0' && c <= '9') continue;
		if (c == '_' || c == '-') continue;
		return FALSE;
	}
	return TRUE;
};

string(string encoded, float limit) Tour_Text =
{
	local string s, out;
	local float i, c;
	s = uri_unescape(encoded); out = "";
	for (i = 0; i < min(strlen(s), limit); i += 1)
	{
		c = str2chr(s, i);
		if (c < 32 || c == 127) continue;
		out = strcat(out, chr2str(c));
	}
	if (out == "-") return "";
	return out;
};

float(string s) Tour_MapOK =
{
	local float i, c;
	if (!strlen(s) || strlen(s) > 64) return FALSE;
	for (i = 0; i < strlen(s); i += 1)
	{
		c = str2chr(s, i);
		if (c >= 'a' && c <= 'z') continue;
		if (c >= 'A' && c <= 'Z') continue;
		if (c >= '0' && c <= '9' && i > 0) continue;
		if (i > 0 && (c == '_' || c == '-' || c == '+' || c == '.')) continue;
		return FALSE;
	}
	return TRUE;
};

void() Tour_Close =
{
	local float i;
	for (i = 0; i < TOUR_KN; i += 1) tour_kd[i] = 0;
	tour_open = FALSE;
	UI_CursorRelease(UIC_TOURNAMENT);
	sui_reset_actions();
};

void() Tour_Clear =
{
	local float i;
	// An empty-state poll is not a user close. Keep the configuration panel
	// and its cursor claim open; otherwise an idle server shuts it every2s.
	sui_reset_actions();
	tour_stage = tour_revision = tour_np = tour_nm = tour_entered = 0;
	tour_id = tour_phase = tour_me = tour_note = "";
	tour_next_action = tour_request_at = tour_spec_page = tour_cards_page = 0;
	if (tour_meta >= 0) fclose(tour_meta);
	tour_meta = -1;
	for (i = 0; i < TOUR_MAPS; i += 1)
	{
		tour_page[i] = tour_cell[i] = -1;
		tour_pic[i] = tour_mapname[i] = "";
	}
};

void() Tour_Open =
{
	local float i;
	if (UI_CursorHeld() || rec_sb_open)
	{
		print("tournament: close the other window first\n");
		return;
	}
	tour_open = TRUE; tour_openat = cltime;
	for (i = 0; i < TOUR_KN; i += 1) tour_kd[i] = 0;
	sui_reset_actions();
	UI_CursorClaim(UIC_TOURNAMENT);
};

void() Tour_Init =
{
	local float create;
	create = cvar("cl_tourney_create");
	tour_players = buf_create(); tour_maps = buf_create();
	tour_stage_players = buf_create(); tour_stage_maps = buf_create();
	registercvar("cl_tourney_create", "0", 0); // transient menu -> connected CSQC handoff
	cvar_set("cl_tourney_create", create ? "1" : "0");
	registercommand("tournament");
	registercommand("tourney_begin"); registercommand("tourney_player");
	registercommand("tourney_map"); registercommand("tourney_end");
	registercommand("tourney_clear"); registercommand("tourney_notice");
	registercommand("tourney_open"); registercommand("tourney_clock");
	tour_create_seats = 2; tour_create_seconds = 300;
	Tour_Clear();
};

void() Tour_Shutdown =
{
	Tour_Clear();
	cvar_set("cl_tourney_create", "0");
};

void(string action) Tour_Ask =
{
	if (action != "resync" && action != "open" && substring(action, 0, 7) != "create ")
	if (tour_id == "" || cltime - tour_received > 20)
	{ tour_note = "This view is out of date. Click Refresh first."; return; }
	if (cltime < tour_next_action) return;
	tour_next_action = cltime + 0.75;
	localcmd(strcat("cmd tour ", action, "\n"));
	tour_request_at = cltime + 8;
	tour_note = "Sent. Waiting for the server...";
};

// P1649: the big centre line for a phase change, read from the staged snapshot before it is swapped
// in (tour_phase is still the old phase). Nothing on the first snapshot of a match: a late joiner
// is not shown a stale GO.
void(strbuf staged) Tour_Event =
{
	local string nphase, outs, wins, name, mname;
	local float i, minplace, place;
	tokenize(tour_header);
	nphase = argv(3);
	if (nphase == tour_phase || (strcmp(argv(1), tour_id) && !(tour_id == "" && nphase == "loading"))) return;
	mname = uri_unescape(argv(12)); tour_evtsub = Tour_Text(argv(14), 180);
	tour_evt = sprintf("ROUND %s OF %s", argv(6), argv(7));
	minplace = 999; outs = wins = "";
	for (i = 0; i < tour_sp; i += 1)
	{
		tokenize(bufstr_get(staged, i));
		name = Tour_Text(argv(2), 32); place = stof(argv(8));
		if (argv(3) == "eliminated" && place > 0)
		{
			if (place < minplace) { minplace = place; outs = name; }
			else if (place == minplace) outs = strcat(outs, ", ", name);
		}
		if (argv(3) == "player" && place == 1) wins = strlen(wins) ? strcat(wins, ", ", name) : name;
	}
	tour_evtat = cltime; tour_evtcolour = '0.45 0.85 1'; tour_evtfor = 3;
	if (nphase == "loading") { tour_evtsub = (mname != "-") ? mname : ""; }
	else if (nphase == "live") { tour_evt = "GO!"; tour_evtsub = ""; tour_evtfor = 1.5; tour_evtcolour = '0.45 1 0.55'; }
	else if (nphase == "results")
	{
		tour_evt = strlen(wins) ? ((strstrofs(wins, ", ", 0) >= 0) ? "SHARED FIRST PLACE" : strcat(wins, " WINS!")) : "ROUND OVER";
		tour_evtsub = strlen(outs) ? strcat("Out: ", outs) : tour_evtsub; tour_evtfor = 5;
		if (strlen(wins)) tour_evtcolour = '1 0.82 0.2';
	}
	else if (nphase == "finished")
	{
		tour_evt = strlen(wins) ? ((strstrofs(wins, ", ", 0) >= 0) ? "SHARED FIRST PLACE" : strcat(wins, " WINS THE TOURNAMENT")) : "TOURNAMENT OVER";
		tour_evtsub = (strstrofs(wins, ", ", 0) >= 0) ? wins : ""; tour_evtfor = 8; tour_evtcolour = '1 0.82 0.2';
	}
	else if (nphase == "aborted" || nphase == "cancelled") { tour_evt = "NO CONTEST"; tour_evtfor = 6; tour_evtcolour = '1 0.4 0.35'; }
	else tour_evt = "";
};

float(float argc, string line) Tour_Command =
{
	local string op, tourmap, role;
	local float rev, tmp, i, keepclock;
	local string phase;
	op = argv(0);
	if (op == "tournament")
	{
		if (argv(1) == "status")
		{
			print(sprintf("tournament: open %g revision %.0f phase %s players %g maps %g staging %g\n", tour_open, tour_revision, tour_phase, tour_np, tour_nm, tour_stage));
			return TRUE;
		}
		if (tour_open) Tour_Close();
		else { Tour_Open(); Tour_Ask("open"); }
		return TRUE;
	}
	if (substring(op, 0, 8) != "tourney_") return FALSE;
	if (op == "tourney_clear") { Tour_Clear(); return TRUE; }
	if (op == "tourney_open") { if (!tour_open) Tour_Open(); return TRUE; }
	if (op == "tourney_notice") { tour_note = Tour_Text(argv(1), 180); tour_request_at = 0; return TRUE; }
	if (op == "tourney_clock")
	{
		if (argc == 4 && stof(argv(1)) == tour_revision && !strcmp(argv(3), tour_phase))
		{ tour_remaining = bound(0, stof(argv(2)), 900); tour_clock_at = tour_received = cltime; }
		return TRUE;
	}
	if (op == "tourney_begin")
	{
		tour_stage = FALSE;
		if (argc != 15 || strlen(line) > 1024) return TRUE;
		rev = stof(argv(2));
		if (!Tour_Token(argv(1), 64) || rev < 1 || rev > 16777215 || rev != floor(rev)) return TRUE;
		phase = argv(3);
		if (phase != "lobby" && phase != "draft" && phase != "loading" && phase != "countdown" && phase != "live" && phase != "results" && phase != "finished" && phase != "cancelled" && phase != "aborted") return TRUE;
		if (!strcmp(argv(1), tour_id) && rev < tour_revision) return TRUE;
		tour_header = line; tour_stage_revision = rev;
		tour_sp = tour_sm = tour_competitors = tour_spectators = 0;
		tour_stage = TRUE; tour_stage_at = cltime;
		return TRUE;
	}
	if (op == "tourney_player")
	{
		if (!tour_stage) return TRUE;
		role = argv(3);
		if (argc != 9 || tour_sp >= TOUR_PLAYERS || !Tour_Token(argv(1), 128) || strlen(line) > 768)
		{ tour_stage = FALSE; return TRUE; }
		if (role != "player" && role != "spectator" && role != "eliminated") { tour_stage = FALSE; return TRUE; }
		if (role != "spectator") tour_competitors += 1;
		else tour_spectators += 1;
		if (tour_competitors > 8 || tour_spectators > 64) { tour_stage = FALSE; return TRUE; }
		bufstr_set(tour_stage_players, tour_sp, line); tour_sp += 1;
		return TRUE;
	}
	if (op == "tourney_map")
	{
		if (!tour_stage) return TRUE;
		tourmap = uri_unescape(argv(1));
		if ((argc != 4 && argc != 5) || tour_sm >= TOUR_MAPS || !Tour_MapOK(tourmap) || strlen(line) > 256)
		{ tour_stage = FALSE; return TRUE; }
		bufstr_set(tour_stage_maps, tour_sm, line); tour_sm += 1;
		return TRUE;
	}
	if (op == "tourney_end")
	{
		if (!tour_stage || argc != 2 || stof(argv(1)) != tour_stage_revision) return TRUE;
		Tour_Event(tour_stage_players);
		tokenize(tour_header);
		keepclock = (!strcmp(tour_id, argv(1)) && !strcmp(tour_phase, argv(3)) && tour_round == stof(argv(6)));
		if (strcmp(tour_id, argv(1))) tour_entered = 0;
		// The countdown hands the controls back: an open panel sends empty moves (F6 reopens it).
		if (tour_open && argv(3) == "countdown" && tour_phase != "countdown") Tour_Close();
		tour_id = argv(1); tour_revision = tour_stage_revision;
		tour_phase = argv(3); tour_host = argv(4); tour_me = argv(5);
		tour_round = stof(argv(6)); tour_rounds = stof(argv(7)); tour_seconds = stof(argv(8));
		if (!keepclock) { tour_remaining = bound(0, stof(argv(9)), 900); tour_clock_at = cltime; }
		tour_turn = argv(10); tour_kind = argv(11); tour_map = argv(12); tour_reserve = argv(13);
		tour_note = Tour_Text(argv(14), 180);
		tmp = tour_players; tour_players = tour_stage_players; tour_stage_players = tmp;
		tmp = tour_maps; tour_maps = tour_stage_maps; tour_stage_maps = tmp;
		tour_np = tour_sp; tour_nm = tour_sm; tour_stage = FALSE; tour_received = cltime; tour_request_at = 0;
		for (i = 0; i < tour_nm; i += 1)
		{
			tour_mapord[i] = (tokenize(bufstr_get(tour_maps, i)) == 5) ? bound(0, stof(argv(4)), TOUR_MAPS) : 0;
			tour_mapname[i] = uri_unescape(argv(1)); tour_pic[i] = "";
			tour_page[i] = tour_cell[i] = -1;
		}
		if (tour_meta >= 0) fclose(tour_meta);
		tour_meta = fopen("data/mapmeta.txt", FILE_READ); tour_meta_rows = 0;
		return TRUE;
	}
	return TRUE;
};

// Called outside draw: bounded atlas lookup/precache, never an asset load in a button renderer.
void() Tour_Frame =
{
	local float n, i, page, cell;
	local string ln, who;
	if (tour_request_at && cltime > tour_request_at)
	{ tour_request_at = 0; tour_note = "The server did not answer. Click Refresh."; }
	if (tour_stage && cltime - tour_stage_at > 15) { tour_stage = FALSE; tour_note = "Could not load the tournament state. Click Refresh."; }
	if (cvar("cl_tourney_create") != 0)
	{
		if (!tour_create_at) tour_create_at = gettime(0) + 30;
		if (cvar("cl_tourney_create_until") > 0) tour_create_at = min(tour_create_at, cvar("cl_tourney_create_until"));
		who = getplayerkeyvalue(player_localnum, "*ahash");
		if (gettime(0) > tour_create_at)
		{
			cvar_set("cl_tourney_create", "0"); tour_create_at = 0;
			tour_note = "Create handoff expired. Link your account, then open Tournament to create.";
			print(strcat("tournament: ", tour_note, "\n"));
		}
		else if (who != "")
		{
			cvar_set("cl_tourney_create", "0"); tour_create_at = 0;
			// Open configuration; don't race social-token issuance with an automatic mutation.
			if (!tour_open) Tour_Open();
			tour_note = "Choose seats and round time, then click Create.";
		}
	}
	if (tour_id != "" && !tour_entered && tour_me != "-" && tour_me != "")
	if (getplayerkeyvalue(player_localnum, "*ahash") != "")
	{
		tour_entered = TRUE;
		localcmd("cmd tour enter\n");
	}
	if (tour_meta < 0) return;
	for (n = 0; n < 64; n += 1)
	{
		ln = fgets(tour_meta); tour_meta_rows += 1;
		if (ln == __NULL__) { fclose(tour_meta); tour_meta = -1; return; }
		if (tour_meta_rows > 12000) { fclose(tour_meta); tour_meta = -1; return; }
		if (tokenize(ln) < 8) continue;
		if (argv(0) != "meta") continue;
		page = MilkSky_Index(argv(6)); cell = MilkSky_Index(argv(7));
		if (page < 0 || page > 128 || cell < 0 || cell >= 448) continue;
		for (i = 0; i < tour_nm; i += 1)
		if (!strcmp(argv(1), tour_mapname[i]))
		{
			tour_page[i] = page; tour_cell[i] = cell;
			tour_pic[i] = precache_pic(strcat("gfx/mapthumbs/atlas", ftos(page)));
		}
	}
};

float(float key, float down) Tour_Took =
{
	local float i, f;
	f = -1;
	for (i = 0; i < TOUR_KN; i += 1)
	{
		if (key && tour_kd[i] == key) { if (!down) tour_kd[i] = 0; return TRUE; }
		if (!tour_kd[i]) f = i;
	}
	if (down && key && f >= 0) tour_kd[f] = key;
	return FALSE;
};

float(float evtype, float x, float y, float devid) Tour_Input =
{
	if (!tour_open) return FALSE;
	if (evtype == IE_KEYUP)
	{
		sui_input_event(evtype, x, y, devid); // SUI's confirm keys (Enter, pad A) and modifiers
		return Tour_Took(x, FALSE);
	}
	if (evtype == IE_KEYDOWN)
	{
		if (getkeybind(x) == "toggleconsole") { Tour_Close(); return FALSE; }
		// An OS repeat is not a press (cl_chat.qc's chat_rep): a key held into the panel keeps its release.
		if (chat_rep) return TRUE;
		Tour_Took(x, TRUE);
		// Esc, F6 during a match (Tour_Key), or the key bound to `tournament` closes it again.
		if (x == K_ESCAPE || ((getkeybind(x) == "tournament" || (x == K_F6 && (tour_id != "" || serverkey("tournament") != ""))) && cltime - tour_openat > 0.3)) { Tour_Close(); return TRUE; }
		sui_input_event(evtype, x, y, devid);
		return TRUE;
	}
	if (evtype == IE_MOUSEABS || evtype == IE_MOUSEDELTA)
	{
		sui_input_event(evtype, x, y, devid);
		return TRUE;
	}
	return FALSE;
};

// ---------------------------------------------------------------------------
//  F6 panel, in the main-menu lobby's style: native text, panels, seat colours.
// ---------------------------------------------------------------------------
vector(float seat) Tour_SeatColour =
{
	if (seat == 0) return SUI_THEME_ACCENT;
	if (seat == 1) return SUI_THEME_BAD;
	if (seat == 2) return SUI_THEME_GOOD;
	if (seat == 3) return SUI_THEME_WARN;
	if (seat == 4) return SUI_THEME_ACCENT2;
	if (seat == 5) return SUI_THEME_INFO;
	if (seat == 6) return SUI_THEME_FOCUS;
	return SUI_THEME_DIM;
};

// Text fitted into a box (cut at a character boundary), centred on the caps;
// align 0 left, 1 centre, 2 right; face 1 = the display font.
void(vector pos, vector size, string text, float want, vector colour, float align = 0, float face = 0) Tour_Place =
{
	local float previous, legacy, w, lo, hi, mid, x;
	local vector glyph;
	if (text == "" || size_x <= 0) return;
	previous = ui_font_cur;
	Font_Set(face ? ui_font_display : ui_font_ui);
	legacy = drawfont; drawfont = Font_NativeSlot(legacy);
	glyph = sui_native_text_size(want);
	w = stringwidth(text, TRUE, glyph);
	if (w > size_x)
	{
		lo = 0; hi = strlen(text);
		while (lo < hi)
		{
			mid = ceil((lo + hi) / 2);
			if (stringwidth(strcat(substring(text, 0, UI_CharBytes(text, mid)), "..."), TRUE, glyph) <= size_x) lo = mid;
			else hi = mid - 1;
		}
		text = strcat(substring(text, 0, UI_CharBytes(text, lo)), "...");
		w = stringwidth(text, TRUE, glyph);
	}
	drawfont = legacy;
	x = pos_x;
	if (align == 1) x = pos_x + floor((size_x - w) / 2);
	if (align == 2) x = pos_x + size_x - w;
	sui_native_text([x, pos_y + (size_y - glyph_y) / 2 + FONT_CAPDROP * glyph_y], text, want, colour, 1);
	Font_Set(previous);
};

float(vector pos, string text, vector colour, float right = FALSE) Tour_Pill =
{
	local float previous, legacy, w;
	previous = ui_font_cur; Font_Set(ui_font_ui);
	legacy = drawfont; drawfont = Font_NativeSlot(legacy);
	w = ceil(stringwidth(text, TRUE, sui_native_text_size(12))) + 16;
	drawfont = legacy; Font_Set(previous);
	if (right) pos_x -= w;
	sui_style_box(pos, [w, 20], 10, SUI_THEME_PANEL * 0.7 + colour * 0.2, SUI_THEME_PANEL * 0.4 + colour * 0.6, 1);
	Tour_Place(pos, [w, 20], text, 12, colour, 1);
	return w;
};

// style: 0 plain, 1 go, 2 danger. Acting buttons need a fresh snapshot.
float(string id, vector pos, vector size, string label, float style, float enabled) Tour_Btn =
{
	local float hot, held;
	local vector fill, edge, colour, tint;
	if (id != "tour_close" && id != "tour_refresh" && id != "tour_maps_prev" && id != "tour_maps_next"
		&& id != "tour_create_seats" && id != "tour_create_time" && id != "tour_create" && id != "tour_spec_next")
		enabled = (enabled && tour_id != "" && cltime - tour_received <= 20);
	if (enabled) sui_action_element(pos, size, id, sui_noop);
	hot = (enabled && sui_is_hovered(id));
	held = (enabled && sui_is_held(id));
	if (style)
	{
		tint = (style == 2) ? SUI_THEME_BAD : SUI_THEME_GOOD;
		fill = hot ? tint : (SUI_THEME_CHIP * 0.72 + tint * 0.24);
		if (held) fill = tint * 0.8;
		edge = tint; colour = hot ? SUI_THEME_WELL : tint;
	}
	else
	{
		fill = held ? SUI_THEME_PRESSED : (hot ? SUI_THEME_HOVER : SUI_THEME_CHIP);
		edge = hot ? SUI_THEME_ACCENT : SUI_THEME_EDGE;
		colour = hot ? SUI_THEME_ACCENT : SUI_THEME_TEXT;
	}
	if (!enabled) { fill = SUI_THEME_CHIP; edge = SUI_THEME_EDGE; colour = SUI_THEME_MUTED; }
	sui_style_box(pos, size, 7, fill, edge, enabled ? 1 : 0.7);
	Tour_Place(pos + '8 0 0', size - '16 0 0', label, 16, colour, 1);
	return enabled && sui_is_released(id);
};

// The cached atlas cell, or the map's name as a title card.
void(vector pos, vector size, float i) Tour_Thumb =
{
	local float cell;
	local vector uv;
	if (i >= 0 && tour_pic[i] != "" && iscachedpic(tour_pic[i]))
	{
		cell = tour_cell[i]; uv = [(cell % 16) * 128 / 2048, floor(cell / 16) * 72 / 2048];
		sui_subpic(pos, size, tour_pic[i], uv, '0.0625 0.03515625 0', '1 1 1', 1, 0);
	}
	else
	{
		sui_fill(pos, size, '0.05 0.05 0.07', 1, 0);
		if (i >= 0 && size_y >= 36) Tour_Place(pos + '8 0 0', size - '16 0 0', tour_mapname[i], (size_y >= 80) ? 32 : 24, SUI_THEME_EDGE_HI, 1, 1);
	}
	sui_border_box(pos, size, 1, SUI_THEME_EDGE, 1, 0);
};

string(float seconds) Tour_Clock =
{
	local float m, sec;
	seconds = max(0, ceil(seconds)); m = floor(seconds / 60); sec = seconds - m * 60;
	return strcat(ftos(m), (sec < 10) ? ":0" : ":", ftos(sec));
};

float tour_order[TOUR_PLAYERS], tour_seat[TOUR_PLAYERS], tour_maporder[TOUR_MAPS];
string tour_besttext[TOUR_PLAYERS];

void(vector scr) Tour_Draw =
{
	local vector p, size, at, colour;
	local float i, j, k, y, host, accepted, ready, remaining, risk, worst, dnfs, seconds, can, ties, myplayer;
	local float n, seat, rh, lw, bh, top, cards, first, cw, chh, x, bw, spec, rows, mine, place, best, bt;
	local string who, name, role, status, line, phase;
	if (!tour_open) return;
	if (UI_CursorHeld() != UIC_TOURNAMENT || rec_sb_open) { Tour_Close(); return; }
	Font_Set(ui_font_ui);
	// The body grows with the roster and the map list, within the screen.
	n = 0;
	for (i = 0; i < tour_np; i += 1) { tokenize(bufstr_get(tour_players, i)); if (argv(3) != "spectator") n += 1; }
	bh = bound(220, 46 + max(n * 58, min(tour_nm, 10) * 50) + 8, 560);
	size = [min(1120, scr_x - 32), min(scr_y - 32, 172 + bh + 74)];
	p = [floor((scr_x - size_x) * 0.5), floor((scr_y - size_y) * 0.5)];
	sui_begin(scr_x, scr_y);
	sui_fill('0 0 0', scr, '0 0 0', 0.35, 0);
	sui_style_panel(p, size, 12, 1);
	Tour_Place(p + '20 10 0', [size_x - 300, 44], (serverkey("tournament_test") == "1") ? "Tournament  (local test)" : "Tournament", 32, SUI_THEME_TEXT, 0, 1);
	if (Tour_Btn("tour_close", p + [size_x - 132, 14], '116 34 0', "Close (Esc)", 0, TRUE)) Tour_Close();
	if (Tour_Btn("tour_refresh", p + [size_x - 244, 14], '104 34 0', "Refresh", 0, TRUE)) Tour_Ask("resync");
	if (size_x < 600 || size_y < 440)
	{
		Tour_Place(p + '20 70 0', [size_x - 40, 22], "The tournament panel needs a window of at least 640 x 480.", 16, SUI_THEME_WARN);
		sui_end(); Font_Reset(); return;
	}
	if (tour_id == "")
	{
		// The old connected create flow; the main menu's Tournaments page is the usual way in.
		Tour_Place(p + '20 70 0', [size_x - 40, 26], "Create a tournament on this server", 20, SUI_THEME_TEXT);
		Tour_Place(p + '20 100 0', [size_x - 40, 20], "Most players start from the main menu's Tournaments page instead.", 12, SUI_THEME_DIM);
		if (Tour_Btn("tour_create_seats", p + '20 132 0', '160 36 0', sprintf("Seats: %g", tour_create_seats), 0, TRUE))
			tour_create_seats = (tour_create_seats >= 8) ? 2 : tour_create_seats + 1;
		if (Tour_Btn("tour_create_time", p + '192 132 0', '170 36 0', sprintf("Round: %s", Tour_Clock(tour_create_seconds)), 0, TRUE))
		{
			if (tour_create_seconds < 300) tour_create_seconds += 60;
			else if (tour_create_seconds == 300) tour_create_seconds = 600;
			else if (tour_create_seconds == 600) tour_create_seconds = 900;
			else tour_create_seconds = 60;
		}
		if (Tour_Btn("tour_create", p + '374 132 0', '150 36 0', "Create", 1, (getplayerkeyvalue(player_localnum, "*ahash") != "" && !tour_request_at)))
			Tour_Ask(sprintf("create %g %g", tour_create_seats, tour_create_seconds));
		if (getplayerkeyvalue(player_localnum, "*ahash") == "")
			Tour_Place(p + '20 182 0', [size_x - 40, 20], "Waiting for a verified linked account before creating.", 12, SUI_THEME_WARN);
		Tour_Place(p + [20, size_y - 40], [size_x - 40, 20], tour_note, 12, SUI_THEME_WARN);
		sui_end(); Font_Reset(); return;
	}

	// --- who stands where: competitors fastest first, DNF next, eliminated by place
	host = (tour_me != "-" && tour_me != "" && !strcmp(tour_me, tour_host));
	accepted = ready = myplayer = 0; dnfs = ties = 0; worst = -1; risk = -1; n = 0; spec = 0; seat = 0;
	for (i = 0; i < tour_np; i += 1)
	{
		tokenize(bufstr_get(tour_players, i));
		if (!strcmp(argv(1), tour_me)) { accepted = stof(argv(5)); ready = stof(argv(4)); myplayer = (argv(3) == "player"); }
		if (argv(3) == "spectator") { spec += 1; continue; }
		tour_seat[i] = seat; seat += 1;
		tour_besttext[i] = "DNF";
		// P1649: the snapshot's tickrate is ticks per second; Time_TickString wants seconds per tick.
		if (stof(argv(6)) > 0 && stof(argv(7)) > 0) tour_besttext[i] = Time_TickString(stof(argv(6)), 1 / stof(argv(7)));
		tour_order[n] = i; n += 1;
		if (argv(3) != "player") continue;
		seconds = stof(argv(6));
		if (seconds <= 0) { dnfs += 1; risk = i; }
		else if (stof(argv(7)) > 0 && !dnfs)
		{
			seconds /= stof(argv(7));
			if (seconds == worst) ties += 1;
			if (seconds > worst) { worst = seconds; risk = i; ties = 0; }
		}
	}
	if (dnfs > 1 || (!dnfs && ties)) risk = -1;
	for (j = 1; j < n; j += 1)
		for (k = j; k > 0; k -= 1)
		{
			// Rank key: playing with a time < playing DNF < eliminated (by place).
			tokenize(bufstr_get(tour_players, tour_order[k]));
			best = (argv(3) == "eliminated") ? 3000000 + stof(argv(8)) : ((stof(argv(6)) > 0 && stof(argv(7)) > 0) ? stof(argv(6)) / stof(argv(7)) : 2000000);
			tokenize(bufstr_get(tour_players, tour_order[k - 1]));
			bt = (argv(3) == "eliminated") ? 3000000 + stof(argv(8)) : ((stof(argv(6)) > 0 && stof(argv(7)) > 0) ? stof(argv(6)) / stof(argv(7)) : 2000000);
			if (best >= bt) break;
			i = tour_order[k]; tour_order[k] = tour_order[k - 1]; tour_order[k - 1] = i;
		}

	// --- hero: phase, round, map, clock
	phase = tour_phase;
	remaining = max(0, tour_remaining - (cltime - tour_clock_at)); // P1649: every phase's server clock counts down
	colour = SUI_THEME_DIM; line = strtoupper(phase);
	if (phase == "live") { colour = SUI_THEME_GOOD; line = "LIVE"; }
	if (phase == "countdown") { colour = SUI_THEME_FOCUS; line = "GET READY"; }
	if (phase == "loading") { colour = SUI_THEME_WARN; line = "READY CHECK"; }
	if (phase == "results") { colour = SUI_THEME_INFO; line = "ROUND RESULTS"; }
	if (phase == "finished") { colour = SUI_THEME_ACCENT2; line = "FINISHED"; }
	if (phase == "draft") { colour = SUI_THEME_INFO; line = "MAP DRAFT"; }
	if (phase == "lobby") { colour = SUI_THEME_ACCENT; line = "LOBBY"; }
	at = p + '20 62 0';
	sui_style_box(at, [size_x - 40, 96], 10, SUI_THEME_CHIP, SUI_THEME_EDGE, 1);
	x = 16;
	for (i = 0; i < tour_nm; i += 1)
		if (tour_mapname[i] == tour_map) break;
	if (tour_map != "" && tour_map != "-")
	{
		Tour_Thumb(at + '10 10 0', '135 76 0', (i < tour_nm) ? i : -1);
		x = 160;
	}
	Tour_Pill(at + [x, 14], line, colour);
	Tour_Place(at + [x, 36], [size_x - 40 - x - 220, 36], (tour_map != "" && tour_map != "-") ? tour_map : "No map yet", 32, SUI_THEME_TEXT, 0, 1);
	Tour_Place(at + [x, 70], [size_x - 40 - x - 220, 18], (tour_rounds > 0) ? sprintf("Round %g of %g  |  %s per round", tour_round, tour_rounds, Tour_Clock(tour_seconds)) : sprintf("%s per round", Tour_Clock(tour_seconds)), 12, SUI_THEME_DIM);
	if (phase == "live" || phase == "countdown")
		Tour_Place(at + [size_x - 40 - 216, 8], '200 80 0', Tour_Clock(remaining), 64, (remaining <= 30) ? SUI_THEME_BAD : SUI_THEME_TEXT, 2, 1);
	else if (phase == "loading")
		Tour_Place(at + [size_x - 40 - 216, 8], '200 80 0', myplayer ? (ready ? "You are ready" : ((serverkey("tournament_auto") == "0") ? "Click Ready on map" : "Starts once everyone is here")) : "Players are loading", 16, SUI_THEME_DIM, 2);
	else if (phase == "results" || phase == "finished" || phase == "aborted" || phase == "cancelled")
		Tour_Place(at + [size_x - 40 - 216, 8], '200 80 0', sprintf((phase == "results") ? "Next round in %s" : "Back to normal play in %s", Tour_Clock(remaining)), 16, SUI_THEME_DIM, 2);

	// --- body: standings left, maps right
	top = 172; bh = size_y - top - 74; // clamped to the screen above
	lw = floor((size_x - 52) * 0.5);
	at = p + [20, top];
	sui_style_box(at, [lw, bh], 10, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	Tour_Place(at + '14 8 0', [lw - 28, 26], "standings", 20, SUI_THEME_ACCENT);
	Tour_Place(at + [lw - 200, 8], '186 26 0', spec ? sprintf("%g watching", spec) : "", 12, SUI_THEME_DIM, 2);
	rh = bound(40, floor((bh - 46) / max(1, n)) - 6, 52); y = 42;
	for (j = 0; j < n; j += 1)
	{
		if (y + rh > bh - 4) break;
		i = tour_order[j];
		tokenize(bufstr_get(tour_players, i));
		who = argv(1); name = Tour_Text(argv(2), 48); role = argv(3); mine = !strcmp(who, tour_me);
		place = stof(argv(8));
		colour = Tour_SeatColour(tour_seat[i]);
		sui_style_box(at + [10, y], [lw - 20, rh], 8, mine ? SUI_THEME_SELECTED : SUI_THEME_CHIP, mine ? SUI_THEME_ACCENT : SUI_THEME_EDGE, (role == "eliminated") ? 0.55 : 1);
		sui_fill(at + [10, y + 8], [4, rh - 16], colour, 1, 0);
		Tour_Place(at + [22, y], [26, rh], (role == "eliminated" && place > 0) ? sprintf("#%g", place) : ftos(j + 1), 16, (role == "eliminated") ? SUI_THEME_MUTED : colour);
		Tour_Place(at + [52, y + 3], [lw - 220, 22], strcat(name, mine ? " (you)" : ""), 16, (role == "eliminated") ? SUI_THEME_MUTED : SUI_THEME_TEXT);
		x = 52;
		if (!strcmp(who, tour_host)) x += Tour_Pill(at + [x, y + rh - 23], "HOST", SUI_THEME_ACCENT2) + 6;
		if (role == "player" && place == 1) Tour_Pill(at + [x, y + rh - 23], "WINNER", SUI_THEME_GOOD);
		else if (role == "eliminated") Tour_Pill(at + [x, y + rh - 23], "ELIMINATED", SUI_THEME_MUTED);
		else if (i == risk && phase == "live") Tour_Pill(at + [x, y + rh - 23], "AT RISK", SUI_THEME_BAD);
		else if (phase == "loading" || phase == "lobby") Tour_Pill(at + [x, y + rh - 23], stof(argv(4)) ? "READY" : (phase == "lobby" ? (stof(argv(5)) ? "ACCEPTED" : "SEAT OFFERED") : "NOT READY"), stof(argv(4)) ? SUI_THEME_GOOD : SUI_THEME_MUTED);
		Tour_Place(at + [lw - 170, y], [146, rh], tour_besttext[i], 20, (tour_besttext[i] == "DNF") ? SUI_THEME_MUTED : SUI_THEME_TEXT, 2);
		if (host && phase == "lobby")
		if (Tour_Btn(strcat("tour_seat", ftos(i)), at + [lw - 120, y + floor((rh - 30) / 2)], '96 30 0', "Unseat", 0, TRUE)) Tour_Ask(strcat("seat ", who));
		y += rh + 6;
	}

	at = p + [32 + lw, top]; cw = size_x - 52 - lw;
	sui_style_box(at, [cw, bh], 10, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	can = (phase == "draft" && !strcmp(tour_me, tour_turn) && tour_me != "-" && (tour_kind == "ban" || tour_kind == "pick"));
	if (phase == "draft") line = can ? sprintf("your turn: %s a map", tour_kind) : "map draft";
	else line = "maps";
	Tour_Place(at + '14 8 0', [cw - 28, 26], line, 20, can ? SUI_THEME_FOCUS : SUI_THEME_ACCENT);
	// One row per map, in play order: the current map, the picks by round (P1649: the server sends each
	// map's round), the reserve, played ones, the ones nobody picked, and the bans.
	for (i = 0; i < tour_nm; i += 1) tour_maporder[i] = i;
	for (j = 1; j < tour_nm; j += 1)
		for (k = j; k > 0; k -= 1)
		{
			tokenize(bufstr_get(tour_maps, tour_maporder[k])); status = argv(2);
			best = (tour_mapname[tour_maporder[k]] == tour_map) ? 0 : ((status == "picked") ? 1 + tour_mapord[tour_maporder[k]] / 100 : ((status == "reserve") ? 2 : ((status == "played") ? 3 : ((status == "pool") ? 4 : 5))));
			tokenize(bufstr_get(tour_maps, tour_maporder[k - 1])); status = argv(2);
			bt = (tour_mapname[tour_maporder[k - 1]] == tour_map) ? 0 : ((status == "picked") ? 1 + tour_mapord[tour_maporder[k - 1]] / 100 : ((status == "reserve") ? 2 : ((status == "played") ? 3 : ((status == "pool") ? 4 : 5))));
			if (best >= bt) break;
			i = tour_maporder[k]; tour_maporder[k] = tour_maporder[k - 1]; tour_maporder[k - 1] = i;
		}
	chh = 44; rows = max(1, floor((bh - 46 - ((tour_nm * (chh + 6) > bh - 46) ? 36 : 0)) / (chh + 6)));
	cards = rows;
	if (tour_cards_page * cards >= tour_nm) tour_cards_page = 0;
	first = tour_cards_page * cards;
	for (k = first; k < min(tour_nm, first + cards); k += 1)
	{
		i = tour_maporder[k];
		tokenize(bufstr_get(tour_maps, i)); status = argv(2);
		y = 42 + (k - first) * (chh + 6);
		line = "NOT PICKED"; colour = SUI_THEME_MUTED;
		if (status == "picked") { line = (tour_mapord[i] > 0) ? sprintf("ROUND %g", tour_mapord[i]) : "UP NEXT"; colour = SUI_THEME_GOOD; }
		if (status == "picked" && tour_mapord[i] == tour_round + 1) line = "UP NEXT";
		if (status == "played") { line = "PLAYED"; colour = SUI_THEME_DIM; }
		if (status == "reserve") { line = "RESERVE"; colour = SUI_THEME_INFO; }
		if (status == "banned") { line = "BANNED"; colour = SUI_THEME_BAD; }
		if (tour_mapname[i] == tour_map) { line = "NOW"; colour = SUI_THEME_ACCENT; }
		if (phase == "draft" && status == "pool") { line = "OPEN"; colour = SUI_THEME_DIM; }
		if (phase == "draft" && status == "picked") line = "PICKED";
		sui_style_box(at + [10, y], [cw - 20, chh], 8, SUI_THEME_CHIP, (line == "NOW") ? SUI_THEME_ACCENT : SUI_THEME_EDGE, (status == "banned") ? 0.55 : 1);
		Tour_Thumb(at + [16, y + 4], [floor((chh - 8) * 16 / 9), chh - 8], i);
		x = 28 + floor((chh - 8) * 16 / 9);
		Tour_Place(at + [x, y], [cw - x - 130, chh], tour_mapname[i], 16, (status == "banned") ? SUI_THEME_MUTED : SUI_THEME_TEXT);
		if (can && status == "pool")
		{
			if (Tour_Btn(strcat("tour_map", ftos(i)), at + [cw - 108, y + 7], [88, chh - 14], tour_kind, (tour_kind == "ban") ? 2 : 1, TRUE))
				Tour_Ask(strcat(tour_kind, " ", tour_mapname[i]));
		}
		else Tour_Pill(at + [cw - 20, y + floor((chh - 20) / 2)], line, colour, TRUE);
	}
	if (tour_nm > cards)
	{
		if (Tour_Btn("tour_maps_prev", at + [10, bh - 36], '96 28 0', "Previous", 0, tour_cards_page > 0)) tour_cards_page -= 1;
		if (Tour_Btn("tour_maps_next", at + [114, bh - 36], '80 28 0', "Next", 0, (tour_cards_page + 1) * cards < tour_nm)) tour_cards_page += 1;
	}

	// --- actions: leave/cancel left, the phase's own button(s) right
	y = p_y + size_y - 60; bw = 170;
	// P1649: one stray click used to end the match for everyone; leaving takes a second click.
	if (Tour_Btn("tour_leave", [p_x + 20, y], '140 40 0', (cltime < tour_leaveat) ? "Click again" : "Leave event", (cltime < tour_leaveat) ? 2 : 0, tour_id != ""))
	{
		if (cltime < tour_leaveat) { tour_leaveat = 0; Tour_Ask("leave"); }
		else
		{
			tour_leaveat = cltime + 4;
			tour_note = myplayer ? "Leaving drops you out of the tournament. Click again to leave." : "Click again to leave.";
		}
	}
	if (host && (phase == "lobby" || phase == "draft"))
	if (Tour_Btn("tour_cancel", [p_x + 172, y], '120 40 0', "Cancel", 2, TRUE)) Tour_Ask("cancel");
	x = p_x + size_x - 20;
	if (host && phase == "results") { x -= bw; if (Tour_Btn("tour_next", [x, y], [bw, 40], "Next round", 1, TRUE)) Tour_Ask("next"); x -= 10; }
	if (host && phase == "loading") { x -= bw; if (Tour_Btn("tour_start", [x, y], [bw, 40], "Start round", 1, TRUE)) Tour_Ask("start"); x -= 10; }
	if (myplayer && phase == "loading")
	{
		x -= bw;
		if (Tour_Btn("tour_ready", [x, y], [bw, 40], ready ? "Ready" : "Ready on map", ready ? 0 : 1, !strcmp(tour_map, serverkey("map"))))
			Tour_Ask("ready");
		x -= 10;
	}
	if (myplayer && phase == "lobby")
	{
		x -= bw; if (Tour_Btn("tour_accept", [x, y], [bw, 40], accepted ? "Accepted" : "Accept seat", accepted ? 0 : 1, !accepted)) Tour_Ask("accept"); x -= 10;
	}
	if (host && phase == "lobby") { x -= bw; if (Tour_Btn("tour_lock", [x, y], [bw, 40], "Lock roster", 1, TRUE)) Tour_Ask("lock"); x -= 10; }
	line = tour_note;
	if (cltime - tour_received > 20) line = "This view is out of date. Click Refresh.";
	if (line == "") line = (serverkey("tournament_test") == "1") ? "Local test: the practice partner does not surf or set times." : "Press F6 to close this panel.";
	Tour_Place([p_x + 304, y], [x - p_x - 316, 40], line, 12, (cltime - tour_received > 20) ? SUI_THEME_WARN : SUI_THEME_DIM);
	sui_end(); Font_Reset();
};

// ---------------------------------------------------------------------------
//  P1649: the match without opening F6 -- a banner, the standings and centre
//  announcements, for competitors, spectators and a host's stream alike.
// ---------------------------------------------------------------------------

// F6 belongs to the tournament while this server has a match: no bind needed (nothing shipped one).
// With no match, F6 keeps its bind; a report box on screen (it reads "F6 Send report") keeps its F6.
float(float scanx) Tour_Key =
{
	if (scanx != K_F6 || (tour_id == "" && serverkey("tournament") == "")) return FALSE;
	if (PE_BoxUp() || CR_BoxUp()) return FALSE;
	if (tour_open) Tour_Close();
	else { Tour_Open(); Tour_Ask("open"); }
	return TRUE;
};

float tour_hn, tour_hrow[TOUR_PLAYERS];
// Competitors fastest first, then no time yet, then the eliminated by place: tour_hrow[0..tour_hn).
void() Tour_Rank =
{
	local float i, j, k, a, b;
	tour_hn = 0;
	for (i = 0; i < tour_np && tour_hn < TOUR_PLAYERS; i += 1)
	{
		tokenize(bufstr_get(tour_players, i));
		if (argv(3) != "spectator") { tour_hrow[tour_hn] = i; tour_hn += 1; }
	}
	for (j = 1; j < tour_hn; j += 1)
		for (k = j; k > 0; k -= 1)
		{
			tokenize(bufstr_get(tour_players, tour_hrow[k]));
			a = (argv(3) == "eliminated") ? 3000000 + stof(argv(8)) : ((stof(argv(6)) > 0 && stof(argv(7)) > 0) ? stof(argv(6)) / stof(argv(7)) : 2000000);
			tokenize(bufstr_get(tour_players, tour_hrow[k - 1]));
			b = (argv(3) == "eliminated") ? 3000000 + stof(argv(8)) : ((stof(argv(6)) > 0 && stof(argv(7)) > 0) ? stof(argv(6)) / stof(argv(7)) : 2000000);
			if (a >= b) break;
			i = tour_hrow[k]; tour_hrow[k] = tour_hrow[k - 1]; tour_hrow[k - 1] = i;
		}
};

// What this viewer should do or expect next, in one line.
string(float remaining) Tour_NextStep =
{
	local float i, n, rd, mine, myready, myrank, host;
	local string mytime;
	host = (tour_me != "-" && tour_me != "" && !strcmp(tour_me, tour_host));
	n = rd = mine = myready = myrank = 0; mytime = "";
	for (i = 0; i < tour_hn; i += 1)
	{
		tokenize(bufstr_get(tour_players, tour_hrow[i]));
		if (argv(3) != "player") continue;
		n += 1;
		if (stof(argv(4))) rd += 1;
		if (!strcmp(argv(1), tour_me))
		{
			mine = TRUE; myready = stof(argv(4)); myrank = n;
			if (stof(argv(6)) > 0 && stof(argv(7)) > 0) mytime = Time_TickString(stof(argv(6)), 1 / stof(argv(7)));
		}
	}
	if (tour_phase == "loading")
	{
		if (serverkey("tournament_starts") == "1") return sprintf("Everyone is here: the round starts in %s%s", Tour_Clock(remaining), host ? "  (F6 to start now)" : "");
		if (serverkey("tournament_starts") == "2") return sprintf("Starting without the missing players in %s%s", Tour_Clock(remaining), host ? "  (F6 to start now)" : "");
		if (serverkey("tournament_auto") == "0")
		{
			if (mine && !myready) return "Press F6 and click Ready on map";
			if (host && n && rd == n) return "Everyone is ready: press F6 and click Start round";
			return sprintf("Ready: %g of %g. The host starts the round", rd, n);
		}
		return mine ? "Loading in. The round starts once everyone is here" : "Players are loading in";
	}
	if (tour_phase == "countdown") return mine ? "Get ready: you're held at the start until GO" : "The round is about to start";
	if (tour_phase == "live")
	{
		if (!mine) return "Watching: best times so far below";
		if (mytime != "") return sprintf("Your best: %s (%g of %g). Restart any time to beat it", mytime, myrank, n);
		return "No time yet: finish a clean run before the clock runs out";
	}
	if (tour_phase == "results") return sprintf("Round over. Next round in %s", Tour_Clock(remaining));
	if (tour_phase == "finished" || tour_phase == "aborted" || tour_phase == "cancelled")
		return sprintf("%sBack to normal play in %s", (tour_note != "") ? strcat(tour_note, "  ") : "", Tour_Clock(remaining));
	return "Press F6 for the tournament panel";
};

void(vector scr) Tour_Hud =
{
	local vector p, at, colour;
	local float w, h, x, remaining, i, rows, rh, risk, big, n, dnf, starts, sz1, sz2, lh1, lh2, pad;
	local string line, title, name, tm;
	// Plain draws only: sui_begin empties sui's single hit-test list and sui_end clears the click and typing
	// buffers, so an always-on bracket here broke every menu drawn after it (P1649 review). Hidden while
	// any panel holds the cursor.
	if (tour_id == "" || tour_open || rec_sb_open || UI_CursorHeld() || scr_x < 640) return;
	remaining = max(0, tour_remaining - (cltime - tour_clock_at));
	Tour_Rank();
	colour = '0.7 0.72 0.78'; line = strtoupper(tour_phase);
	if (tour_phase == "live") { colour = '0.45 1 0.55'; line = "LIVE"; }
	if (tour_phase == "countdown") { colour = '0.45 0.85 1'; line = "GET READY"; }
	if (tour_phase == "loading") { colour = '1 0.82 0.2'; line = "LOADING"; }
	if (tour_phase == "results") { colour = '0.45 0.85 1'; line = "RESULTS"; }
	if (tour_phase == "finished") { colour = '1 0.82 0.2'; line = "FINISHED"; }
	if (tour_phase == "aborted" || tour_phase == "cancelled") { colour = '1 0.4 0.35'; line = "NO CONTEST"; }
	title = (tour_rounds > 0) ? sprintf("Round %g of %g", max(1, tour_round), tour_rounds) : "Tournament";
	if (tour_map != "" && tour_map != "-") title = strcat(title, "  |  ", tour_map);
	sz1 = 9 * ui_cv_scale; sz2 = 6.5 * ui_cv_scale; lh1 = Font_Px(sz1); lh2 = Font_Px(sz2); pad = 8 * ui_cv_scale;
	w = min(scr_x - 32, max(380, 34 * lh1)); h = pad * 2 + lh1 + 4 * ui_cv_scale + lh2;
	p = '16 8 0';
	// Top-left: the run timer owns the top centre and the map card the top right (first playtest shots).
	drawfill(p, [w, h], '0.05 0.06 0.09', 0.78, 0);
	drawfill(p, [3 * ui_cv_scale, h], colour, 0.95, 0);
	Font_Set(ui_font_display);
	x = p_x + pad + 3 * ui_cv_scale;
	HUD_Text([x, p_y + pad, 0], line, sz1, colour, 1);
	x = x + stringwidth(line, TRUE, [lh1, lh1]) + pad;
	HUD_Text([x, p_y + pad, 0], title, sz1, '1 1 1', 1);
	n = dnf = 0; risk = -1;
	for (i = 0; i < tour_hn; i += 1)
	{
		tokenize(bufstr_get(tour_players, tour_hrow[i]));
		if (argv(3) != "player") continue;
		n += 1; risk = i;
		if (!(stof(argv(6)) > 0)) dnf += 1;
	}
	if (n < 2) risk = -1;
	starts = (tour_phase == "loading" && serverkey("tournament_starts") != "");
	if (tour_phase == "live" || tour_phase == "countdown" || tour_phase == "results" || starts)
		HUD_TextR([p_x + w - pad, p_y + pad, 0], Tour_Clock(remaining), sz1, (tour_phase == "live" && remaining <= 30) ? '1 0.4 0.35' : '1 1 1', 1);
	Font_Set(ui_font_ui);
	HUD_Text([p_x + pad + 3 * ui_cv_scale, p_y + pad + lh1 + 4 * ui_cv_scale, 0], Tour_NextStep(remaining), sz2, '0.75 0.78 0.84', 1);

	// Standings: rank, name, best. While live, who would be out now is red: everyone without a time, or else
	// the slowest (surfd's settle).
	rows = min(tour_hn, 8); rh = lh2 + 5 * ui_cv_scale;
	at = [p_x, p_y + h + 6];
	if (rows > 0)
	{
		drawfill(at, [w, rows * rh + pad], '0.05 0.06 0.09', 0.7, 0);
		for (i = 0; i < rows; i += 1)
		{
			tokenize(bufstr_get(tour_players, tour_hrow[i]));
			name = Tour_Text(argv(2), 28);
			tm = (stof(argv(6)) > 0 && stof(argv(7)) > 0) ? Time_TickString(stof(argv(6)), 1 / stof(argv(7))) : "no time";
			colour = '1 1 1';
			if (argv(3) == "eliminated") { colour = '0.55 0.57 0.62'; tm = "out"; }
			else if (tour_phase == "live" && risk >= 0 && (dnf ? !(stof(argv(6)) > 0) : i == risk)) colour = '1 0.45 0.4';
			if (argv(3) == "player" && stof(argv(8)) == 1) { colour = '0.45 1 0.55'; tm = "WINNER"; }
			if (!strcmp(argv(1), tour_me)) name = strcat(name, " (you)");
			HUD_Text([at_x + pad, at_y + pad * 0.5 + i * rh, 0], strcat(ftos(i + 1), "  ", name), sz2, colour, 1);
			HUD_TextR([at_x + w - pad, at_y + pad * 0.5 + i * rh, 0], tm, sz2, colour, 1);
		}
	}

	// Centre: the countdown digits, then the phase's announcement.
	big = 44 * ui_cv_scale;
	Font_Set(ui_font_display);
	if (tour_phase == "countdown" && remaining > 0)
		HUD_TextC([scr_x * 0.5, scr_y * 0.34, 0], ftos(ceil(remaining)), big * 1.3, '0.45 0.85 1', 0.95);
	else if (tour_evt != "" && cltime - tour_evtat < tour_evtfor)
	{
		HUD_TextC([scr_x * 0.5, scr_y * 0.34, 0], tour_evt, big, tour_evtcolour, 0.95);
		if (tour_evtsub != "")
		{
			Font_Set(ui_font_ui);
			HUD_TextC([scr_x * 0.5, scr_y * 0.34 + Font_Px(big) + 6 * ui_cv_scale, 0], tour_evtsub, 10 * ui_cv_scale, '1 1 1', 0.9);
		}
	}
	Font_Reset();
};
