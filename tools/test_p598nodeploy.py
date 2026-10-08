#!/usr/bin/env python3
"""Acting -Engine -NoDeploy control against both installs, including rollback files."""
from pathlib import Path
import argparse
import hashlib
import os
import json
import subprocess
ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    result = {}
    for root in (ROOT,Path('C:/FTESurf'),Path('C:/FTEQuake')):
        paths = list(root.glob('fte*.exe*'))+list(root.glob('fteplug_*.dll*'))
        paths += [root/'ftesurf'/name for name in ('qwprogs.dat','qwprogs.dat.prev','csprogs.dat',
                  'csprogs.dat.prev','menu.dat','menu.dat.prev','ftesurf.cfg','installed.lst','crashaddr.txt')]
        for p in paths:
            result[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fte',type=Path,default=Path('C:/msys64/home/Lex/fteqw-ui-bridge'))
    p.add_argument('--log',type=Path,required=True); a=p.parse_args()
    before=snapshot(); env=os.environ.copy(); env.pop('MSYS2_ARG_CONV_EXCL',None)
    with a.log.open('w') as out:
        rc=subprocess.run(['pwsh','-NoProfile','-File',str(ROOT/'src/build.ps1'),'-Engine','-NoDeploy',
                           '-Jobs','8','-FteRoot',str(a.fte)],cwd=ROOT/'src',env=env,stdout=out,stderr=subprocess.STDOUT).returncode
    after=snapshot()
    a.log.with_suffix('.hashes.json').write_text(json.dumps({'before':before,'after':after},indent=2)+'\n')
    assert before == after, 'NoDeploy changed install/rollback bytes or path presence'
    text=a.log.read_text(errors='replace')
    assert rc == 0 and 'NoDeploy: native outputs retained' in text, 'Build/native guard did not act'
    assert '==> Deploy ->' not in text, 'Deployment branch acted'
    unknown=subprocess.run(['pwsh','-NoProfile','-File',str(ROOT/'src/build.ps1'),'-NoDeplooy'],
                           cwd=ROOT/'src',env=env,capture_output=True,text=True)
    assert unknown.returncode != 0 and 'QuakeC' not in unknown.stdout, 'Unknown option silently accepted'
    incompatible=subprocess.run(['pwsh','-NoProfile','-File',str(ROOT/'src/build.ps1'),'-NoDeploy','-Pi'],
                                cwd=ROOT/'src',env=env,capture_output=True,text=True)
    assert incompatible.returncode != 0 and 'QuakeC' not in incompatible.stdout, 'NoDeploy/Pi accepted'
    assert after == snapshot(), 'Rejected commands changed install bytes'
    print('P595 NoDeploy: real native/QC build; both installs and rollback/progs/cfg sentinels unchanged;',len(before),'hash witnesses; exit',rc)
