/*
  cl_raceghost.qc -- the comparative ghost.  Patch 746.

  A body that runs a recording beside you on your own clock: your PB for the
  run or stage you are on (data/runs, built into line slots LN_S_GHOST and
  LN_S_GHR by the board lines' job) and the first hud_ghost_lines ticked board
  lines.  It starts when you leave the start box, or with hud_ghost_sync 1 again
  at every stage's box, plus hud_ghost_offset.  hud_ghost 2 highlights the
  ghost's place on its line instead of drawing a body.  A picture only: nothing
  here is sent, and the `ghost` command is the unrelated freecam (cl_ghost.qc).

  Which recording goes with which run follows LineGraph_LiveAlign: a stage's
  line from the stage base, a whole run's from the run's start.  A whole-run
  line asked for a stage is cut at the moment it left that stage's box, found
  from its own samples and the zone file (RG_StageScan).

  Patch 749: the body ducks and faces as the recording's view did (ln_pose), and
  carries a name tag drawn like a player's (RG_Tags, hud_ghost_names).
*/

#define RG_MAX     10           // bodies: the two PB slots and eight lines
#define RG_STG     32           // stage boxes a slot remembers leaving (FS_MAXSPLITS is 24)
#define RG_ZONES   96           // start and stage regions of a track the scan tests
#define RG_SCAN    2048         // samples a frame the stage scan reads
#define RG_HOLD    1.5          // seconds a finished ghost stands at its end
#define RGP_NONE   0
#define RGP_QUEUE  1
#define RGP_BUILD  2
#define RGP_ON     3
#define RGP_FAIL   4

float  rg_cv;                   // hud_ghost: 0 off, 1 body, 2 highlight, 3 both
float  rg_now;                  // the drawn body's run clock; -1 no run
float  rg_lticks, rg_tickat;    // the clock stat, and cltime it last changed
float  rg_lead;                 // what rg_now adds to the stat
float  rg_track, rg_seg, rg_legnow, rg_runleg, rg_base, rg_armed;
float  rg_n;                    // ghosts this frame
float  rg_slot[RG_MAX];
float  rg_t[RG_MAX];            // its run clock
vector rg_pos[RG_MAX];
float  rg_yaw[RG_MAX];
float  rg_duck[RG_MAX];
float  rg_ed[RG_MAX];           // the model rg_ent[g] has: 0 none, 1 standing, 2 ducked
vector rg_col[RG_MAX];
float  rg_end[RG_MAX];          // 1 past its run's end, -1 before its start
float  rg_anc[RG_MAX];          // the slot's clock at the anchor (RG_Anchor)
entity rg_ent[RG_MAX];
vector rg_gp;                   // RG_At's answer
float  rg_gyaw, rg_gduck, rg_gend, rg_gi;
float  rg_shd, rg_shb;          // the dither and blend materials

// The two PB slots: [0] LN_S_GHOST a stage's, [1] LN_S_GHR the whole run's.
string rg_pbpath[2];
float  rg_pbst[2], rg_pbleg[2], rg_pbtrack[2], rg_pbmap;
float  rg_mapgen, rg_rescan, rg_laststate;

// Per slot: when its body left each stage's box (Patch 746, RG_StageScan).
float  *rg_stg;
float  *rg_stggen;
float  *rg_stgi;
float  *rg_stgin;
float  *rg_stgk;
float  *rg_stgz;                // the zones its table was read against (RG_ZoneSig)
float  *rg_slgen;               // a board line's build, and the map it was built on
string *rg_slmap;
float  rg_zl[RG_ZONES];         // RG_StageScan's regions
float  rg_nz;

void() RG_RegisterCvars =
{
	local float s;

	registercvar("hud_ghost",        "1",    CVAR_ARCHIVE);
	registercvar("hud_ghost_sync",   "0",    CVAR_ARCHIVE);
	registercvar("hud_ghost_pb",     "1",    CVAR_ARCHIVE);
	registercvar("hud_ghost_lines",  "4",    CVAR_ARCHIVE);
	registercvar("hud_ghost_offset", "0",    CVAR_ARCHIVE);
	registercvar("hud_ghost_alpha",  "0.55", CVAR_ARCHIVE);
	registercvar("hud_ghost_dither", "1",    CVAR_ARCHIVE);
	registercvar("hud_ghost_near",   "96",   CVAR_ARCHIVE);
	registercvar("hud_ghost_names",  "1",    CVAR_ARCHIVE);
	registercommand("raceghost");
	rg_stg    = memalloc(sizeof(float) * LN_SLOTS * RG_STG);
	rg_stggen = memalloc(sizeof(float) * LN_SLOTS);
	rg_stgi   = memalloc(sizeof(float) * LN_SLOTS);
	rg_stgin  = memalloc(sizeof(float) * LN_SLOTS);
	rg_stgk   = memalloc(sizeof(float) * LN_SLOTS);
	rg_stgz   = memalloc(sizeof(float) * LN_SLOTS);
	rg_slgen  = memalloc(sizeof(float) * LN_SLOTS);
	rg_slmap  = memalloc(sizeof(string) * LN_SLOTS);
	for (s = 0; s < LN_SLOTS; s = s + 1)
		rg_stggen[s] = rg_slgen[s] = -1;
};

