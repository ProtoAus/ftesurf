// Named input templates reference retained rows, never the source project's body.
float *tasr_rows;
float tasr_count;

void() SV_TASRecipeFree =
{
	if (tasr_rows) memfree(tasr_rows);
	tasr_rows = 0; tasr_count = 0;
};

string(string name) SV_TASRecipePath = { return sprintf("data/tasproj/%s/recipes/%s.tasr", mapname, name); };

// The current target has its own base. Only the input span and fixed clock travel.
float(entity e, float *rows, float base, float count, float first, float last) SV_TASRecipeFits =
{
	if (!tasr_rows || tasr_count < 1 || last - first + 1 != tasr_count ||
		first < base + 1 || last > base + count)
	{
		sprint(e, PRINT_HIGH, "tas recipe: selected row count differs; nothing moved\n");
		return FALSE;
	}
	return TRUE;
};

void(float *rows, float base, float first, float last) SV_TASRecipePaste =
{
	local float i, j, target;
	for (i = 0; i < tasr_count; i = i + 1)
	{
		target = (first + i - base - 1) * TAS_INPUT_STRIDE;
		for (j = 0; j < TAS_INPUT_STRIDE; j = j + 1)
			rows[target+j] = tasr_rows[i*TAS_INPUT_STRIDE+j];
	}
};

float(entity e, string name) SV_TASRecipeRead =
{
	local filestream f;
	local string line, hash, path;
	local float first, last, tick, ok, i, j, source;

	SV_TASRecipeFree(); hash = path = "";
	f = fopen(SV_TASRecipePath(name), FILE_READ);
	if (f < 0) { sprint(e, PRINT_HIGH, "tas recipe: no such named recipe on this map\n"); return FALSE; }
	line = strzone(fgets(f));
	ok = !strcmp(fgets(f), "");
	fclose(f);
	if (!ok || tokenize(line) != 6) goto bad;
	if (strcmp(argv(0), "tasrecipe") || strcmp(argv(1), "1") || !SV_TASPHex(argv(2), 64)) goto bad;
	hash = strzone(argv(2));
	if (!SV_TASPNum(argv(3), 1, 16000000, TRUE)) goto bad;
	first = fs_tas_number;
	if (!SV_TASPNum(argv(4), first, 16000000, TRUE)) goto bad;
	last = fs_tas_number;
	if (!SV_TASPNum(argv(5), 0.001, 0.1, FALSE)) goto bad;
	tick = fs_tas_number;
	if (strcmp(line, sprintf("tasrecipe 1 %s %.0f %.0f %.9g",hash,first,last,tick))) goto bad;
	if (tick != run_t_tick)
	{
		sprint(e, PRINT_HIGH, "tas recipe: fixed tick duration differs; nothing moved\n");
		goto bad;
	}
	// Strictly compare the retained input file's map/zone/profile and computed hash.
	// Do not call its base loader or import its token, prefix, made or signature.
	path = strzone(SV_TASPRevPath(hash,"tasp"));
	tpr_pathover = path;
	ok = SV_TASPRead(e,"",TRUE);
	tpr_pathover = "";
	if (!ok)
	{
		sprint(e, PRINT_HIGH, sprintf("tas recipe: retained input source refused (%s); nothing moved\n",tpr_why));
		goto bad;
	}
	if (strcmp(tpr_h,hash) || first < tpr_base+1 || last > tpr_base+tpr_n || last-first+1 > TASP_MAX) goto bad;
	tasr_count = last-first+1;
	tasr_rows = (float*)memalloc(tasr_count*TAS_INPUT_STRIDE*4);
	if (!tasr_rows) goto bad;
	for (i = 0; i < tasr_count; i = i + 1)
	{
		source = (first+i-tpr_base-1)*TAS_INPUT_STRIDE;
		for (j = 0; j < TAS_INPUT_STRIDE; j = j + 1)
			tasr_rows[i*TAS_INPUT_STRIDE+j] = tpr_buf[source+j];
	}
	// op1 is a decode-only native admission check; it neither stages nor moves.
	if (SV_TASPValidate(e,tasr_rows,tasr_count) > 0)
	{
		sprint(e,PRINT_HIGH,"tas recipe: unsupported native input row; nothing moved\n");
		goto bad;
	}
	SV_TASPReadFree(); strunzone(path); strunzone(hash); strunzone(line);
	return TRUE;
:bad
	tpr_pathover = "";
	SV_TASPReadFree(); SV_TASRecipeFree();
	if (path) strunzone(path);
	if (hash) strunzone(hash);
	strunzone(line);
	sprint(e, PRINT_HIGH, "tas recipe: invalid or unavailable template; original retained\n");
	return FALSE;
};

