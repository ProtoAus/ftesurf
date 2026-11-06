// Manual checkpoint intervals only. Names/poses never authorize movement.
// wanted -1 counts; otherwise z is the end marker's named ordinal + 1, or 0.
vector(float *cp, float ncp, float base, float head, float wanted) SV_TASSectionWalk =
{
	local float i, b, tick, previous, section, named;
	if (ncp < 0 || ncp > TASP_CPMAX || ncp != floor(ncp) || head <= base)
		return wanted < 0 ? '0 0 0' : '-1 -1 -1';
	if (ncp && !cp) return wanted < 0 ? '0 0 0' : '-1 -1 -1';
	previous = base; section = named = 0;
	for (i = 0; i < ncp; i = i + 1)
	{
		b = i*TASP_CPSTRIDE;
		if (!cp[b+1]) continue;
		tick = cp[b];
		if (tick > previous && tick <= head)
		{
			if (section == wanted) return [previous,tick,named+1];
			previous = tick; section = section+1;
		}
		named = named+1;
	}
	if (previous < head)
	{
		if (section == wanted) return [previous,head,0];
		section = section+1;
	}
	return wanted < 0 ? [section,0,0] : '-1 -1 -1';
};

void(entity e, float argc) SV_TASSectionsCommand =
{
	local float offset, tag, serial, head, request, s, total, n, i;
	local vector span;
	local string name;
	// Bound/Rows flush settled inputs and may tokenize. Consume argv first.
	if (argc != 7) goto bad;
	if (!FS_TASNumber(argv(2))) goto bad;
	offset = fs_tas_number;
	if (!FS_TASNumber(argv(3))) goto bad;
	tag = fs_tas_number;
	if (!FS_TASNumber(argv(4))) goto bad;
	serial = fs_tas_number;
	if (!FS_TASNumber(argv(5))) goto bad;
	head = fs_tas_number;
	if (!FS_TASNumber(argv(6))) goto bad;
	request = fs_tas_number;
	if (offset < 0 || offset > TASP_CPMAX || offset != floor(offset) ||
		tag < 1 || tag > 16000000 || tag != floor(tag)) goto bad;
	if (serial != floor(serial) || head != floor(head) || request != floor(request)) goto bad;
	if (!SV_TASEditorBound(e,serial,head,request)) return;
	if (!SV_TASEditorRows(e)) return;
	s = SV_TASPSlot(e);
	if (!s || e.tasp_legal) return;
	span = SV_TASSectionWalk(tasp_cp[s],e.tasp_ncp,e.tasp_base,e.tasp_base+e.tasp_n,-1);
	total = span_x;
	offset = min(offset,max(0,total-1));
	n = min(TAS_SECTION_ROWS,total-offset);
	WriteByte(MSG_MULTICAST,SVC_CGAMEPACKET); WriteByte(MSG_MULTICAST,TAS_EV_SECTIONS);
	WriteLong(MSG_MULTICAST,tag); WriteLong(MSG_MULTICAST,serial);
	WriteLong(MSG_MULTICAST,head); WriteLong(MSG_MULTICAST,request);
	WriteLong(MSG_MULTICAST,e.tasp_base); WriteLong(MSG_MULTICAST,e.tasp_base+e.tasp_n);
	WriteString(MSG_MULTICAST,tasp_revsha[s]); WriteByte(MSG_MULTICAST,e.tasp_ncp);
	WriteByte(MSG_MULTICAST,offset); WriteByte(MSG_MULTICAST,total); WriteByte(MSG_MULTICAST,n);
	for (i = 0; i < n; i = i+1)
	{
		span = SV_TASSectionWalk(tasp_cp[s],e.tasp_ncp,e.tasp_base,e.tasp_base+e.tasp_n,offset+i);
		name = span_z ? SV_TASPNameAt(tasp_cpnames[s],span_z-1) : "";
		WriteLong(MSG_MULTICAST,span_x); WriteLong(MSG_MULTICAST,span_y);
		WriteString(MSG_MULTICAST,name);
	}
	msg_entity = e; multicast(e.origin,MULTICAST_ONE_R);
	return;
:bad
	sprint(e,PRINT_HIGH,"tas sections: invalid bound page request\n");
};
