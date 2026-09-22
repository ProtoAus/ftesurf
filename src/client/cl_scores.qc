/*
===========================================================================
  cl_scores.qc -- the +showscores leaderboard.  Build 24, stage 2.

  Stage 1 built the reader and gave it a console command.  This is the thing
  that makes the archive worth having: a list of every run on a leg, in order,
  that you can click a row of and watch.

  THREE FACTS DECIDED THE WHOLE SHAPE, and all three are about not inventing an
  index for something the filesystem already sorts.

  1. THE NAME SORT IS THE LEADERBOARD.  Build 23 zero-padded the tick count into
     the filename precisely so that an ascending filename sort is an ascending
     TIME sort -- 0004108_pb.rec before 0005471_pb.rec, always, for any two runs
     on any leg.  So the rows come straight out of search_begin with FS_NAMESORT
     and there is no index file, no serial, and nothing to keep in step.

     `last.rec` has no stamp, deliberately (see FS_RunPath), and therefore sorts
     after every stamped name because 'l' is above '9'.  That is the right place
     for it: it is the attempt you just did, not a ranked one.  Build 45's
     `cheat.rec` is unstamped for the same reason and lands in the same place,
     just above it -- so the two scratch slots sit together at the bottom and
     the sort needed no change to put them there.

  2. THE LEGS COME FROM THE ZONES, NOT FROM THE DIRECTORY.  zone_track[] and
     zone_seg[] are parsed client-side by shared/sh_zones.qc, so this VM already
     knows the map has a main track, six stages and six bonuses -- INCLUDING the
     ones you have never run, which a directory scan cannot show at all.  It also
     avoids a two-wildcard search_begin pattern, which is a guess about
     Sys_EnumerateFiles2's recursion that nothing on this disk proves; build 23
     refused that guess and named best.pb the way it did to avoid it.

  3. OWNER, DATE AND CLEAN-VS-STITCHED ARE IN THE FILE, NOT THE NAME.  So each
     row costs one fopen and about nine fgets -- the header ends at `begin` and
     nothing past it is read.  Done ONCE when a leg's list is built and cached in
     three strbufs, never per frame.  A few dozen small reads on a click.

  WHY THE ROWS ARE NOT DRAWN FROM A SECOND COPY OF THE HUD's LIST CODE.  They are
  drawn with sui, the same widget library the map browser runs on, compiled into
  csprogs since stage 1.  sui_list_view_begin only emits the rows actually on
  screen -- about a dozen -- which is what lets the browser tokenize per row
  across 1,400 maps and does the same here across however many runs a leg has.
===========================================================================
*/

#define SB_MAXLEG   64
#define SB_MAXROW   256

// The leg table, built from the zone tables on the first open per map.
//
// BUILD 57: rec_sb_legnum was rec_sb_legseg, and the rename is the fix rather
// than tidiness.  It holds the LEG -- 0 the full run, k stage k -- which is what
// FS_RunDir takes now.  It used to hold the 0-based SEGMENT a stage began at, so
// "stage 1" on this board was really stage 2 and stage 1 had no row at all.  A
// name that said `seg` over a value that is not one is how that would come back.
float  rec_sb_legtrack[SB_MAXLEG];
float  rec_sb_legnum[SB_MAXLEG];
float  rec_sb_legn;
float  sc_held;                  // PATCH 341: +showscores is down right now
string rec_sb_legmap;            // the map rec_sb_leg* describes; "" = none
float  rec_sb_legzoned;          // it holds a strzone that has to be given back

// The rows for the selected leg.
float  rec_sb_rowticks[SB_MAXROW];
float  rec_sb_rowtag[SB_MAXROW];         // RT_*
float  rec_sb_rowflags[SB_MAXROW];       // header `flags`, or -1 when absent
float  rec_sb_rowver[SB_MAXROW];         // FTESURF-REC version
float  rec_sb_rown;
float  rec_sb_rowover;                   // files the leg had that would not fit

/*
  Three strbufs and not three string arrays.

  A QC `string x[256]` needs a strzone per entry and a strunzone on every rebuild,
  and a missed unzone is a leak nothing reports.  A strbuf is one handle, one
  buf_del, and bufstr_set overwrites without either -- which is the same reason
  the map browser holds its names this way.
*/
float  rec_sb_bpath;
float  rec_sb_bowner;
float  rec_sb_bdate;

// rec_sb_open IS DECLARED IN cl_hud.qc, not here.  Build 47 moved it, for the
// reason the block beside ui_he_open there gives: cl_watch.qc compiles before
// this file and has to test it to know whether it may let the cursor go.
float  rec_sb_leg;               // index into the leg table
float  rec_sb_legbuilt;          // the leg the rows belong to; -1 = none
float  rec_sb_filter;            // SB_F_*
vector rec_sb_scroll;
vector rec_sb_legscroll;
float  rec_sb_best;              // the fastest CLEAN time on this leg, or 0

/*
  BUILD 44: FOUR CHIPS, AND THE INVARIANT IS THAT NO ROW HIDES UNDER ALL OF THEM.

  The row word now has four states (FS_RunClass) and the filter has three plus
  `all`, so one chip has to cover two classes.  `stitched` takes RC_PRACTICE
  along with RC_SEGMENT -- it is the "not clean, not cheated" bucket -- because
  the alternative is a bare-practice row (a hopped start, or any file written
  before build 44) that appears under `all` and nowhere else.  This file already
  states that rule for the unknowns: a filter that quietly drops the runs it
  cannot classify is one that lies about how many there are, and the same is true
  of the ones it can.

  Every row therefore shows under exactly one of the three, and unknowns show
  under all of them.
*/
#define SB_F_ALL       0
#define SB_F_CLEAN     1
#define SB_F_STITCHED  2
#define SB_F_CHEATED   3

/*
===========================================================================
  BUILD 64, STAGE 2: THREE TABS, AND THE DEFAULT IS THE ONLINE ONE.

  Stage 1 built cl_online.qc -- one GET against surfd, parsed and kept, drawing
  nothing.  This is where that data becomes a board, and the tabs are the axis
  the request asked for in as many words: "the default online leaderboard to
  show, and for there to be a segmented tab, and both of these show players
  best times ranked. with a local times that shows you every recording you
  have."

  SO THE TABS ARE ONLINE / SEGMENTED / LOCAL: which BOARD you are looking at --
  surfd keys `style` into the primary key, so clean and segmented are PEER
  boards, plus this disk's own archive.

  PATCH 355: NO TIER CHIP.  surfd's community tier only ever held runs from our
  own lobbies that certifiable() demoted; the online tabs show OB_TIER (ranked)
  and a demoted run is told to its player and kept in Local instead.

  THE TWO ONLINE TABS ARE ONE REQUEST WITH ONE FIELD CHANGED, which is exactly
  what cl_online.qc's Online_Fetch takes `style` as a parameter for.  Nothing
  about the fetch, the parse or the storage knows a tab exists.

  WHY ONLINE IS THE DEFAULT even though local is the one that always works: a
  board that opens on your own times is a personal-best list, and the request
  was for a leaderboard.  The cost is that opening it on an offline install
  shows an empty panel -- so the empty states below are written to say WHICH
  kind of nothing this is (not configured / still asking / it did not answer /
  genuinely no times yet), because "no times" covering all four would make an
  unplugged install look like an unplayed map.
===========================================================================
*/
#define SB_T_ONLINE    0
#define SB_T_SEGMENT   1
#define SB_T_LOCAL     2

float rec_sb_tab;                // SB_T_*

/*
  The ledger id this board is waiting on, or 0.  Build 66, step R5.

  It exists because the download outlives the board: the transfer completes in
  the engine whether this is open or not, so "a replay is ready" and "this
  player still wants it" are two different facts and only one of them is in
  cl_online.qc.  Cleared by Scores_Close, which is what makes closing the board
  a cancel.
*/
float rec_sb_wantrep;
float rec_sb_wantleg;            // Patch 395: open it at this board leg (its run's file)
float rec_sb_olpick;             // `scores olpick <row>` + 1: the next draw's click
vector rec_sb_oscroll;           // the online list's own scroll position

#define SB_ROW_H   22
#define SB_LEG_H   20

// Promised here, defined below: the draw path closes the board when a row is
// clicked and the console handler prints the status, and both sit above their
// definitions for readability rather than for any structural reason.
void() Scores_Close;
void() Scores_Status;

/*
  The three questions the rest of this file asks about the tab, in one place.

  Written as functions rather than read as `rec_sb_tab == SB_T_SEGMENT` at each
  site because the two online tabs differ in EXACTLY ONE STRING and that string
  goes to surfd -- so the mapping from tab to wire value is a fact with one
  home.  A second copy of `"segmented"` spelled `"segment"` would fetch an
  always-empty board and look like a server with no times on it.
*/
float() Scores_IsOnline = { return (rec_sb_tab != SB_T_LOCAL); };
string() Scores_StyleOf = { return (rec_sb_tab == SB_T_SEGMENT) ? "segmented" : "clean"; };

/*
  PATCH 357: THE BOARD FOLLOWS A FINISH.  Results_BoardWatch (cl_results.qc)
  calls these.  A finish marks Local stale (legbuilt -2 = rescan, keep the
  scroll) and, if the board is shut, makes its next open jump to the finished
  leg; the tab moves only when the current one cannot hold the run.  When
  `*wrank` says the row moved, the online store is marked stale.  seek scrolls
  to the player's row once the answer is in; it survives a -showscores.
*/
float  rec_sb_finpend;           // follow on the next open
float  rec_sb_fintrack, rec_sb_finleg, rec_sb_finticks, rec_sb_finflags;
float  rec_sb_finwait;           // a board answer is still owed
float  rec_sb_finrank;           // *wrank's rank once answered, 0 = none
float  rec_sb_finbest;           // the standing online best (ms) after it
float  rec_sb_seek;
float  rec_sb_tabauto;           // the follow moved the tab to Local; the next can undo it

void() Scores_NoteLocal =
{
	if (rec_sb_legbuilt == rec_sb_leg)
		rec_sb_legbuilt = -2;
};

void(float track, float leg, float ticks, float flags, float owed) Scores_NoteFinish =
{
	Scores_NoteLocal();
	rec_sb_fintrack = track;
	rec_sb_finleg   = leg;
	rec_sb_finticks = ticks;
	rec_sb_finflags = flags;
	rec_sb_finrank  = 0;
	rec_sb_finbest  = 0;
	rec_sb_finwait  = owed;
	rec_sb_finpend  = !(rec_sb_open || sc_held);   // up already: refresh in place
	rec_sb_seek     = TRUE;
};

void(float landed, float rank, float bestms) Scores_NoteAnswer =
{
	rec_sb_finwait = FALSE;
	if (rank > 0)
	{
		rec_sb_finrank = rank;      // the standing, even when this run did not move it
		rec_sb_finbest = bestms;
	}
	if (landed)
		Online_MarkStale();
};

void() Scores_ForgetFinish =
{
	rec_sb_finpend = rec_sb_finwait = rec_sb_seek = FALSE;
	rec_sb_finticks = rec_sb_finrank = 0;
};

string() Scores_FinStyle =
{
	return (FS_RunClass(rec_sb_finflags) == RC_SEGMENT) ? "segmented" : "clean";
};

void() Scores_ApplyFollow =
{
	local float i, c;

	rec_sb_finpend = FALSE;
	for (i = 0; i < rec_sb_legn; i = i + 1)
		if (rec_sb_legtrack[i] == rec_sb_fintrack)
		if (rec_sb_legnum[i] == rec_sb_finleg)
			break;
	if (i >= rec_sb_legn)
		return;
	if (rec_sb_leg != i)
	{
		rec_sb_leg = i;
		rec_sb_legbuilt = -1;
		rec_sb_oscroll = '0 0 0';
	}
	if (!Scores_IsOnline())
	if (!rec_sb_tabauto)
		return;                     // the player chose Local: it holds every finish
	c = FS_RunClass(rec_sb_finflags);
	if (serverkey("board") != "ranked" || (rec_sb_finflags & TF_UNCERT))
	{
		if (rec_sb_tab != SB_T_LOCAL)
			rec_sb_tabauto = TRUE;
		rec_sb_tab = SB_T_LOCAL;    // on no online board this player can see
	}
	else if (c == RC_SEGMENT)
	{
		rec_sb_tab = SB_T_SEGMENT;
		rec_sb_tabauto = FALSE;
	}
	else if (c == RC_CLEAN)
	{
		rec_sb_tab = SB_T_ONLINE;
		rec_sb_tabauto = FALSE;
	}                               // practice/cheated: no board; leave the tab
};

/*
  ---- WHERE A RUN SET HERE ACTUALLY GOES.  Build 64. -----------------------

  THE REPORT: "I set a time on bhop_eazy and it didn't write my time to the
  public leaderboard.  I see the fake times you put there, but not my time?"

  Both halves of that were working as designed and the combination was still a
  defect.  The run was set on a LISTEN SERVER, where Lobby_SubmitRun returns at
  its first gate because there is no lobby_master -- the "Ranked = official
  servers only" line, which exists because a self-hosted server owns its own
  clock and could otherwise post any time it liked.  Meanwhile the Online tab
  is the DEFAULT tab and shows the global board for the current map, which is
  correct and useful and looks exactly like a board your time should be on.

  So the player is shown somebody else's times on their own map, told nothing,
  and left to conclude the submission is broken.  It is not; it never ran.  The
  server knows which of those it is, and now says so.

  READ, NOT DERIVED.  The client cannot work this out for itself: lobby_master
  and lobby_master_key are SERVER cvars and sv_guidkey is an engine cvar on the
  server, none of which a connected client can see.  Lobby_BoardState publishes
  one word into serverinfo (sv_lobby.qc) and this reads it back.

  EMPTY MEANS AN OLDER SERVER AND IS NOT AN ERROR.  Anything running a progs
  from before this key existed publishes nothing, and inventing a confident
  sentence from a missing key would be a statement about a server we have not
  heard from.  Silence there, exactly as the local board says nothing about
  runs it has not scanned.
*/
string() Scores_BoardNote =
{
	local string b;

	b = serverkey("board");

	if (b == "ranked")
		return "this server posts times to the online board";
	if (b == "local")
		return "times set here stay on this machine -- the online board only "
		       "takes runs from official servers";
	if (b == "noid")
		return "this server is set up to post times but cannot identify "
		       "players (sv_guidkey) -- nothing is being submitted";
	return "";
};

/*
  The index of the last `c` in `s`, or -1.

  There is no strrchr in this VM -- strstrofs searches forward and takes a start
  offset -- so this walks it.  Both callers work on a filename, which is tens of
  characters, and both want the LAST occurrence: the final '/' separates the leg
  directory from the basename, and the final '_' separates the tick stamp from
  the tag.
*/
// BUILD 66: the body moved to FS_LastOf in shared/sh_defs.qc, where the rest of
// the filename grammar now lives -- the stamp/who/tag split needs a FIRST-of as
// well and having half the scan here and half there is how the two get to
// disagree about what a separator is.  The name stays because three files call
// it for the '/' and renaming them would be churn in somebody else's diff.
float(string s, float c) Scores_LastOf = { return FS_LastOf(s, c); };

/*
===========================================================================
  Reading one row's header
===========================================================================
*/

/*
  Everything the list shows that is not in the filename, in nine fgets.

  Stops at `begin`, which is the header's own terminator, and bounds itself at 24
  lines as well -- a file whose header never ends is a truncated or corrupt one,
  and reading it to EOF would stall the list on exactly the file least worth
  showing.  Writes straight into the row arrays and the three buffers.
*/
void(float r, string path) Scores_ReadHeader =
{
	local float fh, i, n;
	local string l, owner, date;

	bufstr_set(rec_sb_bowner, r, "");
	bufstr_set(rec_sb_bdate,  r, "");
	rec_sb_rowflags[r] = -1;
	rec_sb_rowver[r]   = 0;

	fh = fopen(path, FILE_READ);
	if (fh < 0)
		return;

	owner = date = "";
	for (i = 0; i < 24; i = i + 1)
	{
		l = fgets(fh);
		if (!l)
			break;

		n = tokenize(l);
		if (n < 1)
			continue;
		if (argv(0) == "begin")
			break;
		if (n < 2)
			continue;

		if (argv(0) == "FTESURF-REC") rec_sb_rowver[r]   = stof(argv(1));
		if (argv(0) == "flags")       rec_sb_rowflags[r] = stof(argv(1));
		if (argv(0) == "owner")       owner = argv(1);

		/*
		  runid is "<yyyymmdd>-<hhmmss>-<slot>" and the list wants the date.
		  Sliced rather than parsed: it is a fixed-width stamp written by one
		  strftime call in SV_RecOpen, and a tokenizer would have to know the
		  slot is not part of the time.
		*/
		if (argv(0) == "runid")
		{
			l = argv(1);
			if (strlen(l) >= 8)
				date = sprintf("%s-%s-%s", substring(l, 0, 4),
				               substring(l, 4, 2), substring(l, 6, 2));
		}
	}
	fclose(fh);

	bufstr_set(rec_sb_bowner, r, owner);
	bufstr_set(rec_sb_bdate,  r, date);
};

