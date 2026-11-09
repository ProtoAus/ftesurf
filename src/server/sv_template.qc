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
  their output edicts (copyentity) and runs each class's spawn function. A spawn costs about 0.5 ms
  (one trigger) to 1.6 ms (bhop_crash_egypt's fruit, three entities and their outputs), nearly all
  of it the engine's edict allocation (70 us each); tools/p1425-templates.md.

  P1432: a member SV_LateStash sets aside keeps its capture (CheckSpawn, SV_LateSpawnAll). The client draws
  an env_sprite from the lump, so a copy of one sends the member's origin and name with its own pose
  (ENTWIRE_TPLFX) and cl_sprites.qc draws it from that member's keys; tools/p1432-tplfx.md.
*/

#define SF_TPL_DONTREMOVE       1
#define SF_TPL_PRESERVE         2
#define SF_MAKER_AUTOSPAWN      1
#define SF_MAKER_WAITDESTROY    2
#define SF_MAKER_IGNOREFACING   4
#define SF_MAKER_CHECKSPACE     8
#define SF_MAKER_CHECKLOOK      16
#define TPL_MAKER_ALIVE         64       // entities one maker's copies may hold at once

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

/*
  A killed entity's output edicts (Kill, sv_entities.qc). Each goes once no delayed fire it started is
  pending -- Source's event queue fires those after the caller is gone, with no caller, so "!self" in
  one resolves to nothing here too. Their links stay: SV_FireOutputBody may be walking this chain (a
  row that Kills its own source, then the rows after it, which Source still fires). Without this a
  template's Kill-then-ForceSpawn cycle (bhop_4muddz, every use) left them all, edicts without end.
*/
void() SV_IOOrphanThink =
{
	// A vbsp_iodelay row points its .owner here; a player-clocked one (SV_PcEligible) can outlast world time.
	if (findentity(world, owner, self))
	{
		self.nextthink = time + 0.5;
		return;
	}
	remove(self);
};

void(entity t) SV_IOOrphan =
{
	local entity o, p;

	for (o = t.vbsp_io_out; o; o = o.vbsp_io_next)
	{
		o.owner = world;
		o.think = SV_IOOrphanThink;
		o.nextthink = time + max(0, o.vbsp_io_delay) + 0.1;
	}
	t.vbsp_io_out = world;
	if (vbsp_onjump_head == t)
		vbsp_onjump_head = t.vbsp_onjump_next;
	else
		for (p = vbsp_onjump_head; p; p = p.vbsp_onjump_next)
			if (p.vbsp_onjump_next == t)
			{
				p.vbsp_onjump_next = t.vbsp_onjump_next;
				break;
			}
};

// One member through its class's spawn function (its outputs already attached, as Source's exist from
// its keyvalues before Spawn, and their text there to read: trigger_multiple drops a model with none,
// SV_SpRawSelfOnly and path_track parse it), then what the first frame did for the map's.
void(entity e) SV_TplRun =
{
	local entity oself, o, nx;

	o = e.vbsp_io_out;
	if (e.tpl_rawi)
		e.vbsp_io_raw = bufstr_get(tpl_raws, e.tpl_rawi - 1);
	oself = self;
	self = e;
	vbsp_late_respawn = TRUE;           // a model-less named trigger keeps its edict (SV_ToolTrig), a filter too
	if (isfunction(e.classname))
		callfunction(e.classname);
	else
		SV_OnEntityNoSpawnFunction();
	vbsp_late_respawn = FALSE;
	self = oself;
	if (wasfreed(e))
	{
		for (; o; o = nx)
		{
			nx = o.vbsp_io_next;
			remove(o);
		}
		return;
	}
	e.vbsp_io_raw = "";
	if (e.tpl_fxi)
	{	// SV_FxInput switches a sprite from here, SV_PsysInput a particle system
		if (e.classname == "info_particle_system")
		{
			e.vbsp_fx_cls = FX_CLS_PSYS;
			e.vbsp_psys_on = SV_PsysOn(e);  // start_active: no sender yet
			if (e.vbsp_psys_on)
			{	// Source's copy starts its system on spawn: a one-shot fires (fresh for a second)
				e.vbsp_psys_starts = 1;
				e.vbsp_psys_fired = time;
			}
		}
		else
		{
			e.vbsp_fx_cls = SV_FxClass(e);
			e.vbsp_fx_on = SV_FxStartOn(e, e.vbsp_fx_cls);
		}
		e.SendEntity = SV_FxSend;
		e.SendFlags = LAS_SF_ID | LAS_SF_STATE;
		e.pvsflags = PVSF_IGNOREPVS;
	}
	if (e.classname != "func_brush" && e.rendermode && substring(e.model, 0, 1) == "*")
		SV_BrushRenderState(e);
	for (o = e.vbsp_io_out; o; o = o.vbsp_io_next)
		if (o.vbsp_io_name == "onjump")
		{
			// Not if it is in already: a copy removed without Kill (a trigger_once, a break) stays linked, and
			// this edict may be its reused slot -- linking it again would close the chain into a loop.
			for (nx = vbsp_onjump_head; nx; nx = nx.vbsp_onjump_next)
				if (nx == e)
					break;
			if (!nx)
			{
				e.vbsp_onjump_next = vbsp_onjump_head;  // SV_EntityIOBuild's OnJump chain
				vbsp_onjump_head = e;
			}
			break;
		}
};

// P1432: ENTWIRE_TPLFX, through SV_FxSend -- the identity once, then the on state.
float(entity to, float changed) SV_TplFxSend =
{
	WriteByte(MSG_ENTITY, ENTWIRE_TYPED);
	WriteByte(MSG_ENTITY, ENTWIRE_TPLFX);
	WriteByte(MSG_ENTITY, ((changed & LAS_SF_ID) ? TPLFX_ID : 0) | TPLFX_V2);
	if (changed & LAS_SF_ID)
	{
		WriteByte(MSG_ENTITY, self.vbsp_fx_cls);
		WriteFloat(MSG_ENTITY, self.tpl_morg_x);
		WriteFloat(MSG_ENTITY, self.tpl_morg_y);
		WriteFloat(MSG_ENTITY, self.tpl_morg_z);
		WriteFloat(MSG_ENTITY, self.tpl_mtnc);
		WriteFloat(MSG_ENTITY, self.tpl_instof);   // a new copy on a reused edict, to a client that missed the remove
		WriteFloat(MSG_ENTITY, self.origin_x);
		WriteFloat(MSG_ENTITY, self.origin_y);
		WriteFloat(MSG_ENTITY, self.origin_z);
		WriteFloat(MSG_ENTITY, self.angles_x);
		WriteFloat(MSG_ENTITY, self.angles_y);
		WriteFloat(MSG_ENTITY, self.angles_z);
	}
	// The same three bytes for every class: a state-only send can reach a client whose identity packet was
	// lost, and it reads them before it knows the class. A particle system's are ENTWIRE_PSYSSTATE2's on,
	// start count and fresh flag.
	if (self.vbsp_fx_cls != FX_CLS_PSYS)
	{
		WriteByte(MSG_ENTITY, self.vbsp_fx_on);
		WriteByte(MSG_ENTITY, 0);
		WriteByte(MSG_ENTITY, 0);
		return TRUE;
	}
	WriteByte(MSG_ENTITY, self.vbsp_psys_on);
	WriteByte(MSG_ENTITY, self.vbsp_psys_starts & 255);
	WriteByte(MSG_ENTITY, (self.vbsp_psys_starts > 0 && time - self.vbsp_psys_fired < 1) ? 1 : 0);
	return TRUE;
};

string(float n) SV_TplSuffix =
{
	local string s;

	s = ftos(n);
	while (strlen(s) < 4)
		s = strcat("0", s);
	return strcat("&", s);
};

// point_template.cpp CreateInstance at a pose (the template's own for ForceSpawn). It succeeds when the
// records are there, as Source's does when they parse -- a member whose spawn function removes it (a CS
// weapon) still counts. tpl_lastfirst is the first entity, Source's m_hCurrentInstance.
entity tpl_lastfirst;
entity tpl_maker_now;           // the env_entity_maker spawning, for tpl_by
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
			// pr_maxedicts is 131072 and Sys_Error past it: an AutoSpawn maker of non-solid members without
			// WaitForDestruction spawns every 0.5 s, as in Source, bounded only by the map's own Kill outputs.
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
		if (SV_FxClass(e) == FX_CLS_SPRITE || e.classname == "info_particle_system")
		{
			e.tpl_fxi = TRUE;
			e.tpl_morg = q.origin;
			e.tpl_mtnc = crc16(TRUE, q.tpl_pname);
		}
		e.tpl_pnext = world;
		e.vbsp_onjump_next = world;
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
		e.tpl_by = tpl_maker_now;
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
	tpl_lastfirst = first;
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

// env_entity_maker.cpp IsPlayerLooking: any player facing it at all (dot > 0), walls or not.
float(vector org) SV_TplLooked =
{
	local entity pl;

	for (pl = find(world, classname, "player"); pl; pl = find(pl, classname, "player"))
	{
		makevectors(pl.v_angle);
		if (normalize(org - (pl.origin + pl.view_ofs)) * v_forward > 0)
			return TRUE;
	}
	return FALSE;
};

// HasRoomToSpawn: the first instance's box at the maker against solids (triggers pass); a blocker that
// has not moved since it blocked still blocks.
float(entity m) SV_TplRoom =
{
	if (m.tpl_blk && !wasfreed(m.tpl_blk) && m.tpl_blk.origin == m.tpl_blkorg)
		return FALSE;
	m.tpl_blk = world;
	tracebox(m.origin, m.tpl_vmin, m.tpl_vmax, m.origin, MOVE_NORMAL, m);
	if (trace_startsolid || (trace_ent && trace_ent != world))
	{
		if (trace_ent != world)
		{
			m.tpl_blk = trace_ent;
			m.tpl_blkorg = trace_ent.origin;
		}
		return FALSE;
	}
	return TRUE;
};

// The current instance lives while its first entity does (an EHANDLE in Source; the instance number
// keeps a reused edict from passing for it).
float(entity m) SV_TplLive =
{
	return m.tpl_cur && !wasfreed(m.tpl_cur) && m.tpl_cur.tpl_instof == m.tpl_inst;
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
	// Copies a maker has alive, capped -- a backstop: the copy blocks its maker until it moves (above), and a
	// mover that cannot run here never moves away.
	local float alive;
	local entity c;
	alive = 0;
	for (c = findentity(world, tpl_by, m); c; c = findentity(c, tpl_by, m))
		alive = alive + 1;
	if (alive >= TPL_MAKER_ALIVE)
	{
		if (SV_CensusAdd("env_entity_maker at its live-copy cap"))
			dprint(sprintf("^3env_entity_maker %s: %g entities of its alive; not spawning more\n", m.targetname, alive));
		return;
	}
	tpl_maker_now = m;
	alive = SV_TplInstance(p, org, ang);
	tpl_maker_now = world;
	if (!alive)
		return;
	m.tpl_inst = tpl_count;
	m.tpl_cur = tpl_lastfirst;
	if (tpl_lastfirst && !wasfreed(tpl_lastfirst))
	{
		// env_entity_maker.cpp:173: "Assume it'll block us" -- until the copy moves or goes.
		m.tpl_blk = tpl_lastfirst;
		m.tpl_blkorg = tpl_lastfirst.origin;
		if (m.tpl_vmin == '0 0 0' && m.tpl_vmax == '0 0 0')
		{
			m.tpl_vmin = tpl_lastfirst.mins;
			m.tpl_vmax = tpl_lastfirst.maxs;
		}
	}
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
	if (self.tpl_inst > 0)
	{
		self.nextthink = time + 0.5;
		if (SV_TplLive(self) && (self.spawnflags & SF_MAKER_WAITDESTROY))
			return;
		if (!SV_TplRoom(self))
			return;
		if (!(self.spawnflags & SF_MAKER_IGNOREFACING) && SV_TplLooked(self.origin))
			return;
	}
	SV_TplMakerSpawn(self, self.origin, self.angles);
};

float(entity t, string in, string pm, entity act, entity caller) SV_TplInput =
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
		if (((t.spawnflags & SF_MAKER_CHECKSPACE) && !SV_TplRoom(t)) ||
		    ((t.spawnflags & SF_MAKER_CHECKLOOK) && SV_TplLooked(t.origin)))
		{
			SV_FireOutput(t, "OnEntityFailedSpawn", t);
			return TRUE;
		}
		SV_TplMakerSpawn(t, t.origin, t.angles);
		return TRUE;
	}
	if (in == "forcespawnatentityorigin")
	{
		// FindEntityByName's special names (entitylist.cpp), case folded as Source's FStrEq does.
		if (FS_IsActivator(pm))
			d = act;
		else if (!strcasecmp(pm, "!caller"))
			d = caller;
		else if (!strcasecmp(pm, "!self"))
			d = t;
		else
			d = SV_FindByName(pm, world);
		if (d && !wasfreed(d))
			SV_TplMakerSpawn(t, d.origin, d.angles);
		return TRUE;
	}
	return FALSE;
};

