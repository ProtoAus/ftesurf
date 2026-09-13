/*
===========================================================================
  m_lobby.qc -- the public-lobby list, client side.  Patch 270, Stage 6a.

  Polls a small directory service (surfd) for the lobbies that are live right
  now and holds the answer for the map picker to draw.  Data only: nothing in
  here draws, because the row drawing needs ui_thumb and the ms_name map list,
  both of which live in m_main.qc -- and m_main.qc compiles AFTER this file.
  So the dependency runs one way only: m_main.qc reads Lob_*, this file reads
  nothing of m_main.qc's.

  OFF BY DEFAULT, AND THAT IS A CONSENT DECISION RATHER THAN CAUTION.

  The terms version 1 showed people said, verbatim: "Nothing is sent anywhere.
  FTESurf has no server to send it to and no code that uploads anything."
  Polling a directory makes that false -- an HTTP GET discloses the player's IP
  address to whoever runs it, which is a small thing but it is not nothing, and
  it is exactly the kind of small thing a promise like that is supposed to
  cover.

  ONE SWITCH, and it is the one with words on it.

  There were two.  lobby_dir shipped empty, so a player had to be told a URL
  before anything worked, and that was described as a safety property.  It was
  not one: a cvar nobody has heard of is not a decision anybody made.  It now
  ships pointing at a directory (see Lob_Init) and the typing step is gone.

  The switch that remains is FS_TERMS_ONLINE.  The terms text now covers lobbies in their
  own paragraph, and every path here that would contact a server requires an
  acceptance at that tier -- the JOIN in ui_connect, and the POLL below, which
  needs its own gate because it discloses an IP merely from opening the map
  picker.  A version-1 player is not force-marched through it: they keep
  playing offline, and see one row explaining why the list is empty (see
  Lob_Blocked).  The reasoning for a second tier rather than bumping
  FS_TERMS_VERSION is at that define in sh_defs.qc.

  NAMING: everything here is lb_ / Lob_, grepped against the whole tree before
  the file existed.  QuakeC has no file scope and fteqcc merges same-named
  globals from different files silently, with no diagnostic -- see the essay
  at the top of sv_lobby.qc for the feature this project has already lost to
  precisely that.
===========================================================================
*/

/*
  FIVE, because that is how many lobbies there are: surf tiers 1-3 on
  27510/27520/27530 and bhop easy and hard on 27540/27550 (cfg/lobby1..5.cfg).

  It was three, "because three is what fits above the map list without pushing
  the list itself off the bottom at 1280x720".  That was true while the lobbies
  were stacked a row each, and stopped being true when Patch 287 put them side
  by side: one row of cells costs the list one ROW_H whether it holds three or
  five.  What five costs instead is WIDTH, and m_main.qc's create panel widens
  to 1400 to pay it -- see the essay over the cells in screen_create.

  The directory may return more.  Lob_Parse keeps the five with the LOWEST
  PORTS, so the extras are dropped here rather than drawn somewhere
  unreachable, and which five are shown does not change as players move.

  ---- BUILD 67: THIS IS THE PARSE CAP, AND IT IS NO LONGER THE DRAW CAP. ----

  Everything above is about how many lobby CELLS fit above the map list, and it
  is still true of the cells.  It stopped being the right bound for the LIST the
  moment build 66 shipped ui_map_players, because that feature does not draw
  lobbies at all -- it walks Lob_Count() and sums the players on each map, to
  put a count beside the map's name in the picker.

  So a cap of five silently became a WRONG ANSWER rather than a smaller one.
  Grow the fleet past five and a map hosted on lobby 6 reports no players; not
  "unknown", which the build-65 silence rule would have drawn as nothing, but
  the same -1 that means "no lobby is on this map".  Eight people would be
  playing a map the picker describes as empty, and nothing anywhere would log a
  word about it.  The two caps had been the same number for so long that the
  second one was never named.

  SIXTY-FOUR, BECAUSE THAT IS surfd's OWN PLANNED CEILING.  surfd.py sets
  CLUSTER_NODES_PLANNED = 64 and sizes RATE_MAX_TRUSTED off it, deliberately
  "well past the RAM ceiling", so 64 is the number the directory is already
  built to serve.  A client cap BELOW the server's planned ceiling is exactly
  the invisible under-count described above, so the two numbers have to be read
  together: if that one moves, this one moves with it.

  WHAT IT COSTS, MEASURED RATHER THAN ASSERTED: 12 BYTES.  menu.dat is 200,678
  at LB_MAX 5 and 200,690 at 64 -- same tree, same compiler, so the widening is
  the changed literal and essentially nothing else.  That was worth compiling
  both ways rather than reasoning about, because this tree has the OPPOSITE
  result on record: four extra recorder rings once cost 563 KB of progs for
  68 KB of data, and the note that left says to split a cap before widening it.
  It does not apply here, and the reason is structural -- these rows are
  parallel STRBUFS that grow on demand (lb_map, lb_addr, ... below), not QC
  arrays, so there is no per-element storage for fteqcc to multiply and an empty
  fleet allocates nothing at all.  What it does cost is
  Lob_Parse's insertion sort, which is O(held x returned) with a string parse in
  the inner test: five lobbies is ~25 of those per poll, sixty-four is ~4096.
  Polls are seconds apart and menuqc is not the frame budget, so that is
  affordable -- but it is the term that would bite first if this number grew
  again, and the fix then is to sort once rather than to shrink the cap back.

  THE CELLS ARE BOUNDED SEPARATELY, in m_main.qc's screen_create, by grid ROWS
  rather than by cell count -- see LOB_ROWS_MAX there.  Bounding them here as
  well would restore this bug in a second place.
*/
#define LB_MAX 64

