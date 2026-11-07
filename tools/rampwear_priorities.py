#!/usr/bin/env python3
"""Freeze the owner's public bonus sheet and report exact-course cosmetic coverage.

This is a cosmetic inventory, not run verification, measured play counts or proof
that every surface/course is covered. Inputs and player identifiers stay private.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re

SOURCE = 'https://docs.google.com/spreadsheets/d/1Hft-1XdK7lge5WWqP5hrNsSUJw_Ss2PS-t-c3CTawpQ'
# Sheet shorthand -> installed revision; never feed another revision's replay to a BSP.
ALIASES = {'surf_android': 'surf_android_ksf', 'surf_cavemissile': 'surf_cavemissile_fix',
           'surf_enlightened': 'surf_enlightened_ksf', 'surf_pandemonium': 'surf_pandemonium_njv',
           'surf_revolution': 'surf_revolution_fix'}


def parse(raw):
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
    if not rows or len(rows[0]) < 12 or rows[0][3] != 'Unit Bonuses' or rows[0][7] != 'Strafe Bonuses':
        raise ValueError('unexpected sheet layout')
    bonuses = {}
    for rownum, row in enumerate(rows[3:], 4):
        for column, category in ((3, 'unit'), (7, 'strafe'), (11, 'to_be_added')):
            if len(row) <= column or not row[column].strip():
                continue
            label = row[column].strip().lower()
            match = re.fullmatch(r'([a-z0-9_]+)\s+b([1-9][0-9]*)(?:\s+\([^()]*\))*', label)
            if not match:
                raise ValueError('unparsed course cell at row %d column %d' % (rownum, column + 1))
            sheet_map, bonus = 'surf_' + match[1], int(match[2])
            name = ALIASES.get(sheet_map, sheet_map)
            entry = bonuses.setdefault((name, bonus), {'map': name, 'bonus': bonus, 'mentions': []})
            entry['mentions'].append({'sheet_map': sheet_map, 'category': category, 'label': label,
                                      'tier_or_style': row[column + 1].strip() if len(row) > column + 1 else '',
                                      'row': rownum})
    if not bonuses:
        raise ValueError('empty bonus sheet')
    return {'source': SOURCE, 'sheet_sha256': hashlib.sha256(raw).hexdigest(),
            'aliases': ALIASES, 'bonuses': [bonuses[key] for key in sorted(bonuses)]}


def coverage(priorities, inventory, reports):
    result = dict(priorities)
    result['coverage_definition'] = ('held exact-map bonus recording and a ready whole-map bake; '
                                     'not proof every bonus ramp surface was touched or a playability verdict')
    result['bonuses'] = []
    for entry in priorities['bonuses']:
        name = entry['map']
        held = inventory['maps'].get(name, {})
        report = reports.get(name, {})
        course_held = [entry['bonus'], 0] in held.get('courses', [])
        result['bonuses'].append(dict(entry, exact_course_input_held=course_held,
                                      map_bake_status=report.get('status', 'not_baked'),
                                      cosmetic_course_input_and_map_ready=course_held and report.get('status') == 'ready'))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sheet', type=Path, required=True)
    p.add_argument('--inventory', type=Path)
    p.add_argument('--reports', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    doc = parse(a.sheet.read_bytes())
    if bool(a.inventory) != bool(a.reports):
        p.error('--inventory and --reports must be supplied together')
    if a.inventory:
        reports = {}
        for f in a.reports.glob('surf_*.json'):
            report = json.loads(f.read_text(encoding='utf-8'))
            if report.get('map'):
                reports[report['map']] = report
        doc = coverage(doc, json.loads(a.inventory.read_text(encoding='utf-8')), reports)
    # Immutable receipt: never silently rewrite an earlier coverage claim.
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
    print(json.dumps({'bonuses': len(doc['bonuses']), 'maps': len({b['map'] for b in doc['bonuses']}),
                      'mentions': sum(len(b['mentions']) for b in doc['bonuses']),
                      'sheet_sha256': doc['sheet_sha256']}))


if __name__ == '__main__':
    main()
