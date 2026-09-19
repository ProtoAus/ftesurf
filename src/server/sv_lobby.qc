/*
===========================================================================
  sv_lobby.qc -- public lobbies.  Patch 270, Stage 1.

  What this file is for: letting several people be on the same map, see and
  hear each other, and not interact in any other way.  No shared triggers, no
  collision, no combat -- everyone is running their own attempt at the map and
  the other bodies are scenery.

  NAMING.  Every global, field and function here starts with `lobby_` /
  `.lobby_` / `Lobby_`, and the whole prefix was grepped against the tree
  before this file existed.  That is not tidiness: QuakeC HAS NO FILE SCOPE,
  fteqcc silently merges two same-named globals from different files into one,
  and it emits no diagnostic at all.  This project has already lost a feature
  to exactly that -- `ui_rs_armed` was declared at file scope in both
  cl_board.qc and cl_results.qc for unrelated purposes, so one cleared the
  other's flag every frame and the results card had never once opened by
  itself.  All three progs compiled clean the whole time.  A single-prefix
  namespace makes the check one grep instead of a judgement call per name.

  WHY THE AVATAR IS A SEPARATE ENTITY AND NOT THE PLAYER.

  The obvious implementation is to give the player a model and let the normal
  entity path draw it.  That is 5x the bandwidth and it is not a tuning
  problem, it is deliberate engine behaviour.  SVFTE_DeltaCalcBits
  (sv_ents.c:998-1006) reads, verbatim:

      // "moving players get extra data forced upon them which is not deltatracked"
      if ((bits & UF_PREDINFO) && (from->u.q1.velocity[0] || ...))
      {
          bits |= UF_ORIGINXY | UF_ORIGINZ;
          if (host_client != svs.clients + to->number-1)
              bits |= UF_ANGLESXZ | UF_ANGLESY;
      }

  That branch is entered for any edict with a non-zero `pmovetype`, which is
  every client whose movement is independent -- i.e. every FTESurf client,
  because pm_physicsmode 1 makes them all so (sv_user.c:8507).  So for a moving
  player the origin AND both angle words are re-sent every single snapshot with
  delta compression bypassed by design.  At 66.7 Hz and 32 players that is
  roughly 30-40 KB/s down per client and ~9 Mbit/s up from the server.

  A separate non-client entity has pmovetype 0, never enters that branch, and
  falls through to the ordinary "did the field actually change" test at
  sv_ents.c:1009.  Move it 15 times a second and it costs 15 updates a second.
  The delta compressor becomes the rate limiter and we do not write one.

  INTERPOLATION IS ALSO FREE, and this is the part worth not re-deriving.  On
  the frames where no delta arrives for an entity, cl_ents.c:5039-5060 leaves
  `snew->sequence` untouched (it is only rewritten in SVFTE_ParseEntityDelta),
  so `le->newsequence != snew->sequence` is false and the client keeps lerping
  toward the last origin it received.  The lerp is clamped by
  cl_lerp_maxinterval, default 0.3s, which is far longer than the 1/15s gap we
  create.  A 15 Hz avatar therefore moves smoothly with ZERO lines of CSQC --
  and this tree has zero lines of CSQC entity code to build on, so that
  mattered.

  ...UP TO 3000 UPS, AND THE PARAGRAPH ABOVE USED TO STOP BEFORE SAYING SO.
  cl_lerp_maxinterval is only one of the two clamps.  The other is a DISTANCE:

      maxdist = cl_lerp_maxdistance * cl_lerp_maxdistance     cl_ents.c:4883
      if (DotProduct(move, move) > maxdist || ...) isnew = true;   :5013

  whose own comment is "disable lerping (and indirectly trails)".  `move` is the
  gap between two consecutive RECEIVED poses, i.e. speed / lobby_av_rate, and
  cl_lerp_maxdistance defaults to 200 (cl_main.c:124).  So the ceiling is

      cl_lerp_maxdistance * lobby_av_rate  =  200 * 15  =  3000 ups

  and above it an avatar is not interpolated at all -- it steps 15 times a
  second -- and any .traileffectnum on it is dropped, because the isnew branch
  at cl_ents.c:5921-5926 delinks the trailstate and `continue`s before the trail
  is ever run.  Surf speeds are above 3000 routinely, so this is the ordinary
  case and not a corner of it.

  Found in Patch 278, while working out why a speed trail would be invisible
  exactly when it was worth having.  It has been true since Stage 1 shipped.
  Two independent ways up, and they multiply: raise cl_lerp_maxdistance on the
  client (512 covers 6400 ups here, at the cost of smearing genuine teleports
  shorter than that, for every entity), or raise lobby_av_rate on the server.
  cfg/lobby/lobby.cfg carries the same note beside the rate.

  A hand-packed CSQC .SendEntity would get ~18 bytes down to ~8.  That is a
  real saving and it is Stage 8, deliberately after this, so that it can be
  argued against a measured baseline rather than a guess.
===========================================================================
*/

/*
  Fields.

  .lobby_av    on the PLAYER  -- its avatar, or world.
  .lobby_owner on the AVATAR  -- the player it mirrors, or world.
  .lobby_next  on the AVATAR  -- next server time to copy the pose.
  .lobby_model on the AVATAR  -- the model name last set, so the duck swap
                                 does not re-setmodel (and therefore re-send
                                 UF_MODEL) on every single pose copy.
  .lobby_colour on the PLAYER -- resolved palette index, 1..FS_AVCOLOURS.
                                 0 means "not resolved yet".  Lives on the
                                 player and not the avatar so that a kill or a
                                 respawn cannot change what colour you are.
  .lobby_fx     on the PLAYER  -- resolved effect mask, AFTER the lobby_av_fxmax
                                 cap has been applied.  Not the raw userinfo
                                 value: what someone asked for and what they got
                                 are different questions and both need answering.
  .lobby_trailc on the PLAYER  -- resolved trail colour, 1..FS_AVCOLOURS.  The
                                 `lobbytrail` infokey when it is in range, else
                                 the player's own colour.  Patch 340.
  .lobby_csent  on the PLAYER  -- the colour index last stuffcmd'd to this
                                 client as cl_pcolour, so the mirror is sent on
                                 CHANGE and not once a second.  Patch 340.
*/
.entity  lobby_av;
.entity  lobby_owner;
.float   lobby_next;
.string  lobby_model;
.float   lobby_colour;
.float   lobby_fx;
.float   lobby_trailc;
.float   lobby_csent;
.vector  lobby_rgb;              // PATCH 341: worn RGB 0..1, custom or palette echo
.float   lobby_custom;           // PATCH 341: lobbyrgb was valid; not a palette entry

/*
  BUILD 57, STAGE T -- THE LOBBY BITS ON THE WIRE, AS STAT_FS_LOBBY.

  The client has to know it is on a lobby before it keeps a time there itself: off
  a lobby the SERVER writes the files and a second writer would double-write, so
  client/cl_lobbytime.qc is inert unless this stat says so.

  THREE BITS, not one: LS_LOBBY, LS_NOPB and LS_NOREC (shared/sh_defs.qc, where
  the essay is).  Lobby_Active() alone would have let lobby_enable 1 with
  lobby_nopb 0 -- a listen server keeping its own files on this very disk -- file
  every run twice.

  A FIELD BECAUSE clientstat TAKES ONE, and the fact is global -- the same shape
  rec_sl_count has, and the reason SV_SaveLocSync exists.  It is mirrored onto
  every player once a frame in Lobby_Frame's dimensions loop, which is the one
  loop here that runs WHETHER OR NOT THE LOBBY IS ON -- so switching lobby_enable
  off clears it rather than leaving the client keeping times on a solo session.

  ON THE PLAYER and not on world, because that is what clientstat can reach.  It
  is registered in sv_main.qc, which compiles last and can therefore see both this
  field and the STAT_FS_* numbers.
*/
.float   lobby_stat;

/*
  Build 64.  "I have already told this client its runs are not being
  submitted."  Per-player rather than a file-scope global because the fault it
  reports affects everyone on the server equally -- a global latch would tell
  whoever finished first and stay silent for every player who joined after
  them, which on a rotating lobby is almost everybody.  Cleared for free by the
  engine when the slot is reused.
*/
.float   lobby_said_noid;

/*
  Build 65.  The same latch for the other fault the player cannot do anything
  about: the directory is reachable but refused or failed this submission.
  Separate from lobby_said_noid because they are different sentences and a
  server can have one without the other -- and because a server that starts
  refusing halfway through an evening would otherwise be silent to anyone who
  had already been told about a missing GUID.
*/
.float   lobby_said_fail;
.float   lobby_ann_due;         // Patch 371: >0 = the join line is owed at this time
.float   lobby_ann_pbat, lobby_ann_rank;   // the last "new best" line said for this player,
.float   lobby_ann_track;       // and its track + 1 (0 = none)
.float   lobby_ann_at;          // the last join or leave line for this player

/*
  Build 65.  The submission this player is waiting on an answer about, and what
  run it was -- see the *wrank essay in sh_defs.qc.

  THE REQUEST ID IS THE WHOLE LOOKUP, and it is on the player rather than in a
  table because the engine maintains the table for free.  A reply arrives with
  only its id (URI_Get_Callback), so something has to map that back to whoever
  finished; findfloat over this field is that map, and it has no fixed size to
  overflow -- which is the objection the parity note raises against a table of
  outstanding ids, and the reason that note is not violated here.

  IT CANNOT MIS-ATTRIBUTE A REPLY TO THE WRONG PLAYER, and that was checked
  rather than assumed.  The failure to worry about is a player who finishes,
  submits, disconnects inside the round trip, and has their slot taken by
  somebody else who is then told a stranger's rank.  It cannot happen: a client
  edict is run through ED_Clear when the slot is set up for a new connection
  (sv_user.c:5654, taken because FTESurf is QW rather than NQ progs), so a new
  player's id is 0 and findfloat cannot reach them.  Zero is never a live id --
  lobby_run_id is seeded to 1 and steps by 2.

  A SECOND SUBMISSION BEFORE THE FIRST ANSWERS overwrites this, so the older
  reply finds nobody and is dropped in silence.  That is the wanted behaviour:
  the answer to the run you just set is the one you want, and the stale one
  would draw a rank for a run that is no longer on screen.
*/
.float   lobby_rq_id;
.float   lobby_rq_track;
.float   lobby_rq_leg;
.float   lobby_rq_ticks;
.float   lobby_rq_flags;        // the submitted flags: FS_CertWhy for the unranked line
// A stage posted from a main run (Patch 360) waits on its OWN id and answers into
// `*srank`, so the final stage and the finish, posted in one frame, both land.
.float   lobby_sq_id;
.float   lobby_sq_track;
.float   lobby_sq_leg;
.float   lobby_sq_flags;
// The stage before it, if its reply is still out: that reply is told in chat
// but never written to *srank, which now describes the newer stage.
.float   lobby_sq_old;
.float   lobby_sq_oldtrack;
.float   lobby_sq_oldleg;
.float   lobby_sq_oldflags;
.float   lobby_sq_told;         // TF_UNCERT reasons already said for stage rows (this map)
// The run's id, the .rec header's `runid`; written by SV_RecOpen (sv_timer.qc,
// which compiles after this file), zoned there.
.string  rec_rec_rid;
float(entity e, float track, float leg, float ticks, float flags) Lobby_SubmitStage;

// Cached cvars, refreshed once per frame in Lobby_Frame.
float lobby_on;
float lobby_nocollide;
float lobby_avatars;
float lobby_rate;
float lobby_alpha;
float lobby_self;
float lobby_colors;
float lobby_fxon;
float lobby_fxmax;

// Edge detector for lobby_on, so a mid-session flip can resync rather than
// waiting for everyone to reconnect.
float lobby_was_on;

/*
  Colour bookkeeping.

  lobby_colcheck paces the userinfo re-read.  A player can retype
  `setinfo lobbycolor` at any time and there is no userinfo-change callback in
  SSQC, so the only way to notice is to look; 1 Hz is far below the cost of
  caring and far above the latency anyone will perceive.
*/
float lobby_colcheck;

/*
===========================================================================
  STAGE 2 -- the policies that only apply inside a lobby.

  Everything here answers one question: this feature was written for one
  player on their own machine, so what does it do when 32 people share it?
  The answers are all "switch it off in a lobby", and the reasons are worth
  stating individually because they fail in different ways:

    lobby_nopb       The personal-best tables (run_pb_ticks[] and friends,
                     sv_timer.qc) are keyed on TRACK, not on player, and
                     SV_PBSave rewrites data/runs/<map>/best.pb whole.  With
                     32 people on the map the "personal" best becomes whoever
                     finished last, every player is shown that number as their
                     own, and THE FILE ON DISK IS DESTROYED -- a player's real
                     history overwritten by strangers.  Silent in both
                     directions: nothing looks wrong until you go home and
                     find your times gone.  This is the worst of the six.

    lobby_norec      The .rec recorder holds an entire run as QC strings in a
                     strbuf until the run closes.  Thirty-two of those is on
                     the order of 50 MB of string table on a machine with 3.2
                     GB and NO SWAP, and the filename
                     <ticks>_<tag>.rec collides outright when two people tie.
                     A lobby is not where a run is proven anyway: Stage 3's
                     telemetry is, and it is server-authored.

    lobby_nosaveloc  The save-loc list is ONE global list of FS_MAXSAVES rows
                     (sv_saveloc.qc), so player A's `save` fills a slot player
                     B then deletes.  A save-loc is a practice tool for a
                     player alone with a map section; it has no meaning in a
                     room of 32 and sharing it is purely destructive.

    lobby_retrigger  A trigger_once removed by the first player through is
                     removed for everyone behind them, and 841 of the
                     library's trigger_onces wire an output.  Handled in
                     sv_entities.qc, which compiles BEFORE this file, so the
                     flag it reads is latched in StartFrame; see vbsp_retrigger
                     there.

  All four default ON (i.e. the restriction applies), and that does not break
  the house rule that a change defaults to today's behaviour, because every one
  of them is ANDed with lobby_enable -- which defaults to 0.  An offline
  session, which runs this identical progs, reaches none of these tests.

  Read as cvars at the point of use rather than cached in Lobby_Frame, and that
  is deliberate: SV_PBLoad runs at map init, BEFORE the first StartFrame, so a
  cached lobby_on would still be 0 there and the map's best.pb would be loaded
  and displayed on a lobby for exactly one map load.  Every caller here is a
  finish, a run start or a console command -- events measured in seconds, not
  frames -- so two cvar lookups are free.
===========================================================================
*/
float() Lobby_Active     = { return cvar("lobby_enable") != 0; };
float() Lobby_NoPB       = { return Lobby_Active() && cvar("lobby_nopb"); };
float() Lobby_NoRec      = { return Lobby_Active() && cvar("lobby_norec"); };
float() Lobby_NoSaveLoc  = { return Lobby_Active() && cvar("lobby_nosaveloc"); };
float() Lobby_Retrigger  = { return Lobby_Active() && cvar("lobby_retrigger"); };

/*
  The two hull shapes, named once.

  This is Ghost_Model()'s rule (cl_ghost.qc:136-141) evaluated on the server
  instead of from a stat.  Deliberately the same two files and the same test:
  the avatar and the free-fly ghost body must never disagree about what a
  ducked player looks like, and the way to guarantee that is to make the rule
  identical rather than similar.

  Two files rather than one scaled model because the hulls are two different
  SHAPES and not two sizes of one -- 32x32x62 standing, 32x32x45 ducked, same
  footprint -- and a uniform .scale would take the width down with the height.
  tools/mkplayermodel.py cuts both from one description so they cannot drift.

  Those heights read 72/54 until Patch 278 and were wrong from build 41 on;
  see the longer note at cl_ghost.qc's Ghost_Model.
*/
string(entity p) Lobby_Model =
{
	if (p.pmove_flags & PMF_DUCKED)
		return "models/player_duck.iqm";
	return "models/player.iqm";
};