/*
  Parallel strbufs, the same shape the map list itself uses (ms_name / ms_src /
  ms_meta).  Declared bare with no initialiser deliberately: fteqcc folds an
  initialised global scalar into a constant and then refuses assignment to it
  (Q106), which is why every buffer in m_main.qc is seeded at runtime too.
*/
strbuf lb_map;                  // map name, e.g. surf_borderlands
strbuf lb_addr;                 // "ip:port", ready for connect
strbuf lb_playv;               // players, as text
strbuf lb_maxv;                 // slots, as text
strbuf lb_name;                 // the server's hostname
strbuf lb_roww;                 // cached ms_name index, filled in by the drawer

float  lb_count;                // rows actually held, 0..LB_MAX
float  lb_ready;                // a reply has been parsed at least once
float  lb_next;                 // time of the next poll
float  lb_req;                  // uri request id, so a stale reply is ignored
float  lb_fail;                 // consecutive failures, for the backoff
float  lb_lastcode;             // last status, so a broken poll logs once

/*
  THE DIRECTORY, AND MOVING INSTALLS THAT ALREADY SAVED THE OLD ONE.

  lobby_dir is CVAR_ARCHIVE.  registercvar does not overwrite a cvar that
  already exists, and ftesurf.cfg on every existing install holds
  `seta lobby_dir "http://192.168.1.102:8084"` from the first time the menu
  ran.  So changing the default above moves new installs and nobody else --
  which is backwards, because the people who need moving are precisely the ones
  who already have the game.

  A GENERATION COUNTER, NOT AN UNCONDITIONAL WRITE.  lobby_dir_gen records
  which migration this install has seen.  When it is behind, and ONLY if the
  saved value is still one this project shipped as a default, the value is
  rewritten.  A directory somebody typed themselves is left alone: overwriting
  a deliberate choice on upgrade is how a config migration becomes a bug
  report, and there is no way for them to tell it happened.

  `seta`, not cvar_set.  The full argument is at the top of cl_hudedit.qc; the
  short version is that Cmd_set_f's not-from-gamecode branch (cmd.c:4266) is
  the only path that puts CVAR_ARCHIVE on a cvar, so a plain cvar_set here
  would change the value for this session and forget it on quit -- and the
  migration would then run again, forever, looking like it had never worked.

  Add to FS_LOBBY_DIR_OLD, never remove: it is the list of values that are safe
  to overwrite, so a value dropped from it becomes a value that gets stranded.
*/
#define FS_LOBBY_DIR_DEFAULT "https://play.proto.bar"
#define FS_LOBBY_DIR_GEN     1

float(string a) Lob_WasShippedDefault =
{
	if (a == "") return TRUE;                       // never set, safe to fill
	if (a == "http://192.168.1.102:8084") return TRUE;   // gen 0, the LAN Pi
	if (a == FS_LOBBY_DIR_DEFAULT) return TRUE;
	return FALSE;
};

