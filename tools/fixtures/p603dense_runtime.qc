//Synthetic motion/probes only. Production negotiates capacity, builds the page,
//receives real input and resolves tokens into current row keys before dispatch.
float(string cmd) P603_DenseCommand =
{
	local string op, target, label;
	local float i, base, rows, selected, font, scale, row, x, y, pad, footer, bar, rh;
	local vector pixel, virt, ratio;
	if (strcmp(argv(0), "p603dense")) return FALSE;
	op = argv(1);
	if (!strcmp(op, "probe"))
	{
		label = argv(2);
		base = 5; rows = 0; selected = -1;
		if (scn_painted && scn_cells != __NULL__)
		{
			if (scn_cells[20] == 6) base = 6;
			rows = (scn_count - base) / 9;
			if (scn_cells[19])
				for (i = 0; i < rows; i = i + 1)
					if (scn_cells[17] == scn_tokens[i]) selected = scn_page + i;
		}
		print(sprintf("P603 DENSE %s limit=%g pagesize=%g page=%g rows=%g count=%g selected=%g\n",
			label, NUI_ModelLimit(), scn_pagesize, scn_page, rows, scn_count, selected));
		if (scn_painted)
			print(sprintf("P603 DENSERANK %s first=%s last=%s\n", label,
				bufstr_get(scn_labels, base), rows > 0 ? bufstr_get(scn_labels, base + (rows - 1) * 9) : "0"));
		print(sprintf("P603 DENSEPATH %s %s\n", label, rec_wt_open ? rec_wt_path : "-"));
	}
	else if (!strcmp(op, "forget")) Scores_ForgetFinish();
	else if (!strcmp(op, "finish"))
	{
		row = stof(argv(2));
		Scores_NoteFinish(rec_sb_legtrack[rec_sb_leg], rec_sb_legnum[rec_sb_leg], rec_sb_rowticks[row], 0, FALSE);
	}
	else if (!strcmp(op, "move") || !strcmp(op, "cursor"))
	{
		//"cursor" sends motion to the native cell's place even while legacy paints
		//(scn_pos outlives a close): the table must not need to have seen it.
		target = argv(2);
		if (!strcmp(op, "move"))
			if (!scn_painted) { P603_Point(target); return TRUE; }
		pixel = getproperty(VF_SCREENPSIZE); virt = getproperty(VF_SCREENVSIZE);
		ratio = [pixel_x / virt_x, pixel_y / virt_y, 0];
		font = Scores_NativeFontPx(); scale = font / 13; row = stof(argv(3));
		x = scn_pos_x * ratio_x + (strcmp(target, "line") ? 235 : 777) * scale;
		rh = font + 2 * floor(3 * scale) + 2 * floor(2 * scale);
		y = scn_pos_y * ratio_y + 55 * scale + row * rh;
		if (!strcmp(argv(3), "tail"))
		{
			pad = floor(8 * scale);
			footer = font + 2 * floor(3 * scale) + floor(4 * scale);
			//All four bakes use the actual inherited viewport. At large sizes
			//the fixed-width columns overflow and consume a horizontal bar.
			bar = floor(14 * scale);
			y = (scn_pos_y + scn_size_y) * ratio_y - pad - footer - bar - rh * 0.5 - 1;
		}
		if (!strcmp(target, "next")) { x = scn_pos_x * ratio_x + 140 * scale; y = (scn_pos_y + scn_size_y) * ratio_y - 18 * scale; }
		if (!strcmp(target, "previous")) { x = scn_pos_x * ratio_x + 42 * scale; y = (scn_pos_y + scn_size_y) * ratio_y - 18 * scale; }
		p603_point = [x, y, 0]; P603_Mouse();
		print(sprintf("P603 DENSEPOINT %s %s %.2f %.2f\n", target, argv(3), x, y));
	}
	else if (!strcmp(op, "wheel"))
	{
		P603_Mouse();
		i = stof(argv(2)) > 0 ? K_MWHEELUP : K_MWHEELDOWN;
		P603_RealInput(IE_KEYDOWN, i, 0, 0);
		P603_RealInput(IE_KEYUP, i, 0, 0);
	}
	else print("P603 DENSE UNKNOWN\n");
	return TRUE;
};
