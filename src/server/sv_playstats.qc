// P1171: consented official-lobby clock, independent of movement/run evidence.
// Durable cumulative outbox carries no capability. Current linked sessions retry it.
// One folder per owner keeps each retry's listing to that player's own files.
#define PS_MAX 16777215
#define PS_FLIGHTS 8            // the engine has 32 download slots for every feature
#define PS_PERIOD 30            // seconds between saves/sends; leaving and map change flush
.float ps_live, ps_paused, ps_last, ps_fraction, ps_seconds, ps_next, ps_tick;
.string ps_stream, ps_owner;
float *ps_attempts;
float ps_hold;                  // no sends before this: the backend failed or timed out
float ps_req[PS_FLIGHTS];
float ps_sent[PS_FLIGHTS];
string ps_path[PS_FLIGHTS];
string ps_hash[PS_FLIGHTS];

string() PlayStats_Dir = { return sprintf("data/playstats-server1/p%g/", cvar("sv_port")); };
string(entity e) PlayStats_Owner = { return strcat(e.acct_who, ".", e.ps_binding); };
string(entity e) PlayStats_Path = { return strcat(PlayStats_Dir(), e.ps_owner, "/", e.ps_stream, ".act"); };

float(string map) PlayStats_MapValid =
{
	local float i, c;
	if (strlen(map) < 1 || strlen(map) > 64 || strstrofs(map, "..", 0) >= 0) return FALSE;
	for (i = 0; i < strlen(map); i = i + 1)
	{
		c = str2chr(map, i);
		if ((c >= 48 && c <= 57) || (c >= 97 && c <= 122)) continue;
		if (i == 0 || (c != 95 && c != 46 && c != 43 && c != 45)) return FALSE;
	}
	return TRUE;
};

string(string path) PlayStats_Read =
{
	local float f;
	local string header, body, hash, end;
	f = fopen(path, FILE_READ);
	if (f < 0) return "";
	header = fgets(f); body = fgets(f); hash = fgets(f); end = fgets(f);
	fclose(f);
	if (strcmp(header, "FTESURF-SERVER-ACTIVITY 1") || strcmp(end, "end")) return "";
	if (strlen(body) > 1024 || strcmp(hash, digest_hex("SHA256", body))) return "";
	return body;
};

void(float i) PlayStats_FlightDrop =
{
	if (strlen(ps_path[i])) strunzone(ps_path[i]);
	if (strlen(ps_hash[i])) strunzone(ps_hash[i]);
	ps_path[i] = ps_hash[i] = "";
	ps_req[i] = ps_sent[i] = 0;
};

void(entity e) PlayStats_Clear =
{
	local float slot, t;
	if (strlen(e.ps_stream)) strunzone(e.ps_stream);
	if (strlen(e.ps_owner)) strunzone(e.ps_owner);
	e.ps_stream = e.ps_owner = "";
	e.ps_live = e.ps_paused = e.ps_last = e.ps_fraction = e.ps_seconds = e.ps_next = 0;
	slot = num_for_edict(e) - 1;
	if (ps_attempts && slot >= 0 && slot < 64)
		for (t = 0; t < 12; t = t + 1) ps_attempts[slot * 12 + t] = 0;
};

float(entity e) PlayStats_Allowed =
{
	if (!Account_On() || !Lobby_Active()) return FALSE;
	if (e.acct_state != ACCT_LINKED || e.run_t_terms != FS_TERMS_ONLINE) return FALSE;
	if (!SV_RecIsHex(e.social_token, 64) || !SV_RecIsHex(e.ps_binding, 32)) return FALSE;
	return SV_RecIsHex(e.acct_who, 8) || SV_RecIsHex(e.acct_who, 12);
};

void(entity e) PlayStats_Advance =
{
	local float now, dt, whole;
	now = gettime(1);
	dt = now - e.ps_last;
	e.ps_last = now;
	if (dt < 0) return;
	e.ps_fraction = e.ps_fraction + dt;
	whole = floor(e.ps_fraction);
	e.ps_fraction = e.ps_fraction - whole;
	e.ps_seconds = min(PS_MAX, e.ps_seconds + whole);
};