void() Lob_MigrateDir =
{
	local string cur;

	if (cvar("lobby_dir_gen") >= FS_LOBBY_DIR_GEN)
		return;

	cur = cvar_string("lobby_dir");
	if (Lob_WasShippedDefault(cur))
	{
		if (cur != FS_LOBBY_DIR_DEFAULT)
		{
			localcmd(strcat("seta lobby_dir \"", FS_LOBBY_DIR_DEFAULT,
			                "\"\n"));
			print(strcat("^3lobby directory moved to ",
			             FS_LOBBY_DIR_DEFAULT, "^7\n"));
		}
	}
	else
	{
		// Somebody set their own.  Say so once, so that a player who wonders
		// why they see no lobbies has the reason in front of them rather than
		// having to guess that an old cvar is shadowing the new default.
		print(strcat("^3lobby_dir is set to ", cur,
		             "^3 -- leaving it alone.  Reset it with: lobby_dir \"",
		             FS_LOBBY_DIR_DEFAULT, "\"^7\n"));
	}

	// Stamped whichever branch ran, so this is a one-shot either way.
	// ftos rather than a second "1" constant: two constants that must agree is
	// a drift waiting to happen, and the drift would re-run the migration on
	// every launch.
	localcmd(strcat("seta lobby_dir_gen \"", ftos(FS_LOBBY_DIR_GEN), "\"\n"));
};

void() Lob_Init =
{
	lb_map   = buf_create();
	lb_addr  = buf_create();
	lb_playv = buf_create();
	lb_maxv  = buf_create();
	lb_name  = buf_create();
	lb_roww  = buf_create();

	/*
	  SHIPPED WITH A DEFAULT, and the empty string is no longer the off switch.

	  It was empty, and the player had to be told a URL to type.  That is a bad
	  shape for a consent control and it was never doing the job it looked like
	  it was doing: a cvar nobody knows about is not a decision anybody made, it
	  is just a feature that does not work.  The real gate is FS_TERMS_ONLINE,
	  which is a screen with words on it, and Lob_Poll tests that FIRST -- before
	  it so much as reads this cvar.  So nothing is sent before an acceptance
	  either way, and removing the typing step removes no protection.

	  The consequence to be aware of: Lob_Blocked is now true for every player
	  who has not accepted the online tier, where before it was true only for
	  the handful who had set this by hand.  So the map picker grows one row
	  advertising lobbies, for everybody, until they answer.  That is on purpose
	  -- it is the only route to the question -- but it is a visible change to a
	  screen that every player sees, so it is written down here rather than
	  discovered.

	  A REAL HOSTNAME NOW, not the LAN placeholder it shipped with.  The old
	  value was http://192.168.1.102:8084 -- the Pi on the developer's own
	  network, unreachable and unresolvable for anybody else, which meant a
	  stranger's install polled a private address forever and showed an empty
	  lobby list with no way to fix it.  That is the whole reason this default
	  moved.

	  CVAR_ARCHIVE IS WHY THIS NEEDED A MIGRATION AND NOT JUST AN EDIT.  This
	  file said so before the change was made: registercvar declines to touch a
	  cvar that already exists, and every install that has ever run this menu
	  has ftesurf.cfg holding `seta lobby_dir "http://192.168.1.102:8084"`.
	  Editing the default alone would move NOBODY -- the people who already
	  have the game, which is everyone this is for.  See Lob_MigrateDir below.

	  32 is CVAR_ARCHIVE, so having opted in once you stay opted in.  The
	  literal rather than the name because the constant is declared in
	  defs/cl_defs.qc:1034 and menu/m_defs.qc has never had it; these are DP's
	  flag numbers, which PF_registercvar translates (pr_bgcmd.c:2017-2028), and
	  they are NOT the engine's own CVAR_* values.
	*/
	registercvar("lobby_dir",  FS_LOBBY_DIR_DEFAULT, 32);
	registercvar("lobby_poll", "6", 32);
	registercvar("lobby_dir_gen", "0", 32);
	Lob_MigrateDir();

	/*
	  lobby_hosts IS NOT REGISTERED HERE, and looking for it here is the
	  expected mistake -- it is the third lobby_ cvar and this is where the
	  other two live.  It is registered in m_main.qc, immediately above the
	  only function that reads it, because cvar_string() on an unregistered
	  name auto-creates it as "" and a later registercvar() declines to
	  overwrite that.  An empty lobby_hosts reads as "allow-list disabled", so
	  losing that race would silently switch the protection off rather than
	  fail loudly.  See the essay over ui_host_allowed.
	*/
};

// Accessors, so m_main.qc never touches the buffers directly and the storage
// can change without touching the drawing.
float()          Lob_Count   = { return lb_count; };
float()          Lob_Ready   = { return lb_ready; };
string(float i)  Lob_Map     = { return bufstr_get(lb_map,   i); };
string(float i)  Lob_Addr    = { return bufstr_get(lb_addr,  i); };
string(float i)  Lob_Name    = { return bufstr_get(lb_name,  i); };
float(float i)   Lob_Players = { return stof(bufstr_get(lb_playv, i)); };
float(float i)   Lob_Max     = { return stof(bufstr_get(lb_maxv,  i)); };

