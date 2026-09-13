/*
===========================================================================
  sh_defs.qc -- constants shared by SSQC and CSQC.

  The movement constants below are DOCUMENTATION, not the implementation.
  Movement is engine-side (engine/common/pm_source.c); these mirror the
  values so the HUD can label things correctly and so QC-side helpers
  (spawn hulls, view offsets) agree with the engine.

  Authority order (CORRECTED in build 41).  Every source below is public:
  Momentum Mod's pre-2020 game code is archived at github.com/momentum-mod/game
  under the Source 1 SDK License.  (Their README explains it -- development went
  closed-source when Valve granted engine access, and the open tree was left up
  deliberately.)  FTESurf copies no code from it; these are the values it had to
  agree with, and where to check them.

    1. mp/src/game/shared/momentum/ in that tree:
         mom_gamemovement.cpp   -- CMomentumGameMovement, the OVERRIDES
         mom_gamerules.cpp      -- g_ViewVectorsMom, the hull and eye constants
         mom_system_gamemode.*  -- GetJumpFactor / GetViewScale / SetGameModeVars
    2. Values measured in-engine against the above and recorded, per build, in
       ENGINE_PATCHES.md in the engine repo (see ENGINE.txt).
    3. gamemovement.cpp / gamemovement_momentummod.cpp -- Momentum's BASE class
       only.  Builds up to 40 treated these as authoritative and got the hull,
       the jump and the mid-air duck all wrong, because CMomentumGameMovement
       overrides every one of them.  Check for an override before quoting them.
===========================================================================
*/

// --- hulls ------------------------------------------------------------------
// Source puts the player origin AT THE FEET, unlike Quake's centred origin.
// Source maps place info_player_* origins on the floor, so we match Source.
//
// These are MOMENTUM's numbers (g_ViewVectorsMom), not CS:S's 72/54/46.  Note
// the standing eye at 64 is deliberately ABOVE the 62-unit crown.
#define PM_HULL_MINS     '-16 -16 0'
#define PM_HULL_MAXS     '16 16 62'
#define PM_DUCK_MINS     '-16 -16 0'
#define PM_DUCK_MAXS     '16 16 45'
#define PM_VIEW_OFS      '0 0 64'
#define PM_DUCK_VIEW_OFS '0 0 47'

// The hull SHRINKS by 62-45 = 17 when you duck, but a mid-air duck only moves
// the origin by GetViewScale() (0.5) of that -- so the feet rise 8.5 and the
// crown drops 8.5.  Builds up to 40 moved it by the whole 17.
#define PM_DUCK_HULL_SHRINK 17
#define PM_DUCK_AIR_SHIFT   8.5

// --- movement ---------------------------------------------------------------
// sqrt(2*800*57), Momentum CGameModeBase::GetJumpFactor().  CS:S's
// 268.3281572999747 (apex 45) is what builds up to 40 shipped, and it made
// every plain jump 9.76 units lower than Momentum's.
#define PM_JUMP_IMPULSE   301.9933774
#define PM_JUMP_APEX      57
#define PM_AIR_CAP        30                 // GetAirSpeedCap()
#define PM_STANDABLE      0.7                // normal_z >= this == ground
#define PM_NONJUMP_VEL    140                // NON_JUMP_VELOCITY
#define PM_STEP_HEIGHT    18
#define PM_TICK           0.015              // 66.666... Hz, 15ms exactly

// Momentum Mod's ground speed, not CS:S's 250.  Only a fallback for the frames
// before sv_maxspeed has been read; cfg/default.cfg is what actually sets it.
#define PM_RUN_SPEED      260
#define PM_WALK_FACTOR    0.52               // -> 135.2
#define PM_DUCK_FACTOR    0.34               // -> 88.4

// --- buttons ----------------------------------------------------------------
// BTN_DUCK is cmd.buttons bit 3, which FTE fills from +button4
// (cl_input.c:1267) and pm_source.c reads as Source's IN_DUCK.
#define BTN_ATTACK  1
#define BTN_JUMP    2
#define BTN_DUCK    8

// pmove_flags, set by the engine when pm_physicsmode is 1 (pmove.h).
#define PMF_JUMP_HELD 1
#define PMF_LADDER    2
#define PMF_DUCKED    4

/*
  --- networked stats --------------------------------------------------------
  Movement is engine-side, so CSQC has no predicted player state of its own to
  read.  The server maps these player fields to client stats (clientstat, see
  SV_RegisterStats) and CSQC pulls them back with getstatf().  On a listen
  server that is exact and one tick old, which is all build 1's HUD needs.

  EV_VECTOR consumes THREE consecutive stat slots, hence the gaps.
*/
#define STAT_FS_VELOCITY   32   // + 33, 34
#define STAT_FS_FLAGS      35   // FL_ONGROUND lives in here
#define STAT_FS_MOVETYPE   36
#define STAT_FS_GROUNDNORM 37   // + 38, 39 -- normal of the surface underfoot

/*
  Board telemetry, written into the player's fields by the engine (Patch 131)
  and relayed here.  run_groundnorm above is a QC re-trace one tick ahead --
  useful for "am I surfing", useless for grading a landing, because it is not
  the plane the engine actually clipped against.  These are.

  run_boardnormal and run_boardvelocity are only meaningful on the frame
  run_boardcount changes; read them at any other time and they are the last
  board's.  cl_board.qc is written to honour that.

  MAX_CL_STATS is 256 (bothdefs.h:1088), so there is plenty of room here.
*/
#define STAT_FS_BOARDNORM  40   // + 41, 42 -- the ramp plane we clipped
#define STAT_FS_BOARDVEL   43   // + 44, 45 -- velocity going in, BEFORE the clip
#define STAT_FS_BOARDCOUNT 46   // monotonic; edge-detect this, never a flag
#define STAT_FS_RAMPCONTACT 47  // 1 while riding; the falling edge is "left"

// pmove_flags, for PMF_DUCKED.  The duck state is NOT in .flags -- it lives
// in the engine's pmove and is written back to pmove_flags each move
// (sv_user.c) -- and the strafe ideal needs it, because crouching crops the
// wishspeed and the ideal turn rate follows it down.
#define STAT_FS_PMFLAGS    48

/*
  The plane the CURRENT tick clipped against (engine Patch 137).

  STAT_FS_BOARDNORM above is the plane of the last board ENTRY and is latched on
  purpose -- it has to be, or the board grade would re-fire on every tick of a
  ride.  The strafe bar wants the opposite: the plane you are on right now,
  updated as a curved ramp turns underneath you.  Same find-by-name field
  mechanism as the four run_board* fields; written on every tick rampcontact is
  set, and zeroed when it is not.
*/
#define STAT_FS_RAMPNORM   49   // + 50, 51

/*
  VF_SKYROOM_CAMERA (pr_common.h:849).  A real CSQC viewproperty -- pr_csqc.c
  handles it in both getproperty and setproperty -- but pr_dumpplatform does
  not emit it, so it is absent from cl_defs.qc and has to be named here.
  Used by CSQC_UpdateView to drive the 3D skybox; see cl_decals.qc.
*/
#define VF_SKYROOM_CAMERA  222

/*
  --- the run timer ----------------------------------------------------------

  The state machine lives on the SERVER (sv_timer.qc) because zone entry is a
  question about the authoritative origin, and because the recorder has to
  sample the post-move position rather than a rendered one.  Everything the HUD
  needs comes back through these stats; CSQC owns none of it.

  TIME IS CARRIED AS TICKS, not seconds.  Momentum's leaderboard times are
  integer tick counts (m_iEndTick - m_iStartTick) and comparing anything else
  to them is a rounding argument waiting to happen -- so the stat is an exact
  integer and only the display divides by the tick rate.  A float holds an
  exact integer to 2^24, which at 66.67 Hz is 69 hours.
*/
#define STAT_FS_TIMERSTATE  52   // TS_*
#define STAT_FS_TIMERTICKS  53   // elapsed, in ticks
#define STAT_FS_TIMERSEG    54   // SEGMENT in progress, 0-based: segment s is stage s+1 (leg s+1)
#define STAT_FS_TIMERSEGS   55   // segments in this track; 1 means linear
#define STAT_FS_TIMERTRACK  56   // 0 main, N bonus N
#define STAT_FS_TIMERFLAGS  57   // TF_*
#define STAT_FS_TIMERSPLIT  58   // ticks at the last split
#define STAT_FS_TIMERDELTA  59   // that split minus the PB's, in ticks (signed)
#define STAT_FS_TIMERPB     60   // this leg's personal best, in ticks; 0 = none

// The save-lock list, so the menu can draw "3/7" without owning the data.
#define STAT_FS_SAVECOUNT   61
#define STAT_FS_SAVEINDEX   62   // 1-based; 0 when the list is empty

/*
  WHICH RUN, so the client's angle sidecar can name the same file the server's
  .rec will be named.

  The two files are written by two different VMs, one tick apart, and nothing
  connects them but their names.  The server owns the naming -- it is the one
  that knows which leg was run and whether the result was a personal best -- so
  it publishes both halves and the client spells the name out of them:

      data/runs/<map>/<leg>/<ticks>_<pb|shadow>.view       (FS_RunPath below)
      data/runs/<map>/<leg>/<last|cheat>.view              -- the unstamped pair

  RUNLEG is track*100+leg+1, and 0 means "no run".  The +1 is not decoration:
  track 0 leg 0 is the main track's full run, the most common leg there is, and
  without it that leg would encode to the same 0 a discarded run leaves behind.
  The server's PB table bounds a leg by FS_MAXSPLITS (24), so the pack cannot
  carry.

  BUILD 57: A LEG, WHERE IT WAS THE STARTING SEGMENT.  0 is the full run and k is
  stage k -- see FS_LegOf.  The old packing could not tell a stage-1 run from a
  full run, because both begin at segment 0, and so stage 1 was the one stage
  that could never be a leg of its own.

  RUNTAG is written at the moment the run closes and left standing until the
  next one opens, which is at minimum a re-arm away -- many frames, so the
  client cannot miss it through a dropped snapshot.  It is the whole reason the
  client can write straight to the final name and the server never has to rename
  a file the client is still holding.
*/
#define STAT_FS_RUNLEG      63   // track * 100 + leg + 1, while recording; 0 = no run
#define STAT_FS_RUNTAG      64   // RT_*, at the moment the run ends

/*
  BUILD 23.  The run's final tick count, published in the SAME breath as RUNTAG
  and left standing exactly as long.

  It exists because the time is now part of the filename, and the client has no
  other way to know it.  STAT_FS_TIMERTICKS is the LIVE clock: by the time the
  client renders the frame that sees RUNTAG change, the timer has been re-armed
  or idled and that stat reads whatever the next attempt is doing.  Spelling the
  sidecar's name from it would name a file the server never wrote -- silently,
  and only on the runs that matter, because a fast re-arm is what a good player
  does after a good run.
*/
#define STAT_FS_RUNTICKS    71

