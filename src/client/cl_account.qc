/*
===========================================================================
  cl_account.qc -- the client's half of sv_account.qc (Patches 615, 617, 619, 625).

  `link` opens a box, and so does a first connect that finds the install
  unlinked.  ENTER STARTS A LINK, ALL OF IT UNDER THAT ONE KEY PRESS (625): this
  VM makes a secret (the opener), names the start from it, has the engine sign
  both, sends that to the lobby, and has the engine open the sign-in page with
  the opener in its address.  The page the player signs in on shows a NUMBER;
  the lobby says whose account signed in, the box asks "link this game to X?"
  and for that number, and Enter signs the lobby's own number and sends the
  page's with it.  A code TYPED into the box (a sign-in that did not start
  here) is 617's flow.  `acct_hello <nonce>` is the server's connect challenge.

  THE ENGINE SIGNS, THROUGH BUILTINS (625).  Through 619 this file asked with a
  console line, `rec_sign`, and console lines are text: game code builds them
  in fifty places out of pieces a server can supply.  `acct_sign` has no text
  in front of it, signs a statement no older engine can produce, and refuses
  to ask, confirm or start unless a device's key press is being delivered
  (cl_receipt.c).  `acct_browse` opens ONE page, the sign-in page, and takes
  only the opener.  Without the builtins this file links nothing and says the
  game needs an update: surfd takes no proof signed the old way.

  THE START'S CODE IS PUBLIC AND LINKS NOTHING.  It is a digest of the opener
  and crosses the wire in the clear.  What ties the browser to THIS game is the
  page's number, which only whoever signed in can see and only a key press here
  can send.  THE NUMBER IS NOT SENT EITHER: what goes to the lobby is a digest
  of it with this VM's opener (Account_Confirm).  A player can be sent to sign
  in for somebody else's start and then be asked, by a box a server's text
  raised, for the number that page showed; four digits in the clear would be
  that somebody's link.  A digest with OUR opener is no use to them.
  (surfd/accounts.py has the cuts before this and what their reviews did.)

  NO KEY BUT ENTER, ESC, DIGITS AND A CODE'S OWN LETTERS.  The first cut took
  Tab for "I have a code", and Alt+Tab is how a player gets to the browser.
  The prompt that comes up by itself and the wait for the browser take Enter
  and Esc only, and the game keeps every other key.

  THE OPENER is the engine's random bytes hashed with a pool of this VM's own
  (Account_Stir: every frame's timing, every key and the mouse's moves; frame
  times jitter at the 0.1 microsecond level, measured).  The start's signature
  is an offline test for a guessed opener, so it is 96 bits.

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

  A TYPED CODE NEVER LEAVES THIS VM.  The server is sent a digest of it under
  a salt drawn for that ask, and so is anyone reading the wire.  Twelve
  characters and a salt since Patch 625: ten under a bare digest were thirty
  GPU-hours or one table, and the packet that claims the code can be dropped.

  NOTHING A SERVER SENDS REACHES localcmd UNCHECKED.  A nonce is 32 lowercase
  hex and the lobby's number six digits, or they are dropped; an account's name
  is only ever drawn.
===========================================================================
*/

#define ACCT_CODELEN    12      // surfd's CODE_LEN
#define ACCT_NOLEN      4       // ...and its SHOWN_LEN: the sign-in page's number
#define ACCT_KEYLEN     24      // ...and its opener's length: 96 bits of the pool
#define ACCT_ALPHABET   "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  // ...and its CODE_ALPHABET

