/*
===========================================================================
  sv_savesync.qc -- Patch 811: a player's lobby saves and the saves in their own
  install are one list.

  The client (cl_savesync.qc) mirrors this player's lobby block into the install's
  offline list, data/saves/<map>/saveNNN, which a local game reads, and sends up
  the rows of that list this block does not have.  `cmd savesync`:

      list <from> <req>                 SS_PAGE rows from row <from>, then SS_EV_END
      add <tag> x y z vx vy vz p y d    a row from the install; answered SS_EV_ROW
      del <tag> <id> x y z p y          that row, if it is still at that place and view

  An added row is the replay-point shape SV_SaveWriteAt writes with no ring sample
  (idle timer, no run, velocity under `rwvel`): what `sl_saveview` already takes
  from any client, so this adds no state a client could not place before.  An add
  or a delete pays SV_SaveLocRate's charge as an sl_ command does, and this file's
  own rate besides.

  Pushed unasked: every new row of the block (SV_SaveLocEvent), every row a
  delete takes (SV_SaveLocDeleteRow), one SS_EV_DELALL when a delete-all finishes.
  The rewind's current resume row is neither listed nor pushed.  Lobby blocks only:
  off-lobby the list is the shared one, and the install's.
===========================================================================
*/
#define SS_RATE  10             // savesync commands a second, burst and sustained

.float ss_tok, ss_tokt;

float ss_new;                   // the row SV_SaveSyncRow sends was just made by an add

void(entity e, float r, float tag) SV_SaveSyncRow =
{
	local vector o, v;
	local float fl;

	// P1052: the old mirror format is position-only. Omit assisted/unknown
	// rows; the existing incomplete-list guard then forbids deletion, too.
	if (SV_SaveTransferFlags(e, r) != 0)
		return;
	o = rec_sl_org[r];
	v = rec_sl_vel[r];
	fl = rec_sl_duck[r] ? SSF_DUCK : 0;
	if (ss_new)
		fl = fl | SSF_NEW;
	if (rec_sl_tick[r] > 0)
		fl = fl | SSF_TIMED;
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, SS_EV_ROW);
	WriteLong(MSG_MULTICAST, tag);
	WriteShort(MSG_MULTICAST, rec_sl_id[r]);
	WriteLong(MSG_MULTICAST, rec_sl_seq[r]);
	WriteFloat(MSG_MULTICAST, o_x);
	WriteFloat(MSG_MULTICAST, o_y);
	WriteFloat(MSG_MULTICAST, o_z);
	WriteFloat(MSG_MULTICAST, v_x);
	WriteFloat(MSG_MULTICAST, v_y);
	WriteFloat(MSG_MULTICAST, v_z);
	WriteFloat(MSG_MULTICAST, rec_sl_pit[r]);
	WriteFloat(MSG_MULTICAST, rec_sl_yaw[r]);
	WriteByte(MSG_MULTICAST, fl);
	msg_entity = e;
	multicast('0 0 0', SH_MC_ONE);
};

// A refused add: id 0, so the client stops waiting for that tag.
void(entity e, float tag) SV_SaveSyncNak =
{
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, SS_EV_ROW);
	WriteLong(MSG_MULTICAST, tag);
	WriteShort(MSG_MULTICAST, 0);
	WriteLong(MSG_MULTICAST, 0);
	WriteFloat(MSG_MULTICAST, 0); WriteFloat(MSG_MULTICAST, 0); WriteFloat(MSG_MULTICAST, 0);
	WriteFloat(MSG_MULTICAST, 0); WriteFloat(MSG_MULTICAST, 0); WriteFloat(MSG_MULTICAST, 0);
	WriteFloat(MSG_MULTICAST, 0); WriteFloat(MSG_MULTICAST, 0);
	WriteByte(MSG_MULTICAST, 0);
	msg_entity = e;
	multicast('0 0 0', SH_MC_ONE);
};

// status: 0 a page, 1 nothing to mirror here (off-lobby, saves off, mid-sweep), 2 busy
// (the save rate: ask again).  kind 0 answers a listing (`req` its number), 1 an
// add or del (`req` its tag): the two numbers are the client's two counters.
void(entity e, float next, float cnt, float status, float req, float kind) SV_SaveSyncEnd =
{
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, SS_EV_END);
	WriteShort(MSG_MULTICAST, next);
	WriteShort(MSG_MULTICAST, cnt);
	WriteByte(MSG_MULTICAST, status);
	WriteLong(MSG_MULTICAST, req);
	WriteByte(MSG_MULTICAST, kind);
	msg_entity = e;
	multicast('0 0 0', SH_MC_ONE);
};

