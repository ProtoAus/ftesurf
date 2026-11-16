/*
===========================================================================
  cl_gamemode.qc -- `hud_gamemode`, the movement mode picker.  P1598.

  Lists P1589's movement profiles 1-7; a click or its digit switches.  The
  engine's movementprofile_switch builtin sets sv_movementprofile (NOTFROMSERVER,
  so no QC text can) and reloads the map, only while this game hosts it: on a
  lobby the rows are inert and say so.  None of these modes is ranked yet.
===========================================================================
*/
#define UIC_GAMEMODE 32768      // cl_hud.qc's cursor register: the next free bit
#define GM_N 7

float(string mode) movementprofile_switch = #0:movementprofile_switch;   // P1598 engine
float() cmdlevel_local = #0:cmdlevel_local;     // P1598 engine: inside the player's own console line or bind

float  ui_gm_open;
float  gm_drag;
vector gm_pos, gm_size, gm_off;
float  gm_mx, gm_my, gm_titleh;
float  gm_rowx, gm_roww, gm_rowy, gm_rowh, gm_rowbh;   // the rows: left, width, first top, pitch, box height
string gm_note;                 // the last refusal, shown in the footer
float  gm_kmine;                // digits whose press we took: their release is ours too (as Vote_Key)
float  gm_note_t;

string(float i) GameMode_Sel =
{
	switch (i)
	{
		case 1: return "default";
		case 2: return "hl2-pre";
		case 3: return "hl2-post";
		case 4: return "ag-100";
		case 5: return "ag-250";
		case 6: return "ag-1000";
		case 7: return "cs16";
	}
	return "";
};

string(float i) GameMode_Name =
{
	switch (i)
	{
		case 1: return "Default";
		case 2: return "Half-Life 2 (pre)";
		case 3: return "Half-Life 2 (post)";
		case 4: return "AG 100";
		case 5: return "AG 250";
		case 6: return "AG 1000";
		case 7: return "Counter-Strike 1.6";
	}
	return "";
};

string(float i) GameMode_Blurb =
{
	switch (i)
	{
		case 1: return "Momentum Mod / CS:S surf and bhop";
		case 2: return "HL2 before the jump limiter: the boost stacks";
		case 3: return "HL2 after the limiter: the boost is capped";
		case 4: return "Adrenaline Gamer / Half-Life, 100 tick";
		case 5: return "Adrenaline Gamer / Half-Life, 250 tick";
		case 6: return "Adrenaline Gamer / Half-Life, 1000 tick";
		case 7: return "CS 1.6: jump stamina and the bhop cap";
	}
	return "";
};

// The running mode's row: serverinfo *movementprofile is the identity ("ag-100-v1"), "" for default.
float() GameMode_Current =
{
	local string id;
	local float i;

	id = serverkey("*movementprofile");
	if (id == "")
		return 1;
	for (i = 2; i <= GM_N; i = i + 1)
		if (id == strcat(GameMode_Sel(i), "-v1"))
			return i;
	return 0;
};

// "" when a pick can act, else why not.
string() GameMode_Why =
{
	if (!isserver())
		return "Only in a game you host (Local game). A lobby keeps its own mode.";
	if (!checkbuiltin(movementprofile_switch))
		return "This game version cannot switch modes yet (needs P1598's engine).";
	return "";
};

// Another panel's cursor claim, or the pinned board: the picker yields, as cl_gfx.qc's does.
float() GameMode_OthersHeld =
{
	local float held;

	held = UI_CursorHeld();
	if (held & UIC_WATCH) held = held - UIC_WATCH;
	if (held & UIC_GAMEMODE) held = held - UIC_GAMEMODE;
	if (held & UIC_GFX) held = held - UIC_GFX;       // GameMode_Open closes it
	return held || rec_sb_open;
};

void() GameMode_Close =
{
	ui_gm_open = FALSE;
	gm_drag = FALSE;
	UI_CursorRelease(UIC_GAMEMODE);
	sui_reset_actions();
	sui_tooltip_reset();
};

