/*
===========================================================================
  cl_chat.qc -- the bottom-left chatbox.  Patch 340.

  THE HOOK, AND THE ONE RULE IT COMES WITH.  Defining CSQC_Parse_Print makes
  the engine route EVERY svc_print through it and print NOTHING itself
  (pr_csqc.c:9595 returns true unconditionally once the function exists --
  the QC return value is not read).  So every level this file does not handle
  is a level that vanishes from the console and the log.  Non-chat levels are
  therefore re-emitted with print(), byte for byte, and only level 3
  (PRINT_CHAT, bothdefs.h:1140) becomes a chatbox line.  What IS given up,
  deliberately: the engine's notify area (top-left scroll) and its chat
  sounds for lines this file drops as silenced.  The console keeps everything.

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

string chat_ring[CHAT_RING];    // built display lines, strzone'd
float  chat_stamp[CHAT_RING];   // time of arrival; 0 = slot empty
float  chat_write;              // next ring slot

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

void(vector scr) Chat_Draw =
{
	local float life, fade, lines, szu, sz, lh, x, yb, maxw;
	local float i, j, age, a;
	local float ord[CHAT_RING];
	local float ordn, nl, k, cut;
	local string draft, piece;

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

	Font_Set(ui_font_ui);

	/*
	  THE DRAFT FIRST, at the very bottom, because it is what the box makes
	  room FOR: every stored line starts one wrapped-draft-line higher while
	  you type.  Wrapped rather than clipped -- a 200-character say is legal
	  and reading only its tail while you edit it is not typing.

	  PATCH 341: THE LINE IS ALWAYS THERE, typing or not.  A box that grew by
	  a line when you started to type is a box that jumped; the reserved line
	  with its idle blinking underscore is the room the messages were always
	  shifted up into.  Idle draws dim, typing draws white -- the underscore
	  is the prompt, not a state.
	*/
	nl = 0;
	if (chat_typing)
		draft = strcat("> ", chat_buf, (floor(time * 2) & 1) ? "_" : " ");
	else
		/*
		  PATCH 341bis: A BLANK RESERVED LINE, not a blinking ghost.  The room
		  is the point -- messages always sit one line higher -- but an idle
		  underscore flashing in the corner reads as a stuck draft, which is
		  exactly the report.  A single space wraps to exactly one line and
		  draws nothing.
		*/
		draft = " ";
	{
		// count wrapped lines of the draft
		k = 0;
		while (k < strlen(draft))
		{
			piece = "";
			cut = k;
			while (cut < strlen(draft))
			{
				piece = strcat(piece, substring(draft, cut, 1));
				if (stringwidth(piece, TRUE, [sz, sz]) > maxw)
					break;
				cut = cut + 1;
			}
			if (cut == k)
				cut = k + 1;              // one char wider than the box: take it anyway
			drawstring([x + 1, yb - lh * (nl + 1) + 1],
			           substring(draft, k, cut - k), [sz, sz], '0 0 0', 0.6, 0);
			drawstring([x, yb - lh * (nl + 1)],
			           substring(draft, k, cut - k), [sz, sz],
			           chat_typing ? '1 1 1' : '0.40 0.40 0.45', 1, 0);
			nl = nl + 1;
			k = cut;
		}
		yb = yb - lh * nl;
	}

	// Newest first, skipping the expired.  A negative age is a stamp from a
	// PREVIOUS map (time restarted under it) -- expired by definition, which
	// is how the ring clears itself on a map change with no hook.
	ordn = 0;
	for (i = 0; i < CHAT_RING && ordn < lines; i = i + 1)
	{
		j = chat_write - 1 - i;
		while (j < 0)
			j = j + CHAT_RING;
		if (chat_ring[j] == "" || chat_stamp[j] <= 0)
			continue;
		age = time - chat_stamp[j];
		if (age < 0 || age > life)
			continue;
		ord[ordn] = j;
		ordn = ordn + 1;
	}

	if (!ordn)
	{
		Font_Reset();
		return;
	}

	Font_Set(ui_font_ui);
	for (i = 0; i < ordn; i = i + 1)
	{
		j   = ord[i];
		age = time - chat_stamp[j];
		a   = (age <= life - fade) ? 1 : 1 - (age - (life - fade)) / fade;
		if (a <= 0)
			continue;
		yb = yb - lh;
		// Shadowed like the rest of the HUD's text: readable over both a dark
		// leaf and a white skybox.
		drawstring([x + 1, yb + 1], Chat_Fit(chat_ring[j], maxw, sz),
		           [sz, sz], '0 0 0', a * 0.6, 0);
		drawstring([x, yb], Chat_Fit(chat_ring[j], maxw, sz),
		           [sz, sz], '1 1 1', a, 0);
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
	  other hud_*_x/y), six lines, gone after 30 s with the last 5 s spent
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
		if (b != "messagemode" && b != "messagemode2" && b != "chat_say")
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
	if (chary >= 32 && chary < 127 && strlen(chat_buf) < 128)
		chat_buf = strcat(chat_buf, chr2str(chary));
	return TRUE;
};

float(string cmd) Chat_ConsoleCommand =
{
	if (argv(0) != "chat_say")
		return FALSE;
	chat_typing = TRUE;
	chat_buf    = "";
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
