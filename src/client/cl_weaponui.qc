/* Local mounted-knife presentation/editor. No inventory or paint-kit equivalence. */
float wpu_open, wpu_frames, wpu_skinstate, wpu_painted;
entity wpu_parts[2];
float wpu_rows[2], wpu_counts[2], wpu_sources[2];
float wpu_source, wpu_srcskel, wpu_srcabs;
int *wpu_armmap;
int *wpu_layermap;
float wpu_drag, wpu_mx, wpu_my, wpu_drop, wpu_tsz, wpu_page;
vector wpu_pos, wpu_size, wpu_offset, wpu_popup_pos, wpu_popup_size;

void() WPU_SourcePose =
{
	if (wpu_source != wp_ent.modelindex)
	{
		if (wpu_srcskel) skel_delete(wpu_srcskel);
		if (wpu_srcabs) skel_delete(wpu_srcabs);
		wpu_source = wp_ent.modelindex;
		wpu_srcskel = skel_create(wp_ent.modelindex);
		wpu_srcabs = skel_create(wp_ent.modelindex, TRUE);
	}
	wp_ent.skeletonindex = 0;
	skel_build(wpu_srcskel, wp_ent, wp_ent.modelindex, 0, 0, 0, 1);
	skel_copybones(wpu_srcabs, wpu_srcskel, 0, 0);
	wp_ent.skeletonindex = wpu_srcabs;
};

void(float slot, float row) WPU_Part =
{
	local entity part;
	local float i, sourcebone, skeleton;
	local int *mapping;
	local string name, rules;
	local vector org, forward, right, up;
	if (row < (float)KCAT_ARMS || !KCAT_Available(row)) return;
	forward = v_forward; right = v_right; up = v_up;
	part = wpu_parts[(int)slot];
	if (!part) { part = spawn(); wpu_parts[(int)slot] = part; }
	if (slot == 0) mapping = wpu_armmap;
	else mapping = wpu_layermap;
	if (!mapping || row != wpu_rows[(int)slot] || wpu_sources[(int)slot] != wpu_source)
	{
		if (part.skeletonindex) skel_delete(part.skeletonindex);
		part.skeletonindex = 0;
		if (mapping) memfree((void*)mapping);
		name = KCAT_Get(row, KCAT_MODEL);
		precache_model(name); setmodel(part, name);
		part.frame = 0; part.lerpfrac = 0; part.scale = 1;
		// Upper-arm parents differ: merge absolute model-space poses.
		skeleton = skel_create(part.modelindex, TRUE);
		wpu_counts[(int)slot] = bound(0, skel_get_numbones(skeleton), 256);
		for (i = 1; i <= wpu_counts[(int)slot]; i = i + 1)
		{
			org = gettaginfo(part, i);
			skel_set_bone(skeleton, i, org, v_forward, v_right, v_up);
		}
		part.skeletonindex = skeleton;
		mapping = (int*)memalloc(((int)wpu_counts[(int)slot] + 1i) * 4i);
		for (i = 1; i <= wpu_counts[(int)slot]; i = i + 1)
			mapping[(int)i] = (int)skel_find_bone(wpu_srcabs, skel_get_bonename(skeleton, i));
		rules = KCAT_SkinRules(row);
		setcustomskin(part, "", rules);
		if (strcmp(rules, "")) strunzone(rules);
		wpu_rows[(int)slot] = row; wpu_sources[(int)slot] = wpu_source;
		if (slot == 0) wpu_armmap = mapping;
		else wpu_layermap = mapping;
	}
	for (i = 1; i <= wpu_counts[(int)slot]; i = i + 1)
	{
		sourcebone = (float)mapping[(int)i];
		if (sourcebone <= 0) continue;
		org = skel_get_boneabs(wpu_srcabs, sourcebone);
		skel_set_bone(part.skeletonindex, i, org, v_forward, v_right, v_up);
	}
	v_forward = forward; v_right = right; v_up = up;
	setorigin(part, wp_ent.origin); part.angles = wp_ent.angles;
	part.renderflags = wp_ent.renderflags; part.effects = wp_ent.effects;
	addentity(part);
};

