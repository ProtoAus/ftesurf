/*
===========================================================================
  cl_saveloc.qc -- the save-lock menu and the keys that drive it.

  The LIST lives on the server (sv_saveloc.qc) -- it has to, because two of
  the three things a save restores are not CSQC's to give back.  This file is
  the view and the keyboard: it draws six rows and a "3/7", and it turns a
  key press into one client command.

  THE KEY MAP.  Momentum's nine with the panel up; three of them with it down.

      PANEL UP                            PANEL DOWN
      z  open / close                     z  open / close
      1  Create Save     5  Go to First   1  Create Save
      2  Load Save       6  Go to Last    2  Load Save
      3  Go to next      7  Remove Save   4  Remove Save
      4  Go to previous  8  Delete All
                         0  Close menu

  EVERY KEY ACTS ON THE CURSOR, and that is the whole of it.  The header's
  "3/7" tells you which save `2` is about to put you back at, and 3/4/5/6 move
  it; the three closed-panel keys send the SAME THREE COMMANDS the open panel
  sends -- sl_save, sl_load+sl_hold, sl_del -- every one of which reads
  self.rec_sl_index on the server.  Nothing here can act on anything but the
  cursor, whether or not you can see it.

  WHAT THAT REPLACES, AND WHY IT WAS A BUG.  Until build 25 the closed state
  had its OWN key map into its own commands: 2 sent sl_loadlast and 4 sent
  sl_dellast, and both read rec_sl_count -- the LENGTH of the list -- rather
  than rec_sl_index, the cursor.  So stepping to save 2 of 5 and pressing 2
  could load save 5, which is the reported "it loads the current save, not the
  one I selected".  Two key maps over one list is what made that possible.
  Build 25 deleted the second map; build 26 brings back its three keys and
  points them at the first map's commands, and sl_loadlast/sl_dellast stay
  gone from the server so the disagreement has nowhere left to live.

  4 IS THE ASYMMETRY AND IT IS DELIBERATE.  With the panel up it steps
  backwards, Momentum's layout; with the panel down it removes, which is where
  it has been since build 11 and where the hand expects it.  Said plainly here
  rather than smoothed over, because the panel's own row 4 reads "Go to
  previous" and is telling the truth about the state it is drawn in.

  8 IS NOT REACHABLE WITH THE PANEL DOWN.  Its confirmation is a row of text on
  a panel that is not being drawn, so arming it there would be a keypress with
  no feedback that erases every save on the map.

  3 AND 4 STILL TELEPORT, as 4 and 5 did (see SV_SaveLocStep), and so do 5
  and 6 -- if half the navigation keys moved you and half did not, the four
  would look alike and behave differently.  `2` is then the key that loads
  the one you are already on, and the key you HOLD to park there.

  8 ASKS TWICE.  It is the only action here with nothing to undo it and it
  is adjacent to 7; see rec_sl_armdel.

  WHY THESE PRESSES ARE CONSUMED

  CSQC_InputEvent returning TRUE stops the engine dispatching the key's bind
  (keys.c:3211).  cl_keys.qc's header is emphatic that the key-light reader
  must NEVER do that -- it is only observing.  This one is not observing: the
  digits ARE the feature, and letting them also run `impulse 1` (which is
  what ftesurf.cfg still binds them to, inherited from stock Quake) would be
  the bug.  So this returns TRUE for exactly the keys it acted on and FALSE
  for everything else, including the digits it does not use.

  It never sees a press while the console or the menu is up: keys.c only
  offers CSQC a key-down when `!Key_Dest_Has(~kdm_game)`.  Key-UP events do
  arrive from those states, which is why cl_keys.qc needs Keys_Clear and this
  file -- acting only on the down edge -- does not.
===========================================================================
*/

float rec_sl_open;               // the menu is up
float rec_sl_cv;

/*
  The Delete All arm.  Build 25.

  8 wipes every save state on the map and QC cannot undo a fremove, so the first
  press arms and the second within FS_SL_ARMTIME confirms.  It lives here rather
  than on the server for one reason worth stating: it is a property of one
  person's keyboard over three seconds, and the server-side alternative is a
  per-player timer field maintained every tick for a decision the server does not
  otherwise take part in.  `cmd sl_delall` from the console is deliberately not
  gated -- the console is already the place where you mean what you type.

  Disarmed by ANY other save-lock key, not just by a timeout, so 8-then-7 cannot
  leave a live arm behind that a later 8 walks into.
*/
float rec_sl_armdel;             // cltime of the first press; 0 = not armed

