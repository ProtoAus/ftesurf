# HTTP admission for guarded backend generations

`surfd_transition_guard.py candidate` permits a server process to start while its
generation is CLOSED. That process lifetime lock does **not** authorize or fence
individual HTTP requests. Sending only health probes does not make a candidate
health-only: real clients can still reach it.

`surfd_http_admission.py` supplies the missing cooperative request fence through
Gunicorn's existing `post_worker_init` config hook. Gunicorn 20.1.0 loads WSGI,
invokes this hook, then starts the worker request loop (including gthread).

## Deployment binding

Do not edit an installed immutable generation or add an environment/argv/proxy
selector. Prepare a new generation and retain its failed predecessors/evidence.
Its selected, sealed `gunicorn.conf.py` installs the gate on `worker.wsgi`:

```python
def post_worker_init(worker):
    admission.install(worker, guard=guard,
                      state_dir=STATE, generation=GENERATION,
                      manifest_sha256=MANIFEST_SHA256)
```

The config must bind exact absolute state/manifest paths and source digests.
Load the declared guard and admission modules by hashing their source bytes and
executing **those same bytes**, not a second import or an unchecked cached pyc.
Seal config/module/guard as generation inputs. Bind the manifest digest from the
actual initialized immutable state manifest; do not create a circular config hash
inside a manifest that embeds the config's own digest. An enclosing reviewed input
binding can seal both independently. Existing Root/model/namespace/actor/dependency
checks remain required; this hook does not expand or replace that authority.

Only exact `GET /health` with an empty query can reach the read-only health route
while CLOSED. All other methods and paths return 503 before the application,
authentication or database access. Missing/malformed/generation-drift state and
changed worker closure also refuse, including health. An OPEN request holds its
own shared admission lock through iteration **and response close**, including
stream cleanup and failures. Concurrent gthread requests never share one open
lock description. Invalid lock metadata must close its newly opened descriptor
before propagating a refusal; long-lived workers cannot rely on CLI process exit.

Closing still publishes CLOSED and drains admission plus candidate/process lifetime.
Use the existing actor stop/death proof: a request fence is not process shutdown.
Health/startup may initialize declared schema. Preserve data and qualify the prior
application on the SAME current schema and nonempty optional queues before a live
window. Do not restore an old database, accept unknown mutations, weaken a failed
gate, reuse authorization history or infer historical key preservation from counts.

## Validation

On Linux with Gunicorn 20.1.0, run in an owned task root (never an install or /tmp):

```sh
python3 -I -B tools/test_surfd_http_admission.py --out /absolute/owned-task/http-controls
python3 -I -B tools/test_surfd_transition_guard.py --out /absolute/owned-task/guard-controls
```

Output paths must be new; source changes and first failures remain evidence, not
renamed successes. The focused HTTP suite uses synthetic loopback traffic/SQLite,
checks actual CLOSED refusals and OPEN writes, response/lock lifecycle failures,
forced preacceptance rejection and same-data fallback. It is not a Root observer,
production-runtime qualification or cheat detector. Separately qualify the actual
application versions and schema before any deployment; keep serving while preparing.
