// Patch 723: publish this server's exact-map ratings, not the client's catalogue.
// Each info value stays below QW's 64-byte large/blob boundary. Initial large
// serverinfo blobs are not delivered by all supported client/server pairs.
// P1371: zones TRUE (SV_ZoneLoad, after this map's file is read) lets the zone file's
// momentumTier/ksfTier replace the main track's row; MOM's source then reads "zone".
void(float zones) SV_MapTierInit =
{
	local float fh, n, i, start, stop, track, leg;
	local string line, value, prefix, row, row00, mom, src, ksf;

	for (i = 0; i <= 99; i = i + 1)
	{
		forceinfokey(world, sprintf("maprating_0_%g", i), "");
		if (i > 0) forceinfokey(world, sprintf("maprating_%g_0", i), "");
	}
	prefix = strzone(strcat("v1;", mapname, ";"));
	value = row00 = "";
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
			{
				forceinfokey(world, sprintf("maprating_%g_%g", track, leg), row);
				if (track == 0 && leg == 0)
				{
					if (row00 != "") strunzone(row00);
					row00 = strzone(row);
				}
			}
			start = stop + 1;
		}
		strunzone(value);
	}
	if (zones && zone_mapname == mapname && (zone_tier_mom > 0 || zone_tier_ksf > 0))
	{
		mom = src = ksf = "-"; line = "-,-";
		if (row00 != "" && tokenizebyseparator(row00, ",") == 7)
		{
			mom = argv(2); src = argv(3); ksf = argv(4);
			line = strcat(argv(5), ",", argv(6));
		}
		row = strcat("0,0,", zone_tier_mom > 0 ? ftos(zone_tier_mom) : mom, ",",
		             zone_tier_mom > 0 ? "zone" : src, ",",
		             zone_tier_ksf > 0 ? ftos(zone_tier_ksf) : ksf, ",", line);
		forceinfokey(world, "maprating_0_0", row);
	}
	if (row00 != "") strunzone(row00);
	// Marker last: missing/unknown data is explicit, never an old-map fallback.
	forceinfokey(world, "mapratings", strcat("v1:", mapname));
	strunzone(prefix);
};