void(entity e, float tag, float id, vector o, float pit, float yaw) SV_SaveSyncDelEv =
{
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, SS_EV_DEL);
	WriteLong(MSG_MULTICAST, tag);
	WriteShort(MSG_MULTICAST, id);
	WriteFloat(MSG_MULTICAST, o_x);
	WriteFloat(MSG_MULTICAST, o_y);
	WriteFloat(MSG_MULTICAST, o_z);
	WriteFloat(MSG_MULTICAST, pit);
	WriteFloat(MSG_MULTICAST, yaw);
	msg_entity = e;
	multicast('0 0 0', SH_MC_ONE);
};

// The rewind's resume row (SV_RewindDropGo replaces it at the next resume).
float(entity e, float r) SV_SaveSyncIsGo =
{
	return (e.rw_goid && rec_sl_id[r] == e.rw_goid && rec_sl_seq[r] == e.rw_goseq);
};

// SV_SaveLocEvent's SLOP_SAVED: the row just made is the cursor's.
void(entity e) SV_SaveSyncPush =
{
	local float blk;

	blk = SL_Blk(e);
	if (blk <= 0 || ss_nopush || clienttype(e) != CLIENTTYPE_REAL)
		return;
	if (e.rec_sl_index < 1 || e.rec_sl_index > rec_sl_nb[blk])
		return;
	SV_SaveSyncRow(e, SL_Base(blk) + e.rec_sl_index - 1, 0);
};

// SV_SaveLocDeleteRow, before the row goes.  A delete-all sends one SS_EV_DELALL.
void(entity e, float r) SV_SaveSyncGone =
{
	if (SL_Blk(e) <= 0 || e.rec_sl_delall || ss_quiet || clienttype(e) != CLIENTTYPE_REAL)
		return;
	SV_SaveSyncDelEv(e, 0, rec_sl_id[r], rec_sl_org[r], rec_sl_pit[r], rec_sl_yaw[r]);
};

void(entity e) SV_SaveSyncDelAll =
{
	if (SL_Blk(e) <= 0 || clienttype(e) != CLIENTTYPE_REAL)
		return;
	WriteByte(MSG_MULTICAST, SVC_CGAMEPACKET);
	WriteByte(MSG_MULTICAST, SS_EV_DELALL);
	msg_entity = e;
	multicast('0 0 0', SH_MC_ONE);
};

// Never the resume row, which the listing and the pushes leave out.
float(entity e, float blk, vector o, float pit, float yaw) SV_SaveSyncFind =
{
	local float base, i;
	local vector ro;

	base = SL_Base(blk);
	for (i = 0; i < rec_sl_nb[blk]; i = i + 1)
	{
		ro = rec_sl_org[base + i];
		if (SS_Same(ro, rec_sl_pit[base + i], rec_sl_yaw[base + i], o, pit, yaw))
		if (!SV_SaveSyncIsGo(e, base + i))
			return base + i;
	}
	return -1;
};

// The new row, appended without moving the cursor or firing a save event: the
// player did not make it here, and their next 2 must still load what it did.
float(entity e, float blk, float dk) SV_SaveSyncAdd =
{
	local float base, cnt, id, seq, row;

	base = SL_Base(blk);
	cnt  = rec_sl_nb[blk];
	if (cnt >= SL_Cap(blk))
		return -1;
	id = SV_SaveFreeID(base, cnt);
	if (id < 1)
		return -1;
	seq = rec_sl_ns[blk];
	rec_sl_ns[blk] = seq + 1;
	rw_dk = dk;
	rw_t = 0;
	rw_statebase = -1;              // no ring sample: the placement shape
	if (!SV_SaveWriteAt(e, id, seq, FALSE))
		return -1;
	row = base + cnt;
	if (SV_SaveReadLight(id, row) < 0)
		return -1;
	rec_sl_seq[row] = seq;
	rec_sl_nb[blk] = cnt + 1;
	SV_SaveGenBump(blk);            // Patch 751: the other lobbies rescan
	return row;
};

