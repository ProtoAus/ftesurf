/*
===========================================================================
  cl_account.qc -- the client's half of sv_account.qc (Patches 615, 617).

  `link` opens a box.  The player types the code from the sign-in page into
  it; the lobby is sent a digest of the code with the engine's signature for
  it, and answers with the account's name; Enter on "link this game to X?"
  signs the lobby's number and links.  `acct_hello <nonce>` is the server's
  connect challenge, stuffed in answer to our `cmd acct_hello`.  The three sign
  ticks -3, -4 and -2, which no run does (sv_account.qc has why).

  THE SIGNING IS ASKED FOR FROM HERE because rec_sign refuses a server's
  stufftext (cl_receipt.c): a server may hand this VM a nonce, not a signature.

  A LINK IS MADE BY THE KEYBOARD AND BY NOTHING ELSE (Patch 617).  A console
  command can be typed FOR the player: by a server's stufftext, by a bind or an
  `in` timer another server left, by whoever can write to the connection.
  Patch 615 took the code as `link <code>` and the consent as `link <number>`,
  and a probe server typed both.  Here no console command carries a code or
  makes a signature for one: both come only from Account_InputEvent, which is
  offered the ENGINE's key events (cl_input_real, set by CSQC_InputEvent and by
  nothing a command can reach).  `vote key` and `hud_edit ui` feed the input
  chain from the console; they do not reach this file, and tools/p615link.py
  presses Enter both ways to show it.

  SO THE CODE IS NEVER A COMMAND'S ARGUMENT either.  A cvar named `link`, left
  by a server the player was on, makes `link ABCD...` a cvar set that goes out
  in the open; a bare `link` gives it nothing to send.

  THE CODE NEVER LEAVES THIS VM.  The server is sent a digest of it, and so is
  anyone reading the wire.  A code is 50 bits, so that digest can be searched
  given days: what keeps the code is that the ask in the same packet claims it.

  NOTHING A SERVER SENDS REACHES localcmd UNCHECKED.  A nonce is 32 lowercase
  hex and the lobby's number six digits, or they are dropped; an account's name
  is only ever drawn.
===========================================================================
*/

#define ACCT_CODELEN    10      // surfd's CODE_LEN
#define ACCT_ALPHABET   "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  // ...and its CODE_ALPHABET

#define ACCT_UI_NONE    0
#define ACCT_UI_CODE    1       // typing the code
#define ACCT_UI_WAIT    2       // sent, and waiting for the lobby
#define ACCT_UI_ASK     3       // the lobby named the account: link?
#define ACCT_UI_NOTE    4       // how it ended, until a key or a few seconds
#define ACCT_UI_ARM     0.6     // s the question ignores keys after it appears
#define ACCT_UI_PATIENCE 20     // s waited for the lobby (it gives surfd 15)
#define ACCT_UI_LINGER  8       // s an ending stays up
#define ACCT_UI_IDLE    45      // s an untouched, empty code box stays up
#define ACCT_UI_OWED    60      // s a late answer to a confirm is still shown
#define ACCT_UI_KN      16      // keys down at once that are followed

float  acct_cl_asks;        // hellos asked for on this map
float  acct_cl_at;          // when the last was, or when this VM first drew
float  acct_cl_wait;        // s from acct_cl_at to the next ask
float  acct_cl_got;         // the server answered one
float  acct_cl_taken;       // `link` or `acct_hello` was somebody's cvar when this VM loaded

float  cl_input_real;       // TRUE only inside the engine's own CSQC_InputEvent call (cl_main.qc)
float  acct_ui;             // ACCT_UI_*
float  acct_ui_t;           // cltime it got there
float  acct_ui_bad;         // cltime Enter last found the code short
string acct_ui_buf;         // the code as typed so far: its alphabet only, zoned
string acct_ui_pin;         // the lobby's number, zoned
string acct_ui_to;          // the account it would link to, zoned; drawn, never run
string acct_ui_from;        // ...and the one it would leave
string acct_ui_note;        // the ending's words
float  acct_ui_good;        // ...and whether it was a link
float  acct_ui_conf;        // the wait is for a CONFIRM: it is out, and cannot be taken back
float  acct_ui_owed;        // cltime a confirm went out whose answer has not been shown
float  acct_ui_kd[ACCT_UI_KN];      // keys down, as the engine's own events said
float  acct_ui_ours[ACCT_UI_KN];    // ...and whether the box took that press

