// Menu-only adapter for P722's existing completed private snapshot and join flow.
// No backend/Steam/schema changes. Non-archived cvars carry no capability/address.
void() Friends_MenuClear =
{
	local float i;
	registercvar("ui_friends_count", "-1", 0);
	registercvar("ui_friends_epoch", "0", 0);
	registercvar("ui_friends_activity", "-1", 0);
	cvar_set("ui_friends_activity", "-1");
	cvar_set("ui_friends_count", "-1");
	cvar_set("ui_friends_epoch", ftos(cvar("ui_friends_epoch") + 1));
	for (i = 0; i < FR_MAX; i = i + 1)
	{
		registercvar(strcat("ui_friend_", ftos(i)), "", 0);
		cvar_set(strcat("ui_friend_", ftos(i)), "");
	}
};

void() Friends_MenuPublish =
{
	local float i, at;
	local string row;
	cvar_set("ui_friends_activity", fr_activity_capable ? ftos(cvar("ui_friends_epoch") + 1) : "-1");
	for (i = 0; i < FR_MAX; i = i + 1)
	{
		row = "";
		if (i < fr_n)
		{
			at = i * FR_FIELDS;
			row = strcat(sprintf("%s %s %s \"%s\" \"%s\" \"%s\" \"%s\"",
				bufstr_get(fr_buf, at), bufstr_get(fr_buf, at + 1), bufstr_get(fr_buf, at + 2),
				uri_escape(bufstr_get(fr_buf, at + 3)), uri_escape(bufstr_get(fr_buf, at + 4)),
				uri_escape(bufstr_get(fr_buf, at + 5)), uri_escape(bufstr_get(fr_buf, at + 6))),
				" ", bufstr_get(fr_buf, at + 7));
		}
		cvar_set(strcat("ui_friend_", ftos(i)), row);
	}
	cvar_set("ui_friends_count", ftos(fr_n));
	cvar_set("ui_friends_epoch", ftos(cvar("ui_friends_epoch") + 1));
};

void(string who) Friends_MenuJoin =
{
	local float i;
	i = Friends_Find(who);
	if (fr_ready && i >= 0)
	if (bufstr_get(fr_buf, i * FR_FIELDS + 1) == "3")
	if (bufstr_get(fr_buf, i * FR_FIELDS + 2) == "1")
	{
		Friends_Action("join", who);
		print("Friends: asking lobby to join friend\n");
	}
};
