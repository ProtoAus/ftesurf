/*
===========================================================================
  cl_online.qc -- the ONLINE half of the leaderboard: ask surfd, parse, keep.

  cl_scores.qc has been a LOCAL board since build 24: it lists the .rec files
  on this disk, which is "every recording you have" and is genuinely useful,
  but it is the only board in the game and it is one player wide.  This file
  is the other side -- one GET against surfd's /api/board, parsed into the
  same shape the local rows already use, so the drawing code can show either.

  IT DRAWS NOTHING.  Fetch, parse and storage only, with a console command to
  prove all three without a UI.  That split is deliberate: the request path
  can then be tested from a config (`board_fetch`, `board_status`) on a
  headless launch, and the tabs that consume it are a separate change that
  cannot break the network path by accident.

  FOUR THINGS DECIDED THE SHAPE, and three of them are traps this tree has
  already paid for once.

  1. SUCCESS IS responsecode 0, NOT 200.  PR_uri_get_callback2
     (pr_bgcmd.c:6014) does

         G_FLOAT(OFS_PARM1) = (replycode!=200)?replycode:0;
             //for compat with DP, we change any 200s to 0.

     so a test written `if (responsecode != 200) fail` classifies every
     SUCCESSFUL reply as a failure and the board is permanently empty against
     a directory that is answering perfectly.  m_lobby.qc records having
     written exactly that bug, and says the same wrong test is the natural
     thing to write in the other progs too -- so this is the third copy of the
     correct one, written from its warning rather than from scratch.

  2. THERE IS EXACTLY ONE URI_Get_Callback PER VM, found by NAME by the engine
     (pr_bgcmd.c:6003).  This is CSQC's first, so nothing has to branch yet --
     but the reqid test below is written as an "is this mine" test rather than
     merely a staleness guard, because the second caller to want uri_get from
     CSQC cannot declare its own and will have to branch inside this one.

  3. A REPLY CAN ARRIVE FOR A BOARD NOBODY IS LOOKING AT ANY MORE.  The player
     can change leg, tab or map between the request and the reply, and a
     several-hundred-millisecond round trip is long enough for all three.  So
     the request records WHAT IT ASKED FOR, and the reply is stored against
     that rather than against whatever is on screen now.  A board that renders
     the previous leg's times under this leg's heading is worse than an empty
     one: it is wrong and it looks right.

  4. STRBUFS, NOT STRING ARRAYS, for the two string columns -- the same reason
     cl_scores.qc gives for its three: a QC `string x[64]` needs a strzone per
     entry and a strunzone on every rebuild, and a missed unzone is a leak
     nothing reports.  A strbuf is one handle and bufstr_set overwrites without
     either.

  WHAT THIS DELIBERATELY DOES NOT DO: it never merges tiers.  `ranked` and
  `community` are fetched and stored separately and the counts for both come
  back with either, so the UI can say "no ranked times yet, 37 community"
  without a second request and without ever ordering a community run into a
  ranked list.  surfd enforces that separation in its primary key; this keeps
  it on the client rather than relying on the server alone.
===========================================================================
*/

#define OB_MAXROW  64      // one page; surfd's own cap is 200 and default 50

/*
  How long a failed board waits before ONE re-ask, and how long a request may
  stay in flight before it is written off.

  30s is long enough that a leaderboard which is down is not being hammered --
  the anti-hammer property Online_Need exists for -- and short enough that a
  player who hit a 429 during a busy minute gets their board back inside the
  same session rather than the next one.

  10s for the deadline because nothing else imposes one.  The engine's HTTP
  client has no wall-clock timeout at all: HTTP_DL_Work's only timeout is a
  0.1s select() used to decide readability (httpclient.c:370-381), and
  URI_Get_Callback runs only when a transfer ENDS.  So a connection that is
  established and then never answered leaves ob_state at OBS_FETCH forever --
  and Online_Need's first test blocks EVERY board while one is in flight, so a
  single wedged request takes the whole online scoreboard out for the session.
*/
#define OB_RETRY_SECS  30
#define OB_DEADLINE    10

// Board_State
#define OBS_IDLE    0      // nothing asked for yet
#define OBS_FETCH   1      // request in flight
#define OBS_OK      2      // rows below are good
#define OBS_FAIL    3      // ob_code / ob_err say why
#define OBS_NODIR   4      // lobby_dir is empty: not an error, not configured
#define OBS_NOTERMS 5      // the online terms have not been accepted

