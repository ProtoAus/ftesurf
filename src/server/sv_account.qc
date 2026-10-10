/*
===========================================================================
  sv_account.qc -- Steam accounts on a keyed server (Patches 615, 617).

  A connection is told which Steam account its install is linked to, and the
  client's link box links it.  Everything rests on ONE proof: the client signs
  a nonce with its `fskey` (the engine's rec_sign, cl_receipt.c) and surfd
  checks the signature (surfd/accounts.py).  This file moves the pieces and
  decides nothing; it ranks, kicks and refuses nobody.

    connect  CSQC `cmd acct_hello` -> stuffcmd `acct_hello <nonce>` -> rec_sign
             -> `rec_rcpt` -> POST /api/account -> "linked to ..."
    link     the box: `cmd link <digest of the code>` and a signature for it
             -> POST /api/link -> the account's name, and a number made here
             -> stuffcmd `acct_ask <number> "name"`; the box asks, Enter signs
             -> `cmd link <number>` and its signature -> POST /api/link -> linked

  AN INSTALL IS ITS KEY.  The guid goes along for the log and is trusted for
  nothing: any server that sends this fleet's sv_guidkey is handed it.

  THE NUMBER BINDS THE ANSWER TO THE QUESTION.  It is this server's, fresh for
  each ask, and the signature that links is over it: a confirm recorded from
  one ask is no good for another.  It is no longer what the player types
  (Patch 615 had `link <number>`, and anything that could write to the
  connection typed it).  Consent is a key press in the client's box, which
  cl_account.qc takes from the engine's own events only.

  THE THREE PROOFS SIGN TICKS -2, -3 AND -4, AND A RUN SIGNS NONE OF THEM.  A
  finish signs its stamp or -1 and a kept abandon 0, so Account_Proof and
  SV_RecRcpt can never want the same `rec_rcpt`; and SV_RecRcpt refuses
  anything below -1, so a proof could not be filed as a run's even if it got
  there.  The first cut signed 0: a kept abandon's hold takes the first receipt
  that signs 0, and the review walked a stray proof into one.

  THE NONCE IS THIS SERVER'S, from the OS (SV_RandHex).  A client-chosen one
  would let a recorded proof be replayed; the netchan is not encrypted.
===========================================================================
*/

#define ACCT_HELLO      1       // .acct_want: a connect's proof, ticks -2
#define ACCT_ASK        2       // ...a link's first step, -3
#define ACCT_CONFIRM    3       // ...and its second, -4
#define ACCT_WAIT       5       // s a proof is waited for (a round trip and a signature)
#define ACCT_HELLOS     3       // nonces one connection may ask for
#define ACCT_GAP        3       // s between one player's codes
#define ACCT_PINLIFE    90      // s the question stays open
#define ACCT_RQLIFE     15      // s an unanswered question blocks the next

#define ACCT_UNKNOWN    0       // .acct_state: nobody has said
#define ACCT_NONE       1
#define ACCT_LINKED     2
#define ACCT_BANNED     3

.float  acct_want;
.float  acct_want_t;
.string acct_nonce;             // the connect nonce in force, zoned
.string acct_tag;               // the digest of the code being linked, zoned
.string acct_pin;               // the number the box must sign, zoned
.float  acct_pin_t;
.float  acct_rq;                // uri request out for this client, 0 = none
.float  acct_rq_kind;
.float  acct_rq_t;
.float  acct_state;
.string acct_name;              // the account's name as surfd made it safe, zoned
.float  acct_last;              // when this player last sent a code
.float  acct_hellos;
.float  acct_here;              // ClientConnect has run for THIS connection
float   acct_rq_next;

// The board's own gate (Lobby_SubmitRun): pointed at a directory, and keyed.
float() Account_On =
{
	registercvar("lobby_master", "");
	registercvar("lobby_master_key", "");
	if (cvar_string("lobby_master") == "")
		return FALSE;
	if (cvar_string("lobby_master_key") == "")
		return FALSE;
	return TRUE;
};

string() Account_Url =
{
	registercvar("lobby_link_url", "proto.bar/ftesurf/board/link");
	return cvar_string("lobby_link_url");
};

void(entity e, string s) Account_SetName =
{
	if (e.acct_name != "")
		strunzone(e.acct_name);
	e.acct_name = "";
	if (s != "")
		e.acct_name = strzone(s);
};

// Forget the link in progress: the code's digest and the number.
void(entity e) Account_Drop =
{
	if (e.acct_tag != "")
		strunzone(e.acct_tag);
	if (e.acct_pin != "")
		strunzone(e.acct_pin);
	e.acct_tag = "";
	e.acct_pin = "";
};