void(entity e, float argc) SaveSync_Command =
{
	local float blk, base, r, last, tag, dk, req, id, n, sent;
	local string op;
	local vector o, v;
	local float pit, yaw;

	if (e.classname != "player" || !e.run_inserver)
		return;
	e.ss_tok  = min(SS_RATE, e.ss_tok + (time - e.ss_tokt) * SS_RATE);
	e.ss_tokt = time;
	if (e.ss_tok < 1)
		return;                     // the client's timeout asks again
	e.ss_tok = e.ss_tok - 1;
	// Every argument first: SV_SaveLocBegin's scan tokenizes.
	op = argv(1);
	tag = floor(stof(argv(2)));
	v = '0 0 0';
	dk = req = id = 0;
	pit = yaw = 0;
	o = '0 0 0';
	if (op == "list")
		req = floor(stof(argv(3)));
	else if (op == "add")
	{
		o = [stof(argv(3)), stof(argv(4)), stof(argv(5))];
		v = [stof(argv(6)), stof(argv(7)), stof(argv(8))];
		pit = stof(argv(9));
		yaw = stof(argv(10));
		dk = (stof(argv(11)) != 0);
	}
	else if (op == "del")
	{
		id = floor(stof(argv(3)));
		o = [stof(argv(4)), stof(argv(5)), stof(argv(6))];
		pit = stof(argv(7));
		yaw = stof(argv(8));
	}
	if (!(tag >= 0 && tag <= 16000000) || !(req >= 0 && req <= 16000000))
		return;
	blk = SL_Blk(e);
	r = FALSE;
	if (blk > 0)                    // nested: QC's || would run the Begin off-lobby too
		r = SV_SaveLocBegin(e, TRUE);
	if (!r)
	{
		if (op == "list")
			SV_SaveSyncEnd(e, 0, 0, 1, req, 0);
		else
			SV_SaveSyncEnd(e, 0, 0, 1, tag, 1);
		return;
	}
	base = SL_Base(blk);

	if (op == "list")               // the tag is the first row asked for
	{
		tag = max(1, tag);
		last = min(rec_sl_nb[blk], tag + SS_PAGE - 1);
		n = sent = 0;
		for (r = 0; r < rec_sl_nb[blk]; r = r + 1)
			if (!SV_SaveSyncIsGo(e, base + r))
				n = n + 1;
		for (r = tag; r <= last; r = r + 1)
			if (!SV_SaveSyncIsGo(e, base + r - 1))
				SV_SaveSyncRow(e, base + r - 1, 0);
		SV_SaveSyncEnd(e, (last < rec_sl_nb[blk]) ? last + 1 : 0, n, 0, req, 0);
		return;
	}

	if (op != "add" && op != "del")
		return;
	// An sl_ command's charge too, so the save list's disk work per player stays
	// Patch 428's.  Quiet: the player did not type it.
	sl_ratequiet = TRUE;
	r = SV_SaveLocRate(e);
	sl_ratequiet = FALSE;
	if (!r)
	{
		SV_SaveSyncEnd(e, 0, 0, 2, tag, 1);
		return;
	}

	if (op == "add" && argc == 12)
	{
		// sl_saveview's checks: a client's numbers, so every one of them.
		if (!SV_SaveOriginSane(o) || !SV_SaveOriginSane(v) || !(vlen(v) <= 32768) ||
		    !(fabs(pit) <= 360) || !(fabs(yaw) <= 360))
		{
			SV_SaveSyncNak(e, tag);
			return;
		}
		r = SV_SaveSyncFind(e, blk, o, pit, yaw);
		ss_new = (r < 0);
		if (r < 0)
		{
			rw_o = o;
			rw_v = v;
			rw_pit = pit;
			rw_yaw = yaw;
			r = SV_SaveSyncAdd(e, blk, dk);
		}
		if (r < 0)
			SV_SaveSyncNak(e, tag);
		else
			SV_SaveSyncRow(e, r, tag);
		ss_new = FALSE;
		return;
	}

	if (op == "del" && argc == 9)
	{
		// That row only: its folder and its place and view, so a reused folder or a
		// second save at one place is never the one taken.
		r = -1;
		if (SV_SaveOriginSane(o) && fabs(pit) <= 360 && fabs(yaw) <= 360)
		for (n = 0; n < rec_sl_nb[blk]; n = n + 1)
			if (rec_sl_id[base + n] == id)
			{
				v = rec_sl_org[base + n];
				if (SS_Same(v, rec_sl_pit[base + n], rec_sl_yaw[base + n], o, pit, yaw))
				if (!SV_SaveSyncIsGo(e, base + n))
					r = base + n;
				break;
			}
		if (r >= 0)
		{
			ss_quiet = TRUE;
			rec_sl_quiet = TRUE;
			SV_SaveLocDeleteRow(e, r - base + 1);
			rec_sl_quiet = FALSE;
			ss_quiet = FALSE;
			SV_SaveGenBump(blk);
		}
		SV_SaveSyncDelEv(e, tag, (r >= 0) ? id : 0, o, pit, yaw);
		return;
	}
};
