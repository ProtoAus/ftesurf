/*
===========================================================================
  sv_saveloc.qc -- save states.

  A save state is a position you can come back to, plus the RUN that was in
  progress when you dropped it.  Momentum calls the position half a saveloc;
  every surf community calls it save/load.  Build 17 added the other half.

  WHAT A SAVE HOLDS, AND WHY THAT IS THE INTERESTING PART

  Until build 17 a save was five floats: origin, velocity, pitch, yaw, duck.
  Loading one teleported you and marked the run practice, and that was all --
  the clock, the splits and the checkpoints stayed at whatever they happened to
  be.  So practising the entry to stage 4 of a good run meant losing the run
  every time you failed it, which is the thing you were practising FOR.

  Now a save holds the attempt.  Load it and the clock reads what it read when
  you saved, the splits behind you are the ones you actually set, the checkpoint
  you last crossed is still crossed, and the recording carries the movement up
  to that point -- so the run you eventually finish is one continuous file from
  the start zone, not a fragment beginning halfway up a ramp.

  It is practice, always: you did not earn the position.  It is also marked
  TF_SHADOW, which is strictly narrower -- and since build 44 TF_SEGMENT, which
  is what the leaderboard calls it.

  TF_SHADOW is USUALLY what the recording is named after, and build 45 made that
  a "usually": if the same attempt also cheated, TF_CHEAT outranks it and the
  file is written as `cheat.rec` instead.  Not a tie-break for neatness -- a
  shadow name is ARCHIVED and would accumulate a stamped junk file per lap, and
  a cheat name is one scratch slot.  See RT_SHADOW and RT_CHEAT.

  WHY THE LIST IS SERVER-SIDE

  Two of the things a save restores are not CSQC's to give back.  The origin has
  to be set authoritatively or prediction fights it, and the DUCK STATE lives
  inside the engine's pmove -- pmove.ducked is carried across commands in
  host_client->pmsrc (sv_user.c:7815) and QC cannot see it, let alone write it.
  Engine Patch 142 adds one optional field, run_forceduck, purely so this file can
  hand it back.

  Restoring the duck matters more than it sounds.  Save while crouched under a
  lip, load standing, and the 62-unit hull spawns inside the ceiling: you arrive
  stuck, in the exact spot you were trying to practise.  (17 units of it, the
  difference between PM_HULL_MAXS and PM_DUCK_MAXS.)

  WHY THE LIST IS GLOBAL, AND THE CURSOR IS NOT

  The saves live on disk now, under the MAP, so they are a property of the map
  and not of whoever is standing on it.  Keeping a per-player copy of a shared
  thing would mean two players could disagree about a file they can both see.
  So the rows are global and only the cursor -- the "3/7", which is a question
  about what YOUR next keypress does -- is per player.
===========================================================================
*/

/*
  ON DISK.

      data/saves/<mapname>/save07/state.txt     the state, one key per line
                                  run.rec       movement up to the save point
                                  run.view      camera + keys, written by CSQC

  `data/` is not a choice: QC's write sandbox allows exactly `data/` and `cfg/`
  (pr_bgcmd.c QC_FixFileName), and everything else is rewritten or refused.
  Nothing has to create the directories -- fclose goes through COM_WriteFile,
  which calls FS_CreatePath first.

  THE FOLDER NUMBER IS NOT THE LIST POSITION.

  Deleting a save slides the list down (see SV_SaveLocDelete), so if position
  were the folder name then every delete would have to rename every folder after
  it -- three files each, across a directory, with no way to make it atomic and
  no way to recover half of it.  So the folder id is STABLE, allocated
  lowest-free at create and never touched again, and the ORDER comes from a
  `seq` counter inside the file.  Nothing is ever renamed, a deleted id is free
  for reuse, and "the newest save is the last one" still holds -- which the menu
  depends on, because `1` then `2` with the menu closed means "save here, put me
  back here".
*/
#define SL_STATE_VERSION 1

// search_begin flags.  QCSEARCH_NAMESORT, pr_bgcmd.c:3506.
#define SL_NAMESORT 32

/*
  The list.  Only what the HUD, the menu and the per-tick hold actually need --
  everything else is read out of state.txt at the moment of a load, which is a
  few hundred bytes once per keypress rather than 32 rows of run state resident
  for the whole map.
*/
#define FS_SLCLIENTS 32
#define FS_SLBLOCK   FS_MAXSAVES       // Patch 428: was 24 a player
#define FS_SLROWS    (FS_MAXSAVES + FS_SLCLIENTS * FS_SLBLOCK)

// Patch 428: memalloc'd, not arrays.  33 x 999 rows cannot fit the 16-bit globals
// table (64547 of 65535 used with 24-row blocks); ~1.85 MB per map, against a QC
// heap the lobbies measured at 5-8 MB used.  SV_SaveLocAlloc; indexing is unchanged.
vector *rec_sl_org;
vector *rec_sl_vel;
float  *rec_sl_pit;
float  *rec_sl_yaw;
float  *rec_sl_duck;
float  *rec_sl_id;                     // folder number, 1..FS_MAXSAVES, stable
float  *rec_sl_seq;                    // creation order; the sort key
float  *rec_sl_tick;                   // the run clock stored in the slot
float  *rec_sl_seg;                    // segment, for the console list
float  *rec_sl_cps;                    // checkpoints crossed, for the same

float  rec_sl_nb[FS_SLCLIENTS + 1];        // rows in use per block
float  rec_sl_ns[FS_SLCLIENTS + 1];        // next seq per block
float  rec_sl_scanlob[FS_SLCLIENTS + 1];   // Lobby_Active()+1 at scan time; 0 never
string rec_sl_owner[FS_SLCLIENTS + 1];     // Patch 428: the guid a lobby block was scanned for; SL_Fresh
string sl_root;                            // directory the paths are spelled from
float  sl_lob_last;                        // lobby state the stamps were taken in

// Every row write is behind a scan or a create, both of which call this first,
// and every read is gated on rec_sl_nb > 0, so no pointer is used before it runs.
// The heap is reset with the globals at every map load (Q_InitProgs).
// Review round 1: THE POINTER, not a flag.  A savegame restores float globals and
// not pointers, so a flag and rec_sl_nb came back over null columns; the counts
// are dropped whenever the columns are (re)made, and the entry points call this.
void() SV_SaveLocAlloc =
{
	local float i;

	if (rec_sl_org)
		return;
	for (i = 0; i <= FS_SLCLIENTS; i = i + 1)
	{
		rec_sl_nb[i] = 0;
		rec_sl_scanlob[i] = 0;
	}
	rec_sl_org  = memalloc(sizeof(vector) * FS_SLROWS);
	rec_sl_vel  = memalloc(sizeof(vector) * FS_SLROWS);
	rec_sl_pit  = memalloc(sizeof(float) * FS_SLROWS);
	rec_sl_yaw  = memalloc(sizeof(float) * FS_SLROWS);
	rec_sl_duck = memalloc(sizeof(float) * FS_SLROWS);
	rec_sl_id   = memalloc(sizeof(float) * FS_SLROWS);
	rec_sl_seq  = memalloc(sizeof(float) * FS_SLROWS);
	rec_sl_tick = memalloc(sizeof(float) * FS_SLROWS);
	rec_sl_seg  = memalloc(sizeof(float) * FS_SLROWS);
	rec_sl_cps  = memalloc(sizeof(float) * FS_SLROWS);
};

// Build 25.  A delete-all drives SV_SaveLocDelete once per row and must not
// print its per-row summary each time.  Bare (Q106), and set/cleared around the
// loop in SV_SaveLocDeleteAll rather than passed down, so the eight other
// callers of that function need no change.
float  rec_sl_quiet;

// Patch 333 replaced this with rec_sl_scanlob[]: a stamp per block, because
// "the disk was read" is now a question about WHICH player's directory, and a
// block read under one lobby state is stale under the other.

.float rec_sl_count;             // networked mirror of the caller's block; SV_SaveLocSync
.float rec_sl_index;             // 1-based cursor; 0 when the list is empty
.float rec_sl_delall;            // Patch 428: a delete-all sweeping; rows deleted + 1
.float rec_sl_tok;               // Patch 428: SV_SaveLocBegin's bucket...
.float rec_sl_tokt;              // ...the time it was last filled...
.float rec_sl_toksay;            // ...and the last "slow down"
.float rec_sl_loadrow;           // Patch 428: with rec_sl_loadt (sv_timer.qc), the load
.float rec_sl_loadseq;           // a hold may follow -- its row and its save

#define SL_TOKRATE  20           // list commands a second, burst and sustained
#define SL_DEMOTED  -1           // rec_sl_tick of a demoted save: never "clock stopped" to `!r`
#define SL_RECKEEP  24           // lobby saves that keep their recording copy (SV_SaveLocCreate)
/*
  Patch 435: the horizontal speed under which a start-box load still arms.
  state.txt writes `velocity %.4f`, so a body at rest reads back at most 0.00005
  a component, and friction leaves a grounded one below sv_stopspeed -- 1 u/s is
  above both and below any prespeed worth carrying into a run.
*/
#define SL_ARM_SPEED 1

// Patch 435: what a row carries, which is the speed its load hands back
// (SV_SaveLocPlace writes rec_sl_vel[r] into the body, and a hold hands the same
// vector back on release).  Read off the ROW and not off e.velocity, which a load
// taken while parked has already zeroed.
//
// PATCH 442: ALL THREE COMPONENTS.  This was `vlen([v_x, v_y, 0])`, and the gate it
// feeds asks whether the save was taken AT REST.  A body mid-JUMP inside a start box
// has vz +302 and no horizontal speed at all, so it read as at rest: the gate fired
// and the load armed a CLEAN attempt.  The hop dwell does not catch it either, and
// NOT for the reason this comment first gave: SV_TimerJumpWatch's `jumped` IS a pure
// velocity edge (sv_timer.qc:9835) and a restored +302 satisfies it -- which is why
// the arm reads `running` one frame after the load on a start-on-jump map.  What
// keeps run_t_hopped clear is that every load sets run_t_startok (SV_SaveApplyState, `e.run_t_startok = TRUE`), and the
// whole hop block is behind `if (!e.run_t_startok)` (sv_timer.qc:9986).  A reviewer
// caught the wrong mechanism; BACKLOG.md carries the startok half, which is bigger
// than this patch.  The paragraph above only ever reasoned about a
// GROUNDED body: friction is horizontal, and so was the test.  Measured both ways,
// cfg/test/p442jump.cfg, including that a REAL save taken standing still arms.
float(float r) SL_RowSpeed =
{
	local vector v;
	v = rec_sl_vel[r];
	return vlen(v);
};
.vector rec_sl_curorg;           // Patch 430: STAT_FS_SLORG, the cursor row, SV_SaveLocSync
.vector rec_sl_curang;           // Patch 430: STAT_FS_SLANG
.float rec_sl_ack;               // Patch 430: STAT_FS_SLACK, SV_ParseClientCommand

// The save/load event stream, for the client's half of the recording.  See
// STAT_FS_SLSEQ in shared/sh_defs.qc.
.float rec_sl_slseq;
.float rec_sl_slop;
.float rec_sl_savetick;          // the cursor slot's stored run clock

/*
  HOLD.

  While the load key is held down the player is parked at the save and starts
  moving the instant it is released.  That is a different tool from a one-shot
  load: it lets you sit at the top of a ramp and study the approach, or line an
  angle up without the fall, and then begin the section when you choose.

  IT FREEZES THE PLAYER; IT DOES NOT RE-PLACE THEM EVERY TICK.

  The first version did re-place them every tick, and that was wrong in a way
  worth writing down, because it looked like a plausible design.  The player
  stayed MOVETYPE_WALK, so the CLIENT went on predicting: it ran the move
  forwards from the last snapshot, drew you a few units along, then the next
  snapshot put you back at the save.  Sixty-six times a second.  That is the
  "glitching and flickering" -- not a bug in the pin, the pin working exactly
  as written against a prediction that was never told to stop.

  MOVETYPE_NONE is how you tell it to stop.  SV_PMTypeForClient maps it to
  PM_NONE (sv_user.c:7398-7399), whose whole purpose is that -- the engine's own
  comment at :7377 calls it "let the client know that its prediction is fucked.
  should make it just lerp."  The same value reaches the client's copy of pmove,
  so both sides agree that this player does not move and neither one has to win.

  And the objection the old comment raised against it is simply not true of the
  Source pmove.  PM_NONE zeroes the move inputs, runs CategorizePosition and
  returns (pm_source.c:1701-1705) -- it never reaches PMSrc_Duck, so
  pmove.ducked is untouched and PMSrc_ApplyHull keeps rebuilding the hull the
  save asked for.  Angles are applied outside pmove, so you can still look
  around while parked, which is most of the point.

  Velocity is zeroed while frozen and the SAVE'S velocity is handed back on
  release, so letting go is exactly a load: same origin, same speed, same hull.

  rec_sl_holdrow is the LIST ROW.  It used to be an absolute array index, which
  meant the same thing when the arrays were per player; now that the list is
  global it is simply the row, and it is still re-pointed rather than trusted --
  deleting an earlier save while holding would otherwise slide the list out from
  under the hold.
*/
// .rec_sl_hold is declared in sv_timer.qc, whose SV_TimerFrame reads it.
.float rec_wt_hold;              // the replay pin (see WATCHING below); here for SV_SaveLocHold
.float rec_sl_holdrow;
.float rec_sl_holdmove;          // the movetype to give back on release

/*
  Build 30.  The velocity the hold is parked on, published as STAT_FS_HOLDVEL.

  It is the same number the release hands back three lines lower down -- this
  field exists only so the CLIENT can see it too, because .velocity is zero for
  the whole hold and the HUD had no other way to know what it was.  Kept in step
  with rec_sl_holdrow rather than written once: the hold can be re-pointed at
  another row (hold 2, tap 4/5) without ever passing through a release.

  '0 0 0' whenever rec_sl_hold is clear, so the stat costs nothing at rest and a
  stale value can never be read back out of it.
*/
.vector rec_sl_holdvel;

/*
  Engine Patch 142.  Written by QC, consumed and cleared by the engine: it is
  found by name with GetEdictFieldValue just before PMSrc_LoadState, applied
  to pmove's carried duck state, and zeroed.  A mod that does not declare it
  (quakers, sharing this engine tree) gets NULL back and the patch does
  nothing at all -- the same idiom as the run_board* telemetry.

  0 = no change, 1 = stand up, 2 = crouch.  Zero is the no-op because a QC
  field is zero on a fresh edict, so nothing has to remember to initialise it.
*/
#define FD_NONE   0
#define FD_STAND  1
#define FD_DUCK   2

.float run_forceduck;

// Defined below, next to the hold it undoes; forward-declared because a reset
// and a respawn both have to be able to let go of one.
void(entity e) SV_SaveLocRelease;

// Patch 438: the event funnel, forward-declared because sl_replay sits above it.
void(entity e, float op, float id) SV_SaveLocEvent;

// Build 24, and forward-declared for the same reason: a map reset has to let go
// of a watch too, and it happens three hundred lines above the definition.
void(entity e) SV_WatchRelease;

// Patch 333: the block machinery, forward-declared because the gate and the
// scan sit below every consumer that needs to name them.
void(float blk) SV_SaveLocScanBlk;
float(entity e) SL_Blk;
float(float blk) SL_Base;
float(float blk) SL_Cap;
void(entity e) SV_SaveRootFor;
float(entity e, float quiet) SV_SaveLocAllowed;
float(entity e, float quiet) SV_SaveLocBegin;
void(entity e) SV_SaveLocDeleteAllStep;     // Patch 428: SV_SaveLocFrame drives it

/*
===========================================================================
  Paths
===========================================================================
*/
/*
  BUILD 25: THE NAME MOVED TO shared/sh_defs.qc, and this is a forwarder.

  It was two digits and local, and build 25 widened the id space to 999.  The
  same string is needed by the client's Rec_SavePath and Seq_Path -- a save's
  four files are joined by nothing but the directory they land in -- so the rule
  is now FS_SaveSlotName, in the file all three VMs compile, and the essay giving
  the reason is there beside it.  Left as a forwarder rather than replaced at the
  eight call sites below, which is the shape SV_TrackSegs and Watch_IsSample
  already have for the same reason.
*/
string(float id) SL_NN = { return FS_SaveSlotName(id); };

string(float id) SL_Dir      = { return sprintf("%s/save%s/", sl_root, SL_NN(id)); };
string(float id) SL_StatePath= { return strcat(SL_Dir(id), "state.txt"); };
string(float id) SL_RecPath  = { return strcat(SL_Dir(id), "run.rec"); };
string(float id) SL_ViewPath = { return strcat(SL_Dir(id), "run.view"); };
// Build 20.  Written by the CLIENT, like run.view -- the segment column is
// client-side state and the server has never seen it.  Named here only so the
// delete below can remove it; see SV_SaveLocDelete for why that matters.
string(float id) SL_SeqPath  = { return strcat(SL_Dir(id), "seq.txt"); };

/*
  PATCH 333 -- WHICH BLOCK, WHICH SLICE, WHICH DIRECTORY.

  SL_Blk is 0 off-lobby and the client slot in one: num_for_edict is 1-based,
  which is why block 0 can be the shared one and why a 33-long array covers a
  32-player server.  The lobby cvar is read live on purpose, the same live read
  Lobby_NoSaveLoc always had: an operator who flips lobby_enable mid-map moves
  every player to a different block, and SV_SaveLocSync's flip watch clears the
  stamps and the holds so the move is a rescan rather than a misread.
*/
float(entity e) SL_Blk =
{
	if (Lobby_Active())
		return num_for_edict(e);
	return 0;
};

float(float blk) SL_Base =
{
	if (blk <= 0)
		return 0;
	return FS_MAXSAVES + (blk - 1) * FS_SLBLOCK;
};

float(float blk) SL_Cap =
{
	if (blk <= 0)
		return FS_MAXSAVES;
	return FS_SLBLOCK;
};

/*
  PATCH 415 -- a point that has been through state.txt, put back on the floor it
  was standing on, and ONLY when that is what the rounding did to it.

  `origin %.4f` rounds to nearest, so it moves a coordinate by at most 0.00005 in
  either direction.  A zone whose bottom IS that floor then rejects the position
  by exactly that: bhop_eazy's start bottom is 64.031250 and a save taken standing
  in the middle of the box holds 64.0312.  Zone_PointInside's ring test passes and
  its z-slab test fails.

  SNAPPED UP TO THE BOTTOM RATHER THAN LIFTED.  An unconditional `+ quantum`
  would also push a save resting on a zone's TOP face out through the ceiling --
  Zone_PointInside tests both ends of the slab -- trading a false negative at the
  floor for one at the roof.  This only moves a point that is within the format's
  own error BELOW the bottom, and moves it exactly onto the bottom, so no other
  answer can change.

  THE TOLERANCE IS NOT JUST THE DECIMAL QUANTUM, and assuming it was is what made
  the first two attempts at this fail.  `%.4f` rounds to 5e-5, but the text is
  then parsed back into a 24-bit mantissa, and THAT error grows with the
  coordinate: 7.6e-6 at z 64, 0.002 at a map's 16384.  bhop_eazy's real gap is
  5.34e-5 -- over a 5e-5 threshold by a third of a float ulp, which is exactly the
  kind of margin that reads as "the feature does not work".  So the tolerance is
  the decimal quantum plus two ulps at this magnitude, and it is still far below
  anything a player or a mapper can express.
*/
#define SL_ORIGIN_QUANTUM 0.0001
#define SL_ORIGIN_ULP     0.00000012            // ~2 float32 ulps, relative

vector(float z, vector p) SV_SaveZonePoint =
{
	local float eps;

	// Guarded although the one caller validates z first: this file's rule is
	// that an array read carries its own bound, because the SECOND caller is
	// where that stops being true and an out-of-range read takes the VM down.
	if (z < 0 || z >= zone_count)
		return p;

	eps = SL_ORIGIN_QUANTUM + fabs(zone_bottom[z]) * SL_ORIGIN_ULP;

	if (p_z < zone_bottom[z])
	if (zone_bottom[z] - p_z <= eps)
		p_z = zone_bottom[z];
	return p;
};

/*
  Is a coordinate out of a save file a number at all?

  NOTHING VALIDATES rec_sl_org.  `origin` is parsed with stof, so a hand-edited
  `nan` or `inf` in state.txt becomes one -- and NaN fails EVERY comparison, so
  Zone_PointInside's slab test, its AABB reject and Zone_XYInRing's edge tests
  are all false-and-therefore-not-outside.  A NaN origin passes the whole zone
  test and reaches setorigin.  Only reachable where the player owns the file (a
  listen server or their own install), so this is hardening rather than a hole,
  but it costs three compares.

  WRITTEN AS A NEGATED RANGE, deliberately: `p_x > 65536 || p_x < -65536` lets a
  NaN straight through, because both halves are false.  Asking "is it inside the
  range" and negating the answer is the form that catches it.  65536 is four
  times a map's +-16384.
*/
float(vector p) SV_SaveOriginSane =
{
	if (!(p_x > -65536 && p_x < 65536))
		return FALSE;
	if (!(p_y > -65536 && p_y < 65536))
		return FALSE;
	if (!(p_z > -65536 && p_z < 65536))
		return FALSE;
	return TRUE;
};

/*
  A certificate guid is not a folder name.  It is hex in practice, but nothing
  promises that, and this string goes straight into a path that fremove later
  reads back -- so everything that is not a plain letter or digit becomes an
  underscore, and an empty or hostile guid can neither escape the directory nor
  collide with the map-root layout (the @ prefix is a character the sanitiser
  cannot produce, so a per-player folder can never be mistaken for a slot).
*/
string(string g) SV_SaveSanitise =
{
	local string o, c, allow;
	local float i;

	// Character-code compares are not in the language; a whitelist haystack
	// and strstrofs are, and a 62-char haystack per character of a guid is
	// nothing next to what the scan it protects costs.
	allow = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
	o = "";
	for (i = 0; i < strlen(g); i = i + 1)
	{
		c = substring(g, i, 1);
		if (strstrofs(allow, c) >= 0)
			o = strcat(o, c);
		else
			o = strcat(o, "_");
	}
	return o;
};