/*
===========================================================================
  PER-PLAYER COLOUR.

  .colormod, and the alternatives are worth ruling out in writing because both
  are the obvious answer and both are dead ends here:

  .colormap / topcolor / bottomcolor cannot work on this model at all.  The
  palette-remap path (GL_ChooseSkin, gl_alias.c:1015-1049) needs 8-bit
  PALETTED skin texels, which only the MDL and .lmp loaders ever produce; an
  IQM has none, and gl_alias.c:808-813 detects exactly that and bails to the
  default textures.  The other arm needs models/player_shirt.tga and
  _pants.tga alpha masks that do not exist.  It is also the only colouring in
  the engine that any client can override for everyone else, with
  cl_enemytopcolor / gl_nocolors (cl_parse.c:5802-5826, gl_alias.c:703).

  .colormod is 3 bytes on the frame it changes and ZERO after -- it is an
  ordinary delta-tracked field (UF_COLORMOD, sv_ents.c:1079-1080), unlike the
  origin and angles of a moving player, which are force-resent every snapshot.
  On the client it becomes shaderRGBAf and resolves to a single multiply in
  defaultskin.glsl:398.  Set it once per player and it costs nothing at all.

  THE ONE THING THAT MAKES THIS NON-OBVIOUS: models/player.tga IS NOT NEUTRAL.
  It is 93.9% a single flat green, RGB (130 236 83) -- measured by decoding the
  RLE, not assumed.  colormod MULTIPLIES, so setting it to the colour you want
  gives you a green-shifted version of that colour.  Every palette entry has to
  be divided by the base first, which is what Lobby_ColourMod does.

  If models/player.tga is ever regenerated neutral, set the three LOBBY_SKINBASE
  numbers to 1 and nothing else in this file changes.  It has deliberately NOT
  been regenerated: cl_ghost.qc:213 sets .colormod on the ghost body from CSQC,
  a path this game has never actually exercised, so a neutral base would risk
  turning the existing ghost white to buy arithmetic that is already fine.
===========================================================================
*/
#define FS_AVCOLOURS 12

#define LOBBY_SKINBASE_R 0.50980		// 130/255
#define LOBBY_SKINBASE_G 0.92549		// 236/255
#define LOBBY_SKINBASE_B 0.32549		//  83/255

/*
  The palette, as the colour you actually want to SEE -- not as colormod values.

  Twelve, because twelve is the most that stay tellable apart at a glance on a
  32-unit-wide box seen across a surf map, and because at 12 nobody in a lobby
  of 12 or fewer shares one.

  PLAIN HUE ORDER, and the spacing lives in the ASSIGNMENT instead (see the
  stride in Lobby_ColourFor).  Two separate jobs: this list wants to be
  readable, so that `setinfo lobbycolor 3` is memorably yellow and a person can
  pick from it; the slot mapping wants consecutive joiners to look nothing
  alike.  Doing both here would mean a scrambled list nobody can read.

  These twelve were chosen by search, not by eye, against the real pipeline --
  divided by the skin, quantised to the wire, decoded, and multiplied back
  through the texture.  A first hand-picked set put violet and indigo 0.200
  apart in rendered RGB, which is not a difference you can see on a distant
  box.  Constraining every entry to keep one channel at >= 0.92 (so nothing
  vanishes in a dark leaf, where colormod's lit term goes to zero) and
  maximising the minimum pairwise distance gives the set below, whose closest
  pair is 0.505 apart -- two and a half times better, and every entry bright.

  An if-ladder and not an array on purpose.  fteqcc emits O(N) accessor code
  per array and the array LENGTH costs about eight times its data in progs.dat
  -- measured on the recorder rings, where four extra slots cost 563 KB for
  68 KB of data.  A twelve-entry vector array would be a real number of
  kilobytes for something read once per player per second.
*/
vector(float i) Lobby_PaletteRGB =
{
	if (i == 1)  return '1.00 0.00 0.00';	// red
	if (i == 2)  return '0.92 0.51 0.09';	// orange
	if (i == 3)  return '1.00 1.00 0.00';	// yellow
	if (i == 4)  return '0.51 0.92 0.09';	// chartreuse
	if (i == 5)  return '0.00 1.00 0.00';	// green
	if (i == 6)  return '0.09 0.92 0.51';	// spring green
	if (i == 7)  return '0.00 1.00 1.00';	// cyan
	if (i == 8)  return '0.09 0.51 0.92';	// azure
	if (i == 9)  return '0.00 0.00 1.00';	// blue
	if (i == 10) return '0.51 0.09 0.92';	// violet
	if (i == 11) return '1.00 0.00 1.00';	// magenta
	if (i == 12) return '0.92 0.09 0.51';	// rose
	return '1 1 1';
};

/*
  A palette entry as the engine wants it.

  Divide by the skin, then respect the engine's own range: sv_ents.c:3919-3930
  packs colormod as byte = qc * 32, so the wire range is 0 .. 7.96875 in steps
  of 1/32.  Clamping here rather than letting the engine do it keeps the QC
  value and the value that actually ships the same -- otherwise a palette edit
  that overflows saturates silently and the colour on screen stops matching the
  colour in this file.

  THE ALL-ZERO TRAP: '0 0 0' is not black, it is IDENTITY.  sv_ents.c:3919
  tests all three channels and substitutes 32,32,32.  So a palette entry that
  quantises to zero on every channel does not go dark, it goes back to plain
  green.  None of the twelve above come near it -- the darkest channel after
  division is 0.10/0.325 = 0.31, which is byte 9 -- but the floor below makes
  it impossible rather than merely unlikely.
*/
vector(float i) Lobby_ColourMod =
{
	local vector v;

	v = Lobby_PaletteRGB(i);
	v_x = v_x / LOBBY_SKINBASE_R;
	v_y = v_y / LOBBY_SKINBASE_G;
	v_z = v_z / LOBBY_SKINBASE_B;

	if (v_x > 7.96) v_x = 7.96;
	if (v_y > 7.96) v_y = 7.96;
	if (v_z > 7.96) v_z = 7.96;

	// One channel above the quantisation floor, so the triple can never read
	// as the engine's "no colormod set" sentinel.
	if (v_x < 0.032 && v_y < 0.032 && v_z < 0.032)
		v_x = 0.032;

	return v;
};

/*
  PATCH 341: THE SAME TWO MODS FROM AN ARBITRARY RGB, and the nearest palette
  entry to one, for `setinfo lobbyrgb "r g b"` (0..255 ints).

  The body colour is exact -- colormod and glowmod are multiplies and take any
  triple -- but the PARTICLES are not: trail and mote effects are generated
  per palette entry by tools/mkavatarfx.py and cannot be tinted per entity,
  so a custom colour wears its own rgb on the model and the NEAREST palette
  entry in its trail, its motes, its chat name and everybody's swatch.  The
  nearest index is what .lobby_colour holds when .lobby_custom is set, which
  is also what keeps two custom players who picked near-identical rgbs from
  confusing the taken-colour logic: they occupy the index they resemble.

  Parse rejects anything but three 0..255 tokens; a half-typed rgb is "no rgb"
  rather than black, because black is a colour somebody might actually want.
*/
vector(string s) Lobby_ParseRGB =
{
	local vector v;
	local float i, sp, val;
	local string t;

	v = '-1 -1 -1';
	for (i = 0; i < 3; i = i + 1)
	{
		s = strtrim(s);
		if (s == "")
			return '-1 -1 -1';
		sp = strstrofs(s, " ", 0);
		if (sp < 0)
		{
			t = s;
			s = "";
		}
		else
		{
			t = substring(s, 0, sp);
			s = substring(s, sp + 1, -1);
		}
		val = stof(t);
		if (val < 0 || val > 255)
			return '-1 -1 -1';
		if (i == 0) v_x = val / 255;
		else if (i == 1) v_y = val / 255;
		else v_z = val / 255;
	}
	return v;
};

float(vector rgb) Lobby_NearestColour =
{
	local float i, best, bi, d;
	local vector c;

	best = -1;
	bi   = 1;
	for (i = 1; i <= FS_AVCOLOURS; i = i + 1)
	{
		c = Lobby_PaletteRGB(i) - rgb;
		d = c_x * c_x + c_y * c_y + c_z * c_z;
		if (best < 0 || d < best)
		{
			best = d;
			bi   = i;
		}
	}
	return bi;
};

vector(vector rgb) Lobby_ColourModRGB =
{
	local vector v;

	v = rgb;
	v_x = v_x / LOBBY_SKINBASE_R;
	v_y = v_y / LOBBY_SKINBASE_G;
	v_z = v_z / LOBBY_SKINBASE_B;
	if (v_x > 7.96) v_x = 7.96;
	if (v_y > 7.96) v_y = 7.96;
	if (v_z > 7.96) v_z = 7.96;
	if (v_x < 0.032 && v_y < 0.032 && v_z < 0.032)
		v_x = 0.032;
	return v;
};

vector(vector rgb) Lobby_GlowModRGB =
{
	local vector v;

	v = rgb;
	if (v_x < 0.032 && v_y < 0.032 && v_z < 0.032)
		v_x = 0.032;
	return v;
};

/*
  PATCH 340: the palette index as a CONSOLE colour, 0..6.

  The chat name colour is not ours to draw.  Every client renders a chat line
  through the engine's own CL_PrintChat, which colours the speaker's name via
  CL_PlayerColor (cl_parse.c) -- and in a non-teamplay QW game that reads the
  `tc` userinfo key: c = atoi(tc), name painted ^(1 + c%7).  So "the chat name
  is the player's colour" is one forceinfokey away, PROVIDED the value is
  0..6: tc >= 7 takes the (c/7)&1 branch, which marks the name as already
  coloured and paints it white instead.

  Seven console colours against twelve palette entries, so this is the nearest
  hue, and two palette neighbours can share one console colour -- orange and
  yellow both say ^3.  That is the console's limit, not this table's; the
  avatar and the customizer swatch carry the exact colour.

  Console colours, for the mapping: ^1 red, ^2 green, ^3 yellow, ^4 blue,
  ^5 cyan, ^6 magenta, ^7 white.
*/
float(float i) Lobby_TcOf =
{
	if (i == 1)  return 0;	// red        -> ^1 red
	if (i == 2)  return 2;	// orange     -> ^3 yellow
	if (i == 3)  return 2;	// yellow     -> ^3 yellow
	if (i == 4)  return 1;	// chartreuse -> ^2 green
	if (i == 5)  return 1;	// green      -> ^2 green
	if (i == 6)  return 1;	// spring     -> ^2 green
	if (i == 7)  return 4;	// cyan       -> ^5 cyan
	if (i == 8)  return 3;	// azure      -> ^4 blue
	if (i == 9)  return 3;	// blue       -> ^4 blue
	if (i == 10) return 5;	// violet     -> ^6 magenta
	if (i == 11) return 5;	// magenta    -> ^6 magenta
	if (i == 12) return 5;	// rose       -> ^6 magenta
	return 6;					// white
};

/*
  Is this palette index already spoken for by somebody else?

  O(players) per call and called at most once per player per second, so 32
  players is about a thousand field compares a second -- against a zone scan
  that is already doing tens of thousands of polygon tests.  Not worth
  optimising into a bitmask that could then disagree with the players.
*/
float(entity p, float idx) Lobby_ColourTaken =
{
	local entity o;

	o = find(world, classname, "player");
	while (o)
	{
		if (o != p && o.lobby_colour == idx)
			return TRUE;
		o = find(o, classname, "player");
	}
	return FALSE;
};

/*
  Which colour this player should be.

  Their own pick wins if they made one and it is free; then the colour they
  already hold if it is still free; then a RANDOM free one (Patch 340 -- it
  used to be the slot index, strided and rotated).  A colour freed by a
  departure is available again the moment the 1 Hz re-resolve runs.

  `setinfo lobbycolor <n>` is how a player picks.  infokey is real in SSQC in
  this engine -- PF_infokey_s, builtin 80 (pr_cmds.c:11437), not PF_Fixme --
  and userinfo archives itself into the client's config the same way name and
  topcolor already do, so the choice survives a restart with no work from us.
  0 or empty means "you choose".
*/
float(entity p) Lobby_ColourFor =
{
	local float idx, tries;
	local string s;

	// The player's own request, honoured only if it is in range and free.
	s = infokey(p, "lobbycolor");
	if (s != "")
	{
		idx = stof(s);
		if (idx >= 1 && idx <= FS_AVCOLOURS && !Lobby_ColourTaken(p, idx))
			return idx;
	}

	/*
	  PATCH 340: THE COLOUR YOU ALREADY HOLD WINS NEXT, and this line is what
	  makes the random pick below safe at all.  This function is re-run for
	  every player once a second (the userinfo re-read above); a bare random()
	  here would re-roll everybody's colour every second.  Held-and-free is
	  stable, so the roll happens once per connection -- at
	  Lobby_ClientConnect's clear -- and a colour only MOVES when its holder
	  leaves or somebody's explicit pick takes it, which is exactly the
	  re-resolve the 1 Hz loop exists for.
	*/
	if (p.lobby_colour >= 1 && p.lobby_colour <= FS_AVCOLOURS
	    && !Lobby_ColourTaken(p, p.lobby_colour))
		return p.lobby_colour;

	/*
	  PATCH 340: RANDOM, where this used to be the slot index strided by 5 and
	  rotated by a per-map shuffle.  The ask is "a random colour skin when they
	  connect", and random is also strictly better at the thing the stride was
	  built for: two people who join together cannot land on adjacent hues
	  because they cannot land on the SAME hue at all -- Lobby_ColourTaken
	  excludes it, which the stride's permutation could not promise once
	  explicit picks had reserved entries out from under it.  The shuffle and
	  its latch died with the stride; a random pick needs no rotation.

	  Bounded by the palette size, so a full lobby simply wraps and shares
	  rather than spinning.
	*/
	idx   = floor(random() * FS_AVCOLOURS) + 1;
	tries = 0;
	while (Lobby_ColourTaken(p, idx) && tries < FS_AVCOLOURS)
	{
		idx = idx + 1;
		if (idx > FS_AVCOLOURS)
			idx = 1;
		tries = tries + 1;
	}
	return idx;
};

/*
  Push a player's colour onto their avatar.

  lobby_colors 0 writes '0 0 0', which is the engine's identity sentinel and
  therefore EXACTLY today's flat green -- that is the falsifier for this whole
  feature, and it has to be the identity value rather than '1 1 1' so that the
  field is not even flagged as changed.
*/
void(entity av, entity p) Lobby_ApplyColour =
{
	if (!lobby_colors)
	{
		av.colormod = '0 0 0';
		return;
	}

	if (!p.lobby_colour)
		p.lobby_colour = Lobby_ColourFor(p);

	if (p.lobby_custom)
		av.colormod = Lobby_ColourModRGB(p.lobby_rgb);
	else
		av.colormod = Lobby_ColourMod(p.lobby_colour);
};

/*
===========================================================================
  PER-PLAYER EFFECTS.

  OPT-IN, PER CLIENT, with `setinfo lobbyfx <mask>`:  1 trail, 2 motes,
  4 glow, and -- Patch 340 -- 8 long trail (modifies bit 1: the ribbon uses
  the slower-dying ftesurf_avtrailL_<n> blocks instead of ftesurf_avtrail_<n>).
  Trail COLOUR is its own key, `setinfo lobbytrail <n>`: unset or out of
  range means "match my colour", which is all bit 1 did before 340.  Both are
  surfaced by the CSQC customizer (cl_player.qc, `hud_player`).
  Off for everybody by default, which is the setting Lex asked for and is also
  the right default for a timing game -- visual clutter around another player
  is not something to inflict on someone mid-run without their say-so.

  BOTH FIELDS ARE FREE TO HOLD AND CHEAP TO SET.  They share one delta bit
  (UF_TRAILEFFECT, sv_ents.c:1091-1092), cost 2 bytes on the frame they change
  and 4 if an emit effect is set, and ZERO per frame after that.  So the entire
  network cost of this feature is a handful of bytes per player per change.

  THE INDEX MUST COME FROM THE SERVER'S OWN particleeffectnum.  SSQC's builtin
  (pr_cmds.c:4476-4504) interns the name in the server's precache table and
  hands back a positive slot, which the client remaps through its own
  precache list (CL_TranslateParticleFromServer, cl_tent.c:2327-2341).  CSQC's
  builtin of the same name returns a NEGATIVE client-only slot which means
  nothing to anyone else and is invalid to put in these fields.

  AND IT DOES NOT VERIFY ANYTHING.  SV_ParticlePrecache_Add does not check that
  the effect exists on any client -- it cannot, the clients are not consulted.
  A name with a typo precaches happily, resolves to P_INVALID on arrival and
  draws nothing, with no error at either end.  That is exactly why the blocks
  are GENERATED from the same palette this file defines, rather than the names
  being written out twice and trusted to match.

  THE ONE-PERSON WRINKLE, worth stating because it will otherwise be found the
  hard way: with lobby_av_self 0 you are not sent your own avatar at all
  (sv_ents.c:4213 drops it before it is networked), so turning your own effects
  on shows you NOTHING.  You are choosing how you look to other people.  Set
  lobby_av_self 1 and use ghost mode to see your own.
===========================================================================
*/
#define FS_AVFX_TRAIL 1
#define FS_AVFX_MOTES 2
#define FS_AVFX_GLOW  4
// Patch 340: the LONG trail variant.  Meaningful only with FS_AVFX_TRAIL --
// it selects ftesurf_avtrailL_<n> (a slower-dying ribbon) instead of
// ftesurf_avtrail_<n>.  Not counted separately by lobby_av_fxmax: it is the
// same one emitter, with a longer life; the cap's job is emitter counts.
#define FS_AVFX_TRAILONG 8