#define ACCT_UI_NONE    0
#define ACCT_UI_CODE    1       // typing the code
#define ACCT_UI_WAIT    2       // sent, and waiting for the lobby
#define ACCT_UI_ASK     3       // the lobby named the account: link?
#define ACCT_UI_NOTE    4       // how it ended, until a key or a few seconds
#define ACCT_UI_PROMPT  5       // "press Enter to link"
#define ACCT_UI_GO      6       // started: the player is signing in, the lobby is waiting
#define ACCT_UI_PROMPTLIFE 40   // s an unanswered prompt stays up
#define ACCT_UI_GOLIFE  660     // s a start is waited on here (the lobby gives up at 600)
#define ACCT_LINK_URL   "proto.bar/ftesurf/board/link"
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
float  acct_ui_copied;      // the sign-in address went to the clipboard
float  acct_ui_opened;      // ...and the engine opened it in a browser
float  acct_cl_old;         // the engine has no acct_sign: nothing here can link
float  acct_ui_free;        // the prompt came up by itself: Enter and Esc are its, the rest the game's
string acct_ui_go;          // the code of a start the lobby is still waiting on, zoned
string acct_ui_key;         // ...and the opener this VM made for it: ACCT_KEYLEN hex, zoned
string acct_pool;           // SHA-256 of everything Account_Stir was given: 64 hex, zoned
float  acct_pool_in;        // input events since the last frame, folded; stirred with the frame
float  acct_ui_num;         // the question wants the sign-in page's number with its Enter
string acct_ui_no;          // ...and that number as typed so far: digits only, zoned
float  acct_ui_owed;        // cltime a confirm went out whose answer has not been shown
float  acct_ui_kd[ACCT_UI_KN];      // keys down, as the engine's own events said
float  acct_ui_ours[ACCT_UI_KN];    // ...and whether the box took that press

// The engine's account builtins (Patch 625, cl_receipt.c).  acct_sign:
// `<pub> <key> <sig> "<server>" <code>` for the lobby, or "" (no key press for
// a kind that needs one, no signing key, not connected).
string(string nonce, float kind) acct_sign = #0:acct_sign;
string(float bytes) acct_random = #0:acct_random;
float(string opener) acct_browse = #0:acct_browse;

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
	registercommand("acct_is");
	acct_cl_old = TRUE;
	if (checkbuiltin(acct_sign))
	if (checkbuiltin(acct_random))
	if (checkbuiltin(acct_browse))
		acct_cl_old = FALSE;
	registercvar("_acct_prompted", "0");    // once a game, not once a map: a cvar outlives this VM
	acct_cl_asks = 0;
	acct_cl_at   = 0;
	acct_cl_got  = FALSE;
	acct_ui      = ACCT_UI_NONE;
	acct_ui_buf  = "";
	acct_ui_pin  = "";
	acct_ui_to   = "";
	acct_ui_from = "";
	acct_ui_note = "";
	acct_ui_go   = "";
	acct_ui_no   = "";
	acct_ui_key  = "";
	acct_pool    = "";
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

// 0 is the ctrl+V clipboard (sys.h).  Declared here since Patch 619: this file
// compiles before cl_entview.qc, which also copies with it.
void(float cliptype, string text) clipboard_set = #0:clipboard_set;

// A code as surfd issues one: ACCT_CODELEN of its alphabet.
float(string s) Account_IsCode =
{
	local float i;

	if (strlen(s) != ACCT_CODELEN)
		return FALSE;
	for (i = 0; i < ACCT_CODELEN; i = i + 1)
		if (strstrofs(ACCT_ALPHABET, substring(s, i, 1)) < 0)
			return FALSE;
	return TRUE;
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
	acct_ui_go   = Account_Keep(acct_ui_go, "");
	acct_ui_key  = Account_Keep(acct_ui_key, "");
	acct_ui_no   = Account_Keep(acct_ui_no, "");
	Account_UiSet(ACCT_UI_NOTE);
	print(sprintf("%s %s\n", good ? "^2steam:^7" : "^1steam:^7", words));
};

void() Account_UiClose =
{
	acct_ui_buf = Account_Keep(acct_ui_buf, "");
	acct_ui_pin = Account_Keep(acct_ui_pin, "");
	acct_ui_go  = Account_Keep(acct_ui_go, "");
	acct_ui_key = Account_Keep(acct_ui_key, "");
	acct_ui_no  = Account_Keep(acct_ui_no, "");
	Account_UiSet(ACCT_UI_NONE);
};

// The pool moves on.  One-way: no later state gives an earlier one back.
void(string more) Account_Stir =
{
	acct_pool = Account_Keep(acct_pool, digest_hex("SHA256", strcat(acct_pool, " ", more)));
};

// The sign-in address for a start, without its scheme.  The engine opens the
// same one from the opener alone (acct_browse); this is for the clipboard and
// the screen.
string() Account_Address =
{
	return sprintf("%s?k=%s", ACCT_LINK_URL, acct_ui_key);
};

