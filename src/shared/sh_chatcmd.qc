// FTESurf Patch 1295: a chat warp command as people type it -- "!b3", "/b 3", "/B3" -- read as "!b 3". A leading '/'
// counts as '!'; one of !m !s !b !r glued to its digits is split from them. Anything else comes back as it came, lower
// case. The server parser (sv_player.qc), the client's prediction (cl_warpop.qc) and the global-room check (cl_chat.qc)
// all read it, so a variant warps, is predicted and stays in its lobby exactly as "!b 3" does.
string(string text) ChatCmd_Normalize =
{
	local string t, w;
	local float i, ch, sp;
	t = strtolower(strtrim(text));
	if (substring(t, 0, 1) == "/")
		t = strcat("!", substring(t, 1, strlen(t) - 1));
	sp = strstrofs(t, " ", 0);
	w = (sp < 0) ? t : substring(t, 0, sp);
	if (strlen(w) < 3 || substring(w, 0, 1) != "!")
		return t;
	ch = str2chr(w, 1);
	if (ch != 'm' && ch != 's' && ch != 'b' && ch != 'r')
		return t;
	for (i = 2; i < strlen(w); i = i + 1)
	{
		ch = str2chr(w, i);
		if (ch < '0' || ch > '9')
			return t;
	}
	if (sp < 0)
		return strcat(substring(w, 0, 2), " ", substring(w, 2, strlen(w) - 2));
	return strcat(substring(w, 0, 2), " ", substring(w, 2, strlen(w) - 2), substring(t, sp, strlen(t) - sp));
};
