# P945 — consumed recording input binding

Development delivery, 23 October 2026. This is not a release or owner Build bump.

## Delivered change

The native verifier identifies the complete recording buffer it loaded, before
parsing, and returns a fresh invocation binding. The backend accepts one matching,
timely report only with an unambiguous terminal result, successful process exit
and unchanged admitted input. Missing or ambiguous binding is retryable `ERROR`,
not player guilt, and supplies no ticks/counts observation.

Native source/tag: `9e73ae1c8ade050af424182b05ae259371a1eefc` / `patch-945`.
Backend overlay: `c6d4b511e2955d6f05268a70152e3e34494be23d`, `surfd/sweep.py`.
Later inspected engine commits changed documentation only, not these compiled
inputs. The later published Sweep is byte-identical to this reviewed overlay.

## Validation

- Seven real-file/SQLite controls expose eleven failing baseline subcases.
- Windows focused input/identity/source/finish/counts suites: **47 pass**.
- ARM: **46 pass, one explicit skip** because Node is absent. The unchanged DOM
  test/template passed in the Windows suite; no Node installation or fake ARM
  DOM pass is claimed.
- Final tagged Windows Full/NoDeploy: 74 inherited native warnings, zero new.
  ARM build qualified; all **60 named physics rows over five maps** match the
  qualified Windows controls in the complete fixture namespace.
- Real dedicated consumed-buffer controls distinguish valid legacy inputs and
  malformed/unsupported inputs. A retained REC15 context refusal is **not** a
  trajectory acceptance claim.
- The documented pin7 legacy replacement passes **9194 ticks / 9192 rows** on
  unchanged and updated ARM binaries. The historical Boreas fixture's existing
  HOLD is preserved, not reclassified. The pin2 control passes 4418 ticks/rows.
- Existing reader suite: 864 checks. The same captured 419-record corpus retains
  its 283 faulted-file baseline with zero added faults; no recording was repaired
  or rewritten to manufacture a pass.
- Independent product protocol/evidence reviews and focused operational-adapter
  reviews found no blocking issues on the frozen artifacts.

## Deployment and readback

| Boundary | UTC | Evidence |
| --- | --- | --- |
| Both Windows installs | 2026-10-23 11:33:28 | Exact existing ten-image native shipset; exclusive P816 image leases, paired rollback and `.prev` history. All ten destination hashes match; 21 protected peer VM/menu/config files unchanged during promotion. |
| Pi native pair and backend | 2026-10-23 11:44:29 | Fresh positive-empty socket/directory checks, all 12 lobby restart epochs, exact native/plugin hashes, guarded backend cold acceptance and handoff. |
| Live Pi readback | 2026-10-23 11:51:28 | All 12 advertised native versions and mapped-plugin OS identities match. The actual staged runtime verifier function plus canonical native executable passes an existing indexed recording and supplies the matching complete-buffer binding, without SQL writes/reclassification. |
| Installed Windows behavior | 2026-10-23 11:54:10 | Installed dedicated binary passes the 4418-tick legacy control and its fresh full-buffer binding through the exact backend normalizer. Owned child exits; temporary owned maps junction removed. |

The backend successor preserves 79 of the serving peer's 80 runtime files,
including its later Story changes. Only Sweep is overlaid; its qualified native
dependency pins and serving-root bindings change together. Actual fresh workers,
managed importer, canonical routes and cron bindings are verified. Current peer
progs/menu/config are preserved rather than deploying older generated artifacts.
No owner game was killed. The AI service remains inactive; it was not restarted
or rebooted. Failed preparatory invocations are retained as failures, not credited
as feature passes.

## Limits and remaining work

This does not add a recording format, collector, device identifier, threshold,
retention policy or database schema. It does not establish physical input, human
honesty, hostile-host resistance or a fully modeled world. Existing verdicts are
not retroactively rebound/revoked. Persisting a recording digest with each verdict
is a distinct provenance change, not implemented or implied by this delivery.
Runtime-required frozen profiles/control/state and protected evidence remain
retained; they are not disposable build directories.
