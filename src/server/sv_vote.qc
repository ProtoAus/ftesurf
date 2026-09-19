/*
===========================================================================
  sv_vote.qc -- the map clock's votes.  Patch 372.

  The time limit is Lobby_Cycle's (sv_lobby.qc); this file decides what it
  changes to, and when a vote pushes it.  Four ways in:
    - the end-of-map vote, lobby_vote_start seconds before the deadline: the
      rotation's next maps (nominations first) plus Extend while extensions
      remain;
    - !rtv: once lobby_rtv_ratio of the players ask, a map vote whose result
      changes the map in ten seconds WITHOUT the Patch 366 hold (the runs park
      as `rotate`, so !resume continues them);
    - !extend: a yes/no vote on lobby_extend_time more;
    - !nominate <map>: one entry of this lobby's lobby_maps onto the next ballot.
  Plus !timeleft and !nextmap, and `cmd` twins of all of them.

  The shared state Lobby_Cycle reads (lobby_vt_*) is declared in sv_lobby.qc,
  which compiles first; every call runs downhill.  The client reads serverinfo
  (grammar: sh_defs.qc, VOTE_*), written only by Vote_Publish.

  A CHANGE A VOTE DECIDES IS ALWAYS EXECUTED BY Lobby_Cycle, from StartFrame:
  that is what keeps lobby_cyc_moving TRUE into SV_Shutdown, so the runs it
  interrupts park as `rotate` -- a changelevel issued from a client command
  runs before StartFrame clears it and would park them as `server`.
===========================================================================
*/

.float  vote_here;              // spawned in (ClientConnect ran; spectators never do)
.float  vote_pick, vote_pickid; // option n in vote id
.float  vote_pkpub;             // the *vpick last published, id*10 + n
.float  vote_rtv;
.string vote_nom;               // a zoned lobby_maps entry, "" none
.float  vote_nomseq;            // order of nomination: oldest go on the ballot first
.float  vote_cmdat;             // next chat command taken (the engine's flood control never sees them)
.float  vote_echoat;            // next cast echoed to the log

float  vote_init, vote_t0, vote_on;
float  vote_id, vote_end, vote_n, vote_optx, vote_cool, vote_extn, vote_rtvgo;
float  vote_nomseqn, vote_pubat, vote_dirty;
string vote_opt[VOTE_MAX];      // zoned map names; the Extend row has none
float  vote_cnt[VOTE_MAX];

void() Vote_Cvars =
{
	// Beside the read: StartFrame precedes worldspawn (Lobby_Frame's essay).
	registercvar("lobby_vote", "1");
	registercvar("lobby_vote_start", "180");
	registercvar("lobby_vote_time", "25");
	registercvar("lobby_vote_maps", "5");
	registercvar("lobby_vote_cooldown", "120");
	registercvar("lobby_extend_time", "600");
	registercvar("lobby_extend_max", "2");
	registercvar("lobby_rtv_ratio", "0.6");
	registercvar("lobby_rtv_delay", "60");
};

float() Vote_Time = { return bound(10, cvar("lobby_vote_time"), 45); };
float() Vote_Step = { return bound(60, cvar("lobby_extend_time"), 3600); };

float(entity p) Vote_IsLive =
{
	return p.vote_here && clienttype(p) == CLIENTTYPE_REAL;
};

float() Vote_Live =
{
	local entity p;
	local float n;

	n = 0;
	p = find(world, classname, "player");
	while (p)
	{
		if (Vote_IsLive(p))
			n = n + 1;
		p = find(p, classname, "player");
	}
	return n;
};

void(entity p, string s) Vote_Tell =
{
	sprint(p, PRINT_CHAT, strcat("^5vote:^7 ", s, "\n"));
};

// Held for runs: the deadline has passed and Lobby_Cycle is waiting (an
// extension in a hold keeps hold0, the cap, with the deadline ahead again).
float() Vote_Held =
{
	return lobby_cyc_hold0 && lobby_cyc_next <= time;
};

// The change is already on its way: forced, issued, or a timed one inside ten seconds.
float() Vote_Changing =
{
	if (lobby_cyc_moving || lobby_vt_force || lobby_cyc_holdend)
		return TRUE;
	if (!Vote_Held())
	if (lobby_cyc_next)
	if (lobby_cyc_next - time <= 10)
	if (time - lobby_cyc_runseen >= 2)
		return TRUE;
	return FALSE;
};