/*
===========================================================================
  BUILD 24 -- A STAGE FINISHED INSIDE A MAIN RUN, AND ITS OWN DEMO.

  You complete every stage of a map on the way through it, and until now none of
  those were recorded as stage runs: the only way to get a row in
  data/runs/<map>/stage_N/ was to arm at that stage's own zone and run it
  deliberately.  So the stage leaderboards on a map you have been grinding for an
  hour were empty.

  ONLY STAGES THAT BEGAN WITH A JUMP, and that filter is the whole design.  On a
  staged surf map some stage boundaries are a platform you land on, stand on and
  jump off -- those are real stage starts and their times are comparable with a
  deliberate stage run.  Others are a plane you fly through at 2000 u/s, which is
  a checkpoint wearing a stage's clothes; timing "your stage 4" from there would
  produce a leaderboard where the only thing being measured is how fast you
  arrived.  SV_StageJump is the test and it is deliberately the narrow one: a
  jump, from a ground phase, with NO ramp contact since the boundary.

  THE FOUR STATS ARE WRITTEN IN ONE BREATH, which is the property that makes
  them safe -- the same one STAT_FS_RUNTAG and STAT_FS_RUNTICKS have.  The client
  edge-detects STAGEREC and writes its own .view slice for exactly the leg and
  exactly the filename the server just wrote a .rec for, so the pair cannot be
  named differently by two spellers.  STAGEAT is sent rather than left to the
  client's own arithmetic over its split list for the same reason: a client that
  dropped one snapshot would compute a start tick that is one boundary out and
  write a sidecar that pairs with nothing.

  STAGEREC never resets while connected, so a missed snapshot is a skipped
  number and not a missed event -- and a skipped number means one stage demo has
  no sidecar, which the reader already handles, rather than a wrong one.
===========================================================================
*/
#define STAT_FS_STAGEREC    72   // monotonic; the edge, never a flag
#define STAT_FS_STAGESEG    73   // the SEGMENT written; its leg is seg + 1 (build 57)
#define STAT_FS_STAGETICKS  74   // the stage's own duration -- the filename stamp
#define STAT_FS_STAGEAT     75   // the run clock the stage STARTED at

/*
  SAVE STATES, and the handshake that keeps the client's half of the recording
  in step with the server's.  Build 17.

  A save writes the recording's PREFIX -- the movement up to the save point --
  and loading it rewinds the recorder to that mark and carries on appending, so
  a run that is saved, failed twice and finished is one continuous file.  The
  server owns .rec; the client owns .view, and the client cannot see a save
  happen, because a save is a client COMMAND handled on the server and nothing
  comes back but stats.

  So these two are that signal, and they are the same edge-detect the recorder
  already uses for TF_RECORDING:

    SLSEQ   a counter, bumped on every create and every load.  Never reset while
            connected, so a missed snapshot is a skipped number rather than a
            missed event -- the client re-syncs on the next one instead of
            silently writing a sidecar against the wrong mark.
    SLOP    what that bump WAS: op * FS_SLOP_RADIX + slot id.  Two fields in one
            stat because they are only ever read together and only ever on the
            frame SLSEQ changes.  Slot ids are 0..FS_MAXSAVES, and the radix is
            one past the largest, so the pack cannot carry.

  BUILD 25: THE RADIX AND THE PACK GET NAMES, because the id space grew.

  It was a literal 100 in four places -- one encoder in sv_saveloc.qc and three
  decoders, in cl_board.qc, cl_saveloc.qc and cl_replay.qc -- each spelling
  `floor(v / 100)` and `v - floor(v / 100) * 100` by hand.  Widening the slots to
  999 means all four have to move together and a missed one does not fail: it
  decodes op 9 id 61 out of a perfectly good SLOP_LOADED of slot 961 and quietly
  ignores the event.  Same argument as FS_RunPath in build 23 and FS_IsSample in
  build 24, and the same fix -- one definition, in the file all three VMs compile.

  The ordering that makes this safe is the same one the .rec/.view pair already
  relies on: the server acts inside a physics tick, the client sees the stat on
  its next RENDERED frame, which is strictly afterwards.  Neither ever has the
  same path open as the other.
*/
#define STAT_FS_SLSEQ       65   // monotonic; edge-detect it
#define STAT_FS_SLOP        66   // SLOP_* * FS_SLOP_RADIX + slot id
#define STAT_FS_SAVETICKS   67   // the run clock stored in the CURRENT slot

// One past the largest slot id.  See the essay above; do not open-code it.
#define FS_SLOP_RADIX 1000

/*
  THE PARKED VELOCITY.  Build 30.

  A save-lock hold is a real freeze -- SV_SaveLocHold sets MOVETYPE_NONE and
  zeroes .velocity, and SV_SaveLocHoldFrame re-zeroes it every tick -- so
  STAT_FS_VELOCITY reads '0 0 0' for as long as the load key is down.  The HUD
  read that verbatim and had no way to know why, which is the whole of "it shows
  0 speed and the wrong energy until you let go":

      the speedometer printed 0, and
      Strafe_Energy lost its entire |v|^2/2g term, so `e` collapsed to bare
      height -- a reading that is not merely stale but a different quantity.

  The velocity is NOT un-zeroed to fix this.  The freeze depends on the zero,
  PM_NONE depends on it, and the essay at the top of sv_saveloc.qc records that
  the implementation which kept the player moving is exactly what produced the
  snapping this one replaced.  So the save's velocity is PUBLISHED ALONGSIDE the
  zero instead, and the HUD prefers it while HOLD is set.  Nothing on the server
  changes behaviour; two stats are added and one branch reads them.

  HOLD is a mirror of .rec_sl_hold, in the same way TF_FROZEN mirrors
  .run_t_freeze: the request lives in the field and this is the copy the client
  is allowed to see.  It gates the read, so a client that never looks at HOLDVEL
  cannot pick up a stale one.
*/
#define STAT_FS_HOLD        76   // 1 while a save-lock hold is parked
#define STAT_FS_HOLDVEL     77   // + 78, 79 -- the velocity the save is holding

/*
  GHOST.  Build 30.  1 while the camera is detached and the body is coasting.

  A REAL STAT RATHER THAN A CLIENT-SIDE GLOBAL, unlike rec_wt_on, and the
  difference matters.  A replay is a client-side fiction -- cl_keys.qc:57-59
  records that there is no builtin to write a stat from CSQC, which is why the
  replay override block exists at all.  A ghost is the opposite: the SERVER is
  the one that has stopped testing zones, so the server is the one that gets to
  say whether it is happening.  The client mirrors this every frame rather than
  latching its own answer when `ghost` is typed, so the picture can never be
  detached while the server still thinks the body's crossings count.
*/
#define STAT_FS_GHOST       80

/*
===========================================================================
  BUILD 43 -- THE STAGE IN PROGRESS, WHICH NOTHING PUBLISHED UNTIL NOW.

  Build 24 published what a stage had ALREADY DONE (the STAGEREC four, written
  in one breath at SV_StageClose) and nothing at all about the one you are
  standing in.  That was tolerable while a stage was a plane crossing and a
  filter nobody could see fire: `cmd timer` was enough, because the only
  question was after the fact.

  Build 43 makes a stage something you ARM and START and can FAIL, and all
  three of those are things you do with your hands and need to see the result
  of within a second.  A reset that is invisible is worse than no reset -- you
  would go on running a stage whose clock has silently gone back to zero.

  THREE STATS AND NOT ONE, because they are three different lifetimes:

    FAILS   a COUNTER, and the client edge-detects it the way it edge-detects
            STAGEREC and STAT_FS_TIMERCP.  It is not a flag and must not be
            read as one: two resets in quick succession are two events, and a
            boolean would collapse them into one flash.  Zeroed at a genuine
            boundary, which is the only place a "reset" can go backwards --
            and going backwards is not an event either, so the edge test is
            "greater than", not "different from".

    ST      a PACKED WORD of the SF_* bits below.  One stat rather than five,
            for the reason STAT_FS_SLOP gives about its own pack: these are
            only ever read together, on the same frame, and a bit that arrived
            a snapshot after its neighbours would describe a state that never
            existed.  Bits and not a small enum because they genuinely co-occur
            -- armed AND dirty is the ordinary state of a stage you noclipped
            back to the top of.

    BASE    the run clock the stage in progress is being timed FROM.  Optional
            in the sense that nothing breaks without it, and worth its slot
            anyway: with the arm rule this number MOVES after the boundary --
            when you walk out of the box -- and "my stage split is not what I
            expected" is answerable from this and from nothing else on screen.

  Ceiling is 256 and 80 was the highest in use, so this is not near anything.
===========================================================================
*/
#define STAT_FS_STAGEFAILS  81   // monotonic within a stage; edge-detect it
#define STAT_FS_STAGEST     82   // SF_* packed
#define STAT_FS_STAGEBASE   83   // the run clock the stage is timed from

/*
  The env_fog_controller the server has put THIS player on, by targetname.  A
  string stat (EV_STRING), which is why it is out here on its own rather than
  packed with anything.

  It has to be per-player and it has to not be a stuffcmd.  Source fires
  SetFogController at !activator from a trigger, so two players standing in
  different fog volumes genuinely want different fog -- that rules out
  serverinfo, which is global.  And a stuffcmd runs at RESTRICT_SERVER, which
  makes CL_Fog_f latch cl.fog_locked (engine cl_main.c); after that the player's
  own vbsp_fog toggle is refused, and refused SILENTLY.  A stat is per-client by
  construction, reliable, delta-compressed, and recorded into demos and replays,
  which is everything this needs.

  Empty means "the server has not moved you", and the map's own default
  controller stands.  cl_fog.qc edge-detects it.
*/
#define STAT_FS_FOGCTRL     84   // targetname of the player's fog controller

/*
===========================================================================
  BUILD 48 -- SAYING WHAT CLOSED.  Five stats, and the first four exist
  because the question they answer is otherwise UNANSWERABLE, not merely
  awkward.

  THE PROBLEM.  STAT_FS_STAGEST describes the stage IN PROGRESS.  At a
  boundary the stage that just ended is gone before any snapshot can be built,
  by two independent mechanisms:

    on a SPLIT   SV_StageOpen re-reads dirty, cheat and ghost from the LIVE
                 LEVEL and zeroes stitch, jump, ramp and hold -- all seven
                 inputs -- in the same PlayerPostThink;
    on a FINISH  there is no SV_StageOpen at all.  SV_StageClose sets
                 run_st_seg = -1 and SV_StageStat's own `if (run_st_seg < 0)
                 w = 0` guard zeroes the word instead.

  The engine samples QC-backed stats when it builds the snapshot, which is
  strictly after every PlayerPostThink, and it deltas against the last value it
  SENT.  So a value that appears and disappears inside one PlayerPostThink is
  never compared against anything and never reaches the wire at all.  This is
  not a race the client narrowly loses and could win with a latch -- there is
  no client-side arrangement that can read it, and a "previous tick" latch is
  not even expressible up there, because CSQC_UpdateView runs per RENDERED
  FRAME and sees four to six frames carrying one snapshot's values.

  SV_StageOpen's own essay saw this coming: "Nothing reads it in that tick
  today -- SV_StageClose runs at the NEXT boundary -- but 'nothing reads it
  yet' is a claim about the whole file."  These stats are that reader.

    ENDREC     monotonic, bumped at the TOP of SV_StageClose on EVERY close
               INCLUDING THE REFUSED ONES.  A counter and not a boolean for the
               reason STAGEREC is one: a one-tick flag is lost outright when a
               snapshot is dropped, whereas a counter that jumps by two is a
               gap the reader can SEE and account for.  It must count refusals
               because a refused stage is exactly the one the mark is about.
    ENDSEG     the segment that closed.
    ENDST      its SF_* word, as it stood at the close.
    ENDTICKS   ticks - run_st_tick.  NOT derivable up there: run_stagearm
               rebases run_st_tick when you leave the boundary box, so a
               stage's own duration is not the difference between two
               consecutive run-relative splits and never was.

  DELIBERATELY NOT GATED BY A CVAR, alone among build 48's additions.  Every
  new RULE here gets a bisection; a REPORT must not have one, because a switch
  on a diagnostic is a setting at which the diagnostic lies.

  PBWAS is separate and fixes a shipped defect rather than enabling a feature.
  SV_TimerFinish re-reads run_t_pb AFTER it has already overwritten
  run_pb_ticks, so on any personal best TIMERPB equals TIMERTICKS and the
  finish row's delta has been identically zero since build 19.  This carries
  the value the run was actually measured against, latched before the table is
  rewritten.

  THE FREE RANGE IS 85..219, NOT 85..255, and the paragraph above at
  STAT_FS_STAGEBASE that says "ceiling is 256" is true of the array and
  misleading about the usable space.  The engine assigns 36 STAT_MOVEVARS_* in
  220..255 and writes them for every PEXT2_PREDINFO client BEFORE
  SV_UpdateQCStats runs -- so a QC stat placed there wins the write and
  corrupts the client's own movement prediction inputs.  32..84 is perfectly
  packed with no reclaimable gaps: the defines appear out of numeric order in
  this file, which makes the block LOOK holed and does not make it so.
===========================================================================
*/
#define STAT_FS_STAGEENDREC    85   // monotonic; edge-detect it, and mind gaps
#define STAT_FS_STAGEENDSEG    86   // the segment that just closed
#define STAT_FS_STAGEENDST     87   // its SF_* word at the close
#define STAT_FS_STAGEENDTICKS  88   // its own duration, in ticks

