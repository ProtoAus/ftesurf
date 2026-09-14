/*
===========================================================================
  env_soundscape -- Build 66.  THE ENTITY SOURCE MAPS ACTUALLY USE FOR
  AMBIENCE, and the reason a Momentum map sounds identical everywhere here.

  surf_tensor2 carries 87 env_soundscape against 31 ambient_generic, named in
  pairs -- spawn_inside/spawn_outside, bonus3_inside/bonus3_outside,
  stage9_upper/stage9_outside -- and spawn_outside plays
  ambient/rain_heavy_sc.wav.  That pairing IS the "rain when you step outside"
  behaviour.  Without this system a map has no way to sound different in one
  room than another, no matter what ambient_generic does.

  Library-wide: 1,702 soundscape entities across 125 maps, 731 distinct names,
  and 97.1% of requests resolve -- 935 uses from maps' own packed
  scripts/soundscapes_<map>.txt (108 maps ship one), 474 from the mounted
  HL2/CS:S packs.  75 uses resolve nowhere and are reported rather than
  averaged away.

  ---------------------------------------------------------------------------
  WHY THIS IS CLIENT-SIDE, AND WHY THAT IS NOT A PREFERENCE.

  A soundscape is ONE LISTENER'S ambience.  Every hard problem build 64's
  ambient_generic hit exists only on the server:

    PHS culling      SV_StartSound multicasts an attenuated sound to the PHS at
                     the instant it is sent (sv_send.c:1340-1343) and never
                     re-sends.  PF_cs_sound (pr_csqc.c:4753-4787) contains no
                     multicast, no leaf query, no PHS test at all.
    crossfade        changing a live channel's volume needs `soundupdate`
                     (cl_defs.qc:2039 -> S_UpdateSound).  It is declared for
                     CSQC and NOT for SSQC.  Build 64's note that "FTE has no
                     way to change the volume of a sound already playing" is
                     true of the server builtin set and false here.
    late joiners     do not exist: this runs in the joiner's own VM.

  So the whole SV_AmbientResend / SOUNDFLAG_RELIABLE / prespawn-replay
  apparatus is simply absent.  cl_emit.qc is the structural precedent and this
  file mirrors it: cvars at CSQC_Init, load at CSQC_WorldLoaded, tick from
  CSQC_UpdateView, a serverkey("map") latch as the safety net, and flat
  strbufs rather than QC arrays.

  NO QC ARRAYS.  Measured in this tree at ~8x the data size, and the cost is
  O(the array's declared LENGTH, not its contents) -- sv_timer.qc:110-125
  records 563 KB of progs bought for 68 KB of data.  cl_entview.qc:65-70 is the
  worked answer for variable-count parsed key/value data and this file uses it:
  parallel strbufs plus a "<first> <count>" index row.

  ---------------------------------------------------------------------------
  THE USER'S CORRECTION, WHICH IS THIS FILE'S DESIGN RULE.

  Asked whether to clamp loudness hard after surf_tensor2 was reported
  deafening, they said: "Leave the loudness true, deafening had to do with the
  fact I could hear pretty much all sounds play?  I think if they were
  correctly playing when they should volume is fine?"

  That is right and it is the whole design.  EXACTLY ONE soundscape is active
  at a time, chosen by distance and an unobstructed line of sight, and
  crossfaded.  Nothing here scales anything down to feel safe.  What is bounded
  is STRUCTURE -- recursion, slot count, and rules that ask for more than full
  scale -- because those are what can run away regardless of what a map meant.
===========================================================================
*/

#define SS_MAXDEF     96	// distinct soundscapes kept from the scripts
#define SS_MAXRULE   512	// rules across all of them
#define SS_MAXENT    256	// env_soundscape entities on the map
#define SS_MAXSLOT    24	// simultaneous looping channels
#define SS_MAXDEPTH    8	// Source's own MAX_SOUNDSCAPE_RECURSION
#define SS_MAXFILES   40	// soundscape scripts read for one map

#define SSR_LOOP    1
#define SSR_RANDOM  2
#define SSR_NEST    3

// The one channel this system owns.  NOT CHAN_AUTO: channel 0 allocates a
// fresh channel per call and cannot be addressed again, so stopsound and
// soundupdate would have nothing to aim at (cl_defs.qc:2043).
#define SS_CHAN     CHAN_VOICE

float  ss_on;			// vbsp_soundscape, read once per frame
float  ss_vol;			// vbsp_soundscape_vol
float  ss_fade;			// vbsp_soundscape_fade, seconds for a full 0..1 ramp
float  ss_dbg;

string ss_map;			// the serverkey("map") latch, as cl_emit.qc uses

// The parsed scripts.  ss_def_name[i] is a soundscape name, ss_def_row[i] is
// "<first> <count>" into ss_rule -- exactly cl_entview.qc's index-row idiom.
strbuf ss_def_name, ss_def_row, ss_rule;
float  ss_def_n, ss_rule_n;

// The map's env_soundscape entities, from the entity lump.
strbuf ss_ent_name, ss_ent_org, ss_ent_rad;
float  ss_ent_n;

float  ss_built;		// the buffers exist (handle 0 is VALID -- see below)
float  ss_active;		// index into ss_def_*, or -1
float  ss_gen;			// bumped on every change; slots carry the generation
float  ss_next;			// next selection evaluation, in `time`
float  ss_dropped_pos;		// rules skipped because they need position0..7
float  ss_missing;		// requested names that resolved nowhere

