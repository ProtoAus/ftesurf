#!/usr/bin/env python3
"""Make synthetic HEADER-ONLY browser fixtures, never playable/evidence runs.

Pass these files to runlines_smoke.py --put under data/runs/surf_dune/stage_2/.
Only write to an owned task-root fixture directory, never an install's data/.
"""
import argparse
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    for name, flags in [('0000100_pb.rec', 0), ('0000200_shadow.rec', 129),
                        ('0000300_shadow.rec', 1), ('0000400_cheat.rec', 257),
                        ('0000500_cheat.rec', None), ('0000600_last.rec', None)]:
        header = 'FTESURF-REC 1\nowner "Synthetic browser fixture"\n'
        if flags is not None:
            header += f'flags {flags}\n'
        (args.output / name).write_text(header + 'begin\n', encoding='utf-8')
    print('Created six header-only fixtures; do not feed them to the verifier.')


if __name__ == '__main__':
    main()
