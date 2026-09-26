/*
===========================================================================
  cl_watch.qc -- reading a recording back.  Build 24.

  cl_replay.qc has said "PLAYBACK IS NOT HERE YET" since build 9.  This is it.

  WHAT IS BEING READ, AND WHY IT TAKES TWO FILES.

  The .rec is one sample per physics tick: position, velocity, the usercmd and
  four state bits, at 66.67 Hz, which is the rate the physics actually ran at
  and is provably enough for position -- the engine's own prediction renders an
  intermediate frame as a pure LERP of the two bracketing ticks, so a finer
  position sample would carry no information.

  The .view is one line per RENDERED frame: the view angles and the keyboard.
  Those are the two things the tick rate genuinely loses.  Between two ticks the
  camera really did sweep through angles no tick holds, and +left / +right have
  no usercmd bit at any sample rate -- they feed CL_AdjustAngles directly -- so
  no server-side recording could ever have got them back.  They are on disk only
  because the client wrote them down.

  So: POSITION comes from the .rec, ANGLES AND KEYS come from the .view, and the
  two are joined by the run clock, which is the only clock both files share.

  THE PLAYBACK CLOCK IS THE .rec's `t` COLUMN, IN SECONDS, AND IT MAY BE
  NEGATIVE.

  That choice is worth stating because the obvious alternative is wrong in a way
  that only shows up on some files.  The .view carries cltime, which is REAL
  time, and driving playback from it would be exact -- until a run that was
  paused on a save-lock hold, where cltime keeps advancing and the run clock does
  not.  A ten-second park would play as ten seconds of nothing.

  `t` has no such hole.  The recorder freezes with the clock (build 18: "rec
  lines held at 679 across the hold"), so a hold costs the file no samples at all
  and the run clock is continuous across it by construction.  reccheck.py has
  refused a non-monotone run clock since build 18, which makes that an invariant
  a reader may rely on rather than a hope.

  Negative t is the PADDING -- the 256-sample ring of approach the server keeps
  before the clock starts.  Your surf_aesthetic run opens at t = -3.8397.  The
  .view has no coverage there at all (the sidecar opens on the TF_RECORDING edge,
  and the pre-start ring is server-side only), so the approach is played with the
  first recorded angle held.  It is the run walking up to the start box, and it
  is worth seeing.

  THE THREE PANELS BUILD 23 REFUSED TO DRAW, AND WHAT CHANGED.

  The strafe bar, the board panel and the segment column are decided by
  STAT_FS_RAMPCONTACT and the PRE-CLIP STAT_FS_BOARDVEL, and .rec v3 carried
  neither -- its flags column had onground, ducked, jump and attack and that was
  all.  Build 23 drew none of the three and said so on screen, because deriving a
  ramp contact from the ground flag would have produced a bar indistinguishable
  from a measured one.

  The fix was not to derive them.  .rec v4 RECORDS them: one flags bit for the
  ramp contact, one plane per sample, and a `board` record carrying the latched
  arrival plane and the pre-clip velocity on the tick the engine's counter moved.
  All three panels now replay from measurement.

  A v3 file still refuses, and still says so.  Every recording on disk before
  this build is v3, including the surf_aesthetic run that proved the reader, so
  this is not a hypothetical branch -- it is the one you will see first.

  THE SEGMENT COLUMN IS BUILT ONCE, AT LOAD, AND NOT PER FRAME.  Board_Frame is
  an accumulator and a scrub runs the clock backwards; re-running it from t0 on
  every frame of a drag would be six thousand iterations per frame.  Watch_BuildSeq
  runs the REAL Board_Frame -- not a second copy of it, which is the thing that
  rots -- over the sample stream once, captures every row it pushes with the tick
  it was pushed at, and restores the live list afterwards.  A seek then becomes
  what Watch_Splits already is: a count into a table.
===========================================================================
*/

/*
  Declared here rather than in the cl_keys.qc override block because nothing
  before this file needs them -- only cl_main.qc does, and it compiles after.
  The block in cl_keys.qc holds exactly the ones the HUD and the timer read,
  and keeping it to those is what makes it obvious what a replay overrides.
*/
float  rec_wt_open;              // a recording is loaded (drawing or paused)
float  rec_wt_tag;               // RT_*, from the filename
float  rec_wt_pitch;
float  rec_wt_yaw;
float  rec_wt_evfin;             // the finish row is in the split list

/*
  The two buffers.  0 is the no-buffer sentinel, not -1: buf_create returns
  i + BUFSTRBASE with BUFSTRBASE == 1, so no real handle is ever 0 -- and a CSQC
  global after a map change is 0.  Same argument as rec_rp_view.
*/
float  rec_wt_rec;
float  rec_wt_view;
float  rec_wt_recn;              // lines in the .rec buffer
float  rec_wt_viewn;
float  rec_wt_rec0;              // first line after `begin`
float  rec_wt_view0;             // ditto, and always FS_VIEWHEAD

string rec_wt_path;              // the .rec we are playing
string rec_wt_owner;             // its `owner` header key
string rec_wt_map;               // its `map` header key
float  rec_wt_endticks;          // the `end` record's tick count
float  rec_wt_nsamp;             // samples in the file
float  rec_wt_recflags;          // the `flags` header key, -1 when absent
float  rec_wt_startseg;          // the SEGMENT the recording began at
// BUILD 57: and the LEG it belongs to -- 0 the full run, k stage k.  The two are
// no longer one number: a stage-1 run and a full run both begin at segment 0.
// From the `leg` header key, or derived from startseg for a file older than it.
float  rec_wt_leg;

/*
  BUILD 26: two more header facts, for hud_watch_info's file rows.

  `runid` is the .rec's only record of WHEN, and it needs no format change to be
  one: SV_RecOpen writes strftime("%Y%m%d-%H%M%S") plus the slot, so the first
  fifteen characters are a local wall clock to the second.  Kept as the raw
  string and formatted at the point of use -- a partial parse into three floats
  would be three ways to be wrong about a field whose only job is to be read.

  `pad` is the trailer's own count of pre-start samples (`end <ticks> <samples>
  <pad> <cps>`).  Nothing read it before, and it is the number that says how much
  of the span before t=0 is real approach rather than a reader's arithmetic --
  which is exactly the disagreement build 25's stage-slice bug turned out to be.
*/
string rec_wt_runid;
float  rec_wt_pad;

// rec_wt_time is declared in the cl_keys.qc override block with rec_wt_rate: it is
// the HUD's frame clock while a replay is up, and cl_hud.qc compiles first.
float  rec_wt_t0;                // first sample's t (negative with padding)
float  rec_wt_t1;                // last sample's t
// rec_wt_rate is declared in the cl_keys.qc override block: HUD_UpdateTurn needs
// it, to measure a turn per RUN second rather than per wall second at 4x speed.
float  rec_wt_slider;            // the speed slider's own 0..1 position
float  rec_wt_paused;
float  rec_wt_lastreal;          // cltime at the previous frame
float  rec_wt_clkerr;            // Patch 379: cltime advance not yet taken (Watch_Frame)

/*
  The cursors.  Both are monotone in the common case -- playback only ever runs
  forward -- so an ordinary frame costs one or two tokenize calls.  A scrub is
  what makes them jump, and that is what the coarse index below is for.
*/
float  rec_wt_rcur;              // .rec line: the sample with the largest t <= now
float  rec_wt_rnext;             // the sample line after it

/*
  THE COARSE INDEX, and it is what stops a scrub being a 25,000-line walk.

  Every Nth sample's line number and time, with N chosen at load so the table
  always fits whatever the file's length turns out to be.  A seek finds the
  entry with the largest t <= target -- a linear scan of at most WT_IDX floats --
  and then walks forward at most N samples.  Bounded either way, and no
  allocation.
*/
#define WT_IDX 512
float  rec_wt_ixline[WT_IDX];
float  rec_wt_ixt[WT_IDX];
float  rec_wt_ixn;
float  rec_wt_ixstep;

float  rec_wt_vxline[WT_IDX];
float  rec_wt_vxc[WT_IDX];       // Patch 379: the line's cltime (was its tick)
float  rec_wt_vxn;
float  rec_wt_vxstep;

/*
  PATCH 378: the load-time tables Watch_Sample interpolates with (sh_interp.qc).
  tools/watchtrace.py --model re-derives every counter here; keep the two in step.
*/
// Sample pairs a straight blend must not cross: keyed by the interval's ta.
#define WT_SNAPMAX 256
float  rec_wt_snt[WT_SNAPMAX];
float  rec_wt_snk[WT_SNAPMAX];   // 1 a record forced it, 2 Interp_Fit did
float  rec_wt_snn;
float  rec_wt_snover;
float  rec_wt_snrec;             // snaps by source, overflow included
float  rec_wt_snkin;
float  rec_wt_nfit0;             // Interp_Fit's verdicts over every pair
float  rec_wt_nfit1;
float  rec_wt_nfit2;
float  rec_wt_nveto;             // kinematic snaps a ride or speed/push/lift warp vetoed

// Eye slides: PMSrc_Duck at sample resolution.  f = Interp_Smooth(u0 + (t-ts)*rate).
#define WT_DKMAX    256
#define WT_DUCK_T   0.4         // pm_source.c:133 PMSRC_TIME_TO_DUCK
#define WT_UNDUCK_T 0.2         // pm_source.c:134 PMSRC_TIME_TO_UNDUCK
float  rec_wt_dks[WT_DKMAX];
float  rec_wt_dke[WT_DKMAX];
float  rec_wt_dku[WT_DKMAX];
float  rec_wt_dkr[WT_DKMAX];
float  rec_wt_dkn;
float  rec_wt_dkover;
float  rec_wt_dkfix;             // hull rose on the ground with no press seen
float  rec_wt_vh;                // eye heights: pmpin 2, serverinfo 1, 64/47 0
float  rec_wt_dvh;
float  rec_wt_vhsrc;

// Watch_Scan's carry between samples (the previous one, and what records said).
float  rec_wt_spt;
vector rec_wt_spo;
vector rec_wt_spv;
float  rec_wt_spfl;
float  rec_wt_spkey;
float  rec_wt_sfrc;
float  rec_wt_sveto;
float  rec_wt_sride;             // a non-zero `ride arm` is open
float  rec_wt_sdkrst;
float  rec_wt_sphase;            // 1 = a ground duck is sliding down
float  rec_wt_spress;

/*
  The .view time map.  A line's run time is tau = cltime - off, off being the
  lower envelope of cltime - ticks*tickrate over a knot (the tick stat only
  lags), lerped toward the next knot of the same span.  A span breaks at any
  record, a WT_VGAP of cltime, cltime or ticks going backwards, or a tick stat
  stalled WT_VGAP (those lines are dropped); `ghost` windows belong to none.
*/
#define WT_VKMAX  256
#define WT_VKSPAN 192           // knots per run length; the rest absorb span starts
#define WT_VGAP   0.1
float  rec_wt_vkline[WT_VKMAX];  // first and last line
float  rec_wt_vkend[WT_VKMAX];
float  rec_wt_vkc0[WT_VKMAX];    // their cltimes
float  rec_wt_vkc1[WT_VKMAX];
float  rec_wt_vkoff[WT_VKMAX];
float  rec_wt_vkbrk[WT_VKMAX];   // 1 = starts a span
float  rec_wt_vkn;
float  rec_wt_vkover;
float  rec_wt_vspans;
float  rec_wt_vshort;            // spans under 3 ticks, discarded
float  rec_wt_vstall;
float  rec_wt_vkstep;            // largest offset step between same-span knots, s
float  rec_wt_vcline;            // the knot being built
float  rec_wt_vcend;
float  rec_wt_vcc0;
float  rec_wt_vcc1;
float  rec_wt_vcoff;
float  rec_wt_vcbrk;
float  rec_wt_vk0;               // ...its span's first knot, and first cltime
float  rec_wt_vsc0;
float  rec_wt_vin;

// Patch 379: Watch_Parse's per-interval cache, and the cursors Watch_Seek resets.
float  rec_wt_ccur;              // the rcur / rnext it holds; -1 none
float  rec_wt_cnext;
float  rec_wt_cta;
float  rec_wt_ctb;
vector rec_wt_ca;
vector rec_wt_cb;
vector rec_wt_cva;
vector rec_wt_cvb;
vector rec_wt_cpa;               // [pitch, yaw, 0]
vector rec_wt_cpb;
float  rec_wt_cfla;
float  rec_wt_cflb;
float  rec_wt_ckeys;
vector rec_wt_cnorm;
vector rec_wt_cmv;
float  rec_wt_cfit;              // INTERP_*: what this interval is drawn with
float  rec_wt_cfa;               // the duck fraction at ta
float  rec_wt_snc;
float  rec_wt_dkc;
float  rec_wt_vkc;
float  rec_wt_vj;                // .view bracket: line vj (tau vjt) to vnl (vnt)
float  rec_wt_vjk;               // ...and their knots
float  rec_wt_vjt;
float  rec_wt_vjl;               // the line vja / vjkeys were read from
vector rec_wt_vja;
float  rec_wt_vjkeys;
float  rec_wt_vnl;               // -1: vj ends its span
float  rec_wt_vnk;
float  rec_wt_vnt;
float  rec_wt_vnal;
vector rec_wt_vna;
float  rec_wt_vnkeys;
float  rec_wt_eyeh;              // eye above the feet
float  rec_wt_asrc;              // 1: this frame's angles came from the .view
float  rec_wt_fit;
#define WT_ASNAP 45             // degrees: a bigger step between two samples is held

float  rec_wt_noview;            // `replay <path> noview`: open without the sidecar
float  rec_wt_loadms;
float  rec_wt_vmapms;
float  rec_wt_trfn;              // `replay trace frames`: real frames left to print
// The engine's host_frametime, bound by name (pr_csqc.c:9079).
float  clframetime;

/*
  The stage and checkpoint records, lifted out of the sample stream at load.

  Collected up front rather than noticed as the clock passes them, because a
  scrub backwards has to rebuild the split list from scratch and re-walking the
  file for it would make a drag cost a full pass per frame.  FS_MAXSPLITS and
  FS_MAXCPS are both 24, so 64 cannot overflow on a legal file; the guard is
  there for an illegal one.
*/
#define WT_EVMAX 64
float  rec_wt_evkind[WT_EVMAX];  // SPK_STAGE or SPK_CP
float  rec_wt_evseg[WT_EVMAX];   // segment, or checkpoint ordinal
float  rec_wt_evtick[WT_EVMAX];
float  rec_wt_evn;
float  rec_wt_evshown;           // how many are in the split list right now

// Patch 395: the stage windows (Watch_StageWindow).
#define WT_STGMAX 24                  // sv_timer.qc FS_MAXSPLITS (server-only define)
float  rec_wt_pw0[WT_STGMAX];         // a seg's `stagepost` window, ticks; -1 none
float  rec_wt_pw1[WT_STGMAX];
float  rec_wt_abandon;                // an `abandon` record: no finish row
float  rec_wt_winseg;                 // the window's seg, -1 none
float  rec_wt_wint0, rec_wt_wint1;    // its start and stop, run seconds
// Patch 431: what the bar, seeks and playback cover -- the file, or the window
// from 1 s before its start (rec_wt_wincut).
float  rec_wt_vt0, rec_wt_vt1;
float  rec_wt_wincut;
float  rec_wt_wantleg;                // the stage (leg) to cut to as the file opens, 0 none
float  rec_wt_bt0, rec_wt_bt1;        // what Watch_ScanRange last built
float  rec_wt_bline;                  // ...and the line it started on
float  rec_wt_wina, rec_wt_winb;      // the window in ticks, and how it was found
string rec_wt_winhow;

// Patch 432: the path is slot 0 of the run lines (cl_lines.qc), every sample of
// the built range.  It replaced 1024 control points and a 2048-point spline, which
// on a long run chose a control every 34 samples (~0.5 s) and drew a vague line.
float  rec_wt_snlast;            // Watch_ScanPair's last verdict: 1 record, 2 kinematic
float  rec_wt_cnt;               // samples the last Watch_ScanRange walked
float  rec_wt_bench;             // `replay bench <n>`: the next draw runs n times
float  rec_wt_p2pts;             // points the last Watch_Path2D projected

/*
  What the screen-space drawer did on the last rendered frame, for `replay
  status`.  Declared up here with the path tables rather than beside the drawer,
  because Watch_Path -- which runs BEFORE renderscene and takes half of the
  probe -- compiles first, and a QC global has to exist before the function that
  reads it.  Same ordering constraint as the two blocks at the top of cl_keys.qc.

  When the line drew nothing at all there was no way to tell "never called" from
  "clipped everything" from "drawn off-screen" from "projected against the wrong
  camera", and those want four different fixes.  Guessing between them cost two
  builds; these five numbers cost none.
*/
float  rec_wt_p2n;               // quads emitted
float  rec_wt_p2clip;            // segments dropped by the near-plane clip
vector rec_wt_p2first;           // where the first quad landed, in screen pixels
vector rec_wt_p2pre;             // a fixed probe projected BEFORE renderscene
vector rec_wt_p2post;            // ...and the same probe projected after it
vector rec_wt_p2axr;             // 64 units RIGHT of the probe, projected
vector rec_wt_p2axu;             // ...and 64 units UP
vector rec_wt_p2min;             // screen bbox of every quad actually emitted
vector rec_wt_p2max;
float  rec_wt_p2wild;            // segments dropped for absurd screen coordinates

/*
===========================================================================
  THE DEAD AIR.  Build 43.

  "the UI of the demo playback should mark parts where the player doesn't move
   as red, and have a selectable option that simply skips those parts during
   playback."

  Found the way everything else that classifies a stretch of this file is found:
  ONE EXTRA TEST INSIDE THE PASS THAT ALREADY WALKS EVERY SAMPLE.  Watch_Scan
  tokenizes all four thousand lines to choose control points, so the velocity is
  already in argv() and this costs a compare.  Per-frame detection was never on
  the table -- the file header's own argument applies unchanged: a scrub runs the
  clock backwards, and re-deriving spans from t0 on every frame of a drag would
  be six thousand iterations per frame.

  WHAT COUNTS AS STILL.  Horizontal speed only, and the vertical is left out
  deliberately: standing on a lift, or hanging at the apex of a jump, is not
  "not moving" in the sense the report means, and a run that idles usually idles
  on the ground where vertical speed is zero anyway.  hud_watch_idle_speed
  defaults to 20 u/s, which is under a walk and well under anything a surf map
  gives you for free.

  FOR HOW LONG.  hud_watch_idle_time, 0.5 s.  SEG_MINTIME (0.10) is this
  codebase's existing answer to "too short to be a thing", and this wants to be
  looser than that: half a second of standing still is deliberate, while a tenth
  is a landing, a crouch or a bad tick.

  A SAVE-LOCK HOLD WILL NEVER APPEAR HERE, AND THAT IS CORRECT.  The recorder
  freezes with the clock (see the file header: "rec lines held at 679 across the
  hold"), so a hold costs the file no samples at all and leaves no gap in `t` to
  find.  Only standing still WHILE THE CLOCK RUNS is marked -- which is the only
  kind that costs you a time.  Worth saying because the opposite is the obvious
  guess, and someone will otherwise go looking for the bug that is not there.

  THE PRE-START PAD IS EXCLUDED BY DEFAULT (hud_watch_idle_pad 0).  The approach
  is MEANT to be slow -- it is you walking up to the start box -- and marking two
  seconds of it red at the left end of the bar would say something false about
  the run.  The bar already marks t=0 with its own amber gradation, so the two
  halves are distinguishable without this.

  OVERFLOW IS REPORTED, not silent.  Same trade as the board cap (:1274) and the
  opposite of the segment column's (:1095): a run with more than WT_IDLEMAX
  parked stretches is doing something strange, and a bar that quietly stops
  marking them looks exactly like a run that stopped idling.
===========================================================================
*/
#define WT_IDLEMAX 64

float rec_wt_idt0[WT_IDLEMAX];   // run clock, seconds, where the stretch begins
float rec_wt_idt1[WT_IDLEMAX];   // ...and where it ends
float rec_wt_idn;
float rec_wt_idover;             // stretches the file had that would not fit

/*
  THE BOARD EVENTS, lifted out of the sample stream at load exactly as the stage
  and checkpoint records are, and for the same reason: the build pass walks the
  file forwards once and needs the board that belongs to the sample it is on.

  512 is generous rather than tight.  A surf run boards on every ramp entry --
  tens to a couple of hundred on a long map -- and a run that overflows this is
  one bouncing off a lip at 66 Hz, where the extra entries are the artifact
  SEG_MINTIME exists to absorb.  The overflow is REPORTED rather than silent; a
  segment column missing its last boards is a column that quietly lies.
*/
#define WT_BDMAX 512
float  rec_wt_bdt[WT_BDMAX];     // the run clock, seconds, at the board
float  rec_wt_bdc[WT_BDMAX];     // the engine's counter after it
vector rec_wt_bdn[WT_BDMAX];     // the latched arrival plane
vector rec_wt_bdv[WT_BDMAX];     // the PRE-clip velocity
float  rec_wt_bdn_n;
float  rec_wt_bdover;            // events the file had that would not fit

/*
  THE SEGMENT COLUMN, built once and then only counted into.

  One entry per row Seq_Push produced, in order, with the run tick it was pushed
  at.  A merge rewrites the last entry in place, exactly as it rewrites the last
  row of the live ring -- Watch_SeqRow is called from inside Seq_Push and is told
  which of the two happened, because from outside a merge and a scroll look the
  same (seq_n does not move for either).

  256 rows is about eight times what SEQ_MAX shows, which is what makes scrubbing
  backwards work: the column has to be able to show the twenty-four rows that
  were on screen at any point in the run, not just the last twenty-four.
*/
#define WT_SQMAX 256
float  rec_wt_sqkind[WT_SQMAX];
float  rec_wt_sqgain[WT_SQMAX];
float  rec_wt_sqde  [WT_SQMAX];
float  rec_wt_sqemax[WT_SQMAX];
float  rec_wt_sqdur [WT_SQMAX];
float  rec_wt_sqpct [WT_SQMAX];
float  rec_wt_sqlau [WT_SQMAX];
float  rec_wt_sqtick[WT_SQMAX];
/*
  BUILD 86 / PATCH 343 -- THE TWO COLUMNS THE CAPTURE NEVER HAD.

  seq_eend arrived in build 65 and seq_sub in build 66, and neither was added
  here, so a replay's column drew them from whatever the BUILD PASS left in the
  live ring -- which is the run's last row, repeated down every line. Every row
  showed the same absolute and the same Jump/Bhop word, and because the numbers
  were plausible nobody read them as missing.

  Both come free: Watch_BuildSeq runs the real segment machine over the file, so
  Seq_Push has already computed them from the .rec's own org/vel and ground
  phases by the time Watch_SeqRow is called. They only had to be kept.

  512 floats. The eight columns beside them are 2048 already, and the budget
  note in AGENTS.md is about the 4096-row tables that forced a 32-bit target.
*/
float  rec_wt_sqeend[WT_SQMAX];
float  rec_wt_sqsub [WT_SQMAX];
float  rec_wt_sqn;
float  rec_wt_sqshown;           // rows applied to the live ring right now
float  rec_wt_sqbuildtick;       // the tick the build pass is currently on
float  rec_wt_bdshown;           // the board event Board_Compute last ran on
float  rec_wt_bridged;           // build 25: ramp-contact gaps the hold bridged

/*
  The live column, put back where the replay found it.

  ITS OWN ARRAYS AND NOT seq_mk_*, deliberately.  That snapshot belongs to the
  save-lock slots and is keyed by id; borrowing it would mean opening a replay
  silently discarded the snapshot a save had taken, and the save's load would
  then fall through to the file without anything saying why.  Entangling two hold
  state machines is the build 11 dead-load-key bug, and this build already
  refused to do it once for the position freeze (rec_wt_hold vs rec_sl_hold).
  170 floats is a cheap price for not doing it again.
*/
float  rec_wt_svn;
float  rec_wt_svhaslaunch;
float  rec_wt_svkind[SEQ_MAX];
float  rec_wt_svgain[SEQ_MAX];
float  rec_wt_svde  [SEQ_MAX];
float  rec_wt_svemax[SEQ_MAX];
float  rec_wt_svdur [SEQ_MAX];
float  rec_wt_svpct [SEQ_MAX];
float  rec_wt_svlau [SEQ_MAX];
/*
  BUILD 86 -- THE THREE COLUMNS THIS PARK HAD BEEN DROPPING.

  seq_eend (build 65), seq_sub (build 66) and seq_eref (build 86) were never added
  here, and the park is one of the "places that move together" the essays beside
  those arrays warn about -- cl_board.qc's list simply never named this file.  The
  cost was real and silent: Watch_BuildSeq runs the segment machine over the FILE,
  so it overwrites all three, and Watch_SeqApply refills only the seven that are
  parked.  Stopping a replay therefore handed the player's own column back with
  every row's absolute (and every air row's Jump/Bhop/Air word) belonging to the
  demo they had just watched.

  All three, not just the new one: an absolute and the reference it is measured
  against are one value in two halves, and restoring either without the other
  would pair a row's energy with a zero from a different run.
*/
float  rec_wt_sveend[SEQ_MAX];
float  rec_wt_svsub [SEQ_MAX];
float  rec_wt_sveref[SEQ_MAX];
float  rec_wt_svheld;            // a snapshot is out; Watch_Stop must restore it

// The .rec sample columns, named so the tokenize calls below read as English.
#define WT_C_T      0
#define WT_C_ORG    1           // +2, +3
#define WT_C_VEL    4           // +5, +6
#define WT_C_PITCH  7
#define WT_C_YAW    8
#define WT_C_FLAGS  9
#define WT_C_KEYS  10
#define WT_C_MOVE  11           // +12, +13 -- fwd, side, up
#define WT_C_NORM  14           // +15, +16 -- v4, the plane under you
#define WT_C_V4N   17           // a v4 sample has at least this many columns

