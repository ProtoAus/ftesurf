/*
  P1382: a player's missing-material report (cl_gfx.qc Gfx_MissingReport), one line appended to
  data/matreport/<port>_<yyyymmdd>.txt in the lobbies' shared gamedir. Caps: one a connection a map,
  24 a lobby a map, 900 bytes, and nothing once MMR_STORE files are on the box (fetch and clear them).
*/
#define MMR_PERLOBBY    24
#define MMR_STORE       400

.float mmr_sent;                // fields clear at a map change
float  mmr_lobby_n;

void(string s) CSEv_mmr_s =
{
	local searchhandle h;
	local float n, fh;
	local string path;

	if (self.mmr_sent || mmr_lobby_n >= MMR_PERLOBBY || strlen(s) > 900)
		return;
	self.mmr_sent = TRUE;
	h = search_begin("data/matreport/*.txt", FALSE, TRUE);
	n = 0;
	if (h >= 0)
	{
		n = search_getsize(h);
		search_end(h);
	}
	path = sprintf("data/matreport/%s_%s.txt", SV_PeSafe(cvar_string("sv_port"), 8), strftime(FALSE, "%Y%m%d"));
	if (n >= MMR_STORE)
	{
		fh = fopen(path, FILE_READ);   // a full store still takes today's file
		if (fh < 0)
			return;
		fclose(fh);
	}
	fh = fopen(path, FILE_APPEND);
	if (fh < 0)
		return;
	mmr_lobby_n = mmr_lobby_n + 1;
	fputs(fh, sprintf("%s utc map %s player %s ver %s %s\n", strftime(FALSE, "%Y-%m-%d %H:%M:%S"), mapname,
	                  SV_PeSafe(self.netname, 32), SV_PeSafe(infokey(self, "*ver"), 80),
	                  strreplace("\n", " ", strreplace("\r", " ", s))));
	fclose(fh);
	print(sprintf("matreport: %s on %s\n", SV_PeSafe(self.netname, 32), mapname));
};
