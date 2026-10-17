#!/bin/sh
# P770: put the previous generation OLD back if the successor in ROOT failed or misbehaves.
#   sh rollback.sh ROOT OLD
# The successor keeps serving until OLD is known to drain; nothing runs if OLD is OPEN.
set -eu
ROOT=$1; OLD=$2
PY=/usr/bin/python3.11
OLDGEN=$($PY -c 'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' $OLD/state/manifest.json)
GUARD_OLD="$PY -I $OLD/control/surfd_transition_guard.py --state-dir $OLD/state"
GUARD_NEW="$PY -I $ROOT/control/surfd_transition_guard.py --state-dir $ROOT/state"
say() { echo "$(date -u +%H:%M:%S.%N | cut -c1-12)Z $*"; }
umask 077
stop() {    # TERM, then KILL after 45 s, every gunicorn process of one generation
  for p in $(pgrep -f "$1/control witness_wsgi:app" || true); do kill -TERM "$p" 2>/dev/null || true; done
  i=0; while pgrep -f "$1/control witness_wsgi:app" > /dev/null && [ $i -lt 45 ]; do sleep 1; i=$((i+1)); done
  for p in $(pgrep -f "$1/control witness_wsgi:app" || true); do kill -KILL "$p" 2>/dev/null || true; done
  sleep 1
}

$GUARD_OLD status | grep -q '"admission": "CLOSED"' || { say "REFUSED: $OLDGEN is OPEN; nothing to roll back"; exit 3; }

say "1. a CLOSED old master (cutover stopped between its steps 1 and 2) only answers 503: stop it"
stop "$OLD"

say "2. drain the old guard; the successor is untouched if this fails"
# momrequests.service holds whichever generation's admission it imported under.
timeout 300 systemctl --user stop momrequests.service || say "   WARN: momrequests stop did not finish"
$GUARD_OLD --timeout 60 close || { say "FAIL: the old guard did not drain; inspect $OLD/state"; exit 7; }

say "3. close the successor and stop it"
$GUARD_NEW --timeout 1 close || true
stop "$ROOT"
i=0; while ss -ltnH | grep -q ':8084 ' && [ $i -lt 30 ]; do sleep 1; i=$((i+1)); done
ss -ltnH | grep -q ':8084 ' && { say "FAIL: 8084 still bound by something else; inspect by hand"; exit 6; }
$GUARD_NEW --timeout 10 close || true

say "4. restart $OLDGEN through its own guard"
CLOSURE=$($PY -c 'import json,sys; print(json.load(open(sys.argv[1]))["closure"])' $OLD/state/state.json)
G=$ROOT/control/rollback-grant.json
rm -f $G
printf '{"generation":"%s","closure":"%s","route":"server","authorized":true}\n' "$OLDGEN" "$CLOSURE" > $G
chmod 600 $G
setsid -f sh -c "exec $GUARD_OLD --timeout 5 candidate --generation $OLDGEN --route server --authorization $G >> $ROOT/control/rollback-candidate.log 2>&1 < /dev/null"
i=0
while [ $i -lt 60 ]; do
  [ -f $OLD/state/candidate.json ] && curl -s -m 2 http://127.0.0.1:8084/health | grep -q '"ok":true' && break
  sleep 1; i=$((i+1))
done
[ -f $OLD/state/candidate.json ] && curl -s -m 2 http://127.0.0.1:8084/health | grep -q '"ok":true' \
  || { say "FAIL: the old candidate did not come up; see $ROOT/control/rollback-candidate.log"; exit 8; }
sleep 3
$PY - "$OLD" "$ROOT" <<'EOF'
import json, os, sys
old, root = sys.argv[1], sys.argv[2]
m = json.load(open(old + '/state/manifest.json'))
s = json.load(open(old + '/state/state.json'))
c = json.load(open(old + '/state/candidate.json'))
r = dict(generation=m['generation'], closure=s['closure'], source_home=m['source_home'],
         hashes=m['hashes'], schema=20, accepted=True, process=c['process'])
path = root + '/control/rollback-receipt.json'
if os.path.exists(path): os.remove(path)
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    json.dump(r, f, sort_keys=True); f.write('\n')
EOF
$GUARD_OLD reopen --generation "$OLDGEN" --receipt $ROOT/control/rollback-receipt.json

say "4b. /srv/nvme/surfd's stubs and run.sh back, where they are the successor's"
for f in surfd.py ksfimport.py ksfgrab.py ksfprofile.py tools/ksfconvert.py tools/ksfreplay_info.py run.sh; do
  if [ -f $ROOT/control/pre/$f ] && cmp -s /srv/nvme/surfd/$f $ROOT/control/stubs/$f; then
    cp $ROOT/control/pre/$f /srv/nvme/surfd/$f.p770old
    chmod --reference=$ROOT/control/pre/$f /srv/nvme/surfd/$f.p770old
    mv -f /srv/nvme/surfd/$f.p770old /srv/nvme/surfd/$f
  fi
done
systemctl --user start momrequests.service || say "   WARN: momrequests did not start"

say "5. the guarded cron lines back to $OLDGEN (other lines untouched)"
SHA=$($PY -c 'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' $ROOT/state/manifest.json)
crontab -l > $ROOT/control/crontab.rollback-before
sed "s#$ROOT/control/surfd_transition_guard.py --state-dir $ROOT/state launch --generation $SHA#$OLD/control/surfd_transition_guard.py --state-dir $OLD/state launch --generation $OLDGEN#" \
  $ROOT/control/crontab.rollback-before > $ROOT/control/crontab.rollback-after
N=$(diff $ROOT/control/crontab.rollback-before $ROOT/control/crontab.rollback-after | grep -c '^>' || true)
if [ "$N" = 4 ]; then
  crontab $ROOT/control/crontab.rollback-after
elif [ "$N" != 0 ]; then
  say "   WARN: $N guarded cron lines name the successor, not 4; crontab left as it is"
fi
curl -s -m 5 http://127.0.0.1:8084/health || true; echo
say "ROLLED BACK to $OLDGEN"
