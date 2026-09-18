/*
===========================================================================
  sv_resume.qc -- Multi-Session: a run parked when its player leaves (drop,
  map change, quit) and continued when they come back.  WP10, design B.

  The slot is a save state -- SV_SaveWriteState/ApplyState with sl_root pointed
  at data/resume/<map>/@<key>/save000/ -- plus ms.txt, the recorder's counters,
  written LAST: no ms.txt, no slot.  One per player per map, single use.

  Accept: claim (rename ms.txt, so two lobbies cannot resume one slot), park the
  player at the saved spot, copy a streamed run.rec into this run's part file
  (R), count down (C), apply.  A buffered slot loads at apply.  The run carries
  TF_MULTISESSION; its .rec holds `pause` ... `session` (grammar block, sv_timer.qc).
===========================================================================
*/

#define MS_NONE   0
#define MS_WAIT   1     // a stream copy is due; another player's copy holds the lobby
#define MS_COPY   2     // copying run.rec into this run's part file
#define MS_COUNT  3     // counting down, then SV_MsApply

.float  run_ms_want;    // connected since the last offer check
.float  run_ms_offer;   // a paused run on this map is on offer
.float  run_ms_warned;  // told a fresh run will drop it
.float  run_ms_keyed;   // *resume carries something
.float  run_ms_keyat;   // when a finished `A` key is cleared
.float  run_ms_until;   // countdown end
.float  run_ms_readyby; // stop waiting for the CSQC reports and the zones
.float  run_ms_norec;   // the run continues unrecorded
.float  run_ms_pct;     // last published copy step (10%)
.vector run_ms_org;     // parked here while R/C runs
.float  rec_ms_src, rec_ms_dst, rec_ms_left, rec_ms_total, rec_ms_flagofs;
entity  rec_ms_owner;   // one copy per lobby: the first fgets reads the whole file

// ms.txt, read by SV_MsReadMeta and consumed in the same call.
float  ms_ticks, ms_seg, ms_segs, ms_track, ms_leg, ms_sess, ms_day, ms_tickrate;
float  ms_lines, ms_bytes, ms_n, ms_padn, ms_cp, ms_in, ms_pk, ms_warp, ms_ride;
float  ms_pm, ms_pe, ms_portal, ms_pauses, ms_rsess, ms_posts, ms_pinned, ms_full;
float  ms_stseg, ms_sttick, ms_starmed, ms_legzone, ms_legtrack, ms_legseg;
string ms_why, ms_mapcrc, ms_zonecrc, ms_zonerule, ms_rec, ms_rid;
vector ms_org, ms_ang;

/*
===========================================================================
  Paths
===========================================================================
*/
// The guid on a lobby; "local" for the listen host, whose guid may be empty.
string(entity e) SV_MsKey =
{
	if (!Lobby_Active())
	if (num_for_edict(e) == 1)
		return "local";
	return SV_SaveSanitise(infokey(e, "guid"));
};

string(entity e) SV_MsRoot = { return sprintf("data/resume/%s/@%s", mapname, SV_MsKey(e)); };
string(entity e, string leaf) SV_MsPath = { return sprintf("%s/save000/%s", SV_MsRoot(e), leaf); };

string() SV_MsClaimLeaf =
{
	if (Lobby_Active())
		return sprintf("ms.p%s.txt", cvar_string("sv_port"));
	return "ms.claim.txt";
};

// Another lobby's writes are not in this process's name hash until a map load;
// renaming a file onto itself adds it (FS_Rename2 -> FS_FlushFSHashWritten).
// Lobbies only: that is where the processes differ, and Linux's rename(a, a)
// is a no-op success.
void(entity e) SV_MsAdopt =
{
	if (!Lobby_Active())
		return;
	frename(SV_MsPath(e, "ms.txt"), SV_MsPath(e, "ms.txt"));
	frename(SV_MsPath(e, "state.txt"), SV_MsPath(e, "state.txt"));
	frename(SV_MsPath(e, "run.rec"), SV_MsPath(e, "run.rec"));
};

