/* Local editor overrides, numeric data only. Public lobbies never load these.
   Names and limits are shared by the editor and server; not arbitrary cvars. */
#define MAPSET_COUNT 6

string(float i) MapSet_Name =
{
	if (i == 0) return "sv_maxvelocity";
	if (i == 1) return "sv_gravity";
	if (i == 2) return "sv_airaccelerate";
	if (i == 3) return "sv_accelerate";
	if (i == 4) return "sv_maxspeed";
	return "sv_friction";
};

string(float i) MapSet_Label =
{
	if (i == 0) return "Max velocity";
	if (i == 1) return "Gravity";
	if (i == 2) return "Air acceleration";
	if (i == 3) return "Ground acceleration";
	if (i == 4) return "Max ground speed";
	return "Friction";
};

float(float i) MapSet_Min =
{
	if (i == 0 || i == 4) return 1;
	if (i == 1) return 1;
	return 0;
};

float(float i) MapSet_Max =
{
	if (i == 0) return 100000;
	if (i == 1 || i == 4) return 10000;
	if (i == 5) return 100;
	return 10000;
};

float(float i, float v) MapSet_Valid =
{
	// Both ordered comparisons must succeed: NaN and infinities fail too.
	return (v >= MapSet_Min(i) && v <= MapSet_Max(i));
};

float(string s) MapSet_Number =
{
	local float i, c, digits, dot;
	digits = dot = 0;
	if (s == "" || strlen(s) > 16) return FALSE;
	for (i = 0; i < strlen(s); i = i + 1)
	{
		c = str2chr(s, i);
		if (c == '.')
		{
			if (dot) return FALSE;
			dot = TRUE;
		}
		else if (c >= '0' && c <= '9') digits = digits + 1;
		else return FALSE;
	}
	return digits > 0;
};

string(string map) MapSet_Path =
{
	return strcat("maps/settings/local/", map, ".cfg");
};
