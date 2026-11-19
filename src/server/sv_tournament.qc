/* Tournament alpha. The keyed backend persists the match; this server alone
   issues live timing events. OFF by default. No payments or 3D lobby. */
#define TQ_QUEUE_MAX 256
#define TQ_CLIENT_MAX 256
#define TQ_HTTP_WAIT 10
#define TQ_HOLD_LIMIT 30

float tq_cvreg, tq_booted, tq_pollat, tq_request, tq_sentat, tq_retry;
float tq_revision, tq_round, tq_roundtotal, tq_seconds, tq_countat, tq_goat;
float tq_live, tq_resultsat, tq_moving, tq_moveat, tq_arrived, tq_arrive_sent, tq_broken;
string tq_ruleset, tq_kind, tq_profile;
float tq_expected_tick;
// A local table epoch fences readiness; it is not a portable zone identity.
int tq_observed_gen;
string tq_observed_map, tq_observed_pin, tq_observed_crc, tq_rules_breach;
float tq_observed_loaded, tq_observed_course, tq_observed_valid, tq_observed_swept, tq_observed_hull, tq_observed_live;
float tq_clockat, tq_creating, tq_releasing, tq_noteat, tq_race, tq_owned;
float tq_phaseat, tq_hostgone, tq_turnat, tq_abortqueued;
float tq_queue, tq_qread, tq_qwrite, tq_wire, tq_wirecount;
string tq_id, tq_phase, tq_host, tq_map, tq_reserve, tq_turn, tq_turnkind;
string tq_note, tq_pending, tq_pendingop, tq_pendingtoken;
string tq_json;
.float tq_role, tq_seenrev, tq_stream, tq_streamat, tq_lastcmd, tq_boundrev;
.float tq_streambuf, tq_streamcount, tq_streamrev;
.float tq_hold, tq_runround, tq_runstart, tq_best, tq_wasspec, tq_bound;
.string tq_boundwho;
void() SV_PlayerRespawn;
void(entity e) Tour_Stream;
void(string op, string data, entity actor) Tour_Queue;

void() Tour_Cvars =
{
	if (tq_cvreg) return;
	tq_cvreg = TRUE;
	registercvar("tournament_enable", "0");
	registercvar("tournament_reserved", "");
	registercvar("tournament_revision", "0");
};

float() Tour_Owns =
{
	Tour_Cvars();
	return strlen(tq_id) || tq_creating || strlen(cvar_string("tournament_reserved"));
};

float() Tour_On =
{
	Tour_Cvars();
	return (cvar("tournament_enable") || Tour_Owns()) && Account_On();
};

// clienttype walks actual native slots, including unspawned clients and native
// spectators. A classname/player-chain count is NOT an admission barrier.
float() Tour_Occupants =
{
	local float i, n, kind;
	local entity e;
	n = 0;
	for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
	{
		e = edict_num(i);
		kind = clienttype(e);
		if (kind == CLIENTTYPE_NOTACLIENT) break;
		if (kind == CLIENTTYPE_REAL || kind == CLIENTTYPE_BOT) n = n + 1;
	}
	return n;
};

float() Tour_Slots =
{
	local float i;
	for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
		if (clienttype(edict_num(i)) == CLIENTTYPE_NOTACLIENT) return i - 1;
	return TQ_CLIENT_MAX;
};

string(string s) Tour_Arg = { return strlen(s) ? uri_escape(s) : "-"; };

void(entity e, string message) Tour_Tell =
{
	if (!e) return;
	sprint(e, PRINT_HIGH, strcat("tournament: ", message, "\n"));
	stuffcmd(e, strcat("tourney_notice ", Tour_Arg(substring(message, 0, 240)), "\n"));
};

void(entity e) Tour_Unhold =
{
	if (!e.tq_hold) return;
	e.tq_hold = FALSE;
	e.run_pmhold = FALSE;
};

void(entity e) Tour_Hold =
{
	if (!e.tq_hold)
	{
		SV_SpecRelease(e, "tournament");
		e.tq_hold = TRUE;
	}
	e.run_pmhold = TRUE;
	e.velocity = '0 0 0';
};

void(entity e) Tour_Connected =
{
	if (e.tq_streambuf) buf_del(e.tq_streambuf);
	e.tq_streambuf = e.tq_streamcount = e.tq_streamrev = 0;
	e.tq_role = e.tq_seenrev = e.tq_stream = e.tq_hold = 0;
	e.tq_runround = e.tq_runstart = e.tq_best = e.tq_bound = 0;
	e.tq_streamat = e.tq_lastcmd = e.tq_boundrev = 0;
	if (strlen(e.tq_boundwho)) strunzone(e.tq_boundwho);
	e.tq_boundwho = "";
	if (Tour_Owns())
	{
		forceinfokey(e, "*spectator", "1");
		e.solid = SOLID_NOT;
	}
	// Only a tournament server has a panel to clear: Tour_Clear resets every CSQC panel's click state.
	if (Tour_On() || Tour_Owns()) stuffcmd(e, "tourney_clear\n");
};

void(entity e) Tour_Disconnected =
{
	if (e.tq_streambuf) buf_del(e.tq_streambuf);
	e.tq_streambuf = e.tq_streamcount = e.tq_streamrev = 0;
	Tour_Unhold(e);
	if (strlen(e.tq_boundwho)) strunzone(e.tq_boundwho);
	e.tq_boundwho = "";
	e.tq_bound = e.tq_role = e.tq_stream = 0;
};

