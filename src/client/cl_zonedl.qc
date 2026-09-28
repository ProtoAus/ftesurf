/*
===========================================================================
  cl_zonedl.qc -- fetch a map's zone file from our own mirror.

  WHY THIS EXISTS.  The zone library ships with the game (release.ps1's
  $ShipGlobs, 609 files), but a map zoned AFTER a release arrives without one,
  and the map downloader only ever fetched the .bsp: PF_m_downloadmap composes
  exactly "maps/<name>.bsp" (pr_menu.c) and the engine's connected-client
  rewrite does the same (cl_parse.c:1002).  So a player could download a map,
  stand on it, and be told it has no legs and no times (cl_scores.qc:2180)
  while the zone file for it sat on our server.  Reported on surf_666 from a
  public lobby.

  THE URL IS A CLIENT CVAR AND NEVER THE SERVER'S.  sv_dlURL arrives in
  serverinfo and is whatever host you happened to connect to; a file fetched
  from there would be a stranger's JSON deciding where this client thinks the
  start zone is.  cl_download_zonesrc is ours, it is not settable by a server,
  and clearing it turns the whole feature off.

  IT WRITES TO ITS OWN DIRECTORY AND LOSES EVERY TIE.  maps/zones/dl/ is tried
  LAST of the three file sources (cl_zones.qc), so a shipped file or your own
  edit always beats a fetched one.  That ordering is the safety property: if
  the mirror ever serves something wrong, the next release's copy silently
  takes over again, and deleting the directory resets to shipped state.

  ON DISK THAT DIRECTORY IS ftesurf/data/maps/zones/dl/, not
  ftesurf/maps/zones/dl/ -- measured, after this comment first claimed the
  latter.  QC fopen READS the whole VFS but WRITES into the data/ sandbox, so
  the same relative path means two different places depending on the verb.
  Both work here because Zone_LoadJson reads through the same VFS that write
  landed in; the practical consequence is only that a human clearing these out
  by hand must go to data/.

  CLIENT-SIDE ONLY.  sv_zones.qc does not consult this directory and must not:
  the server's table is what the clock is a function of (see sh_zones.qc's
  build-81 block), and it is not going to come from an HTTP fetch made by the
  box being timed.  What this buys is the DISPLAY -- legs, the board, the zone
  volumes -- for a client whose server already has zones it does not.

  ONE ATTEMPT PER MAP CHANGE, WHICH IS NOT THE SAME AS ONE PER SESSION, and
  the weaker claim is the true one: zdl_tried holds only the map last asked
  about, so a rotation A -> B -> A asks for A twice.  A miss is the common
  case (1,156 of the 1,743 downloadable maps genuinely have no zones), so what
  matters is that a failure costs one request and not a stream of them -- and
  a map load is already the most expensive thing this client does, so one 4 KB
  GET against it is not worth a table of every name tried.  Stated rather than
  rounded up because a comment claiming the stronger property is how this
  repo has been bitten before.
===========================================================================
*/

// The request in flight, and the map it is for.  0 = nothing outstanding.
// The id comes from Online_NextReq -- see URI_Get_Callback's header in
// cl_online.qc, which is why this file compiles after that one.
float  zdl_req;
string zdl_for;

// The last map asked about, whatever the answer was.  Compared with strcmp:
// both sides are dynamic strings (AGENTS.md's rule), and `==` on those two
// would be a pointer test that happens to work until it does not.
string zdl_tried;

// Set once the reply landed and a file was written, so Zone_LoadForMap can be
// re-run exactly once rather than on every frame that notices zone_count is 0.
float  zdl_landed;

#define ZDL_MAXBYTES    262144      // the biggest shipped zone file is 38 KB

