/* Read-only public playtime queries. Counter collection belongs to P1162.
   Account_NextId and Social_Clear bind replies to the current player session. */
.float ptime_req, ptime_sent, ptime_next, ptime_search;
.string ptime_who, ptime_name, ptime_map;

void(entity e) PublicTime_Reset =
{
	e.ptime_req = e.ptime_search = e.ptime_next = 0;
	if (e.ptime_who != "") strunzone(e.ptime_who);
	if (e.ptime_name != "") strunzone(e.ptime_name);
	if (e.ptime_map != "") strunzone(e.ptime_map);
	e.ptime_who = e.ptime_name = e.ptime_map = "";
};

float(string who) PublicTime_Who =
{
	return SV_RecIsHex(who, 8) || SV_RecIsHex(who, 12);
};

string(string name) PublicTime_Name =
{
	return substring(strreplace("\n", " ", strreplace("\r", " ", strdecolorize(name))), 0, 64);
};

float(entity e, string query, float search) PublicTime_Ask =
{
	local string url;
	e.ptime_search = search;
	e.ptime_req = Account_NextId();
	e.ptime_sent = time;
	url = strcat(cvar_string("lobby_master"), "/api/board?", search ? "players=" : "player=", uri_escape(query));
	if (!search) url = strcat(url, "&on=", uri_escape(e.ptime_map));
	if (!uri_get(url, e.ptime_req))
	{
		e.ptime_req = 0;
		sprint(e, PRINT_HIGH, "^3time:^7 profile service unavailable; try again shortly\n");
		return FALSE;
	}
	return TRUE;
};

void(entity e, string wanted) PublicTime_Command =
{
	local entity p, target;
	local float matches;
	local string needle, who;
	target = world; matches = 0;
	if (!e.acct_here || cvar_string("lobby_master") == "")
	{
		sprint(e, PRINT_HIGH, "^3time:^7 enable online play in the menu before looking up tracked time\n");
		return;
	}
	if (e.ptime_req && time - e.ptime_sent < 10)
	{
		sprint(e, PRINT_HIGH, "^3time:^7 the previous lookup is still loading\n");
		return;
	}
	if (time < e.ptime_next) return;
	PublicTime_Reset(e);
	e.ptime_next = time + 3;
	e.ptime_map = strzone(mapname);
	wanted = strtrim(wanted);
	if (wanted == "") target = e;
	else
	{
		needle = strtolower(PublicTime_Name(wanted));
		p = world;
		while ((p = find(p, classname, "player")))
		if (p.run_inserver)
		if (!strcmp(strtolower(PublicTime_Name(p.netname)), needle))
		{
			target = p;
			matches = matches + 1;
		}
		if (matches > 1)
		{
			sprint(e, PRINT_HIGH, "^3time:^7 that name is ambiguous; use their public profile ID\n");
			return;
		}
	}
	if (target)
	{
		who = target.acct_who;
		if (!PublicTime_Who(who))
		{
			sprint(e, PRINT_HIGH, "^3time:^7 that player has no linked Steam playtime profile\n");
			return;
		}
		e.ptime_who = strzone(who);
		e.ptime_name = strzone(PublicTime_Name(target.netname));
		PublicTime_Ask(e, who, FALSE);
		return;
	}
	e.ptime_name = strzone(PublicTime_Name(wanted));
	if (PublicTime_Who(wanted))
	{
		e.ptime_who = strzone(wanted);
		PublicTime_Ask(e, wanted, FALSE);
	}
	else PublicTime_Ask(e, wanted, TRUE);
};

float(float reqid, float code, string body) PublicTime_Reply =
{
	local entity e;
	local int root, rows, row, activity;
	local float i, matches, exact, seconds, attempts, total;
	local string who, name, found;
	matches = exact = attempts = 0;
	found = "";
	e = findfloat(world, ptime_req, reqid);
	if (!reqid || !e) return FALSE;
	e.ptime_req = 0;
	if (!e.run_inserver || !e.acct_here || strcmp(e.ptime_map, mapname)) return TRUE;
	if (code || strlen(body) > 65536)
	{
		sprint(e, PRINT_HIGH, "^3time:^7 profile lookup unavailable; try again shortly\n");
		return TRUE;
	}
	root = json_parse(body);
	if (!root) { sprint(e, PRINT_HIGH, "^3time:^7 invalid profile reply\n"); return TRUE; }
	if (e.ptime_search)
	{
		rows = json_find_object_child(root, "players");
		for (i = 0; i < min(64, json_get_length(rows)); i = i + 1)
		{
			row = json_get_child_at_index(rows, i);
			who = json_get_string(json_find_object_child(row, "who"));
			name = PublicTime_Name(json_get_string(json_find_object_child(row, "name")));
			if (!PublicTime_Who(who)) continue;
			if (!strcmp(strtolower(name), strtolower(e.ptime_name)))
			{
				if (!exact) { matches = 0; exact = TRUE; }
				found = who;
				matches = matches + 1;
			}
			else if (!exact) { found = who; matches = matches + 1; }
		}
		if (matches == 1)
		{
			e.ptime_who = strzone(found);
			json_free(root);
			PublicTime_Ask(e, e.ptime_who, FALSE);
			return TRUE;
		}
		sprint(e, PRINT_HIGH, matches ? "^3time:^7 several profiles match; use the full name or public profile ID\n" : "^3time:^7 no public profile matches that name\n");
		json_free(root);
		return TRUE;
	}
	who = json_get_string(json_find_object_child(root, "who"));
	activity = json_find_object_child(root, "playtime");
	if (!PublicTime_Who(who) || strcmp(substring(who, 0, strlen(e.ptime_who)), e.ptime_who)
	    || strcasecmp(json_get_string(json_find_object_child(root, "on")), e.ptime_map))
		sprint(e, PRINT_HIGH, "^3time:^7 no matching public map profile was returned\n");
	else if (strcmp(json_get_string(json_find_object_child(activity, "scope")), "steam_linked_game"))
		sprint(e, PRINT_HIGH, "^3time:^7 playtime/attempt tracking is not available for this profile yet\n");
	else
	{
		seconds = max(0, json_get_float(json_find_object_child(activity, "map_seconds")));
		total = max(0, json_get_float(json_find_object_child(activity, "seconds")));
		rows = json_find_object_child(activity, "attempts");
		for (i = 0; i < min(1024, json_get_length(rows)); i = i + 1)
		{
			row = json_get_child_at_index(rows, i);
			if (json_get_float(json_find_object_child(row, "leg")) == 0)
				attempts = attempts + max(0, json_get_float(json_find_object_child(row, "n")));
		}
		name = Lobby_Clean(PublicTime_Name(json_get_string(json_find_object_child(root, "name"))));
		sprint(e, PRINT_HIGH, sprintf("^5time:^7 %s on %s: %gh %gm, %g main/bonus attempts",
		       name, e.ptime_map, floor(seconds / 3600), floor(seconds / 60) % 60, attempts));
		sprint(e, PRINT_HIGH, sprintf(" | total tracked playtime %gh %gm\n", floor(total / 3600), floor(total / 60) % 60));
	}
	json_free(root);
	return TRUE;
};