// SV_RecFlags' bits.  Named here because the server names them by construction
// rather than by constant, and a reader guessing at bit order is how a replay
// ends up crouching in the wrong places.
#define WT_F_ONGROUND  1
#define WT_F_DUCKED    2
#define WT_F_JUMP      4
#define WT_F_ATTACK    8
#define WT_F_RAMP     16        // v4: the move clipped a ramp plane this tick

// The .view sample columns.
#define WT_V_CLTIME 0
#define WT_V_TICKS  2
#define WT_V_PITCH  3
#define WT_V_YAW    4
#define WT_V_KEYS   5

/*
  Is this line a sample or a record?

  A sample begins with its timestamp, so with a digit or a minus; every record
  begins with its keyword.  Testing the first character rather than tokenizing
  matters: the load scan looks at every line in the file and tokenizing all six
  thousand of them to find the dozen that are records would be most of the load
  time for none of the information.
*/
// BUILD 24: the body moved to FS_IsSample in shared/sh_defs.qc, beside the tag
// and path spellers, because the SERVER needs the same test now -- its stage
// slicer has to know which lines carry a `t` it must rebase.  Kept as a name
// because this file calls it in four places.
float(string s) Watch_IsSample = { return FS_IsSample(s); };

/*
  How many segments the replayed track has, straight out of the zone tables --
  which this VM already parsed for the map it is standing on.  The .rec header
  does not carry it, and the live STAT_FS_TIMERSEGS describes whichever leg the
  PLAYER is armed on, which is not necessarily the one being watched.

  Zone_TrackSegs and NOT `max(zone_seg) + 1`, which is what this function said
  when it was first written and which is wrong by one: the END zone's own index
  IS the count, so counting it as a segment made the replay's panel read "stage
  1/6" on surf_aesthetic beside a live panel reading "stage 1/5".  One speller,
  in shared/sh_zones.qc, and the server calls the same one.
*/
float(float track) Watch_TrackSegs = { return Zone_TrackSegs(track); };

void() Watch_Free =
{
	if (rec_wt_rec >= 1)
		buf_del(rec_wt_rec);
	if (rec_wt_view >= 1)
		buf_del(rec_wt_view);
	rec_wt_rec  = 0;
	rec_wt_view = 0;
	rec_wt_recn = rec_wt_viewn = 0;
	Line_Clear(0);
	rec_wt_evn  = 0;
	rec_wt_on   = FALSE;
	rec_wt_wincut = FALSE;          // Patch 395: no window survives the file
	rec_wt_winseg = -1;
	// a `replay trace frames` still counting would print into the next file
	if (rec_wt_trfn > 0)
		print("wtfe\n");
	rec_wt_trfn = 0;
};

/*
  Patch 431: a file into a line buffer.  buf_loadfile splits with VFS_GETS, one
  VFS_READ per byte, and Windows maps only files up to 5 MB (fs_win32.c:480): a
  bigger one is a ReadFile per byte, 12.9 s for surf_rookie's 6.7 MB .rec.
  FILE_READ reads the file whole on the first fgets and splits it in memory
  (34 ms there).  An empty line is a blank line until the offset reaches the end.
*/
float(string path, float buf) Watch_BufLoad =
{
	local float fh, n;
	local string l;

	fh = fopen(path, FILE_READ);
	if (fh < 0)
		return FALSE;
	n = fsize(fh);
	while (1)
	{
		l = fgets(fh);
		if (l == "")
		if (fseek(fh) >= n)
			break;
		bufstr_add(buf, l, TRUE);
	}
	fclose(fh);
	return TRUE;
};

// ---- Patch 378: the interpolation tables, built inside Watch_Scan's pass two ----

void() Watch_TablesReset =
{
	rec_wt_snn = rec_wt_snover = rec_wt_snrec = rec_wt_snkin = 0;
	rec_wt_nfit0 = rec_wt_nfit1 = rec_wt_nfit2 = rec_wt_nveto = 0;
	rec_wt_dkn = rec_wt_dkover = rec_wt_dkfix = 0;
	rec_wt_sfrc = rec_wt_sveto = rec_wt_sride = rec_wt_sdkrst = FALSE;
	rec_wt_sphase = 0;
	rec_wt_spress = 0;
};

/*
  A record between two samples, for the interval they bound.  Only w/p/r lines
  are tokenized, so an `in` row costs one str2chr.  warp kinds per the grammar
  block (sv_timer.qc): tele/telerel/bhop/zone move the body, speed/push/lift only
  its velocity, and an unknown kind is left to Interp_Fit.  `ride` vetoes the
  kinematic test while its carrier moves the body (surf_trance's boosters).
*/
// Patch 433: what a record says about the sample pair it sits in, as bits, so the
// scan and a board line's build (Watch_LineJobStep) classify alike.
#define WTR_FORCE   1           // the body moved: a snap
#define WTR_VETO    2           // only its velocity: no kinematic snap
#define WTR_REWIND  4           // a restart: no duck slide spans it
#define WTR_RIDE    8           // a `ride`: RIDEON says whether its carrier is armed
#define WTR_RIDEON 16

float(string s) Watch_RecordBits =
{
	local float c, n;
	local string k, kind;

	c = str2chr(s, 0);
	if (c != 119 && c != 112 && c != 114)       // 'w' 'p' 'r'
		return 0;
	n = tokenize(s);
	k = argv(0);
	if (k == "warp")
	{
		if (n < 4)
			return 0;
		kind = argv(3);
		if (FS_IsSample(kind))                  // v9: argv(3) is the <row>
		if (n >= 5)
			kind = argv(4);
		if (kind == "tele" || kind == "telerel" || kind == "bhop" || kind == "zone")
			return WTR_FORCE;
		if (kind == "speed" || kind == "push" || kind == "lift")
			return WTR_VETO;
		return 0;
	}
	if (k == "portal")
		return WTR_FORCE;
	if (k == "restart" || k == "resume" || k == "retry")
		return WTR_FORCE | WTR_REWIND;
	if (k == "ride")
	if (n >= 7)
	{
		if (argv(3) == "arm")
		if (stof(argv(4)) != 0 || stof(argv(5)) != 0 || stof(argv(6)) != 0)
			return WTR_VETO | WTR_RIDE | WTR_RIDEON;
		return WTR_VETO | WTR_RIDE;
	}
	return 0;
};

void(string s) Watch_ScanRecord =
{
	local float k;

	k = Watch_RecordBits(s);
	if (k & WTR_FORCE)
		rec_wt_sfrc = TRUE;
	if (k & WTR_VETO)
		rec_wt_sveto = TRUE;
	if (k & WTR_REWIND)
		rec_wt_sdkrst = TRUE;
	if (k & WTR_RIDE)
		rec_wt_sride = (k & WTR_RIDEON) ? TRUE : FALSE;
};

void(float ts, float te, float u0, float rate) Watch_DuckSeg =
{
	if (rec_wt_dkn >= WT_DKMAX)
	{
		rec_wt_dkover = rec_wt_dkover + 1;
		return;
	}
	rec_wt_dks[rec_wt_dkn] = ts;
	rec_wt_dke[rec_wt_dkn] = te;
	rec_wt_dku[rec_wt_dkn] = u0;
	rec_wt_dkr[rec_wt_dkn] = rate;
	rec_wt_dkn = rec_wt_dkn + 1;
};

/*
  The pair (previous sample, this one): its Interp_Fit verdict and snap, and the
  duck machine.  The DUCKED bit is pmove.ducked, which flips at the END of a
  ground slide (sv_user.c:8412), so slides are anchored on the flip: a duck
  runs [press, flip], an unduck [flip - WT_UNDUCK_T, flip] -- exact even when a
  ceiling held the player down.  In the air both are instant.
*/
void(float t, vector o, vector v, float fl, float key) Watch_ScanPair =
{
	local float dt, fit, snap, g, h, k, pg, ph, pk, u0;

	if (rec_wt_sride)
		rec_wt_sveto = TRUE;
	rec_wt_snlast = 0;
	dt = t - rec_wt_spt;
	if (dt > 0)
	{
		fit = Interp_Fit(rec_wt_spo, rec_wt_spv, o, v, dt);
		if (fit == INTERP_SNAP)        rec_wt_nfit0 = rec_wt_nfit0 + 1;
		else if (fit == INTERP_LINEAR) rec_wt_nfit1 = rec_wt_nfit1 + 1;
		else                           rec_wt_nfit2 = rec_wt_nfit2 + 1;

		snap = 0;
		if (rec_wt_sfrc)
			snap = 1;
		else if (fit == INTERP_SNAP)
		{
			if (rec_wt_sveto)
				rec_wt_nveto = rec_wt_nveto + 1;
			else
				snap = 2;
		}
		rec_wt_snlast = snap;
		if (snap)
		{
			if (snap == 1) rec_wt_snrec = rec_wt_snrec + 1;
			else           rec_wt_snkin = rec_wt_snkin + 1;
			if (rec_wt_snn < WT_SNAPMAX)
			{
				rec_wt_snt[rec_wt_snn] = rec_wt_spt;
				rec_wt_snk[rec_wt_snn] = snap;
				rec_wt_snn = rec_wt_snn + 1;
			}
			else
				rec_wt_snover = rec_wt_snover + 1;
		}
	}

	g  = fl & WT_F_ONGROUND;
	h  = (fl & WT_F_DUCKED) ? 1 : 0;
	k  = (key & FSI_DUCK) ? 1 : 0;
	pg = rec_wt_spfl & WT_F_ONGROUND;
	ph = (rec_wt_spfl & WT_F_DUCKED) ? 1 : 0;
	pk = (rec_wt_spkey & FSI_DUCK) ? 1 : 0;
	// A save-state rewind: no slide spans it, and a release slide still running
	// (the only kind that ends past its sample) stops at the last sample before.
	if (rec_wt_sdkrst)
	{
		rec_wt_sphase = 0;
		if (rec_wt_dkn > 0)
		if (rec_wt_dke[rec_wt_dkn - 1] > rec_wt_spt)
			rec_wt_dke[rec_wt_dkn - 1] = rec_wt_spt;
		return;
	}

	if (h && !ph)
	{
		if (rec_wt_sphase == 1)
		{
			// in the air the rest of the slide is instant: Watch_Sample lerps it
			Watch_DuckSeg(rec_wt_spress, pg ? t : rec_wt_spt, 0, 1 / WT_DUCK_T);
			rec_wt_sphase = 0;
		}
		else if (pg)
			rec_wt_dkfix = rec_wt_dkfix + 1;
	}
	else if (ph && !h)
	{
		if (pg)
			Watch_DuckSeg(t - WT_UNDUCK_T, t, 1, -1 / WT_UNDUCK_T);
		rec_wt_sphase = 0;
	}
	else if (!h)
	{
		if (rec_wt_sphase == 1 && pk && !k)
		{
			// released part way down: Duck() inverts the elapsed time (pm_source.c:2441)
			u0 = (t - rec_wt_spress) / WT_DUCK_T;
			if (u0 > 1)
				u0 = 1;
			Watch_DuckSeg(rec_wt_spress, t, 0, 1 / WT_DUCK_T);
			Watch_DuckSeg(t, t + u0 * WT_UNDUCK_T, u0, -1 / WT_UNDUCK_T);
			rec_wt_sphase = 0;
		}
		else if (rec_wt_sphase == 0 && k && !pk && g)
		{
			rec_wt_sphase = 1;
			rec_wt_spress = t;
		}
	}
};

void(float ln, float c, float o, float brk) Watch_VKnotOpen =
{
	rec_wt_vcline = ln;
	rec_wt_vcend  = ln;
	rec_wt_vcc0   = c;
	rec_wt_vcc1   = c;
	rec_wt_vcoff  = o;
	rec_wt_vcbrk  = brk;
};

void() Watch_VKnotClose =
{
	if (rec_wt_vkn >= WT_VKMAX)
	{
		rec_wt_vkover = rec_wt_vkover + 1;
		return;
	}
	rec_wt_vkline[rec_wt_vkn] = rec_wt_vcline;
	rec_wt_vkend[rec_wt_vkn]  = rec_wt_vcend;
	rec_wt_vkc0[rec_wt_vkn]   = rec_wt_vcc0;
	rec_wt_vkc1[rec_wt_vkn]   = rec_wt_vcc1;
	rec_wt_vkoff[rec_wt_vkn]  = rec_wt_vcoff;
	rec_wt_vkbrk[rec_wt_vkn]  = rec_wt_vcbrk;
	rec_wt_vkn = rec_wt_vkn + 1;
};

void() Watch_VSpanEnd =
{
	Watch_VKnotClose();
	rec_wt_vin = FALSE;
	if (rec_wt_vcc1 - rec_wt_vsc0 < 3 * rec_wt_tickrate)
	{
		rec_wt_vkn    = rec_wt_vk0;
		rec_wt_vshort = rec_wt_vshort + 1;
	}
	else
		rec_wt_vspans = rec_wt_vspans + 1;
};

// Every .view line tokenized once; after pass two, which supplies t0 and t1.
void() Watch_ViewMap =
{
	local float i, n, c, k, o, t0, stride, pend, ghost, prevc, prevk, kc;
	local string s;

	rec_wt_vkn = rec_wt_vkover = rec_wt_vspans = rec_wt_vshort = rec_wt_vstall = 0;
	rec_wt_vkstep = 0;
	rec_wt_vin = FALSE;
	if (rec_wt_view < 1)
		return;

	t0 = rec_wt_t0;
	if (t0 < 0)
		t0 = 0;
	stride = (rec_wt_t1 - t0) / WT_VKSPAN;
	if (stride < 1)
		stride = 1;

	pend  = TRUE;
	ghost = FALSE;
	prevc = 0;
	prevk = -1;
	kc    = 0;
	for (i = rec_wt_view0; i < rec_wt_viewn; i = i + 1)
	{
		s = bufstr_get(rec_wt_view, i);
		if (!Watch_IsSample(s))
		{
			tokenize(s);
			if (argv(0) == "ghost")
				ghost = (stof(argv(1)) != 0);
			if (rec_wt_vin)
				Watch_VSpanEnd();
			pend = TRUE;
			continue;
		}
		if (ghost)
			continue;
		n = tokenize(s);
		if (n < 6)
			continue;
		c = stof(argv(WT_V_CLTIME));
		k = stof(argv(WT_V_TICKS));
		if (k != prevk)
			kc = c;
		else if (c - kc > WT_VGAP)
		{
			if (rec_wt_vin)
				Watch_VSpanEnd();
			pend  = TRUE;
			prevc = c;
			rec_wt_vstall = rec_wt_vstall + 1;
			continue;
		}
		if (rec_wt_vin)
		if (c - prevc > WT_VGAP || c < prevc || k < prevk)
		{
			Watch_VSpanEnd();
			pend = TRUE;
		}
		o = c - k * rec_wt_tickrate;
		if (pend)
		{
			rec_wt_vk0  = rec_wt_vkn;
			rec_wt_vsc0 = c;
			Watch_VKnotOpen(i, c, o, 1);
			rec_wt_vin  = TRUE;
			pend = FALSE;
		}
		else if (c - rec_wt_vcc0 >= stride)
		{
			Watch_VKnotClose();
			Watch_VKnotOpen(i, c, o, 0);
		}
		else
		{
			rec_wt_vcend = i;
			rec_wt_vcc1  = c;
			if (o < rec_wt_vcoff)
				rec_wt_vcoff = o;
		}
		prevc = c;
		prevk = k;
	}
	if (rec_wt_vin)
		Watch_VSpanEnd();

	for (i = 1; i < rec_wt_vkn; i = i + 1)
		if (!rec_wt_vkbrk[i])
		{
			o = fabs(rec_wt_vkoff[i] - rec_wt_vkoff[i - 1]);
			if (o > rec_wt_vkstep)
				rec_wt_vkstep = o;
		}
};

/*
  Pass one counts the samples and collects the records; a second walk builds the
  seek index (every ixstep-th sample, one stof each) and reads t0, t1 and the
  sample width.  Patch 431: the per-sample tables moved to Watch_ScanRange, which
  a stage opened from the board runs over its window only.
*/
void() Watch_Scan =
{
	local float i, n, c, ver, nextix;
	local string s;
	local float vp, vq;
	local float wpseg, wpdur, wpend;

	rec_wt_rec0     = 0;
	rec_wt_nsamp    = 0;
	rec_wt_evn      = 0;
	rec_wt_endticks = 0;
	rec_wt_recflags = -1;
	rec_wt_tickrate = 0;
	ver            = 0;
	rec_wt_track    = 0;
	rec_wt_startseg = 0;
	rec_wt_leg      = -1;           // build 57: -1 = no `leg` key seen yet
	rec_wt_owner    = "";
	rec_wt_map      = "";
	rec_wt_runid    = "";
	rec_wt_pad      = 0;
	rec_wt_vhsrc    = 0;

	// ---- the header, up to and including `begin` -------------------------
	for (i = 0; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		n = tokenize(s);
		if (n < 1)
			continue;

		if (argv(0) == "begin")
		{
			rec_wt_rec0 = i + 1;
			break;
		}
		if (n < 2)
			continue;

		// Unknown keys are SKIPPED, never rejected -- the rule the .rec header
		// has followed since v2 and the whole reason v3 could add four columns.
		if (argv(0) == "FTESURF-REC") ver            = stof(argv(1));
		if (argv(0) == "map")         rec_wt_map      = argv(1);
		if (argv(0) == "track")       rec_wt_track    = stof(argv(1));
		if (argv(0) == "startseg")    rec_wt_startseg = stof(argv(1));
		if (argv(0) == "leg")         rec_wt_leg      = stof(argv(1));
		if (argv(0) == "tickrate")    rec_wt_tickrate = stof(argv(1));
		if (argv(0) == "owner")       rec_wt_owner    = argv(1);
		if (argv(0) == "flags")       rec_wt_recflags = stof(argv(1));
		if (argv(0) == "runid")       rec_wt_runid    = argv(1);
		if (argv(0) == "pmpin")
		{
			// The file's own eye heights (sv_user.c:111 pins both by name).
			vp = strstrofs(s, " viewheight=");
			vq = strstrofs(s, " duckviewheight=");
			if (vp >= 0)
			if (vq >= 0)
			{
				rec_wt_vh    = stof(substring(s, vp + 12, 16));
				rec_wt_dvh   = stof(substring(s, vq + 16, 16));
				rec_wt_vhsrc = 2;
			}
		}
	}

	if (rec_wt_tickrate <= 0)
		rec_wt_tickrate = PM_TICK;

	if (!rec_wt_vhsrc)
	{
		rec_wt_vh  = serverkeyfloat("pm_viewheight");
		rec_wt_dvh = serverkeyfloat("pm_duckviewheight");
		rec_wt_vhsrc = 1;
		if (rec_wt_vh <= 0 || rec_wt_dvh <= 0)
		{
			rec_wt_vh    = 64;
			rec_wt_dvh   = 47;          // the engine's and default.cfg:346's, not 46
			rec_wt_vhsrc = 0;
		}
	}

	/*
	  BUILD 57: A FILE WITH NO `leg` KEY IS OLDER THAN STAGE 1 BEING A LEG, and it
	  says exactly one thing: every stage run before build 57 began past segment 0
	  and every run that began AT segment 0 was the full track.  So its leg is
	  derived from the segment by the same helper the writer uses, with stagerun
	  standing in as `startseg > 0` -- which is not a guess about those files but
	  the only thing they could have meant.  After the loop, not inside it, because
	  the header's own rule is that its keys are order-free.
	*/
	if (rec_wt_leg < 0)
		rec_wt_leg = FS_LegOf(rec_wt_startseg, rec_wt_startseg > 0);

	// ---- pass one: count samples, collect records ------------------------
	for (i = 0; i < WT_STGMAX; i = i + 1)
	{
		rec_wt_pw0[i] = -1;
		rec_wt_pw1[i] = -1;
	}
	rec_wt_abandon = FALSE;
	wpseg = -1;
	wpdur = 0;
	rec_wt_bdn_n  = 0;
	rec_wt_bdover = 0;
	for (i = rec_wt_rec0; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		c = str2chr(s, 0);
		if (c == 45 || (c >= 48 && c <= 57))        // FS_IsSample, inline
		{
			rec_wt_nsamp = rec_wt_nsamp + 1;
			continue;
		}
		// Patch 431: `in`, `inend` and `mc` are two thirds of a v9 file; nothing
		// here reads them.
		if (c == 105 || c == 109)
			continue;

		n = tokenize(s);
		if (n < 2)
			continue;

		/*
		  The boards share this walk but not WT_EVMAX: they are bounded only by
		  the map's ramps, and a shared cap would let a board-heavy run push the
		  stages out of the split list.  Overflow is reported (Watch_BuildSeq).
		*/
		if (argv(0) == "board")
		{
			if (n < 9)
				continue;
			if (rec_wt_bdn_n >= WT_BDMAX)
			{
				rec_wt_bdover = rec_wt_bdover + 1;
				continue;
			}
			rec_wt_bdt[rec_wt_bdn_n] = stof(argv(1));
			rec_wt_bdc[rec_wt_bdn_n] = stof(argv(2));
			rec_wt_bdn[rec_wt_bdn_n] = [stof(argv(3)), stof(argv(4)), stof(argv(5))];
			rec_wt_bdv[rec_wt_bdn_n] = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
			rec_wt_bdn_n = rec_wt_bdn_n + 1;
			continue;
		}

		/*
		  Patch 395: `stagepost <seg> <dur>` is written just before the `stage`
		  (or `end`) that closes seg, so its window is [T - dur, T] at that tick
		  -- the stage's own start, past any `!r` restarts inside it.
		*/
		if (argv(0) == "stagepost")
		{
			wpseg = -1;
			if (n >= 3)
			{
				wpseg = stof(argv(1));
				wpdur = stof(argv(2));
			}
			continue;
		}
		if (argv(0) == "abandon")
		{
			rec_wt_abandon = TRUE;
			continue;
		}
		if (wpseg >= 0)
		{
			wpend = -1;
			if (argv(0) == "end")
				wpend = stof(argv(1));
			else if (argv(0) == "stage")
			if (n >= 3)
				wpend = stof(argv(2));
			if (wpend >= 0)
			{
				if (wpseg < WT_STGMAX)
				{
					rec_wt_pw0[wpseg] = wpend - wpdur;
					rec_wt_pw1[wpseg] = wpend;
				}
				wpseg = -1;
			}
		}

		if (argv(0) == "end")
		{
			rec_wt_endticks = stof(argv(1));
			// end <ticks> <samples> <pad> <cps>.  Guarded on the width rather
			// than assumed: a REC 2 trailer is two fields and argv(3) of it is
			// "", which stofs to a confident zero.
			if (n >= 4)
				rec_wt_pad = stof(argv(3));
			continue;
		}

		if (rec_wt_evn >= WT_EVMAX)
			continue;

		if (argv(0) == "stage")
		{
			if (n >= 3)
			{
				rec_wt_evkind[rec_wt_evn] = SPK_STAGE;
				rec_wt_evseg[rec_wt_evn]  = stof(argv(1));
				rec_wt_evtick[rec_wt_evn] = stof(argv(2));
				rec_wt_evn = rec_wt_evn + 1;
			}
			continue;
		}
		if (argv(0) == "cp")
		{
			if (n >= 3)
			{
				rec_wt_evkind[rec_wt_evn] = SPK_CP;
				rec_wt_evseg[rec_wt_evn]  = stof(argv(1));
				rec_wt_evtick[rec_wt_evn] = stof(argv(2));
				rec_wt_evn = rec_wt_evn + 1;
			}
			continue;
		}
	}

	// ---- the seek index, t0 and t1 -----------------------------------------
	rec_wt_ixstep = ceil(rec_wt_nsamp / (WT_IDX - 1));
	if (rec_wt_ixstep < 1)
		rec_wt_ixstep = 1;
	rec_wt_ixn = 0;
	rec_wt_t0  = 0;
	rec_wt_t1  = 0;
	rec_wt_v4  = FALSE;
	nextix = 0;
	n = 0;                          // sample ordinal
	for (i = rec_wt_rec0; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		c = str2chr(s, 0);
		if (c != 45 && (c < 48 || c > 57))
			continue;
		if (n == 0)
		{
			rec_wt_t0 = stof(s);    // atof stops at the space: the `t` column

			/*
			  v4 is decided by the SAMPLE and not by the header key alone.  A v3
			  prefix resumed under a v4 build writes a v4 header over thirteen-
			  column samples, and argv(14) of those is "" -- a zero normal the
			  strafe bar would draw as confidently as a measured one.
			*/
			rec_wt_v4 = (ver >= 4 && tokenize(s) >= WT_C_V4N);
		}
		if (n == rec_wt_nsamp - 1)
			rec_wt_t1 = stof(s);
		if (n == nextix)
		{
			nextix = n + rec_wt_ixstep;
			if (rec_wt_ixn < WT_IDX)
			{
				rec_wt_ixline[rec_wt_ixn] = i;
				rec_wt_ixt[rec_wt_ixn]    = stof(s);
				rec_wt_ixn = rec_wt_ixn + 1;
			}
		}
		n = n + 1;
	}
	rec_wt_bt0 = 0;
	rec_wt_bt1 = -1;                // nothing built yet: Watch_ScanRange

	// ---- the .view's index -----------------------------------------------
	rec_wt_view0  = 0;
	rec_wt_vxn    = 0;
	if (rec_wt_view >= 1)
	{
		for (i = 0; i < rec_wt_viewn; i = i + 1)
		{
			s = bufstr_get(rec_wt_view, i);
			if (Watch_IsSample(s))
				break;
		}
		rec_wt_view0 = i;

		n = rec_wt_viewn - rec_wt_view0;
		rec_wt_vxstep = ceil(n / (WT_IDX - 1));
		if (rec_wt_vxstep < 1)
			rec_wt_vxstep = 1;

		/*
		  BUILD 43 -- RECORDS ARE STEPPED OVER HERE, THE WAY THE .rec'S SCAN
		  ALREADY STEPS OVER ITS OWN.

		  The .view is not all samples.  Rec_ViewFrame interleaves a FOUR-token
		  `ghost <0|1> <cltime> <ticks>` line (cl_replay.qc:1050-1056), and this
		  loop used to take whatever line the stride landed on and read argv(2)
		  as a run tick -- which on a ghost line is a CLTIME, a number in the
		  hundreds where a tick is in the thousands but on a different scale
		  entirely.  One poisoned entry sent Watch_ViewBlock's seek to the wrong
		  starting line, and the same unfiltered read in Watch_ViewBlock itself
		  could hand the camera a tick count as its pitch.  (Patch 379 replaced
		  Watch_ViewBlock with Watch_ViewStart, and the index holds cltime.)

		  Latent rather than observed: no .rec or .view on disk carries a ghost
		  record, because no ghosted run has ever been recorded.  It is fixed
		  here because build 43 is editing the reader either way, and because the
		  .rec side has had FS_IsSample guarding all four of its scans since
		  build 24 -- the .view simply never got the same treatment.

		  The cost is one bufstr_get and one first-character test per line at
		  load instead of one per stride.  The .rec's own pass tokenizes every
		  line in full, so this is not the expensive half of anything.
		*/
		nextix = rec_wt_view0;
		for (i = rec_wt_view0; i < rec_wt_viewn; i = i + 1)
		{
			if (!Watch_IsSample(bufstr_get(rec_wt_view, i)))
			{
				// Push the wanted ordinal past it rather than losing the whole
				// stride: an index that skips an entry is coarser, and this one
				// is already only 512 entries over the file.
				if (i == nextix)
					nextix = i + 1;
				continue;
			}
			if (i != nextix)
				continue;
			nextix = i + rec_wt_vxstep;
			if (rec_wt_vxn >= WT_IDX)
				break;
			tokenize(bufstr_get(rec_wt_view, i));
			rec_wt_vxline[rec_wt_vxn] = i;
			rec_wt_vxc[rec_wt_vxn]    = stof(argv(WT_V_CLTIME));
			rec_wt_vxn = rec_wt_vxn + 1;
		}
	}

	rec_wt_vmapms = gettime(1);
	Watch_ViewMap();
	rec_wt_vmapms = (gettime(1) - rec_wt_vmapms) * 1000;

	/*
	  BUILD 76: THE CEILING IS 5, AND WITHOUT THIS LINE THE NOTE WOULD HAVE FIRED
	  ON EVERY RECORDING THIS GAME MAKES FROM NOW ON.

	  Version 5 has exactly version 4's seventeen columns and version 4's header
	  keys plus one, because the bump is about what the NUMBERS MEAN -- counted
	  off the mover's tick counter rather than sampled off sv.time -- and not
	  about the grammar.  So this reader needed no new parse at all.  What it
	  needed was to stop calling a current file unknown: a yellow "this build
	  knows 4" in front of an ordinary replay is the shape of message a player
	  reports as a bug, and it would teach them to skip the next one, which might
	  matter.

	  STILL ONE-SIDED, deliberately.  A file NEWER than this build is worth a word
	  because the columns really could move next time; an older one is handled by
	  rec_wt_v4 and its own line.  And still a literal rather than a constant: the
	  literal is the thing that must be edited when the format moves, and a
	  constant three files away is how that gets missed.
	*/
	/*
	  BUILD 82: 5 -> 6, AND FOR THE THIRD TIME THIS READER NEEDED NO NEW PARSE.

	  Version 6 adds the INPUT TRACE: one `in` record per simulated move, plus an
	  `instart` header key and a fifth field on `end`.  Every one of those is
	  additive by this format's own rule -- the sample stream still has seventeen
	  columns, the trailer's first four fields are unmoved (the width guard on
	  `end` above already reads `n >= 4` rather than assuming), and an unknown
	  record falls out of both sweeps below without being counted as anything.

	  So the only thing that had to change is this literal, and it had to change
	  for the reason the paragraph above gives: a yellow "this build knows 5" in
	  front of every ordinary replay is the shape of message a player reports as
	  a bug, and it would teach them to skip the next one, which might matter.

	  WHAT v6 DOES COST THIS READER, said plainly because nothing else will say
	  it: the file is about 1.8x the LINES, and this replay loads all of them into
	  rec_wt_rec and sweeps them three times.  Nothing here is quadratic and the
	  sample-indexed tables are sized off rec_wt_nsamp rather than off the line
	  count, so the cost is linear and bounded -- but a long run's replay now
	  holds roughly twice the strings it used to, and that is the first place a
	  memory ceiling will show up.
	*/
	/*
	  BUILD 83: 6 -> 7, AND FOR THE FOURTH TIME THIS READER NEEDED NO NEW PARSE.

	  Version 7 adds `startjit` (a header key, and header keys have been order-free
	  since v3) and `warp` (a record, which falls out of all three sweeps below
	  exactly as `in` does -- Watch_IsSample tests the first character, and `w` is
	  not a digit), plus a sixth field on `end`, which the width guard above reads
	  as `n >= 4` rather than assuming.

	  WHAT THE WATCHER DELIBERATELY DOES NOT DO WITH EITHER, because it is worth
	  saying once rather than being rediscovered as a missing feature.  A `warp` is
	  a discontinuity the camera ALREADY follows correctly: the sample stream
	  carries the post-teleport position, the curve is fitted through the samples,
	  and build 23's control-point logic has handled stage teleports since long
	  before anything recorded them.  The record exists for re-simulation, which
	  happens somewhere else entirely.  Drawing a marker at one would be a feature
	  request, not a format obligation.

	  Same for `startjit`: two units at the run's first frame is below the sample
	  stream's own %.2f-to-the-eye visibility, and the camera has no opinion about
	  where a run was supposed to start.

	  PATCH 379: superseded for `warp` -- a blend across a teleport smeared the
	  camera over the jump, so its kind now feeds the snap table
	  (Watch_ScanRecord), and `ride` vetoes it.
	*/
	/*
	  BUILD 85: 7 -> 8, AND FOR THE FIFTH TIME THIS READER NEEDED NO NEW PARSE.
	  `ride` and `inend` fall out of all three sweeps like `warp` and `in` do
	  (Watch_IsSample tests the first character), and the seventh `end` field is
	  covered by the `n >= 4` width guard above.

	  The camera has even less to do with this one: a ride produces NO position
	  discontinuity at all, so there is nothing to show that the motion does not
	  already show.  The record is for re-simulation, elsewhere.
	*/
	// BUILD 87: 8 -> 9.  `seed`, `pm`, `pe` and `portal` are records this reader
	// skips like `in`; the in row's new column and the trailer's are unread here.
	// Patch 364: 10.  `pause`/`session` are skipped too; `t` runs on across them.
	if (ver > 10)
		print(sprintf("^3replay: %s is FTESURF-REC %g and this build knows 10; "
		              "reading it anyway\n", rec_wt_path, ver));
};