float  ob_state;
float  ob_req;             // uri request id in flight; 0 = none
float  ob_code;            // last non-zero responsecode
float  ob_when;            // cltime the rows landed
float  ob_sent;            // cltime the in-flight request went out; 0 = none
float  ob_retry_at;        // cltime after which ONE re-ask is allowed; 0 = never

/*
  The SERVER's clock at the moment it answered -- root `t`, beside the rows'
  own `when`.  The age column is the difference of those two, so it needs no
  clock on this machine at all: a client with a wrong date, a wrong timezone or
  no RTC still reads "3d" correctly, and there is no strftime here to get the
  %s extension wrong on Windows.

  BOTH ARE UNIX SECONDS IN A QC FLOAT, WHICH IS 32-BIT.  1.75e9 needs 31 bits
  of integer and the mantissa holds 24, so each value lands on a 128-SECOND
  GRID and their difference carries up to ~128 s of error.  That is why the
  finest bucket below is "now" for anything under two minutes and everything
  above it is minutes or coarser -- a seconds-accurate age is not available
  from these two numbers and pretending otherwise would be a made-up digit.
*/
float  ob_t;

/*
  What the IN-FLIGHT request asked for.  Read only by the callback, to label
  the rows it stores; never by the drawing code, which asks what the STORED
  rows describe (ob_have_*).  Keeping the two apart is trap 3 above.
*/
string ob_q_map;
float  ob_q_track, ob_q_leg;
string ob_q_tier, ob_q_style;
float  ob_q_zoned;         // ob_q_* hold strzones that have to be given back

// What the stored rows actually describe.
string ob_have_map;
float  ob_have_track, ob_have_leg;
string ob_have_tier, ob_have_style;
float  ob_have_zoned;

float  ob_n;
float  ob_rank[OB_MAXROW];
float  ob_ticks[OB_MAXROW];
float  ob_ms[OB_MAXROW];
float  ob_flags[OB_MAXROW];
/*
  The row's OWN tickrate, kept rather than assumed.  Time_TickString needs one
  to turn ticks into a duration, and a run set at a different pm_ticrate is
  exactly the case surfd ranks by millis to get right -- formatting it against
  this client's rate would print a time that disagrees with the rank beside it.
*/
float  ob_rate[OB_MAXROW];
float  ob_wrow[OB_MAXROW]; // row `when`: unix seconds, server-side.  See ob_t.
float  ob_bname;           // strbuf: display name per row
float  ob_bplayer;         // strbuf: stable player id per row

// Both tiers' totals for the queried (map, track, leg, style), so the UI can
// report the other tier without asking for it.
float  ob_cnt_ranked;
float  ob_cnt_community;

void() Online_Status;

/*
  Is this failure worth one more try, or is it an answer?

  DEFINED THIS EARLY because URI_Get_Callback needs it and QuakeC has no
  forward declaration for a function with a body below its use.

  A 404 is an ANSWER: the directory does not implement this endpoint, and
  asking again every thirty seconds for the rest of the session is exactly the
  hammering Online_Need's guard exists to prevent.  A 429 is the opposite --
  it means "ask again shortly" by definition, and now that the board sits
  behind a rate limiter a 429 is the EXPECTED reply during a busy minute.
  Treating it as permanent leaves a player's board broken long after the limit
  has cleared, which is how one crowded moment costs somebody their session.

  0 and -1 are this file's own codes for "never left the building" and "the
  reply would not parse", both transient by nature; 5xx is the gateway having
  a moment.  Everything else -- 400, 403, 404 -- is the server telling us
  something true about the request, and repeating it cannot help.
*/
float(float code) Online_Retryable =
{
	if (code <= 0)   return TRUE;       // no reply, or an unparseable one
	if (code == 429) return TRUE;       // rate limited: literally "try later"
	if (code >= 500 && code <= 599) return TRUE;
	return FALSE;
};

/*
  Give back the two zoned query strings.  Called before every overwrite and on
  reset; a strzone that is overwritten without this is a leak, and QC reports
  none of them.
*/
void() Online_FreeQuery =
{
	if (!ob_q_zoned)
		return;
	strunzone(ob_q_map);
	strunzone(ob_q_tier);
	strunzone(ob_q_style);
	ob_q_zoned = FALSE;
};