/*
  buf_create HANDS OUT INDICES FROM ZERO, so a perfectly valid buffer can have
  the handle 0 and `if (ss_rule)` would be false for it.  cl_entview.qc:111-118
  wrote this down after the alternative -- calling buf_del on an uninitialised
  0 -- destroys a buffer someone else owns.  ss_built is the authority, and
  every loop over these is bounded by its own float count, never by
  buf_getsize: bufstr_free does not shrink a buffer (m_lobby.qc:295-345
  records the infinite loop that cost).
*/
void() Snds_Free =
{
	if (!ss_built)
		return;
	buf_del(ss_def_name);	buf_del(ss_def_row);	buf_del(ss_rule);
	buf_del(ss_ent_name);	buf_del(ss_ent_org);	buf_del(ss_ent_rad);
	ss_built = FALSE;
	ss_def_n = ss_rule_n = ss_ent_n = 0;
};

void() Snds_Alloc =
{
	Snds_Free();
	ss_def_name = buf_create();	ss_def_row = buf_create();
	ss_rule     = buf_create();
	ss_ent_name = buf_create();	ss_ent_org = buf_create();
	ss_ent_rad  = buf_create();
	ss_built = TRUE;
};

/*
===========================================================================
  The KeyValues parser.

  LINE BY LINE, tokenised per line, rather than a character scanner over the
  whole file.  Three reasons, each of them a trap this tree has already paid
  for:

    * FILE_READNL returns the entire file but NEVER ADVANCES THE OFFSET
      (pr_bgcmd.c:3052-3058), so `while ((l = fgets(f)))` on a READNL handle
      never terminates.  FILE_READ is the mode that yields lines.
    * a character scanner would be tens of thousands of substring() calls on a
      21 KB script, each allocating a tempstring.
    * tokenize()/argv() share ONE global buffer and cannot nest
      (sv_entities.qc:3663-3666).  Tokenising one short line and reading its
      argv before touching the next is the shape that cannot trip over that.

  The format is Valve KeyValues, and these files are written one or two tokens
  per line, so a per-line tokenize is exact rather than a shortcut:

      "spawn_outside"
      {
          "dsp" "0"
          "playlooping"
              {
              "volume" ".4"
              "wave" "ambient/rain_heavy_sc.wav"
              }
      }

  fopen returns a handle >= 1000 on success and -1 on failure
  (pr_bgcmd.c:2582-2584), so the test is `< 0` and never truthiness.
===========================================================================
*/

// Parser state, global because the state machine spans lines.
float  ssp_st;			// 0 name, 1 expect {, 2 in soundscape, 3 after rule key,
					// 4 in rule block, 5 expect subvalue, 6 in rndwave, 7 rnd value
string ssp_name;		// the soundscape being read
string ssp_key;			// the current rule key / subkey
float  ssp_first;		// first rule index of the current soundscape
float  ssp_kind;
string ssp_wave, ssp_sub;
float  ssp_vol, ssp_pitch, ssp_attn, ssp_t0, ssp_t1, ssp_pos;
float  ssp_want;		// only keep soundscapes whose names the map asked for

/*
  "X" or "X,Y" -- Source's interval literal (public/interval.cpp).  A single
  value is a constant; a pair is a uniform range resolved per play.  Stored as
  base + range so the resolve is one multiply at play time.
*/
float(string s) Snds_IvalBase =
{
	local float c;
	c = strstrofs(s, ",", 0);
	if (c < 0)
		return stof(s);
	return stof(substring(s, 0, c));
};
float(string s) Snds_IvalRange =
{
	local float c;
	c = strstrofs(s, ",", 0);
	if (c < 0)
		return 0;
	return stof(substring(s, c + 1, -1)) - stof(substring(s, 0, c));
};

/*
  soundlevel/attenuation -> FTE attenuation.

  SNDLVL_TO_ATTN (public/soundflags.h:106) is `(a > 50) ? 20/(a-50) : 4`, and
  the units carry across unchanged: soundflags.h:108 says Source "encodes
  attenuation * 64 in 8 bits, so the maximum is (255/64)", and FTE writes
  bound(0, attenuation*64, 255) at sv_send.c:1260.  Identical wire encoding.
  This is the same conversion build 64 verified for ambient_generic.

  SNDLVL_NONE (0) means NO FALLOFF AT ALL, which is also what an omitted
  `position` means -- a soundscape's rain is supposed to be everywhere.
*/
float(float sndlvl) Snds_Attn =
{
	if (sndlvl <= 0)
		return ATTN_NONE;
	if (sndlvl <= 50)
		return 3.9;			// Source's floor of 4.0; 4.0*64 trips a warning
	return bound(0.05, 20 / (sndlvl - 50), 3.9);
};

void() Snds_EmitRule =
{
	if (ss_rule_n >= SS_MAXRULE)
		return;
	if (ssp_wave == "")
		return;

	/*
	  A rule naming a position0..7 slot is DROPPED, and counted.

	  Source resolves `position` against the active env_soundscape's
	  position0..7 keys and, when that slot was not provided, drops the whole
	  rule in silence (c_soundscape.cpp:795-800).  This build does not resolve
	  those entities yet, so every positional rule is in that state.

	  Dropping is the SAFE direction and that is why it is the choice: the
	  alternative -- treating a positional rule as ambient -- would play it
	  2D at full volume everywhere, which is precisely the "I can hear all of
	  them at once" failure this build exists to fix.  ~13% of the library's
	  env_soundscape declare a position at all.
	*/
	if (ssp_pos >= 0)
	{
		ss_dropped_pos = ss_dropped_pos + 1;
		return;
	}

	bufstr_add(ss_rule, sprintf("%g\t%s\t%g\t%g\t%g\t%g\t%g",
	                            ssp_kind, ssp_wave, ssp_vol, ssp_pitch,
	                            ssp_attn, ssp_t0, ssp_t1), TRUE);
	ss_rule_n = ss_rule_n + 1;
};

void() Snds_RuleReset =
{
	ssp_wave = "";
	ssp_vol   = 0;			// Source: a playlooping with no volume is dropped
	ssp_pitch = 100;
	ssp_attn  = Snds_Attn(75);	// ATTN_TO_SNDLVL(ATTN_NORM) -- the playlooping default
	ssp_t0 = ssp_t1 = 0;
	ssp_pos = -1;
};

