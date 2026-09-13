/*
===========================================================================
  cl_lobbytime.qc -- a time set on a public lobby, kept on the player's own PC.
  Build 57, Stage T.

  A lobby used to save nothing at all.  The server switches the personal-best
  tables, the recorder and the stage writer off in a lobby (Lobby_NoPB /
  Lobby_NoRec, and the essays there are about data loss rather than policy: the
  tables have no player dimension and best.pb is rewritten whole, so one
  stranger's run would overwrite the host's entire history for the map).  An
  SSQC write would land on the Pi anyway, which is not the disk anybody's
  records are on.

  Meanwhile all three "leaderboards" in this game already read the CLIENT's
  disk: the +showscores board lists the .rec files under data/runs/<map>/<leg>
  by filename alone (a star and a dot-rec, which cannot be written inside a
  comment in this language -- fteqcc warns F325 on a nested opener), the
  results card's rank counts the same files, and the map picker's time column
  reads data/runs/<map>/best.pb.  So the gap was never "where would a lobby time
  live" -- it was that nobody wrote one.

  THE DESIGN: THE SERVER MEASURES, THIS FILE KEEPS.  Nothing is uploaded and no
  identity is involved, which is the decision this implements ("just me, on my
  PC").  The server publishes five stats (STAT_FS_LOBBY / FINREC / FINTICKS /
  FINLEG / FINFLAGS) and one new bit on the stage-close word (SF_QUALIFIES), and
  every rule about whether a time is legitimate stays on the server side of that
  line.  This file decides one thing only: is it better than what is on disk.

  WHY IT CANNOT JUST WATCH THE TIMER, which is the trap that shaped the whole
  file.  In a lobby:

    RUNTAG never leaves RT_NONE    SV_RecClose is the only writer of the
                                   RUNTAG/RUNTICKS/RUNLEG triple and a lobby
                                   never reaches it -- there is no buffer to
                                   close.  So the card's usual finish edge is
                                   permanently absent.
    TS_FINISHED can be skipped     run_t_pendarm re-arms a chained stage run in
                                   the SAME server frame it finished in, and the
                                   engine deltas each stat against the last
                                   value it SENT.  A state written and
                                   overwritten inside one PlayerPostThink was
                                   never on the wire at all.
    stage closes ARE reliable      STAT_FS_STAGEENDREC is monotonic and is
                                   published at the TOP of SV_StageClose, before
                                   every refusal.

  Hence two edges, both counters, each with its OWN latch in this file:
  STAGEENDREC for a stage beaten mid-run, FINREC for a leg finished.  Neither
  latch is shared with cl_results.qc or cl_timer.qc, which watch the same
  counters: a shared latch makes one panel consume the other's event, and these
  two have different lifetimes again.

  EVERY TRAP THIS FILE IS BUILT AROUND, in the order it meets them:

  1. INERT UNLESS STAT_FS_LOBBY.  Off a lobby the SERVER writes the files --
     best.pb, the .rec archive, the stage slices -- and a second writer would
     double-write every leg on a listen server.  The stat is the only gate that
     can tell the two cases apart, because it is a fact about the server rather
     than about the run.  rec_lobbytimes 0 switches this file off inside a lobby
     as well, for the player who wants a lobby to stay a scratch session.

  2. THE CVAR IS REGISTERED BESIDE THE READ.  cvar() on an unregistered name
     auto-creates it as the EMPTY STRING and registercvar then DECLINES, so a
     non-zero default registered anywhere later never lands -- this tree has lost
     three features to exactly that.  There is no LT_RegisterCvars: this file's
     whole contract with cl_main.qc is ONE call, so the registration lives at the
     read, behind a one-shot latch rather than running every frame.

  3. THE LATCHES ARE SEEDED ON FIRST SIGHT.  Joining a lobby mid-run, or
     reconnecting to one, hands the client whatever the counters already stand
     at; treating that as an edge would write a file for a stage somebody else
     finished before we arrived.  Seeding is also why the latches are NOT
     consumed off a lobby: a map that never was one leaves them at -1, and the
     first lobby frame seeds from the values standing then.

  4. THE LATCHES ARE CONSUMED ABOVE THE rec_lobbytimes RETURN.  A detector you
     can switch off comes back SEEDED from wherever it was switched on -- the
     same defect cl_results.qc fixed in this build, where a close arriving on a
     frame that returned early sat unread and popped a stale toast at the next
     run.  Consuming the counter is one question; deciding to write is another,
     and only the second may be skipped.

  5. LEG IS NOT SEGMENT.  STAT_FS_STAGEENDSEG is the 0-based SEGMENT that closed
     and the folder is keyed by LEG, so every stage write goes through
     FS_LegOf(seg, TRUE) -- seg + 1.  That is true of a full run's lifted stage
     AND of a deliberate `!s N` stage run, whose own stage closes through the
     same function on its finish frame.  The FINISH edge therefore handles
     leg 0 only: a stage run's time has already arrived on the stage edge, and
     taking it twice would write the same time into two folders.

  6. ONLY SF_QUALIFIES.  A refused close still bumps the counter -- it has to, or
     the class marks would miss the very stages they are about -- so the bit is
     what separates "a stage ended" from "a stage counted".  It is the server's
     own SV_StageQualifies, published so this file never re-implements a jump
     detector and a taint ladder it cannot observe.  It exists on the CLOSE word
     only; see SF_QUALIFIES in shared/sh_defs.qc.

  7. A GAP IS ANNOUNCED.  A stat carries only its current value, so two closes
     inside one dropped snapshot arrive as a counter two higher and the older
     one's time is simply gone.  That is rare and it is not recoverable, so it is
     SAID rather than hidden -- a missing stage time with no explanation is the
     shape of bug this project has paid for before.

  8. THE CARD READS THE OLD BEST BEFORE THIS FILE WRITES THE NEW ONE.  The
     server zeroes TIMERPBWAS in a lobby (SV_PBGet returns 0 there), so
     cl_results.qc asks LT_BestOnLeg what the run was measured against.  That
     only works in one order, and cl_main.qc has it: Results_Frame() then
     LT_Frame().  Moving the call above it would make every lobby card read
     "personal best by 0.000".

  9A. THE STATS ON THE WIRE MAY NOT BE MINE, which is the one trap that is about
     WHOSE run this is rather than about which run it is.  A spectator who tracks
     a player is sent THAT PLAYER'S stats: SV_CalcClientStats substitutes the
     tracked edict (engine/server/sv_send.c, `if (client->spectator &&
     client->spec_track > 0) ent = EDICT_NUM_UB(..., client->spec_track);`) and
     the SV_UpdateQCStats call at the END of that same function fills every
     QC-registered clientstat by reading fields off whatever edict it was handed.
     All nine stats this file reads are clientstat(..., EV_FLOAT, <field>) in
     SV_RegisterStats, so while tracking -- and in a demo, which needs no
     spectator slot at all -- every one of them describes the OTHER player's run.
     lobby_stat is a field too, so trap 1's gate reads 1, and every rule above
     this one passes: the SERVER really did decide SF_QUALIFIES and the clean
     flags, for a run that was not ours.  The single rule this file owns is about
     THIS disk, and the answer without a gate here is a stranger's time written
     into the player's own records under the player's own name (LT_Owner reads the
     local userinfo), having deleted the file it beat.  LT_StatsAreMine is the
     test; the refusal is on the WRITE and not on the latches, which is trap 4
     once more -- a spectator keeps up with the counters while watching and so
     re-seeds on joining the game instead of replaying a backlog of somebody
     else's stages.

  9. NO SPLITS AND NO LIVE DELTAS, and that is a documented limit rather than an
     omission.  The server zeroes the split and checkpoint deltas and the PB line
     in a lobby, because those read tables with no player dimension; restoring
     them needs per-player server state, which "just me on my PC" rules out.
     What is kept is what the server actually measured: the leg, its time, its
     flags, and which lobby it happened on.

  WHAT IT WRITES, and both files are the player's own:

    data/runs/<map>/<legdir>/<ticks7>_lobby.rec   a header, no samples.  The same
        v4 grammar in the same order SV_RecOpen writes, so the scoreboard reads
        the owner, the date and the class out of it with no special case, plus
        `lobby <hostname>` and `samples 0` -- which is this format's honest way
        of saying there is no replay behind the row.
    data/runs/<map>/lobby.pb                      FTESURF-PB 2, rewritten whole,
        carrying every other leg's line across.  It sits beside best.pb rather
        than inside it so that each file has exactly one writer; the map picker
        reads both and marks the row when the lobby time is the one it shows.

  NO CONSENT GATE OF ITS OWN, deliberately.  rec_terms is what cl_replay.qc's
  capture checks, because recording movement is collection; this writes a time
  the player set, on their own disk, having reached a lobby at all -- which
  requires FS_TERMS_ONLINE, the stricter of the two tiers.  Anybody who can see
  STAT_FS_LOBBY set has accepted both.
===========================================================================
*/

