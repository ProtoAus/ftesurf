// Human surf controller. Drafts never confer authority or mutate evidence.
#define TAS_TAB_CONTROLS 0
#define TAS_TAB_TIMELINE 1
#define TAS_TAB_SHARED 2
#define TAS_TAB_PROJECT 3
#define TAS_TAB_COUNT 4
float tasu_open, tasu_nextclick, tasu_frames, tasu_advanced, tasu_dirty;
var float tasu_mode = TAS_PLAN_HOLD;
float tasu_forward, tasu_side, tasu_pitch, tasu_yaw, tasu_bits;
var float tasu_count = 8, tasu_amount = 1, tasu_follow;
float tasu_tab;
var float tasu_head = -1, tasu_servermode = -1, tasu_serveramount = -1, tasu_serverfollow = -1;
vector tasu_servermove, tasu_serverangles;
float tasu_serverbits;
float tasu_camera_ready, tasu_camera_pitch, tasu_camera_time, tasu_camera_tick;
float tasu_camera_raw, tasu_camera_override;
vector tasu_camera_feet;
vector() HUD_Feet;
vector() HUD_LiveVel;
void() TASTimeline_Reset;
void(float first) TASTimeline_Request;
void() TASTimeline_Pump;
void(vector at, float width, float tsz, float hint, float row) TASTimeline_Draw;
void(vector at, float width, float tsz, float hint, float row) TASProject_Draw;
void() TASProject_SignPress;
void(vector at, float width, float tsz, float hint, float row) TASShare_Draw;
void(float offset, string sha) TASShare_Request;
float(float argc, float seat) TASShare_ConsoleCommand;

float(float tab) TASUI_UsesTimeline = { return (tab == TAS_TAB_TIMELINE || tab == TAS_TAB_PROJECT); };

void(float tab) TASUI_SelectTab =
{
	tasu_tab = bound(TAS_TAB_CONTROLS, floor(tab), TAS_TAB_PROJECT);
	if (TASUI_UsesTimeline(tasu_tab)) TASTimeline_Request(0);
	else if (tasu_tab == TAS_TAB_SHARED) TASShare_Request(0, "");
};

void() TASUI_FromView =
{
	local vector a;
	a = getproperty(VF_CL_VIEWANGLES);
	tasu_pitch = bound(-89, a_x, 89);
	tasu_yaw = a_y - 360 * floor((a_y + 180) / 360);
};

void() TASUI_FromServer =
{
	local float mode;
	mode = getstatf(STAT_FS_TASPLANMODE);
	tasu_mode = (mode == TAS_PLAN_GUIDE || mode == TAS_PLAN_LEFT || mode == TAS_PLAN_RIGHT) ? TAS_PLAN_GUIDE : TAS_PLAN_HOLD;
	tasu_forward = getstatf(STAT_FS_TASPLANFORWARD);
	tasu_side = getstatf(STAT_FS_TASPLANSIDE);
	tasu_bits = getstatf(STAT_FS_TASPLANBITS);
	tasu_amount = bound(0,getstatf(STAT_FS_TASPLANAMOUNT),4);
	if (getstatf(STAT_FS_TASPLANCAP) < TAS_GUIDE_CAP) tasu_amount = 1;
	tasu_follow = (getstatf(STAT_FS_TASPITCHFOLLOW) == 1);
	tasu_pitch = getstatf(STAT_FS_TASPLANPITCH);
	tasu_pitch = bound(-89, tasu_pitch - 360 * floor((tasu_pitch + 180) / 360), 89);
	tasu_yaw = getstatf(STAT_FS_TASPLANYAW);
	tasu_yaw = tasu_yaw - 360 * floor((tasu_yaw + 180) / 360);
	tasu_dirty = FALSE;
};

void() TASUI_Close =
{
	tasu_open = FALSE;
	TASTimeline_Reset();
	sui_reset_actions(); sui_tooltip_reset();
	UI_CursorRelease(UIC_TAS);
};

