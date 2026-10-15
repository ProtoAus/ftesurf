/* Refresh one client-only zone cache per map visit, including installed maps.
 * Never changes a nonempty active table mid-run, never writes local edits, and
 * the server never reads dl/. Picker Play uses the fixed-origin curated cache
 * BEFORE loading its local server instead (menu/m_zonedl.qc). */
float zdl_req;
string zdl_for, zdl_tried;
float zdl_landed;

void(string map) ZoneDL_Want =
{
	local string base;
	if (cvar("rec_terms") < FS_TERMS_ONLINE) return;
	if (!ZoneFile_Map(map) || zdl_req) return;
	if (strcmp(zdl_tried, map) == 0) return;
	base = cvar_string("cl_download_zonesrc");
	if (base == "") return;
	if (zdl_tried != "") strunzone(zdl_tried);
	zdl_tried = strzone(map);
	if (zdl_for != "") strunzone(zdl_for);
	zdl_for = strzone(map);
	zdl_req = Online_NextReq();
	if (!uri_get(strcat(base, map, ".json"), zdl_req)) zdl_req = 0;
};

float(float reqid, float code, string body) ZoneDL_Reply =
{
	if (!zdl_req || reqid != zdl_req) return FALSE;
	zdl_req = 0;
	if (code != 0 && code != 200) return TRUE;
	if (ZoneFile_Store(strcat("maps/zones/dl/", zdl_for, ".json"), body))
	{
		print(sprintf("^5zones:^7 refreshed cache for %s\n", zdl_for));
		if (strcmp(serverkey("map"), zdl_for) == 0 && zone_count == 0)
			zdl_landed = TRUE;
	}
	return TRUE;
};

void() ZoneDL_Frame =
{
	if (!zdl_landed) return;
	zdl_landed = FALSE;
	if (strcmp(serverkey("map"), zdl_for) != 0 || zone_count != 0) return;
	zone_mapname = "";
	Zone_LoadForMap();
};
