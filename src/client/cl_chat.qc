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
string chat_mark[CHAT_RING];    // Patch 789: the speaker's picture mark, strzone'd or ""
string chat_push_mark;          // set just before Chat_Push by a caller that knows one
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
#define CHAT_KN 8
float  chat_kd[CHAT_KN];        // presses the draft took, still held (Patch 477 round 24)
#define CHAT_DN 16
float  chat_dn[CHAT_DN];        // keys down, whoever took them (round 25)
float  chat_rep;                // this KEYDOWN is an OS repeat of a key already down

// Patch 821: an open draft is a panel -- the history, a one-line field, and the
// mouse (UIC_CHAT) to select and copy with.  The field draws its text raw.
#define CHAT_SENT_MAX   20      // sent lines Up/Down recall
#define CHAT_FADE_IN    0.12    // s
#define CHAT_FADE_OUT   0.18
#define CHAT_MULTI      0.35    // s between the clicks of a double or triple click
float  chat_caret;              // the field's caret, a byte of chat_buf
var float chat_anchor = -1;     // ...the selection's fixed end, -1 none
// Patch 824: the field wraps, and grows a row at a time.  Row r is
// chat_buf[chat_fr[r] .. chat_fr[r + 1]) (the last runs to the end).
#define CHAT_FR_MAX     16
float  chat_fr[CHAT_FR_MAX];
float  chat_fr_n;               // rows; 0 = wrap again
string chat_fr_buf;             // ...the text, width and size they were wrapped for
float  chat_fr_w, chat_fr_sz, chat_fr_face;
float  chat_fld_pw;             // the PM label's width before the text
float  chat_fld_ty;             // the first row's text y
float  chat_blink;              // cltime of the last key: the caret shows solid from it
float  chat_box_a, chat_box_t;  // the panel's fade 0..1, and cltime of its last step
float  chat_scroll;             // history rows scrolled up from the newest
float  chat_scroll_hold;        // lines that came in while scrolled: the view stays where it was
float  chat_rows_n;             // rows the whole history wraps to (last draw)
vector chat_ms;                 // the cursor, from IE_MOUSEABS
float  chat_ms_ok;              // ...which has moved since the panel opened: no position comes before
float  chat_drag;               // mouse1 held from a press on 1 the field, 2 the history
float  chat_clk_t, chat_clk_n;  // the last press's cltime and how many clicks it made
vector chat_clk_p;
// The history's selection: each end is (ring slot, its stamp, offset into its Chat_Plain).
// A slot whose stamp moved was overwritten, and the selection goes with it.
float  chat_sel_on;
float  chat_sa_j, chat_sa_t, chat_sa_o;     // where the drag began
float  chat_sb_j, chat_sb_t, chat_sb_o;     // where it is now
float  chat_s0_j, chat_s0_o, chat_s1_j, chat_s1_o;  // the two in reading order (Chat_SelNorm)
float  chat_hh_j, chat_hh_o;    // Chat_HistHit's answer
string chat_sent;               // sent lines, newest first, "\n"-joined
float  chat_sent_i;             // the sent line on show, -1 = the one being typed
string chat_sent_keep;          // ...which waits here meanwhile
string chat_copied;             // the last copy, for chat_rows
var float chat_copied_t = -100;
// Where the last draw put things, for the mouse.
vector chat_box_p, chat_box_s, chat_fld_p, chat_fld_s;
float  chat_fld_tx;             // the field text's x, its scroll included
float  chat_his_y0, chat_his_y1;
float  chat_dr_x;

// Prototype: Chat_InputEvent submits through it, and it is defined last.
void(string cmd, string text) Chat_RunSafe;
float(string text) WarpOp_Chat;  // cl_warpop.qc, Patch 753
string chat_buf;
string chat_private, chat_private_name;
void() Chat_PrivateClear =
{
	if (chat_private != "") strunzone(chat_private);
	if (chat_private_name != "") strunzone(chat_private_name);
	chat_private = "";
	chat_private_name = "";
};

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
	if (chat_mark[chat_write] != "")
		strunzone(chat_mark[chat_write]);
	chat_mark[chat_write]  = (chat_push_mark != "") ? strzone(chat_push_mark) : "";
	chat_push_mark = "";
	chat_stamp[chat_write] = time;
	chat_wrapn[chat_write] = 0;
	if (chat_scroll > 0)
		chat_scroll_hold = min(CHAT_RING, chat_scroll_hold + 1);
	chat_write = chat_write + 1;
	if (chat_write >= CHAT_RING)
		chat_write = 0;
};

/*
  THE HOOK ITSELF.  The engine looks this name up (pr_csqc.c:9601) and routes
  every server print here once it exists -- see the file header for the
  echo-everything-else rule that comes with it.
*/
void(string msg) Ev_ServerPrint;   // cl_entview.qc, Patch 776: keeps ent_info's reply for a pinned card

void(string msg, float level) CSQC_Parse_Print =
{
	local string line;

	if (level != CHAT_LVL_PRINT)
	{
		Ev_ServerPrint(msg);
		print(msg);
		return;
	}

	Chat_ParseServer(msg);

	if (chat_ps_slot >= 0)
		if (Chat_Silenced(getplayerkeyvalue(chat_ps_slot, "name")))
			return;                      // silenced: neither drawn nor echoed

	line = Chat_BuildLine();
	print(strcat(line, "\n"));
	// The account's mark only: a board's guid digest (*phash) has no picture.
	if (chat_ps_slot >= 0)
		chat_push_mark = getplayerkeyvalue(chat_ps_slot, "*ahash");
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
	// A line with a picture wraps narrower, by the face (Chat_Draw).
	chat_wrap[j]  = Chat_Wrap(chat_ring[j], maxw - ((chat_mark[j] != "") ? sz + 3 : 0), sz);
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
		// The offset black pass is the shadow, and it is the whole of its cost:
		// ~1.5 us a row, measured 2.0 -> 3.5 us for 62 chars.
		drawstring([p_x + 1, p_y + lh * r + 1], t, [sz, sz], '0 0 0', a * 0.6, 0);
		drawstring([p_x, p_y + lh * r], t, [sz, sz], '1 1 1', a, 0);
		if (r == 0)
			chat_dr_y0 = p_y + lh * r;
		chat_dr_yl = p_y + lh * r;
		s = e + 1;
	}
};

