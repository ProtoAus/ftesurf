/*
===========================================================================
  cl_results.qc -- the end-of-run card, and the per-stage toast.  Build 48.

  TWO PANELS AND ONE FILE, because they are the same question asked at two
  scales and they must never both be on screen:

    the CARD    you finished a LEG.  The map, a bonus, or a stage you chose
                with `!s N`.  Time, class, rank, and the whole split table.
    the TOAST   you passed a stage while a full run is still going.  One line,
                fades, no input.  This is deliberately NOT the card: crossing
                stage 3 of 9 is not finishing anything, and a results screen
                there would be six results screens a run.

  The partition is a fact about the SERVER's control flow, not a guess up here.
  Only SV_TimerFinish sets TS_FINISHED, and a stage boundary during a full
  track run goes through SV_TimerSplit, which does not touch the state at all.
  A deliberate stage run (run_t_stagerun) reaches SV_TimerFinish at the NEXT
  boundary -- so "big card for a leg you chose, toast for a stage you flew
  through" already is the shape of the code, and this file only has to not
  fight it.

  BUILD 57: LEGS ARE 1-BASED STAGES NOW, AND SEGMENTS ARE NOT.  RUNLEG decodes to
  a LEG -- 0 the full run, k stage k -- so a stage-1 run (`!s 1`) gets the card
  like any other stage, and the toast for a stage you flew through is named and
  ranked as seg + 1, because STAT_FS_STAGEENDSEG is still a segment.

  NOTHING HERE OWNS RUN STATE.  Everything drawn comes from stats the server
  already publishes and from ui_sp_* in cl_timer.qc, which has held the split
  table since build 19 for the column down the left.  That is the same argument
  cl_timer.qc's own header makes about not inventing a network message for a
  table the client already has, and it is why this file adds no protocol.

  THE ONE THING IT READS FROM DISK is the rank, and it reads FILENAMES ONLY --
  no fopen, no header parse.  See Results_Rank.

  IT NEVER TAKES THE SCREEN.  The card appears unasked while you are standing
  in a map you may be about to run again, so it draws without entering the
  input chain at all and asks for the cursor only when told to.  A panel that
  grabbed the mouse on every finish would cost a run the first time you crossed
  the line with your hand already moving.
===========================================================================
*/

#define RS_ROWS   10            // table rows drawn; the tail, newest last

// Palette: the leaderboard's, deliberately.  This panel sits beside that one in
// the player's head and a second palette would make them look like two games.
#define RSC_PANEL  '0.07 0.08 0.11'
#define RSC_LINE   '0.30 0.55 0.85'
#define RSC_TEXT   '0.88 0.90 0.94'
#define RSC_DIM    '0.55 0.60 0.68'
#define RSC_GOOD   '0.45 0.90 0.50'
#define RSC_BAD    '0.95 0.45 0.40'

// Promised here, defined at the bottom beside the rest of the lifecycle:
// Results_Frame watches for a map change and both sit above their definition,
// the same arrangement Scores_Close and Scores_Status have in cl_scores.qc.
void() Results_MapInit;

/*
  BUILD 57, STAGE T: the fastest lobby time already on a leg, in ticks.

  Defined in client/cl_lobbytime.qc, which compiles AFTER this file -- the same
  arrangement sv_zones.qc has with the timer's SV_TimerChatLeg, and for the same
  reason: that file needs Results_LegName from here, so one of the two directions
  has to be a declaration.  This is the cheaper one, because it is ONE function.

  The card needs it because the server ZEROES the personal best in a lobby:
  SV_PBGet refuses to read the host's table (Lobby_NoPB), so STAT_FS_TIMERPBWAS
  arrives as 0 and the delta the card exists to draw would never appear.  The
  lobby files on this disk are the only record of what the run was measured
  against.

  `mine` is "ignore a file stamped with this time", which is what keeps a card
  REOPENED with `results` from comparing the run against the file it just wrote.
*/
float(string map, float track, float leg, float mine) LT_BestOnLeg;

string ui_rs_map;               // the map the state below describes
float  ui_rs_open;              // the card is up
float  ui_rs_cursor;            // ...and it has asked for the mouse
float  ui_rs_at;                // cltime it appeared; 0 = not shown

// What the card is about, latched at the finish so the re-arm cannot move it
// under the player while they are reading it.
float  ui_rs_ticks;
float  ui_rs_flags;
float  ui_rs_pb;                // the pb this run was measured AGAINST
float  ui_rs_tag;               // RT_*
float  ui_rs_track;
/*
  BUILD 57: TWO NUMBERS WHERE THERE WAS ONE.  ui_rs_leg is what the card is
  about -- 0 the full run, k stage k -- and it is what the rank and the label
  read.  ui_rs_startseg is kept as the SEGMENT that leg began at (leg - 1, or 0
  for a full run), because cl_main.qc's `timer` verification print reads it by
  name and a stage-1 run and a full run now share the value 0 there.
*/
float  ui_rs_leg;
float  ui_rs_startseg;
float  ui_rs_rank;              // 0 = unknown / no archive
float  ui_rs_of;

// The finish edge.  Two of them OR'd -- see Results_Frame.
float  ui_rs_laststate;
float  ui_rs_lasttag;

/*
  BUILD 57, STAGE T: THE THIRD FINISH EDGE, and in a lobby it is the only one
  that ever fires.

  Neither of the two above can work there.  RUNTAG is published by SV_RecClose,
  which a lobby never reaches -- the recorder is off, so there is no buffer to
  close -- and TS_FINISHED can be skipped outright, because run_t_pendarm re-arms
  a chained stage run inside the same server frame and the engine deltas a stat
  against the last value it SENT.  STAT_FS_FINREC is a counter bumped by every
  SV_TimerFinish for exactly that reason; -1 seeds it, as the toast's latch does.
*/
float  ui_rs_lastfinrec;