void() GameMode_Open =
{
	if (GameMode_OthersHeld())
	{
		print("hud_gamemode: close the other panel first\n");
		return;
	}
	if (ui_gfx_open)
		Gfx_Close();
	ui_gm_open = TRUE;
	gm_drag = FALSE;
	gm_mx = gm_my = -100000;        // no stale pointer on a row until the mouse moves (review)
	gm_note = "";
	sui_reset_actions();
	UI_CursorClaim(UIC_GAMEMODE);
};

void(float i, string via) GameMode_Pick =
{
	local string why;

	if (i < 1 || i > GM_N)
		return;
	why = GameMode_Why();
	if (why != "")
	{
		gm_note = why;
		gm_note_t = cltime;
		print(sprintf("hud_gamemode: %s\n", why));
		return;
	}
	if (i == GameMode_Current())
	{
		print(sprintf("hud_gamemode: already %s\n", GameMode_Name(i)));
		GameMode_Close();
		return;
	}
	if (!movementprofile_switch(GameMode_Sel(i)))
	{
		gm_note = "The engine refused the switch (see the console).";
		gm_note_t = cltime;
		return;
	}
	print(sprintf("hud_gamemode: %s (%s), reloading the map\n", GameMode_Name(i), via));
	GameMode_Close();
};

void() GameMode_RegisterCvars =
{
	registercvar("hud_gamemode_x", "0.36", CVAR_ARCHIVE);
	registercvar("hud_gamemode_y", "0.24", CVAR_ARCHIVE);
	registercommand("hud_gamemode");
};

/*
  `hud_gamemode`           toggle the picker
  `hud_gamemode open|close`
  `hud_gamemode <1-7>`     pick, as the key does
  `hud_gamemode status`    one line: the running mode and whether a pick can act
*/
float() GameMode_Console =
{
	local string a;
	local float c;

	if (argv(0) != "hud_gamemode")
		return FALSE;
	a = argv(1);
	// Opening, picking and the pointer hook answer the player's own console and binds only: a server's
	// bind could open the panel under the digit the player presses next (review).
	if (a != "status" && a != "close")
	if (checkbuiltin(cmdlevel_local))      // nested: QC evaluates both sides of &&
	if (!cmdlevel_local())
	{
		print("hud_gamemode: only from your own console or binds\n");
		return TRUE;
	}
	if (a == "status")
	{
		c = GameMode_Current();
		print(sprintf("hud_gamemode: open %g mode %g %s why \"%s\"\n", ui_gm_open, c,
		              c ? GameMode_Sel(c) : serverkey("*movementprofile"), GameMode_Why()));
		if (ui_gm_open)
			print(sprintf("hud_gamemode: rows x %g w %g y %g pitch %g\n", gm_rowx, gm_roww, gm_rowy, gm_rowh));
	}
	else if (a == "mouse")          // harness: move this panel's pointer (a click is `vote key 512`)
	{
		if (ui_gm_open)
		{
			gm_mx = stof(argv(2)); gm_my = stof(argv(3));
			sui_input_event(IE_MOUSEABS, gm_mx, gm_my, 0);
		}
	}
	else if (a == "open")
		GameMode_Open();
	else if (a == "close")
		GameMode_Close();
	else if (a != "")
	{
		c = stof(a);
		if (c != floor(c) || c < 1 || c > GM_N)
			print(sprintf("hud_gamemode: pick 1-%g\n", GM_N));
		else
			GameMode_Pick(c, "console");
	}
	else if (ui_gm_open)
		GameMode_Close();
	else
		GameMode_Open();
	return TRUE;
};

