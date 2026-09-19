/*
===========================================================================
  cl_players.qc -- "who is in this server", beside the leaderboard.  Patch 340.

  DRAWN INSIDE THE SCOREBOARD'S OWN sui BRACKET, and that is structural, not
  tidiness: sui has ONE hit-test list and ONE input buffer, sui_begin empties
  the list and sui_end clears the buffer, so a second bracket in the same
  frame draws buttons that are dead on arrival (cl_main.qc's Ev_Panel comment
  is the long version, and the reason the editor refuses to coexist with
  anything).  Scores_Draw therefore calls Players_Panel(bp, bsz, pad, scr)
  before its own sui_end, with the rect it just computed -- this file
  compiles BEFORE cl_scores.qc so that call needs no forward declaration.

  WHERE IT SITS: to the right of the board when the window has room (the
  board clamps to >= 50% of the screen and centres, so a 16:9 window always
  has some), and docked over the board's right edge when it does not.  A
  panel that moved the leaderboard would fight the layout the board's own
  essay derives character by character.

  THE ROWS come from getplayerkeyvalue(playernum, ...) -- the engine's own
  scoreboard source (cl_defs.qc:1670: name, frags, ping, pl, userid,
  voipspeaking and the rest).  Slot order, which is join order, not rank:
  this is a room list, not a board.

  TWO MUTES, because they are two different systems:
    voice  cl_voip_mute / cl_voip_unmute, engine commands, state readable
           back as the `vignored` infokey (INFOKEY_P_VOIP_MUTED).
    chat   cl_chat.qc's silence list.  The engine's own `ignore` cannot back
           this: its list is not readable from QC, and a toggle button that
           cannot show its own state is a lie waiting to happen.  Silence
           filters the chatbox hook AND the console echo (see cl_chat.qc).

  A ROW CLICK SPECTATES that player (Patch 385, cl_spectate.qc): the row sets
  pl_specpick and Scores_Draw hands it to Spec_Request after its sui_end, which
  closes the board.  Only on the pinned board, whose cursor is real.  Your own
  row has no click; the watched player's row is outlined.  Bodies come from the
  pose stream (Patch 383: one sample per owner tick while watched), not from any
  recording.

  Thumbnails: gfx/thumbnails/ (the voice-status set).  Precached at init --
  drawpic on an unprecached name is a disk hit on the frame you hover the
  panel, the trap cl_hud.qc's crosshair comment documents.
===========================================================================
*/

float pl_specpick;              // slot + 1 a row click asked to spectate, 0 none (Scores_Draw takes it)
float pl_rows;                  // players drawn this frame (diagnostics)

#define PL_MAXSLOT  64          // QW slots; getplayerkeyvalue returns "" past the end
#define PL_RH       26          // row height, px

/*
  PATCH 340: BEST MAIN TIME PER PLAYER, and the ranking it buys.

  The source is the online board (cl_online.qc), absorbed into our own table
  the moment a reply lands -- ob_* is a SINGLE table overwritten by every
  fetch, so anything the room list wants to keep has to be copied out.  The
  match key is the row's `player` field, which surfd stores as the submitter's
  raw guid (surfd.py: "the 8 hex in the middle are sha256(guid)[:8] and
  `player` IS that guid"): FS_GuidId of it is exactly the *phash string
  Lobby_ClientConnect publishes, so a row finds its player through the hash
  and NOT through the name -- a rename mid-session does not move anybody's
  time, which is the same property the run files have.

  A listen server, or a lobby the directory does not know, fetches nothing
  and the list degrades to join order with no medals -- honest about there
  being no board, rather than inventing one.
*/
#define PL_BMAX 64
float  pl_bid;                  // strbuf of 8-hex ids
float  pl_bticks[PL_BMAX];
float  pl_bn;
string pl_bmap;                 // the map the fetch was asked for
float  pl_basked;               // and that we asked at all
float  pl_bgen;                 // ob_gen the room list last asked at (Patch 357)
// Set by Scores_Draw: the board wants a DIFFERENT online board, so the room
// list must not take the shared ob_* store from it with a fetch of its own.
float  pl_boardbusy;