void(entity e, string name, float first, float last) SV_TASRecipeSave =
{
	local float s, ok, search;
	local filestream f;
	local string path, tmp, line, got;

	s = SV_TASPSlot(e);
	if (!s || !SV_TASEditorReady(e) || !SV_TASEditorRows(e)) return;
	if (e.tase_preview || e.tase_operation)
	{
		sprint(e, PRINT_HIGH, "tas recipe: settle Keep/Discard/Undo before saving a template\n"); return;
	}
	if (first < e.tasp_base+1 || last < first || last > e.tasp_base+e.tasp_n)
	{
		sprint(e, PRINT_HIGH, "tas recipe: select an existing captured span\n"); return;
	}
	path = strzone(SV_TASRecipePath(name)); tmp = strzone(strcat(path,".new"));
	if (SV_TASPFileIs(path) || SV_TASPFileIs(tmp))
	{
		sprint(e, PRINT_HIGH, "tas recipe: name or retained unfinished write exists; choose another name\n");
		strunzone(path); strunzone(tmp); return;
	}
	search = search_begin(sprintf("data/tasproj/%s/recipes/*.tasr",mapname),FS_NAMESORT,TRUE);
	if (search >= 0)
	{
		ok = (search_getsize(search) < TASP_FILES); search_end(search);
		if (!ok)
		{
			sprint(e,PRINT_HIGH,"tas recipe: this map already has 64 named templates\n");
			strunzone(path); strunzone(tmp); return;
		}
	}
	if (!SV_TASEditorFreeze(e)) { strunzone(path); strunzone(tmp); return; }
	if (!SV_TASPKeptOK(e,tasp_revsha[s])) { strunzone(path); strunzone(tmp); return; }
	line = strzone(sprintf("tasrecipe 1 %s %.0f %.0f %.9g",tasp_revsha[s],first,last,run_t_tick));
	f = fopen(tmp,FILE_WRITE);
	if (f < 0)
	{
		sprint(e,PRINT_HIGH,"tas recipe: cannot write template; original line unchanged\n");
		strunzone(path); strunzone(tmp); strunzone(line); return;
	}
	fputs(f,strcat(line,"\n")); fclose(f);
	f = fopen(tmp,FILE_READ); ok = FALSE;
	if (f >= 0)
	{
		got = strzone(fgets(f));
		ok = (!strcmp(got,line) && !strcmp(fgets(f),""));
		strunzone(got); fclose(f);
	}
	if (ok) ok = (frename(tmp,path) == 0);
	if (ok) sprint(e,PRINT_HIGH,sprintf("tas recipe: saved %s, %.0f actual input rows at %.9g s/tick; generating intent unknown\n",name,last-first+1,run_t_tick));
	else sprint(e,PRINT_HIGH,"tas recipe: save not committed; retained unfinished write, original line unchanged\n");
	strunzone(path); strunzone(tmp); strunzone(line);
};

// Numeric binding is read before any project/recipe parser changes argv.
void(entity e, float argc) SV_TASRecipeCommand =
{
	local string action, name;
	local float first, last, serial, head, request;

	if (argc != 8) return;
	action = strzone(argv(1)); name = strzone(argv(2));
	if (!FS_TASRecipeNameOK(name)) goto bad;
	if (!FS_TASNumber(argv(3))) goto bad;
	first = fs_tas_number;
	if (!FS_TASNumber(argv(4))) goto bad;
	last = fs_tas_number;
	if (!FS_TASNumber(argv(5))) goto bad;
	serial = fs_tas_number;
	if (!FS_TASNumber(argv(6))) goto bad;
	head = fs_tas_number;
	if (!FS_TASNumber(argv(7))) goto bad;
	request = fs_tas_number;
	if (first < 1 || last < first || last > 16000000 || first != floor(first) || last != floor(last)) goto bad;
	if (!SV_TASEditorBound(e,serial,head,request)) goto done;
	if (!SV_TASEditorRows(e) || e.tase_operation || e.tase_preview) goto bad;
	if (time < e.tase_next) { sprint(e,PRINT_HIGH,"tas recipe: wait for the previous action\n"); goto done; }
	e.tase_next = time+0.35;
	if (!strcmp(action,"recipesave2")) SV_TASRecipeSave(e,name,first,last);
	else if (!strcmp(action,"recipeapply2"))
	{
		if (SV_TASRecipeRead(e,name))
		{
			if (SV_TASRecipeFits(e,tasp_buf[SV_TASPSlot(e)],e.tasp_base,e.tasp_n,first,last))
				SV_TASEditorPreview(e,first,last,TAS_RECIPE_FIELD,0);
			SV_TASRecipeFree();
		}
	}
	else goto bad;
	goto done;
:bad
	sprint(e,PRINT_HIGH,"tas recipe: invalid or unsettled typed action; nothing moved\n");
:done
	strunzone(action); strunzone(name);
};