#define FS_SL_ARMTIME 3

/*
  The load key, held.

  Holding it parks you at the save until you let go (sv_saveloc.qc pins the
  origin each tick).  Two things this has to get right:

  * ONLY THE EDGES GO TO THE SERVER.  A held key repeats -- the engine keeps
    delivering IE_KEYDOWN while you hold it -- and a client command per repeat
    would be a stream of reliable messages for a key you pressed once.  So the
    press is latched here and the server hears exactly one `sl_hold` and one
    `sl_holdoff`.

  * THE RELEASE MUST ALWAYS ARRIVE.  A key-up that lands while the console or
    the menu is up still reaches CSQC (keys.c:3219-3225 forwards up events from
    every state, which is the same guarantee cl_keys.qc relies on) -- but
    alt-tab can still eat one.  Held_Frame below releases the hold whenever the
    HUD is not being drawn, for the same reason Keys_Clear exists.

  BUILD 40: rec_sl_holding itself is DECLARED IN cl_keys.qc, not here.  cl_hud.qc
  compiles before this file (cl_progs.src) and now reads it -- the HUD has to
  know a hold is in flight a round trip before STAT_FS_HOLD can say so, which is
  what the settle guard in HUD_UpdateLatch is for.  Same ordering constraint,
  same answer, as run_ps_release and the rec_wt_* block already living there.
*/
float rec_sl_holdkey;            // the scancode that started it

/*
  The deadman, and why it is armed by evidence rather than by a timer.

  A key held down auto-repeats, and those repeats DO reach CSQC -- keys.c runs
  its `if (down && wasdown) return;` repeat filter at :3429, well below the CSQC
  dispatch at :3211, so binds do not repeat but we see every one.  That gives a
  liveness signal for free: if repeats were arriving and then stop, the key came
  up and we missed the event.

  But not every device repeats, and a hold that expired after two seconds
  because a gamepad or a raw-input path sends no repeats would break the feature
  for its main use -- sitting at the top of a ramp for as long as you like.  So
  the deadman only arms once a repeat has actually been SEEN for this hold.  No
  repeats, no deadman; repeats, then silence, release.

  The window is generous on purpose.  Windows' slowest configurable repeat rate
  is about two a second, so anything under ~0.5s could fire between two real
  repeats; 1.5s cannot, and 1.5s of unwanted freeze that then fixes itself is a
  different order of problem from being stuck until the map changes.
*/
float rec_sl_holdseen;           // cltime of the last down edge for the hold key
float rec_sl_holdrep;            // a repeat has been observed for THIS hold

#define SL_HOLD_DEADMAN 1.5

/*
  Build 12: the hold locks the VIEW as well as the position.

  Freezing where you stand while the camera still swings around is the worst of
  both -- you are studying an approach and the thing you are studying moves with
  the mouse.  Latched on the rising edge and written back every frame.

  VF_CL_VIEWANGLES, not VF_ANGLES, and not input_angles.  VF_ANGLES is the
  RENDER view only, so the server would still receive the mouse and you would
  snap on release.  input_angles reaches only the outgoing usercmd
  (pr_csqc.c:4051-4055 writes cmd->angles and nothing else), so the server would
  freeze while the camera kept turning -- the same client/server disagreement
  that made the position pin flicker before build 11.  VF_CL_VIEWANGLES writes
  csqc_playerview->viewangles (pr_csqc.c:2596-2600), which is the one the camera
  and the usercmd are both built from, so both freeze from one write.
*/
vector rec_sl_holdang;
float  rec_sl_holdang_ok;        // the latch is valid; a hold with no latch yet must not force '0 0 0'

