/*
===========================================================================
  sv_account.qc -- Steam accounts on a keyed server (Patches 615, 617, 619, 625).

  A connection is told which Steam account its install is linked to, and the
  client's link box links it.  Everything rests on ONE proof: the client signs
  a nonce with its `fskey` (the engine's acct_sign builtin, cl_receipt.c) and
  surfd checks the signature (surfd/accounts.py).  This file moves the pieces
  and decides nothing; it ranks, kicks and refuses nobody.

  A PROOF ARRIVES AS `acct_proof <kind> <pub> <key> <sig> "<server>" <code>`
  (Patch 625: the engine's acct_sign output behind the kind that was asked for).  Through 619 it was a run receipt with a negative tick count, signed
  by a console command that text could reach; an engine with the builtin signs
  a statement of its own and says, inside it, whether a device's key was being
  pressed.  An old engine's `rec_rcpt` proof is dropped without a word: surfd
  would refuse it, and the client's game code tells its player to update.

    connect  CSQC `cmd acct_hello` -> stuffcmd `acct_hello <nonce>` -> acct_sign
             -> `cmd acct_proof` -> POST /api/account -> "linked to ..."
    link     the box: `cmd link <digest of the code>` and a signature for it
             -> POST /api/link -> the account's name, and a number made here
             -> stuffcmd `acct_ask <number> "name"`; the box asks, Enter signs
             -> `cmd link <number>` and its signature -> POST /api/link -> linked
    start    (Patches 619, 625) on Enter the client makes an opener, names
             the start from it, signs both and sends `cmd link start <code>`
             with the proof; this file posts /api/link/start and, if surfd
             took it, asks /api/link/wait until somebody has signed in at the
             address the client's ENGINE opened, then sends `acct_ask` with a
             flag: the box asks for the sign-in page's number, and `cmd link
             <number of ours> <number of the page>` carries it to surfd with
             the confirm.  Nothing comes back to the client before the
             question: there is no code a rewritten connection could swap.

  AN INSTALL IS ITS KEY.  The guid goes along for the log and is trusted for
  nothing: any server that sends this fleet's sv_guidkey is handed it.

  THE NUMBER BINDS THE ANSWER TO THE QUESTION.  It is this server's, fresh for
  each ask, and the signature that links is over it: a confirm recorded from
  one ask is no good for another.  It is no longer what the player types
  (Patch 615 had `link <number>`, and anything that could write to the
  connection typed it).  Consent is a key press in the client's box, which
  cl_account.qc takes from the engine's own events only.

  THE FOUR PROOFS ARE KINDS -2 TO -5 OF THEIR OWN STATEMENT, AND A RUN'S
  RECEIPT IS ANOTHER STATEMENT ALTOGETHER.  The numbers are the tick counts
  they once borrowed: SV_RecRcpt still refuses anything below -1, so an old
  engine's proof cannot be filed as a run's.

  THE NONCE IS THIS SERVER'S, from the OS (SV_RandHex).  A client-chosen one
  would let a recorded proof be replayed; the netchan is not encrypted.
===========================================================================
*/

