"""Which trigger_setspeed volumes can drive velocity_z above PM_NONJUMP_VEL (140),
and which of those overlap a START zone?

trigger_setspeed_touch (sv_entities.qc:5932) writes velocity_z directly and is NOT
a run_pushed writer, so Patch 409's gate (`!run_pushed || run_jumpcmd`,
sv_timer.qc:9156) passes and the hopped-start accusation proceeds.  A pad that sets
vel_z above 140 therefore reads as a jump the player did not make.

Dialect follows the QC exactly (:5874): if ANY of Interval / HorizontalSpeedAmount /
VerticalSpeedAmount / KeepHorizontalSpeed / KeepVerticalSpeed is non-zero it is the
new dialect -- vspeed = VerticalSpeedAmount, vmode = Keep ? IGNORE : SET.  Else the
old one: vspeed = VerticalSpeed, vmode = VerticalSpeedMode (0 -> IGNORE).
"""
import contextlib, io, json, os, sys

sys.argv = ['pushcensus']
with contextlib.redirect_stdout(io.StringIO()):
    import pushcensus as pc
import bsplib

SSV_SET, SS_INCREASE, SS_DECREASE, SS_IGNORE = 1, 2, 3, 4
NONJUMP = 140.0
CLASSES = ('trigger_setspeed', 'trigger_momentum_setspeed')


def key2(e, cap, low):
    """SV_Key2: the capitalised key if non-zero, else the lowercase one."""
    for k in (cap, low):
        v = e.get(k)
        if v is None:
            continue
        try:
            f = float(str(v).split()[0])
        except (ValueError, IndexError):
            continue
        if f != 0.0:
            return f
    return 0.0


def vertical(e):
    """-> (vmode, vspeed) exactly as trigger_setspeed_touch computes them."""
    new = any(key2(e, c, c.lower()) != 0.0 for c in (
        'Interval', 'HorizontalSpeedAmount', 'VerticalSpeedAmount',
        'KeepHorizontalSpeed', 'KeepVerticalSpeed'))
    if new:
        vspeed = key2(e, 'VerticalSpeedAmount', 'verticalspeedamount')
        vmode = SS_IGNORE if key2(e, 'KeepVerticalSpeed', 'keepverticalspeed') else SSV_SET
        return vmode, vspeed
    vspeed = key2(e, 'VerticalSpeed', 'verticalspeed')
    vmode = int(key2(e, 'VerticalSpeedMode', 'verticalspeedmode')) or SS_IGNORE
    return vmode, vspeed


def fires_every_command(e):
    return bool(key2(e, 'EveryTick', 'everytick'))


def main():
    maps = {os.path.splitext(f)[0].lower(): os.path.join(pc.MAPS, f)
            for f in os.listdir(pc.MAPS) if f.lower().endswith('.bsp')}
    zfiles = {os.path.splitext(f)[0].lower(): os.path.join(pc.ZON, f)
              for f in os.listdir(pc.ZON) if f.lower().endswith('.json')}

    st = dict(bsp_total=len(maps), scanned=0, unreadable=0, maps_with_ss=0,
              ss_total=0, ss_pointent=0, ss_vertical_up=0, ss_over_nonjump=0,
              nostart=0, over_and_overlap=0, over_and_near300=0)
    rows, overlap_rows = [], []

    for name in sorted(maps):
        try:
            ents, models = bsplib.read(maps[name])
        except Exception:
            st['unreadable'] += 1
            continue
        if ents is None:
            st['unreadable'] += 1
            continue
        st['scanned'] += 1

        pads = [e for e in ents if e.get('classname') in CLASSES]
        if not pads:
            continue
        st['maps_with_ss'] += 1
        st['ss_total'] += len(pads)

        starts = []
        if name in zfiles:
            try:
                starts = pc.json_starts(zfiles[name])
            except Exception:
                starts = []
        if not starts:
            for e in ents:
                if e.get('classname') == 'trigger_momentum_timer_start':
                    b = pc.ent_box(e, models)
                    if b:
                        starts.append(b)

        for e in pads:
            vmode, vspeed = vertical(e)
            if vmode not in (SSV_SET, SS_INCREASE) or vspeed <= 0:
                continue
            st['ss_vertical_up'] += 1
            if vspeed <= NONJUMP:
                continue
            st['ss_over_nonjump'] += 1

            box = pc.ent_box(e, models)
            if box is None:
                st['ss_pointent'] += 1
            gapv = None
            if box and starts:
                gapv = min(pc.gap(box, s) for s in starts)
            rows.append(dict(map=name, vspeed=vspeed,
                             mode='SET' if vmode == SSV_SET else 'INCREASE',
                             everytick=fires_every_command(e),
                             gap=gapv, boxed=box is not None,
                             hasstart=bool(starts)))
            if gapv is not None and gapv <= 0.0:
                st['over_and_overlap'] += 1
                overlap_rows.append(rows[-1])
            elif gapv is not None and gapv <= 300.0:
                st['over_and_near300'] += 1

    print(json.dumps(st, indent=1))
    print('\n-- setspeed pads writing vel_z > 140 that OVERLAP a start zone (%d) --'
          % len(overlap_rows))
    for r in overlap_rows:
        print('  %-30s vel_z %-8.1f %-9s%s' % (
            r['map'], r['vspeed'], r['mode'],
            '  EveryTick' if r['everytick'] else ''))

    near = sorted((r for r in rows if r['gap'] is not None and 0 < r['gap'] <= 300),
                  key=lambda r: r['gap'])
    print('\n-- ...and within 300 u of one (%d) --' % len(near))
    for r in near:
        print('  %-30s vel_z %-8.1f %-9s gap %.1f' % (
            r['map'], r['vspeed'], r['mode'], r['gap']))

    print('\n-- every setspeed pad writing vel_z > 140, by speed (%d) --' % len(rows))
    for r in sorted(rows, key=lambda r: -r['vspeed'])[:40]:
        g = 'n/a' if r['gap'] is None else '%.0f' % r['gap']
        print('  %-30s vel_z %-8.1f %-9s gap %-8s%s' % (
            r['map'], r['vspeed'], r['mode'], g,
            'EveryTick' if r['everytick'] else ''))


if __name__ == '__main__':
    main()
