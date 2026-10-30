// P1140: collaboration is explicit, local-only, and never a human-run import.
// Included after sv_tasproject: all downloads go through its existing strict reader.
#define TSH_MAXBODY 8388608
// FTE's fifth argument posts a string buffer. Generated DP defs expose only four.
float(string url, float id, string mime, string separator, strbuf buffer) tsh_uri_buffer = #513;
.float tsh_req, tsh_at, tsh_kind, tsh_search, tsh_index;
.string tsh_sha, tsh_name, tsh_loadname;
.float tsh_loadat;

void(entity e) SV_TASShareStop =
{
	e.tsh_req = e.tsh_kind = 0;
	if (e.tsh_search) search_end(e.tsh_search - 1);
	e.tsh_search = e.tsh_index = 0;
	if (e.tsh_sha != "") strunzone(e.tsh_sha);
	if (e.tsh_name != "") strunzone(e.tsh_name);
	e.tsh_sha = e.tsh_name = "";
};

void(entity e) SV_TASShareCancel =
{
	SV_TASShareStop(e);
	if (e.tsh_loadname != "") strunzone(e.tsh_loadname);
	e.tsh_loadname = ""; e.tsh_loadat = 0;
};

float(entity e) SV_TASShareLocal =
{
	local string ip;
	if (!SV_TASPLocalOnly(e)) return FALSE;
	ip = strtolower(infokey(e, "ip"));
	if (strcmp(ip, "loopback") && strcmp(ip, "127.0.0.1") && substring(ip, 0, 10) != "127.0.0.1:")
	{
		sprint(e, PRINT_HIGH, "tas share: host this game locally first\n"); return FALSE;
	}
	return TRUE;
};

string() SV_TASShareURL =
{
	// Operator configuration, never a URL supplied by a player or revision.
	local string url;
	url = cvar_string("tas_directory");
	if (!strcmp(url,"")) return "https://play.proto.bar/api/tasrev";
	return url;
};

// The existing reader already bound this saved revision. A buffer keeps this linear
// even for a full project; uri_get joins without an extra terminal blank line.
float(entity e) SV_TASShareBody =
{
	local float f, bytes, rows, id, ok;
	local strbuf b;
	local string line, path;
	path = strzone(SV_TASPRevPath(e.tsh_sha, "tasp"));
	tpr_pathover = path;
	ok = SV_TASPRead(e, "shared", FALSE);
	tpr_pathover = "";
	ok = (ok && !strcmp(tpr_h, e.tsh_sha));
	SV_TASPReadFree();
	if (!ok) { strunzone(path); return FALSE; }
	f = fopen(path, FILE_READ); strunzone(path);
	if (f < 0) return FALSE;
	b = buf_create(); bytes = rows = 0;
	while ((line = fgets(f)))
	{
		bytes = bytes + strlen(line) + 1;
		if (bytes > TSH_MAXBODY || rows > TASP_MAX + TASP_CPMAX + 32) break;
		bufstr_set(b, rows, strcat(line, "\n")); rows = rows + 1;
	}
	fclose(f);
	ok = FALSE;
	if (bytes <= TSH_MAXBODY && rows <= TASP_MAX + TASP_CPMAX + 32)
	{
		id = Account_NextId(); e.tsh_req = id; e.tsh_at = time; e.tsh_kind = 2;
		ok = tsh_uri_buffer(strcat(SV_TASShareURL(), "/revision"), id, "text/x-tasrev", "", b);
	}
	buf_del(b);
	return ok;
};