/*
  PATCH 821: SELECTING IN THE HISTORY.  An offset is into Chat_Plain of the whole
  line -- the bytes that draw, by Chat_Wrap's units -- so it survives a re-wrap.
  A row is that line with the spaces at its break dropped, so a row's start is
  found by its own plain text from where the last row ended.
*/
float(string s, float i, float n, float l) Chat_PlainLen =
{
	if (Chat_CodeLen(s, i, n) > 0)
		return (substring(s, i, 2) == "^^") ? 1 : 0;
	return (str2chr(s, i) < 32) ? 0 : l;
};

string(string s) Chat_Plain =
{
	local float i, n, l, c;
	local string out;

	n = strlen(s);
	out = "";
	i = 0;
	while (i < n)
	{
		l = Chat_UnitLen(s, i, n);
		c = Chat_PlainLen(s, i, n, l);
		if (c == l)
			out = strcat(out, substring(s, i, l));
		else if (c == 1)
			out = strcat(out, "^");
		i = i + l;
	}
	return out;
};

string(string rows, float r) Chat_Row =
{
	local float s, e;

	s = 0;
	for (; r > 0; r = r - 1)
	{
		e = strstrofs(rows, "\n", s);
		if (e < 0)
			return "";
		s = e + 1;
	}
	e = strstrofs(rows, "\n", s);
	if (e < 0)
		e = strlen(rows);
	return substring(rows, s, e - s);
};

// Where row r of slot j starts in Chat_Plain(chat_ring[j]).
float(float j, float r) Chat_RowAt =
{
	local float k, o, f;
	local string p, q;

	p = Chat_Plain(chat_ring[j]);
	o = 0;
	for (k = 0; k <= r; k = k + 1)
	{
		q = Chat_Plain(Chat_Row(chat_wrap[j], k));
		f = strstrofs(p, q, o);
		if (f >= 0)
			o = f;
		if (k < r)
			o = o + strlen(q);
	}
	return o;
};

// The plain offset in row t nearest pixel px from its start.
float(string t, float px, float sz) Chat_RowHit =
{
	local float i, n, l, k, c, w, pw;

	n = strlen(t);
	i = 0;
	k = 0;
	pw = 0;
	while (i < n)
	{
		l = Chat_UnitLen(t, i, n);
		c = Chat_PlainLen(t, i, n, l);
		i = i + l;
		if (c > 0)
		{
			w = stringwidth(substring(t, 0, i), TRUE, [sz, sz]);
			if (px < (pw + w) * 0.5)
				return k;
			pw = w;
			k = k + c;
		}
	}
	return k;
};

// The x of plain offset o in row t.
float(string t, float o, float sz) Chat_RowX =
{
	local float i, n, l, k;

	n = strlen(t);
	i = 0;
	k = 0;
	while (i < n && k < o)
	{
		l = Chat_UnitLen(t, i, n);
		k = k + Chat_PlainLen(t, i, n, l);
		i = i + l;
	}
	return stringwidth(substring(t, 0, i), TRUE, [sz, sz]);
};

// 0 = the newest line, the ring's oldest is CHAT_RING - 1.
float(float j) Chat_Age =
{
	j = chat_write - 1 - j;
	if (j < 0)
		j = j + CHAT_RING;
	return j;
};

// The two ends in reading order into chat_s0_* / chat_s1_*.  -> something is selected.
float() Chat_SelNorm =
{
	local float ka, kb;

	if (!chat_sel_on)
		return FALSE;
	if (chat_stamp[chat_sa_j] != chat_sa_t || chat_stamp[chat_sb_j] != chat_sb_t)
	{
		chat_sel_on = FALSE;
		return FALSE;
	}
	ka = Chat_Age(chat_sa_j);
	kb = Chat_Age(chat_sb_j);
	if (ka > kb || (ka == kb && chat_sa_o <= chat_sb_o))
	{
		chat_s0_j = chat_sa_j; chat_s0_o = chat_sa_o;
		chat_s1_j = chat_sb_j; chat_s1_o = chat_sb_o;
	}
	else
	{
		chat_s0_j = chat_sb_j; chat_s0_o = chat_sb_o;
		chat_s1_j = chat_sa_j; chat_s1_o = chat_sa_o;
	}
	return (chat_s0_j != chat_s1_j || chat_s0_o != chat_s1_o);
};

// The selected history as text, one line per message.
string() Chat_SelText =
{
	local float j, k, a, b;
	local string out, p;

	if (!Chat_SelNorm())
		return "";
	out = "";
	for (k = Chat_Age(chat_s0_j); k >= 0; k = k - 1)
	{
		j = chat_write - 1 - k;
		if (j < 0)
			j = j + CHAT_RING;
		p = Chat_Plain(chat_ring[j]);
		a = (j == chat_s0_j) ? chat_s0_o : 0;
		b = (j == chat_s1_j) ? chat_s1_o : strlen(p);
		p = (b > a) ? substring(p, a, b - a) : "";
		out = (j == chat_s0_j) ? p : strcat(out, "\n", p);
		if (j == chat_s1_j)
			break;
	}
	return out;
};

// The selection behind slot j's n rows, drawn from p.
void(float j, vector p, float n, float sz, float lh, float a) Chat_SelDraw =
{
	local float k, lo, hi, r, o, f, e, x0, x1;
	local string pl, t, q;

	if (!Chat_SelNorm())
		return;
	k = Chat_Age(j);
	if (k > Chat_Age(chat_s0_j) || k < Chat_Age(chat_s1_j))
		return;
	lo = (j == chat_s0_j) ? chat_s0_o : 0;
	hi = (j == chat_s1_j) ? chat_s1_o : 100000;
	pl = Chat_Plain(chat_ring[j]);
	o = 0;
	for (r = 0; r < n; r = r + 1)
	{
		t = Chat_Row(chat_wrap[j], r);
		q = Chat_Plain(t);
		f = strstrofs(pl, q, o);
		if (f >= 0)
			o = f;
		e = o + strlen(q);
		if (hi > o && lo < e)
		{
			x0 = Chat_RowX(t, max(lo, o) - o, sz);
			x1 = Chat_RowX(t, min(hi, e) - o, sz);
			if (x1 > x0)
				drawfill([p_x + x0, p_y + lh * r - (lh - sz) * 0.5], [x1 - x0, lh], SUI_THEME_SELECTED, a, 0);
		}
		o = e;
	}
};