void() SaveLoc_RegisterCvars =
{
	/*
	  The whole feature, including the bare digits.

	  0 hands 1/2/3/4/5/0/z straight back to the engine's bind table, which is
	  the only reason this is a cvar: if you ever want a number row that does
	  something else, there has to be a way to say so.
	*/
	registercvar("rec_savelock",   "1");

	registercvar("hud_saveloc_x", "0.018", CVAR_ARCHIVE);
	registercvar("hud_saveloc_y", "0.34", CVAR_ARCHIVE);

	/*
	  Both do their work on the SERVER, and an unknown console command does
	  NOT reach SV_ParseClientCommand -- Cmd_ExecuteString offers it to SSQC's
	  SV_ParseServerCommand hook instead, where `self` is world and there is
	  no player to move (see Zone_RegisterCvars for the same trap).  Register
	  them here and forward with `cmd`.
	*/
	registercommand("saveloc");
	registercommand("timer");

	/*
	  BUILD 24: `viewpos` -- where am I, in a line that pastes back into setpos.

	  It needs registering here for the same reason `timer` does, and NOT for the
	  reason `setpos` does not: setpos is an engine command with a NULL handler
	  (cl_main.c:6253), which is how the engine says "forward this to the server
	  verbatim".  viewpos has no such entry, so without this line the console
	  would answer "Unknown command" and the forwarding would never happen.
	*/
	registercommand("viewpos");

	// The same toggle `z` does, as a command -- so it can be bound to whatever
	// key you like without editing this file, and so it can be driven from a
	// config.
	registercommand("saveloc_menu");
};

void(string c) SaveLoc_Cmd = { localcmd(strcat("cmd ", c, "\n")); };

void() SaveLoc_Release =
{
	if (!rec_sl_holding)
		return;
	rec_sl_holding = FALSE;
	rec_sl_holdkey = 0;
	rec_sl_holdrep = FALSE;
	rec_sl_holdang_ok = FALSE;
	SaveLoc_Cmd("sl_holdoff");
};

/*
  The view lock.

  BUILD 13 -- it has to run on EVERY RENDERED FRAME, not every usercmd.

  Build 12 called this from CSQC_Input_Frame only, and that is why the view
  "bounces back to your lock every frame" instead of holding still.  The two
  clocks are not the same clock: usercmds are built at cl_netfps (66.7Hz here)
  while the camera draws at whatever the GPU manages, commonly 300+.  The
  engine's mouse accumulator moves the view angles as the samples arrive, so of
  every five drawn frames roughly four render from an angle that has moved and
  one renders from the angle this function just put back.  You see the mouse
  work and then get snapped -- which is exactly the report.

  So it is called from both places, with different jobs:

    CSQC_Input_Frame  -- pins what the SERVER receives (input_angles), so the
                         locked player does not turn for anyone else either.
    CSQC_UpdateView   -- pins what the CAMERA is built from, before the scene
                         is set up, which is the half that was missing.

  VF_CL_VIEWANGLES writes csqc_playerview->viewangles (pr_csqc.c:2596), the
  real client angles rather than the render-only VF_ANGLES, so writing it from
  the draw path also stops the accumulator drifting further -- the lock holds
  at a fixed angle instead of fighting a value that keeps running away.

  The latch is taken on the first frame of the hold rather than on the key
  press, because the press arrives in CSQC_InputEvent where the current view
  angles are not what the next usercmd will carry.  One frame of mouse movement
  gets through; that is invisible, and it is correct, because it is the frame
  you pressed on.
*/
/*
  BUILD 18 -- the lock has to yield to a load, or the save's angle never lands.

  The two things happen in the same keystroke: key 2 sends `sl_load` AND arms the
  lock (SaveLoc_Key).  The lock latches on its very next frame, which is long
  before the server's reply can arrive, so what it latches is the angle you had
  BEFORE the load.  Then it writes that back every rendered frame and every
  usercmd.  When svc_setangle finally lands ~1 RTT later it survives less than one
  frame -- and worse, the next usercmd carries the stale angle back to the server,
  where sv_user.c:7649 copies it into .v_angle now that the one-shot fixangle has
  been consumed (sv_send.c:1651).  The saved angle is gone on both sides, which is
  exactly the reported "it just leaves you with whatever angle you had".

  So: edge-detect the same save event cl_replay.qc already watches, and drop the
  latch when a LOAD lands.  The next call re-latches from the restored angle.  A
  save (SLOP_SAVED) must NOT do this -- nothing moved, and re-latching there would
  hand back a frame of mouse movement you had already been denied.

  The counter is advanced even when not holding, so an event that happened while
  the lock was off cannot fire the first time you press 2 afterwards.
*/
float rec_sl_angseq;

