/*
===========================================================================
  cl_keycfg.qc -- Patch 762: the key configuration panel (`config_menu`) and
  the key hints along the bottom left of the HUD.

  Every key row is an engine bind, read with findkeysforcommandex and written
  with setkeybind on all modifier states. CSQC binds carry the insecure level,
  so cfg_save writes `bindlevel <key> 30 "<command>"`; every command in the
  table runs at that level. A key an action gives up is bound to "", not
  unbound: an unbound key is not written to ftesurf.cfg, so default.cfg's own
  bind would come back on the next launch.

      config_menu                       toggle
      config_menu status                every row, its command and its keys
      config_menu bind <id> <key> [s]   what a press in slot s (0/1) does
      config_menu clear <id> [s]        what a right-click on slot s does
      config_menu capture <id> [s]      open and wait for a key, as a click does
      config_menu reset                 every row back to default.cfg's keys
      config_menu yaw|sens <v>          the two sliders
      config_menu hint                  the bottom-left strip as drawn
===========================================================================
*/

#define KC_N        26

// FTE names it; #630 in the engine table. checkbuiltin-gated in KC_SetBind.
void(float keynum, string bindcmd, optional float bindmap, optional float modifier) setkeybind = #0:setkeybind;
#define KC_STATUS_T 4           // seconds a bind's result stays on the status line

// id|label|command a rebind writes|other bindings that count as this row (;)|default.cfg's keys|group
// Restart/Respawn ship as `say !r`/`say !m` (default.cfg).  Restart is rebound as
// the same warp under its command name (cl_warpop.qc); Respawn as `say !m` itself,
// since goto_spawn is the map's spawn entity (Patch 845).
string(float i) KC_Def =
{
	if (i == 0)  return "forward|Forward|+forward||w|Movement";
	if (i == 1)  return "back|Back|+back||s|Movement";
	if (i == 2)  return "left|Strafe left|+moveleft||a|Movement";
	if (i == 3)  return "right|Strafe right|+moveright||d|Movement";
	if (i == 4)  return "jump|Jump|+jump||SPACE MWHEELUP MWHEELDOWN MOUSE2|Movement";
	if (i == 5)  return "duck|Duck|+duck||LCTRL MOUSE1|Movement";
	if (i == 6)  return "walk|Walk|+speed||LSHIFT|Movement";
	if (i == 7)  return "turnleft|Turn left|+left||e|Movement";
	if (i == 8)  return "turnright|Turn right|+right||q|Movement";
	if (i == 9)  return "hud|HUD editor|hud_edit||c|Menus";
	if (i == 10) return "gfx|Graphics|gfx_menu||x|Menus";
	if (i == 11) return "keys|Key config|config_menu||k|Menus";
	if (i == 12) return "player|Player|hud_player||p|Menus";   // Patch 806
	if (i == 13) return "entview|Entity view|ent_cursor|ent_view|MOUSE3|Menus";   // Patch 809
	if (i == 14) return "savemenu|Save menu|save_menu|saveloc_menu;mom_saveloc_close|z|Saves";
	if (i == 15) return "save|Save|sl_save|mom_saveloc_create|1|Saves";
	if (i == 16) return "load|Load (hold)|+sl_hold|sl_load;+mom_saveloc_current;mom_saveloc_current|2|Saves";
	if (i == 17) return "delete|Delete|sl_del|mom_saveloc_remove_current|4|Saves";
	if (i == 18) return "prev|Previous save|sl_prev|mom_saveloc_nav_prev||Saves";
	if (i == 19) return "next|Next save|sl_next|mom_saveloc_nav_next||Saves";
	if (i == 20) return "restart|Restart|goto_start|say !r|r|Run";
	if (i == 21) return "respawn|Respawn|say !m||m|Run";
	if (i == 22) return "rewind|Rewind|rewind||BACKSPACE|Run";
	if (i == 23) return "noclip|Noclip|noclip||v|Run";
	if (i == 24) return "paint|Paint (hold)|+paint|paint||Run";     // Patch 772: unbound by default
	if (i == 25) return "share|Share (look at a player)|share||f|Run";  // Patch 777
	return "";
};

string(float i, float f) KC_F = { return Gfx_Field(KC_Def(i), f, "|"); };

// The strip's items: rows of the table above, in the order asked for.
float(float n) KC_HintRow =
{
	if (n == 0) return 14;      // save menu
	if (n == 1) return 10;      // graphics
	if (n == 2) return 9;       // hud editor
	if (n == 3) return 12;      // player
	if (n == 4) return 23;      // noclip
	if (n == 5) return 22;      // rewind
	if (n == 6) return 11;      // key config
	return -1;
};
#define KC_HINTS 7

string(float n) KC_HintLabel =
{
	if (n == 0) return "Saves";
	if (n == 1) return "Graphics";
	if (n == 2) return "HUD";
	if (n == 3) return "Player";
	if (n == 4) return "Noclip";
	if (n == 5) return "Rewind";
	return "Keys";
};