/*
  Did the map ask for this name?  The entity lump is walked BEFORE any script
  is read, so by the time a soundscape block is parsed we already know whether
  anything on the map points at it.

  A linear scan over at most SS_MAXENT names, run once per soundscape block in
  a file, is the cheap side of the trade: the alternative is storing all 1,448
  definitions the library can reach.  It also folds duplicates for free --
  tensor2 has 87 entities naming 30-odd distinct soundscapes.
*/
float(string nm) Snds_DefWanted =
{
	local float i;
	for (i = 0; i < ss_ent_n; i = i + 1)
		if (bufstr_get(ss_ent_name, i) == nm)
			return TRUE;
	return FALSE;
};

/*
  How many DISTINCT names the map asks for.  This is the early-out for the
  manifest walk: once that many definitions have been kept there is nothing
  left to find, and the ~70 HL2/CS:S/TF2 scripts the manifest lists do not need
  reading.  tensor2 asks for about 30 distinct names out of its 87 entities.
*/
float() Snds_WantedCount =
{
	local float i, j, n;
	local string nm;

	n = 0;
	for (i = 0; i < ss_ent_n; i = i + 1)
	{
		nm = bufstr_get(ss_ent_name, i);
		j = 0;
		while (j < i && bufstr_get(ss_ent_name, j) != nm)
			j = j + 1;
		if (j >= i)
			n = n + 1;		// first time this name appeared
	}
	return n;
};

// Index of a parsed soundscape by name, or -1.
float(string nm) Snds_DefIndex =
{
	local float i;
	for (i = 0; i < ss_def_n; i = i + 1)
		if (bufstr_get(ss_def_name, i) == nm)
			return i;
	return -1;
};

void(string tok) Snds_Feed =
{
	local float a;

	if (ssp_st == 0)				// waiting for a soundscape name
	{
		if (tok == "{" || tok == "}")
			return;
		ssp_name = strtolower(tok);
		ssp_st = 1;
		return;
	}
	if (ssp_st == 1)				// expect the opening brace
	{
		if (tok != "{")
		{
			ssp_name = strtolower(tok);	// re-sync rather than derail
			return;
		}
		ssp_first = ss_rule_n;
		// Keep only what the map asked for.  1,448 definitions exist library
		// wide and a map wants a handful; parsing everything would be fine but
		// STORING everything is what costs.
		ssp_want = (Snds_DefWanted(ssp_name) && ss_def_n < SS_MAXDEF);
		ssp_st = 2;
		return;
	}
	if (ssp_st == 2)				// inside a soundscape
	{
		if (tok == "}")
		{
			if (ssp_want && ss_rule_n > ssp_first)
			{
				bufstr_add(ss_def_name, ssp_name, TRUE);
				bufstr_add(ss_def_row, sprintf("%g %g", ssp_first,
				                               ss_rule_n - ssp_first), TRUE);
				ss_def_n = ss_def_n + 1;
			}
			ssp_st = 0;
			return;
		}
		ssp_key = strtolower(tok);
		ssp_st = 3;
		return;
	}
	if (ssp_st == 3)				// a rule key: block, or a scalar to ignore
	{
		if (tok == "{")
		{
			Snds_RuleReset();
			ssp_kind = 0;
			if (ssp_key == "playlooping")     ssp_kind = SSR_LOOP;
			if (ssp_key == "playrandom")      ssp_kind = SSR_RANDOM;
			if (ssp_key == "playsoundscape")  ssp_kind = SSR_NEST;
			ssp_st = 4;
			return;
		}
		// dsp / dsp_player / dsp_volume / soundmixer: parsed and ignored on
		// purpose.  They are reverb and mix-group presets that live in Valve's
		// CLOSED engine (c_soundscape.cpp:683-716 only forwards them to
		// IEngineSound / convars).  Named here rather than censused so the
		// census keeps meaning "nobody has looked at this".
		ssp_st = 2;
		return;
	}
	if (ssp_st == 4)				// inside a rule block
	{
		if (tok == "}")
		{
			if (ssp_kind)
				Snds_EmitRule();
			ssp_st = 2;
			return;
		}
		ssp_sub = strtolower(tok);
		ssp_st = 5;
		return;
	}
	if (ssp_st == 5)				// the sub-key's value
	{
		if (tok == "{")			// rndwave { "wave" "..." ... }
		{
			ssp_st = 6;
			return;
		}
		if (ssp_sub == "wave" || ssp_sub == "name")
			ssp_wave = tok;
		else if (ssp_sub == "volume")
		{
			// CLAMPED TO 1, and this is the one place loudness is touched.
			// Source never clamps (c_soundscape.cpp:732 passes it straight
			// through) and the library declares up to 5.0 -- cave.exit and
			// aoki.level1and2, both on maps we load.  A rule asking for five
			// times full scale is not "true loudness", it is a bug in the
			// script, and honouring it is how speakers get hurt.
			ssp_vol = bound(0, Snds_IvalBase(tok), 1);
		}
		else if (ssp_sub == "pitch")
			ssp_pitch = bound(1, Snds_IvalBase(tok), 255);
		else if (ssp_sub == "soundlevel")
		{
			// "SNDLVL_NORM" and friends are names; anything else is numeric.
			if (substring(strtolower(tok), 0, 7) == "sndlvl_")
				ssp_attn = Snds_Attn(75);
			else
				ssp_attn = Snds_Attn(Snds_IvalBase(tok));
		}
		else if (ssp_sub == "attenuation")
		{
			a = Snds_IvalBase(tok);
			ssp_attn = (a <= 0) ? ATTN_NONE : bound(0.05, a, 3.9);
		}
		else if (ssp_sub == "time")
		{
			ssp_t0 = Snds_IvalBase(tok);
			ssp_t1 = Snds_IvalRange(tok);
		}
		else if (ssp_sub == "position")
			ssp_pos = stof(tok);
		ssp_st = 4;
		return;
	}
	if (ssp_st == 6)				// inside rndwave
	{
		if (tok == "}")
		{
			ssp_st = 4;
			return;
		}
		ssp_st = 7;				// this was the "wave" key
		return;
	}
	if (ssp_st == 7)				// one rndwave entry
	{
		// Keep the FIRST only.  A random pick across the set is a refinement;
		// playing one of them is the difference between the rule existing and
		// not, and playrandom is 991 rules against playlooping's 2,447.
		if (ssp_wave == "")
			ssp_wave = tok;
		ssp_st = 6;
		return;
	}
};