/*
  The glow colour.

  NOT divided by the skin, unlike Lobby_ColourMod, and the difference is the
  whole reason this is a separate function: glowmod multiplies the FULLBRIGHT
  texture (models/player_luma.tga, which is white), not the diffuse one
  (models/player.tga, which is green).  Dividing here would tint the belt to
  compensate for a green that is not in this texture.

  Same encoding and the same all-zero trap as colormod -- '0 0 0' is identity,
  not black -- so the floor below keeps a dark entry expressible.
*/
vector(float i) Lobby_GlowMod =
{
	local vector v;

	v = Lobby_PaletteRGB(i);
	if (v_x < 0.032 && v_y < 0.032 && v_z < 0.032)
		v_x = 0.032;
	return v;
};

void(entity av, entity p) Lobby_ApplyFX =
{
	local float m, tc;

	m = p.lobby_fx;

	// Trail colour resolves to the player's own when unset; the 1 Hz loop
	// keeps .lobby_trailc current, but an avatar can be applied before the
	// first pass and 0 is not a palette index.
	tc = p.lobby_trailc;
	if (tc < 1 || tc > FS_AVCOLOURS)
		tc = p.lobby_colour;

	// Assigned unconditionally rather than only on change: the delta
	// compressor compares the packed values and only flags the bit when they
	// actually differ, so writing the same number costs nothing.
	if (m & FS_AVFX_TRAIL)
	{
		if (m & FS_AVFX_TRAILONG)
			av.traileffectnum = particleeffectnum(sprintf("ftesurf_avtrailL_%g", tc));
		else
			av.traileffectnum = particleeffectnum(sprintf("ftesurf_avtrail_%g", tc));
	}
	else
		av.traileffectnum = 0;

	if (m & FS_AVFX_MOTES)
		av.emiteffectnum = particleeffectnum(sprintf("ftesurf_avmote_%g", p.lobby_colour));
	else
		av.emiteffectnum = 0;

	/*
	  The self-lit belt.  5 bytes on change, 0/frame after (UF_GLOW), and it is
	  a no-op unless models/player_luma.tga is present -- the permutation is
	  gated on that texture actually loading (gl_backend.c:4373-4374), so a
	  missing file costs nothing and breaks nothing.

	  NOT capped by lobby_av_fxmax: the cap exists for the particle pool, and
	  this spawns no particles.  It is one extra texture fetch on a model that
	  is already being drawn.

	  Worth having because colormod is applied AFTER lighting and before the
	  fullbright add (defaultskin.glsl:398 then :403).  In a dark leaf a
	  colour-only body goes black and its colour stops telling you anything;
	  the belt does not.
	*/
	if (m & FS_AVFX_GLOW)
		av.glowmod = p.lobby_custom ? Lobby_GlowModRGB(p.lobby_rgb)
		                            : Lobby_GlowMod(p.lobby_colour);
	else
		/*
		  NOT '0 0 0'.  That is the engine's IDENTITY sentinel, not black
		  (sv_ents.c:3931-3933 substitutes 32,32,32 when all three are zero),
		  so writing it would leave glowmod at 1.0 and light the belt at FULL
		  WHITE for every player who did not ask for it -- the presence of
		  models/player_luma.tga turns the fullbright pass on for the model
		  globally, and only glowmod decides how much of it you see.

		  0.032 is one quantisation step: byte 1, which decodes to 8/256 =
		  0.031, i.e. three percent of an additive term.  Off, in every sense
		  that matters, and expressible where black is not.
		*/
		av.glowmod = '0.032 0.032 0.032';
};

/*
  Said out loud at map load rather than discovered mid-run, for the reason
  cl_portal.qc gives: setmodel would load it anyway, and a model the code
  depends on should be named where the map loads.

  It also has to happen here specifically.  worldspawn sets
  sv_gameplayfix_setmodelsize_qw 1 so that props get their model's real bounds;
  with that set, PF_setmodel stamps a hardcoded +/-16 cube onto any entity
  whose model FAILED to load (pr_cmds.c:3181-3186).  An unprecached avatar
  model would therefore not error -- it would quietly become a 32-unit cube.
*/
void() Lobby_Precache =
{
	local float i;

	precache_model("models/player.iqm");
	precache_model("models/player_duck.iqm");

	/*
	  The per-colour effects, precached here rather than lazily at the moment
	  somebody switches them on.

	  particleeffectnum is idempotent and could be called at assignment time --
	  it interns the name and returns the same slot every time -- but doing it
	  at map init means the whole table is in the precache list the client
	  receives when it CONNECTS, rather than arriving later as a stuffed
	  svcfte_precache to everyone already in the game.  Twenty-four slots out of
	  MAX_SSPARTICLESPRE's 1024, whether or not anyone uses them.

	  These names must match tools/mkavatarfx.py's output exactly.  Nothing at
	  either end checks that they do: a name that is not defined client-side
	  precaches happily here, resolves to P_INVALID on arrival, and draws
	  nothing, silently.  That is why the cfg is generated from this file's own
	  palette rather than the twelve names being typed out twice.
	*/
	i = 1;
	while (i <= FS_AVCOLOURS)
	{
		particleeffectnum(sprintf("ftesurf_avtrail_%g", i));
		// Patch 340: the long-trail variant, FS_AVFX_TRAILONG.  Same rule as
		// the short one: precached at map init so the whole table rides the
		// connect-time precache list, and generated by the same tool run.
		particleeffectnum(sprintf("ftesurf_avtrailL_%g", i));
		particleeffectnum(sprintf("ftesurf_avmote_%g", i));
		i = i + 1;
	}
};

/*
  Player-vs-player collision.

  THE OBVIOUS VERSION IS WRONG AND BREAKS THE ENTIRE GAME, so the reasoning is
  here rather than in a commit message.  `dimension_solid = 0` on the player --
  "I am solid in no dimension" -- looks like it says exactly what we want.  It
  does not, because AddEntityToPmove (sv_user.c:7048-7050) uses that field in
  BOTH roles and the two tests are asymmetric:

      pe->notouch = !((int)player->xv->dimension_solid & (int)check->xv->dimension_hit);
      if (!((int)player->xv->dimension_hit & (int)check->xv->dimension_solid))
          return true;

  The first line asks "do MY touches register against this thing", and it asks
  it with the PLAYER's dimension_solid.  Zero that and `notouch` is true for
  every physent on the map, and notouch is what gates the touch dispatch at
  sv_user.c:8314-8315 -- so every trigger_multiple, trigger_teleport,
  trigger_push, func_bhop and entity-I/O output stops firing.  Silently.  The
  timer would never arm and nothing would say why.

  The split that works uses two separate bits:

      dimension_solid = 2   I am solid only in the PLAYER dimension
      dimension_hit   = 1   I collide only with the WORLD dimension

  and everything else on the map keeps the engine default of 255:

      player vs trigger, added?   hit(1) & solid(255)  = 1   -> added
      player vs trigger, touch?   !(solid(2) & hit(255))     -> false, fires
      player A vs player B        A.hit(1) & B.solid(2) = 0  -> not a physent

  Applied every frame rather than once at spawn, so lobby_nocollide flips live
  and the A/B is one console command instead of a map restart.  Two float
  stores per player per frame is not worth a dirty flag.

  The avatar needs none of this: it is SOLID_NOT, and the loop that feeds
  AddEntityToPmove filters on .solid before it ever gets there
  (sv_user.c:7226-7238 lists BSP/BBOX/SLIDEBOX/LADDER/PORTAL/TRIGGER and the
  two Source prop solidities -- SOLID_NOT is not among them).
*/
void(entity p) Lobby_ApplyDimensions =
{
	if (lobby_on && lobby_nocollide)
	{
		p.dimension_solid = 2;
		p.dimension_hit   = 1;
	}
	else
	{
		// The engine default, i.e. exactly upstream behaviour.
		p.dimension_solid = 255;
		p.dimension_hit   = 255;
	}
};

/*
  Hide a player's own avatar from them.

  Without this the owner is standing inside their own body's head.  setorigin
  puts the avatar at the player's FEET origin while the eye sits at
  origin + PM_VIEW_OFS, so first person is a view from inside the model.  It
  did not show up before lobbies existed because the player edict has no model
  at all -- setmodel(self, "") at sv_player.qc:182.

  .nodrawtoclient is a hard `continue` in SV_Snapshot_BuildQ1
  (sv_ents.c:4211-4214):

      //DP_SV_NODRAWONLYTOCLIENT
      if (ent->xv->nodrawtoclient)
          if (client->edict && ent->xv->nodrawtoclient == EDICT_TO_PROG(svprogfuncs, client->edict))
              continue;

  and SV_Snapshot_BuildQ1 is the SHARED per-client gather, not a legacy path:
  sv_ents.c:4492 fills one packet_entities_t, 4503 and 4550 hand it to
  SVFTE_EmitPacketEntities, 4590 hands it to SVQW_EmitPacketEntities.  The
  entity is dropped before either writer sees it, so the owner pays nothing for
  their own avatar -- no bytes, no dlights, no shadow.

  Rejected, recorded so they are not re-proposed:

    .exteriormodeltoclient (sv_ents.c:3667-3672) is also genuinely per-client
    and also works on both paths, but it only sets a render flag.
    gl_alias.c:3596 skips the draw only when !r_refdef.externalview &&
    !chase_active, so the body REAPPEARS in chasecam, in mirrors, and in
    cl_portal.qc's portal views -- and it is still fully networked and still
    casts a shadow unless r_shadow_playershadows is 0.  We want the bytes back.

    .viewmodelforclient (sv_ents.c:4116-4119) is the exact inverse: only that
    client receives it, attached to their view as a weapon model.

    Dimensions would work -- the test at sv_ents.c:4231 is in the same shared
    gather -- but would spend one bit of an 8-bit mask per player, and a
    player's dimension_see ALSO gates which multicasts and sounds reach them
    (sv_send.c:751, 1017), so narrowing it to hide a model would silently drop
    their events.  That is the same class of mistake as dimension_solid = 0.

  Two engine-documented limits, at progdefs.h:334, recorded rather than
  discovered later: the field is not honoured for MVD recording (sv_ents.c:4213
  requires client->edict, which an MVD recorder has not got), and on a
  splitscreen connection it is compared only against the primary seat, so seat
  two would still see it.  Neither affects a normal client.

  lobby_av_self 1 puts the old behaviour back, live, without a reconnect.  It
  is not just symmetry for the house rule: it is the only way to inspect your
  own avatar's pose and duck-swap solo, with one client, in ghost mode.
*/
void(entity av, entity p) Lobby_AvatarSelf =
{
	if (lobby_self)
		av.nodrawtoclient = world;
	else
		av.nodrawtoclient = p;
};

void(entity p) Lobby_AvatarFree =
{
	if (p.lobby_av)
	{
		remove(p.lobby_av);
		p.lobby_av = world;
	}
};

void(entity p) Lobby_AvatarSpawn =
{
	local entity av;

	if (p.lobby_av)
		return;

	av = spawn();
	av.classname   = "lobbyavatar";
	av.lobby_owner = p;
	av.owner       = p;

	/*
	  SOLID_NOT and MOVETYPE_NONE: this entity exists to be looked at.  It is
	  never traced against, never thinks, and never moves itself -- the pose is
	  pushed onto it from Lobby_Frame.
	*/
	av.solid    = SOLID_NOT;
	av.movetype = MOVETYPE_NONE;

	/*
	  PVSF_IGNOREPVS, and it is required rather than an optimisation.

	  Everyone in a lobby is running their own attempt, so two players are
	  routinely in parts of the map that cannot see each other -- which is
	  precisely what the PVS is for and precisely what would delete them.  3 is
	  greater than PVSF_USEPHS, so the visibility test at sv_ents.c:4131-4167
	  skips both of its branches.

	  PVSF_NOREMOVE WAS SET HERE TOO AND HAD TO COME BACK OUT.  It was added on
	  the reasoning that an avatar should never receive a spurious remove.  What
	  it actually does is make an avatar impossible to remove AT ALL, and it
	  broke disconnect.

	  ED_Free (qclib/pr_edict.c:174-210) only marks the edict ER_FREE and stamps
	  freetime; every field-clearing line inside it is commented out, so a
	  removed entity keeps its fields.  SVFTE_EmitPacketEntities' gap loop
	  (sv_ents.c:1630-1631) then reads that freed edict:

	      e = EDICT_NUM_PB(svprogfuncs, o->number);
	      if (!((int)e->xv->pvsflags & PVSF_NOREMOVE))
	      {
	          client->pendingdeltabits[j] = UF_SV_REMOVE;
	          o->number = 0;    // dead

	  With the flag still set, the UF_SV_REMOVE is suppressed AND o->number is
	  left non-zero -- so the suppression repeats on every subsequent frame.  A
	  player who disconnected left their body standing on every other client's
	  screen, frozen at its last pose, until the edict slot was recycled; and
	  ED_Alloc (pr_edict.c:105-146) refuses to recycle a slot for 0.5s and may
	  never reach it at all.  This was live on the build handed over for testing.

	  IGNOREPVS alone is what this entity needs.  Dropping NOREMOVE also makes
	  .nodrawtoclient safe to change at runtime instead of spawn-time-only,
	  which is what lobby_av_self below relies on.
	*/
	av.pvsflags = PVSF_IGNOREPVS;

	Lobby_AvatarSelf(av, p);

	av.alpha = lobby_alpha;

	// Colour before the first snapshot, so the avatar is never briefly green.
	// Costs nothing extra: this is the frame the entity is created on, so
	// colormod rides the same baseline update as the model and the origin.
	Lobby_ApplyColour(av, p);

	av.lobby_model = Lobby_Model(p);
	setmodel(av, av.lobby_model);
	setorigin(av, p.origin);
	av.angles = '0 0 0';
	av.angles_y = p.angles_y;

	// Copy the pose on the very next frame rather than 1/rate from now.
	av.lobby_next = 0;

	p.lobby_av = av;
};

/*
  Push one player's pose onto its avatar, at lobby_rate Hz.

  Yaw only.  The user asked for position and horizontal angle, and it is also
  what the model wants: cl_ghost.qc:194-198 records that FTE pitch-scales alias
  models on the player path, so feeding pitch in tilts the body rather than
  aiming it.  The model's nose is on +X, so a bare yaw is already correct with
  no fixup.

  setorigin rather than assigning .origin, because the entity has to be
  relinked for the delta system to notice it moved.
*/
void(entity av) Lobby_AvatarPose =
{
	local entity p;
	local string want;

	p = av.lobby_owner;

	// Owner gone or no longer a live player: the avatar goes with it.
	if (!p || p.classname != "player")
	{
		if (p)
			p.lobby_av = world;
		remove(av);
		return;
	}

	if (time < av.lobby_next)
		return;
	av.lobby_next = time + (1 / lobby_rate);

	want = Lobby_Model(p);
	if (want != av.lobby_model)
	{
		// Only on the standing<->ducked transition.  setmodel every pose would
		// re-send UF_MODEL every pose for no reason.
		av.lobby_model = want;
		setmodel(av, want);
	}

	setorigin(av, p.origin);
	av.angles_x = 0;
	av.angles_y = p.angles_y;
	av.angles_z = 0;

	if (av.alpha != lobby_alpha)
		av.alpha = lobby_alpha;

	// Re-applied per pose so lobby_av_self flips live.  Safe to change at
	// runtime only because PVSF_NOREMOVE is gone -- with it set, turning this
	// ON would have frozen the avatar on the owner's screen instead of
	// removing it, for the reason spelled out in Lobby_AvatarSpawn.
	Lobby_AvatarSelf(av, p);
};

/*
  Bring the world into line with lobby_on -- spawn the missing avatars, or
  remove all of them.  Only run on a transition, not per frame.
*/
void() Lobby_Resync =
{
	local entity p, av, nx;

	if (lobby_on && lobby_avatars)
	{
		p = find(world, classname, "player");
		while (p)
		{
			Lobby_AvatarSpawn(p);
			p = find(p, classname, "player");
		}
	}
	else
	{
		av = find(world, classname, "lobbyavatar");
		while (av)
		{
			nx = find(av, classname, "lobbyavatar");
			if (av.lobby_owner)
				av.lobby_owner.lobby_av = world;
			remove(av);
			av = nx;
		}
	}
};

