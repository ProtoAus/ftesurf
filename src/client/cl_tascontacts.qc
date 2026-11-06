// A read-only observation page. Selection/seek reuse the full-line editor.
float tact_tag, tact_ready, tact_next, tact_attempts;
float tact_serial, tact_body, tact_request, tact_base, tact_head, tact_flags;
float tact_offset, tact_total, tact_n;
float tact_start[TAS_CONTACT_ROWS], tact_end[TAS_CONTACT_ROWS], tact_kind[TAS_CONTACT_ROWS];
vector tact_normal[TAS_CONTACT_ROWS];
float tact_distance[TAS_CONTACT_ROWS];
string tact_sha, tact_note;

void() TASContacts_Reset =
{
	tact_tag = tact_tag+1;
	if (tact_tag > 16000000) tact_tag = 1;
	tact_ready = tact_next = tact_attempts = tact_offset = tact_total = tact_n = tact_flags = 0;
	if (tact_sha) strunzone(tact_sha);
	if (tact_note) strunzone(tact_note);
	tact_sha = tact_note = "";
};

float() TASContacts_Current =
{
	return (tact_ready && TASTimeline_Current() && tast_v2 && (tast_flags & 2) && !(tast_flags & 4) &&
		tact_serial == tast_serial && tact_body == tast_bodyhead && tact_request == tast_request &&
		tact_body == getstatf(STAT_FS_TIMERTICKS) && tact_base == tast_base && tact_head == tast_head &&
		!strcmp(tact_sha,tasp_cl_sha));
};

void(float offset) TASContacts_Request =
{
	if (!TASTimeline_Current() || !tast_v2) return;
	// Reopening a retained preview still needs status, not new proposals.
	tact_next = cltime+.6;
	localcmd("p1 cmd tas solvestatus2\n");
	if (!(tast_flags & 2) || (tast_flags & 4)) return;
	if (offset < 0 || offset >= TAS_CONTACT_MAX || offset != floor(offset)) return;
	tact_tag = tact_tag+1;
	if (tact_tag > 16000000) tact_tag = 1;
	tact_ready = FALSE; tact_offset = offset;
	tact_attempts = tact_attempts+1;
	TASProject_IntentRequest();
	localcmd(sprintf("p1 cmd tas contacts page %.0f %.0f %.0f %.0f %.0f\n",
		offset,tact_tag,tast_serial,tast_bodyhead,tast_request));
};