// Lines of an existing lobby.pb carried across a rewrite.  A bound of our own
// rather than a read-to-EOF, which is the rule every strbuf loop in this tree
// follows -- a file that never ends would otherwise hang the progs.
#define LT_PBMAX  256

float  lt_endrec;               // our own STAT_FS_STAGEENDREC latch; -1 = seeding
float  lt_finrec;               // our own STAT_FS_FINREC latch
string lt_map;                  // the map those two describe
float  lt_cvars;                // the cvar has been registered; see trap 2

/*
  Per map.  Both latches seed rather than zero, for the reason cl_timer.qc's and
  cl_results.qc's do: the counters legitimately READ zero on a fresh map, so
  seeding to 0 would make the first close of the map an event instead of a seed.
*/
void() LT_MapInit =
{
	lt_endrec = -1;
	lt_finrec = -1;
};

/*
  May this file write?  See trap 2 for why the registration is here.

  0 is "a lobby changes nothing on my disk", which is build 56 exactly.  It gates
  the WRITE and not the latch -- trap 4.
*/
float() LT_Enabled =
{
	if (!lt_cvars)
	{
		lt_cvars = TRUE;
		registercvar("rec_lobbytimes", "1", CVAR_ARCHIVE);
	}
	return cvar("rec_lobbytimes") != 0;
};

