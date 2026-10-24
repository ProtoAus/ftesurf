/* Installed Legacy metadata. No game assets or inventory are distributed. */
#define KCAT_NAME 0i
#define KCAT_MODEL 1i
#define KCAT_BASE 2i
#define KCAT_MASK 3i
#define KCAT_PAINT 4i
#define KCAT_HIDE 5i
#define KCAT_SKIN 6i
#define KCAT_DRAW 7i
#define KCAT_IDLE 8i
#define KCAT_INSPECT 9i
#define KCAT_LIGHT 10i
#define KCAT_HEAVY 11i
#define KCAT_LIGHTHIT 12i
#define KCAT_HEAVYHIT 13i
#define KCAT_REMAP 14i
#define KCAT_FAMILY 15i
#define KCAT_NEUTRAL 16i
#define KCAT_FIELDS 17i
#define KCAT_ARMS 32i
#define KCAT_LAYERS 64i
string *kcat_values;
float kcat_knives, kcat_hands, kcat_layers;
void() KCAT_Data;

void(int row, int field, string value) KCAT_Set =
{
	if (row < 0i || row >= 128i || field < 0i || field >= KCAT_FIELDS) return;
	kcat_values[row * KCAT_FIELDS + field] = value;
};
string(float row, int field) KCAT_Get =
{
	if (!kcat_values) return "";
	if (row < 0 || row >= 128 || row != floor(row)) return "";
	if (field < 0i || field >= KCAT_FIELDS) return "";
	return kcat_values[(int)row * KCAT_FIELDS + field];
};
void(int row, string label, string model) KCAT_Row =
{
	KCAT_Set(row, KCAT_NAME, label); KCAT_Set(row, KCAT_MODEL, model);
};
void(int row, string base, string mask, string paint, string hide, string skin, string remap) KCAT_Mesh =
{
	KCAT_Set(row, KCAT_BASE, base); KCAT_Set(row, KCAT_MASK, mask);
	KCAT_Set(row, KCAT_PAINT, paint); KCAT_Set(row, KCAT_HIDE, hide);
	KCAT_Set(row, KCAT_SKIN, skin); KCAT_Set(row, KCAT_REMAP, remap);
};
void(int row, string draw, string idle, string inspect, string light, string heavy, string lighthit, string heavyhit) KCAT_Clips =
{
	KCAT_Set(row, KCAT_DRAW, draw); KCAT_Set(row, KCAT_IDLE, idle); KCAT_Set(row, KCAT_INSPECT, inspect);
	KCAT_Set(row, KCAT_LIGHT, light); KCAT_Set(row, KCAT_HEAVY, heavy);
	KCAT_Set(row, KCAT_LIGHTHIT, lighthit); KCAT_Set(row, KCAT_HEAVYHIT, heavyhit);
};
void() KCAT_Register =
{
	kcat_values = (string*)memalloc(128i * KCAT_FIELDS * 4i);
	memfill8((void*)kcat_values, 0i, 128i * KCAT_FIELDS * 4i);
	KCAT_Data();
	registercvar("cl_knife_choice", "", CVAR_ARCHIVE);
	registercvar("cl_knife_arm_choice", "", CVAR_ARCHIVE);
	registercvar("cl_knife_sleeve", "auto", CVAR_ARCHIVE);
};

float(float row) KCAT_Valid =
{
	if (row < 0 || row >= 128 || row != floor(row)) return FALSE;
	return strcmp(KCAT_Get(row, KCAT_NAME), "") != 0;
};
float(float row) KCAT_Available =
{
	local string model;
	local float file;
	if (!KCAT_Valid(row)) return FALSE;
	model = KCAT_Get(row, KCAT_MODEL);
	if (!strcmp(model, "")) return TRUE;
	// GA_Exists is sound-only: it prepends sound/, which hides installed models.
	file = fopen(model, FILE_READ);
	if (file < 0) return FALSE;
	fclose(file);
	return TRUE;
};
float(float base, float count, string choice, float fallback) KCAT_Find =
{
	local float i;
	if (strcmp(choice, ""))
	for (i = base; i < base + count; i = i + 1)
		if (!strcmp(KCAT_Get(i, KCAT_MODEL), choice)) return i;
	return fallback;
};
float() KCAT_Knife =
{
	local float legacy;
	legacy = bound(0, floor(cvar("cl_knife_model")), 2);
	if (legacy != 1) return legacy;
	return KCAT_Find(0, kcat_knives, cvar_string("cl_knife_choice"), 1);
};
float() KCAT_Hands =
{
	if (cvar("cl_knife_arm_model") == 1) return (float)KCAT_ARMS + 1;
	return KCAT_Find((float)KCAT_ARMS, kcat_hands, cvar_string("cl_knife_arm_choice"), (float)KCAT_ARMS);
};
float() KCAT_Layer =
{
	local string value;
	value = cvar_string("cl_knife_sleeve");
	if (!strcmp(value, "none")) return (float)KCAT_LAYERS + 1;
	return KCAT_Find((float)KCAT_LAYERS + 2, kcat_layers - 2, value, (float)KCAT_LAYERS);
};
float() KCAT_ActiveLayer =
{
	local float row;
	if (KCAT_Hands() < (float)KCAT_ARMS + 2) return -1; // complete rigs have sleeves
	row = KCAT_Layer();
	if (row == (float)KCAT_LAYERS + 1) return -1;
	if (row == (float)KCAT_LAYERS)
		return KCAT_Find((float)KCAT_LAYERS + 2, kcat_layers - 2, "models/weapons/v_models/arms/sas/v_sleeve_sas.mdl", -1);
	return row;
};

