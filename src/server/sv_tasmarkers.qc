// Local manual metadata only. No supplied pose, input credit or movement grant.
void(entity e, string before, string after) SV_TASContactSpansRetag;
float(string path) SV_TASMarkerSize =
{
	local filestream f;
	local float bytes;
	f = fopen(path,FILE_READ);
	if (f < 0) return 0;
	bytes = fsize(f); fclose(f);
	return max(0,bytes);
};

// Reserve normal named/original/stage/child reads before the FIRST strict parse.
// Optional branch/repair reads also consume the scoped reader budget; recheck the
// stage+child reserve before staging metadata. No implicit input save in Freeze.
float(string name, string sha) SV_TASMarkerBudget =
{
	local float named, original, child;
	named = SV_TASMarkerSize(SV_TASPPath(name));
	original = SV_TASMarkerSize(SV_TASPRevPath(sha,"tasp"));
	if (original <= 0) original = named;
	child = max(named,original)+8192;
	if (named+original+2*child > TASP_MARKER_READBYTES) return 0;
	tasp_markerread = TRUE; tasp_markerleft = TASP_MARKER_READBYTES;
	return child;
};

void(entity e, float *cp, float row, float tick) SV_TASMarkerBody =
{
	local float b;
	b = row*TASP_CPSTRIDE;
	cp[b] = tick; cp[b+1] = 1;
	cp[b+2] = e.origin_x; cp[b+3] = e.origin_y; cp[b+4] = e.origin_z;
	cp[b+5] = e.velocity_x; cp[b+6] = e.velocity_y; cp[b+7] = e.velocity_z;
};