void() WPU_Apply =
{
	local float kind, style, key, isolated;
	local string pattern, name, data, rules, base, program;
	kind = KCAT_Knife();
	style = bound(0, floor(VM_Cvar("cl_knife_finish")), 3);
	base = KCAT_Get(kind, KCAT_BASE);
	isolated = FALSE;
	if (!strcmp(base, "materials/models/weapons/v_models/knife_t/knife_t.vtf"))
		if (cvar_type("fs_knife_texture"))
			if (cvar("fs_knife_texture") > 0)
			{
				base = "materials/ftesurf/knife_legacy_t.vtf";
				isolated = TRUE;
			}
	if (wp_weapon == FS_WEAPON_KNIFE && kind > 0)
	{
		WPU_SourcePose();
		if (VM_Cvar("cl_knife_arms"))
		{
			WPU_Part(0, KCAT_Hands());
			if (KCAT_ActiveLayer() >= (float)KCAT_LAYERS) WPU_Part(1, KCAT_ActiveLayer());
		}
	}
	else wp_ent.skeletonindex = 0;
	key = wp_ent.modelindex * 512 + kind * 4 + style + isolated * 256 + VM_IsMirroring() * 128;
	if (key == wpu_skinstate) return;
	wpu_skinstate = key;
	wp_ent.forceshader = 0;
	wpu_painted = FALSE;
	if (wp_weapon != FS_WEAPON_KNIFE || kind == 0)
	{
		setcustomskin(wp_ent, "", "");
		return;
	}
	name = "";
	if (style > 0 && strcmp(KCAT_Get(kind, KCAT_MASK), ""))
	{
		pattern = "anodized_air/fade";
		if (style == 2) pattern = "hydrographic/webs";
		if (style == 3) pattern = "hydrographic/marbleized";
		name = sprintf("ftesurf/knife_%g_%g", kind, style);
		if (isolated) name = strcat(name, "_legacy");
		program = sprintf("knife_finish#STYLE=%g#FAMILY=%s", style, KCAT_Get(kind, KCAT_FAMILY));
		if (VM_IsMirroring())
		{
			name = strcat(name, "_watched");
			program = strcat(program, "#WATCHED");
		}
		data = sprintf("{\nprogram %s\n{ map %s }\n{ map materials/models/weapons/customization/paints/%s.vtf }\n{ map %s }\n}\n", program, base, pattern, KCAT_Get(kind, KCAT_MASK));
		wpu_painted = (shaderforname(name, data) > 0);
	}
	else if (isolated)
	{
		name = sprintf("ftesurf/knife_%g_original_legacy", kind);
		data = sprintf("{\nprogram defaultskin\n{ map %s }\n}\n", base);
		wpu_painted = (shaderforname(name, data) > 0);
	}
	data = KCAT_Rules(KCAT_Get(kind, KCAT_HIDE), "knife_hidden");
	rules = "";
	if (wpu_painted) rules = KCAT_Rules(KCAT_Get(kind, KCAT_PAINT), name);
	setcustomskin(wp_ent, "", strcat(data, rules));
	if (strcmp(data, "")) strunzone(data);
	if (strcmp(rules, "")) strunzone(rules);
};

void() WPU_Close =
{
	wpu_open = wpu_drag = wpu_drop = FALSE;
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
	wpu_drag = wpu_drop = FALSE;
	sui_reset_actions();
	UI_CursorClaim(UIC_WEAPON);
};

void(float value) WPU_Seed = { cvar_set("cl_knife_seed", ftos(floor(value))); };
void(float value) WPU_Scale = { cvar_set("cl_knife_scale", ftos(value)); };
void(float value) WPU_Rotation = { cvar_set("cl_knife_rotation", ftos(value)); };
void(float value) WPU_Fade = { cvar_set("cl_knife_fade", ftos(value / 100)); };
void(float value) WPU_Wear = { cvar_set("cl_knife_wear", ftos(value)); };