// The history under the cursor into chat_hh_j / chat_hh_o, clamped to the rows
// drawn.  -> any are.
float(vector m) Chat_HistHit =
{
	local float i, j, r, sz, lh, y, ind;
	local string t;

	if (chat_ordn <= 0)
		return FALSE;
	sz = chat_wkey_y;
	lh = sz * 1.35;
	// Row r's band is its highlight's (Chat_SelDraw), half the leading above the glyphs.
	y = bound(chat_his_y0, m_y, chat_his_y1 - 0.01) + (lh - sz) * 0.5;
	Font_Set(ui_font_ui);
	for (i = 0; i < chat_ordn; i = i + 1)       // newest first, from the bottom up
	{
		if (y < chat_ordy[i] && i < chat_ordn - 1)
			continue;
		j = chat_ord[i];
		if (chat_wrapn[j] <= 0)                   // rewritten or re-wrapped since it was drawn
			break;
		chat_hh_j = j;
		r = floor((y - chat_ordy[i]) / lh);
		if (r < 0)
			chat_hh_o = 0;
		else if (r >= chat_ordr[i])
			chat_hh_o = strlen(Chat_Plain(chat_ring[j]));
		else
		{
			ind = (chat_mark[j] != "") ? sz + 3 : 0;
			t = Chat_Row(chat_wrap[j], r);
			chat_hh_o = Chat_RowAt(j, r) + Chat_RowHit(t, m_x - chat_dr_x - ind, sz);
		}
		Font_Reset();
		return TRUE;
	}
	Font_Reset();
	return FALSE;
};

float(string s, float i) Chat_WordStart =
{
	while (i > 0 && str2chr(s, i - 1) != 32)
		i = i - 1;
	return i;
};

float(string s, float i) Chat_WordEnd =
{
	local float n;

	n = strlen(s);
	while (i < n && str2chr(s, i) != 32)
		i = i + 1;
	return i;
};

float() Chat_FieldSelected =
{
	return chat_anchor >= 0 && chat_anchor != chat_caret;
};

// Patch 824: the field's text in rows w wide (raw, as drawn), each ending after a
// space where one fits; a word wider than a row is cut.  The font must be set.
void(float w, float sz) Chat_FieldWrap =
{
	local float n, s, i, sp, e;

	if (chat_fr_n > 0)
	if (strcmp(chat_fr_buf, chat_buf) == 0)
	if (chat_fr_w == w && chat_fr_sz == sz)
	if (chat_fr_face == stringwidth("abcdefghij", FALSE, [sz, sz]))
		return;
	chat_fr_buf  = chat_buf;
	chat_fr_w    = w;
	chat_fr_sz   = sz;
	chat_fr_face = stringwidth("abcdefghij", FALSE, [sz, sz]);
	n = strlen(chat_buf);
	chat_fr[0] = 0;
	chat_fr_n  = 1;
	s = 0;
	while (chat_fr_n < CHAT_FR_MAX)
	{
		sp = -1;
		for (i = s; i < n; i = i + 1)
		{
			if (stringwidth(substring(chat_buf, s, i + 1 - s), FALSE, [sz, sz]) > w)
				break;
			if (str2chr(chat_buf, i) == 32)
				sp = i + 1;
		}
		if (i >= n)
			break;
		if (str2chr(chat_buf, i) == 32)     // the space that did not fit ends the row
			e = i + 1;
		else if (sp > s)
			e = sp;
		else
			e = max(i, s + 1);
		chat_fr[chat_fr_n] = e;
		chat_fr_n = chat_fr_n + 1;
		s = e;
	}
};

// The row byte c is drawn on: a break's own byte starts the next row.
float(float c) Chat_FieldRow =
{
	local float r;

	for (r = chat_fr_n - 1; r > 0; r = r - 1)
		if (c >= chat_fr[r])
			return r;
	return 0;
};

// The field's label and rows for this frame.  -> its height.
float(float maxw, float sz, float lh) Chat_FieldLayout =
{
	chat_fld_pw = 0;
	if (chat_private != "")
		chat_fld_pw = stringwidth(strcat("to ", chat_private_name, "^7:"), TRUE, [sz, sz]) + ceil(sz * 0.4);
	Chat_FieldWrap(max(sz * 3, maxw - ceil(sz * 0.5) * 2 - chat_fld_pw), sz);
	return ceil(sz * 1.75) + lh * (chat_fr_n - 1);
};

// The caret nearest the cursor m, in the field as last drawn.
float(vector m) Chat_FieldHit =
{
	local float i, r, s, e, w, pw, sz, lh, px;

	sz = chat_wkey_y;
	lh = sz * 1.35;
	r = bound(0, floor((m_y - chat_fld_ty + (lh - sz) * 0.5) / lh), max(0, chat_fr_n - 1));
	s = chat_fr[r];
	e = (r + 1 < chat_fr_n) ? chat_fr[r + 1] : strlen(chat_buf);
	if (r + 1 < chat_fr_n && e > s && str2chr(chat_buf, e - 1) == 32)
		e = e - 1;                          // the space a row ends on; past it is the next row
	px = m_x - chat_fld_tx;
	pw = 0;
	Font_Set(ui_font_ui);
	for (i = s + 1; i <= e; i = i + 1)
	{
		w = stringwidth(substring(chat_buf, s, i - s), FALSE, [sz, sz]);
		if (px < (pw + w) * 0.5)
			break;
		pw = w;
	}
	Font_Reset();
	return i - 1;
};

