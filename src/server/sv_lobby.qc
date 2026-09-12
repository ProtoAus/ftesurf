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
  cfg/lobby.cfg carries the same note beside the rate.

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
*/
.entity  lobby_av;
.entity  lobby_owner;
.float   lobby_next;
.string  lobby_model;
.float   lobby_colour;
.float   lobby_fx;

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

  lobby_shuffle is the per-map rotation of the palette: the slot index picks
  the colour, so without it slot 1 would be red on every map forever.  Latched
  ONCE, on the first frame, rather than seeded in worldspawn -- Lobby_Frame
  runs on a StartFrame that PRECEDES PR_SpawnInitialEntities (sv_init.c:1657 vs
  :1686), so worldspawn is too late to be read from here.  Progs are reloaded
  on a map change, so the latch clears itself and the rotation really is per
  map.

  lobby_colcheck paces the userinfo re-read.  A player can retype
  `setinfo lobbycolor` at any time and there is no userinfo-change callback in
  SSQC, so the only way to notice is to look; 1 Hz is far below the cost of
  caring and far above the latency anyone will perceive.
*/
float lobby_shuffle;
float lobby_shuffled;
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

  Their own pick wins if they made one and it is free; otherwise the slot picks,
  rotated by the per-map shuffle, and steps forward past anything taken.

  The slot is num_for_edict - 1, which is stable for a connection and is
  RECYCLED to the next joiner when someone leaves (sv_main.c:2516-2522).  That
  recycling is the right behaviour here and not a bug to work around: a colour
  freed by a departure should be available again.

  `setinfo lobbycolor <n>` is how a player picks.  infokey is real in SSQC in
  this engine -- PF_infokey_s, builtin 80 (pr_cmds.c:11437), not PF_Fixme --
  and userinfo archives itself into the client's config the same way name and
  topcolor already do, so the choice survives a restart with no work from us.
  0 or empty means "you choose".
*/
float(entity p) Lobby_ColourFor =
{
	local float idx, n, tries;
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
	  Otherwise the slot picks, strided and rotated.

	  STRIDE 5, not 1.  The palette is in hue order, so consecutive slots taking
	  consecutive entries would hand two people who join together red and
	  orange.  5 is coprime with 12, so multiplying by it is a permutation --
	  every colour is still reachable and none is reachable twice -- and it
	  moves 150 degrees around the hue circle per slot, which is about as far
	  apart as adjacent joiners can be put.

	  Written as a subtraction rather than with `%` because QC's modulo is not
	  something to rely on across compilers.
	*/
	n = (num_for_edict(p) - 1) * 5 + lobby_shuffle;
	n = n - floor(n / FS_AVCOLOURS) * FS_AVCOLOURS;
	idx = n + 1;

	// Step past anyone already using it.  Bounded by the palette size, so a
	// full lobby simply wraps and shares rather than spinning.
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

	av.colormod = Lobby_ColourMod(p.lobby_colour);
};

/*
===========================================================================
  PER-PLAYER EFFECTS.

  OPT-IN, PER CLIENT, with `setinfo lobbyfx <mask>`:  1 trail, 2 motes.
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
	local float m;

	m = p.lobby_fx;

	// Assigned unconditionally rather than only on change: the delta
	// compressor compares the packed values and only flags the bit when they
	// actually differ, so writing the same number costs nothing.
	if (m & FS_AVFX_TRAIL)
		av.traileffectnum = particleeffectnum(sprintf("ftesurf_avtrail_%g", p.lobby_colour));
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
		av.glowmod = Lobby_GlowMod(p.lobby_colour);
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

void() Lobby_Frame =
{
	local entity av, nx, p;
	local float  nfx, want;

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
	  cfg/lobby.cfg spawned NO AVATARS AT ALL.  Lobby_Resync takes its else
	  branch and removes them, Lobby_Frame returns before the pose loop, and
	  Lobby_ClientConnect's own test refuses too -- so 32 people share a map and
	  see nobody, with nothing printed.  It only ever worked because
	  cfg/lobby.cfg `set`s the value before the map loads, which is exactly the
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
	  Latch the palette rotation.  First frame only, and it has to be here
	  rather than in worldspawn for the same reason the registercvar calls
	  above are here: this function runs before worldspawn exists.
	*/
	if (!lobby_shuffled)
	{
		lobby_shuffled = TRUE;
		lobby_shuffle  = floor(random() * FS_AVCOLOURS);
	}

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
void(float code, string body) Lobby_RunReply;

