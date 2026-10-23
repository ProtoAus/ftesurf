/* Per-player Max Fog event. Native gamecode fog locks ordinary console changes;
   density zero unlocks it again. No global cvar, timing or recording change. */
.float eventfog_on;
.float eventfog_next;

void(entity e, float clearfog) EventFog_Emit =
{
	forceinfokey(e, "*maxfog", e.eventfog_on ? "1" : "");
	if (e.eventfog_on)
	{
		// Positive distances: non-positive density disables native fog drawing.
		stuffcmd(e, "fog 256 0.6 0.6 0.6 1 0\n"
		            "skyroomfog 1 0.6 0.6 0.6 1 0\n"
		            "waterfog 256 0.6 0.6 0.6 1 0\n");
	}
	else if (clearfog)
	{
		// Last command leaves the shared native fog lock clear. CSQC restores
		// the ordinary map/controller settings after its mode key changes.
		stuffcmd(e, "skyroomfog 0\nwaterfog 0\nfog 0\n");
	}
};

void(entity e) EventFog_Reset =
{
	forceinfokey(world, "*maxfogver", "1");
	e.eventfog_on = FALSE;
	e.eventfog_next = 0;
	e.lobby_sty_maxfog = FALSE;
	forceinfokey(e, "*maxfog", "");
};

void(entity e, float argc, string arg) EventFog_Command =
{
	local float on, whole;

	if (clienttype(e) != CLIENTTYPE_REAL) return;
	if (strcmp(e.classname, "player")) return;
	if (argc == 2)
	if (!strcmp(arg, "status"))
	{
		whole = -1;
		if (e.lobby_sty_ok) whole = e.lobby_sty_maxfog;
		sprint(e, PRINT_HIGH, sprintf("maxfog: mode=%g whole-run=%g (unknown=-1)\n",
		       e.eventfog_on, whole));
		return;
	}
	if (argc > 2)
	{
		sprint(e, PRINT_HIGH, "maxfog: [0|1|status], or no argument to toggle\n");
		return;
	}
	on = !e.eventfog_on;
	if (argc == 2)
	{
		if (strcmp(arg, "0") && strcmp(arg, "1"))
		{
			sprint(e, PRINT_HIGH, "maxfog: [0|1|status], or no argument to toggle\n");
			return;
		}
		on = !strcmp(arg, "1");
	}
	if (on == e.eventfog_on) return;
	if (time < e.eventfog_next) return;
	e.eventfog_next = time + 0.25;
	e.eventfog_on = on;
	// A late enable never repairs an already ordinary/disabled run.
	if (!on) e.lobby_sty_maxfog = FALSE;
	EventFog_Emit(e, TRUE);
	if (on)
		sprint(e, PRINT_CHAT, "^5maxfog:^7 ON for you only; restart the timer for a whole-run Max Fog finish\n");
	else
		sprint(e, PRINT_CHAT, "^5maxfog:^7 OFF; ordinary map fog restored\n");
};