/*
  BUILD 51: THIS WAS CALLED ui_rs_armed AND THAT NAME WAS ALREADY TAKEN.

  cl_board.qc:813 declares `float ui_rs_armed` for something completely
  unrelated -- build 26's "a save-lock restore's teleport has not landed yet"
  exemption.  Two files, two meanings, one name, and QuakeC has no file scope:
  fteqcc merges same-named same-typed globals into ONE, which is the very
  mechanism this project relies on for forward declarations (cl_hud.qc:540
  declares HUD_ClearEnergyHistory before defining it).  So build 48 did not
  add a second variable here.  It aliased an existing one, silently, with no
  warning -- all three progs still compiled clean.

  BOTH HALVES BROKE, in opposite directions, because the write sites interleave
  inside one frame.  cl_main.qc runs HUD_Draw (and Board_Frame inside it) at
  :768, then Results_Frame at :813:

    Results_Frame -> Board.  :375 sets it TRUE on EVERY frame of TS_RUNNING, so
      cl_hud.qc:1028 `if (!ui_rs_armed)` and cl_board.qc:2001 read FALSE for the
      whole of every run.  Build 26's teleport re-base guard and build 47's
      start-box re-base were dead from build 48 onwards -- not just after a
      save-lock load, but always, on every map.  That is the reported
      "loading a save-lock corrupts the energy readout": the anchor can no
      longer follow you, so `e` is measured from a reference that is wherever
      the run happened to start.

    Board -> Results_Frame.  cl_board.qc:2229-2231 clears it whenever the
      restore has landed OR the deadline has passed, and ui_rs_deadline is
      written ONLY by Seq_AnchorRestore (cl_board.qc:926).  Until the first
      save-lock load of a map it is 0, so `cltime >= ui_rs_deadline` is true and
      Board_Frame cleared this flag EVERY frame.  Board_Frame runs first; on the
      finish frame state is no longer TS_RUNNING so :375 cannot re-arm it, and
      the gate below reads FALSE.  Results_Open was therefore never reached from
      the finish edge and the build-48 results card has never once appeared by
      itself -- only via the `results` console command.  Which is exactly why
      build 48's own verification list still has "the results card on a map"
      outstanding: the feature was never seen because it could not fire.

  Renamed rather than re-scoped because there is nowhere to scope it to.
*/
float  ui_rs_seen;              // a run has been seen RUNNING since the last card

// The toast.  ui_rs_lastendrec is the EDGE; ui_rs_toastseg is the stage the
// toast on screen is about.  Two different things -- the stat moves on to the
// next stage while the toast is still fading, so what is drawn has to be
// latched rather than re-read.
//
// BUILD 57: ui_rs_toastseg holds the STAGE -- the leg, segment + 1 -- whatever its
// name says.  It keeps the name because cl_main.qc's `timer` verification print
// reads it, and that file is not this build's to edit.

float  ui_rs_lastendrec;        // last STAT_FS_STAGEENDREC seen; -1 = seeding
float  ui_rs_toastat;           // cltime it landed; 0 = none
float  ui_rs_toastseg;
float  ui_rs_toastticks;
float  ui_rs_toastword;
float  ui_rs_toastrank;
float  ui_rs_toastof;

void() Results_RegisterCvars =
{
	/*
	  0 IS BUILD 47 EXACTLY: no card, ever.

	  The LATCH still runs at 0, and that is not an oversight.  A detector that
	  can be switched off is one that comes back seeded from whenever it was
	  switched on -- so turning this to 1 mid-session would pop a card about a
	  run that finished four minutes ago.  The cvar decides whether it DRAWS.
	*/
	registercvar("hud_results", "1", CVAR_ARCHIVE);

	registercvar("hud_results_x", "0.72", CVAR_ARCHIVE);
	registercvar("hud_results_y", "0.50", CVAR_ARCHIVE);

	/*
	  THE RANK SCAN, AND THIS IS THE HONESTY SWITCH AND THE PERFORMANCE A/B IN
	  ONE.

	  0 draws `--` in both rank rows and touches the disk not at all.  One
	  search_begin walks every mounted searchpath, and every package handler
	  answers it with a linear compare over its whole file table -- which on a
	  full install is a large number nobody in this project has measured.  Until
	  somebody does (gettime is #519 and is called nowhere yet), this is the
	  switch that says "the card is lying to me OR the card is costing me
	  frames" and separates the two in one map load.
	*/
	registercvar("hud_results_rank", "1", CVAR_ARCHIVE);

	// The toast.  0 is build 47: a stage boundary says nothing but the split
	// column and the flash under the clock, which is what it said before.
	registercvar("hud_results_toast", "1", CVAR_ARCHIVE);
	registercvar("hud_results_toast_time", "3.5", CVAR_ARCHIVE);

	/*
	  `results` reopens the last card -- the only way back to it once dismissed,
	  and the only way to see one at all with hud_results 0.

	  CHECKED, NOT ASSUMED, which is this project's rule for a reason it has
	  already paid for twice: PF_cs_registercommand is `if (!Cmd_Exists(...))`
	  and returns nothing, so claiming a name somebody else owns is a SILENT
	  no-op and the command simply never arrives.  Grepped the engine tree: the
	  only occurrence of the string is a directory name inside the bundled
	  FreeType test tool, which is not built into the command table.  Free.
	*/
	registercommand("results");
};

