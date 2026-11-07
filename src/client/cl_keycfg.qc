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
      config_menu actions|keyboard      open on that tab (cl_keycfg_tab)
      config_menu place <id> <key>      what a click on a drawn key does with row <id> picked
      config_menu clearkey <key>        what a right-click on a drawn key does
      config_menu layout [caps]         the drawing's caps, names the engine lacks, the strip
      config_menu custom [<command>]    Your own command + Enter: the pick (none: drop it)
      config_menu editkey <key> [<cmd>] Selected key's Edit + Enter (no command: clear)

  Patch 1392, the Keyboard tab: a drawn keyboard and mouse, each cap showing its
  bind. With an action picked, a click puts it on the key (KC_Assign into a new
  slot, so it adds rather than replaces); a right-click binds the key to "".
  Right Shift/Ctrl/Alt, Win and Menu have negative QC key numbers (pr_clcmd.c
  MP_TranslateFTEtoQCCodes); only -1 means "no key" (KC_KeyOk).

  Patch 1400: a typed command can be the pick (Your own command), the Selected
  key box edits or clears a key's whole bind, and Tools and Game rows fill a
  third column on both tabs (KC_Order).
===========================================================================
*/

#define KC_N        40

// FTE names it; #630 in the engine table. checkbuiltin-gated in KC_SetBind.
void(float keynum, string bindcmd, optional float bindmap, optional float modifier) setkeybind = #0:setkeybind;
#define KC_STATUS_T 4           // seconds a bind's result stays on the status line

// id|label|command a rebind writes|other bindings that count as this row (;)|default.cfg's keys|group
// |label on a drawn key cap (Patch 1392)
// Patch 851: m goto_start, r reset (default.cfg); goto_spawn has no key.  The binds that
// shipped before, `say !m` and `say !r`, still count as the first two (cl_warpop.qc).
string(float i) KC_Def =
{
	if (i == 0)  return "forward|Forward|+forward||w|Movement|forward";
	if (i == 1)  return "back|Back|+back||s|Movement|back";
	if (i == 2)  return "left|Strafe left|+moveleft||a|Movement|strafe left";
	if (i == 3)  return "right|Strafe right|+moveright||d|Movement|strafe right";
	if (i == 4)  return "jump|Jump|+jump||SPACE MWHEELUP MWHEELDOWN|Movement|jump";
	if (i == 5)  return "duck|Duck|+duck||LCTRL|Movement|duck";
	if (i == 6)  return "walk|Walk|+speed||LSHIFT|Movement|walk";
	if (i == 7)  return "turnleft|Turn left|+left||q MOUSE1|Movement|turn left";
	if (i == 8)  return "turnright|Turn right|+right||e MOUSE2|Movement|turn right";
	if (i == 9)  return "hud|HUD editor|hud_edit||c|Menus|HUD edit";
	if (i == 10) return "gfx|Graphics|gfx_menu||x|Menus|gfx menu";
	if (i == 11) return "keys|Key config|config_menu||k|Menus|keys menu";
	if (i == 12) return "player|Player|player_edit|hud_player|p|Menus|player";   // Patch 806; 898 player_edit
	if (i == 13) return "entview|Entity view|ent_view|||Tools|ent view";   // Patch 809; P1400 shown among Tools
	if (i == 14) return "savemenu|Save menu|save_menu|saveloc_menu;mom_saveloc_close|z|Saves|save menu";
	if (i == 15) return "save|Save|sl_save|mom_saveloc_create|1|Saves|save";
	if (i == 16) return "load|Load (hold)|+sl_hold|sl_load;+mom_saveloc_current;mom_saveloc_current|2|Saves|load";
	if (i == 17) return "delete|Delete|sl_del|mom_saveloc_remove_current|4|Saves|delete save";
	if (i == 18) return "prev|Previous save|sl_prev|mom_saveloc_nav_prev||Saves|prev save";
	if (i == 19) return "next|Next save|sl_next|mom_saveloc_nav_next||Saves|next save";
	if (i == 20) return "restart|Restart run|goto_start|say !m|m|Run|restart";
	if (i == 21) return "reset|Reset stage|reset|say !r|r|Run|reset";     // Patch 848
	if (i == 22) return "respawn|Go to spawn|goto_spawn|||Run|spawn";     // Patch 845
	if (i == 23) return "rewind|Rewind|rewind||t BACKSPACE|Run|rewind";
	if (i == 24) return "noclip|Noclip|noclip||v|Run|noclip";
	if (i == 25) return "paint|Paint (hold)|paint|+paint|MOUSE3|Run|paint";     // Patch 772; 898 on MOUSE3
	if (i == 26) return "share|Share (look at a player)|share||f|Run|share";  // Patch 777
	// P1400: tools and game keys. ESCAPE is the engine's own menu key (keys.c): never written.
	if (i == 27) return "report|Report|report||F3|Tools|report";
	if (i == 28) return "surfview|Surf view|surf_view|||Tools|surf view";
	if (i == 29) return "entcursor|Entity inspector|ent_cursor|||Tools|inspect";
	if (i == 30) return "zoneedit|Zone editor|zone_edit|||Tools|zones";
	if (i == 31) return "linegraph|Run graph|linegraph|||Tools|run graph";
	if (i == 32) return "ghost|Race ghost|ghost||g|Tools|ghost";
	if (i == 33) return "scores|Scores (hold)|+showscores||TAB|Game|scores";
	if (i == 34) return "chat|Chat|messagemode|chat_open||Game|chat";
	if (i == 35) return "console|Console|toggleconsole||`|Game|console";
	if (i == 36) return "menu|Main menu|togglemenu||ESCAPE|Game|menu";
	if (i == 37) return "journal|Patch notes|ui_journal|ui_updates|F2|Game|notes";
	if (i == 38) return "screenshot|Screenshot|screenshot||F9|Game|screenshot";
	if (i == 39) return "fullscreen|Fullscreen|fullscreen_toggle|vid_toggle|F11|Game|fullscreen";
	return "";
};

// P1400: the order both tabs list the rows in, three columns from KC_COL1 and KC_COL2. Row 13
// keeps its id and index (the hint strip and old binds read them) but is listed with the tools.
#define KC_COL1 13
#define KC_COL2 26
float(float n) KC_Order =
{
	if (n < 13) return n;
	if (n < 28) return n + 1;
	if (n == 28) return 13;
	return n;
};

string(float i, float f) KC_F = { return Gfx_Field(KC_Def(i), f, "|"); };

