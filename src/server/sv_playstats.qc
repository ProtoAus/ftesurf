/* Steam-linked lobby activity. Real elapsed seconds, never run-clock ticks.
   Counters deliberately live outside save/load/rewind state. A connection/map
   owns a random stream; the directory merges cumulative watermarks on retries.
   Only social_token's proven capability attaches activity to an account.
   Scope: connected linked lobbies, including observers; no menu/offline claim.
   Final tails retry in a bounded detached queue while this VM lives. Process
   crashes/map shutdown can lose unacknowledged tails (normally <=30 seconds). */
#define PS_LEGS (FS_MAXTRACKS * FS_MAXSPLITS)
#define PS_CLOSING 64
.float ps_live, ps_last, ps_seconds, ps_fraction, ps_next, ps_req, ps_sent, ps_stage_begun;
.string ps_stream, ps_who;
float *ps_attempts;
string ps_close_form[PS_CLOSING], ps_close_url[PS_CLOSING];
float ps_close_req[PS_CLOSING], ps_close_next[PS_CLOSING];

float(entity e) PlayStats_Base =
{
	local float slot;
	slot = num_for_edict(e) - 1;
	if (slot < 0 || slot >= 64) return -1;
	return slot * PS_LEGS;
};

void(entity e) PlayStats_Connect =
{
	local float base, i;

	if (!ps_attempts) ps_attempts = memalloc(sizeof(float) * 64 * PS_LEGS);
	if (e.ps_stream != "") strunzone(e.ps_stream);
	e.ps_stream = strzone(SV_RandHex(16));
	e.ps_live = TRUE;
	e.ps_last = gettime();
	e.ps_seconds = e.ps_fraction = e.ps_req = e.ps_stage_begun = 0;
	if (e.ps_who != "") strunzone(e.ps_who);
	e.ps_who = "";
	e.ps_next = e.ps_last + 30;
	base = PlayStats_Base(e);
	if (base < 0) return;
	for (i = 0; i < PS_LEGS; i = i + 1) ps_attempts[base + i] = 0;
};

void(entity e, float track, float leg) PlayStats_Attempt =
{
	local float base, at;

	if (!e.ps_live || !ps_attempts) return;
	if (track < 0 || track >= FS_MAXTRACKS || track != floor(track)) return;
	if (leg < 0 || leg >= FS_MAXSPLITS || leg != floor(leg)) return;
	base = PlayStats_Base(e);
	if (base < 0) return;
	at = base + track * FS_MAXSPLITS + leg;
	ps_attempts[at] = min(16777215, ps_attempts[at] + 1);
};

void(entity e) PlayStats_StageReset = { e.ps_stage_begun = FALSE; };
void(entity e, float track, float leg) PlayStats_Stage =
{
	if (e.ps_stage_begun) return;
	PlayStats_Attempt(e, track, leg);
	e.ps_stage_begun = TRUE;
};

void(entity e) PlayStats_Sample =
{
	local float now, dt;

	if (!e.ps_live) return;
	now = gettime();
	dt = now - e.ps_last;
	e.ps_last = now;
	// A backwards clock or suspended server is not observed playing time.
	if (dt > 0 && dt < 60)
	{
		dt = dt + e.ps_fraction;
		e.ps_seconds = min(16777215, e.ps_seconds + floor(dt));
		e.ps_fraction = dt - floor(dt);
	}
};

string(entity e) PlayStats_Body =
{
	local float base, i, n;
	local string attempts, form;

	PlayStats_Sample(e);
	if (!e.ps_live || !Account_On() || !e.social_here) return "";
	base = PlayStats_Base(e);
	if (base < 0) return "";
	attempts = "";
	for (i = 0; i < PS_LEGS; i = i + 1)
	{
		n = ps_attempts[base + i];
		if (n > 0) attempts = strcat(attempts, attempts == "" ? "" : ",",
			sprintf("%d:%d:%d", floor(i / FS_MAXSPLITS), i % FS_MAXSPLITS, n));
	}
	// Numeric colon/comma counters need no escaping; escaping a dense snapshot
	// exceeds uri_escape's 8192-byte buffer. Variable text is escaped.
	form = strcat(Social_Form(), "&token=", e.social_token,
		"&stream=", e.ps_stream, "&map=", uri_escape(strtolower(mapname)));
	return strcat(form, sprintf("&seconds=%d&attempts=", floor(e.ps_seconds)), attempts);
};