void(float row) KCAT_ApplyChoice =
{
	if (!KCAT_Valid(row)) return;
	if (row < kcat_knives)
	{
		// Older server progs still see a valid CSS/Butterfly/M9 fallback.
		cvar_set("cl_knife_model", (row == 0) ? "0" : ((row == 2) ? "2" : "1"));
		cvar_set("cl_knife_choice", (row <= 2) ? "" : KCAT_Get(row, KCAT_MODEL));
	}
	else if (row >= (float)KCAT_ARMS && row < (float)KCAT_ARMS + kcat_hands)
	{
		cvar_set("cl_knife_arm_model", (row == (float)KCAT_ARMS + 1) ? "1" : "0");
		cvar_set("cl_knife_arm_choice", (row < (float)KCAT_ARMS + 2) ? "" : KCAT_Get(row, KCAT_MODEL));
		cvar_set("cl_knife_arms", "1");
	}
	else if (row >= (float)KCAT_LAYERS && row < (float)KCAT_LAYERS + kcat_layers)
	{
		if (row == (float)KCAT_LAYERS) cvar_set("cl_knife_sleeve", "auto");
		else if (row == (float)KCAT_LAYERS + 1) cvar_set("cl_knife_sleeve", "none");
		else cvar_set("cl_knife_sleeve", KCAT_Get(row, KCAT_MODEL));
	}
};

// Owned zoned result, or empty. Called on model/style changes, not each frame.
string(string surfaces, string shader) KCAT_Rules =
{
	local float count, i;
	local string result, previous;
	result = "";
	if (!strcmp(surfaces, "")) return result;
	count = min(64, tokenizebyseparator(surfaces, "|"));
	for (i = 0; i < count; i = i + 1)
	{
		previous = result;
		result = strzone(strcat(result, sprintf("replace \"%s\" \"%s\"\n", argv(i), shader)));
		if (strcmp(previous, "")) strunzone(previous);
	}
	return result;
};
string(float row) KCAT_NeutralRules =
{
	local float i, count;
	local string result, previous, shader, surface, texture;
	result = "";
	count = min(128, tokenizebyseparator(KCAT_Get(row, KCAT_NEUTRAL), "|"));
	for (i = 0; i + 1 < count; i = i + 2)
	{
		surface = argv(i); texture = argv(i + 1);
		shader = sprintf("ftesurf/knife_glove_%g_%g", row, i);
		shaderforname(shader, strcat("{\nprogram knife_glove\n{ map ", texture, " }\n}\n"));
		previous = result;
		result = strzone(strcat(result, sprintf("replace \"%s\" \"%s\"\n", surface, shader)));
		if (strcmp(previous, "")) strunzone(previous);
	}
	return result;
};

string(float row) KCAT_SkinRules =
{
	local string rules, skin, result, neutral;
	local float shader;
	rules = KCAT_Get(row, KCAT_REMAP);
	skin = "";
	if (strcmp(KCAT_Get(row, KCAT_SKIN), ""))
	{
		// Bare skin is not metal; keep this off world and glove materials.
		shader = shaderforname("ftesurf/knife_bare_skin", "{\nprogram defaultskin\n{ map materials/models/weapons/v_models/arms/v_model_base_arms_color.vtf }\n}\n");
		if (shader > 0) skin = KCAT_Rules(KCAT_Get(row, KCAT_SKIN), "ftesurf/knife_bare_skin");
	}
	neutral = KCAT_NeutralRules(row);
	if (!strcmp(skin, "") && !strcmp(rules, "") && !strcmp(neutral, "")) return "";
	result = strzone(strcat(skin, neutral, rules));
	if (strcmp(skin, "")) strunzone(skin);
	if (strcmp(neutral, "")) strunzone(neutral);
	return result;
};