/*
  One script file.  Returns TRUE if it opened.

  A line's `//` comment is cut before tokenising.  Quoted tokens survive
  tokenize() intact, which is what makes a per-line tokenize exact here.
*/
float ss_files_try, ss_files_ok, ss_lines;

float(string path) Snds_ReadFile =
{
	local float f, i, n, c, p, n2;
	local string l, line;

	ss_files_try = ss_files_try + 1;
	f = fopen(path, FILE_READNL);
	if (f < 0)
	{
		dprint(sprintf("soundscape: fopen FAILED %s\n", path));
		return FALSE;
	}
	ss_files_ok = ss_files_ok + 1;
	dprint(sprintf("soundscape: reading %s\n", path));

	/*
	  THE WHOLE FILE IN ONE READ, THEN SPLIT BY HAND -- and this is a deliberate
	  divergence from the sibling loader in cl_emit.qc:385-389, which does
	  `l = fgets(fh); if (!l) break;` in a bounded loop.

	  THAT IDIOM CANNOT READ THESE FILES.  fgets returns "" for a BLANK LINE,
	  and "" is falsy in QC, so `if (!l) break` treats the first empty line as
	  end of file.  soundscapes_surf_tensor2.txt is 21,641 bytes of
	  blank-line-separated blocks; the first version of this function read 39
	  lines of it and reported 0 definitions, which is how this was found.
	  (cl_emit.qc is not wrong today -- data/mapparticles.txt is generated and
	  has no blank lines -- but the idiom is only safe for files like that, and
	  that is worth knowing before it is copied a third time.)

	  FILE_READNL hands back the entire file in one string.  Its documented trap
	  -- that it NEVER ADVANCES THE OFFSET, so a second fgets returns the same
	  string forever (pr_bgcmd.c:3052-3058) -- is exactly the behaviour wanted
	  here, because it is called precisely once.

	  Splitting with strstrofs keeps the scan in C: one call per line rather
	  than one substring per character.
	*/
	l = fgets(f);
	fclose(f);
	if (!l)
		return FALSE;

	p = 0;
	// Bounded rather than while(1): a truncated or garbage file must not be
	// able to spin the client.  The library's largest script is ~1,200 lines.
	for (i = 0; i < 40000; i = i + 1)
	{
		n = strstrofs(l, "\n", p);
		if (n < 0)
			line = substring(l, p, -1);		// the tail, with no newline
		else
			line = substring(l, p, n - p);

		c = strstrofs(line, "//", 0);
		if (c >= 0)
			line = substring(line, 0, c);

		ss_lines = ss_lines + 1;
		c = tokenize(line);
		for (n2 = 0; n2 < c; n2 = n2 + 1)
			Snds_Feed(argv(n2));

		if (n < 0)
			break;
		p = n + 1;
	}
	return TRUE;
};

/*
===========================================================================
  The map's env_soundscape entities, read straight out of the entity lump.

  A FIFTH independent walk of the same lump -- the decals, sprites, fog and
  emitters are the other four, and no one of them reads another.  getentitytoken
  reads the CLIENT's own worldmodel entity string (pr_csqc.c:4396-4428), so
  nothing crosses the wire and the server does not need to know this exists.

  ONLY env_soundscape.  env_soundscape_proxy (251, 12 maps) names another
  ENTITY through MainSoundscapeName and copies its script index at Activate
  (soundscape.cpp:38-62); env_soundscape_triggerable (339, 55 maps) is driven
  by trigger_soundscape brush touches, which is a server->client path this
  build does not add.  Both are counted and reported rather than silently
  skipped, so the gap stays visible.
===========================================================================
*/
float ss_skipped_cls;

void() Snds_LoadEntities =
{
	local string tok, key, cn, nm, org;
	local float rad, dis;

	getentitytoken(0);				// reset to the start of the lump
	while ((tok = getentitytoken()) != "")
	{
		if (tok != "{")
			continue;

		cn = nm = org = "";
		rad = 0;
		dis = 0;

		while ((key = getentitytoken()) != "" && key != "}")
		{
			tok = getentitytoken();
			key = strtolower(key);
			if      (key == "classname")     cn  = tok;
			else if (key == "soundscape")    nm  = tok;
			else if (key == "origin")        org = tok;
			else if (key == "radius")        rad = stof(tok);
			else if (key == "startdisabled") dis = stof(tok);
		}

		if (cn == "env_soundscape_proxy" || cn == "env_soundscape_triggerable")
		{
			ss_skipped_cls = ss_skipped_cls + 1;
			continue;
		}
		if (cn != "env_soundscape" || nm == "" || org == "")
			continue;
		if (dis)
			continue;			// StartDisabled, and nothing can Enable it yet
		if (ss_ent_n >= SS_MAXENT)
			continue;

		/*
		  RADIUS 0 IS NOT A DEFAULT, IT IS "NEVER BY DISTANCE".  Source gates on
		  `m_flRadius > range || m_flRadius == -1` (soundscape.cpp:271), and a
		  zero-filled radius fails both for every range.  47 entities in the
		  library carry radius 0 and they are reachable only through a trigger,
		  which is out of scope -- so they are kept out of the candidate set
		  rather than given an invented default.

		  -1 IS AN EXACT FLOAT COMPARE and -2 would NOT work; that is Source's
		  behaviour too.  381 of the library's env_soundscape use -1, including
		  all 87 on surf_tensor2, so for those maps the winner is purely
		  nearest-with-line-of-sight.
		*/
		if (rad == 0)
			continue;

		bufstr_add(ss_ent_name, strtolower(nm), TRUE);
		bufstr_add(ss_ent_org,  org, TRUE);
		bufstr_add(ss_ent_rad,  ftos(rad), TRUE);
		ss_ent_n = ss_ent_n + 1;
	}
};