// The field at the panel's foot, fh tall from Chat_FieldLayout: box, the PM's
// name, the selection, the rows, the caret.
void(float x, float yb, float maxw, float fh, float sz, float lh, float a) Chat_DrawField =
{
	local vector p, tp;
	local float inset, avail, r, s, e, a0, a1, x0, x1, y, rad;

	p = [x, yb - fh];
	rad = ceil(sz * 0.3);
	_sui_round_draw(p, [maxw, fh], rad, chat_typing ? SUI_THEME_ACCENT : SUI_THEME_EDGE, a);
	_sui_round_draw(p + '1 1 0', [maxw - 2, fh - 2], max(0, rad - 1), SUI_THEME_WELL, a);
	inset = ceil(sz * 0.5);
	tp = [p_x + inset, p_y + floor((ceil(sz * 1.75) - sz) * 0.5)];
	if (chat_private != "")
		drawstring(tp, strcat("to ", chat_private_name, "^7:"), [sz, sz], SUI_THEME_ACCENT2, a, 0);
	avail = maxw - inset * 2 - chat_fld_pw;
	chat_fld_p  = p;
	chat_fld_s  = [maxw, fh];
	chat_fld_tx = tp_x + chat_fld_pw;
	chat_fld_ty = tp_y;

	drawsetcliparea(chat_fld_tx - 2, p_y + 1, avail + 4, fh - 2);
	if (chat_buf == "")
		drawrawstring([chat_fld_tx, tp_y], "Enter sends, Esc closes", [sz, sz], SUI_THEME_MUTED, a, 0);
	a0 = min(chat_anchor, chat_caret);
	a1 = Chat_FieldSelected() ? max(chat_anchor, chat_caret) : a0;
	for (r = 0; r < chat_fr_n; r = r + 1)
	{
		s = chat_fr[r];
		e = (r + 1 < chat_fr_n) ? chat_fr[r + 1] : strlen(chat_buf);
		y = tp_y + lh * r;
		if (a1 > s && a0 < e)
		{
			x0 = stringwidth(substring(chat_buf, s, max(a0, s) - s), FALSE, [sz, sz]);
			x1 = stringwidth(substring(chat_buf, s, min(a1, e) - s), FALSE, [sz, sz]);
			drawfill([chat_fld_tx + x0, y - 1], [x1 - x0, sz + 2], SUI_THEME_SELECTED, a, 0);
		}
		if (e > s)
			drawrawstring([chat_fld_tx, y], substring(chat_buf, s, e - s), [sz, sz], SUI_THEME_TEXT, a, 0);
	}
	if (chat_typing)
	if (!(floor((cltime - chat_blink) * 2) & 1))
	{
		r = Chat_FieldRow(chat_caret);
		x0 = stringwidth(substring(chat_buf, chat_fr[r], chat_caret - chat_fr[r]), FALSE, [sz, sz]);
		drawfill([chat_fld_tx + x0, tp_y + lh * r - 1], [max(1, floor(sz / 12)), sz + 2], SUI_THEME_ACCENT, a, 0);
	}
	drawresetcliparea();
};

