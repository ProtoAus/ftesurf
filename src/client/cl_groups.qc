// P1590: Groups. surfd's game_groups answers, for this map and one board mode, every
// leg's seven cut times (the Top 10's last time, then G1..G6's) off the imported board
// it ladders, and the local player's own group per leg. The TAB board draws a line
// where the group changes and a badge on each leg; one request serves both.
#define GR_MAXLEG 64
#define GR_TTL    120     // s an open board keeps an answer before asking again

// One declaration each: fteqcc reads `float *a, *b` as b a float**.
float *gr_track;
float *gr_leg;
float *gr_x;
float *gr_g;                // the local player's group on the leg, -1 none
float *gr_src;              // 1 KSF, 0 Momentum
float *gr_ms;               // 7 a leg
float gr_n, gr_req, gr_sent, gr_at, gr_wait;
string gr_key;            // "<map>|<style>" the store holds or is asking for (strzoned)

// A finish can move the player's group: the next draw asks again, and an answer from
// before it is dropped.
void() Groups_Stale = { gr_at = -1000; gr_wait = 0; gr_req = 0; };

// surfd echoes the map lower-cased (clean_map); six library maps have capitals.
string(string style) Groups_Key = { return strcat(strtolower(serverkey("map")), "|", style); };

void(string style) Groups_Need =
{
	local string key, dir, me, url;

	if (!gr_track)
	{
		gr_track = (float *)memalloc(GR_MAXLEG * 4);
		gr_leg = (float *)memalloc(GR_MAXLEG * 4);
		gr_x = (float *)memalloc(GR_MAXLEG * 4);
		gr_g = (float *)memalloc(GR_MAXLEG * 4);
		gr_src = (float *)memalloc(GR_MAXLEG * 4);
		gr_ms = (float *)memalloc(GR_MAXLEG * 7 * 4);
		gr_key = strzone("");
		gr_at = -1000;
	}
	key = Groups_Key(style);
	if (gr_req && cltime - gr_sent > OB_DEADLINE)
	{
		gr_req = 0;
		gr_wait = cltime + OB_RETRY_SECS;
	}
	if (strcmp(key, gr_key))
	{
		strunzone(gr_key);
		gr_key = strzone(key);
		gr_n = 0;                    // another board's lines must not stay up
		gr_req = 0;
		gr_at = -1000;
		gr_wait = 0;
	}
	if (gr_req || cltime < gr_wait || cltime - gr_at < GR_TTL)
		return;
	if (serverkey("map") == "")
		return;
	if (ui_consent_ver < FS_TERMS_ONLINE)
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
		return;
	dir = cvar_string("lobby_dir");
	if (dir == "")
		return;
	url = sprintf("%s/api/board?groups=%s&style=%s", dir, uri_escape(serverkey("map")), uri_escape(style));
	me = getplayerkeyvalue(player_localnum, "*phash");
	if (me != "")
		url = strcat(url, "&me=", uri_escape(me));
	gr_req = Online_NextReq();
	gr_sent = cltime;
	if (!uri_get(url, gr_req))
	{
		gr_req = 0;
		gr_wait = cltime + OB_RETRY_SECS;
	}
};

float(float reqid, float code, string body) Groups_Reply =
{
	local int root, legs, leg, ms, g;
	local float i, k, n, at;

	if (!gr_req || reqid != gr_req)
		return FALSE;
	gr_req = 0;
	root = 0;
	if (!code)
		root = json_parse(body);
	if (!root)
	{
		gr_wait = cltime + OB_RETRY_SECS;   // an old surfd 400s the query: asked again in 30 s, not every frame
		dprint(sprintf("groups: no answer (code %g)\n", code));
		return TRUE;
	}
	if (strcmp(strcat(strtolower(json_get_string(json_find_object_child(root, "map"))), "|",
	                  json_get_string(json_find_object_child(root, "style"))), gr_key))
		gr_wait = cltime + OB_RETRY_SECS;   // not the board asked about: never a request a frame
	else
	{
		legs = json_find_object_child(root, "legs");
		n = 0;
		for (i = 0; i < min(GR_MAXLEG, json_get_length(legs)); i = i + 1)
		{
			leg = json_get_child_at_index(legs, i);
			ms = json_find_object_child(leg, "ms");
			k = json_get_length(ms);
			if (k != 7)
				continue;
			gr_track[n] = json_get_float(json_find_object_child(leg, "track"));
			gr_leg[n] = json_get_float(json_find_object_child(leg, "leg"));
			gr_x[n] = json_get_float(json_find_object_child(leg, "x"));
			gr_src[n] = !strcmp(json_get_string(json_find_object_child(leg, "src")), "ksf");
			g = json_find_object_child(leg, "g");
			gr_g[n] = (g > 0) ? json_get_float(g) : -1;
			at = n * 7;
			for (k = 0; k < 7; k = k + 1)
				gr_ms[at + k] = json_get_float(json_get_child_at_index(ms, k));
			n = n + 1;
		}
		gr_n = n;
		gr_at = cltime;
		dprint(sprintf("groups: %s, %g legs\n", gr_key, gr_n));
	}
	json_free(root);
	return TRUE;
};

// The store's index of a leg on the board of `style`, or -1.
float(float track, float leg, string style) Groups_Leg =
{
	local float i;

	if (!gr_n || strcmp(gr_key, Groups_Key(style)))
		return -1;
	for (i = 0; i < gr_n; i = i + 1)
		if (gr_track[i] == track && gr_leg[i] == leg)
			return i;
	return -1;
};

// 0 Top 10, 1-6 G1-G6, 7 ungrouped; -1 nothing to say (no ladder, no time).
float(float li, float ms) Groups_Of =
{
	local float k;

	if (li < 0 || ms <= 0)
		return -1;
	for (k = 0; k < 7; k = k + 1)
		if (ms <= gr_ms[li * 7 + k])
			return k;
	return 7;
};

// "Momentum, 5365 times": what a leg's ladder was measured on.
string(float li) Groups_Source =
{
	if (li < 0)
		return "";
	return sprintf("%s, %g times", gr_src[li] ? "KSF" : "Momentum", gr_x[li]);
};
