#!/usr/bin/env python3
"""
accounts_mutants.py -- does surfd/test_accounts.py notice when the code is wrong?

    python tools/accounts_mutants.py [surfd dir]

Each mutant is ONE textual edit to surfd/steam.py, accounts.py or surfd.py in a
throwaway copy of the surfd tree, and the suite must fail on it.  One line per
mutant, then the count; exit 1 if a mutant survives that should not, or if a
mutant's text no longer matches the source (BAD MUTANT: the code moved, so move
the mutant with it).  About four minutes; nothing outside the temp dir is
written.

A mutant's text must be in the file exactly ONCE.  Where two functions share a
line, a fifth element names the one meant ("def link_return("): the edit is
then the first match after that marker, and the marker must itself be unique.

PAIRS lists mutants that are allowed to survive ALONE because a second check
covers the same hole; together they must die.

Add a mutant with every check you add: a check with no mutant that it alone
kills is a check nobody has seen fail.
"""
import concurrent.futures
import os
import shutil
import subprocess
import sys
import tempfile

SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "surfd")
SCRATCH = tempfile.mkdtemp(prefix="accounts-mutants-")
S, A = "steam.py", "accounts.py"

M = [
    # steam.py: precheck
    ("fields", S, "if set(args) != FIELDS:", "if False:"),
    ("fields-extra", S, "if set(args) != FIELDS:", "if not FIELDS <= set(args):"),
    ("token", S, 'if not _TOKEN.fullmatch(v or ""):', "if False:"),
    ("token-prefix", S, '_TOKEN.fullmatch(v or "")', '_TOKEN.match(v or "")'),
    ("cancel", S, 'if args.get("openid.mode") == "cancel":', "if False:"),
    ("mode", S, 'if args["openid.mode"] != "id_res":', "if False:"),
    ("ns", S, 'if args["openid.ns"] != NS:', "if False:"),
    ("endpoint", S, 'if args["openid.op_endpoint"] != OPENID:', "if False:"),
    ("return_to", S, 'if args["openid.return_to"] != return_to:', "if False:"),
    ("identity", S, 'if claimed != args["openid.identity"]:', "if False:"),
    ("universe", S, "if not m or not is_steamid64(m.group(1)):", "if not m:"),
    ("host", S, r'https://steamcommunity\.com/openid/id/([0-9]{17})',
     r'https://[a-z.]+/openid/id/([0-9]{17})'),
    ("claimed-prefix", S, "m = _CLAIMED.fullmatch(claimed)", "m = _CLAIMED.match(claimed)"),
    ("signed", S, "if len(signed) != len(SIGNED) or set(signed) != SIGNED:", "if False:"),
    ("signed-twice", S, "if len(signed) != len(SIGNED) or set(signed) != SIGNED:",
     "if set(signed) != SIGNED:"),
    ("signed-more", S, "if len(signed) != len(SIGNED) or set(signed) != SIGNED:",
     "if not SIGNED <= set(signed):"),
    ("skew", S, "if abs(now - at) > NONCE_SKEW:", "if False:"),
    ("skew-edge", S, "if abs(now - at) > NONCE_SKEW:", "if abs(now - at) >= NONCE_SKEW:"),
    ("nonce-prefix", S, "m2 = _NONCE.fullmatch(nonce)", "m2 = _NONCE.match(nonce)"),
    # steam.py: confirm, summaries, http
    ("valid-exact", S, 'if verdicts[0] != "true":', 'if not verdicts[0].startswith("true"):'),
    ("valid-any", S, 'if verdicts[0] != "true":', "if False:"),
    ("one-verdict", S, "if len(verdicts) != 1:", "if not verdicts:"),
    ("third-verdict", S, 'raise Unavailable("reply without one verdict")',
     'raise Refused("reply without one verdict")'),
    ("uninvited", S, ' or p.get("steamid") not in want:', ":"),
    ("avatar-prefix", S, "_AVATAR.fullmatch(avatar)", "_AVATAR.match(avatar)"),
    ("ctrl", S, 'name = _CTRL.sub("", name).strip()[:64]', "pass"),
    ("surrogate", S, 'name = name.encode("utf-8", "replace").decode("utf-8")', "pass"),
    ("depth", S, "except (ValueError, KeyError, TypeError, RecursionError):",
     "except (ValueError, KeyError, TypeError):"),
    ("http-client", S, "except (OSError, ValueError, HTTPException) as exc:",
     "except (OSError, ValueError) as exc:"),
    ("redirect", S, "    def redirect_request(self, *_a, **_k):\n        return None",
     "    def redirect_request(self, *a, **k):\n"
     "        return urllib.request.HTTPRedirectHandler.redirect_request(self, *a, **k)"),
    ("limit", S, "if len(body) > HTTP_LIMIT:", "if False:"),
    ("timeout", S, "with opener.open(req, timeout=timeout) as resp:",
     "with opener.open(req, timeout=30) as resp:"),
    ("budget", S, "CONFIRM_TIMEOUT = 2.5", "CONFIRM_TIMEOUT = 4.5"),
    # accounts.py: the sign-in
    ("head", A, 'if request.method != "GET":', "if False:"),
    ("web-rate", A, 'if not d.rate_ok(d.rate_key(), now, WEB_RATE_MAX, "link"):', "if False:"),
    ("state", A, "if not token or not _same(", "if not token or False and not _same("),
    ("burn-stray", A, "if held(db, now) < NONCE_STRAY:", "if False:"),
    ("stray-cap", A, "if held(db, now) < NONCE_STRAY:", "if True:"),
    ("nonce-keep", A, "NONCE_KEEP = 2 * steam.NONCE_SKEW + 60", "NONCE_KEEP = 60"),
    ("twice", A, "if len(values) != 1:", "if False:"),
    ("replay-read", A, 'if db.execute("SELECT 1 FROM linknonces WHERE nonce = ?",',
     'if False and db.execute("SELECT 1 FROM linknonces WHERE nonce = ?",'),
    ("replay-write", A, "            if not burn(db, nonce, now):", "            if False:"),
    ("replay-both", A, None, None),
    ("live-cap", A, "if live >= CODE_LIVE_MAX:", "if False:", "def link_return("),
    ("nonce-cap", A, "elif seen >= NONCE_MAX:", "elif False:"),
    ("nonce-prune", A, "(now - NONCE_KEEP,))", "(0,))"),
    ("source-cap", A, 'elif not d.rate_ok(src, now, OUT_SOURCE_MAX, "linkout1"):', "elif False:"),
    ("out-rate", A, 'elif not d.rate_ok("*", now, OUT_RATE_MAX, "linkout"):', "elif False:"),
    ("gate", A, "elif not asking.acquire(blocking=False):", "elif False:"),
    ("gate-release", A, "            asking.release()\n", "            pass\n"),
    ("cool-off", A, 'while d.rate_ok(src, now, OUT_SOURCE_MAX, "linkout1"):', "while False:"),
    ("profile-any", A, "except Exception as exc:    # a name is never",
     "except steam.Unavailable as exc:    # a name is never"),
    ("profile-text", A, "else type(exc).__name__)", "else exc)"),
    ("unavailable-page", A, 'except steam.Unavailable as exc:\n            log.warning("link: Steam unavailable',
     'except steam.Refused as exc:\n            log.warning("link: Steam unavailable'),
    ("ban-code", A, '            if not acct["banned_at"]:', "            if True:"),
    ("supersede", A, '" WHERE steamid = ? AND used_at = 0 AND code != ?",',
     '" WHERE steamid = ? AND used_at = -1 AND code != ?",'),
    ("code-prune", A, "(now - CODE_KEEP,))", "(0,))", "def link_return("),
    ("escape", A, 'who = html.escape(acct["name"] or "Steam account " + steamid)',
     'who = (acct["name"] or "Steam account " + steamid)'),
    ("secure", A, 'secure = parts.scheme == "https"', "secure = False"),
    ("cookie-host", A, 'cookie = "__Host-ftl" if secure else "ftl"', 'cookie = "ftl"'),
    ("cookie-path", A, 'cookie_path = "/" if secure else parts.path + "/link"',
     'cookie_path = parts.path + "/link"'),
    ("cookie-gone", A, "resp.delete_cookie(cookie, path=cookie_path,",
     'resp.delete_cookie(cookie, path="/x",'),
    ("http-public", A, 'if parts.scheme == "http" and host != "localhost":', "if False:"),
    ("url-prefix", A, "ok = bool(_URL_OK.fullmatch(url))", "ok = bool(_URL_OK.match(url))"),
    ("off", A, "    if not board_url:\n        log.info", "    if False:\n        log.info"),
    # accounts.py: the lobby routes
    ("key", A, "return bool(secret and key and _same(key, secret)) and d.is_trusted(src)",
     "return d.is_trusted(src)"),
    ("trusted", A, "return bool(secret and key and _same(key, secret)) and d.is_trusted(src)",
     "return bool(secret and key and _same(key, secret))"),
    ("acct-marker", A, "d.game_json(dict(payload, acct=1))", "d.game_json(dict(payload))"),
    ("lobby-flood", A, "        if not d.rate_ok(src, now, flood, bucket):", "        if False:"),
    ("link-order", A, 'now, src, early = lobby_call(LINK_FLOOD_MAX, "linkflood")',
     'now, src, early = lobby_call(LINK_RATE_MAX, "linkapi")'),
    ("link-rate", A, 'if not d.rate_ok(src, now, LINK_RATE_MAX, "linkapi"):', "if False:"),
    ("one-bucket", A, 'LINK_RATE_MAX, "linkapi"):', 'LINK_RATE_MAX, "acct"):'),
    ("tries", A, 'if not d.rate_ok(peer, now, TRY_RATE_MAX, "linktry"):', "if False:"),
    ("tries-guid", A, '        peer = peer_of(request.form.get("ip"))\n'
     '        if not d.rate_ok(peer, now, TRY_RATE_MAX, "linktry"):',
     '        peer = request.form.get("player") or "?"\n'
     '        if not d.rate_ok(peer, now, TRY_RATE_MAX, "linktry"):'),
    ("acct-peer", A, 'if not d.rate_ok(peer, now, ACCT_PEER_MAX, "acctpeer"):', "if False:"),
    ("peer-port", A, "    for cand in (raw, raw.rpartition(\":\")[0]):", "    for cand in (raw,):"),
    ("hello-nonce", A, '        if not _STATE.fullmatch(nonce):\n            return d.fail(400, "bad nonce")',
     "        if False:\n            pass", "def account_status("),
    ("hello-why", A, 'return game({"linked": 0, "why": why})', 'return game({"linked": 0})'),
    ("pin-shape", A, "        if pin and not _PIN.fullmatch(pin):", "        if False:"),
    ("pin-prefix", A, "_PIN.fullmatch(pin)", "_PIN.match(pin)"),
    # accounts.py: a code's life -- read before the signature, again under the lock
    ("expiry", A, 'or row["issued_at"] < now - CODE_TTL:', "or False:"),
    ("expiry-pre", A, '"SELECT code, shown FROM linkcodes WHERE used_at = 0 AND issued_at >= ?",\n'
     "                (now - CODE_TTL,)):",
     '"SELECT code, shown FROM linkcodes WHERE used_at = 0 AND issued_at >= ?",\n'
     "                (0,)):"),
    ("expiry-both", A, None, None),
    ("expiry-edge", A, 'or row["issued_at"] < now - CODE_TTL:', 'or row["issued_at"] <= now - CODE_TTL:'),
    ("spent-read", A, 'if row is None or row["used_at"] or', "if row is None or"),
    ("spent-pre", A, '"SELECT code, shown FROM linkcodes WHERE used_at = 0 AND issued_at >= ?"',
     '"SELECT code, shown FROM linkcodes WHERE used_at >= 0 AND issued_at >= ?"'),
    ("spent-write", A, "if spent.rowcount != 1:", "if False:"),
    ("spent-all", A, None, None),
    ("proof-first", A, '            if not code:\n                return game({"ok": 0, "why": "code"})',
     "            if False:\n                pass"),
    ("tag-compare", A, "elif salted and _same(typed_tag(tag[:16], code), tag[16:]):",
     "elif salted:"),
    ("tag-compare-start", A, "if not salted and _same(code_tag(code), tag):", "if not salted:"),
    ("ban-link", A, 'if row["banned_at"]:\n            return {"ok": 0, "why": "banned"}, "", ""',
     'if False:\n            return {"ok": 0, "why": "banned"}, "", ""'),
    ("move-same", A, 'moving = old is not None and old["steamid"] != row["steamid"]',
     "moving = old is not None", "def step("),
    ("claim-read", A, '            if row["claim"] not in ("", pub):', "            if False:"),
    ("claim-write", A, "            if took.rowcount != 1:", "            if False:", "def step("),
    ("claim-both", A, None, None),
    ("claim-steal", A, None, None),
    ("claim-any", A, "\" AND used_at = 0 AND claim IN ('', ?)\", (pub, code, pub))",
     "\" AND used_at = 0 AND ? != ''\", (pub, code, pub))"),
    ("claim-confirm", A, '        if row["claim"] != pub:', "        if False:"),
    ("ask-links", A, "        if not confirming:\n", "        if False:\n"),
    ("relink-stamp", A, '" node = excluded.node, linked_at = excluded.linked_at",',
     '" node = excluded.node",'),
    ("immediate", A, '            db.execute("BEGIN IMMEDIATE")\n', "", "def link_redeem("),
    # accounts.py: the key proof
    ("proof-shape", A, "        if not (_HEX64.fullmatch(pub) and _HEX128.fullmatch(sig)"
     " and _HEX64.fullmatch(gcode)\n"
     "                and _SERVER.fullmatch(server) and keyed in (\"0\", \"1\")):",
     "        if keyed not in (\"0\", \"1\"):"),
    # accounts.py: the game code a proof names
    ("game-foreign", A, "        if not known:\n            log.warning(\"link: key %s signed under game code",
     "        if False:\n            log.warning(\"link: key %s signed under game code"),
    ("game-unread", A, "        if known is None:\n            return (\"later\",) + none\n", ""),
    ("game-unread-ours", A, "return None if unknown or not ours_now else False",
     "return True if unknown or not ours_now else False"),
    ("game-signed", A, "\\nkey %d\\ncode %s\\n\"", "\\nkey %d\\ncode %.0s\\n\""),
    ("game-shape", A, " and _HEX64.fullmatch(gcode)\n", "\n"),
    ("game-redeploy", A, "            if held is not None and held[0] == key:",
     "            if held is not None:"),
    ("game-empty", A, " or len(data) != key[2] or not data:", " or len(data) != key[2]:"),
    ("game-sealed", A, '"%s %s %s" % (sig, server, gcode)))', '"%s %s %s" % (sig, server, "0" * 64)))'),
    ("game-seal-read", A, "TICKS_START, 1, part[2], (\"verify-open\", OPEN_VERIFY_MAX))",
     "TICKS_START, 1, sorted(code_said[\"set\"])[0], (\"verify-open\", OPEN_VERIFY_MAX))"),
    ("proof-sig-prefix", A, "_HEX128.fullmatch(sig)", "_HEX128.match(sig)"),
    ("proof-verify", A, "return bool(ed.verify(bytes.fromhex(pub), msg, bytes.fromhex(sig)))",
     "return True"),
    ("proof-budget", A, 'if ed is None or not d.rate_ok("*", now, budget[1], budget[0]):',
     "if ed is None:"),
    ("budget-split", A, '("verify-hello", HELLO_VERIFY_MAX), key_needed=False)',
     '("verify-link", HELLO_VERIFY_MAX), key_needed=False)'),
    ("statement", A, "nonce %s\\nkind %d\\nkey %d\\n", "nonce %s\\nkind %d\\nkey %d \\n"),
    ("kind-hello", A, "TICKS_HELLO, TICKS_ASK, TICKS_CONFIRM, TICKS_START = -2, -3, -4, -5",
     "TICKS_HELLO, TICKS_ASK, TICKS_CONFIRM, TICKS_START = 0, -3, -4, -5"),
    ("kind-one", A, "TICKS_HELLO, TICKS_ASK, TICKS_CONFIRM, TICKS_START = -2, -3, -4, -5",
     "TICKS_HELLO, TICKS_ASK, TICKS_CONFIRM, TICKS_START = -2, -3, -3, -5"),
    ("kind-start", A, "TICKS_HELLO, TICKS_ASK, TICKS_CONFIRM, TICKS_START = -2, -3, -4, -5",
     "TICKS_HELLO, TICKS_ASK, TICKS_CONFIRM, TICKS_START = -2, -3, -4, -3"),
    ("kind-ask", A, "why, pub = proven(now, node, ask_nonce(code), TICKS_ASK,",
     "why, pub = proven(now, node, ask_nonce(code), TICKS_CONFIRM,"),
    ("kind-confirm", A, "why, pub = proven(now, node, confirm_nonce(code, pin), TICKS_CONFIRM,",
     "why, pub = proven(now, node, confirm_nonce(code, pin), TICKS_ASK,"),
    ("kind-status", A, "why, pub = proven(now, node, nonce, TICKS_HELLO,",
     "why, pub = proven(now, node, nonce, TICKS_ASK,"),
    ("tag-code", A, 'TAG_CODE = "ftesurf-code "', 'TAG_CODE = "ftesurf-link "'),
    ("tag-ask", A, 'TAG_ASK = "ftesurf-link "', 'TAG_ASK = "ftesurf-link"'),
    ("tag-confirm", A, 'TAG_CONFIRM = "ftesurf-confirm "', 'TAG_CONFIRM = "ftesurf-link "'),
    ("confirm-pin", A, 'return _tagged(TAG_CONFIRM, code + " " + pin)', "return _tagged(TAG_CONFIRM, code)"),
    ("confirm-nonce", A, "confirm_nonce(code, pin), TICKS_CONFIRM,", "ask_nonce(code), TICKS_CONFIRM,"),
    ("addr-refuse", A, "        if not here:\n", "        if False:\n"),
    ("addr-later", A, "        if here is None:\n", "        if False:\n"),
    ("addr-port", A, 'if not sep or not port.isdigit() or node != "p" + port:',
     "if not sep or not port.isdigit():"),
    ("addr-port-empty", A, 'if not sep or not port.isdigit() or node != "p" + port:',
     'if not sep or node != "p" + port:'),
    ("addr-mapped", A, 'addr = getattr(addr, "ipv4_mapped", None) or addr', "pass"),
    ("addr-listed", A, "        if addr in own_hosts:\n            return True", "        if False:\n            return True"),
    ("addr-unset", A, "        if not name:\n            return False", "        if False:\n            return False"),
    ("addr-ttl", A, 'fresh = looked["at"] is not None and now - looked["at"] <= HOSTS_TTL',
     'fresh = looked["at"] is not None'),
    ("addr-retry", A, 'or now - looked["tried"] > HOSTS_RETRY):', "or True):"),
    ("addr-retry-never", A, 'or now - looked["tried"] > HOSTS_RETRY):', "or False):"),
    ("addr-stale", A, 'if looked["at"] is None or now - looked["at"] > HOSTS_STALE:',
     'if looked["at"] is None:'),
    ("addr-never", A, 'if looked["at"] is None or now - looked["at"] > HOSTS_STALE:', "if False:"),
    # accounts.py: unlinking on the site
    ("unlink-mac", A, "if not good or not _same(good, m.group(0)) or not -60",
     "if not good or not -60"),
    ("unlink-secret", A, 'b"surfd unlink " + secret.encode("utf-8")', 'b"surfd unlink "'),
    ("unlink-ttl", A, " or not -60 <= now - at <= UNLINK_TTL:", ":"),
    ("unlink-ttl-edge", A, "<= now - at <= UNLINK_TTL:", "<= now - at < UNLINK_TTL:"),
    ("unlink-ask", A, '            if step == "ask":', "            if False:"),
    ("unlink-shape", A, 'm = _UNLINK.fullmatch(request.args.get("t", ""))',
     'm = _UNLINK.match(request.args.get("t", ""))'),
    ("unlink-browser", A, '            ("%s.%d.%s" % (body, linked_at, hashlib.sha256(\n'
     '                browser.encode("utf-8", "replace")).hexdigest())).encode("ascii"),',
     '            ("%s.%d" % (body, linked_at)).encode("ascii"),'),
    ("unlink-stamp", A, '            ("%s.%d.%s" % (body, linked_at, hashlib.sha256(\n'
     '                browser.encode("utf-8", "replace")).hexdigest())).encode("ascii"),',
     '            ("%s.%s" % (body, hashlib.sha256(\n'
     '                browser.encode("utf-8", "replace")).hexdigest())).encode("ascii"),'),
    ("unlink-cookie", A, "resp.set_cookie(ucookie, browser, max_age=UNLINK_TTL, path=cookie_path,",
     'resp.set_cookie("x" + ucookie, browser, max_age=UNLINK_TTL, path=cookie_path,'),
    ("unlink-host", A, 'ucookie = "__Host-ftu" if secure else "ftu"', 'ucookie = "ftu"'),
    ("code-len", A, "CODE_LEN = 12 ", "CODE_LEN = 10 "),
    ("code-dash", A, 'return "-".join(code[i:i + 4] for i in range(0, len(code), 4))',
     'return "-".join(code[i:i + 6] for i in range(0, len(code), 6))'),
    # schema 13
    ("links-12", A, "CREATE TABLE IF NOT EXISTS linkcodes (",
     "CREATE TABLE IF NOT EXISTS links (player TEXT PRIMARY KEY, steamid TEXT NOT NULL,"
     " pub TEXT NOT NULL DEFAULT '', node TEXT NOT NULL DEFAULT '', linked_at INTEGER NOT NULL);\n"
     "CREATE INDEX IF NOT EXISTS links_steamid ON links (steamid);\n"
     "CREATE TABLE IF NOT EXISTS linkcodes ("),
    ("schema-13", "surfd.py", "accounts.upgrade_13(conn)", "pass"),
    ("schema-13-claim", A,
     'if "claim" not in {r[1] for r in conn.execute("PRAGMA table_info(linkcodes)")}:', "if False:"),
    ("schema-13-keep", A, '        if not conn.execute("SELECT 1 FROM links LIMIT 1").fetchone():',
     "        if True:"),
    # accounts.py: the name
    ("game-name", A, '"name": game_name(row["name"]),', '"name": row["name"],'),
    ("name-symbols", A, 'unicodedata.category(ch)[0] in "LN"', 'unicodedata.category(ch)[0] in "LNSPC"'),
    ("name-blank", A, "and ch not in _NAME_BLANK):", "and True):"),
    ("name-bytes", A, 'while len(safe.encode("utf-8")) > NAME_BYTES:', "while len(safe) > NAME_BYTES:"),
    ("name-reserved", A, ' or safe.lower() == "console":', ":"),
    ("name-nfc", A, 'unicodedata.normalize("NFC", name or "")', '(name or "")'),
    # accounts.py: a link the game starts (Patches 619, 625)
    ("start-code-shape", A, '        if not code:\n            return d.fail(400, "bad code")',
     "        if False:\n            pass"),
    ("start-keyed", A, '        if not why and not keyed:\n            why = "proof"\n', ""),
    ("start-server", A, '        if why:\n            return game({"ok": 0, "why": why})\n        db = d.get_db()',
     '        if False:\n            return game({"ok": 0, "why": why})\n        db = d.get_db()'),
    ("start-taken", A, 'if db.execute("SELECT 1 FROM linkcodes WHERE code = ?", (code,)).fetchone():\n'
     "                # Taken:", "if False:\n                # Taken:"),
    ("start-id", A, "return \"\".join(CODE_ALPHABET[b % len(CODE_ALPHABET)] for b in raw[:CODE_LEN])",
     "return \"\".join(CODE_ALPHABET[b % len(CODE_ALPHABET)] for b in raw[1:CODE_LEN + 1])"),
    ("seal", A, "                    fits = opens(row, started, opener, now)",
     "                    fits = True"),
    ("seal-kind", A, 'TICKS_START, 1, part[2], ("verify-open", OPEN_VERIFY_MAX))',
     'TICKS_ASK, 1, part[2], ("verify-open", OPEN_VERIFY_MAX))'),
    ("seal-keyed", A, 'TICKS_START, 1, part[2], ("verify-open", OPEN_VERIFY_MAX))',
     'TICKS_START, 0, part[2], ("verify-open", OPEN_VERIFY_MAX))'),
    ("seal-opener", A, "return _tagged(TAG_START, code + \" \" + opener)",
     "return _tagged(TAG_START, code + \" \")"),
    ("seal-code", A, "return _tagged(TAG_START, code + \" \" + opener)",
     "return _tagged(TAG_START, \" \" + opener)"),
    ("seal-key", A, "return signed(now, row[\"claim\"], part[0], part[1], start_nonce(code, opener),",
     "return True or signed(now, row[\"claim\"], part[0], part[1], start_nonce(code, opener),"),
    ("seal-shape", A, "        if not (len(part) == 3 and _HEX128.fullmatch(part[0]) and "
     "_HEX64.fullmatch(part[2])\n                and _HEX64.fullmatch(row[\"claim\"])):\n"
     "            return False\n", "        if len(part) != 3:\n            return False\n"),
    ("seal-budget", A, "                if fits is None:\n", "                if False:\n"),
    ("seal-budget-own", A, 'TICKS_START, 1, part[2], ("verify-open", OPEN_VERIFY_MAX))',
     'TICKS_START, 1, part[2], ("verify-link", LINK_VERIFY_MAX))'),
    ("opener-shape", A, "    if _OPENER.fullmatch(opener):\n        return start_code_of(opener), opener",
     "    if opener:\n        return start_code_of(opener), opener"),
    ("upgrade-second", A, 'for col in ("shown", "seal"):', 'for col in ("shown",):'),
    # accounts.py: the statement of Patch 625, and the key press it carries
    ("proof-keyed", A, '        if key_needed and not keyed:\n            return "proof", ""\n', ""),
    ("proof-keyed-shape", A, 'and _SERVER.fullmatch(server) and keyed in ("0", "1")):',
     "and _SERVER.fullmatch(server)):"),
    ("proof-keyed-signed", A, "msg = (STATEMENT % (server, nonce, kind, keyed, gcode)).encode(\"utf-8\")",
     "msg = (STATEMENT % (server, nonce, kind, 1, gcode)).encode(\"utf-8\")"),
    ("hello-unkeyed", A, '("verify-hello", HELLO_VERIFY_MAX), key_needed=False)',
     '("verify-hello", HELLO_VERIFY_MAX))'),
    # Links live in a table older code never wrote (SQL_KEYS has why).
    ("old-links-kept", A, 'return conn.execute("DELETE FROM %s" % OLD_LINKS).rowcount', "return 0"),
    ("old-links-dropped", A, 'return conn.execute("DELETE FROM %s" % OLD_LINKS).rowcount',
     'return conn.execute("DROP TABLE %s" % OLD_LINKS).rowcount'),
    ("links-made", "surfd.py", "        gone = accounts.links_now(conn)\n", "        gone = 0\n"),
    ("game-seal-asked", A, "        if not known:\n            return known\n        return signed(",
     "        return signed("),
    ("game-partial", A, "return None if unknown or not ours_now else False",
     "return None if not ours_now else False"),
    ("confirm-keyed", A, "TICKS_CONFIRM,\n                                  (\"verify-link\", LINK_VERIFY_MAX))",
     "TICKS_CONFIRM,\n                                  (\"verify-link\", LINK_VERIFY_MAX), key_needed=False)"),
    ("ask-keyed", A, "TICKS_ASK,\n                                  (\"verify-link\", LINK_VERIFY_MAX))",
     "TICKS_ASK,\n                                  (\"verify-link\", LINK_VERIFY_MAX), key_needed=False)"),
    ("tag-unsalted", A, "            if shown:\n                if not salted and _same(code_tag(code), tag):",
     "            if True:\n                if not salted and _same(code_tag(code), tag):"),
    ("tag-salt", A, "return _tagged(TAG_CODE, salt + \" \" + code)", "return _tagged(TAG_CODE, \" \" + code)"),
    ("start-cap", A, "if waiting >= START_LIVE_MAX:", "if False:"),
    ("start-cap-own", A, '"SELECT COUNT(*) FROM linkcodes WHERE used_at = 0 AND shown = ?"',
     '"SELECT COUNT(*) FROM linkcodes WHERE used_at = 0 AND shown != ?"'),
    ("start-prune", A, "(now - CODE_KEEP,))", "(0,))", "def link_begin("),
    ("attach-newest", A, "\" WHERE shown != '' AND claim = ? AND used_at = 0\"",
     "\" WHERE shown != '' AND claim = ? AND used_at = -1\""),
    ("start-claim", A, '(code, now, pub, NOT_YET, "%s %s %s" % (sig, server, gcode)))',
     '(code, now, "", NOT_YET, "%s %s %s" % (sig, server, gcode)))'),
    ("wait-typed", A, 'if row is None or not row["shown"]:', "if row is None:"),
    ("wait-account", A, 'if not row["steamid"]:', "if False:"),
    ("wait-banned", A, 'if row["name"] is None or row["banned_at"]:',
     'if row["name"] is None:'),
    ("wait-rate", A,
     'return game({"state": "wait"})          # asked too often: it is still a wait', "pass"),
    ("wait-bucket", A, 'lobby_call(WAIT_FLOOD_MAX, "waitflood")',
     'lobby_call(LINK_FLOOD_MAX, "linkflood")'),
    ("wait-steps", A, 'if not d.rate_ok(peer, now, WAIT_RATE_MAX, "linkwait"):',
     'if not d.rate_ok(peer, now, WAIT_RATE_MAX, "linktry"):'),
    ("wait-move", A, 'moving = old is not None and old["steamid"] != row["steamid"]',
     "moving = old is not None", "def link_wait("),
    ("number", A, 'if row["shown"] and not _same(number_proof(row["seal"], pin, row["shown"]), shown):',
     "if False:"),
    ("number-clear", A, 'if row["shown"] and not _same(number_proof(row["seal"], pin, row["shown"]), shown):',
     'if row["shown"] and not (_same(number_proof(row["seal"], pin, row["shown"]), shown)'
     ' or _same(row["shown"], shown)):'),
    ("number-opener", A, "return _tagged(TAG_NUMBER, opener + \" \" + pin + \" \" + number)",
     "return _tagged(TAG_NUMBER, \" \" + pin + \" \" + number)"),
    ("number-pin", A, "return _tagged(TAG_NUMBER, opener + \" \" + pin + \" \" + number)",
     "return _tagged(TAG_NUMBER, opener + \" \" + number)"),
    ("number-kept", A, "(steamid, shown, opener, started))", "(steamid, shown, \"\", started))"),
    ("number-spend", A, "\" WHERE code = ? AND used_at = 0\", (now, MISMATCH, code))",
     "\" WHERE code = ? AND used_at = -1\", (now, MISMATCH, code))"),
    ("number-sent", A, '(request.form.get("shown") or "")[:32])', '"")'),
    ("number-digits", A, 'shown = "".join(secrets.choice("0123456789") for _ in range(SHOWN_LEN))',
     'shown = "".join(secrets.choice("0123456789") for _ in range(1))'),
    ("attach-start", A, "\" AND used_at = 0 AND shown != '' AND issued_at >= ?\",",
     "\" AND used_at = 0 AND issued_at >= ?\","),
    ("attached-opener", A, 'fits = _same(row["seal"], opener)', "fits = True"),
    ("attach-typed", A, None, None),
    ("attach-fresh", A, "\" AND used_at = 0 AND shown != '' AND issued_at >= ?\",",
     "\" AND used_at = 0 AND shown != '' AND issued_at >= ? - 99999\","),
    ("attach-again", A, "\" WHERE steamid = ? AND used_at = 0 AND code != ?\",",
     "\" WHERE steamid = ? AND used_at = 0 AND ? != 'x'\","),
    ("attach-contest", A, "\" WHERE code = ? AND used_at = 0\", (now, CONTESTED, started))",
     "\" WHERE code = ? AND used_at = -1\", (now, CONTESTED, started))"),
    ("attach-second", A, '                    elif row["steamid"]:\n'
     "                        # Two accounts for one start",
     "                    elif False:\n                        # Two accounts for one start"),
    ("attach-no-code", A, "                if started:\n", "                if started and False:\n"),
    ("signin-cap", A, "\"SELECT COUNT(*) FROM linkcodes WHERE used_at = 0 AND steamid != ''\"",
     "\"SELECT COUNT(*) FROM linkcodes WHERE used_at = 0\""),
    ("return-code", A, '(board_url, state, "&k=" + k if k else "")', '(board_url, state, "")'),
    ("page-code", A, '"?k=" + k if k else "")))', '"")))'),
    ("code-shape", A, "if len(code) == CODE_LEN and all(ch in CODE_ALPHABET for ch in code):",
     "if code:"),
    # surfd.py
    ("schema-step", "surfd.py", "conn.executescript(accounts.SQL)", "pass"),
    ("schema-14", "surfd.py", "accounts.upgrade_14(conn)", "pass"),
]
PAIRS = {"spent-all": ("spent-pre", "spent-read", "spent-write"),
         "replay-both": ("replay-read", "replay-write"),
         "expiry-both": ("expiry", "expiry-pre"),
         "claim-both": ("claim-read", "claim-write"),
         "claim-steal": ("claim-read", "claim-any"),
         "attach-typed": ("attach-start", "seal-shape", "attached-opener")}
