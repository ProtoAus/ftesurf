# P1400: the key panel's typed commands, key Edit/Clear and Tools/Game rows (8 Nov 2026, ftesurf-3a)

Lex: "on the keyboard tab, you should be able to type in your own action in the right side box, also I
want to include other tools/options like ent_view surf_view 'report menu' stuff like that."

- src/client/cl_keycfg.qc: "Your own command" field (kc_sel = KC_CUSTOM, the command zoned in kc_cmd);
  Selected key Edit/Clear; field focus takes every key but mouse buttons/wheel (KC_CaptureEvent),
  Esc leaves the field, releases of keys it took are eaten; paste via cl_main.qc's IE_PASTE chain.
  Rows 27-39 (Tools, Game); row 13 keeps id `entview` and now writes ent_view; `entcursor` is new.
  Actions tab: three columns, 568 units wide (1136 px at hud_scale 2).
- Kept keys: Escape (the engine's menu key whatever its bind) and the LAST console key. A spare
  console or menu key is an ordinary key; reset rebinds ` as the console.
- Arm verbs: `config_menu custom [cmd]`, `editkey <key> [cmd]`, `focus cmd|edit <key>`, `click <key>`.

## Evidence

- tools/p1400keys.py (hosted game; WM_KEYDOWN on the game's queue types into the fields). Fixed build:
  own command typed+Enter -> Mouse 4 bound; Edit appends; Esc leaves field, panel open, bind kept;
  empty edit clears; Escape refuses; Report on Home and back; section 4 (review fixes) all as
  designed. Control (pre-fix build, same arm): Escape bound +jump, console left with no key, spare
  menu key not clearable, reset kept H as console, a 145-char bind cut to 127.
- Screenshots looked at (1920x1111: this PC's scaling enlarged the 1280x720 window; vid_conwidth
  did not change the layout). 1280x720 fit is arithmetic only.
- One review (code only): no input leaks; one medium (Actions tab could clear/replace Escape and the
  console key) and four low defects, all fixed and measured above.

## Delivery

- LIVE 7 Nov 22:27Z (8 Nov local): 12 lobbies restarted (nobody on), csprogs b7917bba (qw unchanged
  0a406f51), main 9af1f2bc; codes.txt 90 -> 91 (.pre1400). C:\FTESurf installed (.prev beside each
  file, csprogsvers 165db981 seeded); C:\FTEQuake the same under rig.lock (b8 paused its queue).
- Limits: the backtick never reaches CSQC (cannot be typed); panel binds run at the insecure level
  (bindlevel 30), so a typed command that needs more may save but not run.