/*
  The lobby's name as a cell can afford to draw it.  Build 57.

  lb_name was fetched from the first poll and never drawn: the cells showed the
  map, so five lobbies on the same map were five identical cells.  Every lobby
  this project runs is called "FTESurf -- <what it is>" (the hostname line in
  cfg/lobby1..5.cfg), so in a row of five the first eleven characters would say
  the same thing five times, in the ~140 px a cell has for text at 1280 wide.

  Stripped ONLY when the name starts with exactly that, case aside: a lobby
  somebody else runs keeps its name whole, because there is no other way to
  tell it from ours.  surfd fills an empty hostname with the node id before it
  publishes one, so the address fallback is for a directory that does not.
*/
#define LB_NAME_PREFIX "ftesurf -- "

string(float i) Lob_Title =
{
	local string s;
	local float n, pl;

	s  = bufstr_get(lb_name, i);
	n  = strlen(s);
	pl = strlen(LB_NAME_PREFIX);
	if (n > pl)
		if (strtolower(substring(s, 0, pl)) == LB_NAME_PREFIX)
			s = substring(s, pl, n - pl);

	if (s == "")
		s = bufstr_get(lb_addr, i);
	return s;
};

/*
  The map-list index for a lobby's map, cached by the drawer.

  -2 means "not looked up yet", -1 means "looked up, not installed here".  The
  distinction matters: -1 is a real answer that gets drawn as a greyed row
  saying so, and re-scanning 2200 map names every frame to re-discover it would
  be the one expensive thing on this screen.
*/
float(float i)          Lob_Row    = { return stof(bufstr_get(lb_roww, i)); };
void(float i, float v)  Lob_SetRow = { bufstr_set(lb_roww, i, ftos(v)); };

/*
  "You have asked for lobbies, and consent is what is stopping you."

  Needed because the two gates together would otherwise be a dead end: the poll
  is refused without FS_TERMS_ONLINE, so lb_count stays 0, so no lobby row is
  ever drawn, so ui_connect -- the thing that would have offered the terms --
  is unreachable.  A player who set lobby_dir would get silence and no way to
  find out why, which is a worse failure than the one the gate prevents.

  The lobby_dir test used to mean "only nag people who asked for lobbies".  With
  a default shipped it is true for everybody, so the row is now shown to every
  player who has not answered the online tier.  The test is kept because
  clearing the cvar by hand is still a way to say "never show me this", and
  because it is what makes that a supported thing to do rather than an accident.
*/
float() Lob_Blocked =
{
	if (cvar_string("lobby_dir") == "")
		return FALSE;
	return (cvar("rec_terms") < FS_TERMS_ONLINE);
};

/*
  BOUNDED BY lb_count, NOT BY buf_getsize, AND THAT IS THE WHOLE FUNCTION.

  This was `while (buf_getsize(lb_map) > 0) bufstr_free(lb_map, buf_getsize(lb_map)-1);`
  and it is an INFINITE LOOP.  bufstr_free does not shrink the buffer:

      // #449 void(float bufhandle, float string_index) bufstr_free
      if (strbuflist[bufno].strings[index])
          Z_Free(strbuflist[bufno].strings[index]);
      strbuflist[bufno].strings[index] = NULL;

  -- pr_bgcmd.c:5602-5624, and there is no `used--` anywhere in it.  buf_getsize
  returns `used` (:5356-5367), so freeing the last element leaves the size
  unchanged and the loop condition is true forever.  The engine's runaway
  detector fires, dumps menucore.txt and takes the menu progs down: from the
  player's side the game dies on the map picker.

  SO IT CANNOT HAVE WORKED ONCE THE LIST WAS EVER NON-EMPTY.  The first poll of
  a session clears nothing (used is 0, the loop does not run) and populates
  the rows; the SECOND poll, lobby_poll seconds later, hangs.  That is why it
  reads as "open the picker, wait a bit, crash" rather than as a bad reply --
  the reply was fine, and Lob_Parse never got to look at it.

  THE PROJECT ALREADY KNEW THIS.  m_main.qc:1348-1351, on the map list's own
  compaction, says outright: "bufstr_free's contract about whether the buffer
  actually shrinks is not worth depending on for a compaction that costs
  nothing this way", and just moves ms_count.  This file then depended on it.
  The note was in the right place and the wrong file.

  The count is now the only authority, exactly as ms_count is: every read here
  goes through Lob_Count(), the writes in Lob_Parse are index-addressed, and
  whatever the buffer's high-water mark happens to be is nobody's business.
  The bufstr_free calls stay -- they release the strings, which matters when
  the reason for clearing is that consent was withdrawn -- they just no longer
  drive the loop.
*/
void() Lob_Clear =
{
	local float i;

	for (i = 0; i < lb_count; i = i + 1)
	{
		bufstr_free(lb_map,   i);
		bufstr_free(lb_addr,  i);
		bufstr_free(lb_playv, i);
		bufstr_free(lb_maxv,  i);
		bufstr_free(lb_name,  i);
		bufstr_free(lb_roww,  i);
	}
	lb_count = 0;
};

