# Pi backup rotation (P1702)

Lex, 21 Nov 2026: "I like backups and I like safety, but sensible, I don't need every backup ever made, maybe like
the last 2 at most" and "ensure proper rotation". The rule everywhere: **keep the newest 2**.

| What | Who rotates it |
|---|---|
| Backup copies `NAME.pre*`, `NAME.bak*`, `NAME-pre<N>*` in the surfd home and data, the lobby game folders, the site: two per file (newest by the timestamp in the name, else mtime), plus the two `csprogs.dat.pre[0-9]*` tasupd trusts | `tools/pi_retention.py`, daily |
| Idle task roots in /srv/nvme/agent-work (14 days unchanged, named by nothing live; the newest 2 staged `gen<N>-*`, every root their code names, and any root holding a `RETAIN` file stay) | `tools/pi_retention.py`, daily |
| `tasupd-src-*` checkouts in /srv/nvme/ftesurf-ops | `tools/pi_retention.py`, daily |
| TAS upload releases in /opt/ftesurf-tasupd (root) | `tools/install_tasupd.py` on each upgrade |
| Namespace-observer owner backups (root) and the old `10-guarded-startup.conf.pre*` drop-in copies | the generation kit's owner install (genkit, from gen1702): two newest owner backups, no old drop-in copies |
| surfd DB backups (`surfd.db.bak-pre<N>-*`, one per generation) | `tools/pi_retention.py` (newest 2) |

It **fails closed**: if any configuration file it should read cannot be read (a root installer leaving a drop-in
0600, an unreadable folder, a failing `crontab -l`), it removes nothing and logs `STOPPED` with the path. Only an
unreadable copy no loader picks up (root's 0600 `/etc/nginx/*.conf.pre-*`) and TLS keys are passed over.

Nothing the live configuration names is removed: every systemd unit and drop-in (the surfd drop-in names ~1,170 paths:
deleting one stops surfd starting), nginx, cron, the surfd home's own files, the live generation's manifest and
identity, the namespace observer's policy; nor anything a running process has open, maps or runs; nor a symlink.
So old generation roots and the backup copies the surfd drop-in lists stay until a generation installs a drop-in that
no longer names them (P1702's kit work).

The newest 2 STAGED generations (`gen<N>-*` holding `backend/candidate.json`; a bare mkdir does not count) are kept
whole, and so is every root their own transition code names (`backend/operator`, `retained`, `root-proposal`): the
`ac-lexical-...` activation lock every owner install and swap takes, the retained inputs, and the previous
generation's proposed drop-in. An unreadable `backend/candidate.json` stops the run (it never guesses which generations exist);
an abandoned stage still counts, so `rm -r` it while it is inert. With the trimmed drop-in (gen1702 kit) the old roots therefore go once BOTH kept
generations run trimmed drop-ins, i.e. after the generation after gen1702; until then the previous drop-in in the owner
backup stays restorable (useful only before that generation's swap). This rule must be deployed before the gen1702
owner install (its step 4 checks the deployed file for the rule's code by content). Dead constants in carried-forward retained code keep gen1603,
ac-resume-20261109T0300Z-c2aa and ac-next-20261110T1712Z-c66e (~1.9 GB) indefinitely.

A session that needs its task root kept past 14 idle days puts an empty `RETAIN` file in it. A root is also kept
while anything in it changed (mtime or ctime) in 14 days, while part of it is unreadable or another user's, or if it
crosses a mount.

## Install / update (as proto; no root: proto lingers)
```sh
C=<commit>; D=/srv/nvme/ftesurf-ops/retention; S=/srv/nvme/ftesurf-ops/tasupd-src-<any checkout with $C>
git -C $S cat-file blob $C:tools/pi_retention.py > $D/pi_retention.py.new && mv $D/pi_retention.py.new $D/pi_retention.py
echo $C > $D/SOURCE.txt
for u in ftesurf-retention.service ftesurf-retention.timer; do git -C $S cat-file blob $C:tools/pi-retention/$u > ~/.config/systemd/user/$u; done
systemctl --user daemon-reload && systemctl --user enable --now ftesurf-retention.timer
python3.11 -I -B $D/pi_retention.py            # dry run: what the next run removes
```
Log: /srv/nvme/ftesurf-ops/retention/retention.log (its last 2000 lines). `systemctl --user list-timers`.