// want (any case) -> the lobby_maps entry as spelled there (the Pi's filesystem
// is case-sensitive); exact first, else a unique substring.  "" none, "?a b c"
// ambiguous.  Tokenizes.
string(string want) Vote_MapFind =
{
	local float n, i, hits;
	local string lw, hit, names;

	lw = strtolower(want);
	n = tokenize(cvar_string("lobby_maps"));
	for (i = 0; i < n; i = i + 1)
		if (strcasecmp(argv(i), lw) == 0)
			return argv(i);
	hits = 0;
	hit = "";
	names = "";
	for (i = 0; i < n; i = i + 1)
		if (strstrofs(strtolower(argv(i)), lw, 0) >= 0)
		{
			hits = hits + 1;
			hit = argv(i);
			if (hits <= 3)
				names = strcat(names, " ", argv(i));
		}
	if (hits == 1)
		return hit;
	if (hits > 1)
		return strcat("?", names);
	return "";
};

float(string m, float n) Vote_Usable =
{
	local float i;

	if (m == "" || strcasecmp(m, mapname) == 0)
		return FALSE;
	for (i = 0; i < n; i = i + 1)
		if (strcasecmp(vote_opt[i], m) == 0)
			return FALSE;
	return TRUE;
};

void() Vote_ClearOpts =
{
	local float i;

	for (i = 0; i < VOTE_MAX; i = i + 1)
	{
		if (vote_opt[i] != "")
			strunzone(vote_opt[i]);
		vote_opt[i] = "";
		vote_cnt[i] = 0;
	}
	vote_n = 0;
	vote_optx = 0;
};

// Nominations oldest first, then the rotation's following maps; returns the count.
float(float lim) Vote_BuildMaps =
{
	local float n, i, k, cur, cnt, last;
	local entity p, pick;
	local string m;

	n = 0;
	last = 0;
	while (n < lim)
	{
		pick = world;
		p = find(world, classname, "player");
		while (p)
		{
			if (Vote_IsLive(p))
			if (p.vote_nom != "")
			if (p.vote_nomseq > last)
			if (!pick || p.vote_nomseq < pick.vote_nomseq)
				pick = p;
			p = find(p, classname, "player");
		}
		if (!pick)
			break;
		last = pick.vote_nomseq;
		m = Vote_MapFind(pick.vote_nom);        // lobby_maps may have changed since
		if (strcmp(m, pick.vote_nom) == 0)
		if (Vote_Usable(m, n))
		{
			vote_opt[n] = strzone(m);
			n = n + 1;
		}
	}

	cnt = tokenize(cvar_string("lobby_maps"));
	cur = -1;                                   // off the list: from the top, as Lobby_RotNext
	for (i = 0; i < cnt; i = i + 1)
		if (strcmp(argv(i), mapname) == 0)
			cur = i;
	for (k = 1; k <= cnt; k = k + 1)
	{
		if (n >= lim)
			break;
		i = cur + k;
		while (i >= cnt)
			i = i - cnt;
		m = argv(i);
		if (Vote_Usable(m, n))
		{
			vote_opt[n] = strzone(m);
			n = n + 1;
		}
	}
	return n;
};

string(float i) Vote_Label =
{
	if (lobby_vt_kind == VOTE_EXTEND)
		return (i == 0) ? "Yes" : "No";
	if (i + 1 == vote_optx)
		return sprintf("Extend +%g min", Vote_Step() / 60);
	return vote_opt[i];
};

// Tallies over live players' picks in this vote; returns how many voted.
float() Vote_Tally =
{
	local entity p;
	local float i, v;

	for (i = 0; i < VOTE_MAX; i = i + 1)
		vote_cnt[i] = 0;
	v = 0;
	p = find(world, classname, "player");
	while (p)
	{
		if (Vote_IsLive(p))
		if (p.vote_pickid == vote_id)
		if (p.vote_pick >= 1)
		if (p.vote_pick <= vote_n)
		{
			vote_cnt[p.vote_pick - 1] = vote_cnt[p.vote_pick - 1] + 1;
			v = v + 1;
		}
		p = find(p, classname, "player");
	}
	return v;
};