/*
===========================================================================
  Loading the scripts for one map.

  Source reads scripts/soundscapes_manifest.txt and then APPENDS
  scripts/soundscapes_<mapname>.txt if the manifest did not already list it
  (soundscape_system.cpp:157-160).  This does the same two sources in the
  opposite order, because the map's own script is where 935 of the library's
  1,409 resolutions live -- reading it first means the common case is one file.

  A NOTE ON PRIORITY, because it will eventually bite someone: a map's embedded
  pakfile is mounted at the TAIL of com_searchpaths, i.e. LOWEST priority
  (fs.c:4610-4631).  A loose scripts/soundscapes_<map>.txt in the gamedir, or
  the same name inside a higher-priority VPK, wins over the BSP's own copy.
  whichpack() reports which one answered if that is ever in doubt.
===========================================================================
*/
void() Snds_LoadScripts =
{
	local float f, i, n, c, got;
	local string l, path;

	ssp_st = 0;
	ssp_name = ssp_key = ssp_wave = ssp_sub = "";

	// 1. the map's own script
	Snds_ReadFile(strcat("scripts/soundscapes_", ss_map, ".txt"));

	// 2. the manifest's file list, stopping as soon as every requested name is
	//    accounted for.  The manifest is one root block of "file" "<path>".
	if (ss_def_n >= Snds_WantedCount())
		return;

	f = fopen("scripts/soundscapes_manifest.txt", FILE_READ);
	if (f < 0)
		return;

	got = 0;
	for (i = 0; i < 4000; i = i + 1)
	{
		l = fgets(f);
		if (!l)
			break;
		c = strstrofs(l, "//", 0);
		if (c >= 0)
			l = substring(l, 0, c);
		n = tokenize(l);
		if (n < 2)
			continue;
		if (strtolower(argv(0)) != "file")
			continue;
		path = argv(1);
		if (got >= SS_MAXFILES)
			break;
		got = got + 1;
		// tokenize's buffer is clobbered by the nested read, which is exactly
		// the trap sv_entities.qc:3663-3666 documents -- so `path` is copied
		// out of argv BEFORE Snds_ReadFile tokenises anything of its own, and
		// the manifest line is never touched again after this point.
		Snds_ReadFile(path);
		if (ss_def_n >= Snds_WantedCount())
			break;
	}
	fclose(f);
};

/*
===========================================================================
  SELECTION -- the half of this build that the user is actually missing.

  Transcribed from CEnvSoundscape::UpdateForPlayer (soundscape.cpp:251-353):
  a candidate qualifies when it is inside its radius (or declares -1), AND a
  straight line from it to the listener's ear is completely unobstructed.
  Nearest qualifying candidate wins.  THE TRACE IS THE INSIDE/OUTSIDE
  MECHANISM -- it is what makes rain stop when you step under a roof, and it
  is the entire reason surf_tensor2 currently sounds the same everywhere.

  TWO DELIBERATE DIVERGENCES FROM SOURCE, both forced, both stated here rather
  than discovered later:

  1. NO PVS PREFILTER.  Source narrows the candidate set by cluster before
     tracing (soundscape_system.cpp:193-257).  checkpvs IS registered for CSQC
     and taking its world from the client's own -- and it WAS BUILT, TESTED AND
     REMOVED in this tree, because it culled every zone on the map including
     the four in front of the camera, in both the SOLID_NOT and SOLID_BBOX
     forms (cl_zones.qc:126-153).  Do not re-litigate it from the header file;
     that measurement stands until someone re-runs it.  The trace alone decides
     here, which is a SUPERSET of Source's candidate set, never a subset -- so
     this can pick a soundscape Source would have skipped, but can never miss
     one Source would have chosen.

  2. THE TRACE ORDER IS CHEAPER THAN SOURCE'S.  Source evaluates the current
     soundscape first to seed the best distance, which gives a little
     hysteresis.  This tests distance BEFORE tracing and skips any candidate
     that could not win anyway, so on a map like tensor2 -- 87 candidates, all
     radius -1 -- the great majority cost a subtraction rather than a trace.
     The result is the same nearest-with-line-of-sight; only the trace count
     differs.

  CSQC tracelines fall through brush entities (a trap already recorded in this
  tree).  Source's MASK_SOLID_BRUSHONLY likewise ignores props and models, so
  world geometry is what decides in both engines and the divergence is small.
===========================================================================
*/
float ss_traces;			// last evaluation's trace count, for the report

float(vector eye) Snds_Pick =
{
	local float i, best, bestd, rad, range;
	local vector org;

	best = -1;
	bestd = 0;
	ss_traces = 0;

	for (i = 0; i < ss_ent_n; i = i + 1)
	{
		rad = stof(bufstr_get(ss_ent_rad, i));
		org = stov(bufstr_get(ss_ent_org, i));
		range = vlen(eye - org);

		// -1 is an EXACT compare, exactly as Source has it: -2 would not work
		// there either (soundscape.cpp:271).
		if (!(rad > range || rad == -1))
			continue;
		if (best >= 0 && range >= bestd)
			continue;		// cannot win -- do not spend a trace on it

		traceline(org, eye, MOVE_NOMONSTERS, world);
		ss_traces = ss_traces + 1;
		if (trace_fraction < 1 || trace_startsolid)
			continue;

		best = i;
		bestd = range;
	}
	return best;
};