void(vector scr) Chat_Draw =
{
	local float life, fade, lines, szu, sz, lh, x, yb, maxw;
	local float i, j, age, a, n, used, cap, room, ind, ba, dt, pad, fh, hb, top, total, y, cn, cr, cdone, ca, r, w;
	local float bg;
	local string img;
	local vector key, bp, bs;

	// Patch 821: the panel fades in while a draft is open, and out after.  Patch 824:
	// and while hud_edit is up, so its settings show as they are changed.
	dt = bound(0, cltime - chat_box_t, 0.1);
	chat_box_t = cltime;
	if (chat_typing || (ui_he_open && cvar("hud_chat")))
		chat_box_a = min(1, chat_box_a + dt / CHAT_FADE_IN);
	else
		chat_box_a = max(0, chat_box_a - dt / CHAT_FADE_OUT);
	ba = chat_box_a * chat_box_a * (3 - 2 * chat_box_a);
	if (chat_typing)
	if (!UI_CursorHeld())               // the panel that had it let go (Chat_Open)
		UI_CursorClaim(UIC_CHAT);
	if (!cvar("hud_chat") && ba <= 0)
		return;

	life  = cvar("hud_chat_time");   if (life <= 0)  life = 30;
	fade  = cvar("hud_chat_fade");   if (fade < 0)   fade = 5;
	if (fade > life - 1) fade = life - 1;
	lines = cvar("hud_chat_lines");  if (lines <= 0) lines = 6;
	if (lines > CHAT_RING) lines = CHAT_RING;
	szu   = cvar("hud_chat_size");
	if (szu <= 0)
	{
		szu = 10 * cvar("hud_scale");     // Patch 824: 20 at hud_scale 2, the default (was 4)
		if (szu <= 0)
			szu = 20;
	}
	// Font_Set before Font_Px: the snap used to run on whatever face the last
	// drawer left (HUD_DrawSeq's essay is the same bug).
	Font_Set(ui_font_ui);
	sz  = Font_Px(szu);
	lh  = sz * 1.35;

	x    = scr_x * cvar("hud_chat_x");
	yb   = scr_y * cvar("hud_chat_y");
	maxw = scr_x * bound(0.15, cvar("hud_chat_w"), 0.9);   // Patch 824: was 0.45
	pad  = ceil(sz * 0.5);
	fh   = Chat_FieldLayout(maxw, sz, lh);
	// The history's foot, open or shut, so opening moves no line; a field that grows lifts them.
	hb   = yb - pad - fh - ceil(sz * 0.4);
	chat_dr_bottom = yb;
	chat_dr_x = x;

	// Wrapped rows are good for one width, size and font.
	key = [maxw, sz, stringwidth("abcdefghij", TRUE, [sz, sz])];
	if (key != chat_wkey)
	{
		for (i = 0; i < CHAT_RING; i = i + 1)
			chat_wrapn[i] = 0;
		chat_wkey = key;
	}
	chat_dft_n  = chat_fr_n;             // the field's rows, for chat_rows
	chat_dft_y0 = yb - pad - fh + floor((ceil(sz * 1.75) - sz) * 0.5);
	chat_dft_yl = chat_dft_y0 + lh * (chat_fr_n - 1);

	/*
	  At most hud_chat_lines messages in at most hud_chat_rows rows above the
	  field's place, and older messages only whole.  The newest always shows, and
	  is cut ("..") only when it alone is taller than the room.  Open, the panel
	  holds every line in the ring in up to that many rows, scrolled by the wheel.
	*/
	room = scr_y * 0.02;
	if (vt_box_z > 0)                   // Patch 372: a vote box above, in the chat's column
	if (vt_boxtop < hb)
	if (vt_box_x < x + maxw && vt_box_y > x)
		room = max(room, vt_box_z + lh * 0.25);
	room = floor((hb - pad - room) / lh);
	if (room < 1)
		room = 1;
	cap = cvar("hud_chat_rows");
	if (cap <= 0)
		cap = CHAT_ROWS_MIN;
	if (cap > room)
		cap = room;
	chat_dr_cap  = cap;
	chat_dr_room = room;
	chat_ordn = 0;

	if (ba > 0)
	{
		total = 0;
		for (i = 0; i < CHAT_RING; i = i + 1)
		{
			j = chat_write - 1 - i;
			if (j < 0)
				j = j + CHAT_RING;
			if (chat_ring[j] == "" || chat_stamp[j] <= 0 || time < chat_stamp[j])
				continue;
			total = total + Chat_RowsOf(j, maxw, sz);
		}
		for (i = 0; i < chat_scroll_hold; i = i + 1)   // new lines under a scrolled view
		{
			j = chat_write - 1 - i;
			if (j < 0)
				j = j + CHAT_RING;
			if (chat_ring[j] != "")
				chat_scroll = chat_scroll + Chat_RowsOf(j, maxw, sz);
		}
		chat_scroll_hold = 0;
		chat_rows_n = total;
		// The panel's rows: all of them (hud_chat_full), or as many as the history, 3 to cap.
		used = cvar("hud_chat_full") ? cap : bound(min(3, cap), total, cap);
		top  = hb - used * lh;
		chat_scroll = bound(0, chat_scroll, max(0, total - used));

		sui_style_hud(scr);
		bp = [x - pad, top - pad];
		bs = [maxw + pad * 2, yb - bp_y];       // its foot at hud_chat_y, clear of the key strip
		r  = ceil(sz * 0.45);
		bg = bound(0, cvar("hud_chat_bg"), 1);
		_sui_round_draw(bp + '-2 -1 0', bs + '4 4 0', r + 2, '0 0 0', 0.2 * min(1, bg / 0.88) * ba);
		_sui_round_draw(bp, bs, r, SUI_THEME_EDGE, min(1, bg + 0.07) * ba);
		_sui_round_draw(bp + '1 1 0', bs - '2 2 0', r - 1, SUI_THEME_PANEL, bg * ba);
		chat_box_p  = bp;
		chat_box_s  = bs;
		HUD_Rect("chat", bp, bs, [x, yb]);    // Patch 824: hud_edit's box; the anchor is hud_chat_x/y
		chat_his_y0 = top;
		chat_his_y1 = hb;

		/*
		  A line also keeps the alpha the shut box would give it, so a line that
		  is still on show shut does not fade with the panel.  cdone ends that set
		  where the shut box's loop would break.
		*/
		drawsetcliparea(bp_x, top, bs_x, used * lh);
		y = hb + chat_scroll * lh;
		cn = 0;
		cr = 0;
		cdone = FALSE;
		for (i = 0; i < CHAT_RING; i = i + 1)
		{
			j = chat_write - 1 - i;
			if (j < 0)
				j = j + CHAT_RING;
			if (chat_ring[j] == "" || chat_stamp[j] <= 0)
				continue;
			age = time - chat_stamp[j];
			if (age < 0)
				continue;
			n  = chat_wrapn[j];
			ca = 0;
			if (!cdone)
			if (age <= life)
			{
				if (cn >= lines || cr >= cap || (cn > 0 && cr + n > cap))
					cdone = TRUE;
				else
				{
					ca = (age <= life - fade) ? 1 : 1 - (age - (life - fade)) / fade;
					cn = cn + 1;
					cr = cr + n;
				}
			}
			y = y - lh * n;
			if (y + lh * n <= top)
				break;
			if (y >= hb)
				continue;
			chat_ord[chat_ordn]  = j;
			chat_ordr[chat_ordn] = n;
			chat_ordy[chat_ordn] = y;
			chat_ordn = chat_ordn + 1;
			a = max(ca, ba);
			ind = 0;
			if (chat_mark[j] != "")
			{
				ind = sz + 3;
				img = SteamPic_Of(chat_mark[j]);
				if (img != "")
					drawpic([x, y, 0], img, [sz, sz], '1 1 1', a, 0);
			}
			Chat_SelDraw(j, [x + ind, y], n, sz, lh, ba);
			Chat_DrawRows(chat_wrap[j], n, FALSE, [x + ind, y], sz, lh, a, maxw - ind);
		}
		drawresetcliparea();

		if (total > used)                // the scroll thumb, in the right-hand padding
		{
			w = max(sz, (hb - top) * used / total);
			drawfill([bp_x + bs_x - pad * 0.5 - 1, top + (hb - top - w) * (1 - chat_scroll / (total - used))],
			         [2, w], SUI_THEME_EDGE_HI, ba, 0);
		}
		if (cltime - chat_copied_t < 1.5)
		{
			a = ba * min(1, (1.5 - (cltime - chat_copied_t)) / 0.4);
			w = stringwidth("Copied", FALSE, [sz, sz]) + pad * 2;
			_sui_round_draw([bp_x + bs_x - w - pad * 0.5, bp_y + pad * 0.5], [w, ceil(sz * 1.4)],
			                ceil(sz * 0.3), SUI_THEME_GOOD_BG, a);
			drawrawstring([bp_x + bs_x - w - pad * 0.5 + pad, bp_y + pad * 0.5 + ceil(sz * 0.2)], "Copied",
			              [sz, sz], SUI_THEME_GOOD, a, 0);
		}
		Chat_DrawField(x, yb - pad, maxw, fh, sz, lh, ba);
		Font_Reset();
		return;
	}

	yb = hb;
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
		// Shadowed so a row stays readable over both a dark leaf and a white
		// skybox.  NOT "like the rest of the HUD's text", which this said until
		// Patch 443: HUD_Text drew plain when it was written, and Patch 440's ring
		// and shadow for the mono face are opt-in (hud_font_outline).
		// Patch 789: the speaker's picture at the message's first row.
		ind = 0;
		if (chat_mark[j] != "")
		{
			ind = sz + 3;
			img = SteamPic_Of(chat_mark[j]);
			if (img != "")
				drawpic([x, yb, 0], img, [sz, sz], '1 1 1', a, 0);
		}
		Chat_DrawRows(chat_wrap[j], n, chat_wrapn[j] > n, [x + ind, yb], sz, lh, a, maxw - ind);
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
	// Patch 821: the panel, the field and both selections.
	print(sprintf("chat_rows: panel %.2f claims %g x %.1f box %v %v\n", chat_box_a, UI_CursorHeld(), chat_dr_x,
	              chat_box_p, chat_box_s));
	print(sprintf("chat_rows: field %v %v tx %.1f caret %g anchor %g rows %g\n", chat_fld_p, chat_fld_s,
	              chat_fld_tx, chat_caret, chat_anchor, chat_fr_n));
	rows = "";
	for (i = 0; i < chat_fr_n; i = i + 1)
		rows = strcat(rows, " ", ftos(chat_fr[i]));
	print(sprintf("chat_rows: field starts%s ty %.1f\n", rows, chat_fld_ty));
	print(sprintf("chat_rows: scroll %g of %g sent %g |%s|\n", chat_scroll, chat_rows_n, chat_sent_i,
	              strreplace("^", "^^", chat_buf)));
	print(sprintf("chat_rows: sel %g |%s|\n", Chat_SelNorm(),
	              strreplace("\n", "\\n", strreplace("^", "^^", Chat_SelText()))));
	print(sprintf("chat_rows: copied |%s|\n", strreplace("\n", "\\n", strreplace("^", "^^", chat_copied))));
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
	registercvar("hud_chat_y",     "0.9424", CVAR_ARCHIVE);
	registercvar("hud_chat_lines", "6",     CVAR_ARCHIVE);
	registercvar("hud_chat_time",  "30",    CVAR_ARCHIVE);
	registercvar("hud_chat_fade",  "5",     CVAR_ARCHIVE);
	registercvar("hud_chat_size",  "20",    CVAR_ARCHIVE);   // Patch 821: was 24 (HE_MigrateDefaults)
	// Patch 824: the box's width (of the screen's), rows, full height open, opacity.
	registercvar("hud_chat_w",     "0.3",   CVAR_ARCHIVE);
	registercvar("hud_chat_rows",  "12",    CVAR_ARCHIVE);
	registercvar("hud_chat_full",  "1",     CVAR_ARCHIVE);
	registercvar("hud_chat_bg",    "0.5",   CVAR_ARCHIVE);

	chat_typing = FALSE;
	chat_buf    = "";

	Chat_SilenceLoad();

	registercommand("chat_say");
	registercommand("chat_open");       // Patch 392: a plain "open chat" name
	registercommand("chat_rows");
	registercommand("chat_mouse");      // Patch 821: the cursor through the input chain (cl_main.qc)
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
// Patch 477 rounds 23-24: the draft swallows the release of a press it took,
// and passes any other -- a key held into it (the save-lock's `2`, a `+sl_hold`
// or movement bind) would otherwise keep its hold or its motion, since the
// engine runs a stored release only for an up CSQC passes.  0 is a free slot.
float(float scanx, float down) Chat_Took =
{
	local float i, f;

	f = -1;
	for (i = 0; i < CHAT_KN; i = i + 1)
	{
		if (scanx)
		if (chat_kd[i] == scanx)
		{
			if (!down)
				chat_kd[i] = 0;
			return TRUE;
		}
		if (!chat_kd[i])
			f = i;
	}
	if (down)
	if (scanx)
	if (f >= 0)
		chat_kd[f] = scanx;
	return FALSE;
};

void() Chat_TookReset =
{
	local float i;

	for (i = 0; i < CHAT_KN; i = i + 1)
		chat_kd[i] = 0;
};

// Round 25: every key event, from the top of CSQC_InputEvent beside
// Rewind_Track.  A KEYDOWN of a key already down is an OS repeat, and a key held
// into the draft repeats into it -- recorded as the draft's, its release was
// swallowed after all.  0 is a free slot.
void(float evtype, float scanx) Chat_Track =
{
	local float i, f;

	chat_rep = FALSE;
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP)
		return;
	if (!scanx)
		return;
	f = -1;
	for (i = 0; i < CHAT_DN; i = i + 1)
	{
		if (chat_dn[i] == scanx)
		{
			if (evtype == IE_KEYUP)
				chat_dn[i] = 0;
			else
				chat_rep = TRUE;
			return;
		}
		if (!chat_dn[i])
			f = i;
	}
	if (evtype == IE_KEYDOWN)
	if (f >= 0)
		chat_dn[f] = scanx;
};