string() Vote_Counts =
{
	local float i;
	local string s;

	s = "";
	for (i = 0; i < vote_n; i = i + 1)
		s = (i == 0) ? ftos(vote_cnt[i]) : strcat(s, " ", ftos(vote_cnt[i]));
	return s;
};

void() Vote_RtvClear =
{
	local entity p;

	vote_rtvgo = FALSE;
	p = find(world, classname, "player");
	while (p)
	{
		p.vote_rtv = FALSE;
		p = find(p, classname, "player");
	}
};

float() Vote_RtvCount =
{
	local entity p;
	local float n;

	n = 0;
	p = find(world, classname, "player");
	while (p)
	{
		if (Vote_IsLive(p))
		if (p.vote_rtv)
			n = n + 1;
		p = find(p, classname, "player");
	}
	return n;
};

// ceil(ratio * players), less an epsilon: 0.6f * 5 is 3.0000001.
float(float live) Vote_RtvNeed =
{
	local float n;

	n = ceil(bound(0.01, cvar("lobby_rtv_ratio"), 1) * live - 0.0001);
	if (n < 1)
		n = 1;
	return n;
};

// m is always a vote_opt[] entry, never lobby_vt_next itself.
void(string m) Vote_Decide =
{
	if (lobby_vt_next != "")
		strunzone(lobby_vt_next);
	lobby_vt_next = strzone(m);
	vote_dirty = TRUE;
};

void() Vote_Force =
{
	local string nxt;

	lobby_vt_force = time + 10;
	Vote_RtvClear();
	vote_dirty = TRUE;
	nxt = Lobby_NextMap();
	if (time - lobby_cyc_runseen < 2)
		bprint(PRINT_CHAT, sprintf("^3lobby:^7 %s in ten seconds -- runs still going are "
		       "paused; !resume on %s continues them\n", nxt, mapname));
	else
		bprint(PRINT_CHAT, sprintf("^3lobby:^7 %s in ten seconds\n", nxt));
	print(sprintf("vote: forced change to %s\n", nxt));
};

/*
  An extension moves the deadline and widens Lobby_Cycle's pull-in cap by the
  same amount.  In a hold the deadline has passed: it restarts from now, and
  hold0 stays, so the Patch 366 cap is not restarted by extending.
*/
void(string why) Vote_Extend =
{
	local float step;

	step = Vote_Step();
	vote_extn = vote_extn + 1;
	lobby_vt_ext = lobby_vt_ext + step;
	lobby_cyc_next = max(lobby_cyc_next, time) + step;
	if (lobby_cyc_hold0)
	{
		lobby_cyc_holdwarn = FALSE;
		lobby_cyc_holdend = FALSE;
	}
	lobby_cyc_warn = Lobby_WarnLvl(lobby_cyc_next - time);
	lobby_vt_emap = FALSE;                      // it votes again before the new deadline
	Vote_RtvClear();
	vote_dirty = TRUE;
	bprint(PRINT_CHAT, sprintf("^5vote:^7 extended -- %g more minutes on %s (%s)\n",
	       step / 60, mapname, why));
};

