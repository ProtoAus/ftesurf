/*
===========================================================================
  cl_vote.qc -- the vote box.  Patch 372.

  Drawn on the left in gfx_menu's look while the server runs a vote
  (serverinfo "vote" and friends, grammar in sh_defs.qc; sv_vote.qc writes
  them).  Digits 1..n pick and 0 hides -- but only while the box is asking:
  from VOTE_ARM after it opens until you pick (plus VOTE_GRACE, so a double tap
  re-picks rather than loading a save), and again after a bare `vote`.  The
  rest of the time the digits stay SaveLoc's and gfx's: players bind 1 and 2
  to save and load, and a vote must not eat those.
===========================================================================
*/
#define VOTE_ARM    0.75        // a press already on its way when the box appears goes where it was aimed
#define VOTE_GRACE  0.5
#define VOTE_STALE  120         // an end further off than any vote runs: the last map's key

float vt_on, vt_id, vt_kind, vt_end, vt_n, vt_seen;
float vt_shown;                 // up; a new vote raises it, 0 or `vote` lowers it
float vt_pick;                  // our pick in this vote, 0 none (*vpick confirms it)
float vt_rearm;                 // `vote` after a pick: the digits are live again
float vt_castat;
float vt_kheld, vt_kmine, vt_krep, vt_klast;   // digit bits: down, taken by us; this press repeats
vector vt_box;                  // the box last drawn: x0, x1, bottom y (bottom 0 = not drawn)
float  vt_boxtop;

void() Vote_RegisterCvars =
{
	registercvar("hud_vote_x", "0.018", CVAR_ARCHIVE);
	registercvar("hud_vote_y", "0.30",  CVAR_ARCHIVE);
	registercommand("vote");
	vt_id = -1;
};

// Gfx_Field splits without tokenize, so a caller's argv survives.
void() Vote_Sync =
{
	local string s;
	local float id, n;

	vt_on = FALSE;
	s = HUD_SK("vote");
	if (s == "")
		return;
	id = stof(Gfx_Field(s, 0, " "));
	vt_kind = stof(Gfx_Field(s, 1, " "));
	vt_end  = stof(Gfx_Field(s, 2, " "));
	n       = stof(Gfx_Field(s, 3, " "));
	if (n > VOTE_MAX)
		n = VOTE_MAX;
	if (n < 1 || vt_end - time > VOTE_STALE)
		return;
	vt_n  = n;
	vt_on = TRUE;
	if (id != vt_id)
	{
		vt_id    = id;
		vt_pick  = 0;
		vt_rearm = FALSE;
		vt_shown = TRUE;
		vt_seen  = cltime;
	}
	// The server's copy of our pick, once a local press has had time to reach it.
	s = getplayerkeyvalue(player_localnum, "*vpick");
	if (s != "")
	if (stof(Gfx_Field(s, 0, " ")) == vt_id)
	if (cltime - vt_castat > 1)
		vt_pick = stof(Gfx_Field(s, 1, " "));
};

float() Vote_Spectating =
{
	return getplayerkeyvalue(player_localnum, "*spectator") == "1";
};

float() Vote_Capturing =
{
	if (!vt_on || !vt_shown || vt_end <= time || isdemo())
		return FALSE;
	if (cltime - vt_seen < VOTE_ARM || rec_sl_holding || Vote_Spectating())
		return FALSE;
	return !vt_pick || vt_rearm || cltime - vt_castat < VOTE_GRACE;
};

string() Vote_Title =
{
	if (vt_kind == VOTE_EXTEND)
		return "Vote: extend this map?";
	if (vt_kind == VOTE_RTV)
		return "Vote: change map";
	return "Vote: next map";
};