float() Tour_Remaining =
{
	if (tq_phase == "countdown") return max(0, tq_countat - time);
	if (tq_phase == "live" && tq_live) return max(0, tq_goat + tq_seconds - time);
	if (tq_phase == "results") return max(0, tq_resultsat + 15 - time);
	return 0;
};

float(string phase) Tour_PhaseOK =
{
	return phase == "lobby" || phase == "draft" || phase == "loading" ||
	       phase == "countdown" || phase == "live" || phase == "results" ||
	       phase == "finished" || phase == "cancelled" || phase == "aborted";
};

// Public snapshot rows only. Never put a social token or keyed request here.
void(entity e) Tour_Stream =
{
	local float i, sent;
	local string line;
	sent = 0;
	if (!strlen(tq_id) || !tq_wire) return;
	if (time < e.tq_streamat) return;
	e.tq_streamat = time + 0.1;
	if (!e.tq_stream)
	{
		if (e.tq_streambuf) buf_del(e.tq_streambuf);
		e.tq_streambuf = buf_create();
		for (i = 0; i < tq_wirecount; i = i + 1)
			bufstr_add(e.tq_streambuf, bufstr_get(tq_wire, i), TRUE);
		e.tq_streamcount = tq_wirecount;
		e.tq_streamrev = tq_revision;
		line = sprintf("tourney_begin %s %g %s %s %s %g %g", tq_id, tq_revision,
			tq_phase, Tour_Arg(tq_host), Tour_Arg(e.tq_boundwho), tq_round, tq_roundtotal);
		line = strcat(line, sprintf(" %g %.3f %s %s %s %s %s\n", tq_seconds,
			Tour_Remaining(), Tour_Arg(tq_turn), Tour_Arg(tq_turnkind), Tour_Arg(tq_map),
			Tour_Arg(tq_reserve), Tour_Arg(tq_note)));
		stuffcmd(e, line);
		e.tq_stream = 1;
	}
	for (i = e.tq_stream - 1; i < e.tq_streamcount && sent < 4; i = i + 1)
	{
		stuffcmd(e, bufstr_get(e.tq_streambuf, i));
		sent = sent + 1;
	}
	e.tq_stream = i + 1;
	if (i >= e.tq_streamcount)
	{
		stuffcmd(e, sprintf("tourney_end %g\n", e.tq_streamrev));
		e.tq_seenrev = e.tq_streamrev;
		e.tq_stream = 0;
		buf_del(e.tq_streambuf); e.tq_streambuf = 0;
	}
};

void(entity e) Tour_RefreshRole =
{
	local int root, players, row;
	local float i, role;
	local string who, r;
	local entity saved;
	role = 0;
	if (!strlen(tq_json)) return;
	who = e.acct_who;
	if (e.acct_state != ACCT_LINKED || !strlen(e.social_token)) who = "";
	if (e.tq_bound && e.tq_boundrev == tq_revision && e.tq_boundwho == who) return;
	root = json_parse(tq_json);
	players = json_find_object_child(json_find_object_child(root, "match"), "players");
	for (i = 0; i < min(72, json_get_length(players)); i = i + 1)
	{
		row = json_get_child_at_index(players, i);
		if (strlen(who) && json_get_string(json_find_object_child(row, "who")) == who)
		{
			r = json_get_string(json_find_object_child(row, "role"));
			role = (r == "player") ? 1 : ((r == "eliminated") ? 3 : 2);
			break;
		}
	}
	if (root) json_free(root);
	e.tq_role = role;
	e.tq_boundrev = tq_revision;
	// A snapshot's personalized header must use the SAME verified identity
	// as its completion. Cancel only on identity changes, not score revisions.
	if (strcmp(e.tq_boundwho, who))
	{
		if (e.tq_streambuf) buf_del(e.tq_streambuf);
		e.tq_streambuf = e.tq_stream = e.tq_streamcount = e.tq_streamrev = 0;
		e.tq_streamat = 0;
	}
	if (strlen(e.tq_boundwho)) strunzone(e.tq_boundwho);
	e.tq_boundwho = strlen(who) ? strzone(who) : "";
	e.tq_bound = TRUE;
	e.tq_seenrev = 0;
	if (role == 1 && stof(infokey(e, "*spectator")))
	{
		forceinfokey(e, "*spectator", "0");
		saved = self; self = e; SV_PlayerRespawn(); self = saved;
	}
};

void() Tour_Roles =
{
	local float i, kind;
	local entity e;
	if (!tq_owned || tq_creating || tq_race || !strlen(tq_id)) return;
	for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
	{
		e = edict_num(i);
		kind = clienttype(e);
		if (kind == CLIENTTYPE_NOTACLIENT) break;
		if (kind != CLIENTTYPE_REAL) continue;
		Tour_RefreshRole(e);
		if (e.tq_role != 1)
		{
			Tour_Unhold(e);
			forceinfokey(e, "*spectator", "1");
			e.solid = SOLID_NOT;
		}
		else
		{
			if (stof(infokey(e, "*spectator")))
			{
				forceinfokey(e, "*spectator", "0");
				local entity saved;
				saved = self; self = e; SV_PlayerRespawn(); self = saved;
			}
			if (!tq_releasing && (tq_broken || tq_phase == "countdown" || tq_phase == "results" ||
			    tq_phase == "finished" || tq_phase == "aborted" || tq_phase == "cancelled" ||
			    (tq_phase == "live" && (!tq_live || time > tq_goat + tq_seconds))))
				Tour_Hold(e);
			else Tour_Unhold(e);
		}
		if (e.tq_seenrev != tq_revision) Tour_Stream(e);
	}
};