void(float reqid, float responsecode, string resourcebody) URI_Get_Callback =
{
	// Odd ids are run submissions; see the parity note above.
	if (reqid & 1)
	{
		Lobby_RunReply(responsecode, resourcebody);
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
void(entity e, float track, float leg, float ticks, float flags) Lobby_SubmitRun;

void() Lobby_Heartbeat =
{
	local string url, body;
	local float  per;
	local entity pl;

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
			cvar_set("lobby_run_probe", "0");
			lobby_run_waiting = FALSE;
			print("^5board:^7 probe -- one synthetic CHEATED run, which has no "
			      "board and cannot rank\n");
			Lobby_SubmitRun(pl, 0, 0, 1234, TF_CHEAT);
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
void(float code, string body) Lobby_RunReply =
{
	if (!code)
		lobby_run_ok = lobby_run_ok + 1;

	if (lobby_run_seen && code == lobby_run_lastcode)
		return;
	lobby_run_seen     = TRUE;
	lobby_run_lastcode = code;

	if (!code)
		print("^2board:^7 directory stored a run\n");
	else if (code == 204)
		print("^3board:^7 run has no board (practice or cheated) -- not an error\n");
	else if (code == 403)
		print("^1board:^7 directory refused the key -- this server cannot rank runs\n");
	else
		print(sprintf("^1board:^7 directory returned %g (%s)\n", code, body));
};

void(entity e, float track, float leg, float ticks, float flags) Lobby_SubmitRun =
{
	local string url, key, body, guid, nm;
	local float rate;

	// Registered at the read, like every other cvar in this file, and for the
	// reason Lobby_Heartbeat gives: this can be reached before worldspawn.
	registercvar("lobby_master", "");
	registercvar("lobby_master_key", "");

	url = cvar_string("lobby_master");
	if (url == "")
		return;                 // not pointed at a directory at all

	/*
	  NO KEY, NO REQUEST.  surfd would answer 403, so asking costs a round trip
	  per finish to be told what is already known here -- and on a listen server,
	  which runs this same progs, it would be one refused POST every time anybody
	  crossed a finish line.  This is the "Ranked = official servers only" line.
	*/
	key = cvar_string("lobby_master_key");
	if (key == "")
		return;

	if (ticks < 1)
		return;                 // nothing measurable happened

	/*
	  AN UNIDENTIFIED RUN IS NOT SUBMITTED.  See the header: with sv_guidkey
	  unset the engine never asks for a GUID and this is "", and the board is
	  keyed on the player -- so every anonymous run would overwrite the same
	  row and the board would show one impostor holding every time on the map.
	  Quiet, because it describes a server that is misconfigured rather than a
	  player who did anything.
	*/
	guid = infokey(e, "guid");
	if (guid == "")
		return;

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
	*/
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
	body = sprintf("%s&ticks=%g&tickrate=%.4f&flags=%g&tier=ranked",
	               body, ticks, rate, flags);

	/*
	  ODD, ALWAYS.  Seeded to 1 here rather than at a registration site so that
	  the property is enforced by the only function that can break it: a QC
	  global starts at 0, and 0 + 2 is EVEN, which would route this submission's
	  reply into the heartbeat's status line and corrupt both.
	*/
	if (lobby_run_id < 1)
		lobby_run_id = 1;
	lobby_run_id = lobby_run_id + 2;

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
	local float  per, left;
	local string nxt;

	// Registered beside the read, for the reason spelled out at length in
	// Lobby_Frame: this runs on a StartFrame that precedes worldspawn, so a
	// registration anywhere else is declined and the default never lands.
	registercvar("lobby_maps",  "");
	registercvar("lobby_cycle", "0");

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
	lobby_cyc_next = time + per;
	lobby_cyc_warn = 0;

	nxt = Lobby_NextMap();
	if (nxt == "")
		return;

	localcmd(sprintf("changelevel %s\n", nxt));
};

void(entity p) Lobby_ClientConnect =
{
	// Fresh connection on a possibly-recycled edict: whatever colour the
	// previous occupant of this slot had is not this player's.  Cleared here
	// rather than in Lobby_AvatarSpawn because it must happen even when
	// avatars are off, or turning them on later inherits a stale index.
	p.lobby_colour = 0;

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