/*
===========================================================================
  ms.txt
===========================================================================
*/
void(entity e, float ticks, string why, string mode, float bytes) SV_MsWriteMeta =
{
	local filestream f;

	f = fopen(SV_MsPath(e, "ms.txt"), FILE_WRITE);
	if (f < 0)
		return;
	fputs(f, "FTESURF-RESUME 1\n");
	fputs(f, sprintf("map %s\n", mapname));
	fputs(f, sprintf("day %s\n", strftime(TRUE, "%Y%m%d")));
	fputs(f, sprintf("why %s\n", why));
	fputs(f, sprintf("sessions %d\n", e.run_ms_sessions));
	fputs(f, sprintf("ticks %d\n", ticks));
	fputs(f, sprintf("run %d %d %d %d\n", e.run_t_seg, e.run_t_segs, e.run_t_track,
	                 FS_LegOf(e.run_t_startseg, e.run_t_stagerun)));
	fputs(f, sprintf("origin %.4f %.4f %.4f\n", e.origin_x, e.origin_y, e.origin_z));
	fputs(f, sprintf("angles %.4f %.4f\n", e.v_angle_x, e.v_angle_y));
	fputs(f, sprintf("leglatch %d %d %d\n", e.run_leg_zone, e.run_leg_track, e.run_leg_seg));
	fputs(f, sprintf("stage %d %d %d\n", e.run_st_seg, e.run_st_tick, e.run_st_armed ? 1 : 0));
	if (infokey(world, "*mapcrc") != "")
		fputs(f, sprintf("mapcrc %s\n", infokey(world, "*mapcrc")));
	if (zone_crc != "")
		fputs(f, sprintf("zonecrc %s\n", zone_crc));
	fputs(f, sprintf("zonerule %d %d %d\n", run_t_swept, run_t_hull, run_t_hulllive));
	fputs(f, sprintf("tickrate %.9g\n", run_t_tick));
	fputs(f, sprintf("rec %s\n", mode));
	fputs(f, sprintf("recbytes %d\n", bytes));
	// Every `end` counter, and what SV_RecOpen resets: the resume continues them.
	fputs(f, sprintf("reclines %d %d %d %d\n", e.rec_rec_lines, e.rec_rec_n, e.rec_rec_padn, e.rec_rec_cp));
	fputs(f, sprintf("recrows %d %d %d %d\n", e.rec_rec_in, e.rec_rec_pk, e.rec_rec_warp, e.rec_rec_ride));
	fputs(f, sprintf("recstate %d %d %d %d\n", e.rec_rec_pm, e.rec_rec_pe, e.rec_rec_portal, e.rec_rec_pinned));
	fputs(f, sprintf("recsess %d %d %d %d\n", e.rec_rec_pauses, e.rec_rec_sess, e.rec_rec_posts, e.rec_rec_full));
	if (e.rec_rec_rid != "")
		fputs(f, sprintf("runid %s\n", e.rec_rec_rid));
	fclose(f);
};

float(string path) SV_MsReadMeta =
{
	local filestream f;
	local string k;
	local float n, ok;

	ms_ticks = ms_seg = ms_segs = ms_track = ms_leg = ms_sess = ms_day = ms_tickrate = 0;
	ms_lines = ms_n = ms_padn = ms_cp = ms_in = ms_pk = ms_warp = ms_ride = 0;
	ms_pm = ms_pe = ms_portal = ms_pauses = ms_rsess = ms_posts = ms_pinned = ms_full = 0;
	ms_bytes = -1;
	ms_stseg = ms_legzone = -1;
	ms_sttick = ms_starmed = ms_legtrack = ms_legseg = 0;
	ms_why = ms_mapcrc = ms_zonecrc = ms_zonerule = ms_rid = "";
	ms_rec = "none";
	ms_org = ms_ang = '0 0 0';

	f = fopen(path, FILE_READ);
	if (f < 0)
		return FALSE;
	ok = FALSE;
	while ((k = fgets(f)) != "")
	{
		n = tokenize(k);
		if (n < 2)
			continue;
		k = argv(0);
		if (k == "FTESURF-RESUME") ok = TRUE;
		else if (k == "day")       ms_day = FS_DayNumOf(argv(1));
		else if (k == "why")       ms_why = argv(1);
		else if (k == "sessions")  ms_sess = stof(argv(1));
		else if (k == "ticks")     ms_ticks = stof(argv(1));
		else if (k == "mapcrc")    ms_mapcrc = argv(1);
		else if (k == "zonecrc")   ms_zonecrc = argv(1);
		else if (k == "tickrate")  ms_tickrate = stof(argv(1));
		else if (k == "rec")       ms_rec = argv(1);
		else if (k == "recbytes")  ms_bytes = stof(argv(1));
		else if (k == "runid")     ms_rid = argv(1);
		else if (k == "zonerule")
		{
			if (n >= 4)
				ms_zonerule = sprintf("%s %s %s", argv(1), argv(2), argv(3));
		}
		else if (n >= 5)
		{
			if (k == "run")
			{
				ms_seg = stof(argv(1)); ms_segs = stof(argv(2));
				ms_track = stof(argv(3)); ms_leg = stof(argv(4));
			}
			else if (k == "reclines")
			{
				ms_lines = stof(argv(1)); ms_n = stof(argv(2));
				ms_padn = stof(argv(3)); ms_cp = stof(argv(4));
			}
			else if (k == "recrows")
			{
				ms_in = stof(argv(1)); ms_pk = stof(argv(2));
				ms_warp = stof(argv(3)); ms_ride = stof(argv(4));
			}
			else if (k == "recstate")
			{
				ms_pm = stof(argv(1)); ms_pe = stof(argv(2));
				ms_portal = stof(argv(3)); ms_pinned = stof(argv(4));
			}
			else if (k == "recsess")
			{
				ms_pauses = stof(argv(1)); ms_rsess = stof(argv(2));
				ms_posts = stof(argv(3)); ms_full = stof(argv(4));
			}
		}
		else if (n >= 4)
		{
			if (k == "origin")
				ms_org = [stof(argv(1)), stof(argv(2)), stof(argv(3))];
			else if (k == "leglatch")
			{
				ms_legzone = stof(argv(1)); ms_legtrack = stof(argv(2)); ms_legseg = stof(argv(3));
			}
			else if (k == "stage")
			{
				ms_stseg = stof(argv(1)); ms_sttick = stof(argv(2)); ms_starmed = stof(argv(3));
			}
		}
		else if (k == "angles")
			ms_ang = [stof(argv(1)), stof(argv(2)), 0];
	}
	fclose(f);
	return ok;
};