/*
  The time of an UNSTAMPED recording -- the tags FS_TagArchived answers FALSE
  for, which since build 45 is `last.rec` AND `cheat.rec` rather than the one
  file this comment used to name.

  Every other name carries its tick count, so this runs at most twice per leg.

  The trailer is `end` followed by one `split` per completed segment, so `end` is
  near the bottom but is not the last line.  Patch 431: only the last 16 KB is
  read (the last `end` in it wins); buf_loadfile of a recording over 5 MB took
  12.9 s (see Watch_BufLoad).
*/
float(string path) Scores_TrailerTicks =
{
	local float fh, n, t;
	local string s;

	fh = fopen(path, FILE_READ);
	if (fh < 0)
		return 0;
	n = fsize(fh);
	t = 0;
	if (n > 16384)
	{
		fseek(fh, n - 16384);
		fgets(fh);                  // the partial line the seek landed in
	}
	while (1)
	{
		s = fgets(fh);
		if (s == "")
		if (fseek(fh) >= n)
			break;
		if (substring(s, 0, 4) == "end ")
		{
			tokenize(s);
			t = stof(argv(1));
		}
	}
	fclose(fh);
	return t;
};

/*
  What kind of run this row is -- RC_*, or RC_UNKNOWN when the file cannot say.

  The `flags` header key is v4 and is the real answer, and BUILD 44 STOPPED
  READING IT HERE.  It used to test TF_PRACTICE directly and return one of two
  states, which is what put the word `stitched` on a noclipped run and is the
  report this build answers.  The precedence -- cheat outranks segment outranks
  practice -- now lives in FS_RunClass in shared/sh_defs.qc, because this is one
  of THREE readers that have to agree about a run carrying both bits, and the
  other two are in cl_watch.qc and cl_timer.qc.  One fact, one definition; the
  same argument FS_TagName's own move makes.

  A v3 file has no such key, and rather than invent one the TAG is used, which is
  a partial answer and is honest about being one:

    pb      a personal best, and a practice run cannot set one -> CLEAN
    shadow  written only by a save-state resume, by definition  -> SEGMENT
    last    every other attempt, which says nothing at all      -> UNKNOWN

  An UNKNOWN row shows under EVERY filter setting rather than being hidden by any
  of them.  A file that cannot answer must not be assumed to answer, and a filter
  that quietly drops the runs it cannot classify is one that lies about how many
  there are.
*/
float(float r) Scores_Clean =
{
	if (rec_sb_rowflags[r] >= 0)
		return FS_RunClass(rec_sb_rowflags[r]);

	if (rec_sb_rowtag[r] == RT_PB)     return RC_CLEAN;
	if (rec_sb_rowtag[r] == RT_SHADOW) return RC_SEGMENT;
	// RT_CHEAT is build 45 and every file that carries it also carries a v4
	// `flags` key, so this line is unreachable today and is here anyway: the tag
	// is a complete answer for this one class -- exactly one thing writes it --
	// and leaving the gap would make a hand-renamed or truncated file read
	// UNKNOWN, which shows under every filter including `clean`.
	if (rec_sb_rowtag[r] == RT_CHEAT)  return RC_CHEAT;
	return RC_UNKNOWN;
};

float(float r) Scores_Passes =
{
	local float c;

	if (rec_sb_filter == SB_F_ALL)
		return TRUE;

	c = Scores_Clean(r);
	if (c == RC_UNKNOWN)
		return TRUE;
	if (rec_sb_filter == SB_F_CLEAN)
		return (c == RC_CLEAN);
	if (rec_sb_filter == SB_F_CHEATED)
		return (c == RC_CHEAT);
	// SB_F_STITCHED, which is the "not clean, not cheated" bucket -- see the
	// invariant beside the constants.
	return (c == RC_SEGMENT || c == RC_PRACTICE);
};

/*
===========================================================================
  The two lists
===========================================================================
*/

/*
  Every leg the map has, whether or not it has ever been run.

  Order is what a player expects to read down: the whole main track, then its
  stages in order, then each bonus and its stages.  Derived rather than
  enumerated, because a directory listing can only show the legs somebody has
  already finished -- and "stage 4 has no times yet" is the single most useful
  row on a board you are about to grind.
*/
void() Scores_BuildLegs =
{
	local float i, t, s, maxtrack, segs;

	rec_sb_legn = 0;
	maxtrack = 0;
	for (i = 0; i < zone_count; i = i + 1)
		if (zone_track[i] > maxtrack)
			maxtrack = zone_track[i];

	for (t = 0; t <= maxtrack; t = t + 1)
	{
		/*
		  A gap in the track numbering is legal in the zone format, so "does
		  this track exist" and "how many segments has it got" are two separate
		  questions -- Zone_TrackSegs answers 1 for a track with no zones at all,
		  which would otherwise silently produce a leg for a bonus the map does
		  not have.
		*/
		if (!Zone_TrackExists(t))
			continue;

		/*
		  Zone_TrackSegs, and NOT `max(zone_seg) + 1`, which is what this said
		  when it was written.  The END zone's own segment index IS the count, so
		  counting it as a segment invented a `stage_5` leg on surf_aesthetic --
		  a folder no run can ever be written into, drawn as a row indistinguish-
		  able from a real one until you clicked it.  The server has had this
		  right since build 9; build 24 wrote it wrong twice, here and in the
		  replay reader, which is why the rule now lives in sh_zones.qc.
		*/
		segs = Zone_TrackSegs(t);

		if (rec_sb_legn < SB_MAXLEG)
		{
			rec_sb_legtrack[rec_sb_legn] = t;
			rec_sb_legnum[rec_sb_legn]   = 0;     // leg 0: the full run of this track
			rec_sb_legn = rec_sb_legn + 1;
		}

		/*
		  Stages, and only when there is more than one: on a linear map "stage
		  1" IS the run, and a row for it would be the same leg twice.

		  BUILD 57: 1..segs INCLUSIVE, BY LEG.  This loop used to run the 0-based
		  segments 1..segs-1 and hand them to FS_RunDir as if they were stages, so
		  surf_eclipse's three stages drew as `stage 1` and `stage 2` -- which were
		  really stages 2 and 3 -- and stage 1 had no row at all, because its
		  segment is 0 and 0 was the full run.  A leg is the stage number now
		  (FS_LegOf), so the rows and the folders are the stages a player counts.
		*/
		if (segs > 1)
		for (s = 1; s <= segs; s = s + 1)
			if (rec_sb_legn < SB_MAXLEG)
			{
				rec_sb_legtrack[rec_sb_legn] = t;
				rec_sb_legnum[rec_sb_legn]   = s;     // leg s: stage s
				rec_sb_legn = rec_sb_legn + 1;
			}
	}
};

// `leg` here is the ROW index into the table above; the leg NUMBER it names is
// rec_sb_legnum[leg].  Build 57 made that number the stage itself, so the words
// below are a straight read of it rather than an offset.
string(float leg) Scores_LegName =
{
	local float t, k;

	if (leg < 0 || leg >= rec_sb_legn)
		return "?";

	t = rec_sb_legtrack[leg];
	k = rec_sb_legnum[leg];

	if (t <= 0)
	{
		if (k <= 0)
			return "main";
		return sprintf("stage %g", k);
	}
	if (k <= 0)
		return sprintf("bonus %g", t);
	return sprintf("bonus %g st %g", t, k);
};

/*
  The rows for one leg.

  ONE WILDCARD, IN THE LAST COMPONENT.  FS_RunDir spells the whole path down to
  the leg's own folder and the star is only the filename, which is the pattern
  SV_RecPrune has been running since build 23 and the one this disk has actually
  proven.  FS_NAMESORT is the ordering and it is the entire ranking.
*/
void(float leg) Scores_BuildRows =
{
	local float h, n, i, r, cut, dot;
	local string fn, base, tagw;

	rec_sb_rown     = 0;
	rec_sb_rowover  = 0;
	rec_sb_best     = 0;
	// A rescan after a finish keeps the player's place (Patch 357); a leg
	// change or an open starts at the top.
	if (rec_sb_legbuilt != -2)
		rec_sb_scroll = '0 0 0';
	rec_sb_legbuilt = leg;

	if (leg < 0 || leg >= rec_sb_legn)
		return;

	if (rec_sb_bpath < 1)
	{
		rec_sb_bpath  = buf_create_ex("string", 0);
		rec_sb_bowner = buf_create_ex("string", 0);
		rec_sb_bdate  = buf_create_ex("string", 0);
	}
	if (rec_sb_bpath < 1)
		return;

	h = search_begin(strcat(FS_RunDir(serverkey("map"),
	                                  rec_sb_legtrack[leg], rec_sb_legnum[leg]),
	                        "*.rec"),
	                 FS_NAMESORT, TRUE);
	if (h < 0)
		return;

	n = search_getsize(h);
	for (i = 0; i < n; i = i + 1)
	{
		if (rec_sb_rown >= SB_MAXROW)
		{
			rec_sb_rowover = rec_sb_rowover + 1;
			continue;
		}

		fn = search_getfilename(h, i);

		// The basename, for the stamp-and-tag parse.  Everything before the last
		// '/' is the leg directory we asked for and says nothing new.
		cut  = Scores_LastOf(fn, 47);           // '/'
		base = (cut >= 0) ? substring(fn, cut + 1, strlen(fn) - cut - 1) : fn;

		dot = strlen(base) - 4;                 // ".rec"
		if (dot < 1)
			continue;
		base = substring(base, 0, dot);

		/*
		  <ticks>[_<who>]_<tag>, or a bare <tag> for the unstamped `last`.

		  BUILD 66: THE PARSE MOVED TO sh_defs.qc, beside the speller it undoes,
		  and it grew a middle component while it was there.  It used to be
		  written out here: "the underscore is the split and there is exactly
		  one".  That stopped being true the moment a lobby run could be filed
		  under who set it, and the failure was not a wrong label -- the tag
		  would have come back as the PLAYER, FS_TagFromName would not know the
		  word, and the `continue` below would have dropped every lobby row off
		  the board with no gap and no count.  Two other files had the same two
		  lines copied into them.

		  `who` is read and not used HERE.  A local archive has one player by
		  construction, so the column would be the same value on every row; the
		  reader exists because the list is about to be shown files that were
		  written on somebody else's machine (Phase 5 R4), and a parser that
		  discards a field is a parser that has to be changed again to get it
		  back.  Anything that still does not fit is skipped rather than guessed
		  at, exactly as before.
		*/
		r    = rec_sb_rown;
		tagw = FS_NameTag(base);
		rec_sb_rowticks[r] = FS_NameTicks(base);

		/*
		  THE WORD LIST IS NOT HERE ANY MORE.  Build 45 added a fourth tag and
		  moved the name->RT_* map to FS_TagFromName in shared/sh_defs.qc, beside
		  the forward map it is the inverse of, because this scan and
		  cl_watch.qc's `replay <tag>` were two copies of it.

		  The `continue` is why that mattered: an unrecognised tag word does not
		  fall back to anything, it DROPS THE ROW.  A build that writes cheat.rec
		  and does not read it shows a leaderboard with the run simply absent --
		  no gap, no count, nothing to notice -- which is the opposite of
		  "written, labelled, never ranked".  It is also the argument for the
		  class being a header BIT rather than a tag: an unknown bit degrades to
		  a wrong word, an unknown tag degrades to silence.
		*/
		rec_sb_rowtag[r] = FS_TagFromName(tagw);
		if (rec_sb_rowtag[r] == RT_NONE)
			continue;               // not a name this game writes

		bufstr_set(rec_sb_bpath, r, fn);
		Scores_ReadHeader(r, fn);

		// The unstamped one has to be read out of its own trailer; see there.
		if (rec_sb_rowticks[r] <= 0)
			rec_sb_rowticks[r] = Scores_TrailerTicks(fn);

		rec_sb_rown = rec_sb_rown + 1;
	}
	search_end(h);

	/*
	  The reference the deltas are measured against: the fastest CLEAN run on the
	  leg, whatever the filter is currently showing.  Not "the first row" -- with
	  the filter on stitched that would make every delta relative to a practice
	  run, and a green +0.000 on a save-loaded attempt is exactly the wrong thing
	  for a leaderboard to show.  Unknowns do not set it either: a `last` file
	  from before build 24 cannot claim to be a clean best.
	*/
	for (i = 0; i < rec_sb_rown; i = i + 1)
		if (Scores_Clean(i) == RC_CLEAN)
		if (rec_sb_rowticks[i] > 0)
		if (rec_sb_best == 0 || rec_sb_rowticks[i] < rec_sb_best)
			rec_sb_best = rec_sb_rowticks[i];
};

/*
  Rebuild whenever what is on screen no longer describes what was asked for.

  The map name is strzoned because it has to outlive the serverkey call that
  produced it, and rec_sb_legzoned exists rather than testing the string itself:
  `if (str)` in QuakeC is OP_NOT_S, which is true for the EMPTY string as well as
  for a null one -- so a zoned "" would never be freed, and this runs on every
  frame the board is up.  A leak per frame is not a leak worth reasoning about.
*/
void() Scores_Refresh =
{
	local string m;

	m = serverkey("map");
	if (m == "")
		return;                     // no server yet; there is nothing to list

	if (rec_sb_legmap != m)
	{
		if (rec_sb_legzoned)
			strunzone(rec_sb_legmap);
		rec_sb_legmap   = strzone(m);
		rec_sb_legzoned = TRUE;

		Scores_BuildLegs();
		rec_sb_leg      = 0;
		rec_sb_legbuilt = -1;
	}
	// After the leg table is built (above), on the hold path and the pin alike.
	if (rec_sb_finpend)
	if (rec_sb_open || sc_held)
		Scores_ApplyFollow();
	if (rec_sb_legbuilt != rec_sb_leg)
		Scores_BuildRows(rec_sb_leg);

	/*
	  BUILD 64: AND THE ONLINE BOARD, ASKED FOR FROM HERE.

	  Once per frame the board is open, and Online_Need is a no-op on all but
	  the first -- its guard is "has anybody already asked for exactly this",
	  so a leaderboard that is DOWN gets one request per leg the player clicks
	  rather than one per frame.  The anti-hammer reasoning is written out
	  beside Online_Need itself; what belongs here is why the call is
	  unconditional: the three things that change what board is wanted are the
	  tab, the leg and the map (the tier chip is gone), plain assignments made
	  in a draw loop or a console handler.  Making each of them remember to
	  kick a fetch is four call sites that must agree, and the fourth -- a map
	  change, which nothing in this file initiates -- would have been missed.
	  One question asked every frame cannot be forgotten by a new caller.

	  THE LOCAL ROWS ARE STILL BUILT ON AN ONLINE TAB, deliberately.  It costs
	  one directory scan per leg change, it is what makes clicking Local
	  instant, and the footer reports both counts at once.
	*/
	if (Scores_IsOnline())
	if (rec_sb_leg >= 0 && rec_sb_leg < rec_sb_legn)
		Online_Need(rec_sb_legtrack[rec_sb_leg], rec_sb_legnum[rec_sb_leg],
		            OB_TIER, Scores_StyleOf());
};

/*
===========================================================================
  Drawing
===========================================================================
*/
/*
  EVERY SIZE ON THIS BOARD GOES THROUGH Font_Px, AND EVERY OFFSET IS DERIVED.

  The first cut of this file drew with hardcoded '12 12 0' and '18 18 0' and
  column offsets of 8 / 40 / 150 / 250 / 420 / 520 pixels, and both halves of
  that were wrong in the same way the replay chrome's hint line was wrong: a
  size that is not a baked rung is the same glyph resampled, and 18 is not on
  the UI ladder at all (its neighbours are 16 and 20), so the map name at the
  top was a 1.125x upscale sitting next to crisp rows.  See sh_font.qc's ladder
  essay -- it says in as many words that a call site moved to a face must have
  its constant re-checked against the rendered pixel size rather than copied.

  So: Font_Px after every Font_Set, exactly as HUD_Text does it and for exactly
  the reason the comment there gives.  And the columns are measured in CHARACTERS
  of the monospaced face rather than in pixels, because that face advances 0.6 em
  for every glyph -- so a column's position is a function of the column widths
  before it and nothing else, and the table stays aligned at any hud_scale
  instead of at the one it was eyeballed on.
*/
#define SBC_BG      '0.03 0.04 0.06'
#define SBC_PANEL   '0.07 0.08 0.11'
#define SBC_LINE    '0.30 0.55 0.85'
#define SBC_TEXT    '0.88 0.91 0.96'
#define SBC_DIM     '0.50 0.54 0.60'
#define SBC_HOT     '0.16 0.22 0.32'
#define SBC_SEL     '0.20 0.36 0.55'
#define SBC_GOOD    '0.45 0.90 0.50'
#define SBC_BAD     '0.95 0.45 0.40'
#define SBC_WARN    '1.00 0.82 0.20'