float  kc_open;
float  kc_dirty;                // a bind or a slider changed: cfg_save on close
float  kc_cap_i, kc_cap_s;      // the slot waiting for a key; -1 none
float  kc_eatkey;               // the key a capture took: its repeats and release too
float  kc_hov_i, kc_hov_s;      // the chip under the pointer at the last draw
float  kc_hov_slider;           // 1 yaw, 2 sensitivity, 0 none
float  kc_armed, kc_armat;      // `reset keys` asks twice
string kc_status;
float  kc_statusat;
string kc_keys[KC_N];           // each row's keys, space-separated engine names
float  kc_cnt[KC_N];
float  kc_cacheat;              // cltime of the last read; 0 = read now
string kc_hint;                 // "KEY|label;KEY|label;..." for the strip

void() KC_Register =
{
	registercommand("config_menu");
	registercvar("hud_keyhint",   "1",      CVAR_ARCHIVE);
	registercvar("hud_keyhint_x", "0.0333", CVAR_ARCHIVE);
	registercvar("hud_keyhint_y", "0.955",  CVAR_ARCHIVE);
	kc_cap_i = -1;
	kc_eatkey = -1;
	kc_hov_i = -1;
};

void(string s) KC_Say =
{
	if (kc_status != "")
		strunzone(kc_status);
	kc_status = strzone(s);
	kc_statusat = cltime;
	print(strcat("^5config_menu^7: ", s, "\n"));
};

// The engine's key name as a person would write it on a keycap.
string(string k) KC_KeyLabel =
{
	if (k == "")
		return "";
	if (strlen(k) == 1)
		return strtoupper(k);
	if (k == "BACKSPACE")  return "Bksp";
	if (k == "SPACE")      return "Space";
	if (k == "LCTRL" || k == "CTRL")   return "Ctrl";
	if (k == "RCTRL")      return "RCtrl";
	if (k == "LSHIFT" || k == "SHIFT") return "Shift";
	if (k == "RSHIFT")     return "RShift";
	if (k == "LALT" || k == "ALT")     return "Alt";
	if (k == "RALT")       return "RAlt";
	if (k == "MWHEELUP")   return "Wheel up";
	if (k == "MWHEELDOWN") return "Wheel dn";
	if (k == "UPARROW")    return "Up";
	if (k == "DOWNARROW")  return "Down";
	if (k == "LEFTARROW")  return "Left";
	if (k == "RIGHTARROW") return "Right";
	if (k == "CAPSLOCK")   return "Caps";
	if (k == "BACKSLASH")  return "\\";
	if (k == "SEMICOLON")  return ";";
	if (k == "ENTER")      return "Enter";
	if (k == "TAB")        return "Tab";
	if (k == "PGUP")       return "PgUp";
	if (k == "PGDN")       return "PgDn";
	if (substring(k, 0, 5) == "MOUSE")
		return strcat("Mouse ", substring(k, 5, -1));
	if (substring(k, 0, 3) == "KP_")
		return strcat("Num ", substring(k, 3, -1));
	return strcat(substring(k, 0, 1), strtolower(substring(k, 1, -1)));
};

// Every key whose bind is the row's command or one of its other spellings.
string(float i) KC_Find =
{
	local float j;
	local string s, alts, a, k;

	s = findkeysforcommandex(KC_F(i, 2));
	alts = KC_F(i, 3);
	for (j = 0; j < 8; j = j + 1)
	{
		a = Gfx_Field(alts, j, ";");
		if (a == "")
			break;
		k = findkeysforcommandex(a);
		if (k != "")
			s = (s == "") ? k : strcat(s, " ", k);
	}
	return s;
};

float(string s) KC_Count =
{
	local float n;
	if (s == "")
		return 0;
	for (n = 1; n < 16; n = n + 1)
		if (Gfx_Field(s, n, " ") == "")
			break;
	return n;
};

void() KC_Refresh =
{
	local float i, n, r;
	local string s, h;

	for (i = 0; i < KC_N; i = i + 1)
	{
		s = KC_Find(i);
		if (strcmp(s, kc_keys[i]))
		{
			if (kc_keys[i] != "")
				strunzone(kc_keys[i]);
			kc_keys[i] = (s == "") ? "" : strzone(s);
		}
		kc_cnt[i] = KC_Count(kc_keys[i]);
	}

	h = "";
	for (n = 0; n < KC_HINTS; n = n + 1)
	{
		r = KC_HintRow(n);
		if (!kc_cnt[r])
			continue;               // unbound: nothing to point at
		s = strcat(KC_KeyLabel(Gfx_Field(kc_keys[r], 0, " ")), "|", KC_HintLabel(n));
		h = (h == "") ? s : strcat(h, ";", s);
	}
	if (strcmp(h, kc_hint))
	{
		if (kc_hint != "")
			strunzone(kc_hint);
		kc_hint = (h == "") ? "" : strzone(h);
	}
	kc_cacheat = cltime;
};

