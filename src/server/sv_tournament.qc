/* Tournament alpha. The keyed backend persists the match; this server alone
   issues live timing events. OFF by default. No payments or 3D lobby. */
#define TQ_QUEUE_MAX 256
#define TQ_CLIENT_MAX 256
#define TQ_HTTP_WAIT 10
#define TQ_HOLD_LIMIT 30
// P1648: loading covers connecting, downloads and account checks for strangers; 120 s aborted real rooms.
#define TQ_LOAD_LIMIT 600
#define TQ_HOST_LIMIT 180
float tq_allreadyat, tq_startsent, tq_readyscanat, tq_arrivedat, tq_absentwarned, tq_autorefused, tq_emptysince;
float tq_absentsince, tq_canstart, tq_startnow, tq_waitprev, tq_autofails, tq_startskind, tq_drainat;
string tq_absentset;
.float tq_nojournal, tq_speccmd, tq_joinat;

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
.float tq_hold, tq_runround, tq_runstart, tq_best, tq_wasspec, tq_bound, tq_holdmove;
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
	registercvar("tournament_autostart", "20"); // P1648: seconds after everyone is here; 0 = host only
	registercvar("tournament_noauto", "");      // the match id an older surfd refused autostart for
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

// A connected client by account id: only live slots, never a freed one's leftover fields.
entity(string who) Tour_Client =
{
	local float i;
	local entity e;
	if (!strlen(who)) return world;
	for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
	{
		e = edict_num(i);
		if (clienttype(e) == CLIENTTYPE_NOTACLIENT) break;
		if (clienttype(e) == CLIENTTYPE_REAL && e.acct_who == who) return e;
	}
	return world;
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
	if (e.movetype == MOVETYPE_NONE) e.movetype = e.tq_holdmove ? e.tq_holdmove : MOVETYPE_WALK;
	e.tq_holdmove = 0;
};

// Competitors are drawn as lobby avatars. One released from a forced spectate never ran ClientConnect (a map load
// reconnects a spectator through SpectatorConnect), so it had none and was invisible (Lex 21 Nov); a forced
// spectator's avatar would follow its free camera (Lobby_AvatarPose checks only the classname).
void(entity e) Tour_Avatar =
{
	if (stof(infokey(e, "*spectator"))) { Lobby_AvatarFree(e); return; }
	if (!e.lobby_av && cvar("lobby_enable") && cvar("lobby_avatars")) Lobby_AvatarSpawn(e);
};

void(entity e) Tour_Hold =
{
	if (!e.tq_hold)
	{
		// The tournament hold is the only owner of the movetype while it lasts (P1672 review): a save-lock or replay
		// pin taken over here would otherwise be released into WALK at GO while its own flag is still set.
		SV_SpecRelease(e, "tournament");
		SV_SaveLocRelease(e);
		SV_WatchLetGo(e, "tournament hold");
		// The hold freezes the body mid-run and Tour_Unhold has no rollback, so a held run
		// must end here or it could continue after the hold and post to the ordinary board.
		SV_TimerVoid(e, "tournament hold");
		e.tq_holdmove = e.movetype; // MOVETYPE_NONE is 0: Tour_Unhold gives back WALK
		e.tq_hold = TRUE;
	}
	e.run_pmhold = TRUE;
	// MOVETYPE_NONE stops the client's prediction as well (SV_PMTypeForClient -> PM_NONE): with run_pmhold alone a
	// held player could hold jump and bounce locally, snapped back each snapshot (Lex 21 Nov). The save hold's pin.
	e.movetype = MOVETYPE_NONE;
	e.velocity = '0 0 0';
};

