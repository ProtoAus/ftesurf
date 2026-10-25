/*
===========================================================================
  cl_triggers.qc -- client-side prediction of the stateless Source triggers.

  Phase 1 of playing on the client.  trigger_teleport, trigger_push and
  trigger_setspeed (and their trigger_momentum_* aliases) fire INSIDE client
  prediction, through CSQC_PredictPlayerMove (engine Patch 335), instead of
  one round trip later as an origin correction the renderer refuses to lerp.
  The push carrier rides predmove_basevel: the engine keeps it across commands
  as the mirror of the server's held .run_basevel/.run_basevel_armed pair and
  runs Patch 249's SV_BaseVelocityFrame per predicted command -- the cash-out
  into real velocity on the first command nothing re-armed it, the window
  hand-over to pmove.basevelocity, and the Z spend -- so push entry, ride and
  exit all land on the same command on both sides.

  THE SERVER STAYS THE AUTHORITY.  sv_entities.qc still runs its own copy of
  every trigger, still writes the .rec `warp` records and still latches the
  clock; nothing here touches a run's certification.  What changes is only
  WHEN the local player feels the trigger.  A snap-back after a trigger now
  means the two simulations disagreed -- that is a bug and should be
  reported; `cl_trigdebug 1` prints every local fire so a report can carry
  the client's half of the story.

  WHAT IS MIRRORED, AND WHAT DELIBERATELY IS NOT:

    * Static lump keys, with the filter mirror (TF_EvalD) resolving the
      statically-decidable filternames exactly as the server does -- failing
      open on missing and unimplemented filters is Source's own semantics --
      and only triggers whose verdict depends on the player's runtime
      targetname (outputs rename the player; bhop_futile's anti-backtrack is
      all of this) stay server-only.
    * Outputs, phase 2b: the Enable/Disable half of entity IO is mirrored.
      A StartDisabled trigger whose enablers are all mirrorable IS predicted
      and runs gated on replicated state; a trigger any unmirrorable output
      can rewrite (relays, buttons, timers, counters, Toggle, delays,
      finite-event wiring from classes the client does not simulate) stays
      server-only, which is the old behaviour and the safe direction.  See
      THE IO MIRROR below for the exact rule set.
    * trigger_push's SF_PUSH_ONCE fires at most once per sequence (see
      tg_onceseq).  A bossfight-style IO self-Disable IS mirrored now, as a
      !self output through the same ring as every other state event.
    * trigger_setspeed's OnThink/Interval re-application is treated as
      enter-edge; Only EveryTick re-applies per command, as on the server.

  Continuous pushes with shared Enable/Disable writers use server gate
  snapshots (Patch 670), including delayed cooldowns and other players' IO.
  Until a snapshot exists they stay server-only. Speed/name rewrites, once
  retirement and movement outputs still require the original proof.

  THE ENTER-EDGE ACROSS CHAIN RESTARTS was the one genuinely new problem.
  The prediction chain replays every unacked command on every rendered
  frame, so per-command state must be REBUILT per chain, not carried -- but
  "was the player already inside this pad at the acked command" is history
  the chain does not replay.  So at each chain start the setspeed pads are
  seeded with a zero-length probe at predmove_org0, which on the chain's
  first command IS the acked position: inside means the enter edge is
  behind the chain and must not re-fire; outside means a pad touched later
  in this chain is a genuine enter.  The server's own gate is the 0.05 s
  staleness window on vbsp_ss_stamp; this is the same decision made from
  sequence adjacency instead of a clock, because the replay has no clock.

  Overlap is the server's SOLID_BSPTRIGGER test rather than a box test:
  tracebox with MOVE_TRIGGERS|MOVE_OTHERONLY clips the player hull against
  the trigger's actual submodel brushes (startsolid OR fraction < 1), which
  is what keeps an angled surf ramp trigger from firing across its whole
  AABB -- the exact fault the SOLID_BSPTRIGGER essay at the top of
  sv_entities.qc exists for.  The clip is ZERO-LENGTH at the command's end
  position and deliberately not a sweep of the move: that is the server's own
  dispatch shape, and the run that measured a sweep found it inventing a
  trigger the server never touched (see TG_Overlaps).

  NAMING: tg_ / tt_ / Trig_, grepped against the tree before the file
  existed.  QuakeC has no file scope.
===========================================================================
*/

#define TG_TELE     1
#define TG_PUSH     2
#define TG_SPEED    3
#define TG_EVENT    4       // trigger_multiple kept as an IO event source only

#define TG_MAX      1024        // triggers kept per map
#define TG_TT_MAX   2048        // targetname rows (destinations, landmarks)

// trigger_setspeed modes, resolved at load; values are sv_entities.qc's.
#define TG_SSH_SETDIR    0
#define TG_SSH_SETSPEED  1
#define TG_SS_INCREASE   2
#define TG_SS_DECREASE   3
#define TG_SS_IGNORE     4
#define TG_SSV_SET       1

// Source spawnflags, sv_entities.qc's copies.
#define TG_SF_TELE_CLIENTS      1
#define TG_SF_TELE_KEEPANGLES   32
#define TG_SF_TRIGGER_CLIENTS   1
#define TG_SF_TRIGGER_ALL       64
#define TG_SF_PUSH_ONCE         128

// SOLID_BSPTRIGGER (pr_common.h:712) -- not in the shipped defs dump, same
// #define as sv_entities.qc's.  It is WHY the probe is exact: 
// World_ClipMoveToEntity resolves the entity's submodel ONLY for
// SOLID_BSP/BSPTRIGGER/PORTAL (world.c); with any other solid it falls back
// to the bounding box, and the first cut of this file measured precisely that
// failure -- a fall-reset carpet whose bbox spans 3858x3426 units fired from
// everywhere under it while the server, clipping the real brushes, never
// fired at all.  SOLID_BSPTRIGGER on the client edict makes the client's
// tracebox clip the same brushes the server's startsolid test clips, and
// stays invisible to every ordinary trace (World_ClipToLinks skips trigger
// solids unless the type carries MOVE_TRIGGERS).
#define TG_SOLID_BSPTRIGGER 22

// pmove.h pmtype_t; PM_SPECTATOR is what MOVETYPE_NOCLIP becomes.
#define TG_PM_OLD_SPECTATOR 1
#define TG_PM_SPECTATOR 2
// QW puts +jump on buttons bit 1 (button2 server-side).
#define TG_BUTTON_JUMP  2

// Engine Patch 335's per-command window.  Declared here, not in the
// generated defs: the defs dump predates the patch, and an engine without
// it simply never calls CSQC_PredictPlayerMove and never reads these.
vector predmove_org0;           // origin at the START of the command (ro)
vector predmove_org;            // origin after the mover; rewritten in place (rw)
vector predmove_vel;            // velocity after the mover (rw)
vector predmove_basevel;        // this command's net push write; the engine
                                // holds it as .run_basevel's mirror (w)
float  predmove_bvfired;        // a continuous push fired, even if the net
                                // vector cancelled to zero (w)
vector predmove_bvset;          // Patch 1025: an AddOutput basevelocity write, paid exactly (w)
float  predmove_bvsetflag;      // ...nonzero when written (w)
float  predmove_wasground;      // Patch 1025: on the ground as this move began (ro)
vector predmove_mins;           // player hull (ro)
vector predmove_maxs;           // (ro)
vector predmove_anglesnap;      // absolute view angles for the snap (w)
vector predmove_cmdangles;      // the usercmd's own angles (ro)
float  predmove_onground;       // (rw)
float  predmove_pmtype;         // (ro)
float  predmove_buttons;        // (ro)
float  predmove_fixangle;       // set 1 to apply predmove_anglesnap (w)

float  tg_cv_debug;

float  tg_n;
entity tg_ent[TG_MAX];
float  tg_kind[TG_MAX];
float  tg_flags[TG_MAX];
vector tg_bmin[TG_MAX];
vector tg_bmax[TG_MAX];

// teleport
string tg_target[TG_MAX];
string tg_landmark[TG_MAX];
float  tg_uselm[TG_MAX];        // SV_KeyTri: -1 absent, 0/1 written
float  tg_snapv[TG_MAX];        // SV_KeyTri
float  tg_vmode[TG_MAX];
float  tg_tspeed[TG_MAX];

// push
vector tg_pushdir[TG_MAX];
float  tg_speed[TG_MAX];
float  tg_onceseq[TG_MAX];      // SF_PUSH_ONCE: -1 unarmed, else the sequence it fired on
float  tg_onceoffset[TG_MAX];   // P924: first firing part within that sequence

// setspeed (dialect resolved at load)
float  tg_sshmode[TG_MAX];
float  tg_ssvmode[TG_MAX];
float  tg_sshspeed[TG_MAX];
float  tg_ssvspeed[TG_MAX];
vector tg_ssang[TG_MAX];
float  tg_ssevery[TG_MAX];
float  tg_ssinseq[TG_MAX];      // last command sequence this pad was inside, this chain

// targetname table: destinations and landmarks, in lump order (= edict
// order, so `first match` is the server's find() answer).
float  tt_n;
string tt_name[TG_TT_MAX];
vector tt_org[TG_TT_MAX];
vector tt_ang[TG_TT_MAX];

// chain state
float  tg_lastseq;              // sequence of the last command hooked
float  tg_lastoffset, predmove_offset; // P924: increasing means a split continuation
float  tg_teleseq;              // Patch 611: ...and of the last one a teleport was predicted on (cl_trail.qc)
float  tg_pusharmed;
vector tg_pushvec;
vector tg_pmins, tg_pmaxs;      // last hook's hull, for trig_here

// load census, for trig_dump
float  tg_c_tele, tg_c_push, tg_c_speed, tg_c_filt, tg_c_dis, tg_c_over;
float  tg_c_nodest;
string tg_map;
float  tg_needload;             // lump was not readable yet; Trig_Frame retries
float  tg_hookseen;             // one-shot "hook alive" print, for tests

// skip ledger: WHY each trigger is server-only, for trig_dump and for the
// phase-2 question of which filters are statically resolvable.
#define TG_SKIP_MAX 64
#define TG_SK_NOBRUSH 1
#define TG_SK_FILT    2
#define TG_SK_DIS     3
#define TG_SK_OVER    4
float  tg_sk_n;
float  tg_sk_why[TG_SKIP_MAX];
string tg_sk_cls[TG_SKIP_MAX];
string tg_sk_name[TG_SKIP_MAX];
#define TG_SK_IO    5

void(float why, string cls, string name) TG_Skip =
{
	if (tg_sk_n >= TG_SKIP_MAX)
		return;
	tg_sk_why[tg_sk_n]  = why;
	tg_sk_cls[tg_sk_n]  = cls;
	tg_sk_name[tg_sk_n] = name;
	tg_sk_n = tg_sk_n + 1;
};

/*
  THE FILTER MIRROR: SV_FilterPassesD (sv_entities.qc:1264) evaluated from
  the lump, three-valued.  The server's only dynamic input is the activator's
  targetname -- outputs rewrite it at runtime and the client cannot see the
  rewrite -- so filter_activator_name evaluates to UNKNOWN and every trigger
  that depends on it stays server-only.  Everything else is lump-static and
  faithful:

    * a filtername that resolves to nothing PASSES -- Source's
      CBaseFilter lookup returns NULL and PassesFilter returns true
      (bhop_futile's six `boosterqwd` triggers);
    * an unimplemented filter class PASSES -- the server's own fail-open
      census (bhop_arcane's sixteen `filter_standing` triggers);
    * filter_multi combines its Filter01..08 subs by filtertype (OR starts
      false, AND starts true), recursion is capped at depth 4, and an empty
      multi passes -- all exactly as SV_FilterPassesD;
    * negated/Negated inverts a definite verdict; UNKNOWN survives it.

  UNKNOWN and FAIL both keep the trigger server-authoritative: the client
  under-predicting costs a round trip, over-predicting fights the snapshot.
  Resolution is one-shot at load, not cached-then-stale: the lump cannot
  change mid-map, and neither can this evaluation.
*/
#define TF_MAX 64
#define TFR_PASS    2
#define TFR_UNKNOWN 1
#define TFR_FAIL    0
float  tf_n, tf_over;
// P865: filter_activator_team/class.  The map's team is SV_LateSpawnAll's rule;
// tf_clsdyn says an output renames the player's class, so class filters are UNKNOWN.
string tf_arg[TF_MAX];            // filterclass, or filterteam as text
float  tf_team, tf_clsdyn, tf_ctspawn, tf_tspawn;
string tf_name[TF_MAX];
string tf_class[TF_MAX];
string tf_filt[TF_MAX];           // the filter's OWN filtername (match name)
float  tf_neg[TF_MAX];
float  tf_type[TF_MAX];           // filter_multi's filtertype: 1 = OR
string tf_sub[TF_MAX * 8];
string tg_p_subu[8], tg_p_subl[8];  // dual-case parse scratch, per entity
string tg_filt[TG_MAX];           // admitted trigger's filtername, if any
float  tg_c_filtok;               // filtered but statically passing