/*
  Patch 431: the per-sample tables over [ra, rb] -- the path's control points, the
  dead air, and the snap and duck tables Watch_Sample interpolates with (the
  former pass two of Watch_Scan).  Watch_Open runs it over the whole file, or over
  a stage's cut when the board asked for one (rec_wt_wantseg); Watch_SetCut
  rebuilds for the whole file when the cut is lifted.  The walk starts at the last
  sample at or before ra and ends on the first past rb, which closes the last
  interval.
*/
void(float ra, float rb) Watch_ScanRange =
{
	local float i, k, c;
	local string s;
	local vector o;
	local float t, spd, idlim, idmin, idpad, idfrom, idon, idnow;
	local vector v;
	local float fl, key;

	rec_wt_bt0 = ra;
	rec_wt_bt1 = rb;

	// The index entry at or before ra, then its last sample at or before ra.
	k = 0;
	for (i = 0; i < rec_wt_ixn; i = i + 1)
		if (rec_wt_ixt[i] <= ra)
			k = i;
	rec_wt_bline = (rec_wt_ixn > 0) ? rec_wt_ixline[k] : rec_wt_rec0;
	for (i = rec_wt_bline + 1; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		if (!Watch_IsSample(s))
			continue;
		if (stof(s) > ra)
			break;
		rec_wt_bline = i;
	}
	// The whole file starts where it always did, so a `ride` ahead of the first
	// sample still opens.  A cut misses one armed before its start: the carrier
	// then vetoes nothing until its next record (only the kinematic snap test).
	if (ra <= rec_wt_t0)
		rec_wt_bline = rec_wt_rec0;

	rec_wt_cnt = 0;
	c = 0;                          // sample ordinal, from the range's first
	Line_Begin(0);

	/*
	  The dead-air thresholds, read ONCE.  Registered by Watch_Init with these
	  same defaults; the fallbacks are here because a cvar read before its
	  registercvar returns "" and a zero speed threshold would mark nothing while
	  looking like it was working.
	*/
	rec_wt_idn    = 0;
	rec_wt_idover = 0;
	idon         = FALSE;
	idfrom       = 0;
	idlim        = cvar("hud_watch_idle_speed");
	if (idlim <= 0) idlim = 20;
	idmin        = cvar("hud_watch_idle_time");
	if (idmin <= 0) idmin = 0.5;
	idpad        = cvar("hud_watch_idle_pad");

	Watch_TablesReset();
	for (i = rec_wt_bline; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);
		if (!Watch_IsSample(s))
		{
			Watch_ScanRecord(s);
			continue;
		}

		tokenize(s);
		v   = [stof(argv(WT_C_VEL + 0)), stof(argv(WT_C_VEL + 1)),
		       stof(argv(WT_C_VEL + 2))];
		fl  = stof(argv(WT_C_FLAGS));
		key = stof(argv(WT_C_KEYS));

		o_x = stof(argv(WT_C_ORG + 0));
		o_y = stof(argv(WT_C_ORG + 1));
		o_z = stof(argv(WT_C_ORG + 2));

		/*
		  ---- DEAD AIR, and it is a state machine of one bit ----------------

		  A stretch OPENS on the first slow sample and CLOSES on the first fast
		  one, and is only kept if it lasted.  Closing on the fast sample rather
		  than on the last slow one is deliberate: the run resumed somewhere
		  between those two ticks, and a mark that stops at the last slow sample
		  leaves a tick-wide gap of unmarked standing still at the end of every
		  stretch.  Half a tick long, and wrong in the direction that under-
		  reports, which is the one worth avoiding.

		  The `t >= 0` half is nested rather than &&'d out of habit rather than
		  necessity -- there is no array index here -- but the file's rule is
		  worth keeping uniform, and the two conditions read as the two separate
		  questions they are.
		*/
		t   = stof(argv(WT_C_T));
		spd = vlen([stof(argv(WT_C_VEL + 0)), stof(argv(WT_C_VEL + 1)), 0]);

		idnow = FALSE;
		if (spd < idlim)
		if (idpad || t >= 0)
			idnow = TRUE;

		if (idnow)
		{
			if (!idon)
			{
				idon   = TRUE;
				idfrom = t;
			}
		}
		else if (idon)
		{
			idon = FALSE;
			if (t - idfrom >= idmin)
			{
				if (rec_wt_idn < WT_IDLEMAX)
				{
					rec_wt_idt0[rec_wt_idn] = idfrom;
					rec_wt_idt1[rec_wt_idn] = t;
					rec_wt_idn = rec_wt_idn + 1;
				}
				else
					rec_wt_idover = rec_wt_idover + 1;
			}
		}

		if (c > 0)
			Watch_ScanPair(t, o, v, fl, key);
		// Patch 432: the run line, broken where the pair snapped (a teleport).
		Line_Add(0, o, spd, t, (c > 0) ? rec_wt_snlast : 0);
		rec_wt_spt    = t;
		rec_wt_spo    = o;
		rec_wt_spv    = v;
		rec_wt_spfl   = fl;
		rec_wt_spkey  = key;
		rec_wt_sfrc   = FALSE;
		rec_wt_sveto  = FALSE;
		rec_wt_sdkrst = FALSE;

		c = c + 1;
		if (t > rb)
			break;                  // the sample that closes the last interval
	}

	Line_End(0);
	rec_wt_cnt = c;

	/*
	  A run that ENDS parked still ends parked, and the file's last sample is
	  where it ends.  Without this a player who crossed the line and stood there
	  -- or a `last.rec` from an attempt that was simply abandoned -- would have
	  its final stretch dropped, which is the one stretch most likely to be long.
	*/
	if (idon)
	if (rec_wt_spt - idfrom >= idmin)
	{
		if (rec_wt_idn < WT_IDLEMAX)
		{
			rec_wt_idt0[rec_wt_idn] = idfrom;
			rec_wt_idt1[rec_wt_idn] = rec_wt_spt;
			rec_wt_idn = rec_wt_idn + 1;
		}
		else
			rec_wt_idover = rec_wt_idover + 1;
	}

	if (rec_wt_idover > 0)
		print(sprintf("^3replay: %g still stretch(es) past the %g cap were dropped; "
		              "the bar stops marking them\n", rec_wt_idover, WT_IDLEMAX));
};

/*
  Patch 433: a board line, a run line built from a file over frames (the board's
  `line` column; cl_scores.qc).  Pass one reads the header and, when a stage row
  asked for its stage out of the run's file (leg > 0 and the file is not that
  leg's), finds the stage's window as Watch_WindowFind does; pass two adds every
  sample in the window, broken where Watch_ScanPair would snap.  Another file's
  handle, not rec_wt_rec: a replay open meanwhile is untouched.
*/
#define WT_LJ_PASS1 6000        // lines a frame: pass one only looks at a line's first byte
#define WT_LJ_PASS2 2500        // pass two tokenizes the window's samples

float  wt_lj_fh;                // the file, open while wt_lj_phase is not 0
float  wt_lj_slot, wt_lj_leg, wt_lj_phase;    // phase 1 records, 2 samples, 0 idle
float  wt_lj_hdr;               // still in the header
float  wt_lj_tick, wt_lj_fleg, wt_lj_seg;
float  wt_lj_wseg, wt_lj_wdur, wt_lj_pa, wt_lj_pb, wt_lj_sa, wt_lj_sb, wt_lj_end;
float  wt_lj_ta, wt_lj_tb;      // the window, run seconds
float  wt_lj_c, wt_lj_pt, wt_lj_frc, wt_lj_veto, wt_lj_ride;
vector wt_lj_po, wt_lj_pv;

// Patch 441: THE JOB'S OWN `stage` table and finish tick.  Patch 437 filled the
// REPLAY's (rec_wt_ev*, rec_wt_endticks) instead and cleared it at every job
// start, so opening a board line while watching a replay wiped that replay's
// splits and its finish -- the duration in the title, the playhead clamp
// (:2865) and the FINISH row (:2191) all read those two.  Stage events only: the
// fallback below looks at nothing else.
float  wt_lj_evseg[WT_EVMAX];
float  wt_lj_evtick[WT_EVMAX];
float  wt_lj_evn;
float  wt_lj_endt;              // the job file's `end` ticks

/*
  Patch 441: the `stage` records fallback, over the table the CALLER names -- src
  0 the open replay's, 1 the line job's.  One spelling, which is what Patch 437
  wanted, without the two sharing scratch: it called Watch_WindowFind, and that
  function's job is to SET the replay's cut (rec_wt_wincut/vt0/vt1), so asking it
  about another file retargeted the replay the board row was standing in for.
  Answers in wt_ws_a/wt_ws_b -- the zs_* idiom, so the question writes nothing.
  a is -1 when seg's own record is missing (seg 0 starts at 0); b falls back to
  the file's finish.
*/
float  wt_ws_a, wt_ws_b;

void(float seg, float src) Watch_StageSpan =
{
	local float i, n, sg, tk;

	sg = tk = 0;                    // fteqcc cannot see that the branch below always assigns
	wt_ws_a = (seg > 0) ? -1 : 0;
	wt_ws_b = src ? wt_lj_endt : rec_wt_endticks;
	n       = src ? wt_lj_evn  : rec_wt_evn;
	for (i = 0; i < n; i = i + 1)
	{
		if (src)
		{
			sg = wt_lj_evseg[i];
			tk = wt_lj_evtick[i];
		}
		else
		{
			if (rec_wt_evkind[i] != SPK_STAGE)
				continue;
			sg = rec_wt_evseg[i];
			tk = rec_wt_evtick[i];
		}
		if (sg == seg)
			wt_ws_a = tk;
		if (sg == seg + 1)
		{
			wt_ws_b = tk;
			return;
		}
	}
};

void() Watch_LineJobStop =
{
	if (wt_lj_phase)
		fclose(wt_lj_fh);
	wt_lj_phase = 0;
};

// The window pass two keeps, and on into pass two.  FALSE: no window for the stage.
//
// Patch 437: and the FALLBACK IS THE SAME SPELLING THE REPLAY USES, which it was
// not.  This one took the LAST `stage seg` record where Watch_WindowFind takes the
// one BEFORE the first `stage seg+1`.  The two agree whenever the file carries a
// `stagepost` for the stage, and a board row's run always does -- so the difference
// was reachable only through an old file opened another way, where the board drew
// a line to the run's last stage record and the replay drew one to the next
// boundary.  Watch_WindowFind is the authority: it is the one the bar, the seeks
// and playback are cut to, so a board line that disagrees with the replay it is
// standing in for is the wrong one of the two.
float() Watch_LineJobWindow =
{
	local float a, b;

	wt_lj_ta = 0;                   // a whole file from its clock's start: no pad
	wt_lj_tb = 99999999;
	if (wt_lj_tick <= 0)
		wt_lj_tick = PM_TICK;
	if (wt_lj_fleg < 0)
		wt_lj_fleg = FS_LegOf(wt_lj_seg, wt_lj_seg > 0);
	if (wt_lj_leg > 0)
	if (wt_lj_leg != wt_lj_fleg)
	{
		if (wt_lj_pa < 0)
		{
			/*
			  Pass one read the `stagepost` pair into pa/pb.  Without it, the
			  `stage` records -- through the same Watch_StageSpan the replay's
			  finder uses, over THIS file's table (Patch 441; Patch 437 borrowed
			  the replay's own and its window state with it).  Ticks in both
			  spellings.
			*/
			Watch_StageSpan(wt_lj_leg - 1, 1);
			a = wt_ws_a;
			b = wt_ws_b;
			if (a >= 0 && b > a)
			{
				wt_lj_pa = a;
				wt_lj_pb = b;
			}
			else
			{
				wt_lj_pa = (wt_lj_leg > 1) ? wt_lj_sa : 0;
				wt_lj_pb = (wt_lj_sb >= 0) ? wt_lj_sb : wt_lj_end;
			}
		}
		if (wt_lj_pa < 0 || wt_lj_pb <= wt_lj_pa)
		{
			print(sprintf("scores: no window for stage %g in that run\n", wt_lj_leg));
			return FALSE;
		}
		wt_lj_ta = wt_lj_pa * wt_lj_tick;
		wt_lj_tb = wt_lj_pb * wt_lj_tick;
	}
	wt_lj_phase = 2;
	wt_lj_c = 0;
	wt_lj_frc = wt_lj_veto = wt_lj_ride = FALSE;
	return TRUE;
};

float(float slot, string path, float leg) Watch_LineJobStart =
{
	Watch_LineJobStop();
	wt_lj_fh = fopen(path, FILE_READ);
	if (wt_lj_fh < 0)
		return FALSE;
	wt_lj_slot  = slot;
	wt_lj_leg   = leg;
	wt_lj_phase = 1;
	wt_lj_hdr   = TRUE;
	wt_lj_tick  = 0;
	wt_lj_fleg  = -1;
	wt_lj_seg   = 0;
	wt_lj_wseg  = -1;
	wt_lj_pa = wt_lj_pb = wt_lj_sa = wt_lj_sb = wt_lj_end = -1;
	// Patch 441: the JOB's table, cleared for this file.  Patch 437 cleared the
	// replay's here instead, which is why a board line stole the splits and the
	// finish of a replay that was already open.
	wt_lj_evn  = 0;
	wt_lj_endt = 0;
	Line_Begin(slot);
	return TRUE;
};

// One frame of the job: 0 working, 1 built, -1 failed (nothing to draw).
float() Watch_LineJobStep =
{
	local float i, n, c, k, t, dt, brk, seg;
	local string s;
	local vector o, v;

	if (wt_lj_phase == 0)
		return -1;
	for (i = 0; i < ((wt_lj_phase == 1) ? WT_LJ_PASS1 : WT_LJ_PASS2); i = i + 1)
	{
		s = fgets(wt_lj_fh);
		if (s == "")
		if (fseek(wt_lj_fh) >= fsize(wt_lj_fh))
		{
			if (wt_lj_phase == 1)
			{
				// The window: the stage's own record pair, else the `stage` records.
				if (!Watch_LineJobWindow())
				{
					Watch_LineJobStop();
					return -1;
				}
				fseek(wt_lj_fh, 0);
				wt_lj_hdr = TRUE;
				return 0;
			}
			Line_End(wt_lj_slot);
			Line_Range(wt_lj_slot, wt_lj_ta, wt_lj_tb, wt_lj_ta);
			Watch_LineJobStop();
			return ln_on[wt_lj_slot] ? 1 : -1;
		}

		c = str2chr(s, 0);
		if (wt_lj_hdr)
		{
			if (substring(s, 0, 5) == "begin")
			{
				wt_lj_hdr = FALSE;
				// No stage asked for, or the file is that stage's own: no pass one.
				if (wt_lj_phase == 1)
				if (wt_lj_leg <= 0 || wt_lj_leg == ((wt_lj_fleg >= 0) ? wt_lj_fleg
				                                    : FS_LegOf(wt_lj_seg, wt_lj_seg > 0)))
					Watch_LineJobWindow();
			}
			else if (wt_lj_phase == 1)
			{
				n = tokenize(s);
				if (argv(0) == "tickrate")  wt_lj_tick = stof(argv(1));
				if (argv(0) == "leg")       wt_lj_fleg = stof(argv(1));
				if (argv(0) == "startseg")  wt_lj_seg  = stof(argv(1));
			}
			continue;
		}

		if (wt_lj_phase == 1)
		{
			// Watch_Scan's pass one for one stage: `stagepost` then the closing
			// `stage`/`end`, and the `stage` records around it for an old file.
			if (c != 115 && c != 101)           // 's' 'e'
				continue;
			n = tokenize(s);
			seg = wt_lj_leg - 1;
			if (argv(0) == "stagepost")
			{
				wt_lj_wseg = (n >= 3) ? stof(argv(1)) : -1;
				wt_lj_wdur = stof(argv(2));
				continue;
			}
			k = -1;
			if (argv(0) == "end")
			{
				k = stof(argv(1));
				wt_lj_end = k;
				// `end <ticks> <samples> <pad> <cps>` is the trailer, and a seg-0
				// window ends at it (Watch_StageSpan).  Patch 441: into the job's
				// own, not the open replay's finish tick.
				wt_lj_endt = k;
			}
			else if (argv(0) == "stage")
			if (n >= 3)
			{
				k = stof(argv(2));
				if (stof(argv(1)) == seg)
					wt_lj_sa = k;
				if (stof(argv(1)) == seg + 1)
				if (wt_lj_sb < 0)
					wt_lj_sb = k;
				/*
				  AND THE EVENT TABLE Watch_StageSpan reads, filled here because
				  pass one is the only place this job sees the `stage` records.
				  Every stage event, not just the asked-for pair: the finder walks
				  seg and seg+1 itself, and a table holding only this leg's two
				  would answer "no window" for any other.
				  Patch 441: the job's table (src 1), not the replay's.
				*/
				if (wt_lj_evn < WT_EVMAX)
				{
					wt_lj_evseg [wt_lj_evn] = stof(argv(1));
					wt_lj_evtick[wt_lj_evn] = k;
					wt_lj_evn = wt_lj_evn + 1;
				}
			}
			if (k >= 0)
			if (wt_lj_wseg >= 0)
			{
				if (wt_lj_wseg == seg)
				{
					wt_lj_pa = k - wt_lj_wdur;
					wt_lj_pb = k;
				}
				wt_lj_wseg = -1;
			}
			continue;
		}

		// Pass two.  A record marks the pair it sits in (Watch_RecordBits).
		if (c != 45 && (c < 48 || c > 57))
		{
			k = Watch_RecordBits(s);
			if (k & WTR_FORCE) wt_lj_frc  = TRUE;
			if (k & WTR_VETO)  wt_lj_veto = TRUE;
			if (k & WTR_RIDE)  wt_lj_ride = (k & WTR_RIDEON) ? TRUE : FALSE;
			continue;
		}
		t = stof(s);
		if (t < wt_lj_ta)
		{
			wt_lj_frc = wt_lj_veto = FALSE;
			continue;
		}
		tokenize(s);
		o = [stof(argv(WT_C_ORG)), stof(argv(WT_C_ORG + 1)), stof(argv(WT_C_ORG + 2))];
		v = [stof(argv(WT_C_VEL)), stof(argv(WT_C_VEL + 1)), stof(argv(WT_C_VEL + 2))];
		brk = FALSE;
		if (wt_lj_c > 0)
		{
			dt = t - wt_lj_pt;
			if (wt_lj_frc)
				brk = TRUE;
			else if (dt > 0)
			if (!wt_lj_veto && !wt_lj_ride)
			if (Interp_Fit(wt_lj_po, wt_lj_pv, o, v, dt) == INTERP_SNAP)
				brk = TRUE;
		}
		Line_Add(wt_lj_slot, o, vlen([v_x, v_y, 0]), t, brk);
		wt_lj_c  = wt_lj_c + 1;
		wt_lj_pt = t;
		wt_lj_po = o;
		wt_lj_pv = v;
		wt_lj_frc = wt_lj_veto = FALSE;
		if (t > wt_lj_tb)
		{
			fseek(wt_lj_fh, fsize(wt_lj_fh));   // the window is closed: finish
			continue;
		}
	}
	return 0;
};