// Medal plates, in the order the podium wears them.
vector(float r) Pl_Medal =
{
	if (r == 1) return '1.00 0.84 0.00';   // gold
	if (r == 2) return '0.75 0.78 0.82';   // silver
	if (r == 3) return '0.72 0.45 0.20';   // bronze
	return '0 0 0';
};

void() Players_AbsorbBoard =
{
	local float i, j, t;
	local string id;

	// Only a reply that describes THIS map's main leg, ranked, clean -- the
	// board the room list asked for.  Anything else in ob_* is some other
	// leg's truth and would rank people by a time they set elsewhere.
	if (!Online_Describes(0, 0, OB_TIER, "clean"))
		return;

	for (i = 0; i < ob_n; i = i + 1)
	{
		id = FS_GuidId(bufstr_get(ob_bplayer, i));
		if (id == "")
			continue;
		t = ob_ticks[i];
		if (t <= 0)
			continue;

		j = 0;
		while (j < pl_bn)
		{
			if (strcmp(bufstr_get(pl_bid, j), id) == 0)
				break;
			j = j + 1;
		}
		if (j < pl_bn)
		{
			if (t < pl_bticks[j])
				pl_bticks[j] = t;         // best of whatever tiers we have seen
		}
		else if (pl_bn < PL_BMAX)
		{
			bufstr_set(pl_bid, pl_bn, id);
			pl_bticks[pl_bn] = t;
			pl_bn = pl_bn + 1;
		}
	}
};

// The absorbed best for a player hash, or 0 for "no row we have seen".
float(string id) Players_Best =
{
	local float j;

	if (id == "")
		return 0;
	for (j = 0; j < pl_bn; j = j + 1)
		if (strcmp(bufstr_get(pl_bid, j), id) == 0)
			return pl_bticks[j];
	return 0;
};

void(float slot, string nm) Pl_VoiceToggle =
{
	// cl_voip_mute takes the name (Player_StringtoSlot, cl_ignore.c).
	if (stof(getplayerkeyvalue(slot, "vignored")))
		localcmd(sprintf("cl_voip_unmute \"%s\"\n", nm));
	else
		localcmd(sprintf("cl_voip_mute \"%s\"\n", nm));
};