// SV_FindByName's two passes: exact first, case-insensitive fallback, both in
// lump order (= edict order, so first match is find()'s answer).
// SV_FindFilter also gives "no filter" when a non-filter holds the name first;
// filters only here, so that one case reads the filter (surf_metalpipes, a name
// filter = UNKNOWN, the only library map: BACKLOG).
float(string want) TF_Find =
{
	local float i;
	for (i = 0; i < tf_n; i = i + 1)
		if (!strcmp(tf_name[i], want))
			return i;
	for (i = 0; i < tf_n; i = i + 1)
		if (!strcasecmp(tf_name[i], want))
			return i;
	return -1;
};

// SV_NamesMatch: case-insensitive, `*` ends a prefix.
float(string q, string n) TF_NamesMatch =
{
	local float p;
	p = strstrofs(q, "*", 0);
	if (p >= 0)
		return !strcasecmp(substring(n, 0, p), substring(q, 0, p));
	return !strcasecmp(q, n);
};

float(float r, float depth) TF_EvalD;
float(float r, float depth) TF_EvalD =
{
	local float i, sub, pass, isor, n;

	if (r < 0)
		return TFR_PASS;                // missing filter: Source passes
	if (tf_class[r] == "filter_activator_name")
		return TFR_UNKNOWN;             // act.targetname is output state
	if (tf_class[r] == "filter_velocity")
		return TFR_UNKNOWN;             // the player's speed
	if (tf_class[r] == "filter_activator_team" || tf_class[r] == "filter_activator_class")
	{
		if (tf_class[r] == "filter_activator_team")
			pass = (stof(tf_arg[r]) == tf_team);
		else if (tf_clsdyn)
			return TFR_UNKNOWN;
		else
			pass = TF_NamesMatch(tf_arg[r], "player");
		if (tf_neg[r])
			pass = !pass;
		return pass ? TFR_PASS : TFR_FAIL;
	}
	if (tf_class[r] != "filter_multi")
		return TFR_PASS;                // unimplemented class: fail open

	if (depth > 4)
		return TFR_PASS;                // the server's recursion guard
	isor = tf_type[r];
	pass = isor ? TFR_FAIL : TFR_PASS;
	n = 0;
	for (i = 0; i < 8; i = i + 1)
	{
		if (tf_sub[r * 8 + i] == "")
			continue;
		n = n + 1;
		sub = TF_EvalD(TF_Find(tf_sub[r * 8 + i]), depth + 1);
		if (isor)
		{
			if (sub == TFR_PASS)
				pass = TFR_PASS;
			else if (sub == TFR_UNKNOWN && pass == TFR_FAIL)
				pass = TFR_UNKNOWN;
		}
		else
		{
			if (sub == TFR_FAIL)
				pass = TFR_FAIL;
			else if (sub == TFR_UNKNOWN && pass == TFR_PASS)
				pass = TFR_UNKNOWN;
		}
	}
	if (!n)
		return TFR_PASS;                // empty multi: the server passes it
	if (tf_neg[r] && pass != TFR_UNKNOWN)
		pass = (pass == TFR_PASS) ? TFR_FAIL : TFR_PASS;
	return pass;
};

// Patch 906: whether TF_EvalD's verdict on this filter is evaluated rather than failed open.  The
// server leaves a zone-tool box inert behind a filter it cannot evaluate (SV_FilterKnownD) and checks
// filter_momentum_progress itself; a box the client cannot judge is not predicted.
float(float r, float depth) TF_KnownD =
{
	local float i;

	if (r < 0 || depth > 4)
		return FALSE;
	if (tf_class[r] == "filter_multi")
	{
		for (i = 0; i < 8; i = i + 1)
			if (tf_sub[r * 8 + i] != "")
			if (!TF_KnownD(TF_Find(tf_sub[r * 8 + i]), depth + 1))
				return FALSE;
		return TRUE;
	}
	return (tf_class[r] == "filter_activator_team" || tf_class[r] == "filter_activator_class" ||
	        tf_class[r] == "filter_activator_name" || tf_class[r] == "filter_velocity");
};

float(string s) TT_Find =
{
	local float i;
	for (i = 0; i < tt_n; i = i + 1)
		if (!strcmp(tt_name[i], s))
			return i;
	return -1;
};

/*
===========================================================================
  THE IO MIRROR (phase 2b).  Enable/Disable state, replicated.

  The server's IO (sv_entities.qc) fires an entity's outputs on events; the
  events a client can see for certain are the touch edges of the triggers it
  already mirrors, plus logic_auto's OnMapSpawn, which fires exactly once per
  map on both sides.  This block keeps the state those events write:

    * The lump walk captures every "On*" keyvalue (the server's own capture
      rule: case-sensitive "On" prefix, ED_ParseUnknownEpair) into the io_*
      table, five fields, ESC-or-comma separated, exactly as
      SV_EntityIOBuild parses it.  Cosmetic and unimplemented inputs are
      dropped at parse; stateful ones (Enable/Disable/Toggle/Kill/AddOutput/
      ModifySpeed) are kept even when unmirrorable, because they demote.
    * trigger_multiple joins the slot table as TG_EVENT -- an event source
      with no movement effect -- when and only when it owns outputs.  Its
      touch gates are the server's: health, StartDisabled, filter (static,
      at load), and trigger_once retirement (wait < 0 spends the slot for
      this seat after the first start edge -- pushed through the ring as a
      self-Disable, which is exactly what the server's per-seat
      vbsp_once_done bit looks like from inside one player's session).
      NO noclip and NO spawnflags gate: trigger_multiple_touch checks
      neither, so neither does this.
    * A RESOLUTION fixpoint after the walk decides who is predictable.
      Rule 2: a slot any stateful output it cannot mirror is aimed at stays
      server-only -- that is every wiring from relays, buttons, timers,
      counters, OnTrigger/OnJump/OnLand/OnPressed, the All-variants (their
      firing depends on OTHER players' touches), any delay on a touch
      event, Toggle, Kill, AddOutput-targetname rewrites and ModifySpeed.
      Rule SD: a StartDisabled slot is predicted only if at least one
      mirrorable Enable reaches it (touch edge from a predicted slot, or
      OnMapSpawn), which makes mom_training's TELEPORT_SEND_PLAYER and
      push_prevent_backtrack_t1 predictable and leaves teleport_safeguard
      server-only (its enablers are trigger_userinput keypresses, a class
      the server itself never implemented).
      Rule OWNER: a predicted slot whose own outputs write player movement
      (AddOutput basevelocity/gravity or ModifySpeed at !activator) is
      demoted -- the server's copy would move the player and this mirror
      would not.  AddOutput targetname at !activator is the exception kept:
      the player rename only feeds name filters, which are UNKNOWN and
      server-only already.
      Demotion cascades through the fixpoint: a demoted slot's outputs stop
      being mirrorable and demote what they were aimed at.
    * Runtime state is Patch 337's idiom, because the failure mode it fixed
      is the failure mode any chain-scoped state has here: the chain
      restarts from the ack EVERY rendered frame.  tg_io_on[] is the
      committed state; events a predicted command fires go to the ior_*
      ring keyed by sequence; TG_IOCommit folds every entry the ack has
      passed into tg_io_on at the next chain start and drops the rest --
      speculative events a correction erased this way never become
      persistent, and the ones the server also saw are re-derived by the
      replay.  The bounded residue: an event that fires speculatively, gets
      acked PAST, and commits, while the server's own sub-unit trajectory
      never touched -- the entry-edge transient class wearing an IO hat.  It
      shows up as prederrs on one trigger and is the thing to look for first
      if a map ever mis-gates.
    * OnEndTouch mirrors SV_TriggerEndThink's 0.05 s grace on a chain-local
      clock built from the hook's msec.  The server quantises that window to
      a 0.02-0.03 s think, the client to the command; both are the same
      window, and an end event that lands a command apart re-converges
      because Enable/Disable are idempotent.  Across a chain restart the
      grace history is re-seeded by probe, so an end can double-fire when
      the exit straddles the ack -- idempotent for state, and for finite
      `times` it spends the client's copy early, which is under-prediction.
    * `times` is honoured from io_fired[] (committed) plus this chain's ring
      entries; a fire aimed at several slots pushes one entry per slot and
      so spends one count per slot rather than per delivery -- finite-times
      multi-target outputs exhaust early, again the safe direction.

  THE MAPSPAWN SCHEDULE lives outside the ring on purpose: OnMapSpawn rows
  are unconditional, one-shot and identical on both sides, so Trig_Frame
  writes tg_io_on directly once client `time` passes load+delay.  Until it
  fires the client under-predicts (the old behaviour), and the skew between
  the server's first-frame build and the client's worldload is far smaller
  than the 0.5 s delay the maps actually use.
===========================================================================
*/
#define TIO_MAX     1024        // output rows kept per map
#define IO_RING     256         // pending state events per chain
#define TG_IO_GRACE 0.05        // SV_TriggerEndThink's end-touch window

#define EV_OTHER    -1          // fires somewhere the client cannot see
#define EV_START    1
#define EV_END      2
#define EV_MAPSPAWN 3
#define EV_JUMP     4           // Patch 1025: OnJump, mirrored only for basevelocity rows

#define IN_EN       1
#define IN_DIS      2
#define IN_STATE    3           // toggle/kill: stateful, never mirrored
#define IN_ADDOUT   4           // io_parm says which key
#define IN_MODSPD   5
#define IOP_PMOVE   1           // gravity/origin/angles: player movement
#define IOP_BVEL    3           // Patch 1025: basevelocity, mirrored when tg_bvel_ok
#define IOP_TNAME   2           // targetname: routing state

float  io_n, io_over;
float  io_src[TIO_MAX];         // owner slot; -1 other entity; -3 logic_auto
float  io_ev[TIO_MAX];
float  io_inp[TIO_MAX];
float  io_parm[TIO_MAX];
float  io_delay[TIO_MAX];
float  io_times[TIO_MAX];
float  io_fired[TIO_MAX];       // committed fires; mapspawn rows: 1 = done
string io_tgt[TIO_MAX];
vector *io_bv;                  // Patch 1025: an IOP_BVEL row's vector (memalloc: globals are full)

/*
  Patch 1025: OnEndTouch on the next command (SV_TriggerEndEdge) and AddOutput basevelocity paid
  exactly, both published by the server as fs_endedge 1.  With an engine that takes predmove_bvset,
  a trigger whose only movement writes are delay-0 basevelocity outputs at its activator from
  OnStartTouch/OnEndTouch stays predicted; the write is paid, and the end exact, only while the
  server says fs_endedge (read per frame: the serverinfo is not in yet when the lump is walked).
*/
float  tg_endexact;             // fs_endedge: the server ends touches on the next command
float  tg_bvel_ok;              // this engine mirrors the carrier write

string tg_tname[TG_MAX];
float  tg_sd[TG_MAX];           // the StartDisabled key, as authored
// Patch 892: zone-tool boxes.  Fields, not arrays: the client is at the global limit.
.float  tg_isbox;               // on a slot's entity: no brush, shaped by TG_ShapeBoxes
.entity tgs_next;               // an OnMapSpawn AddOutput mins/maxs row, chained from tgs_head
.string tgs_tgt;
.float  tgs_ismin;
.vector tgs_val;
entity  tgs_head;
float   tg_c_box;
float  tg_io_on[TG_MAX];        // committed enabled state
float  tg_io_gated[TG_MAX];     // state gate applies to this slot
float  tg_io_own[TG_MAX];       // owns mirrored edge outputs
float  tg_io_in[TG_MAX];        // chain: inside, end not yet fired
float  tg_io_seen[TG_MAX];      // chain: sequence of last gated overlap
float  tg_io_stamp[TG_MAX];     // chain clock at last overlap
float  tg_io_endf[TG_MAX];      // chain: end event fired
float  tg_io_once[TG_MAX];      // TG_EVENT with wait < 0
float  tg_io_lastin[TG_MAX];    // PERSISTENT: last seq an edge passed the gate

float  ior_n, ior_lost;
float  ior_slot[IO_RING], ior_val[IO_RING];
float  ior_seq[IO_RING],  ior_out[IO_RING];