/*
===========================================================================
  CHAT ANNOUNCEMENTS.  Patch 371.

  System lines are PRINT_CHAT (the only level the chatbox shows) spelled
  "^C word:^7 text": a ^ always follows the colon, so the engine can never
  read one as a player's "name: " chat (zqtp.c:2288).

  A JOIN IS KEYED ON THE CONNECTION, not on ClientConnect, which runs again
  for everyone on every changelevel and map_restart.  `*ann` is a userinfo
  star key: it survives both, is rebuilt on a real connect (sv_main.c:3147)
  and is cleared at the drop (sv_main.c:682).  Parms would not do: map_restart
  skips SetChangeParms (sv_ccmds.c:1212).  The line waits LOBBY_ANN_DELAY so
  the 1 Hz colour pass has published `tc`, which is what colours the name.
===========================================================================
*/
#define LOBBY_ANN_DELAY 1.5
#define LOBBY_ANN_PACE  30      // observe/join toggling: one join or leave line per player per 30 s
                                // (lobby_ann_at 0: none said yet on this edict this map)

float() Lobby_AnnOn =
{
	registercvar("lobby_announce", "1");        // beside the read: StartFrame precedes worldspawn
	return cvar("lobby_announce") != 0;
};

// {..} is cl_parsewhitetext markup (cl_parse.c:7031); ^[ ^] steer Chat_ParseServer.
string(string s) Lobby_Clean =
{
	s = strreplace("{", "(", s);
	s = strreplace("}", ")", s);
	while (strstrofs(s, "^[", 0) >= 0)          // one pass can make a new one: "^^[["
		s = strreplace("^[", "", s);
	while (strstrofs(s, "^]", 0) >= 0)
		s = strreplace("^]", "", s);
	return s;
};

// The name as the chatbox colours it (cl_chat.qc Chat_ColourOf): `tc`, else the
// userid, ^(1 + c%7); a name with its own ^ codes paints itself.
string(entity p) Lobby_ChatName =
{
	local string nm, t;
	local float c;

	nm = Lobby_Clean(p.netname);
	if (nm == "")
		nm = "player";
	if (strstrofs(nm, "^", 0) >= 0)
		return strcat(nm, "^7");
	t = infokey(p, "tc");
	if (t == "")
		t = infokey(p, "*userid");
	c = stof(t);
	if (c < 0)
		c = 0;
	c = c - floor(c / 7) * 7;
	return sprintf("^%g%s^7", c + 1, nm);
};

string(float track) Lobby_Where =
{
	if (track > 0)
		return sprintf("%s bonus %g", Lobby_Clean(mapname), track);
	return Lobby_Clean(mapname);
};

// PRINT_CHAT to every connected client but one; the server log gets it too.
void(entity except, string msg) Lobby_SayOthers =
{
	local float i, t;
	local entity e;

	i = 1;
	e = edict_num(i);
	t = clienttype(e);
	while (t != CLIENTTYPE_NOTACLIENT)          // past the last slot: world, NOTACLIENT
	{
		if (t == CLIENTTYPE_REAL)
		if (e != except)
			sprint(e, PRINT_CHAT, msg);
		i = i + 1;
		e = edict_num(i);
		t = clienttype(e);
	}
	dprint(strcat("said> ", msg));          // the server log's copy (log_developer)
};

void(entity p) Lobby_AnnConnect =
{
	p.lobby_ann_due = 0;
	if (infokey(p, "*ann") == "")               // this connection is not announced yet
		p.lobby_ann_due = time + LOBBY_ANN_DELAY;
};

void(entity p) Lobby_AnnJoin =
{
	local float t;
	local string host;

	p.lobby_ann_due = 0;
	t = clienttype(p);
	if (t != CLIENTTYPE_REAL)
	if (t != CLIENTTYPE_BOT)
		return;
	forceinfokey(p, "*ann", "1");
	if (!Lobby_AnnOn())
		return;
	if (!p.lobby_ann_at || time >= p.lobby_ann_at + LOBBY_ANN_PACE)
		Lobby_SayOthers(p, sprintf("^5server:^7 %s joined\n", Lobby_ChatName(p)));
	p.lobby_ann_at = time;
	if (t != CLIENTTYPE_REAL)
		return;
	if (strstrofs(infokey(p, "ip"), "LoopBack", 0) >= 0)
		return;                                 // the listen host is not welcomed to its own game
	host = Lobby_Clean(cvar_string("hostname"));
	if (host == "" || host == "unnamed")
		host = "FTESurf";
	sprint(p, PRINT_CHAT, sprintf("^5server:^7 welcome to %s -- on %s\n",
	                              host, Lobby_Clean(mapname)));
};

void(entity p) Lobby_AnnDisconnect =
{
	local float was;

	was = (infokey(p, "*ann") != "");
	p.lobby_ann_due = 0;                        // an unannounced join gets no leave line
	if (!was)
		return;
	forceinfokey(p, "*ann", "");                // `observe` keeps the connection: a later `join` is new
	if (Lobby_AnnOn())
	if (!p.lobby_ann_at || time >= p.lobby_ann_at + LOBBY_ANN_PACE)
		Lobby_SayOthers(p, sprintf("^5server:^7 %s left\n", Lobby_ChatName(p)));
	p.lobby_ann_at = time;
};

/*
  Others hear a new best at most once a minute per player (lobby_announce_gap),
  so a newcomer grinding a bhop map in ten-second runs does not flood the box.
  A climb within the top ten on that track speaks anyway -- taking the world
  record included, but not improving one already held (a fresh board, where
  every best is #1).
*/
float(entity e, float rank, float track) Lobby_AnnGate =
{
	local float gap, prev;

	registercvar("lobby_announce_gap", "60");
	gap = cvar("lobby_announce_gap");
	prev = 0;
	if (e.lobby_ann_track == track + 1)
		prev = e.lobby_ann_rank;
	if (e.lobby_ann_pbat > 0)
	if (time < e.lobby_ann_pbat + gap)
	if (!(rank > 0 && rank <= 10 && (prev <= 0 || rank < prev)))
		return FALSE;
	e.lobby_ann_pbat = time;
	if (rank > 0)
	{
		e.lobby_ann_rank = rank;
		e.lobby_ann_track = track + 1;
	}
	return TRUE;
};

void() Lobby_Frame =
{
	local entity av, nx, p;
	local float  nfx, want, tc;
	local vector rgbv;

	/*
	  REGISTERED HERE, NOT IN worldspawn, AND lobby_avatars IS WHY.

	  SV_ProgStartFrame runs QC's StartFrame before PR_SpawnInitialEntities
	  spawns the world (sv_init.c:1657 vs :1686), so this function reads these
	  names before worldspawn's registercvar can create them.  cvar() on a miss
	  auto-creates as the EMPTY STRING (PF_Cvar_FindOrGet, pr_bgcmd.c:1871-1884,
	  pr_autocreatecvars defaults 1) and registercvar then declines to overwrite
	  (pr_bgcmd.c:2036).  So the read wins and the default never lands.

	  Five of these six survived that by luck rather than design: lobby_enable,
	  lobby_nocollide and lobby_av_self default to "0" and "" reads as 0 anyway,
	  and lobby_av_rate / lobby_av_alpha are caught by their own <= 0 clamps
	  below.  lobby_avatars is the one with a non-zero default and no clamp --
	  and it cannot have one, because `lobby_avatars 0` is a real setting -- so
	  it read 0 for the life of every process.  ftesurf/logs/b51b.log:343 logs
	  "Created QC Cvar lobby_avatars" to prove it.

	  What that cost: a lobby switched on from the console rather than through
	  cfg/lobby/lobby.cfg spawned NO AVATARS AT ALL.  Lobby_Resync takes its else
	  branch and removes them, Lobby_Frame returns before the pose loop, and
	  Lobby_ClientConnect's own test refuses too -- so 32 people share a map and
	  see nobody, with nothing printed.  It only ever worked because
	  cfg/lobby/lobby.cfg `set`s the value before the map loads, which is exactly the
	  kind of accident that hides a bug until the day someone types the command
	  instead.

	  Same trap as run_starthop_strict (sv_timer.qc:5867-5895) and as vbsp_mp in
	  sv_main.qc.  Third time in this tree; register beside the read.
	*/
	registercvar("lobby_enable",    "0");
	registercvar("lobby_nocollide", "0");
	registercvar("lobby_avatars",   "1");
	registercvar("lobby_av_rate",   "15");
	registercvar("lobby_av_alpha",  "1");
	registercvar("lobby_av_self",   "0");
	registercvar("lobby_av_colors", "1");
	registercvar("lobby_av_fx",     "1");
	registercvar("lobby_av_fxmax",  "8");
	/*
	  BUILD 64: the board probe, registered here so it EXISTS at 0 rather than
	  being auto-created by the first cvar() read.  registercvar declines a name
	  that already exists (and cvar() creates it as ""), so a default registered
	  after the first read never lands -- which has silently killed three
	  features in this tree already.  The default is 0 and must stay 0: this is
	  a deliberate, operator-typed action.
	*/
	registercvar("lobby_run_probe", "0");

	lobby_on        = cvar("lobby_enable");
	lobby_nocollide = cvar("lobby_nocollide");
	lobby_avatars   = cvar("lobby_avatars");
	lobby_colors    = cvar("lobby_av_colors");
	lobby_fxon      = cvar("lobby_av_fx");

	// The ceiling on how many players may carry particles at once.  Read with
	// a floor of 0 rather than a <= 0 clamp to a default, because 0 is a real
	// setting here -- "allow effects, but let nobody actually have them" is how
	// you take the particles away without taking the switch away.
	lobby_fxmax = cvar("lobby_av_fxmax");
	if (lobby_fxmax < 0)
		lobby_fxmax = 0;

	lobby_rate = cvar("lobby_av_rate");
	if (lobby_rate <= 0)
		lobby_rate = 15;

	lobby_alpha = cvar("lobby_av_alpha");
	if (lobby_alpha <= 0)
		lobby_alpha = 1;

	lobby_self = cvar("lobby_av_self");

	/*
	  Patch 340: the per-map shuffle latch died with the stride it rotated --
	  Lobby_ColourFor rolls a free colour at random now, and a random pick
	  needs no rotation.  The latch had to live HERE rather than in worldspawn
	  for the StartFrame-vs-SpawnInitialEntities ordering the registercvar
	  block above documents; nothing replaced it because nothing needs it.
	*/

	// Dimensions are cheap and must track the cvar live -- see the essay on
	// Lobby_ApplyDimensions.  Done for every player whether or not the lobby
	// is on, because turning the lobby OFF has to put them back.
	p = find(world, classname, "player");
	while (p)
	{
		Lobby_ApplyDimensions(p);

		/*
		  BUILD 57, STAGE T: and the wire copy of "is this a lobby", for the same
		  reason the dimensions above are done unconditionally -- turning the lobby
		  OFF has to reach the client too, or it would go on keeping lobby times
		  for a session that is writing its own.

		  Through Lobby_Active() rather than the lobby_on just cached above, so
		  there is one speller of the question and not two.  One cvar lookup per
		  player per frame, against an array walk and a setsize on the line above.
		*/
		p.lobby_stat = (Lobby_Active() ? LS_LOBBY : 0)
		             + (Lobby_NoPB()  ? LS_NOPB  : 0)
		             + (Lobby_NoRec() ? LS_NOREC : 0);

		if (p.lobby_ann_due > 0)
		if (time >= p.lobby_ann_due)
			Lobby_AnnJoin(p);               // Patch 371: after the colour pass published tc

		p = find(p, classname, "player");
	}

	if (lobby_on != lobby_was_on)
	{
		lobby_was_on = lobby_on;
		Lobby_Resync();
	}

	if (!lobby_on || !lobby_avatars)
		return;

	/*
	  Re-resolve colours once a second.

	  There is no userinfo-change callback in SSQC, so a `setinfo lobbycolor`
	  typed mid-game can only be noticed by looking.  Re-resolving from scratch
	  rather than diffing the info string also picks up the other case that has
	  no callback either: somebody LEFT, and the colour they were holding is now
	  free for whoever wanted it.

	  Assigning .colormod unconditionally is safe and is not a per-second
	  network cost -- the delta compressor compares the packed bytes and only
	  flags UF_COLORMOD when they actually differ (sv_ents.c:1079-1080), so an
	  unchanged colour writes nothing to any client.
	*/
	if (time >= lobby_colcheck)
	{
		lobby_colcheck = time + 1;

		nfx = 0;
		p = find(world, classname, "player");
		while (p)
		{
			p.lobby_colour = Lobby_ColourFor(p);

			/*
			  PATCH 341: `setinfo lobbyrgb "r g b"` BEATS THE PALETTE for the
			  body, and the palette stays for everything pre-generated: the
			  nearest index becomes .lobby_colour, so trail, motes, chat tc and
			  the taken-colour logic all keep working unchanged, while colormod
			  and glowmod take the exact triple in Lobby_ApplyColour/FX.
			*/
			rgbv = Lobby_ParseRGB(infokey(p, "lobbyrgb"));
			if (rgbv_x >= 0)
			{
				p.lobby_custom = TRUE;
				p.lobby_rgb    = rgbv;
				p.lobby_colour = Lobby_NearestColour(rgbv);
			}
			else
			{
				p.lobby_custom = FALSE;
				p.lobby_colour = Lobby_ColourFor(p);
				p.lobby_rgb    = Lobby_PaletteRGB(p.lobby_colour);
			}

			/*
			  What this player ASKED for, then what they GET.

			  lobby_av_fx 0 is the master switch and beats every opt-in: that
			  is the falsifier for the whole effects feature, and it has to
			  work even for a client who has already set lobbyfx.

			  The cap is counted in find() order, which is edict order, which
			  is join order -- so a full lobby gives the effects to whoever
			  turned them on first rather than to whoever the loop happens to
			  reach.  Deterministic, and explicable to the person who does not
			  get them.
			*/
			want = 0;
			if (lobby_fxon)
			{
				want = stof(infokey(p, "lobbyfx"));
				if (want < 0)
					want = 0;

				// Particles are what the cap is about.  Subtraction rather
				// than a complement because QC has no reliable bitwise not.
				if (nfx >= lobby_fxmax)
					want = want - (want & (FS_AVFX_TRAIL | FS_AVFX_MOTES));
				else if (want & (FS_AVFX_TRAIL | FS_AVFX_MOTES))
					nfx = nfx + 1;
			}
			p.lobby_fx = want;

			/*
			  PATCH 340: trail colour, `setinfo lobbytrail <n>`, resolved here
			  beside the mask rather than inside Lobby_ApplyFX because this loop
			  is the one place that reads userinfo.  Out of range or unset means
			  "match my colour", which is the pre-340 behaviour.
			*/
			tc = stof(infokey(p, "lobbytrail"));
			if (tc >= 1 && tc <= FS_AVCOLOURS)
				p.lobby_trailc = tc;
			else
				p.lobby_trailc = p.lobby_colour;

			/*
			  PATCH 340: PUBLISH THE COLOUR, two keys and one stuffcmd.

			  `tc` is the engine's own chat-name colour key (CL_PlayerColor,
			  cl_parse.c): setting it is what makes the speaker's name in every
			  client's chat -- engine console, notify area and the CSQC chatbox
			  alike -- the colour of their avatar.  forceinfokey rather than a
			  stuffed `setinfo` because it writes the server's copy AND
			  broadcasts the userinfo change (PF_ForceInfoKey_Internal ->
			  SV_BroadcastUserinfoChange, pr_cmds.c:10001) without touching the
			  client's config: the colour belongs to the connection, and a
			  re-roll on the next connect must not fight an archived value.
			  Unchanged writes are detected engine-side and cost no broadcast,
			  so the unconditional 1 Hz call is the cheap one.

			  `lc` is the palette index itself, for the two CSQC panels that
			  draw swatches (the player list, the customizer).  tc is lossy --
			  twelve colours into seven console hues -- and a panel that showed
			  the console colour as "your colour" would disagree with the avatar
			  standing next to it.

			  cl_pcolour is the OWNER's mirror, on change only: the customizer
			  reads it to mark the swatch the server actually resolved, which is
			  not necessarily the one asked for (a taken colour falls through to
			  the random pick).  The slot id rides the *phash infokey, set once
			  at connect in Lobby_ClientConnect; this one can change
			  mid-connection when somebody leaves, so it rides the loop.
			*/
			forceinfokey(p, "tc", ftos(Lobby_TcOf(p.lobby_colour)));
			forceinfokey(p, "lc", ftos(p.lobby_colour));
			/*
			  PATCH 341: the exact worn rgb, for swatches and previews on other
			  clients -- `lc` alone would show the nearest palette entry and a
			  custom colour would read as somebody else's.  Unchanged writes
			  cost no broadcast, so the 1 Hz unconditional call is the cheap one.
			*/
			forceinfokey(p, "lrgb", sprintf("%g %g %g",
			    floor(p.lobby_rgb_x * 255 + 0.5),
			    floor(p.lobby_rgb_y * 255 + 0.5),
			    floor(p.lobby_rgb_z * 255 + 0.5)));
			if (p.lobby_colour != p.lobby_csent)
			{
				p.lobby_csent = p.lobby_colour;
				stuffcmd(p, sprintf("set cl_pcolour %g\n", p.lobby_colour));
			}

			if (p.lobby_av)
			{
				Lobby_ApplyColour(p.lobby_av, p);
				Lobby_ApplyFX(p.lobby_av, p);
			}
			p = find(p, classname, "player");
		}
	}

	av = find(world, classname, "lobbyavatar");
	while (av)
	{
		// Read the successor first: Lobby_AvatarPose can remove `av`.
		nx = find(av, classname, "lobbyavatar");
		Lobby_AvatarPose(av);
		av = nx;
	}
};