// Patch 432: the run line shows the cut; its colours span the stage itself (the
// lead-in and the pre-start pad left out).
void() Watch_LineRange =
{
	Line_Range(0, rec_wt_vt0, rec_wt_vt1, rec_wt_wincut ? rec_wt_wint0 : 0);
};

/*
  Put the .rec cursor on the sample with the largest t <= want.

  Forward from where it is when that is forward, which is every ordinary frame;
  otherwise back to the nearest index entry and forward from there.  Records in
  the stream are stepped over rather than counted.
*/
void(float want) Watch_RecSeek =
{
	local float i, j, t;
	local string s;

	if (rec_wt_rec < 1)
		return;

	/*
	  The nearest index entry at or before the target, and it is consulted on
	  EVERY seek rather than only on a backwards one.

	  A forward drag of the scrub bar is the case that makes that necessary: the
	  cursor is valid and behind the target, so a "walk forward from where we
	  are" would be right but would step through every sample in between -- five
	  thousand of them for a drag to the end, per frame, while the mouse is down.
	  Starting from the index bounds every seek in either direction to one stride,
	  which is twelve samples on a run this length.
	*/
	j = rec_wt_rec0;
	for (i = 0; i < rec_wt_ixn; i = i + 1)
		if (rec_wt_ixt[i] <= want)
			j = rec_wt_ixline[i];

	if (rec_wt_rcur < rec_wt_rec0)
		rec_wt_rcur = j;
	else
	{
		tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
		if (stof(argv(WT_C_T)) > want)
			rec_wt_rcur = j;             // the cursor is ahead: restart
		else if (j > rec_wt_rcur)
			rec_wt_rcur = j;             // the index is further along: skip to it
	}

	// Walk forward while the NEXT sample is still at or before `want`.
	while (1)
	{
		j = -1;
		for (i = rec_wt_rcur + 1; i < rec_wt_recn; i = i + 1)
		{
			s = bufstr_get(rec_wt_rec, i);
			if (Watch_IsSample(s))
			{
				j = i;
				break;
			}
		}
		if (j < 0)
			break;

		tokenize(bufstr_get(rec_wt_rec, j));
		t = stof(argv(WT_C_T));
		if (t > want)
			break;
		rec_wt_rcur = j;
	}

	// And find the one after it, which is the far end of the interpolation.
	rec_wt_rnext = -1;
	for (i = rec_wt_rcur + 1; i < rec_wt_recn; i = i + 1)
		if (Watch_IsSample(bufstr_get(rec_wt_rec, i)))
		{
			rec_wt_rnext = i;
			break;
		}
};

/*
  PATCH 379: .view angles on the knot map (the block over rec_wt_vkline).
  tau = cltime - off is formed per line, never T + off: both sit near the map's
  uptime, so the subtraction is exact, where T + off would round to float32's
  step there (0.24 ms after an hour).
*/
float(float c, float j) Watch_ViewTau =
{
	local float off;

	off = rec_wt_vkoff[j];
	if (j + 1 < rec_wt_vkn)
	if (!rec_wt_vkbrk[j + 1])
	if (rec_wt_vkc0[j + 1] > rec_wt_vkc0[j])
		off = off + (rec_wt_vkoff[j + 1] - off) * (c - rec_wt_vkc0[j])
		                                        / (rec_wt_vkc0[j + 1] - rec_wt_vkc0[j]);
	return c - off;
};

// The line after vj in its span, if any.  Its tau is stof of the line (cltime
// leads it); the angles are read once the bracket settles.
void() Watch_ViewNext =
{
	local float nl, nk;

	nl = rec_wt_vj + 1;
	nk = rec_wt_vjk;
	if (nl > rec_wt_vkend[nk])
	{
		rec_wt_vnl = -1;
		if (nk + 1 >= rec_wt_vkn)
			return;
		if (rec_wt_vkbrk[nk + 1])
			return;
		nk = nk + 1;
		nl = rec_wt_vkline[nk];
	}
	rec_wt_vnl = nl;
	rec_wt_vnk = nk;
	rec_wt_vnt = Watch_ViewTau(stof(bufstr_get(rec_wt_view, nl)), nk);
};

// Put vj on knot j's last indexed line at or before T, else its first line.
void(float j, float T) Watch_ViewStart =
{
	local float i, ln;

	ln = rec_wt_vkline[j];
	for (i = 0; i < rec_wt_vxn; i = i + 1)
	{
		if (rec_wt_vxline[i] > rec_wt_vkend[j])
			break;
		if (rec_wt_vxline[i] > ln)
		if (Watch_ViewTau(rec_wt_vxc[i], j) <= T)
			ln = rec_wt_vxline[i];
	}
	rec_wt_vj   = ln;
	rec_wt_vjk  = j;
	rec_wt_vjt  = Watch_ViewTau(stof(bufstr_get(rec_wt_view, ln)), j);
	rec_wt_vjl  = -1;
	rec_wt_vnal = -1;
	Watch_ViewNext();
};

/*
  Pitch, yaw and keys for rec_wt_time from the .view; FALSE where no knot covers
  it (the approach, a ghost window, a gap), and the caller uses the .rec.  A knot
  is held 2 ticks past its edges.  Keys come from line vj.
*/
float() Watch_ViewAngles =
{
	local float T, j, f;
	local vector ang;

	T = rec_wt_time;
	if (rec_wt_view < 1 || rec_wt_vkn < 1 || T < 0)
		return FALSE;

	j = rec_wt_vkc;
	if (j >= rec_wt_vkn)
		j = 0;
	while (j + 1 < rec_wt_vkn)
	{
		if (rec_wt_vkc0[j + 1] - rec_wt_vkoff[j + 1] > T)
			break;
		j = j + 1;
	}
	while (j > 0)
	{
		if (rec_wt_vkc0[j] - rec_wt_vkoff[j] <= T)
			break;
		j = j - 1;
	}
	rec_wt_vkc = j;

	if (T < rec_wt_vkc0[j] - rec_wt_vkoff[j] - 2 * rec_wt_tickrate)
		return FALSE;
	if (T > rec_wt_vkc1[j] - rec_wt_vkoff[j] + 2 * rec_wt_tickrate)
	{
		if (j + 1 >= rec_wt_vkn)
			return FALSE;
		if (rec_wt_vkbrk[j + 1])
			return FALSE;
	}

	// Walk on from the cursor when it is in knot j, or in the same span's j-1
	// and not past T; otherwise start over inside knot j.
	if (rec_wt_vj < 0)
		Watch_ViewStart(j, T);
	else if (rec_wt_vjk != j && (rec_wt_vjk != j - 1 || rec_wt_vkbrk[j]))
		Watch_ViewStart(j, T);
	else if (rec_wt_vjt > T && rec_wt_vj != rec_wt_vkline[rec_wt_vjk])
		Watch_ViewStart(j, T);

	while (rec_wt_vnl >= 0)
	{
		if (rec_wt_vnt > T)
			break;
		rec_wt_vj  = rec_wt_vnl;
		rec_wt_vjk = rec_wt_vnk;
		rec_wt_vjt = rec_wt_vnt;
		if (rec_wt_vnal == rec_wt_vnl)
		{
			rec_wt_vja    = rec_wt_vna;
			rec_wt_vjkeys = rec_wt_vnkeys;
			rec_wt_vjl    = rec_wt_vj;
		}
		Watch_ViewNext();
	}

	if (rec_wt_vjl != rec_wt_vj)
	{
		tokenize(bufstr_get(rec_wt_view, rec_wt_vj));
		rec_wt_vja    = [stof(argv(WT_V_PITCH)), stof(argv(WT_V_YAW)), 0];
		rec_wt_vjkeys = stof(argv(WT_V_KEYS));
		rec_wt_vjl    = rec_wt_vj;
	}
	if (rec_wt_vnl >= 0)
	if (rec_wt_vnal != rec_wt_vnl)
	{
		tokenize(bufstr_get(rec_wt_view, rec_wt_vnl));
		rec_wt_vna    = [stof(argv(WT_V_PITCH)), stof(argv(WT_V_YAW)), 0];
		rec_wt_vnkeys = stof(argv(WT_V_KEYS));
		rec_wt_vnal   = rec_wt_vnl;
	}

	ang = rec_wt_vja;
	if (rec_wt_vnl >= 0)
	if (fabs(Interp_Arc(rec_wt_vja_x, rec_wt_vna_x)) <= WT_ASNAP)
	if (fabs(Interp_Arc(rec_wt_vja_y, rec_wt_vna_y)) <= WT_ASNAP)
	{
		f = 0;
		if (rec_wt_vnt > rec_wt_vjt)
			f = (T - rec_wt_vjt) / (rec_wt_vnt - rec_wt_vjt);
		if (f < 0) f = 0;
		if (f > 1) f = 1;
		ang = Interp_View(rec_wt_vja, rec_wt_vna, f);
	}
	rec_wt_pitch = ang_x;
	rec_wt_yaw   = Interp_Wrap(ang_y);
	rec_wt_keys  = rec_wt_vjkeys;
	rec_wt_psrel = (rec_wt_vjkeys & FSI_PSREL) ? TRUE : FALSE;
	return TRUE;
};

// The recording's frame rate at the cursor, for `run fps now`.
float() Watch_ViewHz =
{
	if (!rec_wt_asrc || rec_wt_vnl < 0)
		return 0;
	if (rec_wt_vnt <= rec_wt_vjt)
		return 0;
	return 1 / (rec_wt_vnt - rec_wt_vjt);
};

/*
  Rebuild the split list for a playback position.

  Wholesale rather than incrementally, because a scrub can move the clock in
  either direction by any amount and an edge detector run backwards would push a
  row for every stage the run had not reached yet.  Each row's speed and energy
  come from the .rec at THAT ROW'S OWN tick, which is why Timer_SplitsPushAt
  exists -- sampling them here would stamp twelve rows with the speed at the
  seek target.
*/
void(float ntick) Watch_Splits =
{
	local float i, save_r, save_n, sp, en, gravity, fin;
	local vector o, v;

	// Nothing to do on the common case: playing forward with no new event.
	// The finish row is tracked separately because it is not one of them -- the
	// clock passing the end changes nothing about the event count, so testing
	// that alone would mean the finish row could never appear.
	i = 0;
	for (; i < rec_wt_evn; i = i + 1)
		if (rec_wt_evtick[i] > ntick)
			break;

	fin = FALSE;
	if (rec_wt_endticks > 0)
	if (!rec_wt_abandon)                // Patch 395: an abandoned run never finished
	if (ntick >= rec_wt_endticks)
		fin = TRUE;

	if (i == rec_wt_evshown)
	if (fin == rec_wt_evfin)
		return;

	save_r = rec_wt_rcur;
	save_n = rec_wt_rnext;

	gravity = serverkeyfloat("sv_gravity");
	if (gravity < 1) gravity = 800;

	Timer_SplitsClear();
	rec_wt_evshown = i;
	rec_wt_evfin   = fin;

	for (i = 0; i < rec_wt_evshown; i = i + 1)
	{
		Watch_RecSeek(rec_wt_evtick[i] * rec_wt_tickrate);
		if (rec_wt_rcur < rec_wt_rec0)
			continue;

		tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
		o_x = stof(argv(WT_C_ORG + 0));
		o_y = stof(argv(WT_C_ORG + 1));
		o_z = stof(argv(WT_C_ORG + 2));
		v_x = stof(argv(WT_C_VEL + 0));
		v_y = stof(argv(WT_C_VEL + 1));
		v_z = stof(argv(WT_C_VEL + 2));

		sp = vlen([v_x, v_y, 0]);

		/*
		  BUILD 39: RELATIVE, like the live path, because it is the same column.

		  HUD_SplitSample pushes Strafe_Energy(...) - HUD_EnergyRef() and this
		  pushed the raw absolute, into rows Timer_SplitsPushAt shares between
		  them.  Same list, same label, two different quantities -- a replay's
		  split energies were larger than the live ones by the whole height of
		  the anchor, which on a descending map is most of the map.

		  WHAT THIS APPROXIMATES, said out loud.  Watch_Splits rebuilds the whole
		  list at the CURRENT playback position, so every row gets the reference
		  in force now rather than the one in force at its own tick.  At
		  hud_energy_ref 0 the anchor is the leg's start zone and that is exact
		  for a whole leg.  At 1 it is the last jump and it is not, and the
		  honest reading of the column becomes "energy above the reference you
		  are looking at".  Replaying the anchor machine forward to each row's
		  tick means a second driver for HUD_UpdateJumpRef, which is more
		  machinery than this bug is worth.
		*/
		en = Strafe_Energy(o, v, gravity) - HUD_EnergyRef();

		// Zero delta: the archive holds one PB per leg and no per-split table,
		// so there is nothing on disk to compare a replayed split against.  A
		// row with no delta draws its own time, which is the honest answer.
		Timer_SplitsPushAt(rec_wt_evkind[i], rec_wt_evseg[i],
		                   rec_wt_evtick[i], 0, sp, en);
	}

	// The finish row, once the clock is past the end.
	if (fin)
	{
		Watch_RecSeek(rec_wt_t1);
		if (rec_wt_rcur >= rec_wt_rec0)
		{
			tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
			o_x = stof(argv(WT_C_ORG + 0));
			o_y = stof(argv(WT_C_ORG + 1));
			o_z = stof(argv(WT_C_ORG + 2));
			v_x = stof(argv(WT_C_VEL + 0));
			v_y = stof(argv(WT_C_VEL + 1));
			v_z = stof(argv(WT_C_VEL + 2));
			Timer_SplitsPushAt(SPK_FINISH, -1, rec_wt_endticks, 0,
			                   vlen([v_x, v_y, 0]),
			                   // Build 39: relative, like every other row -- see above.
			                   Strafe_Energy(o, v, gravity) - HUD_EnergyRef());
		}
	}

	rec_wt_rcur  = save_r;
	rec_wt_rnext = save_n;
};

/*
===========================================================================
  The segment column and the board readout

  Everything here is a TABLE LOOKUP at draw time.  The work happened once, in
  Watch_BuildSeq, for the reason the file header gives: the machine that produces
  these rows is an accumulator and a scrub runs its clock backwards.
===========================================================================
*/

/*
  Called from inside Seq_Push during the build pass -- see the hook there.

  `merged` means Seq_Push rewrote the last row rather than appending one, which
  from outside is indistinguishable from a scroll (seq_n moves for neither).  The
  history mirrors that by stepping back one and rewriting, so a merged ramp is
  one entry here exactly as it is one row there.
*/
void(float merged) Watch_SeqRow =
{
	local float p;

	if (seq_n < 1)
		return;
	p = seq_n - 1;

	if (merged)
	if (rec_wt_sqn > 0)
		rec_wt_sqn = rec_wt_sqn - 1;

	if (rec_wt_sqn >= WT_SQMAX)
		return;

	rec_wt_sqkind[rec_wt_sqn] = seq_kind[p];
	rec_wt_sqgain[rec_wt_sqn] = seq_gain[p];
	rec_wt_sqde  [rec_wt_sqn] = seq_de[p];
	rec_wt_sqemax[rec_wt_sqn] = seq_emax[p];
	rec_wt_sqdur [rec_wt_sqn] = seq_dur[p];
	rec_wt_sqpct [rec_wt_sqn] = seq_pct[p];
	rec_wt_sqlau [rec_wt_sqn] = seq_launch[p];
	rec_wt_sqtick[rec_wt_sqn] = rec_wt_sqbuildtick;
	// Patch 343.  Read from row p like every column above, which is what makes a
	// MERGE right for free: the decrement above points rec_wt_sqn back at the row
	// being rewritten, and Seq_Push has already put the later half's answer in
	// seq_eend[p] / seq_sub[p] (both are plain assignments there, not sums).
	rec_wt_sqeend[rec_wt_sqn] = seq_eend[p];
	rec_wt_sqsub [rec_wt_sqn] = seq_sub[p];
	rec_wt_sqn = rec_wt_sqn + 1;
};

// Put the player's own column somewhere safe, and give it back.  Its own arrays
// rather than seq_mk_*; see the declaration for why that is not tidiness.
void() Watch_SeqSave =
{
	local float i;

	if (rec_wt_svheld)
		return;                     // already out; a second replay must not eat it

	rec_wt_svn         = seq_n;
	rec_wt_svhaslaunch = seq_haslaunch;
	for (i = 0; i < seq_n; i = i + 1)
	{
		rec_wt_svkind[i] = seq_kind[i];
		rec_wt_svgain[i] = seq_gain[i];
		rec_wt_svde  [i] = seq_de[i];
		rec_wt_svemax[i] = seq_emax[i];
		rec_wt_svdur [i] = seq_dur[i];
		rec_wt_svpct [i] = seq_pct[i];
		rec_wt_svlau [i] = seq_launch[i];
		rec_wt_sveend[i] = seq_eend[i];         // build 86, and see the decls
		rec_wt_svsub [i] = seq_sub[i];
		rec_wt_sveref[i] = seq_eref[i];
	}
	rec_wt_svheld = TRUE;
};

void() Watch_SeqRestore =
{
	local float i;

	if (!rec_wt_svheld)
		return;
	rec_wt_svheld = FALSE;

	seq_n         = rec_wt_svn;
	seq_haslaunch = rec_wt_svhaslaunch;
	seq_fadeat    = 0;
	for (i = 0; i < rec_wt_svn; i = i + 1)
	{
		seq_kind[i]   = rec_wt_svkind[i];
		seq_gain[i]   = rec_wt_svgain[i];
		seq_de[i]     = rec_wt_svde[i];
		seq_emax[i]   = rec_wt_svemax[i];
		seq_dur[i]    = rec_wt_svdur[i];
		seq_pct[i]    = rec_wt_svpct[i];
		seq_launch[i] = rec_wt_svlau[i];
		seq_eend[i]   = rec_wt_sveend[i];       // build 86, and see the decls
		seq_sub[i]    = rec_wt_svsub[i];
		seq_eref[i]   = rec_wt_sveref[i];
	}

	/*
	  Consumed, exactly as Seq_Unmark consumes it and for the same reason: the
	  player's timer has been running the whole time the replay was up, so the
	  next Seq_Frame would see a state change it never saw the start of and read
	  it as a new run -- taking the list we just restored straight back off.
	*/
	seq_laststate = getstatf(STAT_FS_TIMERSTATE);

	// The open segment belongs to a machine that has not run for however long the
	// replay was up, and its e0 was measured before it.  Same call a save-load
	// makes, for the same reason.
	Board_Warped();
};

/*
  Run the REAL segment machine over the file, once.

  Not a second copy of Board_Frame -- that is the thing that rots, and this
  project has said so about the HUD twice already.  The overrides in cl_board.qc
  exist so that one implementation can be fed from two places.

  WALKED LINEARLY rather than through the coarse index, because a `board` record
  is written immediately BEFORE the sample of the tick it happened on and the
  machine needs them in that order.  The file is already in memory; this is one
  tokenize per line and about six thousand of them on an eighty-second run.

  Only for v4.  A v3 file has no ramp contact to feed it, and running the machine
  on `riding = 0` would produce a column of pure air rows -- confidently wrong,
  which is worse than the empty column build 23 shipped.
*/
void() Watch_BuildSeq =
{
	local float i, fl, n, t;
	local vector org, vel;
	local string s;

	rec_wt_sqn      = 0;
	rec_wt_sqshown  = -1;
	rec_wt_bdshown  = -2;            // -1 is "before the first board", a real state

	if (!rec_wt_v4 || rec_wt_rec < 1)
		return;

	Watch_SeqSave();

	rec_wt_build   = TRUE;
	board_ov_seq  = 0;
	board_ov_bnorm = board_ov_bvel = '0 0 0';
	board_ov_now  = rec_wt_bt0;
	board_now     = rec_wt_bt0;

	// Patch 431: over Watch_ScanRange's range.  A cut takes the board in force at
	// its first sample from the table (its record may be lines before).
	if (rec_wt_bt0 > rec_wt_t0)
	{
		t = stof(bufstr_get(rec_wt_rec, rec_wt_bline));
		for (i = 0; i < rec_wt_bdn_n; i = i + 1)
		{
			if (rec_wt_bdt[i] >= t)
				break;
			board_ov_seq   = rec_wt_bdc[i];
			board_ov_bnorm = rec_wt_bdn[i];
			board_ov_bvel  = rec_wt_bdv[i];
		}
	}

	// Board_ResetRun and NOT Board_Clear: the latter also invalidates the
	// save-lock snapshot, which belongs to the player's own save and has nothing
	// to do with the file being read.  See the split in cl_board.qc.
	Board_ResetRun();

	for (i = rec_wt_bline; i < rec_wt_recn; i = i + 1)
	{
		s = bufstr_get(rec_wt_rec, i);

		if (!Watch_IsSample(s))
		{
			if (substring(s, 0, 6) == "board ")
			{
				n = tokenize(s);
				if (n >= 9)
				{
					board_ov_seq   = stof(argv(2));
					board_ov_bnorm = [stof(argv(3)), stof(argv(4)), stof(argv(5))];
					board_ov_bvel  = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
				}
			}
			continue;
		}

		tokenize(s);
		board_ov_now    = stof(argv(WT_C_T));
		fl              = stof(argv(WT_C_FLAGS));
		board_ov_riding = (fl & WT_F_RAMP) ? TRUE : FALSE;

		org = [stof(argv(WT_C_ORG + 0)), stof(argv(WT_C_ORG + 1)),
		       stof(argv(WT_C_ORG + 2))];
		vel = [stof(argv(WT_C_VEL + 0)), stof(argv(WT_C_VEL + 1)),
		       stof(argv(WT_C_VEL + 2))];

		// The tick a row pushed on this sample belongs to.  Below zero it is
		// padding, which the clock has not started for; clamped so the whole
		// approach reads as tick 0 rather than as negative ticks the split list
		// and the scrub bar would have to special-case.
		rec_wt_sqbuildtick = floor(board_ov_now / rec_wt_tickrate);
		if (rec_wt_sqbuildtick < 0)
			rec_wt_sqbuildtick = 0;

		Board_Frame(org, vel, (fl & WT_F_ONGROUND) ? TRUE : FALSE);
		if (board_ov_now > rec_wt_bt1)
			break;                  // Patch 431: the sample that closes the range
	}

	rec_wt_build = FALSE;

	/*
	  BUILD 25: how many ramp-contact gaps the hold bridged over this whole file.

	  Captured HERE rather than read live, because ramp_bridged goes on being
	  written by the player's own frames the moment the pass ends.  This is the
	  file's number and it has to stay the file's number.

	  It is also the only headless evidence that Board_RampHold does anything at
	  all: two files that differ only in whether the ramp bit drops out produce
	  the SAME column either way -- with the hold because the ride is never split,
	  without it because every fragment falls under SEG_MINTIME and the carry and
	  the merge reassemble it.  Same rows, opposite reasons.  This number is what
	  separates them.
	*/
	rec_wt_bridged = ramp_bridged;

	// The build left the ring holding the END of the run.  The draw path fills it
	// from the history for whatever tick the clock is on, so leave it empty
	// rather than showing the finish before the replay has started.
	Seq_Clear();

	if (rec_wt_bdover > 0)
		print(sprintf("^3replay: %g board record(s) past the %g cap were dropped; "
		              "the segment column ends early\n", rec_wt_bdover, WT_BDMAX));
};

