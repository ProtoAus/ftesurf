/*
===========================================================================
  cl_lines.qc -- run lines.  Patch 432.

  Recorded paths drawn as screen-space strips, one point per recorded sample.
  The strip is 1 px (hud_watch_path_px) and anti-aliased by vertex alpha: a
  w px line box-filtered onto pixels is a trapezoid, full across w - 1 px and
  falling to 0 over a pixel each side (a 1 px line: a 2 px tent), so each
  segment is a fan whose outer vertices carry alpha 0.  Joints share mitred
  vertices, so a bend neither overlaps nor gaps.  Colour is per group since Patch
  632 (hud_lines_color_own for the live trail, _others for the rest): a plain
  colour, or a reading such as speed, red (slow) through yellow to green (fast)
  over the shown lines' own range.  A teleport is a break: a square at each end and a
  faint dashed line between.  A segment longer than LN_SUBPX on screen is
  subdivided along a Catmull-Rom through its neighbours.

  Slot 0 is the replay (Watch_ScanRange builds it); 1..8 are board lines.
  Drawn after renderscene, so a line shows through walls.  Points are culled
  by 32-point chunk against the view frustum, and a chunk draws every 2^L-th
  point for the largest L whose error (measured at load, Line_End) is under
  LN_PXERR on screen at its distance.  1 us of QC a drawn point (p432bench), a
  quarter of it the polygons; so past hud_watch_path_far a line fades out and
  is not walked at all (16-chunk groups are culled first).
===========================================================================
*/

// 0 the replay, 1..8 the board's, 9 and 10 the live trail's pair (cl_trail.qc,
// Patch 475 -- two so a finished run can fade while the next one builds over it).
// 3.25 MiB a slot at LN_CAP, counted off Line_Alloc's own arenas.
#define LN_SLOTS   67           // 0 the replay, 1..8 board lines, 9 and 10 the live run, 11..66 more
#define LN_S_BOARD 1            // the first board slot and the first trail slot,
#define LN_S_TRAIL 9            // which pick a slot's width (Line_SlotPx)
#define LN_S_MORE  11           // Patch 649: the first of the fifty-six further board slots
#define LN_CAP     65536        // samples a slot holds (16 min at 66 Hz); past it, halved
#define LN_CAP2    8192         // ... and a further board slot (2 min at 66 Hz; the same halving)
#define LN_TOTAL   (LN_S_MORE * LN_CAP + (LN_SLOTS - LN_S_MORE) * LN_CAP2)
// A slot's first sample in the arenas, its capacity, and whether it is the live run's.
// Slots under LN_S_MORE are where they always were, so LN_B(s) still holds for those.
#define LN_B(s)    (((s) < LN_S_MORE) ? (s) * LN_CAP : LN_S_MORE * LN_CAP + ((s) - LN_S_MORE) * LN_CAP2)
#define LN_C(s)    (((s) < LN_S_MORE) ? LN_CAP : LN_CAP2)
#define LN_TRAIL(s) ((s) >= LN_S_TRAIL && (s) < LN_S_MORE)
// Board line i of the scoreboard's (0 the first) is this slot.
#define LN_BOARDSLOT(i) (((i) < LN_S_TRAIL - LN_S_BOARD) ? (i) + LN_S_BOARD : (i) + LN_S_MORE - (LN_S_TRAIL - LN_S_BOARD))
#define LN_BOARDINDEX(s) (((s) < LN_S_TRAIL) ? (s) - LN_S_BOARD : (s) - LN_S_MORE + (LN_S_TRAIL - LN_S_BOARD))
#define LN_CHUNK   32
#define LN_GROUP   16           // chunks a group sphere covers
#define LN_BKCAP   512          // teleports marked per slot
#define LN_NEAR    8            // near clip, units (project() divides by w unguarded)
#define LN_GUARD   8192         // virtual px: a vertex past this is a near-plane stub
#define LN_LEVELS  5            // strides 2..32 (LN_CHUNK)
#define LN_PXERR   1.0          // physical px a stride may be off the samples
#define LN_SUBPX   16           // virtual px: a longer segment is subdivided

/*
  THE MARKS.  Patch 449.

  Where the run touched down, left the ramp, hopped, and where a segmented run
  was stitched.  They are the EDGES of Board_KindOf (cl_board.qc), the same
  three-state contact function the Segments column is built from, with none of
  that column's row-level debounce -- so every segment row boundary is a mark,
  and a bounce too short to become a row is a mark with no row.  That
  containment is the invariant p449mark grades; a second detector written here
  would drift from the column and the two would disagree about one run.

  A mark carries its own position and velocity rather than a point index, which
  is what makes it survive both decimations (the build-time ln_skip stride and
  the past-the-cap halving) with no index fixup at all.

  MEASURED, AND NOT WORKED AROUND: samples are one per PACKET (43-65/s against
  a nominal 66.67), and a bhop's ground contact is one tick.  A perfect hop's
  contact can fall between two packets and be absent from the file, so the line
  misses those hops -- and so does the Segments column, from the same samples,
  identically.  Do not interpolate hops the file does not contain.
*/
#define LN_EVCAP   4096         // marks a slot holds; past it, peaks go first
#define LN_EVDZ    8            // height a top or bottom stands clear by, each side
#define LN_CELLS   4096         // declutter cells; 64 x 36 at the default gap
#define LN_LABMAX  512          // labels queued for the end of the frame; the last LN_SLOTS are the names'

#define LN_E_LAND    1          // touched ground or ramp
#define LN_E_LEAVE   2          // left it without jumping (a ramp exit, an edge)
#define LN_E_JUMP    3          // left the ground with the jump button down
#define LN_E_APEX    4          // vz turned over
#define LN_E_TROUGH  5          // vz turned back up
#define LN_E_STITCH  6          // a save state was loaded here: resume/retry
#define LN_E_BREAK   7          // a teleport: the marks' own record of a break

/*
  WHY A BREAK IS IN THE MARK TABLE when the teleport pass already draws it.

  It is not drawn from here -- Line_Draw's teleport pass owns the squares and
  the dashes.  It is here because it is the one thing a mark depends on that
  the table did not carry: a break suppresses the contact edge across it, and
  ln_bk cannot say where, because the past-the-cap halving moves a dropped
  sample's break onto the next kept point (up to a sample late, measured on
  bhop_monster_jam save010: 127437 samples, 8 marks out of phase).  So the
  table records the breaks the CLASSIFIER saw, and tools/p449mark.py grades
  against those instead of against a list that has been through decimation.
*/

vector *ln_pos;
string *ln_owner;
float *ln_g;
float *ln_g_assumed;
float *ln_start;
float *ln_graphgen;
// Patch 622: the track and leg a slot's shown window is (leg 0 the whole run, k stage k), for
// the graph to set the live run against; -1 until a loader says (Line_Leg).
float *ln_track;
float *ln_leg;
float  *ln_spd;
float  *ln_t;
float  *ln_born;                // visual publication time, demo and two live slots
float  *ln_published;
float  ln_reveal;               // seconds: chunk/playhead reveal, 0 is immediate
float  *ln_brk;                 // 1: no segment from the previous point (a teleport)
float  *ln_gain;
float  *ln_vz;                  // Patch 452: the third term of the energy
float  *ln_q;                   // Patch 453: air-control grade, -1 = no answer
vector *ln_col;                 // the colour, redone when the range or mode moves
float  *ln_cerr;                // per chunk and level 1..LN_LEVELS: the error, units
vector *ln_cc;                  // per chunk: centre, radius, holds a break
float  *ln_cr;
float  *ln_cbk;
vector *ln_gc;                  // per group of LN_GROUP chunks: centre, radius
float  *ln_gr;
float  *ln_bk;                  // break indices, LN_BKCAP a slot

// The marks: one entry each, position and velocity carried, never an index.
float  *ln_ek;                  // LN_E_*
float  *ln_efd;                 // Patch 632: a contact mark a top or bottom was folded into
float  *ln_es;                  // the contact pair it came from, from * 4 + to
float  *ln_et;                  // the run clock it landed on
vector *ln_ep;
float  *ln_evh;                 // horizontal speed there, u/s
float  *ln_e2;                  // v . v, 3D: the energy term, minus the height
float  *ln_ez;                  // vz, signed
float  *ln_ei;                  // the sample it came from, counted by this slot
float  *ln_ec;                  // the clock of the sample the classifier's edge fell on

// A ride's last REAL contact, where its leave mark is stamped (Line_Point).  Per
// slot: [ordinal, clock] and [position, velocity]; ordinal < 0 is no ride open.
float  *ln_rcf;
vector *ln_rcv;

/*
  THE RIDE'S EDGE AGAINST THE MAP (Line_Edge, Patch 628).  Four records a slot:
  [0] the last contact sample, [1] the one before it, [2] the last sample in the
  hold's gap whose hull is still against the ramp, [3] the first one off it.
  Only a recording's two scanners hand in the plane (Line_Plane); the live line
  does not, and keeps the last-contact stamp.
*/
float  *ln_xi;     // sample ordinal, -1 none
float  *ln_xt;             // clock, ducked
float  *ln_xd;
vector *ln_xo;   // where, how fast, the face
vector *ln_xv;
vector *ln_xn;
vector *ln_cn;         // this sample's plane, and whether one was handed in
float  *ln_cd;
float  *ln_chave;
float  *ln_xon;        // hud_lines_edge as the slot's build began, and the file has planes
float  *ln_xq;         // a sample in this hold's gap could not be read: the leave abstains
float  *ln_xhow;   // leaves: as stamped, edge after [0], edge before [0], edge after [2]
vector ln_hitn;                 // Line_OnRamp's face
entity ln_probe;                // ...and the entity its trace is made as
vector ln_exo, ln_exv;          // Line_Edge's answer: where, how fast,
float  ln_ext, ln_exi;          // when, and the sample it is counted on
#define LN_XREACH  0.5          // u: the hull is "against" a face this near (0.25 above to 0.5 into)
#define LN_XSTEPS  6            // halvings of the tick the edge is found in
// MOVE_NOMONSTERS | MOVE_MISSILE, the engine's world-only trace (World_Move): the
// map's own brushes and displacements and nothing a client entity adds -- the
// glare pass links walk-through brush copies as SOLID_BSP (cl_sprites.qc).
#define LN_XMOVE   3

float  *ln_n;
float  *ln_bkn;
float  *ln_step;       // build decimation: keep every step-th sample
float  *ln_skip;
float  *ln_pbrk;       // a break carried from a dropped sample
float  *ln_on;
float  *ln_ia;     // the shown index range
float  *ln_ib;
float  *ln_lo;     // its speed range
float  *ln_hi;

float  *ln_evn;        // marks held
float  *ln_evcut;      // the peaks were dropped to make room
float  *ln_evdrop;     // marks lost past the cap even so
float  *ln_pkind;      // the contact kind of the last sample, -1 unknown
float  *ln_ron;        // the ramp hold's two variables, this slot's own
float  *ln_rlast;
float  *ln_gjmp;       // +jump seen anywhere in the ground phase
float  *ln_pvz;
vector *ln_po;     // the sample before: where, how fast
vector *ln_pv;
// The tops and bottoms (Line_Peak): the last one marked and its height (or
// where the count began), and the turn waiting for the body to move clear of it.
float  *ln_pklast;
float  *ln_pkz;
float  *ln_pkk;        // its kind, 0 none waiting
float  *ln_pkcov;      // a contact mark on its sample already shows it
float  *ln_phere;      // the sample before carried a contact mark
float  *ln_pkt;     // time, sample, edge clock
float  *ln_pki;
float  *ln_pkc;
vector *ln_pko;
vector *ln_pkv;
float  *ln_nsamp;      // samples this slot has classified
float  *ln_tick;       // the recording's own tick, for the ceiling
float  *ln_pyaw;   // the sample before: yaw, clock
float  *ln_pt;
float  *ln_gsince;     // when the current ground phase began

/*
  THE MOVEMENT SETTINGS THE GRADE IS MEASURED AGAINST.

  Read once per load, from the server this client is on -- which is what the
  strafe bar does for a replay too (HUD_DrawStrafe, cl_hud.qc), so the line and
  the bar grade the same moment the same way.  A recording made on a server
  with different movement settings is therefore graded against THIS one's: that
  is a real limitation, it is the bar's limitation as well, and the v9 header's
  `pmpin` block is where a future patch would get the file's own.
*/
float  ln_mv_airaccel, ln_mv_accel, ln_mv_maxspeed, ln_mv_aircap;
float  ln_mv_gravity, ln_mv_gfric, ln_mv_stopspeed, ln_mv_duck, ln_mv_ghold;

// The window: the stretch of RUN TIME shown around the playhead, set by the
// caller.  Never inferred from tplay -- a board line is drawn with tplay
// 99999999 as a "no playhead" sentinel (cl_scores.qc), and a window derived
// from that shows nothing at all.
float  ln_winon, ln_wina, ln_winb, ln_winka, ln_winkb;

/*
  Patch 624: where the viewer is along a line, so that a board line can be shown in run
  order (the stretch that comes next, through the window above) and not as everything
  within hud_watch_path_far: a later part of the route then does not show through a wall.
  A sample index, followed a few samples a frame. A few times a second the whole line is
  looked over as well, and the cursor moves if the stretch it follows is no longer among the
  nearest (the viewer left for another part of the route).
*/
#define LN_FO_NEAR  48          // samples either side of the cursor searched a frame
#define LN_FO_EVERY 0.25        // seconds between looks at the whole line
#define LN_FO_SOON  0.05        // the same, while a restart is not yet believed
#define LN_FO_FRESH 0.5         // seconds a restart's forget lasts: the stats lead the view by a frame or more
#define LN_FO_SPOTS 24          // stretches near the eye one look can weigh
#define LN_FO_READ  4096        // samples one look may read one by one; past it the 512 stand for the rest
float  *ln_fo_i;       // the cursor
float  *ln_fo_gen;     // ln_graphgen of the line it is on, + 1; 0 = none
float  *ln_fo_d;       // units from the eye to its sample
float  *ln_fo_at;      // cltime of the last look at the whole line
float  *ln_fo_n;   // looks made, and those that moved the cursor (`lines order`)
float  *ln_fo_mv;
float  *ln_fo_ta;  // the window this frame's draw was given
float  *ln_fo_tb;
float  *ln_fo_wt;      // cltime of the frame it was given in: only that frame's is one
float  *ln_fo_jump;             // Patch 649: the viewer was moved away from this cursor: look, do not wait
float  ln_fo_si[LN_FO_SPOTS], ln_fo_sd[LN_FO_SPOTS];    // a look's stretches: the nearest sample of each, its distance
float  ln_fo_clock, ln_fo_state;    // the timer last frame
float  ln_fo_fresh;             // cltime until which a restart leaves no cursor believed

// The marks' own frame state: the cvars, read once, and the declutter grid.
float  ln_mkon, ln_mkland, ln_mkleave, ln_mkjump, ln_mkstitch;
float  ln_mkmax;                // hud_lines_marked: the first this many drawn board lines carry marks
float  ln_mkrank;               // ... and the place among them of the one being drawn
float  ln_mkpx, ln_mkgap, ln_declutter;
// Line widths, px, read once a frame: the replay's, the board's, your own run's.
float  ln_wpx, ln_wpxb, ln_wpxt;

// The numbers (Patch 451), read once a frame.  ln_grav is the reader's, not one
// baked in at load: the same file watched on a different sv_gravity is a
// different run and the energy has to say so.
float  ln_numon, ln_numspeed, ln_numenergy, ln_numvz, ln_numdelta, ln_numtime;
float  ln_numref, ln_numsize, ln_grav, ln_units, ln_names;
float  ln_labsz;                // the size the labels are measured and drawn at, see Line_Marks
float  *ln_z0;       // the slot's first sample: z, v.v
float  *ln_v20;
float  ln_nlab;                 // labels queued, this Line_Draw
float  ln_labover;              // ...and the ones past LN_LABMAX

/*
  THE LABELS ARE QUEUED AND DRAWN AT THE END OF THE FRAME, not where they are
  worked out.

  Measured, not assumed: text drawn from inside Line_Draw does not appear at
  all.  The pass runs inside a stream of R_BeginPolygon batches, which the
  engine defers until a later 2D call flushes them, and a drawstring issued
  between two of them produced nothing -- including a fixed test string at a
  fixed position, which is how this was pinned down rather than guessed.  The
  counters said thirteen labels had drawn and the screenshot had none.

  Ev_Labels (cl_entview.qc) has the same shape for the same reason, and the
  slot for it in cl_main is already there.
*/
vector *ln_lab_p;
vector *ln_lab_c;
float  *ln_lab_a;
float  *ln_lab_w;
vector ln_labelpos, ln_labelscreen;
string ln_lab_t[LN_LABMAX];     // a global array, not allocated: these are temp strings, held a frame
float  ln_lab_n;
/*
  Patch 661: A LABEL STAYS AT ITS OWN MARK (hud_lines_declutter 0, the default).
  The lanes moved it up to eight rows away to keep it whole, which with a
  dozen lines put numbers nowhere near what they were about.  Now the frame's
  labels are taken nearest the eye first (Line_LabelsPlace); one whose place is
  taken fades out, and fades in when moving nearer has parted it from its
  neighbour.  A line's name is a label too and goes first at its distance.
  2 is the lanes, 1 the sparse grid.
*/
#define LN_LB_NAME  (LN_SLOTS * LN_EVCAP)   // a name's fade state: this + slot
#define LN_LB_BUCK  96                      // distance buckets, the order: finer near the eye
#define LN_LB_FAINT 0.3                     // a label under this alpha is drawn but takes no room
#define LN_LB_WRAP  4000000                 // frames before the stamps start again (a float counts to 2^24)
#define LN_LB_GRID  32768                   // room cells: 160 x 200 at most
#define LN_LB_IN    0.15                    // seconds to fade in, and out
#define LN_LB_OUT   0.10
float  *ln_lab_d;               // how far from the eye, less its preference
float  *ln_lab_h;               // text height (a name's is not a number's)
float  *ln_lab_k;               // 0 a mark's numbers; slot + 1 a line's name
float  *ln_lab_key;             // its fade state
float  *ln_lab_nx;              // the next label of its bucket
float  *ln_lfa;                 // fade state: the alpha a label had...
float  *ln_lff;                 // ...and the frame it had it in
float  *ln_lgrid;               // a room cell's last taking frame
float  ln_lb_head[LN_LB_BUCK];
float  ln_labgen, ln_labt;      // this frame's number, and the last one's cltime
float  ln_labfar, ln_labfadek;  // hud_lines_label_far and its fade
float  ln_lanes, ln_sparse;     // hud_lines_declutter 2 and 1
float  ln_lbshown, ln_lbhidden; // last frame: labels with room, and without (`lines native`)
void(float s, vector q, float a) LineGraph_NameDraw;
float  *ln_cell;                // a cell's last claiming frame
float  *ln_lcell;               // and the labels' own grid, see Line_Claim
float  ln_cellgen, ln_cellnx, ln_cellny;
vector ln_qmk;                  // Line_ProjPt's answer (a second return)
float  ln_nmk;                  // marks drawn, this Line_Draw
float  ln_nmkf;                 // ... and since Line_StatsReset (`lines native`: the gate's count)
float  ln_trmk;                 // `replay marktrace`: frames left to print

// per frame
vector ln_eye, ln_fwd, ln_rt, ln_up;
float  ln_tx, ln_ty, ln_kx, ln_ky;           // tan(fov/2), and the sphere slack
float  ln_tolk;                  // units of error a unit of distance allows
float  ln_far, ln_fadek;          // hud_watch_path_far, and 1 / its fade's length
float  ln_cfade;                 // the last sphere tested reaches into the fade
float  ln_px;                   // one physical pixel, virtual units
float  ln_hw, ln_cw, ln_pk;     // outer / full-alpha half widths, peak alpha
float  ln_slo, ln_shi, ln_sinv;
// Patch 632: your own line (the live trail's two slots) and the others (the demo
// and the board's) are coloured separately.  0..4 are the five readings of the
// run; 5 is the group's plain colour: LN_OWNCOL, or the line's place by time.
float  ln_cmown, ln_cmoth;
#define LN_CM_PLAIN 5
#define LN_OWNCOL  '0.30 0.65 1.00'
vector *ln_rk;          // an other line's colour by time, this frame
float  *ln_rkin;    // it is ranked; its place, 0 the fastest
float  *ln_rkpos;
float  *ln_rkof;        // ... among this many lines of its leg
float  *ln_rkt;                 // Patch 649: the time it was ranked on
float  ln_rksum;                // ... and a sum over all of them: the ranks stand while it does
float  *ln_drawf;       // cltime the slot was last drawn (0 never), for `replay colours`
vector *ln_plain;       // the plain colour the slot was last painted
// Patch 649: a slot's build count, and as of ITS last recolour.  This was one count for
// all slots, so the live run's Line_End (every sixteen samples, four times a second)
// repainted every ticked line from its first sample: sixty-four lines' worth of it.
float  *ln_sgen;
float  *ln_scgen;
float  ln_npaint;               // whole repaints of lines that are not the live run's (`lines native`)
float  ln_allocms;              // what Line_Alloc took, ms
float  ln_cslo, ln_cshi, ln_ccown, ln_ccoth;
float  ln_nseg, ln_nclip, ln_nwild, ln_npt;  // the last Line_Draw, for status
vector ln_bbmin, ln_bbmax, ln_first;
float  ln_frames;               // Watch_Path2D calls, to divide profile_csqc by