void(string id, string label, vector pos, float width, float value, vector range, void(float) action, float tsz) WPU_Slider =
{
	local float lw, tw, fraction, h, x;
	local vector track;
	lw = tsz * 7; h = ceil(tsz * 1.8);
	tw = width - lw - tsz * 3;
	sui_text(pos + [0, (h - tsz) * 0.5, 0], [tsz, tsz], label, SUI_THEME_DIM, 1, 0);
	sui_text(pos + [width - tsz * 2.8, (h - tsz) * 0.5, 0], [tsz, tsz], sprintf("%g", value), SUI_THEME_TEXT, 1, 0);
	track = pos + [lw, floor(h * 0.5) - 2, 0];
	fraction = bound(0, (value - range_x) / (range_y - range_x), 1);
	sui_roundbox(track, [tw, 4, 0], 2, SUI_THEME_WELL, 1);
	x = floor(tw * fraction);
	if (x > 0) sui_roundbox(track, [x, 4, 0], 2, SUI_THEME_EDGE_HI, 1);
	sui_roundbox(track + [x - 3, -3, 0], '6 10 0', 2, SUI_THEME_ACCENT, 1);
	sui_slidercontrol(id, pos + [lw, 0, 0], [tw, h, 0], range, value, action);
};

float(float list) WPU_ListCount =
{
	if (list == 1) return kcat_knives;
	if (list == 2) return kcat_hands + 1;
	return kcat_layers;
};

float(float list, float index) WPU_ListRow =
{
	if (list == 1) return index;
	if (list == 2) return (index < kcat_hands) ? (float)KCAT_ARMS + index : -1;
	return (float)KCAT_LAYERS + index;
};

string(float row) WPU_OptionLabel =
{
	if (row == -1) return "Hidden";
	return KCAT_Get(row, KCAT_NAME);
};

float(string id, vector pos, vector size, string label, float tsz, float selected) WPU_ChoiceChip =
{
	local float measured;
	measured = stringwidth(label, TRUE, [tsz, tsz]);
	if (measured > size_x - 12) tsz = tsz * (size_x - 12) / measured;
	return Profile_Chip(id, pos, size, label, tsz, selected);
};

