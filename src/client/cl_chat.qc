/*
===========================================================================
  cl_chat.qc -- the bottom-left chatbox.  Patch 340.

  THE HOOK, AND THE ONE RULE IT COMES WITH.  Defining CSQC_Parse_Print makes
  the engine route EVERY svc_print through it and print NOTHING itself
  (pr_csqc.c:9595 returns true unconditionally once the function exists --
  the QC return value is not read).  So every level this file does not handle
  is a level that vanishes from the console and the log.  Non-chat levels are
  therefore re-emitted with print(), byte for byte, and only level 3
  (PRINT_CHAT, bothdefs.h:1140) becomes a chatbox line.  print() still feeds
  the top-left notify area, and the engine has already played talk.wav by the
  time a chat line gets here (CL_ParseChat, cl_parse.c:6784), silenced or not.

  WHAT A CHAT LINE LOOKS ON ARRIVAL.  CL_PrintChat (cl_parse.c:6900) has
  already formatted it by the time the hook sees it:

      \1^[[^7[^c NAME^d\player\N^]: text\n

  \1 is the chat marker, ^[ ^] are console highlight brackets, \player\N^ is
  the clickable-player escape and N is the player index, ^c is the speaker's
  console colour.  Those escapes belong to the CONSOLE renderer; drawstring's
  parser (COM_ParseFunString) does not know ^[ or \player\, so the line is
  taken apart into (slot, text) and rebuilt rather than blitted.  The name is
  re-read from the slot with getplayerkeyvalue -- the same place the engine
  read it from.

  THE COLOUR RULE IS THE ENGINE'S OWN, mirrored: CL_PlayerColor's non-teamplay
  branch reads the `tc` userinfo key (or hashes the userid when absent) and
  paints the name ^(1 + tc%7).  The server's Lobby_TcOf (sv_lobby.qc) writes
  `tc` from the avatar palette, so a chatbox name is the colour of the body
  standing next to it.  A name carrying its own ^ codes wins, because
  drawstring applies codes left to right over the prefix -- which is what the
  engine's name_coloured flag means too, and what the ask said: "unless the
  player uses their own ^1 ^2 colouring".

  SILENCE IS LOCAL AND IS OURS.  The engine's `ignore` kills a message BEFORE
  this hook (Ignore_Message, cl_parse.c:6718) and its list cannot be read back
  from QC, so the player menu needs a list it can both set and display:
  data/chatsilence.txt, one lowercase name per line, keyed by name because
  that is all a chat line reliably carries.  Silenced means not drawn AND not
  echoed -- the same contract `ignore` has.
===========================================================================
*/

#define CHAT_LVL_PRINT  3       // PRINT_CHAT, bothdefs.h:1140
#define CHAT_RING       32      // messages held; more than fit on screen
#define CHAT_SIL_MAX    32
#define CHAT_NAME_MAX   32
#define CHAT_DRAFT_MAX  128     // typed or prefilled draft characters
#define CHAT_ROWS_MIN   10      // rows the box may use; hud_chat_lines counts messages

string chat_ring[CHAT_RING];    // built display lines, strzone'd
float  chat_stamp[CHAT_RING];   // time of arrival; 0 = slot empty
float  chat_write;              // next ring slot

// Patch 370: each slot's wrapped rows, "\n"-joined and strzone'd; chat_wrapn 0 = stale.
string chat_wrap[CHAT_RING];
float  chat_wrapn[CHAT_RING];
vector chat_wkey;               // (width, size, probe width) the cache was wrapped for
float  chat_wr_n;               // rows in Chat_Wrap's last answer
string chat_wr_carry;           // state codes so far, replayed at each continuation row
string chat_wr_link;            // the carry at ^[, which ^] restores (common.c:4305)
float  chat_wr_inlink;
// What the last Chat_Draw drew, for `chat_rows`.
float  chat_dr_y0, chat_dr_yl;  // Chat_DrawRows' first and last row y
float  chat_dft_n, chat_dft_y0, chat_dft_yl, chat_dr_bottom, chat_dr_cap, chat_dr_room;
float  chat_ord[CHAT_RING];     // ring slots drawn, newest first
float  chat_ordr[CHAT_RING];    // rows drawn of each
float  chat_ordy[CHAT_RING];    // top row y of each
float  chat_ordn;

// The typing line.  Patch 340: `say` opens HERE rather than the engine's
// one-line console input, and the box makes room for it -- messages shift up
// one line (more when the draft wraps) and stay shifted while you type.
float  chat_typing;

// Prototype: Chat_InputEvent submits through it, and it is defined last.
void(string cmd, string text) Chat_RunSafe;
string chat_buf;

string chat_sil[CHAT_SIL_MAX];  // lowercase names
float  chat_sil_n;