// the strip being streamed: the last two screen points, the pending side
float  ln_rn;
vector ln_rq0, ln_rs0, ln_rc0;
float  ln_ra0;
vector ln_rq1, ln_rc1, ln_rn1;
float  ln_ra1;

// the world point before, for the near clip and the subdivision
float  ln_hp, ln_pi, ln_pd, ln_pa;
vector ln_pp, ln_pc;
float  ln_db, ln_dn, ln_da;     // the slot being drawn: base, points, alpha
float  ln_ds;                   // ... and its number (a base no longer says which slot)

/*
  PROVENANCE, AS A TINT RATHER THAN A COLOUR MODE.  A run imported from another
  game (tools/momimport.py; the `foreign` key in its .rec header) is drawn with
  its colour pulled toward blue.

  A TINT AND NOT A SIXTH READING OF THE RUN, which was the obvious shape and
  is the wrong one: a mode REPLACES the colouring, so an imported line could be
  identified or it could be read for speed, gain, contact, energy or air
  control, never both.  Blending composes with all five, so the thing the line
  is FOR still works and the line still says where it came from.

  Luminance is preserved rather than flattened -- the blend keeps the relative
  brightness the mode produced -- so a fast stretch of an imported line is still
  visibly faster than a slow one.
*/
float  *ln_fgn;        // slot holds a foreign run
float  *ln_inf;        // where its ramp contact came from, INF_* (cl_infer.qc)
float  ln_dtint;                // the draw's blend strength, 0 = none
float  *ln_tintd;      // ... as each slot was last drawn (Patch 632)
#define LN_FGNCOL  '0.25 0.45 1.00'

/*
  Patch 645: THE STRIP, NATIVELY.  Line_Feed, Line_Q and Line_Emit are about a
  microsecond a segment in QC (250 instructions, 14 builtin calls): eight lines
  and their graph were 3 ms a frame.  The engine has the same code in C
  (engine/client/pr_csqc_lines.inc) writing the same fans into the same batch.
  THE QC BELOW STAYS, for an engine without the builtins and as the reference:
  a change to one is a change to the other (tools/test_p645lines.py draws both
  and compares the pixels).  hud_lines_native 0 draws the QC way.
  LP_* is lines_draw's parameter block and must match the enum there.
*/
void(float hw, float cw, float pk, float px) lines_width = #0;
void(vector a, vector sa, vector ca, float la, vector b, vector sb, vector cb, float lb) lines_segment = #0;
float(float *pts, float n, vector org, vector scale, vector rgb, float alpha) lines_strip2d = #0;
void(vector *pos, vector *col, float *t, float *brk, float *born, float samples, float bornsamples) lines_arrays = #0;
void(vector *cc, float *cr, float *cerr, vector *gc, float *gr, float chunks, float groups, float levels) lines_lod = #0;
float(float *parm, float count) lines_draw = #0;
#define LP_VERSION   0
#define LP_BASE      1
#define LP_FIRST     2
#define LP_LAST      3
#define LP_COUNT     4
#define LP_PUBLISHED 5
#define LP_FLAGS     6          // 1 demo reveal, 2 births, 4 window, 8 ln_cfade
#define LP_BORNBASE  7
#define LP_CHUNKBASE 8
#define LP_GROUPBASE 9
#define LP_TPLAY     10
#define LP_AHEAD     11
#define LP_ALPHA     12
#define LP_TINT      13
#define LP_PHEAD     14
#define LP_TINTCOL   17
#define LP_WINA      20
#define LP_WINB      21
#define LP_WINKA     22
#define LP_WINKB     23
#define LP_REVEAL    24
#define LP_CLTIME    25
#define LP_EYE       26
#define LP_FWD       29
#define LP_RT        32
#define LP_UP        35
#define LP_TX        38
#define LP_TY        39
#define LP_KX        40
#define LP_KY        41
#define LP_TOLK      42
#define LP_FAR       43
#define LP_FADEK     44
#define LP_CHUNK     45
#define LP_GROUP     46
#define LP_LEVELS    47
#define LP_NEAR      48
#define LP_GUARD     49
#define LP_SUBPX     50
#define LP_NPT       51
#define LP_NSEG      52
#define LP_NWILD     53
#define LP_NCLIP     54
#define LP_BBMIN     55
#define LP_BBMAX     57
#define LP_FIRSTPT   59
#define LP_CFADE     61
#define LP_SIZE      62
float  ln_nath;                 // the engine has the builtins and was told where the samples are
float  ln_nat;                  // ... and this frame draws with them
float  ln_natn, ln_natno;       // passes it drew, and refused, since start (`lines native`)
float  *ln_np;

// Patch 649: the per-slot tables.  Allocated, because csprogs has no global definitions to
// spare for one of each a slot (AGENT_NOTES, "CSPROGS SITS AT FTEQCC'S GLOBAL LIMIT").
// Line_RegisterCvars calls this before anything can read one.
void() Line_AllocSlots =
{
	if (ln_n)
		return;
	ln_lab_p = memalloc(sizeof(vector) * LN_LABMAX);
	ln_lab_c = memalloc(sizeof(vector) * LN_LABMAX);
	ln_lab_a = memalloc(sizeof(float) * LN_LABMAX);
	ln_lab_w = memalloc(sizeof(float) * LN_LABMAX);
	ln_lab_d = memalloc(sizeof(float) * LN_LABMAX);
	ln_lab_h = memalloc(sizeof(float) * LN_LABMAX);
	ln_lab_k = memalloc(sizeof(float) * LN_LABMAX);
	ln_lab_key = memalloc(sizeof(float) * LN_LABMAX);
	ln_lab_nx = memalloc(sizeof(float) * LN_LABMAX);
	ln_lgrid = memalloc(sizeof(float) * LN_LB_GRID);
	ln_owner = memalloc(sizeof(string) * LN_SLOTS);
	ln_g = memalloc(sizeof(float) * LN_SLOTS);
	ln_g_assumed = memalloc(sizeof(float) * LN_SLOTS);
	ln_start = memalloc(sizeof(float) * LN_SLOTS);
	ln_graphgen = memalloc(sizeof(float) * LN_SLOTS);
	ln_track = memalloc(sizeof(float) * LN_SLOTS);
	ln_leg = memalloc(sizeof(float) * LN_SLOTS);
	ln_published = memalloc(sizeof(float) * LN_SLOTS);
	ln_xi = memalloc(sizeof(float) * LN_SLOTS * 4);
	ln_xt = memalloc(sizeof(float) * LN_SLOTS * 4);
	ln_xd = memalloc(sizeof(float) * LN_SLOTS * 4);
	ln_xo = memalloc(sizeof(vector) * LN_SLOTS * 4);
	ln_xv = memalloc(sizeof(vector) * LN_SLOTS * 4);
	ln_xn = memalloc(sizeof(vector) * LN_SLOTS * 4);
	ln_cn = memalloc(sizeof(vector) * LN_SLOTS);
	ln_cd = memalloc(sizeof(float) * LN_SLOTS);
	ln_chave = memalloc(sizeof(float) * LN_SLOTS);
	ln_xon = memalloc(sizeof(float) * LN_SLOTS);
	ln_xq = memalloc(sizeof(float) * LN_SLOTS);
	ln_xhow = memalloc(sizeof(float) * LN_SLOTS * 4);
	ln_n = memalloc(sizeof(float) * LN_SLOTS);
	ln_bkn = memalloc(sizeof(float) * LN_SLOTS);
	ln_step = memalloc(sizeof(float) * LN_SLOTS);
	ln_skip = memalloc(sizeof(float) * LN_SLOTS);
	ln_pbrk = memalloc(sizeof(float) * LN_SLOTS);
	ln_on = memalloc(sizeof(float) * LN_SLOTS);
	ln_ia = memalloc(sizeof(float) * LN_SLOTS);
	ln_ib = memalloc(sizeof(float) * LN_SLOTS);
	ln_lo = memalloc(sizeof(float) * LN_SLOTS);
	ln_hi = memalloc(sizeof(float) * LN_SLOTS);
	ln_evn = memalloc(sizeof(float) * LN_SLOTS);
	ln_evcut = memalloc(sizeof(float) * LN_SLOTS);
	ln_evdrop = memalloc(sizeof(float) * LN_SLOTS);
	ln_pkind = memalloc(sizeof(float) * LN_SLOTS);
	ln_ron = memalloc(sizeof(float) * LN_SLOTS);
	ln_rlast = memalloc(sizeof(float) * LN_SLOTS);
	ln_gjmp = memalloc(sizeof(float) * LN_SLOTS);
	ln_pvz = memalloc(sizeof(float) * LN_SLOTS);
	ln_po = memalloc(sizeof(vector) * LN_SLOTS);
	ln_pv = memalloc(sizeof(vector) * LN_SLOTS);
	ln_pklast = memalloc(sizeof(float) * LN_SLOTS);
	ln_pkz = memalloc(sizeof(float) * LN_SLOTS);
	ln_pkk = memalloc(sizeof(float) * LN_SLOTS);
	ln_pkcov = memalloc(sizeof(float) * LN_SLOTS);
	ln_phere = memalloc(sizeof(float) * LN_SLOTS);
	ln_pkt = memalloc(sizeof(float) * LN_SLOTS);
	ln_pki = memalloc(sizeof(float) * LN_SLOTS);
	ln_pkc = memalloc(sizeof(float) * LN_SLOTS);
	ln_pko = memalloc(sizeof(vector) * LN_SLOTS);
	ln_pkv = memalloc(sizeof(vector) * LN_SLOTS);
	ln_nsamp = memalloc(sizeof(float) * LN_SLOTS);
	ln_tick = memalloc(sizeof(float) * LN_SLOTS);
	ln_pyaw = memalloc(sizeof(float) * LN_SLOTS);
	ln_pt = memalloc(sizeof(float) * LN_SLOTS);
	ln_gsince = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_i = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_gen = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_d = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_at = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_n = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_mv = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_ta = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_tb = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_wt = memalloc(sizeof(float) * LN_SLOTS);
	ln_z0 = memalloc(sizeof(float) * LN_SLOTS);
	ln_v20 = memalloc(sizeof(float) * LN_SLOTS);
	ln_rk = memalloc(sizeof(vector) * LN_SLOTS);
	ln_rkin = memalloc(sizeof(float) * LN_SLOTS);
	ln_rkpos = memalloc(sizeof(float) * LN_SLOTS);
	ln_rkof = memalloc(sizeof(float) * LN_SLOTS);
	ln_rkt = memalloc(sizeof(float) * LN_SLOTS);
	ln_fo_jump = memalloc(sizeof(float) * LN_SLOTS);
	ln_sgen = memalloc(sizeof(float) * LN_SLOTS);
	ln_scgen = memalloc(sizeof(float) * LN_SLOTS);
	ln_drawf = memalloc(sizeof(float) * LN_SLOTS);
	ln_plain = memalloc(sizeof(vector) * LN_SLOTS);
	ln_fgn = memalloc(sizeof(float) * LN_SLOTS);
	ln_inf = memalloc(sizeof(float) * LN_SLOTS);
	ln_tintd = memalloc(sizeof(float) * LN_SLOTS);
};

void() Line_Alloc =
{
	if (ln_pos)
		return;
	ln_allocms = gettime(1);        // Patch 649: 68.9 MiB now (36.7 before): `lines native` says how long
	ln_pos  = memalloc(sizeof(vector) * LN_TOTAL);
	ln_spd  = memalloc(sizeof(float) * LN_TOTAL);
	ln_t    = memalloc(sizeof(float) * LN_TOTAL);
	ln_born = memalloc(sizeof(float) * 3 * LN_CAP);
	ln_brk  = memalloc(sizeof(float) * LN_TOTAL);
	ln_gain = memalloc(sizeof(float) * LN_TOTAL);
	// +2.25 MiB, and the only per-point array the marks and the numbers did
	// not need: energy is z + |v|^2/2g and ln_spd is the HORIZONTAL speed, so
	// without this the colour would be energy with the vertical left out --
	// wrong exactly where a surf line is interesting.
	ln_vz   = memalloc(sizeof(float) * LN_TOTAL);
	ln_q    = memalloc(sizeof(float) * LN_TOTAL);
	ln_col  = memalloc(sizeof(vector) * LN_TOTAL);
	ln_cerr = memalloc(sizeof(float) * LN_TOTAL / LN_CHUNK * LN_LEVELS);
	ln_cc   = memalloc(sizeof(vector) * LN_TOTAL / LN_CHUNK);
	ln_cr   = memalloc(sizeof(float) * LN_TOTAL / LN_CHUNK);
	ln_cbk  = memalloc(sizeof(float) * LN_TOTAL / LN_CHUNK);
	ln_gc   = memalloc(sizeof(vector) * LN_TOTAL / LN_CHUNK / LN_GROUP);
	ln_gr   = memalloc(sizeof(float) * LN_TOTAL / LN_CHUNK / LN_GROUP);
	ln_bk   = memalloc(sizeof(float) * LN_SLOTS * LN_BKCAP);
	// 1.28 MiB for every slot's marks, against 2.25 MiB for ONE more per-point
	// float array.  Nothing about a mark is per point, which is the argument.
	ln_ek   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_efd  = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_es   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_et   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_ep   = memalloc(sizeof(vector) * LN_SLOTS * LN_EVCAP);
	ln_evh  = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_e2   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_ez   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	// The ordinal is the mark's identity.  Two samples can share a `t` (a file
	// records one per packet, and a held clock repeats it -- both bhop fixtures
	// carry such a pair), so time does not identify a sample and a reader that
	// keys on it mis-assigns the mark.  +147 KB.
	ln_ei   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_ec   = memalloc(sizeof(float) * LN_SLOTS * LN_EVCAP);
	ln_rcf  = memalloc(sizeof(float) * LN_SLOTS * 2);
	ln_rcv  = memalloc(sizeof(vector) * LN_SLOTS * 2);
	ln_cell = memalloc(sizeof(float) * LN_CELLS);
	ln_lcell = memalloc(sizeof(float) * LN_CELLS);
	ln_lfa = memalloc(sizeof(float) * (LN_LB_NAME + LN_SLOTS));     // Patch 661: 1.05 MiB each
	ln_lff = memalloc(sizeof(float) * (LN_LB_NAME + LN_SLOTS));
	if (checkbuiltin(lines_draw))
	{
		lines_arrays(ln_pos, ln_col, ln_t, ln_brk, ln_born, LN_TOTAL, 3 * LN_CAP);
		lines_lod(ln_cc, ln_cr, ln_cerr, ln_gc, ln_gr, LN_TOTAL / LN_CHUNK,
		          LN_TOTAL / LN_CHUNK / LN_GROUP, LN_LEVELS);
		ln_np = memalloc(sizeof(float) * LP_SIZE);
		ln_nath = TRUE;
	}
	ln_allocms = (gettime(1) - ln_allocms) * 1000;
};

// The birth arena holds only demo/live slots, not the eight static board lines.
float(float s) Line_BirthBase =
{
	return (s == 0) ? 2 * LN_CAP : (s - LN_S_TRAIL) * LN_CAP;
};

void(float s) Line_Clear =
{
	if (ln_owner[s] != "") strunzone(ln_owner[s]);
	ln_owner[s] = "";
	ln_on[s] = FALSE;
	ln_n[s]  = 0;
	ln_published[s] = 0;
	ln_tintd[s] = ln_drawf[s] = 0;
	ln_g[s] = ln_start[s] = 0;
	ln_track[s] = ln_leg[s] = -1;
	ln_graphgen[s] = ln_graphgen[s] + 1;
	ln_bkn[s] = 0;
	ln_ia[s] = ln_ib[s] = 0;
	ln_evn[s] = 0;
	ln_evcut[s] = FALSE;
	ln_evdrop[s] = 0;
	ln_nsamp[s] = 0;
};

// The recording's own tick.  The energy colour divides by the most energy air
// strafing can add in one (Strafe_PowerCeiling), and that is per tick -- a file
// recorded at a different rate would otherwise read as a different player.
// Patch 470: Line_Grade reads it too (it took the live server's, and graded a
// 0.01 file on a 0.015 lobby against a target 1.5x too low).
void(float s, float tick) Line_Tick =
{
	ln_tick[s] = (tick > 0) ? tick : 0.015;
	ln_g[s] = 800;
	ln_g_assumed[s] = TRUE;
};

// The graph does not grade against this server's gravity. pmpin supplies the
// recorded value; imported/legacy files have no such pin, so label the 800
// assumption explicitly rather than silently borrowing the current server.
void(float s, string name) Line_Owner =
{
	if (ln_owner[s] != "") strunzone(ln_owner[s]);
	ln_owner[s] = strzone(name);
};

void(float s, float track, float leg) Line_Leg =
{
	ln_track[s] = track;
	ln_leg[s] = leg;
};

void(float s, float g) Line_GraphGravity =
{
	ln_g_assumed[s] = !(g >= 1 && g <= 10000);
	ln_g[s] = ln_g_assumed[s] ? 800 : g;
};

float(string header) Line_HeaderGravity =
{
	local float p;
	p = strstrofs(header, " gravity=");
	if (p < 0) return 0;
	return stof(substring(header, p + 9, 24));
};

void() Line_Movevars =
{
	ln_mv_airaccel = serverkeyfloat("sv_airaccelerate");
	ln_mv_accel    = serverkeyfloat("sv_accelerate");     if (ln_mv_accel    <= 0) ln_mv_accel    = 5;
	ln_mv_maxspeed = serverkeyfloat("sv_maxspeed");       if (ln_mv_maxspeed <= 0) ln_mv_maxspeed = PM_RUN_SPEED;
	ln_mv_aircap   = serverkeyfloat("pm_maxairspeed");    if (ln_mv_aircap   <= 0) ln_mv_aircap   = 30;
	ln_mv_gravity  = serverkeyfloat("sv_gravity");        if (ln_mv_gravity  <  1) ln_mv_gravity  = 800;
	ln_mv_gfric    = serverkeyfloat("sv_friction");       if (ln_mv_gfric    <  0) ln_mv_gfric    = 4;
	ln_mv_stopspeed= serverkeyfloat("sv_stopspeed");      if (ln_mv_stopspeed<  0) ln_mv_stopspeed= 75;
	ln_mv_duck     = serverkeyfloat("pm_duckspeed");
	ln_mv_ghold    = cvar("hud_strafe_groundhold");
};

// ---- Patch 628: the ride's edge against the map ---------------------------

// The records, and their planes with them: a cleared record's plane was still
// read by the gap's probe, so one file could mark differently in a used slot.
void(float s) Line_EdgeClear =
{
	ln_xi[s * 4] = ln_xi[s * 4 + 1] = ln_xi[s * 4 + 2] = ln_xi[s * 4 + 3] = -1;
	ln_xn[s * 4] = ln_xn[s * 4 + 1] = ln_xn[s * 4 + 2] = ln_xn[s * 4 + 3] = '0 0 0';
	ln_xq[s] = FALSE;
};

// A file with no plane to ask with (an import, a format before the column): no
// record is kept and no sample costs anything.  After Line_Begin.
void(float s) Line_EdgeOff =
{
	ln_xon[s] = FALSE;
};

// The plane the recording wrote on the sample about to be classified, and its
// hull.  Called just before Line_Point by a scanner that has them.
void(float s, vector n, float ducked) Line_Plane =
{
	ln_cn[s]    = n;
	ln_cd[s]    = ducked;
	ln_chave[s] = TRUE;
};

/*
  Is the hull at o against a ramp face of the loaded map, the way it faces n?
  1 yes, 0 no, -1 THE MAP CANNOT SAY (the hull starts inside something: a
  crease, a pillar beside the path) -- which is not "no", and a caller that
  needs a definite answer abstains on it.
  Traced from a quarter unit off the face to LN_XREACH into it, so a point a hair
  inside it (one on the chord between two samples) still answers.  Measured
  against two native recordings' own bit: 2,861 of 2,888 contact ticks on
  surf_kitsune and 2,091 of 2,130 on surf_voyager are against a face at this
  reach, and most of the misses are a ride's last tick, where the hull has
  already left.
*/
float(vector o, vector n, float ducked) Line_OnRamp =
{
	// Traced as a player's hull is: against player clip as well as solid.  With
	// `world` as the entity the trace passes through clip brushes, and a map whose
	// ramps are clip over a displacement read as having no ramps at all (0 of
	// 382 contact ticks on surf_axiom, 1 of 1,130 on surf_boreas).
	if (!ln_probe)
	{
		ln_probe = spawn();
		ln_probe.hitcontentsmaski = CONTENTBITS_BOXSOLID;
	}
	tracebox(o + n * 0.25, PM_HULL_MINS, ducked ? PM_DUCK_MAXS : PM_HULL_MAXS,
	         o - n * LN_XREACH, LN_XMOVE, ln_probe);
	if (trace_startsolid)
		return -1;
	if (trace_fraction >= 1)
		return FALSE;
	if (fabs(trace_plane_normal_z) < 0.1 || fabs(trace_plane_normal_z) > PM_STANDABLE)
		return FALSE;
	ln_hitn = trace_plane_normal;
	return TRUE;
};

void(float s, float r, float i, float t, vector o, vector v, vector n) Line_EdgeSet =
{
	ln_xi[s * 4 + r] = i;
	ln_xt[s * 4 + r] = t;
	ln_xo[s * 4 + r] = o;
	ln_xv[s * 4 + r] = v;
	ln_xn[s * 4 + r] = n;
	ln_xd[s * 4 + r] = ln_cd[s];
};