void(float kind, entity caller) Vote_Open =
{
	local float t, n, i;
	local string ln;

	Vote_ClearOpts();
	t = Vote_Time();
	n = 2;
	if (kind != VOTE_EXTEND)
	{
		n = Vote_BuildMaps(bound(1, cvar("lobby_vote_maps"), VOTE_MAX - 1));
		if (kind == VOTE_EMAP)
		{
			lobby_vt_emap = TRUE;
			if (vote_extn < cvar("lobby_extend_max"))
			{
				n = n + 1;
				vote_optx = n;
			}
		}
		if (kind == VOTE_RTV)
			Vote_RtvClear();
		if (n < 2)                              // nothing to choose between
		{
			if (kind == VOTE_RTV)
			if (vote_opt[0] != "")
			{
				bprint(PRINT_CHAT, "^5vote:^7 rock the vote passed\n");
				Vote_Decide(vote_opt[0]);
				Vote_Force();
			}
			Vote_ClearOpts();
			return;
		}
	}

	vote_n = n;
	vote_id = vote_id + 1;
	vote_end = time + t;
	lobby_vt_kind = kind;
	vote_dirty = TRUE;
	if (caller)                                 // !extend's caller votes yes
	{
		caller.vote_pick = 1;
		caller.vote_pickid = vote_id;
	}
	// The deadline never fires mid-vote (t is at most 45, under the 60 s floor),
	// and the warnings restart from where it now stands.
	if (!Vote_Held())
	if (lobby_cyc_next)
	if (lobby_cyc_next < vote_end + 10)
	{
		lobby_cyc_next = vote_end + 10;
		lobby_cyc_warn = Lobby_WarnLvl(lobby_cyc_next - time);
	}

	ln = "";
	for (i = 0; i < n; i = i + 1)
		ln = strcat(ln, sprintf(" %g %s", i + 1, Vote_Label(i)));
	print(sprintf("vote: open #%g kind %g, %g s:%s\n", vote_id, kind, t, ln));
	if (kind == VOTE_EXTEND)
		bprint(PRINT_CHAT, sprintf("^5vote:^7 %s asks for %g more minutes on %s -- "
		       "1 yes, 2 no (%g s)\n", Lobby_ChatName(caller), Vote_Step() / 60, mapname, t));
	else if (kind == VOTE_RTV)
		bprint(PRINT_CHAT, sprintf("^5vote:^7 rock the vote passed -- pick the next map, "
		       "keys 1-%g (%g s)\n", n, t));
	else
		bprint(PRINT_CHAT, sprintf("^5vote:^7 vote for the next map -- keys 1-%g (%g s)\n", n, t));
};

// Most votes wins and a tie goes to the option listed first -- except !extend,
// which needs more yes than no.  No votes never extends: an end-of-map vote
// keeps the rotation's next map, an !rtv vote takes its first option.
void() Vote_Close =
{
	local float k, i, total, best, bestc;
	local string res;

	k = lobby_vt_kind;
	Vote_Tally();
	total = 0;
	best = 0;
	bestc = 0;
	for (i = 0; i < vote_n; i = i + 1)
	{
		total = total + vote_cnt[i];
		if (vote_cnt[i] > bestc)
		{
			best = i + 1;
			bestc = vote_cnt[i];
		}
	}
	lobby_vt_kind = 0;
	vote_cool = time + cvar("lobby_vote_cooldown");
	vote_dirty = TRUE;
	print(sprintf("vote: close #%g kind %g tally %s\n", vote_id, k, Vote_Counts()));

	if (k == VOTE_EXTEND)
	{
		res = sprintf("%g yes, %g no", vote_cnt[0], vote_cnt[1]);
		if (vote_cnt[0] > vote_cnt[1])
			Vote_Extend(res);
		else
			bprint(PRINT_CHAT, sprintf("^5vote:^7 no extension (%s)\n", res));
	}
	else if (best && best == vote_optx)
		Vote_Extend(sprintf("%g of %g votes", bestc, total));
	else if (best)
	{
		bprint(PRINT_CHAT, sprintf("^5vote:^7 %s wins (%g of %g votes)\n",
		       vote_opt[best - 1], bestc, total));
		Vote_Decide(vote_opt[best - 1]);
		if (k == VOTE_RTV)
			Vote_Force();
	}
	else if (Vote_Live() < 1)
	{
		if (k == VOTE_EMAP)
			lobby_vt_emap = FALSE;              // nobody was here to ask: ask again
	}
	else if (k == VOTE_RTV)
	{
		bprint(PRINT_CHAT, sprintf("^5vote:^7 no votes -- %s is next\n", vote_opt[0]));
		Vote_Decide(vote_opt[0]);
		Vote_Force();
	}
	else
		bprint(PRINT_CHAT, sprintf("^5vote:^7 no votes -- %s is next\n", Lobby_NextMap()));
	Vote_ClearOpts();
};

void() Vote_Cancel =
{
	lobby_vt_kind = 0;
	Vote_ClearOpts();
	vote_dirty = TRUE;
	if (Lobby_PlayerCount() > 0)
		bprint(PRINT_CHAT, "^5vote:^7 vote cancelled\n");
};

void() Vote_RtvAct =
{
	if (Vote_Changing())
	{
		Vote_RtvClear();
		return;
	}
	if (lobby_vt_next != "")
	{
		bprint(PRINT_CHAT, "^5vote:^7 rock the vote passed\n");
		Vote_Force();
		return;
	}
	Vote_Open(VOTE_RTV, world);
};