/*
  The personal best this run was measured against, latched before the PB table
  is rewritten.  0 = there was none.  See the essay above.
*/
#define STAT_FS_TIMERPBWAS     89

/*
  90 and 91 ARE RESERVED FOR A GLOBAL LEADERBOARD -- a rank and an entry count
  -- and are deliberately NOT registered with clientstat.

  Reserved rather than defined, because a stat that exists and is permanently
  zero is a promise the server is not keeping, and the results card has to be
  able to tell "no board" from "rank 0".  It draws its world row from the
  ABSENCE of a board, not from a zero in a slot.  When the board is real, these
  two numbers are what it sends, and nothing above this line has to change.

    90  STAT_FS_WORLDRANK
    91  STAT_FS_WORLDOF
*/

/*
===========================================================================
  BUILD 65 -- WHERE THE RUN YOU JUST SET LANDED, AS ONE USERINFO KEY.

  THE RESERVATION ABOVE STANDS AND IS NOT WHAT SHIPPED.  Two stats cannot say
  what this has to say, and the reason is worth writing down before the next
  person tries to "finish" the reservation.

  A stat is a bare number with no subject.  The results card is drawn for ONE
  finish -- a track, a leg, a tick count -- and the answer from the directory
  arrives some milliseconds LATER, over a network, after the card is already
  up.  A pair of stats holding (3, 17) cannot tell the card whether that 3 is
  the rank of the run it is drawing, of the previous leg, or of the last run on
  the map before this one.  The card would draw a stale rank against a fresh
  time and be believed, which is worse than the dash it draws today.

  So the answer carries its own subject.  One key, seven fields:

      *wrank = "<map> <track> <leg> <ticks> <state> <rank> <of>"

  and the card draws it ONLY when all four of map, track, leg and ticks are the
  run in front of it.  Anything else is an answer about a different run and is
  not shown.

  THE MAP IS IN THERE FOR A REASON THAT IS NOT PARANOIA.  A map change does not
  disconnect anybody, and only a CONNECT clears a player's fields (ED_Clear,
  sv_user.c:5654), so this key outlives the map it was set on.  Track, leg and
  ticks alone would then match across maps -- and "leg 1 of track 0 took 4108
  ticks" is an ordinary coincidence between two short bonus legs, not a remote
  one.  The result would be a rank from the previous map drawn against this
  map's time, which is precisely the stale-and-believed failure this whole
  design exists to avoid.

  A `*` KEY, WHICH IS THE SECURITY OF IT.  Info keys beginning with `*` cannot
  be set by the client (only forceinfokey reaches them -- pr_cmds.c:11614 says
  so in as many words), so a player cannot award themselves a world record by
  typing setinfo.  It is also, by SV_UserInfoIsBasic (sv_user.c), a BASIC key:
  every `*` key is broadcast to every client, so this is readable for any
  player on the server and not merely for oneself.  That is deliberate -- it is
  what a "so-and-so just took #1" line would be built from later.

  STATE, BECAUSE "NO NUMBER" HAS FOUR DIFFERENT MEANINGS and the card must not
  print the same dash for all of them.  A server that does not rank at all is
  not the same sentence as a directory that refused the key, and neither is the
  same as a run that is ineligible for a board.
===========================================================================
*/
#define WR_PENDING      0       // submitted; the directory has not answered yet
#define WR_RANKED       1       // rank and of are real
#define WR_NOBOARD      2       // 204: practice or cheated, no board exists
#define WR_FAILED       3       // the directory refused it or could not be asked
#define WR_STORED       4       // accepted, but the answer carried no position

/*
  WR_STORED IS NOT A ROUNDING OF WR_FAILED, and the difference is the whole
  reason this build exists.

  A directory that accepts a run and does not say where it landed is a SUCCESS.
  It is what a surfd older than this build answers -- /api/run returned
  {"ok","stored","best"} and nothing else -- and it is therefore exactly what a
  server running these progs against a directory that has not been updated will
  see, which is a window an operator can create by deploying in the wrong
  order.  Folded into WR_FAILED, the game would tell a player "the leaderboard
  did not take your run" about a run that is sitting on the leaderboard.

  That is the same class of false statement as the report this whole build
  started from, pointing the other way, and it would be harder to catch:
  nothing anywhere would disagree with it.
*/

/*
===========================================================================
  BUILD 57, STAGE T -- FIVE STATS, SO A TIME SET ON A PUBLIC LOBBY IS KEPT ON
  THE PLAYER'S OWN PC.

  The choice this implements is "just me, on my PC": a lobby time goes into this
  player's own records and nowhere else.  Nothing is uploaded and no identity is
  involved, so the server's whole job is to MEASURE and to SAY -- the file is
  written by the client, in client/cl_lobbytime.qc.

  WHY THE CLIENT CANNOT ALREADY SEE A LOBBY FINISH, which is the reason 93..96
  exist rather than the card reading what is on the wire already:

    RUNTAG stays RT_NONE   a lobby switches the recorder off (Lobby_NoRec), so
                           SV_RecClose -- the only writer of RUNTAG, RUNTICKS
                           and RUNLEG at a finish -- is never reached.
    TS_FINISHED can be     run_t_pendarm re-arms a chained stage run in the SAME
    skipped outright       server frame it finished in, and the engine deltas a
                           stat against the last value it SENT: a state written
                           and overwritten inside one PlayerPostThink was never
                           on the wire to be read.

  So a finish is published as a COUNTER with its answer beside it -- the
  arrangement STAT_FS_STAGEREC and STAT_FS_STAGEENDREC already use, and for the
  same reason: a lost snapshot becomes a GAP the reader can account for rather
  than an event that silently did not happen.

  FINREC IS BUMPED BY EVERY SV_TimerFinish, lobby or not.  A counter that only
  ran in lobbies would be a second rule to remember at the one site that owns
  the finish, and the client's gate is STAT_FS_LOBBY -- a fact about the SERVER,
  not about this run.

  THE FOUR ANSWERS ARE WRITTEN IN ONE BREATH with the counter LAST, so no
  snapshot can carry the counter ahead of the values it describes.  They are NOT
  cleared by the next arm: `results` reopens the last card, and a value that died
  with the attempt would make that command lie.  RUNTAG has stood the same way
  since build 23 for exactly that reason.

  90 AND 91 ARE STILL NOT HERE.  They stay reserved and unregistered for a world
  board, which this feature deliberately is not -- see the block above.  The
  unbuilt avatar stats an older plan pencilled in at 94/95 move to 97/98.
===========================================================================
*/
/*
  STAT_FS_LOBBY IS THREE BITS, and the reason is that "this is a lobby" and "the
  server is keeping nothing for this run" are different questions with different
  answers.

  Lobby_Active() is one cvar; Lobby_NoPB() and Lobby_NoRec() are that cvar AND
  their own.  cfg/lobby.cfg sets all three, so on a real lobby the three bits
  arrive together -- but lobby_enable 1 with lobby_nopb 0 is a listen server that
  writes best.pb and the .rec archive to THIS disk, and a client that kept its own
  copy there would file the same run twice: two rows on the leaderboard's leg, and
  a rank total inflated by its own duplicate.

  So the client keeps a time only when the server is keeping NEITHER, and the
  card's "am I on a lobby" test stays bit 0.  A reader that wants the old meaning
  masks LS_LOBBY -- the raw value is no longer 0-or-1 and `if (getstatf(...))`
  would now be true for a configuration that means the opposite.
*/
#define STAT_FS_LOBBY      92   // LS_* bits below
#define LS_LOBBY            1   // Lobby_Active(): this server is a public lobby
#define LS_NOPB             2   // Lobby_NoPB():  it keeps no best.pb for this run
#define LS_NOREC            4   // Lobby_NoRec(): it keeps no .rec for this run
#define STAT_FS_FINREC     93   // monotonic; EVERY finish bumps it.  Edge-detect it
#define STAT_FS_FINTICKS   94   // the time that finish was measured at
#define STAT_FS_FINLEG     95   // RUNLEG's encoding: track * 100 + leg + 1
#define STAT_FS_FINFLAGS   96   // TF_*, as the finish decided them

/*
  STAT_FS_STAGEST's bits.

  32 and 64 were reserved by build 43 and are ASSIGNED HERE by build 44, exactly
  as reserved: they split SF_DIRTY the way TF_SEGMENT and TF_CHEAT split
  TF_PRACTICE, and the reservation is why the two halves of that change could not
  pick different numbers.

  SF_DIRTY REMAINS THE UMBRELLA and is what SV_StageClose refuses on -- both new
  bits imply it, so no filter anywhere had to learn them.  They are published so
  that "my stage did not record" has three different answers rather than one:
  `cmd timer`'s `stage class:` line reads them, and SV_StageWrite puts the same
  distinction in the header of every stage file it writes.

  THE HUD READS ONLY THE UMBRELLA, deliberately.  The word under the clock
  already names the run's class, and a stage that is dirty inside a dirty run
  would be saying it twice; what the sub-label draws is the DISAGREEMENT --
  `stage clean` when the run is not -- which is the half build 43 made possible
  and nothing could see.
*/
#define SF_ARMED      1  // standing in the boundary box; the clock has not rebased
#define SF_JUMP       2  // this stage began the way a run begins -- it is recordable
#define SF_RAMP       4  // a ramp has been touched since the boundary
#define SF_DIRTY      8  // THIS STAGE is tainted, whatever the run around it is
#define SF_GHOST     16  // the camera was detached during this stage
#define SF_STITCH    32  // a save state was used inside THIS stage
#define SF_CHEAT     64  // noclip, setpos or sv_cheats inside THIS stage

