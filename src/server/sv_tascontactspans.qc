// Derived sparse spans; no pose import, movement grant, or portable authority.
// A kind0 span means NO OBSERVED RAMP, not a claim that the player was airborne.
#define TASC_SPAN_MAX TAS_CONTACT_MAX
#define TASC_SPAN_STRIDE 20 // start,end,kind,normal xyz,dist,endpoint min/max xyz,samples,first/last post-step velocity xyz
float *tasc_live[FS_MAXPLAYERS+1];
float *tasc_bound[FS_MAXPLAYERS+1];
string tasc_sha[FS_MAXPLAYERS+1];
.float tasc_spanbase, tasc_spanrows, tasc_spanfailed;
.float tasc_boundbase, tasc_boundhead, tasc_boundrows, tasc_boundgaps;

void(entity e) SV_TASContactSpansBegin =
{
	local float s;
	s = SV_TASPSlot(e);
	e.tasc_spanbase = e.tasc_tick;
	e.tasc_spanrows = e.tasc_spanfailed = 0;
	if (!s) { e.tasc_spanfailed = TRUE; return; }
	if (!tasc_live[s]) tasc_live[s] = (float*)memalloc(TASC_SPAN_MAX*TASC_SPAN_STRIDE*4);
	if (!tasc_live[s]) e.tasc_spanfailed = TRUE;
};

void(entity e, float first, float last, float kind, vector normal, float distance, vector point) SV_TASContactSpan =
{
	local float s, b, i, merge;
	local float *rows;
	local vector oldnormal;
	s = SV_TASPSlot(e);
	if (!s || e.tasc_spanfailed || last <= first) return;
	rows = tasc_live[s];
	if (!rows) { e.tasc_spanfailed = TRUE; return; }
	b = 0; merge = FALSE;
	if (e.tasc_spanrows > 0)
	{
		b = (e.tasc_spanrows-1)*TASC_SPAN_STRIDE;
		if (rows[b+1] == first && rows[b+2] == kind)
		{
			merge = TRUE;
			if (kind == 1)
			{
				oldnormal = [rows[b+3],rows[b+4],rows[b+5]];
				merge = (vlen(oldnormal-normal) < .00001 && fabs(rows[b+6]-distance) < .01);
			}
		}
	}
	if (!merge)
	{
		if (e.tasc_spanrows >= TASC_SPAN_MAX) { e.tasc_spanfailed = TRUE; return; }
		b = e.tasc_spanrows*TASC_SPAN_STRIDE;
		for (i = 0; i < TASC_SPAN_STRIDE; i = i+1) rows[b+i] = 0;
		rows[b] = first; rows[b+2] = kind;
		if (kind == 1)
		{
			rows[b+3] = normal_x; rows[b+4] = normal_y; rows[b+5] = normal_z;
			rows[b+6] = distance;
			rows[b+7] = rows[b+10] = point_x;
			rows[b+8] = rows[b+11] = point_y;
			rows[b+9] = rows[b+12] = point_z;
			rows[b+14] = e.velocity_x; rows[b+15] = e.velocity_y; rows[b+16] = e.velocity_z;
		}
		e.tasc_spanrows = e.tasc_spanrows+1;
	}
	rows[b+1] = last; rows[b+13] = rows[b+13]+last-first;
	if (kind != 1) return;
	rows[b+7] = min(rows[b+7],point_x); rows[b+10] = max(rows[b+10],point_x);
	rows[b+8] = min(rows[b+8],point_y); rows[b+11] = max(rows[b+11],point_y);
	rows[b+9] = min(rows[b+9],point_z); rows[b+12] = max(rows[b+12],point_z);
	rows[b+17] = e.velocity_x; rows[b+18] = e.velocity_y; rows[b+19] = e.velocity_z;
};

float(entity e) SV_TASContactSpansBind =
{
	local float s, head;
	s = SV_TASPSlot(e);
	if (!s || !e.tasp_on || e.tasp_legal || e.tasp_load || e.tase_preview || e.tase_operation || e.tasi_dirty) return FALSE;
	if (!SV_TASEditorRows(e)) return FALSE;
	// Recheck AFTER harvesting: legacy literal edits have no intent dirty bit.
	// This gate precedes cached reuse AND fresh-map binding.
	if (e.tasp_rawdirty || e.tasi_dirty || !tasp_pbuf[s]) return FALSE;
	head = e.tasp_base+e.tasp_n;
	if (e.tasp_filehead != head || e.tasp_pn != e.tasp_n || e.tasp_pbase != e.tasp_base) return FALSE;
	if (!SV_TASEditorHashOK(tasp_revsha[s])) return FALSE;
	if (strcmp(tasp_keptsha[s],tasp_revsha[s])) return FALSE;
	if (!SV_TASPFileIs(SV_TASPRevPath(tasp_revsha[s],"tasp"))) return FALSE;
	if (e.tasc_boundrows > 0 && e.tasc_boundbase == e.tasp_base && e.tasc_boundhead == head)
		if (!strcmp(tasc_sha[s],tasp_revsha[s])) return TRUE;
	if (!e.tasc_ready || e.tasc_frozen || e.tasc_spanfailed || e.tasc_spanrows <= 0) return FALSE;
	if (e.tasc_serial != e.rec_rec_serial || e.tasc_gen != e.rec_rec_gen || e.tasc_tick != head || e.tasc_spanbase != e.tasp_base) return FALSE;
	if (!tasc_live[s]) return FALSE;
	if (tasc_live[s][0] != e.tasp_base || tasc_live[s][(e.tasc_spanrows-1)*TASC_SPAN_STRIDE+1] != head) return FALSE;
	// FTE_MEMALLOC already supplies the row buffers. Refuse absent copy support;
	// never replace a bounded native copy with a full-line synchronous VM loop.
	if (!checkbuiltin(memcpy)) return FALSE;
	if (!tasc_bound[s]) tasc_bound[s] = (float*)memalloc(TASC_SPAN_MAX*TASC_SPAN_STRIDE*4);
	if (!tasc_bound[s]) return FALSE;
	memcpy((__variant*)tasc_bound[s],(__variant*)tasc_live[s],(int)(e.tasc_spanrows*TASC_SPAN_STRIDE*4));
	if (tasc_sha[s]) strunzone(tasc_sha[s]);
	tasc_sha[s] = strzone(tasp_revsha[s]);
	e.tasc_boundbase = e.tasp_base; e.tasc_boundhead = head;
	e.tasc_boundrows = e.tasc_spanrows; e.tasc_boundgaps = e.tasc_gaps;
	return TRUE;
};