// Edicts are recycled: a new connection owes nothing and is nobody.
void(entity e) Account_Connect =
{
	if (e.acct_nonce != "")
		strunzone(e.acct_nonce);
	e.acct_nonce  = "";
	Account_Drop(e);
	e.acct_want   = 0;
	e.acct_rq     = 0;
	e.acct_state  = ACCT_UNKNOWN;
	e.acct_last   = 0;
	e.acct_hellos = 0;
	Account_SetName(e, "");
	e.acct_here   = TRUE;
};

/*
  THE SLOT'S NEXT PLAYER MUST FIND NOTHING.  The engine reuses the edict as it
  is and clears it only at the newcomer's `spawn`, and their commands reach
  this file before that: without this, `cmd link` told them the last player's
  account, and an answer still out was theirs.  Freed here too, because that
  clear zeroes the fields without unzoning them.
*/
void(entity e) Account_Disconnect =
{
	Account_Connect(e);
	e.acct_here = FALSE;
};

float(entity e) Account_Busy =
{
	if (!e.acct_rq)
		return FALSE;
	if (time - e.acct_rq_t > ACCT_RQLIFE)
	{
		e.acct_rq = 0;                  // never answered: uri_post has no timeout of ours
		return FALSE;
	}
	return TRUE;
};

void(entity e) Account_Say =
{
	if (e.acct_state == ACCT_LINKED)
		sprint(e, PRINT_HIGH, sprintf("^5steam:^7 this install is linked to ^3%s^7\n",
		                              e.acct_name));
	else if (e.acct_state == ACCT_BANNED)
		sprint(e, PRINT_HIGH, sprintf("^1steam:^7 ^3%s^7 is banned from the "
		                              "leaderboards\n", e.acct_name));
	else if (e.acct_state == ACCT_NONE)
		sprint(e, PRINT_HIGH, sprintf("^5steam:^7 this install is not linked to a Steam "
		                              "account. Sign in at ^3%s^7, then type ^3link^7 in "
		                              "the console\n", Account_Url()));
	else
		sprint(e, PRINT_HIGH, sprintf("^5steam:^7 the leaderboard has not said who this "
		                              "install is yet. To link it, sign in at ^3%s^7, then "
		                              "type ^3link^7 in the console\n", Account_Url()));
};

// A word for the client's box (cl_account.qc has what each says).  Always a
// literal of this file: nothing from the client or from surfd goes in.
void(entity e, string word) Account_Note =
{
	stuffcmd(e, sprintf("acct_note %s\n", word));
};

// A name from surfd, inside a quoted stuffcmd argument.  surfd's allowlist
// (accounts.game_name) has none of these already; this is the second lock.
string(string s) Account_Quoted =
{
	s = strreplace("\"", "'", s);
	s = strreplace("\\", "", s);
	s = strreplace(";", "", s);
	s = strreplace("$", "", s);
	s = strreplace("\n", "", s);
	s = strreplace("\r", "", s);
	return s;
};

// `cmd acct_hello`: the client's game code is up and asks for its nonce.
void(entity e) Account_Hello =
{
	local string n;

	if (!Account_On())
		return;
	if (!e.acct_here)                   // not in the game yet: see Account_Disconnect
		return;
	if (e.acct_hellos >= ACCT_HELLOS)
		return;
	// ONE NONCE IN FORCE.  A proof names no nonce, so a second ask that minted
	// a new one would have the first's signature posted under it and refused:
	// measured, 1 reconnect in 9, and tools/p615link.py arm L forces it.
	if (e.acct_want)
	if (time - e.acct_want_t <= ACCT_WAIT)
		return;
	e.acct_hellos = e.acct_hellos + 1;
	n = SV_RandHex(16);
	if (e.acct_nonce != "")
		strunzone(e.acct_nonce);
	e.acct_nonce  = strzone(n);
	e.acct_want   = ACCT_HELLO;
	e.acct_want_t = time;
	stuffcmd(e, sprintf("acct_hello %s\n", n));
	// dprint here and below, as SV_RecRcpt's refusals are: a client drives these lines.
	dprint(sprintf("^5account:^7 nonce %s.. issued to client %g\n", substring(n, 0, 8),
	              num_for_edict(e)));
};

float(string s) Account_IsPin =
{
	local float i, c;

	if (strlen(s) != 6)
		return FALSE;
	for (i = 0; i < 6; i = i + 1)
	{
		c = str2chr(s, i);
		if (c < '0')
			return FALSE;
		if (c > '9')
			return FALSE;
	}
	return TRUE;
};