/*
  BUILD 48: SOMEBODY ANSWERED.  Not a state -- a marker that the word is real.

  Every other bit here is a fact about a stage.  This one is a fact about the
  REPORT, and it is what separates "this stage was clean" from "nothing told me
  about this stage", which are the same zero without it.

  Three readers need that distinction and all three would otherwise fail the
  same way -- by drawing a confident, wrong answer:

    * a client built against build 48 talking to a server that is not.  A
      QC-only rebuild that leaves the other .dat stale is a mistake this project
      has already paid for once; every new stat reads 0 in that case, and 0
      without this bit is indistinguishable from a clean stage.  With it, the
      marks simply do not appear, which is the correct behaviour for a client
      that has not been told anything.
    * a stage the server never closed -- a run still in progress, or one that
      ended some way that never reached SV_StageClose.
    * a REPLAY.  A .rec carries no per-stage taint and build 48 deliberately
      does not widen it to add one, so a replayed row has nothing to say.  This
      is the same answer Timer_DrawPanel already gives for the stage-arm state:
      a replay passes zeroes and that is CORRECT, not a stub -- inventing a
      class from a file that never recorded one would be worse than the mark
      being absent.

  SET BY THE SERVER, in SV_StageWord, on every word it packs -- including the
  ones that are otherwise zero, which is the whole point.  A reader tests this
  FIRST and stops if it is clear.

  128 and not a ninth stat: it costs nothing, it travels with the value it
  qualifies, and it therefore cannot arrive a snapshot apart from it -- which
  is the same argument the block above makes for packing the SF_* bits into one
  word in the first place.
*/
#define SF_KNOWN    128  // this word was actually reported; 0 alone means "not told"

/*
  BUILD 57, STAGE T: DID THIS STAGE QUALIFY?  The SERVER's answer, so that a
  second writer of stage times never re-implements the rules.

  SV_StageQualifies (sv_timer.qc) is the jump filter, the taint rules and the
  start rules of the stage a run began with, lifted out free of side effects.
  The client cannot derive any of it: run_st_jump is a grounded-jump detector
  with a ramp latch, and the start rules read the run's TF_PRACTICE as it stood
  at the arm.  client/cl_lobbytime.qc writes a file on exactly this bit.

  ON THE CLOSE WORD ONLY -- STAT_FS_STAGEENDST -- AND NEVER ON THE PER-TICK ONE.
  SV_StageWord is shared by both and cannot set this itself: by the time
  SV_StageClose takes the close report it has already put run_st_seg back to -1,
  so that function has no segment left to ask about.  The close site passes the
  segment it latched, which is the only place the right answer exists.  A reader
  of STAT_FS_STAGEST must therefore NOT test this bit -- it is always clear
  there, which is the same "0 means not told" trap SF_KNOWN exists for one bit
  along.

  IT IS NOT A FILTER THE SERVER USES.  SV_StageClose keeps its own refusals --
  is there a recording to slice, may a lobby keep it, did it beat the leg's best
  -- because those are questions about what gets WRITTEN.  This bit says only
  that the STAGE was legitimate, which is the half a second keeper needs.
*/
#define SF_QUALIFIES 256  // SV_StageQualifies said yes.  The CLOSE word only

/*
  Radians to degrees.

  It lived in sh_strafe.qc, which only the CLIENT compiles (cl_progs.src:10).
  Build 25's ramp-plane report is a server-side measurement that prints an angle,
  so it moved here -- the file all three VMs compile -- rather than being spelled
  a second time next to the one print that needed it.
*/
#define DEG_PER_RAD     57.29577951308232

/*
  The serverinfo `maxfps` key, which bounds the client's USERCMD rate.

  Absent, the client falls back to 72 and clamps cl_netfps to it -- see the long
  note at the publish site in SV_TimerMapInit, which has the engine lines.  1000
  because it is a ceiling rather than a target: no tick rate this mod will ever
  run approaches it, and a ceiling that binds is the failure being fixed.
*/
#define FS_SERVERMAXFPS 1000

float(float op, float id) FS_SlopPack = { return op * FS_SLOP_RADIX + id; };
float(float v)            FS_SlopOp   = { return floor(v / FS_SLOP_RADIX); };
float(float v)            FS_SlopId   = { return v - floor(v / FS_SLOP_RADIX) * FS_SLOP_RADIX; };

/*
  CHECKPOINTS ON THE WIRE.  Build 19.

  Until now a checkpoint bumped a counter and wrote one line into the .rec, and
  nothing at all reached the client -- the design note said checkpoints exist to
  compare against afterwards rather than to read while moving.  On a linear map
  like surf_utopia that is the whole of the timing information: it has no stages,
  so its four checkpoint regions were the only structure the run had and the
  split list sat empty from the start zone to the finish.

  These three are STAT_FS_TIMERSEG / SPLIT / DELTA repeated for checkpoints,
  deliberately and exactly, because the stage triple's one safety property is
  worth copying: all three are written inside the same physics tick, so the
  client can read TIMERCPT and TIMERCPD on the TIMERCP edge with no race.

  TIMERCP is the checkpoint's ORDINAL within its segment, not a crossing count.
  It has to be an ordinal for the PB table to have an index, and it is strictly
  increasing within a run (see run_t_cpmax), which is what lets it double as the
  edge.  0 means none crossed yet this run.
*/
#define STAT_FS_TIMERCP     68   // ordinal just crossed; 0 = none.  Edge-detect it
#define STAT_FS_TIMERCPT    69   // ticks at that crossing
#define STAT_FS_TIMERCPD    70   // that crossing minus the PB's, in ticks (signed)

#define SLOP_NONE    0
#define SLOP_SAVED   1
#define SLOP_LOADED  2
/*
  The retry point was restored after a map restart.  Build 18.

  A separate op from SLOP_LOADED because the client has to treat it differently
  in one respect: it must be honoured even when the sequence counter says this
  is not the first event, since the CSQC VM has just been rebuilt and its
  counter is 0 while the server's is whatever it was.  See Rec_ViewSaveEvents.
*/
#define SLOP_RETRY   3

/*
  The save slot `retry` parks its state in.

  Slot 0 rather than a path of its own, and that is load-bearing rather than
  tidy.  FS_SaveSlotName(0) is "000", so data/saves/<map>/save000/ is spelled by
  the SAME path builders both VMs already use -- which matters because after a
  map restart the client's only route back to its sidecar is Rec_ViewLoaded's
  cold buf_loadfile, and that looks exactly there.  A bespoke retry.view would be
  somewhere it does not look.

  It cannot collide with a real save: SV_SaveLocScan skips any id < 1 when it
  rebuilds the list from disk, and SV_SaveFreeID allocates from 1 upwards.  Two
  explicit numeric bounds, not a glob that happens not to match.
*/
#define FS_RETRY_SLOT 0

#define RT_NONE      0   // no run has ended, or the last one was thrown away
#define RT_PB        1   // ended and kept as this leg's personal best
#define RT_LAST      2   // ended and kept as this leg's most recent run
/*
  A run that was resumed from a save state -- a shadow run.

  It is practice by definition (loading a save is what sets TF_PRACTICE), so
  without a tag of its own it would be written as `_last` and would overwrite the
  most recent ORDINARY run on that leg every time you finished one.  Those are
  two different things worth keeping, so they get two different names.
*/
#define RT_SHADOW    3

/*
  BUILD 45: a run the class machine calls CHEATED -- noclip, setpos or sv_cheats
  seen at any point in the attempt.

  This is the identical defect build 17 fixed for shadow runs, one class further
  down.  A cheated run is practice, so it is never a personal best; it is not
  TF_SHADOW unless a save was ALSO loaded; so build 44 tagged it RT_LAST and it
  overwrote `last.rec`.  Toggling noclip for five seconds destroyed the recording
  of the ordinary attempt before it -- which is precisely the file you would want
  to still have, because the cheated one is worthless and the one it replaced was
  not.

  NOT ARCHIVED, and that is where it parts company with RT_SHADOW.  A shadow run
  is a deliberate practice attempt off a save, worth keeping and worth comparing,
  so it earns a stamped name and accumulates.  A cheated run is worth exactly one
  slot: it is written because it happened, and refusing to write it would be
  pretending it did not -- but there is no version of "keep every cheated run on
  this leg" that anyone wants.  Fixed name, next one replaces it.  FS_TagArchived
  is where that is said in code.

  IT WINS OVER RT_SHADOW when a run is both, matching FS_RunClass's precedence
  exactly.  Not for tidiness: a cheated run tagged shadow would take a STAMPED
  name and accumulate one junk file per lap in the archive that the leaderboard
  reads.  The two orderings differ in what they do to the disk, not just in what
  word they print.
*/
#define RT_CHEAT     4

/*
  BUILD 48: A CLEAN RUN THAT DID NOT BEAT ANYTHING IS STILL A RUN.

  Until now the tag ladder had no word for the ordinary case -- you ran the leg,
  you were clean, you were slower than your best -- so it fell through to
  RT_LAST and overwrote the one before it.  One slot, forty attempts an hour,
  and the archive kept exactly one of them.

  WHAT THAT COST IS THE MEANING OF THE WORD `RANK`.  Only PB-beating runs were
  ever archived, so every stamped file on a leg was faster than every file
  written before it -- a monotone improvement chain, not a distribution.  A
  personal best is therefore rank 1 BY CONSTRUCTION, and a slower run's "rank"
  counts your own past bests rather than a field of attempts.  The number was
  arithmetically correct and told you nothing, and no amount of care on the
  reading side could have fixed that: the data was never collected.

  ARCHIVED, so it takes a stamped name and accumulates.  That is the whole
  point of it and it is the one thing that separates it from RT_LAST.

  IT CANNOT EVICT A PERSONAL BEST.  SV_RecPrune's quota is per LEG per TAG
  CLASS, so this competes only with other RT_RUN files -- the same property
  that already lets RT_SHADOW accumulate beside RT_PB without either crowding
  the other out.  rec_runs_keep bounds it.

  IT WINS OVER NOTHING, and sits at the BOTTOM of the ladder: cheated, shadow
  and personal-best all outrank it, because each of those says something this
  does not.  This is what is left when none of them applies.

  AND IT IS THE ARCHIVE THAT GOES ONLINE.  A leaderboard server cannot verify a
  run it was never sent, and "keep one scratch file per leg" is not a corpus.
  This is the local half of that, built now so the shape is right later.
*/
#define RT_RUN       5

/*
  BUILD 57, STAGE T -- A TIME SET ON A PUBLIC LOBBY, AND THE FIRST TAG THE
  SERVER NEVER WRITES.

  A lobby keeps nothing of its own (Lobby_NoPB / Lobby_NoRec) and could not write
  to this disk anyway, so client/cl_lobbytime.qc writes a header-only .rec here
  the instant the server says a leg was finished or a stage was beaten.

  NO MOVEMENT IN IT, deliberately.  The recorder is off in a lobby, so there is
  nothing to slice -- and a header with `samples 0` is the honest shape of that.
  The leaderboard lists the time and clicking the row SAYS so, rather than
  opening a replay of nothing (cl_scores.qc).

  THE WORD HAS NO UNDERSCORE IN IT, and that is a requirement rather than a
  preference.  Both readers of an archived name split it on the LAST underscore
  -- cl_scores.qc's row scan and cl_results.qc's rank count -- so a word like
  `lobby_pb` would parse as a stamp of "<ticks>_lobby" and a tag of "pb".  And an
  unrecognised tag does not mislabel a row, it DROPS it (see FS_TagFromName), so
  the failure mode is a time that is simply not on the board, with no gap and no
  count to notice it by.

  ARCHIVED, because the name carries a tick stamp -- but what bounds it is not
  rec_runs_keep.  Its writer keeps exactly ONE _lobby.rec per leg, the best one,
  and removes the file it beat: a lobby time has no replay behind it, so a
  distribution of them would be a folder of empty files.
*/
#define RT_LOBBY     6