// The parse result, because QC has no tuples and these all come from one walk.
string chat_ps_text;
float  chat_ps_slot;            // -1 = no player (server line, fake chat)
float  chat_ps_team;
float  chat_ps_me;

/*
  The silence list.  Lowercase on both sides of every compare; a name is
  arbitrary text from a stranger and "Lex" and "lex" are the same person as
  far as a mute button is concerned.  strcmp and never ==: both sides are
  runtime strings, and == on those compares POINTERS.
*/
float(string nm) Chat_Silenced =
{
	local float i;
	local string l;

	l = strtolower(nm);
	for (i = 0; i < chat_sil_n; i = i + 1)
		if (strcmp(chat_sil[i], l) == 0)
			return TRUE;
	return FALSE;
};

void() Chat_SilenceSave =
{
	local filestream fh;
	local float i;

	fh = fopen("data/chatsilence.txt", FILE_WRITE);
	if (fh < 0)
	{
		print("^1chat:^7 cannot write data/chatsilence.txt\n");
		return;
	}
	for (i = 0; i < chat_sil_n; i = i + 1)
		fputs(fh, strcat(chat_sil[i], "\n"));
	fclose(fh);
};

void() Chat_SilenceLoad =
{
	local filestream fh;
	local string l;

	chat_sil_n = 0;
	fh = fopen("data/chatsilence.txt", FILE_READ);
	if (fh < 0)
		return;
	for (l = fgets(fh); l != ""; l = fgets(fh))
	{
		l = strtolower(strtrim(l));
		if (l == "" || strlen(l) > CHAT_NAME_MAX)
			continue;
		if (chat_sil_n >= CHAT_SIL_MAX)
			break;
		if (!Chat_Silenced(l))
		{
			chat_sil[chat_sil_n] = l;
			chat_sil_n = chat_sil_n + 1;
		}
	}
	fclose(fh);
};

// Returns TRUE when the name is silenced after the toggle.  The player menu
// (cl_players.qc) calls this and re-draws from the answer.
float(string nm) Chat_SilenceToggle =
{
	local float i;
	local string l;

	l = strtolower(strtrim(nm));
	if (l == "" || strlen(l) > CHAT_NAME_MAX)
		return FALSE;

	for (i = 0; i < chat_sil_n; i = i + 1)
	{
		if (strcmp(chat_sil[i], l) == 0)
		{
			// Remove by sliding the tail down, then unzone the duplicate.
			if (chat_sil[i] != "")
				strunzone(chat_sil[i]);
			chat_sil_n = chat_sil_n - 1;
			while (i < chat_sil_n)
			{
				chat_sil[i] = chat_sil[i + 1];
				i = i + 1;
			}
			Chat_SilenceSave();
			print(sprintf("chat: %s unsilenced\n", nm));
			return FALSE;
		}
	}

	if (chat_sil_n >= CHAT_SIL_MAX)
	{
		print("^1chat:^7 silence list is full (32)\n");
		return FALSE;
	}
	chat_sil[chat_sil_n] = strzone(l);
	chat_sil_n = chat_sil_n + 1;
	Chat_SilenceSave();
	print(sprintf("chat: %s silenced\n", nm));
	return TRUE;
};

/*
  Split one arrived chat line into (slot, team, me, text).  chat_ps_text keeps
  the speaker's own ^ codes untouched -- they are markup, and the colour rule
  above yields to them.
*/
void(string msg) Chat_ParseServer =
{
	local float n, p, q, c;
	local string num, s;

	chat_ps_slot = -1;
	chat_ps_team = FALSE;
	chat_ps_me   = FALSE;
	chat_ps_text = msg;

	s = msg;
	n = strlen(s);

	// Trailing newline (the engine flushes per line, newline included).
	while (n > 0 && ((c = str2chr(s, n - 1)) == 10 || c == 13))
	{
		s = substring(s, 0, n - 1);
		n = n - 1;
	}

	// \1 chat marker.
	if (n > 0 && str2chr(s, 0) == 1)
	{
		s = substring(s, 1, n - 1);
		n = n - 1;
	}

	// /me arrives as "* NAME text" (or the spectator "^0*^7 " variant).
	if (substring(s, 0, 2) == "* ")
		chat_ps_me = TRUE;
	else if (substring(s, 0, 4) == "^0*^")
		chat_ps_me = TRUE;

	// The slot, out of the clickable escape.
	p = strstrofs(s, "\\player\\", 0);
	if (p >= 0)
	{
		q   = p + 8;                  // strlen("\player\")
		num = "";
		while (q < strlen(s))
		{
			c = str2chr(s, q);
			if (c < 48 || c > 57)
				break;
			num = strcat(num, chr2str(c));
			q = q + 1;
		}
		if (num != "")
			chat_ps_slot = stof(num);
	}

	// The body starts after the highlight close, its optional team ")" and
	// the separator.  A line with no "^]" has no name bracket at all -- a
	// server or faked chat line -- and its text is what is left.
	p = strstrofs(s, "^]", 0);
	if (p >= 0)
	{
		s = substring(s, p + 2, strlen(s));
		if (substring(s, 0, 1) == ")")
		{
			chat_ps_team = TRUE;
			s = substring(s, 1, strlen(s));
		}
		if (substring(s, 0, 2) == ": ")
			s = substring(s, 2, strlen(s));
		else if (substring(s, 0, 1) == " ")
			s = substring(s, 1, strlen(s));
	}
	chat_ps_text = s;
};

