# P1379 -- boardarchive.py: archive or restore one map's WOS board times, on purpose

ftesurf-3a (Claude Code), 8 Nov 2026 local. Owner: when a zoner changes a map's mode (P1371's zone-file
gamemode), archive that map's old times, restorable; asked again after review, chose an admin command.

## Use (on the Pi)

    cd /srv/nvme/surfd
    python3 -I boardarchive.py list    --map <map>
    python3 -I boardarchive.py archive --map <map> --label surf            # dry run
    python3 -I boardarchive.py archive --map <map> --label surf --apply
    python3 -I boardarchive.py restore --map <map> --label surf --park-live-as bhop --apply

`--db` defaults to /srv/nvme/surfd/data/surfd.db; each applied operation adds a line to
data/boardarchive.log. Labels are [a-z0-9-], at most 16: name the rules the times were set under.

## How

Standalone sqlite (on the Pi surfd.py is pi.dev's guarded-generation dispatcher; the tool neither
imports nor restarts the service). A runs row or kind='run' replays row of the map whose tier is a WOS
tier (ranked/community, "@<runid>" and "^<tag>" stage forms, each optionally under "banned:") moves to
"mode:<label>:" + tier inside any "banned:" -- accounts.ban_rows' mechanism, so every reader that names
its tiers ignores it, ban/unban nest correctly, restand stays in the family, replay ids (verdicts,
reviews, receipts) are untouched and a restore is exact. Imported tiers never move. Nothing is deleted:
a label already holding rows of the map is refused; restore with live rows needs --park-live-as.

After a restore it names runs whose stage times a review made while parked left hidden (surfd's
restage works on live tiers only): re-review that replay once. The reverse is re-hidden by the
sweeper's restage_rejected within one pass.

## Why not automatic

The first P1379 detected mode changes in surfd (zone file, mapmeta, name) and swapped boards itself. Two
reviews found: boards already mixed would never be archived (first-look bootstrap); an unreadable
mapmeta.txt read as empty and parked boards nobody changed (measured); a zone admin could flip a whole
board twenty times an hour; stage posts carry no recording so old-rules stage times reached the new
board; a swap between check and write filed a run on the wrong board. zonepub itself refuses an
automatic hide/archive ("a separately reviewed leaderboard operation"). Kept on the branch history.

## Known effects (by design, BACKLOG)

Story (story_runs has no tier) still counts parked finishes; the people directory can show parked rows
for up to an hour (its marker keys on MAX(rowid)); admin ban/stage counts include parked rows.

## Verification

test_boardarchive.py 26/26 (fresh surfd schema): dry runs write nothing; archive parks live WOS rows and
recordings incl. stage and banned forms, imported and other maps untouched; the ranked board shows no
parked row (with controls proving the board shows live rows -- a first version planted style 'normal'
and that check passed vacuously); restand keeps a parked replay parked; refusals; --park-live-as swaps
exactly; ban/unban nest; the review-while-parked case is named. Review: round 1 one medium (that case,
now reported) and lows; round 2 on the fix. The five P1369-switched maps have 0 WOS rows, so nothing is
mixed there today.
