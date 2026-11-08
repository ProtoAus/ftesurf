/*
  P1425: point_template and env_entity_maker, as Source has them (server/mapentities.cpp:440-485,
  point_template.cpp, TemplateEntities.cpp, env_entity_maker.cpp).

  Source keeps the keyvalues of every entity a point_template names and removes the entity before it
  spawns (unless spawnflag 1); ForceSpawn makes new ones from those keyvalues each time, placed as
  they sat relative to the template (an env_entity_maker: relative to itself or a target), and names
  the group's members point at among themselves get this instance's "&0001" suffix (unless
  spawnflag 2). bhop_4muddz's teleporters Kill themselves when used and are ForceSpawned again; here
  they used to exist from the start and be gone after one use.

  Members often come before their point_template in the lump, so CheckSpawn keeps every named
  entity's parsed fields (SV_TplCapture). The first frame, before anything resolves a target, makes
  one PROTOTYPE per member from them -- parsed once, its outputs built once by SV_EntityIOBuild like
  the map's, its classname, targetname, parentname and model held in tpl_p* so no walker takes it for
  the real thing -- and removes the members (SV_TplBuild). An instance copies the prototypes and
  their output edicts (copyentity) and runs each class's spawn function. Re-parsing a record and
  rebuilding its outputs per instance cost 1.8 ms for bhop_crash_egypt's 3-entity fruit; see
  tools/p1425-templates.md for the copy's.
*/

#define SF_TPL_DONTREMOVE       1
#define SF_TPL_PRESERVE         2
#define SF_MAKER_AUTOSPAWN      1
#define SF_MAKER_WAITDESTROY    2
#define SF_MAKER_IGNOREFACING   4
#define SF_MAKER_CHECKLOOK      16       // 8, CheckForSpace, is not tested: members are records, not bodies

void() point_template   = { self.solid = SOLID_NOT; self.movetype = MOVETYPE_NONE; setorigin(self, self.origin); };
void() env_entity_maker = { self.solid = SOLID_NOT; self.movetype = MOVETYPE_NONE; setorigin(self, self.origin); };

// Outputs go apart: saveent stops at 64 KB and a member's can be longer.
void(entity e) SV_TplCapture =
{
	local string raw;

	raw = e.vbsp_io_raw;
	e.vbsp_io_raw = "";
	e.tpl_rec = strzone(generateentitydata(e));
	e.vbsp_io_raw = raw;
	if (raw != "")
		e.tpl_io = strzone(raw);
};

float(string list, string nm) SV_TplListed =
{
	return strstrofs(list, strcat("\n", strtolower(nm), "\n"), 0) >= 0;
};

// The string fields a member's names can sit in: not its own name or class, not the prototype's holders.
float(float fld) SV_TplNameField =
{
	local string nm;

	if (entityfieldtype(fld) != EV_STRING)
		return FALSE;
	nm = entityfieldname(fld);
	if (nm == "targetname" || nm == "classname" || nm == "model" || nm == "vbsp_io_raw")
		return FALSE;
	return substring(nm, 0, 4) != "tpl_";
};