/*
  The dither material is cl_playerfade.qc's shape: opaque and depth-writing, a
  pixel kept where the coverage beats a fixed spatial noise.  The body is its
  colour (colormod), lit between 0.6 and 1 so it reads on an unlit ramp, a
  little of the texture in it and a rim at its silhouette, and fades out within
  hud_ghost_near of the eye.  The blend one is the same picture at that alpha.
  (The first cut lit it at texture brightness: a dark olive block on Kitsune.)
*/
float() RG_ShaderDither =
{
	return shaderforname("ftesurf/raceghost_d",
		"{\nglslprogram\n{\n"
		"!!ver 100 150\n"
		"!!permu SKELETAL\n"
		"!!permu FRAMEBLEND\n"
		"!!permu FOG\n"
		"!!samps diffuse\n"
		"!!cvarf hud_ghost_alpha=0.55\n"
		"!!cvarf hud_ghost_near=96\n"
		"#include \"sys/defs.h\"\n"
		"#include \"sys/fog.h\"\n"
		"varying vec2 tc;\n"
		"varying vec3 light;\n"
		"varying float rim;\n"
		"#ifdef VERTEX_SHADER\n"
		"#include \"sys/skeletal.h\"\n"
		"void main(void)\n{\n"
		" vec3 normal, tangent, bitangent, position;\n"
		" gl_Position = skeletaltransform_wnst(position, normal, tangent, bitangent);\n"
		" tc = v_texcoord;\n"
		" float diffuse = dot(normalize(normal), e_light_dir);\n"
		" if (diffuse < 0.0) diffuse *= 13.0/44.0;\n"
		" light = e_light_ambient + e_light_mul * diffuse;\n"
		" rim = 1.0 - abs(dot(normalize(normal), normalize(e_eyepos - position)));\n"
		"}\n#endif\n"
		"#ifdef FRAGMENT_SHADER\n"
		"uniform float cvar_hud_ghost_alpha;\n"
		"uniform float cvar_hud_ghost_near;\n"
		"float coverageNoise(vec2 p)\n{\n"
		" return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));\n"
		"}\n"
		"void main(void)\n{\n"
		" float nearDist = max(0.0, cvar_hud_ghost_near);\n"
		" float cover = clamp(cvar_hud_ghost_alpha, 0.0, 1.0);\n"
		" if (nearDist > 0.0) cover *= smoothstep(nearDist * 0.5, nearDist, length(e_eyepos - vec3(0.0, 0.0, 31.0)));\n"
		" if (cover <= coverageNoise(floor(gl_FragCoord.xy))) discard;\n"
		" vec4 col = texture2D(s_diffuse, tc);\n"
		" float lum = dot(col.rgb, vec3(0.30, 0.59, 0.11));\n"
		" float shade = mix(0.6, 1.0, clamp(dot(light, vec3(0.333)), 0.0, 1.0));\n"
		" col.rgb = e_colourident.rgb * (shade * (0.8 + 0.2 * lum) + 0.6 * rim * rim);\n"
		" gl_FragColor = fog4(vec4(col.rgb, 1.0));\n"
		"}\n#endif\n"
		"}\ndiffusemap models/player\n"
		"{\nmap models/player\nrgbgen lightingdiffuse\n}\n}\n");
};