/*
  The engine's console-colour pick for a player, mirrored from CL_PlayerColor's
  non-teamplay branch (cl_parse.c:7055): the `tc` userinfo key when present,
  else the userid; colour = 1 + (c mod 7).  Returns "1".."7".
*/
string(float slot) Chat_ColourOf =
{
	local string t;
	local float c;

	t = getplayerkeyvalue(slot, "tc");
	if (t == "")
		t = getplayerkeyvalue(slot, "userid");
	c = stof(t);
	if (c < 0)
		c = 0;
	c = c - floor(c / 7) * 7;         // mod, the subtraction way
	return ftos(c + 1);
};

/*
  One display line out of the parse.  The name is coloured by Chat_ColourOf
  UNLESS it carries ^ codes of its own -- in which case nothing is prefixed
  and the name paints itself.
*/
string() Chat_BuildLine =
{
	local string nm, col;

	if (chat_ps_slot < 0)
		return chat_ps_text;

	nm = getplayerkeyvalue(chat_ps_slot, "name");
	if (nm == "")
		return chat_ps_text;

	col = (strstrofs(nm, "^", 0) >= 0) ? "" : strcat("^", Chat_ColourOf(chat_ps_slot));

	if (chat_ps_me)
		return strcat("* ", col, nm, "^7 ", chat_ps_text);
	if (chat_ps_team)
		return strcat("(", col, nm, "^7): ", chat_ps_text);
	return strcat(col, nm, "^7: ", chat_ps_text);
};

void(string line) Chat_Push =
{
	if (chat_ring[chat_write] != "")
		strunzone(chat_ring[chat_write]);
	chat_ring[chat_write]  = strzone(line);
	chat_stamp[chat_write] = time;
	chat_wrapn[chat_write] = 0;
	chat_write = chat_write + 1;
	if (chat_write >= CHAT_RING)
		chat_write = 0;
};

/*
  THE HOOK ITSELF.  The engine looks this name up (pr_csqc.c:9601) and routes
  every server print here once it exists -- see the file header for the
  echo-everything-else rule that comes with it.
*/
void(string msg, float level) CSQC_Parse_Print =
{
	local string line;

	if (level != CHAT_LVL_PRINT)
	{
		print(msg);
		return;
	}

	Chat_ParseServer(msg);

	if (chat_ps_slot >= 0)
		if (Chat_Silenced(getplayerkeyvalue(chat_ps_slot, "name")))
			return;                      // silenced: neither drawn nor echoed

	line = Chat_BuildLine();
	print(strcat(line, "\n"));
	Chat_Push(line);
};

/*
  Cut a built line to a pixel width.  Character-wise from the front; a cut
  that lands inside a ^ code can mis-colour the tail, which is the cheap
  trade for not tokenising -- and the tail is the part being thrown away.
*/
string(string s, float maxw, float sz) Chat_Fit =
{
	local float i, n, w;
	local string out;

	w = stringwidth(s, TRUE, [sz, sz]);
	if (w <= maxw)
		return s;

	n = strlen(s);
	out = "";
	for (i = 0; i < n; i = i + 1)
	{
		out = strcat(out, substring(s, i, 1));
		if (stringwidth(out, TRUE, [sz, sz]) > maxw - sz * 2)
			return strcat(out, "..");
	}
	return out;
};

/*
  PATCH 370: WRAPPING.  A row breaks at a space; a word wider than a row is cut
  between units -- a whole markup code, a UTF-8 run, or one byte -- never inside
  a code.  Unit lengths mirror COM_ParseFunString (common.c:4218-4450), which is
  what drawstring and stringwidth both run.
*/
float(float c) Chat_IsHex =
{
	return (c >= 48 && c <= 57) || (c >= 65 && c <= 70) || (c >= 97 && c <= 102);
};

float(float c, string set) Chat_CharIn =
{
	return c > 0 && strstrofs(set, chr2str(c), 0) >= 0;
};

