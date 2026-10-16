// ISOLATED TEST-ONLY FIXTURE. Never add to production manifests or live lobbies.
// Test-only fixtures. Never included in production .src.
float p732_pass, p732_fail;
void(string label, float yes) P732_Check =
{
	if (yes) { p732_pass = p732_pass + 1; print("P732 PASS ", label, "\n"); }
	else { p732_fail = p732_fail + 1; print("P732 FAIL ", label, "\n"); }
};
void(entity p) P732_Pad =
{
	p.classname = "trigger_setspeed"; p.model = "*108";
	p.StrictMode = 1; p.HorizontalSpeedMode = 0; p.VerticalSpeedMode = 1;
	p.HorizontalSpeed = 1662; p.VerticalSpeed = 398.301;
	p.HorizontalSpeedAngle = '0 180 0';
	p.EveryTick = p.everytick = p.OnThink = p.onthink = 0;
	p.absmin = '-11105 -5553 15935'; p.absmax = '-11007 -4975 16033';
};
void(entity e) P732_Player =
{
	SV_MonolithB4Reset(e); e.run_movetick = 0; e.run_movetickrate = 0.015;
	e.classname = "p732_fake"; e.movetype = MOVETYPE_WALK;
	e.origin = '-10988 -5454 15936';
	e.mins = '-16 -16 0'; e.maxs = '16 16 72';
	e.velocity = '-260 0 0'; e.flags = FL_ONGROUND;
	e.button2 = e.run_jumpcmd = e.run_pushed = e.run_pushlift = 0;
	SV_MonolithB4Command(e);
	e.origin = '-10992 -5454 15936';
};
void() P732_Units =
{
	local entity p, e, b, saved;
	local vector v;
	p = spawn(); e = spawn(); b = spawn();
	P732_Pad(p); P732_Player(e);
	P732_Check("known pad", SV_MonolithB4Pad(p));
	P732_Check("grounded opposed entry acts", SV_MonolithB4Touch(p,e));
	P732_Check("entry1662 zeroZ", e.velocity == '-1662 0 0');
	P732_Check("entry phase1 attribution", (e.run_mono_phase == 1 && e.run_pushed && e.run_pushlift));
	SV_MonolithB4Touch(p,e);
	P732_Check("same-command duplicate cannot reapply", (e.run_mono_phase == 1 && e.velocity == '-1662 0 0'));
	P732_Player(b); SV_MonolithB4Touch(p,b);
	P732_Check("two players independent", (b.run_mono_phase == 1 && e.run_mono_phase == 1));
	SV_MonolithB4Command(e); SV_MonolithB4Touch(p,e);
	P732_Check("zero-tick command cannot reapply", (e.run_mono_phase == 1 && e.velocity == '-1662 0 0'));
	e.run_movetick = e.run_movetick + 1;
	SV_MonolithB4Command(e); e.flags = 0; e.origin = '-11016 -5454 15942'; e.velocity = '-1562 0 375';
	SV_MonolithB4Touch(p,e);
	P732_Check("one next-contact reapplication", (e.run_mono_phase == 2 && e.velocity == '-1784 0 0'));
	P732_Check("other player not advanced", b.run_mono_phase == 1);
	e.run_pushed = e.run_pushlift = 0; SV_MonolithB4Command(e);
	P732_Check("exact next command has causal lift", (e.run_pushed && e.run_pushlift));
	e.run_pushed = e.run_pushlift = 0; SV_MonolithB4Command(e);
	P732_Check("zero-tick command retains pending physical attribution", (e.run_pushed && e.run_pushlift && e.run_mono_phase == 2));
	e.run_movetick = e.run_movetick + 1;
	e.velocity = '-1668.867 0 429'; e.origin = '-11041 -5454 15949';
	SV_MonolithB4Touch(p,e);
	P732_Check("third contact does not reset velocity", e.velocity == '-1668.867 0 429');
	e.run_pushed = e.run_pushlift = 0; SV_MonolithB4Command(e);
	P732_Check("causal marker expires after one move", (!e.run_pushed && !e.run_pushlift && e.run_mono_phase == 3));
	e.origin = '-11140 -5454 15974'; e.velocity = '-1663 27 403'; SV_MonolithB4Frame(e);
	P732_Check("downstream exit clampsXY retainsZ", e.velocity == '-1662 0 403');
	P732_Check("exit clears pending state", (!e.run_mono_phase && !e.run_mono_pad));
	P732_Player(e); SV_MonolithB4Touch(p,e); e.run_movetick = 1;
	e.origin = '-11140 -5454 15974'; e.velocity = '-1663 27 403'; SV_MonolithB4Command(e);
	P732_Check("next command finalizes prior exit before physics", (!e.run_mono_phase && e.velocity == '-1662 0 403'));

	P732_Player(e); p.model = "*109"; P732_Check("other model falls back", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	p.classname = "trigger_multiple"; P732_Check("CSS script class not hijacked", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	p.StrictMode = 0; P732_Check("non-strict pad falls back", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	p.HorizontalSpeedMode = 1; P732_Check("other horizontal mode falls back", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	p.VerticalSpeedMode = 2; P732_Check("other vertical mode falls back", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	p.HorizontalSpeed = 1663; P732_Check("changed author speed falls back", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	p.VerticalSpeed = 399; P732_Check("changed author Z falls back", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	p.HorizontalSpeedAngle = '0 0 0'; P732_Check("changed author angle falls back", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	p.everytick = 1; P732_Check("legacy everytick falls back", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	p.OnThink = 1; P732_Check("on-think falls back", !SV_MonolithB4Touch(p,e)); P732_Pad(p);
	P732_Check("negative guards do not write velocity", e.velocity == '-260 0 0');
	P732_Check("negative guards do not leave pending state", !e.run_mono_phase);
	e.run_movetickrate = 0; P732_Check("legacy engine without clock falls back", !SV_MonolithB4Touch(p,e)); P732_Player(e);

	e.flags = 0; P732_Check("airborne entry falls back", !SV_MonolithB4Touch(p,e)); P732_Player(e);
	e.button2 = 1; P732_Check("input jump entry falls back", !SV_MonolithB4Touch(p,e)); P732_Player(e);
	e.run_jumpcmd = 1; P732_Check("earlier packet jump entry falls back", !SV_MonolithB4Touch(p,e)); P732_Player(e);
	e.velocity = '260 0 0'; P732_Check("reverse entry falls back", !SV_MonolithB4Touch(p,e)); P732_Player(e);
	e.movetype = MOVETYPE_NOCLIP; P732_Check("noclip entry falls back", !SV_MonolithB4Touch(p,e)); P732_Player(e);
	e.run_mono_preorg_x = -11050; P732_Check("side or warp arrival falls back", !SV_MonolithB4Touch(p,e)); P732_Player(e);
	e.run_t_hopped = e.run_t_dirty = 1; SV_MonolithB4Touch(p,e);
	P732_Check("older hopped and dirty are never forgiven", (e.run_t_hopped && e.run_t_dirty));
	e.run_jumpcmd = 1; SV_MonolithB4Command(e); e.run_movetick = e.run_movetick + 1; SV_MonolithB4Touch(p,e);
	P732_Check("real jump latch survives pending reapplication", e.run_jumpcmd);
	P732_Check("existing rejection predicate still wins", (!e.run_pushed || e.run_jumpcmd));

	P732_Player(e); SV_MonolithB4Touch(p,e); e.origin_y = -4800; v = e.velocity; SV_MonolithB4Frame(e);
	P732_Check("side exit clears without injecting speed", (!e.run_mono_phase && e.velocity == v));
	P732_Player(e); SV_MonolithB4Touch(p,e); e.run_mono_deadline = time - 1; e.run_pushed = 0; SV_MonolithB4Command(e);
	P732_Check("timeout clears before attributing lift", (!e.run_mono_phase && !e.run_pushed));
	P732_Player(e); SV_MonolithB4Touch(p,e); p.model = "*109"; e.run_pushed = 0; SV_MonolithB4Command(e);
	P732_Check("changed pad clears before attribution", (!e.run_mono_phase && !e.run_pushed)); P732_Pad(p);
	P732_Player(e); SV_MonolithB4Touch(p,e); v = e.velocity; SV_TimerWarped(e);
	e.origin_x = -11200; SV_MonolithB4Frame(e);
	P732_Check("real warp funnel prevents deferred exit write", (!e.run_mono_phase && e.velocity == v));
	P732_Player(e); SV_MonolithB4Touch(p,e); saved = self; self = e; e.run_pmhold = 1; PlayerPreThink(); self = saved;
	P732_Check("held command clears pending state", !e.run_mono_phase); e.run_pmhold = 0;
	P732_Player(e); SV_MonolithB4Touch(p,e);
	P732_Check("clean reentry restarts first phase", (e.run_mono_phase == 1 && e.velocity == '-1662 0 0'));
	print(sprintf("P732 UNIT SUMMARY pass%g fail%g\n", p732_pass, p732_fail));
	remove(e); remove(b); remove(p); remove(self);
};
void() p732_unit = { self.think = P732_Units; self.nextthink = time + 0.2; };

// Real socket client packet-end lifecycle probes; never in the product manifest.
float p732_case_wait, p732_case_pk, p732_case_zones, p732_case_hold, p732_case_move, p732_case_at;
entity p732_case_player;
void() P732_PacketThink =
{
	local entity e;
	local float request, ok, mark;
	request = cvar("p732_case");
	if (p732_case_wait)
	{
		e = p732_case_player;
		if (e.run_pkn > p732_case_pk || time > p732_case_at + 3)
		{
			ok = (!e.run_bhop_launch_zone && !e.run_bhop_launch_denied &&
			      !e.run_pushed && !e.run_jumpcmd && !e.run_mono_phase && e.run_pkn > p732_case_pk);
			print(sprintf("P732 PACKET case%g acted%g hold%g clean%g\n", p732_case_wait,
			              e.run_pkn > p732_case_pk, e.run_pmhold, ok));
			zone_count = p732_case_zones;
			e.run_pmhold = p732_case_hold;
			e.movetype = p732_case_move;
			p732_case_wait = 0;
			cvar_set("p732_case", "0");
		}
	}
	else if (request == 4)
	{
		e = find(world, classname, "player");
		if (e)
		{
			mark = SV_RecWritePrefix(e, "data/p732-evidence/run.rec");
			print(sprintf("P732 PREFIX mark%g live%g\n", mark, SV_RecLive(e)));
			cvar_set("p732_case", "0");
		}
	}
	else if (request > 0)
	{
		e = find(world, classname, "player");
		if (e)
		{
			p732_case_player = e;
			p732_case_wait = request; p732_case_pk = e.run_pkn; p732_case_at = time;
			p732_case_zones = zone_count; p732_case_hold = e.run_pmhold; p732_case_move = e.movetype;
			e.run_bhop_launch_zone = e.run_bhop_launch_denied = e.run_pushed = e.run_jumpcmd = 1;
			e.run_mono_pad = find(world, model, "*108");
			e.run_mono_phase = 2; e.run_mono_tick = e.run_movetick; e.run_mono_deadline = time + 1;
			if (request == 2) zone_count = 0;
			if (request == 3) e.run_pmhold = 1;
			print(sprintf("P732 PACKET seeded%g pk%g\n", request, e.run_pkn));
		}
	}
	self.nextthink = time + 0.01;
};
void() p732_packet_probe =
{
	registercvar("p732_case", "0");
	self.think = P732_PacketThink;
	self.nextthink = time + 0.1;
};
