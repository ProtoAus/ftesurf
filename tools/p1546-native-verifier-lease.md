# P1546 — Native verifier lifetime

Patch number reserved after fetching both repositories and checking published
patch/claim headings and untracked numbered tests, 14 Nov 2026 UTC.

## Problem

The ordinary native-verifier subprocess used Python's default descriptor closing.
That discarded an explicitly inheritable maintenance lifetime descriptor, unlike
the similarity worker. An isolated real child demonstrated an exclusive drain
succeeding before the child completed after the launcher's reference closed.

## Change

Preserve explicitly inheritable descriptors through the existing native launch.
Ordinary non-inheritable descriptors remain close-on-exec. Command construction,
source challenge, parsing, time limit, scheduling and ranking rules are unchanged.

## Verified / limits

- Matched real Linux launch control: old native path prematurely drains; the
  existing similarity path correctly remains held.
- Fixed source: all 18 process tests pass, including both real lease arms, exact
  descriptor identity/inheritability, private-descriptor exclusion, normal output,
  release, and successful eventual drain. Windows: 18 tests, seven Linux skips.
- Existing sweep checks: zero failures; verifier source tests 15/0 and per-attempt
  count tests 7/0. No compiler or recorder-format change.
- The initial combined test exposed reused ready/release filenames across its two
  arms. Test-local names fix the fixture; original failure/control are retained.
- This claim does not assert independent review or live deployment. Those are
  recorded separately. No universal resource bound, player calibration, new
  capture, native vulnerability audit, or native/build pin change is claimed.
