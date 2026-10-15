/* Refresh the trusted public zone cache BEFORE a picker Play command starts
 * its local server. Client-only maps/zones/dl remains non-authoritative. Local
 * editor overrides still win; failed/404/timed-out refreshes keep prior files. */
#define MZD_SOURCE "https://play.proto.bar/ftesurf/maps/zones/local/"
float mzd_req, mzd_until, mzd_at, mzd_ok;
string mzd_map, mzd_play;
void(string mapname) ui_playlocal_now;

void(string mapname) Mzd_Fetch =
{
	if (cvar("rec_terms") < FS_TERMS_ONLINE || mzd_req) return;
	if (!Mdl_Made(mapname, MDL_NAMECH, 64)) return;
	if (strcmp(mapname, mzd_map) == 0 && gettime(0) - mzd_at < 60) return;
	if (strlen(mzd_map)) strunzone(mzd_map);
	mzd_map = strzone(mapname); mzd_at = gettime(0); mzd_ok = FALSE;
	mzd_req = Lob_NextReq(); mzd_until = gettime(0) + 8;
	if (!uri_get(strcat(MZD_SOURCE, mapname, ".json"), mzd_req))
		mzd_req = 0;
};

void() Mzd_Pump =
{
	local string play;
	if (mzd_req && gettime(0) > mzd_until)
	{
		mzd_req = 0; mzd_at = gettime(0);
		print("^3zones:^7 refresh timed out; existing zones kept\n");
	}
	if (cvar("rec_terms") < FS_TERMS_ONLINE) mzd_req = 0;
	if (!strlen(mzd_play) || mzd_req) return;
	if (cvar("rec_terms") < FS_TERMS_ONLINE || (strcmp(mzd_play, mzd_map) == 0 && gettime(0) - mzd_at < 60))
	{
		play = strzone(mzd_play); strunzone(mzd_play); mzd_play = "";
		ui_playlocal_now(play); strunzone(play);
	}
	else Mzd_Fetch(mzd_play);
};

void(string mapname) Mzd_Play =
{
	if (cvar("rec_terms") < FS_TERMS_ONLINE || !Mdl_Made(mapname, MDL_NAMECH, 64))
	{
		ui_playlocal_now(mapname); return;
	}
	if (strlen(mzd_play)) strunzone(mzd_play);
	mzd_play = strzone(mapname);
	Mzd_Pump();
};

float(float id, float code, string body) Mzd_Reply =
{
	if (!mzd_req || id != mzd_req) return FALSE;
	mzd_req = 0; mzd_at = gettime(0);
	mzd_ok = FALSE;
	if (code == 0 || code == 200)
		mzd_ok = ZoneFile_Store(strcat("maps/zones/curated/", mzd_map, ".json"), body);
	if (mzd_ok)
		print(sprintf("^5zones:^7 refreshed %s (saved local overrides retained)\n", mzd_map));
	else
		print(sprintf("^3zones:^7 no valid refresh for %s; existing zones kept\n", mzd_map));
	return TRUE;
};
