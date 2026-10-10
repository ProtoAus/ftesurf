#!/usr/bin/env python3
"""Actual-scoreboard lifecycle routes; failure seams are explicitly test-only."""
import re


def extend_config(cfg, arm):
    lines = []
    native = arm.startswith('native')

    def reset():
        lines.extend(['set p603life_fail 0', 'set rec_terms 0', 'set lobby_dir ""',
                      'replay off', '-showscores', 'scores filter all',
                      'scores tab local', '+showscores', 'scores open', 'waitms 700'])

    def probe(name, shot=False):
        lines.extend(['p603 probe life_' + name, 'p603life probe ' + name])
        if shot: lines.append('screenshot life_' + name)

    def hold():
        lines.extend(['p603 move watch', 'waitms 200'])
        #Only native has revision-bound held-input cancellation. Legacy/absent
        #are usable route controls, not subjects for a new SUI input contract.
        if native: lines.extend(['p603 down', 'waitms 200'])

    def release():
        if native: lines.append('p603 up')
        lines.append('waitms 500')

    reset(); probe('control', True)
    hold(); lines += ['p603 focus 0 -1', 'waitms 500']; release(); probe('mouse_lost')
    lines += ['p603 focus 1 -1', 'waitms 700']; probe('mouse_back')
    reset(); hold(); lines += ['p603life key 27 1', 'p603life key 27 0']; release(); probe('escape')
    reset(); hold(); lines += ['chat_say LifecycleFixture', 'waitms 500']; release(); probe('chat')
    lines += ['p603life key 27 1', 'p603life key 27 0', 'waitms 700']; probe('chat_back')
    #Editor refuses a pinned board and steps aside if one opens. The supported
    #coexistence is a held read-only board underneath it, followed by repinning.
    reset(); hold(); lines += ['scores close', 'hud_edit on', '+showscores', 'waitms 500']
    release(); probe('editor', True)
    lines += ['hud_edit off', 'scores open', 'waitms 700']; probe('editor_back')
    reset(); hold(); lines += ['togglemenu', 'waitms 700']; release(); probe('menu')
    lines += ['ui_close', 'waitms 700']; probe('menu_back')
    reset(); hold(); lines += ['scores filter clean', 'waitms 500']; release(); probe('filter')
    reset(); hold(); lines += ['scores tab online', 'waitms 700']; release(); probe('source')
    reset(); hold(); lines += ['p603life room', 'waitms 200']; release(); probe('room', True)
    #An actual SUI filter click must still act outside the native table.
    lines += ['p603life target sb_fc', 'waitms 200', 'p603 down', 'waitms 200', 'p603 up', 'waitms 700']
    probe('shell')
    if native:
        #Patch 607: the room list docks over the board only on a canvas too narrow for
        #the board's smallest form (about 600 wide), so this narrows the canvas. It
        #used to raise hud_scale, which the board now answers by shrinking its type.
        wide = (960, 540) if arm == 'native2' else (1920, 1080)
        reset(); hold(); lines += ['vid_conwidth 560', 'vid_conheight 315', 'waitms 900', 'scores status',
                                   'p603life room', 'waitms 200']
        release(); lines += ['p603life dock']; probe('dock', True)
        lines += [f'vid_conwidth {wide[0]}', f'vid_conheight {wide[1]}', 'waitms 900']
        reset()
        for mode, name in ((1, 'first'), (2, 'equivalent'), (3, 'changed')):
            lines += [f'p603life cache_set {mode}', 'waitms 400', f'p603life cache_probe {name}']
        lines += ['p603life cache_restore', 'waitms 400']
        reset(); hold(); lines += ['plug_close ui_imgui', 'waitms 700']; release(); probe('plugin_off', True)
        lines += ['plug_load ui_imgui', 'waitms 700']; probe('plugin_back')
        reset(); hold(); lines += ['vid_restart', 'waitms 1700']; release(); probe('restart', True)
        reset(); probe('restart_back')
        reset(); hold(); lines += ['set ui_native_scores 0', 'waitms 500']; release()
        probe('disabled', True)
        lines += ['echo P603 DISABLED BEGIN', 'ui_imgui_status', 'waitms 700', 'ui_imgui_status',
                  'echo P603 DISABLED END', 'set ui_native_scores 1', 'waitms 700']
        probe('enabled')
        #Disconnect executes the real CSQC shutdown/engine VM-owner cleanup.
        port = re.search(r'connect 127\.0\.0\.1:(\d+)', cfg)[1]
        reset(); hold(); lines += ['echo P603 VM BEGIN', 'disconnect', 'waitms 1000',
                                  'ui_imgui_status', 'echo P603 VM END',
                                  'ui_close', f'connect 127.0.0.1:{port}', 'waitms 6500', 'ui_close']
        reset(); release(); probe('vm_back', True)
        #Exact failure responses exercise production same-frame cover/latch.
        for mode, name in ((1, 'draw'), (2, 'model')):
            lines += ['-showscores', f'set p603life_fail {mode}', '+showscores', 'scores open', 'waitms 700']
            probe(name + '_fail', True)
            lines += ['set p603life_fail 0', 'waitms 700']; probe(name + '_latched')
            lines += ['p603 move watch', 'waitms 200', 'p603 down', 'waitms 200', 'p603 up', 'waitms 700']
            probe(name + '_fallback'); lines += ['replay status']
            reset(); probe(name + '_retry')
    lines += ['-showscores', 'replay off', 'waitms 500']; probe('closed1')
    if arm != 'absent': lines += ['ui_imgui_status']
    lines += ['waitms 500']; probe('closed2')
    if arm != 'absent': lines += ['ui_imgui_status']
    lines += ['echo P603 LIFE FINISHED', 'echo P603 FINISHED', 'quit']
    return cfg.replace('echo P603 FINISHED\nquit\n', '\n'.join(lines) + '\n')