float  tg_io_clock;             // chain-local seconds, for the end grace
float  tg_io_tbase;             // PERSISTENT: clock value at the last ack
float  tg_iotime0;              // client time at load, for mapspawn delays
float  tg_c_event, tg_c_iodem, tg_c_sdok, tg_c_ioown, tg_c_iogated;
.float tg_netgate, tg_netready, tg_neton;
.float tg_sspartoffset;          // EveryTick's last applied part within tg_ssinseq
.float tg_seenoff;               // Patch 1025: predmove_offset of the last touch (tick parts)
#define TG_RING     64          // Patch 1025: commands of tg_io_in kept per slot
float  *tg_inring;              // [(slot * TG_RING + seq % TG_RING) * 2] = in after seq, [+1] = seq
float  *tg_orgring;             // [(seq % TG_RING) * 4] = predicted origin after seq, [+3] = seq
float  tg_baseseq;              // the pre-move hook's command (cl_warpop.qc) and its origin
vector tg_baseorg;              //   before any warp: the state a chain restarts from
void() Body_TrigSeed;       // cl_body: retain snapshots across mirror reloads
string tg_io_esc;

float(string lk) TG_IOEvOf =
{
	// The All-variants are NOT here: with more than one seat on the server
	// their firing depends on other players' touches, which this mirror
	// cannot see.  They land in EV_OTHER and demote what they are aimed at.
	if (lk == "onstarttouch") return EV_START;
	if (lk == "onendtouch")   return EV_END;
	if (lk == "onmapspawn")   return EV_MAPSPAWN;
	if (lk == "onjump")       return EV_JUMP;
	return EV_OTHER;
};

// One raw "On*" keyvalue, captured where the server's ED_ParseUnknownEpair
// captures it and parsed as SV_EntityIOBuild parses it.
void(string key, string val) TG_IOParse =
{
	local string sep, lk, p0, w, kn;
	local float  ev, nt, sp, inp, parm;

	if (io_n >= TIO_MAX)
	{
		io_over = 1;
		return;
	}
	lk = strtolower(key);
	kn = lk;
	ev = TG_IOEvOf(lk);

	sep = ",";
	if (strstrofs(val, tg_io_esc, 0) >= 0)
		sep = tg_io_esc;		// ESC wins: a comma is legal inside a param
	nt = tokenizebyseparator(val, sep);
	if (nt < 2)
		return;					// no input name: nothing to fire

	lk = strtolower(argv(1));
	inp = 0;
	parm = 0;
	if      (lk == "enable")      inp = IN_EN;
	else if (lk == "disable")     inp = IN_DIS;
	else if (lk == "toggle")      inp = IN_STATE;
	else if (lk == "kill")        inp = IN_STATE;
	else if (lk == "modifyspeed") inp = IN_MODSPD;
	else if (lk == "addspeed" || lk == "addhorizontalspeed" || lk == "addverticalspeed")
		inp = IN_MODSPD;		// Patch 1002: moves the player, so its trigger stays server-only
	else if (lk == "addoutput")
	{
		// The keys SV_IOAddOutput implements; anything else is a census line
		// and inert, so it is not recorded at all.  P865: origin and angles at
		// a player move it (a named target is inert on the server), classname
		// feeds class filters (UNKNOWN once any output writes it), and a
		// retargeted teleport is a state the mirror cannot follow.
		inp = IN_ADDOUT;
		p0 = (nt > 2) ? strtolower(argv(2)) : "";
		sp = strstrofs(p0, " ", 0);
		w = (sp < 0) ? p0 : substring(p0, 0, sp);
		if (w == "basevelocity")
		{
			parm = IOP_BVEL;
			if (!io_bv)
				io_bv = memalloc(sizeof(vector) * TIO_MAX);
			io_bv[io_n] = (sp < 0) ? '0 0 0' : stov(substring(p0, sp + 1, -1));
		}
		else if (w == "gravity" || w == "origin" || w == "angles")
			parm = IOP_PMOVE;
		else if (w == "targetname")
			parm = IOP_TNAME;
		else if (w == "classname")
		{
			parm = IOP_TNAME;
			tf_clsdyn = 1;
		}
		else if (w == "target")
			inp = IN_STATE;
		else if ((w == "mins" || w == "maxs") && kn == "onmapspawn")
		{
			// Patch 892: a zone-tool trigger's box, static from map spawn (TG_ShapeBoxes).
			if (sp >= 0)
			{
				local entity row;
				row = spawn();
				row.tgs_tgt = strzone(strtolower(argv(0)));
				row.tgs_ismin = (w == "mins");
				row.tgs_val = stov(substring(p0, sp + 1, -1));
				row.tgs_next = tgs_head;
				tgs_head = row;
			}
			return;
		}
		else
			return;
	}
	else
		return;					// cosmetic or unimplemented: inert on the
								// server (its census says so), and no state

	io_src[io_n]   = -1;		// patched at the end of the entity
	io_ev[io_n]    = ev;
	io_inp[io_n]   = inp;
	io_parm[io_n]  = parm;
	io_delay[io_n] = (nt > 3) ? stof(argv(3)) : 0;
	io_times[io_n] = (nt > 4) ? stof(argv(4)) : -1;
	io_tgt[io_n]   = argv(0);
	io_n = io_n + 1;
};

// Rule-2 matching: exact OR case-insensitive, deliberately broader than
// SV_FindByName's exact-then-fallback delivery -- MISSING a match here would
// keep a trigger predicted that the server can rewrite, the unsafe side.
float(float o, float s) TG_IOHits =
{
	if (!strcmp(io_tgt[o], "!self"))
		return io_src[o] == s;
	if (substring(io_tgt[o], 0, 1) == "!")
		return FALSE;			// !activator and friends are never a slot
	if (tg_tname[s] == "")
		return FALSE;
	return !strcmp(io_tgt[o], tg_tname[s]) ||
	       !strcasecmp(io_tgt[o], tg_tname[s]);
};

float(float o) TG_IOStateful =
{
	if (io_inp[o] == IN_EN || io_inp[o] == IN_DIS || io_inp[o] == IN_STATE)
		return TRUE;
	if (io_inp[o] == IN_MODSPD)
		return TRUE;
	if (io_inp[o] == IN_ADDOUT && io_parm[o] == IOP_TNAME)
		return TRUE;
	return FALSE;
};

float(float o) TG_IOMirrorOK =
{
	if (io_inp[o] != IN_EN && io_inp[o] != IN_DIS)
		return FALSE;
	if (io_ev[o] == EV_MAPSPAWN)
		return io_src[o] == -3;	// only logic_auto fires OnMapSpawn
	if (io_ev[o] != EV_START && io_ev[o] != EV_END)
		return FALSE;
	if (io_delay[o] != 0)
		return FALSE;			// no delayed-output scheduler in prediction
	if (io_src[o] < 0)
		return FALSE;
	return tg_kind[io_src[o]] != 0;	// owner predicted (fixpoint updates this)
};

// Patch 1025: a basevelocity row this mirror can pay (TG_IOFireEv) rather than demoting its owner.
float(float o) TG_IOBvelOK =
{
	if (!tg_bvel_ok || io_delay[o] != 0 || io_times[o] >= 0)
		return FALSE;
	if (io_src[o] < 0)
		return FALSE;	// nested: QC's || does not short-circuit, and [-1] aborts the VM
	if (tg_kind[io_src[o]] != TG_EVENT)
		return FALSE;	// a push re-arms over it, a teleport clears the carrier after it
	return io_ev[o] == EV_START || io_ev[o] == EV_END || io_ev[o] == EV_JUMP;
};

float(float s) TG_IOOwnerBad =
{
	local float o;
	local string t;
	for (o = 0; o < io_n; o = o + 1)
	{
		if (io_src[o] != s)
			continue;
		t = io_tgt[o];
		if (strcmp(t, "!activator") && strcmp(t, "!player") &&
		    strcmp(t, "!caller"))
			continue;
		if (io_inp[o] == IN_MODSPD)
			return TRUE;
		if (io_inp[o] == IN_ADDOUT && io_parm[o] == IOP_PMOVE)
			return TRUE;
		if (io_inp[o] == IN_ADDOUT && io_parm[o] == IOP_BVEL && !TG_IOBvelOK(o))
			return TRUE;
	}
	return FALSE;
};

void(float slot, float val, float seq, float o) TG_IOPush =
{
	if (ior_n >= IO_RING)
	{
		if (!ior_lost)
		{
			ior_lost = 1;
			print("^3trig: IO ring full, dropping events -- a trigger may stay mis-gated until the next map\n");
		}
		return;
	}
	ior_slot[ior_n] = slot;
	ior_val[ior_n]  = val;
	ior_seq[ior_n]  = seq;
	ior_out[ior_n]  = o;
	ior_n = ior_n + 1;
};

float(float i, float seq) TG_IOEff =
{
	local float e;
	// Server snapshots own delayed/shared gates. No stream (older server)
	// means no prediction, not a guess that the trigger is enabled.
	if (tg_ent[i].tg_netgate)
		return tg_ent[i].tg_netready && tg_ent[i].tg_neton;
	if (!tg_io_gated[i])
		return 1;
	for (e = ior_n - 1; e >= 0; e = e - 1)
		if (ior_slot[e] == i && ior_seq[e] <= seq)
			return ior_val[e];
	return tg_io_on[i];
};

float(float o, float seq) TG_IOApply =
{
	local float s, n, e, anyexact, val, pushed;

	pushed = 0;
	if (io_times[o] >= 0)
	{
		n = io_fired[o];
		for (e = 0; e < ior_n; e = e + 1)
			if (ior_out[e] == o)
				n = n + 1;
		if (n >= io_times[o])
			return 0;			// spent, as SV_FireOutput spends it
	}
	val = (io_inp[o] == IN_EN) ? 1 : 0;
	if (!strcmp(io_tgt[o], "!self"))
	{
		s = io_src[o];
		if (s >= 0 && tg_kind[s])
		{
			TG_IOPush(s, val, seq, o);
			pushed = 1;
		}
		return pushed;
	}
	// SV_FindByName: exact matches when any exist, else the case-insensitive
	// fallback; delivered to EVERY matching slot, as Source does.
	anyexact = FALSE;
	for (s = 0; s < tg_n; s = s + 1)
		if (tg_kind[s] && tg_tname[s] != "" &&
		    !strcmp(io_tgt[o], tg_tname[s]))
			anyexact = TRUE;
	for (s = 0; s < tg_n; s = s + 1)
	{
		if (!tg_kind[s] || tg_tname[s] == "")
			continue;
		if (anyexact ? !strcmp(io_tgt[o], tg_tname[s])
		             : !strcasecmp(io_tgt[o], tg_tname[s]))
		{
			TG_IOPush(s, val, seq, o);
			pushed = pushed + 1;
		}
	}
	return pushed;
};

void(float i, float ev, float seq) TG_IOFireEv =
{
	local float o;
	for (o = 0; o < io_n; o = o + 1)
	{
		if (io_src[o] != i || io_ev[o] != ev)
			continue;
		if (ev == EV_JUMP && !(io_inp[o] == IN_ADDOUT && io_parm[o] == IOP_BVEL))
			continue;		// an OnJump state row demoted what it aims at
		if (io_inp[o] == IN_ADDOUT && io_parm[o] == IOP_BVEL)
		{
			// TG_IOOwnerBad kept this slot only if every such row is TG_IOBvelOK, and its
			// targets are the activator (other targets are no carrier of ours).
			if (tg_endexact && TG_IOBvelOK(o))
			if (!strcmp(io_tgt[o], "!activator") || !strcmp(io_tgt[o], "!player") ||
			    !strcmp(io_tgt[o], "!caller"))
			{
				predmove_bvset = io_bv[o];
				predmove_bvsetflag = 1;
				if (tg_cv_debug)
					print(sprintf("^5trig^7: seq %g IO #%g %s -> basevelocity %v\n", seq, i,
					              (ev == EV_START) ? "OnStartTouch" : (ev == EV_END) ? "OnEndTouch" : "OnJump",
					              io_bv[o]));
			}
			continue;
		}
		if (io_inp[o] != IN_EN && io_inp[o] != IN_DIS)
			continue;
		if (io_delay[o] != 0)
			continue;
		// Printed only when the delivery actually reached a slot: the
		// cosmetic and non-slot rows would otherwise narrate every edge.
		if (TG_IOApply(o, seq) && tg_cv_debug)
			print(sprintf("^5trig^7: seq %g IO #%g %s -> %s '%s'\n", seq, i,
			              (ev == EV_START) ? "OnStartTouch" : "OnEndTouch",
			              (io_inp[o] == IN_EN) ? "Enable" : "Disable",
			              io_tgt[o]));
	}
};