/*
===========================================================================
  PLAYBACK.

  One CSQC entity per looping slot.  The entity is what sound()/soundupdate()/
  stopsound() key on, and the channel must not be CHAN_AUTO.

  The generation counter is how a crossfade knows which slots belong to the
  outgoing soundscape: on a change every live slot is marked stale by bumping
  ss_gen, then the incoming soundscape CLAIMS back any slot already playing the
  same wave at the same pitch.  That claim is Source's anti-pop rule
  (c_soundscape.cpp:1100-1194) and it matters more than it sounds: two adjacent
  soundscapes that share a bed -- which is the normal way a mapper builds an
  inside/outside pair -- would otherwise stop and restart the shared loop every
  time you crossed the line.
===========================================================================
*/
.string ssl_wave;
.float  ssl_vol;		// what is playing right now
.float  ssl_tvol;		// what it is ramping towards
// (build 66 carried an .ssl_attn here.  It was written once and read nowhere,
//  and the value it held -- the rule's attenuation -- is exactly the thing a
//  positionless ambient must not use.  Removed in build 67 with the ATTN_NONE
//  fix in Snds_Apply, so the record cannot suggest a falloff that never runs.)
.float  ssl_pitch;
.float  ssl_gen;

entity(string wave, float pitch) Snds_SlotFind =
{
	local entity e;
	for (e = find(world, classname, "ss_slot"); e;
	     e = find(e, classname, "ss_slot"))
		if (e.ssl_wave == wave && e.ssl_pitch == pitch)
			return e;
	return world;
};

float() Snds_SlotCount =
{
	local entity e;
	local float n;
	n = 0;
	for (e = find(world, classname, "ss_slot"); e;
	     e = find(e, classname, "ss_slot"))
		if (e.ssl_wave != "")
			n = n + 1;
	return n;
};

entity() Snds_SlotAlloc =
{
	local entity e;
	for (e = find(world, classname, "ss_slot"); e;
	     e = find(e, classname, "ss_slot"))
		if (e.ssl_wave == "")
			return e;
	if (Snds_SlotCount() >= SS_MAXSLOT)
		return world;
	e = spawn();
	e.classname = "ss_slot";
	return e;
};

// Self-recursive through playsoundscape, so it needs a prototype -- the same
// idiom sv_entities.qc:739 uses for SV_FireOutput.
void(float def, float depth, float mul) Snds_Apply;

void(float def, float depth, float mul) Snds_Apply =
{
	local float i, first, cnt, kind, vol, pitch, sub;
	local string rec, wave;
	local entity e;

	if (def < 0 || depth >= SS_MAXDEPTH)
		return;

	tokenize(bufstr_get(ss_def_row, def));
	first = stof(argv(0));
	cnt   = stof(argv(1));

	for (i = 0; i < cnt; i = i + 1)
	{
		// Copied OUT of the record before anything else tokenises, because
		// tokenize's buffer is global and Snds_Apply recurses.
		rec   = bufstr_get(ss_rule, first + i);
		tokenize(rec);
		kind  = stof(argv(0));
		wave  = argv(1);
		vol   = stof(argv(2)) * mul;
		pitch = stof(argv(3));
		// argv(4) is the rule's attenuation.  It is deliberately NOT read: every
		// rule that survives Snds_EmitRule is a positionless AMBIENT, which is
		// unspatialised in Source and never consults its soundlevel.  See the
		// ATTN_NONE note in Snds_Frame -- and the build 67 comment below, which
		// is why this is now spelled out rather than left implied.

		if (kind == SSR_NEST)
		{
			// The nested soundscape's volume multiplies down the chain, which
			// is Source's masterVolume (c_soundscape.cpp:1039).  A rule with no
			// volume would zero the whole subtree, so an absent one is 1.
			sub = Snds_DefIndex(wave);
			if (sub >= 0)
				Snds_Apply(sub, depth + 1, (stof(argv(2)) > 0) ? vol : mul);
			continue;
		}
		if (kind != SSR_LOOP)
			continue;		// playrandom is scheduled elsewhere
		if (vol <= 0)
			continue;		// Source drops a playlooping with no volume

		e = Snds_SlotFind(wave, pitch);
		if (!e)
		{
			e = Snds_SlotAlloc();
			if (!e)
				continue;	// over SS_MAXSLOT -- reported, not silent
			e.ssl_wave  = wave;
			e.ssl_pitch = pitch;
			e.ssl_vol   = 0;
			setorigin(e, getproperty(VF_ORIGIN));
			/*
			  BUILD 67.  ATTN_NONE HERE TOO, MATCHING Snds_Frame's soundupdate.

			  This used to pass the rule's own attenuation, and Snds_Frame
			  overwrote it with ATTN_NONE on the very next frame -- so a slot
			  spent exactly one frame spatialised before becoming the 2d ambient
			  it was always meant to be.  Inaudible on its own (the slot starts
			  at 0.01 and ramps), and it stayed invisible for exactly that
			  reason.

			  Engine Patch 315 made it visible and made it matter: that one
			  frame has dist_mult != 0, which is the engine's test for "this
			  source wants positioning", so a stereo soundscape sample was being
			  permanently folded to mono for the rest of the session.  The
			  b67a run caught it -- ambient/rain_heavy_sc.wav and
			  ambient/sea_breeze.wav were downmixed on surf_tensor2 while the
			  test's own header asserted soundscapes could not be touched.

			  A one-frame inconsistency with no audible symptom became a
			  permanent quality loss in the layer the user had just called
			  beautiful, which is the whole argument for writing the two call
			  sites the same way rather than nearly the same way.
			*/
			sound(e, SS_CHAN, wave, 0.01, ATTN_NONE, pitch, SOUNDFLAG_FORCELOOP);
		}
		e.ssl_tvol = bound(0, vol, 1);
		e.ssl_gen  = ss_gen;
	}
};

