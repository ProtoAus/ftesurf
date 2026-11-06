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
