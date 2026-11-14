// P1559: order-independent local VIEW association. Completion metadata and a
// rendered view may arrive in either order during native/held publication.
// These local files are NOT upload receipts or authoritative movement evidence.
float(string src, string dst) HV_Rename = #0:frename;
float(string path) HV_Remove = #0:fremove;
string hv_resolved;

float(string s, float limit) HV_Id =
{
	local float i, c;
	if (strlen(s) > limit) return FALSE;
	for (i = 0; i < strlen(s); i = i + 1)
	{
		c = str2chr(s, i);
		if (!(c >= 48 && c <= 57) && !(c >= 65 && c <= 90) && !(c >= 97 && c <= 122)
		    && c != 45 && c != 95 && c != 46) return FALSE;
	}
	return TRUE;
};

// World epoch and the engine connection userid are not restored with a REC
// prefix, and change on a cold map/reconnect attachment.
string() HV_Attachment =
{
	local string epoch, uid;
	epoch = serverkey("fs_historyepoch");
	uid = getplayerkeyvalue(player_localnum, "userid");
	if (strlen(epoch) != 32 || stof(uid) < 1) return "";
	return strcat(epoch, "-", uid);
};

string(string map, string profile, string rid, string nonce, string attachment) HV_Key =
{
	local string id;
	local float c;
	if (!FS_MovementProfileKnown(profile) || !HV_Id(map, 96) || !strcmp(map, "")) return "";
	if (!HV_Id(rid, 96) || !HV_Id(nonce, 32) || !HV_Id(attachment, 64)) return "";
	if (strlen(attachment) < 34 || !strcmp(rid, "")) return "";
	c = str2chr(rid, 0);
	if (!(c >= 48 && c <= 57) && !(c >= 65 && c <= 90) && !(c >= 97 && c <= 122)) return "";
	if (strlen(nonce) != 0 && strlen(nonce) != 32) return "";
	// rid carries the monotonic finish sequence, so tied restored branches do
	// not alias even when they inherited one recorder nonce and run identifier.
	if (!strcmp(rid, "")) return "";
	id = strcat("attachment:", attachment, "|runid:", rid, "|nonce:", nonce);
	return strcat("data/history-pending/", digest_hex("SHA256", "FTESurf local VIEW history v1|", map, "|", profile, "|", id));
};

string(string key) HV_Resolve =
{
	local float fh, mf, runleg, ticks, track, leg, created;
	local string map, profile, leaf, rid, nonce, attachment, dst, tmp;
	if (strcmp(hv_resolved, "")) strunzone(hv_resolved);
	hv_resolved = "";
	if (!strcmp(key, "")) return "";
	mf = fopen(strcat(key, ".meta"), FILE_READ);
	if (mf < 0) return "";
	map = strzone(fgets(mf)); profile = strzone(fgets(mf));
	attachment = strzone(fgets(mf));
	rid = strzone(fgets(mf)); nonce = strzone(fgets(mf));
	runleg = stof(fgets(mf)); ticks = stof(fgets(mf)); leaf = strzone(fgets(mf));
	fclose(mf);
	if (strcmp(key, HV_Key(map, profile, rid, nonce, attachment)) || !FS_HistoryLeaf(leaf)
	    || !(runleg >= 1 && runleg <= 6529 && runleg == floor(runleg))
	    || ticks != FS_NameTicks(leaf))
	{
		strunzone(map); strunzone(profile); strunzone(rid); strunzone(nonce); strunzone(leaf); strunzone(attachment);
		return "";
	}
	track = floor((runleg - 1) / 100); leg = runleg - 1 - track * 100;
	dst = strzone(FS_MovementProfilePath(profile,
		strcat(FS_RunDir(map, track, leg), substring(leaf, 0, strlen(leaf) - 3), "view")));
	fh = fopen(dst, FILE_READ);
	if (fh >= 0) { fclose(fh); hv_resolved = strzone(dst); } // immutable confirmed association
	else
	{
		fh = fopen(strcat(key, ".view"), FILE_READ);
		if (fh >= 0)
		{
			fclose(fh);
			// Create only the destination directory. Rename preserves every byte,
			// including a view beyond float32's exact file-size range.
			tmp = strzone(strcat(dst, ".history.part")); created = FALSE;
			fh = fopen(tmp, FILE_READ);
			if (fh >= 0) fclose(fh);
			else
			{
				fh = fopen(tmp, FILE_WRITE);
				if (fh >= 0) { fclose(fh); created = TRUE; }
			}
			if (HV_Rename(strcat(key, ".view"), dst) == 0)
			{
				hv_resolved = strzone(dst);
				HV_Remove(strcat(key, ".meta"));
			}
			else print("history: completed camera view still pending; original retained\n");
			if (created) HV_Remove(tmp);
			strunzone(tmp);
		}
	}
	strunzone(dst); strunzone(map); strunzone(profile);
	strunzone(rid); strunzone(nonce); strunzone(leaf); strunzone(attachment);
	return hv_resolved;
};

string(float view, float lines, string map, string profile, string rid, string nonce, string attachment) HV_Capture =
{
	local float fh;
	local string key, tmp, result;
	if (view < 1 || lines < 1) return "";
	result = "";
	key = strzone(HV_Key(map, profile, rid, nonce, attachment));
	if (strcmp(key, ""))
	{
		// A duplicate capture cannot silently replace an earlier pending view.
		fh = fopen(strcat(key, ".view"), FILE_READ);
		if (fh >= 0) fclose(fh);
		else
		{
			tmp = strzone(strcat(key, ".view.part"));
			fh = fopen(tmp, FILE_WRITE);
			if (fh >= 0)
			{
				buf_writefile(fh, view, 0, lines); fclose(fh);
				if (HV_Rename(tmp, strcat(key, ".view")) != 0)
					print("history: pending camera view could not be published; partial retained\n");
			}
			strunzone(tmp);
		}
		result = HV_Resolve(key);
	}
	strunzone(key);
	return result;
};

void(string leaf, string map, float runleg, float ticks, string rid, string nonce, string profile, string attachment) HV_Kept =
{
	local float fh;
	local string key, tmp;
	if (!FS_HistoryLeaf(leaf) || FS_NameTicks(leaf) != ticks) return;
	key = strzone(HV_Key(map, profile, rid, nonce, attachment));
	if (strcmp(key, ""))
	{
		tmp = strzone(strcat(key, ".meta.part"));
		fh = fopen(tmp, FILE_WRITE);
		if (fh >= 0)
		{
			fputs(fh, strcat(map, "\n", profile, "\n", attachment, "\n"));
			fputs(fh, strcat(rid, "\n", nonce, "\n"));
			fputs(fh, sprintf("%d\n%d\n%s\n", runleg, ticks, leaf));
			fclose(fh);
			// Existing pending association remains immutable, including ties.
			fh = fopen(strcat(key, ".meta"), FILE_READ);
			if (fh >= 0) { fclose(fh); HV_Remove(tmp); }
			else HV_Rename(tmp, strcat(key, ".meta"));
		}
		strunzone(tmp); HV_Resolve(key);
	}
	strunzone(key);
};