/*
  "How many archived CLEAN runs on this leg are faster than `ticks`?"

  FILENAMES ONLY.  FS_RunPath stamps an archived run's tick count into its name,
  zero-padded to seven digits, precisely so an ascending name sort is an
  ascending time sort -- cl_scores.qc's header calls that the leaderboard and
  builds its whole row list on it.  So a rank is a count of names, and this
  function opens nothing.  That matters because the TOAST calls it at a stage
  boundary, mid-run, and on a listen server a stall inside CSQC_UpdateView
  delays the next SV_Frame -- i.e. it stalls the mover, in the air, on the tick
  a boundary is being crossed.  Nine fgets a row, which is what the leaderboard
  pays to show an owner, is not affordable there.

  ONLY RT_PB AND RT_RUN COUNT.  Both are clean by construction: a personal best
  refuses a tainted run outright, and RT_RUN is only reached by a run that was
  neither practice, segmented nor cheated.  RT_SHADOW is stamped too and is
  deliberately excluded -- it is a practice attempt off a save state, and
  ranking against it would put a save-loaded time in a field of earned ones.
  The unstamped tags (last, cheat) carry no time in the name and cannot be
  ranked even in principle.

  BUILD 57, STAGE T: AND RT_LOBBY, which is clean by the same construction.  Its
  writer refuses a practice or shadow finish and files a stage only on the
  server's own SF_QUALIFIES, so a lobby file on a leg is an earned time -- and in
  a lobby it is the ONLY file there is, because the server keeps nothing.  Left
  out, the card's rank row would read "no local archive yet" on every lobby
  finish, on a leg whose whole archive this build just wrote.

  STRICTLY FASTER, so the run just written cannot outrank itself if it is
  already on disk, and cannot be missed if it is not.  The `of` count is the
  softer number and it does wobble by one depending on whether the server has
  flushed yet -- which is why the card says "of N" and never "you beat N-1
  people".

  Returns the rank in `rank` and the field size in `of`.  rank 0 means "no
  archive to rank against", which is a different sentence from rank 1 and the
  card draws it differently.
*/
void(float track, float leg, float ticks,
     __inout float rank, __inout float of) Results_Rank =
{
	local float h, n, i, cut, dot, us, t, faster, total;
	local string fn, base, tagw;

	rank = 0;
	of   = 0;

	if (!cvar("hud_results_rank"))
		return;

	// BUILD 57: a LEG (0 the full run, k stage k), which is what FS_RunDir takes.
	h = search_begin(strcat(FS_RunDir(serverkey("map"), track, leg), "*.rec"),
	                 FS_NAMESORT, TRUE);
	if (h < 0)
		return;                 // no such directory: the first run on this leg

	n = search_getsize(h);
	faster = 0;
	total  = 0;

	for (i = 0; i < n; i = i + 1)
	{
		fn = search_getfilename(h, i);

		cut  = Scores_LastOf(fn, 47);           // '/'
		base = (cut >= 0) ? substring(fn, cut + 1, strlen(fn) - cut - 1) : fn;

		dot = strlen(base) - 4;                 // ".rec"
		if (dot < 1)
			continue;
		base = substring(base, 0, dot);

		us = Scores_LastOf(base, 95);           // '_'
		if (us < 0)
			continue;                           // unstamped: last, cheat

		tagw = substring(base, us + 1, strlen(base) - us - 1);
		if (FS_TagFromName(tagw) != RT_PB)
		if (FS_TagFromName(tagw) != RT_RUN)
		if (FS_TagFromName(tagw) != RT_LOBBY)   // build 57, stage T
			continue;

		t = stof(substring(base, 0, us));
		if (t <= 0)
			continue;

		total = total + 1;
		if (t < ticks)
			faster = faster + 1;
	}
	search_end(h);

	/*
	  BUILD 57, STAGE T: AN EMPTY FOLDER IS RANK 1 OF 1 IN A LOBBY, not "no
	  archive".  cl_main.qc runs Results_Frame before LT_Frame -- deliberately,
	  so the card can read what the run was measured against before this run's
	  file joins it -- so on the FIRST lobby time for a leg this scan runs one
	  call before the file exists.  Left as a bare return the card drew
	  "--  no local archive yet" while the console printed "main saved" about the
	  same finish: two statements about one time, contradicting each other, on the
	  one finish a player is most likely to be reading.

	  It is rank 1 of 1 by construction: the write that follows IS the whole
	  archive for that leg.  Off a lobby nothing changed -- the server has already
	  written its file by the time this runs, so total > 0 there.
	*/
	if (total <= 0)
	{
		if ((getstatf(STAT_FS_LOBBY) & LS_LOBBY) && ticks > 0)
		{
			rank = 1;
			of   = 1;
		}
		return;                 // nothing archived yet; rank stays 0
	}

	// +1 for this run itself, which may or may not be on disk yet.  Counting
	// strictly-faster names and adding one is right either way.
	rank = faster + 1;
	of   = total;
	if (of < rank)
		of = rank;
};

/*
  ---- THE WORLD ROW.  Build 65. --------------------------------------------

  The local rank above is a directory scan.  This one is an ANSWER FROM A
  SERVER, arriving over a network some milliseconds after the card is already
  drawn, and every difference between the two functions follows from that.

  IT MUST MATCH THE RUN IN FRONT OF IT OR SAY NOTHING.  The server publishes
  `*wrank` as "<map> <track> <leg> <ticks> <state> <rank> <of>" (sh_defs.qc has
  the essay) precisely so this comparison is possible: a rank with no subject
  would be drawn against whatever finish happened to be on screen, and a rank
  from the previous leg drawn beside this leg's time is worse than the dash the
  card drew before any of this existed -- it is wrong and it is believed.

  RE-READ EVERY FRAME, not latched.  That is the whole mechanism by which a
  late answer reaches a card that is already up: the row says "..." while the
  directory is being asked and becomes "#3 of 17" in place when it replies,
  with no event, no timer and no state of its own.

  WR_NONE is returned for "nothing here is about this run", which covers the
  server never having submitted anything, a key about some other run, and a
  server that does not rank at all.  The caller separates those by asking the
  serverinfo `board` key, because that is a property of the SERVER and this
  function only knows about runs.
*/
#define WR_NONE (-1)

float(float track, float leg, float ticks,
      __inout float rank, __inout float of) Results_WorldRank =
{
	rank = 0;
	of   = 0;

	// Seven fields exactly.  A short key is a key from an older server, and a
	// reader that took what it could get out of one would be inventing.
	if (tokenize(getplayerkeyvalue(player_localnum, "*wrank")) < 7)
		return WR_NONE;

	if (argv(0) != serverkey("map"))
		return WR_NONE;
	if (stof(argv(1)) != track)
		return WR_NONE;
	if (stof(argv(2)) != leg)
		return WR_NONE;
	if (stof(argv(3)) != ticks)
		return WR_NONE;

	rank = stof(argv(5));
	of   = stof(argv(6));
	return stof(argv(4));
};

/*
  The sentence the world row draws, as a PURE function of the state.

  SPLIT OUT SO THE CONSOLE CAN PRINT THE SAME STRING THE CARD DRAWS, on the
  SV_RulesetBroken precedent (p313): the card cannot be opened without a real
  finish, and a finish cannot be reached from a config on a zoned map, so a
  rule that only existed inside the draw call could not be checked headlessly
  at all.  Asking it costs nothing and has no side effect, so `results wrank`
  reports the truth rather than a second copy of it.

  SIX SENTENCES, and the last three are about the SERVER rather than the run --
  which is why they are reached only when nothing was published about this run.
*/
string(float wst, float wrank, float wof) Results_WorldNote =
{
	if (wst == WR_RANKED && wrank > 0)
		return sprintf("#%g of %g", wrank, wof);

	// Deliberately shown.  The gap between finishing and the directory
	// answering is the moment the player is asking "did that count?", and an
	// empty row through it reads as "no".
	if (wst == WR_PENDING)
		return "...  asking the leaderboard";

	// Accepted, position unknown -- see WR_STORED's essay in sh_defs.qc.  It
	// says what is actually known and does not guess at a number, which is the
	// point of it being a separate state rather than a rank of 0.
	if (wst == WR_STORED)
		return "--  on the board (no rank given)";

	if (wst == WR_NOBOARD)
		return "--  this run has no board";
	if (wst == WR_FAILED)
		return "--  the leaderboard did not take it";

	if (serverkey("board") == "noid")
		return "--  this server cannot identify you";

	// A ranked server that published nothing about this run: every gate in
	// Lobby_SubmitRun that returns without posting lands here.
	if (serverkey("board") == "ranked")
		return "--  not submitted";

	/*
	  NO CLAIM AT ALL WHEN THE SERVER HAS NOT SAID.  An empty `board` key means
	  either a server older than build 64 or -- caught in the b65rank run, at
	  the very first sample -- serverinfo that has simply not arrived yet.  On
	  that sample this row read "times here stay on this machine" ON A RANKED
	  SERVER, which is a positive statement about somebody's times that happened
	  to be false.  It cannot reach a player today, because a card needs a
	  finish and a finish is long after serverinfo; it would the moment anything
	  else drew this note.  A dash claims nothing and is always true.
	*/
	if (serverkey("board") == "")
		return "--";

	// The ordinary case, and the one the player most needed told: a listen
	// server, or a server with no key.  Nothing is broken.
	return "--  times here stay on this machine";
};

