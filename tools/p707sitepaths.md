# P707 — prepare parallel World of Surf website paths

## Scope and baselines

Source preparation, **not deployed**. Initial game base `54902ea2419e9e234f5e98eb0e1eeadcdc4f2342`;
engine ledger base `31b9c86d720c7852896854aa9e3efb28889047cf`. At start published
maximum was 705; precommit refetch found concurrent published P706 (game
`a70aaaa52a6eb233231d2e39f3a759e7f823fa07`, ledger
`2458d94e8640e44ba188a97d8edffbc7951f2c41`). Use max+1 **707**, not the earlier
provisional number in retained artifacts. Canonical untracked pNNN maximum 702.
Owned root: `C:/FTESurf-worktrees/rebrand2-20261014T154554Z/`; OWNER.md and
pre-registered predictions in artifacts/PLAN.md. Parent sole writer; scout and
independent reviewer read only. No peer uncommitted source/install inputs used.

## Change

- Add `/worldofsurf/` static/font/board/map-POST locations beside `/ftesurf/` in
  the existing snippet. Same directory, backend, shared rate zone, method policy,
  IP-header overwrite, timeouts, legacy install marker, font MIME/cache and 404s.
- Preserve query strings on both slashless site/board redirects. Remove redundant
  `text/html` gzip type from both static blocks (nginx enables it implicitly).
- Keep `SURFD_BOARD_URL`, callbacks/unlink paths and backing DB unchanged. A
  new-prefix start intentionally advertises the LEGACY callback in this stage.
  OpenID realm remains origin-only; signed return paths cannot be blindly moved.
- Installer backs up the old snippet outside loaded nginx directories. Both proxy
  paths must return marker, JSON MIME and real v1 maps envelope; a root SPA's
  misleading 200 is rejected. Syntax-failure instructions identify both backups.
- `ACCOUNTS_TEST_BOARD_URL` parameterizes only the complete mock account suite.
  No account app, association, cookie, wire-format or collection policy changes.
- New real-nginx/real-isolated-surfd harness substitutes only deployment addresses
  in the authored snippet. All env/home/game-code/log/temp paths are owned,
  including POSIX nginx's compiled-in default temp paths. No existing standalone
  test suite is imported. Foreground master PID is checked; prefix-scoped signals,
  process reap and closed listener precede fixture retirement. Unproved shutdown
  retains the fixture and fails rather than silently deleting an active tree.

No canonical social metadata, client/release/publish defaults, R2 keys, DNS/TLS,
service hosts, signed updater identity/keys, native/QC code, player data or build
number changed. ENGINE.txt patch only; engine commit/tag pin remains unchanged.

## Verification

From isolated game checkout, Python 3.10, Flask 3.1.3, Werkzeug 3.1.8:

```sh
python -B tools/test_site_routes.py --nginx <distribution>/nginx.exe \
  --work-root <owned-root>/tmp -v
# Linux: supply --nginx <extracted>/usr/sbin/nginx and
# --mime-types <extracted>/etc/nginx/mime.types with owned Flask deps in PYTHONPATH.
python -B surfd/test_web.py
python -B surfd/test_accounts.py
ACCOUNTS_TEST_BOARD_URL=https://proto.bar/worldofsurf/board python -B surfd/test_accounts.py
python -B surfd/test_board.py
python -B tools/test_rebrand.py
sh -n src/release/install.sh
git diff --check
```

Regression subprocesses set TMP/TEMP/TMPDIR under owned tmp/, PYTHONUTF8=1 and
use -B. nginx 1.28.0 on **Windows and WSL Ubuntu 22.04**: five integration groups
pass per platform, zero nginx syntax warnings. Both prefixes' index/Anti-Cheat/
SVG/JS/CSS/TTF/JSON byte equality/MIME/cache; missing assets 404; slash queries;
real maps JSON; relative account CSS; exact backend/raw encoded and duplicate
queries; GET/HEAD/selected-map POST; other POST/PUT denied before app; spoofed
IP headers overwritten. Host-root Secure/HttpOnly/Lax cookie attributes and
no-store remain; both Steam redirect URLs contain original realm/legacy return
including opener. Cancellation and invalid callbacks/unlink reach app without
blanket redirects. Installer's actual Python probe accepts the maps envelope and
rejects SPA/missing marker/wrong envelope.