void() Account_RegisterCvars =
{
	// A NAME IS ONLY FREE UNTIL A SERVER TAKES IT.  The engine and plugins have
	// no `link`, but a server the player was on can leave a cvar of that name,
	// and the registration below then fails without a word.  Read before
	// registering: afterwards it is a command.
	acct_cl_taken = FALSE;
	if (cvar_type("link"))
		acct_cl_taken = TRUE;
	if (cvar_type("acct_hello"))
		acct_cl_taken = TRUE;
	registercommand("link");
	registercommand("acct_hello");
	registercommand("acct_ask");
	registercommand("acct_note");
	acct_cl_asks = 0;
	acct_cl_at   = 0;
	acct_cl_got  = FALSE;
	acct_ui      = ACCT_UI_NONE;
	acct_ui_buf  = "";
	acct_ui_pin  = "";
	acct_ui_to   = "";
	acct_ui_from = "";
	acct_ui_note = "";
};

// `s` kept in place of `old`.  `s` must not BE `old`: it is freed first.
string(string old, string s) Account_Keep =
{
	if (old != "")
		strunzone(old);
	if (s == "")
		return "";
	return strzone(s);
};

// TRUE for `n` characters, each from `lo` to `hi`, digits, or nothing else.
float(string s, float n, float lo, float hi) Account_Is =
{
	local float i, c;

	if (strlen(s) != n)
		return FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (c >= '0')
		if (c <= '9')
			continue;
		if (c < lo)
			return FALSE;
		if (c > hi)
			return FALSE;
	}
	return TRUE;
};

// 32 hex of a tagged SHA-256: surfd's code_tag, ask_nonce and confirm_nonce.
string(string tag, string text) Account_Digest =
{
	return substring(strtolower(digest_hex("SHA256", strcat(tag, text))), 0, 32);
};

void(float state) Account_UiSet =
{
	acct_ui   = state;
	acct_ui_t = cltime;
};

void(float good, string words) Account_UiEnd =
{
	acct_ui_owed = 0;
	acct_ui_note = Account_Keep(acct_ui_note, words);
	acct_ui_good = good;
	acct_ui_buf  = Account_Keep(acct_ui_buf, "");
	acct_ui_pin  = Account_Keep(acct_ui_pin, "");
	Account_UiSet(ACCT_UI_NOTE);
	print(sprintf("%s %s\n", good ? "^2steam:^7" : "^1steam:^7", words));
};

void() Account_UiClose =
{
	acct_ui_buf = Account_Keep(acct_ui_buf, "");
	acct_ui_pin = Account_Keep(acct_ui_pin, "");
	Account_UiSet(ACCT_UI_NONE);
};

