/* P1437: consume one coherent save event, never a sequence with stale payload.
 * Numeric stats and the string can span packets. The existing endpoint string
 * now also carries E seq/packed-op/ticks/tag; publish only when its seq matches.
 * Refresh at callback boundaries, not inside getters (tokenize owns argv).
 */
float sl_event_seq, sl_event_slop, sl_event_ticks, sl_event_tag;
vector sl_event_origin;
float(string text, float cap) Watch_OwnViewNumber;

void() SaveEvent_Init =
{
	sl_event_seq = sl_event_slop = sl_event_ticks = sl_event_tag = 0;
	sl_event_origin = '0 0 0';
};

void() SaveEvent_Frame =
{
	local float n, at, seq, packed, ticks, tag, op, i, rawseq;
	local string packet;
	local vector origin;

	rawseq = getstatf(STAT_FS_SLSEQ);
	if (!rawseq) { SaveEvent_Init(); return; }
	if (rawseq == sl_event_seq) return;
	packet = getstats(STAT_FS_SLLEAD);
	n = tokenize(packet);
	at = 0;
	if (n == 14)
	{
		if (strcmp(argv(0), "L")) return;
		at = 9;
	}
	else if (n != 5 && n != 8)
		return;
	if (strcmp(argv(at), "E")) return;
	for (i = at + 1; i < at + ((n == 8) ? 8 : 5); i += 1)
		if (!Watch_OwnViewNumber(argv(i), 100000000)) return;
	seq = stof(argv(at + 1));
	packed = stof(argv(at + 2));
	ticks = stof(argv(at + 3));
	tag = stof(argv(at + 4));
	if (seq < 1 || seq != floor(seq) || seq != rawseq) return;
	if (packed < 0 || packed != floor(packed)) return;
	if (ticks < -1 || ticks != floor(ticks) || tag < 0 || tag != floor(tag)) return;
	op = FS_SlopOp(packed);
	if (op < SLOP_SAVED || op > SLOP_RESUME || op != floor(op)) return;
	origin = '0 0 0';
	if (n == 14)
	{
		if (op != SLOP_LOADED) return;
		for (i = 1; i < 9; i += 1)
			if (!Watch_OwnViewNumber(argv(i), 100000000)) return;
		if (stof(argv(1)) != seq || stof(argv(2)) != FS_SlopId(packed)) return;
		if (stof(argv(8)) != 0 && stof(argv(8)) != 1) return;
		origin = [stof(argv(3)), stof(argv(4)), stof(argv(5))];
	}
	else if (n == 8)
	{
		if (op != SLOP_SAVED) return;
		origin = [stof(argv(5)), stof(argv(6)), stof(argv(7))];
	}
	else if (op == SLOP_LOADED || op == SLOP_SAVED)
		return;
	sl_event_seq = seq;
	sl_event_slop = packed;
	sl_event_ticks = ticks;
	sl_event_tag = tag;
	sl_event_origin = origin;
};

// Terminal/refusal/destructive decisions need to distinguish an unfinished
// publication from an already consumed event. Payload getters alone cannot.
float() SaveEvent_Pending = { return (getstatf(STAT_FS_SLSEQ) != sl_event_seq); };
float() SaveEvent_Seq = { return sl_event_seq; };
float() SaveEvent_Slop = { return sl_event_slop; };
float() SaveEvent_Ticks = { return sl_event_ticks; };
float() SaveEvent_Tag = { return sl_event_tag; };
vector() SaveEvent_Origin = { return sl_event_origin; };
