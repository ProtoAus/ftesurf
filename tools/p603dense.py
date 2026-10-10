"""Bounded /2 density gate; synthetic input, real QC data/model/actions/rendering."""
import math
from pathlib import Path
import re


def config_dense(base, arm):
    marker = 'set ui_native_scores_font 13\nscores tab local\n+showscores\n'
    if base.count(marker) != 1:
        raise ValueError('unique scoreboard startup required')
    prefix = base.split(marker)[0] + 'set ui_native_scores_font 13\n'
    active = arm in ('native1', 'native2', 'oldplugin', 'oldengine')
    dense = arm.startswith('native')
    def probe(label):
        return [f'p603dense probe {label}', f'p603 probe {label}']
    def click(target, row='0'):
        return [f'p603dense move {target} {row}', 'waitms 200', 'p603 down', 'waitms 200',
                'p603 up', 'waitms 500']
    reset = ['-showscores', 'replay off', 'p603dense forget', 'waitms 200',
             'scores tab local', '+showscores', 'waitms 500', 'p603 pin', 'p603 unpin', 'waitms 700']
    lines = ['scores tab local', '+showscores', 'waitms 1000', *probe('dense_peek'), *click('watch')]
    if active:
        lines += [*probe('dense_passive'), 'p603 pin', 'p603 unpin', 'waitms 800']
    else:
        #Existing legacy peek is clickable; verify that acting cover separately,
        #then close its watch before pinning. No legacy-inertness acceptance.
        lines += probe('dense_legacy_peekwatch') + reset
    lines += [*probe('dense_page0'), 'screenshot dense_page0']
    if active:
        lines += click('line')
    else:
        lines += ['scores line 0', 'waitms 1000']
    lines += probe('dense_line')
    lines += click('line') if active else ['scores line 0', 'waitms 400']
    lines += probe('dense_lineoff') + click('watch') + probe('dense_watch0') + reset
    if dense:
        lines += click('watch', '8') + probe('dense_watch8') + reset
    if active:
        lines += click('next') + probe('dense_next') + ['screenshot dense_next']
        lines += click('watch') + probe('dense_pagewatch') + reset
        lines += click('next') + click('previous') + probe('dense_previous')
        lines += ['p603dense finish 31', 'waitms 1000', *probe('dense_follow'), 'screenshot dense_follow']
        lines += reset + ['p603dense move watch 0', 'waitms 200', 'p603 down', 'waitms 200',
                          'p603 rescan', 'waitms 700', 'p603 up', 'waitms 400', *probe('dense_stale')]
        lines += click('watch') + probe('dense_recovery') + reset
    if dense:
        #Motion made while the table is not painting, then a click with no motion:
        #it must land where the cursor is (row 0), not where the table last saw it (row 8).
        lines += ['p603dense move watch 8', 'waitms 200', 'set ui_native_scores 0', 'waitms 400',
                  'p603dense cursor watch 0', 'waitms 200', 'set ui_native_scores 1', 'waitms 600',
                  'p603 rawdown', 'waitms 200', 'p603 rawup', 'waitms 500', *probe('dense_cursor')] + reset
    if active:
        lines += probe('dense_quiet_begin') + ['ui_imgui_status', 'waitms 1000'] + probe('dense_quiet_end') + ['ui_imgui_status']
    if dense:
        for font in (13, 16, 20, 24):
            lines += [f'set ui_native_scores_font {font}', *reset, *probe(f'dense_font{font}'),
                      f'screenshot dense_font{font}', *click('watch'), *probe(f'dense_font{font}_watch')]
        lines += ['set ui_native_scores_font 16', *reset, 'p603dense move watch 0', 'waitms 200']
        for _ in range(30):
            lines += ['p603dense wheel -1', 'waitms 50']
        lines += probe('dense_tail') + ['screenshot dense_tail', *click('watch', 'tail'), *probe('dense_tailwatch')]
        lines += ['set ui_native_scores_font 13', *reset, 'p603dense move watch 0', 'waitms 200',
                  'p603 down', 'waitms 200', 'set ui_native_scores_font 20', 'waitms 600',
                  'p603 up', 'waitms 400', *probe('dense_fontstale'), *click('watch'), *probe('dense_fontrecovery')]
    lines += ['-showscores', 'replay off', 'waitms 500', *probe('dense_closed1')]
    if arm != 'absent': lines += ['ui_imgui_status']
    lines += ['waitms 800', *probe('dense_closed2')]
    if arm != 'absent': lines += ['ui_imgui_status']
    lines += ['echo P603 FINISHED', 'quit']
    return prefix + '\n'.join(lines) + '\n'


