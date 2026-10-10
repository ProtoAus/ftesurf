#!/usr/bin/env python3
"""Patch 614: do the plot fixtures notice a broken engine? A mutant is one edit to a COPY of the
engine tree's files, and the fixture built against the copy must fail. Three sweeps:

  host      fixtures/p614plot_host.c against engine/client/cl_plugin_ui_plot.inc (the builtins)
  grammar   fixtures/p614plot_valid.cpp against plugins/ui_model.h (the rules both sides run)
  provider  fixtures/p614plots_host.cpp against plugins/ui_imgui (owner 206)

The anchors are the engine's source at this patch. One that is not in the tree exactly once stops
the sweep: a stale anchor must not read as a catch. Nor does a mutant that fails to BUILD (the
trees compile with -Werror, so an edit that orphans a variable does): that is NO RUN, and wrong.
EQUIVALENT names the mutants no fixture can tell from the original, each with its reason; the
sweep fails if any other survives, and also if one of those is caught, because its reason then no
longer holds.

    python tools/p614mutants.py --fte <engine tree> --out <owned scratch dir> [host grammar provider] [--only text]

The provider sweep compiles Dear ImGui and ImPlot once a mutant: about 25 s each, 350 MB of compiler.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from p598build import build  # noqa: E402
from test_p590bridge_unit import host_controls  # noqa: E402

PLOT = 'engine/client/cl_plugin_ui_plot.inc'
P = 'plugins/ui_imgui/plots.inc'
U = 'plugins/ui_imgui/ui_imgui.cpp'
N = 'PlugUI_PlotNumber'
F = 'PlugUI_Finite'
HOST = [
    ('revisions need not rise', PLOT, '!revision || revision <= v->plotrevision || count < 0', '!revision || count < 0'),
    ('no begin budget', PLOT, 'v->plotbegins == PLUGUI_PLOT_BEGINS || ', ''),
    ('series out of order', PLOT, 'IS_NAN(index) || index != v->plotseries || ', 'IS_NAN(index) || '),
    ('a series before the last one has rows', PLOT, 'v->plotseries >= v->plot.count || !v->plotrows || flags < 0', 'v->plotseries >= v->plot.count || flags < 0'),
    ('any gap', PLOT, 'if (!PlugUI_PlotNumber(s.gap) || !(s.gap > 0)) return;', ''),
    ('gap of any size', PLOT, 'if (!PlugUI_PlotNumber(s.gap) || !(s.gap > 0)) return;', 'if (!PlugUI_Finite(s.gap) || !(s.gap > 0)) return;'),
    ('x of any size', PLOT, 'if (!PlugUI_PlotNumber(xv) || ', 'if (!PlugUI_Finite(xv) || '),
    ('x judged before its offset', PLOT, 'if (!PlugUI_PlotNumber(xv) || ', 'if (!PlugUI_PlotNumber(Plug_NativeUI_Float(x, i)) || '),
    ('a of any size', PLOT, '!PlugUI_PlotNumber(av) || ', '!PlugUI_Finite(av) || '),
    ('b of any size', PLOT, '!PlugUI_PlotNumber(bv) || ', '!PlugUI_Finite(bv) || '),
    ('view mark of any size', 'plugins/ui_model.h', 'PlugUI_PlotNumber(v->mark)', 'PlugUI_Finite(v->mark)'),
    ('view range start of any size', 'plugins/ui_model.h', 'PlugUI_PlotNumber(v->x0)', 'PlugUI_Finite(v->x0)'),
    ('view range end of any size', 'plugins/ui_model.h', 'PlugUI_PlotNumber(v->x1);', 'PlugUI_Finite(v->x1);'),
    ('any colour', PLOT, 'if (!PlugUI_Finite(s.rgb[i]) || s.rgb[i] < 0 || s.rgb[i] > 1) return;', ''),
    ('rows twice', PLOT, 'index != v->plotseries - 1 || v->plotrows ||', 'index != v->plotseries - 1 ||'),
    ('b without HAS_B', PLOT, 'else if (G_INT(OFS_PARM4)) return;', ''),
    ('time may run backwards', PLOT, '(i && xv < last)) return;', '(i && xv < last && 0)) return;'),
    ('offset not applied', PLOT, 'xv = Plug_NativeUI_Float(x, i) - xoffset;', 'xv = Plug_NativeUI_Float(x, i);'),
    ('break flag kept raw', PLOT, 'v->plotbrk[at+i] = (kv != 0);', 'v->plotbrk[at+i] = (qbyte)kv;'),
    ('b not zeroed without HAS_B', PLOT, 'bv = b ? Plug_NativeUI_Float(b, i) : 0;', 'bv = b ? Plug_NativeUI_Float(b, i) : av;'),
    ('row allowance unchecked', PLOT, 'if (rows > PLUGUI_PLOT_MAX_TOTAL - v->plot.points) return false;', ''),
    ('commit with a series short', PLOT, 'v->plotbad || v->plotseries != v->plot.count || !v->plotrows', 'v->plotbad || !v->plotrows'),
    ('commit twice', PLOT, 'if (!v || !v->plotactive) return;\n\tv->plotactive = false;\n\tif (v->plotbad', 'if (!v || !v->plotactive) return;\n\tif (v->plotbad'),
    ('refusing provider keeps the owner', PLOT, 'if (!ok) Plug_NativeUI_CloseOwner(v, PLUGUI_CLOSE_FAILED);\n\t\telse { v->plotrevision', 'if (!ok) {}\n\t\telse { v->plotrevision'),
    ('view before a plot', PLOT, 'if (!v || !v->plotrevision || marked < 0', 'if (!v || marked < 0'),
    ('view unvalidated', PLOT, 'if (!PlugUI_PlotViewValid(&view)) return;', ''),
    ('staging outside the draw bracket', PLOT, 'return v && v->drawing && handle && handle == v->owner.generation &&\n\t\tPlug_NativeUI_PlotReady() ? v : NULL;', 'return v && handle && handle == v->owner.generation &&\n\t\tPlug_NativeUI_PlotReady() ? v : NULL;'),
    ('rows kept past the owner', 'engine/client/cl_plugin_ui.inc', '\tPlug_NativeUI_PlotFree(v);\n\tif (!owner.generation', '\tif (0) Plug_NativeUI_PlotFree(v);\n\tif (!owner.generation'),
    ('register before input', PLOT, 'plugui_busy || !plugui_input.Input || plugui_plot.SetPlot) return false;', 'plugui_busy || plugui_plot.SetPlot) return false;'),
    ('register twice', PLOT, 'plugui_busy || !plugui_input.Input || plugui_plot.SetPlot) return false;', 'plugui_busy || !plugui_input.Input) return false;'),
]
GRAMMAR = [
    ('plot: any structsize', 'p->structsize != sizeof(*p) || ', ''),
    ('plot: revision zero', '!p->revision || p->revision > PLUGUI_MODEL_MAX_ID', 'p->revision > PLUGUI_MODEL_MAX_ID'),
    ('plot: revision past the id range', '!p->revision || p->revision > PLUGUI_MODEL_MAX_ID ||', '!p->revision ||'),
    ('plot: seventeen series', 'p->count > PLUGUI_PLOT_MAX_SERIES || ', ''),
    ('plot: any total', 'p->points > PLUGUI_PLOT_MAX_TOTAL ||', ''),
    ('plot: null x', '(!p->x || !p->a || !p->b || !p->brk)', '(!p->a || !p->b || !p->brk)'),
    ('plot: null a', '(!p->x || !p->a || !p->b || !p->brk)', '(!p->x || !p->b || !p->brk)'),
    ('plot: null b', '(!p->x || !p->a || !p->b || !p->brk)', '(!p->x || !p->a || !p->brk)'),
    ('plot: null brk', '(!p->x || !p->a || !p->b || !p->brk)', '(!p->x || !p->a || !p->b)'),
    ('series: any flag', 's->flags > PLUGUI_PLOT_FLAGS || ', ''),
    ('series: empty', '!s->count || s->count > PLUGUI_PLOT_MAX_POINTS', 's->count > PLUGUI_PLOT_MAX_POINTS'),
    ('series: any length', '!s->count || s->count > PLUGUI_PLOT_MAX_POINTS ||', '!s->count ||'),
    ('series: any first row', 's->first != at || ', ''),
    ('series: past the rows', 's->count > p->points - at ||', ''),
    ('series: gap of any size', '!' + N + '(s->gap)', '!' + F + '(s->gap)'),
    ('series: gap not positive', ' || !(s->gap > 0)) return 0;', ') return 0;'),
    ('series: colour not finite', '!PlugUI_Finite(s->rgb[j]) || ', ''),
    ('series: colour below zero', 's->rgb[j] < 0 || ', ''),
    ('series: colour above one', ' || s->rgb[j] > 1) return 0;', ') return 0;'),
    ('rows: x of any size', '!' + N + '(p->x[k])', '!' + F + '(p->x[k])'),
    ('rows: a of any size', '!' + N + '(p->a[k])', '!' + F + '(p->a[k])'),
    ('rows: b of any size', '!' + N + '(p->b[k])', '!' + F + '(p->b[k])'),
    ('rows: x unchecked', '!' + N + '(p->x[k]) || ', ''),
    ('rows: a unchecked', '!' + N + '(p->a[k]) || ', ''),
    ('rows: b unchecked', '!' + N + '(p->b[k]) ||', '0 ||'),
    ('rows: any break byte', 'p->brk[k] > 1) return 0;', '0) return 0;'),
    ('rows: time backwards', 'if (k > at && p->x[k] < p->x[k-1]) return 0;', ''),
    ('rows: backwards across the first pair', 'if (k > at && p->x[k] < p->x[k-1]) return 0;', 'if (k > at + 1 && p->x[k] < p->x[k-1]) return 0;'),
    ('plot: rows left over', 'return at == p->points;', 'return 1;'),
    ('number: no lower bound', 'value >= -PLUGUI_PLOT_MAX_VALUE && ', ''),
    ('number: no upper bound', ' && value <= PLUGUI_PLOT_MAX_VALUE;', ';'),
    ('number: not finite', 'return PlugUI_Finite(value) && value >= -PLUGUI_PLOT_MAX_VALUE', 'return value >= -PLUGUI_PLOT_MAX_VALUE'),
    ('view: any structsize', 'v->structsize == sizeof(*v) && v->hidden', 'v->hidden'),
    ('view: hidden mask too wide', 'v->hidden < (1u << PLUGUI_PLOT_MAX_SERIES) &&', ''),
    ('view: emphasis mask too wide', 'v->emphasis < (1u << PLUGUI_PLOT_MAX_SERIES) && ', ''),
    ('view: marked not a flag', 'v->marked <= 1 && ', ''),
    ('view: mark of any size', N + '(v->mark)', F + '(v->mark)'),
    ('view: mark unchecked', N + '(v->mark) &&', '1 &&'),
    ('view: caption size not finite', 'PlugUI_Finite(v->textpx) && ', ''),
    ('view: caption size below one', 'v->textpx >= 1 && ', ''),
    ('view: caption size above 256', 'v->textpx <= 256 &&', ''),
    ('view: any range serial', 'v->rangeserial <= PLUGUI_MODEL_MAX_ID && ', ''),
    ('view: range start of any size', N + '(v->x0)', F + '(v->x0)'),
    ('view: range end of any size', N + '(v->x1);', F + '(v->x1);'),
    ('view: range start unchecked', N + '(v->x0) && ', ''),
    ('view: range end unchecked', ' && ' + N + '(v->x1);', ';'),
]
PROVIDER = [
    ('cone twice as wide', P, 'lo = (p.y-PlotsTolerance-anchor.y)/dx; hi = (p.y+PlotsTolerance-anchor.y)/dx;\n\t\tlast = p; pending = true;',
     'lo = (p.y-2*PlotsTolerance-anchor.y)/dx; hi = (p.y+2*PlotsTolerance-anchor.y)/dx;\n\t\tlast = p; pending = true;'),
    ('cone never narrows', P, 'lo = std::max(lo,(p.y-PlotsTolerance-anchor.y)/dx); hi = std::min(hi,(p.y+PlotsTolerance-anchor.y)/dx);', ''),
    ('breaks joined', P, '\t\t\tif (i > i0 && (bk[i] || xs[i]-xs[i-1] > s.gap)) swing.End();\n\t\t\tswing.Add(pixel(i));', '\t\t\tswing.Add(pixel(i));'),
    ('gaps joined', P, 'if (i > i0 && (bk[i] || xs[i]-xs[i-1] > s.gap)) swing.End();', 'if (i > i0 && bk[i]) swing.End();'),
    ('strips never kept', P, '\tpool.pos = pos; pool.size = size;\n\tpool.valid = true;', '\tpool.pos = pos; pool.size = size;'),
    ('strips kept across a zoom', P, 'pool.shown == shown && pool.x0 == lim.X.Min &&\n\t\tpool.x1 == lim.X.Max && ', 'pool.shown == shown &&\n\t\t'),
    ('strips kept across a revision', P, 'pool.valid && pool.revision == st.revision && ', 'pool.valid && '),
    ('hidden mask ignored', P, 'const unsigned shown = live & ~st.view.hidden, loud = shown & st.view.emphasis;', 'const unsigned shown = live, loud = shown & st.view.emphasis;'),
    ('emphasis not dimming', P, '(loud && !up) ? 0.30f : 1.0f),ImDrawFlags_None', '1.0f),ImDrawFlags_None'),
    ('range request dropped', P, '\t\tst.range = !st.fit;\n', '\t\tst.range = false;\n'),
    ('serial honoured every call', P, 'if (v->rangeserial != st.rangeseen)', 'if (true)'),
    ('right button does nothing', P, 'ImGui::GetIO().MouseDragMaxDistanceSqr[ImGuiMouseButton_Right] < 16.0f) st.fit = true;', 'ImGui::GetIO().MouseDragMaxDistanceSqr[ImGuiMouseButton_Right] < 16.0f) {}'),
    ('wheel step 0.2', U, 'ZoomRate = 0.25f;', 'ZoomRate = 0.2f;'),
    ('no share of the pool', P, 'if (!PlotsSimplify(pool,st,i,second,lim,ax,bx,ay,by,0,fit) || pool.npts-points > share)', 'if (!PlotsSimplify(pool,st,i,second,lim,ax,bx,ay,by,0,fit) && false)'),
    ('rows not copied', P, 'std::memcpy(next->x,p->x,p->points*sizeof(float)); ', ''),
    ('any rectangle', P, 'if (!(width >= 160 && height >= 120 && width <= f.pixelwidth && height <= f.pixelheight)) return false;', ''),
    ('opens without the table', U, 'if (PlotsOwner(*o) && !plotRegistered) return qfalse;', ''),
    ('marker not drawn', P, 'if (st.view.marked)\n', 'if (false)\n'),
    ('hover reported off the plots', P, 'if (st.hover) Action(c,PlotsReportHover,bounded(st.hoverx));', 'Action(c,PlotsReportHover,bounded(st.hoverx));'),
    ('marker drawn out of view', P, 'if (!(double(st.view.mark) >= ImPlot::GetPlotLimits().X.Min && double(st.view.mark) <= ImPlot::GetPlotLimits().X.Max)) continue;', ''),
    ('clock minutes not bounded', P, 'std::min(std::round(std::fabs(value)*scale)/scale,1e11)', 'std::round(std::fabs(value)*scale)/scale'),
    ('clock drops the sign', P, '(value < 0 && v > 0) ? "-" : ""', '""'),
    ('longer revision resets a zoom', P, 'next->fit = old->fit || (whole && next->xmax != old->xmax);', 'next->fit = old->fit || next->xmax != old->xmax || (whole && !whole);'),
    ('range request not kept in the run', P, 'st.want0 = std::min(std::max(double(v->x0),0.0),xmax);', 'st.want0 = v->x0;'),
    ('range request end not kept in the run', P, 'st.want1 = std::min(std::max(double(v->x1),0.0),xmax);', 'st.want1 = v->x1;'),
    ('pixels not bounded', P, 'return ImVec2(float(std::min(std::max(ax*xs[i]+bx,-1e6),1e6)),float(std::min(std::max(ay*ys[i]+by,-1e6),1e6)));', 'return ImVec2(float(ax*xs[i]+bx),float(ay*ys[i]+by));'),
    ('reports not bounded', P, 'auto bounded = [](double value) { return float(std::min(std::max(value,-1e6),1e6)); };', 'auto bounded = [](double value) { return float(value); };'),
    ('usage error ignored', U, 'bool ok = panelok && !c->plotserror && !c->actionoverflow', 'bool ok = panelok && !c->actionoverflow'),
    ('usage errors still assert', U, 'io.ConfigErrorRecoveryEnableAssert = io.ConfigErrorRecoveryEnableDebugLog = io.ConfigErrorRecoveryEnableTooltip = false;', 'io.ConfigErrorRecoveryEnableDebugLog = io.ConfigErrorRecoveryEnableTooltip = false;'),
    ('a view from a stale revision is kept', P, 'if (!c || !PlotsOwner(*o) || !PlugUI_PlotValid(p) || (c->plots && p->revision <= c->plots->revision))', 'if (!c || !PlotsOwner(*o) || !PlugUI_PlotValid(p))'),
]
EQUIVALENT = {
    'host': {
        'commit with a series short': 'the grammar refuses the undeclared series (count 0) on the same call',
    },
    'grammar': {
        'plot: seventeen series': "series[16] is the struct's own pointer bytes, which no rule takes for a series",
        'series: past the rows': 'the totals compared at the end refuse it too, by design',
        'number: not finite': 'NaN and infinity fail the bounds as well; PlugUI_Finite is there for a fast-math build',
        'view: caption size not finite': 'NaN and infinity fail the 1..256 bounds as well',
    },
    'provider': {
        'strips kept across a revision': 'a new revision is a new PlotStore, whose pools start invalid',
        'range request not kept in the run': "ImPlot's own limit cuts a low start in the same frame, and a start past the end is a fit",
    },
}


def mutated(src, dst, name, old, new):
    s = src.read_bytes().decode().replace('\r\n', '\n')
    if old:
        if s.count(old) != 1:
            raise SystemExit(f'STALE ANCHOR {name}: found {s.count(old)} times in {src}')
        s = s.replace(old, new)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(s.encode())


def run_host(a, scratch, name, rel, old, new):
    for f in (a.fte / 'engine/client').glob('cl_plugin_ui*.inc'):
        mutated(f, scratch / 'engine/client' / f.name, name, '', '')
    for f in ('plugin.h', 'ui_model.h'):
        mutated(a.fte / 'plugins' / f, scratch / 'plugins' / f, name, '', '')
    if old:
        mutated(a.fte / rel, scratch / rel, name, old, new)
    # The fixtures print from child processes: both descriptors go to a file for the run.
    log = scratch / 'host.log'
    sys.stdout.flush()
    saved = os.dup(1), os.dup(2)
    with open(log, 'w') as f:
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
        try:
            rc = host_controls(scratch, a.cc.with_name('gcc.exe'), ROOT / 'tools/fixtures/p614plot_host.c')
        finally:
            sys.stdout.flush()
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])
    lines = [ln for ln in log.read_text(errors='replace').splitlines() if ln.strip()]
    tail = [ln for ln in lines if ln.startswith('P614 plot bridge')]
    if not tail and any(': error:' in ln or 'treated as errors' in ln or 'undefined reference' in ln for ln in lines):
        return 'norun', 'did not build: ' + next(ln for ln in lines if 'error' in ln)[-100:]
    return 'fail' if rc else 'pass', tail[-1] if tail else ('crashed; last line: ' + lines[-1][:90] if lines else 'no output')


def run_grammar(a, scratch, name, old, new):
    header = scratch / 'ui_model.h'
    mutated(a.fte / 'plugins/ui_model.h', header, name, old, new)
    run = subprocess.run([sys.executable, str(ROOT / 'tools/test_p614plot_unit.py'), '--fte', str(a.fte), '--out',
                          str(scratch / 'out'), '--cc', str(a.cc), '--header', str(header)], capture_output=True, text=True)
    text = run.stdout + run.stderr
    fails = [ln for ln in text.splitlines() if ln.startswith('FAIL')]
    summary = [ln for ln in text.splitlines() if ln.startswith('P614 PLOT GRAMMAR')]
    if 'did not compile clean' in text:
        return 'norun', 'did not build: ' + text.strip().splitlines()[0][-100:]
    return 'fail' if run.returncode else 'pass', fails[0][5:80] if fails else (summary[0] if summary else text.strip()[-100:])


def run_provider(a, scratch, name, rel, old, new):
    shutil.copytree(a.fte / 'plugins/ui_imgui', scratch / 'plugins/ui_imgui')
    for f in ('plugin.h', 'ui_model.h'):
        shutil.copy2(a.fte / 'plugins' / f, scratch / 'plugins' / f)
    for h in (a.fte / 'engine').rglob('*.h'):
        r = h.relative_to(a.fte)
        if 'release' in r.parts or 'debug' in r.parts or r.parts[1].startswith('libs-'):
            continue
        (scratch / r).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(h, scratch / r)
    if old:
        mutated(a.fte / rel, scratch / rel, name, old, new)
    env = os.environ.copy()
    env['PATH'] = str(a.cc.parent) + os.pathsep + env['PATH']
    try:
        exe = build(scratch, scratch / 'out', a.cc, host=True, host_source=ROOT / 'tools/fixtures/p614plots_host.cpp')
    except (Exception, SystemExit) as e:
        return 'norun', 'did not build: ' + str(e)[-100:]
    run = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
    fails = [ln for ln in (run.stdout + run.stderr).splitlines() if ln.startswith('FAIL')]
    return 'fail' if run.returncode else 'pass', f'{len(fails)} FAIL lines' + (': ' + fails[0][5:70] if fails else '')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--fte', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--cc', type=Path, default=Path('C:/msys64/ucrt64/bin/g++.exe'))
    p.add_argument('--only', action='append', default=[], help='mutants whose name holds this text (repeatable)')
    p.add_argument('sweeps', nargs='*', default=['host', 'grammar', 'provider'])
    a = p.parse_args()
    a.fte, out = a.fte.resolve(), a.out.resolve()
    if not any((d / 'OWNER.md').is_file() for d in [out, *out.parents]):
        raise SystemExit('--out requires an ancestor OWNER.md before population')
    out.mkdir(parents=True, exist_ok=True)
    lists = {'host': HOST, 'grammar': GRAMMAR, 'provider': PROVIDER}
    wrong = 0
    for sweep in a.sweeps:
        known = EQUIVALENT[sweep]
        assert set(known) <= {m[0] for m in lists[sweep]}, 'EQUIVALENT names a mutant that is not in the list'
        todo = [m for m in lists[sweep] if not a.only or any(o in m[0] for o in a.only)]
        caught = survived = 0
        for mutant in [None] + todo:
            name = mutant[0] if mutant else 'control: no edit'
            with tempfile.TemporaryDirectory(prefix=f'p614-{sweep}-', dir=str(out)) as d:
                if sweep == 'grammar':
                    state, detail = run_grammar(a, Path(d), name, *(mutant[1:] if mutant else ('', '')))
                else:
                    runner = run_host if sweep == 'host' else run_provider
                    state, detail = runner(a, Path(d), name, *(mutant[1:] if mutant else (PLOT, '', '')))
            bad = state == 'fail'
            if state == 'norun':
                verdict = 'NO RUN'
                wrong += 1
            elif not mutant:
                verdict = 'CONTROL OK' if not bad else 'CONTROL BROKEN'
                wrong += bad
            elif bad:
                caught += 1
                verdict = 'CAUGHT' if name not in known else 'CAUGHT, WAS CALLED EQUIVALENT'
                wrong += name in known
            else:
                survived += 1
                verdict = 'EQUIVALENT' if name in known else 'MISSED'
                wrong += name not in known
                detail = known.get(name, detail)
            print(f'{sweep:8s} {verdict:14s} {name}: {detail}', flush=True)
        print(f'{sweep}: {caught} of {len(todo)} mutants caught, {survived} survived ({len(known)} are called equivalent)', flush=True)
    print('P614 MUTANTS wrong verdicts:', wrong)
    raise SystemExit(bool(wrong))