// SV_TriggerIOTouch's entry half.  Called where the server calls it: after
// the touch function's own gates, before the movement effect.
float(float i, float seq) TG_IOEdge =
{
	tg_io_seen[i]  = seq;
	tg_ent[i].tg_seenoff = predmove_offset;
	tg_io_stamp[i] = tg_io_tbase + tg_io_clock;
	tg_io_lastin[i] = seq;
	if (tg_io_in[i])
		return FALSE;
	tg_io_in[i]   = 1;
	tg_io_endf[i] = 0;
	TG_IOFireEv(i, EV_START, seq);
	return TRUE;
};

void(float seq) TG_IOEndSweep =
{
	local float i;
	for (i = 0; i < tg_n; i = i + 1)
	{
		if (!tg_io_own[i] || !tg_io_in[i] || tg_io_endf[i])
			continue;
		if (tg_io_seen[i] == seq)
		if (!tg_endexact || tg_ent[i].tg_seenoff == predmove_offset)
			continue;	// Patch 1025: the server reads touches per tick part (P893)
		if (tg_io_once[i] && tg_io_gated[i] && !TG_IOEff(i, seq))
		{
			// A spent once slot ends silently: the server's retired trigger fires no OnEndTouch.
			// A disabled trigger ends here like any other.
			tg_io_endf[i] = 1;
			tg_io_in[i]   = 0;
			continue;
		}
		// ABSOLUTE command time, not chain-local: the chain restarts every
		// rendered frame, and a minimized window renders slower than the
		// command rate, so one chain can span MORE than the 0.05 s grace --
		// a chain-local clock fires END mid-chain and START-END oscillates
		// every frame (p338c, measured).  tg_io_tbase + tg_io_clock is the
		// same value for a given command on every replay pass, because the
		// base is the committed clock at the ack and the per-command msecs
		// re-add identically.
		if (!tg_endexact)
		if (tg_io_tbase + tg_io_clock - tg_io_stamp[i] <= TG_IO_GRACE)
			continue;
		tg_io_endf[i] = 1;
		tg_io_in[i]   = 0;
		TG_IOFireEv(i, EV_END, seq);
	}
};

float(float i, float s) TG_RingAt =
{
	return (i * TG_RING + (s - TG_RING * floor(s / TG_RING))) * 2;
};

// Patch 1025: TRUE when the last replay of command s (or the latest recorded command before it,
// within TG_RING - 1) ended at org -- the client's replay is the server's history, so its ring is.
float(float s, vector org) TG_RingTrusted =
{
	local float d, k;
	local vector o;

	for (d = 0; d < TG_RING; d = d + 1)
	{
		k = (s - d - TG_RING * floor((s - d) / TG_RING)) * 4;
		if (tg_orgring[k + 3] == s - d)
		{
			o_x = tg_orgring[k];
			o_y = tg_orgring[k + 1];
			o_z = tg_orgring[k + 2];
			return vlen(o - org) < 1;
		}
	}
	return FALSE;
};

// Patch 1025: slot i's tg_io_in after command s as the last replay of s left it, -1 if unknown.
// A missing command ran no hook (held, or with exact ends or cl_triggers off), so the latest
// recorded one at or before s, within TG_RING - 1, stands for it.
float(float i, float s) TG_InAfter =
{
	local float d, k;

	for (d = 0; d < TG_RING; d = d + 1)
	{
		k = TG_RingAt(i, s - d);
		if (tg_inring[k + 1] == s - d)
			return tg_inring[k];
	}
	return -1;
};

void(float s0) TG_IOCommit =
{
	local float e;
	for (e = 0; e < ior_n; e = e + 1)
		if (ior_seq[e] < s0)
		{
			tg_io_on[ior_slot[e]] = ior_val[e];
			if (ior_out[e] >= 0)
				io_fired[ior_out[e]] = io_fired[ior_out[e]] + 1;
		}
	ior_n = 0;
};

void(float i, float why) TG_DemoteIO =
{
	if (tg_kind[i] == TG_TELE)       tg_c_tele  = tg_c_tele - 1;
	else if (tg_kind[i] == TG_PUSH)  tg_c_push  = tg_c_push - 1;
	else if (tg_kind[i] == TG_SPEED) tg_c_speed = tg_c_speed - 1;
	else                             tg_c_event = tg_c_event - 1;
	if (why == TG_SK_DIS)
		tg_c_dis = tg_c_dis + 1;
	else
		tg_c_iodem = tg_c_iodem + 1;
	TG_Skip(why,
	        (tg_kind[i] == TG_TELE) ? "trigger_teleport" :
	        (tg_kind[i] == TG_PUSH) ? "trigger_push" :
	        (tg_kind[i] == TG_SPEED) ? "trigger_setspeed" : "trigger_multiple",
	        tg_tname[i]);
	remove(tg_ent[i]);
	tg_ent[i]  = world;
	tg_kind[i] = 0;
	tg_bmin[i] = '1 1 1';
	tg_bmax[i] = '-1 -1 -1';
};

// Patch 892: a box slot takes its logic_auto's OnMapSpawn mins and maxs, as the server's AddOutput
// does a second after spawn; one without both is demoted.
void() TG_ShapeBoxes =
{
	local float i, gotlo, gothi;
	local vector lo, hi;
	local string nm;
	local entity row, nx;

	for (i = 0; i < tg_n; i = i + 1)
	{
		if (!tg_kind[i] || !tg_ent[i].tg_isbox)
			continue;
		nm = strtolower(tg_tname[i]);
		gotlo = gothi = 0;
		lo = hi = '0 0 0';
		for (row = tgs_head; row; row = row.tgs_next)
		{
			if (strcmp(row.tgs_tgt, nm))
				continue;
			if (row.tgs_ismin) { lo = row.tgs_val; gotlo = 1; }
			else               { hi = row.tgs_val; gothi = 1; }
		}
		if (!gotlo || !gothi)
		{
			TG_DemoteIO(i, TG_SK_NOBRUSH);
			continue;
		}
		setsize(tg_ent[i], lo, hi);
		tg_ent[i].solid = SOLID_TRIGGER;
		setorigin(tg_ent[i], tg_ent[i].origin);
		tg_bmin[i] = tg_ent[i].origin + lo;
		tg_bmax[i] = tg_ent[i].origin + hi;
		tg_c_box = tg_c_box + 1;
	}
	for (row = tgs_head; row; row = nx)
	{
		nx = row.tgs_next;
		strunzone(row.tgs_tgt);
		remove(row);
	}
	tgs_head = world;
};

// Brush submodel numbers are shared by the BSP on both sides. State arrives
// on the existing CSQC entity stream, including changes caused by OTHER
// players. The callback's REMOVE revokes readiness as well as enabled state.
void(float modelnum, float ready, float on) Trig_NetState =
{
	local float i;
	local string modelname;

	modelname = sprintf("*%g", modelnum);
	for (i = 0; i < tg_n; i = i + 1)
		if (tg_kind[i] == TG_PUSH)
			if (!strcmp(tg_ent[i].model, modelname))
			{
				tg_ent[i].tg_netready = ready;
				tg_ent[i].tg_neton = on;
				if (cvar("cl_trigdebug"))
					print(sprintf("trig: server gate #%g %s ready %g on %g\n",
					              i, modelname, ready, on));
			}
};

void() TG_IOResolve =
{
	local float s, o, pass, changed, ok, hit;

	if (io_over)
	{
		// The graph did not fit: every NAMED slot could be wired by a row
		// that was dropped, and every SD slot could have lost its enabler.
		// Unnamed slots survive -- outputs reach a slot only by targetname
		// or !self, and !self rows were kept while the table had room.
		for (s = 0; s < tg_n; s = s + 1)
			if (tg_kind[s] && (tg_tname[s] != "" || tg_sd[s]))
				TG_DemoteIO(s, TG_SK_IO);
	}

	for (s = 0; s < tg_n; s = s + 1)
		if (tg_kind[s] && TG_IOOwnerBad(s))
			TG_DemoteIO(s, TG_SK_IO);

	// Zero-delay gates are shared too. A push follows authoritative state,
	// not just this seat's output chain. Never widen a truncated graph.
	if (!io_over)
		for (s = 0; s < tg_n; s = s + 1)
			if (tg_kind[s] == TG_PUSH && !(tg_flags[s] & TG_SF_PUSH_ONCE))
				for (o = 0; o < io_n; o = o + 1)
					if (io_inp[o] == IN_EN || io_inp[o] == IN_DIS)
						if (TG_IOHits(o, s))
							tg_ent[s].tg_netgate = 1;

	pass = 0;
	changed = TRUE;
	while (changed && pass < 16)
	{
		changed = FALSE;
		pass = pass + 1;
		for (s = 0; s < tg_n; s = s + 1)
		{
			if (!tg_kind[s])
				continue;
			hit = FALSE;
			for (o = 0; o < io_n; o = o + 1)
			{
				if (!TG_IOStateful(o) || TG_IOMirrorOK(o))
					continue;
				if (TG_IOHits(o, s))
				{
					// Only enabled state is networked; speed rewrites, names,
					// once retirement and player movement remain unmirrorable.
					if (tg_ent[s].tg_netgate)
						if (io_inp[o] == IN_EN || io_inp[o] == IN_DIS)
							continue;
					hit = TRUE;
					break;
				}
			}
			if (!hit && tg_sd[s] && !tg_ent[s].tg_netgate)
			{
				ok = FALSE;
				for (o = 0; o < io_n; o = o + 1)
					if (io_inp[o] == IN_EN && io_src[o] != s &&
					    TG_IOMirrorOK(o) && TG_IOHits(o, s))
					{
						ok = TRUE;
						break;
					}
				hit = !ok;
			}
			if (hit)
			{
				TG_DemoteIO(s, tg_sd[s] ? TG_SK_DIS : TG_SK_IO);
				changed = TRUE;
			}
		}
	}
	if (changed)
		print("^3trig: IO resolution did not converge in 16 passes\n");

	for (s = 0; s < tg_n; s = s + 1)
	{
		if (!tg_kind[s])
			continue;
		tg_io_on[s] = !tg_sd[s];
		if (tg_sd[s])
		{
			tg_c_sdok = tg_c_sdok + 1;
			tg_io_gated[s] = 1;
		}
		if (tg_io_once[s])
			tg_io_gated[s] = 1;	// the retirement rides the same gate
		for (o = 0; o < io_n; o = o + 1)
		{
			if (io_inp[o] != IN_EN && io_inp[o] != IN_DIS)
				continue;
			if (!TG_IOMirrorOK(o))
				continue;
			if (TG_IOHits(o, s))
				tg_io_gated[s] = 1;
			if (io_src[o] == s &&
			    (io_ev[o] == EV_START || io_ev[o] == EV_END))
				tg_io_own[s] = 1;
		}
		for (o = 0; o < io_n; o = o + 1)
			if (io_src[o] == s && io_inp[o] == IN_ADDOUT && io_parm[o] == IOP_BVEL && TG_IOBvelOK(o))
				tg_io_own[s] = 1;   // Patch 1025
		if (tg_io_own[s])
			tg_c_ioown = tg_c_ioown + 1;
		if (tg_io_gated[s])
			tg_c_iogated = tg_c_iogated + 1;
	}
};

// logic_auto's OnMapSpawn schedule, fired from Trig_Frame.  Unconditional
// and one-shot on both sides, so it writes the committed state directly --
// no ring, no sequences.
void() Trig_IOMapSpawn =
{
	local float o, s, anyexact, val;
	for (o = 0; o < io_n; o = o + 1)
	{
		if (io_ev[o] != EV_MAPSPAWN || io_src[o] != -3 || io_fired[o])
			continue;
		if (io_inp[o] != IN_EN && io_inp[o] != IN_DIS)
			continue;			// stateful others demoted their targets
		if (time < tg_iotime0 + io_delay[o])
			continue;
		io_fired[o] = 1;
		val = (io_inp[o] == IN_EN) ? 1 : 0;
		anyexact = FALSE;
		for (s = 0; s < tg_n; s = s + 1)
			if (tg_kind[s] && tg_tname[s] != "" &&
			    !strcmp(io_tgt[o], tg_tname[s]))
				anyexact = TRUE;
		for (s = 0; s < tg_n; s = s + 1)
		{
			if (!tg_kind[s] || tg_tname[s] == "")
				continue;
			if (anyexact ? !strcmp(io_tgt[o], tg_tname[s])
			             : !strcasecmp(io_tgt[o], tg_tname[s]))
			{
				tg_io_on[s] = val;
				tg_io_gated[s] = 1;
				if (cvar("cl_trigdebug"))
					print(sprintf("^5trig^7: OnMapSpawn +%gs %s '%s' -> #%g\n",
					              io_delay[o], val ? "Enable" : "Disable",
					              io_tgt[o], s));
			}
		}
	}
};