// Amber for the two states that explain a MISSING time, dim for the one that
// explains nothing.  Never red: neither is something the player did, and this
// palette's red is for a run that was refused.  Down here rather than beside
// Scores_BoardNote because these are #defines and fteqcc's preprocessor only
// knows what it has already read.
vector() Scores_BoardNoteCol =
{
	return (serverkey("board") == "ranked") ? SBC_DIM : SBC_WARN;
};

/*
  The column table, in characters of the mono face.

  Widths first, then the offsets are their running sum -- so inserting a column
  or widening one cannot leave a stale offset behind, which is what a list of
  pixel constants guarantees eventually.  The widths are worst cases: a time is
  "1:22.065" (8) and could be "10:22.065" (9), a delta carries a leading '+',
  and a Source player name is capped at 31 but 18 is what fits without pushing
  the date off a 1280-wide window.
*/
#define SBW_RANK    4
#define SBW_TIME   10
#define SBW_DELTA  11
#define SBW_OWNER  19
#define SBW_DATE   12
#define SBW_KIND    9
// BUILD 64: 7 -> 11.  The online tabs put the DEMOTION REASON in this column
// ("no ruleset", "no journal" -- 10 characters), where the local tab puts the
// file's tag.  Widening the last column only widens what the panel ASKS for;
// the clamp against the window and the drop order below are unchanged.
// PATCH 340: 11 -> 10.  The eleventh character was a gutter nobody could see
// the need for, and on a wide window it read as the dead space to the right
// of "why" that the panel was then blamed for.  Ten is the longest word the
// column can hold; the drop order still protects it on narrow windows.
#define SBW_TAG    10
/*
  BUILD 68: THE REPLAY MARK, AND ITS POSITION IS THE WHOLE POINT.

  Seven characters -- six for the longest word (was "remote") plus a gutter, which
  is what SBW_TAG was before build 64 widened it.

  IT GOES BETWEEN `player` AND `age`, NOT AT THE END, AND THAT IS NOT A TASTE
  DECISION.  The drop rule below keeps the largest of three budgets that fits:
  SBX_END, then SBX_TAG, then SBX_DATE.  With this column inserted here those
  become 83 / 72 / 51, and every one of them clears SBX_REP (44) -- so the mark
  is drawn at every window width there is.  Put at the end instead it would sit
  past SBX_TAG and vanish on the first narrowing.

  That matters because of what the RT_LOBBY precedent actually says, which is
  the opposite of how it is usually quoted.  Its WORD lives in the tag column
  and its own comment concedes that column "is the first column this board DROPS
  on a narrow window"; the amber on the TIME cell is there precisely as "the
  half of the mark that always survives".  So the precedent is not "a word
  survives" -- it is "a word does not, so pay for it in colour".  A column that
  survives on its own is the better answer to the same problem, and it is why
  this needs no second mark on the time.
*/
#define SBW_REP     7

#define SBX_RANK    0
#define SBX_TIME   (SBX_RANK  + SBW_RANK)
#define SBX_DELTA  (SBX_TIME  + SBW_TIME)
#define SBX_OWNER  (SBX_DELTA + SBW_DELTA)
#define SBX_REP    (SBX_OWNER + SBW_OWNER)
#define SBX_DATE   (SBX_REP   + SBW_REP)
#define SBX_KIND   (SBX_DATE  + SBW_DATE)
#define SBX_TAG    (SBX_KIND  + SBW_KIND)
// Patch 433: the `line` tick right of `why`, dropped first when the window narrows.
#define SBW_LINE    5
#define SBX_LINE   (SBX_TAG   + SBW_TAG)
#define SBX_END    (SBX_LINE  + SBW_LINE)

// The advance of the mono face, per em.  Measured out of GoogleMed.ttf's hmtx
// in build 21 rather than trusted from its `post` table, which claims
// isFixedPitch 0 and is simply wrong in the file.
#define SB_EM      0.6

// Per-frame layout, computed once in Scores_Draw and read by the row loop.
float rec_sb_szrow;              // the row font's pixel size, SNAPPED
float rec_sb_szhead;
float rec_sb_sztitle;
float rec_sb_cw;                 // one mono character, in pixels
float rec_sb_rowh;
float rec_sb_cols;               // how many columns the window can afford

/*
  Text, at a size the font was actually baked at.

  sui_text and not drawstring, because inside a list view sui has a frame
  transform and a clip area pushed -- a raw drawstring would ignore both and
  draw rows outside the scroll box.  The snap happens here so that no call site
  can forget it, which is the same reasoning HUD_Text is built on.
*/
void(vector pos, float sz, string text, vector col, float a) Scores_Text =
{
	sz = Font_Px(sz);
	sui_text(pos, [sz, sz], text, col, a, 0);
};

// ...and right-aligned, for the numeric columns.  A right edge has to be
// MEASURED rather than counted: the mono face makes a column's width a function
// of its character count, but the string in it may be shorter than the column.
void(vector pos, float sz, string text, vector col, float a) Scores_TextR =
{
	sz = Font_Px(sz);
	pos_x = pos_x - stringwidth(text, TRUE, [sz, sz]);
	sui_text(pos, [sz, sz], text, col, a, 0);
};

// Patch 374: the Verified mark, drawn as two lines.  None of the three faces
// has U+2713, and a missing glyph draws as a box with its hex code in it.
void(vector pos, float sz, vector col, float a) Scores_Tick =
{
	float w;
	sz = Font_Px(sz);
	sui_transform_box(pos, [sz, sz]);
	w = max(1, sz * 0.14);
	drawline(w, pos + [sz*0.06, sz*0.50] + '1 1 0', pos + [sz*0.28, sz*0.76] + '1 1 0', '0 0 0', a * 0.5, 0);
	drawline(w, pos + [sz*0.28, sz*0.76] + '1 1 0', pos + [sz*0.72, sz*0.18] + '1 1 0', '0 0 0', a * 0.5, 0);
	drawline(w, pos + [sz*0.06, sz*0.50], pos + [sz*0.28, sz*0.76], col, a, 0);
	drawline(w, pos + [sz*0.28, sz*0.76], pos + [sz*0.72, sz*0.18], col, a, 0);
};

// The x of a column, in pixels, from its character offset.
float(float chars) Scores_ColX = { return chars * rec_sb_cw; };

// A filter chip.  Returns TRUE on the frame it is clicked.  Its own size comes
// from the row size so the chips and the rows are one type scale.
float(string id, vector pos, vector sz, string label, float on) Scores_Chip =
{
	sui_action_element(pos, sz, id, sui_noop);
	sui_fill(pos, sz, on ? SBC_SEL : (sui_is_hovered(id) ? SBC_HOT : SBC_PANEL),
	         1, 0);
	sui_border_box(pos, sz, 1, on ? SBC_LINE : SBC_DIM, on ? 0.9 : 0.4, 0);
	Scores_Text([pos_x + rec_sb_cw, pos_y + (sz_y - rec_sb_szrow) * 0.5],
	            rec_sb_szrow, label, on ? SBC_TEXT : SBC_DIM, 1);
	return sui_is_released(id);
};

/*
===========================================================================
  Patch 433: board lines -- a row's run drawn in the world while you play, from
  the `line` column.  Up to SB_LNMAX at once in run-line slots 1.. (cl_lines.qc),
  built over frames by Watch_LineJob*.  An online row's file comes through the
  one replay fetch, after any watch the board asked for; a stage row played out
  of its run (Patch 395) draws only that stage.
===========================================================================
*/
#define SB_LNMAX   8
#define SBL_FREE   0
#define SBL_FETCH  1                  // waiting for its download
#define SBL_QUEUE  2                  // the file is here, waiting for the builder
#define SBL_BUILD  3
#define SBL_ON     4
#define SBL_FAIL   5

string sb_ln_key[SB_LNMAX];           // strzoned; "l:<path>" or "r<rep>:<leg>"
string sb_ln_path[SB_LNMAX];          // strzoned; an online one's once it is cached
string sb_ln_hint[SB_LNMAX];          // strzoned; an online one's cache folder
float  sb_ln_rep[SB_LNMAX];
float  sb_ln_leg[SB_LNMAX];
float  sb_ln_st[SB_LNMAX];
float  sb_ln_fetch;                   // the line the replay fetch is for, + 1
float  rec_sb_lnpick;                 // a row's box clicked this frame, row + 1

// The current tab's row as a line key, "" when nothing is behind it.
string(float row) Scores_LineKey =
{
	if (Scores_IsOnline())
	{
		if (Online_RowRep(row) < 1)
			return "";
		return sprintf("r%g:%g", Online_RowRep(row), Online_RowLeg(row));
	}
	if (row < 0 || row >= rec_sb_rown)
		return "";
	if (rec_sb_rowtag[row] == RT_LOBBY)          // nested: || does not short-circuit
		return "";
	return strcat("l:", bufstr_get(rec_sb_bpath, row));
};

float(string key) Scores_LineFind =
{
	local float i;

	for (i = 0; i < SB_LNMAX; i = i + 1)
		if (sb_ln_st[i] != SBL_FREE)
		if (!strcmp(sb_ln_key[i], key))
			return i;
	return -1;
};

void(float i) Scores_LineFree =
{
	if (wt_lj_phase)
	if (wt_lj_slot == i + 1)
		Watch_LineJobStop();
	if (sb_ln_fetch == i + 1)
		sb_ln_fetch = 0;
	Line_Clear(i + 1);
	if (sb_ln_key[i])  strunzone(sb_ln_key[i]);
	if (sb_ln_path[i]) strunzone(sb_ln_path[i]);
	if (sb_ln_hint[i]) strunzone(sb_ln_hint[i]);
	sb_ln_key[i] = sb_ln_path[i] = sb_ln_hint[i] = __NULL__;
	sb_ln_st[i] = SBL_FREE;
};

void(float row) Scores_LineToggle =
{
	local string key, s;
	local float i;

	key = Scores_LineKey(row);
	if (key == "")
	{
		print("^3scores:^7 no recording behind that row -- no line to draw.\n");
		return;
	}
	i = Scores_LineFind(key);
	if (i >= 0)
	{
		Scores_LineFree(i);
		print(sprintf("scores: line %g off\n", i + 1));
		return;
	}
	for (i = 0; i < SB_LNMAX; i = i + 1)
		if (sb_ln_st[i] == SBL_FREE)
			break;
	if (i >= SB_LNMAX)
	{
		print(sprintf("^3scores:^7 %g lines at most -- untick one first.\n", SB_LNMAX));
		return;
	}
	sb_ln_key[i] = strzone(key);
	sb_ln_rep[i] = 0;
	sb_ln_leg[i] = 0;
	sb_ln_st[i]  = SBL_QUEUE;
	if (Scores_IsOnline())
	{
		// Online_ReplayFetchRow's folder: the row's leg, or its run's for a `run`.
		sb_ln_rep[i] = Online_RowRep(row);
		sb_ln_leg[i] = Online_RowLeg(row);
		s = "";
		if (ob_have_zoned)
			s = Online_CacheDir(ob_have_map, ob_have_track,
			                    (sb_ln_leg[i] > 0) ? 0 : ob_have_leg);
		sb_ln_hint[i] = strzone(s);
		s = Online_ReplayFind(sb_ln_rep[i], s);
		if (s == "")
			sb_ln_st[i] = SBL_FETCH;
		else
			sb_ln_path[i] = strzone(s);
	}
	else
		sb_ln_path[i] = strzone(bufstr_get(rec_sb_bpath, row));
	print(sprintf("scores: line %g on: %s\n", i + 1, key));
};

/*
  Every frame, board open or not: one builder step, and the download of a line
  waiting for its file -- only while no watch is waiting on the same fetch.
*/
void() Scores_LinesFrame =
{
	local float i, k;

	if (wt_lj_phase)
	{
		k = Watch_LineJobStep();
		if (k)
		{
			i = wt_lj_slot - 1;
			sb_ln_st[i] = (k > 0) ? SBL_ON : SBL_FAIL;
			print(sprintf("scores: line %g %s (%g points, %g teleports)\n", i + 1,
			              (k > 0) ? "drawn" : "failed", ln_n[i + 1], ln_bkn[i + 1]));
		}
	}
	else
		for (i = 0; i < SB_LNMAX; i = i + 1)
			if (sb_ln_st[i] == SBL_QUEUE)
			{
				sb_ln_st[i] = Watch_LineJobStart(i + 1, sb_ln_path[i], sb_ln_leg[i])
				              ? SBL_BUILD : SBL_FAIL;
				break;
			}

	if (sb_ln_fetch)
	{
		i = sb_ln_fetch - 1;
		Online_ReplayPoll();
		if (Online_ReplayRep() != sb_ln_rep[i])
			sb_ln_fetch = 0;                    // a watch took the fetch: ask again
		else if (Online_ReplayState() == ORS_READY)
		{
			sb_ln_path[i] = strzone(Online_ReplayFile());
			sb_ln_st[i] = SBL_QUEUE;
			sb_ln_fetch = 0;
			if (!rec_sb_wantrep)
				Online_ReplayClear();
		}
		else if (Online_ReplayState() != ORS_FETCH)
		{
			sb_ln_st[i] = SBL_FAIL;
			sb_ln_fetch = 0;
			print(sprintf("^3scores:^7 line %g: the download failed (%g).\n", i + 1,
			              Online_ReplayCode()));
			if (!rec_sb_wantrep)
				Online_ReplayClear();
		}
		return;
	}
	if (rec_sb_wantrep || Online_ReplayState() == ORS_FETCH)
		return;
	for (i = 0; i < SB_LNMAX; i = i + 1)
		if (sb_ln_st[i] == SBL_FETCH)
		{
			if (Online_ReplayFetchIn(sb_ln_rep[i], sb_ln_hint[i]))
				sb_ln_fetch = i + 1;
			else
			{
				sb_ln_st[i] = SBL_FAIL;
				print(sprintf("^3scores:^7 line %g: could not ask for it -- check lobby_dir.\n",
				              i + 1));
			}
			break;
		}
};

float() Scores_LinesOn =
{
	local float i;

	for (i = 0; i < SB_LNMAX; i = i + 1)
		if (sb_ln_st[i] == SBL_ON)
			return TRUE;
	return FALSE;
};

// Before renderscene, when no replay's Watch_Path does it: pin the projection
// the 2D pass will use (see Watch_Path).
void() Scores_LinesPin =
{
	if (!Scores_LinesOn())
		return;
	makevectors(getproperty(VF_ANGLES));
	project(getproperty(VF_ORIGIN) + v_forward * 256);
};

// After renderscene, beside the replay's path.
void() Scores_LinesDraw =
{
	local float i;

	if (!Scores_LinesOn())
		return;
	Line_ViewFrame();
	Line_StatsReset();
	for (i = 0; i < SB_LNMAX; i = i + 1)
		if (sb_ln_st[i] == SBL_ON)
			Line_Draw(i + 1, 99999999, '0 0 0', 1, 0.85);
};

// `scores lines`: the table.
void() Scores_LinesStatus =
{
	local float i;
	local string w;

	for (i = 0; i < SB_LNMAX; i = i + 1)
	{
		if (sb_ln_st[i] == SBL_FREE)
			continue;
		w = "failed";
		if (sb_ln_st[i] == SBL_FETCH)      w = "fetching";
		else if (sb_ln_st[i] == SBL_QUEUE) w = "queued";
		else if (sb_ln_st[i] == SBL_BUILD) w = "building";
		else if (sb_ln_st[i] == SBL_ON)    w = "drawn";
		if (!ln_on[i + 1])
		{
			print(sprintf("  line %g %s  %s\n", i + 1, w, sb_ln_key[i]));
			continue;
		}
		print(sprintf("  line %g %s  %s  %g pts (%g shown) ", i + 1, w, sb_ln_key[i],
		              ln_n[i + 1], ln_ib[i + 1] - ln_ia[i + 1] + 1),
		      sprintf("%g tele  t %.4f..%.4f  speed %.0f..%.0f\n", ln_bkn[i + 1],
		              ln_t[(i + 1) * LN_CAP + ln_ia[i + 1]], ln_t[(i + 1) * LN_CAP + ln_ib[i + 1]],
		              ln_lo[i + 1], ln_hi[i + 1]));
	}
	w = "";
	for (i = 0; i < SB_LNMAX; i = i + 1)
		if (sb_ln_st[i] == SBL_ON)
			w = strcat(w, "*");
	print(sprintf("  lines: %g drawn, %g segments last frame\n", strlen(w), ln_nseg));
};

