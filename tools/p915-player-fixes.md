# Player fixes through P915: deployment and acceptance

## Exact delivered source

- QC/backend product source: `bf3c41992e648a6e95588296fac386cc835512b5`.
  This includes the earlier P907-P914 menu, board, startmark, spectator,
  Story and viewing-clock changes, plus P915 disconnected clocks and retained
  clean stage attempts.
- Native source retained from P916:
  `14c3030275736ae5548f725d5d04dd05122ecef6`, the published merge of REC13
  structural support and mover 11. Neither published patch tag was moved.
  This rollout did not replace those native binaries.
- Backend handoff completed 22 Oct 2026 at **08:39:47 UTC**. All 80 runtime
  files and 16 loaded module origins/hashes matched; schema remained 20.
  The predecessor was closed/drained, not reset. No database was restored.
  Canonical reader dependencies were promoted before the candidate app import.
  The final audit-note failure was repaired separately after live revalidation;
  the completed transaction was not replayed or its evidence redated.
- Both Windows installs received matching six DAT/LNO files; the shared Pi
  QW/CS pair was swapped with its previous pair retained. All 12 empty lobbies
  restarted successfully by **08:53:46 UTC**. Required readers were installed
  before enabling REC13 producers. Build number and release publication did
  not change.

Deployed DAT SHA256 values:

| File | SHA256 |
|---|---|
| `qwprogs.dat` | `cb9f62d8b4e97f52101c34f77f5a56c0205e7370907e849f143b9e19d453ac60` |
| `csprogs.dat` | `c8033d872f3ccd1420659e3818a301a486d69e7dc51eaed8dd87d5a85a98f757` |
| `menu.dat` | `f3a466f3ab5781ed76957c78ae3d9b461d897767b05e0be20d9e9e854018ace9` |

These are the tested artifacts, not a later rebuild after a release preview.
Normal-emission and isolated-build artifacts were byte-identical. The follow-up
commit containing this receipt changes documentation only; the deployed runtime
remains bound to the product commit above.

## Verified, without inventing owner acceptance

- Three VM compiles had zero warnings. The final reader suite passed **864
  checks, zero failures**. A fresh post-deploy sweep of **405 recordings** kept
  the **271 pre-existing fault checks**, with no file gaining faults. All 529
  baseline corpus files retained their exact bytes; the six later arrivals
  were separately checked, including their viewing sidecars, without faults.
- Dedicated-socket archive acceptance: **31 ordinary**, **21 targeted boundary**
  and **7 metadata-interleaving** controls. These cover actual selection and
  playback, persisted-output failures/retries, owner separation, stale transfer
  generations, captured verified row metadata and active shutdown cleanup.
  This is synthetic account-proof boundary testing, not a claim of a real
  remote sign-in, accepted terms or official record grant.
- On each of Windows and ARM, the actual merged P916 native bytes passed all
  five supported-map matrices (**60 complete named outcome rows**), **37 REC13
  structural controls** and **two retained native legacy compatibility runs**.
  Complete physics rows matched cross-platform, not just a headline digest.
- Post-swap checks confirmed all 12 active native process identities started
  after the progs swap and loaded the retained native generation. Destination
  hashes and the ordinary previous pair matched the recorded provenance.
- An isolated cold client, without seeded CSQC, connected to a real lobby and
  downloaded CSQC with the exact deployed SHA256. The board drew, its screenshot
  was inspected, the client exited normally and no QC runtime errors occurred.
  Its online-terms guard remained in place; no consent was fabricated. This
  was not authenticated Local-browser or Story owner acceptance.
- The actual live board API accepted the normal control and all three new
  segmented-direction query keys; an invalid key returned 400. This changes
  read filters, not existing record labels or submission eligibility.

Full private machine receipts and diagnostic evidence remain private; no player
identifiers, credentials or raw private runtime inventories are published here.

## Limits and the remaining human checks

- Positive viewing-time or disconnected parked-time carry is displayed and
  retained but remains **explicitly unsupported by native simulation**.
  Ordinary zero-carry REC13 is supported. No verification tier was added.
- Automatic resume is restricted to eligible clean whole-main progress. Old
  saves do not acquire an invented disconnect instant, and refusal preserves
  slot bytes. No unspecified cannot-beat-stage attempt/time threshold was
  guessed; manual saves retain their existing route.
- New completed clean stage attempts are retained under existing recording
  limits. Lobby retrieval uses the connection's existing normal account proof;
  old unsealed files do not gain remote ownership authority by filename.
- The intermittent departed unnamed/non-spectatable roster row was not
  reproduced. No speculative filter was shipped; legitimate accented names
  remain. BACKLOG.md keeps its sites and falsifier.
- Owner camera/reset/startmark feel, genuine remote-account Local retrieval,
  immediate Story experience and menu interactions remain pending in
  `lextest.md`. A passing automated check is not an owner's confirmation.
