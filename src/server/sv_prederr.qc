/*
  Patch 1195: a player's prederror report (cl_prederr.qc), stored in the lobbies' shared gamedir as
  data/prederr/<map>_<utc>_p<port>_s<slot>.txt.  Chunk 0 is "begin <stem> <chunks> <worst> <seq>";
  each chunk is answered with `prederr_ack <n>` so the client sends the next one only then, and a
  refusal ends the upload.  Streamed to disk (nothing held in RAM).  Caps, review 1: 400 chunks of
  1 KB whatever the client declares; per connection 3 a map and 20 s apart; per lobby 12 a map and
  10 s apart; and nothing is taken once PE_SV_STORE files are on the box (fetch and clear them).

  P1238: the server's own side.  Every command a player runs adds one row to that player's ring:
  P675's context (kind 1 network, 2 timestamp-split, 0 a loss fill or untagged) and time taken at
  its PlayerPreThink, the body written at the next one, after PlayerPostThink's pins and teleports
  (PostThink runs once a packet, not once a command).  The client marks a report the moment it sees the error (CSEv_pe_mk_f); 1.6 s later
  the ring is frozen, and the upload writes it as "== server" with the stalls around it.
*/
#define PE_SV_CHUNKS   400
#define PE_SV_CHUNK    1024
#define PE_SV_PERMAP   3
#define PE_SV_LOBBY    12
#define PE_SV_STORE    600

.float pe_open, pe_fh, pe_next, pe_total, pe_count, pe_last;
float  pe_lobby_n, pe_lobby_last;

#define PE_SV_ROWS     512      // ~7.7 s at 66 commands a second
#define PE_SV_HITCHES  32
.float pe_rb, pe_rn;            // per-command ring: strbuf + 1 (0 = none; fields clear at a map change), rows ever
.float pe_sb, pe_sn;            // the frozen snapshot: strbuf + 1, rows
.float pe_mk_due, pe_mk_seq, pe_mk_t, pe_mk_last, pe_sn_seq, pe_sn_t;
.float pe_ck, pe_cs, pe_cm, pe_cp, pe_co, pe_ci;   // the pending command's context, from its PlayerPreThink
.float pe_ct, pe_crt, pe_cpend;                    // ...its time and realtime, and whether one is pending
float  pe_hit_t[PE_SV_HITCHES], pe_hit_d[PE_SV_HITCHES];
float  pe_hit_n, pe_rt_last;    // server frames longer than 50 ms: lobby-wide, newest PE_SV_HITCHES

// P1404: a rig replay's start (cl_prederr.qc pe_replay), sv_cheats only: the state lands before the
// first command at or past pe_st_seq, so the replayed rows start from the report's server state.
.float  pe_st_seq;
.vector pe_st_org, pe_st_vel;
.string pe_st_name;                 // P1405: the activator name the report recorded
.float  pe_st_hasname;              // ...when it gave one ("" included: a cleared name is a name)

// P1405: each player's targetname as infokey *tn, so the client judges name filters itself (maps rename
// the player with AddOutput: stage-nexus teleports, bhop block resets). Checked once a packet against the
// key itself: star keys outlive a changelevel or map_restart, which clears the edict (review 2).
float   pe_tn_live;
void(entity p) SV_PeNameSync =
{
	if (infokey(p, "*tn") != p.targetname)
		forceinfokey(p, "*tn", p.targetname);
};

void(entity p, float argc) SV_PeStateCmd =
{
	if (cvar("sv_cheats") != 1)
	{
		sprint(p, PRINT_HIGH, "pe_state: needs sv_cheats 1\n");
		return;
	}
	if (argc < 8)
	{
		sprint(p, PRINT_HIGH, "pe_state <command> <origin> <velocity>\n");
		return;
	}
	p.pe_st_seq = stof(argv(1));
	p.pe_st_org = [stof(argv(2)), stof(argv(3)), stof(argv(4))];
	p.pe_st_vel = [stof(argv(5)), stof(argv(6)), stof(argv(7))];
	p.pe_st_hasname = (argc >= 9);
	p.pe_st_name = p.pe_st_hasname ? strzone(argv(8)) : "";
};

// StartFrame: a server frame that started 50+ ms after the last one.
void() SV_PeFrame =
{
	local float rt, i;
	if (!pe_tn_live)                    // P1405: before any client loads its triggers
	{
		pe_tn_live = TRUE;
		forceinfokey(world, "fs_tn", "1");
	}
	rt = gettime(0);
	if (pe_rt_last > 0 && rt - pe_rt_last > 0.05)
	{
		i = pe_hit_n - floor(pe_hit_n / PE_SV_HITCHES) * PE_SV_HITCHES;
		pe_hit_t[i] = time;
		pe_hit_d[i] = rt - pe_rt_last;
		pe_hit_n = pe_hit_n + 1;
	}
	pe_rt_last = rt;
};

void(entity p) SV_PeSnap =
{
	local float i, i0, b;
	p.pe_mk_due = 0;
	if (!p.pe_rb)
		return;
	if (p.pe_sb)
		buf_del(p.pe_sb - 1);
	b = buf_create();
	p.pe_sb = b + 1;
	i0 = max(0, p.pe_rn - PE_SV_ROWS);
	for (i = i0; i < p.pe_rn; i = i + 1)
		bufstr_add(b, bufstr_get(p.pe_rb - 1, i - floor(i / PE_SV_ROWS) * PE_SV_ROWS), TRUE);
	p.pe_sn = p.pe_rn - i0;
	p.pe_sn_seq = p.pe_mk_seq;
	p.pe_sn_t = p.pe_mk_t;
};

