// P924: static Source ground carriers; no extra collision or draw entities.
float predground_active;
.entity cv_next;
.vector cv_velocity;
entity cv_head;
float cv_n, cv_over;

void() Conveyor_Clear =
{
	local entity e, next;
	e = cv_head;
	while (e != world)
	{
		next = e.cv_next;
		remove(e);
		e = next;
	}
	cv_head = world;
	cv_n = cv_over = 0;
	predground_active = 0;
};

void(string mdl, vector org, vector dirangles, float speed, float flags) Conveyor_Add =
{
	local entity e;
	if (flags & 3) return;          // Source VISUAL=1, NOTSOLID=2
	if (strcmp(substring(mdl, 0, 1), "*")) return;
	if (cv_n >= 512)
	{
		if (!cv_over) print("conveyor: metadata cap; excess belts stay server-only\n");
		cv_over = TRUE;
		return;
	}
	if (!speed) speed = 100;
	e = spawn();
	setmodel(e, mdl);
	setorigin(e, org);
	e.solid = SOLID_NOT;            // metadata only; never adds a collision/draw
	makevectors(dirangles);
	e.cv_velocity = v_forward * speed;
	e.cv_next = cv_head;
	cv_head = e;
	cv_n = cv_n + 1;
	predground_active = 1;
};

vector(float groundent) Conveyor_GroundVelocity =
{
	local entity e;
	local float mi;
	local vector org;
	if (groundent <= 0) return '0 0 0'; // world/air or a native without P924
	mi = getentity(groundent, GE_MODELINDEX);
	org = getentity(groundent, GE_ORIGIN);
	for (e = cv_head; e != world; e = e.cv_next)
		if (e.modelindex == mi)
		if (vlen(e.origin - org) <= 0.25) // static origin, including net quantisation
			return e.cv_velocity;
	return '0 0 0';
};

// Native probes the pre-move body so fixed-tick/replay scratch cannot pick a belt.
vector(float seat, float seq, float groundent) CSQC_PredictGroundVelocity =
{
	local vector velocity;
	if (!cvar("cl_triggers")) return '0 0 0';
	velocity = Conveyor_GroundVelocity(groundent);
	if (velocity != '0 0 0')
		if (cvar("cl_trigdebug"))
			print(sprintf("conveyor: seq %g ground %g carry %v\n", seq, groundent, velocity));
	return velocity;
};
