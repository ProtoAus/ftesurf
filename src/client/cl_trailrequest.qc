/* Serialize native saves and following state changes across a round trip.
   Capture viewer pictures at request time. Separate terminal save stats also
   survive a raw load replacing the ordinary latest-event stat. */
#define TR_REQUESTS 8
string tr_req_cmd[TR_REQUESTS];
float tr_req_raw[TR_REQUESTS], tr_req_tick[TR_REQUESTS], tr_req_end[TR_REQUESTS];
float tr_req_save[TR_REQUESTS];
float tr_req_head, tr_req_n, tr_req_at, tr_req_dispatch;
float() Rewind_Waiting;
void() Trail_RequestSend;

void() Trail_RequestReset =
{
	local float i;
	for (i = 0; i < TR_REQUESTS; i = i + 1)
	{
		if (tr_req_raw[i] >= 1)
			buf_del(tr_req_raw[i]);
		if (tr_req_cmd[i] != "")
			strunzone(tr_req_cmd[i]);
		tr_req_raw[i] = 0;
		tr_req_cmd[i] = "";
	}
	tr_req_head = tr_req_n = tr_req_wait = tr_req_dispatch = 0;
};

float() Trail_RequestBusy = { return tr_req_wait || tr_req_n; };
float() Trail_RequestDispatching = { return tr_req_dispatch; };

float(string c) Trail_Request =
{
	local float i, raw, tick, endt, ack, go, saving, curt;
	if (tr_req_dispatch)
		return FALSE;
	saving = !strcmp(c, "sl_save");
	if (!saving)
	{
		if (!Trail_RequestBusy() || substring(c, 0, 3) != "sl_")
			return FALSE;
		// A release is never delayed; a queued hold is checked again at send.
		if (!strcmp(c, "sl_holdoff") || strstrofs(c, "sl_list", 0) == 0)
			return FALSE;
	}
	if (tr_req_n >= TR_REQUESTS)
	{
		print("^3save: pending save queue is full\n");
		return TRUE;
	}
	i = (tr_req_head + tr_req_n) % TR_REQUESTS;
	tr_req_save[i] = saving;
	// A go in flight is observed before saving the held body, not re-scrubbed.
	if (saving && !Rewind_Waiting())
	{
		raw = tr_rep_raw; tick = tr_rep_tick; endt = tr_rep_end;
		ack = tr_rep_ack; go = tr_rep_go;
		tr_rep_raw = 0;
		c = SaveLoc_SaveCommand();
		if (!strcmp(c, "sl_save") && tr_on && tr_nsamp > 0)
		{
			curt = tr_cur_t;
			tr_cur_t = tr_lastt;
			Trail_RewindPrefix();
			tr_cur_t = curt;
		}
		tr_req_raw[i] = tr_rep_raw;
		tr_req_tick[i] = tr_rep_tick;
		tr_req_end[i] = tr_rep_end;
		tr_rep_raw = raw; tr_rep_tick = tick; tr_rep_end = endt;
		tr_rep_ack = ack; tr_rep_go = go;
	}
	tr_req_cmd[i] = strzone(c);
	tr_req_n = tr_req_n + 1;
	// Preserve 1 then 2 ordering even within one command-buffer pass.
	if (!tr_req_wait && tr_req_n == 1 && !Rewind_Waiting())
		Trail_RequestSend();
	return TRUE;
};

void() Trail_RequestSend =
{
	local float i, saving, skip;
	local string c;
	i = tr_req_head;
	c = tr_req_cmd[i];
	saving = tr_req_save[i];
	skip = (!strcmp(c, "sl_hold") && !rec_sl_holding);
	tr_rep_raw = tr_req_raw[i];
	tr_rep_tick = tr_req_tick[i];
	tr_rep_end = tr_req_end[i];
	tr_req_raw[i] = 0;
	if (!skip)
	{
		tr_req_dispatch = TRUE;
		SaveLoc_Cmd(c);
		tr_req_dispatch = FALSE;
		if (!strcmp(c, "sl_hold"))
		{
			rec_sl_holdack = rec_sl_sent;
			rec_sl_holdackat = 0;
		}
	}
	strunzone(c);
	tr_req_cmd[i] = "";
	tr_req_head = (i + 1) % TR_REQUESTS;
	tr_req_n = tr_req_n - 1;
	if (saving)
	{
		tr_req_wait = tr_saveack;
		tr_req_at = cltime;
	}
};

// Before the latest-event load can clear/rebase the current visual history.
void() Trail_SaveAnswerFrame =
{
	local float op;
	if (!LT_StatsAreMine() || !tr_req_wait)
		return;
	if (getstatf(STAT_FS_SLSAVEACK) != tr_req_wait)
		return;
	op = getstatf(STAT_FS_SLSAVEOP);
	if (FS_SlopOp(op) == SLOP_SAVED)
		Trail_Save(FS_SlopId(op), getstatf(STAT_FS_SLSAVETICK));
	else
		Trail_ReplayClear();
};

void() Trail_RequestFrame =
{
	if (!LT_StatsAreMine())
	{
		Trail_RequestReset();
		return;
	}
	if (tr_req_wait)
	{
		if (getstatf(STAT_FS_SLSAVEACK) != tr_req_wait)
		{
			if (cltime - tr_req_at > 5)
			{
				print("^3save: pending save lost its acknowledgement\n");
				Trail_RequestReset();
				Trail_ReplayClear();
			}
			return;
		}
		tr_req_wait = 0;
		Trail_ReplayClear();
	}
	if (!Rewind_Waiting())
	while (tr_req_n && !tr_req_wait)
		Trail_RequestSend();           // load + hold stay in one command-buffer pass
};