/*
  Parse one /lobbies.json body.

  Leans on the two properties sh_json.qc's header spells out, and would be much
  longer without them: handle 0 is a valid null node, so a path that does not
  exist yields 0 at every level and needs no null checks; and strings out of a
  node are reference-tracked tempstrings, so they survive until bufstr_add has
  copied them without a strzone/strunzone dance.

  json_free is called on the ROOT only -- that is the documented rule, the
  builtin is PF_memfree underneath, and freeing a child would be a double free.

  SORTED BY PORT, build 57, and the directory's own order is thrown away on
  purpose.  surfd lists lobbies busiest first, which is a fine order for a list
  somebody reads top to bottom and a bad one for five cells in a row: every
  time a player joined one lobby, the cells would swap places under the cursor
  between two polls, and a click aimed at "tier 2" would land on whichever
  lobby had just slid into that slot.  The port is fixed per lobby
  (27510..27550 is tier 1..bhop hard), so ordering by it pins every lobby to
  one cell for as long as it is up.

  INSERTED IN PLACE, not collected and sorted afterwards.  The buffers are
  index-addressed and lb_count is the only authority on how many rows exist
  (see Lob_Clear), so a row goes straight to the slot it will be read from and
  the rows above it move down one with bufstr_set.  At five rows that is at
  most four copies a row, once per poll.  When all five are held, a row with a
  lower port pushes the highest one out, so the set kept is the five lowest
  ports rather than the first five the directory happened to send -- which
  would otherwise be the five busiest, and change as people moved.
*/

// Sorts after every real port, so a row with no parseable port is the first
// to be dropped when there are more rows than cells.
#define LB_PORT_NONE 65536

/*
  The port half of "host:port", or LB_PORT_NONE.

  FIRST colon, for the reason ui_host_of in m_main.qc gives: bracketed IPv6 is
  refused on both sides, so a colon is always the port separator.  That function
  cannot be called from here -- m_main.qc compiles after this file -- so this is
  the port-side twin rather than a second copy of the host side.
*/
float(string a) Lob_PortOf =
{
	local float p, v;

	p = strstrofs(a, ":");
	if (p < 0)
		return LB_PORT_NONE;
	v = stof(substring(a, p + 1, strlen(a) - p - 1));
	if (v < 1 || v > 65535)
		return LB_PORT_NONE;
	return v;
};

// One row of every lb_ buffer, copied.  All six, so a buffer added later
// without a line here is the only way a moved row can arrive half-moved.
void(float from, float to) Lob_CopyRow =
{
	bufstr_set(lb_map,   to, bufstr_get(lb_map,   from));
	bufstr_set(lb_addr,  to, bufstr_get(lb_addr,  from));
	bufstr_set(lb_name,  to, bufstr_get(lb_name,  from));
	bufstr_set(lb_playv, to, bufstr_get(lb_playv, from));
	bufstr_set(lb_maxv,  to, bufstr_get(lb_maxv,  from));
	bufstr_set(lb_roww,  to, bufstr_get(lb_roww,  from));
};