// The ask timer, the connect check, and the box's own clocks.
void() Account_Frame =
{
	local float c;

	if (acct_ui == ACCT_UI_WAIT)
	if (cltime - acct_ui_t > ACCT_UI_PATIENCE)
	{
		// A confirm may still land: its answer is shown if it comes (acct_note).
		c = acct_ui_conf ? cltime : 0;
		Account_UiEnd(FALSE, "The server did not answer. Try again in a minute.");
		acct_ui_owed = c;
	}
	if (acct_ui == ACCT_UI_NOTE)
	if (cltime - acct_ui_t > ACCT_UI_LINGER)
		Account_UiClose();
	// Opened and never typed in: a box a server opened must not sit on the keys.
	if (acct_ui == ACCT_UI_CODE)
	if (acct_ui_buf == "")
	if (cltime - acct_ui_t > ACCT_UI_IDLE)
		Account_UiClose();

	if (acct_cl_got)
		return;
	if (acct_cl_asks >= 2)
		return;
	// cltime, NOT time: the game clock jumps at connect (measured: 33.7 on the
	// first frame, 116.5 on the next), which fired this timer at once and could
	// fire the retry with it.
	if (!acct_cl_at)
	{
		// Three to seven seconds in, not the same instant as everyone else on
		// the map: the engine refuses uri_post past 32 in flight.
		acct_cl_at   = cltime;
		acct_cl_wait = 3 + random() * 4;
		return;
	}
	if (cltime - acct_cl_at < acct_cl_wait)
		return;
	acct_cl_asks = acct_cl_asks + 1;
	acct_cl_at   = cltime;
	acct_cl_wait = 8;
	if (acct_cl_taken)
	{
		// Said here, where the connect line would be, and not at load, where
		// it scrolls away under the map's own output.
		print("^1steam:^7 another server changed this game's ^3link^7 command, so it cannot "
		      "be linked now. Restart the game first, and never type a code after ^3link^7\n");
		acct_cl_asks = 2;
		return;
	}
	localcmd("cmd acct_hello\n");
};

/*
  WHICH KEYS ARE DOWN, AND WHOSE PRESS EACH WAS.  From the engine's events only
  (cl_input_real): cl_chat.qc's chat_rep answers the same question, but
  `vote key` feeds Chat_Track from the console, so text could make a held Enter
  look fresh.  -1 = not down; else the slot.
*/
float(float scanx) Account_Slot =
{
	local float i;

	for (i = 0; i < ACCT_UI_KN; i = i + 1)
		if (acct_ui_kd[i] == scanx)
			return i;
	return -1;
};

float(float scanx) Account_Press =
{
	local float i;

	for (i = 0; i < ACCT_UI_KN; i = i + 1)
	{
		if (!acct_ui_kd[i])
		{
			acct_ui_kd[i]   = scanx;
			acct_ui_ours[i] = FALSE;
			return i;
		}
	}
	return -1;                              // sixteen keys down: not followed, never ours
};

void() Account_Backspace =
{
	if (acct_ui_buf != "")
		acct_ui_buf = Account_Keep(acct_ui_buf, substring(acct_ui_buf, 0, strlen(acct_ui_buf) - 1));
	acct_ui_t = cltime;
};