vector(vector a, vector b) TG_VMin =
{
	return [min(a_x, b_x), min(a_y, b_y), min(a_z, b_z)];
};

vector(vector a, vector b) TG_VMax =
{
	return [max(a_x, b_x), max(a_y, b_y), max(a_z, b_z)];
};

/*
  The overlap probe: the player hull at the command's END position against
  ONE trigger's submodel -- a zero-length clip, which is exactly the server's
  test: player touches are dispatched by World_LinkEdict's World_TouchAllLinks
  AFTER the move (sv_user.c:8350), as World_ClipMoveToEntity(..., origin,
  mins, maxs, origin, ...) with every contents bit on a Source map (world.c,
  Patch 881; it was MASK_WORLDSOLID, which missed GRATE-only brushes) -- hence
  TG_Probe as the pass entity, whose hitcontentsmaski the trace takes.  The
  first cut swept [org0..org1] instead and measured the cost: a graze of a
  trigger edge that the server's endpoint test never saw fired the client
  alone, and one 203-unit prederr followed -- the snap-back this patch exists
  to end.  Parity beats completeness: if the server can miss a thin volume at
  speed, the client must miss it identically.
  `other` is the channel MOVE_OTHERONLY reads (csqc_world.g.other is bound to
  the QC global, pr_csqc.c), and the flags reach World_ClipMoveToEntity
  through PF_cs_tracebox's `nomonsters|MOVE_IGNOREHULL` parameter.
*/
// Patch 881: the pass entity for trigger probes; a trace takes its mask (world.c World_Move).
entity tg_probe;
entity() TG_Probe =
{
	if (!tg_probe)
	{
		tg_probe = spawn();
		tg_probe.hitcontentsmaski = -1i;
	}
	return tg_probe;
};

float(entity trig, vector o0, vector o1) TG_Overlaps =
{
	other = trig;
	tracebox(o1, predmove_mins, predmove_maxs, o1,
	         MOVE_TRIGGERS | MOVE_OTHERONLY, TG_Probe());
	return trace_startsolid || trace_allsolid || trace_fraction < 1;
};

/*
  trigger_teleport_touch, minus everything that is IO state or server-only:
  the noclip bypass, the health gate, the spawnflags default-on rule, the
  landmark/angle-snap/VelocityMode decisions and the one-unit destination
  lift, each with sv_entities.qc's own reasoning behind it.  No SV_TimerWarped
  and no SV_RecWarp here on purpose -- the timer and the evidence belong to
  the server's copy, and a client that wrote them would be writing them
  twice.
*/
float(float i, float seq) TG_FireTeleport =
{
	local float drow, mrow, snapang, hs, vmode;
	local vector newpos, dang;

	// SV_TeleportBypassed: noclip ALONE still teleports; noclip + jump is the
	// "I am flying to look at something" bypass.
	if ((predmove_pmtype == TG_PM_OLD_SPECTATOR ||
	     predmove_pmtype == TG_PM_SPECTATOR) && (predmove_buttons & TG_BUTTON_JUMP))
		return 0;
	if (getstatf(STAT_HEALTH) <= 0)
		return 0;
	// A key of exactly 0 means the map never wrote spawnflags: default ON.
	if (tg_flags[i] && !(tg_flags[i] & TG_SF_TELE_CLIENTS))
		return 0;

	// SV_TriggerIOTouch, where the server puts it: after the gates, before
	// the destination lookup -- "an output that renames the activator must
	// land while the activator is still where the map thinks it is."
	TG_IOEdge(i, seq);

	drow = TT_Find(tg_target[i]);
	if (drow < 0)
	{
		tg_c_nodest = tg_c_nodest + 1;
		return 0;
	}

	mrow = -1;
	if (tg_landmark[i] != "")
		mrow = TT_Find(tg_landmark[i]);

	if (mrow >= 0)
	{
		newpos  = tt_org[drow] + (predmove_org - tt_org[mrow]);
		snapang = (tg_uselm[i] > 0);
	}
	else
	{
		newpos  = tt_org[drow] + '0 0 1';
		snapang = !(tg_flags[i] & TG_SF_TELE_KEEPANGLES);   // Patch 398: as sv_entities.qc
	}

	predmove_org = newpos;
	tg_teleseq   = seq;
	// "I did not travel here, I was put here" -- Source clears the ground
	// entity before moving you.
	predmove_onground = 0;

	if (snapang)
	{
		// Destinations are yaw markers; the server zeroes pitch and roll.
		dang = tt_ang[drow];   // through a temporary: `tt_ang[drow]_y` is not
		predmove_anglesnap = [0, dang_y, 0];   // a component expression (fteqcc)
		// Patch 401: predict the view snap only on an engine that reconciles it
		// exactly -- Patch 396 registers the command predangle_dump (1 = an engine
		// command; a cvar's ENGINE flag would not do: any `set` marks it user-made).
		// Older engines double or undo the snap at fps above cl_netfps; unpredicted,
		// the server's delta turns you 1 RTT late.
		if (checkcommand("predangle_dump") == 1)
			predmove_fixangle = 1;

		if (tg_snapv[i] > 0)
		{
			hs = vlen([predmove_vel_x, predmove_vel_y, 0]);
			makevectors(predmove_anglesnap);
			predmove_vel = v_forward * hs + '0 0 1' * predmove_vel_z;
		}
	}

	// Landmark mode carries velocity through untouched; VelocityMode is the
	// non-landmark exit's only.
	if (mrow >= 0)
		return 1;

	vmode = tg_vmode[i];
	if (vmode == 1)
		predmove_vel = '0 0 0';
	else if (vmode == 2)
		predmove_vel = [0, 0, min(predmove_vel_z, 0)];
	else if (vmode == 3)
	{
		hs = tg_tspeed[i];
		if (hs <= 0)
			hs = vlen(predmove_vel);
		makevectors(tt_ang[drow]);
		predmove_vel = v_forward * hs;
	}
	return 1;
};

/*
  trigger_push_touch.  The once arm is an impulse ADD through
  SV_ClampImpulse's clamp; the continuous arm accumulates the carrier across
  overlapping pads within ONE command (server: FL_BASEVELOCITY is cleared at
  the top of every command) and hands it to the engine, which folds it into
  the next command's pmove.basevelocity.
*/
float(float i, float seq) TG_FirePush =
{
	local vector dir, push;
	local float  spd, l;

	if (predmove_pmtype == TG_PM_OLD_SPECTATOR ||
	    predmove_pmtype == TG_PM_SPECTATOR)
		return 0;
	if (!(tg_flags[i] & (TG_SF_TRIGGER_CLIENTS | TG_SF_TRIGGER_ALL)))
		return 0;
	TG_IOEdge(i, seq);

	makevectors(tg_pushdir[i]);
	dir = v_forward;
	spd = tg_speed[i];
	if (!spd)
		spd = 100;

	if (tg_flags[i] & TG_SF_PUSH_ONCE)
	{
		// Reapply the first firing part on replay, never on a later split part.
		if (tg_onceseq[i] >= 0)
		{
			if (seq > tg_onceseq[i]) return 0;
			if (seq == tg_onceseq[i] && predmove_offset > tg_onceoffset[i]) return 0;
		}
		tg_onceseq[i] = seq;
		tg_onceoffset[i] = predmove_offset;

		if (dir_z > 0)
			predmove_onground = 0;

		push = dir * spd;
		l = vlen(push);
		if (l >= 400000)
			push = '0 0 0';               // Source discards the impulse
		else if (l > 4000)
			push = push * (4000 / l);     // k_flMaxEntitySpeed * 2
		predmove_vel = predmove_vel + push;
		return 1;
	}

	push = dir * spd;
	if (tg_pusharmed)
		push = push + tg_pushvec;

	// Tested AFTER the accumulate, on the net push: clear the ground flag and
	// lift one unit, or the ground check re-grounds the same command.
	if (push_z > 0 && predmove_onground)
	{
		predmove_onground = 0;
		predmove_org = predmove_org + '0 0 1';
	}

	tg_pushvec   = push;
	tg_pusharmed = 1;
	predmove_basevel = push;
	predmove_bvfired = 1;
	return 1;
};

/*
  trigger_setspeed_touch, both dialects pre-resolved at load.  The enter-edge
  gate is sequence adjacency (see the header); EveryTick re-applies on every
  command like the server's every frame.
*/
float(float i, float seq) TG_FireSpeed =
{
	local vector vel, dir, aang;
	local float  enter, cur, hmode, vmode, hspeed, vspeed;

	if (predmove_pmtype == TG_PM_OLD_SPECTATOR ||
	    predmove_pmtype == TG_PM_SPECTATOR)
		return 0;
	TG_IOEdge(i, seq);

	if (tg_ssinseq[i] == seq)
	{
		if (!tg_ssevery[i]) return 0;         // enter-only, including later parts
		if (predmove_offset <= tg_ent[i].tg_sspartoffset) return 0;
	}
	enter = (tg_ssinseq[i] != seq && tg_ssinseq[i] != seq - 1);
	tg_ssinseq[i] = seq;
	tg_ent[i].tg_sspartoffset = predmove_offset;
	if (!enter && !tg_ssevery[i])
		return 0;

	hmode  = tg_sshmode[i];
	vmode  = tg_ssvmode[i];
	hspeed = tg_sshspeed[i];
	vspeed = tg_ssvspeed[i];

	vel = predmove_vel;
	cur = vlen([vel_x, vel_y, 0]);

	if (hmode != TG_SS_IGNORE)
	{
		if (hmode == TG_SSH_SETDIR)
		{
			aang = tg_ssang[i];
			makevectors([0, aang_y, 0]);   // YAW ONLY, per the FGD
			dir = v_forward;
		}
		else if (cur > 0)
			dir = normalize([vel_x, vel_y, 0]);
		else
		{
			makevectors([0, predmove_cmdangles_y, 0]);
			dir = v_forward;
		}

		if (hmode == TG_SS_INCREASE)       { if (cur < hspeed) cur = hspeed; }
		else if (hmode == TG_SS_DECREASE)  { if (cur > hspeed) cur = hspeed; }
		else                               cur = hspeed;

		vel_x = dir_x * cur;
		vel_y = dir_y * cur;
	}

	// Signed, not magnitude: increase/decrease are max()/min() on vel_z.
	if (vmode == TG_SSV_SET)             vel_z = vspeed;
	else if (vmode == TG_SS_INCREASE)    { if (vel_z < vspeed) vel_z = vspeed; }
	else if (vmode == TG_SS_DECREASE)    { if (vel_z > vspeed) vel_z = vspeed; }

	predmove_vel = vel;
	return 1;
};