/*
  THE RECORDING TERMS, build 22.

  What the player has to have read and accepted before FTESurf records anything
  about how they play.  Bumping this number invalidates every existing acceptance
  and puts the terms screen back in front of everyone -- which is the point of
  having a number at all: the text and the version live together in the QC, so a
  change to what is being agreed to cannot slip past an old agreement.

  The record itself is data/consent.txt, written by the menu.  The `rec_terms`
  cvar mirrors the accepted version so the OTHER two VMs can see it without each
  one parsing the file -- and so the capture in client/cl_replay.qc can refuse to
  run for somebody who has never been shown the screen, which is the half of a
  consent gate that actually matters.  A blocked button is not consent; not
  collecting is.

  Deliberately NOT tamper-proof, and the terms say so.  It is a local record that
  a person agreed, not a lock: anyone who can edit consent.txt could equally set
  the cvar or edit the binary.  A consent record's job is to be honest, not
  unforgeable.
*/
#define FS_TERMS_VERSION 1

/*
  PATCH 270 -- THE ONLINE TIER, and why this is a SECOND number rather than
  FS_TERMS_VERSION becoming 2.

  Public lobbies made the version-1 text false in one specific place.  It said,
  verbatim, "Nothing is sent anywhere.  FTESurf has no server to send it to and
  no code that uploads anything."  There is a server now, and joining a lobby
  shares a position with the other people on it.

  BUILD 57 NARROWED THE SECOND HALF OF THAT SENTENCE, which read "and uploads
  times" and was never true -- the same false promise the essay over
  FS_TERMS_ONLINE records at lines 14-15 of the version-1 text.  Stage T keeps a
  lobby time in data/runs on the player's own PC (client/cl_lobbytime.qc) and
  sends nothing, which is why saving lobby times needs no version bump at all.

  The obvious response is to bump FS_TERMS_VERSION to 2, and it is wrong -- not
  because it is inconvenient, but because it would be a false statement about
  the player.  m_draw forces the terms screen whenever the accepted version is
  below FS_TERMS_VERSION and screen_terms has no way off it except accepting or
  quitting.  So bumping it would stop an existing player from launching the
  OFFLINE game they already agreed to, until they agreed to something else.
  Nothing about their offline session changed; every word of version 1 is still
  true for it.  Being re-prompted to keep playing exactly as before, with quit
  as the only alternative, is the shape of a dark pattern even when the text is
  honest.

  So: two tiers.  FS_TERMS_VERSION stays 1 and remains the gate on recording and
  on launching a map.  FS_TERMS_ONLINE is what anything that contacts a server
  requires -- joining a lobby, and polling the lobby directory, which discloses
  an IP address before any lobby is joined and therefore needs consent in its
  own right.  An acceptance always stamps the highest tier, so a new player
  agrees once and a version-1 player is asked exactly when it becomes true of
  them, and can decline and carry on playing.

  Add a tier here rather than bumping when a change affects only some players.
  Bump FS_TERMS_VERSION when the change is to what happens to EVERYONE.

  3, NOT 2, SINCE PATCH 285.  Two things changed in the online text and only one
  of them would have justified a re-ask on its own:

    * lines 14-15 promised that checkpoint and finish times "go to that server
      so runs can be ranked".  No such upload exists or ever existed -- see the
      essay over FS_TERMS_LINES in m_main.qc.  NARROWING a false promise does
      not need a re-ask; nobody agreed to less than they thought.
    * the text now names play.proto.bar as the host the map picker asks which
      lobbies are live.  That IS a disclosure the reader was never shown -- the
      poll has been happening since lobby_dir got a real default -- and naming
      the host somebody's IP goes to is exactly what this tier is for.

  So the bump is for the second one.  It re-asks only players who already
  accepted the online tier; an offline player is untouched, which is the whole
  point of the two-number design above.

  The NEXT bump is already spoken for: whoever wires engine/common/qkupdate.c's
  `update_check` must go to 4 and add dl.proto.bar to the text in that same
  change.  Do not add the line ahead of the code -- that is precisely how
  lines 14-15 came to be false.
*/
#define FS_TERMS_ONLINE 3

#define TS_IDLE      0   // nothing armed
#define TS_ARMED     1   // standing in the zone the run will start from
#define TS_RUNNING   2
#define TS_FINISHED  3   // crossed the end; the time stays up until you re-arm

// STAT_FS_TIMERFLAGS
#define TF_PRACTICE   1  // a save-lock was loaded during this run: it will not be kept
#define TF_RECORDING  2  // a recording is being accumulated
#define TF_HAVEPB     4  // STAT_FS_TIMERPB is meaningful
/*
  This attempt was resumed from a save state.

  Strictly narrower than TF_PRACTICE, which every save-lock load sets: this one
  means the CLOCK and the checkpoints came out of the save too, so the run in
  progress is a continuation rather than a fresh attempt from a free position.
  Cleared by SV_TimerArm with the rest of run_t_flags, because arming is what
  begins a new attempt.  Reaches the HUD through STAT_FS_TIMERFLAGS, which is
  already networked -- no new stat.
*/
#define TF_SHADOW     8
/*
  The run clock is stopped right now -- a save-lock is being held.

  A MIRROR, NOT THE TRUTH.  The request lives in .run_t_freeze, outside run_t_flags,
  and this bit is recomputed from it once per tick by SV_TimerFreezeFrame.  It has
  to be, because SV_TimerArm and SV_TimerIdle both ZERO run_t_flags -- and arming
  is reachable while parked, since the arm test is a point test and a save can sit
  inside a start box.  A flag that arming can clear would leave the clock running
  under a player who is still pinned.  Same argument as run_t_dirty.

  For the same reason it is masked out of a save file: it is a statement about a
  hold that exists now, exactly like TF_RECORDING, and no file can assert it.

  The client needs it because Timer_Display EXTRAPOLATES between snapshots -- and
  without this the readout does not merely fail to freeze, it parks at ticks+6 and
  stays there, because the edge detector only restamps when `ticks` changes.
*/
#define TF_FROZEN    16
/*
  The run clock is stopped because the run ENDED without finishing, and the time
  it stopped at is still on screen.  Build 19.

  Different from TF_FROZEN, which is a clock held under a player who is still in
  a run.  This one says the run is over and what you are reading is an epitaph:
  where you were when you hit `!r`, or touched a cancel zone, or teleported away.
  Before this the readout snapped to 0:00.000 the instant you voided, so the one
  number you wanted -- how far you got -- was the one thing you could not see.

  A MIRROR, for the identical reason TF_FROZEN is one, and the reason bites
  harder here: the void path is SV_TimerVoid -> SV_TimerIdle -> SV_TimerArm, and
  BOTH of those zero run_t_flags.  A bit written by the void would not survive to
  the next frame.  The truth lives in .run_t_stopat and SV_TimerStopFrame
  recomputes this once per tick -- and re-writes run_t_ticks with it, because the
  arm has just zeroed that too.

  Cleared by SV_TimerStart: leaving the start zone is the reset.
*/
#define TF_STOPPED   32

/*
  The camera is detached and the body is coasting.  Build 30.

  A MARKER, NOT A TAINT, and that is a deliberate decision rather than an
  oversight: it does NOT imply TF_PRACTICE and a ghosted run is still a run.
  The argument for that is that ghosting is close to self-policing -- the body
  keeps running physics with no hands on it, so on most maps a ghost of any
  length ends the attempt by itself -- and the argument against is that a long
  ramp will carry a body for a while, which makes ghosting a way to scout ahead.
  This bit is what lets that be decided later, by a leaderboard, without
  re-recording anything.

  WHAT IT IS ACTUALLY FOR is that a ghost window is otherwise INDISTINGUISHABLE
  FROM LETTING GO.  While detached the usercmd carries no movement and no
  buttons and its angles are pinned, so the .rec's `fl` and `keys` columns go
  flat zero and pitch/yaw stop moving -- and reccheck.py's rule is that the key
  mask must agree with the movement columns it is derived from, which zeros do.
  It would have passed silently.  Worse, the .view sidecar keeps recording the
  GHOST CAMERA's angles (Rec_ViewSample reads VF_CL_VIEWANGLES), so for the
  first time the two files disagree about where the player was looking -- which
  is exactly the cross-check hidcheck.py lists as the one it does not do yet.

  So the window is declared in three places rather than inferred anywhere: this
  bit in the .rec header's `flags`, a `ghost` RECORD at each edge in the sample
  stream (same shape as `resume`, and skipped by an older reader for the same
  reason), and the same pair of markers in the .view.
*/
#define TF_GHOST     64

/*
===========================================================================
  WHY THIS RUN IS NOT CLEAN.  Build 44, and it splits one bit into three.

  The report:

    "stitched runs are legit settings but save locked, anything else cheated,
     sv_cheats, noclipped is a cheated run." ... "that needs to be labeled
     'cheated run' not segmented."

  Before this there was one taint and the leaderboard drew one word for it --
  `stitched` -- over noclip, setpos, sv_cheats, a save-lock load and a hopped
  start alike.  Two of those are somebody practising with legal physics and the
  rest are not, and calling them the same thing is what the report is about.

  TF_PRACTICE STAYS AND BECOMES THE UMBRELLA.  Both new bits IMPLY it, and that
  is what makes the change free downstream: SV_TimerFinish and rec_sb_best already
  refuse TF_PRACTICE, so ranking needs no new test anywhere.  Every existing
  reader keeps working and simply gets a coarser answer than the new ones.

  THE RESIDUAL IS HONEST AND MUST NOT BE GUESSED.  A run with TF_PRACTICE and
  neither reason has exactly one live cause -- a hopped start, which is neither
  a cheat nor a stitch -- plus every recording written before this build, where
  a noclip and a save-load are genuinely indistinguishable in the file.  Those
  read `practice`, and a reader that sorted them into one of the other two would
  be inventing a fact about somebody's run.  See FS_RunClass.

  128 AND 256 WERE RESERVED FOR THIS, and the reservation is the reason the
  SF_* block above could name its own 32 and 64 before this build assigned them:
  the two halves of a change that spans a boundary cannot pick different numbers
  if the numbers are written down first.
===========================================================================
*/
/*
  A SAVE STATE WAS USED: legal settings, stitched together.

  The gestures are a save-lock LOAD and a save-lock HOLD, and BOTH ALREADY
  TAINTED -- the load through SV_SaveApplyState and the hold through
  SV_TimerFreeze, which build 18 added with the sentence "a stopped clock is not
  something a kept run may have".  So this bit renames an existing taint rather
  than inventing one, and nothing about which runs are kept changes with it.
  Worth saying plainly because the first cut of this build assumed the hold was
  clean and wrote a paragraph here celebrating a hole it had closed; the hole had
  been closed for twenty-six builds.

  TF_SHADOW implies this.  Not the other way round: a shadow run took its CLOCK
  out of the save as well, which is the narrower claim, and a load taken while
  idle or armed is a stitch that is not a shadow.

  FILES WRITTEN BEFORE BUILD 44 CARRY TF_SHADOW WITHOUT THIS, so FS_RunClass
  reads shadow as segment rather than faulting on the pair -- three files on
  disk are in exactly that state and none of them is wrong.
*/
#define TF_SEGMENT  128
/*
  sv_cheats, noclip, or setpos.

  setpos is classified here rather than as a stitch, and it is the one call in
  this block that could honestly go either way: it is the mod's OWN deliberately
  ungated command and it is reached mid-run for "put me at that ramp", which is
  a practice gesture and not a cheat.  It hands you a position you did not earn,
  which is noclip's whole argument, and noclip is not in doubt.  One line either
  way and this is the line -- said out loud so that changing it later is a
  decision rather than a discovery.

  THE HONEST GAP, and it is written down instead of papered over.  The
  authoritative predicate for "were the physics locked" is the engine's
  SV_MovementLocked() = pm_lockmovement.defaultstr && !sv_cheats, and QC can see
  only half of it.  QC must NOT re-derive the other half from
  cvar("pm_lockmovement"): that reads the LIVE value, and the engine reads
  defaultstr precisely because the live one can be changed by the thing being
  policed.  So this bit means "cheats were off", not "the ruleset was locked".
  The correct fix is a one-line engine patch publishing SV_MovementLocked() as a
  *ruleset serverinfo key; until then the stamp says what it can prove.

  BUILD 62: THAT PATCH EXISTS NOW (engine 313) AND THE OTHER HALF IS TF_NORULESET,
  below -- not this bit.  The gap is closed by a SEPARATE flag rather than by
  widening this one, because the two say different things: this one says the
  player took a position they did not earn, and that one says the server cannot
  prove which physics they took it under.  An install with pm_lockmovement
  unset is misconfigured, not cheating, and TF_CHEAT is the word this game
  prints in red.  Read the sentence above as still true of THIS bit, by design.
*/
#define TF_CHEAT    256

