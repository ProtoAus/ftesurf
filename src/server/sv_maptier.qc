// Patch 723: publish this server's exact-map ratings, not the client's catalogue.
// Each info value stays below QW's 64-byte large/blob boundary. Initial large
// serverinfo blobs are not delivered by all supported client/server pairs.
void() SV_MapTierInit =
{
	local float fh, n, i, start, stop, track, leg;
	local string line, value, prefix, row;

	for (i = 0; i <= 99; i = i + 1)
	{
		forceinfokey(world, sprintf("maprating_0_%g", i), "");
		if (i > 0) forceinfokey(world, sprintf("maprating_%g_0", i), "");
	}
	prefix = strzone(strcat("v1;", mapname, ";"));
	value = "";
	fh = fopen("maps/tiers.txt", FILE_READ);
	if (fh >= 0)
	{
		while ((line = fgets(fh)))
		{
			n = tokenize(line);
			if (n != 3) continue;
			if (strcmp(argv(0), "tiers")) continue;
			if (strcmp(argv(1), mapname)) continue;
			if (strlen(argv(2)) > 2047) continue;
			if (strstrofs(argv(2), prefix, 0) != 0) continue;
			value = strzone(argv(2));
			break;
		}
		fclose(fh);
	}
	if (value != "")
	{
		start = strlen(prefix);
		while ((stop = strstrofs(value, ";", start)) >= 0)
		{
			row = substring(value, start, stop - start);
			n = tokenizebyseparator(row, ",");
			track = stof(argv(0));
			leg = stof(argv(1));
			if (n == 7 && strlen(row) < 64)
			if (track >= 0 && track <= 99 && leg >= 0 && leg <= 99)
			if (track == floor(track) && leg == floor(leg))
			if (track == 0 || leg == 0)
				forceinfokey(world, sprintf("maprating_%g_%g", track, leg), row);
			start = stop + 1;
		}
		strunzone(value);
	}
	// Marker last: missing/unknown data is explicit, never an old-map fallback.
	forceinfokey(world, "mapratings", strcat("v1:", mapname));
	strunzone(prefix);
};