/*
  The leg, spelled for a HUMAN.

  NOT FS_LegDir, which is the path speller: it answers "bonus_2_stage_3" because
  that is a directory name, and a directory name is the one thing a player
  should never be shown.  Same fact, two audiences, and the project already
  keeps those apart everywhere else.

  BUILD 57: BY LEG, and the words did not change -- the number under them did.
  `startseg` was the 0-based segment, so this card said "stage 2" about a stage-3
  run and could never say "stage 1".  A leg IS the stage number (FS_LegOf).
*/
string(float track, float leg) Results_LegName =
{
	if (track <= 0)
	{
		if (leg <= 0) return "main";
		return sprintf("stage %g", leg);
	}
	if (leg <= 0) return sprintf("bonus %g", track);
	return sprintf("bonus %g, stage %g", track, leg);
};

void() Results_Close =
{
	if (!ui_rs_open)
		return;
	ui_rs_open = FALSE;

	/*
	  Give the cursor back only if we had taken it, and only if nothing else
	  still wants it.  Three panels share this and all three now ask the same
	  question -- see the block beside rec_sb_open in cl_hud.qc for what it cost
	  when one of them did not.

	  BUILD 55: this site had the most complete list of the four and it was
	  still going to be wrong on the next owner.  ui_rs_cursor stays -- it is
	  the card's own record of whether it ever took the mouse, which is not the
	  same as whether the card is drawn -- but the "does anyone else want it"
	  half is now one call.  See the cursor claim register in cl_hud.qc.
	*/
	if (ui_rs_cursor)
	{
		ui_rs_cursor = FALSE;
		UI_CursorRelease(UIC_RESULTS);
	}
};

void() Results_TakeCursor =
{
	if (ui_rs_cursor)
		return;
	ui_rs_cursor = TRUE;
	UI_CursorClaim(UIC_RESULTS);
};

/*
  THE FINISH LATCH, and it watches TWO edges because neither alone is enough.

    TS_FINISHED arriving    the obvious one, and it can be missed: the state
                            does not stand still.  run_t_pendarm re-arms you a
                            couple of ticks after a stage run finishes, and a
                            dropped snapshot across that window delivers ARMED
                            without ever having shown FINISHED.
    RUNTAG leaving RT_NONE  published by SV_RecClose at the end of the finish
                            and left standing -- SV_RecDiscard deliberately does
                            not clear it, so that a client which has not
                            rendered a frame since the finish still sees it.
                            That is exactly the property a latch wants.

  ui_rs_seen is what stops the second edge firing twice.  A tag stands until
  the next run overwrites it, so without an arm the card would reopen every time
  anything else re-evaluated -- the latch closes when the card is raised and
  opens again only when a run is genuinely RUNNING.
*/
void() Results_Open =
{
	local float leg, lobby;

	/*
	  BUILD 57, STAGE T -- IN A LOBBY THE CARD IS DRAWN FROM A DIFFERENT SET OF
	  STATS, because the usual three are never published there.

	  RUNTICKS, RUNTAG and RUNLEG are all written by SV_RecClose, and a lobby
	  switches the recorder off -- so this function used to open a card reading
	  0:00.000 on the main leg of whatever track the player happened to be on.
	  FINTICKS / FINFLAGS / FINLEG are the same three facts, published by
	  SV_TimerFinish itself and standing until the next finish, which is what lets
	  `results` reopen the card later.
	*/
	// BUILD 57: LS_LOBBY, masked -- the stat carries three bits now and the
	// question here is only "is this a lobby", because what is missing on one
	// (RUNTICKS/RUNTAG/RUNLEG) is missing whatever its keeping cvars say.
	lobby = getstatf(STAT_FS_LOBBY) & LS_LOBBY;

	if (lobby)
	{
		ui_rs_ticks = getstatf(STAT_FS_FINTICKS);
		ui_rs_flags = getstatf(STAT_FS_FINFLAGS);

		/*
		  BUILD 57: NOTHING TO SHOW IS NOT A CARD.  Off a lobby this branch falls
		  back to the live clock, which is why `results` before a finish shows the
		  attempt in progress; in a lobby there is no such fallback -- FINTICKS is
		  0 until the first finish -- so a bare `results` drew 0:00.000 on `main`,
		  class clean, "first".  Every one of those is false.  Refuse instead, and
		  say which of the two it is, because "no finish yet" and "the card is
		  switched off" look identical from the console.
		*/
		if (ui_rs_ticks <= 0)
		{
			print("^3results:^7 no finish on this map yet -- nothing to show\n");
			return;
		}
	}
	else
	{
		ui_rs_ticks = getstatf(STAT_FS_RUNTICKS);
		if (ui_rs_ticks <= 0)
			ui_rs_ticks = getstatf(STAT_FS_TIMERTICKS);

		ui_rs_flags = getstatf(STAT_FS_TIMERFLAGS);
	}

	/*
	  READ THE SAME WAY IN BOTH CASES, and in a lobby it is RT_NONE -- which is
	  true rather than missing: the server kept no file for this run, and the one
	  this client writes is not the server's answer to give.  Nothing on the card
	  draws from it (cl_main.qc's `timer` verification print is its only reader),
	  so an invented tag here would be a lie with no upside.
	*/
	ui_rs_tag = getstatf(STAT_FS_RUNTAG);

	/*
	  THE PB THE RUN WAS MEASURED AGAINST, and not STAT_FS_TIMERPB.

	  SV_TimerFinish re-reads run_t_pb AFTER it has overwritten run_pb_ticks, so
	  on any personal best TIMERPB has already become this run's own time and the
	  delta is identically zero.  That has been true since build 19 and is why
	  the finish row down the left has never drawn a number.  STAT_FS_TIMERPBWAS
	  is the value latched before the table was rewritten.
	*/
	ui_rs_pb = getstatf(STAT_FS_TIMERPBWAS);

	// RUNLEG is track*100 + leg + 1 (sh_defs.qc).  BUILD 57: a LEG, so a stage-1
	// run decodes to 1 and gets its own name and its own rank, where it used to
	// decode to 0 and be ranked against the whole map.  STAGE T: FINLEG carries
	// the identical encoding, so the decode below is shared rather than repeated.
	leg = lobby ? getstatf(STAT_FS_FINLEG) : getstatf(STAT_FS_RUNLEG);
	if (leg >= 1)
	{
		leg = leg - 1;
		ui_rs_track = floor(leg / 100);
		ui_rs_leg   = leg - ui_rs_track * 100;
	}
	else
	{
		ui_rs_track = getstatf(STAT_FS_TIMERTRACK);
		ui_rs_leg   = 0;
	}
	ui_rs_startseg = (ui_rs_leg > 0) ? ui_rs_leg - 1 : 0;

	/*
	  BUILD 57, STAGE T -- "PERSONAL BEST BY" AND "FIRST" IN A LOBBY COME FROM
	  THIS DISK, because the server's answer there is deliberately zero.

	  SV_PBGet refuses to read the host's table in a lobby (Lobby_NoPB, whose
	  essay is about showing a stranger's time as yours), so TIMERPBWAS arrives as
	  0 and the card would say "first" on every attempt for ever.  The lobby files
	  ARE the record, so they are what this is measured against.

	  THE ORDER WITH cl_lobbytime.qc IS LOAD-BEARING: cl_main.qc calls
	  Results_Frame() and then LT_Frame(), so this read happens before this run's
	  own file exists.  `ui_rs_ticks` is passed as the file to ignore anyway, which
	  is what keeps a card reopened by `results` from comparing the run against
	  itself.
	*/
	if (lobby)
		ui_rs_pb = LT_BestOnLeg(serverkey("map"), ui_rs_track, ui_rs_leg,
		                        ui_rs_ticks);

	Results_Rank(ui_rs_track, ui_rs_leg, ui_rs_ticks,
	             ui_rs_rank, ui_rs_of);

	ui_rs_open   = TRUE;
	ui_rs_at     = cltime;
	ui_rs_cursor = FALSE;
	ui_rs_seen   = FALSE;
};

