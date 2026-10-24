# P969 — preserve the installed Windows cohort

This source composition starts from the inspected Windows P968 server source
`53c54f97a6fd`, not main's different client/Friends cohort. It applies only the
three reviewed P969 server module hunks from `0e172504d1a7`: sv_timer.qc,
sv_saveloc.qc (contract comment) and sv_resume.qc (plain-save metadata reset).
Their predecessor bytes match the native controls and their new bytes exactly
match the independently reviewed, native-tested main modules.

The writer separates live memory marks from disk confirmation; a failed disk
copy must not cancel valid warm lineage. New additive save metadata gates cold
buffered use. No recording-format, stream-copy, native source/pin/tag, input
capture, detector threshold, Build or release change. Historical saves remain
unbound; this is not atomic/durable state-prefix storage or authentication.

Qualification uses the existing three-VM NoDeploy build from a clean inspected
commit. It may compile client/menu to prove the source closure, but delivery is
ONLY qwprogs.dat and qwprogs.lno to BOTH Windows installs. Each destination has
an inspected P968 predecessor; fresh client/menu/native/settings/config hashes
are protected. Keep .prev, verify destination and protected hashes, never stop
or restart the owner's processes. No player data is edited or cleaned.

Main's actual writer/key/Rewind API controls12+12, three-VM zero-warning build,
924reader checks and unchanged430recordings/126paired views (294existing faults,
all556hashes) qualify the identical module delta. Two fresh independent recorder
reviews found no introduced issues. This is not full state-load, real engine
push/signing/posting, performance, owner acceptance or broader rule8 completion.

This composition's clean build, branch publication and Windows installation are
pending. Native/client/menu files are not delivery artifacts. Pi needs its own
unchanged-cohort composition and live safety boundary, not these client files.