// The strip's items: rows of the table above, in the order asked for.
float(float n) KC_HintRow =
{
	if (n == 0) return 14;      // save menu
	if (n == 1) return 10;      // graphics
	if (n == 2) return 9;       // hud editor
	if (n == 3) return 12;      // player
	if (n == 4) return 24;      // noclip
	if (n == 5) return 23;      // rewind
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
// Patch 863: the strip's measured layout, kept until its text, size, font or screen changes and
// re-taken at each KC_Refresh. Per item: [0] chip width, [1] key text's offset in it,
// [2] label width; the strings are zoned beside it.
float *kc_hl;
string *kc_hs;
float kc_hl_n, kc_hl_w, kc_hl_at, kc_hl_sc, kc_hl_lsz, kc_hl_rx, kc_hl_font;
vector kc_hl_scr;

// Patch 1392: the Keyboard tab.
#define KC_TAB_ROWS 0
#define KC_TAB_KEYS 1
#define KC_KB_MAX   128
#define KC_KB_F     8           // floats per cap: x y w h (key units), key, row (-1 none), bound (2: as left),
                                // bind is the own command (P1400)
#define KC_KB_S     4           // strings per cap: layout name, face, bind lines 1 and 2
#define KC_KS_F     4
#define KC_KS_MAX   16          // the strip of bound keys off the drawing: key, chip width, row, own command
#define KC_SLOT_ADD 64          // past any row's keys: KC_Assign adds the key, replacing none
#define KC_KB_U     24          // a key unit, in panel units
#define KC_KB_UH    6.25        // the drawing's height in key units (26.5 wide)
#define KC_KB_PW    652         // the tab's panel: 8 + 26.5 * 24 + 8
#define KC_KB_PH    386
#define KC_KB_COLW  130         // three action columns, then the info column
#define KC_KB_LABW  64
#define KC_KB_INFW  210
float  kc_tab;
float  kc_gen;                  // bumped by a KC_Refresh that found a bind changed: the drawing's cache key
float() KC_KbSig;
float(string id) KC_RowId;
float(float scan) KC_KeyKept;
float(float scan) KC_LeftOf;
float  kc_sel;                  // the picked action; -1 none
float  kc_kb_key;               // the key last clicked; 0 none
float  kc_kb_hov;               // the key under the pointer at the last draw; 0 none
float  kc_kb_hovrow;            // the action row under the pointer; -1 none
float  *kc_kbf;
string *kc_kbs;
float  kc_kb_n, kc_kb_parsed;
string kc_kb_miss;              // layout names stringtokeynum does not know
float  kc_kb_gen, kc_kb_sc, kc_kb_font;
vector kc_kb_px;
float  *kc_ksq;
string *kc_kss;
float  kc_ks_n, kc_ks_all;
string kc_kb_rl[KC_N];          // each row's label and keys, fitted to the list
string kc_kb_rk[KC_N];
float  kc_ki_key, kc_ki_gen, kc_ki_w, kc_ki_font, kc_ki_row, kc_ki_capw;
vector kc_ki_px;
string kc_ki_name, kc_ki_cap, kc_ki_l1, kc_ki_l2;
string kc_fit2;                 // KC_Fit's second line

// P1400: a typed command as the pick, and the two text fields (Your own command, Edit key).
#define KC_CUSTOM   -2          // kc_sel for the typed command
#define KC_FLD_CMD  1
#define KC_FLD_EDIT 2
#define KC_FLD_MAX  127
string kc_cmd;                  // the typed command once Entered; "" none
string kc_ckeys;                // keys bound to exactly kc_cmd
float  kc_ccnt;
float  kc_fld;                  // the field with the keyboard; 0 none
string kc_ctext, kc_etext;      // the fields' text
float  kc_ccaret, kc_ecaret;
float  kc_ekey;                 // the key the Edit field rebinds
vector kc_cf_p, kc_cf_s, kc_ef_p, kc_ef_s;   // the fields as last drawn, for a click's focus
float  *kc_fkeys;               // keys pressed into a field: their releases are eaten (QC key + 1024)

void() KC_Register =
{
	registercommand("config_menu");
	registercvar("hud_keyhint",   "1",      CVAR_ARCHIVE);
	registercvar("hud_keyhint_x", "0.0448", CVAR_ARCHIVE);
	registercvar("hud_keyhint_y", "0.9582", CVAR_ARCHIVE);
	registercvar("cl_keycfg_tab", "0",      CVAR_ARCHIVE);
	kc_cap_i = -1;
	kc_eatkey = -1;
	kc_hov_i = -1;
	kc_sel = -1;
	kc_kb_hovrow = -1;
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
	if (k == "LWIN")       return "Win";
	if (k == "RWIN")       return "RWin";
	if (k == "APP")        return "Menu";
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

// stringtokeynum's "no such key" is -1; Right Shift/Ctrl/Alt, Win and Menu are other negatives.
float(float k) KC_KeyOk = { return (k != 0 && k != -1); };

string(string old, string s) KC_Rezone =
{
	if (old != "")
		strunzone(old);
	if (s == "")
		return "";
	return strzone(s);
};

// P1400: the keys whose own bind is exactly the typed command (findkeysforcommandex also
// takes "say hi" for "say", and Shift+ binds stringtokeynum refuses).
void() KC_CmdKeys =
{
	local string all, k, s;
	local float j, code, n;

	s = "";
	n = 0;
	if (kc_cmd != "")
	{
		all = findkeysforcommandex(kc_cmd);
		for (j = 0; j < 32; j = j + 1)
		{
			k = Gfx_Field(all, j, " ");
			if (k == "")
				break;
			code = stringtokeynum(k);
			if (!KC_KeyOk(code))
				continue;
			if (strcmp(getkeybind(code), kc_cmd))
				continue;
			s = (s == "") ? k : strcat(s, " ", k);
			n = n + 1;
		}
	}
	kc_ckeys = KC_Rezone(kc_ckeys, s);
	kc_ccnt = n;
};

void() KC_Refresh =
{
	local float i, n, r;
	local string s, h;

	// The Keyboard tab rebuilds its 510-key scan on kc_gen: only for a changed bind (KC_KbSig).
	if (!kc_open || KC_KbSig())
		kc_gen = kc_gen + 1;
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
		kc_hl_at = -1;              // a command can change it inside one cltime: measure again
	}
	KC_CmdKeys();
	kc_cacheat = cltime;
};

// A bind changed: read the table again now, not at the next half second.
// A console verb with the panel closed saves at once: KC_Close (which saves) never runs for it.
void() KC_Changed =
{
	kc_dirty = TRUE;
	kc_cacheat = 0;
	KC_Refresh();
	if (!kc_open)
	{
		kc_dirty = FALSE;
		localcmd("cfg_save\n");
	}
};

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

	if (i < 0 || i >= KC_N || !KC_KeyOk(scan))
		return;
	kn = keynumtostring(scan);
	if (kn == "")
		return;
	if (KC_KeyKept(scan))
		return;
	was = getkeybind(scan);
	if (was == "")
	if (KC_KeyOk(KC_LeftOf(scan)))
		was = getkeybind(KC_LeftOf(scan));     // it followed the left key; it no longer does
	other = KC_RowOf(was);
	old = Gfx_Field(kc_keys[i], s, " ");
	if (old != "")
	{
		ok = stringtokeynum(old);
		if (KC_KeyOk(ok) && ok != scan)
		{
			if (KC_KeyKept(ok))
				return;
			KC_SetBind(ok, "");
		}
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
	if (!KC_KeyOk(ok) || KC_KeyKept(ok))
		return;
	KC_SetBind(ok, "");
	KC_Say(sprintf("%s cleared from %s", KC_KeyLabel(old), KC_F(i, 1)));
	KC_Changed();
};

// With no bind of its own (none, or ""), a right Shift/Ctrl/Alt/Win runs the left one's
// (keys.c Key_Event's fallback). -> that left key, or 0.
float(float scan) KC_LeftOf =
{
	local string n;
	n = keynumtostring(scan);
	if (n == "RSHIFT") return stringtokeynum("LSHIFT");
	if (n == "RCTRL")  return stringtokeynum("LCTRL");
	if (n == "RALT")   return stringtokeynum("LALT");
	if (n == "RWIN")   return stringtokeynum("LWIN");
	return 0;
};

// Escape (the engine's menu key whatever its bind, keys.c) and the LAST console key stay: a spare
// console or menu key is an ordinary key. Shift+Esc opens the console, but not with con_stayhidden 2.
float(float scan) KC_IsKept =
{
	local float r;
	if (scan == K_ESCAPE)
		return TRUE;
	if (getkeybind(scan) != "toggleconsole")
		return FALSE;
	r = KC_RowId("console");
	return (r < 0 || kc_cnt[r] <= 1);
};

float(float scan) KC_KeyKept =
{
	if (KC_IsKept(scan))
	{
		KC_Say(sprintf("%s stays the %s key", KC_KeyLabel(keynumtostring(scan)),
		               (scan == K_ESCAPE) ? "menu" : "console"));
		return TRUE;
	}
	return FALSE;
};

// A right-click on a drawn key: bound to "", as KC_Clear does.
void(float scan) KC_ClearKey =
{
	local string was, kn;
	local float r;

	if (!KC_KeyOk(scan))
		return;
	kn = KC_KeyLabel(keynumtostring(scan));
	if (KC_KeyKept(scan))
		return;
	was = getkeybind(scan);
	if (was == "")
	{
		r = KC_LeftOf(scan);
		if (KC_KeyOk(r))
		if (getkeybind(r) != "")
		{
			KC_Say(sprintf("%s has no bind of its own: it does what %s does", kn, KC_KeyLabel(keynumtostring(r))));
			return;
		}
		KC_Say(sprintf("%s is not bound", kn));
		return;
	}
	r = KC_RowOf(was);
	KC_SetBind(scan, "");
	if (r >= 0)
		was = KC_F(r, 1);
	else
		was = sprintf("\"%s\"", was);
	// "" on a right modifier is no bind to the engine: it now does what the left one does.
	r = KC_LeftOf(scan);
	if (KC_KeyOk(r) && getkeybind(r) != "")
		KC_Say(sprintf("%s no longer %s: it now does what %s does", kn, was, KC_KeyLabel(keynumtostring(r))));
	else
		KC_Say(sprintf("%s cleared (was %s)", kn, was));
	KC_Changed();
};

// P1400: key `scan` now runs the typed command cmd; KC_Assign's report of what it was.
void(string cmd, float scan) KC_AssignCmd =
{
	local string was, kn;
	local float other;

	if (cmd == "" || !KC_KeyOk(scan))
		return;
	kn = KC_KeyLabel(keynumtostring(scan));
	was = getkeybind(scan);
	if (was == "")
	if (KC_KeyOk(KC_LeftOf(scan)))
		was = getkeybind(KC_LeftOf(scan));
	other = KC_RowOf(was);
	KC_SetBind(scan, cmd);
	if (was == "" || !strcmp(was, cmd))
		kn = sprintf("%s: \"%s\"", kn, cmd);
	else if (other >= 0)
		kn = sprintf("%s: \"%s\" (was %s)", kn, cmd, KC_F(other, 1));
	else
		kn = sprintf("%s: \"%s\" (was \"%s\")", kn, cmd, was);
	was = KC_PanelDigit(scan);
	if (was != "")
		kn = strcat(kn, "; with the save menu open it is ", was);
	KC_Say(kn);
	KC_Changed();
};

// A click on a drawn key: it gets the picked action, or is only read into the info box.
void(float scan) KC_KeyClick =
{
	if (!KC_KeyOk(scan))
		return;
	kc_kb_key = scan;
	if (kc_sel == KC_CUSTOM)
	if (!KC_KeyKept(scan))
		KC_AssignCmd(kc_cmd, scan);
	if (kc_sel >= 0)
	if (!KC_KeyKept(scan))
		KC_Assign(kc_sel, KC_SLOT_ADD, scan);
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
			if (KC_KeyOk(k) && k != K_ESCAPE)   // ` is the console row's default, rebound below
				KC_SetBind(k, "");
		}
	for (i = 0; i < KC_N; i = i + 1)
	{
		d = KC_F(i, 4);
		for (j = 0; j < 8; j = j + 1)
		{
			k = stringtokeynum(Gfx_Field(d, j, " "));
			if (!KC_KeyOk(k))
				break;
			if (k != K_ESCAPE)
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

/*
  P1400: the Keyboard tab's two text fields. While one has the keyboard every key
  is its (KC_CaptureEvent, ahead of the chat draft), Esc leaves it, and a key it
  took has its release eaten even after it lets go, as hud_edit's field does.
*/
string(string was, string now) KC_Rezoned =
{
	if (!strcmp(was, now))
		return was;
	if (now != "")
		now = strzone(now);
	if (was != "")
		strunzone(was);
	return now;
};

float(float k) KC_FieldOwned =
{
	if (!kc_fkeys || k < -1024 || k >= 1024)
		return FALSE;
	return kc_fkeys[k + 1024];
};

void(float k, float v) KC_FieldOwn =
{
	if (k < -1024 || k >= 1024)
		return;
	if (!kc_fkeys)
		kc_fkeys = memalloc(sizeof(float) * 2048);
	kc_fkeys[k + 1024] = v;
};

// Leave the field: the typed command stays in its box; an edit is dropped.
void() KC_FieldStop =
{
	if (kc_fld == KC_FLD_EDIT)
	{
		kc_etext = KC_Rezone(kc_etext, "");
		kc_ecaret = 0;
		kc_ekey = 0;
	}
	if (kc_fld)
		sui_keys_forget();          // a Shift held while typing would stay held for the next field
	kc_fld = 0;
	if (sui_field_focused() == "kc_cf" || sui_field_focused() == "kc_ef")
		sui_text_unfocus();
};

void(float evtype, float scan, float char) KC_FieldKey =
{
	local string was;

	if (kc_fld == KC_FLD_CMD)
	{
		was = kc_ctext;
		sui_text_event(evtype, scan, char, "kc_cf", kc_ctext, kc_ccaret);
		if (strlen(kc_ctext) > KC_FLD_MAX && strlen(kc_ctext) > strlen(was))
			kc_ctext = was;
		else
			kc_ctext = KC_Rezoned(was, kc_ctext);
		kc_ccaret = min(kc_ccaret, strlen(kc_ctext));
	}
	else if (kc_fld == KC_FLD_EDIT)
	{
		was = kc_etext;
		sui_text_event(evtype, scan, char, "kc_ef", kc_etext, kc_ecaret);
		if (strlen(kc_etext) > KC_FLD_MAX && strlen(kc_etext) > strlen(was))
			kc_etext = was;         // only growth past the limit is refused
		else
			kc_etext = KC_Rezoned(was, kc_etext);
		kc_ecaret = min(kc_ecaret, strlen(kc_etext));
	}
};

// One pasted character (cl_main.qc's IE_PASTE chain), for the field with the keyboard.
float(float c) KC_Paste =
{
	if (!kc_open || !kc_fld || c < 32 || c > 126)
		return FALSE;
	KC_FieldKey(IE_KEYDOWN, 0, c);
	return TRUE;
};

// A bind with a double quote would not survive cfg_save's quoting.
float(string s) KC_CmdBad =
{
	if (strstrofs(s, "\"", 0) < 0)
		return FALSE;
	KC_Say("a double quote cannot go in a bind here");
	return TRUE;
};

// Enter in Your own command, or `config_menu custom`: the command becomes the pick.
void(string s) KC_CustomSet =
{
	s = strtrim(s);
	if (KC_CmdBad(s))
		return;
	kc_ctext = KC_Rezoned(kc_ctext, s);
	kc_ccaret = strlen(kc_ctext);
	kc_cmd = KC_Rezone(kc_cmd, s);
	kc_kb_gen = -1;                 // the caps' own-command marks are read again
	KC_CmdKeys();
	if (s == "")
	{
		if (kc_sel == KC_CUSTOM)
			kc_sel = -1;
	}
	else
	{
		kc_sel = KC_CUSTOM;
		KC_Say(sprintf("click keys to bind \"%s\" to them", s));
	}
	if (kc_fld == KC_FLD_CMD)
		KC_FieldStop();
};

// Enter in the Edit field, or `config_menu editkey`: the key runs s; empty clears it.
void(float key, string s) KC_EditKey =
{
	s = strtrim(s);
	if (!KC_KeyOk(key))
		return;
	if (KC_KeyKept(key))
		return;
	if (KC_CmdBad(s))
		return;
	kc_kb_key = key;
	if (s == "")
		KC_ClearKey(key);
	else
		KC_AssignCmd(s, key);
	if (kc_fld == KC_FLD_EDIT)
		KC_FieldStop();
};

void(float key) KC_EditBegin =
{
	if (!kc_open || kc_tab != KC_TAB_KEYS)
		return;
	if (!KC_KeyOk(key))
	{
		KC_Say("click a key first");
		return;
	}
	if (KC_KeyKept(key))
		return;
	KC_FieldStop();
	kc_ekey = key;
	kc_etext = KC_Rezone(kc_etext, getkeybind(key));
	kc_ecaret = strlen(kc_etext);
	kc_fld = KC_FLD_EDIT;
	sui_field_focus("kc_ef");
};

// A press of Mouse 1: on a field it takes the keyboard; anywhere else the field lets go.
void() KC_FieldClick =
{
	if (kc_tab != KC_TAB_KEYS)
		return;
	if (is_2dpoint_in_bbox(_cursor_position, kc_cf_p, kc_cf_s))
	{
		if (kc_fld != KC_FLD_CMD)
			KC_FieldStop();
		kc_fld = KC_FLD_CMD;
		sui_field_focus("kc_cf");
		return;
	}
	if (kc_fld == KC_FLD_EDIT)
	if (is_2dpoint_in_bbox(_cursor_position, kc_ef_p, kc_ef_s))
		return;
	if (kc_fld)
		KC_FieldStop();
};

void() KC_Close =
{
	if (!kc_open)
		return;
	kc_open = FALSE;
	KC_FieldStop();
	sui_keys_forget();
	kc_cap_i = -1;
	kc_armed = FALSE;
	kc_sel = -1;                    // reopened later, a click only reads a key until one is picked
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

void(float t) KC_SetTab =
{
	t = (t == KC_TAB_KEYS) ? KC_TAB_KEYS : KC_TAB_ROWS;
	if (t != kc_tab)
	{
		kc_cap_i = -1;
		kc_armed = FALSE;
		KC_FieldStop();
		sui_tooltip_reset();
	}
	kc_tab = t;
	if (cvar("cl_keycfg_tab") != t)
		cvar_set("cl_keycfg_tab", ftos(t));
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
	KC_FieldStop();
	sui_keys_forget();
	kc_cap_i = -1;
	kc_eatkey = -1;
	kc_armed = FALSE;
	kc_hov_i = -1;
	kc_hov_slider = 0;
	kc_tab = (cvar("cl_keycfg_tab") == KC_TAB_KEYS) ? KC_TAB_KEYS : KC_TAB_ROWS;
	kc_kb_hov = 0;
	kc_kb_hovrow = -1;
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

// The drawing in key units, "x y|cap cap ...": a cap is NAME[:w[:h]] in the engine's key
// names (keys.c keynames), _w a gap. A name stringtokeynum does not know is left off.
string(float n) KC_KbLine =
{
	if (n == 0)  return "0 0|ESCAPE _1 F1 F2 F3 F4 _0.5 F5 F6 F7 F8 _0.5 F9 F10 F11 F12";
	if (n == 1)  return "15.5 0|PRINTSCREEN SCROLLLOCK PAUSE";
	if (n == 2)  return "24 0|MOUSE1:1.25 MOUSE2:1.25";
	if (n == 3)  return "0 1.25|` 1 2 3 4 5 6 7 8 9 0 - = BACKSPACE:2";
	if (n == 4)  return "0 2.25|TAB:1.5 q w e r t y u i o p [ ] BACKSLASH:1.5";
	if (n == 5)  return "0 3.25|CAPSLOCK:1.75 a s d f g h j k l SEMICOLON ' ENTER:2.25";
	if (n == 6)  return "0 4.25|LSHIFT:2.25 z x c v b n m , . / RSHIFT:2.75";
	if (n == 7)  return "0 5.25|LCTRL:1.25 LWIN:1.25 LALT:1.25 SPACE:6.25 RALT:1.25 RWIN:1.25 APP:1.25 RCTRL:1.25";
	if (n == 8)  return "15.5 1.25|INS HOME PGUP";
	if (n == 9)  return "15.5 2.25|DEL END PGDN";
	if (n == 10) return "16.5 4.25|UPARROW";
	if (n == 11) return "15.5 5.25|LEFTARROW DOWNARROW RIGHTARROW";
	if (n == 12) return "19 1.25|KP_NUMLOCK KP_SLASH KP_STAR KP_MINUS";
	if (n == 13) return "19 2.25|KP_HOME KP_UPARROW KP_PGUP KP_PLUS:1:2";
	if (n == 14) return "19 3.25|KP_LEFTARROW KP_5 KP_RIGHTARROW";
	if (n == 15) return "19 4.25|KP_END KP_DOWNARROW KP_PGDN KP_ENTER:1:2";
	if (n == 16) return "19 5.25|KP_INS:2 KP_DEL";
	if (n == 17) return "24 1.25|MWHEELUP:2.5";
	if (n == 18) return "24 2.25|MOUSE3:2.5";
	if (n == 19) return "24 3.25|MWHEELDOWN:2.5";
	if (n == 20) return "24 4.25|MOUSE4:1.25 MOUSE5:1.25";
	return "";
};

// A key's face on the drawing: KC_KeyLabel, shorter, and the numpad by what it types.
string(string k) KC_CapLabel =
{
	if (k == "ESCAPE")        return "Esc";
	if (k == "PRINTSCREEN")   return "PrtSc";
	if (k == "SCROLLLOCK")    return "ScrLk";
	if (k == "BACKSPACE")     return "Backspace";
	if (k == "APOSTROPHE")    return "'";
	if (k == "RSHIFT")        return "Shift";
	if (k == "RCTRL")         return "Ctrl";
	if (k == "RALT")          return "Alt";
	if (k == "RWIN")          return "Win";
	if (k == "INS")           return "Ins";
	if (k == "DEL")           return "Del";
	if (k == "MWHEELDOWN")    return "Wheel down";
	if (k == "KP_NUMLOCK")    return "NumLk";
	if (k == "KP_SLASH")      return "/";
	if (k == "KP_STAR")       return "*";
	if (k == "KP_MINUS")      return "-";
	if (k == "KP_PLUS")       return "+";
	if (k == "KP_ENTER")      return "Enter";
	if (k == "KP_INS")        return "0";
	if (k == "KP_END")        return "1";
	if (k == "KP_DOWNARROW")  return "2";
	if (k == "KP_PGDN")       return "3";
	if (k == "KP_LEFTARROW")  return "4";
	if (k == "KP_5")          return "5";
	if (k == "KP_RIGHTARROW") return "6";
	if (k == "KP_HOME")       return "7";
	if (k == "KP_UPARROW")    return "8";
	if (k == "KP_PGUP")       return "9";
	if (k == "KP_DEL")        return ".";
	return KC_KeyLabel(k);
};

void() KC_KbParse =
{
	local float n, j, x, y, w, h, code, c, b;
	local string line, xy, toks, t, name, miss;

	if (!kc_kbf)
	{
		kc_kbf = memalloc(sizeof(float) * KC_KB_MAX * KC_KB_F);
		kc_kbs = memalloc(sizeof(string) * KC_KB_MAX * KC_KB_S);
		kc_ksq = memalloc(sizeof(float) * KC_KS_MAX * KC_KS_F);
		kc_kss = memalloc(sizeof(string) * KC_KS_MAX);
	}
	c = 0;
	miss = "";
	for (n = 0; n < 32; n = n + 1)
	{
		line = KC_KbLine(n);
		if (line == "")
			break;
		xy = Gfx_Field(line, 0, "|");
		toks = Gfx_Field(line, 1, "|");
		x = stof(Gfx_Field(xy, 0, " "));
		y = stof(Gfx_Field(xy, 1, " "));
		for (j = 0; j < 24; j = j + 1)
		{
			t = Gfx_Field(toks, j, " ");
			if (t == "")
				break;
			if (substring(t, 0, 1) == "_")
			{
				x = x + stof(substring(t, 1, -1));
				continue;
			}
			name = Gfx_Field(t, 0, ":");
			w = stof(Gfx_Field(t, 1, ":"));
			h = stof(Gfx_Field(t, 2, ":"));
			if (w <= 0)
				w = 1;
			if (h <= 0)
				h = 1;
			code = stringtokeynum(name);
			if (!KC_KeyOk(code))
				miss = (miss == "") ? name : strcat(miss, " ", name);
			else if (c < KC_KB_MAX)
			{
				b = c * KC_KB_F;
				kc_kbf[b] = x;
				kc_kbf[b + 1] = y;
				kc_kbf[b + 2] = w;
				kc_kbf[b + 3] = h;
				kc_kbf[b + 4] = code;
				kc_kbf[b + 5] = -1;
				kc_kbf[b + 6] = FALSE;
				kc_kbs[c * KC_KB_S] = KC_Rezone(kc_kbs[c * KC_KB_S], name);
				kc_kbs[c * KC_KB_S + 1] = KC_Rezone(kc_kbs[c * KC_KB_S + 1], KC_CapLabel(name));
				c = c + 1;
			}
			x = x + w;
		}
	}
	kc_kb_n = c;
	kc_kb_miss = KC_Rezone(kc_kb_miss, miss);
	kc_kb_parsed = TRUE;
};

float(float code) KC_KbHas =
{
	local float c;
	for (c = 0; c < kc_kb_n; c = c + 1)
		if (kc_kbf[c * KC_KB_F + 4] == code)
			return TRUE;
	return FALSE;
};

// TRUE when any key's bind differs from the last call: two Adler sums of crc16 over keys 2..511
// (KC_KbScan's range), cheap beside the scan and its text fitting, which only run on a change.
float kc_siga, kc_sigb;
float() KC_KbSig =
{
	local float k, a, b;
	local string t;
	a = 1;
	b = 0;
	for (k = 2; k < 512; k = k + 1)
	{
		t = getkeybind((k < 128) ? k : -k);
		if (t == "")
			continue;
		a = a + crc16(FALSE, t) + k;
		a = a - floor(a / 65521) * 65521;
		b = b + a;
		b = b - floor(b / 65521) * 65521;
	}
	if (a == kc_siga && b == kc_sigb)
		return FALSE;
	kc_siga = a;
	kc_sigb = b;
	return TRUE;
};

// Each cap's bind and row, and the bound keys the drawing lacks. Engine keys 2..511: below 128
// the QC number is the engine's; above, -k reads engine key k (MP_TranslateQCtoFTECodes).
void() KC_KbScan =
{
	local float c, k, code, q, n;
	local string b;

	for (c = 0; c < kc_kb_n; c = c + 1)
	{
		code = kc_kbf[c * KC_KB_F + 4];
		b = getkeybind(code);
		kc_kbf[c * KC_KB_F + 6] = (b != "");
		if (b == "")
		{
			q = KC_LeftOf(code);
			if (KC_KeyOk(q))
			{
				b = getkeybind(q);
				if (b != "")
					kc_kbf[c * KC_KB_F + 6] = 2;    // follows the left key
			}
		}
		kc_kbf[c * KC_KB_F + 5] = KC_RowOf(b);
		kc_kbf[c * KC_KB_F + 7] = FALSE;
		if (kc_cmd != "")
			kc_kbf[c * KC_KB_F + 7] = !strcmp(b, kc_cmd);
	}
	n = 0;
	kc_ks_all = 0;
	for (k = 2; k < 512; k = k + 1)
	{
		code = (k < 128) ? k : -k;
		b = getkeybind(code);
		if (b == "")
			continue;
		q = stringtokeynum(keynumtostring(code));     // the number the drawing would hold
		if (!KC_KeyOk(q))
			q = code;
		if (KC_KbHas(q))
			continue;
		kc_ks_all = kc_ks_all + 1;
		if (n < KC_KS_MAX)
		{
			kc_ksq[n * KC_KS_F] = q;
			kc_ksq[n * KC_KS_F + 2] = KC_RowOf(b);
			kc_ksq[n * KC_KS_F + 3] = FALSE;
			if (kc_cmd != "")
				kc_ksq[n * KC_KS_F + 3] = !strcmp(b, kc_cmd);
			n = n + 1;
		}
	}
	kc_ks_n = n;
};

void(float caps) KC_KbReport =
{
	local float i, b;
	local string s;

	KC_Refresh();
	if (!kc_kb_parsed)
		KC_KbParse();
	KC_KbScan();
	kc_kb_gen = -1;                 // the strip's chips are measured again at the next draw
	s = "";
	for (i = 0; i < kc_ks_n; i = i + 1)
		s = (s == "") ? keynumtostring(kc_ksq[i * KC_KS_F]) : strcat(s, " ", keynumtostring(kc_ksq[i * KC_KS_F]));
	print(sprintf("config_menu: layout caps %g missing [%s] offboard %g [%s]\n", kc_kb_n, kc_kb_miss, kc_ks_all, s));
	if (!caps)
		return;
	for (i = 0; i < kc_kb_n; i = i + 1)
	{
		b = i * KC_KB_F;
		print(sprintf("config_menu: cap %s key %g at %g,%g size %gx%g ", kc_kbs[i * KC_KB_S],
		              kc_kbf[b + 4], kc_kbf[b], kc_kbf[b + 1], kc_kbf[b + 2], kc_kbf[b + 3]));
		print(sprintf("row %g bind [%s]\n", kc_kbf[b + 5], getkeybind(kc_kbf[b + 4])));
	}
};

// The rest of the command line from argument n, or argument n alone when it is the last.
string(string cmd, float n) KC_Tail =
{
	if (argv(n) == "" || argv(n + 1) == "")
		return argv(n);
	return substring(cmd, argv_start_index(n), -1);
};

float(string cmd) KC_Console =
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
		print(sprintf("config_menu: tab %g picked %s field %g own [%s] keys [%s]\n", kc_tab,
		              (kc_sel >= 0) ? KC_F(kc_sel, 0) : ((kc_sel == KC_CUSTOM) ? "own" : "-"), kc_fld, kc_cmd, kc_ckeys));
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
	if (a == "actions" || a == "keyboard")
	{
		KC_Open();
		KC_SetTab((a == "keyboard") ? KC_TAB_KEYS : KC_TAB_ROWS);
		return TRUE;
	}
	if (a == "layout")
	{
		KC_KbReport(argv(2) == "caps");
		return TRUE;
	}
	if (a == "custom")
	{
		KC_CustomSet(KC_Tail(cmd, 2));
		return TRUE;
	}
	if (a == "focus")               // arm: what a click on the field (cmd) or Edit (edit <key>) does
	{
		KC_Open();
		KC_SetTab(KC_TAB_KEYS);
		KC_Refresh();
		if (argv(2) == "edit")
			KC_EditBegin(stringtokeynum(argv(3)));
		else if (kc_tab == KC_TAB_KEYS)
		{
			KC_FieldStop();
			kc_fld = KC_FLD_CMD;
			sui_field_focus("kc_cf");
		}
		print(sprintf("config_menu: field %g\n", kc_fld));
		return TRUE;
	}
	if (a == "click")               // arm: a click on a key with the current pick
	{
		KC_Refresh();
		k = stringtokeynum(argv(2));
		if (!KC_KeyOk(k))
			print(sprintf("config_menu: no key called %s\n", argv(2)));
		else
			KC_KeyClick(k);
		return TRUE;
	}
	if (a == "editkey")
	{
		KC_Refresh();
		k = stringtokeynum(argv(2));
		if (!KC_KeyOk(k))
			print(sprintf("config_menu: no key called %s\n", argv(2)));
		else
			KC_EditKey(k, KC_Tail(cmd, 3));
		return TRUE;
	}
	if (a == "clearkey")
	{
		KC_Refresh();
		k = stringtokeynum(argv(2));
		if (!KC_KeyOk(k))
			print(sprintf("config_menu: no key called %s\n", argv(2)));
		else
			KC_ClearKey(k);
		return TRUE;
	}

	i = KC_RowId(argv(2));
	if (i < 0)
	{
		print("config_menu [status | hint | reset | yaw <v> | sens <v> | actions | keyboard |\n"
		      "             bind <id> <key> [slot] | clear <id> [slot] | capture <id> [slot] |\n"
		      "             place <id> <key> | clearkey <key> | layout [caps] |\n"
		      "             custom [<command>] | editkey <key> [<command>]]\n");
		return TRUE;
	}
	KC_Refresh();
	if (a == "bind")
	{
		s = bound(0, stof(argv(4)), 1);
		k = stringtokeynum(argv(3));
		if (!KC_KeyOk(k))
			print(sprintf("config_menu: no key called %s\n", argv(3)));
		else
			KC_Assign(i, s, k);
		return TRUE;
	}
	if (a == "place")
	{
		k = stringtokeynum(argv(3));
		if (!KC_KeyOk(k))
			print(sprintf("config_menu: no key called %s\n", argv(3)));
		else
		{
			kc_sel = i;
			KC_KeyClick(k);
		}
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
			KC_SetTab(KC_TAB_ROWS);     // the waiting chip is on the Actions tab
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
	if (evtype == IE_KEYUP)
	if (KC_FieldOwned(scanx))
	{
		KC_FieldOwn(scanx, FALSE);
		if (kc_fld)
			KC_FieldKey(evtype, scanx, chary);
		return TRUE;
	}
	if (!kc_open)
		return FALSE;
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP)
		return FALSE;
	// P1400: a text field takes every key but the mouse's (K_MOUSE1..10, the wheel: 512..523).
	if (kc_fld && evtype == IE_KEYDOWN)
	if (scanx < K_MOUSE1 || scanx > K_MOUSE1 + 11)
	{
		if (chat_rep && !KC_FieldOwned(scanx))
			return TRUE;            // a repeat of a key held from before: neither typed nor its release taken
		KC_FieldOwn(scanx, TRUE);
		if (scanx == K_ESCAPE)
			KC_FieldStop();
		else if (scanx == K_ENTER || scanx == K_KP_ENTER)
		{
			if (kc_fld == KC_FLD_CMD)
				KC_CustomSet(kc_ctext);
			else
				KC_EditKey(kc_ekey, kc_etext);
		}
		else
			KC_FieldKey(evtype, scanx, chary);
		return TRUE;
	}
	if (kc_eatkey != -1 && scanx == kc_eatkey)
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
		if (evtype == IE_KEYDOWN)
			KC_FieldClick();
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN)
		{
			if (kc_tab == KC_TAB_KEYS)
				KC_ClearKey(kc_kb_hov);
			else if (kc_hov_i >= 0)
				KC_Clear(kc_hov_i, kc_hov_s);
		}
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

// True where the n-th listed row starts a column or a group: it gets a heading.
float(float n) KC_NewGroup =
{
	if (n == 0 || n == KC_COL1 || n == KC_COL2)
		return TRUE;
	return strcmp(KC_F(KC_Order(n), 5), KC_F(KC_Order(n - 1), 5)) != 0;
};

// A column's next line: a heading where the group changes, then the n-th listed row.
float(float n, vector p, float y, float labw, float chipw, float colw, float rh, float sc) KC_ColumnRow =
{
	if (KC_NewGroup(n))
	{
		KC_Heading([p_x, y, 0], colw, KC_F(KC_Order(n), 5), sc);
		y = y + rh;
	}
	KC_Row(KC_Order(n), [p_x, y, 0], labw, chipw, rh, sc);
	return y + rh;
};

// How many of s's characters fit in width w at text size want.
float(string s, float w, float want) KC_Prefix =
{
	local float lo, hi, mid;
	lo = 0;
	hi = strlen(s);
	while (lo < hi)
	{
		mid = ceil((lo + hi) * 0.5);
		if (KC_TextW(substring(s, 0, mid), want) <= w)
			lo = mid;
		else
			hi = mid - 1;
	}
	return lo;
};

// s in `lines` (1 or 2) lines of width w, broken at a space where one fits: line 1 is
// returned, line 2 left in kc_fit2; ".." marks a cut.
string(string s, float w, float want, float lines) KC_Fit =
{
	local float n, j, dots;
	local string a, rest;

	kc_fit2 = "";
	if (s == "" || KC_TextW(s, want) <= w)
		return s;
	dots = KC_TextW("..", want);
	if (lines < 2)
		return strcat(substring(s, 0, KC_Prefix(s, w - dots, want)), "..");
	n = KC_Prefix(s, w, want);
	if (n < 1)
		return "";
	for (j = n; j > 0; j = j - 1)
		if (substring(s, j, 1) == " ")
			break;
	if (j > 0)
	{
		a = substring(s, 0, j);
		rest = substring(s, j + 1, -1);
	}
	else
	{
		a = substring(s, 0, n);
		rest = substring(s, n, -1);
	}
	if (KC_TextW(rest, want) <= w)
		kc_fit2 = rest;
	else
		kc_fit2 = strcat(substring(rest, 0, KC_Prefix(rest, w - dots, want)), "..");
	return a;
};

// Short words for engine and menu commands a key often carries (the table's rows have their own).
string(string b) KC_CmdShort =
{
	if (b == "chat_say") return "chat";
	if (b == "messagemode2") return "team chat";
	if (b == "+attack") return "attack";
	if (b == "+use") return "use";
	return b;
};

// The Keyboard tab's words, measured once per bind read (KC_Refresh) and scale, not per frame.
void(float sc) KC_KbFit =
{
	local float c, b, row, w, i, j;
	local string t, s;

	for (c = 0; c < kc_kb_n; c = c + 1)
	{
		b = c * KC_KB_F;
		t = "";
		if (kc_kbf[b + 6])
		{
			row = kc_kbf[b + 5];
			if (row >= 0)
				t = KC_F(row, 6);
			else if (kc_kbf[b + 6] == 2)
				t = KC_CmdShort(getkeybind(KC_LeftOf(kc_kbf[b + 4])));
			else
				t = KC_CmdShort(getkeybind(kc_kbf[b + 4]));
			if (kc_kbf[b + 6] == 2)
				t = strcat(t, " (as left)");
		}
		w = (kc_kbf[b + 2] * KC_KB_U - 1.5 - 4) * sc;
		t = KC_Fit(t, w, 6 * sc, 2);
		kc_kbs[c * KC_KB_S + 2] = KC_Rezone(kc_kbs[c * KC_KB_S + 2], t);
		kc_kbs[c * KC_KB_S + 3] = KC_Rezone(kc_kbs[c * KC_KB_S + 3], kc_fit2);
	}
	for (i = 0; i < KC_N; i = i + 1)
	{
		s = "";
		for (j = 0; j < kc_cnt[i]; j = j + 1)
		{
			t = KC_KeyLabel(Gfx_Field(kc_keys[i], j, " "));
			s = (s == "") ? t : strcat(s, ", ", t);
		}
		kc_kb_rk[i] = KC_Rezone(kc_kb_rk[i], KC_Fit(s, (KC_KB_COLW - KC_KB_LABW - 4) * sc, 7 * sc, 1));
		kc_kb_rl[i] = KC_Rezone(kc_kb_rl[i], KC_Fit(KC_F(i, 1), (KC_KB_LABW - 6) * sc, 7 * sc, 1));
	}
	for (i = 0; i < kc_ks_n; i = i + 1)
	{
		row = kc_ksq[i * KC_KS_F + 2];
		if (row >= 0)
			t = KC_F(row, 6);
		else
			t = getkeybind(kc_ksq[i * KC_KS_F]);
		s = strcat(KC_KeyLabel(keynumtostring(kc_ksq[i * KC_KS_F])), ": ", KC_Fit(t, 70 * sc, 7 * sc, 1));
		kc_kss[i] = KC_Rezone(kc_kss[i], s);
		kc_ksq[i * KC_KS_F + 1] = KC_TextW(s, 7 * sc) + 8 * sc;
	}
};

// Inside the sui bracket with the UI face set: KC_TextW needs both.
void(float sc) KC_KbCache =
{
	if (!kc_kb_parsed)
		KC_KbParse();
	if (kc_kb_gen == kc_gen && kc_kb_sc == sc && kc_kb_font == ui_font_gen && kc_kb_px == sui_style_pixel_ratio)
		return;
	KC_KbScan();
	KC_KbFit(sc);
	kc_kb_gen = kc_gen;
	kc_kb_sc = sc;
	kc_kb_font = ui_font_gen;
	kc_kb_px = sui_style_pixel_ratio;
};

// One side of the tab switch, on a WELL pill KC_Header drew (Profile_Seg's look).
float(string id, vector pos, vector sz, string label, float on, float sc) KC_Seg =
{
	local float hot;
	local vector glyph;

	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	if (on)
		sui_roundbox(pos + [sc, sc, 0], sz - [2 * sc, 2 * sc, 0], (sz_y - 2 * sc) * 0.5, SUI_THEME_SELECTED, 1);
	else if (hot)
		sui_roundbox(pos + [sc, sc, 0], sz - [2 * sc, 2 * sc, 0], (sz_y - 2 * sc) * 0.5, SUI_THEME_HOVER, 1);
	glyph = sui_native_text_size(7 * sc);
	sui_native_text([pos_x + (sz_x - KC_TextW(label, 7 * sc)) * 0.5, pos_y + (sz_y - glyph_y) * 0.5, 0], label,
	                7 * sc, on ? SUI_THEME_ACCENT : (hot ? SUI_THEME_TEXT : SUI_THEME_DIM), 1);
	return sui_is_released(id);
};

// Both tabs' title row: the title, the tab switch, "Esc closes". -> the tab clicked, or -1.
float(vector p, float panw, float pad, float sc) KC_Header =
{
	local float x, segw, h, t;

	sui_native_text([p_x + pad, p_y + 6 * sc, 0], "Key configuration", 10 * sc, SUI_THEME_TEXT, 1);
	sui_native_text([p_x + panw - pad - KC_TextW("Esc closes", 7 * sc), p_y + 8 * sc, 0],
	                "Esc closes", 7 * sc, SUI_THEME_MUTED, 1);
	segw = 44 * sc;
	h = 13 * sc;
	x = p_x + pad + KC_TextW("Key configuration", 10 * sc) + 10 * sc;
	sui_roundbox([x, p_y + 4 * sc, 0], [segw * 2, h, 0], h * 0.5, SUI_THEME_WELL, 1);
	t = -1;
	if (KC_Seg("kc_tab0", [x, p_y + 4 * sc, 0], [segw, h, 0], "Actions", kc_tab == KC_TAB_ROWS, sc))
		t = KC_TAB_ROWS;
	if (KC_Seg("kc_tab1", [x + segw, p_y + 4 * sc, 0], [segw, h, 0], "Keyboard", kc_tab == KC_TAB_KEYS, sc))
		t = KC_TAB_KEYS;
	return t;
};

// An action in the Keyboard tab's list: a click picks it, a second click lets it go.
void(float i, vector pos, float w, float rh, float sc) KC_KbAction =
{
	local string id, k;
	local float hot, on, ty;
	local vector glyph;

	id = sprintf("kc_ar%g", i);
	sui_action_element(pos, [w, rh, 0], id, sui_noop);
	hot = sui_is_hovered(id);
	on = (kc_sel == i);
	if (hot)
		kc_kb_hovrow = i;
	if (on)
		sui_roundbox(pos, [w, rh, 0], 2 * sc, SUI_THEME_SELECTED, 1);
	else if (sui_is_held(id))
		sui_roundbox(pos, [w, rh, 0], 2 * sc, SUI_THEME_PRESSED, 1);
	else if (hot)
		sui_roundbox(pos, [w, rh, 0], 2 * sc, SUI_THEME_HOVER, 1);
	glyph = sui_native_text_size(7 * sc);
	ty = pos_y + (rh - glyph_y) * 0.5;
	sui_native_text([pos_x + 3 * sc, ty, 0], kc_kb_rl[i], 7 * sc, (on || hot) ? SUI_THEME_TEXT : SUI_THEME_DIM, 1);
	k = kc_kb_rk[i];
	if (k == "")
		sui_native_text([pos_x + KC_KB_LABW * sc, ty, 0], "-", 7 * sc, SUI_THEME_MUTED, 1);
	else
		sui_native_text([pos_x + KC_KB_LABW * sc, ty, 0], k, 7 * sc, on ? SUI_THEME_ACCENT : SUI_THEME_TEXT, 1);
	if (sui_is_released(id))
		kc_sel = on ? -1 : i;
};

// Cap c of the drawing at origin o, u a key unit: face top left, its bind under it.
void(float c, vector o, float u, float sc) KC_Cap =
{
	local float b, code, row, hot, on, edged, lh;
	local vector pos, sz, fill, fg, lc, edge, glyph;
	local string id, t;

	b = c * KC_KB_F;
	code = kc_kbf[b + 4];
	row = kc_kbf[b + 5];
	pos = [o_x + kc_kbf[b] * u, o_y + kc_kbf[b + 1] * u, 0];
	sz = [kc_kbf[b + 2] * u - 1.5 * sc, kc_kbf[b + 3] * u - 1.5 * sc, 0];
	id = sprintf("kc_kb%g", c);
	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	if (hot)
		kc_kb_hov = code;
	on = FALSE;
	if (row >= 0)
	if (row == kc_sel)
		on = TRUE;
	if (kc_sel == KC_CUSTOM)
		on = kc_kbf[b + 7];

	fill = SUI_THEME_CHIP;
	lc = SUI_THEME_DIM;
	fg = (row >= 0) ? SUI_THEME_TEXT : SUI_THEME_DIM;
	if (on)
	{
		fill = SUI_THEME_ACCENT;
		lc = SUI_THEME_WELL;
		fg = SUI_THEME_WELL;
	}
	else
	{
		if (!kc_kbf[b + 6] || code == K_ESCAPE)
		{
			fill = SUI_THEME_WELL;
			lc = SUI_THEME_MUTED;
			fg = SUI_THEME_MUTED;
		}
		if (sui_is_held(id))
			fill = SUI_THEME_PRESSED;
		else if (hot)
			fill = SUI_THEME_HOVER;
	}
	edged = TRUE;
	edge = SUI_THEME_EDGE_HI;
	if (hot)
	{
		if (on)
			edge = SUI_THEME_TEXT;
	}
	else if (code == kc_kb_key)
		edge = SUI_THEME_FOCUS;
	else if (row >= 0 && row == kc_kb_hovrow)
		edge = SUI_THEME_ACCENT;    // the action under the pointer in the list
	else
		edged = FALSE;
	if (edged)
		sui_style_box(pos, sz, 2 * sc, fill, edge, 1);
	else
		sui_roundbox(pos, sz, 2 * sc, fill, 1);

	glyph = sui_native_text_size(6 * sc);
	lh = glyph_y;
	sui_native_text([pos_x + 2 * sc, pos_y + 1.5 * sc, 0], kc_kbs[c * KC_KB_S + 1], 6 * sc, lc, 1);
	t = kc_kbs[c * KC_KB_S + 2];
	if (t != "")
	if (1.5 * sc + lh * 2 <= sz_y)
	{
		sui_native_text([pos_x + 2 * sc, pos_y + 1.5 * sc + lh, 0], t, 6 * sc, fg, 1);
		t = kc_kbs[c * KC_KB_S + 3];
		if (t != "")
		if (1.5 * sc + lh * 3 <= sz_y)
			sui_native_text([pos_x + 2 * sc, pos_y + 1.5 * sc + lh * 2, 0], t, 6 * sc, fg, 1);
	}
	if (sui_is_clicked(id))         // released over this cap: a press dragged away binds nothing
		KC_KeyClick(code);
};

// A key off the drawing (Keys for, the strip). -> released.
float(string id, vector pos, vector sz, string label, float code, float on, float sc) KC_KbChip =
{
	local float hot;
	local vector glyph, fill;

	sui_action_element(pos, sz, id, sui_noop);
	hot = sui_is_hovered(id);
	if (hot)
	if (KC_KeyOk(code))
		kc_kb_hov = code;
	fill = on ? SUI_THEME_ACCENT : SUI_THEME_CHIP;
	if (hot)
		sui_style_box(pos, sz, 2.5 * sc, fill, on ? SUI_THEME_TEXT : SUI_THEME_EDGE_HI, 1);
	else
		sui_roundbox(pos, sz, 2.5 * sc, fill, 1);
	glyph = sui_native_text_size(7 * sc);
	sui_native_text([pos_x + 4 * sc, pos_y + (sz_y - glyph_y) * 0.5, 0], label, 7 * sc,
	                on ? SUI_THEME_WELL : SUI_THEME_TEXT, 1);
	return sui_is_clicked(id);
};

// Bound keys the drawing has no cap for (joystick, aux, Mouse 6+...), as many as fit.
void(vector pos, float w, float sc) KC_KbStrip =
{
	local float i, x, cw, code, row, ty;
	local string lab;
	local vector glyph;

	glyph = sui_native_text_size(7 * sc);
	ty = pos_y + (11 * sc - glyph_y) * 0.5;
	lab = "Bound, but not on this keyboard:";
	sui_native_text([pos_x, ty, 0], lab, 7 * sc, SUI_THEME_MUTED, 1);
	x = pos_x + KC_TextW(lab, 7 * sc) + 6 * sc;
	if (!kc_ks_all)
	{
		sui_native_text([x, ty, 0], "none", 7 * sc, SUI_THEME_MUTED, 1);
		return;
	}
	for (i = 0; i < kc_ks_n; i = i + 1)
	{
		cw = kc_ksq[i * KC_KS_F + 1];
		if (x + cw > pos_x + w - 34 * sc)
			break;
		code = kc_ksq[i * KC_KS_F];
		row = kc_ksq[i * KC_KS_F + 2];
		if (KC_KbChip(sprintf("kc_ks%g", i), [x, pos_y, 0], [cw, 11 * sc, 0], kc_kss[i], code,
		              (kc_sel == KC_CUSTOM) ? kc_ksq[i * KC_KS_F + 3] : (row >= 0 && row == kc_sel), sc))
			KC_KeyClick(code);
		x = x + cw + 3 * sc;
	}
	if (i < kc_ks_all)
		sui_native_text([x, ty, 0], sprintf("+%g more", kc_ks_all - i), 7 * sc, SUI_THEME_MUTED, 1);
};

// What the info box shows for a key, read again when the key, the binds or the scale change.
void(float key, float w, float sc) KC_KbInfoRead =
{
	local string b, n, as;
	local float l;

	if (key == kc_ki_key && kc_ki_gen == kc_gen && kc_ki_w == w && kc_ki_font == ui_font_gen
	    && kc_ki_px == sui_style_pixel_ratio)
		return;
	kc_ki_key = key;
	kc_ki_gen = kc_gen;
	kc_ki_w = w;
	kc_ki_font = ui_font_gen;
	kc_ki_px = sui_style_pixel_ratio;
	n = keynumtostring(key);
	b = getkeybind(key);
	as = "";
	if (b == "")
	{
		l = KC_LeftOf(key);
		if (KC_KeyOk(l))
		{
			b = getkeybind(l);
			as = strcat("as ", KC_KeyLabel(keynumtostring(l)), ": ");
		}
	}
	kc_ki_row = KC_RowOf(b);
	kc_ki_name = KC_Rezone(kc_ki_name, n);
	kc_ki_cap = KC_Rezone(kc_ki_cap, KC_CapLabel(n));
	kc_ki_capw = KC_TextW(kc_ki_cap, 7 * sc);
	if (b != "")
		b = strcat(as, "\"", b, "\"");
	b = KC_Fit(b, w, 7 * sc, 2);
	kc_ki_l1 = KC_Rezone(kc_ki_l1, b);
	kc_ki_l2 = KC_Rezone(kc_ki_l2, kc_fit2);
};

// The legend on one line: picked, bound to something else, unbound.
void(vector pos, float sc) KC_Legend =
{
	local float s, ty;
	local vector glyph;

	glyph = sui_native_text_size(7 * sc);
	s = 7 * sc;
	ty = pos_y + (10 * sc - glyph_y) * 0.5;
	sui_roundbox([pos_x, pos_y + 1.5 * sc, 0], [s, s, 0], 1.5 * sc, SUI_THEME_ACCENT, 1);
	sui_native_text([pos_x + s + 3 * sc, ty, 0], "picked", 7 * sc, SUI_THEME_DIM, 1);
	pos_x = pos_x + s + 3 * sc + KC_TextW("picked", 7 * sc) + 8 * sc;
	sui_roundbox([pos_x, pos_y + 1.5 * sc, 0], [s, s, 0], 1.5 * sc, SUI_THEME_CHIP, 1);
	sui_native_text([pos_x + s + 3 * sc, ty, 0], "bound elsewhere", 7 * sc, SUI_THEME_DIM, 1);
	pos_x = pos_x + s + 3 * sc + KC_TextW("bound elsewhere", 7 * sc) + 8 * sc;
	sui_style_box([pos_x, pos_y + 1.5 * sc, 0], [s, s, 0], 1.5 * sc, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	sui_native_text([pos_x + s + 3 * sc, ty, 0], "unbound", 7 * sc, SUI_THEME_DIM, 1);
};

// P1400: a one-line text field (which: KC_FLD_CMD or KC_FLD_EDIT), scrolled to its caret.
void(float which, vector pos, vector sz, string hint, float sc) KC_FieldDraw =
{
	local vector glyph, tp;
	local float on, tw, room, scroll;
	local string was, t;

	glyph = sui_native_text_size(7 * sc);
	on = (kc_fld == which);
	sui_style_box(pos, sz, 2.5 * sc, SUI_THEME_WELL, on ? SUI_THEME_ACCENT : SUI_THEME_EDGE, 1);
	room = sz_x - 6 * sc;
	if (which == KC_FLD_CMD)
	{
		kc_cf_p = pos;
		kc_cf_s = sz;
		tw = KC_TextW(substring(kc_ctext, 0, kc_ccaret), 7 * sc);
		scroll = max(0, tw - room);
		sui_text_metrics(3 * sc - scroll, glyph);
		was = kc_ctext;
		sui_text_input("kc_cf", pos, sz, kc_ctext, kc_ccaret);
		kc_ctext = KC_Rezoned(was, kc_ctext);
		t = kc_ctext;
		tw = KC_TextW(substring(t, 0, kc_ccaret), 7 * sc);
	}
	else
	{
		kc_ef_p = pos;
		kc_ef_s = sz;
		tw = KC_TextW(substring(kc_etext, 0, kc_ecaret), 7 * sc);
		scroll = max(0, tw - room);
		sui_text_metrics(3 * sc - scroll, glyph);
		was = kc_etext;
		sui_text_input("kc_ef", pos, sz, kc_etext, kc_ecaret);
		kc_etext = KC_Rezoned(was, kc_etext);
		t = kc_etext;
		tw = KC_TextW(substring(t, 0, kc_ecaret), 7 * sc);
	}
	tp = [pos_x + 3 * sc, pos_y + (sz_y - glyph_y) * 0.5, 0];
	drawsetcliparea(tp_x, pos_y, room + 1, sz_y);
	if (t == "" && !on)
		sui_native_text(tp, hint, 7 * sc, SUI_THEME_MUTED, 1);
	else
		sui_native_text(tp - [scroll, 0, 0], t, 7 * sc, SUI_THEME_TEXT, 1);
	if (on)
		drawfill(tp + [tw - scroll, -1, 0], [1, glyph_y + 2, 0], SUI_THEME_ACCENT, 1, 0);
	drawresetcliparea();
};

// The right column: Your own command, the pick's keys, the key under the pointer with Edit
// and Clear, the legend. Drawn after the caps so it reads this frame's kc_kb_hov.
void(vector pos, float w, float sc) KC_KbInfo =
{
	local float i, x, y, line, code, cw, key, ch, sel, n, bx, dim;
	local string k, lab, keys;
	local vector glyph, c;

	glyph = sui_native_text_size(7 * sc);
	ch = 11 * sc;
	sel = kc_sel;
	KC_Heading(pos, w, "Your own command", sc);
	KC_FieldDraw(KC_FLD_CMD, [pos_x, pos_y + 13 * sc, 0], [w, 12 * sc, 0], "type a command, then Enter", sc);

	y = pos_y + 30 * sc;
	keys = "";
	n = 0;
	if (sel == KC_CUSTOM)
	{
		KC_Heading([pos_x, y, 0], w, KC_Fit(strcat("Keys for ", kc_cmd), w, 7 * sc, 1), sc);
		keys = kc_ckeys;
		n = kc_ccnt;
	}
	else if (sel >= 0)
	{
		KC_Heading([pos_x, y, 0], w, strcat("Keys for ", KC_F(sel, 1)), sc);
		keys = kc_keys[sel];
		n = kc_cnt[sel];
	}
	else
		KC_Heading([pos_x, y, 0], w, "Keys for an action", sc);
	x = pos_x;
	y = y + 13 * sc;
	line = 0;
	for (i = 0; i < n; i = i + 1)
	{
		k = Gfx_Field(keys, i, " ");
		lab = KC_KeyLabel(k);
		cw = KC_TextW(lab, 7 * sc) + 8 * sc;
		if (x + cw > pos_x + w)
		{
			if (line)
				break;
			line = 1;
			x = pos_x;
			y = y + ch + 2 * sc;
		}
		code = stringtokeynum(k);
		if (KC_KbChip(sprintf("kc_kf%g", i), [x, y, 0], [cw, ch, 0], lab, code, TRUE, sc))
		if (KC_KeyOk(code))
			kc_kb_key = code;
		x = x + cw + 3 * sc;
	}
	if (sel == -1)
		sui_native_text([pos_x, y + (ch - glyph_y) * 0.5, 0],
		                "Pick an action, then click keys to place it.", 7 * sc, SUI_THEME_MUTED, 1);
	else if (!n)
		sui_native_text([pos_x, y + (ch - glyph_y) * 0.5, 0], "No key yet: click one below.", 7 * sc,
		                SUI_THEME_MUTED, 1);

	y = pos_y + 71 * sc;
	KC_Heading([pos_x, y, 0], w, "Selected key", sc);
	y = y + 13 * sc;
	sui_roundbox([pos_x, y, 0], [w, 50 * sc, 0], 3 * sc, SUI_THEME_WELL, 1);
	// Edit and Clear act on the key last clicked: the pointer is on them, not on a key.
	bx = pos_x + w - 63 * sc;
	dim = (!KC_KeyOk(kc_kb_key) || KC_IsKept(kc_kb_key) || kc_fld == KC_FLD_EDIT);
	if (KC_Button("kc_edit", [bx, y + 2 * sc, 0], [30 * sc, 11 * sc, 0], "Edit",
	              dim ? SUI_THEME_WELL : SUI_THEME_CHIP, dim ? SUI_THEME_MUTED : SUI_THEME_DIM, sc))
		KC_EditBegin(kc_kb_key);
	if (KC_Button("kc_clr", [bx + 32 * sc, y + 2 * sc, 0], [30 * sc, 11 * sc, 0], "Clear",
	              dim ? SUI_THEME_WELL : SUI_THEME_CHIP, dim ? SUI_THEME_MUTED : SUI_THEME_DIM, sc))
	{
		if (KC_KeyOk(kc_kb_key))
			KC_ClearKey(kc_kb_key);
		else
			KC_Say("click a key first");
	}
	x = pos_x + 4 * sc;
	y = y + 3 * sc;
	key = kc_kb_hov;
	if (!KC_KeyOk(key))
		key = kc_kb_key;
	if (kc_fld == KC_FLD_EDIT)
		key = kc_ekey;
	kc_ef_s = '0 0 0';
	if (!KC_KeyOk(key))
		sui_native_text([x, y, 0], "Point at a key to read its bind.", 7 * sc, SUI_THEME_MUTED, 1);
	else
	{
		KC_KbInfoRead(key, w - 8 * sc, sc);
		sui_native_text([x, y, 0], kc_ki_cap, 7 * sc, SUI_THEME_TEXT, 1);
		if (strcmp(kc_ki_cap, kc_ki_name))
			sui_native_text([x + kc_ki_capw + 5 * sc, y, 0], kc_ki_name, 7 * sc, SUI_THEME_MUTED, 1);
		y = y + 10 * sc;
		c = SUI_THEME_MUTED;
		if (kc_fld == KC_FLD_EDIT)
		{
			lab = "Enter binds it, empty clears, Esc cancels";
			c = SUI_THEME_FOCUS;
		}
		else if (key == K_ESCAPE)
			lab = "the menu key: not placed here";
		else if (kc_ki_row >= 0)
		{
			lab = sprintf("%s, from the list", KC_F(kc_ki_row, 1));
			c = SUI_THEME_ACCENT;
		}
		else if (kc_ki_l1 != "")
		{
			lab = "not one of the listed actions";
			c = SUI_THEME_DIM;
		}
		else
			lab = "unbound";
		sui_native_text([x, y, 0], lab, 7 * sc, c, 1);
		y = y + 10 * sc;
		if (kc_fld == KC_FLD_EDIT)
			KC_FieldDraw(KC_FLD_EDIT, [x - 2 * sc, y, 0], [w - 4 * sc, 12 * sc, 0], "", sc);
		else
		{
			if (kc_ki_l1 != "")
				sui_native_text([x, y, 0], kc_ki_l1, 7 * sc, SUI_THEME_WARN, 1);
			if (kc_ki_l2 != "")
				sui_native_text([x, y + 10 * sc, 0], kc_ki_l2, 7 * sc, SUI_THEME_WARN, 1);
		}
	}
	KC_Legend([pos_x, pos_y + 140 * sc, 0], sc);
};

// The Keyboard tab (Patch 1392). KC_Draw has done the closing checks and the bind read.
void(vector scr) KC_DrawKeys =
{
	local float sc, fit, pad, u, panw, panh, rh, x, y, top, i, tab, done, bw;
	local vector p, o, footc;
	local string foot;

	sc = ui_cv_scale;
	if (sc <= 0) sc = 2;
	// Fitted as KC_Draw does, but under 1 rather than off a small screen.
	fit = min(scr_x * 0.96 / KC_KB_PW, scr_y * 0.96 / KC_KB_PH);
	if (sc > fit)
	{
		if (fit >= 1)
			sc = floor(fit * 2) / 2;
		else
			sc = fit;
	}
	pad  = 8 * sc;
	u    = KC_KB_U * sc;
	rh   = 10 * sc;
	panw = KC_KB_PW * sc;
	panh = KC_KB_PH * sc;
	p = [floor((scr_x - panw) * 0.5), floor((scr_y - panh) * 0.5), 0];
	kc_kb_hov = 0;
	kc_kb_hovrow = -1;

	sui_begin(scr_x, scr_y);
	Font_Set(ui_font_ui);
	KC_KbCache(sc);
	sui_fill('0 0 0', [scr_x, scr_y, 0], '0 0 0', 0.35, 0);
	sui_action_element(p, [panw, panh, 0], "kc_panel", sui_noop);
	sui_style_panel(p, [panw, panh, 0], 7 * sc, 1);
	tab = KC_Header(p, panw, pad, sc);
	top = p_y + 24 * sc;

	// The actions in the Actions tab's three columns and order.
	y = top;
	x = p_x + pad;
	for (i = 0; i < KC_N; i = i + 1)
	{
		if (i == KC_COL1 || i == KC_COL2)
		{
			x = x + (KC_KB_COLW + 12) * sc;
			y = top;
		}
		if (KC_NewGroup(i))
		{
			KC_Heading([x, y, 0], KC_KB_COLW * sc, KC_F(KC_Order(i), 5), sc);
			y = y + 12 * sc;
		}
		KC_KbAction(KC_Order(i), [x, y, 0], KC_KB_COLW * sc, rh, sc);
		y = y + rh;
	}

	o = [p_x + pad, top + 172 * sc, 0];
	for (i = 0; i < kc_kb_n; i = i + 1)
		KC_Cap(i, o, u, sc);
	y = o_y + KC_KB_UH * u + 4 * sc;
	KC_KbStrip([p_x + pad, y, 0], panw - pad * 2, sc);
	KC_KbInfo([p_x + pad + (KC_KB_COLW * 3 + 36) * sc, top, 0], KC_KB_INFW * sc, sc);

	y = y + 17 * sc;
	bw = 64 * sc;
	done = KC_Button("kc_done", [p_x + panw - pad - bw, y, 0], [bw, 12 * sc, 0], "done",
	                 SUI_THEME_SELECTED, SUI_THEME_TEXT, sc);
	if (kc_status != "" && cltime - kc_statusat < KC_STATUS_T)
	{
		foot = kc_status;
		footc = SUI_THEME_GOOD;
	}
	else if (kc_fld)
	{
		foot = "typing: Enter takes it, Esc leaves the box";
		footc = SUI_THEME_FOCUS;
	}
	else if (kc_sel == KC_CUSTOM)
	{
		foot = sprintf("click a key to bind \"%s\" to it   right-click a key clears it   click an action to go back", kc_cmd);
		footc = SUI_THEME_FOCUS;
	}
	else if (kc_sel >= 0)
	{
		foot = sprintf("click a key to put %s on it   right-click a key clears it   click the action again to let go",
		               KC_F(kc_sel, 1));
		footc = SUI_THEME_FOCUS;
	}
	else
	{
		foot = "pick an action, then click keys to place it   right-click a key clears it";
		footc = SUI_THEME_MUTED;
	}
	sui_native_text([p_x + pad, y + 2 * sc, 0], KC_Fit(foot, panw - pad * 2 - bw - 8 * sc, 7 * sc, 1), 7 * sc,
	                footc, 1);

	sui_end();
	Font_Reset();
	if (tab >= 0)
		KC_SetTab(tab);
	if (done)
		KC_Close();
};

void(vector scr) KC_Draw =
{
	local float sc, fit, pad, rh, labw, chipw, colw, gap, panw, panh, y, y0, i, done, bw, tab;
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
	kc_hov_i = -1;
	kc_hov_slider = 0;
	if (kc_tab == KC_TAB_KEYS)
	{
		KC_DrawKeys(scr);
		return;
	}
	kc_kb_hov = 0;

	sc = ui_cv_scale;
	if (sc <= 0) sc = 2;
	fit = min(scr_x * 0.96 / 568, scr_y * 0.96 / 288);   // P1400: three columns (568 wide)
	if (sc > fit)
		sc = max(1, floor(fit * 2) / 2);

	pad   = 8 * sc;
	rh    = 13 * sc;
	labw  = 70 * sc;
	chipw = 44 * sc;
	colw  = labw + 2 * chipw + 6 * sc + 12 * sc;
	gap   = 12 * sc;
	panw  = pad * 2 + colw * 3 + gap * 2;
	panh  = 6 * sc + 18 * sc + 18 * rh + 4 * sc + rh + 2 * sc + 4 * sc + 10 * sc + 6 * sc;
	p = [floor((scr_x - panw) * 0.5), floor((scr_y - panh) * 0.5), 0];

	sui_begin(scr_x, scr_y);
	Font_Set(ui_font_ui);
	sui_fill('0 0 0', [scr_x, scr_y, 0], '0 0 0', 0.35, 0);
	sui_action_element(p, [panw, panh, 0], "kc_panel", sui_noop);
	sui_style_panel(p, [panw, panh, 0], 7 * sc, 1);

	tab = KC_Header(p, panw, pad, sc);
	y = p_y + 24 * sc;
	y0 = y;

	// Columns: movement and menus; saves, the run and turning; tools and game keys.
	c0 = [p_x + pad, 0, 0];
	c1 = [p_x + pad + colw + gap, 0, 0];
	for (i = 0; i < KC_COL1; i = i + 1)
		y = KC_ColumnRow(i, c0, y, labw, chipw, colw, rh, sc);
	y = y0;
	for (i = KC_COL2; i < KC_N; i = i + 1)
		y = KC_ColumnRow(i, c1 + [colw + gap, 0, 0], y, labw, chipw, colw, rh, sc);
	y = y0;
	for (i = KC_COL1; i < KC_COL2; i = i + 1)
		y = KC_ColumnRow(i, c1, y, labw, chipw, colw, rh, sc);
	KC_Heading([c1_x, y, 0], colw, "Turning and mouse", sc);
	y = y + rh;
	KC_Slider(1, [c1_x, y, 0], labw, colw, rh, sc);
	y = y + rh;
	KC_Slider(2, [c1_x, y, 0], labw, colw, rh, sc);

	y = y0 + 18 * rh + 4 * sc;
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
	if (tab >= 0)
		KC_SetTab(tab);
	if (done)
		KC_Close();
};

void(float sc, float lsz, vector scr) KC_HintMeasure =
{
	local float i, cap, gap, sw;
	local string it, k, lab;

	if (!kc_hl)
	{
		kc_hl = memalloc(sizeof(float) * KC_HINTS * 3);
		kc_hs = memalloc(sizeof(string) * KC_HINTS * 2);
	}
	for (i = 0; i < kc_hl_n; i = i + 1)
	{
		strunzone(kc_hs[i * 2]);
		strunzone(kc_hs[i * 2 + 1]);
	}
	cap = 11 * sc - 3 * sc;
	gap = 6 * sc;
	kc_hl_w = 3 * sc;
	for (i = 0; i < KC_HINTS; i = i + 1)
	{
		it = Gfx_Field(kc_hint, i, ";");
		if (it == "")
			break;
		k = Gfx_Field(it, 0, "|");
		lab = Gfx_Field(it, 1, "|");
		sw = stringwidth(k, TRUE, [lsz, lsz]);
		kc_hl[i * 3] = max(cap, sw + 4 * sc);
		kc_hl[i * 3 + 1] = (kc_hl[i * 3] - sw) * 0.5;
		kc_hl[i * 3 + 2] = stringwidth(lab, TRUE, [lsz, lsz]);
		kc_hs[i * 2] = strzone(k);
		kc_hs[i * 2 + 1] = strzone(lab);
		kc_hl_w = kc_hl_w + kc_hl[i * 3] + 3 * sc + kc_hl[i * 3 + 2] + gap;
	}
	kc_hl_n = i;
	kc_hl_w = kc_hl_w - gap + 4 * sc;
	kc_hl_at = kc_cacheat;
	kc_hl_sc = sc;
	kc_hl_lsz = lsz;
	kc_hl_scr = [scr_x, scr_y, sui_style_pixel_ratio_y];
	kc_hl_rx = sui_style_pixel_ratio_x;
	kc_hl_font = ui_font_gen;
};

#ifdef P863CHECK
// The strip as it was drawn before Patch 863, for the paused pixel A/B (p863_olddraw 1).
void(vector scr) KC_HintDrawOld =
{
	local float sc, n, i, x, h, cap, lsz, kw, lw, w, gap;
	local string it, k, lab;
	local vector p;

	sc  = ui_cv_scale;
	Font_Set(ui_font_ui);
	lsz = Font_Px(7 * sc);
	h   = 11 * sc;
	cap = h - 3 * sc;
	gap = 6 * sc;
	n = KC_HINTS;
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

	// The layout cache's numbers, as this frame works them out.
	p863_kc_n += 1;
	if (w != kc_hl_w || i != kc_hl_n)
		p863_kc_bad += 1;
	for (i = 0; i < kc_hl_n; i = i + 1)
	{
		it = Gfx_Field(kc_hint, i, ";");
		k = Gfx_Field(it, 0, "|");
		lab = Gfx_Field(it, 1, "|");
		kw = max(cap, stringwidth(k, TRUE, [lsz, lsz]) + 4 * sc);
		if (kw != kc_hl[i * 3] || (kw - stringwidth(k, TRUE, [lsz, lsz])) * 0.5 != kc_hl[i * 3 + 1]
		    || stringwidth(lab, TRUE, [lsz, lsz]) != kc_hl[i * 3 + 2]
		    || k != kc_hs[i * 2] || lab != kc_hs[i * 2 + 1])
			p863_kc_bad += 1;
	}
	if (!cvar("p863_olddraw"))
	{
		Font_Reset();
		return;
	}

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
#endif

/*
  The strip along the bottom left: the key each menu and gesture is on, read
  from the binds, so it shows the player's own keys. Unbound items are left out.
  Patch 863: every chip, then every word, so the strip is three GL draws, not two an
  item. No chip touches another item's words, so the order changes no pixel.
*/
void(vector scr) KC_HintDraw =
{
	local float sc, i, x, h, cap, lsz, gap, ty;
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
	if (kc_hl_at != kc_cacheat || kc_hl_sc != sc || kc_hl_lsz != lsz
	    || kc_hl_scr != [scr_x, scr_y, sui_style_pixel_ratio_y] || kc_hl_rx != sui_style_pixel_ratio_x
	    || kc_hl_font != ui_font_gen)
		KC_HintMeasure(sc, lsz, scr);
#ifdef P863CHECK
	KC_HintDrawOld(scr);
	if (cvar("p863_olddraw"))
		return;
	Font_Set(ui_font_ui);
#endif

	p = [scr_x * cvar("hud_keyhint_x"), scr_y * cvar("hud_keyhint_y"), 0];
	_sui_round_draw(p, [kc_hl_w, h, 0], 4 * sc, SUI_THEME_PANEL, 0.75);
	ty = p_y + (h - lsz) * 0.5 + lsz * FONT_CAPDROP;   // P1221: capitals centred on the chip
	x = p_x + 3 * sc;
	// Under 6 pixels between items a glyph's edge, or the fallback font's shadow and ring,
	// could reach the next chip: then each item whole, in the old order.
	if (gap * sui_style_pixel_ratio_x < 6)
	{
		for (i = 0; i < kc_hl_n; i = i + 1)
		{
			_sui_round_draw([x, p_y + 1.5 * sc, 0], [kc_hl[i * 3], cap, 0], 2 * sc, SUI_THEME_CHIP, 1);
			HUD_TextDraw([x + kc_hl[i * 3 + 1], ty], kc_hs[i * 2], lsz, SUI_THEME_TEXT, 1);
			x = x + kc_hl[i * 3] + 3 * sc;
			HUD_TextDraw([x, ty], kc_hs[i * 2 + 1], lsz, SUI_THEME_DIM, 1);
			x = x + kc_hl[i * 3 + 2] + gap;
		}
		Font_Reset();
		HUD_Rect("keyhint", p, [kc_hl_w, h, 0], p);
		return;
	}
	for (i = 0; i < kc_hl_n; i = i + 1)
	{
		_sui_round_draw([x, p_y + 1.5 * sc, 0], [kc_hl[i * 3], cap, 0], 2 * sc, SUI_THEME_CHIP, 1);
		x = x + kc_hl[i * 3] + 3 * sc;
		x = x + kc_hl[i * 3 + 2] + gap;
	}
	x = p_x + 3 * sc;
	for (i = 0; i < kc_hl_n; i = i + 1)
	{
		HUD_TextDraw([x + kc_hl[i * 3 + 1], ty], kc_hs[i * 2], lsz, SUI_THEME_TEXT, 1);
		x = x + kc_hl[i * 3] + 3 * sc;
		HUD_TextDraw([x, ty], kc_hs[i * 2 + 1], lsz, SUI_THEME_DIM, 1);
		x = x + kc_hl[i * 3 + 2] + gap;
	}
	Font_Reset();
	HUD_Rect("keyhint", p, [kc_hl_w, h, 0], p);
};
