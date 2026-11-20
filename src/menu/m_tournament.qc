// Main-menu tournament waiting rooms. NO game connection/reservation before host Start.
// Proofs stay in this VM's transient memory and go only to the fixed service.
// Room layout (AoE2/Worms style): seat slots on the left, the host's live settings on
// the right (the draft and the schedule take that panel later), one action bar below.
#define MT_SITE "https://play.proto.bar"
#define MT_JSON_ARRAY 3 // engine/common/common.h json_type_array
#define MT_JSON_NUMBER 1 // required numeric metadata must not default missing fields to zero
#define MT_DIR_FIELDS 7
#define MT_PLAYER_FIELDS 10 // who name role accepted ready best eliminated menu_ready online seat
#define MT_MAP_FIELDS 9 // name status by page cell tier by-seat by-name style
#define MT_CAT_FIELDS 5 // name tier provenance page cell
#define MT_SCHED_MAX 8
#define MT_SOLID '0.098 0.106 0.145' // PANEL-like but not a theme token, so glass leaves it opaque
#define MT_SPEC_MAX 72
string(string nonce, string op, string who) friends_sign;
float mt_req, mt_wire, mt_phase_wire, mt_sent, mt_next, mt_dirreq, mt_dirwire, mt_dirnext, mt_enabled, mt_dirloaded;
var float mt_dirrows = 6, mt_maprows = 6, mt_rosterrows = 8;
float mt_engaged, mt_ok;
var float mt_newseats = 4, mt_newseconds = 300;
float mt_revision, mt_capacity, mt_seconds, mt_np, mt_nm, mt_nd, mt_fresh, mt_started;
float mt_rosterpage, mt_mappage, mt_dirpage, mt_view;
string mt_payload, mt_hash, mt_op, mt_note, mt_id, mt_host, mt_me, mt_phase, mt_name;
string mt_turnkind, mt_turnwho, mt_turnname, mt_reserve, mt_launched, mt_launchmap;
float mt_players, mt_maps, mt_directory, mt_notetime, mt_noteerr, mt_turnseat, mt_seated, mt_nspec;
float mt_nsched, mt_reserveidx, mt_sched[MT_SCHED_MAX], mt_seatof[8], mt_specof[MT_SPEC_MAX];
// Pending edits are independent of the last authoritative snapshot.
string mt_kind, mt_profile, mt_pool, mt_editpool, mt_actualkind, mt_actualprofile, mt_actualpool, mt_ruleset;
float mt_tiers, mt_actualtiers, mt_actualtick, mt_settingsinit, mt_metadata;
float mt_catalog, mt_catalogcount, mt_catalogtotal, mt_unqualified, mt_catalogoffset;
var float mt_cataloglimit = 6;
float mt_catalogfresh, mt_catalognext, mt_catalogmin, mt_cataloghosting;
string mt_catalogkey, mt_querykey, mt_catalogmsg;
// Host edits apply themselves after a short pause (configure resets every seat, so
// not per click). Clicks made while the one wire is busy wait in a short FIFO
// instead of being dropped; a stale-revision refusal re-sends the click once after
// a fresh snapshot (not Lock: the host should see the changed roster first).
#define MT_QMAX 4
#define MT_QF 8 // strings per queued click: op id target map value expected retried text
float mt_dirty, mt_editgen, mt_sentgen, mt_applyat, mt_cfgretry, mt_modal, mt_autoaccept, mt_confirm, mt_kickat, mt_holdat;
string mt_kickwho; // host's Kick needs a second click within 3 s: a kicked player cannot rejoin that room
float mt_queue, mt_qn, mt_qstale;
string mt_fid, mt_ftarget, mt_fmap, mt_ftext, mt_rejoin;
float mt_fvalue, mt_fexpected, mt_fretried, mt_userop;
// Room chat: the last 40 lines from the party snapshot, wrapped once per change/width.
#define MT_CHAT_FIELDS 4 // who name text seat
float mt_chat, mt_nchat, mt_chatgen, mt_chatlines, mt_chatnl, mt_chatwrapgen, mt_chatwrapw, mt_chatseen, mt_chatat;
string mt_chatsig; // mt_chatdraft is declared in m_main.qc (console command)
float mt_chatcursor;
// The TOURNAMENT tab shows only where the service has tournaments switched on
// (or ui_tournaments 1): a quiet public GET, re-asked every 5 minutes.
float mt_probeat;
// mt_launchaddr: the launched server while the backend still hands it out (Rejoin/Watch).
// mt_watch: room id of a browser Watch click, so its refusal reads as one.
string mt_launchaddr, mt_watch;
float mt_needlink, mt_ingame;
// P1650's draft clock: turn_left seconds as of mt_turnat, counted down between polls; -1 = not sent.
var float mt_turnleft = -1;
float mt_turnat;
#define MT_RULE "Each round, anyone who doesn't finish (or the slowest finisher) is out. Last one standing wins."

string(float i) MT_ProfileID =
{
	if (i == 1) return "hl2-pre";
	if (i == 2) return "hl2-post";
	if (i == 3) return "ag-100";
	if (i == 4) return "ag-250";
	if (i == 5) return "ag-1000";
	if (i == 6) return "cs16";
	return "default";
};
float(string id) MT_ProfileIndex =
{
	local float i;
	for (i = 0; i < 7; i += 1) if (!strcmp(id, MT_ProfileID(i))) return i;
	return -1;
};
// Default keeps each map kind's own tick: surf 66.7 Hz, bhop 100 Hz (P1639; tournament_rules.tick_for).
float(string id, string kind) MT_ProfileTick =
{
	if (id == "ag-1000") return 1000;
	if (id == "ag-250") return 4000;
	if (id == "ag-100" || id == "cs16") return 10000;
	if (id == "default" && kind == "bhop") return 10000;
	return 15000;
};
string(string id) MT_ProfileName =
{
	if (id == "hl2-pre") return "HL2 pre";
	if (id == "hl2-post") return "HL2 post";
	if (id == "ag-100") return "AG 100";
	if (id == "ag-250") return "AG 250";
	if (id == "ag-1000") return "AG 1000";
	if (id == "cs16") return "CS 1.6";
	return "Default";
};
string(string id, string kind) MT_ProfileLabel =
{
	local float tick;
	tick = MT_ProfileTick(id, kind);
	return sprintf("%s, %s tick", MT_ProfileName(id), (tick == 15000) ? "66" : ftos(1000000 / tick));
};
string(string kind) MT_KindLabel = { return (kind == "bhop") ? "Bhop" : "Surf"; };
string(float seconds) MT_Minutes = { return sprintf("%g min", seconds / 60); };

// Fitting is repeated only when a visible label/font/width changes, not each frame.
#define MT_FIT_MAX 192
float mt_fit_cache, mt_fit_used;
float mt_fit_width[MT_FIT_MAX], mt_fit_font[MT_FIT_MAX], mt_fit_gen[MT_FIT_MAX], mt_fit_kerning[MT_FIT_MAX];
vector mt_fit_size[MT_FIT_MAX];

void(string a, __inout string value) MT_Set =
{
	if (value != "") strunzone(value);
	value = (a == "") ? "" : strzone(a);
};
void(string text) MT_Note = { MT_Set(text, mt_note); mt_notetime = time; mt_noteerr = FALSE; };

void() MT_SettingsInit =
{
	if (mt_settingsinit) return;
	mt_settingsinit = TRUE; mt_tiers = 7;
	MT_Set("surf", mt_kind); MT_Set("default", mt_profile); MT_Set("-", mt_pool);
};
string() MT_CatalogKey =
{
	return sprintf("kind=%s&tiers=%.0f&profile=%s&offset=%.0f&limit=%.0f",
		mt_kind, mt_tiers, mt_profile, mt_catalogoffset, mt_cataloglimit);
};
void() MT_FilterChanged =
{
	// A hand-picked list never carries over to another kind/tier/movement.
	if (mt_pool != "-") { MT_Set("-", mt_pool); MT_Note("Filters changed, so the map pool went back to Auto."); }
	mt_catalogoffset = 0;
};
float(string pool, string name) MT_InPool =
{
	if (pool == "-") return TRUE;
	return strstrofs(strcat(",", pool, ","), strcat(",", name, ","), 0) >= 0;
};
float(string pool) MT_PoolCount =
{
	local float i, count;
	if (pool == "-" || pool == "_") return 0;
	count = 1;
	for (i = 0; i < strlen(pool); i += 1) if (str2chr(pool, i) == ',') count += 1;
	return count;
};
void(string name) MT_ToggleMap =
{
	local float i, start;
	local string out, part;
	if (mt_editpool == "-") return;
	if (!MT_InPool(mt_editpool, name))
	{
		if (MT_PoolCount(mt_editpool) >= 24) { MT_Note("A manual pool holds at most 24 maps."); return; }
		MT_Set((mt_editpool == "_") ? name : strcat(mt_editpool, ",", name), mt_editpool); return;
	}
	out = ""; start = 0;
	for (i = 0; i <= strlen(mt_editpool); i += 1)
		if (i == strlen(mt_editpool) || str2chr(mt_editpool, i) == ',')
		{
			part = substring(mt_editpool, start, i - start); start = i + 1;
			if (strcmp(part, name)) out = strcat(out, (out == "") ? "" : ",", part);
		}
	MT_Set((out == "") ? "_" : out, mt_editpool);
};

// Runs of tiers read as ranges: "T1-T3, T5, unrated". Ten tiers exist (bit 20 = unrated).
#define MT_TIERS 10
#define MT_TIER_ALL 1049599 // T1-T10 + unrated
string(float mask) MT_TierLabel =
{
	local float i, start;
	local string text;
	text = ""; start = -1;
	for (i = 0; i <= MT_TIERS; i += 1)
	{
		if (i < MT_TIERS)
		if (mask & pow(2, i))
		{
			if (start < 0) start = i;
			continue;
		}
		if (start >= 0)
		{
			if (text != "") text = strcat(text, ", ");
			text = strcat(text, (i - 1 == start) ? sprintf("T%g", start + 1) : sprintf("T%g-T%g", start + 1, i));
			start = -1;
		}
	}
	if (mask & 1048576) text = strcat(text, (text == "") ? "" : ", ", "unrated");
	return text;
};

float(string s, float n) MT_Hex =
{
	local float i, c;
	if (strlen(s) != n) return FALSE;
	for (i = 0; i < n; i += 1)
	{
		c = str2chr(s, i);
		if (c >= '0' && c <= '9') continue;
		if (c >= 'a' && c <= 'f') continue;
		return FALSE;
	}
	return TRUE;
};

float(string s) MT_Who = { return MT_Hex(s, 8) || MT_Hex(s, 12); };

string(string s, float limit) MT_Text =
{
	local string out;
	local float i, c, n;
	out = "";
	n = min(strlen(s), limit);
	// A byte limit must not leave half a UTF-8 character in a player's name.
	if (n < strlen(s))
		while (n > 0 && (str2chr(s, n) & 192) == 128) n -= 1;
	for (i = 0; i < n; i += 1)
	{
		c = str2chr(s, i);
		if (c >= 32 && c != 127 && c != '"' && c != ';' && c != '\\') out = strcat(out, chr2str(c));
	}
	return UI_NameShow(out, 0);
};

// Chat keeps quotes and punctuation (it is only ever drawn), drops control bytes, caps bytes.
string(string s) MT_ChatText =
{
	local string out;
	local float i, c, n, clean;
	n = min(strlen(s), 400);
	if (n < strlen(s))
		while (n > 0 && (str2chr(s, n) & 192) == 128) n -= 1;
	clean = TRUE;
	for (i = 0; i < n; i += 1) { c = str2chr(s, i); if (c < 32 || c == 127) clean = FALSE; }
	out = substring(s, 0, n);
	if (!clean)
	{
		out = "";
		for (i = 0; i < n; i += 1) { c = str2chr(s, i); if (c >= 32 && c != 127) out = strcat(out, chr2str(c)); }
	}
	return UI_NameShow(out, 0);
};