// A row's `line` box: empty, a tick when drawn, amber while it loads, red if it
// failed.  Registered after the row, so a click here is the box's and not a watch.
void(vector lp, float idx) Scores_LineCell =
{
	local string key, id;
	local float i, st, bs;
	local vector bp;

	if (rec_sb_cols <= SBX_LINE)
		return;
	key = Scores_LineKey(idx);
	if (key == "")
		return;
	i  = Scores_LineFind(key);
	st = (i >= 0) ? sb_ln_st[i] : SBL_FREE;
	bs = floor(Font_Px(rec_sb_szrow) * 0.75);
	bp = [lp_x + Scores_ColX(SBX_LINE) + rec_sb_cw * 0.5, lp_y + floor((rec_sb_rowh - bs) * 0.5)];
	id = strcat("sb_ln", ftos(idx));
	sui_action_element(bp - '3 3 0', [bs + 6, bs + 6], id, sui_noop);
	sui_border_box(bp, [bs, bs], 1, sui_is_hovered(id) ? SBC_TEXT : SBC_DIM, 0.9, 0);
	if (st == SBL_ON)
		Scores_Tick(bp + [bs * 0.1, 0], bs, SBC_GOOD, 0.95);
	else if (st == SBL_FAIL)
		sui_fill(bp + [bs * 0.3, bs * 0.3], [bs * 0.4, bs * 0.4], SBC_BAD, 0.9, 0);
	else if (st != SBL_FREE)
		sui_fill(bp + [bs * 0.3, bs * 0.3], [bs * 0.4, bs * 0.4], SBC_WARN, 0.9, 0);
	if (sui_is_released(id))
		rec_sb_lnpick = idx + 1;
};

/*
===========================================================================
  The rows -- one drawer per source

  BUILD 64 SPLIT THESE OUT OF Scores_Draw RATHER THAN BRANCHING INSIDE ITS ROW
  LOOP, and the reason is the column table.  The two sources share the layout
  (rank, time, delta, player, then three that fit only on a wide window) and
  share nothing else: one reads .rec headers off this disk, the other reads
  ob_* out of a JSON reply that may describe a different leg than the one on
  screen.  A single loop carrying both would need a conditional at every cell,
  which is where a board starts drawing one source's data under the other's
  heading.

  They take the layout as parameters and read the type scale from the globals
  Scores_Draw computed this frame, so neither can pick its own font size -- the
  ladder argument at the top of the drawing section applies to both.
===========================================================================
*/

/*
  This disk's recordings.  Returns the row index a click landed on, or -1 --
  see the hand-off note at the bottom of Scores_Draw for why it is returned
  rather than acted on here.
*/
float(vector rp, vector rs, float tick, float pad) Scores_DrawLocalRows =
{
	local vector lp;
	local float idx, hot, on, cl, d, ticks, pick, fin;
	local string s, rid;

	pick = -1;

	if (rec_sb_rown <= 0)
	{
		Scores_Text([rp_x, rp_y + rec_sb_szhead + pad], rec_sb_szrow,
		            "no runs recorded on this leg yet", SBC_DIM, 1);
		return pick;
	}

	// Patch 357: on the finished leg, seek once to the finish just set.
	fin = FALSE;
	if (rec_sb_finticks > 0)
	if (rec_sb_leg >= 0)
	if (rec_sb_legtrack[rec_sb_leg] == rec_sb_fintrack)
	if (rec_sb_legnum[rec_sb_leg] == rec_sb_finleg)
		fin = TRUE;
	if (fin && rec_sb_seek && !Scores_IsOnline())
	{
		for (idx = 0; idx < rec_sb_rown; idx = idx + 1)
			if (rec_sb_rowticks[idx] == rec_sb_finticks)
			{
				rec_sb_scroll_y = max(0, (idx - 2) * rec_sb_rowh);
				break;
			}
		rec_sb_seek = FALSE;
	}

	sui_list_view_begin("sb_runs", [rp_x, rp_y + rec_sb_szhead + pad * 0.5], rs,
	                    [rs_x - pad * 0.5, rec_sb_rowh], rec_sb_rown,
	                    rec_sb_scroll, [0, ceil(rec_sb_cw)]);

	lp = '0 0 0';
	for (idx = sui_list_item(lp); idx > -1; idx = sui_list_item(lp))
	{
		/*
		  A FILTERED-OUT ROW IS DRAWN DIM RATHER THAN REMOVED, and that is a
		  decision rather than laziness.  sui_list_view is virtualised on a
		  fixed item count, so hiding rows means maintaining a second index
		  from view position to real row -- which is what the map browser's
		  ms_view buffer is, and it exists there because 1,400 maps down to
		  six is a different problem from a couple of dozen runs down to
		  eighteen.  Dimming keeps the rank numbers honest (row 3 is still
		  the third fastest) and keeps "how many did the filter drop" visible
		  instead of silently changing the length of the list.
		*/
		rid = strcat("sb_run", ftos(idx));
		hot = FALSE;
		on  = Scores_Passes(idx);
		d   = lp_y + (rec_sb_rowh - rec_sb_szrow) * 0.5;   // the row's baseline

		if (fin)
		if (rec_sb_rowticks[idx] == rec_sb_finticks)
			sui_fill(lp, [rs_x - pad * 0.5, rec_sb_rowh], SBC_SEL, 0.35, 0);

		if (on)
		{
			sui_action_element(lp, [rs_x - pad * 0.5, rec_sb_rowh], rid, sui_noop);
			hot = sui_is_hovered(rid);
			if (hot)
				sui_fill(lp, [rs_x - pad * 0.5, rec_sb_rowh], SBC_HOT, 1, 0);
			if (sui_is_released(rid))
				pick = idx;
		}

		ticks = rec_sb_rowticks[idx];
		cl    = Scores_Clean(idx);

		/*
		  THE NUMBERS IN THE MONO FACE AND THE WORDS IN THE UI ONE, and the
		  face is switched per column rather than per row because Font_Px
		  snaps against whichever face is CURRENTLY selected -- the two
		  ladders differ, so a size asked for before the Font_Set snaps
		  against the wrong one and gets resampled.  That is the exact defect
		  build 21 found in HUD_DrawSeq, one function over.
		*/
		Font_Set(ui_font_mono);

		Scores_TextR([lp_x + Scores_ColX(SBX_TIME) - rec_sb_cw, d],
		             rec_sb_szrow, sprintf("%g", idx + 1),
		             SBC_DIM, on ? 1 : 0.35);

		/*
		  BUILD 57, STAGE T: A LOBBY TIME IS COLOURED, not just labelled.

		  The word is in the TAG column below, which is the first column this
		  board DROPS on a narrow window -- so on a 1280-wide screen the mark
		  would disappear and a row with no replay behind it would look like
		  every other row.  The time itself is never dropped, so the colour is
		  the half of the mark that always survives.  Amber and not green: it
		  is a real time set against real players, and it is also the one row
		  here that cannot be watched.
		*/
		Scores_Text([lp_x + Scores_ColX(SBX_TIME), d], rec_sb_szrow,
		            (ticks > 0) ? Time_TickString(ticks, tick) : "--:--.---",
		            on ? ((rec_sb_rowtag[idx] == RT_LOBBY) ? SBC_WARN : SBC_TEXT)
		               : SBC_DIM,
		            on ? 1 : 0.35);

		// The delta against the leg's fastest clean run.  The reference row
		// itself says "best" rather than "+0.000", which is a number that
		// reads as a measurement and is really a tautology.
		if (rec_sb_best > 0 && ticks > 0 && ticks != rec_sb_best)
			Scores_Text([lp_x + Scores_ColX(SBX_DELTA), d], rec_sb_szrow,
			            sprintf("+%s", Time_TickString(ticks - rec_sb_best, tick)),
			            SBC_BAD, on ? 0.9 : 0.3);
		else if (ticks > 0 && ticks == rec_sb_best)
			Scores_Text([lp_x + Scores_ColX(SBX_DELTA), d], rec_sb_szrow,
			            "best", SBC_GOOD, on ? 0.9 : 0.3);

		Font_Set(ui_font_ui);

		s = bufstr_get(rec_sb_bowner, idx);
		Scores_Text([lp_x + Scores_ColX(SBX_OWNER), d], rec_sb_szrow,
		            (s != "") ? s : "unknown", on ? SBC_TEXT : SBC_DIM,
		            on ? 0.9 : 0.35);

		if (rec_sb_cols > SBX_DATE)
		{
			s = bufstr_get(rec_sb_bdate, idx);
			Scores_Text([lp_x + Scores_ColX(SBX_DATE), d], rec_sb_szrow,
			            (s != "") ? s : "--", SBC_DIM, on ? 0.9 : 0.35);
		}

		/*
		  What kind of run this was, in one word, and the honest fourth state.

		  A v3 file has no `flags` key at all -- every recording anyone has on
		  disk before build 24 -- so `last` genuinely cannot answer and says so
		  with a dash rather than being guessed into one of the others.

		  BUILD 44: THE WORD COMES FROM FS_RunClassName AND NOT FROM A LADDER
		  HERE.  It was three branches with three literals, and the report is
		  that one of those literals was wrong on a whole class of run.  A
		  second copy of the words is a second place for that to happen.

		  THE COLOUR STAYS LOCAL, because it is the only part that is about
		  this list rather than about the run: red for cheated, amber for the
		  two middle states -- which is what `practice` already is under the
		  live timer -- green for clean, and dim for the dash.
		*/
		if (rec_sb_cols > SBX_KIND)
		{
			if (cl == RC_CLEAN)             // "multi" for a Multi-Session run
				Scores_Text([lp_x + Scores_ColX(SBX_KIND), d], rec_sb_szrow,
				            (rec_sb_rowflags[idx] > 0) ? FS_RunKindName(rec_sb_rowflags[idx])
				                                        : FS_RunClassName(cl),
				            SBC_GOOD, on ? 0.85 : 0.3);
			else if (cl == RC_CHEAT)
				Scores_Text([lp_x + Scores_ColX(SBX_KIND), d], rec_sb_szrow,
				            FS_RunClassName(cl), SBC_BAD, on ? 0.85 : 0.3);
			else if (cl == RC_UNKNOWN)
				Scores_Text([lp_x + Scores_ColX(SBX_KIND), d], rec_sb_szrow,
				            "--", SBC_DIM, on ? 0.6 : 0.25);
			else
				Scores_Text([lp_x + Scores_ColX(SBX_KIND), d], rec_sb_szrow,
				            FS_RunClassName(cl), SBC_WARN, on ? 0.85 : 0.3);
		}

		/*
		  The TAG column says WHICH FILE this row is, not what kind of run
		  it was -- the `run` column beside it already carries the word.
		  There are two unstamped slots as of build 45 and both mean the
		  same thing here: the newest of its kind, not a ranked archive
		  entry.  So both get `latest` and neither repeats what KIND says.
		*/
		/*
		  BUILD 57, STAGE T: and `lobby`, which is the one word in this column
		  that changes what a CLICK does -- see the hand-off below.  Five
		  characters, so SBW_TAG's seven still fit it.
		*/
		/*
		  BUILD 76: AND `old clock`, WHICH IS THE VERSION MARKER FOR AN ARCHIVED RUN.

		  The clock migration needed some way for a run filed before build 76 to be
		  distinguishable from one filed after, because the two were measured with
		  different instruments: the sampled clock ran 0-2 ticks long, always in the
		  same direction, so a mixed list sorts two measurements into one order and
		  the delta column differences across them.  That is exactly the cost build
		  43 named when the stage measurement changed -- one list ranking runs that
		  were never comparable -- and it was called out then as a real price rather
		  than waved through.

		  THE MARKER IS THE FILE'S OWN VERSION AND IT WAS ALREADY BEING READ.  The
		  obvious route was a marker in the FILENAME, which would have touched
		  FS_RunPathWho's grammar, the 7-digit stamp parse, FS_TagFromName, the
		  pruner's glob and ui_who -- for a fact the file already states on its
		  first line.  Scores_ReadHeader has parsed `FTESURF-REC <n>` into
		  rec_sb_rowver[] for every listed row since build 23; nothing drew it.  So
		  the whole marker is this branch.  Same shape as the padding ring on the
		  server side: the cheap route was the one that added nothing.

		  THIS COLUMN, because for the rows that matter it is EMPTY.  A stamped
		  archive row -- which is every row in a PB list, and the only kind whose
		  ordering this can distort -- draws nothing here today.  `lobby` keeps
		  precedence because it is the one word in this column that changes what a
		  CLICK does, and `latest` keeps it over this because a fixed-name file is
		  overwritten every attempt, so its clock is whatever the last attempt used
		  and the word would go stale in place.

		  VERSION 0 IS NOT VERSION 4.  A row whose header could not be read at all
		  leaves rec_sb_rowver at 0, and drawing `old clock` for it would be
		  asserting a measurement about a file nothing could open -- the sv_mapcheck
		  shape, a comparison whose two sides are not comparable answering anyway.
		  Unknown draws nothing, which is this board's standing rule since build 65.

		  Nine characters, so SBW_TAG's eleven still fit, and the same two words the
		  online tab uses for TF_NOCLOCK -- deliberately, because it is the same fact
		  about the reader's row: this time was taken on the old clock.
		*/
		if (rec_sb_cols > SBX_TAG)
		{
			if (rec_sb_rowtag[idx] == RT_LOBBY)
			{
				// A demoted lobby run is kept here (LT_Keep) and says why it is
				// on no board; FS_CertWhy's words fit SBW_TAG.
				s = "";
				if (rec_sb_rowflags[idx] > 0)
					s = FS_CertWhy(rec_sb_rowflags[idx]);
				if (s == "")
					s = "lobby";
				Scores_Text([lp_x + Scores_ColX(SBX_TAG), d], rec_sb_szrow,
				            s, SBC_WARN, on ? 0.85 : 0.3);
			}
			else if (rec_sb_rowtag[idx] == RT_LAST || rec_sb_rowtag[idx] == RT_CHEAT)
				Scores_Text([lp_x + Scores_ColX(SBX_TAG), d], rec_sb_szrow,
				            "latest", SBC_DIM, on ? 0.7 : 0.25);
			else if (rec_sb_rowver[idx] > 0 && rec_sb_rowver[idx] < 5)
				Scores_Text([lp_x + Scores_ColX(SBX_TAG), d], rec_sb_szrow,
				            "old clock", SBC_DIM, on ? 0.7 : 0.25);
		}
		Scores_LineCell(lp, idx);           // Patch 433
	}
	sui_list_view_end();

	return pick;
};