/*
  Are the stats on the wire the LOCAL player's own?  See trap 9A for why this is
  not implied by STAT_FS_LOBBY, and for the engine path that makes it necessary.

  player_localentnum is "the entity number the player is seeing from/spectating,
  or the player themself" and player_localnum is the 0-based local player slot
  (defs/cl_defs.qc).  On a QW server client N is edict N + 1, so the two agree
  exactly when nothing has been substituted for us -- and they disagree while
  tracking another player and while playing back a demo of one.

  IT FAILS CLOSED, deliberately and in both unknown directions: an unset
  player_localentnum, a slot of -1 before the server has assigned one, anything
  that is not positively "these are mine" refuses the write.  The cost of a
  wrong refusal is a lobby time that is not saved; the cost of a wrong
  acceptance is a stranger's time in the player's records with the file it
  replaced already deleted.  Those are not the same size of mistake.

  UNVERIFIED IN GAME AT THE TIME OF WRITING -- the identity is read off the
  engine source and the CSQC declarations, not off a running lobby.  Both
  numbers are printed by the `timer` command (cl_main.qc) next to this
  function's answer precisely so that one command falsifies it, on a listen
  server and on a lobby, without a build.
*/
float() LT_StatsAreMine =
{
	return player_localentnum == player_localnum + 1;
};