void(vector scr) WPU_Draw =
{
	local float sc, tsz, ttl, hint, pad, row, width, kind, arms, style, oldfont, i, selected, count, option, start;
	local vector pos, size, at, box, pop;
	local string text;
	if (!wpu_open) return;
	if (UI_CursorHeld() != UIC_WEAPON || rec_sb_open) { WPU_Close(); return; }
	wpu_frames = wpu_frames + 1;
	pop = '0 0 0';
	sc = max(0.5, ui_cv_scale);
	while (sc > 0.5 && (Font_Px(8 * sc) * 38 > scr_x - 12 || Font_Px(8 * sc) * 36 > scr_y - 12)) sc = sc - 0.5;
	oldfont = drawfont;
	Font_Set(ui_font_ui);
	tsz = Font_Px(8 * sc); ttl = Font_Px(10 * sc); hint = Font_Px(6 * sc);
	wpu_tsz = tsz;
	pad = tsz; row = ceil(tsz * 1.8);
	size = [min(scr_x - 8, tsz * 38), min(scr_y - 8, tsz * 41), 0];
	pos = [cvar("hud_knife_x") * scr_x, cvar("hud_knife_y") * scr_y, 0];
	if (wpu_drag) pos = [wpu_mx, wpu_my, 0] - wpu_offset;
	pos_x = bound(4, pos_x, max(4, scr_x - size_x - 4));
	pos_y = bound(4, pos_y, max(4, scr_y - size_y - 4));
	if (wpu_drag)
	{
		cvar_set("hud_knife_x", ftos(pos_x / scr_x));
		cvar_set("hud_knife_y", ftos(pos_y / scr_y));
	}
	wpu_pos = pos; wpu_size = size;
	sui_begin(scr_x, scr_y);
	sui_style_panel(pos, size, ceil(pad * 0.75), 0.98);
	sui_text(pos + [pad, pad, 0], [ttl, ttl], "Knife workshop", SUI_THEME_TEXT, 1, 0);
	if (Profile_Chip("wpu_close", pos + [size_x - pad - row, pad * 0.65, 0], [row, row, 0], "X", tsz, FALSE))
	{
		WPU_Close(); sui_end(); Font_Set(oldfont); return;
	}
	sui_tooltip_for("wpu_close", "Close (Esc). Drag the title bar to move this window.", sc);
	at = pos + [pad, tsz * 4, 0];
	width = size_x - pad * 2;
	kind = KCAT_LocalKnife();
	arms = cvar("cl_knife_arms") ? KCAT_LocalHands() : -1;
	style = bound(0, floor(cvar("cl_knife_finish")), 3);
	sui_text(at + [0, (row - tsz) * 0.5, 0], [tsz, tsz], "Knife", SUI_THEME_DIM, 1, 0);
	box = [width - tsz * 7, row, 0];
	if (WPU_ChoiceChip("wpu_knife", at + [tsz * 7, 0, 0], box, strcat(WPU_OptionLabel(kind), "  v"), tsz, wpu_drop == 1))
		{ wpu_drop = (wpu_drop == 1) ? 0 : 1; wpu_page = 0; }
	if (wpu_drop == 1) pop = at + [tsz * 7, row + 4, 0];
	at_y = at_y + tsz * 2.7;
	sui_text(at + [0, (row - tsz) * 0.5, 0], [tsz, tsz], "Hands", SUI_THEME_DIM, 1, 0);
	if (WPU_ChoiceChip("wpu_arms", at + [tsz * 7, 0, 0], box, strcat(WPU_OptionLabel(arms), "  v"), tsz, wpu_drop == 2))
		{ wpu_drop = (wpu_drop == 2) ? 0 : 2; wpu_page = 0; }
	if (wpu_drop == 2) pop = at + [tsz * 7, row + 4, 0];
	at_y = at_y + tsz * 2.7;
	sui_text(at + [0, (row - tsz) * 0.5, 0], [tsz, tsz], "Sleeves", SUI_THEME_DIM, 1, 0);
	if (WPU_ChoiceChip("wpu_sleeves", at + [tsz * 7, 0, 0], box, strcat(WPU_OptionLabel(KCAT_LocalLayer()), "  v"), tsz, wpu_drop == 3))
		{ wpu_drop = (wpu_drop == 3) ? 0 : 3; wpu_page = 0; }
	if (wpu_drop == 3) pop = at + [tsz * 7, row + 4, 0];
	at_y = at_y + tsz * 3.1;
	for (i = 0; i < 4; i = i + 1)
	{
		text = "Original";
		if (i == 1) text = "Fade";
		if (i == 2) text = "Web";
		if (i == 3) text = "Marble";
		if (Profile_Chip(sprintf("wpu_finish%g", i), at + [i * (width + 6) / 4, 0, 0], [(width - 18) / 4, row, 0], text, tsz, style == i))
			cvar_set("cl_knife_finish", ftos(i));
	}
	at_y = at_y + tsz * 2.5;
	WPU_Slider("wpu_seed", "Pattern seed", at, width, floor(cvar("cl_knife_seed")), '0 1000 1000', WPU_Seed, tsz);
	at_y = at_y + tsz * 2.1;
	WPU_Slider("wpu_scale", "Scale", at, width, cvar("cl_knife_scale"), '0.25 4 75', WPU_Scale, tsz);
	at_y = at_y + tsz * 2.1;
	WPU_Slider("wpu_rotation", "Rotation", at, width, cvar("cl_knife_rotation"), '0 360 360', WPU_Rotation, tsz);
	at_y = at_y + tsz * 2.1;
	WPU_Slider("wpu_fade_amount", "Fade %", at, width, cvar("cl_knife_fade") * 100, '0 100 100', WPU_Fade, tsz);
	at_y = at_y + tsz * 2.1;
	WPU_Slider("wpu_wear", "Wear", at, width, cvar("cl_knife_wear"), '0 1 100', WPU_Wear, tsz);
	at_y = at_y + tsz * 2.7;
	if (Profile_Chip("wpu_inspect", at, [(width - 12) / 3, row, 0], "Inspect", tsz, FALSE)) WP_Inspect();
	if (Profile_Chip("wpu_random", at + [(width + 6) / 3, 0, 0], [(width - 12) / 3, row, 0], "Random seed", tsz, FALSE)) WPU_Seed(floor(random() * 1001));
	if (Profile_Chip("wpu_drop", at + [(width + 6) * 2 / 3, 0, 0], [(width - 12) / 3, row, 0], "Drop", tsz, FALSE)) localcmd("cmd drop\n");
	at_y = at_y + tsz * 2.7;
	if (Profile_Chip("wpu_mount", at, [width, row, 0], "Mount installed CS:GO Legacy", tsz, FALSE)) WP_MountKnifeContent(-1);
	sui_tooltip_for("wpu_mount", "Session-only installed assets; also requested automatically when selecting a Legacy knife. No download.", sc);
	at_y = at_y + tsz * 2.7;
	if (Profile_Chip("wpu_account_save", at, [(width - 6) / 2, row, 0], "Save to account", tsz, FALSE)) VM_ProfileAction("save");
	if (Profile_Chip("wpu_account_reload", at + [(width + 6) / 2, 0, 0], [(width - 6) / 2, row, 0], "Reload account", tsz, FALSE)) VM_ProfileAction("reload");
	at_y = at_y + tsz * 2.5;
	sui_text(at, [hint, hint], VM_Status(), SUI_THEME_MUTED, 1, 0);
	at_y = at_y + tsz * 1.6;
	text = "Local previews, not inventory or exact CS paint kits.";
	if (kind > 0 && style > 0 && !strcmp(KCAT_Get(kind, KCAT_MASK), "")) text = "No compatible paint mask: showing the original finish.";
	sui_text(at, [hint, hint], text, SUI_THEME_MUTED, 1, 0);
	sui_text(at + [0, hint * 1.4, 0], [hint, hint], "CSS has embedded arms. Legacy hands use matte textures.", SUI_THEME_MUTED, 1, 0);
	// Last in this bracket: the open list owns hit-tests over covered controls.
	if (wpu_drop)
	{
		count = WPU_ListCount(wpu_drop);
		wpu_page = bound(0, wpu_page, floor((count - 1) / 9));
		start = wpu_page * 9;
		wpu_popup_size = [box_x, row * (min(9, count - start) + 1) + 8, 0];
		pop_y = bound(4, pop_y, max(4, scr_y - wpu_popup_size_y - 4));
		wpu_popup_pos = pop;
		sui_style_panel(pop, wpu_popup_size, pad * 0.5, 1);
		selected = kind;
		if (wpu_drop == 2) selected = arms;
		if (wpu_drop == 3) selected = KCAT_LocalLayer();
		for (i = 0; i < min(9, count - start); i = i + 1)
		{
			option = WPU_ListRow(wpu_drop, start + i);
			text = WPU_OptionLabel(option);
			if (WPU_ChoiceChip(sprintf("wpu_option%g_%g", wpu_drop, start + i), pop + [4, 4 + row * i, 0], [box_x - 8, row, 0], text, tsz, selected == option))
			{
				if (option == -1) cvar_set("cl_knife_arms", "0");
				else WP_ChooseKnife(option);
				wpu_drop = 0;
				break;
			}
		}
		at = pop + [4, wpu_popup_size_y - row - 4, 0];
		if (Profile_Chip("wpu_prev", at, [row * 2, row, 0], "<", tsz, FALSE)) wpu_page = max(0, wpu_page - 1);
		if (Profile_Chip("wpu_next", at + [box_x - row * 2 - 8, 0, 0], [row * 2, row, 0], ">", tsz, FALSE)) wpu_page = min(floor((count - 1) / 9), wpu_page + 1);
		sui_text(at + [row * 2 + 4, (row - hint) * 0.5, 0], [hint, hint], sprintf("%g-%g / %g", start + 1, min(start + 9, count), count), SUI_THEME_DIM, 1, 0);
	}
	sui_end();
	Font_Set(oldfont);
};