// Why the slot no longer describes this server, or "".  A side that is still
// empty (zones load after PutClientInServer) is not a difference: SV_MsApply
// asks again.
string() SV_MsStale =
{
	local float days;

	if (ms_mapcrc != "")
	if (infokey(world, "*mapcrc") != "")
	if (ms_mapcrc != infokey(world, "*mapcrc"))
		return "the map changed";
	if (ms_zonecrc != "")
	if (zone_crc != "")
	{
		if (ms_zonecrc != zone_crc)
			return "the zones changed";
		if (ms_zonerule != sprintf("%d %d %d", run_t_swept, run_t_hull, run_t_hulllive))
			return "the zone rules changed";
		if (fabs(ms_tickrate - run_t_tick) > 0.000001)
			return "the tick rate changed";
	}
	days = cvar("run_resume_days");
	if (days > 0)
	if (ms_day > 0)
	if (FS_DayNumOf(strftime(TRUE, "%Y%m%d")) - ms_day > days)
		return "it expired";
	return "";
};

/*
  Remove a slot.  A run that posted stages keeps its recording as evidence
  (Patch 360's rule): its rows are on the board.  `leaf` is the ms file that
  is present (ms.txt, or a claim); the meta must already be read.
*/
void(string dir, string leaf) SV_MsWipeDir =
{
	local string dst;

	if (ms_posts > 0)
	if (ms_rid != "")
	{
		dst = sprintf("data/evidence/%s/%s.rec", mapname, ms_rid);
		fremove(dst);
		frename(strcat(dir, "run.rec"), dst);
	}
	fremove(strcat(dir, "run.rec"));
	fremove(strcat(dir, "state.txt"));
	fremove(strcat(dir, leaf));
};

void(entity e, string leaf) SV_MsWipe =
{
	SV_MsWipeDir(sprintf("%s/save000/", SV_MsRoot(e)), leaf);
};

/*
===========================================================================
  The *resume key -- the client's HUD reads it (HUD_DrawResumeOffer)
    O <ticks> <seg> <segs> <track> <leg> <sessions>   on offer
    R <pct>                                           restoring the recording
    C <secs>                                          counting down
    A <sessions> <omitted> [<seg> <ticks>]...         resumed: the splits back
===========================================================================
*/
void(entity e, string v) SV_MsKeySet =
{
	forceinfokey(e, "*resume", v);
	e.run_ms_keyed = (v != "");
	e.run_ms_keyat = time + 3600;
};

/*
===========================================================================
  Park
===========================================================================
*/
float(entity e) SV_MsEligible =
{
	if (!cvar("run_resume"))
		return FALSE;
	if (e.run_t_state != TS_RUNNING)
		return FALSE;
	if (e.run_ms_phase)
		return FALSE;
	// A retry or cold load not yet answered by its session: a second pause
	// would be a file no reader accepts.  One packet wide.
	if (e.rec_rec_sesspend)
		return FALSE;
	if (SV_MsKey(e) == "")
		return FALSE;
	if (SV_TimerElapsed(e) < cvar("run_resume_min"))
		return FALSE;
	if (e.run_ms_sessions + 2 > cvar("run_resume_max"))
		return FALSE;
	return TRUE;
};

void(entity e) SV_MsCheck;