/*
  Per frame, before anything draws.  Owns the two latches and nothing else.

  THE TOAST IS RAISED AT THE BOTTOM AND ONLY IF THE CARD WAS NOT, which is the
  one ordering rule in this file.  The client sees SNAPSHOTS, not ticks: on the
  frame a leg finishes, the stage-close edge and the finish edge can both be
  present, and a toast raised from the first would sit under the card
  announcing a fragment of the run the card is already summarising.
*/
void() Results_Frame =
{
	local float state, tag, endrec, seg, leg, fresh;
	local float finrec, finfresh;   // build 57, stage T: the lobby's finish edge

	/*
	  A map change retires everything here -- the card describes a leg on a map
	  you are no longer standing in, and the toast's rank was counted out of that
	  map's folder.

	  Watched from here rather than hooked out of cl_main.qc for the reason
	  cl_timer.qc gives for doing the same thing: one string compare a frame is
	  cheaper than the coupling, and it keeps this file's whole contract with
	  cl_main.qc down to four calls.
	*/
	if (zone_mapname != ui_rs_map)
	{
		ui_rs_map = zone_mapname;
		Results_MapInit();
	}

	state = getstatf(STAT_FS_TIMERSTATE);
	tag   = getstatf(STAT_FS_RUNTAG);

	/*
	  BUILD 57, STAGE T: the finish counter, latched here -- above everything that
	  can open or close a card, and with no return between.  Consuming an edge is
	  one question and deciding to draw is another; that is the same defect this
	  build fixed for the toast latch below.
	*/
	finrec   = getstatf(STAT_FS_FINREC);
	finfresh = FALSE;
	if (ui_rs_lastfinrec >= 0)          // -1 seeds: the first value is not an event
	if (finrec > ui_rs_lastfinrec)
		finfresh = TRUE;
	ui_rs_lastfinrec = finrec;

	if (state == TS_RUNNING)
	{
		ui_rs_seen = TRUE;
		// A new run retires the old card and any toast still fading.  The player
		// is running; nothing on screen should still be about the last attempt.
		Results_Close();
		ui_rs_at      = 0;
		ui_rs_toastat = 0;
	}

	/*
	  Edge one: the state.  Edge two: the tag leaving RT_NONE.

	  BUILD 57, STAGE T -- EDGE THREE REPLACES BOTH IN A LOBBY, and it is an
	  either/or rather than a third term OR'd in.  Neither of the first two can
	  fire there (see ui_rs_lastfinrec), and this one needs no ui_rs_seen arm: a
	  counter cannot re-fire on a value it has already consumed, which is the
	  whole reason the server publishes one.  The TS_RUNNING block above still
	  retires the card when the next attempt starts.
	*/
	if (getstatf(STAT_FS_LOBBY) & LS_LOBBY)
	{
		if (finfresh)
			Results_Open();
	}
	else if (ui_rs_seen)
	{
		if ((state == TS_FINISHED && ui_rs_laststate != TS_FINISHED)
		 || (tag != RT_NONE && ui_rs_lasttag == RT_NONE))
			Results_Open();
	}

	ui_rs_laststate = state;
	ui_rs_lasttag   = tag;

	/*
	  The toast.  Same stage-close edge cl_timer.qc watches for the class mark,
	  read independently here rather than shared, because the two panels have
	  different lifetimes and a shared latch would make one of them consume the
	  other's event.

	  A DELIBERATE STAGE RUN GETS NO TOAST.  Its boundary IS its finish and the
	  card has just covered it -- which the `ui_rs_open` test below happens to
	  cover as well, but the leg test says why rather than relying on the order
	  two latches ran in.

	  BUILD 57: THE EDGE IS LATCHED FIRST, ABOVE EVERY RETURN, and that is a
	  defect fix.  The latch used to sit at the bottom, past three returns --
	  the cvar, `state != TS_RUNNING` and the stage-run test -- so a close that
	  arrived on a frame that returned early was never consumed.  A stage run's
	  close is raised on its FINISH frame, which is exactly such a frame, and it
	  then sat unread until the next run went RUNNING and popped a toast about
	  the attempt before.  Consuming the counter is one question and deciding
	  to draw is another; only the second may be skipped.
	*/
	endrec = getstatf(STAT_FS_STAGEENDREC);
	fresh  = FALSE;
	if (ui_rs_lastendrec >= 0)          // -1 seeds: the first value is not an event
	if (endrec > ui_rs_lastendrec)
		fresh = TRUE;
	ui_rs_lastendrec = endrec;

	if (!fresh)
		return;

	/*
	  BUILD 57, STAGE T: IN A LOBBY THE CARD RAISED THIS FRAME OWNS THE ENDING,
	  and the leg test below cannot say so there.

	  That test reads STAT_FS_RUNLEG, which only SV_RecOpen and SV_RecRewind ever
	  write -- and a lobby switches the recorder off, so RUNLEG is 0 for the whole
	  session and "a stage run: the card owns its ending" is dead in exactly the
	  place this build added a card.  The finish counter is the one signal that
	  still fires there, so it is what the refusal hangs on: if this frame opened a
	  card, no toast.  That keeps the promise the header makes -- the toast is
	  raised at the bottom and ONLY if the card was not.
	*/
	if (finfresh)
		return;

	if (!cvar("hud_results_toast"))
		return;
	if (state != TS_RUNNING)
		return;

	// RUNLEG is track*100 + leg + 1.  BUILD 57: a LEG, so a stage-1 run -- which
	// begins at segment 0 exactly as a full run does -- is still a stage run here.
	leg = getstatf(STAT_FS_RUNLEG);
	if (leg >= 1)
	{
		leg = leg - 1;
		leg = leg - floor(leg / 100) * 100;
	}
	else
		leg = 0;
	if (leg > 0)
		return;                 // a stage run: the card owns its ending

	ui_rs_toastword  = getstatf(STAT_FS_STAGEENDST);
	ui_rs_toastticks = getstatf(STAT_FS_STAGEENDTICKS);
	seg              = getstatf(STAT_FS_STAGEENDSEG);

	/*
	  Only for a stage that actually closed with a duration.  A refused close
	  still bumps the counter -- it has to, or the class mark would miss the
	  very rows it is about -- but a toast saying "stage 3: 0:00.000" is
	  noise, and the mark down the left already carried the refusal.

	  BUILD 57: SEGMENT 0 IS A STAGE, so the `seg > 0` half of this test is gone
	  and stage 1 gets its toast at the stage-2 boundary like every other stage.
	  `seg >= 0` stays: -1 is "no stage was open", which has no leg to name.  The
	  stat is a SEGMENT and the toast is about a LEG, so both the label and the
	  rank take seg + 1 -- the same FS_LegOf(seg, TRUE) the server filed it under.
	*/
	if (ui_rs_toastticks > 0)
	if (seg >= 0)
	{
		ui_rs_toastat  = cltime;
		ui_rs_toastseg = FS_LegOf(seg, TRUE);   // latched: the stat moves on, the toast does not
		Results_Rank(getstatf(STAT_FS_TIMERTRACK), ui_rs_toastseg, ui_rs_toastticks,
		             ui_rs_toastrank, ui_rs_toastof);
	}
};