void(entity e, float argc) SV_TASMarkersCommand =
{
	local float op, expectedtick, serial, body, request, s, fullhead;
	local float i, j, b, n, named, selected, ordinal, target, inserted, tick, pose;
	local float oldn, oldrev, oldparentrev, olda, oldb, kept, childbytes;
	local float *work;
	local float *oldcp;
	local string old, replacement, expected, name, before, oldnames, acc, label, seen;
	old = replacement = expected = name = before = seen = "";
	op = b = 0;
	work = (float*)0;
	if (argc != 10) goto bad;
	if (!strcmp(argv(2),"add")) op = 1;
	else if (!strcmp(argv(2),"rename")) op = 2;
	else if (!strcmp(argv(2),"remove")) op = 3;
	else if (!strcmp(argv(2),"move")) op = 4;
	else goto bad;
	if (!FS_TASRecipeNameOK(argv(3)) || !FS_TASRecipeNameOK(argv(4))) goto bad;
	old = strzone(argv(3)); replacement = strzone(argv(4)); expected = strzone(argv(6));
	if (strlen(expected) != 64) goto bad;
	if (!FS_TASNumber(argv(5))) goto bad;
	expectedtick = fs_tas_number;
	if (!FS_TASNumber(argv(7))) goto bad;
	serial = fs_tas_number;
	if (!FS_TASNumber(argv(8))) goto bad;
	body = fs_tas_number;
	if (!FS_TASNumber(argv(9))) goto bad;
	request = fs_tas_number;
	if (expectedtick < 0 || expectedtick != floor(expectedtick) ||
		serial != floor(serial) || body != floor(body) || request != floor(request)) goto bad;
	// Bound/Rows/Freeze/Read may tokenize. Every argv value above is now owned.
	if (!SV_TASPLocalOnly(e)) goto done;
	if (!SV_TASEditorBound(e,serial,body,request)) goto done;
	if (!SV_TASEditorRows(e)) goto done;
	if (e.tase_preview || e.tase_operation || e.tasp_load || e.tasp_legal) goto refused;
	s = SV_TASPSlot(e);
	if (!s) goto refused;
	if (strcmp(expected,tasp_revsha[s])) goto stale;
	name = strzone(tasp_name[s]);
	if (e.tasi_dirty || e.tasp_filehead != e.tasp_base+e.tasp_n) goto refused;
	childbytes = SV_TASMarkerBudget(name,expected);
	if (!childbytes) goto budget;
	if (!SV_TASEditorSameInputs(e)) goto refused;
	// Do not overwrite a different current named revision from another writer.
	if (!SV_TASPRead(e,name,TRUE))
	{
		sprint(e,PRINT_HIGH,sprintf("tas marker: attached project unreadable: %s; original retained\n",tpr_why)); goto done;
	}
	if (strcmp(tpr_h,expected))
	{
		// Undo leaves the newer named file in place. Fork only from our own
		// retained history, never overwrite an unrelated writer's revision.
		seen = strzone(tpr_h); kept = FALSE;
		if (!strcmp(e.tase_histname,name) && e.tase_history > 0)
			for (i = 0; i < min(16,e.tase_count*2); i = i+1)
				if (!strcmp(bufstr_get(e.tase_history,i),seen)) kept = TRUE;
		if (!kept) goto stale;
		if (!SV_TASPKeptOK(e,seen)) goto refused;
	}
	if (!SV_TASEditorFreeze(e)) goto done;
	if (tasp_markerleft < 2*childbytes) goto budget;
	if (!SV_TASEditorSameInputs(e)) goto refused;
	fullhead = e.tasp_base+e.tasp_n;
	if (body < e.tasp_base || body > fullhead || e.tasp_filehead != fullhead) goto refused;
	before = strzone(tasp_revsha[s]);
	oldn = e.tasp_ncp; oldcp = tasp_cp[s]; oldnames = tasp_cpnames[s];
	if (oldn < 0 || oldn > TASP_CPMAX || oldn != floor(oldn)) goto refused;
	if (oldn && !oldcp) goto refused;
	selected = target = -1; named = 0;
	ordinal = SV_TASPNameIndex(oldnames,old);
	for (i = 0; i < oldn; i = i+1)
	{
		b = i*TASP_CPSTRIDE;
		if (oldcp[b] == body) target = i;
		if (!oldcp[b+1]) continue;
		if (named == ordinal) selected = i;
		named = named+1;
	}
	if (op == 1)
	{
		if (expectedtick != body) goto stale;
		if (SV_TASPNameIndex(oldnames,replacement) >= 0) goto duplicate;
	}
	else
	{
		if (selected < 0) goto stale;
		if (oldcp[selected*TASP_CPSTRIDE] != expectedtick) goto stale;
		if (op == 2)
		{
			if (!strcmp(old,replacement)) goto unchanged;
			if (SV_TASPNameIndex(oldnames,replacement) >= 0) goto duplicate;
		}
		if (op == 4 && expectedtick == body) goto unchanged;
	}
	if (op == 1 || op == 4)
	{
		if (body <= e.tasp_base)
		{
			sprint(e,PRINT_HIGH,"tas marker: base is already the implicit section start\n"); goto done;
		}
		if (target >= 0)
		if (oldcp[target*TASP_CPSTRIDE+1]) goto duplicate;
	}
	work = (float*)memalloc(TASP_CPMAX*TASP_CPSTRIDE*4);
	if (!work) goto refused;
	n = named = inserted = 0; acc = "";
	for (i = 0; i <= oldn; i = i+1)
	{
		label = ""; tick = 16000001;
		if (i < oldn)
		{
			b = i*TASP_CPSTRIDE; tick = oldcp[b];
			if (oldcp[b+1]) { label = SV_TASPNameAt(oldnames,named); named = named+1; }
		}
		if (op == 1 || op == 4)
		if (!inserted && body < tick)
		{
			if (n >= TASP_CPMAX) goto full;
			SV_TASMarkerBody(e,work,n,body); n = n+1; inserted = TRUE;
			acc = strcat(acc,op == 1 ? replacement : old,";"); // NameAt needs a trailing separator
		}
		if (i == oldn) break;
		if (i == selected && (op == 3 || op == 4))
		{
			if (tick != fullhead) continue;
			label = ""; // preserve the retained end's real snapshot, just remove its name
		}
		if (i == selected && op == 2) label = replacement;
		pose = FALSE;
		if (op == 1 || op == 4)
		if (!inserted && tick == body)
		{
			label = op == 1 ? replacement : old; pose = inserted = TRUE;
		}
		if (n >= TASP_CPMAX) goto full;
		if (pose) SV_TASMarkerBody(e,work,n,body);
		else
		{
			for (j = 0; j < TASP_CPSTRIDE; j = j+1) work[n*TASP_CPSTRIDE+j] = oldcp[b+j];
			work[n*TASP_CPSTRIDE+1] = strlen(label) > 0;
		}
		if (strlen(label)) acc = strcat(acc,label,";");
		n = n+1;
	}
	oldrev = e.tasp_rev; oldparentrev = e.tasp_parentrev;
	olda = e.tasp_supa; oldb = e.tasp_supb;
	if (oldrev >= 16000000) goto refused;
	tasp_cp[s] = work; tasp_cpnames[s] = strzone(acc); e.tasp_ncp = n;
	e.tasp_parentrev = oldrev; e.tasp_rev = oldrev+1;
	e.tasp_supa = e.tasp_supb = 0; // names and snapshots supply no new input
	if (!SV_TASPWrite(e,s,name,name))
	{
		strunzone(tasp_cpnames[s]); tasp_cpnames[s] = oldnames; tasp_cp[s] = oldcp;
		e.tasp_ncp = oldn; e.tasp_rev = oldrev; e.tasp_parentrev = oldparentrev;
		e.tasp_supa = olda; e.tasp_supb = oldb;
		sprint(e,PRINT_HIGH,"tas marker: NOT saved; previous marker map restored, immutable original retained\n");
		goto done;
	}
	work = (float*)0; // the slot now owns it
	if (oldcp) memfree((void*)oldcp);
	if (oldnames) strunzone(oldnames);
	// Match the local parent emitted by the successful write, never on rollback.
	if (tasp_parent[s]) strunzone(tasp_parent[s]);
	tasp_parent[s] = strzone(name);
	e.tasp_filehead = fullhead;
	// Synced/lasthead stay at the ACTUAL body, not the future metadata horizon.
	SV_TASPParentKeep(e,s);
	kept = SV_TASPKeep(SV_TASPPath(name),tasp_revsha[s],FALSE,FALSE);
	if (kept) kept = SV_TASPKeptOK(e,tasp_revsha[s]);
	// Expected is the request-bound unchanged line, before any metadata freeze.
	if (kept) SV_TASContactSpansRetag(e,expected,tasp_revsha[s]);
	if (kept)
		kept = SV_TASEditorHistoryPush(e,before,tasp_revsha[s]);
	if (!kept) sprint(e,PRINT_HIGH,"tas marker: saved; new immutable history unavailable, previous original retained\n");
	e.tasp_made = SV_TASPFileIs(SV_TASPRevPath(tasp_revsha[s],"made"));
	e.tasp_signed = SV_TASPSignedFor(tasp_revsha[s]);
	sprint(e,PRINT_HIGH,sprintf("tas marker: saved %s; complete inputs %.0f..%.0f, body %.0f, supply none\n",
		op == 1 ? replacement : old,e.tasp_base+1,fullhead,body));
	SV_TASProjectEvent(e);
	goto done;
:full
	sprint(e,PRINT_HIGH,"tas marker: checkpoint storage full; nothing changed\n"); goto done;
:duplicate
	sprint(e,PRINT_HIGH,"tas marker: that name or body tick already has a named endpoint; nothing changed\n"); goto done;
:unchanged
	sprint(e,PRINT_HIGH,"tas marker: endpoint already unchanged\n"); goto done;
:stale
	sprint(e,PRINT_HIGH,"tas marker: stale revision or endpoint; Refresh before editing\n"); goto done;
:budget
	sprint(e,PRINT_HIGH,"tas marker: project too large for one synchronous marker edit; original retained\n"); goto done;
:refused
	sprint(e,PRINT_HIGH,"tas marker: complete unchanged local line required; original retained\n"); goto done;
:bad
	sprint(e,PRINT_HIGH,"tas marker: invalid bound metadata request\n");
:done
	tasp_markerread = FALSE; tasp_markerleft = 0;
	if (work) memfree((void*)work);
	if (old) strunzone(old);
	if (replacement) strunzone(replacement);
	if (expected) strunzone(expected);
	if (name) strunzone(name);
	if (before) strunzone(before);
	if (seen) strunzone(seen);
};
