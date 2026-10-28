/* Admin zone uploads. A frozen SAVED file, bound to a one-use nonce; the
 * existing account key signs a distinct purpose only under a real press (P822:
 * the dialog's Publish click, or Enter, inside the engine's own key event).
 * No lobby secret, SteamID or role claim here; surfd/zonepub.py decides and,
 * for an admin, publishes (P815: lobbies time with it from their next map load).
 * P1081: also from a lobby (ZonePub_Offhost), opened by `zone_edit publish`, and
 * "Reload now" signs a second nonce that has the service reload the map's lobbies. */
#define ZP_CHALLENGE 1
#define ZP_CONFIRM   2
#define ZP_UPLOAD    3
#define ZP_DONE      4   // the service's answer, on screen until OK
#define ZP_BASE "https://play.proto.bar/api/zones/"
float zp_state, zp_req, zp_next, zp_until, zp_count, zp_bad, zp_live, zp_shown;
float zp_cap;                       // P841: the saved file's maxVelocity, 0 = not set
float zp_bycmd;                     // P1081: a command opened it: only a click on a button sends
float zp_armed;                     // P1081: presses before this (the page's first 0.6 s) are ignored
string zp_map, zp_body, zp_sha, zp_nonce, zp_crc, zp_said;
string zp_nonce_now;                // P1081: the service's second nonce, "reload now"
vector zp_go_p, zp_go_s, zp_no_p, zp_no_s;   // the dialog's buttons as last drawn; a zero size is no button
vector zp_now_p, zp_now_s;
vector zp_geo_go, zp_geo_size, zp_geo_now, zp_geo_no;  // P1081: the buttons as last drawn, to see them move
float zp_out_go, zp_out_now;        // P1081 round 3: the device pointer was outside that button since arming

void() ZonePub_Cancel =
{
	if (strlen(zp_map)) strunzone(zp_map);
	if (strlen(zp_body)) strunzone(zp_body);
	if (strlen(zp_sha)) strunzone(zp_sha);
	if (strlen(zp_nonce)) strunzone(zp_nonce);
	if (strlen(zp_nonce_now)) strunzone(zp_nonce_now);
	if (strlen(zp_crc)) strunzone(zp_crc);
	if (strlen(zp_said)) strunzone(zp_said);
	zp_map = zp_body = zp_sha = zp_nonce = zp_nonce_now = zp_crc = zp_said = "";
	zp_state = zp_req = zp_count = zp_bad = zp_live = zp_cap = zp_bycmd = zp_armed = 0;
	zp_shown = -1;                  // P1081 review: no page counts as drawn until it is drawn again
	zp_go_s = zp_no_s = zp_now_s = '0 0 0';
};

// The dialog's last page: what the service said (or why nothing went).
void(string said, float bad, float live) ZonePub_Answer =
{
	local string map, crc;
	local float n, cap;
	map = strzone(zp_map); crc = strzone(zp_crc); n = zp_count; cap = zp_cap;
	ZonePub_Cancel();
	zp_map = map; zp_crc = crc; zp_count = n; zp_cap = cap;
	zp_said = strzone(said); zp_bad = bad; zp_live = live;
	zp_state = ZP_DONE;
};

void() ZonePub_Pump =
{
	if (!zp_state) return;
	// The dialog is drawn only on the panel with the cursor up. Anywhere else it is not on
	// screen, and a press meant for the editor (Enter closes a polygon) must not publish.
	if (zp_state == ZP_DONE)
	{
		if (ui_ze_state != ZE_PANEL || strcmp(zp_map, serverkey("map")) != 0) ZonePub_Cancel();
		return;
	}
	// Sent: nothing here changes what went, so only its answer or its silence ends it.
	if (zp_state == ZP_UPLOAD)
	{
		if (gettime(0) > zp_until)
			ZonePub_Answer("No answer from the zone service. The upload may still have arrived; "
			               "check before publishing again.", TRUE, FALSE);
		return;
	}
	// Also when the table on screen is no longer what the dialog names.
	if (ui_ze_state != ZE_PANEL || ze_settings || !ze_cursor
	 || strcmp(zp_map, serverkey("map")) != 0 || gettime(0) > zp_until
	 || ze_dirty || strcmp(zone_crc, zp_crc) != 0)
	{
		ZonePub_Cancel();
		ZoneEdit_Note("zone upload cancelled or expired; saved file unchanged");
	}
};