/*
  Chain-start seeding: on the chain's first command predmove_org0 IS the
  acked position, so a zero-length probe there answers "was the enter edge
  behind the chain" for every setspeed pad.  See the header essay.
*/
void(float seq) TG_ChainStart =
{
	local float i, probe, r, trust;
	local vector base;

	// Acked IO events fold into the committed state; the speculative rest
	// is dropped and the replay re-derives it.  See THE IO MIRROR.
	TG_IOCommit(seq);
	tg_io_tbase = tg_io_tbase + tg_io_clock;
	tg_io_clock = 0;

	// Patch 1025: the in-state ring is the client's replay of the ack; trust it only where that
	// replay ended where the server's state now starts (an unpredicted reset or teleport did not).
	base = predmove_org0;
	if (tg_baseseq == seq)
		base = tg_baseorg;      // a warp op at seq has moved org0 already
	trust = FALSE;
	if (tg_endexact && tg_inring)
		trust = TG_RingTrusted(seq - 1, base);

	for (i = 0; i < tg_n; i = i + 1)
	{
		if (!tg_kind[i])
			continue;
		if (tg_io_own[i])
		{
			// CONTINUATION, PENDING END, OR FRESH ENTRY -- decided by
			// persistent stamps, because the chain restarts from the ack
			// EVERY rendered frame.  "Seed fresh" re-fires START a hundred
			// times a second; "seed from the probe" alone swallows the
			// START of a warp-in (a teleport chain landing inside an
			// enabler), which the server's empty touch-bits DO fire --
			// both measured by p338c.  tg_io_lastin survives the restart:
			// an overlap at or adjacent to the ack is the same continuous
			// stay, whose START is committed; a gap is a materialisation
			// and the edge is new.  A pending END (out at the ack, grace
			// not yet elapsed -- on localhost the ack lands INSIDE the
			// 0.05 s) survives too: in stays 1 and the persistent absolute
			// stamp lets the sweep finish the grace.  A gated-off slot
			// seeds fresh: the server's bits are empty for it as well, its
			// touch returning at the gate.  Under exact ends the ring says.
			tg_io_endf[i] = 0;
			tg_io_seen[i] = seq - 1;
			r = -1;
			if (trust)
				r = TG_InAfter(i, seq - 1);
			probe = 0;
			if (r < 0)
			{
				other = tg_ent[i];
				tracebox(predmove_org0, predmove_mins, predmove_maxs,
				         predmove_org0,
				         MOVE_TRIGGERS | MOVE_OTHERONLY, TG_Probe());
				probe = trace_startsolid || trace_allsolid || trace_fraction < 1;
			}
			if (tg_cv_debug >= 2)
				print(sprintf("trig: seed #%g seq %g ring %g probe %g eff %g lastin %g in %g\n",
			              i, seq, r, probe, TG_IOEff(i, seq), tg_io_lastin[i],
			              tg_io_in[i]));
			if (r >= 0)
			{
				// Patch 1025: what the last replay of the ack left, as the server's touch bits
				// do; a probe cannot see a teleport's or a warp's exit, nor a Disable since.
				tg_io_in[i]    = r;
				tg_io_stamp[i] = r ? tg_io_tbase : 0;
			}
			else if (tg_io_in[i] && !probe && TG_IOEff(i, seq) && !tg_endexact)
			{
				// pending END: keep in + stamp.  Patch 1025: an exact end at the ack has
				// fired already (its carrier is in the engine's ring for that sequence).
			}
			else if (probe && TG_IOEff(i, seq) &&
			         tg_io_lastin[i] >= seq - 2)
			{
				tg_io_in[i]    = 1;
				tg_io_stamp[i] = tg_io_tbase;
			}
			else
			{
				tg_io_in[i]    = 0;
				tg_io_stamp[i] = 0;
			}
		}
		if (tg_kind[i] != TG_SPEED)
			continue;
		other = tg_ent[i];
		tracebox(predmove_org0, predmove_mins, predmove_maxs, predmove_org0,
		         MOVE_TRIGGERS | MOVE_OTHERONLY, TG_Probe());
		if (trace_startsolid || trace_allsolid)
			tg_ssinseq[i] = seq - 1;     // inside at the ack: edge is history
		else
			tg_ssinseq[i] = -99999;
	}
};

void(float seat, float seq) WarpOp_PostMove;   // cl_warpop.qc, Patch 753

void(float seat, float seq, float msec) CSQC_PredictPlayerMove =
{
	local float i, hit, k;
	local vector smin, smax, org1, b0, b1;

	WarpOp_PostMove(seat, seq);
	if (!cvar("cl_triggers")) return;
	if (!tg_n) return;
	tg_cv_debug = cvar("cl_trigdebug");

	if (seq < tg_lastseq || (seq == tg_lastseq && predmove_offset <= tg_lastoffset))
		TG_ChainStart(seq);
	tg_lastseq = seq;
	tg_lastoffset = predmove_offset;
	tg_io_clock = tg_io_clock + msec;

	// One-shot proof of life for the headless tests: it appears exactly once
	// against a remote server, and on a listen server unless cl_predict_listen 0
	// gates the hook off there (Patch 862).
	if (!tg_hookseen)
	{
		tg_hookseen = 1;
		print(sprintf("trig: prediction hook alive (seq %g, %g triggers)\n",
		              seq, tg_n));
	}

	tg_pmins = predmove_mins;
	tg_pmaxs = predmove_maxs;

	/*
	  PATCH 410: UNCONDITIONAL, because the server's is (sv_entities.qc's
	  `pl.run_basevel_armed = FALSE`, whose comment ends "Drop it and a push
	  compounds forever").  This mirror dropped it, and it compounded.

	  The accumulator exists to sum OVERLAPPING pads within one command -- it is
	  written and re-read inside the trigger loop below, and nothing outside this
	  function reads it -- so a per-command clear keeps that sum and kills
	  everything else.  Keying it on `seq` instead assumed one hook call per
	  sequence, and the engine makes two kinds of repeat call: CL_PredictUsercmd
	  splits any command over 50 ms and recurses with the SAME sequence, and the
	  pt_extrap=2 branch re-runs the last replayed command verbatim.  Each repeat
	  folded the previous call's push into the new one, so the mirror rode
	  n x 3000 u/s where the server rode 1 x 3000.

	  MEASURED, surf_666 bonus 3 (the player's own prederr log, 15 consecutive
	  acked commands): the error vector divided by one command of the pad's
	  ramp-clipped carrier, (0, 36, 18) u at pm_ticrate 0.015, gives
	  9,7,9,8,8,8,9,0,8,0,8,0,8,0,-1 -- integers on both components to three
	  decimals, and dx exactly 0.0 on all fifteen.  A client simply running
	  ahead in TIME would have shown 2.007 u of x error per command; there is
	  none, so the offset is parallel to the CARRIER, not to the trajectory.
	  That is also what rules out Patch 403's run_startcap, which was blamed for
	  this in commit 341341b: the server was doing 3243 u/s past a cap of 290.

	  P924 supplies a read-only logical-input offset: increasing offsets at the
	  same sequence continue a split, rather than starting another replay. The
	  once arm and IO chain-start test use that distinction above.
	*/
	tg_pusharmed = 0;
	tg_pushvec   = '0 0 0';

	// The sweep's bounding box, for the cheap reject.  org1 is latched
	// BEFORE any fire: a teleport rewrites predmove_org mid-pass and the
	// remaining probes of this command must still test the path actually
	// travelled, not a line to wherever the first pad put us.
	org1 = predmove_org;
	smin = TG_VMin(predmove_org0, org1) + predmove_mins;
	smax = TG_VMax(predmove_org0, org1) + predmove_maxs;

	for (i = 0; i < tg_n; i = i + 1)
	{
		if (!tg_kind[i])
			continue;                       // demoted to server-only at load
		b0 = tg_bmin[i];
		b1 = tg_bmax[i];
		if (smin_x > b1_x || smin_y > b1_y || smin_z > b1_z)
			continue;
		if (smax_x < b0_x || smax_y < b0_y || smax_z < b0_z)
			continue;
		if (!TG_Overlaps(tg_ent[i], predmove_org0, org1))
			continue;

		// The server's gate: a disabled trigger_teleport returns at its
		// StartDisabled check before the IO touch, and a disabled push or
		// setspeed is SOLID_NOT and never dispatched at all.  Either way:
		// no effect and no edge state while gated off.
		if (tg_io_gated[i] && !TG_IOEff(i, seq))
			continue;

		if (tg_kind[i] == TG_EVENT)
		{
			// trigger_multiple_touch: health gate, IO touch, and the
			// trigger_once retirement.  No noclip gate, no spawnflags gate:
			// the server checks neither on this class.
			if (getstatf(STAT_HEALTH) > 0)
			{
				if (TG_IOEdge(i, seq) && tg_io_once[i])
					TG_IOPush(i, 0, seq, -1);   // spent for this seat
			}
			continue;
		}

		if (tg_kind[i] == TG_TELE)
			hit = TG_FireTeleport(i, seq);
		else if (tg_kind[i] == TG_SPEED)
			hit = TG_FireSpeed(i, seq);
		else
			hit = TG_FirePush(i, seq);

		if (hit && tg_cv_debug)
			print(sprintf("^5trig^7: seq %g trig #%g kind %g fired (org %v vel %v)\n",
			              seq, i, tg_kind[i], predmove_org, predmove_vel));
	}

	// Patch 1025: OnJump, as SV_TriggerJumpEdge in the next PreThink: grounded before this move,
	// not after it, rising; before the end sweep, so a trigger the jump just left still counts.
	if (tg_bvel_ok && tg_endexact && predmove_wasground)
	if (!predmove_onground && predmove_vel_z > 0)
		for (i = 0; i < tg_n; i = i + 1)
			if (tg_kind[i] && tg_io_own[i] && tg_io_in[i] && TG_IOEff(i, seq))
				TG_IOFireEv(i, EV_JUMP, seq);

	TG_IOEndSweep(seq);
	if (tg_endexact && tg_inring)
	{
		k = (seq - TG_RING * floor(seq / TG_RING)) * 4;
		tg_orgring[k]     = predmove_org_x;
		tg_orgring[k + 1] = predmove_org_y;
		tg_orgring[k + 2] = predmove_org_z;
		tg_orgring[k + 3] = seq;
		for (i = 0; i < tg_n; i = i + 1)
			if (tg_io_own[i])
			{
				k = TG_RingAt(i, seq);
				tg_inring[k]     = tg_io_in[i];
				tg_inring[k + 1] = seq;
			}
	}
};

