"""Bounded physical-font scoreboard gate, synthetic input through real QC bodies."""
import math
import re
from pathlib import Path

SIZES = (13, 16, 20, 24)
NORMAL = ((14.5, 13), (18, 16), (22, 20), (128, 24), (0, 13), (-1, 13), (129, 13),
          ('nan', 13), ('inf', 13), ('-inf', 13))


def extend_config(cfg, arm, fallback=False):
    native = arm.startswith('native')
    reset = ['-showscores', 'replay off', 'waitms 300', 'scores tab local', '+showscores',
             'waitms 500', 'p603 pin', 'p603 unpin', 'waitms 700']
    def probe(label):
        return ['p603font probe ' + label, 'p603 probe ' + label]
    def click(target):
        return ['p603font move ' + target, 'waitms 200', 'p603 down', 'waitms 200',
                'p603 up', 'waitms 500']
    lines = ['set ui_native_scores_font 13', *reset]
    for size in SIZES:
        lines += [f'set ui_native_scores_font {size}', *reset, *probe(f'font{size}'),
                  f'screenshot font{size}']
        if native and not (fallback and size != 13):
            lines += click('next') + probe(f'font{size}_next')
            lines += click('previous') + probe(f'font{size}_previous')
        lines += click('watch') + probe(f'font{size}_watch') + ['replay status']
    lines += ['set ui_native_scores_font 13', *reset, *probe('font_bakes_begin'), 'ui_imgui_status'] if arm != 'absent' else ['set ui_native_scores_font 13', *reset, *probe('font_bakes_begin')]
    if not fallback:
        for index, (request, size) in enumerate(NORMAL):
            lines += [f'set ui_native_scores_font {request}', 'waitms 400', *probe(f'font_norm{index}')]
        lines += ['set ui_native_scores_font 13', 'waitms 500', *probe('font_bakes_end')]
        if arm != 'absent': lines += ['ui_imgui_status']
        lines += ['p603font move watch', 'waitms 200', 'p603 down', 'waitms 200',
                  'set ui_native_scores_font 20', 'waitms 500', 'p603 up', 'waitms 500',
                  *probe('font_stale')]
        if native:
            lines += click('watch') + probe('font_recovery_watch') + ['replay status']
    else:
        #Same gesture must cover legacy exactly once when old score schema rejects metadata.
        lines += ['set ui_native_scores_font 20', 'waitms 500', *probe('font_old_cover'),
                  'ui_imgui_status', 'waitms 800', *probe('font_old_quiet'), 'ui_imgui_status',
                  *click('watch'), *probe('font_old_watch'), 'replay status',
                  'set ui_native_scores_font 13', *reset, *probe('font_old_recovered')]
    lines += ['set ui_native_scores_font 13']
    marker = '-showscores\nreplay off\nwaitms 500\np603 probe closed1'
    if cfg.count(marker) != 1: raise ValueError('unique final closed marker required')
    return cfg.replace(marker, '\n'.join(lines) + '\n' + marker)


def captures(text):
    result = {}
    for kind, label, payload in re.findall(r'P603 (FONT|STATE|ACTIVE) (font\w+) ([^\r\n]+)', text):
        key = (kind, label)
        if key in result: raise ValueError('duplicate ' + kind + ' ' + label)
        fields = {}
        for field, value in re.findall(r'(\w+)=([^\s]+)', payload):
            if field in fields: raise ValueError('duplicate field ' + key[0] + ' ' + field)
            fields[field] = float(value)
        if kind == 'FONT':
            if set(fields) != {'request', 'snapped', 'committed', 'count'}:
                raise ValueError('incomplete/unknown FONT fields ' + label)
            if not all(math.isfinite(v) for k, v in fields.items() if k != 'request'):
                raise ValueError('non-finite FONT result ' + label)
        result[key] = fields
    return result