/*
  Whose time it is, for the `owner` header line.

  The player's own name from the userinfo, which is what the server would have
  written as e.netname.  A name with a space in it truncates to its first word
  when the scoreboard tokenizes the line -- that is true of every .rec this game
  has ever written and is a property of the grammar, not of this writer.
*/
string() LT_Owner =
{
	local string s;

	s = getplayerkeyvalue(player_localnum, "name");
	if (s == "")
		s = cvar_string("name");
	if (s == "")
		s = "unknown";
	return s;
};

/*
  Which lobby it happened on, for the `lobby` header line.

  hostname is CVAR_SERVERINFO in the engine (server/sv_main.c:213), so serverkey
  finds it in cl.serverinfo without any protocol of our own.  The address is the
  fallback because a server with no hostname set still has one of the two, and a
  row that cannot say where it was set is worth less than one that can.

  NOTHING IN QC READS THIS BACK.  It is for the person opening the file, and for
  whatever one day imports it; the tag in the filename is what code tests.
*/
string() LT_Host =
{
	local string s;

	s = serverkey("hostname");
	if (s == "")
		s = serverkey("ip");
	if (s == "")
		s = "unknown";
	return s;
};

/*
  The stage's own flags, for the header -- the same four lines SV_StageWrite
  derives ITS header from, read off the published word instead of the taint
  fields, which the client cannot see.

  A second spelling of four lines, and it is the cheapest of the three options.
  A sixth stat would carry a value that is 0 on every file this writer actually
  produces (SF_QUALIFIES refuses a dirty stage under the default ruleset), and a
  literal `flags 0` would LIE under run_stageclean 0, where the taint rules are
  the run's rather than the stage's and a dirty stage can still qualify.  The
  mapping is an implication in one direction only, exactly as it is there: the
  two class bits imply the umbrella, and the umbrella is what every filter reads.
*/
float(float word) LT_StageFlags =
{
	local float f;

	f = 0;
	if (word & SF_DIRTY)  f = f | TF_PRACTICE;
	if (word & SF_GHOST)  f = f | TF_GHOST;
	if (word & SF_STITCH) f = f | TF_PRACTICE | TF_SEGMENT;
	if (word & SF_CHEAT)  f = f | TF_PRACTICE | TF_CHEAT;
	return f;
};

/*
  The fastest lobby time already on a leg, in ticks, or 0 for none.

  FILENAMES ONLY, which is the same reading cl_results.qc's rank does and for the
  same reason: the tick count is zero-padded into the name precisely so that no
  file has to be opened to be compared.  One search_begin with ONE wildcard, in
  the last component, which is the pattern this disk has proven.

  `mine` is "ignore a file whose stamp is this number" -- pass 0 to count them
  all.  The improvement test passes 0, because at that moment nothing of this
  run's is on disk yet.  The results card passes the time it is drawing, so that
  `results` REOPENED after the write still reports the best the run was measured
  against rather than the run's own file.  A previous attempt with the identical
  tick count is the one case that confuses it, and that is the case the
  improvement test below refuses anyway.
*/
float(string map, float track, float leg, float mine) LT_BestOnLeg =
{
	local float h, n, i, best, t, cut, dot;
	local string fn, base, tagw;

	if (map == "" || track < 0 || leg < 0)
		return 0;

	h = search_begin(sprintf("%s*_%s.rec", FS_RunDir(map, track, leg),
	                         FS_TagName(RT_LOBBY)), FS_NAMESORT, TRUE);
	if (h < 0)
		return 0;               // no such directory: nothing on this leg yet

	best = 0;
	n    = search_getsize(h);
	for (i = 0; i < n; i = i + 1)
	{
		fn   = search_getfilename(h, i);

		cut  = Scores_LastOf(fn, 47);           // '/'
		base = (cut >= 0) ? substring(fn, cut + 1, strlen(fn) - cut - 1) : fn;

		dot  = strlen(base) - 4;                // ".rec"
		if (dot < 1)
			continue;
		base = substring(base, 0, dot);

		// <ticks>[_<who>]_<tag>.  The tag word is checked rather than assumed
		// from the search pattern, so a file somebody dropped in the folder is
		// skipped instead of being read as a time.  BUILD 66: through the shared
		// parse -- this was the third copy of the split, and these files are
		// written by THIS client on THIS disk so they never carry a `who`; the
		// point of routing it through anyway is that there is now one answer to
		// what a run filename means rather than three that happen to agree.
		tagw = FS_NameTag(base);
		if (FS_TagFromName(tagw) != RT_LOBBY)
			continue;

		t = FS_NameTicks(base);
		if (t <= 0)
			continue;
		if (mine > 0 && t == mine)
			continue;
		if (best == 0 || t < best)
			best = t;
	}
	search_end(h);
	return best;
};

