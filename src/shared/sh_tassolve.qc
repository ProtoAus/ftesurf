// Bounded input search, not a pose author or a global route optimizer.
#define TAS_SOLVE_FIELD 10
#define TAS_SOLVE_CANDIDATES 9
#define TAS_SOLVE_ROWS 1024
#define TAS_SOLVE_BUDGET 80000
#define TAS_SOLVE_RADIUS 64
#define TAS_SOLVE_SLACK 8
#define TAS_SOLVE_PROBES (TAS_SOLVE_SLACK*2+1)
#define TAS_SOLVE_PROBE_STRIDE 11

float(float previous, float current, float emitted, float candidate) FS_TASSolveYaw =
{
	local float delta, scale, bias;
	if (!candidate || candidate == 5 || candidate == 6) return current;
	delta = current-previous;
	delta = delta-floor((delta+32768)/65536)*65536;
	scale = 1; bias = 0;
	if (candidate == 1 || candidate == 7) scale = .98;
	if (candidate == 2 || candidate == 8) scale = 1.02;
	if (candidate == 3) bias = -.05*65536/360;
	if (candidate == 4) bias = .05*65536/360;
	// Quantize to actual native angle words; wrap on the signed domain.
	delta = rint(emitted+delta*scale+bias);
	return delta-floor((delta+32768)/65536)*65536;
};

float(float bits, float candidate) FS_TASSolveButtons =
{
	// Native tape words use compact jump1/duck2/walk4, NOT QC BTN_DUCK8.
	if (candidate == 5 || candidate == 7 || candidate == 8) return bits | 2;
	if (candidate == 6) return bits & ~2;
	return bits;
};

float(float tick, float target) FS_TASSolveWindow =
{
	return (tick >= max(0,target-TAS_SOLVE_SLACK) && tick <= target+TAS_SOLVE_SLACK);
};

float(vector value) FS_TASSolveFinite =
{
	return (value_x == value_x && value_y == value_y && value_z == value_z &&
		fabs(value_x) <= 10000000 && fabs(value_y) <= 10000000 && fabs(value_z) <= 10000000);
};

float(vector normal, float distance, vector point, vector goalnormal, float goaldistance, vector goalpoint, vector velocity, vector goalvelocity) FS_TASSolveContact =
{
	local vector v, g;
	if (!FS_TASSolveFinite(normal) || !FS_TASSolveFinite(point) || !FS_TASSolveFinite(goalnormal) ||
		!FS_TASSolveFinite(goalpoint) || !FS_TASSolveFinite(velocity) || !FS_TASSolveFinite(goalvelocity)) return FALSE;
	if (distance != distance || goaldistance != goaldistance || fabs(distance) > 10000000 || fabs(goaldistance) > 10000000) return FALSE;
	if (vlen(normal-goalnormal) > .002 || fabs(distance-goaldistance) > .01) return FALSE;
	if (vlen(point-goalpoint) > TAS_SOLVE_RADIUS) return FALSE;
	v = velocity; v_z = 0; g = goalvelocity; g_z = 0;
	if (vlen(g) < 1) return TRUE;
	if (vlen(v) < 1) return FALSE;
	return (normalize(v)*normalize(g) >= .7);
};

void(float *rows, float index, float tick, vector normal, float distance, vector point, vector velocity) FS_TASSolveProbe =
{
	local float b;
	if (!rows || index < 0 || index >= TAS_SOLVE_PROBES || index != floor(index)) return;
	b = index*TAS_SOLVE_PROBE_STRIDE;
	rows[b] = tick;
	rows[b+1] = normal_x; rows[b+2] = normal_y; rows[b+3] = normal_z;
	rows[b+4] = distance;
	rows[b+5] = point_x; rows[b+6] = point_y; rows[b+7] = point_z;
	rows[b+8] = velocity_x; rows[b+9] = velocity_y; rows[b+10] = velocity_z;
};

vector(float *rows, float count, float target, vector goalnormal, float goaldistance, vector goalpoint, vector goalvelocity) FS_TASSolveBaseline =
{
	local float i, b, tick;
	local vector n, p, v;
	if (!rows || count < 1 || count > TAS_SOLVE_PROBES || count != floor(count)) return '0 0 0';
	for (i = 0; i < count; i = i+1)
	{
		b = i*TAS_SOLVE_PROBE_STRIDE; tick = rows[b];
		if (!FS_TASSolveWindow(tick,target)) continue;
		n = [rows[b+1],rows[b+2],rows[b+3]];
		p = [rows[b+5],rows[b+6],rows[b+7]];
		v = [rows[b+8],rows[b+9],rows[b+10]];
		if (!FS_TASSolveContact(n,rows[b+4],p,goalnormal,goaldistance,goalpoint,v,goalvelocity)) continue;
		v_z = 0;
		return [vlen(v),tick,1];
	}
	return '0 0 0';
};

float(float feasible, float speed, float tick, float bestfeasible, float bestspeed, float besttick) FS_TASSolveBetter =
{
	if (!feasible) return FALSE;
	if (!bestfeasible) return TRUE;
	if (speed > bestspeed) return TRUE;
	return (speed == bestspeed && tick < besttick);
};