float(float evtype, float scanx, float chary, float devid) WPU_Input =
{
	if (!wpu_open) return FALSE;
	if (evtype == IE_KEYDOWN && scanx == K_ESCAPE)
	{
		if (wpu_drop) wpu_drop = 0;
		else WPU_Close();
		return TRUE;
	}
	if (evtype == IE_MOUSEABS)
	{
		wpu_mx = scanx; wpu_my = chary;
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	if (scanx == K_MOUSE1)
	{
		if (evtype == IE_KEYUP && wpu_drag) { wpu_drag = FALSE; return TRUE; }
		if (evtype == IE_KEYDOWN)
		if (wpu_mx >= wpu_pos_x && wpu_mx < wpu_pos_x + wpu_size_x - wpu_size_y * 0.11 &&
		    wpu_my >= wpu_pos_y && wpu_my < wpu_pos_y + wpu_size_y * 0.105)
		{
			wpu_drag = TRUE; wpu_drop = 0;
			wpu_offset = [wpu_mx, wpu_my, 0] - wpu_pos;
			return TRUE;
		}
		if (evtype == IE_KEYDOWN && wpu_drop)
		if (wpu_mx < wpu_popup_pos_x || wpu_mx >= wpu_popup_pos_x + wpu_popup_size_x ||
		    wpu_my < wpu_popup_pos_y || wpu_my >= wpu_popup_pos_y + wpu_popup_size_y)
		if (wpu_mx < wpu_pos_x + wpu_tsz * 8 || wpu_mx >= wpu_pos_x + wpu_size_x - wpu_tsz ||
		    wpu_my < wpu_pos_y + wpu_tsz * 4 || wpu_my >= wpu_pos_y + wpu_tsz * 12)
		{
			wpu_drop = 0;
			return TRUE;
		}
	}
	if (scanx == K_MOUSE1 || scanx == K_MOUSE2)
	{
		if (evtype == IE_KEYDOWN) _sui_mouse_move(_cursor_position, FALSE);
		sui_input_event(evtype, scanx, chary, devid);
		return TRUE;
	}
	return FALSE;
};

float() WPU_Command =
{
	local float i;
	if (strcmp(argv(0), "knife_menu")) return FALSE;
	if (!strcmp(argv(1), "select"))
	{
		if (!strcmp(argv(2), "") || strcmp(argv(3), "")) print("knife_menu select <catalog number>; knife_menu catalog lists choices\n");
		else WP_ChooseKnife(stof(argv(2)));
		return TRUE;
	}
	if (!strcmp(argv(1), "catalog"))
	{
		for (i = 0; i < 128; i = i + 1)
			if (KCAT_Valid(i)) print(sprintf("knife catalog %g: %s\n", i, KCAT_Get(i, KCAT_NAME)));
		return TRUE;
	}
	if (!strcmp(argv(1), "status"))
	{
		print(sprintf("knife_menu: open %g claims %g frames %g kind %g finish %g painted %g\n", wpu_open, UI_CursorHeld(), wpu_frames, cvar("cl_knife_model"), cvar("cl_knife_finish"), wpu_painted));
		print(sprintf("knife_menu: pos %v size %v drag %g dropdown %g arm-model %g\n", wpu_pos, wpu_size, wpu_drag, wpu_drop, KCAT_Hands()));
		print(sprintf("knife_menu: catalog knife %g hands %g layer %g active-layer %g page %g\n", KCAT_Knife(), KCAT_Hands(), KCAT_Layer(), KCAT_ActiveLayer(), wpu_page));
		print(sprintf("knife_menu: part-models %g %g bones %g %g source %g\n", wpu_parts[0].modelindex, wpu_parts[1].modelindex, wpu_counts[0], wpu_counts[1], wpu_source));
		return TRUE;
	}
	if (!strcmp(argv(1), "mount")) { WP_MountKnifeContent(-1); return TRUE; }
	if (!strcmp(argv(1), "resetpos")) { cvar_set("hud_knife_x", "0.02"); cvar_set("hud_knife_y", "0.14"); return TRUE; }
	if (!strcmp(argv(1), "close")) WPU_Close();
	else if (!strcmp(argv(1), "open")) { if (!wpu_open) WPU_Open(); }
	else if (wpu_open) WPU_Close();
	else WPU_Open();
	return TRUE;
};

void() WPU_Register =
{
	wpu_skinstate = -1;
	shaderforname("knife_hidden", "{\nsurfaceparm nodraw\n}\n");
	registercommand("knife_menu");
	registercvar("cl_knife_arms", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_arm_model", "0", CVAR_ARCHIVE);
	registercvar("hud_knife_x", "0.02", CVAR_ARCHIVE);
	registercvar("hud_knife_y", "0.14", CVAR_ARCHIVE);
	registercvar("cl_knife_finish", "0", CVAR_ARCHIVE);
	registercvar("cl_knife_seed", "0", CVAR_ARCHIVE);
	registercvar("cl_knife_scale", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_rotation", "0", CVAR_ARCHIVE);
	registercvar("cl_knife_fade", "1", CVAR_ARCHIVE);
	registercvar("cl_knife_wear", "0", CVAR_ARCHIVE);
};