/*
  surfd's board -- OB_TIER, in the style the tab names.

  IT DRAWS FOUR DIFFERENT KINDS OF NOTHING, and that is most of the function.

  The local list has one empty state, because a directory either has files in
  it or does not.  A network board has four, they mean entirely different
  things to the player, and collapsing them into "no times" is what makes an
  unplugged install look like an unplayed map:

    not configured  lobby_dir is "" -- an offline install, which is a normal
                    way to own this game and is not a fault
    still asking    a request is in flight; the rows in memory, if any, are
                    some other leg's
    did not answer  it answered with a code, or the reply would not parse --
                    the last good rows are deliberately still in memory, but
                    they are not THIS board's, so they are not drawn
    genuinely none  it answered, and this leg has no times of this kind yet

  Only the fourth is "no times".
*/
float(vector rp, vector rs, float pad) Scores_DrawOnlineRows =
{
	local vector lp, ncol;
	local float idx, hot, d, ref, i, track, leg, pick, pinned;
	local string s, rid;

	if (rec_sb_leg < 0 || rec_sb_leg >= rec_sb_legn)
		return -1;

	track = rec_sb_legtrack[rec_sb_leg];
	leg   = rec_sb_legnum[rec_sb_leg];

	/*
	  Online_Describes and NOT `ob_state == OBS_OK`.  A reply that landed for
	  the previous leg leaves the state OK and the rows valid -- for that leg.
	  Asking whether the stored rows describe THIS board is the whole of trap 3
	  in cl_online.qc, and it is one function call here because it is one fact
	  there.
	*/
	// Shows, not Describes: a refetch of this same board keeps its rows up.
	if (!Online_Shows(track, leg, OB_TIER, Scores_StyleOf()))
	{
		lp = [rp_x, rp_y + rec_sb_szhead + pad];

		if (ob_state == OBS_NOTERMS)
		{
			/*
			  NOT AN ERROR, AND IT MUST NOT LOOK LIKE ONE.  Nothing was asked
			  and nothing was disclosed, which is the correct behaviour for a
			  player who has not accepted the online terms -- see the essay at
			  the top of Online_Fetch.  Dim, like the unconfigured case, rather
			  than red like a failure.
			*/
			Scores_Text(lp, rec_sb_szrow,
			            "the online terms have not been accepted",
			            SBC_DIM, 1);
			Scores_Text([lp_x, lp_y + rec_sb_rowh], rec_sb_szrow,
			            "accept them from the main menu to see online times",
			            SBC_DIM, 0.7);
		}
		else if (ob_state == OBS_NODIR)
		{
			Scores_Text(lp, rec_sb_szrow,
			            "this install is not pointed at a leaderboard",
			            SBC_DIM, 1);
			Scores_Text([lp_x, lp_y + rec_sb_rowh], rec_sb_szrow,
			            "set one with:  lobby_dir \"http://host:8084\"",
			            SBC_DIM, 0.7);
		}
		else if (ob_state == OBS_FAIL)
		{
			/*
			  THE THREE FAILURES ARE THREE DIFFERENT SENTENCES, because they
			  ask the player for three different things -- and "the leaderboard
			  answered 404" asks for nothing at all, which is why it read as a
			  dead end when a real player hit it.

			  404 is the one case where the SERVER is fine and the endpoint is
			  simply not there, which is an operator problem and not the
			  player's; 429 clears by itself and says so; anything else is the
			  directory being unreachable or unwell.
			*/
			if (ob_code == 404)
			{
				Scores_Text(lp, rec_sb_szrow,
				            "this leaderboard does not offer a board for this map",
				            SBC_BAD, 1);
				Scores_Text([lp_x, lp_y + rec_sb_rowh], rec_sb_szrow,
				            "the directory is up, but has no /api/board -- tell whoever runs it",
				            SBC_DIM, 0.7);
			}
			else if (ob_code == 429)
			{
				Scores_Text(lp, rec_sb_szrow,
				            "the leaderboard is busy -- asking again shortly",
				            SBC_WARN, 1);
				Scores_Text([lp_x, lp_y + rec_sb_rowh], rec_sb_szrow,
				            "nothing is wrong with your run or your times",
				            SBC_DIM, 0.7);
			}
			else
			{
				Scores_Text(lp, rec_sb_szrow,
				            (ob_code > 0)
				              ? sprintf("the leaderboard answered %g", ob_code)
				              : "the leaderboard could not be reached",
				            SBC_BAD, 1);
				Scores_Text([lp_x, lp_y + rec_sb_rowh], rec_sb_szrow,
				            "your own times are on the Local tab, and are unaffected",
				            SBC_DIM, 0.7);
			}
		}
		else
			Scores_Text(lp, rec_sb_szrow, "asking the leaderboard...",
			            SBC_DIM, 1);
		return -1;
	}

	if (ob_n <= 0)
	{
		lp = [rp_x, rp_y + rec_sb_szhead + pad];
		Scores_Text(lp, rec_sb_szrow,
		            sprintf("no %s times on this leg yet", Scores_StyleOf()),
		            SBC_DIM, 1);
		return -1;
	}

	/*
	  THE DELTA REFERENCE IS THE FASTEST ROW IN MILLISECONDS, not the first row
	  and not the fastest tick count.

	  surfd ranks by millis for a reason it writes down: a tick is only a
	  duration at a tickrate, and 4000 ticks at 100 Hz beats 3000 at 50 Hz
	  despite being the larger number.  Subtracting two rows' ticks would
	  reproduce exactly that bug in the delta column, on a board that had
	  ordered them correctly -- so the rank and the gap would disagree.
	*/
	ref = 0;
	for (i = 0; i < ob_n; i = i + 1)
		if (ob_ms[i] > 0)
		if (ref == 0 || ob_ms[i] < ref)
			ref = ob_ms[i];

	// Patch 357.  The player's own row, pinned under the list when the finish
	// just set ranks past the page (OB_MAXROW); then the one-time seek to it.
	pinned = FALSE;
	if (ob_mine < 0 && rec_sb_finrank > 0 && ob_n > 0)
	if (track == rec_sb_fintrack && leg == rec_sb_finleg)
	if (!strcmp(Scores_StyleOf(), Scores_FinStyle()))
	if (rec_sb_finrank > ob_rank[ob_n - 1])
	{
		pinned = TRUE;
		rs_y = rs_y - rec_sb_rowh;
	}
	if (rec_sb_seek && !rec_sb_finwait && ob_state == OBS_OK && ob_q_gen == ob_gen)
	if (track == rec_sb_fintrack && leg == rec_sb_finleg)
	if (!strcmp(Scores_StyleOf(), Scores_FinStyle()))
	{
		if (ob_mine >= 0)
			rec_sb_oscroll_y = max(0, (ob_mine - 2) * rec_sb_rowh);
		rec_sb_seek = FALSE;
	}

	sui_list_view_begin("sb_online", [rp_x, rp_y + rec_sb_szhead + pad * 0.5], rs,
	                    [rs_x - pad * 0.5, rec_sb_rowh], ob_n,
	                    rec_sb_oscroll, [0, ceil(rec_sb_cw)]);

	// Explicitly, and not left to the local stack: 0 means "nobody clicked",
	// and a row index of 0 is a real answer -- hence the +1 at the click site.
	pick = 0;
	lp = '0 0 0';
	for (idx = sui_list_item(lp); idx > -1; idx = sui_list_item(lp))
	{
		rid = strcat("sb_ob", ftos(idx));
		d   = lp_y + (rec_sb_rowh - rec_sb_szrow) * 0.5;

		/*
		  CLICKABLE WHEN THERE IS SOMETHING BEHIND IT -- build 66, step R5.

		  This used to refuse every online row with "online times are set on
		  other machines -- there is no replay on this disk", which was true
		  when it was written and is now true of only some rows.  A lobby
		  writes a .rec, surfd indexes it, and the row carries the ledger id;
		  what is missing is a download, not a recording.

		  THE PICK IS RETURNED, NEVER ACTED ON HERE, and the local drawer's
		  essay one function down is the reason: acting inside the list runs
		  with the scroll view's clip still pushed and sui's click-once state
		  uncleared, so the next frame sees the same release and fires twice.
		*/
		sui_action_element(lp, [rs_x - pad * 0.5, rec_sb_rowh], rid, sui_noop);
		hot = sui_is_hovered(rid);
		/*
		  THE HIGHLIGHT IS THE AFFORDANCE: a row with no recording behind it
		  does not light up, so the list says which rows are worth clicking
		  before one is clicked.  It still ACCEPTS the click -- silence is
		  worse than a sentence -- and the hand-off says which of the three
		  reasons applies.

		  Still owed: the same fact as a WORD, in a column, per the RT_LOBBY
		  precedent.  Colour alone is a poor mark and this board has no spare
		  column to put one in yet.
		*/
		if (idx == ob_mine)
			sui_fill(lp, [rs_x - pad * 0.5, rec_sb_rowh], SBC_SEL, 0.45, 0);
		if (hot)
		if (Online_RowRep(idx) > 0)
			sui_fill(lp, [rs_x - pad * 0.5, rec_sb_rowh], SBC_HOT, 1, 0);
		if (sui_is_released(rid))
			pick = idx + 1;     // +1 so row 0 is distinguishable from "none"

		Font_Set(ui_font_mono);

		/*
		  THE SERVER'S RANK, NOT `idx + 1`.  They agree today because nothing
		  asks for an offset, but the row carries `r` precisely so that a
		  second page would not renumber itself from 1 -- and a board whose
		  displayed rank is a function of the scroll position is wrong in a
		  way nobody would think to check.
		*/
		Scores_TextR([lp_x + Scores_ColX(SBX_TIME) - rec_sb_cw, d],
		             rec_sb_szrow, sprintf("%g", ob_rank[idx]), SBC_DIM, 1);

		/*
		  EVERY ROW AT ITS OWN RATE.  Time_TickString wants SECONDS PER TICK
		  and surfd stores HERTZ; the inversion is here rather than at the
		  parse so the stored value stays in the server's units, which is the
		  rule cl_online.qc's header sets out.  Getting it backwards printed
		  0:52.500 as 64:48:53.328.
		*/
		Scores_Text([lp_x + Scores_ColX(SBX_TIME), d], rec_sb_szrow,
		            Time_TickString(ob_ticks[idx], 1 / ob_rate[idx]),
		            SBC_TEXT, 1);

		/*
		  Milliseconds formatted AS milliseconds: Time_TickString(ms, 0.001)
		  multiplies back to exactly the number it was given, so the same
		  m:ss.mmm formatting serves a gap that was never measured in ticks
		  at all.  No second formatter, and no tickrate assumed for a
		  difference between two runs that may not share one.
		*/
		if (ref > 0 && ob_ms[idx] > ref)
			Scores_Text([lp_x + Scores_ColX(SBX_DELTA), d], rec_sb_szrow,
			            sprintf("+%s", Time_TickString(ob_ms[idx] - ref, 0.001)),
			            SBC_BAD, 0.9);
		else if (ref > 0 && ob_ms[idx] == ref)
			Scores_Text([lp_x + Scores_ColX(SBX_DELTA), d], rec_sb_szrow,
			            "best", SBC_GOOD, 0.9);

		Font_Set(ui_font_ui);

		s = bufstr_get(ob_bname, idx);
		ncol = SBC_TEXT;
		if (idx == ob_mine)
			ncol = SBC_GOOD;
		Scores_Text([lp_x + Scores_ColX(SBX_OWNER), d], rec_sb_szrow,
		            (s != "") ? s : "unknown", ncol, 0.9);

		/*
		  WHETHER THERE IS ANYTHING BEHIND THIS ROW TO OPEN -- build 68.

		  GREEN IS FOR THE ACTIONABLE ONE ONLY.  "watch" is the single row state
		  on this board that a click does something with, so it gets the one
		  colour that means "yes"; both negatives are SBC_DIM and neither is
		  SBC_BAD, on the rule this palette already follows for the `why` column
		  below -- red here is for a run that was REFUSED, and a missing
		  recording is not something the player did.

		  The guard is insurance rather than live logic: SBX_REP is 44 and the
		  narrowest budget the drop rule can choose is 51, so this is true at
		  every width today.  It is written anyway because a fourth drop step is
		  exactly the kind of thing that gets added later, and an unguarded
		  column is how the one that was added last time ran off the edge.
		*/
		if (rec_sb_cols > SBX_REP)
		{
			s = Online_RepString(idx);
			Scores_Text([lp_x + Scores_ColX(SBX_REP), d], rec_sb_szrow,
			            s, (Online_RowRep(idx) > 0) ? SBC_GOOD : SBC_DIM, 0.85);
			// Patch 374: after the word; "watch" + the mark fits SBW_REP in Roboto.
			if (ob_ver[idx] > 0)
				Scores_Tick([lp_x + Scores_ColX(SBX_REP) + rec_sb_cw * 0.3
				             + stringwidth(s, TRUE, [Font_Px(rec_sb_szrow), Font_Px(rec_sb_szrow)]), d],
				            rec_sb_szrow, SBC_GOOD, 0.95);
		}

		if (rec_sb_cols > SBX_DATE)
		{
			s = Online_AgeString(idx);
			Scores_Text([lp_x + Scores_ColX(SBX_DATE), d], rec_sb_szrow,
			            (s != "") ? s : "--", SBC_DIM, 0.9);
		}

		/*
		  THE CLASS WORD IS REDUNDANT HERE AND IS DRAWN ANYWAY, as a
		  cross-check rather than as information.  surfd derives `style` from
		  `flags` with its own mirror of FS_RunClass, so every row on the
		  clean tab should read `clean` and every row on the segmented tab
		  `segmented`.  If one ever does not, the two implementations of that
		  precedence have diverged -- which is a real risk with a rule written
		  twice in two languages, and this column is the only place it would
		  ever be visible.
		*/
		if (rec_sb_cols > SBX_KIND)
		{
			i = FS_RunClass(ob_flags[idx]);
			Scores_Text([lp_x + Scores_ColX(SBX_KIND), d], rec_sb_szrow,
			            FS_RunClassName(i),
			            (i == RC_CLEAN) ? SBC_GOOD : SBC_WARN, 0.85);
		}

		/*
		  WHY this row is not ranked, when the run itself says so.  Amber and
		  never red: the TF_UNCERT bits describe a hole in the certification,
		  not something the player did.  Blank on a ranked board by construction.
		*/
		if (rec_sb_cols > SBX_TAG)
		{
			s = Online_WhyString(idx);
			if (s != "")
				Scores_Text([lp_x + Scores_ColX(SBX_TAG), d], rec_sb_szrow,
				            s, SBC_WARN, 0.85);
		}
		Scores_LineCell(lp, idx);           // Patch 433
	}
	sui_list_view_end();

	// The pinned own row: rank, the standing time, the name.  Not clickable.
	if (pinned)
	{
		lp = [rp_x, rp_y + rec_sb_szhead + pad * 0.5 + rs_y];
		sui_fill(lp, [rs_x - pad * 0.5, rec_sb_rowh], SBC_SEL, 0.45, 0);
		d = lp_y + (rec_sb_rowh - rec_sb_szrow) * 0.5;
		Font_Set(ui_font_mono);
		Scores_TextR([lp_x + Scores_ColX(SBX_TIME) - rec_sb_cw, d],
		             rec_sb_szrow, sprintf("%g", rec_sb_finrank), SBC_DIM, 1);
		if (rec_sb_finbest > 0)
			Scores_Text([lp_x + Scores_ColX(SBX_TIME), d], rec_sb_szrow,
			            Time_TickString(rec_sb_finbest, 0.001), SBC_TEXT, 1);
		Font_Set(ui_font_ui);
		Scores_Text([lp_x + Scores_ColX(SBX_OWNER), d], rec_sb_szrow,
		            getplayerkeyvalue(player_localnum, "name"), SBC_GOOD, 0.9);
	}
	// Patch 395: `scores olpick`, a click minus the hit test.
	if (!pick)
	if (rec_sb_olpick > 0)
	if (rec_sb_olpick <= ob_n)
	{
		pick = rec_sb_olpick;
		print(sprintf("scores: olpick row %g\n", pick - 1));
	}
	rec_sb_olpick = 0;
	return pick - 1;
};

/*
  Acting on a click in the ONLINE list -- build 66, step R5.

  TWO PHASES, BECAUSE THE FILE IS NOT HERE YET.  The local list can hand a path
  straight to Watch_Open; this one has to ask for ~1 MB over the network first,
  so the click STARTS something and a later frame finishes it.  Both halves run
  from here, after sui_end, for the reason the local hand-off gives at length.

  THE INTENT IS REMEMBERED IN rec_sb_wantrep, and that is not bookkeeping for
  its own sake.  The download completes in the engine whether or not this board
  is open -- URI_Get_Callback is driven by the transfer, not by the draw -- so
  without a live intent, closing the board mid-fetch and reopening it later
  would find a READY replay sitting there and open it, seconds after the player
  had moved on.  Closing the board cancels the intent; the bytes are still
  cached, so the next click on that row is instant.
*/
void(float pick) Scores_OnlineHandOff =
{
	local string path;
	local float rep, st, code, leg;

	if (pick >= 0)
	{
		// Patch 395: a stage row with no recording of its own plays its run's.
		rep = Online_RowRep(pick);
		leg = Online_RowLeg(pick);
		if (rep < 1)
		{
			if (ob_have_leg > 0)
				print("^3scores:^7 no recording was kept for that stage time -- "
				      "the run it was set in was not kept (unranked, expired, or "
				      "before recorded lobbies).\n");
			else
				print("^3scores:^7 no recording was kept for that run -- "
				      "it predates recorded lobbies, or none was stored.\n");
		}
		else
		{
			rec_sb_wantrep = rep;
			rec_sb_wantleg = leg;
			if (!Online_ReplayFetchRow(pick))
				print("^3scores:^7 could not ask for that replay -- "
				      "check lobby_dir.\n");
			else if (Online_ReplayState() == ORS_FETCH)
				print("^3scores:^7 fetching replay...\n");
		}
	}

	// The deadline: nothing else polls, and the engine's HTTP client has no
	// wall-clock timeout of its own.
	Online_ReplayPoll();

	if (!rec_sb_wantrep)
		return;

	st = Online_ReplayState();

	if (st == ORS_FAIL)
	{
		code = Online_ReplayCode();
		if (code == 404)
			print("^3scores:^7 that recording is no longer on the server.\n");
		else if (code == 429)
			print("^3scores:^7 too many replay downloads just now -- "
			      "try again in a minute.\n");
		else if (code)
			print(sprintf("^3scores:^7 replay download failed (%g).\n", code));
		else
			print("^3scores:^7 replay download failed.\n");
		rec_sb_wantrep = 0;
		rec_sb_wantleg = 0;
		Online_ReplayClear();
		return;
	}

	if (st != ORS_READY)
		return;

	// A reply for a row the player has since clicked away from is not this
	// board's business: the id that landed must be the id still wanted.
	if (Online_ReplayRep() != rec_sb_wantrep)
		return;

	path = Online_ReplayFile();
	if (path == "")
	{
		rec_sb_wantrep = 0;
		rec_sb_wantleg = 0;
		return;
	}

	/*
	  ORDER MATTERS: Watch_Open reads the file while `path` still points into
	  cl_online.qc's strzone, so the clear comes last.  Scores_Close touches
	  neither -- but it clears rec_sb_wantleg, so the leg is taken first.
	*/
	leg = rec_sb_wantleg;
	rec_sb_wantrep = 0;
	rec_sb_wantleg = 0;
	Scores_Close();
	rec_wt_wantleg = leg;           // Patch 431: cut to the stage as it opens
	Watch_Open(path);
	Online_ReplayClear();
};

