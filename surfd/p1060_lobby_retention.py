#!/usr/bin/env python3
"""P1060: real heartbeat/SQLite stale-row retention and bounded-node falsifiers.

Run beside surfd.py, with TMPDIR under an owned test root. --expect-bug proves
that the unmodified reaper ACTED; it is not acceptance of the product behavior.
Only synthetic homes/databases/requests are used. No server or network is run.
"""
import argparse
import contextlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
NOW = 10_000_000
SOURCE = "198.51.100.20"
KEY = "OWN-p1060-key"


def fresh():
    home = Path(tempfile.mkdtemp(prefix="p1060-lobbies-"))
    (home / "surfd.env").write_text("SURFD_KEY=" + KEY + "\n", encoding="utf-8")
    os.environ.update(SURFD_HOME=str(home), SURFD_DB=str(home / "OWN.db"),
                      SURFD_ENV=str(home / "surfd.env"), SURFD_KEY=KEY,
                      SURFD_RUNS=str(home / "OWN-runs"), SURFD_RCON_PASSWORD="OWN-disabled")
    os.environ.pop("SURFD_PUBLIC_HOST", None)
    os.environ.pop("SURFD_TRUSTED", None)
    sys.modules.pop("surfd", None)
    module = importlib.import_module("surfd")
    module._p1060_db = home / "OWN.db"
    module.time = SimpleNamespace(**{name: getattr(module.time, name) for name in dir(module.time)
                                    if not name.startswith("_")})
    module.time.time = lambda: NOW
    return home, module


def seed(module, count):
    with contextlib.closing(sqlite3.connect(module._p1060_db)) as conn:
        for index in range(count):
            conn.execute("""INSERT INTO lobbies
                (node,map,players,maxplayers,addr,name,last_seen,last_used)
                VALUES(?,?,?,?,?,?,?,?)""",
                ("own-%03d" % index, "surf_ace", 0, 24,
                 "%s:%d" % (SOURCE, 30000 + index), "OWN lobby", NOW - 7200, 100 + index))
        conn.commit()


def rows(module):
    with contextlib.closing(sqlite3.connect(module._p1060_db)) as conn:
        return [tuple(row) for row in conn.execute(
            "SELECT node,addr,last_used FROM lobbies ORDER BY node")]


def beat(module, index):
    return module.app.test_client().post("/api/heartbeat", data={
        "key": KEY, "node": "own-%03d" % index, "map": "surf_ace", "players": "0",
        "max": "24", "port": str(30000 + index), "name": "OWN lobby"},
        environ_base={"REMOTE_ADDR": SOURCE})


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--expect-bug", action="store_true")
    options = args.parse_args()
    homes = []
    try:
        home, module = fresh()
        homes.append(home)
        seed(module, 12)
        before = rows(module)
        first = beat(module, 0)
        assert first.status_code == 200, first.status_code
        first_rows = rows(module)
        visible_one = module.app.test_client().get("/lobbies.json").get_json()["lobbies"]
        assert len(visible_one) == 1  # Freshness filters visibility, not retained row count.
        for index in range(1, 12):
            response = beat(module, index)
            assert response.status_code == 200, response.status_code
        all_rows = rows(module)
        visible_all = module.app.test_client().get("/lobbies.json").get_json()["lobbies"]
        assert len(visible_all) == 12

        home, capacity = fresh()
        homes.append(home)
        assert capacity.MAX_NODES == 200
        seed(capacity, capacity.MAX_NODES)
        cap_before = rows(capacity)
        existing = beat(capacity, 0)
        assert existing.status_code == 200
        unknown = beat(capacity, capacity.MAX_NODES)
        cap_after = rows(capacity)
        retained = first_rows == before and all_rows == before
        bounded = (unknown.status_code == 429 and
                   "node limit reached" in json.dumps(unknown.get_json()) and cap_after == cap_before)
        old_reaper_acted = (len(first_rows) == 1 and all_rows != before and
                            unknown.status_code == 200 and len(cap_after) < len(cap_before))
        home, racing = fresh()
        homes.append(home)
        seed(racing, racing.MAX_NODES - 1)
        race_before = rows(racing)
        ready = threading.Barrier(2)
        def request_node(index):
            ready.wait(timeout=5)
            return beat(racing, index).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(request_node, [racing.MAX_NODES - 1, racing.MAX_NODES]))
        race_after = rows(racing)
        atomic = (statuses == [200, 429] and len(race_after) == racing.MAX_NODES and
                  all(row in race_after for row in race_before))
        if options.expect_bug:
            assert old_reaper_acted, "old-code counterexample did not ACT"
        else:
            assert retained, "stale heartbeat discarded persistent lobby rows/recency"
            assert bounded, "node cap evicted retained rows or admitted an unknown node"
            assert atomic, "concurrent node admission crossed capacity or evicted retained rows"
        print(json.dumps({"passed": True, "old_code_control_ACTED": old_reaper_acted,
                          "retained_after_first_and_all12_heartbeats": retained,
                          "fresh_visibility_one_then12": True, "existing_node_updates_at_capacity": True,
                          "hard200_capacity_refuses_without_eviction": bounded,
                          "concurrent_unknown_nodes_atomic_capacity": atomic,
                          "synthetic_SQLite_and_requests_only": True,
                          "expect_bug_control_not_product_acceptance": options.expect_bug}))
    finally:
        # These exact homes were just created by this process; no install/data tree.
        for home in homes:
            shutil.rmtree(home)


if __name__ == "__main__":
    main()
