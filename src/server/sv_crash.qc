/*
  P1418: crash reports from players (cl_crash.qc), stored in data/crash/ beside the lobby with a header
  the client cannot write: lobby, map, player, account, engine version.  The channel and the limits
  mirror sv_prederr.qc's: chunk 0 is "begin <stem> <chunks>", then one chunk per crash_ack.  Raw
  reports are private (console lines carry names, chat and paths).
*/
#define CR_SV_CHUNKS   121
#define CR_SV_CHUNK    1024
#define CR_SV_LOBBY    6        // a lobby, per map
#define CR_SV_STORE    300

.float cr_open, cr_fh, cr_next, cr_total, cr_count;
float  cr_lobby_n, cr_lobby_last;

float() SV_CrStored =
{
	local searchhandle h;
	local float n;
	h = search_begin("data/crash/*.txt", FALSE, TRUE);
	if (h < 0)
		return 0;
	n = search_getsize(h);
	search_end(h);
	return n;
};

void(entity p) SV_CrClose =
{
	if (!p.cr_open)
		return;
	fclose(p.cr_fh);
	p.cr_open = FALSE;
};

void(entity p, string why) SV_CrRefuse =
{
	if (p.cr_open)
		fputs(p.cr_fh, sprintf("== refused %s\n", why));
	SV_CrClose(p);
	stuffcmd(p, sprintf("crash_ack refused %s\n", why));
};

void(entity p, string s) SV_CrBegin =
{
	local float n, t;
	local string path;
	n = tokenize(s);
	if (n < 3 || argv(0) != "begin")
		return SV_CrRefuse(p, "header");
	t = stof(argv(2));
	if (!(t >= 1 && t <= CR_SV_CHUNKS) || t != floor(t))    // positive form: NaN fails it
		return SV_CrRefuse(p, "size");
	if (p.cr_count)
		return SV_CrRefuse(p, "one-this-map");
	if (cr_lobby_n >= CR_SV_LOBBY || (cr_lobby_n && time < cr_lobby_last + 10))
		return SV_CrRefuse(p, "lobby-busy");
	if (SV_CrStored() >= CR_SV_STORE)
		return SV_CrRefuse(p, "store-full");
	path = sprintf("data/crash/%s_p%s_s%g.txt", strftime(FALSE, "%Y%m%d_%H%M%S"),
	               SV_PeSafe(cvar_string("sv_port"), 8), num_for_edict(p));
	p.cr_fh = fopen(path, FS_FILE_WRITESTREAM);
	if (p.cr_fh < 0)
		return SV_CrRefuse(p, "io");
	p.cr_open = TRUE;
	p.cr_total = t;
	p.cr_next = 1;
	p.cr_count = 1;
	cr_lobby_n = cr_lobby_n + 1;
	cr_lobby_last = time;
	fputs(p.cr_fh, "FTESURF-CRASH-LOBBY 1\n");
	fputs(p.cr_fh, sprintf("lobby %s port %s\nmap %s\nutc %s\n",
	                       strreplace("\n", " ", cvar_string("hostname")), cvar_string("sv_port"), mapname,
	                       strftime(FALSE, "%Y-%m-%d %H:%M:%S")));
	fputs(p.cr_fh, sprintf("player %s slot %g account %s engine %s\n",
	                       strreplace("\r", " ", strreplace("\n", " ", substring(p.netname, 0, 64))),
	                       num_for_edict(p), SV_PeSafe(infokey(p, "*ahash"), 64), SV_PeSafe(infokey(p, "*ver"), 96)));
	fputs(p.cr_fh, sprintf("client %s\n== client\n", SV_PeSafe(argv(1), 96)));
	print(sprintf("crash: report from %s -> %s\n", p.netname, path));
	stuffcmd(p, "crash_ack 0\n");
};

void(float idx, string s) CSEv_cr_fs =
{
	if (self.classname != "player" || clienttype(self) != CLIENTTYPE_REAL)
		return;
	if (idx == 0)
	{
		SV_CrClose(self);
		SV_CrBegin(self, s);
		return;
	}
	if (!self.cr_open)
		return;                     // after a refusal or the end: dropped
	if (!(idx == self.cr_next && idx <= self.cr_total && idx <= CR_SV_CHUNKS))
		return SV_CrRefuse(self, "order");
	if (strlen(s) > CR_SV_CHUNK)
		return SV_CrRefuse(self, "chunk");
	// Each client line under "| ": its console tail carries other players' chat, which may say "== end".
	if (substring(s, strlen(s) - 1, 1) == "\n")
		s = substring(s, 0, strlen(s) - 1);
	fputs(self.cr_fh, strcat("| ", strreplace("\n", "\n| ", s), "\n"));
	self.cr_next = self.cr_next + 1;
	if (idx == self.cr_total)
	{
		fputs(self.cr_fh, "== end\n");
		SV_CrClose(self);
	}
	stuffcmd(self, sprintf("crash_ack %g\n", idx));
};