void() SaveLoc_AngleEvents =
{
	local float seq, op;

	seq = getstatf(STAT_FS_SLSEQ);
	if (seq == rec_sl_angseq)
		return;
	rec_sl_angseq = seq;

	op = FS_SlopOp(getstatf(STAT_FS_SLOP));
	if (op == SLOP_LOADED)
		rec_sl_holdang_ok = FALSE;
};

void() SaveLoc_LockAngles =
{
	SaveLoc_AngleEvents();

	if (!rec_sl_holding)
	{
		rec_sl_holdang_ok = FALSE;
		return;
	}

	if (!rec_sl_holdang_ok)
	{
		rec_sl_holdang = getproperty(VF_CL_VIEWANGLES);
		rec_sl_holdang_ok = TRUE;
		return;
	}

	setproperty(VF_CL_VIEWANGLES, rec_sl_holdang);
};

void() SaveLoc_InputFrame =
{
	SaveLoc_LockAngles();
	if (rec_sl_holding && rec_sl_holdang_ok)
		input_angles = rec_sl_holdang;
};

/*
  Called every frame the HUD is not drawn -- the menu, the console, a lost
  window.  See the note on rec_sl_holding: a release that never arrives would
  otherwise leave you parked at a save with no way out but pressing 2 again.
*/
void() SaveLoc_Idle = { SaveLoc_Release(); };

/*
  The load key, from either state.

  ONE function, because the two call sites have to send the same pair in the
  same order and latch the same three fields: sl_load puts you back and sl_hold
  pins you there until the release.  A second copy that ever sent one without
  the other is either a load you cannot get out of or a hold on a save you are
  not standing at -- and a second copy of a save-lock key path is exactly what
  sl_loadlast was.  See the header.
*/
void(float scan) SaveLoc_LoadKey =
{
	SaveLoc_Cmd("sl_load");
	SaveLoc_Cmd("sl_hold");
	rec_sl_holding  = TRUE;
	rec_sl_holdkey  = scan;
	rec_sl_holdseen = cltime;
	rec_sl_holdrep  = FALSE;
};

// Called every frame the HUD IS drawn.  The deadman above.
void() SaveLoc_HoldFrame =
{
	if (!rec_sl_holding)
		return;
	if (!rec_sl_holdrep)
		return;                 // nothing has repeated, so silence proves nothing
	if (cltime - rec_sl_holdseen > SL_HOLD_DEADMAN)
		SaveLoc_Release();
};