// One press of digit d, from a key or from `vote <d>`: 0 hides, 1..n picks.
void(float d, string via) Vote_Press =
{
	if (!vt_on)
	{
		print("vote: no vote running\n");
		return;
	}
	if (d == 0)
	{
		vt_shown = FALSE;
		vt_rearm = FALSE;
		return;
	}
	if (d < 1 || d > vt_n)
	{
		print(sprintf("vote: pick 1..%g\n", vt_n));
		return;
	}
	if (vt_end <= time || isdemo() || Vote_Spectating())
	{
		print("vote: not now\n");
		return;
	}
	vt_pick   = d;
	vt_rearm  = FALSE;
	vt_castat = cltime;
	localcmd(sprintf("cmd vote_cast %g %g\n", d, vt_id));
	print(sprintf("vote: you picked %g, %s (vote %g, %s)\n", d,
	              HUD_SK(sprintf("vote%g", d)), vt_id, via));
};

// '0'..'9' -> 0..9, the keypad (K_KP_INS 157 .. K_KP_PGUP 166) -> 10..19, else -1.
float(float scan) Vote_Slot =
{
	if (scan >= '0' && scan <= '9')
		return scan - '0';
	if (scan >= K_KP_INS && scan <= K_KP_PGUP)
		return 10 + scan - K_KP_INS;
	return -1;
};

// An observer, first in CL_InputChain: the chat draft and the panels swallow
// key-ups, and a repeat must be told from a fresh press.
void(float ev, float scan) Vote_Track =
{
	local float s, b;

	if (ev != IE_KEYDOWN && ev != IE_KEYUP)
		return;                         // a mouse event's scanx is a coordinate
	s = Vote_Slot(scan);
	if (s < 0)
		return;
	b = bitshift(1, s);
	if (cltime - vt_klast > 1.1)
		vt_kheld = vt_kmine = 0;            // a release lost to a focus change
	vt_klast = cltime;
	if (ev == IE_KEYDOWN)
	{
		vt_krep  = (vt_kheld & b) != 0;
		vt_kheld = vt_kheld | b;
	}
	else if (ev == IE_KEYUP)
	{
		vt_kheld = vt_kheld - (vt_kheld & b);
		vt_kmine = vt_kmine - (vt_kmine & b);
	}
};

// Key-downs only.  A repeat of a key we took stays ours (2 must not start a
// save-load hold); a key held from before the box asked stays its owner's.
float(float scan) Vote_Key =
{
	local float s, b, d;

	s = Vote_Slot(scan);
	if (s < 0)
		return FALSE;
	b = bitshift(1, s);
	if (vt_kmine & b)
		return TRUE;
	if (vt_krep)
		return FALSE;
	if (!Vote_Capturing())
		return FALSE;
	d = s - 10 * floor(s / 10);
	if (d > vt_n)
		return FALSE;                       // not an option: gfx and SaveLoc keep it
	Vote_Press(d, "key");
	vt_kmine = vt_kmine | b;
	return TRUE;
};

void() Vote_Status =
{
	local float i;
	local string c;

	if (!vt_on)
		print(sprintf("vote: none (time %.1f)\n", time));
	else
	{
		print(sprintf("vote: id %g kind %g n %g left %.1f shown %g pick %g capture %g\n",
		              vt_id, vt_kind, vt_n, vt_end - time, vt_shown, vt_pick, Vote_Capturing()));
		c = HUD_SK("votec");
		for (i = 1; i <= vt_n; i = i + 1)
			print(sprintf("vote:  %g %-22s %s%s\n", i, HUD_SK(sprintf("vote%g", i)),
			              Gfx_Field(c, i - 1, " "), (i == vt_pick) ? "  <- yours" : ""));
	}
	print(sprintf("mapclock: \"%s\" left %.1f row \"%s\" next \"%s\" saves %g\n",
	              HUD_SK("mapclock"), MapClock_Left(), HUD_MapClockText(), HUD_SK("mapnext"),
	              getstatf(STAT_FS_SAVECOUNT)));
};