void() TASContacts_Event =
{
	local float tag, serial, body, request, base, head, flags, offset, total, n, take, good;
	local float i, j, c, first, last, kind, previous;
	local float values[10];
	local string sha, note;
	tag = readlong(); serial = readlong(); body = readlong(); request = readlong();
	base = readlong(); head = readlong(); sha = strzone(readstring()); flags = readbyte();
	offset = readshort(); total = readshort(); n = readbyte(); note = strzone(readstring());
	take = (tag == tact_tag && tasu_open && tasu_tab == TAS_TAB_SECTIONS && LT_StatsAreMine() && numclientseats <= 1);
	good = (base >= 0 && body >= base && head >= body && head < 16000000 && flags <= 31 &&
		total >= 0 && total <= TAS_CONTACT_MAX && offset >= 0 && n <= TAS_CONTACT_ROWS &&
		n == min(TAS_CONTACT_ROWS,total-offset) && strlen(note) <= 160);
	if (!total && (offset || n)) good = FALSE;
	if (total && offset >= total) good = FALSE;
	if (total && !(flags & 1)) good = FALSE;
	if ((flags & 1) && !total) good = FALSE;
	if (strlen(sha) != 64)
		if (strlen(sha) || (flags & 1)) good = FALSE;
	for (i = 0; i < min(64,strlen(sha)); i = i+1)
	{
		c = str2chr(sha,i);
		if (!((c >= 48 && c <= 57) || (c >= 97 && c <= 102))) good = FALSE;
	}
	previous = -1;
	for (i = 0; i < n; i = i+1)
	{
		first = readlong(); last = readlong(); kind = readbyte();
		for (j = 0; j < 10; j = j+1)
		{
			values[j] = readfloat();
			if (values[j] != values[j] || fabs(values[j]) > 10000000) good = FALSE;
		}
		if (first < base || last <= first || last > head || kind > 3) good = FALSE;
		if (i && first != previous) good = FALSE;
		if (!i && !offset && first != base) good = FALSE;
		if (i == n-1 && offset+n == total && last != head) good = FALSE;
		if (kind == 1)
		{
			// Native uses |nz| >= .1 and a configurable inclusive ceiling.
			// The ceiling is not on this wire; kind1 is the native classification.
			if (fabs(values[2]) < .1) good = FALSE;
			if (fabs(values[0]*values[0]+values[1]*values[1]+values[2]*values[2]-1) > .002) good = FALSE;
			for (j = 0; j < 3; j = j+1)
				if (values[4+j] > values[7+j]) good = FALSE;
		}
		previous = last;
		if (take && i < TAS_CONTACT_ROWS)
		{
			tact_start[i] = first; tact_end[i] = last; tact_kind[i] = kind;
			tact_normal[i] = [values[0],values[1],values[2]]; tact_distance[i] = values[3];
		}
	}
	// Server-side reads may reject/recover a source without changing body keys.
	// Consume the WHOLE packet before handling this reserved empty-page signal.
	if (!tag)
	{
		if (good && !serial && !body && !request && !base && !head && !flags &&
			!offset && !total && !n && !strlen(sha) && !strlen(note)) TASContacts_Reset();
		strunzone(sha); strunzone(note); return;
	}
	if (!take || !good)
	{
		if (take) tact_ready = FALSE;
		strunzone(sha); strunzone(note); return;
	}
	if (tact_sha) strunzone(tact_sha);
	if (tact_note) strunzone(tact_note);
	tact_sha = sha; tact_note = note;
	tact_serial = serial; tact_body = body; tact_request = request;
	tact_base = base; tact_head = head; tact_flags = flags;
	tact_offset = offset; tact_total = total; tact_n = n; tact_ready = TRUE;
	if (!(flags & 16)) tact_attempts = 0;
	print(sprintf("tas observations: page %.0f rows %.0f total %.0f base %.0f head %.0f current %g\n",
		tact_offset,tact_n,tact_total,tact_base,tact_head,TASContacts_Current()));
};

void() TASContacts_Pump =
{
	if (!TASTimeline_Current()) return;
	if ((!TASContacts_Current() || (tact_flags & 16)) && cltime >= tact_next && tact_attempts < 4)
		TASContacts_Request(tact_offset);
};

void(float row, float action) TASContacts_Action =
{
	if (!TASContacts_Current() || !(tact_flags & 1) || row < 0 || row >= tact_n || row != floor(row)) return;
	if (action == 0)
	{
		tast_from = tact_start[row]+1; tast_to = tact_end[row]; tast_pick = tast_from;
		TASUI_SelectTab(TAS_TAB_TIMELINE); TASTimeline_Request(tast_from);
	}
	else TASTimeline_Action("seek2",action == 2 ? tact_end[row] : tact_start[row]);
};

void() TASContacts_Status =
{
	local float i;
	print(sprintf("tas observations view: current %g flags %.0f page %.0f rows %.0f total %.0f body %.0f head %.0f\n",
		TASContacts_Current(),tact_flags,tact_offset,tact_n,tact_total,tact_body,tact_head));
	for (i = 0; i < tact_n; i = i+1)
		print(sprintf("tas observation %.0f: body %.0f..%.0f kind %.0f\n",tact_offset+i+1,tact_start[i],tact_end[i],tact_kind[i]));
};

#include "cl_tassolve.qc"

