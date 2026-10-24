/* Local mounted-knife presentation/editor. No inventory, networking or paint-kit
 * equivalence: the finish is an explicitly local shader preview. */
float wpu_open, wpu_frames, wpu_skinstate, wpu_painted;
entity wpu_arms;
float wpu_source, wpu_srcskel, wpu_srcabs, wpu_armcount;
int *wpu_armmap;

void() WPU_SourcePose =
{
	if (wpu_source != wp_ent.modelindex)
	{
		if (wpu_srcskel) skel_delete(wpu_srcskel);
		if (wpu_srcabs) skel_delete(wpu_srcabs);
		if (wpu_armmap) { memfree((void*)wpu_armmap); wpu_armmap = __NULL__; }
		wpu_source = wp_ent.modelindex;
		wpu_srcskel = skel_create(wp_ent.modelindex);
		wpu_srcabs = skel_create(wp_ent.modelindex, TRUE);
	}
	// Sample animation, not our previously attached pose. Native conversion is
	// the same model-space contract used for the separate merged arms.
	wp_ent.skeletonindex = 0;
	skel_build(wpu_srcskel, wp_ent, wp_ent.modelindex, 0, 0, 0, 1);
	skel_copybones(wpu_srcabs, wpu_srcskel, 0, 0);
	wp_ent.skeletonindex = wpu_srcabs;
};

void() WPU_Arms =
{
	local float i, sourcebone, skeleton;
	local string name;
	local vector org, forward, right, up;
	forward = v_forward; right = v_right; up = v_up;
	if (!wpu_armmap)
	{
		if (!wpu_arms)
		{
			wpu_arms = spawn();
			precache_model("models/weapons/ct_arms.mdl");
			setmodel(wpu_arms, "models/weapons/ct_arms.mdl");
			wpu_arms.frame = 0; wpu_arms.lerpfrac = 0; wpu_arms.scale = 1;
			if (wpu_arms.modelindex)
			{
				// Weapon forearms are roots; arms have upper-arm parents. Merge
				// ABSOLUTE model-space poses, not incompatible relative poses.
				skeleton = skel_create(wpu_arms.modelindex, TRUE);
				wpu_armcount = bound(0, skel_get_numbones(skeleton), 256);
				for (i = 1; i <= wpu_armcount; i = i + 1)
				{
					org = gettaginfo(wpu_arms, i);
					skel_set_bone(skeleton, i, org, v_forward, v_right, v_up);
				}
				wpu_arms.skeletonindex = skeleton;
			}
		}
		wpu_armcount = bound(0, skel_get_numbones(wpu_arms.skeletonindex), 256);
		wpu_armmap = (int*)memalloc(((int)wpu_armcount + 1i) * 4i);
		for (i = 1; i <= wpu_armcount; i = i + 1)
		{
			name = skel_get_bonename(wpu_arms.skeletonindex, i);
			wpu_armmap[(int)i] = (int)skel_find_bone(wpu_srcabs, name);
		}
	}
	if (!wpu_srcabs || !wpu_arms.skeletonindex)
	{
		v_forward = forward; v_right = right; v_up = up;
		return;
	}
	for (i = 1; i <= wpu_armcount; i = i + 1)
	{
		sourcebone = (float)wpu_armmap[(int)i];
		if (sourcebone <= 0) continue;
		org = skel_get_boneabs(wpu_srcabs, sourcebone);
		skel_set_bone(wpu_arms.skeletonindex, i, org, v_forward, v_right, v_up);
	}
	v_forward = forward; v_right = right; v_up = up;
	setorigin(wpu_arms, wp_ent.origin);
	wpu_arms.angles = wp_ent.angles;
	wpu_arms.renderflags = wp_ent.renderflags;
	wpu_arms.effects = wp_ent.effects;
	addentity(wpu_arms);
};

void() WPU_Apply =
{
	local float kind, style, key, shader;
	local string model, pattern, name, data;
	kind = bound(0, floor(cvar("cl_knife_model")), 2);
	style = bound(0, floor(cvar("cl_knife_finish")), 3);
	if (wp_weapon == FS_WEAPON_KNIFE && kind > 0)
	{
		WPU_SourcePose();
		if (cvar("cl_knife_arms")) WPU_Arms();
	}
	else wp_ent.skeletonindex = 0;
	key = wp_ent.modelindex * 16 + kind * 4 + style;
	if (key == wpu_skinstate)
	{
		if (kind <= 0 || style <= 0 || wp_ent.forceshader) return;
	}
	wpu_skinstate = key;
	if (wp_weapon != FS_WEAPON_KNIFE || kind == 0 || style == 0)
	{
		wp_ent.forceshader = 0;
		wpu_painted = FALSE;
		return;
	}
	model = (kind == 1) ? "knife_butterfly" : "knife_m9_bay";
	pattern = "anodized_air/fade";
	if (style == 2) pattern = "hydrographic/webs";
	if (style == 3) pattern = "hydrographic/marbleized";
	name = sprintf("ftesurf/knife_%g_%g", kind, style);
	data = sprintf("{\nprogram knife_finish#STYLE=%g\n{ map materials/models/weapons/v_models/%s/%s.vtf }\n{ map materials/models/weapons/customization/paints/%s.vtf }\n{ map materials/models/weapons/customization/%s/%s_masks.vtf }\n}\n",
		style, model, model, pattern, model, model);
	shader = shaderforname(name, data);
	if (shader <= 0) return;
	// These MDLs have one material; force only this knife's shader, not the hands.
	wp_ent.forceshader = shader;
	wpu_painted = TRUE;
};