void(entity e, string why) SV_MsPark =
{
	local float ticks, bytes;
	local string mode, oldroot, key;
	local entity p;
	local filestream f;

	if (!SV_MsEligible(e))
		return;

	// An unconsumed slot wins: the fresh run was told it would not keep it.
	SV_MsAdopt(e);
	f = fopen(SV_MsPath(e, "ms.txt"), FILE_READ);
	if (f >= 0)
	{
		fclose(f);
		return;
	}

	SV_SaveLocRelease(e);
	if (e.rec_gh_on)
		SV_GhostSet(e, FALSE);
	// This session's evidence, folded the way a finish folds it.
	SV_TimerJournal(e);
	SV_TimerRuleset(e, FALSE);
	SV_TimerProfile(e, FALSE);

	ticks = SV_TimerTicks(e);
	ms_posts = 0;                       // a half-written slot's leftovers are not evidence
	SV_MsWipe(e, "ms.txt");
	mode = "none";
	bytes = -1;
	if (SV_RecLive(e))
	{
		SV_RecParkLine(e, why, ticks);
		if (e.rec_rec_stream)
		{
			bytes = fseek(e.rec_rec_fh);
			fclose(e.rec_rec_fh);
			e.rec_rec_fh = -1;
			e.rec_rec_stream = FALSE;
			if (frename(SV_RecPartPath(e), SV_MsPath(e, "run.rec")) == 0)
				mode = "stream";
			else
				fremove(SV_RecPartPath(e));
		}
		else
			mode = "buffer";            // SV_SaveWriteState writes the prefix
	}

	oldroot = sl_root;
	sl_root = SV_MsRoot(e);
	SV_SaveWriteState(e, 0, 0);
	sl_root = oldroot;
	SV_MsWriteMeta(e, ticks, why, mode, bytes);

	// The recording is in the slot now: nothing for the idle below to keep or drop.
	if (e.rec_rec_buf >= 1)
		buf_del(e.rec_rec_buf);
	e.rec_rec_buf = -1;
	SV_TimerIdle(e);

	dprint(sprintf("resume: parked %s's run on %s at %s (%s, recording %s)\n",
	               e.netname, mapname, SV_TimerString(ticks), why, mode));

	// A reconnect whose old connection had not timed out yet spawned before
	// this slot existed.
	key = SV_MsKey(e);
	p = world;
	while ((p = find(p, classname, "player")))
		if (p != e)
		if (!p.run_ms_phase)
		if (SV_MsKey(p) == key)
			SV_MsCheck(p);
};

/*
===========================================================================
  Offer
===========================================================================
*/
void(entity e) SV_MsCheck =
{
	local string why;

	e.run_ms_offer = FALSE;
	e.run_ms_warned = FALSE;
	if (!cvar("run_resume"))
		return;
	if (SV_MsKey(e) == "")
		return;
	SV_MsAdopt(e);
	if (!SV_MsReadMeta(SV_MsPath(e, "ms.txt")))
		return;
	why = SV_MsStale();
	if (why != "")
	{
		SV_MsWipe(e, "ms.txt");
		sprint(e, PRINT_CHAT, sprintf("^5resume:^7 your paused run here was dropped -- %s\n", why));
		return;
	}
	e.run_ms_offer = TRUE;
	SV_MsKeySet(e, sprintf("O %d %d %d %d %d %d", ms_ticks, ms_seg, ms_segs,
	                       ms_track, ms_leg, ms_sess));
	sprint(e, PRINT_CHAT, sprintf("^5resume:^7 your run here is paused at %s -- say "
	       "^5!resume^7 (or F2) to continue it, ^5!discard^7 to drop it\n",
	       SV_TimerString(ms_ticks)));
};

// PutClientInServer: the first spawn after a connect asks; a respawn during a
// restore (`kill`) gives the claim back.
void(entity e) SV_MsAbort;
void(entity e) SV_MsOffer =
{
	if (e.run_ms_phase)
		SV_MsAbort(e);
	if (!e.run_ms_want)
		return;
	e.run_ms_want = FALSE;
	SV_MsCheck(e);
};

void(entity e, string why) SV_MsDiscardOffer =
{
	if (!e.run_ms_offer)
		return;
	SV_MsAdopt(e);
	SV_MsReadMeta(SV_MsPath(e, "ms.txt"));
	SV_MsWipe(e, "ms.txt");
	e.run_ms_offer = FALSE;
	SV_MsKeySet(e, "");
	sprint(e, PRINT_CHAT, sprintf("^5resume:^7 paused run dropped (%s)\n", why));
};

