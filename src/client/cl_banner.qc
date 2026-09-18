/*
===========================================================================
  cl_banner.qc -- the completion banner.  Patch 361.

  A full-width angled ribbon when a leg ends (MAP / STAGE k / BONUS t
  COMPLETE): the time, the delta to the PB, the placement.  A compact strip for
  a stage passed during a main run; on the finish frame the last stage rides
  under the ribbon as a tail.  The placement is re-read every frame from the
  server's `*wrank` / `*srank` (Results_KeyRank), so a late answer lands in
  place.  Own FINREC / STAGEENDREC latches -- the card and the toast keep theirs.
===========================================================================
*/
#define BN_NONE     0
#define BN_FULL     1
#define BN_STAGE    2

#define BN_TIN      0.25        // full: slide in
#define BN_TOUT     0.22        //       slide out
#define BN_CTIN     0.18        // compact: fade in
#define BN_CTOUT    0.20
#define BN_CHOLD    0.7         // compact hold, a fraction of hud_banner_hold
#define BN_MINAGE   1.2         // a new attempt ends a full banner no sooner than this
#define BN_GRACE    1.0         // the key of a submitted run can trail the finish
#define BN_PENDMAX  2.0         // the longest a hold waits for an answer
#define BN_REPLYMIN 1.5         // a late answer stays up at least this long

#define BNC_BAND     '0.06 0.07 0.10'
#define BNC_WR       '1.00 0.84 0.30'
#define BNC_TOP      '0.55 0.85 1.00'
#define BNC_UNRANKED '1.00 0.66 0.30'

string ui_bn_map;
float  ui_bn_kind;              // BN_*
float  ui_bn_at;                // cltime raised
float  ui_bn_outat;             // cltime the exit began; 0 = holding
float  ui_bn_exit;              // yield: leave no later than this; 0 = none
float  ui_bn_replyat;           // cltime the answer landed; 0 = not yet
float  ui_bn_test;              // raised by `banner test|stage`
float  ui_bn_wrsaid;

// The subject.  flags are TF_* (a stage's from its word, like LT_Keep's).
float  ui_bn_track, ui_bn_leg, ui_bn_ticks, ui_bn_flags, ui_bn_word, ui_bn_pb;
float  ui_bn_mine, ui_bn_slot, ui_bn_sub, ui_bn_lrank, ui_bn_lof;
// The last stage of a main run, drawn under the ribbon.  tailleg -1 = none.
float  ui_bn_tailleg, ui_bn_tailticks, ui_bn_tailword, ui_bn_tailpb;
float  ui_bn_taillrank, ui_bn_taillof;
// Where each PB came from (Bn_PBOf: 1 server, 2 lobby files, 0 none), and whether
// the server kept the stage as a record (the STAGEREC edge in its close frame).
float  ui_bn_pbsrc, ui_bn_kept, ui_bn_tailpbsrc, ui_bn_tailkept;
float  ui_bn_lastsrec, ui_bn_sndowed, ui_bn_pbsrcnow;

float  ui_bn_lastfin, ui_bn_lastend, ui_bn_laststate, ui_bn_lastent;
string ui_bn_fake;              // `banner fake`: a key read by test banners only

// Sound files present on this map (probed at map init; `banner probe` again).
float  ui_bn_sndok_end, ui_bn_sndok_pb, ui_bn_sndok_wr;

// What Bn_Place / Bn_Delta decided, for one draw (tempstrings: this frame only).
string ui_bn_pl1, ui_bn_pl2, ui_bn_dl;
vector ui_bn_plc, ui_bn_pl2c, ui_bn_dlc, ui_bn_placc;
float  ui_bn_newpb;
float  ui_bn_drawu;             // the unit the last full draw fitted to (`banner` prints it)

void() Banner_RegisterCvars =
{
	registercvar("hud_banner", "1", CVAR_ARCHIVE);
	registercvar("hud_banner_stages", "1", CVAR_ARCHIVE);  // 0: the one-line toast instead
	registercvar("hud_banner_hold", "3.5", CVAR_ARCHIVE);
	registercvar("hud_banner_x", "0.5", CVAR_ARCHIVE);
	registercvar("hud_banner_y", "0.25", CVAR_ARCHIVE);
	registercvar("hud_banner_size", "0", CVAR_ARCHIVE);    // 0 = 32 * hud_scale
	registercvar("hud_banner_sound", "1", CVAR_ARCHIVE);
	// The mod's own files -- none ship yet; a missing one is skipped silently.
	registercvar("hud_banner_snd_end", "sound/ftesurf/complete.wav", CVAR_ARCHIVE);
	registercvar("hud_banner_snd_pb", "sound/ftesurf/pb.wav", CVAR_ARCHIVE);
	registercvar("hud_banner_snd_wr", "sound/ftesurf/wr.wav", CVAR_ARCHIVE);
	registercommand("banner");      // free: grepped the engine and plugins
	ui_bn_lastfin = -1;             // the first value seen is not an event
	ui_bn_lastend = -1;
	ui_bn_lastsrec = -1;
	ui_bn_tailleg = -1;
};

// ---- sound -----------------------------------------------------------------

// A cvar's value as a path under the gamedir ("sound/..."), and as the name
// localsound wants (relative to sound/).
string(string v) Bn_SndPath =
{
	if (substring(v, 0, 6) == "sound/")
		return v;
	return strcat("sound/", v);
};

float(string cv) Bn_SndProbe =
{
	local float h, n;
	local string p;

	if (cvar_string(cv) == "")
		return FALSE;
	p = Bn_SndPath(cvar_string(cv));
	h = search_begin(p, TRUE, TRUE);
	if (h < 0)
		return FALSE;
	n = search_getsize(h);
	search_end(h);
	if (n <= 0)
		return FALSE;
	precache_sound(substring(p, 6, -1));
	return TRUE;
};

void() Bn_SndProbeAll =
{
	ui_bn_sndok_end = Bn_SndProbe("hud_banner_snd_end");
	ui_bn_sndok_pb  = Bn_SndProbe("hud_banner_snd_pb");
	ui_bn_sndok_wr  = Bn_SndProbe("hud_banner_snd_wr");
};