/*
  The toast: one line, above the split column, gone in a few seconds.

  Built on the split-flash idiom rather than on sui -- it takes no input, it has
  no hit target, and a sui frame per stage boundary would be a frame stack push
  for something that is one string.
*/
void(vector scr) Results_DrawToast =
{
	local float a, sz, life, tick;
	local vector p, col;
	local string s;

	if (ui_rs_toastat <= 0)
		return;

	tick = Timer_Tick();

	life = cvar("hud_results_toast_time");
	if (life <= 0)
		life = 3.5;

	a = 1 - (cltime - ui_rs_toastat) / life;
	if (a <= 0)
	{
		ui_rs_toastat = 0;
		return;
	}
	if (a > 1)
		a = 1;

	Font_Set(ui_font_mono);
	sz = Font_Px(8 * ui_cv_scale);

	col = RSC_TEXT;
	if (ui_rs_toastword & SF_KNOWN)
	if (ui_rs_toastword & SF_DIRTY)
		col = RSC_DIM;          // it did not record; say so by going quiet

	if (ui_rs_toastrank > 0)
		s = sprintf("stage %g  %s  #%g of %g",
		            ui_rs_toastseg,
		            Time_TickString(ui_rs_toastticks, tick),
		            ui_rs_toastrank, ui_rs_toastof);
	else
		s = sprintf("stage %g  %s",
		            ui_rs_toastseg,
		            Time_TickString(ui_rs_toastticks, tick));

	p = [scr_x * cvar("hud_splits_x"), scr_y * cvar("hud_splits_y") * 0.62, 0];
	HUD_Text(p, s, sz, col, a);
	Font_Reset();
};