/*
===========================================================================
  Accept -> restore -> countdown -> apply
===========================================================================
*/
float(entity e) SV_MsCopyBegin =
{
	e.rec_ms_src = fopen(SV_MsPath(e, "run.rec"), FILE_READ);
	if (e.rec_ms_src < 0)
		return FALSE;
	e.rec_ms_dst = fopen(SV_RecPartPath(e), FS_FILE_WRITESTREAM);
	if (e.rec_ms_dst < 0)
	{
		fclose(e.rec_ms_src);
		e.rec_ms_src = -1;
		return FALSE;
	}
	e.rec_ms_left = e.rec_ms_total;
	e.rec_ms_flagofs = -1;
	e.run_ms_pct = -1;
	rec_ms_owner = e;
	e.run_ms_phase = MS_COPY;
	return TRUE;
};

void(entity e) SV_MsCountdown =
{
	e.run_ms_phase = MS_COUNT;
	e.run_ms_until = time + cvar("run_resume_countdown");
	SV_MsKeySet(e, sprintf("C %g", cvar("run_resume_countdown")));
};

void(entity e) SV_MsAccept =
{
	local string claim;

	if (e.run_ms_phase)
		return;
	if (!e.run_ms_offer)
	{
		sprint(e, PRINT_HIGH, "^5resume:^7 no paused run on this map\n");
		return;
	}
	SV_MsAdopt(e);
	if (!SV_MsReadMeta(SV_MsPath(e, "ms.txt")))
	{
		e.run_ms_offer = FALSE;
		SV_MsKeySet(e, "");
		sprint(e, PRINT_HIGH, "^5resume:^7 the paused run is gone (another server resumed it?)\n");
		return;
	}
	// The claim.  POSIX rename is atomic, so a second lobby's fails here.
	claim = SV_MsPath(e, SV_MsClaimLeaf());
	fremove(claim);
	if (frename(SV_MsPath(e, "ms.txt"), claim) != 0)
	{
		e.run_ms_offer = FALSE;
		SV_MsKeySet(e, "");
		sprint(e, PRINT_HIGH, "^5resume:^7 another server took the paused run\n");
		return;
	}

	SV_TimerVoid(e, "resuming the paused run");
	SV_SaveLocRelease(e);
	if (e.rec_gh_on)
		SV_GhostSet(e, FALSE);

	e.run_ms_org = ms_org;
	setorigin(e, ms_org);
	e.velocity = '0 0 0';
	e.angles = ms_ang;
	e.v_angle = ms_ang;
	e.fixangle = TRUE;
	e.movetype = MOVETYPE_NONE;
	SV_TimerWarped(e);

	e.run_ms_readyby = time + 10;
	e.rec_ms_total = ms_lines;
	e.rec_ms_src = e.rec_ms_dst = -1;
	e.run_ms_norec = FALSE;
	if (!SV_RecEnabled())
		e.run_ms_norec = TRUE;
	if (ms_rec == "none")
		e.run_ms_norec = TRUE;
	if (ms_bytes > cvar("run_resume_recmb") * 1048576)
		e.run_ms_norec = TRUE;

	// The recording continues in the mode it was parked in.
	if (!e.run_ms_norec)
	if (ms_rec == "stream")
	{
		e.run_ms_phase = MS_WAIT;
		SV_MsKeySet(e, "R 0");
		sprint(e, PRINT_HIGH, "^5resume:^7 restoring the recording\n");
		return;
	}
	SV_MsCountdown(e);
};

void(entity e) SV_MsCopyStep =
{
	local float i, cap, pct;
	local string l;

	cap = cvar("run_resume_copylines");
	if (cap < 1)
		cap = 2000;
	for (i = 0; i < cap; i = i + 1)
	{
		if (e.rec_ms_left <= 0)
			break;
		l = fgets(e.rec_ms_src);
		// "" is EOF (the file has no blank lines); fgets caps a line at 4095.
		// Either way the file is not what ms.txt says: continue unrecorded.
		if (l == "" || strlen(l) >= 4095)
		{
			fclose(e.rec_ms_src);
			fclose(e.rec_ms_dst);
			e.rec_ms_src = e.rec_ms_dst = -1;
			fremove(SV_RecPartPath(e));
			rec_ms_owner = world;
			e.run_ms_norec = TRUE;
			sprint(e, PRINT_HIGH, "^3resume:^7 the recording could not be restored -- the run continues unrecorded\n");
			SV_MsCountdown(e);
			return;
		}
		// A file with a `pause` is v10; a stream could not rewrite line 0 in place.
		if (e.rec_ms_left == e.rec_ms_total)
		if (l == "FTESURF-REC 9")
			l = "FTESURF-REC 10";
		// The version line may have grown a byte: take the offset from this copy.
		if (substring(l, 0, 6) == "flags ")
			e.rec_ms_flagofs = fseek(e.rec_ms_dst);
		fputs(e.rec_ms_dst, l, "\n");
		e.rec_ms_left = e.rec_ms_left - 1;
	}
	pct = floor(10 * (e.rec_ms_total - e.rec_ms_left) / max(1, e.rec_ms_total)) * 10;
	if (pct != e.run_ms_pct)
	{
		e.run_ms_pct = pct;
		SV_MsKeySet(e, sprintf("R %d", pct));
	}
	if (e.rec_ms_left > 0)
		return;
	fclose(e.rec_ms_src);
	e.rec_ms_src = -1;
	rec_ms_owner = world;
	SV_MsCountdown(e);
};

