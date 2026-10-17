#!/bin/sh
# P770: hand surfd from the serving generation OLD to the successor in ROOT.
#   sh cutover.sh ROOT SHA OLD
# Refuses before any change unless the pidfile master is OLD's and every lobby
# is empty. Each step prints a UTC time. On a failure after step 1, run rollback.sh.
set -eu
ROOT=$1; SHA=$2; OLD=$3
PY=/usr/bin/python3.11
OLDGEN=$($PY -c 'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' $OLD/state/manifest.json)
GUARD_OLD="$PY -I $OLD/control/surfd_transition_guard.py --state-dir $OLD/state"
GUARD_NEW="$PY -I $ROOT/control/surfd_transition_guard.py --state-dir $ROOT/state"
say() { echo "$(date -u +%H:%M:%S.%N | cut -c1-12)Z $*"; }
umask 077

MASTER=$(cat /srv/nvme/surfd/surfd.pid)
tr '\0' ' ' < /proc/$MASTER/cmdline | grep -q "$OLD/control witness_wsgi:app" || { say "REFUSED: pidfile master $MASTER is not $OLD's"; exit 3; }
[ "$(awk '{print $4}' /proc/$MASTER/stat)" = 1 ] || { say "REFUSED: master $MASTER is not a ppid-1 master"; exit 3; }
$GUARD_NEW status | grep -q '"admission": "CLOSED"' || { say "REFUSED: new guard is not CLOSED"; exit 3; }
$GUARD_NEW status | grep -q "\"generation\": \"$SHA\"" || { say "REFUSED: $SHA is not the successor's generation"; exit 3; }
for f in acceptance-receipt.json worker-witness.json candidate-grant.json; do
  [ ! -e $ROOT/control/$f ] || { say "REFUSED: $ROOT/control/$f exists; a used successor root is not reused"; exit 3; }
done
crontab -l > $ROOT/control/crontab.before
sed "s#$OLD/control/surfd_transition_guard.py --state-dir $OLD/state launch --generation $OLDGEN#$ROOT/control/surfd_transition_guard.py --state-dir $ROOT/state launch --generation $SHA#" \
  $ROOT/control/crontab.before > $ROOT/control/crontab.after
N=$(diff $ROOT/control/crontab.before $ROOT/control/crontab.after | grep -c '^>' || true)
[ "$N" = 4 ] || { say "REFUSED: expected 4 guarded cron lines, found $N"; exit 3; }
# A cron launch holds admission shared while it runs; step 3 would wait on it.
flock -n -x $OLD/state/admission.lock true || { say "REFUSED: a guarded cron job is running; try again"; exit 4; }
PLAYERS=$(curl -s -m 5 http://127.0.0.1:8084/lobbies.json | $PY -c 'import json,sys; d=json.load(sys.stdin); print(sum(l["players"] for l in d["lobbies"]), len(d["lobbies"]))')
say "lobbies: players lobbies = $PLAYERS"
[ "${PLAYERS%% *}" = 0 ] || { say "REFUSED: players are on the lobbies"; exit 4; }

say "1. close $OLDGEN (its app answers 503 except /health from here)"
$GUARD_OLD --timeout 1 close || true
grep -q '"admission": "CLOSED"' $OLD/state/state.json || { say "FAIL: old guard not CLOSED"; exit 5; }

say "2. stop the old master $MASTER"
kill -TERM "$MASTER"
i=0
while [ -d /proc/$MASTER ] && [ $i -lt 45 ]; do sleep 1; i=$((i+1)); done
if [ -d /proc/$MASTER ]; then
  say "   master survived 45 s: SIGKILL to the old generation's gunicorn processes"
  for p in $(pgrep -f "$OLD/control witness_wsgi:app" || true); do kill -KILL "$p" 2>/dev/null || true; done
  sleep 2
fi
[ ! -d /proc/$MASTER ] || { say "FAIL: master $MASTER still alive; run rollback.sh"; exit 6; }
i=0
while ss -ltnH | grep -q ':8084 ' && [ $i -lt 20 ]; do sleep 1; i=$((i+1)); done
ss -ltnH | grep -q ':8084 ' && { say "FAIL: 8084 still bound"; exit 6; }
say "   stopped after ${i}s port wait"

say "3. finish the old drain (a failure here does not stop the successor)"
$GUARD_OLD --timeout 60 close || say "   WARN: old drain did not finish; rollback.sh closes it again first"

say "4. start the successor candidate"
CLOSURE=$($PY -c 'import json,sys; print(json.load(open(sys.argv[1]))["closure"])' $ROOT/state/state.json)
printf '{"generation":"%s","closure":"%s","route":"server","authorized":true}\n' "$SHA" "$CLOSURE" > $ROOT/control/candidate-grant.json
chmod 600 $ROOT/control/candidate-grant.json
setsid -f sh -c "exec $GUARD_NEW --timeout 5 candidate --generation $SHA --route server --authorization $ROOT/control/candidate-grant.json >> $ROOT/control/candidate.log 2>&1 < /dev/null"
i=0
while [ $i -lt 60 ]; do
  [ -f $ROOT/state/candidate.json ] && [ -f $ROOT/control/worker-witness.json ] && curl -s -m 2 http://127.0.0.1:8084/health | grep -q '"ok":true' && break
  sleep 1; i=$((i+1))
done
[ -f $ROOT/control/worker-witness.json ] || { say "FAIL: no worker witness after 60 s"; tail -30 $ROOT/control/candidate.log; exit 7; }
say "   candidate up after ${i}s: $(cat $ROOT/state/candidate.json)"

say "5. receipt and reopen"
$PY - "$ROOT" <<'EOF'
import json, os, sys
root = sys.argv[1]
m = json.load(open(root + '/control/guard-manifest.json'))
s = json.load(open(root + '/state/state.json'))
c = json.load(open(root + '/state/candidate.json'))
w = json.load(open(root + '/control/worker-witness.json'))
assert w['generation'] == m['generation'] and w['closure'] == s['closure'] and w['schema'] == 20, w
r = dict(generation=m['generation'], closure=s['closure'], source_home=m['source_home'],
         hashes=m['hashes'], schema=20, accepted=True, process=c['process'])
fd = os.open(root + '/control/acceptance-receipt.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as f:
    json.dump(r, f, sort_keys=True); f.write('\n')
EOF
$GUARD_NEW reopen --generation "$SHA" --receipt $ROOT/control/acceptance-receipt.json

say "6. read back"
curl -s -m 5 -o /dev/null -w 'board %{http_code}\n' 'http://127.0.0.1:8084/api/board?map=surf_ace&track=0&leg=0&tier=ranked&style=clean&limit=5' || true
curl -s -m 5 'http://127.0.0.1:8084/api/social/menu/challenge?op=list&who=-' | head -c 120 || true; echo
curl -s -m 5 http://127.0.0.1:8084/health || true; echo
ps -eo pid,ppid,lstart,cmd | grep "$ROOT/control witness_wsgi" | grep -v grep | cut -c1-120 || true

say "7. crontab: the guarded routes move to the successor (rewrite checked before step 1)"
crontab -l | cmp -s - $ROOT/control/crontab.before || { say "FAIL: crontab changed during the cutover; not replaced"; exit 8; }
crontab $ROOT/control/crontab.after
say "DONE: 4 cron lines moved; $SHA serving"