/*
  Set sl_root for this player and TELL THEM, because the client writes two of
  the four files in a slot -- seq.txt from cl_board.qc, run.view from
  cl_replay.qc -- and spells their paths from the same root.  One stuffcmd per
  saveloc operation is a `set` of a cvar the client never registers, and it
  means the two VMs cannot drift: the server is the only place that knows the
  lobby state, the guid and the map name at once.
*/
// Patch 428: the root alone, for work that is not a gesture (SV_SaveLocFrame's
// sweep): sl_root is one global every player's command re-points.
void(entity e) SV_SaveRootSet =
{
	local string k;

	k = "";
	if (Lobby_Active() && !cvar("lobby_nosaveloc"))
		k = SV_SaveSanitise(infokey(e, "guid"));

	if (k != "")
		sl_root = sprintf("data/saves/%s/@%s", mapname, k);
	else
		sl_root = sprintf("data/saves/%s", mapname);
};

void(entity e) SV_SaveRootFor =
{
	SV_SaveRootSet(e);
	stuffcmd(e, sprintf("set cl_saveroot \"%s\"\n", sl_root));
};

/*
  The gate every list-mutating and list-reading command goes through.

  Off-lobby it is the old behaviour exactly: the shared block, scanned once and
  cached.  In a lobby it is the two questions patch 270 had no answer for --
  does the operator want saves here at all, and can this player be attributed
  -- and then a scan of THAT PLAYER'S block, rescanned whenever the stamp says
  the lobby state has moved since the last one.
*/
/*
  THE TWO POLICY GATES, SPLIT OUT BY PATCH 415 so a caller can ask them without
  paying for the scan below.

  They are cheap -- a cvar and an infokey -- while the expensive half is the
  directory read.  SV_SaveLocPickInZone wants the gates on every `!r` and the
  scan only when the block is stale, and the first cut of it got that by skipping
  SV_SaveLocBegin when the block was fresh, which skipped the gates too.  On a
  lobby that is always: SV_SaveLocSync stamps rec_sl_scanlob from every
  PlayerPostThink, so SV_SaveLocBegin was never reached from `!r` at all.  Both
  gates silently stopped applying -- `lobby_nosaveloc` was no longer an off
  switch, and a player with no certificate reads SL_Blk's per-player block filled
  from the SHARED directory (SV_SaveRootFor's no-guid fallback), i.e. other
  players' saves, which is the cross-player placement Patch 333's essay below
  calls structurally gone.  Two functions, so "may I" and "load the list" cannot
  come apart again.

  `quiet` is for a caller that is ASKING rather than being told.  Every gesture
  below this is a player typing `sl_something`, and a refusal owes them the
  reason; `!r` looking to see whether there is a save to prefer is not a gesture,
  and printing "save points are off" at every restart would be noise about a
  feature the player never asked for.
*/
float(entity e, float quiet) SV_SaveLocAllowed =
{
	local float blk;

	blk = SL_Blk(e);

	if (blk > 0 && cvar("lobby_nosaveloc"))
	{
		if (!quiet)
			sprint(e, PRINT_HIGH,
			       "^3save: save points are off in this lobby -- the operator set "
			       "lobby_nosaveloc.\n");
		return FALSE;
	}

	if (blk > 0 && infokey(e, "guid") == "")
	{
		if (!quiet)
			sprint(e, PRINT_HIGH,
			       "^3save: lobby saves are per player and need your certificate -- "
			       "the server has no sv_guidkey to attribute them with.\n");
		return FALSE;
	}

	return TRUE;
};

/*
  Patch 428: A LOBBY BLOCK IS A SLOT, and nothing let go of it when its player
  left -- the next player in that slot on the same map inherited the old rows
  while SV_SaveRootFor pointed every file operation at their own folder: the
  other player's count on the HUD, a load placing them at the other player's
  save, and a delete removing THEIR save that shared the other's folder number.
  So a lobby block is fresh only for the guid it was scanned for.  Checked at
  use, not cleared at ClientConnect (review round 1): a QW spectator enters a
  slot without ClientConnect, and a clear there let a player force a 999-row
  rescan at every reconnect.
*/
float(entity e, float blk) SL_Fresh =
{
	if (rec_sl_scanlob[blk] != Lobby_Active() + 1)
		return FALSE;
	if (blk > 0 && strcmp(rec_sl_owner[blk], infokey(e, "guid")))
		return FALSE;
	return TRUE;
};

void(entity e, float blk) SV_SaveLocScanFor =
{
	SV_SaveLocScanBlk(blk);
	if (rec_sl_owner[blk] != "")
		strunzone(rec_sl_owner[blk]);
	rec_sl_owner[blk] = strzone(infokey(e, "guid"));
};

/*
  Patch 428: a bucket of SL_TOKRATE sl_ commands, refilled at that rate --
  ONE CHARGE A COMMAND, from SV_ParseClientCommand (review round 2: charged in
  SV_SaveLocBegin, 3/4/5/6 paid twice, Step's Begin and Load's).  At 999 saves a
  burst of sl_save or sl_del in one packet is seconds of disk work in one frame.
*/
float(entity e) SV_SaveLocRate =
{
	e.rec_sl_tok  = min(SL_TOKRATE, e.rec_sl_tok + (time - e.rec_sl_tokt) * SL_TOKRATE);
	e.rec_sl_tokt = time;
	if (e.rec_sl_tok < 1)
	{
		if (time - e.rec_sl_toksay > 1)
		{
			sprint(e, PRINT_HIGH, "^3save: slow down\n");
			e.rec_sl_toksay = time;
		}
		return FALSE;
	}
	e.rec_sl_tok = e.rec_sl_tok - 1;
	return TRUE;
};

// Patch 428: the player sweeping block blk with a delete-all, or world.  Any
void(entity e, float n) SV_SaveLocReplay =
{
	/*
	  Patch 438: `sl_replay <n>` -- a LOAD EVENT WITH NO SAVE BEHIND IT.

	  The client's sidecar reload (Rec_ViewLoaded) is gated on a save/load event
	  it is allowed to act on, and the only way to produce one is a real save --
	  which puts the file where the server's own save root says, not where a
	  harness can put a 6 MB one.  This fires the event for an absolute slot and
	  nothing else: no placement, no clock, no row, no state file read.  It is a
	  harness handle for the evidence code's own reader, charged like any other
	  sl_ command so it cannot be spammed, and it cannot launder a run because it
	  cannot move one.

	  PATCH 441: AND IT NEEDS sv_cheats, because it does not have to move a run to
	  damage one.  The event it fires is the one Rec_ViewLoaded acts on, and that
	  either TRUNCATES the live sidecar to this slot's remembered mark or REPLACES
	  the buffer from the slot's file (cl_replay.qc:1478-1533) -- so ungated, any
	  client could drop its own angle evidence mid-run, repeatedly, without ever
	  taking a save.  The lobbies run this progs with rec_enable 1.
	  cvar() and NOT SV_CheatsOn(), which answers FALSE whenever run_cheatwatch is
	  0 and would refuse the arm this exists for.  Every configuration where the
	  command now works is one where the run does not rank: cheatwatch 1 taints it
	  through SV_CheatLevel, cheatwatch 0 makes every run practice (default.cfg:427).
	*/
	if (!cvar("sv_cheats"))
	{
		sprint(e, PRINT_HIGH, "^3save: sl_replay needs sv_cheats 1\n");
		return;
	}
	if (n < FS_RETRY_SLOT || n > FS_MAXSAVES)
	{
		sprint(e, PRINT_HIGH, sprintf("^3save: %g is not a slot\n", n));
		return;
	}
	/*
	  Patch 441 round 2: THE CHARGE AND THE ACK ARE THE DISPATCHER'S, and this
	  function was doing both a second time.  SV_ParseClientCommand counts every
	  `sl_` command and pays SV_SaveLocRate's one charge before dispatch
	  (sv_player.qc:775-788) -- which is what Patch 428's review round 2 centralised
	  after 3/4/5/6 paid twice -- so the local `SV_SaveLocRate(e)` was a second
	  token off the bucket and `rec_sl_ack + 1` a second ack, and the ack is what
	  Patch 430's early draw compares against what the client sent.  Both gone.
	  The refusal above is therefore throttled without being charged here.

	  AND THE ATTEMPT IN PROGRESS IS PRACTICE FROM HERE.  The gate argues that no
	  configuration lets this command work on a ranking run (cheatwatch 1 taints,
	  cheatwatch 0 makes every run practice) -- but that safety is entirely INHERITED
	  from two distant blocks, and a later edit to either re-opens this silently.  A
	  taint at the gesture is one line that does not depend on them.
	  WHAT IT DOES NOT DO, because the first draft of this paragraph claimed it did:
	  survive the next arm.  SV_TimerArm re-derives the class from the level
	  (sv_timer.qc:10566) and the retry/Multi-Session restores put the saved flags
	  back, so `sl_replay` then `!r` clears it.  That is the scope every other taint
	  has; it is not a guarantee about the player's next attempt.  BACKLOG.md carries
	  the rest, including that this function has no run_ms_phase refusal.
	*/
	SV_TimerPractice(e);
	SV_SaveLocEvent(e, SLOP_LOADED, n);
	sprint(e, PRINT_HIGH, sprintf("save: replay event for slot %g\n", n));
};

// Patch 428: the player sweeping block blk with a delete-all, or world.  Any
// player's: block 0 is shared, so a save by anyone on it mid-sweep would be the
// next row the sweep deletes.
entity(float blk) SL_Sweeper =
{
	local entity p;

	p = world;
	while ((p = find(p, classname, "player")))
		if (p.rec_sl_delall)
		if (SL_Blk(p) == blk)
			return p;
	return world;
};

float(entity e, float quiet) SV_SaveLocBegin =
{
	local float blk;

	SV_SaveLocAlloc();
	blk = SL_Blk(e);

	if (!SV_SaveLocAllowed(e, quiet))
		return FALSE;

	// Patch 428: nothing joins or moves the list while a delete-all sweeps it
	// from the end -- a save taken now would be the next row it deletes.
	if (SL_Sweeper(blk))
	{
		if (!quiet)
			sprint(e, PRINT_HIGH, sprintf("^3save: still deleting -- %g left\n", rec_sl_nb[blk]));
		return FALSE;
	}

	SV_SaveRootFor(e);

	if (!SL_Fresh(e, blk))
		SV_SaveLocScanFor(e, blk);

	return TRUE;
};

/*
===========================================================================
  Writing a save
===========================================================================
*/
/*
  The state file.

  Plain text, one key per line, ANY ORDER, and an unknown key MUST be skipped
  rather than rejected -- the same grammar the .rec header uses and for the same
  reason: it is what lets a later build add a key without breaking a reader that
  was written before it existed.  A format you can read with `type` is the one
  that survives being written before its reader.
*/
void(entity e, float id, float seq) SV_SaveWriteState =
{
	local filestream f;
	local float i, mark;
	local string p;

	p = SL_StatePath(id);
	f = fopen(p, FILE_WRITE);
	if (f < 0)
	{
		sprint(e, PRINT_HIGH, sprintf("^1save: cannot write %s\n", p));
		return;
	}

	/*
	  The recording's prefix goes out FIRST, so that `reclines` below describes a
	  file that already exists.  If the write fails we record a mark of 0, which
	  a load reads as "this save has no movement behind it" -- degraded, not
	  wrong, and exactly what a save taken before the clock started looks like
	  anyway.
	*/
	mark = SV_RecWritePrefix(e, SL_RecPath(id));

	fputs(f, sprintf("FTESURF-SAVE %d\n", SL_STATE_VERSION));
	fputs(f, sprintf("map %s\n", mapname));
	fputs(f, sprintf("seq %d\n", seq));
	fputs(f, sprintf("created %s\n", strftime(TRUE, "%Y%m%d-%H%M%S")));

	// Position.  Written at full precision rather than the %.1f the console
	// `setpos` line uses: this is a state file and not something to read.
	fputs(f, sprintf("origin %.4f %.4f %.4f\n",
	                 e.origin_x, e.origin_y, e.origin_z));
	fputs(f, sprintf("velocity %.4f %.4f %.4f\n",
	                 e.velocity_x, e.velocity_y, e.velocity_z));
	fputs(f, sprintf("angles %.4f %.4f\n", e.v_angle_x, e.v_angle_y));
	fputs(f, sprintf("duck %d\n", (e.pmove_flags & PMF_DUCKED) ? 1 : 0));

	// The timer.
	fputs(f, sprintf("state %d\n", e.run_t_state));
	fputs(f, sprintf("track %d\n", e.run_t_track));
	fputs(f, sprintf("startseg %d\n", e.run_t_startseg));
	/*
	  BUILD 57: WHETHER THIS IS A STAGE-ONLY RUN, because startseg no longer says.

	  A stage-1 run and a full run both begin at segment 0, so `startseg 0` names
	  two different legs now -- `main` and `stage_1` -- and a load that guessed would
	  file a stage-1 attempt's finish under the whole map.  Additive, by this
	  format's own rule: an older build skips the key, and a save written before it
	  restores as `stagerun = (startseg > 0)`, which is exactly what those files
	  meant, since nothing before build 57 could run stage 1 on its own.
	*/
	fputs(f, sprintf("stagerun %d\n", e.run_t_stagerun ? 1 : 0));
	fputs(f, sprintf("seg %d\n", e.run_t_seg));
	fputs(f, sprintf("segs %d\n", e.run_t_segs));
	/*
	  ZERO WHEN THERE IS NO RUN, and this was a real bug rather than a nicety.

	  SV_TimerTicks differences against an origin that is 0 until a run starts --
	  so on an idle timer it returns the number of ticks since the MAP loaded, and
	  the save list cheerfully printed that as the run time.  Three saves taken
	  while idle read 0:09.330, 0:16.170 and 0:18.780, which look exactly like
	  three points along a run and are the wall clock.

	  BUILD 76 DID NOT FIX THAT AND THIS GUARD IS STILL WHAT STANDS BETWEEN IT AND
	  THE LIST.  The clock moved onto the mover's counter, so the idle reading is
	  now simulated ticks since the map loaded rather than wall ticks, which is a
	  different wrong number and no better.  SV_TimerTicks says the same thing at
	  its own definition, and says why it was left alone in a build whose job was
	  to move the clock.

	  Caught by the verification pass, which is the only place it could have
	  been: every number was plausible and they even increased in the right
	  order.

	  A FINISHED timer needs the other of the two, for the mirror-image reason:
	  SV_TimerTicks keeps counting after the finish, so the live figure would
	  grow while you stood in the end zone.  run_t_ticks is the one that stopped.
	*/
	if (e.run_t_state == TS_RUNNING)
		fputs(f, sprintf("ticks %d\n", SV_TimerTicks(e)));
	else if (e.run_t_state == TS_FINISHED)
		fputs(f, sprintf("ticks %d\n", e.run_t_ticks));
	else
		fputs(f, "ticks 0\n");
	/*
	  THE OTHER HALF OF THE CLOCK, and since build 76 that is the accurate way to
	  put it -- it used to be "the same clock unrounded".

	  BEFORE: `ticks` was the elapsed seconds ROUNDED, so restoring from it put
	  the clock up to half a tick behind where the save was taken, which made the
	  first sample after a resume older than the last sample already in the
	  recording.  Time running backwards mid-file is not something a reader can
	  interpolate through, and tools/reccheck.py refuses it.  This key existed to
	  give the load something exact to restore from.

	  NOW: both are exact and neither is a rounding of the other.  `ticks` is the
	  integer the mover produced and is what ranks; this is the simulated seconds
	  the mover consumed, carry included, and is what the recorder stamps.  They
	  differ by the sub-tick phase the run happened to start on -- up to one tick,
	  by construction and not by error.  The load restores BOTH, each into its own
	  origin, which is why SV_TimerResume takes two arguments now and why the
	  half-tick problem this key was invented for cannot occur.

	  A READER MUST NOT DERIVE ONE FROM THE OTHER in either direction.  It was
	  always unsound and it used to be nearly right; it is now a statement about
	  the start phase, which no reader knows.
	*/
	fputs(f, sprintf("elapsed %.6f\n",
	                 (e.run_t_state == TS_RUNNING) ? SV_TimerElapsed(e) : 0));
	/*
	  BUILD 76: WHICH CLOCK THE TWO NUMBERS ABOVE WERE TAKEN ON.

	  Additive, by this format's own rule -- an older build skips the key, and a
	  save written before it is `sampled`, which is what every file predating this
	  build meant.  Nothing in the load branches on it: both origins are re-based
	  against readings taken at the resume, so a save crosses between clocks
	  correctly either way, and a save load marks the run practice regardless.

	  It is written for the person reading the file, not for the loader.  A save
	  is the one artefact in this game that can be carried between installs, so
	  "these seconds are wall seconds" is a fact a human may need and the file is
	  the only place it could be recorded.
	*/
	fputs(f, sprintf("clock %s\n", e.run_t_clock ? "counted" : "sampled"));
	fputs(f, sprintf("split %d\n", e.run_t_split));
	fputs(f, sprintf("delta %d\n", e.run_t_delta));

	// TF_FROZEN and TF_STOPPED are masked out for the same reason TF_RECORDING
	// is on the way back in (see SV_SaveApplyState): each states something that
	// is true RIGHT NOW -- a hold, and a cancelled run still on screen -- and no
	// file can assert one.  Save while parked and the flag would otherwise
	// travel to whoever loads that state later.
	//
	// Patch 416 adds TF_NONCE to exactly that list, and it is the strongest case
	// of the three: the bit says THIS client, on THIS connection, answered THIS
	// session's number.  A file cannot assert any of the three, and a save taken
	// in the round trip before the answer landed would otherwise clear a bit the
	// client had already earned.
	fputs(f, sprintf("flags %d\n",
	                 e.run_t_flags - (e.run_t_flags & (TF_FROZEN | TF_STOPPED | TF_NONCE))));
	fputs(f, sprintf("pb %d\n", e.run_t_pb));
	fputs(f, sprintf("dirty %d\n", e.run_t_dirty));
	/*
	  BUILD 44: the class latch, beside the umbrella it belongs to.

	  Only `retry` reads it back -- a load is a stitch and re-derives its own
	  class -- but a retry of a run that had been noclipped before the clock
	  started must come back cheated, and TF_CHEAT in `flags` above cannot say so:
	  the whole reason run_t_cheat exists is that the flags word is zeroed by the
	  arm and the latch is what crosses it.  A retry restores an attempt that may
	  not have started yet.

	  A NEW KEY IS BACKWARD-COMPATIBLE IN BOTH DIRECTIONS.  The reader is a
	  key-match loop with defaults, so an older save simply reads 0 here, and an
	  older build reading a newer save skips a key it does not know.  No version
	  and no format bump -- the same property the `fromsave` key relied on.
	*/
	fputs(f, sprintf("cheat %d\n", e.run_t_cheat));
	// Which save this attempt was already resumed from, if any.  Only `retry`
	// reads it back -- a load overwrites it with its own slot -- but without it
	// a retry of a shadow run restores TF_SHADOW from `flags` and then reports
	// "shadow run from save 0" at the finish.
	fputs(f, sprintf("fromsave %d\n", e.run_t_fromsave));

	/*
	  The occupancy latches, VERBATIM.

	  These are "which zones am I already standing in, and which have already
	  fired".  A save taken inside a stage box has to restore them or the very
	  next tick sees the box as newly entered and fires the split again -- which
	  is the difference between "exactly like it was" and "nearly".
	*/
	fputs(f, sprintf("azone %d\n", e.run_t_azone));
	fputs(f, sprintf("evzone %d\n", e.run_t_evzone));
	fputs(f, sprintf("armzone %d\n", e.run_t_armzone));
	fputs(f, sprintf("cpzone %d\n", e.run_t_cpzone));
	// Patch 436: written, and the loader drops it -- see the `pendarm` key in
	// SV_SaveApplyState.  Keeping the line costs nothing and keeps the file's
	// shape stable for an older build that still restores it.
	fputs(f, sprintf("pendarm %d\n", e.run_t_pendarm));
	/*
	  BUILD 19: the checkpoint high-water mark, which is a latch in exactly the
	  same sense as the four above it.  Without it, resuming a save taken past
	  checkpoint 2 lets you collect 1 and 2 again on the way back through --
	  their times would overwrite the run's, and on a PB the .pb file would
	  record gates reached the second time round.
	*/
	fputs(f, sprintf("cpmax %d\n", e.run_t_cpmax));

	// The splits actually set this run, one line each.  Zeroes are skipped:
	// a segment with no split is not the same as a segment completed in 0.
	for (i = 1; i < FS_MAXSPLITS; i = i + 1)
		if (SV_TimerGetRunSplit(e, i) > 0)
			fputs(f, sprintf("runsplit %d %d\n", i, SV_TimerGetRunSplit(e, i)));

	/*
	  BUILD 23: and the checkpoint times, which this file has never carried.

	  cpmax above restores WHICH checkpoints have been passed; this restores WHEN.
	  Without it a retried run reaches the finish with an all-zero checkpoint row,
	  and if that run is a personal best SV_TimerFinish copies the zeroes into
	  run_pb_cp and SV_PBSave then writes a .pb with no cp lines at all -- the
	  map's checkpoint records deleted by the act of beating your own time.  See
	  SV_TimerGetRunCP in sv_timer.qc.

	  Zeroes skipped for the same reason as the splits: a checkpoint not yet
	  reached is not a checkpoint reached at tick 0.
	*/
	for (i = 1; i < FS_MAXCPS; i = i + 1)
		if (SV_TimerGetRunCP(e, i) > 0)
			fputs(f, sprintf("runcp %d %d\n", i, SV_TimerGetRunCP(e, i)));

	// The recorder.
	fputs(f, sprintf("reclines %d\n", mark));
	fputs(f, sprintf("recsamples %d\n", e.rec_rec_n));
	fputs(f, sprintf("recpad %d\n", e.rec_rec_padn));
	fputs(f, sprintf("reccp %d\n", e.rec_rec_cp));
	fputs(f, sprintf("recserial %d\n", e.rec_rec_serial));
	SV_RecSaveKeys(e, f);           // Patch 375: the lineage, and a stream's counters

	fclose(f);
};