void() TASUI_Sync =
{
	local float head, mode, amount, follow, changed, bits;
	local vector moves, angles;
	if (numclientseats > 1 || !LT_StatsAreMine()) return;
	head = getstatf(STAT_FS_TIMERTICKS); mode = getstatf(STAT_FS_TASPLANMODE);
	amount = getstatf(STAT_FS_TASPLANAMOUNT); follow = getstatf(STAT_FS_TASPITCHFOLLOW);
	moves = [getstatf(STAT_FS_TASPLANFORWARD), getstatf(STAT_FS_TASPLANSIDE), 0];
	angles = [getstatf(STAT_FS_TASPLANPITCH), getstatf(STAT_FS_TASPLANYAW), 0];
	bits = getstatf(STAT_FS_TASPLANBITS);
	changed = (mode != tasu_servermode || amount != tasu_serveramount || follow != tasu_serverfollow ||
		moves != tasu_servermove || angles != tasu_serverangles || bits != tasu_serverbits);
	if (head != tasu_head)
	{
		tasu_dirty = FALSE;
		TASUI_FromServer();
	}
	else if (changed && !tasu_dirty) TASUI_FromServer();
	tasu_head = head; tasu_servermode = mode; tasu_serveramount = amount; tasu_serverfollow = follow;
	tasu_servermove = moves; tasu_serverangles = angles; tasu_serverbits = bits;
};

void(float seat) TASUI_Toggle =
{
	if (tasu_open) { TASUI_Close(); return; }
	if (seat || numclientseats > 1) { print("tas: workshop currently needs one local seat\n"); return; }
	if (!LT_StatsAreMine()) { print("tas: return to your own body before opening the workshop\n"); return; }
	if (UI_CursorHeld() || rec_sb_open) { print("tas: close the other panel first\n"); return; }
	TASUI_Sync();
	tasu_nextclick = tasu_frames = 0;
	tasu_open = TRUE; sui_reset_actions(); UI_CursorClaim(UIC_TAS);
	TASUI_SelectTab(tasu_tab);
};

void() TASUI_Mouse =
{
	if (!cvar_type("cl_tas_mouselock")) { print("tas: mouse lock needs the updated client engine\n"); return; }
	cvar_set("cl_tas_mouselock", cvar("cl_tas_mouselock") ? "0" : "1");
};

void(float count) TASUI_Send =
{
	local string line;
	if (cltime < tasu_nextclick) return;
	if (getstatf(STAT_FS_TASPLANCAP) < TAS_GUIDE_CAP) { print("tas: these controls need the updated native engine/server\n"); return; }
	if (getstatf(STAT_FS_TASPAUSE) != 1) { print("tas: press Pause first\n"); return; }
	if (getstatf(STAT_FS_TASPENDING) || getstatf(STAT_FS_TASREPLAY) == TAS_TAPE_ACTIVE || getstatf(STAT_FS_TASREPLAY) == TAS_TAPE_STAGING)
	{
		print("tas: wait for steps/replay, or Play to cancel\n"); return;
	}
	if (!tasu_advanced) TASUI_FromView();
	tasu_nextclick = cltime + .3;
	line = sprintf("tas %s %s %g %g %.13f %.13f %g", count ? "next" : "plan",
		FS_TASPlanName(tasu_mode), tasu_forward, tasu_side, tasu_pitch, tasu_yaw, tasu_bits);
	if (count) line = strcat(line,sprintf(" %g",count));
	line = strcat(line,sprintf(" %.6f %g\n",tasu_amount,tasu_follow));
	tasu_dirty = FALSE;
	localcmd(line);
};

void(float v) TASUI_Forward = { tasu_forward = rint(v); tasu_dirty = TRUE; };
void(float v) TASUI_Side = { tasu_side = rint(v); tasu_dirty = TRUE; };
void(float v) TASUI_Pitch = { tasu_pitch = v; tasu_dirty = TRUE; };
void(float v) TASUI_Yaw = { tasu_yaw = v; tasu_dirty = TRUE; };
void(float v) TASUI_Amount = { tasu_amount = bound(0,rint(v*1000)/1000,4); tasu_dirty = TRUE; };
void(float v) TASUI_Count = { tasu_count = bound(1,rint(v),TAS_TAPE_MAX); };
void(float bit) TASUI_Bit =
{
	if (tasu_bits & bit) tasu_bits = tasu_bits - bit;
	else tasu_bits = tasu_bits + bit;
	tasu_dirty = TRUE;
};