/*
  THE RUN WAS SET WITH THE RAW INPUT JOURNAL SWITCHED OFF.  Build 58.

  IT IS NOT A TAINT CLASS AND IT IS DELIBERATELY OUTSIDE THE RC_* PRECEDENCE
  BELOW.  `rec_hid 0` says nothing whatever about how the run was played -- the
  physics are untouched, no save was loaded, nothing was noclipped -- so folding
  it in beside practice/segment/cheat would put a fault word on an honest run.
  What it is instead is a hole in the EVIDENCE: the one recording that says a
  human moved the mouse in real time was not taken.  TF_GHOST is the precedent
  for a bit that is recorded, is read by the archive, and implies none of the
  three classes.

  WHY THE SERVER RECORDS IT AT ALL, when `.view` already carries a `hid` key.
  The `.view` is written by the CLIENT -- the same party that turned the journal
  off -- so today the only record of the switch is in a file kept by the person
  the switch is there to audit.  This bit puts the claim in the SERVER's own
  file, where it can be compared against whether a `.hid` ever arrives.

  AND HERE IS WHAT IT IS NOT, said out loud so nobody builds an accusation on
  it: the server learns this from a userinfo key the client sets, so a client
  that lies sets `1` and records nothing.  This is a gate against the console
  opt-out that `m_main.qc:509` currently advertises to players, NOT attestation.
  Its value is that the lie becomes PROVABLE the moment the backend asks for the
  file it claims exists -- which is Phase 2's upload-on-PB, not this build.

  THE ABSENT KEY IS "UNKNOWN" AND MUST NEVER BE READ AS "NO JOURNAL".  Only a
  literal "0" sets this bit.  A client that has not sent the key yet, or is an
  older build, or reconnected a frame ago, is not making a claim -- and marking
  such a run would be a false statement about a player on that player's own
  screen, which is the one failure this whole feature may not have.  A quiet
  gate survives a false negative; an accusation does not.
*/
#define TF_NOJOURNAL 512

/*
  THE RUN'S PHYSICS WERE NOT PROVABLY THE RULESET'S.  Build 62, engine Patch 313.

  WHAT THIS FIXES IS THE GAP THE TF_CHEAT COMMENT ABOVE ADMITS TO.  That comment
  says QC can see only half of SV_MovementLocked() and that "the correct fix is a
  one-line engine patch publishing it as a *ruleset serverinfo key".  Patch 313
  is that patch, and it publishes four fields rather than one:

      *ruleset "<locked> <off> <seq> <breach>"

    locked  SV_MovementLocked() = pm_lockmovement.defaultstr && !sv_cheats.
            BOTH halves, assembled inside the engine where defaultstr is
            readable.  QC still may not derive it here: cvar("pm_lockmovement")
            is the LIVE value, which is exactly what the lock exists to police.
    off     how many cvars in the locked movement table currently differ from
            the canonical value for this map -- which is the gamemode or per-map
            override where one applies, NOT defaultstr.  0 while locked.
    seq     every off-canonical set of a table cvar since the server came up,
            counted whether or not the lock was engaged, never reset.
    breach  the subset of those that STOOD, i.e. that happened while the lock
            was off so nothing reverted them.  THIS is the one a taint may read.

  IT IS NOT A TAINT CLASS, and TF_NOJOURNAL is the precedent rather than
  TF_CHEAT.  An unlocked ruleset is a hole in the CERTIFICATION -- the server
  cannot prove what physics the run was played under -- and not something the
  player did.  Folding it into SV_CheatsOn() would print `cheated`, in red, at a
  player whose install was merely misconfigured, or who joined a community server
  that never set pm_lockmovement.  The same rule as the bit above: a quiet gate
  survives a false negative; an accusation does not.  So it is recorded, it is
  read by the archive, it implies none of the three classes, and the board simply
  declines to rank it.

  WHY IT READS A COUNTER AND NOT ONLY off, which is the whole reason the engine
  publishes four numbers.  `off` is a snapshot, and a snapshot cannot mark a
  span: sv_cheats 1, move sv_airaccelerate, sv_cheats 0 restores it, and a run
  spanning that window reads off == 0 at BOTH ends while its physics were not the
  ruleset's in the middle.  Measured on the shipped binary as exactly that --
  "0 0 1 0" then "0 1 2 1" then "1 0 2 1".  So the start latches and the finish
  compares, the same shape SV_TimerJournal uses for a mid-run rec_hid 0.

  AND WHY IT LATCHES breach RATHER THAN seq.  seq counts ATTEMPTS; under the lock
  the engine reverts inside the same Cvar_Set, so no physics tick ever sees the
  value and the run's physics really were the ruleset's.  Differencing seq would
  therefore set this bit -- whose meaning is "not provably the ruleset's" -- on a
  run where they provably were, because somebody mistyped a cvar name into the
  console.  That is the Patch 305 failure mode one layer up, and it is the reason
  the engine publishes the two counts separately instead of one.

  THE COUNTER IS NOT REDUNDANT WITH SV_NoclipWatch's sv_cheats watch, which was
  the first thing to check before adding a second mechanism for one gesture.
  That watch is an EDGE -- sv_player.qc:472, `if (sc) if (!e.run_lastcheats)` --
  sampled once per PlayerPostThink, so a toggle that goes 1 and back to 0 between
  two of them sets no TF_CHEAT, and every snapshot of this key still reads
  locked 1 / off 0 either side of it.  breach is the only thing that sees it.

  THE ABSENT KEY IS "UNKNOWN" AND MUST NEVER BE READ AS "UNLOCKED", for the
  identical reason spelled out for TF_NOJOURNAL one block up.  serverkey returns
  "" on any engine older than Patch 313, and "" is not a claim that the ruleset
  was open -- it is an engine that cannot answer the question.  Marking those
  runs would stamp a false statement on every run this game has ever recorded.
*/
#define TF_NORULESET 1024

/*
  THE PRECEDENCE, IN ONE PLACE, because three readers ask it.

  cl_scores.qc's row word, cl_watch.qc's replay panel and cl_timer.qc's
  sub-label all have to agree about a run that BOTH noclipped and loaded a save
  -- it carries both bits -- and a reader that tested segment first would put
  the gentler word on the worse run.  Cheat outranks segment outranks practice,
  and it is spelled once here for the same reason FS_TagName is: the server had
  one copy and the client had another, each with a comment saying the other
  existed and had to match.

  UNKNOWN is never returned by this function -- a flags word always answers.  It
  exists because a v3 file has no `flags` key at all, and the board's rule is
  that a file which cannot answer must be shown under every filter rather than
  guessed into one.  The caller that has no word supplies it.
*/
#define RC_CLEAN     0
#define RC_PRACTICE  1
#define RC_SEGMENT   2
#define RC_CHEAT     3
#define RC_UNKNOWN   4

float(float flags) FS_RunClass =
{
	if (flags & TF_CHEAT)    return RC_CHEAT;
	if (flags & TF_SEGMENT)  return RC_SEGMENT;
	// Pre-build-44 files, and the implication in the one direction it holds.
	if (flags & TF_SHADOW)   return RC_SEGMENT;
	if (flags & TF_PRACTICE) return RC_PRACTICE;
	return RC_CLEAN;
};

/*
  ...and the word, which is what the report actually asked to change.

  "segmented" is 9 characters and SBW_KIND is 9, so the leaderboard's column
  width is unchanged by this build.  IT HAS NO SLACK LEFT: the next word added
  here does not fit and the column has to grow with it.
*/
string(float c) FS_RunClassName =
{
	if (c == RC_CLEAN)    return "clean";
	if (c == RC_PRACTICE) return "practice";
	if (c == RC_SEGMENT)  return "segmented";
	if (c == RC_CHEAT)    return "cheated";
	return "--";
};

/*
  THE INPUT MASK, written into every v3 sample and every sidecar frame.

  Two writers, and they do not see the same thing -- which is the point of
  having both rather than one.

  The SERVER writes it from .movement and the button fields, so its bits are
  what the usercmd actually CARRIED.  That is the truth for physics: if
  run_prestrafe dropped +forward for a pre-strafe jump, the server's FWD bit is
  clear, because no forwardmove was sent.

  The CLIENT writes it from the keyboard (cl_keys.qc), so its bits are what your
  HANDS were doing.  That is the truth for the key display, and it is strictly
  larger: +left and +right have no usercmd button bit at all (cl_input.c:1368
  feeds them to CL_AdjustAngles directly), so the server cannot record them at
  any sample rate, and the prestrafe release only exists as a difference between
  the two masks.

  Playing the two against each other is what reproduces HUD_DrawKeys exactly:
  a key set on the client and clear on the server is KEY_RELEASED, and DUCKED
  in the sample flags with no client DUCK bit is KEY_FORCED.

  BIT ORDER IS FSK ORDER.  FSI_<x> is exactly 1 << FSK_<x> (cl_keys.qc), which
  is why the client side is a four-line loop over its own key table rather than
  eight hand-written ORs that could drift out of step with it.  Keep them
  aligned if either list grows.
*/
#define FSI_FWD        1    // FSK_FWD
#define FSI_BACK       2    // FSK_BACK
#define FSI_LEFT       4    // FSK_LEFT   -- +moveleft
#define FSI_RIGHT      8    // FSK_RIGHT  -- +moveright
#define FSI_JUMP      16    // FSK_JUMP
#define FSI_DUCK      32    // FSK_DUCK
#define FSI_TLEFT     64    // FSK_TLEFT  -- +left,  client only, see above
#define FSI_TRIGHT   128    // FSK_TRIGHT -- +right, client only, see above

// Past the key table, so these stay free as it grows.
#define FSI_ATTACK   256
#define FSI_PSREL    512    // client only: run_prestrafe is suppressing +forward

/*
  Save-locks.

  The list is server-side (it has to move the player, and the duck state it
  restores is engine-owned -- see run_forceduck), so the menu is a pure view
  over two stats and every key sends a command.

  BUILD 25: 32 -> 999, requested as "unlimited".  Unlimited is not a thing QC can
  offer -- every one of these is a fixed global array -- so this is the largest
  number the rest of the design already supports, and the three things that
  decide it all move together:

    the folder name    data/saves/<map>/save007/, three digits (below)
    the directory scan reads exactly that many characters back out
    STAT_FS_SLOP       packs op * FS_SLOP_RADIX + id into one float

  Ten arrays of 999 -- two of them vectors -- is about 14k floats, 56 KB, which
  is a fifth of what one .rec buffer costs during a run.
*/
#define FS_MAXSAVES  999