/*
===========================================================================
  Reading a save
===========================================================================
*/
/*
  The light row -- what the list, the HUD and the per-tick hold need.

  Read for every slot at map load, which is why it is separated from the full
  restore below: thirty-two of these is thirty-two small files, and none of them
  needs the run state until somebody actually presses load.

  Returns the seq, or -1 if the file is not a save state we understand.
*/
float(float id, float row) SV_SaveReadLight =
{
	local filestream f;
	local string k;
	local float n, seq, dem;
	local vector v;

	f = fopen(SL_StatePath(id), FILE_READ);
	if (f < 0)
		return -1;

	seq = -1;
	dem = FALSE;

	rec_sl_org [row] = '0 0 0';
	rec_sl_vel [row] = '0 0 0';
	rec_sl_pit [row] = 0;
	rec_sl_yaw [row] = 0;
	rec_sl_duck[row] = 0;
	rec_sl_id  [row] = id;
	rec_sl_tick[row] = 0;
	rec_sl_seg [row] = 0;
	rec_sl_cps [row] = 0;

	while ((k = fgets(f)) != "")
	{
		n = tokenize(k);
		if (n < 2)
			continue;
		k = argv(0);

		// The two VECTORS below need a real local on the way into the array --
		// an array element is not an lvalue fteqcc will swizzle, which is the
		// same thing SV_ZoneMove needs zone_centre for.  The floats are fine
		// assigned straight in.
		if (k == "seq")      { seq = stof(argv(1)); continue; }
		if (k == "ticks")    { rec_sl_tick[row] = stof(argv(1)); continue; }
		if (k == "seg")      { rec_sl_seg [row] = stof(argv(1)); continue; }
		if (k == "reccp")    { rec_sl_cps [row] = stof(argv(1)); continue; }
		if (k == "duck")     { rec_sl_duck[row] = stof(argv(1)); continue; }
		if (k == "demoted")  { dem = TRUE; continue; }     // Patch 428

		if (k == "origin")
		{
			if (n >= 4)
			{
				v = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
				rec_sl_org[row] = v;
			}
			continue;
		}
		if (k == "velocity")
		{
			if (n >= 4)
			{
				v = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
				rec_sl_vel[row] = v;
			}
			continue;
		}
		if (k == "angles")
		{
			if (n >= 3)
			{
				rec_sl_pit[row] = stof(argv(1));
				rec_sl_yaw[row] = stof(argv(2));
			}
			continue;
		}
		// anything else: skipped, by the grammar's own rule
	}
	fclose(f);
	if (dem)
		rec_sl_tick[row] = SL_DEMOTED;

	/*
	  A file with no `seq` is not one of ours -- or is one of ours that was
	  half-written when something went wrong, which amounts to the same thing.
	  Refusing it here is what keeps a torn file out of the list rather than in
	  it at position zero.
	*/
	return seq;
};

/*
  The full restore.  Everything the light read skipped, applied straight to the
  player.  Returns TRUE if the file was readable.

  ORDER MATTERS ONCE, at the end: the recorder is rewound AFTER the timer is
  restored, because the `resume` record it writes carries the restored tick.

  `retry` SWITCHES TWO BEHAVIOURS, and the difference is exactly what the marking
  means:

    * A LOAD gives you a position you did not travel to, so the attempt is
      practice from then on, and a running one is a shadow run.  That is right,
      and it is why loading a save cannot set a PB.

    * A RETRY does not move you at all -- the MAP was reset around you.  So the
      attempt is restored verbatim, flags and all, including whether it was
      already practice.  Forcing practice here would make `retry` useless for a
      real run, which is the entire point of the feature.

  A retry also has to PLACE the player, which a load does not: SV_SaveLocPlace
  does that from the in-memory rec_sl_* arrays, and the retry point is slot 0 --
  deliberately outside the list, so it has no row.  Hence the four position keys
  below, which the loader has always skipped.
*/
// Patch 441: this call cancelled the run (a failed rewind under a RUNNING save),
// which means SV_TimerVoid cleared the occupancy latches and the taint the load
// wrote is no longer on a run.  Set on EVERY call (above the fopen, so a failed
// read cannot leave a stale TRUE) and read by SV_SaveLocLoad's arm gate -- the one
// reader, the other two callers (SV_RetryApply, SV_MsApply) ask nothing of it.
float sl_voided;

float(entity e, float id, float retry) SV_SaveApplyState =
{
	local filestream f;
	local string k;
	local float n;
	local float ticks, elapsed, haveelapsed, mark, samples, padn, cps, serial;
	local float st, tr, ss, sg, sgs, spl, dlt, flg, pbv, dty, rfrom;
	local float cht;                // build 44, the cheat latch
	local float srun;               // build 57, a stage-only run; -1 = the key was absent
	local float az, ez, am, cz, cmx;
	local float rpit, ryaw, rduck;
	local float wasrec;             // Patch 426: recording when the rewind began
	local float hadrec;             // Patch 441 r3: ...and when the LOAD began
	local string drid;              // Patch 426: the run the Patch 360 discard kept
	local vector rorg, rvel;

	sl_voided = FALSE;
	f = fopen(SL_StatePath(id), FILE_READ);
	if (f < 0)
		return FALSE;

	// Defaults are "what an idle timer looks like", so a save file missing a key
	// restores a sane state rather than an undefined one.
	ticks = elapsed = haveelapsed = mark = samples = padn = cps = serial = 0;
	st = TS_IDLE; tr = ss = sg = spl = dlt = flg = pbv = dty = rfrom = 0;
	cht = 0;                        // a pre-44 save file knows nothing about it
	srun = -1;                      // a pre-57 save file: derived from startseg below
	sgs = 1;
	az = ez = am = cz = -1;
	cmx = 0;                        // a pre-19 save file has reached no checkpoint
	rpit = ryaw = rduck = 0;
	rorg = e.origin;                // a file with no origin leaves you where you are
	rvel = '0 0 0';

	SV_RecKeysReset();              // Patch 375

	// The splits are cleared BEFORE the file is read, not after: a save with
	// fewer splits than the run currently in progress must not inherit the
	// leftovers of the one it is replacing.
	SV_TimerClearSplits(e);

	while ((k = fgets(f)) != "")
	{
		n = tokenize(k);
		if (n < 2)
			continue;
		k = argv(0);

		if (k == "state")      { st  = stof(argv(1)); continue; }
		if (k == "track")      { tr  = stof(argv(1)); continue; }
		if (k == "startseg")   { ss  = stof(argv(1)); continue; }
		if (k == "stagerun")   { srun = stof(argv(1)); continue; }
		if (k == "seg")        { sg  = stof(argv(1)); continue; }
		if (k == "segs")       { sgs = stof(argv(1)); continue; }
		if (k == "ticks")      { ticks = stof(argv(1)); continue; }
		if (k == "elapsed")    { elapsed = stof(argv(1)); haveelapsed = TRUE; continue; }
		if (k == "split")      { spl = stof(argv(1)); continue; }
		if (k == "delta")      { dlt = stof(argv(1)); continue; }
		if (k == "flags")      { flg = stof(argv(1)); continue; }
		if (k == "pb")         { pbv = stof(argv(1)); continue; }
		if (k == "dirty")      { dty = stof(argv(1)); continue; }
		if (k == "cheat")      { cht = stof(argv(1)); continue; }

		if (k == "azone")      { az = stof(argv(1)); continue; }
		if (k == "evzone")     { ez = stof(argv(1)); continue; }
		if (k == "armzone")    { am = stof(argv(1)); continue; }
		if (k == "cpzone")     { cz = stof(argv(1)); continue; }
		/*
		  Patch 436: `pendarm` is READ AND DROPPED, deliberately -- an unknown key
		  would be skipped anyway, but a key the writer still writes and the reader
		  silently ignores is exactly the drift the grammar block exists to prevent,
		  so it is named here.  A pending arm is an arm that has not happened, and
		  SV_TimerArm zeroes run_t_flags when it does: see the restore below.
		*/
		if (k == "pendarm")    { continue; }
		if (k == "cpmax")      { cmx = stof(argv(1)); continue; }

		if (k == "fromsave")   { rfrom = stof(argv(1)); continue; }

		/*
		  The position keys, read only because `retry` has no rec_sl_* row to be
		  placed from.  A load ignores these and goes through SV_SaveLocPlace,
		  which has already run by the time this is called.
		*/
		if (k == "origin")   { if (n >= 4) rorg = [stof(argv(1)), stof(argv(2)), stof(argv(3))]; continue; }
		if (k == "velocity") { if (n >= 4) rvel = [stof(argv(1)), stof(argv(2)), stof(argv(3))]; continue; }
		if (k == "angles")   { if (n >= 3) { rpit = stof(argv(1)); ryaw = stof(argv(2)); } continue; }
		if (k == "duck")     { rduck = stof(argv(1)); continue; }

		if (k == "reclines")   { mark    = stof(argv(1)); continue; }
		if (k == "recsamples") { samples = stof(argv(1)); continue; }
		if (k == "recpad")     { padn    = stof(argv(1)); continue; }
		if (k == "reccp")      { cps     = stof(argv(1)); continue; }
		if (k == "recserial")  { serial  = stof(argv(1)); continue; }
		if (SV_RecKeyRead(k, n))  continue;   // Patch 375

		if (k == "runsplit")
		{
			if (n >= 3)
				SV_TimerSetRunSplit(e, stof(argv(1)), stof(argv(2)));
			continue;
		}

		// BUILD 23.  Additive by this format's own rule, so a state.txt written
		// by build 22 simply has no runcp lines and restores as it always did --
		// which is the pre-existing behaviour, not a new failure.
		if (k == "runcp")
		{
			if (n >= 3)
				SV_TimerSetRunCP(e, stof(argv(1)), stof(argv(2)));
			continue;
		}
	}
	fclose(f);

	/*
	  Patch 441 round 3: DID THIS RUN HOLD A RECORDER WHEN THE LOAD BEGAN, taken
	  HERE and not at the rewind.  The Patch 360 discard below clears TF_RECORDING
	  (SV_RecDiscard does it unconditionally, sv_timer.qc:5034), so `wasrec` -- read
	  far below, where Patch 426 wants it -- "recording when the rewind began" --
	  answers FALSE for every run that has posted a stage.  The failed-rewind branch
	  was asking that question of `wasrec` and so could not see a recorder this very
	  function had just thrown away: one stage boundary plus a `reclines 0` save was
	  a RUNNING attempt continuing with no recorder, which is Patch 434's own defect
	  and the third wrong predicate in as many rounds.  Both readings are kept
	  because they answer different questions at different moments.
	*/
	hadrec = e.run_t_flags & TF_RECORDING;

	// Patch 360: a run that posted stages keeps its recording as it stands, before
	// the restore below rewrites its clock and flags and the rewind drops it.
	drid = "";
	if (e.rec_rec_posts > 0)
	{
		drid = strcat(e.rec_rec_rid);
		SV_RecDiscard(e);
	}

	/*
	  Place the player, retry only.  Same shape as SV_SaveLocPlace, including
	  the pitch in BOTH angle fields -- the engine transmits .angles rather than
	  .v_angle whenever fixangle is set (sv_send.c:1535), so writing [0,yaw,0]
	  would silently drop the pitch.
	*/
	if (retry)
	{
		setorigin(e, rorg);
		e.velocity = rvel;
		SV_ClearCarrier(e);     // Patch 400, as SV_SaveLocPlace
		e.angles   = [rpit, ryaw, 0];
		e.v_angle  = e.angles;
		e.fixangle = TRUE;
		e.run_forceduck = rduck ? FD_DUCK : FD_STAND;
		SV_TimerWarped(e);

		/*
		  EVERY MOVER IN THE MAP JUST WENT BACK TO ITS SPAWN STATE, so a spot
		  that was open air when the point was written can be inside a door or
		  a lift now.  Warn rather than refuse: refusing would strand the player
		  at the map's spawn having asked not to be moved, and `!r` is one key
		  away.  tracebox against self so we test the player's own hull.
		*/
		tracebox(e.origin, e.mins, e.maxs, e.origin, FALSE, e);
		if (trace_startsolid)
			sprint(e, PRINT_HIGH,
			       "^3retry: you are inside something -- the map's movers reset\n");
	}

	e.run_t_state    = st;
	e.run_t_track    = tr;
	e.run_t_startseg = ss;
	/*
	  BUILD 57: the leg, from the file where it says, and from startseg where it
	  does not -- a pre-57 save cannot hold a stage-1 run, so startseg > 0 is
	  exactly what "a stage run" meant when it was written.

	  THE STAGE-1 REQUEST COMES BACK WITH IT, because this attempt may be ARMED in
	  the START box.  The very next zone scan re-arms that zone idempotently, and
	  SV_TimerArm re-derives run_t_stagerun from run_t_wantstage1 -- so restoring
	  the leg without the request would quietly turn a saved stage-1 attempt into
	  a full run one tick after the load.  It is set from the restored leg rather
	  than left as it was, so loading a full run also ends a stage-1 request.
	*/
	if (srun < 0)
		srun = (ss > 0);
	e.run_t_stagerun   = srun ? TRUE : FALSE;
	e.run_t_wantstage1 = FALSE;
	if (e.run_t_stagerun)
	if (ss == 0)
	if (tr == 0)
		e.run_t_wantstage1 = TRUE;
	e.run_t_seg      = sg;
	e.run_t_segs     = (sgs > 0) ? sgs : 1;
	e.run_t_split    = spl;
	e.run_t_delta    = dlt;
	e.run_t_pb       = pbv;
	e.run_t_dirty    = dty;

	e.run_t_azone    = az;
	e.run_t_evzone   = ez;
	e.run_t_armzone  = am;
	e.run_t_cpzone   = cz;
	/*
	  Patch 436: A PENDARM IS NOT A LATCH, IT IS AN ARM THAT HAS NOT HAPPENED.

	  SV_TimerFrame's FINISHED branch waits for the body to LEAVE run_t_pendarm's
	  box and then calls SV_TimerArm, which zeroes run_t_flags -- so a save taken
	  after a stage finish, in the next stage's box, restored that pending arm and
	  handed the player a CLEAN stage run at whatever speed the save carried, as
	  often as they liked: load, step out, run.  The legitimate handover is
	  reached by CROSSING the finish, not by being placed in the next box, and the
	  placement is the only thing this restore adds.

	  Not the speed, and not the flags: the restored TF_SEGMENT|TF_PRACTICE is the
	  honest class for a stitched attempt and SV_TimerArm clearing it is what every
	  arm does.  The pending arm is the part the file cannot be allowed to decide,
	  and dropping it costs nothing -- leaving the box starts no run, and walking
	  back through the stage's start arms it the ordinary way.
	*/
	e.run_t_pendarm  = -1;
	e.run_t_cpmax    = cmx;

	/*
	  BUILD 19: a restored run is not a start, so the hop rule is already over.

	  It would settle on its own within FS_STARTSETTLE, since you come back
	  airborne or on a ramp -- but `retry` restores a CLEAN run across a
	  map_restart into a fresh edict where every field reads zero, and leaving
	  this false would put a 0.4-second window at the far end of a two-minute run
	  in which a hop could mark it practice.  Saying so outright is cheaper than
	  reasoning about that window.
	*/
	e.run_t_startok  = TRUE;

	/*
	  TF_RECORDING and TF_FROZEN are NOT restored from the file.

	  Both are statements about something that exists right now -- a buffer, and
	  a hold -- and neither can be true because a file says so.  The file cannot
	  know whether the rewind below is going to succeed; taking TF_RECORDING from
	  the saved flags would leave the HUD claiming a recording that no buffer is
	  backing, and the client would then write a sidecar for a .rec that is never
	  going to be written.  TF_FROZEN would be recomputed away by the next
	  maintain anyway, but a state file that carries it is still lying, and it
	  would be a stopped clock the moment the mirror ever became authoritative.
	*/
	/*
	  Patch 416: TF_NONCE joins the three, from the other side.  A pre-416 save,
	  or one taken before the answer's round trip landed, carries the bit clear
	  and would otherwise CLEAR one the client has already earned -- and a save
	  from another run would hand this one an answer it never gave.  So the file
	  decides nothing about it and the live value stands, until a rewind takes it
	  down deliberately (SV_RecNoncePublish, which runs after this).
	*/
	wasrec = e.run_t_flags & TF_RECORDING;
	e.run_t_flags = (flg - (flg & (TF_RECORDING | TF_FROZEN | TF_STOPPED | TF_NONCE)))
	                | (e.run_t_flags & TF_NONCE);

	/*
	  Prefer the unrounded clock; fall back to the rounded one for a save file
	  written before `elapsed` existed.  The fallback is exactly the half-tick
	  approximation this key was added to remove, so it is degraded rather than
	  wrong -- and the only cost of that is one `resume` join a reader may find
	  a few milliseconds out of order.

	  BUILD 76 CHANGED WHAT THE PAIR MEANS AND DID NOT CHANGE THIS FALLBACK.
	  `ticks` and `elapsed` are now two independent exact readings of one counter
	  rather than a rounded quantity and its original, so on a build-76 file
	  neither is derived from the other.  But a file that has no `elapsed` was
	  written by a build that had no counter either, so `ticks * run_t_tick`
	  remains the best available reconstruction of what IT meant.  Multiplying by
	  run_t_tick rather than the mover's rate is right for the same reason: it is
	  the rate the build that wrote the file was using.
	*/
	if (!haveelapsed)
		elapsed = ticks * run_t_tick;

	/*
	  ONLY A RUNNING CLOCK IS RESUMED.

	  SV_TimerResume recomputes run_t_ticks from the origins it just set, so
	  calling it for a FINISHED state would move them to now and rewrite the
	  finishing time as zero -- erasing the result the save was taken to keep.
	  An idle or armed save has no clock to put back either.

	  BUILD 76: BOTH NUMBERS GO IN, and it is a resume rather than a re-derive.
	  The run's tick count is an integer the mover produced, so the file's `ticks`
	  is restored exactly into run_t_starttick instead of being recomputed from
	  the seconds -- which is what the old single-argument call had to do, and
	  what cost it up to half a tick.  See SV_TimerResume, which got shorter.
	*/
	if (st == TS_RUNNING)
		SV_TimerResume(e, ticks, elapsed);
	else
		e.run_t_ticks = ticks;

	/*
	  Every load is practice.  Only a load of a RUNNING save is a shadow run.

	  The two are not the same claim, and the difference is load-bearing.
	  TF_PRACTICE means "you got here by a route that is not a run", which noclip
	  sets too.  TF_SHADOW means "the clock and the checkpoints came out of the
	  save as well", which is what makes the finished attempt a continuation
	  worth recording under its own name.

	  A save taken while IDLE or ARMED has no run in it to continue.  Marking one
	  TF_SHADOW would be wrong in a way that then sticks: leaving the start zone
	  from a restored ARMED state runs SV_TimerStart directly, and SV_TimerStart
	  does not clear run_t_flags -- only SV_TimerArm does, and no arm happens on
	  that path.  So the flag would survive into a genuinely fresh run and label
	  its recording `_shadow`.  Practice via run_t_dirty is the correct and
	  sufficient marking for those: you did teleport, and that is all that
	  happened.

	  A FINISHED save is excluded for the same reason -- there is nothing left to
	  continue, only a result to look at.

	  NONE OF WHICH APPLIES TO A RETRY, which is why it has its own branch.  A
	  retry did not teleport you and did not give you a clock you had not run
	  for -- the map reset around a player who never moved -- so the attempt is
	  restored exactly as it was written, practice flag and all.  Marking it
	  would mean `retry` could never be used during a real attempt, and using it
	  during a real attempt is the request.
	*/
	if (retry)
	{
		e.run_t_dirty    = dty;
		e.run_t_fromsave = rfrom;

		/*
		  BUILD 43: and the stage taint with it, as closely as the file allows.

		  run_st_dirty is NOT in the save format and is not being added to it: a
		  retry restores an attempt that was written a moment ago by a player who
		  did not move, so the run's own taint is the best available statement
		  about the stage inside it.  The two can disagree in exactly one case --
		  a clean run whose CURRENT stage was dirtied after the save was taken --
		  and there the stage is being under-tainted for one boundary.  Cheap to
		  fix later by widening the save; not worth a format bump for a gesture
		  whose whole premise is that nothing happened.
		*/
		e.run_st_dirty = dty;

		// Build 44, and the same two-field shape one class down: the latch so a
		// retry of an attempt that was cheated before the clock started still is,
		// and the per-stage copy for the same reason run_st_dirty takes one.
		e.run_t_cheat  = cht;
		e.run_st_cheat = cht;
	}
	else
	{
		/*
		  BUILD 43: THROUGH THE FUNNEL, not around it.

		  These were two direct writes -- `run_t_flags |= TF_PRACTICE` and
		  `run_t_dirty = TRUE` -- which is what SV_TimerPractice does plus the
		  per-stage taint it now also owns.  Bypassing it meant the one gesture
		  the "segmented" category is NAMED after would be the one that never set
		  the per-stage field, and a save-locked stage would have been admitted to
		  the stage board as clean.

		  AND THE CHEAT LATCH IS RE-APPLIED FIRST, because the flags restore above
		  can otherwise LAUNDER one.  The word came out of the file, so a run that
		  was clean when the save was taken and has been noclipped since gets its
		  TF_CHEAT wiped by the load and finishes labelled `segmented`.  A load
		  rewinds the clock; it does not rewind your hands.  Nothing about ranking
		  turns on it -- both classes are practice -- but a label that can be
		  removed by a gesture is not a label, and labels are the whole of this
		  build.  run_t_cheat survives because SV_TimerArm is the only thing that
		  clears it, which is exactly what it was made to survive.

		  Caught by a scripted trace and not by reading: it needs a save taken
		  before a cheat and a load taken after one, which is three gestures in an
		  order nobody writes down.

		  BUILD 46: AND IT NEEDS THE run_class GATE, which it did not need when
		  it was written.  This is the third and last place TF_CHEAT is set, and it
		  was safe ungated only because run_t_cheat could not BE true at
		  run_class 0 -- every source of the latch was gated upstream.  Build 46
		  ungated the sv_cheats source on purpose, so without this line the bit
		  would arrive at run_class 0 through a save-load and through nothing
		  else: `cheated` from one gesture and `practice` from every other, which
		  is worse than either answer.  Nothing about ranking turns on it in either
		  direction -- the run is practice from the funnel below regardless.
		*/
		if (e.run_t_cheat)
		if (run_t_runclass)
			e.run_t_flags = e.run_t_flags | TF_CHEAT;

		/*
		  ...AND THEN THE FUNNEL.

		  It prints "practice mode -- this run will not be saved" on a load taken
		  while the clock is running, which the direct writes did not.  That is a
		  new line on screen and it is the truth: the run you just loaded into is
		  not going to be kept.

		  BUILD 44: AND IT IS THE GESTURE THE CLASS IS NAMED AFTER.  A save-lock
		  load is "legit settings, stitched together" verbatim, so it goes through
		  the stitch sibling rather than the bare funnel -- and the line on screen
		  now reads `segmented run` instead of `practice run`, which is the whole
		  of what was asked for one level up.  Under run_class 0 the sibling
		  degrades to exactly the call that was here.
		*/
		SV_TimerStitched(e);

		if (st == TS_RUNNING)
		{
			e.run_t_flags = e.run_t_flags | TF_SHADOW;
			e.run_t_fromsave = id;
		}
		else
			e.run_t_fromsave = 0;
	}

	/*
	  And the movement behind it.  Last, so the `resume` record lands after the
	  rewind and carries the tick the timer was just put back to.

	  A REWIND THAT FAILS MUST DISCARD, and this is the sharp edge of the whole
	  feature.  If it fails while a buffer from some OTHER run is still in hand
	  -- you saved, voided, ran something else, then loaded -- then leaving that
	  buffer alone would append the resumed run's samples onto the tail of an
	  unrelated one, and the file written at the finish would be two runs spliced
	  together with nothing in it to say so.  A recording that is missing is
	  recoverable; one that is quietly wrong is not.
	*/
	// Multi-Session (retry 2): SV_MsApply attaches the recorder and reopens the
	// stage itself -- the slot's counters are in ms.txt, not in this file.
	if (retry == 2)
		return TRUE;
	if (SV_RecRewind(e, SL_RecPath(id), mark, serial, samples, padn, cps))
	{
		// Patch 426: a kept abandon THIS load held (the Patch 360 discard above)
		// never ends for the client -- recording resumed in the same frame -- so
		// its receipt cannot come; a later failed rewind must not hand it one.
		// An earlier abandon's hold is signable and stays.  Told apart by runid:
		// `time` is shared by every packet in one physics step (round 7).
		if (drid != "" && e.rec_end_rid == drid && e.rec_end_ticks == 0)
			SV_RecEndHold(e, "", "", 0);
		/*
		  A DIFFERENT RECORD FOR A RETRY, and not merely for tidiness.

		  A `resume` tells a reader that the .view sidecar jumps FORWARD here by
		  however long the abandoned attempt lasted.  A retry's sidecar jumps
		  BACKWARDS instead: cltime is realtime - cl.mapstarttime and
		  clientcommandframe is cl.movesequence, and the map restart resets both
		  to near zero.  A reader told "resume" would see the sidecar's own two
		  clocks run backwards and have no way to know that was expected.

		  Across a retry the only join key that stays valid is the run clock --
		  field 3 of a .view line, STAT_FS_TIMERTICKS -- because SV_TimerResume
		  makes the .rec's `t` column continuous by construction.
		*/
		// Patch 364: a prefix read off disk opens a new session (v10).
		if (rec_rewind_cold)
			SV_RecPause(e, retry ? "retry" : "load", ticks);
		if (retry)
			SV_RecPut(e, sprintf("retry %d", ticks));
		else
			SV_RecPut(e, sprintf("resume %d %d", id, ticks));

		/*
		  BUILD 43 -- AND THE STAGE HAS TO BE REOPENED, WHICH IS NOT OPTIONAL.

		  run_st_line is an INDEX INTO THE BUFFER THE REWIND JUST MOVED.  A warm
		  rewind sets rec_rec_lines back to `mark`, and the stage in progress was
		  almost certainly opened after that -- so run_st_line now points PAST the
		  end of the recording, and SV_StageClose's [run_st_line, rec_rec_lines)
		  range is empty or inverted.  The `if (rec_rec_lines <= run_st_line)` guard
		  there catches the empty case and writes nothing, which is the safe
		  failure; reopening is the correct one.

		  AFTER the record above, so the `resume` or `retry` line is not the first
		  line of the new slice -- the same ordering SV_StageFail and
		  SV_TimerRestartSeg both document, and for the same reason.

		  It re-arms.  There is no crossing to arm ON, so the arm resolves itself
		  from the boundary box on the next tick exactly as it does after `!r`:
		  land inside it and the stage times from when you leave, land outside and
		  it disarms.  Correct either way.
		*/
		if (e.run_t_state == TS_RUNNING)
		if (e.run_st_seg >= 0)
		{
			SV_StageOpen(e, e.run_t_seg, ticks);

			/*
			  AND PUT THE TAINT BACK, because SV_StageOpen reads it from the
			  LEVEL -- the movetype at this instant -- which is MOVETYPE_WALK for
			  a player who walked to the save key and pressed load.  Opening the
			  stage would therefore launder the load, and the load is the gesture
			  the whole "segmented" category is named after.

			  run_t_dirty and not TRUE: on the retry path it carries the saved
			  attempt's own value, so a retry of a clean run stays clean and a
			  retry of a dirty one stays dirty.
			*/
			e.run_st_dirty = e.run_t_dirty;

			/*
			  BUILD 44: and the CLASS with it, from the run's own word.

			  SV_StageOpen zeroes the stitch half and re-reads the cheat half from
			  the level, and both are wrong here for the reason the paragraph above
			  gives about the umbrella: the level is MOVETYPE_WALK with cheats off
			  for a player who walked to the save key and pressed load.  So the run
			  answers for the stage, exactly as it does for run_st_dirty -- the same
			  over-taint in the same one case (a clean run whose current stage was
			  dirtied after the save was taken) and the same argument for accepting
			  it rather than widening the save format.
			*/
			if (e.run_t_flags & TF_SEGMENT)
				e.run_st_stitch = TRUE;
			if (e.run_t_cheat)
			{
				e.run_st_cheat = TRUE;
				e.run_st_dirty = TRUE;
			}
		}
	}
	else
	{
		/*
		  Patch 434: AND A RUN THAT LOST ITS RECORDING IS OVER.

		  The clock was resumed above, so until now a failed rewind left a
		  RUNNING attempt with no buffer and no stream behind it: it kept
		  counting, it kept posting splits and stages, and its finish filed a
		  time with nothing for pm_verify to replay and no `warp` or `resume`
		  row to explain the gap.  A run whose evidence could not be restored
		  is not a run any more.

		  SV_TimerVoid is the funnel every other abort uses -- it keeps the
		  restored time on screen greyed rather than snapping it to zero, and
		  its SV_TimerIdle does the discard, so this branch must not do it too
		  (a second SV_RecDiscard would re-run the Patch 426 hold logic below
		  against a run that has already ended).

		  PATCH 441 -- TWO CORRECTIONS, the first of which took three rounds.

		  ONLY A RUN WHOSE EVIDENCE WAS EXPECTED:
		      SV_RecEnabled() || hadrec || (retry && mark > 0)
		  -- four rounds for three clauses.  The question is whether this leaves a RUNNING
		  attempt without evidence it was supposed to have, and each clause answers one
		  part of "supposed to":
		    SV_RecEnabled() -- the server writes .rec files at all, so a run with none is
		  anomalous whatever this run's own history is.
		    hadrec -- this run held a recorder when the LOAD began, captured above the
		  Patch 360 discard, which is the whole point of it being a second variable.  The
		  load took evidence away even if the operator has since switched recording off.
		    retry && mark > 0 -- ON THE RETRY PATH ONLY, and it is this run's own prefix.
		  A retry writes state.txt and the prefix moments before the map_restart, and
		  `mark` is `reclines`, which SV_RecWritePrefix returns only AFTER buf_writefile
		  and fclose (sv_timer.qc:5562): a receipt for a file that existed, not a claim.
		  The clause is here because the restart is the one place the other two go blind --
		  the progs are re-initialised, so `hadrec` is structurally 0, which is why the
		  arming flag has to travel in a cvar (:4116) -- and SV_RetryApply then fremoves
		  that prefix.  Without it, `rec_enable 0` under a recorded CLEAN run plus one
		  `retry` left a clean, rankable, RUNNING attempt with no recording and no message
		  of any kind.  NOT on the load path: `mark` is some earlier session's prefix
		  there, and reading it as this run's expectation is how round 2 put the absence
		  trap back.
		  With all three clear, nothing was lost and nothing was expected: the run was
		  already unverifiable by the operator's own configuration before the load arrived,
		  and cancelling THAT is the absence trap -- a check that cannot see answering
		  "guilty".  Patch 434 did exactly that.

		  THREE WRONG PREDICATES CAME BEFORE THIS ONE.  Each is worth its lines because
		  each looks right, and all three were caught by review rather than by me:
		  `SV_RecEnabled()` ALONE -- it asks about the SERVER NOW, not this run.
		  rec_enable is read at SV_RecOpen (sv_timer.qc:4410) and nowhere per sample, so a
		  live recorder survives `rec_enable 0`; SV_RecRewind then refuses on its own copy
		  of that test (sv_timer.qc:5988) and this branch skipped the void while
		  SV_RecDiscard threw the recording away.  Measured, cfg/test/p441mid.cfg:
		  `timer: running` at 0:06.600 with `recorder: buffer -1`.
		  `wasrec` ALONE -- it is captured BELOW the Patch 360 discard, which
		  clears TF_RECORDING (sv_timer.qc:5034), so it reads FALSE for every run that has
		  posted a stage.  And after one failed load the run is not recording either, so a
		  SECOND load of the same row let a RUNNING attempt carry on with no recorder --
		  `sl_goto <n>` being itself a load (sv_player.qc:1046), the pair is one keypress
		  apart.  cfg/test/p441twice.cfg is that arm.
		    `mark > 0 || wasrec` ON EVERY PATH -- `mark` is then a receipt for SOME run's
		  prefix, and reading it as THIS run's expectation cancelled an honest run loading an
		  old save on a server with rec_enable 0: the absence trap, put back.  (`reclines 0`
		  is ambiguous the other way too, "no recorder" or "the prefix write failed"
		  (sv_timer.qc:5556), so it is no evidence of innocence either.)
		    AND `mark` DROPPED ENTIRELY, which is what round 3 did -- that regressed the retry
		  path the round before had been covering by accident.  The fourth round's job was to
		  separate the two cases instead of choosing between them.

		  AND THE LATCHES GO BACK, because SV_TimerVoid clears all four
		  (sv_timer.qc:8736, so a `!r` into the box you are standing in re-arms).
		  Here that left an IDLE timer in the save's start box with azone -1: the
		  next tick is an arm edge, SV_TimerArm clears the load's taint, and leaving
		  the box starts a CLEAN run at the saved speed -- the hole Patch 428 r3
		  closed for a demoted save, reopened through the void.  A scan and not the
		  az/ez/cz this file restored, because a demoted save's are all -1 (r3's own
		  finding).  armzone stays -1: a cancelled run has no zone it armed in.
		*/
		if (st == TS_RUNNING && (SV_RecEnabled() || hadrec || (retry && mark > 0)))
		{
			SV_TimerVoid(e, "the save's recording could not be restored");
			sl_voided = TRUE;
			SV_ZoneScan(e.origin, e.origin, SV_RunHullMins(e), SV_RunHullMaxs(e));
			e.run_t_azone  = zs_az;
			e.run_t_evzone = zs_ez;
			e.run_t_cpzone = zs_cp;
		}
		else
			SV_RecDiscard(e);
		// Patch 426: recording stopped with nothing live to discard, so no end
		// handler cleared the hold -- and the client signs this edge with the
		// RUNTICKS it now sees.  A hold with those ticks would take that
		// receipt as its own (review round 5).  Only if it WAS recording: a
		// save with no recording (mark 0, any START-box save) fails here on
		// every load, and the held finish or this load's kept abandon is still
		// owed its receipt (round 6).
		if (wasrec && e.rec_end_rid != "" && e.rec_end_ticks == e.rec_rec_ticks)
			SV_RecEndHold(e, "", "", 0);
	}

	return TRUE;
};