// The pending command's row: its context and time, and the body as it stands now.  Columns are in
// the == server header line.
void(entity p) SV_PeRow =
{
	local float b;
	p.pe_cpend = FALSE;
	if (!p.pe_rb)
		p.pe_rb = buf_create() + 1;
	b = p.pe_rb - 1;
	bufstr_set(b, p.pe_rn - floor(p.pe_rn / PE_SV_ROWS) * PE_SV_ROWS,
	           strcat(sprintf("%.3f %.3f %g %.0f %g %g %g ", p.pe_ct, p.pe_crt, p.pe_ck, p.pe_cs,
	                          p.pe_cm, p.pe_cp, p.pe_co),
	                  sprintf("%.2f %.2f %.2f %.1f %.1f %.1f ", p.origin_x, p.origin_y, p.origin_z,
	                          p.velocity_x, p.velocity_y, p.velocity_z),
	                  sprintf("%g %g %g", p.movetype, (p.flags & FL_ONGROUND) ? 1 : 0, p.pe_ci)));
	p.pe_rn = p.pe_rn + 1;
	if (p.pe_mk_due && time >= p.pe_mk_due)
		SV_PeSnap(p);
};

// The top of PlayerPreThink, once per command part (loss fills and tick parts included): the last
// command's row, then this one's context, which sv_user.c publishes around PlayerPreThink only.
void(entity p) SV_PeCmd =
{
	if (clienttype(p) != CLIENTTYPE_REAL)
		return;
	if (p.pe_cpend)
		SV_PeRow(p);
	p.pe_ck = input_cmd_kind;
	p.pe_cs = input_cmd_sequence_hi * 65536 + input_cmd_sequence_lo;
	p.pe_cm = input_cmd_msec;
	p.pe_cp = input_cmd_piece_msec;
	p.pe_co = input_cmd_offset_msec;
	p.pe_ci = input_impulse;
	p.pe_ct = time;
	p.pe_crt = gettime(1);
	p.pe_cpend = TRUE;
};

// The client saw an error at its command `seq`; freeze the ring once the commands after it ran.
void(float seq) CSEv_pe_mk_f =
{
	if (self.classname != "player" || clienttype(self) != CLIENTTYPE_REAL)
		return;
	if (self.pe_mk_due || (self.pe_mk_last && time < self.pe_mk_last + 10) || !(seq >= 0))
		return;
	self.pe_mk_last = time;
	self.pe_mk_due = time + 1.6;
	self.pe_mk_seq = floor(seq);
	self.pe_mk_t = time;
};

void(entity p) SV_PeForget =
{
	if (p.pe_rb)
		buf_del(p.pe_rb - 1);
	if (p.pe_sb)
		buf_del(p.pe_sb - 1);
	p.pe_rb = p.pe_rn = p.pe_sb = p.pe_sn = p.pe_mk_due = p.pe_cpend = 0;
};

// The frozen ring, if it is this report's: its mark within 1000 commands of the worst line.
void(entity p, float worstseq) SV_PeWriteServer =
{
	local float i, j, k;
	if (p.pe_mk_due)
		SV_PeSnap(p);               // sent before the freeze was due: the rows so far
	if (!p.pe_sb)
	{
		fputs(p.pe_fh, "== server none (no mark from this client on this map)\n");
		return;
	}
	if (!(fabs(p.pe_sn_seq - worstseq) <= 1000))       // positive form: NaN fails it
	{
		fputs(p.pe_fh, sprintf("== server none (the last mark was seq %.0f)\n", p.pe_sn_seq));
		return;
	}
	fputs(p.pe_fh, "== server\n");
	fputs(p.pe_fh, sprintf("FTESURF-PREDSV 1\nmark seq %.0f at %.3f; rows %g; sv_fps %s sv_mintic %s sv_maxtic %s\n",
	                       p.pe_sn_seq, p.pe_sn_t, p.pe_sn, cvar_string("sv_fps"), cvar_string("sv_mintic"),
	                       cvar_string("sv_maxtic")));
	fputs(p.pe_fh, sprintf("packet stalls %g credited %g (%.3f s)\n", p.run_t_ckgaps, p.run_t_ckncr, p.run_t_ckcr));
	k = max(0, pe_hit_n - PE_SV_HITCHES);
	for (i = k; i < pe_hit_n; i = i + 1)
	{
		j = i - floor(i / PE_SV_HITCHES) * PE_SV_HITCHES;
		if (fabs(pe_hit_t[j] - p.pe_sn_t) < 15)
			fputs(p.pe_fh, sprintf("stall %.3f %.0f ms\n", pe_hit_t[j], pe_hit_d[j] * 1000));
	}
	fputs(p.pe_fh, "# time realtime kind seq msec piece offset org(3) vel(3) movetype onground impulse\n");
	for (i = 0; i < p.pe_sn; i = i + 1)
		fputs(p.pe_fh, strcat(bufstr_get(p.pe_sb - 1, i), "\n"));
};

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
	SV_PeWriteServer(p, stof(argv(4)));     // P1238
	fputs(p.pe_fh, "== client\n");         // what follows is the client's: the triage reads no server rows there
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
