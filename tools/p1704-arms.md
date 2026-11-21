# P1704 arms -- run views over HTTPS (worldofsurf-47, 21 Nov 2026)

Rig: one dedicated server + one client, a local collector serving surfd/hidupload.py's /api/hid and /api/view on
127.0.0.1 (client `rec_hid_testurl`), storing into the server's data/evidence. The collector waits 3 s before reading
each request, so a POST is still in flight when the client disconnects, reconnects or finishes its next run. Server
`run_evidence_ul 2`, `sv_recupload_https 1` (not in gateoff); client `rec_hid 1`, `rec_hid_upload 1`, terms 10.
surf_ace with a short course. Graded by the files: each `.view`/`.hid` beside the receipt, sha256 equal to the
receipt's `signed view` / `signed hid` digest, plus the engines' own lines; the client's queue folder (httpq/ under
FS_ROOT, the install root, since review 10) must be empty at the end, and a planted leftover gone after the first
frame. `gamedir httpq` and `gamedir HTTPQ.` are refused (review 11).

| case | client / server | result |
|---|---|---|
| V1 one run | P1704 / P1704 | server `asked .. over HTTPS` for view and journal; both stored, digests equal |
| V2 disconnect once asked | P1704 / P1704 | both stored; client `view HTTP stored and digest acknowledged` after the disconnect |
| V2 control | first cut (before CL_Receipt_Disarm kept jobs) | client `view HTTP cancelled` at the disconnect |
| V3 two runs back to back | P1704 / P1704 | four files stored; `queued (1 waiting)`, `(2 waiting)` |
| V4 reconnect once asked | P1704 / P1704 | a witness file in data/staged/ is gone (the new csprogs cleared it); both files stored from the queue folder |
| retry | collector answers the first request 429 | `view HTTP not acknowledged (status 429); trying again in 30 s`; journal stored meanwhile; view stored 30 s later |
| tamper | as retry; the queued view overwritten (from outside the game) during its 30 s wait | client `not sent: it is not the file this game signed for that run`; no second /api/view request; journal stored |
| noterms | as patched, then `rec_terms 1` (csprogs still arms from consent.txt) | client `not sent: the online terms are not accepted` for view and journal; the collector sees no request |
| nomove | as patched, rename() into httpq/ failing (LD_PRELOAD shim, as Windows fails when another program holds the file) | client `could not be moved; copied` for the journal (0 in the control); both stored; the staged journal gone |
| own replay | patched and nomove, right after the run | the staged view is still in data/staged/ (cl_watch.qc's own-replay recovery); the staged journal is not |
| gateoff | P1704 / P1704, sv_recupload_https 0 | view over the netchan (`Receiving`), journal over HTTPS; both stored |
| compat | released 0.1.54 / P1704 | view over the netchan, journal over HTTPS; both stored |
| compat | P1704 / released | view over the netchan, journal through the new HTTPS queue (the released lobby already asks journals over HTTPS); both stored |

A rig profile without online consent signs a view digest and stages nothing (`replay: sidecar dropped`), so the arm
writes a tier-10 consent record for its run and restores the previous state afterwards.

Production baseline (lobby logs 18-21 Nov, read-only): 67 receipts signed a view; 51 asked; 47 transfers started; 23
views landed; 16 runs never asked (`not asking again`); 4 asked clients never started.