float(float evtype, float scanx, float chary, float devid) GameMode_Input =
{
	local float b;

	// A pick closes the panel on the press; SaveLoc must not then act on its repeats or its release.
	if ((evtype == IE_KEYDOWN || evtype == IE_KEYUP) && scanx >= '1' && scanx < '1' + GM_N)
	{
		b = bitshift(1, scanx - '1');
		if (gm_kmine & b)
		{
			if (evtype == IE_KEYUP)
				gm_kmine = gm_kmine - b;
			return TRUE;
		}
	}
	if (!ui_gm_open || sc_held)
		return FALSE;
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE)
	{
		GameMode_Close();
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx >= '1' && scanx < '1' + GM_N)
	{
		// Vote_Track (first in the chain) marks repeats: ours stay ours, a key held from before is its owner's.
		if (vt_krep)
			return FALSE;
		gm_kmine = gm_kmine | bitshift(1, scanx - '1');
		GameMode_Pick(scanx - '0', "key");
		return TRUE;
	}
	if (evtype == IE_MOUSEABS)
	{
		gm_mx = scanx; gm_my = chary;
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE1)
	{
		if (evtype == IE_KEYUP && gm_drag)
		{
			gm_drag = FALSE;
			return TRUE;
		}
		// A row picks on the press, inside this event: the builtin answers only a device press or the
		// player's own console (a click resolved later in the draw would be neither).
		if (evtype == IE_KEYDOWN && gm_rowh > 0)
		if (gm_mx >= gm_rowx && gm_mx < gm_rowx + gm_roww && gm_my >= gm_rowy && gm_my < gm_rowy + GM_N * gm_rowh)
		if (gm_my - gm_rowy - gm_rowh * floor((gm_my - gm_rowy) / gm_rowh) < gm_rowbh)
		{
			GameMode_Pick(1 + floor((gm_my - gm_rowy) / gm_rowh), "click");
			return TRUE;
		}
		if (evtype == IE_KEYDOWN)
		if (gm_mx >= gm_pos_x && gm_mx < gm_pos_x + gm_size_x - gm_titleh * 1.2)
		if (gm_my >= gm_pos_y && gm_my < gm_pos_y + gm_titleh)
		{
			gm_drag = TRUE;
			gm_off = [gm_mx, gm_my, 0] - gm_pos;
			return TRUE;
		}
	}
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN)
			_sui_mouse_move(_cursor_position, FALSE);
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MWHEELUP || scanx == K_MWHEELDOWN)
	if (gm_mx >= gm_pos_x && gm_mx < gm_pos_x + gm_size_x && gm_my >= gm_pos_y && gm_my < gm_pos_y + gm_size_y)
		return TRUE;
	return FALSE;
};