/*
  One lobby time per leg: remove every _lobby.rec on it except the one just
  written.

  SV_RecPrune's shape, minus the quota and minus the sidecars.  There is no
  rec_runs_keep here because accumulating is not the feature: a lobby time has no
  .view and no .hid behind it -- there is nothing to watch -- so twenty of them
  on one leg would be twenty empty files and nineteen wrong answers to "what is
  my best on this lobby".  `keep` is matched as a SUFFIX of the path, exactly as
  the pruner matches its own, rather than by rebuilding the full path a second
  way.
*/
void(string map, float track, float leg, string keep) LT_Prune =
{
	local float h, n, i, kl;
	local string fn;

	h = search_begin(sprintf("%s*_%s.rec", FS_RunDir(map, track, leg),
	                         FS_TagName(RT_LOBBY)), FS_NAMESORT, TRUE);
	if (h < 0)
		return;

	kl = strlen(keep);
	n  = search_getsize(h);
	for (i = 0; i < n; i = i + 1)
	{
		fn = search_getfilename(h, i);

		if (strlen(fn) >= kl)
		if (substring(fn, strlen(fn) - kl, kl) == keep)
			continue;               // the file just written

		fremove(fn);
		dprint(sprintf("lobbytime: removed %s\n", fn));
	}
	search_end(h);
};

