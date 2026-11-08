/*
  P1418: crash reports, the capture half.  m_init runs on every launch and never on a lobby.  When the engine's
  Sys_Error left data/crash/error.txt (P1417, P1421: the error, the engine, the console's last lines without
  typed commands or lines naming a secret), this copies it into data/crash/report_<utc>.txt and marks error.txt
  reported.  cl_crash.qc offers the report to a lobby.  No console log is involved (P1418 review 1).
*/
#define CR_LINES  120

void() Crash_Init =
{
	local float fh, out, n;
	local string ln, stem;

	registercvar("ui_crash_report", "1", 32);     // archived (cl_defs.qc CVAR_ARCHIVE); 0: never offered
	fh = fopen("data/crash/error.txt", FILE_READ);
	if (fh < 0)
		return;
	ln = fgets(fh);
	if (!ln || substring(ln, 0, 10) != "Sys_Error:")
	{
		fclose(fh);                 // none, or one already reported (rewritten below)
		return;
	}
	stem = strcat("report_", strftime(FALSE, "%Y%m%d_%H%M%S"));
	out = fopen(strcat("data/crash/", stem, ".txt"), FILE_WRITE);
	if (out < 0)
	{
		fclose(fh);
		return;
	}
	fputs(out, "FTESURF-CRASH 2\n");
	fputs(out, sprintf("utc %s\n", strftime(FALSE, "%Y-%m-%d %H:%M:%S")));
	for (n = 0; ln && n < CR_LINES; n = n + 1)
	{
		fputs(out, strcat(substring(ln, 0, 200), "\n"));
		ln = fgets(fh);
	}
	fclose(out);
	fclose(fh);
	fh = fopen("data/crash/error.txt", FILE_WRITE);
	if (fh >= 0)
	{
		fputs(fh, sprintf("reported %s\n", stem));
		fclose(fh);
	}
	print(sprintf("crash: the last session ended with an error; report saved as data/crash/%s.txt\n", stem));
};