// 0 end, 1 pb, 2 wr.  A file that was not there at the probe plays nothing.
void(float which) Bn_Sound =
{
	local string cv;

	if (!cvar("hud_banner") || !cvar("hud_banner_sound"))
		return;
	cv = "hud_banner_snd_end";
	if (which == 1)
	{
		if (!ui_bn_sndok_pb)
			return;
		cv = "hud_banner_snd_pb";
	}
	else if (which == 2)
	{
		if (!ui_bn_sndok_wr)
			return;
		cv = "hud_banner_snd_wr";
	}
	else if (!ui_bn_sndok_end)
		return;
	localsound(substring(Bn_SndPath(cvar_string(cv)), 6, -1));
};

// ---- words -----------------------------------------------------------------

// Never "WR" for a local placement; the r/o guard keeps #10 of 11 off TOP 10.
string(float r, float o, float loc) Bn_TierWord =
{
	local float p;

	if (r < 1 || o < 1)
		return "";
	if (r == 1)
	{
		if (loc)
			return "";
		return "WR";
	}
	p = r / o;
	if (r <= 10 && p <= 0.5)
		return "TOP 10";
	if (p <= 0.10)
		return "TOP 10%";
	if (p <= 0.25)
		return "TOP 25%";
	if (p <= 0.50)
		return "TOP 50%";
	return "";
};

string(float track, float leg) Bn_LegLabel =
{
	if (track <= 0)
	{
		if (leg <= 0)
			return "MAP";
		return sprintf("STAGE %g", leg);
	}
	if (leg <= 0)
		return sprintf("BONUS %g", track);
	return sprintf("BONUS %g STAGE %g", track, leg);
};

// The key for the subject (tail: the last stage's).  A faked key reaches only
// a test banner's own subject -- never the card, never a real banner.
string(float tail) Bn_Raw =
{
	if (!tail && ui_bn_test && ui_bn_fake != "")
		return ui_bn_fake;
	if (tail || ui_bn_kind == BN_STAGE)
		return getplayerkeyvalue(ui_bn_slot, "*srank");
	return getplayerkeyvalue(ui_bn_slot, "*wrank");
};

// The board's answer for the subject, into ui_bn_ans*.  A stage close that was
// not posted has no answer of its own -- a matching key is an older post's.
float  ui_bn_ansr, ui_bn_anso, ui_bn_anstier, ui_bn_ansstored;

float(float tail) Bn_Answer =
{
	local float leg, ticks, r, o, tier, stored, st;

	ui_bn_ansr = ui_bn_anso = ui_bn_anstier = 0;
	ui_bn_ansstored = -1;
	leg   = ui_bn_leg;
	ticks = ui_bn_ticks;
	if (tail)
	{
		leg   = ui_bn_tailleg;
		ticks = ui_bn_tailticks;
		if (!(ui_bn_tailword & SF_POSTED))
			return WR_NONE;
	}
	else if (ui_bn_kind == BN_STAGE && !ui_bn_sub && !ui_bn_test)
		return WR_NONE;

	r = o = tier = stored = 0;
	st = Results_KeyRank(Bn_Raw(tail), ui_bn_track, leg, ticks, r, o, tier, stored);
	ui_bn_ansr = r;
	ui_bn_anso = o;
	ui_bn_anstier = tier;
	ui_bn_ansstored = stored;
	return st;
};

// The placement lines.  The class comes first: a run that is not timed for
// the board says so, and another player's is never accused (NOT TIMED).
void(float tail) Bn_PlaceRaw =
{
	local float flags, sub, lr, lo, cls, st, r, o, stored;
	local string w;

	if (tail)
	{
		flags = LT_StageFlags(ui_bn_tailword) | (ui_bn_flags & TF_UNCERT);
		sub   = (ui_bn_tailword & SF_POSTED) != 0;
		lr    = ui_bn_taillrank;
		lo    = ui_bn_taillof;
	}
	else
	{
		flags = ui_bn_flags;
		sub   = ui_bn_sub;
		lr    = ui_bn_lrank;
		lo    = ui_bn_lof;
	}

	cls = FS_RunClass(flags);
	if (flags & TF_SHADOW)
	{
		ui_bn_pl1 = "SHADOW";
		ui_bn_pl2 = "from a save";
		ui_bn_plc = TC_SHADOW;
		ui_bn_placc = TC_SHADOW;
		return;
	}
	if (cls == RC_CHEAT || cls == RC_PRACTICE)
	{
		if (!ui_bn_mine)
		{
			ui_bn_pl1 = "NOT TIMED";
			ui_bn_plc = RSC_DIM;
			return;
		}
		ui_bn_pl2 = "not saved";
		if (cls == RC_CHEAT)
		{
			ui_bn_pl1 = "CHEATED";
			ui_bn_plc = TC_CHEAT;
			ui_bn_placc = TC_CHEAT;
		}
		else
		{
			ui_bn_pl1 = "PRACTICE";
			ui_bn_plc = TC_PRACTICE;
			ui_bn_placc = TC_PRACTICE;
		}
		return;
	}

	st = Bn_Answer(tail);
	r = ui_bn_ansr;
	o = ui_bn_anso;
	stored = ui_bn_ansstored;
	if (st == WR_PENDING || (st == WR_NONE && sub && cltime - ui_bn_at < BN_GRACE))
	{
		ui_bn_pl1 = "...";
		ui_bn_pl2 = "asking the leaderboard";
		ui_bn_plc = RSC_DIM;
		return;
	}
	if (st == WR_UNRANKED)
	{
		ui_bn_pl1 = "UNRANKED";
		ui_bn_pl2 = FS_CertWhy(flags);
		if (ui_bn_pl2 == "")
			ui_bn_pl2 = "not certified";
		ui_bn_plc = BNC_UNRANKED;
		ui_bn_pl2c = BNC_UNRANKED;
		ui_bn_placc = BNC_UNRANKED;
		return;
	}
	if (st == WR_RANKED && r > 0)
	{
		ui_bn_pl1 = sprintf("#%g of %g", r, o);
		w = Bn_TierWord(r, o, FALSE);
		// Gold and "WR" only when this run IS the row: a slower run by the
		// holder is answered with the standing row's rank.
		if (r == 1 && stored != 1)
			w = "";
		if (w == "WR")
		{
			ui_bn_plc = BNC_WR;
			ui_bn_pl2c = BNC_WR;
			ui_bn_placc = BNC_WR;
		}
		else if (w == "TOP 10" || w == "TOP 10%")
			ui_bn_pl2c = BNC_TOP;
		else
			ui_bn_pl2c = RSC_TEXT;
		if (stored == 0)
		{
			if (w != "")
				w = strcat(w, "  ");
			w = strcat(w, "PB STANDS");
		}
		ui_bn_pl2 = w;
		return;
	}
	if (st == WR_STORED)
	{
		ui_bn_pl1 = "ON THE BOARD";
		ui_bn_pl2 = "no rank given";
		return;
	}
	if (st == WR_FAILED)
	{
		// Refused or not reached (any non-204 code): the card's words.
		ui_bn_pl1 = "NOT ON THE BOARD";
		ui_bn_pl2 = "the board did not take it";
		ui_bn_plc = RSC_DIM;
		return;
	}
	// No board answered: this disk's placement, never called WR, and only for
	// the class that disk's field is made of.
	if (ui_bn_mine && lr > 0 && cls == RC_CLEAN)
	{
		ui_bn_pl1 = sprintf("#%g of %g", lr, lo);
		w = Bn_TierWord(lr, lo, TRUE);
		ui_bn_pl2 = "LOCAL";
		if (w != "")
			ui_bn_pl2 = strcat("LOCAL  ", w);
	}
};