// TemplateEntities.cpp:200-290: a member's key (not its targetname) naming a member -- an output by
// its target -- gets the suffix, and so does the named member's targetname. The members are the same
// every instance, so the first one finds the names and the fields (tpl_refs, tpl_flds) and later
// instances only rewrite those.
void(entity p, entity first, string suffix) SV_TplFixup =
{
	local entity e, o;
	local string grp, refs, flds, v;
	local float n, fld, i, nf;

	if (!p.tpl_fix)
	{
		grp = "\n";
		for (e = first; e; e = e.tpl_chain)
			if (e.targetname != "")
				grp = strcat(grp, strtolower(e.targetname), "\n");
		refs = "\n";
		flds = "";
		n = numentityfields();
		for (e = first; e; e = e.tpl_chain)
		{
			for (fld = 1; fld < n; fld = fld + 1)
			{
				if (!SV_TplNameField(fld))
					continue;
				v = getentityfieldstring(fld, e);
				if (v == "" || !SV_TplListed(grp, v))
					continue;
				if (!SV_TplListed(refs, v))
					refs = strcat(refs, strtolower(v), "\n");
				if (strstrofs(strcat(" ", flds), strcat(" ", ftos(fld), " "), 0) < 0)
					flds = strcat(flds, ftos(fld), " ");
			}
			for (o = e.vbsp_io_out; o; o = o.vbsp_io_next)
				if (SV_TplListed(grp, o.vbsp_io_target) && !SV_TplListed(refs, o.vbsp_io_target))
					refs = strcat(refs, strtolower(o.vbsp_io_target), "\n");
		}
		p.tpl_fix = (refs == "\n") ? -1 : 1;
		p.tpl_refs = strcat(refs);
		p.tpl_flds = strcat(flds);
	}
	if (p.tpl_fix < 0)
		return;
	refs = p.tpl_refs;
	nf = tokenize(p.tpl_flds);
	for (e = first; e; e = e.tpl_chain)
	{
		if (e.targetname != "" && SV_TplListed(refs, e.targetname))
			e.targetname = strcat(e.targetname, suffix);
		for (i = 0; i < nf; i = i + 1)
		{
			fld = stof(argv(i));
			v = getentityfieldstring(fld, e);
			if (v != "" && SV_TplListed(refs, v))
				putentityfieldstring(fld, e, strcat(v, suffix));
		}
		for (o = e.vbsp_io_out; o; o = o.vbsp_io_next)
			if (SV_TplListed(refs, o.vbsp_io_target))
				o.vbsp_io_target = strcat(o.vbsp_io_target, suffix);
	}
};

// matEntityToTemplate then the new template pose (point_template.cpp CreateInstance). The position is
// exact for any pose (makevectors both ways); angles compose the yaw only -- no template or maker in
// the library that spawns a moving or solid member is pitched or rolled.
void(entity e, vector torg, vector tang, vector morg, vector mang) SV_TplPlace =
{
	local vector d, lo;

	if (morg == torg && mang == tang)
		return;
	makevectors(tang);
	d = e.origin - torg;
	lo = [d * v_forward, d * v_right, d * v_up];
	makevectors(mang);
	e.origin = morg + v_forward * lo_x + v_right * lo_y + v_up * lo_z;
	e.angles_y = e.angles_y + mang_y - tang_y;
};

// One member through its class's spawn function (its outputs already attached, as Source's exist
// from its keyvalues before Spawn), then what the first frame did for the map's.
void(entity e) SV_TplRun =
{
	local entity oself, o, nx;

	o = e.vbsp_io_out;
	// A spawn function asks only whether the entity has outputs -- trigger_multiple drops a model with none
	// (sv_entities.qc, "vbsp_io_raw is complete by now") -- and the instance's are already built.
	if (e.tpl_hadio)
		e.vbsp_io_raw = "outputs";
	oself = self;
	self = e;
	vbsp_late_respawn = TRUE;           // a model-less named trigger keeps its edict (SV_ToolTrig)
	if (isfunction(e.classname))
		callfunction(e.classname);
	else
		SV_OnEntityNoSpawnFunction();
	vbsp_late_respawn = FALSE;
	self = oself;
	if (!wasfreed(e))
		e.vbsp_io_raw = "";
	if (wasfreed(e))
	{
		for (; o; o = nx)
		{
			nx = o.vbsp_io_next;
			remove(o);
		}
		return;
	}
	if (e.classname != "func_brush" && e.rendermode && substring(e.model, 0, 1) == "*")
		SV_BrushRenderState(e);
};

string(float n) SV_TplSuffix =
{
	local string s;

	s = ftos(n);
	while (strlen(s) < 4)
		s = strcat("0", s);
	return strcat("&", s);
};