/*
===========================================================================
  The scan -- the disk IS the list
===========================================================================
*/
/*
  Sort the rows by seq.

  A sort rather than "trust the filename order" because the folder id is
  deliberately NOT the order -- see the header.  Ten parallel arrays swap
  together; a swap that misses one would put one save's origin against another's
  clock, and that failure is silent and would look like the timer being wrong.

  Patch 428: a SHELL sort (gaps 1, 4, 13, 40 ... 364).  The insertion sort it
  generalises was nothing at 24 rows and ~500k row moves at 999 in reverse order.
*/
void(float base, float cnt) SV_SaveSort =
{
	local float i, j, gap;
	local vector vo, vv;
	local float a, b, c, d, g, h, k, m;

	gap = 1;
	while (gap * 3 + 1 < cnt)
		gap = gap * 3 + 1;

	for (; gap >= 1; gap = floor(gap / 3))
	for (i = base + gap; i < base + cnt; i = i + 1)
	{
		vo = rec_sl_org [i];  vv = rec_sl_vel [i];
		a  = rec_sl_pit [i];  b  = rec_sl_yaw [i];
		c  = rec_sl_duck[i];  d  = rec_sl_id  [i];
		g  = rec_sl_seq [i];  h  = rec_sl_tick[i];
		k  = rec_sl_seg [i];  m  = rec_sl_cps [i];

		j = i;
		while (j >= base + gap)
		{
			if (rec_sl_seq[j - gap] <= g)
				break;
			rec_sl_org [j] = rec_sl_org [j - gap];
			rec_sl_vel [j] = rec_sl_vel [j - gap];
			rec_sl_pit [j] = rec_sl_pit [j - gap];
			rec_sl_yaw [j] = rec_sl_yaw [j - gap];
			rec_sl_duck[j] = rec_sl_duck[j - gap];
			rec_sl_id  [j] = rec_sl_id  [j - gap];
			rec_sl_seq [j] = rec_sl_seq [j - gap];
			rec_sl_tick[j] = rec_sl_tick[j - gap];
			rec_sl_seg [j] = rec_sl_seg [j - gap];
			rec_sl_cps [j] = rec_sl_cps [j - gap];
			j = j - gap;
		}

		rec_sl_org [j] = vo;  rec_sl_vel [j] = vv;
		rec_sl_pit [j] = a;   rec_sl_yaw [j] = b;
		rec_sl_duck[j] = c;   rec_sl_id  [j] = d;
		rec_sl_seq [j] = g;   rec_sl_tick[j] = h;
		rec_sl_seg [j] = k;   rec_sl_cps [j] = m;
	}
};

/*
  Build the list from what is on disk.

  The pattern is data/saves/<map>/ then a star then /state.txt -- spelled out in
  words because the literal ends a C comment, which is a lesson this file learnt
  the loud way.

  A wildcard in a MIDDLE path component, which is legal here and was checked
  rather than assumed: Sys_EnumerateFiles2 (client/sys_win.c) splits the pattern
  at the first wildcard and recurses into every directory that matches it.  These
  are loose files we wrote ourselves, so the package search paths are not in the
  way either.

  The id is taken from the folder NAME rather than from inside the file, because
  the name is what the three paths are spelled from -- a file whose `seq` says
  one thing and whose folder says another is still found under its folder.
*/
void(float blk) SV_SaveLocScanBlk =
{
	local searchhandle h;
	local string pre, fn;
	local float i, cnt, id, seq, pl, base, cap, n;

	SV_SaveLocAlloc();              // Patch 428
	base = SL_Base(blk);
	cap  = SL_Cap(blk);
	n    = 0;
	rec_sl_ns[blk] = 1;
	rec_sl_nb[blk] = 0;             // Patch 428 r2: an early return below must not
	rec_sl_scanlob[blk] = 0;        // leave the old rows fresh for a new owner

	/*
	  PATCH 333 -- THE GATE MOVED INTO THE CALLERS, and became a question about
	  WHO rather than WHETHER.  Patch 270 refused the scan in a lobby because the
	  list it filled was shared: an operator's solo practice points landed in
	  front of 32 strangers' delete-all keys.  The scan now fills ONE PLAYER'S
	  block from ONE PLAYER'S directory, so the destruction it enabled is gone
	  with the sharing, and a lobby scan is the ordinary case rather than the
	  refused one.  What remains of 270 is the stamp: a block scanned under one
	  lobby state is not valid under the other, because the root it was read
	  from is not the root the next operation would spell.

	  Below the resets on purpose, as before: a map change must clear the block
	  even when nothing is rescanned into it.
	*/
	if (mapname == "")
		return;

	pre = strcat(sl_root, "/save");
	pl  = strlen(pre);

	h = search_begin(sprintf("%s/*/state.txt", sl_root), SL_NAMESORT, TRUE);
	if (h < 0)
		return;

	cnt = search_getsize(h);
	for (i = 0; i < cnt; i = i + 1)
	{
		if (n >= cap)
			break;

		fn = strtolower(search_getfilename(h, i));
		if (substring(fn, 0, pl) != strtolower(pre))
			continue;

		// FS_SAVENAMELEN characters, because that is what FS_SaveSlotName always
		// writes -- reading the id back by offset is only sound while the width
		// is fixed, which is why that constant lives beside the writer.
		id = stof(substring(fn, pl, FS_SAVENAMELEN));
		if (id < 1 || id > FS_MAXSAVES)
			continue;

		seq = SV_SaveReadLight(id, base + n);
		if (seq < 0)
			continue;               // not a save state, or torn

		rec_sl_seq[base + n] = seq;
		n = n + 1;

		if (seq >= rec_sl_ns[blk])
			rec_sl_ns[blk] = seq + 1;
	}
	search_end(h);

	SV_SaveSort(base, n);

	rec_sl_nb[blk] = n;
	rec_sl_scanlob[blk] = Lobby_Active() + 1;

	if (n > 0)
		dprint(sprintf("saveloc: %g save state(s) under %s\n", n, sl_root));
};

/*
  Per map.  Called from SV_TimerMapInit, which is after mapname is known and
  after the zones are loaded.

  It no longer just clears -- the saves outlive the map change now, which is
  most of the point of putting them on disk.  What it does clear is every
  player's hold and cursor, because those are about a session and not about the
  map.
*/
void() SV_SaveLocReset =
{
	local entity p;
	local float i;

	p = world;
	while ((p = find(p, classname, "player")))
	{
		// Before the list is rebuilt: releasing reads the row it was holding.
		SV_SaveLocRelease(p);

		// And a watch, for the same reason a hold is cleared here: the CSQC VM
		// that opened it was destroyed by the map change, so nothing is left to
		// send the release and the player would spawn on the new map pinned.
		SV_WatchRelease(p);
		p.rec_sl_index = 0;
		p.rec_sl_delall = 0;            // Patch 428: a sweep stops at the map change
	}

	/*
	  PATCH 333: a map change re-roots the paths and invalidates every block --
	  the rows belong to the previous map's directories, shared or personal.
	  Block 0 is rescanned straight away when the lobby is off, which is the old
	  map-init behaviour; in a lobby no block is scanned until that player's
	  next Sync or command asks for it, because there is no single directory
	  that is the map's any more.
	*/
	SV_SaveLocAlloc();              // Patch 428
	sl_root = sprintf("data/saves/%s", mapname);
	sl_lob_last = Lobby_Active();
	for (i = 0; i <= FS_SLCLIENTS; i = i + 1)
	{
		rec_sl_nb[i] = 0;
		rec_sl_ns[i] = 1;
		rec_sl_scanlob[i] = 0;
	}
	if (!Lobby_Active())
		SV_SaveLocScanBlk(0);

	p = world;
	while ((p = find(p, classname, "player")))
	{
		i = rec_sl_nb[SL_Blk(p)];
		if (i > 0)
			p.rec_sl_index = i;
	}
};

/*
  Mirror the global list into the fields that are actually networked, and keep
  the cursor inside it.

  Called once per tick from PlayerPostThink.  clientstat takes a FIELD, so a
  global list cannot be published directly -- and a mirror updated at every
  mutation site instead would be one more thing to remember at each of the five
  places the list changes.  Three float compares a tick is cheaper than that
  bug.
*/
void(entity e) SV_SaveLocSync =
{
	local float blk, base, cnt;
	local entity p;

	SV_SaveLocAlloc();

	/*
	  PATCH 333 -- THE FLIP WATCH.  An operator flipping lobby_enable mid-map
	  moves every player between block 0 and their own block, which is a
	  different directory and a different row set; a hold parked on a row of the
	  old block would re-place its player at somebody else's save.  So the flip
	  drops every hold and every stamp, and the rescan below is the first thing
	  that repopulates anything.  One loop on the frame the cvar moves, not a
	  per-tick cost.
	*/
	if (sl_lob_last != Lobby_Active())
	{
		sl_lob_last = Lobby_Active();
		sl_root = sprintf("data/saves/%s", mapname);
		for (blk = 0; blk <= FS_SLCLIENTS; blk = blk + 1)
		{
			rec_sl_nb[blk] = 0;
			rec_sl_ns[blk] = 1;
			rec_sl_scanlob[blk] = 0;
		}
		p = world;
		while ((p = find(p, classname, "player")))
		{
			SV_SaveLocRelease(p);
			SV_WatchRelease(p);
			if (p.rec_sl_delall)        // Patch 428: its rows are gone with the block
			{
				sprint(p, PRINT_HIGH, sprintf("^3save: delete-all stopped after %g -- the lobby switched\n",
				                              p.rec_sl_delall - 1));
				p.rec_sl_delall = 0;
			}
		}
	}

	blk = SL_Blk(e);
	/*
	  Patch 428 r2: SAVES OFF FOR THIS PLAYER (lobby_nosaveloc, no guid): nothing
	  scanned and nothing published.  The root there is the SHARED folder, and a
	  block filled from it stayed fresh for its guid after the operator turned
	  saves back on -- every sl_ command then spelled that player's own folder
	  with the shared list's folder numbers.
	*/
	if (!SV_SaveLocAllowed(e, TRUE))
	{
		e.rec_sl_count = 0;
		e.rec_sl_index = 0;
		e.rec_sl_savetick = 0;
		e.rec_sl_curorg = '0 0 0';
		e.rec_sl_curang = '0 0 0';
		return;
	}
	if (!SL_Fresh(e, blk))
	{
		SV_SaveRootFor(e);
		SV_SaveLocScanFor(e, blk);
	}

	base = SL_Base(blk);
	cnt  = rec_sl_nb[blk];

	e.rec_sl_count = cnt;

	if (e.rec_sl_index > cnt)
		e.rec_sl_index = cnt;
	if (cnt > 0 && e.rec_sl_index < 1)
		e.rec_sl_index = 1;

	e.rec_sl_savetick = 0;
	e.rec_sl_curorg = '0 0 0';
	e.rec_sl_curang = '0 0 0';
	if (e.rec_sl_index >= 1)
		if (e.rec_sl_index <= cnt)
		{
			e.rec_sl_savetick = rec_sl_tick[base + e.rec_sl_index - 1];
			e.rec_sl_curorg = rec_sl_org[base + e.rec_sl_index - 1];
			e.rec_sl_curang = [rec_sl_pit[base + e.rec_sl_index - 1],
			                   rec_sl_yaw[base + e.rec_sl_index - 1],
			                   rec_sl_duck[base + e.rec_sl_index - 1] ? 1 : 0];
		}
};