float() RG_ShaderBlend =
{
	return shaderforname("ftesurf/raceghost_b",
		"{\nglslprogram\n{\n"
		"!!ver 100 150\n"
		"!!permu SKELETAL\n"
		"!!permu FRAMEBLEND\n"
		"!!permu FOG\n"
		"!!samps diffuse\n"
		"!!cvarf hud_ghost_alpha=0.55\n"
		"!!cvarf hud_ghost_near=96\n"
		"#include \"sys/defs.h\"\n"
		"#include \"sys/fog.h\"\n"
		"varying vec2 tc;\n"
		"varying vec3 light;\n"
		"varying float rim;\n"
		"#ifdef VERTEX_SHADER\n"
		"#include \"sys/skeletal.h\"\n"
		"void main(void)\n{\n"
		" vec3 normal, tangent, bitangent, position;\n"
		" gl_Position = skeletaltransform_wnst(position, normal, tangent, bitangent);\n"
		" tc = v_texcoord;\n"
		" float diffuse = dot(normalize(normal), e_light_dir);\n"
		" if (diffuse < 0.0) diffuse *= 13.0/44.0;\n"
		" light = e_light_ambient + e_light_mul * diffuse;\n"
		" rim = 1.0 - abs(dot(normalize(normal), normalize(e_eyepos - position)));\n"
		"}\n#endif\n"
		"#ifdef FRAGMENT_SHADER\n"
		"uniform float cvar_hud_ghost_alpha;\n"
		"uniform float cvar_hud_ghost_near;\n"
		"void main(void)\n{\n"
		" float nearDist = max(0.0, cvar_hud_ghost_near);\n"
		" float cover = clamp(cvar_hud_ghost_alpha, 0.0, 1.0);\n"
		" if (nearDist > 0.0) cover *= smoothstep(nearDist * 0.5, nearDist, length(e_eyepos - vec3(0.0, 0.0, 31.0)));\n"
		" vec4 col = texture2D(s_diffuse, tc);\n"
		" float lum = dot(col.rgb, vec3(0.30, 0.59, 0.11));\n"
		" float shade = mix(0.6, 1.0, clamp(dot(light, vec3(0.333)), 0.0, 1.0));\n"
		" col.rgb = e_colourident.rgb * (shade * (0.8 + 0.2 * lum) + 0.6 * rim * rim);\n"
		" gl_FragColor = fog4(vec4(col.rgb, cover));\n"
		"}\n#endif\n"
		"}\ndiffusemap models/player\n"
		"{\nmap models/player\nblendfunc blend\nrgbgen lightingdiffuse\n}\n}\n");
};

void(float i) RG_PBClear =
{
	local float s;

	s = i ? LN_S_GHR : LN_S_GHOST;
	if (wt_lj_phase)
	if (wt_lj_slot == s)
		Watch_LineJobStop();
	if (rg_pbpath[i]) strunzone(rg_pbpath[i]);
	rg_pbpath[i] = __NULL__;
	rg_pbst[i] = RGP_NONE;
	Line_Clear(s);
};

// A map change: the slots hold the last map's runs (Trail_Reset's reason).
void() RG_Reset =
{
	RG_PBClear(0);
	RG_PBClear(1);
	rg_pbleg[0] = rg_pbleg[1] = rg_pbtrack[0] = rg_pbtrack[1] = -1;
	rg_mapgen = rg_mapgen + 1;
	rg_n = 0;
};

/*
  The fastest `_pb` file of a leg.  FS_RunDir's names lead with the zero-padded
  tick count, so FS_NAMESORT puts the PB first; a lobby's header-only `_lobby`
  is another tag and never matches.
*/
string(float track, float leg) RG_PBFind =
{
	local float h;
	local string f;

	h = search_begin(strcat(FS_RunDir(serverkey("map"), track, leg), "*_pb.rec"), FS_NAMESORT, TRUE);
	if (h < 0)
		return "";
	f = "";
	if (search_getsize(h) > 0)
		f = search_getfilename(h, 0);
	search_end(h);
	return f;
};

// PB slot i should hold leg `leg` of `track` (-1: nothing, -2: whatever it holds).
// Looked for again on a change of leg, of map, or after a run ended (a new PB has
// just been written).
void(float i, float track, float leg) RG_PBWant =
{
	local string f;

	if (leg == -2)
		return;
	if (leg < 0)
	{
		if (rg_pbst[i] != RGP_NONE)
			RG_PBClear(i);
		rg_pbleg[i] = -1;
		return;
	}
	if (leg == rg_pbleg[i] && track == rg_pbtrack[i] && rg_pbmap == rg_mapgen && !rg_rescan)
		return;
	rg_pbleg[i] = leg;
	rg_pbtrack[i] = track;
	f = RG_PBFind(track, leg);
	if (f == "")
	{
		RG_PBClear(i);
		return;
	}
	if (rg_pbpath[i])
	if (!strcmp(rg_pbpath[i], f))
	if (rg_pbst[i] != RGP_FAIL)
		return;                     // that file, held or on its way
	RG_PBClear(i);
	rg_pbpath[i] = strzone(f);
	rg_pbst[i] = RGP_QUEUE;
};