// ---- serverinfo (grammar: sh_defs.qc) ---------------------------------------

string() Vote_ClockKey =
{
	if (!vote_on || !lobby_cyc_next)
		return "";
	if (lobby_vt_force)
		return sprintf("%.1f 2", lobby_vt_force);
	if (lobby_cyc_holdend)
	if (lobby_cyc_next < time + 11)
		return sprintf("%.1f 2", lobby_cyc_next);
	if (lobby_cyc_hold0)
	if (lobby_cyc_next <= time)
		return sprintf("%.1f 1", lobby_cyc_hold0 + cvar("lobby_cycle_hold"));
	return sprintf("%.1f 0", lobby_cyc_next);
};

/*
  Every key on each 0.25 s compose, or at once when something changed: the
  engine sends a key only when its value differs (pr_cmds.c:9969), and the
  first compose of a map clears what the last map left (serverinfo outlives a
  changelevel).  While a vote runs its id goes last, after the rows it names.
*/
void() Vote_Publish =
{
	local float i, v;
	local entity p;
	local string lab;

	if (!vote_dirty)
	if (time < vote_pubat)
		return;
	vote_dirty = FALSE;
	vote_pubat = time + 0.25;

	forceinfokey(world, "mapclock", Vote_ClockKey());
	forceinfokey(world, "mapnext", vote_on ? Lobby_NextMap() : "");
	if (!lobby_vt_kind)
		forceinfokey(world, "vote", "");
	for (i = 0; i < VOTE_MAX; i = i + 1)
	{
		lab = "";
		if (lobby_vt_kind)
		if (i < vote_n)
			lab = Vote_Label(i);
		forceinfokey(world, strcat("vote", ftos(i + 1)), lab);
	}
	forceinfokey(world, "votec", lobby_vt_kind ? Vote_Counts() : "");
	if (lobby_vt_kind)
		forceinfokey(world, "vote", sprintf("%g %g %.1f %g", vote_id, lobby_vt_kind, vote_end, vote_n));

	// Each player's own pick, so their panel shows what the server holds.
	p = find(world, classname, "player");
	while (p)
	{
		v = 0;
		if (lobby_vt_kind)
		if (p.vote_pickid == vote_id)
			v = p.vote_pickid * 10 + p.vote_pick;
		if (v != p.vote_pkpub)
		if (clienttype(p) == CLIENTTYPE_REAL)
		{
			p.vote_pkpub = v;
			forceinfokey(p, "*vpick", v ? sprintf("%g %g", p.vote_pickid, p.vote_pick) : "");
		}
		p = find(p, classname, "player");
	}
};

void() Vote_Frame =
{
	local float live, c, left;

	Vote_Cvars();
	if (!vote_init)
	{
		vote_init = TRUE;
		vote_t0 = time;
	}
	if (lobby_cyc_moving)
		return;                                 // the change is issued: nothing opens on its frame
	vote_on = cvar("lobby_cycle") > 0 && Lobby_RotNext() != "";
	if (!vote_on || !cvar("lobby_vote"))
	{
		if (lobby_vt_kind)
			Vote_Cancel();
		if (!vote_on)
			lobby_vt_force = 0;
		Vote_RtvClear();
		Vote_Publish();
		return;
	}

	live = Vote_Live();
	if (Lobby_PlayerCount() < 1)
		lobby_vt_force = 0;                     // a broker claim may move an empty lobby itself

	if (lobby_vt_kind)
	{
		c = Vote_Tally();
		if (time >= vote_end || live < 1 || c >= live)
			Vote_Close();
	}

	if (!vote_rtvgo)
	if (live >= 1)
	if (cvar("lobby_rtv_ratio") > 0)        // switched off: nobody's earlier !rtv counts
	{
		c = Vote_RtvCount();
		if (c >= 1)
		if (c >= Vote_RtvNeed(live))
		{
			vote_rtvgo = TRUE;
			print(sprintf("vote: rtv passed %g of %g\n", c, live));
		}
	}
	if (vote_rtvgo)
	if (!lobby_vt_kind)
	if (!lobby_vt_force)
		Vote_RtvAct();

	// The end-of-map vote; a cooldown yields at its last chance.
	if (!lobby_vt_kind)
	if (!lobby_vt_force)
	if (!lobby_vt_emap)
	if (lobby_vt_next == "")
	if (live > 0)
	if (lobby_cyc_next)
	if (cvar("lobby_vote_start") > 0)
	if (!Vote_Changing())
	{
		left = lobby_cyc_next - time;
		if (left <= cvar("lobby_vote_start"))
		if (time >= vote_cool || left <= Vote_Time() + 15)
			Vote_Open(VOTE_EMAP, world);
	}

	Vote_Publish();
};

