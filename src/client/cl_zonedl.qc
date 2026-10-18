/* Refresh one client-only zone cache per map visit, including installed maps.
 * Never changes a nonempty active table mid-run, never writes local edits, and
 * the server never reads dl/. Picker Play uses the fixed-origin curated cache
 * BEFORE loading its local server instead (menu/m_zonedl.qc).
 * P815: a fetch is per map AND server zonecrc, so a publish made while you play
 * is fetched at your next visit, and Zone_SyncServer shows it when it matches. */
#define ZDL_SOURCE "https://play.proto.bar/ftesurf/maps/zones/local/"
float zdl_req, zdl_at, zdl_synct;
string zdl_for, zdl_tried, zdl_crcseen;
float zdl_landed;

void(string map) ZoneDL_Want =
{
	local string base, key;
	if (cvar("rec_terms") < FS_TERMS_ONLINE) return;
	if (!ZoneFile_Map(map) || zdl_req) return;
	key = strcat(map, " ", serverkey("zonecrc"));
	if (strcmp(zdl_tried, key) == 0) return;
	// A server can change zonecrc at will: one fetch of a map a minute, whatever it says.
	if (strcmp(zdl_for, map) == 0 && zdl_at > 0 && cltime - zdl_at < 60) return;
	// A server can `set` this cvar too, so it only switches the fetch off ("");
	// the address is always ours.
	if (cvar_string("cl_download_zonesrc") == "") return;
	base = ZDL_SOURCE;
	zdl_at = cltime;
	if (zdl_tried != "") strunzone(zdl_tried);
	zdl_tried = strzone(key);
	if (zdl_for != "") strunzone(zdl_for);
	zdl_for = strzone(map);
	zdl_req = Online_NextReq();
	if (!uri_get(strcat(base, map, ".json"), zdl_req)) zdl_req = 0;
};

float(float reqid, float code, string body) ZoneDL_Reply =
{
	if (!zdl_req || reqid != zdl_req) return FALSE;
	zdl_req = 0;
	if (code != 0 && code != 200)
	{
		zdl_at = cltime - 50;       // a failure spends 10 s, not the minute: the next crc may ask
		return TRUE;
	}
	if (ZoneFile_Store(strcat("maps/zones/dl/", zdl_for, ".json"), body))
	{
		print(sprintf("^5zones:^7 refreshed cache for %s\n", zdl_for));
		if (strcmp(serverkey("map"), zdl_for) == 0 && (zone_count == 0 || Zone_WantsServer()))
			zdl_landed = TRUE;
	}
	return TRUE;
};

void() ZoneDL_Frame =
{
	// The server's crc can arrive or change after the table was built; a server
	// changing it every frame gets one look every 2 s.
	if (strcmp(serverkey("zonecrc"), zdl_crcseen) != 0)
	if (cltime - zdl_synct >= 2)
	{
		zdl_synct = cltime;
		if (zdl_crcseen != "") strunzone(zdl_crcseen);
		zdl_crcseen = strzone(serverkey("zonecrc"));
		if (zone_mapname != "" && strcmp(serverkey("map"), zone_mapname) == 0)
		{
			ZoneDL_Want(zone_mapname);
			Zone_SyncServer(zone_mapname);
		}
	}
	if (zone_sync_wait && getstatf(STAT_FS_TIMERSTATE) != TS_RUNNING)
		Zone_SyncServer(zone_mapname);
	if (!zdl_landed || ZoneEdit_Busy()) return;     // a landing waits for the editor too
	zdl_landed = FALSE;
	if (strcmp(serverkey("map"), zdl_for) != 0) return;
	if (zone_count == 0)
	{
		zone_mapname = "";
		Zone_LoadForMap();
	}
	else
		Zone_SyncServer(zdl_for);
};
