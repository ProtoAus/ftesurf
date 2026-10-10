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

PAIRS lists mutants that are allowed to survive ALONE because a second check
covers the same hole; the two together must die.

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
    ("live-cap", A, "if live >= CODE_LIVE_MAX:", "if False:"),
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
    ("ban-code", A, 'if not acct["banned_at"]:', "if True:"),
    ("supersede", A, '" WHERE steamid = ? AND used_at = 0",', '" WHERE steamid = ? AND used_at = -1",'),
    ("code-prune", A, "(now - CODE_KEEP,))", "(0,))"),
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
    ("expiry", A, 'or row["issued_at"] < now - CODE_TTL:', "or False:"),
    ("expiry-edge", A, 'or row["issued_at"] < now - CODE_TTL:', 'or row["issued_at"] <= now - CODE_TTL:'),
    ("spent-read", A, 'if row is None or row["used_at"] or', "if row is None or"),
    ("spent-write", A, "if spent.rowcount != 1:", "if False:"),
    ("spent-both", A, None, None),
    ("ban-link", A, 'if row["banned_at"]:\n            return {"ok": 0, "why": "banned"}, None',
     'if False:\n            return {"ok": 0, "why": "banned"}, None'),
    ("move-ask", A, "if moving and not confirmed:", "if False:"),
    ("move-same", A, 'moving = old is not None and old["steamid"] != row["steamid"]',
     "moving = old is not None"),
    ("tries", A, 'if not d.rate_ok(player, now, TRY_RATE_MAX, "linktry"):', "if False:"),
    ("link-rate", A, 'if not d.rate_ok(src, now, LINK_RATE_MAX, "linkapi"):', "if False:"),
    ("link-flood", A, 'if not d.rate_ok(src, now, LINK_FLOOD_MAX, "linkflood"):', "if False:"),
    ("link-order", A, 'if not d.rate_ok(src, now, LINK_FLOOD_MAX, "linkflood"):',
     'if not d.rate_ok(src, now, LINK_RATE_MAX, "linkapi"):'),
    ("acct-rate", A, 'if not d.rate_ok(src, now, ACCT_RATE_MAX, "acct"):', "if False:"),
    ("one-bucket", A, 'LINK_RATE_MAX, "linkapi"):', 'LINK_RATE_MAX, "acct"):'),
    ("code-shape", A, 'return code if _CODE_OK.fullmatch(code) else ""', "return code"),
    # accounts.py: the name
    ("game-name", A, '"name": game_name(row["name"]),', '"name": row["name"],'),
    ("name-symbols", A, 'unicodedata.category(ch)[0] in "LN"', 'unicodedata.category(ch)[0] in "LNSPC"'),
    ("name-blank", A, "and ch not in _NAME_BLANK):", "and True):"),
    ("name-bytes", A, 'while len(safe.encode("utf-8")) > NAME_BYTES:', "while len(safe) > NAME_BYTES:"),
    ("name-reserved", A, ' or safe.lower() == "console":', ":"),
    ("name-nfc", A, 'unicodedata.normalize("NFC", name or "")', '(name or "")'),
    # surfd.py
    ("schema-step", "surfd.py", "conn.executescript(accounts.SQL)", "pass"),
]
PAIRS = {"spent-both": ("spent-read", "spent-write"),
         "replay-both": ("replay-read", "replay-write")}
# replay-write dies alone (the stored row is counted); its partner does not.
EXPECT = {"spent-read", "spent-write", "replay-read"}
BY = {m[0]: m for m in M}


def run(item):
    name, fname, old, new = item
    dst = os.path.join(SCRATCH, name)
    shutil.copytree(SRC, dst, ignore=shutil.ignore_patterns("__pycache__"))
    edits = [(fname, old, new)]
    if name in PAIRS:
        edits = [BY[k][1:] for k in PAIRS[name]]
    for f, old, new in edits:
        path = os.path.join(dst, f)
        with open(path, encoding="utf-8", newline="") as fh:
            src = fh.read()
        if src.count(old) != 1:
            return name, "BAD MUTANT (%d matches)" % src.count(old)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(src.replace(old, new))
    # A private temp dir: a mutant that crashes the suite skips its cleanup,
    # and whatever it leaves has to die with this copy.
    tmp = os.path.join(dst, "tmp")
    os.makedirs(tmp)
    p = subprocess.run([sys.executable, "test_accounts.py"], cwd=dst,
                       env=dict(os.environ, TEMP=tmp, TMP=tmp, TMPDIR=tmp),
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