void(string op, string data, entity actor) Tour_Queue =
{
	local string actorid, token, requestid;
	if (op == "abort" && tq_abortqueued) return;
	if (!tq_queue) tq_queue = buf_create();
	if (tq_qwrite - tq_qread >= TQ_QUEUE_MAX)
	{
		tq_broken = TRUE;
		print("tournament: queue full; holding match, no result may advance\n");
		return;
	}
	if (op == "abort") tq_abortqueued = TRUE;
	actorid = actor ? actor.acct_who : "";
	token = actor ? actor.social_token : "";
	requestid = SV_RandHex(16);
	bufstr_set(tq_queue, tq_qwrite * 4, op);
	bufstr_set(tq_queue, tq_qwrite * 4 + 1, strcat(data, "&request=", requestid));
	bufstr_set(tq_queue, tq_qwrite * 4 + 2, actorid);
	bufstr_set(tq_queue, tq_qwrite * 4 + 3, token);
	tq_qwrite = tq_qwrite + 1;
};

void() Tour_Clear =
{
	local entity e;
	local float i, kind;
	for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
	{
		e = edict_num(i); kind = clienttype(e);
		if (kind == CLIENTTYPE_NOTACLIENT) break;
		if (kind != CLIENTTYPE_REAL) continue;
		Tour_Unhold(e);
		if (e.tq_streambuf) buf_del(e.tq_streambuf);
		e.tq_streambuf = e.tq_streamcount = 0;
		e.tq_role = e.tq_bound = e.tq_stream = 0;
		stuffcmd(e, "tourney_clear\n");
	}
	if (strlen(tq_id)) strunzone(tq_id);
	if (strlen(tq_phase)) strunzone(tq_phase);
	if (strlen(tq_json)) strunzone(tq_json);
	tq_id = tq_phase = tq_json = "";
	if (strlen(tq_ruleset)) strunzone(tq_ruleset);
	if (strlen(tq_kind)) strunzone(tq_kind);
	if (strlen(tq_profile)) strunzone(tq_profile);
	tq_ruleset = tq_kind = tq_profile = ""; tq_expected_tick = 0;
	if (strlen(tq_rules_breach)) strunzone(tq_rules_breach);
	tq_rules_breach = "";
	tq_live = tq_broken = tq_creating = tq_releasing = tq_moving = tq_race = tq_owned = 0;
	tq_revision = tq_round = tq_roundtotal = tq_seconds = tq_arrived = tq_arrive_sent = tq_abortqueued = 0;
	tq_goat = tq_countat = tq_resultsat = tq_phaseat = tq_turnat = tq_hostgone = tq_clockat = 0;
	if (tq_wire) buf_del(tq_wire);
	tq_wire = tq_wirecount = 0;
	// Leave pending request/queue counters intact: release's callback still
	// needs to consume its own head before the next tournament can start.
	cvar_set("tournament_reserved", "");
	cvar_set("tournament_revision", "0");
	forceinfokey(world, "tournament", "");
	if (cvar("lobby_cycle") > 0) lobby_cyc_next = time + max(60, cvar("lobby_cycle"));
	// Empty state is polled repeatedly. Don't announce a nonexistent cancelled vote.
	if (vote_on || lobby_vt_kind) Vote_Cancel();
};

string(string profile) Tour_ProfileMovement =
{
	if (profile == "default") return "default";
	if (profile == "hl2-pre") return "hl2-pre-v1";
	if (profile == "hl2-post") return "hl2-post-v1";
	if (profile == "ag-100") return "ag100-v1";
	if (profile == "ag-250") return "ag250-v1";
	if (profile == "ag-1000") return "ag1000-v1";
	if (profile == "cs16") return "cs16-v1";
	return "";
};
float(string profile) Tour_ProfileTick =
{
	if (profile == "default" || profile == "hl2-pre" || profile == "hl2-post") return 15000;
	if (profile == "ag-100" || profile == "cs16") return 10000;
	if (profile == "ag-250") return 4000;
	if (profile == "ag-1000") return 1000;
	return 0;
};
float(float seconds) Tour_TickUS = { return floor(seconds * 1000000 + 0.5); };
float() Tour_NativeRules =
{
	local string rules;
	// A map-applied label is qualified only under the existing native lock.
	// Unknown remains unqualified here; normal record classification is intact.
	rules = serverkey("*ruleset");
	if (!strlen(rules) || tokenize(rules) < 4 || cvar("sv_cheats") != 0) return FALSE;
	return argv(0) == "1" && argv(1) == "0" && SV_RecIsInt(argv(2), FALSE) && SV_RecIsInt(argv(3), FALSE);
};
string() Tour_Movement =
{
	local string movement;
	if (!Tour_NativeRules()) return "unqualified";
	movement = infokey(world, "*movementprofile");
	return movement == "" ? "default" : movement;
};

