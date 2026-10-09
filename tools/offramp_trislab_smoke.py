#!/usr/bin/env python3
"""PRIVATE setup-only full native BIH back-slab query installer; NEVER ship."""
import argparse
import hashlib
from pathlib import Path

from offramp_contact_smoke import isolated
from offramp_tricopy_smoke import prepare as copy_prepare
from stitched_rewind_smoke import once

ROOT = Path(__file__).resolve().parent.parent
TARGET = 'offramp_trislab_native.inc'


def source_digest():
    return hashlib.sha256(b''.join((ROOT/'tools'/n).read_bytes() for n in
                                  (TARGET, 'offramp_trislab_smoke.py'))).hexdigest()


def prepare(engine):
    common = engine/'engine/common'
    if (common/TARGET).exists():
        raise RuntimeError('Refusing to overwrite private back-slab include')
    # Preserve the old layers and their digests; new setup queries restore state
    # before the unchanged twenty-case mover, never alter its capture category.
    prepared = copy_prepare(engine)
    bih = common/'com_bih.c'
    prepared[bih] = once(prepared[bih], '#include "offramp_origin_selftest.inc"',
                         'static void OfframpTriSlab_Selftest(void);\n#include "offramp_origin_selftest.inc"')
    prepared[bih] += (f'\n#define OFFRAMP_TRISLAB_SOURCE_SHA256 "{source_digest()}"\n'
                      f'#include "{TARGET}"\n')
    setup = common/'offramp_origin_selftest.inc'
    prepared[setup] = once(prepared[setup], '\tOfframpTriCopy_Selftest(&world);',
                          '\tOfframpTriCopy_Selftest(&world);\n\tOfframpTriSlab_Selftest();')
    prepared[common/TARGET] = (ROOT/'tools'/TARGET).read_text()
    return prepared


def instrument(engine):
    isolated(engine)
    prepared = prepare(engine)
    for path, text in prepared.items():
        path.write_text(text, newline='' if path.name == 'offramp_motion_native.inc' else None)
    print('Private setup-only native back-slab seams installed:', engine)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--instrument-native', type=Path, required=True)
    instrument(ap.parse_args().instrument_native)


if __name__ == '__main__':
    main()