/*
  WHERE THE HULL LEFT THE RAMP, for the leave whose edge fell on this sample
  (o, v, t).  TRUE with ln_ex*; FALSE: the map cannot say, and the mark stays on
  the last contact sample, as before this patch.

  The recording's bit says the mover clipped a ramp DURING a tick, and its
  sample is where that tick ended -- usually already past the lip.  So: the
  last sample whose hull is still against the ramp (the last contact sample if
  it is, else the one before it, else a sample in the hold's gap that the bit
  missed), the next sample, and the tick between them halved LN_XSTEPS times
  along the straight line from one to the other.  The answer is the last point
  found against the ramp.
*/
float(float s, vector o, vector v, float t) Line_Edge =
{
	local float b, l, i, lo, hi, mid, how, tf, r;
	local vector ol, vl, of, vf, n;

	b = s * 4;
	if (!ln_xon[s])
		return FALSE;
	if (ln_xq[s])
		return FALSE;
	l = -1;
	how = 0;
	n = '0 0 0';
	of = o;
	vf = v;
	tf = t;
	if (ln_xi[b + 2] >= 0)
	{
		l = 2;                      // contact outlived the bit
		how = 3;
		n = ln_xn[b + 2];
	}
	else if (ln_xi[b] >= 0 && ln_xn[b] != '0 0 0')
	{
		r = Line_OnRamp(ln_xo[b], ln_xn[b], ln_xd[b]);
		if (r > 0)
		{
			l = 0;                  // the lip is in the tick after the last contact
			how = 1;
			n = ln_hitn;
		}
		else if (r == 0)            // off it for certain: not "cannot say"
		if (ln_xi[b + 1] >= 0)
		if (ln_xn[b + 1] != '0 0 0')
		if (ln_xi[b] - ln_xi[b + 1] == 1)
		if (Line_OnRamp(ln_xo[b + 1], ln_xn[b + 1], ln_xd[b + 1]) > 0)
		{
			l = 1;                  // ...or in the last contact tick itself
			how = 2;
			n = ln_hitn;
			of = ln_xo[b];
			vf = ln_xv[b];
			tf = ln_xt[b];
		}
	}
	if (l < 0)
		return FALSE;
	if (l != 1)
	{
		if (ln_xi[b + 3] >= 0)
		{
			of = ln_xo[b + 3];
			vf = ln_xv[b + 3];
			tf = ln_xt[b + 3];
		}
		// The far end is the sample the leave was seen on, which nothing has
		// asked about: a body that never left the face would be "placed" 63/64
		// of the way into its last tick.
		else if (Line_OnRamp(o, n, ln_cd[s]) != 0)
			return FALSE;
	}
	ol = ln_xo[b + l];
	vl = ln_xv[b + l];
	lo = 0;
	hi = 1;
	for (i = 0; i < LN_XSTEPS; i = i + 1)
	{
		mid = (lo + hi) * 0.5;
		r = Line_OnRamp(ol + (of - ol) * mid, n, ln_xd[b + l]);
		if (r < 0)
			return FALSE;
		if (r)
		{
			lo = mid;
			n = ln_hitn;
		}
		else
			hi = mid;
	}
	ln_exo = ol + (of - ol) * lo;
	ln_exv = vl + (vf - vl) * lo;
	ln_ext = ln_xt[b + l] + (tf - ln_xt[b + l]) * lo;
	ln_exi = ln_xi[b + l];
	ln_xhow[b + how] = ln_xhow[b + how] + 1;
	// For an arm: the answer, and the map asked afresh at it and at the first
	// point found off the ramp (1 and 0, or the halving went the wrong way).
	if (cvar("hud_lines_edgedebug"))
		print(sprintf("lnx %g %g %g %.4f %.4f %s %s\n", s, how, ln_exi, ln_xt[b + l], tf,
		              sprintf("%.4f %.4f %.2f %.2f %.2f", ln_ext, lo, ln_exo_x, ln_exo_y, ln_exo_z),
		              sprintf("%g %g", Line_OnRamp(ln_exo, n, ln_xd[b + l]),
		                      Line_OnRamp(ol + (of - ol) * hi, n, ln_xd[b + l]))));
	return TRUE;
};

void(float s) Line_Begin =
{
	Line_Alloc();
	Line_Movevars();
	Line_Clear(s);
	ln_step[s] = 1;
	ln_skip[s] = 0;
	ln_pbrk[s] = FALSE;
	ln_tick[s] = 0.015;
	ln_pkind[s] = -1;               // unknown, not "in the air": the first sample
	ln_ron[s]   = FALSE;            // of a board line's window must mark nothing
	ln_fgn[s]   = FALSE;            // until the header says otherwise
	ln_inf[s]   = INF_MEASURED;
	ln_rlast[s] = 0;
	ln_rcf[s * 2] = -1;
	Line_EdgeClear(s);
	ln_chave[s] = FALSE;
	ln_xon[s]   = cvar("hud_lines_edge");
	ln_xhow[s * 4] = ln_xhow[s * 4 + 1] = ln_xhow[s * 4 + 2] = ln_xhow[s * 4 + 3] = 0;
	ln_gjmp[s]  = FALSE;
	ln_pvz[s]   = 0;
	ln_po[s]    = ln_pv[s] = '0 0 0';
	ln_pklast[s] = ln_pkz[s] = ln_pkk[s] = 0;
	ln_phere[s] = FALSE;
	ln_pyaw[s]  = 0;
	ln_pt[s]    = 0;
	ln_gsince[s] = 0;
};

/*
  The run in this slot came from another game.  Called by whichever scanner read
  the header -- the replay's (slot 0) and the board-line job's (slots 1..8) are
  separate passes over the same grammar, so both have to say it.

  Set AFTER Line_Begin, which clears it: a slot is reused by whatever is drawn
  there next, and a foreign line leaving its tint behind for the local run that
  replaces it would be a lie that persists until the map changes.
*/
void(float s, float on) Line_Foreign =
{
	if (s >= 0 && s < LN_SLOTS)
		ln_fgn[s] = on ? TRUE : FALSE;
};

float(float s) Line_IsForeign =
{
	return (s >= 0 && s < LN_SLOTS) ? ln_fgn[s] : FALSE;
};

// Where this slot's ramp contact came from: set by the same two scanners, after
// Line_Begin.  An inferred ramp edge's label says so (Line_Label).
void(float s, float why) Line_Inferred =
{
	if (s >= 0 && s < LN_SLOTS)
		ln_inf[s] = why;
};

/*
  One mark.  Full is handled in two stages rather than by truncating:

    1. the peaks go, as a class, in one pass.  They are dense, derived, and
       carry no glyph, and a line that keeps every hop and says the peaks went
       beats one that shows 600 of 1200 hops and says nothing.
    2. past that it stops and counts, which `replay status` prints (slot 0).

  Halving, the way the point array does, is the wrong answer here: it would
  drop every other hop.

  `si` and `tc`: the sample the mark is stamped with, and the clock of the sample
  the classifier's edge fell on.  They differ only for a ramp leave (Line_Point).
*/
void(float i, float j) Line_EvSwap =
{
	local float f;
	local vector p;

	f = ln_ek[i];   ln_ek[i]  = ln_ek[j];   ln_ek[j]  = f;
	f = ln_efd[i];  ln_efd[i] = ln_efd[j];  ln_efd[j] = f;
	f = ln_es[i];   ln_es[i]  = ln_es[j];   ln_es[j]  = f;
	f = ln_et[i];   ln_et[i]  = ln_et[j];   ln_et[j]  = f;
	p = ln_ep[i];   ln_ep[i]  = ln_ep[j];   ln_ep[j]  = p;
	f = ln_evh[i];  ln_evh[i] = ln_evh[j];  ln_evh[j] = f;
	f = ln_e2[i];   ln_e2[i]  = ln_e2[j];   ln_e2[j]  = f;
	f = ln_ez[i];   ln_ez[i]  = ln_ez[j];   ln_ez[j]  = f;
	f = ln_ei[i];   ln_ei[i]  = ln_ei[j];   ln_ei[j]  = f;
	f = ln_ec[i];   ln_ec[i]  = ln_ec[j];   ln_ec[j]  = f;
};

void(float s, float k, float sub, float t, vector o, vector v, float si, float tc) Line_EvAt =
{
	local float b, n, i, j;

	if (ln_evcut[s])
	if (k == LN_E_APEX || k == LN_E_TROUGH)
		return;

	b = s * LN_EVCAP;
	n = ln_evn[s];
	if (n >= LN_EVCAP)
	{
		if (!ln_evcut[s])
		{
			j = 0;
			for (i = 0; i < n; i = i + 1)
				if (ln_ek[b + i] != LN_E_APEX)
				if (ln_ek[b + i] != LN_E_TROUGH)
				{
					ln_ek[b + j]  = ln_ek[b + i];
					ln_efd[b + j] = ln_efd[b + i];
					ln_ei[b + j]  = ln_ei[b + i];
					ln_ec[b + j]  = ln_ec[b + i];
					ln_es[b + j]  = ln_es[b + i];
					ln_et[b + j]  = ln_et[b + i];
					ln_ep[b + j]  = ln_ep[b + i];
					ln_evh[b + j] = ln_evh[b + i];
					ln_e2[b + j]  = ln_e2[b + i];
					ln_ez[b + j]  = ln_ez[b + i];
					j = j + 1;
				}
			ln_evn[s] = n = j;
			ln_evcut[s] = TRUE;
			// The peak that filled the table goes with the others.
			if (k == LN_E_APEX || k == LN_E_TROUGH)
				return;
		}
		if (n >= LN_EVCAP)
		{
			ln_evdrop[s] = ln_evdrop[s] + 1;
			return;
		}
	}
	ln_ek[b + n]  = k;
	ln_efd[b + n] = FALSE;
	ln_es[b + n]  = sub;
	ln_et[b + n]  = t;
	ln_ep[b + n]  = o;
	ln_evh[b + n] = vlen([v_x, v_y, 0]);
	ln_e2[b + n]  = v * v;
	ln_ez[b + n]  = v_z;
	ln_ei[b + n]  = si;
	ln_ec[b + n]  = tc;
	ln_evn[s] = n + 1;
	// Kept in time order, which Line_EvFind searches by: a ramp leave is stamped
	// back at its last contact, behind a turnaround marked in the hold's gap.
	while (n > 0)
	{
		if (ln_et[b + n - 1] <= t)
			break;
		Line_EvSwap(b + n - 1, b + n);
		n = n - 1;
	}
};

// A mark on the sample being classified, which is every mark but a ramp leave.
void(float s, float k, float sub, float t, vector o, vector v) Line_Ev =
{
	Line_EvAt(s, k, sub, t, o, v, ln_nsamp[s], t);
};

// Whether mark e of slot s carries its numbers at this frame's hud_lines_nums.
// Patch 632: at 3 a contact keeps its chevron and gives up its number, unless it
// is itself a top or a bottom (Line_EvFold).  `replay marks` prints this too.
float(float s, float e) Line_LabelOn =
{
	local float k;

	if (!ln_numon)
		return FALSE;
	if (ln_numon != 3)
		return TRUE;
	k = ln_ek[s * LN_EVCAP + e];
	if (k == LN_E_APEX || k == LN_E_TROUGH)
		return TRUE;
	return ln_efd[s * LN_EVCAP + e];
};

// Patch 632: the contact mark on sample si or the one before IS the top or bottom
// that was folded into it (Line_Peak's `here`).  At hud_lines_nums 3 it is the
// only place that turn's number can go: 1 of 11 bottoms of p492voy.rec and 2 of 5
// of runlines_peaks.rec are landings (the review's count).
void(float s, float si) Line_EvFold =
{
	local float b, i;

	b = s * LN_EVCAP;
	for (i = ln_evn[s] - 1; i >= 0; i = i - 1)
	{
		if (ln_ei[b + i] < si - 1)
			return;                     // marks are in time order: none further back
		if (ln_ek[b + i] <= LN_E_JUMP)
		if (ln_ei[b + i] == si || ln_ei[b + i] == si - 1)
		{
			ln_efd[b + i] = TRUE;
			return;
		}
	}
};

// One sample.  brk: the segment from the previous sample is a teleport.
void(float s, vector o, float spd, float vz, float q, float t, float brk) Line_Add =
{
	local float b, n, i, j;

	if (brk)
		ln_pbrk[s] = TRUE;
	if (ln_skip[s] > 0)
	{
		ln_skip[s] = ln_skip[s] - 1;
		return;
	}
	b = LN_B(s);
	n = ln_n[s];
	if (n >= LN_C(s))
	{
		// Past the cap: keep the even points, a dropped one's break on the next.
		for (i = 0; i < LN_C(s) / 2; i = i + 1)
		{
			j = b + 2 * i;
			ln_pos[b + i] = ln_pos[j];
			ln_spd[b + i] = ln_spd[j];
			ln_vz[b + i]  = ln_vz[j];
			ln_q[b + i]   = ln_q[j];
			ln_t[b + i]   = ln_t[j];
			if (s == 0 || LN_TRAIL(s))
				ln_born[Line_BirthBase(s) + i] = ln_born[Line_BirthBase(s) + 2 * i];
			ln_brk[b + i] = ln_brk[j];
			if (i > 0)
			if (ln_brk[j - 1])
				ln_brk[b + i] = TRUE;
		}
		if (ln_brk[b + LN_C(s) - 1])
			ln_pbrk[s] = TRUE;
		n = LN_C(s) / 2;
		ln_published[s] = ceil(ln_published[s] / 2);
		ln_step[s] = ln_step[s] * 2;
	}
	ln_skip[s] = ln_step[s] - 1;
	ln_pos[b + n] = o;
	ln_spd[b + n] = spd;
	ln_vz[b + n]  = vz;
	ln_q[b + n]   = q;
	ln_t[b + n]   = t;
	if (LN_TRAIL(s))
		ln_born[Line_BirthBase(s) + n] = cltime;
	// The newest point can draw before the bulk tables' four-sample rebuild.
	ln_brk[b + n] = (n > 0 && ln_pbrk[s]);
	j = n;
	for (i = 0; i < 2; i = i + 1)
		if (j > 0)
		if (!ln_pbrk[s] && !ln_brk[b + j])
			j = j - 1;
	ln_gain[b + n] = (t > ln_t[b + j]) ? (spd - ln_spd[b + j]) / (t - ln_t[b + j]) : 0;
	ln_pbrk[s] = FALSE;
	ln_n[s] = n + 1;
};

/*
  HOW GOOD WAS THE AIR CONTROL AT THIS SAMPLE, on the strafe bar's own terms.

  This is the bar's regime logic (HUD_DrawStrafe, cl_hud.qc), sample by sample
  instead of frame by frame, and it calls the SAME sh_strafe.qc functions with
  the same movement settings -- so the line and the bar cannot grade one moment
  two ways.  The three regimes are not variations of one formula:

    ground   Accelerate has no 30 u/s cap, so the optimum is wishdir nearly
             ALONG the velocity, and it is evaluated after friction.
    ramp     the clip couples gravity into the rotating component; on a 53
             degree face the ideal is 17-55% of the flat one, so the flat
             figure would overstate the target by up to 6x.
    air      the flat formula.

  It returns -1 -- NO ANSWER, drawn grey -- rather than a grade wherever the
  bar refuses one: an air cap that does not bind (a turn rate then grades the
  server, not the player), a ground target under 10 deg/s where the square-root
  shoulder makes 1 u/s swing it 15 deg/s, a plane the maths cannot answer for,
  and the first sample of a slot, which has no previous yaw to turn from.  A
  colour that says "bad" when it means "cannot tell" is the failure this
  codebase has paid for more than once.
*/
float(float s, vector v, float fl, float t, vector aux) Line_Grade =
{
	local float speed, turn, dt, ideal, cscale, gain, fric, wishspeed, vf, ong, tick;

	tick = ln_tick[s];
	dt = t - ln_pt[s];
	if (dt <= 0 || ln_nsamp[s] < 1)
		return -1;                      // nothing to have turned from
	if (fl & WT_F_RAMPI)
		return -1;                      // a ramp tick with no plane to grade against

	// Unsigned degrees per second, the short way round the circle.
	turn = aux_x - ln_pyaw[s];
	while (turn > 180)  turn = turn - 360;
	while (turn < -180) turn = turn + 360;
	turn = fabs(turn) / dt;

	speed = vlen([v_x, v_y, 0]);
	ong = fl & WT_F_ONGROUND;
	// A one-tick bhop landing is not a grounded phase -- the bar's own gate.
	if (ong)
	if (ln_mv_ghold > 0)
	if (t - ln_gsince[s] < ln_mv_ghold)
		ong = FALSE;

	wishspeed = ln_mv_maxspeed;
	if (ong)
	if (fl & WT_F_DUCKED)
	if (ln_mv_duck > 0)
		wishspeed = ln_mv_maxspeed * ln_mv_duck;

	// Surface friction: airborne and rising, below the non-jump velocity.
	fric = 1;
	if (!ong && v_z > 0 && v_z <= PM_NONJUMP_VEL)
		fric = 0.25;

	cscale = ln_mv_aircap;
	if (ong)
	{
		gain  = Strafe_GroundGain(ln_mv_accel, wishspeed, tick, fric);
		vf    = Strafe_AfterFriction(speed, ln_mv_gfric, ln_mv_stopspeed, tick);
		ideal = Strafe_IdealTurnGround(vf, gain, wishspeed, tick);
		if (ideal <= 10)
			return -1;                  // the shoulder: not a number to grade on
	}
	else if (!Strafe_CapBinds(ln_mv_airaccel, ln_mv_maxspeed, tick, fric,
	                          ln_mv_aircap))
		return -1;                      // the cap has slack: this grades the server
	else
	{
		gain = Strafe_AirGain(ln_mv_airaccel, wishspeed, tick, fric,
		                      ln_mv_aircap);
		if (aux_y >= 0.05 && aux_y <= PM_STANDABLE && aux_z != 0)
		{
			ideal  = Strafe_IdealTurnPlane(speed, tick, gain, ln_mv_gravity,
			                               aux_y, aux_z);
			cscale = Strafe_CScale(ln_mv_gravity, tick, aux_y, aux_z,
			                       ln_mv_aircap);
			if (ideal <= 0.001)
				return -1;              // the ramp is doing the turning, not you
		}
		else
			ideal = Strafe_IdealTurn(speed, gain, tick);
	}
	return Strafe_Quality(turn, ideal, cscale, ln_mv_aircap);
};

/*
  This sample's contact kind, with the slot's own ramp hold moved on.  It does
  NOT touch ln_pkind: the mark is the edge between two samples, so the caller
  owns what the previous one was.

  THE BRIDGED-GAP COUNTERS ARE DELIBERATELY NOT REPLICATED.  Board_RampHold
  also keeps ramp_raw/ramp_rawlast and counts ramp_drops/ramp_bridged on a
  gap's trailing edge; this has no equivalent and therefore cannot answer "how
  many gaps were bridged".  It does not need to -- the line wants kind EDGES,
  not a count -- but do not "fix" the omission: those counters belong to the
  live board, and `replay status`'s `ramp gaps bridged` is the board's number,
  not this one's (review, Patch 449).
*/
float(float s, vector v, float fl, float t) Line_Contact =
{
	local float raw, held;

	raw  = fl & (WT_F_RAMP | WT_F_RAMPI);
	held = Board_RampHeld(raw, ln_ron[s], ln_rlast[s], t);
	if (raw)
		ln_rlast[s] = t;
	ln_ron[s] = held;
	return Board_KindOf(fl & WT_F_ONGROUND, held);
};

// What a sample leaves behind for the next one to be compared against.
void(float s, float k, vector v, float fl) Line_Was =
{
	ln_pkind[s] = k;
	ln_pvz[s]   = v_z;
	ln_gjmp[s]  = (k == SEG_NONE) ? (ln_gjmp[s] || (fl & WT_F_JUMP)) : FALSE;
};

// The tops and bottoms start again at height z: on a slot's first sample, after
// a break or a loaded save, and on or beside ground.  Nothing waits, nothing to
// alternate with.
void(float s, float z) Line_PeakReset =
{
	ln_pkk[s]    = 0;
	ln_pklast[s] = 0;
	ln_pkz[s]    = z;
};

// The far side: at height z the body is LN_EVDZ clear of the turn that waits.
void(float s, float z) Line_PeakFar =
{
	local vector w;

	if (!ln_pkk[s])
		return;
	w = ln_pko[s];
	if ((ln_pkk[s] == LN_E_APEX) ? (w_z - z < LN_EVDZ) : (z - w_z < LN_EVDZ))
		return;
	if (!ln_pkcov[s])
		Line_EvAt(s, ln_pkk[s], 0, ln_pkt[s], w, ln_pkv[s], ln_pki[s], ln_pkc[s]);
	else
		Line_EvFold(s, ln_pki[s]);
	ln_pklast[s] = ln_pkk[s];
	ln_pkz[s]    = w_z;
	ln_pkk[s]    = 0;
};