// From Scores_LinesFrame when no line job runs: start a queued PB's.  Before the
// board's own queue, because a ghost is wanted the moment its run starts.
float() RG_JobStart =
{
	local float i, s;

	for (i = 1; i >= 0; i = i - 1)
		if (rg_pbst[i] == RGP_QUEUE)
		{
			s = i ? LN_S_GHR : LN_S_GHOST;
			rg_pbst[i] = Watch_LineJobStart(s, rg_pbpath[i], rg_pbleg[i]) ? RGP_BUILD : RGP_FAIL;
			rg_stggen[s] = -1;
			return TRUE;
		}
	return FALSE;
};

void(float k) RG_JobDone =
{
	local float i;

	i = (wt_lj_slot == LN_S_GHR) ? 1 : 0;
	if (rg_pbst[i] != RGP_BUILD)
		return;
	rg_pbst[i] = (k > 0) ? RGP_ON : RGP_FAIL;
	rg_stggen[wt_lj_slot] = -1;
	print(sprintf("raceghost: %s PB %s (%g points)\n", i ? "run" : "stage",
	              (k > 0) ? "ready" : "failed", ln_n[wt_lj_slot]));
};

// The zone tables, as a number that moves when they are loaded or edited.
float() RG_ZoneSig =
{
	return zone_count * 4096 + zone_ptcount;
};

/*
  Where slot s's body left each stage's box: rg_stg[s * RG_STG + seg], the clock of
  its first sample outside, -1 never.  Only the box of the furthest stage reached
  is written, so a fail back into the stage's own box moves its start to the try
  that went on, and an earlier box passed again does not.  RG_SCAN samples a frame,
  from RG_Frame only (one slot a frame); RG_StageAt answers -1 until it is done.
*/
void(float s) RG_StageScan =
{
	local float b, i, e, z, k, track;
	local vector p;

	if (rg_stggen[s] != ln_graphgen[s] || rg_stgz[s] != RG_ZoneSig())
	{
		rg_stggen[s] = ln_graphgen[s];
		rg_stgz[s] = RG_ZoneSig();
		rg_stgi[s] = ln_ia[s];
		rg_stgin[s] = -1;
		rg_stgk[s] = -1;
		for (k = 0; k < RG_STG; k = k + 1)
			rg_stg[s * RG_STG + k] = -1;
	}
	if (rg_stgi[s] > ln_ib[s])
		return;
	if (zone_count <= 0)
		return;                     // no zones yet: nothing read, so nothing done
	track = (ln_track[s] >= 0) ? ln_track[s] : rg_track;
	rg_nz = 0;
	for (z = 0; z < zone_count; z = z + 1)
		if (zone_track[z] == track)
		if (zone_type[z] == ZONE_START || zone_type[z] == ZONE_STAGE)
		if (rg_nz < RG_ZONES)
		{
			rg_zl[rg_nz] = z;
			rg_nz = rg_nz + 1;
		}
	b = LN_B(s);
	e = min(ln_ib[s], rg_stgi[s] + RG_SCAN - 1);
	for (i = rg_stgi[s]; i <= e; i = i + 1)
	{
		p = ln_pos[b + i];
		k = -1;
		for (z = 0; z < rg_nz; z = z + 1)
			if (Zone_PointInside(rg_zl[z], p))
			{
				k = (zone_type[rg_zl[z]] == ZONE_START) ? 0 : zone_seg[rg_zl[z]];
				break;
			}
		if (k >= 0)
		{
			rg_stgk[s] = max(rg_stgk[s], k);
			rg_stgin[s] = k;
		}
		else if (rg_stgin[s] >= 0)
		{
			k = rg_stgin[s];
			if (k >= rg_stgk[s])
			if (k < RG_STG)
				rg_stg[s * RG_STG + k] = ln_t[b + i];
			rg_stgin[s] = -1;
		}
	}
	rg_stgi[s] = e + 1;
};

float(float s) RG_StageDone =
{
	return (rg_stggen[s] == ln_graphgen[s] && rg_stgz[s] == RG_ZoneSig() && rg_stgi[s] > ln_ib[s]);
};

float(float s, float seg) RG_StageAt =
{
	if (seg <= 0)
		return ln_start[s];         // a whole run's clock starts as it leaves the start
	if (seg >= RG_STG)
		return -1;
	if (!RG_StageDone(s))
		return -1;                  // still reading
	return rg_stg[s * RG_STG + seg];
};