// Six digits, one from each of six OS random bytes.  A byte, not a hex
// character: the character's code mod 10 makes six of the digits twice as
// likely as the other four.  A byte leaves 26 in 256 against 25.
string() Account_NewPin =
{
	local string h, out;
	local float  i, hi, lo;

	h   = SV_RandHex(6);
	out = "";
	for (i = 0; i < 6; i = i + 1)
	{
		hi  = str2chr(h, i * 2);
		lo  = str2chr(h, i * 2 + 1);
		hi  = (hi > '9') ? hi - 'a' + 10 : hi - '0';
		lo  = (lo > '9') ? lo - 'a' + 10 : lo - '0';
		hi  = hi * 16 + lo;
		out = strcat(out, ftos(hi - floor(hi / 10) * 10));
	}
	return out;
};

/*
  `cmd link` (who am I), `cmd link cancel`, `cmd link <32 hex>` (asking: the
  digest of a code) or `cmd link <six digits>` (confirming: the number
  Account_Reply sent the box).  The client's signature follows in the same
  packet; Account_Proof posts.  Every refusal is a word for the box.
*/
void(entity e, string arg) Account_Link =
{
	if (!e.acct_here)
		return;
	if (arg == "cancel")
	{
		e.acct_want = 0;
		Account_Drop(e);
		return;
	}
	if (!Account_On())
	{
		if (arg == "")
			sprint(e, PRINT_HIGH, "^5steam:^7 this server has no leaderboard to link to\n");
		else
			Account_Note(e, "off");
		return;
	}
	if (arg == "")
	{
		Account_Say(e);
		return;
	}
	if (Account_Busy(e))
	{
		Account_Note(e, "busy");
		return;
	}
	if (Account_IsPin(arg))
	{
		if (e.acct_pin == "")
		{
			Account_Note(e, "code");
			return;
		}
		if (time - e.acct_pin_t > ACCT_PINLIFE)
		{
			Account_Drop(e);
			Account_Note(e, "stale");
			return;
		}
		if (strcmp(arg, e.acct_pin))
		{
			// One try.  The box sends the number it was sent; anything else guessed.
			Account_Drop(e);
			Account_Note(e, "proof");
			return;
		}
		e.acct_want   = ACCT_CONFIRM;
		e.acct_want_t = time;
		return;
	}
	if (!SV_RecIsHex(arg, 32))
	{
		Account_Note(e, "code");
		return;
	}
	if (e.acct_last)
	if (time - e.acct_last < ACCT_GAP)
	{
		Account_Note(e, "soon");
		return;
	}
	e.acct_last = time;
	Account_Drop(e);
	e.acct_tag    = strzone(arg);
	e.acct_want   = ACCT_ASK;
	e.acct_want_t = time;
};

float() Account_NextId =
{
	if (acct_rq_next < ACCT_ID_BASE)
		acct_rq_next = ACCT_ID_BASE;
	if (acct_rq_next >= ACCT_ID_BASE + 400000)
		acct_rq_next = ACCT_ID_BASE;
	acct_rq_next = acct_rq_next + 1;
	return acct_rq_next;
};

/*
  A `rec_rcpt`.  FALSE = it is a run's, and SV_RecRcpt gets it as before.
  TRUE = it signs one of the three proof kinds: it is ours, wanted or not, and
  is never passed on.
*/
float(entity e, string pub, string ticks, string sig, string svname) Account_Proof =
{
	local float  kind;
	local string body, path;

	kind = 0;
	if (ticks == "-2")
		kind = ACCT_HELLO;
	if (ticks == "-3")
		kind = ACCT_ASK;
	if (ticks == "-4")
		kind = ACCT_CONFIRM;
	if (!kind)
		return FALSE;
	if (!e.acct_here)
		return TRUE;                    // ours by its kind, and from nobody yet
	if (e.acct_want != kind)
		return TRUE;                    // nobody asked for this one
	e.acct_want = 0;
	if (time - e.acct_want_t > ACCT_WAIT)
		return TRUE;
	if (!Account_On())
		return TRUE;
	if (Account_Busy(e))
		return TRUE;                    // one question at a time
	if (!SV_RecIsHex(pub, 64))
		return TRUE;
	if (!SV_RecIsHex(sig, 128))
		return TRUE;

	// Seven values, then the kind's own (sprintf takes eight).  `ip` is what
	// THIS server saw: surfd's per-player limits are keyed on it, not the guid.
	body = sprintf("key=%s&node=%s&ip=%s&player=%s&pub=%s&sig=%s&server=%s",
	               uri_escape(cvar_string("lobby_master_key")),
	               uri_escape(sprintf("p%g", cvar("sv_port"))),
	               uri_escape(infokey(e, "ip")), uri_escape(infokey(e, "guid")),
	               pub, sig, uri_escape(svname));
	path = "/api/link";
	if (kind == ACCT_HELLO)
	{
		path = "/api/account";
		body = strcat(body, "&nonce=", e.acct_nonce);
	}
	else
		body = strcat(body, "&tag=", e.acct_tag);
	if (kind == ACCT_CONFIRM)
		body = strcat(body, "&pin=", e.acct_pin);

	e.acct_rq      = Account_NextId();
	e.acct_rq_kind = kind;
	e.acct_rq_t    = time;
	dprint(sprintf("^5account:^7 kind %g asked for client %g (request %d, nonce %s..)\n", kind,
	              num_for_edict(e), e.acct_rq, substring(e.acct_nonce, 0, 8)));
	if (!uri_post(strcat(cvar_string("lobby_master"), path), e.acct_rq,
	              "application/x-www-form-urlencoded", body))
	{
		// The engine takes 32 requests at once and no callback will come.
		e.acct_rq = 0;
		dprint("^1account:^7 uri_post refused the request\n");
		if (kind != ACCT_HELLO)
			Account_Note(e, "busy");
	}
	return TRUE;
};

