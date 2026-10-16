/*
  P732: explicit KSF compatibility for the known Momentum Monolith B4 port.
  Its final1662/398.301 vector applied inside the ramp loses horizontal speed.
  Preserve the reference entry/reapplication/exit phases instead. Not a generic
  StrictMode/VScript implementation. Provenance: tools/p732monolith.md.
*/
// Existing native mover counter, declared here so the profile and timer share it.
.float run_movetick;
.entity run_mono_pad;
.float run_mono_phase;
.float run_mono_deadline;
.float run_mono_tick;
.float run_mono_cmdtick;
.float run_mono_jumpbefore;
.vector run_mono_preorg;

void(entity e) SV_MonolithB4Frame;

void(entity e) SV_MonolithB4Reset =
{
	e.run_mono_pad = world;
	e.run_mono_phase = e.run_mono_deadline = 0;
	e.run_mono_tick = -1;
	e.run_mono_cmdtick = e.run_movetick;
	e.run_mono_jumpbefore = e.run_jumpcmd;
};

// Drop only this zero-tick command's new latch; never raise a consumed latch.
void(entity e) SV_MonolithB4InputEnd =
{
	if (!e.run_mono_phase) return;
	if (e.run_movetick != e.run_mono_cmdtick) return;
	if (!e.run_mono_jumpbefore) e.run_jumpcmd = FALSE;
};

float(entity pad) SV_MonolithB4Pad =
{
	if (strcmp(mapname, "surf_monolith")) return FALSE;
	if (strcmp(pad.classname, "trigger_setspeed")) return FALSE;
	if (strcmp(pad.model, "*108")) return FALSE;
	if (!pad.StrictMode) return FALSE;
	if (pad.HorizontalSpeedMode != SSH_SETDIR || pad.VerticalSpeedMode != SSV_SET) return FALSE;
	if (pad.HorizontalSpeed != 1662 || fabs(pad.VerticalSpeed - 398.301) > 0.01) return FALSE;
	if (pad.HorizontalSpeedAngle != '0 180 0') return FALSE;
	if (SV_Key2(pad.EveryTick, pad.everytick) || SV_Key2(pad.OnThink, pad.onthink)) return FALSE;
	return TRUE;
};

void(entity e) SV_MonolithB4Command =
{
	SV_MonolithB4InputEnd(e);
	e.run_mono_preorg = e.origin;
	e.run_mono_cmdtick = e.run_movetick;
	e.run_mono_jumpbefore = e.run_jumpcmd;
	if (!e.run_mono_phase) return;
	if (!e.run_mono_pad || e.movetype != MOVETYPE_WALK || time > e.run_mono_deadline)
	{
		SV_MonolithB4Reset(e);
		return;
	}
	if (!SV_MonolithB4Pad(e.run_mono_pad))
	{
		SV_MonolithB4Reset(e);
		return;
	}
	// Finalize the previous move before another command in this packet.
	SV_MonolithB4Frame(e);
	// Only the move immediately after reapplication can manufacture this lift.
	if (e.run_mono_phase == 2)
	{
		if (e.run_movetick == e.run_mono_tick)
		{
			e.run_pushed = TRUE;
			e.run_pushlift = TRUE;
		}
		else
			e.run_mono_phase = 3;
	}
};

float(entity pad, entity e) SV_MonolithB4Touch =
{
	local vector vel;
	if (!SV_MonolithB4Pad(pad)) return FALSE;
	if (e.run_movetickrate <= 0) return FALSE;
	if (e.run_mono_pad != pad || !e.run_mono_phase)
	{
		if (e.movetype != MOVETYPE_WALK) return FALSE;
		if (!(e.flags & FL_ONGROUND) || e.button2 || e.run_jumpcmd) return FALSE;
		if (e.velocity_x >= 0) return FALSE;
		// Cross the opposed face; never initialise from a side/warp arrival.
		if (e.run_mono_preorg_x + e.mins_x < pad.absmax_x - 1) return FALSE;
		e.run_mono_pad = pad;
		e.run_mono_phase = 1;
		e.run_mono_deadline = time + 0.5;
		e.run_mono_tick = e.run_movetick;
		vel = '-1662 0 0';
	}
	else
	{
		pad.vbsp_ss_stamp = time;
		SV_MonolithB4InputEnd(e);
		if (e.run_movetick == e.run_mono_cmdtick) return TRUE;
		// Do not erase a real rise before JumpWatch's velocity-edge gate.
		// Consume this contact: legacy fallback must not replace it either.
		if (e.run_jumpcmd || e.button2)
		{
			SV_MonolithB4Reset(e);
			return TRUE;
		}
		if (e.run_mono_tick == e.run_movetick) return TRUE;
		if (e.run_mono_phase != 1) return TRUE;
		e.run_mono_phase = 2;
		e.run_mono_tick = e.run_movetick;
		// CSS entry1760 + (reference endpoint1662 - CSS endpoint1638).
		vel = '-1784 0 0';
	}
	pad.vbsp_ss_stamp = time;
	// A bounded following slope move supplies Z. Real jumpcmd still wins;
	// never clear any earlier hopped/dirty taint to make this profile eligible.
	e.run_pushed = TRUE;
	e.run_pushlift = TRUE;
	e.velocity = vel;
	SV_RecWarp(e, "speed");
	return TRUE;
};

void(entity e) SV_MonolithB4Frame =
{
	local entity pad;
	local vector vel;
	if (!e.run_mono_phase) return;
	SV_MonolithB4InputEnd(e);
	pad = e.run_mono_pad;
	if (!pad) { SV_MonolithB4Reset(e); return; }
	if (!SV_MonolithB4Pad(pad) || e.movetype != MOVETYPE_WALK || time > e.run_mono_deadline)
	{
		SV_MonolithB4Reset(e);
		return;
	}
	if (e.origin_y + e.maxs_y < pad.absmin_y || e.origin_y + e.mins_y > pad.absmax_y ||
	    e.origin_z + e.maxs_z < pad.absmin_z || e.origin_z + e.mins_z > pad.absmax_z ||
	    e.origin_x + e.mins_x > pad.absmax_x)
	{
		SV_MonolithB4Reset(e);
		return;
	}
	if (e.origin_x + e.maxs_x < pad.absmin_x)
	{
		vel = e.velocity;
		vel_x = -1662;
		vel_y = 0;
		e.velocity = vel;
		SV_RecWarp(e, "speed");
		SV_MonolithB4Reset(e);
	}
};