/*
  Rewrite data/runs/<map>/lobby.pb whole, with this leg's new time in it.

  WHOLE, AND THAT IS SAFE HERE IN A WAY IT IS NOT FOR best.pb.  SV_PBSave's own
  essay refuses to rewrite best.pb in a lobby because it would be writing a table
  that holds whoever finished last; this file is writing ONE leg's line, read
  back from the one player's own disk, and carries every other line across
  verbatim.  Nothing here has a player dimension to lose.

  EVERY LINE THAT IS NOT OURS IS KEPT, not just the `best` ones.  The .pb grammar
  is additive -- unknown keywords fall through to nothing, which is what lets an
  older build read a newer file -- so dropping a key this build has not heard of
  would quietly make that promise false.  The header and the `#` comment are
  rewritten rather than carried, because they are this writer's own statement
  about the file it has just produced.

  THE KEY IS MATCHED WITH ITS TRAILING SPACE.  "best 0 1 " cannot prefix-match
  "best 0 10 ...", which is leg 10 of the same track and a different row.
*/
void(string map, float track, float leg, float ticks) LT_PBWrite =
{
	local float fh, buf, i, n, seen;
	local string path, ln, mine;

	path = sprintf("%s%s%s", FS_RUNS_ROOT, map, FS_LOBBYPB_LEAF);
	mine = sprintf("best %g %g ", track, leg);

	buf = buf_create_ex("string", 0);
	if (buf < 1)
	{
		print("^3lobbytime:^7 buf_create failed; lobby.pb is unchanged\n");
		return;
	}

	// Read first, write second, and the read is CLOSED before the write opens:
	// this is the same path on both sides.
	fh = fopen(path, FILE_READ);
	if (fh >= 0)
	{
		for (seen = 0; seen < LT_PBMAX; seen = seen + 1)
		{
			ln = fgets(fh);
			if (!ln)
				break;
			if (substring(ln, 0, 11) == "FTESURF-PB ")
				continue;
			if (substring(ln, 0, 1) == "#")
				continue;
			if (substring(ln, 0, strlen(mine)) == mine)
				continue;               // the leg being replaced
			bufstr_set(buf, buf_getsize(buf), ln);
		}
		fclose(fh);
	}

	fh = fopen(path, FILE_WRITE);
	if (fh < 0)
	{
		print(sprintf("^3lobbytime:^7 cannot write %s\n", path));
		buf_del(buf);
		return;
	}

	// Always version 2: there was never a version-1 lobby.pb, so nothing here
	// needs the segment-to-leg shift SV_PBLoad does for an old best.pb.
	fputs(fh, "FTESURF-PB 2\n");
	fputs(fh, sprintf("# %s  lobby times  %s\n", map,
	                  strftime(TRUE, "%Y-%m-%d %H:%M")));
	fputs(fh, sprintf("best %g %g %g\n", track, leg, ticks));

	// fgets returns the line without its newline, so each one is put back.
	n = buf_getsize(buf);
	for (i = 0; i < n; i = i + 1)
		fputs(fh, strcat(bufstr_get(buf, i), "\n"));

	fclose(fh);
	buf_del(buf);
	dprint(sprintf("lobbytime: wrote %s (%g other line(s) kept)\n", path, n));
};

/*
  A leg was finished on a lobby.  Keep it if it beats what is on disk.

  THE ONLY RULE THIS FILE OWNS, and it is deliberately the only one: everything
  about whether the time is LEGITIMATE was decided by the server and arrived as
  SF_QUALIFIES or as FINFLAGS.  What is left is the player's own records, which
  is the one question the server cannot answer -- it cannot see this disk.

  STRICTLY FASTER, so a repeat of your own best does not rewrite the file and
  does not re-print "saved".  The refusal is printed too: a run that was not kept
  and said nothing would read as a run the game failed to notice.
*/
void(float track, float leg, float ticks, float flags) LT_Keep =
{
	local float prev, fh, tick;
	local string map, dst, nm;

	if (track < 0 || leg < 0 || ticks <= 0)
		return;

	map = serverkey("map");
	if (map == "")
		return;                 // no server: there is no leg to file this under

	tick = Timer_Tick();
	prev = LT_BestOnLeg(map, track, leg, 0);

	if (prev > 0)
	if (ticks >= prev)
	{
		print(sprintf("^7%s  %s  ^3not a lobby best^7 (%s)\n",
		              Results_LegName(track, leg),
		              Time_TickString(ticks, tick),
		              Time_TickString(prev, tick)));
		return;
	}

	nm  = sprintf("%s_%s.rec", FS_RunStamp(ticks), FS_TagName(RT_LOBBY));
	dst = FS_RunPath(map, track, leg, ticks, FS_TagName(RT_LOBBY), "rec");

	fh = fopen(dst, FILE_WRITE);
	if (fh < 0)
	{
		print(sprintf("^3lobbytime:^7 cannot write %s\n", dst));
		return;
	}

	/*
	  THE HEADER, IN SV_RecOpen'S OWN ORDER AND GRAMMAR, because the readers of a
	  .rec are shared: cl_scores.qc takes the owner, the date and the `flags`
	  class out of exactly these keys, and a file that answered them in a
	  different shape would need a special case in a reader this build does not
	  own.

	  `startseg` is the SEGMENT the leg began at and `leg` is the leg -- the pair
	  build 57 separated -- so a reader with no `leg` key derives the same answer
	  FS_LegOf would give it.  `runid` carries the date the board shows, which is
	  why it is a stamp rather than a serial.  The two new keys are additive by
	  the header's own rule: `lobby` says where it happened, and `samples 0` says
	  out loud that there is no movement in here.  There is no `begin` and no
	  `end`, because both of those introduce a body this file does not have.
	*/
	fputs(fh, "FTESURF-REC 4\n");
	fputs(fh, sprintf("map %s\n", map));
	fputs(fh, sprintf("track %g\n", track));
	fputs(fh, sprintf("startseg %g\n", (leg > 0) ? leg - 1 : 0));
	fputs(fh, sprintf("leg %g\n", leg));
	fputs(fh, sprintf("tickrate %g\n", tick));
	fputs(fh, sprintf("owner %s\n", LT_Owner()));
	fputs(fh, sprintf("runid %s-l%g\n", strftime(TRUE, "%Y%m%d-%H%M%S"), leg));
	fputs(fh, sprintf("flags %g\n", flags));
	fputs(fh, sprintf("lobby %s\n", LT_Host()));
	fputs(fh, "samples 0\n");
	fclose(fh);

	// The .rec is the archive and lobby.pb is the summary the map picker reads,
	// in that order: a summary written first would name a file that did not exist
	// if the write below failed.
	LT_Prune(map, track, leg, nm);
	LT_PBWrite(map, track, leg, ticks);

	if (prev > 0)
		print(sprintf("^2%s saved^7 -- %s, lobby best by ^2%s^7\n",
		              Results_LegName(track, leg),
		              Time_TickString(ticks, tick),
		              Time_TickString(prev - ticks, tick)));
	else
		print(sprintf("^2%s saved^7 -- %s, first one on a lobby\n",
		              Results_LegName(track, leg),
		              Time_TickString(ticks, tick)));
};

