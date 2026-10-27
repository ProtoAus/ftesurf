// Player-origin I/O keeps its admission identity until the actual body write.
// VM-local only: not a recording field, native fence or persistent-map ledger.
.int bank_attempt;
.float bank_practice;
.entity bank_src_player;
.int bank_src_attempt;
.float bank_src_bad;
.void() bank_callback;

int bank_serial;
entity bank_ctx_player;
int bank_ctx_attempt;
float bank_ctx_bad, bank_ctx_depth;

void(entity e) SV_TimerPractice;
float(entity e) SV_BankSourceTaint;

void(entity e) SV_BankAdvance =
{
	// Exhaustion cannot alias an earlier admission. Negative identities taint.
	if (bank_serial == 2147483647i)
		e.bank_attempt = -1i;
	else
	{
		bank_serial = bank_serial + 1i;
		e.bank_attempt = bank_serial;
	}
};

void(entity e) SV_BankNewAttempt =
{
	SV_BankAdvance(e);
	e.bank_practice = FALSE;
};

void(entity e) SV_BankWatch =
{
	if (e.bank_practice)
		SV_TimerPractice(e);
};

void(entity act) SV_BankBegin =
{
	bank_ctx_player = world;
	bank_ctx_attempt = 0i;
	bank_ctx_bad = FALSE;
	if (act.classname != "player")
		return;
	bank_ctx_player = act;
	bank_ctx_attempt = act.bank_attempt;
	// Zero is reserved for world origin, not an unidentified player.
	if (bank_ctx_attempt == 0i)
		bank_ctx_attempt = -1i;
	bank_ctx_bad = SV_BankSourceTaint(act);
};

void(entity pending) SV_BankSnapshot =
{
	pending.bank_src_player = bank_ctx_player;
	pending.bank_src_attempt = bank_ctx_attempt;
	pending.bank_src_bad = bank_ctx_bad;
};

void() SV_BankThink =
{
	local entity bp;
	local int ba;
	local float bb, bd;
	local void() fn;

	bp = bank_ctx_player;
	ba = bank_ctx_attempt;
	bb = bank_ctx_bad;
	bd = bank_ctx_depth;
	fn = self.bank_callback;
	bank_ctx_player = self.bank_src_player;
	bank_ctx_attempt = self.bank_src_attempt;
	bank_ctx_bad = self.bank_src_bad;
	bank_ctx_depth = 1;
	fn();
	bank_ctx_player = bp;
	bank_ctx_attempt = ba;
	bank_ctx_bad = bb;
	bank_ctx_depth = bd;
};

void(entity body) SV_BankAffect =
{
	if (body.classname != "player")
		return;
	if (!bank_ctx_depth || bank_ctx_attempt == 0i)
		return;
	if (!bank_ctx_bad && bank_ctx_attempt > 0i)
	if (bank_ctx_player.classname == "player")
	if (bank_ctx_player.bank_attempt == bank_ctx_attempt)
		return;

	if (!body.bank_practice)
		sprint(body, PRINT_HIGH, "^3practice^7 -- inherited player-origin map effect\n");
	body.bank_practice = TRUE;
	SV_TimerPractice(body);
};