void(float tail) Bn_Place =
{
	local float flags;

	ui_bn_pl1 = "";
	ui_bn_pl2 = "";
	ui_bn_plc = RSC_TEXT;
	ui_bn_pl2c = RSC_DIM;
	ui_bn_placc = RSC_LINE;
	Bn_PlaceRaw(tail);

	flags = ui_bn_flags;
	if (tail)
		flags = LT_StageFlags(ui_bn_tailword);
	if (FS_RunClass(flags) == RC_SEGMENT)
	if (!(flags & TF_SHADOW))
		ui_bn_pl2 = strcat("SEGMENTED  ", ui_bn_pl2);
};

// The delta to the PB.  A claim (NEW PB / FIRST TIME) only where the run was
// kept as one: the clean class, a PB source (pbsrc 1 the server's table, 2 this
// disk's lobby files, 0 none), for a stage SF_QUALIFIES and -- on the server's
// table -- the stage-record edge (kept: rec_enable 0 keeps nothing); never
// beside a board answer that says the standing PB is at least as fast.
void(float tail) Bn_Delta =
{
	local float ticks, pb, flags, word, cls, tick, clean, claim, src, kept, st;

	ui_bn_dl = "";
	ui_bn_dlc = RSC_DIM;
	ui_bn_newpb = FALSE;
	if (tail)
	{
		ticks = ui_bn_tailticks;
		pb    = ui_bn_tailpb;
		word  = ui_bn_tailword;
		flags = LT_StageFlags(word);
		src   = ui_bn_tailpbsrc;
		kept  = ui_bn_tailkept;
	}
	else
	{
		ticks = ui_bn_ticks;
		pb    = ui_bn_pb;
		word  = ui_bn_word;
		flags = ui_bn_flags;
		src   = ui_bn_pbsrc;
		kept  = ui_bn_kept;
	}
	tick = Timer_Tick();
	cls = FS_RunClass(flags);
	if (cls == RC_CHEAT || src == 0)
		return;
	clean = (cls == RC_CLEAN);
	if (tail || ui_bn_kind == BN_STAGE)
	if (!(word & SF_QUALIFIES))
		clean = FALSE;
	claim = clean;
	if (tail || ui_bn_kind == BN_STAGE)
	if (src == 1 && !kept)
		claim = FALSE;
	st = Bn_Answer(tail);
	if (st == WR_RANKED || st == WR_STORED)
	if (ui_bn_ansstored == 0)
		claim = FALSE;

	if (!ui_bn_mine || !clean)
	{
		if (pb > 0)
		{
			ui_bn_dl = Time_DeltaString(ticks - pb, tick);
			if (!clean)
				ui_bn_dlc = RSC_DIM;
			else if (ticks <= pb)
				ui_bn_dlc = TC_AHEAD;
			else
				ui_bn_dlc = TC_BEHIND;
		}
		return;
	}
	if (pb <= 0)
	{
		if (claim)
		{
			ui_bn_dl = "FIRST TIME";
			ui_bn_dlc = TC_AHEAD;
			ui_bn_newpb = TRUE;
		}
		return;
	}
	ui_bn_dl = Time_DeltaString(ticks - pb, tick);
	ui_bn_dlc = TC_BEHIND;
	if (ticks <= pb)
		ui_bn_dlc = TC_AHEAD;
	if (ticks == pb)
		ui_bn_dl = strcat(ui_bn_dl, "  TIED");          // a statement, not a claim
	else if (ticks < pb && claim)
	{
		ui_bn_dl = strcat(ui_bn_dl, "  NEW PB");
		ui_bn_newpb = TRUE;
	}
};

// The accent: the taint, the WR, a new best, unranked, the house line.
vector() Bn_Accent =
{
	if (ui_bn_placc != RSC_LINE)
		return ui_bn_placc;
	if (ui_bn_newpb)
		return TC_AHEAD;
	return RSC_LINE;
};

vector() Bn_HeroColor =
{
	local float cls;

	cls = FS_RunClass(ui_bn_flags);
	if (ui_bn_flags & TF_SHADOW)
		return TC_SHADOW;
	if (cls == RC_CHEAT)
		return TC_CHEAT;
	if (cls != RC_CLEAN)
		return TC_PRACTICE;
	if (ui_bn_pb > 0 && ui_bn_ticks > ui_bn_pb)
		return TC_BEHIND;
	if (!ui_bn_mine && ui_bn_pb <= 0)
		return RSC_TEXT;
	return TC_AHEAD;
};

// ---- raising ---------------------------------------------------------------

void() Bn_Begin =
{
	ui_bn_at      = cltime;
	ui_bn_outat   = 0;
	ui_bn_exit    = 0;
	ui_bn_replyat = 0;
	ui_bn_wrsaid  = FALSE;
	ui_bn_sndowed = FALSE;
	ui_bn_tailleg = -1;
};

// Whose stats these are: the server says (STAT_FS_STATOWNER); an older one does
// not, and then the view entity is the guess.
float() Bn_Owner =
{
	local float o;

	o = getstatf(STAT_FS_STATOWNER);
	if (o > 0)
		return o;
	return player_localentnum;
};