// Observe the authoritative BUILT table, never an expected pin echoed by QC.
// Full hashing is done only after a load/rebuild/latched-rule change. Existing
// recorder/timer helpers and normal movement defaults are left untouched.
void() Tour_Observe =
{
	local float ready, dirty, z, mainend, active, rulesok;
	local string pin, crc, breach;
	ready = (zone_entsready && zone_loaded && zone_generation > 0i && zone_mapname == mapname);
	active = (Tour_Owns() && (tq_arrived || tq_arrive_sent) &&
		(tq_phase == "loading" || tq_phase == "countdown" || tq_phase == "live"));
	rulesok = Tour_NativeRules();
	if (rulesok)
	{
		// Consume before another tokenizer call; text preserves the native
		// counter exactly even after QC floats lose single-integer precision.
		breach = argv(3);
		if (active && strlen(tq_rules_breach) && tq_rules_breach != breach) tq_broken = TRUE;
		if ((!active || !strlen(tq_rules_breach)) && tq_rules_breach != breach)
		{
			if (strlen(tq_rules_breach)) strunzone(tq_rules_breach);
			tq_rules_breach = strzone(breach);
		}
	}
	dirty = (!tq_observed_loaded || tq_observed_map != mapname || tq_observed_gen != zone_generation ||
		tq_observed_swept != run_t_swept || tq_observed_hull != run_t_hull || tq_observed_live != run_t_hulllive);
	if (ready && dirty)
	{
		if (active) tq_broken = TRUE;
		pin = SV_VerifyZoneFullPin(); crc = infokey(world, "*mapcrc"); mainend = FALSE;
		for (z = 0; z < zone_count; z += 1)
			if (zone_track[z] == 0 && zone_type[z] == ZONE_END) mainend = TRUE;
		if (strlen(tq_observed_map)) strunzone(tq_observed_map);
		if (strlen(tq_observed_pin)) strunzone(tq_observed_pin);
		if (strlen(tq_observed_crc)) strunzone(tq_observed_crc);
		tq_observed_map = strzone(mapname);
		tq_observed_pin = strlen(pin) ? strzone(pin) : "";
		tq_observed_crc = strlen(crc) ? strzone(crc) : "";
		tq_observed_gen = zone_generation; tq_observed_loaded = TRUE;
		tq_observed_swept = run_t_swept; tq_observed_hull = run_t_hull; tq_observed_live = run_t_hulllive;
		tq_observed_course = (mainend && SV_ZoneFindLeg(0, 0) >= 0 && strlen(zone_crc) &&
			SV_RecIsHex(pin, 64) && SV_RecIsHex(crc, 8) && crc != "00000000");
	}
	if (!ready) tq_observed_loaded = tq_observed_course = FALSE;
	tq_observed_valid = (ready && tq_observed_course && rulesok);
	if (active)
	{
		if (!tq_observed_valid || mapname != tq_map ||
			infokey(world, "*mapcrc") != tq_observed_crc || serverkey("gamemode") != tq_kind ||
			Tour_Movement() != Tour_ProfileMovement(tq_profile) ||
			Tour_TickUS(cvar("pm_ticrate")) != tq_expected_tick ||
			Tour_TickUS(run_t_tick) != tq_expected_tick)
			tq_broken = TRUE;
		if (tq_broken && !tq_abortqueued) Tour_Queue("abort", "&reason=loaded_ruleset_changed", world);
	}
};

void(string s) Tour_StoreNote =
{
	if (strlen(tq_note)) strunzone(tq_note);
	tq_note = strlen(s) ? strzone(substring(s, 0, 180)) : "";
};

