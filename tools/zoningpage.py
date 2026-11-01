#!/usr/bin/env python3
"""
zoningpage.py -- the data behind the site's zoning page (src/release/site/zoning.html).

Writes two site files:
    zoning.json         the maps that had no zones when this ran, with KSF's facts
    zoning-thumbs.webp  their pictures, one 128x72 cell each, 16 to a row

The page itself asks the live board (board/api/maps) which of them have zones now,
so a map a zoner publishes leaves the list without this being re-run.  Re-run it when
KSF adds maps, then publish with src/release/sitepage.ps1.

The set is P1174's worklist: every catalogue row KSF lists (`k` in src) with zoned 0,
folded second builds included, plus KEEP.  KSF facts (linear, stages, bonuses, plays,
mappers, main WR) come from ksf.surf's own API, cached per map under --cache.

    python tools/zoningpage.py                     # live catalogue from the Pi's surfd
    python tools/zoningpage.py --catalogue FILE    # a saved /api/board?maps=1 reply
    python tools/zoningpage.py --offline           # cached KSF facts only
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SURFDIR = os.path.dirname(HERE)
CATALOGUE_URL = "http://192.168.1.102:8084/api/board?maps=1"
KSF = "https://ksf.surf"
UA = "WorldOfSurf-zoningpage/1 (+https://proto.bar/ftesurf/)"
KEEP = ("surf_sinister",)       # Lex, 1 Nov: not a KSF map, but keep it on the list
CELL_W, CELL_H, COLS = 128, 72, 16

# What P1174's audit and KSF WR replay checks found for builds with a related map.
RELATED = {
    "surf_compulsive_njv_h": ("surf_compulsive", "Same world as Momentum's surf_compulsive, but KSF's timer starts 7 ticks earlier and stops 30 ticks later than Momentum's zones. Move the start and end."),
    "surf_race_final": ("surf_race", "Same world as surf_race; start and end match KSF, but KSF's WR route misses one of Momentum's stage zones and KSF's restart points sit up to ~1,700 units higher."),
    "surf_beyer2_css": ("surf_beyer2", "Same world as surf_beyer2; start and end match KSF, but one Momentum checkpoint is off KSF's WR route. 'false_start' is named 'falsebonus_start' here."),
    "surf_aquaflow_css": ("surf_aquaflow", "Different build of surf_aquaflow. The main track is close (KSF's start is left 4 ticks sooner); Momentum's bonus starts lie outside this build."),
    "surf_botanica_css": ("surf_botanica", "Restart positions differ from surf_botanica's by up to 256 units."),
    "surf_sundown_css": ("surf_sundown", "Restart positions differ from surf_sundown's by up to 30,464 units."),
    "surf_classics2_css": ("surf_classics2", "Restart 'fury_start' is missing and one of surf_classics2's stages lies outside this build."),
    "surf_echo_css": ("surf_echo", "Restarts differ from surf_echo's by up to 6,888 units; bonus 3's start lies outside this build."),
    "surf_eclipse_css": ("surf_eclipse", "Restart positions differ from surf_eclipse's by up to 1,182 units."),
    "surf_lullaby_ksf": ("surf_lullaby", "Three of surf_lullaby's restarts are missing; its end and both bonuses lie outside this build."),
    "surf_the_gloaming_css": ("surf_the_gloaming", "Restart positions differ from surf_the_gloaming's by up to 206 units."),
    "surf_cyanide_css": ("surf_cyanide", "Restarts 'dest_s1_start' and 'dest_s2_start' are missing."),
    "surf_seaside_css": ("surf_seaside", "Restarts differ from surf_seaside's by up to 31,499 units; bonus 1 lies outside this build."),
    "surf_sequoia_fix": ("surf_sequoia", "Five named restarts are offset by (-96, -352, +1472) from surf_sequoia's, but the geometry is not a pure shift. 'b3_reset' is missing."),
    "surf_shady_h": ("surf_shady", "Restart positions differ from surf_shady's by up to 53 units."),
    "surf_conserve_css": ("surf_conserve", "A different version of surf_conserve, not a drop-in."),
    "surf_sinister": ("surf_sinister_evil", "Not a KSF map. Early sections match surf_sinister_evil; later sections and restarts differ by ~16 and ~141 units."),
}


def read_catalogue(src):
    if src.startswith("http"):
        with urllib.request.urlopen(src, timeout=30) as r:
            text = r.read().decode("utf-8")
    else:
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
    if not text.startswith("FTESURF-MAPDL 1"):
        raise SystemExit("not a FTESURF-MAPDL 1 catalogue: " + src)
    rows = {}
    for line in text.splitlines():
        t = line.split()
        # dl name mode src tier kb first new mtier ktier of zoned enabled
        if len(t) == 13 and t[0] == "dl":
            rows[t[1]] = t
    return rows


class Ksf:
    def __init__(self, cache, offline):
        self.cache, self.offline, self.asked = cache, offline, 0
        os.makedirs(cache, exist_ok=True)

    def get(self, path):
        if self.offline:
            return None
        time.sleep(0.35)
        self.asked += 1
        req = urllib.request.Request(KSF + path, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except (OSError, ValueError) as exc:
            print("  ksf: %s: %s" % (path, exc), file=sys.stderr)
            return None

    def facts(self, name):
        cf = os.path.join(self.cache, name + ".json")
        try:
            with open(cf, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            pass
        rows = self.get("/api/maps/search/" + urllib.parse.quote(name))
        if rows is None:
            return {}
        row = next((r for r in rows if isinstance(r, dict) and str(r.get("name", "")).lower() == name), None)
        doc = {"found": row is not None}
        if row:
            doc.update({k: row.get(k) for k in ("isLinear", "cp_count", "b_count", "tier", "totalplaytimes")})
            doc["mappers"] = [m.get("name") or m.get("mapperName") for m in row.get("mappers") or [] if isinstance(m, dict)]
            wr = self.get("/api/maps/%s/records/zone/0/1?game=css&mode=0" % urllib.parse.quote(name))
            if isinstance(wr, list) and wr and isinstance(wr[0], dict):
                doc["wr"], doc["wr_by"] = wr[0].get("time"), wr[0].get("name")
        with open(cf + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        os.replace(cf + ".tmp", cf)
        return doc


def num(s):
    return int(s) if s.isdigit() else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalogue", default=CATALOGUE_URL)
    ap.add_argument("--gamedir", default=os.path.join(SURFDIR, "ftesurf"))
    ap.add_argument("--cache", default=os.path.join(SURFDIR, "dist", "zoning-cache"))
    ap.add_argument("--out", default=os.path.join(SURFDIR, "src", "release", "site"))
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()

    sys.path.insert(0, HERE)            # python -I leaves the script's dir off the path
    import mapthumbs
    from PIL import Image
    mapthumbs.KSFSHOTS = os.path.join(a.gamedir, "gfx", "mapshots", "ksf")
    mapthumbs.FETCHED = os.path.join(a.gamedir, "gfx", "mapshots")
    mapthumbs.SHOTS = os.path.join(a.gamedir, "screenshots")

    cat = read_catalogue(a.catalogue)
    uuid = {}                           # mapmeta.txt: meta name tier linear stages bonuses page cell thumbid ...
    with open(os.path.join(a.gamedir, "data", "mapmeta.txt"), encoding="utf-8") as fh:
        for line in fh:
            m = line.split()
            if len(m) > 8 and m[0] == "meta":
                uuid[m[1].lower()] = m[8]
    names = sorted(n for n, t in cat.items() if "k" in t[3] and t[11] == "0")
    names += [n for n in KEEP if n in cat and cat[n][11] == "0" and n not in names]
    print("%d catalogue rows, %d without zones" % (len(cat), len(names)))

    ksf = Ksf(a.cache, a.offline)
    rows, cells = [], []
    for n in names:
        t = cat[n]
        k = ksf.facts(n) if "k" in t[3] else {}
        kname = n
        if not k.get("found") and t[10] != "-" and "k" in t[3]:
            k, kname = ksf.facts(t[10]), t[10]     # a folded _css build: KSF lists it by its base name
        tier = num(t[9]) or num(t[4]) or (k.get("tier") or 0)
        linear = k.get("isLinear")
        cps, bon = k.get("cp_count") or 0, k.get("b_count") or 0
        gates = 0 if linear is None else (cps if linear else max(cps - 1, 0))
        rel = RELATED.get(n)
        row = {"n": n, "t": tier, "z": 2 + gates + 2 * bon, "c": cps, "b": bon,
               "l": None if linear is None else int(bool(linear)),
               "p": k.get("totalplaytimes") or 0,
               "m": ", ".join(x for x in k.get("mappers") or [] if x),
               "w": round(k["wr"], 2) if k.get("wr") else None, "wb": k.get("wr_by") or "",
               "of": t[10] if t[10] != "-" else "", "k": kname if k.get("found") and kname != n else "",
               "s": -1}
        if rel:
            row["d"], row["x"] = rel
        src = (mapthumbs.source_for(n, uuid.get(n, "-"), mapthumbs.MOMENTUM)
               or (t[10] != "-" and mapthumbs.source_for(t[10], uuid.get(t[10], "-"), mapthumbs.MOMENTUM)))
        if src:
            try:
                with Image.open(src) as im:
                    im = im.convert("RGB")
                    # 16:9 centre crop, then a box filter down to the cell
                    w, h = im.size
                    cw, ch = (w, w * 9 // 16) if w * 9 <= h * 16 else (h * 16 // 9, h)
                    im = im.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2))
                    cells.append(im.resize((CELL_W, CELL_H), Image.LANCZOS))
                row["s"] = len(cells) - 1
            except (OSError, ValueError) as exc:
                print("  picture %s: %s" % (src, exc), file=sys.stderr)
        rows.append(row)

    sheet = Image.new("RGB", (CELL_W * COLS, CELL_H * max(1, -(-len(cells) // COLS))), (13, 13, 17))
    for i, im in enumerate(cells):
        sheet.paste(im, ((i % COLS) * CELL_W, (i // COLS) * CELL_H))
    sheet_path = os.path.join(a.out, "zoning-thumbs.webp")
    sheet.save(sheet_path, "WEBP", quality=62, method=6)
    made = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {"v": 1, "made": made, "cell": [CELL_W, CELL_H, COLS, sheet.height // CELL_H], "rows": rows}
    with open(os.path.join(a.out, "zoning.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, separators=(",", ":"))
        fh.write("\n")
    print("%d rows, %d pictures (%d bytes), %d KSF requests" % (
        len(rows), len(cells), os.path.getsize(sheet_path), ksf.asked))


if __name__ == "__main__":
    main()
