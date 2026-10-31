// TAS workshop: local draft -> existing validated command/ticket channel.
float tasu_open, tasu_mode, tasu_forward, tasu_side, tasu_pitch, tasu_yaw, tasu_bits, tasu_count;
float tasu_nextclick, tasu_frames, tasu_tab;
void() TASTimeline_Reset;
void(float first) TASTimeline_Request;
void(vector at, float width, float tsz, float hint, float row) TASTimeline_Draw;
void(vector at, float width, float tsz, float hint, float row) TASShare_Draw;
void(float before, string sha) TASShare_Request;
float(float argc, float seat) TASShare_ConsoleCommand;
void() TASProject_SignPress;

void() TASUI_Close =
{
	if (!tasu_open) return;
	tasu_open = FALSE;
	tasu_tab = 0;
	TASTimeline_Reset();
	UI_CursorRelease(UIC_TAS);
	sui_reset_actions();
	sui_tooltip_reset();
};

void() TASUI_FromServer =
{
	tasu_mode = bound(TAS_PLAN_LIVE, getstatf(STAT_FS_TASPLANMODE), TAS_PLAN_RIGHT);
	tasu_forward = getstatf(STAT_FS_TASPLANFORWARD);
	tasu_side = getstatf(STAT_FS_TASPLANSIDE);
	// Quantized +89 is 89.000244 degrees; retain its word via legal endpoint.
	tasu_pitch = bound(-89, getstatf(STAT_FS_TASPLANPITCH), 89);
	tasu_yaw = getstatf(STAT_FS_TASPLANYAW);
	tasu_bits = getstatf(STAT_FS_TASPLANBITS);
};

void() TASUI_FromView =
{
	local vector angles;
	angles = getproperty(VF_ANGLES);
	if (angles_x > 180) angles_x = angles_x - 360;
	tasu_pitch = bound(-89, angles_x, 89);
	tasu_yaw = angles_y - floor((angles_y + 180) / 360) * 360;
};

void(float seat) TASUI_Toggle =
{
	if (tasu_open) { TASUI_Close(); return; }
	if (seat != 0 || numclientseats > 1)
	{
		print("tas: window is single-seat; use the active-seat console controls for split screen\n");
		return;
	}
	if (!LT_StatsAreMine()) { print("tas: return to your own body before opening the workshop\n"); return; }
	if (UI_CursorHeld() || rec_sb_open) { print("tas: close the other panel first\n"); return; }
	TASUI_FromServer();
	if (tasu_mode == TAS_PLAN_LIVE)
	{
		tasu_forward = 450; tasu_side = tasu_bits = 0;
		TASUI_FromView();
	}
	tasu_count = 8;
	tasu_nextclick = tasu_frames = 0;
	tasu_open = TRUE;
	sui_reset_actions();
	UI_CursorClaim(UIC_TAS);
};

void() TASUI_Mouse =
{
	if (!cvar_type("cl_tas_mouselock"))
	{
		print("tas: mouse lock needs the updated client engine\n");
		return;
	}
	cvar_set("cl_tas_mouselock", cvar("cl_tas_mouselock") ? "0" : "1");
};

void(float count) TASUI_Send =
{
	local string line;
	if (cltime < tasu_nextclick) return;
	if (getstatf(STAT_FS_TASPLANCAP) < TAS_PLAN_CAP) { print("tas: authored inputs need the updated server engine\n"); return; }
	if (getstatf(STAT_FS_TASPAUSE) != 1) { print("tas: press Pause first\n"); return; }
	if (getstatf(STAT_FS_TASPENDING) || getstatf(STAT_FS_TASREPLAY) == TAS_TAPE_ACTIVE)
	{
		print("tas: wait for the current steps/replay, or Play to cancel\n");
		return;
	}
	tasu_nextclick = cltime + 0.3;
	// Stats can lag a newer configuration. Every Advance binds its full draft;
	// native idempotent configuration preserves an unchanged assist's heading.
	line = sprintf("tas %s %s %g %g %.13f %.13f %g", count ? "next" : "plan",
		FS_TASPlanName(tasu_mode), tasu_forward, tasu_side, tasu_pitch, tasu_yaw, tasu_bits);
	if (count) line = strcat(line, sprintf(" %g", count));
	localcmd(strcat(line, "\n"));
};

void(float v) TASUI_Forward = { tasu_forward = rint(v); };
void(float v) TASUI_Side = { tasu_side = rint(v); };
void(float v) TASUI_Pitch = { tasu_pitch = v; };
void(float v) TASUI_Yaw = { tasu_yaw = v; };
void(float v) TASUI_Count = { tasu_count = bound(1, rint(v), TAS_TAPE_MAX); };
void(float bit) TASUI_Bit =
{
	if (tasu_bits & bit) tasu_bits = tasu_bits - bit;
	else tasu_bits = tasu_bits + bit;
};

