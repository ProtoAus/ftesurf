#undef CSQC_Init
#undef CSQC_ConsoleCommand
#undef CSQC_UpdateView
#undef CSQC_InputEvent

vector p603_point;

void() P603_HttpFrame;
void(float width, float height, float notmenu) CSQC_UpdateView =
{
	P603_RealView(width, height, notmenu);
	P603_HttpFrame(); //HTTP snapshots observe the completed real draw, not the prior frame.
};

float(float type, float scan, float chars, float device) CSQC_InputEvent =
{
	//This synthetic-event rig owns absolute motion. Win32's real cursor otherwise
	//overwrites it every inactive-mouse frame (INS_Accumulate), cancelling clicks.
	if (type == IE_MOUSEABS) return FALSE;
	return P603_RealInput(type, scan, chars, device);
};

void() P603_Mouse =
{
	local vector pixel, virt;
	pixel = getproperty(VF_SCREENPSIZE);
	virt = getproperty(VF_SCREENVSIZE);
	P603_RealInput(IE_MOUSEABS, p603_point_x * virt_x / pixel_x, p603_point_y * virt_y / pixel_y, 0);
};

void(float apilevel, string enginename, float engineversion) CSQC_Init =
{
	P603_RealInit(apilevel, enginename, engineversion);
	registercommand("p603");
	registercommand("p603follow");
	registercommand("p603http");
	registercommand("p603life");
	registercommand("p603font");
	registercommand("p603dense");
	registercvar("p603life_fail", "0");
	print(sprintf("P603 CAP gamefocus=%g model=%g\n", checkbuiltin(ui_native_gamefocus),
		checkbuiltin(ui_native_model_commit)));
};

void(string target) P603_Point =
{
	local int i;
	local float literal;
	local vector pixel, virt, ratio;
	local string id;
	pixel = getproperty(VF_SCREENPSIZE);
	virt = getproperty(VF_SCREENVSIZE);
	ratio = [pixel_x / virt_x, pixel_y / virt_y, 0];
	//A target spelt as a sui id (the source switch, sb_t0..3) is QC's on either route.
	literal = !strcmp(substring(target, 0, 3), "sb_");
	if (scn_painted && !literal)
	{
		//Coordinates of actual rendered fixed-width columns, not an injected
		//native action. The grader requires Watch_Open/line work to ACT.
		p603_point = [scn_pos_x * ratio_x + 235, scn_pos_y * ratio_y + 55, 0];
		if (!strcmp(target, "line")) p603_point_x = scn_pos_x * ratio_x + 777;
		if (!strcmp(target, "missing")) p603_point_y = p603_point_y + 23;
		if (!strcmp(target, "next")) p603_point =
			[scn_pos_x * ratio_x + 140, (scn_pos_y + scn_size_y) * ratio_y - 18, 0];
		if (!strcmp(target, "previous")) p603_point =
			[scn_pos_x * ratio_x + 42, (scn_pos_y + scn_size_y) * ratio_y - 18, 0];
	}
	else
	{
		id = !strcmp(target, "line") ? "sb_ln0" : "sb_run0";
		if (Scores_IsOnline())
			if (strcmp(target, "line")) id = !strcmp(target, "missing") ? "sb_ob1" : "sb_ob0";
		if (literal) id = target;
		for (i = 0i; i < (int)min(MAX_ACTION_ELEMENTS, _action_elements_index); i = i + 1i)
			if (!strcmp(_action_elements[i].id, id))
			{
				p603_point = _action_elements[i].pos + [12, _action_elements[i].size.y * 0.5, 0];
				p603_point_x = p603_point_x * ratio_x;
				p603_point_y = p603_point_y * ratio_y;
				break;
			}
	}
	print(sprintf("P603 POINT %s %.2f %.2f\n", target, p603_point_x, p603_point_y));
	P603_Mouse();
};