// A bind changed: read the table again now, not at the next half second.
void() KC_Changed = { kc_dirty = TRUE; kc_cacheat = 0; KC_Refresh(); };

void(float scan, string b) KC_SetBind =
{
	if (checkbuiltin(setkeybind))
		setkeybind(scan, b);
	else
		localcmd(sprintf("bind %s \"%s\"\n", keynumtostring(scan), b));
};

// The row a binding belongs to, the way findkeysforcommandex matches it.
float(string b, string c) KC_Matches =
{
	local float l;
	local string t;
	if (c == "")
		return FALSE;
	l = strlen(c);
	if (strcmp(substring(b, 0, l), c))
		return FALSE;
	t = substring(b, l, 1);
	return (t == "" || t == " " || t == ";");
};

float(string b) KC_RowOf =
{
	local float i, j;
	local string alts, a;

	if (b == "")
		return -1;
	for (i = 0; i < KC_N; i = i + 1)
	{
		if (KC_Matches(b, KC_F(i, 2)))
			return i;
		alts = KC_F(i, 3);
		for (j = 0; j < 8; j = j + 1)
		{
			a = Gfx_Field(alts, j, ";");
			if (a == "")
				break;
			if (KC_Matches(b, a))
				return i;
		}
	}
	return -1;
};

// The open save panel takes these digits first (SaveLoc_Key); its own key is let through.
string(float scan) KC_PanelDigit =
{
	if (scan == '1') return "Create save";
	if (scan == '2') return "Load save";
	if (scan == '3') return "Go to next";
	if (scan == '4') return "Go to previous";
	if (scan == '5') return "Go to first";
	if (scan == '6') return "Go to last";
	if (scan == '7') return "Remove save";
	if (scan == '8') return "Delete all";
	if (scan == '0') return "Close menu";
	return "";
};

// Key `scan` now does row i, in place of whatever slot s held.
void(float i, float s, float scan) KC_Assign =
{
	local string old, was, kn;
	local float ok, other;

	if (i < 0 || i >= KC_N || scan <= 0)
		return;
	kn = keynumtostring(scan);
	if (kn == "")
		return;
	was = getkeybind(scan);
	other = KC_RowOf(was);
	old = Gfx_Field(kc_keys[i], s, " ");
	if (old != "")
	{
		ok = stringtokeynum(old);
		if (ok > 0 && ok != scan)
			KC_SetBind(ok, "");
	}
	KC_SetBind(scan, KC_F(i, 2));
	if (other >= 0 && other != i)
		kn = sprintf("%s: %s (was %s)", KC_KeyLabel(kn), KC_F(i, 1), KC_F(other, 1));
	else if (was != "" && other != i)
		kn = sprintf("%s: %s (was \"%s\")", KC_KeyLabel(kn), KC_F(i, 1), was);
	else
		kn = sprintf("%s: %s", KC_KeyLabel(kn), KC_F(i, 1));
	was = KC_PanelDigit(scan);
	if (was != "" && strcmp(KC_F(i, 0), "savemenu"))
		kn = strcat(kn, "; with the save menu open it is ", was);
	KC_Say(kn);
	KC_Changed();
};

void(float i, float s) KC_Clear =
{
	local string old;
	local float ok;

	old = Gfx_Field(kc_keys[i], s, " ");
	if (old == "")
		return;
	ok = stringtokeynum(old);
	if (ok <= 0)
		return;
	KC_SetBind(ok, "");
	KC_Say(sprintf("%s cleared from %s", KC_KeyLabel(old), KC_F(i, 1)));
	KC_Changed();
};

void() KC_Reset =
{
	local float i, j, k;
	local string d;

	KC_Refresh();
	for (i = 0; i < KC_N; i = i + 1)
		for (j = 0; j < kc_cnt[i]; j = j + 1)
		{
			k = stringtokeynum(Gfx_Field(kc_keys[i], j, " "));
			if (k > 0)
				KC_SetBind(k, "");
		}
	for (i = 0; i < KC_N; i = i + 1)
	{
		d = KC_F(i, 4);
		for (j = 0; j < 8; j = j + 1)
		{
			k = stringtokeynum(Gfx_Field(d, j, " "));
			if (k <= 0)
				break;
			KC_SetBind(k, KC_F(i, 2));
		}
	}
	KC_Say("every key back to its default");
	KC_Changed();
};

// cl_yawspeed is not archived by the engine; seta archives it (cl_gfx.qc's Gfx_Cycle note).
void(float v) KC_SetYaw =
{
	v = bound(0, floor(v / 5 + 0.5) * 5, 1000);
	if (v == cvar("cl_yawspeed"))
		return;
	localcmd(sprintf("seta cl_yawspeed %g\n", v));
	kc_dirty = TRUE;
};