void() Online_FreeHave =
{
	if (!ob_have_zoned)
		return;
	strunzone(ob_have_map);
	strunzone(ob_have_tier);
	strunzone(ob_have_style);
	ob_have_zoned = FALSE;
};

/*
  Throw the rows away.  Not called on a failed fetch -- see Online_Parse: a
  reply that cannot be parsed leaves the LAST GOOD rows in place rather than
  blanking a board the player is reading because one poll went missing.
*/
void() Online_Clear =
{
	ob_n = 0;
	ob_t = 0;
	ob_cnt_ranked = 0;
	ob_cnt_community = 0;
	Online_FreeHave();
};

/*
  Ask surfd for one board.

  `tier` and `style` are passed rather than inferred, because the two online
  tabs are the same request with one field changed and nothing else differs --
  which is the whole reason the server put style in the key rather than making
  the client filter a merged list.

  Returns TRUE if a request went out.  A false return is not an error: an
  unconfigured lobby_dir is the normal state of an offline install, and the
  board says so rather than reporting a failure nobody caused.
*/
float(float track, float leg, string tier, string style) Online_Fetch =
{
	local string dir, url, mname;

	/*
	  CONSENT FIRST, BEFORE THE URL IS EVEN READ.

	  sh_defs.qc:878 states the rule this file was missing: "FS_TERMS_ONLINE is
	  what anything that contacts a server requires -- joining a lobby, and
	  polling the lobby directory, which discloses an IP address before any
	  lobby is joined and therefore needs consent in its own right."  m_lobby.qc
	  has honoured that since it shipped; this file never did.

	  THE GAP WAS ONE KEYPRESS WIDE.  The scoreboard opens on the ONLINE tab by
	  default and +showscores is TAB, so on any loaded map -- including a purely
	  offline single-player session with no server involved -- one TAB sent a GET
	  to play.proto.bar and disclosed the player's address, whether or not they
	  had ever accepted the online terms.  That is exactly the disclosure
	  Lob_Blocked exists to prevent, and the argument there transfers verbatim:
	  gating only the JOIN would mean the first disclosure happened before the
	  question was asked, which makes the question decorative.

	  THE OR IS THE SAME ONE Rec_HidOK AND HUD_DrawSubmitWarn USE, and it is not
	  belt-and-braces: rec_terms is UNREGISTERED in a headless or early launch,
	  so the cvar alone reads 0 for a player whose data/consent.txt says they
	  accepted -- and telling them they have not is the false accusation
	  cl_hud.qc:2820 spends a paragraph refusing to make.

	  NO QUERY IS RECORDED on this path, so accepting the terms makes the board
	  work on the very next frame rather than needing a manual refresh.
	*/
	if (ui_consent_ver < FS_TERMS_ONLINE)
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
	{
		ob_state = OBS_NOTERMS;
		return FALSE;
	}

	dir = cvar_string("lobby_dir");
	if (dir == "")
	{
		ob_state = OBS_NODIR;
		return FALSE;
	}

	/*
	  serverkey("map") and NOT the `mapname` global -- cl_board.qc:1078 records
	  why: in CSQC that global reads wrong.  Four other files in this VM take
	  the same route for the same reason.
	*/
	mname = serverkey("map");
	if (mname == "")
		return FALSE;

	Online_FreeQuery();
	ob_q_map   = strzone(mname);
	ob_q_tier  = strzone(tier);
	ob_q_style = strzone(style);
	ob_q_track = track;
	ob_q_leg   = leg;
	ob_q_zoned = TRUE;

	/*
	  uri_escape on the map name even though every name in the library is
	  [a-z0-9_], because this string reaches a URL and the library is not the
	  only source of map names -- a custom map with a '+' or a '&' in it would
	  otherwise silently query a different board, or a malformed one.  The same
	  reasoning sv_lobby.qc's heartbeat uses for the map field.
	*/
	url = sprintf("%s/api/board?map=%s&track=%g&leg=%g&tier=%s&style=%s&limit=%g",
	              dir, uri_escape(mname), track, leg,
	              uri_escape(tier), uri_escape(style), OB_MAXROW);

	/*
	  A NEW REQUEST ABANDONS THE OLD ONE rather than queueing behind it.  The
	  reply to the old one still arrives and is dropped by the reqid test in
	  the callback.  That is the right behaviour for a board the player is
	  clicking around: the most recent click is the one they are waiting on.
	*/
	ob_req = ob_req + 1;
	if (!uri_get(url, ob_req))
	{
		ob_state = OBS_FAIL;
		ob_code  = 0;
		ob_retry_at = cltime + OB_RETRY_SECS;
		return FALSE;
	}

	ob_state = OBS_FETCH;
	ob_sent  = cltime;          // the deadline Online_Need enforces
	return TRUE;
};