/*
  Connect / disconnect hooks, called from sv_player.qc.

  Spawning on connect rather than lazily in Lobby_Frame means a joining player
  is visible on the frame they appear rather than up to 1/rate later, and it
  keeps the per-frame path a pure pose copy with no allocation in it.
*/
/*
===========================================================================
  The master-server heartbeat.  Patch 270, Stage 3a.

  WHY THIS EXISTS AT ALL, given that FTE ships a master server.  It cannot be
  used.  SV_Heartbeat (net_master.c:604) opens with

      if (sv_public.ival <= 0 || SSV_IsSubServer())
          return;

  so a mapcluster child -- which is exactly what every lobby will be once
  Stage 5 lands -- never advertises itself to any master, ever.  The player
  counts the map picker wants therefore cannot come from gethostcache*, and
  a small directory service is not a preference, it is the only option.  This
  is recorded here because "just use the master server" is the obvious
  objection and it is already closed.

  Off unless lobby_master names a URL.  A server that has not been pointed at
  a directory sends nothing anywhere, which keeps a listen server -- i.e.
  every single-player session, which runs this same progs -- silent.
===========================================================================
*/
float  lobby_run_waiting;       // build 64: the probe has said "waiting" once
string lobby_board_said;        // what serverinfo "board" currently says
float  lobby_hb_next;           // next server time to send
float  lobby_hb_id;             // uri request id, so replies can be told apart
float  lobby_hb_lastcode;       // last status reported, to log changes only
float  lobby_hb_seen;           // has any reply been classified yet

/*
  Fire-and-forget, but not silent-on-failure.

  A heartbeat that is being refused looks identical to one that is working:
  the server carries on, and the lobby simply never appears in anyone's
  picker.  Logging only on a CHANGE of status code gives one line when it
  breaks and one line when it recovers, instead of one line every five
  seconds forever.

  This is the only URI_Get_Callback in the server progs -- the engine finds it
  by name (pr_bgcmd.c:6003) and there can be exactly one, so anything else
  that ever wants uri_get on the server has to branch inside this function
  rather than declare its own.

  BUILD 64 MADE THAT PROMISE COME TRUE, and it is the reason for the parity
  test at the top of the function.  The run submission below is the second
  caller, it could not declare its own callback, and until it branched here
  every one of its replies was being read as a heartbeat status -- a 204 from
  /api/run would have printed "directory returned 204" and then SUPPRESSED the
  next genuine heartbeat change, because lobby_hb_lastcode had been overwritten
  by a code the heartbeat never produced.

  THE DISCRIMINATOR IS THE PARITY OF THE REQUEST ID.  Heartbeats take even ids
  and run submissions odd ones, from two counters that both step by two, so the
  two streams cannot collide however many of either are in flight.  The
  alternative -- a table of outstanding submission ids -- is a fixed-size array
  that silently mis-classifies the reply once more runs finish at once than it
  has slots, which on a full lobby at a stage boundary is not hypothetical.
*/
void(float reqid, float code, string body) Lobby_RunReply;

/*
===========================================================================
  THE DIRECTORY CAN MOVE THIS SERVER.  Build 67.

  WHAT IT IS FOR.  "Every map someone plays is a lobby": the menu asks surfd
  where to play a map, surfd picks an idle server, and THIS is how that server
  finds out.  It closes the plan's Layer 0 -- on a listen server the host owns
  sv.time, the movement cvars, the progs and the timer, so a world record there
  is a cvar edit rather than a cheat, which is why Lobby_SubmitRun refuses one.
  Getting the player onto a server the operator runs is the whole fix, and it
  needs a way to put that server on the map they asked for.

  WHY THE HEARTBEAT REPLY AND NOT RCON.  The obvious implementation is
  `rcon changelevel <map>` from surfd, and it is wrong three times over.  FTE's
  amplification guard gates rcon BEFORE the password check with no loopback
  exemption, and fifteen packets in thirty seconds is a SELF-EXTENDING
  24-HOUR BLOCK that only a restart clears -- so a busy evening would silently
  take the admin panel down for a day.  It would need the rcon password in
  surfd's reach for something that is not administration.  And it would only
  work for a lobby on surfd's own machine, which is the exact assumption
  `replays.node` exists to stop us baking in twice.

  This channel already exists and is already authenticated: the POST carries
  lobby_master_key, so only the directory we chose to key can answer it.

  NOTHING ABOUT THE REPLY IS TRUSTED ANYWAY, and that is not belt-and-braces.
  The body goes to localcmd, which is the console: a reply of
  "map surf_x\nquit" or "map surf_x; rcon_password hunter2" is remote code
  execution against this server from whoever answers lobby_master.  The menu
  has had exactly this guard on lobby addresses since build 55 (ui_addr_ok) for
  exactly this reason, and a directory that is compromised, substituted, or
  simply typo'd into a hostile host is the threat both of them answer.  So the
  name is checked character by character against an ALLOW-list -- enumerate
  what a map name may contain and refuse everything else, so no metacharacter
  anybody thinks of later gets through.

  WHY IT DOES NOT SIMPLY OBEY.  Two refusals, and both are about people:

    * ANYBODY HERE AND THE ANSWER IS NO.  surfd only ever claims a server
      reporting zero players, but the reply it sends describes the world as of
      that heartbeat, up to lobby_master_rate seconds ago, and somebody can
      join inside that window.  Moving the map then would throw a stranger out
      of a run to satisfy a menu -- which is precisely the outcome the idle
      rule exists to make impossible, and a rule enforced at only one end is
      enforced nowhere.  surfd drops the claim the moment it sees a player, so
      refusing here costs one wasted instruction and never loops.

    * THE MAP WE ARE ALREADY ON IS NOT A DESTINATION.  `changelevel` to the
      current map is a full reload: it drops every client to reconnect for
      nothing.  Lobby_NextMap refuses the same thing for the same reason.
===========================================================================
*/
float() Lobby_PlayerCount;

/*
  May this string be a map name?  The allow-list, and a transcription of
  surfd's own _MAPNAME_OK so the two ends agree about what they will exchange.

    48-57  0-9      46  .        65-90  A-Z
    97-122 a-z      95  _        43  +      45  -

  Numeric codes because 'x' in QuakeC is a VECTOR literal, not a character --
  the same note ui_addr_ok carries in m_main.qc.  No '/', no '\', no ';', no
  whitespace, no quote, no control character: a name that passes this cannot
  start a second console command however it is interpolated.
*/
float(string s) Lobby_MapNameOK =
{
	local float i, n, c;

	n = strlen(s);
	if (n < 1 || n > 64)
		return FALSE;

	// Must OPEN alphanumeric, so a name can never look like a switch to the
	// console parser and can never be a bare "." or "-".
	c = str2chr(s, 0);
	if (!(c >= 48 && c <= 57) && !(c >= 97 && c <= 122) && !(c >= 65 && c <= 90))
		return FALSE;

	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (c >= 48 && c <= 57)  continue;
		if (c >= 97 && c <= 122) continue;
		if (c >= 65 && c <= 90)  continue;
		if (c == 46 || c == 95 || c == 43 || c == 45) continue;
		return FALSE;
	}
	return TRUE;
};

/*
  Act on one heartbeat reply.  Returns TRUE if it carried an instruction,
  whether or not we obeyed it -- the caller uses that only to decide whether
  the body was ordinary, and every refusal below says so on the console,
  because a directory quietly failing to move a server is the shape of bug
  that takes a day to find.

  "ok" IS THE ONLY OTHER BODY THIS HAS EVER SENT, so anything that is not an
  instruction is left entirely alone -- including a future word this build has
  never heard of.  That is what makes the channel extensible in the safe
  direction: an older server reads a newer instruction as a successful
  heartbeat and does nothing, which is a lobby with fewer maps rather than a
  broken one.
*/
float(string body) Lobby_Directed =
{
	local string want;
	local float  n;

	if (substring(body, 0, 4) != "map ")
		return FALSE;

	want = substring(body, 4, strlen(body) - 4);

	/*
	  TRIM TRAILING WHITESPACE, and nothing else.  A proxy or a future writer
	  can legitimately leave a newline on a text/plain body, and refusing the
	  whole instruction over it would be a fault that only appears once nginx
	  is in the path -- i.e. in production and not in any test.  Leading
	  whitespace is NOT trimmed: it cannot get past Lobby_MapNameOK's opening
	  character test, and silently accepting it would mean two spellings of one
	  instruction.
	*/
	n = strlen(want);
	while (n > 0 && str2chr(want, n - 1) <= 32)
		n = n - 1;
	want = substring(want, 0, n);

	if (!Lobby_MapNameOK(want))
	{
		print(sprintf("^1lobby:^7 directory asked for a map name this server "
		              "will not put on a console -- ignored (%g chars)\n", n));
		return TRUE;
	}

	if (strtolower(want) == strtolower(mapname))
		return TRUE;            // already there; a reload is not a move

	if (Lobby_PlayerCount() > 0)
	{
		print(sprintf("^3lobby:^7 directory wants %s, but somebody is here -- "
		              "staying on %s\n", want, mapname));
		return TRUE;
	}

	print(sprintf("^5lobby:^7 directory sends this server to %s\n", want));
	localcmd(sprintf("changelevel %s\n", want));
	return TRUE;
};

void(float reqid, float responsecode, string resourcebody) URI_Get_Callback =
{
	// Odd ids are run submissions; see the parity note above.
	//
	// THE ID IS PASSED ON, not just used to classify.  Build 65 answers the
	// submitter with their rank, so the reply has to reach the player who
	// finished -- and the id is the only thing tying it to them.  See the
	// lobby_rq_id field note.
	if (reqid & 1)
	{
		Lobby_RunReply(reqid, responsecode, resourcebody);
		return;
	}

	/*
	  SUCCESS IS 0, NOT 200, AND THIS COST A DEBUGGING SESSION.

	  PR_uri_get_callback2 (pr_bgcmd.c:6014) reads, verbatim:

	      G_FLOAT(OFS_PARM1) = (replycode!=200)?replycode:0;
	          //for compat with DP, we change any 200s to 0.

	  So QC never sees 200.  A working request arrives here as responsecode 0,
	  and the obvious `if (responsecode == 200)` is dead code that can never run.

	  The second half of the trap is worse, because it hides the first: a QC
	  global starts at 0, so a "has the status changed" test against a
	  zero-initialised lastcode ALSO swallows the very first success.  The
	  result is a heartbeat loop that is working perfectly and says nothing at
	  all -- indistinguishable from one that is not running.  Hence the explicit
	  `seen` flag rather than a sentinel value in lobby_hb_lastcode.
	*/
	/*
	  ABOVE THE STATUS-CHANGE TEST, AND THAT PLACEMENT IS THE WHOLE THING.

	  The `return` below fires whenever the status code has not changed -- which
	  on a healthy lobby is EVERY BEAT FOREVER, because a working heartbeat
	  returns 0 every five seconds for the life of the map.  A directive handled
	  after it would be read exactly once, on the first reply after a status
	  change, and be invisible the rest of the time.  That failure has no
	  symptom on either end: surfd logs that it told the server to move, the
	  server logs a healthy heartbeat, and the map never changes.

	  Only on success.  A 403 or a 500 carries an error page, not an
	  instruction, and running the parser over one is how a body that happens to
	  begin "map " becomes a console command.
	*/
	if (!responsecode)
		Lobby_Directed(resourcebody);

	if (lobby_hb_seen && responsecode == lobby_hb_lastcode)
		return;
	lobby_hb_seen     = TRUE;
	lobby_hb_lastcode = responsecode;

	if (!responsecode)
		print("^2lobby:^7 directory accepted heartbeat\n");
	else
		print(sprintf("^1lobby:^7 directory returned %g (%s)\n",
		              responsecode, resourcebody));
};

/*
  How many people are actually here.

  THE CLASSNAME WALK ALONE COUNTS THE DEAD.  This was a bare
  find(world, classname, "player") loop, and the answer it gives is "how many
  edicts have ever been a player since the map loaded" -- because a client that
  disconnects does not release its edict, and nothing clears the classname.
  One person joining and leaving left the directory advertising a permanently
  occupied lobby, which is the shape the bug was reported in: a server sitting
  at "1 / 32 players" with nobody on it.

  THIS FILE ALREADY SAID SO, NINETY LINES DOWN.  Lobby_ClientDisconnect clears
  .lobby_colour with the comment "Lobby_ColourTaken walks entities whose
  classname is still 'player', and a disconnected client's edict is not freed
  -- it is kept and recycled (sv_main.c:2516-2522)".  The consequence was
  written down for the colour allocator and then not applied to the counter
  directly above it.  Fixing the count rather than clearing the classname on
  disconnect, because the classname is load-bearing for the colour allocator,
  for sv_entities.qc's trigger dispatch and for anything else that finds
  players -- and because the engine already knows the answer.

  clienttype() IS the engine's own liveness flag, not a QC approximation:
  PF_clienttype (pr_cmds.c:4253-4271) bounds-checks the edict against
  sv.allocated_client_slots and then reads svs.clients[n].state directly,
  returning DISCONNECTED for anything below cs_connected.  There is no state
  a departed client can be left in that reads as connected here.

  Bots count.  There are none in FTESurf, but a bot occupies a slot and shows
  up as a body, so if one ever exists it belongs in the number a player reads
  before deciding whether to join.
*/
float() Lobby_PlayerCount =
{
	local entity p;
	local float n, t;

	n = 0;
	p = find(world, classname, "player");
	while (p)
	{
		t = clienttype(p);
		if (t == CLIENTTYPE_REAL || t == CLIENTTYPE_BOT)
			n = n + 1;
		p = find(p, classname, "player");
	}
	return n;
};

/*
  Defined below, beside the rest of the submission machinery; forward-declared
  here because the probe hook lives in the per-frame function and QuakeC needs
  a definition before a use.  The alternative was a second call in sv_main.qc's
  StartFrame, which another session is editing.
*/
void(entity e, float track, float leg, float ticks, float flags,
     string rec, float recbytes, float rectrunc) Lobby_SubmitRun;

