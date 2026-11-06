// Own revision-bound observations, through the existing editor body binding.
void(entity e, float argc) SV_TASContactsPage =
{
	local float offset, tag, serial, body, request, s, bound, flags, total, n, i, j, b;
	local float *rows;
	local string note, sha;
	if (argc != 8) goto bad;
	if (!FS_TASNumber(argv(3))) goto bad;
	offset = fs_tas_number;
	if (!FS_TASNumber(argv(4))) goto bad;
	tag = fs_tas_number;
	if (!FS_TASNumber(argv(5))) goto bad;
	serial = fs_tas_number;
	if (!FS_TASNumber(argv(6))) goto bad;
	body = fs_tas_number;
	if (!FS_TASNumber(argv(7))) goto bad;
	request = fs_tas_number;
	if (offset < 0 || offset >= TAS_CONTACT_MAX || offset != floor(offset) ||
		tag < 1 || tag > 16000000 || tag != floor(tag) || serial != floor(serial) ||
		body != floor(body) || request != floor(request)) goto bad;
	// Everything above is copied: Rows/Flush may tokenize.
	if (!SV_TASPLocalOnly(e)) return;
	if (!SV_TASEditorBound(e,serial,body,request)) return;
	if (!SV_TASEditorRows(e)) return;
	s = SV_TASPSlot(e);
	if (!s || e.tasp_legal) return;
	bound = SV_TASContactSpansBind(e);
	flags = total = 0;
	sha = tasp_revsha[s];
	if (e.run_tas_contactinfo_x == 1) flags = flags | 2;
	if (e.tasc_spanfailed) flags = flags | 8;
	note = "No whole-source observations. Replay unchanged to the retained head, then Refresh.";
	if (!(flags & 2)) note = "Native contact metadata unavailable; no ramp proposals inferred.";
	else if (flags & 8) note = "Observation capacity/allocation reached; original inputs retained, no complete cache claimed.";
	if (bound)
	{
		flags = flags | 1;
		if (e.tasc_boundgaps) flags = flags | 4;
		total = e.tasc_boundrows; sha = tasc_sha[s];
		note = "Observed world ramp faces; no-ramp transit is not a guessed airborne state.";
		if (flags & 4) note = "Contains explicit gaps/unsupported contacts; do not infer a ramp or free flight there.";
	}
	if (total < 0 || total > TAS_CONTACT_MAX || total != floor(total)) return;
	offset = min(offset,max(0,total-1));
	n = min(TAS_CONTACT_ROWS,total-offset);
	WriteByte(MSG_MULTICAST,SVC_CGAMEPACKET); WriteByte(MSG_MULTICAST,TAS_EV_CONTACTS);
	WriteLong(MSG_MULTICAST,tag); WriteLong(MSG_MULTICAST,serial);
	WriteLong(MSG_MULTICAST,body); WriteLong(MSG_MULTICAST,request);
	WriteLong(MSG_MULTICAST,e.tasp_base); WriteLong(MSG_MULTICAST,e.tasp_base+e.tasp_n);
	WriteString(MSG_MULTICAST,sha); WriteByte(MSG_MULTICAST,flags);
	WriteShort(MSG_MULTICAST,offset); WriteShort(MSG_MULTICAST,total); WriteByte(MSG_MULTICAST,n);
	WriteString(MSG_MULTICAST,note);
	rows = tasc_bound[s];
	for (i = 0; i < n; i = i+1)
	{
		b = (offset+i)*TASC_SPAN_STRIDE;
		WriteLong(MSG_MULTICAST,rows[b]); WriteLong(MSG_MULTICAST,rows[b+1]);
		WriteByte(MSG_MULTICAST,rows[b+2]);
		for (j = 3; j < 13; j = j+1) WriteFloat(MSG_MULTICAST,rows[b+j]);
	}
	msg_entity = e; multicast(e.origin,MULTICAST_ONE_R);
	return;
:bad
	sprint(e,PRINT_HIGH,"tas contacts: invalid bound observation-page request\n");
};
