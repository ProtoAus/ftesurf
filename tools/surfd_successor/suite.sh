#!/bin/sh
# The surfd suite in a staged archive (the list surfd-deploy.ps1 runs).
#   sh suite.sh STAGE    (archive surfd/, tools/, src/shared/ and
#                        src/release/ftesurf.nginx, used by test_ksftopup)
set -e
STAGE=$1
mkdir -p $STAGE/tmp
cd $STAGE/surfd
TMPDIR=$STAGE/tmp
export TMPDIR
rc=0
for t in test_hidupload test_hid_proxy_install test_web test_recplot test_board test_join test_replays test_sweep test_surfd test_simcheck test_momboards test_momgrab test_momrequest test_accounts test_social test_ranked test_ksfimport test_ksfprofile test_ksftopup test_ksfgrab test_mapwatch test_zonefit test_variants test_mappool test_admin test_completion_pool test_story; do
  [ -f "$t.py" ] || continue
  printf '%-16s ' "$t"
  if [ "$t" = test_ksfgrab ]; then set -- --out "$STAGE/tmp/ksfgrab"; else set --; fi
  if TMPDIR=$STAGE/tmp SURFD_HOME=$(mktemp -d) python3 "$t.py" "$@" > "$STAGE/tmp/$t.out" 2>&1; then
    tail -2 "$STAGE/tmp/$t.out" | tr '\n' ' '; echo
  else
    echo "FAILED"; tail -30 "$STAGE/tmp/$t.out"; rc=1
  fi
done
if [ -f ../tools/test_ksfconvert.py ]; then
  if TMPDIR=$STAGE/tmp python3 ../tools/test_ksfconvert.py > $STAGE/tmp/test_ksfconvert.out 2>&1; then
    tail -2 $STAGE/tmp/test_ksfconvert.out
  else
    echo 'FAILED test_ksfconvert'; tail -30 $STAGE/tmp/test_ksfconvert.out; rc=1
  fi
fi
echo "SUITE_RC=$rc"
exit $rc