/*
  ---- DOES THIS SERVER POST TIMES?  Build 64. ------------------------------

  THE REPORT THIS EXISTS FOR: "I set a time on bhop_eazy and it didn't write my
  time to the public leaderboard.  I see the fake times you put there, but not
  my time?"  The run was set on a listen server, where Lobby_SubmitRun returns
  at its very first gate -- no lobby_master, therefore no submission -- which
  is the "Ranked = official servers only" decision working exactly as designed.

  THE DESIGN WAS RIGHT AND THE SILENCE WAS NOT.  Every one of those gates
  returns without a word, deliberately: they describe a server that is not
  configured for the board, and printing a complaint on somebody's
  single-player session every time they crossed a finish line would be noise
  about a decision they did not make.  But the player is left with a finish
  screen, a personal best, and a leaderboard that never changes, and NOTHING in
  the game connects those three facts.  A quiet gate is right; an invisible one
  is not.

  SERVERINFO RATHER THAN A STAT, because this is a property of the SERVER and
  not of the player, it is one short word, and it is wanted by the scoreboard
  before any run has happened.  The idiom is already in this tree both ways --
  SV_UpdateMovementServerInfo publishes with forceinfokey(world, ...) and CSQC
  reads with serverkey() all over cl_hud.qc.

  THE VALUES, and each names a DIFFERENT thing to do about it:

    "ranked"  pointed at a directory, keyed, and asking clients for a GUID.
              A finish here goes up.
    "local"   no lobby_master or no lobby_master_key.  Every listen server,
              i.e. every single-player session.  Nothing is wrong; times stay
              on this machine.
    "noid"    keyed and pointed, but sv_guidkey is unset -- so infokey(e,"guid")
              is "" and Lobby_SubmitRun drops every run at its identity gate.
              This is the one that is a FAULT, it is an operator's fault rather
              than a player's, and before this key existed it was completely
              invisible from both ends: the server logged nothing and the
              player's times simply never arrived.

  LATCHED ON CHANGE.  forceinfokey every frame would push a serverinfo update
  to every connected client 66 times a second for a string that changes at most
  when an operator edits a cvar.  The compare is safe against QC string
  lifetimes because `want` only ever holds a LITERAL -- assigning a cvar_string
  result to a global would be a dangling pointer next frame, which is the trap
  the heartbeat documents below.
*/
void() Lobby_BoardState =
{
	local string want;

	registercvar("lobby_master", "");
	registercvar("lobby_master_key", "");

	if (cvar_string("lobby_master") == "")
		want = "local";
	else if (cvar_string("lobby_master_key") == "")
		want = "local";
	else if (cvar_string("sv_guidkey") == "")
		want = "noid";
	else
		want = "ranked";

	if (want == lobby_board_said)
		return;

	/*
	  ONE LINE ON THE SERVER CONSOLE WHEN IT BECOMES A FAULT, and only then.
	  "local" is the normal state of every single-player session and says
	  nothing; "ranked" is the normal state of a lobby and says nothing.  An
	  operator who has set a master and a key has declared an intent to rank,
	  and sv_guidkey silently defeating it is worth interrupting them for --
	  sv_main.c:1855 never asks the client for a GUID unless it is set, so
	  there is no other symptom to notice.
	*/
	if (want == "noid")
		print("^1board:^7 sv_guidkey is unset -- runs cannot be attributed to a "
		      "player and NONE will be submitted.  See cfg/lobby/lobby.cfg.\n");

	lobby_board_said = want;
	forceinfokey(world, "board", want);
};

// Patch 371: where the board answers finishes, Lobby_RunReply tells the others
// about a new best; elsewhere SV_TimerFinish does.  One finish, one line.
float() Lobby_BoardAnswers =
{
	return lobby_board_said == "ranked";
};

void() Lobby_Heartbeat =
{
	local string url, body;
	local float  per, pflags;
	local entity pl;

	/*
	  FIRST, AND ABOVE THE lobby_master GATE BELOW.  The whole point of this key
	  is to describe servers that send nothing -- so publishing it after the
	  early return would tell exactly the servers that need it nothing at all.
	*/
	Lobby_BoardState();

	/*
	  Read fresh rather than cached in a global, and that is a QC lifetime
	  issue rather than a style choice.  cvar_string returns a TEMP string;
	  parked in a global it is valid this frame and dangling by the next.  The
	  float cvars elsewhere in this file are cached because floats have no such
	  problem.
	*/
	// Registered at the read, like the rest.  Reached on the pre-worldspawn
	// StartFrame, so the registration in worldspawn never landed; harmless
	// because the default is "" either way, and corrected anyway so the next
	// person to give one of these a real default does not inherit the trap.
	registercvar("lobby_master", "");

	url = cvar_string("lobby_master");
	if (url == "")
		return;

	/*
	  ---- THE BOARD PROBE.  Build 64, stage 3. --------------------------------

	  `lobby_run_probe 1` submits one synthetic run for the first player on the
	  server and clears itself.  It answers the operator's question -- "is my key
	  right and can this server reach the board at all" -- without waiting for
	  somebody to finish a map, and it is the ONLY way any of this gets tested:
	  a finish cannot be scripted on a zoned map, because zone_goto and setpos
	  both route through SV_TimerWarped, which VOIDS the attempt, so
	  SV_TimerFinish is unreachable from a config by construction.

	  IT SUBMITS WITH TF_CHEAT AND THAT IS THE WHOLE POINT.  surfd refuses a
	  cheated run a board entirely -- 204, deliberately not an error -- so this
	  CANNOT put a time on a leaderboard however it is invoked, by anyone, on any
	  server.  A probe that could would be a forgery tool shipped inside a game
	  whose entire claim is that times are validated, and no amount of "it is
	  only for testing" survives that.

	  AND THE 204 IS A COMPLETE TEST OF THE REQUEST, which is what makes the
	  trade worth taking rather than a consolation.  surfd validates map, track,
	  leg, player, ticks, tickrate, flags and tier -- each a 400 with its own
	  message -- and only THEN decides the run has no board.  So a 204 means
	  every field was well formed and the key was accepted; the only thing it
	  does not exercise is the row actually being written, and that half was
	  already measured in stage 2 against the same field set.  A 400 names the
	  field that is wrong, which is more than a stored row would have told us.
	*/
	if (cvar("lobby_run_probe"))
	{
		/*
		  IT STAYS ARMED UNTIL A PLAYER EXISTS, rather than firing once and
		  clearing.  A submission needs an entity to read a GUID off, and a
		  dedicated server has no player entity until somebody joins -- so the
		  obvious "one shot, whatever happens" version spends itself on the
		  frame the operator typed it, prints a complaint, and leaves them
		  typing it again at exactly the moment they are busy watching a client
		  connect.  Armed-and-waiting also makes it settable in a server config,
		  which is the only way to reach it on a headless box without rcon.

		  The complaint is printed ONCE per arming for the same reason the
		  heartbeat logs only on a change: every frame would be 66 lines a
		  second of the same sentence.
		*/
		pl = find(world, classname, "player");
		if (!pl)
		{
			if (!lobby_run_waiting)
			{
				lobby_run_waiting = TRUE;
				print("^3board:^7 probe armed -- waiting for a player to join\n");
			}
		}
		else
		{
			// 3 adds TF_NOPROFILE: still cheated (real surfd answers 204), but a
			// stub in `cert` mode answers "community", driving the unranked path.
			pflags = TF_CHEAT;
			if (cvar("lobby_run_probe") == 3)
				pflags = pflags | TF_NOPROFILE;
			// 2: a stage-3 post in the SAME frame as the finish below, as a
			// main run's final stage and its finish are (Patch 360).  TF_CHEAT
			// too: a clean probe would be a forgery tool.
			if (cvar("lobby_run_probe") == 2)
				Lobby_SubmitStage(pl, 0, 3, 1111, TF_CHEAT);
			cvar_set("lobby_run_probe", "0");
			lobby_run_waiting = FALSE;
			print("^5board:^7 probe -- one synthetic CHEATED run, which has no "
			      "board and cannot rank\n");
			// No recording: the probe is synthetic, nothing was written, and
			// naming a file that does not exist is the one thing the ledger
			// must never be told.  It still exercises the whole submission
			// path and now prints rep=0 back, which is what makes the chain
			// checkable with nobody on the server.
			Lobby_SubmitRun(pl, 0, 0, 1234, pflags, "", -1, 0);
		}
	}

	if (time < lobby_hb_next)
		return;

	/*
	  Clamped, and the LOW end is the one that matters.  surfd expires a lobby
	  after 30s, so anything up to ~25 is safe; below 1 this would hammer the
	  directory once per frame if the cvar were ever set to 0 by accident, and
	  a 66 Hz HTTP POST loop is a denial of service against your own server.
	*/
	per = cvar("lobby_master_rate");
	if (per < 1)  per = 5;
	if (per > 25) per = 25;
	lobby_hb_next = time + per;

	/*
	  The node id is the PORT and nothing else.

	  It has to be stable across a map change, or an RTV would leave the old
	  map advertised alongside the new one until the directory expired it --
	  one server showing up as two lobbies.  It also has to be unique per
	  process, and under mapcluster every child binds sv_port+N
	  (sv_cluster.c), so the port is unique there by construction.  mapname is
	  the obvious choice and is wrong for the first reason; serverid is 0 on a
	  non-cluster server and is wrong for the second.

	  Note what is NOT sent: no address.  surfd takes the address from the
	  source IP of this request, so a heartbeat cannot advertise a host it does
	  not speak from.
	*/
	body = sprintf("key=%s&node=%s&map=%s&players=%g&max=%g&port=%g&name=%s",
	               uri_escape(cvar_string("lobby_master_key")),
	               uri_escape(sprintf("p%g", cvar("sv_port"))),
	               uri_escape(mapname),
	               Lobby_PlayerCount(),
	               cvar("sv_playerslots"),
	               cvar("sv_port"),
	               uri_escape(cvar_string("hostname")));

	// uri_escape on every field, and it is not decoration: hostname is
	// free-form operator text and an unescaped & or = in it would silently
	// inject extra form fields into this request.
	url = strcat(url, "/api/heartbeat");

	// STEPS BY TWO, so heartbeat ids stay EVEN and can never collide with a run
	// submission's odd ones.  See the parity note on URI_Get_Callback.
	lobby_hb_id = lobby_hb_id + 2;
	uri_post(url, lobby_hb_id, "application/x-www-form-urlencoded", body);
};

/*
===========================================================================
  THE RUN SUBMISSION.  Build 64, stage 3.

  Stages 1 and 2 built the client half of the leaderboard: it asks surfd for a
  board, parses it, and draws it under three tabs.  Every row it has ever drawn
  was put there by hand with curl, because UNTIL THIS FUNCTION THERE WAS NO
  WRITER AT ALL -- `uri_post` appeared exactly once in the whole tree and it was
  the heartbeat above.  A leaderboard nobody can get onto is a demo.

  WHO MAY WRITE IS THE ENTIRE SECURITY MODEL, and it is one `if`.

  surfd refuses a POST without the shared key, so only a server the operator has
  keyed can put a row on the board.  That IS the plan's "Ranked = official
  servers only" decision, and it closes the hole the plan ranks above every
  input-layer concern: on a listen server the host owns sv.time, the movement
  cvars, the progs and the timer, so "beat the world record" is a cvar edit
  rather than a cheat.  A player-hosted server holds no key, and the test below
  means it does not even ask -- it keeps its times locally instead, which is the
  Local tab and has existed since build 24.

  WHAT IS DELIBERATELY NOT DECIDED HERE:

  - WHICH RUNS HAVE A BOARD.  Practice and cheated runs have none, and surfd
    answers 204 for them rather than an error.  This function could mirror that
    rule with FS_RunClass and save the request -- and deliberately does not.
    The rule is written twice already (here in QC, once in Python), and a third
    copy that disagreed would mean a run silently never submitted, which is the
    one failure nobody would ever see.  A finish is a rare event; one POST that
    comes back 204 costs less than a rule that can drift.
  - WHICH TIER THE ROW LANDS IN.  This always claims `ranked`; surfd lowers it
    when the flags are not certifiable (TF_NOJOURNAL, TF_NORULESET) or when the
    key does not vouch for the tier.  A submitter that graded itself would be a
    submitter that could grade itself generously.

  THE PLAYER ID IS THE ENGINE's GUID, AND IT IS A PLACEHOLDER THAT SAYS SO.
  sv_main.c:137 warns in as many words: "do NOT treat the client's GUID as
  something that is secure", and surfd's own header says a row means "an
  official server saw this player finish", not "this human finished".  The
  local-keypair work is Phase 2 of the plan and it is a VALUE change in this
  one field rather than a schema change, which is why the column exists now.

  It requires `sv_guidkey` to be set on the server (sv_main.c:1855) -- with it
  empty the engine never asks the client for a GUID and infokey returns "".  A
  run with no identity is not submitted, because the board's primary key is the
  player and a row keyed on "" would collect every anonymous player's times
  into one impostor.

  NO runid IS SENT, and that is a decision rather than an omission.  surfd takes
  the field so evidence can be found later, but the evidence link that matters
  is Phase 3's rolling commitment hash, not a local filename stamp -- and the
  stamp is not kept anywhere after SV_RecOpen writes it, so sending one would
  mean adding a zoned string field to hold a value Phase 3 replaces.  The column
  stays empty until there is a real answer to put in it.
===========================================================================
*/
float lobby_run_id;             // uri request id; ODD, always -- see the parity note
float lobby_run_sent;           // submissions attempted this session
float lobby_run_ok;             // ...and how many surfd stored
float lobby_run_lastcode;
float lobby_run_seen;

/*
  The other half of the callback.  Fire-and-forget like the heartbeat, and
  noisy on a CHANGE of status for the same reason: a board that is refusing
  every run looks exactly like one nobody has finished on.

  204 IS NOT A FAILURE and is reported as what it is.  It means the run was
  received and understood and has no board to stand on -- a practice or cheated
  run -- which is the single most common non-zero answer this will ever get and
  must not read as an error beside it.
*/
/*
  ---- WHERE THE RUN LANDED, PUBLISHED TO THE PLAYER.  Build 65. ------------

  Two halves of one key, and they are separate functions because they know
  different things at different times.  See the *wrank essay in sh_defs.qc for
  the wire format and for why this is a userinfo key rather than the two stats
  the plan reserved.

  THE SUBJECT IS STAMPED ONCE, AT SUBMISSION, AND NEVER RE-DERIVED.  The answer
  comes back some milliseconds later over a network, and by then `mapname` may
  be a different map -- a map change disconnects nobody, so this key outlives
  the map it describes.  Re-deriving the map at reply time would stamp a fresh
  map name onto an old run's track/leg/ticks and manufacture exactly the false
  match the format exists to prevent.  So Lobby_RankAnswer READS THE SUBJECT
  BACK out of the key it is about to rewrite and copies it across verbatim; it
  never asks the world what map this is.

  If the key has gone (it cannot, but a rewrite that assumes is a rewrite that
  can invent) the answer is dropped rather than published against a guess.
*/
// `key` is "*wrank" (a finish); "*srank" is reserved for stage fill-in.  The
// grammar is sh_defs.qc's, trailing fields included.
void(entity e, string key, float track, float leg, float ticks) Lobby_RankPending =
{
	// %d ticks: %g turns 1000000+ into exponent form and the client's exact
	// subject match (Results_KeyRank) then never fires.
	forceinfokey(e, key,
	             sprintf("%s %g %g %d %g 0 0 0 0 0",
	                     mapname, track, leg, ticks, WR_PENDING));
};

void(entity e, string key, float state, float rank, float of,
     float stored, float prevms, float tier) Lobby_RankAnswer =
{
	local string subject;

	// tokenize is the server's command tokenizer (KRIMZON_SV_PARSECLIENTCOMMAND).
	// Safe here: this runs from the engine's uri callback, never nested inside
	// SV_ParseClientCommand, so there is no argv() state being clobbered under
	// somebody else's feet.
	if (tokenize(infokey(e, key)) < 4)
		return;
	subject = sprintf("%s %s %s %s", argv(0), argv(1), argv(2), argv(3));

	forceinfokey(e, key,
	             sprintf("%s %g %g %g %g %d %g", subject, state, rank, of,
	                     stored, prevms, tier));
};

// A demoted run is TOLD, in the chatbox (PRINT_CHAT; PRINT_HIGH only reaches
// the console): with the Community chip gone it is on no board the player sees.
void(entity e, float flags) Lobby_SayUnranked =
{
	local string why;

	why = FS_CertWhy(flags);
	if (why == "")
		why = "not certified";      // surfd and TF_UNCERT disagree: worth seeing
	sprint(e, PRINT_CHAT, sprintf("^5board:^7 ^3unranked (%s)^7 -- not on the "
	       "online board\n", why));
};

// Patch 371: the others hear a new online best (the finisher has their own line,
// cl_banner.qc).  Full runs on the ranked board only; Lobby_AnnGate paces it.
void(entity e, float rank, float of, float prevms) Lobby_SayBoardPB =
{
	local string nm, where, t, pos;
	local float rate;

	if (!Lobby_AnnOn())
		return;
	if (clienttype(e) != CLIENTTYPE_REAL)
		return;                                 // gone before the board answered
	if (!Lobby_AnnGate(e, rank, e.lobby_rq_track))
		return;
	rate = e.run_movetickrate;                  // the rate that made the count (Lobby_RunBody)
	if (rate <= 0)
		rate = cvar("pm_ticrate");
	nm    = Lobby_ChatName(e);
	where = Lobby_Where(e.lobby_rq_track);
	t     = Time_TickString(e.lobby_rq_ticks, rate);
	if (rank == 1)
	{
		Lobby_SayOthers(e, sprintf("^3board:^7 %s set the ^3world record^7 on %s -- %s\n",
		                nm, where, t));
		return;
	}
	pos = "";
	if (rank > 0)
		pos = sprintf(", #%g of %g", rank, of);
	if (prevms <= 0)
		Lobby_SayOthers(e, sprintf("^5board:^7 %s finished %s for the first time -- %s%s\n",
		                nm, where, t, pos));
	else
		Lobby_SayOthers(e, sprintf("^5board:^7 %s set a personal best on %s -- %s%s\n",
		                nm, where, t, pos));
};