/*
  The run clock of the body you see, seconds; -1 when no run is on.  The stat
  describes the command frame the server last acknowledged (Patch 611's
  Trail_Pair), which is a round trip behind the predicted body: the wall time
  since that frame was predicted is added.  On a local server the frame is the
  current one, and the time since the stat moved, at most a tick, is added.
*/
float() RG_Clock =
{
	local float tick, ticks, lead, n, p, c;

	if (ui_rw_on)
		return ui_rw_time;          // the rewind cursor (display only)
	if (getstatf(STAT_FS_TIMERSTATE) != TS_RUNNING)
		return -1;
	tick = Timer_Tick();
	ticks = getstatf(STAT_FS_TIMERTICKS);
	if (ticks != rg_lticks)
	{
		rg_lticks = ticks;
		rg_tickat = cltime;
	}
	rg_lead = 0;
	if (getstatf(STAT_FS_TIMERFLAGS) & TF_FROZEN)
		return ticks * tick;
	lead = -1;
	n = clientcommandframe;
	p = servercommandframe + TR_LEAD;
	if (tr_kf)
	if (p < n)
	if (n - p < TR_RING - 3)
	if (!cvar("cl_nopred"))
	{
		c = (p & (TR_RING - 1)) * 4;
		if (tr_kf[c] == p)
			lead = cltime - tr_kf[c + 1];
	}
	if (lead < 0)
		lead = min(cltime - rg_tickat, tick);
	rg_lead = bound(0, lead, 0.5);
	return ticks * tick + rg_lead;
};

// Slot s at run clock t: rg_gp, rg_gyaw and rg_gduck (its view's, Patch 749), rg_gend.
void(float s, float t) RG_At =
{
	local float b, ia, ib, i, f, p0, p1, d0, d1;

	b  = LN_B(s);
	ia = ln_ia[s];
	ib = ln_ib[s];
	i  = Line_Find(s, t);
	rg_gend = 0;
	f = 1;
	if (i <= ia)
	{
		i = ia;
		rg_gp = ln_pos[b + ia];
		if (t < ln_t[b + ia])
			rg_gend = -1;
	}
	else if (i > ib)
	{
		i = ib;
		rg_gp = ln_pos[b + ib];
		rg_gend = 1;
	}
	else
	{
		f = ln_t[b + i] - ln_t[b + i - 1];
		f = (f > 0) ? (t - ln_t[b + i - 1]) / f : 1;
		if (ln_brk[b + i])
			f = (f < 0.5) ? 0 : 1;  // a teleport: no slide across it
		rg_gp = ln_pos[b + i - 1] + (ln_pos[b + i] - ln_pos[b + i - 1]) * f;
	}
	rg_gi = i;
	p1 = ln_pose[b + i];
	p0 = (f < 1) ? ln_pose[b + i - 1] : p1;
	d0 = (p0 >= LN_POSE_DUCK);
	d1 = (p1 >= LN_POSE_DUCK);
	p0 = p0 - d0 * LN_POSE_DUCK;
	p1 = p1 - d1 * LN_POSE_DUCK;
	p1 = p1 - p0;
	if (p1 > 180)
		p1 = p1 - 360;
	else if (p1 < -180)
		p1 = p1 + 360;
	rg_gyaw = p0 + p1 * f;
	rg_gduck = (f < 0.5) ? d0 : d1;
};

/*
  The clock slot c runs at against yours, or -1 for none: a stage's recording from
  the stage base, a whole run's from the start.  M is your clock at the anchor and
  A the slot's, so the ghost is at A + (rg_now - M) + hud_ghost_offset.
*/
float rg_am;
float(float c) RG_Anchor =
{
	local float legc, leg;

	if (!ln_on[c] || ln_ib[c] <= ln_ia[c])
		return -1;
	if (ln_track[c] >= 0)
	if (ln_track[c] != rg_track)
		return -1;
	legc = ln_leg[c];
	rg_am = 0;
	// A rewind's cursor is on the run's clock: the stage in play now says nothing of it.
	if (cvar("hud_ghost_sync") && rg_legnow > 0 && !ui_rw_on)
	{
		if (rg_armed)
			return -1;              // in the box: this stage has not started
		rg_am = rg_base;
		leg = rg_legnow;
	}
	else
		leg = (rg_runleg > 0) ? rg_runleg : 0;
	if (legc > 0)
		return (legc == leg) ? ln_start[c] : -1;
	return RG_StageAt(c, leg - 1);
};

// Slot c as a ghost, if a slot is free and it runs here; FALSE when it does not.
float(float c, vector col) RG_Add =
{
	local float a, t;

	if (rg_n >= RG_MAX)
		return FALSE;
	a = RG_Anchor(c);
	if (a < 0)
		return FALSE;
	// A negative offset holds it where its clock starts until it is due.
	t = max(a, a + (rg_now - rg_am) + cvar("hud_ghost_offset"));
	RG_At(c, t);
	if (rg_gend > 0)
	if (t - ln_t[LN_B(c) + ln_ib[c]] > RG_HOLD)
		return TRUE;                // finished a while ago: still this run's ghost
	rg_slot[rg_n] = c;
	rg_t[rg_n] = t;
	rg_pos[rg_n] = rg_gp;
	rg_yaw[rg_n] = rg_gyaw;
	rg_duck[rg_n] = rg_gduck;
	rg_end[rg_n] = rg_gend;
	rg_anc[rg_n] = a;
	if (col == '0 0 0')
		col = ln_col[LN_B(c) + rg_gi];
	if (col == '0 0 0')
		col = '0.55 0.85 1.00';     // no drawer has painted the line this map
	rg_col[rg_n] = col;
	rg_n = rg_n + 1;
	return TRUE;
};