// Camera only: never write VF_CL_VIEWANGLES, input pitch, yaw or movement.
void() TASUI_Camera =
{
	local vector feet, velocity, angles, raw;
	local float horizontal, target, dt, tick;
	if (numclientseats > 1 || !LT_StatsAreMine() || rec_gh_on || rec_wt_on || rw_on)
	{
		tasu_camera_ready = FALSE; return;
	}
	TASUI_Sync();
	if (!tasu_follow || getstatf(STAT_FS_TASPITCHFOLLOW) != 1)
	{
		tasu_camera_ready = FALSE; return;
	}
	feet = HUD_Feet(); velocity = HUD_LiveVel(); raw = getproperty(VF_CL_VIEWANGLES);
	tick = getstatf(STAT_FS_TIMERTICKS);
	horizontal = vlen([velocity_x,velocity_y,0]);
	target = 0;
	if (horizontal > 1 || fabs(velocity_z) > 1)
		target = bound(-75,-atan2(velocity_z,horizontal)*57.295779513,75);
	dt = bound(0,cltime-tasu_camera_time,.1);
	if (!tasu_camera_ready || tick < tasu_camera_tick || vlen(feet-tasu_camera_feet) > 256 || cltime-tasu_camera_time > .3)
	{
		tasu_camera_pitch = raw_x; tasu_camera_override = 0;
		tasu_camera_raw = raw_x;
	}
	else if (fabs(raw_x-tasu_camera_raw) > .05)
	{
		tasu_camera_override = cltime+1;
		tasu_camera_pitch = raw_x;
		tasu_camera_raw = raw_x;
	}
	if (cltime < tasu_camera_override) target = raw_x;
	tasu_camera_pitch = tasu_camera_pitch + (target-tasu_camera_pitch)*(1-pow(.0003354626,dt));
	tasu_camera_time = cltime; tasu_camera_tick = tick; tasu_camera_feet = feet;
	tasu_camera_ready = TRUE;
	angles = getproperty(VF_ANGLES); angles_x = tasu_camera_pitch;
	setproperty(VF_ANGLES,angles);
};