/*
  One key press.  Returns TRUE when it consumed it.
*/
float(float scan, float down) SaveLoc_Key =
{
	rec_sl_cv = cvar("rec_savelock");
	if (!rec_sl_cv)
	{
		SaveLoc_Release();
		return FALSE;
	}

	if (!down)
	{
		// The only release that means anything is the load key's.  Consume it
		// so it matches the press, which was consumed too.
		if (rec_sl_holding && scan == rec_sl_holdkey)
		{
			SaveLoc_Release();
			return TRUE;
		}
		return FALSE;
	}

	// A REPEAT of the key already held.  The engine keeps delivering key-down
	// while a key is held; the server has already been told once.  Stamping it
	// here is what arms the deadman -- see rec_sl_holdrep.
	if (rec_sl_holding && scan == rec_sl_holdkey)
	{
		rec_sl_holdseen = cltime;
		rec_sl_holdrep  = TRUE;
		return TRUE;
	}

	if (scan == 'z')
	{
		rec_sl_open = !rec_sl_open;
		rec_sl_armdel = 0;           // an arm does not survive the panel closing
		return TRUE;
	}

	/*
	  BUILD 26: THE PANEL-DOWN KEYS.  Create, load, remove -- and nothing else.

	  The same three commands the open panel sends, so both states act on the
	  cursor and the build 25 header's argument survives intact: there is still
	  only one key map in the sense that matters, which is one set of commands
	  over one index.  What differs is which keys reach it.

	  Every other digit returns FALSE here and goes to the engine's own bind
	  table untouched.  8 is deliberately not among these -- its confirmation is
	  a row on a panel that is not being drawn.
	*/
	if (!rec_sl_open)
	{
		if (scan == '1') { SaveLoc_Cmd("sl_save"); return TRUE; }
		if (scan == '2') { SaveLoc_LoadKey(scan);  return TRUE; }
		if (scan == '4') { SaveLoc_Cmd("sl_del");  return TRUE; }
		return FALSE;
	}

	/*
	  8 twice.  Tested before the disarm below, and the disarm is what every
	  other key falls through to -- so 8, 7, 8 is two separate first presses
	  rather than a confirmation.
	*/
	if (scan == '8')
	{
		if (rec_sl_armdel > 0 && cltime - rec_sl_armdel <= FS_SL_ARMTIME)
		{
			rec_sl_armdel = 0;
			SaveLoc_Cmd("sl_delall");
		}
		else
			rec_sl_armdel = cltime;
		return TRUE;
	}

	rec_sl_armdel = 0;

	/*
	  2 loads the SELECTED save, and it is HELD: it loads on the press and parks
	  you there until you let go.
	*/
	if (scan == '2') { SaveLoc_LoadKey(scan); return TRUE; }

	if (scan == '1') { SaveLoc_Cmd("sl_save");  return TRUE; }

	// 3/4/5/6 LOAD as well as move the cursor -- see SV_SaveLocStep.
	if (scan == '3') { SaveLoc_Cmd("sl_next");  return TRUE; }
	if (scan == '4') { SaveLoc_Cmd("sl_prev");  return TRUE; }
	if (scan == '5') { SaveLoc_Cmd("sl_first"); return TRUE; }
	if (scan == '6') { SaveLoc_Cmd("sl_last");  return TRUE; }

	if (scan == '7') { SaveLoc_Cmd("sl_del");   return TRUE; }
	if (scan == '0') { rec_sl_open = FALSE;      return TRUE; }

	return FALSE;
};

/*
  One row.  `hot` is the action the header's index is about to act on, which
  is load -- so it is the row that tells you what `2` will do.
*/
void(vector p, float w, float h, string key, string label, float hot, float lsz) SaveLoc_Row =
{
	local vector fg;

	drawfill(p, [w, h], hot ? '0.16 0.22 0.30' : '0 0 0', hot ? 0.80 : 0.55, 0);

	fg = hot ? '1.00 0.90 0.55' : '0.80 0.83 0.88';
	HUD_Text([p_x + h * 0.35, p_y + (h - lsz) * 0.5], key, lsz, fg, 1);
	HUD_Text([p_x + h * 1.25, p_y + (h - lsz) * 0.5], label, lsz,
	         hot ? '1 1 1' : '0.72 0.75 0.80', 1);
};