float(string s) MT_MapNameOK =
{
	local float i, c;
	if (strlen(s) < 1 || strlen(s) > 64) return FALSE;
	c = str2chr(s, 0);
	if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9'))) return FALSE;
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

float(string map, float empty) MT_MapAllowed =
{
	if (map == "") return empty;
	// Missing local maps follow the normal guarded game download path.
	// Qualification is backend-owned; this guard rejects command/path injection.
	return MT_MapNameOK(map);
};

string(float i, float field) MT_Player = { return bufstr_get(mt_players, i * MT_PLAYER_FIELDS + field); };
string(float i, float field) MT_Map = { return bufstr_get(mt_maps, i * MT_MAP_FIELDS + field); };
string(float i, float field) MT_Dir = { return bufstr_get(mt_directory, i * MT_DIR_FIELDS + field); };
string(float i, float field) MT_Cat = { return bufstr_get(mt_catalog, i * MT_CAT_FIELDS + field); };

float() MT_MeIndex =
{
	local float i;
	for (i = 0; i < mt_np; i += 1) if (MT_Player(i, 0) == mt_me) return i;
	return -1;
};

void() MT_ClampPages =
{
	mt_dirpage = bound(0, mt_dirpage, max(0, ceil(mt_nd / max(1, mt_dirrows)) - 1));
	mt_rosterpage = bound(0, mt_rosterpage, max(0, ceil((mt_capacity + 1 + max(1, mt_nspec)) / max(1, mt_rosterrows)) - 1));
	mt_mappage = bound(0, mt_mappage, max(0, ceil(mt_nm / max(1, mt_maprows)) - 1));
};
void() MT_ClearQueue = { mt_qn = 0; };
float(string op, string target) MT_Queued =
{
	local float i;
	for (i = 0; i < mt_qn; i += 1)
		if (bufstr_get(mt_queue, i * MT_QF) == op)
		if ((op != "seat" && op != "kick") || bufstr_get(mt_queue, i * MT_QF + 2) == target) return TRUE;
	return FALSE;
};
void(string op, string id, string target, string map, float value, float expected, float retried, float front, string text) MT_Enqueue =
{
	local float i, f, slot;
	if (!mt_queue) mt_queue = buf_create();
	if (mt_qn >= MT_QMAX) { MT_Note("Too many clicks at once; wait a moment and try again."); return; }
	slot = mt_qn;
	if (front)
	{
		for (i = mt_qn; i > 0; i -= 1)
			for (f = 0; f < MT_QF; f += 1) bufstr_set(mt_queue, i * MT_QF + f, bufstr_get(mt_queue, (i - 1) * MT_QF + f));
		slot = 0;
	}
	bufstr_set(mt_queue, slot * MT_QF, op); bufstr_set(mt_queue, slot * MT_QF + 1, id);
	bufstr_set(mt_queue, slot * MT_QF + 2, target); bufstr_set(mt_queue, slot * MT_QF + 3, map);
	bufstr_set(mt_queue, slot * MT_QF + 4, ftos(value)); bufstr_set(mt_queue, slot * MT_QF + 5, ftos(expected));
	bufstr_set(mt_queue, slot * MT_QF + 6, ftos(retried)); bufstr_set(mt_queue, slot * MT_QF + 7, text);
	mt_qn += 1;
};
void() MT_Dequeue =
{
	local float i, f;
	for (i = 1; i < mt_qn; i += 1)
		for (f = 0; f < MT_QF; f += 1) bufstr_set(mt_queue, (i - 1) * MT_QF + f, bufstr_get(mt_queue, i * MT_QF + f));
	mt_qn = max(0, mt_qn - 1);
};
// A room you only joined does not hand its rules to the next room you host.
void() MT_ResetSettings =
{
	mt_tiers = 7; mt_newseats = 4; mt_newseconds = 300;
	MT_Set("surf", mt_kind); MT_Set("default", mt_profile); MT_Set("-", mt_pool);
};
void() MT_SyncPending =
{
	if (mt_actualkind == "") return;
	MT_Set(mt_actualkind, mt_kind); MT_Set(mt_actualprofile, mt_profile); MT_Set(mt_actualpool, mt_pool);
	mt_tiers = mt_actualtiers; mt_newseats = mt_capacity; mt_newseconds = mt_seconds;
};
float() MT_PendingDiffers =
{
	return (strcmp(mt_kind, mt_actualkind) || strcmp(mt_profile, mt_actualprofile) || strcmp(mt_pool, mt_actualpool)
		|| mt_tiers != mt_actualtiers || mt_newseats != mt_capacity || mt_newseconds != mt_seconds);
};
float(string op) MT_Busy = { return (mt_req && mt_op == op) || MT_Queued(op, ""); };
void() MT_Edit =
{
	if (mt_id == "" || mt_me != mt_host || mt_phase != "lobby" || MT_Busy("lock")) return;
	mt_dirty = TRUE; mt_editgen += 1; mt_applyat = time + 0.6;
};
void(float k) MT_ToggleTier =
{
	local float bit;
	bit = pow(2, k);
	if (mt_tiers == bit) { MT_Note("Keep at least one tier selected."); return; }
	mt_tiers = mt_tiers ^ bit;
	MT_FilterChanged(); MT_Edit();
};
void() MT_ClearParty =
{
	if (mt_id != "" && mt_me != mt_host) MT_ResetSettings();
	MT_Set("", mt_id); MT_Set("", mt_host); MT_Set("", mt_phase); MT_Set("", mt_name);
	MT_Set("", mt_turnkind); MT_Set("", mt_turnwho); MT_Set("", mt_turnname); MT_Set("", mt_reserve);
	MT_Set("", mt_launchaddr);
	if (mt_players) buf_del(mt_players);
	if (mt_maps) buf_del(mt_maps);
	mt_players = mt_maps = mt_np = mt_nm = mt_revision = mt_fresh = mt_started = 0;
	mt_rosterpage = mt_mappage = mt_view = mt_nsched = mt_seated = mt_nspec = 0;
	mt_dirty = mt_modal = mt_confirm = mt_autoaccept = mt_cfgretry = 0; mt_reserveidx = -1;
	if (mt_chat) buf_del(mt_chat);
	mt_chat = mt_nchat = mt_chatat = 0; mt_chatgen += 1; MT_Set("", mt_chatsig);
	// Without a room nothing needs the 2 s presence poll off this screen.
	mt_engaged = FALSE;
	MT_ClearQueue();
};

// Backend refusals in the words a player needs; raw = the text came from surfd,
// and anything unmapped is shown as the server's own words.
string(string note, float raw = FALSE) MT_Friendly =
{
	if (strstrofs(note, "stale revision", 0) >= 0) return "The room changed; refreshing.";
	if (strstrofs(note, "every competitor must accept", 0) >= 0) return "Every seated player has to accept first.";
	if (strstrofs(note, "qualified maps", 0) >= 0) return "Not enough qualified maps for this many players.";
	if (strstrofs(note, "no enabled empty fresh node", 0) >= 0)
		return "All tournament servers are busy, or someone is playing on them. Try again in a minute.";
	if (strstrofs(note, "online and ready", 0) >= 0) return "Everyone seated has to be online and ready.";
	if (strstrofs(note, "party closed or already joined", 0) >= 0) return "That room has closed or already started.";
	if (strstrofs(note, "linked account required", 0) >= 0) return "Link your Steam account to play tournaments.";
	if (strstrofs(note, "hosting unavailable", 0) >= 0) return "Tournament hosting is unavailable right now.";
	if (strstrofs(note, "capacity below roster", 0) >= 0) return "Move a player to spectators before removing their seat.";
	if (strstrofs(note, "seats full", 0) >= 0) return "Every seat is taken. Add a seat first.";
	if (strstrofs(note, "proof unavailable", 0) >= 0 || strstrofs(note, "try again shortly", 0) >= 0
		|| strstrofs(note, "storage unavailable", 0) >= 0)
		return "The tournament service is busy; try again in a moment.";
	if (strstrofs(note, "removed from this room", 0) >= 0) return "The host removed you from that room.";
	if (strstrofs(note, "chat is closed", 0) >= 0) return "Chat closes once the tournament starts.";
	if (strstrofs(note, "bad text", 0) >= 0) return "That message could not be sent.";
	if (strstrofs(note, "already in a party", 0) >= 0) { mt_next = 0; return "You are already in a room; reopening it."; }
	if (strstrofs(note, "spectator roster full", 0) >= 0 || strstrofs(note, "account history full", 0) >= 0) return "This room is full.";
	if (strstrofs(note, "proof expired", 0) >= 0 || strstrofs(note, "invalid signature", 0) >= 0 || strstrofs(note, "proof replay", 0) >= 0)
		return "Your connection check expired. Click again.";
	if (strstrofs(note, "not your draft turn", 0) >= 0) return "It's not your turn yet.";
	if (strstrofs(note, "map is not available", 0) >= 0) return "That map was just taken. Pick another.";
	if (strstrofs(note, "drafted qualification changed", 0) >= 0)
		return "A drafted map changed on the server. The host should close the room and start again.";
	if (strstrofs(note, "selected map", 0) >= 0 || strstrofs(note, "manual pool mismatch", 0) >= 0)
		return "A map in the pool is no longer available. Edit the map pool.";
	if (strstrofs(note, "catalogue unavailable", 0) >= 0 || strstrofs(note, "registry", 0) >= 0)
		return "The map list is unavailable right now; it retries by itself.";
	if (strstrofs(note, "party not found", 0) >= 0 || strstrofs(note, "match is closed", 0) >= 0) return "That room has closed.";
	if (strstrofs(note, "not a current member", 0) >= 0) return "You are no longer in that room.";
	if (strstrofs(note, "tournaments disabled", 0) >= 0) return "Tournaments are switched off on the server right now.";
	// After launch surfd takes only leave (party_lobbies.py); a host Close lands here.
	if (strstrofs(note, "already started", 0) >= 0 || strstrofs(note, "after first GO", 0) >= 0)
		return "The tournament is already running on its server; the room can't be closed or changed now.";
	// Neutral: P1650's host may unseat or kick in the draft and ready check, today's only in the lobby.
	if (strstrofs(note, "waiting room only", 0) >= 0 || strstrofs(note, "roster frozen", 0) >= 0) return "You can't change seats right now.";
	if (strstrofs(note, "settings frozen", 0) >= 0) return "Settings are locked once the draft starts.";
	if (strstrofs(note, "need at least two", 0) >= 0) return "The draft needs at least two seated players.";
	if (strstrofs(note, "Pre-Beta tournament", 0) >= 0) return "This room is from an older version. Close it and host a new one.";
	if (!strcmp(note, "host only")) return "Only the host can do that.";
	if (raw && note != "") return strcat("Server says: ", note);
	return note;
};

void(string note, float raw = FALSE) MT_Fail =
{
	local float stale, busy;
	stale = (strstrofs(note, "stale revision", 0) >= 0);
	// surfd's shared signature budget or a rate limit: back off with jitter, keep the controls.
	busy = (strstrofs(note, "proof unavailable", 0) >= 0 || strstrofs(note, "try again shortly", 0) >= 0);
	mt_req = mt_phase_wire = 0;
	// Refused/invalid replies cannot keep the previous controls "fresh". In
	// particular, repeated stale-revision clicks must not postpone resync.
	if (!busy) mt_fresh = 0;
	mt_next = time + (busy ? 3 + random() * 3 : 4);
	if (busy) { mt_holdat = mt_next; if (mt_op == "state") note = ""; }
	// Unlinked: the browser's Link banner says it once instead of a toast every poll.
	if (strstrofs(note, "linked account required", 0) >= 0) { mt_needlink = TRUE; if (mt_op == "state") note = ""; }
	// A poll whose proof aged out just polls again; only a click is told to retry.
	if (mt_op == "state" && strstrofs(note, "proof expired", 0) >= 0) note = "";
	// A busy resync keeps the queued clicks: they wait out the hold with the poll.
	if (mt_op == "state" && mt_qstale && !busy) { mt_qstale = FALSE; MT_ClearQueue(); }
	if (mt_op == "configure")
	{
		// Host intent survives a roster change or a busy service; any other refusal reverts the panel.
		if (busy) { mt_applyat = mt_holdat; note = ""; }
		else if (stale && mt_cfgretry < 3) { mt_cfgretry += 1; mt_qstale = TRUE; mt_next = 0; note = ""; }
		else { mt_dirty = FALSE; mt_cfgretry = 0; MT_SyncPending(); }
	}
	else if (busy && !mt_fretried && mt_op != "" && mt_op != "state")
	{
		// Refused only for load: the same click goes again once, after the hold.
		MT_Enqueue(mt_op, mt_fid, mt_ftarget, mt_fmap, mt_fvalue, mt_fexpected, TRUE, TRUE, mt_ftext);
		note = "";
	}
	else if (stale && !mt_fretried && mt_op == "join")
	{
		// The directory's revision was old: rejoin from a fresh listing (MT_Reply).
		MT_Set(mt_fid, mt_rejoin); mt_dirnext = 0; note = "";
	}
	else if (stale && mt_op == "lock")
	{
		mt_next = 0; note = "The room changed. Check the seats, then start the draft again."; raw = FALSE;
	}
	else if (stale && !mt_fretried && mt_op != "" && mt_op != "state" && mt_op != "create")
	{
		MT_Enqueue(mt_op, mt_fid, mt_ftarget, mt_fmap, mt_fvalue, mt_fexpected, TRUE, TRUE, mt_ftext);
		mt_qstale = TRUE; mt_next = 0; note = "";
	}
	else if (mt_op == "create" && strstrofs(note, "selected map", 0) >= 0)
	{
		MT_Set("-", mt_pool);
		note = "A map in your saved pool no longer qualifies, so the pool is back to Auto. Host again."; raw = FALSE;
	}
	if (note != "")
	{
		// Today's surfd admits joins only before the draft; a Watch refusal says so plainly.
		if (mt_op == "join" && mt_watch != "" && strstrofs(note, "party closed or already joined", 0) >= 0)
			note = "This tournament has already started and can't be watched from here.";
		else note = MT_Friendly(note, raw);
		MT_Note(note); mt_noteerr = TRUE;
	}
	MT_Set("", mt_payload); MT_Set("", mt_hash); MT_Set("", mt_op);
};

void(string op, string id, string target, string map, float value, float expected, float retried, string text) MT_Send =
{
	local string request, payload, hash;
	local float revision;
	MT_SettingsInit();
	if (mt_req || mt_wire) return;
	revision = (expected >= 0) ? expected : mt_revision;
	if (ms_consent < FS_TERMS_ONLINE) { MT_Note("Read the online terms first."); return; }
	if (clientstate() != 1) { MT_Note("Leave your current game to use tournament rooms."); return; }
	if (id == "") id = "-";
	if (target == "") target = "-";
	if (map == "") map = "-";
	if (text == "") text = "-";
	// A request ID is an idempotency label, NOT a credential. The server nonce
	// and native Ed25519 signature provide freshness/authenticity independently.
	request = substring(digest_hex("SHA256", sprintf("%s|%g|%g|%g|%g", op, gettime(1), time, random(), Lob_NextReq())), 0, 32);
	payload = strcat("op=", op, "&id=", id, "&revision=", ftos(revision));
	payload = strcat(payload, "&request=", request, "&capacity=", ftos(mt_newseats));
	payload = strcat(payload, "&round_seconds=", ftos(mt_newseconds), "&target=", target);
	// String comparisons can return a non-unit truth value. The wire protocol
	// deliberately accepts only canonical 0/1, not an arbitrary truthy number.
	payload = strcat(payload, "&map=", map, "&value=", value ? "1" : "0");
	payload = strcat(payload, "&kind=", uri_escape(mt_kind), "&tiers=", sprintf("%.0f", mt_tiers));
	payload = strcat(payload, "&profile=", uri_escape(mt_profile), "&pool=", uri_escape(mt_pool));
	payload = strcat(payload, "&text=", uri_escape(text));
	if (strlen(payload) > 2048) { MT_Note("That request is too long to send."); return; }
	hash = digest_hex("SHA256", payload);
	if (!MT_Hex(hash, 64)) { MT_Fail("Update the game to use tournament rooms."); return; }
	MT_Set(payload, mt_payload); MT_Set(hash, mt_hash); MT_Set(op, mt_op);
	MT_Set(id, mt_fid); MT_Set(target, mt_ftarget); MT_Set(map, mt_fmap); MT_Set(text, mt_ftext);
	mt_fvalue = value; mt_fexpected = expected; mt_fretried = retried; mt_userop = (op != "state");
	mt_req = Lob_NextReq(); mt_wire = mt_req; mt_phase_wire = 1; mt_sent = time; mt_engaged = TRUE;
	if (!uri_get(strcat(MT_SITE, "/api/tournament-lobbies/challenge?hash=", hash), mt_req))
	{
		mt_wire = 0;
		MT_Fail("Can't reach the tournament service. Try again in a moment.");
	}
};


// A click is never dropped because a poll holds the wire, and a repeat of the
// same action already waiting or in flight is not a second request.
void(string op, string id, string target, string map, float value, float expected, float retried, string text = "") MT_Request =
{
	if (op == "seat" || op == "kick")
	{
		if (MT_Queued(op, target)) return;
		if (mt_req && mt_op == op && mt_ftarget == target) return;
	}
	else if (MT_Busy(op)) return;
	if (mt_req || mt_wire || mt_qstale || mt_qn) { MT_Enqueue(op, id, target, map, value, expected, retried, FALSE, text); return; }
	MT_Send(op, id, target, map, value, expected, retried, text);
};
void(string op, string id, string target, string map, float value, float expected = -1) MT_Action =
{
	MT_Request(op, id, target, map, value, expected, FALSE);
};

void() MT_Directory =
{
	if (mt_dirwire || mt_dirreq || time < mt_dirnext || ms_consent < FS_TERMS_ONLINE) return;
	mt_dirreq = Lob_NextReq(); mt_dirwire = mt_dirreq; mt_dirnext = time + 10;
	if (!uri_get(strcat(MT_SITE, "/api/tournament-lobbies?brief=1"), mt_dirreq)) mt_dirwire = mt_dirreq = 0;
};

float(int party) MT_Snapshot =
{
	local int players, maps, item, settings, pool, sched, chat;
	local float np, nm, i, j, pb, mb, good, hostfound, mefound, row, page, cell, seat, byseat;
	local string id, host, phase, who, role, name, status, kind, profile, selected, ruleset, by, byname, style;
	local float tiers, tick, count, revision, capacity, seconds, tier, cb, n, at;
	local string text;
	id = json_get_string(json_find_object_child(party, "id"));
	if (id == "")
	{
		if (mt_id != "" && mt_op == "state") MT_Note("The room closed, or the host removed you from it.");
		MT_ClearParty(); return TRUE;
	}
	host = json_get_string(json_find_object_child(party, "host"));
	phase = json_get_string(json_find_object_child(party, "phase"));
	if (!MT_Hex(id, 32) || !MT_Who(host)) return FALSE;
	if (phase != "lobby" && phase != "draft" && phase != "loading" && phase != "starting" && phase != "in-game" && phase != "finished" && phase != "cancelled" && phase != "aborted") return FALSE;
	revision = json_get_float(json_find_object_child(party, "revision"));
	capacity = json_get_float(json_find_object_child(party, "capacity"));
	seconds = json_get_float(json_find_object_child(party, "round_seconds"));
	if (revision < 1 || revision != floor(revision) || capacity < 2 || capacity > 8 || capacity != floor(capacity) || seconds < 60 || seconds > 900 || seconds != floor(seconds)) return FALSE;
	settings = json_find_object_child(party, "settings");
	kind = json_get_string(json_find_object_child(settings, "kind"));
	profile = json_get_string(json_find_object_child(settings, "profile"));
	tiers = json_get_float(json_find_object_child(settings, "tiers"));
	tick = json_get_float(json_find_object_child(settings, "tick_us"));
	ruleset = json_get_string(json_find_object_child(party, "ruleset_id"));
	if ((kind != "surf" && kind != "bhop") || MT_ProfileIndex(profile) < 0 || tiers < 1 || tiers > 2097151 || tiers != floor(tiers) || tick != MT_ProfileTick(profile, kind)) return FALSE;
	if ((phase == "draft" || phase == "loading" || phase == "starting" || phase == "in-game") && !MT_Hex(ruleset, 64)) return FALSE;
	if (ruleset != "" && !MT_Hex(ruleset, 64)) return FALSE;
	pool = json_find_object_child(settings, "pool"); selected = "-";
	// json_type_null = 6; absent fields are not Auto.
	if (json_get_value_type(pool) == MT_JSON_ARRAY)
	{
		count = json_get_length(pool); if (count > 24) return FALSE;
		selected = "";
		for (j = 0; j < count; j += 1)
		{
			name = json_get_string(json_get_child_at_index(pool, j));
			if (!MT_MapNameOK(name)) return FALSE;
			if (strstrofs(strcat(",", selected, ","), strcat(",", name, ","), 0) >= 0) return FALSE;
			selected = strcat(selected, j ? "," : "", name);
		}
		if (!count) selected = "_";
	}
	else if (!pool || json_get_value_type(pool) != 6) return FALSE;
	players = json_find_object_child(party, "players"); maps = json_find_object_child(party, "maps");
	if (json_get_value_type(players) != MT_JSON_ARRAY || json_get_value_type(maps) != MT_JSON_ARRAY) return FALSE;
	np = json_get_length(players); nm = json_get_length(maps);
	if (np < 1 || np > 72 || nm < 0 || nm > 24) return FALSE;
	pb = buf_create(); mb = buf_create(); good = TRUE; hostfound = mefound = FALSE; seat = 0;
	for (i = 0; i < np; i += 1)
	{
		item = json_get_child_at_index(players, i);
		who = json_get_string(json_find_object_child(item, "who"));
		role = json_get_string(json_find_object_child(item, "role"));
		if (!MT_Who(who) || (role != "player" && role != "spectator")) { good = FALSE; break; }
		if (who == host) hostfound = TRUE;
		if (who == mt_me) mefound = TRUE;
		bufstr_set(pb, i * MT_PLAYER_FIELDS, who);
		bufstr_set(pb, i * MT_PLAYER_FIELDS + 1, MT_Text(json_get_string(json_find_object_child(item, "name")), 64));
		bufstr_set(pb, i * MT_PLAYER_FIELDS + 2, role);
		bufstr_set(pb, i * MT_PLAYER_FIELDS + 3, ftos(json_get_float(json_find_object_child(item, "accepted"))));
		bufstr_set(pb, i * MT_PLAYER_FIELDS + 4, ftos(json_get_float(json_find_object_child(item, "ready"))));
		bufstr_set(pb, i * MT_PLAYER_FIELDS + 5, ftos(json_get_float(json_find_object_child(item, "best_ms"))));
		bufstr_set(pb, i * MT_PLAYER_FIELDS + 6, ftos(json_get_float(json_find_object_child(item, "eliminated"))));
		bufstr_set(pb, i * MT_PLAYER_FIELDS + 7, ftos(json_get_float(json_find_object_child(item, "menu_ready"))));
		bufstr_set(pb, i * MT_PLAYER_FIELDS + 8, ftos(json_get_float(json_find_object_child(item, "menu_online"))));
		// Seat number = order among competitors; it picks the slot and its colour.
		if (role == "player")
		{
			if (seat >= 8) { good = FALSE; break; }
			bufstr_set(pb, i * MT_PLAYER_FIELDS + 9, ftos(seat)); seat += 1;
		}
		else bufstr_set(pb, i * MT_PLAYER_FIELDS + 9, "-1");
	}
	for (i = 0; good && i < nm; i += 1)
	{
		item = json_get_child_at_index(maps, i);
		name = json_get_string(json_find_object_child(item, "name")); status = json_get_string(json_find_object_child(item, "status"));
		if (!MT_MapNameOK(name) || (status != "pool" && status != "banned" && status != "picked" && status != "reserve")) { good = FALSE; break; }
		by = MT_Text(json_get_string(json_find_object_child(item, "by")), 12);
		bufstr_set(mb, i * MT_MAP_FIELDS, name);
		bufstr_set(mb, i * MT_MAP_FIELDS + 1, status);
		bufstr_set(mb, i * MT_MAP_FIELDS + 2, by);
		// Resolve metadata on state adoption, never scan the map list in Draw.
		row = ui_map_index(name); page = cell = -1; style = "";
		if (row >= 0)
		if (tokenize(bufstr_get(ms_meta, row)) > MT_UUID)
		{
			if (argv(MT_PAGE) != "-") page = stof(argv(MT_PAGE));
			if (argv(MT_CELL) != "-") cell = stof(argv(MT_CELL));
			if (stof(argv(MT_STAGES)) > 0) style = sprintf("%g stages", stof(argv(MT_STAGES)));
			else if (argv(MT_LINEAR) == "1") style = "Linear";
		}
		bufstr_set(mb, i * MT_MAP_FIELDS + 3, ftos(page));
		bufstr_set(mb, i * MT_MAP_FIELDS + 4, ftos(cell));
		tier = json_get_float(json_find_object_child(item, "tier"));
		if (tier < 0 || tier > 20 || tier != floor(tier)) { good = FALSE; break; }
		bufstr_set(mb, i * MT_MAP_FIELDS + 5, tier ? sprintf("T%g", tier) : "Unrated");
		byseat = -1; byname = "";
		if (by != "")
			for (j = 0; j < np; j += 1)
				if (bufstr_get(pb, j * MT_PLAYER_FIELDS) == by)
				{
					byseat = stof(bufstr_get(pb, j * MT_PLAYER_FIELDS + 9));
					byname = bufstr_get(pb, j * MT_PLAYER_FIELDS + 1);
				}
		bufstr_set(mb, i * MT_MAP_FIELDS + 6, ftos(byseat));
		bufstr_set(mb, i * MT_MAP_FIELDS + 7, byname);
		bufstr_set(mb, i * MT_MAP_FIELDS + 8, style);
	}
	if (!good || !hostfound) { buf_del(pb); buf_del(mb); return FALSE; }
	// A leave/cancel reply still carries the room; a member who is gone, or a
	// closed room, is the browser again.
	if (!mefound || phase == "finished" || phase == "cancelled" || phase == "aborted")
	{
		buf_del(pb); buf_del(mb);
		if (mt_op == "state" && phase == "cancelled") MT_Note("The host closed the room.");
		MT_ClearParty(); return TRUE;
	}
	if (id != mt_id)
	{
		mt_rosterpage = mt_mappage = 0;
		mt_autoaccept = mt_confirm = mt_cfgretry = 0; mt_dirty = FALSE;
	}
	// Only P1650's surfd sends a started room back to the lobby (a leave or unseat before launch).
	if (id == mt_id && phase == "lobby" && mt_phase != "lobby" && mt_phase != "")
		MT_Note("Back to the lobby: someone left or was unseated, so the draft starts over.");
	if (id != mt_id || phase != mt_phase) mt_view = (phase == "lobby") ? 0 : 1;
	if (mt_players) buf_del(mt_players);
	if (mt_maps) buf_del(mt_maps);
	mt_players = pb; mt_maps = mb; mt_np = np; mt_nm = nm;
	MT_Set(id, mt_id); MT_Set(host, mt_host); MT_Set(phase, mt_phase);
	MT_Set(MT_Text(json_get_string(json_find_object_child(party, "name")), 64), mt_name);
	MT_Set(MT_Text(json_get_string(json_find_object_child(party, "turn_kind")), 12), mt_turnkind);
	MT_Set(MT_Text(json_get_string(json_find_object_child(party, "turn_who")), 12), mt_turnwho);
	item = json_find_object_child(party, "turn_left"); mt_turnleft = -1;
	if (item && json_get_value_type(item) == MT_JSON_NUMBER && phase == "draft")
	{
		mt_turnleft = json_get_float(item); mt_turnat = time;
		if (mt_turnleft < 0 || mt_turnleft > 3600 || mt_turnleft != floor(mt_turnleft)) mt_turnleft = -1;
	}
	MT_Set(MT_Text(json_get_string(json_find_object_child(party, "reserve")), 64), mt_reserve);
	mt_revision = revision; mt_capacity = capacity; mt_seconds = seconds;
	mt_started = (json_get_float(json_find_object_child(party, "menu_started")) == 1);
	MT_Set(kind, mt_actualkind); MT_Set(profile, mt_actualprofile); MT_Set(selected, mt_actualpool);
	MT_Set(ruleset, mt_ruleset); mt_actualtiers = tiers; mt_actualtick = tick;
	// Derived tables for Draw: seat slots, spectators, whose turn, the schedule.
	for (i = 0; i < 8; i += 1) mt_seatof[i] = -1;
	mt_seated = mt_nspec = 0; mt_turnseat = -1; byname = "";
	for (i = 0; i < np; i += 1)
	{
		seat = stof(MT_Player(i, 9));
		if (seat >= 0) { mt_seatof[seat] = i; mt_seated += 1; }
		else if (mt_nspec < MT_SPEC_MAX) { mt_specof[mt_nspec] = i; mt_nspec += 1; }
		if (MT_Player(i, 0) == mt_turnwho) { mt_turnseat = seat; byname = MT_Player(i, 1); }
	}
	MT_Set(byname, mt_turnname);
	mt_nsched = 0; mt_reserveidx = -1;
	sched = json_find_object_child(party, "schedule");
	if (json_get_value_type(sched) == MT_JSON_ARRAY)
		for (j = 0; j < min(json_get_length(sched), MT_SCHED_MAX); j += 1)
		{
			name = json_get_string(json_get_child_at_index(sched, j));
			for (i = 0; i < nm; i += 1)
				if (MT_Map(i, 0) == name) { mt_sched[mt_nsched] = i; mt_nsched += 1; break; }
		}
	for (i = 0; i < nm; i += 1) if (mt_reserve != "" && MT_Map(i, 0) == mt_reserve) mt_reserveidx = i;
	// Chat is re-read only when its length or newest sequence number moved.
	chat = json_find_object_child(party, "chat"); count = at = 0;
	if (json_get_value_type(chat) == MT_JSON_ARRAY) count = min(json_get_length(chat), 200);
	if (count > 0) at = json_get_float(json_find_object_child(json_get_child_at_index(chat, count - 1), "seq"));
	text = sprintf("%g|%g", count, at);
	if (text != mt_chatsig)
	{
		MT_Set(text, mt_chatsig);
		cb = buf_create(); n = 0;
		for (j = max(0, count - 40); j < count; j += 1)
		{
			item = json_get_child_at_index(chat, j);
			who = json_get_string(json_find_object_child(item, "who"));
			text = MT_ChatText(json_get_string(json_find_object_child(item, "text")));
			if (!MT_Who(who) || text == "") continue;
			seat = -1;
			for (i = 0; i < np; i += 1) if (MT_Player(i, 0) == who) seat = stof(MT_Player(i, 9));
			bufstr_set(cb, n * MT_CHAT_FIELDS, who);
			bufstr_set(cb, n * MT_CHAT_FIELDS + 1, MT_Text(json_get_string(json_find_object_child(item, "name")), 64));
			bufstr_set(cb, n * MT_CHAT_FIELDS + 2, text);
			bufstr_set(cb, n * MT_CHAT_FIELDS + 3, ftos(seat));
			n += 1;
		}
		if (mt_chat) buf_del(mt_chat);
		mt_chat = cb; mt_nchat = n; mt_chatgen += 1; mt_chatat = time;
	}
	mt_fresh = time;
	if (mt_op == "configure" && mt_editgen == mt_sentgen) mt_dirty = FALSE;
	if (phase != "lobby" && mt_dirty) MT_Note("The draft started before your last settings change was saved.");
	if (phase != "lobby" || host != mt_me) mt_dirty = FALSE;
	if (phase != "lobby" || (mt_modal == 2 && host != mt_me)) mt_modal = 0;
	if (!mt_dirty) MT_SyncPending();
	MT_ClampPages();
	return TRUE;
};

void(int root) MT_Launch =
{
	local int launch;
	local float i, member;
	local string id, epoch, addr, map, key;
	launch = json_find_object_child(root, "launch");
	id = json_get_string(json_find_object_child(launch, "id"));
	// No launch in the reply: nothing to rejoin (not started, ended, or no longer a member).
	if (id == "") { MT_Set("", mt_launchaddr); return; }
	epoch = json_get_string(json_find_object_child(launch, "epoch"));
	addr = json_get_string(json_find_object_child(launch, "addr"));
	map = json_get_string(json_find_object_child(launch, "map"));
	member = FALSE;
	for (i = 0; i < mt_np; i += 1) if (MT_Player(i, 0) == mt_me) member = TRUE;
	if (!member || id != mt_id || !MT_Hex(epoch, 32) || !ui_addr_ok(addr) || !ui_host_allowed(addr) || !MT_MapAllowed(map, FALSE))
	{
		MT_Set("", mt_launchaddr);
		MT_Note("The tournament started, but the server details it sent look wrong, so the game did not connect. Tell the host.");
		return;
	}
	if (clientstate() != 1) return;
	// The node is still loading the round's map; joining now could hang on its level change.
	MT_Set(map, mt_launchmap);
	if (json_get_float(json_find_object_child(launch, "ready")) != 1) { MT_Set("", mt_launchaddr); return; }
	MT_Set(addr, mt_launchaddr);
	// Auto-connect once per launch AND address: a new round or a moved node connects again,
	// a player back at the menu on the same one gets the Rejoin button instead.
	key = strcat(epoch, "@", addr);
	if (!strcmp(mt_launched, key)) return;
	MT_Set(key, mt_launched);
	MT_Note("The host started the tournament. Connecting everyone to the assigned game server...");
	// Public ID only, not a capability. SSQC still verifies the same linked key.
	cvar_set("cl_tourney_create", "0");
	localcmd(sprintf("connect %s\n", addr));
	m_close();
};

// The Rejoin / Watch on the server button: the address MT_Launch already validated.
void() MT_Rejoin =
{
	if (!ui_addr_ok(mt_launchaddr) || !ui_host_allowed(mt_launchaddr)) return;
	MT_Note("Connecting to the tournament server...");
	cvar_set("cl_tourney_create", "0");
	localcmd(sprintf("connect %s\n", mt_launchaddr));
	m_close();
};

// The catalogue feeds the lobby's qualified-map count and pool strip and the pool
// editor; public GET, no proof. One request per second at most, 10 s per failed key.
void() MT_Catalog =
{
	local string key;
	if (mt_id == "" || mt_phase != "lobby" || menu_screen != SCREEN_TOURNAMENT) return;
	if (mt_wire || mt_req || mt_qn || mt_dirty || time < mt_catalogmin) return;
	key = MT_CatalogKey();
	if (mt_catalogfresh && !strcmp(key, mt_catalogkey)) return;
	if (!strcmp(key, mt_querykey) && time < mt_catalognext) return;
	MT_Set(key, mt_querykey);
	mt_req = Lob_NextReq(); mt_wire = mt_req; mt_phase_wire = 3; mt_sent = time;
	mt_catalognext = time + 10; mt_catalogmin = time + 1; mt_userop = FALSE;
	if (!uri_get(strcat(MT_SITE, "/api/tournament-map-pool?", key), mt_req))
	{
		mt_wire = mt_req = mt_phase_wire = 0;
		MT_Set("The map list is unavailable right now; it retries by itself.", mt_catalogmsg);
	}
};
float(int root, string key, float maximum) MT_CatalogUInt =
{
	local int item;
	local float value;
	item = json_find_object_child(root, key);
	if (!item || json_get_value_type(item) != MT_JSON_NUMBER) return FALSE;
	value = json_get_float(item);
	return value >= 0 && value <= maximum && value == floor(value);
};

void(int root) MT_CatalogReply =
{
	local int rows, filters, item;
	local float i, n, db, tier, total, unqualified, good, row, page, cell, mom, ksf;
	local string name, previous, key, kind;
	key = MT_CatalogKey();
	if (strcmp(key, mt_querykey)) return;
	mt_catalogfresh = FALSE;
	if (json_get_float(json_find_object_child(root, "ok")) != 1)
	{ MT_Set(MT_Friendly(MT_Text(json_get_string(json_find_object_child(root, "error")), 180), TRUE), mt_catalogmsg); return; }
	if (json_get_float(json_find_object_child(root, "enabled")) != 1)
	{ MT_Set("Tournaments are switched off on the server right now.", mt_catalogmsg); return; }
	rows = json_find_object_child(root, "rows"); filters = json_find_object_child(root, "filters");
	if (!MT_CatalogUInt(root, "ok", 1) || !MT_CatalogUInt(root, "enabled", 1) || !MT_CatalogUInt(root, "hosting", 1)
		|| !MT_CatalogUInt(root, "total", 8192) || !MT_CatalogUInt(root, "unqualified", 1000000)
		|| !MT_CatalogUInt(root, "offset", 8192) || !MT_CatalogUInt(root, "limit", 32)
		|| !MT_CatalogUInt(root, "tick_us", 100000) || !MT_CatalogUInt(filters, "tiers", 2097151)) return;
	n = json_get_length(rows); total = json_get_float(json_find_object_child(root, "total"));
	unqualified = json_get_float(json_find_object_child(root, "unqualified"));
	if (json_get_value_type(rows) != MT_JSON_ARRAY || n != min(mt_cataloglimit, max(0, total - mt_catalogoffset))) return;
	if (strcmp(json_get_string(json_find_object_child(filters, "kind")), mt_kind) || strcmp(json_get_string(json_find_object_child(filters, "profile")), mt_profile)
		|| json_get_float(json_find_object_child(filters, "tiers")) != mt_tiers
		|| json_get_float(json_find_object_child(root, "offset")) != mt_catalogoffset
		|| json_get_float(json_find_object_child(root, "limit")) != mt_cataloglimit
		|| json_get_float(json_find_object_child(root, "tick_us")) != MT_ProfileTick(mt_profile, mt_kind)
		|| json_get_string(json_find_object_child(root, "policy")) != "free_beta") return;
	db = buf_create(); good = TRUE; previous = "";
	for (i = 0; i < n; i += 1)
	{
		item = json_get_child_at_index(rows, i);
		name = json_get_string(json_find_object_child(item, "name"));
		kind = json_get_string(json_find_object_child(item, "kind"));
		if (!MT_CatalogUInt(item, "tier", 20) || !MT_CatalogUInt(item, "mt", 100000000)
			|| !MT_CatalogUInt(item, "kt", 100000000)) { good = FALSE; break; }
		tier = json_get_float(json_find_object_child(item, "tier"));
		if (!MT_MapNameOK(name) || strcmp(kind, mt_kind) || tier < 0 || tier > 20 || tier != floor(tier)) { good = FALSE; break; }
		if (i && strcmp(previous, name) >= 0) { good = FALSE; break; }
		if (!(mt_tiers & (tier ? pow(2, tier - 1) : 1048576))) { good = FALSE; break; }
		mom = json_get_float(json_find_object_child(item, "mt"));
		ksf = json_get_float(json_find_object_child(item, "kt"));
		row = ui_map_index(name); page = cell = -1;
		if (row >= 0)
		if (tokenize(bufstr_get(ms_meta, row)) > MT_UUID)
		{
			if (argv(MT_PAGE) != "-") page = stof(argv(MT_PAGE));
			if (argv(MT_CELL) != "-") cell = stof(argv(MT_CELL));
		}
		bufstr_set(db, i * MT_CAT_FIELDS, name);
		bufstr_set(db, i * MT_CAT_FIELDS + 1, tier ? sprintf("T%g", tier) : "Unrated");
		bufstr_set(db, i * MT_CAT_FIELDS + 2, sprintf("Momentum %s  |  KSF %s", mom ? sprintf("T%g", mom) : "-", ksf ? sprintf("T%g", ksf) : "-"));
		bufstr_set(db, i * MT_CAT_FIELDS + 3, ftos(page));
		bufstr_set(db, i * MT_CAT_FIELDS + 4, ftos(cell));
		previous = name;
	}
	if (!good) { buf_del(db); return; }
	if (mt_catalog) buf_del(mt_catalog);
	mt_catalog = db; mt_catalogcount = n; mt_catalogtotal = total; mt_unqualified = unqualified;
	mt_cataloghosting = json_get_float(json_find_object_child(root, "hosting"));
	MT_Set(key, mt_catalogkey); MT_Set("", mt_catalogmsg); mt_catalogfresh = TRUE;
};

float(float req, float code, string body) MT_Reply =
{
	local int root, rows, item;
	local float n, i, db, me;
	local string id, nonce, expires, ticket, proof, pub, sig, form, note;
	if (req == mt_dirwire && mt_dirwire)
	{
		mt_dirwire = 0;
		if (req != mt_dirreq) { mt_dirnext = 0; return TRUE; }
		mt_dirreq = 0;
		if (code || strlen(body) > 131072) return TRUE;
		root = json_parse(body); if (!root) return TRUE;
		mt_enabled = json_get_float(json_find_object_child(root, "enabled"));
		rows = json_find_object_child(root, "rows"); n = json_get_length(rows);
		if (json_get_value_type(rows) != MT_JSON_ARRAY || n < 0 || n > 200) { json_free(root); return TRUE; }
		db = buf_create(); mt_nd = 0;
		for (i = 0; i < n; i += 1)
		{
			item = json_get_child_at_index(rows, i); id = json_get_string(json_find_object_child(item, "id"));
			if (!MT_Hex(id, 32)) continue;
			bufstr_set(db, mt_nd * MT_DIR_FIELDS, id);
			bufstr_set(db, mt_nd * MT_DIR_FIELDS + 1, MT_Text(json_get_string(json_find_object_child(item, "host")), 64));
			bufstr_set(db, mt_nd * MT_DIR_FIELDS + 2, ftos(json_get_float(json_find_object_child(item, "capacity"))));
			bufstr_set(db, mt_nd * MT_DIR_FIELDS + 3, ftos(json_get_float(json_find_object_child(item, "members"))));
			bufstr_set(db, mt_nd * MT_DIR_FIELDS + 4, MT_Text(json_get_string(json_find_object_child(item, "phase")), 20));
			bufstr_set(db, mt_nd * MT_DIR_FIELDS + 5, ftos(json_get_float(json_find_object_child(item, "revision"))));
			bufstr_set(db, mt_nd * MT_DIR_FIELDS + 6, MT_Text(json_get_string(json_find_object_child(item, "name")), 64));
			mt_nd += 1;
		}
		if (mt_directory) buf_del(mt_directory);
		mt_directory = db; mt_dirloaded = TRUE;
		json_free(root); MT_ClampPages();
		if (mt_rejoin != "")
		{
			for (i = 0; i < mt_nd; i += 1)
				if (MT_Dir(i, 0) == mt_rejoin) break;
			if (i == mt_nd) MT_Note("That room has closed.");
			else if (MT_Dir(i, 4) != "lobby" && strcmp(mt_watch, mt_rejoin)) MT_Note("That room has already started. Click Watch to spectate.");
			else MT_Request("join", mt_rejoin, "-", "-", 0, stof(MT_Dir(i, 5)), TRUE);
			MT_Set("", mt_rejoin);
		}
		return TRUE;
	}
	if (!mt_wire || req != mt_wire) return FALSE;
	mt_wire = 0;
	if (!mt_req || req != mt_req) { mt_next = 0; return TRUE; }
	mt_req = 0;
	if (mt_phase_wire == 3)
	{
		mt_phase_wire = 0;
		if (clientstate() != 1 || ms_consent < FS_TERMS_ONLINE) return TRUE;
		MT_Set("The map list is unavailable right now; it retries by itself.", mt_catalogmsg);
		if (code || strlen(body) > 32768) return TRUE;
		root = json_parse(body); if (!root) return TRUE;
		MT_CatalogReply(root); json_free(root); return TRUE;
	}
	if (clientstate() != 1 || ms_consent < FS_TERMS_ONLINE) { MT_Fail("That request was cancelled. Try again from the menu."); return TRUE; }
	if (code == 429) { MT_Fail("try again shortly"); return TRUE; } // a per-IP limit: back off like a busy reply
	if (code || strlen(body) > 131072) { MT_Fail("The tournament service didn't answer. Try again in a moment."); return TRUE; }
	root = json_parse(body); if (!root) { MT_Fail("The tournament service sent a reply the game can't read. Try again in a moment."); return TRUE; }
	if (json_get_float(json_find_object_child(root, "ok")) != 1)
	{
		note = MT_Text(json_get_string(json_find_object_child(root, "error")), 220);
		if (mt_op == "join") mt_dirnext = 0;
		if (note == "") MT_Fail("The tournament service refused that. Try again in a moment.");
		else MT_Fail(note, TRUE);
		json_free(root); return TRUE;
	}
	if (mt_phase_wire == 1)
	{
		nonce = json_get_string(json_find_object_child(root, "nonce"));
		expires = json_get_string(json_find_object_child(root, "expires")); ticket = json_get_string(json_find_object_child(root, "ticket"));
		if (!MT_Hex(nonce, 32) || !MT_Hex(ticket, 64) || strlen(expires) != 10) { MT_Fail("Your connection check failed. Click again."); json_free(root); return TRUE; }
		for (i = 0; i < 10; i += 1) if (strstrofs("0123456789", substring(expires, i, 1), 0) < 0) break;
		if (i != 10) { MT_Fail("Your connection check failed. Click again."); json_free(root); return TRUE; }
		proof = "";
		if (checkbuiltin(friends_sign)) proof = friends_sign(nonce, "tournament", mt_hash);
		if (tokenize(proof) != 2) { MT_Fail("Update the game to use tournament rooms."); json_free(root); return TRUE; }
		pub = argv(0); sig = argv(1);
		if (!MT_Hex(pub, 64) || !MT_Hex(sig, 128)) { MT_Fail("Your game identity isn't ready yet. Try again in a moment."); json_free(root); return TRUE; }
		form = strcat("payload=", uri_escape(mt_payload), "&nonce=", nonce, "&expires=", expires);
		form = strcat(form, "&ticket=", ticket, "&pub=", pub, "&sig=", sig);
		mt_req = Lob_NextReq(); mt_wire = mt_req; mt_phase_wire = 2; mt_sent = time;
		if (!uri_get(strcat(MT_SITE, "/api/tournament-lobbies/action"), mt_req, "application/x-www-form-urlencoded", form))
		{
			mt_wire = 0;
			MT_Fail("Can't reach the tournament service. Try again in a moment.");
		}
	}
	else
	{
		id = json_get_string(json_find_object_child(root, "me"));
		if (!MT_Who(id)) { MT_Fail("The tournament service sent a reply the game can't read. Try again in a moment."); json_free(root); return TRUE; }
		MT_Set(id, mt_me); mt_needlink = FALSE;
		if (!MT_Snapshot(json_find_object_child(root, "party"))) { MT_Fail("The room didn't load properly. Retrying in a few seconds."); json_free(root); return TRUE; }
		if (mt_op != "state" && mt_noteerr) MT_Set("", mt_note);
		if (mt_op == "configure") mt_cfgretry = 0;
		mt_qstale = FALSE;
		// Every poll is a signature surfd verifies in Python: seats poll every 3 s, spectators
		// every 6 s (presence TTL 35 s); outside a room it only finds this account's own room.
		mt_phase_wire = 0; mt_next = time + 30;
		if (mt_id != "")
		{
			mt_next = time + 6;
			me = MT_MeIndex();
			if (me >= 0)
			if (MT_Player(me, 2) == "player") mt_next = time + 3;
		}
		MT_Set("", mt_payload); MT_Set("", mt_hash); MT_Set("", mt_op);
		MT_Launch(root);
	}
	json_free(root); return TRUE;
};

void() MT_Frame =
{
	local float host, me, value, expected, retried;
	local string op, id, target, map, text;
	MT_SettingsInit();

	// Logical timeout does not cancel native HTTP; only its matching callback
	// releases the wire gate, including callbacks for abandoned logical work.
	if (mt_req && time - mt_sent > 15)
	{
		// A slow public catalogue GET must not mark the room's controls stale.
		if (mt_phase_wire == 3) { mt_req = mt_phase_wire = 0; MT_Set("The map list is slow to load; retrying.", mt_catalogmsg); }
		else MT_Fail("The tournament service is slow to answer; still waiting.");
	}
	if (mt_dirreq && time >= mt_dirnext + 10) mt_dirreq = 0;
	if (ms_consent < FS_TERMS_ONLINE) return;
	// Connected: nothing queued while disconnected may be signed after a later disconnect.
	if (clientstate() != 1) { MT_ClearQueue(); mt_qstale = FALSE; mt_ingame = TRUE; return; }
	// Dropped or quit out of a launched tournament: open on this tab (its Rejoin button), freshly polled.
	if (mt_ingame)
	{
		mt_ingame = FALSE;
		if (mt_launchaddr != "") { menu_screen = SCREEN_TOURNAMENT; mt_next = 0; }
	}
	if (!mt_metadata && menu_screen == SCREEN_TOURNAMENT)
	{
		mt_metadata = TRUE;
		if (!ms_count) ui_load_maps();
	}
	if (menu_screen == SCREEN_TOURNAMENT && mt_id == "") MT_Directory();
	else if (time >= mt_probeat && mt_id == "") { mt_probeat = time + 300; MT_Directory(); }
	host = (mt_id != "" && mt_me == mt_host && mt_phase == "lobby");
	// While a configure is in flight the snapshot is pre-edit: an undo back to it is still an edit.
	if (host && mt_dirty && !MT_Busy("configure") && !MT_PendingDiffers()) mt_dirty = FALSE;
	// The host made the room, so their own seat is accepted for them (configure
	// and seat changes reset it). Once per revision: a refusal cannot loop.
	if (host && !mt_dirty && !mt_qn && mt_autoaccept != mt_revision && mt_fresh && time - mt_fresh < 12)
	{
		me = MT_MeIndex();
		if (me >= 0)
		if (MT_Player(me, 2) == "player")
		if (!stof(MT_Player(me, 3)))
		{
			mt_autoaccept = mt_revision;
			MT_Action("accept", mt_id, "-", "-", 0);
		}
	}
	if (!mt_req && !mt_wire)
	{
		if (mt_qn && !mt_qstale && time >= mt_holdat)
		{
			// bufstr_get hands back copies, so the head can be popped before sending.
			op = bufstr_get(mt_queue, 0); id = bufstr_get(mt_queue, 1); target = bufstr_get(mt_queue, 2);
			map = bufstr_get(mt_queue, 3); value = stof(bufstr_get(mt_queue, 4));
			expected = stof(bufstr_get(mt_queue, 5)); retried = stof(bufstr_get(mt_queue, 6));
			text = bufstr_get(mt_queue, 7);
			MT_Dequeue();
			MT_Send(op, id, target, map, value, expected, retried, text);
		}
		else if (host && mt_dirty && !mt_qstale && time >= mt_applyat && time >= mt_holdat)
		{
			mt_sentgen = mt_editgen;
			MT_Send("configure", mt_id, "-", "-", 0, -1, FALSE, "-");
		}
		else if ((mt_engaged || menu_screen == SCREEN_TOURNAMENT) && time >= mt_next)
			MT_Send("state", "-", "-", "-", 0, -1, FALSE, "-");
	}
	MT_Catalog();
};

void(float i) MT_Connect =
{
	// Legacy name kept for menu fixture callers; joining is now BACKEND-ONLY.
	if (i < 0 || i >= mt_nd || !MT_Hex(MT_Dir(i, 0), 32)) return;
	if (stof(MT_Dir(i, 5)) < 1) { mt_dirnext = 0; return; }
	// A started room's button is Watch: the same join, refused by today's surfd (MT_Fail).
	MT_Set((MT_Dir(i, 4) != "lobby") ? MT_Dir(i, 0) : "", mt_watch);
	MT_Action("join", MT_Dir(i, 0), "-", "-", 0, stof(MT_Dir(i, 5)));
};

// ---------------------------------------------------------------------------
//  Drawing. Native single-pass text, measured fitting, fixed control geometry.
// ---------------------------------------------------------------------------

// Measure with the SAME physical font/size that sui_native_text draws. The
// frame-local cache index gives stable labels an O(1) hit without parsing or
// wrapping their text every frame. Cutting is at UTF-8 character boundaries.
string(string text, float want, float width) MT_Fit =
{
	local float slot, legacy, lo, hi, mid, n, kerning;
	local vector glyph;
	local string result, trial;
	slot = mt_fit_used; mt_fit_used += 1;
	legacy = drawfont; drawfont = Font_NativeSlot(legacy);
	glyph = sui_native_text_size(want); kerning = cvar("r_font_kerning");
	if (!mt_fit_cache) mt_fit_cache = buf_create();
	if (slot < MT_FIT_MAX && mt_fit_cache)
	{
		if (bufstr_get(mt_fit_cache, slot * 2) == text && mt_fit_width[slot] == width
			&& mt_fit_font[slot] == drawfont && mt_fit_gen[slot] == ui_font_gen && mt_fit_size[slot] == glyph
			&& mt_fit_kerning[slot] == kerning)
		{
			result = bufstr_get(mt_fit_cache, slot * 2 + 1);
			drawfont = legacy;
			return result;
		}
	}
	result = text;
	if (stringwidth(text, TRUE, glyph) > width)
	{
		result = "";
		if (stringwidth("...", TRUE, glyph) <= width)
		{
			lo = 0; hi = strlen(text);
			while (lo < hi)
			{
				mid = ceil((lo + hi) / 2); n = UI_CharBytes(text, mid);
				trial = strcat(substring(text, 0, n), "...");
				if (stringwidth(trial, TRUE, glyph) <= width) lo = mid;
				else hi = mid - 1;
			}
			result = strcat(substring(text, 0, UI_CharBytes(text, lo)), "...");
		}
	}
	if (slot < MT_FIT_MAX && mt_fit_cache)
	{
		bufstr_set(mt_fit_cache, slot * 2, text); bufstr_set(mt_fit_cache, slot * 2 + 1, result);
		mt_fit_width[slot] = width; mt_fit_font[slot] = drawfont;
		mt_fit_gen[slot] = ui_font_gen; mt_fit_size[slot] = glyph; mt_fit_kerning[slot] = kerning;
	}
	drawfont = legacy;
	return result;
};

// face 0 = Roboto (body/headings), 1 = Bebas Neue (titles, big card overlays).
float(string text, float want, float face) MT_Width =
{
	local float previous, legacy, w;
	previous = ui_font_cur;
	Font_Set(face ? ui_font_display : ui_font_ui);
	legacy = drawfont; drawfont = Font_NativeSlot(legacy);
	w = stringwidth(text, TRUE, sui_native_text_size(want));
	drawfont = legacy; Font_Set(previous);
	return w;
};

void(vector pos, string text, float want, vector colour, float width = 0, float face = 0) MT_Label =
{
	local float previous;
	previous = ui_font_cur;
	Font_Set(face ? ui_font_display : ui_font_ui);
	if (width > 0) text = MT_Fit(text, want, width);
	sui_native_text(pos, text, want, colour, 1);
	Font_Set(previous);
};

// Text fitted into a box, centred on the caps; align 0 left, 1 centre, 2 right.
void(vector pos, vector size, string text, float want, vector colour, float align = 0, float face = 0) MT_Place =
{
	local float previous, legacy, w, x;
	local vector glyph;
	if (text == "" || size_x <= 0) return;
	previous = ui_font_cur;
	Font_Set(face ? ui_font_display : ui_font_ui);
	legacy = drawfont; drawfont = Font_NativeSlot(legacy);
	glyph = sui_native_text_size(want); drawfont = legacy;
	text = MT_Fit(text, want, size_x);
	x = pos_x;
	if (align)
	{
		legacy = drawfont; drawfont = Font_NativeSlot(legacy);
		w = stringwidth(text, TRUE, glyph); drawfont = legacy;
		x = (align == 1) ? (pos_x + floor((size_x - w) / 2)) : (pos_x + size_x - w);
	}
	sui_native_text([x, pos_y + (size_y - glyph_y) / 2 + FONT_CAPDROP * glyph_y], text, want, colour, 1);
	Font_Set(previous);
};

// Word-wrapped text, at most maxlines lines of (want + 4) px; the last one is fitted with "...".
// Returns the lines used; draw FALSE only measures.
float(vector pos, float width, string text, float want, vector colour, float maxlines, float draw) MT_Para =
{
	local float n, at, cut, j;
	local string rest, line;
	rest = text; n = 0;
	while (rest != "" && n < maxlines)
	{
		cut = 0;
		if (n < maxlines - 1)
		if (MT_Width(rest, want, 0) > width)
		{
			j = 0;
			while (TRUE)
			{
				at = strstrofs(rest, " ", j);
				if (at < 0) break;
				if (MT_Width(substring(rest, 0, at), want, 0) > width) break;
				cut = at; j = at + 1;
			}
		}
		line = rest; rest = "";
		if (cut > 0) { rest = substring(line, cut + 1, -1); line = substring(line, 0, cut); }
		if (draw) MT_Place(pos + [0, n * (want + 4)], [width, want + 4], line, want, colour);
		n += 1;
	}
	return n;
};

// A small status tag; returns its width so a row can be laid out right to left.
float(vector pos, string text, vector colour, float right = FALSE) MT_Pill =
{
	local float w;
	w = ceil(MT_Width(text, 12, 0)) + 16;
	if (right) pos_x -= w;
	sui_style_box(pos, [w, 20], 10, SUI_THEME_PANEL * 0.7 + colour * 0.2, SUI_THEME_PANEL * 0.4 + colour * 0.6, 1);
	MT_Place(pos, [w, 20], text, 12, colour, 1);
	return w;
};

// style: 0 plain, 1 go (mint), 2 danger (rose), 3 accent (sky). Label centred.
float(string id, vector pos, vector size, string label, float style = 0,
	float enabled = TRUE, float selected = FALSE) MT_Button =
{
	local float hot, held;
	local vector fill, edge, colour, tint;
	if (enabled) sui_action_element(pos, size, id, sui_noop);
	hot = (enabled && sui_is_hovered(id));
	held = (enabled && sui_is_held(id));
	if (style)
	{
		tint = SUI_THEME_GOOD;
		if (style == 2) tint = SUI_THEME_BAD;
		if (style == 3) tint = SUI_THEME_ACCENT;
		fill = hot ? tint : (SUI_THEME_CHIP * 0.72 + tint * 0.24);
		if (held) fill = tint * 0.8;
		edge = tint;
		colour = hot ? SUI_THEME_WELL : tint;
	}
	else
	{
		// QC's ?: binds tighter than &&/||: group boolean conditions explicitly.
		// A selected toggle is a stronger sky fill with white text, so it never
		// reads like the hover state under a parked cursor.
		fill = held ? SUI_THEME_PRESSED : (hot ? SUI_THEME_HOVER : SUI_THEME_CHIP);
		if (selected) fill = SUI_THEME_CHIP * (hot ? 0.5 : 0.62) + SUI_THEME_ACCENT * (hot ? 0.48 : 0.38);
		edge = (hot || selected) ? SUI_THEME_ACCENT : SUI_THEME_EDGE;
		colour = selected ? SUI_THEME_TEXT : (hot ? SUI_THEME_ACCENT : SUI_THEME_TEXT);
	}
	if (!enabled)
	{
		fill = SUI_THEME_CHIP; edge = SUI_THEME_EDGE; colour = SUI_THEME_MUTED;
		if (selected) { fill = SUI_THEME_CHIP * 0.7 + SUI_THEME_ACCENT * 0.22; colour = SUI_THEME_DIM; }
	}
	sui_style_box(pos, size, 7, fill, edge, enabled ? 1 : 0.7);
	if (label != "") MT_Place(pos + '8 0 0', size - '16 0 0', label, 16, colour, 1);
	return enabled && sui_is_released(id);
};

// [-] value [+] (numeric) or [<] choice [>]; returns -1, 0 or +1.
float(string id, vector pos, vector size, string text, vector colour, float canprev, float cannext, float numeric) MT_Stepper =
{
	local float r, bw;
	bw = size_y + 4; r = 0;
	if (MT_Button(strcat(id, "_down"), pos, [bw, size_y], numeric ? "-" : "<", 0, canprev)) r = -1;
	sui_style_box(pos + [bw + 4, 0], [size_x - 2 * bw - 8, size_y], 7, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	MT_Place(pos + [bw + 12, 0], [size_x - 2 * bw - 24, size_y], text, 16, colour, 1);
	if (MT_Button(id, pos + [size_x - bw, 0], [bw, size_y], numeric ? "+" : ">", 0, cannext)) r = 1;
	return r;
};

// A missing preview gets the map's name as a title card instead of a black block.
void(vector pos, vector size, float page, float cell, string name) MT_Thumb =
{
	ui_thumb(pos, size, page, cell);
	if (page < 0 || cell < 0)
	if (name != "")
	if (size_y >= 40)
		MT_Place(pos + '10 0 0', size - '20 0 0', name, (size_y >= 90) ? 32 : 24, SUI_THEME_EDGE_HI, 1, 1);
	sui_border_box(pos, size, 1, SUI_THEME_EDGE, 1, 0);
};

// What a player sees where the host sees a control.
void(vector pos, vector size, string text, vector colour) MT_Value =
{
	sui_style_box(pos, size, 7, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	MT_Place(pos + '12 0 0', size - '24 0 0', text, 16, colour);
};

// Slot colours, as in an RTS lobby: the seat bar, the draft cards and the schedule agree.
vector(float seat) MT_SeatColour =
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

string(string name) MT_RoomTitle = { return (name != "") ? strcat(name, "'s tournament") : "Tournament room"; };
string() MT_Summary =
{
	return sprintf("%s  |  %s  |  %s  |  %s rounds", MT_KindLabel(mt_actualkind), MT_TierLabel(mt_actualtiers),
		MT_ProfileLabel(mt_actualprofile, mt_actualkind), MT_Minutes(mt_seconds));
};
float() MT_PhaseStep =
{
	if (mt_phase == "lobby") return 0;
	if (mt_phase == "draft") return 1;
	if (!mt_started) return 2;
	return 3;
};
float(float s, float dir) MT_SecondsStep =
{
	if (dir > 0)
	{
		if (s < 300) return floor(s / 60) * 60 + 60;
		if (s < 600) return 600;
		return 900;
	}
	if (s > 600) return 600;
	if (s > 300) return 300;
	return max(60, ceil(s / 60) * 60 - 60);
};

// 1 Lobby - 2 Map draft - 3 Ready check - 4 Launch.
void(vector pos, float w, float step) MT_Steps =
{
	local float i, x, segw, lw, done, cur, compact;
	local string label;
	local vector col;
	segw = floor(w / 4); compact = (segw < 160);
	for (i = 0; i < 4; i += 1)
	{
		x = pos_x + i * segw;
		done = (i < step); cur = (i == step);
		col = done ? SUI_THEME_GOOD : (cur ? SUI_THEME_ACCENT : SUI_THEME_MUTED);
		label = "Launch";
		if (i == 0) label = "Lobby";
		if (i == 1) label = compact ? "Draft" : "Map draft";
		if (i == 2) label = compact ? "Ready" : "Ready check";
		sui_style_box([x, pos_y], '28 28 0', 14, (done || cur) ? (SUI_THEME_PANEL * 0.6 + col * 0.3) : SUI_THEME_WELL, col, 1);
		MT_Place([x, pos_y], '28 28 0', ftos(i + 1), 16, (done || cur) ? col : SUI_THEME_MUTED, 1);
		lw = MT_Width(label, 16, 0);
		MT_Place([x + 36, pos_y], [segw - 44, 28], label, 16, cur ? SUI_THEME_TEXT : col);
		if (i < 3)
		if (segw - 56 - lw >= 16)
			sui_fill([x + 48 + lw, pos_y + 13], [segw - 56 - lw, 2], done ? SUI_THEME_GOOD : SUI_THEME_EDGE, 1, 0);
	}
};

// Returns TRUE on the confirming click.
float(vector pos, string who, float i) MT_KickButton =
{
	local float armed;
	armed = (mt_kickwho == who && time < mt_kickat);
	if (!MT_Button(sprintf("mt_kick%g", i), pos, '64 30 0', armed ? "Sure?" : "Kick", armed ? 2 : 0, mt_ok)) return FALSE;
	if (armed) { MT_Set("", mt_kickwho); return TRUE; }
	MT_Set(who, mt_kickwho); mt_kickat = time + 3;
	return FALSE;
};

void(vector pos, vector size, float seat, float i) MT_SeatRow =
{
	local float host, lobby, right, mine, online, accepted, ready, want, x;
	local string who, name, text;
	local vector colour, pillc;
	colour = MT_SeatColour(seat);
	host = (mt_me == mt_host); lobby = (mt_phase == "lobby");
	if (i < 0)
	{
		sui_style_box(pos, size, 8, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
		sui_fill(pos + '0 10 0', [3, size_y - 20], colour, 0.4, 0);
		MT_Place(pos + '14 0 0', [24, size_y], ftos(seat + 1), 16, SUI_THEME_MUTED);
		MT_Place(pos + '52 0 0', [size_x - 64, size_y], lobby ? "Open seat" : "Empty seat", 16, SUI_THEME_MUTED);
		return;
	}
	who = MT_Player(i, 0); name = MT_Player(i, 1); mine = (who == mt_me);
	online = stof(MT_Player(i, 8)); accepted = stof(MT_Player(i, 3)); ready = stof(MT_Player(i, 7));
	sui_style_box(pos, size, 8, mine ? SUI_THEME_SELECTED : SUI_THEME_CHIP, mine ? SUI_THEME_ACCENT : SUI_THEME_EDGE, 1);
	sui_fill(pos + '0 8 0', [4, size_y - 16], colour, 1, 0);
	MT_Place(pos + '14 0 0', [24, size_y], ftos(seat + 1), 16, colour);
	sui_roundbox(pos + [36, 13], '8 8 0', 4, online ? SUI_THEME_GOOD : SUI_THEME_MUTED, 1);
	right = size_x - 10;
	if (host && lobby)
	{
		if (!mine)
		{
			if (MT_KickButton(pos + [right - 64, floor((size_y - 30) / 2)], who, i)) MT_Action("kick", mt_id, who, "-", 0);
			right -= 72;
		}
		if (MT_Button(sprintf("mt_seat%g", i), pos + [right - 96, floor((size_y - 30) / 2)], '96 30 0', "Spectate", 0, mt_ok))
			MT_Action("seat", mt_id, who, "-", 0);
		right -= 104;
	}
	text = ""; pillc = SUI_THEME_DIM;
	if (!online) { text = "OFFLINE"; pillc = SUI_THEME_BAD; }
	else if (lobby) { text = accepted ? "ACCEPTED" : "SEAT OFFERED"; pillc = accepted ? SUI_THEME_GOOD : SUI_THEME_WARN; }
	else if (mt_phase == "draft")
	{
		if (who == mt_turnwho) { text = (mt_turnkind == "ban") ? "BANNING" : "PICKING"; pillc = SUI_THEME_FOCUS; }
	}
	else if (!mt_started) { text = ready ? "READY" : "NOT READY"; pillc = ready ? SUI_THEME_GOOD : SUI_THEME_MUTED; }
	// Name on the top line, its tags under it: a long name keeps the row's width.
	want = (size_y >= 56) ? 20 : 16;
	MT_Place(pos + '52 4 0', [right - 58, 22], strcat(name, mine ? " (you)" : ""), want, SUI_THEME_TEXT);
	x = 52;
	if (who == mt_host) x += MT_Pill(pos + [x, size_y - 24], "HOST", SUI_THEME_ACCENT2) + 6;
	if (text != "") MT_Pill(pos + [x, size_y - 24], text, pillc);
};

void(vector pos, vector size, float i) MT_SpecRow =
{
	local float right, mine;
	local string who;
	who = MT_Player(i, 0); mine = (who == mt_me);
	sui_style_box(pos, size, 8, mine ? SUI_THEME_SELECTED : SUI_THEME_WELL, mine ? SUI_THEME_ACCENT : SUI_THEME_EDGE, 1);
	sui_roundbox(pos + [16, floor(size_y / 2) - 4], '8 8 0', 4, stof(MT_Player(i, 8)) ? SUI_THEME_GOOD : SUI_THEME_MUTED, 1);
	right = size_x - 10;
	// P1650's host can remove a spectator until launch; today's surfd refuses it outside the lobby (MT_Friendly).
	if (mt_me == mt_host && !mt_started && !mine)
	{
		if (MT_KickButton(pos + [right - 64, floor((size_y - 30) / 2)], who, i)) MT_Action("kick", mt_id, who, "-", 0);
		right -= 72;
	}
	if (mt_me == mt_host && mt_phase == "lobby")
	{
		if (MT_Button(sprintf("mt_seat%g", i), pos + [right - 110, floor((size_y - 30) / 2)], '110 30 0', "Give seat", 3, (mt_ok && mt_seated < mt_capacity)))
			MT_Action("seat", mt_id, who, "-", 1);
		right -= 118;
	}
	if (who == mt_host) right -= MT_Pill(pos + [right, floor((size_y - 20) / 2)], "HOST", SUI_THEME_ACCENT2, TRUE) + 6;
	MT_Place(pos + '32 0 0', [right - 38, size_y], strcat(MT_Player(i, 1), mine ? " (you)" : ""), 16, SUI_THEME_DIM);
};

float(float rh) MT_RosterHeight = { return 56 + (mt_capacity + 1 + max(1, mt_nspec)) * (rh + 6) + 4; };

// Seats first (every slot, open ones included), then spectators; one paged list.
// Draws inside the caller's panel; `size` is the usable area.
void(vector size) MT_DrawRoster =
{
	local float host, rh, avail, items, perpage, k, y, first, last;
	host = (mt_me == mt_host);
	MT_Label('16 14 0', "players", 24, SUI_THEME_ACCENT, size_x - 190);
	MT_Place([size_x - 186, 12], '170 30 0', sprintf("%g of %g seats taken", mt_seated, mt_capacity), 12, SUI_THEME_DIM, 2);
	rh = (size_y >= 560) ? 56 : 48;
	items = mt_capacity + 1 + max(1, mt_nspec);
	avail = size_y - 56 - 4;
	perpage = floor(avail / (rh + 6));
	if (items > perpage) perpage = max(1, floor((avail - 40) / (rh + 6)));
	mt_rosterrows = perpage; MT_ClampPages();
	first = mt_rosterpage * perpage; last = min(items, first + perpage);
	y = 56;
	for (k = first; k < last; k += 1)
	{
		if (k < mt_capacity) MT_SeatRow([12, y], [size_x - 24, rh], k, mt_seatof[k]);
		else if (k == mt_capacity) MT_Place([16, y + 6], [size_x - 32, rh - 6], sprintf("spectators (%g)", mt_nspec), 16, SUI_THEME_TEXT);
		else if (mt_nspec) MT_SpecRow([12, y], [size_x - 24, rh], mt_specof[k - mt_capacity - 1]);
		else MT_Place([16, y], [size_x - 32, rh], host ? "Friends who join wait here until you give them a seat." : "Nobody is spectating.", 12, SUI_THEME_MUTED);
		y += rh + 6;
	}
	if (items > perpage)
	{
		y = size_y - 40;
		if (MT_Button("mt_players_prev", [12, y], '96 30 0', "Previous", 0, mt_rosterpage > 0)) mt_rosterpage -= 1;
		if (MT_Button("mt_players_next", [116, y], '80 30 0', "Next", 0, last < items)) mt_rosterpage += 1;
		MT_Place([208, y], [size_x - 220, 30], sprintf("page %g of %g", mt_rosterpage + 1, ceil(items / perpage)), 12, SUI_THEME_MUTED);
	}
};

float(string label, float y, float stacked, float cx, float ch) MT_RowLabel =
{
	if (stacked) { MT_Place([16, y], [cx + 400, 16], label, 12, SUI_THEME_MUTED); return y + 18; }
	MT_Place([16, y], [cx - 24, ch], label, 16, SUI_THEME_DIM);
	return y;
};

void() MT_OpenPool =
{
	MT_Set((mt_me == mt_host && mt_phase == "lobby") ? mt_pool : mt_actualpool, mt_editpool);
	mt_modal = 1; mt_catalogoffset = 0;
};

// Every setting on one panel: live controls for the host, the same rows read-only
// for everyone else, then whether the pool can feed a draft, then the pool itself.
void(vector size) MT_DrawSettings =
{
	local float edit, stacked, y, cx, cw, cy, ch, gap, i, k, chipw, r, idx, need, ready, x, tw, th, n, rows, shown, count;
	local string text, name, pool;
	local vector colour;
	edit = (mt_me == mt_host && mt_phase == "lobby" && !MT_Busy("lock"));
	MT_Label('16 14 0', "settings", 24, SUI_THEME_ACCENT, size_x - 230);
	if (edit)
	{
		text = (mt_dirty || MT_Busy("configure")) ? "Saving..." : "Saved; everyone sees these";
		colour = (mt_dirty || MT_Busy("configure")) ? SUI_THEME_WARN : SUI_THEME_MUTED;
	}
	else { text = "Set by the host"; colour = SUI_THEME_MUTED; }
	MT_Place([size_x - 226, 12], '210 30 0', text, 12, colour, 2);
	stacked = (size_x < 400);
	cx = stacked ? 16 : 136; cw = size_x - cx - 16;
	ch = (size_y < 380) ? 30 : 34;
	gap = bound(4, floor((size_y - 56 - 6 * (ch + (stacked ? 18 : 0)) - 64) / 6), 10);
	y = 56;

	cy = MT_RowLabel("Mode", y, stacked, cx, ch);
	if (edit)
	{
		if (MT_Button("mt_kind_surf", [cx, cy], [floor((cw - 6) / 2), ch], "Surf", 0, TRUE, mt_kind == "surf"))
			if (mt_kind != "surf") { MT_Set("surf", mt_kind); MT_FilterChanged(); MT_Edit(); }
		if (MT_Button("mt_kind_bhop", [cx + floor((cw - 6) / 2) + 6, cy], [cw - floor((cw - 6) / 2) - 6, ch], "Bhop", 0, TRUE, mt_kind == "bhop"))
			if (mt_kind != "bhop") { MT_Set("bhop", mt_kind); MT_FilterChanged(); MT_Edit(); }
	}
	else MT_Value([cx, cy], [cw, ch], MT_KindLabel(mt_actualkind), SUI_THEME_TEXT);
	y = cy + ch + gap;

	// T1-T10 and unrated, all inline.
	cy = MT_RowLabel("Tiers", y, stacked, cx, ch);
	if (edit)
	{
		chipw = floor((cw - MT_TIERS * 4) / (MT_TIERS + 1));
		for (i = 0; i <= MT_TIERS; i += 1)
		{
			k = (i == MT_TIERS) ? 20 : i;
			x = cx + i * (chipw + 4);
			if (MT_Button(sprintf("mt_tier%g", k + 1), [x, cy], [(i == MT_TIERS) ? (cx + cw - x) : chipw, ch], (k == 20) ? "?" : ftos(k + 1), 0, TRUE, mt_tiers & pow(2, k)))
				MT_ToggleTier(k);
		}
		sui_tooltip_for("mt_tier21", "Maps that have no tier yet.", 2);
	}
	else MT_Value([cx, cy], [cw, ch], MT_TierLabel(mt_actualtiers), SUI_THEME_TEXT);
	y = cy + ch + gap;

	cy = MT_RowLabel("Movement", y, stacked, cx, ch);
	if (edit)
	{
		r = MT_Stepper("mt_movement", [cx, cy], [cw, ch], MT_ProfileLabel(mt_profile, mt_kind), (mt_profile == "default") ? SUI_THEME_TEXT : SUI_THEME_WARN, TRUE, TRUE, FALSE);
		if (r)
		{
			idx = MT_ProfileIndex(mt_profile) + r;
			if (idx < 0) idx = 6;
			if (idx > 6) idx = 0;
			MT_Set(MT_ProfileID(idx), mt_profile); MT_FilterChanged(); MT_Edit();
		}
	}
	else MT_Value([cx, cy], [cw, ch], MT_ProfileLabel(mt_actualprofile, mt_actualkind), (mt_actualprofile == "default") ? SUI_THEME_TEXT : SUI_THEME_WARN);
	y = cy + ch + gap;

	cy = MT_RowLabel("Round time", y, stacked, cx, ch);
	if (edit)
	{
		r = MT_Stepper("mt_seconds", [cx, cy], [cw, ch], MT_Minutes(mt_newseconds), SUI_THEME_TEXT, mt_newseconds > 60, mt_newseconds < 900, TRUE);
		if (r) { mt_newseconds = MT_SecondsStep(mt_newseconds, r); MT_Edit(); }
	}
	else MT_Value([cx, cy], [cw, ch], MT_Minutes(mt_seconds), SUI_THEME_TEXT);
	y = cy + ch + gap;

	cy = MT_RowLabel("Seats", y, stacked, cx, ch);
	if (edit)
	{
		r = MT_Stepper("mt_capacity", [cx, cy], [cw, ch], sprintf("%g players", mt_newseats), SUI_THEME_TEXT, mt_newseats > max(2, mt_seated), mt_newseats < 8, TRUE);
		if (r) { mt_newseats = bound(max(2, mt_seated), mt_newseats + r, 8); MT_Edit(); }
	}
	else MT_Value([cx, cy], [cw, ch], sprintf("%g players", mt_capacity), SUI_THEME_TEXT);
	y = cy + ch + gap;

	cy = MT_RowLabel("Map pool", y, stacked, cx, ch);
	pool = edit ? mt_pool : mt_actualpool;
	count = MT_PoolCount(pool);
	MT_Value([cx, cy], [cw - 96, ch], (pool == "-") ? "Auto: every matching map" : sprintf("Manual: %g picked", count), SUI_THEME_TEXT);
	if (MT_Button("mt_pool", [cx + cw - 88, cy], [88, ch], edit ? "Edit" : "View")) MT_OpenPool();
	y = cy + ch + gap + 6;

	// Can this pool feed a draft? Said before Lock refuses it.
	ready = (mt_catalogfresh && !strcmp(MT_CatalogKey(), mt_catalogkey));
	need = 3 * max(2, mt_seated);
	colour = SUI_THEME_GOOD;
	if (!ready) { text = (mt_catalogmsg != "") ? mt_catalogmsg : "Checking which maps qualify..."; colour = SUI_THEME_MUTED; }
	else if (!mt_cataloghosting) { text = "Tournament hosting is unavailable right now."; colour = SUI_THEME_BAD; }
	else if (pool != "-" && count < need) { text = sprintf("The manual pool has %g maps; the draft needs %g (3 per player).", count, need); colour = SUI_THEME_WARN; }
	else if (mt_catalogtotal < need) { text = sprintf("Only %g maps qualify; the draft needs %g (3 per player).", mt_catalogtotal, need); colour = SUI_THEME_WARN; }
	else text = sprintf("%g qualified maps match. The draft uses %g (3 per player).", mt_catalogtotal, need);
	MT_Place([16, y], [size_x - 32, 18], text, 12, colour); y += 20;
	if ((edit ? mt_profile : mt_actualprofile) != "default")
	if (y + 18 <= size_y - 6) { MT_Place([16, y], [size_x - 32, 18], "Unranked movement profile.", 12, SUI_THEME_WARN); y += 20; }
	if (y + 18 <= size_y - 6)
		MT_Place([16, y], [size_x - 32, 18], edit ? "Changing a setting un-accepts every seat." : "Only the host can change settings.", 12, SUI_THEME_MUTED);
	y += 30;

	// The pool at a glance: the first catalogue page, as pictures.
	n = max(1, floor((size_x - 32 + 10) / (150 + 10)));
	tw = floor((size_x - 32 - 10 * (n - 1)) / n); th = floor(tw * 9 / 16);
	rows = bound(1, floor((size_y - y - 44) / (th + 30)), 2);
	th = min(th, size_y - y - 44 - (rows - 1) * (th + 30) - 30);
	if (!mt_modal && (mt_cataloglimit != min(16, n * rows) || mt_catalogoffset)) { mt_cataloglimit = min(16, n * rows); mt_catalogoffset = 0; }
	if (ready && mt_catalogcount && th >= 40)
	{
		MT_Place([16, y], [size_x - 32, 16], (pool == "-") ? "in the pool" : "in the pool (this page)", 12, SUI_THEME_MUTED);
		y += 20; shown = 0;
		for (i = 0; i < mt_catalogcount && shown < n * rows; i += 1)
		{
			name = MT_Cat(i, 0);
			if (!MT_InPool(pool, name)) continue;
			x = 16 + (shown - floor(shown / n) * n) * (tw + 10);
			MT_Thumb([x, y + floor(shown / n) * (th + 30)], [tw, th], stof(MT_Cat(i, 3)), stof(MT_Cat(i, 4)), name);
			MT_Place([x, y + floor(shown / n) * (th + 30) + th + 4], [tw, 18], name, 12, SUI_THEME_DIM);
			shown += 1;
		}
		if (pool == "-" && mt_catalogtotal > shown)
			MT_Place([16, y + ceil(shown / n) * (th + 30)], [size_x - 32, 18], sprintf("and %g more", mt_catalogtotal - shown), 12, SUI_THEME_MUTED);
	}
};

float(vector p, vector size, float i, float clickable) MT_MapCard =
{
	local string id, status, info, by;
	local float hot, th, w;
	local vector edge, tp, ts;
	id = sprintf("mt_map%g", i);
	status = MT_Map(i, 1);
	if (clickable) sui_action_element(p, size, id, sui_noop);
	hot = (clickable && sui_is_hovered(id));
	th = size_y - 62;
	edge = SUI_THEME_EDGE;
	if (status == "picked") edge = SUI_THEME_GOOD;
	if (status == "reserve") edge = SUI_THEME_INFO;
	if (hot) edge = (mt_turnkind == "ban") ? SUI_THEME_BAD : SUI_THEME_GOOD;
	sui_style_box(p, size, 10, hot ? SUI_THEME_HOVER : SUI_THEME_CHIP, edge, 1);
	tp = p + '6 6 0'; ts = [size_x - 12, th];
	MT_Thumb(tp, ts, stof(MT_Map(i, 3)), stof(MT_Map(i, 4)), (status == "banned" || hot) ? "" : MT_Map(i, 0));
	if (status == "banned")
	{
		sui_fill(tp, ts, '0 0 0', 0.64, 0);
		MT_Place(tp, ts, "BANNED", 24, SUI_THEME_BAD, 1, 1);
	}
	else if (hot)
	{
		sui_fill(tp, ts, '0 0 0', 0.4, 0);
		MT_Place(tp, ts, (mt_turnkind == "ban") ? "BAN" : "PICK", 32, edge, 1, 1);
	}
	else if (status == "picked") MT_Pill(tp + '6 6 0', "PICKED", SUI_THEME_GOOD);
	else if (status == "reserve") MT_Pill(tp + '6 6 0', "RESERVE", SUI_THEME_INFO);
	MT_Place(p + [10, th + 12], [size_x - 20, 22], MT_Map(i, 0), 16, (status == "banned") ? SUI_THEME_MUTED : SUI_THEME_TEXT);
	info = MT_Map(i, 5);
	if (MT_Map(i, 8) != "") info = strcat(info, "  |  ", MT_Map(i, 8));
	by = MT_Map(i, 7); w = size_x - 20;
	if (status != "pool" && by != "")
	{
		MT_Place(p + [10 + floor(w * 0.45), th + 36], [w - floor(w * 0.45), 18], by, 12, MT_SeatColour(stof(MT_Map(i, 6))), 2);
		w = floor(w * 0.45) - 6;
	}
	MT_Place(p + [10, th + 36], [w, 18], info, 12, SUI_THEME_DIM);
	return (clickable && sui_is_released(id));
};

void(vector size) MT_DrawDraft =
{
	local float i, c, bans, picks, myturn, gap, cols, cardw, cardh, thumbh, rows, top, avail, first, last, row, pagerh, need;
	local float left, urgent, hint, want, tw, cw;
	local vector p, colour;
	local string text, clock;
	MT_Label('16 14 0', "map draft", 24, SUI_THEME_ACCENT, size_x - 250);
	bans = picks = 0;
	for (i = 0; i < mt_nm; i += 1)
	{
		if (MT_Map(i, 1) == "banned") bans += 1;
		else if (MT_Map(i, 1) != "pool") picks += 1;
	}
	MT_Place([size_x - 246, 12], '230 30 0', sprintf("bans %g of %g  |  picks %g of %g", bans, mt_seated, picks, mt_seated), 12, SUI_THEME_DIM, 2);
	myturn = (mt_turnwho != "" && mt_turnwho == mt_me);
	colour = myturn ? SUI_THEME_FOCUS : MT_SeatColour(mt_turnseat);
	p = '12 52 0';
	sui_style_box(p, [size_x - 24, 52], 10, myturn ? (SUI_THEME_PANEL * 0.62 + SUI_THEME_FOCUS * 0.26) : SUI_THEME_CHIP, myturn ? SUI_THEME_FOCUS : SUI_THEME_EDGE, 1);
	sui_fill(p + '0 10 0', '4 32 0', colour, 1, 0);
	if (myturn) text = (mt_turnkind == "ban") ? "Your turn: ban a map" : "Your turn: pick a map";
	else text = sprintf("%s is %s", mt_turnname, (mt_turnkind == "ban") ? "banning a map" : "picking a map");
	// P1650's turn clock beside it; at 0 the server bans/picks for whoever is up.
	left = -1;
	if (mt_turnleft >= 0) left = max(0, ceil(mt_turnleft - (time - mt_turnat)));
	urgent = (left >= 0 && left < 10);
	clock = "";
	if (left >= 0) clock = (myturn && urgent) ? sprintf("(%g s, or one is chosen for you)", left) : sprintf("(%g s)", left);
	// The hint gives way first: on a narrow panel, or to the urgent clock, the turn line needs the width.
	hint = (size_x >= 640 && !(myturn && urgent));
	want = (size_x >= 440) ? 20 : 16;
	tw = size_x - 60 - (hint ? 200 : 0);
	cw = 0;
	if (clock != "") cw = min(ceil(MT_Width(clock, 16, 0)), floor(tw * 0.6));
	MT_Place(p + '18 0 0', [tw - (cw ? cw + 8 : 0), 52], text, want, myturn ? SUI_THEME_FOCUS : SUI_THEME_TEXT);
	if (cw) MT_Place(p + [26 + min(ceil(MT_Width(text, want, 0)), tw - cw - 8), 0], [cw, 52], clock, 16, urgent ? SUI_THEME_WARN : SUI_THEME_DIM);
	if (hint) MT_Place(p + [size_x - 236, 0], '200 52 0', myturn ? "Click a map card." : "The cards update live.", 12, myturn ? SUI_THEME_TEXT : SUI_THEME_MUTED, 2);
	top = 116; gap = 12;
	if (size_y >= 420)
	{
		MT_Place('16 110 0', [size_x - 32, 18], "Everyone bans one map, then picks one in reverse order. Rounds are drawn from the picks; one pick is the reserve.", 12, SUI_THEME_MUTED);
		top = 136;
	}
	avail = size_y - top - 12;
	// The biggest cards that still show the whole pool on one page; paging is
	// for pools that do not fit even as 120 px cards.
	cols = 0;
	for (c = 1; c <= 6; c += 1)
	{
		cardw = floor((size_x - 24 - gap * (c - 1)) / c);
		if (cardw < 120) break;
		if (ceil(mt_nm / c) * (floor(cardw * 9 / 16) + 62 + gap) - gap <= avail) { cols = c; break; }
	}
	pagerh = 0;
	if (cols)
	{
		cardw = floor((size_x - 24 - gap * (cols - 1)) / cols);
		thumbh = floor(cardw * 9 / 16);
	}
	else
	{
		cols = bound(1, floor((size_x - 24 + gap) / (150 + gap)), 6);
		cardw = floor((size_x - 24 - gap * (cols - 1)) / cols);
		need = ceil(mt_nm / cols);
		thumbh = max(54, min(floor(cardw * 9 / 16), floor(avail / min(3, need)) - gap - 62));
		if (need * (thumbh + 62 + gap) - gap > avail) pagerh = 44;
	}
	cardh = thumbh + 62;
	rows = max(1, floor((avail - pagerh + gap) / (cardh + gap)));
	mt_maprows = rows * cols; MT_ClampPages();
	first = mt_mappage * mt_maprows; last = min(mt_nm, first + mt_maprows);
	for (i = first; i < last; i += 1)
	{
		row = i - first;
		p = [12 + (row - floor(row / cols) * cols) * (cardw + gap), top + floor(row / cols) * (cardh + gap)];
		if (MT_MapCard(p, [cardw, cardh], i, (mt_ok && myturn && MT_Map(i, 1) == "pool")))
			MT_Action(mt_turnkind, mt_id, "-", MT_Map(i, 0), 0);
	}
	if (mt_nm > mt_maprows)
	{
		p = [12, size_y - 40];
		if (MT_Button("mt_maps_prev", p, '104 30 0', "Previous", 0, mt_mappage > 0)) mt_mappage -= 1;
		if (MT_Button("mt_maps_next", p + '112 0 0', '84 30 0', "Next", 0, last < mt_nm)) mt_mappage += 1;
		MT_Place(p + '208 0 0', [size_x - 232, 30], sprintf("page %g of %g", mt_mappage + 1, ceil(mt_nm / mt_maprows)), 12, SUI_THEME_MUTED);
	}
};

void(vector p, vector size, string label, float idx, vector colour) MT_SchedRow =
{
	local float th, tw, x;
	local string info;
	sui_style_box(p, size, 8, SUI_THEME_CHIP, SUI_THEME_EDGE, 1);
	sui_fill(p + '0 8 0', [4, size_y - 16], colour, 1, 0);
	MT_Pill(p + [14, floor((size_y - 20) / 2)], label, colour);
	x = 110;
	if (idx < 0) { MT_Place(p + [x, 0], [size_x - x - 12, size_y], "Not drawn yet", 16, SUI_THEME_MUTED); return; }
	th = size_y - 12; tw = floor(th * 16 / 9);
	MT_Thumb(p + [x, 6], [tw, th], stof(MT_Map(idx, 3)), stof(MT_Map(idx, 4)), MT_Map(idx, 0));
	x += tw + 14;
	MT_Place(p + [x, floor(size_y / 2) - 24], [size_x - x - 12, 24], MT_Map(idx, 0), 20, SUI_THEME_TEXT);
	info = MT_Map(idx, 5);
	if (MT_Map(idx, 8) != "") info = strcat(info, "  |  ", MT_Map(idx, 8));
	if (MT_Map(idx, 7) != "") info = strcat(info, "  |  picked by ", MT_Map(idx, 7));
	MT_Place(p + [x, floor(size_y / 2) + 2], [size_x - x - 12, 18], info, 12, SUI_THEME_DIM);
};

void(vector size) MT_DrawSchedule =
{
	local float y, rh, r, i;
	local string banned;
	MT_Label('16 14 0', "schedule", 24, SUI_THEME_ACCENT, size_x - 230);
	MT_Place([size_x - 226, 12], '210 30 0', sprintf("%g round%s + reserve", mt_nsched, (mt_nsched == 1) ? "" : "s"), 12, SUI_THEME_DIM, 2);
	MT_Place('16 46 0', [size_x - 32, 18], MT_Summary(), 12, SUI_THEME_DIM);
	y = 74;
	rh = bound(56, floor((size_y - y - 40) / max(1, mt_nsched + 1)) - 8, 96);
	for (r = 0; r < mt_nsched; r += 1)
	{
		if (y + rh > size_y - 30) break;
		MT_SchedRow([12, y], [size_x - 24, rh], sprintf("ROUND %g", r + 1), mt_sched[r], SUI_THEME_ACCENT);
		y += rh + 8;
	}
	if (y + rh <= size_y - 30)
	{
		MT_SchedRow([12, y], [size_x - 24, rh], "RESERVE", mt_reserveidx, SUI_THEME_INFO);
		y += rh + 8;
	}
	banned = "";
	for (i = 0; i < mt_nm; i += 1)
		if (MT_Map(i, 1) == "banned") banned = strcat(banned, (banned == "") ? "Banned: " : ", ", MT_Map(i, 0));
	MT_Place([16, y], [size_x - 32, 18], banned, 12, SUI_THEME_MUTED);
};

// Room chat, word-wrapped with the drawn font once per change of lines or width.
string(float i, float field) MT_Chat = { return bufstr_get(mt_chat, i * MT_CHAT_FIELDS + field); };
void(float width) MT_WrapChat =
{
	local float i, previous, legacy, nw, w, cut, j, at, lo, hi, mid, first;
	local vector glyph;
	local string rest, line, prefix;
	if (mt_chatlines && mt_chatwrapgen == mt_chatgen && mt_chatwrapw == width) return;
	mt_chatwrapgen = mt_chatgen; mt_chatwrapw = width;
	if (!mt_chatlines) mt_chatlines = buf_create();
	mt_chatnl = 0;
	previous = ui_font_cur; Font_Set(ui_font_ui);
	legacy = drawfont; drawfont = Font_NativeSlot(legacy);
	glyph = sui_native_text_size(16);
	for (i = 0; i < mt_nchat; i += 1)
	{
		prefix = strcat(MT_Chat(i, 1), ": ");
		nw = ceil(stringwidth(prefix, TRUE, glyph));
		rest = MT_Chat(i, 2); w = max(40, width - nw); first = TRUE;
		while (rest != "" && mt_chatnl < 240)
		{
			if (stringwidth(rest, TRUE, glyph) <= w) { line = rest; rest = ""; }
			else
			{
				cut = 0; j = 0;
				while (TRUE)
				{
					at = strstrofs(rest, " ", j);
					if (at < 0) break;
					if (stringwidth(substring(rest, 0, at), TRUE, glyph) > w) break;
					cut = at; j = at + 1;
				}
				if (cut > 0) { line = substring(rest, 0, cut); rest = substring(rest, cut + 1, strlen(rest) - cut - 1); }
				else
				{
					// One word wider than the line: cut it at a character boundary.
					lo = 1; hi = strlen(rest);
					while (lo < hi)
					{
						mid = ceil((lo + hi) / 2);
						if (stringwidth(substring(rest, 0, UI_CharBytes(rest, mid)), TRUE, glyph) <= w) lo = mid;
						else hi = mid - 1;
					}
					cut = max(1, UI_CharBytes(rest, lo));
					// Never split a doubled caret: the half left on the next line would be a colour code.
					j = cut; at = 0;
					while (j > 0 && str2chr(rest, j - 1) == '^') { at += 1; j -= 1; }
					if (at & 1) cut = (cut > 1) ? cut - 1 : 2;
					line = substring(rest, 0, cut); rest = substring(rest, cut, strlen(rest) - cut);
				}
			}
			bufstr_set(mt_chatlines, mt_chatnl * 4, MT_Chat(i, 3));
			bufstr_set(mt_chatlines, mt_chatnl * 4 + 1, first ? prefix : "");
			bufstr_set(mt_chatlines, mt_chatnl * 4 + 2, first ? ftos(nw) : "0");
			bufstr_set(mt_chatlines, mt_chatnl * 4 + 3, line);
			// Continuation lines are indented so they never line up with a speaker's name.
			mt_chatnl += 1; first = FALSE; w = width - 14;
		}
	}
	drawfont = legacy; Font_Set(previous);
};

void() MT_ChatSend =
{
	local string text;
	local float n;
	text = strtrim(mt_chatdraft);
	if (text == "" || mt_id == "" || mt_started) return;
	// 180 bytes keep the escaped payload well inside the 2048-byte request.
	n = min(strlen(text), 180);
	if (n < strlen(text))
		while (n > 0 && (str2chr(text, n) & 192) == 128) n -= 1;
	MT_Request("say", mt_id, "-", "-", 0, -1, FALSE, substring(text, 0, n));
	mt_chatdraft = ""; mt_chatcursor = 0;
};

void(vector size) MT_DrawChat =
{
	local float top, fieldy, avail, lines, first, k, y, seat, nw;
	local vector colour;
	MT_Label('16 14 0', "room chat", 24, SUI_THEME_ACCENT, size_x - 32);
	fieldy = size_y - 48;
	ui_field("mt_chat_text", [16, fieldy], [size_x - 32 - 88, 34], mt_chatdraft, mt_chatcursor, mt_started ? "Chat closes at launch" : "Message the room...");
	if (MT_Button("mt_chat_send", [size_x - 96, fieldy], '80 34 0', MT_Busy("say") ? "..." : "Send", 0, (mt_ok && !mt_started && strlen(mt_chatdraft) > 0)))
		MT_ChatSend();
	top = 52; avail = fieldy - 10 - top;
	MT_WrapChat(size_x - 32);
	lines = max(0, floor(avail / 20));
	first = max(0, mt_chatnl - lines);
	y = top + avail - (mt_chatnl - first) * 20;
	for (k = first; k < mt_chatnl; k += 1)
	{
		seat = stof(bufstr_get(mt_chatlines, k * 4));
		colour = (seat >= 0) ? MT_SeatColour(seat) : SUI_THEME_DIM;
		nw = stof(bufstr_get(mt_chatlines, k * 4 + 2));
		if (nw > 0) MT_Place([16, y], [nw, 20], bufstr_get(mt_chatlines, k * 4 + 1), 16, colour);
		else nw = 14;
		MT_Place([16 + nw, y], [size_x - 32 - nw, 20], bufstr_get(mt_chatlines, k * 4 + 3), 16, SUI_THEME_TEXT);
		y += 20;
	}
	if (!mt_nchat) MT_Place([16, top], [size_x - 32, 20], "Say hi. Everyone in the room sees this, players and spectators.", 12, SUI_THEME_MUTED);
};

// What to do next, as one line: under the panels when the screen has room below
// the shell, otherwise beside the action buttons.
string mt_stext;
vector mt_scolour;
void() MT_Status =
{
	local float me, host, isplayer, myaccepted, myready, nacc, nready, i;
	host = (mt_me == mt_host); me = MT_MeIndex();
	isplayer = myaccepted = myready = FALSE;
	if (me >= 0)
	{
		isplayer = (MT_Player(me, 2) == "player");
		myaccepted = stof(MT_Player(me, 3)); myready = stof(MT_Player(me, 7));
	}
	nacc = nready = 0;
	for (i = 0; i < 8; i += 1)
		if (mt_seatof[i] >= 0)
		{
			if (stof(MT_Player(mt_seatof[i], 3))) nacc += 1;
			if (stof(MT_Player(mt_seatof[i], 7)))
			if (stof(MT_Player(mt_seatof[i], 8))) nready += 1;
		}
	mt_scolour = SUI_THEME_TEXT;
	if (mt_started)
	{
		mt_stext = (mt_launchmap != "") ? sprintf("Starting: the server is loading %s. Everyone joins automatically.", mt_launchmap)
			: "Starting: the server is getting ready. Everyone joins automatically.";
		// Back at the menu after the auto-connect (dropped, quit, or a refused connect).
		if (mt_launchaddr != "")
			mt_stext = isplayer ? "The tournament is running. Click Rejoin to get back on the server."
				: "The tournament is running. Click Watch on the server to spectate.";
		mt_scolour = SUI_THEME_GOOD;
	}
	else if (mt_phase == "lobby")
	{
		if (host)
		{
			mt_stext = "Everyone has accepted. Start the draft when you are ready.";
			if (nacc < mt_seated) mt_stext = sprintf("Waiting for %g of %g players to accept their seat.", mt_seated - nacc, mt_seated);
			if (mt_seated < 2) mt_stext = "Give someone a seat: the draft needs at least two players.";
		}
		else if (!isplayer) mt_stext = "You are spectating. The host can give you a seat.";
		else if (myaccepted) mt_stext = "You are in. Waiting for the host to start the draft.";
		else { mt_stext = "The host gave you a seat. Accept it to play."; mt_scolour = SUI_THEME_WARN; }
	}
	else if (mt_phase == "draft")
	{
		if (mt_turnwho == mt_me) { mt_stext = sprintf("Your turn: %s a map.", mt_turnkind); mt_scolour = SUI_THEME_FOCUS; }
		else mt_stext = sprintf("Waiting for %s to %s a map.", mt_turnname, mt_turnkind);
	}
	else
	{
		mt_stext = sprintf("%g of %g players ready.", nready, mt_seated);
		if (nready == mt_seated) mt_stext = host ? "Everyone is ready. Launch sends the whole group to one server." : "Everyone is ready. Waiting for the host to launch.";
		if (isplayer && !myready) mt_scolour = SUI_THEME_WARN;
	}
};

// The phase's buttons, right-aligned on a strip at the bottom of the panel the
// caller has pushed. draw FALSE only counts them, so the panel can reserve room.
float(vector size, float draw, float textinside) MT_Actions =
{
	local float i, me, host, isplayer, myaccepted, myready, nacc, nready, x, y, bw, n, rw;
	host = (mt_me == mt_host); me = MT_MeIndex();
	isplayer = myaccepted = myready = FALSE;
	if (me >= 0)
	{
		isplayer = (MT_Player(me, 2) == "player");
		myaccepted = stof(MT_Player(me, 3)); myready = stof(MT_Player(me, 7));
	}
	nacc = nready = 0;
	for (i = 0; i < 8; i += 1)
		if (mt_seatof[i] >= 0)
		{
			if (stof(MT_Player(mt_seatof[i], 3))) nacc += 1;
			if (stof(MT_Player(mt_seatof[i], 7)))
			if (stof(MT_Player(mt_seatof[i], 8))) nready += 1;
		}
	bw = bound(140, floor(size_x * 0.28), 200); x = size_x - 16; y = size_y - 50; n = 0;
	if (draw) sui_fill([16, size_y - 62], [size_x - 32, 1], SUI_THEME_EDGE, 1, 0);
	// Not gated on mt_ok: a stale snapshot must not keep anyone off the server.
	if (mt_started)
	if (mt_launchaddr != "")
	{
		rw = min(size_x - 32, 300);
		x -= rw; n += 1;
		if (draw)
		if (MT_Button("mt_rejoin", [x, y], [rw, 40], isplayer ? "Rejoin the tournament server" : "Watch on the server", 1))
			MT_Rejoin();
		x -= 10;
	}
	if (!mt_started)
	if (mt_phase == "lobby")
	{
		if (host)
		{
			x -= bw; n += 1;
			if (draw)
			if (MT_Button("mt_lock", [x, y], [bw, 40], MT_Busy("lock") ? "Starting..." : "Start draft", 1, (mt_ok && mt_seated >= 2 && nacc == mt_seated && !mt_dirty)))
				MT_Action("lock", mt_id, "-", "-", 0);
			x -= 10;
		}
		// The host's own seat is accepted automatically; the button is only the fallback.
		if (isplayer && !myaccepted && (!host || (mt_autoaccept == mt_revision && !MT_Busy("accept"))))
		{
			x -= bw; n += 1;
			if (draw)
			if (MT_Button("mt_accept", [x, y], [bw, 40], MT_Busy("accept") ? "Accepting..." : "Accept seat", host ? 0 : 1, mt_ok))
				MT_Action("accept", mt_id, "-", "-", 0);
			x -= 10;
		}
	}
	else if (mt_phase != "draft")
	{
		if (host)
		{
			x -= bw; n += 1;
			if (draw)
			if (MT_Button("mt_start", [x, y], [bw, 40], MT_Busy("start") ? "Launching..." : "Launch", 1, (mt_ok && mt_seated >= 2 && nready == mt_seated)))
				MT_Action("start", mt_id, "-", "-", 0);
			x -= 10;
		}
		if (isplayer)
		{
			x -= bw; n += 1;
			if (draw)
			if (MT_Button("mt_ready", [x, y], [bw, 40], myready ? "Not ready" : "I'm ready", myready ? 0 : 1, mt_ok))
				MT_Action("ready", mt_id, "-", "-", !myready);
			x -= 10;
		}
	}
	if (draw && textinside) MT_Place([18, y], [x - 24, 40], mt_stext, 16, mt_scolour);
	return n;
};

// Room space below the shell, in the shell's own (virtual) units.
float() MT_SpaceBelow =
{
	local vector origin, shell;
	origin = MH_ShellOrigin(sui_style_screen); shell = MH_ShellSize(sui_style_screen);
	return sui_style_screen_y - origin_y - shell_y;
};

void(vector scr) MT_DrawRoom =
{
	local float wide, lw, y0, bh, host, w3, below, strip, ph, chath, rh, unread, me, risky, armed, cw, sw, rulew, lines;
	local string label, code, warn;
	local vector size;
	host = (mt_me == mt_host);
	wide = (scr_x >= 820);
	MT_Status();
	below = (MT_SpaceBelow() >= 34);
	strip = (MT_Actions(scr, FALSE, FALSE) || !below) ? 64 : 0;
	// The browser row's code, for the host to read out.
	code = strcat("Room ", substring(mt_id, 0, 8));
	cw = ceil(MT_Width(code, 20, 0)) + 12;
	MT_Label('2 0 0', MT_RoomTitle(mt_name), wide ? 40 : 32, SUI_THEME_TEXT, scr_x - 184 - cw, 1);
	MT_Place([scr_x - 172 - cw, 4], [cw, 36], code, 20, SUI_THEME_ACCENT, 2);
	// Closing, or a seated player leaving once the draft has started, takes a second click
	// within 4 s: today's surfd aborts the tournament, P1650's resets it to the lobby.
	risky = host;
	me = MT_MeIndex();
	warn = "Click again to close the room for everyone.";
	if (host && mt_phase != "lobby") warn = "Click again to close the room. This ends the tournament for everyone.";
	if (!host && me >= 0 && mt_phase != "lobby")
	if (MT_Player(me, 2) == "player")
	{
		risky = TRUE;
		warn = mt_started ? "Click again to leave. Leaving now counts as dropping out of the tournament."
			: "Click again to leave. Leaving sends the room back to the lobby (or ends it on an older server).";
	}
	armed = (risky && time < mt_confirm);
	label = host ? (armed ? "Confirm close" : "Close room") : (armed ? "Confirm leave" : "Leave room");
	if (MT_Button("mt_leave", [scr_x - 160, 4], '160 36 0', label, armed ? 2 : 0))
	{
		if (risky && !armed)
		{
			mt_confirm = time + 4;
			MT_Note(warn); mt_notetime = time - 4; // the toast lasts as long as the window
		}
		else { mt_confirm = 0; MT_Action(host ? "cancel" : "leave", mt_id, "-", "-", 0); }
	}
	// The format in one line: beside the steps when it fits in two lines there, else under them.
	sw = min(scr_x - 4, 760); rulew = scr_x - sw - 22;
	MT_Steps('2 52 0', sw, MT_PhaseStep());
	lines = 3;
	if (rulew >= 240) lines = MT_Para('0 0 0', rulew, MT_RULE, 12, SUI_THEME_DIM, 3, FALSE);
	// The panels run to the bottom of the shell, level with the sidebar's chat.
	y0 = 94;
	if (lines <= 2) MT_Para([sw + 20, 66 - lines * 8], rulew, MT_RULE, 12, SUI_THEME_DIM, 2, TRUE);
	else y0 = 94 + MT_Para('2 86 0', scr_x - 4, MT_RULE, 12, SUI_THEME_DIM, 2, TRUE) * 16 + 4;
	bh = scr_y - y0;
	if (wide)
	{
		lw = bound(360, floor(scr_x * 0.38), 500);
		rh = (bh >= 760) ? 56 : 48;
		chath = bound(170, bh - MT_RosterHeight(rh) - 12, floor(bh * 0.5));
		ph = bh - chath - 12;
		sui_style_panel([0, y0], [lw, ph], 12, 1);
		sui_push_frame([0, y0], [lw, ph]); MT_DrawRoster([lw, ph]); sui_pop_frame();
		sui_style_panel([0, y0 + ph + 12], [lw, chath], 12, 1);
		sui_push_frame([0, y0 + ph + 12], [lw, chath]); MT_DrawChat([lw, chath]); sui_pop_frame();
		size = [scr_x - lw - 12, bh];
		sui_style_panel([lw + 12, y0], size, 12, 1);
		sui_push_frame([lw + 12, y0], size);
		if (mt_phase == "lobby") MT_DrawSettings([size_x, size_y - strip]);
		else if (mt_phase == "draft") MT_DrawDraft([size_x, size_y - strip]);
		else MT_DrawSchedule([size_x, size_y - strip]);
		if (strip) MT_Actions(size, TRUE, !below);
		sui_pop_frame();
	}
	else
	{
		// Narrow: Players | Settings/Draft/Schedule | Chat, the action strip on every tab.
		w3 = floor((scr_x - 16) / 3);
		if (mt_view == 2) mt_chatseen = mt_chatat;
		unread = (mt_chatat > mt_chatseen && mt_view != 2);
		if (MT_Button("mt_view_players", [0, y0], [w3, 34], sprintf("Players  %g/%g", mt_seated, mt_capacity), 0, TRUE, mt_view == 0)) mt_view = 0;
		label = "Schedule";
		if (mt_phase == "lobby") label = "Settings";
		if (mt_phase == "draft") label = "Map draft";
		if (MT_Button("mt_view_maps", [w3 + 8, y0], [w3, 34], label, 0, TRUE, mt_view == 1)) mt_view = 1;
		if (MT_Button("mt_view_chat", [2 * w3 + 16, y0], [scr_x - 2 * w3 - 16, 34], unread ? "Chat (new)" : "Chat", unread ? 3 : 0, TRUE, mt_view == 2)) mt_view = 2;
		size = [scr_x, bh - 42];
		sui_style_panel([0, y0 + 42], size, 12, 1);
		sui_push_frame([0, y0 + 42], size);
		if (mt_view == 0) MT_DrawRoster([size_x, size_y - strip]);
		else if (mt_view == 2) MT_DrawChat([size_x, size_y - strip]);
		else if (mt_phase == "lobby") MT_DrawSettings([size_x, size_y - strip]);
		else if (mt_phase == "draft") MT_DrawDraft([size_x, size_y - strip]);
		else MT_DrawSchedule([size_x, size_y - strip]);
		if (strip) MT_Actions(size, TRUE, !below);
		sui_pop_frame();
	}
	if (below) MT_Place([4, scr_y + 8], [scr_x - 8, 24], mt_stext, 16, mt_scolour);
};

float(float i, vector p, vector size, float clickable) MT_PoolRow =
{
	local string id;
	local float sel, hot, manual, th, tw, x;
	id = sprintf("mt_pool_map%g", i);
	manual = (mt_editpool != "-");
	sel = (manual && MT_InPool(mt_editpool, MT_Cat(i, 0)));
	if (clickable) sui_action_element(p, size, id, sui_noop);
	hot = (clickable && sui_is_hovered(id));
	sui_style_box(p, size, 8, sel ? SUI_THEME_SELECTED : (hot ? SUI_THEME_HOVER : SUI_THEME_CHIP), (hot || sel) ? SUI_THEME_ACCENT : SUI_THEME_EDGE, 1);
	x = 12;
	if (manual)
	{
		sui_style_box(p + [x, floor((size_y - 20) / 2)], '20 20 0', 5, sel ? SUI_THEME_ACCENT : SUI_THEME_WELL, sel ? SUI_THEME_ACCENT : SUI_THEME_EDGE_HI, 1);
		if (sel) sui_roundbox(p + [x + 6, floor((size_y - 20) / 2) + 6], '8 8 0', 2, SUI_THEME_WELL, 1);
		x += 32;
	}
	th = size_y - 12; tw = floor(th * 16 / 9);
	MT_Thumb(p + [x, 6], [tw, th], stof(MT_Cat(i, 3)), stof(MT_Cat(i, 4)), "");
	x += tw + 14;
	MT_Place(p + [x, 8], [size_x - x - 100, 22], MT_Cat(i, 0), 16, SUI_THEME_TEXT);
	MT_Place(p + [x, size_y - 28], [size_x - x - 100, 18], MT_Cat(i, 2), 12, SUI_THEME_DIM);
	MT_Pill(p + [size_x - 12, floor((size_y - 20) / 2)], MT_Cat(i, 1), SUI_THEME_ACCENT, TRUE);
	return (clickable && sui_is_released(id));
};

void(vector scr) MT_DrawPool =
{
	local vector p, size;
	local float edit, rows, i, y, ready, rh, need, segw, count;
	local string text;
	size = [min(scr_x - 24, 860), scr_y - 24]; p = [floor((scr_x - size_x) / 2), 12];
	edit = (mt_me == mt_host && mt_phase == "lobby");
	sui_push_frame(p, size);
	sui_roundbox('0 0 0', size, 12, MT_SOLID, 1);
	sui_style_panel('0 0 0', size, 12, 1);
	MT_Label('16 14 0', "map pool", 24, SUI_THEME_ACCENT, size_x - 260);
	if (edit)
	{
		if (MT_Button("mt_pool_done", [size_x - 112, 12], '96 32 0', "Done", 1))
		{
			if (strcmp(mt_editpool, mt_pool)) { MT_Set(mt_editpool, mt_pool); MT_Edit(); }
			mt_modal = 0; mt_catalogoffset = 0;
		}
		if (MT_Button("mt_pool_cancel", [size_x - 216, 12], '96 32 0', "Cancel")) { mt_modal = 0; mt_catalogoffset = 0; }
	}
	else if (MT_Button("mt_pool_done", [size_x - 112, 12], '96 32 0', "Close")) { mt_modal = 0; mt_catalogoffset = 0; }
	MT_Place('16 48 0', [size_x - 32, 18], sprintf("%s  |  %s  |  %s", MT_KindLabel(mt_kind), MT_TierLabel(mt_tiers), MT_ProfileLabel(mt_profile, mt_kind)), 12, SUI_THEME_DIM);
	segw = floor((size_x - 38) / 2);
	if (MT_Button("mt_pool_auto", '16 74 0', [segw, 36], "Auto: every matching map", 0, edit, mt_editpool == "-")) MT_Set("-", mt_editpool);
	if (MT_Button("mt_pool_manual", [22 + segw, 74], [segw, 36], "Manual: up to 24", 0, edit, mt_editpool != "-"))
		if (mt_editpool == "-") MT_Set("_", mt_editpool);
	need = 3 * max(2, mt_seated); count = MT_PoolCount(mt_editpool);
	ready = (mt_catalogfresh && !strcmp(MT_CatalogKey(), mt_catalogkey));
	if (ready) text = sprintf("%g qualified maps  |  %g not qualified yet  |  the draft needs %g", mt_catalogtotal, mt_unqualified, need);
	else text = (mt_catalogmsg != "") ? mt_catalogmsg : "Loading qualified maps...";
	MT_Place('16 118 0', [size_x - 32, 20], text, 16, ready ? SUI_THEME_TEXT : SUI_THEME_MUTED);
	if (mt_editpool == "-") text = "Auto drafts from every qualified map that matches. Switch to Manual to hand-pick.";
	else text = sprintf("%g of 24 picked. Click maps to add or remove them.", count);
	MT_Place('16 142 0', [size_x - 32, 18], text, 12, (mt_editpool != "-" && count < need) ? SUI_THEME_WARN : SUI_THEME_MUTED);
	y = 170; rh = 58;
	rows = bound(1, floor((size_y - y - 56) / (rh + 6)), 16);
	if (rows != mt_cataloglimit) { mt_cataloglimit = rows; mt_catalogoffset = 0; }
	if (ready)
	{
		for (i = 0; i < mt_catalogcount; i += 1)
		{
			if (MT_PoolRow(i, [16, y], [size_x - 32, rh], (edit && mt_editpool != "-"))) MT_ToggleMap(MT_Cat(i, 0));
			y += rh + 6;
		}
		if (!mt_catalogtotal) MT_Place([16, y], [size_x - 32, 22], "No qualified maps match. Try more tiers or Default movement.", 16, SUI_THEME_WARN);
	}
	y = size_y - 46;
	if (MT_Button("mt_pool_prev", [16, y], '104 32 0', "Previous", 0, mt_catalogoffset > 0)) mt_catalogoffset = max(0, mt_catalogoffset - mt_cataloglimit);
	if (MT_Button("mt_pool_next", [128, y], '84 32 0', "Next", 0, (ready && mt_catalogoffset + mt_cataloglimit < mt_catalogtotal))) mt_catalogoffset += mt_cataloglimit;
	if (ready && mt_catalogtotal)
		MT_Place([224, y], [200, 32], sprintf("%g-%g of %g", mt_catalogoffset + 1, min(mt_catalogtotal, mt_catalogoffset + mt_cataloglimit), mt_catalogtotal), 12, SUI_THEME_MUTED);
	if (MT_Button("mt_pool_refresh", [size_x - 126, y], '110 32 0', "Refresh")) { mt_catalogfresh = 0; mt_catalognext = 0; }
	sui_pop_frame();
};

// n 0 draws no number badge; the body wraps to two lines.
void(vector p, vector size, float n, string title, string body) MT_HowCard =
{
	local float x, top, lines;
	sui_style_box(p, size, 10, SUI_THEME_PANEL, SUI_THEME_EDGE, 1);
	x = 16;
	if (n > 0)
	{
		sui_style_box(p + [14, floor((size_y - 28) / 2)], '28 28 0', 14, SUI_THEME_PANEL * 0.6 + SUI_THEME_ACCENT * 0.3, SUI_THEME_ACCENT, 1);
		MT_Place(p + [14, floor((size_y - 28) / 2)], '28 28 0', ftos(n), 16, SUI_THEME_ACCENT, 1);
		x = 54;
	}
	lines = MT_Para('0 0 0', size_x - x - 12, body, 12, SUI_THEME_DIM, 2, FALSE);
	top = floor((size_y - 22 - lines * 16) / 2);
	MT_Place(p + [x, top], [size_x - x - 12, 20], title, 16, SUI_THEME_TEXT);
	MT_Para(p + [x, top + 22], size_x - x - 12, body, 12, SUI_THEME_DIM, 2, TRUE);
};

void(vector scr) MT_DrawBrowser =
{
	local float y, i, rh, top, ph, howh, ruleh, w, statw, playw, joinw, first, last, namew, cw, lines, lh, started;
	local string phase, label, text;
	local vector colour, p;
	MT_Label('2 0 0', "Tournaments", (scr_x >= 820) ? 40 : 32, SUI_THEME_TEXT, scr_x - 250, 1);
	if (MT_Button("mt_new", [scr_x - 220, 4], '220 40 0', MT_Busy("create") ? "Creating..." : "Host a tournament", 1, (mt_ok || !mt_fresh)))
		MT_Action("create", "-", "-", "-", 0);
	MT_Place('2 52 0', [scr_x - 4, 22], "Everyone gathers in a room first. The host sets the rules, you draft maps together, then one click sends the whole group to a server.", 16, SUI_THEME_DIM);
	top = 88;
	// surfd refused this install as unlinked: the existing Steam sign-in (m_main.qc screen_steam).
	if (mt_needlink)
	{
		text = "You join a lobby, sign in on Steam's page in your browser, then type the number it shows back into the game. Then leave the lobby and come back here.";
		lines = MT_Para('0 0 0', scr_x - 236, text, 12, SUI_THEME_DIM, 2, FALSE);
		lh = 44 + lines * 16;
		sui_style_box([0, top], [scr_x, lh], 10, SUI_THEME_PANEL * 0.75 + SUI_THEME_WARN * 0.12, SUI_THEME_PANEL * 0.3 + SUI_THEME_WARN * 0.7, 1);
		MT_Place([16, top + 10], [scr_x - 236, 22], "Link your Steam account to play tournaments.", 16, SUI_THEME_WARN);
		MT_Para([16, top + 34], scr_x - 236, text, 12, SUI_THEME_DIM, 2, TRUE);
		if (MT_Button("mt_link", [scr_x - 196, top + floor((lh - 40) / 2)], '180 40 0', "Link Steam", 1))
		{
			// The lobby's Enter prompt comes once a game (cl_account.qc _acct_prompted); this click asks for it.
			localcmd("set _acct_prompted 0\n");
			ui_steam_t0 = time; menu_screen = SCREEN_STEAM;
		}
		top += lh + 12;
	}
	howh = (scr_x >= 820 && scr_y >= 560) ? 76 : 0;
	ruleh = (scr_y >= 520) ? 56 : 0;
	ph = scr_y - top - (howh ? howh + 12 : 0) - (ruleh ? ruleh + 12 : 0);
	sui_push_frame([0, top], [scr_x, ph]);
	sui_style_panel('0 0 0', [scr_x, ph], 12, 1);
	MT_Label('16 14 0', "open rooms", 24, SUI_THEME_ACCENT, scr_x - 160);
	if (MT_Button("mt_refresh", [scr_x - 126, 12], '110 30 0', "Refresh")) { mt_dirnext = 0; mt_next = 0; }
	w = scr_x - 24; joinw = 120; statw = 130; playw = (w >= 600) ? 140 : 0;
	namew = w - joinw - statw - playw - 48;
	MT_Place('28 54 0', [namew, 16], "ROOM", 12, SUI_THEME_MUTED);
	if (playw) MT_Place([28 + namew + 8, 54], [playw, 16], "PLAYERS", 12, SUI_THEME_MUTED);
	MT_Place([28 + namew + 8 + playw, 54], [statw, 16], "STATUS", 12, SUI_THEME_MUTED);
	y = 76; rh = 60;
	mt_dirrows = max(1, floor((ph - y - 52) / (rh + 8)));
	MT_ClampPages();
	if (!mt_dirloaded) MT_Place([12, y], [w, ph - y - 52], "Looking for rooms...", 16, SUI_THEME_MUTED, 1);
	else if (!mt_enabled) MT_Place([12, y], [w, ph - y - 52], "Tournaments are switched off on the server right now.", 16, SUI_THEME_WARN, 1);
	else if (!mt_nd)
	{
		MT_Place([12, y + floor((ph - y - 52) / 2) - 28], [w, 26], "No open rooms yet", 20, SUI_THEME_TEXT, 1);
		MT_Place([12, y + floor((ph - y - 52) / 2) + 2], [w, 22], "Host one and it shows up here for your friends.", 16, SUI_THEME_DIM, 1);
	}
	first = mt_dirpage * mt_dirrows; last = min(mt_nd, first + mt_dirrows);
	for (i = first; i < last; i += 1)
	{
		p = [12, y];
		phase = MT_Dir(i, 4);
		sui_style_box(p, [w, rh], 8, SUI_THEME_CHIP, SUI_THEME_EDGE, 1);
		MT_Place(p + '16 8 0', [namew, 26], MT_RoomTitle(MT_Dir(i, 6)), 20, SUI_THEME_TEXT);
		MT_Place(p + '16 36 0', [namew, 16], strcat("room ", substring(MT_Dir(i, 0), 0, 8)), 12, SUI_THEME_MUTED);
		if (playw)
		{
			MT_Place(p + [16 + namew + 8, 8], [playw, 26], sprintf("%s in room", MT_Dir(i, 3)), 16, SUI_THEME_TEXT);
			MT_Place(p + [16 + namew + 8, 36], [playw, 16], sprintf("%s seats", MT_Dir(i, 2)), 12, SUI_THEME_DIM);
		}
		label = "IN GAME"; colour = SUI_THEME_MUTED;
		if (phase == "lobby") { label = "OPEN"; colour = SUI_THEME_GOOD; }
		if (phase == "draft") { label = "DRAFTING"; colour = SUI_THEME_INFO; }
		if (phase == "loading") { label = "READY CHECK"; colour = SUI_THEME_WARN; }
		MT_Pill(p + [16 + namew + 8 + playw, floor((rh - 20) / 2)], label, colour);
		started = (phase != "lobby");
		if (MT_Button(sprintf("mt_join%g", i), p + [w - joinw - 12, floor((rh - 36) / 2)], [joinw, 36], started ? "Watch" : "Join", started ? 3 : 1, !MT_Busy("join")))
			MT_Connect(i);
		if (started) sui_tooltip_for(sprintf("mt_join%g", i), "Join as a spectator.", 2);
		y += rh + 8;
	}
	if (mt_nd > mt_dirrows)
	{
		y = ph - 44;
		if (MT_Button("mt_prev", [12, y], '104 30 0', "Previous", 0, mt_dirpage > 0)) mt_dirpage = max(0, mt_dirpage - 1);
		if (MT_Button("mt_next", [124, y], '84 30 0', "Next", 0, last < mt_nd)) mt_dirpage = min(floor((mt_nd - 1) / mt_dirrows), mt_dirpage + 1);
	}
	sui_pop_frame();
	y = top + ph + 12;
	if (howh)
	{
		cw = floor((scr_x - 24) / 3);
		MT_HowCard([0, y], [cw, howh], 1, "Lobby", "The host sets the rules; players take seats.");
		MT_HowCard([cw + 12, y], [cw, howh], 2, "Map draft", "Everyone bans a map, then picks one.");
		MT_HowCard([2 * cw + 24, y], [scr_x - 2 * cw - 24, howh], 3, "Launch", "One click sends the whole group to a server.");
		y += howh + 12;
	}
	if (ruleh) MT_HowCard([0, y], [scr_x, ruleh], howh ? 4 : 0, "Rounds", MT_RULE);
};

void(vector scr, float bottom) MT_DrawToast =
{
	local string text;
	local vector colour, p;
	local float w, h;
	text = ""; colour = SUI_THEME_WARN;
	if (mt_note != "" && time - mt_notetime < 8) text = mt_note;
	else if (mt_req && mt_userop) { text = "Sending..."; colour = SUI_THEME_DIM; }
	else if (mt_id != "" && !mt_ok) { text = "Reconnecting to the tournament service..."; colour = SUI_THEME_DIM; }
	if (text == "") return;
	// Two lines on a narrow screen rather than cutting off the next step.
	w = min(scr_x - 24, ceil(MT_Width(text, 16, 0)) + 36);
	h = 14 + 20 * MT_Para('0 0 0', w - 36, text, 16, colour, 2, FALSE);
	p = [floor((scr_x - w) / 2), bottom - 6 - h];
	sui_style_box(p, [w, h], 10, SUI_THEME_PANEL * 0.75 + colour * 0.12, SUI_THEME_PANEL * 0.3 + colour * 0.7, 1);
	MT_Para(p + '18 7 0', w - 36, text, 16, colour, 2, TRUE);
};

void(vector scr, string title, string body) MT_DrawMessage =
{
	MT_Label('2 0 0', "Tournaments", (scr_x >= 820) ? 40 : 32, SUI_THEME_TEXT, scr_x - 4, 1);
	sui_push_frame('0 88 0', [scr_x, 150]);
	sui_style_panel('0 0 0', [scr_x, 150], 12, 1);
	MT_Label('16 14 0', title, 24, SUI_THEME_ACCENT, scr_x - 32);
	MT_Place('16 52 0', [scr_x - 32, 22], body, 16, SUI_THEME_DIM);
	sui_pop_frame();
};

void(vector scr) MT_Draw =
{
	local float acts;
	mt_fit_used = 0;
	MT_Frame();
	mt_ok = (mt_fresh && time - mt_fresh < 12);
	if (clientstate() != 1)
	{
		MT_DrawMessage(scr, "You are in a game", "Press F6 for tournament controls while you are in a game.");
		return;
	}
	if (ms_consent < FS_TERMS_ONLINE)
	{
		MT_DrawMessage(scr, "Online terms needed", "Tournaments use the online service. Read and accept the online terms to continue.");
		if (MT_Button("mt_terms", '16 186 0', '220 36 0', "Read online terms", 1)) menu_screen = SCREEN_TERMS;
		return;
	}
	if (mt_id == "")
	{
		mt_modal = 0;
		MT_DrawBrowser(scr);
		MT_DrawToast(scr, scr_y - 88);
		return;
	}
	acts = _action_elements_index;
	MT_DrawRoom(scr);
	MT_DrawToast(scr, scr_y - 72);
	if (mt_modal)
	{
		// The room stays drawn but is struck from sui's hit list under the dialog.
		_action_elements_index = acts;
		sui_fill('0 0 0', scr, '0 0 0', 0.7, 0);
		MT_DrawPool(scr);
	}
};

// Escape closes a dialog before it leaves the page.
float() MT_Esc =
{
	if (menu_screen != SCREEN_TOURNAMENT || !mt_modal) return FALSE;
	mt_modal = 0; mt_catalogoffset = 0;
	return TRUE;
};

// The tab bar asks before drawing TOURNAMENT (m_home.qc).
float() MT_TabVisible = { return mt_enabled == 1 || mt_id != "" || cvar("ui_tournament_tab") != 0; };