// The recorder, continued: the stream from the copy, or the buffer from the slot.
void(entity e) SV_MsRecAttach =
{
	local float ok;
	local string oldroot;

	if (e.run_ms_norec)
	{
		if (e.rec_ms_dst >= 0)
		{
			fclose(e.rec_ms_dst);
			e.rec_ms_dst = -1;
			fremove(SV_RecPartPath(e));
		}
		return;
	}
	if (ms_rec == "stream")
	{
		if (e.rec_ms_dst < 0)
			return;
		e.rec_rec_fh = e.rec_ms_dst;
		e.rec_ms_dst = -1;
		e.rec_rec_stream = TRUE;
		e.rec_rec_buf = -1;
		e.rec_rec_lines = ms_lines;
		e.rec_rec_flagofs = e.rec_ms_flagofs;
		e.rec_rec_flagline = -1;
		e.rec_rec_n = ms_n;
		e.rec_rec_padn = ms_padn;
		e.rec_rec_cp = ms_cp;
		e.rec_rec_in = ms_in;
		e.rec_rec_warp = ms_warp;
		e.rec_rec_ride = ms_ride;
		e.rec_rec_pm = ms_pm;
		e.rec_rec_pe = ms_pe;
		e.rec_rec_portal = ms_portal;
		e.rec_rec_pinned = ms_pinned;
		e.rec_rec_pauses = ms_pauses;
		e.rec_rec_sess = ms_rsess;
		e.rec_rec_full = ms_full;
		if (e.rec_rec_pk < ms_pk)
			e.rec_rec_pk = ms_pk;
		// SV_RecRecount's latches, for a body it cannot read.
		e.rec_rec_bvset = FALSE;
		e.rec_rec_pcset = FALSE;
		e.rec_rec_epoch = 0;
		e.rec_rec_portalx = e.run_portalx;
		e.rec_rec_lastbc = e.run_boardcount;
		e.rec_rec_sesspend = 1 + e.rec_rec_pinned;
		e.rec_rec_serial = SV_RecNextSerial();
		e.rec_rec_leg = e.run_t_track * 100 + FS_LegOf(e.run_t_startseg, e.run_t_stagerun) + 1;
		e.run_t_flags = e.run_t_flags | TF_RECORDING;
	}
	else if (ms_rec == "buffer")
	{
		// Cold (serial -1 matches nothing): SV_RecRecount re-arms the open pause.
		oldroot = sl_root;
		sl_root = SV_MsRoot(e);
		ok = SV_RecRewind(e, SL_RecPath(0), ms_lines, -1, ms_n, ms_padn, ms_cp);
		sl_root = oldroot;
		if (!ok)
			return;
	}
	else
		return;
	e.rec_rec_posts = ms_posts;
	e.rec_rec_tag = RT_NONE;
	e.rec_rec_ticks = 0;
	e.rec_rec_saved = FALSE;
	e.rec_rec_bytes = -1;
	e.rec_rec_zseed = FALSE;
	if (e.rec_rec_rid != "")
		strunzone(e.rec_rec_rid);
	e.rec_rec_rid = "";
	if (ms_rid != "")
		e.rec_rec_rid = strzone(ms_rid);
};

// The splits back to the client (Timer_ResumeSeed), newest first, under the
// size an infokey value carries safely.
string(entity e) SV_MsSplitKey =
{
	local string s, pair;
	local float i, omit;

	s = "";
	omit = 0;
	for (i = FS_MAXSPLITS - 1; i >= 1; i = i - 1)
	{
		if (SV_TimerGetRunSplit(e, i) <= 0)
			continue;
		pair = sprintf(" %d %d", i, SV_TimerGetRunSplit(e, i));
		if (strlen(s) + strlen(pair) > 200)
			omit = omit + 1;
		else
			s = strcat(s, pair);
	}
	return sprintf("A %d %d%s", e.run_ms_sessions, omit, s);
};