// One save/load event out to the client.  See STAT_FS_SLSEQ.
void(entity e, float op, float id) SV_SaveLocEvent =
{
	// FS_SlopPack, not a literal radix -- see STAT_FS_SLOP.  The three decoders
	// are in three other files and one of them is in another VM.
	e.rec_sl_slop = FS_SlopPack(op, id);
	e.rec_sl_slseq = e.rec_sl_slseq + 1;
};

/*
===========================================================================
  The list
===========================================================================
*/
void(entity e) SV_SaveLocSay =
{
	if (rec_sl_nb[SL_Blk(e)] <= 0)
		sprint(e, PRINT_HIGH, "^7saves: ^3none\n");
	else
		sprint(e, PRINT_HIGH, sprintf("^7saves: ^2%g^7/%g\n", e.rec_sl_index, rec_sl_nb[SL_Blk(e)]));
};

/*
  The lowest folder number nobody is using.

  Lowest-free rather than highest-plus-one so the ids stay dense and the folder
  listing stays readable; the ORDER comes from seq, so reusing a hole cannot
  reorder the list.

  BUILD 25: ONE PASS, NOT TWO NESTED ONES.  It used to walk the whole list for
  every candidate id, which at 32 slots was 1,024 compares in the worst case and
  invisible.  At 999 it is a million, on a keypress, and the worst case is the
  ordinary one -- a full list is exactly when every id has to be tested.  Marking
  the used ids into a scratch row first makes it linear.

  rec_sl_used is bare and is not cleared between calls beyond the ids it is about
  to read: only the rows actually in the list are stamped, and only those rows
  are consulted, so a stale mark from a longer list cannot be reached.  The stamp
  is rec_sl_ns[blk], which is monotonic for the life of the block and therefore
  cannot collide with a previous call's.
*/
float  rec_sl_used[FS_MAXSAVES + 1];      // id -> the stamp of the call that used it
float  rec_sl_usedstamp;

float(float base, float cnt) SV_SaveFreeID =
{
	local float id, i;

	rec_sl_usedstamp = rec_sl_usedstamp + 1;

	for (i = 0; i < cnt; i = i + 1)
	{
		id = rec_sl_id[base + i];
		if (id >= 0)
		if (id <= FS_MAXSAVES)
			rec_sl_used[id] = rec_sl_usedstamp;
	}

	for (id = 1; id <= FS_MAXSAVES; id = id + 1)
		if (rec_sl_used[id] != rec_sl_usedstamp)
			return id;

	return 0;
};

/*
  Patch 428: IN A LOBBY ONLY THE NEWEST SL_RECKEEP SAVES KEEP THEIR RUN.
  Every save of a streaming run queues a copy of the stream so far
  (SV_RecSnapshot): 999 are ~1.4 GB of one minute's run on the shared disk, and
  a queue that size is one SV_RecCopyFlush stall.  The save SL_RECKEEP back
  keeps its place and loses its run: the copy goes, and state.txt is rewritten
  as a position with an idle timer, so a load is a teleport that ends the run.
  Review round 2: round 1 only removed the copy, and a cold load of that save
  then resumed its clock with the recording dropped -- a segmented finish
  whose evidence the player had chosen to lose.  Block 0 is a player's own
  machine and always had 999 whole saves.
*/
// Patch 428: what a state file says it is -- seq, run clock (SL_DEMOTED for a
// demoted file) and origin, the columns SV_SaveReadLight filled the row from.
float  sl_fseq, sl_fticks;
vector sl_forg;

float(float id) SV_SaveReadIdent =
{
	local filestream f;
	local string k;
	local float n, dem;

	f = fopen(SL_StatePath(id), FILE_READ);
	if (f < 0)
		return FALSE;
	sl_fseq = -1;
	sl_fticks = 0;
	sl_forg = '0 0 0';
	dem = FALSE;
	while ((k = fgets(f)) != "")
	{
		n = tokenize(k);
		if (n < 2)
			continue;
		k = argv(0);
		if (k == "seq")     { sl_fseq = stof(argv(1)); continue; }
		if (k == "ticks")   { sl_fticks = stof(argv(1)); continue; }
		if (k == "demoted") { dem = TRUE; continue; }
		if (k == "origin")  { if (n >= 4) sl_forg = [stof(argv(1)), stof(argv(2)), stof(argv(3))]; continue; }
	}
	fclose(f);
	if (dem)
		sl_fticks = SL_DEMOTED;
	return TRUE;
};

// ...and whether that is still row r.
float(float r) SV_SaveRowIs =
{
	if (sl_fseq != rec_sl_seq[r] || sl_fticks != rec_sl_tick[r])
		return FALSE;
	return vlen(sl_forg - rec_sl_org[r]) <= 0.01;
};

void(float row) SV_SaveDemote =
{
	local filestream f;
	local float id;
	local vector o, v;

	/*
	  Review round 3: the file must still BE this row -- with two connections on
	  one guid the other may have deleted it (the rewrite would bring it back) or
	  saved a newer one into the number (it would be overwritten).  And the row is
	  marked before the rewrite, the copy removed after it: a rewrite that fails
	  leaves a file the load pre-check refuses, not a clock with no copy behind it.
	*/
	id = rec_sl_id[row];
	if (rec_sl_tick[row] <= 0)
		return;                         // no run to take (idle, armed, or already demoted)
	if (!SV_SaveReadIdent(id) || !SV_SaveRowIs(row))
		return;
	rec_sl_tick[row] = SL_DEMOTED;
	rec_sl_seg [row] = 0;
	rec_sl_cps [row] = 0;
	/*
	  Review round 4: and its SPEED.  A demoted load is an idle timer; its latches
	  come from a zone scan at the %.4f origin, which on a floor-bottom start box
	  lies a hair below the zone -- the first hop into it armed, with the saved
	  speed.  A position at rest has no speed to carry into a start.
	*/
	rec_sl_vel[row] = '0 0 0';

	f = fopen(SL_StatePath(id), FILE_WRITE);
	if (f < 0)
		return;
	o = rec_sl_org[row];
	v = rec_sl_vel[row];
	fputs(f, sprintf("FTESURF-SAVE %d\n", SL_STATE_VERSION));
	fputs(f, sprintf("map %s\n", mapname));
	fputs(f, sprintf("seq %d\n", rec_sl_seq[row]));
	fputs(f, sprintf("origin %.4f %.4f %.4f\n", o_x, o_y, o_z));
	fputs(f, "velocity 0 0 0\n");
	fputs(f, sprintf("angles %.4f %.4f\n", rec_sl_pit[row], rec_sl_yaw[row]));
	fputs(f, sprintf("duck %d\n", rec_sl_duck[row] ? 1 : 0));
	fputs(f, "demoted 1\n");       // for the reader: everything else defaults to an idle timer
	fclose(f);

	SV_RecCopyDrop(SL_RecPath(id));
	fremove(SL_RecPath(id));
};

/*
  Create.  Appended, and the new one becomes current -- so `1` then `2` with
  the menu closed is always "save here, put me back here", which is the whole
  point of the two-key form.
*/
void(entity e) SV_SaveLocCreate =
{
	local float id, seq, row, blk, base, cnt;

	/*
	  PATCH 333 -- THE REFUSAL BECAME A OWNERSHIP.  Patch 270 turned saves off in
	  a lobby because the list had no player dimension: one list, 32 cursors, and
	  a delete-all that reached across players.  The list grew the dimension
	  (SL_Blk) and the disk grew a directory per player (SV_SaveRootFor), so a
	  lobby save is now yours alone -- rows, seq counter, folder and all -- and
	  the gate below is only the two questions that remain: does the operator
	  want saves here at all, and can this player be attributed at all.
	*/
	if (!SV_SaveLocBegin(e, FALSE))
		return;
	// Patch 382: a held body's recording ends in an open `spec` window.
	if (e.run_pmhold)
	{
		sprint(e, PRINT_HIGH, "^3save: stop spectating first\n");
		return;
	}
	// Patch 428 review round 6: a held body is the save's, not a new place --
	// and a save taken under a hold could pass the demotion mark while it was
	// held (hold, step, save... kept rows out of it for good).
	if (e.rec_sl_hold)
	{
		sprint(e, PRINT_HIGH, "^3save: let go of the load key first\n");
		return;
	}

	blk  = SL_Blk(e);
	base = SL_Base(blk);
	cnt  = rec_sl_nb[blk];

	if (cnt >= SL_Cap(blk))
	{
		sprint(e, PRINT_HIGH,
		       sprintf("^3save: the list is full (%g).  Delete one first.\n", SL_Cap(blk)));
		return;
	}

	id = SV_SaveFreeID(base, cnt);
	if (id < 1)
	{
		sprint(e, PRINT_HIGH, "^3save: no free slot number\n");
		return;
	}

	seq = rec_sl_ns[blk];
	rec_sl_ns[blk] = rec_sl_ns[blk] + 1;

	SV_SaveLocAlloc();              // Patch 428: SV_SaveLocBegin's scan has, unless it was stamped fresh
	SV_SaveWriteState(e, id, seq);

	// Read the light row straight back out of the file we just wrote, rather
	// than filling it from the player here.  It is one small read, and it means
	// the list is showing what a load would ACTUALLY restore -- if the write
	// failed or was short, the list says so instead of showing a row that only
	// exists in memory.
	row = base + cnt;
	if (SV_SaveReadLight(id, row) < 0)
	{
		sprint(e, PRINT_HIGH, "^1save: the state file did not come back readable\n");
		return;
	}
	rec_sl_seq[row] = seq;
	rec_sl_nb[blk] = cnt + 1;

	// Patch 428: in a lobby only the newest SL_RECKEEP keep their run.
	if (blk > 0 && cnt >= SL_RECKEEP)
		SV_SaveDemote(base + cnt - SL_RECKEEP);

	e.rec_sl_index = cnt + 1;
	SV_SaveLocEvent(e, SLOP_SAVED, id);

	sprint(e, PRINT_HIGH, sprintf("^7save ^2%g^7 (slot %s)  %s\n",
	                              cnt + 1, SL_NN(id),
	                              (e.run_t_state == TS_RUNNING)
	                                ? SV_TimerString(SV_TimerTicks(e))
	                                : "no run"));
};

/*
  Build 30.  Republish the parked velocity for the row the hold is on.

  One funnel, called from all three places a hold's row can be established --
  the press, a re-point while parked, and the per-tick frame -- so there is no
  path that freezes a player without saying what they are frozen at.  Guarded
  the way every array read in this file is (nested ifs: QuakeC's && evaluates
  both sides and would index the array anyway), and it clears rather than holds
  a stale vector when the row has gone.
*/
void(entity e) SV_SaveLocHoldVel =
{
	e.rec_sl_holdvel = '0 0 0';

	if (!e.rec_sl_hold)
		return;
	if (e.rec_sl_holdrow < 0)
		return;
	if (e.rec_sl_holdrow >= SL_Base(SL_Blk(e)) + rec_sl_nb[SL_Blk(e)])
		return;

	e.rec_sl_holdvel = rec_sl_vel[e.rec_sl_holdrow];
};

/*
  Put the player at row `r`.  Split out from SV_SaveLocLoad because the hold
  calls it every tick and must not re-print, re-arm practice mode, touch the
  timer, or move the cursor while it does.
*/
void(entity e, float r) SV_SaveLocPlace =
{
	setorigin(e, rec_sl_org[r]);
	e.velocity = rec_sl_vel[r];
	SV_ClearCarrier(e);     // Patch 400: Momentum's load passes a velocity to Teleport

	/*
	  THE PITCH GOES IN BOTH, and that is not a style choice -- it is the whole
	  of why a loaded save has never restored the angle you saved it at.

	  .angles on a player is the MODEL's orientation and .v_angle is the view,
	  so writing the real pitch into .angles looks wrong.  But sv_send.c:1535 is

	      ang = ent->v->fixangle ? ent->v->angles : ent->v->v_angle;

	  -- when fixangle is set the engine transmits .angles, NOT .v_angle.  So
	  `[0, yaw, 0]` here meant the saved pitch was dropped on the wire every
	  single time, and only the yaw ever reached the client.  The model is
	  wrong for the one frame before the client's own angles come back, which
	  is what every other correct caller in this codebase already accepts:
	  SV_ZoneGotoAng (sv_zones.qc:513) writes [pitch, yaw, 0] and is the path
	  that has always aimed correctly.  The engine's own setpos (sv_user.c:5605,
	  Patch 165) writes the full triple to both and its comment is this bug.
	*/
	e.angles   = [rec_sl_pit[r], rec_sl_yaw[r], 0];
	e.v_angle  = e.angles;

	// Hand the duck state back to the engine's pmove.  See run_forceduck.
	e.run_forceduck = rec_sl_duck[r] ? FD_DUCK : FD_STAND;

	// A save state is a teleport as far as the swept zone test is concerned.
	SV_TimerWarped(e);
};

void(entity e, float n) SV_SaveLocLoad =
{
	local float r, id, blk, base, cnt, dem;

	/*
	  PATCH 333 -- load goes through the same gate as create: in a lobby the row
	  set is the caller's own block, scanned from their own directory, so the
	  cross-player teleport patch 270 refused is structurally gone rather than
	  refused.  Off-lobby this is the shared list exactly as before.
	*/
	if (!SV_SaveLocBegin(e, FALSE))
		return;
	// Patch 375: a resume's copy owns the part file until it attaches.
	if (e.run_ms_phase)
	{
		sprint(e, PRINT_HIGH, "^3save: wait for the resume to finish\n");
		return;
	}

	blk  = SL_Blk(e);
	base = SL_Base(blk);
	cnt  = rec_sl_nb[blk];

	if (cnt <= 0)
	{
		sprint(e, PRINT_HIGH, "^3save: nothing saved on this map\n");
		return;
	}

	if (n < 1) n = 1;
	if (n > cnt) n = cnt;
	e.rec_sl_index = n;

	r  = base + n - 1;
	id = rec_sl_id[r];

	/*
	  Patch 428 r1: REFUSED BEFORE THE PLACEMENT.  SV_SaveApplyState's only failure
	  is this fopen, and it ran after SV_SaveLocPlace: a teleport that marked
	  nothing -- reachable with two connections on one guid, one deleting the
	  files under the other's list.
	  Round 2: and the file must still BE the row.  The placement is the row, the
	  run state is the file; the other connection saving into this folder number
	  paired one save's position with another's clock.  Refused, not rescanned: a
	  rescan on every refusal would be a stall a player can order at 20/s.
	*/
	if (!SV_SaveReadIdent(id))
	{
		sprint(e, PRINT_HIGH, "^3save: the state file could not be read\n");
		return;
	}
	if (!SV_SaveRowIs(r))
	{
		// Not "rejoin": a rejoin on the same guid keeps the list (SL_Fresh).
		sprint(e, PRINT_HIGH, "^3save: that save changed on disk -- the list rereads at the next map\n");
		return;
	}
	dem = (sl_fticks == SL_DEMOTED);

	SV_SpecRelease(e, "load");          // Patch 382: before the rewind
	SV_SaveLocPlace(e, r);
	e.rec_sl_loadt   = time;            // Patch 428 r3: the load a hold may follow
	e.rec_sl_loadrow = r;
	e.rec_sl_loadseq = rec_sl_seq[r];

	/*
	  BUILD 39 -- "I DID NOT LAND HERE, I WAS PUT HERE", and this was the one
	  placement in the codebase that never said so.

	  trigger_teleport_touch clears this, trigger_teleport_relative_touch now
	  clears this, SV_BhopTeleport clears this.  A load did not -- and a load is
	  the only one of the four that also hands you back a VELOCITY, which is the
	  combination that matters: save while rising, load onto a floor, and the
	  first tick believes it is standing there with your old rise still on the
	  clock.

	  WHAT THIS DOES NOT DO, so nobody assumes it later: it does not close the
	  double-jump hole.  PMSrc_Tick calls CategorizePosition (pm_source.c:2732)
	  BEFORE FullWalkMove, and that re-derives onground from a fresh trace and
	  overwrites whatever sv_user.c:7944 loaded out of this flag.  The jump is
	  Patch 241's problem and Patch 241 solves it.  This is about the QC's own
	  view of the world -- STAT_FS_FLAGS, the HUD's ground regime, Board_Frame's
	  segment kind, the bhop dwell timer -- all of which read the flag and none
	  of which get a trace of their own.

	  HERE AND NOT IN SV_SaveLocPlace, which is where it was first written and
	  which would have been wrong: SV_SaveLocHoldFrame re-calls Place every tick
	  the origin has drifted (:1517), so the clear would land mid-park and flicker
	  the ground flag under a frozen player who is demonstrably standing still.
	  Loading is the event; re-pinning is not.
	*/
	e.flags = e.flags - (e.flags & FL_ONGROUND);

	/*
	  The run state, and it is a full restore rather than a "keep going".

	  SV_SaveApplyState is what makes this a save STATE rather than a save-lock:
	  the clock goes back to the tick it read at the save, the splits behind you
	  become the ones you actually set, the latches go back verbatim so a box you
	  were standing in does not fire again, and the recorder rewinds to the
	  movement you had done by then.
	*/
	if (!SV_SaveApplyState(e, id, FALSE))
		sprint(e, PRINT_HIGH, "^3save: the state file could not be read\n");

	/*
	  Loading WHILE PARKED re-targets the hold rather than fighting it.

	  You can hold 2 and tap 4/5 to walk the list without unfreezing, which is
	  the natural way to find the save you meant.  Without this the next tick's
	  drift check would drag you straight back to the row the hold started on.
	*/
	if (e.rec_sl_hold)
	{
		e.rec_sl_holdrow = r;
		e.velocity = '0 0 0';

		// The published copy follows the re-point, or walking the list while
		// parked would leave the HUD reading the row you started the hold on.
		SV_SaveLocHoldVel(e);
	}

	/*
	  BUILD 47: LOADING AT A START BOX IS HOW YOU PICK A START, NOT A STITCH.

	  A save-lock load taints the attempt -- SV_TimerStitched above sets
	  TF_SEGMENT and TF_PRACTICE, and sl_hold's copy adds its own through
	  SV_TimerFreeze, both of which arrive on ONE keypress because
	  cl_saveloc.qc sends sl_load and sl_hold together.  That is right for a
	  load taken halfway down a map.  It is wrong for the ordinary gesture of
	  putting yourself back at a start box to pick which start you are running
	  from, and there is nothing segmented about walking out of it afterwards.

	  AFTER SV_SaveApplyState ON PURPOSE.  That call restores run_t_azone and
	  run_t_armzone verbatim from the file (the whole point of a save STATE), so
	  anything written before it is overwritten.  It is also exactly why the
	  taint survived: with azone restored to the box you are standing in, the
	  edge test in SV_TimerFrame (`az != e.run_t_azone`) never fires, so
	  SV_TimerArm -- the ONLY thing that launders an attempt -- never runs.

	  SO THIS FORCES THE EDGE AND LETS THE EXISTING MACHINE DO THE REST.
	  SV_TimerArm already zeroes run_t_flags, run_t_said, run_t_hopped and
	  run_t_fromsave, and RE-DERIVES run_t_dirty and run_t_cheat from the live
	  state -- so a player who is actually noclipping or has sv_cheats on stays
	  tainted, which is correct and is why reusing the arm beats writing a
	  parallel clear that would have to remember all six fields.

	  TS_RUNNING is excluded: a save taken mid-run that happens to sit inside a
	  start box is still a resumed run and still owes its TF_SHADOW.  Nothing is
	  printed in the intervening tick either -- SV_TimerClassSay is gated on
	  TS_RUNNING, so the taint that is about to be laundered was never announced.

	  PATCH 415 MEASURED THIS GATE FAILING AND DELIBERATELY LEFT IT ALONE.

	  state.txt stores `origin %.4f`, so on a map whose start zone BOTTOM IS ITS
	  FLOOR the placed origin lands below the zone by that rounding -- bhop_eazy's
	  bottom is 64.031250 and the slot holds 64.0312.  Zone_PointInside's ring test
	  passes and its z-slab test fails by 0.00005, so SV_ZoneStartAt answers -1 and
	  this gate never fires.  Even forced past it the laundering does not complete:
	  the scan cannot see that body in the box either, so `run_t_azone = -1`
	  produces no edge and SV_TimerArm never runs.  Measured -- `arm zone -1
	  (armed from 0)` two seconds after the load, run still reading `segmented,
	  stitch 1, practice 1`.

	  SO A START-BOX LOAD KEEPS A TAINT BUILD 47 SAYS IT SHOULD LOSE -- BUT ONLY
	  WHERE THE ZONE'S BOTTOM IS THE FLOOR, AND THAT IS NOT MOST MAPS.  Measured
	  over the 48 shipped start regions that carry an authored teleDestPos, the
	  only ones where the floor and the bottom can be compared from data: 37 have
	  the destination AT the bottom, where the gate fails as described; 11 have it
	  ABOVE, by up to 189 units (surf_simpsons2, surf_leet_xl_beta7z_swg, others).
	  On those eleven the rounded origin is still inside the slab, the gate fires,
	  the scan sees the body, the edge comes and SV_TimerArm launders normally.

	  WHICH IS WHY IT IS LEFT ALONE RATHER THAN FIXED, and the reason is not scope.
	  `SV_SaveLocPlace` writes `e.velocity = rec_sl_vel[r]` and this function clears
	  the ground flag, so a save taken while carrying speed inside a start box is a
	  prespeed injection into a clean armed attempt -- live TODAY on that quarter of
	  regions, via `sl_load`.  Closing the rounding would extend it to the other
	  three quarters.  The velocity has to be answered first; until then this stays
	  broken in the direction that fails safe.  It is why `!r` (Patch 415) takes the
	  save's ORIGIN through SV_ZoneMove instead of loading it at all.

	  PATCH 435 ANSWERS THE VELOCITY, so the rounding is no longer what decides.
	  The gate asks the ROW what it carries: a save with speed on it does not force
	  the edge, keeps the load's TF_SEGMENT|TF_PRACTICE, and leaving the box starts
	  a practice run at the speed you saved with -- which is what a stitched
	  attempt is for.  A save at rest arms exactly as before.  That is the answer
	  the 37 regions already gave by accident, now given by all of them on purpose,
	  and it is why the rounding is still not worth closing: a gate that fails to
	  fire is no longer an injection, it is a practice run.
	*/
	// Patch 441: NOT AFTER A VOID.  The state is non-RUNNING here because the load
	// just cancelled the run, not because it restored an idle save, and this gate
	// exists to arm a RESTORED save at rest -- forcing the edge would undo the
	// latches SV_SaveApplyState put back and hand the taint-clearing arm straight
	// back.  You start that run by leaving the box and entering it, as anywhere.
	if (!sl_voided)
	if (e.run_t_state != TS_RUNNING)
	if (SV_ZoneStartAt(e, e.origin) >= 0)
	if (SL_RowSpeed(r) < SL_ARM_SPEED)
		e.run_t_azone = -1;

	/*
	  Patch 428 r3: A DEMOTED SAVE ARMS NOTHING.  It restores an idle timer with
	  every latch -1, so in a start or stage box the next tick was an arm edge --
	  SV_TimerArm clears the load's taint -- and leaving the box started a CLEAN
	  run at the saved speed.  The latches are those of where it put you, so a run
	  starts only by leaving and entering a box, as anywhere else.
	*/
	if (dem)
	{
		SV_ZoneScan(e.origin, e.origin, SV_RunHullMins(e), SV_RunHullMaxs(e));
		e.run_t_azone  = zs_az;
		e.run_t_evzone = zs_ez;
		e.run_t_cpzone = zs_cp;
	}

	// fixangle only on the one-shot load.  The hold re-places the origin every
	// tick but must NOT keep stamping the view angles, or you could not look
	// around while parked.
	e.fixangle = TRUE;

	SV_SaveLocEvent(e, SLOP_LOADED, id);

	if (e.run_t_state == TS_RUNNING)
		sprint(e, PRINT_HIGH,
		       sprintf("^5save %g^7 -- run resumed at ^5%s^7, %g checkpoint(s), shadow run\n",
		               n, SV_TimerString(e.run_t_ticks), rec_sl_cps[r]));
	else
		SV_SaveLocSay(e);
};