/*
  A key event, FROM THE ENGINE.  cl_main.qc offers it only while cl_input_real
  is set and this checks again: a console command that feeds the input chain
  must find nobody here.

  Keys only.  The mouse stays the game's, so the box holds no cursor claim and
  `hud_edit ui`, which drives whatever holds one, has nothing of ours to drive.

  PRESSES ARE TAKEN, RELEASES NEVER.  A press the box takes ran no bind, so its
  release has nothing to undo and may go on to the game; a release the box
  swallowed would be the game's `-forward` if the press was older than this VM
  (a key held through a map change), and the player walks until they tap it.
  What IS kept from the game is the REPEAT of a press the box took, for as long
  as the key stays down, box open or not: the first cut let those through once
  the box closed, and a held `2` loaded a saveloc, a held digit cast a vote.
*/
float(float evtype, float scanx, float chary) Account_InputEvent =
{
	local float c, slot;

	if (!cl_input_real)
		return FALSE;
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP)
		return FALSE;
	if (!scanx)
		return FALSE;
	if (scanx >= K_MOUSE1)                  // mice, wheels, pads
		return FALSE;
	slot = Account_Slot(scanx);
	if (evtype == IE_KEYUP)
	{
		if (slot >= 0)
			acct_ui_kd[slot] = 0;
		return FALSE;
	}
	if (slot >= 0)
	{
		// An OS repeat.  Of the game's press: the game's.  Of ours: nobody's,
		// but Backspace's, and a held Enter must never answer a question it
		// did not see.
		if (!acct_ui_ours[slot])
			return FALSE;
		if (scanx == K_BACKSPACE)
		if (acct_ui == ACCT_UI_CODE)
			Account_Backspace();
		return TRUE;
	}
	slot = Account_Press(scanx);
	if (!acct_ui)
		return FALSE;
	if (getkeybind(scanx) == "toggleconsole")
		return FALSE;
	if (slot >= 0)
		acct_ui_ours[slot] = TRUE;

	if (acct_ui == ACCT_UI_NOTE)
	{
		Account_UiClose();
		return TRUE;
	}
	if (acct_ui == ACCT_UI_WAIT)
	{
		// An ask can be dropped.  A confirm is already with surfd: saying
		// "cancelled" over it was a lie the review caught, so Esc waits too.
		if (scanx == K_ESCAPE)
		if (!acct_ui_conf)
		{
			localcmd("cmd link cancel\n");
			Account_UiClose();
			print("^5steam:^7 link cancelled\n");
		}
		return TRUE;
	}
	if (acct_ui == ACCT_UI_ASK)
	{
		if (cltime - acct_ui_t < ACCT_UI_ARM)
			return TRUE;                    // a key already on its way down when it appeared
		if (scanx == K_ESCAPE || chary == 'n' || chary == 'N')
		{
			localcmd("cmd link cancel\n");
			Account_UiClose();
			print("^5steam:^7 link cancelled\n");
			return TRUE;
		}
		if (scanx == K_ENTER || scanx == K_KP_ENTER || chary == 'y' || chary == 'Y')
		{
			localcmd(sprintf("cmd link %s\nrec_sign %s -4 - 0\n", acct_ui_pin,
			                 Account_Digest("ftesurf-confirm ",
			                                strcat(acct_ui_buf, " ", acct_ui_pin))));
			Account_UiSet(ACCT_UI_WAIT);
			acct_ui_conf = TRUE;
			acct_ui_owed = cltime;
			print("^5steam:^7 linking\n");
		}
		return TRUE;
	}

	// ACCT_UI_CODE
	if (scanx == K_ESCAPE)
	{
		Account_UiClose();
		print("^5steam:^7 link cancelled\n");
		return TRUE;
	}
	if (scanx == K_BACKSPACE)
	{
		Account_Backspace();
		return TRUE;
	}
	if (scanx == K_ENTER || scanx == K_KP_ENTER)
	{
		if (strlen(acct_ui_buf) != ACCT_CODELEN)
		{
			acct_ui_bad = cltime;
			print(sprintf("^5steam:^7 a code is %g characters, and the box has %g\n",
			              ACCT_CODELEN, strlen(acct_ui_buf)));
			return TRUE;
		}
		// The buffer is its alphabet by construction and the rest is hex.
		localcmd(sprintf("cmd link %s\nrec_sign %s -3 - 0\n",
		                 Account_Digest("ftesurf-code ", acct_ui_buf),
		                 Account_Digest("ftesurf-link ", acct_ui_buf)));
		Account_UiSet(ACCT_UI_WAIT);
		acct_ui_conf = FALSE;
		print("^5steam:^7 code sent\n");
		return TRUE;
	}
	c = chary;
	if (c >= 'a')
	if (c <= 'z')
		c = c - 32;
	if (c > 32)
	if (c < 127)
	if (strlen(acct_ui_buf) < ACCT_CODELEN)
	if (strstrofs(ACCT_ALPHABET, chr2str(c)) >= 0)
	{
		acct_ui_buf = Account_Keep(acct_ui_buf, strcat(acct_ui_buf, chr2str(c)));
		acct_ui_t   = cltime;
	}
	return TRUE;
};

// A name the lobby sent, for drawing: no colour or link markup, and not long.
string(string s) Account_Plain =
{
	s = strreplace("^", "", s);
	return substring(s, 0, 40);
};