void(vector at, float width, float tsz, float hint, float row) TASContacts_Draw =
{
	local float i;
	local vector chip, normal;
	local string label;
	chip = [(width-12)/3,row,0];
	if (Profile_Chip("tact_refresh",at,chip,"Refresh",tsz,FALSE)) { TASContacts_Reset(); TASTimeline_Request(0); }
	if (TASContacts_Current())
	{
		if (tact_offset > 0)
			if (Profile_Chip("tact_previous",at+[(width+6)/3,0,0],chip,"Previous",tsz,FALSE)) TASContacts_Request(max(0,tact_offset-TAS_CONTACT_ROWS));
		if (tact_offset+tact_n < tact_total)
			if (Profile_Chip("tact_next",at+[(width+6)*2/3,0,0],chip,"Next",tsz,FALSE)) TASContacts_Request(tact_offset+TAS_CONTACT_ROWS);
	}
	at_y = at_y+row+hint;
	at_y = at_y+TASSolve_Draw(at,width,hint,row);
	if (tast_v2 && (tast_flags & 4))
	{
		sui_text(at,[hint,hint],"Keep/Discard the candidate before showing current proposals.",SUI_THEME_MUTED,1,0);
		at_y = at_y+hint*2;
		sui_text(at,[hint,hint],"Cached original observations are not replaced by a preview.",SUI_THEME_DIM,1,0);
		return;
	}
	if (!TASContacts_Current())
	{
		label = tact_attempts >= 2 ? "No current contact-page reply. Refresh; older servers may offer manual sections only." : "Pause a supported captured local line; requesting its actual observations.";
		sui_text(at,[hint,hint],label,SUI_THEME_MUTED,1,0); return;
	}
	sui_text(at,[hint,hint],tact_note,SUI_THEME_DIM,1,0); at_y = at_y+hint*2;
	if (!(tact_flags & 1))
	{
		if (tact_flags & 2)
		{
			if (Profile_Chip("tact_replay",at,[width,row,0],"Replay unchanged to retained head",tsz,FALSE))
			{
				TASTimeline_Action("seek2",tact_head); TASContacts_Reset();
			}
			at_y = at_y+row+hint;
			sui_text(at,[hint,hint],"Replay moves the body to the head; Play cancels. The original line is retained.",SUI_THEME_MUTED,1,0);
		}
		return;
	}
	sui_text(at,[hint,hint],sprintf("Observed %.0f..%.0f of %.0f | body %.0f; full source to %.0f",
		tact_offset+1,tact_offset+tact_n,tact_total,tact_body,tact_head),SUI_THEME_TEXT,1,0);
	at_y = at_y+hint*2;
	sui_text(at,[hint,hint],"Solve: choose earlier input ticks in Inputs, then a later target face below (maximum1024 edited ticks).",SUI_THEME_MUTED,1,0);
	at_y = at_y+hint*1.8;
	for (i = 0; i < tact_n; i = i+1)
	{
		label = tact_kind[i] == 1 ? "World ramp face" : (tact_kind[i] == 0 ? "Transit: no ramp observed" : (tact_kind[i] == 2 ? "Non-world: unsupported" : "Gap/unsupported"));
		sui_text(at,[hint,hint],sprintf("%.0f: %.0f -> %.0f | %s%s",tact_offset+i+1,tact_start[i],tact_end[i],label,
			(tact_kind[i] == 1 && tact_end[i] == tact_head) ? " (continues at head)" : ""),SUI_THEME_TEXT,1,0);
		at_y = at_y+hint*1.8;
		if (tact_kind[i] == 1)
		{
			normal = tact_normal[i];
			sui_text(at,[hint,hint],sprintf("Native normal %.3f %.3f %.3f | plane %.2f",normal_x,normal_y,normal_z,tact_distance[i]),SUI_THEME_DIM,1,0);
			at_y = at_y+hint*1.8;
		}
		if (Profile_Chip(sprintf("tact_select%g",i),at,chip,"Inputs",hint,FALSE)) TASContacts_Action(i,0);
		if (Profile_Chip(sprintf("tact_start%g",i),at+[(width+6)/3,0,0],chip,"Go to start",hint,FALSE)) TASContacts_Action(i,1);
		if (Profile_Chip(sprintf("tact_end%g",i),at+[(width+6)*2/3,0,0],chip,"Go to end",hint,FALSE)) TASContacts_Action(i,2);
		at_y = at_y+row+hint;
		if (tact_kind[i] == 1)
		{
			if (Profile_Chip(sprintf("tact_solve%g",i),at,[width,row,0],"Solve selected earlier inputs to this face",hint,FALSE)) TASSolve_Start(i);
			at_y = at_y+row+hint;
		}
	}
	sui_text(at,[hint,hint],"Observations are read-only proposals. Use Manual markers for your own boundaries/names.",SUI_THEME_MUTED,1,0);
};