// Patch 372: the map clock beside the title, dropped (next map first) if it cannot fit.
void(vector tp, float xmax) Scores_DrawClock =
{
	local string s, t;
	local float x;
	local vector col;

	s = HUD_MapClockText();
	if (s == "")
		return;
	t = serverkey("map");
	if (t == "")
		t = "no map";
	x = tp_x + stringwidth(t, TRUE, [rec_sb_sztitle, rec_sb_sztitle]) + rec_sb_cw * 3;
	col = SBC_DIM;
	if (ui_mc_level == 1)
		col = SBC_WARN;
	else if (ui_mc_level == 2)
		col = SBC_BAD;
	t = HUD_SK("mapnext");
	if (ui_mc_state != 2)
	if (t != "")
	if (x + stringwidth(strcat(s, "   next ", t), TRUE, [rec_sb_szhead, rec_sb_szhead]) <= xmax)
		s = strcat(s, "   next ", t);
	if (x + stringwidth(s, TRUE, [rec_sb_szhead, rec_sb_szhead]) > xmax)
		return;
	Scores_Text([x, tp_y + rec_sb_sztitle - rec_sb_szhead], rec_sb_szhead, s, col, 1);
};

// Patch 385: a room-list row click (cl_players.qc), after sui_end like the replay
// pick.  The board closes only when a request actually went out.
float() Scores_SpecHandOff =
{
	local float slot;

	if (!pl_specpick)
		return FALSE;
	slot = pl_specpick - 1;
	pl_specpick = 0;
	if (!Spec_Request(slot))
		return FALSE;
	Scores_Close();
	return TRUE;
};

void(vector scr) Scores_Draw =
{
	local vector p, sz, rp, rs, lp;
	local float w, h, x0, y0, lw, idx, hot, on, tick, pick;
	local float scale, chipw, chiph, pad, legw, ytabs, yhead, footh;
	local string s, rid;

	if (!rec_sb_open && !sc_held)
		return;

	Scores_Refresh();

	sui_begin(scr_x, scr_y);

	// The panel: most of the screen, with the world dimmed behind it rather than
	// hidden.  A leaderboard you cannot see the map through reads as a menu, and
	// this one is opened mid-session with the same key you use to peek.
	sui_fill('0 0 0', [scr_x, scr_y], '0 0 0', 0.55, 0);

	/*
	  THE TYPE SCALE, and it is read here rather than inherited.

	  ui_cv_scale is set by HUD_ReadCvars at the top of HUD_Draw, which does run
	  before this every frame -- but only on the frames HUD_Draw runs at all, and
	  a board that changes size when the HUD is switched off would be a genuinely
	  baffling bug.  One cvar read while the board is up costs nothing.

	  The bases are chosen so that hud_scale 2 lands ON a rung of each ladder
	  rather than relying on Font_Px to round: 6*2 = 12 and 8*2 = 16 are both UI
	  and mono rungs.  Font_Px still runs, because hud_scale is a float and
	  somebody will set it to 1.5.
	*/
	scale = cvar("hud_scale");
	if (scale <= 0)
		scale = 2;

	Font_Set(ui_font_mono);
	rec_sb_szrow  = Font_Px(6 * scale);
	rec_sb_cw     = rec_sb_szrow * SB_EM;

	Font_Set(ui_font_ui);
	rec_sb_szhead  = Font_Px(6 * scale);
	rec_sb_sztitle = Font_Px(8 * scale);

	pad   = ceil(rec_sb_cw * 1.5);
	rec_sb_rowh = ceil(rec_sb_szrow * 1.7);
	chiph = ceil(rec_sb_szrow * 1.8);

	/*
	  The panel's size, and the width is asked for in CHARACTERS.

	  SBX_END is the whole table's width, so the panel asks for exactly what its
	  contents need plus the leg column plus padding, and is then clamped to the
	  window.  Asking for a fraction of the screen and hoping the columns fit
	  inside it is what put the replay chrome's hint line out through its own
	  border, and this is the same mistake one panel over.
	*/
	legw = ceil(rec_sb_cw * 15);
	w = SBX_END * rec_sb_cw + legw + pad * 4;
	if (w > scr_x - pad * 2) w = scr_x - pad * 2;
	/*
	  PATCH 340: THE FLOOR DROPPED FROM HALF THE WINDOW TO 42%.

	  The floor existed so a narrow window could not squeeze the board into
	  illegibility, but on a WIDE one it did the opposite harm: the content
	  asks for ~78 characters and the clamp handed the panel 960 px anyway,
	  and the ~200 px of difference landed to the right of the last column --
	  "the why column has way too much room", as the report put it.  The
	  slack was never the column's; it was the clamp's.  42% still clears
	  every column budget at 1280 and stops inventing space at 1920.
	*/
	if (w < scr_x * 0.42)     w = scr_x * 0.42;

	h = scr_y * 0.78;
	if (h > rec_sb_rowh * 26) h = rec_sb_rowh * 26;

	x0 = floor((scr_x - w) * 0.5);
	y0 = floor((scr_y - h) * 0.5);
	p  = [x0, y0];
	sz = [w, h];

	sui_fill(p, sz, SBC_BG, 0.94, 0);
	sui_border_box(p, sz, 1, SBC_LINE, 0.9, 0);

	// ---- the header ------------------------------------------------------
	Font_Set(ui_font_ui);
	Scores_Text([x0 + pad, y0 + pad], rec_sb_sztitle,
	            (serverkey("map") != "") ? serverkey("map") : "no map",
	            SBC_TEXT, 1);
	Scores_DrawClock([x0 + pad, y0 + pad], Scores_IsOnline() ? x0 + w - pad
	                 : x0 + w - pad * 5 - ceil(rec_sb_cw * 10) * 4);   // left of the chips

	if (zone_count <= 0)
	{
		Scores_Text([x0 + pad, y0 + pad * 2 + rec_sb_sztitle], rec_sb_szhead,
		            "this map has no zone file, so it has no legs and no times",
		            SBC_DIM, 1);
		pl_boardbusy = FALSE;             // no legs: no online board to protect
		Players_Panel(p, sz, pad, scr);   // Patch 340: the room list is not
		sui_end();                        // about zones; it shows here too.
		Font_Reset();
		Scores_SpecHandOff();
		return;
	}

	/*
	  The class chips, top right, on LOCAL only (build 44).  "all" is the
	  default: hiding rows by default makes a board that disagrees with the
	  folder it came from.  The online tabs have no chips (Patch 355: ranked
	  only -- never merge tiers, which is why there was never an "all" there).
	*/
	chipw = ceil(rec_sb_cw * 10);
	if (!Scores_IsOnline())
	{
		if (Scores_Chip("sb_fx", [x0 + w - pad - chipw, y0 + pad], [chipw, chiph],
		                "cheated", rec_sb_filter == SB_F_CHEATED))
			rec_sb_filter = SB_F_CHEATED;
		if (Scores_Chip("sb_fs", [x0 + w - pad * 2 - chipw * 2, y0 + pad],
		                [chipw, chiph], "stitched", rec_sb_filter == SB_F_STITCHED))
			rec_sb_filter = SB_F_STITCHED;
		if (Scores_Chip("sb_fc", [x0 + w - pad * 3 - chipw * 3, y0 + pad],
		                [chipw, chiph], "clean", rec_sb_filter == SB_F_CLEAN))
			rec_sb_filter = SB_F_CLEAN;
		if (Scores_Chip("sb_fa", [x0 + w - pad * 4 - chipw * 4, y0 + pad],
		                [chipw, chiph], "all", rec_sb_filter == SB_F_ALL))
			rec_sb_filter = SB_F_ALL;
	}

	/*
	  ---- the tabs, on their own row ---------------------------------------

	  A ROW OF THEIR OWN AND NOT BESIDE THE MAP NAME.  The obvious cheaper
	  layout puts them to the right of the title and costs no vertical space,
	  but the title is a map name of unbounded width -- surf_air_arena_rebuild
	  is a real file -- so the tabs would collide with it on exactly the maps
	  whose names are longest, and nowhere else.  One row is 1/26th of the
	  panel's height and is predictable at every width.

	  The refresh chip is the ONLY way an online tab re-asks for a board it has
	  already asked for; see the anti-hammer note beside Online_Need.  It is
	  drawn only on the online tabs because the local list rebuilds itself from
	  the directory on every open anyway.
	*/
	ytabs = y0 + pad * 2 + rec_sb_sztitle;
	if (Scores_Chip("sb_t0", [x0 + pad, ytabs], [chipw, chiph],
	                "online", rec_sb_tab == SB_T_ONLINE))
	{
		rec_sb_tab = SB_T_ONLINE;
		rec_sb_tabauto = FALSE;     // the player chose; the follow leaves it
	}
	if (Scores_Chip("sb_t1", [x0 + pad * 2 + chipw, ytabs], [chipw, chiph],
	                "segmented", rec_sb_tab == SB_T_SEGMENT))
	{
		rec_sb_tab = SB_T_SEGMENT;
		rec_sb_tabauto = FALSE;
	}
	if (Scores_Chip("sb_t2", [x0 + pad * 3 + chipw * 2, ytabs], [chipw, chiph],
	                "local", rec_sb_tab == SB_T_LOCAL))
	{
		rec_sb_tab = SB_T_LOCAL;
		rec_sb_tabauto = FALSE;
	}

	if (Scores_IsOnline())
	if (rec_sb_leg >= 0 && rec_sb_leg < rec_sb_legn)
	if (Scores_Chip("sb_tref", [x0 + w - pad - chipw, ytabs], [chipw, chiph],
	                "refresh", FALSE))
		Online_Fetch(rec_sb_legtrack[rec_sb_leg], rec_sb_legnum[rec_sb_leg],
		             OB_TIER, Scores_StyleOf());

	yhead = ytabs + chiph + ceil(pad * 0.5);

	// ---- the legs, down the left ----------------------------------------
	lw = legw;
	rp = [x0 + pad, yhead];
	Scores_Text(rp, rec_sb_szhead, "leg", SBC_DIM, 1);

	/*
	  THE FOOTER IS TWO LINES NOW, AND BOTH LISTS HAVE TO KNOW.

	  Every list height below ends `- pad * 2 - footh`, where footh used to be
	  the single row the counts line occupies.  Build 64 adds the board-state
	  sentence underneath it (Scores_BoardNote), and reserving the space in only
	  one of the two lists would leave the legs column overlapping the text.

	  RESERVED UNCONDITIONALLY, even on a server that publishes no state and
	  therefore draws nothing there.  A panel whose list is a row taller when
	  the server happens to be old is a layout that moves under the player for
	  reasons they cannot see -- and one blank row costs less than that.
	*/
	footh = rec_sb_szrow * 2 + ceil(pad * 0.35);

	lp = [x0 + pad, rp_y + rec_sb_szhead + pad * 0.5];
	sui_list_view_begin("sb_legs", lp, [lw, y0 + h - lp_y - pad * 2 - footh],
	                    [lw - pad * 0.5, rec_sb_rowh], rec_sb_legn,
	                    rec_sb_legscroll, [0, ceil(rec_sb_cw)]);
	rs = [lw - pad * 0.5, rec_sb_rowh];
	lp = '0 0 0';
	for (idx = sui_list_item(lp); idx > -1; idx = sui_list_item(lp))
	{
		rid = strcat("sb_leg", ftos(idx));
		sui_action_element(lp, rs, rid, sui_noop);

		on  = (idx == rec_sb_leg);
		hot = sui_is_hovered(rid);
		if (on || hot)
			sui_fill(lp, rs, on ? SBC_SEL : SBC_HOT, 1, 0);

		Scores_Text([lp_x + rec_sb_cw, lp_y + (rec_sb_rowh - rec_sb_szrow) * 0.5],
		            rec_sb_szrow, Scores_LegName(idx),
		            (on || hot) ? SBC_TEXT : SBC_DIM, 1);

		if (sui_is_released(rid))
			rec_sb_leg = idx;
	}
	sui_list_view_end();

	// ---- the runs, on the right -----------------------------------------
	rp = [x0 + pad * 2 + lw, yhead];
	rs = [w - lw - pad * 3, y0 + h - (rp_y + rec_sb_szhead + pad * 0.5) - pad * 2 - footh];

	/*
	  HOW MANY COLUMNS THE WINDOW CAN AFFORD, decided here and obeyed below.

	  The table is 83 characters wide at full dress (76 before build 68 added
	  the replay column).  On a narrow window that does not fit, and a column
	  that runs off the right edge is worse than one that is not drawn -- so the
	  two least load-bearing go first: the last column (the file's tag locally,
	  the demotion reason online), then the date/age.  Rank, time, delta, player
	  and the class word are what a leaderboard IS and are never dropped.

	  THE THREE BUDGETS ARE 83 / 72 / 51, AND THE FLOOR MOVED BY SEVEN.  That is
	  the one cost of the new column and it is worth stating rather than
	  discovering: the narrowest table this board can produce is now 51
	  characters where it was 44, so a window that could just fit the old floor
	  can overflow the new one.  No fourth step was added to drop the replay
	  column too, deliberately -- the mark surviving every width is the reason it
	  was put at SBX_REP in the first place, and 51 characters is roughly 370 px
	  at the shipped scale, which no window this game runs in is narrower than.
	  If one ever is, the honest fix is a fourth budget, not a narrower mark.

	  BUILD 64: BOTH SOURCES OBEY THIS ONE DECISION.  rec_sb_cols is read by
	  both row drawers, so a window narrow enough to drop a column drops the
	  same column on every tab.  A per-drawer copy of this arithmetic would
	  eventually let two tabs disagree about how wide the same table is.
	*/
	rec_sb_cols = SBX_END;
	if (Scores_ColX(rec_sb_cols) > rs_x - pad) rec_sb_cols = SBX_LINE;   // Patch 433
	if (Scores_ColX(rec_sb_cols) > rs_x - pad) rec_sb_cols = SBX_TAG;
	if (Scores_ColX(rec_sb_cols) > rs_x - pad) rec_sb_cols = SBX_DATE;

	Font_Set(ui_font_ui);
	Scores_Text([rp_x + Scores_ColX(SBX_RANK), rp_y], rec_sb_szhead, "#", SBC_DIM, 1);
	Scores_Text([rp_x + Scores_ColX(SBX_TIME), rp_y], rec_sb_szhead, "time", SBC_DIM, 1);
	Scores_Text([rp_x + Scores_ColX(SBX_DELTA), rp_y], rec_sb_szhead, "delta", SBC_DIM, 1);
	Scores_Text([rp_x + Scores_ColX(SBX_OWNER), rp_y], rec_sb_szhead, "player", SBC_DIM, 1);

	/*
	  THE LAST THREE HEADINGS ARE WHERE THE TWO SOURCES STOP AGREEING.

	  An online row has no `date`.  surfd stores a submission timestamp, but
	  this client has no clock it may trust against it -- so the column is an
	  AGE, computed from the reply's own `t` minus the row's own `when`, both
	  server-side.  Calling that "date" would be a heading that lies about its
	  units, and a player would read "3d" as a day of the month.
	*/
	/*
	  BUILD 68: `replay` IS AN ONLINE HEADING ONLY, AND THE LOCAL BOARD KEEPS
	  THE GAP RATHER THAN FILLING IT.

	  One column table serves both tabs, so the local board now has seven blank
	  characters between `player` and `date`.  Filling them (RT_LOBBY -> "none",
	  everything else -> "watch") would be the unification, and it is deliberately
	  NOT done here: every local row's recording is on this disk already, so the
	  column would answer a question nobody on that tab is asking, and the answer
	  would be "yes" on essentially every row.  A heading over a column that says
	  the same thing throughout is worse than a gap, which at least reads as
	  "this tab does not use this".  Same reasoning the line below already gives
	  for leaving the local tag column unlabelled.
	*/
	if (rec_sb_cols > SBX_REP)
	if (Scores_IsOnline())
		Scores_Text([rp_x + Scores_ColX(SBX_REP), rp_y], rec_sb_szhead,
		            "replay", SBC_DIM, 1);

	if (rec_sb_cols > SBX_DATE)
		Scores_Text([rp_x + Scores_ColX(SBX_DATE), rp_y], rec_sb_szhead,
		            Scores_IsOnline() ? "age" : "date", SBC_DIM, 1);
	if (rec_sb_cols > SBX_KIND)
		Scores_Text([rp_x + Scores_ColX(SBX_KIND), rp_y], rec_sb_szhead, "run", SBC_DIM, 1);
	// The local board has never labelled its last column and does not start
	// now: `latest` and `lobby` say what they are.  "no ruleset" does not.
	if (rec_sb_cols > SBX_TAG)
	if (Scores_IsOnline())
		Scores_Text([rp_x + Scores_ColX(SBX_TAG), rp_y], rec_sb_szhead, "why", SBC_DIM, 1);
	if (rec_sb_cols > SBX_LINE)
		Scores_Text([rp_x + Scores_ColX(SBX_LINE), rp_y], rec_sb_szhead, "line", SBC_DIM, 1);

	/*
	  The tick this map's server is actually running, which is what every LOCAL
	  time on screen is divided by.  Read once per frame rather than per row.

	  The online rows deliberately do NOT use it: each carries the rate it was
	  actually set at, which is the case surfd ranks by milliseconds to get
	  right.  Formatting a foreign run against this client's tickrate would
	  print a time that disagrees with the rank printed beside it.
	*/
	tick = Timer_Tick();
	pick = -1;

	if (Scores_IsOnline())
		pick = Scores_DrawOnlineRows(rp, rs, pad);
	else
		pick = Scores_DrawLocalRows(rp, rs, tick, pad);

	// ---- the footer ------------------------------------------------------
	Font_Set(ui_font_ui);
	if (Scores_IsOnline())
	{
		/*
		  ONLY WHEN THE ROWS IN MEMORY ARE THIS BOARD'S, and that test was
		  missing.  ob_n and ob_cnt_* survive a failed or in-flight fetch by
		  design (Online_Clear is not called on failure), so this footer
		  cheerfully printed the PREVIOUS leg's counts under the current leg's
		  heading -- next to a panel that was simultaneously saying "asking the
		  leaderboard...".  That is precisely the failure cl_online.qc's own
		  header calls "worth spending four string reads to make impossible",
		  written into the one place it was not checked.
		*/
		if (Online_Shows(rec_sb_legtrack[rec_sb_leg],
		                 rec_sb_legnum[rec_sb_leg],
		                 OB_TIER, Scores_StyleOf()))
		{
			s = sprintf("%g %s time(s) on %s", ob_n,
			            Scores_StyleOf(), Scores_LegName(rec_sb_leg));
			if (ob_cnt_ranked > ob_n)
				s = sprintf("%s  (top %g of %g shown)", s, ob_n, ob_cnt_ranked);
			if (ob_state == OBS_FETCH)
				s = strcat(s, "   refreshing...");
		}
		else
			s = sprintf("%s on %s", Scores_StyleOf(), Scores_LegName(rec_sb_leg));
	}
	else
	{
		s = sprintf("%g run(s) on %s", rec_sb_rown, Scores_LegName(rec_sb_leg));
		if (rec_sb_rowover > 0)
			s = sprintf("%s  (%g more than the %g this list holds)",
			            s, rec_sb_rowover, SB_MAXROW);
	}
	Scores_Text([x0 + pad, y0 + h - pad - footh], rec_sb_szrow, s, SBC_DIM, 1);

	/*
	  The hint says what a CLICK does, and on the online tabs a click does not
	  open anything -- so it names the keys instead of promising a replay that
	  is on somebody else's disk.

	  BUILD 86: "rmb pins" became "rmb for cursor", and the online string gained
	  the key.  Letting go of +showscores now closes the board on every tab, so
	  "esc to close" alone was understating it -- and the pin no longer outlives
	  the key, which means what mouse2 actually buys you is the cursor for the rest
	  of the hold.  A hint that names a behaviour the build removed is worse than
	  no hint.
	*/
	s = Scores_IsOnline()
	      ? "left/right change tab    up/down change leg    rmb for cursor    tab or esc to close"
	      : "click a run to watch it    tab or esc to close";
	Scores_TextR([x0 + w - pad, y0 + h - pad - footh], rec_sb_szrow,
	             s, SBC_DIM, 0.8);

	/*
	  ---- AND WHERE A RUN SET HERE GOES.  On EVERY tab, including Local.

	  Local is where the player's own times are, so it is exactly where "why is
	  this the only place they are" gets asked -- putting the sentence only on
	  the online tabs would hide it from the tab the question is asked on.

	  Below the counts rather than beside them because it is a different KIND of
	  fact: the line above describes the board being looked at, this one
	  describes the server being played on, and running them together reads as
	  one sentence about the board.
	*/
	s = Scores_BoardNote();
	if (s != "")
		Scores_Text([x0 + pad, y0 + h - pad - rec_sb_szrow], rec_sb_szrow,
		            s, Scores_BoardNoteCol(), 0.85);

	/*
	  PATCH 340: the room list, INSIDE this bracket and before its sui_end.

	  A second sui bracket in the same frame draws dead buttons -- sui_begin
	  empties the hit-test list and sui_end clears the input buffer, so the
	  LAST bracket owns every click (cl_main.qc's Ev_Panel comment).  Sharing
	  this one is what makes the mute buttons live.  It gets the rect this
	  function just computed because it anchors to it; cl_players.qc's header
	  has the rest.
	*/
	// Nested, never && around an index (QC evaluates both sides).
	pl_boardbusy = Scores_IsOnline();
	if (rec_sb_tab == SB_T_ONLINE)
	if (rec_sb_leg >= 0)
	if (rec_sb_leg < rec_sb_legn)
	if (rec_sb_legtrack[rec_sb_leg] == 0)
	if (rec_sb_legnum[rec_sb_leg] == 0)
		pl_boardbusy = FALSE;
	Players_Panel(p, sz, pad, scr);

	sui_end();
	Font_Reset();

	if (Scores_SpecHandOff())
		return;

	// Patch 433: a `line` box, on the frame boundary like the row picks below.
	if (rec_sb_lnpick)
	{
		Scores_LineToggle(rec_sb_lnpick - 1);
		rec_sb_lnpick = 0;
		return;
	}

	/*
	  THE HAND-OFF, AFTER sui_end AND AFTER THE LOOP.

	  Acting on the click inside the list would close the board and open a
	  recording in the middle of a virtualised draw -- with the scroll view's
	  clip area still pushed and sui's click-once actions not yet cleared, so the
	  next frame would see the same release again and re-open the same file.  A
	  pending index costs one float and lands the whole transition on a frame
	  boundary, which is what every other button in this file does implicitly by
	  being the last thing drawn.
	*/
	if (Scores_IsOnline())
	{
		Scores_OnlineHandOff(pick);
		return;
	}

	if (pick >= 0)
	{
		/*
		  BUILD 57, STAGE T -- A LOBBY ROW HAS NOTHING TO WATCH, AND IT SAYS SO.

		  The recorder is off in a lobby, so the file behind that row is a header
		  with `samples 0` and no movement at all.  Watch_Open would refuse it --
		  "holds 0 samples -- nothing to play" -- but it would refuse it AFTER
		  closing this board and claiming the cursor, which reads as the replay
		  having broken rather than as there being no replay.  Refused here, where
		  the reason is known, and the board stays up so the next click is
		  somewhere useful.
		*/
		if (rec_sb_rowtag[pick] == RT_LOBBY)
			print("^3scores:^7 that time was set on a lobby -- no replay\n");
		else
		{
			s = bufstr_get(rec_sb_bpath, pick);
			Scores_Close();
			Watch_Open(s);
		}
	}
};