/*
  The column, as of `ticks`.  A rebuild rather than a nudge, which is what makes
  a backwards scrub free -- and the same shape Watch_Splits already has.

  rec_wt_sqshown is the guard: at 300 fps the tick changes every fifth frame, and
  refilling seven arrays on the other four would be work for no change.
*/
void(float ticks) Watch_SeqApply =
{
	local float i, n, first, p;

	if (!rec_wt_v4)
		return;

	n = 0;
	for (i = 0; i < rec_wt_sqn; i = i + 1)
	{
		if (rec_wt_sqtick[i] > ticks)
			break;
		n = i + 1;
	}

	if (n == rec_wt_sqshown)
		return;
	rec_wt_sqshown = n;

	// The ring shows the last SEQ_MAX, which is what it would have been showing
	// at this point in the run.
	first = n - SEQ_MAX;
	if (first < 0)
		first = 0;

	seq_n         = n - first;
	seq_haslaunch = FALSE;
	seq_fadeat    = 0;

	for (i = 0; i < seq_n; i = i + 1)
	{
		p = first + i;
		seq_kind[i]   = rec_wt_sqkind[p];
		seq_gain[i]   = rec_wt_sqgain[p];
		seq_de[i]     = rec_wt_sqde[p];
		seq_emax[i]   = rec_wt_sqemax[p];
		seq_dur[i]    = rec_wt_sqdur[p];
		seq_pct[i]    = rec_wt_sqpct[p];
		seq_launch[i] = rec_wt_sqlau[p];
		if (seq_launch[i])
			seq_haslaunch = TRUE;
		// Patch 343: the row's own absolute and its Jump/Bhop word, from the file
		// rather than from whatever the build pass left in the live ring.
		seq_eend[i]   = rec_wt_sqeend[p];
		seq_sub[i]    = rec_wt_sqsub[p];
		/*
		  BUILD 86: a replay's rows are stamped with the LIVE reference, which is
		  the same approximation -- and the same reasoning -- Watch_Splits already
		  applies to the split column's energies a few hundred lines up: replaying
		  the anchor machine forward to each row's tick means a second driver for
		  HUD_UpdateJumpRef, which is more machinery than this is worth.

		  So the ABSOLUTE is the file's and the ZERO is the viewer's. That pairing
		  is exact at hud_energy_ref 0, where the anchor is the leg's start zone
		  and does not move; at 1 it is the last jump and the column reads "energy
		  above the reference you are looking at", which is the same honest
		  approximation the split list has made since build 39.
		*/
		seq_eref[i]   = HUD_EnergyRef();
	}

	/*
	  The one-line gain readout under the strafe bar is the newest row, and it is
	  set here rather than replayed from Board_SegmentEnd for the same reason the
	  column is: it is the last thing that FINISHED, and after a backwards scrub
	  that is a different row.  gain_time is in the .rec's own clock, which is
	  what Board_Alpha now fades against.
	*/
	if (n > 0)
	{
		p = n - 1;
		gain_kind  = rec_wt_sqkind[p];
		gain_speed = rec_wt_sqgain[p];
		gain_de    = rec_wt_sqde[p];
		gain_dur   = rec_wt_sqdur[p];
		gain_time  = rec_wt_sqtick[p] * rec_wt_tickrate;
	}
	else
	{
		gain_kind = SEG_NONE;
		gain_time = 0;
	}

	/*
	  BUILD 34: no live row in a replay.

	  Board_Frame does not run during playback -- HUD_Draw gates it on !rec_wt_on --
	  so seg_live_* would otherwise still hold whatever segment the player happened
	  to be riding when they opened the replay, and the column would draw a
	  provisional pair under a run that is not theirs and is not moving.

	  The scrubbed column is the ring and only the ring, which is also what makes
	  it match the column that was watched live: every row in it is a row that
	  Board_SegmentEnd committed.
	*/
	seg_live_kind = 0;
	seg_live_de   = 0;
	seg_live_dur  = 0;
};

/*
  The board readout, as of the playback clock.

  Board_Compute is a pure function of the plane and the pre-clip velocity -- it
  writes the board_* globals and reads nothing else -- so running it on the newest
  event at or before the clock reproduces the panel exactly, including on a
  backwards scrub, which simply lands on an earlier event.
*/
void() Watch_BoardApply =
{
	local float i, k;

	if (!rec_wt_v4)
		return;

	k = -1;
	for (i = 0; i < rec_wt_bdn_n; i = i + 1)
	{
		if (rec_wt_bdt[i] > rec_wt_time)
			break;
		k = i;
	}

	if (k == rec_wt_bdshown)
		return;
	rec_wt_bdshown = k;

	if (k < 0)
	{
		board_time = 0;             // nothing has been boarded yet; the row is blank
		leave_time = 0;
		return;
	}

	// board_now is the stamp Board_Compute takes board_time from, and the draw
	// path has already set it to the playback clock.  Set explicitly here so the
	// board is stamped with the moment it HAPPENED rather than with now.
	board_now = rec_wt_bdt[k];
	Board_Compute(rec_wt_bdv[k], rec_wt_bdn[k]);
	board_now = rec_wt_time;

	// `leaving` has no record of its own -- it is the falling edge of ramp
	// contact, which the sample stream carries -- and reproducing it would want a
	// second table for one row.  Left blank rather than stale: a leave speed from
	// somewhere else in the run is a wrong number in a slot that keeps its place.
	leave_time = 0;
};

void(float t) Watch_Seek =
{
	if (t < rec_wt_vt0) t = rec_wt_vt0;
	if (t > rec_wt_vt1) t = rec_wt_vt1;
	rec_wt_time = t;

	// A seek can go either way, so every cursor is invalidated rather than
	// nudged.  Watch_RecSeek notices it is ahead of the target and restarts from
	// the index; the rest restart from zero or from their own index.
	rec_wt_ccur    = -1;             // Patch 379: the parse cache and its cursors
	rec_wt_snc     = 0;
	rec_wt_dkc     = 0;
	rec_wt_vkc     = 0;
	rec_wt_vj      = -1;
	rec_wt_evshown = -1;             // force Watch_Splits to rebuild
	rec_wt_evfin   = -1;
	rec_wt_sqshown = -1;             // and the segment column with it
	rec_wt_bdshown = -2;
};

/*
  PATCH 379: tokenize rcur and rnext once per interval, and decide there what
  the interval is drawn with: SNAP from the load table, else Interp_Fit, with
  a vetoed snap and a hull change (the 8.5 u air shift) drawn LINEAR.
*/
void() Watch_Parse =
{
	local float snap;

	rec_wt_ccur  = rec_wt_rcur;
	rec_wt_cnext = rec_wt_rnext;

	tokenize(bufstr_get(rec_wt_rec, rec_wt_rcur));
	rec_wt_cta   = stof(argv(WT_C_T));
	rec_wt_ca    = [stof(argv(WT_C_ORG)), stof(argv(WT_C_ORG + 1)),
	                stof(argv(WT_C_ORG + 2))];
	rec_wt_cva   = [stof(argv(WT_C_VEL)), stof(argv(WT_C_VEL + 1)),
	                stof(argv(WT_C_VEL + 2))];
	rec_wt_cpa   = [stof(argv(WT_C_PITCH)), stof(argv(WT_C_YAW)), 0];
	rec_wt_cfla  = stof(argv(WT_C_FLAGS));
	rec_wt_ckeys = stof(argv(WT_C_KEYS));
	rec_wt_cnorm = '0 0 1';
	rec_wt_cmv   = '0 0 0';
	if (rec_wt_v4)
	{
		rec_wt_cnorm = [stof(argv(WT_C_NORM)), stof(argv(WT_C_NORM + 1)),
		                stof(argv(WT_C_NORM + 2))];
		rec_wt_cmv   = [stof(argv(WT_C_MOVE)), stof(argv(WT_C_MOVE + 1)), 0];
	}

	rec_wt_ctb  = rec_wt_cta;
	rec_wt_cb   = rec_wt_ca;
	rec_wt_cvb  = rec_wt_cva;
	rec_wt_cpb  = rec_wt_cpa;
	rec_wt_cflb = rec_wt_cfla;
	if (rec_wt_rnext >= rec_wt_rec0)
	{
		tokenize(bufstr_get(rec_wt_rec, rec_wt_rnext));
		rec_wt_ctb  = stof(argv(WT_C_T));
		rec_wt_cb   = [stof(argv(WT_C_ORG)), stof(argv(WT_C_ORG + 1)),
		               stof(argv(WT_C_ORG + 2))];
		rec_wt_cvb  = [stof(argv(WT_C_VEL)), stof(argv(WT_C_VEL + 1)),
		               stof(argv(WT_C_VEL + 2))];
		rec_wt_cpb  = [stof(argv(WT_C_PITCH)), stof(argv(WT_C_YAW)), 0];
		rec_wt_cflb = stof(argv(WT_C_FLAGS));
	}

	rec_wt_cfit = INTERP_LINEAR;
	if (rec_wt_ctb > rec_wt_cta)
	{
		if (rec_wt_snc > 0)
		if (rec_wt_snt[rec_wt_snc - 1] >= rec_wt_cta)
			rec_wt_snc = 0;
		while (rec_wt_snc < rec_wt_snn)
		{
			if (rec_wt_snt[rec_wt_snc] >= rec_wt_cta)
				break;
			rec_wt_snc = rec_wt_snc + 1;
		}
		snap = FALSE;
		if (rec_wt_snc < rec_wt_snn)
		if (rec_wt_snt[rec_wt_snc] == rec_wt_cta)
			snap = TRUE;
		if (snap)
			rec_wt_cfit = INTERP_SNAP;
		else
		{
			rec_wt_cfit = Interp_Fit(rec_wt_ca, rec_wt_cva, rec_wt_cb, rec_wt_cvb,
			                         rec_wt_ctb - rec_wt_cta);
			if (rec_wt_cfit == INTERP_SNAP)
				rec_wt_cfit = INTERP_LINEAR;
			if ((rec_wt_cfla & WT_F_DUCKED) != (rec_wt_cflb & WT_F_DUCKED))
				rec_wt_cfit = INTERP_LINEAR;
		}
	}

	// The duck fraction at ta: a slide covering ta (ending exactly on it counts),
	// else the hull bit.
	if (rec_wt_dkc > 0)
	if (rec_wt_dke[rec_wt_dkc - 1] >= rec_wt_cta)
		rec_wt_dkc = 0;
	while (rec_wt_dkc < rec_wt_dkn)
	{
		if (rec_wt_dke[rec_wt_dkc] >= rec_wt_cta)
			break;
		rec_wt_dkc = rec_wt_dkc + 1;
	}
	rec_wt_cfa = (rec_wt_cfla & WT_F_DUCKED) ? 1 : 0;
	if (rec_wt_dkc < rec_wt_dkn)
	if (rec_wt_dks[rec_wt_dkc] <= rec_wt_cta)
		rec_wt_cfa = Interp_Smooth(rec_wt_dku[rec_wt_dkc]
		                           + (rec_wt_cta - rec_wt_dks[rec_wt_dkc])
		                             * rec_wt_dkr[rec_wt_dkc]);
};

/*
  Fill the override block for this frame.

  Interpolated BY TIMESTAMP rather than by index -- a sample is written per
  received packet, and measured rates are 65, 64.6 and 43.5/s against a nominal
  66.67.  PATCH 379: the feet follow the interval's verdict (Watch_Parse): a
  Hermite through both samples' recorded velocities, a lerp, or on a snap a jump
  at the midpoint with each half moving at its own sample's velocity.  The eye
  follows the duck-slide table.  Angles come from the .view on the knot map
  where a knot covers T (Watch_ViewAngles), else from the .rec pair on the
  shortest arc, holding either side of a snap or a step over WT_ASNAP.
*/
void() Watch_Sample =
{
	local float t, tick, i, s, dt, f, db, reseek;
	local vector fwd, rgt, ang;

	// Inside the interval already parsed: no seek and no tokenize.
	reseek = TRUE;
	if (rec_wt_ccur >= rec_wt_rec0)
	if (rec_wt_ccur == rec_wt_rcur)
	if (rec_wt_time >= rec_wt_cta)
	if (rec_wt_time < rec_wt_ctb || rec_wt_cnext < rec_wt_rec0)
		reseek = FALSE;
	if (reseek)
	{
		Watch_RecSeek(rec_wt_time);
		if (rec_wt_rcur < rec_wt_rec0)
			return;
		if (rec_wt_rcur != rec_wt_ccur || rec_wt_rnext != rec_wt_cnext)
			Watch_Parse();
	}

	s  = 0;
	dt = rec_wt_ctb - rec_wt_cta;
	if (dt > 0)
	{
		s = (rec_wt_time - rec_wt_cta) / dt;
		if (s < 0) s = 0;
		if (s > 1) s = 1;
	}

	if (dt <= 0)
		rec_wt_org = rec_wt_ca;
	else if (rec_wt_cfit == INTERP_SNAP)
	{
		if (s < 0.5)
			rec_wt_org = rec_wt_ca + rec_wt_cva * (rec_wt_time - rec_wt_cta);
		else
			rec_wt_org = rec_wt_cb - rec_wt_cvb * (rec_wt_ctb - rec_wt_time);
	}
	else if (rec_wt_cfit == INTERP_HERMITE)
		rec_wt_org = Interp_Hermite(rec_wt_ca, rec_wt_cva, rec_wt_cb, rec_wt_cvb, dt, s);
	else
		rec_wt_org = rec_wt_ca + (rec_wt_cb - rec_wt_ca) * s;
	rec_wt_vel      = rec_wt_cva + (rec_wt_cvb - rec_wt_cva) * s;
	rec_wt_onground = (rec_wt_cfla & WT_F_ONGROUND) ? TRUE : FALSE;
	rec_wt_ducked   = (rec_wt_cfla & WT_F_DUCKED)   ? TRUE : FALSE;
	rec_wt_fit      = rec_wt_cfit;

	// The eye: a slide covering T, else from ta's fraction to rnext's hull bit
	// across the interval (an air duck: the head drops 8.5 u, as it did).
	db = (rec_wt_cflb & WT_F_DUCKED) ? 1 : 0;
	f  = -1;
	for (i = rec_wt_dkc; i < rec_wt_dkn; i = i + 1)
	{
		if (rec_wt_dks[i] > rec_wt_time)
			break;
		if (rec_wt_dke[i] >= rec_wt_time)
		{
			f = Interp_Smooth(rec_wt_dku[i] + (rec_wt_time - rec_wt_dks[i]) * rec_wt_dkr[i]);
			break;
		}
	}
	if (f < 0)
		f = rec_wt_cfa + (db - rec_wt_cfa) * s;
	rec_wt_eyeh = rec_wt_vh + (rec_wt_dvh - rec_wt_vh) * f;

	/*
	  v4: the plane, the ramp contact and the wishdir, all from rcur and not
	  interpolated: the plane is a direction (a lerp of two normals is neither
	  unit nor on the short arc) and changes discontinuously at a ramp edge.
	*/
	rec_wt_gnorm = rec_wt_cnorm;
	rec_wt_rc    = FALSE;
	if (rec_wt_v4)
		rec_wt_rc = (rec_wt_cfla & WT_F_RAMP) ? TRUE : FALSE;

	/*
	  ---- the angles and the keys ------------------------------------------

	  Before t = 0 the sidecar has no lines (it opens on the TF_RECORDING edge),
	  but the .rec's pad has carried real per-tick angles since build 18
	  (SV_RecPad), so the approach and a file with no .view use the .rec's
	  columns: tick-rate, 0.1 degree, no +left/+right and no FSI_PSREL.  Their
	  yaw may be written 270 against -89.5 (the first pad sample after a spawn);
	  Interp_View takes the shortest arc and wraps, so HUD_UpdateTurn never sees
	  a 359.5-degree turn.
	*/
	tick = rec_wt_time / rec_wt_tickrate;
	if (tick < 0)
		tick = 0;

	rec_wt_keys  = 0;
	rec_wt_psrel = FALSE;
	rec_wt_asrc  = Watch_ViewAngles();
	if (!rec_wt_asrc)
	{
		if (rec_wt_cfit == INTERP_SNAP
		 || fabs(Interp_Arc(rec_wt_cpa_x, rec_wt_cpb_x)) > WT_ASNAP
		 || fabs(Interp_Arc(rec_wt_cpa_y, rec_wt_cpb_y)) > WT_ASNAP)
		{
			if (s < 0.5)
				ang = rec_wt_cpa;
			else
				ang = rec_wt_cpb;
		}
		else
			ang = Interp_View(rec_wt_cpa, rec_wt_cpb, s);
		rec_wt_pitch = Interp_Wrap(ang_x);
		rec_wt_yaw   = Interp_Wrap(ang_y);
		rec_wt_keys  = rec_wt_ckeys;
	}

	/*
	  The wishdir, the way AirMove builds it: the usercmd's forward and side
	  against the .rec's yaw (the angle the server simulated the tick with, not
	  the finer .view one), flattened BEFORE normalising.  input_movevalues is
	  zeroed while a replay is up, so it is rebuilt here.
	*/
	rec_wt_wish = '0 0 0';
	if (rec_wt_v4)
	if (rec_wt_cmv_x != 0 || rec_wt_cmv_y != 0)
	{
		makevectors([0, rec_wt_cpa_y, 0]);
		fwd = v_forward;  fwd_z = 0;
		rgt = v_right;    rgt_z = 0;
		if (vlen(fwd) > 0.001) fwd = normalize(fwd);
		if (vlen(rgt) > 0.001) rgt = normalize(rgt);
		rec_wt_wish = fwd * rec_wt_cmv_x + rgt * rec_wt_cmv_y;
		rec_wt_wish_z = 0;
		if (vlen(rec_wt_wish) < 0.001)
			rec_wt_wish = '0 0 0';
		else
			rec_wt_wish = normalize(rec_wt_wish);
	}

	// ---- the clock -------------------------------------------------------
	t = floor(tick);
	if (t < 0) t = 0;
	if (rec_wt_endticks > 0)
	if (t > rec_wt_endticks)
		t = rec_wt_endticks;
	rec_wt_ticks = t;

	if (rec_wt_time < 0)
		rec_wt_state = TS_ARMED;
	else if (rec_wt_endticks > 0 && t >= rec_wt_endticks && !rec_wt_abandon)
		rec_wt_state = TS_FINISHED;
	else
		rec_wt_state = TS_RUNNING;

	/*
	  The flags the panel may draw.

	  TF_RECORDING and TF_FROZEN are masked out because neither is a fact about
	  the run -- one says a buffer was open and the other says a save-lock was
	  being held at that instant, and both would put a word on the panel that is
	  about the recording rather than about what is on screen.

	  A file with no `flags` key is a pre-build-24 recording, and rather than
	  invent an answer the tag is used: a personal best cannot be a practice run,
	  and a shadow run is one by definition.  Anything else reads clean-unknown.
	*/
	// BUILD 44: the two class bits join the mask.  They are facts about the run
	// exactly as TF_PRACTICE is -- the panel's `format` row and the timer's
	// sub-label both read this word through FS_RunClass, and a bit masked out
	// here would silently demote a cheated replay to `stitched`.
	if (rec_wt_recflags >= 0)
		rec_wt_flags = rec_wt_recflags &
		              (TF_PRACTICE | TF_SHADOW | TF_SEGMENT | TF_CHEAT);
	else if (rec_wt_tag == RT_SHADOW)
		rec_wt_flags = TF_PRACTICE | TF_SHADOW;
	else if (rec_wt_tag == RT_CHEAT)
		// Unreachable today -- nothing writes this name without also writing a
		// v4 header -- and kept in step with cl_scores.qc's identical fallback
		// so the panel and the board cannot disagree about one file.
		rec_wt_flags = TF_PRACTICE | TF_CHEAT;
	else
		rec_wt_flags = 0;

	rec_wt_pb   = 0;
	rec_wt_seg  = rec_wt_startseg;
	for (i = 0; i < rec_wt_evn; i = i + 1)
		if (rec_wt_evkind[i] == SPK_STAGE)
		if (rec_wt_evtick[i] <= rec_wt_ticks)
			rec_wt_seg = rec_wt_evseg[i];

	Watch_Splits(rec_wt_ticks);
	Watch_SeqApply(rec_wt_ticks);
	Watch_BoardApply();
};

/*
===========================================================================
  The path.  Patch 432: slot 0 of the run lines (cl_lines.qc), every sample of
  the built range, broken at teleports.

    hud_watch_path_mode 2   screen space, after renderscene (the default): a
                            1 px anti-aliased strip that shows through walls.
    hud_watch_path_mode 1   build 26's world ribbon, queued before renderscene
                            and depth-tested; mitred, its width a fixed angle
                            (hud_watch_path_width at 512 u, _scale 0 for world).

  An untextured 2D polygon's shader has no `cull` line and so culls one winding
  (r_2d.c, gl_shader.c); every 2D polygon here is TWOSIDED, and
  hud_watch_path_probe 1-5 draws the five primitives that diagnosed it (4, the
  old winding without the flag, must not draw).  `replay status` prints what
  the last frame drew.
===========================================================================
*/

// The side offset at one vertex: half the width, perpendicular to both the
// averaged direction and the line of sight.
vector(vector prev, vector p, vector next, vector eye, float wid) Watch_Side =
{
	local vector din, dout, dir, look;

	din  = p - prev;
	dout = next - p;

	if (din  != '0 0 0') din  = normalize(din);
	if (dout != '0 0 0') dout = normalize(dout);

	dir = din + dout;
	if (dir == '0 0 0')
		dir = (dout != '0 0 0') ? dout : din;
	if (dir == '0 0 0')
		return '0 0 0';
	dir = normalize(dir);

	look = p - eye;
	if (look == '0 0 0')
		return '0 0 0';

	return normalize(crossproduct(dir, normalize(look))) * (wid * 0.5);
};

// The ribbon's width at one vertex (a fixed angle, clamped near and far).
float(vector p, vector eye, float base, float scaled) Watch_Wid =
{
	local float w;

	if (!scaled)
		return base;

	w = base * (vlen(p - eye) / 512);
	if (w < base * 0.35) w = base * 0.35;
	if (w > base * 6)    w = base * 6;
	return w;
};

float() Watch_PathMode =
{
	local float m;

	// Registered with a default of 2, but a cvar read before its registercvar
	// returns "" -- and "" is 0, which is "off", which would look exactly like
	// the feature having been removed.
	m = cvar("hud_watch_path_mode");
	if (m <= 0)
	if (cvar_string("hud_watch_path_mode") == "")
		m = 2;

	return m;
};

void() Watch_Path =
{
	local float i, j, k, ib, st, wid, ahead, scaled, a0, a1, brk;
	local vector eye, c0, c1, s0, s1, p0, p1, pin;

	if (!cvar("hud_watch_path"))
		return;
	if (!ln_on[0])
		return;

	if (Watch_PathMode() != 1)
	{
		/*
		  Mode 2 draws after renderscene, but its projection is pinned here:
		  cs_buildmatricies is lazy and renderscene rewrites r_refdef.vrect (render
		  scale, portals), so the first project() of the frame must come before it.
		  The probe 256 u ahead lands mid-screen if the matrix is the scene's;
		  Watch_Path2D takes it again after, and `replay status` prints both.
		*/
		if (Watch_PathMode() == 2)
		{
			makevectors(getproperty(VF_ANGLES));
			pin = getproperty(VF_ORIGIN) + v_forward * 256;
			rec_wt_p2pre = project(pin);
		}
		return;
	}

	// Mode 1: every st-th point (about 2000 drawn), a ring per quad (a fan), each
	// vertex computed once and shared by the two quads beside it.
	eye    = getproperty(VF_ORIGIN);
	wid    = cvar("hud_watch_path_width");
	ahead  = cvar("hud_watch_path_ahead");
	scaled = cvar("hud_watch_path_scale");
	Line_ViewFrame();
	i  = ln_ia[0];
	ib = ln_ib[0];
	if (ib <= i)
		return;
	st = max(1, ceil((ib - i) / 2000));
	p0 = ln_pos[i];
	c0 = ln_col[i];
	a0 = (ln_t[i] <= rec_wt_time) ? 1 : 0.5;
	s0 = Watch_Side(p0, p0, ln_pos[min(i + st, ib)], eye, Watch_Wid(p0, eye, wid, scaled));
	while (i < ib)
	{
		j = min(i + st, ib);
		brk = FALSE;
		for (k = i + 1; k <= j; k = k + 1)
			if (ln_brk[k])
				brk = TRUE;
		p1 = ln_pos[j];
		s1 = Watch_Side(p0, p1, ln_pos[min(j + st, ib)], eye, Watch_Wid(p1, eye, wid, scaled));
		c1 = ln_col[j];
		a1 = (ln_t[j] <= rec_wt_time) ? 1 : 0.5;
		// A teleport, the part ahead when it is off, a degenerate side, or the eye
		// inside 48 u (a quad with no facing plane smears across the screen).
		if (!brk)
		if (ahead || a0 >= 1 || a1 >= 1)
		if (s0 != '0 0 0' && s1 != '0 0 0')
		if (vlen(p0 - eye) >= 48 && vlen(p1 - eye) >= 48)
		{
			R_BeginPolygon("");
			R_PolygonVertex(p0 - s0, '0 0 0', c0, a0);
			R_PolygonVertex(p0 + s0, '0 0 0', c0, a0);
			R_PolygonVertex(p1 + s1, '0 0 0', c1, a1);
			R_PolygonVertex(p1 - s1, '0 0 0', c1, a1);
			R_EndPolygon();
		}
		p0 = p1;  s0 = s1;  c0 = c1;  a0 = a1;
		i = j;
	}
};

