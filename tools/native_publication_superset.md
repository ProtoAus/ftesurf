# Separate Windows deferred full-survivor publication oracle

Test tooling only: no engine/product/pin/tag/build/release/deployment changes.
Historical pending-only graders and helper sources remain unchanged.

`test_update_native_publication_superset.py` imports the immutable deferred
source-lock and deferred-interruption actors. It supplies a separate fixture and
oracle, not a rewritten historical expected-orphan predicate. Original rows are
derived from the verified signed manifest and the two independently selected
old managed destinations, never from candidate authority. Both pending positions
in signed manifest order are exercised; this does not manufacture a differently
signed envelope or reverse its row order.

## Executed contract

Both exact clean-before `f9ba9842a5a138cfcffcd1c826488fad6dfbecbc2e3588b18a4d7cc067f514bc`
and corrected-candidate `b566bf46b17a2f7cb4e95599e2089ad7fabff4dc9397ac5bc982ed6210480596`
have P692 atomic wide publication. They are NOT the historical pre-P692
unlink-before-rename client. Their complete executable/companion text and native
writer/initial/deferred caller/import/frame shape are bound before startup.

Each client runs eight live cases and eight fresh recorded ordinary cold repair
phases: second-writer source-sharing failure, before/after publication process
interruption, and successful uninterrupted publication, for both pending positions.
Each live case proves the other destination actually installed. Full selected
signed closure, current partial ledger/version, consent, missing premature
certificate, protected zone/settings/recording and unmanaged bytes are checked.
Every staged leaf and sibling is inventoried, not merely pending objects.

Failure/pre-interruption must preserve original attempt1 authority and ALL stages.
Candidate native temp and committed authority must retain both original rows;
legacy committed reduced authority must FAIL the new full-row oracle. Post native
interruption leaves both stage objects present. The candidate uninterrupted
positive removes the installed stage only following publication. Ordinary repair
must ACT completion/ledger/signed certificate and retire carried objects. The
legacy reduced-authority repair instead retains its exact installed-row orphan;
this is a characterizing before control, not subject acceptance. Before full-row
repair can leave a byte-exact failed temp sibling: it is exported and not adopted.

Interruption uses immutable `native_journal_initial.c` hooks: actual raw native
caller/thread/path/ordinal/order and successful return are exported, instructions
restored, only owned child interrupted86. This is process interruption, NOT power
loss. Source-lock uses immutable `native_journal_live_fault.c`: real writer1/2,
source-writable/independent rename32 and native rewrite-error actor are observed.
**That older actor does not export the product rename API return or boundary path
check. This slice therefore does not close the requested raw source-lock-return
sub-gate.** No inferred return is relabelled as a native observation.

All actors launch suspended into registered owned jobs, export checked full
runtime inventories/raw metadata including TMP/stage/log identities, and require
natural pre/post-cleanup job0. Signed-mirror workers are non-daemon with bounded
socket reads; final census is taken only after server_close joins all accepted
handlers, including cold repairs. It is mirror scope, not all-network silence.
Sources and helper/client disk hashes are checked unchanged through each matrix.

## Commands and retained paths

Build the two immutable helper sources in the owned publication artifacts lane:

```text
gcc -municode -static -O2 -Wall -Wextra -Werror tools/native_journal_initial.c -o <lane>/native_journal_initial.exe
gcc -municode -static -O2 -Wall -Wextra -Werror tools/native_journal_live_fault.c -o <lane>/native_journal_live_fault.exe
pwsh -NoProfile -Command '$env:FTESURF_TEST_SCRATCH="<existing uniquely owned scratch directory>"; python -B -m unittest discover -s tools -p test_update_native_publication_superset_unit.py -v'
python -B <parent serialized-native.py> tools/test_update_native_publication_superset.py --engine <exact client> --symbols <matching companion> --helper <initial helper> --failure-helper <live fault helper> --feed <retained signed feed> --objects <closure-a> --objects <closure-b> --runtime-root <fresh lane runtime> --evidence <fresh lane evidence> --serializer <parent serialized-native.py>
```

Append `--expect-before` for exact clean-before ONLY. No signer/key/pin override.
Evidence lives under `C:/FTESurf-worktrees/wjfinish-20261014T075250Z/artifacts/publication/`.
Command logs include exact argv; per-case live/repair process.json, raw debug.jsonl,
seed/final/full phase exports and publication-oracle.json are independent review
inputs. All runtime copies under the sibling runtime/publication lane are retained
explicitly through review, including failures; no blanket cleanup is authorized.

Failures: before01 live source-lock acted successfully but cold setup refused before
launch (required recorder sentinel filename mismatch); before02 live/cold acted but
new oracle incorrectly expected legacy failed-temp deletion. Both remain FAIL with
runtime/evidence/guard history. The corrected oracle requires that sibling's exact
survival, matching immutable historical constraints. Fresh before03/subject01
matrices passed, not relabelled earlier attempts.

Remaining: raw native return/path source-lock sub-gate, independent initial and
cold full-superset extensions, corruption/exhaustion branches of this new live
oracle, hostile ancestor swaps/hardlinks, Linux and power-loss durability. Existing
cold/initial actors have separate historical evidence; this extension does not
upgrade or claim it. Product publication remains blocked by these and other lanes'
partial-read/retained-generation/launcher gates. Independent review is required.
