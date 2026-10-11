#!/usr/bin/env python3
"""plan_audit.py -- which of surfd's statements change plan if an index is added?

    python tools/plan_audit.py "CREATE INDEX runs_player ON runs (player)" [suite ...]

An index is not only a faster path.  On 11 Oct 2026 `runs_player` was built on
the live database for one query and moved two others that GROUP BY player onto a
walk of it with a table lookup a row: 8.0 s became 34.2 s (Patch 636).

Runs the service's suites in this process with every sqlite statement traced,
keeps one example of each statement shape that names the index's table, and
compares EXPLAIN QUERY PLAN on a fresh schema with and without the index.  With
no sqlite_stat1 (the live file has none) the planner's choice does not depend on
the data, so these plans are the Pi's.  A statement only a tool run by cron
issues is seen only if a suite drives that tool in-process: grep those by hand.

Prints every statement whose plan moves; the ones to worry about say
`SCAN ... USING INDEX <the new one>`, an ordered walk of the whole table.  Pin a
statement that must not move with a unary plus on the column (`GROUP BY
+player`) and a test of its plan.
"""
import io
import os
import re
import runpy
import shutil
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SURFD = os.path.join(os.path.dirname(HERE), "surfd")
SUITES = ["test_web", "test_board", "test_ranked", "test_accounts", "test_replays",
          "test_evidence", "test_sweep", "test_momboards", "test_admin"]


def shape(sql):
    s = re.sub(r"'(?:[^']|'')*'", "?", sql)
    s = re.sub(r"\b\d+(\.\d+)?\b", "?", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ddl = sys.argv[1]
    m = re.match(r"\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+(\w+)",
                 ddl, re.I)
    if not m:
        print("not a CREATE INDEX statement: %r" % ddl)
        return 2
    index, table = m.group(1), m.group(2)
    suites = sys.argv[2:] or SUITES
    sys.path.insert(0, SURFD)
    os.chdir(SURFD)
    sys.dont_write_bytecode = True
    scratch = tempfile.mkdtemp(prefix="plan-audit-")
    os.environ["TEMP"] = os.environ["TMP"] = tempfile.tempdir = scratch

    seen = {}
    real_connect = sqlite3.connect
    skip = ("CREATE", "PRAGMA", "EXPLAIN", "BEGIN", "COMMIT", "ALTER", "DROP")

    def trace(sql):
        if table in sql and not sql.lstrip().upper().startswith(skip):
            seen.setdefault(shape(sql), sql)

    def connect(*a, **k):
        conn = real_connect(*a, **k)
        conn.set_trace_callback(trace)
        return conn

    sqlite3.connect = connect
    for name in suites:
        real_stdout, sys.stdout = sys.stdout, io.StringIO()
        try:
            sys.argv = [name + ".py"]
            runpy.run_path(os.path.join(SURFD, name + ".py"), run_name="__main__")
        except SystemExit:
            pass
        except Exception as exc:
            real_stdout.write("suite %s raised %r\n" % (name, exc))
        finally:
            sys.stdout = real_stdout
        for mod in ("surfd", "admin", "rcon", "sweep", "accounts"):
            sys.modules.pop(mod, None)
        print("%-16s traced; %d statement shapes on %s" % (name, len(seen), table))
    sqlite3.connect = real_connect

    # The schema: a fresh start of the service, then the index dropped / made.
    home = tempfile.mkdtemp(prefix="plan-audit-home-", dir=scratch)
    with open(os.path.join(home, "surfd.env"), "w") as fh:
        fh.write("SURFD_KEY=testkey\n")
    os.environ.update(SURFD_HOME=home, SURFD_DB=os.path.join(home, "with.db"),
                      SURFD_ENV=os.path.join(home, "surfd.env"))
    import importlib
    import logging
    importlib.import_module("surfd")
    logging.shutdown()
    shutil.copy(os.path.join(home, "with.db"), os.path.join(home, "without.db"))
    a = real_connect(os.path.join(home, "with.db"))
    b = real_connect(os.path.join(home, "without.db"))
    b.execute("DROP INDEX IF EXISTS " + index)
    a.execute("DROP INDEX IF EXISTS " + index)
    a.execute(ddl)
    print("\n%d statements to compare, with and without %s\n" % (len(seen), index))
    moved = walks = skipped = 0
    for sh, sql in sorted(seen.items()):
        try:
            pa = "; ".join(r[3] for r in a.execute("EXPLAIN QUERY PLAN " + sql))
            pb = "; ".join(r[3] for r in b.execute("EXPLAIN QUERY PLAN " + sql))
        except sqlite3.Error:
            skipped += 1
            continue
        if pa != pb:
            moved += 1
            walk = ("SCAN %s USING INDEX %s" % (table, index)) in pa
            walks += walk
            print("%s %s\n   without: %s\n   with   : %s\n"
                  % ("WALK " if walk else "moved", sh[:240], pb[:200], pa[:200]))
    print("%d statements change plan; %d of them walk the whole index in order"
          " (%d could not be explained)" % (moved, walks, skipped))
    a.close()
    b.close()
    shutil.rmtree(scratch, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