void(float at) PlayStats_CloseSend =
{
	local float now;
	now = gettime();
	if (ps_close_form[at] == "" || now < ps_close_next[at]) return;
	ps_close_req[at] = Account_NextId();
	ps_close_next[at] = now + 15;
	if (!uri_post(ps_close_url[at], ps_close_req[at], "application/x-www-form-urlencoded", ps_close_form[at]))
		ps_close_req[at] = 0;
};

void(entity e) PlayStats_Disconnect =
{
	local float i;
	local string form;

	form = PlayStats_Body(e);
	if (form != "")
	{
		for (i = 0; i < PS_CLOSING; i = i + 1)
			if (ps_close_form[i] == "") break;
		if (i < PS_CLOSING)
		{
			ps_close_form[i] = strzone(form);
			ps_close_url[i] = strzone(strcat(cvar_string("lobby_master"), "/api/social/playstats"));
			ps_close_req[i] = ps_close_next[i] = 0;
			PlayStats_CloseSend(i);
		}
		else print("playstats: closing queue full; unsent activity tail could not be retained\n");
	}
	e.ps_live = FALSE;
	e.ps_req = 0;
	if (e.ps_stream != "") strunzone(e.ps_stream);
	e.ps_stream = "";
	if (e.ps_who != "") strunzone(e.ps_who);
	e.ps_who = "";
};

void(entity e, string who) PlayStats_Bind =
{
	if (e.ps_who != "" && e.ps_who != who)
	{
		PlayStats_Disconnect(e);
		PlayStats_Connect(e);
	}
	if (e.ps_who != "") strunzone(e.ps_who);
	e.ps_who = strzone(who);
};

void(entity e) PlayStats_Send =
{
	local float now;
	local string form;

	PlayStats_Sample(e);
	if (!e.ps_live || !Account_On() || !e.social_here) return;
	now = gettime();
	if (now < e.ps_next || (e.ps_req && now - e.ps_sent < 15)) return;
	form = PlayStats_Body(e);
	if (form == "") return;
	e.ps_req = Account_NextId();
	e.ps_sent = now;
	e.ps_next = now + 30;
	if (!uri_post(strcat(cvar_string("lobby_master"), "/api/social/playstats"), e.ps_req,
		"application/x-www-form-urlencoded", form)) e.ps_req = 0;
};

float(float reqid, float code, string body) PlayStats_Reply =
{
	local entity e;
	local float i, ok;
	local int root;

	for (i = 0; i < PS_CLOSING; i = i + 1)
	if (ps_close_req[i] == reqid && reqid > 0)
	{
		ps_close_req[i] = 0;
		root = json_parse(body);
		ok = !code && json_get_float(json_find_object_child(root, "ok"));
		if (root) json_free(root);
		if (ok || code == 403)
		{
			// Revocation must not be bypassed to rescue an unacknowledged tail.
			if (!ok) print("playstats: account proof revoked; closing tail was not credited\n");
			strunzone(ps_close_form[i]);
			strunzone(ps_close_url[i]);
			ps_close_form[i] = ps_close_url[i] = "";
		}
		else ps_close_next[i] = gettime() + 10;
		return TRUE;
	}
	e = findfloat(world, ps_req, reqid);
	if (!e) return FALSE;
	e.ps_req = 0;
	root = json_parse(body);
	if (code || !json_get_float(json_find_object_child(root, "ok")))
		e.ps_next = gettime() + 10;
	if (root) json_free(root);
	return TRUE;
};

void() PlayStats_Frame =
{
	local entity e;
	local float i;
	e = world;
	while ((e = findfloat(e, ps_live, TRUE))) PlayStats_Send(e);
	for (i = 0; i < PS_CLOSING; i = i + 1) PlayStats_CloseSend(i);
};
