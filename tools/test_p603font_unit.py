#!/usr/bin/env python3
"""Read-only positive/negative controls on completed real font matrices."""
from pathlib import Path
from unittest.mock import patch
import argparse
import hashlib
import json
import re
from PIL import Image
from p603scores import grade


def run(current, previous):
    original_read = Path.read_text
    original_glob = Path.glob
    original_open = Image.open
    sources = {}
    for rig in (current, previous):
        for p in [rig / 'report.json', *rig.glob('*/ftesurf/logs/scores*.log'),
                  *rig.glob('*/ftesurf/screenshots/font*.png')]:
            sources[p] = hashlib.sha256(p.read_bytes()).hexdigest()
    checks = 0
    def expect(rig, name, texts=None, hidden=None, wrong_image=None):
        nonlocal checks
        replacements = texts or {}
        def read(path, *args, **kwargs):
            return replacements[path] if path in replacements else original_read(path, *args, **kwargs)
        def glob(path, pattern):
            return iter(()) if hidden and path == hidden.parent and pattern == hidden.stem + '.*' else original_glob(path, pattern)
        def image(path, *args, **kwargs):
            return original_open(wrong_image[1] if wrong_image and Path(path) == wrong_image[0] else path, *args, **kwargs)
        with patch.object(Path, 'read_text', read), patch.object(Path, 'glob', glob), patch.object(Image, 'open', image):
            errors = grade(rig)
        checks += 1
        if not errors: raise AssertionError('accepted mutant: ' + name)
        print('Rejected', name)
    for rig in (current, previous):
        errors = grade(rig)
        if errors: raise AssertionError('positive matrix failed: ' + '; '.join(errors))
        checks += 1
    log = current / 'native1/ftesurf/logs/scores.log'
    text = original_read(log, errors='replace')
    def record(kind, label):
        matches = re.findall(r'^.*P603 ' + kind + ' ' + label + r' [^\r\n]+\r?\n', text, re.M)
        if len(matches) != 1: raise AssertionError('unique mutation record missing: ' + label)
        return matches[0]
    def change(kind, label, old, new, name):
        line = record(kind, label)
        if line.count(old) != 1: raise AssertionError('unique mutation field missing: ' + name)
        expect(current, name, {log: text.replace(line, line.replace(old, new))})
    line = record('FONT', 'font16')
    expect(current, 'missing font probe', {log: text.replace(line, '')})
    expect(current, 'duplicate font probe', {log: text.replace(line, line + line)})
    for old, new, name in [('snapped=16', 'snapped=13', 'wrong snapping'),
                           ('committed=16', 'committed=13', 'wrong bake metadata'),
                           ('count=60', 'count=59', 'lost rows/metadata'),
                           ('committed=16', 'committed=nan', 'nonfinite output'),
                           (' count=60', '', 'incomplete metadata'),
                           ('count=60', 'count=60 extra=1', 'unknown metadata')]:
        change('FONT', 'font16', old, new, name)
    change('FONT', 'font_norm1', 'request=18', 'request=17', 'inert numeric request')
    change('FONTREQUEST', 'font_norm7', 'text=nan', 'text=bogus', 'inert nonfinite spelling')
    raw = record('FONTREQUEST', 'font_norm8')
    expect(current, 'missing raw request', {log: text.replace(raw, '')})
    change('ACTIVE', 'font24_watch', 'watch=1', 'watch=0', 'inert watch')
    change('ACTIVE', 'font24_watch', 'samples=20', 'samples=0', 'empty watch body')
    change('STATE', 'font24_next', 'page=6', 'page=0', 'inert paging')
    change('ACTIVE', 'font_stale', 'watch=0', 'watch=1', 'stale held activation')
    begin = record('STATE', 'font_bakes_begin')
    end = record('STATE', 'font_bakes_end')
    normalized = record('STATE', 'font_norm8')
    normrev = re.search(r'\brevision=(\d+)', normalized)[1]
    expect(current, 'equivalent normalized request republishes authority',
           {log: text.replace(normalized, re.sub(r'\brevision=\d+', 'revision=' + str(int(normrev) + 1), normalized))})
    start_h = re.search(r'\bh=(\d+)', begin)[1]
    expect(current, 'context reopened on size change', {log: text.replace(end, re.sub(r'\bh=\d+', 'h=' + str(int(start_h) + 1), end))})
    rev = re.search(r'\brevision=(\d+)', end)[1]
    stale = record('STATE', 'font_stale')
    expect(current, 'stale size subject did not act', {log: text.replace(stale, re.sub(r'\brevision=\d+', 'revision=' + rev, stale))})
    start = text.index('P603 FONT font24 ')
    stop = text.index('P603 FONT font24_watch ')
    interval = text[start:stop]
    if interval.count('P603 Row0  0:01.500  20 samples') != 1: raise AssertionError('watch identity control missing')
    expect(current, 'wrong action identity cannot borrow later control',
           {log: text[:start] + interval.replace('P603 Row0  0:01.500  20 samples', 'P603 Row1  0:01.500  20 samples') + text[stop:]})
    for label, mode in [('font_bakes_begin', 'missing'), ('font_bakes_end', 'upload'), ('font_bakes_end', 'duplicate')]:
        start = text.index('P603 FONT ' + label + ' ')
        stop = text.find('P603 FONT ', start + 1)
        segment = text[start:stop]
        status = re.search(r'^.*UIIMGUI STATUS [^\r\n]+\r?\n', segment, re.M)[0]
        if mode == 'missing': altered = segment.replace(status, '')
        elif mode == 'duplicate': altered = segment.replace(status, status + status)
        else: altered = segment.replace(status, re.sub(r'\buploads=(\d+)', lambda m: 'uploads=' + str(int(m[1]) + 1), status))
        expect(current, 'atlas ' + mode + ' ' + label, {log: text[:start] + altered + text[stop:]})
    report = current / 'report.json'
    data = json.loads(original_read(report))
    for field in ('font', 'font_fallback'):
        bad = dict(data); bad.pop(field)
        expect(current, 'removed plan ' + field, {report: json.dumps(bad)})
    image = current / 'native1/ftesurf/screenshots/font20.png'
    expect(current, 'missing screenshot', hidden=image)
    expect(current, 'wrong actual glyph size', wrong_image=(image, image.with_name('font13.png')))
    image2 = current / 'native2/ftesurf/screenshots/font20.png'
    expect(current, 'different physical ink at second virtual scale', wrong_image=(image2, image2.with_name('font24.png')))

    oldlog = previous / 'native1/ftesurf/logs/scores.log'
    oldtext = original_read(oldlog, errors='replace')
    for label, old, new, name in [('font_old_cover', 'failed=1', 'failed=0', 'old provider did not latch'),
                                   ('font_old_quiet', 'h=0', 'h=7', 'old provider retained context')]:
        line = re.search(r'^.*P603 STATE ' + label + r' [^\r\n]+\r?\n', oldtext, re.M)[0]
        expect(previous, name, {oldlog: oldtext.replace(line, line.replace(old, new))})
    line = re.search(r'^.*P603 ACTIVE font_old_watch [^\r\n]+\r?\n', oldtext, re.M)[0]
    expect(previous, 'old fallback watch did not act', {oldlog: oldtext.replace(line, line.replace('watch=1', 'watch=0'))})
    line = re.search(r'^.*P603 FONT font_old_recovered [^\r\n]+\r?\n', oldtext, re.M)[0]
    expect(previous, 'old default schema failed to recover', {oldlog: oldtext.replace(line, line.replace('committed=13', 'committed=0'))})
    for path, digest in sources.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise AssertionError('fixture changed: ' + str(path))
    print(f'Font reader checks: {checks}, failed=0; all fixture hashes unchanged')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('current', type=Path)
    p.add_argument('previous', type=Path)
    a = p.parse_args()
    run(a.current, a.previous)