// Bytes of markup at s[i]; 0 = the byte draws itself.
float(string s, float i, float n) Chat_CodeLen =
{
	local float c, l;

	l = 0;
	if (i + 1 >= n)
		return 0;
	c = str2chr(s, i);
	if (c == 38)                         // ezQuake &cRGB / &r (common.c:4469), on by default
	{
		if (!cvar("ezcompat_markup"))
			return 0;
		c = str2chr(s, i + 1);
		if (c == 114)
			return 2;
		if (c == 99)
		if (Chat_IsHex(str2chr(s, i + 2)) && Chat_IsHex(str2chr(s, i + 3))
		 && Chat_IsHex(str2chr(s, i + 4)))
			return min(5, n - i);
		return 0;
	}
	if (c != 94)
		return 0;
	c = str2chr(s, i + 1);
	if ((c >= 48 && c <= 57) || Chat_CharIn(c, "bdmahsr[]^"))
		return 2;
	if (c == 120)                        // ^xRGB; a bad ^x is still eaten as 2
		return (Chat_IsHex(str2chr(s, i + 2)) && Chat_IsHex(str2chr(s, i + 3))
		     && Chat_IsHex(str2chr(s, i + 4))) ? 5 : 2;
	if (c == 38)                         // ^&FB, else a literal ^
		return (Chat_CharIn(str2chr(s, i + 2), "0123456789ABCDEF-")
		     && Chat_CharIn(str2chr(s, i + 3), "0123456789ABCDEF-")) ? 4 : 0;
	if (c == 85)                         // ^U always takes six
		return min(6, n - i);
	if (c == 123)                        // ^{hex} and its optional close
	{
		l = 2;
		while (i + l < n && Chat_IsHex(str2chr(s, i + l)))
			l = l + 1;
		if (str2chr(s, i + l) == 125)
			l = l + 1;
		return min(l, n - i);
	}
	if (c == 96)                         // ^`u8: opens a span the engine reads to its `= or
	if (substring(s, i + 2, 3) == "u8:")   // the string's end: a row may split it safely
		return min(5, n - i);
	return 0;
};

float(string s, float i, float n) Chat_UnitLen =
{
	local float l, c;

	l = Chat_CodeLen(s, i, n);
	if (l > 0)
		return l;
	l = 1;
	if (str2chr(s, i) >= 192)            // UTF-8 lead: keep its continuation bytes
		while (i + l < n)
		{
			c = str2chr(s, i + l);
			if (c < 128 || c >= 192)
				break;
			l = l + 1;
		}
	return l;
};

// Continuation rows replay the state codes seen so far, in order (so ^d and the
// ^s/^r stack replay too); a link restores the state it opened with, and glyph
// codes are not state.
void(string u) Chat_CarryEat =
{
	local float c;

	c = str2chr(u, 1);
	if (c == 91)
	{
		chat_wr_link   = chat_wr_carry;
		chat_wr_inlink = TRUE;
	}
	else if (c == 93)
	{
		if (chat_wr_inlink)
			chat_wr_carry = chat_wr_link;
		chat_wr_inlink = FALSE;
	}
	else if (!Chat_CharIn(c, "^U{`"))
	if (c != 120 || strlen(u) == 5)
		chat_wr_carry = strcat(chat_wr_carry, u);
};

void(string w) Chat_CarryScan =
{
	local float i, n, l;

	if (strstrofs(w, "^", 0) < 0)
	if (strstrofs(w, "&", 0) < 0)
		return;
	n = strlen(w);
	i = 0;
	while (i < n)
	{
		l = Chat_UnitLen(w, i, n);
		if (Chat_CodeLen(w, i, n) > 0)
			Chat_CarryEat(substring(w, i, l));
		i = i + l;
	}
};

string(string out, string row) Chat_WrEmit =
{
	chat_wr_n = chat_wr_n + 1;
	return (chat_wr_n == 1) ? row : strcat(out, "\n", row);
};

