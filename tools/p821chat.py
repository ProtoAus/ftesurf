#!/usr/bin/env python3
"""Patches 821 and 824: an open chat is a panel -- history, a field, a selection, the mouse;
its width, height and full-height switch, a field that wraps, and hud_edit's Chat pane.

One windowed client hosting a listen server on a generated map, in an owned
basedir under --out (beneath an OWNER.md).  Keys go through the whole input
chain with `vote key`, the cursor with `chat_mouse`; the grades are what
`chat_rows` prints (the panel's fade, the cursor claims, the field, both
selections, the last copy) and `hud_chat_size` after a config saved at 24.
Screenshots of the panel shut, open, with history and with field selected.
Run it under the rig lock.  It writes the Windows clipboard (the copies are real).

  python tools/p821chat.py --out <fresh dir> --progs <dir holding the three .dat>
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from test_ui_modern import make_map  # noqa: E402

K_ENTER, K_ESCAPE, K_BACKSPACE = 13, 27, 127
K_UP, K_DOWN, K_LEFT = 128, 129, 130
K_LCTRL, K_LSHIFT, K_HOME, K_END = 133, 134, 151, 152
K_MOUSE1, K_MOUSE2, K_WHEELUP = 512, 513, 515
LONG = ('alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike '
        'november oscar papa quebec romeo sierra tango uniform victor whiskey')
WRAP = ('the quick brown fox jumps over the lazy dog and then keeps on running down '
        'the long road until the night falls')
NUM = r'(-?[\d.]+)'
VEC = r"'?" + NUM + ' ' + NUM + ' ' + NUM + r"'?"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Client:
    def __init__(self, exe, base, cfg):
        self.log = base / 'ftesurf/logs/probe.log'
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4              # shown, not activated: the owner keeps the focus
        self.proc = subprocess.Popen(
            [str(exe), '-plugin', '-nohome', '-noreset', '-nobrowse',
             '-basedir', str(base), '-manifest', str(base / 'default.fmf'),
             '-window', '-width', '1280', '-height', '720', '-nosound',
             '+set', 'cfg_save_auto', '0', '+exec', cfg],
            cwd='C:/FTESurf', stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)
        (base / 'owned-pid.txt').write_text(str(self.proc.pid) + '\n')

    def text(self):
        return self.log.read_text(encoding='utf-8', errors='replace') if self.log.exists() else ''

    def send(self, *lines):
        for line in lines:
            self.proc.stdin.write(line.encode('utf-8') + b'\n')
        self.proc.stdin.flush()

    def wait(self, pattern, offset=0, timeout=25):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            found = re.search(pattern, self.text()[offset:])
            if found:
                return found
            if self.proc.poll() is not None:
                raise RuntimeError(f'client exited {self.proc.returncode}: {self.log}')
            time.sleep(.1)
        raise RuntimeError(f'not reached: {pattern}: {self.log}')

    def query(self, pattern, *lines, timeout=25):
        offset = len(self.text())
        self.send(*lines)
        return self.wait(pattern, offset, timeout)

    def stop(self):
        if self.proc.poll() is None:
            self.send('quit')
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=10)


def prepare(a):
    base = a.out / 'client'
    game = base / 'ftesurf'
    for folder in ('cfg', 'maps', 'logs', 'gfx'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for folder in ('fonts', 'ui'):
        shutil.copytree(a.content / 'ftesurf/gfx' / folder, game / 'gfx' / folder)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    (game / 'maps/p821.map').write_text(make_map())
    (game / 'data').mkdir()
    (game / 'data/consent.txt').write_text('version 4\n')   # no first-boot terms over the HUD
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfP821Fixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG p821-unused\n')
    (game / 'probe.cfg').write_text('\n'.join([
        'cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name probe',
        'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 100', 'set run_resume 0',
        'set lobby_dir ""', 'set lobby_master ""', 'set cl_run_upload 0', 'set cl_board_url ""',
        'set sv_public 0', 'vid_conautoscale 0', 'vid_conwidth 1280', 'vid_conheight 720',
        'scr_sshot_type png', 'con_notifylines 0', 'set name Tester', f'sv_port {a.port}',
        'set sv_floodprotect 0',        # the filler lines come faster than 4 in 4 s
        'seta hud_chat_size 24',        # a config saved before 821, at the old default
        'seta hud_chat_bg 0.5',         # P824: saved first, so 0.5 is its default -- reset all must not keep it
        'set hud_chat 1', 'set hud_chat_lines 6', 'set hud_chat_time 600',
        'set hud_chat_x 0.05', 'set hud_chat_y 0.95',
        'map p821.map']) + '\n')
    return base


def rows(t):
    """chat_rows' state, from the last dump in t."""
    at = t.rfind('chat_rows: maxw ')
    t = t[at:]
    head = re.search(r'chat_rows: maxw ' + NUM + ' sz ' + NUM + ' lh ' + NUM + ' lines ' + NUM
                     + ' cap ' + NUM, t)
    panel = re.search(r'chat_rows: panel ' + NUM + ' claims ' + NUM + ' x ' + NUM + ' box ' + VEC
                      + ' ' + VEC, t)
    starts = re.search(r'chat_rows: field starts((?: \d+)+) ty ' + NUM, t)
    frows = re.search(r' rows (\d+)\n', t[t.find('chat_rows: field '):])
    fld = re.search(r'chat_rows: field ' + VEC + ' ' + VEC + ' tx ' + NUM + ' caret ' + NUM
                    + ' anchor ' + NUM, t)
    scr = re.search(r'chat_rows: scroll ' + NUM + ' of ' + NUM + ' sent ' + NUM + r' \|(.*)\|', t)
    sel = re.search(r'chat_rows: sel ' + NUM + r' \|(.*)\|', t)
    cop = re.search(r'chat_rows: copied \|(.*)\|', t)
    msgs = []
    for m in re.finditer(r'chat_rows: msg(\d+) n (\d+) drawn (\d+) y0 ' + NUM, t):
        body = re.findall(r'chat_rows: msg' + m.group(1) + r' \d+ w [\d.]+ \|(.*)\|', t)
        msgs.append({'n': int(m.group(2)), 'y0': float(m.group(4)), 'rows': body})
    return {
        'maxw': float(head.group(1)), 'sz': float(head.group(2)), 'lh': float(head.group(3)),
        'cap': int(float(head.group(5))), 'box': [float(panel.group(i)) for i in range(4, 10)],
        'starts': [int(v) for v in starts.group(1).split()], 'ty': float(starts.group(2)),
        'frows': int(frows.group(1)),
        'panel': float(panel.group(1)), 'claims': int(float(panel.group(2))), 'x': float(panel.group(3)),
        'field': [float(fld.group(i)) for i in range(1, 7)], 'tx': float(fld.group(7)),
        'caret': int(float(fld.group(8))), 'anchor': int(float(fld.group(9))),
        'scroll': int(float(scr.group(1))), 'total': int(float(scr.group(2))),
        'sent': int(float(scr.group(3))), 'buf': scr.group(4),
        'sel': sel.group(2).replace('\\n', '\n') if int(float(sel.group(1))) else None,
        'copied': cop.group(1).replace('\\n', '\n'), 'msgs': msgs}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--port', type=int, default=27617)
    ap.add_argument('--content', type=Path, default=Path('C:/FTESurf'))
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    checks = []
    report = {'progs': {p: sha(a.progs / p)[:8] for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client)[:8], 'checks': checks}

    def check(ok, name, got=None):
        checks.append({'name': name, 'pass': bool(ok), 'got': got})
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok or got is None else f'  (got {got!r})'),
              flush=True)

    c = None
    try:
        base = prepare(a)
        c = Client(a.client, base, 'probe.cfg')
        c.wait(r'Server spawned|entered the game|Tester', timeout=60)
        time.sleep(3)
        c.send('menu_restart')
        time.sleep(1)
        c.send('ui_close')
        time.sleep(1)

        def dump():
            c.query(r'chat_rows: copied \|.*\|\n', 'chat_rows')
            time.sleep(.2)
            return rows(c.text())

        def key(scan, char=0, mods=()):
            for m in mods:
                c.send(f'vote key {m} 1')
            c.send(f'vote key {scan} 1 {char}', f'vote key {scan} 0')
            for m in mods:
                c.send(f'vote key {m} 0')

        def mouse(x, y, scan=0, down=0):
            c.send(f'chat_mouse {x:.1f} {y:.1f} {scan} {down}' if scan else f'chat_mouse {x:.1f} {y:.1f}')

        def say(t):
            c.query(re.escape('Tester^7: ' + t) + '\n', f'cmd say "{t}"')   # the log keeps the codes

        size = c.query(r'"hud_chat_size" is "([^"]*)"', 'hud_chat_size').group(1)
        check(size == '20' and 'chat: the chat text is a size smaller now' in c.text(),
              'a config at the old 24 moves to 20 and says so', size)

        say('hello world one')
        say('second line')
        say('^2' + LONG)
        say('^3yellow words ^7and plain')
        time.sleep(.5)
        r = dump()
        check(r['panel'] == 0 and r['claims'] == 0, 'shut: no panel, nobody holds the mouse',
              (r['panel'], r['claims']))
        c.send('screenshot p821_shut')

        c.send('chat_open')
        time.sleep(.6)
        r = dump()
        check(r['panel'] == 1 and r['claims'] == 1024, 'open: the panel faded in and holds the mouse alone',
              (r['panel'], r['claims']))
        check(r['sz'] == 20, 'the chat text is drawn at 20', r['sz'])
        check(abs(r['maxw'] - 0.35 * 1280) < 1, 'P824: the box is 35% of the screen wide', r['maxw'])
        fit_h = r['box'][4]
        c.send('set hud_chat_full 1')
        time.sleep(.4)
        r2 = dump()
        want = (r['cap'] - max(min(3, r['cap']), min(r['total'], r['cap']))) * r['lh']
        check(want > 0 and abs(r2['box'][4] - fit_h - want) < 1.5,
              'P824: full height opens the box its whole height with only a few lines in it',
              (fit_h, r2['box'][4], want))
        c.send('screenshot p824_full')
        time.sleep(.5)
        c.send('set hud_chat_rows 6')
        time.sleep(.4)
        r3 = dump()
        check(abs(r2['box'][4] - r3['box'][4] - 4 * r['lh']) < 1.5,
              'P824: Height 6 makes the full box four rows shorter than 10', (r2['box'][4], r3['box'][4]))
        c.send('set hud_chat_rows 10')
        time.sleep(.3)
        c.send('set hud_chat_full 0')
        time.sleep(.3)
        c.send('screenshot p821_open')

        def find(word):
            for m in r['msgs']:
                if any(word in row for row in m['rows']):
                    return m
            raise RuntimeError('no message holds ' + word)

        lh, x, right = r['lh'], r['x'], r['x'] + r['maxw'] + 4
        one, two, lng, col = find('hello world one'), find('second line'), find('alpha bravo'), find('yellow')
        check(lng['n'] >= 3, 'the long line wraps to three rows or more', lng['n'])

        def drag(p, q):
            mouse(*p, K_MOUSE1, 1)
            mouse(*q)
            mouse(*q, K_MOUSE1, 0)
            time.sleep(.3)
            return dump()

        r = drag((x + 1, one['y0'] + lh / 2), (right, one['y0'] + lh / 2))
        check(r['sel'] == 'Tester: hello world one', 'a drag along a row selects it', r['sel'])
        r = drag((x + 1, lng['y0'] + lh / 2), (right, lng['y0'] + lh * (lng['n'] - 0.5)))
        check(r['sel'] == 'Tester: ' + LONG, 'a drag over a wrapped, coloured line gives its plain text whole',
              r['sel'])
        r = drag((x + 1, col['y0'] + lh / 2), (right, col['y0'] + lh / 2))
        check(r['sel'] == 'Tester: yellow words and plain', 'colour codes are not copied', r['sel'])
        both = 'Tester: hello world one\nTester: second line'
        r = drag((x + 1, one['y0'] + lh / 2), (right, two['y0'] + lh / 2))
        check(r['sel'] == both, 'a drag over two messages gives both, a line each', r['sel'])
        r = drag((right, two['y0'] + lh / 2), (x + 1, one['y0'] + lh / 2))
        check(r['sel'] == both, 'the same drag backwards gives the same text', r['sel'])
        c.send('screenshot p821_history')
        mouse(x + 300, one['y0'] + lh / 2, K_MOUSE2, 1)
        mouse(x + 300, one['y0'] + lh / 2, K_MOUSE2, 0)
        time.sleep(.3)
        r = dump()
        check(r['copied'] == both, 'mouse2 copies the selection', r['copied'])
        p = (x + 1, one['y0'] + lh / 2)
        for _ in range(2):
            mouse(*p, K_MOUSE1, 1)
            mouse(*p, K_MOUSE1, 0)
        time.sleep(.3)
        r = dump()
        check(r['sel'] == 'Tester:', 'a double click takes the word', r['sel'])
        time.sleep(.5)
        for _ in range(3):
            mouse(*p, K_MOUSE1, 1)
            mouse(*p, K_MOUSE1, 0)
        time.sleep(.3)
        r = dump()
        check(r['sel'] == 'Tester: hello world one', 'a triple click takes the line', r['sel'])

        for ch in 'hi there':
            key(ord(ch), ord(ch))
        time.sleep(.3)
        r = dump()
        check(r['buf'] == 'hi there' and r['caret'] == 8, 'typing fills the field', (r['buf'], r['caret']))
        for _ in range(5):
            key(K_LEFT, 0, (K_LSHIFT,))
        key(ord('c'), 3, (K_LCTRL,))
        time.sleep(.3)
        r = dump()
        check(r['anchor'] == 8 and r['caret'] == 3 and r['copied'] == 'there' and r['sel'] is None,
              'shift+left selects in the field, ctrl+c copies it, and the history lets go',
              (r['anchor'], r['caret'], r['copied'], r['sel']))
        key(ord('X'), ord('X'))
        key(K_LEFT, 0, (K_LCTRL,))
        time.sleep(.3)
        r = dump()
        check(r['buf'] == 'hi X' and r['caret'] == 3, 'a key replaces the selection; ctrl+left jumps a word',
              (r['buf'], r['caret']))
        key(K_HOME)
        h = dump()['caret']
        key(K_END)
        e = dump()['caret']
        check((h, e) == (0, 4), 'home and end', (h, e))
        key(ord('a'), 1, (K_LCTRL,))
        key(K_BACKSPACE)
        for ch in 'abc def':
            key(ord(ch), ord(ch))
        key(K_BACKSPACE, 127, (K_LCTRL,))
        time.sleep(.3)
        r = dump()
        check(r['buf'] == 'abc ', 'ctrl+a, backspace, then ctrl+backspace takes the last word', r['buf'])

        fx, fy, fw, fh = r['field'][0], r['field'][1], r['field'][3], r['field'][4]
        mouse(r['tx'] + 1, fy + fh / 2, K_MOUSE1, 1)
        mouse(r['tx'] + 1, fy + fh / 2, K_MOUSE1, 0)
        time.sleep(.3)
        k = dump()['caret']
        r = drag((r['tx'] + 1, fy + fh / 2), (fx + fw - 2, fy + fh / 2))
        check(k == 0 and (r['anchor'], r['caret']) == (0, 4), 'a click places the caret, a drag selects',
              (k, r['anchor'], r['caret']))
        c.send('screenshot p821_field')
        time.sleep(.5)
        key(ord('c'), 3, (K_LCTRL,))
        time.sleep(.3)
        clip = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-Clipboard -Raw'],
                              capture_output=True, text=True).stdout.rstrip('\r\n')
        check(dump()['copied'] == 'abc ' and clip == 'abc ',
              'the field selection is what ctrl+c copies, onto the Windows clipboard', clip == 'abc ')

        # P824: the field wraps and grows a row at a time.
        key(ord('a'), 1, (K_LCTRL,))
        key(K_BACKSPACE)
        one = dump()
        for ch in WRAP:
            key(ord(ch), ord(ch))
        time.sleep(.4)
        r = dump()
        n, grew = r['frows'], r['box'][4] - one['box'][4]
        check(r['buf'] == WRAP and one['frows'] == 1 and n >= 2
              and abs(r['field'][4] - (35 + r['lh'] * (n - 1))) < 1 and abs(grew - r['lh'] * (n - 1)) < 1.5,
              'P824: a long line wraps the field onto more rows and the box grows by them',
              (n, r['field'][4], grew))
        row2 = r['ty'] + r['lh'] * 1.5
        mouse(r['tx'] + 1, row2, K_MOUSE1, 1)
        mouse(r['tx'] + 1, row2, K_MOUSE1, 0)
        time.sleep(.3)
        k = dump()['caret']
        check(len(r['starts']) >= 2 and k == r['starts'][1], 'P824: a click at the second row puts the caret there',
              (k, r['starts']))
        c.send('screenshot p824_wrap')
        time.sleep(.6)
        key(ord('a'), 1, (K_LCTRL,))
        key(K_BACKSPACE)
        for ch in 'abc ':
            key(ord(ch), ord(ch))
        time.sleep(.3)
        check(dump()['frows'] == 1, 'P824: emptied, the field is one row again')

        key(K_ENTER)
        time.sleep(.6)
        r = dump()
        check(r['panel'] == 0 and r['claims'] == 0, 'enter sends, the panel fades out, the mouse goes back',
              (r['panel'], r['claims']))
        c.wait(r'Tester\^7: abc', 0, 10)
        c.send('chat_open')
        key(K_UP)
        time.sleep(.3)
        r = dump()
        u = (r['buf'], r['sent'])
        key(K_DOWN)
        time.sleep(.3)
        r = dump()
        check(u == ('abc ', 0) and (r['buf'], r['sent']) == ('', -1), 'up recalls the sent line, down returns',
              (u, r['buf'], r['sent']))

        for i in range(10):
            say(f'filler number {i}')
        time.sleep(.3)
        key(K_WHEELUP)
        time.sleep(.3)
        s0 = dump()['scroll']
        say('arrives while scrolled')
        time.sleep(.5)
        r = dump()
        check(s0 == 3 and r['scroll'] == 4 and r['total'] > 10,
              'the wheel scrolls; a new line keeps a scrolled view where it was', (s0, r['scroll'], r['total']))
        c.send('screenshot p821_scrolled')
        time.sleep(.5)
        key(K_ESCAPE)
        time.sleep(.6)
        r = dump()
        check(r['panel'] == 0 and r['claims'] == 0, 'escape closes and gives the mouse back',
              (r['panel'], r['claims']))
        c.send('chat_open')
        time.sleep(.3)
        key(ord('`'), ord('`'))
        time.sleep(.6)
        r = dump()
        check(r['panel'] == 0 and r['claims'] == 0, 'the console key closes it too', (r['panel'], r['claims']))

        c.send('config_menu')
        time.sleep(.5)
        held = dump()['claims']
        c.send('chat_open')
        time.sleep(.4)
        r = dump()
        over = (r['panel'] == 1, r['claims'])
        key(K_ESCAPE)
        time.sleep(.6)
        after = dump()['claims']
        key(K_ESCAPE)                   # now the key panel's
        time.sleep(.4)
        check(held == 512 and over == (True, 512) and after == 512 and dump()['claims'] == 0,
              'over a panel holding the mouse chat claims nothing and takes nothing away',
              (held, over, after))

        # The zone editor in look/fly mode is open and holds no claim; it closes on a
        # foreign one, so chat's must not count as one.
        def ze_state():
            return c.query(r'zone_edit: state (\d+)', 'zone_edit status').group(1)
        c.send('zone_edit')
        time.sleep(.5)
        c.send('zone_edit mouse')
        time.sleep(.4)
        z0, h0 = ze_state(), dump()['claims']
        at = len(c.text())
        c.send('chat_open')
        time.sleep(.5)
        h1, z1 = dump()['claims'], ze_state()
        key(K_ESCAPE)
        time.sleep(.5)
        z2 = ze_state()
        check((z0, h0, h1, z1, z2) == ('1', 0, 1024, '1', '1') and 'closed --' not in c.text()[at:],
              'chat over the zone editor looking takes the mouse and leaves the editor open',
              (z0, h0, h1, z1, z2))
        c.send('zone_edit')
        time.sleep(1)
        # P824: hud_edit draws the box open, lists Chat with it, and its pane works.
        c.send('hud_edit on')
        time.sleep(.8)
        r = dump()
        st = c.query(r'  chat +(on|off) +x +([\d.]+) y +([\d.]+)  ([^\n]*)', 'hud_edit status')
        check(r['panel'] == 1 and r['claims'] == 4 and 'drawn' in st.group(4),
              'P824: hud_edit shows the box open, takes only its own claim, and lists Chat as drawn',
              (r['panel'], r['claims'], st.group(0).strip()))
        c.query(r'sui_hover \[he_sel_chat\]', 'hud_edit ui hover he_sel_chat')
        c.send('hud_edit ui down mouse1')
        time.sleep(.3)
        c.send('hud_edit ui up mouse1')
        time.sleep(.6)
        at = len(c.text())
        c.query(r'sui_panel open', 'hud_edit ui')
        time.sleep(.4)
        ids = set(re.findall(r'sui_element \[(he_(?:o|sz)_[^\]]*)\]', c.text()[at:]))
        wantids = {'he_o_hud_chat_' + k for k in ('w', 'rows', 'full', 'lines', 'time', 'bg')}
        check(wantids <= ids and any(i.startswith('he_sz_chat') for i in ids),
              'P824: the Chat pane has width, height, full height, shut lines, time, box and size',
              sorted(i for i in ids if 'chat' in i))
        c.send('screenshot p824_pane')
        time.sleep(.5)
        c.query(r'sui_hover \[he_o_hud_chat_w\]', 'hud_edit ui hover he_o_hud_chat_w')
        c.send('hud_edit ui down mouse1')
        time.sleep(.3)
        c.send('hud_edit ui up mouse1')
        time.sleep(.6)
        w = c.query(r'"hud_chat_w" is "([^"]*)"', 'hud_chat_w').group(1)
        r = dump()
        check(abs(float(w) - 0.4) < 1e-4 and abs(r['maxw'] - 0.4 * 1280) < 1,
              'P824: the Width chip steps 35% to 40% and the box follows', (w, r['maxw']))
        c.send('screenshot p824_wider')
        time.sleep(.5)
        c.send('set hud_chat 0')
        time.sleep(.6)
        r = dump()
        st = c.query(r'  chat +(on|off) +x +([\d.]+) y +([\d.]+)  ([^\n]*)', 'hud_edit status')
        check(r['panel'] == 0 and st.group(1) == 'off' and 'not drawn' in st.group(4),
              'P824: Chat switched off, the editor draws no box and lists it not drawn',
              (r['panel'], st.group(0).strip()))
        c.send('set hud_chat 1')
        time.sleep(.4)
        pre = c.query(r'"hud_chat_bg" is [^\n]*', 'hud_chat_bg').group(0)   # shows its default
        print('  before reset all:', pre, flush=True)
        for _ in range(2):              # reset all asks once, then does it
            c.query(r'sui_hover \[he_rstall\]', 'hud_edit ui hover he_rstall')
            c.send('hud_edit ui down mouse1')
            time.sleep(.3)
            c.send('hud_edit ui up mouse1')
            time.sleep(.6)
        bg = c.query(r'"hud_chat_bg" is "([^"]*)"', 'hud_chat_bg').group(1)
        w = c.query(r'"hud_chat_w" is "([^"]*)"', 'hud_chat_w').group(1)
        check(abs(float(bg) - 0.88) < 1e-4 and abs(float(w) - 0.35) < 1e-4,
              'P824: reset all puts Box back to 88% (saved first at 50%) and Width to 35%', (bg, w))
        c.send('hud_edit off')
        time.sleep(.6)
        r = dump()
        check(r['panel'] == 0 and r['claims'] == 0, 'P824: hud_edit closed, the box goes and so does the mouse',
              (r['panel'], r['claims']))
        focus = re.findall(r'\[focus\] window is foreground[^\n]*', c.text())
        check(not focus, 'the window never had the focus (no owner click reached it)', focus[:2])
    finally:
        if c:
            c.stop()
        report['log'] = str(c.log) if c else None
        (a.out / 'report.json').write_text(json.dumps(report, indent=1))
    shots = sorted(p.name for p in (a.out / 'client/ftesurf/screenshots').glob('*.png')) \
        if (a.out / 'client/ftesurf/screenshots').is_dir() else []
    print('screenshots:', shots)
    failed = [x['name'] for x in checks if not x['pass']]
    print(f'{len(checks) - len(failed)} of {len(checks)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