/*
  `vote`            show the box, or re-arm it after a pick
  `vote <n>`        press digit n (0 hides) -- the same path as the key
  `vote status`     the state, one grep-able line each
  `vote fake clock <secs> <state> | next <map> | open <kind> <secs> <n> |
             label <i> <text> | votec "<c ..>" | off`
                    local serverinfo overrides for harnesses (HUD_SK)
  (`vote key <scan> <0|1>` is cl_main.qc's: it runs the whole input chain.)
*/
float() Vote_Console =
{
	local string a;

	a = argv(1);
	if (a == "status")
	{
		Vote_Status();
		return TRUE;
	}
	if (a == "fake")
	{
		a = argv(2);
		if (a == "off")
			HUD_SKFakeOff();
		else if (a == "clock")
			HUD_SKFake("mapclock", sprintf("%.1f %g", time + stof(argv(3)), stof(argv(4))));
		else if (a == "next")
			HUD_SKFake("mapnext", argv(3));
		else if (a == "open")
			HUD_SKFake("vote", sprintf("%g %g %.1f %g", vt_id + 1, stof(argv(3)),
			                          time + stof(argv(4)), stof(argv(5))));
		else if (a == "label")
			HUD_SKFake(strcat("vote", argv(3)), argv(4));
		else if (a == "votec")
			HUD_SKFake("votec", argv(3));
		else
			print("vote fake clock|next|open|label|votec|off\n");
		return TRUE;
	}
	if (a != "")
	{
		Vote_Press(stof(a), "console");
		return TRUE;
	}
	if (!vt_on)
		print("vote: no vote running\n");
	else if (!vt_shown)
	{
		vt_shown = TRUE;
		vt_rearm = (vt_pick != 0);
	}
	else if (vt_pick && !vt_rearm)
		vt_rearm = TRUE;
	else
		vt_shown = FALSE;
	return TRUE;
};

void(vector scr) Vote_Draw =
{
	local vector p;
	local float w, h, lsz, gap, y, i, left, cap;
	local string c, lab, foot;

	vt_box = '0 0 0';
	if (!vt_on || !vt_shown)
		return;

	Font_Set(ui_font_ui);
	lsz = Font_Px(8 * ui_cv_scale);
	h   = 13 * ui_cv_scale;
	gap = 1 * ui_cv_scale;
	w   = 110 * ui_cv_scale;
	for (i = 1; i <= vt_n; i = i + 1)
		w = max(w, stringwidth(HUD_SK(sprintf("vote%g", i)), TRUE, [lsz, lsz])
		           + stringwidth("000", TRUE, [lsz, lsz]) + h * 2.1);
	w = min(w, scr_x * 0.4);

	p = [scr_x * cvar("hud_vote_x"), scr_y * cvar("hud_vote_y"), 0];
	y = p_y;
	left = max(vt_end - time, 0);
	cap = Vote_Capturing();

	drawfill([p_x, y], [w, h + gap], '0.10 0.13 0.17', 0.85, 0);
	HUD_Text([p_x + h * 0.35, y + (h - lsz) * 0.5], Vote_Title(), lsz, '1 1 1', 1);
	HUD_TextR([p_x + w - h * 0.35, y + (h - lsz) * 0.5], sprintf("%gs", ceil(left)), lsz,
	          (left < 5) ? '1 0.35 0.30' : '1.00 0.90 0.55', 1);
	y = y + h + gap * 2;

	c = HUD_SK("votec");
	for (i = 1; i <= vt_n; i = i + 1)
	{
		lab = HUD_SK(sprintf("vote%g", i));
		if (i == vt_pick)
			drawfill([p_x, y], [w, h], '0.35 0.49 0.67', 1, 0);   // under Gfx_Row's black
		Gfx_Row([p_x, y], w, h, sprintf("%g", i), lab, Gfx_Field(c, i - 1, " "),
		        FALSE, "", lsz);
		y = y + h + gap;
	}

	if (Vote_Spectating())
		foot = "spectating";
	else if (left <= 0)
		foot = "vote closed";
	else if (!vt_pick)
		foot = sprintf("1-%g vote   0 hide", vt_n);
	else if (cap && vt_rearm)
		foot = sprintf("1-%g change vote   0 hide", vt_n);
	else
		foot = "voted -- results in chat";
	y = y + gap * 2;
	HUD_Text([p_x + h * 0.35, y], foot, lsz * 0.9, '0.55 0.58 0.62', 1);
	y = y + lsz;

	Font_Reset();
	HUD_Rect("vote", p, [w, y - p_y, 0], p);
	vt_box = [p_x, p_x + w, y];     // the chatbox stops below it (Chat_Draw, next frame)
	vt_boxtop = p_y;
};