// s wrapped to maxw in the current font: rows "\n"-joined, chat_wr_n of them (>= 1).
// A \n or \r in s forces a break.
string(string s, float maxw, float sz) Chat_Wrap =
{
	local float n, i, j, k, p, l, c, wd;
	local string out, row, u, cand;

	n   = strlen(s);
	out = "";
	row = "";
	wd  = 0;
	chat_wr_n      = 0;
	chat_wr_carry  = "";
	chat_wr_link   = "";
	chat_wr_inlink = FALSE;
	c = str2chr(s, 0);
	if (c == 1 || c == 2)
		chat_wr_carry = "^m";            // a leading \1 or \2 flips the charset (common.c:4167)

	i = 0;
	while (i < n)
	{
		j = i;
		while (j < n && str2chr(s, j) == 32)
			j = j + 1;
		k = j;
		while (k < n)
		{
			c = str2chr(s, k);
			if (c == 32 || c == 10 || c == 13)
				break;
			k = k + 1;
		}

		// Spaces with no word after them (end, or a forced break) are dropped.
		if (k > j)
		{
			cand = strcat(row, substring(s, i, k - i));
			l = stringwidth(cand, TRUE, [sz, sz]);
			if (l <= maxw)
			{
				row = cand;
				wd  = l;
				Chat_CarryScan(substring(s, j, k - j));
			}
			else
			{
				cand = strcat(chat_wr_carry, substring(s, j, k - j));
				l = stringwidth(cand, TRUE, [sz, sz]);
				if (wd > 0 && l <= maxw)
				{
					// Break at the space; the spaces themselves are dropped.
					out = Chat_WrEmit(out, row);
					row = cand;
					wd  = l;
					Chat_CarryScan(substring(s, j, k - j));
				}
				else
				{
					// Wider than a whole row: fill this row first, then cut by units.
					if (wd > 0)
						row = strcat(row, substring(s, i, j - i));
					p = j;
					while (p < k)
					{
						l = Chat_UnitLen(s, p, k);
						u = substring(s, p, l);
						cand = strcat(row, u);
						c = stringwidth(cand, TRUE, [sz, sz]);
						if (c > maxw && wd > 0)
						{
							out  = Chat_WrEmit(out, row);
							cand = strcat(chat_wr_carry, u);
							c    = stringwidth(cand, TRUE, [sz, sz]);
						}
						row = cand;
						wd  = c;
						if (Chat_CodeLen(s, p, k) > 0)
							Chat_CarryEat(u);
						p = p + l;
					}
				}
			}
		}

		i = k;
		c = str2chr(s, i);
		if (i < n && c != 32)            // \n or \r
		{
			out = Chat_WrEmit(out, row);
			row = chat_wr_carry;
			wd  = 0;
			i = i + 1;
		}
	}
	return Chat_WrEmit(out, row);
};

float(float j, float maxw, float sz) Chat_RowsOf =
{
	if (chat_wrapn[j] > 0)
		return chat_wrapn[j];
	if (chat_wrap[j] != "")
		strunzone(chat_wrap[j]);
	chat_wrap[j]  = Chat_Wrap(chat_ring[j], maxw, sz);
	if (chat_wrap[j] != "")             // a zoned "" would read as unset and never be freed
		chat_wrap[j] = strzone(chat_wrap[j]);
	chat_wrapn[j] = chat_wr_n;
	return chat_wr_n;
};

// The longest unit-whole prefix of t that still fits maxw with ".." after it.
string(string t, float maxw, float sz) Chat_Cut =
{
	local float i, n, l;
	local string keep;

	n = strlen(t);
	keep = "";
	i = 0;
	while (i < n)
	{
		l = Chat_UnitLen(t, i, n);
		if (stringwidth(strcat(substring(t, 0, i + l), ".."), TRUE, [sz, sz]) > maxw)
			break;
		i = i + l;
		keep = substring(t, 0, i);
	}
	return strcat(keep, "..");
};

// n rows of a "\n"-joined block, top-down from p; cut = the last row ends "..".
void(string rows, float n, float cut, vector p, float sz, float lh, float a, float maxw) Chat_DrawRows =
{
	local float r, s, e;
	local string t;

	s = 0;
	for (r = 0; r < n; r = r + 1)
	{
		e = strstrofs(rows, "\n", s);
		if (e < 0)
			e = strlen(rows);
		t = substring(rows, s, e - s);
		if (cut && r == n - 1)
			t = Chat_Cut(t, maxw, sz);
		drawstring([p_x + 1, p_y + lh * r + 1], t, [sz, sz], '0 0 0', a * 0.6, 0);
		drawstring([p_x, p_y + lh * r], t, [sz, sz], '1 1 1', a, 0);
		if (r == 0)
			chat_dr_y0 = p_y + lh * r;
		chat_dr_yl = p_y + lh * r;
		s = e + 1;
	}
};