#define ACCT_HELLO      1       // .acct_want: a connect's proof, ticks -2
#define ACCT_ASK        2       // ...a link's first step, -3
#define ACCT_CONFIRM    3       // ...and its second, -4
#define ACCT_START      4       // ...or a link the game starts, -5
#define ACCT_WAITING    5       // .acct_rq_kind only: a wait carries no proof
#define ACCT_POLL       2       // s between waits, for the first ACCT_POLL_EAGER s
#define ACCT_POLL_EAGER 90
#define ACCT_POLL_IDLE  5       // ...then: a start left alone is 150 requests, not 300
#define ACCT_POLL_MISS  20      // ...and after a wait surfd never answered
#define ACCT_STARTLIFE  600     // s a start is waited on: a code's life (surfd CODE_TTL)
#define ACCT_WAIT       5       // s a proof is waited for (a round trip and a signature)
#define ACCT_HELLOS     8       // nonces one connection is given: its own ask, and the lobby's re-asks
#define ACCT_REHELLO    30      // s before the lobby asks again a client it has no answer about
#define ACCT_SETTLE     20      // s after a connect in which "has not asked yet" is not "cannot ask"
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
.string acct_scode;             // a start's code, as its client made it, zoned
.float  acct_poll_t;            // when to ask /api/link/wait next
.float  acct_poll_end;          // ...and when to give up; 0 = not waiting
.string acct_tag;               // the digest of the code being linked, zoned
.string acct_pin;               // the number the box must sign, zoned
.float  acct_pin_t;             // when it stops being good
.float  acct_start_end;         // when the start being waited on dies; kept past the wait
.string acct_num;               // the sign-in page's number as the box sent it, zoned
.float  acct_rq;                // uri request out for this client, 0 = none
.float  acct_rq_kind;
.float  acct_rq_t;
.float  acct_state;
.string acct_name;              // the account's name as surfd made it safe, zoned
.float  acct_last;              // when this player last sent a code
.float  acct_hellos;
.float  acct_here;              // ClientConnect has run for THIS connection
// Patch 629: the key surfd verified a proof from on THIS connection, zoned, or
// "".  Sent with the run (sv_lobby.qc); surfd says whose account it is then.
.string acct_pub;
.string acct_rq_pub;            // ...and the key in the proof that is out, zoned
.float  acct_fail;              // why there is none yet: ACCT_F_*
.float  acct_since;             // when this connection began
.string acct_who;               // surfd's mark for a linked account's rows, zoned
// Patch 638: a linked player's name here is their Steam account's.
.float  acct_named;             // surfd says the account has a name of its own
.string acct_forced;            // what the engine made of the name forced, zoned; "" = none
.float  acct_name_t;            // when the name is next looked at
.float  acct_name_told;         // said once why `name` does nothing
.float  acct_bare_t;            // when a "(1)" before the name is next tried without
void(entity e) Account_NameNow;  // below Account_Think, which calls it
#define ACCT_F_NONE     0       // nothing has failed (or nothing was tried)
#define ACCT_F_SILENT   1       // the directory did not answer
#define ACCT_F_LATER    2       // ...or could not check right now
#define ACCT_F_PROOF    3       // the proof was refused: signature, shape
#define ACCT_F_SERVER   4       // ...or names an address the directory does not know
#define ACCT_F_GAME     5       // ...or game code that is not this lobby's
float   acct_rq_next;
float() Account_NextId;

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

void(entity e, string s) Account_SetName =
{
	if (e.acct_name != "")
		strunzone(e.acct_name);
	e.acct_name = "";
	if (s != "")
		e.acct_name = strzone(s);
};

/*
  A wait or a start in flight belongs to a link the player has since moved on
  from: its answer is nobody's, and it must not make them "busy".  A START's
  answer in particular: the review pressed Esc between the Enter and surfd's
  reply, and the reply then armed ten minutes of waits for a box that had
  closed.  Forgotten here, it finds no player in Account_Reply.
*/
void(entity e) Account_Unwait =
{
	if (!e.acct_rq)
		return;
	if (e.acct_rq_kind == ACCT_WAITING || e.acct_rq_kind == ACCT_START)
		e.acct_rq = 0;
};

// Forget the link in progress: the code's digest, the numbers, and a wait on it.
void(entity e) Account_Drop =
{
	Account_Unwait(e);
	if (e.acct_tag != "")
		strunzone(e.acct_tag);
	if (e.acct_pin != "")
		strunzone(e.acct_pin);
	if (e.acct_num != "")
		strunzone(e.acct_num);
	e.acct_tag = "";
	e.acct_pin = "";
	e.acct_num = "";
	e.acct_poll_end = 0;
};