/*
  Release.  Idempotent, and safe on a player who was never holding -- it is
  called from the key-up, from the deadman below, from PutClientInServer and
  from anything else that needs to be sure.
*/
void(entity e) SV_SaveLocRelease =
{
	if (!e.rec_sl_hold)
		return;

	e.rec_sl_hold = FALSE;

	// MOVETYPE_NONE is 0, so a stored 0 means "it was already frozen when the
	// hold started" -- give back WALK, which is the only thing a player can
	// usefully be here and is what PutClientInServer sets.
	e.movetype = e.rec_sl_holdmove ? e.rec_sl_holdmove : MOVETYPE_WALK;
	e.rec_sl_holdmove = 0;

	/*
	  Hand back the save's velocity.  While frozen it was zero; letting go has
	  to be indistinguishable from a fresh load or "park, then start the
	  section" would always start you from a standstill.

	  Guarded, because the row can have gone away under the hold -- the same
	  nested-if rule every array read in this build follows, since QuakeC's &&
	  evaluates both sides and would read the array anyway.
	*/
	if (e.rec_sl_holdrow >= 0)
		if (e.rec_sl_holdrow < SL_Base(SL_Blk(e)) + rec_sl_nb[SL_Blk(e)])
			e.velocity = rec_sl_vel[e.rec_sl_holdrow];

	// The published copy goes with it.  .velocity is the live answer again from
	// here on, so leaving this set would give the HUD two sources that disagree
	// the moment you move.
	e.rec_sl_holdvel = '0 0 0';

	// And the clock starts again.  This is the single thaw funnel: every way a
	// hold can end -- key-up, the client deadman, the console or menu taking
	// focus, the save being deleted, the list emptying, a map change, respawn,
	// setpos -- arrives here, which is why the freeze is safe to make sticky.
	SV_TimerThaw(e);
};

/*
  Hold / release.  `down` arrives from the client on the key's edges only
  (cl_saveloc.qc filters the repeats), so this is not per-tick traffic.
*/
void(entity e, float down) SV_SaveLocHold =
{
	local float row;

	SV_SaveLocAlloc();
	if (!down)
	{
		SV_SaveLocRelease(e);
		return;
	}

	// Already holding: the client re-sent it.  Not an error -- see the deadman
	// heartbeat in cl_saveloc.qc -- and it must not stack a second movetype.
	if (e.rec_sl_hold)
		return;
	if (e.run_pmhold)                   // Patch 382
	{
		sprint(e, PRINT_HIGH, "^3save: stop spectating first\n");
		return;
	}
	// Patch 428 review round 7: the replay pin and the ghost refuse a hold, and
	// a hold now refuses them -- "the two can never be on at once" (SV_WatchHold).
	if (e.rec_wt_hold || e.rec_gh_on)
		return;
	if (SL_Sweeper(SL_Blk(e)))          // Patch 428: its row is about to go
		return;
	if (!SV_SaveLocAllowed(e, TRUE))
		return;

	if (rec_sl_nb[SL_Blk(e)] <= 0)
	{
		sprint(e, PRINT_HIGH, "^3save: nothing saved on this map\n");
		return;
	}

	/*
	  Patch 428 r2-r4: ONLY RIGHT AFTER A LOAD OF THIS SAVE.  `2` sends sl_load
	  then sl_hold in one reliable message, so a real press always passes.  Every
	  part was a hole on its own: without the load, the hold's re-place and the
	  release's saved velocity were a teleport and a free speed; without the SEQ,
	  a delete in between slid another save under the loaded row; without the
	  ORIGIN (and SV_TimerWarped voiding rec_sl_loadt), a respawn in between put
	  the hold's arm edge on a fresh idle timer -- a clean run from any save.
	*/
	if (e.rec_sl_index < 1 || e.rec_sl_index > rec_sl_nb[SL_Blk(e)])
		return;
	row = SL_Base(SL_Blk(e)) + e.rec_sl_index - 1;
	if (e.rec_sl_loadt != time || e.rec_sl_loadrow != row || e.rec_sl_loadseq != rec_sl_seq[row])
		return;
	if (vlen(e.origin - rec_sl_org[row]) > 1)
		return;

	e.rec_sl_hold    = TRUE;
	e.rec_sl_holdrow = SL_Base(SL_Blk(e)) + e.rec_sl_index - 1;
	e.rec_sl_holdmove = e.movetype;

	e.movetype = MOVETYPE_NONE;
	e.velocity = '0 0 0';

	// ...and the same number published, before the first snapshot of the hold
	// goes out.  Doing it here as well as in the per-tick frame below is what
	// makes the readout correct ON THE PRESS rather than one tick later, which
	// is the whole complaint this build is answering.
	SV_SaveLocHoldVel(e);

	/*
	  BUILD 44 -- THE HOLD IS A STITCH, AND IT IS A RENAMING RATHER THAN A NEW
	  TAINT.

	  A hold has marked the run practice since build 18 and does it inside
	  SV_TimerFreeze below, whose own comment is the argument: "a stopped clock is
	  not something a kept run may have".  Which is right, and it is also exactly
	  what `segmented` means -- park at every hard section, study the line, let go,
	  and the number at the end was never run in one take.  So the word changes and
	  nothing about what is kept does.

	  BEFORE SV_TimerFreeze, DELIBERATELY, and this is the whole reason the call is
	  here rather than left to that function.  SV_TimerFreeze's own
	  SV_TimerPractice would fire first and spend the class message on the word
	  `practice`; the print reports an UPGRADE and there is only one.  Marking here
	  first makes the freeze's call the silent one.

	  AND NOT IN SV_TimerFreeze ITSELF, which has a second caller: opening a REPLAY
	  mid-attempt freezes the clock the same way and is not a save-lock.  Pausing
	  to watch somebody's demo is plain practice, and moving the stitch one level
	  down would have relabelled it on the strength of a shared implementation
	  detail.
	*/
	SV_TimerStitched(e);

	// Build 18: and the clock stops with you.  Studying an approach from a
	// parked position is not time spent on the run, and letting it count made
	// the save-lock unusable mid-attempt.  Only asks -- SV_TimerFreezeFrame
	// does the arithmetic, at a `time` this hook does not have.
	SV_TimerFreeze(e);
};

/*
===========================================================================
  WATCHING A RECORDING.  Build 24.

  `rec_watch 1` pins the player exactly as a save-lock hold does, and for the
  reason the request gave: watching a replay must not start a run or trigger
  anything on the map.  The camera is entirely client-side -- the client sets
  VF_ORIGIN and VF_ANGLES from the file and the server is never told where the
  recording goes -- so this is the whole of the server's involvement.

  IT DELIBERATELY DOES NOT REUSE rec_sl_hold, AND THAT IS THE POINT.

  It would fit: the pin is the same MOVETYPE_NONE, the clock stop is the same
  SV_TimerFreeze, and the release is the same pair undone.  But a save-lock hold
  is a KEY BEING HELD, with a client heartbeat and a deadman and a list row it is
  anchored to; a watch is a mode that stays on until something closes it.  Two
  state machines sharing one flag means every future edit to either has to be
  correct for both, and build 11's dead load key was exactly that failure --
  one missing release left the flag latched and every later press was swallowed
  by a guard that thought the key was still down.

  So: its own field, its own release, and it REFUSES while a save-lock hold is
  live rather than silently taking the movetype out from under it.  The two can
  never be on at once, which is the invariant that makes them independent.

  The client also empties its own usercmd the moment a replay opens
  (CSQC_Input_Frame), so nothing can move between the command being sent and it
  arriving.  This is the half that stops gravity and the movers.
*/
.float rec_wt_holdmove;

/*
===========================================================================
  BUILD 43 -- THE PVS EYE, AND WHY A DETACHED CAMERA NEEDS ONE.

  The essay above says "the server is never told where the recording goes" as
  though it were the end of the design.  It is, for movement -- but not for
  VISIBILITY, and that turned out to be a bug the report found before we did:

      "surf_fiellu Demo playback like on some maps, doesn't show some of the
       models or ramps, playing the map is fine."

  The server builds a client's PVS from client->edict (sv_ents.c:4375) and drops
  every entity that fails it (sv_ents.c:4163).  During a replay client->edict is
  the pinned body, standing wherever the key was pressed, and it never moves --
  so the camera flies away and the entity set stays behind.  The world BSP keeps
  drawing, because it is client-side and follows the overridden view; what
  vanishes is precisely what the SERVER sends.  FTESurf spawns surf ramps as
  func_brush/func_slide and decorations as prop_dynamic, all of them networked
  entities, so what vanishes is "models and ramps".  prop_static survives -- it
  is not an entity at all, it lives in the map's own game lump.

  MEASURED ON surf_fiellu BEFORE ANY OF THIS WAS WRITTEN (cfg/test/b43pvs):
      baseline        entities 324 (brush 0) -> 3 (brush 0) -> 0 (brush 0)
      sv_nopvs 1      entities 268 (brush 41) -> 107 (brush 41) -> 104 (brush 41)
      sv_nopvs 0      entities 164 (brush 0) -> 0 (brush 0)      (matches baseline)
      r_novis 1       entities 217 (brush 0) -> 3 (brush 0)      (fixes NOTHING)
  Forty-one brush entities, present only when the SERVER stops culling.  The
  r_novis arm is the one that makes it a diagnosis rather than a story: it is
  the CLIENT's world cull, and it brought nothing back.

  THE FIX IS AN ENGINE HOOK THAT ALREADY EXISTS.  sv_ents.c:4382-4383 feeds a
  client's `.view2` to SV_AddCameraEntity, which UNIONS a second origin and area
  into the PVS rather than replacing it.  So one invisible marker, moved to the
  camera, and the server's answer becomes "the body OR the camera".  FTESurf has
  never set .view2 anywhere; no engine change is needed.

  ONE FIELD FOR BOTH MODES, AND THE INVARIANT THAT MAKES IT SAFE.  The essay
  above is emphatic that the replay pin must not share rec_sl_hold, and it is
  right -- two state machines sharing one flag means every future edit to either
  has to be correct for both.  This is not that: it is a RESOURCE with one owner
  at a time, and the ownership is already enforced.  A watch refuses under a
  save-lock hold (:1391) and a ghost refuses under a watch (SV_GhostSet), so the
  two callers can never both hold it.  If that ever stops being true this needs
  splitting -- and the reason it would need splitting is written here so the
  next person does not have to derive it.

  THE POSITION COMES FROM THE CLIENT, at a few times a second and only when it
  has moved.  PVS granularity is a whole visleaf, so nothing here wants per-tick
  precision, and a stringcmd per tick to say the camera moved forty units would
  be silly.  See Watch_Camera for the throttle.
===========================================================================
*/
.entity rec_vw_eye;

/*
  Take the eye away.  Called from both releases, and safe to call when there is
  none -- which is the ordinary case for every player who has never opened a
  replay.
*/
void(entity e) SV_ViewEyeDetach =
{
	if (e.rec_vw_eye == world)
		return;

	remove(e.rec_vw_eye);
	e.rec_vw_eye = world;
	e.view2     = world;
};

/*
  Give it one, at `org`, creating it on the first call.

  MOVETYPE_NONE and SOLID_NOT with no model: it exists only to be a second
  origin for FatPVS, so it must not collide, must not be sent to anyone and must
  not touch anything on the way past.  setorigin relinks without running touch
  functions, which is what makes moving it every few frames free of side effects
  -- and is why this does NOT reuse the pinned player as its own eye, which
  would have been simpler and would have driven the timer's zone scan through
  every stage boundary on the map.
*/
void(entity e, vector org) SV_ViewEyeAt =
{
	/*
	  DETACHES rather than merely declining, so the cvar is a real bisection and
	  not a one-way switch.  Read live rather than latched at map init for the
	  same reason: turning it off with a replay already open has to put the
	  entity set back to build 42's on the next snapshot, or an A/B against it
	  measures whatever the eye happened to be pointing at when it was turned
	  off -- which is a third state neither arm describes.
	*/
	if (!cvar("rec_watch_pvs"))
	{
		SV_ViewEyeDetach(e);
		return;
	}

	if (e.rec_vw_eye == world)
	{
		e.rec_vw_eye = spawn();
		e.rec_vw_eye.classname = "rec_view_eye";
		e.rec_vw_eye.movetype  = MOVETYPE_NONE;
		e.rec_vw_eye.solid     = SOLID_NOT;
		e.rec_vw_eye.owner     = e;
		setmodel(e.rec_vw_eye, "");
		setsize(e.rec_vw_eye, '0 0 0', '0 0 0');
		e.view2 = e.rec_vw_eye;
	}

	setorigin(e.rec_vw_eye, org);
};

void(entity e) SV_WatchRelease =
{
	if (!e.rec_wt_hold)
		return;

	e.rec_wt_hold = FALSE;
	SV_ViewEyeDetach(e);

	// MOVETYPE_NONE is 0, so a stored 0 means "already frozen when this
	// started" -- hand back WALK, which is what PutClientInServer sets.  Same
	// argument as SV_SaveLocRelease, and the same trap: a plain restore of a
	// zero would leave the player pinned with nothing left holding them.
	e.movetype = e.rec_wt_holdmove ? e.rec_wt_holdmove : MOVETYPE_WALK;
	e.rec_wt_holdmove = 0;

	SV_TimerThaw(e);
};

void(entity e, float on) SV_WatchHold =
{
	if (!on)
	{
		SV_WatchRelease(e);
		return;
	}

	if (e.rec_wt_hold)
		return;                 // already watching; must not stack a movetype

	/*
	  Refuse under a save-lock hold rather than fight it.  Both want the
	  movetype and both would give it back; whichever released second would hand
	  back a MOVETYPE_NONE it had stored from the other, and the player would be
	  frozen with nothing holding them and no way to ask for a release.
	*/
	if (e.rec_sl_hold)
	{
		sprint(e, PRINT_HIGH,
		       "^3replay: let go of the save-lock key first\n");
		return;
	}
	if (e.run_pmhold)                   // Patch 382
	{
		sprint(e, PRINT_HIGH, "^3replay: stop spectating first\n");
		return;
	}

	e.rec_wt_hold     = TRUE;
	e.rec_wt_holdmove = e.movetype;

	e.movetype = MOVETYPE_NONE;
	e.velocity = '0 0 0';

	/*
	  Seeded at the BODY, not left absent until the first rec_watchpos arrives.
	  A replay opens with the camera on the run's first sample, which on most
	  maps is somewhere near where you were standing anyway -- but for the frame
	  or two before the client's first position lands, an eye at the body gives
	  exactly build 42's entity set rather than an unpredictable one.  Starting
	  from "no worse than before" is cheap here and worth having.
	*/
	SV_ViewEyeAt(e, e.origin + e.view_ofs);

	// And the clock stops, so opening a replay mid-attempt costs nothing.  Only
	// asks: SV_TimerFreezeFrame does the arithmetic, at a `time` this hook does
	// not have -- a client command runs at physicstime and a usercmd at sv.time,
	// which is the build 18 finding.
	SV_TimerFreeze(e);
};

/*
===========================================================================
  GHOST.  Build 30.  The third mode, and the one that is not a pin.

  `rec_ghost 1` detaches the player's CAMERA and leaves the body running.  It is
  here, beside the other two, because the three have to refuse each other and
  because a reader looking for "what can take a player out of ordinary play"
  should find all of them in one place.  It is otherwise their opposite:

      save-lock hold   MOVETYPE_NONE, velocity zeroed, clock frozen
      replay pin       MOVETYPE_NONE, velocity zeroed, clock frozen
      ghost            NOTHING TOUCHED.  The body keeps its movetype, its
                       velocity and its clock, and goes on surfing unattended.

  SO THERE IS NO MOVETYPE TO STORE AND NO RELEASE TRAP.  The bug both of those
  carry -- MOVETYPE_NONE is 0, so a stored 0 has to be restored as WALK or the
  player is left pinned with nothing holding them -- cannot arise here, because
  nothing is ever stored.  That is worth saying out loud rather than leaving as
  an absence, because the obvious way to write a third mode is to copy the
  second one.

  IT STILL REFUSES UNDER THE OTHER TWO, for a different reason than they refuse
  each other.  Not contention over the movetype -- ghost wants none -- but
  because both of them mean the body is FROZEN, and a ghost of a body that
  cannot move is a worse `replay` with none of its controls.  The client also
  refuses to fly while either is open.

  WHAT IT DOES NOT DO, deliberately: it does not mark the run practice.  A
  ghosted run stays valid and is MARKED instead, via TF_GHOST and a pair of
  records in the .rec -- see SV_TimerGhostMark and the essay in sh_defs.qc.
  Ghosting is close to self-policing (a body with no hands on it does not
  survive most maps for long), and where it is not, the marker is what lets a
  leaderboard decide later without re-recording anything.
===========================================================================
*/
void(entity e, float on) SV_GhostSet =
{
	if (!on)
	{
		if (!e.rec_gh_on)
			return;

		e.rec_gh_on = FALSE;
		SV_ViewEyeDetach(e);

		/*
		  The swept test's far end, one last time.  Every ghosted tick warped it
		  already (see the gate in SV_TimerFrame), so this is belt and braces
		  rather than the mechanism -- but the cost is two assignments and the
		  failure it guards against is a run being silently finished by a segment
		  drawn across the map.
		*/
		SV_TimerWarped(e);
		SV_TimerGhostMark(e, FALSE);

		sprint(e, PRINT_HIGH, "^5ghost off^7 -- back in your body\n");
		return;
	}

	if (e.rec_gh_on)
		return;

	if (e.rec_sl_hold)
	{
		sprint(e, PRINT_HIGH, "^3ghost: let go of the save-lock key first\n");
		return;
	}
	if (e.rec_wt_hold)
	{
		sprint(e, PRINT_HIGH, "^3ghost: stop the replay first\n");
		return;
	}
	if (e.run_pmhold)                   // Patch 382
	{
		sprint(e, PRINT_HIGH, "^3ghost: stop spectating first\n");
		return;
	}
	// Patch 373: the restore voids the run first, so a ghost begun here would
	// write no `ghost 1` and leave the later `ghost 0` unpaired.
	if (e.run_ms_phase)
	{
		sprint(e, PRINT_HIGH, "^3ghost: wait for the resume to finish\n");
		return;
	}

	e.rec_gh_on = TRUE;

	/*
	  BUILD 43: the ghost camera has the same stale-PVS defect a replay does, and
	  for the same reason -- rec_gh_camorg is a client-side setproperty and the
	  server is not told about it either.  It is MILDER here only because the
	  body is still moving and so the stale PVS at least drifts, which is why it
	  was never the report.  Same eye, same one-owner rule: a ghost has already
	  refused under a watch four lines above.
	*/
	SV_ViewEyeAt(e, e.origin + e.view_ofs);

	// Mark the recording BEFORE the first ghosted tick is sampled, so the
	// marker sits ahead of the samples it describes rather than one inside them.
	SV_TimerGhostMark(e, TRUE);

	if (e.run_t_state == TS_RUNNING)
		sprint(e, PRINT_HIGH,
		       "^5ghost^7 -- your body is still running; the clock has not stopped\n");
	else
		sprint(e, PRINT_HIGH, "^5ghost^7 -- `ghost` again to go back\n");
};

/*
===========================================================================
  SPECTATE.  Patch 382.  The fourth mode: the body is HELD where it is --
  MOVETYPE_NONE plus .run_pmhold, so the engine runs zero mover ticks and no
  trigger touches it (Patch 380) -- while the client watches another player.
  Velocity is kept.  A ranked run is marked (TF_SPEC and a `spec` pair, grammar
  block), not tainted.  The release is a rollback to the snapshot taken at entry,
  so its `spec 0` restates the `spec 1`.  Refuses under the other three modes and
  they refuse under it (one owner of the movetype and of rec_vw_eye).
===========================================================================
*/

// Serverinfo fs_spec: lobby, avatars and the pose stream.  lobby_av_stream is
// Patch 383's -- a cvar() read before its registercvar would create it empty and
// its default would never land (the trap in Lobby_Frame), so ask whether it exists.
float() SV_SpecOffered =
{
	return (lobby_on && lobby_avatars && lobby_stream);    // Lobby_Frame's cache
};

