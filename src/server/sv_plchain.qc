/*
  P1406: StartFrame's per-frame functions each walked every edict with find(e, classname, "player")
  (surf_voyager: 774 edicts, most of StartFrame's QC time).  StartFrame now chains the client
  edicts named "player" once and they read it through SV_PlNext; outside StartFrame, or on a map
  that names a non-client edict "player", SV_PlNext is find().  The same answer as find(): .classname
  "player" is written by PutClientInServer on a client edict and otherwise only by the lump (spawn,
  SV_LateSpawnAll's restore, both before SV_PlStrayScan); AddOutput keeps it (sv_entities.qc).  A new
  writer of that classname must keep this true.  Check build and mutants: P1406 in BACKLOG.md.
*/
.entity sv_plnext;
entity  sv_plhead;
float   sv_plok;
float   sv_plstray;             // this map has a non-client edict named "player" (SV_PlStrayScan)

// P1406 follow-up: the same walk chains the connections (acct_here) for Archive_Frame, PlayStats_Frame
// and Account_SelfFrame through SV_AcNext.  acct_here is written only by Account_Connect/_Disconnect,
// from the engine's connect and drop callbacks on a client edict, never inside StartFrame.
.float  acct_here;              // ClientConnect has run for THIS connection (sv_account.qc)
.entity sv_acnext;
entity  sv_achead;
float   sv_acok;
float   sv_acstray;             // the lump set acct_here on a non-client edict

// Once a map, after SV_LateSpawnAll: nothing names a non-client edict "player" after it.
void() SV_PlStrayScan =
{
	local entity e;

	sv_plstray = FALSE;
	for (e = find(world, classname, "player"); e; e = find(e, classname, "player"))
		if (clienttype(e) == CLIENTTYPE_NOTACLIENT)
			sv_plstray = TRUE;
	sv_acstray = FALSE;
	for (e = findfloat(world, acct_here, TRUE); e; e = findfloat(e, acct_here, TRUE))
		if (clienttype(e) == CLIENTTYPE_NOTACLIENT)
			sv_acstray = TRUE;
};

void() SV_PlChainBuild =
{
	local entity e, last, alast;

	if (sv_plstray && sv_acstray)
		return;                     // such a map keeps find()/findfloat() everywhere (sv_plok, sv_acok stay FALSE)
	sv_plhead = last = sv_achead = alast = world;
	// Client edicts are 1..sv.allocated_client_slots (PF_clienttype) and are never freed (ED_CanFree).
	for (e = nextent(world); e; e = nextent(e))
	{
		if (clienttype(e) == CLIENTTYPE_NOTACLIENT)
			break;
		if (!sv_plstray)
		if (e.classname == "player")
		{
			if (last)
				last.sv_plnext = e;
			else
				sv_plhead = e;
			last = e;
		}
		if (!sv_acstray)
		if (e.acct_here == TRUE)
		{
			if (alast)
				alast.sv_acnext = e;
			else
				sv_achead = e;
			alast = e;
		}
	}
	if (last)
		last.sv_plnext = world;
	if (alast)
		alast.sv_acnext = world;
	sv_plok = !sv_plstray;
	sv_acok = !sv_acstray;
};

// find(e, classname, "player").
entity(entity e) SV_PlNext =
{
	if (!sv_plok)
		return find(e, classname, "player");
	if (e == world)
		return sv_plhead;
	return e.sv_plnext;
};

// findfloat(e, acct_here, TRUE).
entity(entity e) SV_AcNext =
{
	if (!sv_acok)
		return findfloat(e, acct_here, TRUE);
	if (e == world)
		return sv_achead;
	return e.sv_acnext;
};