void(vector scr) Chat_Draw =
{
	local float life, fade, lines, szu, sz, lh, x, yb, maxw;
	local float i, j, age, a, n, used, cap, room;
	local string draft;
	local vector key;

	draft = "";
	if (!cvar("hud_chat"))
		return;

	life  = cvar("hud_chat_time");   if (life <= 0)  life = 30;
	fade  = cvar("hud_chat_fade");   if (fade < 0)   fade = 5;
	if (fade > life - 1) fade = life - 1;
	lines = cvar("hud_chat_lines");  if (lines <= 0) lines = 6;
	if (lines > CHAT_RING) lines = CHAT_RING;
	szu   = cvar("hud_chat_size");
	if (szu <= 0)
	{
		szu = 4 * cvar("hud_scale");
		if (szu <= 0)
			szu = 8;
	}
	sz  = Font_Px(szu);
	lh  = sz * 1.35;

	x    = scr_x * cvar("hud_chat_x");
	yb   = scr_y * cvar("hud_chat_y");
	maxw = scr_x * 0.45;
	chat_dr_bottom = yb;

	Font_Set(ui_font_ui);

	// Wrapped rows are good for one width, size and font.
	key = [maxw, sz, stringwidth("abcdefghij", TRUE, [sz, sz])];
	if (key != chat_wkey)
	{
		for (i = 0; i < CHAT_RING; i = i + 1)
			chat_wrapn[i] = 0;
		chat_wkey = key;
	}

	/*
	  THE DRAFT at the very bottom, first row on top (Patch 370: it used to grow
	  upward).  Wrapped with the cursor always in, so the blink cannot re-wrap
	  it.  Idle it is one blank row: the room the messages always sit above
	  (341bis), so the box does not jump when you start typing.
	*/
	chat_dft_n  = 1;
	chat_dft_y0 = yb - lh;
	chat_dft_yl = yb - lh;
	if (chat_typing)
	{
		draft = Chat_Wrap(strcat("> ", chat_buf, "_"), maxw, sz);
		chat_dft_n = chat_wr_n;
		if (!(floor(time * 2) & 1))
			draft = strcat(substring(draft, 0, strlen(draft) - 1), " ");
		Chat_DrawRows(draft, chat_dft_n, FALSE, [x, yb - lh * chat_dft_n], sz, lh, 1, maxw);
		chat_dft_y0 = chat_dr_y0;
		chat_dft_yl = chat_dr_yl;
	}
	yb = yb - lh * chat_dft_n;

	/*
	  Newest first, skipping the expired (a negative age is a previous map's
	  stamp).  At most hud_chat_lines messages in at most max(lines, 10) rows,
	  and older messages only whole.  The newest always shows, and is cut ("..")
	  only when it alone is taller than the room above the draft.
	*/
	room = scr_y * 0.02;
	if (vt_box_z > 0)                   // Patch 372: a vote box above, in the chat's column
	if (vt_boxtop < yb)
	if (vt_box_x < x + maxw && vt_box_y > x)
		room = max(room, vt_box_z + lh * 0.25);
	room = floor((yb - room) / lh);
	if (room < 1)
		room = 1;
	cap = max(lines, CHAT_ROWS_MIN);
	if (cap > room)
		cap = room;
	chat_dr_cap  = cap;
	chat_dr_room = room;

	chat_ordn = 0;
	used = 0;
	for (i = 0; i < CHAT_RING; i = i + 1)
	{
		if (chat_ordn >= lines || used >= cap)
			break;
		j = chat_write - 1 - i;
		while (j < 0)
			j = j + CHAT_RING;
		if (chat_ring[j] == "" || chat_stamp[j] <= 0)
			continue;
		age = time - chat_stamp[j];
		if (age < 0 || age > life)
			continue;
		n = Chat_RowsOf(j, maxw, sz);
		if (chat_ordn > 0)
		if (used + n > cap)
			break;
		if (n > room)
			n = room;
		chat_ord[chat_ordn]  = j;
		chat_ordr[chat_ordn] = n;
		chat_ordn = chat_ordn + 1;
		used = used + n;
	}

	for (i = 0; i < chat_ordn; i = i + 1)
	{
		j   = chat_ord[i];
		n   = chat_ordr[i];
		age = time - chat_stamp[j];
		a   = (age <= life - fade) ? 1 : 1 - (age - (life - fade)) / fade;
		yb  = yb - lh * n;
		chat_ordy[i] = yb;
		if (a <= 0)
			continue;
		// Shadowed like the rest of the HUD's text: readable over both a dark
		// leaf and a white skybox.
		Chat_DrawRows(chat_wrap[j], n, chat_wrapn[j] > n, [x, yb], sz, lh, a, maxw);
		chat_ordy[i] = chat_dr_y0;
	}
	Font_Reset();
};

// `chat_rows`: what the last draw wrapped and where it drew it (^ doubled for the log).
void(string tag, string rows, float n) Chat_DumpBlock =
{
	local float r, s, e;
	local string t;

	s = 0;
	for (r = 0; r < n; r = r + 1)
	{
		e = strstrofs(rows, "\n", s);
		if (e < 0)
			e = strlen(rows);
		t = substring(rows, s, e - s);
		print(sprintf("chat_rows: %s %g w %.1f |%s|\n", tag, r,
		              stringwidth(t, TRUE, [chat_wkey_y, chat_wkey_y]), strreplace("^", "^^", t)));
		s = e + 1;
	}
};

