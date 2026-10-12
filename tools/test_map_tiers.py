#!/usr/bin/env python3
"""Source-bound guards and optional isolated menu runtime controls.

python tools/test_map_tiers.py
python tools/test_map_tiers.py --progs <NoDeploy directory> --output-dir <owned artifacts>
Runtime requires a quiet Windows machine; never swaps canonical fixtures/progs.
"""
import argparse
import pathlib
import re
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def source_tier_checks(source, load):
    import math
    body = source.split('string(string value) ui_source_tier =', 1)[1].split('void() ui_meta_load =', 1)[0]
    condition = body.split('if (', 1)[1].splitlines()[0][:-1]
    condition = condition.replace('&&', 'and').replace('floor(tier)', 'math.floor(tier)')
    def tier(value):
        try:
            number = float(value)
        except ValueError:
            number = 0
        return int(number) if eval(condition, {'__builtins__': {}}, {'tier': number, 'math': math}) else 0
    for value, expected in [('99', 0), ('999', 0), ('3.5', 0), ('-2', 0), ('0', 0),
                            ('-', 0), ('1', 1), ('10', 10), ('3', 3), ('inf', 0)]:
        assert tier(value) == expected, (value, expected)
    alias = load.split('if (!strcmp(argv(10), "alias"))', 1)[1].split('else if', 1)[0]
    assert 'if (!strcmp(bufstr_get(ms_momtsrc, row), "local"))' in alias
    assert 'bufstr_set(ms_momtier, row, "0")' in alias
    assert 'bufstr_set(ms_momtsrc, row, "")' in alias
    assert 'else if (stof(ui_source_tier(argv(2))) > 0)' in load
    assert 'if (!strcmp(argv(10), "sugg"))' in load
    assert 'argv(10) == "sugg" || argv(10) == "alias"' not in load
    assert 'MOM tier inherited' not in source
    # Source-bound conditions with a fixture merge model; not a QC VM interpreter.
    fixtures = [('99', '4', '3', 'sugg', '-', 'network', (3, 4)),
                ('3.5', '999', '3', 'sugg', '4', 'local', (3, 4)),
                ('-2', '-1', '99', 'rank', '999', 'network', (0, 0)),
                ('1', '10', '0', 'rank', '0', 'local', (1, 10)),
                ('0', '4', '3', 'alias', '4', 'network', (0, 4)),
                ('3', '4', '3', 'alias', '4', 'local', (0, 4)),
                ('2', '4', '3', 'alias', '4', 'network', (2, 4)),
                ('0', '0', '1.5', 'rank', '-2', 'network', (0, 0)),
                ('0', '0', '1', 'rank', '10', 'network', (1, 10))]
    for m, k, mt, tsrc, kt, origin, expected in fixtures:
        mom, ksf = tier(m), tier(k)
        if tsrc == 'alias':
            if origin == 'local':
                mom = 0
        elif tier(mt):
            if tsrc == 'ksf':
                ksf = tier(mt)
            elif tsrc != 'sugg' or mom == 0:
                mom = tier(mt)
        if tier(kt):
            ksf = tier(kt)
        assert (mom, ksf) == expected
        if tsrc == 'alias' and not mom:
            assert 4 in (mom, ksf) and 3 not in (mom, ksf)
    print('PASS exact-source tier-range predicate + 9 guarded merge fixtures (not VM execution)')