def grade_life(rig, report):
    errors = []
    base = ('control', 'mouse_lost', 'mouse_back', 'escape', 'chat', 'chat_back', 'editor',
            'editor_back', 'menu', 'menu_back', 'filter', 'source', 'room', 'shell', 'closed1', 'closed2')
    extra = ('plugin_off', 'plugin_back', 'restart', 'restart_back', 'disabled', 'enabled', 'vm_back', 'dock') + tuple(
        kind + '_' + phase for kind in ('draw', 'model') for phase in ('fail', 'latched', 'fallback', 'retry'))
    for arm in report['arms']:
        native = arm.startswith('native')
        logs = list((rig / arm / 'ftesurf/logs').glob('scores*.log'))
        if len(logs) != 1:
            errors.append(arm + ': lifecycle unique log required'); continue
        text = logs[0].read_text(errors='replace')
        def need(ok, why):
            if not ok: errors.append(arm + ': lifecycle ' + why)
        need(text.count('P603 LIFE FINISHED') == 1, 'completion missing/duplicated')
        need('P603 LIFEUNKNOWN' not in text, 'unknown fixture command')
        captures = {}
        for kind, name, body in re.findall(r'P603 (STATE|OWNER|ACTIVE|LIFE|LIFEFALL) (\w+) ([^\r\n]+)', text):
            if kind in ('STATE', 'OWNER', 'ACTIVE'):
                if not name.startswith('life_'): continue
                name = name[5:]
            key = kind, name
            need(key not in captures, 'duplicate ' + kind + '/' + name)
            pairs = re.findall(r'(\w+)=(-?[0-9]+(?:\.[0-9]+)?)', body)
            need(len(pairs) == len({k for k, v in pairs}), 'duplicate field ' + kind + '/' + name)
            captures[key] = {k: float(v) for k, v in pairs}
        fields = {'STATE': {'h', 'painted', 'failed', 'revision', 'page', 'rows'},
                  'OWNER': {'held', 'pin', 'cursor', 'focus', 'down', 'taken'},
                  'ACTIVE': {'watch', 'samples', 'lines'},
                  'LIFE': {'chat', 'editor', 'mouse', 'keyboard', 'tab', 'filter'},
                  'LIFEFALL': {'draw', 'model'}}
        names = base + (extra if native else ())
        missing = False
        for name in names:
            for kind, expected in fields.items():
                ok = set(captures.get((kind, name), {})) == expected
                need(ok, 'missing/malformed ' + kind + '/' + name)
                missing |= not ok
        if missing: continue
        def get(kind, name, field): return captures[kind, name][field]
        for name in names:
            if not name.endswith('_fallback'):
                need(get('ACTIVE', name, 'watch') == 0, 'stale/unrequested watch ' + name)
            need(get('OWNER', name, 'down') == 0 and get('OWNER', name, 'taken') == 0,
                 'stuck button pair ' + name)
        for name in ('control', 'mouse_back', 'chat_back', 'editor_back', 'menu_back', 'room', 'shell'):
            need(get('OWNER', name, 'pin') == 1 and get('OWNER', name, 'cursor') != 0,
                 'usable pinned control ' + name)
            need((get('STATE', name, 'h') > 0) == native and get('STATE', name, 'painted') == int(native),
                 'restored native/fallback route ' + name)
        need(get('LIFE', 'mouse_lost', 'mouse') == 0 and get('LIFE', 'mouse_lost', 'keyboard') == 1,
             'independent mouse focus subject did not act')
        need(get('LIFE', 'chat', 'chat') == 1 and get('LIFE', 'chat_back', 'chat') == 0,
             'chat interruption did not act')
        need(get('LIFE', 'editor', 'editor') == 1 and get('LIFE', 'editor_back', 'editor') == 0,
             'higher editor interruption did not act')
        need(get('OWNER', 'menu', 'focus') == 0 and get('OWNER', 'menu_back', 'focus') == 1,
             'engine menu precedence did not act')
        for name in ('mouse_lost', 'chat', 'editor', 'menu', 'source', 'escape'):
            need(get('STATE', name, 'h') == 0, 'suspended/closed owner retained ' + name)
        need(get('LIFE', 'filter', 'filter') != get('LIFE', 'control', 'filter'), 'filter change inert')
        need(get('LIFE', 'source', 'tab') != get('LIFE', 'control', 'tab'), 'source change inert')
        need(get('LIFE', 'shell', 'filter') != get('LIFE', 'control', 'filter') and
             text.count('P603 LIFETARGET id=sb_fc found=1') == 1, 'actual SUI filter click inert')
        rects = re.findall(r'P603 LIFEROOM width=([0-9.]+) height=([0-9.]+)', text)
        need(len(rects) == (2 if native else 1) and all(float(v) > 0 for rect in rects for v in rect),
             'room rectangle absent/inert')
        for name in ('escape', 'closed1', 'closed2'):
            need(all(get('OWNER', name, key) == 0 for key in ('held', 'pin', 'cursor')) and
                 get('STATE', name, 'h') == 0, 'close ownership ' + name)
        if native:
            docks = re.findall(r'P603 DOCK clipped=([\d.]+) gap=([\d.]+) hover=([\d.]+)', text)
            need(len(docks) == 1 and tuple(map(float, docks[0])) == (1,1,0) and
                 get('STATE', 'dock', 'painted') == 1 and get('OWNER', 'dock', 'pin') == 1 and
                 get('ACTIVE', 'dock', 'watch') == 0, 'docked room overlaps native viewport/hit/action')
            cache = {}
            for name, body in re.findall(r'P603 CACHE (\w+) ([^\r\n]+)', text):
                need(name not in cache, 'duplicate cache probe ' + name)
                cache[name] = {k: float(v) for k,v in re.findall(r'(\w+)=(-?[\d.]+)', body)}
            need(set(cache) == {'first', 'equivalent', 'changed'} and
                 all(c.get('ok') == 1 and c.get('raw') == 1 for c in cache.values()),
                 'plain-label cache lost live metadata/control stripping')
            if set(cache) == {'first', 'equivalent', 'changed'}:
                need(cache['first'].get('revision', -1) == cache['equivalent'].get('revision', -2) and
                     cache['changed'].get('revision', -1) > cache['equivalent'].get('revision', -1),
                     'pure-equivalent metadata republished or changed metadata not republished')
            need(get('STATE', 'filter', 'revision') > get('STATE', 'control', 'revision'),
                 'held filter authority unchanged')
            need(get('STATE', 'plugin_off', 'h') == 0, 'unloaded plugin retained owner')
            need(get('STATE', 'disabled', 'h') == 0 and get('STATE', 'disabled', 'painted') == 0 and
                 get('OWNER', 'disabled', 'pin') == 1, 'preference disable did not cover/release native')
            disabled = re.findall(r'P603 DISABLED BEGIN(.*?)P603 DISABLED END', text, re.S)
            vm = re.findall(r'P603 VM BEGIN(.*?)P603 VM END', text, re.S)
            need(len(disabled) == 1 and len(vm) == 1, 'disable/VM interval missing/duplicated')
            if len(disabled) == 1:
                stats = re.findall(r'UIIMGUI STATUS ([^\r\n]+)', disabled[0])
                need(len(stats) == 2 and stats[0] == stats[1] and 'live=0' in stats[0],
                     'disabled steady state adds native work/resources')
            if len(vm) == 1:
                stats = re.findall(r'UIIMGUI STATUS ([^\r\n]+)', vm[0])
                need(len(stats) == 1 and 'live=0' in stats[0] and
                     len(re.findall(r'FTESurf CSQC loaded', text)) == 2, 'real VM teardown/reload did not act')
            for name in ('plugin_back', 'restart_back', 'enabled', 'vm_back', 'draw_retry', 'model_retry'):
                need(get('STATE', name, 'h') > 0 and get('STATE', name, 'painted') == 1,
                     'fresh gesture did not recover ' + name)
            for kind, expected in (('draw', (1, 0)), ('model', (1, 1))):
                for phase in ('fail', 'latched'):
                    name = kind + '_' + phase
                    need(get('STATE', name, 'h') == 0 and get('STATE', name, 'failed') == 1 and
                         get('STATE', name, 'painted') == 0, 'failure did not cover/latch ' + name)
                    need(tuple(get('LIFEFALL', name, k) for k in ('draw', 'model')) == expected,
                         'failure response inert or retry spam ' + name)
                name = kind + '_fallback'
                need(get('ACTIVE', name, 'watch') == 1 and get('ACTIVE', name, 'samples') == 20,
                     'legacy failure cover cannot watch ' + kind)
        for name in ('control', 'editor', 'room') + (('plugin_off', 'restart', 'disabled', 'vm_back', 'draw_fail', 'model_fail') if native else ()):
            need(len(list((rig / arm / 'ftesurf/screenshots').glob('life_' + name + '.*'))) == 1,
                 'missing/duplicate screenshot ' + name)
    return errors
