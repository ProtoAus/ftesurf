/* P925: observational KSF playback on explicitly linked map builds only.
   The board's family or the menu's persisted map list supplies the relation;
   suffixes never do. This says nothing about BSP identity or native evidence. */
#define MAPPORT_MAXFAMILY 256
#define MAPPORT_MAXBYTES 2097152
#define MAPPORT_MAXLINES 16384

float mapport_board; // strbuf: one validated board family's names

float(string s) MapPort_Word =
{
	local float i, c, n;

	n = strlen(s);
	if (n < 1 || n > 64) return FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		c = str2chr(s, i);
		if (c >= 'a' && c <= 'z') continue;
		if (c >= '0' && c <= '9') continue;
		if (c == '_' || c == '-') continue;
		return FALSE;
	}
	return TRUE;
};

// Called only after Online_Reply has accepted the request's scope.
void(string map, float root) MapPort_Board =
{
	local float a, n, i, have;
	local string s;

	if (mapport_board > 0) buf_del(mapport_board);
	mapport_board = 0;
	a = json_find_object_child(root, "family");
	n = json_get_length(a);
	if (n < 1 || n > MAPPORT_MAXFAMILY) return;
	mapport_board = buf_create();
	have = FALSE;
	for (i = 0; i < n; i = i + 1)
	{
		s = json_get_string(json_get_child_at_index(a, i));
		if (!MapPort_Word(s)) break;
		bufstr_set(mapport_board, i, s);
		if (!strcasecmp(s, map)) have = TRUE;
	}
	if (i < n || !have)
	{
		buf_del(mapport_board);
		mapport_board = 0;
	}
};

string(string path) MapPort_Mtime =
{
	local searchhandle h;
	local string s;

	h = search_begin(path, 0, TRUE);
	if (h < 0) return "";
	s = "";
	if (search_getsize(h) > 0) s = search_getfilemtime(h, 0);
	search_end(h);
	return s;
};

// Match the menu's net-vs-shipped freshness choice, including unknown pak mtimes.
float() MapPort_OpenList =
{
	local float f, shipped;
	local string a, b;

	a = strzone(MapPort_Mtime("data/mapdl.net.txt"));
	b = MapPort_Mtime("data/mapdl.txt");
	shipped = FALSE;
	if (a != "" && b != "") shipped = (strcmp(a, b) < 0);
	strunzone(a);
	if (shipped) f = fopen("data/mapdl.txt", FILE_READ);
	else f = fopen("data/mapdl.net.txt", FILE_READ);
	if (f < 0) f = fopen("data/mapdl.txt", FILE_READ);
	return f;
};

float(string source, string loaded) MapPort_MatchClean =
{
	local float i, n, a, b, f, lines, bytes, valid, source_n, loaded_n, root_n;
	local string s, base, source_base, loaded_base;

	if (!MapPort_Word(source) || !MapPort_Word(loaded)) return FALSE;
	if (!strcmp(source, loaded)) return TRUE;
	a = b = lines = source_n = loaded_n = root_n = 0;
	source_base = loaded_base = "";
	if (mapport_board > 0)
	{
		for (i = 0; i < buf_getsize(mapport_board); i = i + 1)
		{
			s = bufstr_get(mapport_board, i);
			if (!strcmp(s, source)) a = TRUE;
			if (!strcmp(s, loaded)) b = TRUE;
		}
		if (a && b) return TRUE;
	}

	f = MapPort_OpenList();
	if (f < 0) return FALSE;
	bytes = fsize(f);
	valid = (bytes <= MAPPORT_MAXBYTES);
	s = fgets(f);
	if (strcmp(s, "FTESURF-MAPDL 1")) valid = FALSE;
	while (valid)
	{
		s = fgets(f);
		if (s == "")
		if (fseek(f) >= bytes) break;
		lines = lines + 1;
		if (lines > MAPPORT_MAXLINES) { valid = FALSE; break; }
		n = tokenize(s);
		if (n < 10) continue;
		if (strcmp(argv(0), "dl")) continue;
		if (!MapPort_Word(argv(1))) continue;
		base = argv(1);
		if (n >= 11)
		if (strcmp(argv(10), "-"))
		{
			if (!MapPort_Word(argv(10))) continue;
			if (!strcmp(argv(1), argv(10))) continue;
			base = argv(10);
		}
		if (!strcmp(argv(1), source))
		{
			source_n = source_n + 1;
			if (source_n == 1) source_base = strzone(base);
		}
		if (!strcmp(argv(1), loaded))
		{
			loaded_n = loaded_n + 1;
			if (loaded_n == 1) loaded_base = strzone(base);
		}
	}
	a = FALSE;
	if (valid && source_n == 1 && loaded_n == 1)
	if (!strcmp(source_base, loaded_base))
	{
		// Like the backend: a family root cannot itself be a linked child.
		fseek(f, 0);
		lines = 0;
		while (1)
		{
			s = fgets(f);
			if (s == "")
			if (fseek(f) >= bytes) break;
			lines = lines + 1;
			if (lines > MAPPORT_MAXLINES) { a = FALSE; break; }
			n = tokenize(s);
			if (n < 10) continue;
			if (strcmp(argv(0), "dl")) continue;
			if (strcmp(argv(1), source_base)) continue;
			root_n = root_n + 1;
			a = TRUE;
			if (n >= 11)
			if (strcmp(argv(10), "-")) a = FALSE;
		}
		if (root_n != 1) a = FALSE;
	}
	fclose(f);
	if (source_n > 0) strunzone(source_base);
	if (loaded_n > 0) strunzone(loaded_base);
	return a;
};

float(string source, string loaded) MapPort_Match =
{
	local string a, b;
	local float yes;

	if (source == "" || loaded == "") return FALSE;
	if (!strcmp(source, loaded)) return TRUE;
	a = strzone(strtolower(source));
	b = strzone(strtolower(loaded));
	yes = MapPort_MatchClean(a, b);
	strunzone(a);
	strunzone(b);
	return yes;
};
