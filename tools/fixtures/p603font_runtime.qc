//Test-only motion/probes; production chooses fonts, draws, resolves and dispatches actions.
float(string cmd) P603_FontCommand =
{
	local string op, label;
	local float scale, committed;
	local vector pixel, virt, ratio;
	if (strcmp(argv(0), "p603font")) return FALSE;
	op = argv(1);
	if (!strcmp(op, "probe"))
	{
		label = argv(2);
		print(sprintf("P603 FONTREQUEST %s text=%s\n", label, cvar_string("ui_native_scores_font")));
		committed = 0;
		if (scn_painted && scn_cells != __NULL__)
		{
			committed = 13;
			if (scn_cells[20] == 6) committed = stof(bufstr_get(scn_labels, 5));
		}
		print(sprintf("P603 FONT %s request=%g snapped=%g committed=%g count=%g\n",
			label, cvar("ui_native_scores_font"), Scores_NativeFontPx(), committed, scn_count));
	}
	else if (!strcmp(op, "move"))
	{
		if (!scn_painted) { P603_Point(argv(2)); return TRUE; }
		pixel = getproperty(VF_SCREENPSIZE);
		virt = getproperty(VF_SCREENVSIZE);
		ratio = [pixel_x / virt_x, pixel_y / virt_y, 0];
		scale = Scores_NativeFontPx() / 13;
		p603_point = [scn_pos_x * ratio_x + 235 * scale, scn_pos_y * ratio_y + 55 * scale, 0];
		if (!strcmp(argv(2), "next")) p603_point =
			[scn_pos_x * ratio_x + 140 * scale, (scn_pos_y + scn_size_y) * ratio_y - 18 * scale, 0];
		if (!strcmp(argv(2), "previous")) p603_point =
			[scn_pos_x * ratio_x + 42 * scale, (scn_pos_y + scn_size_y) * ratio_y - 18 * scale, 0];
		P603_Mouse();
		print(sprintf("P603 FONTPOINT %s %.2f %.2f\n", argv(2), p603_point_x, p603_point_y));
	}
	else print("P603 FONT UNKNOWN\n");
	return TRUE;
};