// Before clearscene, after Trail_Frame (whose kept frames RG_Clock reads).
void() RG_Frame =
{
	local float st, i, k, lines, s, leg, sync, had;
	local string pbr, mp;

	rg_n = 0;
	rg_cv = cvar("hud_ghost");
	st = getstatf(STAT_FS_TIMERSTATE);
	if (st != rg_laststate)
	{
		if (rg_laststate == TS_RUNNING)
			rg_rescan = TRUE;       // a run ended: its PB may be new
		rg_laststate = st;
	}
	if (!rg_cv)
		return;

	rg_track  = getstatf(STAT_FS_TIMERTRACK);
	rg_seg    = getstatf(STAT_FS_TIMERSEG);
	rg_legnow = (getstatf(STAT_FS_TIMERSEGS) > 1) ? rg_seg + 1 : 0;
	// RUNLEG is track * 100 + leg + 1 while a run is open.  SV_RecOpen sets it for
	// every run, one that is not written included (measured with rec_enable 0).
	rg_runleg = getstatf(STAT_FS_RUNLEG);
	rg_runleg = (rg_runleg > 0) ? rg_runleg - floor(rg_runleg / 100) * 100 - 1 : -1;
	rg_base   = getstatf(STAT_FS_STAGEBASE) * Timer_Tick();
	rg_armed  = (getstatf(STAT_FS_STAGEST) & SF_ARMED) ? TRUE : FALSE;

	/*
	  The PBs: the run's whenever asked, and a stage's for a stage run or a stage
	  start.  Between attempts (no run open: RUNLEG is 0 from a discarded run until
	  the next leaves its box) the stage's is kept, or loaded already while you stand
	  in a stage's box, whose run is the next; it is not cleared and read again for
	  every attempt (the review).  No zones yet: nothing is decided.
	*/
	sync = cvar("hud_ghost_sync");
	if (!cvar("hud_ghost_pb"))
	{
		RG_PBWant(0, 0, -1);
		RG_PBWant(1, 0, -1);
	}
	else if (zone_count > 0)
	{
		RG_PBWant(1, rg_track, 0);
		leg = -2;
		if (sync)
			leg = (rg_legnow > 0) ? rg_legnow : -1;
		else if (rg_runleg > 0)
			leg = rg_runleg;
		else if (rg_runleg == 0)
			leg = -1;
		else if (st == TS_ARMED && rg_legnow > 1)
			leg = rg_legnow;
		RG_PBWant(0, rg_track, leg);
		rg_pbmap = rg_mapgen;
		rg_rescan = FALSE;
	}

	/*
	  The stage tables, in the background once a later stage is in play: standing in
	  its box is long enough (measured: no ghost 0.02 s into a stage run when the table
	  was begun only at its start).  One unfinished slot a frame, RG_SCAN samples.
	*/
	lines = cvar("hud_ghost_lines");
	if (sync || rg_legnow > 1)
	{
		s = -1;
		if (rg_pbst[1] == RGP_ON)
		if (!RG_StageDone(LN_S_GHR))
			s = LN_S_GHR;
		for (i = 0; i < SB_LNMAX && s < 0 && lines > 0; i = i + 1)
			if (sb_ln_st[i] == SBL_ON)
			if (ln_leg[LN_BOARDSLOT(i)] <= 0)
			if (!RG_StageDone(LN_BOARDSLOT(i)))
				s = LN_BOARDSLOT(i);
		if (s >= 0)
			RG_StageScan(s);
	}

	rg_now = RG_Clock();
	if (rg_now < 0 || rec_wt_on || Spec_Active())
		return;

	// A stage's own PB first; the whole run's only where that is not this run's
	// ghost (drawn, or finished and gone: the review's whole-run pop-in) or on its
	// way (a swap at the stage's start would jump).
	had = FALSE;
	pbr = "";
	if (rg_pbst[0] == RGP_ON)
		had = RG_Add(LN_S_GHOST, LN_GHOSTCOL);
	if (had)
	{
		if (rg_pbpath[0])
			pbr = rg_pbpath[0];
	}
	else if (rg_pbst[1] == RGP_ON)
	if (rg_pbst[0] != RGP_QUEUE && rg_pbst[0] != RGP_BUILD)
	if (RG_Add(LN_S_GHR, LN_GHOSTCOL))
	if (rg_pbpath[1])
		pbr = rg_pbpath[1];

	// The first hud_ghost_lines ticked lines that run here.  A line is stamped with
	// the map it was built on: a ticked line can outlive a map change, and on another
	// map its track 0 is somewhere else (the review).
	mp = serverkey("map");
	k = 0;
	for (i = 0; i < SB_LNMAX && k < lines; i = i + 1)
		if (sb_ln_st[i] == SBL_ON)
		{
			s = LN_BOARDSLOT(i);
			if (rg_slgen[s] != ln_graphgen[s])
			{
				rg_slgen[s] = ln_graphgen[s];
				if (rg_slmap[s]) strunzone(rg_slmap[s]);
				rg_slmap[s] = strzone(mp);
			}
			if (strcmp(rg_slmap[s], mp))
				continue;
			if (pbr != "")
			if (sb_ln_path[i])
			if (!strcmp(sb_ln_path[i], pbr))
				continue;           // your PB ticked as well: one ghost of it
			if (RG_Add(s, '0 0 0'))
				k = k + 1;
		}
};