void(vector scr) TASUI_Draw =
{
	local float sc, tsz, hint, row, pad, width, oldfont, i, paused, seat;
	local vector pos, size, at, chip;
	local string label;
	if (!tasu_open) return;
	// fteqcc compares a bare __variant as a 64-bit pair (OP_NE_I64 against 0 and
	// the next constant), which returned here every frame; read it as a float.
	seat = getproperty(VF_ACTIVESEAT);
	if (seat != 0) return;
	if (numclientseats > 1 || UI_CursorHeld() != UIC_TAS || rec_sb_open || !LT_StatsAreMine())
	{
		TASUI_Close(); return;
	}
	tasu_frames = tasu_frames + 1;
	sc = max(0.5, ui_cv_scale);
	while (sc > 0.5 && (Font_Px(8 * sc) * 48 > scr_x - 12 || Font_Px(8 * sc) * 44 > scr_y - 12)) sc = sc - 0.5;
	oldfont = drawfont; Font_Set(ui_font_ui);
	tsz = Font_Px(8 * sc); hint = Font_Px(6 * sc); row = ceil(tsz * 1.8); pad = tsz;
	size = [min(scr_x - 8, tsz * 48), min(scr_y - 8, tsz * 44), 0];
	pos = [scr_x - size_x - 6, max(4, (scr_y - size_y) * 0.5), 0];
	width = size_x - pad * 2;
	sui_begin(scr_x, scr_y);
	sui_style_panel(pos, size, ceil(pad * 0.75), 0.98);
	sui_text(pos + [pad, pad, 0], [tsz * 1.25, tsz * 1.25], "TAS workshop", SUI_THEME_TEXT, 1, 0);
	if (Profile_Chip("tasu_close", pos + [size_x - pad - row, pad * 0.6, 0], [row, row, 0], "X", tsz, FALSE))
	{
		TASUI_Close(); sui_end(); Font_Set(oldfont); return;
	}
	if (Profile_Chip("tasu_tab", pos + [size_x - pad - row - tsz*9, pad*0.6, 0], [tsz*8,row,0],
		tasu_tab == 0 ? "Timeline" : (tasu_tab == 1 ? "Shared" : "Next input"), hint, tasu_tab))
	{
		tasu_tab = (tasu_tab + 1) % 3;
		if (tasu_tab == 1) TASTimeline_Request(0);
		if (tasu_tab == 2) TASShare_Request(0,"");
	}
	at = pos + [pad, tsz * 3, 0];
	sui_text(at, [hint, hint], "ASSISTED / PRACTICE - never a human ranked run", SUI_THEME_ACCENT, 1, 0);
	at_y = at_y + tsz * 1.7;
	paused = (getstatf(STAT_FS_TASPAUSE) == 1);
	sui_text(at, [hint, hint], sprintf("%s | pending %.0f | completed %.0f | request %.0f",
		paused ? "PAUSED" : "PLAYING", getstatf(STAT_FS_TASPENDING), getstatf(STAT_FS_TASDONE), getstatf(STAT_FS_TASREQUEST)), SUI_THEME_DIM, 1, 0);
	at_y = at_y + tsz * 1.6;
	chip = [(width - 12) / 3, row, 0];
	if (Profile_Chip("tasu_pause", at, chip, "Pause", tsz, paused)) localcmd("tas pause\n");
	if (Profile_Chip("tasu_play", at + [(width + 6) / 3, 0, 0], chip, "Play", tsz, FALSE))
		{ localcmd("tas play\n"); TASUI_Close(); sui_end(); Font_Set(oldfont); return; }
	if (Profile_Chip("tasu_off", at + [(width + 6) * 2 / 3, 0, 0], chip, "Controls off", tsz, FALSE))
		{ localcmd("tas off\n"); TASUI_Close(); sui_end(); Font_Set(oldfont); return; }
	at_y = at_y + tsz * 2.7;
	if (tasu_tab)
	{
		if (tasu_tab == 2) TASShare_Draw(at,width,tsz,hint,row);
		else TASTimeline_Draw(at,width,tsz,hint,row);
		sui_end(); Font_Set(oldfont); return;
	}
	sui_text(at, [hint, hint], "Choose the NEXT command; nothing moves until Advance.", SUI_THEME_DIM, 1, 0);
	at_y = at_y + tsz * 1.6;
	for (i = 0; i < 4; i = i + 1)
	{
		label = "Live keys";
		if (i == 1) label = "Manual";
		if (i == 2) label = "Auto left";
		if (i == 3) label = "Auto right";
		if (Profile_Chip(sprintf("tasu_mode%g", i), at + [i * (width + 6) / 4, 0, 0], [(width - 18) / 4, row, 0], label, tsz, tasu_mode == i)) tasu_mode = i;
	}
	at_y = at_y + tsz * 2.5;
	sui_text(at, [hint, hint], "Auto: best observed-air yaw each tick; NOT route search.", SUI_THEME_MUTED, 1, 0);
	at_y = at_y + tsz * 1.5;
	sui_text(at, [hint, hint], "Air uses full 450-side key; ground/other states use preset:", SUI_THEME_MUTED, 1, 0);
	at_y = at_y + tsz * 1.7;
	WPU_Slider("tasu_forward", "Forward", at, width, tasu_forward, '-450 450 900', TASUI_Forward, tsz);
	at_y = at_y + tsz * 2.2;
	WPU_Slider("tasu_side", "Side", at, width, tasu_side, '-450 450 900', TASUI_Side, tsz);
	at_y = at_y + tsz * 2.2;
	for (i = 0; i < 5; i = i + 1)
	{
		label = "W";
		if (i == 1) label = "A";
		if (i == 2) label = "S";
		if (i == 3) label = "D";
		if (i == 4) label = "None";
		if (Profile_Chip(sprintf("tasu_key%g", i), at + [i * (width + 6) / 5, 0, 0], [(width - 24) / 5, row, 0], label, tsz, FALSE))
		{
			tasu_forward = tasu_side = 0;
			if (i == 0) tasu_forward = 450;
			if (i == 1) tasu_side = -450;
			if (i == 2) tasu_forward = -450;
			if (i == 3) tasu_side = 450;
		}
	}
	at_y = at_y + tsz * 2.5;
	if (Profile_Chip("tasu_jump", at, chip, "Jump held", tsz, tasu_bits & 1)) TASUI_Bit(1);
	if (Profile_Chip("tasu_duck", at + [(width + 6) / 3, 0, 0], chip, "Duck held", tsz, tasu_bits & 2)) TASUI_Bit(2);
	if (Profile_Chip("tasu_walk", at + [(width + 6) * 2 / 3, 0, 0], chip, "Walk held", tsz, tasu_bits & 4)) TASUI_Bit(4);
	at_y = at_y + tsz * 2.5;
	WPU_Slider("tasu_pitch", "Pitch", at, width, tasu_pitch, '-89 89 1780', TASUI_Pitch, tsz);
	at_y = at_y + tsz * 2.2;
	WPU_Slider("tasu_yaw", "Yaw", at, width, tasu_yaw, '-180 180 3600', TASUI_Yaw, tsz);
	at_y = at_y + tsz * 2.2;
	if (Profile_Chip("tasu_view", at, chip, "Use view", tsz, FALSE)) TASUI_FromView();
	if (Profile_Chip("tasu_server", at + [(width + 6) / 3, 0, 0], chip, "Use server", tsz, FALSE)) TASUI_FromServer();
	label = cvar("cl_tas_mouselock") ? "Mouse locked" : "Mouse free";
	if (Profile_Chip("tasu_mouse", at + [(width + 6) * 2 / 3, 0, 0], chip, label, tsz, cvar("cl_tas_mouselock"))) TASUI_Mouse();
	at_y = at_y + tsz * 2.5;
	WPU_Slider("tasu_count", "Ticks", at, width, tasu_count, '1 128 127', TASUI_Count, tsz);
	at_y = at_y + tsz * 2.3;
	if (Profile_Chip("tasu_back", at, [(width - 18) / 4, row, 0], "Back 1", tsz, FALSE)) localcmd("tas back 1\n");
	if (Profile_Chip("tasu_one", at + [(width + 6) / 4, 0, 0], [(width - 18) / 4, row, 0], "Advance 1", tsz, FALSE)) TASUI_Send(1);
	if (Profile_Chip("tasu_many", at + [(width + 6) / 2, 0, 0], [(width - 18) / 4, row, 0], sprintf("Advance %g", tasu_count), tsz, FALSE)) TASUI_Send(tasu_count);
	if (Profile_Chip("tasu_apply", at + [(width + 6) * 3 / 4, 0, 0], [(width - 18) / 4, row, 0], "Apply only", tsz, FALSE)) TASUI_Send(0);
	at_y = at_y + tsz * 2.7;
	label = sprintf("Server: %s | last authored step: %s", FS_TASPlanName(getstatf(STAT_FS_TASPLANMODE)), getstatf(STAT_FS_TASPLANAIR) ? "air selector" : "preset/live");
	if (getstatf(STAT_FS_TASPLANCAP) < TAS_PLAN_CAP) label = "Authoring unavailable: update the server engine.";
	sui_text(at, [hint, hint], label, SUI_THEME_DIM, 1, 0);
	at_y = at_y + tsz * 1.7;
	sui_text(at, [hint, hint], "Mouse free: Esc, aim, reopen, Use view. Esc keeps pause/plan.", SUI_THEME_MUTED, 1, 0);
	at_y = at_y + tsz * 1.5;
	sui_text(at, [hint, hint], "Back needs a running recorded timeline. Shared world is NOT paused.", SUI_THEME_MUTED, 1, 0);
	sui_end(); Font_Set(oldfont);
};

float(float evtype, float scanx, float chary, float devid) TASUI_Input =
{
	if (!tasu_open) return FALSE;
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE) { TASUI_Close(); return TRUE; }
	if (evtype == IE_MOUSEABS)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN) _sui_mouse_move(_cursor_position, FALSE);
		if (evtype == IE_KEYDOWN && scanx == K_MOUSE1 && tasu_tab == 1 && sui_is_hovered("tasp_sign")) TASProject_SignPress();
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	return FALSE; // do not strand releases of keys held before the panel opened
};
