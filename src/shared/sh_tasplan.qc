// Native-owned next-command presets. Shared parsing, never evidence import.
float fs_tasp_mode, fs_tasp_bits;
vector fs_tasp_move, fs_tasp_angles;

float(string name) FS_TASPlanMode =
{
	if (!strcmp(name, "live")) return TAS_PLAN_LIVE;
	if (!strcmp(name, "manual")) return TAS_PLAN_MANUAL;
	if (!strcmp(name, "left")) return TAS_PLAN_LEFT;
	if (!strcmp(name, "right")) return TAS_PLAN_RIGHT;
	return -1;
};

string(float mode) FS_TASPlanName =
{
	if (mode == TAS_PLAN_MANUAL) return "manual";
	if (mode == TAS_PLAN_LEFT) return "left";
	if (mode == TAS_PLAN_RIGHT) return "right";
	return "live";
};

float(float argc) FS_TASPlanRead =
{
	if (argc < 8 || argc > 10) return FALSE;
	fs_tasp_mode = FS_TASPlanMode(argv(2));
	if (fs_tasp_mode < 0) return FALSE;
	fs_tasp_move = fs_tasp_angles = '0 0 0';
	if (!FS_TASNumber(argv(3))) return FALSE;
	fs_tasp_move_x = fs_tas_number;
	if (!FS_TASNumber(argv(4))) return FALSE;
	fs_tasp_move_y = fs_tas_number;
	if (!FS_TASNumber(argv(5))) return FALSE;
	fs_tasp_angles_x = fs_tas_number;
	if (!FS_TASNumber(argv(6))) return FALSE;
	fs_tasp_angles_y = fs_tas_number;
	if (!FS_TASNumber(argv(7))) return FALSE;
	fs_tasp_bits = fs_tas_number;
	return (fs_tasp_move_x >= -450 && fs_tasp_move_x <= 450 && floor(fs_tasp_move_x) == fs_tasp_move_x &&
		fs_tasp_move_y >= -450 && fs_tasp_move_y <= 450 && floor(fs_tasp_move_y) == fs_tasp_move_y &&
		FS_TASEditValue(4, fs_tasp_angles_x) && FS_TASEditValue(5, fs_tasp_angles_y) &&
		fs_tasp_bits >= 0 && fs_tasp_bits <= 7 && floor(fs_tasp_bits) == fs_tasp_bits);
};