float(entity e) SV_TASShareNext =
{
	local float f, i, c;
	local string path, line;
	while (e.tsh_search)
	{
		if (e.tsh_index >= search_getsize(e.tsh_search - 1)) break;
		path = search_getfilename(e.tsh_search - 1, e.tsh_index); e.tsh_index = e.tsh_index + 1;
		f = fopen(path, FILE_READ);
		if (f < 0) { sprint(e, PRINT_HIGH,"tas share: cannot read a saved statement\n"); return FALSE; }
		line = strzone(fgets(f)); fclose(f);
		// Signature verification remains at tasrevd. Only its fixed ASCII line is
		// permitted in this JSON string; no local paths, keys or arbitrary files.
		if (strlen(line) > 1024 || tokenize(line) != 10)
		{
			strunzone(line); sprint(e, PRINT_HIGH,"tas share: malformed saved statement\n"); return FALSE;
		}
		if (strcmp(argv(0),"tasrev") || strcmp(argv(1),"1") || strcmp(argv(2), e.tsh_sha))
		{
			strunzone(line); sprint(e, PRINT_HIGH,"tas share: statement identity does not match\n"); return FALSE;
		}
		for (i = 0; i < strlen(line); i = i + 1)
		{
			c = str2chr(line, i);
			if (!(c == 32 || c == 45 || (c >= 48 && c <= 57) || (c >= 97 && c <= 122)))
			{
				strunzone(line); sprint(e, PRINT_HIGH,"tas share: unsafe saved statement text\n"); return FALSE;
			}
		}
		e.tsh_req = Account_NextId(); e.tsh_at = time; e.tsh_kind = 1;
		f = uri_get(strcat(SV_TASShareURL(), "/statement"), e.tsh_req,
			"application/json", sprintf("{\"line\":\"%s\"}", line));
		strunzone(line);
		return f;
	}
	if (e.tsh_search) search_end(e.tsh_search - 1);
	e.tsh_search = 0;
	return SV_TASShareBody(e);
};

void(entity e, string body) SV_TASShareInstall =
{
	local string tmp, dst, name, sha, why;
	local float f, ok;
	name = strzone(e.tsh_name); sha = strzone(e.tsh_sha);
	dst = strzone(SV_TASPPath(name)); tmp = strzone(strcat(dst, ".download"));
	f = fopen(dst, FILE_READ);
	if (f >= 0)
	{
		fclose(f); sprint(e, PRINT_HIGH, "tas open: that project name already exists; choose another name\n"); goto done;
	}
	f = fopen(tmp, FILE_READ);
	if (f >= 0)
	{
		fclose(f); sprint(e, PRINT_HIGH, "tas open: a staged download already exists; choose another name (existing bytes retained)\n"); goto done;
	}
	if (strlen(body) <= 0 || strlen(body) > TSH_MAXBODY)
	{
		sprint(e, PRINT_HIGH, "tas open: empty or oversized project\n"); goto done;
	}
	f = fopen(tmp, FILE_WRITE);
	if (f < 0) { sprint(e, PRINT_HIGH, "tas open: cannot stage the project\n"); goto done; }
	fputs(f, body); fclose(f);
	tpr_pathover = tmp;
	ok = SV_TASPRead(e, name, TRUE);
	tpr_pathover = "";
	why = tpr_why;
	if (ok && tpr_ver != 3) { ok = FALSE; why = "this old project needs its author's base save; only legal-start v3 projects are portable"; }
	if (ok && strcmp(tpr_h, sha)) { ok = FALSE; why = "the downloaded revision hash does not match"; }
	SV_TASPReadFree();
	if (!ok)
	{
		fremove(tmp); sprint(e, PRINT_HIGH, strcat("tas open: refused: ", why, "\n")); goto done;
	}
	// No author statement is made by downloading or opening. Keep named saves
	// and existing rev/ history intact; the ordinary loader records all playback.
	if (frename(tmp, dst) != 0)
	{
		sprint(e, PRINT_HIGH, "tas open: cannot install the project; staged bytes retained\n"); goto done;
	}
	sprint(e, PRINT_HIGH, sprintf("tas open: saved %s as %s; opening as TAS, not a ranked human run\n", substring(sha,0,12), name));
	// Parse again only on a later server frame, beyond this action's normal
	// cooldown. Two full parses in one callback exhaust QC on long tapes.
	e.tsh_loadname = strzone(name); e.tsh_loadat = time + 0.001;
	done:
	strunzone(name); strunzone(sha); strunzone(dst); strunzone(tmp);
};

