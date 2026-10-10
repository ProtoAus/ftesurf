//Loopback driver/probes only. Production URI callback/parser/identity/actions run.
string p603_http_label;
void() P603_HttpFrame =
{
	local float i;
	local string label;
	if (!strcmp(p603_http_label, "")) return;
	label = p603_http_label;
	print(sprintf("P603 HTTP %s state=%g rows=%g mine=%g epoch=%g revision=%g page=%g\n",
		label, ob_state, ob_n, ob_mine, ob_epoch, scn_revision, scn_page));
	print(sprintf("P603 ROUTE %s painted=%g handle=%g watch=%g samples=%g lines=%g ready=%g\n",
		label, scn_painted, scn_handle, rec_wt_open, rec_wt_nsamp, sb_ln_st[0], ln_n[1]));
	print(sprintf("P603 PHASH %s: %s\n", label, getplayerkeyvalue(player_localnum, "*phash")));
	if (scn_labels >= 0)
		for (i = 0; i < scn_count; i = i + 1)
			print(sprintf("P603 CELL %s %g: %s\n", label, i, bufstr_get(scn_labels, i)));
	strunzone(p603_http_label);
	p603_http_label = "";
};
float(string cmd) P603_HttpCommand =
{
	if (strcmp(argv(0), "p603http")) return FALSE;
	if (!strcmp(argv(1), "probe"))
	{
		if (strcmp(p603_http_label, ""))
		{
			print("P603 HTTP ERROR unconsumed probe\n");
			strunzone(p603_http_label);
		}
		p603_http_label = strzone(argv(2));
	}
	else print("P603 HTTP ERROR unknown command\n");
	return TRUE;
};
