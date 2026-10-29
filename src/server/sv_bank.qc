// Player-origin I/O keeps its admission identity until the actual body write.
// Source metadata stays VM-local; only TF_BANKTAINT declares tier exclusion.
// Low reason preserves legacy practice; high reason excludes every style.
#define BANK_PRACTICE 1
#define BANK_UNRANKED 2
.int bank_attempt;
.float bank_practice;
.entity bank_src_player;
.int bank_src_attempt;
.float bank_src_bad;
.void() bank_callback;
.entity bank_speed_player;
.int bank_speed_attempt;
.float bank_speed_bad;

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

void(entity e) SV_BankWatch;

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

// Explicit scalar assignment replaces this property's source, not body debt.
void(entity body) SV_BankSpeedSnapshot =
{
	body.bank_speed_player = world;
	body.bank_speed_attempt = 0i;
	body.bank_speed_bad = FALSE;
	if (bank_ctx_depth)
	{
		body.bank_speed_player = bank_ctx_player;
		body.bank_speed_attempt = bank_ctx_attempt;
		body.bank_speed_bad = bank_ctx_bad;
	}
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

// Stored causes and active I/O share the same delivery-time policy.
void(entity body, entity cause_player, int cause_attempt, float cause_bad) SV_BankCauseAffect =
{
	local float current;

	if (body.classname != "player")
		return;
	if (cause_attempt == 0i)
		return;
	current = (cause_attempt > 0i && cause_player.classname == "player"
		&& cause_player.bank_attempt == cause_attempt);
	if (!cause_bad && current)
		return;

	if (!body.bank_practice)
		sprint(body, PRINT_HIGH, "^3practice^7 -- inherited player-origin map effect\n");
	body.bank_practice = body.bank_practice | BANK_PRACTICE;
	if (!current || (cause_bad & BANK_UNRANKED))
		body.bank_practice = body.bank_practice | BANK_UNRANKED;
	SV_TimerPractice(body);
};

void(entity body) SV_BankAffect =
{
	if (bank_ctx_depth)
		SV_BankCauseAffect(body, bank_ctx_player, bank_ctx_attempt, bank_ctx_bad);
};