def grade_font(rig, report):
    errors = []
    if report.get('font') is not True: errors.append('font: planned gate required')
    if type(report.get('font_fallback')) is not bool: errors.append('font: explicit fallback plan required')
    fallback = report.get('font_fallback', False)
    pixels = {}
    for arm, result in report.get('arms', {}).items():
        def need(ok, why):
            if not ok: errors.append(arm + ': font ' + why)
        logs = list((rig / arm / 'ftesurf/logs').glob('scores*.log'))
        if len(logs) != 1: errors.append(arm + ': font unique log required'); continue
        text = logs[0].read_text(errors='replace')
        try: values = captures(text)
        except ValueError as e: errors.append(arm + ': font ' + str(e)); continue
        def get(kind, label, field):
            return values.get((kind, label), {}).get(field, -999)
        def route(label, size, cover=False):
            native = arm.startswith('native') and not cover
            need(get('FONT', label, 'snapped') == size, 'wrong snapped request ' + label)
            need(get('STATE', label, 'painted') == int(native), 'route did not act ' + label)
            need(get('FONT', label, 'committed') == (size if native else 0), 'wrong committed metadata ' + label)
            if native:
                need(get('STATE', label, 'h') > 0 and get('FONT', label, 'count') == (59 if size == 13 else 60),
                     'incomplete native rows/metadata ' + label)
        for size in SIZES:
            label = f'font{size}'
            cover = fallback and size != 13
            route(label, size, cover)
            if arm.startswith('native') and not cover:
                need(get('STATE', label + '_next', 'page') == 6 and get('STATE', label + '_previous', 'page') == 0,
                     'paging did not act at ' + str(size))
            need(get('ACTIVE', label + '_watch', 'watch') == 1 and get('ACTIVE', label + '_watch', 'samples') == 20,
                 'actual watch did not act at ' + str(size))
            #Bind identity to this action's own interval, never borrow a later Row0 control.
            start = text.find('P603 FONT ' + label + ' ')
            end = text.find('P603 FONT ' + label + '_watch ')
            need(start >= 0 and end > start and len(re.findall(r'replay: data/runs/p603scores\.map/main/0000100_p6030_pb\.rec\s+P603 Row0\s+0:01\.500\s+20 samples', text[start:end])) == 1,
                 'wrong watch identity at ' + str(size))
            images = list((rig / arm / 'ftesurf/screenshots').glob(label + '.*'))
            need(len(images) == 1, 'missing/duplicate ' + label + ' screenshot')
            if arm.startswith('native') and not cover and len(images) == 1:
                #Measure screenshot ink, not merely PNG existence/selected metadata.
                try:
                    from PIL import Image
                    rect = re.findall(r'P603 RECT ' + label + r' ([0-9.e+\-]+) ([0-9.e+\-]+) ([0-9.e+\-]+) ([0-9.e+\-]+)', text)
                    if len(rect) != 1: raise ValueError('unique physical rectangle missing')
                    ratio = 2 if arm == 'native2' else 1
                    x, y = (round(float(v) * ratio) for v in rect[0][:2])
                    with Image.open(images[0]) as source:
                        image = source.convert('RGB')
                    if image.size != (1920, 1080): raise ValueError('wrong physical screenshot dimensions')
                    crop = image.crop((x, y, x + 220, y + int(8 * size / 13) + size))
                    mask = Image.new('L', crop.size)
                    rgb = crop.tobytes()
                    mask.putdata([255 if min(rgb[i:i + 3]) > 150 else 0 for i in range(0, len(rgb), 3)])
                    box = mask.getbbox()
                    minimum = {13: 8, 16: 10, 20: 12, 24: 15}[size]
                    need(box is not None and minimum <= box[3] - box[1] <= minimum + 3, 'actual heading glyph height ' + label)
                    pixels[(arm, size)] = mask.tobytes()
                except (OSError, ValueError) as e: errors.append(arm + ': font image ' + str(e))
        if not fallback:
            for index, (request, size) in enumerate(NORMAL):
                route(f'font_norm{index}', size)
                actual = get('FONT', f'font_norm{index}', 'request')
                raw = re.findall(r'P603 FONTREQUEST font_norm' + str(index) + r' text=([^\r\n]+)', text)
                #FTE's cvar numeric parser reads nan/inf spellings as +/-0, not
                #IEEE NaN/Inf. Prove the raw request acted and its numeric result.
                expected = 0 if isinstance(request, str) else request
                need(actual == expected and raw == [str(request)], 'normalization subject did not act ' + str(request))
            route('font_bakes_begin', 13); route('font_bakes_end', 13)
            if arm.startswith('native'):
                for index in range(5, len(NORMAL)):
                    need(get('STATE', f'font_norm{index}', 'revision') == get('STATE', 'font_norm4', 'revision'),
                         'equivalent default requests republished model authority')
                need(get('STATE', 'font_bakes_begin', 'h') == get('STATE', 'font_bakes_end', 'h') and
                     get('STATE', 'font_bakes_end', 'revision') > get('STATE', 'font_bakes_begin', 'revision'),
                     'size changes did not retain context and advance authority')
                need(get('ACTIVE', 'font_stale', 'watch') == 0 and get('STATE', 'font_stale', 'painted') == 1 and
                     get('STATE', 'font_stale', 'revision') > get('STATE', 'font_bakes_end', 'revision'), 'held size-change click activated/inert subject')
                need(get('ACTIVE', 'font_recovery_watch', 'watch') == 1 and get('ACTIVE', 'font_recovery_watch', 'samples') == 20,
                     'fresh new-size watch did not act')
        else:
            for label in ('font_old_cover', 'font_old_quiet'):
                route(label, 20, True)
                need(get('STATE', label, 'failed') == 1 and get('STATE', label, 'h') == 0, 'old-provider cover did not release/latch')
            need(get('ACTIVE', 'font_old_watch', 'watch') == 1 and get('ACTIVE', 'font_old_watch', 'samples') == 20,
                 'old-provider usable fallback watch did not act')
            route('font_old_recovered', 13)
        if arm != 'absent':
            labels = ('font_old_cover', 'font_old_quiet') if fallback else ('font_bakes_begin', 'font_bakes_end')
            stats = []
            for label in labels:
                start = text.find('P603 FONT ' + label + ' ')
                end = text.find('P603 FONT ', start + 1)
                section = text[start:end if end >= 0 else len(text)] if start >= 0 else ''
                matches = re.findall(r'UIIMGUI STATUS ([^\r\n]+)', section)
                stats.append({k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', matches[0])} if len(matches) == 1 else {})
            fields = ('opens', 'closes', 'uploads')
            need(all(k in s for s in stats for k in fields) and all(stats[0][k] == stats[1][k] for k in fields),
                 'recreated/reuploaded atlas or retried failed owner')
            if fallback:
                need(stats[0].get('live') == stats[1].get('live') == 0 and stats[0] == stats[1], 'old-provider closed work/resources')
    if 'native1' in report.get('arms', {}) and 'native2' in report.get('arms', {}):
        for size in SIZES:
            if fallback and size != 13: continue
            if not pixels.get(('native1', size)) or pixels.get(('native1', size)) != pixels.get(('native2', size)):
                errors.append('font: physical heading ink differs between virtual scales at ' + str(size))
    return errors


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('rig', type=Path)
    a = p.parse_args()
    from p603scores import grade
    errors = grade(a.rig)
    for e in errors: print('FAIL', e)
    print('Font gate failures:', len(errors))
    raise SystemExit(bool(errors))
