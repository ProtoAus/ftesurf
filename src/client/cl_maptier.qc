// Patch 723. One speller for the HUD and scoreboard. Ratings are display-only.
// HUD_SK's existing fake overlay supplies non-mutating runtime controls.
string(string k) HUD_SK;

string(string row, float field) MapTier_Field =
{
	local float start, stop, i;

	start = 0;
	for (i = 0; i <= field; i = i + 1)
	{
		stop = strstrofs(row, ",", start);
		if (stop < 0) stop = strlen(row);
		if (i == field) return substring(row, start, stop - start);
		if (stop == strlen(row)) return "";
		start = stop + 1;
	}
	return "";
};

string(float track, float leg) MapTier_Row =
{
	local string raw, prefix, key;
	local float start, stop;

	raw = HUD_SK("mapratings");
	// Real servers publish short, unencoded per-leg keys (no info blobs).
	if (!strcmp(raw, strcat("v1:", HUD_SK("map"))))
		return HUD_SK(sprintf("maprating_%g_%g", track, leg));
	// The existing non-mutating HUD_SK fake overlay can supply a whole payload.
	prefix = strcat("v1;", HUD_SK("map"), ";");
	if (strstrofs(raw, prefix, 0) != 0) return "";
	key = sprintf(";%g,%g,", track, leg);
	start = strstrofs(raw, key, strlen(prefix) - 1);
	if (start < 0) return "";
	start = start + 1;
	stop = strstrofs(raw, ";", start);
	if (stop < 0) return "";           // an incomplete row is not a rating
	return substring(raw, start, stop - start);
};

float(string s) MapTier_Number =
{
	local float n;

	n = stof(s);
	if (n < 1 || n > 10) return 0;
	if (strcmp(s, ftos(n))) return 0;
	if (n != floor(n)) return 0;
	return n;
};

string(string s) MapTier_Letter =
{
	if (strlen(s) != 1) return "";
	if (strstrofs("?YXSABCDFG", s, 0) < 0) return "";
	return s;
};

string(float track, float leg, float compact, float unknown) MapTier_Text =
{
	local string row, src, mom, ksf, unit, strafe;
	local float mt, kt;

	row = MapTier_Row(track, leg);
	src = MapTier_Field(row, 3);
	mt = 0;
	if (!strcmp(src, "rank") || !strcmp(src, "sugg"))
		mt = MapTier_Number(MapTier_Field(row, 2));
	kt = MapTier_Number(MapTier_Field(row, 4));
	unit = MapTier_Letter(MapTier_Field(row, 5));
	strafe = MapTier_Letter(MapTier_Field(row, 6));

	// Old servers publish one tier only. Never relabel KSF/aliases as MOM.
	if (HUD_SK("mapratings") == "")
	if (track == 0 && leg == 0)
	{
		src = HUD_SK("maptiersrc");
		if (!strcmp(src, "rank") || !strcmp(src, "sugg"))
			mt = MapTier_Number(HUD_SK("maptier"));
		else if (!strcmp(src, "ksf"))
			kt = MapTier_Number(HUD_SK("maptier"));
	}
	mom = ksf = "";
	if (mt > 0)
	{
		mom = sprintf(compact ? "MOM %g" : "MOM tier %g", mt);
		if (!strcmp(src, "sugg"))
			mom = strcat(mom, compact ? "*" : " (suggested)");
	}
	else if (unknown)
		mom = compact ? "MOM ?" : "MOM tier ?";
	if (track > 0 && leg == 0)
	{
		if (unit != "")
			ksf = sprintf(compact ? "KSF U:%s" : "KSF bonus %s (unit)", unit);
		if (strafe != "")
		{
			if (ksf != "")
				ksf = strcat(ksf, sprintf(compact ? " S:%s" : " / %s (strafe)", strafe));
			else
				ksf = sprintf(compact ? "KSF S:%s" : "KSF bonus %s (strafe)", strafe);
		}
	}
	else if (track == 0 && leg == 0)
	{
		if (kt > 0) ksf = sprintf(compact ? "KSF %g" : "KSF tier %g", kt);
	}
	if (ksf == "" && unknown)
		ksf = compact ? "KSF ?" : "KSF tier ?";
	if (mom == "") return ksf;
	if (ksf == "") return mom;
	return strcat(mom, compact ? "  " : " | ", ksf);
};

// Current server-timed stage (0-based stat -> 1-based leg), not checkpoint N.
string() MapTier_Current =
{
	local float track, leg;
	local string s;

	track = getstatf(STAT_FS_TIMERTRACK);
	leg = 0;
	if (getstatf(STAT_FS_TIMERSEGS) > 1)
		leg = getstatf(STAT_FS_TIMERSEG) + 1;
	if (track == 0 && leg == 0) return "";
	s = MapTier_Text(track, leg, FALSE, FALSE);
	// A staged bonus may have a whole-bonus rating but no per-stage rating.
	if (track > 0 && leg > 0)
	{
		if (s != "")
			return sprintf("bonus %g stage %g: %s", track, leg, s);
		leg = 0;
		s = MapTier_Text(track, 0, FALSE, FALSE);
	}
	if (s == "") return "";
	if (track > 0)
	{
		if (leg > 0) return sprintf("bonus %g stage %g: %s", track, leg, s);
		return sprintf("bonus %g: %s", track, s);
	}
	return sprintf("stage %g: %s", leg, s);
};