/*
  THE SLOT'S FOLDER NAME, AND IT HAS ONE SPELLER FOR A REASON.

  A save state is three files written by two different VMs -- state.txt and
  run.rec by the server, run.view and seq.txt by the client -- joined by nothing
  whatever except landing in the same directory.  Until build 25 that directory
  name was spelled THREE times: SL_NN in sv_saveloc.qc, and an inline copy in
  each of Seq_Path (cl_board.qc) and Rec_SavePath (cl_replay.qc).  Widening the
  id from two digits to three means all three have to change in the same commit,
  and if one is missed the failure is silent -- the server writes save007 and the
  client writes save07, a load restores the position and the clock and then finds
  no camera and no segment list, which looks like the replay half being broken
  rather than like a path bug.

  Build 23 moved FS_RunPath here after exactly that class of bug and build 24
  moved FS_IsSample and Zone_TrackSegs after two more.  This is the same move.

  Fixed width, because SL_NAMESORT has to order the folders the way a human
  reading `dir` would -- a listing that sorts save10 before save2 looks like a
  bug every time you see it -- and because the scanner reads the id back out by
  offset rather than by parsing to a delimiter.

  Not sprintf's own width flags: this codebase has never relied on them and the
  three-branch form is obvious at the call site.
*/
string(float id) FS_SaveSlotName =
{
	if (id < 10)  return sprintf("00%g", id);
	if (id < 100) return sprintf("0%g", id);
	return sprintf("%g", id);
};

// The width FS_SaveSlotName always returns, which the directory scan needs in
// order to read an id back out of a filename.  Stated once, beside the writer.
#define FS_SAVENAMELEN 3

/*
===========================================================================
  WHERE RECORDINGS LIVE.  Build 23.

      data/runs/<map>/main/0004108_pb.rec
      data/runs/<map>/main/0004108_pb.view
      data/runs/<map>/main/0004108_pb.hid
      data/runs/<map>/main/last.rec
      data/runs/<map>/stage_3/0000512_pb.rec
      data/runs/<map>/bonus_1/0001204_shadow.rec
      data/runs/<map>/best.pb

  It replaces data/runs/<map>_t0_s0_pb.rec, which put every recording for every
  map in one flat directory and kept exactly three per leg, because the tag was
  the whole name and a new run overwrote the old one.

  THE TIME IS IN THE NAME, AND THAT IS THE FEATURE.  Zero-padded to seven digits
  so a plain ascending filename sort IS the leaderboard -- fastest first, no
  index file, no parsing, and SB_NAMESORT (which search_begin already offers) is
  the whole of the sort.  Seven digits is 9,999,999 ticks, about 41 hours at
  66.67 Hz.  It also means a new run no longer overwrites the old one, so a leg
  accumulates a real archive rather than a single best.

  WHY THIS FILE.  All three VMs compile sh_defs.qc, and until now the server
  (SV_RecFinalPath) and the client (Rec_ViewPath) each spelled this convention
  out separately, with a comment in each begging the other to be kept in step.
  Two spellers of one name is a bug waiting for someone to edit one of them; the
  .rec and .view of a run are joined by nothing whatever except being named the
  same, so a drift orphans both halves and neither writer errors.

  `last` is DELIBERATELY unstamped.  pb and shadow are archive classes and a new
  one must not overwrite an older one; `last` is a scratch slot meaning "the
  attempt I just did", and stamping it would write a file per attempt -- forty an
  hour, megabytes each, for runs nobody will ever open.

  BUILD 45 gave it a second scratch slot, `cheat`, for the same reason it has one
  at all: a cheated run WAS a `last`, and so a noclip overwrote the ordinary
  attempt before it.  Two unstamped names now, and both sort after every stamped
  one because 'c' and 'l' are both above '9' -- so the leaderboard's name-sort
  still puts the ranked archive first and the scratch slots at the bottom, with
  `cheat` above `last`.  Nothing in the sort had to learn anything.
===========================================================================
*/

/*
===========================================================================
  BUILD 57 -- THE LEG IS NOT THE SEGMENT, AND THIS IS THE ONE PLACE THAT SAYS
  WHICH IS WHICH.

  A SEGMENT is the zone parser's 0-based index: stage 1 begins at segment 0 (the
  map's START), stage k at segment k-1, and the END zone carries the count.
  A LEG is a thing with its own folder, its own personal best and its own
  leaderboard: 0 is the full run of a track and k is stage k.

  Until build 57 there was only the segment, and it was used as the leg -- 0
  meant "full run" and N meant "a run that began at segment N", spelled stage_N.
  That is one stage late on every staged map, and it gave stage 1 no leg at all,
  because stage 1's segment is 0 and 0 was already the whole track.  So `!s 1`
  armed the map, the stage-1 lift was refused, and every scoreboard was one
  stage short with every stage row misnamed.

  A leg cannot be recovered from the segment alone -- a full run and a stage-1
  run both begin at segment 0 -- so the server carries the missing bit
  (sv_timer.qc: run_t_stagerun) and every caller on either side of the wire
  asks this function rather than doing the arithmetic:

      a live run         FS_LegOf(run_t_startseg, run_t_stagerun)
      a lifted stage     FS_LegOf(seg, TRUE)          -- always a stage leg
      an old .rec/save   FS_LegOf(startseg, startseg > 0)
                         which is not a guess: before build 57 nothing could
                         run stage 1 alone, so startseg > 0 WAS "a stage run".

  Callers must not pass a negative segment; -1 is "no stage open" and it has no
  leg, which this function would otherwise answer as `main`.
===========================================================================
*/
float(float startseg, float stagerun) FS_LegOf =
{
	if (stagerun)
		return startseg + 1;
	return 0;
};

/*
  The leg's folder name.  track 0 is the main track and tracks 1+ are bonuses
  (sh_zones.qc: zone_track); leg 0 is a full run of that track and leg k is
  stage k -- see FS_LegOf just above for how a leg is derived.

  BUILD 57: A LEG, NOT A SEGMENT, and the body did not change -- the number
  handed to it did.  stage_k is now stage k.  Folders written before build 57
  hold stage k+1 under stage_k; tools/migrate_runs.py legs1 renames them.

  Words rather than t0_s0, because these are directories a player opens.
*/
string(float track, float leg) FS_LegDir =
{
	if (track <= 0)
	{
		if (leg <= 0)
			return "main";
		return sprintf("stage_%g", leg);
	}
	if (leg <= 0)
		return sprintf("bonus_%g", track);

	// A stage of a bonus track.  Rare, but the zone format allows it and a
	// collision here would silently file two different legs together.
	return sprintf("bonus_%g_stage_%g", track, leg);
};

/*
  Ticks, zero-padded to seven.  Built with a loop rather than a %07g, because
  fteqcc's sprintf implements a subset of printf and a width-with-zero-flag on a
  float is not a thing worth betting a filename on.
*/
string(float ticks) FS_RunStamp =
{
	local string s;

	if (ticks < 0)
		ticks = 0;

	s = ftos(floor(ticks));
	while (strlen(s) < 7)
		s = strcat("0", s);
	return s;
};

// The directory for one leg, trailing slash included.  fopen/COM_WriteFile call
// FS_CreatePath, so nothing has to create these.  BUILD 57: `leg` is a LEG (0
// the full run, k stage k) and never a segment -- see FS_LegOf.
string(string map, float track, float leg) FS_RunDir =
{
	return sprintf("data/runs/%s/%s/", map, FS_LegDir(track, leg));
};

/*
  The full path of one recording.  `tag` is SV_RecTagName's word and `ext` is
  rec, view or hid.  `leg` as FS_RunDir takes it.

  An empty stamp is how `last` gets its fixed name: the caller passes ticks < 0
  to mean "not archived".
*/
string(string map, float track, float leg, float ticks,
       string tag, string ext) FS_RunPath =
{
	if (ticks < 0)
		return sprintf("%s%s.%s", FS_RunDir(map, track, leg), tag, ext);

	return sprintf("%s%s_%s.%s", FS_RunDir(map, track, leg),
	               FS_RunStamp(ticks), tag, ext);
};

/*
  The per-map record file.

  A FIXED basename inside the map's own folder rather than <map>.pb, so the
  menu's census can scan "data/runs/" + star + "/best.pb" -- ONE wildcard, in a
  middle component, which is the exact pattern SV_SaveLocScan has been running
  since build 17 and is therefore known to work in FTE's enumerator.  A pattern
  with two wildcards would be a guess about Sys_EnumerateFiles2's recursion that
  nothing on this disk currently proves.
*/
#define FS_RUNS_ROOT  "data/runs/"
#define FS_PB_LEAF    "/best.pb"

/*
  BUILD 57, STAGE T -- THE SECOND .pb IN THE SAME FOLDER, AND WHY IT IS A SECOND
  FILE RATHER THAN MORE KEYS IN THE FIRST.

  best.pb is what a run on THIS PC wrote (SV_PBSave, which rewrites it whole from
  a table with no player dimension).  lobby.pb beside it is what the client wrote
  when a run on a public lobby beat the player's own lobby best -- two different
  claims about the same leg, which the map list shows side by side and marks.

  Keeping them apart is what makes each writer safe.  SV_PBSave would otherwise
  have to preserve keys it knows nothing about on every write, in a lobby where
  it is refused outright; and the client would have to rewrite a file the server
  owns, on a disk where the server is also running.  One writer per file, same
  grammar, same fixed-leaf-in-a-wildcard-component shape as best.pb.

  `best <track> <leg> <ticks>`, FTESURF-PB 2 -- always 2: there was never a
  version-1 lobby.pb, so nothing here needs the segment-to-leg shift SV_PBLoad
  does for an old best.pb.  The menu's map list reads both files through the same
  parser (m_main.qc: run_pb_scan), which takes this name as an argument the same
  way it takes FS_PB_LEAF -- one speller, here.
*/
#define FS_LOBBYPB_LEAF  "/lobby.pb"

/*
  search_begin's SB_NAMESORT flag.  Named here because it is load-bearing for
  the layout above and not merely convenient: the archive has no index file, and
  an ascending name sort over zero-padded tick counts IS the leaderboard.

  sv_saveloc.qc calls the same flag SL_NAMESORT, which predates this and is left
  alone; both are 32 and both mean the same thing to the engine.
*/
#define FS_NAMESORT   32

string(string map) FS_PBPath = { return sprintf("%s%s%s", FS_RUNS_ROOT, map, FS_PB_LEAF); };

/*
  RT_* to the word that goes in the filename.

  Also moved here in build 23, and for the same reason as the path: the server
  had SV_RecTagName and the client had Rec_TagName, each carrying a comment
  saying the other one existed and had to agree with it character for character.
  They are one fact and they now have one definition.

  ARCHIVED says whether a tag's files carry a time and accumulate, or take a
  fixed name and overwrite.  It is asked in three places -- the writer, the
  pruner and the reader -- so it is answered once, here, beside the names it is
  about.
*/
string(float tag) FS_TagName =
{
	if (tag == RT_PB)     return "pb";
	if (tag == RT_SHADOW) return "shadow";
	if (tag == RT_CHEAT)  return "cheat";
	if (tag == RT_RUN)    return "run";     // build 48
	// Build 57, stage T.  No underscore -- see the block over RT_LOBBY, where
	// that is a requirement of the two readers rather than a style choice.
	if (tag == RT_LOBBY)  return "lobby";
	return "last";
};

