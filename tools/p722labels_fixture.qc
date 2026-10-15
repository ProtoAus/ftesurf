/* TEST BUILD ONLY, never part of cl_progs.src/ship set.
   Reuse a real participant/body and its actual PVS admission. Override only
   the overhead target during its draw, restoring the pose before other HUD
   readers. Near/far isolate typography (far forces admission, NOT a real
   unoccluded player); wall uses an actual solid-world trace beyond its first
   hit; behind-camera tests the real forward/frustum gate. Register the cvar,
   don't pretend a QC global is a harness handle. Mutants must fail the grader. */
entity lf_body;
vector lf_original, lf_wall;
float lf_mode;
void() LabelFixture_Register = { registercvar("label_fixture", "0"); };
void(entity b, vector eye, vector forward) LabelFixture_Apply =
{
	local float mode;
	local vector point;
	mode = cvar("label_fixture");
	if (mode < 1 || b.pb_slot != 2) return;
	if (mode != lf_mode)
	{
		b.tag_next = 0;
		if (mode == 3)
		{
			traceline(eye, eye + forward * 2800, MOVE_NOMONSTERS, world);
			lf_wall = trace_endpos + forward * 128 + '0 0 16';
			print(sprintf("label fixture wall acted: fraction %.5f distance %.1f\n", trace_fraction, vlen(lf_wall - eye)));
		}
		lf_mode = mode;
		print(sprintf("label fixture mode %g\n", mode));
	}
	lf_body = b;
	lf_original = b.pb_rorg;
	point = eye + forward * (mode == 2 ? 1500 : (mode == 4 ? -256 : 256)) + '0 0 16';
	if (mode == 3) point = lf_wall;
	b.pb_rorg = point - [0, 0, b.pb_reye + 16];
};
void() LabelFixture_Restore =
{
	if (lf_body) lf_body.pb_rorg = lf_original;
	lf_body = world;
};