float(string cmd) Account_ConsoleCommand =
{
	if (argv(0) == "acct_hello")
	{
		acct_cl_got = TRUE;
		if (Account_Is(argv(1), 32, 'a', 'f'))
			localcmd(sprintf("rec_sign %s -2 - 0\n", argv(1)));
		return TRUE;
	}

	/*
	  The lobby's answers to the box.  Either may be stuffed by anyone, so each
	  is believed only while the box is WAITING for it, changes only what is
	  drawn, and the number is used only under a key press that follows.
	*/
	if (argv(0) == "acct_ask")
	{
		if (acct_ui != ACCT_UI_WAIT)
			return TRUE;
		if (acct_ui_buf == "")
			return TRUE;
		if (!Account_Is(argv(1), 6, '0', '9'))
			return TRUE;
		acct_ui_pin  = Account_Keep(acct_ui_pin, argv(1));
		acct_ui_to   = Account_Keep(acct_ui_to, Account_Plain(argv(2)));
		acct_ui_from = Account_Keep(acct_ui_from, Account_Plain(argv(3)));
		Account_UiSet(ACCT_UI_ASK);
		print(sprintf("^5steam:^7 link this game to ^3%s^7? Enter to link, Esc to cancel\n",
		              acct_ui_to));
		return TRUE;
	}
	if (argv(0) == "acct_note")
	{
		if (acct_ui != ACCT_UI_WAIT)
		{
			if (!acct_ui_owed)
				return TRUE;
			if (cltime - acct_ui_owed > ACCT_UI_OWED)
				return TRUE;
		}
		if (argv(1) == "linked")
			Account_UiEnd(TRUE, sprintf("This game is now linked to %s.", Account_Plain(argv(2))));
		else if (argv(1) == "banned")
			Account_UiEnd(FALSE, "That Steam account is banned from the leaderboards.");
		else if (argv(1) == "slow")
			Account_UiEnd(FALSE, "Too many tries. Wait a minute.");
		else if (argv(1) == "soon")
			Account_UiEnd(FALSE, "One code at a time. Wait a few seconds.");
		else if (argv(1) == "stale")
			Account_UiEnd(FALSE, "That took too long. Type link and enter the code again.");
		else if (argv(1) == "later")
			Account_UiEnd(FALSE, "The leaderboard cannot check that right now. Try again in a minute.");
		else if (argv(1) == "server")
			Account_UiEnd(FALSE, "The leaderboard does not know this server by the address you joined it on.");
		else if (argv(1) == "proof")
			Account_UiEnd(FALSE, "This game could not sign for the code. Try again.");
		else if (argv(1) == "busy")
			Account_UiEnd(FALSE, "The server is busy. Try again in a moment.");
		else if (argv(1) == "off")
			Account_UiEnd(FALSE, "This server has no leaderboard to link to.");
		else if (argv(1) == "silent")
			Account_UiEnd(FALSE, "The leaderboard did not answer. Try again in a minute.");
		else
			Account_UiEnd(FALSE, "That code is not valid or has expired. Get a new one from the sign-in page.");
		return TRUE;
	}
	if (argv(0) != "link")
		return FALSE;

	if (acct_cl_taken)
	{
		print("^1steam:^7 another server changed this game's ^3link^7 command. Restart the "
		      "game first\n");
		return TRUE;
	}
	if (argv(1) != "")
		print("^5steam:^7 the code goes in the box, not after ^3link^7\n");
	if (acct_ui)
	if (acct_ui != ACCT_UI_NOTE)
		return TRUE;                        // one is up: a second `link` is not a reset
	acct_ui_buf  = Account_Keep(acct_ui_buf, "");
	acct_ui_bad  = 0;
	acct_ui_owed = 0;
	Account_UiSet(ACCT_UI_CODE);
	print("^5steam:^7 link box open. Close the console and type the code from the sign-in page\n");
	localcmd("cmd link\n");               // the lobby says where this install stands
	return TRUE;
};

