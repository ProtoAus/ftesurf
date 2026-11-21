// P1345: shared native final-camera predicate, not a pointcontents approximation.
// The latch is visual-only; body capture, recorder and input state keep advancing.
float cl_scene_worldonly;

float() CL_SceneWorldOnly =
{
	local float prop;

	if (!cvar("r_voidscene"))
		return FALSE;
	prop = 228; // VF_WORLDONLY; dynamic argument also supports older fteqcc tables.
	return getproperty(prop);
};

// P1698: on a Source map the engine culls entities by each view's PVS (it sets r_entpvs_active); CSQC's own
// polygons follow, and the engine's checkpvs then judges by the same rules (an eye in solid from the last good
// cluster). One eye a frame; cached answers renew each 0.1 s or 64 units of eye travel. Off under a TAS viz
// camera, which moves VF_ORIGIN after these draw.
float(entity e) Portal_EyesSee;
float() TASOptViz_CamOn;
.float scene_pvsep, scene_pvsok;
float  scene_pvs_on, scene_pvs_epoch, scene_pvs_next, scene_pvs_frame;
vector scene_pvs_eye, scene_pvs_epocheye;
void() Scene_PVSFrame =
{
	if (scene_pvs_frame == cltime)
		return;
	scene_pvs_frame = cltime;
	scene_pvs_eye = getproperty(VF_ORIGIN);
	scene_pvs_on = (cvar("r_entpvs_active") && !TASOptViz_CamOn());   // brackets: = binds tighter than &&
	if (cltime >= scene_pvs_next || cltime < scene_pvs_next - 0.2 || vlen(scene_pvs_eye - scene_pvs_epocheye) > 64)
	{
		scene_pvs_epoch = scene_pvs_epoch + 1;
		scene_pvs_next = cltime + 0.1;
		scene_pvs_epocheye = scene_pvs_eye;
	}
};
// e must be linked where it is drawn. Cached: static things (ropes, emitters); not: a body that moves.
float(entity e, float cached) Scene_InPVS =
{
	Scene_PVSFrame();
	if (!scene_pvs_on)
		return TRUE;
	if (cached && e.scene_pvsep == scene_pvs_epoch)
		return e.scene_pvsok;
	e.scene_pvsep = scene_pvs_epoch;
	e.scene_pvsok = checkpvs(scene_pvs_eye, e);
	if (!e.scene_pvsok)
		e.scene_pvsok = Portal_EyesSee(e);
	return e.scene_pvsok;
};