void(float v) KC_SetSens =
{
	v = bound(0.01, floor(v * 100 + 0.5) / 100, 20);
	if (v == cvar("sensitivity"))
		return;
	localcmd(sprintf("seta sensitivity %g\n", v));
	kc_dirty = TRUE;
};

// The sliders' travel: yaw linear 0..600, sensitivity logarithmic 0.05..10.
#define KC_SENS_LO 0.05
#define KC_SENS_HI 10
float(float v) KC_SensT = { return bound(0, log(max(v, KC_SENS_LO) / KC_SENS_LO) / log(KC_SENS_HI / KC_SENS_LO), 1); };
float(float t) KC_SensV = { return KC_SENS_LO * pow(KC_SENS_HI / KC_SENS_LO, t); };

void() KC_Close =
{
	if (!kc_open)
		return;
	kc_open = FALSE;
	kc_cap_i = -1;
	kc_armed = FALSE;
	sui_tooltip_reset();
	sui_reset_actions();            // a slider held through ESC would drag on the next open
	UI_CursorRelease(UIC_KEYCFG);
	if (kc_dirty)
	{
		kc_dirty = FALSE;
		localcmd("cfg_save\n");
		print("^5config_menu^7: keys saved to ftesurf.cfg\n");
	}
};

void() KC_Open =
{
	if (kc_open)
		return;
	if (rec_sb_open || rec_wt_open)
	{
		print("^3config_menu^7: close the scoreboard or the replay first\n");
		return;
	}
	if (ui_he_open)
		HUD_EditClose();
	if (UI_CursorHeld())
	{
		print("^3config_menu^7: another panel has the mouse -- close it first\n");
		return;
	}
	kc_open = TRUE;
	kc_cap_i = -1;
	kc_eatkey = -1;
	kc_armed = FALSE;
	kc_hov_i = -1;
	kc_hov_slider = 0;
	sui_reset_actions();
	KC_Refresh();
	UI_CursorClaim(UIC_KEYCFG);
};

float(string id) KC_RowId =
{
	local float i;
	for (i = 0; i < KC_N; i = i + 1)
		if (!strcmp(KC_F(i, 0), id))
			return i;
	return -1;
};

float() KC_Console =
{
	local string a;
	local float i, s, k;

	a = argv(1);
	if (a == "")
	{
		if (kc_open)
			KC_Close();
		else
			KC_Open();
		return TRUE;
	}
	if (a == "status")
	{
		KC_Refresh();
		print(sprintf("config_menu: open %g capture %g/%g savepanel %g hold %g/%g ",
		              kc_open, kc_cap_i, kc_cap_s, rec_sl_open, rec_sl_holding, rec_sl_holdkey));
		print(sprintf("yawspeed %g sensitivity %g\n", cvar("cl_yawspeed"), cvar("sensitivity")));
		for (i = 0; i < KC_N; i = i + 1)
			print(sprintf("config_menu: %-9s %-14s %-11s keys [%s]\n",
			              KC_F(i, 0), KC_F(i, 1), KC_F(i, 2), kc_keys[i]));
		return TRUE;
	}
	if (a == "hint")
	{
		KC_Refresh();
		print(sprintf("config_menu: hint [%s] shown %g\n", kc_hint, cvar("hud_keyhint")));
		return TRUE;
	}
	if (a == "reset")
	{
		KC_Reset();
		return TRUE;
	}
	if (a == "yaw")  { KC_SetYaw(stof(argv(2)));  return TRUE; }
	if (a == "sens") { KC_SetSens(stof(argv(2))); return TRUE; }

	i = KC_RowId(argv(2));
	if (i < 0)
	{
		print("config_menu [status | hint | reset | yaw <v> | sens <v> |\n"
		      "             bind <id> <key> [slot] | clear <id> [slot] | capture <id> [slot]]\n");
		return TRUE;
	}
	KC_Refresh();
	if (a == "bind")
	{
		s = bound(0, stof(argv(4)), 1);
		k = stringtokeynum(argv(3));
		if (k <= 0)
			print(sprintf("config_menu: no key called %s\n", argv(3)));
		else
			KC_Assign(i, s, k);
		return TRUE;
	}
	if (a == "clear")
	{
		KC_Clear(i, bound(0, stof(argv(3)), 1));
		return TRUE;
	}
	if (a == "capture")
	{
		KC_Open();
		if (kc_open)
		{
			kc_cap_i = i;
			kc_cap_s = bound(0, stof(argv(3)), 1);
			print(sprintf("config_menu: waiting for a key for %s\n", KC_F(i, 0)));
		}
		return TRUE;
	}
	return TRUE;
};