// A start's code, from its opener: one of the alphabet's 32 from each of twelve
// bytes of a digest (surfd's start_code_of).
string(string opener) Account_CodeOf =
{
	local string h, out;
	local float  i, v;

	h   = strtolower(digest_hex("SHA256", strcat("ftesurf-id ", opener)));
	out = "";
	for (i = 0; i < ACCT_CODELEN; i = i + 1)
	{
		v   = strstrofs("0123456789abcdef", substring(h, i * 2, 1)) * 16
		    + strstrofs("0123456789abcdef", substring(h, i * 2 + 1, 1));
		out = strcat(out, substring(ACCT_ALPHABET, v & 31, 1));
	}
	return out;
};

/*
  The engine signs `nonce` as `kind`, and the proof goes to the lobby behind
  `first` (the command that says what it is for) in one console pass, so the
  two arrive in order.  FALSE: the engine would not.  What it returns is hex, a
  digit and the address it read off the connection, quoted: nothing a server
  chose goes into this line.
*/
float(string nonce, float kind, string first) Account_Send =
{
	local string p;

	if (acct_cl_old)
		return FALSE;
	p = acct_sign(nonce, kind);
	if (p == "")
		return FALSE;
	localcmd(strcat(first, "cmd acct_proof ", ftos(kind), " ", p, "\n"));
	return TRUE;
};

void() Account_Copy =
{
	acct_ui_copied = FALSE;
	if (!checkbuiltin(clipboard_set))
		return;
	clipboard_set(0, strcat("https://", Account_Address()));
	acct_ui_copied = TRUE;
};

// One more letter of a code, upper-cased, if `chary` is one.  -> it was.
float(float chary) Account_Type =
{
	if (chary >= 'a')
	if (chary <= 'z')
		chary = chary - 32;
	if (chary <= 32)
		return FALSE;
	if (chary >= 127)
		return FALSE;
	if (strstrofs(ACCT_ALPHABET, chr2str(chary)) < 0)
		return FALSE;
	if (strlen(acct_ui_buf) < ACCT_CODELEN)
		acct_ui_buf = Account_Keep(acct_ui_buf, strcat(acct_ui_buf, chr2str(chary)));
	acct_ui_t = cltime;
	return TRUE;
};