/*
  ONE SAMPLE'S PART IN THE TOPS AND BOTTOMS.  Patch 627.

  A turn is where vz crossed zero between the sample before and this one, read
  off the straight line vz draws between the two (exact in the air: the mover's
  gravity is two half steps): its time, its height, its sideways speed.  On a
  ramp it is the same reading of the same two samples.

  It is MARKED when it stands LN_EVDZ of height clear on both sides: of the turn
  before it (or of where the count began), and of where the body goes next.  So
  a mark is stamped back at its turn once the body has moved on -- Line_EvAt
  keeps the table in time order -- tops and bottoms alternate, and a wobble
  smaller than that marks nothing however fast vz flips.  Before this patch the
  test was |vz| >= 40 and the air only, which missed every bottom on a ramp;
  that test with a height alternative, tried first, marked 52 pairs under 0.1 s
  apart in 400 imports where this marks none.

  `here`: a contact mark sits on this sample or the one before (a landing on an
  upslope IS the bottom, and half of them turn vz up a tick after the landing's
  own sample), so the turn counts for the alternation and is not drawn twice.
*/
void(float s, vector o, vector v, float t, float here) Line_Peak =
{
	local float pk, f, dt, z;
	local vector po, pv, eo, ev, w;

	pk = 0;
	if (ln_pvz[s] > 0 && v_z <= 0)
		pk = LN_E_APEX;
	else if (ln_pvz[s] <= 0 && v_z > 0)
		pk = LN_E_TROUGH;
	f = dt = 0;
	eo = o;
	ev = v;
	if (pk)
	{
		po = ln_po[s];
		pv = ln_pv[s];
		dt = t - ln_pt[s];
		f  = (pv_z != v_z) ? bound(0, pv_z / (pv_z - v_z), 1) : 1;
		eo = po + (o - po) * f;
		eo_z = po_z + 0.5 * pv_z * f * dt;
		ev = pv + (v - pv) * f;
		ev_z = 0;
	}

	// The far side: the body, or the turn it has just made, is clear of the one waiting.
	if (ln_pkk[s])
	{
		z = o_z;
		if (pk)
			z = (ln_pkk[s] == LN_E_APEX) ? min(z, eo_z) : max(z, eo_z);
		Line_PeakFar(s, z);
	}
	if (!pk)
		return;
	if (ln_pkk[s] == pk)
	{
		// The same kind again before the first was clear: the higher top, the lower bottom.
		w = ln_pko[s];
		if ((pk == LN_E_APEX) ? (eo_z <= w_z) : (eo_z >= w_z))
			return;
	}
	else if (ln_pkk[s] || pk == ln_pklast[s])
		return;                     // the other kind inside LN_EVDZ of the one waiting: a wobble
	else if ((pk == LN_E_APEX) ? (eo_z - ln_pkz[s] < LN_EVDZ) : (ln_pkz[s] - eo_z < LN_EVDZ))
		return;                     // the near side
	ln_pkk[s]   = pk;
	ln_pkcov[s] = here;
	ln_pkt[s]   = ln_pt[s] + f * dt;
	ln_pko[s]   = eo;
	ln_pkv[s]   = ev;
	ln_pki[s]   = ln_nsamp[s];
	ln_pkc[s]   = t;
};

/*
  A sample BEFORE the shown window: its state only, no point and no mark.

  Slot 0's scan starts one sample early (rec_wt_bline) so its first shown point
  has a predecessor; a board line's job skips straight to its window and had
  none, which made the two mark the same run differently at its first contact.
  Exactly ONE sample seeds, in both -- a longer history would warm this slot's
  ramp hold while slot 0 starts it cold, and they would disagree again.
*/
void(float s, vector o, vector v, float fl, float t, float yaw) Line_Seed =
{
	Line_Was(s, Line_Contact(s, v, fl, t), v, fl);
	ln_pyaw[s] = yaw;
	ln_pt[s] = t;
	ln_po[s] = o;                   // a turnaround before the first shown sample is
	ln_pv[s] = v;                   // stamped between the two, as slot 0's is
	Line_PeakReset(s, o_z);
	ln_phere[s] = FALSE;
	ln_nsamp[s] = 0;                // the window's first sample is ordinal 0
};

/*
  One sample, classified, then handed to Line_Add.  Patch 449.

  It runs ABOVE Line_Add's decimation return on purpose: once a slot has halved
  or is striding, half the samples never reach the point array, and a hop
  landing on one of them would vanish.  Same reason ln_pbrk is set up there.

  `stitch`: this sample is where a save state was loaded (a resume/retry record
  sits in the interval before it).  It is marked whatever the contact did --
  a load also moves the body, so brk is set here too and the contact edge across
  it is suppressed as meaningless.
*/
void(float s, vector o, vector v, float fl, float t, float brk, float stitch,
     vector aux) Line_Point =
{
	local float k, q, here, r;
	local vector edge;

	// aux is [yaw, the plane's z, wishdir . plane] -- one parm slot rather than
	// three, which is what keeps this call inside fteqcc's eight.
	if (brk)
	{
		// A ramp hold cannot bridge a teleport into free air or another ride.
		ln_ron[s] = FALSE;
		ln_rlast[s] = t - 999;
		ln_pt[s] = t;              // no turn grade across a discontinuity
	}
	q = Line_Grade(s, v, fl, t, aux);
	k = Line_Contact(s, v, fl, t);
	if (k == SEG_NONE && ln_pkind[s] != SEG_NONE)
		ln_gsince[s] = t;               // this ground phase began here

	if (brk)
		Line_Ev(s, LN_E_BREAK, 0, t, o, v);
	if (stitch)
		Line_Ev(s, LN_E_STITCH, 0, t, o, v);
	// A leave stamped behind either mark would be out of order (a stitch on a
	// repeated clock arrives with no break, and the hold survives it).
	if (brk || stitch)
	{
		ln_rcf[s * 2] = -1;
		Line_EdgeClear(s);
	}

	here = FALSE;                   // a contact mark sits on this very sample
	// Not across a break (the body moved), nor before anything is known.
	if (!brk && ln_pkind[s] >= 0)
	if (k != ln_pkind[s])
	{
		here = TRUE;
		if (k == SEG_NONE || k == SEG_RAMP)
			Line_Ev(s, LN_E_LAND, ln_pkind[s] * 4 + k, t, o, v);
		else if (ln_pkind[s] == SEG_RAMP)
		{
			// ALWAYS a leave, never a hop: +jump held through a whole surf would
			// otherwise put a double chevron on every ramp exit.
			// Patch 608: the edge is seen when the hold runs out, and the mark
			// goes back to the ride's last real contact -- 0.09 s and a median
			// 211 u earlier on the surf_kitsune fixture (84..315).
			// Patch 628: and from there to the ramp's own edge, where the loaded
			// map can say where the hull left it (Line_Edge).
			if (ln_rcf[s * 2] >= 0)
			{
				if (Line_Edge(s, o, v, t))
					Line_EvAt(s, LN_E_LEAVE, ln_pkind[s] * 4 + k, ln_ext, ln_exo, ln_exv,
					          ln_exi, t);
				else
				{
					ln_xhow[s * 4] = ln_xhow[s * 4] + 1;
					Line_EvAt(s, LN_E_LEAVE, ln_pkind[s] * 4 + k, ln_rcf[s * 2 + 1],
					          ln_rcv[s * 2], ln_rcv[s * 2 + 1], ln_rcf[s * 2], t);
				}
				here = FALSE;
			}
			else
			{
				ln_xhow[s * 4] = ln_xhow[s * 4] + 1;    // every ramp leave is counted once
				Line_Ev(s, LN_E_LEAVE, ln_pkind[s] * 4 + k, t, o, v);
			}
		}
		else
			Line_Ev(s, ln_gjmp[s] ? LN_E_JUMP : LN_E_LEAVE,
			        ln_pkind[s] * 4 + k, t, o, v);
	}

	// The tops and bottoms (Line_Peak): in the air, on a ramp and across the
	// change between them -- most of a surf run's bottoms are ON a ramp.  Never
	// on or beside ground (a takeoff is not a bottom), nor across a break.
	if (brk || stitch || ln_pkind[s] < 0 || k == SEG_NONE || ln_pkind[s] == SEG_NONE)
	{
		// A landing on ground is itself the far side of a turn that waits: a
		// hop onto a ledge 9 u under its top was marked or not by where the
		// last air sample fell.
		if (!brk && !stitch && k == SEG_NONE && ln_pkind[s] > SEG_NONE)
			Line_PeakFar(s, o_z);
		Line_PeakReset(s, o_z);
	}
	else
		Line_Peak(s, o, v, t, here || ln_phere[s]);
	ln_phere[s] = here;

	/*
	  The ride's last real contact.  On the two authored exits measured the bit
	  stayed set through the tick the hull left in (tools/OFFRAMP_CONTACT.md), so
	  that sample is the first at or past the exit.  A ride with no contact of
	  its own since the slot began or the last break or stitch -- or one the hold
	  opened as the body left ground -- takes its first such sample, which keeps
	  the marks in sample order.
	*/
	if (k != SEG_RAMP)
		ln_rcf[s * 2] = -1;
	else if ((fl & (WT_F_RAMP | WT_F_RAMPI)) || ln_rcf[s * 2] < 0)
	{
		ln_rcf[s * 2]     = ln_nsamp[s];
		ln_rcf[s * 2 + 1] = t;
		ln_rcv[s * 2]     = o;
		ln_rcv[s * 2 + 1] = v;
	}

	// Line_Edge's records.  A contact sample moves the last one back and takes
	// its place; a sample in the hold's gap is asked of the map until one is off.
	// Nothing here for a slot that will not place (the switch, a file with no
	// plane): it was 8 budget events a sample on the longest import's open.
	if (ln_xon[s])
	{
		if (k != SEG_RAMP)
		{
			if (ln_xi[s * 4] >= 0)      // [0] is the first record a ride sets
				Line_EdgeClear(s);
		}
		else if (fl & (WT_F_RAMP | WT_F_RAMPI))
		{
			Line_EdgeSet(s, 1, ln_xi[s * 4], ln_xt[s * 4], ln_xo[s * 4], ln_xv[s * 4], ln_xn[s * 4]);
			ln_xd[s * 4 + 1] = ln_xd[s * 4];
			Line_EdgeSet(s, 0, ln_nsamp[s], t, o, v, ln_chave[s] ? ln_cn[s] : '0 0 0');
			ln_xi[s * 4 + 2] = ln_xi[s * 4 + 3] = -1;
			ln_xq[s] = FALSE;
		}
		else if (ln_chave[s])
		if (!ln_xq[s])
		if (ln_xi[s * 4 + 3] < 0)
		{
			// The plane of a record that is HELD: [2], else [0].
			edge = '0 0 0';
			if (ln_xi[s * 4 + 2] >= 0)
				edge = ln_xn[s * 4 + 2];
			else if (ln_xi[s * 4] >= 0)
				edge = ln_xn[s * 4];
			if (edge != '0 0 0')
			{
				r = Line_OnRamp(o, edge, ln_cd[s]);
				if (r > 0)
					Line_EdgeSet(s, 2, ln_nsamp[s], t, o, v, ln_hitn);
				else if (r == 0)
					Line_EdgeSet(s, 3, ln_nsamp[s], t, o, v, '0 0 0');
				else
					ln_xq[s] = TRUE;    // the map cannot say: this leave stays as stamped
			}
		}
	}
	ln_chave[s] = FALSE;

	Line_Was(s, k, v, fl);
	ln_pyaw[s] = aux_x;
	ln_pt[s] = t;
	ln_po[s] = o;
	ln_pv[s] = v;
	if (!ln_nsamp[s])
	{
		ln_z0[s]  = o_z;        // the run's own start, one choice of energy zero
		ln_v20[s] = v * v;
	}
	ln_nsamp[s] = ln_nsamp[s] + 1;
	Line_Add(s, o, vlen([v_x, v_y, 0]), v_z, q, t, brk);
};

/*
  Slot s's speed range over points ia..ib at or after tsc: mean +- 2 sd inside
  min..max.  A stop after a teleport or a restart put min at 0 and drew a whole
  stage one green (p432shot).
*/
void(float s, float ia, float ib, float tsc) Line_SpeedRange =
{
	local float b, i, v, n, sum, sq, mn, mx, sd;

	b = LN_B(s);
	n = sum = sq = 0;
	mn = 99999;
	mx = 0;
	for (i = ia; i <= ib; i = i + 1)
	{
		if (ln_t[b + i] < tsc)
			continue;
		v = ln_spd[b + i];
		mn = min(mn, v);
		mx = max(mx, v);
		sum = sum + v;
		sq = sq + v * v;
		n = n + 1;
	}
	ln_lo[s] = 0;
	ln_hi[s] = 1;
	if (n > 0)
	{
		v = sum / n;
		sd = sqrt(max(0, sq / n - v * v));
		ln_lo[s] = max(mn, v - 2 * sd);
		ln_hi[s] = min(mx, v + 2 * sd);
		if (ln_hi[s] <= ln_lo[s])
			ln_hi[s] = ln_lo[s] + 1;
	}
};

// The tables drawing needs: chunk spheres, the break list, the gain.
void(float s) Line_End =
{
	local float b, n, c, i, i0, i1, j0, j1, k, dt;
	local vector mn, mx, p;

	b = LN_B(s);
	n = ln_n[s];
	// Patch 632: your own line has a speed range too.  Only Line_Range set one and
	// nothing calls it for the trail, so "speed" over your line alone was 0..0 and
	// every point the slow end's red (58 of 58 on a 116-point line, the review).
	if (LN_TRAIL(s))
		Line_SpeedRange(s, 0, n - 1, -99999999);
	// One demo fade, not a stagger restarted every chunk. Live births belong
	// to sample arrival in Line_Add; bulk rebuilds never reset their ages.
	if (s == 0)
		for (i = ln_published[s]; i < n; i = i + 1)
			ln_born[Line_BirthBase(s) + i] = cltime;
	ln_published[s] = n;
	ln_bkn[s] = 0;
	for (i = 1; i < n; i = i + 1)
		if (ln_brk[b + i])
		if (ln_bkn[s] < LN_BKCAP)
		{
			ln_bk[s * LN_BKCAP + ln_bkn[s]] = i;
			ln_bkn[s] = ln_bkn[s] + 1;
		}

	// Each chunk's box takes the point before it, so the joining segment is in.
	for (c = 0; c * LN_CHUNK < n; c = c + 1)
	{
		i0 = max(0, c * LN_CHUNK - 1);
		i1 = min(n, (c + 1) * LN_CHUNK);
		mn = mx = ln_pos[b + i0];
		k = FALSE;
		for (i = i0; i < i1; i = i + 1)
		{
			p = ln_pos[b + i];
			if (p_x < mn_x) mn_x = p_x;  if (p_x > mx_x) mx_x = p_x;
			if (p_y < mn_y) mn_y = p_y;  if (p_y > mx_y) mx_y = p_y;
			if (p_z < mn_z) mn_z = p_z;  if (p_z > mx_z) mx_z = p_z;
			if (ln_brk[b + i])
				k = TRUE;
		}
		ln_cc[LN_B(s) / LN_CHUNK + c]  = (mn + mx) * 0.5;
		ln_cr[LN_B(s) / LN_CHUNK + c]  = vlen(mx - mn) * 0.5;
		ln_cbk[LN_B(s) / LN_CHUNK + c] = k;
	}
	for (c = 0; c * LN_CHUNK * LN_GROUP < n; c = c + 1)
	{
		i0 = max(0, c * LN_CHUNK * LN_GROUP - 1);
		i1 = min(n, (c + 1) * LN_CHUNK * LN_GROUP);
		mn = mx = ln_pos[b + i0];
		for (i = i0; i < i1; i = i + 1)
		{
			p = ln_pos[b + i];
			if (p_x < mn_x) mn_x = p_x;  if (p_x > mx_x) mx_x = p_x;
			if (p_y < mn_y) mn_y = p_y;  if (p_y > mx_y) mx_y = p_y;
			if (p_z < mn_z) mn_z = p_z;  if (p_z > mx_z) mx_z = p_z;
		}
		ln_gc[LN_B(s) / LN_CHUNK / LN_GROUP + c] = (mn + mx) * 0.5;
		ln_gr[LN_B(s) / LN_CHUNK / LN_GROUP + c] = vlen(mx - mn) * 0.5;
	}

	// Gain, u/s per s, over up to two samples each side within the same piece.
	for (i = 0; i < n; i = i + 1)
	{
		j0 = i;
		j1 = i;
		for (k = 0; k < 2; k = k + 1)
		{
			if (j0 > 0)
			if (!ln_brk[b + j0])
				j0 = j0 - 1;
			if (j1 + 1 < n)
			if (!ln_brk[b + j1 + 1])
				j1 = j1 + 1;
		}
		dt = ln_t[b + j1] - ln_t[b + j0];
		ln_gain[b + i] = (dt > 0) ? (ln_spd[b + j1] - ln_spd[b + j0]) / dt : 0;
	}

	/*
	  The stride errors: for each chunk and level L, the furthest any sample lies
	  from the polyline through every 2^L-th point (the chunk's first and last
	  kept), in units.  A chunk holding a break never strides.
	*/
	for (c = 0; c * LN_CHUNK < n; c = c + 1)
	{
		i0 = c * LN_CHUNK;
		i1 = min(n, i0 + LN_CHUNK) - 1;
		k = (LN_B(s) / LN_CHUNK + c) * LN_LEVELS;
		for (j0 = 1; j0 <= LN_LEVELS; j0 = j0 + 1)
		{
			dt = 0;
			if (ln_cbk[LN_B(s) / LN_CHUNK + c])
				dt = 99999;
			else
			{
				j1 = pow(2, j0);
				for (i = i0 + 1; i < i1; i = i + 1)
				{
					mn = ln_pos[b + i0 + floor((i - i0) / j1) * j1];
					mx = ln_pos[b + min(i0 + (floor((i - i0) / j1) + 1) * j1, i1)] - mn;
					p  = ln_pos[b + i] - mn;
					dt = max(dt, vlen(p - mx * bound(0, (mx * mx > 0) ? (p * mx) / (mx * mx) : 0, 1)));
				}
			}
			ln_cerr[k + j0 - 1] = dt;
		}
	}

	ln_ia[s] = 0;
	ln_ib[s] = n - 1;
	ln_on[s] = (n >= 2);
	ln_sgen[s] = ln_sgen[s] + 1;
};

/*
  SHOW ONLY [ta, tb] OF RUN TIME, wherever the camera is.

  The distance cull answers "is it near me"; this answers "is it near where I
  am WATCHING", which is the question a replay actually asks.  It composes with
  the shown range by intersection -- a stage cut always wins and the window can
  only narrow it -- and with `ahead 0`, which clamps afterwards as it always did.

  ln_winon is set by the caller and never derived from tplay: a board line is
  drawn with tplay 99999999 to mean "no playhead", and `if (tplay < 99999)`,
  the obvious shortcut, makes every board line draw nothing.  p449win W5.
*/
void(float ta, float tb) Line_Window =
{
	ln_winon = TRUE;
	ln_wina  = ta;
	ln_winb  = tb;
	// Faded over a sixth of the span at each end: a line that stops dead reads
	// as a break in the recording rather than as the edge of a window.
	ln_winka = (tb > ta) ? 6 / (tb - ta) : 0;
	ln_winkb = ln_winka;
};

void() Line_WindowOff =
{
	ln_winon = FALSE;
};

// Patch 624. Once a frame, before the lines that follow the viewer are drawn: a run
// that starts again (the clock steps back, or the timer arms) leaves no cursor believed
// for LN_FO_FRESH, so the stretch taken is the earliest and not the one nearest in time
// to where the last run had got to. Not for one frame: the stats arrive before the view
// does, and a forget spent where the viewer still was took the old place's stretch.
/*
  Patch 649: THE FOLLOW SEARCH'S COST IS PER LINE, so past eight lines it is
  thinned: with n drawn, a look at a whole line comes every LN_FO_EVERY * n/8
  seconds (64 lines: 2 s each, 32 looks a second in all as with eight) and the
  cursor is tracked over LN_FO_NEAR * 8/n samples either side, 12 at least.
  Up to eight lines nothing changes.  Scores_LinesDraw says how many.
*/
float  ln_fo_scale, ln_fo_near, ln_fo_budget;
#define LN_FO_JUMP  512         // units further in one frame than any speed carries a viewer
void(float lines) Line_FollowScale =
{
	ln_fo_scale = max(1, ceil(lines / 8));
	ln_fo_near = max(12, floor(LN_FO_NEAR / ln_fo_scale));
};

void() Line_FollowFrame =
{
	local float clock, state;

	ln_fo_budget = 4;               // Patch 649: looks a moved viewer may ask for this frame
	clock = getstatf(STAT_FS_TIMERTICKS);
	state = getstatf(STAT_FS_TIMERSTATE);
	if (clock < ln_fo_clock || (state == TS_ARMED && ln_fo_state != TS_ARMED))
		ln_fo_fresh = cltime + LN_FO_FRESH;
	ln_fo_clock = clock;
	ln_fo_state = state;
};

// One stretch of a look: its nearest sample and how near. The LN_FO_SPOTS nearest are kept.
float ln_fo_sn;
void(float i, float d) Line_FollowSpot =
{
	local float m, j;

	m = ln_fo_sn;
	if (ln_fo_sn < LN_FO_SPOTS)
		ln_fo_sn = ln_fo_sn + 1;
	else
	{
		m = 0;
		for (j = 1; j < LN_FO_SPOTS; j = j + 1)
			if (ln_fo_sd[j] > ln_fo_sd[m])
				m = j;
		if (d >= ln_fo_sd[m])
			return;
	}
	ln_fo_si[m] = i;
	ln_fo_sd[m] = d;
};