void(vector scr) SaveLoc_Draw =
{
	local vector p;
	local float w, h, lsz, gap, count, idx, y;
	local string hdr;

	if (!rec_sl_open)
		return;
	if (!cvar("rec_savelock"))
	{
		rec_sl_open = FALSE;         // turned off underneath us
		return;
	}

	count = getstatf(STAT_FS_SAVECOUNT);
	idx   = getstatf(STAT_FS_SAVEINDEX);

	Font_Set(ui_font_ui);
	lsz = Font_Px(8 * ui_cv_scale);
	h   = 13 * ui_cv_scale;
	w   = 84 * ui_cv_scale;
	gap = 1 * ui_cv_scale;

	p = [scr_x * cvar("hud_saveloc_x"), scr_y * cvar("hud_saveloc_y"), 0];
	y = p_y;

	// Header: the title on the left, the cursor on the right.  "3/7" is the
	// whole point of the menu -- it is what `2` is about to load.
	drawfill([p_x, y], [w, h + gap], '0.10 0.13 0.17', 0.85, 0);
	HUD_Text([p_x + h * 0.35, y + (h - lsz) * 0.5], "Save Lock", lsz, '1 1 1', 1);

	hdr = (count > 0) ? sprintf("%g/%g", idx, count) : "--";
	HUD_TextR([p_x + w - h * 0.35, y + (h - lsz) * 0.5], hdr, lsz,
	          (count > 0) ? '1.00 0.90 0.55' : '0.55 0.58 0.62', 1);
	y = y + h + gap * 2;

	/*
	  Build 17: the run clock stored in the slot the cursor is on.

	  "3/7" says which save `2` will load and nothing about WHICH SAVE THAT IS,
	  which is fine when they are three metres apart and useless when they are
	  seven points along one run.  The time is the thing that distinguishes them,
	  and it is the same number the timer will read after the load.

	  Drawn only when there is one: a save taken outside a run stores 0, and
	  "0:00.000" would read as a save at the start of the run rather than as a
	  save with no run behind it.
	*/
	if (getstatf(STAT_FS_SAVETICKS) > 0)
	{
		drawfill([p_x, y], [w, h], '0.10 0.13 0.17', 0.75, 0);
		HUD_Text([p_x + h * 0.35, y + (h - lsz) * 0.5], "run at", lsz,
		         '0.55 0.58 0.62', 1);
		HUD_TextR([p_x + w - h * 0.35, y + (h - lsz) * 0.5],
		          Time_TickString(getstatf(STAT_FS_SAVETICKS), Timer_Tick()), lsz,
		          '0.45 0.85 1.00', 1);
		y = y + h + gap * 2;
	}

	/*
	  Build 25 -- Momentum's nine, in Momentum's order.

	  `hot` is still "the row the header's index is about to act on", which is
	  Load; the four navigation rows move that index rather than being it, so
	  they are not hot even though they also teleport.

	  Row 8 says what it is about to do rather than what it is called, and that
	  is the whole of the confirmation being visible: an armed Delete All reads
	  "Delete All -- again to confirm" in the same warning red the timer uses for
	  a voided run, and goes back to its own label when the arm lapses.
	*/
	SaveLoc_Row([p_x, y], w, h, "1", "Create Save",   FALSE, lsz);      y = y + h + gap;
	SaveLoc_Row([p_x, y], w, h, "2", "Load Save",     count > 0, lsz);  y = y + h + gap;
	SaveLoc_Row([p_x, y], w, h, "3", "Go to next",    FALSE, lsz);      y = y + h + gap;
	SaveLoc_Row([p_x, y], w, h, "4", "Go to previous",FALSE, lsz);      y = y + h + gap;
	SaveLoc_Row([p_x, y], w, h, "5", "Go to First",   FALSE, lsz);      y = y + h + gap;
	SaveLoc_Row([p_x, y], w, h, "6", "Go to Last",    FALSE, lsz);      y = y + h + gap;
	SaveLoc_Row([p_x, y], w, h, "7", "Remove Save",   FALSE, lsz);      y = y + h + gap;

	if (rec_sl_armdel > 0 && cltime - rec_sl_armdel <= FS_SL_ARMTIME)
	{
		drawfill([p_x, y], [w, h], '0.30 0.08 0.08', 0.90, 0);
		HUD_Text([p_x + h * 0.35, y + (h - lsz) * 0.5], "8", lsz, '1.00 0.80 0.55', 1);
		HUD_Text([p_x + h * 1.25, y + (h - lsz) * 0.5], "again to confirm", lsz,
		         '1.00 0.65 0.55', 1);
	}
	else
	{
		// Lapsed, or never armed.  Cleared here as well as on the next keypress
		// so the row cannot sit armed-looking after the window has gone.
		if (rec_sl_armdel > 0)
			rec_sl_armdel = 0;
		SaveLoc_Row([p_x, y], w, h, "8", "Delete All", FALSE, lsz);
	}
	y = y + h + gap;

	SaveLoc_Row([p_x, y], w, h, "0", "Close menu",    FALSE, lsz);
	y = y + h + gap;

	Font_Reset();

	// Build 31: the box, for `hud_edit`.  Left/top anchored like the gfx menu,
	// and only registered while the menu is open -- the editor falls back to a
	// nominal rect for the closed case, since a panel you cannot see at this
	// moment is still one you might want to move.
	HUD_Rect("saveloc", p, [w, y - p_y, 0], p);
};