/*
  Input. A capture comes first in CL_InputChain, ahead of the chat draft's steal
  of messagemode keys, so any key can be taken; the rest follows hud_edit's
  manners: MOUSE1 and MOUSE2 are the panel's, ESC closes, other keys keep their
  binds (the key bound to config_menu closes it that way).
*/
float(float evtype, float scanx, float chary, float devid) KC_CaptureEvent =
{
	if (!kc_open)
		return FALSE;
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP)
		return FALSE;
	if (kc_eatkey >= 0 && scanx == kc_eatkey)
	{
		if (evtype == IE_KEYUP)
			kc_eatkey = -1;
		return TRUE;
	}
	if (kc_cap_i < 0 || evtype != IE_KEYDOWN || chat_rep)
		return FALSE;               // a key held from before keeps its repeats and release
	kc_eatkey = scanx;
	// A click binds Mouse 1 only on the waiting chip; anywhere else it cancels.
	if (scanx == K_ESCAPE || (scanx == K_MOUSE1 && (kc_hov_i != kc_cap_i || kc_hov_s != kc_cap_s)))
		KC_Say("cancelled");
	else
		KC_Assign(kc_cap_i, kc_cap_s, scanx);
	kc_cap_i = -1;
	return TRUE;
};

float(float evtype, float scanx, float chary, float devid) KC_InputEvent =
{
	local float step;

	if (!kc_open)
		return FALSE;
	if (evtype == IE_MOUSEABS)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP)
		return FALSE;

	if (scanx == K_MOUSE1)
	{
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN && kc_hov_i >= 0)
			KC_Clear(kc_hov_i, kc_hov_s);
		return TRUE;
	}
	if (scanx == K_MWHEELUP || scanx == K_MWHEELDOWN)
	{
		if (evtype == IE_KEYDOWN)
		{
			step = (scanx == K_MWHEELUP) ? 1 : -1;
			if (kc_hov_slider == 1)
				KC_SetYaw(cvar("cl_yawspeed") + step * 5);
			else if (kc_hov_slider == 2)
				KC_SetSens(cvar("sensitivity") + step * 0.01);
		}
		return TRUE;
	}
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE)
	{
		KC_Close();
		return TRUE;
	}
	return FALSE;
};

/*
===========================================================================
  Drawing
===========================================================================
*/
float(string s, float want) KC_TextW =
{
	local float w, legacy;
	legacy = drawfont;
	drawfont = Font_NativeSlot(legacy);
	w = stringwidth(s, TRUE, sui_native_text_size(want));
	drawfont = legacy;
	return w;
};

// A flat button in hud_edit's chip style. TRUE on the frame it is released.
float(string id, vector pos, vector sz, string label, vector fill, vector fg, float sc) KC_Button =
{
	local float hot;
	local vector glyph;

	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	if (sui_is_held(id))
		fill = SUI_THEME_PRESSED;
	else if (hot)
		fill = SUI_THEME_HOVER;
	if (hot)
		sui_style_box(pos, sz, 3 * sc, fill, SUI_THEME_EDGE_HI, 1);
	else
		sui_roundbox(pos, sz, 3 * sc, fill, 1);
	glyph = sui_native_text_size(8 * sc);
	sui_native_text([pos_x + (sz_x - KC_TextW(label, 8 * sc)) * 0.5, pos_y + (sz_y - glyph_y) * 0.5, 0],
	                label, 8 * sc, hot ? SUI_THEME_TEXT : fg, 1);
	return sui_is_released(id);
};

// One key slot of row i.
void(float i, float s, vector pos, vector sz, float sc) KC_Chip =
{
	local string id, k, lab;
	local float hot, cap;
	local vector fill, fg, glyph;

	id = sprintf("kc_k%g_%g", i, s);
	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	cap = (kc_cap_i == i && kc_cap_s == s);
	k = Gfx_Field(kc_keys[i], s, " ");
	if (hot)
	{
		kc_hov_i = i;
		kc_hov_s = s;
	}

	fill = SUI_THEME_CHIP;
	fg = SUI_THEME_TEXT;
	lab = KC_KeyLabel(k);
	if (k == "")
	{
		fill = SUI_THEME_WELL;
		fg = SUI_THEME_MUTED;
		lab = "-";
	}
	if (cap)
	{
		sui_style_box(pos, sz, 3 * sc, SUI_THEME_SELECTED, SUI_THEME_FOCUS, 1);
		lab = "press";
		fg = SUI_THEME_FOCUS;
	}
	else if (sui_is_held(id))
		sui_roundbox(pos, sz, 3 * sc, SUI_THEME_PRESSED, 1);
	else if (hot)
		sui_style_box(pos, sz, 3 * sc, SUI_THEME_HOVER, SUI_THEME_EDGE_HI, 1);
	else
		sui_roundbox(pos, sz, 3 * sc, fill, 1);

	glyph = sui_native_text_size(8 * sc);
	sui_native_text([pos_x + (sz_x - KC_TextW(lab, 8 * sc)) * 0.5, pos_y + (sz_y - glyph_y) * 0.5, 0],
	                lab, 8 * sc, fg, cap ? 0.6 + 0.4 * fabs(sin(cltime * 5)) : 1);
	if (k != "" && !cap)
		sui_tooltip_for(id, "Click, then press a key. Right-click clears.", sc);

	if (sui_is_released(id))
	{
		kc_cap_i = i;
		kc_cap_s = s;
		kc_armed = FALSE;
	}
};