/*
  Parse one /api/board body.

  Written against the GRAMMAR surfd/README.md documents, not against surfd.py,
  for the same reason tools/reccheck.py was written from the .rec grammar: a
  reader built from the writer agrees with the writer's bugs.

  Handle 0 is a valid null node (sh_json.qc's header, property 1): every
  accessor maps it to a static json_null, so a walk down a path that does not
  exist produces 0 at the end rather than needing a check at every level.  That
  is why there are so few null tests here and it is deliberate, not sloppy.
*/
void(string body) Online_Parse =
{
	local float root, rows, counts, row, n, i;
	local string s;

	root = json_parse(body);
	if (!root)
	{
		// Not OBS_FAIL with the rows cleared: see Online_Clear's note.  A
		// body we cannot parse is a bad poll, not a reason to blank a board.
		ob_state = OBS_FAIL;
		ob_code  = -1;
		ob_retry_at = cltime + OB_RETRY_SECS;   // -1 is transient by nature
		return;
	}

	if (!ob_bname)
		ob_bname = buf_create();
	if (!ob_bplayer)
		ob_bplayer = buf_create();

	Online_Clear();

	counts = json_find_object_child(root, "counts");
	ob_cnt_ranked    = json_get_float(json_find_object_child(counts, "ranked"));
	ob_cnt_community = json_get_float(json_find_object_child(counts, "community"));

	// The reply's own clock, which the age column is measured against.
	ob_t = json_get_float(json_find_object_child(root, "t"));

	/*
	  Label the rows with what the SERVER says it answered, not with what we
	  asked for.  They should agree -- surfd echoes the query back -- but if
	  they ever do not, the heading should describe the data on screen.  A
	  board that says "ranked" over community rows is the failure worth
	  spending four string reads to make impossible.
	*/
	Online_FreeHave();
	s = json_get_string(json_find_object_child(root, "map"));
	ob_have_map   = strzone(s == "" ? ob_q_map : s);
	s = json_get_string(json_find_object_child(root, "tier"));
	ob_have_tier  = strzone(s == "" ? ob_q_tier : s);
	s = json_get_string(json_find_object_child(root, "style"));
	ob_have_style = strzone(s == "" ? ob_q_style : s);
	ob_have_track = json_get_float(json_find_object_child(root, "track"));
	ob_have_leg   = json_get_float(json_find_object_child(root, "leg"));
	ob_have_zoned = TRUE;

	rows = json_find_object_child(root, "rows");
	n = json_get_length(rows);
	if (n > OB_MAXROW)
		n = OB_MAXROW;          // asked for OB_MAXROW; believe nothing

	for (i = 0; i < n; i = i + 1)
	{
		row = json_get_child_at_index(rows, i);

		ob_rank[i]  = json_get_float(json_find_object_child(row, "r"));
		ob_ticks[i] = json_get_float(json_find_object_child(row, "ticks"));
		ob_ms[i]    = json_get_float(json_find_object_child(row, "ms"));
		ob_flags[i] = json_get_float(json_find_object_child(row, "flags"));
		/*
		  HERTZ, as surfd stores it -- NOT seconds per tick.  Kept in the
		  server's units and converted at the point of use, so there is exactly
		  one place that knows about the inversion (Online_Status) rather than
		  a silent convention spread across the file.
		*/
		ob_rate[i]  = json_get_float(json_find_object_child(row, "rate"));
		if (ob_rate[i] <= 0)
			ob_rate[i] = 1 / PM_TICK;   // a row with no rate: the shipped one

		ob_wrow[i]  = json_get_float(json_find_object_child(row, "when"));

		bufstr_set(ob_bname,   i, json_get_string(json_find_object_child(row, "name")));
		bufstr_set(ob_bplayer, i, json_get_string(json_find_object_child(row, "player")));
	}
	ob_n = n;

	/*
	  json_free MUST only be called on the root (sh_json.qc: it maps to
	  PF_memfree).  Freeing a child would hand the allocator an interior
	  pointer.
	*/
	json_free(root);

	ob_state = OBS_OK;
	ob_code  = 0;
	ob_when  = cltime;
	ob_retry_at = 0;            // it worked; nothing is owed a retry
};