SCHEMAS = {
    'DENSE': {'limit', 'pagesize', 'page', 'rows', 'count', 'selected'},
    'DENSERANK': {'first', 'last'},
    'STATE': {'h', 'painted', 'failed', 'revision', 'page', 'rows'},
    'ACTIVE': {'watch', 'samples', 'lines'},
    'OWNER': {'held', 'pin', 'cursor', 'focus', 'down', 'taken'},
    'LINE': {'ready', 'samples'},
}


def captures(text):
    result = {}
    for kind, label, body in re.findall(r'P603 (DENSE|DENSERANK|STATE|ACTIVE|OWNER|LINE) (dense_\w+) ([^\r\n]+)', text):
        key = kind, label
        if key in result: raise ValueError('duplicate ' + '/'.join(key))
        pairs = re.findall(r'(\w+)=([^\s]+)', body)
        if len(pairs) != len(SCHEMAS[kind]) or {k for k, _ in pairs} != SCHEMAS[kind]:
            raise ValueError('incomplete/unknown fields ' + '/'.join(key))
        fields = {k: float(v) for k, v in pairs}
        if not all(math.isfinite(v) and v == int(v) for v in fields.values()):
            raise ValueError('non-finite/non-integral result ' + '/'.join(key))
        result[key] = fields
    return result