// A group heading: accent text over a hairline.
void(vector pos, float w, string title, float sc) KC_Heading =
{
	local vector glyph;
	glyph = sui_native_text_size(7 * sc);
	sui_native_text([pos_x, pos_y + 9 * sc - glyph_y, 0], title, 7 * sc, SUI_THEME_ACCENT, 1);
	sui_fill([pos_x, pos_y + 11 * sc, 0], [w, 1, 0], SUI_THEME_EDGE_HI, 0.7, 0);
};

// A slider row: label, -, track, +, value. which: 1 yaw, 2 sensitivity.
void(float which, vector pos, float labw, float w, float rh, float sc) KC_Slider =
{
	local string id, val, lab;
	local float t, tw, bw, valw, v, hot;
	local vector tp, ts, glyph;

	glyph = sui_native_text_size(8 * sc);
	bw = 10 * sc;
	valw = 24 * sc;
	if (which == 1)
	{
		lab = "Turn speed";
		v = cvar("cl_yawspeed");
		t = bound(0, v / 600, 1);
		val = sprintf("%g", v);
	}
	else
	{
		lab = "Sensitivity";
		v = cvar("sensitivity");
		t = KC_SensT(v);
		val = sprintf("%.2f", v);
	}
	sui_native_text([pos_x, pos_y + (rh - glyph_y) * 0.5, 0], lab, 8 * sc, SUI_THEME_DIM, 1);

	id = sprintf("kc_sl%g", which);
	tp = [pos_x + labw + bw + 3 * sc, pos_y + sc, 0];
	tw = w - labw - 2 * bw - 6 * sc - valw - 3 * sc;
	ts = [tw, rh - 2 * sc, 0];
	sui_action_element(tp, ts, id, sui_noop);
	hot = (sui_is_hovered(id) || sui_is_held(id));
	if (hot)
		kc_hov_slider = which;
	if (sui_is_held(id))
	{
		t = bound(0, (_cursor_position_x - tp_x) / tw, 1);
		if (which == 1)
			KC_SetYaw(t * 600);
		else
			KC_SetSens(KC_SensV(t));
	}
	sui_style_box([tp_x, tp_y + ts_y * 0.5 - 2 * sc, 0], [tw, 4 * sc, 0], 2 * sc,
	              SUI_THEME_WELL, hot ? SUI_THEME_EDGE_HI : SUI_THEME_EDGE, 1);
	if (t > 0)
		sui_roundbox([tp_x, tp_y + ts_y * 0.5 - 2 * sc, 0], [max(4 * sc, tw * t), 4 * sc, 0], 2 * sc,
		             SUI_THEME_ACCENT, hot ? 1 : 0.75);
	sui_roundbox([tp_x + tw * t - 3 * sc, tp_y + ts_y * 0.5 - 4 * sc, 0], [6 * sc, 8 * sc, 0], 2.5 * sc,
	             hot ? SUI_THEME_TEXT : SUI_THEME_DIM, 1);
	sui_tooltip_for(id, (which == 1)
		? "How fast the turn binds (+left / +right) turn, in degrees a second."
		: "Mouse sensitivity. The wheel nudges it while the pointer is here.", sc);

	if (KC_Button(sprintf("kc_sm%g", which), [pos_x + labw, pos_y + sc, 0], [bw, rh - 2 * sc, 0],
	              "-", SUI_THEME_CHIP, SUI_THEME_DIM, sc))
	{
		if (which == 1) KC_SetYaw(v - 5); else KC_SetSens(v - 0.05);
	}
	if (KC_Button(sprintf("kc_sp%g", which), [tp_x + tw + 3 * sc, pos_y + sc, 0], [bw, rh - 2 * sc, 0],
	              "+", SUI_THEME_CHIP, SUI_THEME_DIM, sc))
	{
		if (which == 1) KC_SetYaw(v + 5); else KC_SetSens(v + 0.05);
	}
	sui_native_text([pos_x + w - KC_TextW(val, 8 * sc), pos_y + (rh - glyph_y) * 0.5, 0],
	                val, 8 * sc, SUI_THEME_WARN, 1);
};