/*
  THE LOAD.  A sixth independent walk of the entity lump (decals, sprites,
  fog, emitters and soundscapes are the other five), from the same hook and
  for the same reason: CSQC_WorldLoaded is the engine's own "the entity lump
  is now readable" point.  Keys are lowercased once and matched against the
  lowercase spelling, which folds the dual-spelling pairs SV_Key2 exists for
  ("Speed"/"speed", "VelocityMode"/"velocitymode") into one comparison --
  safe because no class in scope writes both spellings of one key with
  different values.

  The tri-state keys (UseLandmarkAngles, snapvelocitytodestangles) are the
  exception that proves the rule: ABSENT and "0" are different decisions
  (SV_KeyTri's whole essay), so they are tracked as seen/unseen rather than
  folded into a zeroed float.
*/
void() Trig_LoadForMap =
{
	local string tok, key, cn, mdl;
	local string target, landmark, filt, tname, uselm_s, snapv_s, farg;
	local vector org, ang, pushdir, ssang, ssdir, cvdir;
	local float  spawnflags, disabled, vmode, tspeed, speed;
	local float  hmode, hs, hsmode, vsmode, hsp, vsp, ssstrict;
	local float  negu, negl, ftype, fi, r;
	local float  keeph, keepv, hsamount, vsamount, onthink, interval, everytick;
	local float  kind, i, opened, pend0, waitk, box;
	local entity e;

	// free the previous map's probe edicts
	for (i = 0; i < tg_n; i = i + 1)
		remove(tg_ent[i]);
	tg_n = 0;
	Conveyor_Clear();
	tt_n = 0;
	tg_lastseq = tg_lastoffset = -1;
	tg_teleseq = 0;
	tg_pusharmed = 0;
	tg_hookseen = 0;
	tg_c_tele = tg_c_push = tg_c_speed = 0;
	tg_c_filt = tg_c_dis = tg_c_over = tg_c_nodest = 0;
	tg_c_filtok = 0;
	tf_n = 0;
	tf_over = 0;
	tf_clsdyn = tf_ctspawn = tf_tspawn = 0;
	tg_sk_n = 0;
	tg_needload = 0;
	io_n = 0;
	io_over = 0;
	tgs_head = world;
	tg_c_box = 0;
	ior_n = 0;
	ior_lost = 0;
	tg_io_clock = 0;
	tg_io_tbase = 0;
	tg_iotime0 = time;
	tg_bvel_ok = checkextension("FTESURF_PREDICT_BVSET");
	tg_io_esc = chr2str(27);
	tg_c_event = tg_c_iodem = tg_c_sdok = tg_c_ioown = tg_c_iogated = 0;

	getentitytoken(0);
	opened = FALSE;
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;
		opened = TRUE;

		cn = mdl = "";
		target = landmark = filt = tname = uselm_s = snapv_s = farg = "";
		org = ang = pushdir = ssang = ssdir = cvdir = '0 0 0';
		spawnflags = disabled = vmode = tspeed = speed = 0;
		hmode = hs = hsmode = vsmode = hsp = vsp = ssstrict = 0;
		keeph = keepv = hsamount = vsamount = 0;
		onthink = interval = everytick = 0;
		negu = negl = ftype = 0;
		pend0 = io_n;
		waitk = 0;
		for (fi = 0; fi < 8; fi = fi + 1)
			tg_p_subu[fi] = tg_p_subl[fi] = "";

		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();

			// The server's output capture rule, exactly: ED_ParseUnknownEpair
			// takes keys whose RAW spelling starts with "On" -- case-
			// sensitive, like every other key the engine binds, so a capital
			// "OnThink" is an (inert) output there and never the setspeed
			// dialect key.  Skipping the field matching below for these is
			// the same decision from the other side.
			if (substring(key, 0, 2) == "On")
			{
				TG_IOParse(key, tok);
				continue;
			}

			// The filter keys ED_ParseEdict matches CASE-SENSITIVELY, in both
			// spellings where the server declares both (SV_KeyS2 prefers the
			// capital one; filtertype exists lowercase only).  Captured raw,
			// before the lowercase pass below erases the distinction.
			if (key == "Negated")
				negu = stof(tok);
			else if (key == "negated")
				negl = stof(tok);
			else if (key == "filtertype")
				ftype = stof(tok);
			else if (strlen(key) == 8 &&
			         (substring(key, 0, 6) == "Filter" ||
			          substring(key, 0, 6) == "filter"))
			{
				fi = stof(substring(key, 6, 2)) - 1;
				if (fi >= 0 && fi < 8)
				{
					if (substring(key, 0, 1) == "F")
						tg_p_subu[fi] = tok;
					else
						tg_p_subl[fi] = tok;
				}
			}

			key = strtolower(key);

			if      (key == "classname")              cn       = tok;
			else if (key == "model")                  mdl      = tok;
			else if (key == "origin")                 org      = stov(tok);
			else if (key == "angles")                 ang      = stov(tok);
			else if (key == "targetname")             tname    = tok;
			else if (key == "target")                 target   = tok;
			else if (key == "landmark")               landmark = tok;
			else if (key == "spawnflags")             spawnflags = stof(tok);
			else if (key == "startdisabled")          disabled = stof(tok);
			else if (key == "filtername")             filt     = tok;
			else if (key == "filterclass" || key == "filterteam") farg = tok;
			else if (key == "uselandmarkangles")      uselm_s  = tok;
			else if (key == "snapvelocitytodestangles") snapv_s = tok;
			else if (key == "velocitymode")           vmode    = stof(tok);
			else if (key == "setspeed")               tspeed   = stof(tok);
			else if (key == "pushdir")                pushdir  = stov(tok);
			else if (!strcmp(key, "movedir"))          cvdir    = stov(tok);
			else if (key == "speed")                  speed    = stof(tok);
			// setspeed, new (shipped-FGD) dialect
			else if (key == "horizontalspeedmode")    hsmode   = stof(tok);
			else if (key == "horizontalspeed")        hsp      = stof(tok);
			else if (key == "horizontalspeedangle")   ssang    = stov(tok);
			else if (key == "verticalspeedmode")      vsmode   = stof(tok);
			else if (key == "verticalspeed")          vsp      = stof(tok);
			else if (key == "strictmode")             ssstrict = stof(tok);
			// setspeed, old (this tree's momentum.fgd) dialect
			else if (key == "keephorizontalspeed")    keeph    = stof(tok);
			else if (key == "keepverticalspeed")      keepv    = stof(tok);
			else if (key == "horizontalspeedamount")  hsamount = stof(tok);
			else if (key == "verticalspeedamount")    vsamount = stof(tok);
			else if (key == "direction")              ssdir    = stov(tok);
			else if (key == "onthink")                onthink  = stof(tok);
			else if (key == "interval")               interval = stof(tok);
			else if (key == "everytick")              everytick = stof(tok);
			else if (key == "wait")                   waitk    = stof(tok);
		}

		if (!strcmp(cn, "func_conveyor"))
			Conveyor_Add(mdl, org, cvdir, speed, spawnflags);

		// The targetname table takes EVERY entity, point or brush: the
		// server's find(world, targetname, ...) does not care what class the
		// destination is, and neither may this.
		if (cn == "info_player_counterterrorist")
			tf_ctspawn = 1;
		else if (cn == "info_player_terrorist")
			tf_tspawn = 1;

		if (tname != "" && tt_n < TG_TT_MAX)
		{
			tt_name[tt_n] = tname;
			tt_org[tt_n]  = org;
			tt_ang[tt_n]  = ang;
			tt_n = tt_n + 1;
		}

		// The filter table, for TF_Find.  First row per name wins, matching
		// find(); a table overflow poisons every filtered verdict to UNKNOWN
		// (tf_over), the safe direction.
		if (tname != "" && substring(cn, 0, 7) == "filter_")
		{
			if (tf_n < TF_MAX)
			{
				tf_name[tf_n]  = tname;
				tf_class[tf_n] = cn;
				tf_filt[tf_n]  = filt;
				tf_neg[tf_n]   = negu ? negu : negl;
				tf_type[tf_n]  = ftype;
				tf_arg[tf_n]   = farg;
				for (fi = 0; fi < 8; fi = fi + 1)
					tf_sub[tf_n * 8 + fi] =
						(tg_p_subu[fi] != "") ? tg_p_subu[fi] : tg_p_subl[fi];
				tf_n = tf_n + 1;
			}
			else
				tf_over = tf_over + 1;
		}

		kind = 0;
		if (cn == "trigger_teleport" || cn == "trigger_momentum_teleport")
			kind = TG_TELE;
		else if (cn == "trigger_push")
			kind = TG_PUSH;
		else if (cn == "trigger_setspeed" || cn == "trigger_momentum_setspeed")
			kind = TG_SPEED;
		// A trigger_multiple is an event source and nothing else: it moves
		// nobody, but its touch edges fire the outputs that gate the slots
		// that do.  Slotted only when it owns rows -- there are maps with
		// over a thousand unwired multiples.
		else if (cn == "trigger_multiple" && io_n > pend0)
			kind = TG_EVENT;
		if (!kind)
		{
			for (r = pend0; r < io_n; r = r + 1)
				io_src[r] = (!strcmp(cn, "logic_auto")) ? -3 : -1;
			continue;
		}

		// Not a brush, or not predictable from the lump alone -- except a named trigger with no
		// brush, which may be a zone-tool box (Patch 892, TG_ShapeBoxes).
		box = (mdl == "" && tname != "");
		if (!box && (mdl == "" || substring(mdl, 0, 1) != "*"))
		{
			TG_Skip(TG_SK_NOBRUSH, cn, mdl);
			continue;
		}
		// filt is NOT a skip reason any more: it rides along in tg_filt[] and
		// the resolution pass after the walk decides (filters can follow their
		// triggers in the lump -- futile's do -- the same reason the server
		// resolves on first touch and caches, sv_entities.qc:1353).
		// Neither is `disabled` any more: StartDisabled is IO state, and the
		// IO resolution decides whether this mirror can replicate the state.
		if (tg_n >= TG_MAX)
		{
			tg_c_over = tg_c_over + 1;
			TG_Skip(TG_SK_OVER, cn, tname);
			continue;
		}

		i = tg_n;
		e = spawn();
		if (box)
			e.solid = SOLID_NOT;	// shaped, or demoted, after the walk
		else
		{
			setmodel(e, mdl);
			e.solid = TG_SOLID_BSPTRIGGER;
		}
		// Match the server's rotated brush clip and its linked world bounds.
		e.angles = ang;
		setorigin(e, org);
		e.tg_isbox = box;
		tg_ent[i]   = e;
		tg_kind[i]  = kind;
		tg_flags[i] = spawnflags;
		tg_bmin[i]  = e.absmin;
		tg_bmax[i]  = e.absmax;
		tg_onceseq[i] = tg_onceoffset[i] = -1;
		tg_ssinseq[i] = -99999;
		tg_filt[i] = filt;
		tg_tname[i] = tname;
		tg_sd[i] = disabled;
		tg_io_once[i] = (kind == TG_EVENT && waitk < 0);
		tg_io_on[i] = !disabled;
		tg_io_gated[i] = 0;
		tg_io_own[i] = 0;
		tg_io_in[i] = 0;
		tg_io_seen[i] = -99999;
		tg_io_stamp[i] = 0;
		tg_io_endf[i] = 0;
		tg_io_lastin[i] = -99999;

		if (kind == TG_TELE)
		{
			tg_target[i]   = target;
			tg_landmark[i] = landmark;
			tg_uselm[i]    = (uselm_s != "") ? (stof(uselm_s) != 0) : -1;
			tg_snapv[i]    = (snapv_s != "") ? (stof(snapv_s) != 0) : -1;
			tg_vmode[i]    = vmode;
			tg_tspeed[i]   = tspeed;
			tg_c_tele = tg_c_tele + 1;
		}
		else if (kind == TG_PUSH)
		{
			tg_pushdir[i] = pushdir;
			tg_speed[i]   = speed;
			tg_c_push = tg_c_push + 1;
		}
		else if (kind == TG_SPEED)
		{
			// Dialect, decided exactly as the server decides it: the old one
			// always writes interval/amount/keep keys, the new one never does.
			if (interval != 0 || hsamount != 0 || vsamount != 0 ||
			    keeph != 0 || keepv != 0)
			{
				tg_sshspeed[i] = hsamount;
				tg_ssvspeed[i] = vsamount;
				tg_ssang[i]    = ssdir;
				tg_sshmode[i]  = keeph ? TG_SS_IGNORE : TG_SSH_SETDIR;
				tg_ssvmode[i]  = keepv ? TG_SS_IGNORE : TG_SSV_SET;
				tg_ssevery[i]  = everytick;
			}
			else
			{
				tg_sshspeed[i] = hsp;
				tg_ssvspeed[i] = vsp;
				tg_ssang[i]    = ssang;
				tg_sshmode[i]  = hsmode;
				// 0 is not a vertical mode; an absent key is the FGD
				// default, Ignore.
				tg_ssvmode[i]  = vsmode ? vsmode : TG_SS_IGNORE;
				tg_ssevery[i]  = 0;
			}
			if (ssstrict)
				print(sprintf("^3trig: setspeed #%g has StrictMode -- the "
				              "server's conditions are not mirrored\n", i));
			tg_c_speed = tg_c_speed + 1;
		}
		else
			tg_c_event = tg_c_event + 1;
		for (r = pend0; r < io_n; r = r + 1)
			io_src[r] = i;
		tg_n = tg_n + 1;
	}

	if (!opened)
	{
		// Patch 207's ordering wart: the lump can still be a frame behind the
		// hook.  Retry per frame until it opens, like cl_emit's particle cfg.
		tg_needload = 1;
		return;
	}

	tf_team = (tf_ctspawn || !tf_tspawn) ? 3 : 2;

	TG_ShapeBoxes();

	// Filter resolution, after the walk.  A trigger whose verdict is not a
	// static PASS is demoted: edict freed, kind zeroed, box inverted so every
	// consumer -- fire loop and the trig_* commands alike -- skips the slot.
	for (i = 0; i < tg_n; i = i + 1)
	{
		if (tg_filt[i] == "" || !tg_kind[i])
			continue;                   // no filter, or TG_ShapeBoxes demoted it already
		r = tf_over ? TFR_UNKNOWN : TF_EvalD(TF_Find(tg_filt[i]), 0);
		if (r == TFR_PASS && tg_ent[i].tg_isbox && !TF_KnownD(TF_Find(tg_filt[i]), 0))
			r = TFR_UNKNOWN;            // Patch 906: the server's box is inert, or judged there
		if (r == TFR_PASS)
		{
			tg_c_filtok = tg_c_filtok + 1;
			continue;
		}
		if (tg_kind[i] == TG_TELE)
			tg_c_tele = tg_c_tele - 1;
		else if (tg_kind[i] == TG_PUSH)
			tg_c_push = tg_c_push - 1;
		else if (tg_kind[i] == TG_SPEED)
			tg_c_speed = tg_c_speed - 1;
		else
			tg_c_event = tg_c_event - 1;
		tg_c_filt = tg_c_filt + 1;
		TG_Skip(TG_SK_FILT,
		        (tg_kind[i] == TG_TELE) ? "trigger_teleport" :
		        (tg_kind[i] == TG_PUSH) ? "trigger_push" :
		        (tg_kind[i] == TG_SPEED) ? "trigger_setspeed" :
		                                  "trigger_multiple",
		        tg_filt[i]);
		if (tg_ent[i].tg_isbox)
			tg_c_box = tg_c_box - 1;    // the trig line's boxes are predicted ones
		remove(tg_ent[i]);
		tg_ent[i]  = world;
		tg_kind[i] = 0;
		tg_bmin[i] = '1 1 1';
		tg_bmax[i] = '-1 -1 -1';
	}

	TG_IOResolve();
	Body_TrigSeed();
	if (!tg_inring)
	{
		tg_inring  = memalloc(sizeof(float) * TG_MAX * TG_RING * 2);
		tg_orgring = memalloc(sizeof(float) * TG_RING * 4);
	}
	if (tg_inring)
	if (tg_orgring)
	{
		// Patch 1025: no command recorded on this map yet (-0.5 matches no sequence)
		for (i = 0; i < tg_n * TG_RING; i = i + 1)
			tg_inring[i * 2 + 1] = -0.5;
		for (i = 0; i < TG_RING; i = i + 1)
			tg_orgring[i * 4 + 3] = -0.5;
	}

	tg_map = serverkey("map");
	if (cv_n) print(sprintf("conveyor: %g static ground carriers loaded\n", cv_n));
	print(sprintf("trig: %s -- %g teleports, %g pushes, %g setspeeds predicted (%g zone-tool boxes)\n",
	              tg_map, tg_c_tele, tg_c_push, tg_c_speed, tg_c_box));
	print(sprintf("trig: skipped %g filtered, %g startdisabled, %g over cap; "
	              "%g filtered resolved static; %g targetname rows, %g filters\n",
	              tg_c_filt, tg_c_dis, tg_c_over, tg_c_filtok, tt_n, tf_n));
	print(sprintf("trig: IO %g rows%s, %g gated (%g startdisabled predicted, "
	              "%g event sources), %g demoted, %g event multiples\n",
	              io_n, io_over ? " (TABLE FULL -- named slots demoted)" : "",
	              tg_c_iogated, tg_c_sdok, tg_c_ioown, tg_c_iodem,
	              tg_c_event));
};

