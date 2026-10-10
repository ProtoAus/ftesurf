/*
===========================================================================
  cl_account.qc -- the client's half of sv_account.qc (Patch 615).

  `link <code>` sends the server a digest of the code and has the engine sign
  for it; the server answers with the account's name and a number, and
  `link <number>` signs that number.  `acct_hello <nonce>` is the server's
  connect challenge, stuffed in answer to our `cmd acct_hello`.  The three sign
  ticks -3, -4 and -2, which no run does (sv_account.qc has why).

  THE SIGNING IS ASKED FOR FROM HERE because rec_sign refuses a server's
  stufftext (cl_receipt.c): a server may hand this VM a nonce, not a signature.

  THE CODE NEVER LEAVES THIS VM.  The server is sent a digest of it, and so is
  anyone reading the wire.  A code is 40 bits, so that digest can be searched:
  what keeps the code is that the ask riding in the same packet claims it.

  NOTHING A SERVER SENDS REACHES localcmd UNCHECKED.  A stuffed command runs
  below this VM's own level, so pasting its argument into a command line would
  hand the server ours.  A nonce is 32 lowercase hex or it is dropped; a code
  is eight characters of its alphabet and a number six digits, or nothing is
  sent.  That `link` itself can be run by text a server left behind is what the
  number is for.
===========================================================================
*/

float  acct_cl_asks;        // hellos asked for on this map
float  acct_cl_at;          // when the last was, or when this VM first drew
float  acct_cl_wait;        // s from acct_cl_at to the next ask
float  acct_cl_got;         // the server answered one
string acct_cl_code;        // the code last typed, zoned: the number is signed with it
float  acct_cl_taken;       // `link` or `acct_hello` was somebody's cvar when this VM loaded

void() Account_RegisterCvars =
{
	// A NAME IS ONLY FREE UNTIL A SERVER TAKES IT.  The engine and plugins have
	// no `link`, but a server the player was on can leave a cvar of that name,
	// the registration below then fails without a word, and a typed code becomes
	// that cvar's value.  Read before registering: afterwards it is a command.
	acct_cl_taken = FALSE;
	if (cvar_type("link"))
		acct_cl_taken = TRUE;
	if (cvar_type("acct_hello"))
		acct_cl_taken = TRUE;
	registercommand("link");
	registercommand("acct_hello");
	acct_cl_asks = 0;
	acct_cl_at   = 0;
	acct_cl_got  = FALSE;
	acct_cl_code = "";
};

// What a player typed -> the eight characters, or "".  The alphabet is surfd's
// CODE_ALPHABET; nothing checks the code again before it is digested.
string(string raw) Account_Code =
{
	local string out, ch;
	local float  i, n;

	raw = strtoupper(raw);
	n   = strlen(raw);
	out = "";
	for (i = 0; i < n; i = i + 1)
	{
		ch = substring(raw, i, 1);
		if (ch == "-")
			continue;
		if (strstrofs("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", ch) < 0)
			return "";
		out = strcat(out, ch);
	}
	if (strlen(out) != 8)
		return "";
	return out;
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

// Once the VM is up, ask who this install is; once more if nothing came back.
void() Account_Frame =
{
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
		print("^1steam:^7 another server changed this game's ^3link^7 command. Do NOT type "
		      "a code now: it would be sent in the open. Restart the game first\n");
		acct_cl_asks = 2;
		return;
	}
	localcmd("cmd acct_hello\n");
};

float(string cmd) Account_ConsoleCommand =
{
	local string code, raw;
	local float  i, n;

	if (argv(0) == "acct_hello")
	{
		acct_cl_got = TRUE;
		if (Account_Is(argv(1), 32, 'a', 'f'))
			localcmd(sprintf("rec_sign %s -2 - 0\n", argv(1)));
		return TRUE;
	}
	if (argv(0) != "link")
		return FALSE;

	// `link`, `link ABCD-EFGH`, `link ABCD EFGH`, `link 482913`.
	n = tokenize(cmd);
	raw = "";
	for (i = 1; i < n; i = i + 1)
		raw = strcat(raw, argv(i));
	if (raw == "")
	{
		localcmd("cmd link\n");         // the server says where this install stands
		return TRUE;
	}
	if (Account_Is(raw, 6, '0', '9'))
	{
		if (acct_cl_code == "")
		{
			print("^1steam:^7 no number is waiting. Type ^3link <code>^7 first\n");
			return TRUE;
		}
		localcmd(sprintf("cmd link %s\nrec_sign %s -4 - 0\n", raw,
		                 Account_Digest("ftesurf-confirm ", strcat(acct_cl_code, " ", raw))));
		return TRUE;
	}
	code = Account_Code(raw);
	if (code == "")
	{
		print("^1steam:^7 that is not a code. It looks like ^3link ABCD-EFGH^7\n");
		return TRUE;
	}
	if (acct_cl_code != "")
		strunzone(acct_cl_code);
	acct_cl_code = strzone(code);
	localcmd(sprintf("cmd link %s\nrec_sign %s -3 - 0\n",
	                 Account_Digest("ftesurf-code ", code),
	                 Account_Digest("ftesurf-link ", code)));
	return TRUE;
};