void() Bn_Subject =
{
	ui_bn_mine = LT_StatsAreMine();
	ui_bn_slot = Bn_Owner() - 1;            // the player the stats describe
};

// The PB a run is measured against; its source in ui_bn_pbsrcnow: 1 the server's
// table (`server`), 2 this disk's lobby files where the server keeps none and
// this disk does (LT_Keeps), 0 none.  `mine` 0 to LT_BestOnLegC: this run's file
// is not written yet (LT_Frame runs after us), so a tie still counts as one.
float(float track, float leg, float flags, float server) Bn_PBOf =
{
	ui_bn_pbsrcnow = 1;
	if (!(getstatf(STAT_FS_LOBBY) & LS_NOPB))
		return server;
	ui_bn_pbsrcnow = 0;
	if (!ui_bn_mine || !LT_Keeps())
		return 0;
	ui_bn_pbsrcnow = 2;
	return LT_BestOnLegC(serverkey("map"), track, leg, 0, (flags & TF_UNCERT) != 0);
};

// A full banner's sound, for the answer in hand (WR_NONE: none is coming).
// Called before Bn_Delta, which overwrites the answer it reads.
void(float st) Bn_SoundFor =
{
	if (st == WR_RANKED && ui_bn_ansr == 1 && ui_bn_ansstored == 1)
	{
		ui_bn_wrsaid = TRUE;
		Bn_Sound(2);
		return;
	}
	Bn_Delta(FALSE);                        // no claim beside a standing PB
	if (FS_RunClass(ui_bn_flags) == RC_CLEAN && ui_bn_newpb)
		Bn_Sound(1);
	else
		Bn_Sound(0);
};

void(float state) Bn_RaiseFull =
{
	local float leg, uncert, cls, server;

	leg = getstatf(STAT_FS_FINLEG);
	if (leg < 1 || getstatf(STAT_FS_FINTICKS) <= 0)
		return;
	leg = leg - 1;
	ui_bn_track = floor(leg / 100);
	ui_bn_leg   = leg - ui_bn_track * 100;
	ui_bn_ticks = getstatf(STAT_FS_FINTICKS);
	ui_bn_flags = getstatf(STAT_FS_FINFLAGS);
	ui_bn_word  = 0;
	Bn_Subject();
	uncert = (ui_bn_flags & TF_UNCERT) != 0;

	// A chained stage run re-arms in its finish frame and that zeroes PBWAS;
	// stat 99 is the same leg's PB from the close SV_TimerFinish ran first.
	server = getstatf(STAT_FS_TIMERPBWAS);
	if (ui_bn_leg > 0)
		server = getstatf(STAT_FS_STAGEENDPBWAS);
	ui_bn_pb = Bn_PBOf(ui_bn_track, ui_bn_leg, ui_bn_flags, server);
	ui_bn_pbsrc = ui_bn_pbsrcnow;
	ui_bn_kept = TRUE;                      // a finish's PB write has no recorder gate

	ui_bn_lrank = ui_bn_lof = 0;
	if (ui_bn_mine && ui_bn_pbsrc != 0)
	{
		// The card raised this frame has just scanned the same folder.
		if (ui_rs_open && ui_rs_at == cltime && ui_rs_ticks == ui_bn_ticks
		 && ui_rs_leg == ui_bn_leg && ui_rs_track == ui_bn_track)
		{
			ui_bn_lrank = ui_rs_rank;
			ui_bn_lof   = ui_rs_of;
		}
		else
			Results_Rank(ui_bn_track, ui_bn_leg, ui_bn_ticks, uncert,
			             ui_bn_lrank, ui_bn_lof);
	}

	ui_bn_sub  = (serverkey("board") == "ranked");
	ui_bn_kind = BN_FULL;
	ui_bn_test = FALSE;
	Bn_Begin();
	// A chained stage run re-arms in the finish frame: FINISHED never arrives.
	if (state == TS_RUNNING)
		ui_bn_exit = ui_bn_at + BN_MINAGE;

	// Own clean or segmented runs make a sound; with a board to hear from it
	// waits for the answer (Banner_Frame), so the PB sting cannot contradict it.
	cls = FS_RunClass(ui_bn_flags);
	if (ui_bn_mine)
	if (cls == RC_CLEAN || (cls == RC_SEGMENT && !(ui_bn_flags & TF_SHADOW)))
	{
		if (ui_bn_sub)
			ui_bn_sndowed = TRUE;
		else
			Bn_SoundFor(WR_NONE);
	}
};

// The final stage of a main run closes in the finish frame: a tail, not a banner.
// kept: its STAGEREC edge came with this close.
void(float kept) Bn_LatchTail =
{
	local float seg, ticks, uncert;

	if (ui_bn_kind != BN_FULL || ui_bn_leg != 0)
		return;
	seg   = getstatf(STAT_FS_STAGEENDSEG);
	ticks = getstatf(STAT_FS_STAGEENDTICKS);
	if (seg < 0 || ticks <= 0 || getstatf(STAT_FS_TIMERSEGS) <= 1)
		return;
	ui_bn_tailleg   = FS_LegOf(seg, TRUE);
	ui_bn_tailticks = ticks;
	ui_bn_tailword  = getstatf(STAT_FS_STAGEENDST);
	ui_bn_tailkept  = kept;
	uncert = (ui_bn_flags & TF_UNCERT) != 0;
	ui_bn_tailpb = Bn_PBOf(ui_bn_track, ui_bn_tailleg,
	                       LT_StageFlags(ui_bn_tailword) | (ui_bn_flags & TF_UNCERT),
	                       getstatf(STAT_FS_STAGEENDPBWAS));
	ui_bn_tailpbsrc = ui_bn_pbsrcnow;
	ui_bn_taillrank = ui_bn_taillof = 0;
	if (ui_bn_mine && ui_bn_tailpbsrc != 0)
	if (ui_bn_tailword & SF_QUALIFIES)
		Results_Rank(ui_bn_track, ui_bn_tailleg, ticks, uncert,
		             ui_bn_taillrank, ui_bn_taillof);
};