/*
===========================================================================
  Opening, closing and input
===========================================================================
*/
void() Scores_Close =
{
	/*
	  CLOSING THE BOARD CANCELS A PENDING REPLAY, and this line is the whole
	  reason rec_sb_wantrep exists.  The download itself is not cancelled --
	  nothing in the engine can cancel one, and the bytes are worth having
	  cached anyway -- but a player who closed the board is not waiting, and a
	  replay that opened itself ten seconds later would be inexplicable.

	  Before the `rec_sb_open` test, deliberately: Scores_Close is called on
	  paths where the board is already shut and the intent must still go.
	*/
	rec_sb_wantrep = 0;
	rec_sb_wantleg = 0;
	rec_sb_olpick  = 0;
	sc_held = FALSE;          // PATCH 341: esc closes even mid-hold

	if (!rec_sb_open)
		return;
	rec_sb_open = FALSE;

	/*
	  The cursor goes back to the game ONLY if nothing else still wants it.

	  A replay can be underneath this board -- picking a second demo without
	  stopping the first is the ordinary way to use it -- and turning the cursor
	  off there would leave the playback chrome up with no way to press anything
	  on it.  One test, at the one place both features let go.

	  BUILD 47: AND THE EDITOR, which this had always missed.  hud_edit can be
	  opened over the board -- HUD_EditOpen refuses nothing -- and closing the
	  board from under it took the cursor away from a panel whose whole interface
	  is dragging.  cl_hudedit.qc has tested both of the others since it shipped;
	  this file tested one of two and cl_watch.qc tested none.  All three now ask
	  the same question, which is the property that was actually missing.

	  BUILD 55: "all three" was already FOUR when that was written -- the
	  results card takes the cursor too -- and this site could not test it,
	  because ui_rs_cursor is declared at cl_results.qc:58 and that file
	  compiles after this one.  So the card was missing from the list by
	  construction.  The question is now asked once, in cl_hud.qc's cursor
	  claim register, and no owner names another.
	*/
	UI_CursorRelease(UIC_SCORES);
};

void() Scores_Open =
{
	if (rec_sb_open)
		return;
	rec_sb_open = TRUE;
	// Re-read the folder every time it opens; a pin from the hold keeps the
	// player's place (-2, Patch 357).
	rec_sb_legbuilt = sc_held ? -2 : -1;
	UI_CursorClaim(UIC_SCORES);
};

void() Scores_Toggle =
{
	if (rec_sb_open)
		Scores_Close();
	else
		Scores_Open();
};

/*
  The board's input, and it takes priority over the replay chrome underneath.

  IE_MOUSEABS RETURNS TRUE UNCONDITIONALLY.  setcursormode(TRUE) makes the engine
  send absolute positions instead of deltas (in_generic.c:1324-1344), and it zeroes
  the accumulated delta ONLY when CSQC returns TRUE -- so a handler that forgets
  leaves the view turning under the cursor while you are trying to click a row.

  MOUSE1 and MOUSE2 ARE SWALLOWED because default.cfg binds them to +duck and
  +jump.  Returning TRUE here also keeps them out of Keys_Edge in cl_main.qc,
  which is the documented exception: the key display would otherwise light the
  duck box every time you clicked a run.
*/
float(float evtype, float scanx, float chary, float devid) Scores_InputEvent =
{
	/*
	  PATCH 341: THE PIN.  MOUSE2 while the held board is up toggles the pinned
	  state -- the one press that makes the scoreboard stay.  Swallowed, so the
	  pin click is not also a jump; every other mouse2 in the game is untouched,
	  because the gate is "the board is up because the key is down and not
	  because it was pinned", which is exactly the moment a click can only
	  have meant "keep this" or "let it go".
	*/
	if (evtype == IE_KEYDOWN && scanx == K_MOUSE2 && sc_held && !rec_sb_open)
	{
		Scores_Open();
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_MOUSE2 && sc_held && rec_sb_open)
	{
		Scores_Close();
		/*
		  BUILD 86: BACK TO THE PEEK, NOT TO NOTHING.  Scores_Close clears sc_held
		  as well -- it has to, because esc closes mid-hold -- but the key is still
		  down on this path, and now that letting go of it is what closes the board
		  (see Scores_ConsoleCommand) the two would otherwise disagree: unpinning
		  would end a gesture the player is still making.  The pin owns the cursor;
		  the key owns the board.
		*/
		sc_held = TRUE;
		return TRUE;
	}

	if (!rec_sb_open && !sc_held)
		return FALSE;

	if (evtype == IE_MOUSEABS)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}

	if (evtype == IE_KEYDOWN || evtype == IE_KEYUP)
	{
		if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
		{
			sui_input_event(evtype, scanx, chary, devid);
			return TRUE;
		}

		if (evtype == IE_KEYDOWN)
		{
			// keys.c:3205 -- "csqc is allowed to steal the escape key (unless
			// shift)" -- and the board is open with key_dest still kdm_game, so
			// the test there passes and the menu never opens behind it.
			if (scanx == K_ESCAPE)
			{
				Scores_Close();
				return TRUE;
			}
			if (scanx == K_UPARROW)
			{
				if (rec_sb_leg > 0)
					rec_sb_leg = rec_sb_leg - 1;
				return TRUE;
			}
			if (scanx == K_DOWNARROW)
			{
				if (rec_sb_leg < rec_sb_legn - 1)
					rec_sb_leg = rec_sb_leg + 1;
				return TRUE;
			}

			/*
			  BUILD 64: LEFT AND RIGHT CHANGE THE TAB, because up and down
			  already change the leg and a board with three tabs and no
			  keyboard route to them is one the mouse has to be borrowed for.

			  They DO NOT WRAP.  A wrapping strip means pressing right twice
			  from `local` lands on `segmented`, and a tab strip is a spatial
			  thing -- the row does not loop on screen and it should not loop
			  under the keys either.  Clamped, so holding a key settles at an
			  end rather than cycling.
			*/
			if (scanx == K_LEFTARROW)
			{
				if (rec_sb_tab > SB_T_ONLINE)
					rec_sb_tab = rec_sb_tab - 1;
				rec_sb_tabauto = FALSE;
				return TRUE;
			}
			if (scanx == K_RIGHTARROW)
			{
				if (rec_sb_tab < SB_T_LOCAL)
					rec_sb_tab = rec_sb_tab + 1;
				rec_sb_tabauto = FALSE;
				return TRUE;
			}
		}
		return FALSE;
	}

	return FALSE;
};