float sv_sp_fspub;              // fs_spec as last published, plus 1; 0 = not on this map

// StartFrame, after Lobby_Frame refreshed lobby_on/lobby_avatars.  The fs_counts
// pattern (SV_TimerMapInit), on change.
void() SV_SpecPublish =
{
	local float on;

	on = SV_SpecOffered();
	if (sv_sp_fspub == on + 1)
		return;
	sv_sp_fspub = on + 1;
	localcmd(sprintf("serverinfo fs_spec %g\n", on));
};

// Who may be watched: a connected player other than e, with a body.
float(entity e, entity t) SV_SpecTarget =
{
	local float ct;

	if (t == world || t == e || t.classname != "player")
		return FALSE;
	ct = clienttype(t);
	if (ct != CLIENTTYPE_REAL && ct != CLIENTTYPE_BOT)
		return FALSE;
	if (!t.lobby_av)
		return FALSE;
	return SV_SpecOffered();
};

// The first target after entnum `after`, wrapping; world if there is none.
entity(entity e, float after) SV_SpecPick =
{
	local float i;
	local entity p, first;

	first = world;
	i = 1;
	p = edict_num(i);
	while (clienttype(p) != CLIENTTYPE_NOTACLIENT)
	{
		if (SV_SpecTarget(e, p))
		{
			if (i > after)
				return p;
			if (!first)
				first = p;
		}
		i = i + 1;
		p = edict_num(i);
	}
	return first;
};

void(entity e) SV_SpecStat =
{
	if (e.run_sp_phase == 1)
		e.run_sp_stat = num_for_edict(e.pb_watch);
	else if (e.run_sp_phase == 2)
		e.run_sp_stat = -max(1, ceil(e.run_sp_until - time));
	else
		e.run_sp_stat = 0;
};

/*
  The PVS eye while held.  The server steers it (at the target, or at the body in
  the countdown) unless the client claims it with `rec_watchpos x y z` (a freecam);
  the claim lapses SPEC_EYE_STALE after the last one, on a new target, on the
  countdown, or on a bare `rec_watchpos`.
*/
#define SPEC_EYE_STALE 1.0      // 2x cl_keys.qc's PVS_MAXDT: a detached camera re-sends at least that often

void(entity e, string why) SV_SpecEyeServer =
{
	if (e.run_sp_eyeat)
		dprint(sprintf("spectate: %s eye -> server (%s)\n", e.netname, why));
	e.run_sp_eyeat = 0;
};

void(entity e) SV_SpecEyeClient =
{
	if (!e.run_sp_eyeat)
		dprint(sprintf("spectate: %s eye -> client\n", e.netname));
	e.run_sp_eyeat = time;
};

// Once per held packet, and at every change of phase or target.
void(entity e) SV_SpecEyeSteer =
{
	if (e.run_sp_eyeat)
	if (time - e.run_sp_eyeat > SPEC_EYE_STALE)
		SV_SpecEyeServer(e, "stale");
	if (e.run_sp_eyeat)
		return;
	if (e.run_sp_phase == 1)
		SV_ViewEyeAt(e, e.pb_watch.origin + e.pb_watch.view_ofs);
	else
		SV_ViewEyeAt(e, e.origin + e.view_ofs);
};

void(entity e, entity t) SV_SpecWatch =
{
	e.pb_watch = t;
	e.run_sp_uid = stof(infokey(t, "*userid"));
	e.run_sp_phase = 1;
	e.run_sp_lost = FALSE;
	SV_SpecEyeServer(e, "target");
	SV_SpecEyeSteer(e);
	SV_SpecStat(e);
};

// The countdown (run_spec_countdown s) back into the body; `lost`: the target left.
void(entity e, float lost) SV_SpecCount =
{
	e.run_sp_phase = 2;
	e.run_sp_until = time + max(0, cvar("run_spec_countdown"));
	e.run_sp_lost = lost;
	e.pb_watch = world;
	SV_SpecEyeServer(e, "countdown");
	SV_SpecEyeSteer(e);
	SV_SpecStat(e);
};

// The contract's refusal: the reason, and a stuffcmd so the client's pending
// request clears at once rather than timing out.
void(entity e, string why) SV_SpecRefuse =
{
	sprint(e, PRINT_HIGH, sprintf("^3spectate:^7 %s\n", why));
	stuffcmd(e, "spectate _refused\n");
};

void(entity e, float n) SV_SpecStart =
{
	local entity t;
	local float  pend;

	t = edict_num(n);
	if (!SV_SpecOffered())
	{
		SV_SpecRefuse(e, "this server does not offer it");
		return;
	}
	if (t == e)
	{
		SV_SpecRefuse(e, "you cannot watch yourself");
		return;
	}
	if (!SV_SpecTarget(e, t))
	{
		SV_SpecRefuse(e, sprintf("nobody to watch at %g", n));
		return;
	}

	// Already held: a new target, or back from the countdown.  No record.
	if (e.run_sp_phase)
	{
		if (e.run_sp_phase != 1 || e.pb_watch != t)
			SV_SpecWatch(e, t);
		return;
	}

	if (e.rec_sl_hold)
	{
		SV_SpecRefuse(e, "let go of the save-lock key first");
		return;
	}
	if (e.rec_wt_hold)
	{
		SV_SpecRefuse(e, "stop the replay first");
		return;
	}
	if (e.rec_gh_on)
	{
		SV_SpecRefuse(e, "leave ghost first");
		return;
	}
	if (e.run_ms_phase)
	{
		SV_SpecRefuse(e, "wait for the resume to finish");
		return;
	}
	if (e.movetype != MOVETYPE_WALK)
	{
		SV_SpecRefuse(e, "only while walking");
		return;
	}
	if (e.teleport_time)
	{
		SV_SpecRefuse(e, "not during a water jump");
		return;
	}
	// The engine applies a forced duck even on a zero-tick move (sv_user.c:8294).
	if (e.run_forceduck)
	{
		SV_SpecRefuse(e, "a save is still landing");
		return;
	}
	// A trigger's state (a push carrier, a `wait`) would run on in world time under
	// a held body.  run_trig_pkn 0: no touch since connecting.
	if (e.run_trig_pkn)
	if (e.run_trig_pkn >= e.run_pkn)
	{
		SV_SpecRefuse(e, "a trigger is touching you -- step out of it first");
		return;
	}
	pend = SV_TrigPending(e);
	if (pend == 1)
	{
		SV_SpecRefuse(e, "a trigger has not seen you leave yet -- try again");
		return;
	}
	if (pend == 2)
	{
		SV_SpecRefuse(e, "a map output is still due on you -- try again");
		return;
	}

	if (e.run_t_state == TS_RUNNING)
	{
		if (infokey(world, "*pmhold") != "1")
		{
			SV_SpecRefuse(e, "this server's engine cannot hold a running body");
			return;
		}
		if (e.rec_rec_sesspend || e.run_t_starttick == -2)
		{
			SV_SpecRefuse(e, "the run is still resuming");
			return;
		}
		if (e.run_movetickrate <= 0 || !e.run_t_clock || (e.run_t_flags & TF_NOCLOCK))
		{
			SV_SpecRefuse(e, "this run's clock is not counted");
			return;
		}
		// The edge binds to the last `in` row (grammar block).
		if (SV_RecLive(e))
		if (e.rec_rec_in < 1)
		{
			SV_SpecRefuse(e, "the run has not recorded a move yet");
			return;
		}
	}

	e.run_sp_org  = e.origin;
	e.run_sp_vel  = e.velocity;
	e.run_sp_gnd  = e.flags & FL_ONGROUND;
	e.run_sp_gent = e.groundentity;
	e.run_sp_t0   = time;
	e.run_sp_move = e.movetype;
	e.run_sp_eyeat = 0;

	e.movetype = MOVETYPE_NONE;
	e.run_pmhold = 1;
	e.run_t_flags = e.run_t_flags | TF_FROZEN;      // a mirror: the HUD and the .view gate
	if (e.run_t_state == TS_RUNNING)
	{
		e.run_t_flags = e.run_t_flags | TF_SPEC;
		e.run_st_sp = TRUE;
		SV_TimerSpecMark(e, TRUE, "");
	}
	SV_SpecWatch(e, t);
	sprint(e, PRINT_HIGH, sprintf("^5spectate:^7 watching %s -- your body is held\n",
	                              Lobby_ChatName(t)));
};

void(entity e, float n) SV_SpecCmd =
{
	if (n)
		SV_SpecStart(e, n);
	else if (e.run_sp_phase == 1)
		SV_SpecCount(e, FALSE);
};

/*
  The release, from every exit (see the grammar block's <why> list).  Rolls back
  only what the edges state (origin, velocity, FL_ONGROUND; groundentity rides
  with them), so the `spec 0` restates the `spec 1`.  gravity, speedmod and
  basevel are the map's: a write during the hold stands, and the first move after
  it records it (`pm`, `ride pay`) -- restoring them would keep a value the map
  has already reset.  The two world-time latches keyed on the player are rebased
  here; a new one needs a line here too.
*/
void(entity e, string why) SV_SpecRelease =
{
	local string rb;

	if (!e.run_sp_phase)
		return;

	rb = "";
	if (e.origin != e.run_sp_org)
	{
		setorigin(e, e.run_sp_org);         // relinks; touches nothing
		rb = strcat(rb, " origin");
	}
	if (e.velocity != e.run_sp_vel)
	{
		e.velocity = e.run_sp_vel;
		rb = strcat(rb, " velocity");
	}
	if ((e.flags & FL_ONGROUND) != e.run_sp_gnd)
	{
		e.flags = e.flags - (e.flags & FL_ONGROUND) + e.run_sp_gnd;
		rb = strcat(rb, " onground");
	}
	// A zero-tick move can write a stale one (sv_user.c:8547).
	if (e.groundentity != e.run_sp_gent)
	{
		e.groundentity = e.run_sp_gent;
		rb = strcat(rb, " groundentity");
	}

	if (e.vbsp_bhop_since)                          // the func_bhop dwell
		e.vbsp_bhop_since = e.vbsp_bhop_since + (time - e.run_sp_t0);
	if (e.run_t_state == TS_RUNNING)                // `cmd timer`'s sampled side
		e.run_t_startwall = e.run_t_startwall + (time - e.run_sp_t0);

	SV_TimerSpecMark(e, FALSE, why);

	// Engine noclip ("move") changed it: that movetype is the player's now.
	if (e.movetype == MOVETYPE_NONE)
		e.movetype = e.run_sp_move ? e.run_sp_move : MOVETYPE_WALK;

	e.run_pmhold = 0;
	e.run_sp_phase = 0;
	e.run_sp_lost = FALSE;
	e.pb_watch = world;
	e.run_sp_stat = 0;
	e.run_t_flags = e.run_t_flags - (e.run_t_flags & TF_FROZEN);
	SV_ViewEyeDetach(e);
	dprint(sprintf("spectate: %s released (%s) after %.3f s%s\n", e.netname, why,
	               time - e.run_sp_t0, (rb != "") ? strcat(", rolled back:", rb) : ""));
};

// Once per packet from the held PlayerPostThink.
void(entity e) SV_SpecFrame =
{
	local entity t;

	if (e.movetype != MOVETYPE_NONE)
	{
		SV_SpecRelease(e, "move");
		return;
	}

	// The target left, lost its body, or its slot went to someone else.
	t = e.pb_watch;
	if (e.run_sp_phase == 1)
	if (!SV_SpecTarget(e, t) || stof(infokey(t, "*userid")) != e.run_sp_uid)
	{
		t = SV_SpecPick(e, num_for_edict(t));
		if (t)
		{
			SV_SpecWatch(e, t);
			sprint(e, PRINT_HIGH, sprintf("^5spectate:^7 now watching %s\n", Lobby_ChatName(t)));
		}
		else
		{
			SV_SpecCount(e, TRUE);
			sprint(e, PRINT_HIGH, "^3spectate:^7 nobody left to watch\n");
		}
	}

	if (e.run_sp_phase == 2)
	if (time >= e.run_sp_until)
	{
		SV_SpecRelease(e, e.run_sp_lost ? "notarget" : "leave");
		return;
	}

	SV_SpecEyeSteer(e);
	SV_SpecStat(e);
};

// Developer only: moves the held body, which the release must roll back -- the
// rollback's one test subject (nothing honest moves a held body).  Taints.
void(entity e) SV_SpecNudge =
{
	if (!cvar("developer") || !e.run_sp_phase)
	{
		sprint(e, PRINT_HIGH, "^3rec_spec_nudge:^7 developer only, while spectating\n");
		return;
	}
	SV_TimerCheat(e);
	setorigin(e, e.origin + '0 16 0');
	dprint(sprintf("spectate: %s nudged to %v\n", e.netname, e.origin));
};

// ClientConnect: the edict may be a recycled one.  Nothing is written.
void(entity e) SV_SpecForget =
{
	e.run_pmhold = 0;
	e.run_sp_phase = 0;
	e.run_sp_open = FALSE;
	e.run_sp_stat = 0;
	e.pb_watch = world;
	e.run_pkn = e.run_trig_pkn = 0;
};

/*
  Per tick, from PlayerPostThink.  Not the pin any more -- MOVETYPE_NONE is the
  pin.  This is the two things freezing alone cannot do.
*/
void(entity e) SV_SaveLocHoldFrame =
{
	local vector o;

	if (!e.rec_sl_hold)
		return;
	SV_SaveLocAlloc();

	// The list can shrink underneath a hold (3 deletes it, and the menu stays
	// up while you hold 2).  Let go rather than stay frozen against a row that
	// is no longer part of the list.
	if (rec_sl_nb[SL_Blk(e)] <= 0 || e.rec_sl_holdrow < 0
	    || e.rec_sl_holdrow < SL_Base(SL_Blk(e))
	    || e.rec_sl_holdrow >= SL_Base(SL_Blk(e)) + rec_sl_nb[SL_Blk(e)])
	{
		SV_SaveLocRelease(e);
		return;
	}

	/*
	  A frozen player is not an unmovable one: a teleport zone still calls
	  setorigin on them, and so does anything else in this tree that moves a
	  player without asking pmove.  Re-place only when the origin has actually
	  drifted, so the ordinary case sends nothing and cannot re-introduce the
	  per-tick snapping this rewrite exists to remove.
	*/
	o = rec_sl_org[e.rec_sl_holdrow];
	if (e.origin != o)
		SV_SaveLocPlace(e, e.rec_sl_holdrow);

	e.velocity = '0 0 0';
	// Patch 428 review round 7: and no push carrier -- the re-place clears one
	// only when the body drifted, and a push armed on the last held command
	// cashed out into the release packet, before any start clamp.
	SV_ClearCarrier(e);

	// Re-asserted every tick for the same reason the origin above is: the LIST
	// can move under a stationary hold (a delete slides every later row down by
	// one), so the row's velocity has to be re-read rather than remembered.
	SV_SaveLocHoldVel(e);
};

/*
  Delete.  The three files go; the DIRECTORY stays.

  QC has no way to remove a directory -- there is no builtin for it and the
  write sandbox would not reach one anyway -- so an emptied save07/ is left
  behind.  That is deliberately harmless rather than merely tolerated: the scan
  keys on state.txt, so a folder without one is not a save, its id is free for
  reuse, and the next create writes straight back into it.  The cost is one
  directory entry.
*/
// Patch 428: the row half of SV_SaveLocDelete, so a delete-all passes the gate
// once -- SV_SaveLocBegin stuffs cl_saveroot, and 999 of those overflow the
// client's reliable channel.
void(entity e, float n) SV_SaveLocDeleteRow =
{
	local float i, id, r, blk, base, cnt;
	local entity p;

	blk  = SL_Blk(e);
	base = SL_Base(blk);
	cnt  = rec_sl_nb[blk];

	if (cnt <= 0)
	{
		sprint(e, PRINT_HIGH, "^3save: nothing saved on this map\n");
		return;
	}

	if (n < 1) n = 1;
	if (n > cnt) n = cnt;

	r  = base + n - 1;
	id = rec_sl_id[r];

	/*
	  Anyone parked at or after this row lets go FIRST.

	  The bounds check in SV_SaveLocHoldFrame only catches a row that has fallen
	  off the end -- and the rows below the deleted one all slide down, so a hold
	  on row 4 of 6 would survive the delete of row 2 and silently re-place the
	  player at what used to be row 5.  Being teleported to a different save
	  because someone deleted an earlier one is exactly the class of thing that
	  looks like the save list being corrupt.
	*/
	p = world;
	while ((p = find(p, classname, "player")))
		if (p.rec_sl_hold)
			if (p.rec_sl_holdrow >= r)
			if (p.rec_sl_holdrow < base + cnt)  // Patch 428 r1: rows are laid out by slot, so a
				SV_SaveLocRelease(p);           // bare >= reached every higher slot's hold

	/*
	  state.txt FIRST.  It is the file the scan keys on, so if the process dies
	  between these the slot is already gone from the list rather than half
	  present -- and the orphans are overwritten by the next create that reuses
	  the id.

	  FOUR files as of build 20, and the fourth is not optional.  seq.txt is
	  written by the client, so nothing else here would ever remove it; left
	  behind, it would pair with the fresh state.txt of whatever save next reused
	  this id and restore ANOTHER attempt's segment column.  That is the failure
	  class Rec_ViewRetry's own fremove essay describes: it does not look broken,
	  it looks like it worked.
	*/
	SV_RecCopyDrop(SL_RecPath(id));     // Patch 375: a pending copy must not recreate it
	fremove(SL_StatePath(id));
	fremove(SL_RecPath(id));
	fremove(SL_ViewPath(id));
	fremove(SL_SeqPath(id));

	for (i = r + 1; i < base + cnt; i = i + 1)
	{
		rec_sl_org [i - 1] = rec_sl_org [i];
		rec_sl_vel [i - 1] = rec_sl_vel [i];
		rec_sl_pit [i - 1] = rec_sl_pit [i];
		rec_sl_yaw [i - 1] = rec_sl_yaw [i];
		rec_sl_duck[i - 1] = rec_sl_duck[i];
		rec_sl_id  [i - 1] = rec_sl_id  [i];
		rec_sl_seq [i - 1] = rec_sl_seq [i];
		rec_sl_tick[i - 1] = rec_sl_tick[i];
		rec_sl_seg [i - 1] = rec_sl_seg [i];
		rec_sl_cps [i - 1] = rec_sl_cps [i];
	}

	rec_sl_nb[blk] = cnt - 1;

	if (e.rec_sl_index > cnt - 1)
		e.rec_sl_index = cnt - 1;
	if (cnt - 1 > 0 && e.rec_sl_index < 1)
		e.rec_sl_index = 1;

	// Build 25: silent when a delete-all is driving, which would otherwise print
	// one "saves: 39/39" line per row and bury its own summary.
	if (!rec_sl_quiet)
		SV_SaveLocSay(e);
};

void(entity e, float n) SV_SaveLocDelete =
{
	/*
	  PATCH 333 -- delete reaches only the caller's own block, scanned from
	  their own directory, so "somebody's disk" is always the somebody who
	  pressed the key.  What remains of the 270 refusal is the operator's
	  lobby_nosaveloc, inside SV_SaveLocBegin.
	*/
	if (!SV_SaveLocBegin(e, FALSE))
		return;
	SV_SaveLocDeleteRow(e, n);
};

/*
  Previous / next, and THEY LOAD.

  They used to move the cursor and leave you where you were, so cycling to the
  save you wanted took 4,4,4,2 -- and the only way to find out which one 3/7
  actually was, was to load it.  Stepping now teleports you there, which makes
  4 and 5 a walk backwards and forwards along the saves themselves.  Requested;
  and it also makes "Load Save" honest, since it is now the only key that does
  something 4 and 5 do not.
*/
void(entity e, float dir) SV_SaveLocStep =
{
	local float cnt;

	if (!SV_SaveLocBegin(e, FALSE))
		return;

	cnt = rec_sl_nb[SL_Blk(e)];
	if (cnt <= 0)
	{
		SV_SaveLocSay(e);
		return;
	}

	e.rec_sl_index = e.rec_sl_index + dir;

	// Wrap rather than clamp: the menu's 3/4 are a two-key cycle through a
	// short list and stopping dead at the ends makes it feel broken.
	if (e.rec_sl_index < 1)          e.rec_sl_index = cnt;
	if (e.rec_sl_index > cnt)        e.rec_sl_index = 1;

	SV_SaveLocLoad(e, e.rec_sl_index);
};

/*
  First and last.  Build 25, and they are Step's siblings rather than a different
  kind of thing: Momentum's menu offers all four, and if 3 and 4 teleport then 5
  and 6 have to as well or two of the four navigation keys would silently mean
  something else.  SV_SaveLocLoad clamps its argument, so an empty list is the
  same refusal it already prints.
*/
void(entity e) SV_SaveLocFirst =
{
	if (!SV_SaveLocBegin(e, FALSE)) return;
	if (rec_sl_nb[SL_Blk(e)] <= 0) { SV_SaveLocSay(e); return; }
	SV_SaveLocLoad(e, 1);
};

void(entity e) SV_SaveLocLast =
{
	if (!SV_SaveLocBegin(e, FALSE)) return;
	if (rec_sl_nb[SL_Blk(e)] <= 0) { SV_SaveLocSay(e); return; }
	SV_SaveLocLoad(e, rec_sl_nb[SL_Blk(e)]);
};

/*
  Delete every save on this map.

  IT DELETES FROM THE END, one row at a time, through SV_SaveLocDeleteRow.  A loop
  that removed the files itself and then set rec_sl_nb[blk] = 0 would be shorter and
  would skip three things that function does and that this one needs just as
  much: it drops every hold whose row is going away (otherwise a player parked on
  save 4 stays frozen against an array that no longer describes anything), it
  removes ALL FOUR files including the client-written seq.txt (an orphan seq.txt
  pairs with the next save that reuses the id and restores another attempt's
  segment column -- the failure Rec_ViewRetry's essay describes, which does not
  look broken, it looks like it worked), and it keeps the cursor inside the list
  as it shrinks.

  From the END so the slide-down inside SV_SaveLocDeleteRow never has anything to
  move: deleting row 1 of 40 copies 39 rows down, forty times over, for a list
  that is about to be empty.

  The CONFIRMATION IS THE CLIENT'S, deliberately.  This is the one action in the
  menu with nothing to undo it and 7 and 8 are adjacent keys, so the second press
  is required -- but the arm is a 3-second timer belonging to one player's
  keyboard, and putting it here would mean a per-player timer field on the server
  for a decision the server does not otherwise take part in.  A console
  `cmd sl_delall` is deliberately NOT gated: the console is already the place
  where you mean what you type.
*/
#define SL_DELBATCH 2               // Patch 428: rows a server frame; ~7 ms on the Pi

