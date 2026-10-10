string p603life_saved_name;
float(string cmd) P603_LifeCommand =
{
	local string op;
	local vector pixel, virt;
	local float took, found, mode;
	local string label;
	local int i;
	tokenize(cmd);
	if (strcmp(argv(0), "p603life")) return FALSE;
	op = argv(1);
	if (!strcmp(op, "key"))
	{
		took = CSQC_InputEvent(stof(argv(3)) ? IE_KEYDOWN : IE_KEYUP, stof(argv(2)), 0, 0);
		print(sprintf("P603 LIFEKEY scan=%s down=%s took=%g\n", argv(2), argv(3), took));
	}
	else if (!strcmp(op, "target"))
	{
		pixel = getproperty(VF_SCREENPSIZE);
		virt = getproperty(VF_SCREENVSIZE);
		found = FALSE;
		for (i = 0i; i < (int)min(MAX_ACTION_ELEMENTS, _action_elements_index); i = i + 1i)
			if (!strcmp(_action_elements[i].id, argv(2)))
			{
				p603_point = _action_elements[i].pos + _action_elements[i].size * 0.5;
				p603_point_x = p603_point_x * pixel_x / virt_x;
				p603_point_y = p603_point_y * pixel_y / virt_y;
				found = TRUE;
				break;
			}
		print(sprintf("P603 LIFETARGET id=%s found=%g\n", argv(2), found));
		P603_Mouse();
	}
	else if (!strcmp(op, "room"))
	{
		pixel = getproperty(VF_SCREENPSIZE);
		virt = getproperty(VF_SCREENVSIZE);
		p603_point = pl_panelpos + pl_panelsize * 0.5;
		p603_point_x = p603_point_x * pixel_x / virt_x;
		p603_point_y = p603_point_y * pixel_y / virt_y;
		print(sprintf("P603 LIFEROOM width=%g height=%g\n", pl_panelsize_x, pl_panelsize_y));
		P603_Mouse();
	}
	else if (!strcmp(op, "dock"))
	{
		print(sprintf("P603 DOCK clipped=%g gap=%g hover=%g\n",
			fabs(scn_pos_x + scn_size_x + 1 - pl_panelpos_x) < 0.01,
			pl_panelpos_x - (scn_pos_x + scn_size_x), scn_hover));
	}
	else if (!strcmp(op, "cache_set"))
	{
		if (!strcmp(p603life_saved_name, "")) p603life_saved_name = strzone(bufstr_get(rec_sb_bowner, 0));
		mode = stof(argv(2));
		label = mode == 1 ? "^1P603 cache\nLiteral\t## / ###" : "^2P603 cache\nLiteral\t## / ###";
		if (mode == 3) label = "^2P603 changed\rLiteral\t## / ###";
		bufstr_set(rec_sb_bowner, 0, label);
	}
	else if (!strcmp(op, "cache_probe"))
	{
		label = Scores_NativePlain(bufstr_get(rec_sb_bowner, 0));
		print(sprintf("P603 CACHE %s ok=%g raw=%g revision=%g\n", argv(2),
			!strcmp(bufstr_get(scn_labels, 72), label),
			!strcmp(bufstr_get(scn_rawlabels, 8), bufstr_get(rec_sb_bowner, 0)), scn_revision));
	}
	else if (!strcmp(op, "cache_restore"))
	{
		bufstr_set(rec_sb_bowner, 0, p603life_saved_name);
		strunzone(p603life_saved_name); p603life_saved_name = "";
	}
	else if (!strcmp(op, "probe"))
	{
		print(sprintf("P603 LIFE %s chat=%g editor=%g mouse=%g keyboard=%g tab=%g filter=%g\n",
			argv(2), chat_typing, ui_he_open, sui_style_mouse_focus, sui_style_key_focus, rec_sb_tab, rec_sb_filter));
		print(sprintf("P603 LIFEFALL %s draw=%g model=%g\n", argv(2), p603life_drawfails, p603life_modelfails));
	}
	else print("P603 LIFEUNKNOWN\n");
	return TRUE;
};