// ---- player commands ----------------------------------------------------------

void(entity p) Vote_TimeLeft =
{
	local float left;
	local string s;

	if (!vote_on || !lobby_cyc_next)
	{
		sprint(p, PRINT_CHAT, "^5lobby:^7 no time limit here\n");
		return;
	}
	if (lobby_vt_force)
	{
		sprint(p, PRINT_CHAT, sprintf("^5lobby:^7 %s in %g seconds\n", Lobby_NextMap(),
		       ceil(lobby_vt_force - time)));
		return;
	}
	left = lobby_cyc_next - time;
	if (left <= 0)
	if (lobby_cyc_hold0)
	{
		sprint(p, PRINT_CHAT, sprintf("^5lobby:^7 time is up -- %s waits for the runs in "
		       "progress (at most %s more)\n", Lobby_NextMap(),
		       Time_Clock(lobby_cyc_hold0 + cvar("lobby_cycle_hold") - time)));
		return;
	}
	s = sprintf("^5lobby:^7 %s left on %s", Time_Clock(left), mapname);
	if (lobby_vt_next != "")
		s = strcat(s, " -- next: ", lobby_vt_next);
	sprint(p, PRINT_CHAT, strcat(s, "\n"));
};

void(entity p) Vote_NextMapSay =
{
	if (!vote_on)
		sprint(p, PRINT_CHAT, "^5lobby:^7 no map rotation here\n");
	else if (lobby_vt_next != "")
		sprint(p, PRINT_CHAT, sprintf("^5lobby:^7 next map is %s (voted)\n", lobby_vt_next));
	else if (lobby_vt_kind == VOTE_EMAP || lobby_vt_kind == VOTE_RTV)
		sprint(p, PRINT_CHAT, "^5lobby:^7 a map vote is running -- pick with the number keys\n");
	else if (!lobby_vt_emap && cvar("lobby_vote") && cvar("lobby_vote_start") > 0)
		sprint(p, PRINT_CHAT, sprintf("^5lobby:^7 next map is %s -- the map vote opens %s "
		       "before the end\n", Lobby_RotNext(), Time_Clock(cvar("lobby_vote_start"))));
	else
		sprint(p, PRINT_CHAT, sprintf("^5lobby:^7 next map is %s\n", Lobby_NextMap()));
};

void(entity p) Vote_MapList =
{
	local float n, i;
	local string s;

	n = tokenize(cvar_string("lobby_maps"));
	s = "";
	for (i = 0; i < n; i = i + 1)
		if (strcasecmp(argv(i), mapname) != 0)
			s = strcat(s, " ", argv(i));
	Vote_Tell(p, sprintf("!nominate one of%s", s));
};

void(entity p) Vote_Rtv =
{
	local float need;

	if (cvar("lobby_rtv_ratio") <= 0)
		Vote_Tell(p, "rock the vote is off here");
	else if (Vote_Changing())
		Vote_Tell(p, "the map is already changing");
	else if (lobby_vt_kind == VOTE_EMAP || lobby_vt_kind == VOTE_RTV)
		Vote_Tell(p, "a map vote is running -- pick with the number keys");
	else if (vote_rtvgo)
		Vote_Tell(p, "rock the vote already passed");
	else if (time < vote_t0 + cvar("lobby_rtv_delay"))
		Vote_Tell(p, sprintf("rock the vote opens in %g s",
		          ceil(vote_t0 + cvar("lobby_rtv_delay") - time)));
	else
	{
		need = Vote_RtvNeed(Vote_Live());
		if (p.vote_rtv)
		{
			Vote_Tell(p, sprintf("you already asked (%g of %g)", Vote_RtvCount(), need));
			return;
		}
		p.vote_rtv = TRUE;
		bprint(PRINT_CHAT, sprintf("^5vote:^7 %s wants a new map (%g of %g -- !rtv)\n",
		       Lobby_ChatName(p), Vote_RtvCount(), need));
	}
};