/*
  Which members are taken. Kept as they were: a solid one (SV_RecSim_Run replays a recording's movement
  in a fresh map's physics world, which has no runtime copies), a parented one and a mover (follower and
  rider chains are built once, SV_SpResolve / SV_TrkResolve, and a copy would never join), and a csprogs
  effect drawn from its wire. Triggers -- their state wire (SV_TrigStateSend) included, which the spawn
  function gives a copy again -- point entities and non-solid props are the members.
*/
float(entity e) SV_TplTakes =
{
	if (e.solid == SOLID_BSP || e.solid == SOLID_BBOX || e.solid == SOLID_SLIDEBOX || e.parentname != "")
		return FALSE;
	// A brush that is not a trigger may turn solid later (StartDisabled func_brush, func_wall_toggle, Enable
	// makes any brush SOLID_BSP: SV_IOEnable), and areaportals sit in a list built at load.
	if (substring(e.model, 0, 1) == "*" && substring(e.classname, 0, 8) != "trigger_")
		return FALSE;
	if (e.vbsp_io_solid == SOLID_BSP)
		return FALSE;
	if (e.SendEntity == SV_SpSend || e.SendEntity == SV_TrkSend || e.SendEntity == SV_TrkPropSend ||
	    e.SendEntity == SV_PsysSend || e.SendEntity == SV_LaserSend || e.SendEntity == SV_PortalSend)
		return FALSE;
	if (e.vbsp_trk_cand)
		return FALSE;
	switch (e.classname)
	{
		case "func_rotating": case "func_movelinear": case "func_tracktrain": case "func_train":
		case "func_tanktrain": case "func_door": case "func_door_rotating": case "func_rot_button":
		case "momentary_rot_button": case "func_plat": case "func_platrot":
			return FALSE;
		// P1432: the client draws these from the lump and has no per-copy instance of them (env_sprite and
		// info_particle_system have: ENTWIRE_TPLFX)
		case "env_laser": case "env_beam": case "point_tesla":
		case "point_spotlight": case "beam_spotlight":
			return FALSE;
	}
	return TRUE;
};

