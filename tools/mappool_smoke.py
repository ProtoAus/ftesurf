#!/usr/bin/env python3
"""Acting map pool/parser/filter smoke in an owned content overlay.

python tools/mappool_smoke.py --qc-artifacts <build-nodeploy-dir> --output-dir <owned task root>/menu
No install swaps, no shared player data, no network consent, no lobby processes.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--qc-artifacts', type=Path, required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    a = ap.parse_args()
    out = a.output_dir.resolve()
    if not any((p/'OWNER.md').is_file() for p in (out, *out.parents)):
        raise ValueError('output-dir requires an owned task root')
    out.mkdir(exist_ok=False, parents=True)
    manifest = out/'mapdl.txt'
    manifest.write_text('FTESURF-MAPDL 1\n'
                        'dl surf_aircontrol surf m 2 1 2026-10-14 0 2 0 - 1 0\n'
                        'dl surf_aircontrol_ksf surf k 1 1 2026-10-14 0 0 1 surf_aircontrol 0 1\n'
                        'dl surf_ace surf m 1 1 2026-10-14 0 1 0 - 1 0\n'
                        'dl surf_dune surf m 1 1 2026-10-14 0 1 0 - 0 1\n'
                        'dl surf_p698disabled surf k 1 1 2026-10-14 0 0 1 - 1 0\n')
    consent = out/'fixture-offline-consent.txt'
    consent.write_text('version 1\n// synthetic offline-only test fixture, not owner consent\n')
    result = subprocess.run([sys.executable, str(ROOT/'tools/runlines_smoke.py'),
                             str(ROOT/'ftesurf/cfg/test/p698mappool.cfg'),
                             '--output-dir', str(out), '--mount', '--timeout','90',
                             '--ssqc', str(a.qc_artifacts/'qwprogs.dat'),
                             '--csqc', str(a.qc_artifacts/'csprogs.dat'),
                             '--mqc', str(a.qc_artifacts/'menu.dat'),
                             '--put', 'data/mapdl.net.txt='+str(manifest),
                             '--put', 'data/consent.txt='+str(consent)],
                            capture_output=True, text=True)
    (out/'runtime.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError('runtime failed; see '+str(out/'runtime.log'))
    games = list(out.glob('ftesurf-runlines-*/ftesurf'))
    if len(games) != 1:
        raise RuntimeError('expected one owned gamedir')
    text = (games[0]/'logs/runlines_smoke.log').read_text(errors='replace')
    required = ('ui_pool: surf_aircontrol enabled 0 zones 1 visible 1',
                'ui_pool: surf_aircontrol_ksf enabled 1 zones 0 linked surf_aircontrol',
                'plays surf_aircontrol_ksf;',
                'ui_pool: surf_ace enabled 0 zones 1 visible 0',
                'ui_pool: surf_dune enabled 1 zones 0 visible 1',
                'ui_find: surf_p698disabled view 0 first -',
                'ui_find: surf_dune view 1 first surf_dune',
                'ui_find: surf_aircontrol view 1 first surf_aircontrol')
    for needle in required:
        assert needle in text, 'missing acting result: '+needle
    assert not re.search(r'(?:^|\n)(?:Error in|QC error)',text), 'QC runtime error'
    print('PASS per-build flags, missing zones, related-build fallback, disabled switch refusal, enabled/disabled filter controls')
    print('Screenshot retained for visual inspection:', games[0]/'screenshots')


if __name__ == '__main__':
    main()