// Edicts are recycled: a new connection owes nothing and is nobody.
void(entity e) Account_Connect =
{
	if (e.acct_nonce != "")
		strunzone(e.acct_nonce);
	if (e.acct_scode != "")
		strunzone(e.acct_scode);
	if (e.acct_pub != "")
		strunzone(e.acct_pub);
	if (e.acct_rq_pub != "")
		strunzone(e.acct_rq_pub);
	e.acct_nonce  = "";
	e.acct_scode  = "";
	if (e.acct_who != "")
		strunzone(e.acct_who);
	e.acct_pub    = "";
	e.acct_rq_pub = "";
	e.acct_who    = "";
	e.acct_fail   = ACCT_F_NONE;
	e.acct_since  = time;
	Account_Drop(e);
	e.acct_want   = 0;
	e.acct_rq     = 0;
	e.acct_state  = ACCT_UNKNOWN;
	e.acct_last   = 0;
	e.acct_hellos = 0;
	Account_SetName(e, "");
	e.acct_named  = FALSE;
	if (e.acct_forced != "")
		strunzone(e.acct_forced);
	e.acct_forced = "";
	e.acct_name_told = FALSE;
	e.acct_bare_t = 0;
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
		sprint(e, PRINT_HIGH, "^5steam:^7 this install is not linked to a Steam account. "
		                      "Type ^3link^7 in the console to link it\n");
	else
		sprint(e, PRINT_HIGH, "^5steam:^7 the leaderboard has not said who this install is "
		                      "yet. Type ^3link^7 in the console to link it\n");
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

// Patch 629, for sv_lobby.qc (which is compiled first and holds the prototypes).
// The key this connection proved, or "": what a run is submitted under.
string(entity e) Account_ProvenKey =
{
	if (!e.acct_here)
		return "";
	return e.acct_pub;
};

// Why a run of this connection's has no proven key, in words for its player.
// Whether "no key yet" is this connection's settled state: its game has asked,
// or has had the time to.  Until then the reason is not latched (sv_lobby.qc).
float(entity e) Account_UnprovenSettled =
{
	if (e.acct_hellos)
		return TRUE;
	return (time - e.acct_since > ACCT_SETTLE);
};

string(entity e) Account_UnprovenWhy =
{
	if (!e.acct_hellos)
	if (Account_UnprovenSettled(e))
		return "this game has not proved which install it is. An FTESurf from before "
		       "Steam linking cannot: update it to rank";
	if (e.acct_fail == ACCT_F_SERVER)
		return "the leaderboard does not know this server by the address you joined it on";
	if (e.acct_fail == ACCT_F_GAME)
		return "this game is not running this lobby's own game code";
	if (e.acct_fail == ACCT_F_PROOF)
		return "this game's proof of its install was refused";
	return "the leaderboard has not been able to check this install yet";
};

// The board's mark for this player's rows (`*phash`, read by cl_online.qc and
// cl_players.qc): a ranked row is under the ACCOUNT, so a linked player's mark
// is surfd's digest of that (`who`), and anybody else's is their guid's.
//
// TWO NAMESPACES, NEVER BOTH.  An account's mark is surfd's word; a guid's is a
// digest of a string its client chose, and eight hex of one can be made to
// equal anybody's.  So while surfd ranks by account (acct_mode 1) only a
// linked player has a mark at all, and while it ranks by guid (2, or not yet
// heard) the mark is the guid's as it always was.
void(entity e, string who) Account_Mark =
{
	local float byguid;

	// By guid when surfd says rows are under guids, or there is no surfd.
	byguid = FALSE;
	if (acct_mode == 2)
		byguid = TRUE;
	if (acct_mode == 0)
	if (!Account_On())
		byguid = TRUE;
	if (byguid)
		forceinfokey(e, "*phash", FS_GuidId(infokey(e, "guid")));
	else if (acct_mode != 1)
		forceinfokey(e, "*phash", "");  // surfd not heard yet this map
	else if (SV_RecIsHex(who, FS_WHO_IDLEN))
		forceinfokey(e, "*phash", who);
	else
		forceinfokey(e, "*phash", "");  // not linked
	dprint(sprintf("^5account:^7 client %g is marked '%s' on the board\n", num_for_edict(e),
	              infokey(e, "*phash")));
};

// surfd said which way it ranks.  The first word of a map re-marks everybody:
// a guid's mark set before it must not outlive it.
void(float ranked) Account_Mode =
{
	local entity p;
	local float m;

	m = ranked ? 1 : 2;
	if (m == acct_mode)
		return;
	acct_mode = m;
	// Every connection, whatever it has become since (an observer is not a
	// "player" by classname and kept its connect-time mark: the review).
	p = findfloat(world, acct_here, TRUE);
	while (p)
	{
		Account_Mark(p, p.acct_who);
		p = findfloat(p, acct_here, TRUE);
	}
};

// A run this connection began before its proof landed (the first seconds of
// every map) takes the key now: nobody else's hand has been on it.  A paused
// run picked up here keeps the key it was parked under (run_own is false).
void(entity e) Account_OwnRun =
{
	if (e.run_own)
	if (e.run_pub == "")
		Lobby_RunKey(e, e.acct_pub);
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

// `n` digits and nothing else.
float(string s, float n) Account_Digits =
{
	local float i, c;

	if (strlen(s) != n)
		return FALSE;
	for (i = 0; i < n; i = i + 1)
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

// A code as surfd issues one: twelve of its alphabet (accounts.CODE_LEN, CODE_ALPHABET).
float(string s) Account_IsCode =
{
	local float i;

	if (strlen(s) != 12)
		return FALSE;
	for (i = 0; i < 12; i = i + 1)
		if (strstrofs("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", substring(s, i, 1)) < 0)
			return FALSE;
	return TRUE;
};

/*
  `cmd link start <code>`: the box started a link.  The code is the client's
  own (a digest of the opener only it has); its proof follows in the same
  packet and Account_Proof posts both.  The same gap as a typed code's.
*/
void(entity e, string code) Account_Start =
{
	if (!Account_On())
	{
		Account_Note(e, "off");
		return;
	}
	if (!Account_IsCode(code))
	{
		Account_Note(e, "proof");
		return;
	}
	Account_Unwait(e);
	if (Account_Busy(e))
	{
		Account_Note(e, "busy");
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
	if (e.acct_scode != "")
		strunzone(e.acct_scode);
	e.acct_scode  = strzone(code);
	e.acct_want   = ACCT_START;
	e.acct_want_t = time;
};

/*
  A started link, waited on.  From PlayerPostThink, so it stops with the
  player.  No proof rides on a wait: it reads an account's NAME for a code
  surfd already keeps for this player's key.
*/
void(entity e) Account_Think =
{
	if (time >= e.acct_name_t)
	{
		e.acct_name_t = time + 1;
		Account_NameNow(e);
	}
	// Patch 629: a connection the directory has said nothing about is asked
	// again, by itself, while its client is one that answers (it sent the
	// first ask).  A run submitted meanwhile is nobody's (sv_lobby.qc).
	// Not while a link is in hand (its box is waiting on a round trip), and
	// Account_Busy, not acct_rq: only that gives up on a request never answered.
	if (e.acct_state == ACCT_UNKNOWN)
	if (e.acct_hellos)
	if (e.acct_hellos < ACCT_HELLOS)
	if (e.acct_tag == "")
	if (e.acct_pin == "")
	if (time - e.acct_want_t > ACCT_REHELLO)
	if (!Account_Busy(e))
		Account_Hello(e);
	if (!e.acct_poll_end)
		return;
	if (time > e.acct_poll_end)
	{
		Account_Drop(e);
		Account_Note(e, "stale");
		return;
	}
	if (time < e.acct_poll_t)
		return;
	if (e.acct_rq)
	{
		if (time - e.acct_rq_t <= ACCT_RQLIFE)
			return;
		// Never answered.  The engine may still be holding that request (it has
		// 32 and no timeout of ours), so the next is not for a while.
		e.acct_rq     = 0;
		e.acct_poll_t = time + ACCT_POLL_MISS;
		return;
	}
	e.acct_poll_t  = time + ACCT_POLL_IDLE;
	if (time < e.acct_poll_end - ACCT_STARTLIFE + ACCT_POLL_EAGER)
		e.acct_poll_t = time + ACCT_POLL;
	e.acct_rq      = Account_NextId();
	e.acct_rq_kind = ACCT_WAITING;
	e.acct_rq_t    = time;
	if (!uri_post(strcat(cvar_string("lobby_master"), "/api/link/wait"), e.acct_rq,
	              "application/x-www-form-urlencoded",
	              sprintf("key=%s&node=%s&ip=%s&tag=%s",
	                      uri_escape(cvar_string("lobby_master_key")),
	                      uri_escape(sprintf("p%g", cvar("sv_port"))),
	                      uri_escape(infokey(e, "ip")), e.acct_tag)))
		e.acct_rq = 0;                  // the engine is full: the next think asks again
};

/*
  `cmd link` (who am I), `cmd link cancel`, `cmd link start <code>`, `cmd link
  <48 hex>` (asking: a salt and the digest of a typed code under it) or `cmd
  link <six digits> [<32 hex>]` (confirming: the number Account_Reply sent the
  box and, for a start, the client's digest of the one the sign-in page showed).  The client's signature follows in the same packet;
  Account_Proof posts.  Every refusal is a word for the box.
*/
void(entity e, string arg, string num) Account_Link =
{
	if (!e.acct_here)
		return;
	if (arg == "cancel")
	{
		e.acct_want = 0;
		Account_Drop(e);
		return;
	}
	if (arg == "start")
	{
		Account_Start(e, num);
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
	Account_Unwait(e);                  // a typed code outranks the start it replaces
	if (Account_Busy(e))
	{
		Account_Note(e, "busy");
		return;
	}
	if (Account_Digits(arg, 6))
	{
		if (e.acct_pin == "")
		{
			Account_Note(e, "code");
			return;
		}
		if (time > e.acct_pin_t)
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
		// The page's number, as the client's digest of it with its opener
		// (32 hex), or nothing.  This file never sees the number; surfd judges.
		if (e.acct_num != "")
			strunzone(e.acct_num);
		e.acct_num = "";
		if (SV_RecIsHex(num, 32))
			e.acct_num = strzone(num);
		e.acct_want   = ACCT_CONFIRM;
		e.acct_want_t = time;
		return;
	}
	// A typed code's digest under the client's salt: 16 hex of one, 32 of the other.
	if (!SV_RecIsHex(arg, 48))
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
  TRUE for the tick counts Patches 615-619 signed their proofs under.  Such a
  `rec_rcpt` is an old engine's: it is nobody's now, and is not a run's.
*/
float(string ticks) Account_OldProof =
{
	if (ticks == "-2")
		return TRUE;
	if (ticks == "-3")
		return TRUE;
	if (ticks == "-4")
		return TRUE;
	if (ticks == "-5")
		return TRUE;
	return FALSE;
};

/*
  `acct_proof <kind> <pub> <key> <sig> "<server>"`: what the client's engine
  signed for the step this file is waiting on.  Wanted or not, it goes nowhere
  else.  `key` is the engine's word that a device's key was down, and `gcode`
  its word for which csprogs asked (a SHA-256); both are inside the signature,
  so surfd is the one to judge them.
*/
void(entity e, string kindarg, string pub, string keyed, string sig, string svname,
     string gcode) Account_Proof =
{
	local float  kind;
	local string body, path;

	kind = 0;
	if (kindarg == "-2")
		kind = ACCT_HELLO;
	if (kindarg == "-3")
		kind = ACCT_ASK;
	if (kindarg == "-4")
		kind = ACCT_CONFIRM;
	if (kindarg == "-5")
		kind = ACCT_START;
	if (!kind)
		return;
	if (!e.acct_here)
		return;                         // from nobody yet
	if (e.acct_want != kind)
		return;                         // nobody asked for this one
	e.acct_want = 0;
	if (time - e.acct_want_t > ACCT_WAIT)
		return;
	if (!Account_On())
		return;
	if (Account_Busy(e))
		return;                         // one question at a time
	if (!SV_RecIsHex(pub, 64))
		return;
	if (!SV_RecIsHex(sig, 128))
		return;
	if (!SV_RecIsHex(gcode, 64))
		return;
	if (keyed != "1")
		keyed = "0";
	// The key this proof is by: the connection's, once surfd has verified it.
	if (e.acct_rq_pub != "")
		strunzone(e.acct_rq_pub);
	e.acct_rq_pub = strzone(pub);

	// Seven values, then the kind's own (sprintf takes eight).  `ip` is what
	// THIS server saw: surfd's per-player limits are keyed on it, not the guid.
	body = sprintf("key=%s&node=%s&ip=%s&player=%s&pub=%s&sig=%s&server=%s",
	               uri_escape(cvar_string("lobby_master_key")),
	               uri_escape(sprintf("p%g", cvar("sv_port"))),
	               uri_escape(infokey(e, "ip")), uri_escape(infokey(e, "guid")),
	               pub, sig, uri_escape(svname));
	body = strcat(body, "&keyed=", keyed, "&game=", gcode);
	path = "/api/link";
	if (kind == ACCT_HELLO)
	{
		path = "/api/account";
		body = strcat(body, "&nonce=", e.acct_nonce);
	}
	else if (kind == ACCT_START)
	{
		path = "/api/link/start";
		body = strcat(body, "&code=", e.acct_scode);
	}
	else
		body = strcat(body, "&tag=", e.acct_tag);
	if (kind == ACCT_CONFIRM)
		body = strcat(body, "&pin=", e.acct_pin, "&shown=", e.acct_num);

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
};

/*
  THE STEAM NAME IS THE NAME (Patch 638).  forceinfokey rewrites the userinfo
  name and netname without announcing it, for this server only: the player's
  own saved name is untouched.  THE ENGINE MAY ALTER WHAT IT IS GIVEN (a "(1)"
  before a name somebody here already has, "unnamed" for one with "console" in
  it, a cut at 31 bytes), so what is latched is what the engine MADE, and the
  name is forced again only when it has moved off that: an unconditional force
  each second would never match and would re-send the name to everybody.
  A client's own `setinfo name` is dropped before the engine sees it
  (sv_player.qc); one sent as an encoded key gets past that and is put back
  here within the second.
*/
void(entity e) Account_NameNow =
{
	local string was;

	if (!e.acct_named)
		return;
	if (e.acct_name == "")
		return;
	if (e.acct_forced != "")
	if (!strcmp(e.netname, e.acct_forced))
	{
		// Held, and where the engine put it.  If that is not the bare name
		// (somebody here had it first, so this player is "(1)Name"), the
		// bare name is tried again now and then: the other may have left.
		if (!strcmp(e.netname, e.acct_name))
			return;
		if (time < e.acct_bare_t)
			return;
	}
	e.acct_bare_t = time + 15;
	was = strcat(e.netname);
	forceinfokey(e, "name", e.acct_name);
	// THE ENGINE WOULD NOT HAVE IT (its reserved-word test is wider than
	// surfd's, which now ports it; this is the second lock): nobody is held
	// under "unnamed".  The name the player came with goes back.
	if (e.netname == "unnamed")
	if (strcmp(e.acct_name, "unnamed"))
	{
		forceinfokey(e, "name", was);
		e.acct_named = FALSE;
		if (e.acct_forced != "")
			strunzone(e.acct_forced);
		e.acct_forced = "";
		dprint(sprintf("account: client %g keeps '%s': the engine refused its account's "
		               "name\n", num_for_edict(e), e.netname));
		return;
	}
	if (e.acct_forced != "")
		strunzone(e.acct_forced);
	e.acct_forced = strzone(e.netname);
	if (strcmp(was, e.netname))
		dprint(sprintf("account: client %g is named '%s' (its account's '%s')\n",
		               num_for_edict(e), e.netname, e.acct_name));
};

/*
  IS THIS CLIENT COMMAND A RENAME?  By THE ENGINE'S OWN TOKENS: tokenize()
  takes a comment for the command word where the engine skips it, so a rename
  behind one reached the engine and not this test (the review).  The engine
  renames on three spellings: `setinfo name x`; its own `name x` command; and
  a userinfo key sent encoded, which decodes to anything, so a key that does
  not begin with a plain character is refused too.  Clobbers argv: call it
  BEFORE the caller's own tokenize.
*/
float(string cmd) Account_IsRename =
{
	local float n, hit;
	local string c, k;

	n = tokenize_console(cmd);
	c = strtolower(argv(0));
	k = strtolower(argv(1));
	hit = FALSE;
	if (c == "name")
		hit = TRUE;
	if (c == "setinfo")
	if (n >= 2)
	{
		if (k == "name")
			hit = TRUE;
		if (str2chr(k, 0) > 126)
			hit = TRUE;
	}
	return hit;
};

float(entity e) Account_NameHeld =
{
	if (!e.acct_named)
		return FALSE;
	if (e.acct_forced == "")
		return FALSE;
	return TRUE;
};

void(entity e) Account_NameTell =
{
	if (e.acct_name_told)
		return;
	e.acct_name_told = TRUE;
	sprint(e, PRINT_HIGH, "^5steam:^7 your name here is your Steam name. Change it on "
	       "Steam and it follows\n");
};

void(entity who, float linked, float banned, string nm, float named) Account_Is =
{
	who.acct_state = ACCT_NONE;
	if (linked)
		who.acct_state = ACCT_LINKED;
	if (linked)
	if (banned)
		who.acct_state = ACCT_BANNED;
	Account_SetName(who, linked ? nm : "");
	// A banned account keeps the name its game came with.
	who.acct_named = FALSE;
	if (who.acct_state == ACCT_LINKED)
	if (named)
		who.acct_named = TRUE;
	// surfd has just said who this is: the latch is dropped, so a link moved
	// to another account mid-connection renames (the name there now is the
	// LAST account's, and matched the latch).  A force of the same name is the
	// engine's no-op.
	if (who.acct_forced != "")
		strunzone(who.acct_forced);
	who.acct_forced = "";
	Account_NameNow(who);
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
	else if (why == "game")
		Account_Note(who, "game");
	else if (why == "number")
		Account_Note(who, "number");
	else
		Account_Note(who, "code");
};

// surfd's answer.  Called from URI_Get_Callback (sv_lobby.qc) for ids past ACCT_ID_BASE.
void(float reqid, float code, string body) Account_Reply =
{
	local entity who;
	local int    root;
	local float  kind, answered, ok, linked, banned, rmode, named;
	local string why, nm, a, b, st, cd, mark;

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
	st       = strcat(json_get_string(json_find_object_child(root, "state")));
	cd       = strcat(json_get_string(json_find_object_child(root, "code")));
	mark     = strcat(json_get_string(json_find_object_child(root, "who")));
	rmode    = json_get_float(json_find_object_child(root, "ranked"));
	named    = json_get_float(json_find_object_child(root, "named"));
	if (root)
		json_free(root);
	if (code)
	{
		answered = FALSE;
		dprint(sprintf("^1account:^7 the directory returned %g to request %d\n", code, reqid));
	}
	// Seven values: a varargs call takes eight parameters, the format among them.
	// A wait that says "wait" is every two seconds for ten minutes: not printed.
	if (kind != ACCT_WAITING || st != "wait")
		dprint(sprintf("^5account:^7 kind %g answered for client %g: answered %g ok %g "
		              "linked %g banned %g why '%s'\n", kind, num_for_edict(who), answered,
		              ok, linked, banned, strcat(why, st)));

	if (kind == ACCT_WAITING)
	{
		// Unanswered, or still waiting: Account_Think asks again.
		if (!answered)
			return;
		if (!who.acct_poll_end)
			return;                     // cancelled while this was out
		if (st == "ready")
		{
			who.acct_poll_end = 0;
			if (who.acct_pin != "")
				strunzone(who.acct_pin);
			who.acct_pin   = strzone(Account_NewPin());
			// Good for as long as the start is: the player is in a browser
			// when this is sent, and 90 s of it ran out there in the review.
			who.acct_pin_t = who.acct_start_end;
			// "n": the box asks for the number the sign-in page shows.
			stuffcmd(who, sprintf("acct_ask %s \"%s\" \"%s\" n\n", who.acct_pin,
			                      Account_Quoted(b), Account_Quoted(a)));
		}
		else if (st == "gone")
		{
			// Replaced, contested or spent: not "took too long".
			Account_Drop(who);
			Account_Note(who, (why == "banned") ? "banned" : "gone");
		}
		return;
	}

	if (!answered)
	{
		// A connect says nothing and knows nothing; a link is owed a word.
		if (kind != ACCT_HELLO)
		{
			Account_Drop(who);
			Account_Note(who, "silent");
		}
		else
			who.acct_fail = ACCT_F_SILENT;
		return;
	}
	if (kind == ACCT_HELLO)
	{
		if (why != "")
		{
			// Could not be checked: not "not linked".  Kept apart, for the
			// run this connection submits meanwhile (Account_UnprovenWhy).
			who.acct_fail = ACCT_F_LATER;
			if (why == "proof")
				who.acct_fail = ACCT_F_PROOF;
			if (why == "server")
				who.acct_fail = ACCT_F_SERVER;
			if (why == "game")
				who.acct_fail = ACCT_F_GAME;
			return;
		}
		// surfd verified that proof: its key is this connection's.
		if (who.acct_pub != "")
			strunzone(who.acct_pub);
		who.acct_pub  = strzone(who.acct_rq_pub);
		who.acct_fail = ACCT_F_NONE;
		Account_Is(who, linked, banned, nm, named);
		if (who.acct_who != "")
			strunzone(who.acct_who);
		who.acct_who = "";
		if (linked)
		if (SV_RecIsHex(mark, FS_WHO_IDLEN))
			who.acct_who = strzone(mark);
		Account_Mode(rmode);
		Account_Mark(who, who.acct_who);
		Account_OwnRun(who);
		Account_Say(who);
		// For the client's prompt: 1 not linked, 2 linked, 3 banned.
		stuffcmd(who, sprintf("acct_is %g\n", who.acct_state));
		return;
	}
	if (kind == ACCT_START)
	{
		if (!ok)
		{
			Account_Refused(who, (why == "") ? "later" : why);
			return;
		}
		// surfd took the start.  Its code is the client's own and links
		// nothing (the header); the digest is what every later call names it by.
		if (who.acct_tag != "")
			strunzone(who.acct_tag);
		who.acct_tag = strzone(substring(strtolower(digest_hex("SHA256",
		                       strcat("ftesurf-code ", who.acct_scode))), 0, 32));
		who.acct_poll_t    = time + ACCT_POLL;
		who.acct_poll_end  = time + ACCT_STARTLIFE;
		who.acct_start_end = who.acct_poll_end;
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
		who.acct_pin_t = time + ACCT_PINLIFE;
		// The names are only ever drawn by the box; the number it validates.
		stuffcmd(who, sprintf("acct_ask %s \"%s\" \"%s\"\n", who.acct_pin,
		                      Account_Quoted(b), Account_Quoted(a)));
		return;
	}
	Account_Drop(who);
	if (ok)
	{
		// The confirm's proof was verified too, under a key press: its key is
		// this connection's from here (the same one, from an honest client).
		if (who.acct_pub != "")
			strunzone(who.acct_pub);
		who.acct_pub  = strzone(who.acct_rq_pub);
		who.acct_fail = ACCT_F_NONE;
		Account_Is(who, TRUE, banned, nm, named);
		if (who.acct_who != "")
			strunzone(who.acct_who);
		who.acct_who = "";
		if (SV_RecIsHex(mark, FS_WHO_IDLEN))
			who.acct_who = strzone(mark);
		Account_Mode(rmode);            // a link can be the first word of a map
		Account_Mark(who, who.acct_who);
		Account_OwnRun(who);
		stuffcmd(who, sprintf("acct_note linked \"%s\"\n", Account_Quoted(nm)));
		return;
	}
	Account_Refused(who, why);
};

/*
  A QW SPECTATOR IS NOT A PLAYER TO ClientConnect, and the engine copies a
  connect packet's userinfo in whole, star keys with it: a spectator slot
  kept whatever `*phash` its client sent, and the room list drew another
  account's best beside it (Patch 629's review; true before it too).
*/
void() SpectatorConnect =
{
	forceinfokey(self, "*phash", "");
};