void() Watch_Path2D =
{
	local float t;
	local vector eye, fwd, q0;

	rec_wt_p2n    = 0;
	rec_wt_p2clip = 0;
	rec_wt_p2wild = 0;

	if (!cvar("hud_watch_path"))
		return;
	if (Watch_PathMode() != 2)
		return;
	if (!ln_on[0])
		return;

	// The other half of the probe (see Watch_Path), and two off-axis points: a
	// centre probe cannot fail, 64 u right and up must land right and above it.
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	rec_wt_p2post = project(eye + fwd * 256);
	rec_wt_p2axr = project(eye + fwd * 256 + v_right * 64);
	rec_wt_p2axu = project(eye + fwd * 256 + v_up * 64);

	// hud_watch_path_probe: 1 a quad through the path's calls, 2 drawline, 3 drawfill
	// (the control), 4 the quad wound backwards (must NOT draw), 5 that with TWOSIDED.
	// A literal centre: a getproperty() scaled implicitly casts and lands at 0,0.
	t = cvar("hud_watch_path_probe");
	if (t == 1)
	{
		// A literal, not a derived centre: getproperty returns __variant and
		// scaling it implicitly casts to float, which put the square at 0,0 and
		// made a working probe look like a broken one.
		q0 = '400 300 0';
		R_BeginPolygon("", 0, TRUE);
		R_PolygonVertex(q0 + '-100 -100 0', '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 -100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 100 0',   '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '-100 100 0',  '0 0 0', '1 0 1', 1);
		R_EndPolygon();
	}
	else if (t == 2)
		drawline(4, '400 300 0', '900 700 0', '1 0 1', 1, 0);
	else if (t == 3)
		drawfill('400 300 0', '200 200 0', '1 0 1', 1, 0);
	else if (t == 4)
	{
		q0 = '400 300 0';
		R_BeginPolygon("", 0, TRUE);
		R_PolygonVertex(q0 + '-100 100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 100 0',   '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 -100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '-100 -100 0', '0 0 0', '1 0 1', 1);
		R_EndPolygon();
	}
	else if (t == 5)
	{
		q0 = '400 300 0';
		R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
		R_PolygonVertex(q0 + '-100 100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 100 0',   '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '100 -100 0',  '0 0 0', '1 0 1', 1);
		R_PolygonVertex(q0 + '-100 -100 0', '0 0 0', '1 0 1', 1);
		R_EndPolygon();
	}

	ln_frames = ln_frames + 1;
	Line_ViewFrame();
	Line_StatsReset();
	Line_Draw(0, rec_wt_time, rec_wt_org, cvar("hud_watch_path_ahead") ? 0.5 : 0, 1);

	// `replay bench <n>`: the draw n more times in this frame, unprofiled (gettime(1)
	// counts whole ms, so n draws make the resolution 1/n ms).
	rec_wt_p2pts = ln_npt;
	if (rec_wt_bench > 0)
	{
		rec_wt_bench = min(rec_wt_bench, floor(1000000 / max(1, ln_npt)));
		q0_x = gettime(1);
		for (t = 0; t < rec_wt_bench; t = t + 1)
			Line_Draw(0, rec_wt_time, rec_wt_org, cvar("hud_watch_path_ahead") ? 0.5 : 0, 1);
		q0_y = (gettime(1) - q0_x) * 1000;
		print(sprintf("replay: bench %g draws %.0f ms = %.3f ms each (%g pts, %g segs)\n",
		              rec_wt_bench, q0_y, q0_y / rec_wt_bench, ln_npt / (rec_wt_bench + 1),
		              ln_nseg / (rec_wt_bench + 1)));
		rec_wt_bench = 0;
	}
	rec_wt_p2n     = ln_nseg;
	rec_wt_p2clip  = ln_nclip;
	rec_wt_p2wild  = ln_nwild;
	rec_wt_p2first = ln_first;
	rec_wt_p2min   = ln_bbmin;
	rec_wt_p2max   = ln_bbmax;
};

// The camera origin; `replay trace` prints this, so it is what was drawn.
// Patch 379: rec_wt_eyeh slides with the duck (Watch_Sample).
vector() Watch_Eye =
{
	return rec_wt_org + [0, 0, rec_wt_eyeh];
};

void() Watch_Camera =
{
	local vector eye;

	eye = Watch_Eye();
	setproperty(VF_ORIGIN, eye);
	setproperty(VF_ANGLES, [rec_wt_pitch, rec_wt_yaw, 0]);

	/*
	  BUILD 43: and TELL THE SERVER, which is the one thing this function used to
	  do that nothing else could and did not do.  Not so the server can move
	  anything -- it still knows nothing about the recording -- but so the
	  entities it decides to send are the ones in front of the camera rather than
	  the ones in front of a body standing where you pressed the key.  Throttled
	  in PVS_Publish; see the essay there and the measurement in sv_saveloc.qc.

	  Here, at the single site the camera origin exists, rather than in
	  Watch_Frame: a seek, a scrub and an ordinary frame all arrive through this
	  function, so there is no path that moves the camera without publishing it.
	*/
	PVS_Publish(eye);
};

void() Watch_Stop =
{
	if (!rec_wt_open)
		return;

	rec_wt_open = FALSE;
	rec_wt_on   = FALSE;
	Watch_Free();
	Timer_SplitsClear();

	// The player's own segment column, back where it was.  Before the print, so
	// that a restore that faults says so with the stop line still to come.
	Watch_SeqRestore();

	/*
	  BUILD 47: ONLY IF NOTHING ELSE STILL WANTS THE CURSOR.

	  This was an unconditional release and it was not carelessness -- it was
	  unwritable.  rec_sb_open lived in cl_scores.qc, which compiles AFTER this
	  file, so the test could not be spelled here at all.  Build 47 moved that
	  declaration up to cl_hud.qc, beside ui_he_open, which is the same thing
	  done for the same reason; see the block there.

	  The sequence it cost is the one Scores_Close calls ordinary: open the
	  board, click a row to watch it, stop the replay -- and the cursor went back
	  to the game underneath a board that was still drawn, with nothing able to
	  press anything on it.  The only way out was to guess that ESC still worked.

	  All three panels now ask the same question at the one place each lets go.

	  BUILD 55: there were FOUR by then, and this site could not test the
	  fourth either.  ui_rs_cursor (the results card) is declared at
	  cl_results.qc:58, which also compiles after this file -- so the same
	  constraint that made rec_sb_open unwritable in build 47 was still hiding
	  the card.  Moving one more declaration up would have worked once more and
	  then broken again on the fifth owner, so the question itself moved
	  instead: see the cursor claim register in cl_hud.qc.
	*/
	UI_CursorRelease(UIC_WATCH);
	localcmd("cmd rec_watch 0\n");
	print("replay: stopped\n");
};

/*
  Open a recording.

  The .view is found by replacing the extension, which is the whole of the
  relationship between the two files -- they are joined by nothing but their
  names, which is exactly why build 23 moved the naming to one function in
  shared/sh_defs.qc.  A missing sidecar is not fatal: the .rec's own angle
  columns are a coarser camera and a partial replay beats a refused one.
*/
float(float seg) Watch_WindowFind;     // Patch 431, below

float(string path) Watch_Open =
{
	local float buf, leg;
	local string vp;

	leg = rec_wt_wantleg;           // Patch 431: taken whatever happens below
	rec_wt_wantleg = 0;

	// Patch 385: the server refuses the pin under spectate (a pending one too), and
	// both would own the camera.
	if (Spec_Active())
	{
		print("^3replay:^7 stop spectating first\n");
		return FALSE;
	}

	rec_wt_loadms = gettime(1);
	Watch_Free();

	if (strstrofs(path, ".rec") < 0)
	{
		print(sprintf("replay: %s is not a .rec\n", path));
		return FALSE;
	}

	buf = buf_create_ex("string", 0);
	if (buf < 1)
	{
		print("replay: buf_create failed\n");
		return FALSE;
	}
	if (!Watch_BufLoad(path, buf))
	{
		buf_del(buf);
		print(sprintf("replay: cannot read %s\n", path));
		return FALSE;
	}
	rec_wt_rec  = buf;
	rec_wt_recn = buf_getsize(buf);
	rec_wt_path = strzone(path);

	vp = strcat(substring(path, 0, strlen(path) - 4), ".view");
	buf = 0;
	if (rec_wt_noview)
		print("replay: noview -- the sidecar is not loaded\n");
	else
		buf = buf_create_ex("string", 0);
	if (buf >= 1)
	{
		if (Watch_BufLoad(vp, buf))
		{
			rec_wt_view  = buf;
			rec_wt_viewn = buf_getsize(buf);
		}
		else
		{
			buf_del(buf);
			print(sprintf("replay: no sidecar at %s -- "
			              "angles will be tick-rate and the turn keys are lost\n", vp));
		}
	}

	// The tag, from the name.  Only used as the fallback for a file with no
	// `flags` header key; see Watch_Sample.
	//
	// The archived two match on `_<tag>.rec` because a stamp always precedes
	// them.  `cheat` is unstamped, so its whole basename is the tag and the '/'
	// is what an underscore is for the others -- matching on "cheat.rec" alone
	// would also fire on a leg folder somebody named `cheat`.
	rec_wt_tag = RT_LAST;
	if (strstrofs(path, "_pb.rec") >= 0)     rec_wt_tag = RT_PB;
	if (strstrofs(path, "_shadow.rec") >= 0) rec_wt_tag = RT_SHADOW;
	if (strstrofs(path, "/cheat.rec") >= 0)  rec_wt_tag = RT_CHEAT;

	Watch_Scan();

	if (rec_wt_nsamp < 2)
	{
		print(sprintf("replay: %s holds %g samples -- nothing to play\n",
		              path, rec_wt_nsamp));
		Watch_Free();
		return FALSE;
	}

	if (rec_wt_map != "")
	if (rec_wt_map != serverkey("map"))
		print(sprintf("^3replay: this run is on %s and you are on %s -- "
		              "the camera will fly through nothing\n",
		              rec_wt_map, serverkey("map")));

	rec_wt_segs   = Watch_TrackSegs(rec_wt_track);
	rec_wt_vt0    = rec_wt_t0;
	rec_wt_vt1    = rec_wt_t1;
	rec_wt_winseg = -1;
	if (leg > 0)
		Watch_WindowFind(leg - 1);
	rec_wt_rate   = 1;
	rec_wt_slider = 0.5;
	rec_wt_paused = FALSE;
	rec_wt_rcur   = -1;
	rec_wt_lastreal = cltime;
	rec_wt_clkerr   = 0;
	rec_wt_open   = TRUE;

	// The passes that cost anything at load, and between them the reason both a
	// scrub and a frame are cheap: the drawn curve and the segment column are
	// tables by the time anything asks for them.  Patch 431: over the cut only.
	Watch_ScanRange(rec_wt_vt0, rec_wt_vt1);
	Watch_LineRange();
	Watch_BuildSeq();
	rec_wt_loadms = (gettime(1) - rec_wt_loadms) * 1000;
	print(sprintf("replay: opened in %.0f ms (view map %.0f ms)\n",
	              rec_wt_loadms, rec_wt_vmapms));

	if (!rec_wt_v4)
		print("^3replay: this recording is FTESURF-REC 3 -- no ramp contact and no "
		      "pre-clip velocity, so the strafe bar, the board panel and the "
		      "segment column stay off.  Runs recorded from build 24 carry them.\n");

	Watch_Seek(rec_wt_vt0);
	if (rec_wt_winseg >= 0)
		print(sprintf("replay: stage %g window %.4f..%.4f s from %.4f (ticks %g..%g, %s)\n",
		              rec_wt_winseg + 1, rec_wt_wint0, rec_wt_wint1, rec_wt_time,
		              rec_wt_wina, rec_wt_winb, rec_wt_winhow));

	// Pin the player.  MOVETYPE_NONE maps to PM_NONE, which is what stops the
	// CLIENT predicting as well as the server moving -- build 11's finding.  The
	// input gate in CSQC_Input_Frame covers the round trip until this lands.
	localcmd("cmd rec_watch 1\n");
	// Build 43: so the first Watch_Camera publishes immediately rather than
	// waiting out a throttle window seeded by the last replay this session.
	PVS_Forget();
	UI_CursorClaim(UIC_WATCH);

	print(sprintf("replay: %s  %s  %s  %g samples%s\n",
	              rec_wt_path, rec_wt_owner,
	              Time_TickString(rec_wt_endticks, rec_wt_tickrate), rec_wt_nsamp,
	              rec_wt_abandon ? " (abandoned)" : ""));

	// Said once per replay rather than once per session, and only when it is
	// off: the panel is the answer to "what am I actually watching" and there
	// is no other route to knowing it exists.  See the chrome's hint line.
	if (!cvar("hud_watch_info"))
		print("        ^5hud_watch_info 1^7 for the run's frame rate, tick rate, "
		      "sample rate and file details\n");
	return TRUE;
};

/*
  Patch 395: stage `seg` (0-based) of the open file.  The window is the
  `stagepost` table from Watch_Scan, else the `stage` records around seg.
  Patch 431: found here and cut to (Watch_SetCut); Watch_Open calls it before
  anything per-sample is built, so a board row builds only its stage.
*/
float(float seg) Watch_WindowFind =
{
	local float a, b;

	rec_wt_winseg = -1;
	rec_wt_wincut = FALSE;
	a = b = -1;
	rec_wt_winhow = "stagepost";
	if (seg >= 0 && seg < WT_STGMAX)
	{
		a = rec_wt_pw0[seg];
		b = rec_wt_pw1[seg];
		if (a < 0)
		{
			rec_wt_winhow = "stage records";
			// Patch 441: the one spelling, shared with the board's line job.
			Watch_StageSpan(seg, 0);
			a = wt_ws_a;
			b = wt_ws_b;
		}
	}
	if (a < 0 || b <= a)
	{
		print(sprintf("replay: no window for stage %g in this file\n", seg + 1));
		return FALSE;
	}
	rec_wt_winseg = seg;
	rec_wt_wina   = a;
	rec_wt_winb   = b;
	rec_wt_wint0  = a * rec_wt_tickrate;
	rec_wt_wint1  = min(b * rec_wt_tickrate, rec_wt_t1);
	rec_wt_wincut = TRUE;
	rec_wt_vt0    = max(rec_wt_t0, rec_wt_wint0 - 1);
	rec_wt_vt1    = rec_wt_wint1;
	return TRUE;
};

/*
  Patch 431: the bar, seeks and playback cut to the window (from 1 s before its
  start), or the whole file back -- rebuilding the per-sample tables when what
  was built does not cover it.  Playback pauses at the cut's end.
*/
void(float on) Watch_SetCut =
{
	local float ms;

	rec_wt_wincut = (on && rec_wt_winseg >= 0);
	rec_wt_vt0 = rec_wt_t0;
	rec_wt_vt1 = rec_wt_t1;
	if (rec_wt_wincut)
	{
		rec_wt_vt0 = max(rec_wt_t0, rec_wt_wint0 - 1);
		rec_wt_vt1 = rec_wt_wint1;
	}
	if (rec_wt_vt0 < rec_wt_bt0 || rec_wt_vt1 > rec_wt_bt1)
	{
		ms = gettime(1);
		Watch_ScanRange(rec_wt_vt0, rec_wt_vt1);
		Watch_BuildSeq();
		print(sprintf("replay: built %.4f..%.4f in %.0f ms\n", rec_wt_vt0, rec_wt_vt1,
		              (gettime(1) - ms) * 1000));
	}
	Watch_LineRange();
	Watch_Seek(rec_wt_time);
};

// Patch 395: play stage `seg` from its start less 1 s, pausing at its end.
float(float seg) Watch_StageWindow =
{
	if (!rec_wt_open)
		return FALSE;
	if (!Watch_WindowFind(seg))
	{
		Watch_SetCut(FALSE);
		return FALSE;
	}
	Watch_SetCut(TRUE);
	Watch_Seek(rec_wt_vt0);
	rec_wt_paused = FALSE;
	print(sprintf("replay: stage %g window %.4f..%.4f s from %.4f (ticks %g..%g, %s)\n",
	              seg + 1, rec_wt_wint0, rec_wt_wint1, rec_wt_time, rec_wt_wina,
	              rec_wt_winb, rec_wt_winhow));
	return TRUE;
};

/*
===========================================================================
  The chrome
===========================================================================
*/
void(float v) Watch_ScrubTo =
{
	Watch_Seek(rec_wt_vt0 + v * (rec_wt_vt1 - rec_wt_vt0));
};

/*
  The speed slider is 0..1 and 1x is the MIDDLE, which is what was asked for and
  is not what a linear 0.1..4 gives -- that would put 1x at 0.23.  So the two
  halves are separate ranges, 0.1..1 below the centre and 1..4 above it, with a
  dead zone either side of 0.5 so the natural place to let go is exactly 1x.
*/
void(float v) Watch_SetSpeed =
{
	if (v > 0.47)
	if (v < 0.53)
		v = 0.5;

	rec_wt_slider = v;

	if (v <= 0.5)
		rec_wt_rate = 0.1 + (v / 0.5) * 0.9;
	else
		rec_wt_rate = 1 + ((v - 0.5) / 0.5) * 3;
};

// The same setting from the other end: a console `replay speed 2` means two
// times, not slider position 2.  Inverting the two halves keeps the knob and
// the command describing one value rather than two that drift.
void(float r) Watch_SetRate =
{
	if (r < 0.1) r = 0.1;
	if (r > 4)   r = 4;

	rec_wt_rate = r;
	if (r <= 1)
		rec_wt_slider = ((r - 0.1) / 0.9) * 0.5;
	else
		rec_wt_slider = 0.5 + ((r - 1) / 3) * 0.5;
};

/*
  The chrome, and every number in it is DERIVED.

  Build 24's first cut hardcoded a 46-pixel panel and drew the hint line at
  `small - 1`, and both were wrong for the same underlying reason: the text
  scales with hud_scale and the box did not.  At hud_scale 2 the hint ran out
  through the bottom border, and `small - 1` was a size one pixel off whichever
  rung Font_Px had just snapped to -- which is not a smaller font, it is the same
  font resampled by 0.94, sitting next to crisp text that makes it obvious.  That
  is the exact defect build 21 found in HUD_DrawSeq and wrote a ladder essay
  about; it went straight back in here because these constants were typed rather
  than measured.

  So: two font sizes, both snapped, and every vertical is a sum of those two plus
  named padding.  The panel's height is what its contents came to.

  THE MONO FACE, WHICH IS THE GOOGLE ONE ON DISK.  gfx/fonts/GoogleMed.ttf is
  Google Sans Code Medium and every glyph in it advances exactly 0.6 em -- see
  the ladder essay in sh_font.qc.  For a panel whose entire top line is a CLOCK
  that is not a preference: with a proportional face the elapsed time shifts
  sideways as the digits change under it, and at 1x that is a readout that
  jitters four times a second.  Fixed pitch also makes the width of a line
  computable from its character count, which is what lets the layout below fit
  itself to the window instead of hoping.
*/
#define WT_PAD   10                 // panel edge to content, both axes
#define WT_GAP    6                 // between the three rows

/*
  BUILD 34 -- THE PANEL IS MEASURED, AND IT SCALES.

      "when I pause the demo, the text in the demo player extends to the point
       where the word pause is off the UI.  can you extend the size of the demo
       player?"

  Two separate things, and the first one is the bug.

  THE WIDTH WAS A CHARACTER COUNT WITH A MAGIC NUMBER IN IT: (owner + 46) * cw.
  46 assumed a 34-character status line and reserved nothing at all for the close
  button or its gap.  The status line is 27 characters running and 35 PAUSED --
  and 37 past ten minutes, 41 past an hour, because Time_TickString grows a field
  at each.  At hud_scale 2 the paused string therefore overlapped the X by about
  30 px and at ten minutes ran 19 px past the border.  At hud_scale 1 the 380
  floor absorbed it, which is why this only ever showed up on a scaled HUD.

  It also asked for strlen(rec_wt_owner) while the title DRAWS "unknown" when that
  is empty, so a headerless .rec under-reserved by seven characters.

  Now both strings are built before the panel is sized and measured with
  stringwidth, so the panel fits what it is actually about to draw.  The mono
  face makes that identical to strlen*cw today (sh_font.qc's ladder essay), but
  it stops being an assumption -- and it lifts the "no colour codes in these
  values" constraint Watch_InfoRow carries for the same reason.

  hud_watch_scale is the second half: the panel and its text together, on top of
  hud_scale, because "bigger" was asked for separately from "not broken".
*/
void(vector scr) Watch_Chrome =
{
	local vector p, sz;
	local float w, h, y, sp, small, tiny, cw, bx, bw, sw, xs;
	local float wsc, pad, gap, wtitle, wclock, th, kw;
	local string s, stitle, sclock;
	local float i, xa, xb, skw, skx, skon;

	wsc = cvar("hud_watch_scale");
	if (wsc < 0.5) wsc = 0.5;       // below this the hint is unreadable anyway
	if (wsc > 4)   wsc = 4;         // above it the panel is wider than any window

	Font_Set(ui_font_mono);
	small = Font_Px(8 * ui_cv_scale * wsc);
	tiny  = Font_Px(7 * ui_cv_scale * wsc);
	cw    = small * 0.6;            // this face's advance, exactly
	pad   = floor(WT_PAD * wsc);    // panel edge to content
	gap   = floor(WT_GAP * wsc);    // between rows, and either side of the clock

	/*
	  The two strings the top row actually holds, built BEFORE the panel is sized.
	  The owner is spelled once, here, so the width and the draw cannot disagree
	  about whether it is "unknown".
	*/
	s = (rec_wt_owner != "") ? rec_wt_owner : "unknown";
	stitle = sprintf("%s   %s%s", s, Time_TickString(rec_wt_endticks, rec_wt_tickrate),
	                 rec_wt_abandon ? " (abandoned)" : "");
	sclock = sprintf("%s / %s   %.2fx%s",
	                 Time_TickString(rec_wt_ticks, rec_wt_tickrate),
	                 Time_TickString(rec_wt_endticks, rec_wt_tickrate),
	                 rec_wt_rate, rec_wt_paused ? "  paused" : "");
	// Patch 431: a cut reads in the stage's own time (negative in the lead-in).
	if (rec_wt_wincut)
	{
		stitle = sprintf("%s   stage %g", s, rec_wt_winseg + 1);
		sclock = sprintf("%s / %s   %.2fx%s",
		                 Time_TickString((rec_wt_time - rec_wt_wint0) / rec_wt_tickrate,
		                                 rec_wt_tickrate),
		                 Time_TickString((rec_wt_wint1 - rec_wt_wint0) / rec_wt_tickrate,
		                                 rec_wt_tickrate),
		                 rec_wt_rate, rec_wt_paused ? "  paused" : "");
	}

	wtitle = stringwidth(stitle, TRUE, [small, small]);
	wclock = stringwidth(sclock, TRUE, [small, small]);
	bw     = small + 4;             // the close button is square on the row height

	/*
	  The width the panel WANTS, and then what the window will give it: both
	  strings, the gap between them, the gap before the close button, and the
	  button.  Everything on the widest row, named rather than counted.
	*/
	w = pad * 2 + wtitle + gap + wclock + gap + bw;
	if (w < 380 * wsc) w = 380 * wsc;
	if (w > scr_x - 24) w = scr_x - 24;

	// Height: title, bar, hint, with a gap between each and padding top and
	// bottom.  The bar is the tallest of the three because it is a control.
	h = pad * 2 + small + gap + (small + 4) + gap + tiny;

	p  = [floor((scr_x - w) * 0.5), 12];
	sz = [w, h];

	// Published for Timer_DrawPanel, which is drawn EARLIER in the frame -- so
	// this is last frame's value and the timer settles one frame after a
	// hud_scale change.  Publishing it from here rather than recomputing the
	// layout twice is the same trade ui_strafe_bottom makes, and one frame of
	// a panel being 8 px out on a cvar change is not worth a second layout pass.
	rec_wt_chromebot = p_y + h;

	sui_fill(p, sz, '0.03 0.04 0.06', 0.88, 0);
	sui_border_box(p, sz, 1, '0.30 0.55 0.85', 0.9, 0);

	// --- the title line ---------------------------------------------------
	y  = p_y + pad;
	bx = p_x + w - pad - bw;

	drawstring([p_x + pad, y], stitle, [small, small], '0.90 0.93 0.98', 1, 0);

	/*
	  Where we are, against how long it is -- RIGHT-ALIGNED off the close button
	  rather than placed at 42% of the width.  A fraction of the width is a
	  guess about how long the owner's name is, and it was the reason this line
	  could collide with the title on a narrow window.

	  The floor is the title's MEASURED end plus a gap, not a second guess at how
	  long the owner's name is.  With the width above sized off the same two
	  measurements it cannot fire unless the window itself clamped the panel --
	  which is the one case where something has to give, and the title is the half
	  you can afford to lose the end of.
	*/
	xs = bx - gap - wclock;
	if (xs < p_x + pad + wtitle + gap)
		xs = p_x + pad + wtitle + gap;
	drawstring([xs, y], sclock, [small, small],
	           rec_wt_paused ? '1.00 0.82 0.20' : '0.65 0.70 0.78', 1, 0);

	// --- the close button, top right --------------------------------------
	sui_action_element([bx, y - 2], [bw, bw], "wt_x", sui_noop);
	if (sui_is_hovered("wt_x"))
		sui_fill([bx, y - 2], [bw, bw], '0.55 0.15 0.15', 1, 0);
	drawstring([bx + (bw - cw) * 0.5, y], "X", [small, small], '1 1 1', 1, 0);
	if (sui_is_released("wt_x"))
	{
		Watch_Stop();
		return;
	}

	// --- the scrub bar ----------------------------------------------------
	//
	// The speed slider is a fixed share of the width rather than a fixed 110
	// pixels: at hud_scale 2 on a 4K window 110 px is a knob you cannot hit, and
	// on a 720p window it was a third of the panel.
	y  = p_y + pad + small + gap;
	sw = w * 0.22;
	// Build 34: the clamps travel with hud_watch_scale too, or a scaled-up panel
	// gets the same 80px slider it had at 1x sitting in a much wider row.
	if (sw < 80 * wsc) sw = 80 * wsc;
	if (sw > 220 * wsc) sw = 220 * wsc;

	sp = (rec_wt_vt1 > rec_wt_vt0)
	   ? (rec_wt_time - rec_wt_vt0) / (rec_wt_vt1 - rec_wt_vt0) : 0;

	bw = w - pad * 2 - sw - gap * 2;      // the scrub bar's own width
	th = floor(6 * wsc);                  // the track's own thickness
	kw = floor(4 * wsc);                  // and the width of a slider knob

	sui_fill([p_x + pad, y + (small + 4) * 0.5 - th * 0.5], [bw, th],
	         '0.12 0.14 0.18', 1, 0);
	sui_fill([p_x + pad, y + (small + 4) * 0.5 - th * 0.5], [bw * sp, th],
	         '0.35 0.72 1.00', 1, 0);

	/*
	  The t = 0 mark: everything left of it is the approach the padding ring
	  kept, which is time the clock had not started for.

	  BUILD 26 -- IT IS DRAWN UNDER THE TRACK NOW, AND THIS WAS THE REPORT.

	  It used to be a two-pixel FULL-HEIGHT bar in bright amber, cutting through
	  the track at a FIXED position -- and it was the only thing on this bar
	  shaped like a handle, because the scrub bar had no playhead at all (see
	  below).  So the one control-looking object on the control never moved, and
	  it sits near the left end: on an 86s run with the usual 256-sample ring the
	  padding is 3.84s, i.e. 4.5% along, which reads as zero.  "The playback head
	  is stuck at 0" is exactly right about what it looks like and exactly wrong
	  about what it is.

	  So it becomes a gradation on the ruler rather than a control: three pixels
	  tall, hanging below the track, in the amber the timer already uses for a
	  clock that has not started.  It is still a fact worth marking -- it is
	  where the run's own clock begins -- and it is no longer competing with the
	  thing you grab.
	*/
	// Patch 431: in a cut the mark is the stage's start.
	xa = rec_wt_wincut ? rec_wt_wint0 : 0;
	if (rec_wt_vt0 < xa)
	if (rec_wt_vt1 > xa)
		sui_fill([p_x + pad + bw * ((xa - rec_wt_vt0) / (rec_wt_vt1 - rec_wt_vt0)) - kw * 0.5,
		          y + (small + 4) * 0.5 + th * 0.5 + 1],
		         [kw * 0.5, floor(3 * wsc)], '1.00 0.82 0.20', 0.9, 0);

	/*
	  THE DEAD AIR, IN RED.  Build 43.

	  ON the track and not below it, unlike the t=0 gradation above -- that one is
	  a single instant and wants to be a tick mark on a ruler, while these are
	  EXTENTS and want to read as parts of the run.  Drawn AFTER the progress fill
	  so a stretch is visible whether it has been played or not: the blue fill
	  would otherwise swallow every mark behind the playhead, which is exactly the
	  half you look at after a run to see where the time went.

	  0.9 rather than 1 so the blue still shows through faintly and the mark reads
	  as part of the bar rather than as a hole in it.

	  A run can legitimately have none of these, and most do; the loop then costs
	  one compare.  Clamped to the track at both ends because a stretch that runs
	  to the last sample would otherwise put half a pixel past the right edge.
	*/
	if (rec_wt_vt1 > rec_wt_vt0)
	for (i = 0; i < rec_wt_idn; i = i + 1)
	{
		if (rec_wt_idt1[i] < rec_wt_vt0 || rec_wt_idt0[i] > rec_wt_vt1)
			continue;                   // Patch 431: outside the cut
		xa = bw * (rec_wt_idt0[i] - rec_wt_vt0) / (rec_wt_vt1 - rec_wt_vt0);
		xb = bw * (rec_wt_idt1[i] - rec_wt_vt0) / (rec_wt_vt1 - rec_wt_vt0);
		xa = bound(0, xa, bw);
		xb = bound(0, xb, bw);
		// Never thinner than a pixel: a two-tick park is a real fact about the
		// run and a zero-width fill is not a mark.
		if (xb - xa < 1)
			xb = xa + 1;
		sui_fill([p_x + pad + xa, y + (small + 4) * 0.5 - th * 0.5],
		         [xb - xa, th], '0.85 0.25 0.25', 0.9, 0);
	}

	/*
	  THE PLAYHEAD, and there was not one.

	  sui_slidercontrol draws NOTHING -- it is sui_action_element plus the drag
	  and keyboard handling, and every caller draws its own track and its own
	  knob (sui_sys.qc:1140).  The speed slider beside this one does exactly that
	  four lines down; this one drew a track and a progress fill and stopped, so
	  the leading edge of the fill was the only indication of where you were and
	  there was nothing to aim a mouse at.

	  Drawn like the speed slider's knob, deliberately: same width, same full row
	  height, same near-white, so the two controls on this row look like the same
	  kind of object.  Clamped a knob's width inside either end so it is still
	  wholly on the bar at t0 and t1 rather than half outside the panel.
	*/
	sui_fill([p_x + pad + bound(0, bw * sp, bw) - kw * 0.5, y], [kw, small + 4],
	         '0.90 0.93 0.98', 1, 0);

	sui_slidercontrol("wt_scrub", [p_x + pad, y], [bw, small + 4],
	                  [0, 1, 0], sp, Watch_ScrubTo);

	// --- the speed slider -------------------------------------------------
	xs = p_x + w - pad - sw;
	sui_fill([xs, y + (small + 4) * 0.5 - th * 0.5], [sw, th], '0.12 0.14 0.18', 1, 0);
	sui_fill([xs + sw * 0.5 - kw * 0.25, y + 1], [kw * 0.5, small + 2],
	         '0.55 0.58 0.65', 1, 0);
	sui_fill([xs + sw * rec_wt_slider - kw * 0.5, y], [kw, small + 4],
	         '0.90 0.93 0.98', 1, 0);
	sui_slidercontrol("wt_speed", [xs, y], [sw, small + 4],
	                  [0, 1, 0], rec_wt_slider, Watch_SetSpeed);

	// --- the hint ---------------------------------------------------------
	//
	// Drawn at a SNAPPED size, and shortened when the window cannot hold the long
	// form.  A string that runs out of the box is worse than a shorter one.
	/*
	  BUILD 26 -- IT NAMES hud_watch_info, AND THAT IS THE WHOLE OF THAT REPORT.

	  The detail panel shipped in build 25 and was asked for again in build 26,
	  because it defaults to 0 and NOTHING anywhere said it existed: not this
	  line, not the console, not default.cfg's own section.  A feature nobody can
	  find has not shipped.  It is still off by default -- it covers a third of
	  the left edge -- but it is now one readable string away.
	*/
	y = p_y + h - pad - tiny;

	/*
	  THE SKIP TOGGLE, and why it is a visible control rather than only a cvar.

	  Build 25 shipped hud_watch_info defaulting to 0 with nothing anywhere
	  naming it; build 26 got the same feature reported as missing, and the note
	  that came out of it was "A feature nobody can find has not shipped."  A
	  switch that changes what playback DOES is a worse thing to hide than a
	  panel, so it gets a label you can click.

	  ON THE HINT ROW rather than the control row, which costs no layout change
	  at all: the row already exists, `h` is unchanged, and the hint beside it
	  simply measures itself against what is left.  Putting it on the scrub row
	  would have meant re-deriving bw and the two sliders around it.

	  It carries the COUNT because that is the fact the toggle is about -- "skip
	  still (3)" says both that the switch exists and that this particular run
	  has three stretches worth skipping, which the red on the bar above says in
	  the other direction.
	*/
	skon = cvar("hud_watch_skipidle");
	if (rec_wt_idn > 0)
		s = sprintf("skip still (%g)", rec_wt_idn);
	else
		s = "skip still";

	skw = stringwidth(s, TRUE, [tiny, tiny]) + pad;
	skx = p_x + w - pad - skw;

	sui_action_element([skx, y - 2], [skw, tiny + 4], "wt_skip", sui_noop);
	if (sui_is_hovered("wt_skip"))
		sui_fill([skx, y - 2], [skw, tiny + 4], '0.16 0.20 0.26', 1, 0);

	// Green only when it is both on AND has something to do.  On with nothing to
	// skip is a true statement about the switch and a misleading one about the
	// run, so it reads as dim -- the same distinction the KIND column makes
	// between "clean" and "--".
	drawstring([skx + pad * 0.5, y], s, [tiny, tiny],
	           (skon && rec_wt_idn > 0) ? '0.45 0.85 0.50' : '0.40 0.42 0.48', 1, 0);

	if (sui_is_released("wt_skip"))
		localcmd(skon ? "hud_watch_skipidle 0\n" : "hud_watch_skipidle 1\n");

	// Patch 431: a stage window's cut, and the way back to the whole run.
	if (rec_wt_winseg >= 0)
	{
		s = rec_wt_wincut ? "whole run" : sprintf("stage %g only", rec_wt_winseg + 1);
		xb = stringwidth(s, TRUE, [tiny, tiny]) + pad;
		skx = skx - gap - xb;
		skw = skw + gap + xb;
		sui_action_element([skx, y - 2], [xb, tiny + 4], "wt_cut", sui_noop);
		if (sui_is_hovered("wt_cut"))
			sui_fill([skx, y - 2], [xb, tiny + 4], '0.16 0.20 0.26', 1, 0);
		drawstring([skx + pad * 0.5, y], s, [tiny, tiny], '0.55 0.75 0.95', 1, 0);
		if (sui_is_released("wt_cut"))
			Watch_SetCut(!rec_wt_wincut);
	}

	s = "space pause   arrows seek 5s   drag to scrub   hud_watch_info 1   esc close";
	// Build 34: measured like everything else on the panel now.  This ladder was
	// already the only part that adapted to the width; it just did it by counting.
	// Build 43: measured against what the toggle left, not against the whole
	// row, or the long form runs under it on a narrow window.
	if (stringwidth(s, TRUE, [tiny, tiny]) > w - pad * 2 - skw - gap)
		s = "space  arrows  esc   hud_watch_info 1";
	if (stringwidth(s, TRUE, [tiny, tiny]) > w - pad * 2 - skw - gap)
		s = "space  arrows  esc";
	if (stringwidth(s, TRUE, [tiny, tiny]) > w - pad * 2 - skw - gap)
		s = "";
	drawstring([p_x + pad, y], s, [tiny, tiny], '0.45 0.48 0.55', 1, 0);

	Font_Reset();
};

/*
===========================================================================
  hud_watch_info -- WHAT THIS RECORDING ACTUALLY IS.  Build 25.

  Most of it is header keys and cursor state that `replay status` has printed
  since build 24, and repeating them on screen is worth doing only because of
  the three that are NOT in there and cannot usefully be:

  THE RUN'S OWN FRAME RATE, LIVE.  The .view sidecar is one line per RENDERED
  frame and the reader already brackets the two lines it is drawing between
  (Watch_ViewHz, Patch 379: one over their spacing on the knot map).  So that is
  the frame rate the run was actually being played at AT THIS MOMENT -- not an
  average over the file, which is a different and much less interesting number.
  Watch it against the scrub and you can see where the recording's own machine
  struggled.

  THE .rec's MEASURED SAMPLE RATE.  The nominal rate is 66.67, and the recorder's
  own comment measures 65, 64.6 and 43.5 on real files, because a sample is
  written per received PACKET and a packet can carry several usercmds.  Which of
  those you are watching decides how much of the smoothness is interpolation.

  AND THE VIEWER'S OWN FRAME RATE, so the two are distinguishable.  Without it,
  "the run was at 300" and "you are at 300" look like the same statement.

  DRAWN LEFT, UNDER THE CHROME.  rec_wt_chromebot is published by Watch_Chrome
  for exactly this kind of thing (Timer_DrawPanel already reads it), so the panel
  cannot land on top of the scrub bar at any hud_scale.
===========================================================================
*/
float rec_wt_fps;                // the VIEWER's frame rate, smoothed

/*
  HOW TALL THE PANEL IS, counted where the rows are rather than once at the top.

  Build 25 wrote `rows = 14` a hundred lines above the fourteen rows, and build
  26 adds five -- which is exactly the shape of the constant that goes stale.
  Four small numbers, each sitting immediately above the block it counts, is not
  self-deriving but it is countable on one screen, which the single 19 was not.
  Add a row, bump the number three lines above it.
*/
#define WT_INFO_FILE   7        // path, owner, format, map, tag, recorded, size
#define WT_INFO_RUN    5        // leg, time, tick, at, playback
#define WT_INFO_RATE   4        // run fps, your fps, rec rate, samples
#define WT_INFO_STATE  3        // ramp, rows, path

// One row: label left, value right-aligned inside the panel's width.
void(vector p, float w, float sz, float cw, string k, string v) Watch_InfoRow =
{
	drawstring([p_x, p_y], k, [sz, sz], '0.52 0.56 0.64', 1, 0);
	drawstring([p_x + w - strlen(v) * cw, p_y], v, [sz, sz], '0.86 0.90 0.96', 1, 0);
};

/*
  WHEN THIS RUN WAS RECORDED, out of the header key that already carries it.

  The .rec has no `created` key and does not need one: `runid` is
  strftime("%Y%m%d-%H%M%S") plus the slot (sv_timer.qc:1045), so the answer has
  been in every file since v3.  Sliced rather than parsed into numbers -- three
  stofs would be three ways to be wrong about a field whose only job is to be
  read by a person -- and refused outright below fifteen characters, because a
  runid from some other writer is not a date and must not be printed as one.
*/
string(string id) Watch_RunDate =
{
	if (strlen(id) < 15)
		return "--";
	return sprintf("%s-%s-%s %s:%s",
	               substring(id, 0, 4), substring(id, 4, 2), substring(id, 6, 2),
	               substring(id, 9, 2), substring(id, 11, 2));
};

void(vector scr) Watch_Info =
{
	local vector p;
	local float w, h, sz, cw, lh, y, rows;
	local float span, rechz, viewhz, livehz, tick;
	local string s;

	Font_Set(ui_font_mono);
	sz = Font_Px(7 * ui_cv_scale);
	cw = sz * 0.6;                  // GoogleMed advances 0.6em for every glyph
	lh = sz + 3 * ui_cv_scale;

	rows = WT_INFO_FILE + WT_INFO_RUN + WT_INFO_RATE + WT_INFO_STATE;
	w    = 34 * cw;                 // the widest row, in characters
	h    = WT_PAD * 2 + rows * lh;

	p = [12, rec_wt_chromebot + 10, 0];
	if (p_y + h > scr_y - 12)
		p_y = scr_y - 12 - h;       // a short window pushes it up rather than off

	sui_fill(p, [w + WT_PAD * 2, h], '0.03 0.04 0.06', 0.82, 0);
	sui_border_box(p, [w + WT_PAD * 2, h], 1, '0.30 0.55 0.85', 0.55, 0);

	p_x = p_x + WT_PAD;
	y   = p_y + WT_PAD;

	/*
	  The three rates.

	  span is the .rec's own, padding included, so rechz is measured over exactly
	  the samples the file holds rather than over the run clock -- a file with 256
	  samples of pre-start ring has a real 3.8s of them and they are real samples.

	  The .view's average is taken over the same span deliberately, even though
	  the sidecar has no coverage over the negative padding: the two numbers are
	  then in the same denominator and the ratio between them is the frames per
	  tick, which is the thing worth reading off two adjacent rows.  The live one
	  below is exact and is what to trust for a moment.
	*/
	span   = rec_wt_t1 - rec_wt_t0;
	rechz  = (span > 0.001) ? (rec_wt_nsamp / span) : 0;
	viewhz = (span > 0.001) ? ((rec_wt_viewn - rec_wt_view0) / span) : 0;

	tick   = rec_wt_tickrate;
	if (tick <= 0) tick = PM_TICK;
	livehz = Watch_ViewHz();

	s = rec_wt_path;
	if (strlen(s) > 34)
		s = substring(s, strlen(s) - 34, 34);
	Watch_InfoRow([p_x, y], w, sz, cw, "", s);                              y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "owner",
	              (rec_wt_owner != "") ? rec_wt_owner : "unknown");           y = y + lh;

	/*
	  What kind of run this is -- the same states the leaderboard shows, from the
	  same source.  A REC 3 file cannot answer (its header has no `flags` key),
	  and saying so is the point: the alternative is asserting one of the others,
	  which would be a guess about somebody's run.

	  BUILD 44: FOUR WORDS, FROM FS_RunClass.  This was a truth test on the whole
	  masked word, which was correct while the mask admitted only TF_PRACTICE and
	  TF_SHADOW and stops being correct the moment it admits anything else -- and
	  the mask two thousand lines up now admits two more bits.  A test that is
	  right because of what a distant line masks out is the shape of bug this
	  build is fixing one level up.  This is the second of the three readers the
	  shared classifier exists to keep in step; the third is cl_timer.qc's
	  sub-label, which this same panel draws through Timer_DrawPanel.
	*/
	if (!rec_wt_v4)             s = "rec3  unknown";
	else                       s = strcat("rec4  ",
	                                      FS_RunKindName(rec_wt_flags));
	Watch_InfoRow([p_x, y], w, sz, cw, "format", s);                        y = y + lh;

	/*
	  WHICH MAP, and whether it is the one under you.

	  Watch_Open already prints this as a console warning when they differ, and a
	  warning that scrolled past ten replays ago is not an answer to "why is the
	  camera flying through nothing".  Same comparison, on screen, permanently.

	  No colour code in it, deliberately: Watch_InfoRow right-aligns on
	  strlen(v) and a ^1 is two characters that occupy no width, so a coloured
	  value would sit four characters off the edge every other row.
	*/
	s = (rec_wt_map != "") ? rec_wt_map : "unknown";
	if (rec_wt_map != "")
	if (rec_wt_map != serverkey("map"))
		s = strcat(s, " (elsewhere)");
	Watch_InfoRow([p_x, y], w, sz, cw, "map", s);                           y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "tag", FS_TagName(rec_wt_tag));       y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "recorded",
	              Watch_RunDate(rec_wt_runid));                              y = y + lh;

	/*
	  How big the two files are, in LINES rather than bytes: buf_getsize is free
	  and a byte count would be a guess at the average line length of a format
	  whose lines vary by a factor of three.

	  These are whole-file counts and the `samples` row below is the payload, so
	  the difference between them is the header plus every split, checkpoint and
	  board record -- which is the one thing neither number says on its own.
	*/
	Watch_InfoRow([p_x, y], w, sz, cw, "file",
	              sprintf("%g rec  %g view lines",
	                      rec_wt_recn, rec_wt_viewn));                        y = y + lh;

	// Build 57: the LEG and the segment it began at, which stopped being one
	// number when stage 1 became a leg -- a stage-1 run and a full run both read
	// `seg 0`, and only `leg` tells them apart.
	Watch_InfoRow([p_x, y], w, sz, cw, "leg",
	              sprintf("track %g  leg %g  seg %g",
	                      rec_wt_track, rec_wt_leg, rec_wt_startseg));        y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "time",
	              sprintf("%s  %g ticks",
	                      Time_TickString(rec_wt_endticks, tick),
	                      rec_wt_endticks));                                 y = y + lh;

	/*
	  The tick the run was SIMULATED at, and the padding ring in front of it.

	  Both matter for the same reason and neither was on screen: a 100Hz bhop
	  recording and a 66.7Hz surf one are different files that look identical
	  here, and the span before t=0 is approach rather than run -- the trailer
	  counts it, so this prints the trailer's own number rather than deriving one
	  from t0, which is the disagreement build 25's stage slices turned out to be.

	  The Hz deliberately stays on the `rec rate` row below and is not repeated
	  here: that row already frames it as measured-against-nominal, and two rows
	  of one number is the thing this panel exists to avoid.
	*/
	Watch_InfoRow([p_x, y], w, sz, cw, "tick",
	              sprintf("%.4f s   pad %g samples", tick, rec_wt_pad));     y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "at",
	              sprintf("%.3f  of %.3f..%.3f",
	                      rec_wt_time, rec_wt_t0, rec_wt_t1));                 y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "playback",
	              sprintf("%.2fx%s", rec_wt_rate,
	                      rec_wt_paused ? "  paused" : ""));                 y = y + lh;

	// --- the three rates, together, because they are only useful compared ---
	/*
	  "no sidecar" rather than two zeros, and this is not cosmetic.

	  The run's frame rate is a property of the .view, and a .rec with no .view
	  beside it has no answer -- a recording made before build 17, or a fixture,
	  or a run whose sidecar was lost.  Printing 0 there says "that machine
	  rendered no frames", which is a claim about somebody's run rather than an
	  admission that the file cannot say.  The leaderboard's clean/stitched column
	  makes the same distinction for the same reason.
	*/
	Watch_InfoRow([p_x, y], w, sz, cw, "run fps",
	              (rec_wt_view >= 1)
	                ? sprintf("%.0f now  %.0f avg", livehz, viewhz)
	                : "no sidecar");                                        y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "your fps",
	              sprintf("%.0f", rec_wt_fps));                              y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "rec rate",
	              sprintf("%.1f Hz of %.1f", rechz,
	                      (tick > 0) ? (1 / tick) : 0));                    y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "samples",
	              sprintf("%g rec  %g view", rec_wt_nsamp,
	                      rec_wt_viewn - rec_wt_view0));                      y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "ramp",
	              rec_wt_v4
	                ? sprintf("%g  %.2f %.2f %.2f", rec_wt_rc ? 1 : 0,
	                          rec_wt_gnorm_x, rec_wt_gnorm_y, rec_wt_gnorm_z)
	                : "not recorded");                                      y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "rows",
	              sprintf("%g seq (%g)  %g board", rec_wt_sqn,
	                      rec_wt_sqshown, rec_wt_bdn_n));                     y = y + lh;

	Watch_InfoRow([p_x, y], w, sz, cw, "path",
	              sprintf("%g pts  %g tele  %g ev",
	                      ln_n[0], ln_bkn[0], rec_wt_evn));

	Font_Reset();
};

