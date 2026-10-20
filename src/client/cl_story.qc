// Patch 856: the Story medal toast.  Lobby_StoryTell (sv_lobby.qc) writes `*story`
// on the finisher: "<serial> <b|s|g> <trophies>|<map>|<challenge> -- <list> <n>|<chapter>".
// A new value shows for 7 s, top centre.  The first value a csprogs reads is not
// news: the key outlives a map change, the csprogs does not.

float sty_tinit, sty_tstart, sty_tend, sty_tm, sty_ttot;
string sty_tkey, sty_tmap, sty_ttext, sty_tch;

void() StoryToast_Poll =
{
	local string v, m;

	v = getplayerkeyvalue(player_localnum, "*story");
	if (sty_tinit && !strcmp(v, sty_tkey))
		return;
	if (sty_tkey != "") strunzone(sty_tkey);
	sty_tkey = strzone(v);
	if (!sty_tinit)
	{
		sty_tinit = TRUE;
		return;
	}
	if (tokenizebyseparator(v, "|") < 4)
		return;
	if (sty_tmap != "") strunzone(sty_tmap);
	if (sty_ttext != "") strunzone(sty_ttext);
	if (sty_tch != "") strunzone(sty_tch);
	sty_tmap = strzone(argv(1));
	sty_ttext = strzone(argv(2));
	sty_tch = strzone(argv(3));
	if (tokenize(argv(0)) < 3)
		return;
	m = argv(1);
	sty_tm = !strcmp(m, "g") ? 3 : !strcmp(m, "s") ? 2 : 1;
	sty_ttot = stof(argv(2));
	sty_tstart = cltime;
	sty_tend = cltime + 7;
	print(sprintf("story: toast %s %s \"%s\" %g trophies\n", m, sty_tmap, sty_ttext, sty_ttot));
};

void(vector scr) StoryToast_Draw =
{
	local float sc, a, w, h, lsz, bsz, d, x, y;
	local vector col, p;
	local string head, foot;

	StoryToast_Poll();
	if (cltime >= sty_tend)
		return;
	a = bound(0, (cltime - sty_tstart) / 0.25, 1) * bound(0, (sty_tend - cltime) / 0.6, 1);
	col = SUI_THEME_FOCUS;
	head = "BRONZE MEDAL";
	if (sty_tm == 2) { col = '0.78 0.80 0.88'; head = "SILVER MEDAL"; }
	if (sty_tm == 3) { col = SUI_THEME_WARN; head = "GOLD MEDAL"; }
	foot = sprintf("%g trophies", sty_ttot);
	if (sty_tch != "")
		foot = sprintf("%s  -  %s is open", foot, sty_tch);

	sc = ui_cv_scale;
	Font_Set(ui_font_ui);
	lsz = Font_Px(8 * sc);
	bsz = Font_Px(13 * sc);
	d = 40 * sc;
	w = max(stringwidth(sty_tmap, TRUE, [bsz, bsz]), stringwidth(sty_ttext, TRUE, [lsz, lsz]),
	        stringwidth(foot, TRUE, [lsz, lsz]), stringwidth(head, TRUE, [lsz, lsz]));
	w = min(w + d + 30 * sc, scr_x - 16 * sc);
	h = 12 * sc + lsz * 3 + bsz + 6 * sc;
	p = [(scr_x - w) * 0.5, scr_y * 0.16, 0];
	_sui_round_draw(p, [w, h, 0], 6 * sc, SUI_THEME_PANEL, 0.92 * a);
	_sui_round_draw(p, [3 * sc, h, 0], 1.5 * sc, col, a);
	// The medal: a disc, a darker face, a bright rim.
	x = p_x + 12 * sc;
	y = p_y + (h - d) * 0.5;
	_sui_round_draw([x, y, 0], [d, d, 0], d * 0.5, col, a);
	_sui_round_draw([x + 4 * sc, y + 4 * sc, 0], [d - 8 * sc, d - 8 * sc, 0], (d - 8 * sc) * 0.5,
	                col * 0.72, a);
	HUD_TextC([x + d * 0.5, y + (d - bsz) * 0.5], ftos(sty_tm), bsz, SUI_THEME_PANEL, a);
	x = x + d + 12 * sc;
	y = p_y + 6 * sc;
	HUD_Text([x, y], head, lsz, col, a);
	y = y + lsz + 2 * sc;
	HUD_Text([x, y], sty_tmap, bsz, SUI_THEME_TEXT, a);
	y = y + bsz + 2 * sc;
	HUD_Text([x, y], sty_ttext, lsz, SUI_THEME_DIM, a);
	y = y + lsz + 2 * sc;
	HUD_Text([x, y], foot, lsz, SUI_THEME_WARN, a);
	Font_Reset();
};