// point_template.cpp CreateInstance at a pose (the template's own for ForceSpawn).
float(entity p, vector morg, vector mang) SV_TplInstance =
{
	local entity q, e, o, n, tail, nx, first, last;

	if (!p.tpl_proto)
		return FALSE;
	tpl_count = tpl_count + 1;
	if (tpl_count >= 10000)
		tpl_count = 1;                  // Source wraps at 10^4 (TemplateEntities.cpp:312); 0 marks "none" here
	first = last = world;
	for (q = p.tpl_proto; q; q = q.tpl_pnext)
	{
		e = spawn();
		if (num_for_edict(e) > 100000)
		{
			// pr_maxedicts is 131072 and Sys_Error past it: an AutoSpawn maker without WaitForDestruction
			// spawns every 0.5 s, as in Source, and only the map's own Kill outputs bound it.
			remove(e);
			for (e = first; e; e = nx)
			{
				nx = e.tpl_chain;
				for (o = e.vbsp_io_out; o; o = n)
				{
					n = o.vbsp_io_next;
					remove(o);
				}
				remove(e);
			}
			if (SV_CensusAdd("template instances past 100000 edicts"))
				dprint("^1point_template: the map spawned instances up to 100000 edicts; refusing more\n");
			return FALSE;
		}
		copyentity(q, e);
		e.classname = q.tpl_pclass;
		e.targetname = q.tpl_pname;
		e.parentname = q.tpl_pparent;
		e.model = q.tpl_pmodel;
		e.tpl_pclass = e.tpl_pname = e.tpl_pparent = e.tpl_pmodel = "";
		e.tpl_pnext = world;
		e.vbsp_io_out = tail = world;
		for (o = q.vbsp_io_out; o; o = o.vbsp_io_next)
		{
			n = spawn();
			copyentity(o, n);
			n.owner = e;
			n.vbsp_io_next = world;
			if (tail)
				tail.vbsp_io_next = n;
			else
				e.vbsp_io_out = n;
			tail = n;
			vbsp_io_n = vbsp_io_n + 1;
		}
		e.tpl_instof = tpl_count;
		e.tpl_chain = world;
		SV_TplPlace(e, p.tpl_torg, p.tpl_tang, morg, mang);
		if (last)
			last.tpl_chain = e;
		else
			first = e;
		last = e;
	}
	if (!(p.spawnflags & SF_TPL_PRESERVE))
		SV_TplFixup(p, first, SV_TplSuffix(tpl_count));
	for (e = first; e; e = nx)
	{
		nx = e.tpl_chain;
		e.tpl_chain = world;
		SV_TplRun(e);
	}
	if (cvar("developer"))
		dprint(sprintf("point_template %s: instance %g, %g entities\n", p.targetname, tpl_count, p.tpl_n));
	return TRUE;
};

// CBaseCombatCharacter::FInViewCone plus a clear line, for any player.
float(vector org) SV_TplLooked =
{
	local entity pl;
	local vector eye;

	for (pl = find(world, classname, "player"); pl; pl = find(pl, classname, "player"))
	{
		eye = pl.origin + pl.view_ofs;
		makevectors(pl.v_angle);
		if (normalize(org - eye) * v_forward < 0.5)
			continue;
		traceline(eye, org, TRUE, pl);
		if (trace_fraction == 1)
			return TRUE;
	}
	return FALSE;
};

void() SV_TplMakerThink;

void(entity m, vector org, vector ang) SV_TplMakerSpawn =
{
	local entity p;

	for (p = find(world, classname, "point_template"); p; p = find(p, classname, "point_template"))
		if (!strcasecmp(p.targetname, m.tpl_maker))
			break;
	if (!p)
	{
		if (SV_CensusAdd("env_entity_maker without its point_template"))
			dprint(sprintf("^3env_entity_maker %s: no point_template named %s\n", m.targetname, m.tpl_maker));
		return;
	}
	if (!SV_TplInstance(p, org, ang))
		return;
	m.tpl_inst = tpl_count;
	SV_FireOutput(m, "OnEntitySpawned", m);
	if (m.spawnflags & SF_MAKER_AUTOSPAWN)
	{
		m.think = SV_TplMakerThink;
		m.nextthink = time + 0.5;
	}
};

// env_entity_maker.cpp CheckSpawnThink; the first spawn is Activate's, without the checks.
void() SV_TplMakerThink =
{
	self.nextthink = time + 0.5;
	if (self.tpl_inst > 0)
	{
		if (self.spawnflags & SF_MAKER_WAITDESTROY)
		if (findfloat(world, tpl_instof, self.tpl_inst))
			return;
		if (!(self.spawnflags & SF_MAKER_IGNOREFACING))
		if (SV_TplLooked(self.origin))
			return;
	}
	SV_TplMakerSpawn(self, self.origin, self.angles);
};