// Patch 821: every way a draft opens and closes comes through these two, and the
// mouse with them.
void(string t) Chat_Open =
{
	Chat_PrivateClear();
	chat_typing = TRUE;
	chat_buf    = t;
	chat_caret  = strlen(t);
	chat_anchor = -1;
	chat_fr_n   = 0;
	chat_scroll = 0;
	chat_sel_on = FALSE;
	chat_drag   = 0;
	chat_sent_i = -1;
	chat_blink  = cltime;
	chat_ms_ok  = FALSE;
	Chat_TookReset();
	// Only a free mouse: the inspector and the zone editor let go of theirs (and the
	// editor closes) when another claim appears.  One already up shows the cursor.
	if (!UI_CursorHeld())
		UI_CursorClaim(UIC_CHAT);
};

void() Chat_Close =
{
	Chat_PrivateClear();
	chat_typing = FALSE;
	chat_buf    = "";
	chat_caret  = 0;
	chat_anchor = -1;
	chat_sel_on = FALSE;
	chat_drag   = 0;
	chat_scroll = 0;
	UI_CursorRelease(UIC_CHAT);
};

// Cut the field's selection out.  -> there was one.
float() Chat_FieldCut =
{
	local float a, b;

	if (!Chat_FieldSelected())
	{
		chat_anchor = -1;
		return FALSE;
	}
	a = min(chat_anchor, chat_caret);
	b = max(chat_anchor, chat_caret);
	chat_buf = strcat(substring(chat_buf, 0, a), substring(chat_buf, b, strlen(chat_buf) - b));
	chat_caret  = a;
	chat_anchor = -1;
	return TRUE;
};

// Typed or pasted text at the caret, over the selection; the draft is capped so a
// held key cannot grow it past what say itself would take.
void(string s) Chat_Insert =
{
	local float n;

	Chat_FieldCut();
	n = CHAT_DRAFT_MAX - strlen(chat_buf);
	if (n <= 0)
		return;
	if (strlen(s) > n)
		s = substring(s, 0, n);
	chat_buf = strcat(substring(chat_buf, 0, chat_caret), s,
	                  substring(chat_buf, chat_caret, strlen(chat_buf) - chat_caret));
	chat_caret = chat_caret + strlen(s);
};

// The caret to `to`; with Shift held the field's selection stretches there.
void(float to, float shift) Chat_CaretTo =
{
	if (shift)
	{
		if (chat_anchor < 0)
			chat_anchor = chat_caret;
		chat_sel_on = FALSE;            // one selection at a time
	}
	else
		chat_anchor = -1;
	chat_caret = bound(0, to, strlen(chat_buf));
	if (chat_anchor == chat_caret)
		chat_anchor = -1;
};

// The field's selection if it has one, else the history's, onto the clipboard.
void() Chat_Copy =
{
	local string s;

	if (Chat_FieldSelected())
		s = substring(chat_buf, min(chat_anchor, chat_caret), fabs(chat_anchor - chat_caret));
	else
		s = Chat_SelText();
	if (s == "")
		return;
	if (!checkbuiltin(clipboard_set))
		return;
	clipboard_set(0, s);
	chat_copied   = s;
	chat_copied_t = cltime;
};