void(int match, string envelope) Tour_Adopt =
{
	local string id, phase, current, line, ruleset, kind, profile;
	local float revision, roundnum, i, changed, phasechanged, tick, unfrozenend;
	local int players, maps, row, settings, schedule;
	local entity e, saved;
	id = json_get_string(json_find_object_child(match, "id"));
	phase = json_get_string(json_find_object_child(match, "phase"));
	revision = json_get_float(json_find_object_child(match, "revision"));
	current = json_get_string(json_find_object_child(match, "current_map"));
	settings = json_find_object_child(match, "settings");
	kind = json_get_string(json_find_object_child(settings, "kind"));
	profile = json_get_string(json_find_object_child(settings, "profile"));
	tick = json_get_float(json_find_object_child(settings, "tick_us"));
	ruleset = json_get_string(json_find_object_child(match, "ruleset_id"));
	schedule = json_find_object_child(match, "schedule");
	// Pre-Lock cancellation/abort has no frozen identity. The actual backend
	// schema is one-based in rounds, with zero/empty schedule before Lock.
	// Never accept disappearance of an already pinned ruleset.
	unfrozenend = ((phase == "cancelled" || phase == "aborted") && !strlen(ruleset) &&
		!strlen(tq_ruleset) && !tq_roundtotal &&
		json_get_value_type(json_find_object_child(match, "round_index")) == 1 &&
		json_get_float(json_find_object_child(match, "round_index")) == 0 &&
		json_get_value_type(json_find_object_child(match, "generation")) == 1 &&
		json_get_float(json_find_object_child(match, "generation")) == 0 &&
		json_get_value_type(json_find_object_child(match, "round_total")) == 1 &&
		json_get_float(json_find_object_child(match, "round_total")) == 0 &&
		json_get_value_type(schedule) == 3 && json_get_length(schedule) == 0);
	if ((kind != "surf" && kind != "bhop") || tick != Tour_ProfileTick(profile) || tick <= 0 ||
		((phase != "lobby") && !unfrozenend && !SV_RecIsHex(ruleset, 64)) ||
		(strlen(tq_ruleset) && ruleset != tq_ruleset && tq_phase != "lobby"))
	{
		tq_broken = TRUE;
		print("tournament: missing or changed frozen ruleset; holding\n");
		return;
	}
	if (strlen(id) < 16 || strlen(id) > 64 || !SV_RecIsHex(id, strlen(id)) ||
	    !Tour_PhaseOK(phase) || revision < 1 || (strlen(current) && !Lobby_MapNameOK(current)))
	{
		tq_broken = TRUE;
		print("tournament: malformed match; holding instead of applying untrusted state\n");
		return;
	}
	if (strlen(tq_id) && tq_id != id)
	{
		tq_broken = TRUE;
		print("tournament: unexpected owner; refusing replacement\n");
		return;
	}
	if (revision < tq_revision) return;
	changed = (revision != tq_revision || !strlen(tq_id));
	phasechanged = (phase != tq_phase);
	roundnum = json_get_float(json_find_object_child(match, "round_index"));
	if (roundnum != tq_round)
	{
		tq_arrived = tq_arrive_sent = FALSE;
		tq_live = FALSE;
		for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
		{
			e = edict_num(i); if (clienttype(e) == CLIENTTYPE_NOTACLIENT) break;
			e.tq_best = e.tq_runround = 0;
		}
	}
	if (strlen(tq_id)) strunzone(tq_id);
	tq_id = strzone(id);
	if (strlen(tq_phase)) strunzone(tq_phase);
	tq_phase = strzone(phase);
	tq_revision = revision;
	tq_round = roundnum;
	if (strlen(tq_ruleset)) strunzone(tq_ruleset);
	if (strlen(tq_kind)) strunzone(tq_kind);
	if (strlen(tq_profile)) strunzone(tq_profile);
	tq_ruleset = strlen(ruleset) ? strzone(ruleset) : "";
	tq_kind = strzone(kind); tq_profile = strzone(profile); tq_expected_tick = tick;
	tq_seconds = bound(60, json_get_float(json_find_object_child(match, "round_seconds")), 900);
	tq_roundtotal = json_get_float(json_find_object_child(match, "round_total"));
	if (strlen(tq_host)) strunzone(tq_host);
	tq_host = strzone(json_get_string(json_find_object_child(match, "host")));
	if (strlen(tq_map)) strunzone(tq_map);
	tq_map = strzone(current);
	if (strlen(tq_reserve)) strunzone(tq_reserve);
	tq_reserve = strzone(json_get_string(json_find_object_child(match, "reserve")));
	if (tq_turn != json_get_string(json_find_object_child(match, "turn_who"))) tq_turnat = time;
	if (strlen(tq_turn)) strunzone(tq_turn);
	tq_turn = strzone(json_get_string(json_find_object_child(match, "turn_who")));
	if (strlen(tq_turnkind)) strunzone(tq_turnkind);
	tq_turnkind = strzone(json_get_string(json_find_object_child(match, "turn_kind")));
	Tour_StoreNote(json_get_string(json_find_object_child(match, "note")));
	if (strlen(tq_json)) strunzone(tq_json);
	tq_json = strzone(envelope);
	cvar_set("tournament_reserved", tq_id);
	cvar_set("tournament_revision", ftos(tq_revision));
	forceinfokey(world, "tournament", tq_phase);
	if (changed)
	{
		if (tq_wire) buf_del(tq_wire);
		tq_wire = buf_create();
		tq_wirecount = 0;
		players = json_find_object_child(match, "players");
		for (i = 0; i < min(72, json_get_length(players)); i = i + 1)
		{
			row = json_get_child_at_index(players, i);
			line = sprintf("tourney_player %s %s %s %g %g %g",
				Tour_Arg(json_get_string(json_find_object_child(row, "who"))),
				Tour_Arg(substring(json_get_string(json_find_object_child(row, "name")), 0, 64)),
				Tour_Arg(json_get_string(json_find_object_child(row, "role"))),
				json_get_float(json_find_object_child(row, "ready")),
				json_get_float(json_find_object_child(row, "accepted")),
				json_get_float(json_find_object_child(row, "best_ticks")));
			line = strcat(line, sprintf(" %.9g %g\n",
				json_get_float(json_find_object_child(row, "tickrate")),
				json_get_float(json_find_object_child(row, "place"))));
			bufstr_add(tq_wire, line, TRUE);
		}
		maps = json_find_object_child(match, "maps");
		for (i = 0; i < min(24, json_get_length(maps)); i = i + 1)
		{
			row = json_get_child_at_index(maps, i);
			bufstr_add(tq_wire, sprintf("tourney_map %s %s %s\n",
				Tour_Arg(json_get_string(json_find_object_child(row, "name"))),
				Tour_Arg(json_get_string(json_find_object_child(row, "status"))),
				Tour_Arg(json_get_string(json_find_object_child(row, "by")))), TRUE);
		}
		tq_wirecount = buf_getsize(tq_wire);
		for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
		{
			e = edict_num(i); if (clienttype(e) == CLIENTTYPE_NOTACLIENT) break;
			e.tq_bound = 0;
		}
	}
	if (phasechanged)
	{
		tq_phaseat = time;
		if (phase == "countdown")
		{
			tq_countat = time + 5;
			for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
			{
				e = edict_num(i); if (clienttype(e) == CLIENTTYPE_NOTACLIENT) break;
				if (clienttype(e) != CLIENTTYPE_REAL) continue;
				Tour_RefreshRole(e);
				if (e.tq_role != 1) continue;
				saved = self; self = e;
				SV_PlayerRespawn();
				SV_ZoneChatCommand("!m", 0);
				self = saved;
				Tour_Hold(e);
			}
		}
		if (phase == "live")
		{
			if (tq_pendingop == "go")
			{
				tq_goat = time;
				tq_live = TRUE;
			}
			else
			{
				tq_broken = TRUE;
				Tour_Queue("abort", "&reason=interrupted_live_round", world);
			}
		}
		if (phase == "results" || phase == "finished" || phase == "aborted" || phase == "cancelled")
		{
			tq_resultsat = time;
			tq_live = FALSE;
		}
	}
};