/*
  Ask the mirror for one map's zones.

  Called from Zone_LoadForMap when all three local sources came up empty, so by
  construction we are not about to overwrite anything we already had.
*/
void(string map) ZoneDL_Want =
{
	local string url, base;

	if (map == "")
		return;
	if (zdl_req)                         // one at a time; the reply re-enters
		return;
	if (zdl_tried != "")
		if (!strcmp(zdl_tried, map))     // strcmp: 0 means equal
			return;

	base = cvar_string("cl_download_zonesrc");
	if (base == "")
		return;                          // switched off, deliberately

	if (zdl_tried != "")
		strunzone(zdl_tried);
	zdl_tried = strzone(map);

	url = strcat(base, map, ".json");
	zdl_req = Online_NextReq();
	if (zdl_for != "")
		strunzone(zdl_for);
	zdl_for = strzone(map);

	if (!uri_get(url, zdl_req))
	{
		// The engine refused to start it -- no web client in this build, or
		// the url is not one it will take.  Drop the id rather than leave a
		// reply slot armed for a request nobody made.
		zdl_req = 0;
		dprint(sprintf("zones: mirror request for %s would not start\n", map));
	}
};

/*
  The reply.  Branched to from CSQC's one URI_Get_Callback; returns TRUE when
  it recognised the id, so the caller stops looking.

  RESPONSECODE 0 IS SUCCESS, not 200 -- PR_uri_get_callback2, and the same
  trap cl_online.qc's header records.  Anything else is a miss, and a miss is
  ordinary: most maps have no zones and the mirror answers 404 for them.
*/
float(float reqid, float code, string bdy) ZoneDL_Reply =
{
	local string part, dst;
	local float fh;

	if (!zdl_req)
		return FALSE;
	if (reqid != zdl_req)
		return FALSE;

	zdl_req = 0;

	if (code != 0 || bdy == "")
	{
		dprint(sprintf("zones: mirror has nothing for %s (%g)\n", zdl_for, code));
		return TRUE;
	}
	if (strlen(bdy) > ZDL_MAXBYTES)
	{
		dprint(sprintf("zones: mirror sent %g bytes for %s -- ignoring\n",
		               strlen(bdy), zdl_for));
		return TRUE;
	}
	// A JSON object or nothing.  This is not a parse -- Zone_LoadJson does
	// that, and sh_zones.qc:1462 already refuses a file that yields no zones
	// -- it is there so an error page saved under a map's name never becomes a
	// file on disk that the loader has to keep rejecting on every map load.
	if (substring(bdy, 0, 1) != "{")
	{
		dprint(sprintf("zones: mirror sent a non-JSON body for %s\n", zdl_for));
		return TRUE;
	}

	// .part then rename, the shape Online_ReplayStore uses: a half-written
	// file under the real name would be parsed as a broken zone table rather
	// than as an absent one.  fopen calls FS_CreatePath, so maps/zones/dl/
	// does not have to exist.
	part = strcat("maps/zones/dl/", zdl_for, ".json.part");
	dst  = strcat("maps/zones/dl/", zdl_for, ".json");

	fh = fopen(part, FILE_WRITE);
	if (fh < 0)
	{
		dprint(sprintf("zones: cannot write %s\n", part));
		return TRUE;
	}
	fputs(fh, bdy);
	fclose(fh);

	// Windows MoveFileW will not overwrite (sys_win.c Sys_Rename), so clear
	// the target first -- the same note Online_ReplayStore carries.
	fh = fopen(dst, FILE_READ);
	if (fh >= 0)
	{
		fclose(fh);
		fremove(dst);
	}
	if (frename(part, dst) != 0)
	{
		fremove(part);
		return TRUE;
	}

	zdl_landed = TRUE;
	return TRUE;
};

/*
  Re-read the zone table once, after a fetch landed.  Driven from the client
  frame rather than done inside the reply because Zone_LoadForMap clears and
  rebuilds the table, and doing that from inside a URI callback runs it in the
  middle of whatever the frame was doing.
*/
void() ZoneDL_Frame =
{
	if (!zdl_landed)
		return;
	zdl_landed = FALSE;
	Zone_LoadForMap();
};