void(float kept) Bn_RaiseStage =
{
	local float seg, ticks, uncert, shown;

	seg   = getstatf(STAT_FS_STAGEENDSEG);
	ticks = getstatf(STAT_FS_STAGEENDTICKS);
	if (seg < 0 || ticks <= 0)
		return;
	shown = (ui_bn_kind == BN_STAGE && !ui_bn_outat);

	ui_bn_track = getstatf(STAT_FS_TIMERTRACK);
	ui_bn_leg   = FS_LegOf(seg, TRUE);
	ui_bn_ticks = ticks;
	ui_bn_word  = getstatf(STAT_FS_STAGEENDST);
	ui_bn_flags = LT_StageFlags(ui_bn_word) | (getstatf(STAT_FS_TIMERFLAGS) & TF_UNCERT);
	ui_bn_kept  = kept;
	Bn_Subject();
	uncert = (ui_bn_flags & TF_UNCERT) != 0;
	ui_bn_pb = Bn_PBOf(ui_bn_track, ui_bn_leg, ui_bn_flags, getstatf(STAT_FS_STAGEENDPBWAS));
	ui_bn_pbsrc = ui_bn_pbsrcnow;

	ui_bn_lrank = ui_bn_lof = 0;
	if (ui_bn_mine && ui_bn_pbsrc != 0)
	if (ui_bn_word & SF_QUALIFIES)
	{
		if (ui_rs_toastat == cltime && ui_rs_toastseg == ui_bn_leg
		 && ui_rs_toastticks == ticks)
		{
			ui_bn_lrank = ui_rs_toastrank;
			ui_bn_lof   = ui_rs_toastof;
		}
		else
			Results_Rank(ui_bn_track, ui_bn_leg, ticks, uncert,
			             ui_bn_lrank, ui_bn_lof);
	}

	ui_bn_sub  = (ui_bn_word & SF_POSTED) != 0;
	ui_bn_kind = BN_STAGE;
	ui_bn_test = FALSE;
	Bn_Begin();
	if (shown)
		ui_bn_at = cltime - BN_CTIN;    // already up: replace in place
	ui_rs_toastat = 0;                  // this is the toast now
};

void() Banner_MapInit =
{
	ui_bn_kind = BN_NONE;
	ui_bn_lastfin = -1;
	ui_bn_lastend = -1;
	ui_bn_lastsrec = -1;
	ui_bn_laststate = -1;
	ui_bn_tailleg = -1;
	ui_bn_sndowed = FALSE;
	Bn_SndProbeAll();
};

// ---- the frame -------------------------------------------------------------

void(float pend) Bn_Timeline =
{
	local float hold, tin, tout, base, te;

	hold = cvar("hud_banner_hold");
	if (hold <= 0)
		hold = 3.5;
	tin = BN_TIN;
	tout = BN_TOUT;
	if (ui_bn_kind == BN_STAGE)
	{
		hold = hold * BN_CHOLD;
		tin = BN_CTIN;
		tout = BN_CTOUT;
	}

	if (ui_bn_outat > 0)
	{
		if (cltime - ui_bn_outat >= tout)
			ui_bn_kind = BN_NONE;
		return;
	}

	// A pending answer holds the banner (capped); a late one extends it, an
	// early one never shortens it.
	base = ui_bn_at + tin + hold;
	te = base;
	if (pend)
		te = base + BN_PENDMAX;
	else if (ui_bn_replyat > base - BN_REPLYMIN)
		te = max(base, min(ui_bn_replyat + BN_REPLYMIN, base + BN_PENDMAX + BN_REPLYMIN));
	if (ui_bn_exit > 0)
	if (ui_bn_exit < te)
		te = ui_bn_exit;
	if (cltime >= te)
	{
		ui_bn_outat = cltime;
		if (ui_bn_sndowed)
		{
			ui_bn_sndowed = FALSE;          // no answer came: the local verdict
			Bn_SoundFor(WR_NONE);
		}
	}
};

void() Banner_Frame =
{
	local float state, finrec, endrec, srec, finfresh, fresh, skept, st, pend, own;

	if (strcmp(zone_mapname, ui_bn_map))
	{
		ui_bn_map = zone_mapname;
		Banner_MapInit();
	}
	// Watching someone else: their counters are not ours to take edges from.
	// The owner stat arrives WITH the counters, so a target switch re-seeds on
	// the frame the new target's stats land, not a round trip early.
	own = Bn_Owner();
	if (own != ui_bn_lastent)
	{
		ui_bn_lastent = own;
		ui_bn_lastfin = -1;
		ui_bn_lastend = -1;
		ui_bn_lastsrec = -1;
	}

	// The latches first, with no return between (the toast's lesson).
	state  = getstatf(STAT_FS_TIMERSTATE);
	finrec = getstatf(STAT_FS_FINREC);
	endrec = getstatf(STAT_FS_STAGEENDREC);
	srec   = getstatf(STAT_FS_STAGEREC);    // bumped in the same close when the stage was kept
	finfresh = FALSE;
	if (ui_bn_lastfin >= 0)
	if (finrec > ui_bn_lastfin)
		finfresh = TRUE;
	ui_bn_lastfin = finrec;
	fresh = FALSE;
	if (ui_bn_lastend >= 0)
	if (endrec > ui_bn_lastend)
		fresh = TRUE;
	ui_bn_lastend = endrec;
	skept = FALSE;
	if (ui_bn_lastsrec >= 0)
	if (srec > ui_bn_lastsrec)
		skept = TRUE;
	ui_bn_lastsrec = srec;

	// Yields.  A new attempt ends a full banner (not before BN_MINAGE); a
	// compact one goes the moment its run stops running.
	if (!ui_bn_test)
	if (ui_bn_exit <= 0)
	{
		if (ui_bn_kind == BN_FULL)
		if (state == TS_RUNNING && ui_bn_laststate != TS_RUNNING)
			ui_bn_exit = max(cltime, ui_bn_at + BN_MINAGE);
		if (ui_bn_kind == BN_STAGE)
		if (state != TS_RUNNING)
			ui_bn_exit = cltime;
	}
	ui_bn_laststate = state;

	if (finfresh)
	{
		Bn_RaiseFull(state);
		if (fresh)
			Bn_LatchTail(skept);    // FINREC wins a shared frame
	}
	else if (fresh)
	if (state == TS_RUNNING)
	if (cvar("hud_banner") && cvar("hud_banner_stages"))
	if (!(ui_bn_kind == BN_FULL && cltime - ui_bn_at < BN_MINAGE))
		Bn_RaiseStage(skept);

	if (ui_bn_kind == BN_NONE)
		return;

	st = Bn_Answer(FALSE);
	pend = (st == WR_PENDING);
	if (st == WR_NONE && ui_bn_sub && cltime - ui_bn_at < BN_GRACE)
		pend = TRUE;
	if (!pend && st != WR_NONE && !ui_bn_replyat)
		ui_bn_replyat = cltime;
	if (ui_bn_sndowed && !pend)
	{
		ui_bn_sndowed = FALSE;
		Bn_SoundFor(st);
	}

	// The card was asked for (F1 / MOUSE3 / `results`): the banner makes way.
	if (ui_bn_kind == BN_FULL && ui_rs_cursor && ui_bn_outat <= 0)
		ui_bn_outat = cltime;
	Bn_Timeline(pend);

	// The card covers the same rows: it waits until this banner starts to leave.
	if (ui_bn_kind == BN_FULL && ui_bn_outat <= 0 && cvar("hud_banner"))
		ui_bn_cardat = cltime;
};