// The run clock of slot s's sample nearest the eye, in run order; -1 for no line.
float(float s) Line_Follow =
{
	local float b, ia, ib, i, j, d, best, bi, lo, hi, stride, half, tol, tprev, k, bk, have, prev, n, m;
	local float open, obi, obk, mseg, left;
	local vector p, pp, pn;

	b  = LN_B(s);
	ia = ln_ia[s];
	ib = ln_ib[s];
	if (!ln_on[s] || ib < ia)
		return -1;
	have = (ln_fo_gen[s] == ln_graphgen[s] + 1);
	prev = have;
	if (cltime < ln_fo_fresh)
		prev = FALSE;
	tprev = 0;
	if (have)
	{
		// Followed: the nearest of the samples round the cursor, and the LAST of equals,
		// so it walks through a stop in the recording instead of resting at its start
		// (a 9 s stop left nothing drawn ahead of the viewer). A line's own teleport is
		// two neighbouring samples, so the cursor crosses it with the viewer.
		lo = max(ia, ln_fo_i[s] - ln_fo_near);
		hi = min(ib, ln_fo_i[s] + ln_fo_near);
		best = 99999999;
		bi = lo;
		for (i = lo; i <= hi; i = i + 1)
		{
			d = vlen(ln_pos[b + i] - ln_eye);
			if (d <= best)
			{
				best = d;
				bi = i;
			}
		}
		// Patch 649: the viewer was moved (a fail back to a stage start, a saveloc):
		// the samples round the cursor are suddenly far.  Asked for a look now.
		if (ln_fo_scale > 1)
		if (best > ln_fo_d[s] + LN_FO_JUMP)
			ln_fo_jump[s] = TRUE;
		ln_fo_i[s] = bi;
		ln_fo_d[s] = best;
		tprev = ln_t[b + bi];
		k = (prev ? LN_FO_EVERY : LN_FO_SOON) * ln_fo_scale;
		if (ln_fo_scale > 1)
		{
			// Past eight lines a slot looks once an interval AT ITS OWN SIXTEENTH of
			// it, whenever it last looked: measured from the last look, the first
			// restart put every line's look on one frame for good (the review's
			// model: fifty on one frame every two seconds).  A moved viewer's look
			// does not wait for it, four lines a frame.
			j = (s - 16 * floor(s / 16)) / 16;
			if (ln_fo_jump[s] && ln_fo_budget > 0)
				ln_fo_budget = ln_fo_budget - 1;
			else if (floor(cltime / k - j) == floor(ln_fo_at[s] / k - j))
				return tprev;
		}
		else
		{
			if (cltime >= ln_fo_at[s])
			if (cltime - ln_fo_at[s] < k)
				return tprev;
		}
	}
	// The whole line. 512 samples of it say how near it comes... (A slot's first look is
	// back-dated by its number, so eight lines do not all look on one frame.)
	ln_fo_at[s] = cltime;
	ln_fo_jump[s] = FALSE;
	if (!have)
	if (ln_fo_scale <= 1)
		ln_fo_at[s] = cltime - s * 0.03;
	ln_fo_n[s] = ln_fo_n[s] + 1;
	stride = max(1, ceil((ib - ia + 1) / 512));
	half = floor(stride * 0.5);
	best = 99999999;
	bi = ia;
	mseg = 0;
	pp = ln_pos[b + ia];
	for (i = ia; i <= ib; i = i + stride)
	{
		p = ln_pos[b + i];
		mseg = max(mseg, vlen(p - pp));
		pp = p;
		d = vlen(p - ln_eye);
		if (d < best)
		{
			best = d;
			bi = i;
		}
	}
	// A line with no sample that could be inside hud_watch_path_far draws nothing: the
	// nearest of the 512 will do, and a viewer far from eight long lines pays for no more.
	if (ln_far > 0)
	if (best - mseg > ln_far)
	{
		if (!have || ln_fo_i[s] != bi)
			ln_fo_mv[s] = ln_fo_mv[s] + 1;
		ln_fo_i[s] = bi;
		ln_fo_d[s] = best;
		ln_fo_gen[s] = ln_graphgen[s] + 1;
		return ln_t[b + bi];
	}
	// ...and wherever one of them could have a point that near beside it, every sample
	// is looked at: the 512 are up to 128 samples apart, hundreds of units at speed,
	// against a tolerance of 128 u (the first cut took the later pass a quarter of the
	// time at 2000 u/s). A sample between two is at most their spacing nearer than either.
	// A run of such samples is one stretch, one pass by the eye, and gives one spot.
	tol = max(best * 1.5, best + 128);
	ln_fo_sn = 0;
	open = FALSE;
	obi = obk = 0;
	left = LN_FO_READ;
	pp = ln_pos[b + ia];
	for (i = ia; i <= ib; i = i + stride)
	{
		p = ln_pos[b + i];
		pn = ln_pos[b + min(ib, i + stride)];
		d = vlen(p - ln_eye) - max(vlen(p - pp), vlen(pn - p));
		pp = p;
		if (d > tol)
		{
			if (open)
				Line_FollowSpot(obi, obk);
			open = FALSE;
			continue;
		}
		lo = max(ia, i - half);
		hi = min(ib, i + half);
		if (left <= 0)
			lo = hi = i;
		left = left - (hi - lo + 1);
		for (j = lo; j <= hi; j = j + 1)
		{
			d = vlen(ln_pos[b + j] - ln_eye);
			if (!open || d < obk)
			{
				obk = d;
				obi = j;
				open = TRUE;
			}
		}
	}
	if (open)
		Line_FollowSpot(obi, obk);
	n = ln_fo_sn;
	// Which stretch, when the route passes here more than once: of those as near as the
	// nearest, the one being followed; else the one nearest in time to it; or with no
	// cursor believed (a new line, a new run) the earliest.
	best = 99999999;
	for (j = 0; j < n; j = j + 1)
		if (ln_fo_sd[j] < best)
			best = ln_fo_sd[j];
	tol = max(best * 1.5, best + 128);
	if (prev)
	if (ln_fo_d[s] <= tol)
		return tprev;
	m = -1;
	bk = 99999999;
	for (j = 0; j < n; j = j + 1)
	{
		if (ln_fo_sd[j] > tol)
			continue;
		k = ln_fo_si[j] - ia;
		if (prev)
			k = fabs(ln_t[b + ln_fo_si[j]] - tprev);
		if (k < bk)
		{
			bk = k;
			m = j;
		}
	}
	if (m < 0)
		return have ? tprev : -1;
	if (!have || ln_fo_i[s] != ln_fo_si[m])
		ln_fo_mv[s] = ln_fo_mv[s] + 1;
	ln_fo_i[s] = ln_fo_si[m];
	ln_fo_d[s] = ln_fo_sd[m];
	ln_fo_gen[s] = ln_graphgen[s] + 1;
	return ln_t[b + ln_fo_i[s]];
};

// A window of `ahead` seconds of slot s's run from where the viewer is along it, and a
// quarter of that behind; FALSE (and no window) when the slot has no line.
float(float s, float ahead) Line_FollowWindow =
{
	local float t;

	t = Line_Follow(s);
	if (t < 0)
	{
		Line_WindowOff();
		return FALSE;
	}
	ln_fo_ta[s] = t - max(1, ahead * 0.25);
	ln_fo_tb[s] = t + ahead;
	ln_fo_wt[s] = cltime;
	Line_Window(ln_fo_ta[s], ln_fo_tb[s]);
	return TRUE;
};

// The first mark at or after t.  Line_EvAt keeps the list in time order.
float(float s, float t) Line_EvFind =
{
	local float b, lo, hi, m;

	b = s * LN_EVCAP;
	lo = 0;
	hi = ln_evn[s];
	while (lo < hi)
	{
		m = floor((lo + hi) * 0.5);
		if (ln_et[b + m] < t)
			lo = m + 1;
		else
			hi = m;
	}
	return lo;
};

// The first point at or after t (binary search on the run clock).
float(float s, float t) Line_Find =
{
	local float b, lo, hi, m;

	b = LN_B(s);
	lo = 0;
	hi = ln_n[s];
	while (lo < hi)
	{
		m = floor((lo + hi) * 0.5);
		if (ln_t[b + m] < t)
			lo = m + 1;
		else
			hi = m;
	}
	return lo;
};

// Show [ta, tb] of slot s; its colour range is its speeds at or after tsc
// (Line_SpeedRange).
void(float s, float ta, float tb, float tsc) Line_Range =
{
	ln_start[s] = tsc;
	ln_graphgen[s] = ln_graphgen[s] + 1;
	ln_ia[s] = Line_Find(s, ta);
	ln_ib[s] = Line_Find(s, tb + 0.0001) - 1;
	Line_SpeedRange(s, ln_ia[s], ln_ib[s], tsc);
};

// ---- the anti-aliased strip ---------------------------------------------------

// Width w in physical px; sets the half widths the emitters use.
void(float w) Line_Width =
{
	if (w <= 0)
		w = 1;
	ln_pk = min(1, w);
	ln_hw = (max(w, 1) * 0.5 + 0.5) * ln_px;
	ln_cw = (max(w, 1) * 0.5 - 0.5) * ln_px;
	if (ln_nath)
		lines_width(ln_hw, ln_cw, ln_pk, ln_px);    // the engine's copy, for every native emitter
};

void() Line_PxFrame =
{
	local vector ps, vs;

	ps = getproperty(VF_SCREENPSIZE);
	vs = getproperty(VF_SCREENVSIZE);
	ln_px = 1;
	if (ps_x > 0)
		ln_px = vs_x / ps_x;
	// In brackets: QC's `=` binds tighter than `&&`, and bare this was (ln_nat = ln_nath).
	ln_nat = (ln_nath && cvar("hud_lines_native"));
};

// One segment a->b, sides sa/sb (unit, times the mitre factor).  Fans whose
// outer vertices carry alpha 0: a tent at 1 px, a trapezoid (two fans) wider.
void(vector a, vector sa, vector ca, float la, vector b, vector sb, vector cb, float lb) Line_Emit =
{
	local vector oa, ob, ia, ib;

	if (ln_nat)
	{
		lines_segment(a, sa, ca, la, b, sb, cb, lb);
		return;
	}
	oa = sa * ln_hw;
	ob = sb * ln_hw;
	R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
	if (ln_cw <= 0)
	{
		R_PolygonVertex(a,      '0 0 0', ca, la * ln_pk);
		R_PolygonVertex(a + oa, '0 0 0', ca, 0);
		R_PolygonVertex(b + ob, '0 0 0', cb, 0);
		R_PolygonVertex(b,      '0 0 0', cb, lb * ln_pk);
		R_PolygonVertex(b - ob, '0 0 0', cb, 0);
		R_PolygonVertex(a - oa, '0 0 0', ca, 0);
		R_EndPolygon();
		return;
	}
	ia = sa * ln_cw;
	ib = sb * ln_cw;
	R_PolygonVertex(a + ia, '0 0 0', ca, la);
	R_PolygonVertex(a + oa, '0 0 0', ca, 0);
	R_PolygonVertex(b + ob, '0 0 0', cb, 0);
	R_PolygonVertex(b + ib, '0 0 0', cb, lb);
	R_PolygonVertex(b - ib, '0 0 0', cb, lb);
	R_PolygonVertex(a - ia, '0 0 0', ca, la);
	R_EndPolygon();
	R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
	R_PolygonVertex(a - ia, '0 0 0', ca, la);
	R_PolygonVertex(b - ib, '0 0 0', cb, lb);
	R_PolygonVertex(b - ob, '0 0 0', cb, 0);
	R_PolygonVertex(a - oa, '0 0 0', ca, 0);
	R_EndPolygon();
};

// A lone segment in screen units (the mouse pad's trail, a dash): flat ends.
void(vector a, vector b, vector ca, float la, vector cb, float lb) Line_Seg2D =
{
	local vector d;
	local float l;

	d = b - a;
	d_z = 0;
	l = vlen(d);
	if (l < 0.001)
		return;
	d = [d_y, 0 - d_x, 0] * (1 / l);
	Line_Emit(a, d, ca, la, b, d, cb, lb);
};

void() Line_RunEnd =
{
	if (ln_rn >= 2)
	{
		Line_Emit(ln_rq0, ln_rs0, ln_rc0, ln_ra0, ln_rq1, ln_rn1, ln_rc1, ln_ra1);
		ln_nseg = ln_nseg + 1;
	}
	ln_rn = 0;
};

/*
  A screen point onto the strip.  A segment is emitted a point late, when the
  side at its far end (the mitre with the next) is known; a point under a
  quarter pixel from the last is dropped.
*/
void(vector q, vector c, float a) Line_Q =
{
	local vector d, n, m;
	local float l, k;

	ln_npt = ln_npt + 1;
	if (q_x < ln_bbmin_x) ln_bbmin_x = q_x;
	if (q_y < ln_bbmin_y) ln_bbmin_y = q_y;
	if (q_x > ln_bbmax_x) ln_bbmax_x = q_x;
	if (q_y > ln_bbmax_y) ln_bbmax_y = q_y;
	if (ln_rn > 0)
	{
		d = q - ln_rq1;
		l = vlen(d);
		if (l < 0.25 * ln_px)
			return;
		n = [d_y, 0 - d_x, 0] * (1 / l);
		if (ln_rn == 1)
			ln_rs0 = n;
		else
		{
			m = ln_rn1 + n;
			l = vlen(m);
			if (l < 0.1)
				m = n;              // doubled back: no mitre to take
			else
			{
				m = m * (1 / l);
				k = m * n;
				m = m * (1 / ((k > 0.5) ? k : 0.5));
			}
			Line_Emit(ln_rq0, ln_rs0, ln_rc0, ln_ra0, ln_rq1, m, ln_rc1, ln_ra1);
			ln_nseg = ln_nseg + 1;
			ln_rs0 = m;
		}
		ln_rq0 = ln_rq1;
		ln_rc0 = ln_rc1;
		ln_ra0 = ln_ra1;
		ln_rn1 = n;
		ln_rn = 2;
	}
	else
	{
		ln_rn = 1;
		if (ln_nseg == 0)
			ln_first = q;
	}
	ln_rq1 = q;
	ln_rc1 = c;
	ln_ra1 = a;
};

// A projected point's guard: FALSE for a near-plane stub beside the eye (the
// strip is ended there).
float(vector q) Line_Sane =
{
	if (q_z < -1 || q_x > LN_GUARD || q_x < -LN_GUARD || q_y > LN_GUARD || q_y < -LN_GUARD)
	{
		ln_nwild = ln_nwild + 1;
		Line_RunEnd();
		return FALSE;
	}
	return TRUE;
};

// A world point in front of the near plane, onto the strip.
void(vector w, vector c, float a) Line_Pt =
{
	local vector q;

	q = project(w);
	if (!Line_Sane(q))
		return;
	q_z = 0;
	Line_Q(q, c, a);
};

// ---- colour -------------------------------------------------------------------

// Point i's colour: speed red -> yellow -> green over the shown range, or
// gain (u/s per s) grey -> green, loss grey -> red, full at 800.
vector(float i, float m) Line_Col =
{
	local float f;

	if (m == 1)
	{
		f = bound(-1, ln_gain[i] / 800, 1);
		if (f >= 0)
			return '0.85 0.85 0.85' + ('-0.55 0.15 -0.45' * f);
		return '0.85 0.85 0.85' + ('0.15 -0.60 -0.60' * (0 - f));
	}
	f = bound(0, (ln_spd[i] - ln_slo) * ln_sinv, 1);
	if (f < 0.5)
		return '1.00 0.22 0.22' + ('0.00 0.68 0.00' * (f * 2));
	return '1.00 0.90 0.22' + ('-0.70 0.10 0.13' * ((f - 0.5) * 2));
};

/*
  CONTACT: ground, ramp or air, as a colour rather than a glyph.

  Taken from the MARKS, which are the edges of exactly this function, so the
  colour and the chevrons cannot disagree -- and no per-point kind has to be
  stored to do it.  A phase runs from one contact mark to the next, and a
  mark's sub-code carries the pair it crossed (from * 4 + to).
*/
void(float s) Line_ColContact =
{
	local float b, e, n, i, k, upto, sub;
	local vector c;

	b = LN_B(s);
	n = s * LN_EVCAP;
	// Before the first contact mark the run was in that mark's `from` state.
	k = -1;
	for (e = 0; e < ln_evn[s]; e = e + 1)
		if (ln_ek[n + e] <= LN_E_JUMP)
		{
			k = floor(ln_es[n + e] / 4);
			break;
		}
	e = 0;
	i = 0;
	while (i < ln_n[s])
	{
		// The next contact mark closes this phase.
		upto = ln_n[s];
		while (e < ln_evn[s])
		{
			if (ln_ek[n + e] <= LN_E_JUMP)
			{
				upto = Line_Find(s, ln_et[n + e]);
				break;
			}
			e = e + 1;
		}
		if (k == SEG_NONE)      c = '1.00 0.62 0.20';    // ground, the V's colour
		else if (k == SEG_RAMP) c = '0.35 0.85 1.00';    // riding a plane
		else if (k == SEG_AIR)  c = '0.85 0.88 0.95';    // neither
		else                    c = '0.45 0.45 0.50';    // before the first mark
		while (i < upto && i < ln_n[s])
		{
			ln_col[b + i] = c;
			i = i + 1;
		}
		if (e >= ln_evn[s])
		{
			while (i < ln_n[s])
			{
				ln_col[b + i] = c;
				i = i + 1;
			}
			return;
		}
		sub = ln_es[n + e];
		k = sub - floor(sub / 4) * 4;
		e = e + 1;
	}
};

/*
  ENERGY GAINED OR LOST, against the most air strafing can add.

  E = z + |v|^2/2g (Strafe_Energy), differenced over the same two-samples-each-
  side window the speed gain uses, and divided by Strafe_PowerCeiling -- the
  denominator the live strafe gauge already normalises by, so full green here
  and a full gauge there mean the same thing.  Speed and energy are NOT the
  same colour: a surfer trading height for speed reads green on gain and flat
  here, which is the point of having both.
*/
void(float s) Line_ColEnergy =
{
	local float b, i, j0, j1, dt, f, p, e0, e1;
	local vector o;

	b = LN_B(s);
	// pm_maxairspeed, not a literal 30: the grade in Line_Grade reads the
	// server's, and two air caps in one file is how the line would come to
	// disagree with itself on a server that changed it.
	p = Strafe_PowerCeiling(ln_mv_aircap, ln_grav, ln_tick[s]);
	if (p <= 0)
		p = 37.5;
	for (i = 0; i < ln_n[s]; i = i + 1)
	{
		j0 = j1 = i;
		for (dt = 0; dt < 2; dt = dt + 1)
		{
			if (j0 > 0)
			if (!ln_brk[b + j0])
				j0 = j0 - 1;
			if (j1 + 1 < ln_n[s])
			if (!ln_brk[b + j1 + 1])
				j1 = j1 + 1;
		}
		dt = ln_t[b + j1] - ln_t[b + j0];
		o = ln_pos[b + j0];
		e0 = o_z + (ln_spd[b + j0] * ln_spd[b + j0]
		            + ln_vz[b + j0] * ln_vz[b + j0]) / (2 * ln_grav);
		o = ln_pos[b + j1];
		e1 = o_z + (ln_spd[b + j1] * ln_spd[b + j1]
		            + ln_vz[b + j1] * ln_vz[b + j1]) / (2 * ln_grav);
		f = (dt > 0) ? bound(-1, ((e1 - e0) / dt) / p, 1) : 0;
		if (f >= 0)
			ln_col[b + i] = '0.85 0.85 0.85' + ('-0.55 0.15 -0.45' * f);
		else
			ln_col[b + i] = '0.85 0.85 0.85' + ('0.15 -0.60 -0.60' * (0 - f));
	}
};

/*
  AIR CONTROL, as the strafe bar grades it: green good, red poor, and GREY
  where there is no answer.  HUD_QualityColor is the bar's own ramp, so a
  stretch of line and the bar at that moment are the same colour.
*/
void(float s) Line_ColQuality =
{
	local float b, i;

	b = LN_B(s);
	for (i = 0; i < ln_n[s]; i = i + 1)
		ln_col[b + i] = HUD_QualityColor(ln_q[b + i]);
};

// The colouring a slot is drawn in: its group's.
float(float s) Line_Mode =
{
	return (LN_TRAIL(s)) ? ln_cmown : ln_cmoth;
};

// A shown line's time: its window's end less the clock its window counts from
// (Line_Range), so a stage line is the stage's time and a run the run's.
float(float s) Line_Time =
{
	return ln_t[LN_B(s) + ln_ib[s]] - ln_start[s];
};

float() Watch_PathMode;         // cl_watch.qc: 1 or 2 when a drawer draws the demo's line

