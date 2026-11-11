// Test-only StartFrame wrapper, compiled by test_map_entity_runtime.py.
float mapprobe_phase, mapprobe_fail;
entity mapprobe_d1, mapprobe_d2;
void(float ok, string label) MapProbeAssert =
{
	if (!ok) mapprobe_fail += 1;
	bprint(PRINT_HIGH, sprintf("MAPPROBE %s %s\n", ok ? "PASS" : "FAIL", label));
};
void(entity p, entity b) MapProbeLand =
{
	p.flags = FL_ONGROUND;
	p.groundentity = b;
	SV_BhopFrame(p);
	p.flags = 0;
	SV_BhopFrame(p);
};
void() MapProbeCounters =
{
	local entity p, a, b;
	p = spawn(); a = spawn(); b = spawn();
	p.movetype = MOVETYPE_WALK;
	a.classname = b.classname = "func_bhop"; a.solid = b.solid = SOLID_BSP;
	a.LandingLimit = b.LandingLimit = 100;
	a.TimeLimit = b.TimeLimit = 100;
	a.spawnflags = b.spawnflags = 3;
	MapProbeLand(p, a); MapProbeLand(p, b); MapProbeLand(p, a);
	MapProbeAssert(a.count == 1 && b.count == 0, "reset-true A-air-B-air-A");
	MapProbeLand(p, a);
	MapProbeAssert(a.count == 2, "repeat-A counts second landing");
	a.count = b.count = 0;
	a.spawnflags = b.spawnflags = 1;
	p.vbsp_bhop_cntblk = world;
	MapProbeLand(p, a); MapProbeLand(p, b); MapProbeLand(p, a);
	MapProbeAssert(a.count == 2 && b.count == 1, "reset-false persists A-air-B-air-A");
	a.count = b.count = 0;
	a.spawnflags = b.spawnflags = 3;
	p.vbsp_bhop_cntblk = world;
	MapProbeLand(p, a);
	b.classname = "func_brush";
	MapProbeLand(p, b);
	MapProbeAssert(a.count == 0 && p.vbsp_bhop_cntblk == world, "ordinary ground consumes prior reset once");
	a.count = 7;
	p.flags = FL_ONGROUND;
	p.groundentity = b;
	SV_BhopFrame(p);
	MapProbeAssert(a.count == 7, "standing on ordinary ground preserves another landing count");
	p.flags = 0;
	SV_BhopFrame(p);
	a.count = 0;
	MapProbeLand(p, a);
	MapProbeAssert(a.count == 1, "ordinary ground clears reset-true count across air");
	a.classname = "func_brush";
	a.count = 17;
	p.vbsp_bhop_cntblk = a;
	MapProbeLand(p, b);
	MapProbeAssert(a.count == 17, "stale previous handle cannot clear another entity class");
	remove(p); remove(a); remove(b);
};
void(entity door) MapProbeGate =
{
	local entity oldself;
	local float id;
	oldself = self; self = door;
	MapProbeAssert(!SV_BunnyDoorMatch("bhop_wrong", "431ee83e"), "wrong map refused");
	MapProbeAssert(!SV_BunnyDoorMatch("bhop_bunnyrace", "431ee83f"), "wrong CRC refused");
	id = self.hammerid; self.hammerid = id + 1;
	MapProbeAssert(!SV_BunnyDoorMatch("bhop_bunnyrace", "431ee83e"), "wrong entity fingerprint refused");
	self.hammerid = id;
	self = oldself;
};
void() StartFrame =
{
	MapEntityOriginalStartFrame();
	if (time < 1) return;
	if (!mapprobe_phase)
	{
		MapProbeCounters();
		mapprobe_d1 = find(world, model, "*17");
		mapprobe_d2 = find(world, model, "*18");
		bprint(PRINT_HIGH, strcat("MAPPROBE mapcrc ", infokey(world, "*mapcrc"), "\n"));
		bprint(PRINT_HIGH, sprintf("MAPPROBE door origin=%v mins=%v maxs=%v\n", mapprobe_d1.origin, mapprobe_d1.mins, mapprobe_d1.maxs));
		bprint(PRINT_HIGH, sprintf("MAPPROBE door id=%g speed=%g lip=%g wait=%g flags=%g movedir=%v\n", mapprobe_d1.hammerid, mapprobe_d1.speed, mapprobe_d1.lip, mapprobe_d1.wait, mapprobe_d1.spawnflags, mapprobe_d1.movedir));
		MapProbeAssert(mapprobe_d1.vbsp_door_slide && mapprobe_d2.vbsp_door_slide, "both exact doors qualify");
		MapProbeGate(mapprobe_d1); MapProbeGate(mapprobe_d2);
		traceline('1660 -1040 -1216', '1660 -992 -1216', FALSE, world);
		MapProbeAssert(trace_ent == mapprobe_d1, "closed passage hits solid door");
		SV_FireOutput(find(world, model, "*19"), "OnStartTouch", world);
		MapProbeAssert(mapprobe_d1.vbsp_mv_state == TS_GOING_UP, "Open input acted");
		mapprobe_phase = 1;
	}
	else if (mapprobe_phase == 1 && time >= 2)
	{
		MapProbeAssert(mapprobe_d1.origin == '1412 -1016 -1216' && mapprobe_d2.origin == '2172 -1016 -1216', "both brushes reach authored endpoints");
		MapProbeAssert(mapprobe_d1.solid == SOLID_BSP && mapprobe_d2.solid == SOLID_BSP, "doors remain solid");
		traceline('1660 -1040 -1216', '1660 -992 -1216', FALSE, world);
		MapProbeAssert(trace_fraction == 1, "open passage trace clear");
		mapprobe_phase = 2;
	}
	else if (mapprobe_phase == 2 && time >= 4)
	{
		MapProbeAssert(mapprobe_d1.vbsp_mv_state == TS_AT_TOP && mapprobe_d1.velocity == '0 0 0', "authored wait holds open for three seconds");
		mapprobe_phase = 3;
	}
	else if (mapprobe_phase == 3 && time >= 5)
	{
		MapProbeAssert(mapprobe_d1.origin == '1660 -1016 -1216' && mapprobe_d2.origin == '1924 -1016 -1216', "authored wait automatically closes both brushes");
		traceline('1660 -1040 -1216', '1660 -992 -1216', FALSE, world);
		MapProbeAssert(trace_ent == mapprobe_d1, "closed passage blocks again");
		bprint(PRINT_HIGH, sprintf("MAPPROBE DONE failures=%g\n", mapprobe_fail));
		localcmd("quit\n");
		mapprobe_phase = 4;
	}
};
