/* Patch 502: bounded snapshots of the existing save-state contract.
   Included by sv_saveloc.qc after its ring globals. No new evidence grammar:
   a rewind writes the same state and prefix a normal save/load consumes. */

void(entity e, float b) SV_RewindStateSample =
{
	local float *m;
	local float i;
	local int bytes;
	m = rw_slot[num_for_edict(e)];
	m[b+10] = e.run_t_track;
	m[b+11] = e.run_t_startseg;
	m[b+12] = e.run_t_stagerun;
	m[b+13] = e.run_t_seg;
	m[b+14] = e.run_t_segs;
	m[b+15] = SV_TimerElapsed(e);
	m[b+16] = e.run_t_split;
	m[b+17] = e.run_t_delta;
	m[b+18] = e.run_t_flags - (e.run_t_flags & (TF_FROZEN | TF_STOPPED | TF_NONCE));
	m[b+19] = e.run_t_pb;
	m[b+20] = e.run_t_dirty;
	m[b+21] = e.run_t_cheat;
	m[b+22] = e.run_t_hopped;
	m[b+23] = e.run_t_fromsave;
	m[b+24] = e.run_t_azone;
	m[b+25] = e.run_t_evzone;
	m[b+26] = e.run_t_armzone;
	m[b+27] = e.run_t_cpzone;
	m[b+28] = e.run_t_cpmax;
	m[b+29] = e.rec_rec_lines;
	m[b+30] = e.rec_rec_n;
	m[b+31] = e.rec_rec_padn;
	m[b+32] = e.rec_rec_cp;
	m[b+33] = e.rec_rec_serial;
	m[b+34] = e.rec_rec_gen;
	m[b+35] = e.rec_rec_ver;
	m[b+36] = e.rec_rec_flagofs;
	m[b+37] = e.rec_rec_sesspend;
	m[b+38] = e.rec_rec_in;
	m[b+39] = e.rec_rec_pk;
	m[b+40] = e.rec_rec_warp;
	m[b+41] = e.rec_rec_ride;
	m[b+42] = e.rec_rec_pm;
	m[b+43] = e.rec_rec_pe;
	m[b+44] = e.rec_rec_portal;
	m[b+45] = e.rec_rec_pinned;
	m[b+46] = e.rec_rec_pauses;
	m[b+47] = e.rec_rec_sess;
	m[b+48] = e.rec_rec_inmt;
	m[b+49] = e.rec_rec_incy;
	m[b+50] = e.run_t_handcarry;
	m[b+51] = e.run_t_clock;
	m[b+54] = e.run_t_pendarm;
	// Two exact 16-bit limbs, never a byte offset rounded through float32.
	bytes = 0i;
	if (e.rec_rec_stream && e.rec_rec_fh >= 0)
		bytes = fseek(e.rec_rec_fh);
	m[b+52] = bytes >> 16i;
	m[b+53] = bytes & 65535i;
	for (i = 1; i < FS_MAXSPLITS; i = i + 1)
		m[b+RW_SPLITBASE+i] = SV_TimerGetRunSplit(e, i);
	for (i = 1; i < FS_MAXCPS; i = i + 1)
		m[b+RW_CPBASE+i] = SV_TimerGetRunCP(e, i);
};