// Before renderscene: the bodies.
void() RG_DrawBodies =
{
	local float g, dither, m;
	local entity e;

	if (!(rg_cv & 1) || rg_n < 1)
		return;
	dither = cvar("hud_ghost_dither");
	if (dither && !rg_shd)
		rg_shd = RG_ShaderDither();
	if (!dither && !rg_shb)
		rg_shb = RG_ShaderBlend();
	for (g = 0; g < rg_n; g = g + 1)
	{
		e = rg_ent[g];
		if (!e)
		{
			e = spawn();
			rg_ent[g] = e;
		}
		m = rg_duck[g] ? 2 : 1;
		if (rg_ed[g] != m)
		{
			rg_ed[g] = m;
			setmodel(e, (m == 2) ? "models/player_duck.iqm" : "models/player.iqm");
		}
		setorigin(e, rg_pos[g]);
		e.angles = [0, rg_yaw[g], 0];
		e.colormod = rg_col[g];
		e.glowmod = '0.032 0.032 0.032';
		e.forceshader = dither ? rg_shd : rg_shb;
		addentity(e);
	}
};

// Before renderscene, as Trail_Pin: the 2D pass's projection.
void() RG_Pin =
{
	if (!(rg_cv & 2) || rg_n < 1)
		return;
	makevectors(getproperty(VF_ANGLES));
	project(getproperty(VF_ORIGIN) + v_forward * 256);
};

// After renderscene, beside the other lines: the stretch each ghost has just run.
void() RG_DrawLines =
{
	local float g, s;

	if (!(rg_cv & 2) || rg_n < 1)
		return;
	Line_ViewFrame();
	ln_nomk = TRUE;
	ln_pxover = max(4, 3 * cvar("hud_watch_path_px"));
	for (g = 0; g < rg_n; g = g + 1)
	{
		s = rg_slot[g];
		Line_Window(rg_t[g] - 0.6, rg_t[g] + 0.06);
		Line_Draw(s, rg_t[g], rg_pos[g], 0, 1);
		Line_Square(rg_pos[g] + '0 0 36', rg_col[g], 1);
	}
	Line_WindowOff();
	ln_nomk = FALSE;
	ln_pxover = 0;
};

/*
  Patch 749: each ghost's name over its head, as PlayerLabels_Draw draws a player's
  (its picture, the name fading out past 256 u, nothing past hud_playerlabels_far
  or behind a wall), after the world's labels.  Your PB says so.
*/
float rg_tagn;                  // drawn last frame (`raceghost`)
float rg_tagd[RG_MAX];
string rg_who;                  // RG_Name's picture mark, "" none

string(float g) RG_Name =
{
	local float s, i;
	local string nm;

	s = rg_slot[g];
	rg_who = "";
	if (s >= LN_S_GHOST)
	{
		rg_who = getplayerkeyvalue(player_localnum, "*ahash");
		if (rg_who == "")
			rg_who = getplayerkeyvalue(player_localnum, "*phash");
		if (s == LN_S_GHOST && rg_pbleg[0] > 0)
			return sprintf("Your stage %g PB", rg_pbleg[0]);
		return "Your PB";
	}
	i = LN_BOARDINDEX(s);
	if (sb_ln_who[i])
		rg_who = sb_ln_who[i];
	nm = ln_owner[s];
	if (nm == "")
		nm = sb_ln_name[i];
	if (nm == "")
		nm = "unknown";
	return nm;
};

