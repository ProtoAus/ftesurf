/* Admin zone uploads. A frozen SAVED file, bound to a one-use nonce; the
 * existing account key signs a distinct purpose only under a real Enter.
 * No lobby secret, SteamID or role claim here; surfd/zonepub.py decides and,
 * for an admin, publishes (P815: lobbies time with it from their next map load). */
#define ZP_CHALLENGE 1
#define ZP_CONFIRM   2
#define ZP_UPLOAD    3
#define ZP_BASE "https://play.proto.bar/api/zones/"
float zp_state, zp_req, zp_next, zp_until, zp_count;
string zp_map, zp_body, zp_sha, zp_nonce, zp_crc;

void() ZonePub_Cancel =
{
	if (strlen(zp_map)) strunzone(zp_map);
	if (strlen(zp_body)) strunzone(zp_body);
	if (strlen(zp_sha)) strunzone(zp_sha);
	if (strlen(zp_nonce)) strunzone(zp_nonce);
	if (strlen(zp_crc)) strunzone(zp_crc);
	zp_map = zp_body = zp_sha = zp_nonce = zp_crc = "";
	zp_state = zp_req = zp_count = 0;
};

void() ZonePub_Pump =
{
	if (!zp_state) return;
	// Also when the table on screen is no longer what the prompt names.
	if (!ui_ze_state || strcmp(zp_map, serverkey("map")) != 0 || gettime(0) > zp_until
	 || ze_dirty || strcmp(zone_crc, zp_crc) != 0)
	{
		ZonePub_Cancel();
		ZoneEdit_Note("zone upload cancelled or expired; saved file unchanged");
	}
};

string() ZonePub_Line =
{
	if (zp_state == ZP_CHALLENGE) return "Requesting an admin upload confirmation...";
	if (zp_state == ZP_CONFIRM)
		return sprintf("Enter: publish %s (%g zones, crc %s) to the lobbies; Esc: cancel", zp_map, zp_count, zp_crc);
	if (zp_state == ZP_UPLOAD) return "Publishing zones...";
	return "";
};

// The bytes the saved file holds now: one read of the whole file (fgets drops a byte at
// every 4095), by its data/ path.
string() ZonePub_Saved = { return Zone_ReadFile(strcat("data/maps/zones/local/", ze_map, ".json")); };

// real: the Publish saved button's own device click (ze_real_t); a command never is.
// Only in a game this client hosts: on another server its packages can stand in for the
// saved file and its commands for the editor.
void(float real) ZonePub_Begin =
{
	local float id;
	local string body;
	ZonePub_Pump();
	if (zp_state) { ZoneEdit_Note("a zone upload is already pending"); return; }
	if (zp_next >= 6199998) { ZoneEdit_Note("restart the game before another upload"); return; }
	if (!real) { ZoneEdit_Note("click Publish saved: a command cannot start a publish"); return; }
	if (!ZoneEdit_Hosting())
	{
		ZoneEdit_Note("publish from a game you host (Play the map from the map list), not on a server"); return;
	}
	if (!ZoneFile_Map(ze_map) || strcmp(ze_map, zone_mapname) != 0)
	{
		ZoneEdit_Note("open this map's editor and use its Publish saved button"); return;
	}
	if (ze_dirty) { ZoneEdit_Note("Save zones before publishing; unsaved edits are not sent"); return; }
	if (!zone_own) { ZoneEdit_Note("Save zones first: what is on screen is not your saved file"); return; }
	if (cvar("rec_terms") < FS_TERMS_ONLINE)
	{
		ZoneEdit_Note("enable online features from the main menu before uploading"); return;
	}
	// What goes out is what is on screen: the table written once more and read back by
	// ZoneEdit_Save, then the file in place, which must be those very bytes.
	ZoneEdit_Save(TRUE);
	if (!ze_saved_ok) { ZoneEdit_Note("NOT published: the zones did not save"); return; }
	body = ZonePub_Saved();
	if (strlen(body) < 16 || strlen(body) > 262144
	 || strcmp(strtolower(digest_hex("SHA256", body)), ze_saved_sha) != 0)
	{
		ZoneEdit_Note("NOT published: the saved file does not read back as what was saved"); return;
	}
	zp_crc = strzone(zone_crc); zp_count = zone_count;
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
	// Still the file and the game the prompt was made from.
	if (!ZoneEdit_Hosting() || strcmp(strtolower(digest_hex("SHA256", ZonePub_Saved())), zp_sha) != 0)
	{
		ZonePub_Cancel(); ZoneEdit_Note("the saved file changed; nothing uploaded"); return TRUE;
	}
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
			ZoneEdit_Note("press Enter to publish the saved file to the lobbies, or Esc to cancel");
		}
		else { ZonePub_Cancel(); ZoneEdit_Note("invalid upload confirmation; nothing sent"); }
	}
	else
	{
		message = json_get_string(json_find_object_child(root, "note"));
		ZonePub_Cancel();
		if (!strlen(message)) message = "uploaded";
		ZoneEdit_Note(substring(message, 0, 160));
		print(sprintf("zone_edit: upload answered: %s\n", substring(message, 0, 160)));
	}
	if (root) json_free(root);
	return TRUE;
};
