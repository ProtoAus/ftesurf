// Native-owned next-command presets. Shared parsing, never evidence import.
float fs_tasp_mode, fs_tasp_bits, fs_tasp_amount, fs_tasp_follow;
vector fs_tasp_move, fs_tasp_angles;

float(string name) FS_TASPlanMode =
{
	if (!strcmp(name, "live")) return TAS_PLAN_LIVE;
	if (!strcmp(name, "manual")) return TAS_PLAN_MANUAL;
	if (!strcmp(name, "left")) return TAS_PLAN_LEFT;
	if (!strcmp(name, "right")) return TAS_PLAN_RIGHT;
	if (!strcmp(name, "guide")) return TAS_PLAN_GUIDE;
	if (!strcmp(name, "hold")) return TAS_PLAN_HOLD;
	return -1;
};

string(float mode) FS_TASPlanName =
{
	if (mode == TAS_PLAN_MANUAL) return "manual";
	if (mode == TAS_PLAN_LEFT) return "left";
	if (mode == TAS_PLAN_RIGHT) return "right";
	if (mode == TAS_PLAN_GUIDE) return "guide";
	if (mode == TAS_PLAN_HOLD) return "hold";
	return "live";
};

float(float argc) FS_TASPlanRead =
{
	local float next;
	if (argc < 8 || argc > 12) return FALSE;
	fs_tasp_mode = FS_TASPlanMode(argv(2));
	if (fs_tasp_mode < 0) return FALSE;
	fs_tasp_amount = 1; fs_tasp_follow = 0;
	next = !strcmp(argv(1), "next");
	if (fs_tasp_mode >= TAS_PLAN_GUIDE)
	{
		if ((!next && argc != 10) || (next && argc != 11 && argc != 12)) return FALSE;
		if (!FS_TASNumber(argv(next ? 9 : 8))) return FALSE;
		fs_tasp_amount = fs_tas_number;
		if (fs_tasp_amount < 0 || fs_tasp_amount > 4) return FALSE;
		if (!FS_TASNumber(argv(next ? 10 : 9))) return FALSE;
		fs_tasp_follow = fs_tas_number;
		if (fs_tasp_follow != 0 && fs_tasp_follow != 1) return FALSE;
	}
	else if ((!next && argc != 8) || (next && argc != 9 && argc != 10)) return FALSE;
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
