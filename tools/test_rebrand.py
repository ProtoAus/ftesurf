#!/usr/bin/env python3
"""Offline stage-1 brand/compatibility checks. Run: python tools/test_rebrand.py."""

import ast
from html.parser import HTMLParser
from pathlib import Path
import re
import struct
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "src/release/site"
sys.path.insert(0, str(ROOT / "surfd"))


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.copy = []
        self.attrs = []
        self.code = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.attrs.append((tag, dict(attrs)))
        if tag in ("code", "script", "style"):
            self.code += 1

    def handle_endtag(self, tag):
        if tag in ("code", "script", "style"):
            self.code -= 1

    def handle_data(self, text):
        if not self.code:
            self.copy.append(text)


def text(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def visible_brand(doc):
    page = Page(doc)
    return "World of Surf" in doc and not re.search(r"\bFTESurf\b|\bFTE\b", " ".join(page.copy), re.I)


class BrandTests(unittest.TestCase):
    def test_pages_and_detector_control(self):
        self.assertFalse(visible_brand('<title>FTESurf</title><p>FTE</p>'))
        for rel in ("src/release/page.template.html", "src/release/site/anticheat.html", "surfd/web/board.html"):
            with self.subTest(rel=rel):
                doc = text(rel)
                self.assertTrue(visible_brand(doc))
                self.assertRegex(doc, r"<title>World of Surf[^<]*</title>")
                self.assertIn('aria-label="World of Surf home"', doc)
                self.assertIn('favicon.svg', doc)

    def test_release_tokens_and_technical_instructions(self):
        doc = text("src/release/page.template.html")
        outside = re.sub(r"<!--LINUX-BEGIN-->.*?<!--LINUX-END-->", "", doc, flags=re.S)
        tokens = set(re.findall(r"@@([A-Z0-9_]+)@@", outside))
        self.assertEqual(tokens, {"VERSION", "FILENAME", "URL", "SIZE_HUMAN", "SIZE_BYTES", "SHA256", "DATE", "QCBUILD",
                                  "ENGINEPATCH", "LAUNCHER_URL", "LAUNCHER_SHA256"})
        self.assertEqual(set(re.findall(r"@@(LINUX_[A-Z0-9_]+)@@", doc)),
                         {"LINUX_URL", "LINUX_FILENAME", "LINUX_SIZE_HUMAN", "LINUX_SIZE_BYTES", "LINUX_SHA256", "LINUX_GLIBC",
                          "LINUX_ENGINE", "LINUX_LAUNCHER_URL", "LINUX_LAUNCHER_SHA256"})
        # P852: the launcher is the download; no wrapper-script instructions.
        self.assertIn("https://github.com/ProtoAus/ftesurf", doc)
        for legacy in ("<code>ftesurf.bat</code>", "<code>./ftesurf.sh</code>"):
            self.assertNotIn(legacy, doc)
        self.assertIn("Built on FTEQW", doc)

    def test_compatible_social_routes(self):
        # Website-path cutover is a later stage. Only the image gets a fresh key.
        for rel in ("src/release/page.template.html", "src/release/site/anticheat.html"):
            doc = text(rel)
            self.assertIn('content="https://proto.bar/ftesurf/og-worldofsurf.png"', doc)
            self.assertIn('property="og:url" content="https://proto.bar/ftesurf/', doc)
            self.assertIn('name="twitter:image" content="https://proto.bar/ftesurf/og-worldofsurf.png"', doc)
            self.assertIn('property="og:site_name" content="World of Surf"', doc)
            self.assertIn('property="og:image:width" content="1200"', doc)
            self.assertIn('property="og:image:height" content="630"', doc)

    def test_board_display_and_storage_are_distinct(self):
        js = text("surfd/web/board.js")
        self.assertIn("ranked: ['WOS', 'Set on an official World of Surf server", js)
        self.assertIn("['ranked', 'WOS']", js)
        self.assertNotRegex(js, r"\bFTESurf\b|\bFTE\b")
        self.assertEqual(len(re.findall(r"document.title = .*World of Surf", js)), 5)
        self.assertIn('class="src src-ranked">WOS</span>', text("surfd/web/board.html"))

    def test_account_rendering_and_wire_tags(self):
        import accounts
        for depth in (0, 1, 2):
            with self.subTest(depth=depth):
                doc = accounts._page(depth, "Link Steam", "<h1>Link Steam</h1>").get_data(as_text=True)
                self.assertIn('<title>Link Steam - World of Surf</title>', doc)
                self.assertIn('World of <b>Surf</b>', doc)
                self.assertIn('href="' + '../' * (depth + 1) + '"', doc)
        self.assertEqual(accounts.STATEMENT, "FTESURF-ACCT 1\nserver %s\nnonce %s\nkind %d\nkey %d\ncode %s\n")
        self.assertEqual([getattr(accounts, "TAG_" + n) for n in ("CODE", "ASK", "CONFIRM", "START", "ID", "NUMBER")],
                         ["ftesurf-code ", "ftesurf-link ", "ftesurf-confirm ", "ftesurf-start ", "ftesurf-id ", "ftesurf-number "])
        # User-facing literals must not regress; paths and signed formats may stay.
        constants = [n.value for n in ast.walk(ast.parse(text("surfd/accounts.py")))
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        self.assertFalse(any(re.search(r"\bFTESurf\b", s) and '<' in s for s in constants))

    def test_self_contained_outlined_vectors(self):
        paths = list((ROOT / "src/brand").glob("*.svg")) + [SITE / "favicon.svg", SITE / "worldofsurf-wordmark.svg"]
        self.assertGreaterEqual(len(paths), 7)
        for path in paths:
            with self.subTest(path=path.name):
                doc = ET.fromstring(path.read_bytes())
                tags = {el.tag.split('}')[-1] for el in doc.iter()}
                self.assertIn("path", tags)
                self.assertFalse(tags & {"text", "script", "image", "foreignObject", "use"})
                self.assertIn("World of Surf", path.read_text(encoding="utf-8"))
                self.assertFalse(any(k.endswith('href') for el in doc.iter() for k in el.attrib))
        gallery = ROOT / "src/brand/index.html"
        for tag, attrs in Page(gallery.read_text(encoding="utf-8")).attrs:
            target = attrs.get("src") if tag == "img" else attrs.get("href")
            if target:
                self.assertNotIn(":", target)
                self.assertTrue((gallery.parent / target).resolve().is_file(), target)

    def test_raster_dimensions(self):
        for name, size in [("og-worldofsurf.png", (1200, 630)), ("apple-touch-icon.png", (180, 180)),
                           ("worldofsurf-192.png", (192, 192)), ("worldofsurf-512.png", (512, 512))]:
            data = (SITE / name).read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), size)
        data = (ROOT / "src/brand/worldofsurf.ico").read_bytes()
        self.assertEqual(struct.unpack("<HHH", data[:6]), (0, 1, 7))
        sizes = {(data[6 + i * 16] or 256, data[7 + i * 16] or 256) for i in range(7)}
        self.assertEqual(sizes, {(n, n) for n in (16, 24, 32, 48, 64, 128, 256)})


if __name__ == "__main__":
    unittest.main()