// One key row: label, two slots, and how many more keys it has.
void(float i, vector pos, float labw, float chipw, float rh, float sc) KC_Row =
{
	local vector glyph;
	local float x, more;
	local string id;

	glyph = sui_native_text_size(8 * sc);
	sui_native_text([pos_x, pos_y + (rh - glyph_y) * 0.5, 0], KC_F(i, 1), 8 * sc,
	                (kc_cap_i == i) ? SUI_THEME_TEXT : SUI_THEME_DIM, 1);
	x = pos_x + labw;
	KC_Chip(i, 0, [x, pos_y + sc, 0], [chipw, rh - 2 * sc, 0], sc);
	x = x + chipw + 3 * sc;
	KC_Chip(i, 1, [x, pos_y + sc, 0], [chipw, rh - 2 * sc, 0], sc);
	x = x + chipw + 3 * sc;
	more = kc_cnt[i] - 2;
	if (more > 0)
	{
		id = sprintf("kc_more%g", i);
		sui_action_element([x, pos_y + sc, 0], [12 * sc, rh - 2 * sc, 0], id, sui_noop);
		sui_native_text([x + sc, pos_y + (rh - glyph_y) * 0.5, 0], sprintf("+%g", more), 8 * sc,
		                SUI_THEME_MUTED, 1);
		sui_tooltip_for(id, sprintf("Also on: %s", kc_keys[i]), sc);
	}
};

// Column c's next line: a heading where the group changes, then the row.
float(float i, vector p, float y, float labw, float chipw, float colw, float rh, float sc) KC_ColumnRow =
{
	if (i == 0 || strcmp(KC_F(i, 5), KC_F(i - 1, 5)))
	{
		KC_Heading([p_x, y, 0], colw, KC_F(i, 5), sc);
		y = y + rh;
	}
	KC_Row(i, [p_x, y, 0], labw, chipw, rh, sc);
	return y + rh;
};

void(vector scr) KC_Draw =
{
	local float sc, fit, pad, rh, labw, chipw, colw, gap, panw, panh, y, y0, i, done, bw;
	local vector p, c0, c1;
	local string foot;
	local vector footc;

	if (!kc_open)
		return;
	// A panel that takes the mouse after this opened (the board, a replay, the
	// editor) wins it: one SUI bracket a frame owns the clicks.
	if (rec_sb_open || rec_wt_open || (UI_CursorHeld() - (UI_CursorHeld() & UIC_KEYCFG)))
	{
		KC_Close();
		return;
	}
	if (cltime - kc_cacheat > 0.5)
		KC_Refresh();
	if (kc_armed && cltime - kc_armat > 3)
		kc_armed = FALSE;

	sc = ui_cv_scale;
	if (sc <= 0) sc = 2;
	fit = min(scr_x * 0.96 / 380, scr_y * 0.96 / 288);
	if (sc > fit)
		sc = max(1, floor(fit * 2) / 2);

	pad   = 8 * sc;
	rh    = 13 * sc;
	labw  = 70 * sc;
	chipw = 44 * sc;
	colw  = labw + 2 * chipw + 6 * sc + 12 * sc;
	gap   = 12 * sc;
	panw  = pad * 2 + colw * 2 + gap;
	panh  = 6 * sc + 18 * sc + 17 * rh + 4 * sc + rh + 2 * sc + 4 * sc + 10 * sc + 6 * sc;
	p = [floor((scr_x - panw) * 0.5), floor((scr_y - panh) * 0.5), 0];

	kc_hov_i = -1;
	kc_hov_slider = 0;

	sui_begin(scr_x, scr_y);
	Font_Set(ui_font_ui);
	sui_fill('0 0 0', [scr_x, scr_y, 0], '0 0 0', 0.35, 0);
	sui_action_element(p, [panw, panh, 0], "kc_panel", sui_noop);
	sui_style_panel(p, [panw, panh, 0], 7 * sc, 1);

	y = p_y + 6 * sc;
	sui_native_text([p_x + pad, y, 0], "Key configuration", 10 * sc, SUI_THEME_TEXT, 1);
	sui_native_text([p_x + panw - pad - KC_TextW("Esc closes", 7 * sc), y + 2 * sc, 0],
	                "Esc closes", 7 * sc, SUI_THEME_MUTED, 1);
	y = y + 18 * sc;
	y0 = y;

	// Left column: movement and the menus. Right: saves, the run, turning.
	c0 = [p_x + pad, 0, 0];
	c1 = [p_x + pad + colw + gap, 0, 0];
	for (i = 0; i <= 13; i = i + 1)
		y = KC_ColumnRow(i, c0, y, labw, chipw, colw, rh, sc);
	y = y0;
	for (i = 14; i < KC_N; i = i + 1)
		y = KC_ColumnRow(i, c1, y, labw, chipw, colw, rh, sc);
	KC_Heading([c1_x, y, 0], colw, "Turning and mouse", sc);
	y = y + rh;
	KC_Slider(1, [c1_x, y, 0], labw, colw, rh, sc);
	y = y + rh;
	KC_Slider(2, [c1_x, y, 0], labw, colw, rh, sc);

	y = y0 + 17 * rh + 4 * sc;
	sui_fill([p_x + pad, y - 2 * sc, 0], [panw - pad * 2, 1, 0], SUI_THEME_EDGE_HI, 0.7, 0);
	bw = 64 * sc;
	if (KC_Button("kc_reset", [p_x + pad, y, 0], [bw, rh, 0],
	              kc_armed ? "sure? click again" : "reset keys",
	              kc_armed ? SUI_THEME_BAD_BG : SUI_THEME_CHIP,
	              kc_armed ? SUI_THEME_BAD : SUI_THEME_DIM, sc))
	{
		if (kc_armed)
		{
			kc_armed = FALSE;
			KC_Reset();
		}
		else
		{
			kc_armed = TRUE;
			kc_armat = cltime;
		}
	}
	sui_tooltip_for("kc_reset", "Every key in this panel back to how it shipped. Asks first.", sc);
	done = KC_Button("kc_done", [p_x + panw - pad - bw, y, 0], [bw, rh, 0], "done",
	                 SUI_THEME_SELECTED, SUI_THEME_TEXT, sc);
	y = y + rh + 6 * sc;

	if (kc_cap_i >= 0)
	{
		foot = sprintf("press a key for %s   click it again for Mouse 1   Esc cancels", KC_F(kc_cap_i, 1));
		footc = SUI_THEME_FOCUS;
	}
	else if (kc_status != "" && cltime - kc_statusat < KC_STATUS_T)
	{
		foot = kc_status;
		footc = SUI_THEME_GOOD;
	}
	else
	{
		foot = "click a key to change it   right-click clears it";
		footc = SUI_THEME_MUTED;
	}
	sui_native_text([p_x + pad, y, 0], foot, 7 * sc, footc, 1);

	sui_end();
	Font_Reset();

	// After sui_end, as HUD_EditDraw does: closing inside the bracket would drop
	// the cursor with sui's click-once actions still latched.
	if (done)
		KC_Close();
};