// The bytes the saved file holds now: one read of the whole file (fgets drops a byte at
// every 4095), by its data/ path.
string() ZonePub_Saved = { return Zone_ReadFile(strcat("data/maps/zones/local/", ze_map, ".json")); };

/* P1081: publishing on a server this client does not host. Its packages could stand in for
 * the saved file and its commands for the editor, so: no table a `zone_edit` command changed
 * here (zone_cmd_taint; such a table cannot be saved here either), and the saved file must
 * resolve loose, ours, not from a package. The signer's csprogs is checked by the service. */
string() ZonePub_Offhost =
{
	local string path;
	if (isdemo()) return "publish from a game, not a demo";
	if (ZoneEdit_Hosting()) return "";
	if (zone_cmd_taint) return "a console command changed these zones on this server: Reload, edit with the panel, save";
	if (zone_base_untrusted) return "these zones came from this server's map or packages: publish them from a game you host";
	path = strcat("data/maps/zones/local/", ze_map, ".json");
	dprint(sprintf("zone_edit: saved file at %s\n", whichpack(path, 2)));
	if (!Zone_LooseOwn(path)) return "your saved file is not a loose file of this game's own";
	return "";
};

// P1081: the server's address as this client's netchan has it, kept to address characters
// (it goes into hand-built JSON). Loopback, unspecified, link-local and private addresses are
// this client's own network -- a local server or relay on a lobby port -- never one of our
// lobbies, so they go as "unknown", which the service refuses (as it refuses them itself).
string() ZonePub_Where =
{
	local string ip, host;
	local float i, second, first, next;
	ip = serverkey("ip");
	if (strlen(ip) < 3 || strlen(ip) > 64) return "unknown";
	for (i = 0; i < strlen(ip); i = i + 1)
		if (strstrofs("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.:[]-_",
		              substring(ip, i, 1), 0) < 0) return "unknown";
	host = strtolower(ip);
	first = strstrofs(host, ":", 0);
	next = (first >= 0) ? strstrofs(host, ":", first + 1) : -1;
	if (strcmp(substring(host, 0, 1), "[") == 0)
		host = substring(host, 1, max(0, strstrofs(host, "]", 0) - 1));    // [v6]:port
	else if (first >= 0 && next < 0)
		host = substring(host, 0, first);                                   // v4:port or name:port
	second = stof(substring(host, 4, 3));                                   // 172.<second>.
	if (strcmp(substring(host, 0, 4), "127.") == 0 || strcmp(substring(host, 0, 2), "0.") == 0
	 || strcmp(substring(host, 0, 3), "10.") == 0 || strcmp(substring(host, 0, 8), "192.168.") == 0
	 || strcmp(substring(host, 0, 8), "169.254.") == 0
	 || (strcmp(substring(host, 0, 4), "172.") == 0 && second >= 16 && second <= 31)
	 || strcmp(host, "::1") == 0 || strcmp(host, "::") == 0 || strcmp(host, "localhost") == 0
	 || strcmp(substring(host, 0, 2), "fc") == 0 || strcmp(substring(host, 0, 2), "fd") == 0
	 || strcmp(substring(host, 0, 4), "fe80") == 0 || strstrofs(host, "qloopback", 0) >= 0)
		return "unknown";
	return ip;
};

// P1081: the saved file, loaded over the table, gives back the same count, crc and speed cap.
float() ZonePub_Matches =
{
	local string was;
	local float n, mv, ok, same;
	was = strzone(zone_crc); n = zone_count; mv = zone_maxvel;
	ok = Zone_LoadJson(strcat("data/maps/zones/local/", ze_map, ".json"), ZSRC_LOCAL);
	if (ok) Zone_Hash();
	same = (ok && zone_count == n && strcmp(zone_crc, was) == 0 && zone_maxvel == mv);
	strunzone(was);
	if (!ok)
	{
		zone_mapname = "";           // the loader may have emptied the table: read the map again
		Zone_LoadForMap();
		ze_sel = -1;
	}
	return same;
};

