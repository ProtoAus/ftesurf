/* Admin zone drafts. A frozen SAVED file, bound to a one-use nonce; the
 * existing account key signs a distinct purpose only under a real Enter.
 * No lobby secret, SteamID, role claim, live-zone write or activation here. */
#define ZP_CHALLENGE 1
#define ZP_CONFIRM   2
#define ZP_UPLOAD    3
#define ZP_BASE "https://play.proto.bar/api/zones/"
float zp_state, zp_req, zp_next, zp_until;
string zp_map, zp_body, zp_sha, zp_nonce;

void() ZonePub_Cancel =
{
	if (strlen(zp_map)) strunzone(zp_map);
	if (strlen(zp_body)) strunzone(zp_body);
	if (strlen(zp_sha)) strunzone(zp_sha);
	if (strlen(zp_nonce)) strunzone(zp_nonce);
	zp_map = zp_body = zp_sha = zp_nonce = "";
	zp_state = zp_req = 0;
};

void() ZonePub_Pump =
{
	if (!zp_state) return;
	if (!ui_ze_state || strcmp(zp_map, serverkey("map")) != 0 || gettime(0) > zp_until)
	{
		ZonePub_Cancel();
		ZoneEdit_Note("zone upload cancelled or expired; saved file unchanged");
	}
};

string() ZonePub_Line =
{
	if (zp_state == ZP_CHALLENGE) return "Requesting an admin draft confirmation...";
	if (zp_state == ZP_CONFIRM) return "Enter: upload SAVED zones as an admin draft; Esc: cancel";
	if (zp_state == ZP_UPLOAD) return "Uploading admin draft (this does not activate zones)...";
	return "";
};

void() ZonePub_Begin =
{
	local float f, id;
	local string s, body;
	ZonePub_Pump();
	if (zp_state) { ZoneEdit_Note("a zone upload is already pending"); return; }
	if (zp_next >= 6199998) { ZoneEdit_Note("restart the game before another upload"); return; }
	if (!ZoneEdit_MayWrite() || !ZoneFile_Map(ze_map) || strcmp(ze_map, zone_mapname) != 0)
	{
		ZoneEdit_Note("open this map's editor and use its Upload saved button"); return;
	}
	if (ze_dirty) { ZoneEdit_Note("Save zones before uploading; unsaved edits are not sent"); return; }
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
	{
		ZoneEdit_Note("enable online features from the main menu before uploading"); return;
	}
	f = fopen(strcat("maps/zones/local/", ze_map, ".json"), FILE_READ);
	if (f < 0) { ZoneEdit_Note("Save zones first: no saved local zone file"); return; }
	body = "";
	while ((s = fgets(f)))
	{
		body = strcat(body, s, "\n");
		if (strlen(body) > 262144) break;
	}
	fclose(f);
	if (strlen(body) < 16 || strlen(body) > 262144)
	{
		ZoneEdit_Note("saved zone file is empty or too large; nothing uploaded"); return;
	}
	zp_map = strzone(ze_map); zp_body = strzone(body);
	zp_sha = strzone(strtolower(digest_hex("SHA256", body)));
	zp_state = ZP_CHALLENGE; zp_until = gettime(0) + 120;
	zp_next = max(zp_next + 1, 6100000); zp_req = id = zp_next;
	if (!uri_post(strcat(ZP_BASE, "challenge"), id, "application/json",
	              sprintf("{\"map\":\"%s\",\"sha\":\"%s\"}", zp_map, zp_sha)))
	{
		ZonePub_Cancel(); ZoneEdit_Note("zone upload service could not be reached");
	}
};

float(float scan) ZonePub_Confirm =
{
	local string p, envelope;
	ZonePub_Pump();
	if (zp_state != ZP_CONFIRM) return FALSE;
	if (scan == K_ESCAPE)
	{
		ZonePub_Cancel(); ZoneEdit_Note("zone upload cancelled"); return TRUE;
	}
	if (scan != K_ENTER && scan != K_KP_ENTER) return FALSE;
	// Engine proof signing separately enforces a real, non-repeated device key.
	if (!cl_input_real) return TRUE;
	p = acct_sign(zp_nonce, -6);
	if (!strlen(p))
	{
		ZonePub_Cancel(); ZoneEdit_Note("update the engine, then confirm with a real Enter key"); return TRUE;
	}
	if (tokenize(p) != 5)
	{
		ZonePub_Cancel(); ZoneEdit_Note("could not form an account proof"); return TRUE;
	}
	// Raw JSON preserves the exact frozen bytes whose SHA256 the nonce names.
	// No uri_escape/sprintf of the large file (both have small output bounds).
	envelope = sprintf("{\"nonce\":\"%s\",\"pub\":\"%s\",\"sig\":\"%s\",\"game\":\"%s\",\"zones\":",
	                   zp_nonce, argv(0), argv(2), argv(4));
	envelope = strcat(envelope, zp_body, "}");
	zp_state = ZP_UPLOAD; zp_until = gettime(0) + 120;
	zp_next = zp_next + 1; zp_req = zp_next;
	if (!uri_post(strcat(ZP_BASE, "draft"), zp_req, "application/json", envelope))
	{
		ZonePub_Cancel(); ZoneEdit_Note("zone upload service could not be reached");
	}
	return TRUE;
};

float(float id, float code, string body) ZonePub_Reply =
{
	local int root;
	local string nonce, message;
	if (id < 6100000 || id >= 6200000) return FALSE;
	if (!zp_state || id != zp_req) return TRUE;
	ZonePub_Pump();
	if (!zp_state) return TRUE;
	zp_req = 0;
	root = json_parse(body);
	if ((code != 0 && code != 200) || !json_get_float(json_find_object_child(root, "ok")))
	{
		message = json_get_string(json_find_object_child(root, "error"));
		if (!strlen(message)) message = "zone upload unavailable; saved file unchanged";
		ZoneEdit_Note(substring(message, 0, 160));
		if (root) json_free(root);
		ZonePub_Cancel(); return TRUE;
	}
	if (zp_state == ZP_CHALLENGE)
	{
		nonce = json_get_string(json_find_object_child(root, "nonce"));
		if (strlen(nonce) == 32
		 && strcmp(json_get_string(json_find_object_child(root, "map")), zp_map) == 0
		 && strcmp(json_get_string(json_find_object_child(root, "sha")), zp_sha) == 0)
		{
			zp_nonce = strzone(nonce); zp_state = ZP_CONFIRM;
			ZoneEdit_Note("press Enter to upload the saved file as an admin draft, or Esc to cancel");
		}
		else { ZonePub_Cancel(); ZoneEdit_Note("invalid upload confirmation; nothing sent"); }
	}
	else
	{
		ZonePub_Cancel();
		ZoneEdit_Note("saved as an admin draft; review and activation are still required");
	}
	if (root) json_free(root);
	return TRUE;
};