// ONLY the strict metadata writer calls this, after its unchanged-input checks
// and successful immutable readback. A rename is not a new physical line.
void(entity e, string before, string after) SV_TASContactSpansRetag =
{
	local float s;
	local string kept;
	s = SV_TASPSlot(e);
	if (!s || e.tasc_boundrows <= 0 || !tasc_bound[s]) return;
	if (!SV_TASEditorHashOK(after) || strcmp(tasc_sha[s],before)) return;
	if (e.tasi_dirty || e.tase_preview || e.tasp_filehead != e.tasp_base+e.tasp_n) return;
	if (e.tasc_boundbase != e.tasp_base || e.tasc_boundhead != e.tasp_base+e.tasp_n) return;
	if (strcmp(tasp_revsha[s],after) || strcmp(tasp_keptsha[s],after)) return;
	kept = strzone(after);
	if (tasc_sha[s]) strunzone(tasc_sha[s]);
	tasc_sha[s] = kept;
};

void(entity e) SV_TASContactSpansFree =
{
	local float s;
	s = SV_TASPSlot(e);
	if (!s) return;
	if (tasc_live[s]) memfree(tasc_live[s]);
	if (tasc_bound[s]) memfree(tasc_bound[s]);
	if (tasc_sha[s]) strunzone(tasc_sha[s]);
	tasc_live[s] = tasc_bound[s] = 0; tasc_sha[s] = "";
	e.tasc_ready = e.tasc_spanrows = e.tasc_spanfailed = e.tasc_boundrows = 0;
	e.tasc_spanbase = e.tasc_boundbase = e.tasc_boundhead = e.tasc_boundgaps = 0;
	e.tasc_samples = e.tasc_gaps = e.tasc_ramps = e.tasc_frozen = 0;
};

void(entity e) SV_TASContactSpansStatus =
{
	local float s, bound, i, b;
	local float *rows;
	// Command caller consumed argv. This flush does not grant any native work.
	bound = FALSE;
	if (SV_TASEditorRows(e)) bound = SV_TASContactSpansBind(e);
	s = SV_TASPSlot(e);
	sprint(e,PRINT_HIGH,sprintf("tas contact spans: bound%.0f liveRows%.0f failed%.0f base%.0f head%.0f rows%.0f\n",
		bound,e.tasc_spanrows,e.tasc_spanfailed,e.tasc_boundbase,e.tasc_boundhead,e.tasc_boundrows));
	if (!bound || !s)
	{
		sprint(e,PRINT_HIGH,"tas contact spans: no complete source-bound cache; save the whole settled line or analyze it, never infer missing samples\n");
		return;
	}
	sprint(e,PRINT_HIGH,sprintf("tas contact source: %s gaps%.0f; derived trace endpoints, not surface poses or authority\n",tasc_sha[s],e.tasc_boundgaps));
	rows = tasc_bound[s];
	for (i = 0; i < min(e.tasc_boundrows,8); i = i+1)
	{
		b = i*TASC_SPAN_STRIDE;
		sprint(e,PRINT_HIGH,sprintf("tas contact span %.0f: body%.0f..%.0f kind%.0f samples%.0f%s\n",
			i+1,rows[b],rows[b+1],rows[b+2],rows[b+13],(rows[b+2] == 1 && rows[b+1] == e.tasc_boundhead) ? " continues at retained head" : ""));
		if (rows[b+2] == 1)
		{
			sprint(e,PRINT_HIGH,sprintf("tas contact plane %.0f: dist%.9g normal%.9g,%.9g,%.9g\n",
				i+1,rows[b+6],rows[b+3],rows[b+4],rows[b+5]));
			sprint(e,PRINT_HIGH,sprintf("tas contact region %.0f: %.9g,%.9g,%.9g..%.9g,%.9g,%.9g\n",
				i+1,rows[b+7],rows[b+8],rows[b+9],rows[b+10],rows[b+11],rows[b+12]));
		}
	}
};