void() WPU_Close =
{
	wpu_open = FALSE;
	UI_CursorRelease(UIC_WEAPON);
	sui_reset_actions();
	sui_tooltip_reset();
};

void() WPU_Open =
{
	if (UI_CursorHeld() || rec_sb_open)
	{
		print("knife_menu: close the other panel first\n");
		return;
	}
	wpu_open = TRUE;
	sui_reset_actions();
	UI_CursorClaim(UIC_WEAPON);
};

float(string id, string label, vector pos, vector size, float selected, float sc) WPU_Button =
{
	local vector colour, glyph;
	sui_action_element(pos, size, id, sui_noop);
	colour = selected ? SUI_THEME_SELECTED : SUI_THEME_CHIP;
	if (sui_is_hovered(id)) colour = SUI_THEME_HOVER;
	if (sui_is_held(id)) colour = SUI_THEME_PRESSED;
	sui_style_box(pos, size, 3 * sc, colour, selected ? SUI_THEME_ACCENT : SUI_THEME_EDGE, 1);
	glyph = sui_native_text_size(8 * sc);
	sui_native_text(pos + [8 * sc, (size_y - glyph_y) * 0.5, 0], label, 8 * sc, SUI_THEME_TEXT, 1);
	return sui_is_released(id);
};

void(float value) WPU_Seed = { cvar_set("cl_knife_seed", ftos(floor(value))); };
void(float value) WPU_Scale = { cvar_set("cl_knife_scale", ftos(value)); };
void(float value) WPU_Rotation = { cvar_set("cl_knife_rotation", ftos(value)); };
void(float value) WPU_Fade = { cvar_set("cl_knife_fade", ftos(value / 100)); };
void(float value) WPU_Wear = { cvar_set("cl_knife_wear", ftos(value)); };

void(string id, string label, vector pos, float width, float value, vector range, void(float) action, float sc) WPU_Slider =
{
	local vector track;
	local float fraction;
	sui_native_text(pos, label, 8 * sc, SUI_THEME_DIM, 1);
	sui_native_text(pos + [width - 56 * sc, 0, 0], sprintf("%g", value), 8 * sc, SUI_THEME_TEXT, 1);
	track = pos + [100 * sc, 2 * sc, 0];
	width = width - 165 * sc;
	fraction = bound(0, (value - range_x) / (range_y - range_x), 1);
	sui_roundbox(track + [0, 5 * sc, 0], [width, 3 * sc, 0], sc, SUI_THEME_WELL, 1);
	sui_roundbox(track + [fraction * width - 3 * sc, 1 * sc, 0], [6 * sc, 11 * sc, 0], 2 * sc, SUI_THEME_ACCENT, 1);
	sui_slidercontrol(id, track - [0, 4 * sc, 0], [width, 22 * sc, 0], range, value, action);
};