/*
  The panel.  Called from inside Scores_Draw's sui bracket; bp/bsz are the
  board's rect this frame, pad its padding, scr the window.
*/
void(vector bp, vector bsz, float pad, vector scr) Players_Panel =
{
	local vector p, sz;
	local float i, j, y, rh, n, avail, voiceon, voicemuted, silenced, me;
	local float tsz, namew, bt, key, bestkey, kj, xx, r, b, showping, tw;
	local float slot[PL_MAXSLOT];
	local float best[PL_MAXSLOT];
	local float rank[PL_MAXSLOT];
	local string nm, ping, id, map;

	// Nothing to list before a server is loaded (main-menu board peeks).
	map = serverkey("map");
	if (map == "")
		return;

	/*
	  One fetch per map, the moment the panel first draws on it: the main
	  leg's ranked board is what the ranking reads.  Online_Fetch has its own
	  anti-hammer and retry rules (cl_online.qc); asking once and letting
	  those rules answer is the whole trigger.
	*/
	if (pl_bmap != map)
	{
		if (pl_bmap != "")
			strunzone(pl_bmap);
		pl_bmap  = strzone(map);
		pl_basked = FALSE;
		pl_bn = 0;                      // another map's times are not this one's
	}
	// The board's own main/clean fetch serves the room list; otherwise ask,
	// again after a finish made the store stale, but never mid-flight and
	// never out from under a board showing another leg.
	Online_Poll();
	if (Online_Asked(0, 0, OB_TIER, "clean", TRUE))
	{
		pl_basked = TRUE;               // asked at this gen: its backoff is the board's
		pl_bgen = ob_gen;
	}
	else if ((!pl_basked || pl_bgen != ob_gen) && ob_state != OBS_FETCH
	         && !pl_boardbusy)
	{
		pl_basked = TRUE;
		pl_bgen = ob_gen;
		Online_Fetch(0, 0, OB_TIER, "clean");
	}

	rh = PL_RH;
	p  = '0 0 0';
	sz = '0 0 0';

	// Count first: the header says how many, and a slot walk that stops at
	// the first "" would truncate a server whose slot 0 is empty.
	n = 0;
	for (i = 0; i < PL_MAXSLOT; i = i + 1)
	{
		if (getplayerkeyvalue(i, "name") == "")
			continue;
		slot[n] = i;
		id = getplayerkeyvalue(i, "*phash");
		best[n] = Players_Best(id);
		n = n + 1;
	}
	if (n == 0)
		return;
	pl_rows = n;

	/*
	  RANKED, FIRST TO LAST: timed players by ascending time, then the untimed
	  in join order.  Insertion sort over at most 64 rows once per frame is a
	  few hundred compares -- cheaper than the string reads above it, and
	  stable by construction because equal keys keep discovery order.
	*/
	for (i = 1; i < n; i = i + 1)
	{
		key  = (best[i] > 0) ? best[i] : 999999999;
		bt   = slot[i];
		bestkey = best[i];
		j = i - 1;
		while (j >= 0)
		{
			kj = (best[j] > 0) ? best[j] : 999999999;
			if (kj <= key)
				break;
			slot[j + 1] = slot[j];
			best[j + 1] = best[j];
			j = j - 1;
		}
		slot[j + 1] = bt;
		best[j + 1] = bestkey;
	}
	// rank[] = podium position among the TIMED, 0 = no time yet.
	j = 0;
	for (i = 0; i < n; i = i + 1)
	{
		if (best[i] > 0)
		{
			j = j + 1;
			rank[i] = j;
		}
		else
			rank[i] = 0;
	}

	// Geometry: right of the board, or docked over its right edge.
	avail = scr_x - (bp_x + bsz_x) - pad * 2;
	sz_y  = bsz_y;
	if (avail >= 190)
	{
		p_x = bp_x + bsz_x + pad;
		sz_x = avail;
		if (sz_x > 300)
			sz_x = 300;
	}
	else
	{
		sz_x = 200;
		p_x  = bp_x + bsz_x - sz_x - pad;
	}
	p_y = bp_y;

	sui_fill(p, sz, '0.05 0.05 0.07', 0.92, 0);
	sui_border_box(p, sz, 1, '0.28 0.30 0.36', 0.9, 0);

	/*
	  One type scale, snapped to the font ladder like every other panel:
	  ui_cv_scale is cl_hud.qc's per-frame mirror of hud_scale, and this runs
	  inside Scores_Draw, after HUD_ReadCvars has refreshed it.
	*/
	tsz = Font_Px(6 * ui_cv_scale);
	if (tsz <= 0)
		tsz = 12;

	Font_Set(ui_font_ui);
	sui_text([p_x + pad, p_y + pad], [tsz, tsz],
	         sprintf("in this server  %g", n), '0.35 0.75 1', 1, 0);

	y  = p_y + pad + 22;
	me = player_localnum;

	/*
	  Column budget, right to left: voice icon, silence chip, ping (only when
	  the panel is wide enough to deserve it), best time, then the name takes
	  what is left.  A docked 200 px panel drops the ping rather than
	  squeezing the name into illegibility.
	*/
	showping = (sz_x >= 260) ? 1 : 0;
	tw  = ceil(tsz * 5.2);              // best-time column
	namew = sz_x - pad * 2 - ceil(tsz * 1.8) - 16
	      - tw - 46 - (showping ? ceil(tsz * 3) : 0);
	if (namew < tsz * 4)
		namew = tsz * 4;

	for (i = 0; i < n; i = i + 1)
	{
		j  = slot[i];
		r  = rank[i];
		b  = best[i];
		nm = getplayerkeyvalue(j, "name");
		if (y + rh > p_y + sz_y - 34)
		{
			// Out of room: say how many are missing rather than clip silently.
			sui_text([p_x + pad, y], [tsz, tsz],
			         sprintf("... %g more", n - i), '0.55 0.55 0.58', 1, 0);
			break;
		}

		// The row is the spectate button.  The voice and chat chips register after
		// it, so they are in front and keep their own clicks (sui hit-tests front
		// to back).  sui_is_clicked: pressed AND released on the row.
		if (spc_stat == j + 1)
			sui_fill([p_x + 4, y], [sz_x - 8, rh - 2], '0.16 0.22 0.30', 1, 0);
		if (j != me)
		{
			sui_action_element([p_x + 4, y], [sz_x - 8, rh - 2],
			                   sprintf("pl_row%g", j), sui_noop);
			if (sui_is_hovered(sprintf("pl_row%g", j)))
				sui_fill([p_x + 4, y], [sz_x - 8, rh - 2], '0.12 0.12 0.16', 0.6, 0);
			// A held-TAB peek has no cursor: a click there lands on a stale position.
			if (rec_sb_open)
			if (sui_is_clicked(sprintf("pl_row%g", j)))
				pl_specpick = j + 1;
		}
		if (spc_stat == j + 1)
			sui_border_box([p_x + 4, y], [sz_x - 8, rh - 2], 1, '0.35 0.85 1', 0.95, 0);

		xx = p_x + pad;

		/*
		  THE PLATE.  Gold, silver, bronze over the rank of the timed, in the
		  order the board's own ranking gave us; everybody else gets a plain
		  rank number, and the untimed get a dash -- a medal for a time we
		  have never seen would be a lie with a shine on it.
		*/
		if (r >= 1 && r <= 3)
		{
			sui_fill([xx, y + 5], [ceil(tsz * 1.5), rh - 12], Pl_Medal(r), 0.9, 0);
			sui_text([xx + 3, y + 6], [tsz, tsz], ftos(r), '0.1 0.1 0.1', 1, 0);
		}
		else if (b > 0)
			sui_text([xx + 3, y + 6], [tsz, tsz], ftos(r), '0.55 0.55 0.58', 1, 0);
		else
			sui_text([xx + 3, y + 6], [tsz, tsz], "-", '0.4 0.4 0.44', 1, 0);
		xx = xx + ceil(tsz * 1.8);

		// Colour swatch: the exact worn rgb (`lrgb`, Patch 341), which for a
		// palette player IS the palette entry -- one source, no nearest-lie.
		sui_fill([xx, y + 7], [12, 12], Av_WornRGB(j), 1, 0);
		xx = xx + 16;

		// The name, in the chat colour -- the same rule the chatbox uses, so
		// a name is ONE colour everywhere it appears.
		id = (strstrofs(nm, "^", 0) >= 0)
			? nm
			: strcat("^", Chat_ColourOf(j), nm, "^7");
		id = Chat_Fit(id, namew, tsz);
		sui_text([xx, y + 6], [tsz, tsz], id, '1 1 1', 1, 0);
		if (j == me)
			sui_text([xx + stringwidth(id, TRUE, [tsz, tsz]) + 6, y + 6], [tsz, tsz],
			         "you", '0.45 0.45 0.5', 1, 0);

		// Best main time, right-aligned before the icon block; medal-coloured
		// on the podium, plain above it.
		xx = p_x + sz_x - pad - 46 - tw;
		if (showping)
			xx = xx - ceil(tsz * 3);
		if (b > 0)
		{
			id = Time_TickString(b, Timer_Tick());
			sui_text([xx + tw - ceil(tsz * 0.6) - stringwidth(id, TRUE, [tsz, tsz]), y + 6],
			         [tsz, tsz], id,
			         (r >= 1 && r <= 3) ? Pl_Medal(r) : '0.65 0.65 0.7', 1, 0);
		}
		if (showping)
		{
			ping = getplayerkeyvalue(j, "ping");
			// After the time column, before the voice icon.  (It was drawn at the
			// time column's own start -- unseen until the room list absorbed rows.)
			if (ping != "")
				sui_text([p_x + sz_x - pad - 46 - ceil(tsz * 3), y + 6],
				         [tsz, tsz], strcat(ping, "ms"), '0.55 0.55 0.58', 1, 0);
		}

		// Voice: icon button.  speaking > muted > idle.
		voiceon     = stof(getplayerkeyvalue(j, "voipspeaking"));
		voicemuted  = stof(getplayerkeyvalue(j, "vignored"));
		sui_action_element([p_x + sz_x - pad - 46, y + 4], [18, 18],
		                   sprintf("pl_v%g", j), sui_noop);
		drawpic([p_x + sz_x - pad - 46, y + 4],
		        voicemuted ? "gfx/thumbnails/muted"
		                   : (voiceon ? "gfx/thumbnails/speaking"
		                              : "gfx/thumbnails/speaking_off"),
		        [18, 18], '1 1 1',
		        (voicemuted || voiceon) ? 1 : 0.45, 0);
		if (sui_is_hovered(sprintf("pl_v%g", j)))
			sui_border_box([p_x + sz_x - pad - 46, y + 4], [18, 18], 1,
			               '0.5 0.8 1', 1, 0);
		if (sui_is_released(sprintf("pl_v%g", j)) && j != me)
			Pl_VoiceToggle(j, nm);

		// Chat silence: a chip that shows its own state.
		silenced = Chat_Silenced(nm);
		if (j != me)
		{
			sui_action_element([p_x + sz_x - pad - 24, y + 4], [24, 18],
			                   sprintf("pl_c%g", j), sui_noop);
			sui_fill([p_x + sz_x - pad - 24, y + 4], [24, 18],
			         silenced ? '0.30 0.16 0.16' : '0.10 0.10 0.13', 1, 0);
			sui_border_box([p_x + sz_x - pad - 24, y + 4], [24, 18], 1,
			               silenced ? '1 0.5 0.4'
			                        : (sui_is_hovered(sprintf("pl_c%g", j))
			                           ? '0.5 0.8 1' : '0.28 0.30 0.36'), 1, 0);
			sui_text([p_x + sz_x - pad - 18, y + 7], [tsz - 1, tsz - 1],
			         silenced ? "off" : "chat",
			         silenced ? '1 0.7 0.65' : '0.55 0.55 0.58', 1, 0);
			if (sui_is_released(sprintf("pl_c%g", j)))
				Chat_SilenceToggle(nm);
		}

		y = y + rh;
	}

	// ---- footer: what a row click does -------------------------------------
	if (spc_stat > 0)
		nm = strcat("watching ", getplayerkeyvalue(spc_stat - 1, "name"), "^7 -- esc to return");
	else if (serverkeyfloat("fs_spec") != 1)
		nm = "this server does not offer spectate";
	else if (!rec_sb_open)
		nm = "pin the board (mouse2) to pick a player";
	else
		nm = "click a player to spectate";
	sui_text([p_x + pad, p_y + sz_y - 24], [tsz, tsz], Chat_Fit(nm, sz_x - pad * 2, tsz),
	         '0.55 0.55 0.58', 1, 0);
};

void() Players_RegisterCvars =
{
	if (!pl_bid)
		pl_bid = buf_create();

	precache_pic("gfx/thumbnails/speaking");
	precache_pic("gfx/thumbnails/speaking_off");
	precache_pic("gfx/thumbnails/muted");
};