def grade_dense(rig: Path, report):
    errors = []
    arms = report.get('arms', {})
    if report.get('dense') is not True or report.get('dense_http') is not True:
        errors.append('density/local-and-online plan required')
    if not arms or set(report.get('planned_arms', ())) != set(arms): errors.append('planned/acting arm set differs')
    pixels = {}
    digest = lambda value: isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None
    if not digest(report.get('csprogs_sha256')) or not digest(report.get('plugin_sha256')):
        errors.append('density candidate hashes required')
    for arm, result in arms.items():
        def need(ok, why):
            if not ok: errors.append(arm + ': dense ' + why)
        need(arm in ('native1', 'native2', 'oldplugin', 'oldengine', 'legacy', 'absent'), 'unknown arm')
        need(type(result.get('returncode')) is int and result['returncode'] == 0, 'client exit')
        need(all(digest(result.get(key)) for key in ('engine_sha256','server_sha256','qwprogs_sha256','csprogs_sha256','menu_sha256')),
             'runtime input provenance required')
        need(result.get('csprogs_sha256') == report.get('csprogs_sha256'), 'wrong compiled fixture')
        need(type(result.get('port')) is int and 27520 <= result['port'] <= 27620, 'designated real dedicated socket required')
        if arm == 'absent': need(result.get('plugin_sha256') is None, 'absent provider present')
        elif arm == 'oldplugin':
            need(digest(result.get('plugin_sha256')) and result['plugin_sha256'] != report.get('plugin_sha256'), 'previous-provider control not distinct')
        else: need(result.get('plugin_sha256') == report.get('plugin_sha256'), 'wrong provider candidate')
        active = arm in ('native1', 'native2', 'oldplugin', 'oldengine')
        dense = arm.startswith('native')
        cap = 256 if dense or arm == 'legacy' else 64 if active else 0
        page = 24 if dense else 6
        logs = list((rig/arm/'ftesurf/logs').glob('scores*.log'))
        if len(logs) != 1: errors.append(arm + ': dense unique log required'); continue
        text = logs[0].read_text(errors='replace')
        backend = {'gl':'OpenGL','d3d9':'Direct3D9','d3d11':'Direct3D11','vk':'Vulkan'}.get(report.get('renderer'))
        need(backend is not None and backend+' renderer initialized' in text, 'requested renderer did not positively initialize')
        need(text.count('P603 FINISHED') == 1, 'unique completion marker')
        need(not re.search(r'Unknown command|QC runtime error|CSQC_Abort|Menu_Abort|DENSE UNKNOWN|VK_ERROR|Device lost', text, re.I), 'runtime/command error')
        try: values = captures(text)
        except ValueError as e: errors.append(arm + ': dense ' + str(e)); continue
        def get(kind, label, field):
            return values.get((kind, label), {}).get(field, -999)
        def route(label, expected_page=0, font=13):
            need(get('STATE', label, 'painted') == int(active), 'route did not act ' + label)
            need(get('DENSE', label, 'limit') == cap, 'wrong negotiated ABI capacity ' + label)
            if active:
                rows = min(page, 32-expected_page)
                need(get('STATE', label, 'h') > 0 and get('STATE', label, 'failed') == 0, 'owner failed ' + label)
                need(get('DENSE', label, 'pagesize') == page and get('DENSE', label, 'page') == expected_page and
                     get('STATE', label, 'page') == expected_page, 'wrong bounded page ' + label)
                need(get('DENSE', label, 'rows') == rows and get('DENSE', label, 'count') == (5 if font == 13 else 6)+rows*9,
                     'incomplete/unbounded counted snapshot ' + label)
                need(get('DENSERANK', label, 'first') == expected_page+1 and
                     get('DENSERANK', label, 'last') == expected_page+rows, 'wrong row range ' + label)
        def watch(label, row):
            need(get('ACTIVE', label, 'watch') == 1 and get('ACTIVE', label, 'samples') == 20, 'watch did not ACT ' + label)
            paths = re.findall(r'P603 DENSEPATH ' + re.escape(label) + r' ([^\r\n]+)', text)
            need(paths == [f'data/runs/p603scores.map/main/{100+row:07d}_p603{row}_pb.rec'], 'wrong watch identity ' + label)
        route('dense_page0')
        need(get('STATE', 'dense_peek', 'rows') == 32, 'full source dataset did not act')
        if active:
            need(get('ACTIVE', 'dense_passive', 'watch') == 0 and
                 get('OWNER', 'dense_passive', 'pin') == 0, 'passive native click acted')
        else:
            watch('dense_legacy_peekwatch', 0)
        need(get('OWNER', 'dense_page0', 'pin') == 1, 'pin did not act')
        need(get('LINE', 'dense_line', 'ready') == 1 and get('LINE', 'dense_line', 'samples') == 20 and
             get('ACTIVE', 'dense_line', 'lines') == 1 and get('ACTIVE', 'dense_lineoff', 'lines') == 0, 'actual line on/off did not ACT')
        watch('dense_watch0', 0)
        if active:
            route('dense_next', page); watch('dense_pagewatch', page); route('dense_previous')
            follow_page = (31//page)*page
            route('dense_follow', follow_page)
            need(get('DENSE', 'dense_follow', 'selected') == 31, 'finish follow/highlight wrong current identity')
            route('dense_stale')
            need(get('ACTIVE', 'dense_stale', 'watch') == 0, 'held rescan click retargeted')
            watch('dense_recovery', 0)
            route('dense_quiet_begin'); route('dense_quiet_end')
            need(get('STATE', 'dense_quiet_begin', 'revision') == get('STATE', 'dense_quiet_end', 'revision') and
                 get('STATE', 'dense_quiet_begin', 'h') == get('STATE', 'dense_quiet_end', 'h'), 'unchanged page republished/reopened')
        if dense:
            watch('dense_watch8', 8)
            watch('dense_cursor', 0)
            for font in (13, 16, 20, 24):
                route(f'dense_font{font}', font=font); watch(f'dense_font{font}_watch', 0)
            route('dense_tail', font=16); watch('dense_tailwatch', 23)
            route('dense_fontstale', font=20)
            need(get('ACTIVE', 'dense_fontstale', 'watch') == 0, 'held font click retargeted')
            watch('dense_fontrecovery', 0)
        if active:
            from p603dense_http import grade
            errors.extend(grade(rig, arm, text, values))
        for label in ('dense_closed1', 'dense_closed2'):
            need(get('STATE', label, 'painted') == 0 and get('STATE', label, 'h') == 0 and
                 get('ACTIVE', label, 'watch') == 0, 'close did not release ' + label)
        if arm != 'absent':
            def status(label):
                start = text.find('P603 DENSE '+label+' ')
                end = text.find('P603 DENSE ', start+1)
                matches = re.findall(r'UIIMGUI STATUS ([^\r\n]+)', text[start:end if end >= 0 else len(text)]) if start >= 0 else []
                return {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', matches[0])} if len(matches) == 1 else {}
            first, last = status('dense_closed1'), status('dense_closed2')
            need(first and first == last and last.get('live') == 0 and last.get('opens') == last.get('closes'), 'closed work/leaked resources')
            if active:
                first, last = status('dense_quiet_begin'), status('dense_quiet_end')
                need(first and last and all(first.get(k) == last.get(k) for k in ('opens', 'closes', 'uploads')) and
                     last.get('frames', 0) > first.get('frames', 0), 'steady draws did not ACT/recreated atlas')
        shots = ['dense_page0'] + (['dense_next', 'dense_follow'] if active else [])
        if dense: shots += ['dense_font13', 'dense_font16', 'dense_font20', 'dense_font24', 'dense_tail']
        for shot in shots:
            images = list((rig/arm/'ftesurf/screenshots').glob(shot+'.*'))
            need(len(images) == 1, 'missing/duplicate screenshot '+shot)
            if dense and shot == 'dense_page0' and len(images) == 1:
                try:
                    from PIL import Image
                    rect = re.findall(r'P603 RECT '+shot+r' ([0-9.e+\-]+) ([0-9.e+\-]+) ([0-9.e+\-]+) ([0-9.e+\-]+)', text)
                    if len(rect) != 1: raise ValueError('unique physical rect required')
                    ratio = 2 if arm == 'native2' else 1
                    x, y, w, h = [round(float(v)*ratio) for v in rect[0]]
                    with Image.open(images[0]) as source: image = source.convert('RGB')
                    if image.size != (1920,1080): raise ValueError('wrong image dimensions')
                    crop = image.crop((x+8,y+42,x+40,y+h-45))
                    white = [any(min(crop.getpixel((px,py))) > 150 for px in range(crop.width)) for py in range(crop.height)]
                    groups = sum(v and (i == 0 or not white[i-1]) for i,v in enumerate(white))
                    need(groups >= 8, 'actual rank ink did not exceed six rows')
                    #The legacy shell has different physical height/width at
                    #the two virtual scales. Compare font ink in a fixed common
                    #420px region, not variable crop extents or hover/background.
                    need(crop.height >= 420, 'common rank-ink viewport too small')
                    pixels[arm] = bytes(min(crop.getpixel((px,py))) > 150
                                       for py in range(min(420,crop.height)) for px in range(crop.width))
                except (OSError,ValueError) as e: errors.append(arm+': dense image '+str(e))
    if 'native1' in arms and 'native2' in arms:
        if not pixels.get('native1') or pixels.get('native1') != pixels.get('native2'):
            errors.append('dense: physical rank ink differs between virtual scales')
    return errors