// ---- drawing ---------------------------------------------------------------

// One quad, TL TR BR BL, the left edge at one alpha and the right at another.
void(vector tl, vector tr, vector br, vector bl, vector col, float la, float ra) Bn_Quad =
{
	R_BeginPolygon("", DRAWFLAG_TWOSIDED, TRUE);
	R_PolygonVertex(tl, '0 0 0', col, la);
	R_PolygonVertex(tr, '0 0 0', col, ra);
	R_PolygonVertex(br, '0 0 0', col, ra);
	R_PolygonVertex(bl, '0 0 0', col, la);
	R_EndPolygon();
};

// A "/" band y..y+h over [x0, x1] (its BOTTOM edge), skewed k over its full
// height, split at xm with the alpha peaking there.
void(float y, float h, float x0, float x1, float xm, float k, vector col, vector al) Bn_Band =
{
	local float s;

	s = k / max(h, 1);      // x shift per unit of height
	Bn_Quad([x0 + h * s, y], [xm + h * s, y], [xm, y + h], [x0, y + h], col, al_x, al_y);
	Bn_Quad([xm + h * s, y], [x1 + h * s, y], [x1, y + h], [xm, y + h], col, al_y, al_x);
};

float(float face, float px, string s) Bn_W =
{
	Font_Set(face);
	px = Font_Px(px);
	return stringwidth(s, TRUE, [px, px]);
};

// The strings a full banner draws.  The editor's sample fills them itself.
string ui_bn_s_title, ui_bn_s_sub, ui_bn_s_time;
vector ui_bn_s_hero, ui_bn_s_acc;

void() Bn_FullStrings =
{
	local string nm;

	ui_bn_s_title = strcat(Bn_LegLabel(ui_bn_track, ui_bn_leg), " COMPLETE");
	ui_bn_s_sub = serverkey("map");
	if (!ui_bn_mine)
	{
		nm = getplayerkeyvalue(ui_bn_slot, "name");
		if (nm != "")
			ui_bn_s_sub = strcat(nm, "  ", ui_bn_s_sub);
	}
	ui_bn_s_time = Time_TickString(ui_bn_ticks, Timer_Tick());
	Bn_Delta(FALSE);
	Bn_Place(FALSE);
	ui_bn_s_hero = Bn_HeroColor();
	ui_bn_s_acc = Bn_Accent();
};

// ox: the slide offset.  Returns the band's height (the tail sits under it).
float(vector scr, float ox, float a) Bn_DrawFull =
{
	local float u, pass, tsz, hsz, ssz, dsz, psz, p2sz, gl, gh, gr, H, wl, wh, wr;
	local float gap, x0, y0, xl, xr, k, span;

	x0 = scr_x * cvar("hud_banner_x");
	y0 = scr_y * cvar("hud_banner_y");
	u = HUD_Size("hud_banner_size", 32 * ui_cv_scale) / 32;
	tsz = hsz = ssz = dsz = psz = p2sz = wl = wh = wr = xl = xr = gap = 0;

	// The three groups must clear both edges; one step down if they do not.
	for (pass = 0; pass < 2; pass = pass + 1)
	{
		if (pass)
			u = u * 0.75;
		tsz  = 20 * u;
		hsz  = 32 * u;
		ssz  = 8 * u;
		dsz  = 9 * u;
		psz  = 20 * u;
		p2sz = 8 * u;
		gap  = 20 * u;
		wl = max(Bn_W(ui_font_display, tsz, ui_bn_s_title), Bn_W(ui_font_ui, ssz, ui_bn_s_sub));
		wh = max(Bn_W(ui_font_display, hsz, ui_bn_s_time), Bn_W(ui_font_mono, dsz, ui_bn_dl));
		wr = max(Bn_W(ui_font_display, psz, ui_bn_pl1), Bn_W(ui_font_ui, p2sz, ui_bn_pl2));
		xl = x0 - wh * 0.5 - gap;
		xr = x0 + wh * 0.5 + gap;
		if (xl - wl >= 16 * u && xr + wr <= scr_x - 16 * u)
			break;
	}

	ui_bn_drawu = u;
	gl = tsz + 2 * u + ssz;
	gh = hsz + u + dsz;
	gr = psz + 2 * u + p2sz;
	H = 8 * u + max(gl, max(gh, gr));
	k = 0.35 * H;
	span = scr_x + 2 * k + 16 * u;

	Bn_Band(y0, H, ox - 8 * u - k, ox + scr_x + 8 * u, x0 + ox - k * 0.5, k,
	        BNC_BAND, [0.45 * a, 0.86 * a]);
	Bn_Band(y0, 2 * u, ox - 8 * u - k + (H - 2 * u) * 0.35, ox + scr_x + 8 * u + (H - 2 * u) * 0.35,
	        x0 + ox - k * 0.5 + (H - 2 * u) * 0.35, 2 * u * 0.35, ui_bn_s_acc, [0.35 * a, 0.95 * a]);
	Bn_Band(y0 + H - 2 * u, 2 * u, ox - 8 * u - k, ox + scr_x + 8 * u,
	        x0 + ox - k * 0.5, 2 * u * 0.35, ui_bn_s_acc, [0.35 * a, 0.95 * a]);

	Font_Set(ui_font_display);
	HUD_TextR([xl + ox, y0 + (H - gl) * 0.5], ui_bn_s_title, tsz, RSC_TEXT, a);
	HUD_TextC([x0 + ox, y0 + (H - gh) * 0.5], ui_bn_s_time, hsz, ui_bn_s_hero, a);
	HUD_Text([xr + ox, y0 + (H - gr) * 0.5], ui_bn_pl1, psz, ui_bn_plc, a);
	Font_Set(ui_font_ui);
	HUD_TextR([xl + ox, y0 + (H - gl) * 0.5 + tsz + 2 * u], ui_bn_s_sub, ssz, RSC_DIM, a);
	HUD_Text([xr + ox, y0 + (H - gr) * 0.5 + psz + 2 * u], ui_bn_pl2, p2sz, ui_bn_pl2c, a);
	Font_Set(ui_font_mono);
	HUD_TextC([x0 + ox, y0 + (H - gh) * 0.5 + hsz + u], ui_bn_dl, dsz, ui_bn_dlc, a);

	HUD_Rect("banner", [xl - wl, y0], [xr + wr - (xl - wl), H], [x0, y0]);
	return H;
};