/*
  Per frame, from CSQC_UpdateView, immediately AFTER Results_Frame -- see trap 8
  for why that order is load-bearing.  Draws nothing and owns two latches.
*/
void() LT_Frame =
{
	local float endrec, finrec, gap, stagefresh, finfresh;
	local float word, seg, ticks, leg, track, flags;

	/*
	  A map change retires both latches.  Watched from here rather than hooked out
	  of cl_main.qc for the reason cl_results.qc and cl_timer.qc give for doing the
	  same: one string compare a frame is cheaper than the coupling, and it keeps
	  this file's whole contract with cl_main.qc down to one call.
	*/
	if (zone_mapname != lt_map)
	{
		lt_map = zone_mapname;
		LT_MapInit();
	}

	/*
	  Trap 1.  Off a lobby the server owns the files, and the latches stay
	  unseeded so that joining one later starts from the values standing then.

	  BOTH "KEEPS NOTHING" BITS, not merely LS_LOBBY.  lobby_enable 1 with
	  lobby_nopb 0 is a listen server writing best.pb and the .rec archive to THIS
	  disk; keeping a second copy beside them would put one run on the leg twice
	  and inflate the card's rank total with its own duplicate.  The condition this
	  writer exists for is "the server kept nothing", and that is what it tests.
	*/
	if (!(getstatf(STAT_FS_LOBBY) & LS_LOBBY))
		return;
	if ((getstatf(STAT_FS_LOBBY) & (LS_NOPB | LS_NOREC)) != (LS_NOPB | LS_NOREC))
		return;

	endrec = getstatf(STAT_FS_STAGEENDREC);
	finrec = getstatf(STAT_FS_FINREC);

	// Trap 3.  One seed for both counters: the first frame on a lobby is never an
	// event, whichever of the two it arrives with.
	if (lt_endrec < 0)
	{
		lt_endrec = endrec;
		lt_finrec = finrec;
		return;
	}

	// Trap 4: both counters are consumed BEFORE anything below can return.
	gap        = endrec - lt_endrec;
	stagefresh = (gap > 0);
	lt_endrec  = endrec;

	finfresh  = (finrec > lt_finrec);
	lt_finrec = finrec;

	/*
	  Trap 9A.  These stats may be somebody else's: a spectator who tracks a
	  player, and a demo of one, are both SENT the run they are watching, lobby
	  stat and qualify bit and all.  Everything below this line writes to the
	  player's own records, so this is the last point at which "whose run is
	  this" can still be asked.

	  ABOVE IT ON PURPOSE, exactly as trap 4 puts the rec_lobbytimes return
	  above it: the two counters have already been taken, so a spectator keeps
	  up with them while watching and joining the game re-seeds from where they
	  stand rather than replaying every stage beaten while we were a camera.
	*/
	if (!LT_StatsAreMine())
		return;

	if (!LT_Enabled())
		return;

	if (stagefresh)
	{
		// Trap 7.  The newest close is still readable; the ones behind it are not.
		if (gap >= 2)
			print(sprintf("^3lobbytime:^7 %g stage close(es) did not arrive -- "
			              "a stage time was missed\n", gap - 1));

		word  = getstatf(STAT_FS_STAGEENDST);
		ticks = getstatf(STAT_FS_STAGEENDTICKS);
		seg   = getstatf(STAT_FS_STAGEENDSEG);

		/*
		  All four read in the SAME frame, which is the property the server built
		  them with: they are written in one breath and the counter is bumped last,
		  so a counter that moved is a counter whose answers are already here.

		  SF_KNOWN first and SF_QUALIFIES second -- trap 6.  A duration of 0 is a
		  close with nothing in it, and -1 is "no stage was open", which has no leg.

		  The TRACK comes from STAT_FS_TIMERTRACK, which is the one thing the close
		  report does not carry; cl_results.qc's toast ranks the same close off the
		  same stat.  It is the run's own track for every close inside a run, and
		  the shared risk is an arm onto a different track landing in the same
		  snapshot as a bonus track's close.
		*/
		if (word & SF_KNOWN)
		if (word & SF_QUALIFIES)
		if (ticks > 0)
		if (seg >= 0)
			LT_Keep(getstatf(STAT_FS_TIMERTRACK), FS_LegOf(seg, TRUE), ticks,
			        LT_StageFlags(word));
	}

	if (finfresh)
	{
		ticks = getstatf(STAT_FS_FINTICKS);
		flags = getstatf(STAT_FS_FINFLAGS);

		// FINLEG is RUNLEG's encoding, track * 100 + leg + 1, so that 0 can mean
		// "no run at all" -- decoded here exactly as cl_results.qc and
		// Rec_ViewPath decode the live one.
		leg = getstatf(STAT_FS_FINLEG);
		if (leg >= 1)
		{
			leg   = leg - 1;
			track = floor(leg / 100);
			leg   = leg - track * 100;
		}
		else
		{
			track = 0;
			leg   = -1;             // nothing to file
		}

		/*
		  LEG 0 ONLY -- trap 5.  A full run of the main track or of a bonus.  A
		  stage run's finish closes its own stage through SV_StageClose on this same
		  frame, so it has already been written above; filing it again here would
		  put one time in two folders, one of them the wrong one.

		  THE CLEAN TEST IS THE LOCAL FINISH PATH'S, read off the flags the server
		  decided: SV_TimerFinish prints a shadow run and a practice run in their
		  own branches and reaches its personal-best arm only when neither bit is
		  set.  TF_CHEAT and TF_SEGMENT both imply TF_PRACTICE (FS_RunClass's
		  precedence), so those two tests are the whole ladder rather than a
		  sample of it.
		*/
		if (leg == 0)
		if (ticks > 0)
		if (!(flags & TF_PRACTICE))
		if (!(flags & TF_SHADOW))
			LT_Keep(track, 0, ticks, flags);
	}
};