float(entity e, float id, float seq, float go) SV_RewindWriteState =
{
	local float *m;
	local float b, f, fh, i, mark;
	local int bytes;
	local string path;
	m = rw_slot[num_for_edict(e)];
	b = rw_statebase;
	mark = m[b+29];
	// An ended run's part/buffer may have gone. Its physics still make a save,
	// but it cannot claim a clock with no prefix behind it.
	if (!(m[b+18] & TF_RECORDING) || mark <= 0)
		return FALSE;
	if (e.rec_rec_serial != m[b+33] || e.rec_rec_lines < mark)
		return FALSE;
	if (!SV_RecCutOK(e, m[b+34], mark))
		return FALSE;                 // regrowth cannot resurrect an abandoned prefix
	bytes = ((int)m[b+52] << 16i) | (int)m[b+53];
	if (e.rec_rec_stream)
	if (bytes <= 0i || bytes > FS_RECCOPY_MAX)
		return FALSE;
	path = SL_RecPath(id);
	if (bytes > 0i)
	{
		if (!e.rec_rec_stream || e.rec_rec_fh < 0)
			return FALSE;
		if (fsize(e.rec_rec_fh) < bytes)
			return FALSE;
		if (e.rec_cp_q < 1)
		{
			e.rec_cp_q = buf_create_ex("string", 0);
			e.rec_cp_head = 0;
		}
		if (e.rec_cp_q < 1)
			return FALSE;
		SV_RecCopyDrop(path);
		bufstr_set(e.rec_cp_q, buf_getsize(e.rec_cp_q),
		           sprintf("%s 0 %s %s", itos(bytes), SV_RecPartPath(e), path));
	}
	else
	{
		if (e.rec_rec_buf < 1)
			return FALSE;
		fh = fopen(path, FILE_WRITE);
		if (fh < 0)
			return FALSE;
		buf_writefile(fh, e.rec_rec_buf, 0, mark);
		fclose(fh);
	}
	f = fopen(SL_StatePath(id), FILE_WRITE);
	if (f < 0)
		return FALSE;
	fputs(f, sprintf("FTESURF-SAVE %d\nmap %s\nmapcrc %s\nseq %d\n",
	                 SL_STATE_VERSION, mapname, infokey(world, "*mapcrc"), seq));
	fputs(f, sprintf("created %s\nclock %s\n", strftime(TRUE, "%Y%m%d-%H%M%S"),
	                 m[b+51] ? "counted" : "sampled"));
	fputs(f, sprintf("origin %.4f %.4f %.4f\nvelocity %.4f %.4f %.4f\n",
	                 rw_o_x, rw_o_y, rw_o_z, rw_v_x, rw_v_y, rw_v_z));
	fputs(f, sprintf("angles %.4f %.4f\nduck %d\nstate %d\nticks %d\nelapsed %.6f\n",
	                 rw_pit, rw_yaw, rw_dk, TS_RUNNING, rw_t, m[b+15]));
	fputs(f, sprintf("track %d\nstartseg %d\nstagerun %d\nseg %d\nsegs %d\nsplit %d\ndelta %d\n",
	                 m[b+10], m[b+11], m[b+12], m[b+13], m[b+14], m[b+16], m[b+17]));
	fputs(f, sprintf("flags %d\npb %d\ndirty %d\ncheat %d\nhopped %d\nfromsave %d\nhandcarry %d\n",
	                 m[b+18], m[b+19], m[b+20], m[b+21], m[b+22], m[b+23], m[b+50]));
	fputs(f, sprintf("azone %d\nevzone %d\narmzone %d\ncpzone %d\ncpmax %d\npendarm %d\n",
	                 m[b+24], m[b+25], m[b+26], m[b+27], m[b+28], m[b+54]));
	for (i = 1; i < FS_MAXSPLITS; i = i + 1)
		if (m[b+RW_SPLITBASE+i] > 0)
			fputs(f, sprintf("runsplit %d %d\n", i, m[b+RW_SPLITBASE+i]));
	for (i = 1; i < FS_MAXCPS; i = i + 1)
		if (m[b+RW_CPBASE+i] > 0)
			fputs(f, sprintf("runcp %d %d\n", i, m[b+RW_CPBASE+i]));
	fputs(f, sprintf("reclines %d\nrecsamples %d\nrecpad %d\nreccp %d\nrecserial %d\nrecgen %d\n",
	                 mark, m[b+30], m[b+31], m[b+32], m[b+33], m[b+34]));
	// The snapshot's serial/cut gate above proves this is still its attachment.
	if (strcmp(e.rec_rec_branch, ""))
		fputs(f, sprintf("recbranch %s\n", e.rec_rec_branch));
	if (strcmp(e.rec_rec_rid, ""))
		fputs(f, sprintf("recrid %s\n", e.rec_rec_rid));
	if (bytes > 0i)
	{
		fputs(f, sprintf("recbytes %s\nrecstream %d %d %d\n", itos(bytes), m[b+35], m[b+36], m[b+37]));
		fputs(f, sprintf("recrows %d %d %d %d\n", m[b+38], m[b+39], m[b+40], m[b+41]));
		fputs(f, sprintf("recstate %d %d %d %d\n", m[b+42], m[b+43], m[b+44], m[b+45]));
		fputs(f, sprintf("recsess %d %d\n", m[b+46], m[b+47]));
		if (m[b+48] >= 0)
			fputs(f, sprintf("reclast %d %.9g\n", m[b+48], m[b+49]));
	}
	if (go)
		fputs(f, sprintf("rewindgo %d\n", seq));
	fclose(f);
	return TRUE;
};