void(entity who, float linked, float banned, string nm) Account_Is =
{
	who.acct_state = ACCT_NONE;
	if (linked)
		who.acct_state = ACCT_LINKED;
	if (linked)
	if (banned)
		who.acct_state = ACCT_BANNED;
	Account_SetName(who, linked ? nm : "");
};

// surfd's refusal, as one of the box's words.  `why` is surfd's text: it is
// matched here and never passed on.
void(entity who, string why) Account_Refused =
{
	if (why == "banned")
		Account_Note(who, "banned");
	else if (why == "slow")
		Account_Note(who, "slow");
	else if (why == "later")
		Account_Note(who, "later");
	else if (why == "server")
		Account_Note(who, "server");
	else if (why == "proof")
		Account_Note(who, "proof");
	else
		Account_Note(who, "code");
};

// surfd's answer.  Called from URI_Get_Callback (sv_lobby.qc) for ids past ACCT_ID_BASE.
void(float reqid, float code, string body) Account_Reply =
{
	local entity who;
	local int    root;
	local float  kind, answered, ok, linked, banned;
	local string why, nm, a, b;

	who = findfloat(world, acct_rq, reqid);
	if (who == world)
		return;                         // the player left before the answer
	kind = who.acct_rq_kind;
	who.acct_rq = 0;

	/*
	  CODE 0 IS NOT "200 WITH A BODY".  A request that never connected, or timed
	  out, also arrives as 0 with nothing in it (httpclient.c), and nothing reads
	  as "not linked".  surfd puts `acct` in every answer; without it there was
	  no answer.  Handle 0 is a valid null node and must not be freed.
	*/
	root     = json_parse(body);
	answered = json_get_float(json_find_object_child(root, "acct"));
	ok       = json_get_float(json_find_object_child(root, "ok"));
	linked   = json_get_float(json_find_object_child(root, "linked"));
	banned   = json_get_float(json_find_object_child(root, "banned"));
	why      = strcat(json_get_string(json_find_object_child(root, "why")));
	nm       = strcat(json_get_string(json_find_object_child(root, "name")));
	a        = strcat(json_get_string(json_find_object_child(root, "from")));
	b        = strcat(json_get_string(json_find_object_child(root, "to")));
	if (root)
		json_free(root);
	if (code)
	{
		answered = FALSE;
		dprint(sprintf("^1account:^7 the directory returned %g to request %d\n", code, reqid));
	}
	// Seven values: a varargs call takes eight parameters, the format among them.
	dprint(sprintf("^5account:^7 kind %g answered for client %g: answered %g ok %g "
	              "linked %g banned %g why '%s'\n", kind, num_for_edict(who), answered,
	              ok, linked, banned, why));

	if (!answered)
	{
		// A connect says nothing and knows nothing; a link is owed a word.
		if (kind != ACCT_HELLO)
		{
			Account_Drop(who);
			Account_Note(who, "silent");
		}
		return;
	}
	if (kind == ACCT_HELLO)
	{
		if (why != "")
			return;                     // could not be checked: not "not linked"
		Account_Is(who, linked, banned, nm);
		Account_Say(who);
		return;
	}
	if (kind == ACCT_ASK)
	{
		if (why != "confirm")
		{
			Account_Drop(who);
			Account_Refused(who, why);
			return;
		}
		if (who.acct_pin != "")
			strunzone(who.acct_pin);
		who.acct_pin   = strzone(Account_NewPin());
		who.acct_pin_t = time;
		// The names are only ever drawn by the box; the number it validates.
		stuffcmd(who, sprintf("acct_ask %s \"%s\" \"%s\"\n", who.acct_pin,
		                      Account_Quoted(b), Account_Quoted(a)));
		return;
	}
	Account_Drop(who);
	if (ok)
	{
		Account_Is(who, TRUE, banned, nm);
		stuffcmd(who, sprintf("acct_note linked \"%s\"\n", Account_Quoted(nm)));
		return;
	}
	Account_Refused(who, why);
};