void() Chat_DumpRows =
{
	local float i, j;
	local string rows;

	rows = "";
	if (chat_wkey_x <= 0)
	{
		print("chat_rows: not drawn yet\n");
		return;
	}
	Font_Set(ui_font_ui);
	print(sprintf("chat_rows: maxw %.1f sz %g lh %.2f lines %g cap %g room %g shown %g\n",
	              chat_wkey_x, chat_wkey_y, chat_wkey_y * 1.35, cvar("hud_chat_lines"),
	              chat_dr_cap, chat_dr_room, chat_ordn));
	print(sprintf("chat_rows: draft n %g y0 %.1f yl %.1f bottom %.1f typing %g\n",
	              chat_dft_n, chat_dft_y0, chat_dft_yl, chat_dr_bottom, chat_typing));
	if (chat_typing)
	{
		rows = Chat_Wrap(strcat("> ", chat_buf, "_"), chat_wkey_x, chat_wkey_y);
		print(sprintf("chat_rows: draft len %g\n", strlen(chat_buf)));
		Chat_DumpBlock("draft", rows, chat_wr_n);
	}
	for (i = 0; i < chat_ordn; i = i + 1)
	{
		j = chat_ord[i];
		print(sprintf("chat_rows: msg%g n %g drawn %g y0 %.1f\n", i, chat_wrapn[j],
		              chat_ordr[i], chat_ordy[i]));
		Chat_DumpBlock(sprintf("msg%g", i), chat_wrap[j], chat_wrapn[j]);
	}
	Font_Reset();
};

void() Chat_RegisterCvars =
{
	/*
	  REGISTERED BESIDE THE READ, the rule this tree has lost features to four
	  times: cvar() auto-creates an unregistered name as "" and a later
	  registercvar declines to overwrite it.  Chat_Draw reads all of these.

	  Defaults: on, bottom-left slightly off the corner (fractions, like every
	  other hud_*_x/y), six messages, gone after 30 s with the last 5 s spent
	  fading -- the ask, "~30sec", as a lifetime rather than a cliff.
	*/
	registercvar("hud_chat",       "1",     CVAR_ARCHIVE);
	registercvar("hud_chat_x",     "0.05",  CVAR_ARCHIVE);
	registercvar("hud_chat_y",     "0.95",  CVAR_ARCHIVE);
	registercvar("hud_chat_lines", "6",     CVAR_ARCHIVE);
	registercvar("hud_chat_time",  "30",    CVAR_ARCHIVE);
	registercvar("hud_chat_fade",  "5",     CVAR_ARCHIVE);
	registercvar("hud_chat_size",  "24",    CVAR_ARCHIVE);

	chat_typing = FALSE;
	chat_buf    = "";

	Chat_SilenceLoad();

	registercommand("chat_say");
	registercommand("chat_open");       // Patch 392: a plain "open chat" name
	registercommand("chat_rows");
};

/*
  THE TYPING LINE'S INPUT.  Offered FIRST in CL_InputChain, ahead of every
  panel and ahead of Keys_Edge, for the obvious reason: while a draft exists
  every key belongs to the draft, and a W that also ducked is a draft you
  cannot trust.

  HOW IT OPENS WITHOUT TOUCHING ANYBODY'S BINDS.  The engine's `say` is an
  engine command and CSQC_ConsoleCommand never sees it (cmd beats CSQC), but
  the KEY that runs it is offered here first: getkeybind(scanx) names the
  command a press would run, so a press bound to messagemode/say starts the
  draft instead and the engine's corner input never opens.  Existing binds
  keep working, unchanged, and `say text` typed at the console still takes
  the engine path.
*/
float(float evtype, float scanx, float chary, float devid) Chat_InputEvent =
{
	local string b;

	if (!chat_typing)
	{
		if (evtype != IE_KEYDOWN)
			return FALSE;
		b = getkeybind(scanx);
		if (b != "messagemode" && b != "messagemode2" && b != "chat_say" && b != "chat_open")
			return FALSE;
		chat_typing = TRUE;
		chat_buf    = "";
		return TRUE;
	}

	// Typing.  Releases are swallowed silently; presses belong to the draft
	// except the console's own key, which has to stay reachable.
	if (evtype == IE_KEYUP)
		return TRUE;
	if (evtype != IE_KEYDOWN)
		return TRUE;

	if (getkeybind(scanx) == "toggleconsole")
	{
		chat_typing = FALSE;             // abandon, do not fight the console
		return FALSE;
	}

	if (scanx == K_ENTER)
	{
		if (strtrim(chat_buf) != "")
			Chat_RunSafe("cmd say", chat_buf);
		chat_typing = FALSE;
		return TRUE;
	}
	if (scanx == K_ESCAPE)
	{
		chat_typing = FALSE;
		return TRUE;
	}
	if (scanx == K_BACKSPACE)
	{
		if (strlen(chat_buf) > 0)
			chat_buf = substring(chat_buf, 0, strlen(chat_buf) - 1);
		return TRUE;
	}

	// Printable characters only; the draft is capped so a held key cannot
	// grow it past what say itself would take.
	if (chary >= 32 && chary < 127 && strlen(chat_buf) < CHAT_DRAFT_MAX)
		chat_buf = strcat(chat_buf, chr2str(chary));
	return TRUE;
};