void(entity e) PlayStats_Begin =
{
	local float slot;
	slot = num_for_edict(e) - 1;
	if (slot < 0 || slot >= 64) return;
	if (!ps_attempts) ps_attempts = memalloc(sizeof(float) * 64 * 12);
	e.ps_stream = strzone(SV_RandHex(16));
	e.ps_owner = strzone(PlayStats_Owner(e));
	e.ps_live = TRUE;
	e.ps_paused = FALSE;
	e.ps_last = gettime(1);
	e.ps_seconds = e.ps_fraction = 0;
	e.ps_next = e.ps_last + 10 + (slot - floor(slot / 20) * 20);   // spread a map's arrivals
};

string(entity e) PlayStats_Snapshot =
{
	local string attempts;
	local float slot, t, n;
	attempts = "";
	slot = num_for_edict(e) - 1;
	for (t = 0; t < 12; t = t + 1)
	{
		n = ps_attempts[slot * 12 + t];
		if (n > 0) attempts = strcat(attempts, !strlen(attempts) ? "" : ",", sprintf("%d:0:%d", t, n));
	}
	return sprintf("{\"owner\":\"%s\",\"binding\":\"%s\",\"stream\":\"%s\",\"map\":\"%s\",\"seconds\":%d,\"attempts\":\"%s\"}",
		e.ps_owner, e.ps_binding, e.ps_stream, mapname, e.ps_seconds, attempts);
};

float(entity e) PlayStats_Save =
{
	local float f;
	local string path, part, old, body;
	if (!e.ps_live || !PlayStats_MapValid(mapname)) return FALSE;
	path = PlayStats_Path(e); part = strcat(path, ".new"); old = strcat(path, ".prev");
	body = PlayStats_Snapshot(e);
	f = fopen(part, FS_FILE_WRITESTREAM);    // creates the folder; no COM_WriteFile log line
	if (f < 0) return FALSE;
	fputs(f, "FTESURF-SERVER-ACTIVITY 1\n", body, "\n", digest_hex("SHA256", body), "\nend\n");
	fclose(f);
	if (strcmp(PlayStats_Read(part), body)) return FALSE;
	// Keep the last good snapshot until the new sealed file has landed.
	if (strlen(PlayStats_Read(path)))
	{
		fremove(old);
		if (frename(path, old) != 0) return FALSE;
	}
	if (frename(part, path) != 0) return FALSE;
	if (strcmp(PlayStats_Read(path), body)) return FALSE;
	fremove(old);
	return TRUE;
};

void(entity e, string path) PlayStats_Send =
{
	local float i, free, seconds;
	local int root;
	local string body, owner, stream, map, attempts, form;
	if (gettime(1) < ps_hold) return;
	body = PlayStats_Read(path);
	if (!strlen(body)) return;
	free = -1;
	for (i = 0; i < PS_FLIGHTS; i = i + 1)
	{
		// The engine may still hold a dropped request: back off before reusing its slot.
		if (ps_req[i] && gettime(1) - ps_sent[i] >= 15) { PlayStats_FlightDrop(i); ps_hold = gettime(1) + 30; }
		if (ps_req[i] && !strcmp(ps_path[i], path)) return;
		if (!ps_req[i]) free = i;
	}
	if (free < 0 || gettime(1) < ps_hold) return;
	root = json_parse(body);
	if (!root) return;
	owner = json_get_string(json_find_object_child(root, "owner"));
	stream = json_get_string(json_find_object_child(root, "stream"));
	map = json_get_string(json_find_object_child(root, "map"));
	seconds = json_get_float(json_find_object_child(root, "seconds"));
	attempts = json_get_string(json_find_object_child(root, "attempts"));
	form = "";
	if (!strcmp(owner, PlayStats_Owner(e)))
	if (SV_RecIsHex(stream, 32) && PlayStats_MapValid(map))
	if (seconds >= 0 && seconds <= PS_MAX && seconds == floor(seconds))
	{
		form = strcat(Social_Form(), "&consent=", ftos(FS_TERMS_ONLINE), "&token=", e.social_token, "&binding=", e.ps_binding);
		form = strcat(form, "&stream=", stream, "&map=", uri_escape(map));
		form = strcat(form, sprintf("&seconds=%d", seconds), "&attempts=", uri_escape(attempts));
	}
	json_free(root);
	if (!strlen(form)) return;
	ps_req[free] = Account_NextId(); ps_sent[free] = gettime(1);
	ps_path[free] = strzone(path); ps_hash[free] = strzone(digest_hex("SHA256", body));
	if (!uri_post(strcat(cvar_string("lobby_master"), "/api/social/playstats"), ps_req[free],
		"application/x-www-form-urlencoded", form)) PlayStats_FlightDrop(free);
};

