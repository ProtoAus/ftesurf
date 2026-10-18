# Patch 774: signed input-journal collection

The game netchan is no longer the large-journal transport for capable clients.
Install the matching native client/server, `surfd.py` plus `hidupload.py`, and the
exact `/api/hid` nginx route/zones together. The backend deployment planner keeps
its Python dependency set atomic; nginx configuration remains a separate tested
installation. Ordinary builds/development deployment do not make a release.

## Contract

- Existing recording consent and `rec_upload` still apply. Raw journal uploads
  additionally require the separate **default-off** `rec_hid_upload` choice in
  the main menu's **Input journal uploads** panel. Accepting online terms never
  enables it. Both native switches preserve early local values and refuse remote
  enablement; turning either off cancels an active journal upload. No account,
  ranking or ban policy is enabled here.
- The existing server-selected evidence request chooses nonce, kind and
  destination basename. Only an explicitly opted-in armed `.hid` can be sent,
  via the new native-only `rec_ul_http` verb. `.view` retains its original path.
  Older clients are not requested to upload raw journals; new native clients
  never send raw data through the legacy route.
- A new client posts to the fixed official HTTPS collector. The signed request
  must agree with an already-written signed receipt on key, nonce, length,
  SHA-256 and kept status. The request cannot choose another directory or URL.
- A 1024-byte bounded header precedes raw bytes. The receiver streams to an
  owner-only temporary file, hashes it and atomically links a complete matching
  file without replacing existing evidence. An identical retry succeeds; a
  conflicting existing file is preserved for investigation.
- The collector accepts at most 64 MiB. Native ownership/deadline and tiny-response
  bounds are explicit. The nginx body increase is route-local, request buffering
  is on, and dedicated IP/global budgets limit concurrent temporary bodies.
  Other APIs keep their original limits and private heartbeat/run writers.
- Missing receipts and filesystem failures are retryable service errors. A
  failed/unknown acknowledgement is not evidence that the journal was never
  stored, and is never an anti-cheat verdict.
- Evidence requests are still governed by the existing server collection policy
  (`run_evidence_ul`). This patch does not silently change the operator's policy.

## Verification

```
python -m unittest discover -s surfd -p test_hidupload.py -v
python surfd/test_surfd.py
python surfd/test_sweep.py
python tools/test_reccheck.py
```

The backend suite covers a real >4 MiB body, dotted/plus map basenames, invalid
identity/signature/commitment, traversal, malformed lengths/truncation, duplicate
and conflicting evidence, temporary cleanup, and unchanged body limits elsewhere.
`surfd-deploy.ps1` runs it against its exact committed staging tree.

Native dedicated-socket controls used synthetic transport files and test-owned
signing keys, not player data: 5,242,913 bytes arrived exactly with a matching
acknowledgement and the legacy view path stayed intact. A historical older
protocol control hit the 4,194,304-byte refusal; the final server preserves old
clients' view uploads while deliberately skipping their raw journal request.
Early global upload-off and independent raw-opt-in-off controls resisted acting
remote enable attempts; explicit local re-enablement then succeeded. A malformed
chunked reply failed and released the slot for an immediately successful retry.
The reader suite reported 306 checks, zero failed; collection does not modify
recorder/verifier grammar or detection thresholds.

These results do not claim a valid human input journal, clean historical corpus,
measured throughput, calibrated input detection, full 64 MiB acceptance, forced
300-second timeout, human menu-click acceptance, fleet restart or release
acceptance. Real Allow/Stop and compact-window layout checks remain human checks
in `lextest.md`. Record actual deployed
commit/artifact hashes, live behavior and UTC separately. Do not deploy private
fixture QC or substitute fixture acceptance for real lobby evidence.