void() Trig_Frame =
{
	tg_endexact = (serverkey("fs_endedge") == "1");     // Patch 1025
	Trig_IOMapSpawn();
	if (!tg_needload)
		return;
	Trig_LoadForMap();
};

void() Trig_RegisterCvars =
{
	// Values are read per command inside CSQC_PredictPlayerMove, following
	// Zone_RegisterCvars' pattern: register here, cvar() there.
	registercvar("cl_triggers", "1");
	registercvar("cl_trigdebug", "0");
	registercommand("trig_dump");
	registercommand("trig_here");
	registercommand("trig_tp");
	registercommand("trig_probe");
	registercommand("trig_at");
	registercommand("trig_models");
	registercommand("trig_io");
};

float(string cmd) Trig_ConsoleCommand =
{
	local float i, n, hit, want, t, oi;
	local vector o, b0, b1, ctr;

	if (argv(0) == "trig_dump")
	{
		print(sprintf("trig: map %s, cl_triggers %g, cl_trigdebug %g\n",
		              tg_map, cvar("cl_triggers"), cvar("cl_trigdebug")));
		print(sprintf("trig: %g teleports, %g pushes, %g setspeeds; "
		              "%g skipped filtered, %g startdisabled, %g over cap; "
		              "%g filtered resolved static\n",
		              tg_c_tele, tg_c_push, tg_c_speed, tg_c_filt, tg_c_dis,
		              tg_c_over, tg_c_filtok));
		print(sprintf("trig: %g targetname rows, %g unresolved dests\n",
		              tt_n, tg_c_nodest));
		for (i = 0; i < tg_sk_n; i = i + 1)
			print(sprintf("trig: skip %s %s '%s'\n",
			              (tg_sk_why[i] == TG_SK_FILT) ? "filtered" :
			              (tg_sk_why[i] == TG_SK_DIS) ? "startdisabled" :
			              (tg_sk_why[i] == TG_SK_OVER) ? "over cap" :
			              (tg_sk_why[i] == TG_SK_IO) ? "io-wired" : "no brush",
			              tg_sk_cls[i], tg_sk_name[i]));
		for (i = 0; i < tg_n; i = i + 1)
			if (tg_ent[i].tg_netgate)
				print(sprintf("trig: server-gated #%g %s ready %g on %g\n",
				              i, tg_ent[i].model, tg_ent[i].tg_netready, tg_ent[i].tg_neton));
		print(sprintf("trig: IO %g rows%s; %g gated, %g predicted-disabled, %g ring entries\n",
		              io_n, io_over ? " (TABLE FULL)" : "", tg_c_iogated,
		              tg_c_sdok, ior_n));
		for (i = 0; i < tg_n; i = i + 1)
			if (tg_io_gated[i])
				print(sprintf("trig: io #%g kind %g '%s' %s%s%s\n", i,
			              tg_kind[i], tg_tname[i],
			              tg_io_on[i] ? "ON" : "off",
			              tg_io_own[i] ? " edge-source" : "",
			              tg_sd[i] ? " startdisabled" : ""));
		return TRUE;
	}

	if (argv(0) == "trig_here")
	{
		// The hull from the last predicted command, at the predicted origin;
		// where the hook never ran (cl_predict_listen 0 offline) there is none,
		// so fall back to the Source player hull.
		o = pmove_org;
		if (tg_pmins == '0 0 0' && tg_pmaxs == '0 0 0')
		{
			tg_pmins = '-16 -16 0';
			tg_pmaxs = '16 16 62';
		}
		n = 0;
		for (i = 0; i < tg_n; i = i + 1)
		{
			b0 = tg_bmin[i];
			b1 = tg_bmax[i];
			if (o_x + tg_pmaxs_x < b0_x || o_x + tg_pmins_x > b1_x)
				continue;
			if (o_y + tg_pmaxs_y < b0_y || o_y + tg_pmins_y > b1_y)
				continue;
			if (o_z + tg_pmaxs_z < b0_z || o_z + tg_pmins_z > b1_z)
				continue;
			other = tg_ent[i];
			tracebox(o, tg_pmins, tg_pmaxs, o, MOVE_TRIGGERS | MOVE_OTHERONLY, TG_Probe());
			hit = trace_startsolid || trace_allsolid;
			print(sprintf("trig: #%g kind %g %s target '%s' flags %g%s\n",
			              i, tg_kind[i], hit ? "INSIDE" : "box only",
			              tg_kind[i] == TG_TELE ? tg_target[i] : "",
			              tg_flags[i],
			              (tg_flags[i] & TG_SF_PUSH_ONCE) ? " once" : ""));
			n = n + 1;
		}
		if (!n)
			print("trig: nothing near pmove_org\n");
		return TRUE;
	}

	if (argv(0) == "trig_tp")
	{
		// TEST AFFORDANCE: `cmd setpos` (a cheat command, so this is for the
		// headless harness and not for play) into the middle of the Nth
		// teleport volume, so a prediction test does not depend on a map's
		// spawn happening to face a pad.  With the `walk` argument it instead
		// places the player JUST OUTSIDE the box's -x face, yaw 0, so a
		// +forward crosses the boundary under the player's own power -- which
		// is the case where the client's prediction reaches the volume before
		// the server has even received the crossing command.
		want = stof(argv(1));
		t = 0;
		for (i = 0; i < tg_n; i = i + 1)
		{
			if (tg_kind[i] != TG_TELE)
				continue;
			if (t != want)
			{
				t = t + 1;
				continue;
			}
			b0 = tg_bmin[i];
			b1 = tg_bmax[i];
			ctr = (b0 + b1) * 0.5;
			print(sprintf("trig: tp into #%g target '%s' box %v..%v\n",
			              i, tg_target[i], b0, b1));
			if (argv(2) == "walk")
				localcmd(sprintf("cmd setpos %g %g %g 0 0 0\n",
				                  b0_x - 24, ctr_y, ctr_z));
			else
				localcmd(sprintf("cmd setpos %g %g %g\n",
				                  ctr_x, ctr_y, ctr_z));
			return TRUE;
		}
		print(sprintf("trig: no teleport #%g (have %g)\n", want, t));
		return TRUE;
	}

	if (argv(0) == "trig_probe")
	{
		// DIAGNOSTIC: `trig_probe N x y z` -- one trigger's own submodel asked
		// whether it contains a point, with the box it would be culled by and
		// the model it resolves to.  The server's answer to the same question
		// is `cmd ent_info <classname> x y z`.
		i = stof(argv(1));
		o = [stof(argv(2)), stof(argv(3)), stof(argv(4))];
		if (i < 0 || i >= tg_n)
		{
			print(sprintf("trig: probe: no slot %g (have %g)\n", i, tg_n));
			return TRUE;
		}
		if (!tg_kind[i])
		{
			print(sprintf("trig: probe: slot %g is server-only or empty\n", i));
			return TRUE;
		}
		if (tg_pmins == '0 0 0' && tg_pmaxs == '0 0 0')
		{
			tg_pmins = '-16 -16 0';
			tg_pmaxs = '16 16 62';
		}
		b0 = tg_bmin[i];
		b1 = tg_bmax[i];
		print(sprintf("trig: probe #%g kind %g model '%s' target '%s' flags %g\n",
		              i, tg_kind[i], tg_ent[i].model, tg_target[i], tg_flags[i]));
		print(sprintf("trig: probe box %v..%v org %v\n", b0, b1,
		              tg_ent[i].origin));
		other = tg_ent[i];
		tracebox(o, tg_pmins, tg_pmaxs, o, MOVE_TRIGGERS | MOVE_OTHERONLY, TG_Probe());
		print(sprintf("trig: probe at %v -> startsolid %g allsolid %g frac %g endpos %v\n",
		              o, trace_startsolid, trace_allsolid, trace_fraction,
		              trace_endpos));
		return TRUE;
	}

	if (argv(0) == "trig_at")
	{
		// DIAGNOSTIC: `trig_at x y z` -- every predicted trigger whose BOX
		// contains the point, with the submodel clip's answer beside it.  The
		// server's equivalent is `cmd ent_info <class> x y z`.
		o = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
		if (tg_pmins == '0 0 0' && tg_pmaxs == '0 0 0')
		{
			tg_pmins = '-16 -16 0';
			tg_pmaxs = '16 16 62';
		}
		n = 0;
		for (i = 0; i < tg_n; i = i + 1)
		{
			b0 = tg_bmin[i];
			b1 = tg_bmax[i];
			if (o_x < b0_x || o_x > b1_x || o_y < b0_y || o_y > b1_y ||
			    o_z < b0_z || o_z > b1_z)
				continue;
			other = tg_ent[i];
			tracebox(o, tg_pmins, tg_pmaxs, o, MOVE_TRIGGERS | MOVE_OTHERONLY, TG_Probe());
			hit = trace_startsolid || trace_allsolid;
			print(sprintf("trig: at #%g kind %g model '%s' target '%s' box %v..%v -> %s\n",
			              i, tg_kind[i], tg_ent[i].model,
			              tg_kind[i] == TG_TELE ? tg_target[i] : "",
			              b0, b1, hit ? "INSIDE" : "box only"));
			n = n + 1;
		}
		if (!n)
			print("trig: no predicted trigger box contains that point\n");
		return TRUE;
	}

	if (argv(0) == "trig_models")
	{
		// DIAGNOSTIC: every predicted slot's model, origin and box, one per
		// line, in lump order -- for matching a slot against the server's
		// ent_info answer for the same '*N'.
		for (i = 0; i < tg_n; i = i + 1)
		{
			b0 = tg_bmin[i];
			b1 = tg_bmax[i];
			print(sprintf("trig: #%g kind %g model '%s' org %v box %v..%v target '%s'\n",
			              i, tg_kind[i], tg_ent[i].model, tg_ent[i].origin,
			              b0, b1, tg_kind[i] == TG_TELE ? tg_target[i] : ""));
		}
		return TRUE;
	}

	if (argv(0) == "trig_io")
	{
		// DIAGNOSTIC: the whole captured output graph and the live state of
		// it -- src slot (-3 logic_auto, -1 other entity), event, input,
		// target, delay, times, committed fires; then the pending ring.
		for (oi = 0; oi < io_n; oi = oi + 1)
		{
			print(sprintf("trig: io %g: src %g ev %g inp %g tgt '%s'\n",
			              oi, io_src[oi], io_ev[oi], io_inp[oi],
			              io_tgt[oi]));
			print(sprintf("trig: io %g:     delay %g times %g fired %g\n",
			              oi, io_delay[oi], io_times[oi], io_fired[oi]));
		}
		for (oi = 0; oi < ior_n; oi = oi + 1)
			print(sprintf("trig: ring %g: slot %g val %g seq %g out %g\n",
			              oi, ior_slot[oi], ior_val[oi], ior_seq[oi],
			              ior_out[oi]));		print(sprintf("trig: io %g rows, over %g, clock %g, load time %g\n",
		              io_n, io_over, tg_io_clock, tg_iotime0));
		return TRUE;
	}

	return FALSE;
};