/*
  CSQC's one URI_Get_Callback.  See trap 2 at the top: the engine finds this by
  name and there can be exactly one, so a second consumer of uri_get in this
  VM must branch here rather than declare its own.
*/
void(float reqid, float responsecode, string resourcebody) URI_Get_Callback =
{
	if (reqid != ob_req)
		return;                 // a board we have already replaced, or not ours

	ob_sent = 0;                // it landed; the deadline no longer applies

	// TRAP 1.  0 is success; the engine rewrote 200 to 0 for DP compat.
	if (responsecode)
	{
		ob_state = OBS_FAIL;
		ob_code  = responsecode;
		// One re-ask later, but only for a code that means "later" -- see
		// Online_Retryable.  A 404 is an answer and is not asked again.
		ob_retry_at = Online_Retryable(responsecode) ? cltime + OB_RETRY_SECS : 0;
		return;
	}

	Online_Parse(resourcebody);
};

/*
===========================================================================
  What the tabs ask -- build 64 stage 2

  cl_scores.qc drives all of this, once per drawn frame, and these three are
  the whole interface between the two files.  They live here rather than there
  because every one of them reads ob_q_* or ob_have_*, and the distinction
  between those two is the trap this file exists to keep straight (point 3 at
  the top).  A draw loop that compared the wrong one would render the previous
  leg's times under this leg's heading.
===========================================================================
*/

/*
  Do the STORED rows describe this board?  ob_have_*, i.e. what the server said
  it answered -- never ob_q_*, which is only what was last asked for.

  The tab that is on screen calls this to decide whether to draw rows or to say
  it is still waiting.  While a fetch for a DIFFERENT leg is in flight this is
  FALSE, which is correct: the rows in memory are the old leg's.
*/
float(float track, float leg, string tier, string style) Online_Describes =
{
	if (ob_state != OBS_OK || !ob_have_zoned)
		return FALSE;
	return (ob_have_map   == serverkey("map") &&
	        ob_have_track == track && ob_have_leg == leg &&
	        ob_have_tier  == tier  && ob_have_style == style);
};

/*
  Ask for this board if nobody has asked for it yet.  Called every frame the
  board is open, so the guard is the whole function.

  THE GUARD IS ob_q_*, NOT ob_have_*, AND THAT IS THE ANTI-HAMMER PROPERTY.  A
  request that FAILED still recorded what it asked for, so a leaderboard that
  is down gets exactly one request per leg the player clicks on -- not one per
  frame for as long as they leave the board open.  Retrying is the refresh
  chip's job, because a retry the player did not ask for is indistinguishable
  from a retry loop.

  The two cases that DO retry by themselves are the two that self-heal and cost
  nothing to re-test: no lobby_dir and no map.  Online_Fetch returns before
  recording the query in both, so setting lobby_dir or loading a map makes the
  board work on the next frame rather than on the next click.
*/
float(float track, float leg, string tier, string style) Online_Need =
{
	if (ob_state == OBS_FETCH)
	{
		/*
		  THE DEADLINE, because nothing under us has one -- see OB_DEADLINE.
		  Without it a single request that is never answered wedges every
		  board on the panel for the rest of the session, and the only way
		  out a player would ever find is the refresh chip.

		  Written off rather than cancelled: there is no way to abort a
		  uri_get, so the reply may still land.  It is dropped harmlessly by
		  the reqid test in URI_Get_Callback, which is what that test is for.
		*/
		if (ob_sent > 0 && cltime - ob_sent > OB_DEADLINE)
		{
			ob_state = OBS_FAIL;
			ob_code  = 0;
			ob_sent  = 0;
			ob_retry_at = cltime + OB_RETRY_SECS;
		}
		return FALSE;                   // one in flight; let it land
	}

	if (ob_q_zoned)
	if (ob_q_map   == serverkey("map") &&
	    ob_q_track == track && ob_q_leg == leg &&
	    ob_q_tier  == tier  && ob_q_style == style)
	{
		/*
		  Already asked for exactly this -- so normally, nothing to do.

		  THE ONE EXCEPTION IS A TRANSIENT FAILURE THAT HAS AGED OUT.  The
		  guard above is the anti-hammer property and it is right for an
		  answer; it is wrong for a 429, which the board now gets by design
		  whenever the directory is busy.  One re-ask, then the deadline is
		  cleared, so a board that keeps failing still costs one request per
		  OB_RETRY_SECS and never one per frame.
		*/
		if (ob_state == OBS_FAIL && ob_retry_at > 0 && cltime >= ob_retry_at)
		if (Online_Retryable(ob_code))
		{
			ob_retry_at = 0;
			return Online_Fetch(track, leg, tier, style);
		}
		return FALSE;
	}

	return Online_Fetch(track, leg, tier, style);
};

