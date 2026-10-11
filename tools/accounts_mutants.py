#!/usr/bin/env python3
"""
accounts_mutants.py -- does surfd/test_accounts.py notice when the code is wrong?

    python tools/accounts_mutants.py [surfd dir]

Each mutant is ONE textual edit to surfd/steam.py, accounts.py or surfd.py in a
throwaway copy of the surfd tree, and the suite must fail on it.  One line per
mutant, then the count; exit 1 if a mutant survives that should not, or if a
mutant's text no longer matches the source (BAD MUTANT: the code moved, so move
the mutant with it).  About half an hour; nothing outside the temp dir is
written.

EVERY SUITE RUNS ONCE ON AN UNMUTATED COPY FIRST, in the sweep's own
environment, and the sweep stops (exit 2) if one fails there: a suite that
fails by itself "kills" every mutant, and a crash counts as a kill, so
without that control nothing says the sweep cannot measure (Patches 662 to
665 ran so).  ACCOUNTS_MUTANTS_ONLY=<prefix> sweeps the mutants whose names
start with it and says so in the count.

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
    # Patch 629: ranked means linked (test_ranked.py).
    ("rank-linked", A, "        live = (sid, \"\") if state == RANK_LINKED else (install, state)",
     "        live = (install, \"\") if state == RANK_LINKED else (install, state)"),
    ("rank-banned", A, "        if state == RANK_BANNED:\n            return RANK_BANNED, sid\n", ""),
    ("rank-banned-since", A, "        if row is None or row[0]:\n            return RANK_BANNED, player",
     "        if row is None:\n            return RANK_BANNED, player"),
    ("rank-nobody", "surfd.py", "        if acct_why:\n            tier = TIER_COMMUNITY\n",
     "        if acct_why:\n            tier = TIER_RANKED\n"),
    ("rank-why", "surfd.py", "                    \"why\": acct_why})\n\n\ndef _ban_late(db, player):",
     "                    \"why\": \"\"})\n\n\ndef _ban_late(db, player):"),
    ("rank-why-own", "surfd.py", "        if acct_why and tier != TIER_RANKED:\n            acct_why = \"\"",
     "        if False:\n            acct_why = \"\""),
    ("rank-key-shape", A, "    if not _HEX64.fullmatch(pub or \"\"):\n        return RANK_UNPROVEN, \"\"",
     "    if not pub:\n        return RANK_UNPROVEN, \"\""),
    ("rank-ban-read", A, "    return (RANK_BANNED if row[1] else RANK_LINKED), row[0]",
     "    return RANK_LINKED, row[0]"),
    ("rank-leaf", "surfd.py", "want = hashlib.sha256(install.encode(\"utf-8\", \"replace\")).hexdigest()[:8]",
     "want = hashlib.sha256(player.encode(\"utf-8\", \"replace\")).hexdigest()[:8]"),
    ("rank-switch-on", "surfd.py", "RANKED_LINKED = (setting(\"SURFD_RANKED_LINKED\") or \"1\").strip() != \"0\"",
     "RANKED_LINKED = True"),
    ("rank-switch-off", "surfd.py", "RANKED_LINKED = (setting(\"SURFD_RANKED_LINKED\") or \"1\").strip() != \"0\"",
     "RANKED_LINKED = (setting(\"SURFD_RANKED_LINKED\") or \"0\").strip() != \"0\""),
    # ...one identity a run
    ("pin-read", A, "            pin = pinned()              # whoever pinned it first",
     "            pin = None                  # whoever pinned it first"),
    ("pin-kept", A, "    pin = pinned() if runid else None", "    pin = None"),
    ("pin-install", A, "    if pin is not None and pin[0] == install:", "    if pin is not None:"),
    ("pin-write", A, "        if runid and pin is None:\n            db.execute(\"INSERT OR IGNORE INTO runpins",
     "        if False:\n            db.execute(\"INSERT OR IGNORE INTO runpins"),
    ("pin-prune", A, "    conn.execute(\"DELETE FROM runpins WHERE at < ?\", (int(time.time()) - PIN_KEEP,))\n", ""),
    ("pin-runid-untrusted", "surfd.py", "        log.warning(\"ignoring runid from untrusted source %s\", src)\n        runid = \"\"\n\n    # WHOSE",
     "        log.warning(\"ignoring runid from untrusted source %s\", src)\n\n    # WHOSE"),
    # ...an install is never named like an account; the key is a lobby's word
    ("guid-steamid", A, "    if steam.is_steamid64(guid) or (guid.isdigit() and len(guid) == 17):\n        return False\n",
     ""),
    ("guid-digits", A, "    if steam.is_steamid64(guid) or (guid.isdigit() and len(guid) == 17):",
     "    if steam.is_steamid64(guid):"),
    ("guid-shape", A, "    return bool(_GUID.fullmatch(guid)) if strict else True", "    return True"),
    ("guid-strict-off", A, "    return bool(_GUID.fullmatch(guid)) if strict else True",
     "    return bool(_GUID.fullmatch(guid))"),
    ("pub-untrusted", "surfd.py", "            log.warning(\"ignoring pub from untrusted source %s\", src)\n            pub = \"\"",
     "            log.warning(\"ignoring pub from untrusted source %s\", src)"),
    # ...the move
    ("rank-move-all", A, "        \" AND (tier = 'ranked' OR tier LIKE 'ranked@%' OR tier LIKE 'ranked^%')\"\n"
     "        \" AND \" + SQL_NOT_ACCOUNT).fetchall()",
     "        \" AND (tier = 'ranked' OR tier LIKE 'ranked@%' OR tier LIKE 'ranked^%')\"\n"
     "        ).fetchall()"),
    ("rank-move-shape", A, "SQL_NOT_ACCOUNT = \"player NOT IN (SELECT steamid FROM accounts)\"",
     "SQL_NOT_ACCOUNT = \"NOT (length(player) = 17 AND player GLOB '7656119*')\""),
    ("rank-move-tags", A, "(tier = 'ranked' OR tier LIKE 'ranked@%' OR tier LIKE 'ranked^%')",
     "(tier = 'ranked')"),
    ("rank-move-recs", A, "        \"UPDATE replays SET tier = 'community' WHERE tier = 'ranked' AND kind = 'run'\"",
     "        \"UPDATE replays SET tier = 'community' WHERE 0 AND tier = 'ranked' AND kind = 'run'\""),
    ("rank-move-better", A, "        if there is not None and there[1] <= millis:", "        if False:"),
    ("rank-move-worse", A, "        if there is not None and there[1] <= millis:", "        if there is not None:"),
    ("rank-move-off", "surfd.py", "        if RANKED_LINKED:\n            moved = accounts.ranked_now(conn, TIERS_IMPORTED)",
     "        if True:\n            moved = accounts.ranked_now(conn, TIERS_IMPORTED)"),
    ("rank-move-never", "surfd.py", "        if RANKED_LINKED:\n            moved = accounts.ranked_now(conn, TIERS_IMPORTED)",
     "        if False:\n            moved = accounts.ranked_now(conn, TIERS_IMPORTED)"),
    ("rank-move-lock", A, "    conn.execute(\"BEGIN IMMEDIATE\")\n    moved = 0\n", "    moved = 0\n"),
    ("rank-move-index", A, "return (\"CREATE INDEX IF NOT EXISTS runs_live ON runs (tier, player) WHERE tier NOT IN (%s)\"",
     "return (\"CREATE INDEX IF NOT EXISTS runs_live ON runs (tier, player) WHERE tier IN (%s)\""),
    ("pin-key", A, "        if not why and not (pub and _same(pub, pin[3])):\n            return RANK_HELD, player",
     "        if False:\n            return RANK_HELD, player"),
    ("pin-key-empty", A, "        if not why and not (pub and _same(pub, pin[3])):",
     "        if not why and pub and not _same(pub, pin[3]):"),
    ("pin-key-kept", A, "                        pub if state == RANK_LINKED else \"\"))",
     "                        \"\"))"),
    ("pin-refresh", A, "        if now - pin[4] > 86400:", "        if False:"),
    ("pin-upgrade", A, "    if \"pub\" not in {r[1] for r in conn.execute(\"PRAGMA table_info(runpins)\")}:",
     "    if False:"),
    ("pin-upgrade-kept", A, "                raise\n        conn.execute(\"DELETE FROM runpins\")",
     "                raise"),
    ("held-why", "surfd.py", "                            \"why\": accounts.RANK_HELD})",
     "                            \"why\": accounts.RANK_UNPROVEN})"),
    ("pin-held-stored", "surfd.py", "        if acct_why == accounts.RANK_HELD:", "        if False:"),
    # Patch 639: Steam pictures
    ("av-banned", "surfd.py",
     "        if banned or not accounts.avatar_ok(h):",
     "        if not accounts.avatar_ok(h):"),
    ("av-on-disk", "surfd.py",
     "        if not os.path.isfile(base + \".jpg\"):\n            continue\n        new[\"site\"][sid] = h",
     "        new[\"site\"][sid] = h"),
    ("av-game-copy", "surfd.py",
     "        if os.path.isfile(base + \".txt\"):\n            new[\"game\"][sid] = h",
     "        if True:\n            new[\"game\"][sid] = h"),
    ("av-twice", "surfd.py",
     "        if marks[mark] > 1:",
     "        if False:"),
    ("av-twice-pictured", "surfd.py",
     "        marks[mark] = marks.get(mark, 0) + 1\n        if banned or not accounts.avatar_ok(h):\n            continue\n        base = os.path.join(AVATAR_DIR, h)\n        if not os.path.isfile(base + \".jpg\"):\n            continue",
     "        if banned or not accounts.avatar_ok(h):\n            continue\n        base = os.path.join(AVATAR_DIR, h)\n        if not os.path.isfile(base + \".jpg\"):\n            continue\n        marks[mark] = marks.get(mark, 0) + 1"),
    ("av-game-linked", "surfd.py",
     "    if not RANKED_LINKED or not re.fullmatch(r\"[0-9a-f]{8}\", who or \"\"):",
     "    if not re.fullmatch(r\"[0-9a-f]{8}\", who or \"\"):"),
    ("av-row-game", "surfd.py",
     "        pics = avatars(now, db)[\"game\"]",
     "        pics = {}"),
    ("av-row-game-site", "surfd.py",
     "        pics = avatars(now, db)[\"game\"]",
     "        pics = avatars(now, db)[\"site\"]"),
    ("av-row-site", "surfd.py",
     "        if row[\"player\"] in pics:\n            row[\"av\"] = 1               # /board/avatar/<who> has their picture",
     "        if False:\n            row[\"av\"] = 1"),
    ("av-row-all", "surfd.py",
     "            if row[\"player\"] in pics:\n                row[\"av\"] = 1",
     "            if True:\n                row[\"av\"] = 1"),
    ("av-list", "surfd.py",
     "        if e[\"who\"] in pics:",
     "        if False:"),
    ("av-page", "surfd.py",
     "                  \"av\": 1 if player in pics else 0,",
     "                  \"av\": 0,"),
    ("av-bucket", "surfd.py",
     "    if not rate_ok(rate_key(), now, WEB_AVATAR_MAX, \"avatar\"):",
     "    if not rate_ok(rate_key(), now, WEB_SHOT_MAX, \"webshot\"):"),
    ("av-ban-now", "admin.py",
     "            if bans.get(\"changed\"):\n                bans[\"changed\"]()",
     "            if False:\n                bans[\"changed\"]()"),
    ("av-hash-shape", A,
     "    return isinstance(h, str) and re.fullmatch(r\"[0-9a-f]{40}\", h) is not None",
     "    return isinstance(h, str)"),
    ("pic-magic", "steamsync.py",
     "            if data[:3] != b\"\\xff\\xd8\\xff\" or (pillow and form is None):",
     "            if pillow and form is None:"),
    ("pic-opened", "steamsync.py",
     "            if data[:3] != b\"\\xff\\xd8\\xff\" or (pillow and form is None):",
     "            if data[:3] != b\"\\xff\\xd8\\xff\":"),
    ("pic-dry", "steamsync.py",
     "            if not go:\n                fetched += not have_jpg\n                asks += not have_jpg\n                made += pillow and not have_txt\n                continue",
     "            if False:\n                continue"),
    ("pic-once", "steamsync.py",
     "            if have_jpg and (have_txt or not pillow):\n                continue",
     "            if False:\n                continue"),
    ("pic-refused", "steamsync.py",
     "                    if not _refused(exc):",
     "                    if True:"),
    ("pic-throttled", "steamsync.py",
     "            return int(text[7:]) in _NOT_THIS_ONE",
     "            return 300 <= int(text[7:]) < 500"),
    ("pic-down", "steamsync.py",
     "                        break\n                    data = b\"\"",
     "                        pass\n                    data = b\"\""),
    ("pic-bad-wait", "steamsync.py",
     "            if os.path.isfile(bad) and 0 <= now - os.path.getmtime(bad) < BAD_RETRY:\n                continue",
     "            if False:\n                continue"),
    ("pic-bad-forever", "steamsync.py",
     "            if os.path.isfile(bad) and 0 <= now - os.path.getmtime(bad) < BAD_RETRY:",
     "            if os.path.isfile(bad):"),
    ("pic-bad-mark", "steamsync.py",
     "                _write(bad, b\"\")\n                os.utime(bad, (now, now))",
     "                pass"),
    ("pic-bad-clock", "steamsync.py",
     "                os.utime(bad, (now, now))",
     "                pass"),
    ("pic-bad-drop", "steamsync.py",
     "                if have_jpg:\n                    os.remove(jpg)",
     "                if False:\n                    os.remove(jpg)"),
    ("pic-prune", "steamsync.py",
     "    pruned = prune(directory, set(hashes)) if go and all_asked else 0",
     "    pruned = 0"),
    ("pic-prune-dry", "steamsync.py",
     "    pruned = prune(directory, set(hashes)) if go and all_asked else 0",
     "    pruned = prune(directory, set(hashes)) if all_asked else 0"),
    ("pic-prune-ours", "steamsync.py",
     "        if _OURS.fullmatch(name) and name[:40] not in keep:",
     "        if name[:40] not in keep:"),
    ("pic-prune-keep", "steamsync.py",
     "        if _OURS.fullmatch(name) and name[:40] not in keep:",
     "        if _OURS.fullmatch(name):"),
    ("pic-oserror", "steamsync.py",
     "        except OSError as exc:\n            # One picture's file trouble is not the next one's.",
     "        except ZeroDivisionError as exc:\n            # One picture's file trouble is not the next one's."),
    ("pic-tmp", "steamsync.py",
     "    finally:\n        if os.path.exists(tmp):",
     "    finally:\n        if False:"),
    ("pic-size", "steamsync.py",
     "    return (\"FTESURF-AVATAR 1 %d %d\\n\" % (GAME_PX, GAME_PX)",
     "    return (\"FTESURF-AVATAR 1 %d %d\\n\" % (GAME_PX, GAME_PX + 1)"),
    ("pic-big", "steamsync.py",
     "        if max(img.size) > 1024:",
     "        if False:"),
    # Patch 660: the imported rows' players
    ("ppl-ours", "surfd.py",
     "        if sid in ours:\n            continue\n        new[\"site\"][sid] = h",
     "        new[\"site\"][sid] = h"),
    ("ppl-mark-two", "surfd.py",
     "        if not game or shared[mark] > 1 or mark in marks:",
     "        if not game or mark in marks:"),
    ("ppl-mark-acct", "surfd.py",
     "        if not game or shared[mark] > 1 or mark in marks:",
     "        if not game or shared[mark] > 1:"),
    ("ppl-txt", "surfd.py",
     "        if not game or shared[mark] > 1 or mark in marks:",
     "        if shared[mark] > 1 or mark in marks:"),
    ("ppl-jpg", "surfd.py",
     "        if not accounts.avatar_ok(h) or h + \".jpg\" not in names:",
     "        if not accounts.avatar_ok(h):"),
    ("ppl-hash-shape", "surfd.py",
     "        if not accounts.avatar_ok(h) or h + \".jpg\" not in names:",
     "        if h + \".jpg\" not in names:"),
    ("ppl-stamp", "surfd.py",
     "    elif stamp != _avb[\"stamp\"]:\n        _board_kick(stamp)",
     "    elif False:\n        _board_kick(stamp)"),
    ("ppl-every-look", "surfd.py",
     "    elif stamp != _avb[\"stamp\"]:\n        _board_kick(stamp)",
     "    elif True:\n        _board_kick(stamp)"),
    ("ppl-inline", "surfd.py",
     "    elif stamp != _avb[\"stamp\"]:\n        _board_kick(stamp)",
     "    elif stamp != _avb[\"stamp\"]:\n        _board_install(*_board_build(db), stamp=stamp)"),
    ("ppl-fail-empty", "surfd.py",
     "            log.exception(\"imported players' pictures: the table was not rebuilt\")",
     "            _board_install({}, {}, stamp=stamp)"),
    ("ppl-fail-stamped", "surfd.py",
     "            conn = connect()\n            try:\n                built = _board_build(conn)\n            finally:\n                conn.close()\n            _board_install(*built, stamp=stamp)",
     "            conn = connect()\n            _avb[\"stamp\"] = stamp\n            try:\n                built = _board_build(conn)\n            finally:\n                conn.close()\n            _board_install(*built, stamp=stamp)"),
    ("ppl-ban-drops", "surfd.py",
     "    global _av\n    _av = _av_none\n",
     "    global _av\n    _av = _av_none\n    _avb.update(stamp=None, people={}, marks={})\n"),
    ("ppl-patience", "steamsync.py",
     "        got = ask(key, chunk, patient(http), out)",
     "        got = ask(key, chunk, http, out)"),
    ("ppl-again", "steamsync.py",
     "        (int(now) - PEOPLE_AGAIN, limit))]",
     "        (int(now), limit))]"),
    ("ppl-unknown", "steamsync.py",
     "                    conn.execute(\"UPDATE boardpics SET asked_at = ? WHERE steamid = ?\",\n                                 (int(now), sid))",
     "                    if p:\n                        conn.execute(\"UPDATE boardpics SET asked_at = ? WHERE steamid = ?\",\n                                     (int(now), sid))"),
    ("ppl-nopic", "steamsync.py",
     "                    if p and p[\"avatar\"]:",
     "                    if p:"),
    ("ppl-scan-daily", "steamsync.py",
     "        due = not 0 <= now - os.path.getmtime(stamp) < PEOPLE_SCAN",
     "        due = True"),
    ("ppl-empty-scan", "steamsync.py",
     "    if due or not have:",
     "    if due:"),
    ("ppl-dry", "steamsync.py",
     "        if go:\n            try:\n                with conn:\n                    conn.executemany(\"INSERT OR IGNORE",
     "        if True:\n            try:\n                with conn:\n                    conn.executemany(\"INSERT OR IGNORE"),
    ("ppl-dry-ask", "steamsync.py",
     "    if not go:\n        # The never-asked go first",
     "    if False:\n        # The never-asked go first"),
    ("ppl-gone", "steamsync.py",
     "                                     [(sid,) for sid in gone])",
     "                                     [])"),
    ("ppl-zero", "steamsync.py",
     "    if not limit:\n        return 0, 0, 0, 0",
     "    if False:\n        return 0, 0, 0, 0"),
    ("ppl-down", "steamsync.py",
     "        if got is None:\n            break\n        try:\n            with conn:",
     "        if got is None:\n            got = {}\n        try:\n            with conn:"),
    ("ppl-busy", "steamsync.py",
     "        except sqlite3.OperationalError as exc:\n            out(\"the database was busy (%s); %d asked about\" % (exc, asked))\n            break",
     "        except ZeroDivisionError as exc:\n            out(\"the database was busy (%s); %d asked about\" % (exc, asked))\n            break"),
    ("ppl-busy-counted", "steamsync.py",
     "        except sqlite3.OperationalError as exc:\n            out(\"the database was busy (%s); %d asked about\" % (exc, asked))\n            break\n        asked += len(chunk)",
     "        except sqlite3.OperationalError as exc:\n            out(\"the database was busy (%s); %d asked about\" % (exc, asked))\n            asked += len(chunk)\n            break\n        asked += len(chunk)"),
    ("ppl-limit", "steamsync.py",
     "        \"SELECT steamid FROM boardpics WHERE asked_at <= ? ORDER BY asked_at, steamid LIMIT ?\",\n        (int(now) - PEOPLE_AGAIN, limit))]",
     "        \"SELECT steamid FROM boardpics WHERE asked_at <= ? ORDER BY asked_at, steamid LIMIT ?\",\n        (int(now) - PEOPLE_AGAIN, 1000000))]"),
    ("ppl-tier", "steamsync.py",
     "PEOPLE_SQL = (\"SELECT DISTINCT +player FROM runs WHERE tier IN (%s) AND length(player) = 17\"",
     "PEOPLE_SQL = (\"SELECT DISTINCT +player FROM runs WHERE tier NOT IN (%s) AND length(player) = 17\""),
    ("ppl-plan", "steamsync.py",
     "PEOPLE_SQL = (\"SELECT DISTINCT +player FROM runs WHERE tier IN (%s) AND length(player) = 17\"\n              \" AND +player GLOB '7656119[0-9]*'\")",
     "PEOPLE_SQL = (\"SELECT DISTINCT player FROM runs WHERE tier IN (%s) AND length(player) = 17\"\n              \" AND player GLOB '7656119[0-9]*'\")"),
    ("ppl-tell", "steamsync.py",
     "    if moved or differ:\n        changed(directory, now)",
     "    if False:\n        changed(directory, now)"),
    ("ppl-tell-always", "steamsync.py",
     "    if moved or differ:\n        changed(directory, now)",
     "    if True:\n        changed(directory, now)"),
    ("ppl-tell-pictures", "steamsync.py",
     "    if go and (fetched or made or pruned):\n        changed(directory, now)",
     "    if False:\n        changed(directory, now)"),
    ("ppl-budget", "steamsync.py",
     "            if not have_jpg and budget is not None and asks >= budget:\n                continue",
     "            if False:\n                continue"),
    ("ppl-textonly", "steamsync.py",
     "            if not have_jpg and budget is not None and asks >= budget:",
     "            if budget is not None and asks >= budget:"),
    ("ppl-prune-wait", "steamsync.py",
     "    pruned = prune(directory, set(hashes)) if go and all_asked else 0",
     "    pruned = prune(directory, set(hashes)) if go else 0"),
    ("ppl-pictures", "steamsync.py",
     "    hashes += sorted(board - set(hashes))",
     "    hashes += []"),
    # Patch 638: an account's name
    ("name-row", "surfd.py", "            name = accounts.account_name(get_db(), player) or name",
     "            name = name"),
    ("name-named", A, "    return name != \"player\" and not _engine_reserved(name)", "    return not _engine_reserved(name)"),
    ("name-answer", A, "                \"named\": 1 if account_named(row[\"name\"]) else 0}",
     "                \"named\": 0}"),
    ("name-listed", "surfd.py", "        if sid in rows and accounts.account_named(raw):", "        if False:"),
    ("sync-dry", "steamsync.py", "            if go:\n                with conn:\n                    conn.execute(\"UPDATE accounts SET name = ?, avatar = ? WHERE steamid = ?\",",
     "            if True:\n                with conn:\n                    conn.execute(\"UPDATE accounts SET name = ?, avatar = ? WHERE steamid = ?\","),
    ("sync-dry-rows", "steamsync.py", "        if not go:\n            rows += conn.execute(\"SELECT COUNT(*) FROM runs\" + where, (sid, new)).fetchone()[0]\n            continue",
     "        if False:\n            continue"),
    ("sync-blank", "steamsync.py", "            if not p or not p[\"name\"]:", "            if not p:"),
    ("sync-picture", "steamsync.py", "            avatar = p[\"avatar\"] or old[1]", "            avatar = p[\"avatar\"]"),
    ("sync-imported", "steamsync.py", "    where = \" WHERE player = ? AND \" + not_imported + \" AND name <> ?\"",
     "    where = \" WHERE player = ? AND 1 = 1 AND name <> ?\""),
    ("sync-recordings", "steamsync.py", "            conn.execute(\"UPDATE replays SET name = ?\" + where",
     "            conn.execute(\"UPDATE replays SET name = name || substr(?, 1, 0)\" + where"),
    ("sync-unshowable", "steamsync.py", "        if not accounts.account_named(raw):\n            continue\n        new = accounts.game_name(raw)",
     "        new = accounts.game_name(raw)"),
    ("sync-same", "steamsync.py", "            if (old[0], old[1]) == (p[\"name\"], avatar):\n                continue",
     "            if False:\n                continue"),
    ("sync-split", "steamsync.py", "        if str(exc) not in _BAD_REPLY:", "        if True:"),
    ("name-engine-word", A, "    return name != \"player\" and not _engine_reserved(name)", "    return name != \"player\""),
    ("name-leet", A, "        c = {\"3\": \"e\", \"4\": \"a\", \"0\": \"o\", \"1\": \"l\", \"7\": \"l\"}.get(c, c).lower()",
     "        c = c.lower()"),
    ("name-spaces", A, "        if c not in \"_ ~\":\n            out.append(c)", "        out.append(c)"),
    # Patch 633: a ban
    ("ban-rows", A, "    moved, recs = ban_rows(conn, steamid, banned, imported)\n    return was, moved, recs",
     "    moved, recs = 0, 0\n    return was, moved, recs"),
    ("ban-recordings", A, "            \"UPDATE replays SET tier = 'banned:' || tier WHERE player = ? AND kind = 'run'\"",
     "            \"UPDATE replays SET tier = tier WHERE player = ? AND kind = 'run'\""),
    ("ban-imported", A, "        \" WHERE player = ? AND \" + not_imported +\n        \" AND \" + (\"NOT \" if banned else \"\") + held, (steamid,)).fetchall()",
     "        \" WHERE player = ? AND 1 AND 1 = ? AND \" + (\"NOT \" if banned else \"\") + held, (steamid, 1)).fetchall()"),
    ("ban-back", A, "        dest = BAN_TIER + tier if banned else tier[len(BAN_TIER):]",
     "        dest = BAN_TIER + tier if banned else tier"),
    ("ban-back-recordings", A, "            \"UPDATE replays SET tier = substr(tier, %d) WHERE player = ? AND kind = 'run'\"",
     "            \"UPDATE replays SET tier = substr(tier, %d - 99) WHERE player = ? AND kind = 'run'\""),
    ("ban-in-the-way", A, "        if inway is not None and (inway[1], inway[2]) <= (ms, at):", "        if False:"),
    ("ban-in-the-way-worse", A, "        if inway is not None and (inway[1], inway[2]) <= (ms, at):",
     "        if inway is not None:"),
    ("ban-in-the-way-tie", A, "        if inway is not None and (inway[1], inway[2]) <= (ms, at):",
     "        if inway is not None and inway[1] <= ms:"),
    ("ban-seen", A, "    if seen is not None and seen != (row[0] if row is not None else 0):", "    if False:"),
    ("ban-not-banned", A, "    if not banned and (row is None or not row[0]):", "    if not banned and row is None:"),
    ("ban-family", "surfd.py", "    if row is not None and row[0]:\n        return tuple(accounts.BAN_TIER + t for t in TIERS)",
     "    if False:\n        return TIERS"),
    ("ban-family-counts", "surfd.py", "    fam = _family(db, run[2])", "    fam = TIERS"),
    ("ban-evidence", "surfd.py", "            row[\"owner_banned\"] and row[\"kind\"] in (\"run\", \"evidence\")):",
     "            False):"),
    ("ban-evidence-kinds", "surfd.py", "            row[\"owner_banned\"] and row[\"kind\"] in (\"run\", \"evidence\")):",
     "            row[\"owner_banned\"]):"),
    ("ban-late", "surfd.py", "        if RANKED_LINKED and player != install:\n            _ban_late(db, player)",
     "        if False:\n            pass"),
    ("ban-late-reread", "surfd.py", "            if row is not None and row[0]:\n                moved, recs = accounts.ban_rows(db, player, True, TIERS_IMPORTED)",
     "            if True:\n                moved, recs = accounts.ban_rows(db, player, True, TIERS_IMPORTED)"),
    ("bans-now", "surfd.py", "        moved = accounts.bans_now(conn, TIERS_IMPORTED)", "        moved = (0, 0)"),
    ("bans-now-all", A, "             \" player IN (SELECT steamid FROM accounts WHERE banned_at > 0)\")",
     "             \" player IN (SELECT steamid FROM accounts)\")"),
    ("ban-note-kept", A, "        conn.execute(\"UPDATE accounts SET banned_at = 0, ban_note = CASE WHEN ? <> '' THEN ?\"",
     "        conn.execute(\"UPDATE accounts SET banned_at = 0, ban_note = CASE WHEN ? <> ? THEN ''\""),
    ("ban-file-login", "admin.py", "        def run_file(rid):\n            if not logged_in():",
     "        def run_file(rid):\n            if False:"),
    ("ban-download", "admin.py", "                \"download\": \"/admin/api/run/%d/file\" % rid,",
     "                \"download\": \"/api/replay/%d\" % rid,"),
    ("ban-nobody", A, "    if not banned and (row is None or not row[0]):", "    if False:"),
    ("ban-stub", A, "        conn.execute(\"INSERT INTO accounts (steamid, created_at) VALUES (?, ?)\", (steamid, now))",
     "        raise ValueError(\"no such account\")"),
    ("ban-date", A, "\"UPDATE accounts SET banned_at = CASE WHEN banned_at > 0 THEN banned_at\"",
     "\"UPDATE accounts SET banned_at = CASE WHEN banned_at < 0 THEN banned_at\""),
    ("ban-unban-flag", A, "        conn.execute(\"UPDATE accounts SET banned_at = 0, ban_note = CASE WHEN ? <> '' THEN ?\"",
     "        conn.execute(\"UPDATE accounts SET banned_at = banned_at, ban_note = CASE WHEN ? <> '' THEN ?\""),
    ("ban-shape", A, "    if not steam.is_steamid64(steamid):\n        raise ValueError(\"not a SteamID64\")\n    note = (note or \"\")[:BAN_NOTE_MAX]",
     "    note = (note or \"\")[:BAN_NOTE_MAX]"),
    ("ban-note", "admin.py", "            if action == \"ban\" and not note:", "            if False:"),
    ("ban-action", "admin.py", "            if action not in (\"ban\", \"unban\"):", "            if False:"),
    ("ban-list-login", "admin.py", "        def accounts_list():\n            if not logged_in():",
     "        def accounts_list():\n            if False:"),
    ("guid-seat", A, "_GUID = re.compile(r\"[0-9a-f]{32}(:[0-9]{1,2})?\")", "_GUID = re.compile(r\"[0-9a-f]{32}\")"),
    ("rank-install", A, "    if live is not None and not why and player == live[0]:\n        note_install(",
     "    if False:\n        note_install("),
    ("rank-install-once", A, "    if live is not None and not why and player == live[0]:",
     "    if not why:"),
    ("rank-install-cap", A, "(steamid,)).fetchone()[0] >= INSTALLS_MAX:", "(steamid,)).fetchone()[0] < 0:"),
    ("rank-name", "surfd.py", "or (install if player == install else \"player\")", "or install"),
    ("rank-ext", "surfd.py", "    ext = web_ext(TIER_MOMENTUM if me[\"mom\"] else TIER_KSF if me[\"ksf\"] else me[\"src\"], player)",
     "    ext = web_ext(me[\"src\"], player)"),
    ("rank-who", A, "return hashlib.sha256(steamid.encode(\"ascii\", \"replace\")).hexdigest()[:8]",
     "return hashlib.sha256(steamid.encode(\"ascii\", \"replace\")).hexdigest()[:12]"),
    ("rank-who-off", A, "        if d.ranked_linked:\n            mode[\"who\"] = who_of(row[\"steamid\"])",
     "        if True:\n            mode[\"who\"] = who_of(row[\"steamid\"])"),
    ("rank-mode-said", A, "        mode = {\"ranked\": 1} if d.ranked_linked else {}", "        mode = {}"),
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
M += [
    # Patch 662: the game's player search and breakdown (surfd/test_web.py).
    ("gp-route-players", "surfd.py",
     '    if request.args.get("players") is not None:     # Patch 662: see game_players',
     "    if False:"),
    ("gp-route-player", "surfd.py",
     '    if request.args.get("player") is not None:      # ...and game_player',
     "    if False:"),
    ("gp-order", "surfd.py",
     "        r = 2 if not q or not key.startswith(q) else 0 if key == q else 1",
     "        r = 2"),
    ("gp-exact", "surfd.py",
     "        r = 2 if not q or not key.startswith(q) else 0 if key == q else 1",
     "        r = 2 if not q or not key.startswith(q) else 1"),
    ("gp-cap", "surfd.py",
     "    for e in (ranks[0] + ranks[1] + ranks[2])[:GAME_SEARCH_MAX]:",
     "    for e in ranks[0] + ranks[1] + ranks[2]:"),
    ("gp-miss", "surfd.py",
     "        if q and q not in key:\n            continue\n        r = 2 if",
     "        r = 2 if"),
    ("gp-plain", "surfd.py",
     '    q = web_plain(clean_text(raw, 64) or "").lower()\n    try:\n        db = get_db()\n'
     "        by_handle, people = web_people(db, now)",
     '    q = clean_text(raw, 64) or ""\n    try:\n        db = get_db()\n'
     "        by_handle, people = web_people(db, now)"),
    ("gp-search-av", "surfd.py",
     '        if by_handle.get(e["who"]) in have:\n            row["av"] = 1',
     '        if e["who"] in have:\n            row["av"] = 1'),
    ("gp-search-av-all", "surfd.py",
     '        if by_handle.get(e["who"]) in have:\n            row["av"] = 1',
     '        row["av"] = 1'),
    ("gp-shape", "surfd.py",
     'if not re.fullmatch(r"[0-9a-f]{8}|[0-9a-f]{%d}" % WEB_HANDLE_LEN, raw):',
     'if not re.fullmatch(r"[0-9a-f]{8,%d}" % WEB_HANDLE_LEN, raw):'),
    ("gp-mark", "surfd.py",
     '                handle = _people.get("by_mark", {}).get(raw)',
     "                handle = None"),
    ("gp-mark-shared", "surfd.py",
     "        marks[h[:8]] = None if h[:8] in marks else h",
     "        marks[h[:8]] = h"),
    ("gp-figures", "surfd.py",
     "    wr, wrc, top10, comp = _profile_figures(ranked, main_maps)\n"
     '    rows = [{"map"',
     "    wrc, wr, top10, comp = _profile_figures(ranked, main_maps)\n"
     '    rows = [{"map"'),
    ("gp-disp", "surfd.py",
     '    rows = [{"map": bsp.get(r["map"], r["map"]), "track": r["track"], "leg": r["leg"],',
     '    rows = [{"map": r["map"].upper(), "track": r["track"], "leg": r["leg"],'),
    ("gp-offset", "surfd.py",
     "            for r, rk, of in ranked[offset:offset + limit]]",
     "            for r, rk, of in ranked[:limit]]"),
    ("gp-limit", "surfd.py",
     '    limit = clamp_int(request.args.get("limit"), 1, GAME_PROFILE_MAX, GAME_PROFILE_ROWS)',
     '    limit = clamp_int(request.args.get("limit"), 1, WEB_PROFILE_MAX, WEB_PROFILE_ROWS)'),
    ("gp-gate", "surfd.py",
     "    if len(raw) == 8 and not RANKED_LINKED:",
     "    if False:"),
    ("gp-kick", "surfd.py",
     "                _people_kick(now)           # player_of's rule for a miss: a new player's own mark",
     "                pass"),
    ("gp-stop", "surfd.py",
     "        elif not q or r == 0:",
     "        elif not q:"),
    ("gp-utf8-search", "surfd.py",
     '    return Response(game_json({"v": 1, "t": now, "q": q, "players": out}),',
     '    return Response(json.dumps({"v": 1, "t": now, "q": q, "players": out}),'),
    ("gp-utf8-player", "surfd.py",
     '    return Response(game_json(\n        {"v": 1, "t": now, "who": handle, "name": me["name"], "src": me["src"],',
     '    return Response(json.dumps(\n        {"v": 1, "t": now, "who": handle, "name": me["name"], "src": me["src"],'),
    ("gp-row-n", "surfd.py",
     '        row = {"who": e["who"], "name": e["name"], "n": e["n"], "maps": e["maps"],',
     '        row = {"who": e["who"], "name": e["name"], "n": 0, "maps": e["maps"],'),
    ("gp-row-src", "surfd.py",
     '        row = {"who": e["who"], "name": e["name"], "n": e["n"], "maps": e["maps"],\n'
     '               "src": e["src"]}',
     '        row = {"who": e["who"], "name": e["name"], "n": e["n"], "maps": e["maps"],\n'
     '               "src": "ranked"}'),
    ("gp-q", "surfd.py",
     '    return Response(game_json({"v": 1, "t": now, "q": q, "players": out}),',
     '    return Response(game_json({"v": 1, "t": now, "q": raw, "players": out}),'),
    ("gp-when", "surfd.py",
     '             "when": r["submitted"], "r": rk, "of": of}\n'
     "            for r, rk, of in ranked[offset:offset + limit]]",
     '             "when": 0, "r": rk, "of": of}\n'
     "            for r, rk, of in ranked[offset:offset + limit]]"),
    ("gp-offclamp", "surfd.py",
     '    offset = clamp_int(request.args.get("offset"), 0, MAX_RUNS, 0)\n'
     '    limit = clamp_int(request.args.get("limit"), 1, GAME_PROFILE_MAX, GAME_PROFILE_ROWS)',
     '    offset = max(0, int(request.args.get("offset") or 0))\n'
     '    limit = clamp_int(request.args.get("limit"), 1, GAME_PROFILE_MAX, GAME_PROFILE_ROWS)'),
    ("gp-upper", "surfd.py",
     'if not re.fullmatch(r"[0-9a-f]{8}|[0-9a-f]{%d}" % WEB_HANDLE_LEN, raw):',
     'if not re.fullmatch(r"[0-9a-fA-F]{8}|[0-9a-fA-F]{%d}" % WEB_HANDLE_LEN, raw):'),
    # Patch 665: a tier's maps, and a player's rows on one map.
    ("gp-ct-first", "surfd.py",
     '        maps = [m for m in maps if "ms" in m] + [m for m in maps if "ms" not in m]',
     "        maps = list(maps)"),
    ("gp-ct-tier", "surfd.py",
     '        maps = groups.get(None if ct == "u" else int(ct), {"maps": []})["maps"]',
     '        maps = groups.get(None, {"maps": []})["maps"]'),
    ("gp-ct-page", "surfd.py",
     "        for m in maps[offset:offset + limit]:",
     "        for m in maps[:limit]:"),
    ("gp-ct-shape", "surfd.py",
     'if ct is not None and not re.fullmatch(r"[1-9][0-9]?|u", ct):',
     'if ct is not None and not re.fullmatch(r"[0-9]+|u|U", ct):'),
    ("gp-ct-done", "surfd.py",
     '             "done": sum(1 for m in maps if "ms" in m), "offset": offset, "total": len(maps),',
     '             "done": 0, "offset": offset, "total": len(maps),'),
    ("gp-ct-time", "surfd.py",
     '                row["ms"], row["tr"], row["s"] = m["ms"], m["tr"], m["s"]',
     '                row["ms"], row["tr"], row["s"] = 0, m["tr"], m["s"]'),
    ("gp-on-map", "surfd.py",
     '                if r["map"] == (base if r["tier"] in TIERS_IMPORTED else on)]',
     "                if True]"),
    ("gp-on-base", "surfd.py",
     "        base = variant_base(on) or on",
     "        base = on"),
    ("gp-on-sort", "surfd.py",
     '        mine.sort(key=lambda x: (x[0]["track"], x[0]["leg"], x[0]["millis"], x[0]["tier"],\n'
     '                                 x[0]["style"]))',
     "        pass"),
    ("gp-on-total", "surfd.py",
     '             "av": 1 if player in have else 0, "total": len(mine),',
     '             "av": 1 if player in have else 0, "total": 0,'),
    ("gp-on-bad", "surfd.py",
     '            return fail(400, "bad map")',
     "            on = None"),
    ("gp-av", "surfd.py",
     '         "av": 1 if player in have else 0, "completion": comp,\n         "offset": offset,'
     ' "total": len(ranked), "limit": limit, "rows": rows}),',
     '         "av": 1, "completion": comp,\n         "offset": offset,'
     ' "total": len(ranked), "limit": limit, "rows": rows}),'),
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
# What run_identity reads back after its own insert differs from what it
# inserted only when two posts of one run arrive together: no suite races that.
EXPECT |= {"pin-read"}
BY = {m[0]: m for m in M}


TOOLS = os.path.dirname(os.path.abspath(__file__))


def suites_for(name):
    """test_accounts.py, and then test_ranked.py (Patch 629: whose row a run is)
    for a mutant the first lets through.  The gp- mutants (Patch 662, the
    game's lookups) are test_web.py's alone."""
    return ("test_web.py",) if name.startswith("gp-") else ("test_accounts.py", "test_ranked.py")


def run_suites(dst, suites):
    """`suites` in the copy `dst`, until one fails: -> that process, or the last."""
    # A private temp dir: a mutant that crashes the suite skips its cleanup,
    # and whatever it leaves has to die with this copy.
    tmp = os.path.join(dst, "tmp")
    os.makedirs(tmp)
    env = dict(os.environ, TEMP=tmp, TMP=tmp, TMPDIR=tmp, ACCOUNTS_TEST_TOOLS=TOOLS)
    # THE TOOLS PATH IS test_web.py's ALONE (it imports from there), and it is
    # THIS FILE'S directory, whatever the surfd tree was called by.  Patch 662
    # set it for every suite, and test_accounts.py's "a host with no
    # ed25519.py" check takes tools/ off sys.path to make its host: with the
    # path here as well the module still imported, the check failed on
    # UNMUTATED code, and it "killed" every mutant, 173 of them by itself alone.
    env.pop("PYTHONPATH", None)
    if suites == ("test_web.py",):
        env["PYTHONPATH"] = TOOLS
    for suite in suites:
        p = subprocess.run([sys.executable, suite], cwd=dst, env=env,
                           capture_output=True, text=True, errors="replace")
        if p.returncode != 0:
            break
    return p


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
    p = run_suites(dst, suites_for(name))
    fails = [l[5:70].strip() for l in p.stdout.splitlines() if l.startswith("FAIL")]
    crash = p.returncode != 0 and "FAILURE(S)" not in p.stdout and " failed" not in p.stdout
    shutil.rmtree(dst)
    if p.returncode == 0:
        return name, "SURVIVED"
    return name, "killed by %d check(s)%s: %s" % (
        len(fails), " + crash" if crash else "", "; ".join(fails[:2]))


ONLY = os.environ.get("ACCOUNTS_MUTANTS_ONLY", "")
SWEPT = [m for m in M if m[0].startswith(ONLY)]
try:
    for suites in sorted({suites_for(m[0]) for m in SWEPT}):
        dst = os.path.join(SCRATCH, "unmutated-" + suites[0])
        shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__"))
        p = run_suites(dst, suites)
        shutil.rmtree(dst)
        if p.returncode != 0:
            print("THE SWEEP CANNOT MEASURE: %s fails on UNMUTATED code here.  Its last lines:"
                  % " then ".join(suites))
            print("\n".join("  " + l for l in (p.stdout + p.stderr).splitlines()[-12:]))
            sys.exit(2)
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        results = list(pool.map(run, SWEPT))
finally:
    shutil.rmtree(SCRATCH, ignore_errors=True)
bad = []
for name, verdict in results:
    print("%-16s %s" % (name, verdict))
    survived = verdict == "SURVIVED"
    if verdict.startswith("BAD") or survived != (name in EXPECT):
        bad.append(name)
print("\n%d mutants%s, %d killed, %d survive alone as expected, unexpected: %s" % (
    len(results), (" (those named %s*, of %d)" % (ONLY, len(M))) if ONLY else "",
    sum(1 for _, v in results if v.startswith("killed")),
    sum(1 for n, v in results if v == "SURVIVED" and n in EXPECT), bad or "none"))
sys.exit(1 if bad else 0)