/*
  The strip along the bottom left: the key each menu and gesture is on, read
  from the binds, so it shows the player's own keys. Unbound items are left out.
*/
void(vector scr) KC_HintDraw =
{
	local float sc, n, i, x, h, cap, lsz, kw, lw, w, gap;
	local string it, k, lab;
	local vector p;

	if (!cvar("hud_keyhint") || kc_open || rec_wt_open || rec_wt_on || spc_hud)
		return;
	if (cltime - kc_cacheat > 0.5 || !kc_cacheat)
		KC_Refresh();
	if (kc_hint == "")
		return;

	sc  = ui_cv_scale;
	Font_Set(ui_font_ui);
	lsz = Font_Px(7 * sc);
	h   = 11 * sc;
	cap = h - 3 * sc;
	gap = 6 * sc;
	n = KC_HINTS;

	// Measure first: the card is drawn under the items.
	w = 3 * sc;
	for (i = 0; i < n; i = i + 1)
	{
		it = Gfx_Field(kc_hint, i, ";");
		if (it == "")
			break;
		k = Gfx_Field(it, 0, "|");
		lab = Gfx_Field(it, 1, "|");
		w = w + max(cap, stringwidth(k, TRUE, [lsz, lsz]) + 4 * sc) + 3 * sc
		      + stringwidth(lab, TRUE, [lsz, lsz]) + gap;
	}
	w = w - gap + 4 * sc;

	p = [scr_x * cvar("hud_keyhint_x"), scr_y * cvar("hud_keyhint_y"), 0];
	_sui_round_draw(p, [w, h, 0], 4 * sc, SUI_THEME_PANEL, 0.75);
	x = p_x + 3 * sc;
	for (i = 0; i < n; i = i + 1)
	{
		it = Gfx_Field(kc_hint, i, ";");
		if (it == "")
			break;
		k = Gfx_Field(it, 0, "|");
		lab = Gfx_Field(it, 1, "|");
		kw = max(cap, stringwidth(k, TRUE, [lsz, lsz]) + 4 * sc);
		_sui_round_draw([x, p_y + 1.5 * sc, 0], [kw, cap, 0], 2 * sc, SUI_THEME_CHIP, 1);
		HUD_Text([x + (kw - stringwidth(k, TRUE, [lsz, lsz])) * 0.5, p_y + (h - lsz) * 0.5], k, lsz,
		         SUI_THEME_TEXT, 1);
		x = x + kw + 3 * sc;
		lw = stringwidth(lab, TRUE, [lsz, lsz]);
		HUD_Text([x, p_y + (h - lsz) * 0.5], lab, lsz, SUI_THEME_DIM, 1);
		x = x + lw + gap;
	}
	Font_Reset();
	HUD_Rect("keyhint", p, [w, h, 0], p);
};