// The ask timer, the connect check, the box's own clocks, and the pool.
void() Account_Frame =
{
	local float c;

	// Nine digits: every bit of a float.  frametime's low ones are the timer's,
	// and acct_pool_in is whatever the mouse and keys did since the last frame.
	Account_Stir(sprintf("%.9g %.9g %.9g %.9g", cltime, frametime, random(), acct_pool_in));

	if (acct_ui == ACCT_UI_WAIT)
	if (cltime - acct_ui_t > ACCT_UI_PATIENCE)
	{
		// A confirm may still land: its answer is shown if it comes (acct_note).
		// An ask is taken back.
		if (!acct_ui_conf)
			localcmd("cmd link cancel\n");
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
	if (acct_ui == ACCT_UI_PROMPT)
	if (cltime - acct_ui_t > ACCT_UI_PROMPTLIFE)
		Account_UiClose();
	// The lobby ends a start at 600 s; this is for a lobby that went quiet.
	if (acct_ui == ACCT_UI_GO)
	if (cltime - acct_ui_t > ACCT_UI_GOLIFE)
		Account_UiEnd(FALSE, "That took too long. Type link to start again.");

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
	if (acct_cl_old)
	{
		// No builtin, no proof surfd would take: say so once, where the
		// connect line would be, and ask the lobby nothing.
		print("^5steam:^7 this game needs an update before it can link a Steam account\n");
		acct_cl_asks = 2;
		return;
	}
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
	if (acct_ui == ACCT_UI_ASK)
	{
		if (acct_ui_no != "")
			acct_ui_no = Account_Keep(acct_ui_no, substring(acct_ui_no, 0, strlen(acct_ui_no) - 1));
		return;
	}
	if (acct_ui_buf != "")
		acct_ui_buf = Account_Keep(acct_ui_buf, substring(acct_ui_buf, 0, strlen(acct_ui_buf) - 1));
	acct_ui_t = cltime;
};

// The box is up and is NOT the keyboard's owner: Enter and Esc are its.
float() Account_Light =
{
	if (acct_ui == ACCT_UI_GO)
		return TRUE;
	if (acct_ui == ACCT_UI_PROMPT)
	if (acct_ui_free)
		return TRUE;
	return FALSE;
};

// The consent: the lobby's number, signed under this key press.  For a start
// the sign-in page's number goes beside it as a digest with this VM's opener
// (the header); surfd, which the browser gave the opener, compares, and
// spends the start either way.
void() Account_Confirm =
{
	local string num;

	num = "";
	if (acct_ui_num)
		num = Account_Digest("ftesurf-number ",
		                     strcat(acct_ui_key, " ", acct_ui_pin, " ", acct_ui_no));
	if (!Account_Send(Account_Digest("ftesurf-confirm ", strcat(acct_ui_buf, " ", acct_ui_pin)),
	                  -4, sprintf("cmd link %s %s\n", acct_ui_pin, num)))
	{
		localcmd("cmd link cancel\n");
		Account_UiEnd(FALSE, "This game could not sign for that. Try again.");
		return;
	}
	Account_UiSet(ACCT_UI_WAIT);
	acct_ui_conf = TRUE;
	acct_ui_owed = cltime;
	print("^5steam:^7 linking\n");
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
	local float  slot;
	local string salt;

	if (!cl_input_real)
		return FALSE;
	// For the pool: every real event, the mouse's moves among them.  Folded
	// here and stirred once a frame (a mouse reports a thousand times a second).
	acct_pool_in = acct_pool_in * 1.000001 + evtype * 7.31 + scanx * 1.37 + chary * 0.61;
	if (evtype != IE_KEYDOWN && evtype != IE_KEYUP)
		return FALSE;
	if (!scanx)
		return FALSE;
	if (scanx >= K_MOUSE1)                  // mice, wheels, pads
		return FALSE;
	Account_Stir(sprintf("%g %g %g %.9g", evtype, scanx, chary, cltime));
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
		if (acct_ui == ACCT_UI_CODE || acct_ui == ACCT_UI_ASK)
			Account_Backspace();
		return TRUE;
	}
	slot = Account_Press(scanx);
	if (!acct_ui)
		return FALSE;
	if (getkeybind(scanx) == "toggleconsole")
		return FALSE;
	if (Account_Light())
	if (scanx != K_ESCAPE)
	if (scanx != K_ENTER)
	if (scanx != K_KP_ENTER)
		return FALSE;
	if (slot >= 0)
		acct_ui_ours[slot] = TRUE;

	if (acct_ui == ACCT_UI_PROMPT)
	{
		if (scanx == K_ESCAPE)
		{
			Account_UiClose();
			print("^5steam:^7 not linked. Type ^3link^7 in the console when you want to\n");
			return TRUE;
		}
		if (scanx == K_ENTER || scanx == K_KP_ENTER)
		{
			// Start, all of it under this key press.  An opener of this
			// start's own (the engine's random bytes with the pool, which
			// moves on either side so the opener is not its state; with no
			// system entropy it is the pool alone), the start's code from
			// it, the engine's signature over both, and the browser.
			Account_Stir("open");
			acct_ui_key = Account_Keep(acct_ui_key, substring(strtolower(digest_hex("SHA256",
			                           strcat(acct_pool, " ", acct_random(16)))), 0, ACCT_KEYLEN));
			Account_Stir("opened");
			acct_ui_go  = Account_Keep(acct_ui_go, Account_CodeOf(acct_ui_key));
			acct_ui_buf = Account_Keep(acct_ui_buf, "");
			if (!Account_Send(Account_Digest("ftesurf-start ", strcat(acct_ui_go, " ", acct_ui_key)),
			                  -5, sprintf("cmd link start %s\n", acct_ui_go)))
			{
				Account_UiEnd(FALSE, "This game could not sign for that. Try again.");
				return TRUE;
			}
			acct_ui_opened = acct_browse(acct_ui_key);
			Account_Copy();
			Account_UiSet(ACCT_UI_GO);
			print(sprintf("^5steam:^7 sign in at ^3%s^7%s\n", Account_Address(), acct_ui_opened
			              ? " (opened in your browser)"
			              : (acct_ui_copied ? " (copied: paste it into your browser)" : "")));
			return TRUE;
		}
		// Asked for with `link` (not free): a code's first letter.
		acct_ui_buf = Account_Keep(acct_ui_buf, "");
		acct_ui_bad = 0;
		if (Account_Type(chary))
			Account_UiSet(ACCT_UI_CODE);
		return TRUE;
	}
	if (acct_ui == ACCT_UI_GO)
	{
		if (scanx == K_ESCAPE)
		{
			localcmd("cmd link cancel\n");
			Account_UiClose();
			print("^5steam:^7 link cancelled\n");
			return TRUE;
		}
		// Enter: the page again, and the address on the clipboard again.
		acct_ui_opened = acct_browse(acct_ui_key);
		Account_Copy();
		return TRUE;
	}

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
		if (scanx == K_ESCAPE)
		{
			localcmd("cmd link cancel\n");
			Account_UiClose();
			print("^5steam:^7 link cancelled\n");
			return TRUE;
		}
		if (acct_ui_num)
		{
			// A started link: the page's number, then Enter.  No Y or N: the
			// answer is four digits only the signed-in browser shows.
			if (scanx == K_BACKSPACE)
			{
				Account_Backspace();
				return TRUE;
			}
			if (scanx == K_ENTER || scanx == K_KP_ENTER)
			{
				if (strlen(acct_ui_no) != ACCT_NOLEN)
				{
					acct_ui_bad = cltime;
					return TRUE;
				}
				Account_Confirm();
				return TRUE;
			}
			if (chary >= '0')
			if (chary <= '9')
			if (strlen(acct_ui_no) < ACCT_NOLEN)
				acct_ui_no = Account_Keep(acct_ui_no, strcat(acct_ui_no, chr2str(chary)));
			return TRUE;
		}
		if (chary == 'n' || chary == 'N')
		{
			localcmd("cmd link cancel\n");
			Account_UiClose();
			print("^5steam:^7 link cancelled\n");
			return TRUE;
		}
		if (scanx == K_ENTER || scanx == K_KP_ENTER || chary == 'y' || chary == 'Y')
			Account_Confirm();
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
		// The code's digest goes out behind a salt drawn for this ask.
		salt = acct_random(8);
		if (salt == "")
			salt = substring(acct_pool, 0, 16);
		Account_Stir("asked");
		if (!Account_Send(Account_Digest("ftesurf-link ", acct_ui_buf), -3,
		                  sprintf("cmd link %s%s\n", salt, Account_Digest("ftesurf-code ",
		                          strcat(salt, " ", acct_ui_buf)))))
		{
			Account_UiEnd(FALSE, "This game could not sign for that. Try again.");
			return TRUE;
		}
		Account_UiSet(ACCT_UI_WAIT);
		acct_ui_conf = FALSE;
		print("^5steam:^7 code sent\n");
		return TRUE;
	}
	Account_Type(chary);
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
		// The connect's proof: no key press, and the engine says so in it.
		acct_cl_got = TRUE;
		if (Account_Is(argv(1), 32, 'a', 'f'))
			Account_Send(argv(1), -2, "");
		return TRUE;
	}

	/*
	  The lobby's answers to the box.  Any may be stuffed by anyone, so each is
	  believed only while the box is WAITING for it, changes only what is drawn,
	  and a number is used only under a key press that follows.
	*/
	if (argv(0) == "acct_is")
	{
		// 1 = this install is not linked.  Offered once a game, and only to a
		// screen with no box on it.
		if (argv(1) == "1")
		if (!acct_cl_old)
		if (!acct_ui)
		if (!cvar("_acct_prompted"))
		{
			cvar_set("_acct_prompted", "1");
			acct_ui_free = TRUE;
			Account_UiSet(ACCT_UI_PROMPT);
			print("^5steam:^7 press ^3Enter^7 to link your Steam account, ^3Esc^7 for later\n");
		}
		return TRUE;
	}
	if (argv(0) == "acct_ask")
	{
		if (!Account_Is(argv(1), 6, '0', '9'))
			return TRUE;
		if (acct_ui == ACCT_UI_GO)
		{
			// The start's answer: the question is about the code the lobby
			// was waiting on.
			// The opener stays: the number is sent as a digest with it.
			acct_ui_buf = Account_Keep(acct_ui_buf, acct_ui_go);
			acct_ui_go  = Account_Keep(acct_ui_go, "");
		}
		else if (acct_ui != ACCT_UI_WAIT)
			return TRUE;
		else if (acct_ui_conf)
			return TRUE;                    // the question was answered: no second one
		if (acct_ui_buf == "")
			return TRUE;
		acct_ui_pin  = Account_Keep(acct_ui_pin, argv(1));
		acct_ui_to   = Account_Keep(acct_ui_to, Account_Plain(argv(2)));
		acct_ui_from = Account_Keep(acct_ui_from, Account_Plain(argv(3)));
		acct_ui_no   = Account_Keep(acct_ui_no, "");
		// The page's number is asked for only by a start of OURS: with no
		// opener to hide it behind, it is not asked for and not sent.
		acct_ui_num  = FALSE;
		if (argv(4) == "n")
		if (acct_ui_key != "")
			acct_ui_num = TRUE;
		acct_ui_bad  = 0;
		Account_UiSet(ACCT_UI_ASK);
		print(sprintf("^5steam:^7 link this game to ^3%s^7? %s\n", acct_ui_to, acct_ui_num
		              ? "Type the number from the sign-in page, then Enter"
		              : "Enter to link, Esc to cancel"));
		return TRUE;
	}
	if (argv(0) == "acct_note")
	{
		if (acct_ui != ACCT_UI_WAIT)
		if (acct_ui != ACCT_UI_GO)
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
			Account_UiEnd(FALSE, "One at a time. Wait a few seconds.");
		else if (argv(1) == "stale")
			Account_UiEnd(FALSE, "That took too long. Type link to start again.");
		else if (argv(1) == "gone")
			Account_UiEnd(FALSE, "That sign-in link has ended. Type link to start again.");
		else if (argv(1) == "number")
			Account_UiEnd(FALSE, "That is not the number on the page. Type link to start again.");
		else if (argv(1) == "later")
			Account_UiEnd(FALSE, "The leaderboard cannot check that right now. Try again in a minute.");
		else if (argv(1) == "server")
			Account_UiEnd(FALSE, "The leaderboard does not know this server by the address you joined it on.");
		else if (argv(1) == "proof")
			Account_UiEnd(FALSE, "This game could not sign for that. Try again.");
		else if (argv(1) == "game")
			Account_UiEnd(FALSE, "This game is not running this lobby's own game code, so it cannot be linked.");
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

	if (acct_cl_old)
	{
		print("^5steam:^7 this game needs an update before it can link a Steam account\n");
		return TRUE;
	}
	if (acct_cl_taken)
	{
		print("^1steam:^7 another server changed this game's ^3link^7 command. Restart the "
		      "game first\n");
		return TRUE;
	}
	if (argv(1) != "")
		print("^5steam:^7 a code is typed into the box, not after ^3link^7\n");
	if (acct_ui)
	if (acct_ui != ACCT_UI_NOTE)
	{
		// One is up: a second `link` is not a reset.  But the prompt that came
		// up by itself becomes the asked-for one, which takes a typed code.
		if (acct_ui != ACCT_UI_PROMPT)
			return TRUE;
		if (!acct_ui_free)
			return TRUE;
	}
	acct_ui_buf  = Account_Keep(acct_ui_buf, "");
	acct_ui_bad  = 0;
	acct_ui_owed = 0;
	acct_ui_free = FALSE;
	Account_UiSet(ACCT_UI_PROMPT);
	print("^5steam:^7 link box open. Close the console, then press ^3Enter^7 to link\n");
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
	if (acct_ui == ACCT_UI_ASK)
	if (acct_ui_num)
		h = lsz * 11.6 + pad * 2;           // the question, and the number under it
	x   = (scr_x - w) * 0.5;
	y0  = min(scr_y * 0.56, scr_y - h - pad);
	y   = y0;

	drawfill([x, y], [w, h], '0.10 0.13 0.17', 0.94, 0);
	drawfill([x, y], [w, lsz + pad], '0.35 0.49 0.67', 1, 0);
	HUD_Text([x + pad, y + pad * 0.5], "Link Steam", lsz, '1 1 1', 1);
	y = y + lsz + pad * 1.6;

	foot = "Esc  cancel";
	if (acct_ui == ACCT_UI_PROMPT)
	{
		HUD_Text([x + pad, y], "Rank your times under your Steam name.", lsz, '0.85 0.88 0.92', 1);
		y = y + lsz * 1.6;
		HUD_Text([x + pad, y], acct_ui_free ? "It takes about twenty seconds."
		                                    : "Have a code from the sign-in page? Type it here.",
		         lsz * 0.9, '0.55 0.58 0.62', 1);
		y = y + lsz * 2.2;
		HUD_TextC([x + w * 0.5, y], "Press Enter to link", lsz * 1.4, '1.00 0.90 0.55', 1);
		foot = acct_ui_free ? "Enter  link     Esc  later" : "Enter  link     Esc  cancel";
	}
	else if (acct_ui == ACCT_UI_GO)
	{
		if (acct_ui_opened)
			s = "Sign in on the page that opened in your browser.";
		else if (acct_ui_copied)
			s = "Paste this into your browser and sign in:";
		else
			s = "Open this in your browser and sign in:";
		HUD_Text([x + pad, y], s, lsz, '0.85 0.88 0.92', 1);
		y = y + lsz * 1.6;
		s = Account_Address();
		drawfill([x + pad, y - lsz * 0.3], [w - pad * 2, lsz * 1.7], '0.05 0.07 0.10', 1, 0);
		// Fifty characters, read and not typed: the largest size on the font's
		// ladder that fits.  HUD_TextC snaps to the ladder, so a computed size
		// came back a rung too big and ran past the field.
		for (n = lsz; n > 6; n = n - 1)
			if (stringwidth(s, TRUE, [Font_Px(n), Font_Px(n)]) <= w - pad * 3)
				break;
		HUD_TextC([x + w * 0.5, y + (lsz - Font_Px(n)) * 0.5], s, n,
		          acct_ui_opened ? '0.55 0.58 0.62' : '1.00 0.90 0.55', 1);
		y = y + lsz * 2.0;
		HUD_Text([x + pad, y], "Waiting for you to sign in...", lsz * 0.9, '0.55 0.95 0.60', 1);
		y = y + lsz * 1.4;
		HUD_Text([x + pad, y], "The page gives you a number to type here.", lsz * 0.9,
		         '0.55 0.58 0.62', 1);
		foot = "Enter  open it again     Esc  cancel";
	}
	else if (acct_ui == ACCT_UI_CODE)
	{
		HUD_Text([x + pad, y], "Type the code from the sign-in page", lsz, '0.85 0.88 0.92', 1);
		y = y + lsz * 1.6;
		// ABCDE-FGH__ : what is typed, then what is still owed.
		n = strlen(acct_ui_buf);
		s = "";
		for (i = 0; i < ACCT_CODELEN; i = i + 1)
		{
			if (i > 0)
			if (!(i & 3))
				s = strcat(s, "-");             // ABCD-EFGH-JKLM, as the page shows it
			s = strcat(s, (i < n) ? substring(acct_ui_buf, i, 1) : "_");
		}
		drawfill([x + pad, y - lsz * 0.3], [w - pad * 2, lsz * 2.1], '0.05 0.07 0.10', 1, 0);
		HUD_TextC([x + w * 0.5, y], s, lsz * 1.5,
		          (cltime - acct_ui_bad < 0.6) ? '1 0.35 0.30' : '1.00 0.90 0.55', 1);
		foot = "Enter  continue     Esc  cancel";
	}
	else if (acct_ui == ACCT_UI_WAIT)
	{
		HUD_Text([x + pad, y], acct_ui_conf ? "Linking..." : "Asking the leaderboard...",
		         lsz, '0.85 0.88 0.92', 1);
		foot = acct_ui_conf ? "" : "Esc  cancel";
	}
	else if (acct_ui == ACCT_UI_ASK)
	{
		HUD_Text([x + pad, y], "Link this game to the Steam account", lsz, '0.85 0.88 0.92', 1);
		y = y + lsz * 1.6;
		HUD_TextC([x + w * 0.5, y], acct_ui_to, lsz * 1.4, '1.00 0.90 0.55', 1);
		y = y + lsz * 2.2;
		if (acct_ui_from != "")
		{
			HUD_Text([x + pad, y], sprintf("It is linked to %s now, and would move", acct_ui_from),
			         lsz * 0.9, '1 0.60 0.45', 1);
			if (acct_ui_num)
				y = y + lsz * 1.5;
		}
		foot = "Enter  link     Esc  cancel";
		if (acct_ui_num)
		{
			HUD_Text([x + pad, y], "Type the number the sign-in page shows:", lsz * 0.9,
			         '0.85 0.88 0.92', 1);
			y = y + lsz * 1.7;
			// 4 8 _ _ : what is typed, then what is still owed.
			n = strlen(acct_ui_no);
			s = "";
			for (i = 0; i < ACCT_NOLEN; i = i + 1)
				s = strcat(s, (i > 0) ? " " : "", (i < n) ? substring(acct_ui_no, i, 1) : "_");
			drawfill([x + pad, y - lsz * 0.3], [w - pad * 2, lsz * 2.1], '0.05 0.07 0.10', 1, 0);
			HUD_TextC([x + w * 0.5, y], s, lsz * 1.5,
			          (cltime - acct_ui_bad < 0.6) ? '1 0.35 0.30' : '1.00 0.90 0.55', 1);
		}
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