// The last stage of a main run, a thin strip under the ribbon.
void(vector scr, float ox, float a, float H) Bn_DrawTail =
{
	local float u, sz, w, x0, y;
	local string s;

	if (ui_bn_tailleg < 1)
		return;
	u = HUD_Size("hud_banner_size", 32 * ui_cv_scale) / 32;
	Bn_Place(TRUE);
	Bn_Delta(TRUE);
	s = sprintf("%s  %s  %s  %s %s", Bn_LegLabel(ui_bn_track, ui_bn_tailleg),
	            Time_TickString(ui_bn_tailticks, Timer_Tick()), ui_bn_dl,
	            ui_bn_pl1, ui_bn_pl2);
	Font_Set(ui_font_ui);
	sz = Font_Px(8 * u);
	w = stringwidth(s, TRUE, [sz, sz]) + 16 * u;
	x0 = scr_x * cvar("hud_banner_x") + ox;
	y = scr_y * cvar("hud_banner_y") + H + 3 * u;
	drawfill([x0 - w * 0.5, y], [w, sz + 4 * u], BNC_BAND, 0.8 * a, 0);
	HUD_TextC([x0, y + 2 * u], s, sz, RSC_TEXT, a);
};

void(vector scr) Bn_DrawStage =
{
	local float u, t, a, dx, lsz, msz, psz, wlab, wtm, wdl, wpl, w, hc, x, y, k;
	local string lab, tm, pl;

	t = (cltime - ui_bn_at) / BN_CTIN;
	a = min(t, 1);
	dx = -24 * (1 - a);
	if (ui_bn_outat > 0)
	{
		t = (cltime - ui_bn_outat) / BN_CTOUT;
		a = max(1 - t, 0);
		dx = 24 * t;
	}
	if (a <= 0)
		return;

	u = HUD_Size("hud_banner_size", 32 * ui_cv_scale) / 32;
	dx = dx * u;
	lab = Bn_LegLabel(ui_bn_track, ui_bn_leg);
	tm = Time_TickString(ui_bn_ticks, Timer_Tick());
	Bn_Delta(FALSE);
	Bn_Place(FALSE);
	pl = ui_bn_pl1;
	if (ui_bn_pl2 != "")
		pl = strcat(pl, "  ", ui_bn_pl2);

	lsz = 16 * u;
	msz = 8 * u;
	psz = 8 * u;
	wlab = Bn_W(ui_font_display, lsz, lab);
	wtm  = Bn_W(ui_font_display, lsz, tm);
	wdl  = Bn_W(ui_font_mono, msz, ui_bn_dl);
	wpl  = Bn_W(ui_font_ui, psz, pl);
	w = wlab + 10 * u + wtm + 10 * u + wdl + 10 * u + wpl + 24 * u;
	hc = 8 * u + lsz;
	k = 0.35 * hc;
	x = scr_x * cvar("hud_banner_x") - w * 0.5 + dx;
	y = scr_y * cvar("hud_banner_y") + 10 * u;

	Bn_Band(y, hc, x, x + w, x + w * 0.5, k, BNC_BAND, [0.7 * a, 0.86 * a]);
	Bn_Band(y, hc, x, x + 3 * u, x + 3 * u, k, Bn_Accent(), [a, a]);

	x = x + 12 * u + k * 0.5;
	Font_Set(ui_font_display);
	HUD_Text([x, y + 4 * u], lab, lsz, RSC_DIM, a);
	x = x + wlab + 10 * u;
	HUD_Text([x, y + 4 * u], tm, lsz, RSC_TEXT, a);
	x = x + wtm + 10 * u;
	Font_Set(ui_font_mono);
	HUD_Text([x, y + (hc - Font_Px(msz)) * 0.5], ui_bn_dl, msz, ui_bn_dlc, a);
	x = x + wdl + 10 * u;
	Font_Set(ui_font_ui);
	HUD_Text([x, y + (hc - Font_Px(psz)) * 0.5], pl, psz, ui_bn_plc, a);
	Font_Reset();
};

void(vector scr) Banner_Draw =
{
	local float t, ox, a, H, span, k;

	if (!cvar("hud_banner"))
		return;
	if (rec_sb_open || sc_held || ui_rs_cursor || rec_wt_on)
		return;

	if (ui_bn_kind == BN_STAGE)
	{
		Bn_DrawStage(scr);
		return;
	}

	if (ui_bn_kind == BN_FULL)
	{
		Bn_FullStrings();
		// Slide in (ease-out cubic), out to the right (ease-in).  The span is
		// generous: the band is a screen wide plus its skew.
		k = 0.35 * 100 * ui_cv_scale;
		span = scr_x + 2 * k + 64 * ui_cv_scale;
		a = 1;
		t = min((cltime - ui_bn_at) / BN_TIN, 1);
		ox = -(1 - t) * (1 - t) * (1 - t) * span;
		if (ui_bn_outat > 0)
		{
			t = min((cltime - ui_bn_outat) / BN_TOUT, 1);
			ox = t * t * t * span;
		}
		H = Bn_DrawFull(scr, ox, a);
		Bn_DrawTail(scr, ox, a, H);
		Font_Reset();
		return;
	}

	// The layout editor's sample, so the banner can be placed with none up.
	if (ui_he_open)
	{
		ui_bn_s_title = "MAP COMPLETE";
		ui_bn_s_sub   = serverkey("map");
		ui_bn_s_time  = "1:23.456";
		ui_bn_s_hero  = TC_AHEAD;
		ui_bn_s_acc   = TC_AHEAD;
		ui_bn_dl      = "-0:00.512  NEW PB";
		ui_bn_dlc     = TC_AHEAD;
		ui_bn_pl1     = "#3 of 17";
		ui_bn_plc     = RSC_TEXT;
		ui_bn_pl2     = "TOP 10";
		ui_bn_pl2c    = BNC_TOP;
		Bn_DrawFull(scr, 0, 1);
		Font_Reset();
	}
};