void(vector scr) TASUI_Draw =
{
	local float sc, tsz, hint, row, pad, width, oldfont, i, paused, seat;
	local vector pos, size, at, chip, small;
	local string label;
	if (!tasu_open) return;
	seat = getproperty(VF_ACTIVESEAT);
	if (seat != 0) return;
	if (numclientseats > 1 || UI_CursorHeld() != UIC_TAS || rec_sb_open || !LT_StatsAreMine()) { TASUI_Close(); return; }
	tasu_frames = tasu_frames+1;
	sc = max(.5,ui_cv_scale);
	while (sc > .5 && (Font_Px(8*sc)*48 > scr_x-12 || Font_Px(8*sc)*(tasu_advanced?58:46) > scr_y-12)) sc = sc-.5;
	oldfont = drawfont; Font_Set(ui_font_ui);
	tsz = Font_Px(8*sc); hint = Font_Px(6*sc); row = ceil(tsz*1.8); pad = tsz;
	size = [min(scr_x-8,tsz*48),min(scr_y-8,tsz*(tasu_advanced?58:46)),0];
	pos = [scr_x-size_x-6,max(4,(scr_y-size_y)*.5),0]; width = size_x-pad*2;
	sui_begin(scr_x,scr_y); sui_style_panel(pos,size,ceil(pad*.75),.98);
	sui_text(pos+[pad,pad,0],[tsz*1.25,tsz*1.25],"Surf line editor",SUI_THEME_TEXT,1,0);
	if (Profile_Chip("tasu_close",pos+[size_x-pad-row,pad*.6,0],[row,row,0],"X",tsz,FALSE))
		{ TASUI_Close(); sui_end(); Font_Set(oldfont); return; }
	at = pos+[pad,tsz*3,0]; chip = [(width-18)/4,row,0];
	for (i=0;i<TAS_TAB_COUNT;i=i+1)
	{
		label = i == TAS_TAB_CONTROLS ? "Controls" : (i == TAS_TAB_TIMELINE ? "Timeline" : (i == TAS_TAB_SHARED ? "Shared" : "Project"));
		if (Profile_Chip(sprintf("tasu_tab%g",i),at+[i*(width+6)/4,0,0],chip,label,tsz,tasu_tab==i))
			TASUI_SelectTab(i);
	}
	if (TASUI_UsesTimeline(tasu_tab)) TASTimeline_Pump();
	at_y = at_y+row+hint; chip = [(width-12)/3,row,0];
	paused = (getstatf(STAT_FS_TASPAUSE) == 1);
	sui_text(at,[hint,hint],sprintf("%s | tick %.0f | queued %.0f | ASSISTED / PRACTICE",paused?"PAUSED":"PLAYING",getstatf(STAT_FS_TIMERTICKS),getstatf(STAT_FS_TASPENDING)),SUI_THEME_DIM,1,0);
	at_y = at_y+hint*1.7;
	if (Profile_Chip("tasu_pause",at,chip,"Pause",tsz,paused)) localcmd("tas pause\n");
	if (Profile_Chip("tasu_play",at+[(width+6)/3,0,0],chip,"Play",tsz,FALSE))
		{ localcmd("tas play\n"); TASUI_Close(); sui_end(); Font_Set(oldfont); return; }
	if (Profile_Chip("tasu_off",at+[(width+6)*2/3,0,0],chip,"Controls off",tsz,FALSE))
		{ localcmd("tas off\n"); TASUI_Close(); sui_end(); Font_Set(oldfont); return; }
	at_y = at_y+row+hint;
	if (tasu_tab != TAS_TAB_CONTROLS)
	{
		if (tasu_tab == TAS_TAB_SHARED) TASShare_Draw(at,width,tsz,hint,row);
		else if (tasu_tab == TAS_TAB_PROJECT) TASProject_Draw(at,width,tsz,hint,row);
		else TASTimeline_Draw(at,width,tsz,hint,row);
		sui_end(); Font_Set(oldfont); return;
	}
	sui_text(at,[hint,hint],"Choose movement. Nothing advances until you press Step.",SUI_THEME_DIM,1,0);
	at_y = at_y+hint*1.6;
	if (Profile_Chip("tasu_forward",at+[(width+6)/3,0,0],chip,"Forward",tsz,tasu_forward>0)) TASUI_Forward(tasu_forward > 0 ? 0 : 450);
	at_y = at_y+row+3;
	if (Profile_Chip("tasu_left",at,chip,"Left",tsz,tasu_side<0)) TASUI_Side(tasu_side < 0 ? 0 : -450);
	if (Profile_Chip("tasu_back",at+[(width+6)/3,0,0],chip,"Back",tsz,tasu_forward<0)) TASUI_Forward(tasu_forward < 0 ? 0 : -450);
	if (Profile_Chip("tasu_right",at+[(width+6)*2/3,0,0],chip,"Right",tsz,tasu_side>0)) TASUI_Side(tasu_side > 0 ? 0 : 450);
	at_y = at_y+row+hint;
	if (Profile_Chip("tasu_jump",at,chip,"Jump held",tsz,tasu_bits&1)) TASUI_Bit(1);
	if (Profile_Chip("tasu_duck",at+[(width+6)/3,0,0],chip,"Duck held",tsz,tasu_bits&2)) TASUI_Bit(2);
	if (Profile_Chip("tasu_clear",at+[(width+6)*2/3,0,0],chip,"Clear keys",tsz,FALSE))
		{ tasu_forward=tasu_side=tasu_bits=0; tasu_dirty=TRUE; }
	at_y = at_y+row+hint;
	if (Profile_Chip("tasu_auto",at,[width,row,0],tasu_mode == TAS_PLAN_GUIDE ? "Auto strafe ON - direction follows Left / Right" : "Auto strafe OFF - your movement and aim",tsz,tasu_mode == TAS_PLAN_GUIDE))
		{ tasu_mode = tasu_mode == TAS_PLAN_GUIDE ? TAS_PLAN_HOLD : TAS_PLAN_GUIDE; tasu_dirty=TRUE; }
	at_y = at_y+row+hint;
	WPU_Slider("tasu_amount","Turn amount",at,width,tasu_amount,'0 4 4000',TASUI_Amount,tsz);
	at_y = at_y+tsz*2.2; small=[(width-24)/5,row,0];
	if (Profile_Chip("tasu_coarseminus",at,small,"-0.10",hint,FALSE)) TASUI_Amount(tasu_amount-.1);
	if (Profile_Chip("tasu_fineminus",at+[(width+6)/5,0,0],small,"-0.01",hint,FALSE)) TASUI_Amount(tasu_amount-.01);
	if (Profile_Chip("tasu_reference",at+[(width+6)*2/5,0,0],small,"1.00x",hint,FALSE)) TASUI_Amount(1);
	if (Profile_Chip("tasu_fineplus",at+[(width+6)*3/5,0,0],small,"+0.01",hint,FALSE)) TASUI_Amount(tasu_amount+.01);
	if (Profile_Chip("tasu_coarseplus",at+[(width+6)*4/5,0,0],small,"+0.10",hint,FALSE)) TASUI_Amount(tasu_amount+.1);
	at_y = at_y+row+hint;
	sui_text(at,[hint,hint],"Gentler < 1.00 gain reference > sharper; not a route solver.",SUI_THEME_MUTED,1,0);
	at_y = at_y+hint*1.7;
	if (Profile_Chip("tasu_follow",at,[width,row,0],tasu_follow?"Vertical look: Follow travel (view only)":"Vertical look: Manual",tsz,tasu_follow))
		{ tasu_follow=!tasu_follow; tasu_dirty=TRUE; TASUI_Send(0); }
	at_y = at_y+row+hint;
	WPU_Slider("tasu_count","Step ticks",at,width,tasu_count,'1 128 127',TASUI_Count,tsz);
	at_y = at_y+tsz*2.2; small=[(width-18)/4,row,0];
	if (Profile_Chip("tasu_backone",at,small,"Back 1",tsz,FALSE)) localcmd("tas back 1\n");
	if (Profile_Chip("tasu_one",at+[(width+6)/4,0,0],small,"Step 1",tsz,FALSE)) TASUI_Send(1);
	if (Profile_Chip("tasu_many",at+[(width+6)/2,0,0],small,sprintf("Step %g",tasu_count),tsz,FALSE)) TASUI_Send(tasu_count);
	if (Profile_Chip("tasu_apply",at+[(width+6)*3/4,0,0],small,"Apply only",hint,FALSE)) TASUI_Send(0);
	at_y = at_y+row+hint;
	label = "Manual / preset: air, ground or transition model not applied";
	if (getstatf(STAT_FS_TASPLANAIR)==1) label="Last step: air gain guide (movement keys preserved)";
	if (getstatf(STAT_FS_TASPLANAIR)==2) label="Last step: ground gain guide (actual crouch crop)";
	if (getstatf(STAT_FS_TASPLANCAP)<TAS_GUIDE_CAP) label="Update the native server for these controls.";
	sui_text(at,[hint,hint],label,SUI_THEME_DIM,1,0); at_y=at_y+hint*1.7;
	if (Profile_Chip("tasu_advanced",at,[width,row,0],tasu_advanced?"Hide advanced":"Advanced: exact aim, analog input, mouse",hint,tasu_advanced)) tasu_advanced=!tasu_advanced;
	at_y=at_y+row+hint;
	if (tasu_advanced)
	{
		WPU_Slider("tasu_fraw","Forward",at,width,tasu_forward,'-450 450 900',TASUI_Forward,tsz); at_y=at_y+tsz*2.1;
		WPU_Slider("tasu_sraw","Side",at,width,tasu_side,'-450 450 900',TASUI_Side,tsz); at_y=at_y+tsz*2.1;
		WPU_Slider("tasu_pitch","Input pitch",at,width,tasu_pitch,'-89 89 1780',TASUI_Pitch,tsz); at_y=at_y+tsz*2.1;
		WPU_Slider("tasu_yaw","Input yaw",at,width,tasu_yaw,'-180 180 3600',TASUI_Yaw,tsz); at_y=at_y+tsz*2.1;
		if (Profile_Chip("tasu_view",at,chip,"Use view",hint,FALSE)) { TASUI_FromView(); tasu_dirty=TRUE; }
		if (Profile_Chip("tasu_server",at+[(width+6)/3,0,0],chip,"Use server",hint,FALSE)) TASUI_FromServer();
		if (Profile_Chip("tasu_mouse",at+[(width+6)*2/3,0,0],chip,cvar("cl_tas_mouselock")?"Mouse locked":"Mouse free",hint,cvar("cl_tas_mouselock"))) TASUI_Mouse();
	}
	sui_end(); Font_Set(oldfont);
};

float(float evtype, float scanx, float chary, float devid) TASUI_Input =
{
	if (!tasu_open) return FALSE;
	if (evtype==IE_KEYDOWN && scanx==K_ESCAPE) { TASUI_Close(); return TRUE; }
	if (evtype==IE_MOUSEABS) { sui_input_event(evtype,scanx,chary,devid); return TRUE; }
	if (scanx==K_MOUSE1 || scanx==K_MOUSE2)
	{
		if (evtype==IE_KEYDOWN) _sui_mouse_move(_cursor_position,FALSE);
		if (evtype==IE_KEYDOWN && scanx==K_MOUSE1 && tasu_tab==TAS_TAB_PROJECT && sui_is_hovered("tasp_sign")) TASProject_SignPress();
		sui_input_event(evtype,scanx,chary,devid); return TRUE;
	}
	return FALSE;
};