/*
  BY TIME: the fastest of the other lines green, the slowest red, the rest
  between through yellow (the speed ramp's three colours, turned round).  Over the
  lines that are being shown, so hiding the demo or the board's lines re-ranks
  what is left; one line alone is green.  Nine slots: every frame, no cache.

  Among lines of ONE LEG: a stage's time beside a whole run's says nothing about
  either (measured: stage 2 of a file placed ahead of the same file whole), and a
  ticked line outlives the leg the board showed when it was ticked.  Equal times
  share a place: a run both watched and ticked is one run in two slots, and the
  review's lone run came out red over green.
*/
void() Line_Rank =
{
	local float s, o, n, r, t, f, demo, board;

	demo  = cvar("hud_watch_path");
	if (demo)
	{
		f = Watch_PathMode();
		demo = (f == 1 || f == 2);
	}
	board = cvar("hud_lines_board");
	// Patch 649: who is ranked and on what time, and a sum that moves when any of it does.
	// With sixty-five slots the pairing below is 4,225 turns, so it is done on a change
	// and not every frame.
	f = 0;
	for (s = 0; s < LN_SLOTS; s = s + 1)
	{
		ln_rkin[s] = FALSE;
		if (LN_TRAIL(s))
			continue;                   // the live run's own: not ranked among the others
		if (!ln_on[s])
			continue;
		if (ln_n[s] < 1)
			continue;
		if (ln_ib[s] < ln_ia[s])
			continue;                   // nothing of it in its window: no time to read
		if (!(s ? board : demo))
			continue;
		ln_rkin[s] = TRUE;
		ln_rkt[s] = Line_Time(s);
		f = f + (s + 1) * (ln_rkt[s] + 3 * ln_track[s] + 7 * ln_leg[s] + 11);
	}
	if (f == ln_rksum)
		return;
	ln_rksum = f;
	for (s = 0; s < LN_SLOTS; s = s + 1)
	{
		r = 0;
		n = 0;
		if (ln_rkin[s])
		{
			t = ln_rkt[s];
			for (o = 0; o < LN_SLOTS; o = o + 1)
			{
				if (!ln_rkin[o])
					continue;
				if (ln_track[o] != ln_track[s] || ln_leg[o] != ln_leg[s])
					continue;           // another leg's line: another list
				n = n + 1;
				if (o != s)
				if (ln_rkt[o] < t)
					r = r + 1;
			}
		}
		ln_rkpos[s] = r;
		ln_rkof[s]  = n;
		f = (n > 1) ? r / (n - 1) : 0;
		if (f < 0.5)
			ln_rk[s] = '0.30 1.00 0.35' + ('0.70 -0.10 -0.13' * (f * 2));
		else
			ln_rk[s] = '1.00 0.90 0.22' + ('0.00 -0.68 0.00' * ((f - 0.5) * 2));
	}
};

// Slot s's colours from point `from` on, in mode m.  Contact, energy and air
// control are whole-slot walks whatever `from` says (see Line_ViewFrame).
void(float s, float m, float from) Line_Paint =
{
	local float i, b;
	local vector c;

	if (m == 2) { Line_ColContact(s); return; }
	if (m == 3) { Line_ColEnergy(s);  return; }
	if (m == 4) { Line_ColQuality(s); return; }
	b = LN_B(s);
	if (m >= LN_CM_PLAIN)
	{
		c = (LN_TRAIL(s)) ? LN_OWNCOL : ln_rk[s];
		for (i = b + from; i < b + ln_n[s]; i = i + 1)
			ln_col[i] = c;
		return;
	}
	for (i = b + from; i < b + ln_n[s]; i = i + 1)
		ln_col[i] = Line_Col(i, m);
};

// ---- per frame ------------------------------------------------------------------

// The view the lines are projected against, and the shared colour range.
void() Line_ViewFrame =
{
	local vector fov, c;
	local float s, m, dirty, rd;

	Line_PxFrame();
	ln_wpx  = cvar("hud_watch_path_px");
	ln_wpxb = cvar("hud_watch_path_px_board");
	ln_wpxt = cvar("hud_watch_path_px_trail");
	Line_Width(ln_wpx);
	ln_reveal = bound(0, cvar("hud_lines_reveal"), 1);
	ln_eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	ln_fwd = v_forward;
	ln_rt  = v_right;
	ln_up  = v_up;
	fov = getproperty(VF_FOV);
	ln_tx = tan(bound(1, fov_x, 179) * (M_PI / 360));
	ln_ty = tan(bound(1, fov_y, 179) * (M_PI / 360));
	ln_kx = sqrt(1 + ln_tx * ln_tx);
	ln_ky = sqrt(1 + ln_ty * ln_ty);
	fov = getproperty(VF_SCREENPSIZE);
	ln_labelscreen = fov;
	ln_tolk = LN_PXERR * ln_tx / max(1, fov_x * 0.5);
	ln_far  = cvar("hud_watch_path_far");
	ln_fadek = (ln_far > 0) ? 3 / ln_far : 0;       // fades over its last third
	ln_cmown = bound(0, cvar("hud_lines_color_own"), LN_CM_PLAIN);
	ln_cmoth = bound(0, cvar("hud_lines_color_others"), LN_CM_PLAIN);
	// The marks, read once a frame beside the rest.
	ln_mkon     = cvar("hud_lines_marks");
	ln_mkmax    = cvar("hud_lines_marked");
	ln_mkland   = cvar("hud_lines_land");
	ln_mkleave  = cvar("hud_lines_leave");
	ln_mkjump   = cvar("hud_lines_jump");
	ln_mkstitch = cvar("hud_lines_stitch");
	ln_mkpx     = cvar("hud_lines_size");   if (ln_mkpx < 1) ln_mkpx = 4;
	ln_declutter = cvar("hud_lines_declutter");
	ln_sparse   = (ln_declutter == 1);
	ln_lanes    = (ln_declutter == 2);
	// Patch 661: the numbers' own range, nearer than the line's; 0 is the line's.
	ln_labfar   = cvar("hud_lines_label_far");
	if (ln_labfar <= 0 || (ln_far > 0 && ln_labfar > ln_far))
		ln_labfar = ln_far;
	ln_labfadek = (ln_labfar > 0) ? 3 / ln_labfar : 0;
	ln_mkgap    = cvar("hud_lines_gap");    if (ln_mkgap < 4) ln_mkgap = 40;
	ln_mkgap    = ln_mkgap * ln_px;
	ln_numon     = cvar("hud_lines_nums");
	ln_numspeed  = cvar("hud_lines_speed");
	ln_numenergy = cvar("hud_lines_energy");
	ln_numvz     = cvar("hud_lines_vz");
	ln_numdelta  = cvar("hud_lines_delta");
	ln_numtime   = cvar("hud_lines_time");
	ln_numref    = cvar("hud_lines_ref");
	ln_numsize   = cvar("hud_lines_numsize");  if (ln_numsize < 6) ln_numsize = 12;
	ln_names     = cvar("hud_lines_names");
	// Patch 661: a label's energy has its own unit, 1 energy as the speedometer
	// prints it (the default), 0 the speed it is worth; -1 is the split list's
	// (hud_seq_units, which a label followed until now and which reads u/s).
	ln_units     = cvar("hud_lines_units");
	if (ln_units < 0)
		ln_units = cvar("hud_seq_units");
	ln_grav      = serverkeyfloat("sv_gravity");
	if (ln_grav < 1)
		ln_grav = 800;
	fov = getproperty(VF_SCREENVSIZE);
	ln_cellnx = min(64, floor(fov_x / ln_mkgap) + 1);
	ln_cellny = min(LN_CELLS / max(1, ln_cellnx), floor(fov_y / ln_mkgap) + 1);
	ln_cellgen = ln_cellgen + 1;
	// The speed ramp's range, over the lines that are coloured by speed: a line in
	// another colouring does not move it (Patch 632).
	ln_slo = 99999;
	ln_shi = 0;
	for (s = 0; s < LN_SLOTS; s = s + 1)
		if (ln_on[s])
		if (Line_Mode(s) == 0)
		{
			ln_slo = min(ln_slo, ln_lo[s]);
			ln_shi = max(ln_shi, ln_hi[s]);
		}
	if (ln_shi < ln_slo)
	{
		ln_slo = 0;                 // nothing is coloured by speed
		ln_shi = 1;
	}
	ln_sinv = (ln_shi > ln_slo) ? 1 / (ln_shi - ln_slo) : 0;

	// The colours, once per change of range, mode or line (not per frame); and a
	// line coloured by time again when its place among the shown lines moves.
	Line_Rank();
	// Patch 649: each for its own reason.  A colouring chosen anew repaints every line;
	// the speed ramp moving repaints the lines coloured by speed (Line_Col is its only
	// reader); a line built again repaints that line.
	dirty = (ln_cmown != ln_ccown || ln_cmoth != ln_ccoth);
	rd = (ln_slo != ln_cslo || ln_shi != ln_cshi);
	for (s = 0; s < LN_SLOTS; s = s + 1)
		if (ln_on[s])
		{
			m = Line_Mode(s);
			c = (LN_TRAIL(s)) ? LN_OWNCOL : ln_rk[s];
			if (m < LN_CM_PLAIN)
				c = '0 0 0';
			if (dirty || ln_sgen[s] != ln_scgen[s] || (rd && m == 0) || c != ln_plain[s])
			{
				Line_Paint(s, m, 0);
				ln_plain[s] = c;
				ln_scgen[s] = ln_sgen[s];
				if (!LN_TRAIL(s))
					ln_npaint = ln_npaint + 1;
			}
		}
	ln_cslo = ln_slo;
	ln_cshi = ln_shi;
	ln_ccown = ln_cmown;
	ln_ccoth = ln_cmoth;
	// Only the small live tail changes between bulk rebuilds. Do not invalidate
	// the eight static board colour caches on every arrival. Contact/energy
	// retain their existing whole-slot classifiers rather than guessing a kind.
	for (s = LN_S_TRAIL; s < LN_S_MORE; s = s + 1)
		if (ln_n[s] > ln_published[s])
			Line_Paint(s, ln_cmown, ln_published[s]);
	// Patch 645: the frame's half of lines_draw's block (Line_Native has the slot's).
	if (ln_nat)
	{
		ln_np[LP_VERSION] = 1;
		ln_np[LP_REVEAL] = ln_reveal;
		ln_np[LP_CLTIME] = cltime;
		ln_np[LP_EYE] = ln_eye_x;  ln_np[LP_EYE + 1] = ln_eye_y;  ln_np[LP_EYE + 2] = ln_eye_z;
		ln_np[LP_FWD] = ln_fwd_x;  ln_np[LP_FWD + 1] = ln_fwd_y;  ln_np[LP_FWD + 2] = ln_fwd_z;
		ln_np[LP_RT] = ln_rt_x;    ln_np[LP_RT + 1] = ln_rt_y;    ln_np[LP_RT + 2] = ln_rt_z;
		ln_np[LP_UP] = ln_up_x;    ln_np[LP_UP + 1] = ln_up_y;    ln_np[LP_UP + 2] = ln_up_z;
		ln_np[LP_TX] = ln_tx;
		ln_np[LP_TY] = ln_ty;
		ln_np[LP_KX] = ln_kx;
		ln_np[LP_KY] = ln_ky;
		ln_np[LP_TOLK] = ln_tolk;
		ln_np[LP_FAR] = ln_far;
		ln_np[LP_FADEK] = ln_fadek;
		ln_np[LP_CHUNK] = LN_CHUNK;
		ln_np[LP_GROUP] = LN_GROUP;
		ln_np[LP_LEVELS] = LN_LEVELS;
		ln_np[LP_NEAR] = LN_NEAR;
		ln_np[LP_GUARD] = LN_GUARD;
		ln_np[LP_SUBPX] = LN_SUBPX;
		c = LN_FGNCOL;
		ln_np[LP_TINTCOL] = c_x;   ln_np[LP_TINTCOL + 1] = c_y;   ln_np[LP_TINTCOL + 2] = c_z;
	}
};

// A sphere against the view: -1 outside the frustum or past hud_watch_path_far,
// else the distance to its surface (0 inside it).
float(vector cen, float rad) Line_Sphere =
{
	local vector r;
	local float z, x;

	r = cen - ln_eye;
	z = r * ln_fwd;
	if (z < 0 - rad)
		return -1;
	x = r * ln_rt;
	if (x < 0) x = 0 - x;
	if (x - z * ln_tx > rad * ln_kx)
		return -1;
	x = r * ln_up;
	if (x < 0) x = 0 - x;
	if (x - z * ln_ty > rad * ln_ky)
		return -1;
	x = vlen(r);
	ln_cfade = (ln_far > 0 && x + rad > ln_far * 0.66);   // parts of it fade
	x = x - rad;
	if (x < 0)
		return 0;
	if (ln_far > 0)
	if (x > ln_far)
		return -1;
	return x;
};

// Chunk c of slot s: 0 off screen, else the stride (1, 2 .. LN_CHUNK) whose
// error is under LN_PXERR at its distance.
float(float s, float c) Line_ChunkStep =
{
	local float k, tol, l;

	k = LN_B(s) / LN_CHUNK + c;
	tol = Line_Sphere(ln_cc[k], ln_cr[k]);
	if (tol < 0)
		return 0;
	tol = tol * ln_tolk;
	k = k * LN_LEVELS;
	for (l = LN_LEVELS; l >= 1; l = l - 1)
		if (ln_cerr[k + l - 1] <= tol)
			return pow(2, l);
	return 1;
};

// Visual alpha only. Demo points brighten smoothly as their playhead passes;
// live points use arrival time, not their (possibly held/rewound) run clock.
float(float s, float i, float t, float tplay, float ahead) Line_Reveal =
{
	local float a, f;

	a = (t <= tplay) ? 1 : ahead;
	if (ln_reveal <= 0)
		return a;
	if (s == 0)
	{
		f = bound(0, (tplay - t) / ln_reveal, 1);
		a = ahead + (1 - ahead) * f;
	}
	if (s == 0 || LN_TRAIL(s))
	{
		if (ln_published[s] > 0)
		{
			f = bound(0, (cltime - ln_born[Line_BirthBase(s) + i]) / ln_reveal, 1);
			a = a * f;
		}
	}
	return a;
};

// Point i of slot base b onto the strip: the near clip against the point before,
// the subdivision of a long segment, and the playhead split.
void(float i, float st, float tplay, vector phead, float ahead) Line_Feed =
{
	local vector p, c, x, pm, pn, w, q0, q1;
	local float b, d, a, f, k, j, sub, l;

	b = ln_db;
	p = ln_pos[b + i];
	d = (p - ln_eye) * ln_fwd;
	c = ln_col[b + i];
	if (ln_dtint)
		c = c + (LN_FGNCOL - c) * ln_dtint;
	a = Line_Reveal(ln_ds, i, ln_t[b + i], tplay, ahead) * ln_da;
	// The fade is by distance, as the cull is (review: by depth it cut hard at
	// the screen's sides); only a chunk reaching into it pays the vlen.
	if (ln_cfade)
		a = a * bound(0, (ln_far - vlen(p - ln_eye)) * ln_fadek, 1);
	if (ln_winon)
		a = a * bound(0, min((ln_t[b + i] - ln_wina) * ln_winka,
		                     (ln_winb - ln_t[b + i]) * ln_winkb), 1);

	if (!ln_hp)
	{
		if (d >= LN_NEAR)
			Line_Pt(p, c, a);
	}
	else if (ln_pd >= LN_NEAR && d >= LN_NEAR)
	{
		// The playhead between the two: the line bright to it, dim after (or
		// ended there, `ahead` 0).
		if (ln_t[b + ln_pi] <= tplay && ln_t[b + i] > tplay)
		{
			f = (tplay - ln_t[b + ln_pi]) / max(0.0001, ln_t[b + i] - ln_t[b + ln_pi]);
			k = ln_da;
			if (ln_reveal > 0)
				k = Line_Reveal(ln_ds, i, tplay, tplay, ahead) * ln_da;
			Line_Pt(phead, ln_pc + (c - ln_pc) * f, k);
			if (ahead <= 0)
			{
				Line_RunEnd();
				ln_hp = FALSE;
				return;
			}
			st = 0;                 // no curve back over the playhead (review)
		}

		// A long segment on screen: Catmull-Rom through the neighbours (none across
		// a break), and only at full resolution.
		q1 = project(p);
		if (!Line_Sane(q1))
		{
			ln_hp = TRUE;
			ln_pi = i;
			ln_pp = p;
			ln_pd = d;
			ln_pc = c;
			ln_pa = a;
			return;
		}
		q1_z = 0;
		sub = 1;
		if (st == 1)
		if (ln_rn > 0)
		{
			q0 = ln_rq1;
			l = vlen(q1 - q0);
			if (l > LN_SUBPX)
				sub = min(8, ceil(l / (LN_SUBPX * 0.5)));
		}
		if (sub > 1)
		{
			pm = (ln_pi > 0 && !ln_brk[b + ln_pi]) ? ln_pos[b + ln_pi - 1]
			                                       : 2 * ln_pp - p;
			pn = 2 * p - ln_pp;
			if (i + 1 < ln_dn)
			if (!ln_brk[b + i + 1])
				pn = ln_pos[b + i + 1];
			for (j = 1; j < sub; j = j + 1)
			{
				f = j / sub;
				k = f * f;
				w = 0.5 * ((2 * ln_pp) + (p - pm) * f
				           + (2 * pm - 5 * ln_pp + 4 * p - pn) * k
				           + (3 * ln_pp - pm - 3 * p + pn) * k * f);
				if ((w - ln_eye) * ln_fwd >= LN_NEAR)
					Line_Pt(w, ln_pc + (c - ln_pc) * f, ln_pa + (a - ln_pa) * f);
			}
		}
		Line_Q(q1, c, a);
	}
	else if (ahead <= 0 && ln_t[b + i] > tplay)
	{
		Line_RunEnd();              // ahead 0: nothing past the playhead
		ln_nclip = ln_nclip + 1;
	}
	else if (ln_pd >= LN_NEAR)
	{
		x = ln_pp + (p - ln_pp) * ((ln_pd - LN_NEAR) / (ln_pd - d));
		Line_Pt(x, c, a);
		Line_RunEnd();
		ln_nclip = ln_nclip + 1;
	}
	else if (d >= LN_NEAR)
	{
		x = p + (ln_pp - p) * ((d - LN_NEAR) / (d - ln_pd));
		Line_Pt(x, ln_pc, ln_pa);
		Line_Pt(p, c, a);
		ln_nclip = ln_nclip + 1;
	}
	else
		ln_nclip = ln_nclip + 1;

	ln_hp = TRUE;
	ln_pi = i;
	ln_pp = p;
	ln_pd = d;
	ln_pc = c;
	ln_pa = a;
};

// A dashed line a->b in the world (a teleport's jump), clipped to the near plane.
void(vector a, vector b, vector c, float al) Line_Dash =
{
	local float da, db, l, t, dash, gap;
	local vector qa, qb, u;

	da = (a - ln_eye) * ln_fwd;
	db = (b - ln_eye) * ln_fwd;
	if (da < LN_NEAR && db < LN_NEAR)
		return;
	if (da < LN_NEAR)
		a = a + (b - a) * ((LN_NEAR - da) / (db - da));
	else if (db < LN_NEAR)
		b = b + (a - b) * ((LN_NEAR - db) / (da - db));
	qa = project(a);
	qb = project(b);
	qa_z = qb_z = 0;
	if (fabs(qa_x) > LN_GUARD || fabs(qa_y) > LN_GUARD
	 || fabs(qb_x) > LN_GUARD || fabs(qb_y) > LN_GUARD)
		return;
	u = qb - qa;
	l = vlen(u);
	if (l < 1)
		return;
	u = u * (1 / l);
	dash = 6 * ln_px;
	gap  = 5 * ln_px;
	for (t = 0; t < l && t < 4000 * ln_px; t = t + dash + gap)
		Line_Seg2D(qa + u * t, qa + u * min(l, t + dash), c, al, c, al);
};

// A teleport's end: a small square with a dark edge.
void(vector w, vector c, float al) Line_Square =
{
	local vector q;
	local float h;

	if ((w - ln_eye) * ln_fwd < LN_NEAR)
		return;
	q = project(w);
	if (q_z < -1 || fabs(q_x) > LN_GUARD || fabs(q_y) > LN_GUARD)
		return;
	h = 3 * ln_px;
	q = [floor(q_x / ln_px + 0.5) * ln_px, floor(q_y / ln_px + 0.5) * ln_px, 0];
	drawfill(q - [h + ln_px, h + ln_px], [2 * h + 2 * ln_px, 2 * h + 2 * ln_px],
	         '0 0 0', al * 0.7, 0);
	drawfill(q - [h, h], [2 * h, 2 * h], c, al, 0);
};

/*
  A world point onto the screen, or FALSE.  The dot product runs BEFORE
  project(), which divides by w with no zero guard (pr_csqc.c) -- a point on
  the eye plane otherwise returns a NaN that reaches drawfill and drawstring.
  cl_entview.qc:1288-1294 is the same guard for the same reason.
*/
float(vector w) Line_ProjPt =
{
	if ((w - ln_eye) * ln_fwd < LN_NEAR)
		return FALSE;
	ln_qmk = project(w);
	if (ln_qmk_z < -1 || fabs(ln_qmk_x) > LN_GUARD || fabs(ln_qmk_y) > LN_GUARD)
		return FALSE;
	ln_qmk_z = 0;
	ln_qmk = [floor(ln_qmk_x / ln_px + 0.5) * ln_px,
	          floor(ln_qmk_y / ln_px + 0.5) * ln_px, 0];
	return TRUE;
};

/*
  One screen cell a mark, at most.  A generation stamp rather than a clear: the
  grid is 4096 floats and zeroing it per frame would cost more than the marks.

  This is what bounds the pass: 300 hops inside twenty screen pixels draw one
  chevron, not 300, and the cost follows what is READABLE rather than what is
  in range.  A numeric cap would instead keep the first N in time order, which
  is not the N you are looking at.
*/
float(vector q) Line_CellOf =
{
	local float cx, cy, i;

	cx = floor(q_x / ln_mkgap);
	cy = floor(q_y / ln_mkgap);
	if (cx < 0 || cy < 0 || cx >= ln_cellnx || cy >= ln_cellny)
		return -1;                      // off screen: not drawn, not claimed
	i = cy * ln_cellnx + cx;
	return (i < 0 || i >= LN_CELLS) ? -1 : i;
};

float(vector q, float lab) Line_Claim =
{
	local float i;

	i = Line_CellOf(q);
	if (i < 0)
		return FALSE;
	if (!ln_sparse)
		return TRUE;
	// Labels claim their OWN grid.  Sharing one, a label lost every cell its
	// own glyph had just taken -- at gap 240 that was every number on screen
	// (p451num N6: 9 marks, 0 labels), which is not thinning, it is off.
	if (lab)
	{
		if (ln_lcell[i] == ln_cellgen)
			return FALSE;
		ln_lcell[i] = ln_cellgen;
		return TRUE;
	}
	if (ln_cell[i] == ln_cellgen)
		return FALSE;
	ln_cell[i] = ln_cellgen;
	return TRUE;
};

