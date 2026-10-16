// Test-only dispatcher overlay. Never deploy fixture progs.
#undef SV_ParseClientCommand
#undef PutClientInServer
float sm_checks, sm_failed;

void(float ok, string label) SM_Check =
{
	sm_checks += 1;
	if (!ok)
	{
		sm_failed += 1;
		bprint(2, strcat("SAVEMARKER FAIL ", label, "\n"));
	}
};

// Distinguish absent keys from explicitly empty markers.
string(float id) SM_ReadName =
{
	local float f, n;
	local string line, value;
	value = "<absent>";
	f = fopen(SL_StatePath(id), FILE_READ);
	if (f < 0) return "<missing-file>";
	while ((line = fgets(f)) != "")
	{
		n = tokenize(line);
		if (n >= 2)
		if (argv(0) == "targetname") value = argv(1);
	}
	fclose(f);
	return value;
};

void(entity e) SM_Run =
{
	local string root, special;
	local entity trig, output, cleanup, endall, counter, filt, peer, savedself;
	local float b, i, blk, row, f, mp;
	local float *m;
	local int bit, peerbit;
	sm_checks = sm_failed = 0;
	SM_Check(e.classname == "player" && e.run_inserver, "real connected player actor");
	SM_Check(e.run_t_state == TS_RUNNING && (e.run_t_flags & TF_RECORDING)
		&& e.rec_rec_buf > 0 && e.rec_rec_lines > 0 && e.rw_n > 0,
		"walked recording and warm ring actor");
	if (!(e.run_t_flags & TF_RECORDING) || e.rec_rec_buf < 1 || e.rw_n < 1)
	{
		bprint(2, "SAVEMARKER SETUP FAILED\n"); return;
	}
	root = strzone(sl_root); mp = vbsp_mp;
	SV_SaveRootFor(e);
	m = rw_slot[num_for_edict(e)];
	b = ((e.rw_head - 1 + RW_CAP) % RW_CAP) * RW_STRIDE;
	e.targetname = "block1";
	SV_RewindStateSample(e, b);
	SM_Check(SV_RewindFind(e, m[b], e.origin, TRUE), "warm sample selection actor");
	e.targetname = "block2";
	SM_Check(SV_SaveWriteAt(e, 701, 701, FALSE), "recorded rewind writer actor");
	SM_Check(!strcmp(SM_ReadName(701), "block1"), "recorded rewind uses sampled not present marker");
	m[b+18] = m[b+18] - (m[b+18] & TF_RECORDING);
	SM_Check(SV_SaveWriteAt(e, 702, 702, FALSE), "position-only rewind writer actor");
	SM_Check(!strcmp(SM_ReadName(702), "block1"), "position-only rewind retains sample marker");
	// Physical last and first rows exercise wrap/overwrite without a long fake run.
	e.targetname = "last-row"; SV_RewindStateSample(e, (RW_CAP - 1) * RW_STRIDE);
	e.targetname = "wrapped-row"; SV_RewindStateSample(e, 0);
	e.targetname = "present-row";
	rw_statebase = (RW_CAP - 1) * RW_STRIDE;
	m[rw_statebase+18] = 0;
	SM_Check(SV_SaveWriteAt(e, 703, 703, FALSE) && !strcmp(SM_ReadName(703), "last-row"), "ring last row independent");
	rw_statebase = 0; m[18] = 0;
	SM_Check(SV_SaveWriteAt(e, 704, 704, FALSE) && !strcmp(SM_ReadName(704), "wrapped-row"), "ring wrapped row independent");
	e.targetname = "replacement"; SV_RewindStateSample(e, 0); m[18] = 0;
	SM_Check(SV_SaveWriteAt(e, 705, 705, FALSE) && !strcmp(SM_ReadName(705), "replacement"), "ring overwrite replaces old marker");
	e.targetname = ""; SV_RewindStateSample(e, 0); m[18] = 0;
	SM_Check(SV_SaveWriteAt(e, 707, 707, FALSE) && !strcmp(SM_ReadName(707), ""), "ring captured empty marker is not absent");
	rw_statebase = -1;
	SM_Check(SV_SaveWriteAt(e, 706, 706, FALSE) && !strcmp(SM_ReadName(706), "<absent>"), "unsampled replay does not invent progress");

	SV_TimerVoid(e, "save marker fixture");
	// Exercise the actual save/load dispatcher, not only the state helpers.
	e.targetname = "filter_name_1";
	MP_TestOriginalCommand("sl_save");
	blk = SL_Blk(e); row = SL_Base(blk) + e.rec_sl_index - 1;
	SM_Check(rec_sl_nb[blk] == 1, "save dispatcher created actual row");
	SM_Check(!strcmp(SM_ReadName(rec_sl_id[row]), "filter_name_1"), "ordinary save captures marker");
	e.targetname = "filter_name_2";
	MP_TestOriginalCommand("sl_load");
	SM_Check(!strcmp(e.targetname, "filter_name_1"), "ordinary load restores earlier progress");
	MP_TestOriginalCommand("sl_hold");
	SM_Check(e.rec_sl_hold && e.movetype == MOVETYPE_NONE, "real save lock hold actor");
	MP_TestOriginalCommand("sl_holdoff");
	SM_Check(!e.rec_sl_hold && !strcmp(e.targetname, "filter_name_1"), "release retains restored progress");

	// Both actual map filter predicates, with wrong-marker controls that ACT.
	filt = spawn(); filt.classname = "filter_activator_name";
	filt.filtername = "filter_name_1"; filt.Negated = TRUE;
	SM_Check(!SV_FilterPasses(filt, e), "Monolith B4 restored marker suppresses reset");
	e.targetname = "filter_name_2";
	SM_Check(SV_FilterPasses(filt, e), "Monolith B4 wrong marker still resets");
	filt.filtername = "block2"; filt.Negated = FALSE;
	e.targetname = "block1"; SV_SaveWriteState(e, 710, 710);
	e.targetname = "block2";
	SM_Check(SV_FilterPasses(filt, e), "futile wrong later marker resets");
	SM_Check(SV_SaveApplyState(e, 710, FALSE) && !strcmp(e.targetname, "block1")
		&& !SV_FilterPasses(filt, e), "futile restored earlier marker suppresses reset");

	// Quoted markers must not corrupt following state keys; empty is NOT absent.
	special = "name with spaces";
	e.targetname = special; SV_SaveWriteState(e, 711, 711); e.targetname = "changed";
	SM_Check(SV_SaveApplyState(e, 711, FALSE) && !strcmp(e.targetname, special), "quoted whitespace marker roundtrip");
	special = "name \"quoted\" \\tail";
	e.targetname = special; SV_SaveWriteState(e, 711, 711); e.targetname = "changed";
	SM_Check(SV_SaveApplyState(e, 711, FALSE) && !strcmp(e.targetname, special), "quoted backslash marker roundtrip");
	e.targetname = ""; SV_SaveWriteState(e, 712, 712); e.targetname = "block2";
	SM_Check(!strcmp(SM_ReadName(712), ""), "empty marker explicitly serialized");
	SM_Check(SV_SaveApplyState(e, 712, FALSE) && !strcmp(e.targetname, ""), "empty marker clears later progress");
	// Retry and multi-session share this state reader, including cold players.
	for (i = 1; i <= 2; i += 1)
	{
		e.targetname = "";
		SM_Check(SV_SaveApplyState(e, 710, i) && !strcmp(e.targetname, "block1"), "retry/resume cold state reader marker");
	}
	// A demote rewrite must preserve the ORIGINAL file's marker and absence.
	row = SL_Base(blk) + rec_sl_nb[blk];
	e.targetname = "demoted-original"; SV_SaveWriteState(e, 713, 713);
	rec_sl_id[row] = rec_sl_seq[row] = 713; rec_sl_org[row] = e.origin;
	rec_sl_tick[row] = 123;
	f = fopen(SL_StatePath(713), FILE_APPEND); fputs(f, "ticks 123\n"); fclose(f);
	e.targetname = "demoting-current"; SV_SaveDemote(row);
	SM_Check(rec_sl_tick[row] == SL_DEMOTED && !strcmp(SM_ReadName(713), "demoted-original"), "demote preserves old file marker");
	SM_Check(SV_SaveApplyState(e, 713, FALSE) && !strcmp(e.targetname, "demoted-original"), "demoted marker restores");
	f = fopen(SL_StatePath(714), FILE_WRITE);
	fputs(f, "FTESURF-SAVE 1\nseq 714\nticks 123\norigin 0 0 0\n"); fclose(f);
	rec_sl_id[row] = rec_sl_seq[row] = 714; rec_sl_org[row] = '0 0 0'; rec_sl_tick[row] = 123;
	SV_SaveDemote(row);
	SM_Check(!strcmp(SM_ReadName(714), "<absent>"), "legacy demote does not manufacture marker");
	e.targetname = "legacy-current";
	SM_Check(SV_SaveApplyState(e, 714, FALSE) && !strcmp(e.targetname, "legacy-current"), "legacy absence keeps prior behavior after named read");

	// Stale EndTouch must not reapply abandoned progress, in MP or legacy mode.
	trig = spawn(); output = spawn(); cleanup = spawn(); endall = spawn(); counter = spawn();
	counter.classname = "math_counter"; counter.targetname = "sm_end_all";
	trig.vbsp_io_out = output; output.owner = trig;
	output.vbsp_io_next = cleanup; cleanup.owner = trig; cleanup.vbsp_io_next = endall;
	cleanup.vbsp_io_name = "onendtouch"; cleanup.vbsp_io_target = "!activator";
	cleanup.vbsp_io_input = "AddOutput"; cleanup.vbsp_io_param = "gravity 1";
	cleanup.vbsp_io_times = -1;
	endall.owner = trig; endall.vbsp_io_name = "onendtouchall";
	endall.vbsp_io_target = "sm_end_all"; endall.vbsp_io_input = "Add";
	endall.vbsp_io_param = "1"; endall.vbsp_io_times = -1;
	output.vbsp_io_name = "onendtouch"; output.vbsp_io_target = "!activator";
	output.vbsp_io_input = "AddOutput"; output.vbsp_io_param = "targetname abandoned";
	output.vbsp_io_times = -1;
	peer = edict_num(2); peer.targetname = "peer-marker";
	bit = (int)1 << ((int)num_for_edict(e) - 1i); peerbit = 2i;
	for (i = 0; i < 2; i += 1)
	{
		vbsp_mp = i;
		trig.vbsp_touch_who = (i == 0) ? e : world; trig.vbsp_touch_when = time - 1;
		trig.vbsp_touch_in = (i == 1) ? bit : 0; trig.vbsp_touch_out = trig.vbsp_touch_in;
		trig.vbsp_touch_seen = 0;
		trig.vbsp_once_done = bit | peerbit; trig.vbsp_io_gate_seen = bit | peerbit;
		e.targetname = "abandoned"; e.gravity = 0.25; counter.count = 0;
		SM_Check(SV_SaveApplyState(e, 710, FALSE), "stale exit load actor");
		savedself = self; self = trig; SV_TriggerEndThink(); self = savedself;
		SM_Check(!strcmp(e.targetname, "block1"), "stale EndTouch cannot overwrite restored marker");
		SM_Check(e.gravity == 1, "non-name exit cleanup retained");
		SM_Check(counter.count == 1, "last-occupant cleanup delivered exactly once");
		SM_Check(trig.vbsp_once_done == (bit | peerbit) && trig.vbsp_io_gate_seen == (bit | peerbit), "once/cooldown progress not erased");
	}
	vbsp_mp = 1; counter.count = 0;
	trig.vbsp_touch_in = bit | peerbit; trig.vbsp_touch_seen = peerbit; trig.vbsp_touch_out = 0;
	SM_Check(SV_SaveApplyState(e, 710, FALSE), "peer occupancy load actor");
	SM_Check(trig.vbsp_touch_in == peerbit && trig.vbsp_touch_seen == peerbit
		&& !strcmp(peer.targetname, "peer-marker"), "other player marker and occupancy retained");
	SM_Check(counter.count == 0, "peer occupancy prevents premature last-occupant output");
	// Positive exit control proves the same output really renames its activator.
	trig.vbsp_touch_in = bit; trig.vbsp_touch_out = bit; trig.vbsp_touch_seen = 0;
	savedself = self; self = trig; SV_TriggerEndThink(); self = savedself;
	SM_Check(!strcmp(e.targetname, "abandoned"), "real EndTouch still updates map progress");
	SM_Check(counter.count == 1, "real final exit still fires EndTouchAll once");
	vbsp_mp = mp;
	remove(output); remove(cleanup); remove(endall); remove(counter); remove(trig); remove(filt);
	sl_root = root; strunzone(root);
	bprint(2, sprintf("SAVEMARKER COMPLETE checks=%d failed=%d\n", sm_checks, sm_failed));
};

void(string s) SV_ParseClientCommand =
{
	if (s == "p735_savemarker") { SM_Run(self); return; }
	if (s == "p735_retry")
	{
		self.targetname = "retry-marker";
		registercvar("p735_expect_cold", "0");
		cvar_set("p735_expect_cold", "1");
		MP_TestOriginalCommand("rec_retry");
		bprint(2, sprintf("SAVEMARKER RETRY ACTOR sent=%d\n", rec_retry_sent));
		return;
	}
	MP_TestOriginalCommand(s);
};

// Observe the restore boundary before legitimate new map touches can rename it.
void() PutClientInServer =
{
	SM_OriginalPutClientInServer();
	if (cvar("p735_expect_cold"))
	{
		cvar_set("p735_expect_cold", "0");
		bprint(2, sprintf("SAVEMARKER COLD COMPLETE restarted=%d failed=%d\n",
			(!rec_retry_sent && !rec_retry_armed) ? 1 : 0, strcmp(self.targetname, "retry-marker") ? 1 : 0));
	}
};
