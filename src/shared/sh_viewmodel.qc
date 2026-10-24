/* P970: versioned cosmetic setup only. Catalog-v1 IDs are append-only.
   Numeric wire data, never commands/paths, credentials or recorder state. */
#define VM_VERSION 1
#define VM_FIELDS 21i
// Presentation only: leave recorder/stat-source authority untouched.
#define STAT_VM_WEAPON 220
#define STAT_VM_EVENT 221
#define STAT_VM_INSPECT 222
#define STAT_VM_MODE 223
#define VM_ENABLED 1
#define VM_KNIFE 2
#define VM_HANDS 3
#define VM_LAYER 4
#define VM_ARMS 5
#define VM_FINISH 6
#define VM_SEED 7
#define VM_SCALE 8
#define VM_ROTATION 9
#define VM_FADE 10
#define VM_WEAR 11
#define VM_LEFT 12
#define VM_BOB 13
#define VM_SWAY 14
#define VM_FOV 15
#define VM_LEGACYFOV 16
#define VM_MUZZLE 17
#define VM_SFX 18
#define VM_UIX 19
#define VM_UIY 20

vector(float field) VM_Range =
{
	if (field == 0) return '1 1 1';
	if (field == VM_KNIFE) return '0 24 1';
	if (field == VM_HANDS) return '32 49 1';
	if (field == VM_LAYER) return '64 117 1';
	if (field == VM_FINISH) return '0 3 1';
	if (field == VM_SEED) return '0 1000 1';
	if (field == VM_SCALE) return '0.25 4 0';
	if (field == VM_ROTATION) return '0 360 0';
	if (field == VM_FOV || field == VM_LEGACYFOV) return '0 179 0';
	if (field == VM_BOB || field == VM_SWAY || field == VM_FADE || field == VM_WEAR ||
	    field == VM_SFX || field == VM_UIX || field == VM_UIY) return '0 1 0';
	return '0 1 1';
};

float(string text) VM_NumberToken =
{
	local float i, c, dot, digits;
	if (strlen(text) < 1 || strlen(text) > 12) return FALSE;
	dot = digits = 0;
	for (i = 0; i < strlen(text); i = i + 1)
	{
		c = str2chr(text, i);
		if (c == 45 && i == 0) continue;
		if (c == 46)
		{
			if (dot || !digits || i == strlen(text) - 1) return FALSE;
			dot = TRUE;
			continue;
		}
		if (c < 48 || c > 57) return FALSE;
		digits = digits + 1;
	}
	return (digits > 0);
};

float(float field, float value) VM_ValueOK =
{
	local vector limits;
	limits = VM_Range(field);
	if (!(value >= limits_x && value <= limits_y)) return FALSE;
	if (limits_z && value != floor(value)) return FALSE;
	return TRUE;
};

string(float value) VM_Number =
{
	local string text;
	text = sprintf("%.4f", value);
	while (strlen(text) > 0 && str2chr(text, strlen(text) - 1) == 48)
		text = substring(text, 0, strlen(text) - 1);
	if (str2chr(text, strlen(text) - 1) == 46) text = substring(text, 0, strlen(text) - 1);
	if (!strcmp(text, "-0")) return "0";
	return text;
};

string(string packed) VM_Normalize =
{
	local float i, n, value;
	local string result, token;
	if (strlen(packed) > 256) return "";
	result = "";
	n = tokenizebyseparator(packed, ",");
	if (n != VM_FIELDS) return "";
	for (i = 0; i < VM_FIELDS; i = i + 1)
	{
		token = argv(i);
		if (!VM_NumberToken(token)) return "";
		value = stof(token);
		if (!VM_ValueOK(i, value)) return "";
		result = strcat(result, i ? "," : "", VM_Number(value));
	}
	return result;
};

float(string packed, float field) VM_Get =
{
	if (field < 0 || field >= VM_FIELDS) return 0;
	tokenizebyseparator(packed, ",");
	return stof(argv(field));
};

string(string packed) VM_PublicSetup =
{
	local float i;
	local string result, value;
	if (tokenizebyseparator(packed, ",") != VM_FIELDS) return "";
	result = "";
	for (i = 0; i < VM_FIELDS; i = i + 1)
	{
		value = argv(i);
		if (i == VM_UIX || i == VM_UIY) value = "0";
		result = strcat(result, i ? "," : "", value);
	}
	return result;
};