void(vector scr) RG_Tags =
{
	local float g, dist, far, a, tsz, icon, nw, x;
	local vector eye, fwd, head, v, q;
	local string nm, who;

	rg_tagn = 0;
	for (g = 0; g < RG_MAX; g = g + 1)
		rg_tagd[g] = FALSE;
	if (!cvar("hud_ghost_names") || rg_n < 1)
		return;
	if (rec_sb_open || av_open)
		return;
	eye = getproperty(VF_ORIGIN);
	makevectors(getproperty(VF_ANGLES));
	fwd = v_forward;
	far = bound(0, cvar("hud_playerlabels_far"), 6000);
	Font_Set(ui_font_ui);
	tsz = max(8, Font_Px(6 * max(1, ui_cv_scale)));
	icon = tsz * 1.6;
	for (g = 0; g < rg_n; g = g + 1)
	{
		rg_tagd[g] = FALSE;
		head = rg_pos[g] + (rg_duck[g] ? PM_DUCK_VIEW_OFS : PM_VIEW_OFS) + '0 0 16';
		v = head - eye;
		dist = vlen(v);
		if (dist < 24 || dist > far || v * fwd <= 8)
			continue;
		q = project(head);
		if (q_x < icon || q_x > scr_x - icon || q_y < icon || q_y > scr_y - icon)
			continue;
		traceline(eye, head - '0 0 16', MOVE_NOMONSTERS, world);
		if (trace_fraction < 1 || trace_startsolid)
			continue;
		nm = RG_Name(g);
		who = rg_who;
		a = bound(0, (1024 - dist) / 768, 1);
		nw = 0;
		if (a > 0)
		{
			nm = Chat_Fit(nm, tsz * 24, tsz);
			nw = stringwidth(nm, TRUE, [tsz, tsz]);
		}
		x = q_x - (icon + a * (nw + tsz * 0.5)) * 0.5;
		if (who == "" || !SteamPic_Draw([x, q_y - icon * 0.5], icon, who, 1))
			sui_roundbox([x, q_y - icon * 0.5], [icon, icon], icon * 0.25, rg_col[g], 1);
		if (a > 0)
		{
			drawstring([x + icon + tsz * 0.5 + 1, q_y - tsz * 0.5 + 1], nm, [tsz, tsz], '0 0 0', a, 0);
			drawstring([x + icon + tsz * 0.5, q_y - tsz * 0.5], nm, [tsz, tsz], '1 1 1', a, 0);
		}
		rg_tagd[g] = TRUE;
		rg_tagn = rg_tagn + 1;
	}
	Font_Reset();
};

// `raceghost`: what it is following and where.
float() RG_Console =
{
	local float g, i;
	local vector p;

	if (argv(0) != "raceghost")
		return FALSE;
	print(sprintf("raceghost: cv %g sync %g offset %g lines %g pb %g\n", cvar("hud_ghost"),
	              cvar("hud_ghost_sync"), cvar("hud_ghost_offset"), cvar("hud_ghost_lines"),
	              cvar("hud_ghost_pb")));
	print(sprintf("raceghost: clock %.4f (stat %g, lead %.4f) track %g seg %g legnow %g",
	              rg_now, rg_lticks, rg_lead, rg_track, rg_seg, rg_legnow),
	      sprintf(" runleg %g (stat %g) base %.3f armed %g\n", rg_runleg, getstatf(STAT_FS_RUNLEG),
	              rg_base, rg_armed));
	for (i = 0; i < 2; i = i + 1)
		print(sprintf("raceghost: pb %s leg %g state %g pts %g %s\n", i ? "run" : "stage",
		              rg_pbleg[i], rg_pbst[i], ln_n[i ? LN_S_GHR : LN_S_GHOST],
		              rg_pbpath[i] ? rg_pbpath[i] : "-"));
	for (g = 0; g < rg_n; g = g + 1)
	{
		p = rg_pos[g];
		print(sprintf("raceghost: ghost %g slot %g t %.4f at %.1f %.1f %.1f",
		              g, rg_slot[g], rg_t[g], p_x, p_y, p_z),
		      sprintf(" yaw %.1f end %g anchor %.4f mine %.4f duck %g\n", rg_yaw[g], rg_end[g],
		              rg_anc[g], rg_am, rg_duck[g]));
		print(sprintf("raceghost: tag %g \"%s\" drawn %g\n", g, RG_Name(g), rg_tagd[g]));
	}
	p = pmove_org;
	print(sprintf("raceghost: you at %.1f %.1f %.1f\n", p_x, p_y, p_z));
	print(sprintf("raceghost: %g shown, %g tags\n", rg_n, rg_tagn));
	return TRUE;
};