/*
  The card.

  DRAWN WITH RAW HUD_Text AND drawfill WHILE PASSIVE, and only wrapped in a sui
  frame once the cursor has been taken.  A sui_begin/sui_end pair every frame
  for a panel with no hit targets would put this file in the input system's way
  for no benefit, and "appears free" means exactly that: until you ask for it,
  this is a picture.
*/
void(vector scr) Results_Draw =
{
	local float a, y, sz, hero, w, hgt, x, tick;
	local vector p, col;
	local string s;

	if (!ui_rs_open || !cvar("hud_results"))
		return;

	// Taken here rather than passed in, so the two call sites in cl_main.qc are
	// one argument each and neither has to know this panel formats times at all.
	tick = Timer_Tick();

	// A 100 ms beat before it appears, so the stopped clock registers as the
	// first thing that changed and this arrives as the second.
	a = (cltime - ui_rs_at - 0.10) / 0.18;
	if (a <= 0)
		return;
	if (a > 1)
		a = 1;

	Font_Set(ui_font_mono);
	sz   = Font_Px(7 * ui_cv_scale);
	hero = Font_Px(18 * ui_cv_scale);

	w   = 300 * ui_cv_scale;
	hgt = (10 + RS_ROWS) * (sz + 3 * ui_cv_scale) + hero;
	x   = scr_x * cvar("hud_results_x") - w * 0.5;
	if (x < 0) x = 0;
	if (x + w > scr_x) x = scr_x - w;

	p = [x, scr_y * cvar("hud_results_y") - hgt * 0.5, 0];

	drawfill(p, [w, hgt, 0], RSC_PANEL, a * 0.92, 0);
	drawfill(p, [w, 1 * ui_cv_scale, 0],
	         Timer_Color(TS_FINISHED, ui_rs_ticks, ui_rs_pb, ui_rs_flags), a, 0);

	y = p_y + 8 * ui_cv_scale;

	// The one number the card is for.
	Font_Set(ui_font_display);
	HUD_Text([p_x + 10 * ui_cv_scale, y],
	         Time_TickString(ui_rs_ticks, tick),
	         Font_Px(18 * ui_cv_scale),
	         Timer_Color(TS_FINISHED, ui_rs_ticks, ui_rs_pb, ui_rs_flags), a);
	Font_Set(ui_font_mono);

	// ...and what it was against.  ui_rs_pb is PBWAS, so this is a real delta
	// on a personal best rather than the zero TIMERPB would give.
	if (ui_rs_pb > 0)
	{
		col = (ui_rs_ticks < ui_rs_pb) ? RSC_GOOD : RSC_BAD;
		HUD_TextR([p_x + w - 10 * ui_cv_scale, y + 6 * ui_cv_scale],
		          Time_DeltaString(ui_rs_ticks - ui_rs_pb, tick), sz, col, a);
	}
	else
		HUD_TextR([p_x + w - 10 * ui_cv_scale, y + 6 * ui_cv_scale],
		          "first", sz, RSC_DIM, a);

	y = y + hero + 4 * ui_cv_scale;

	HUD_Text([p_x + 10 * ui_cv_scale, y],
	         sprintf("%s  -  %s  -  %s",
	                 serverkey("map"),
	                 Results_LegName(ui_rs_track, ui_rs_leg),
	                 FS_RunClassName(FS_RunClass(ui_rs_flags))),
	         sz, RSC_DIM, a);
	y = y + (sz + 6 * ui_cv_scale);

	/*
	  THE RANK BLOCK.  Two rows, and the second is always drawn.

	  `world` WAS a reserved dash and is now a real answer.  The reservation in
	  sh_defs.qc (stats 90 and 91) still stands and is still unregistered -- it
	  is NOT what shipped, and the essay beside it says why two numbers with no
	  subject cannot answer this question.  What arrives instead is one userinfo
	  key that names the run it is about, which is what lets this row tell "your
	  rank" from "somebody's rank", and lets a late reply land on a card that is
	  already on screen.

	  SIX SENTENCES, NOT A NUMBER AND A DASH.  Every one of these was, before
	  this build, drawn as the same "no board yet" -- including the two that
	  describe a FAULT an operator could fix and the one where the run really is
	  on the board.  A single dash covering all of them is how a working feature
	  and a broken one came to look identical from the player's seat, which is
	  the report that started this work.
	*/
	if (ui_rs_rank > 0)
		s = sprintf("#%g of %g", ui_rs_rank, ui_rs_of);
	else
		s = "--  no local archive yet";
	HUD_Text([p_x + 10 * ui_cv_scale, y], "local", sz, RSC_DIM, a);
	HUD_Text([p_x + 60 * ui_cv_scale, y], s, sz, RSC_TEXT, a);
	y = y + (sz + 3 * ui_cv_scale);

	{
		local float  wst, wrank, wof, wlit;
		local vector wcol;

		// Initialised for the COMPILER, not because the callee might not write
		// them: fteqcc cannot see through __inout and warns F302 on the call
		// otherwise.  Results_WorldRank zeroes both on its first two lines.
		wrank = 0;
		wof   = 0;
		wst   = Results_WorldRank(ui_rs_track, ui_rs_leg, ui_rs_ticks,
		                          wrank, wof);
		s     = Results_WorldNote(wst, wrank, wof);
		wlit  = (wst == WR_RANKED && wrank > 0);   // an ANSWER, or a note?

		// Nested rather than a ternary on the colour: fteqcc's ternary
		// evaluates BOTH arms, which is a documented trap in this tree, and a
		// vector-valued one is not worth finding the edge of.
		wcol = RSC_DIM;
		if (wlit)
			wcol = RSC_TEXT;

		HUD_Text([p_x + 10 * ui_cv_scale, y], "world", sz, RSC_DIM,
		         wlit ? a : a * 0.7);
		HUD_Text([p_x + 60 * ui_cv_scale, y], s, sz, wcol,
		         wlit ? a : a * 0.7);
	}
	y = y + (sz + 8 * ui_cv_scale);

	drawfill([p_x + 10 * ui_cv_scale, y], [w - 20 * ui_cv_scale, 1, 0],
	         RSC_LINE, a * 0.4, 0);
	y = y + 6 * ui_cv_scale;

	/*
	  THE TABLE.  ui_sp_*, the same rows the column down the left is drawing,
	  including its class marks -- one table, two presentations, and no second
	  copy of the list.  The TAIL is shown: on a long map the stages you just
	  did are the ones you came to read.
	*/
	{
		local float i, first;
		local string mark;
		local vector mcol;

		first = ui_sp_n - RS_ROWS;
		if (first < 0)
			first = 0;

		if (first > 0 || ui_sp_over > 0)
		{
			HUD_Text([p_x + 10 * ui_cv_scale, y],
			         sprintf("+%g earlier", first + ui_sp_over),
			         sz, RSC_DIM, a * 0.8);
			y = y + (sz + 3 * ui_cv_scale);
		}

		for (i = first; i < ui_sp_n; i = i + 1)
		{
			if (ui_sp_kind[i] == SPK_FINISH)
				s = "finish";
			else if (ui_sp_kind[i] == SPK_CP)
				s = sprintf("cp %g", ui_sp_seg[i]);
			else
				s = sprintf("stage %g", ui_sp_seg[i]);

			col  = RSC_TEXT;
			mcol = col;
			mark = Timer_SplitsClass(ui_sp_class[i], mcol);
			if (mark != "")
			{
				HUD_Text([p_x + 4 * ui_cv_scale, y], mark, sz, mcol, a);
				col = mcol;
			}

			HUD_Text([p_x + 14 * ui_cv_scale, y], s, sz, col, a * 0.9);
			HUD_Text([p_x + 70 * ui_cv_scale, y],
			         Time_TickString(ui_sp_ticks[i], tick), sz, RSC_TEXT, a);
			if (ui_sp_speed[i] > 0)
				HUD_TextR([p_x + w - 10 * ui_cv_scale, y],
				          sprintf("%d u/s", rint(ui_sp_speed[i])),
				          sz, RSC_DIM, a * 0.85);
			y = y + (sz + 3 * ui_cv_scale);
		}
	}

	// The footer says how to reach the buttons, because a panel that needs a
	// gesture nobody guesses is a panel with no buttons.
	if (!ui_rs_cursor)
		HUD_Text([p_x + 10 * ui_cv_scale, p_y + hgt - (sz + 8 * ui_cv_scale)],
		         "f1 or mouse3 for cursor    esc to close", sz, RSC_DIM, a * 0.7);

	Font_Reset();
	HUD_Rect("results", p, [w, hgt, 0], p);
};