void(string t) Chat_SentAdd =
{
	local float n, i;
	local string s;

	n = 0;
	if (chat_sent != "")
	{
		n = tokenizebyseparator(chat_sent, "\n");
		if (strcmp(argv(0), t) == 0)
			return;
	}
	s = t;
	for (i = 0; i < n && i < CHAT_SENT_MAX - 1; i = i + 1)
		s = strcat(s, "\n", argv(i));
	chat_sent = s;
};

// Up (d 1) is an older sent line, Down (d -1) a newer one, past the newest the
// line that was being typed.
void(float d) Chat_Recall =
{
	local float n, i;

	n = (chat_sent != "") ? tokenizebyseparator(chat_sent, "\n") : 0;
	i = bound(-1, chat_sent_i + d, n - 1);
	if (i == chat_sent_i)
		return;
	if (chat_sent_i < 0)
		chat_sent_keep = chat_buf;
	chat_sent_i = i;
	chat_buf = (i < 0) ? chat_sent_keep : sprintf("%s", argv(i));
	chat_caret  = strlen(chat_buf);
	chat_anchor = -1;
};

float(vector m, vector p, vector s) Chat_In =
{
	return m_x >= p_x && m_x < p_x + s_x && m_y >= p_y && m_y < p_y + s_y;
};

// MOUSE1 down: the caret or a selection, in the field or the history.  A double
// click takes a word, a triple the whole line.
void() Chat_Press =
{
	local float at, shift;
	local string p;

	if (!chat_ms_ok)
		return;
	shift = (ui_kmods & 3);
	if (cltime - chat_clk_t < CHAT_MULTI && vlen(chat_ms - chat_clk_p) < 6)
		chat_clk_n = chat_clk_n + 1;
	else
		chat_clk_n = 1;
	chat_clk_t = cltime;
	chat_clk_p = chat_ms;
	chat_drag  = 0;

	if (Chat_In(chat_ms, chat_fld_p, chat_fld_s))
	{
		chat_sel_on = FALSE;
		at = Chat_FieldHit(chat_ms);
		if (chat_clk_n == 2)
		{
			chat_anchor = Chat_WordStart(chat_buf, at);
			chat_caret  = Chat_WordEnd(chat_buf, at);
		}
		else if (chat_clk_n >= 3)
		{
			chat_anchor = 0;
			chat_caret  = strlen(chat_buf);
		}
		else
		{
			if (!shift)
				chat_anchor = at;
			else if (chat_anchor < 0)
				chat_anchor = chat_caret;
			chat_caret = at;
			chat_drag  = 1;
			return;                     // the release drops an empty selection
		}
		if (chat_anchor == chat_caret)
			chat_anchor = -1;
		return;
	}
	if (Chat_In(chat_ms, [chat_box_p_x, chat_his_y0], [chat_box_s_x, chat_his_y1 - chat_his_y0]))
	if (Chat_HistHit(chat_ms))
	{
		chat_anchor = -1;
		p = Chat_Plain(chat_ring[chat_hh_j]);
		if (chat_clk_n == 1)
		{
			if (!shift || !Chat_SelNorm())
			{
				chat_sa_j = chat_hh_j;
				chat_sa_t = chat_stamp[chat_hh_j];
				chat_sa_o = chat_hh_o;
			}
			chat_drag = 2;
		}
		else
		{
			chat_sa_j = chat_hh_j;
			chat_sa_t = chat_stamp[chat_hh_j];
			chat_sa_o = (chat_clk_n == 2) ? Chat_WordStart(p, chat_hh_o) : 0;
			chat_hh_o = (chat_clk_n == 2) ? Chat_WordEnd(p, chat_hh_o) : strlen(p);
		}
		chat_sb_j = chat_hh_j;
		chat_sb_t = chat_stamp[chat_hh_j];
		chat_sb_o = chat_hh_o;
		chat_sel_on = TRUE;
		return;
	}
	chat_sel_on = FALSE;                // a press beside both lets the history's go
};

void() Chat_DragTo =
{
	if (chat_drag == 1)
		chat_caret = Chat_FieldHit(chat_ms);
	else if (chat_drag == 2)
	if (Chat_HistHit(chat_ms))
	{
		chat_sb_j = chat_hh_j;
		chat_sb_t = chat_stamp[chat_hh_j];
		chat_sb_o = chat_hh_o;
	}
};

// A key for the field.  A chord is Ctrl without Alt, known by its control code
// or, with no character, by the key under Ctrl (sui_handle_text_input's rule).
void(float scanx, float chary) Chat_FieldKey =
{
	local float shift, ctrl, n, chord, to;

	shift = (ui_kmods & 3);
	ctrl  = (ui_kmods & 48);
	n = strlen(chat_buf);
	chat_caret = bound(0, chat_caret, n);
	if (chat_anchor > n)
		chat_anchor = -1;

	chord = 0;
	if (!(ui_kmods & 12))
	{
		if (chary == 1 || chary == 3 || chary == 24)
			chord = chary + 96;
		else if (chary == 0 && ctrl && scanx >= 'a' && scanx <= 'z')
			chord = scanx;
	}
	if (chord)
	{
		if (chord == 'a' && n > 0)
		{
			chat_anchor = 0;
			chat_caret  = n;
			chat_sel_on = FALSE;
		}
		else if (chord == 'c')
			Chat_Copy();
		else if (chord == 'x' && Chat_FieldSelected())
		{
			Chat_Copy();
			Chat_FieldCut();
		}
		return;
	}
	if (scanx == K_INS && ctrl)
	{
		Chat_Copy();
		return;
	}
	if (scanx == K_BACKSPACE)
	{
		if (!Chat_FieldCut())
		{
			to = chat_caret - 1;
			if (ctrl)                   // the word before the caret, as Ctrl+Left goes
			{
				to = chat_caret;
				while (to > 0 && str2chr(chat_buf, to - 1) == 32)
					to = to - 1;
				to = Chat_WordStart(chat_buf, to);
			}
			if (to >= 0)
			{
				chat_buf = strcat(substring(chat_buf, 0, to), substring(chat_buf, chat_caret, n - chat_caret));
				chat_caret = to;
			}
		}
		return;
	}
	if (scanx == K_DEL)
	{
		if (shift && Chat_FieldSelected())
			Chat_Copy();                // Shift+Delete is a cut
		if (!Chat_FieldCut())
		{
			to = chat_caret + 1;
			if (ctrl)
			{
				to = Chat_WordEnd(chat_buf, chat_caret);
				while (to < n && str2chr(chat_buf, to) == 32)
					to = to + 1;
			}
			if (to <= n)
				chat_buf = strcat(substring(chat_buf, 0, chat_caret), substring(chat_buf, to, n - to));
		}
		return;
	}
	if (scanx == K_LEFTARROW)
	{
		if (ctrl)
		{
			to = chat_caret;
			while (to > 0 && str2chr(chat_buf, to - 1) == 32)
				to = to - 1;
			to = Chat_WordStart(chat_buf, to);
		}
		else if (!shift && Chat_FieldSelected())
			to = min(chat_anchor, chat_caret);
		else
			to = chat_caret - 1;
		Chat_CaretTo(to, shift);
		return;
	}
	if (scanx == K_RIGHTARROW)
	{
		if (ctrl)
		{
			to = Chat_WordEnd(chat_buf, chat_caret);
			while (to < n && str2chr(chat_buf, to) == 32)
				to = to + 1;
		}
		else if (!shift && Chat_FieldSelected())
			to = max(chat_anchor, chat_caret);
		else
			to = chat_caret + 1;
		Chat_CaretTo(to, shift);
		return;
	}
	if (scanx == K_HOME || scanx == K_END)
	{
		Chat_CaretTo((scanx == K_HOME) ? 0 : n, shift);
		return;
	}
	if (scanx == K_UPARROW || scanx == K_DOWNARROW)
	{
		Chat_Recall((scanx == K_UPARROW) ? 1 : -1);
		return;
	}
	if (chary >= 32 && chary < 127)
		Chat_Insert(chr2str(chary));
};