float(float reqid, float code, string body) Tour_Reply =
{
	local int root, match;
	local float ok;
	local entity actor;
	local string message, status;
	if (!tq_request || reqid != tq_request) return FALSE;
	tq_request = 0;
	Tour_Observe(); // a late GO/arrival must not outrun a local table/rule change
	root = json_parse(body);
	ok = (!code && json_get_float(json_find_object_child(root, "ok")));
	status = json_get_string(json_find_object_child(root, "status"));
	actor = find(world, social_token, tq_pendingtoken);
	if (!strlen(tq_pendingtoken)) actor = world;
	if (!ok)
	{
		message = json_get_string(json_find_object_child(root, "error"));
		if (!strlen(message)) message = "Service unavailable; tournament held, retrying";
		if (actor) Tour_Tell(actor, message);
		else if (time >= tq_noteat)
		{
			tq_noteat = time + 10;
			print(strcat("tournament: ", message, "\n"));
		}
		// Transport errors retry the EXACT same idempotent mutation. No later
		// score or settle may pass an unacknowledged earlier event.
		if (code || !root || status == "storage")
		{
			tq_sentat = time;
			tq_pollat = time + 2;
			if (Tour_Owns()) tq_broken = TRUE;
			if (root) json_free(root);
			return TRUE;
		}
	}
	if (strlen(tq_id) && (status == "disabled" || (!ok &&
	    (tq_pendingop == "go" || tq_pendingop == "score" || tq_pendingop == "settle" ||
	     tq_pendingop == "arrive" || tq_pendingop == "advance"))))
		tq_broken = TRUE; // trusted control refused: use durable abort, never strand LIVE
	match = json_find_object_child(root, "match");
	if (ok && tq_pendingop == "release") Tour_Clear();
	else if (match && json_get_value_type(match) == 2)
	{
		// A public arrival won the reservation race. Leave them in ordinary
		// play; abort/release the new reservation without spectator coercion.
		if (ok && tq_pendingop == "create" && Tour_Occupants() != 1)
		{
			tq_broken = TRUE;
			Tour_Adopt(match, body);
			tq_race = TRUE;
			Tour_Queue("abort", "&reason=reservation_race", world);
		}
		else
		{
			Tour_Adopt(match, body);
			if (tq_broken && tq_phase != "aborted" && tq_phase != "cancelled" && tq_phase != "finished" && tq_pendingop != "abort")
				Tour_Queue("abort", "&reason=service_interrupted", world);
		}
	}
	else if (ok && tq_pendingop == "state" && !Tour_Owns()) Tour_Clear();
	// Sent is not arrived: local Ready stays gated until this exact ACK.
	if (ok && tq_pendingop == "arrive" && !tq_broken && tq_observed_valid && mapname == tq_map)
		tq_arrived = TRUE;
	if (tq_pendingop == "create") tq_creating = FALSE;
	if (tq_pendingop != "state")
	{
		tq_qread = tq_qread + 1;
		if (tq_qread == tq_qwrite)
		{
			buf_del(tq_queue); tq_queue = 0;
			tq_qread = tq_qwrite = 0;
		}
	}
	if (strlen(tq_pending)) strunzone(tq_pending);
	tq_pending = "";
	if (strlen(tq_pendingtoken)) strunzone(tq_pendingtoken);
	tq_pendingtoken = "";
	if (strlen(tq_pendingop)) strunzone(tq_pendingop);
	tq_pendingop = "";
	tq_retry = 0;
	if (root) json_free(root);
	tq_pollat = min(tq_pollat, time + 2);
	return TRUE;
};

string(string op, string data, string token) Tour_Form =
{
	local string form;
	Tour_Observe();
	form = strcat(Social_Form(), "&op=", op, "&id=", tq_id, "&revision=", ftos(tq_revision));
	form = strcat(form, "&occupants=", ftos(Tour_Occupants()), "&current_map=", uri_escape(mapname),
		"&token=", token, data);
	form = strcat(form, "&movement=", uri_escape(Tour_Movement()),
		"&tick_us=", ftos(Tour_TickUS(cvar("pm_ticrate"))));
	form = strcat(form, "&clock_us=", ftos(Tour_TickUS(run_t_tick)),
		"&gamemode=", uri_escape(serverkey("gamemode")));
	form = strcat(form, "&mapcrc=", uri_escape(infokey(world, "*mapcrc")),
		"&zonepin=", uri_escape(tq_observed_pin));
	// FTE's %d reads float bits; %i is the typed-integer format.
	form = strcat(form, "&zonegen=", sprintf("%i", tq_observed_gen), "&ruleset=", uri_escape(tq_ruleset));
	form = strcat(form, "&epoch=", tq_id, "&generation=", ftos(tq_round), "&round=", ftos(tq_round));
	return strcat(form, "&enabled=", cvar("tournament_enable") ? "1" : "0");
};

void() Tour_Send =
{
	local string op, data, token;
	data = token = "";
	if (tq_request || time < tq_pollat) return;
	if (!strlen(tq_pending))
	{
		if (tq_qread < tq_qwrite)
		{
			op = bufstr_get(tq_queue, tq_qread * 4);
			data = bufstr_get(tq_queue, tq_qread * 4 + 1);
			token = bufstr_get(tq_queue, tq_qread * 4 + 3);
		}
		else op = "state";
		tq_pendingop = strzone(op);
		tq_pendingtoken = strlen(token) ? strzone(token) : "";
		tq_pending = strzone(Tour_Form(op, data, token));
	}
	tq_request = Account_NextId();
	tq_sentat = time;
	if (!uri_post(strcat(cvar_string("lobby_master"), "/api/tournaments/game"), tq_request,
		"application/x-www-form-urlencoded", tq_pending))
	{
		tq_request = 0;
		tq_pollat = time + 2;
	}
	else tq_pollat = time + (tq_qread < tq_qwrite ? 0.05 : 2);
};