/*
  Input, and it is only ever reached once the cursor has been taken -- the chain
  in cl_main.qc tests ui_rs_cursor, not ui_rs_open, so a card that is merely on
  screen swallows nothing at all.

  IE_MOUSEABS RETURNS TRUE UNCONDITIONALLY, for the reason Scores_InputEvent
  documents at length: setcursormode(TRUE) makes the engine send absolute
  positions and it zeroes the accumulated delta ONLY when CSQC returns TRUE, so
  a handler that forgets leaves the view spinning under the cursor.
*/
float(float evtype, float scanx, float chary, float devid) Results_InputEvent =
{
	if (!ui_rs_cursor)
		return FALSE;

	if (evtype == IE_MOUSEABS)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE)
	{
		Results_Close();
		return TRUE;
	}
	return FALSE;
};

/*
  The passive half: the two gestures that ASK for the cursor.

  F1 AND MOUSE3, both, because the request was "a key or a click" and a literal
  left click is not available -- MOUSE1 and MOUSE2 are +duck and +jump in
  cfg/default.cfg, so taking either would cost movement.  MOUSE3 is free in the
  shipped config and is the only click there is.

  Reached from the key path in cl_main.qc while the card is open and the cursor
  has NOT been taken.  Returns TRUE only when it consumed the press.
*/
float(float scanx) Results_PassiveKey =
{
	if (!ui_rs_open || !cvar("hud_results"))
		return FALSE;

	if (scanx == K_F1 || scanx == K_MOUSE3)
	{
		Results_TakeCursor();
		return TRUE;
	}
	if (scanx == K_ESCAPE)
	{
		Results_Close();
		return TRUE;
	}
	return FALSE;
};

float(string cmd) Results_ConsoleCommand =
{
	// argv(0) RATHER THAN cmd, so the command can take a subcommand at all:
	// `cmd` is the whole line, so `results wrank` never equalled "results" and
	// fell through to the engine as an unknown command.  A bare `results` is
	// unaffected.
	if (argv(0) != "results")
		return FALSE;

	/*
	  ---- `results wrank`.  Build 65. --------------------------------------

	  THE WORLD ROW IS THE ONE THING ON THIS CARD THAT COMES FROM A SERVER, and
	  the card cannot be opened without a real finish, which cannot be reached
	  from a config on a zoned map.  So without this handle the entire path --
	  a submission, a directory answer, a userinfo key, a subject match and a
	  sentence -- was uncheckable except by playing the game, and "it looked
	  right when I played it" is the standard this tree does not accept.

	  IT PRINTS THE RAW KEY BEFORE ANYTHING IS DECIDED FROM IT.  A decoded
	  reading that disagrees with its own input is the failure worth catching,
	  and a reader that only ever showed its conclusion could not show it.
	*/
	if (argv(1) == "wrank")
	{
		local float wst, wrank, wof, qtrack, qleg, qticks;
		local string raw;

		/*
		  THE SUBJECT MAY BE NAMED: `results wrank <track> <leg> <ticks>`.

		  Without it this can only ever ask about the card's own finish, which
		  on a headless client is 0/0/0 forever -- so the two answers that
		  matter, "this IS your run" and "this is NOT your run", could not both
		  be produced in one session.  Naming it turns the subject match itself
		  into something a config can falsify: ask about the run that was
		  submitted and about one digit off it, and the second must come back
		  with nothing however good the first looks.
		*/
		if (argv(2) != "")
		{
			qtrack = stof(argv(2));
			qleg   = stof(argv(3));
			qticks = stof(argv(4));
		}
		else
		{
			qtrack = ui_rs_track;
			qleg   = ui_rs_leg;
			qticks = ui_rs_ticks;
		}

		raw = getplayerkeyvalue(player_localnum, "*wrank");
		print(sprintf("  *wrank = %s\n", (raw != "") ? raw : "(unset)"));
		print(sprintf("  board  = %s\n",
		              (serverkey("board") != "") ? serverkey("board")
		                                         : "(unpublished)"));

		// The card's own subject is printed whether or not it is the one being
		// asked about, because a key that matched a subject of all zeroes
		// would be a bug in the stamp and this is where it would show.
		print(sprintf("  card   = track %g leg %g ticks %g\n",
		              ui_rs_track, ui_rs_leg, ui_rs_ticks));
		print(sprintf("  asking = track %g leg %g ticks %g\n",
		              qtrack, qleg, qticks));

		wrank = 0;
		wof   = 0;
		wst   = Results_WorldRank(qtrack, qleg, qticks, wrank, wof);
		print(sprintf("  state  = %g  rank %g of %g%s\n", wst, wrank, wof,
		              (wst == WR_NONE) ? "   (nothing published about this run)"
		                               : ""));
		print(sprintf("  draws  = %s\n", Results_WorldNote(wst, wrank, wof)));
		return TRUE;
	}

	if (ui_rs_open)
		Results_Close();
	else
	{
		Results_Open();
		Results_TakeCursor();
	}
	return TRUE;
};

/*
  Per map.  The toast latch seeds to -1 for the reason cl_timer.qc's does: the
  stat legitimately reads 0 on a fresh map, and seeding to 0 would make the
  first close of the map invisible instead of the first close being a seed.
*/
void() Results_MapInit =
{
	Results_Close();
	ui_rs_at        = 0;
	ui_rs_toastat    = 0;
	ui_rs_toastseg   = 0;
	ui_rs_lastendrec = -1;
	ui_rs_lastfinrec = -1;          // build 57, stage T; seeded, like the one above
	ui_rs_laststate  = -1;
	ui_rs_lasttag   = RT_NONE;
	ui_rs_seen      = FALSE;
	ui_rs_rank      = 0;
	ui_rs_of        = 0;
};