/*
  sui_begin / sui_end bracket every frame that draws with sui, and they are here
  rather than in cl_main.qc so that the one caller cannot forget: sui_end is what
  clears the click-once actions, and without it sui_is_released would latch true
  forever and the close button would fire on every subsequent frame.
*/
void(vector scr) Watch_Draw =
{
	if (!rec_wt_open)
	{
		rec_wt_chromebot = 0;
		return;
	}

	sui_begin(scr_x, scr_y);
	Watch_Chrome(scr);

	// AFTER the chrome, which is what publishes rec_wt_chromebot -- this panel
	// hangs off it, so drawing first would lay it out against last frame's.
	if (cvar("hud_watch_info"))
		Watch_Info(scr);

	sui_end();
};

/*
===========================================================================
  Per frame
===========================================================================
*/
void() Watch_Frame =
{
	local float dt, i, dtcl, was;
	local vector e;

	rec_wt_on = FALSE;
	if (!rec_wt_open)
		return;

	// The map changed under us.  The camera would be flying through another
	// map's geometry, and the frozen player is a different edict now.
	if (rec_wt_map != "")
	if (rec_wt_map != serverkey("map"))
	{
		Watch_Stop();
		return;
	}

	dt = cltime - rec_wt_lastreal;
	rec_wt_lastreal = cltime;
	dtcl = dt;
	// Patch 379: cltime is a float32 of map uptime (0.24 ms steps after an hour,
	// 2 ms after 4.5); clframetime is exact but the frame pacer moves it off the
	// cltime delta by up to half a frame (cl_main.c:7572).  The difference is
	// banked and paid once past half a frame (missed time, an unrendered
	// stretch), so the clock cannot drift from cltime.  A per-frame choice
	// between the two drifts whenever it is not the same choice every frame.
	if (clframetime > 0)
	{
		rec_wt_clkerr = rec_wt_clkerr + dt - clframetime;
		dt = clframetime;
		if (fabs(rec_wt_clkerr) > clframetime * 0.5 + cltime * 0.00000024)
		{
			dt = dt + rec_wt_clkerr;
			rec_wt_clkerr = 0;
		}
	}
	if (dt < 0 || dt > 0.5)             // a hitch, a load, or the first frame
		dt = 0;

	/*
	  BUILD 25: the VIEWER's frame rate, for the info panel.

	  Exponentially smoothed at about a fifth of a second, which is the same time
	  constant the strafe bar's turn window uses and for the same reason: 1/dt on
	  a single frame is a number that swings by a third at 300 fps and reads as
	  noise rather than as a rate.  Taken here because this is where the replay
	  already measures real elapsed time, before the playback rate scales it --
	  rec_wt_time's clock is the recording's and this one has to be yours.
	*/
	if (dt > 0)
		rec_wt_fps = rec_wt_fps + ((1 / dt) - rec_wt_fps) * (dt / 0.2 > 1 ? 1 : dt / 0.2);

	if (!rec_wt_paused)
	{
		was = rec_wt_time;
		rec_wt_time = rec_wt_time + dt * rec_wt_rate;
		if (rec_wt_time >= rec_wt_vt1)
		{
			rec_wt_time   = rec_wt_vt1;
			rec_wt_paused = TRUE;        // hold on the last frame rather than
		}                               // snapping back to your own body

		/*
		  ---- AND SKIP THE DEAD AIR.  Build 43. ------------------------------

		  Only while PLAYING, and that is the whole of the gating this needs.  A
		  pause is someone looking at a still frame -- including, deliberately,
		  a still frame inside a parked stretch, which is exactly where you would
		  pause to see what the player was doing -- and yanking the clock out
		  from under that would make the pause useless.  A drag is a pause too:
		  sui_slidercontrol calls Watch_ScrubTo, which sets rec_wt_time directly
		  and does not come through here, so a scrub INTO a stretch stays where
		  it was put and only starts skipping when you press play again.  That
		  falls out of the structure rather than needing a test, and it is the
		  behaviour you want: the marks are on the bar to be scrubbed to.

		  THROUGH Watch_Seek AND NOT BY WRITING rec_wt_time.  Watch_Seek is the
		  one entry point that invalidates all four cursor caches -- the view
		  block, the split list, the segment column and the board -- and a jump
		  of thirty seconds that skipped them would leave the panels describing
		  where the clock used to be.  That is the same reason Watch_ScrubTo goes
		  through it.

		  Landed just PAST the end of the stretch rather than exactly on it, by
		  one tick.  Exactly on it re-enters the same span on the next frame if
		  the sample at that boundary is still under the threshold, which it is
		  by construction -- the span closes on the first FAST sample, so its end
		  time is a tick after the last slow one.  Half a tick of margin costs
		  nothing and removes a loop that would otherwise be possible.
		*/
		if (rec_wt_idn > 0)
		if (cvar("hud_watch_skipidle"))
		for (i = 0; i < rec_wt_idn; i = i + 1)
		{
			if (rec_wt_time < rec_wt_idt0[i])
				break;                  // the spans are in order; the rest are ahead
			if (rec_wt_time < rec_wt_idt1[i])
			{
				Watch_Seek(rec_wt_idt1[i] + rec_wt_tickrate);
				break;
			}
		}

		// Patch 395: a stage window's end, on a playback crossing (after the idle
		// skip, so a skip over it counts; a seek or scrub does not).  Patch 431:
		// the cut ends there, so the pause above has already happened.
		if (rec_wt_wincut)
		if (was < rec_wt_vt1)
		if (rec_wt_time >= rec_wt_vt1)
		{
			Watch_Seek(rec_wt_vt1);
			rec_wt_paused = TRUE;
			print(sprintf("replay: stage %g window end %.4f -- paused\n",
			              rec_wt_winseg + 1, rec_wt_time));
		}
	}

	Watch_Sample();
	rec_wt_on = TRUE;

	// `replay trace frames`: turnrate is ui_turnrate, i.e. the previous frame's.
	if (rec_wt_trfn > 0)
	{
		e = Watch_Eye();
		print(sprintf("wtf %.6f %.6f %.5f %.3f ", dtcl, clframetime, rec_wt_time, e_z),
		      sprintf("%.3f %.1f %.3f %g\n", rec_wt_yaw, ui_turnrate, rec_wt_rate,
		              rec_wt_paused));
		rec_wt_trfn = rec_wt_trfn - 1;
		if (rec_wt_trfn <= 0)
			print("wtfe\n");
	}
};

