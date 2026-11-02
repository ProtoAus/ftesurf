/*
  Patch 1195: a player's prederror report (cl_prederr.qc), stored in the lobbies' shared gamedir as
  data/prederr/<map>_<utc>_p<port>_s<slot>.txt.  Chunk 0 is "begin <stem> <chunks> <worst> <seq>";
  each chunk is answered with `prederr_ack <n>` so the client sends the next one only then, and a
  refusal ends the upload.  Streamed to disk (nothing held in RAM).  Caps, review 1: 400 chunks of
  1 KB whatever the client declares; per connection 3 a map and 20 s apart; per lobby 12 a map and
  10 s apart; and nothing is taken once PE_SV_STORE files are on the box (fetch and clear them).
*/
#define PE_SV_CHUNKS   400
#define PE_SV_CHUNK    1024
#define PE_SV_PERMAP   3
#define PE_SV_LOBBY    12
#define PE_SV_STORE    600

.float pe_open, pe_fh, pe_next, pe_total, pe_count, pe_last;
float  pe_lobby_n, pe_lobby_last;

// [A-Za-z0-9_.-] only: the stem goes into a header line and the map into a file name.
string(string s, float n) SV_PeSafe =
{
	local float i, c;
	local string o;
	o = "";
	for (i = 0; i < strlen(s) && i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if ((c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c == 45 || c == 46 || c == 95)
			o = strcat(o, chr2str(c));
		else
			o = strcat(o, "_");
	}
	return o;
};

float() SV_PeStored =
{
	local searchhandle h;
	local float n;
	h = search_begin("data/prederr/*.txt", FALSE, TRUE);
	if (h < 0)
		return 0;
	n = search_getsize(h);
	search_end(h);
	return n;
};

void(entity p) SV_PeClose =
{
	if (!p.pe_open)
		return;
	fclose(p.pe_fh);
	p.pe_open = FALSE;
};

void(entity p, string why) SV_PeRefuse =
{
	if (p.pe_open)
		fputs(p.pe_fh, sprintf("== refused %s\n", why));
	SV_PeClose(p);
	stuffcmd(p, sprintf("prederr_ack refused %s\n", why));
};

void(entity p, string s) SV_PeBegin =
{
	local float n, t;
	local string path;
	n = tokenize(s);
	if (n < 5 || argv(0) != "begin")
		return SV_PeRefuse(p, "header");
	t = stof(argv(2));
	if (!(t >= 1 && t <= PE_SV_CHUNKS) || t != floor(t))    // positive form: NaN fails it
		return SV_PeRefuse(p, "size");
	if (p.pe_count >= PE_SV_PERMAP)
		return SV_PeRefuse(p, "three-this-map");
	if (p.pe_count && time < p.pe_last + 20)
		return SV_PeRefuse(p, "wait");
	if (pe_lobby_n >= PE_SV_LOBBY || (pe_lobby_n && time < pe_lobby_last + 10))
		return SV_PeRefuse(p, "lobby-busy");
	if (SV_PeStored() >= PE_SV_STORE)
		return SV_PeRefuse(p, "store-full");
	path = sprintf("data/prederr/%s_%s_p%s_s%g.txt", SV_PeSafe(mapname, 64), strftime(FALSE, "%Y%m%d_%H%M%S"),
	               SV_PeSafe(cvar_string("sv_port"), 8), num_for_edict(p));
	p.pe_fh = fopen(path, FS_FILE_WRITESTREAM);
	if (p.pe_fh < 0)
		return SV_PeRefuse(p, "io");
	p.pe_open = TRUE;
	p.pe_total = t;
	p.pe_next = 1;
	p.pe_count = p.pe_count + 1;
	p.pe_last = time;
	pe_lobby_n = pe_lobby_n + 1;
	pe_lobby_last = time;
	fputs(p.pe_fh, "FTESURF-PREDERR 1\n");
	fputs(p.pe_fh, sprintf("lobby %s port %s\nmap %s\nutc %s servertime %.3f\n",
	                       strreplace("\n", " ", cvar_string("hostname")), cvar_string("sv_port"), mapname,
	                       strftime(FALSE, "%Y-%m-%d %H:%M:%S"), time));
	fputs(p.pe_fh, sprintf("player %s slot %g account %s ping %s\n",
	                       strreplace("\r", " ", strreplace("\n", " ", substring(p.netname, 0, 64))),
	                       num_for_edict(p), SV_PeSafe(infokey(p, "*ahash"), 64), infokey(p, "ping")));
	fputs(p.pe_fh, sprintf("client %s worst %.0f seq %.0f\n", SV_PeSafe(argv(1), 96), stof(argv(3)), stof(argv(4))));
	fputs(p.pe_fh, sprintf("server origin %v velocity %v movetype %g flags %g run_t_flags %g\n",
	                       p.origin, p.velocity, p.movetype, p.flags, p.run_t_flags));
	print(sprintf("prederr: report from %s -> %s\n", p.netname, path));
	stuffcmd(p, "prederr_ack 0\n");
};

void(float idx, string s) CSEv_pe_fs =
{
	if (self.classname != "player" || clienttype(self) != CLIENTTYPE_REAL)
		return;
	if (idx == 0)
	{
		SV_PeClose(self);
		SV_PeBegin(self, s);
		return;
	}
	if (!self.pe_open)
		return;                     // after a refusal or the end: dropped
	if (!(idx == self.pe_next && idx <= self.pe_total && idx <= PE_SV_CHUNKS))
		return SV_PeRefuse(self, "order");
	if (strlen(s) > PE_SV_CHUNK)
		return SV_PeRefuse(self, "chunk");
	fputs(self.pe_fh, s);
	self.pe_next = self.pe_next + 1;
	if (idx == self.pe_total)
	{
		fputs(self.pe_fh, "== end\n");
		SV_PeClose(self);
	}
	stuffcmd(self, sprintf("prederr_ack %g\n", idx));
};