float(float reqid, float code, string body) SV_TASShareReply =
{
	local entity e;
	local int root;
	local float kind, ok;
	local string note;
	for (e = world; (e = find(e, classname, "player")); )
	{
		if (!e.tsh_req || e.tsh_req != reqid) continue;
		kind = e.tsh_kind; e.tsh_req = 0;
		if (time - e.tsh_at > 30 || !SV_TASShareLocal(e))
		{
			SV_TASShareStop(e); sprint(e, PRINT_HIGH, "tas share: expired; retry explicitly\n"); return TRUE;
		}
		if (kind == 3)
		{
			if (!code) SV_TASShareInstall(e, body);
			else sprint(e, PRINT_HIGH, "tas open: download failed; no project installed\n");
			SV_TASShareStop(e); return TRUE;
		}
		root = json_parse(body); ok = FALSE; note = "directory unavailable";
		if (root > 0i)
		{
			ok = (code == 0 && json_get_float(json_find_object_child(root,"ok")) == 1);
			if (!ok) note = substring(json_get_string(json_find_object_child(root,"error")),0,160);
			if (kind == 2)
				ok = (ok && !strcmp(json_get_string(json_find_object_child(root,"sha")), e.tsh_sha));
			json_free(root);
		}
		if (!ok)
		{
			sprint(e, PRINT_HIGH, strcat("tas share: not shared: ", note, "\n")); SV_TASShareStop(e); return TRUE;
		}
		if (kind == 1)
		{
			if (!SV_TASShareNext(e))
			{
				sprint(e, PRINT_HIGH, "tas share: could not continue; revision not sent\n"); SV_TASShareStop(e);
			}
		}
		else
		{
			sprint(e, PRINT_HIGH, sprintf("tas share: shared revision %s (parents must also be shared for complete credit)\n", e.tsh_sha));
			SV_TASShareStop(e);
		}
		return TRUE;
	}
	return FALSE;
};

void(entity e, float argc) SV_TASShareCommand =
{
	local string op, sha, name;
	local float s;
	op = argv(2); sha = argv(3); name = argv(4);
	if (!SV_TASShareLocal(e)) return;
	if (e.tsh_kind && time - e.tsh_at < 30)
	{
		sprint(e, PRINT_HIGH, "tas share: a request is still in progress\n"); return;
	}
	SV_TASShareCancel(e);
	if (!strcmp(op,"share"))
	{
		if (argc != 4 || strcmp(sha,"yes"))
		{
			sprint(e, PRINT_HIGH, "tas project share yes: publicly uploads the saved revision and its existing signatures, including saved date and project metadata. Sign first for credit. No keys are uploaded.\n"); return;
		}
		s = SV_TASPSlot(e);
		if (!s) return;
		sha = tasp_revsha[s];
		if (!SV_RecIsHex(sha,64)) { sprint(e, PRINT_HIGH, "tas share: save a project revision first\n"); return; }
		e.tsh_sha = strzone(sha);
		e.tsh_search = search_begin(strcat("data/tasproj/",mapname,"/rev/",sha,".*.tasrev"), TRUE, TRUE) + 1;
		if (e.tsh_search)
		if (search_getsize(e.tsh_search - 1) > 32)
		{
			sprint(e, PRINT_HIGH, "tas share: too many statements (limit 32)\n"); SV_TASShareStop(e); return;
		}
		if (!SV_TASShareNext(e))
		{
			sprint(e, PRINT_HIGH, "tas share: cannot read this revision or start the request\n"); SV_TASShareStop(e);
		}
		return;
	}
	if (argc < 4 || argc > 5 || !SV_RecIsHex(sha,64))
	{
		sprint(e, PRINT_HIGH, "tas project open <64-digit revision> [new-name]: download a legal-start project on this map\n"); return;
	}
	if (!strcmp(name,"")) name = strcat("shared_",substring(sha,0,16));
	if (!SV_TASPNameOK(name)) { sprint(e, PRINT_HIGH, "tas open: invalid project name\n"); return; }
	e.tsh_sha = strzone(sha); e.tsh_name = strzone(name); e.tsh_kind = 3; e.tsh_at = time; e.tsh_req = Account_NextId();
	if (!uri_get(strcat(SV_TASShareURL(), "/rev/", sha, "/file"), e.tsh_req))
	{
		sprint(e, PRINT_HIGH, "tas open: request could not start\n"); SV_TASShareStop(e);
	}
};

void() SV_TASShareFrame =
{
	local entity e, oldself;
	local string name;
	oldself = self;
	for (e = world; (e = find(e, classname, "player")); )
	{
		if (e.tsh_loadname == "") continue;
		if (time < e.tsh_loadat || time < e.tasp_next) continue;
		name = e.tsh_loadname; e.tsh_loadname = ""; e.tsh_loadat = 0;
		if (SV_TASShareLocal(e))
		{
			self = e; SV_TASProjectLoad(e, name, ""); self = oldself;
		}
		strunzone(name);
	}
};