void(entity e) Tour_Connected =
{
	if (e.tq_streambuf) buf_del(e.tq_streambuf);
	e.tq_streambuf = e.tq_streamcount = e.tq_streamrev = 0;
	e.tq_role = e.tq_seenrev = e.tq_stream = e.tq_hold = 0;
	e.tq_runround = e.tq_runstart = e.tq_best = e.tq_bound = e.tq_nojournal = e.tq_speccmd = 0;
	e.tq_streamat = e.tq_lastcmd = e.tq_boundrev = 0;
	if (strlen(e.tq_boundwho)) strunzone(e.tq_boundwho);
	e.tq_boundwho = "";
	if (infokey(e, "*tqspec") == "1" && !stof(infokey(e, "*spectator"))) // a held match re-tags it just below
	{
		// Rejoined through Cmd_Join_f (Tour_Clear): its SpectatorDisconnect/ClientConnect dropped the account link
		// and CSQC asks only once per VM load, so the server asks again (Account_Connect ran just before this).
		forceinfokey(e, "*tqspec", "");
		Account_IssueHello(e, FALSE);
	}
	if (Tour_Owns())
	{
		if (!stof(infokey(e, "*spectator"))) { forceinfokey(e, "*tqspec", "1"); }
		forceinfokey(e, "*spectator", "1");
		e.solid = SOLID_NOT;
		Lobby_AvatarFree(e);
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
	// P1649: what the HUD counts down to: the loading abort, the release back to public play.
	if (tq_phase == "loading" && tq_allreadyat && !tq_autorefused && cvar("tournament_autostart") > 0)
		return max(0, tq_allreadyat + cvar("tournament_autostart") - time);
	if (tq_phase == "loading") return max(0, tq_phaseat + TQ_LOAD_LIMIT - time);
	if (tq_phase == "finished" || tq_phase == "aborted" || tq_phase == "cancelled") return max(0, tq_resultsat + 30 - time);
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
		forceinfokey(e, "*spectator", "0"); forceinfokey(e, "*tqspec", "");
		saved = self; self = e; SV_PlayerRespawn(); self = saved;
		Tour_Avatar(e);
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
			if (!stof(infokey(e, "*spectator"))) { forceinfokey(e, "*tqspec", "1"); }
			forceinfokey(e, "*spectator", "1");
			e.solid = SOLID_NOT;
			Lobby_AvatarFree(e);
		}
		else
		{
			if (stof(infokey(e, "*spectator")))
			{
				forceinfokey(e, "*spectator", "0"); forceinfokey(e, "*tqspec", "");
				local entity saved;
				saved = self; self = e; SV_PlayerRespawn(); self = saved;
			}
			Tour_Avatar(e);
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
	local float i, kind, held;
	held = (tq_id != ""); // Tour_Clear also runs on every idle state poll
	for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
	{
		e = edict_num(i); kind = clienttype(e);
		if (kind == CLIENTTYPE_NOTACLIENT) break;
		if (kind != CLIENTTYPE_REAL) continue;
		Tour_Unhold(e);
		// The tournament's forced spectators (only they carry *tqspec) rejoin play through the engine's `join`
		// (Cmd_Join_f: slot check, SetNewParms, ClientConnect, PutClientInServer). Tour_Clear also runs on
		// every idle poll, so a refused join (a full server, still connecting) is retried every 10 s.
		if (infokey(e, "*tqspec") == "1")
		{
			if (!stof(infokey(e, "*spectator"))) forceinfokey(e, "*tqspec", "");
			else if (time >= e.tq_joinat)
			{
				// Cmd_Join_f despawns through SpectatorDisconnect, which skips Lobby_ClientDisconnect: free the
				// avatar the player had before being forced, or it stays as a second body (review round 7).
				e.tq_joinat = time + 10;
				Lobby_AvatarFree(e);
				stuffcmd(e, "cmd join\n");
			}
		}
		if (e.tq_streambuf) buf_del(e.tq_streambuf);
		e.tq_streambuf = e.tq_streamcount = 0;
		e.tq_role = e.tq_bound = e.tq_stream = 0;
		if (held) stuffcmd(e, "tourney_clear\n");
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
	forceinfokey(world, "tournament_auto", ""); forceinfokey(world, "tournament_starts", "");
	tq_autorefused = tq_allreadyat = tq_startsent = tq_arrivedat = tq_absentwarned = tq_absentsince = tq_canstart = tq_startnow = 0;
	tq_waitprev = tq_autofails = tq_startskind = tq_drainat = 0;
	if (strlen(tq_absentset)) strunzone(tq_absentset);
	tq_absentset = "";
	cvar_set("tournament_noauto", "");
	// vote_on means "map votes enabled", not "a vote is open": testing it here cancelled (and announced) a vote on
	// every idle poll and pushed the map cycle back each time (Lex 21 Nov).
	if (held && cvar("lobby_cycle") > 0) lobby_cyc_next = time + max(60, cvar("lobby_cycle"));
	if (held && lobby_vt_kind) Vote_Cancel();
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
// Default keeps each map kind's own tick (P1639): bhop runs 100 Hz under mode_bhop.cfg.
float(string profile, string kind) Tour_ProfileTick =
{
	if (profile == "default" && kind == "bhop") return 10000;
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
	// P1648: the engine names AG "ag-100-v1" (pm_ag.c:11); surfd's PROFILES and Tour_ProfileMovement say "ag100-v1".
	if (movement == "ag-100-v1") return "ag100-v1";
	if (movement == "ag-250-v1") return "ag250-v1";
	if (movement == "ag-1000-v1") return "ag1000-v1";
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

string(float n) Tour_Ordinal =
{
	local float t;
	t = n - floor(n / 100) * 100;
	if (t >= 11 && t <= 13) return strcat(ftos(n), "th");
	t = n - floor(n / 10) * 10;
	if (t == 1) return strcat(ftos(n), "st");
	if (t == 2) return strcat(ftos(n), "nd");
	if (t == 3) return strcat(ftos(n), "rd");
	return strcat(ftos(n), "th");
};

#define TQ_SAY "^3tournament:^7 "
// P1649: everyone on the server (competitors, spectators, a host's stream) reads the match in chat, not
// only inside F6: each phase, every new round best with its rank, who is out, who won.
void(string prev, string oldphase) Tour_Announce =
{
	local int nroot, oroot, np, op, row, orow;
	local float i, j, n, best, rate, rank, oldbest, place, other, otherrate;
	local string who, name, role, oldrole, outs, winners, line, crown;
	nroot = json_parse(tq_json);
	np = json_find_object_child(json_find_object_child(nroot, "match"), "players");
	oroot = strlen(prev) ? json_parse(prev) : 0;
	op = oroot ? json_find_object_child(json_find_object_child(oroot, "match"), "players") : 0;
	n = 0;
	for (i = 0; i < min(72, json_get_length(np)); i = i + 1)
		if (json_get_string(json_find_object_child(json_get_child_at_index(np, i), "role")) == "player") n = n + 1;
	outs = winners = "";
	for (i = 0; i < min(72, json_get_length(np)); i = i + 1)
	{
		row = json_get_child_at_index(np, i);
		who = json_get_string(json_find_object_child(row, "who"));
		name = substring(json_get_string(json_find_object_child(row, "name")), 0, 32);
		role = json_get_string(json_find_object_child(row, "role"));
		best = json_get_float(json_find_object_child(row, "best_ticks"));
		rate = json_get_float(json_find_object_child(row, "tickrate")); // ticks per second
		place = json_get_float(json_find_object_child(row, "place"));
		oldbest = 0; oldrole = "";
		for (j = 0; op && j < min(72, json_get_length(op)); j = j + 1)
		{
			orow = json_get_child_at_index(op, j);
			if (json_get_string(json_find_object_child(orow, "who")) != who) continue;
			oldbest = json_get_float(json_find_object_child(orow, "best_ticks"));
			oldrole = json_get_string(json_find_object_child(orow, "role"));
			break;
		}
		if (role == "player" && place == 1) winners = strlen(winners) ? strcat(winners, ", ", name) : name;
		if (role == "eliminated" && oldrole == "player") outs = strlen(outs) ? strcat(outs, ", ", name) : name;
		if (role != "player" || tq_phase != "live" || best <= 0 || rate <= 0 || best == oldbest) continue;
		rank = 1;
		for (j = 0; j < min(72, json_get_length(np)); j = j + 1)
		{
			orow = json_get_child_at_index(np, j);
			if (j == i || json_get_string(json_find_object_child(orow, "role")) != "player") continue;
			other = json_get_float(json_find_object_child(orow, "best_ticks"));
			otherrate = json_get_float(json_find_object_child(orow, "tickrate"));
			if (other > 0 && otherrate > 0 && other / otherrate < best / rate) rank = rank + 1;
		}
		if (!strlen(prev)) continue; // a reloaded server does not re-announce every best
		bprint(PRINT_CHAT, sprintf("%s^3%s^7  %s  ^5%s of %g^7\n", TQ_SAY, name, Time_TickString(best, 1 / rate), Tour_Ordinal(rank), n));
	}
	if (oroot) json_free(oroot);
	if (nroot) json_free(nroot);
	if (strlen(outs) && tq_phase != "results") // a forfeit mid-round; results say it in their own line
		bprint(PRINT_CHAT, sprintf("%s^1Out:^7 %s\n", TQ_SAY, outs));
	if (tq_phase == oldphase) return;
	crown = (strstrofs(winners, ", ", 0) >= 0) ? strcat("^3", winners, " share first place!^7") : strcat("^3", winners, " wins the tournament!^7");
	// Globals reset with each map, so the round's map announces itself once loaded (not again on the old one).
	if (tq_phase == "loading" && tq_roundtotal > 0 && mapname == tq_map)
		bprint(PRINT_CHAT, sprintf("%s^5Round %g of %g:^7 %s. %s\n", TQ_SAY, tq_round, tq_roundtotal, tq_map,
			(cvar("tournament_autostart") > 0) ? "The round starts by itself once everyone is here." : "The host starts the round once everyone is ready."));
	else if (tq_phase == "countdown")
		bprint(PRINT_CHAT, sprintf("%s^5Round %g starts in 5 seconds.^7 Set your best time on %s before the clock runs out.\n", TQ_SAY, tq_round, tq_map));
	else if (tq_phase == "live")
		bprint(PRINT_CHAT, sprintf("%s^2GO!^7 %s on the clock. Restart as often as you like; your best run counts.\n", TQ_SAY, Time_Clock(tq_seconds)));
	else if (tq_phase == "results")
	{
		line = sprintf("%s^5Round %g over.^7", TQ_SAY, tq_round);
		if (strlen(outs)) line = strcat(line, " ^1Out:^7 ", outs, ".");
		else if (strlen(tq_note)) line = strcat(line, " ", tq_note);
		if (strlen(winners)) line = strcat(line, " ", crown);
		else line = strcat(line, " Next round in 15 seconds.");
		bprint(PRINT_CHAT, strcat(line, "\n"));
	}
	else if (tq_phase == "finished")
		bprint(PRINT_CHAT, strcat(TQ_SAY, (strlen(winners) && oldphase != "results") ? crown : "^5The tournament is over.^7",
			" Back to normal play in 30 seconds.\n"));
	else if (tq_phase == "aborted" || tq_phase == "cancelled")
		bprint(PRINT_CHAT, sprintf("%s^1Tournament over.^7 %s Back to normal play in 30 seconds.\n", TQ_SAY, tq_note));
};

void(int match, string envelope) Tour_Adopt =
{
	local string id, phase, current, line, ruleset, kind, profile, prev, oldphase, mname;
	local float revision, roundnum, i, j, order, changed, phasechanged, tick, unfrozenend;
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
	if ((kind != "surf" && kind != "bhop") || tick != Tour_ProfileTick(profile, kind) || tick <= 0 ||
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
	prev = strlen(tq_json) ? strzone(tq_json) : "";   // Tour_Announce diffs against it
	oldphase = strlen(tq_phase) ? strzone(tq_phase) : "";
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
			// P1649: the map's round number in the schedule (0 = not scheduled), so F6 can list play order.
			mname = json_get_string(json_find_object_child(row, "name"));
			order = 0;
			for (j = 0; j < min(24, json_get_length(schedule)); j = j + 1)
				if (json_get_string(json_get_child_at_index(schedule, j)) == mname) { order = j + 1; break; }
			bufstr_add(tq_wire, sprintf("tourney_map %s %s %s %g\n", Tour_Arg(mname),
				Tour_Arg(json_get_string(json_find_object_child(row, "status"))),
				Tour_Arg(json_get_string(json_find_object_child(row, "by"))), order), TRUE);
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
		tq_allreadyat = tq_startsent = tq_absentwarned = tq_absentsince = tq_canstart = tq_startnow = 0;
		tq_waitprev = tq_autofails = tq_startskind = tq_drainat = 0;
		if (strlen(tq_absentset)) strunzone(tq_absentset);
		tq_absentset = "";
		forceinfokey(world, "tournament_starts", "");
		tq_autorefused = (cvar_string("tournament_noauto") == id); // an older surfd refused it earlier in this match
		forceinfokey(world, "tournament_auto", (tq_autorefused || cvar("tournament_autostart") <= 0) ? "0" : "");
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
				Tour_Avatar(e);
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
	if (changed || phasechanged) Tour_Announce(prev, oldphase);
	if (strlen(prev)) strunzone(prev);
	if (strlen(oldphase)) strunzone(oldphase);
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
	actor = world; // state polls carry no token; find() on "" warns on every reply
	if (strlen(tq_pendingtoken)) actor = find(world, social_token, tq_pendingtoken);
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
	{
		tq_arrived = TRUE;
		tq_arrivedat = time;
	}
	// A surfd without P1650 refuses the server's autostart (HTTP 200, no token): this map falls back
	// to the manual buttons, and clients are told (serverinfo tournament_auto 0).
	if (tq_pendingop == "autostart")
	{
		if (!ok && !tq_autorefused && strstrofs(json_get_string(json_find_object_child(root, "error")), "token required", 0) >= 0)
		{
			tq_autorefused = TRUE;
			cvar_set("tournament_noauto", tq_id);
			forceinfokey(world, "tournament_auto", "0"); forceinfokey(world, "tournament_starts", "");
			bprint(PRINT_CHAT, strcat(TQ_SAY, "Automatic start isn't available here: each player presses F6 and clicks Ready on map, then the host clicks Start round.\n"));
		}
		else if (ok) forceinfokey(world, "tournament_auto", "1");
		else if (!ok)
		{
			print(strcat("tournament: autostart refused: ", json_get_string(json_find_object_child(root, "error")), "\n"));
			tq_autofails = tq_autofails + 1;
			tq_allreadyat = tq_startsent = tq_startskind = 0; forceinfokey(world, "tournament_starts", "");
			if (tq_autofails >= 3 && !tq_autorefused)
			{
				tq_autorefused = TRUE;
				forceinfokey(world, "tournament_auto", "0");
				bprint(PRINT_CHAT, strcat(TQ_SAY, "The automatic start keeps failing: each player presses F6 and clicks Ready on map, then the host clicks Start round.\n"));
			}
		}
	}
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
	// P1649: a newcomer must learn why a finish did not count, not just see no time appear.
	if (e.run_t_finleg != 1) { Tour_Tell(e, "Only full runs of the main course count in the tournament, not bonuses or single stages."); return; }
	if (FS_RunClass(e.run_t_finflags) != RC_CLEAN)
	{
		Tour_Tell(e, sprintf("That was a %s run, so it doesn't count. Restart and run the map straight through from the start.",
			FS_RunClassName(FS_RunClass(e.run_t_finflags))));
		return;
	}
	// Clean is not enough: resumed from a park, paused to spectate, or uncertified (slow clock, no ruleset...) runs
	// do not score. A journal opt-out (TF_NOJOURNAL) scores but is noted (Lex 20 Nov: allow, note, not on the board).
	if (e.run_t_finflags & (TF_MULTISESSION | TF_SPEC | (TF_UNCERT - TF_NOJOURNAL)))
	{
		Tour_Tell(e, "That run can't count: it was resumed, paused to spectate, or not certified. Restart and run it in one go.");
		return;
	}
	if (!(e.run_t_finticks > 0 && e.run_t_finticks < 16000000) || e.run_movetickrate <= 0) return;
	if (e.tq_best > 0 && e.run_t_finticks >= e.tq_best) return;
	rate = 1 / e.run_movetickrate;
	if (fabs(e.run_movetickrate - run_t_tick) > 0.0000001) return;
	e.tq_best = e.run_t_finticks;
	e.tq_nojournal = (e.run_t_finflags & TF_NOJOURNAL) ? TRUE : FALSE;
	if (e.tq_nojournal)
	{
		// Lex 20 Nov: allowed, noted, not ranked. Privately: the bit is also set when a client never reported.
		Tour_Tell(e, "Your time counts for the tournament. Input recording was off, so it won't be ranked on the leaderboard.");
		print(sprintf("tournament: %s scored with input recording off (TF_NOJOURNAL; not ranked)\n", e.acct_who));
	}
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
		if (!stof(infokey(e, "*spectator"))) { forceinfokey(e, "*tqspec", "1"); }
		forceinfokey(e, "*spectator", "1");
		e.solid = SOLID_NOT;
		Lobby_AvatarFree(e);
		return TRUE;
	}
	if (e.tq_hold)
	{
		SV_SpecRelease(e, "tournament"); // a respawn and `spec` in one packet could start one inside the hold (review)
		e.run_pmhold = TRUE;
		e.movetype = MOVETYPE_NONE;
		e.velocity = '0 0 0';
		return TRUE;
	}
	return FALSE;
};

float(entity e, float argc) Tour_Command =
{
	local float i;
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
		// Nobody is ready in surfd before autostart, so the host's Start means "start now" through it.
		if (op == "start" && e.acct_who == tq_host && tq_phase == "loading" && !tq_autorefused && cvar("tournament_autostart") > 0)
		{
			if (tq_canstart) { tq_startnow = TRUE; Tour_Tell(e, "Starting now."); }
			else Tour_Tell(e, "Waiting for everyone to arrive; the round then starts by itself.");
			return TRUE;
		}
	}
	// A full queue breaks the match (Tour_Queue): players' own requests stop well short of it, and a
	// non-competitor holds at most one queued request (server ops need an empty queue to go out).
	if (tq_qwrite - tq_qread > 32 || time < tq_drainat + 3) { Tour_Tell(e, "The tournament is busy; try again in a moment."); return TRUE; }
	if (strlen(tq_id) && strlen(e.acct_who))
	{
		if (e.tq_role != 1)
		{
			if (time < e.tq_speccmd && op != "leave") return TRUE;
			e.tq_speccmd = time + 3;
		}
		for (i = tq_qread; i < tq_qwrite; i = i + 1)
			if (bufstr_get(tq_queue, i * 4 + 2) == e.acct_who) { Tour_Tell(e, "Your last request is still being sent."); return TRUE; }
	}
	Tour_Queue(op, data, e);
	return TRUE;
};

// P1648: a dedicated server keeps every model NAME it ever loaded (gl_model.c mod_known, 8192 slots; Mod_Purge frees
// data, never the slot), so one lobby process dies of MAX_MOD_KNOWN after ~17-36 maps (tournament_qualify_live's
// measure). An empty, unreserved lobby quits past its cap and systemd (Restart=always) brings it back clean; a
// tournament lobby's lower cap makes every match (<= 8 loads) start on a fresh process.
float tq_mlcounted, tq_mlquit;
void() Tour_Recycle =
{
	local float loads, cap;
	Tour_Cvars();
	if (!tq_mlcounted)
	{
		tq_mlcounted = TRUE;
		registercvar("lobby_maploads", "0"); // QC cvars outlive the progs: one count per process
		registercvar("lobby_maploads_max", "12");
		registercvar("lobby_maploads_tour", "4");
		cvar_set("lobby_maploads", ftos(cvar("lobby_maploads") + 1));
	}
	if (tq_mlquit || !cvar("lobby_enable")) return;
	loads = cvar("lobby_maploads");
	if (cvar("tournament_enable")) cap = cvar("lobby_maploads_tour");
	else cap = cvar("lobby_maploads_max");
	if (cap <= 0 || loads < max(3, cap)) return; // >= 3: a quit every map would trip systemd's StartLimitBurst
	// Empty for 120 s of this map: a run post or a directed arrival is never cut off (P1648 review).
	if (Tour_Owns() || Tour_Occupants()) { tq_emptysince = 0; return; }
	if (!tq_emptysince) tq_emptysince = time;
	if (time - tq_emptysince < 120) return;
	tq_mlquit = TRUE;
	print(sprintf("lobby: %g map loads in this process and nobody here: restarting before the model table fills\n", loads));
	localcmd("quit\n");
};

// P1648: players had no way to reach the in-game Ready/Start buttons (F6 was bound only in the playtest).
// The server starts the round itself, tournament_autostart seconds after every competitor is on the arrived
// map (P1650 surfd's server-only autostart readies those present). A competitor missing for 60 s on end, at
// least 120 s after arrival, is named in `absent` and forfeited -- but not while anyone on the server is still
// connecting or being verified (a map download, an account check), unless that drags past 300 s. Players' and
// the host's own Ready/Start still work (the host's Start in auto mode means start now).
void() Tour_AutoReady =
{
	local int root, players, row;
	local float i, n, here, absent, delay, waiting, forfeit;
	local entity e;
	local string who, gone, names, nm;
	if (time < tq_readyscanat && !tq_startnow) return;
	tq_readyscanat = time + 1;
	waiting = 0; // connected clients not yet known (downloading, connecting, unverified)
	for (i = 1; i <= TQ_CLIENT_MAX; i = i + 1)
	{
		e = edict_num(i);
		if (clienttype(e) == CLIENTTYPE_NOTACLIENT) break;
		if (clienttype(e) == CLIENTTYPE_REAL && (!strlen(e.acct_who) || e.acct_state != ACCT_LINKED)) waiting = waiting + 1;
	}
	root = json_parse(tq_json);
	players = json_find_object_child(json_find_object_child(root, "match"), "players");
	n = here = absent = 0; gone = names = "";
	for (i = 0; i < min(72, json_get_length(players)); i = i + 1)
	{
		row = json_get_child_at_index(players, i);
		if (json_get_string(json_find_object_child(row, "role")) != "player") continue;
		n = n + 1;
		who = json_get_string(json_find_object_child(row, "who"));
		e = Tour_Client(who);
		if (json_get_float(json_find_object_child(row, "ready")) || (e && e.acct_state == ACCT_LINKED)) { here = here + 1; continue; }
		if (!SV_RecIsHex(who, FS_WHO_IDLEN)) continue; // checks the length too (sv_timer.qc SV_RecIsHex)
		absent = absent + 1;
		nm = substring(json_get_string(json_find_object_child(row, "name")), 0, 32);
		gone = strlen(gone) ? strcat(gone, ",", who) : who;
		names = strlen(names) ? strcat(names, ", ", nm) : nm;
	}
	if (root) json_free(root);
	if (gone != tq_absentset) // the missing set changed: a fresh grace; a fresh warning if someone new is missing
	{
		for (i = 0; i < strlen(gone); i = i + FS_WHO_IDLEN + 1)
			if (strstrofs(tq_absentset, substring(gone, i, FS_WHO_IDLEN), 0) < 0) tq_absentwarned = tq_allreadyat = 0;
		if (strlen(tq_absentset)) strunzone(tq_absentset);
		tq_absentset = strlen(gone) ? strzone(gone) : "";
		tq_absentsince = min(time, tq_arrivedat + 240); // capped: leaving and rejoining cannot stall past +300
	}
	if (waiting < tq_waitprev) tq_absentsince = min(time, tq_arrivedat + 240); // a downloader dropped
	tq_waitprev = waiting;
	forfeit = (absent && time >= tq_arrivedat + 120 && time >= tq_absentsince + 60 && (!waiting || time >= tq_arrivedat + 300));
	delay = cvar("tournament_autostart");
	if (absent && !tq_absentwarned && time > tq_arrivedat + 30 && delay > 0 && !tq_autorefused)
	{
		tq_absentwarned = TRUE;
		bprint(PRINT_CHAT, sprintf("%sWaiting for ^3%s^7 to arrive. If they don't make it, the round starts without them.\n", TQ_SAY, names));
	}
	tq_canstart = (n && here + absent == n && (!absent || forfeit));
	if (!tq_canstart || delay <= 0 || tq_autorefused)
	{
		if (serverkey("tournament_starts") != "") forceinfokey(world, "tournament_starts", "");
		tq_allreadyat = tq_startskind = 0; tq_startnow = FALSE;
		return;
	}
	if (tq_allreadyat && tq_startskind != (absent ? 2 : 1)) // someone arrived (or left) during the countdown
	{
		tq_startskind = absent ? 2 : 1;
		forceinfokey(world, "tournament_starts", ftos(tq_startskind));
	}
	if (!tq_allreadyat)
	{
		tq_allreadyat = time; tq_startskind = absent ? 2 : 1;
		forceinfokey(world, "tournament_starts", ftos(tq_startskind)); // 2 = starting without someone
		if (absent) bprint(PRINT_CHAT, sprintf("%s^5Starting without ^3%s^5 in %g seconds.^7\n", TQ_SAY, names, delay));
		else bprint(PRINT_CHAT, sprintf("%s^5Everyone is here.^7 Round %g starts in %g seconds.\n", TQ_SAY, tq_round, delay));
	}
	if (time < tq_startsent) { tq_startnow = FALSE; return; }
	if (!tq_startnow && time < tq_allreadyat + delay) return;
	if ((tq_request && tq_pendingop != "state") || tq_qread != tq_qwrite) { tq_drainat = time; return; } // players' requests pause (Tour_Command)
	tq_startsent = time + 15; tq_startnow = FALSE;
	Tour_Queue("autostart", strcat("&absent=", gone), world);
	tq_pollat = min(tq_pollat, time);
};

void() Tour_Frame =
{
	local float i;
	local entity e;
	Tour_Recycle();
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
			// P1648: rounds no longer need the host once loading (auto-ready/start below), so a host
			// gone only stops the server-side create flow's lobby and draft.
			if ((tq_phase == "lobby" && time - tq_phaseat > 900) ||
			    (tq_phase == "draft" && time - tq_turnat > 60))
			{
				tq_broken = TRUE;
				Tour_Queue("abort", "&reason=alpha_lobby_timeout", world);
			}
			else if (tq_phase == "loading" && time - tq_phaseat > TQ_LOAD_LIMIT)
			{
				tq_broken = TRUE;
				Tour_Queue("abort", "&reason=loading_timeout", world);
			}
			else if (tq_hostgone && time - tq_hostgone > ((tq_phase == "loading") ? ((tq_autorefused || cvar("tournament_autostart") <= 0) ? 120 : TQ_LOAD_LIMIT) : TQ_HOST_LIMIT))
			{
				tq_broken = TRUE;
				Tour_Queue("abort", "&reason=host_gone", world);
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
		if (tq_phase == "loading" && tq_arrived && !tq_broken) Tour_AutoReady();
		// P1648: a competitor who drops during the countdown no longer aborts everyone's match;
		// they simply cannot finish the round (a non-finisher under surfd's settle).
		if (tq_phase == "countdown" && !tq_broken)
		{
			if (time >= tq_countat && (tq_qread != tq_qwrite || tq_request)) tq_drainat = time;
			if (time >= tq_countat && tq_qread == tq_qwrite && !tq_request)
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