float(entity t, string in, string pm, entity act) SV_TplInput =
{
	local entity d;

	if (t.classname == "point_template")
	{
		if (in != "forcespawn")
			return FALSE;
		if (SV_TplInstance(t, t.origin, t.angles))
			SV_FireOutput(t, "OnEntitySpawned", t);
		return TRUE;
	}
	if (t.classname != "env_entity_maker")
		return FALSE;
	if (in == "forcespawn")
	{
		if (t.spawnflags & SF_MAKER_CHECKLOOK)
		if (SV_TplLooked(t.origin))
		{
			SV_FireOutput(t, "OnEntityFailedSpawn", t);
			return TRUE;
		}
		SV_TplMakerSpawn(t, t.origin, t.angles);
		return TRUE;
	}
	if (in == "forcespawnatentityorigin")
	{
		if (pm == "!activator")
			d = act;
		else if (pm == "!self" || pm == "!caller")
			d = t;
		else
			d = SV_FindByName(pm, world);
		if (d)
			SV_TplMakerSpawn(t, d.origin, d.angles);
		return TRUE;
	}
	return FALSE;
};

// The first frame, before the late spawns and every target resolve: prototypes, then members leave.
void() SV_TplBuild =
{
	local entity p, e, q, last, nx;
	local float p0, pn, nmem, nrem, ntpl, nproto;
	local string names, nm, have;

	tpl_built = TRUE;
	nrem = ntpl = nproto = 0;
	// The captured names, once: a template name nothing carries (bhop_4muddz names 7 "glock" weapons, gone
	// at spawn) then costs a string search instead of a walk of every edict (61 ms there before).
	have = "\n";
	if (find(world, classname, "point_template"))
		for (e = nextent(world); e; e = nextent(e))
			if (e.tpl_rec != "")
				have = strcat(have, strtolower(e.targetname), "\n");
	for (p = find(world, classname, "point_template"); p; p = find(p, classname, "point_template"))
	{
		ntpl = ntpl + 1;
		p.tpl_proto = last = world;
		p.tpl_n = 0;
		p.tpl_fix = 0;
		p.tpl_torg = p.origin;
		p.tpl_tang = p.angles;
		names = p.tpl_names;
		p0 = 0;
		while ((pn = strstrofs(names, "\n", p0)) >= 0)
		{
			nm = substring(names, p0, pn - p0);
			p0 = pn + 1;
			nmem = 0;
			if (SV_TplListed(have, nm))
			for (e = nextent(world); e; e = nextent(e))
			{
				if (e == p || e.tpl_rec == "" || e.classname == "tpl_proto" || strcasecmp(e.targetname, nm))
					continue;
				q = spawn();
				parseentitydata(q, e.tpl_rec);
				q.vbsp_io_raw = strcat(e.tpl_io);       // SV_EntityIOBuild, later this frame, builds them once
				q.tpl_hadio = (e.tpl_io != "");
				q.tpl_pclass = q.classname;
				q.tpl_pname = q.targetname;
				q.tpl_pparent = q.parentname;
				q.tpl_pmodel = q.model;
				q.classname = "tpl_proto";
				q.targetname = q.parentname = q.model = "";
				q.tpl_pnext = world;
				if (last)
					last.tpl_pnext = q;
				else
					p.tpl_proto = q;
				last = q;
				p.tpl_n = p.tpl_n + 1;
				nmem = nmem + 1;
				nproto = nproto + 1;
				e.tpl_member = TRUE;
				if (p.spawnflags & SF_TPL_DONTREMOVE)
					e.tpl_keep = TRUE;
			}
			if (!nmem && cvar("developer"))
				dprint(sprintf("point_template %s: nothing named %s\n", p.targetname, nm));
		}
	}
	for (e = nextent(world); e; e = nx)
	{
		nx = nextent(e);
		if (e.tpl_rec != "")
		{
			strunzone(e.tpl_rec);
			e.tpl_rec = "";
		}
		if (e.tpl_io != "")
		{
			strunzone(e.tpl_io);
			e.tpl_io = "";
		}
		if (e.tpl_member && !e.tpl_keep)
		{
			remove(e);
			nrem = nrem + 1;
		}
	}
	// AutoSpawn is Activate's in Source, once every entity exists: the next think, after SV_EntityIOBuild
	// has made the maker's own OnEntitySpawned.
	for (e = find(world, classname, "env_entity_maker"); e; e = find(e, classname, "env_entity_maker"))
		if (e.spawnflags & SF_MAKER_AUTOSPAWN)
		{
			e.tpl_inst = 0;
			e.think = SV_TplMakerThink;
			e.nextthink = time + 0.05;
		}
	if (ntpl)
		dprint(sprintf("point_template: %g templates, %g prototypes, %g members left the map\n", ntpl, nproto,
		               nrem));
};