/*
  The first frame, before the late spawns and every target resolve: prototypes, then members leave.
  In lump order, as mapentities.cpp walks its point_templates: a template that removes an entity takes
  it from the ones after it; one with "Don't remove template entities" leaves it for them.
*/
void() SV_TplBuild =
{
	local entity p, e, q, last, nx;
	local float p0, pn, nmem, nrem, ntpl, nproto;
	local string names, nm, have;

	tpl_built = TRUE;
	if (tpl_raws > 0)
		buf_del(tpl_raws);
	tpl_raws = buf_create();
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
			if (strstrofs(nm, "*", 0) >= 0 || SV_TplListed(have, nm))
			for (e = nextent(world); e; e = nextent(e))
			{
				if (e == p || e.tpl_rec == "" || e.tpl_member || !SV_NamesMatch(nm, e.targetname))
					continue;
				if (!SV_TplTakes(e))
					continue;
				q = spawn();
				parseentitydata(q, e.tpl_rec);
				q.vbsp_io_raw = strcat(e.tpl_io);       // SV_EntityIOBuild, later this frame, builds them once
				if (e.tpl_io != "")
				{
					bufstr_add(tpl_raws, e.tpl_io, TRUE);
					q.tpl_rawi = buf_getsize(tpl_raws);
				}
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
				if (!(p.spawnflags & SF_TPL_DONTREMOVE))
					e.tpl_member = TRUE;
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
		if (e.tpl_member)
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