// ---- console ---------------------------------------------------------------

void() Bn_Status =
{
	local float st, r, o, tier, stored;

	print(sprintf("banner: kind %g test %g age %.2f outat %.2f exit %.2f\n",
	              ui_bn_kind, ui_bn_test, cltime - ui_bn_at,
	              (ui_bn_outat > 0) ? cltime - ui_bn_outat : -1,
	              (ui_bn_exit > 0) ? ui_bn_exit - cltime : -1));
	print(sprintf("banner: subject track %g leg %g ticks %g flags %g word %g pb %g\n",
	              ui_bn_track, ui_bn_leg, ui_bn_ticks, ui_bn_flags, ui_bn_word, ui_bn_pb));
	print(sprintf("banner: mine %g slot %g sub %g local #%g of %g replyat %.2f\n",
	              ui_bn_mine, ui_bn_slot, ui_bn_sub, ui_bn_lrank, ui_bn_lof,
	              (ui_bn_replyat > 0) ? ui_bn_replyat - ui_bn_at : -1));
	r = o = tier = stored = 0;
	st = Results_KeyRank(Bn_Raw(FALSE), ui_bn_track, ui_bn_leg, ui_bn_ticks,
	                     r, o, tier, stored);
	print(sprintf("banner: key \"%s\" -> state %g rank %g of %g tier %g stored %g\n",
	              Bn_Raw(FALSE), st, r, o, tier, stored));
	if (ui_bn_kind != BN_NONE)
	{
		Bn_Delta(FALSE);
		Bn_Place(FALSE);
		print(sprintf("banner: draws \"%s\" \"%s\" | \"%s\" | \"%s\" / \"%s\"\n",
		              strcat(Bn_LegLabel(ui_bn_track, ui_bn_leg),
		                     (ui_bn_kind == BN_FULL) ? " COMPLETE" : ""),
		              Time_TickString(ui_bn_ticks, Timer_Tick()),
		              ui_bn_dl, ui_bn_pl1, ui_bn_pl2));
		print(sprintf("banner: accent %v hero %v\n", Bn_Accent(), Bn_HeroColor()));
	}
	if (ui_bn_tailleg >= 1)
	{
		Bn_Delta(TRUE);
		Bn_Place(TRUE);
		print(sprintf("banner: tail leg %g ticks %g word %g pb %g draws \"%s\" \"%s\" / \"%s\"\n",
		              ui_bn_tailleg, ui_bn_tailticks, ui_bn_tailword, ui_bn_tailpb,
		              ui_bn_dl, ui_bn_pl1, ui_bn_pl2));
	}
	print(sprintf("banner: latches fin %g end %g state %g toastat %.2f drawu %g\n",
	              ui_bn_lastfin, ui_bn_lastend, ui_bn_laststate,
	              (ui_rs_toastat > 0) ? cltime - ui_rs_toastat : -1, ui_bn_drawu));
	print(sprintf("banner: sound %g  end %g pb %g wr %g  (%s)\n",
	              cvar("hud_banner_sound"), ui_bn_sndok_end, ui_bn_sndok_pb,
	              ui_bn_sndok_wr, Bn_SndPath(cvar_string("hud_banner_snd_end"))));
};

float(string cmd) Banner_ConsoleCommand =
{
	local string sub;

	if (argv(0) != "banner")
		return FALSE;
	sub = argv(1);

	// banner test <track> <leg> <ticks> [pb] [flags]  -- a full banner, this subject
	// banner stage <track> <leg> <ticks> [pb] [word]  -- a compact one
	if (sub == "test" || sub == "stage")
	{
		ui_bn_track = stof(argv(2));
		ui_bn_leg   = stof(argv(3));
		ui_bn_ticks = stof(argv(4));
		ui_bn_pb    = stof(argv(5));
		ui_bn_mine  = TRUE;
		ui_bn_slot  = player_localnum;
		ui_bn_lrank = ui_bn_lof = 0;
		ui_bn_kind  = BN_FULL;
		ui_bn_word  = 0;
		ui_bn_flags = stof(argv(6));
		if (sub == "stage")
		{
			ui_bn_kind  = BN_STAGE;
			ui_bn_word  = stof(argv(6));
			ui_bn_flags = LT_StageFlags(ui_bn_word);
		}
		ui_bn_sub  = FALSE;
		ui_bn_pbsrc = 1;
		ui_bn_kept = TRUE;
		ui_bn_test = TRUE;
		Bn_Begin();
		Bn_Status();
		return TRUE;
	}
	// banner fake "<key>" | banner fake  -- the key a test banner reads
	if (sub == "fake")
	{
		if (ui_bn_fake != "")
			strunzone(ui_bn_fake);
		ui_bn_fake = "";
		if (argv(2) != "")
			ui_bn_fake = strzone(argv(2));
		print(sprintf("banner: fake key \"%s\"\n", ui_bn_fake));
		return TRUE;
	}
	if (sub == "off")
	{
		ui_bn_kind = BN_NONE;
		return TRUE;
	}
	if (sub == "probe")
		Bn_SndProbeAll();
	// banner sound end|pb|wr  -- plays it as a banner would (or nothing)
	if (sub == "sound")
	{
		if (argv(2) == "pb")
			Bn_Sound(1);
		else if (argv(2) == "wr")
			Bn_Sound(2);
		else
			Bn_Sound(0);
	}
	Bn_Status();
	return TRUE;
};