/*
  A label's whole span, claimed in ONE go.

  Its two ends can fall in the same cell, and claiming them one after the other
  made the label lose to ITSELF: at gap 240 that was every number on screen
  (p451num N6, 9 marks and 0 labels).  So: test both, then take both.
*/
float(vector lp, float lw) Line_ClaimSpan =
{
	local float i0, i1;

	i0 = Line_CellOf(lp);
	i1 = Line_CellOf(lp + [lw, 0, 0]);
	if (i0 < 0 && i1 < 0)
		return FALSE;
	if (!ln_sparse)
		return TRUE;
	if (i0 >= 0 && ln_lcell[i0] == ln_cellgen)
		return FALSE;
	if (i1 >= 0 && ln_lcell[i1] == ln_cellgen)
		return FALSE;
	if (i0 >= 0) ln_lcell[i0] = ln_cellgen;
	if (i1 >= 0) ln_lcell[i1] = ln_cellgen;
	return TRUE;
};

float(vector p, float w) Line_LabelOccupied =
{
	local float i;
	local vector other;

	for (i = 0; i < ln_lab_n; i = i + 1)
	{
		other = ln_lab_p[i];
		if (fabs(p_y - other_y) >= ln_labsz + 3 * ln_px)
			continue;
		if (p_x < other_x + ln_lab_w[i] + 3 * ln_px &&
		    p_x + w + 3 * ln_px > other_x)
			return TRUE;
	}
	return FALSE;
};

// One label for the end of the frame.  key is its fade state: a mark's index in
// the mark tables, or LN_LB_NAME + slot for a line's name.  d is how far it is
// from the eye, for the order.
float(vector p, string t, vector c, float a, float w, float h, float d, float key) Line_LabelQueue =
{
	// The names are queued last (cl_main.qc) and a crowd's numbers must not use up
	// their places: a number stops LN_SLOTS short of the end.
	if (ln_lab_n >= ((key >= LN_LB_NAME) ? LN_LABMAX : LN_LABMAX - LN_SLOTS))
	{
		ln_labover = ln_labover + 1;
		return FALSE;
	}
	ln_lab_p[ln_lab_n] = p;
	ln_lab_t[ln_lab_n] = t;
	ln_lab_c[ln_lab_n] = c;
	ln_lab_a[ln_lab_n] = a;
	ln_lab_w[ln_lab_n] = w;
	ln_lab_h[ln_lab_n] = h;
	ln_lab_d[ln_lab_n] = d;
	ln_lab_key[ln_lab_n] = key;
	ln_lab_k[ln_lab_n] = (key >= LN_LB_NAME) ? key - LN_LB_NAME + 1 : 0;
	ln_lab_n = ln_lab_n + 1;
	return TRUE;
};

// hud_lines_declutter 2 moves nearby labels into bounded vertical lanes rather
// than losing them to the overlap grid. In an impossibly dense view the fallback
// overprints; the renderer's explicit label-cap counter still applies.
void(vector p, float w) Line_LabelPlace =
{
	local float lane, dy;
	local vector q;

	ln_labelpos = p;
	if (!ln_lanes)
		return;
	for (lane = 0; lane < 16; lane = lane + 1)
	{
		q = p;
		dy = ceil(lane / 2) * (ln_labsz + 3 * ln_px);
		if (lane & 1)
			q_y = p_y + dy;
		else
			q_y = p_y - dy;
		if (q_y < 0 || q_y + ln_labsz > ln_labelscreen_y)
			continue;
		if (!Line_LabelOccupied(q, w))
		{
			ln_labelpos = q;
			return;
		}
	}
};

// n chevrons, stacked upwards, apex up (+1) or down (-1).  Polygons and not
// drawstring("A"): whether the bundled font covers U+039B and whether
// utf8_enable is on are two questions nobody should answer to see a mark.
void(vector q, float up, float n, vector c, float al) Line_Chev =
{
	local float w, h, i, pass, a;
	local vector a2, col;

	w = ln_mkpx * ln_px;
	h = w;
	/*
	  Two passes, a dark wider stroke under the colour -- the border
	  Line_Square already draws, for the reason p449shot_on showed: a white
	  take-off chevron against surf_aesthetic's sky is invisible, and the trace
	  said twelve of them had drawn in the frame I could not find them in.
	*/
	for (pass = 0; pass < 2; pass = pass + 1)
	{
		Line_Width(ln_mkpx * 0.5 + (pass ? 0 : 2));
		col = pass ? c : '0 0 0';
		a   = pass ? al : al * 0.6;
		for (i = 0; i < n; i = i + 1)
		{
			a2 = q - [0, up * (h + i * (h + ln_px)), 0];
			Line_Seg2D(a2 - [w, 0 - up * h, 0], a2, col, a, col, a);
			Line_Seg2D(a2, a2 + [w, up * h, 0], col, a, col, a);
		}
	}
};

// A closed triangle, pointing up at an arc's top and down at a ride's bottom.
void(vector q, float up, vector c, float al) Line_Triangle =
{
	local float w, h, pass, a;
	local vector tip, left, right, col;

	w = ln_mkpx * ln_px;
	h = w;
	tip = q - [0, up * h, 0];
	left = q + [0 - w, up * h, 0];
	right = q + [w, up * h, 0];
	for (pass = 0; pass < 2; pass = pass + 1)
	{
		Line_Width(ln_mkpx * 0.5 + (pass ? 0 : 2));
		col = pass ? c : '0 0 0';
		a = pass ? al : al * 0.6;
		Line_Seg2D(left, tip, col, a, col, a);
		Line_Seg2D(tip, right, col, a, col, a);
		Line_Seg2D(right, left, col, a, col, a);
	}
};

// The stitch: two bars, the dark edge Line_Square draws.  A save state came
// back here, so the run either side of it was not flown in one go.
void(vector q, vector c, float al) Line_Bars =
{
	local float w, h;

	w = ln_px;
	h = ln_mkpx * ln_px * 1.5;
	drawfill(q - [w * 3 + ln_px, h + ln_px], [2 * w + 2 * ln_px, 2 * h + 2 * ln_px],
	         '0 0 0', al * 0.7, 0);
	drawfill(q + [w, 0 - h - ln_px, 0], [2 * w + 2 * ln_px, 2 * h + 2 * ln_px],
	         '0 0 0', al * 0.7, 0);
	drawfill(q - [w * 3, h], [2 * w, 2 * h], c, al, 0);
	drawfill(q + [w * 2, 0 - h, 0], [2 * w, 2 * h], c, al, 0);
};

/*
  ONE MARK'S NUMBERS, as a single string. Inline colours keep one HUD_Text
  and one shadow pass; diagnostic readers retain the plain-text form.

  hud_lines_names 1 says what each number is -- "701 u/s  E -28  vz +120  dE +12
  1.23 s" -- with two spaces between fields so a name never reads as the previous
  field's unit; 0 is the bare "701 -28e +120z +12e 1.23s".

  The energy zero is a choice and it is the reader's: hud_lines_ref 0 takes the
  HUD's own (HUD_EnergyRef, what the split list measures from, so the two
  agree), 1 takes the RUN's first sample, which is self-contained and
  comparable between two recordings of the same map -- the reason it is the
  default on a line, where the watching player's anchor means nothing.
*/
string(float s, float e, float colour) Line_LabelText =
{
	local float b, ev, en, ref, de;
	local vector ep;                // an array element is not swizzleable
	local string t, sep, f;

	b = s * LN_EVCAP;
	t = "";
	sep = (ln_names ? "  " : " ");
	ev = ln_evh[b + e];
	// E = z + |v|^2 / 2g, Strafe_Energy evaluated from what the mark carries.
	ep = ln_ep[b + e];
	en = ep_z + ln_e2[b + e] / (2 * ln_grav);
	// Patch 661: at hud_lines_ref 0 the zero is the speedometer's in every state it
	// has (HUD_DrawSpeed): a rewind's own, and where it prints "-- no start zone"
	// there is none to share, so the run's own start stands in.
	ref = ln_z0[s] + ln_v20[s] / (2 * ln_grav);
	if (!ln_numref)
	{
		if (ui_rw_on)
		{
			if (ui_rw_refok)
				ref = ui_rw_ref;
		}
		else if (HUD_ZeroKnown())
			ref = HUD_EnergyRef();
	}

	if (ln_numspeed)
	{
		t = sprintf("%.0f", ev);
		if (ln_names)
			t = strcat(t, " u/s");
		if (colour)
			t = strcat("^xFF3", t, "^7");
	}
	if (ln_numenergy)
	{
		f = HUD_SeqAbsTight(en - ref, ln_grav, ln_units, ln_names);
		if (colour)
			f = strcat("^x4F6", f, "^7");
		t = strcat(t, (t != "") ? sep : "", f);
	}
	if (ln_numvz)
	{
		if (ln_names)
			f = sprintf("vz %+.0f", ln_ez[b + e]);
		else
			f = sprintf("%+.0fz", ln_ez[b + e]);
		t = strcat(t, (t != "") ? sep : "", f);
	}
	if (ln_numdelta)
	if (e > 0)
	{
		ep = ln_ep[b + e - 1];
		de = en - (ep_z + ln_e2[b + e - 1] / (2 * ln_grav));
		t = strcat(t, (t != "") ? sep : "",
		           HUD_SeqDelTight(de, Strafe_EquivSpeed(de, ln_grav), ln_units, ln_names));
	}
	if (ln_numtime)
	{
		if (ln_names)
			f = sprintf("%.2f s", ln_et[b + e]);
		else
			f = sprintf("%.2fs", ln_et[b + e]);
		t = strcat(t, (t != "") ? sep : "", f);
	}
	// An inferred ramp edge says so: "~701 u/s".  sub is from-kind * 4 + to-kind.
	if (t != "")
	if (ln_inf[s] == INF_INFERRED)
	if (ln_ek[b + e] == LN_E_LAND || ln_ek[b + e] == LN_E_LEAVE)
	if (floor(ln_es[b + e] / 4) == SEG_RAMP || (ln_es[b + e] & 3) == SEG_RAMP)
		t = strcat("~", t);
	return t;
};

string(float s, float e) Line_Label =
{
	return Line_LabelText(s, e, FALSE);
};

// One sampled ground contact followed immediately by takeoff: the jump says both.
// Keep the table intact for labels, Segments and diagnostics; suppress only ink.
float(float s, float e) Line_LandIsHop =
{
	local float b;

	if (!ln_mkjump || e + 1 >= ln_evn[s])
		return FALSE;
	b = s * LN_EVCAP;
	if ((ln_es[b + e] & 3) != SEG_NONE)
		return FALSE;
	if (ln_ek[b + e + 1] != LN_E_JUMP)
		return FALSE;
	if (floor(ln_es[b + e + 1] / 4) != SEG_NONE)
		return FALSE;
	return ln_ei[b + e + 1] - ln_ei[b + e] <= 1;
};

/*
  The marks over the drawn stretch, after the teleport pass so a stitch's bars
  sit over its dashes.  Walked from the mark list rather than from the points:
  the LOD stride skips points, and a mark on a skipped one must still draw.
*/
void(float s, float ia, float ib, float tplay, float ahead, float alpha) Line_Marks =
{
	local float b, n, e, k, k2, al, t0, t1, lw, f0, d, la;
	local vector p, c, q, lp;
	local string lab;

	if (!ln_mkon)
		return;
	/*
	  The labels are Bebas, measured here in the face and at the size
	  Line_FrameEnd draws them in.  4/3 keeps a digit's ink area: they drew in the
	  engine's default lhfont (a digit is 10x12 px of its 16 px cell), Bebas's is
	  0.71x0.33 em -- so numsize 12 -> 16 is 1.5x as tall at 0.6x the width (61 px^2
	  against 67).  The chips 10/12/14/18 land on 12/16/20/24.
	*/
	f0 = ui_font_cur;
	Font_Set(ui_font_dispsm);
	ln_labsz = Font_Px(ln_numsize * 4 / 3);
	b = LN_B(s);
	n = s * LN_EVCAP;
	t0 = ln_t[b + ia];
	t1 = ln_t[b + ib];
	for (e = Line_EvFind(s, t0); e < ln_evn[s]; e = e + 1)
	{
		if (ln_et[n + e] > t1)
			break;
		if (ahead <= 0)
		if (ln_et[n + e] > tplay)
			break;
		k = ln_ek[n + e];
		c = '1 1 1';                    // fteqcc cannot see the chain covers it
		if (k == LN_E_LAND)
		{
			if (!ln_mkland || Line_LandIsHop(s, e)) continue;
			c = '1.00 0.62 0.20';
		}
		else if (k == LN_E_LEAVE)  { if (!ln_mkleave)  continue; c = '0.92 0.95 1.00'; }
		else if (k == LN_E_JUMP)   { if (!ln_mkjump)   continue; c = '0.35 0.85 1.00'; }
		else if (k == LN_E_STITCH) { if (!ln_mkstitch) continue; c = '0.72 0.74 0.78'; }
		else if (k == LN_E_APEX || k == LN_E_TROUGH)
		{
			if (ln_numon < 2)
				continue;
			c = (k == LN_E_APEX) ? '1.00 0.35 0.65' : '0.70 0.40 1.00';
		}
		else
			continue;                   // a break: the teleport pass owns it
		p = ln_ep[n + e];
		// Patch 649: the sample's index is only read for a birth (the replay's line and the
		// live run's); a board line's mark does not pay the search for it.
		k2 = 0;
		if (s == 0 || LN_TRAIL(s))
			k2 = Line_Find(s, ln_et[n + e]);
		al = Line_Reveal(s, k2, ln_et[n + e], tplay, ahead) * alpha;
		if (ln_fadek > 0)
			al = al * bound(0, (ln_far - vlen(p - ln_eye)) * ln_fadek, 1);
		if (ln_winon)
			al = al * bound(0, min((ln_et[n + e] - ln_wina) * ln_winka,
			                       (ln_winb - ln_et[n + e]) * ln_winkb), 1);
		if (al <= 0)
			continue;
		if (!Line_ProjPt(p))
			continue;
		if (!Line_Claim(ln_qmk, FALSE))
			continue;
		q = ln_qmk;
		if (k == LN_E_STITCH)
			Line_Bars(q, c, al);
		else if (k == LN_E_APEX || k == LN_E_TROUGH)
			Line_Triangle(q, (k == LN_E_APEX) ? 1 : -1, c, al);
		else
			Line_Chev(q, (k == LN_E_LAND) ? -1 : 1,
			          (k == LN_E_JUMP) ? 2 : 1, c, al);
		ln_nmk = ln_nmk + 1;

		// The label claims its OWN cells -- the numbers are wider than the
		// glyph, so a mark can keep its chevron and lose its number rather
		// than the pair of them overprinting a neighbour.
		lab = "";
		if (Line_LabelOn(s, e))
		{
			// Patch 661: the numbers have their own range, nearer than the line's.
			d = vlen(p - ln_eye);
			la = al;
			if (ln_labfadek > 0)
				la = la * bound(0, (ln_labfar - d) * ln_labfadek, 1);
			if (la > 0)
				lab = Line_LabelText(s, e, TRUE);
			if (lab != "")
			{
				lp = q + [6 * ln_px, 0 - (ln_labsz + 4) * ln_px, 0];
				lw = stringwidth(lab, TRUE, [ln_labsz, ln_labsz]);
				Line_LabelPlace(lp, lw);
				lp = ln_labelpos;
				if (Line_ClaimSpan(lp, lw))
				{
					if (Line_LabelQueue(lp, lab, '1 1 1', la, lw, ln_labsz, d, n + e))
						ln_nlab = ln_nlab + 1;
				}
				else
					lab = "";
			}
		}
		if (ln_trmk > 0)
			print(sprintf("lndm %g %g %.4f %.1f %.1f %s\n", s, k, ln_et[n + e],
			              q_x, q_y, (lab != "") ? strcat("\"", Line_Label(s, e), "\"") : "-"));
	}
	Font_Set(f0);
};

// Slot s's width, px.  The board's and your own run's follow the replay's at -1
// (the shipped default), so nobody's lines changed when they got their own.
float(float s) Line_SlotPx =
{
	local float w;

	w = -1;
	if (LN_TRAIL(s))
		w = ln_wpxt;
	else if (s >= LN_S_BOARD)
		w = ln_wpxb;
	if (w < 0)
		w = ln_wpx;
	return w;
};

// Patch 645: Line_Draw's loop over slot s, in the engine.  FALSE: it refused (nothing
// drawn) and the QC loop runs.  ln_db, ln_dn, ln_da and ln_dtint are Line_Draw's.
float(float s, float ia, float ib, float tplay, vector phead, float ahead) Line_Native =
{
	local float f;

	f = (s == 0) ? 3 : ((LN_TRAIL(s)) ? 2 : 0);
	if (ln_winon) f = f + 4;
	if (ln_cfade) f = f + 8;
	ln_np[LP_BASE] = ln_db;
	ln_np[LP_FIRST] = ia;
	ln_np[LP_LAST] = ib;
	ln_np[LP_COUNT] = ln_dn;
	ln_np[LP_PUBLISHED] = ln_published[s];
	ln_np[LP_FLAGS] = f;
	ln_np[LP_BORNBASE] = (s == 0 || LN_TRAIL(s)) ? Line_BirthBase(s) : 0;
	ln_np[LP_CHUNKBASE] = LN_B(s) / LN_CHUNK;
	ln_np[LP_GROUPBASE] = LN_B(s) / LN_CHUNK / LN_GROUP;
	ln_np[LP_TPLAY] = tplay;
	ln_np[LP_AHEAD] = ahead;
	ln_np[LP_ALPHA] = ln_da;
	ln_np[LP_TINT] = ln_dtint;
	ln_np[LP_PHEAD] = phead_x;  ln_np[LP_PHEAD + 1] = phead_y;  ln_np[LP_PHEAD + 2] = phead_z;
	ln_np[LP_WINA] = ln_wina;
	ln_np[LP_WINB] = ln_winb;
	ln_np[LP_WINKA] = ln_winka;
	ln_np[LP_WINKB] = ln_winkb;
	ln_np[LP_NPT] = ln_npt;
	ln_np[LP_NSEG] = ln_nseg;
	ln_np[LP_NWILD] = ln_nwild;
	ln_np[LP_NCLIP] = ln_nclip;
	ln_np[LP_BBMIN] = ln_bbmin_x;    ln_np[LP_BBMIN + 1] = ln_bbmin_y;
	ln_np[LP_BBMAX] = ln_bbmax_x;    ln_np[LP_BBMAX + 1] = ln_bbmax_y;
	ln_np[LP_FIRSTPT] = ln_first_x;  ln_np[LP_FIRSTPT + 1] = ln_first_y;
	if (!lines_draw(ln_np, LP_SIZE))
	{
		ln_natno = ln_natno + 1;    // counted: the QC loop then draws the same picture
		return FALSE;
	}
	ln_npt = ln_np[LP_NPT];
	ln_nseg = ln_np[LP_NSEG];
	ln_nwild = ln_np[LP_NWILD];
	ln_nclip = ln_np[LP_NCLIP];
	ln_bbmin_x = ln_np[LP_BBMIN];    ln_bbmin_y = ln_np[LP_BBMIN + 1];
	ln_bbmax_x = ln_np[LP_BBMAX];    ln_bbmax_y = ln_np[LP_BBMAX + 1];
	ln_first_x = ln_np[LP_FIRSTPT];  ln_first_y = ln_np[LP_FIRSTPT + 1];
	ln_cfade = ln_np[LP_CFADE];
	ln_natn = ln_natn + 1;
	return TRUE;
};

