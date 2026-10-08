/* PRIVATE setup-only REAL hull application + snapshot controls.
 * NOT movement trajectories, collision queries, or physical-exit acceptance.
 * All touched mover inputs/state are restored before replay begins.
 */
static void OfframpHull_Check(int *n, int *failed, const char *label, qboolean ok)
{
	(*n)++;
	if (!ok)
		(*failed)++;
	Con_Printf("OFFRAMPHULL_CHECK %i %s %i\n", *n, label, !!ok);
}
static void OfframpHull_Selftest(void)
{
	static playermove_t saved;
	movevars_t savedvars = movevars;
	vec3_t savedmins, savedmaxs;
	struct offramp_hull_s standing, crouched, transition, later;
	int n = 0, failed = 0;

	saved = pmove;
	VectorCopy(pms_standmins, savedmins);
	VectorCopy(pms_standmaxs, savedmaxs);
	memset(&pmove, 0, sizeof(pmove));
	pms_standmins[0] = -19; pms_standmins[1] = -13; pms_standmins[2] = -99;
	pms_standmaxs[0] = 20; pms_standmaxs[1] = 17; pms_standmaxs[2] = 999;
	movevars.standheight = 70;
	movevars.duckheight = 41;
	pmove.pm_type = PM_NORMAL;
	PMSrc_ApplyHull();
	OfframpHull_Snapshot(&standing);
	OfframpHull_Check(&n, &failed, "actual-nondefault-standing-hull",
		standing.mins[0] == -19 && standing.mins[1] == -13 && standing.mins[2] == 0 &&
		standing.maxs[0] == 20 && standing.maxs[1] == 17 && standing.maxs[2] == 70 &&
		!standing.ducked && !standing.ducking && standing.raw_standheight == 70 && standing.raw_duckheight == 41);

	pmove.ducked = true;
	pmove.ducktime = 812.5f;
	pmove.oldbuttons = BUTTON_DUCK;
	PMSrc_ApplyHull();
	OfframpHull_Snapshot(&crouched);
	OfframpHull_Check(&n, &failed, "actual-crouched-hull-and-posture",
		crouched.maxs[2] == 41 && crouched.ducked && !crouched.ducking &&
		crouched.ducktime == 812.5f && crouched.oldbuttons == BUTTON_DUCK);

	pmove.ducked = false;
	pmove.ducking = true;
	pmove.ducktime = 925.5f;
	PMSrc_ApplyHull();
	OfframpHull_Snapshot(&transition);
	OfframpHull_Check(&n, &failed, "transition-flag-does-not-guess-small-hull",
		transition.maxs[2] == 70 && !transition.ducked && transition.ducking && transition.ducktime == 925.5f);

	pmove.capsule = true;
	pmove.pm_type = PM_DEAD;
	OfframpHull_Snapshot(&later);
	OfframpHull_Check(&n, &failed, "capsule-and-movement-type-copied",
		later.capsule && later.pmtype == PM_DEAD && !standing.capsule && standing.pmtype == PM_NORMAL);

	pmove.player_mins[0] = -999;
	pmove.player_maxs[2] = 999;
	pmove.ducktime = 0;
	movevars.standheight = 999;
	OfframpHull_Check(&n, &failed, "mutable-source-cannot-change-snapshot",
		standing.mins[0] == -19 && standing.maxs[2] == 70 && standing.raw_standheight == 70 && crouched.ducktime == 812.5f);
	OfframpHull_Check(&n, &failed, "contact-and-tick-snapshots-can-differ",
		crouched.maxs[2] == 41 && transition.maxs[2] == 70 && crouched.ducked && !transition.ducked);

	movevars.standheight = movevars.duckheight = 0;
	pmove.ducked = false;
	PMSrc_ApplyHull();
	OfframpHull_Snapshot(&standing);
	pmove.ducked = true;
	PMSrc_ApplyHull();
	OfframpHull_Snapshot(&crouched);
	OfframpHull_Check(&n, &failed, "raw-height-fallback-is-not-observed-height",
		standing.raw_standheight == 0 && crouched.raw_duckheight == 0 && standing.maxs[2] == 62 && crouched.maxs[2] == 45);

	pmove = saved;
	movevars = savedvars;
	VectorCopy(savedmins, pms_standmins);
	VectorCopy(savedmaxs, pms_standmaxs);
	Con_Printf("OFFRAMPHULL_SELFTEST %i %i\n", n, failed);
}
