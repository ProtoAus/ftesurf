# P1564 - TAS boards and completed-run history

## Scope and current state

The requested feature has two delivery parts: a separate TAS leaderboard, then
local retention/browsing and replay-camera corrections. This first change is
the **backend part only**. Local game changes are not represented as deployed
or accepted by these backend tests. No release, native pin/tag or Build bump.
Original private test labels P1559 predate the published claims through P1563;
the single feature number is now P1564.

## Backend change

- Native assisted submissions retain their original flags in community TAS
  boards. TAS remains uncertifiable, including linked-account submissions.
- The web map page has a separate TAS selector and TAS counts. Ordinary clean
  and segmented boards, completion/Story statistics and points stay separate.
- Existing submission-key, account-ban and native replay gates remain in force.
  A native replay index is not a public sharing grant: community runs remain
  unavailable from the public web run/track viewer, and TAS rows expose no web
  replay link. No new player identity or evidence fields are published.

## Verification

The isolated backend lane passed four focused `surfd/test_tas.py` tests:
classification/ordinary-board isolation; community web counts and native/public
replay gates; linked-account TAS storage and banned-owner refusal; and required
submission-key rejection. Existing `test_web.py` and `test_board.py` pass, as do
JavaScript syntax and diff whitespace checks. One untouched, pre-existing
`test_ranked.py` template assertion fails and was preserved, not repaired here.
These synthetic API fixtures are not native physics or certification evidence.

The backend lane was fast-forwarded from 069886ba to inspected public d4917336
before publication, retaining the already-published prediction-report changes
and patch claims. No peer uncommitted source is part of this feature.

## Delivery (pending)

Commit/push and deployment are separate states. No live backend generation swap
or Windows/lobby gamecode delivery is claimed yet. Use the currently serving
runtime and guarded code-only generation procedure against CURRENT data; retain
its rollback and admission history, replace only the declared backend files,
and verify destination hashes and live behavior. Never restore an old database
or manually reopen a consumed admission grant. See
[surfd generation procedure](surfd-generation-p996.md).

The local-history and camera half still needs its own acting game controls,
clean integrated build, publication and delivery. A compiler pass or completed
review is not a substitute for those remaining actions.