def source_checks(source=None):
    if source is None:
        source = (ROOT / "src/menu/m_main.qc").read_text()
    load = source.split("void() ui_meta_load =", 1)[1].split("local float fb;", 1)[0]
    assert 'bufstr_set(ms_momtier, row, ui_source_tier(argv(2)))' in load
    assert '!strcmp(argv(10), "ksf")' in load
    assert 'bufstr_set(ms_ksftier, row, ui_source_tier(argv(11)))' in load
    source_tier_checks(source, load)
    assert 'usemom = (stof(bufstr_get(ms_momtier, row)) <= 0)' in load
    assert 'bufstr_set(ms_momtsrc, row,' in load
    assert 'mtsrc = bufstr_get(ms_momtsrc, real)' in source
    dl = source.split("void() ui_dl_load =", 1)[1].split("void() ui_data_load =", 1)[0]
    for index in ("row", "ms_count"):
        assert f'bufstr_set(ms_momtier, {index}, (n >= 9) ? ui_source_tier(argv(8)) : "0")' in dl
        assert f'bufstr_set(ms_ksftier, {index}, (n >= 10) ? ui_source_tier(argv(9)) : "0")' in dl
    for index in ('row', 'ms_count'):
        assert f'bufstr_set(ms_momtsrc, {index}, network ? "network" : "local")' in dl
    assert 'network = (fh >= 0)' in dl
    assert 'bufstr_add(ms_momtsrc, "", TRUE)' in source
    fallback = source.split("local float fb;", 1)[1].split("Start the atlas loads", 1)[0]
    assert "ms_momtier" not in fallback and "ms_ksftier" not in fallback
    refilter = source.split("void() ui_refilter =", 1)[1].split("// The library switch", 1)[0]
    assert 'stof(bufstr_get(ms_momtier, i)) != ms_tier' in refilter
    assert 'stof(bufstr_get(ms_ksftier, i)) != ms_tier' in refilter
    assert 'strcat("MOM T", mtier) : "MOM -", \'0.25 0.55 1\', 1, 0' in source
    assert 'strcat("KSF T", mktier) : "KSF -", \'1 1 1\', 1, 0' in source
    for symbol in ('strcat("T", mtier, "~")', 'strcat("T", mtier, "?")', 'strcat("T", mtier, "k")'):
        assert symbol not in source
    assert 'ms_tierv = ms_momtier = ms_ksftier = ms_momtsrc =' in source
    # Execute the exact source predicate after translating its side-effect-free
    # QC lookups/operators. This checks the exemption, not the menu VM or pixels.
    bare = source.split('if (stof(bufstr_get(ms_dataq, i)) == DQ_BARE)', 1)[1]
    predicate = bare.split('if (!(', 1)[1].split('\n\t\t\t{', 1)[0][:-2]
    predicate = predicate.replace('bufstr_get(ms_have, i)', 'have')
    predicate = predicate.replace('stof(bufstr_get(ms_src, i))', 'src')
    predicate = predicate.replace('substring(movementname, 0, 5)', 'name[:5]')
    predicate = predicate.replace('SRC_BIT_MOM', '2').replace('SRC_BIT_CSS', '4')
    predicate = ' '.join(predicate.replace('&&', 'and').replace('||', 'or').split())
    cases = [('1', 2, 'surf_unknown', True), ('1', 4, 'bhop_unknown', True),
             ('1', 6, 'surf_unknown', True), ('1', 2, 'agtricks', False),
             ('0', 2, 'surf_unknown', False), ('2', 2, 'surf_unknown', False),
             ('1', 1, 'surf_unknown', False), ('1', 8, 'bhop_unknown', False),
             ('1', 2, 'surfer', False), ('1', 4, 'bhop', False)]
    for have, src, name, expected in cases:
        assert bool(eval(predicate, {'__builtins__': {}}, {'have': have, 'src': src, 'name': name})) == expected, (have, src, name)
    print('PASS exact-source bare exemption truth table: 10 cases (not VM execution)')
    print("PASS source guards: independent buffers, provenance capture before fallback, either-source predicate, explicit colors/labels")