void(float reqid, float code, string body) Lobby_RunReply =
{
	local entity who;
	local int   root;
	local float rank, of, stored, prevms, tier, isstage, isold, strk, sleg, sfl, u;
	local string key;

	if (!code)
		lobby_run_ok = lobby_run_ok + 1;

	/*
	  THE SUBMITTER, IF THEY ARE STILL HERE.  world means nobody is waiting on
	  this id -- the player left, or has since submitted again -- and the answer
	  is then dropped without a word.  findfloat returns world for no match and
	  world is a perfectly valid entity to hold, so the guard is on USING it,
	  not on the search.
	*/
	isstage = isold = FALSE;
	strk = sleg = sfl = 0;
	who = findfloat(world, lobby_rq_id, reqid);
	if (who != world)
		who.lobby_rq_id = 0;            // answered; do not match it twice
	else
	{
		// A stage posted from a main run (Patch 360): its own id, its own key.
		who = findfloat(world, lobby_sq_id, reqid);
		if (who != world)
		{
			who.lobby_sq_id = 0;
			isstage = TRUE;
			strk = who.lobby_sq_track;
			sleg = who.lobby_sq_leg;
			sfl  = who.lobby_sq_flags;
		}
		else
		{
			who = findfloat(world, lobby_sq_old, reqid);
			if (who != world)
			{
				who.lobby_sq_old = 0;
				isstage = isold = TRUE;
				strk = who.lobby_sq_oldtrack;
				sleg = who.lobby_sq_oldleg;
				sfl  = who.lobby_sq_oldflags;
			}
		}
	}
	key = "*wrank";
	if (isstage)
		key = "*srank";

	/*
	  PARSED WITH THE REAL PARSER.  sh_json.qc is already in sv_progs.src, and
	  a hand-rolled scan for `"rank":` would be a second JSON implementation
	  written to match one server's current key order -- Flask sorts its keys
	  and is entitled to stop.

	  HANDLE 0 IS A VALID NULL NODE (see sh_json.qc), so a body that is not JSON
	  at all, or one from an older surfd with no rank in it, walks to 0 and
	  reads 0 -- which is exactly the "no answer" value the client already draws
	  as a dash.  The only thing that must not happen is json_free on a failed
	  parse, because json_free is PF_memfree and 0 is the engine's static node.
	*/
	root   = json_parse(body);
	rank   = json_get_float(json_find_object_child(root, "rank"));
	of     = json_get_float(json_find_object_child(root, "of"));
	stored = json_get_float(json_find_object_child(root, "stored"));
	prevms = json_get_float(json_find_object_child(root, "prevms"));
	// A surfd older than Patch 353 sends no tier: read as ranked, as it was.
	tier   = WRT_RANKED;
	if (json_get_string(json_find_object_child(root, "tier")) == "community")
		tier = WRT_COMMUNITY;
	if (root)
		json_free(root);

	if (who != world)
	{
		/*
		  BRANCHED ON THE CODE FIRST AND THE RANK SECOND, which is not how this
		  was first written and the difference matters.

		  The first cut tested `!code && rank > 0` and let everything else fall
		  through to the failure branch -- so a directory that ACCEPTED the run
		  and simply did not say where it landed was reported to the player as
		  one that had refused it.  That is not hypothetical: it is precisely
		  what a surfd older than this build answers, so deploying these progs
		  before the directory would have had the game telling players their
		  runs were rejected while the rows went up on the board behind them.
		  See WR_STORED in sh_defs.qc.
		*/
		if (!code)
		{
			if (!isold)                 // an older stage: *srank is the newer one's
			{
				if (rank > 0)
					Lobby_RankAnswer(who, key, WR_RANKED, rank, of,
					                 stored, prevms, tier);
				else
					Lobby_RankAnswer(who, key, WR_STORED, 0, 0,
					                 stored, prevms, tier);
			}

			/*
			  A LINE ONLY WHEN THE BOARD ACTUALLY MOVED.  The finish card
			  draws the rank either way, and a run that did not improve has
			  not changed anything the player did not already know.  On a
			  bhop map a finish is ten seconds apart, so a line on every one
			  of them would bury the messages that matter -- including the
			  two below.
			*/
			if (stored)
			{
				if (tier == WRT_COMMUNITY && isstage)
				{
					// Once per reason: every stage of a run carries the same bits.
					u = sfl & TF_UNCERT;
					if (!u)
						u = 1;              // surfd's own reason: said once too
					if (u - (u & who.lobby_sq_told))
					{
						Lobby_SayUnranked(who, sfl);
						who.lobby_sq_told = who.lobby_sq_told | u;
					}
				}
				else if (tier == WRT_COMMUNITY)
				{
					// Once per reason, like the stages: the finish line says UNRANKED too.
					u = who.lobby_rq_flags & TF_UNCERT;
					if (!u)
						u = 1;
					if (u - (u & who.lobby_sq_told))
					{
						Lobby_SayUnranked(who, who.lobby_rq_flags);
						who.lobby_sq_told = who.lobby_sq_told | u;
					}
				}
				else if (rank > 0 && isstage)
					sprint(who, PRINT_HIGH,
					       sprintf("^5board:^7 %s: ^2#%g^7 of %g\n",
					               FS_LegWord(strk, sleg), rank, of));
				else if (rank > 0)
					sprint(who, PRINT_HIGH,
					       sprintf("^5board:^7 your time is up: ^2#%g^7 of %g\n",
					               rank, of));
			}
			if (stored)
			if (!isstage)
			if (who.lobby_rq_leg == 0)
			if (tier == WRT_RANKED)
			if (FS_RunClass(who.lobby_rq_flags) == RC_CLEAN)
				Lobby_SayBoardPB(who, rank, of, prevms);
		}
		else if (isold)
			isold = FALSE;              // an older stage's failure: nothing to say
		else if (code == 204)
			Lobby_RankAnswer(who, key, WR_NOBOARD, 0, 0, 0, 0, 0);
		else if (isstage)
			Lobby_RankAnswer(who, key, WR_FAILED, 0, 0, 0, 0, 0);  // the finish's notice is not spent on a stage
		else
		{
			Lobby_RankAnswer(who, "*wrank", WR_FAILED, 0, 0, 0, 0, 0);

			/*
			  LATCHED PER PLAYER, on the lobby_said_noid precedent and for the
			  same reason: a directory that is down is down for everybody, so a
			  global latch would tell whoever finished first and nobody after.
			  This is a fault the player did not cause and cannot fix, so it is
			  said once and then dropped -- the server console keeps the
			  per-code detail below.
			*/
			if (!who.lobby_said_fail)
			{
				who.lobby_said_fail = TRUE;
				sprint(who, PRINT_HIGH, "^1board:^7 the leaderboard did not "
				         "take your run -- it is saved on this machine.\n");
			}
		}
	}

	if (lobby_run_seen && code == lobby_run_lastcode)
		return;
	lobby_run_seen     = TRUE;
	lobby_run_lastcode = code;

	if (!code)
		print(sprintf("^2board:^7 directory stored a run (rank %g of %g, %s)\n",
		              rank, of, (tier == WRT_COMMUNITY) ? "community" : "ranked"));
	else if (code == 204)
		print("^3board:^7 run has no board (practice or cheated) -- not an error\n");
	else if (code == 403)
		print("^1board:^7 directory refused the key -- this server cannot rank runs\n");
	else
		print(sprintf("^1board:^7 directory returned %g (%s)\n", code, body));
};

/*
  BUILD 66: `rec` IS A PARAMETER, AND IT HAD TO BE.

  It is the BASENAME of the recording this run left on disk, "" when it left
  none.  surfd stores it in the replay ledger, which is what lets a beaten run
  stay attributable now that lobbies delete nothing (rec_runs_keep 0): the
  board keeps one row per player, and the ledger keeps every file behind it.

  WHY A PARAMETER RATHER THAN A FIELD READ HERE.  Two compile-order facts, and
  between them they leave no other shape.  sv_lobby.qc is line 27 of
  sv_progs.src and sv_timer.qc is line 29, so this file cannot see a field
  sv_timer.qc declares, nor call SV_RecWho to rebuild the name -- QuakeC has no
  forward references.  The alternative was declaring the field in shared defs,
  which would put a server recorder's bookkeeping in the CSQC and menu VMs to
  save one argument.

  AND IT IS THE RIGHT SHAPE ANYWAY, because the caller is the only code that
  can answer the question honestly.  SV_RecClose does fremove-then-frename and
  a FAILED rename leaves the bytes in data/parts/ under a name nobody can
  serve; only SV_TimerFinish, reading what the close actually did, knows
  whether the file it is about to name exists.  A name rebuilt here from ticks
  and tag would be right in every case except that one, and that one is
  invisible.
*/
// The gates and the form, shared by a finish and a stage post (Patch 360):
// "" when this server does not submit.
string(entity e, float track, float leg, float ticks, float flags,
       string rec, float recbytes, float rectrunc) Lobby_RunBody =
{
	local string url, key, body, guid, nm;
	local float rate;

	// Registered at the read, like every other cvar in this file, and for the
	// reason Lobby_Heartbeat gives: this can be reached before worldspawn.
	registercvar("lobby_master", "");
	registercvar("lobby_master_key", "");

	url = cvar_string("lobby_master");
	if (url == "")
		return "";                 // not pointed at a directory at all

	/*
	  NO KEY, NO REQUEST.  surfd would answer 403, so asking costs a round trip
	  per finish to be told what is already known here -- and on a listen server,
	  which runs this same progs, it would be one refused POST every time anybody
	  crossed a finish line.  This is the "Ranked = official servers only" line.
	*/
	key = cvar_string("lobby_master_key");
	if (key == "")
		return "";

	if (ticks < 1)
		return "";                 // nothing measurable happened

	/*
	  AN UNIDENTIFIED RUN IS NOT SUBMITTED.  See the header: with sv_guidkey
	  unset the engine never asks for a GUID and this is "", and the board is
	  keyed on the player -- so every anonymous run would overwrite the same
	  row and the board would show one impostor holding every time on the map.
	  Quiet, because it describes a server that is misconfigured rather than a
	  player who did anything.

	  QUIET TO THE SERVER LOG; NOT QUIET TO THE PERSON WHO JUST FINISHED.  This
	  is the gate that fires on a server which has been set up to rank -- master
	  set, key set -- and therefore on a server where the player has every
	  reason to expect their time to go up.  It fired silently, and the only
	  symptom was a leaderboard that never changed, which is the exact shape of
	  the report that started this: "it didn't write my time... I see the fake
	  times you put there, but not my time?"

	  ONCE PER CLIENT, latched on the player rather than globally: a global
	  latch would tell the first person to finish and nobody after them, on a
	  server where the fault affects everybody equally.  sprint, not a
	  centerprint -- the finish card owns the screen at this moment and a
	  message competing with it would be read as part of the result.
	*/
	guid = infokey(e, "guid");
	if (guid == "")
	{
		if (!e.lobby_said_noid)
		{
			e.lobby_said_noid = TRUE;
			sprint(e, PRINT_HIGH, "^1board:^7 this server cannot identify you, "
			         "so your times are not being submitted (sv_guidkey).\n");
		}
		return "";
	}

	nm = e.netname;
	if (nm == "")
		nm = "player";

	/*
	  HERTZ ON THE WIRE, and this is the third time the same inversion has had
	  to be written down.  pm_ticrate is SECONDS PER TICK (0.015); surfd's
	  `tickrate` is HERTZ (66.6667) because it computes millis = ticks * 1000 /
	  tickrate and ranks on the result.  Submitting 0.015 does not corrupt the
	  board -- the 1..10000 bound rejects it with a 400 -- but it would mean
	  every run from this server silently failing to store.

	  BUILD 76: THE MOVER'S RATE, NOT THE CVAR, AND THIS IS THE LINE THAT MATTERED
	  MOST IN THE WHOLE MIGRATION.

	  `ticks` on the line below used to be a count of sv.time intervals, divided
	  out by whatever run_t_tick said -- so cvar("pm_ticrate") was not merely the
	  available answer, it was the RIGHT one: the same number had produced the
	  count.  Since build 76 `ticks` is the count the MOVER produced, and the
	  mover divides by movevars.ticrate with a fallback of its own.  The two
	  should be identical and the entire reason Patch 325 publishes
	  run_movetickrate is that nothing had ever checked.  If they ever differ,
	  every millisecond surfd stores for every run from this server is out by
	  their ratio, silently, with a board that looks completely normal -- which is
	  precisely the bug build 64 shipped in the other direction, reading bhop maps
	  at a 0.015 constant when they run at 0.01.

	  So the count and its rate now leave this server from the SAME source.  The
	  cvar stays as the fallback and only as the fallback: run_movetickrate is 0
	  on an engine older than Patch 325, and a run from such a server was timed on
	  the sampled clock anyway (it carries TF_NOCLOCK, and surfd's certifiable()
	  demotes it), so the cvar is exactly the number that produced ITS ticks.
	  Each branch uses the rate that made the count it is describing.
	*/
	rate = e.run_movetickrate;
	if (rate <= 0)
		rate = cvar("pm_ticrate");
	if (rate <= 0)
		rate = PM_TICK;
	rate = 1 / rate;

	/*
	  BUILT IN THREE PIECES BECAUSE A QC CALL TAKES AT MOST EIGHT PARAMETERS.
	  Eleven fields plus the format is not expressible in one sprintf, and the
	  ninth onward would be DROPPED by the calling convention rather than
	  refused by the compiler -- a submission silently missing its flags would
	  put a tainted run on the clean board.

	  uri_escape on every free-form field for the reason the heartbeat gives:
	  a player name is arbitrary text and an unescaped & or = in it would inject
	  extra form fields into this request.  The player NAME reaches surfd from a
	  stranger, so this is the one place in the file where that is not theory.
	*/
	body = sprintf("key=%s&map=%s&track=%g&leg=%g&node=%s",
	               uri_escape(key), uri_escape(mapname), track, leg,
	               uri_escape(sprintf("p%g", cvar("sv_port"))));
	body = sprintf("%s&player=%s&name=%s",
	               body, uri_escape(guid), uri_escape(nm));
	body = sprintf("%s&ticks=%d&tickrate=%.4f&flags=%g&tier=ranked",
	               body, ticks, rate, flags);
	/*
	  A FOURTH sprintf, for the same reason there are three: the eighth
	  parameter is the last one the calling convention carries and the ninth is
	  DROPPED rather than refused.  Appending to a fourth is the cheap, boring
	  way to stay under it, and the alternative -- squeezing these onto the end
	  of the third -- would put this file one field away from silently
	  submitting runs with no flags again.

	  uri_escape on the leaf even though FS_RunLeaf can only emit [a-z0-9_.-]:
	  it is a filename, this is a form body, and the escape costs nothing.  An
	  empty `rec` is sent as an empty field rather than omitted, because
	  clean_text(None) and clean_text("") are the same "" to surfd and one
	  spelling is easier to grep for than two.

	  %d AND NOT %g, AND THIS IS NOT STYLE.  `%g` carries SIX SIGNIFICANT
	  DIGITS and then switches to exponent form, so a seven-digit byte count
	  goes out as `1.12889e+06`, which surfd's strict_int correctly refuses --
	  and a refused recbytes falls back to -1, i.e. "not stated", silently.
	  That is exactly what the first real run on a public lobby did: 1,128,886
	  bytes on disk, `bytes -1` in the ledger, no error anywhere.

	  The test could not have caught it and that is the lesson worth keeping.
	  The only finish a config can produce is a noclip flight, which is over in
	  seconds -- 38,902 bytes, FIVE digits, which `%g` prints exactly.  The
	  harness was not wrong, it was SMALLER THAN REALITY, and the boundary sat
	  between the two.  Any field here that can reach seven digits has the same
	  flaw, so `ticks` above takes %d as well: at 66.67/s it needs a 4.2-hour
	  run to reach it, but that field is the TIME, and a time that arrives as
	  `1.00000e+06` is not a time.

	  Both are floats, and %d on a float is exact to 2^24 (16.7 MB, ~43 minutes
	  of recording) and truncating beyond -- which for a size hint is fine, and
	  is a different question from the one this fixes.
	*/
	body = sprintf("%s&rec=%s&recbytes=%d&rectrunc=%g",
	               body, uri_escape(rec), recbytes, rectrunc);
	// The run's id (the .rec header's runid): joins a stage row to its run.
	if (e.rec_rec_rid != "")
		body = sprintf("%s&runid=%s", body, uri_escape(e.rec_rec_rid));
	return body;
};