// The box.  Low on the screen: `link` is typed in a console that covers the top.
void(vector scr) Account_Draw =
{
	local float  w, h, lsz, pad, y, y0, x, i, n;
	local string s, foot;

	if (!acct_ui)
		return;

	Font_Set(ui_font_ui);
	lsz = Font_Px(9 * ui_cv_scale);
	pad = 8 * ui_cv_scale;
	w   = min(250 * ui_cv_scale, scr_x * 0.9);
	h   = lsz * 8.6 + pad * 2;
	x   = (scr_x - w) * 0.5;
	y0  = min(scr_y * 0.56, scr_y - h - pad);
	y   = y0;

	drawfill([x, y], [w, h], '0.10 0.13 0.17', 0.94, 0);
	drawfill([x, y], [w, lsz + pad], '0.35 0.49 0.67', 1, 0);
	HUD_Text([x + pad, y + pad * 0.5], "Link Steam", lsz, '1 1 1', 1);
	y = y + lsz + pad * 1.6;

	foot = "Esc  cancel";
	if (acct_ui == ACCT_UI_CODE)
	{
		HUD_Text([x + pad, y], "Type the code from the sign-in page", lsz, '0.85 0.88 0.92', 1);
		y = y + lsz * 1.6;
		// ABCDE-FGH__ : what is typed, then what is still owed.
		n = strlen(acct_ui_buf);
		s = "";
		for (i = 0; i < ACCT_CODELEN; i = i + 1)
		{
			if (i == ACCT_CODELEN / 2)
				s = strcat(s, "-");
			s = strcat(s, (i < n) ? substring(acct_ui_buf, i, 1) : "_");
		}
		drawfill([x + pad, y - lsz * 0.3], [w - pad * 2, lsz * 2.1], '0.05 0.07 0.10', 1, 0);
		HUD_TextC([x + w * 0.5, y], s, lsz * 1.5,
		          (cltime - acct_ui_bad < 0.6) ? '1 0.35 0.30' : '1.00 0.90 0.55', 1);
		foot = "Enter  continue     Esc  cancel";
	}
	else if (acct_ui == ACCT_UI_WAIT)
	{
		HUD_Text([x + pad, y], acct_ui_conf ? "Linking..." : "Asking the leaderboard...", lsz,
		         '0.85 0.88 0.92', 1);
		foot = acct_ui_conf ? "" : "Esc  cancel";
	}
	else if (acct_ui == ACCT_UI_ASK)
	{
		HUD_Text([x + pad, y], "Link this game to the Steam account", lsz, '0.85 0.88 0.92', 1);
		y = y + lsz * 1.6;
		HUD_TextC([x + w * 0.5, y], acct_ui_to, lsz * 1.4, '1.00 0.90 0.55', 1);
		y = y + lsz * 2.2;
		if (acct_ui_from != "")
			HUD_Text([x + pad, y], sprintf("It is linked to %s now, and would move", acct_ui_from),
			         lsz * 0.9, '1 0.60 0.45', 1);
		foot = "Enter  link     Esc  cancel";
	}
	else
	{
		// Two lines of it at most: the endings are short.
		s = acct_ui_note;
		n = strlen(s);
		i = n;
		if (stringwidth(s, TRUE, [lsz, lsz]) > w - pad * 2)
		{
			for (i = floor(n * 0.55); i > 0; i = i - 1)
				if (substring(s, i, 1) == " ")
					break;
		}
		HUD_Text([x + pad, y], substring(s, 0, i), lsz, acct_ui_good ? '0.55 0.95 0.60' : '1 0.60 0.45', 1);
		if (i < n)
			HUD_Text([x + pad, y + lsz * 1.4], substring(s, i + 1, n), lsz,
			         acct_ui_good ? '0.55 0.95 0.60' : '1 0.60 0.45', 1);
		foot = "Any key  close";
	}
	HUD_Text([x + pad, y0 + h - lsz - pad * 0.6], foot, lsz * 0.9, '0.55 0.58 0.62', 1);
	Font_Reset();
};