void(entity e) SV_SaveLocDeleteAll =
{
	local float n, blk;

	if (!SV_SaveLocBegin(e, FALSE))
		return;

	blk = SL_Blk(e);

	if (rec_sl_nb[blk] <= 0)
	{
		sprint(e, PRINT_HIGH, "^3save: nothing saved on this map\n");
		return;
	}

	// Patch 428: started here, finished by SV_SaveLocFrame a batch a SERVER
	// FRAME.  One delete measured ~3.5 ms on the Pi (FS_Remove walks every search
	// path to update the name hash), so 999 in this call froze the lobby ~3.5 s.
	// A batch a PACKET froze it just the same: SV_ReadPackets drains the socket
	// in one loop, and a batch as long as the packet interval never lets it end.
	n = rec_sl_nb[blk];
	e.rec_sl_delall = 1;
	if (n > SL_DELBATCH)
		sprint(e, PRINT_HIGH, sprintf("^3deleting %g save state(s)...\n", n));
	SV_SaveLocDeleteAllStep(e);
};

void(entity e) SV_SaveLocDeleteAllStep =
{
	local float blk, i, before;

	blk = SL_Blk(e);
	/*
	  PATCH 333 -- the sweep runs on the caller's own block.  The 270 essay
	  described a spin when the callee declines; the progress check below still
	  guards that, and a gate that closes mid-sweep (lobby_nosaveloc) or a block
	  that went stale (a lobby flip) stops it where it is.
	*/
	if (!SV_SaveLocAllowed(e, TRUE) || !SL_Fresh(e, blk))
		i = -1;
	else
	{
		SV_SaveRootSet(e);          // another player's command may have re-pointed it
		rec_sl_quiet = TRUE;
		for (i = 0; i < SL_DELBATCH && rec_sl_nb[blk] > 0; i = i + 1)
		{
			before = rec_sl_nb[blk];
			SV_SaveLocDeleteRow(e, rec_sl_nb[blk]);
			if (rec_sl_nb[blk] >= before)
			{
				i = -1;             // declined or failed: stop, do not spin
				break;
			}
			e.rec_sl_delall = e.rec_sl_delall + 1;
		}
		rec_sl_quiet = FALSE;
		if (i >= 0 && rec_sl_nb[blk] > 0)
			return;                 // more next frame
	}

	// What was actually removed, not what was planned: they differ if it stopped.
	// No count left: after a lobby flip blk is not the block that was swept.
	if (i < 0)
		sprint(e, PRINT_HIGH, sprintf("^3save: delete-all stopped after %g\n",
		                              e.rec_sl_delall - 1));
	else
		sprint(e, PRINT_HIGH, sprintf("^1deleted^7 all %g save state(s) on %s\n",
		                              e.rec_sl_delall - 1, mapname));
	e.rec_sl_delall = 0;
};

// Patch 428: StartFrame.  ONE batch a server frame, whoever is sweeping --
// two sweeps at once would each cost the frame SL_DELBATCH (review round 1) --
// and the sweeps take turns in entnum order after the last one served (round 2:
// lowest-first let low slots hold a higher slot's list refused).
float sl_sweeplast;

void() SV_SaveLocFrame =
{
	local entity p, first, next;

	SV_SaveLocAlloc();
	first = next = world;
	p = world;
	while ((p = find(p, classname, "player")))
	{
		if (!p.rec_sl_delall)
			continue;
		if (clienttype(p) != CLIENTTYPE_REAL && clienttype(p) != CLIENTTYPE_BOT)
		{
			p.rec_sl_delall = 0;        // left mid-sweep: a departed edict keeps its classname
			continue;
		}
		if (!first)
			first = p;
		if (!next)
		if (num_for_edict(p) > sl_sweeplast)
			next = p;
	}
	if (!next)
		next = first;
	if (!next)
		return;
	sl_sweeplast = num_for_edict(next);
	SV_SaveLocDeleteAllStep(next);
};

/*
  PATCH 415 -- WHERE `!r` should put you, if you left yourself a spot.

      "can you make it when you !r, it loads the last save you placed in the
       start zone if you have one"

  A PLACEMENT, NOT A LOAD, and that distinction is the whole design.  This hands
  back an origin and a view angle and nothing else; `!r` then goes through
  SV_ZoneMove exactly as it always has.  The first cut called SV_SaveLocLoad and
  three independent reviews took it apart for the same reason: a load restores the
  save's whole run state, and `.velocity` is part of that.

      SV_ZoneMove zeroes velocity and clears the push carrier (Patch 400, whose
      comment is "`!r` inside a trigger_push launched you out of the start at the
      push's speed").  SV_SaveLocPlace writes `e.velocity = rec_sl_vel[r]` and the
      load clears the ground flag, so there is no friction tick either.

  So the loading version turned the restart key into a prespeed injector: carry
  speed into the start box -- on a surf map re-entering one while running ARMS
  you outright, and on a bhop map, where SV_TimerTryArm refuses that under
  run_t_bhopjump, voiding first and flying in while idle does the same -- press
  save while the clock reads 0, and every `!r` afterwards hands that velocity back
  into a freshly armed attempt whose `.rec` opens with it in the seed, no lead-in
  and no warp record.  pm_verify would PASS it.  Taking only the origin cannot do
  that, because the placement it feeds zeroes velocity and clears the carrier --
  and the ground snap below is what stops the same trick returning as height.

  It also drops everything else the file could have decided: the leg
  (SV_SaveApplyState overwrites run_t_stagerun/run_t_wantstage1 from `state.txt`,
  so the save was choosing which board your finish filed under), the timer state,
  the taint, the zone latches, and the recorder lineage.  Nothing here is trusted
  but a position, and a position is bounded by the zone test below.

  THE ZONE IS THE LEG'S OWN, not "any start zone".  surf_prosurf has five bonus
  starts; `!r` on bonus 4 must not find the save you left in bonus 1.  Asking
  SV_ZoneStartAt instead would also re-derive the leg and get it wrong where two
  starts share geometry -- surf_aircontrol's bonus-2 start is byte-identical to
  its main one, which is why SV_ZoneMove latches an INDEX (see its essay).

  SV_ZoneOcc, the arm scan's own occupancy test, so a save the timer would not
  call "in the box" is not one this offers.  At the shipped run_t_hullocc 0 that
  is Zone_PointInside -- the ORIGIN in the quad, not the hull overlapping it, and
  the two differ by a hull width at the edges.

  ONLY SAVES TAKEN WITH THE CLOCK STOPPED, through rec_sl_tick, which
  SV_SaveReadLight already carries -- no new column in the ten parallel rec_sl_
  arrays and no new key in state.txt.  `!= 0`, NOT `> 0`: `ticks` comes from a
  file and a negative one is not "not running".  The proxy is faithful because
  SV_TimerArm zeroes run_t_ticks, so an armed attempt writes `ticks 0`; if arming
  ever stops doing that, this reads the wrong thing silently.

  NEWEST BY seq, not by index or slot: ids are stable and lowest-free
  (SV_SaveFreeID), so slot 2 can be newer than slot 7.
*/
float(entity e, float z, __out vector org, __out float yaw, __out float pit)
	SV_SaveLocPickInZone =
{
	local float i, blk, base, cnt, bestseq;
	local vector o, mn, mx, down;

	org = '0 0 0';
	yaw = 0;
	pit = 0;

	if (z < 0 || z >= zone_count)
		return FALSE;
	if (e.run_ms_phase)
		return FALSE;		// a resume owns the part file; let !r do its old thing

	// The policy gates ALWAYS, the scan only when stale.  They are a cvar and an
	// infokey; the directory read is the expensive half and `!r` is a held key.
	// See SV_SaveLocAllowed for what skipping them silently turned off.
	if (!SV_SaveLocAllowed(e, TRUE))	// quiet: this is asking, not being told
		return FALSE;

	SV_SaveLocAlloc();
	blk = SL_Blk(e);
	if (!SL_Fresh(e, blk))
		if (!SV_SaveLocBegin(e, TRUE))
			return FALSE;

	base = SL_Base(blk);
	cnt  = rec_sl_nb[blk];

	mn = SV_RunHullMins(e);
	mx = SV_RunHullMaxs(e);

	bestseq = -1;
	for (i = 0; i < cnt; i = i + 1)
	{
		if (rec_sl_tick[base + i] != 0)
			continue;
		if (rec_sl_seq[base + i] <= bestseq)
			continue;

		// A real local: an array element is not an lvalue fteqcc will swizzle,
		// the same thing SV_SaveLocList needs one for.
		o = rec_sl_org[base + i];
		if (!SV_SaveOriginSane(o))
			continue;
		if (!SV_ZoneOcc(z, SV_SaveZonePoint(z, o), mn, mx))
			continue;

		bestseq = rec_sl_seq[base + i];
		org     = o;
		yaw     = rec_sl_yaw[base + i];
		// Clamped: an edited `angles` pitch reaches the wire, because fixangle
		// makes the engine transmit .angles rather than .v_angle.  One frame and
		// cosmetic -- the client sends its own on the next command -- but there
		// is no reason to pass a file's number through unlooked at.
		pit     = bound(-90, rec_sl_pit[base + i], 90);
	}

	if (bestseq < 0)
		return FALSE;

	/*
	  GROUND-SNAP AND HULL-TEST THE ANSWER, and REFUSE it if either fails.

	  Same shape SV_ZoneDest ends with -- its essay is where the reasoning lives,
	  including why trace_fraction cannot answer "did it land on anything" and why
	  resting exactly on a floor reads solid.  THE FALLBACK IS THE DIFFERENCE and
	  it is the whole reason this is written here rather than shared: a mapper's
	  destination falls back to ITSELF, because the mapper put it somewhere the
	  player fits.  A save carries no such warrant.

	  WITHOUT THE SNAP THE VELOCITY HOLE COMES BACK AS POTENTIAL ENERGY.  A start
	  slab is typically 256 units tall, a save taken mid-jump inside one still has
	  `ticks 0`, and parking the player up there with velocity zeroed lets gravity
	  supply the prespeed instead -- repeatable, and as invisible as the stored
	  velocity was.  Build 47 deleted SV_ZoneDest's unconditional +1 lift on the
	  grounds that "a start position that is not the one you settle at is wrong
	  twice over"; this would have reopened that at up to 250 units and let the
	  player choose it.

	  WITHOUT THE FIT TEST a save taken DUCKED under an overhang, or made inside
	  geometry while noclipping, places a standing hull in solid on every press,
	  with no way out but `!m`.  Neither the picker nor SV_ZoneMoveAt restores
	  run_forceduck -- this is a placement, not a load -- so the duck that made
	  that spot legal is gone.

	  The zone test is re-run on the SNAPPED point: a save floating inside the box
	  whose floor is outside it is not a start you can have.
	*/
	down = org - [0, 0, ZONE_SNAP_DROP];
	tracebox(org, PM_HULL_MINS, PM_HULL_MAXS, down, FALSE, e);
	if (org_z - trace_endpos_z >= ZONE_SNAP_DROP)
		return FALSE;			// nothing under it at all -- SV_ZoneDest's void case

	org = trace_endpos;
	tracebox(org, PM_HULL_MINS, PM_HULL_MAXS, org, FALSE, e);
	if (trace_startsolid || trace_allsolid)
	{
		org = org + '0 0 1';
		tracebox(org, PM_HULL_MINS, PM_HULL_MAXS, org, FALSE, e);
		if (trace_startsolid || trace_allsolid)
			return FALSE;
	}

	/*
	  THROUGH SV_SaveZonePoint AGAIN, and the answer is what gets RETURNED.

	  Two reasons, and the first cost a run of this arm.  A save standing on a
	  floor that IS the zone's bottom traces down zero distance -- it is already
	  resting there -- so the snapped point carries the same sub-ulp shortfall the
	  raw one did, and testing it unlifted rejects the save all over again.  And
	  the placement has to agree with the ARM SCAN about where the body is: hand
	  back a point the zone table calls outside, and at run_zone_hull 0 (the
	  documented A/B control) SV_ZoneIn degrades to the same point test, answers
	  "hull outside" on the first frame, and SV_TimerStart fires with the player
	  standing still on their save.
	*/
	org = SV_SaveZonePoint(z, org);
	return SV_ZoneOcc(z, org, mn, mx);
};

// Patch 428: a window, not the whole list -- 999 rows of this overflow the
// client's reliable channel.  `sl_list <n>` starts at row n; 0 centres the cursor.
#define SL_LISTROWS 30

void(entity e, float from) SV_SaveLocList =
{
	local float i, blk, base, cnt, last;
	local vector o, v;

	if (!SV_SaveLocBegin(e, FALSE))
		return;

	blk  = SL_Blk(e);
	base = SL_Base(blk);
	cnt  = rec_sl_nb[blk];

	if (cnt <= 0)
	{
		sprint(e, PRINT_HIGH, "saveloc: nothing saved on this map\n");
		return;
	}

	if (from < 1)
		from = e.rec_sl_index - floor(SL_LISTROWS / 2);
	from = floor(bound(1, from, max(1, cnt - SL_LISTROWS + 1)));
	last = min(cnt, from + SL_LISTROWS - 1);

	sprint(e, PRINT_HIGH, sprintf("saveloc: %g saved on %s, current %g\n",
	                              cnt, sl_root, e.rec_sl_index));
	for (i = from - 1; i < last; i = i + 1)
	{
		// An array element is not an lvalue fteqcc will swizzle, so both of
		// these need a real local -- the same thing SV_ZoneMove needs for
		// zone_centre.  Three sprintfs, because varargs cap at 8.
		o = rec_sl_org[base + i];
		v = rec_sl_vel[base + i];

		sprint(e, PRINT_HIGH, strcat(
		       sprintf("  %s%2g^7 slot %s  %6.0f %6.0f %6.0f  ",
		               (i + 1 == e.rec_sl_index) ? "^2" : "^7", i + 1,
		               SL_NN(rec_sl_id[base + i]), o_x, o_y, o_z),
		       // Patch 442: the whole vector, like the gate -- a row carrying a
		       // jump's +302 printed "0 u/s  standing", which is how the vertical
		       // half of SL_RowSpeed stayed hidden from anyone reading their list.
		       sprintf("%4.0f u/s  yaw %4.0f  %s  ",
		               vlen(v), rec_sl_yaw[base + i],
		               rec_sl_duck[base + i] ? "ducked" : "standing"),
		       sprintf("%s  stage %g  %g cp\n",
		               (rec_sl_tick[base + i] > 0) ? SV_TimerString(rec_sl_tick[base + i]) : "--",
		               rec_sl_seg[base + i] + 1, rec_sl_cps[base + i])));
	}
	if (from > 1 || last < cnt)
		sprint(e, PRINT_HIGH, sprintf("saveloc: rows %g-%g of %g -- `saveloc <n>` lists from row n\n",
		                              from, last, cnt));
};

/*
===========================================================================
  `retry` -- restart the map's entities without moving the player

  The gesture is Source's: put me back into the game I am already in.  On a
  listen server that is a map reload, which is the surf-practice move -- doors,
  platforms, buttons and the run you triggered by accident all go back to their
  spawn state.  Engine Patch 167 made the command do that.  What it did NOT do
  was keep you where you were, so a retry mid-run cost you the run and the
  walk back, which made it useless for the thing it exists for.

  THIS IS A SAVE STATE WITH A DIFFERENT LIFETIME, and almost none of it is new
  code.  Build 17 already writes origin, velocity, angles, duck, the whole timer
  block, the four occupancy latches, the run splits and the recorder's mark to a
  text file, and already reads them back.  A retry point is that file, parked in
  slot 0, consumed once, and deleted.

  WHY DISK, when this is the same process.  SV_SpawnServer calls PR_Deinit, so
  every SSQC global and every edict is destroyed; on the client side
  CLQW_ParseServerData calls CSQC_Shutdown unconditionally, so the CSQC VM and
  its sidecar buffer go too.  Nothing survives a map_restart in either VM.  Disk
  is not a convenience here, it is the only channel there is.

  THE ORDERING IS NOT A RACE, which is worth stating because it looks like one.
  CL_Retry_f offers the command to CSQC and PR_ExecuteProgram runs QC to
  completion -- so the client's fopen/buf_writefile/fclose of its sidecar is on
  disk before the builtin even returns.  Only then does QC ask the server, via a
  reliable stringcmd, and only then does the server restart the map.  There is
  no interleaving available.

  The honest shortfall: the sidecar covers the run to the KEYSTROKE and the .rec
  covers it to the moment the server handled the command, one client frame and
  one round trip later -- so 1-2 ticks of .rec have no camera behind them.  The
  exact fix is an ack with a timeout, on a gesture that has to feel instant.
  Not worth it; recorded here so the gap is known rather than discovered.
===========================================================================
*/

/*
  rec_retry_armed -- latched from a cvar in SV_TimerMapInit, this map only.  A
  GLOBAL because PR_Deinit zeroes it, which makes it per-map for free.  It is
  DECLARED in sv_timer.qc, which sv_progs.src compiles first and which is where
  the latch happens; this is the code that owns it.

  A map_restart is already queued.

  sv.mapchangelocked guards the changelevel BUILTIN, not localcmd, so two
  `retry`s arriving in the same frame would queue two restarts -- and the second
  would find the point already consumed and simply restart the map again, which
  reads as the command being flaky.  Zeroed by PR_Deinit, so per-map for free.
*/
float rec_retry_sent;

void(entity e) SV_RetryPoint =
{
	local float n;

	if (!cvar("rec_retry"))
	{
		sprint(e, PRINT_HIGH, "^3retry: disabled (rec_retry 0)\n");
		return;
	}
	if (e.classname != "player")
		return;
	if (rec_retry_sent)
		return;

	/*
	  ONE PLAYER ONLY.  A retry restarts the map for everyone on the server, so
	  "whose position is restored" has no good answer with more than one person
	  connected -- and silently restoring the person who typed it while throwing
	  everyone else back to spawn is worse than refusing.  Single-player is what
	  this build is, so this is a guard rather than a limitation.
	*/
	// Patch 382: CONNECTED players -- a departed one's edict keeps its classname
	// (Lobby_PlayerCount), and a spectator left alone must be able to retry.
	n = Lobby_PlayerCount();
	if (n > 1)
	{
		sprint(e, PRINT_HIGH,
		       "^3retry: restarts the map for everyone -- not while others are connected\n");
		return;
	}

	/*
	  LET GO FIRST, and this is not politeness.

	  A save-lock hold zeroes the velocity (SV_SaveLocHold) and keeps it zero
	  every tick, and only SV_SaveLocRelease hands the real one back.  Writing
	  the state under a hold would restore you standing still, silently
	  discarding the speed you had -- and it would write TF_FROZEN into a file
	  with no client left alive to ever send sl_holdoff.  Releasing here makes
	  "retry while parked" mean "let go, then retry", which is the only sane
	  reading of it.
	*/
	SV_SpecRelease(e, "retry");         // Patch 382: before the state is written
	SV_SaveLocRelease(e);

	// Patch 333: the retry point is a slot like any other, and in a lobby its
	// folder lives under the player's own root -- same root a load would spell.
	SV_SaveRootFor(e);

	// Patch 368: a lobby streams, and a stream has no prefix to carry across.
	SV_RecDestream(e);
	SV_SaveWriteState(e, FS_RETRY_SLOT, 0);

	rec_retry_sent = TRUE;
	cvar_set("rec_retry_armed", "1");
	localcmd("map_restart\n");
};

/*
  Consume the retry point.  Called at the END of PutClientInServer, which is the
  first moment at which this player exists AND the map's zones are loaded.
*/
void(entity e) SV_RetryApply =
{
	/*
	  The zones have to be loaded before the state is applied, or the restore puts
	  the position and the splits back and lands in a world with no boxes to be
	  inside.  The ordering is in fact guaranteed (SV_SpawnServer runs two physics
	  frames before any client is put in), but this is one compare against a
	  silent failure, and it is the idiom sv_zones.qc already uses.

	  BUILD 76 RETIRED THE OTHER HALF OF THIS NOTE, which said SV_TimerResume
	  early-returns when run_t_tick is still zero and would therefore silently not
	  restore the clock.  That early return existed to guard a division; the
	  counted clock restores by subtraction and there is nothing to divide, so the
	  guard and the hazard are both gone.  Recorded rather than deleted, because a
	  note describing a defence that no longer exists is worse than no note.
	*/
	if (!zone_loaded)
		SV_ZoneFrame();

	if (!rec_retry_armed)
		return;

	// Exactly once, whatever happens below -- a second player spawning must not
	// re-consume it, and a failed read must not leave it armed for the next map.
	rec_retry_armed = FALSE;

	// Patch 333: same root the retry point was written under.
	SV_SaveRootFor(e);

	if (!SV_SaveApplyState(e, FS_RETRY_SLOT, TRUE))
	{
		sprint(e, PRINT_HIGH, "^3retry: the saved state could not be read\n");
		return;
	}

	SV_SaveLocEvent(e, SLOP_RETRY, FS_RETRY_SLOT);

	/*
	  state.txt first, for the reason SV_SaveLocDelete gives: it is the file the
	  scan keys on, so a crash between these two leaves an orphan .rec rather
	  than a state the reader would try to pair with a missing recording.

	  THE .view IS NOT OURS TO DELETE.  The client has not read it yet -- it
	  learns to, from the stat event above, on its NEXT RENDERED FRAME, which is
	  strictly after this runs.  Removing it here is the one ordering mistake
	  that would make the camera track silently vanish with nothing to show for
	  it.  The client removes its own, on the next retry.
	*/
	fremove(SL_StatePath(FS_RETRY_SLOT));
	fremove(SL_RecPath(FS_RETRY_SLOT));

	if (e.run_t_state == TS_RUNNING)
		sprint(e, PRINT_HIGH,
		       sprintf("^5retry^7 -- run restored at ^5%s^7\n",
		               SV_TimerString(e.run_t_ticks)));
	else
		sprint(e, PRINT_HIGH, "^5retry^7 -- back where you were\n");
};