/*
  +showscores, from the engine's own TAB handler.

  It arrives through Sbar_ShowTeamScores (sbar.c:788) rather than through
  Sbar_ShowScores, because scr_scoreboard_teamscores defaults to 1 and that
  function hands off before reaching its own CSQC hook.  Either way the string
  passed is Cmd_Argv(0), so CSQC sees the literal bind.

  PATCH 341: HOLD, NOT TOGGLE.  `+showscores` arms sc_held for as long as the
  key is down and `-showscores` drops it; the board draws while either it or
  the pinned rec_sb_open is true.  The TOGGLE is MOUSE2 while the held board
  is up (Scores_InputEvent, below) -- a board you can hold to peek and click
  to keep, instead of one that flips state on every TAB press.

  `-showscores` is still CONSUMED rather than left alone, so that the engine's
  own scoreboard state does not flicker underneath -- VF_DRAWENGINESBAR 0 already
  keeps it off screen, but leaving a handler out because something else happens
  to hide the result is how a feature breaks when that something else changes.

  BUILD 86: THE RELEASE CLOSES THE PIN TOO.

      "When you release +showscores the scoreboard should close even when you
       toggle it on with mouse2."

  Patch 341 cleared only sc_held here, so a board that had been pinned stayed up
  after the key came back -- and the pin is far easier to set than it looks:
  default.cfg binds MOUSE2 to +jump, so jumping once while peeking at the board
  pinned it, and the board was then stuck open with the cursor captured and no
  obvious way back.  The key is the gesture; letting go of it ends the gesture.

  Scores_Close() RATHER THAN TWO ASSIGNMENTS, because closing is more than two
  flags: it releases the cursor claim (UIC_SCORES) and drops a pending replay.
  Clearing the flags by hand here would have left the cursor with this panel
  after its board was gone, which is the one failure that makes the game
  unplayable rather than merely untidy.
*/
float(string cmd) Scores_ConsoleCommand =
{
	if (argv(0) == "+showscores")
	{
		sc_held = TRUE;
		return TRUE;
	}
	if (argv(0) == "-showscores")
	{
		Scores_Close();
		return TRUE;
	}

	// A console handle, for the same reason `replay status` exists: a board that
	// can only be reached by a keypress is one no config can ever check.
	if (argv(0) == "scores")
	{
		if (argv(1) == "close")
			Scores_Close();
		else if (argv(1) == "open")
			Scores_Open();
		else if (argv(1) == "pick")
		{
			// Patch 385: a room-list row click, minus the hit test -- the next
			// Scores_Draw hands it off (Scores_SpecHandOff).  Pinned board only.
			local float sp_s;
			sp_s = Spec_FindName(argv(2));
			if (!rec_sb_open || sp_s < 0)
				print("scores pick <name>: pin the board, name one player\n");
			else
				pl_specpick = sp_s + 1;
		}
		// Patch 395: an online-list row click (0-based), taken by the next draw.
		// Patch 433: `line <row>` (0-based, this tab) toggles its line; `lines`
		// prints them, `lines clear` drops them all.
		else if (argv(1) == "line")
		{
			Scores_Refresh();
			Scores_LineToggle(stof(argv(2)));
			return TRUE;
		}
		else if (argv(1) == "lines")
		{
			if (argv(2) == "clear")
			{
				local float li;
				for (li = 0; li < SB_LNMAX; li = li + 1)
					if (sb_ln_st[li] != SBL_FREE)
						Scores_LineFree(li);
			}
			Scores_LinesStatus();
			return TRUE;
		}
		else if (argv(1) == "olpick")
		{
			rec_sb_olpick = stof(argv(2)) + 1;
			return TRUE;
		}
		else if (argv(1) == "leg")
		{
			Scores_Refresh();
			rec_sb_leg = stof(argv(2));
			if (rec_sb_leg < 0) rec_sb_leg = 0;
			if (rec_sb_leg >= rec_sb_legn) rec_sb_leg = rec_sb_legn - 1;
		}
		else if (argv(1) == "filter")
		{
			if (argv(2) == "clean")         rec_sb_filter = SB_F_CLEAN;
			else if (argv(2) == "stitched") rec_sb_filter = SB_F_STITCHED;
			// Build 44.  `segmented` as well, because that is the word the row
			// now shows and a console handle nobody can guess is not one.
			else if (argv(2) == "segmented") rec_sb_filter = SB_F_STITCHED;
			else if (argv(2) == "cheated")  rec_sb_filter = SB_F_CHEATED;
			else                            rec_sb_filter = SB_F_ALL;
		}
		/*
		  BUILD 64.  THE TAB, THE TIER AND A FORCED REFETCH, from the console.

		  These are the whole headless surface for stage 2, and they exist for
		  the reason `replay status` and `board_status` both do: a config can
		  neither click a chip nor read a pixel, so a feature reachable only by
		  the mouse is one no arm can check.  Every one of them lands in the
		  same state the chip would set, and the `Scores_Refresh()` below then
		  drives the fetch exactly as a drawn frame would.

		  AN UNKNOWN WORD FALLS BACK TO THE DEFAULT rather than being refused,
		  which matches `scores filter` one block up.  `scores tab` on its own
		  is therefore "go back to the default board", which is a useful thing
		  to be able to type and is what the fall-through already means.
		*/
		else if (argv(1) == "tab")
		{
			if (argv(2) == "segmented")  rec_sb_tab = SB_T_SEGMENT;
			else if (argv(2) == "local") rec_sb_tab = SB_T_LOCAL;
			else                         rec_sb_tab = SB_T_ONLINE;
			rec_sb_tabauto = FALSE;
		}
		// Patch 357 test hooks: a certified finish cannot be scripted (noclip needs
		// sv_cheats, which breaks the ruleset), so these stand in for
		// Results_BoardWatch's two calls.  `note <track> <leg> <ticks> <flags>`,
		// `landed` (rank and prevms taken from this player's *wrank).
		else if (argv(1) == "note")
		{
			Scores_NoteFinish(stof(argv(2)), stof(argv(3)), stof(argv(4)),
			                  stof(argv(5)), TRUE);
			return TRUE;        // not the shared tail: it would Refresh (fetch)
		}
		else if (argv(1) == "landed")
		{
			// Mirrors Results_BoardWatch: stored -> this run's time, else prevms.
			tokenize(getplayerkeyvalue(player_localnum, "*wrank"));
			if (stof(argv(7)) == 1)
				Scores_NoteAnswer(TRUE, stof(argv(5)),
				                  rint(rec_sb_finticks * Timer_Tick() * 1000));
			else
				Scores_NoteAnswer(TRUE, stof(argv(5)), stof(argv(8)));
			return TRUE;
		}
		// Kept handled: an unknown word falls through to Scores_Toggle, and old
		// fixtures still type this.
		else if (argv(1) == "tier")
			print("scores: the board shows ranked times only (Patch 355)\n");
		else if (argv(1) == "refresh")
		{
			/*
			  The refresh chip's twin, and it calls Online_Fetch DIRECTLY --
			  Online_Need would decline, because the whole point of its guard
			  is that a board already asked for is not asked for again.  This
			  is the one path that is allowed past it, on both the chip and
			  the console, and there is no third.
			*/
			Scores_Refresh();
			if (rec_sb_leg >= 0 && rec_sb_leg < rec_sb_legn)
				Online_Fetch(rec_sb_legtrack[rec_sb_leg], rec_sb_legnum[rec_sb_leg],
				             OB_TIER, Scores_StyleOf());
		}
		// `scores` on its own toggles the board, which makes it useless for
		// asking what the board holds.  This asks without touching anything.
		else if (argv(1) == "status")
		{
			Scores_Refresh();
			Scores_Status();
			return TRUE;
		}
		else if (argv(1) == "legs")
		{
			/*
			  THE WHOLE DERIVED TABLE, and it earns its own subcommand.

			  The leg count is the one number on this board that comes from
			  arithmetic over the zone tables rather than from a file, so "10
			  legs" is exactly the kind of answer that can be plausibly wrong --
			  an off-by-one in `max(zone_seg) + 1` invents a leg nobody can run,
			  and it would look identical to a real one until you clicked it.
			  zone_dests prints only the zones with a teleport destination, so it
			  cannot be read against this without doing the arithmetic by hand.
			*/
			local float i;
			Scores_Refresh();
			print(sprintf("scores: %g leg(s) derived from %g zone(s) on %s\n",
			              rec_sb_legn, zone_count, serverkey("map")));
			for (i = 0; i < rec_sb_legn; i = i + 1)
				print(sprintf("  %2g  track %g leg %g  \"%s\"  %s\n",
				              i + 1, rec_sb_legtrack[i], rec_sb_legnum[i],
				              Scores_LegName(i),
				              FS_RunDir(serverkey("map"), rec_sb_legtrack[i],
				                        rec_sb_legnum[i])));
			return TRUE;
		}
		else if (argv(1) == "watch")
		{
			Scores_Refresh();
			if (stof(argv(2)) >= 1)
			if (stof(argv(2)) <= rec_sb_rown)
			{
				// Build 57, stage T: the same refusal the click gets, because a
				// console handle that opened a file the mouse will not is a handle
				// that cannot be used to check the mouse.
				if (rec_sb_rowtag[stof(argv(2)) - 1] == RT_LOBBY)
					print("^3scores:^7 that time was set on a lobby -- no replay\n");
				else
				{
					Scores_Close();
					Watch_Open(bufstr_get(rec_sb_bpath, stof(argv(2)) - 1));
				}
			}
			return TRUE;
		}
		else
			Scores_Toggle();

		Scores_Refresh();
		Scores_Status();
		return TRUE;
	}

	return FALSE;
};

/*
  Everything the board is showing, said out loud.

  The same instrument `replay status` is and for the same reason: a scripted
  config cannot click a row or read a pixel, so without this the leg derivation,
  the name sort, the header reads and the clean/stitched rule would all be
  verifiable only by looking at them.  Every number here is the one the list is
  drawn from rather than a recomputation.
*/
void() Scores_Status =
{
	local float i, cl, shown;
	local string s;

	/*
	  BUILD 64 SPLIT THIS INTO TWO LINES, and the reason is the eight-parameter
	  ceiling rather than taste: `filter` was the seventh argument of a call
	  that now has a tab and a tier to report as well, and a ninth would be
	  dropped by the calling convention rather than refused by the compiler.
	  A status line silently missing its last field is precisely the defect
	  this function exists to prevent elsewhere.
	*/
	/*
	  BUILD 86: THE HOLD IS REPORTED TOO.  rec_sb_open alone stopped describing the
	  board when patch 341 made it a hold with a pin -- a board that is up because
	  the key is down reads "closed" here, which is the one thing a status line must
	  not do.  Three states, named: pinned (rec_sb_open), held (sc_held only), or
	  closed.  Without this the release fix has no headless witness at all.
	*/
	print(sprintf("scores: %s on %s  leg %g/%g \"%s\"\n",
	              rec_sb_open ? (sc_held ? "pinned+held" : "pinned")
	                          : (sc_held ? "held" : "closed"),
	              (rec_sb_legmap != "") ? rec_sb_legmap : "-",
	              rec_sb_leg + 1, rec_sb_legn, Scores_LegName(rec_sb_leg)));

	/*
	  `cols` is the LAST DRAWN FRAME's column budget, and it is reported because
	  it is otherwise checkable only by eye.

	  The drop rule (SBX_END -> SBX_TAG -> SBX_DATE) is arithmetic over the
	  panel width, and both row drawers obey the same global -- but a config
	  cannot read a pixel, and the first attempt to test it set vid_conwidth,
	  which is the MENU's virtual screen and does not reach CSQC at all.  The
	  board looked identical and the arm looked passed.  A number that says
	  which budget was actually chosen cannot be misread that way.

	  It is 0 until the board has been drawn once, which is honest: nothing has
	  decided a width yet.
	*/
	print(sprintf("  tab %s   filter %s   cols %g\n",
	              (rec_sb_tab == SB_T_LOCAL) ? "local"
	                : ((rec_sb_tab == SB_T_SEGMENT) ? "segmented" : "online"),
	              (rec_sb_filter == SB_F_CLEAN) ? "clean"
	              : ((rec_sb_filter == SB_F_STITCHED) ? "stitched"
	              : ((rec_sb_filter == SB_F_CHEATED) ? "cheated" : "all")),
	              rec_sb_cols));

	/*
	  THE SERVER'S ANSWER VERBATIM, then this file's reading of it.

	  Both, because they are two different failures.  An empty `board=` means
	  the server never published -- an older progs, or Lobby_BoardState not
	  reached -- and is a SERVER problem.  A `board=local` with no sentence
	  beside it would mean Scores_BoardNote does not recognise a word the server
	  does send, which is a CLIENT problem, and printing only the sentence would
	  make the two look identical from here.
	*/
	s = serverkey("board");
	print(sprintf("  board=%s  %s\n", (s != "") ? s : "(unpublished)",
	              (Scores_BoardNote() != "") ? Scores_BoardNote()
	                                         : "-- no note drawn"));

	// Witnesses: does the online store describe the leg on screen, and how many
	// best times has the room list absorbed from it.
	shown = 0;
	if (rec_sb_leg >= 0 && rec_sb_leg < rec_sb_legn)
		shown = Online_Shows(rec_sb_legtrack[rec_sb_leg], rec_sb_legnum[rec_sb_leg],
		                     OB_TIER, Scores_StyleOf());
	print(sprintf("  shows %g   room list: %g best time(s)\n", shown, pl_bn));
	print(sprintf("  follow %g leg %g/%g ticks %g  seek %g wait %g  rank %g\n",
	              rec_sb_finpend, rec_sb_fintrack, rec_sb_finleg, rec_sb_finticks,
	              rec_sb_seek, rec_sb_finwait, rec_sb_finrank));

	/*
	  BUILD 44: HOW MANY ROWS THE FILTER ACTUALLY KEEPS.

	  Scores_Passes is consulted nowhere but the DRAW, so until this line the only
	  way to check a filter was a screenshot -- and a screenshot in this engine
	  lands one step behind the command that set it up, which has cost this project
	  three builds once already.  Now `all` against the sum of the other three is
	  an arithmetic check any config can make, and it is the invariant the four
	  chips are built on: every row shows under exactly one of clean / stitched /
	  cheated, and an unknown row shows under all three.

	  Counted over every row, not over the twenty printed below: the cap is a
	  courtesy to the log and must not change the number.
	*/
	shown = 0;
	for (i = 0; i < rec_sb_rown; i = i + 1)
		if (Scores_Passes(i))
			shown = shown + 1;

	/*
	  Timer_Tick() AND NOT PM_TICK, IN BOTH PLACES BELOW.  Found by build 64's
	  tab arm, on a screenshot taken beside the log it was meant to confirm.

	  PM_TICK is the COMPILE-TIME default, 0.015 -- and bhop maps run at 0.01
	  (mode_bhop.cfg sets cl_netfps 100 to match).  So on every bhop map in the
	  library this function has printed times 50% LONG since build 24, while
	  the board two functions up drew them correctly from Timer_Tick(): one
	  4976-tick PB read `0:49.760` on screen and `1:14.640` in the log.

	  That is the worst possible place for the error.  This report exists so a
	  scripted arm can check a board it cannot see, and a report that disagrees
	  with the thing it reports is worse than no report at all -- an arm would
	  either chase a phantom or, far likelier, enshrine the wrong number as the
	  expected one.  cl_hud.qc:2595 records fixing this exact substitution once
	  before; these two were the last of it in the client.
	*/
	print(sprintf("  legs: %g   rows: %g (%g pass the filter)   best %s\n",
	              rec_sb_legn, rec_sb_rown, shown,
	              rec_sb_best > 0 ? Time_TickString(rec_sb_best, Timer_Tick()) : "-"));

	// Bounded: a status line is for reading, and twenty rows is already more
	// than anyone scrolls past in a log.  EVERY row is listed whatever the filter
	// says, and the `*` is which ones it keeps -- a status dump that hid rows
	// would be unable to answer "why is my run not on the board", which is the
	// question it is most often reached for.
	for (i = 0; i < rec_sb_rown && i < 20; i = i + 1)
	{
		cl = Scores_Clean(i);
		// Build 44: the same word the row draws, from the same function, so a
		// log and a screenshot of the board cannot disagree about one file.
		s  = (cl == RC_UNKNOWN) ? "unknown" : FS_RunClassName(cl);
		print(sprintf("  %s%2g %s  rec%g %-9s  %s\n",
		              Scores_Passes(i) ? "*" : " ",
		              i + 1, Time_TickString(rec_sb_rowticks[i], Timer_Tick()),
		              rec_sb_rowver[i], s, bufstr_get(rec_sb_bpath, i)));
	}
	if (rec_sb_rown > 20)
		print(sprintf("  ... and %g more\n", rec_sb_rown - 20));

	/*
	  AND THE ONLINE BOARD, WHEN AN ONLINE TAB IS THE ONE ON SCREEN.

	  Online_Status and NOT a second copy of it.  The rows, the Hz-to-seconds
	  conversion and the demotion reason are all printed there already, and two
	  reports of one board that could disagree by a digit is worse than one
	  report -- the units bug b64board.cfg caught would have been invisible if
	  the tab had printed its own idea of the time.

	  EVERYTHING ABOVE THIS LINE IS THE LOCAL LIST, on every tab.  It is built
	  regardless (see Scores_Refresh), so a run of this command answers "what
	  is on my disk" and "what is on the board" in one go, which is the
	  comparison an arm actually wants to make.
	*/
	if (Scores_IsOnline())
		Online_Status();
};

void() Scores_RegisterCvars =
{
	/*
	  `scores` is free and was CHECKED rather than assumed: registercommand
	  SILENTLY no-ops on a name the engine already owns (pr_csqc.c:5497), so an
	  unchecked name is a command that does nothing with no error anywhere.

	  +showscores and -showscores are NOT registered.  They are engine commands
	  that offer themselves to CSQC on their own (sbar.c:788, :810); registering
	  them would be the silent no-op above, and believing it had worked would be
	  worse than not trying.
	*/
	registercommand("scores");

	rec_sb_legbuilt = -1;
	rec_sb_legzoned = FALSE;
	rec_sb_bpath = rec_sb_bowner = rec_sb_bdate = 0;

	/*
	  BUILD 64: THE DEFAULT TAB, SET RATHER THAN INHERITED FROM ZERO.

	  SB_T_ONLINE is 0, so a QC global would already hold it -- and that is
	  exactly why this is written out.  "The online
	  board is the default" is the request, not an accident of which constant
	  was listed first, and reordering the three #defines would silently open
	  the board on Local with nothing anywhere saying it had changed.
	*/
	rec_sb_tab  = SB_T_ONLINE;
};