void(entity e) PlayStats_Retry =
{
	local searchhandle h;
	local float i, n;
	local string path;
	if (gettime(1) < ps_hold) return;
	h = search_begin(strcat(PlayStats_Dir(), PlayStats_Owner(e), "/*.act*"), 0, TRUE);
	if (h < 0) return;
	n = min(8, search_getsize(h));
	for (i = 0; i < n; i = i + 1)
	{
		path = search_getfilename(h, i);
		if (!strcmp(substring(path, strlen(path) - 4, 4), ".act") ||
			!strcmp(substring(path, strlen(path) - 9, 9), ".act.prev") ||
			!strcmp(substring(path, strlen(path) - 8, 8), ".act.new"))
			PlayStats_Send(e, path);
	}
	search_end(h);
};

void(entity e) PlayStats_Leaving =
{
	if (e.ps_live)
	{
		if (PlayStats_Allowed(e) && !e.ps_paused) PlayStats_Advance(e);
		if (PlayStats_Save(e)) PlayStats_Send(e, PlayStats_Path(e));
	}
};

// Same identity keeps its stream through a paused answer; a new one ends it.
void(entity e) PlayStats_Resume =
{
	if (e.ps_live && strcmp(e.ps_owner, PlayStats_Owner(e))) { PlayStats_Leaving(e); PlayStats_Clear(e); }
	if (!e.ps_live) PlayStats_Begin(e);
	if (e.ps_live && e.ps_paused) { e.ps_paused = FALSE; e.ps_last = gettime(1); }
};

// Counted in memory; the periodic save or leaving writes it (no file per start).
void(entity e, float track, float leg) PlayStats_Attempt =
{
	local float slot;
	if (leg != 0 || track < 0 || track >= 12 || track != floor(track)) return;
	if (!PlayStats_Allowed(e)) return;
	PlayStats_Resume(e);
	if (!e.ps_live) return;
	slot = (num_for_edict(e) - 1) * 12 + track;
	ps_attempts[slot] = min(PS_MAX, ps_attempts[slot] + 1);
};

float(float reqid, float code, string body) PlayStats_Reply =
{
	local float i, ok, same;
	local int root;
	local string current;
	for (i = 0; i < PS_FLIGHTS; i = i + 1)
	if (ps_req[i] == reqid && reqid > 0)
	{
		root = json_parse(body);
		ok = FALSE;
		if (root) ok = (!code && json_get_float(json_find_object_child(root, "ok")));
		if (root) json_free(root);
		current = PlayStats_Read(ps_path[i]);
		same = (strlen(current) && !strcmp(digest_hex("SHA256", current), ps_hash[i]));
		// 400 refuses this snapshot for good (stream, map or binding); 403 is the
		// player's own session; anything else is the backend, so everyone waits.
		if (same && (ok || code == 400)) fremove(ps_path[i]);
		if (!ok && code != 400 && code != 403) ps_hold = gettime(1) + 30;
		PlayStats_FlightDrop(i);
		return TRUE;
	}
	return FALSE;
};

void() PlayStats_Frame =
{
	local entity e;
	local float now;
	now = gettime(1);
	e = world;
	while ((e = findfloat(e, acct_here, TRUE)))
	{
		if (now < e.ps_tick) continue;           // once a second per player
		e.ps_tick = now + 1;
		if (!PlayStats_Allowed(e))
		{
			// Pause, do not end: a toggled answer must not mint new streams.
			if (e.ps_live && !e.ps_paused) { PlayStats_Leaving(e); e.ps_paused = TRUE; }
			continue;
		}
		PlayStats_Resume(e);
		if (!e.ps_live) continue;
		PlayStats_Advance(e);
		if (now < e.ps_next) continue;
		e.ps_next = now + PS_PERIOD;
		PlayStats_Save(e);
		PlayStats_Retry(e);
	}
};
