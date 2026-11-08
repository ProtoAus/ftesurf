/*
  P1406: StartFrame's per-frame functions each walked every edict with find(e, classname, "player")
  (surf_voyager, ~1,500 edicts: most of StartFrame's QC time).  StartFrame now builds the chain once
  and they read it through SV_PlNext; outside StartFrame SV_PlNext is find().  It is find()'s answer:
  .classname "player" is written by PutClientInServer on a client edict and otherwise only by the
  lump (spawn, SV_LateSpawnAll's restore, both before SV_PlStrayScan); AddOutput keeps it
  (sv_entities.qc).  Test-only check build and mutants: P1406 in BACKLOG.md.
*/
.entity sv_plnext;
entity  sv_plhead;
float   sv_plok;
float   sv_plstray;             // this map has a non-client edict named "player" (SV_PlStrayScan)

// Once a map, after SV_LateSpawnAll: nothing names a non-client edict "player" after it.
void() SV_PlStrayScan =
{
	local entity e;

	sv_plstray = FALSE;
	for (e = find(world, classname, "player"); e; e = find(e, classname, "player"))
		if (clienttype(e) == CLIENTTYPE_NOTACLIENT)
			sv_plstray = TRUE;
};

void() SV_PlChainBuild =
{
	local entity e, last;

	sv_plhead = last = world;
	// Client edicts are 1..sv.allocated_client_slots (PF_clienttype); nextent skips a freed one as find does.
	if (sv_plstray)
		e = find(world, classname, "player");
	else
		e = nextent(world);
	for (; e; e = sv_plstray ? find(e, classname, "player") : nextent(e))
	{
		if (!sv_plstray)
		{
			if (clienttype(e) == CLIENTTYPE_NOTACLIENT)
				break;
			if (e.classname != "player")
				continue;
		}
		if (last)
			last.sv_plnext = e;
		else
			sv_plhead = e;
		last = e;
	}
	if (last)
		last.sv_plnext = world;
	sv_plok = TRUE;
};

// find(e, classname, "player").  A freed one is skipped as find() skips it (an IO Kill from
// SV_SpFrame could only reach a map brush spawned with that classname).
entity(entity e) SV_PlNext =
{
	if (!sv_plok)
		return find(e, classname, "player");
	e = (e == world) ? sv_plhead : e.sv_plnext;
	while (e && wasfreed(e))
		e = e.sv_plnext;
	return e;
};