/*
  Slot s over its shown range.  tplay: points after it draw at `ahead` (0 stops
  the line at the playhead, which phead marks); a board line passes a tplay past
  its end.  alpha scales the whole line.
*/
void(float s, float tplay, vector phead, float ahead, float alpha) Line_Draw =
{
	local float b, i, ib, c, st, ce, k, j, ia, al, g, ge, d0, d1, wpx;
	local vector p0, p1;

	if (!ln_on[s])
		if (!LN_TRAIL(s) || ln_n[s] < 2)
			return;
	b  = LN_B(s);
	ia = ln_ia[s];
	ib = ln_ib[s];
	// Expose each new live sample, keeping expensive spheres/LOD batched.
	// A deliberately cut shown range must not be extended.
	if (LN_TRAIL(s))
	if (ib == ln_published[s] - 1)
		ib = ln_n[s] - 1;
	// The window narrows the shown range; the cut it was set inside still wins.
	if (ln_winon)
	{
		ia = max(ia, Line_Find(s, ln_wina));
		ib = min(ib, Line_Find(s, ln_winb + 0.0001) - 1);
	}
	if (ib <= ia)
		return;
	if (ahead <= 0)
		ib = min(ib, Line_Find(s, tplay));   // the first point past the playhead
	ln_db = b;
	ln_ds = s;
	ln_dn = ln_n[s];
	ln_da = alpha;
	// Read per draw, not per point: the cvar cannot change inside one line.
	// Patch 632: over one of the five readings only.  A plain colour is the line's
	// own (blue, or its place by time); pulled toward blue it would say neither.
	ln_dtint = 0;
	if (ln_fgn[s])
	if (Line_Mode(s) < LN_CM_PLAIN)
		ln_dtint = bound(0, cvar("hud_watch_path_foreign"), 1);
	ln_tintd[s] = ln_dtint;         // for `replay colours`: ln_col is before the blend
	ln_drawf[s] = cltime;           // ... and a slot no drawer reached has neither
	// Per slot: Line_Width writes globals every emitter reads, the teleport
	// dashes below included, and one frame draws up to eleven slots.
	wpx = Line_SlotPx(s);
	Line_Width(wpx);

	ln_rn = 0;
	ln_hp = FALSE;
	i = ia;
	st = 1;
	c = 0;
	ce = -1;
	ge = -1;
	if (ln_nat)
	if (Line_Native(s, ia, ib, tplay, phead, ahead))
		i = ib + 1;                 // the engine drew it: nothing left for the loop
	while (i <= ib)
	{
		// Unbuilt tail: up to TR_BUILD-1 (15) samples in live capture. No stale
		// sphere/LOD may cull or skip it; Line_Feed retains near clip and breaks.
		if (i >= ln_published[s])
		{
			st = 1;
			ce = ge = ib;
			if (!ln_hp && i > ia && !ln_brk[b + i])
				Line_Feed(i - 1, 1, tplay, phead, ahead);
		}
		// A group of LN_GROUP chunks off screen or past the far distance: skipped whole.
		if (i > ge)
		{
			g  = floor(i / (LN_CHUNK * LN_GROUP));
			ge = min(min(ib, ln_published[s] - 1), (g + 1) * LN_CHUNK * LN_GROUP - 1);
			k  = LN_B(s) / LN_CHUNK / LN_GROUP + g;
			if (Line_Sphere(ln_gc[k], ln_gr[k]) < 0)
			{
				Line_RunEnd();
				ln_hp = FALSE;
				i = ge + 1;
				ce = ge;
				continue;
			}
		}
		if (i > ce)
		{
			c  = floor(i / LN_CHUNK);
			ce = min(min(ib, ln_published[s] - 1), (c + 1) * LN_CHUNK - 1);
			st = Line_ChunkStep(s, c);
			if (!st)
			{
				Line_RunEnd();
				ln_hp = FALSE;
				i = ce + 1;
				continue;
			}
			// Entering after a culled chunk: from the point before, unless a break.
			if (!ln_hp)
			if (i > ia)
			if (!ln_brk[b + i])
				Line_Feed(i - 1, st, tplay, phead, ahead);
		}
		if (ln_brk[b + i])
		{
			Line_RunEnd();
			ln_hp = FALSE;
		}
		Line_Feed(i, st, tplay, phead, ahead);
		if (ahead <= 0)
		if (ln_t[b + i] > tplay)
			break;
		// On the chunk's grid of st, and its last point (the error was measured so).
		if (i >= ce)
			i = ce + 1;
		else
			i = min(ce, c * LN_CHUNK + (floor((i - c * LN_CHUNK) / st) + 1) * st);
	}
	Line_RunEnd();

	// The teleports: a square at each end and a faint dashed line between.
	for (k = 0; k < ln_bkn[s]; k = k + 1)
	{
		j = ln_bk[s * LN_BKCAP + k];
		if (j <= ia || j > ib)
			continue;
		if (ahead <= 0)
		if (ln_t[b + j] > tplay)
			continue;
		p0 = ln_pos[b + j - 1];
		p1 = ln_pos[b + j];
		al = Line_Reveal(s, j, ln_t[b + j], tplay, ahead) * alpha *
		     bound(0, cvar("hud_lines_telealpha"), 1);
		d0 = d1 = al;
		if (ln_fadek > 0)
		{
			d0 = al * bound(0, (ln_far - vlen(p0 - ln_eye)) * ln_fadek, 1);
			d1 = al * bound(0, (ln_far - vlen(p1 - ln_eye)) * ln_fadek, 1);
		}
		// Patch 624: and with the window, as Line_Feed and Line_Marks do. A board line's
		// window moves with the viewer now, and a join at full strength beside a line
		// that is fading out pops.
		if (ln_winon)
		{
			d0 = d0 * bound(0, min((ln_t[b + j - 1] - ln_wina) * ln_winka,
			                       (ln_winb - ln_t[b + j - 1]) * ln_winkb), 1);
			d1 = d1 * bound(0, min((ln_t[b + j] - ln_wina) * ln_winka,
			                       (ln_winb - ln_t[b + j]) * ln_winkb), 1);
		}
		if (d0 <= 0 && d1 <= 0)
			continue;
		Line_Dash(p0, p1, '0.85 0.88 0.95', max(d0, d1));
		if (d0 > 0)
			Line_Square(p0, ln_col[b + j - 1], d0);
		if (d1 > 0)
			Line_Square(p1, ln_col[b + j], d1);
	}

	// Patch 449.  The glyph stroke is its own width, and the slot's is put back.
	// Patch 649: a board line past the first hud_lines_marked (eight) DRAWN is a line
	// only (ln_mkrank: its place among the drawn ones, from Scores_LinesDraw; by its
	// place among the drawn and not by its slot, or unticking the first eight of
	// twenty would leave twelve lines with no marks).  Marks and their numbers are QC
	// a mark, half of sixty-four lines' cost when all had them (2.2 of 4.2 ms a
	// frame), and fifty lines of them cover the view.
	ln_nmk = ln_nlab = 0;
	k = TRUE;
	if (s >= LN_S_BOARD)
	if (!LN_TRAIL(s))
	if (ln_mkrank >= ln_mkmax)
		k = FALSE;
	if (k)
	{
		Line_Width(ln_mkpx * 0.5);
		Line_Marks(s, ia, ib, tplay, ahead, alpha);
		Line_Width(wpx);
		ln_nmkf = ln_nmkf + ln_nmk;
	}

	// Two prints and not one: fteqcc caps a varargs call at eight and drops
	// the rest silently.  Every number here was computed by the pass above.
	if (ln_trmk > 0)
	{
		print(sprintf("lnd %g %.4f %g %.4f %.4f\n", s, tplay, ln_winon,
		              ln_wina, ln_winb));
		print(sprintf("lnd2 %g %g %g %g %g %g\n", s, ia, ib, ln_npt, ln_nseg,
		              ln_nmk));
		print(sprintf("lnd3 %g %g\n", s, ln_nlab));
	}
};

// The frame's marks are done: cl_main calls this after the board lines, which
// are drawn after the replay's.
/*
  Patch 661: which of the frame's labels have room (the block over ln_lab_d).
  Taken nearest first: a name at half its distance, and one that is showing at
  0.85 of its own, so two at about one distance do not trade places every
  frame.  Room is a grid of cells stamped with the frame's number, a label's
  whole box and two pixels round it.  The order is a bucket sort: the queue
  holds 256 and sixty-four lines can fill it.
*/
void() Line_LabelsPlace =
{
	local float i, j, f, dt, a, room, cw, ch, nx, ny, x0, x1, y0, y1, x, y, key, dmax;
	local vector p, vs;

	dt = bound(0, cltime - ln_labt, 0.1);
	ln_labt = cltime;
	ln_lbshown = ln_lbhidden = 0;
	if (!ln_lfa || ln_lab_n < 1)
		return;
	dmax = 1;
	for (i = 0; i < ln_lab_n; i = i + 1)
	{
		key = ln_lab_key[i];
		f = ln_lab_d[i];
		if (ln_lab_k[i])
			f = f * 0.5;
		if (ln_lff[key] == ln_labgen - 1)
		if (ln_lfa[key] > 0.5)
			f = f * 0.85;
		ln_lab_d[i] = f;
		if (f > dmax)
			dmax = f;
	}
	for (j = 0; j < LN_LB_BUCK; j = j + 1)
		ln_lb_head[j] = -1;
	for (i = ln_lab_n - 1; i >= 0; i = i - 1)      // backwards: a bucket keeps the queue's order
	{
		// The root: one label 12000 u off must not put every near one in one bucket.
		j = floor(sqrt(ln_lab_d[i] / dmax) * (LN_LB_BUCK - 1));
		ln_lab_nx[i] = ln_lb_head[j];
		ln_lb_head[j] = i;
	}
	vs = getproperty(VF_SCREENVSIZE);
	cw = max(12 * ln_px, vs_x / 160);
	ch = max(6 * ln_px, vs_y / 200);
	nx = min(160, floor(vs_x / cw) + 1);
	ny = min(floor(LN_LB_GRID / nx), floor(vs_y / ch) + 1);
	for (j = 0; j < LN_LB_BUCK; j = j + 1)
	for (i = ln_lb_head[j]; i >= 0; i = ln_lab_nx[i])
	{
		p = ln_lab_p[i];
		x0 = max(0, floor((p_x - 2 * ln_px) / cw));
		x1 = min(nx - 1, floor((p_x + ln_lab_w[i] + 2 * ln_px) / cw));
		y0 = max(0, floor((p_y - ln_px) / ch));
		y1 = min(ny - 1, floor((p_y + ln_lab_h[i] + ln_px) / ch));
		room = TRUE;
		for (y = y0; y <= y1; y = y + 1)
		{
			for (x = x0; x <= x1; x = x + 1)
				if (ln_lgrid[y * nx + x] == ln_labgen)
				{
					room = FALSE;
					break;
				}
			if (!room)
				break;
		}
		// One that is nearly faded out (the end of its range or of the line's window)
		// is drawn where it is but keeps nobody else out.
		if (room)
		if (ln_lab_a[i] >= LN_LB_FAINT)
			for (y = y0; y <= y1; y = y + 1)
				for (x = x0; x <= x1; x = x + 1)
					ln_lgrid[y * nx + x] = ln_labgen;
		key = ln_lab_key[i];
		a = (ln_lff[key] == ln_labgen - 1) ? ln_lfa[key] : 0;
		if (room)
		{
			a = min(1, a + dt / LN_LB_IN);
			ln_lbshown = ln_lbshown + 1;
		}
		else
		{
			a = max(0, a - dt / LN_LB_OUT);
			ln_lbhidden = ln_lbhidden + 1;
		}
		ln_lfa[key] = a;
		ln_lff[key] = ln_labgen;
		ln_lab_a[i] = ln_lab_a[i] * a;
	}
};

void() Line_FrameEnd =
{
	local float i, f0;

	ln_labgen = ln_labgen + 1;
	if (ln_labgen > LN_LB_WRAP)
	{
		// A float stops counting at 2^24, a day and a half at 144 fps: start again
		// well before, with every stamp forgotten (a third of a million writes, once).
		ln_labgen = 2;
		for (i = 0; i < LN_LB_GRID; i = i + 1)
			ln_lgrid[i] = 0;
		if (ln_lff)
			for (i = 0; i < LN_LB_NAME + LN_SLOTS; i = i + 1)
				ln_lff[i] = 0;
	}
	if (ln_lanes || ln_sparse)
	{
		ln_lbshown = ln_lab_n;          // those two placed theirs as they were queued
		ln_lbhidden = 0;
	}
	else
		Line_LabelsPlace();
	if (ln_lab_n > 0)
	{
		f0 = ui_font_cur;
		Font_Set(ui_font_dispsm);
		for (i = 0; i < ln_lab_n; i = i + 1)
			if (ln_lab_a[i] > 0)
			if (!ln_lab_k[i])
				HUD_Text(ln_lab_p[i], ln_lab_t[i], ln_labsz, ln_lab_c[i], ln_lab_a[i]);
		Font_Set(f0);
		// A line's name (cl_linegraph.qc): its own face, and the row's picture.
		for (i = 0; i < ln_lab_n; i = i + 1)
			if (ln_lab_a[i] > 0)
			if (ln_lab_k[i])
				LineGraph_NameDraw(ln_lab_k[i] - 1, ln_lab_p[i], ln_lab_a[i]);
	}
	if (ln_trmk > 0)
	{
		print(sprintf("lnde %g %g\n", ln_lab_n, ln_labover));
		ln_trmk = ln_trmk - 1;
	}
	ln_lab_n = 0;
	ln_labover = 0;
};

/*
  THE LINE'S OWN CVARS.  Patch 449.

  Registered here rather than in cl_watch.qc's block, where the hud_watch_path_*
  family lives, because this file owns them -- but they keep that family's
  CVAR_ARCHIVE and its shipped `set` lines in default.cfg, and nothing is
  renamed: hud_watch_path_far is still how far the lines are visible.

  The window defaults OFF.  It changes what an existing player sees, and a
  display change nobody asked for is a bug report.
*/
void() Line_RegisterCvars =
{
	local float i;

	Line_AllocSlots();
	registercommand("lines");
	registercvar("hud_lines_reveal", "0.18", CVAR_ARCHIVE);
	registercvar("hud_lines_board", "1", CVAR_ARCHIVE);
	registercvar("hud_lines_marks",  "1", CVAR_ARCHIVE);
	registercvar("hud_lines_land",   "1", CVAR_ARCHIVE);
	registercvar("hud_lines_leave",  "1", CVAR_ARCHIVE);
	registercvar("hud_lines_jump",   "1", CVAR_ARCHIVE);
	registercvar("hud_lines_stitch", "1", CVAR_ARCHIVE);
	// Patch 628: 1 a recording's off-ramp mark goes to the ramp's own edge where
	// the loaded map can find it; 0 it stays on the last contact sample.  Read
	// when a line is built.  _edgedebug prints each one as it is found.
	registercvar("hud_lines_edge",   "1", CVAR_ARCHIVE);
	registercvar("hud_lines_edgedebug", "0");
	registercvar("hud_lines_size",   "4", CVAR_ARCHIVE);
	registercvar("hud_lines_gap",   "40", CVAR_ARCHIVE);
	// 0 (Patch 661) every label at its own mark, the nearest first, one without
	// room faded out; 2 moved into lanes, the default before; 1 the sparse grid.
	registercvar("hud_lines_declutter", "0", CVAR_ARCHIVE);
	// Patch 661: how far a mark's numbers show, units; 0 as far as its line.
	registercvar("hud_lines_label_far", "3000", CVAR_ARCHIVE);
	// Patch 661: a label's energy, 1 as the speedometer prints it, 0 as a speed,
	// -1 as the split list has it (hud_seq_units).
	registercvar("hud_lines_units", "1", CVAR_ARCHIVE);
	registercvar("hud_lines_telealpha", "0.3", CVAR_ARCHIVE);
	// Patch 451: the numbers.  1 = on the contact marks; 2 adds the peaks, which
	// is dense on a bhop run; 3 (Patch 632) the peaks alone.  OFF by default since
	// Patch 637, the owner's own layout as the template; 451 had turned them on at
	// his asking and 627 made that 2.
	registercvar("hud_lines_nums",    "0", CVAR_ARCHIVE);
	// Patch 632: your line and the others, each 0 speed, 1 gain, 2 contact, 3 energy,
	// 4 air control, or 5 its plain colour (blue; by time).  hud_watch_path_color,
	// the one setting they replace, is no longer read: a saved value of it would
	// have kept these defaults from anyone who had ever clicked its chip.
	registercvar("hud_lines_color_own",    "5", CVAR_ARCHIVE);
	registercvar("hud_lines_color_others", "5", CVAR_ARCHIVE);
	// A config that had chosen gain, contact, energy or air control keeps it, for
	// both groups, once (the old name is then put back to 0 so the next start
	// does not undo a later choice of plain).  Speed, the old default, does not:
	// it cannot be told from never having chosen.
	i = cvar("hud_watch_path_color");
	if (i >= 1 && i <= 4)
		localcmd(sprintf("seta hud_lines_color_own %g\nseta hud_lines_color_others %g\n"
		                 "seta hud_watch_path_color 0\n", i, i));
	registercvar("hud_lines_speed",   "1", CVAR_ARCHIVE);
	registercvar("hud_lines_energy",  "1", CVAR_ARCHIVE);
	registercvar("hud_lines_vz",      "0", CVAR_ARCHIVE);
	registercvar("hud_lines_delta",   "0", CVAR_ARCHIVE);
	registercvar("hud_lines_time",    "0", CVAR_ARCHIVE);
	// Patch 661: 0, the speedometer's own zero, so a label and the energy line
	// under your speed are one measurement; it was 1, the run's first sample.
	registercvar("hud_lines_ref",     "0", CVAR_ARCHIVE);
	registercvar("hud_lines_numsize","12", CVAR_ARCHIVE);
	// Lex, 4 Oct 2026: the numbers say what they are by default.
	registercvar("hud_lines_names",   "1", CVAR_ARCHIVE);
	registercvar("hud_lines_win",    "0", CVAR_ARCHIVE);
	// Patch 624: seconds of each ticked board line shown ahead of where the viewer is
	// along it (and a quarter of that behind); 0 is everything within hud_watch_path_far.
	registercvar("hud_lines_order",  "4", CVAR_ARCHIVE);
	registercvar("hud_lines_winf",   "0", CVAR_ARCHIVE);
	// Patch 649: of the ticked lines (sixty-four at most now), the first this many have
	// marks and numbers; the rest are lines.  The graph and the names are the first
	// eight's whatever this says.
	registercvar("hud_lines_marked", "8", CVAR_ARCHIVE);
	// Patch 645: 0 draws lines and plots with the QC loop on an engine that has the
	// native one (the comparison, and the way back).  Not saved.
	registercvar("hud_lines_native", "1");
};

// Advanced settings stay addressable by their archived names.
float() Line_Console =
{
	local float s;

	if (argv(0) != "lines")
		return FALSE;
	// Patch 624, for an arm: where the viewer is along each board line and what was drawn.
	if (argv(1) == "order")
	{
		print(sprintf("lines: order %g eye %.1f %.1f %.1f\n", cvar("hud_lines_order"), ln_eye_x, ln_eye_y, ln_eye_z));
		for (s = LN_S_BOARD; s < LN_SLOTS; s = s + 1)
		{
			if (!ln_on[s] || LN_TRAIL(s))
				continue;
			print(sprintf("lines: order slot %g cursor %g t %.4f at %.1f u searches %g moved %g",
			              s, ln_fo_i[s], ln_t[LN_B(s) + ln_fo_i[s]], ln_fo_d[s], ln_fo_n[s], ln_fo_mv[s]));
			print(sprintf(" window %.4f %.4f\n", ln_fo_ta[s], ln_fo_tb[s]));
		}
		return TRUE;
	}
	if (argv(1) == "native")
	{
		print(sprintf("lines: native builtins %g in use %g passes %g refused %g\n",
		              ln_nath, ln_nat, ln_natn, ln_natno));
		// the last drawer's counters, which both ways must agree on
		print(sprintf("lines: last points %g segments %g wild %g clipped %g\n",
		              ln_npt, ln_nseg, ln_nwild, ln_nclip));
		print(sprintf("lines: last box %g %g %g %g\n", ln_bbmin_x, ln_bbmin_y, ln_bbmax_x, ln_bbmax_y));
		print(sprintf("lines: last marks %g of the first %g lines\n", ln_nmkf, ln_mkmax));
		print(sprintf("lines: last labels %g with room, %g without (placing %g, within %g u)\n",
		              ln_lbshown, ln_lbhidden, ln_declutter, ln_labfar));
		print(sprintf("lines: repainted %g times (the live run's own not counted); tables made in %.1f ms\n",
		              ln_npaint, ln_allocms));
		return TRUE;
	}
	print("lines: independent switches (0 off, 1 on):\n"
	      "  hud_trail 1       player line\n"
	      "  hud_watch_path 1  open demo line\n"
	      "  hud_lines_board 1 selected board lines\n"
	      "Labels: hud_lines_nums 0/1/2/3 (off/contacts/both/tops and bottoms)\n"
	      "  hud_lines_speed/energy/vz/delta/time/names 0/1\n"
	      "  ~ before a number: a ramp edge inferred on an imported run\n"
	      "  hud_lines_marks/land/leave/jump/stitch 0/1\n"
	      "  hud_lines_edge 1 (off-ramp mark at the ramp's edge, from the map)\n"
	      "  hud_lines_numsize 12, hud_lines_size 4, hud_lines_gap 40\n"
	      "  hud_lines_declutter 0 (at the mark, nearest first); 2 (lanes); 1 (sparse)\n"
	      "  hud_lines_label_far 3000 (0: as far as the line)\n"
	      "  hud_lines_ref 0/1 (HUD/run start)\n"
	      "  hud_lines_units 1/0/-1 (energy/speed it is worth/as the split list)\n"
	      "Style: hud_lines_color_own / _others 0..4 (speed/gain/contact/energy/\n"
	      "    air control) or 5 (blue; by time), hud_watch_path_far 6000\n"
	      "  hud_watch_path_px 1, _px_trail / _px_board -1 (inherit)\n"
	      "  hud_watch_path_ahead 1, hud_watch_path_foreign 0.55\n"
	      "  hud_lines_telealpha 0.3 (faded dashed teleport joins)\n"
	      "  hud_lines_win/winf 0 (whole line), or seconds behind/ahead\n"
	      "  hud_lines_order 8 (board lines: seconds ahead of you; 0 all near)\n"
	      "  hud_trail_prev 1, hud_trail_fade 1 (seconds)\n"
	      "  hud_lines_reveal 0.18 (chunk reveal seconds; 0 instant)\n"
	      "Nearby players (use seta, or it is not saved): cl_playerfade 1,\n"
	      "  cl_playerfade_near 32 (hidden within), cl_playerfade_far 128 (opaque beyond)\n");
	return TRUE;
};

void() Line_StatsReset =
{
	ln_nseg = ln_nclip = ln_nwild = ln_npt = ln_nmkf = 0;
	ln_bbmin = '99999 99999 0';
	ln_bbmax = '-99999 -99999 0';
	ln_first = '0 0 0';
};