void(entity e) SV_MsApply =
{
	local string why, oldroot, claim;
	local float ok, hold;

	// The CSQC reports and the zone table have to be in: without them the start
	// latches below read "broken" and the slot cannot be checked.
	if (time < e.run_ms_readyby)
	{
		hold = FALSE;
		if (!e.run_t_jev)
			hold = TRUE;
		if (!e.run_t_pev)
			hold = TRUE;
		if (zone_crc == "")
			hold = TRUE;
		if (hold)
		{
			e.run_ms_until = time + 0.25;
			return;
		}
	}

	claim = SV_MsPath(e, SV_MsClaimLeaf());
	if (!SV_MsReadMeta(claim))
	{
		SV_MsAbort(e);
		sprint(e, PRINT_HIGH, "^3resume:^7 the paused run's files are gone\n");
		return;
	}
	why = SV_MsStale();
	if (why == "")
	if (ms_zonecrc != "")
	if (zone_crc == "")
		why = "the zones did not load";
	if (why != "")
	{
		SV_MsAbort(e);
		SV_MsReadMeta(SV_MsPath(e, "ms.txt"));
		SV_MsWipe(e, "ms.txt");
		e.run_ms_offer = FALSE;
		SV_MsKeySet(e, "");
		sprint(e, PRINT_CHAT, sprintf("^5resume:^7 paused run dropped -- %s\n", why));
		return;
	}

	e.movetype = MOVETYPE_WALK;
	oldroot = sl_root;
	sl_root = SV_MsRoot(e);
	ok = SV_SaveApplyState(e, 0, 2);
	sl_root = oldroot;
	if (!ok || e.run_t_state != TS_RUNNING)
	{
		SV_MsAbort(e);
		sprint(e, PRINT_HIGH, "^3resume:^7 the paused run could not be applied\n");
		return;
	}

	e.run_ms_sessions = ms_sess + 1;
	e.run_t_flags = e.run_t_flags | TF_MULTISESSION;
	if (e.run_t_cheat)
		SV_TimerCheat(e);
	else if (SV_CheatLevel(e))
		SV_TimerCheat(e);
	// The start-style latches, as SV_TimerStart takes them: an unlock or a
	// profile flip inside this session is caught at the finish.
	e.run_t_rbreach = -1;
	e.run_t_pbad = -1;
	SV_TimerJournal(e);
	SV_TimerRuleset(e, TRUE);
	SV_TimerProfile(e, TRUE);
	SV_TimerMap(e);
	SV_TimerClock(e);

	SV_MsRecAttach(e);

	// The stage in progress spans the pause, so it never qualifies (run_st_ms);
	// a box exit from here starts a clean one.  Its base is the original tick.
	if (ms_stseg >= 0)
	{
		SV_StageOpen(e, ms_stseg, ms_sttick);
		e.run_st_armed = ms_starmed ? TRUE : FALSE;
		e.run_st_ms = TRUE;
	}
	e.run_leg_zone = ms_legzone;
	e.run_leg_track = ms_legtrack;
	e.run_leg_seg = ms_legseg;

	SV_SaveLocEvent(e, SLOP_RESUME, e.run_ms_sessions);
	SV_MsKeySet(e, SV_MsSplitKey(e));
	e.run_ms_keyat = time + 3;

	// The recording continues in this run, stage posts and all: nothing to keep.
	ms_posts = 0;
	SV_MsWipeDir(sprintf("%s/save000/", SV_MsRoot(e)), SV_MsClaimLeaf());
	e.run_ms_phase = MS_NONE;
	e.run_ms_offer = FALSE;
	sprint(e, PRINT_HIGH, sprintf("^5resume:^7 run resumed at %s -- session %g%s\n",
	       SV_TimerString(ms_ticks), e.run_ms_sessions + 1,
	       e.run_ms_norec ? " (unrecorded)" : ""));
};

// Give the claim back and stand the player up; the offer stands.
void(entity e) SV_MsAbort =
{
	local string claim;

	if (!e.run_ms_phase)
		return;
	if (e.rec_ms_src >= 0)
		fclose(e.rec_ms_src);
	if (e.rec_ms_dst >= 0)
	{
		fclose(e.rec_ms_dst);
		fremove(SV_RecPartPath(e));
	}
	e.rec_ms_src = e.rec_ms_dst = -1;
	if (rec_ms_owner == e)
		rec_ms_owner = world;
	claim = SV_MsPath(e, SV_MsClaimLeaf());
	fremove(SV_MsPath(e, "ms.txt"));
	frename(claim, SV_MsPath(e, "ms.txt"));
	e.movetype = MOVETYPE_WALK;
	e.run_ms_phase = MS_NONE;
	e.run_ms_offer = FALSE;
	SV_MsKeySet(e, "");
};