void(string body) Lob_Parse =
{
	local int root, arr, o;
	local float n, i, k, at, port;
	local string m, ad;

	Lob_Clear();

	root = json_parse(body);
	if (!root)
	{
		// A non-JSON body is a real outcome, not an impossible one: a captive
		// portal or a misconfigured proxy answers 200 with HTML.  Treated as a
		// failed poll so the backoff applies, rather than as an empty list.
		lb_fail = lb_fail + 1;
		return;
	}

	arr = json_find_object_child(root, "lobbies");
	n   = json_get_length(arr);

	// Every row is looked at, not the first LB_MAX: a sixth row may have a
	// lower port than one already held, and that one is kept instead.
	for (i = 0; i < n; i = i + 1)
	{
		o = json_get_child_at_index(arr, i);

		m = json_get_string(json_find_object_child(o, "map"));
		if (m == "")
			continue;               // a row with no map is not drawable

		ad   = json_get_string(json_find_object_child(o, "addr"));
		port = Lob_PortOf(ad);

		// The slot: below every held row whose port is no higher than this
		// one's, so two rows on one port keep the directory's order.  An
		// explicit break rather than a compound while(): QC does not promise
		// to short-circuit &&, and the second half would read row -1.
		at = lb_count;
		while (at > 0)
		{
			if (Lob_PortOf(bufstr_get(lb_addr, at - 1)) <= port)
				break;
			at = at - 1;
		}
		if (at >= LB_MAX)
			continue;               // higher than all five held rows

		// Open the slot from the bottom up.  When all five are held, start one
		// row higher, so the row that falls off the end is the highest port.
		k = lb_count;
		if (k >= LB_MAX)
			k = LB_MAX - 1;
		while (k > at)
		{
			Lob_CopyRow(k - 1, k);
			k = k - 1;
		}

		/*
		  bufstr_SET at the slot, not bufstr_add(..., TRUE).

		  The second half of the Lob_Clear bug, and it would have outlived the
		  fix: `order` true means "append at used" (PF_bufstr_add_internal,
		  pr_bgcmd.c:5549-5556), and used is exactly the counter that nothing
		  ever decrements.  So the first reply lands at 0,1,2 and the second at
		  3,4,5 -- while Lob_Map/Lob_Players and the drawer's row loop all index
		  from 0 to Lob_Count()-1.  The list would have frozen on whatever the
		  first poll of the session happened to say, and gone on looking live.

		  Index-addressed, so a row always lands where it will be read from, and
		  the count and the storage cannot drift apart.  Build 57's port order
		  depends on exactly that: the slot is chosen above, and nothing here
		  appends.
		*/
		bufstr_set(lb_map,   at, m);
		bufstr_set(lb_addr,  at, ad);
		bufstr_set(lb_name,  at, json_get_string(json_find_object_child(o, "name")));
		bufstr_set(lb_playv, at, ftos(json_get_float(json_find_object_child(o, "players"))));
		bufstr_set(lb_maxv,  at, ftos(json_get_float(json_find_object_child(o, "max"))));
		bufstr_set(lb_roww,  at, "-2");   // unresolved; see Lob_Row

		// A full list stays full: the insert above pushed its highest row out.
		if (lb_count < LB_MAX)
			lb_count = lb_count + 1;
	}

	json_free(root);

	lb_ready = TRUE;
	lb_fail  = 0;
};

/*
===========================================================================
  ASKING THE DIRECTORY WHERE TO PLAY A MAP.  Build 67.

  WHAT IT IS FOR, AND IT IS NOT CONVENIENCE.  Picking a map starts a LISTEN
  SERVER today (ui_launch's `map <name>`), and on a listen server the host owns
  sv.time, the movement cvars, the progs and the timer -- so a world record
  there is a cvar edit rather than a cheat.  That is exactly why
  Lobby_SubmitRun refuses to submit one and why those times are Local-only.
  The plan calls it tier T3 and ranks it above every input-layer concern.

  So "every map someone plays is a lobby" is not a social feature with an
  anti-cheat side effect; it IS the anti-cheat fix, and this is the half of it
  the player touches: before starting a map locally, ask surfd whether there is
  a server for it.

  THE SHARED REQUEST COUNTER.  There is exactly one URI_Get_Callback per VM and
  the request id is the ONLY thing separating a directory poll's reply from a
  join's, so both draw from one counter and each remembers its own id.  This is
  the same shape cl_online.qc uses for the board and the replay fetch, and for
  the same reason: two independent counters can and eventually do collide.

  A SEPARATE STATE MACHINE, NOT A FLAG ON THE POLL.  Lob_Poll's backoff exists
  to stop hammering a dead directory for a browser nobody is looking at, and a
  join is the opposite kind of request -- one, now, because somebody pressed a
  button.  Sharing lb_state would also mean a join in flight made the lobby
  list read as loading, which is what cl_online.qc's Online_Need essay records
  as the cost of sharing one there.
===========================================================================
*/
#define LJ_IDLE   0
#define LJ_ASK    1
#define LJ_READY  2
#define LJ_FAIL   3

// How long to wait before giving up and playing locally.  Short, because the
// player is looking at a button they just pressed and the fallback is a map
// that starts instantly.  A directory that cannot answer in this long is a
// directory that is down, and the offline path is not a degraded experience --
// it is the game as it shipped.
#define LJ_DEADLINE 8

float  lj_state;
float  lj_req;                  // 0 when nothing is outstanding
float  lj_at;                   // when the ask went out
float  lj_code;                 // last status, for the message
float  lj_timed;                // can a run on this map even be timed?
string lj_addr;                 // strzoned
string lj_map;                  // strzoned; what we asked for
string lj_why;                  // strzoned; the directory's own word