void(vector scr) GameMode_Draw =
{
	local float sc, tsz, ttl, hint, pad, rh, cap, i, cur, live, hot, kw, w;
	local vector pos, size, at, rs;
	local string id, why, foot;

	if (!ui_gm_open)
		return;
	if (GameMode_OthersHeld())
	{
		GameMode_Close();
		return;
	}
	if (sc_held || ui_gfx_open)
		return;                         // those brackets own the frame's clicks

	Font_Set(ui_font_ui);
	sc = max(0.5, ui_cv_scale);
	tsz = Font_Px(8 * sc); ttl = Font_Px(11 * sc); hint = Font_Px(6.5 * sc);
	pad = tsz;
	rh = ceil(tsz * 2.6);
	cap = rh - ceil(tsz * 0.8);
	w = tsz * 34;
	gm_titleh = pad * 0.8 + ttl + hint * 1.5 + pad * 0.5;
	size = [w, gm_titleh + GM_N * rh + pad * 0.5 + hint * 2.6 + pad, 0];

	pos = [cvar("hud_gamemode_x") * scr_x, cvar("hud_gamemode_y") * scr_y, 0];
	if (gm_drag)
		pos = [gm_mx, gm_my, 0] - gm_off;
	pos_x = bound(4, pos_x, max(4, scr_x - size_x - 4));
	pos_y = bound(4, pos_y, max(4, scr_y - size_y - 4));
	if (gm_drag)
	{
		cvar_set("hud_gamemode_x", ftos(pos_x / scr_x));
		cvar_set("hud_gamemode_y", ftos(pos_y / scr_y));
	}
	gm_pos = pos; gm_size = size;

	why = GameMode_Why();
	live = (why == "");
	cur = GameMode_Current();

	sui_begin(scr_x, scr_y);
	sui_style_panel(pos, size, ceil(pad * 0.75), 0.97);
	sui_text(pos + [pad, pad * 0.8, 0], [ttl, ttl], "Movement mode", SUI_THEME_TEXT, 1, 0);
	sui_text(pos + [pad, pad * 0.8 + ttl + hint * 0.4, 0], [hint, hint],
	         "Click one or press its number.  Drag here to move.", SUI_THEME_MUTED, 1, 0);
	if (Gfx_Chip("gm_close", pos + [size_x - pad - cap, pad * 0.7, 0], [cap, cap, 0], cap * 0.5, "X", tsz, FALSE, TRUE))
	{
		GameMode_Close(); sui_end(); Font_Reset(); return;
	}
	sui_tooltip_for("gm_close", "Close (Esc, or hud_gamemode again).", sc);
	drawfill(pos + [pad * 0.5, gm_titleh - pad * 0.4, 0], [size_x - pad, 1, 0], SUI_THEME_EDGE_HI, 0.6, 0);

	at = pos + [pad * 0.5, gm_titleh, 0];
	rs = [size_x - pad, rh - ceil(tsz * 0.3), 0];
	gm_rowx = at_x; gm_roww = rs_x; gm_rowy = at_y; gm_rowh = rh; gm_rowbh = rs_y;
	for (i = 1; i <= GM_N; i = i + 1)
	{
		id = sprintf("gm_row%g", i);
		sui_action_element(at, rs, id, sui_noop);
		hot = live && sui_is_hovered(id);
		if (i == cur)
			sui_roundbox(at, rs, ceil(tsz * 0.35), SUI_THEME_SELECTED, 1);
		else if (hot)
			sui_style_box(at, rs, ceil(tsz * 0.35), SUI_THEME_HOVER, SUI_THEME_EDGE_HI, 1);
		// keycap, name, blurb
		sui_roundbox(at + [tsz * 0.4, (rs_y - cap) * 0.5, 0], [cap, cap, 0], ceil(tsz * 0.25),
		             (i == cur) ? SUI_THEME_ACCENT : SUI_THEME_CHIP, live ? 1 : 0.5);
		kw = stringwidth(ftos(i), TRUE, [tsz, tsz]);
		sui_text(at + [tsz * 0.4 + (cap - kw) * 0.5, (rs_y - tsz) * 0.5, 0], [tsz, tsz], ftos(i),
		         (i == cur) ? SUI_THEME_WELL : SUI_THEME_DIM, live ? 1 : 0.5, 0);
		sui_text(at + [tsz * 0.9 + cap, rs_y * 0.5 - tsz * 0.95, 0], [tsz, tsz], GameMode_Name(i),
		         (i == cur || hot) ? SUI_THEME_TEXT : SUI_THEME_DIM, (live || i == cur) ? 1 : 0.6, 0);
		sui_text(at + [tsz * 0.9 + cap, rs_y * 0.5 + tsz * 0.1, 0], [hint, hint], GameMode_Blurb(i),
		         SUI_THEME_MUTED, (live || i == cur) ? 1 : 0.6, 0);
		if (i == cur)
			sui_text(at + [rs_x - tsz * 0.5 - stringwidth("current", TRUE, [hint, hint]), (rs_y - hint) * 0.5, 0],
			         [hint, hint], "current", SUI_THEME_ACCENT, 1, 0);
		at_y = at_y + rh;
	}

	if (gm_note != "" && cltime - gm_note_t < 4)
		foot = gm_note;
	else if (!live)
		foot = why;
	else
		foot = "Reloads the map.  Unranked: times in these modes are not recorded yet.";
	sui_text(pos + [pad, size_y - pad - hint * 1.6, 0], [hint, hint], foot,
	         (!live || gm_note != "") ? SUI_THEME_WARN : SUI_THEME_MUTED, 1, 0);

	sui_end();
	Font_Reset();
};