void(vector scr) WPU_Draw =
{
	local float sc, width, y, kind, style, oldfont;
	local vector pos, size;
	if (!wpu_open) return;
	if (UI_CursorHeld() != UIC_WEAPON || rec_sb_open) { WPU_Close(); return; }
	wpu_frames = wpu_frames + 1;
	sc = bound(0.65, ui_cv_scale * 0.5, min(1.2, min(scr_x / 420, scr_y / 440)));
	width = 388 * sc;
	pos = [20 * sc, max(16 * sc, (scr_y - 405 * sc) * 0.5), 0];
	size = [width, 405 * sc, 0];
	oldfont = drawfont;
	Font_Set(ui_font_ui);
	sui_begin(scr_x, scr_y);
	sui_style_box(pos, size, 7 * sc, SUI_THEME_PANEL, SUI_THEME_EDGE_HI, 1);
	sui_native_text(pos + [14 * sc, 12 * sc, 0], "Knife workshop", 11 * sc, SUI_THEME_TEXT, 1);
	if (WPU_Button("wpu_close", "X", pos + [width - 40 * sc, 8 * sc, 0], [28 * sc, 24 * sc, 0], FALSE, sc)) WPU_Close();
	pos = pos + [14 * sc, 48 * sc, 0];
	width = width - 28 * sc;
	kind = cvar("cl_knife_model"); style = cvar("cl_knife_finish");
	if (WPU_Button("wpu_css", "CSS", pos, [90 * sc, 28 * sc, 0], kind == 0, sc)) WP_ChooseKnife(0);
	if (WPU_Button("wpu_butterfly", "Butterfly", pos + [96 * sc, 0, 0], [132 * sc, 28 * sc, 0], kind == 1, sc)) WP_ChooseKnife(1);
	if (WPU_Button("wpu_m9", "M9", pos + [234 * sc, 0, 0], [126 * sc, 28 * sc, 0], kind == 2, sc)) WP_ChooseKnife(2);
	y = 40 * sc;
	if (WPU_Button("wpu_original", "Original", pos + [0, y, 0], [90 * sc, 28 * sc, 0], style == 0, sc)) cvar_set("cl_knife_finish", "0");
	if (WPU_Button("wpu_fade", "Fade", pos + [96 * sc, y, 0], [84 * sc, 28 * sc, 0], style == 1, sc)) cvar_set("cl_knife_finish", "1");
	if (WPU_Button("wpu_web", "Web", pos + [186 * sc, y, 0], [78 * sc, 28 * sc, 0], style == 2, sc)) cvar_set("cl_knife_finish", "2");
	if (WPU_Button("wpu_marble", "Marble", pos + [270 * sc, y, 0], [90 * sc, 28 * sc, 0], style == 3, sc)) cvar_set("cl_knife_finish", "3");
	WPU_Slider("wpu_seed", "Pattern seed", pos + [0, 84 * sc, 0], width, floor(cvar("cl_knife_seed")), '0 1000 1000', WPU_Seed, sc);
	WPU_Slider("wpu_scale", "Scale", pos + [0, 118 * sc, 0], width, cvar("cl_knife_scale"), '0.25 4 75', WPU_Scale, sc);
	WPU_Slider("wpu_rotation", "Rotation", pos + [0, 152 * sc, 0], width, cvar("cl_knife_rotation"), '0 360 360', WPU_Rotation, sc);
	WPU_Slider("wpu_fade_amount", "Fade %", pos + [0, 186 * sc, 0], width, cvar("cl_knife_fade") * 100, '0 100 100', WPU_Fade, sc);
	WPU_Slider("wpu_wear", "Wear", pos + [0, 220 * sc, 0], width, cvar("cl_knife_wear"), '0 1 100', WPU_Wear, sc);
	if (WPU_Button("wpu_inspect", "Inspect", pos + [0, 258 * sc, 0], [110 * sc, 28 * sc, 0], FALSE, sc)) WP_Inspect();
	if (WPU_Button("wpu_random", "Random seed", pos + [116 * sc, 258 * sc, 0], [130 * sc, 28 * sc, 0], FALSE, sc)) WPU_Seed(floor(random() * 1001));
	if (WPU_Button("wpu_drop", "Drop", pos + [252 * sc, 258 * sc, 0], [108 * sc, 28 * sc, 0], FALSE, sc)) localcmd("cmd drop\n");
	sui_native_text(pos + [0, 302 * sc, 0], "Local preview - not exact CS paint kits or inventory.", 6 * sc, SUI_THEME_MUTED, 1);
	sui_native_text(pos + [0, 320 * sc, 0], "Butterfly/M9 need installed CS:GO Legacy content.", 6 * sc, SUI_THEME_MUTED, 1);
	sui_native_text(pos + [0, 338 * sc, 0], "Mount once: fs_load \"steam:Counter-Strike Global Offensive/csgo\"", 6 * sc, SUI_THEME_MUTED, 1);
	sui_end();
	Font_Set(oldfont);
};

float(float evtype, float scanx, float chary, float devid) WPU_Input =
{
	if (!wpu_open) return FALSE;
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE) { WPU_Close(); return TRUE; }
	if (evtype == IE_MOUSEABS || scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN) _sui_mouse_move(_cursor_position, FALSE);
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	return FALSE;
};

float() WPU_Command =
{
	if (strcmp(argv(0), "knife_menu")) return FALSE;
	if (!strcmp(argv(1), "status"))
	{
		print(sprintf("knife_menu: open %g claims %g frames %g kind %g finish %g painted %g\n", wpu_open, UI_CursorHeld(), wpu_frames, cvar("cl_knife_model"), cvar("cl_knife_finish"), wpu_painted));
		return TRUE;
	}
	if (!strcmp(argv(1), "close")) WPU_Close();
	else if (!strcmp(argv(1), "open")) { if (!wpu_open) WPU_Open(); }
	else if (wpu_open) WPU_Close();
	else WPU_Open();
	return TRUE;
};

void() WPU_Register =
{
	wpu_skinstate = -1;
	registercommand("knife_menu");
	registercvar("cl_knife_arms", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_finish", "0", CVAR_ARCHIVE);
	registercvar("cl_knife_seed", "0", CVAR_ARCHIVE);
	registercvar("cl_knife_scale", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_rotation", "0", CVAR_ARCHIVE);
	registercvar("cl_knife_fade", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_wear", "0", CVAR_ARCHIVE);
};