void(entity p) Vote_ExtendCall =
{
	if (Vote_Changing())
		Vote_Tell(p, "the map is already changing");
	else if (lobby_vt_kind)
		Vote_Tell(p, "a vote is already running");
	else if (vote_extn >= cvar("lobby_extend_max"))
		Vote_Tell(p, sprintf("no extensions left (%g of %g used)", vote_extn,
		          cvar("lobby_extend_max")));
	else if (time < vote_cool)
		Vote_Tell(p, sprintf("!extend again in %g s", ceil(vote_cool - time)));
	else
		Vote_Open(VOTE_EXTEND, p);
};

void(entity p, string tail) Vote_Nominate =
{
	local float sp, n;
	local string want, shown, m;
	local entity q;

	if (tail == "")
	{
		Vote_MapList(p);
		return;
	}
	sp = strstrofs(tail, " ", 0);
	want = (sp < 0) ? tail : substring(tail, 0, sp);
	shown = Lobby_MapNameOK(want) ? want : "that";
	if (lobby_vt_next != "" || lobby_vt_force)
	{
		Vote_Tell(p, sprintf("the next map is already decided: %s", Lobby_NextMap()));
		return;
	}
	if (lobby_vt_kind == VOTE_EMAP || lobby_vt_kind == VOTE_RTV)
	{
		Vote_Tell(p, "a map vote is running -- pick with the number keys");
		return;
	}
	m = Vote_MapFind(want);
	if (m == "")
	{
		Vote_Tell(p, sprintf("%s is not in this lobby's rotation -- !nominate lists them", shown));
		return;
	}
	if (str2chr(m, 0) == 63)
	{
		Vote_Tell(p, sprintf("%s matches%s -- be more specific", shown,
		          substring(m, 1, strlen(m) - 1)));
		return;
	}
	if (strcasecmp(m, mapname) == 0)
	{
		Vote_Tell(p, sprintf("you are on %s already", m));
		return;
	}
	if (p.vote_nom != "")
	if (strcmp(p.vote_nom, m) == 0)
	{
		Vote_Tell(p, sprintf("you already nominated %s", m));
		return;
	}
	n = 0;
	q = find(world, classname, "player");
	while (q)
	{
		if (q != p)
		if (Vote_IsLive(q))
		if (q.vote_nom != "")
		{
			n = n + 1;
			if (strcmp(q.vote_nom, m) == 0)
			{
				Vote_Tell(p, sprintf("%s is already nominated", m));
				return;
			}
		}
		q = find(q, classname, "player");
	}
	if (n >= bound(1, cvar("lobby_vote_maps"), VOTE_MAX - 1))
	{
		Vote_Tell(p, sprintf("nominations are full (%g)", n));
		return;
	}
	if (p.vote_nom != "")
		strunzone(p.vote_nom);
	p.vote_nom = strzone(m);                    // a new one replaces yours
	vote_nomseqn = vote_nomseqn + 1;
	p.vote_nomseq = vote_nomseqn;
	bprint(PRINT_CHAT, sprintf("^5vote:^7 %s nominated %s\n", Lobby_ChatName(p), m));
};

void(entity p, float n, float id) Vote_Cast =
{
	if (!lobby_vt_kind)
	{
		sprint(p, PRINT_MEDIUM, "vote: no vote running\n");
		return;
	}
	if (id >= 0)
	if (id != vote_id)
	{
		sprint(p, PRINT_MEDIUM, "vote: that vote has closed\n");
		return;
	}
	if (!Vote_IsLive(p))
	{
		sprint(p, PRINT_MEDIUM, "vote: only players in the game can vote\n");
		return;
	}
	n = floor(n);
	if (n < 1 || n > vote_n)
	{
		sprint(p, PRINT_MEDIUM, sprintf("vote: pick 1-%g\n", vote_n));
		return;
	}
	// The latest pick always counts; only the log echo is rate-limited.
	p.vote_pick = n;
	p.vote_pickid = vote_id;
	if (time >= p.vote_echoat)
	{
		p.vote_echoat = time + 0.3;
		print(sprintf("vote: %s^7 picks %g in #%g\n", p.netname, n, vote_id));
	}
};