void(float def) Snds_Start =
{
	local entity e;

	ss_gen = ss_gen + 1;
	ss_active = def;

	// Everything currently playing is stale until the incoming soundscape
	// claims it back by wave+pitch.  Anything left unclaimed fades out.
	Snds_Apply(def, 0, 1);

	for (e = find(world, classname, "ss_slot"); e;
	     e = find(e, classname, "ss_slot"))
		if (e.ssl_wave != "" && e.ssl_gen != ss_gen)
			e.ssl_tvol = 0;
};

void() Snds_StopAll =
{
	local entity e;
	for (e = find(world, classname, "ss_slot"); e;
	     e = find(e, classname, "ss_slot"))
	{
		if (e.ssl_wave == "")
			continue;
		stopsound(e, SS_CHAN);
		e.ssl_wave = "";
		e.ssl_vol = e.ssl_tvol = 0;
	}
	ss_active = -1;
};

void() Snds_LoadForMap =
{
	local float i, def;

	Snds_StopAll();
	Snds_Alloc();
	ss_map = serverkey("map");
	ss_active = -1;
	ss_dropped_pos = ss_missing = ss_skipped_cls = 0;
	ss_files_try = ss_files_ok = ss_lines = 0;

	if (ss_map == "")
		return;

	Snds_LoadEntities();
	if (!ss_ent_n)
		return;				// no soundscapes on this map; stay inert

	Snds_LoadScripts();

	// Every wave a kept soundscape can play, precached once here rather than
	// on first use.  CSQC_WorldLoaded is where precaches belong (cl_main.qc
	// records this) and a mid-run load is a frame this game cannot spare.
	// CSQC's precache_sound takes no MAX_PRECACHE_SOUNDS slot -- it is a plain
	// S_PrecacheSound (pr_csqc.c:3363), unlike the server's.
	for (i = 0; i < ss_rule_n; i = i + 1)
	{
		tokenize(bufstr_get(ss_rule, i));
		if (stof(argv(0)) == SSR_NEST)
			continue;
		precache_sound(argv(1));
	}

	// Requested names that resolved NOWHERE.  Counted per distinct name and
	// reported, rather than left inside a 97.1% figure -- a percentage that
	// high gets quoted as "it works" and the tail is where the reports come
	// from.  75 uses across the library resolve to no script at all.
	for (i = 0; i < ss_ent_n; i = i + 1)
	{
		def = Snds_DefIndex(bufstr_get(ss_ent_name, i));
		if (def < 0)
			ss_missing = ss_missing + 1;
	}
};

void() Snds_LoadFromWorld = { Snds_LoadForMap(); };

/*
===========================================================================
  The per-frame tick.

  Selection runs on a TIMER, not every frame.  Source re-evaluates every tick
  with a 20-trace budget shared across players (soundscape_system.cpp:297-310);
  there is one listener here, so the budget becomes a rate instead.  4 Hz is
  far faster than a player can cross a soundscape boundary and, with the
  distance pre-test in Snds_Pick, costs a handful of traces on a typical map.

  The RAMP runs every frame, because that is what a crossfade is.
===========================================================================
*/
void() Snds_Frame =
{
	local entity e;
	local float step, pick, def;
	local vector eye;

	ss_on = cvar("vbsp_soundscape");
	if (!ss_on)
	{
		if (ss_active >= 0 || Snds_SlotCount())
			Snds_StopAll();		// the kill switch actually kills
		return;
	}

	// The same lazy-reload latch cl_emit.qc:1477 uses, and BEFORE the count
	// test for the same reason it gives: a net skipped whenever the count is 0
	// would never catch arriving on a map WITH soundscapes from one without.
	if (serverkey("map") != ss_map)
	{
		Snds_LoadForMap();
		return;
	}
	if (!ss_ent_n)
		return;

	ss_vol  = cvar("vbsp_soundscape_vol");
	ss_fade = cvar("vbsp_soundscape_fade");
	if (ss_fade <= 0)
		ss_fade = 0.01;

	eye = getproperty(VF_ORIGIN);

	if (time >= ss_next)
	{
		ss_next = time + 0.25;
		pick = Snds_Pick(eye);
		if (pick >= 0)
		{
			def = Snds_DefIndex(bufstr_get(ss_ent_name, pick));
			if (def >= 0 && def != ss_active)
				Snds_Start(def);
		}
		/*
		  NOTHING HAPPENS WHEN NO CANDIDATE QUALIFIES, and that is Source's
		  behaviour rather than an omission: UpdateForPlayer never clears
		  audio.ent, so a player who walks out of every soundscape's line of
		  sight KEEPS the last one until another takes over (the comment at
		  soundscape.cpp:241-247 says so explicitly).  Cutting to silence
		  instead would make every doorway a dropout.
		*/
	}

	step = frametime / ss_fade;

	for (e = find(world, classname, "ss_slot"); e;
	     e = find(e, classname, "ss_slot"))
	{
		if (e.ssl_wave == "")
			continue;
		if (e.ssl_vol == e.ssl_tvol)
			continue;

		if (e.ssl_vol < e.ssl_tvol)
		{
			e.ssl_vol = e.ssl_vol + step;
			if (e.ssl_vol > e.ssl_tvol)
				e.ssl_vol = e.ssl_tvol;
		}
		else
		{
			e.ssl_vol = e.ssl_vol - step;
			if (e.ssl_vol < e.ssl_tvol)
				e.ssl_vol = e.ssl_tvol;
		}

		if (e.ssl_vol <= 0 && e.ssl_tvol <= 0)
		{
			stopsound(e, SS_CHAN);
			e.ssl_wave = "";
			continue;
		}

		/*
		  ATTN_NONE ON EVERY SLOT, and it is Source-correct rather than lazy.
		  A soundscape rule with no `position` is an AMBIENT in Source -- it
		  goes to AddLoopingAmbient (c_soundscape.cpp:791), which is
		  unspatialised, has no falloff, and never reads the rule's soundlevel
		  at all.  The rule's soundlevel only matters for POSITIONAL rules, and
		  those are dropped at parse time (see Snds_EmitRule).

		  That is also why this cannot stack the way ambient_generic did: the
		  gating is the SELECTION -- one soundscape, chosen by distance and line
		  of sight -- not distance falloff on a permanent bed of emitters.
		*/
		soundupdate(e, SS_CHAN, e.ssl_wave,
		            bound(0, e.ssl_vol * ss_vol, 1), ATTN_NONE,
		            e.ssl_pitch, SOUNDFLAG_FORCELOOP, 0);
	}
};