/*
  How long ago row `i` was set, in one short word.

  Server minus server: `ob_t` is the clock of the reply and `when` is the clock
  of the submission, so this machine's own date never enters into it.  See
  ob_t's declaration for why the finest bucket is two minutes wide -- both
  numbers sit on a 128-second grid once a QC float has held them, and a
  seconds-accurate age is simply not recoverable from them.
*/
string(float i) Online_AgeString =
{
	local float a;

	if (i < 0 || i >= ob_n || ob_t <= 0 || ob_wrow[i] <= 0)
		return "";

	a = ob_t - ob_wrow[i];
	if (a < 120)        return "now";           // and see the grid note above
	if (a < 3600)       return sprintf("%gm", floor(a / 60));
	if (a < 86400)      return sprintf("%gh", floor(a / 3600));
	if (a < 86400 * 365) return sprintf("%gd", floor(a / 86400));
	return sprintf("%gy", floor(a / (86400 * 365)));
};

/*
  WHY a row is not on the ranked board, in the row's own words, or "" when the
  run itself says nothing.

  Two bits demote a run without accusing anyone of anything -- TF_NOJOURNAL
  (build 58) and TF_NORULESET (build 62) -- and both are deliberately NOT taint
  classes: they describe a hole in the CERTIFICATION, not something the player
  did.  So this is a separate column from `run`, which keeps saying clean or
  segmented, and the two never contradict each other.

  "" IS THE HONEST ANSWER FOR MOST COMMUNITY ROWS.  A run set on a server that
  holds no key is community because of the SERVER, and the run carries no bit
  saying so -- inventing a reason here would be putting words in its mouth.
*/
string(float i) Online_WhyString =
{
	if (i < 0 || i >= ob_n)
		return "";
	// Journal first: no journal is no evidence at all, where an unlocked
	// ruleset is evidence that has not been certified.  A run can carry both.
	if (ob_flags[i] & TF_NOJOURNAL) return "no journal";
	if (ob_flags[i] & TF_NORULESET) return "no ruleset";
	return "";
};

