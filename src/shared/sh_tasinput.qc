// P1065: console numbers are plain decimals, never stof's malformed=>zero.
float fs_tas_number;
float(string text) FS_TASNumber =
{
	local float i, n, c, dots, digits;

	n = strlen(text);
	if (n < 1 || n > 32) return FALSE;
	i = dots = digits = 0;
	c = str2chr(text, 0);
	if (c == 43 || c == 45) i = 1;
	for (; i < n; i = i + 1)
	{
		c = str2chr(text, i);
		if (c >= 48 && c <= 57) digits = digits + 1;
		else if (c == 46 && dots == 0) dots = 1;
		else return FALSE;
	}
	if (!digits) return FALSE;
	fs_tas_number = stof(text);
	return TRUE;
};

float(string name) FS_TASEditField =
{
	if (!strcmp(name, "forward")) return 1;
	if (!strcmp(name, "side")) return 2;
	if (!strcmp(name, "up")) return 3;
	if (!strcmp(name, "pitch")) return 4;
	if (!strcmp(name, "yaw")) return 5;
	if (!strcmp(name, "jump")) return 6;
	if (!strcmp(name, "duck")) return 7;
	if (!strcmp(name, "walk")) return 8;
	return 0;
};

string(float field) FS_TASEditName =
{
	if (field == 1) return "forward";
	if (field == 2) return "side";
	if (field == 3) return "up";
	if (field == 4) return "pitch";
	if (field == 5) return "yaw";
	if (field == 6) return "jump";
	if (field == 7) return "duck";
	if (field == 8) return "walk";
	return "unchanged";
};

float(float field, float value) FS_TASEditValue =
{
	if (field >= 1 && field <= 3)
		return (value >= -32768 && value <= 32767 && floor(value) == value);
	if (field == 4) return (value >= -89 && value <= 89);
	if (field == 5) return (value >= -360 && value <= 360);
	if (field >= 6 && field <= 8) return (value == 0 || value == 1);
	return FALSE;
};

float(float degrees) FS_TASAngleWord =
{
	local float word;

	word = rint(degrees * 65536 / 360);
	return word - floor((word + 32768) / 65536) * 65536;
};