/*
===========================================================================
  Per frame, and the entry points
===========================================================================
*/
void(entity e) SV_MsFrame =
{
	local float grace;

	// The rotation hold (Lobby_Cycle) waits while any run is going.  A player who
	// is timing out sends no packets, stops refreshing this, and is parked.
	if (e.run_t_state == TS_RUNNING)
		lobby_cyc_runseen = time;

	if (e.run_ms_phase)
	{
		// Parked: no run can start under a restore in flight.
		e.movetype = MOVETYPE_NONE;
		e.velocity = '0 0 0';
		if (e.origin != e.run_ms_org)
		{
			setorigin(e, e.run_ms_org);
			SV_TimerWarped(e);
		}
		if (e.run_ms_phase == MS_WAIT)
		{
			if (rec_ms_owner == world)
			if (!SV_MsCopyBegin(e))
			{
				e.run_ms_norec = TRUE;
				SV_MsCountdown(e);
			}
		}
		else if (e.run_ms_phase == MS_COPY)
			SV_MsCopyStep(e);
		else if (time >= e.run_ms_until)
			SV_MsApply(e);
		return;
	}

	// A fresh run with an offer standing: warned once, then it wins.
	if (e.run_ms_offer)
	{
		grace = cvar("run_resume_grace");
		if (e.run_t_state == TS_RUNNING)
		{
			if (!e.run_ms_warned)
			{
				e.run_ms_warned = TRUE;
				sprint(e, PRINT_HIGH, sprintf("^3resume:^7 your paused run is dropped %g s "
				       "into this one -- ^5!resume^7 goes back to it\n", grace));
			}
			if (SV_TimerElapsed(e) >= grace)
				SV_MsDiscardOffer(e, "a new run went on");
		}
		else if (e.run_t_state == TS_FINISHED)
		{
			if (e.run_ms_warned)
				SV_MsDiscardOffer(e, "a new run finished");
		}
	}
	else if (e.run_ms_keyed)
	{
		if (time > e.run_ms_keyat)
			SV_MsKeySet(e, "");
	}
};

void(entity e) SV_MsConnect =
{
	e.run_ms_want = TRUE;
	e.run_ms_offer = FALSE;
	e.run_ms_warned = FALSE;
	e.run_ms_phase = MS_NONE;
	e.rec_ms_src = e.rec_ms_dst = -1;
	SV_MsKeySet(e, "");
};

void(entity e) SV_MsDisconnect =
{
	if (e.run_ms_phase)
		SV_MsAbort(e);
	else
		SV_MsPark(e, "drop");
};

// sv_main.qc's SV_Shutdown: quit, disconnect, every map change -- but not a
// `retry`, whose own slot carries the run across its map_restart.
void() SV_MsShutdown =
{
	local entity p;

	if (rec_retry_sent)
		return;
	p = world;
	while ((p = find(p, classname, "player")))
	{
		if (p.run_ms_phase)
			SV_MsAbort(p);
		else
			SV_MsPark(p, lobby_cyc_moving ? "rotate" : "server");
	}
};

void(entity e) SV_MsDiscardCmd =
{
	if (e.run_ms_phase)
		return;
	if (!e.run_ms_offer)
	{
		sprint(e, PRINT_HIGH, "^5resume:^7 no paused run on this map\n");
		return;
	}
	SV_MsDiscardOffer(e, "you dropped it");
};

// worldspawn: slots on this map past run_resume_days.
void() SV_MsSweep =
{
	local float h, n, i, days, cut;
	local string fn, dir, leaf;

	days = cvar("run_resume_days");
	if (days <= 0)
		return;
	h = search_begin(sprintf("data/resume/%s/*/save000/ms*.txt", mapname), FS_NAMESORT, TRUE);
	if (h < 0)
		return;
	n = search_getsize(h);
	for (i = 0; i < n; i = i + 1)
	{
		fn = search_getfilename(h, i);
		if (!SV_MsReadMeta(fn))
			continue;
		if (ms_day <= 0)
			continue;
		if (FS_DayNumOf(strftime(TRUE, "%Y%m%d")) - ms_day <= days)
			continue;
		cut = strlen(fn) - 1;
		while (cut >= 0 && str2chr(fn, cut) != 47)     // '/'
			cut = cut - 1;
		dir = substring(fn, 0, cut + 1);
		leaf = substring(fn, cut + 1, strlen(fn) - cut - 1);
		SV_MsWipeDir(dir, leaf);
	}
	search_end(h);
};