// real: the Publish saved button's own device click (ze_real_t). `zone_edit publish` opens
// the same dialog (P1081), and then only a click on one of its buttons sends.
void(float real) ZonePub_Begin =
{
	local float id;
	local string body, why;
	ZonePub_Pump();
	if (zp_state) { ZoneEdit_Note("a zone upload is already pending"); return; }
	if (ui_ze_state != ZE_PANEL || ze_settings) { ZoneEdit_Note("finish placing first"); return; }
	if (zp_next >= 6199998) { ZoneEdit_Note("restart the game before another upload"); return; }
	if (isdemo() || ((zone_cmd_taint || zone_base_untrusted) && !ZoneEdit_Hosting()))
	{
		ZoneEdit_Note(ZonePub_Offhost()); return;
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
	// ZoneEdit_Save, then the file in place, which must be those very bytes. Only the
	// button's own click writes: a command-opened publish never saves (P1081 review).
	if (real && ZoneEdit_MayWrite())
	{
		ZoneEdit_Save(TRUE);
		if (!ze_saved_ok) { ZoneEdit_Note("NOT published: the zones did not save"); return; }
		body = ZonePub_Saved();
		if (strlen(body) < 16 || strlen(body) > 262144
		 || strcmp(strtolower(digest_hex("SHA256", body)), ze_saved_sha) != 0)
		{
			ZoneEdit_Note("NOT published: the saved file does not read back as what was saved"); return;
		}
	}
	else
	{
		// P1081: no write allowed (a command, or off-host without a click), so the saved file must
		// already be the table on screen: read it back into the table, as Save checks its .part.
		if (ze_dirty || !zone_own) { ZoneEdit_Note("Save zones with the panel first; a command does not save"); return; }
		why = ZonePub_Offhost();        // provenance before the file is loaded over the table
		if (strlen(why)) { ZoneEdit_Note(strcat("NOT published: ", why)); return; }
		body = ZonePub_Saved();
		if (strlen(body) < 16 || strlen(body) > 262144 || !ZonePub_Matches())
		{
			ZoneEdit_Note("NOT published: the saved file is not the zones on screen"); return;
		}
	}
	why = ZonePub_Offhost();
	if (strlen(why)) { ZoneEdit_Note(strcat("NOT published: ", why)); return; }
	zp_bycmd = !real;
	zp_crc = strzone(zone_crc); zp_count = zone_count; zp_cap = zone_maxvel;
	zp_map = strzone(ze_map); zp_body = strzone(body);
	zp_sha = strzone(strtolower(digest_hex("SHA256", body)));
	zp_state = ZP_CHALLENGE; zp_until = gettime(0) + 120;
	// A map change restarts this VM's counter and the engine hands a late reply to the new
	// VM, so ids start somewhere else each time (review: an old answer shown as the new one).
	if (zp_next < 6100000) zp_next = 6100000 + floor(random() * 80000);
	zp_next = zp_next + 1; zp_req = id = zp_next;
	print(sprintf("zone_edit: publish dialog open for %s (%g zones, crc %s, speed cap %g)\n", zp_map, zp_count, zp_crc, zp_cap));
	// P1081: where this client is, as its own netchan says (a server cannot set it); the
	// service accepts off-host publishing only from its own lobbies.
	if (!uri_post(strcat(ZP_BASE, "challenge"), id, "application/json",
	              sprintf("{\"map\":\"%s\",\"sha\":\"%s\",\"server\":\"%s\"}", zp_map, zp_sha,
	                      ZoneEdit_Hosting() ? "host" : ZonePub_Where())))
		ZonePub_Answer("The zone upload service could not be reached. Nothing was sent.", TRUE, FALSE);
};

// Publish's press, Enter's or the click's. The engine signs only while a device's key
// event is being delivered (CSQC_RealKey), so a command or a frame never gets here signed.
// now: the "Reload now" button, which signs the service's second nonce (P1081).
void(float now) ZonePub_Send =
{
	local string p, envelope, why;
	if (zp_state != ZP_CONFIRM) return;
	if (!cl_input_real) { ZoneEdit_Note("click Publish: a command cannot start a publish"); return; }
	if (now && strlen(zp_nonce_now) != 32) return;
	// Still the file and the game the dialog was made from.
	why = ZonePub_Offhost();
	if (strlen(why)) { ZonePub_Answer(strcat(why, ". Nothing was sent."), TRUE, FALSE); return; }
	if (strcmp(strtolower(digest_hex("SHA256", ZonePub_Saved())), zp_sha) != 0)
	{
		ZonePub_Answer("The saved file changed. Nothing was sent.", TRUE, FALSE); return;
	}
	p = acct_sign(now ? zp_nonce_now : zp_nonce, -6);
	if (!strlen(p))
	{
		ZonePub_Answer("The game would not sign the upload: it needs a linked Steam account, "
		               "the latest engine and a real click or key. Nothing was sent.", TRUE, FALSE);
		return;
	}
	if (tokenize(p) != 5) { ZonePub_Answer("Could not form an account proof. Nothing was sent.", TRUE, FALSE); return; }
	// Raw JSON preserves the exact frozen bytes whose SHA256 the nonce names.
	// No uri_escape/sprintf of the large file (both have small output bounds).
	envelope = sprintf("{\"nonce\":\"%s\",\"pub\":\"%s\",\"sig\":\"%s\",\"game\":\"%s\",\"zones\":",
	                   now ? zp_nonce_now : zp_nonce, argv(0), argv(2), argv(4));
	envelope = strcat(envelope, zp_body, "}");
	zp_state = ZP_UPLOAD; zp_until = gettime(0) + 120;
	zp_next = zp_next + 1; zp_req = zp_next;
	if (!uri_post(strcat(ZP_BASE, "draft"), zp_req, "application/json", envelope))
		ZonePub_Answer("The zone upload service could not be reached. Nothing was sent.", TRUE, FALSE);
	else print("zone_edit: upload sent, signed under a real press\n");
};

void(float now) ZonePub_Go =
{
	if (zp_shown != zp_state) return;     // a reply lands between frames: act on the page drawn
	if (zp_state == ZP_CONFIRM) { if (zp_armed > 0 && gettime(0) >= zp_armed) ZonePub_Send(now); }
	else if (zp_state == ZP_DONE && !now) ZonePub_Cancel();
};

// An upload in flight is not withdrawn: the service may already have it.
void() ZonePub_Back =
{
	if (zp_state == ZP_DONE) ZonePub_Cancel();
	else if (zp_state == ZP_CHALLENGE || zp_state == ZP_CONFIRM)
	{
		ZonePub_Cancel(); ZoneEdit_Note("zone upload cancelled; nothing sent");
	}
};

// Modal while open: its keys and every mouse button are its own, other keys pass.
// The click acts on the press, the only moment the engine will sign.
float(float scan) ZonePub_Key =
{
	local vector at;
	local float seen, entered;
	ZonePub_Pump();
	if (!zp_state) return FALSE;
	if (ui_ze_state != ZE_PANEL || !ze_cursor) return FALSE;   // not on screen: the editor's keys
	if (scan == K_ESCAPE) { ZonePub_Back(); return TRUE; }
	if (scan == K_ENTER || scan == K_KP_ENTER)
	{
		// P1081: a dialog a command opened is confirmed by a click on its button, never Enter.
		if (zp_bycmd && zp_state == ZP_CONFIRM) ZoneEdit_Note("click Publish or Reload now: Enter does not confirm here");
		else ZonePub_Go(FALSE);
		return TRUE;
	}
	if (scan == K_MOUSE1)
	{
		// P1081 review: a real press lands where the DEVICE put the pointer (cl_main.qc records it
		// before any panel takes the move), and on a confirm page only after it moved there once the
		// page armed. chat_mouse and hud_edit move ze_mouse with no device; such a press can only
		// cancel, as Send refuses it.
		at = cl_input_real ? cl_ptr_real : ze_mouse;
		seen = cl_input_real ? cl_ptr_real_ok : ze_mouse_seen;
		if (cl_input_real && zp_state == ZP_CONFIRM && (zp_armed <= 0 || cl_ptr_real_t < zp_armed)) seen = FALSE;
		entered = !(cl_input_real && zp_state == ZP_CONFIRM);          // an entry is asked of real presses
		if (seen && is_2dpoint_in_bbox(at, zp_go_p, zp_go_s)) { if (entered || zp_out_go) ZonePub_Go(FALSE); }
		else if (seen && is_2dpoint_in_bbox(at, zp_now_p, zp_now_s)) { if (entered || zp_out_now) ZonePub_Go(TRUE); }
		else if (seen && is_2dpoint_in_bbox(at, zp_no_p, zp_no_s)) ZonePub_Back();
		return TRUE;
	}
	return (scan == K_MOUSE2 || scan == K_MOUSE3);
};

// Greedy word wrap; draw FALSE only measures. Returns the y under the last line.
float(vector at, float w, float sz, string s, vector col, float draw) ZonePub_Wrap =
{
	local float k, e, n;
	local string line, word, next;
	n = strlen(s);
	line = "";
	for (k = 0; k < n; k = e + 1)
	{
		e = strstrofs(s, " ", k);
		if (e < 0) e = n;
		word = substring(s, k, e - k);
		next = strlen(line) ? strcat(line, " ", word) : word;
		if (strlen(line) && stringwidth(next, TRUE, [sz, sz]) > w)
		{
			if (draw) sui_text(at, [sz, sz], line, col, 1, 0);
			at_y = at_y + sz + 3;
			line = word;
		}
		else line = next;
	}
	if (strlen(line))
	{
		if (draw) sui_text(at, [sz, sz], line, col, 1, 0);
		at_y = at_y + sz + 3;
	}
	return at_y;
};

// One button; hovered from SUI (registered above the blocker), clicked in ZonePub_Key.
// primary: 1 the default action, 2 the disruptive one (P1081 Reload now, warning colours).
void(vector p, vector s, string id, string word, float sz, float primary, float live) ZonePub_Button =
{
	local float w;
	local vector col;
	if (live) sui_action_element(p, s, id, sui_noop);
	if (!live) sui_style_box(p, s, 4, SUI_THEME_WELL, SUI_THEME_EDGE, 1);
	else if (primary == 2)
		sui_style_box(p, s, 4, sui_is_hovered(id) ? SUI_THEME_HOVER : SUI_THEME_WELL, SUI_THEME_WARN, 1);
	else if (primary)
		sui_style_box(p, s, 4, sui_is_hovered(id) ? SUI_THEME_PRESSED : SUI_THEME_SELECTED, SUI_THEME_EDGE_HI, 1);
	else sui_style_box(p, s, 4, sui_is_hovered(id) ? SUI_THEME_HOVER : SUI_THEME_CHIP, SUI_THEME_EDGE, 1);
	col = !live ? SUI_THEME_MUTED : (primary == 2 ? SUI_THEME_WARN : (primary ? SUI_THEME_ACCENT : SUI_THEME_TEXT));
	w = stringwidth(word, TRUE, [sz, sz]);
	sui_text(p + [(s_x - w) * 0.5, (s_y - sz) * 0.5], [sz, sz], word, col, 1, 0);
};

// Drawn inside ZoneEdit_Panel's sui bracket, after the panel, so it is on top.
void(vector scr) ZonePub_Draw =
{
	local vector p, s, tp, gp, np, bs;
	local float w, pad, tsz, rsz, bh, h, y;
	local string title, head, body, go;

	ZonePub_Pump();
	zp_go_s = zp_no_s = zp_now_s = '0 0 0';
	if (!zp_state && zp_shown) print("zone_edit: publish dialog closed\n");
	if (!zp_state)
	{
		zp_shown = 0;
		if (strcmp(substring(ze_press, 0, 3), "zp_") == 0) { strunzone(ze_press); ze_press = ""; }
		return;
	}
	pad = 12 * ui_cv_scale;
	tsz = Font_Px(11 * ui_cv_scale);
	rsz = Font_Px(8 * ui_cv_scale);
	bh = rsz + 12 * ui_cv_scale;
	w = min(scr_x - 32, (strlen(zp_nonce_now) ? 460 : 380) * ui_cv_scale);

	head = sprintf("%s  /  %g zones  /  crc %s", zp_map, zp_count, zp_crc);
	go = "Publish";
	if (zp_state == ZP_DONE)
	{
		title = zp_bad ? "Not published" : (zp_live ? "Zones published" : "Zones accepted");
		body = zp_said; go = "OK";
	}
	else
	{
		title = "Publish zones to the lobbies?";
		if (zp_state == ZP_CHALLENGE) body = "Asking the zone service...";
		else if (zp_state == ZP_UPLOAD) { body = "Publishing..."; go = "Publishing"; }
		else body = sprintf("Your saved file goes to every lobby. They switch to it once none of them has "
		                    "had %s loaded for 10 minutes and its runs are verified. Existing times stay. %s", zp_map,
		                    zp_cap > 0 ? sprintf("Speed cap %g goes with it.", zp_cap) : "It sets no speed cap.");
		if (zp_state == ZP_CONFIRM && strlen(zp_nonce_now))
			body = strcat(body, " Reload now: Lobbies on it are warned, then reload with these zones once its runs "
			              "are verified, usually within 10 minutes; runs in progress there end.");
	}

	// Measure, then draw: the box fits what it says.
	h = pad + tsz + 6 + rsz + 3 + pad * 0.75;
	h = ZonePub_Wrap([0, h], w - pad * 2, rsz, body, SUI_THEME_TEXT, FALSE);
	h = h + pad * 0.75 + bh + pad;
	p = [(scr_x - w) * 0.5, (scr_y - h) * 0.5, 0];
	s = [w, h, 0];

	sui_action_element('0 0 0', scr, "zp_block", sui_noop);   // nothing under the dialog hovers
	drawfill('0 0 0', scr, '0 0 0', 0.45, 0);
	sui_action_element(p, s, "zp_bg", sui_noop);
	sui_style_panel(p, s, 8, 1);

	tp = p + [pad, pad];
	sui_text(tp, [tsz, tsz], title, zp_bad ? SUI_THEME_BAD : SUI_THEME_TEXT, 1, 0);
	tp_y = tp_y + tsz + 6;
	sui_text(tp, [rsz, rsz], head, SUI_THEME_DIM, 1, 0);
	tp_y = tp_y + rsz + 3 + pad * 0.75;
	y = ZonePub_Wrap(tp, w - pad * 2, rsz, body, (zp_state == ZP_CONFIRM || zp_state == ZP_DONE) ? SUI_THEME_TEXT : SUI_THEME_DIM, TRUE);

	bs = [max(stringwidth("Publishing", TRUE, [rsz, rsz]) + 28 * ui_cv_scale, 96 * ui_cv_scale), bh, 0];
	gp = [p_x + w - pad - bs_x, p_y + h - pad - bh, 0];
	np = gp - [bs_x + 8 * ui_cv_scale, 0, 0];
	ZonePub_Button(gp, bs, "zp_go", go, rsz, TRUE, zp_state == ZP_CONFIRM || zp_state == ZP_DONE);
	if (zp_state == ZP_CONFIRM || zp_state == ZP_DONE) { zp_go_p = gp; zp_go_s = bs; }
	if (zp_state == ZP_CHALLENGE || zp_state == ZP_CONFIRM)
	{
		ZonePub_Button(np, bs, "zp_no", "Cancel", rsz, FALSE, TRUE);     // P815's place, unchanged
		zp_no_p = np; zp_no_s = bs;
	}
	if (zp_state == ZP_CONFIRM && strlen(zp_nonce_now))
	{
		// P1081: the disruptive choice at the far left, away from Cancel, a click only (ZonePub_Key).
		tp = [p_x + pad, gp_y, 0];
		ZonePub_Button(tp, bs, "zp_now", "Reload now", rsz, 2, TRUE);
		zp_now_p = tp; zp_now_s = bs;
	}
	else if (zp_state == ZP_CONFIRM)
		sui_text([p_x + pad, gp_y + (bh - rsz) * 0.5], [rsz, rsz], zp_bycmd ? "click to confirm" : "Enter / Esc",
		         SUI_THEME_MUTED, 1, 0);

	// P1081 review: buttons that moved (hud_scale, a resize) under a resting pointer arm again.
	if (zp_state == ZP_CONFIRM && zp_shown == zp_state)
	if (zp_go_p != zp_geo_go || zp_go_s != zp_geo_size || zp_now_p != zp_geo_now || zp_no_p != zp_geo_no)
	{
		zp_armed = gettime(0) + 0.6;
		zp_out_go = zp_out_now = FALSE;
	}
	zp_geo_go = zp_go_p; zp_geo_size = zp_go_s; zp_geo_now = zp_now_p; zp_geo_no = zp_no_p;

	// Where it is, once a page: an arm clicks by these (developer 1).
	if (zp_shown != zp_state)
	{
		if (zp_state == ZP_CONFIRM)
		{
			zp_armed = gettime(0) + 0.6;    // P1081: no press carried in from before
			zp_out_go = zp_out_now = FALSE;
		}
		dprint(sprintf("zone_edit: publish dialog page %g, screen %v, go %v %v, cancel %v %v",
		               zp_state, scr, zp_go_p, zp_go_s, zp_no_p, zp_no_s));
		dprint(sprintf(", now %v %v\n", zp_now_p, zp_now_s));
	}
	zp_shown = zp_state;
	// P1081 round 3: Publish or Reload now counts a press only once the device pointer has been
	// outside it since arming -- a delta queued at a resting pointer (in_journal_synth) is no entry.
	if (zp_state == ZP_CONFIRM && cl_ptr_real_ok)
	{
		if (!is_2dpoint_in_bbox(cl_ptr_real, zp_go_p, zp_go_s)) zp_out_go = TRUE;
		if (!is_2dpoint_in_bbox(cl_ptr_real, zp_now_p, zp_now_s)) zp_out_now = TRUE;
	}

	// `zone_edit press zp_go|zp_now|zp_no` for arms: Back works, Go reaches Send, which refuses a command.
	if (ZoneEdit_Clicked("zp_no")) ZonePub_Back();
	else if (ZoneEdit_Clicked("zp_go")) ZonePub_Go(FALSE);
	else if (ZoneEdit_Clicked("zp_now")) ZonePub_Go(TRUE);
};

// A non-200 reply reaches QC with no body (httpclient.c keeps no file), so zonepub.py answers
// its refusals 200 with ok=0 and the reason (P826). These words are for what never gets that
// far: nginx's own 413, a 502 while the service restarts, a service older than P826.
string(float code) ZonePub_Refused =
{
	if (code == 403) return "Refused: update the game, link your Steam account, or ask for the zone-admin role.";
	if (code == 409) return "The confirmation expired or the saved file changed. Try again.";
	if (code == 429) return "Too many uploads for now. Try again later.";
	if (code == 400 || code == 413) return "The zone service refused this file.";
	if (code == 500) return "The zone service failed on this upload. Ask an operator to look.";
	return "Zone uploads are unavailable right now; your saved file is unchanged";
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
		if (!strlen(message)) message = ZonePub_Refused(code);
		message = substring(message, 0, 160);
		print(sprintf("zone_edit: upload answered: %s\n", message));
		if (root) json_free(root);
		ZonePub_Answer(message, TRUE, FALSE); return TRUE;
	}
	if (zp_state == ZP_CHALLENGE)
	{
		nonce = json_get_string(json_find_object_child(root, "nonce"));
		if (strlen(nonce) == 32
		 && strcmp(json_get_string(json_find_object_child(root, "map")), zp_map) == 0
		 && strcmp(json_get_string(json_find_object_child(root, "sha")), zp_sha) == 0)
		{
			zp_nonce = strzone(nonce); zp_state = ZP_CONFIRM;
			nonce = json_get_string(json_find_object_child(root, "nonce_now"));
			if (strlen(nonce) == 32 && strcmp(nonce, zp_nonce) != 0) zp_nonce_now = strzone(nonce);
			print(sprintf("zone_edit: publish dialog waiting for Publish%s or Cancel%s\n",
			              strlen(zp_nonce_now) ? ", Reload now" : "", zp_bycmd ? " (opened by command)" : ""));
		}
		else ZonePub_Answer("The zone service's confirmation did not match this file. Nothing was sent.", TRUE, FALSE);
	}
	else
	{
		message = json_get_string(json_find_object_child(root, "note"));
		if (!strlen(message)) message = "uploaded";
		message = substring(message, 0, 160);
		print(sprintf("zone_edit: upload answered: %s\n", message));
		ZonePub_Answer(message, FALSE, json_get_float(json_find_object_child(root, "published")));
	}
	if (root) json_free(root);
	return TRUE;
};
