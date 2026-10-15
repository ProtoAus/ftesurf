// TEST ONLY: inserted into an owned source overlay, never a production manifest.
float players_fixture_first, players_fixture_last, players_fixture_drawn, players_fixture_generation;
string(float slot, string key) PlayersFixture_Key =
{
	if (!cvar("players_fixture")) return getplayerkeyvalue(slot, key);
	if (!strcmp(key, "name")) return sprintf("FIXTURE Player %02g", slot + 1);
	if (!strcmp(key, "*ahash") || !strcmp(key, "*phash")) return sprintf("%08x", slot + 1);
	if (!strcmp(key, "ping")) return "42";
	if (!strcmp(key, "userid")) return ftos(slot + 100);
	return "";
};
void() PlayersFixture_Begin =
{
	players_fixture_generation = players_fixture_generation + 1;
	players_fixture_first = -1;
	players_fixture_last = -1;
	players_fixture_drawn = 0;
};
void(float row) PlayersFixture_Row =
{
	if (players_fixture_first < 0) players_fixture_first = row;
	players_fixture_last = row;
	players_fixture_drawn = players_fixture_drawn + 1;
};
void() PlayersFixture_Status =
{
	print(sprintf("PLAYERS FIXTURE mode %g visible %g..%g drawn %g gen %g\n", cvar("players_fixture"),
	              players_fixture_first, players_fixture_last, players_fixture_drawn, players_fixture_generation));
};