float  lb_nextid;

float() Lob_NextReq =
{
	lb_nextid = lb_nextid + 1;
	return lb_nextid;
};

void() Lob_JoinFree =
{
	if (lj_addr) { strunzone(lj_addr); lj_addr = ""; }
	if (lj_map)  { strunzone(lj_map);  lj_map  = ""; }
	if (lj_why)  { strunzone(lj_why);  lj_why  = ""; }
};

void() Lob_JoinClear =
{
	Lob_JoinFree();
	lj_state = LJ_IDLE;
	lj_req   = 0;
	lj_at    = 0;
	lj_code  = 0;
	lj_timed = 0;
};

/*
  Parse one /api/join reply.

  EVERY FIELD IS OPTIONAL AS FAR AS THIS IS CONCERNED.  The body came off the
  network from whoever answers lobby_dir; a missing "addr" must read as a
  failure with a message, never as a connect to "".  json_get_string returns ""
  for a child that is not there, so the emptiness test below is the whole guard
  and it is deliberately on the VALUE rather than on the child pointer.
*/
void(float code, string body) Lob_JoinReply =
{
	local float  root;
	local string ad, why;

	lj_req  = 0;
	lj_code = code;

	if (code)
	{
		/*
		  A refusal still carries a sentence, and it is the useful half: "that
		  map is not installed on this server" and "every server is busy right
		  now" are different problems with different answers, and a bare status
		  code is neither.  Parsed on the failure path for exactly that reason.
		*/
		why = "";
		root = json_parse(body);
		if (root)
		{
			why = json_get_string(json_find_object_child(root, "error"));
			json_free(root);
		}
		if (why == "")
			why = sprintf("the directory returned %g", code);
		if (lj_why) strunzone(lj_why);
		lj_why   = strzone(why);
		lj_state = LJ_FAIL;
		return;
	}

	root = json_parse(body);
	if (!root)
	{
		if (lj_why) strunzone(lj_why);
		lj_why   = strzone("the directory sent something this build cannot read");
		lj_state = LJ_FAIL;
		return;
	}

	ad      = json_get_string(json_find_object_child(root, "addr"));
	why     = json_get_string(json_find_object_child(root, "why"));
	lj_timed = json_get_float(json_find_object_child(root, "timed"));
	json_free(root);

	if (ad == "")
	{
		if (lj_why) strunzone(lj_why);
		lj_why   = strzone("the directory named no server");
		lj_state = LJ_FAIL;
		return;
	}

	if (lj_addr) strunzone(lj_addr);
	if (lj_why)  strunzone(lj_why);
	lj_addr  = strzone(ad);
	lj_why   = strzone(why);
	lj_state = LJ_READY;
};

/*
  Start one ask.  Returns FALSE if there is no directory to ask, which is the
  offline case and is not an error -- the caller plays locally and says so.
*/
float(string mapname) Lob_JoinAsk =
{
	local string dir;

	/*
	  THE SAME CONSENT TIER THE POLL USES, and for the reason Lob_Poll's essay
	  gives at length: this GET discloses this machine's address to whoever runs
	  the directory.  Starting a map must not be the thing that does that behind
	  a question the player has not been asked.
	*/
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
		return FALSE;

	dir = cvar_string("lobby_dir");
	if (dir == "")
		return FALSE;

	Lob_JoinClear();
	lj_map   = strzone(mapname);
	lj_at    = time;
	lj_state = LJ_ASK;
	lj_req   = Lob_NextReq();

	// uri_escape on the name even though it came from our own directory scan:
	// it is going into a query string, and a name with a & or a = in it would
	// otherwise add fields to the request.  It costs nothing.
	uri_get(sprintf("%s/api/join?map=%s", dir, uri_escape(mapname)), lj_req);
	return TRUE;
};

/*
  Give up if nothing came back.  A uri_get that never calls back leaves the
  state at LJ_ASK forever, and the symptom is a button that does nothing --
  which is worse than an error, because there is nothing to report.
*/
void() Lob_JoinPoll =
{
	if (lj_state != LJ_ASK)
		return;
	if (time - lj_at < LJ_DEADLINE)
		return;

	lj_req   = 0;
	lj_state = LJ_FAIL;
	if (lj_why) strunzone(lj_why);
	lj_why = strzone("the directory did not answer");
};

