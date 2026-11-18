# P1618 delivery -- r2gateway LIVE 18 Nov 2026 23:08Z (19 Nov AEDT), Claude Code worldofsurf-15, Lex's sudo

## Map/zone redirect (ftesurf-r2gateway, runtime /srv/nvme/ftesurf-ops/r2gateway-4a3f)

- r2gateway.py cfc6c2c4 -> 0d5873ef (= game main c6663d57 tools/r2gateway.py); gateway.json 8a4f58ea -> 8eb04e04 (adds
  "public_base": "https://maps.proto.bar"). Backups beside them: r2gateway.py.pre1618-20261118T230758Z,
  gateway.json.pre1618-20261118T230758Z. bundle.json still names the October install (the installer is one-time).
- Installed by root-1618.sh (task root artifacts/; Lex ran it after a sha256 check): hash-checked .new files, copies,
  mv, systemctl restart, then a loopback request that must answer a maps.proto.bar redirect within 10 s or the old
  files go back. It answered.
- maps.proto.bar: R2 custom domain on bucket ftesurf-public + Cloudflare cache rule (hostname equals maps.proto.bar,
  eligible, edge TTL from Cache-Control), both set up by Lex on 19 Nov. dl.proto.bar is a different bucket.
- Postflight: 23:12:58Z, ledger side files absent after r2mirror's 23:05:03 run (formerly = Pi fallback): four maps
  302 -> maps.proto.bar; full surf_vitamin_e 103 MB in 9.3 s twice; cf-cache MISS then HIT.
- Rollback: `cd /srv/nvme/ftesurf-ops/r2gateway-4a3f && sudo cp -p r2gateway.py.pre1618-20261118T230758Z r2gateway.py &&
  sudo cp -p gateway.json.pre1618-20261118T230758Z gateway.json && sudo systemctl restart ftesurf-r2gateway`.
  Immediate bypass (maps from the Pi): `sudo systemctl stop ftesurf-r2gateway`.
- Why a map came from the Pi, from now on: `sudo journalctl -u ftesurf-r2gateway | grep "disk for"`.

## Lobby logs

- History archived (gzip -1) to /srv/nvme/ftesurf-server/logs-archive/server<N>-until-<UTC>.log.gz: 1-3 at 18:38Z by
  proto, 4-12 at 23:08Z by root-1618.sh (they are root's: systemd creates StandardOutput=append: files). 16 GB -> 489 MB;
  /srv/nvme free 59 -> 74 GB. Live files truncated in place (copytruncate semantics).
- /etc/logrotate.d/ftesurf-lobbies (22f0b3c6): daily, rotate 30, compress, copytruncate, dateext; logrotate.timer runs
  00:00Z. A log logrotate has not seen before rotates from its second daily run.
- The flood itself ("Extension FTESURF_QC_FILESTREAM_HASH is supported", ~3 KB/s a lobby) stops with P1617's progs at
  the next lobby restart (worldofsurf-58, main 70835ae1).