// ODD, always: even ids route to the heartbeat's reply (see Lobby_RunReply).
float() Lobby_NextRunId =
{
	if (lobby_run_id < 1)
		lobby_run_id = 1;
	lobby_run_id = lobby_run_id + 2;
	return lobby_run_id;
};

void(entity e, float track, float leg, float ticks, float flags,
     string rec, float recbytes, float rectrunc) Lobby_SubmitRun =
{
	local string url, body;

	body = Lobby_RunBody(e, track, leg, ticks, flags, rec, recbytes, rectrunc);
	if (body == "")
		return;
	url = cvar_string("lobby_master");

	/*
	  ODD, ALWAYS.  Seeded to 1 in Lobby_NextRunId rather than at a registration
	  site so that the property is enforced by the only function that can break
	  it: a QC global starts at 0, and 0 + 2 is EVEN, which would route this
	  submission's reply into the heartbeat's status line and corrupt both.
	*/
	Lobby_NextRunId();

	/*
	  WHO TO ANSWER, AND ABOUT WHAT.  Recorded BEFORE the post, because
	  uri_post is asynchronous in principle and a reply that arrived before
	  these were written would find lobby_rq_id still holding the PREVIOUS
	  submission's id -- so the answer to this run would be attributed to the
	  last one, on the same player, which is the one mis-attribution this
	  design cannot detect afterwards.  It costs nothing to be in the right
	  order and the wrong order is untestable.
	*/
	e.lobby_rq_id    = lobby_run_id;
	e.lobby_rq_track = track;
	e.lobby_rq_leg   = leg;
	e.lobby_rq_ticks = ticks;
	e.lobby_rq_flags = flags;
	Lobby_RankPending(e, "*wrank", track, leg, ticks);

	lobby_run_sent = lobby_run_sent + 1;
	uri_post(strcat(url, "/api/run"), lobby_run_id,
	         "application/x-www-form-urlencoded", body);

	/*
	  ONE LINE PER SUBMISSION, ON THE SERVER CONSOLE ONLY.

	  This is the whole headless test surface for stage 3, and it has to be a
	  print rather than a console subcommand: the server's command dispatch
	  lives in SV_ParseClientCommand (sv_player.qc), which another session is
	  editing, and adding a report there would be a merge conflict in somebody
	  else's file for a line I can put in my own.

	  Proportionate rather than noisy, because every gate above has already
	  fired: an install with no directory, no key or no GUID -- which is every
	  listen server and therefore every single-player session -- has returned
	  long before here and says nothing at all.  What is left is a keyed server,
	  where a finish is a notable event and its operator wants to see that runs
	  are actually going up.  The KEY is not printed and never is; the body is
	  not printed for the same reason.
	*/
	print(sprintf("^5board:^7 submitting %s track %g leg %g -- %g ticks, flags %g\n",
	              mapname, track, leg, ticks, flags));
	/*
	  THE RECORDING ON ITS OWN LINE, and only when there is one.

	  It is the operator's proof that the run and the file on their disk are the
	  same event -- the only end-to-end check of the recorder, the naming and
	  the ledger that does not require reading the database.  A run with no
	  recording says nothing rather than printing an empty field, because
	  "submitting" already told the story and a blank value invites the reader
	  to wonder which half broke.
	*/
	if (rec != "")
		print(sprintf("^5board:^7   recording %s (%g bytes%s)\n",
		              rec, recbytes, rectrunc ? ", TRUNCATED" : ""));
};

/*
  A STAGE FROM A MAIN RUN, posted to that stage's board (Patch 360).  SV_StageClose
  decides it qualifies (primed start, at or under run_stagecap); this only posts.
  No recording leaf: a stage row has none of its own (runid joins it to the run).
  TRUE when the post went out, which is what SF_POSTED records.
*/
float(entity e, float track, float leg, float ticks, float flags) Lobby_SubmitStage =
{
	local string url, body;

	body = Lobby_RunBody(e, track, leg, ticks, flags, "", -1, 0);
	if (body == "")
		return FALSE;
	url = cvar_string("lobby_master");

	if (e.lobby_sq_id)                  // the previous stage's reply is still out
	{
		e.lobby_sq_old      = e.lobby_sq_id;
		e.lobby_sq_oldtrack = e.lobby_sq_track;
		e.lobby_sq_oldleg   = e.lobby_sq_leg;
		e.lobby_sq_oldflags = e.lobby_sq_flags;
	}
	e.lobby_sq_id    = Lobby_NextRunId();
	e.lobby_sq_track = track;
	e.lobby_sq_leg   = leg;
	e.lobby_sq_flags = flags;
	Lobby_RankPending(e, "*srank", track, leg, ticks);

	lobby_run_sent = lobby_run_sent + 1;
	uri_post(strcat(url, "/api/run"), e.lobby_sq_id,
	         "application/x-www-form-urlencoded", body);
	print(sprintf("^5board:^7 submitting %s track %g leg %g -- %g ticks, flags %g (stage)\n",
	              mapname, track, leg, ticks, flags));
	return TRUE;
};

/*
===========================================================================
  MAP ROTATION.  Patch 275.

  A lobby that never changes map is a lobby nobody comes back to, and there is
  no engine feature for this: FTE has no sv_mapcycle, no maplist, no timelimit
  that changes level.  `changelevel` from QC is the whole mechanism, and the
  only real work is deciding WHEN.

  TWO GLOBALS AND NEITHER OF THEM SURVIVES THE CHANGE, WHICH IS THE POINT.
  QW reloads the server progs on every map (PR_LoadProgs from SV_SpawnServer),
  so every global here is back at 0 on the new map and the deadline re-latches
  by itself on the first frame.  That is also why the deadline is stored as an
  absolute time rather than a countdown: `time` restarts at 0 too, so a
  countdown carried across would have been meaningless, and an absolute
  deadline carried across would have fired instantly.  Neither happens, but
  only because nothing is carried across at all -- so do not "optimise" this
  by making either global persist.

  RCON STILL WORKS AND IS NOT AFFECTED.  `changelevel surf_x` typed at the
  console or over rcon goes wherever it is told; the rotation just picks up
  from wherever that landed, because Lobby_NextMap searches for the CURRENT
  map in the list rather than keeping an index.  An index would have gone out
  of sync with reality the first time an admin moved the server by hand, and
  would then have jumped somewhere unrelated at the next expiry.
===========================================================================
*/
float  lobby_cyc_next;          // absolute deadline; 0 = not latched this map
float  lobby_cyc_warn;          // 0 none given, 1 the minute, 2 the ten seconds
// WP11, the rotation hold.  All zeroed by the map change, which is what caps it:
// players taking turns cannot restart lobby_cyc_hold0.
float  lobby_cyc_runseen;       // last time a run was in progress (sv_resume.qc writes it)
float  lobby_cyc_hold0;         // when the hold began; 0 = not holding
float  lobby_cyc_holdwarn;      // the minute-to-cap warning is out
float  lobby_cyc_holdend;       // the runs ended inside the hold: ten seconds given
float  lobby_cyc_moving;        // the rotation's own changelevel: parks say `rotate`

/*
  The map after this one.

  Returns "" for "do not rotate", which covers three separate cases on
  purpose: no list, a list of one (rotating to yourself is a reload, not a
  rotation, and it would kick everyone off the map they are already on for
  nothing), and a list whose entries are all the current map.

  A current map that is NOT in the list returns the first entry rather than
  "".  That is the rcon case above: an admin moves the server somewhere off
  the rotation, and the rotation should resume at the top rather than give up
  silently and leave the lobby parked there forever.
*/
string() Lobby_NextMap =
{
	local float n, i, j;

	n = tokenize(cvar_string("lobby_maps"));
	if (n < 2)
		return "";

	for (i = 0; i < n; i = i + 1)
	{
		if (argv(i) != mapname)
			continue;

		j = i + 1;
		if (j >= n)
			j = 0;
		if (argv(j) == mapname)
			return "";          // a list that is all one map
		return argv(j);
	}

	if (argv(0) == mapname)
		return "";
	return argv(0);
};

void() Lobby_Cycle =
{
	local float  per, left, hold;
	local string nxt;

	// Registered beside the read, for the reason spelled out at length in
	// Lobby_Frame: this runs on a StartFrame that precedes worldspawn, so a
	// registration anywhere else is declined and the default never lands.
	registercvar("lobby_maps",  "");
	registercvar("lobby_cycle", "0");
	registercvar("lobby_cycle_hold", "7200");

	per = cvar("lobby_cycle");
	if (per <= 0)
	{
		/*
		  Off.  Clearing the deadline rather than just returning means switching
		  the cycle ON mid-map gives a full period from that moment, instead of
		  inheriting a deadline latched before anyone thought about it.
		*/
		lobby_cyc_next = 0;
		return;
	}

	/*
	  Floored at 60 seconds.  Not a safety rail against a hostile value -- this
	  cvar is set by whoever runs the server -- but against a plausible typo:
	  `lobby_cycle 30` reads as "thirty minutes" to anyone who has just read the
	  documentation for it, and thirty SECONDS would changelevel the server out
	  from under a run before the run got to the second stage.  A minute is the
	  shortest value that is still a rotation rather than a fault.
	*/
	if (per < 60)
		per = 60;

	if (!lobby_cyc_next)
	{
		lobby_cyc_next = time + per;
		lobby_cyc_warn = 0;
		return;
	}

	/*
	  A SHORTENED PERIOD APPLIES NOW, not after the outstanding one expires.

	  Without this, `lobby_cycle 60` typed over rcon on a server that started at
	  1800 does nothing at all for up to half an hour and then starts working,
	  which is indistinguishable from the feature being broken -- and it is
	  exactly what an admin types when they want the map to move along.  It is
	  also what makes this testable at all: a rotation whose shortest observable
	  period is the one it was launched with can only be falsified by waiting
	  out a full cycle.

	  Only ever pulls the deadline IN.  Raising the cvar mid-map leaves the
	  earlier deadline standing, because extending a period someone is already
	  most of the way through would mean the map they were told was ending in a
	  minute silently is not.
	*/
	if (lobby_cyc_next > time + per)
		lobby_cyc_next = time + per;

	left = lobby_cyc_next - time;

	if (left > 0)
	{
		lobby_cyc_moving = FALSE;       // a change that did not happen is not moving
		/*
		  Two warnings, and only when somebody is listening.  An empty lobby
		  rotates in silence -- there is no one to warn, and the log line every
		  half hour on an idle server is noise that makes the real ones harder
		  to find.

		  Sixty seconds is enough to finish a stage; ten is enough to stop
		  starting one.  Both are printed with the destination, because "the map
		  is changing" without saying to what is the thing that makes people
		  leave rather than wait.
		*/
		if (left <= 60 && lobby_cyc_warn < 1)
		{
			lobby_cyc_warn = 1;
			nxt = Lobby_NextMap();
			if (nxt != "" && Lobby_PlayerCount() > 0)
				bprint(PRINT_HIGH, sprintf("^3lobby:^7 %s in one minute\n", nxt));
		}
		if (left <= 10 && lobby_cyc_warn < 2)
		{
			lobby_cyc_warn = 2;
			nxt = Lobby_NextMap();
			if (nxt != "" && Lobby_PlayerCount() > 0)
				bprint(PRINT_HIGH, sprintf("^3lobby:^7 %s in ten seconds\n", nxt));
		}
		return;
	}

	/*
	  Re-arm BEFORE the changelevel, not after.

	  On a successful change none of this matters -- the progs reload and every
	  global here is zeroed anyway.  It matters when the change does NOT happen:
	  a map that is not installed on this server leaves `changelevel` printing
	  an error and the server exactly where it was, and without a fresh deadline
	  this function would then retry on every single frame, at 66 Hz, forever.
	  One failed rotation should cost one log line per period, not a flood.
	*/
	/*
	  WP11: THE DEADLINE WAITS FOR RUNS IN PROGRESS, for at most
	  lobby_cycle_hold seconds (0 = the old behaviour).  At the cap the change
	  goes ahead and SV_Shutdown parks every run still going (Multi-Session,
	  `rotate`): !resume back on this map continues them.  Runs that end inside
	  the hold get the usual ten seconds, once.
	*/
	hold = cvar("lobby_cycle_hold");
	nxt = Lobby_NextMap();
	if (hold > 0)
	if (nxt != "")
	{
		if (time - lobby_cyc_runseen < 2)
		{
			if (!lobby_cyc_hold0)
			{
				lobby_cyc_hold0 = time;
				bprint(PRINT_HIGH, sprintf("^3lobby:^7 %s waits for the runs in progress "
				       "(at most %g min)\n", nxt, ceil(hold / 60)));
			}
			if (time - lobby_cyc_hold0 < hold)
			{
				if (!lobby_cyc_holdwarn)
				if (time - lobby_cyc_hold0 >= hold - 60)
				{
					lobby_cyc_holdwarn = TRUE;
					bprint(PRINT_HIGH, sprintf("^3lobby:^7 %s in one minute -- runs still "
					       "going are paused; !resume on %s continues them\n", nxt, mapname));
				}
				return;
			}
		}
		else if (lobby_cyc_hold0)
		if (!lobby_cyc_holdend)
		{
			lobby_cyc_holdend = TRUE;
			lobby_cyc_next = time + 10;
			lobby_cyc_warn = 2;
			bprint(PRINT_HIGH, sprintf("^3lobby:^7 %s in ten seconds\n", nxt));
			return;
		}
	}

	lobby_cyc_next = time + per;
	lobby_cyc_warn = 0;

	if (nxt == "")
		return;

	lobby_cyc_moving = TRUE;
	localcmd(sprintf("changelevel %s\n", nxt));
};

void(entity p) Lobby_ClientConnect =
{

	// Fresh connection on a possibly-recycled edict: whatever colour the
	// previous occupant of this slot had is not this player's.  Cleared here
	// rather than in Lobby_AvatarSpawn because it must happen even when
	// avatars are off, or turning them on later inherits a stale index.
	p.lobby_colour = 0;

	/*
	  PATCH 340: THE PLAYER HASH, published to its owner once per connection.

	  FS_GuidId is the same 8 hex chars the run filenames carry (SV_RecWho ->
	  FS_PlayerSeg), so the string on the customizer panel and the string in
	  data/runs are ONE spelling from ONE function.  It survives renames
	  because the guid does -- that is the whole ask: records follow the
	  hash, not the name.  "" on a server with no sv_guidkey, which the panel
	  renders as "no id" rather than an empty hex box.

	  THROUGH forceinfokey AND NOT A STUFFED `set`, and the first cut got this
	  wrong the interesting way: a server-stuffed set is Cvar_LockFromServer
	  (cvar.c:1466), which takes control of the cvar and LATCHES the client's
	  previous value -- and PF_cvar_string returns the LATCHED string to QC
	  (pr_bgcmd.c:1975), so the panel read "" forever while the console
	  cheerfully printed the hash as the "effective value".  The star-key
	  route is the tree's established server->client string channel (*wrank,
	  read back in cl_results.qc with getplayerkeyvalue) and has no latch in
	  it anywhere.
	*/
	forceinfokey(p, "*phash", FS_GuidId(infokey(p, "guid")));

	// The colour mirror re-sends on the next 1 Hz pass, whichever colour the
	// re-roll lands on; 0 is not a palette index, so the compare always fires.
	p.lobby_csent = 0;

	if (cvar("lobby_enable") && cvar("lobby_avatars"))
		Lobby_AvatarSpawn(p);
};

void(entity p) Lobby_ClientDisconnect =
{
	Lobby_AvatarFree(p);

	/*
	  Release the colour.

	  Load-bearing, not tidiness.  Lobby_ColourTaken walks entities whose
	  classname is still "player", and a disconnected client's edict is not
	  freed -- it is kept and recycled (sv_main.c:2516-2522).  Leave the index
	  set and a departed player goes on holding their colour against everybody
	  still here, so the palette shrinks by one per person who ever leaves.
	*/
	p.lobby_colour = 0;
};