// Called exactly where the native timer starts, not inferred from sampled HUD
// state. A warmup/restored attempt cannot inherit the current round identity.
void(entity e) Tour_RunStart =
{
	e.tq_runround = 0;
	if (!Tour_Owns() || tq_phase != "live" || !tq_live || tq_broken || e.tq_role != 1) return;
	if (time < tq_goat || time >= tq_goat + tq_seconds) return;
	Tour_Observe(); if (tq_broken) return;
	e.tq_runround = tq_round;
	e.tq_runstart = time - tq_goat;
};

void(entity e) Tour_Finished =
{
	local string data;
	local float rate;
	if (!Tour_Owns() || tq_phase != "live" || !tq_live || tq_broken || e.tq_role != 1) return;
	if (e.tq_runround != tq_round || time > tq_goat + tq_seconds || time < tq_goat) return;
	Tour_Observe(); if (tq_broken || !tq_arrived) return;
	if (e.run_t_finleg != 1 || FS_RunClass(e.run_t_finflags) != RC_CLEAN) return;
	if (!(e.run_t_finticks > 0 && e.run_t_finticks < 16000000) || e.run_movetickrate <= 0) return;
	if (e.tq_best > 0 && e.run_t_finticks >= e.tq_best) return;
	rate = 1 / e.run_movetickrate;
	if (fabs(e.run_movetickrate - run_t_tick) > 0.0000001) return;
	e.tq_best = e.run_t_finticks;
	data = sprintf("&who=%s&ticks=%d&tickrate=%.9g&elapsed_ms=%d&start_elapsed_ms=%d",
		e.acct_who, e.run_t_finticks, rate, floor((time - tq_goat) * 1000), floor(e.tq_runstart * 1000));
	data = strcat(data, "&clean=1&runid=", SV_RandHex(16));
	Tour_Queue("score", data, world);
};

float(entity e) Tour_PreThink =
{
	if (!tq_owned || tq_creating || tq_race) return FALSE;
	if (e.tq_role != 1)
	{
		forceinfokey(e, "*spectator", "1");
		e.solid = SOLID_NOT;
		return TRUE;
	}
	if (e.tq_hold)
	{
		e.run_pmhold = TRUE;
		e.velocity = '0 0 0';
		return TRUE;
	}
	return FALSE;
};

float(entity e, float argc) Tour_Command =
{
	local string op, data, target;
	data = "";
	if (argc < 2 || argv(1) == "open")
	{
		stuffcmd(e, "tourney_open\n");
		e.tq_seenrev = 0;
		return TRUE;
	}
	op = argv(1);
	if (op == "resync") { e.tq_seenrev = 0; return TRUE; }
	if (!Tour_On()) { Tour_Tell(e, "Tournament alpha is disabled on this server"); return TRUE; }
	if (e.acct_state != ACCT_LINKED || !strlen(e.social_token))
	{
		Tour_Tell(e, "Link Steam and wait for account verification first");
		return TRUE;
	}
	if (time < e.tq_lastcmd + 0.5) return TRUE;
	e.tq_lastcmd = time;
	if (op == "create")
	{
		if (!cvar("tournament_enable") || Tour_Owns() || Tour_Occupants() != 1)
		{
			Tour_Tell(e, "Creation requires an opted-in empty server with only you connected");
			return TRUE;
		}
		if (argc != 4 || stof(argv(2)) < 2 || stof(argv(2)) > 8 ||
		    stof(argv(3)) < 60 || stof(argv(3)) > 900)
		{
			Tour_Tell(e, "Use tour create <2..8 seats> <60..900 round seconds>");
			return TRUE;
		}
		if (cvar("maxclients") < floor(stof(argv(2))) ||
		    cvar("maxspectators") > Tour_Slots() - floor(stof(argv(2))))
		{
			Tour_Tell(e, "Configure enough player slots and leave competitor capacity outside the spectator cap");
			return TRUE;
		}
		tq_creating = tq_owned = TRUE;
		data = sprintf("&capacity=%g&round_seconds=%g", floor(stof(argv(2))), floor(stof(argv(3))));
	}
	else
	{
		if (!strlen(tq_id)) { Tour_Tell(e, "No tournament is active here"); return TRUE; }
		if (op == "ban" || op == "pick")
		{
			if (argc != 3 || !Lobby_MapNameOK(argv(2))) return TRUE;
			data = strcat("&map=", uri_escape(argv(2)));
		}
		else if (op == "seat")
		{
			target = argv(2);
			if (argc != 3 || !SV_RecIsHex(target, FS_WHO_IDLEN)) return TRUE;
			data = strcat("&target=", target);
		}
		else if (op == "ready")
		{
			Tour_Observe();
			if (tq_broken || !tq_observed_valid) { Tour_Tell(e, "Loaded tournament rules changed; match held"); return TRUE; }
			if (tq_phase != "loading" || mapname != tq_map || !tq_arrived)
			{
				Tour_Tell(e, "Wait until the tournament map is loaded");
				return TRUE;
			}
			data = strcat("&map=", uri_escape(mapname), "&round_index=", ftos(tq_round));
		}
		else if (op != "enter" && op != "accept" && op != "lock" && op != "start" &&
		         op != "next" && op != "leave" && op != "cancel") return TRUE;
	}
	Tour_Queue(op, data, e);
	return TRUE;
};

