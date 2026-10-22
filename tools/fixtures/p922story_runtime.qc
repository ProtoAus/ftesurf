// Test-only wrapper: the real Story formatter, not a Python copy of its rule.
#undef m_consolecommand
float(string cmd) m_consolecommand =
{
	tokenize(cmd);
	if (argv(0) == "ui_menu_probe" && argv(1) == "p921story")
	{
		print(sprintf("P921 STORY zero=%g one=%g many=%g unknown=%g\n",
			!strcmp(Sty_Population(0), ""), !strcmp(Sty_Population(1), "1 player live"),
			!strcmp(Sty_Population(3), "3 players live"),
			!strcmp(Sty_Population(-1), "Players live: unavailable")));
		return TRUE;
	}
	return P921_RealMenuCommand(cmd);
};
