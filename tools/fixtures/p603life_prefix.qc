//Test-only response seams; production native bodies still run unchanged.
float p603life_drawfails, p603life_modelfails;
float(float handle) P603Life_Draw =
{
	if (cvar("p603life_fail") == 1)
	{
		p603life_drawfails = p603life_drawfails + 1;
		return FALSE;
	}
	return NUI_Draw(handle);
};
float(float handle) P603Life_Commit =
{
	if (cvar("p603life_fail") == 2)
	{
		p603life_modelfails = p603life_modelfails + 1;
		return FALSE;
	}
	return NUI_ModelCommit(handle);
};
#define NUI_Draw P603Life_Draw
#define NUI_ModelCommit P603Life_Commit