def runtime(a):
    import p615link as L
    # No maps mount: only the synthetic downloadable names enter the list.
    L.CONTENT_DIRS = tuple(n for n in L.CONTENT_DIRS if n != "maps")
    a.content = pathlib.Path("C:/FTESurf")
    a.output_dir = a.output_dir.resolve()
    a.output_dir.mkdir(parents=True, exist_ok=True)
    a.progs = a.progs.resolve()
    rig, gd, junctions = L.build_rig(a)
    client = None
    try:
        data = gd / "data"
        data.mkdir()
        data.joinpath("consent.txt").write_text("version 4\n")
        # Collapsed argv4 deliberately differs from independent argv8/9.
        names = ["diff", "mom", "ksf", "oldksf", "unknown", "sugg", "alias",
                 "manifestonly", "knownsugg", "knownalias", "unknownmerge", "bad", "fractional", "negative", "bounds"]
        sources = [(8, 9), (8, 0), (0, 5), (0, 0), (0, 0), (0, 0), (0, 4),
                   (2, 4), (5, 0), ((2 if a.network else 3), 4), (7, 8), (99, 999), (3.5, -2), (-3, -4), (1, 10)]
        rows = [f"dl surf_tiers_{n} surf km 9 100 2026-10-01 0 {m} {k}"
                for n, (m, k) in zip(names, sources)]
        # Truly legacy row: no independent source columns, cannot infer from argv4.
        rows.append("dl surf_tiers_collapsed surf m 7 100 2026-10-01 0")
        rows.append("dl surf_tiers_diff_css surf k 4 200 2026-10-01 0 0 4 surf_tiers_diff")
        manifest = "FTESURF-MAPDL 1\n" + "\n".join(rows) + "\n"
        data.joinpath("mapdl.txt").write_text(manifest)
        # Same sanitized grammar/read path for cached network catalogue.
        if a.network:
            data.joinpath("mapdl.net.txt").write_text(manifest)
        values = [("diff", 2, "rank", 4), ("mom", 3, "rank", "-"),
                  ("ksf", "-", "-", 5), ("oldksf", 6, "ksf", "-"),
                  ("unknown", "-", "-", "-"), ("sugg", 3, "sugg", "-"),
                  ("alias", 3, "alias", "4"), ("knownsugg", 3, "sugg", "-"),
                  ("knownalias", 3, "alias", "4"), ("unknownmerge", "-", "-", "-"), ("bad", 3, "sugg", 4),
                  ("fractional", 3, "sugg", 4), ("negative", 99, "rank", 999),
                  ("bounds", 0, "rank", 0)]
        data.joinpath("mapmeta.txt").write_text("FTESURF-MAPMETA 1\n" + "".join(
            f"meta surf_tiers_{n} {t} 1 0 0 - - - 1 {src} {k}\n" for n, t, src, k in values))
        # Authoritative shared gate: immediately before launch, no peer/owner game.
        gate = subprocess.run(["pwsh", "-NoProfile", "-Command",
            'Get-CimInstance Win32_Process | Where-Object { $_.Name -match "fte(surf|qw).*exe" } | ForEach-Object { "ACTIVE $($_.ProcessId) $($_.Name)" }'],
            check=True, capture_output=True, text=True)
        if gate.stdout.strip():
            raise RuntimeError("runtime blocked by active owner/peer game: " + gate.stdout.strip())
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4
        client = subprocess.Popen([str(a.content / "ftesurf64.exe"), "-plugin", "-nobrowse",
            "-basedir", str(rig), "-manifest", str(rig / "default.fmf"),
            "+set", "cfg_save_auto", "0", "+set", "log_enable", "1", "+set", "log_dir", "logs",
            "+set", "log_name", "tiers", "-window", "-nosound", "+set", "con_savehistory", "0",
            "+set", "cl_idlefps", "0", "+set", "cl_maxfps", "100"], cwd=a.content,
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si)
        print("owned client PID", client.pid, "rig", rig)
        def send(line):
            client.stdin.write((line + "\n").encode("ascii"))
            client.stdin.flush()
        log = L.Log(gd / "logs/tiers.log")
        time.sleep(12)
        for line in ('menu_restart', 'set lobby_dir ""', 'set ui_maps_showall 1', 'ui_strip_test screen create'):
            send(line)
            time.sleep(0.5)
        assert log.wait(r"ui_strip_test: screen create", 10), "create command did not act"
        time.sleep(2)
        def click(tier):
            send(f"ui_hover @cs_tier{tier}")
            time.sleep(0.4)
            send("ui_mouse down")
            time.sleep(0.2)
            send("ui_mouse up")
            time.sleep(0.6)
        def find(query, count):
            send('ui_find "' + query + '"')
            found = log.wait(r"ui_find: " + re.escape(query) + r" view (\d+) first (\S+)", 8)
            assert found and int(found.group(1)) == count, (query, count, found and found.groups())
        for tier, queries in [(2, [("diff", 1), ("tiers_alias", 0), ("ksf", 0), ("manifestonly", 1), ("knownalias", 1 if a.network else 0)]),
                              (4, [("diff", 1), ("mom", 0), ("manifestonly", 1), ("knownalias", 1), ("tiers_alias", 1), ("bad", 1)]),
                              (3, [("mom", 1), ("tiers_sugg", 1), ("knownsugg", 0), ("bad", 1), ("fractional", 1)]),
                              (5, [("tiers_ksf", 1), ("diff", 0), ("knownsugg", 1)]),
                              (6, [("oldksf", 1), ("knownalias", 0)]),
                              (7, [("collapsed", 0), ("tiers_unknown", 1), ("unknownmerge", 1)]),
                              (8, [("unknownmerge", 1), ("diff", 0)]),
                              (10, [("bounds", 1), ("negative", 0)])]:
            click(tier)
            for query, count in queries:
                find(query, count)
            # Pixel evidence needs an acted positive row, not the final
            # zero-match negative (particularly the boundary T10 fixture).
            find(queries[0][0], queries[0][1])
            send(f"screenshot tiers_filter{tier}")
            time.sleep(1)
            print("PASS runtime filter", tier, queries)
        click(0)
        find("", 16)
        find("diff_css", 1)
        send("ui_build surf_tiers_diff css")
        assert log.wait(r"ui_build: surf_tiers_diff .*pick css; plays surf_tiers_diff_css", 8)
        send("screenshot tiers_clear")
        time.sleep(2)
        assert "no control" not in log.text()
        assert not any(w in log.text() for w in ("Unknown command", "QC VM error", "Cannot call", "stack overflow"))
        print("PASS clear restored 16 rows; variant alias search + build selection retained; screenshots require inspection")
        send("quit")
        client.wait(timeout=20)
    finally:
        if client is not None and client.poll() is None:
            client.terminate()
            client.wait(timeout=10)
        for path in junctions:
            if not path.lstat().st_file_attributes & 0x400:
                raise RuntimeError("not our junction: " + str(path))
            path.rmdir()
        print("rig retained with junctions removed:", rig)
        print("owned client stopped:", client is None or client.poll() is not None)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--network", action="store_true", help="exercise cached mapdl.net.txt rather than shipped list")
    ap.add_argument("--progs", type=pathlib.Path)
    ap.add_argument("--output-dir", type=pathlib.Path)
    a = ap.parse_args()
    source_checks()
    mutated = (ROOT / 'src/menu/m_main.qc').read_text().replace(
        'bufstr_get(ms_have, i) == "1"', '"1" == "1"')
    try:
        source_checks(mutated)
    except AssertionError:
        print('PASS negative control: removing installed gate fails bare-row truth table')
    else:
        raise AssertionError('bare-row mutation unexpectedly passed')
    current = (ROOT / 'src/menu/m_main.qc').read_text()
    for description, old, new in [('tier bound', 'tier <= 10', 'tier <= 999'),
                                  ('fractional tier', 'tier == floor(tier)', 'tier == tier'),
                                  ('local alias provenance', 'ms_momtsrc, row), "local"', 'ms_momtsrc, row), "network"')]:
        assert old in current
        try:
            source_checks(current.replace(old, new))
        except AssertionError:
            print('PASS negative control:', description)
        else:
            raise AssertionError(description + ' mutation unexpectedly passed')
    baseline = subprocess.check_output(["git", "-C", str(ROOT), "show",
                                        "2c540555d67e6237dc7e83bef36ca711aaa519fe:src/menu/m_main.qc"], text=True)
    try:
        source_checks(baseline)
    except AssertionError:
        print("PASS negative control: pre-change source fails the independent-source guards")
    else:
        raise AssertionError("pre-change source unexpectedly passed")
    if a.progs:
        if a.output_dir is None:
            ap.error("runtime needs an explicitly owned --output-dir")
        runtime(a)


if __name__ == "__main__":
    main()