void() Tour_Frame =
{
	local float i;
	local int root, players, row;
	local entity e;
	local string who;
	tq_owned = Tour_Owns();
	if (!Tour_On() || !zone_entsready) return;
	Tour_Observe();
	if (!tq_booted)
	{
		tq_booted = TRUE;
		tq_pollat = time + 1;
	}
	if (tq_request && time - tq_sentat > TQ_HTTP_WAIT)
	{
		tq_request = 0;
		tq_retry = tq_retry + 1;
		if (Tour_Owns()) tq_broken = TRUE;
		print("tournament: timed out; retaining reservation, retrying identical request\n");
	}
	if (tq_retry > 2 && Tour_Owns())
	{
		tq_broken = TRUE;
		Tour_Roles();
	}
	if (strlen(tq_id) && !tq_creating)
	{
		if (!tq_broken && (tq_phase == "lobby" || tq_phase == "draft" || tq_phase == "loading"))
		{
			e = find(world, acct_who, tq_host);
			if (!e || clienttype(e) != CLIENTTYPE_REAL || e.acct_state != ACCT_LINKED)
			{
				if (!tq_hostgone) tq_hostgone = time;
			}
			else tq_hostgone = 0;
			if ((tq_phase == "lobby" && time - tq_phaseat > 900) ||
			    (tq_phase == "draft" && time - tq_turnat > 60) ||
			    (tq_phase == "loading" && time - tq_phaseat > 120) ||
			    (tq_hostgone && time - tq_hostgone > 60))
			{
				tq_broken = TRUE;
				Tour_Queue("abort", "&reason=alpha_lobby_timeout", world);
			}
		}
		if (tq_phase == "loading")
		{
			if (mapname != tq_map)
			{
				if (!tq_moving && !tq_broken && !tq_request && tq_qread == tq_qwrite)
				{
					tq_moving = TRUE; tq_moveat = time; lobby_cyc_moving = TRUE;
					localcmd(sprintf("changelevel \"%s\"\n", tq_map));
				}
				if (tq_moving && time - tq_moveat > 15 && !tq_broken)
				{
					tq_broken = TRUE;
					Tour_Queue("abort", "&reason=map_change_failed", world);
				}
			}
			else if (!tq_broken && !tq_arrived && !tq_arrive_sent && !tq_request && tq_qread == tq_qwrite)
			{
				if (!tq_observed_valid)
				{
					tq_broken = TRUE;
					Tour_Queue("abort", "&reason=unqualified_loaded_table", world);
				}
				else
				{
					tq_arrive_sent = TRUE;
					Tour_Queue("arrive", strcat("&map=", uri_escape(mapname), "&round_index=", ftos(tq_round)), world);
				}
			}
		}
		if (tq_phase == "countdown" && !tq_broken)
		{
			// Every remaining account must still have a live, verified slot.
			root = json_parse(tq_json);
			players = json_find_object_child(json_find_object_child(root, "match"), "players");
			for (i = 0; i < min(72, json_get_length(players)); i = i + 1)
			{
				row = json_get_child_at_index(players, i);
				if (json_get_string(json_find_object_child(row, "role")) != "player") continue;
				who = json_get_string(json_find_object_child(row, "who"));
				e = find(world, acct_who, who);
				if (!e || clienttype(e) != CLIENTTYPE_REAL || e.acct_state != ACCT_LINKED)
				{
					tq_broken = TRUE;
					Tour_Queue("abort", "&reason=competitor_lost_during_countdown", world);
					break;
				}
			}
			if (root) json_free(root);
			if (!tq_broken && time >= tq_countat && tq_qread == tq_qwrite && !tq_request)
				Tour_Queue("go", sprintf("&elapsed_ms=%d&tickrate=%.9g",
					max(5000, floor((time - tq_countat + 5) * 1000)), 1 / run_t_tick), world);
		}
		if (tq_phase == "live" && tq_live && !tq_broken && time > tq_goat + tq_seconds)
		{
			tq_live = FALSE;
			Tour_Queue("settle", sprintf("&elapsed_ms=%d", max(tq_seconds * 1000,
				floor((time - tq_goat) * 1000))), world);
		}
		if (tq_phase == "results" && time >= tq_resultsat + 15 && tq_qread == tq_qwrite && !tq_request)
			Tour_Queue("advance", "", world);
		if ((tq_phase == "finished" || tq_phase == "aborted" || tq_phase == "cancelled") &&
		    time >= tq_resultsat + 30 && !tq_releasing && tq_qread == tq_qwrite && !tq_request)
		{
			// All modifications were role/hold/rotation ownership, not physics.
			for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
			{
				e = edict_num(i); if (clienttype(e) == CLIENTTYPE_NOTACLIENT) break;
				Tour_Unhold(e);
			}
			tq_releasing = TRUE;
			Tour_Queue("release", "&restored=1", world);
		}
	}
	Tour_Roles();
	if (time >= tq_clockat && strlen(tq_id))
	{
		tq_clockat = time + 0.5;
		for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
		{
			e = edict_num(i); if (clienttype(e) == CLIENTTYPE_NOTACLIENT) break;
			if (clienttype(e) == CLIENTTYPE_REAL && e.tq_seenrev == tq_revision)
				stuffcmd(e, sprintf("tourney_clock %g %.3f %s\n", tq_revision, Tour_Remaining(), tq_phase));
		}
	}
	Tour_Send();
};