# Each of these survives ALONE because the same fact is read more than once:
# an assertion's replay and a code's age, spending and claim are each checked
# before the costly step and again under the lock or by the write itself.
EXPECT = {"replay-read", "expiry", "expiry-pre", "spent-pre", "spent-read", "spent-write",
          "claim-read", "claim-write", "claim-any"}
# Patch 619: live_code is no longer only the costly step's pre-check -- /api/link/wait
# reads through it and nothing else, so `expiry-pre` and `spent-pre` now die alone.
EXPECT -= {"expiry-pre", "spent-pre"}
# A typed code named as a start is turned away three times: by the query (it
# has no `shown`), by its empty seal's shape, and by that seal not being the
# opener.
EXPECT |= {"attach-start", "seal-shape", "attached-opener"}
BY = {m[0]: m for m in M}


def run(item):
    name = item[0]
    dst = os.path.join(SCRATCH, name)
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__"))
    edits = [item[1:]]
    if name in PAIRS:
        edits = [BY[k][1:] for k in PAIRS[name]]
    for f, old, new, *within in edits:
        path = os.path.join(dst, f)
        with open(path, encoding="utf-8", newline="") as fh:
            src = fh.read()
        if within:
            # The first match inside the named function: from its marker to
            # the next definition at the same depth.
            if src.count(within[0]) != 1:
                shutil.rmtree(dst)
                return name, "BAD MUTANT (marker: %d matches)" % src.count(within[0])
            lo = src.index(within[0])
            hi = src.find("\n    def ", lo + 1)
            hi = len(src) if hi < 0 else hi
            if src.count(old, lo, hi) != 1:
                shutil.rmtree(dst)
                return name, "BAD MUTANT (%d matches in %s)" % (src.count(old, lo, hi), within[0])
            at = src.index(old, lo, hi)
            src = src[:at] + new + src[at + len(old):]
        else:
            if src.count(old) != 1:
                shutil.rmtree(dst)
                return name, "BAD MUTANT (%d matches)" % src.count(old)
            src = src.replace(old, new)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(src)
    # A private temp dir: a mutant that crashes the suite skips its cleanup,
    # and whatever it leaves has to die with this copy.
    tmp = os.path.join(dst, "tmp")
    os.makedirs(tmp)
    p = subprocess.run([sys.executable, "test_accounts.py"], cwd=dst,
                       env=dict(os.environ, TEMP=tmp, TMP=tmp, TMPDIR=tmp,
                                ACCOUNTS_TEST_TOOLS=os.path.dirname(os.path.abspath(__file__))),
                       capture_output=True, text=True, errors="replace")
    fails = [l[5:70].strip() for l in p.stdout.splitlines() if l.startswith("FAIL")]
    crash = p.returncode != 0 and "FAILURE(S)" not in p.stdout
    shutil.rmtree(dst)
    if p.returncode == 0:
        return name, "SURVIVED"
    return name, "killed by %d check(s)%s: %s" % (
        len(fails), " + crash" if crash else "", "; ".join(fails[:2]))


try:
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        results = list(pool.map(run, M))
finally:
    shutil.rmtree(SCRATCH, ignore_errors=True)
bad = []
for name, verdict in results:
    print("%-16s %s" % (name, verdict))
    survived = verdict == "SURVIVED"
    if verdict.startswith("BAD") or survived != (name in EXPECT):
        bad.append(name)
print("\n%d mutants, %d killed, %d survive alone as expected, unexpected: %s" % (
    len(results), sum(1 for _, v in results if v.startswith("killed")),
    sum(1 for n, v in results if v == "SURVIVED" and n in EXPECT), bad or "none"))
sys.exit(1 if bad else 0)