float(float evtype, float scanx, float chary, float devid) Chat_InputEvent =
{
	local string b;

	if (!chat_typing)
	{
		if (evtype != IE_KEYDOWN)
			return FALSE;
		// Round 26: a repeat never opens one -- its press went elsewhere (the
		// rewind's go, held past the count, then opened a draft over the release).
		if (chat_rep)
			return FALSE;
		b = getkeybind(scanx);
		if (b != "messagemode" && b != "messagemode2" && b != "chat_say" && b != "chat_open")
			return FALSE;
		// Rounds 25-26: the keys the rewind's phase takes are its own, whatever
		// they are bound to -- `bind enter messagemode` made its ENTER a draft.
		if (Rewind_Owns(scanx))
			return FALSE;
		Chat_Open("");
		return TRUE;
	}

	// Typing.  Presses belong to the draft except the console's own key, which
	// has to stay reachable; releases are its own only (Chat_Took).  The cursor
	// is the panel's, and TRUE for it keeps the view still.
	if (evtype == IE_MOUSEABS)
	{
		chat_ms = [scanx, chary];
		chat_ms_ok = TRUE;
		Chat_DragTo();
		return TRUE;
	}
	if (evtype == IE_KEYUP)
	{
		if (scanx == K_MOUSE1)
		{
			if (chat_drag == 1 && chat_anchor == chat_caret)
				chat_anchor = -1;
			if (chat_drag == 2 && chat_sa_j == chat_sb_j && chat_sa_o == chat_sb_o)
				chat_sel_on = FALSE;
			chat_drag = 0;
		}
		return Chat_Took(scanx, FALSE);
	}
	if (evtype != IE_KEYDOWN)
		return TRUE;

	if (getkeybind(scanx) == "toggleconsole")
	{
		Chat_Close();                    // abandon, do not fight the console
		return FALSE;
	}
	if (!chat_rep)                   // round 25: a repeat of a key held into the draft is not its press
		Chat_Took(scanx, TRUE);
	chat_blink = cltime;

	if (scanx == K_ENTER || scanx == K_KP_ENTER)
	{
		if (strtrim(chat_buf) != "")
		{
			if (chat_private == "")       // a private line never comes back to go public
				Chat_SentAdd(chat_buf);
			if (chat_private != "")
				localcmd(sprintf("cmd friend message %s %s\n", chat_private, uri_escape(chat_buf)));
			else if (!WarpOp_Chat(chat_buf))
				Chat_RunSafe("cmd say", chat_buf);
		}
		Chat_Close();
		return TRUE;
	}
	if (scanx == K_ESCAPE)
	{
		Chat_Close();
		return TRUE;
	}
	if (scanx == K_MOUSE1)
	{
		if (!chat_rep)
			Chat_Press();
		return TRUE;
	}
	if (scanx == K_MOUSE2)
	{
		Chat_Copy();                     // as ent_view's mouse2 copies
		return TRUE;
	}
	if (scanx == K_MWHEELUP || scanx == K_MWHEELDOWN || scanx == K_PGUP || scanx == K_PGDN)
	{
		if (scanx == K_MWHEELUP)   chat_scroll = chat_scroll + 3;
		if (scanx == K_MWHEELDOWN) chat_scroll = chat_scroll - 3;
		if (scanx == K_PGUP)       chat_scroll = chat_scroll + max(1, chat_dr_cap - 1);
		if (scanx == K_PGDN)       chat_scroll = chat_scroll - max(1, chat_dr_cap - 1);
		chat_scroll = max(0, chat_scroll);  // the draw bounds the top
		return TRUE;
	}

	if (scanx == 'v' || scanx == K_INS)
	if (!(ui_kmods & 48) || scanx == 'v')   // Ctrl+Insert is a copy
	if (sui_paste_ask())                // Patch 667: Chat_Paste gets what the player allows
		return TRUE;

	Chat_FieldKey(scanx, chary);
	return TRUE;
};

// Patch 667: one pasted character, into a draft being typed.  -> the draft's.
float(float c) Chat_Paste =
{
	if (!chat_typing)
		return FALSE;
	Chat_Insert(chr2str(c));
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
	Chat_Open(t);
	return TRUE;
};

/*
  BARE `say` OPENS THE DRAFT; `say <text>` IS A SEND.

  The engine offers the whole command here before it sends anything
  (zqtp.c:3774), and patch 341 took BOTH forms -- which broke every caller that
  passes text.  `say !r` and `say !m` were the R and M binds in default.cfg until Patch 851
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
	if (WarpOp_Chat(args))
		return TRUE;           // Patch 753: `!r` / `!m` predicted, not sent as chat
	if (strtrim(args) != "")
		return FALSE;          // `say <text>` is a send, not a draft
	Chat_Open("");
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

void(string who, string nm) Chat_Private =
{
	Chat_Open("");
	chat_private = strzone(who);
	chat_private_name = strzone(nm);
};