/*
  One line saying what the online board currently holds.  This is the whole
  headless test surface -- the same argument build 58 and Patch 313 both
  landed on: when a scripted test needs an artefact only the UI produces, add
  a report line instead of chasing the UI.
*/
void() Online_Status =
{
	local float i;
	local string word;

	     if (ob_state == OBS_IDLE)    word = "idle";
	else if (ob_state == OBS_FETCH)   word = "fetching";
	else if (ob_state == OBS_OK)      word = "ok";
	else if (ob_state == OBS_NODIR)   word = "no lobby_dir";
	else if (ob_state == OBS_NOTERMS) word = "terms not accepted";
	else                              word = "failed";

	print(sprintf("^5online board:^7 %s", word));
	if (ob_state == OBS_FAIL)
	{
		print(sprintf(" (code %g)", ob_code));
		// Whether it will ask again, and when.  The difference between a
		// board that is waiting and one that has given up is invisible
		// otherwise, and it is the first thing anyone debugging this asks.
		if (ob_retry_at > 0)
			print(sprintf(", retrying in %gs", ceil(ob_retry_at - cltime)));
		else
			print(", not retrying");
	}
	print("\n");

	if (ob_state == OBS_NOTERMS)
	{
		print("  the online terms have not been accepted, so nothing was "
		      "asked.\n  Accept them from the main menu; play stays unranked "
		      "until you do.\n");
		return;
	}

	if (ob_state == OBS_NODIR)
	{
		print("  lobby_dir is empty -- this install is not pointed at a "
		      "directory.\n  Set it with: lobby_dir \"http://host:8084\"\n");
		return;
	}

	if (ob_have_zoned)
		print(sprintf("  board: %s track %g leg %g  tier %s  style %s\n",
		              ob_have_map, ob_have_track, ob_have_leg,
		              ob_have_tier, ob_have_style));

	print(sprintf("  rows %g   ranked %g   community %g\n",
	              ob_n, ob_cnt_ranked, ob_cnt_community));

	/*
	  1/rate, AND THE INVERSION IS THE POINT.  Two different units meet here and
	  both are called "tickrate":

	    surfd's `rate` is HERTZ.  Its millis = ticks * 1000 / tickrate, and the
	    submission bound is 1..10000, so 66.6667 is what goes on the wire.
	    sh_time.qc's Time_TickString parameter is SECONDS PER TICK, despite the
	    name -- its body is ms = ticks * tickrate * 1000, the same units as
	    pm_ticrate, which ships as 0.015.

	  Handing one to the other printed 3500 ticks as 64:48:53.328 instead of
	  0:52.500 -- caught by b64board.cfg, which registered the expected times
	  before the run.  A units error of 4444x is obvious in a log; the same
	  error on a leaderboard row beside a correct rank would just look like the
	  clock being broken.
	*/
	/*
	  EIGHT ARGUMENTS INCLUDING THE FORMAT, WHICH IS THE CEILING.  A QC call
	  passes at most MAX_PARMS=8, so the age and the reason are combined into
	  one string above the call rather than passed as two -- a ninth would be
	  dropped by the calling convention rather than refused by the compiler,
	  and a status line silently missing its last column is the kind of defect
	  this whole function exists to prevent.
	*/
	for (i = 0; i < ob_n; i = i + 1)
	{
		word = Online_WhyString(i);
		if (word != "")
			word = strcat(Online_AgeString(i), " ", word);
		else
			word = Online_AgeString(i);

		print(sprintf("   %3g  %-20s %10s  ticks %g @ %.6g Hz  flags %g  %s\n",
		              ob_rank[i], bufstr_get(ob_bname, i),
		              Time_TickString(ob_ticks[i], 1 / ob_rate[i]),
		              ob_ticks[i], ob_rate[i], ob_flags[i], word));
	}
};

/*
  Console commands, registered in cl_main.qc beside the others.

      board_fetch [track] [leg] [tier] [style]
      board_status

  They exist so the network path is testable from a cfg on a headless launch,
  before any of it is wired to a tab -- and they stay afterwards, because a
  report line is how this tree verifies anything a config cannot click.
*/
void() Online_RegisterCommands =
{
	registercommand("board_fetch");
	registercommand("board_status");
};

float(string cmd) Online_ConsoleCommand =
{
	local float track, leg;
	local string tier, style;

	/*
	  argv(0) is the command, not `cmd` -- the engine has already tokenized by
	  the time CSQC_ConsoleCommand runs, which is the idiom every other handler
	  in this VM uses (cl_scores.qc:1199).  There is no argv_count() here, so a
	  missing argument is tested as "" rather than counted.
	*/
	if (argv(0) == "board_status")
	{
		Online_Status();
		return TRUE;
	}

	if (argv(0) == "board_fetch")
	{
		track = (argv(1) != "") ? stof(argv(1)) : 0;
		leg   = (argv(2) != "") ? stof(argv(2)) : 0;
		tier  = (argv(3) != "") ? argv(3) : "ranked";
		style = (argv(4) != "") ? argv(4) : "clean";

		if (Online_Fetch(track, leg, tier, style))
			print(sprintf("^5online board:^7 asked %s for %s track %g leg %g "
			              "(%s/%s)\n", cvar_string("lobby_dir"),
			              serverkey("map"), track, leg, tier, style));
		else
			Online_Status();
		return TRUE;
	}

	return FALSE;
};