float(string cmd) Chat_ConsoleCommand =
{
	local float n, i;
	local string t;

	if (argv(0) == "chat_rows")
	{
		Chat_DumpRows();
		return TRUE;
	}
	if (argv(0) != "chat_say" && argv(0) != "chat_open")
		return FALSE;

	// `chat_say <text>` opens the draft already filled (a test handle); bare is unchanged.
	// chat_open is the same command under a plainer name.
	n = tokenize_console(cmd);
	t = "";
	for (i = 1; i < n; i = i + 1)
		t = (i == 1) ? argv(1) : strcat(t, " ", argv(i));
	if (strlen(t) > CHAT_DRAFT_MAX)
		t = substring(t, 0, CHAT_DRAFT_MAX);
	chat_typing = TRUE;
	chat_buf    = t;
	return TRUE;
};

/*
  BARE `say` OPENS THE DRAFT; `say <text>` IS A SEND.

  The engine offers the whole command here before it sends anything
  (zqtp.c:3774), and patch 341 took BOTH forms -- which broke every caller that
  passes text.  `say !r` and `say !m` are the R and M binds in default.cfg:864
  and defaultuser.cfg:96, `!s N`/`!b N` are how you reach a stage or a bonus,
  and six cfgs under cfg/test/ drive runs with them: all of them silently
  opened a prefilled typing line and sent nothing, so the restart keys did
  nothing at all.

  Only the ARGUMENT-LESS form is the gesture the typing line replaced, so that
  is the only one taken.  Text is declined and the engine's own send runs,
  which is also the right half to hand it to: CL_Say wraps the message in
  exactly the one quote pair SV_Say strips (sv_user.c:4385), so `say !s 3`
  arrives as one command with its argument intact.  Returning FALSE for a bare
  `say` would instead reach the engine's `Cmd_Argc() < 2` branch and open the
  engine's own corner prompt (zqtp.c:3777), which is the thing patch 341
  replaced -- hence TRUE there and only there.

  What the draft itself sends is Chat_RunSafe's business, below, and it is
  unaffected: `cmd say` never enters CL_Say, so it cannot re-enter this hook.
*/
float(string args, float team) CSQC_ChatSay =
{
	if (team)
		return FALSE;          // say_team: no teams here, let the engine answer
	if (strtrim(args) != "")
		return FALSE;          // `say <text>` is a send, not a draft
	chat_typing = TRUE;
	chat_buf    = "";
	return TRUE;
};

/*
  PATCH 341: SEND CHAT TEXT WITHOUT LEAVING QUOTES IN IT, AND WITHOUT LETTING
  THE TEXT EXECUTE ANYTHING.

  The wire contract is one quote pair: the client's legacy send wraps sendtext
  in quotes (zqtp.c:3910) and the server strips exactly one pair (sv_user.c:
  4385), so a %S-quoted draft arrived as `"text"` in everybody's chat -- the
  pair was ours, one too many.  Unquoted, though, the draft's own text goes
  through the local command buffer, where a `;` ends the command and starts
  the next one: "gg; wp" would have sent "gg" and run `wp`.

  So the text travels in a cvar instead.  `set` takes it quoted (the buffer's
  split is quote-aware, cmd.c:614-655, so a `;` inside is inert), and the send
  line then carries only `$cl_safetmp`, which Cmd_ExpandString substitutes
  AFTER the buffer already cut the line -- the substituted semicolons are
  plain argument characters by then.  The send is `cmd say`, not `say`: Patch
  341's own CSQC_ChatSay hook intercepts CL_Say, so a bare `say $cl_safetmp`
  would reopen the draft with its own text instead of sending it.  `cmd`
  forwards the stringcmd straight to the server, whose SV_Say sees unquoted
  text and strips nothing -- the chat reads exactly what was typed.
*/
void(string cmd, string text) Chat_RunSafe =
{
	localcmd(sprintf("set cl_safetmp %S\n%s $cl_safetmp\n", text, cmd));
};