float()  Lob_JoinState = { return lj_state; };
float()  Lob_JoinTimed = { return lj_timed; };
string() Lob_JoinAddr  = { return lj_addr ? lj_addr : ""; };
string() Lob_JoinMap   = { return lj_map  ? lj_map  : ""; };
string() Lob_JoinWhy   = { return lj_why  ? lj_why  : ""; };

/*
  The one URI_Get_Callback in the menu progs.

  The engine finds it by NAME (pr_bgcmd.c:6003) and there can be exactly one,
  so anything else that ever wants uri_get from the menu has to branch inside
  this function rather than declare its own.  Hence the reqid test rather than
  an unconditional parse: it is both the stale-reply guard and the "is this
  mine" test that a second caller would need.
*/
void(float reqid, float responsecode, string resourcebody) URI_Get_Callback =
{
	/*
	  THE JOIN IS TESTED FIRST AND ONLY WHEN ONE IS OUTSTANDING.  lj_req is 0
	  whenever nothing is in flight, and a reqid of 0 is never issued
	  (Lob_NextReq pre-increments), so an idle join can never swallow a poll's
	  reply.  Written as nested ifs rather than `if (lj_req && reqid == lj_req)`
	  because `&&` evaluates both sides in fteqcc, which is the trap recorded
	  against array guards elsewhere in this tree.
	*/
	if (lj_req)
	if (reqid == lj_req)
	{
		Lob_JoinReply(responsecode, resourcebody);
		return;
	}

	if (reqid != lb_req)
		return;                     // a reply to a poll we have already replaced

	/*
	  SUCCESS IS 0 HERE, NOT 200.  PR_uri_get_callback2 (pr_bgcmd.c:6014):

	      G_FLOAT(OFS_PARM1) = (replycode!=200)?replycode:0;
	          //for compat with DP, we change any 200s to 0.

	  Written as `responsecode != 200` first, which meant every SUCCESSFUL poll
	  was classified as a failure, the body was never parsed, and the browser
	  would have been permanently empty against a directory that was answering
	  correctly.  Left as a comment rather than quietly fixed because the same
	  wrong test is the natural thing to write in the server progs too, and it
	  is written there as well (sv_lobby.qc).
	*/
	if (responsecode)
	{
		if (responsecode != lb_lastcode)
		{
			lb_lastcode = responsecode;
			print(sprintf("^1lobby:^7 directory returned %g\n", responsecode));
		}
		lb_fail = lb_fail + 1;
		return;
	}
	lb_lastcode = 0;

	Lob_Parse(resourcebody);
};

/*
  Poll, on a timer, with a backoff.

  Called only while the map picker is open, so a player sitting in the main
  menu or in a game makes no requests at all.  The backoff exists because the
  common failure is "the directory is not running", and a fixed 6s poll against
  a dead host is a request every six seconds forever -- for a feature nobody is
  looking at.  Capped so it recovers on its own when the service comes back.
*/
void() Lob_Poll =
{
	local string dir;
	local float  per;

	/*
	  Consent gates the POLL, not just the join, and that distinction is the
	  whole reason this check is here rather than only in ui_connect.

	  A GET of /lobbies.json discloses this machine's IP address to whoever runs
	  the directory, and it happens merely from opening the map picker -- before
	  any lobby has been chosen, and with nothing on screen to suggest a server
	  was contacted.  Gating only the join would mean the first disclosure
	  happened before the question was asked, which makes the question
	  decorative.

	  Read through the `rec_terms` cvar rather than ms_consent because that
	  global lives in m_main.qc, which compiles after this file.  It is the
	  established cross-module route for exactly this -- client/cl_replay.qc
	  refuses to open a journal the same way -- and it is set from the file on
	  every boot, so it cannot drift from data/consent.txt.
	*/
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
	{
		if (lb_count)
			Lob_Clear();
		lb_ready = FALSE;
		return;
	}

	dir = cvar_string("lobby_dir");
	if (dir == "")
	{
		// Switched off.  Drop anything a previous session left so the picker
		// does not keep drawing lobbies that are no longer being refreshed.
		if (lb_count)
			Lob_Clear();
		lb_ready = FALSE;
		return;
	}

	if (time < lb_next)
		return;

	per = cvar("lobby_poll");
	if (per < 2) per = 6;
	if (lb_fail > 0)
	{
		per = per * (lb_fail + 1);
		if (per > 60)
			per = 60;
	}
	lb_next = time + per;

	// SHARED WITH THE JOIN, see Lob_NextReq.  Was `lb_req + 1`; two independent
	// counters in one VM with one callback collide the moment both are used.
	lb_req = Lob_NextReq();
	uri_get(strcat(dir, "/lobbies.json"), lb_req);
};