Full initial-base regressions, then repeated after integration onto published
P706 game `a70aaaa`: **268 web, 400 legacy-base accounts, 400 future-base accounts,
350 board checks, seven brand tests**, zero failures. Both-platform four-arm nginx
matrices also repeat against the integrated clean commit (integrated-*.log). Only
ENGINE.txt's patch-history insertion conflicted; retain both P707 and P706 entries. Full account suites
use fake Steam that records requests, including accepted proof/profile and refusal/
replay controls; not real Steam. Shell syntax/whitespace pass. No LSP diagnostics
recorded; Python execution establishes parse/use, not native/QC build cleanliness.

### Acting controls and retained failures

Original snippet retained from `git show 54902ea:src/release/ftesurf.nginx`.
Control normalizes ONLY original redundant gzip `text/html` to let behavioral
checks run past the preexisting warning. Same test against baseline-test.nginx:
exit 1 on both platforms, five groups ran, ten assertions plus one JSON-decode
error. Missing new paths actually return unrelated filebrowser sentinel; old
slash redirects lose queries. Subject passes five groups per platform.

Independent review found no production-route defect but identified POSIX default
daemonization: waiting for Popen could reap only a launcher. Fixed foreground
master ownership, bounded stop fallback, explicit master PID/listener checks and
retention on unproved stop. `--lifecycle-control setup` and `shutdown` deliberately
fail after actual startup / graceful-signal failure on BOTH platforms: expected
nonzero discriminator, serving master reaped, listener closed, zero new fixture
directories. artifacts/route-matrix.py and matrix-{win,linux}.log record all four
arms per platform; per-arm logs retain full output. No global process-name kills.
Independent frozen-source follow-up review accepted the fix with no remaining
blockers (artifacts/lifecycle-review.md); reviews did not execute independent tests.

Initial Windows fixture failed because nginx needed the temp/ parent; adding it
fixed setup. This also exposed duplicate HTML gzip warnings fixed in source.
Initial WSL dependency curl wrapper lost shell variable quoting; absolute paths
worked. Initial direct WSL Python launch hit MSYS path conversion before any test;
`MSYS_NO_PATHCONV=1 wsl ...` fixed invocation. These were harness/command failures,
not passing product evidence. Early logs retained separately from final matrix.

Development-only official HTTPS nginx downloads, not shipped product dependencies:
- Windows nginx-1.28.0.zip SHA256
  `db8c7a529f84c819702bd1c50926b27d961a48b4f72fc7c46b30314fc2bbfd7c`.
- Linux nginx_1.28.0-1~jammy_amd64.deb SHA256
  `ad8d4f2d1cdcb628d820f4bcf44bbd860e060fd4c29745c4a6118ffba907e40c`.
Package extracted under owned deps, not installed system-wide. Hashes record tested
tools, not independent package-signature verification. pip warned about WSL's root
user; its packages target owned deps, not system Python. nginx syntax itself has
zero warnings. No claim of actual shared-zone/load behavior (fixture rate is high).

## Remaining gates / rollback

- P705 owner art/compact-label acceptance remains open; prep does not imply it.
- Approve privileged parallel-routing deployment window. Stage inspected source,
  preserve vhost/snippet backups, run **target-host** nginx -t, reload only if
  valid; externally probe old/new marker/MIME/body/404/redirect/download hashes,
  installed snippet identity and unaffected services. Restore both backups then
  nginx -t/reload on regression. Nothing installed/reloaded here; complete live
  installer/rollback not exercised. WSL does not prove NanoPi/ARM configuration.
- Real HTTPS browser/Steam/game-opener/unlink/existing-account acceptance, fragment
  preservation and live worker provenance remain pending. Local HTTP verifies
  cookie attributes, not browser secure-cookie transmission.
- Same-host path preserves realm; `openid.return_to` changes. Quiesce old starts
  and drain configured 600s window before changing SURFD_BOARD_URL/replacing
  workers. No mixed callback authority. Very late returns may expire/retry.
  Seamless old signed callbacks need separate explicit allowlisting and tests.
- Synthetic direct JSON bytes are NOT signed-feed validation or released updater
  round-trip. Keep legacy reader identity/feed URLs/R2 artifacts/keys. Canonical
  social/default changes and updater bridge remain final-cutover work. Do not
  retire any old endpoint on these local tests. No native/progs build/deploy made.