/*
  THE INVERSE: a tag WORD back to its RT_*, or RT_NONE when the word is not one
  this game writes.

  Added in build 45, and the reason is the shape of the bug it prevents.  The
  forward map lived in one place; the reverse map lived in TWO -- cl_scores.qc's
  directory scan and cl_watch.qc's `replay <tag>` -- and adding a fourth tag to
  one of them and not the other would have left both compiling and running.  The
  scoreboard has the sharper failure: it skips any file whose word will not map,
  so a tag it does not recognise does not mislabel the row, it DROPS it.  A run the
  user was told is "written, labelled, never ranked" would simply not be on the
  list, with no gap and no count to notice it by.

  RT_NONE is the "no" answer and cannot collide with a real one -- it means "no
  run has ended, or the last one was thrown away", and nothing is ever named
  after it, so FS_TagName never returns a word that maps back to it.
*/
float(string w) FS_TagFromName =
{
	if (w == "pb")     return RT_PB;
	if (w == "shadow") return RT_SHADOW;
	if (w == "cheat")  return RT_CHEAT;
	if (w == "last")   return RT_LAST;
	// Build 48.  Taught to the READER in the same edit that named it, which is
	// the whole reason this function exists -- the paragraph above is about a
	// fourth tag that reached the writer and not the scan, and this is the fifth.
	if (w == "run")    return RT_RUN;
	// Build 57, stage T, and the sixth one makes the paragraph above literal: the
	// tag is written by the CLIENT and read by the client's own scoreboard and
	// rank count, so a word taught to the writer and not to this function would
	// drop every lobby time off the board it was written for.
	if (w == "lobby")  return RT_LOBBY;
	return RT_NONE;
};

/*
  IS THIS .rec LINE A SAMPLE OR A RECORD?

  A sample begins with its own timestamp, so with a digit or with a minus; every
  record type begins with its keyword.  That is the .rec grammar's one structural
  rule, and it is stated here because THREE things now depend on it: the reader's
  load scan, the reader's cursor walk, and -- as of build 24 -- the server's own
  stage slicer, which has to know which lines carry a `t` it must rebase.

  Testing the first character rather than tokenizing is what makes it affordable
  at that scale: the load scan looks at every line in a six-thousand-line file
  and tokenizing all of them to find the dozen that are records would be most of
  the load time for none of the information.
*/
float(string s) FS_IsSample =
{
	local float c;

	c = str2chr(s, 0);
	if (c == 45)                    // '-', the pre-start padding's negative t
		return TRUE;
	if (c >= 48)
	if (c <= 57)                    // '0'..'9'
		return TRUE;
	return FALSE;
};

float(float tag) FS_TagArchived =
{
	if (tag == RT_PB)     return TRUE;
	if (tag == RT_SHADOW) return TRUE;
	/*
	  BUILD 48, and this is the argument the comment below asks a new tag to make.

	  RT_RUN accumulates because ACCUMULATING IS THE ENTIRE FEATURE.  It exists to
	  turn a leg directory from a chain of personal bests into a distribution of
	  attempts, and a fixed overwritten name would leave it exactly the RT_LAST it
	  was carved out of -- the same one slot, renamed.

	  What bounds it is SV_RecPrune's quota, which is per leg PER TAG CLASS, so
	  this crowds out only other RT_RUN files and can never evict a personal best.
	  That is the same property that already lets RT_SHADOW accumulate beside
	  RT_PB, and it is why "archived" is safe to grant here and was not for
	  RT_CHEAT -- there is no version of "keep every cheated run" anyone wants,
	  and there is an obvious one of "keep my last twenty-five clean attempts".
	*/
	if (tag == RT_RUN)    return TRUE;
	/*
	  BUILD 57, STAGE T, and it makes the argument this comment asks for.

	  RT_LOBBY's name carries a tick stamp because the BOARD is a name sort: an
	  unstamped lobby.rec would sort under the scratch slots and carry no time at
	  all, which is the one thing the row is for.  What it does NOT get from being
	  archived is accumulation -- its writer keeps one file per leg and removes
	  the one it beat, so "archived" here means stamped, and the quota that bounds
	  the other three is not what bounds this.
	*/
	if (tag == RT_LOBBY)  return TRUE;
	// RT_LAST and RT_CHEAT both fall through: one fixed name each, overwritten
	// every time.  Written as the fall-through rather than as two more tests
	// because the question is "does this class accumulate on disk", and a tag
	// added later should have to argue its way to TRUE rather than inherit it.
	return FALSE;
};

/*
===========================================================================
  BUILD 46 -- THE fs_ MOVE, AND THE ONE THING THAT KEEPS IT FROM COSTING
  SOMEBODY THEIR CONFIG.

  Every cvar this mod owns used to sit in the ENGINE's filesystem namespace.
  fs_game, fs_basepath, fs_automount, fs_cache and fs_restart are the
  filesystem's; fs_stagehop and fs_runclass were ours; and nothing in either
  name said which.  That is not a cosmetic complaint -- sv_player.qc's essay
  records the day it cost a bound key, because `bind x fs_restart` reached the
  ENGINE's filesystem-rebuild command every time and the mod's own command of
  the same name was unreachable by the obvious route.  So the names moved to
  say what they DO:

    run_    the timer and the ruleset -- what makes a run legal, how it is
            measured, the stage rules, the movement assists
    rec_    recording and playing back: the recorder, replays, ghosts, the
            save-lock, the leaderboard
    vbsp_   drawing and running Source map content -- props, sprites, decals,
            overlays, portals, entity I/O, teleports, water
    ui_     the HUD, the menu, fonts, the strafe board instrument

  fs_missingwarn stayed, alone, because it really is about the filesystem --
  which is the point of the exercise rather than an exception to it.  After
  this, `fs_` in this tree means the engine's filesystem and nothing else.

  WHY THIS FUNCTION EXISTS.  A renamed cvar does not fail loudly.  A config
  that sets the old name sets a cvar nobody reads, which is the "control that
  never ran" trap the testrun notes are full of -- the run comes out on the
  default path while claiming to be the arm you asked for.  default.cfg and the
  145 testrun cfgs were rewritten alongside the source, so those are safe; what
  is NOT safe is the player's own saved ftesurf.cfg, their binds, and weeks of
  muscle memory.  So each old name forwards its value once and says where it
  went.

  IT IS DELIBERATELY SILENT WHEN THERE IS NOTHING TO SAY.  A cvar that was
  never set reads "" and the pair is skipped; a pair whose two sides already
  agree is skipped too, so a config carrying the DEFAULT under the old name
  costs no line of console noise.  Only a value that would otherwise have been
  lost prints anything.  That also makes this idempotent, which is why both
  callers can run it without the second repeating the first.

  CVARS ARE ENGINE-GLOBAL, NOT PER-VM, which is why one list serves all three
  progs and why it does not matter that the menu registers four of these names
  and the server eleven.  cvar_set on a name the owning VM has not registered
  yet creates it with this value, and registercvar then declines to overwrite
  it -- the same FTE behaviour that makes a pre-map `hud_*` set a silent no-op
  is what makes the forward survive here.

  DELETE THIS WHOLE BLOCK ONCE THE OLD NAMES ARE OUT OF LIVING MEMORY.  It is a
  migration, not an interface, and leaving it forever would quietly make the
  old namespace half-supported -- which is the state it was moved out of.
===========================================================================
*/
void(string oldn, string newn) FS_CvarMoved =
{
	local string v;

	v = cvar_string(oldn);
	if (v == "")
		return;
	if (v == cvar_string(newn))
		return;

	cvar_set(newn, v);
	print(sprintf("^3%s is now %s^7 (carried your %s over)\n", oldn, newn, v));

	/*
	  AND THE OLD NAME IS EMPTIED, so this says its piece exactly once in the
	  life of the install rather than on every launch.  The empty string is the
	  "never set" case the guard at the top already returns on, and it is the
	  only value available -- QC cannot unregister a cvar, and the read above
	  has by now caused the engine to create it if a config mentioned it.

	  It also stops cfg_save writing the old name back out with a real value
	  and quietly resurrecting a second source of truth for the same setting,
	  which is the failure this whole function exists to prevent one build
	  earlier in its life.
	*/
	cvar_set(oldn, "");
};

void() FS_CvarsMoved =
{
	// The ruleset.
	FS_CvarMoved("fs_starthop",         "run_starthop");
	FS_CvarMoved("fs_starthop_strict",  "run_starthop_strict");
	FS_CvarMoved("fs_rearmstops",       "run_rearmstops");
	FS_CvarMoved("fs_rearmhop",         "run_rearmhop");
	FS_CvarMoved("fs_zone_swept",       "run_zone_swept");
	FS_CvarMoved("fs_teleport_warp",    "run_teleport_warp");
	FS_CvarMoved("fs_stagefail",        "run_stagefail");
	FS_CvarMoved("fs_stagearm",         "run_stagearm");
	FS_CvarMoved("fs_stageclean",       "run_stageclean");
	FS_CvarMoved("fs_stagehop",         "run_stagehop");
	FS_CvarMoved("fs_runclass",         "run_class");
	FS_CvarMoved("fs_cheatwatch",       "run_cheatwatch");
	FS_CvarMoved("fs_prestrafe",        "run_prestrafe");
	FS_CvarMoved("fs_prestrafe_time",   "run_prestrafe_time");
	FS_CvarMoved("fs_bv_debug",         "run_bv_debug");

	// Recording, replay, the save-lock, the board.
	FS_CvarMoved("fs_record",           "rec_enable");
	FS_CvarMoved("fs_hid",              "rec_hid");
	FS_CvarMoved("fs_runs_keep",        "rec_runs_keep");
	FS_CvarMoved("fs_terms",            "rec_terms");
	FS_CvarMoved("fs_watch_pvs",        "rec_watch_pvs");
	FS_CvarMoved("fs_savelock",         "rec_savelock");
	FS_CvarMoved("fs_retry",            "rec_retry");
	FS_CvarMoved("fs_retry_armed",      "rec_retry_armed");

	// Source map content.
	FS_CvarMoved("fs_decals",           "vbsp_decals");
	FS_CvarMoved("fs_decal_size",       "vbsp_decal_size");
	FS_CvarMoved("fs_overlays",         "vbsp_overlays");
	FS_CvarMoved("fs_overlay_depth",    "vbsp_overlay_depth");
	FS_CvarMoved("fs_overlay_shear",    "vbsp_overlay_shear");
	FS_CvarMoved("fs_sprites",          "vbsp_sprites");
	FS_CvarMoved("fs_sprite_dist",      "vbsp_sprite_dist");
	FS_CvarMoved("fs_sprite_debug",     "vbsp_sprite_debug");
	FS_CvarMoved("fs_spotlights",       "vbsp_spotlights");
	FS_CvarMoved("fs_skyroom",          "vbsp_skyroom");
	FS_CvarMoved("fs_portal_render",    "vbsp_portal_render");
	FS_CvarMoved("fs_portal_dist",      "vbsp_portal_dist");
	FS_CvarMoved("fs_portal_debug",     "vbsp_portal_debug");
	FS_CvarMoved("fs_entity_io",        "vbsp_entity_io");

	// The menu and the launch self-check.
	FS_CvarMoved("fs_bootcheck",        "ui_bootcheck");
	FS_CvarMoved("fs_bootmap",          "ui_bootmap");
	FS_CvarMoved("fs_bootangles",       "ui_bootangles");
	FS_CvarMoved("fs_maps_assetmounts", "ui_maps_assetmounts");
};