float(string cmd) P603_FollowCommand;
float(string cmd) P603_HttpCommand;
float(string cmd) P603_LifeCommand;
float(string cmd) P603_FontCommand;
float(string cmd) P603_DenseCommand;
float(string cmd) CSQC_ConsoleCommand =
{
	local string op, label;
	local float i, lines;
	tokenize(cmd);
	if (P603_FollowCommand(cmd)) return TRUE;
	if (P603_HttpCommand(cmd)) return TRUE;
	if (P603_LifeCommand(cmd)) return TRUE;
	if (P603_FontCommand(cmd)) return TRUE;
	if (P603_DenseCommand(cmd)) return TRUE;
	if (strcmp(argv(0), "p603")) return P603_RealCommand(cmd);
	op = argv(1);
	if (!strcmp(op, "probe"))
	{
		label = argv(2);
		lines = 0;
		for (i = 0; i < SB_LNMAX; i = i + 1) if (sb_ln_st[i] != SBL_FREE) lines = lines + 1;
		print(sprintf("P603 STATE %s h=%g painted=%g failed=%g revision=%g page=%g rows=%g\n",
			label, scn_handle, scn_painted, scn_failed, scn_revision, scn_page, rec_sb_rown));
		print(sprintf("P603 OWNER %s held=%g pin=%g cursor=%g focus=%g down=%g taken=%g\n",
			label, sc_held, rec_sb_open, UI_CursorHeld(), NUI_GameFocus(), cl_btn_down, cl_btn_taken));
		print(sprintf("P603 ACTIVE %s watch=%g samples=%g lines=%g\n",
			label, rec_wt_open, rec_wt_nsamp, lines));
		print(sprintf("P603 LINE %s ready=%g samples=%g\n", label, sb_ln_st[0] == SBL_ON, ln_n[1]));
		print(sprintf("P603 RECT %s %g %g %g %g\n", label, scn_pos_x, scn_pos_y, scn_size_x, scn_size_y));
	}
	else if (!strcmp(op, "move")) P603_Point(argv(2));
	else if (!strcmp(op, "tab"))
		print(sprintf("P603 TAB %s tab=%g online=%g\n", argv(2), rec_sb_tab, Scores_IsOnline()));
	else if (!strcmp(op, "down"))
	{
		P603_Mouse();
		lines = CSQC_InputEvent(IE_KEYDOWN, K_MOUSE1, 0, 0);
		print(sprintf("P603 EDGE down took=%g hover=%g handle=%g revision=%g focus=%g\n",
			lines, scn_hover, scn_handle, scn_revision, NUI_GameFocus()));
	}
	else if (!strcmp(op, "up"))
	{
		P603_Mouse();
		lines = CSQC_InputEvent(IE_KEYUP, K_MOUSE1, 0, 0);
		print(sprintf("P603 EDGE up took=%g hover=%g handle=%g revision=%g focus=%g\n",
			lines, scn_hover, scn_handle, scn_revision, NUI_GameFocus()));
	}
	//Button edges with no position refresh: the cursor is wherever motion left it.
	else if (!strcmp(op, "rawdown")) CSQC_InputEvent(IE_KEYDOWN, K_MOUSE1, 0, 0);
	else if (!strcmp(op, "rawup")) CSQC_InputEvent(IE_KEYUP, K_MOUSE1, 0, 0);
	else if (!strcmp(op, "pin")) CSQC_InputEvent(IE_KEYDOWN, K_MOUSE2, 0, 0);
	else if (!strcmp(op, "unpin")) CSQC_InputEvent(IE_KEYUP, K_MOUSE2, 0, 0);
	else if (!strcmp(op, "focus")) CSQC_InputEvent(IE_FOCUS, stof(argv(2)), stof(argv(3)), 0);
	else if (!strcmp(op, "rescan")) rec_sb_legbuilt = -2;
	else print("P603 UNKNOWN\n");
	return TRUE;
};
