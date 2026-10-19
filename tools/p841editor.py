#!/usr/bin/env python3
"""Grade a ftesurf/cfg/test/p841editor.cfg run: python tools/p841editor.py <retained rig>

The rig is planted with a hosted settings file at cap 3500 against surf_dune's zone file at
4000. A settings save that does not touch the Speed cap stages nothing; an edited cap is
written into the saved zone file without moving its crc, the file passes the publish
validator, and the next load takes the cap from that file -- each graded on a line the
subject prints, not on the cvar alone.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'surfd'))
CRC = r'zones\(sv\): \S+ on surf_dune \(\S+\) crc (\S+)'


def main():
    rig = pathlib.Path(sys.argv[1])
    gd = rig / 'ftesurf'
    text = re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '',
                  (gd / 'logs/runlines_smoke.log').read_text(errors='replace'), flags=re.M)
    text = re.sub(r'\^[0-9a-z]', '', text)
    load1, rest = text.split('P841 LOAD1', 1)
    untouched, rest = rest.split('P841 UNTOUCHED', 1)
    saved, load2 = rest.split('P841 SAVED', 1)
    checks = []

    def check(name, ok, got=''):
        checks.append(bool(ok))
        print('%s %s%s' % ('ok  ' if ok else 'FAIL', name, (' -- ' + str(got)) if got else ''))

    m = re.search(r'map ruleset: surf_dune sv_maxvelocity (\S+) from (\S+)', load1)
    check('load 1: zone file read at 4000', m and m[1] == '4000'
          and m[2] == 'maps/zones/local/surf_dune.json', m and m.group(0))
    check('load 1: the planted settings file wins at 3500',
          'map_settings: surf_dune maxvelocity 3500' in load1)
    check('load 1: the QC says the zone file asks for another cap',
          'zones: surf_dune asks maxVelocity 4000, this server runs sv_maxvelocity 3500' in load1)
    crc1 = re.findall(CRC, load1)
    check('load 1: the server hashed its zones', crc1, crc1)
    v1 = re.search(r'"sv_maxvelocity" is "([^"]*)"', untouched)
    check('load 1: sv_maxvelocity reads 3500', v1 and v1[1] == '3500', v1 and v1[1])
    check('gravity-only settings save stages no cap',
          'Saved locally; reload the hosted map to apply' in untouched
          and 'reaches lobbies' not in untouched)
    check('so the zones have nothing to save', 'nothing has changed since these zones were read' in untouched)
    check('an edited cap is staged', 'speed cap 6500 reaches lobbies with the zones' in saved)
    s = re.search(r'saved (\d+) zones to data/maps/zones/local/surf_dune\.json \(crc (\S+)\), speed cap (\S+)', saved)
    check('zone save names the cap', s and s[3] == '6500', s and s.group(0))
    f = gd / 'data/maps/zones/local/surf_dune.json'
    body = f.read_bytes() if f.is_file() else b''
    j = json.loads(body) if body else {}
    check('saved file carries maxVelocity 6500', j.get('maxVelocity') == 6500, j.get('maxVelocity'))
    try:
        import zonepub
        zonepub.validate(body)
        check('saved file passes the publish validator', True)
    except ImportError as e:
        check('publish validator importable', False, e)
    except ValueError as e:
        check('saved file passes the publish validator', False, e)
    check('the cap does not move the zone crc', s and crc1 and s[2] == crc1[-1],
          '%s vs %s' % (s and s[2], crc1 and crc1[-1]))
    m = re.search(r'map ruleset: surf_dune sv_maxvelocity (\S+) from (\S+)', load2)
    check('load 2: cap 6500 from the saved zone file', m and m[1] == '6500'
          and m[2] == 'data/maps/zones/local/surf_dune.json', m and m.group(0))
    check('load 2: the hosted settings file agrees',
          'map_settings: surf_dune maxvelocity 6500' in load2)
    check('load 2: movement names the zone file and the settings file',
          'data/maps/zones/local/surf_dune.json + data/maps/settings/local/surf_dune.cfg' in load2)
    v2 = re.search(r'"sv_maxvelocity" is "([^"]*)"', load2)
    check('load 2: sv_maxvelocity reads 6500', v2 and v2[1] == '6500', v2 and v2[1])
    crc2 = re.findall(CRC, load2)
    check('load 2: same zone crc', crc2 and crc1 and crc2[-1] == crc1[-1], crc2)
    check('load 2: no QC warning', 'asks maxVelocity' not in load2)
    print('P841 editor: %d passed, %d failed' % (sum(checks), len(checks) - sum(checks)))
    return 0 if all(checks) else 1


if __name__ == '__main__':
    sys.exit(main())
