// Progress is display-only. Every solve/cancel command is bound again by SSQC.
float tsol_cl_serial, tsol_cl_request, tsol_cl_state, tsol_cl_candidate;
float tsol_cl_feasible, tsol_cl_best, tsol_cl_speed, tsol_cl_work;
string tsol_cl_sha, tsol_cl_note;

void() TASSolve_Reset =
{
	if (tsol_cl_sha) strunzone(tsol_cl_sha);
	if (tsol_cl_note) strunzone(tsol_cl_note);
	tsol_cl_sha = tsol_cl_note = ""; tsol_cl_state = tsol_cl_request = 0;
};

void() TASSolve_Event =
{
	local string sha, note;
	local float serial, request, state, candidate, feasible, best, speed, work, good, i, c;
	// Consume the whole fixed packet even on a stale/malformed/other-seat reply.
	sha = strzone(readstring()); serial = readlong(); request = readlong();
	state = readbyte(); candidate = readbyte(); feasible = readbyte(); best = readbyte();
	speed = readfloat(); work = readlong(); note = strzone(readstring());
	good = (state <= 3 && candidate <= TAS_SOLVE_CANDIDATES && feasible <= TAS_SOLVE_CANDIDATES &&
		best <= TAS_SOLVE_CANDIDATES && speed == speed && speed >= 0 && speed <= 10000000 &&
		work >= 0 && work <= 16000000 && strlen(note) <= 160);
	if (state && (strlen(sha) != 64 || serial < 1 || request < 1 || request > 16000000)) good = FALSE;
	if (state && serial == tsol_cl_serial && request < tsol_cl_request) good = FALSE;
	for (i = 0; i < min(64,strlen(sha)); i = i+1)
	{
		c = str2chr(sha,i);
		if (!((c >= 48 && c <= 57) || (c >= 97 && c <= 102))) good = FALSE;
	}
	if (!good || !LT_StatsAreMine() || numclientseats > 1)
	{
		strunzone(sha); strunzone(note); return;
	}
	TASSolve_Reset();
	tsol_cl_sha = sha; tsol_cl_note = note; tsol_cl_serial = serial; tsol_cl_request = request;
	tsol_cl_state = state; tsol_cl_candidate = candidate; tsol_cl_feasible = feasible;
	tsol_cl_best = best; tsol_cl_speed = speed; tsol_cl_work = work;
	print(sprintf("tas solver view: state%.0f candidate%.0f feasible%.0f best%.0f work%.0f %s\n",
		state,candidate,feasible,best,work,note));
};

void(float row) TASSolve_Start =
{
	if (!TASContacts_Current() || !(tact_flags & 1) || row < 0 || row >= tact_n || row != floor(row)) return;
	if (tact_kind[row] != 1 || tast_from < tact_base+1 || tast_to < tast_from ||
		tast_to-tast_from+1 > TAS_SOLVE_ROWS || tast_to > tact_start[row])
	{
		print("tas solve: select 1..1024 actual input ticks BEFORE the target face in Inputs, then choose that later face.\n"); return;
	}
	localcmd(sprintf("p1 cmd tas solve2 %.0f %.0f %.0f %s %.0f %.0f %.0f\n",
		tast_from,tast_to,tact_offset+row+1,tact_sha,tast_serial,tast_bodyhead,tast_request));
};

float(vector at, float width, float hint, float row) TASSolve_Draw =
{
	local float height;
	if (!tsol_cl_state || strcmp(tsol_cl_sha,tasp_cl_sha)) return 0;
	if (tsol_cl_serial != tast_serial) return 0;
	height = hint*3.6+row+hint;
	sui_text(at,[hint,hint],sprintf("Best FOUND search: tested %.0f/%.0f | feasible %.0f | native work %.0f",
		min(tsol_cl_candidate,TAS_SOLVE_CANDIDATES),TAS_SOLVE_CANDIDATES,tsol_cl_feasible,tsol_cl_work),SUI_THEME_TEXT,1,0);
	at_y = at_y+hint*1.8;
	sui_text(at,[hint,hint],tsol_cl_note,SUI_THEME_MUTED,1,0); at_y = at_y+hint*1.8;
	if (tsol_cl_state == 1)
	{
		if (Profile_Chip("tsol_cancel",at,[width,row,0],"Cancel search (retain original)",hint,FALSE))
			localcmd(sprintf("p1 cmd tas solvecancel2 %.0f %.0f %s\n",tsol_cl_serial,tsol_cl_request,tsol_cl_sha));
	}
	else if (Profile_Chip("tsol_preview",at,[width,row,0],"Open input preview / original recovery",hint,FALSE))
	{
		TASUI_SelectTab(TAS_TAB_TIMELINE); TASTimeline_Request(0);
	}
	return height;
};