void(entity p) Vote_SvStatus =
{
	local float i;

	Vote_Tally();
	sprint(p, PRINT_HIGH, sprintf("svvote: on %g kind %g id %g n %g left %.1f\n",
	       vote_on, lobby_vt_kind, vote_id, vote_n, lobby_vt_kind ? vote_end - time : 0));
	sprint(p, PRINT_HIGH, sprintf("svvote: extn %g rtv %g/%g\n",
	       vote_extn, Vote_RtvCount(), Vote_RtvNeed(Vote_Live())));
	for (i = 0; i < vote_n; i = i + 1)
		sprint(p, PRINT_HIGH, sprintf("svvote:  %g %s %g\n", i + 1, Vote_Label(i), vote_cnt[i]));
	sprint(p, PRINT_HIGH, sprintf("svvote: mapclock \"%s\" next \"%s\" left %.1f force %g\n",
	       Vote_ClockKey(), Lobby_NextMap(), lobby_cyc_next - time, lobby_vt_force));
};

// Chat: !rtv !extend !nominate [map] !timeleft !nextmap.  The chatbox's own
// submit arrives as several words (`cmd say $cl_safetmp`), so the tail is also
// rebuilt from argv(from..argc-1) -- before anything here tokenizes.
float(entity p, string w, string tail, float from, float argc) Vote_Say =
{
	local float i;

	if (w != "!rtv") if (w != "!nominate") if (w != "!extend")
	if (w != "!timeleft") if (w != "!nextmap")
		return FALSE;
	for (i = from; i < argc; i = i + 1)
		tail = strcat(tail, " ", strtolower(argv(i)));
	tail = strtrim(tail);
	if (w != "!nominate")
	if (tail != "")
		return FALSE;                           // "!rtv pls" is chat
	Vote_Cvars();
	if (time < p.vote_cmdat)
	{
		Vote_Tell(p, "one command a second");  // the engine's flood control never sees these
		return TRUE;
	}
	p.vote_cmdat = time + 1;
	if (w == "!timeleft")
		Vote_TimeLeft(p);
	else if (w == "!nextmap")
		Vote_NextMapSay(p);
	else if (!vote_on)
		Vote_Tell(p, "no map rotation on this server");
	else if (!cvar("lobby_vote"))
		Vote_Tell(p, "votes are off here");
	else if (!Vote_IsLive(p))
		Vote_Tell(p, "only players in the game can vote");
	else if (w == "!rtv")
		Vote_Rtv(p);
	else if (w == "!extend")
		Vote_ExtendCall(p);
	else
		Vote_Nominate(p, tail);
	return TRUE;
};

// `cmd vote_cast <n> [id]` from the panel (`cmd vote` is its twin: QC shadows
// the engine's own `vote`, sv_user.c:6893), bare for a status dump; plus the
// chat commands' twins, for binds.
float(entity p, string c, float argc) Vote_Command =
{
	local float n, id;

	if (c == "vote_cast" || c == "vote")
	{
		Vote_Cvars();
		if (argc < 2)
		{
			Vote_SvStatus(p);
			return TRUE;
		}
		n = stof(argv(1));
		id = -1;
		if (argc >= 3)
			id = stof(argv(2));
		Vote_Cast(p, n, id);
		return TRUE;
	}
	if (c == "rtv" || c == "extend" || c == "timeleft" || c == "nextmap")
		return Vote_Say(p, strcat("!", c), "", 1, 1);
	if (c == "nominate")
		return Vote_Say(p, "!nominate", "", 1, argc);
	return FALSE;
};

// Every begin, map changes included (edicts are recycled; *vpick outlives a map).
void(entity p) Vote_ClientConnect =
{
	p.vote_here = TRUE;
	p.vote_pick = p.vote_pickid = 0;
	p.vote_rtv = FALSE;
	p.vote_nom = "";
	p.vote_nomseq = 0;
	p.vote_cmdat = p.vote_echoat = 0;
	p.vote_pkpub = 0;
	forceinfokey(p, "*vpick", "");
};

void(entity p) Vote_ClientDisconnect =
{
	p.vote_here = FALSE;
	if (p.vote_nom != "")
		strunzone(p.vote_nom);
	p.vote_nom = "";
	p.vote_rtv = FALSE;
	p.vote_pick = p.vote_pickid = 0;
};