float(float evtype, float scanx, float chary, float devid) Watch_InputEvent =
{
	if (!rec_wt_open)
		return FALSE;

	// The cursor.  sui wants absolute positions and gets them because
	// setcursormode(TRUE) put kdm_game into key_dest_absolutemouse, which is
	// what makes the engine call CSQC_MousePosition instead of CSQC_MouseMove.
	// Returning TRUE is not optional: the deltas are zeroed only on a true
	// return, so forgetting it leaves the view turning under the cursor.
	if (evtype == IE_MOUSEABS)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}

	if (evtype == IE_KEYDOWN || evtype == IE_KEYUP)
	{
		/*
		  MOUSE1 is bound to +duck and MOUSE2 to +jump, so a click on the close
		  button would also crouch the frozen player.  Both are swallowed whole
		  while the chrome is up -- and the caller must not have fed them to
		  Keys_Edge either, or the duck box lights every time you click.
		*/
		if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
		{
			sui_input_event(evtype, scanx, chary, devid);
			return TRUE;
		}

		if (evtype == IE_KEYUP)
			return FALSE;

		// Escape closes.  keys.c:3205 says csqc may steal it, and the board is
		// open with key_dest still kdm_game, so the test there passes and the
		// menu does not open behind us.
		if (scanx == K_ESCAPE)
		{
			Watch_Stop();
			return TRUE;
		}
		if (scanx == K_SPACE)
		{
			rec_wt_paused = !rec_wt_paused;
			return TRUE;
		}
		if (scanx == K_LEFTARROW)
		{
			Watch_Seek(rec_wt_time - 5);
			return TRUE;
		}
		if (scanx == K_RIGHTARROW)
		{
			Watch_Seek(rec_wt_time + 5);
			return TRUE;
		}
	}

	return FALSE;
};

/*
  `replay` -- the command.

  The name is free: nothing in the engine registers it.  That had to be checked
  rather than assumed, because PF_cs_registercommand is `if (!Cmd_Exists(...))`
  and therefore SILENTLY does nothing when the name is taken -- the command would
  simply never arrive and nothing would say why.
*/
// BUILD 57: `leg` is the LEG -- 0 the full run, k stage k -- as FS_RunPath takes it.
string(float track, float leg, string tag) Watch_LegPath =
{
	return FS_RunPath(serverkey("map"), track, leg, -1, tag, "rec");
};

/*
  The best archived run on a leg: the archive is sorted by name and the names are
  zero-padded tick counts, so the first match IS the fastest.  That property is
  the whole reason build 23 padded them, and it is what lets a leaderboard exist
  with no index file.

  BUILD 57: keyed on the LEG.  It took the 0-based starting segment and handed it
  to FS_RunDir as though it were one, which is why `replay stage 2` opened stage
  3's folder and `replay stage 1` opened stage 2's.
*/
string(float track, float leg, string tag) Watch_BestOnLeg =
{
	local float h;
	local string fn;

	h = search_begin(sprintf("%s*_%s.rec", FS_RunDir(serverkey("map"),
	                                                 track, leg), tag),
	                 FS_NAMESORT, TRUE);
	if (h < 0)
		return "";
	if (search_getsize(h) < 1)
	{
		search_end(h);
		return "";
	}
	fn = search_getfilename(h, 0);
	search_end(h);
	return fn;
};

/*
  `replay status` -- the reader, said out loud.

  This engine has no viewpos and no way to ask what the camera is doing, so
  without a line like this the entire playback path would be verifiable only by
  looking at it, which is exactly the class of thing that ships subtly wrong.
  It is the same instrument as the server timer's "would write" line: every
  number on it is the one the frame actually used, not a recomputation.

  Three prints because fteqcc caps varargs at eight and SILENTLY drops the rest,
  which would fill the tail of the line with zeroes rather than fail to compile.
*/
void() Watch_Status =
{
	local vector sv;
	if (!rec_wt_open)
	{
		print("replay: nothing loaded\n");
		return;
	}

	print(sprintf("replay: %s\n", rec_wt_path));
	print(sprintf("  owner %s  map %s  track %d seg %d  end %d  samples %d\n",
	              (rec_wt_owner != "") ? rec_wt_owner : "-",
	              (rec_wt_map != "") ? rec_wt_map : "-",
	              rec_wt_track, rec_wt_startseg, rec_wt_endticks, rec_wt_nsamp));
	print(sprintf("  t %.4f  span %.4f..%.4f  tick %g  rate %.2f  paused %g\n",
	              rec_wt_time, rec_wt_t0, rec_wt_t1, rec_wt_ticks,
	              rec_wt_rate, rec_wt_paused));
	// Patch 395.  Stage 0 = no window; finrow = the finish row is in the list.
	print(sprintf("  window stage %g  %.4f..%.4f  cut %g  abandoned %g  state %g  finrow %g\n",
	              rec_wt_winseg + 1, rec_wt_wint0, rec_wt_wint1, rec_wt_wincut,
	              rec_wt_abandon, rec_wt_state, rec_wt_evfin));
	print(sprintf("  view %.4f..%.4f\n", rec_wt_vt0, rec_wt_vt1));   // Patch 431
	print(sprintf("  org %.2f %.2f %.2f  vel %.2f %.2f %.2f\n",
	              rec_wt_org_x, rec_wt_org_y, rec_wt_org_z,
	              rec_wt_vel_x, rec_wt_vel_y, rec_wt_vel_z));
	print(sprintf("  ang %.2f %.2f  keys %g  ground %g  duck %g  flags %g\n",
	              rec_wt_pitch, rec_wt_yaw, rec_wt_keys,
	              rec_wt_onground, rec_wt_ducked, rec_wt_flags));
	print(sprintf("  view %g lines (%g index)  path %g of %g samples, %g shown, %g tele  events %g\n",
	              rec_wt_viewn, rec_wt_vxn, ln_n[0], rec_wt_cnt,
	              ln_ib[0] - ln_ia[0] + 1, ln_bkn[0], rec_wt_evn));
	// Build 43.  A SECOND print rather than six more fields on the one above --
	// fteqcc caps varargs at 8 including the format and drops the ninth silently.
	// `curve` reaching exactly WT_PATHMAX is the build-42 truncation bug; `still`
	// is what the red on the bar is drawn from and what skip would jump.
	print(sprintf("  still %g stretch(es)%s  skip %g\n",
	              rec_wt_idn,
	              (rec_wt_idover > 0) ? sprintf(" (+%g dropped)", rec_wt_idover) : "",
	              cvar("hud_watch_skipidle")));
	/*
	  The screen-space drawer's last frame.  Three numbers because "the line is
	  not there" has three different causes and they need telling apart: mode/0
	  quads means it never ran, quads 0 with clip high means the near-plane clip
	  ate everything, and quads high with `first` outside the screen means it
	  drew somewhere you cannot see.  Guessing between those cost a build.
	*/
	print(sprintf("  path mode %g  2d %g seg(s)  clipped %g  wild %g  first %.0f,%.0f\n",
	              Watch_PathMode(), rec_wt_p2n, rec_wt_p2clip, rec_wt_p2wild,
	              rec_wt_p2first_x, rec_wt_p2first_y));
	print(sprintf("  path %g pts projected  %g draws  speed %.0f..%.0f  colour %g\n",
	              rec_wt_p2pts, ln_frames, ln_slo, ln_shi, ln_cmode));   // Patch 432
	// The probe: 256 units dead ahead, projected either side of renderscene.
	// Both should read the centre of the screen and they should agree.
	sv = getproperty(VF_SCREENVSIZE);
	print(sprintf("  probe pre %.0f,%.0f  post %.0f,%.0f  screen %g x %g\n",
	              rec_wt_p2pre_x, rec_wt_p2pre_y,
	              rec_wt_p2post_x, rec_wt_p2post_y, sv_x, sv_y));
	print(sprintf("  2d bbox %.0f,%.0f .. %.0f,%.0f\n",
	              rec_wt_p2min_x, rec_wt_p2min_y,
	              rec_wt_p2max_x, rec_wt_p2max_y));

	/*
	  THE v4 HALF, and it is the whole of what stage 1b added.

	  Six lines was the varargs cap on ONE sprintf, not on the function, so these
	  are two more prints rather than a squeeze.  They are here for the same
	  reason the rest of this exists: no config can look at the strafe bar, and
	  without these the ramp contact, the plane, the board table and the segment
	  build would be verifiable only by watching the screen.

	  `seq` reading `0 rows` on a v4 file is the failure that matters -- it means
	  the build pass ran and Board_Frame produced nothing, which is either a
	  missing ramp bit or a plane the engine never wrote.
	*/
	print(sprintf("  v4 %g  rc %g  plane %.3f %.3f %.3f  wish %.2f %.2f\n",
	              rec_wt_v4, rec_wt_rc,
	              rec_wt_gnorm_x, rec_wt_gnorm_y, rec_wt_gnorm_z,
	              rec_wt_wish_x, rec_wt_wish_y));
	print(sprintf("  seq %g rows (%g shown)  boards %g (at %g)  turn %.0f/s\n",
	              rec_wt_sqn, rec_wt_sqshown, rec_wt_bdn_n, rec_wt_bdshown,
	              ui_turnrate));
	// Build 25.  See Watch_BuildSeq: this is the only headless evidence that the
	// ramp hold does anything, because the column looks the same either way.
	print(sprintf("  ramp gaps bridged %g  (hold %.2fs, the engine's own board gate)\n",
	              rec_wt_bridged, RAMP_GAP));

	// Patch 378: the interpolation tables.  tools/watchtrace.py --model prints
	// these three lines from the file; a difference is SUSPECT.
	print(sprintf("  fit %d hermite  %d linear  %d snap   snaps %d rec  %d kin  "
	              "(%d vetoed, +%d over)\n", rec_wt_nfit2, rec_wt_nfit1, rec_wt_nfit0,
	              rec_wt_snrec, rec_wt_snkin, rec_wt_nveto, rec_wt_snover));
	print(sprintf("  duck %d slide(s)  %d fix  (+%d over)  eye %g / %g  src %d\n",
	              rec_wt_dkn, rec_wt_dkfix, rec_wt_dkover, rec_wt_vh, rec_wt_dvh,
	              rec_wt_vhsrc));
	if (rec_wt_view >= 1)
		print(sprintf("  view %d span(s)  %d knot(s)  (+%d over)  %d short  "
		              "%d stalled  step %.1f ms\n", rec_wt_vspans, rec_wt_vkn,
		              rec_wt_vkover, rec_wt_vshort, rec_wt_vstall, rec_wt_vkstep * 1000));
	else
		print("  view none\n");
	print(sprintf("  load %.0f ms  view map %.0f ms\n", rec_wt_loadms, rec_wt_vmapms));
	print(sprintf("  now angles %s  fit %g  eye %.2f  view line %g (knot %g)\n",
	              rec_wt_asrc ? "view" : "rec", rec_wt_fit, rec_wt_eyeh, rec_wt_vj,
	              rec_wt_vkc));

	/*
	  BUILD 25: the same three rates the info panel draws, so the console and the
	  screen cannot say different things.  See Watch_Info for what each is and why
	  the live one is worth more than the average.
	*/
	{
		local float span, tick;
		span = rec_wt_t1 - rec_wt_t0;
		tick = rec_wt_tickrate;
		if (tick <= 0) tick = PM_TICK;

		// See Watch_Info: with no sidecar the run's own frame rate has no answer,
		// and two zeros would read as one.
		if (rec_wt_view >= 1)
			print(sprintf("  run fps %.0f now / %.0f avg   yours %.0f   rec %.1f Hz of %.1f\n",
			              Watch_ViewHz(),
			              (span > 0.001) ? ((rec_wt_viewn - rec_wt_view0) / span) : 0,
			              rec_wt_fps,
			              (span > 0.001) ? (rec_wt_nsamp / span) : 0,
			              1 / tick));
		else
			print(sprintf("  run fps no sidecar   yours %.0f   rec %.1f Hz of %.1f\n",
			              rec_wt_fps,
			              (span > 0.001) ? (rec_wt_nsamp / span) : 0,
			              1 / tick));
	}
};

/*
  `replay trace <n> <dt>`: n synthetic frames dt run-seconds apart from the
  current position, one `wtr T ex ey ez pitch yaw src fit eyeh` line each, then
  back to where it started.  Frame-rate independent, so a headless harness can
  measure smoothness (tools/watchtrace.py --analyse).
*/
void(float n, float dt) Watch_Trace =
{
	local float i, t0;
	local vector e;

	if (!rec_wt_open)
	{
		print("replay: nothing loaded\n");
		return;
	}
	t0 = rec_wt_time;
	print(sprintf("wtrb %g %g %.5f %g %s\n", n, dt, t0,
	              (rec_wt_view >= 1) ? 1 : 0, rec_wt_path));
	for (i = 0; i < n; i = i + 1)
	{
		rec_wt_time = t0 + i * dt;
		if (rec_wt_time > rec_wt_vt1)
			break;
		Watch_Sample();
		e = Watch_Eye();
		print(sprintf("wtr %.6f %.3f %.3f %.3f ", rec_wt_time, e_x, e_y, e_z),
		      sprintf("%.3f %.3f %g %g %.3f\n", rec_wt_pitch, rec_wt_yaw,
		              rec_wt_asrc, rec_wt_fit, e_z - rec_wt_org_z));
	}
	print("wtre\n");
	Watch_Seek(t0);
	Watch_Sample();
};

string(float rep, string dir) Online_ReplayFind;     // cl_online.qc, compiled after

float(string cmd) Watch_ConsoleCommand =
{
	local string a, p;
	local float track, leg, nv;

	tokenize(cmd);
	if (argv(0) != "replay")
		return FALSE;

	a = argv(1);
	nv = (argv(2) == "noview" || argv(3) == "noview" || argv(4) == "noview");

	if (a == "stop" || a == "off")
	{
		Watch_Stop();
		return TRUE;
	}

	/*
	  The scripted controls.  They exist so a config can drive the reader to an
	  exact position and read it back -- playback otherwise advances with the
	  wall clock, and at the 4 fps a headless run manages, "wait 40 frames" is
	  ten seconds of a run rather than a fixed place in it.
	*/
	if (a == "status")
	{
		Watch_Status();
		return TRUE;
	}
	if (a == "pause")  { rec_wt_paused = TRUE;  return TRUE; }
	if (a == "play")   { rec_wt_paused = FALSE; return TRUE; }
	if (a == "seek")
	{
		if (!rec_wt_open)
		{
			print("replay: nothing loaded\n");
			return TRUE;
		}
		// `end` rather than a number, because the last sample's t is in the file
		// and a config cannot know it -- and the end is the position the whole
		// reader is most worth checking at.
		Watch_Seek((argv(2) == "end") ? rec_wt_vt1 : stof(argv(2)));
		Watch_Sample();
		return TRUE;
	}
	if (a == "speed")
	{
		Watch_SetRate(stof(argv(2)));
		print(sprintf("replay: %.2fx\n", rec_wt_rate));
		return TRUE;
	}
	// Patch 378: see Watch_Trace; `frames` prints the next n real frames instead.
	if (a == "trace")
	{
		if (argv(2) == "frames")
		{
			rec_wt_trfn = stof(argv(3));
			print(sprintf("wtfb %g %g %s\n", rec_wt_trfn, (rec_wt_view >= 1) ? 1 : 0,
			              rec_wt_path));
		}
		else
			Watch_Trace(stof(argv(2)), stof(argv(3)));
		return TRUE;
	}

	// Patch 395: `window <leg>` plays that stage of the open file (Watch_StageWindow).
	if (a == "window")
	{
		if (!rec_wt_open)
			print("replay: nothing loaded\n");
		else
			Watch_StageWindow(stof(argv(2)) - 1);
		return TRUE;
	}
	// Patch 432: `bench <n>`, the path's draw timed (Watch_Path2D).
	if (a == "bench")
	{
		rec_wt_bench = max(1, stof(argv(2)));
		return TRUE;
	}
	// Patch 431: `cut 0|1`, the chrome's "whole run" / "stage N only".
	if (a == "cut")
	{
		if (!rec_wt_open)
			print("replay: nothing loaded\n");
		else
			Watch_SetCut(stof(argv(2)));
		return TRUE;
	}

	track = 0;
	leg   = 0;
	p     = "";

	if (a == "")
		p = Watch_BestOnLeg(0, 0, "pb");
	// Patch 395: `online <id>`, a downloaded run by its ledger id (data/online/).
	else if (a == "online")
	{
		p = Online_ReplayFind(stof(argv(2)), "");
		if (p == "")
		{
			print(sprintf("replay: r%s is not cached -- board_replay %s\n",
			              argv(2), argv(2)));
			return TRUE;
		}
		// Patch 431: `online <id> <leg>` opens cut to that stage, as a board row does.
		rec_wt_wantleg = stof(argv(3));
	}
	/*
	  The word IS the tag, so there is no list here to keep in step -- build 45
	  asks FS_TagFromName whether the argument names one, and a fifth tag needs
	  no edit in this file at all.  `stage`, `bonus` and a bare path fall past it
	  because none of them is a tag word.

	  The branch inside is archived-or-not rather than a second list of names: an
	  archived tag has many files on the leg and wants the fastest, an unstamped
	  one has exactly one and its path is already known.  Same reason SV_RecClose
	  stopped spelling that test out in the same build.
	*/
	/*
	  BUILD 57: A LOBBY TIME HAS NO REPLAY, and saying so is the whole fix.  Its
	  .rec is a header with `samples 0`: the server measured the run and kept
	  nothing, and this client wrote down only what the stats told it.  Left to
	  fall through, Watch_Open reports "holds 0 samples -- nothing to play", which
	  reads as a truncated or corrupt recording rather than as the shape every
	  lobby row has.  The leaderboard already refuses the same click in the same
	  words; this is the console door to it.
	*/
	else if (FS_TagFromName(a) == RT_LOBBY)
	{
		print("^3replay:^7 that time was set on a lobby -- no replay was recorded\n");
		return TRUE;
	}
	else if (FS_TagFromName(a) != RT_NONE)
	{
		p = FS_TagArchived(FS_TagFromName(a)) ? Watch_BestOnLeg(0, 0, a)
		                                      : Watch_LegPath(0, 0, a);
	}
	/*
	  BUILD 57: `replay stage N` IS LEG N -- stage N as the HUD, `!s N` and the
	  scoreboard all count it.  The number used to reach FS_RunDir as a 0-based
	  segment, so `replay stage 2` opened stage 3's folder and stage 1 could not
	  be asked for at all.  `bonus T N` takes the same leg for the bonus's stage N.
	*/
	else if (a == "stage")
	{
		leg = stof(argv(2));
		p   = Watch_BestOnLeg(0, leg, "pb");
	}
	else if (a == "bonus")
	{
		track = stof(argv(2));
		leg   = stof(argv(3));
		p     = Watch_BestOnLeg(track, leg, "pb");
	}
	else
		p = a;

	if (p == "")
	{
		print(sprintf("replay: no recording for %s\n",
		              FS_RunDir(serverkey("map"), track, leg)));
		return TRUE;
	}

	rec_wt_noview = nv;
	Watch_Open(p);
	rec_wt_noview = FALSE;
	return TRUE;
};

void() Watch_RegisterCvars =
{
	registercommand("replay");

	// The path.  Drawn behind walls correctly because Zone_Line queues into the
	// scene before renderscene; see Watch_Path.
	registercvar("hud_watch_path", "1");

	// The part of the run you have not reached yet.  On by default because a
	// line that stops at the camera is much harder to read as a route.
	registercvar("hud_watch_path_ahead", "1");

	/*
	  The ribbon's width, in world units at 512 units of range.  6 is about a
	  finger's width at arm's length on a 1080p window.
	*/
	registercvar("hud_watch_path_width", "6");

	/*
	  Whether that width follows the distance to the camera.

	  1 (default) makes it a fixed ANGULAR size, so the line reads the same
	  thickness the whole way down the map; 0 makes it a fixed WORLD size, which
	  is honest geometry and vanishes into a hairline at range.  Both are
	  computed per VERTEX rather than per segment either way -- that is the thing
	  that stopped it looking like a row of slugs, and it is not optional.
	*/
	registercvar("hud_watch_path_scale", "1");

	/*
	  BUILD 25 -- the tech panel.

	  `replay status` has printed most of this to the console since build 24, and
	  a console line is the wrong instrument for three of the numbers below: they
	  change every frame, and reading them means watching them move against the
	  scrub rather than sampling one.  Off by default because it covers a third of
	  the left of the screen and the ride is what a replay is for.
	*/
	registercvar("hud_watch_info", "0");

	/*
	  BUILD 34 -- how big the playback panel is, on top of hud_scale.

	  hud_scale sizes the whole HUD together, and the demo player is a control
	  rather than a readout: it wants to be reachable with a mouse without
	  dragging every other panel up with it.  Multiplies the two font sizes, the
	  padding, the row gaps, the track and the slider knobs, so the panel keeps
	  its proportions rather than growing a fat border around 1x text.

	  Clamped 0.5..4 in Watch_Chrome: below that the hint row is unreadable and
	  above it the panel is wider than any window it would sit in.

	  CVAR_ARCHIVE like the rest of the hud_watch_* family.  Note the caveat the
	  cl_hud.qc essay makes about that flag on an install with a cfg/default.cfg:
	  the flag is inert there and default.cfg's value is what you get.
	*/
	registercvar("hud_watch_scale", "1", CVAR_ARCHIVE);

	/*
	  BUILD 43 -- the dead air, and skipping it.

	  hud_watch_idle_speed is the horizontal speed under which the run counts as
	  parked, and hud_watch_idle_time is how long it has to stay under it before
	  the bar says so.  Both are read ONCE, in Watch_Scan, because the spans are
	  built at load -- so changing either takes effect on the NEXT `replay`, not
	  on the one already open.  That is the same contract Watch_BuildSeq's
	  thresholds have and it is worth knowing before someone tunes one live and
	  concludes it does nothing.

	  hud_watch_idle_pad brings the pre-start approach into scope.  Off, because
	  the approach is meant to be slow and marking it red says something false
	  about the run; on, if what you want to see is the whole file rather than
	  the timed part of it.

	  hud_watch_skipidle is ON by default and this is a deliberate choice about
	  which way round the surprise should go.  Someone who opens a replay to
	  study a line does not want to sit through forty seconds of a parked player,
	  and the marks on the bar make it obvious what was skipped and that a switch
	  exists -- the chrome carries a clickable toggle beside the speed slider for
	  the same reason.  hud_watch_info shipped defaulting to 0 in build 25, was
	  reported missing in build 26, and the note that came out of it was "A
	  feature nobody can find has not shipped."
	*/
	/*
	  BUILD 43 -- which path drawer, and how wide the screen-space one is.

	  DEFAULT 2 FROM BUILD 45.  It shipped at 1 for two builds because mode 2
	  computed correct geometry and did not reach the screen, and a default that
	  draws nothing is worse than the ribbon it replaced.  The cause was the
	  winding, the fix is one sign, and the essay at Watch_PathMode says why the
	  three builds of measurement either side of it all read correct.

	  Mode 1 is not deprecated and is not going away.  It is the depth-tested
	  one: a path behind a wall is hidden by the wall in mode 1 and drawn over it
	  in mode 2, and that is a real preference and not a defect in either.

	  hud_watch_path_px is a SEPARATE cvar from hud_watch_path_width rather than
	  a reinterpretation of it, because the two are not the same quantity: the
	  ribbon's 6 is world units at a 512-unit reference distance, and this one is
	  pixels.  Sharing the name would have silently made every existing config a
	  six-pixel line.  Patch 432: 1, anti-aliased (cl_lines.qc).
	*/
	registercvar("hud_watch_path_mode", "2", CVAR_ARCHIVE);
	registercvar("hud_watch_path_px", "1", CVAR_ARCHIVE);
	registercvar("hud_watch_path_color", "0", CVAR_ARCHIVE);   // 0 speed, 1 gain/loss
	registercvar("hud_watch_path_far", "6000", CVAR_ARCHIVE);  // fade out by here, 0 never
	registercvar("hud_watch_path_probe", "0");

	registercvar("hud_watch_idle_speed", "20", CVAR_ARCHIVE);
	registercvar("hud_watch_idle_time", "0.5", CVAR_ARCHIVE);
	registercvar("hud_watch_idle_pad", "0", CVAR_ARCHIVE);
	registercvar("hud_watch_skipidle", "1", CVAR_ARCHIVE);
};