/*
===========================================================================
  Reporting.  `snd_report` prints what is actually loaded and playing.

  This build's whole history is instruments that were correct and could not
  express the failure, so this one prints the things that can BE wrong: which
  soundscape won, how far away it was, how many traces that cost, what is
  audible right now and at what level, and every count that was dropped.
===========================================================================
*/
void() Snds_Report =
{
	local entity e;
	local float i, n;
	local vector eye;

	print(sprintf("soundscapes: %g entit(ies), %g definition(s), %g rule(s) on %s\n",
	              ss_ent_n, ss_def_n, ss_rule_n, ss_map));
	print(sprintf("  scripts: %g of %g opened, %g line(s) parsed, %g name(s) wanted\n",
	              ss_files_ok, ss_files_try, ss_lines, Snds_WantedCount()));

	if (!ss_on)
	{
		print("^3  vbsp_soundscape is 0 -- parsed but silent^7\n");
		return;
	}

	/*
	  THE LISTENER POSITION IS PRINTED, and it is not decoration.  setpos does
	  not noclip (a trap already recorded in this tree), so a scripted arm that
	  places the player at a computed point may leave them somewhere else
	  entirely -- fallen to the floor, or pushed out of geometry.  An arm that
	  asserted only the soundscape NAME could not tell a wrong selection from a
	  player who never arrived.  Printing where the trace actually started makes
	  the assertion checkable against a recomputation at the REAL position.
	*/
	eye = getproperty(VF_ORIGIN);
	print(sprintf("  listener: %.0f %.0f %.0f\n", eye_x, eye_y, eye_z));

	if (ss_active >= 0)
		print(sprintf("  active: %s   (%g trace(s) at the last evaluation)\n",
		              bufstr_get(ss_def_name, ss_active), ss_traces));
	else
		print("^3  active: NONE -- no candidate is both in range and in line of sight^7\n");

	n = 0;
	for (e = find(world, classname, "ss_slot"); e;
	     e = find(e, classname, "ss_slot"))
	{
		if (e.ssl_wave == "")
			continue;
		n = n + 1;
		print(sprintf("    %-44s vol %.2f -> %.2f  pitch %g\n",
		              e.ssl_wave, e.ssl_vol * ss_vol, e.ssl_tvol * ss_vol,
		              e.ssl_pitch));
	}
	print(sprintf("  %g loop(s) playing of %g slot(s)\n", n, SS_MAXSLOT));

	if (ss_missing)
		print(sprintf("^3  %g entit(ies) name a soundscape that resolves NOWHERE^7\n",
		              ss_missing));
	if (ss_dropped_pos)
		print(sprintf("^3  %g rule(s) dropped -- they need position0..7, which this "
		              "build does not resolve^7\n", ss_dropped_pos));
	if (ss_skipped_cls)
		print(sprintf("^3  %g env_soundscape_proxy/_triggerable skipped -- not "
		              "implemented^7\n", ss_skipped_cls));

	for (i = 0; i < ss_ent_n && ss_dbg; i = i + 1)
		print(sprintf("      ent %g  %-30s r=%-7s %s\n", i,
		              bufstr_get(ss_ent_name, i), bufstr_get(ss_ent_rad, i),
		              bufstr_get(ss_ent_org, i)));
};

void() Snds_RegisterCvars =
{
	/*
	  REGISTERED BESIDE THE READ, never after it.  cvar() is PF_Cvar_FindOrGet
	  and with pr_autocreatecvars a miss CREATES the name as "", after which
	  registercvar declines to touch it (`if (Cvar_FindVar(name)) return 0;`).
	  Whichever runs first wins, and that trap is recorded as having silently
	  killed three features in this tree.  Snds_Frame is the only reader and it
	  cannot run before CSQC_Init.
	*/
	registercvar("vbsp_soundscape",      "1",   CVAR_ARCHIVE);
	registercvar("vbsp_soundscape_vol",  "1",   CVAR_ARCHIVE);
	registercvar("vbsp_soundscape_fade", "3",   CVAR_ARCHIVE);
	registercvar("vbsp_soundscape_debug","0");

	registercommand("snd_report");

	ss_active = -1;
	ss_map = "";
};

float(string cmd) Snds_ConsoleCommand =
{
	// argv(0), not cmd.  CSQC_ConsoleCommand tokenises the whole line first
	// (cl_main.qc:1572) and every other handler in the ladder compares argv(0)
	// -- `cmd` carries the full command line, so a direct compare silently
	// fails to match and the command reads as if it did nothing at all.  That
	// is exactly how this shipped its first run: registered, reached, and mute.
	if (argv(0) == "snd_report")
	{
		ss_dbg = cvar("vbsp_soundscape_debug");
		Snds_Report();
		return TRUE;
	}
	return FALSE;
};
